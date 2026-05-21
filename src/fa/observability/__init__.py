"""Observability surface — :mod:`fa.observability`.

A thin package for hooks that accumulate per-call cost / token
rollups + later (Wave-3+) insight-extractor / anti-pattern catalog
landings (R-10 / R-32). Lives outside ``inner_loop/hooks/`` because
the observability hooks are not part of the deterministic loop
substrate — they sit on top of the runtime and read its outputs.

First entry: :class:`CostGuardian` (Wave-3 R-45).
"""

from __future__ import annotations

from fa.observability.cost_guardian import (
    COST_ARTIFACT_PREFIX,
    CostExtractor,
    CostGuardian,
    CostObservation,
    CostRollup,
    default_cost_extractor,
)

__all__ = [
    "COST_ARTIFACT_PREFIX",
    "CostExtractor",
    "CostGuardian",
    "CostObservation",
    "CostRollup",
    "default_cost_extractor",
]
