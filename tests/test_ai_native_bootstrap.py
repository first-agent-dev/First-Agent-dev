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
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from fa.execution.protocol import CONFIG_ID
from fa.execution.publication import render_bundle
from fa.inner_loop import workflow_controller
from fa.inner_loop.coder_loop import SessionOutcome
from fa.inner_loop.managed_acquisition import (
    INITIAL_INCREMENT_SLUG,
    BootstrapNewProjectChoice,
    BootstrapProposal,
)
from fa.inner_loop.plan_admission import PLAN_V2, parse_dispositions, snapshot_from_bytes
from fa.inner_loop.plan_semantics import PlanSemantics, parse_semantics, render_project
from fa.inner_loop.registry import ToolResult
from fa.inner_loop.tools import workflow_tool
from fa.inner_loop.tools.workflow_tool import (
    _PROJECT_SLUG_RE,
    INVOKE_WORKFLOW_SCHEMA,
    WorkflowInvocationContext,
)
from fa.inner_loop.tools.workspace_port import PortRead, WorkspacePortError
from fa.inner_loop.workflow_artifacts import FlowState
from tests.test_execution_workspace import Site
from tests.test_execution_workspace import site as site


def _payload(
    *,
    evidence: str = "TEST_REQUIRED",
    reason: str | None = None,
    contracts: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """The typed semantics a PLAN-V2 bootstrap carries (D-V2-7).

    The planner no longer writes Markdown, so the fixture is a payload and the controller
    renders it. ``evidence``/``reason`` vary the R1/R5/R6 cells; ``contracts`` lets the
    refusal oracles describe a claim the grammar will reject without restating a rule here.
    """
    invariant: dict[str, object] = {
        "number": "1",
        "kind": "HARD",
        "text": "publication requires a sealed selection.",
        "evidence": evidence,
        "reason": reason,
    }
    return {
        "intent": "Ship the demo slice.",
        "out_of_scope": "Everything outside SLICE1.",
        "questions": [],
        "invariants": [invariant],
        "scenarios": [],
        "slices": [
            {
                "number": "1",
                "name": "Foundation",
                "steps_mode": "prescriptive",
                "contracts": contracts
                or [
                    {
                        "number": "1",
                        "cls": "FUNCTIONAL",
                        "inv": "INV-1",
                        "text": "publication requires a sealed selection",
                    }
                ],
                "acceptance": [
                    {
                        "test_id": "TEST-1.1",
                        "ct": "CT-1.1",
                        "selector": "acceptance/tests/test_publish.py::test_publish",
                    }
                ],
                "kill_targets": [],
                "exit_checks": [{"check": "CHECK-1", "step": "STEP1", "test_ids": ["TEST-1.1"]}],
                "steps": [{"number": "1", "text": "publish through the sealed authority.", "check": "CHECK-1"}],
            }
        ],
    }


def _semantics(**kwargs: object) -> PlanSemantics:
    return parse_semantics(_payload(**kwargs))  # type: ignore[arg-type]


def _rendered(project_slug: str = "demo-project") -> tuple[str, str]:
    """The pair the controller would install, rendered by the production renderer."""
    files = render_project(_semantics(), project_slug=project_slug)
    return files["roadmap.md"], files["increments/increment-01-initial-plan.md"]


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
        dispositions=(),
        acquisition=None,
    )


def _choice(semantics: PlanSemantics | None = None, *, prose: str = "") -> BootstrapNewProjectChoice:
    """A PLAN-V2 choice carries semantics; the legacy route's shape stays expressible."""
    return BootstrapNewProjectChoice(
        project_slug="demo-project",
        increment_slug="foundation",
        roadmap_body="",
        increment_body=prose,
        semantics=semantics,
    )


def _requesting_semantics() -> PlanSemantics:
    """R1 shape: the plan asks for a disposition by reason and cannot name an owner."""
    return _semantics(evidence="NON_EXECUTABLE", reason="HOST_READINESS")


