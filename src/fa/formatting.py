"""Shared display formatting helpers.

Extracted to avoid copy-paste duplication between :mod:`fa.output`
(live console renderer) and :mod:`fa.stats` (post-hoc analytics).
Zero dependencies beyond stdlib.
"""

from __future__ import annotations

__all__ = [
    "fmt_tokens",
]


def fmt_tokens(n: int) -> str:
    """Format a token count for human display: ``1200 → '1.2k'``."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)
