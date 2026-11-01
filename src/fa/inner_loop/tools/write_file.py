from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchError, PlannerDispatchKind
from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools.base import require_string, resolve_workspace_path
from fa.inner_loop.tools.mutation_guard import BLACKBOARD_UNAVAILABLE, check_mutation_allowed, record_mutation
from fa.inner_loop.tools.workspace_port import WorkspacePort, WorkspacePortError, port_relative
from fa.inner_loop.workflow_artifacts import _private_artifact_directory, _replace_private_bytes

logger = logging.getLogger(__name__)


def _write_with_guard(
    root: Path,
    path: Path,
    rel_path: str,
    content: str,
    writer: Callable[[], None],
    *,
    retryable: bool = True,
    managed: bool = False,
) -> ToolResult:
    session: Any = None
    blackboard: Any = None
    transaction: Any = None
    try:
        from fa.inner_loop.context import get_current_session

        session = get_current_session()
        if session is not None:
            blackboard = session.blackboard if session is not None else None
            transaction = session.transaction if session is not None else None
    except Exception as exc:  # noqa: BLE001 # legacy host mode remains graceful; managed fails closed
        logger.warning("get_current_session failed in write_file: %s", exc)
        if managed:
            return ToolResult.fail(BLACKBOARD_UNAVAILABLE, "managed session context unavailable", retryable=False)

    read_set: list[str] = []
    write_set: list[str] = [rel_path]
    try:
        if transaction is not None:
            read_set = list(transaction.read_set)
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        logger.warning("transaction.read_set failed: %s", exc)

    denial = check_mutation_allowed(
        blackboard, read_set=read_set, write_set=write_set, root=root, managed=managed, session=session
    )
    if denial is not None:
        return denial

    try:
        writer()
    except (OSError, PermissionError, ValueError) as exc:
        return ToolResult.fail("write_failed", str(exc), retryable=retryable)

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
        managed=managed,
    )

    return ToolResult.ok(
        f"wrote {path.relative_to(root)}",
        result={"path": str(path), "bytes": len(content.encode("utf-8"))},
    )


def build_write_file_tool(workspace_root: Path, *, workspace_io: WorkspacePort | None = None) -> ToolSpec:
    """Write inside the workspace.

    With ``workspace_io`` the bytes go to the admitted view through the port and
    the host path is only a display value; without it the historical host-path
    writer is used unchanged (the pre-cutover composition).
    """
    root = workspace_root.resolve()

    def handler(params: Mapping[str, object]) -> ToolResult:
        data = dict(params)
        try:
            raw_path = require_string(data, "path")
            content = require_string(data, "content")
            if workspace_io is None:
                path = resolve_workspace_path(root, raw_path)
                rel_path = str(path.relative_to(root))
            else:
                rel_path = port_relative(raw_path)
                path = root / rel_path
        except WorkspacePortError as exc:
            return ToolResult.fail("invalid_params", f"path rejected: {exc.code}", retryable=True)
        except (OSError, PermissionError, ValueError) as exc:
            return ToolResult.fail("write_failed", str(exc), retryable=True)

        if workspace_io is None:

            def writer() -> None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

        else:

            def writer() -> None:
                workspace_io.write_file(rel_path, content)

        try:
            return _write_with_guard(root, path, rel_path, content, writer, managed=workspace_io is not None)
        except WorkspacePortError as exc:
            return _port_failure(exc)

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


def _port_failure(exc: WorkspacePortError) -> ToolResult:
    """Map a substrate refusal onto the tool vocabulary; never a silent success."""
    codes = {
        "stale": ("write_failed", False),
        "denied": ("permission_denied", False),
        "invalid_request": ("invalid_params", True),
        "input_policy": ("write_failed", False),
    }
    if exc.code not in codes:
        return ToolResult.fail(
            "write_failed", "workspace write outcome is unknown; do not retry without recovery", retryable=False
        )
    code, retryable = codes[exc.code]
    return ToolResult.fail(code, f"workspace refused the write: {exc.code}", retryable=retryable)


def build_scoped_write_file_tool(workspace_root: Path, dispatch: PlannerDispatch) -> ToolSpec:
    """Exact candidate capability; do not forward a checked path to the generic writer."""
    if not isinstance(dispatch, PlannerDispatch) or dispatch.kind == PlannerDispatchKind.ORDINARY_PLANNING:
        raise PlannerDispatchError
    target = dispatch.candidate_target
    if target is None:
        raise PlannerDispatchError
    root = workspace_root.absolute()
    path = root / target

    def handler(params: Mapping[str, object]) -> ToolResult:
        if params.get("path") != target:
            return ToolResult.fail("scope_denied", "planner candidate target does not match controller scope")
        try:
            content = require_string(params, "content")
            raw = content.encode("utf-8")
        except (ValueError, UnicodeError):
            return ToolResult.fail("write_failed", "candidate content must be valid UTF-8 text")

        def writer() -> None:
            with _private_artifact_directory(path.parent) as directory_fd:
                _replace_private_bytes(directory_fd, path.name, raw)

        return _write_with_guard(root, path, target, content, writer, retryable=False)

    return ToolSpec(
        name="fs_write_file",
        description=f"Write UTF-8 only to controller candidate {target}. No other path is permitted.",
        input_schema={
            "type": "object",
            "required": ["path", "content"],
            "additionalProperties": False,
            "properties": {"path": {"type": "string", "enum": [target]}, "content": {"type": "string"}},
        },
        permission="workspace",
        handler=handler,
        tags=("fs", "write"),
    )


__all__ = ["build_scoped_write_file_tool", "build_write_file_tool"]
