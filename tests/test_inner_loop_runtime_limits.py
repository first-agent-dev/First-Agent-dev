"""``RuntimeLimits`` config loader tests (T-4 mini + ADR-7 \u00a7Amendment 2026-05-20).

Covers F-6 + F-7 from the PR #24 must-fix block:

- F-6: loop driver reads ``max_iterations`` from config, not a code
  constant.
- F-7: bash tool reads ``bash_timeout_seconds`` from config, not a code
  constant.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

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
from fa.inner_loop.runtime_limits import DEFAULT_COST_BUDGET_USD
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


def test_load_runtime_limits_accepts_zero_for_suppression_keys() -> None:
    """R-4 suppression-seconds keys document ``0`` as «observe-only»;
    the loader must accept ``0`` for these three keys without
    warning, while still rejecting negative values and rejecting
    ``0`` for every other key.

    Regression test for Devin-Review BUG flagged on PR #26: prior to
    the fix, ``rate_limit_suppression_seconds: 0`` got a spurious
    «value must be positive» warning and was silently dropped, so
    the user could not opt the rate-limit / lockfile blockers into
    observe-only mode via config (the auth-expired default 0 worked
    only because the field-default is 0, but still emitted a
    spurious warning).
    """

    text = """\
runtime_limits:
  rate_limit_suppression_seconds: 0
  lockfile_suppression_seconds: 0
  auth_expired_suppression_seconds: 0
"""
    result = load_runtime_limits(text)
    assert result.warnings == (), result.warnings
    assert result.limits.rate_limit_suppression_seconds == 0
    assert result.limits.lockfile_suppression_seconds == 0
    assert result.limits.auth_expired_suppression_seconds == 0


def test_load_runtime_limits_still_rejects_zero_for_positive_only_keys() -> None:
    """``0`` is only accepted for the three suppression-seconds keys;
    every other key still requires a strictly positive value.

    Pinning this prevents accidental relaxation: if a future edit
    moves the wrong key into ``_ZERO_ALLOWED_KEYS`` (e.g.
    ``max_iterations``), the loop driver would silently run zero
    iterations.
    """

    text = """\
runtime_limits:
  max_iterations: 0
  bash_timeout_seconds: 0
  loop_guard_window: 0
  qa_max_iterations: 0
"""
    result = load_runtime_limits(text)
    assert result.limits.max_iterations == DEFAULT_MAX_ITERATIONS
    assert result.limits.bash_timeout_seconds == DEFAULT_BASH_TIMEOUT_SECONDS
    # Four warnings, all positive-only complaints (not zero-allowed).
    assert {w.key for w in result.warnings} == {
        "max_iterations",
        "bash_timeout_seconds",
        "loop_guard_window",
        "qa_max_iterations",
    }
    for w in result.warnings:
        assert "must be positive" in w.detail


def test_load_runtime_limits_rejects_negative_suppression_seconds() -> None:
    """Negative values are still rejected for the suppression-seconds
    keys (the loosened bound is ``< 0``, not ``< -1``).
    """

    text = """\
runtime_limits:
  rate_limit_suppression_seconds: -1
"""
    result = load_runtime_limits(text)
    assert result.limits.rate_limit_suppression_seconds == 30  # back to default
    assert len(result.warnings) == 1
    assert result.warnings[0].key == "rate_limit_suppression_seconds"
    assert "non-negative" in result.warnings[0].detail


def test_load_runtime_limits_parses_cost_budget_usd_float() -> None:
    """R-45 ``cost_budget_usd`` is the only ``_FLOAT_KEYS`` member so
    the float-parse branch in :func:`load_runtime_limits` is exercised
    only by this key. Pin both the integer-valued YAML shape
    (``cost_budget_usd: 5``) and the fractional shape
    (``cost_budget_usd: 0.5``) so a future float-key addition cannot
    silently regress one of the two parse paths.
    """

    int_text = """\
