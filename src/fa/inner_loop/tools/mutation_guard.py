"""Shared pre-write conflict contract for the mutating filesystem tools (S5.4).

Both ``fs_write_file`` and ``fs_edit_file`` must answer one question the same
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

For a managed workspace the logical host root is not the admitted view. An
active Blackboard check requires revision and file stamps read from the admitted
view; missing or invalid view metadata fails closed and the legacy host lookup
must not run. An explicitly disabled board or direct use with no active session
remains supported.
"""

from __future__ import annotations

import hashlib
import logging
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any

from fa.inner_loop.registry import ToolResult
from fa.inner_loop.tools.workspace_port import PORT_READ_MAX_BYTES, PortRead, WorkspacePort

logger = logging.getLogger(__name__)

# Denial codes. Kept distinct so operators and the model can tell the cause
# apart; collapsing them into one generic refusal is the S5-P25 kill-check.
CONFLICT_DETECTED = "conflict_detected"
BLACKBOARD_UNAVAILABLE = "blackboard_unavailable"
_SHA256 = re.compile(r"[0-9a-f]{64}")


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
            check=False,  # a non-zero exit is the documented "unknown" answer below
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


def managed_metadata_required(session: Any) -> bool:
    """Whether this managed session requires view-bound stamps for Blackboard checks."""
    if session is None:
        return False
    flags = session.feature_flags
    return flags is None or flags.blackboard_enabled is not False


def managed_version_dependencies(workspace_io: WorkspacePort) -> dict[str, str] | None:
    """Read conflict stamps from the admitted view, never from the controller's project path."""
    base_revision = getattr(workspace_io, "base_revision_id", None)
    if not isinstance(base_revision, str) or re.fullmatch(r"rev-[0-9a-f]{32}", base_revision) is None:
        return None
    try:
        llms = workspace_io.read_file("knowledge/llms.txt", max_bytes=PORT_READ_MAX_BYTES)
    except Exception as exc:  # noqa: BLE001 # all managed metadata failures deny the write
        logger.warning("managed llms metadata read failed: %s", exc)
        return None
    if (
        not isinstance(llms, PortRead)
        or not isinstance(llms.content, str)
        or llms.eof is not True
        or not isinstance(llms.sha256, str)
        or _SHA256.fullmatch(llms.sha256) is None
        or hashlib.sha256(llms.content.encode("utf-8")).hexdigest() != llms.sha256
    ):
        return None
    return {"base_revision": base_revision, "llms.txt": llms.sha256[:12]}


def _entry_for(
    *,
    entry_id: str,
    root: Path,
    read_set: list[str],
    write_set: list[str],
    managed_versions: dict[str, str] | None = None,
) -> Any:
    from fa.blackboard.blackboard import BlackboardEntry

    if managed_versions is None:
        revision_key = "base_commit"
        base = _base_commit(root)
        llms_sha = _file_hash(_llms_path_for(root))
    else:
        revision_key = "base_revision"
        base = managed_versions["base_revision"]
        llms_sha = managed_versions["llms.txt"]
    return BlackboardEntry.create(
        id=entry_id,
        type="file_version",
        payload={"path": write_set[0] if write_set else "unknown"},
        read_set=read_set,
        write_set=write_set,
        assumptions=[f"{revision_key} {base}"],
        version_dependencies={revision_key: base, "llms.txt": llms_sha},
    )


def check_mutation_allowed(
    blackboard: Any,
    *,
    read_set: list[str],
    write_set: list[str],
    root: Path,
    managed: bool = False,
    session: Any = None,
    managed_versions: dict[str, str] | None = None,
) -> ToolResult | None:
    """Return a denial ``ToolResult``, or ``None`` when the mutation may proceed.

    Called by both mutating tools *before* the file is touched.
    """
    # A logical host root is not the managed view. Active managed checks need
    # view-bound stamps; host Git or file hashes cannot prove this conflict
    # check. A configured board that failed initialization is not the same as a
    # deliberately disabled board.
    if managed:
        if session is None:
            # Preserve session-less direct/library use only when no Blackboard
            # check is active; an attached board needs view-bound stamps.
            if blackboard is None:
                return None
            if managed_versions is None:
                return ToolResult.fail(
                    BLACKBOARD_UNAVAILABLE,
                    "managed workspace conflict metadata is unavailable; refusing mutation",
                    retryable=False,
                )
        elif managed_metadata_required(session):
            if blackboard is None or managed_versions is None:
                return ToolResult.fail(
                    BLACKBOARD_UNAVAILABLE,
                    "managed workspace conflict metadata is unavailable; refusing mutation",
                    retryable=False,
                )
        else:
            # Explicit operator disable is the only managed-session bypass.
            blackboard = None

    # Direct/library use and deliberately disabled boards keep their supported
    # behavior; a foreign/active board without a session is still not trusted.
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
                managed_versions=managed_versions if managed else None,
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
    managed: bool = False,
    managed_versions: dict[str, str] | None = None,
    session: Any = None,
) -> None:
    """Append the post-write ``file_version`` entry.

    Best-effort by design: the mutation already happened, so failing here must
    not turn a successful write into an error. The write is still visible in
    the event log, and S5.4.1 means this entry never blocks its own author.
    """
    if blackboard is None:
        return
    if managed and session is not None and not managed_metadata_required(session):
        return
    if managed and managed_versions is None:
        logger.warning("managed post-write metadata unavailable for %s", write_set)
        return
    if not managed and not belongs_to_workspace(blackboard, root):
        return
    try:
        entry = _entry_for(
            entry_id=f"post-{uuid.uuid4().hex[:8]}",
            root=root,
            read_set=read_set,
            write_set=write_set,
            managed_versions=managed_versions if managed else None,
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
    "managed_metadata_required",
    "managed_version_dependencies",
    "record_mutation",
]
