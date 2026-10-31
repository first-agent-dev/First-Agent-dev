"""Provisioning contract between session lifecycle and the workspace supervisor.

The session manager owns logical identity (manifest, session DB, run
reservations); the supervisor owns canonical workspace bytes. This module is the
narrow value boundary between them and deliberately imports nothing from
``fa.execution``, so the session layer never depends on the execution
implementation.

Ownership is expressed as data, once, in a frozen result: either the supervisor
registered and verified those bytes (``registered=True`` with the identity it owns)
or the value describes uncommitted scratch that only the manager may clean up. A
partial result is a contract breach and is rejected at construction time rather
than repaired at a call site.

``tree_sha256`` is optional on a registered result because the supervisor's
``register_workspace`` answer carries ``workspace_id`` and ``revision_id`` only
(``service.py:591``, spec ``:153``); a caller that already holds the tree hash may
still pass it, and it is validated when present.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

_SHA256 = re.compile(r"[0-9a-f]{64}")


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
            if any(value is None or value == "" for value in identity[:2]):
                raise ValueError("a registered provisioned workspace requires a complete identity")
            if self.tree_sha256 is not None and _SHA256.fullmatch(str(self.tree_sha256)) is None:
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
