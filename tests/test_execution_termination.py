"""E278 — the terminal barrier's two facts: owned cells and kernel emptiness.

Classes (knowledge/skills/tests-writing):
  C3 — `cgroup.descendants_empty` over a real filesystem (real directories, real
       symlinks, real oversized/malformed files) and `OwnedCellTermination` over
       the real `OperationJournal` on disk;
  C1 — the stop call's Docker seam is a recording double: issuing a real
       SIGKILL to a real container is host work (`tests/integration` under
       `FA_REQUIRE_EXECUTION_HOST=1`), not something a unit can claim.

What must stay true (each test names the producer it kills):
  * `True` exists only for a readable `populated 0` — never for a missing
    cgroup, an unreadable one, a symlink, a malformed file or a truncated read;
  * both known driver layouts are probed, and the cgroupfs one wins when both
    exist;
  * a view with no EXEC record binding a container id is empty by a *journal*
    fact, and needs no daemon;
  * a view with a cell is never called empty without a cgroup answer, and is
    never stopped without a backend;
  * the stop uses the record's own operation id and the exact view, so one
    view's stop cannot touch another's cell.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from fa.execution.cgroup import descendants_empty
from fa.execution.profiles import ExecutionProfile
from fa.execution.supervisor import SupervisorError
from fa.execution.termination import OwnedCellTermination
from fa.execution.types import Access, ExecutionContractError, GrantReply, NamespaceRef, ViewPurpose, ViewRef
from tests.test_execution_admission import claim as claim_operation
from tests.test_execution_admission import request as exec_request
from tests.test_execution_readers import ref
from tests.test_execution_views import native_profile
from tests.test_execution_workspace import ACTOR, PEER, Site
from tests.test_execution_workspace import site as site

CID = "a" * 64
OTHER_CID = "b" * 64


def until() -> float:
    return time.monotonic() + 10


def _events(root: Path, parent: str, name: str, body: str) -> Path:
    directory = root.joinpath(*parent.split("/")) / name
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "cgroup.events"
    path.write_text(body)
    return path


# ---------------------------------------------------------------------------
# C3 — the kernel fact
# ---------------------------------------------------------------------------


def test_populated_zero_is_the_only_true_answer(tmp_path: Path) -> None:
    """producer-kill-check: treat any readable cgroup.events as empty."""
    _events(tmp_path, "fa.slice", CID, "populated 0\nfrozen 0\n")
    assert descendants_empty(tmp_path, "fa.slice", CID) is True
    _events(tmp_path, "fa.slice", OTHER_CID, "populated 3\nfrozen 0\n")
    assert descendants_empty(tmp_path, "fa.slice", OTHER_CID) is False


def test_the_systemd_scope_layout_is_also_a_real_cell_location(tmp_path: Path) -> None:
    """producer-kill-check: only probe the cgroupfs layout."""
    _events(tmp_path, "fa.slice/sub", f"docker-{CID}.scope", "populated 0\n")
    assert descendants_empty(tmp_path, "fa.slice/sub", CID) is True


def test_cgroupfs_wins_when_both_layouts_exist(tmp_path: Path) -> None:
    """producer-kill-check: pick whichever layout sorts first."""
    _events(tmp_path, "fa.slice", CID, "populated 1\n")
    _events(tmp_path, "fa.slice", f"docker-{CID}.scope", "populated 0\n")
    assert descendants_empty(tmp_path, "fa.slice", CID) is False


@pytest.mark.parametrize(
    "body",
    [
        "",  # empty file
        "frozen 0\n",  # no population line at all
        "populated 0\npopulated 0\n",  # ambiguous double answer
        "populated zero\n",  # not an integer
        "POPULATED 0\n",  # not the kernel's spelling
    ],
)
def test_malformed_events_are_unknown_never_empty(tmp_path: Path, body: str) -> None:
    """producer-kill-check: search for 'populated 0' instead of parsing one line."""
    _events(tmp_path, "fa.slice", CID, body)
    assert descendants_empty(tmp_path, "fa.slice", CID) is None


def test_a_missing_cgroup_is_unknown_not_empty(tmp_path: Path) -> None:
    """producer-kill-check: a missing path means the cell is gone."""
    assert descendants_empty(tmp_path, "fa.slice", CID) is None


def test_an_unreadable_or_wrong_shaped_path_is_unknown(tmp_path: Path) -> None:
    """producer-kill-check: follow a symlink or accept a directory as a file."""
    directory = tmp_path / "fa.slice" / CID
    directory.mkdir(parents=True)
    (directory / "cgroup.events").mkdir()  # a directory, not the kernel file
    assert descendants_empty(tmp_path, "fa.slice", CID) is None

    directory2 = tmp_path / "fa.slice" / OTHER_CID
    directory2.mkdir()
    target = tmp_path / "elsewhere.events"
    target.write_text("populated 0\n")
    (directory2 / "cgroup.events").symlink_to(target)
    assert descendants_empty(tmp_path, "fa.slice", OTHER_CID) is None


def test_an_oversized_events_file_is_unknown(tmp_path: Path) -> None:
    """producer-kill-check: read without a bound."""
    path = _events(tmp_path, "fa.slice", CID, "populated 0\n")
    path.write_text("populated 0\n" + "#" * (70 * 1024))
    assert descendants_empty(tmp_path, "fa.slice", CID) is None


@pytest.mark.parametrize(
    ("parent", "container_id"), [("../escape", CID), ("/abs", CID), ("a//b", CID), ("ok", "A" * 64)]
)
def test_a_bad_parent_or_id_is_refused_not_answered(tmp_path: Path, parent: str, container_id: str) -> None:
    """producer-kill-check: join an unvalidated parent into the cgroup path."""
    with pytest.raises(ValueError, match=r"cgroup parent|container id"):
        descendants_empty(tmp_path, parent, container_id)


# ---------------------------------------------------------------------------
# C3/C1 — the adapter
# ---------------------------------------------------------------------------


class RecordingCells:
    """The `DockerCells` seam: records the stop, never signals a process."""

    def __init__(self, *, failure: Exception | None = None) -> None:
        self.stops: list[tuple[str, NamespaceRef, ViewRef]] = []
        self.failure = failure

    def force_stop_operation(
        self,
        *,
        operation_id: str,
        namespace: NamespaceRef,
        view: ViewRef,
        profile: ExecutionProfile,
        deadline: float,
    ) -> None:
        self.stops.append((operation_id, namespace, view))
        if self.failure is not None:
            raise self.failure


def _project_view(owner: Any, ids: dict[str, str], lease: GrantReply) -> GrantReply:
    return owner.create_view(
        PEER,
        ACTOR,
        workspace_id=ids["workspace_id"],
        capability=lease.capability,
        purpose=ViewPurpose.PROJECT,
        access=Access.WRITE,
        candidate_scope=None,
        plan_ref=None,
        formal_evidence=False,
        deadline=until(),
    )


def _view_with_cell(site: Site) -> tuple[Any, ViewRef, str]:
    """A live view plus one EXEC record that really binds a container id."""
    owner = site.owner(view_profile=native_profile())
    owner.__enter__()
    ids = site.register(owner)
    lease = site.claim(owner, ids)
    grant = _project_view(owner, ids, lease)
    request = exec_request(grant)
    claim_operation(owner, request)
    owner.journal.record_container(request["payload"]["operation_id"], ACTOR, CID)
    return owner, ref(grant), request["payload"]["operation_id"]


def test_a_view_with_no_exec_record_is_empty_by_the_journal_alone(site: Site) -> None:
    """producer-kill-check: require a Docker observation for a view that never ran."""
    owner = site.owner(view_profile=native_profile())
    with owner:
        ids = site.register(owner)
        lease = site.claim(owner, ids)
        grant = _project_view(owner, ids, lease)
        termination = OwnedCellTermination(owner.journal, cells=None, profile=native_profile())
        assert termination.cells_terminal(ACTOR, ref(grant)) is True
        termination.stop_cells(ACTOR, ref(grant), deadline=until())  # nothing to stop, no error


def test_a_cell_without_a_backend_is_never_terminal_and_never_stopped(site: Site) -> None:
    """producer-kill-check: answer True when no backend could observe the cell."""
    owner, view, _operation_id = _view_with_cell(site)
    try:
        termination = OwnedCellTermination(owner.journal, cells=None, profile=native_profile())
        assert termination.cells_terminal(ACTOR, view) is None
        with pytest.raises(SupervisorError) as refused:
            termination.stop_cells(ACTOR, view, deadline=until())
        assert refused.value.code == "BACKEND_UNAVAILABLE"
        # A missing profile is the same refusal: no cgroup parent, no fact.
        unprofiled = OwnedCellTermination(owner.journal, cells=RecordingCells(), profile=None)
        assert unprofiled.cells_terminal(ACTOR, view) is None
    finally:
        owner.__exit__(None, None, None)


def test_a_cell_is_stopped_by_its_own_record_and_observed_in_its_cgroup(site: Site, tmp_path: Path) -> None:
    """producer-kill-check: stop by name, or read another cell's cgroup."""
    owner, view, operation_id = _view_with_cell(site)
    try:
        cells = RecordingCells()
        termination = OwnedCellTermination(owner.journal, cells=cells, profile=native_profile(), cgroup_root=tmp_path)
        _events(tmp_path, native_profile().cgroup_parent, CID, "populated 1\n")
        assert termination.cells_terminal(ACTOR, view) is False
        # Another view of the same workspace owns no cell: while THIS one is
        # populated, that one is still empty, and it stops nothing.
        other = ViewRef.from_dict({**view.to_dict(), "view_id": "view-" + "c" * 32})
        assert termination.cells_terminal(ACTOR, other) is True
        termination.stop_cells(ACTOR, other, deadline=until())
        assert cells.stops == []

        termination.stop_cells(ACTOR, view, deadline=until())
        assert [(op, ns, ref_view) for op, ns, ref_view in cells.stops] == [(operation_id, ACTOR, view)]

        _events(tmp_path, native_profile().cgroup_parent, CID, "populated 0\n")
        assert termination.cells_terminal(ACTOR, view) is True
    finally:
        owner.__exit__(None, None, None)


def test_a_stop_failure_is_a_closed_code_not_a_terminal_claim(site: Site, tmp_path: Path) -> None:
    """producer-kill-check: swallow the daemon failure and report the stop succeeded."""
    owner, view, _operation_id = _view_with_cell(site)
    try:
        cells = RecordingCells(failure=RuntimeError("daemon gone"))
        termination = OwnedCellTermination(owner.journal, cells=cells, profile=native_profile(), cgroup_root=tmp_path)
        with pytest.raises(RuntimeError):
            termination.stop_cells(ACTOR, view, deadline=until())
        assert termination.cells_terminal(ACTOR, view) is None  # no cgroup file was written
    finally:
        owner.__exit__(None, None, None)


def test_the_adapter_refuses_a_partial_configuration(tmp_path: Path, site: Site) -> None:
    """producer-kill-check: accept a relative cgroup root or a non-journal."""
    owner = site.owner(view_profile=native_profile())
    with owner:
        with pytest.raises(ExecutionContractError):
            OwnedCellTermination(owner.journal, cells=None, profile=native_profile(), cgroup_root=Path("relative"))
        with pytest.raises(ExecutionContractError):
            OwnedCellTermination(object(), cells=None, profile=native_profile())  # type: ignore[arg-type]