runtime_limits:
  cost_budget_usd: 5
"""
    int_result = load_runtime_limits(int_text)
    assert int_result.warnings == (), int_result.warnings
    assert int_result.limits.cost_budget_usd == 5.0
    assert isinstance(int_result.limits.cost_budget_usd, float)

    fractional_text = """\
runtime_limits:
  cost_budget_usd: 0.50
"""
    fractional_result = load_runtime_limits(fractional_text)
    assert fractional_result.warnings == (), fractional_result.warnings
    assert fractional_result.limits.cost_budget_usd == 0.50


def test_load_runtime_limits_accepts_zero_for_cost_budget_usd() -> None:
    """R-45 documents ``cost_budget_usd: 0`` as «observe-only» — the
    guardian still accumulates :class:`CostRollup` and emits
    ``cost_observation`` rows but never denies a call. This is the
    same shape as the three ``*_suppression_seconds`` knobs landed
    in PR-3; if a future edit drops ``cost_budget_usd`` from
    :data:`_ZERO_ALLOWED_KEYS` the observe-only mode silently breaks
    (config-set ``0`` would fall back to the ``None`` default and
    observe-only would be unreachable from config).
    """

    text = """\
runtime_limits:
  cost_budget_usd: 0
"""
    result = load_runtime_limits(text)
    assert result.warnings == (), result.warnings
    assert result.limits.cost_budget_usd == 0.0


def test_load_runtime_limits_rejects_invalid_cost_budget_usd() -> None:
    """Non-numeric and negative ``cost_budget_usd`` values must both
    surface as warnings and fall back to the anchored default
    (``None`` = unbounded). Pinning both branches so an unbounded-by-
    accident regression (e.g. swapping ``float()`` for a permissive
    parser) is caught at the parse layer rather than at runtime when
    the guardian silently never denies a call.
    """

    text = """\
runtime_limits:
  cost_budget_usd: free
"""
    bad_value = load_runtime_limits(text)
    # Two separate asserts — ``x == DEFAULT is None`` chains into
    # ``(x == DEFAULT) and (DEFAULT is None)`` which works today but
    # is a CodeQL-flagged ambiguous comparison (py/test-equals-none).
    # Pinning both DEFAULT identity and the fallback value explicitly.
    assert DEFAULT_COST_BUDGET_USD is None
    assert bad_value.limits.cost_budget_usd is None
    assert len(bad_value.warnings) == 1
    assert bad_value.warnings[0].key == "cost_budget_usd"
    assert "non-numeric" in bad_value.warnings[0].detail

    text = """\
runtime_limits:
  cost_budget_usd: -1.0
"""
    negative = load_runtime_limits(text)
    assert negative.limits.cost_budget_usd is None
    assert len(negative.warnings) == 1
    assert negative.warnings[0].key == "cost_budget_usd"
    assert "non-negative" in negative.warnings[0].detail


def test_load_runtime_limits_rejects_nan_and_inf_cost_budget_usd() -> None:
    """``float("nan")`` and ``float("inf")`` parse without raising —
    without an explicit guard the loader would accept ``cost_budget_usd:
    nan`` and silently disable the guardian (``NaN`` comparisons are
    always ``False`` so the gate stops denying) or accept ``inf`` and
    always allow. Reject both at the parse layer rather than relying
    on :class:`CostGuardian.__init__` to catch it later.

    Regression guard for Devin-Review BUG #27 run 3 sibling-NaN
    finding on the float parser.
    """

    for raw in ("nan", "NaN", "inf", "-inf", "Infinity"):
        text = f"""\
runtime_limits:
  cost_budget_usd: {raw}
"""
        result = load_runtime_limits(text)
        assert result.limits.cost_budget_usd is None
        assert len(result.warnings) == 1
        assert result.warnings[0].key == "cost_budget_usd"
        assert "finite" in result.warnings[0].detail


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


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
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
