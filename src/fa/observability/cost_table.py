"""Provider x model pricing lookup (ADR-9 §4 cost+token accounting).

The Tier-1 ``llm_call`` observability row's ``cost_usd`` is computed
by multiplying the successful chain attempt's ``in_tokens`` /
``out_tokens`` (read from the provider ``usage`` block, normalised
into :class:`fa.providers.base.ResponseInfo` by the adapter) by the
pricing entry returned from :func:`lookup`. Misses return ``None``,
which the inner-loop runtime translates into a
``cost_estimate_missing`` warning row + ``cost_usd: null`` payload
(see ADR-9 §4 last paragraph). :class:`fa.observability.cost_guardian.CostGuardian`
tolerates ``None`` by treating it as zero plus a flag on the rolling
tally, so a pricing-table-miss never silently breaks the budget gate.

The seed table is intentionally small (a handful of canonical
provider-x-slug rows for the default chains in ``~/.fa/models.yaml``);
amendments add rows as new providers land. The lookup key is
``(family, provider, slug)`` so the same model identity on multiple
providers carries the provider-specific price (Fireworks vs Groq vs
OpenRouter vs NVIDIA Build all price the same DeepSeek-v3 weights
differently).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostPerMillion:
    """Pricing entry: USD per million input / output tokens."""

    input_usd_per_million: float
    output_usd_per_million: float


# Seed table — append by amendment as new providers land per ADR-9 §5
# closing note. Pricing snapshots are from each provider's public
# price page as of the ADR-9 landing date; stale pricing surfaces as
# the ``cost_estimate_missing`` rate on the Tier-1 observability row.
_COST_TABLE: dict[tuple[str, str, str], CostPerMillion] = {
    ("deepseek", "openrouter", "deepseek/deepseek-chat-v3"): CostPerMillion(0.27, 1.10),
    ("deepseek", "fireworks", "accounts/fireworks/models/deepseek-v3"): CostPerMillion(0.90, 0.90),
    ("deepseek", "nvidia_build", "deepseek-ai/deepseek-v3"): CostPerMillion(0.0, 0.0),
    ("deepseek", "groq", "deepseek-v3"): CostPerMillion(0.0, 0.0),
    ("kimi", "openrouter", "moonshotai/kimi-k2"): CostPerMillion(0.60, 2.50),
    ("kimi", "groq", "kimi-k2"): CostPerMillion(0.0, 0.0),
    ("qwen", "openrouter", "qwen/qwen-3-32b-instruct"): CostPerMillion(0.10, 0.30),
    ("qwen", "nvidia_build", "qwen/qwen-3-32b"): CostPerMillion(0.0, 0.0),
    ("anthropic", "anthropic", "claude-3-5-sonnet-latest"): CostPerMillion(3.00, 15.00),
}


def lookup(family: str, provider: str, slug: str) -> CostPerMillion | None:
    """Return pricing for ``(family, provider, slug)`` or ``None`` on miss."""

    return _COST_TABLE.get((family, provider, slug))
