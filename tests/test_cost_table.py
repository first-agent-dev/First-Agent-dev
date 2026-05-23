"""Cost-table lookup (ADR-9 §4 cost+token accounting)."""

from __future__ import annotations

from fa.observability.cost_table import CostPerMillion, lookup


def test_lookup_returns_known_entry() -> None:
    price = lookup("deepseek", "openrouter", "deepseek/deepseek-chat-v3")
    assert price is not None
    assert isinstance(price, CostPerMillion)
    assert price.input_usd_per_million > 0
    assert price.output_usd_per_million > 0


def test_lookup_returns_none_on_miss() -> None:
    assert lookup("unknown-family", "openrouter", "unknown-slug") is None


def test_lookup_distinguishes_per_provider_pricing_for_same_family() -> None:
    openrouter = lookup("deepseek", "openrouter", "deepseek/deepseek-chat-v3")
    fireworks = lookup("deepseek", "fireworks", "accounts/fireworks/models/deepseek-v3")
    assert openrouter is not None
    assert fireworks is not None
    assert openrouter != fireworks
