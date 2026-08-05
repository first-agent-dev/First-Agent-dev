"""S13.6 — rate-limit-aware live runner (C1, offline with an induced 429).

Plan: ``worklogs/implementation-plans/PLAN-cli-trace-S13-multi-provider-conformance.md``
§S13.6 DoD:
1. a matrix run survives an induced 429 without losing prior rows;
2. a second run of the same matrix does not collide with the first;
3. cleanup removes every ``conf-*`` dir it created and nothing else.

The provider call is injected as ``execute`` so the orchestration is tested
offline — no real HTTP, no keys.

**Resumability is keyed by an explicit stable ``run_id``** (the S13.6 resumability
bug fix): a 429 stops the run, the stable run-id keeps pointing at the same dir,
and a re-invocation with the SAME run-id resumes from the durable rows — it does
NOT restart from case 1 in a fresh dir.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from fa.providers.live_runner import (
    MARKER_NAME,
    RateLimitError,
    RunnerConfig,
    RunnerResult,
    cleanup,
    mint_run_id,
    run_matrix,
)


def _mk_case(i: int) -> SimpleNamespace:
    return SimpleNamespace(name=f"case-{i}", case=i)


def _ok_execute(case: Any, run_id: str) -> dict[str, Any]:
    del run_id
    return {"case": getattr(case, "case", 0), "ok": True}


def _config(tmp_path: Path, *, pace_seconds: float = 0.0) -> RunnerConfig:
    return RunnerConfig(
        provider="mistral",
        rpm_limit=10,
        base_dir=tmp_path,
        pace_seconds=pace_seconds,
    )


def test_mints_unique_run_id_across_runs() -> None:
    """C1 — two separate invocations get distinct run-ids (no collision)."""
    a = mint_run_id("mistral", now=1000)
    b = mint_run_id("mistral", now=1001)
    assert a == "conf-mistral-1000"
    assert b == "conf-mistral-1001"
    assert a != b


def test_resumes_after_429_with_same_run_id_keeps_prior_rows(tmp_path: Path) -> None:
    """C1 (DoD 1) — an induced 429 discards nothing, and a resume continues.

    The first invocation 429s after case 1; its stable run-id persists case 1.
    Re-invoking with the SAME run-id must resume from case 2 (reading the durable
    row), not restart from case 1 in a fresh dir.
    """
    run_id = mint_run_id("mistral", now=100)
    calls: list[int] = []

    def flaky_execute(case: Any, rid: str) -> dict[str, Any]:
        del rid
        n = getattr(case, "case", 0)
        calls.append(n)
        if n == 2:
            raise RateLimitError("429 rate limited")
        return {"case": n, "ok": True}

    cases = [_mk_case(i) for i in (1, 2, 3)]
    r1 = run_matrix(cases, config=_config(tmp_path), execute=flaky_execute, run_id=run_id)
    assert isinstance(r1, RunnerResult)
    assert r1.rate_limited is True
    assert r1.resumed is False
    assert [int(r["case"]) for r in r1.rows] == [1]

    # Resume with the SAME run_id and a working executor.
    def good_execute(case: Any, rid: str) -> dict[str, Any]:
        del rid
        return {"case": getattr(case, "case", 0), "ok": True}

    r2 = run_matrix(cases, config=_config(tmp_path), execute=good_execute, run_id=run_id)
    assert r2.resumed is True
    # It continued from case 2, and case 1 was loaded from the durable row.
    assert sorted(int(r["case"]) for r in r2.rows) == [1, 2, 3]
    # Both runs share the SAME run-id dir (the resume reused it).
    assert r2.run_id == r1.run_id == run_id


def test_second_run_does_not_collide_when_run_id_omitted(tmp_path: Path) -> None:
    """C1 (DoD 2) — omitting run_id mints a fresh id; no collision."""
    cases = [_mk_case(i) for i in (1, 2, 3)]
    r1 = run_matrix(cases, config=_config(tmp_path), execute=_ok_execute, now=100)
    r2 = run_matrix(cases, config=_config(tmp_path), execute=_ok_execute, now=200)
    assert r1.run_id != r2.run_id
    assert (tmp_path / r1.run_id).exists()
    assert (tmp_path / r2.run_id).exists()


def test_cleanup_removes_only_created(tmp_path: Path) -> None:
    """C1 (DoD 3) — cleanup removes every conf-* the runner made and nothing else."""
    cases = [_mk_case(i) for i in (1, 2, 3)]
    run_matrix(cases, config=_config(tmp_path), execute=_ok_execute, now=100)
    run_matrix(cases, config=_config(tmp_path), execute=_ok_execute, now=200)

    (tmp_path / "unrelated.txt").write_text("keep me", encoding="utf-8")
    (tmp_path / "conf-something-user-made").mkdir()  # no marker

    removed = cleanup(tmp_path)
    assert len(removed) == 2
    assert (tmp_path / "unrelated.txt").exists()
    assert (tmp_path / "conf-something-user-made").exists()  # untouched
    # marker files gone with their dirs
    assert not any((tmp_path / r).exists() for r in removed)


def test_pacing_sleeps_between_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C1 — per-provider pacing sleeps between calls when pace_seconds > 0."""
    import time as _time

    sleeps: list[float] = []
    monkeypatch.setattr(_time, "sleep", lambda s: sleeps.append(s))

    cases = [_mk_case(i) for i in (1, 2, 3)]
    run_matrix(cases, config=_config(tmp_path, pace_seconds=0.05), execute=_ok_execute, now=100)
    # 3 cases -> 2 inter-call sleeps (not after the last).
    assert len(sleeps) == 2
    assert all(s == 0.05 for s in sleeps)


def test_manifest_and_marker_written(tmp_path: Path) -> None:
    """C1 — a run writes the manifest + marker (the cleanup/discovery contract)."""
    cases = [_mk_case(i) for i in (1, 2, 3)]
    r = run_matrix(cases, config=_config(tmp_path), execute=_ok_execute, now=100)
    run_dir = tmp_path / r.run_id
    assert (run_dir / MARKER_NAME).exists()
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "results.jsonl").exists()
