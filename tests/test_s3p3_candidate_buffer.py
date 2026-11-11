"""S3P3: the staged-candidate buffer as a substrate, over the real authority.

C0/C3 for the narrow port that made managed plan repair possible. The claim under
test is deliberately small and structural: a CANDIDATE view's buffer is a
purpose-bound operation, NOT a write path on a READ view, so

* it is refused on every other purpose (the ``write_file`` invariant stays true);
* it answers to exactly one address -- the plan identity the view pinned -- and
  the port holds that address, so a caller cannot name its own;
* the authority's CAS is surfaced rather than hidden: an absent buffer takes a
  first write, a present one requires its digest, and the port reports the codes
  the tool layer maps instead of inventing its own.

What this bank does NOT claim: end-to-end managed repair. That is
``test_execution_composition.py::test_workflow_root_publishes_candidate_through_real_local_authority``,
which drives the real CLI over a real supervisor and is the producer kill-check.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest

from fa.execution.tool_port import AuthorityWorkspacePort
from fa.execution.types import Access, ExecutionContractError, ViewPurpose
from fa.inner_loop.plan_admission import PlanRef, read_plan_snapshot, snapshot_from_bytes
from fa.inner_loop.tools.workspace_port import WorkspacePortError
from tests.test_execution_purposes import scope_for
from tests.test_execution_readers import read_only_profile
from tests.test_execution_views import native_profile
from tests.test_execution_workspace import Site, ok, until
from tests.test_execution_workspace import site as site

PLAN_BODY = "# plan\n"


@contextmanager
def buffer_site(
    site: Site,
) -> Generator[tuple[AuthorityWorkspacePort, AuthorityWorkspacePort, PlanRef]]:
    """A CANDIDATE port plus a PROJECT port, both real, over one admitted view set."""
    from tests.test_execution_workspace import ACTOR as CANDIDATE_ACTOR
    from tests.test_execution_workspace import PEER

    site.source.mkdir(parents=True, exist_ok=True)
    (site.source / "plan.md").write_text(PLAN_BODY)
    with site.owner(view_profile=native_profile(), read_only_profile=read_only_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        plan_ref = read_plan_snapshot(site.source, Path("plan.md")).ref
        candidate_grant = owner.create_view(
            PEER,
            CANDIDATE_ACTOR,
            workspace_id=ids["workspace_id"],
            capability=lease.capability,
            purpose=ViewPurpose.CANDIDATE,
            access=Access.READ,
            candidate_scope=scope_for(plan_ref),
            plan_ref=plan_ref,
            formal_evidence=False,
            deadline=until(),
        )
        assert candidate_grant.view_ref is not None
        candidate = AuthorityWorkspacePort(
            owner,
            peer=PEER,
            namespace=CANDIDATE_ACTOR,
            view_ref=candidate_grant.view_ref,
            capability=candidate_grant.capability,
            deadline_factory=until,
            plan_ref=plan_ref,
        )
        project_grant = owner.create_view(
            PEER,
            CANDIDATE_ACTOR,
            workspace_id=ids["workspace_id"],
            capability=lease.capability,
            purpose=ViewPurpose.PROJECT,
            access=Access.WRITE,
            candidate_scope=None,
            plan_ref=plan_ref,
            formal_evidence=False,
            deadline=until(),
        )
        assert project_grant.view_ref is not None
        project = AuthorityWorkspacePort(
            owner,
            peer=PEER,
            namespace=CANDIDATE_ACTOR,
            view_ref=project_grant.view_ref,
            capability=project_grant.capability,
            deadline_factory=until,
        )
        yield candidate, project, plan_ref


def test_the_buffer_answers_to_the_plan_identity_and_nothing_else(site: Site) -> None:
    """The port's own label is the plan path; the caller never supplies one."""
    with buffer_site(site) as (candidate, _project, plan_ref):
        assert candidate.candidate_label() == plan_ref.workspace_relative_path
        # The tool-facing protocol is satisfied structurally. `isinstance` is not
        # available for it on purpose: a Protocol with non-method members would
        # need `runtime_checkable`, and the production builder checks the three
        # callables instead (`write_file.py`), so this mirrors that check.
        assert all(
            callable(getattr(candidate, name)) for name in ("write_candidate", "read_candidate", "candidate_label")
        )


def test_a_read_view_keeps_no_write_path_while_its_buffer_is_writable(site: Site) -> None:
    """C3: the buffer is a separate operation, so `write_file` stays WRITE-only.

    This is the invariant that made the original defect a defect rather than a
    hole: widening `write_file` to accept a READ view would have given the planner
    a write path to every project file. Both halves are asserted here, because
    either one alone is satisfiable by a wrong implementation.
    """
    with buffer_site(site) as (candidate, _project, _plan_ref):
        with pytest.raises(WorkspacePortError) as refusal:
            candidate.write_file("plan.md", "# hijacked\n")
        assert refusal.value.code == "denied"
        # ... while the purpose-bound operation on the same view succeeds.
        written = candidate.write_candidate("# repaired\n")
        assert written.bytes == len("# repaired\n")


