"""Candidate allocation and the managed publication port (Q58 / Q89).

The controller may create a private draft for planner tools, but it never
replaces the canonical plan by host-path IO. Promotion is delegated to the
injected execution publisher, which stages the validated bytes in the
supervisor-owned CANDIDATE buffer and commits them through Operation.PUBLISH.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from fa.inner_loop.plan_admission import PlanRef, PlanSnapshot, snapshot_from_bytes
from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind
from fa.inner_loop.workflow_artifacts import _private_artifact_directory

_CANONICAL_PARENT = ("worklogs", "planning-topology-and-executable-contracts-loop", "increments")


class PlanPromotionError(ValueError):
    """Static closed reason and irreversible-boundary state; no paths or bodies."""

    def __init__(self, rule: str, *, replaced: bool = False) -> None:
        self.rule = rule
        self.replaced = replaced
        super().__init__(f"plan promotion failed: {rule}")


class CandidatePlanPublisher(Protocol):
    """Injected port for one validated candidate-to-PLAN publication."""

    def publish_candidate(
        self, source: PlanSnapshot, candidate: PlanSnapshot, *, deadline: float | None = None
    ) -> PlanRef: ...


def _canonical_parts(snapshot: PlanSnapshot) -> tuple[str, ...]:
    parts = tuple(snapshot.ref.workspace_relative_path.split("/"))
    if len(parts) < 4 or parts[:3] != _CANONICAL_PARENT or any(p in {"", ".", ".."} or "\x00" in p for p in parts):
        raise PlanPromotionError("scope-denied")
    return parts


def _write_all(fd: int, raw: bytes) -> None:
    remaining = memoryview(raw)
    while remaining:
        written = os.write(fd, remaining)
        if written <= 0:
            raise OSError("short plan write")
        remaining = remaining[written:]


def seed_plan_candidate(
    workspace: Path,
    source: PlanSnapshot,
    *,
    run_id: str,
    kind: PlannerDispatchKind,
    draft: PlanSnapshot | None = None,
) -> PlannerDispatch:
    """Fresh no-clobber draft from exact captured bytes, never a second active plan."""
    _canonical_parts(source)  # Scope rejection must precede candidate allocation/provider.
    if kind == PlannerDispatchKind.ORDINARY_PLANNING:
        raise PlanPromotionError("scope-denied")
    target = f".fa/admission/{run_id}/candidate-{uuid4().hex}.md"
    dispatch = PlannerDispatch(kind, run_id, source.ref.workspace_relative_path, target)
    raw = source.utf8_bytes if draft is None else draft.utf8_bytes
    snapshot_from_bytes(target, raw)  # Strict UTF-8/nonempty/size; structural FAILs may seed.
    path = workspace / target
    try:
        with _private_artifact_directory(path.parent) as parent:
            _create_candidate(parent, path.name, raw)
    except OSError as error:
        raise PlanPromotionError("prepare-failed") from error
    return dispatch


def _create_candidate(parent: int, name: str, raw: bytes) -> None:
    created = False
    complete = False
    try:
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=parent)
        created = True
        try:
            _write_all(fd, raw)
            os.fchmod(fd, 0o600)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(parent)
        complete = True
    finally:
        if created and not complete:
            os.unlink(name, dir_fd=parent)


__all__ = ["CandidatePlanPublisher", "PlanPromotionError", "seed_plan_candidate"]
