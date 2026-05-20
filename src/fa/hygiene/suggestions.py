"""Hint-builder for an audit report (R-13).

Ports Gortex ``internal/audit/audit.go:185-199`` (15 LOC) — turns
the raw report counters into 1-3 short human-readable hints. The
function is deliberately deterministic and side-effect-free so it
plugs into ``fa audit`` (future CLI command) without coupling to
any specific output formatter.
"""

from __future__ import annotations

from dataclasses import dataclass

_BLOAT_THRESHOLD: int = 60


@dataclass(frozen=True)
class AuditReport:
    """Raw counters one audit pass produces.

    Field semantics mirror Gortex ``internal/audit/audit.go``:

    - ``stale_symbol_refs`` — count of backticked identifiers in
      agent docs that do not resolve in the source tree.
    - ``bloat_score`` — composite 0-100 score; ≥ 60 triggers
      "configs bloated" hint.
    - ``probed_paths`` — paths the discover step actually checked
      (length, not the paths themselves, drives the hint).
    """

    stale_symbol_refs: int
    bloat_score: int
    probed_paths: int


def build_suggestions(report: AuditReport) -> list[str]:
    """Return 1-3 short hints for ``report``.

    Order is stable across calls: stale refs first (most actionable),
    bloat second, then the catch-all "config looks clean" when no
    other hint fires. At most three hints are returned per Gortex
    reference behaviour — callers can render them as a single line.
    """

    hints: list[str] = []
    if report.stale_symbol_refs > 0:
        hints.append("Remove stale symbol references")
    if report.bloat_score >= _BLOAT_THRESHOLD:
        hints.append("Config files are bloated (score >=60)")
    if not hints:
        hints.append("Config looks clean.")
    return hints


__all__ = ["AuditReport", "build_suggestions"]
