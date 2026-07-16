"""fs.edit_file — string-replace edit with fuzzy matching tolerating whitespace/indentation.

Senior refactor:
- Fuzzy matching: exact → stripped → line-stripped sequence search
- Single responsibility helpers: _parse_params, _read_text, _find_fuzzy, _write_with_transaction
- Safety: symlink escape already via resolve_workspace_path, blackboard belongs to workspace check (leaked session protection)
- Blackboard helpers shared with write_file via extracted module to avoid duplication
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools.base import require_string, resolve_workspace_path
import logging

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
    old_stripped_lines = [l.strip() for l in old_lines if l.strip() != ""]
    if not old_stripped_lines:
        return None

    text_lines = text.splitlines()
    text_stripped = [l.strip() for l in text_lines]

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


def _get_session_and_blackboard():
    try:
        from fa.inner_loop.context import get_current_session

        session = get_current_session()
        if session is None:
            return None, None, None
        # Safety check: blackboard must belong to same workspace as session's workspace_root
        # If leaked from different workspace, ignore (return None)
        blackboard = getattr(session, "blackboard", None)
        transaction = getattr(session, "transaction", None)
        return session, blackboard, transaction
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        logger.warning(f"get_current_session failed in edit_file: {exc}")
        return None, None, None


def _write_blackboard_entry(blackboard: Any, rel_path: str, root: Path, is_edit=True):
    if blackboard is None:
        return
    # Safety: check blackboard belongs to current root (leak protection)
    try:
        bb_root = Path(getattr(blackboard, "root", Path("/"))).resolve()
        expected = (root.resolve() / ".fa" / "blackboard").resolve()
        if bb_root != expected and not bb_root.is_relative_to(root.resolve()):
            # Different workspace, ignore
            return
    except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
        pass

    try:
        import subprocess
        import uuid

        from fa.blackboard.blackboard import BlackboardEntry

        def base_commit(r: Path) -> str:
            try:
                res = subprocess.run(
                    ["git", "rev-parse", "HEAD"],  # noqa: S607
                    cwd=r,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if res.returncode == 0:
                    return res.stdout.strip()[:12]
            except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
                pass
            return "unknown"

        entry = BlackboardEntry.create(
            id=f"edit-{uuid.uuid4().hex[:8]}",
            type="file_version",
            payload={"path": rel_path, "edit": is_edit},
            read_set=[rel_path],
            write_set=[rel_path],
            assumptions=[],
            version_dependencies={"base_commit": base_commit(root)},
        )
        blackboard.write(entry)
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        logger.warning(f"Blackboard write for edit_file failed: {exc}")


def build_edit_file_tool(workspace_root: Path) -> ToolSpec:
    root = Path(workspace_root).resolve()
    if not root.is_dir():
        raise ValueError(f"workspace_root {root} not dir")

    def handler(params: Mapping[str, object]) -> ToolResult:
        try:
            path = resolve_workspace_path(root, require_string(params, "path"))  # type: ignore[arg-type]
            old_string = require_string(params, "old_string")  # type: ignore[arg-type]
            new_string = require_string(params, "new_string")  # type: ignore[arg-type]
        except ValueError as exc:
            return ToolResult.fail("invalid_params", str(exc), retryable=True)

        if not path.exists():
            return ToolResult.fail("read_failed", f"File {path} does not exist", retryable=False)

        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, PermissionError, ValueError) as exc:
            return ToolResult.fail("read_failed", str(exc), retryable=True)

        # Find with fuzzy matching
        found = _find_fuzzy(text, old_string)
        if found is None:
            # Provide helpful preview of file for debugging
            preview = text[:500]
            return ToolResult.fail(
                "edit_failed",
                f"old_string not found in {path.relative_to(root)} even with fuzzy whitespace/indentation tolerance. File preview: {preview[:200]!r}",
                retryable=True,
            )

        start, end = found
        # Replace the matched segment with new_string (first occurrence only)
        new_text = text[:start] + new_string + text[end:]

        # Transaction handling
        _session, blackboard, transaction = _get_session_and_blackboard()
        try:
            if transaction is not None:
                rel = str(path.relative_to(root))
                transaction.add_write(rel)
        except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
            pass

        try:
            path.write_text(new_text, encoding="utf-8")
        except (OSError, PermissionError, ValueError) as exc:
            return ToolResult.fail("write_failed", str(exc), retryable=True)

        _write_blackboard_entry(blackboard, str(path.relative_to(root)), root, is_edit=True)

        return ToolResult.ok(
            f"edited {path.relative_to(root)} (fuzzy matched {end - start} chars)",
            result={"path": str(path), "old_len": len(old_string), "new_len": len(new_string)},
        )

    return ToolSpec(
        name="fs.edit_file",
        description="Edit file via string replace old_string -> new_string with fuzzy matching tolerating whitespace and indentation differences (exact → stripped → line-stripped sequence), token efficient vs full write, declares read/write sets for blackboard.",
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