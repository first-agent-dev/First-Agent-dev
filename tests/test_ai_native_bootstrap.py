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
    "\n## INVARIANTS\n### INV-1\nKIND: HARD\n"
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
        "\n## INVARIANTS\n### INV-1\nKIND: HARD\n"
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
        "\n## INVARIANTS\n### INV-1\nKIND: HARD\n"
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


def test_a_create_new_repair_may_write_only_the_documents_admission_read() -> None:
    """D-V2-9.8: the repair stage is narrower than the stage it repairs.

    The control is not "repair works" -- that needs a live planner. It is the part
    that must hold whatever the planner does: a repair stage's writer admits the
    increment and the question record, and refuses the roadmap. That split is what
    keeps a repair from publishing a project admission never read, and it is enforced
    by the allowlist rather than by asking the model nicely.
    """
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind
    from fa.inner_loop.profiles import build_registry_for_role

    root = "worklogs/widget-project"
    dispatch = PlannerDispatch(
        PlannerDispatchKind.CREATE_NEW_PROJECT,
        "repair-run",
        authoring_root=root,
        repair_allowlist=(f"{root}/increments/increment-01-initial-plan.md", f"{root}/open-questions.md"),
    )
    registry = build_registry_for_role("planner", Path.cwd(), planner_dispatch=dispatch)
    # The planner profile names the tool ``fs_write_file``; the limited builder is what
    # that name resolves to for a planner, so the allowlist is on the tool the model sees.
    writer = registry.lookup("fs_write_file")

    denied = writer.handler({"path": f"{root}/roadmap.md", "content": "# rewritten"})
    assert denied.error is not None and denied.error.code == "path_denied"

    # And the scope is the *repair* one, not the whole authoring root: a second
    # document the planner authored in the first stage is out of reach too.
    ledger = writer.handler({"path": f"{root}/ledger.md", "content": "# rewritten"})
    assert ledger.error is not None and ledger.error.code == "path_denied"


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
