"""Routing-calibration reliability table — pure core (S10.6 / CT8, DP-6).

The estimator is scored against what actually happened (Q22). This module
turns the cross-run global-history projection rows into a per
``recommended_mode`` reliability table:

  * ``runs_total``      — ALL runs bucketed into the mode (success + failure);
  * ``runs_succeeded``  — runs with exit code 0;
  * ``success_rate``    — runs_succeeded / runs_total (0.0 when all failed);
  * ``below_reliability_target`` — flagged only when the sample is large
    enough (``runs_total >= min_flag_runs``) AND the rate misses the target
    by more than ``epsilon`` (``rate < 1 - epsilon``). Below the minimum
    sample the number is shown but never flagged, so a single bad run does
    not cry wolf.

ACRR stats remain **successful-run only** (Q22): a cheap failure is not an
efficiency. This module is display-only — nothing here feeds a runtime
gate; the epsilon / minimum-sample are code variables the caller supplies.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

__all__ = [
    "CalibrationBucket",
    "CalibrationReport",
    "build_calibration_report",
    "mode_from_row",
]


@dataclass(frozen=True)
class CalibrationBucket:
    """One recommended_mode row of the calibration table."""

    recommended_mode: str
    runs_total: int
    runs_succeeded: int
    success_rate: float
    acrr_mean: float | None
    acrr_min: float | None
    acrr_max: float | None
    below_reliability_target: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommended_mode": self.recommended_mode,
            "runs_total": self.runs_total,
            "runs_succeeded": self.runs_succeeded,
            "success_rate": round(self.success_rate, 4),
            "acrr_mean": None if self.acrr_mean is None else round(self.acrr_mean, 4),
            "acrr_min": None if self.acrr_min is None else round(self.acrr_min, 4),
            "acrr_max": None if self.acrr_max is None else round(self.acrr_max, 4),
            "below_reliability_target": self.below_reliability_target,
        }


@dataclass(frozen=True)
class CalibrationReport:
    """The whole calibration view: table + the parameters used to build it."""

    buckets: tuple[CalibrationBucket, ...]
    skipped_without_acrr: int
    epsilon: float
    min_flag_runs: int
    gate_enabled: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "calibration": [b.to_dict() for b in self.buckets],
            "epsilon_used": self.epsilon,
            "min_flag_runs": self.min_flag_runs,
            "chat_escalation_gate": self.gate_enabled,
            "skipped_without_acrr": self.skipped_without_acrr,
        }

    def flagged_modes(self) -> tuple[CalibrationBucket, ...]:
        return tuple(b for b in self.buckets if b.below_reliability_target)


def mode_from_row(row: Mapping[str, Any]) -> str:
    """Extract the recommended_mode from a global-history row.

    Reads ``scope_estimate_json`` (the S3.5 projection); unknown/absent
    estimates group under ``(no estimate)``.
    """
    raw_scope = str(row.get("scope_estimate_json") or "{}")
    try:
        parsed = json.loads(raw_scope)
        if isinstance(parsed, dict):
            mode = str(parsed.get("recommended_mode", "") or "")
            return mode or "(no estimate)"
    except (TypeError, ValueError):
        pass
    return "(no estimate)"


def build_calibration_report(
    rows: Iterable[Mapping[str, Any]],
    *,
    epsilon: float,
    min_flag_runs: int,
    gate_enabled: bool,
) -> CalibrationReport:
    """Bucket ALL runs per recommended_mode and score reliability.

    Args:
        rows: iterable of global-history row mappings (each carrying
            ``exit_code``, ``acrr``, ``scope_estimate_json``).
        epsilon: tolerance; the target is ``1 - epsilon``.
        min_flag_runs: minimum sample for ``below_reliability_target``.
        gate_enabled: the current ``chat_escalation_gate`` value, surfaced
            in the report so the operator sees the live default.

    Failed runs ARE counted in ``runs_total`` (and drag success_rate down);
    only the ACRR aggregates exclude them (Q22).
    """
    # mode -> [total, succeeded, acrr_values]
    totals: dict[str, int] = {}
    succeeded: dict[str, int] = {}
    acrr_by_mode: dict[str, list[float]] = {}
    skipped_without_acrr = 0

    for row in rows:
        mode = mode_from_row(row)
        totals[mode] = totals.get(mode, 0) + 1

        ok = int(row.get("exit_code", 0) or 0) == 0
        if ok:
            succeeded[mode] = succeeded.get(mode, 0) + 1
            acrr_value = row.get("acrr")
            if acrr_value is None:
                skipped_without_acrr += 1
            else:
                acrr_by_mode.setdefault(mode, []).append(float(acrr_value))
        # failed runs never contribute an ACRR (cheap failure != efficiency)

    buckets: list[CalibrationBucket] = []
    for mode in sorted(totals):
        total = totals[mode]
        succ = succeeded.get(mode, 0)
        rate = succ / total if total else 0.0
        acrr_values = acrr_by_mode.get(mode, [])
        acrr_mean = sum(acrr_values) / len(acrr_values) if acrr_values else None
        acrr_min = min(acrr_values) if acrr_values else None
        acrr_max = max(acrr_values) if acrr_values else None

        flagged = total >= min_flag_runs and rate < (1.0 - epsilon)
        buckets.append(
            CalibrationBucket(
                recommended_mode=mode,
                runs_total=total,
                runs_succeeded=succ,
                success_rate=rate,
                acrr_mean=acrr_mean,
                acrr_min=acrr_min,
                acrr_max=acrr_max,
                below_reliability_target=flagged,
            )
        )

    return CalibrationReport(
        buckets=tuple(buckets),
        skipped_without_acrr=skipped_without_acrr,
        epsilon=epsilon,
        min_flag_runs=min_flag_runs,
        gate_enabled=gate_enabled,
    )
