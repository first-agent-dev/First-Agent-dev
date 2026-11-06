"""SLICE4 STEP2b/1 — committing one execution view to the canonical tree (C0/C1/C3).

**Why this bank exists.** STEP2a gave the file tools a write path into a view. A
view is a copy: without a commit, every managed file write would be thrown away at
the end of the stage — worse than the host fallback it replaces, because it would
look successful. `publish_stage` is that commit (stop → seal → publish), and it is
also where CT97's plan-write boundary gets its producer: the plan may not be
rewritten through an ordinary revision seal (`publication.py:308`).

Root: a real `SupervisorService`, a real Unix socket, a real `ExecutionClient`.
Only the transport is subclassed where the assertions are about which operations
were sent.

Path inventory:
  Q1 a stage view's writes become canonical bytes, one revision forward; the run
     keeps its writer and the next stage opens on the committed base
  Q2 the commit ends the view: no write may land after the projection
  Q3 the plan is not writable from a stage view, and a seal that refused to
     publish its manifest stops the commit (CT97's two lines of defence)
  Q4 a moved base refuses the commit before any projection (the CAS is the view's);
     and a plan write cannot overlap an open stage view (one write epoch)
  Q5 a read view, a foreign grant and a malformed reply never become a publication
  Q6 an unproven end or an unproven publish is reported, never rounded up
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.execution.client import ExecutionRejectedError, ExecutionUncertainError, StagePublication
from fa.execution.types import (
    Access,
    ExecutionContractError,
    GrantReply,
    Operation,
    ViewPurpose,
    ViewRef,
)
from fa.inner_loop.plan_admission import read_plan_snapshot, snapshot_from_bytes
from fa.inner_loop.tools.workspace_port import WorkspacePortError
from tests.test_execution_client_port import (
    PLAN_BYTES,
    PLAN_RELATIVE,
    _fixed_grant,
    _FramedClient,
    _namespace,
    _plan_ref,
    _port,
    _read_view_grant,
    _served,
)
from tests.test_execution_workspace import Site
from tests.test_execution_workspace import site as site

SEAL_REPLY = {
    "sealed_manifest_id": "seal-" + "7" * 32,
    "revision_id": "rev-" + "8" * 32,
    "tree_sha256": "9" * 64,
}
PUBLISH_REPLY = {
    "workspace_id": "ws-" + "1" * 32,
    "revision_id": SEAL_REPLY["revision_id"],
    "tree_sha256": SEAL_REPLY["tree_sha256"],
    "operation_id": "op-" + "3" * 32,
    "projection_complete": True,
    "plan_ref": None,
    "already_published": False,
}


def _stage_port(managed, plan, *, purpose: ViewPurpose = ViewPurpose.MUTATION):
    """One write view of the run's workspace, plus the grant that owns it."""
    grant = managed.open_view(
        access=Access.WRITE, purpose=purpose, base_revision=managed.grant.revision_id, plan_ref=plan
    )
    return _port(managed.client, managed.binding.namespace, grant), grant


def _other_write_grant() -> GrantReply:
    """A well-formed grant for a different view — the caller-bug case."""
    view = ViewRef(
        "ws-" + "3" * 32,
        "view-" + "9" * 32,
        "rev-" + "5" * 32,
        "run-1",
        1,
        Access.WRITE,
        ViewPurpose.MUTATION,
    )
    return GrantReply(Operation.CREATE_VIEW, "2" * 64, view, None, None)


# ---------------------------------------------------------------------------
# Q1 — the commit is what keeps the stage's bytes
# ---------------------------------------------------------------------------