def test_a_v2_bootstrap_without_semantics_is_refused_before_the_authority() -> None:
    """The V2 route has no path that skips the renderer, and no path that skips the gate.

    D-V2-7 moved the "body does not parse" refusal earlier: `parse_semantics` renders the
    payload through a probe slug, so a payload that would not admit is refused inside
    `parse_acquisition_choice` and never reaches the controller at all. What the controller
    still has to refuse is the *missing* payload -- a V2 choice whose semantics were never
    produced -- and it must do so before `prepare_bundle` is touched.
    """
    ctx, refusal, detail = workflow_controller._install_bootstrap_project_with_detail(
        _v2_context(),  # type: ignore[arg-type]
        _choice(None),
        creation_authorized=True,
    )

    assert refusal is not None
    assert refusal.rule == "bootstrap-invalid-body"
    assert detail is not None
    assert (detail.validator, detail.rule, detail.severity) == ("bootstrap", "invalid-body", "FAIL")
    assert detail.operation_id is None  # nothing was installed, so there is no operation
    assert ctx.run_id == "run-bootstrap-v2"  # unchanged: nothing was bound


_EVIDENCE_PATH = "worklogs/demo-project/notes/readiness.md"
_EVIDENCE_DIGEST = "a" * 64
_EVIDENCE_REF = f"doc:{_EVIDENCE_PATH}@sha256:{_EVIDENCE_DIGEST}"


class _EvidencePort:
    """One pinned view, as far as a ``doc:`` grant is concerned."""

    def __init__(self, read: PortRead | None) -> None:
        self.read = read
        self.paths: list[str] = []

    def read_file(self, path: str, *, offset_bytes: int = 0, max_bytes: int = 1024 * 1024) -> PortRead:
        self.paths.append(path)
        if self.read is None:
            raise WorkspacePortError("denied")
        return self.read


def _granting_context(
    *,
    reviewed_at: str,
    evidence: str = _EVIDENCE_REF,
    read: PortRead | None = None,
) -> SimpleNamespace:
    context = _v2_context()
    context.dispositions = parse_dispositions(
        [{"reason": "HOST_READINESS", "owner": "W4", "evidence": evidence, "reviewed_at": reviewed_at}]
    )
    if read is not None or evidence.startswith("doc:"):
        context.acquisition = SimpleNamespace(port=_EvidencePort(read))
    return context


def test_a_requested_disposition_that_was_not_granted_never_installs() -> None:
    """R1 (E577): the plan asks, the caller grants; an ungranted request is a refusal."""
    ctx, refusal, detail = workflow_controller._install_bootstrap_project_with_detail(
        _v2_context(),  # type: ignore[arg-type]
        _choice(_requesting_semantics()),
        creation_authorized=True,
    )

    assert refusal is not None
    assert refusal.rule == "bootstrap-invalid-body"
    assert detail is not None
    assert (detail.validator, detail.rule, detail.severity) == ("bootstrap", "invalid-body", "FAIL")
    assert detail.operation_id is None  # nothing was installed
    assert ctx.run_id == "run-bootstrap-v2"


def test_a_granted_request_passes_the_pre_install_gate() -> None:
    """Proof the gate *accepted* it: the authority double is reached, and raises."""
    ctx = _granting_context(
        reviewed_at=datetime.now(UTC).date().isoformat(),
        read=PortRead(content="readiness: pass\n", sha256=_EVIDENCE_DIGEST, eof=True),
    )

    with pytest.raises(AssertionError, match="authority reached before validation"):
        workflow_controller._install_bootstrap_project_with_detail(
            ctx,  # type: ignore[arg-type]
            _choice(_requesting_semantics()),
            creation_authorized=True,
        )


def test_a_plan_cannot_own_its_own_waiver() -> None:
    """G1: the grant is not a plan field, so the bootstrap refuses the body outright."""
    ctx, refusal, detail = workflow_controller._install_bootstrap_project_with_detail(
        _granting_context(reviewed_at=datetime.now(UTC).date().isoformat()),  # type: ignore[arg-type]
        _choice(_requesting_semantics()),
        creation_authorized=True,
    )

    assert refusal is not None and refusal.rule == "bootstrap-invalid-body"
    assert detail is not None and detail.severity == "FAIL"
    assert ctx.run_id == "run-bootstrap-v2"


