from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools.base import require_string, resolve_workspace_path


def build_write_file_tool(workspace_root: Path) -> ToolSpec:
    def handler(params: Mapping[str, object]) -> ToolResult:
        data = dict(params)
        try:
            path = resolve_workspace_path(workspace_root, require_string(data, "path"))
            content = require_string(data, "content")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except (OSError, PermissionError, ValueError) as exc:
            return ToolResult.fail("write_failed", str(exc), retryable=True)

        return ToolResult.ok(
            f"wrote {path.relative_to(workspace_root)}",
            result={"path": str(path), "bytes": len(content.encode("utf-8"))},
        )

    return ToolSpec(
        name="fs.write_file",
        description="Write a full UTF-8 file inside the workspace.",
        input_schema={
            "type": "object",
            "required": ["path", "content"],
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
        },
        permission="workspace",
        handler=handler,
        tags=("fs", "write"),
    )


__all__ = ["build_write_file_tool"]
