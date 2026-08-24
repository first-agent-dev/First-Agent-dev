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
from fa.inner_loop.runtime_limits import (
    DEFAULT_COST_BUDGET_USD,
    ROLE_ITERATION_DEFAULTS,
    resolve_limits_for_role,
)
from fa.inner_loop.tools import build_baseline_registry
from tests._capabilities import requires_pty_backend


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

    Regression test for Agent-Review BUG flagged on PR #26: prior to
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

    Regression guard for Agent-Review BUG #27 run 3 sibling-NaN
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
    state = SessionState(workspace_root=tmp_path, run_id="t-cap", log=EventLog(tmp_path / "ev.jsonl"))

    limits = RuntimeLimits(max_iterations=2, bash_timeout_seconds=10)
    calls = tuple(
        ToolCall(name="fs_read_file", params={"path": p}, call_id=f"tc-{p}") for p in ("a.txt", "b.txt", "c.txt")
    )
    results = run_session(calls, registry=registry, hooks=hooks, state=state, limits=limits)

    # Only the first two calls executed; the third was truncated by the cap.
    assert len(results) == 2
    assert all(result.error is None for result in results)


@requires_pty_backend
def test_bash_timeout_is_plumbed_into_tool(tmp_path: Path) -> None:
    registry = build_baseline_registry(tmp_path, bash_timeout_seconds=1)
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    state = SessionState(workspace_root=tmp_path, run_id="t-timeout", log=EventLog(tmp_path / "ev.jsonl"))

    results = run_session(
        (ToolCall(name="fs_run_bash", params={"command": "sleep 3"}, call_id="tc-1"),),
        registry=registry,
        hooks=hooks,
        state=state,
        limits=RuntimeLimits(max_iterations=1, bash_timeout_seconds=1),
    )

    assert results[0].error is not None
    assert results[0].error.code == "command_timeout"
    assert "1s" in results[0].summary


# ── S14b.2: per-role iteration keys + resolution (operator decisions 2026-08-17) ──


def test_per_role_keys_parse_into_role_iterations() -> None:
    result = load_runtime_limits(
        """runtime_limits:
  max_iterations: 6
  max_iterations_coder: 40
  max_iterations_planner: 12
"""
    )
    assert result.warnings == (), result.warnings
    assert result.role_iterations == {"coder": 40, "planner": 12}
    # The global knob is untouched by per-role keys.
    assert result.limits.max_iterations == 6


def test_per_role_stub_keys_parse_but_never_apply() -> None:
    result = load_runtime_limits(
        """runtime_limits:
  max_iterations_researcher: 7
  max_iterations_code-reviewer: 8
"""
    )
    assert result.role_iterations == {"researcher": 7, "code-reviewer": 8}
    resolved = resolve_limits_for_role(result, "researcher")
    assert resolved.max_iterations == DEFAULT_MAX_ITERATIONS  # stub: global value, NOT 7
    resolved_reviewer = resolve_limits_for_role(result, "code-reviewer")
    assert resolved_reviewer.max_iterations == DEFAULT_MAX_ITERATIONS  # stub: global value, NOT 8


def test_per_role_key_zero_warns_and_is_absent() -> None:
    result = load_runtime_limits("runtime_limits:\n  max_iterations_coder: 0\n")
    assert any(w.key == "max_iterations_coder" for w in result.warnings)
    assert "coder" not in result.role_iterations


def test_per_role_key_non_integer_warns_and_is_absent() -> None:
    result = load_runtime_limits("runtime_limits:\n  max_iterations_eval: many\n")
    assert any(w.key == "max_iterations_eval" for w in result.warnings)
    assert "eval" not in result.role_iterations


def test_role_iterations_empty_without_keys() -> None:
    result = load_runtime_limits("runtime_limits:\n  bash_timeout_seconds: 45\n")
    assert result.role_iterations == {}


def test_resolve_limits_for_role_config_override_wins() -> None:
    loaded = load_runtime_limits("runtime_limits:\n  max_iterations_coder: 10\n")
    resolved = resolve_limits_for_role(loaded, "coder")
    assert resolved.max_iterations == 10
    # Other fields preserved (replace, not rebuild).
    assert resolved.bash_timeout_seconds == DEFAULT_BASH_TIMEOUT_SECONDS


def test_resolve_limits_for_role_testing_stage_default_99() -> None:
    loaded = load_runtime_limits("runtime_limits:\n  max_iterations: 6\n")
    for role in ("planner", "coder", "eval"):
        assert resolve_limits_for_role(loaded, role).max_iterations == ROLE_ITERATION_DEFAULTS[role] == 99


def test_resolve_limits_for_role_unknown_and_none_keep_global() -> None:
    loaded = load_runtime_limits("runtime_limits:\n  max_iterations: 6\n")
    assert resolve_limits_for_role(loaded, "bogus").max_iterations == 6
    assert resolve_limits_for_role(loaded, None).max_iterations == 6