def test_v1_route_keeps_its_existing_authority_order() -> None:
    """The pre-install V2 check is route-scoped: a V1 bootstrap still reaches prepare."""
    legacy = _v2_context()
    legacy.plan_format = "PLAN-V1"

    with pytest.raises(AssertionError, match="authority reached before validation"):
        workflow_controller._install_bootstrap_project_with_detail(
            legacy,  # type: ignore[arg-type]
            _choice(prose="## SLICE1: Foundation\nCONTRACTS:\n  CT1 [CONSTRAINT]: holds.\nTESTS: tests/x.py\n"),
            creation_authorized=True,
        )


def test_rendered_v2_bundle_is_the_pair_admission_parses() -> None:
    """The controller validates the bodies; this proves the *rendered* files agree."""
    roadmap_body, increment_body = _rendered()
    files = render_bundle("demo-project", "foundation", roadmap_body, increment_body, created="2026-11-20")
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


def test_a_bootstrap_takes_its_identity_from_the_caller_and_the_harness() -> None:
    """CT-2.1 (E586): the planner returns content; the route supplies the names.

    The old contract let the planner write a slug that the controller then *replaced*,
    logging a warning the model never saw and the operator could not audit. Now the wire
    has no identity field at all, so this function can only fill in facts the route
    already owns -- and refuses when the caller never named a project.
    """
    proposal = BootstrapProposal(semantics=_semantics())

    assert workflow_controller._resolve_bootstrap_identity(proposal, None) is None
    choice = workflow_controller._resolve_bootstrap_identity(proposal, "chat-name")
    assert choice is not None
    assert choice.project_slug == "chat-name"
    assert choice.increment_slug == INITIAL_INCREMENT_SLUG == "initial-plan"
    assert choice.semantics is proposal.semantics  # content untouched
    # The slug is caller authority, so the *rendered* selectors must follow it.
    rendered = render_project(choice.semantics, project_slug=choice.project_slug)
    assert (
        "worklogs/chat-name/acceptance/tests/test_publish.py::test_publish"
        in rendered["increments/increment-01-initial-plan.md"]
    )


# --- CT-2.1: creation is a caller decision, proven through a real managed run --


def _bootstrap_text() -> str:
    """The only bootstrap shape the wire accepts: content, never identity (E586)."""
    return json.dumps({"kind": "BOOTSTRAP_NEW_PROJECT", "semantics": _payload()})


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
        planner_text=_bootstrap_text(),
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
        planner_text=_bootstrap_text(),
        project_slug="chat-project",
    )
    assert code == 0
    assert state is not None and state.status == "DONE"
    assert record["plan_ref"]["source_kind"] == "BOOTSTRAP"
    # CT-2.1 + E586: the caller names the project, the harness names the increment.
    assert record["plan_ref"]["workspace_relative_path"] == (
        "worklogs/chat-project/increments/increment-01-initial-plan.md"
    )
    assert (site.source / "worklogs" / "chat-project" / "roadmap.md").exists()
    assert not (site.source / "worklogs" / "sneaky-project").exists()


def _stage_task_for(slug: str | None) -> str:
    substrate = workflow_controller.AcquisitionSubstrate(
        port=object(),
        project_names=("demo-project",),
        incomplete_names=(),
        project_slug=slug,
    )
    task = workflow_controller._acquisition_stage_task(
        SimpleNamespace(acquisition=substrate),
        "do the thing",
    )
    assert task is not None
    return task


def test_a_select_only_route_is_told_it_may_only_select() -> None:
    """The planner is told which project action this call allows, and it is the same one enforced.

    A prompt that offered creation to a select-only call would produce a
    well-formed bootstrap the controller must refuse; the model would be failing a
    test it was never given the rule for.
    """
    task = _stage_task_for(None)

    assert "Project creation is NOT authorized" in task
    assert "Project creation IS authorized" not in task
    assert "Projects (SELECT_EXISTING): demo-project" in task
    assert "COLLISION" not in task


