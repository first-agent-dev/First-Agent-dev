from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
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
    assert result.result is not None
    assert result.result["content"] == "two"


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


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_run_bash_tool_runs_in_workspace(tmp_path: Path) -> None:
    registry = build_baseline_registry(tmp_path)

    result = registry.dispatch(ToolCall(name="fs.run_bash", params={"command": "pwd"}))

    assert result.error is None
    assert result.result is not None
    assert result.result["stdout"].strip() == str(tmp_path)


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


def test_read_file_tolerates_unresolved_workspace_root(tmp_path: Path) -> None:
    """Devin-Review BUG-0002: a workspace_root containing ``..`` MUST NOT
    cause ``relative_to`` to raise ``ValueError`` out of the handler.

    Before the fix, ``build_read_file_tool`` captured the *unresolved*
    ``workspace_root`` in its closure and then called
    ``path.relative_to(workspace_root)`` against it, while
    ``resolve_workspace_path`` had already returned a fully resolved
    path -- so when the root had a ``..`` segment the two paths were
    not comparable and ``ValueError`` propagated uncaught.
    """

    (tmp_path / "real").mkdir()
    (tmp_path / "real" / "sample.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    unresolved_root = tmp_path / "real" / ".." / "real"
    registry = build_baseline_registry(unresolved_root)

    result = registry.dispatch(ToolCall(name="fs.read_file", params={"path": "sample.txt"}))

    assert result.error is None
    assert result.result is not None
    assert result.result["content"] == "alpha\nbeta\n"
    assert result.summary.startswith("read sample.txt")


def test_write_file_tolerates_unresolved_workspace_root(tmp_path: Path) -> None:
    """Devin-Review BUG-0002, write-side mirror of the read-side test
    above. ``build_write_file_tool`` now resolves ``workspace_root``
    once at build time so the summary's ``relative_to`` is safe."""

    (tmp_path / "real").mkdir()
    unresolved_root = tmp_path / "real" / ".." / "real"
    registry = build_baseline_registry(unresolved_root)

    result = registry.dispatch(
        ToolCall(
            name="fs.write_file",
            params={"path": "out.txt", "content": "ok\n"},
        )
    )

    assert result.error is None
    assert (tmp_path / "real" / "out.txt").read_text(encoding="utf-8") == "ok\n"
    assert result.summary == "wrote out.txt"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
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


def test_build_planner_registry_has_read_and_bash(tmp_path: Path) -> None:
    """Planner registry: read-only reconnaissance (read_file + run_bash, no write_file)."""
    from fa.inner_loop.tools import build_planner_registry

    registry = build_planner_registry(tmp_path)
    names = {spec.name for spec in registry.specs()}
    assert "fs.read_file" in names
    assert "fs.run_bash" in names
    assert "fs.write_file" not in names


def test_build_eval_registry_has_read_and_bash(tmp_path: Path) -> None:
    """Eval registry: read-only verification (read_file + run_bash, no write_file)."""
    from fa.inner_loop.tools import build_eval_registry

    registry = build_eval_registry(tmp_path)
    names = {spec.name for spec in registry.specs()}
    assert "fs.read_file" in names
    assert "fs.run_bash" in names
    assert "fs.write_file" not in names
