"""Tests for the Level-1 rule package (ADR-11; src/fa/authoring_rules).

Pins the public surface of the allowlist module so PR-3+ cannot
silently change the contract: the count, identity, and ordering of
:data:`fa.authoring_rules.RULE_ALLOWLIST` are deliberate invariants.
"""

from __future__ import annotations

from fa import authoring_rules
from fa.authoring_tcb import Rule, RuleContext, RuleResult


def test_allowlist_pr2_has_three_rules() -> None:
    # PR 2 registers three rule callables: exports (V2), test-decay
    # (V4 family), placeholder-asserts (V11). Bumping this count is a
    # deliberate act — bump the assertion together with the new entry.
    assert len(authoring_rules.RULE_ALLOWLIST) == 3
    assert isinstance(authoring_rules.RULE_ALLOWLIST, tuple)


def test_allowlist_contains_exact_rule_callables() -> None:
    assert authoring_rules.RULE_ALLOWLIST == (
        authoring_rules.EXPORTS_COMPLETENESS,
        authoring_rules.TEST_SEMANTIC_DECAY,
        authoring_rules.PLACEHOLDER_ASSERTION,
    )


def test_every_allowlist_entry_satisfies_rule_protocol() -> None:
    for rule in authoring_rules.RULE_ALLOWLIST:
        assert isinstance(rule, Rule)


def test_reexports_kernel_protocol_surface() -> None:
    assert authoring_rules.Rule is Rule
    assert authoring_rules.RuleContext is RuleContext
    assert authoring_rules.RuleResult is RuleResult


def test_dunder_all_is_explicit() -> None:
    assert set(authoring_rules.__all__) == {
        "EXPORTS_COMPLETENESS",
        "PLACEHOLDER_ASSERTION",
        "RULE_ALLOWLIST",
        "Rule",
        "RuleContext",
        "RuleResult",
        "TEST_SEMANTIC_DECAY",
    }
