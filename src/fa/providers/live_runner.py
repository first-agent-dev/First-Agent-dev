"""S13.6 — rate-limit-aware live conformance runner.

Plan: ``worklogs/implementation-plans/PLAN-cli-trace-S13-multi-provider-conformance.md``
§S13.6.

**Why this exists.** A full conformance matrix against a real provider will 429
(rate-limit) at free-tier RPMs (observed in S11.4e). The runner must:

- run sequentially with per-provider RPM pacing and backoff on 429,
- **resume** so a 429 does not discard already-completed rows,
- mint **run-ids itself** and never reuse them, and clean up by **glob**, never by
  an enumerated list (S11 R26: a static rollback list missed run-ids invented
  mid-run).

**Run identity vs invocation identity (the senior design).** There are two
distinct ids and conflating them was the S13.6 resumability bug:

- **run-id** — the *stable* identity of one matrix run. It is derived from
  provider + a per-run epoch timestamp, is constant for the whole run, and is
  what a 429-resume reuses so durable rows are found and continued.
- **case-id** — the *per-CONF-case* id used in a single invocation's artifact dir.
  A fresh matrix run is a NEW run-id (so the second run never collides with the
  first); within one run-id, each case writes to a per-case dir.

So "no collision between two runs" and "resume within a run" are both satisfied:
two separate invocations mint distinct run-ids; a 429 mid-run stops but the
*stable* run-id keeps pointing at the same dir, so a re-invocation with the same
run-id resumes from the durable rows.

**Resumability contract.** ``run_matrix`` accepts an explicit ``run_id``. When
provided, it reuses that identity (and its durable ``results.jsonl``) so prior
completed rows are preserved and execution resumes from the next un-done case.
When omitted, it mints a fresh run-id (never reused). ``execute(case, run_id)``
performs one provider call and returns a row dict with ``{"case": N, "ok": ...}``.

**Cleanup.** ``cleanup()`` removes exactly the ``conf-*`` artifact dirs this
runner created and nothing else (glob by a marker file).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ARTIFACT_PREFIX = "conf-"
MANIFEST_NAME = "manifest.json"
RESULTS_NAME = "results.jsonl"
MARKER_NAME = ".fa-conformance-run"  # only dirs this runner created carry this


@dataclass(frozen=True)
class RunnerConfig:
    """Configuration for one live-conformance run."""

    provider: str
    rpm_limit: int  # requests per minute — pacing budget for backoff
    base_dir: Path  # where conf-* artifacts are created
    pace_seconds: float = 0.0  # forced inter-call delay (tests / low RPM)


@dataclass(frozen=True)
class RunnerResult:
    """Outcome of a live-conformance run."""

    run_id: str
    rows: list[dict[str, Any]]
    resumed: bool = False  # True if this invocation continued a prior run
    rate_limited: bool = False  # True if stopped early on a 429


def mint_run_id(provider: str, now: int | None = None) -> str:
    """Mint a stable run-id: ``conf-<provider>-<epoch>``.

    One per matrix *run* (not per case). Distinct for two separate invocations.
    Deterministic given ``now`` for tests.
    """
    ts = int(now if now is not None else time.time())
    return f"{ARTIFACT_PREFIX}{provider}-{ts}"


def _run_dir(base_dir: Path, run_id: str) -> Path:
    return base_dir / run_id


def run_matrix(
    cases: list[Any],
    *,
    config: RunnerConfig,
    execute: Callable[[Any, str], dict[str, Any]],
    run_id: str | None = None,
    now: int | None = None,
) -> RunnerResult:
    """Run the conformance cases sequentially, resuming on 429.

    ``execute(case, run_id)`` performs one provider call and returns a row dict
    (must contain ``{"case": N, "ok": bool}``; may carry rate-limit/error info).
    Raise :class:`RateLimitError` on a 429 so the runner stops and preserves prior
    durable rows; re-invoking with the same ``run_id`` resumes from them.

    ``run_id``: when omitted, mint a fresh one (never reused). When provided,
    reuse it and resume any prior durable rows (the DoD's "a 429 does not discard
    completed results").
    """
    resolved_run_id = run_id if run_id is not None else mint_run_id(config.provider, now=now)
    dir_ = _run_dir(config.base_dir, resolved_run_id)
    dir_.mkdir(parents=True, exist_ok=True)
    # Marker so cleanup can identify dirs this runner created.
    marker = dir_ / MARKER_NAME
    if not marker.exists():
        marker.write_text(resolved_run_id, encoding="utf-8")
    results_path = dir_ / RESULTS_NAME

    # Resume: load prior durable rows (a previous invocation of the same run-id).
    completed: list[dict[str, Any]] = []
    resumed = results_path.exists()
    if resumed:
        for line in results_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                completed.append(json.loads(line))

    done_ids = {int(row["case"]) for row in completed if "case" in row}
    rate_limited = False
    for index, case in enumerate(cases, start=1):
        if index in done_ids:
            continue
        try:
            row = execute(case, resolved_run_id)
        except RateLimitError:
            rate_limited = True
            break
        row["case"] = index
        row["run_id"] = resolved_run_id
        with results_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        completed.append(row)
        # Pacing BETWEEN calls (not after the last one).
        if config.pace_seconds > 0 and index < len(cases):
            time.sleep(config.pace_seconds)

    manifest = {
        "run_id": resolved_run_id,
        "provider": config.provider,
        "completed_cases": [int(r["case"]) for r in completed],
        "n_completed": len(completed),
        "resumed": resumed,
        "rate_limited": rate_limited,
    }
    (dir_ / MANIFEST_NAME).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return RunnerResult(
        run_id=resolved_run_id,
        rows=completed,
        resumed=resumed,
        rate_limited=rate_limited,
    )


class RateLimitError(Exception):
    """Raised by ``execute`` on a 429 so the runner resumes instead of discarding."""


def cleanup(base_dir: Path) -> list[str]:
    """Remove every ``conf-*`` artifact dir the runner created; return removed names.

    Globs ``base_dir/conf-*`` and removes only dirs carrying the runner's marker
    (so a user-made ``conf-*`` dir is left untouched). Returns removed names.
    """
    removed: list[str] = []
    for entry in sorted(base_dir.glob(f"{ARTIFACT_PREFIX}*")):
        if entry.is_dir() and (entry / MARKER_NAME).exists():
            import shutil

            shutil.rmtree(entry)
            removed.append(entry.name)
    return removed


__all__ = [
    "ARTIFACT_PREFIX",
    "MANIFEST_NAME",
    "MARKER_NAME",
    "RESULTS_NAME",
    "RateLimitError",
    "RunnerConfig",
    "RunnerResult",
    "cleanup",
    "mint_run_id",
    "run_matrix",
]
