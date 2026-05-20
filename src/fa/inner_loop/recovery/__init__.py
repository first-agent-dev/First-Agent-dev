"""Failure classification + attempt-history (Wave-2 R-3 + R-6).

R-3 maps a :class:`ToolError` to a :class:`RecoveryAction` deterministically
(per AGENTS.md PR Checklist rule #10 question 4: classification is a
deterministic Python function, never an LLM call). R-6 maintains the
per-run ``attempt_history.json`` writer that the future
``knowledge/prompts/coder-recovery.md`` reader prompt consumes before
each retry.

Both surfaces share one shape:

- ``classify(error)`` → ``RecoveryAction`` is the pure mapping.
- ``AttemptHistory`` is the JSON-backed sliding window (cap + max-age
  loaded from ``RuntimeLimits``).
- The observers that wire them into ``HookRegistry`` live next to the
  other built-in hooks in ``fa.inner_loop.hooks``.
"""

from __future__ import annotations

from fa.inner_loop.recovery.attempt_history import (
    AttemptHistory,
    AttemptHistoryEntry,
    canonical_params_hash,
)
from fa.inner_loop.recovery.classify import (
    FailureCategory,
    RecoveryAction,
    RecoveryActionKind,
    classify,
    classify_result,
)

__all__ = [
    "AttemptHistory",
    "AttemptHistoryEntry",
    "FailureCategory",
    "RecoveryAction",
    "RecoveryActionKind",
    "canonical_params_hash",
    "classify",
    "classify_result",
]