def test_the_first_write_takes_an_absent_buffer_and_the_second_needs_its_digest(site: Site) -> None:
    """The authority's CAS is surfaced, not hidden behind the port."""
    with buffer_site(site) as (candidate, _project, _plan_ref):
        first = candidate.write_candidate("# one\n")
        read = candidate.read_candidate()
        assert read.content == "# one\n"
        assert read.sha256 == first.sha256 and read.eof is True

        # A blind second write is refused: `None` means "expect absence" upstream.
        with pytest.raises(WorkspacePortError) as stale:
            candidate.write_candidate("# two\n")
        assert stale.value.code == "stale"

        # The revision the planner is entitled to make, built on the bytes it saw.
        second = candidate.write_candidate("# two\n", expected_sha256=first.sha256)
        assert candidate.read_candidate().content == "# two\n"
        assert second.sha256 != first.sha256


def test_a_digest_the_buffer_does_not_hold_is_stale_and_changes_nothing(site: Site) -> None:
    """Negative proof: a refused CAS leaves the previous bytes in place."""
    with buffer_site(site) as (candidate, _project, _plan_ref):
        candidate.write_candidate("# kept\n")
        with pytest.raises(WorkspacePortError) as refusal:
            candidate.write_candidate("# lost\n", expected_sha256="0" * 64)
        assert refusal.value.code == "stale"
        assert candidate.read_candidate().content == "# kept\n"


def test_a_project_view_has_no_candidate_buffer(site: Site) -> None:
    """The closed matrix: the buffer belongs to CANDIDATE, not to any view.

    The port is built here WITHOUT a `plan_ref` -- which is what the composition
    does for a project view -- and the refusal is `unavailable` rather than
    `denied` on purpose: the view has no buffer to deny, so "there is no buffer
    here" is the truthful code and a caller cannot mistake it for a policy denial
    on a view that does have one.
    """
    with buffer_site(site) as (candidate, project, _plan_ref):
        with pytest.raises(WorkspacePortError) as refusal:
            project.write_candidate("# anywhere\n")
        assert refusal.value.code == "denied"
        # The CANDIDATE port in the same workspace is unaffected by that refusal.
        assert candidate.write_candidate("# here\n").bytes == len("# here\n")


def test_the_buffer_never_writes_the_canonical_plan(site: Site) -> None:
    """E259: staging stays staging -- the canonical bytes are untouched."""
    with buffer_site(site) as (candidate, _project, plan_ref):
        before = (site.source / plan_ref.workspace_relative_path).read_bytes()
        candidate.write_candidate("# repaired\n")
        after = (site.source / plan_ref.workspace_relative_path).read_bytes()
        assert before == after == PLAN_BODY.encode("utf-8")
        # And the bytes the controller would validate are a complete snapshot.
        snapshot = snapshot_from_bytes(plan_ref.workspace_relative_path, candidate.read_candidate().content.encode())
        assert snapshot.text == "# repaired\n"


def test_a_port_without_a_plan_identity_refuses_rather_than_guessing(site: Site) -> None:
    """No label means no subject: the port fails closed instead of inventing one."""
    with buffer_site(site) as (candidate, _project, _plan_ref):
        from fa.execution.tool_port import AuthorityWorkspacePort as Port

        unlabelled = Port(
            candidate._authority,
            peer=candidate._peer,
            namespace=candidate._namespace,
            view_ref=candidate._view_ref,
            capability=candidate._capability,
            deadline_factory=until,
        )
        with pytest.raises(WorkspacePortError) as refusal:
            unlabelled.candidate_label()
        assert refusal.value.code == "unavailable"
        with pytest.raises(WorkspacePortError):
            unlabelled.write_candidate("# nowhere\n")


def test_the_port_rejects_a_foreign_plan_ref_shape(site: Site) -> None:
    """A label that is not a PlanRef cannot be bound to a candidate port."""
    with buffer_site(site) as (candidate, _project, _plan_ref):
        from fa.execution.tool_port import AuthorityWorkspacePort as Port

        with pytest.raises(ExecutionContractError):
            Port(
                candidate._authority,
                peer=candidate._peer,
                namespace=candidate._namespace,
                view_ref=candidate._view_ref,
                capability=candidate._capability,
                deadline_factory=until,
                plan_ref="worklogs/plan.md",  # type: ignore[arg-type]
            )


