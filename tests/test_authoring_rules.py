"""Tests for the Level-1 rule package (ADR-11; src/fa/authoring_rules).

For PR 1 the allowlist is empty; these tests pin that invariant and the
re-exported protocol surface so PR 2 cannot silently change the contract.
"""

from __future__ import annotations

from fa import authoring_rules
from fa.authoring_tcb import Rule, RuleContext, RuleResult


def test_allowlist_is_empty_tuple_for_pr1() -> None:
    assert authoring_rules.RULE_ALLOWLIST == ()
    assert isinstance(authoring_rules.RULE_ALLOWLIST, tuple)


def test_reexports_kernel_protocol_surface() -> None:
    assert authoring_rules.Rule is Rule
    assert authoring_rules.RuleContext is RuleContext
    assert authoring_rules.RuleResult is RuleResult


def test_dunder_all_is_explicit() -> None:
    assert set(authoring_rules.__all__) == {
        "RULE_ALLOWLIST",
        "Rule",
        "RuleContext",
        "RuleResult",
    }
