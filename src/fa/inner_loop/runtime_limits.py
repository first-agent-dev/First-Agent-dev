"""Runtime caps loaded from ``~/.fa/config.yaml`` (ADR-7 §Amendment 2026-05-20).

Two caps live on the loop driver, not in hook code:

- ``max_iterations`` — hard cap on the deterministic loop (ADR-7 §1
  step 8 + Amendment 2026-05-20 rule 2: default = 6 per R-30/YT-4
  empirical anchor).
- ``bash_timeout_seconds`` — wall-clock timeout for ``fs_run_bash``
  (anchored at 30s in v0.1; raise via config, never via a code constant).

Amendment 2026-05-20 rule 1 says «every retry loop reads its hard cap
from ``~/.fa/config.yaml`` — never from a constant in hook code». The
M-1 substrate ships the canonical anchors as the documented fallback so
the smoke entrypoint runs cleanly out-of-the-box; the future ``fa run``
LLM driver (T-2) tightens this to «refuse to start on missing key».
This is the **T-4 mini** loader — it parses exactly the
``runtime_limits:`` block; the full YAML loader lands with T-4 proper.

Tool context budgets (S12.7 CT2/GAP4) — one ceiling + tabled outliers.
``DEFAULT_TOOL_CONTEXT_BYTES`` (defined beside ``ToolSpec`` in
``registry.py``) is the documented ceiling AND the
``ToolSpec.max_context_bytes`` default. It is NOT imported from here: a
module-scope ``registry → runtime_limits`` import closes the cycle
``registry → runtime_limits → recovery → registry`` (verified S12.7
R14) — import it from ``fa.inner_loop.registry``, never re-type the
literal. Source of truth for every per-tool value:

- Ceiling tier (spec budget = 32_768):
    ``fs_read_file``, ``fs_write_file``, ``fs_spawn_subagent``,
    ``fs_exploration_metrics`` and any tool without an explicit budget
    (``fs_prepare_pr``, workflow tool) — ride the default;
    ``fs_search`` (was 30_000), ``fs_reach`` (was 30_000, an S12.7
    inventory miss confirmed live and unified here), ``fs_run_bash``
    (was 8_000; both builder sites).
  NOTE: fs_search / fs_reach / fs_run_bash still pre-truncate INTERNALLY
  below the ceiling (30_000 / 30_000 / 8_000) until S5/S7 restructure
  their frames; the spec budget is the projection-chokepoint ceiling,
  not the internal cap.
- Deliberate small outliers (kept, with reason):
    4_000  fs_edit_file, fs_chronicle_search, fs_diff — ack-shaped
           envelopes; full payload recoverable via ``[artifact:]``;
    2_048  fs_blackboard_query — compact answer envelope (S8 mention
           purge pending);
    2_000  fs_usage, fs_list_tasks — compact status envelopes;
    1_000  fs_checkpoint, fs_undo, fs_send_ctrl_c — ack-only.
- ``profiles.py`` ``PROFILES_RAW`` ``max_context_bytes`` keys (4096 /
  2048) are unconsumed metadata (verified S12.7 R14: no reader outside
  the dict itself) — noted here so the scatter hunt need not repeat.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from pathlib import Path

from fa._yaml_subset import strip_inline_comment
from fa.config import DEFAULT_CONFIG_PATH
from fa.inner_loop.recovery.attempt_history import (
    DEFAULT_ATTEMPT_HISTORY_MAX_AGE_SECONDS,
    DEFAULT_ATTEMPT_HISTORY_MAX_ENTRIES,
)

# Anchors documented in ADR-7 §Amendment 2026-05-20 rule 2 (max_iterations=6)
# and the bash timeout that PR #24 introduced (30s). Both live here so any
# code that needs the documented default imports from one place — no
# magic constants in ``loop.py`` / ``run_bash.py``.
# §I-S14b-2: iteration cap anchor — role-less ADR-7 default; per-turn semantics (one run_session
# invocation = one LLM response batch); per-role caps resolve via ROLE_ITERATION_DEFAULTS.
DEFAULT_MAX_ITERATIONS = 6
DEFAULT_BASH_TIMEOUT_SECONDS = 30
# S14b.2 (operator decision 2026-08-17, Q-S14b2-1): TESTING-STAGE anchors —
# 99 per turn ≈ uncapped so the deep-testing stage observes the harness
# without the old ill-fitted 6 cap; the operator re-tunes these after the
# testing stage. Per-TURN semantics: one ``run_session`` invocation is one
# LLM response batch (not a session budget). ``DEFAULT_MAX_ITERATIONS``
# above is NOT changed — it stays the ADR-7 §Amendment 2026-05-20 anchor
# for role-less callers (inner-loop-smoke, conformance, tests).
ROLE_ITERATION_DEFAULTS: dict[str, int] = {
    "planner": 99,
    "coder": 99,
    "eval": 99,
    "researcher": 99,  # STUB (Q-S14b2-2): no runtime driver today; kept for future features
    "code-reviewer": 99,  # STUB (Q-S14b2-2): no runtime driver today; kept for future features
}
# Roles that actually reach ``run_session`` through the CLI/workflow driver
# (``cli.py:625``). Stub keys are parsed and retained in
# ``RuntimeLimitsLoadResult.role_iterations`` but NEVER applied by
# ``resolve_limits_for_role`` until a runtime driver exists.
_LIVE_ROLE_NAMES: frozenset[str] = frozenset({"planner", "coder", "eval"})
# Config key → canonical role name. Keys are the runtime role strings, NOT
# the tool-profile names (implementer/verifier never reach ``run_session``;
# their repo-wide rename is tracked in PLAN-role-vocabulary-unification.md).
_ROLE_KEY_TO_NAME: dict[str, str] = {
    "max_iterations_planner": "planner",
    "max_iterations_coder": "coder",
    "max_iterations_eval": "eval",
    "max_iterations_researcher": "researcher",
    "max_iterations_code-reviewer": "code-reviewer",
}
# Wave-2 R-2 LoopGuard caps (Kronos `kronos/security/loop_detector.py`
# 3-detector shape + Aperant `recovery-manager.ts:120-145` simpleHash
# threshold). Defaults documented in `borrow-roadmap-2026-05.md` R-2.
DEFAULT_LOOP_GUARD_REPEAT_WARN = 3
DEFAULT_LOOP_GUARD_CIRCUIT_BREAKER = 5
DEFAULT_LOOP_GUARD_WINDOW = 8
# S12.7 (CT1): period-2 ping-pong oscillation detector (Detector 3). Warn at
# 3 full A-B cycles (6 calls), deny at 4 cycles (8 calls = the default
# window). Field precedent: OpenHands "Alternating Patterns" (6+ cycles),
# OpenClaw pingPong detector. Preventive — no FA transcript shows A-B-A-B
# yet (PLAN-s12.7 RN11).
DEFAULT_LOOP_GUARD_PINGPONG_WARN_CYCLES = 3
DEFAULT_LOOP_GUARD_PINGPONG_BREAK_CYCLES = 4
# Wave-2 R-34 QA-loop circuit-breaker constants (Aperant `qa-loop.ts`
# magic-validated anchors per `borrow-roadmap-2026-05.md` R-34). The
# constants land here as documented defaults so the future QA
# orchestrator R-N inherits them rather than reinventing magic numbers;
# nothing in M-1/M-2/M-3 wires them yet because the QA orchestrator
# itself is DEFER per roadmap §2.9. Anchors:
# - ``MAX_QA_ITERATIONS = 50`` — hard cap on the QA refinement loop
#   before the engine forces a hand-off (Aperant prod-tuned default).
# - ``MAX_CONSECUTIVE_ERRORS = 3`` — trip the circuit breaker after
#   three consecutive failed iterations.
# - ``RECURRING_ISSUE_THRESHOLD = 3`` — escalate-to-human after the
#   same issue recurs three times (different from consecutive errors:
#   counts identical issues, not consecutive ones).
DEFAULT_QA_MAX_ITERATIONS = 50
DEFAULT_QA_MAX_CONSECUTIVE_ERRORS = 3
DEFAULT_QA_RECURRING_ISSUE_THRESHOLD = 3
# Wave-2 R-4 BlockerMiddleware suppression windows. Suppress = window
# during which subsequent calls to the same tool are denied after a
# blocker pattern has been observed, with a synthetic-failure reason
# (synthetic-credential-injection lands with T-2 LLM driver; M-1 only
# emits the deny + ``kind="hook_decision"`` audit row).
#
# - Rate-limit: 30s matches Aperant ``pause-handler.ts:30-80`` interval
#   (the only proven prod-tuned anchor in the roadmap §R-4 source set).
# - Lockfile: 5s — most lockfile contention self-resolves within a few
#   seconds (apt, cargo, npm); longer waits indicate stuck process and
#   the LLM should see the failure on the next retry.
# - Auth-expired: 0 = observe-only (no gating). The LLM-driver T-2 will
#   wire synthetic re-auth via ``Decision.modify``; until then, denying
#   on auth would block the LLM from being notified of the auth state.
# S4b/RK6: wall-clock ceiling for a NESTED workflow pipeline launched by the
# ``invoke_workflow`` tool. Serial tool dispatch has no timeout (the only
# timeouts in ``loop.py`` are on the parallel branch), and RuntimeLimits has no
# session wall-clock cap, so one ``invoke_workflow`` call could otherwise run
# planner -> coder -> eval plus repair/replan rounds with no bound on elapsed
# time, blocking the chat turn indefinitely. Strictly positive: ``0`` is NOT
# "disabled" (that is what omitting ``deadline_mono`` means), so this key stays
# out of ``_ZERO_ALLOWED_KEYS``.
DEFAULT_WORKFLOW_TIMEOUT_SECONDS = 1800

# S7 / CT8 -> S10/CT9 (Q25): the chat escalation gate ships OFF. The
# mechanism stays in place and the key remains honoured — an operator who
# wants the estimator's top-confidence bucket to auto-suggest workflow sets
# ``chat_escalation_gate: true``. Observe-only expansion advice (levels,
# observations, handoff) is unaffected; no tool is ever removed mid-run.
DEFAULT_CHAT_ESCALATION_GATE = False

# S10 / CT6: structural escalation budget K — the maximum number of
# ``invoke_workflow`` calls per chat session. Enforced in the tool via the
# invocation-count closure (the (K+1)-th call returns
# ``workflow_budget_exhausted``). The pure expansion module deliberately
# does not know K (audit F1): level 3 *is* that tool call.
DEFAULT_MAX_WORKFLOW_INVOCATIONS = 2

# S10 / CT8 (DP-6): calibration showcase knobs. ``epsilon`` is the tolerance
# for the below-reliability flag (flag when success_rate < 1 - epsilon);
# ``min_flag_runs`` is the minimum sample size below which the flag never
# fires (avoid crying wolf on 1-2 runs). Both are display-only — no runtime
# consumer, both are code variables so they can be retuned per install. The
# flag toggles OFF by setting ``min_flag_runs`` above the available sample
# (epsilon itself stays in the valid (0.0, 1.0] tolerance range).
DEFAULT_CALIBRATION_EPSILON = 0.05
DEFAULT_MIN_FLAG_RUNS = 10

DEFAULT_RATE_LIMIT_SUPPRESSION_SECONDS = 30
DEFAULT_LOCKFILE_SUPPRESSION_SECONDS = 5
DEFAULT_AUTH_EXPIRED_SUPPRESSION_SECONDS = 0
# Wave-3 R-45 cost guardian default. ``None`` = unbounded (no gating,
# no upper limit); ``0.0`` = observe-only (extractor still runs and
# the rollup still accumulates, but the gate never denies); ``> 0`` =
# hard cap. The default sits at ``None`` because the M-1 substrate has
# no cost signal on baseline tools (the LLM-driver T-2 emits the
# ``cost=...`` artifact the extractor reads); pinning a concrete USD
# default here would silently shape the first T-2 runs before the
# baseline-USD is measured. See ``fa.observability.cost_guardian``
# module docstring for the per-mode semantics.
DEFAULT_COST_BUDGET_USD: float | None = None
# ADR-15: subagent spawn limit for 1 subagent v0.1 to eliminate scope creep,
# sequential single-shot, enforced via RuntimeLimits.
DEFAULT_MAX_SUBAGENT_SPAWNS_PER_SESSION = 3


@dataclass(frozen=True)
class RuntimeLimits:
    """Loop-driver caps. Construct via :func:`load_runtime_limits`."""

    max_iterations: int = DEFAULT_MAX_ITERATIONS
    bash_timeout_seconds: int = DEFAULT_BASH_TIMEOUT_SECONDS
    # Wave-2 R-2 LoopGuard knobs.
    loop_guard_repeat_warn: int = DEFAULT_LOOP_GUARD_REPEAT_WARN
    loop_guard_circuit_breaker: int = DEFAULT_LOOP_GUARD_CIRCUIT_BREAKER
    loop_guard_window: int = DEFAULT_LOOP_GUARD_WINDOW
    # S12.7 (CT1): ping-pong oscillation knobs (Detector 3).
    loop_guard_pingpong_warn_cycles: int = DEFAULT_LOOP_GUARD_PINGPONG_WARN_CYCLES
    loop_guard_pingpong_break_cycles: int = DEFAULT_LOOP_GUARD_PINGPONG_BREAK_CYCLES
    # Wave-2 R-6 attempt-history knobs (Aperant anchors).
    attempt_history_max_entries: int = DEFAULT_ATTEMPT_HISTORY_MAX_ENTRIES
    attempt_history_max_age_seconds: int = DEFAULT_ATTEMPT_HISTORY_MAX_AGE_SECONDS
    # Wave-2 R-34 QA-loop circuit-breaker constants (documented
    # defaults; not yet wired — QA orchestrator is DEFER per
    # `borrow-roadmap-2026-05.md` §2.9).
    qa_max_iterations: int = DEFAULT_QA_MAX_ITERATIONS
    qa_max_consecutive_errors: int = DEFAULT_QA_MAX_CONSECUTIVE_ERRORS
    qa_recurring_issue_threshold: int = DEFAULT_QA_RECURRING_ISSUE_THRESHOLD
    # Wave-2 R-4 BlockerMiddleware suppression windows (seconds; 0 =
    # observe-only). See module-level anchors for rationale.
    rate_limit_suppression_seconds: int = DEFAULT_RATE_LIMIT_SUPPRESSION_SECONDS
    lockfile_suppression_seconds: int = DEFAULT_LOCKFILE_SUPPRESSION_SECONDS
    auth_expired_suppression_seconds: int = DEFAULT_AUTH_EXPIRED_SUPPRESSION_SECONDS
    # Wave-3 R-45 cost guardian budget; see module-level
    # ``DEFAULT_COST_BUDGET_USD`` anchor for the tri-mode semantics.
    cost_budget_usd: float | None = DEFAULT_COST_BUDGET_USD
    # ADR-15: subagent spawn limit
    max_subagent_spawns_per_session: int = DEFAULT_MAX_SUBAGENT_SPAWNS_PER_SESSION
    # S4b/RK6: nested-workflow wall-clock ceiling (seconds).
    workflow_timeout_seconds: int = DEFAULT_WORKFLOW_TIMEOUT_SECONDS
    chat_escalation_gate: bool = DEFAULT_CHAT_ESCALATION_GATE
    # S10 / CT6: structural escalation budget K (see DEFAULT_MAX_WORKFLOW_INVOCATIONS).
    max_workflow_invocations: int = DEFAULT_MAX_WORKFLOW_INVOCATIONS
    # S10 / CT8: calibration showcase knobs (display-only; see anchors).
    calibration_epsilon: float = DEFAULT_CALIBRATION_EPSILON
    min_flag_runs: int = DEFAULT_MIN_FLAG_RUNS

    @classmethod
    def anchored_defaults(cls) -> RuntimeLimits:
        """Return the canonical defaults from ADR-7 §Amendment 2026-05-20."""
        return cls(
            max_iterations=DEFAULT_MAX_ITERATIONS,
            bash_timeout_seconds=DEFAULT_BASH_TIMEOUT_SECONDS,
            loop_guard_repeat_warn=DEFAULT_LOOP_GUARD_REPEAT_WARN,
            loop_guard_circuit_breaker=DEFAULT_LOOP_GUARD_CIRCUIT_BREAKER,
            loop_guard_window=DEFAULT_LOOP_GUARD_WINDOW,
            loop_guard_pingpong_warn_cycles=DEFAULT_LOOP_GUARD_PINGPONG_WARN_CYCLES,
            loop_guard_pingpong_break_cycles=DEFAULT_LOOP_GUARD_PINGPONG_BREAK_CYCLES,
            attempt_history_max_entries=DEFAULT_ATTEMPT_HISTORY_MAX_ENTRIES,
            attempt_history_max_age_seconds=DEFAULT_ATTEMPT_HISTORY_MAX_AGE_SECONDS,
            qa_max_iterations=DEFAULT_QA_MAX_ITERATIONS,
            qa_max_consecutive_errors=DEFAULT_QA_MAX_CONSECUTIVE_ERRORS,
            qa_recurring_issue_threshold=DEFAULT_QA_RECURRING_ISSUE_THRESHOLD,
            rate_limit_suppression_seconds=DEFAULT_RATE_LIMIT_SUPPRESSION_SECONDS,
            lockfile_suppression_seconds=DEFAULT_LOCKFILE_SUPPRESSION_SECONDS,
            auth_expired_suppression_seconds=DEFAULT_AUTH_EXPIRED_SUPPRESSION_SECONDS,
            cost_budget_usd=DEFAULT_COST_BUDGET_USD,
            max_subagent_spawns_per_session=DEFAULT_MAX_SUBAGENT_SPAWNS_PER_SESSION,
            workflow_timeout_seconds=DEFAULT_WORKFLOW_TIMEOUT_SECONDS,
            chat_escalation_gate=DEFAULT_CHAT_ESCALATION_GATE,
            max_workflow_invocations=DEFAULT_MAX_WORKFLOW_INVOCATIONS,
            calibration_epsilon=DEFAULT_CALIBRATION_EPSILON,
            min_flag_runs=DEFAULT_MIN_FLAG_RUNS,
        )


@dataclass(frozen=True)
class RuntimeLimitsWarning:
    """Non-fatal issue surfaced during parse (mirror of CapabilityWarning)."""

    line_no: int
    key: str
    detail: str


@dataclass(frozen=True)
class RuntimeLimitsLoadResult:
    limits: RuntimeLimits
    warnings: tuple[RuntimeLimitsWarning, ...] = field(default_factory=tuple)
    # S14b.2: role name → iteration cap, from the ``max_iterations_<role>``
    # config keys. Includes stub roles (researcher/code-reviewer) — parsed
    # and retained, never applied by ``resolve_limits_for_role``.
    role_iterations: dict[str, int] = field(default_factory=dict)


_KNOWN_KEYS: frozenset[str] = frozenset(
    {
        "max_iterations",
        "bash_timeout_seconds",
        "loop_guard_repeat_warn",
        "loop_guard_circuit_breaker",
        "loop_guard_window",
        "loop_guard_pingpong_warn_cycles",
        "loop_guard_pingpong_break_cycles",
        "attempt_history_max_entries",
        "attempt_history_max_age_seconds",
        "qa_max_iterations",
        "qa_max_consecutive_errors",
        "qa_recurring_issue_threshold",
        "rate_limit_suppression_seconds",
        "lockfile_suppression_seconds",
        "auth_expired_suppression_seconds",
        "cost_budget_usd",
        "max_subagent_spawns_per_session",
        "workflow_timeout_seconds",
        # S7 / CT8: the only boolean key. See _BOOL_KEYS for parsing.
        "chat_escalation_gate",
        # S10: escalation budget K + calibration showcase knobs (CT6/CT8).
        "max_workflow_invocations",
        "calibration_epsilon",
        "min_flag_runs",
        # S14b.2 per-role iteration keys (three live + two stubs, Q-S14b2-2).
        "max_iterations_planner",
        "max_iterations_coder",
        "max_iterations_eval",
        "max_iterations_researcher",
        "max_iterations_code-reviewer",
    }
)

# Keys where ``0`` is documented as a valid value («observe-only» mode for
# ``BlockerMiddleware``: gate returns ``allow`` when ``suppression_seconds
# <= 0``, see ``hooks/blockers.py`` ``_gate``). The default validator
# rejects ``value <= 0`` because every other knob in the config (loop
# caps, history limits, QA thresholds) must be strictly positive; these
# four are the explicit exception (three R-4 suppression windows +
# R-45 ``cost_budget_usd`` where ``0`` is observe-only — see
# ``fa.observability.cost_guardian`` module docstring).
_ZERO_ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        "rate_limit_suppression_seconds",
        "lockfile_suppression_seconds",
        "auth_expired_suppression_seconds",
        "cost_budget_usd",
    }
)

# Keys parsed as ``float`` rather than ``int``. ``cost_budget_usd`` is
# a USD value (R-45) so the YAML config can carry sub-dollar budgets
# like ``0.50`` without losing precision; every other knob is an
# integer count (iterations, seconds, entries, ...).
_FLOAT_KEYS: frozenset[str] = frozenset({"cost_budget_usd", "calibration_epsilon"})

# Float keys bounded to (0.0, 1.0] (probability/tolerance values). Zero is
# NOT allowed for these (``epsilon: 0`` would flag every imperfect mode with
# no tolerance); operators who want the flag off set ``min_flag_runs`` above
# their sample size. NaN/Inf are rejected by the shared float path.
_UNIT_INTERVAL_KEYS: frozenset[str] = frozenset({"calibration_epsilon"})

# ``chat_escalation_gate`` is still the only boolean knob. It gets its own
# set for the same reason ``_FLOAT_KEYS`` exists — so a typo in one key
# can never silently fall through the wrong type-check.
_BOOL_KEYS: frozenset[str] = frozenset({"chat_escalation_gate"})

# Accepted spellings, lowercased. Deliberately NOT ``bool(value_str)``: that
# maps "false" and "0" to True, which would turn an operator's attempt to
# disable the gate into a no-op they could only discover by reading the source.
_BOOL_TRUE: frozenset[str] = frozenset({"true", "yes", "on", "1"})
_BOOL_FALSE: frozenset[str] = frozenset({"false", "no", "off", "0"})


def _accept_bool_key(
    *,
    key: str,
    value_str: str,
    line_no: int,
    found_bool: dict[str, bool],
    warnings: list[RuntimeLimitsWarning],
) -> None:
    """Parse one boolean key into *found_bool*, or record a warning.

    Hoisted out of :func:`load_runtime_limits` — including its warn branch —
    to keep that function under the S10b cyclomatic-complexity ceiling of 15.
    Inlining the parse measured 17, and leaving the warn branch behind still
    measured 16.

    Tolerates surrounding quotes because YAML writers habitually add them. An
    unrecognised value warns and writes nothing, so the anchored default
    stands: silently guessing is exactly the wrong move for a key whose whole
    job is enabling or disabling a guard.
    """
    lowered = value_str.strip().strip('"').strip("'").lower()
    if lowered in _BOOL_TRUE:
        found_bool[key] = True
        return
    if lowered in _BOOL_FALSE:
        found_bool[key] = False
        return
    warnings.append(
        RuntimeLimitsWarning(
            line_no=line_no,
            key=key,
            detail=f"non-boolean value: {value_str!r}",
        )
    )


def _accept_float_key(
    *,
    key: str,
    value_str: str,
    line_no: int,
    found_float: dict[str, float],
    warnings: list[RuntimeLimitsWarning],
) -> None:
    """Parse one float key into *found_float*, or record a warning.

    Mirrors :func:`_accept_bool_key` and is hoisted for the same reason:
    keeping :func:`load_runtime_limits` under the S10b cyclomatic-complexity
    ceiling of 15. NaN/Inf are rejected (they silently disable the cost
    guardian); keys in :data:`_UNIT_INTERVAL_KEYS` are bounded to
    ``(0.0, 1.0]``; every other float key follows the non-negative /
    positive rule shared with the int path. On any failure the anchored
    default stands — a typo never silently disables a guard.
    """
    try:
        float_value = float(value_str)
    except ValueError:
        warnings.append(
            RuntimeLimitsWarning(
                line_no=line_no,
                key=key,
                detail=f"non-numeric value: {value_str!r}",
            )
        )
        return
    # ``float("nan")`` / ``float("inf")`` parse without raising, but NaN
    # poisons the rollup and +/-Inf flips the gate the opposite way.
    if math.isnan(float_value) or math.isinf(float_value):
        warnings.append(
            RuntimeLimitsWarning(
                line_no=line_no,
                key=key,
                detail=f"value must be a finite number: {value_str!r}",
            )
        )
        return
    if key in _UNIT_INTERVAL_KEYS:
        if not 0.0 < float_value <= 1.0:
            warnings.append(
                RuntimeLimitsWarning(
                    line_no=line_no,
                    key=key,
                    detail=f"value must be in (0.0, 1.0]: {float_value}",
                )
            )
            return
        found_float[key] = float_value
        return
    min_allowed_float = 0.0 if key in _ZERO_ALLOWED_KEYS else 1.0
    if float_value < min_allowed_float:
        detail = (
            f"value must be non-negative: {float_value}"
            if key in _ZERO_ALLOWED_KEYS
            else f"value must be positive: {float_value}"
        )
        warnings.append(RuntimeLimitsWarning(line_no=line_no, key=key, detail=detail))
        return
    found_float[key] = float_value


def load_runtime_limits(text: str) -> RuntimeLimitsLoadResult:
    """Parse a ``runtime_limits:`` block from a YAML config text.

    Recognises exactly:

    .. code-block:: yaml

        runtime_limits:
          max_iterations: 6
          bash_timeout_seconds: 30

    Lines outside the block are ignored. Unknown keys inside the block
    surface as :class:`RuntimeLimitsWarning` entries; missing keys
    inherit the documented anchors so the loop driver still starts.
    Negative values surface as warnings and the anchor is kept. ``0``
    is rejected for every key **except** the
    :data:`_ZERO_ALLOWED_KEYS` set (the three R-4 ``*_suppression_seconds``
    blocker knobs where ``0`` means «observe-only», plus the R-45
    ``cost_budget_usd`` knob with the same observe-only semantics).
    Values for keys in :data:`_FLOAT_KEYS` are parsed as ``float``
    rather than ``int`` (currently just R-45 ``cost_budget_usd``).
    """

    # Two dicts keyed by ``_FLOAT_KEYS`` membership so the dataclass
    # constructor below can type-narrow each ``found.get`` call to its
    # exact field type (avoids ``int | float`` unions leaking into the
    # constructor under mypy --strict).
    # Reviewed duplicate-code waiver: the line-scanner skeleton below
    # mirrors fa.config.load_capabilities by design — both implement the
    # same hand-rolled YAML-subset walk documented in pyproject.toml
    # (pyyaml dependency comment). Unify when the shared YAML loader
    # lands (v0.2 HookRegistry PR, R-1); until then keep both in sync.
    # pylint: disable=duplicate-code
    found: dict[str, int] = {}
    found_float: dict[str, float] = {}
    found_bool: dict[str, bool] = {}
    found_role: dict[str, int] = {}
    warnings: list[RuntimeLimitsWarning] = []
    in_block = False

    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if indent == 0:
            in_block = stripped.rstrip(":") == "runtime_limits" and stripped.endswith(":")
            continue
        if not in_block:
            continue
        if ":" not in stripped:
            continue
        key_raw, _, rest = stripped.partition(":")
        key = key_raw.strip()
        value_str = strip_inline_comment(rest).strip()
        if key not in _KNOWN_KEYS:
            warnings.append(RuntimeLimitsWarning(line_no=line_no, key=key, detail="unknown key"))
            continue
        # R-45: ``cost_budget_usd`` is a float-valued USD knob; every
        # other key is an integer count (iterations, seconds, entries,
        # …). Keep the per-key parse type explicit so a typo in one
        # key never silently falls through the wrong type-check.
        if key in _BOOL_KEYS:
            _accept_bool_key(
                key=key,
                value_str=value_str,
                line_no=line_no,
                found_bool=found_bool,
                warnings=warnings,
            )
            continue
        if key in _FLOAT_KEYS:
            _accept_float_key(
                key=key,
                value_str=value_str,
                line_no=line_no,
                found_float=found_float,
                warnings=warnings,
            )
            continue
        try:
            int_value = int(value_str)
        except ValueError:
            warnings.append(
                RuntimeLimitsWarning(
                    line_no=line_no,
                    key=key,
                    detail=f"non-integer value: {value_str!r}",
                )
            )
            continue
        min_allowed = 0 if key in _ZERO_ALLOWED_KEYS else 1
        if int_value < min_allowed:
            detail = (
                f"value must be non-negative: {int_value}"
                if key in _ZERO_ALLOWED_KEYS
                else f"value must be positive: {int_value}"
            )
            warnings.append(
                RuntimeLimitsWarning(
                    line_no=line_no,
                    key=key,
                    detail=detail,
                )
            )
            continue
        found[key] = int_value
        # S14b.2: per-role iteration keys resolve to role names after passing
        # the same positive-int validation as every other knob.
        if key in _ROLE_KEY_TO_NAME:
            found_role[_ROLE_KEY_TO_NAME[key]] = int_value

    limits = RuntimeLimits(
        max_iterations=found.get("max_iterations", DEFAULT_MAX_ITERATIONS),
        bash_timeout_seconds=found.get("bash_timeout_seconds", DEFAULT_BASH_TIMEOUT_SECONDS),
        loop_guard_repeat_warn=found.get("loop_guard_repeat_warn", DEFAULT_LOOP_GUARD_REPEAT_WARN),
        loop_guard_circuit_breaker=found.get("loop_guard_circuit_breaker", DEFAULT_LOOP_GUARD_CIRCUIT_BREAKER),
        loop_guard_window=found.get("loop_guard_window", DEFAULT_LOOP_GUARD_WINDOW),
        loop_guard_pingpong_warn_cycles=found.get(
            "loop_guard_pingpong_warn_cycles", DEFAULT_LOOP_GUARD_PINGPONG_WARN_CYCLES
        ),
        loop_guard_pingpong_break_cycles=found.get(
            "loop_guard_pingpong_break_cycles", DEFAULT_LOOP_GUARD_PINGPONG_BREAK_CYCLES
        ),
        attempt_history_max_entries=found.get("attempt_history_max_entries", DEFAULT_ATTEMPT_HISTORY_MAX_ENTRIES),
        attempt_history_max_age_seconds=found.get(
            "attempt_history_max_age_seconds", DEFAULT_ATTEMPT_HISTORY_MAX_AGE_SECONDS
        ),
        qa_max_iterations=found.get("qa_max_iterations", DEFAULT_QA_MAX_ITERATIONS),
        qa_max_consecutive_errors=found.get("qa_max_consecutive_errors", DEFAULT_QA_MAX_CONSECUTIVE_ERRORS),
        qa_recurring_issue_threshold=found.get("qa_recurring_issue_threshold", DEFAULT_QA_RECURRING_ISSUE_THRESHOLD),
        rate_limit_suppression_seconds=found.get(
            "rate_limit_suppression_seconds", DEFAULT_RATE_LIMIT_SUPPRESSION_SECONDS
        ),
        lockfile_suppression_seconds=found.get("lockfile_suppression_seconds", DEFAULT_LOCKFILE_SUPPRESSION_SECONDS),
        auth_expired_suppression_seconds=found.get(
            "auth_expired_suppression_seconds", DEFAULT_AUTH_EXPIRED_SUPPRESSION_SECONDS
        ),
        cost_budget_usd=found_float.get("cost_budget_usd", DEFAULT_COST_BUDGET_USD),
        max_subagent_spawns_per_session=found.get(
            "max_subagent_spawns_per_session", DEFAULT_MAX_SUBAGENT_SPAWNS_PER_SESSION
        ),
        workflow_timeout_seconds=found.get("workflow_timeout_seconds", DEFAULT_WORKFLOW_TIMEOUT_SECONDS),
        chat_escalation_gate=found_bool.get("chat_escalation_gate", DEFAULT_CHAT_ESCALATION_GATE),
        max_workflow_invocations=found.get("max_workflow_invocations", DEFAULT_MAX_WORKFLOW_INVOCATIONS),
        calibration_epsilon=found_float.get("calibration_epsilon", DEFAULT_CALIBRATION_EPSILON),
        min_flag_runs=found.get("min_flag_runs", DEFAULT_MIN_FLAG_RUNS),
    )
    return RuntimeLimitsLoadResult(limits=limits, warnings=tuple(warnings), role_iterations=found_role)


def load_runtime_limits_from_path(
    path: Path | None = None,
) -> RuntimeLimitsLoadResult:
    """Read ``runtime_limits:`` from ``path``; fall back to anchored defaults.

    Missing file = anchored defaults + empty warnings (the smoke
    entrypoint must run before the user creates ``~/.fa/config.yaml``).
    The stricter «refuse-to-start-on-missing-key» mode lands with the
    ``fa run`` driver in T-2.

    ``path=None`` resolves :data:`DEFAULT_CONFIG_PATH` at CALL time, not at
    import time: the module-level constant is frozen at first import, so a
    deferred lookup is what keeps the CLI honouring the operator's HOME as
    of process start and lets tests monkeypatch the module global (S14b.2
    seam test). Callers that pass an explicit path are unaffected.
    """
    if path is None:
        path = DEFAULT_CONFIG_PATH
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return RuntimeLimitsLoadResult(limits=RuntimeLimits.anchored_defaults())
    return load_runtime_limits(text)


def resolve_limits_for_role(loaded: RuntimeLimitsLoadResult, role: str | None) -> RuntimeLimits:
    """Resolve the per-role iteration cap on top of a loaded config result.

    Cascade (S14b.2 CT-2, operator decisions Q-S14b2-1/Q-S14b2-2):
    1. live role + config key present  → ``role_iterations[role]``;
    2. live role, no config key        → ``ROLE_ITERATION_DEFAULTS[role]``
       (TESTING-STAGE anchor, 99 per turn);
    3. stub roles (researcher/code-reviewer) and any other/unknown role →
       the loaded global value (``max_iterations``) unchanged.

    Pure function — no I/O, no warnings: the loader owns parse feedback;
    this owns the application policy. ``None`` role means «no role scope»
    (smoke/conformance paths) and keeps the global value.
    """
    if role is not None and role in _LIVE_ROLE_NAMES:
        role_str: str = role
        return replace(
            loaded.limits,
            max_iterations=loaded.role_iterations.get(role_str, ROLE_ITERATION_DEFAULTS[role_str]),
        )
    return loaded.limits


__all__ = [
    "DEFAULT_ATTEMPT_HISTORY_MAX_AGE_SECONDS",
    "DEFAULT_ATTEMPT_HISTORY_MAX_ENTRIES",
    "DEFAULT_AUTH_EXPIRED_SUPPRESSION_SECONDS",
    "DEFAULT_BASH_TIMEOUT_SECONDS",
    "DEFAULT_CALIBRATION_EPSILON",
    "DEFAULT_CHAT_ESCALATION_GATE",
    "DEFAULT_COST_BUDGET_USD",
    "DEFAULT_LOCKFILE_SUPPRESSION_SECONDS",
    "DEFAULT_LOOP_GUARD_CIRCUIT_BREAKER",
    "DEFAULT_LOOP_GUARD_PINGPONG_BREAK_CYCLES",
    "DEFAULT_LOOP_GUARD_PINGPONG_WARN_CYCLES",
    "DEFAULT_LOOP_GUARD_REPEAT_WARN",
    "DEFAULT_LOOP_GUARD_WINDOW",
    "DEFAULT_MAX_ITERATIONS",
    "DEFAULT_MAX_SUBAGENT_SPAWNS_PER_SESSION",
    "DEFAULT_MAX_WORKFLOW_INVOCATIONS",
    "DEFAULT_MIN_FLAG_RUNS",
    "DEFAULT_QA_MAX_CONSECUTIVE_ERRORS",
    "DEFAULT_QA_MAX_ITERATIONS",
    "DEFAULT_QA_RECURRING_ISSUE_THRESHOLD",
    "DEFAULT_RATE_LIMIT_SUPPRESSION_SECONDS",
    "DEFAULT_WORKFLOW_TIMEOUT_SECONDS",
    "ROLE_ITERATION_DEFAULTS",
    "RuntimeLimits",
    "RuntimeLimitsLoadResult",
    "RuntimeLimitsWarning",
    "load_runtime_limits",
    "load_runtime_limits_from_path",
    "resolve_limits_for_role",
]
