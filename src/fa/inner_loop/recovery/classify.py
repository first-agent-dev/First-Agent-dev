"""Failure classifier + ``RecoveryAction`` dispatcher (Wave-2 R-3).

Maps a :class:`ToolError` (or a whole :class:`ToolResult`) to two
artefacts that the inner loop and the future coder-recovery prompt
both consume:

- :class:`FailureCategory` — a tripartite rollup (YT-1 § «failure
  modes that matter to the harness»: invalid_arguments,
  unexpected_environments, provider_errors) plus the Aperant
  ``recovery-manager.ts:200-340`` extension labels
  (broken_build / verification_failed / circular_fix /
  context_exhausted / rate_limited / auth_failure / unknown).
- :class:`RecoveryAction` — what the loop driver SHOULD do next
  (``rollback`` / ``retry`` / ``skip`` / ``escalate``) plus the
  target (which tool / file / subtask) and reason.

This is a **deterministic Python function**, not an LLM call,
per [AGENTS.md PR Checklist rule
#10](../../../../AGENTS.md#pr-checklist) question 4 — classification
is parsing + a lookup table, no model judgement required. The future
``coder-recovery.md`` prompt reads :class:`RecoveryAction` already-
materialised; it does not re-derive the category itself.

Sources: Aperant ``recovery-manager.ts`` (200-340) Part 2 item 8 +
YT-1 #1 tripartite rollup (see ``borrow-roadmap-2026-05.md`` §R-3).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from fa.inner_loop.registry import ToolError, ToolResult


class FailureCategory(StrEnum):
    """Single label per failure; the loop driver routes on this."""

    # YT-1 tripartite rollup. Used when no Aperant-specific label fits.
    INVALID_ARGUMENTS = "invalid_arguments"
    UNEXPECTED_ENVIRONMENTS = "unexpected_environments"
    PROVIDER_ERRORS = "provider_errors"

    # Aperant ``recovery-manager.ts`` extension labels.
    BROKEN_BUILD = "broken_build"
    VERIFICATION_FAILED = "verification_failed"
    CIRCULAR_FIX = "circular_fix"
    CONTEXT_EXHAUSTED = "context_exhausted"
    RATE_LIMITED = "rate_limited"
    AUTH_FAILURE = "auth_failure"

    # Policy / sandbox denials get their own label so coder-recovery
    # can articulate «harness blocked this» rather than «I made a
    # mistake». Aperant has no equivalent because their guards do not
    # emit a classifiable error code.
    POLICY_DENIED = "policy_denied"

    UNKNOWN = "unknown"


class RecoveryActionKind(StrEnum):
    """Deterministic next-step recommendation."""

    ROLLBACK = "rollback"
    RETRY = "retry"
    SKIP = "skip"
    ESCALATE = "escalate"


@dataclass(frozen=True)
class RecoveryAction:
    """Carrier for the loop driver / coder-recovery prompt."""

    kind: RecoveryActionKind
    category: FailureCategory
    target: str
    reason: str
    retryable: bool


# Direct code → category mapping for codes the M-1 runtime emits.
# Anything not in this table falls through to keyword matching on the
# lowercased error message.
_CODE_TO_CATEGORY: dict[str, FailureCategory] = {
    "invalid_params": FailureCategory.INVALID_ARGUMENTS,
    "invalid_payload": FailureCategory.INVALID_ARGUMENTS,
    "hook_deny": FailureCategory.POLICY_DENIED,
    "read_failed": FailureCategory.UNEXPECTED_ENVIRONMENTS,
    "write_failed": FailureCategory.UNEXPECTED_ENVIRONMENTS,
    "command_timeout": FailureCategory.PROVIDER_ERRORS,
    "command_failed": FailureCategory.BROKEN_BUILD,
    "audit_failure": FailureCategory.UNEXPECTED_ENVIRONMENTS,
}


# Keyword → category fallback. Order matters: most specific first.
# Lowercase the message before matching. Keywords are intentionally
# narrow to avoid false-positives on user code in the error string.
_KEYWORD_TO_CATEGORY: tuple[tuple[str, FailureCategory], ...] = (
    ("rate limit", FailureCategory.RATE_LIMITED),
    ("rate_limited", FailureCategory.RATE_LIMITED),
    ("too many requests", FailureCategory.RATE_LIMITED),
    ("429", FailureCategory.RATE_LIMITED),
    ("unauthorized", FailureCategory.AUTH_FAILURE),
    ("forbidden", FailureCategory.AUTH_FAILURE),
    ("401", FailureCategory.AUTH_FAILURE),
    ("403", FailureCategory.AUTH_FAILURE),
    ("invalid api key", FailureCategory.AUTH_FAILURE),
    ("context length", FailureCategory.CONTEXT_EXHAUSTED),
    ("context_length", FailureCategory.CONTEXT_EXHAUSTED),
    ("maximum context", FailureCategory.CONTEXT_EXHAUSTED),
    ("token limit", FailureCategory.CONTEXT_EXHAUSTED),
    ("verification failed", FailureCategory.VERIFICATION_FAILED),
    ("dsv_violation", FailureCategory.VERIFICATION_FAILED),
    ("build failed", FailureCategory.BROKEN_BUILD),
    ("compile error", FailureCategory.BROKEN_BUILD),
    ("provider", FailureCategory.PROVIDER_ERRORS),
    ("connection", FailureCategory.PROVIDER_ERRORS),
    ("timeout", FailureCategory.PROVIDER_ERRORS),
)


# Category → action mapping. The action is what the loop driver
# / coder-recovery prompt SHOULD do; the loop driver still owns the
# decision (it can override based on attempt count, see R-6).
_CATEGORY_TO_ACTION: dict[FailureCategory, RecoveryActionKind] = {
    FailureCategory.INVALID_ARGUMENTS: RecoveryActionKind.RETRY,
    FailureCategory.UNEXPECTED_ENVIRONMENTS: RecoveryActionKind.RETRY,
    FailureCategory.PROVIDER_ERRORS: RecoveryActionKind.RETRY,
    FailureCategory.BROKEN_BUILD: RecoveryActionKind.RETRY,
    FailureCategory.VERIFICATION_FAILED: RecoveryActionKind.RETRY,
    FailureCategory.RATE_LIMITED: RecoveryActionKind.RETRY,
    FailureCategory.CIRCULAR_FIX: RecoveryActionKind.ESCALATE,
    FailureCategory.CONTEXT_EXHAUSTED: RecoveryActionKind.ESCALATE,
    FailureCategory.AUTH_FAILURE: RecoveryActionKind.ESCALATE,
    FailureCategory.POLICY_DENIED: RecoveryActionKind.ESCALATE,
    FailureCategory.UNKNOWN: RecoveryActionKind.ESCALATE,
}


def _category_for(error: ToolError) -> FailureCategory:
    """Resolve a category from the error's code first, then message."""

    direct = _CODE_TO_CATEGORY.get(error.code)
    if direct is not None:
        return direct
    message_lc = error.message.lower()
    for keyword, category in _KEYWORD_TO_CATEGORY:
        if keyword in message_lc:
            return category
    return FailureCategory.UNKNOWN


def classify(error: ToolError, *, target: str = "") -> RecoveryAction:
    """Map a :class:`ToolError` to a :class:`RecoveryAction`.

    ``target`` is the subject the action operates on — typically the
    tool name (``"fs.run_bash"``) or a file path. The caller supplies
    it because the classifier only sees the error, not the call shape.
    A blank target is valid; coder-recovery handles that gracefully.
    """

    category = _category_for(error)
    return RecoveryAction(
        kind=_CATEGORY_TO_ACTION[category],
        category=category,
        target=target,
        reason=error.message,
        # ``error.retryable`` is the runtime's own signal; the
        # classifier carries it through so the loop driver can AND it
        # with the category-derived retry hint.
        retryable=error.retryable,
    )


def classify_result(result: ToolResult, *, target: str = "") -> RecoveryAction | None:
    """Convenience wrapper: ``None`` for successful results."""

    if result.error is None:
        return None
    return classify(result.error, target=target)
