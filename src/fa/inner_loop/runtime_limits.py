"""Runtime caps loaded from ``~/.fa/config.yaml`` (ADR-7 §Amendment 2026-05-20).

Two caps live on the loop driver, not in hook code:

- ``max_iterations`` — hard cap on the deterministic loop (ADR-7 §1
  step 8 + Amendment 2026-05-20 rule 2: default = 6 per R-30/YT-4
  empirical anchor).
- ``bash_timeout_seconds`` — wall-clock timeout for ``fs.run_bash``
  (anchored at 30s in v0.1; raise via config, never via a code constant).

Amendment 2026-05-20 rule 1 says «every retry loop reads its hard cap
from ``~/.fa/config.yaml`` — never from a constant in hook code». The
M-1 substrate ships the canonical anchors as the documented fallback so
the smoke entrypoint runs cleanly out-of-the-box; the future ``fa run``
LLM driver (T-2) tightens this to «refuse to start on missing key».
This is the **T-4 mini** loader — it parses exactly the
``runtime_limits:`` block; the full YAML loader lands with T-4 proper.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
DEFAULT_MAX_ITERATIONS = 6
DEFAULT_BASH_TIMEOUT_SECONDS = 30
# Wave-2 R-2 LoopGuard caps (Kronos `kronos/security/loop_detector.py`
# 3-detector shape + Aperant `recovery-manager.ts:120-145` simpleHash
# threshold). Defaults documented in `borrow-roadmap-2026-05.md` R-2.
DEFAULT_LOOP_GUARD_REPEAT_WARN = 3
DEFAULT_LOOP_GUARD_CIRCUIT_BREAKER = 5
DEFAULT_LOOP_GUARD_WINDOW = 8
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


@dataclass(frozen=True)
class RuntimeLimits:
    """Loop-driver caps. Construct via :func:`load_runtime_limits`."""

    max_iterations: int = DEFAULT_MAX_ITERATIONS
    bash_timeout_seconds: int = DEFAULT_BASH_TIMEOUT_SECONDS
    # Wave-2 R-2 LoopGuard knobs.
    loop_guard_repeat_warn: int = DEFAULT_LOOP_GUARD_REPEAT_WARN
    loop_guard_circuit_breaker: int = DEFAULT_LOOP_GUARD_CIRCUIT_BREAKER
    loop_guard_window: int = DEFAULT_LOOP_GUARD_WINDOW
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

    @classmethod
    def anchored_defaults(cls) -> RuntimeLimits:
        """Return the canonical defaults from ADR-7 §Amendment 2026-05-20."""
        return cls(
            max_iterations=DEFAULT_MAX_ITERATIONS,
            bash_timeout_seconds=DEFAULT_BASH_TIMEOUT_SECONDS,
            loop_guard_repeat_warn=DEFAULT_LOOP_GUARD_REPEAT_WARN,
            loop_guard_circuit_breaker=DEFAULT_LOOP_GUARD_CIRCUIT_BREAKER,
            loop_guard_window=DEFAULT_LOOP_GUARD_WINDOW,
            attempt_history_max_entries=DEFAULT_ATTEMPT_HISTORY_MAX_ENTRIES,
            attempt_history_max_age_seconds=DEFAULT_ATTEMPT_HISTORY_MAX_AGE_SECONDS,
            qa_max_iterations=DEFAULT_QA_MAX_ITERATIONS,
            qa_max_consecutive_errors=DEFAULT_QA_MAX_CONSECUTIVE_ERRORS,
            qa_recurring_issue_threshold=DEFAULT_QA_RECURRING_ISSUE_THRESHOLD,
            rate_limit_suppression_seconds=DEFAULT_RATE_LIMIT_SUPPRESSION_SECONDS,
            lockfile_suppression_seconds=DEFAULT_LOCKFILE_SUPPRESSION_SECONDS,
            auth_expired_suppression_seconds=DEFAULT_AUTH_EXPIRED_SUPPRESSION_SECONDS,
            cost_budget_usd=DEFAULT_COST_BUDGET_USD,
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


_KNOWN_KEYS: frozenset[str] = frozenset(
    {
        "max_iterations",
        "bash_timeout_seconds",
        "loop_guard_repeat_warn",
        "loop_guard_circuit_breaker",
        "loop_guard_window",
        "attempt_history_max_entries",
        "attempt_history_max_age_seconds",
        "qa_max_iterations",
        "qa_max_consecutive_errors",
        "qa_recurring_issue_threshold",
        "rate_limit_suppression_seconds",
        "lockfile_suppression_seconds",
        "auth_expired_suppression_seconds",
        "cost_budget_usd",
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
_FLOAT_KEYS: frozenset[str] = frozenset({"cost_budget_usd"})


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
    found: dict[str, int] = {}
    found_float: dict[str, float] = {}
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
        if key in _FLOAT_KEYS:
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
                continue
            min_allowed_float = 0.0 if key in _ZERO_ALLOWED_KEYS else 1.0
            if float_value < min_allowed_float:
                detail = (
                    f"value must be non-negative: {float_value}"
                    if key in _ZERO_ALLOWED_KEYS
                    else f"value must be positive: {float_value}"
                )
                warnings.append(
                    RuntimeLimitsWarning(
                        line_no=line_no,
                        key=key,
                        detail=detail,
                    )
                )
                continue
            found_float[key] = float_value
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

    limits = RuntimeLimits(
        max_iterations=found.get("max_iterations", DEFAULT_MAX_ITERATIONS),
        bash_timeout_seconds=found.get("bash_timeout_seconds", DEFAULT_BASH_TIMEOUT_SECONDS),
        loop_guard_repeat_warn=found.get("loop_guard_repeat_warn", DEFAULT_LOOP_GUARD_REPEAT_WARN),
        loop_guard_circuit_breaker=found.get(
            "loop_guard_circuit_breaker", DEFAULT_LOOP_GUARD_CIRCUIT_BREAKER
        ),
        loop_guard_window=found.get("loop_guard_window", DEFAULT_LOOP_GUARD_WINDOW),
        attempt_history_max_entries=found.get(
            "attempt_history_max_entries", DEFAULT_ATTEMPT_HISTORY_MAX_ENTRIES
        ),
        attempt_history_max_age_seconds=found.get(
            "attempt_history_max_age_seconds", DEFAULT_ATTEMPT_HISTORY_MAX_AGE_SECONDS
        ),
        qa_max_iterations=found.get("qa_max_iterations", DEFAULT_QA_MAX_ITERATIONS),
        qa_max_consecutive_errors=found.get(
            "qa_max_consecutive_errors", DEFAULT_QA_MAX_CONSECUTIVE_ERRORS
        ),
        qa_recurring_issue_threshold=found.get(
            "qa_recurring_issue_threshold", DEFAULT_QA_RECURRING_ISSUE_THRESHOLD
        ),
        rate_limit_suppression_seconds=found.get(
            "rate_limit_suppression_seconds", DEFAULT_RATE_LIMIT_SUPPRESSION_SECONDS
        ),
        lockfile_suppression_seconds=found.get(
            "lockfile_suppression_seconds", DEFAULT_LOCKFILE_SUPPRESSION_SECONDS
        ),
        auth_expired_suppression_seconds=found.get(
            "auth_expired_suppression_seconds", DEFAULT_AUTH_EXPIRED_SUPPRESSION_SECONDS
        ),
        cost_budget_usd=found_float.get("cost_budget_usd", DEFAULT_COST_BUDGET_USD),
    )
    return RuntimeLimitsLoadResult(limits=limits, warnings=tuple(warnings))


def load_runtime_limits_from_path(
    path: Path = DEFAULT_CONFIG_PATH,
) -> RuntimeLimitsLoadResult:
    """Read ``runtime_limits:`` from ``path``; fall back to anchored defaults.

    Missing file = anchored defaults + empty warnings (the smoke
    entrypoint must run before the user creates ``~/.fa/config.yaml``).
    The stricter «refuse-to-start-on-missing-key» mode lands with the
    ``fa run`` driver in T-2.
    """

    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return RuntimeLimitsLoadResult(limits=RuntimeLimits.anchored_defaults())
    return load_runtime_limits(text)


__all__ = [
    "DEFAULT_ATTEMPT_HISTORY_MAX_AGE_SECONDS",
    "DEFAULT_ATTEMPT_HISTORY_MAX_ENTRIES",
    "DEFAULT_AUTH_EXPIRED_SUPPRESSION_SECONDS",
    "DEFAULT_BASH_TIMEOUT_SECONDS",
    "DEFAULT_COST_BUDGET_USD",
    "DEFAULT_LOCKFILE_SUPPRESSION_SECONDS",
    "DEFAULT_LOOP_GUARD_CIRCUIT_BREAKER",
    "DEFAULT_LOOP_GUARD_REPEAT_WARN",
    "DEFAULT_LOOP_GUARD_WINDOW",
    "DEFAULT_MAX_ITERATIONS",
    "DEFAULT_QA_MAX_CONSECUTIVE_ERRORS",
    "DEFAULT_QA_MAX_ITERATIONS",
    "DEFAULT_QA_RECURRING_ISSUE_THRESHOLD",
    "DEFAULT_RATE_LIMIT_SUPPRESSION_SECONDS",
    "RuntimeLimits",
    "RuntimeLimitsLoadResult",
    "RuntimeLimitsWarning",
    "load_runtime_limits",
    "load_runtime_limits_from_path",
]
