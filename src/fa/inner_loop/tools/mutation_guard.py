"""Shared pre-write conflict contract for the mutating filesystem tools (S5.4).

Both ``fs.write_file`` and ``fs.edit_file`` must answer one question the same
way before touching a file: *may this agent mutate this path right now?* This
module owns that decision so the two tools cannot drift apart — ``edit_file``
previously had no check at all while claiming in its docstring to share one
with ``write_file`` (gap V15/V17).

Posture (ADR-16 I-6.3)
----------------------
Fail **closed** when the substrate is present but broken: an unguarded write is
a silent correctness hole, a denied write is a loud, diagnosable one. Fail
**open** when the substrate is deliberately absent, because disabling a guard
on purpose is not the same as a guard failing:

===========================  ==========================  ================
situation                    meaning                     outcome
===========================  ==========================  ================
no session bound             direct/library tool use     permit
``blackboard_enabled=False`` operator disabled it        permit
Blackboard from another root leaked contextvar           permit (ignore)
conflicting entry found      another agent claimed it    ``conflict_detected``
Blackboard raised            substrate is broken         ``blackboard_unavailable``
===========================  ==========================  ================

The last row is the behaviour change this slice lands: those paths previously
logged ``"Blackboard check failed: ..., allowing write"`` and permitted the
mutation. Denials name *which* precondition failed (S5-P25) so an operator can
tell "the substrate is broken" from "you have a real conflict".
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
import uuid
from pathlib import Path
from typing import Any

from fa.inner_loop.registry import ToolResult

logger = logging.getLogger(__name__)

# Denial codes. Kept distinct so operators and the model can tell the cause
# apart; collapsing them into one generic refusal is the S5-P25 kill-check.
CONFLICT_DETECTED = "conflict_detected"
BLACKBOARD_UNAVAILABLE = "blackboard_unavailable"


def _base_commit(root: Path) -> str:
    """Short HEAD sha for version_dependencies, or ``"unknown"``.

    Degrading to ``"unknown"`` is intentional: a workspace need not be a git
    repo, and conflict detection must still work there.
    """
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            return res.stdout.strip()[:12]
    except Exception as exc:  # noqa: BLE001 # not the substrate; observable WARNING
        logger.warning("base_commit lookup failed: %s", exc)
    return "unknown"


def _file_hash(path: Path) -> str:
    """Short content hash for version_dependencies, or ``"missing"``."""
    try:
        if path.exists():
            return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    except Exception as exc:  # noqa: BLE001 # not the substrate; observable WARNING
        logger.warning("file hash failed for %s: %s", path, exc)
    return "missing"


def _llms_path_for(root: Path) -> Path:
    """Locate ``llms.txt`` for the version-dependency stamp."""
    candidate = root / "knowledge" / "llms.txt"
    return candidate if candidate.exists() else root / "llms.txt"


def belongs_to_workspace(blackboard: Any, root: Path) -> bool:
    """Whether ``blackboard`` is the one for ``root``.

    Protects against a leaked contextvar handing us another workspace's
    substrate: entries there describe different files and must not deny writes
    here. A Blackboard we cannot place is treated as foreign (ignored) rather
    than as authority, because acting on the wrong authority is worse than not
    acting on it.
    """
    try:
        bb_root = Path(getattr(blackboard, "root", Path("/"))).resolve()
        expected = root.resolve()
        return bb_root == expected / ".fa" / "blackboard" or bb_root.is_relative_to(expected)
    except Exception as exc:  # noqa: BLE001 # observable WARNING, treat as foreign
        logger.warning("blackboard ownership check failed: %s, ignoring blackboard", exc)
        return False


def _entry_for(
    *,
    entry_id: str,
    root: Path,
    read_set: list[str],
    write_set: list[str],
) -> Any:
    from fa.blackboard.blackboard import BlackboardEntry

    base = _base_commit(root)
    return BlackboardEntry.create(
        id=entry_id,
        type="file_version",
        payload={"path": write_set[0] if write_set else "unknown"},
        read_set=read_set,
        write_set=write_set,
        assumptions=[f"base_commit {base}"],
        version_dependencies={
            "base_commit": base,
            "llms.txt": _file_hash(_llms_path_for(root)),
        },
    )


def check_mutation_allowed(
    blackboard: Any,
    *,
    read_set: list[str],
    write_set: list[str],
    root: Path,
) -> ToolResult | None:
    """Return a denial ``ToolResult``, or ``None`` when the mutation may proceed.

    Called by both mutating tools *before* the file is touched.
    """
    # Substrate deliberately absent (no session bound, or blackboard_enabled=
    # False). Supported configuration — cli.py:972 ships it. Permit.
    if blackboard is None:
        return None

    # Leaked contextvar from another workspace: not our authority. Permit.
    if not belongs_to_workspace(blackboard, root):
        return None

    try:
        conflicts = blackboard.detect_conflict(
            _entry_for(
                entry_id=f"pre-{uuid.uuid4().hex[:8]}",
                root=root,
                read_set=read_set,
                write_set=write_set,
            )
        )
    except Exception as exc:  # noqa: BLE001 # substrate present but broken -> fail closed
        logger.warning("Blackboard conflict check failed for %s: %s, denying", write_set, exc)
        return ToolResult.fail(
            BLACKBOARD_UNAVAILABLE,
            (
                f"Cannot verify write safety for {write_set}: the blackboard is present but "
                f"unreadable ({exc}). Refusing the mutation rather than writing unguarded. "
                "Check the session database, then retry."
            ),
            retryable=True,
        )

    if conflicts:
        details = "; ".join(c.reason for c in conflicts)
        ids = [c.conflicting_entry_id for c in conflicts]
        return ToolResult.fail(
            CONFLICT_DETECTED,
            f"Conflict for {write_set}: {details}. Conflicts: {ids}",
            retryable=True,
        )
    return None


def record_mutation(
    blackboard: Any,
    *,
    read_set: list[str],
    write_set: list[str],
    root: Path,
    payload_extra: dict[str, Any] | None = None,
) -> None:
    """Append the post-write ``file_version`` entry.

    Best-effort by design: the mutation already happened, so failing here must
    not turn a successful write into an error. The write is still visible in
    the event log, and S5.4.1 means this entry never blocks its own author.
    """
    if blackboard is None or not belongs_to_workspace(blackboard, root):
        return
    try:
        entry = _entry_for(
            entry_id=f"post-{uuid.uuid4().hex[:8]}",
            root=root,
            read_set=read_set,
            write_set=write_set,
        )
        if payload_extra:
            entry.payload = {**entry.payload, **payload_extra}
        blackboard.write(entry)
    except Exception as exc:  # noqa: BLE001 # post-write bookkeeping; observable WARNING
        logger.warning("Blackboard post-write record failed for %s: %s", write_set, exc)


__all__ = [
    "BLACKBOARD_UNAVAILABLE",
    "CONFLICT_DETECTED",
    "belongs_to_workspace",
    "check_mutation_allowed",
    "record_mutation",
]
