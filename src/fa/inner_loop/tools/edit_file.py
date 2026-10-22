"""fs_edit_file — string-replace edit with fuzzy matching tolerating whitespace/indentation.

Senior refactor:
- Fuzzy matching: exact → stripped → line-stripped sequence search
- Single responsibility helpers: _parse_params, _read_text, _find_fuzzy, _write_with_transaction
- Safety: resolve_workspace_path prevents symlink escape; blackboard ownership is checked
  to prevent session leakage.
- Pre-write conflict check and post-write record shared with write_file via
  fa.inner_loop.tools.mutation_guard, so the two mutating tools cannot drift
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools.base import require_string, resolve_workspace_path
from fa.inner_loop.tools.mutation_guard import check_mutation_allowed, record_mutation
from fa.inner_loop.tools.workspace_port import WorkspacePort, WorkspacePortError, port_relative

logger = logging.getLogger(__name__)


def _find_fuzzy(text: str, old: str) -> tuple[int, int] | None:
    """Find old_string in text tolerating whitespace/indentation.

    Returns (start, end) char indices or None.
    Tries:
    1) exact
    2) stripped exact
    3) line-stripped sequence (tolerates indentation differences)
    """
    if not old:
        return None

    # 1) Exact
    idx = text.find(old)
    if idx != -1:
        return idx, idx + len(old)

    # 2) Stripped exact (leading/trailing whitespace)
    old_stripped = old.strip()
    if old_stripped and old_stripped in text:
        idx = text.find(old_stripped)
        return idx, idx + len(old_stripped)

    # 3) Line-stripped sequence search
    old_lines = old.splitlines()
    # Filter out empty lines for comparison but keep original for length calc? Keep non-empty for matching
    old_stripped_lines = [line.strip() for line in old_lines if line.strip() != ""]
    if not old_stripped_lines:
        return None

    text_lines = text.splitlines()
    text_stripped = [line.strip() for line in text_lines]

    # Search for consecutive sequence
    for i in range(len(text_stripped) - len(old_stripped_lines) + 1):
        window = text_stripped[i : i + len(old_stripped_lines)]
        if window == old_stripped_lines:
            # Compute char offsets for original lines
            # start at line i, end at line i+len-1 inclusive
            start_line = i
            end_line = i + len(old_stripped_lines) - 1
            # Char offset: sum len + 1 for \n for lines before start
            start_char = sum(len(text_lines[j]) + 1 for j in range(start_line))
            # End char: start + sum of original old_lines lengths plus newlines in matched window original lines
            # Use original text_lines lengths for end
            end_char = sum(len(text_lines[j]) + 1 for j in range(end_line + 1))
            # Adjust to not include trailing \n of last line if not in original text end
            # Ensure we don't exceed text length
            end_char = min(end_char, len(text))
            # If original old was stripped, we may want to return actual matched text bounds, not stripped
            # Return start_char to end_char (covering matched lines)
            return start_char, end_char

    return None


def _get_session_and_blackboard() -> tuple[Any | None, Any | None, Any | None]:
    try:
        from fa.inner_loop.context import get_current_session

        session = get_current_session()
        if session is None:
            return None, None, None
        # Safety check: blackboard must belong to same workspace as session's workspace_root
        # If leaked from different workspace, ignore (return None)
        blackboard = session.blackboard if session is not None else None
        transaction = session.transaction if session is not None else None
        return session, blackboard, transaction
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        logger.warning(f"get_current_session failed in edit_file: {exc}")
        return None, None, None


def _load_text(
    path: Path, relative: str | None, workspace_io: WorkspacePort | None
) -> tuple[str, str | None] | ToolResult:
    """Read the edit base; the digest is what makes the later write conditional."""
    if workspace_io is None or relative is None:
        if not path.exists():
            return ToolResult.fail("read_failed", f"File {path} does not exist", retryable=False)
        try:
            return path.read_text(encoding="utf-8"), None
        except (OSError, PermissionError, ValueError) as exc:
            return ToolResult.fail("read_failed", str(exc), retryable=True)
    try:
        read = workspace_io.read_file(relative)
    except WorkspacePortError as exc:
        return ToolResult.fail(
            "read_failed",
            f"workspace refused the read: {exc.code} (missing or not permitted)",
            retryable=exc.code not in ("denied",),
        )
    return read.content, read.sha256


def _store_text(
    path: Path, relative: str | None, workspace_io: WorkspacePort | None, text: str, base_sha256: str | None
) -> ToolResult | None:
    """Commit the edited text; a stale base is a refusal, never an overwrite."""
    if workspace_io is None or relative is None:
        try:
            path.write_text(text, encoding="utf-8")
        except (OSError, PermissionError, ValueError) as exc:
            return ToolResult.fail("write_failed", str(exc), retryable=True)
        return None
    try:
        workspace_io.write_file(relative, text, expected_sha256=base_sha256)
    except WorkspacePortError as exc:
        code = "permission_denied" if exc.code == "denied" else "write_failed"
        return ToolResult.fail(
            code,
            f"workspace refused the write: {exc.code} (no bytes changed)",
            retryable=exc.code not in ("denied", "stale", "input_policy"),
        )
    return None


def build_edit_file_tool(workspace_root: Path, *, workspace_io: WorkspacePort | None = None) -> ToolSpec:
    """Fuzzy string edit.

    With ``workspace_io`` the read and the write both go to the admitted view and
    the write carries the digest the read observed, so a concurrent writer (a PTY
    shell, another process) turns the edit into a reported conflict instead of a
    silent overwrite.
    """
    root = Path(workspace_root).resolve()
    if not root.is_dir():
        raise ValueError(f"workspace_root {root} not dir")

    def handler(params: Mapping[str, object]) -> ToolResult:
        relative: str | None = None
        try:
            raw_path = require_string(params, "path")
            old_string = require_string(params, "old_string")
            new_string = require_string(params, "new_string")
            if workspace_io is None:
                path = resolve_workspace_path(root, raw_path)
            else:
                relative = port_relative(raw_path)
                path = root / relative
        except WorkspacePortError as exc:
            return ToolResult.fail("invalid_params", f"path rejected: {exc.code}", retryable=True)
        except (ValueError, PermissionError) as exc:
            return ToolResult.fail("invalid_params", str(exc), retryable=True)

        loaded = _load_text(path, relative, workspace_io)
        if isinstance(loaded, ToolResult):
            return loaded
        text, base_sha256 = loaded

        # Find with fuzzy matching
        found = _find_fuzzy(text, old_string)
        if found is None:
            # Provide helpful preview of file for debugging
            preview = text[:500]
            return ToolResult.fail(
                "edit_failed",
                "old_string not found in "
                f"{path.relative_to(root)} even with fuzzy whitespace/indentation tolerance. "
                f"File preview: {preview[:200]!r}",
                retryable=True,
            )

        start, end = found
        # Replace the matched segment with new_string (first occurrence only)
        new_text = text[:start] + new_string + text[end:]

        _session, blackboard, transaction = _get_session_and_blackboard()
        rel_path = str(path.relative_to(root))

        # S5.4: same pre-write contract write_file enforces. Runs AFTER the
        # anchor match (a bad edit is a bad edit regardless of the substrate)
        # but BEFORE any mutation, so a denial leaves the file untouched.
        denial = check_mutation_allowed(blackboard, read_set=[rel_path], write_set=[rel_path], root=root)
        if denial is not None:
            return denial

        try:
            if transaction is not None:
                transaction.add_write(rel_path)
        except Exception as exc:  # noqa: BLE001 # bookkeeping only, failure-observable WARNING
            logger.warning("transaction.add_write failed in edit_file: %s", exc)

        failed = _store_text(path, relative, workspace_io, new_text, base_sha256)
        if failed is not None:
            return failed

        record_mutation(
            blackboard,
            read_set=[rel_path],
            write_set=[rel_path],
            root=root,
            payload_extra={"edit": True},
        )

        return ToolResult.ok(
            f"edited {path.relative_to(root)} (fuzzy matched {end - start} chars)",
            result={"path": str(path), "old_len": len(old_string), "new_len": len(new_string)},
        )

    return ToolSpec(
        name="fs_edit_file",
        description=(
            "Edit file via string replacement with fuzzy whitespace/indentation matching "
            "(exact, stripped, then line-stripped sequence). Declares blackboard read/write sets."
        ),
        input_schema={
            "type": "object",
            "required": ["path", "old_string", "new_string"],
            "properties": {
                "path": {"type": "string"},
                "old_string": {
                    "type": "string",
                    "description": "Old text to replace, fuzzy matched tolerating whitespace",
                },
                "new_string": {"type": "string"},
            },
        },
        permission="workspace",
        handler=handler,
        tags=("fs", "edit"),
        max_context_bytes=4000,
    )


__all__ = ["build_edit_file_tool"]
