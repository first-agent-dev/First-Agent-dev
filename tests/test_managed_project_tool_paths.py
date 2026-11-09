"""Shipped fs_search/fs_reach managed handlers must cross the typed port."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fa.inner_loop.tools.fs_reach import build_fs_reach_tool
from fa.inner_loop.tools.fs_search import build_fs_search_tool


class _Executor:
    def __init__(self, envelope: dict[str, Any]) -> None:
        self.envelope = envelope
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(self, tool: str, params: dict[str, Any], *, timeout: int = 25) -> str:
        self.calls.append((tool, params))
        return json.dumps(self.envelope, separators=(",", ":"))


def _envelope(result: dict[str, Any]) -> dict[str, Any]:
    return {"summary": "managed result", "result": result, "error": None, "artifacts": []}


def test_managed_search_builder_uses_executor_and_checks_controller_paths(tmp_path: Path) -> None:
    root = tmp_path / "controller-root"
    root.mkdir()
    executor = _Executor(_envelope({"query": "", "files": [{"path": "src/a.py"}]}))
    tool = build_fs_search_tool(root / ".fa" / "fts.db", root, workspace_io=object(), project_tool_executor=executor)

    result = tool.handler({"output_mode": "files"})

    assert result.error is None and result.result == executor.envelope["result"]
    assert executor.calls == [("fs_search", {"output_mode": "files"})]
    assert not (root / ".fa" / "fts.db").exists()

    bad = _Executor(_envelope({"query": "", "files": [{"path": "../outside"}]}))
    bad_tool = build_fs_search_tool(root / ".fa" / "fts.db", root, workspace_io=object(), project_tool_executor=bad)
    refused = bad_tool.handler({"output_mode": "files"})
    assert refused.error is not None and refused.error.code == "project_tool_failed"
    assert refused.result is None


def test_managed_role_builders_bind_the_typed_supplier_and_serial_tag(tmp_path: Path) -> None:
    from fa.inner_loop.profiles import _build_tool_builders

    root = tmp_path / "controller-root"
    root.mkdir()
    executor = _Executor(_envelope({"query": "", "files": []}))

    builders = _build_tool_builders(
        root,
        workspace_io=object(),  # type: ignore[arg-type] - builders only require a non-null managed binding
        project_tool_executor=executor,
    )
    search = builders["fs_search"]()
    reach = builders["fs_reach"]()

    assert "managed-view-serial" in search.tags
    assert "managed-view-serial" in reach.tags
    search.handler({"output_mode": "files"})
    reach.handler({"symbol": "f"})
    assert executor.calls == [
        ("fs_search", {"output_mode": "files"}),
        ("fs_reach", {"symbol": "f"}),
    ]


def test_managed_reach_builder_uses_executor_and_keeps_legacy_default_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "controller-root"
    root.mkdir()
    executor = _Executor(_envelope({"resolved": "f", "callers": [], "callees": [], "unresolved": 0}))
    tool = build_fs_reach_tool(root, workspace_io=object(), project_tool_executor=executor)

    result = tool.handler({"symbol": "f"})

    assert result.error is None and result.result == executor.envelope["result"]
    assert executor.calls == [("fs_reach", {"symbol": "f"})]
    assert not (root / ".fa" / "structural.db").exists()

    legacy_managed = build_fs_reach_tool(root, workspace_io=object())
    refused = legacy_managed.handler({"symbol": "f"})
    assert refused.error is not None and refused.error.code == "reach_failed"