# ── S14b.2 mutation-triage strengthening (mutation-clearing skill) ──────────
# These pin the full config matrix (tests-writing skill §16.3): every key
# present with a distinctive value, and the all-absent path equal to
# anchored defaults field-by-field. They kill the default-argument and
# key-string mutant class that survived the first targeted sweep.


def test_all_keys_parse_with_distinct_values() -> None:
    """Kitchen-sink config: every knob + all five per-role keys, comments,
    and an inline comment containing a colon (pins partition-vs-rpartition)."""
    result = load_runtime_limits(
        """# leading comment line (with colon: x) — must be ignored
runtime_limits:
  # indented comment with colon: must be ignored too
  no_colon_line_inside_block
  max_iterations: 7
  bash_timeout_seconds: 45
  loop_guard_repeat_warn: 1
  loop_guard_circuit_breaker: 55
  loop_guard_window: 88
  attempt_history_max_entries: 9
  attempt_history_max_age_seconds: 10
  qa_max_iterations: 100
  qa_max_consecutive_errors: 5
  qa_recurring_issue_threshold: 4
  rate_limit_suppression_seconds: 11
  lockfile_suppression_seconds: 12
  auth_expired_suppression_seconds: 13
  cost_budget_usd: 1.25
  max_subagent_spawns_per_session: 14
  max_iterations_planner: 21
  max_iterations_coder: 22  # inline comment with colon: must strip cleanly
  max_iterations_eval: 23
  max_iterations_researcher: 24
  max_iterations_code-reviewer: 25
"""
    )
    assert result.warnings == (), result.warnings
    limits = result.limits
    assert limits.max_iterations == 7
    assert limits.bash_timeout_seconds == 45
    assert limits.loop_guard_repeat_warn == 1
    assert limits.loop_guard_circuit_breaker == 55
    assert limits.loop_guard_window == 88
    assert limits.attempt_history_max_entries == 9
    assert limits.attempt_history_max_age_seconds == 10
    assert limits.qa_max_iterations == 100
    assert limits.qa_max_consecutive_errors == 5
    assert limits.qa_recurring_issue_threshold == 4
    assert limits.rate_limit_suppression_seconds == 11
    assert limits.lockfile_suppression_seconds == 12
    assert limits.auth_expired_suppression_seconds == 13
    assert limits.cost_budget_usd == 1.25
    assert limits.max_subagent_spawns_per_session == 14
    assert result.role_iterations == {
        "planner": 21,
        "coder": 22,
        "eval": 23,
        "researcher": 24,
        "code-reviewer": 25,
    }


def test_no_runtime_limits_block_equals_anchored_defaults_exactly() -> None:
    """Absent block → every field equals its anchor (dataclass equality).

    Kills the mutated-default-argument mutant class: any field whose
    default arg is mutated now differs from the anchor."""
    result = load_runtime_limits("capabilities:\n  ENABLE_DYNAMIC_TOOLS: false\n")
    assert result.warnings == (), result.warnings
    assert result.limits == RuntimeLimits.anchored_defaults()
    assert result.role_iterations == {}


def test_warning_carries_exact_line_no() -> None:
    """line_no is 1-based file position — pins enumerate(start=…) mutants."""
    result = load_runtime_limits("runtime_limits:\n  max_iterations: 6\n  bogus_key: 1\n  max_iterations_coder: 0\n")
    keys = {w.key: w for w in result.warnings}
    assert "bogus_key" in keys
    assert keys["bogus_key"].line_no == 3
    assert keys["max_iterations_coder"].line_no == 4


def test_first_line_indented_is_outside_any_block() -> None:
    """A config whose first line is indented must be ignored entirely
    (documented: lines outside the block are ignored; there is no block
    yet). Pins the ``in_block`` initial-value mutant."""
    result = load_runtime_limits("  max_iterations: 99\n")
    assert result.warnings == (), result.warnings
    assert result.limits == RuntimeLimits.anchored_defaults()


def test_invalid_value_branches_do_not_stop_parsing() -> None:
    """Each warning branch must continue parsing subsequent keys, with exact
    line_no. Kills continue→break and line_no→None mutant classes."""
    cases = {
        "max_iterations: bad": 2,
        "max_iterations: -1": 2,
        "cost_budget_usd: bad": 2,
        "cost_budget_usd: -1.0": 2,
        "cost_budget_usd: nan": 2,
        "cost_budget_usd: inf": 2,
    }
    for bad_line, expected_line_no in cases.items():
        result = load_runtime_limits(f"runtime_limits:\n  {bad_line}\n  bash_timeout_seconds: 45\n")
        assert result.limits.bash_timeout_seconds == 45, bad_line  # later key still parsed
        assert len(result.warnings) == 1, (bad_line, result.warnings)
        assert result.warnings[0].line_no == expected_line_no, bad_line


def test_stray_indented_line_before_block_is_ignored() -> None:
    """An indented line before any block is ignored (not a parse stop)."""
    result = load_runtime_limits("  stray: 1\nruntime_limits:\n  max_iterations: 7\n")
    assert result.limits.max_iterations == 7
    assert result.warnings == (), result.warnings
