from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools.base import optional_int, require_string, resolve_workspace_path


def build_read_file_tool(workspace_root: Path) -> ToolSpec:
    # ``resolve_workspace_path`` returns a fully resolved path; resolve the
    # closure root once here so ``relative_to`` below also sees a resolved
    # base. Matches ``build_run_bash_tool`` (which does the same on line 26).
    root = workspace_root.resolve()

    def handler(params: Mapping[str, object]) -> ToolResult:
        data = dict(params)
        try:
            path = resolve_workspace_path(root, require_string(data, "path"))
            start_line = optional_int(data, "start_line")
            end_line = optional_int(data, "end_line")
            text = path.read_text(encoding="utf-8")
        except (OSError, PermissionError, ValueError) as exc:
            return ToolResult.fail("read_failed", str(exc), retryable=True)

        lines = text.splitlines()
        if start_line is not None or end_line is not None:
            start = 1 if start_line is None else start_line
            end = len(lines) if end_line is None else end_line
            if start < 1 or end < start:
                return ToolResult.fail("invalid_params", "invalid line window", retryable=True)
            selected = lines[start - 1 : end]
            content = "\n".join(selected)
        else:
            content = text

        return ToolResult.ok(
            f"read {path.relative_to(root)}",
            result={
                "path": str(path),
                "content": content,
                "line_count": len(lines),
            },
        )

    return ToolSpec(
        name="fs.read_file",
        description="Read a UTF-8 file inside the workspace.",
        input_schema={
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": "integer"},
                "end_line": {"type": "integer"},
            },
        },
        permission="read",
        handler=handler,
        tags=("fs", "read"),
    )


__all__ = ["build_read_file_tool"]