def test_a_stage_views_writes_become_canonical_bytes(site: Site, tmp_path: Path) -> None:
    """C1: after the commit the host tree holds the bytes and the revision moved."""
    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        port, grant = _stage_port(managed, plan)
        port.write_file("src/kept.py", "KEPT = True\n")
        port.write_file("scripts/run.sh", "echo kept\n")
        assert not (site.source / "src/kept.py").exists()  # nothing host-side yet

        published = managed.publish_stage(grant)

        assert isinstance(published, StagePublication)
        assert published.sealed_manifest_id.startswith("seal-")
        assert published.revision_id.startswith("rev-")
        assert published.operation_id.startswith("op-")
        assert (site.source / "src/kept.py").read_text(encoding="utf-8") == "KEPT = True\n"
        assert (site.source / "scripts/run.sh").read_text(encoding="utf-8") == "echo kept\n"
        # The plan the run promised is byte-identical: a stage commits ordinary bytes only.
        assert (site.source / PLAN_RELATIVE).read_bytes() == PLAN_BYTES
        # The run keeps its writer: the next stage opens its own view on the new base.
        following = managed.open_view(
            access=Access.WRITE,
            purpose=ViewPurpose.MUTATION,
            base_revision=published.revision_id,
            plan_ref=plan,
        )
        assert following.view_ref is not None
        assert following.view_ref.base_revision == published.revision_id


def test_a_committed_view_is_closed_to_further_writes(site: Site, tmp_path: Path) -> None:
    """C1: a write after the projection cannot land in the committed tree."""
    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        port, grant = _stage_port(managed, plan)
        port.write_file("src/first.py", "one")
        managed.publish_stage(grant)

        with pytest.raises(WorkspacePortError) as late:
            port.write_file("src/second.py", "two")

        assert late.value.code in {"denied", "unavailable", "stale"}
        assert not (site.source / "src/second.py").exists()


# ---------------------------------------------------------------------------
# Q3 — CT97: the plan cannot travel through a stage view
# ---------------------------------------------------------------------------


def test_the_plan_is_not_writable_from_a_stage_view(site: Site, tmp_path: Path) -> None:
    """C1 (CT97, first line): the authority refuses the plan path to any write view.

    Measured over the live service: `WRITE_FILE` on the view's own `plan_ref` path
    is `PATH_DENIED` (E259's gate), not merely refused later at seal. The canonical
    bytes stay identical and the stage has nothing to commit.
    """
    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        port, grant = _stage_port(managed, plan, purpose=ViewPurpose.PROJECT)

        with pytest.raises(WorkspacePortError) as refused:
            port.write_file(PLAN_RELATIVE, "# rewritten by the coder\n")

        assert refused.value.code == "denied"
        assert (site.source / PLAN_RELATIVE).read_bytes() == PLAN_BYTES
        port.write_file("src/ordinary.py", "fine = 1\n")
        # The stage still commits its ordinary bytes: the refused write left no trace.
        managed.publish_stage(grant)
        assert (site.source / "src/ordinary.py").read_text(encoding="utf-8") == "fine = 1\n"


def test_a_seal_refusal_stops_the_commit_before_any_publish() -> None:
    """C1 (CT97, second line): the seal's own plan boundary refuses the manifest.

    The write gate above makes this unreachable from a live write view today; the
    seal keeps it as the last line, and this proves the client does not publish a
    manifest the authority refused to seal.
    """
    grant = _fixed_grant()
    client = _FramedClient(
        {
            Operation.STOP_VIEW: {"terminal": True, "view_id": "view-1"},
            Operation.SEAL: ExecutionRejectedError("INPUT_POLICY", None),
        }
    )

    with pytest.raises(ExecutionRejectedError) as refused:
        client.publish_stage(_namespace(), view=grant.view_ref, grant=grant)

    assert refused.value.code == "INPUT_POLICY"
    assert client.sent == [Operation.STOP_VIEW, Operation.SEAL]


# ---------------------------------------------------------------------------
# Q4 — the CAS is the view's own base, checked by the authority
# ---------------------------------------------------------------------------


def test_a_moved_base_refuses_the_commit_before_any_projection(site: Site, tmp_path: Path) -> None:
    """C1: a stage that lost the race does not overwrite the revision that won."""
    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        stale_port, stale_grant = _stage_port(managed, plan)
        stale_port.write_file("src/mine.py", "mine\n")
        # A second view over the same base wins the commit; the first must not
        # then project its bytes over the revision that won.
        winning_port, winning_grant = _stage_port(managed, plan)
        winning_port.write_file("src/theirs.py", "theirs\n")
        assert managed.publish_stage(winning_grant).revision_id.startswith("rev-")

        with pytest.raises(ExecutionRejectedError) as refused:
            managed.publish_stage(stale_grant)

        assert refused.value.code in {"STALE_REVISION", "VIEW_CLOSED"}
        assert (site.source / "src/theirs.py").exists()
        assert not (site.source / "src/mine.py").exists()