def test_a_create_route_is_told_to_author_and_never_offered_a_choice() -> None:
    """D-V2-9: the create route is an authoring stage, not a chooser (P2-3's root cause).

    The old text told the model to "return BOOTSTRAP_NEW_PROJECT with exactly that
    project_slug" while the parser had started refusing that field: a model that
    followed the instruction was guaranteed a `choice-malformed`. The contract now
    is that the create task says nothing about emitting a choice at all -- it
    describes the scaffold the harness already wrote and asks the model to fill it.
    """
    task = _stage_task_for("chat-project")

    # What must NOT be there: the payload instruction that contradicted the parser.
    assert "BOOTSTRAP_NEW_PROJECT" not in task
    assert "project_slug" not in task
    assert "COLLISION" not in task
    assert "Projects (SELECT_EXISTING)" not in task

    # What must be: the fixed identity and the files that already exist.
    assert "This run creates a new project" in task
    assert "worklogs/chat-project/roadmap.md" in task
    assert "increments/increment-01-initial-plan.md" in task
    assert "Do not emit a JSON choice" in task


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


# --- R6 (E577): a doc: grant is verified against bytes before it authorises ---


@pytest.mark.parametrize(
    ("read", "granted"),
    [
        (PortRead(content="readiness: pass\n", sha256=_EVIDENCE_DIGEST, eof=True), True),
        (None, False),  # the pinned view has no such file
        (PortRead(content="readiness: pass\n", sha256="b" * 64, eof=True), False),  # other bytes
        (PortRead(content="readiness: pass\n", sha256=_EVIDENCE_DIGEST, eof=False), False),  # not fully read
    ],
)
def test_only_a_doc_grant_whose_bytes_match_can_authorise(read: PortRead | None, granted: bool) -> None:
    """R6: the digest pins the claim, so an unverifiable reference grants nothing."""
    ctx = _granting_context(reviewed_at=datetime.now(UTC).date().isoformat(), read=read)

    if granted:
        with pytest.raises(AssertionError, match="authority reached before validation"):
            workflow_controller._install_bootstrap_project_with_detail(
                ctx,  # type: ignore[arg-type]
                _choice(_requesting_semantics()),
                creation_authorized=True,
            )
        return
    _ctx_after, refusal, detail = workflow_controller._install_bootstrap_project_with_detail(
        ctx,  # type: ignore[arg-type]
        _choice(_requesting_semantics()),
        creation_authorized=True,
    )
    assert refusal is not None and refusal.rule == "bootstrap-invalid-body"
    assert detail is not None and detail.severity == "FAIL"


def test_a_doc_grant_without_a_pinned_view_is_unresolvable() -> None:
    """No view means no bytes to check, and an unchecked digest is not evidence."""
    context = _v2_context()
    context.dispositions = parse_dispositions(
        [{"reason": "HOST_READINESS", "owner": "W4", "evidence": _EVIDENCE_REF, "reviewed_at": "2026-11-20"}]
    )

    _ctx_after, refusal, _detail = workflow_controller._install_bootstrap_project_with_detail(
        context,  # type: ignore[arg-type]
        _choice(_requesting_semantics()),
        creation_authorized=True,
    )

    assert refusal is not None and refusal.rule == "bootstrap-invalid-body"


def test_a_typed_reference_this_system_cannot_resolve_still_authorises() -> None:
    """`issue:`/`review:` are attested-with-reference, never reported as verified (R6)."""
    context = _granting_context(reviewed_at=datetime.now(UTC).date().isoformat(), evidence="issue:FIRST-42")
    assert context.acquisition is None  # nothing to read, and nothing pretends to

    with pytest.raises(AssertionError, match="authority reached before validation"):
        workflow_controller._install_bootstrap_project_with_detail(
            context,  # type: ignore[arg-type]
            _choice(_requesting_semantics()),
            creation_authorized=True,
        )
