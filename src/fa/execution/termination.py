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
        if not isinstance(cgroup_root, Path) or not cgroup_root.is_absolute():
            raise ExecutionContractError
        self._journal, self._cells, self._profile = journal, cells, profile
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

    def stop_cells(self, namespace: NamespaceRef, view_ref: ViewRef, *, deadline: float) -> None:
        """Stop every owned cell of this view; never create, replace or replay one."""
        records = self._bindings(namespace, view_ref)
        if not records:
            return
        if self._cells is None or self._profile is None:
            raise SupervisorError("BACKEND_UNAVAILABLE")
        for record in records:
            if deadline <= time.monotonic():
                raise SupervisorError("BACKEND_UNAVAILABLE")
            try:
                # The record's own id is the identity: intent is persisted before
                # any daemon contact, and a cancelled record cannot be created or
                # started later (E262/E249 rules).
                self._cells.force_stop_operation(
                    operation_id=record["operation_id"],
                    namespace=namespace,
                    view=view_ref,
                    profile=self._profile,
                    deadline=deadline,
                )
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
        if self._profile is None:
            return None
        try:
            verdicts = [
                cgroup.descendants_empty(self._cgroup_root, self._profile.cgroup_parent, container_id)
                for container_id in container_ids
            ]
        except ValueError:
            return None
        if any(verdict is False for verdict in verdicts):
            return False
        if any(verdict is None for verdict in verdicts):
            return None
        return True
