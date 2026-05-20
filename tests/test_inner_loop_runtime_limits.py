"""``RuntimeLimits`` config loader tests (T-4 mini + ADR-7 \u00a7Amendment 2026-05-20).

Covers F-6 + F-7 from the PR #24 must-fix block:

- F-6: loop driver reads ``max_iterations`` from config, not a code
  constant.
- F-7: bash tool reads ``bash_timeout_seconds`` from config, not a code
  constant.
"""

from __future__ import annotations

from pathlib import Path

from fa.inner_loop import (
    DEFAULT_BASH_TIMEOUT_SECONDS,
    DEFAULT_MAX_ITERATIONS,
    EventLog,
    RuntimeLimits,
    SessionState,
    ToolCall,
    load_runtime_limits,
    load_runtime_limits_from_path,
    run_session,
)
from fa.inner_loop.hooks import HookRegistry, SandboxHook
from fa.inner_loop.tools import build_baseline_registry


def test_anchored_defaults_match_amendment() -> None:
    defaults = RuntimeLimits.anchored_defaults()
    assert defaults.max_iterations == DEFAULT_MAX_ITERATIONS == 6
    assert defaults.bash_timeout_seconds == DEFAULT_BASH_TIMEOUT_SECONDS == 30


def test_load_runtime_limits_parses_block() -> None:
    text = """\
capabilities:
  ENABLE_DYNAMIC_TOOLS: false

runtime_limits:
  max_iterations: 12  # raised per session hot.md note
  bash_timeout_seconds: 90
"""
    result = load_runtime_limits(text)
    assert result.limits.max_iterations == 12
    assert result.limits.bash_timeout_seconds == 90
    assert result.warnings == ()


def test_load_runtime_limits_warns_on_unknown_key_and_keeps_defaults() -> None:
    text = """\
runtime_limits:
  max_iterations: 8
  what_is_this: 99
  bash_timeout_seconds: not-an-int
"""
    result = load_runtime_limits(text)
    assert result.limits.max_iterations == 8
    # Bad value falls back to the anchored default; warning is surfaced.
    assert result.limits.bash_timeout_seconds == DEFAULT_BASH_TIMEOUT_SECONDS
    detail_by_key = {w.key: w.detail for w in result.warnings}
    assert detail_by_key.get("what_is_this") == "unknown key"
    assert "non-integer" in detail_by_key.get("bash_timeout_seconds", "")


def test_load_runtime_limits_rejects_non_positive_values() -> None:
    text = """\
runtime_limits:
  max_iterations: 0
  bash_timeout_seconds: -5
"""
    result = load_runtime_limits(text)
    assert result.limits.max_iterations == DEFAULT_MAX_ITERATIONS
    assert result.limits.bash_timeout_seconds == DEFAULT_BASH_TIMEOUT_SECONDS
    assert {w.key for w in result.warnings} == {"max_iterations", "bash_timeout_seconds"}


def test_load_runtime_limits_from_missing_path_returns_anchors(tmp_path: Path) -> None:
    result = load_runtime_limits_from_path(tmp_path / "no-such-file.yaml")
    assert result.limits == RuntimeLimits.anchored_defaults()
    assert result.warnings == ()


def test_load_runtime_limits_parses_blocker_suppression_keys() -> None:
    """R-4 suppression-seconds keys must be both validated AND wired
    into ``RuntimeLimits`` — otherwise the smoke CLI silently uses
    defaults regardless of the user's ``~/.fa/config.yaml`` and the
    blocker config is undocumented-but-unconfigurable.
    """

    text = """\
runtime_limits:
  rate_limit_suppression_seconds: 45
  lockfile_suppression_seconds: 10
  auth_expired_suppression_seconds: 7
"""
    result = load_runtime_limits(text)
    assert result.warnings == (), result.warnings
    assert result.limits.rate_limit_suppression_seconds == 45
    assert result.limits.lockfile_suppression_seconds == 10
    assert result.limits.auth_expired_suppression_seconds == 7


def test_load_runtime_limits_parses_qa_constants() -> None:
    """R-34 QA constants are validated AND wired so a future QA
    orchestrator can read them via the same ``RuntimeLimits`` shape.

    Prior to this fix the loader accepted the keys (no «unknown key»
    warning) but silently discarded the values — the ``RuntimeLimits``
    instance always used the field-default.
    """

    text = """\
runtime_limits:
  qa_max_iterations: 100
  qa_max_consecutive_errors: 5
  qa_recurring_issue_threshold: 4
"""
    result = load_runtime_limits(text)
    assert result.warnings == (), result.warnings
    assert result.limits.qa_max_iterations == 100
    assert result.limits.qa_max_consecutive_errors == 5
    assert result.limits.qa_recurring_issue_threshold == 4


def test_max_iterations_truncates_run_session(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b\n", encoding="utf-8")
    (tmp_path / "c.txt").write_text("c\n", encoding="utf-8")
    registry = build_baseline_registry(tmp_path)
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    state = SessionState(
        workspace_root=tmp_path, run_id="t-cap", log=EventLog(tmp_path / "ev.jsonl")
    )

    limits = RuntimeLimits(max_iterations=2, bash_timeout_seconds=10)
    calls = tuple(
        ToolCall(name="fs.read_file", params={"path": p}, call_id=f"tc-{p}")
        for p in ("a.txt", "b.txt", "c.txt")
    )
    results = run_session(calls, registry=registry, hooks=hooks, state=state, limits=limits)

    # Only the first two calls executed; the third was truncated by the cap.
    assert len(results) == 2
    assert all(result.error is None for result in results)


def test_bash_timeout_is_plumbed_into_tool(tmp_path: Path) -> None:
    registry = build_baseline_registry(tmp_path, bash_timeout_seconds=1)
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    state = SessionState(
        workspace_root=tmp_path, run_id="t-timeout", log=EventLog(tmp_path / "ev.jsonl")
    )

    results = run_session(
        (ToolCall(name="fs.run_bash", params={"command": "sleep 3"}, call_id="tc-1"),),
        registry=registry,
        hooks=hooks,
        state=state,
        limits=RuntimeLimits(max_iterations=1, bash_timeout_seconds=1),
    )

    assert results[0].error is not None
    assert results[0].error.code == "command_timeout"
    assert "1s" in results[0].summary
