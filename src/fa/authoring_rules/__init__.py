"""Level-1 authoring rule packs (ADR-11, two-tier TCB).

This package holds the **allowlisted** Level-1 rules dispatched by the
frozen Level-0 kernel (:mod:`fa.authoring_tcb`). Rules return structured
:class:`~fa.authoring_tcb.RuleResult` diagnostics; they never own
dispatch, hashing, or output (ADR-11-I1). New rules land here behind the
static :data:`RULE_ALLOWLIST` **without modifying Level 0** — the kernel
imports nothing from this package, so the TCB boundary stays frozen.

For v0.1 (PR 1) the allowlist is **empty**: the kernel parses the
manifest, enumerates+hashes the snapshot, and emits an empty diagnostic
list on a clean tree. The first teeth (V2 exports, V4/V10/V11 tests) land
in PR 2; see the blueprint Appendix B
(``knowledge/research/ADR-11-Authoring-Guardrails-Blueprint.md``).

Diagnostic-code namespace (ADR-11-I2, frozen + append-only):
``FA-AUTHORING-V<N>-<SLUG>``. ``V0`` is **reserved** for the Level-0
kernel's own fail-closed diagnostics (manifest / snapshot / rule-crash);
``V1``+ are the Level-1 catch-corpus vectors (``V1..V14``) defined in the
ADR §Verification ``F-1..F-10`` table. A ``V<N>`` is never re-used for a
different rule.
"""

from __future__ import annotations

from fa.authoring_tcb import Rule, RuleContext, RuleResult

__all__ = ["RULE_ALLOWLIST", "Rule", "RuleContext", "RuleResult"]

# Static allowlist dispatched by the Level-0 kernel. Append-only and
# explicit: no dynamic discovery (ADR-11-I1). Empty for PR 1.
RULE_ALLOWLIST: tuple[Rule, ...] = ()
