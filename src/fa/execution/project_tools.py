"""Cell-local reuse of project discovery tools; never a supervisor or authority.

The CLI binds fixed cell mounts. Its JSON is untrusted tool data, not evidence
of identity or completion; the controller must still validate its envelope.
"""

from __future__ import annotations

import base64
import binascii
import json
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from fa.execution.protocol import _loads
from fa.execution.types import ExecutionContractError
from fa.inner_loop.registry import ToolCall, ToolRegistry, ToolResult
from fa.inner_loop.tools.fs_reach import build_fs_reach_tool
from fa.inner_loop.tools.fs_search import build_fs_search_tool

_MAX_REQUEST_BYTES = 64 * 1024
# Leaves room under the worker's 64 KiB output tail for the newline and framing.
_MAX_ENVELOPE_BYTES = 60 * 1024
_TOOLS = frozenset({"fs_search", "fs_reach"})


def _refusal() -> ToolResult:
    return ToolResult.fail("project_tool_failed", "cell project tool request failed", retryable=False)


def _dispatch(tool: str, params: dict[str, Any], *, root: Path, scratch: Path) -> ToolResult:
    """Run against caller-supplied cell mounts; CLI never takes paths from input."""
    if tool not in _TOOLS:
        return _refusal()
    try:
        source = root.resolve(strict=True)
        cache = scratch.resolve(strict=True)
        if not source.is_dir() or not cache.is_dir() or cache.is_relative_to(source) or source.is_relative_to(cache):
            return _refusal()
        with ExitStack() as cleanup:
            registry = ToolRegistry()
            if tool == "fs_search":
                registry.register(build_fs_search_tool(Path(":memory:"), source, cleanup=cleanup))
            else:
                registry.register(build_fs_reach_tool(source, in_memory=True, cleanup=cleanup))
            return registry.dispatch(ToolCall(tool, params))
    except Exception:  # noqa: BLE001 - untrusted tool data must not become a traceback or partial success
        return _refusal()


def _envelope(result: ToolResult) -> str:
    """Encode one bounded envelope; artifacts stay with the controller."""
    if result.artifacts:
        result = _refusal()
    error = result.error
    payload: dict[str, Any] = {
        "summary": result.summary,
        "result": result.result,
        "error": None
        if error is None
        else {"code": error.code, "message": error.message, "retryable": error.retryable},
        "artifacts": [],
    }
    try:
        # A PTY may normalize/drop combining characters without reporting
        # truncation. First reject invalid Unicode, then send ASCII-only JSON.
        utf8 = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        if len(utf8) <= _MAX_ENVELOPE_BYTES:
            encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
            if len(encoded) <= _MAX_ENVELOPE_BYTES:
                return encoded
    except (TypeError, ValueError, UnicodeError, RecursionError):
        pass
    return json.dumps(
        {
            "summary": "cell project tool output rejected",
            "result": None,
            "error": {"code": "project_tool_failed", "message": "invalid or oversized cell output", "retryable": False},
            "artifacts": [],
        },
        separators=(",", ":"),
    )


def _parse(encoded: str) -> tuple[str, dict[str, Any]] | None:
    try:
        if len(encoded) > 4 * ((_MAX_REQUEST_BYTES + 2) // 3):
            return None
        data = base64.b64decode(encoded, validate=True)
        if len(data) > _MAX_REQUEST_BYTES:
            return None
        value = _loads(data, max_bytes=_MAX_REQUEST_BYTES)
    except (ValueError, UnicodeError, binascii.Error, RecursionError, ExecutionContractError):
        return None
    if not isinstance(value, dict) or set(value) != {"tool", "params"}:
        return None
    tool, params = value["tool"], value["params"]
    if not isinstance(tool, str) or tool not in _TOOLS or not isinstance(params, dict):
        return None
    return tool, params


def main(args: list[str] | None = None) -> int:
    argv = sys.argv[1:] if args is None else args
    parsed = _parse(argv[0]) if len(argv) == 1 else None
    result = _refusal() if parsed is None else _dispatch(*parsed, root=Path("/workspace"), scratch=Path("/scratch"))
    sys.stdout.write(_envelope(result) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
