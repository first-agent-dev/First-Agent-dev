"""The real `CellTermination`: journal-owned cells, kernel-observed emptiness.

`supervisor.ViewStopper` owns *when* to stop and observe; this module owns *how*.
Two facts decide every answer:

* which cells belong to this view — the operation journal's own EXEC records with
  a durable container id (`owned_cells()`), filtered to the exact namespace and
  `ViewRef`. Nothing else is a cell inventory: not the live episode map (memory
  is lost on restart, and a one-shot cell never appears there), not a name.
* whether those cells' descendants are gone — `cgroup.descendants_empty()`, which
  answers `True` only for a readable `populated 0`.

A view that has no EXEC record with a container id has never had a cell, so its
emptiness is proved by the journal alone and needs no daemon contact. A view that
has one needs both a real backend (to stop it) and a cgroup observation: without
either the answer is `None`, and `stop_view` then reports `terminal: false`. No
stopped container, lost reply or elapsed budget is ever converted into `True`.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fa.execution import cgroup
from fa.execution.docker import DockerUnavailableError
from fa.execution.journal import JournalError, OperationJournal
from fa.execution.profiles import ExecutionProfile
from fa.execution.supervisor import SupervisorError
from fa.execution.types import ExecutionContractError, NamespaceRef, ViewRef


class OwnedCellTermination:
    """`CellTermination` over the journal, the owned-cell stop and the cgroup fact.

    Construction accepts `cells=None`/`profile=None` so the composed service can
    run without a Docker configuration: it can then prove that a never-executed
    view is empty, and it refuses (`cells_terminal` -> None) as soon as a cell
    would have to be observed. That refusal is the honest answer, not a stub.
    """

    def __init__(
        self,
        journal: OperationJournal,
        *,
        cells: Any | None,
        profile: ExecutionProfile | None,
        profile_for_view: Callable[[ViewRef], ExecutionProfile | None] | None = None,
        cgroup_root: Path = Path("/sys/fs/cgroup"),
    ) -> None:
        if not isinstance(journal, OperationJournal):
            raise ExecutionContractError
        # A seam, like `ViewStopper.cells`: the real `DockerCells` in production,
        # a recording double in the local bank. Only the one call is required.
        if cells is not None and not callable(getattr(cells, "force_stop_operation", None)):
            raise ExecutionContractError
        if profile is not None and not isinstance(profile, ExecutionProfile):
            raise ExecutionContractError
        if profile_for_view is not None and not callable(profile_for_view):
            raise ExecutionContractError
        if not isinstance(cgroup_root, Path) or not cgroup_root.is_absolute():
            raise ExecutionContractError
        self._journal, self._cells, self._profile = journal, cells, profile
        self._profile_for_view = profile_for_view
        self._cgroup_root = cgroup_root

    def _bindings(self, namespace: NamespaceRef, view_ref: ViewRef) -> list[dict[str, Any]]:
        """This view's EXEC records that still bind a durable container id."""
        if not isinstance(namespace, NamespaceRef) or not isinstance(view_ref, ViewRef):
            raise ExecutionContractError
        try:
            records = self._journal.owned_cells()
        except JournalError as error:
            raise SupervisorError(error.code) from None
        return [
            record
            for record in records
            if record["namespace"] == namespace.to_dict() and record["view_ref"] == view_ref.to_dict()
        ]

    def _profile_for(self, view_ref: ViewRef) -> ExecutionProfile | None:
        if self._profile_for_view is not None:
            return self._profile_for_view(view_ref)
        return self._profile

    def stop_cells(self, namespace: NamespaceRef, view_ref: ViewRef, *, deadline: float) -> None:
        """Stop every owned cell with the profile bound to this exact view."""
        records = self._bindings(namespace, view_ref)
        if not records:
            return
        profile = self._profile_for(view_ref)
        if self._cells is None or profile is None:
            raise SupervisorError("BACKEND_UNAVAILABLE")
        stopped_cells: set[tuple[str, str]] = set()
        for record in records:
            if deadline <= time.monotonic():
                raise SupervisorError("BACKEND_UNAVAILABLE")
            try:
                owner_operation_id = self._journal.resolve_cell_owner(
                    record["operation_id"],
                    namespace,
                    view=view_ref,
                    container_id=record["container_id"],
                    deadline=deadline,
                )
                identity = (owner_operation_id, record["container_id"])
                if identity in stopped_cells:
                    continue
                # The creator record is the durable cell identity. Each EXEC
                # keeps its own receipt, but one interactive cell is stopped once.
                self._cells.force_stop_operation(
                    operation_id=owner_operation_id,
                    namespace=namespace,
                    view=view_ref,
                    profile=profile,
                    deadline=deadline,
                )
                stopped_cells.add(identity)
            except JournalError as error:
                raise SupervisorError(error.code) from None
            except ExecutionContractError:
                raise SupervisorError("PATH_DENIED") from None
            except DockerUnavailableError as error:
                raise SupervisorError("PATH_DENIED" if error.status is None else "BACKEND_UNAVAILABLE") from None
            except TimeoutError:
                raise SupervisorError("BACKEND_UNAVAILABLE") from None

    def cells_terminal(self, namespace: NamespaceRef, view_ref: ViewRef) -> bool | None:
        """True only when every cell of this view is kernel-proved empty."""
        records = self._bindings(namespace, view_ref)
        container_ids = sorted({record["container_id"] for record in records if record["container_id"]})
        if not container_ids:
            # No EXEC record binds a cell: nothing was created, so nothing can
            # still be writing. A journal fact, not an inference from silence.
            return True
        profile = self._profile_for(view_ref)
        if profile is None:
            return None
        try:
            verdicts = [
                cgroup.descendants_empty(self._cgroup_root, profile.cgroup_parent, container_id)
                for container_id in container_ids
            ]
        except ValueError:
            return None
        if any(verdict is False for verdict in verdicts):
            return False
        if any(verdict is None for verdict in verdicts):
            return None
        return True
