"""Shared data types for the provider chain (ADR-9).

Separated from ``chain.py`` and ``errors.py`` to break the circular
dependency that would arise if ``ProviderChainExhaustedError`` needed
to reference ``ChainAttemptRecord`` at definition time while
``chain.py`` imports from ``errors.py``.

Dependency graph::

    types.py  ← chain.py   (producer — creates records)
    types.py  ← errors.py  (carrier  — typed attempts list)
    types.py  ← cli.py     (consumer — reads records in fa probe)
    types.py  ← coder_loop (consumer — logs records on exhaustion)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChainAttemptRecord:
    """Per-attempt trace row consumed by the Tier-1 / Tier-2 observability surface."""

    provider: str
    slug: str
    status: int
    ms: int
    error: str | None


__all__ = ["ChainAttemptRecord"]
