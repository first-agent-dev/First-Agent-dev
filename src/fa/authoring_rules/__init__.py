"""Level-1 authoring rule packs (ADR-11, two-tier TCB).

This package holds the **allowlisted** Level-1 rules dispatched by the
frozen Level-0 kernel (:mod:`fa.authoring_tcb`). Rules return structured
:class:`~fa.authoring_tcb.RuleResult` diagnostics; they never own
dispatch, hashing, or output (ADR-11-I1). New rules land here behind the
static :data:`RULE_ALLOWLIST` **without modifying Level 0** — the kernel
imports nothing from this package, so the TCB boundary stays frozen.

PR 2 (this) registers:

* :data:`EXPORTS_COMPLETENESS` (``FA-AUTHORING-V2-EXPORTS-COMPLETENESS``) —
  HARD-BLOCK; consumes catch-corpus historical omissions F-2 + F-7.
* :data:`TEST_SEMANTIC_DECAY` (``FA-AUTHORING-V4-PYTEST-SKIP`` /
  ``-NON-STRICT-XFAIL`` / ``-FOCUS-MARKER``) — HARD-BLOCK; implements
  ADR-11-I5 §HARD-BLOCK items 1-3.
* :data:`PLACEHOLDER_ASSERTION`
  (``FA-AUTHORING-V11-PLACEHOLDER-ASSERT``) — HARD-BLOCK; implements
  ADR-11-I5 §HARD-BLOCK item 4 and consumes F-9.

See the blueprint Appendix B
(``knowledge/research/ADR-11-Authoring-Guardrails-Blueprint.md``) for
the full PR rollout schedule.

Diagnostic-code namespace (ADR-11-I2, frozen + append-only):
``FA-AUTHORING-V<N>-<SLUG>``. ``V0`` is **reserved** for the Level-0
kernel's own fail-closed diagnostics (manifest / snapshot / rule-crash);
``V1``+ are the Level-1 catch-corpus vectors (``V1..V14``) defined in the
ADR §Verification ``F-1..F-10`` table. A ``V<N>`` is never re-used for a
different rule.
"""

from __future__ import annotations

from fa.authoring_rules.exports import EXPORTS_COMPLETENESS
from fa.authoring_rules.tests import PLACEHOLDER_ASSERTION, TEST_SEMANTIC_DECAY
from fa.authoring_tcb import Rule, RuleContext, RuleResult

__all__ = [
    "EXPORTS_COMPLETENESS",
    "PLACEHOLDER_ASSERTION",
    "RULE_ALLOWLIST",
    "TEST_SEMANTIC_DECAY",
    "Rule",
    "RuleContext",
    "RuleResult",
]

# Static allowlist dispatched by the Level-0 kernel. Append-only and
# explicit: no dynamic discovery (ADR-11-I1). Order is the dispatch
# order; the kernel sorts diagnostics deterministically before output
# so authoring order here does NOT leak into the report.
RULE_ALLOWLIST: tuple[Rule, ...] = (
    EXPORTS_COMPLETENESS,
    TEST_SEMANTIC_DECAY,
    PLACEHOLDER_ASSERTION,
)
