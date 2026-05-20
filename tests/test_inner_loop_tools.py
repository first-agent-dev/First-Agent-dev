from __future__ import annotations

import subprocess
from pathlib import Path

from pytest import MonkeyPatch

from fa.inner_loop import ToolCall
from fa.inner_loop.tools import build_baseline_registry
from fa.inner_loop.tools.run_bash import build_run_bash_tool


def test_read_file_tool_reads_line_window(tmp_path: Path) -> None:
    (tmp_path / "sample.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
    registry = build_baseline_registry(tmp_path)

    result = registry.dispatch(
        ToolCall(
            name="fs.read_file",
            params={"path": "sample.txt", "start_line": 2, "end_line": 2},
        )
    )

    assert result.error is None
    assert result.result["content"] == "two"  # type: ignore[index]


def test_write_file_tool_writes_inside_workspace(tmp_path: Path) -> None:
    registry = build_baseline_registry(tmp_path)

    result = registry.dispatch(
        ToolCall(name="fs.write_file", params={"path": "out.txt", "content": "hello\n"})
    )

    assert result.error is None
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "hello\n"


def test_workspace_path_escape_is_rejected(tmp_path: Path) -> None:
    registry = build_baseline_registry(tmp_path)

    result = registry.dispatch(
        ToolCall(name="fs.write_file", params={"path": "../escape.txt", "content": "no"})
    )

    assert result.error is not None
    assert result.error.code == "write_failed"


def test_run_bash_tool_runs_in_workspace(tmp_path: Path) -> None:
    registry = build_baseline_registry(tmp_path)

    result = registry.dispatch(ToolCall(name="fs.run_bash", params={"command": "pwd"}))

    assert result.error is None
    assert result.result["stdout"].strip() == str(tmp_path)  # type: ignore[index]


def test_run_bash_tool_returns_timeout_error(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    def raise_timeout(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        del args, kwargs
        raise subprocess.TimeoutExpired(cmd="sleep", timeout=30)

    monkeypatch.setattr(subprocess, "run", raise_timeout)
    tool = build_run_bash_tool(tmp_path)

    result = tool.handler({"command": "sleep 31"})

    assert result.error is not None
    assert result.error.code == "command_timeout"
    assert result.error.retryable is True


def test_run_bash_tool_preserves_failure_diagnostics(tmp_path: Path) -> None:
    registry = build_baseline_registry(tmp_path)

    result = registry.dispatch(
        ToolCall(
            name="fs.run_bash",
            params={"command": "printf 'visible stdout'; printf 'visible stderr' >&2; exit 7"},
        )
    )

    assert result.error is not None
    assert result.error.code == "command_failed"
    assert "bash exited 7" in result.error.message
    assert "visible stderr" in result.error.message
    assert "visible stdout" in result.error.message
