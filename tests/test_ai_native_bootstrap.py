"""V2 bootstrap: validate the pair before the irreversible install (SLICE2).

The new-project route is where a project comes into existence, so the order of
operations is the contract: render, validate, install, read back, seal. A body
that does not parse must be refused while nothing exists yet, because the
recovery for an installed-but-refused bootstrap is forward recovery, not undo.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from fa.execution.protocol import CONFIG_ID
from fa.execution.publication import render_bundle
from fa.inner_loop import workflow_controller
from fa.inner_loop.coder_loop import SessionOutcome
from fa.inner_loop.managed_acquisition import BootstrapNewProjectChoice
from fa.inner_loop.plan_admission import PLAN_V2, snapshot_from_bytes
from fa.inner_loop.registry import ToolResult
from fa.inner_loop.tools import workflow_tool
from fa.inner_loop.tools.workflow_tool import (
    _PROJECT_SLUG_RE,
    INVOKE_WORKFLOW_SCHEMA,
    WorkflowInvocationContext,
)
from fa.inner_loop.workflow_artifacts import FlowState
from tests.test_execution_workspace import Site
from tests.test_execution_workspace import site as site

_ROADMAP_BODY = (
    "Plan-Format: AI-NATIVE-PLAN-V2\n\n"
    "## Intent\n\nShip the demo slice.\n\n"
    "## Out of scope\n\nEverything outside SLICE1.\n"
)

_INCREMENT_BODY = (
    "Plan-Format: AI-NATIVE-PLAN-V2\n\n"
    "## INVARIANTS\n"
    "### INV-1\n"
    "KIND: HARD\n"
    "TEXT: publication requires a sealed selection.\n"
    "EVIDENCE: TEST_REQUIRED\n\n"
    "## SLICE1: Foundation\n"
    "STEPS: prescriptive\n"
    "CONTRACTS:\n"
    "  CT-1.1 [FUNCTIONAL] INV: INV-1: publication requires a sealed selection\n"
    "ACCEPTANCE:\n"
    "  TEST-ID: TEST-1.1 | CT: CT-1.1 | SELECTOR: "
    "worklogs/demo-project/acceptance/tests/test_publish.py::test_publish\n"
    "STEP-EXIT-CHECKS:\n"
    "  CHECK-ID: CHECK-1 | STEP: STEP1 | TEST-ID[]: TEST-1.1\n"
    "- [ ] STEP1: publish through the sealed authority. EXIT-CHECK: CHECK-1\n"
)


class _AuthorityMustNotBeTouched:
    """Any authority call before validation is the defect this file guards."""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"authority reached before validation: {name}")


def _v2_context() -> SimpleNamespace:
    return SimpleNamespace(
        managed_execution=SimpleNamespace(
            current_revision_id="rev-1",
            client=_AuthorityMustNotBeTouched(),
        ),
        plan_format=PLAN_V2,
        deadline_mono=None,
        run_id="run-bootstrap-v2",
    )


def _choice(increment_body: str) -> BootstrapNewProjectChoice:
    return BootstrapNewProjectChoice(
        project_slug="demo-project",
        increment_slug="foundation",
        roadmap_body=_ROADMAP_BODY,
        increment_body=increment_body,
    )


def test_v2_bootstrap_pair_is_validated_before_the_irreversible_install() -> None:
    """An unparseable V2 body is refused while nothing exists — no prepare, no install."""
    ctx, refusal, detail = workflow_controller._install_bootstrap_project_with_detail(
        _v2_context(),  # type: ignore[arg-type]
        _choice(_INCREMENT_BODY.replace("## INVARIANTS", "## NOT_INVARIANTS")),
        creation_authorized=True,
    )

    assert refusal is not None
    assert refusal.rule == "bootstrap-invalid-body"
    assert detail is not None
    assert (detail.validator, detail.rule, detail.severity) == ("bootstrap", "invalid-body", "FAIL")
    assert detail.operation_id is None  # nothing was installed, so there is no operation
    assert ctx.run_id == "run-bootstrap-v2"  # unchanged: nothing was bound


def test_v1_route_keeps_its_existing_authority_order() -> None:
    """The pre-install V2 check is route-scoped: a V1 bootstrap still reaches prepare."""
    legacy = _v2_context()
    legacy.plan_format = "PLAN-V1"

    with pytest.raises(AssertionError, match="authority reached before validation"):
        workflow_controller._install_bootstrap_project_with_detail(
            legacy,  # type: ignore[arg-type]
            _choice("## SLICE1: Foundation\nCONTRACTS:\n  CT1 [CONSTRAINT]: holds.\nTESTS: tests/x.py\n"),
            creation_authorized=True,
        )


def test_rendered_v2_bundle_is_the_pair_admission_parses() -> None:
    """The controller validates the bodies; this proves the *rendered* files agree."""
    files = render_bundle(
        "demo-project",
        "foundation",
        _ROADMAP_BODY,
        _INCREMENT_BODY,
        created="2026-11-20",
    )
    roadmap_path = "worklogs/demo-project/roadmap.md"
    increment_path = "worklogs/demo-project/increments/increment-01-foundation.md"

    assert b"Plan-Format: AI-NATIVE-PLAN-V2" in files[roadmap_path]
    assert b"Plan-Format: AI-NATIVE-PLAN-V2" in files[increment_path]

    snapshot = snapshot_from_bytes(
        increment_path,
        files[increment_path],
        source_kind="BOOTSTRAP",
        format=PLAN_V2,
        roadmap=files[roadmap_path].decode("utf-8"),
    )

    assert snapshot.graph is not None
    validation = workflow_controller._validate_plan_admission(snapshot)
    assert validation.outcome == "PASS", validation.diagnostics
    assert snapshot.graph.contracts()["CT-1.1"].inv == "INV-1"


# --- CT-2.1: the chat owns the slug, the planner cannot restate it -----------


def _ctx() -> WorkflowInvocationContext:
    return WorkflowInvocationContext(
        parent_run_id="parent-1",
        config=Path("config/models.yaml"),
        workspace=Path("/tmp/workspace"),
        max_turns=3,
        run_stage_fn=lambda **_: 0,
        workflow_timeout_seconds=60,
    )


@pytest.mark.parametrize(
    ("params", "code"),
    [
        ({"task": "t", "project_action": "CREATE_NEW"}, "invalid_project_slug"),
        ({"task": "t", "project_slug": "demo"}, "invalid_project_slug"),
        ({"task": "t", "project_action": "DELETE_EVERYTHING"}, "invalid_project_action"),
        ({"task": "t", "project_action": "CREATE_NEW", "project_slug": "Demo Project"}, "invalid_project_slug"),
        ({"task": "t", "project_action": "CREATE_NEW", "project_slug": "-demo"}, "invalid_project_slug"),
    ],
)
def test_invoke_workflow_refuses_an_ambiguous_or_invalid_project_route(params: dict[str, object], code: str) -> None:
    """Slug and route are validated together, before any child run exists."""
    prepared = workflow_tool._prepare_invocation(params, _ctx(), 0)

    assert isinstance(prepared, ToolResult)
    assert prepared.error is not None and prepared.error.code == code


def test_invoke_workflow_carries_the_chat_slug_into_the_child_request() -> None:
    """A valid CREATE_NEW yields exactly the slug the caller supplied."""
    prepared = workflow_tool._prepare_invocation(
        {"task": "t", "roles": "planner", "project_action": "CREATE_NEW", "project_slug": "demo-project"},
        _ctx(),
        0,
    )

    assert not isinstance(prepared, ToolResult)
    assert prepared.project_slug == "demo-project"


def test_selecting_an_existing_project_carries_no_slug() -> None:
    """AUTO_SELECT_EXISTING can never create: it leaves the hint empty."""
    prepared = workflow_tool._prepare_invocation({"task": "t", "roles": "planner"}, _ctx(), 0)

    assert not isinstance(prepared, ToolResult)
    assert prepared.project_slug is None


def test_the_chat_slug_overrides_the_planner_slug_without_substitution() -> None:
    """The caller's project name wins; the planner's guess is recorded, not installed."""
    choice = BootstrapNewProjectChoice(
        project_slug="planner-guess",
        increment_slug="foundation",
        roadmap_body=_ROADMAP_BODY,
        increment_body=_INCREMENT_BODY,
    )

    assert workflow_controller._with_project_hint(choice, None) is choice
    assert workflow_controller._with_project_hint(choice, "planner-guess") is choice
    overridden = workflow_controller._with_project_hint(choice, "chat-name")
    assert overridden is not None
    assert overridden.project_slug == "chat-name"
    assert overridden.increment_body == choice.increment_body  # semantics untouched


# --- CT-2.1: creation is a caller decision, proven through a real managed run --


def _v2_pair(project: str) -> tuple[str, str]:
    increment = _INCREMENT_BODY.replace("worklogs/demo-project/", f"worklogs/{project}/")
    return _ROADMAP_BODY, increment


def _bootstrap_text(project: str) -> str:
    roadmap, increment = _v2_pair(project)
    return json.dumps(
        {
            "kind": "BOOTSTRAP_NEW_PROJECT",
            "project_slug": project,
            "increment_slug": "foundation",
            "roadmap_body": roadmap,
            "increment_body": increment,
        }
    )


def _run_case(
    site: Site,
    tmp_path: Path,
    *,
    child_run_id: str,
    planner_text: str,
    project_slug: str | None,
    roles: list[str] | None = None,
) -> tuple[int, FlowState | None, dict[str, Any], str]:
    """Run one real managed child and return its exit code, state, record, revision."""
    from .test_admission_v2_provenance import _eval_pass_stage, _managed_child_env, _read_admission

    # Each case gets its own authority state: the journal is keyed by request id
    # and lives under `state_root`, so a shared one would make the second
    # registration a replay of the first.
    case_dir = tmp_path / child_run_id
    case_site = Site(case_dir / "protected", site.roots, site.source)
    with _managed_child_env(case_site, case_dir, child_run_id=child_run_id) as (
        managed,
        _publisher,
        child_ctx,
        _yaml,
    ):
        initial_rev = managed.current_revision_id

        def stage_fn(args: argparse.Namespace, **kwargs: Any) -> int:
            role = str(getattr(args, "role", ""))
            sink = kwargs.get("outcome_sink")
            if role == "planner" and isinstance(sink, list):
                sink.append(SessionOutcome(0, "stopped_by_llm", 1, planner_text))
            elif role == "eval":
                return _eval_pass_stage(sink)
            return 0

        code, state = workflow_controller.run_workflow(
            roles=roles or ["planner", "coder"],
            task="ct-2.1",
            per_role_task={},
            mode="linear",
            max_repairs=0,
            max_replans=0,
            run_id=child_ctx.run_id,
            config=_yaml,
            workspace=site.source,
            max_turns=2,
            output_mode="quiet",
            run_stage_fn=stage_fn,
            run_context=child_ctx,
            managed_execution=managed,
            acquisition=workflow_controller.AcquisitionSubstrateRequest(project_slug=project_slug),
        )
        record = _read_admission(child_ctx.run_log_dir, child_ctx.run_id)
        return code, state, record, str(managed.current_revision_id) + f"|{initial_rev}"


def test_chat_slug_and_explicit_route_are_required_for_new_project(site: Site, tmp_path: Path) -> None:
    """CT-2.1: only a caller-authorized create route may install, under the caller's name.

    Three facts, each proven against the real authority rather than a mocked DTO:
    a select-only call cannot create even when the planner asks; a create call
    cannot be satisfied by an existing project; and when both name a project the
    caller's name is the one that is installed.
    """
    # 1. Select-only route: a well-formed bootstrap reply is refused, nothing installs.
    code, state, record, revisions = _run_case(
        site,
        tmp_path,
        child_run_id="ct21-select-route",
        planner_text=_bootstrap_text("sneaky-project"),
        project_slug=None,
    )
    current_rev, initial_rev = revisions.split("|")
    assert code == 2
    assert state is not None
    assert state.blocked_reason == "plan-ref/project-route-mismatch"
    assert record["status"] == "BLOCKED"
    assert record["plan_ref"] is None
    attempt = record["attempts"][-1]
    assert (attempt["diagnostics"][0]["validator"], attempt["diagnostics"][0]["rule"]) == (
        "selection",
        "project-route-mismatch",
    )
    assert attempt["operation_id"] is None and attempt["bundle_sha256"] is None
    assert current_rev == initial_rev  # the authority's revision never moved
    assert not (site.source / "worklogs" / "sneaky-project").exists()

    # 2. Create route answered by an existing selection: refused, not redirected.
    from .test_admission_v2_provenance import _VALID_INCREMENT, _write_project_files

    _write_project_files(site.source, "demo-project", _VALID_INCREMENT)
    code, state, record, _revisions = _run_case(
        site,
        tmp_path,
        child_run_id="ct21-create-route",
        planner_text=json.dumps({"kind": "SELECT_EXISTING", "project_slug": "demo-project", "increment_id": "I01"}),
        project_slug="wanted-new-project",
    )
    assert code == 2
    assert state is not None
    assert state.blocked_reason == "plan-ref/project-route-mismatch"
    assert record["status"] == "BLOCKED"
    assert record["plan_ref"] is None

    # 3. Both named a project: the caller's slug is the one that exists afterwards.
    code, state, record, _revisions = _run_case(
        site,
        tmp_path,
        child_run_id="ct21-caller-slug",
        planner_text=_bootstrap_text("planner-guess"),
        project_slug="chat-project",
    )
    assert code == 0
    assert state is not None and state.status == "DONE"
    assert record["plan_ref"]["source_kind"] == "BOOTSTRAP"
    assert record["plan_ref"]["workspace_relative_path"] == (
        "worklogs/chat-project/increments/increment-01-foundation.md"
    )
    assert (site.source / "worklogs" / "chat-project" / "roadmap.md").exists()
    assert not (site.source / "worklogs" / "planner-guess").exists()


@pytest.mark.parametrize(
    ("slug", "stated", "absent"),
    [
        (None, "Project creation is NOT authorized", "Project creation IS authorized"),
        ("chat-project", "Project creation IS authorized", "Project creation is NOT authorized"),
    ],
)
def test_the_acquisition_task_states_the_route_the_controller_enforces(
    slug: str | None, stated: str, absent: str
) -> None:
    """The planner is told which project action this call allows, and it is the same one enforced.

    A prompt that offers creation to a select-only call would produce a well-formed
    bootstrap that the controller must refuse; the model would be failing a test it
    was never given the rule for.
    """
    substrate = workflow_controller.AcquisitionSubstrate(
        port=object(),  # type: ignore[arg-type]
        project_names=("demo-project",),
        incomplete_names=(),
        project_slug=slug,
    )
    task = workflow_controller._acquisition_stage_task(
        SimpleNamespace(acquisition=substrate),  # type: ignore[arg-type]
        "do the thing",
    )

    assert task is not None
    assert stated in task
    assert absent not in task
    assert "Projects (SELECT_EXISTING): demo-project" in task
    if slug is not None:
        assert f"caller: {slug}" in task
        assert "COLLISION" in task  # the no-clobber warning belongs to the creating route only
    else:
        assert "COLLISION" not in task


# --- D2: one slug grammar, imported rather than restated ---------------------


_SLUG_CORPUS = (
    "a",
    "a1",
    "auth-service",
    "a--b",
    "1project",
    "-a",
    "a-",
    "A",
    "Ab",
    "a_b",
    "a" * 48,
    "a" * 49,
    "worklogs",
)


@pytest.mark.parametrize("candidate", _SLUG_CORPUS)
def test_the_pre_child_slug_check_accepts_exactly_what_the_authority_accepts(candidate: str) -> None:
    """CT-2.1: the tool must not invent a second slug grammar.

    Two hand-written copies diverged once: `1project`/`a--b` passed the tool and
    were refused by `_install_prepare`, while `a` — a legal name — was refused
    before a child run existed. The authority's `CONFIG_ID` document is the only
    definition.

    The production path is what is asserted: `_prepare_invocation` itself, not a
    copy of its predicate. An earlier version of this test restated the rule and
    survived the mutant that deleted the length check.
    """
    authority = re.compile(str(CONFIG_ID["pattern"]))
    accepted_by_authority = bool(authority.fullmatch(candidate)) and len(candidate) <= int(CONFIG_ID["maxLength"])

    prepared = workflow_tool._prepare_invocation(
        {"task": "t", "roles": "planner", "project_action": "CREATE_NEW", "project_slug": candidate},
        _ctx(),
        0,
    )

    if accepted_by_authority:
        assert not isinstance(prepared, ToolResult), candidate
        assert prepared.project_slug == candidate
    else:
        assert isinstance(prepared, ToolResult), candidate
        assert prepared.error is not None and prepared.error.code == "invalid_project_slug"


def test_the_tool_schema_publishes_the_authority_slug_bound() -> None:
    """A schema bound that disagrees with the validator is a lie in the tool contract."""
    slug_schema = INVOKE_WORKFLOW_SCHEMA["properties"]["project_slug"]

    assert _PROJECT_SLUG_RE.pattern == str(CONFIG_ID["pattern"])
    assert slug_schema["maxLength"] == CONFIG_ID["maxLength"]