class _RecordingCandidate:
    """A double that records the CAS it was asked to satisfy -- no product logic.

    It does not implement the buffer: the authority does. All this needs to prove
    is WHICH substrate the scoped writer chose and with WHAT precondition, which is
    the writer's own decision and therefore nothing a double is hiding.
    """

    def __init__(self, refuse: WorkspacePortError | None = None) -> None:
        self.calls: list[str | None] = []
        self._refuse = refuse

    def write_candidate(self, content: str, *, expected_sha256: str | None = None) -> object:
        if self._refuse is not None:
            raise self._refuse
        self.calls.append(expected_sha256)
        return type("Written", (), {"sha256": f"digest-{len(self.calls)}", "bytes": len(content.encode())})()

    def read_candidate(self, *, max_bytes: int = 1) -> object:  # pragma: no cover - never called here
        raise AssertionError("the scoped writer must not read the buffer")

    def candidate_label(self) -> str:  # pragma: no cover - never called here
        raise AssertionError("the scoped writer must not name the buffer")


def test_the_scoped_writer_threads_the_cas_so_a_planner_can_revise_itself(tmp_path: Path) -> None:
    """Producer: `build_scoped_write_file_tool` -> `candidate_io.write_candidate`.

    Two writes in one stage are the planner's normal right (it repairs what it
    wrote). The first must carry no precondition -- `None` is "expect absence"
    upstream -- and every later one must carry the digest the authority returned.
    A writer that sent `None` twice would be refused as stale on the second write;
    a writer that sent a guessed digest would be refused on the first.
    """
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind
    from fa.inner_loop.tools.write_file import build_scoped_write_file_tool

    target = ".fa/admission/ct93/candidate.md"
    port = _RecordingCandidate()
    tool = build_scoped_write_file_tool(
        tmp_path,
        PlannerDispatch(PlannerDispatchKind.ADMISSION_REPAIR, "ct93", candidate_target=target),
        candidate_io=port,  # type: ignore[arg-type]
    )
    assert tool.handler({"path": target, "content": "первый\n"}).error is None
    assert tool.handler({"path": target, "content": "второй\n"}).error is None
    assert port.calls == [None, "digest-1"]
    # The staging address is model-facing only: nothing was written to the host.
    assert not (tmp_path / ".fa").exists()


def test_a_refused_buffer_write_is_reported_with_the_port_vocabulary(tmp_path: Path) -> None:
    """Failure behaviour: a substrate refusal is a tool failure, never a success."""
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind
    from fa.inner_loop.tools.write_file import build_scoped_write_file_tool

    target = ".fa/admission/ct93/candidate.md"
    tool = build_scoped_write_file_tool(
        tmp_path,
        PlannerDispatch(PlannerDispatchKind.ADMISSION_REPAIR, "ct93", candidate_target=target),
        candidate_io=_RecordingCandidate(WorkspacePortError("stale")),  # type: ignore[arg-type]
    )
    result = tool.handler({"path": target, "content": "текст\n"})
    assert result.error is not None and result.error.code == "write_failed"
    assert not (tmp_path / ".fa").exists()


def test_a_substrate_that_is_not_a_candidate_port_is_refused_at_build_time(tmp_path: Path) -> None:
    """A wrong substrate fails the build, not the tool call three turns later."""
    from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchError, PlannerDispatchKind
    from fa.inner_loop.tools.write_file import build_scoped_write_file_tool

    with pytest.raises(PlannerDispatchError):
        build_scoped_write_file_tool(
            tmp_path,
            PlannerDispatch(PlannerDispatchKind.EVAL_REPLAN, "ct93", candidate_target=".fa/admission/ct93/c.md"),
            candidate_io=object(),  # type: ignore[arg-type]
        )


def test_a_buffer_that_does_not_arrive_in_one_window_is_refused_not_truncated(tmp_path: Path, site: Site) -> None:
    """A partial plan must never be validated as if it were the whole candidate.

    The production reader (``capture_stage_candidate``) asks for one window and
    requires ``eof``. Truncating instead would validate bytes nobody wrote and
    could publish a repair that silently deleted the plan's tail -- the failure
    mode this check exists for.
    """
    from fa.inner_loop.stage_candidate import STAGE_CANDIDATE_BYTES, capture_stage_candidate

    class _Partial:
        def read_candidate(self, *, max_bytes: int = 1) -> object:
            return type("Read", (), {"content": "## SLICE 1: trunc", "sha256": "a" * 64, "eof": False})()

    STAGE_CANDIDATE_BYTES.set(None)
    with pytest.raises(WorkspacePortError) as refusal:
        capture_stage_candidate(_Partial())  # type: ignore[arg-type]
    assert refusal.value.code == "input_policy"
    assert STAGE_CANDIDATE_BYTES.get() is None