def test_a_plan_write_cannot_overlap_an_open_stage_view(site: Site, tmp_path: Path) -> None:
    """C1: one write epoch at a time — the boundary must order commit and publish.

    Measured: a plan publication while a stage view is open is ``WORKSPACE_BUSY``,
    and the stage still commits cleanly afterwards. So `run_stage_with_plan_write_boundary`
    may not hold a stage view across a controller plan write; it commits first.
    """
    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        port, grant = _stage_port(managed, plan)
        port.write_file("src/stage.py", "stage\n")

        with pytest.raises(ExecutionRejectedError) as busy:
            managed.publish_plan(
                read_plan_snapshot(site.source, Path(PLAN_RELATIVE)),
                snapshot_from_bytes("draft.md", b"# Repaired plan\n"),
            )
        assert busy.value.code == "WORKSPACE_BUSY"

        managed.publish_stage(grant)
        assert (site.source / "src/stage.py").exists()


# ---------------------------------------------------------------------------
# Q5/Q6 — the wire shape, and what is never assumed
# ---------------------------------------------------------------------------


def test_an_unproven_end_seals_nothing() -> None:
    """C0: no terminality verdict means no seal, no publish — one refusal, no guessing."""
    client = _FramedClient({Operation.STOP_VIEW: {"terminal": False, "view_id": "view-1"}})
    grant = _fixed_grant()

    with pytest.raises(ExecutionUncertainError):
        client.publish_stage(_namespace(), view=grant.view_ref, grant=grant)

    assert client.sent == [Operation.STOP_VIEW]


def test_a_read_view_and_a_foreign_grant_never_reach_the_wire() -> None:
    """C0: the two caller bugs are refused locally, with no round trip."""
    read_grant = _read_view_grant()
    read_client = _FramedClient({})
    with pytest.raises(ExecutionContractError):
        read_client.publish_stage(_namespace(), view=read_grant.view_ref, grant=read_grant)

    write_grant = _fixed_grant()
    foreign_client = _FramedClient({})
    with pytest.raises(ExecutionContractError):
        foreign_client.publish_stage(_namespace(), view=write_grant.view_ref, grant=_other_write_grant())

    assert read_client.sent == [] and foreign_client.sent == []


def test_an_unproven_publish_is_reported() -> None:
    """C3: a lost publish reply may have committed the revision — it is reported as unproved."""
    grant = _fixed_grant()
    client = _FramedClient(
        {
            Operation.STOP_VIEW: {"terminal": True, "view_id": "view-1"},
            Operation.SEAL: SEAL_REPLY,
            Operation.PUBLISH: ExecutionUncertainError("op-1"),
        }
    )

    with pytest.raises(ExecutionUncertainError):
        client.publish_stage(_namespace(), view=grant.view_ref, grant=grant)

    assert client.sent == [Operation.STOP_VIEW, Operation.SEAL, Operation.PUBLISH]


def test_a_reply_that_names_another_revision_is_never_accepted() -> None:
    """C3: the committed revision must be the one seal derived from these bytes."""
    grant = _fixed_grant()
    client = _FramedClient(
        {
            Operation.STOP_VIEW: {"terminal": True, "view_id": "view-1"},
            Operation.SEAL: SEAL_REPLY,
            Operation.PUBLISH: {**PUBLISH_REPLY, "revision_id": "rev-" + "2" * 32},
        }
    )

    with pytest.raises(ExecutionUncertainError):
        client.publish_stage(_namespace(), view=grant.view_ref, grant=grant)


def test_a_malformed_seal_id_in_the_reply_is_a_contract_bug() -> None:
    """C3: a reply this client cannot type is a contract breach, not a publication."""
    grant = _fixed_grant()
    client = _FramedClient(
        {
            Operation.STOP_VIEW: {"terminal": True, "view_id": "view-1"},
            Operation.SEAL: {**SEAL_REPLY, "sealed_manifest_id": "not-a-seal"},
        }
    )

    with pytest.raises(ExecutionContractError):
        client.publish_stage(_namespace(), view=grant.view_ref, grant=grant)
    assert client.sent == [Operation.STOP_VIEW, Operation.SEAL]
