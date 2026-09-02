from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
from pytest import MonkeyPatch

from fa.inner_loop import ToolCall
from fa.inner_loop.tools import build_baseline_registry
from fa.inner_loop.tools.run_bash import build_run_bash_tool
from tests._capabilities import requires_posix_shell, requires_pty_backend


def test_read_file_tool_reads_line_window(tmp_path: Path) -> None:
    (tmp_path / "sample.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
    registry = build_baseline_registry(tmp_path)

    result = registry.dispatch(
        ToolCall(
            name="fs_read_file",
            params={"path": "sample.txt", "start_line": 2, "end_line": 2},
        )
    )

    assert result.error is None
    assert result.result is not None
    assert result.result["content"] == "two"


def test_write_file_tool_writes_inside_workspace(tmp_path: Path) -> None:
    registry = build_baseline_registry(tmp_path)

    result = registry.dispatch(ToolCall(name="fs_write_file", params={"path": "out.txt", "content": "hello\n"}))

    assert result.error is None
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "hello\n"


def test_workspace_path_escape_is_rejected(tmp_path: Path) -> None:
    registry = build_baseline_registry(tmp_path)

    result = registry.dispatch(ToolCall(name="fs_write_file", params={"path": "../escape.txt", "content": "no"}))

    assert result.error is not None
    assert result.error.code == "write_failed"


@requires_posix_shell
def test_run_bash_tool_runs_in_workspace(tmp_path: Path) -> None:
    registry = build_baseline_registry(tmp_path)

    result = registry.dispatch(ToolCall(name="fs_run_bash", params={"command": "pwd"}))

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


@requires_pty_backend
def test_run_bash_large_output_offloads_artifact_without_internal_error(tmp_path: Path) -> None:
    from fa.inner_loop.context import reset_current_session, set_current_session
    from fa.inner_loop.state import SessionState

    state = SessionState(workspace_root=tmp_path, run_id="test-bash-large")
    token = set_current_session(state)
    try:
        tool = build_run_bash_tool(tmp_path)
        # S12.7 (CT4): offload threshold is the 30k retention target (was 8k)
        result = tool.handler({"command": "python3 - <<'PY'\nprint('A' * 30001)\nPY"})
    finally:
        reset_current_session(token)

    assert result.error is None
    assert result.result is not None
    assert result.result["artifact_id"] is not None
    assert "truncated" in result.result


def test_read_file_tolerates_unresolved_workspace_root(tmp_path: Path) -> None:
    """Agent-Review BUG-0002: a workspace_root containing ``..`` MUST NOT
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

    result = registry.dispatch(ToolCall(name="fs_read_file", params={"path": "sample.txt"}))

    assert result.error is None
    assert result.result is not None
    assert result.result["content"] == "alpha\nbeta\n"
    assert result.summary.startswith("read sample.txt")


def test_write_file_tolerates_unresolved_workspace_root(tmp_path: Path) -> None:
    """Agent-Review BUG-0002, write-side mirror of the read-side test
    above. ``build_write_file_tool`` now resolves ``workspace_root``
    once at build time so the summary's ``relative_to`` is safe."""

    (tmp_path / "real").mkdir()
    unresolved_root = tmp_path / "real" / ".." / "real"
    registry = build_baseline_registry(unresolved_root)

    result = registry.dispatch(
        ToolCall(
            name="fs_write_file",
            params={"path": "out.txt", "content": "ok\n"},
        )
    )

    assert result.error is None
    assert (tmp_path / "real" / "out.txt").read_text(encoding="utf-8") == "ok\n"
    assert result.summary == "wrote out.txt"


@requires_posix_shell
def test_run_bash_tool_preserves_failure_diagnostics(tmp_path: Path) -> None:
    registry = build_baseline_registry(tmp_path)

    result = registry.dispatch(
        ToolCall(
            name="fs_run_bash",
            params={"command": "printf 'visible stdout'; printf 'visible stderr' >&2; exit 7"},
        )
    )

    assert result.error is not None
    assert result.error.code == "command_failed"
    assert "bash exited 7" in result.error.message
    assert "visible stderr" in result.error.message
    assert "visible stdout" in result.error.message


def test_build_planner_registry_has_read_and_bash(tmp_path: Path) -> None:
    """Planner registry v3 reduced: read-only analysis + limited write to research docs, no bash.

    Per ADR-14/15 v3 reduced surface + Q3 decision planner gets limited write_file to
    knowledge/research/** + .fa/** for filesystem-canon plans, not full write.
    Old test expected read+bash, now expects read+glob+grep+instant_grep+limited write, no bash.
    Kept name for backward compat but checks new reduced surface.
    """
    from fa.inner_loop.tools import build_planner_registry

    registry = build_planner_registry(tmp_path)
    names = {spec.name for spec in registry.specs()}
    # Planner should have read-only reconnaissance + limited write for plans
    assert "fs_read_file" in names
    assert "fs_search" in names
    # S14b.1: old search tool names removed.
    for old in ("fs_glob", "fs_grep", "fs_instant_grep"):
        assert old not in names
    # Limited write_file should be present (knowledge/research/** + .fa/**)
    assert "fs_write_file" in names
    # No bash for planner in reduced surface (pair over autonomy, implementer has bash)
    assert "fs_run_bash" not in names

    # Verify limited write denies src/ but allows knowledge/research/
    result_denied = registry.dispatch(ToolCall(name="fs_write_file", params={"path": "src/illegal.py", "content": "x"}))
    assert result_denied.error is not None
    assert result_denied.error.code == "path_denied"

    result_allowed = registry.dispatch(
        ToolCall(name="fs_write_file", params={"path": "knowledge/research/plan.md", "content": "# Plan\n"})
    )
    assert result_allowed.error is None


def test_build_eval_registry_has_read_and_bash(tmp_path: Path) -> None:
    """Eval registry v3 reduced: verifier profile [bash] only + observability, no read/write.

    Per PROFILES verifier = [fs_run_bash] only, 200 tokens. Old test expected read+bash.
    """
    from fa.inner_loop.tools import build_eval_registry

    registry = build_eval_registry(tmp_path)
    names = {spec.name for spec in registry.specs()}
    # Verifier should have bash
    assert "fs_run_bash" in names
    # No read_file, no write_file for verifier (cheap deterministic)
    assert "fs_read_file" not in names
    assert "fs_write_file" not in names
    # Observability tools may be present (chronicle_search, usage) per _register_extra_tools
    # That's okay, but core verifier is bash


def test_fs_search_matches_mode_returns_lines_with_numbers(tmp_path: Path) -> None:
    """S14b.1: fs_search in output_mode='matches' returns line numbers and content."""
    from fa.inner_loop.tools.fs_search import build_fs_search_tool

    # Write a test file
    test_file = tmp_path / "test.py"
    test_file.write_text("line 1\nline 2 matching target\nline 3\n", encoding="utf-8")

    tool = build_fs_search_tool(tmp_path / ".fa" / "fts.db", tmp_path)
    result = tool.handler(
        {
            "query": "matching target",
            "output_mode": "matches",
            "context_lines": 0,
            "limit": 10,
        }
    )

    assert result.error is None, f"unexpected error: {result.error}"
    result_data = cast(dict[str, Any], result.result or {})
    # Must return either via FTS or python-walk fallback
    assert result_data.get("method") in ("fts5_bm25", "fts5_trigram_fallback", "literal_fallback")
    matches = result_data.get("matches", [])
    assert len(matches) >= 1
    # S12.7 §A6: matches are merged regions — line 2 must be a reported hit
    hit = next((m for m in matches if m.get("path") == "test.py" and 2 in m.get("match_lines", [])), None)
    assert hit is not None, f"expected line-2 hit region in test.py; got {matches}"
    assert any("2:" in s and "matching target" in s for s in hit["snippet"])


def test_spawn_subagent_tool_gated_by_flag(tmp_path: Path) -> None:
    from fa.feature_flags import FeatureFlags
    from fa.inner_loop.context import set_current_session
    from fa.inner_loop.state import SessionState
    from fa.inner_loop.tools.spawn_subagent import build_spawn_subagent_tool

    tool = build_spawn_subagent_tool(tmp_path)

    # 1. Disabled by default (flag = False)
    state_disabled = SessionState(
        workspace_root=tmp_path,
        run_id="test-spawn-dis",
        feature_flags=FeatureFlags(subagent_spawning_enabled=False),
    )
    token = set_current_session(state_disabled)
    try:
        res = tool.handler({"task_id": "subtask", "command": "echo 42", "role": "verifier"})
        assert res.error is not None
        assert res.error.code == "disabled"
    finally:
        from fa.inner_loop.context import reset_current_session

        reset_current_session(token)

    # 2. Enabled (flag = True)
    state_enabled = SessionState(
        workspace_root=tmp_path,
        run_id="test-spawn-en",
        feature_flags=FeatureFlags(subagent_spawning_enabled=True),
    )
    token = set_current_session(state_enabled)
    try:
        res = tool.handler({"task_id": "subtask-ok", "command": "echo 42", "role": "researcher"})
        assert res.error is None
        assert "completed successfully" in res.summary
        assert res.result is not None
        assert '"type": "researcher"' in res.result
        assert state_enabled.log is not None
        kinds = [e.kind for e in state_enabled.log.read_all()]
        assert "subagent_spawn_start" in kinds
        assert "subagent_spawn_done" in kinds
    finally:
        from fa.inner_loop.context import reset_current_session

        reset_current_session(token)


def test_spawn_subagent_obeys_sandbox_and_secret_guards(tmp_path: Path) -> None:
    from fa.inner_loop.hooks import (
        HookPayload,
        HookRegistry,
        IntentGuard,
        LifecyclePoint,
        SandboxHook,
        SecretGuard,
    )
    from fa.inner_loop.pr_draft import PrDraftStore
    from fa.inner_loop.registry import ToolCall

    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    hooks.register(SecretGuard(secrets=frozenset({"sekret"})))
    hooks.register(IntentGuard(repo_root=tmp_path, draft_store=PrDraftStore(tmp_path / "draft.md")))

    with pytest.raises(PermissionError):
        hooks.dispatch(
            LifecyclePoint.BEFORE_TOOL_EXEC,
            HookPayload(
                tool_call=ToolCall(
                    name="fs_spawn_subagent",
                    params={"task_id": "x", "command": "sudo rm -rf /", "role": "verifier"},
                    call_id="tc-1",
                )
            ),
        )

    with pytest.raises(PermissionError):
        hooks.dispatch(
            LifecyclePoint.BEFORE_TOOL_EXEC,
            HookPayload(
                tool_call=ToolCall(
                    name="fs_spawn_subagent",
                    params={"task_id": "x", "command": "echo sekret", "role": "verifier"},
                    call_id="tc-2",
                )
            ),
        )

    # Mutating shell-like subagent command should require a trusted draft just like fs_run_bash.
    with pytest.raises(PermissionError):
        hooks.dispatch(
            LifecyclePoint.BEFORE_TOOL_EXEC,
            HookPayload(
                tool_call=ToolCall(
                    name="fs_spawn_subagent",
                    params={"task_id": "x", "command": "touch created.txt", "role": "verifier"},
                    call_id="tc-3",
                )
            ),
        )
