"""V2 bootstrap: validate the pair before the irreversible install (SLICE2).

The new-project route is where a project comes into existence, so the order of
operations is the contract: render, validate, install, read back, seal. A body
that does not parse must be refused while nothing exists yet, because the
recovery for an installed-but-refused bootstrap is forward recovery, not undo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest import mock

import pytest

from fa.execution.protocol import CONFIG_ID
from fa.inner_loop import workflow_controller
from fa.inner_loop.coder_loop import SessionOutcome
from fa.inner_loop.managed_acquisition import INITIAL_INCREMENT_SLUG
from fa.inner_loop.plan_admission import PLAN_V2, PlanRefError, parse_dispositions, snapshot_from_bytes
from fa.inner_loop.plan_v2 import EvidenceMode, contract_evidence, parse_plan
from fa.inner_loop.project_metadata import MetadataError, check_project_metadata
from fa.inner_loop.project_scaffold import scaffold_files, scaffold_paths
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

#: The body the planner is expected to author into the scaffold: one invariant, one
#: slice, one contract, one acceptance entry. Kept as a format string so a test can
#: point the selectors at the project it actually published.
_AUTHORED_BODY = (
    "\n## INVARIANTS\n### INV-1\n"
    "TEXT: the initial boundary holds.\nEVIDENCE: TEST_REQUIRED\n"
    "\n## SLICE1: Foundation\n\nSTEPS: outcome\n\n"
    "CONTRACTS:\n"
    "  CT-1.1 [CONSTRAINT] INV: INV-1: the initial boundary holds.\n\n"
    "ACCEPTANCE:\n"
    "  TEST-ID: TEST-1.1 | CT: CT-1.1 | "
    "SELECTOR: worklogs/{slug}/acceptance/tests/test_initial.py::test_initial\n"
)


def _requiring_pair() -> tuple[str, str]:
    """A scaffolded pair whose plan *requests* a disposition and grants itself none."""
    files = scaffold_files("waiver-project", created="2026-11-20")
    # The waiver the R1 test needs: an invariant the plan *declares it cannot test*.
    # `DISPOSITION-REASON` is the request; no owner and no evidence reference, because
    # those are the caller's to supply (R1) -- and this test supplies none.
    body = (
        "\n## INVARIANTS\n### INV-1\n"
        "TEXT: the host is ready.\nEVIDENCE: NON_EXECUTABLE\nDISPOSITION-REASON: HOST_READINESS\n"
        "\n## SLICE1: Foundation\n\nSTEPS: outcome\n\n"
        "CONTRACTS:\n"
        "  CT-1.1 [CONSTRAINT] INV: INV-1: the host is ready.\n\n"
        "ACCEPTANCE:\n"
        "  TEST-ID: TEST-1.1 | CT: CT-1.1 | "
        "SELECTOR: worklogs/waiver-project/acceptance/tests/test_initial.py::test_initial\n"
    )
    increment = files["worklogs/waiver-project/increments/increment-01-initial-plan.md"].replace(
        "slices: 0", "slices: 1"
    ) + body
    return files["worklogs/waiver-project/roadmap.md"], increment


_EVIDENCE_DIGEST = "a" * 64


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


def test_a_doc_grant_must_describe_the_bytes_in_the_pinned_view() -> None:
    """R6: the digest pins the claim, so an unverifiable reference grants nothing.

    D-V2-9 deleted the installer this used to live in, but the property is not an
    install-time courtesy -- it is the only thing that makes a ``doc:`` grant a
    claim about real bytes -- so the authoring route verifies it just the same.
    """
    declaration = parse_dispositions(
        [
            {
                "reason": "HOST_READINESS",
                "owner": "W4",
                "evidence": f"doc:evidence/readiness.md@sha256:{_EVIDENCE_DIGEST}",
                "reviewed_at": "2026-11-20",
            }
        ]
    )

    # Bytes that match the declared digest: the grant stands.
    matching = _EvidencePort(PortRead(content="readiness: pass\n", sha256=_EVIDENCE_DIGEST, eof=True))
    assert workflow_controller._granted_dispositions(matching, declaration) == declaration

    # Bytes that differ: refused, and the rule names *which* fact failed.
    mismatched = _EvidencePort(PortRead(content="readiness: pass\n", sha256="0" * 64, eof=True))
    with pytest.raises(PlanRefError) as refusal:
        workflow_controller._granted_dispositions(mismatched, declaration)
    assert refusal.value.rule == "disposition-evidence-mismatch"


def test_a_doc_grant_that_the_view_cannot_hold_is_refused_not_trusted() -> None:
    """A missing artifact is a refusal: the reference may not outrun the revision."""
    declaration = parse_dispositions(
        [
            {
                "reason": "HOST_READINESS",
                "owner": "W4",
                "evidence": f"doc:evidence/absent.md@sha256:{_EVIDENCE_DIGEST}",
                "reviewed_at": "2026-11-20",
            }
        ]
    )
    with pytest.raises(PlanRefError) as refusal:
        workflow_controller._granted_dispositions(_EvidencePort(None), declaration)
    assert refusal.value.rule == "disposition-evidence-missing"


def test_a_plan_cannot_own_its_own_waiver() -> None:
    """R1: an unbound ``NON_EXECUTABLE`` invariant is a request, not an attestation.

    The plan names why it cannot test a claim; only the caller's declaration supplies
    the owner. Grading the bare request as attested would publish a verdict nobody
    gave, so `contract_evidence` must read an owner-less invariant as uncovered.
    """
    roadmap, increment = _requiring_pair()
    graph = parse_plan(roadmap=roadmap, increment=increment)
    waiver = graph.invariants[0]
    assert waiver.evidence == "NON_EXECUTABLE"
    assert waiver.owner is None  # the plan asked; nobody granted

    graded = contract_evidence(graph)
    assert EvidenceMode.ATTESTED not in graded.values()

def test_admission_refuses_documents_whose_front_matter_disagrees() -> None:
    """D-V2-9.3 is a *check inside admission*, not advice in a docstring.

    The scaffold ships valid metadata, so a passing authoring test cannot tell whether
    admission verified anything at all: delete the call and the happy path still goes
    green (this test exists because a mutant proved exactly that). The negative case is
    the observable one -- an author who renames the roadmap id, or marks the increment
    shipped, must be refused *before* the coder, under the metadata rule.
    """
    for documents, why in (
        ({"roadmap_id": "RM-other-project"}, "the roadmap id disagrees with the directory name"),
        ({"active-increment": "I07"}, "the roadmap points at an increment that is not I01"),
    ):
        files = scaffold_files("meta-project", created="2026-11-20")
        roadmap_path = "worklogs/meta-project/roadmap.md"
        increment_path = "worklogs/meta-project/increments/increment-01-initial-plan.md"
        roadmap = files[roadmap_path]
        increment = files[increment_path]
        roadmap = roadmap.replace(
            "Roadmap-ID: RM-meta-project", f"Roadmap-ID: {documents.get('roadmap_id', 'RM-meta-project')}"
        )
        roadmap = roadmap.replace(
            "active-increment: I01", f"active-increment: {documents.get('active-increment', 'I01')}"
        )

        with pytest.raises(MetadataError):
            check_project_metadata({roadmap_path: roadmap, increment_path: increment})
        assert why


def test_the_scaffold_is_a_pair_the_metadata_check_and_the_grammar_accept() -> None:
    """The harness's own half must be *admissible prose*, or every authoring run fails.

    D-V2-9 replaced render-then-install with write-scaffold-then-author, so the property
    to prove moved: it is no longer "the renderer's output parses" but "the scaffold the
    harness writes is a legal document envelope" -- real front matter, closed key set,
    the V2 marker, and one increment file whose metadata names the initial plan.
    """
    files = scaffold_files("demo-project", created="2026-11-20")
    roadmap_path = "worklogs/demo-project/roadmap.md"
    increment_path = "worklogs/demo-project/increments/increment-01-initial-plan.md"

    # The metadata table accepts both halves as written -- no authoring required.
    check_project_metadata({roadmap_path: files[roadmap_path], increment_path: files[increment_path]})

    # And the grammar accepts the envelope once a slice body exists (the planner's half).
    body = (
        "\n## INVARIANTS\n### INV-1\n"
        "TEXT: the initial boundary holds.\nEVIDENCE: TEST_REQUIRED\n"
        "\n## SLICE1: Foundation\n\nSTEPS: outcome\n\n"
        "CONTRACTS:\n"
        "  CT-1.1 [CONSTRAINT] INV: INV-1: the initial boundary holds.\n\n"
        "ACCEPTANCE:\n"
        "  TEST-ID: TEST-1.1 | CT: CT-1.1 | "
        "SELECTOR: worklogs/demo-project/acceptance/tests/test_initial.py::test_initial\n"
    )
    increment = files[increment_path].replace("slices: 0", "slices: 1") + body
    snapshot = snapshot_from_bytes(
        increment_path,
        increment.encode("utf-8"),
        source_kind="BOOTSTRAP",
        format=PLAN_V2,
        roadmap=files[roadmap_path],
    )

    assert snapshot.graph is not None
    assert workflow_controller._validate_plan_admission(snapshot).outcome == "PASS"
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
    """CT-2.1 (E586): the route supplies the names, and nothing else can.

    The old contract let the planner write a slug that the controller then *replaced*,
    logging a warning the model never saw and the operator could not audit. D-V2-9 went
    further: the wire has no bootstrap shape at all, and the scaffold the harness writes
    inside the stage is the only thing that names the project. The property worth
    keeping is the one below -- the caller's slug reaches every rendered path, so a plan
    cannot be authored against a project other than the one that was asked for.
    """
    files = scaffold_files("chat-name", created="2026-11-21")

    assert set(files) == set(scaffold_paths("chat-name"))
    # The increment the harness owns, named under the caller's slug.
    assert f"worklogs/chat-name/increments/increment-01-{INITIAL_INCREMENT_SLUG}.md" in files
    # And every path it emits is under that slug -- no second identity source.
    assert all(path.startswith("worklogs/chat-name/") for path in files)


# --- CT-2.1: creation is a caller decision, proven through a real managed run --


def _bootstrap_text() -> str:
    """The retired bootstrap shape, verbatim: a select-only route must refuse it.

    Kept as a literal rather than built from a type, because the point of the case is
    that the *wire* value is gone (D-V2-9) and only the refusal remains.
    """
    return json.dumps({"kind": "BOOTSTRAP_NEW_PROJECT", "semantics": {}})


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
    # 1. Select-only route: the retired bootstrap shape is refused, nothing installs.
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
    # D-V2-9 made the refusal earlier and more precise: the retired shape is refused
    # where the model's text is read, so the run never reaches a route contradiction.
    # The stage fails on its own choice error rather than exiting with a controller
    # refusal -- the operator still sees one closed rule and nothing was installed.
    assert state.blocked_reason == "stage 'planner' exited 2"
    assert record["status"] == "BLOCKED"
    assert record["plan_ref"] is None
    attempt = record["attempts"][-1]
    assert (attempt["diagnostics"][0]["validator"], attempt["diagnostics"][0]["rule"]) == (
        "bootstrap",
        "retired-choice",
    )
    assert current_rev == initial_rev  # the authority's revision never moved
    assert not (site.source / "worklogs" / "sneaky-project").exists()

    # 2. Create route: the stage is an authoring stage, so a selection reply has no
    #    reader. What the run refuses on is the absence of authored documents, not on
    #    the reply's shape -- D-V2-9 removed the wire, so there is nothing to parse and
    #    nothing a reply can redirect. The caller's project is not created either way.
    code, state, record, _revisions = _run_case(
        site,
        tmp_path,
        child_run_id="ct21-create-route",
        planner_text=json.dumps({"kind": "SELECT_EXISTING", "project_slug": "demo-project", "increment_id": "I01"}),
        project_slug="wanted-new-project",
    )
    assert code == 2
    assert state is not None
    assert state.blocked_reason == "plan-ref/bootstrap-invalid-body"
    # A refusal is BLOCKED with its rule; nothing was authored, so there is no plan
    # ref to record either.
    assert record["status"] == "BLOCKED"
    assert record["plan_ref"] is None
    assert not (site.source / "worklogs" / "wanted-new-project").exists()

    # 3. The authoring route is proved separately, by
    #    `test_the_authoring_stage_publishes_and_admits_the_project`: under D-V2-9 the
    #    planner writes documents through a stage port, and a planner *saying*
    #    something can no longer prove a project was created.


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


def test_the_authoring_stage_publishes_and_admits_the_project(site: Site, tmp_path: Path) -> None:
    """D-V2-9 end to end: scaffold, authored documents, one publication, then admission.

    This is the create route's whole contract, and it is deliberately *not* driven
    by a planner payload: under D-V2-9 the planner writes documents through the
    stage's own port. A payload-shaped double would still pass if the route
    regressed to rendering, which is why the oracle runs the real stage machinery
    (`_run_cli_stage`) against the real authority and then asserts on the revision
    and the admitted plan.

    Four facts, in the order they must happen:

    1. the harness scaffold exists in the published revision (`roadmap.md` first,
       the placeholder test module, both `README.md` carriers);
    2. the planner's bytes are in that same revision -- one publication, not two;
    3. admission bound the pair *after* the publication, so the coder is not
       dispatchable against an unadmitted revision (D-V2-8);
    4. the project is named by the caller and the increment by the harness.
    """
    import argparse as _argparse

    from fa import cli as _cli
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind
    from fa.inner_loop.project_scaffold import scaffold_files, scaffold_paths
    from tests.test_admission_v2_provenance import _managed_child_env

    slug = "auto-project"

    # Fill the scaffold's empty bodies rather than replace the files: the
    # frontmatter is the harness's half (D-V2-9.3), and overwriting it would be a
    # test that proves the planner may rewrite identity -- the opposite of the rule.
    scaffold = scaffold_files(slug, created="2026-11-21")
    roadmap_scaffold = scaffold[f"worklogs/{slug}/roadmap.md"]
    increment_scaffold = scaffold[f"worklogs/{slug}/increments/increment-01-{INITIAL_INCREMENT_SLUG}.md"]
    authored = {
        "roadmap.md": roadmap_scaffold.replace(
            "## Intent\n\n## Out of scope\n",
            "## Intent\n\nBuild the demo slice cleanly.\n\n## Out of scope\n\nEverything outside SLICE1.\n",
        ),
        f"increments/increment-01-{INITIAL_INCREMENT_SLUG}.md": increment_scaffold.replace(
            "slices: 0", "slices: 1"
        )
        + _AUTHORED_BODY.format(slug=slug),
    }

    case_dir = tmp_path / "authoring"
    case_site = Site(case_dir / "protected", site.roots, site.source)
    with _managed_child_env(case_site, case_dir, child_run_id="ct28-authoring") as (
        managed,
        _publisher,
        child_ctx,
        _yaml,
    ):
        base_rev = managed.current_revision_id
        seen: dict[str, object] = {}

        def build_registry(workspace_io: object, _executor: object, _lease: object) -> object:
            seen["port"] = workspace_io
            return object()  # the stage's tools are irrelevant; `drive` writes the bytes

        def drive(_registry: object) -> SessionOutcome:
            # Fill the scaffold the harness just wrote. The read-then-write is the
            # planner's own loop too: `expected_sha256` is what makes a write an
            # *update* rather than a create (`None` means expected absence), and the
            # scaffold means these files already exist.
            port = seen["port"]
            for relative, body in authored.items():
                path = f"worklogs/{slug}/{relative}"
                port.write_file(path, body, expected_sha256=port.read_file(path).sha256)
            # Capture inside `drive`: the port is released when the stage settles,
            # so a read after `_run_cli_stage` returns would be a closed view.
            seen["wrote"] = {
                path: port.read_file(path).content for path in (f"worklogs/{slug}/{rel}" for rel in authored)
            }
            seen["scaffold"] = {path: port.read_file(path).content for path in scaffold_paths(slug)}
            return SessionOutcome(0, "stopped_by_llm", 1, "")

        dispatch = PlannerDispatch(
            PlannerDispatchKind.CREATE_NEW_PROJECT, child_ctx.run_id, authoring_root=f"worklogs/{slug}"
        )
        outcome, released = _cli._run_cli_stage(
            # The workflow-owner path: `_managed_execution` on args is how a
            # controller-driven stage reuses the run's writer instead of
            # composing a second one.
            args=_argparse.Namespace(_managed_execution=managed),
            run_context=child_ctx,
            run_id=child_ctx.run_id,
            run_log_dir=tmp_path / "run-log",
            session_db=None,
            log=SimpleNamespace(path=tmp_path / "events.jsonl"),
            workspace=site.source,
            role="planner",
            plan_ref=None,
            planner_dispatch=dispatch,
            build_registry=build_registry,
            drive=drive,
        )
        assert outcome is not None and outcome.exit_code == 0
        assert released
        published = managed.current_revision_id
        assert published != base_rev, "the stage published nothing"

        # 1 + 2: one revision holds both the scaffold and the planner's bytes, and
        # the bytes read back are the ones `drive` wrote -- captured in-stage because
        # the view is released the moment the stage settles.
        assert set(seen["scaffold"]) == set(scaffold_paths(slug))
        assert all(seen["scaffold"].values()), "a scaffold file is empty"
        for relative, body in authored.items():
            assert seen["wrote"][f"worklogs/{slug}/{relative}"] == body

        # 3: admission runs against the published revision and binds the pair.
        bound, refusal = _admit_in(case_site, child_ctx, managed, _yaml, slug)
        assert refusal is None, f"admission refused the published project: {refusal}"
        assert bound.admission is not None and bound.admission.snapshot.format == PLAN_V2
        assert bound.admission.snapshot.graph is not None

        # 4: the caller named the project, the harness named the increment.
        assert bound.managed_plan_ref is not None
        assert bound.managed_plan_ref.workspace_relative_path == (
            f"worklogs/{slug}/increments/increment-01-{INITIAL_INCREMENT_SLUG}.md"
        )


def test_admission_calls_the_metadata_check_it_documents(tmp_path: Path) -> None:
    """D-V2-9.3, pinned: the cross-check runs *inside* admission.

    `test_admission_refuses_documents_whose_front_matter_disagrees` proves the table
    refuses; it does not prove admission consults it. That gap is not hypothetical --
    a mutant that emptied the call survived the whole bank, because the scaffold's own
    front matter is valid and the happy path cannot tell the difference. Here the
    pinned view returns a pair whose roadmap names another project, everything else is
    a real scaffold, and the only rule that can produce the refusal is the metadata one.
    """
    from fa.inner_loop.workflow_controller import _admit_published_project

    scaffold = scaffold_files("meta-project", created="2026-11-21")
    increment_path = f"worklogs/meta-project/increments/increment-01-{INITIAL_INCREMENT_SLUG}.md"
    # The disagreement the grammar cannot see: the increment names a different roadmap
    # than the one in the directory it lives in. Both documents still parse, so the
    # only rule that can refuse this pair is the metadata cross-check.
    increment = (
        scaffold[increment_path].replace("slices: 0", "slices: 1")
        + _AUTHORED_BODY.format(slug="meta-project")
    ).replace("Roadmap-ID: RM-meta-project", "Roadmap-ID: RM-other-project")
    documents = {
        "worklogs/meta-project/roadmap.md": scaffold["worklogs/meta-project/roadmap.md"],
        increment_path: increment,
    }

    ctx = workflow_controller.WorkflowContext(
        run_id="meta-check",
        base_task="t",
        per_role_task={},
        artifact_paths=workflow_controller.workflow_artifact_paths("meta-check", base_dir=tmp_path / "logs"),
        config=tmp_path / "models.yaml",
        workspace=tmp_path,
        max_turns=1,
        output_mode="quiet",
        managed_execution=cast("Any", object()),
        project_hint="meta-project",
    )
    substrate = workflow_controller.AcquisitionSubstrate(port=_DocumentPort(documents), project_names=())

    with mock.patch.object(workflow_controller, "_pinned_acquisition_substrate", _yield(substrate)):
        _bound, refusal = _admit_published_project(ctx)

    assert refusal is not None, "admission did not consult the metadata table"
    assert refusal.rule == "bootstrap-invalid-metadata"


class _DocumentPort:
    """A pinned view holding exactly the documents it was given."""

    def __init__(self, documents: dict[str, str]) -> None:
        self.documents = documents

    def read_file(self, path: str, *, offset_bytes: int = 0, max_bytes: int = 1024 * 1024) -> PortRead:
        key = path if path.startswith("/") else f"/{path}"
        content = self.documents.get(key, self.documents.get(path))
        if content is None:
            raise WorkspacePortError("denied")
        return PortRead(content=content, sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(), eof=True)


def _yield(substrate: object) -> Any:
    """A stand-in for `_pinned_acquisition_substrate` that yields one substrate."""

    @contextmanager
    def _cm(_ctx: object) -> Any:
        yield substrate

    return _cm


def test_rejected_create_leaves_no_project_and_no_reader_sees_bytes(site: Site, tmp_path: Path) -> None:
    """CT-2.9 (D-V2-8): publication is not admission, and a refusal is not a publication.

    The authoring stage writes real bytes into a real WRITE view. If it settles
    *rejected*, those bytes must not become a revision: the canonical tree gains no
    `worklogs/<slug>/`, and no reader pin can see what the planner wrote. This is the
    difference between "the work was lost" and "the work is lying around unpublished
    waiting for the next run to trip over it"; D-V2-9.1 chose the first deliberately,
    which is why there is no observable half-written tree.
    """
    import argparse as _argparse

    from fa import cli as _cli
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind
    from fa.inner_loop.project_scaffold import scaffold_files
    from tests.test_admission_v2_provenance import _managed_child_env

    slug = "rejected-project"
    authored = scaffold_files(slug, created="2026-11-21")
    roadmap_path = f"worklogs/{slug}/roadmap.md"

    case_dir = tmp_path / "rejected"
    case_site = Site(case_dir / "protected", site.roots, site.source)
    with _managed_child_env(case_site, case_dir, child_run_id="ct29-rejected") as (
        managed,
        _publisher,
        child_ctx,
        _yaml,
    ):
        base_rev = managed.current_revision_id
        wrote: dict[str, str] = {}

        def build_registry(workspace_io: object, _executor: object, _lease: object) -> object:
            return workspace_io

        def drive(port: object) -> SessionOutcome:
            # Write like a planner would, then fail: the stage is refused *after* the
            # bytes exist in the view, which is exactly the case that must not leak.
            for path, content in authored.items():
                # The harness already wrote the scaffold, so each write is an update:
                # `expected_sha256=None` would mean "expect absence" and be refused.
                current = port.read_file(path).sha256  # type: ignore[attr-defined]
                port.write_file(path, content, expected_sha256=current)  # type: ignore[attr-defined]
                wrote[path] = content
            return SessionOutcome(exit_code=2, stop_reason="error", turns=1, final_text="failed")

        dispatch = PlannerDispatch(
            PlannerDispatchKind.CREATE_NEW_PROJECT, child_ctx.run_id, authoring_root=f"worklogs/{slug}"
        )
        outcome, released = _cli._run_cli_stage(
            args=_argparse.Namespace(_managed_execution=managed),
            run_context=child_ctx,
            run_id=child_ctx.run_id,
            run_log_dir=tmp_path / "run-log",
            session_db=None,
            log=SimpleNamespace(path=tmp_path / "events.jsonl"),
            workspace=site.source,
            role="planner",
            plan_ref=None,
            planner_dispatch=dispatch,
            build_registry=build_registry,
            drive=drive,
        )

        # The bytes really were written -- otherwise this test would pass for the
        # wrong reason, on a stage that never got far enough to write anything.
        assert wrote[roadmap_path] == authored[roadmap_path]
        assert outcome is not None and outcome.exit_code != 0
        assert released
        # 1. Nothing was published: the canonical revision never moved.
        assert managed.current_revision_id == base_rev
        # 2. And no reader pin can reach what was written: the rejected view is gone,
        #    so a fresh pin sees the pre-stage tree, not the planner's bytes.
        probe_ctx = _rejected_ctx(case_site, child_ctx, _yaml, managed)
        with workflow_controller._pinned_acquisition_substrate(probe_ctx) as probe:
            assert probe is not None, "the pre-stage revision should still be readable"
            with pytest.raises(WorkspacePortError):
                probe.port.read_file(roadmap_path)

    # 3. The canonical tree has no project either -- the refusal was not a partial install.
    assert not any(
        (root / "worklogs" / slug).exists() for root in (site.source, *site.roots.iterdir())
    )


def _rejected_ctx(case_site: Site, child_ctx: Any, yaml_path: Path, managed: Any) -> Any:
    """A context that pins the *current* revision, for asking what survived."""
    return workflow_controller.WorkflowContext(
        run_id=child_ctx.run_id,
        base_task="ct-2.9",
        per_role_task={},
        artifact_paths=workflow_controller.workflow_artifact_paths(
            child_ctx.run_id, base_dir=child_ctx.run_log_dir
        ),
        config=yaml_path,
        workspace=case_site.source,
        max_turns=1,
        output_mode="quiet",
        managed_execution=managed,
    )


def test_a_create_new_repair_may_write_only_the_paths_a_refusal_can_be_fixed_in(tmp_path: Path) -> None:
    """D-V2-9.8/P4-3: the repair scope reaches through the *real* writer, from the real list.

    Three things were wrong at once here, and each one hides the others:

    * the scope was a hand-copied tuple, so it could drift from the dispatch's;
    * it named only the plan and the question record, so a missing test -- the *common*
      refusal under D-V2-10 -- could not be fixed by any repair;
    * and because `is_path_within_allowlist` is strictly-descendant, naming a file admitted
      nothing at all: a real repair was denied the very document it was dispatched to fix.
      The previous version of this test never noticed, because it injected the workspace
      port directly and skipped the limited writer.

    So this asserts the behaviour through `build_registry_for_role`, the way a stage gets
    its tools.
    """
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind
    from fa.inner_loop.profiles import build_registry_for_role
    from fa.inner_loop.workflow_controller import _repair_allowlist

    slug = "widget-project"
    root = f"worklogs/{slug}"
    for relative in ("increments", "acceptance/tests", "notes"):
        (tmp_path / root / relative).mkdir(parents=True)
    for name in ("roadmap.md", "ledger.md", "open-questions.md"):
        (tmp_path / root / name).write_text("original\n", encoding="utf-8")

    dispatch = PlannerDispatch(
        PlannerDispatchKind.CREATE_NEW_PROJECT,
        "repair-run",
        authoring_root=root,
        repair_allowlist=_repair_allowlist(root),
    )
    writer = build_registry_for_role("planner", tmp_path, planner_dispatch=dispatch).lookup(
        "fs_write_file"
    )

    def write(relative: str) -> str | None:
        result = writer.handler({"path": relative, "content": "changed\n"})
        return None if result.error is None else result.error.code

    # Every family a repairable refusal lives in is reachable -- the plan and the question
    # record (metadata refusals), the roadmap (`plan-format-marker-roadmap`), and the
    # acceptance tree (any evidence refusal).
    assert write(f"{root}/increments/increment-01-initial-plan.md") is None
    assert write(f"{root}/open-questions.md") is None
    assert write(f"{root}/roadmap.md") is None
    assert write(f"{root}/acceptance/tests/test_initial.py") is None
    assert write(f"{root}/acceptance/pytest.ini") is None

    # ...and nothing else: not the ledger, not a sibling subtree, not another project.
    assert write(f"{root}/ledger.md") == "path_denied"
    assert write(f"{root}/notes/README.md") == "path_denied"
    assert write("worklogs/other-project/roadmap.md") == "path_denied"
    assert (tmp_path / root / "ledger.md").read_text(encoding="utf-8") == "original\n"
def test_the_repair_task_names_the_rule_and_every_path_it_may_write() -> None:
    """P4-3: "invalid metadata" is not an actionable instruction; the rule is.

    The path list is derived from the allowlist, so the text cannot promise a scope the
    writer does not have -- which is exactly what "you may write exactly two files" did
    once and would do again.
    """
    from fa.inner_loop.workflow_controller import _AdmissionDiagnostic as _Diag
    from fa.inner_loop.workflow_controller import _bounded_rule, _repair_stage_task

    task = _repair_stage_task(
        "base task",
        slug="demo-project",
        diagnostics=(_Diag("bootstrap", "invalid-body", "FAIL"),),
        rule="contract-without-evidence",
    )

    assert "Admission's rule: `contract-without-evidence`" in task
    for suffix in workflow_controller._REPAIR_WRITABLE_SUFFIXES:
        assert f"`worklogs/demo-project/{suffix}`" in task
    assert "`worklogs/demo-project/ledger.md`" not in task
    # Both legal ways out of an evidence refusal, named: the fix is a test, and the
    # alternative is a declaration the caller must grant, never a quiet deletion.
    assert "Deleting the contract or the invariant" in task
    assert "DISPOSITION-REASON" in task

    # A rule is model-influenced by the time it renders (document identifiers are embedded
    # in it), so anything not shaped like one of ours is dropped -- at the single place that
    # turns a code into prose, so no caller has to remember to bound it first.
    assert _bounded_rule("invariant-1-text") == "invariant-1-text"
    for hostile in ("drop this. /etc/passwd", "a" * 90, "Rule", "\u0440\u0443"):
        rendered = _repair_stage_task(None, slug="demo-project", diagnostics=(), rule=hostile)
        assert "Admission gave no rule name" in rendered, hostile
        assert hostile not in rendered


def test_a_repair_allowlist_outside_the_authoring_root_is_refused_at_construction() -> None:
    """The narrowing is checked where the dispatch is built, not where it is used.

    A dispatch is the one object that describes a stage; allowing it to carry a scope
    that points outside its own root would make the allowlist a suggestion. Each of
    these is a real mistake a future call site could make, and each is refused before
    a stage exists, so the failure names the dispatch rather than a path at tool level.
    """
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchError, PlannerDispatchKind

    root = "worklogs/widget-project"
    with pytest.raises(PlannerDispatchError):
        PlannerDispatch(
            PlannerDispatchKind.CREATE_NEW_PROJECT,
            "repair-run",
            authoring_root=root,
            repair_allowlist=("worklogs/other-project/increments/increment-01-initial-plan.md",),
        )
    with pytest.raises(PlannerDispatchError):
        # An empty scope is a writer that can write nothing.
        PlannerDispatch(
            PlannerDispatchKind.CREATE_NEW_PROJECT, "repair-run", authoring_root=root, repair_allowlist=()
        )
    with pytest.raises(PlannerDispatchError):
        # ...and the narrowing does not belong on any other kind.
        PlannerDispatch(
            PlannerDispatchKind.ORDINARY_PLANNING,
            "repair-run",
            repair_allowlist=(f"{root}/open-questions.md",),
        )


def test_a_create_new_repair_is_budgeted_and_never_overwrites_on_collision() -> None:
    """D-V2-9.8: two refusals are *not* repairable, however much budget is left.

    A repair is a second authoring stage, so its cost is a planner call -- which means
    the decision to start one has to answer two questions, not one: is there budget,
    and is this refusal about content at all. A collision is a fact about the
    workspace: repairing it would ask the planner to author into a directory it does
    not own, which is how a repair becomes an overwrite. Unavailability is about the
    authority, so a second stage would fail identically. Both must refuse to repair
    even with budget to spare.
    """
    from dataclasses import replace

    from fa.inner_loop.workflow_controller import WorkflowContext, _may_repair_authored_project

    ctx = WorkflowContext(
        run_id="repair-budget",
        base_task="ct-2.8",
        per_role_task={},
        artifact_paths=cast("Any", object()),
        config=Path("fa.yaml"),
        workspace=Path.cwd(),
        max_turns=1,
        output_mode="quiet",
        replans_allowed=3,
        authored_repairs=0,
    )

    def refusal(rule: str) -> PlanRefError:
        return PlanRefError(rule)

    # Budget remains, but these are not content refusals.
    assert _may_repair_authored_project(ctx, refusal("bootstrap-collision")) is False
    assert _may_repair_authored_project(ctx, refusal("bootstrap-unavailable")) is False
    assert _may_repair_authored_project(ctx, refusal("project-route-mismatch")) is False
    # A failed repair is not repaired by another repair.
    assert _may_repair_authored_project(ctx, refusal("bootstrap-refused")) is False
    # A content refusal with budget is repairable...
    assert _may_repair_authored_project(ctx, refusal("bootstrap-invalid-metadata")) is True
    assert _may_repair_authored_project(ctx, refusal("bootstrap-invalid-body")) is True
    # ...and stops being repairable when the budget is spent.
    spent = replace(ctx, authored_repairs=3)
    assert _may_repair_authored_project(spent, refusal("bootstrap-invalid-metadata")) is False


class _RecordingPort:
    """A port that records writes instead of performing them.

    The property under test is *silence*, so the double has to be able to tell
    "wrote nothing" apart from "wrote something and it happened to be accepted".
    A real managed view would refuse a second scaffold on its own -- which is exactly
    the failure a repair stage must not run into -- so the double is deliberate.
    """

    def __init__(self) -> None:
        self.writes: list[tuple[str, str]] = []

    def write_file(self, path: str, content: str, *, expected_sha256: str | None = None) -> object:
        self.writes.append((path, content))
        return SimpleNamespace(path=path, sha256="0" * 64, created=expected_sha256 is None)


def test_a_create_new_repair_writes_no_scaffold() -> None:
    """D-V2-9.9: the harness writes only the scaffold, and a repair writes none of it.

    `_write_project_scaffold` is create-only on purpose: `expected_sha256=None` is what
    turns a colliding project into a refusal instead of an overwrite. A repair stage runs
    at the revision the first stage published, so every scaffold file already exists --
    writing it again would fail on the first file with exactly the rule that protects
    creation, and the repair could never run. The seed function therefore has to
    distinguish the two stages, and this is the test that says so in the only way that
    cannot be accidentally satisfied: a double that would happily accept the write.
    """
    from fa import cli as _cli
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind

    root = "worklogs/widget-project"

    first = PlannerDispatch(PlannerDispatchKind.CREATE_NEW_PROJECT, "run-1", authoring_root=root)
    port = _RecordingPort()
    _cli._seed_scaffold_if_authoring(cast("Any", port), first)
    # The first authoring stage does seed: the scaffold is the only harness write.
    assert [path for path, _ in port.writes] == [
        f"{root}/roadmap.md",
        f"{root}/ledger.md",
        f"{root}/open-questions.md",
        f"{root}/increments/increment-01-initial-plan.md",
        f"{root}/notes/README.md",
        f"{root}/reviews/README.md",
        f"{root}/acceptance/tests/test_acceptance_placeholder.py",
    ]

    repair = PlannerDispatch(
        PlannerDispatchKind.CREATE_NEW_PROJECT,
        "run-1",
        authoring_root=root,
        repair_allowlist=(f"{root}/increments/increment-01-initial-plan.md", f"{root}/open-questions.md"),
    )
    repair_port = _RecordingPort()
    _cli._seed_scaffold_if_authoring(cast("Any", repair_port), repair)
    assert repair_port.writes == [], "a repair stage must not rewrite the scaffold"

    # And an ordinary planner stage never seeds it either, allowlist or not.
    ordinary = PlannerDispatch(PlannerDispatchKind.ORDINARY_PLANNING, "run-1", "plans/plan.md")
    ordinary_port = _RecordingPort()
    _cli._seed_scaffold_if_authoring(cast("Any", ordinary_port), ordinary)
    assert ordinary_port.writes == []


def test_the_bound_repair_path_runs_both_stages_and_binds_the_result(site: Site, tmp_path: Path) -> None:
    """D-V2-9.8: `_bind_authored_project` itself repairs -- not just "a repair is possible".

    The sibling test assembles the second stage by hand, which proves the mechanism but
    leaves the wiring unproven: a regression that stopped `_bind_authored_project` from
    calling `_run_create_new_repair` would leave it green, and so would a repair that ran
    with no narrowed scope (M3 in this bank's mutant list survived that test).

    `run_stage_fn` is the same recursion seam production uses (`_cmd_run` through
    `invoke_workflow`): each dispatch lands back in `_run_cli_stage`. Only the planner's
    behaviour is scripted per attempt -- the seam, the authority, the views and the
    publication are the real ones.
    """
    import argparse as _argparse
    from dataclasses import replace as _replace

    from fa import cli as _cli
    from fa.inner_loop.project_scaffold import scaffold_files
    from tests.test_admission_v2_provenance import _managed_child_env

    slug = "bound-repair"
    scaffold = scaffold_files(slug, created="2026-11-21")
    roadmap_path = f"worklogs/{slug}/roadmap.md"
    increment_path = f"worklogs/{slug}/increments/increment-01-initial-plan.md"
    body = _AUTHORED_BODY.format(slug=slug)
    good_roadmap = scaffold[roadmap_path]
    good_increment = scaffold[increment_path].replace("slices: 0", "slices: 1") + body
    broken_increment = good_increment.replace("Roadmap-ID: RM-bound-repair", "Roadmap-ID: RM-elsewhere")

    case_dir = tmp_path / "bound"
    case_site = Site(case_dir / "protected", site.roots, site.source)

    with _managed_child_env(case_site, case_dir, child_run_id="ct28-bound") as (
        managed,
        _publisher,
        child_ctx,
        yaml_path,
    ):
        scopes: list[str] = []

        def build_registry(workspace_io: object, _executor: object, _lease: object) -> object:
            # The stage's port is the registry this drive needs: it writes documents.
            return workspace_io

        def drive_first(port: object) -> object:
            for path, content in ((roadmap_path, good_roadmap), (increment_path, broken_increment)):
                current = port.read_file(path).sha256  # type: ignore[attr-defined]
                port.write_file(path, content, expected_sha256=current)  # type: ignore[attr-defined]
            return SessionOutcome(exit_code=0, stop_reason="stopped_by_llm", turns=1, final_text="authored")

        def drive_repair(port: object) -> object:
            current = port.read_file(increment_path).sha256  # type: ignore[attr-defined]
            port.write_file(increment_path, good_increment, expected_sha256=current)  # type: ignore[attr-defined]
            return SessionOutcome(exit_code=0, stop_reason="stopped_by_llm", turns=1, final_text="repaired")

        # ---- stage 1: a real authoring stage publishes a pair that disagrees ----------
        from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind

        first_dispatch = PlannerDispatch(
            PlannerDispatchKind.CREATE_NEW_PROJECT, child_ctx.run_id, authoring_root=f"worklogs/{slug}"
        )
        _cli._run_cli_stage(
            args=_argparse.Namespace(_managed_execution=managed),
            run_context=child_ctx,
            run_id=child_ctx.run_id,
            run_log_dir=case_dir / "log-1",
            session_db=None,
            log=SimpleNamespace(path=case_dir / "events.jsonl"),
            workspace=case_site.source,
            role="planner",
            plan_ref=None,
            planner_dispatch=first_dispatch,
            build_registry=build_registry,
            drive=drive_first,
        )
        published = managed.current_revision_id

        # ---- stage 2: the BOUND path, which must dispatch the repair itself -----------
        prompts: list[str] = []

        def stage_runner(args: object, **kwargs: object) -> int:
            dispatch = kwargs["planner_dispatch"]
            scopes.append("narrowed" if dispatch.repair_allowlist else "unbounded")
            prompts.append(args.task)  # type: ignore[attr-defined]
            outcome, _released = _cli._run_cli_stage(
                args=_argparse.Namespace(_managed_execution=managed),
                run_context=child_ctx,
                run_id=child_ctx.run_id,
                run_log_dir=case_dir / "log-2",
                session_db=None,
                log=SimpleNamespace(path=case_dir / "events.jsonl"),
                workspace=case_site.source,
                role="planner",
                plan_ref=None,
                planner_dispatch=dispatch,
                build_registry=build_registry,
                drive=drive_repair,
            )
            return 0 if outcome is not None and outcome.exit_code == 0 else 2

        ctx = _replace(
            _stage_ctx(case_site, child_ctx, yaml_path, managed, slug), replans_allowed=1
        )
        bound, blocked = workflow_controller._bind_authored_project(
            ctx,
            progress=workflow_controller.WorkflowProgress("WORKFLOW"),
            run_stage_fn=stage_runner,
        )

        assert blocked is None, f"the bound path refused instead of repairing ({blocked})"
        # Exactly one repair stage ran, and it ran with the narrowed scope. This is the
        # assertion that kills "the repair runs with no narrowed scope" (M3).
        assert scopes == ["narrowed"], f"expected one narrowed repair stage, got {scopes}"
        # P4-3: the repair is TOLD the rule, not just "invalid metadata" -- and the scope it
        # is told is the scope it actually has. Both travel with the refusal, so a regression
        # that drops either one shows up here and not only in a hand-written unit test.
        assert len(prompts) == 1
        assert "Admission's rule: `roadmap-id-mismatch`" in prompts[0], prompts[0][:600]
        assert "`worklogs/bound-repair/acceptance`" in prompts[0]
        assert "exactly two files" not in prompts[0]
        assert bound.authored_repairs == 1
        assert bound.admission is not None and bound.admission.snapshot.graph is not None
        assert list(bound.admission.snapshot.graph.contracts()) == ["CT-1.1"]
        # The repair published a SECOND revision on top of the refused one.
        assert managed.current_revision_id != published


def test_a_grammar_refusal_reaches_the_repair_as_the_parser_rule(site: Site, tmp_path: Path) -> None:
    """P4-3: the *parse* rule travels too, not only the metadata cross-check's.

    A refusal reported as ``bootstrap-invalid-metadata`` is a family, and the family is all
    admission's closed vocabulary can hold. But the repair stage is the one actor that has
    to act on the rule -- "invalid metadata" tells a planner nothing -- so the parser's own
    name for the failure rides along on the refusal. This pins that second path; the
    metadata path is pinned by the bound-repair test above.
    """
    import argparse as _argparse
    import re as _re
    from dataclasses import replace as _replace

    from fa import cli as _cli
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind
    from fa.inner_loop.project_scaffold import scaffold_files
    from tests.test_admission_v2_provenance import _managed_child_env

    slug = "grammar-repair"
    scaffold = scaffold_files(slug, created="2026-11-21")
    roadmap_path = f"worklogs/{slug}/roadmap.md"
    increment_path = f"worklogs/{slug}/increments/increment-01-initial-plan.md"
    good_roadmap = scaffold[roadmap_path]
    good_increment = scaffold[increment_path].replace("slices: 0", "slices: 1") + _AUTHORED_BODY.format(
        slug=slug
    )
    # Metadata-clean, grammar-broken: the parser wants an INVARIANTS section, and nothing in
    # the front matter is wrong, so this refusal can only come from the parse.
    broken_increment = _re.sub(r"## INVARIANTS.*?(?=\n## |\Z)", "", good_increment, flags=_re.S)

    case_dir = tmp_path / "grammar"
    case_site = Site(case_dir / "protected", site.roots, site.source)
    with _managed_child_env(case_site, case_dir, child_run_id="ct28-grammar") as (
        managed,
        _publisher,
        child_ctx,
        yaml_path,
    ):

        def build_registry(workspace_io: object, _executor: object, _lease: object) -> object:
            return workspace_io

        def rewrite(port: object, path: str, content: str) -> None:
            current = port.read_file(path).sha256  # type: ignore[attr-defined]
            port.write_file(path, content, expected_sha256=current)  # type: ignore[attr-defined]

        def drive_first(port: object) -> object:
            rewrite(port, roadmap_path, good_roadmap)
            rewrite(port, increment_path, broken_increment)
            return SessionOutcome(exit_code=0, stop_reason="stopped_by_llm", turns=1, final_text="authored")

        def drive_repair(port: object) -> object:
            rewrite(port, increment_path, good_increment)
            return SessionOutcome(exit_code=0, stop_reason="stopped_by_llm", turns=1, final_text="repaired")

        first_dispatch = PlannerDispatch(
            PlannerDispatchKind.CREATE_NEW_PROJECT, child_ctx.run_id, authoring_root=f"worklogs/{slug}"
        )
        _cli._run_cli_stage(
            args=_argparse.Namespace(_managed_execution=managed),
            run_context=child_ctx,
            run_id=child_ctx.run_id,
            run_log_dir=case_dir / "log-1",
            session_db=None,
            log=SimpleNamespace(path=case_dir / "events.jsonl"),
            workspace=case_site.source,
            role="planner",
            plan_ref=None,
            planner_dispatch=first_dispatch,
            build_registry=build_registry,
            drive=drive_first,
        )

        prompts: list[str] = []

        def stage_runner(args: object, **kwargs: object) -> int:
            prompts.append(args.task)  # type: ignore[attr-defined]
            outcome, _released = _cli._run_cli_stage(
                args=_argparse.Namespace(_managed_execution=managed),
                run_context=child_ctx,
                run_id=child_ctx.run_id,
                run_log_dir=case_dir / "log-2",
                session_db=None,
                log=SimpleNamespace(path=case_dir / "events.jsonl"),
                workspace=case_site.source,
                role="planner",
                plan_ref=None,
                planner_dispatch=kwargs["planner_dispatch"],
                build_registry=build_registry,
                drive=drive_repair,
            )
            return 0 if outcome is not None and outcome.exit_code == 0 else 2

        bound, blocked = workflow_controller._bind_authored_project(
            _replace(_stage_ctx(case_site, child_ctx, yaml_path, managed, slug), replans_allowed=1),
            progress=workflow_controller.WorkflowProgress("WORKFLOW"),
            run_stage_fn=stage_runner,
        )

        assert blocked is None, f"a grammar refusal was not repaired ({blocked})"
        assert len(prompts) == 1
        assert "Admission's rule: `missing-invariants`" in prompts[0], prompts[0][:600]
        assert bound.admission is not None and bound.admission.snapshot.graph is not None


def test_metadata_table_and_parse_refusal_block_coder_then_repair_rewrites_published_file(
    site: Site, tmp_path: Path
) -> None:
    """TEST-2.8 (D-V2-9.3/9.4/9.8): a refused project is repaired in place, not re-created.

    Two real stages against the real authority, no doubles at the seam that matters:

    1. the authoring stage publishes a project whose roadmap disagrees with its
       increment about `Roadmap-ID`. The grammar is fine; the *cross-check* is what
       refuses it, which is the whole point of moving the metadata table into
       admission (D-V2-9.3) instead of trusting the renderer;
    2. the repair stage reopens a WRITE view at that revision and rewrites the
       increment. Admission reads the new revision and binds it.

    What this pins that the unit tests cannot: the repair opens a *second* WRITE view
    over a published revision (so it is not the candidate buffer), it writes through
    the narrowed allowlist, and the run ends with an admitted plan rather than a loop.
    """
    import argparse as _argparse

    from fa import cli as _cli
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind
    from fa.inner_loop.project_scaffold import scaffold_files
    from tests.test_admission_v2_provenance import _managed_child_env

    slug = "repair-project"
    scaffold = scaffold_files(slug, created="2026-11-21")
    roadmap_path = f"worklogs/{slug}/roadmap.md"
    increment_path = f"worklogs/{slug}/increments/increment-01-initial-plan.md"
    authored_body = _AUTHORED_BODY.format(slug=slug)

    good_roadmap = scaffold[roadmap_path]
    # The increment claims a different roadmap than the one published beside it.
    good_increment = scaffold[increment_path].replace("slices: 0", "slices: 1") + authored_body
    broken_increment = good_increment.replace("Roadmap-ID: RM-repair-project", "Roadmap-ID: RM-somewhere-else")

    case_dir = tmp_path / "repair"
    # The shared roots/source of the `site` fixture: the authority is registered once
    # against them, so a fresh tree here would hand the service an unregistered root.
    case_site = Site(case_dir / "protected", site.roots, site.source)
    with _managed_child_env(case_site, case_dir, child_run_id="ct28-repair") as (
        managed,
        _publisher,
        child_ctx,
        yaml_path,
    ):
        first_rev = managed.current_revision_id

        def build_registry(workspace_io: object, _executor: object, _lease: object) -> object:
            return workspace_io

        def _rewrite(port: object, path: str, content: str) -> None:
            current = port.read_file(path).sha256  # type: ignore[attr-defined]
            port.write_file(path, content, expected_sha256=current)  # type: ignore[attr-defined]

        def first_drive(port: object) -> object:
            _rewrite(port, roadmap_path, good_roadmap)
            _rewrite(port, increment_path, broken_increment)
            return SessionOutcome(exit_code=0, stop_reason="stopped_by_llm", turns=1, final_text="authored")

        dispatch = PlannerDispatch(
            PlannerDispatchKind.CREATE_NEW_PROJECT, child_ctx.run_id, authoring_root=f"worklogs/{slug}"
        )
        _cli._run_cli_stage(
            args=_argparse.Namespace(_managed_execution=managed),
            run_context=child_ctx,
            run_id=child_ctx.run_id,
            run_log_dir=case_dir / "log-1",
            session_db=None,
            log=SimpleNamespace(path=case_dir / "events.jsonl"),
            workspace=case_site.source,
            role="planner",
            plan_ref=None,
            planner_dispatch=dispatch,
            build_registry=build_registry,
            drive=first_drive,
        )
        # The stage published (it wrote valid bytes; the *pair* is what disagrees).
        assert managed.current_revision_id != first_rev

        ctx = _stage_ctx(case_site, child_ctx, yaml_path, managed, slug)
        refused_ctx, refusal = workflow_controller._admit_published_project(ctx)
        assert refusal is not None and refusal.rule == "bootstrap-invalid-metadata"
        assert refused_ctx.admission is None, "a refused project must not bind an admission"

        # The repair: a second stage at the published revision, narrowed to the increment.
        repair_dispatch = PlannerDispatch(
            PlannerDispatchKind.CREATE_NEW_PROJECT,
            child_ctx.run_id,
            authoring_root=f"worklogs/{slug}",
            repair_allowlist=(increment_path,),
        )

        def repair_drive(port: object) -> object:
            _rewrite(port, increment_path, good_increment)
            return SessionOutcome(exit_code=0, stop_reason="stopped_by_llm", turns=1, final_text="repaired")

        _cli._run_cli_stage(
            args=_argparse.Namespace(_managed_execution=managed),
            run_context=child_ctx,
            run_id=child_ctx.run_id,
            run_log_dir=case_dir / "log-2",
            session_db=None,
            log=SimpleNamespace(path=case_dir / "events.jsonl"),
            workspace=case_site.source,
            role="planner",
            plan_ref=None,
            planner_dispatch=repair_dispatch,
            build_registry=build_registry,
            drive=repair_drive,
        )

        bound, second_refusal = workflow_controller._admit_published_project(ctx)
        assert second_refusal is None, f"the repaired revision must admit, got {second_refusal}"
        assert bound.admission is not None and bound.admission.admitted is False
        assert bound.admission.snapshot.graph is not None
        assert list(bound.admission.snapshot.graph.contracts()) == ["CT-1.1"]


def _stage_ctx(case_site: Any, child_ctx: Any, yaml_path: Path, managed: Any, slug: str) -> Any:
    """The run context admission reads: a real frozen dataclass, real project hint."""
    return workflow_controller.WorkflowContext(
        run_id=child_ctx.run_id,
        base_task="ct-2.8",
        per_role_task={},
        artifact_paths=workflow_controller.workflow_artifact_paths(
            child_ctx.run_id, base_dir=child_ctx.run_log_dir
        ),
        config=yaml_path,
        workspace=case_site.source,
        max_turns=2,
        output_mode="quiet",
        managed_execution=managed,
        project_hint=slug,
    )


def test_a_missing_grant_is_never_repaired_by_rewriting_the_plan() -> None:
    """R1/D-V2-10: the grant is the caller's, so a repair cannot manufacture one.

    A repair rewrites the documents, and the cheapest way for it to satisfy
    ``disposition-undeclared`` is to delete the request -- quietly dropping a claim the
    planner said it could not test. So the rule is excluded from repairability and the
    run stops for the caller instead.
    """
    ctx = workflow_controller.WorkflowContext(
        run_id="run-20260101-000000-" + "0" * 8,
        base_task="task",
        per_role_task={},
        artifact_paths=workflow_controller.workflow_artifact_paths("run-20260101-000000-" + "0" * 8),
        config=Path("config.yaml"),
        workspace=Path("."),
        max_turns=1,
        output_mode="quiet",
        replans_allowed=1,  # budget exists, so "no repair" is the rule and not the counter
    )

    assert workflow_controller._may_repair_authored_project(ctx, PlanRefError("disposition-undeclared")) is False
    assert workflow_controller._may_repair_authored_project(ctx, PlanRefError("bootstrap-invalid-metadata")) is True


def test_an_ungranted_request_is_refused_even_when_the_caller_sends_no_declarations(
    site: Site, tmp_path: Path
) -> None:
    """P4-1: binding used to run only when the caller *also* sent declarations.

    `_admit_published_project` read `if snapshot.graph is not None and granted:`, so the
    one combination with no other gate -- a plan that requests a waiver and a caller who
    supplies none -- skipped the binding entirely and reached admission with the request
    unbound. The control here is the same published revision admitted twice: without the
    declaration it is refused, with it the grant is bound.
    """
    from fa import cli as _cli
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind
    from tests.test_admission_v2_provenance import _managed_child_env

    slug = "waiver-project"
    roadmap_path = f"worklogs/{slug}/roadmap.md"
    increment_path = f"worklogs/{slug}/increments/increment-01-initial-plan.md"
    roadmap, increment = _requiring_pair()

    case_dir = tmp_path / "ungranted"
    case_site = Site(case_dir / "protected", site.roots, site.source)
    with _managed_child_env(case_site, case_dir, child_run_id="p41-ungranted") as (
        managed,
        _publisher,
        child_ctx,
        yaml_path,
    ):

        def build_registry(workspace_io: object, _executor: object, _lease: object) -> object:
            return workspace_io

        def drive(port: object) -> SessionOutcome:
            for path, content in ((roadmap_path, roadmap), (increment_path, increment)):
                current = port.read_file(path).sha256  # type: ignore[attr-defined]
                port.write_file(path, content, expected_sha256=current)  # type: ignore[attr-defined]
            return SessionOutcome(exit_code=0, stop_reason="stopped_by_llm", turns=1, final_text="authored")

        _cli._run_cli_stage(
            args=argparse.Namespace(_managed_execution=managed),
            run_context=child_ctx,
            run_id=child_ctx.run_id,
            run_log_dir=case_dir / "log",
            session_db=None,
            log=SimpleNamespace(path=case_dir / "events.jsonl"),
            workspace=case_site.source,
            role="planner",
            plan_ref=None,
            planner_dispatch=PlannerDispatch(
                PlannerDispatchKind.CREATE_NEW_PROJECT, child_ctx.run_id, authoring_root=f"worklogs/{slug}"
            ),
            build_registry=build_registry,
            drive=drive,
        )

        ctx = _stage_ctx(case_site, child_ctx, yaml_path, managed, slug)
        admitted, refusal = workflow_controller._admit_published_project(ctx)

        assert refusal is not None and refusal.rule == "disposition-undeclared"
        assert admitted.admission is None, "a refused request must not bind an admission"

        declaration = parse_dispositions(
            [
                {
                    "reason": "HOST_READINESS",
                    "owner": "W4",
                    "evidence": "issue:FA-1234",
                    "reviewed_at": "2026-11-20",
                }
            ]
        )
        bound, granted_refusal = workflow_controller._admit_published_project(
            replace(ctx, dispositions=declaration)
        )

        assert granted_refusal is None
        assert bound.admission is not None and bound.admission.snapshot.graph is not None
        waiver = {item.id: item for item in bound.admission.snapshot.graph.invariants}["INV-1"]
        assert waiver.owner == "W4"


def test_create_over_existing_directory_is_project_exists_and_unchanged(
    site: Site, tmp_path: Path
) -> None:
    """CT-2.7 (D-V2-9.2): a create onto an existing project refuses, and nothing is lost.

    The guard has two independent halves and either one failing is a data-loss bug, so
    both are checked here:

    * the *decision* -- `_authoring_collision` reads the pinned inventory and refuses
      before the stage is dispatched, so no provider is reached and no view is opened;
    * the *write* -- the scaffold writer asks for create-only on every file
      (`expected_sha256=None`), so even a bypassed decision ends in the authority's
      `STALE_REVISION` rather than an overwrite.

    "Refused" alone is not the property: the existing project's bytes must survive. The
    second half therefore runs against the real authority -- a second stage trying to
    create the same slug -- and compares the tree byte for byte afterwards.
    """
    import argparse as _argparse

    from fa import cli as _cli
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind
    from fa.inner_loop.project_scaffold import scaffold_files
    from fa.inner_loop.workflow_controller import _authoring_collision
    from tests.test_admission_v2_provenance import _managed_child_env

    slug = "taken-project"
    root = f"worklogs/{slug}"

    # ---- half 1: the decision, against a pinned inventory that says "it exists" -------
    def ctx_with(project_names: tuple[str, ...], incomplete_names: tuple[str, ...]) -> object:
        return SimpleNamespace(
            run_id="collision",
            acquisition=SimpleNamespace(project_names=project_names, incomplete_names=incomplete_names),
        )

    dispatch = PlannerDispatch(PlannerDispatchKind.CREATE_NEW_PROJECT, "collision", authoring_root=root)
    taken = _authoring_collision(cast("Any", ctx_with((slug,), ())), dispatch)
    assert taken is not None and taken.rule == "bootstrap-collision"
    # An *incomplete* directory collides too: a create may not finish someone else's tree.
    half = _authoring_collision(cast("Any", ctx_with((), (slug,))), dispatch)
    assert half is not None and half.rule == "bootstrap-collision"
    # A free name passes, so the refusal is about the collision and not the route.
    assert _authoring_collision(cast("Any", ctx_with(("other",), ())), dispatch) is None
    # A non-authoring kind is never asked the question at all.
    ordinary = PlannerDispatch(PlannerDispatchKind.ORDINARY_PLANNING, "collision", "plans/plan.md")
    assert _authoring_collision(cast("Any", ctx_with((slug,), ())), ordinary) is None

    # ---- half 2: the bytes survive a real second create ------------------------------
    case_dir = tmp_path / "collision"
    case_site = Site(case_dir / "protected", site.roots, site.source)
    scaffold = scaffold_files(slug, created="2026-11-21")

    with _managed_child_env(case_site, case_dir, child_run_id="ct27-collision") as (
        managed,
        _publisher,
        child_ctx,
        _yaml,
    ):
        def _stage(dispatch: object, drive: object) -> tuple[object, bool]:
            return _cli._run_cli_stage(
                args=_argparse.Namespace(_managed_execution=managed),
                run_context=child_ctx,
                run_id=child_ctx.run_id,
                run_log_dir=case_dir / "log",
                session_db=None,
                log=SimpleNamespace(path=case_dir / "events.jsonl"),
                workspace=case_site.source,
                role="planner",
                plan_ref=None,
                planner_dispatch=dispatch,
                build_registry=lambda workspace_io, _e, _l: workspace_io,
                drive=drive,
            )

        def author(port: object) -> object:
            for path, content in scaffold.items():
                current = port.read_file(path).sha256  # type: ignore[attr-defined]
                port.write_file(path, content, expected_sha256=current)  # type: ignore[attr-defined]
            return SessionOutcome(exit_code=0, stop_reason="stopped_by_llm", turns=1, final_text="first")

        first_dispatch = PlannerDispatch(PlannerDispatchKind.CREATE_NEW_PROJECT, child_ctx.run_id, authoring_root=root)
        _stage(first_dispatch, author)
        first_revision = managed.current_revision_id
        before = dict(scaffold)

        # The second create: same slug, and the planner tries to overwrite the roadmap.
        reached: list[str] = []

        def overwrite(port: object) -> object:
            reached.append("provider reached")
            port.write_file(f"{root}/roadmap.md", "# replaced", expected_sha256=None)  # type: ignore[attr-defined]
            return SessionOutcome(exit_code=0, stop_reason="stopped_by_llm", turns=1, final_text="second")

        second_dispatch = PlannerDispatch(PlannerDispatchKind.CREATE_NEW_PROJECT, child_ctx.run_id, authoring_root=root)
        try:
            _stage(second_dispatch, overwrite)
        except WorkspacePortError:
            # Expected: create-only write against an existing file. The stage refused.
            pass

        # 0. The refusal happened *before* the planner ran. The scaffold writer is what
        #    refuses -- its create-only write hits an existing `roadmap.md` -- so the model
        #    is never asked to author over a project it does not own. That ordering is the
        #    guarantee: a provider called first would have spent tokens on a doomed run.
        assert reached == [], "the planner ran before the collision was refused"
        # 1. Nothing was published: the second create never became a revision.
        assert managed.current_revision_id == first_revision
        # 2. And the project's bytes are exactly what the first create wrote.
        probe = _stage_ctx(case_site, child_ctx, _yaml, managed, slug)
        with workflow_controller._pinned_acquisition_substrate(probe) as substrate:
            assert substrate is not None
            for path, content in before.items():
                assert substrate.port.read_file(path).content == content, f"{path} was overwritten"


def test_create_new_stage_scaffolds_then_planner_writes_only_inside_slug() -> None:
    """CT-2.3 (D-V2-9 / 9.6 / 9.7): the harness owns the tree, the planner owns the prose.

    Three properties, each of which has a distinct failure mode if it rots:

    * **the file set** -- exactly seven files, and the three roots exist only as parents of
      those files. The writer has no mkdir and refuses dot-only names, so a `.gitkeep`
      would not survive; an "empty" `acceptance/tests/` cannot exist at all. That is why
      the scaffold carries a module with no test functions rather than a placeholder.
    * **the scaffold is not a plan** -- `parse_plan` must refuse the unfilled increment.
      This is the one that matters most: a scaffold that parsed would let an authoring
      stage that wrote nothing reach admission with a fake plan.
    * **the boundary** -- the stage's writer admits `worklogs/<slug>/` and nothing else,
      including traversal out of it and a sibling project.

    The boundary is checked on the tool the model actually calls (`fs_write_file`, which
    resolves to the limited builder for a planner), not on a helper.
    """
    from fa.inner_loop.plan_v2 import PlanV2Error, parse_plan
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind
    from fa.inner_loop.profiles import build_registry_for_role
    from fa.inner_loop.project_scaffold import scaffold_files

    slug = "demo-project"
    root = f"worklogs/{slug}"
    files = scaffold_files(slug, created="2026-11-21")

    # ---- the file set ---------------------------------------------------------------
    assert list(files) == [
        f"{root}/roadmap.md",
        f"{root}/ledger.md",
        f"{root}/open-questions.md",
        f"{root}/increments/increment-01-initial-plan.md",
        f"{root}/notes/README.md",
        f"{root}/reviews/README.md",
        f"{root}/acceptance/tests/test_acceptance_placeholder.py",
    ]
    # No dot-only component anywhere: the writer refuses those, so any would be a silent
    # drop rather than a directory.
    assert not any("/." in path or path.endswith(".") for path in files)

    # ---- the scaffold is refused as a plan -------------------------------------------
    increment = files[f"{root}/increments/increment-01-initial-plan.md"]
    with pytest.raises(PlanV2Error) as refused:
        parse_plan(roadmap=files[f"{root}/roadmap.md"], increment=increment)
    assert refused.value.rule == "missing-slice"
    # ...and the placeholder module cannot become a passing oracle.
    placeholder = files[f"{root}/acceptance/tests/test_acceptance_placeholder.py"]
    assert "def test_" not in placeholder

    # ---- the boundary ---------------------------------------------------------------
    dispatch = PlannerDispatch(PlannerDispatchKind.CREATE_NEW_PROJECT, "ct23", authoring_root=root)
    writer = build_registry_for_role("planner", Path.cwd(), planner_dispatch=dispatch).lookup("fs_write_file")

    inside = writer.handler({"path": f"{root}/roadmap.md", "content": "x"})
    assert inside.error is None, "the stage must be able to write its own project"
    for path in (
        "src/fa/evil.py",
        f"{root}/../escape.md",
        "worklogs/another-project/roadmap.md",
        "README.md",
        ".fa/admission/candidate.md",
    ):
        denied = writer.handler({"path": path, "content": "x"})
        assert denied.error is not None and denied.error.code == "path_denied", path


def _admit_in(
    case_site: Site, child_ctx: Any, managed: Any, yaml_path: Path, slug: str
) -> tuple[Any, Any]:
    """Run admission over the revision the stage published, in a real context.

    A real `WorkflowContext` and not a double: `_admit_published_project` returns a
    *replaced* context, which is the point -- the binding is a new value, never a
    mutation of the run's shared state.
    """
    from fa.inner_loop.workflow_controller import _admit_published_project

    ctx = workflow_controller.WorkflowContext(
        run_id=child_ctx.run_id,
        base_task="ct-2.8",
        per_role_task={},
        artifact_paths=workflow_controller.workflow_artifact_paths(
            child_ctx.run_id, base_dir=child_ctx.run_log_dir
        ),
        config=yaml_path,
        workspace=case_site.source,
        max_turns=2,
        output_mode="quiet",
        managed_execution=managed,
        project_hint=slug,
    )
    return _admit_published_project(ctx)
