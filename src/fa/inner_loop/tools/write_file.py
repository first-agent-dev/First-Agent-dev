from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools.base import require_string, resolve_workspace_path
from fa.inner_loop.tools.mutation_guard import check_mutation_allowed, record_mutation

logger = logging.getLogger(__name__)


def build_write_file_tool(workspace_root: Path) -> ToolSpec:
    root = workspace_root.resolve()

    def handler(params: Mapping[str, object]) -> ToolResult:
        data = dict(params)
        try:
            path = resolve_workspace_path(root, require_string(data, "path"))
            content = require_string(data, "content")
        except (OSError, PermissionError, ValueError) as exc:
            return ToolResult.fail("write_failed", str(exc), retryable=True)

        try:
            rel_path = str(path.relative_to(root))
        except ValueError:
            rel_path = str(path)

        session: Any = None
        blackboard: Any = None
        transaction: Any = None
        try:
            from fa.inner_loop.context import get_current_session

            session = get_current_session()
            if session is not None:
                blackboard = session.blackboard if session is not None else None
                transaction = session.transaction if session is not None else None
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            logger.warning("get_current_session failed in write_file: %s", exc)

        read_set: list[str] = []
        write_set: list[str] = [rel_path]
        try:
            if transaction is not None:
                read_set = list(transaction.read_set)
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            logger.warning("transaction.read_set failed: %s", exc)

        denial = check_mutation_allowed(blackboard, read_set=read_set, write_set=write_set, root=root)
        if denial is not None:
            return denial

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except (OSError, PermissionError, ValueError) as exc:
            return ToolResult.fail("write_failed", str(exc), retryable=True)

        try:
            if transaction is not None:
                transaction.add_write(rel_path)
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            logger.warning("transaction.add_write failed: %s", exc)

        record_mutation(
            blackboard,
            read_set=read_set,
            write_set=write_set,
            root=root,
            payload_extra={"bytes": len(content.encode())},
        )

        return ToolResult.ok(
            f"wrote {path.relative_to(root)}",
            result={"path": str(path), "bytes": len(content.encode("utf-8"))},
        )

    return ToolSpec(
        name="fs_write_file",
        description=(
            "Write UTF-8 file inside workspace. Declares read_set/write_set "
            "for blackboard conflict detection (Phase 0.5), fails with "
            "conflict_detected if concurrent write without coordination."
        ),
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
