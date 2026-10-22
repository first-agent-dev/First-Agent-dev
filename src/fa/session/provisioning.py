"""Provisioning contract between session lifecycle and the workspace supervisor.

The session manager owns logical identity (manifest, session DB, run
reservations); the supervisor owns canonical workspace bytes. This module is the
narrow value boundary between them and deliberately imports nothing from
``fa.execution``, so the session layer never depends on the execution
implementation.

Ownership is expressed as data, once, in a frozen result: either the supervisor
registered and verified those bytes (``registered=True`` with a complete
identity) or the value describes uncommitted scratch that only the manager may
clean up. A partial result is a contract breach and is rejected at construction
time rather than repaired at a call site.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ProvisionMode(StrEnum):
    """Why the manager is asking for workspace bytes."""

    #: The caller named an existing directory and asked to use it.
    REUSE = "reuse"
    #: A new canonical root must be created from the managed source.
    PROVISION = "provision"


@dataclass(frozen=True, slots=True)
class ProvisionRequest:
    """One provisioning ask, carrying the real run identity it is admitted under."""

    mode: ProvisionMode
    session_id: str
    run_id: str
    workspace_path: Path
    deadline: float


@dataclass(frozen=True, slots=True)
class ProvisionedWorkspace:
    """Frozen ownership result: registered identity, or cleanup-eligible scratch."""

    registered: bool
    workspace_id: str | None
    revision_id: str | None
    tree_sha256: str | None

    def __post_init__(self) -> None:
        identity = (self.workspace_id, self.revision_id, self.tree_sha256)
        if self.registered:
            if any(value is None or value == "" for value in identity):
                raise ValueError("a registered provisioned workspace requires a complete identity")
            if len(str(self.tree_sha256)) != 64:
                raise ValueError("tree_sha256 must be a lowercase sha256 hex digest")
        elif any(value is not None for value in identity):
            raise ValueError("unregistered scratch has no supervisor identity")


#: The manager accepts any callable with this shape; production injects the
#: supervisor-backed adapter, tests inject the same boundary.
WorkspaceProvisioner = Callable[[ProvisionRequest], ProvisionedWorkspace]


__all__ = [
    "ProvisionMode",
    "ProvisionRequest",
    "ProvisionedWorkspace",
    "WorkspaceProvisioner",
]
