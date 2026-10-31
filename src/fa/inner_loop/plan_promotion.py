"""Candidate allocation and the managed publication port (Q58 / Q89).

The controller may create a private draft for planner tools, but it never
replaces the canonical plan by host-path IO. Promotion is delegated to the
injected execution publisher, which stages the validated bytes in the
supervisor-owned CANDIDATE buffer and commits them through Operation.PUBLISH.
"""

from __future__ import annotations

import os
import time
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


#: The one refused-draft slot per run. A fixed name, not a digest: the operator
#: reads the draft the run last refused, and the attempts themselves are already
#: hashed in ``admission.json`` (``candidate_sha256`` per attempt), so the file
#: name does not have to carry evidence.
_DRAFT_NAME = "draft.md"


def retain_plan_draft(workspace: Path, run_id: str, raw: bytes, *, deadline: float | None = None) -> Path:
    """CT119 / Q100: one refused draft per run, replaced atomically.

    A newer refusal supersedes the older bytes — the run keeps what it refused
    last, not an archaeology of attempts. Replacement never loses the current
    draft: the bytes are written to a private temporary file in the same
    directory, fsynced, and renamed over the slot, so a reader sees either the
    old draft or the new one and a crash (or a failed write) leaves the old one
    untouched. Retention writes only after the run's own deadline check, because
    a draft kept past the budget delays the operator's answer without helping it.
    """
    if deadline is not None and time.monotonic() > deadline:
        raise PlanPromotionError("prepare-failed")
    if not run_id or "/" in run_id or run_id in {".", ".."} or "\x00" in run_id:
        raise PlanPromotionError("scope-denied")
    path = workspace / f".fa/admission/{run_id}" / _DRAFT_NAME
    temporary = f".{_DRAFT_NAME}.{uuid4().hex}.tmp"
    try:
        with _private_artifact_directory(path.parent) as parent:
            try:
                _create_candidate(parent, temporary, raw)
                os.replace(temporary, _DRAFT_NAME, src_dir_fd=parent, dst_dir_fd=parent)
                os.fsync(parent)
            except BaseException:
                # Nothing was replaced unless the rename completed: drop the
                # temporary file and leave whatever draft the run already had.
                try:
                    os.unlink(temporary, dir_fd=parent)
                except OSError:
                    pass
                raise
    except (OSError, ValueError) as error:
        raise PlanPromotionError("prepare-failed") from error
    return path


__all__ = ["CandidatePlanPublisher", "PlanPromotionError", "retain_plan_draft", "seed_plan_candidate"]