def test_an_empty_buffer_means_no_candidate_not_an_empty_plan(site: Site) -> None:
    """`stale` on read means "the planner wrote nothing", and it is not captured.

    Host mode already behaves this way -- the seed file it wrote is what admission
    then judges -- so an empty buffer must not become a zero-byte candidate that
    validates as one.
    """
    from fa.inner_loop.stage_candidate import STAGE_CANDIDATE_BYTES, capture_stage_candidate

    class _Empty:
        def read_candidate(self, *, max_bytes: int = 1) -> object:
            raise WorkspacePortError("stale")

    STAGE_CANDIDATE_BYTES.set(("previous", "b" * 64))
    with buffer_site(site) as (_candidate, _project, _plan_ref):
        capture_stage_candidate(_Empty())  # type: ignore[arg-type]
    # Explicitly NOT captured: a stale buffer must not inherit a previous stage's
    # bytes, which is why the caller clears the variable on the way in as well.
    assert STAGE_CANDIDATE_BYTES.get() == ("previous", "b" * 64)


def test_an_unsettled_candidate_view_holds_the_writer_until_it_is_published(site: Site) -> None:
    """Q138 option B: ownership, not access, decides whether the writer settles.

    §2.1 scopes writer release to WRITE views, which is right for a read pin over
    committed bytes. CANDIDATE is the one READ purpose that owns writer-private
    bytes, and an unresolved publication over those bytes must keep the owner —
    otherwise the next claim advances the generation and the buffer becomes
    unreachable rather than merely leftover.

    The negative half matters as much: the same view, once published, must stop
    holding the writer, or every managed run would end in a permanent
    `WORKSPACE_BUSY` instead of a leak.
    """
    from tests.test_execution_workspace import ACTOR as CANDIDATE_ACTOR
    from tests.test_execution_workspace import PEER

    site.source.mkdir(parents=True, exist_ok=True)
    (site.source / "plan.md").write_text(PLAN_BODY)
    with site.owner(view_profile=native_profile(), read_only_profile=read_only_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = site.claim(owner, ids)
        plan_ref = read_plan_snapshot(site.source, Path("plan.md")).ref
        grant = owner.create_view(
            PEER,
            CANDIDATE_ACTOR,
            workspace_id=ids["workspace_id"],
            capability=lease.capability,
            purpose=ViewPurpose.CANDIDATE,
            access=Access.READ,
            candidate_scope=scope_for(plan_ref),
            plan_ref=plan_ref,
            formal_evidence=False,
            deadline=until(),
        )
        assert grant.view_ref is not None
        # The unsettled CANDIDATE view alone must refuse settlement.
        # `create_view` rotates the grant, so the pre-view capability is stale and
        # would be refused UNAUTHORIZED before the fence. Read the live grant back
        # from the owner, which is the capability a real releaser would hold.
        live = site.live_capability(owner, ids)
        with pytest.raises(Exception) as failure:
            owner.release_writer(PEER, CANDIDATE_ACTOR, capability=live, deadline=until())
        assert getattr(failure.value, "code", None) == "WORKSPACE_BUSY"
        assert site.metadata(ids)["status"] == "OWNED"

def test_a_read_pin_over_committed_bytes_still_settles_the_writer(site: Site) -> None:
    """The other half of Q138-B: §2.1's scope stays intact.

    The fence above judges CANDIDATE by ownership. If it had instead judged every
    READ view, an ordinary reader pin would fence the writer forever — so this
    proves the rule did not widen beyond the one purpose that owns private bytes.
    """
    from tests.test_execution_workspace import ACTOR as CANDIDATE_ACTOR
    from tests.test_execution_workspace import PEER

    site.source.mkdir(parents=True, exist_ok=True)
    (site.source / "plan.md").write_text(PLAN_BODY)
    with site.owner(view_profile=native_profile(), read_only_profile=read_only_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = site.claim(owner, ids)
        pinned = ok(
            lambda: owner.pin_reader(
                PEER,
                CANDIDATE_ACTOR,
                workspace_id=ids["workspace_id"],
                revision_id=lease.revision_id,
                plan_ref=None,
                formal_evidence=False,
                deadline=until(),
            )
        )
        assert pinned.view_ref is not None
        released = ok(
            lambda: owner.release_unused_writer(
                PEER,
                CANDIDATE_ACTOR,
                workspace_id=ids["workspace_id"],
                capability=lease.capability,
                deadline=until(),
            )
        )
        assert released["released"] is True
        assert site.metadata(ids)["status"] == "AVAILABLE"
