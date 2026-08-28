"""S10.6 — calibration success_rate + reliability flag (CT8, DP-6, G9).

class=C0 (pure report) + C2 (CLI --calibration). Oracle=exact fields.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from fa.calibration import CalibrationBucket, CalibrationReport, build_calibration_report, mode_from_row
from fa.inner_loop.global_history import GlobalHistoryStore


def _row(mode: str, exit_code: int, acrr: float | None = None) -> dict[str, Any]:
    return {
        "exit_code": exit_code,
        "acrr": acrr,
        "scope_estimate_json": json.dumps({"recommended_mode": mode}),
    }


def _report(
    rows: list[dict[str, Any]], *, epsilon: float = 0.05, min_flag_runs: int = 10, gate: bool = False
) -> CalibrationReport:
    return build_calibration_report(rows, epsilon=epsilon, min_flag_runs=min_flag_runs, gate_enabled=gate)


def _bucket(report: CalibrationReport, mode: str) -> CalibrationBucket:
    for b in report.buckets:
        if b.recommended_mode == mode:
            return b
    raise AssertionError(f"no bucket for {mode}")


# ── success_rate over ALL runs ─────────────────────────────────────────────


def test_all_failed_mode_shows_zero_rate() -> None:
    rows = [_row("chat_direct", exit_code=1) for _ in range(12)]
    report = _report(rows)
    b = _bucket(report, "chat_direct")
    assert b.runs_total == 12
    assert b.runs_succeeded == 0
    assert b.success_rate == 0.0
    assert b.below_reliability_target is True


def test_success_rate_counts_failures_in_denominator() -> None:
    rows = [_row("chat_direct", 0, acrr=1.0)] * 7 + [_row("chat_direct", 1)] * 3
    report = _report(rows)
    b = _bucket(report, "chat_direct")
    assert b.runs_total == 10
    assert b.runs_succeeded == 7
    assert abs(b.success_rate - 0.7) < 1e-9


def test_all_succeed_rate_one() -> None:
    rows = [_row("workflow_linear", 0, acrr=2.0) for _ in range(10)]
    report = _report(rows)
    b = _bucket(report, "workflow_linear")
    assert b.success_rate == 1.0
    assert b.below_reliability_target is False


# ── ACRR stays successful-only (Q22) ───────────────────────────────────────


def test_acrr_aggregates_exclude_failed_runs() -> None:
    rows = [_row("chat_direct", 0, acrr=2.0), _row("chat_direct", 0, acrr=4.0), _row("chat_direct", 1)]
    report = _report(rows)
    b = _bucket(report, "chat_direct")
    assert b.acrr_mean == 3.0
    assert b.acrr_min == 2.0
    assert b.acrr_max == 4.0


def test_successful_run_without_acrr_counted_in_rate() -> None:
    rows = [_row("chat_direct", 0, acrr=None)] * 5
    report = _report(rows)
    b = _bucket(report, "chat_direct")
    assert b.runs_succeeded == 5
    assert b.success_rate == 1.0
    assert b.acrr_mean is None
    assert report.skipped_without_acrr == 5


# ── epsilon boundary, both sides ───────────────────────────────────────────


def test_epsilon_boundary_just_above_target_not_flagged() -> None:
    # rate = 0.96 >= 1 - 0.05 = 0.95 -> not flagged
    rows = [_row("chat_direct", 0, acrr=1.0)] * 96 + [_row("chat_direct", 1)] * 4
    report = _report(rows, epsilon=0.05, min_flag_runs=10)
    b = _bucket(report, "chat_direct")
    assert abs(b.success_rate - 0.96) < 1e-9
    assert b.below_reliability_target is False


def test_epsilon_boundary_just_below_target_flagged() -> None:
    # rate = 0.94 < 0.95 -> flagged
    rows = [_row("chat_direct", 0, acrr=1.0)] * 94 + [_row("chat_direct", 1)] * 6
    report = _report(rows, epsilon=0.05, min_flag_runs=10)
    b = _bucket(report, "chat_direct")
    assert abs(b.success_rate - 0.94) < 1e-9
    assert b.below_reliability_target is True


def test_epsilon_toggle_changes_flag() -> None:
    # 0.90 rate: flagged at epsilon=0.05 (target .95), not at epsilon=0.20 (target .80)
    rows = [_row("chat_direct", 0, acrr=1.0)] * 9 + [_row("chat_direct", 1)]
    report_strict = _report(rows, epsilon=0.05, min_flag_runs=10)
    report_loose = _report(rows, epsilon=0.20, min_flag_runs=10)
    assert _bucket(report_strict, "chat_direct").below_reliability_target is True
    assert _bucket(report_loose, "chat_direct").below_reliability_target is False


# ── min sample gate: n < min_flag_runs shown but never flagged ─────────────


def test_small_sample_shown_not_flagged() -> None:
    rows = [_row("chat_direct", 1)] * 3  # rate 0.0 but only 3 runs
    report = _report(rows, min_flag_runs=10)
    b = _bucket(report, "chat_direct")
    assert b.runs_total == 3
    assert b.success_rate == 0.0
    assert b.below_reliability_target is False


def test_min_flag_runs_boundary_at_exactly_n() -> None:
    # n == min_flag_runs AND failing -> flagged (>=, not >)
    rows = [_row("chat_direct", 1)] * 10
    report = _report(rows, min_flag_runs=10)
    assert _bucket(report, "chat_direct").below_reliability_target is True
    # n == min_flag_runs - 1 -> not flagged
    report9 = _report(rows[:9], min_flag_runs=10)
    assert _bucket(report9, "chat_direct").below_reliability_target is False


# ── grouping / mode extraction ─────────────────────────────────────────────


def test_modes_bucketed_separately() -> None:
    rows = [_row("chat_direct", 0, acrr=1.0), _row("workflow_linear", 1)]
    report = _report(rows)
    modes = {b.recommended_mode for b in report.buckets}
    assert modes == {"chat_direct", "workflow_linear"}


def test_missing_estimate_groups_separately() -> None:
    row = {"exit_code": 0, "acrr": 1.0, "scope_estimate_json": "{}"}
    assert mode_from_row(row) == "(no estimate)"
    bad = {"exit_code": 0, "acrr": 1.0, "scope_estimate_json": "not json"}
    assert mode_from_row(bad) == "(no estimate)"
    report = _report([row])
    assert _bucket(report, "(no estimate)").success_rate == 1.0


def test_report_dict_carries_parameters() -> None:
    report = _report([_row("chat_direct", 0, acrr=1.0)], epsilon=0.1, min_flag_runs=20, gate=True)
    d = report.to_dict()
    assert d["epsilon_used"] == 0.1
    assert d["min_flag_runs"] == 20
    assert d["chat_escalation_gate"] is True
    assert "calibration" in d


# ── C2: real CLI `fa stats --calibration` ──────────────────────────────────


def _export_mode(store: GlobalHistoryStore, run_id: str, mode: str, exit_code: int, acrr: float | None = None) -> None:
    store.export_run(
        {
            "run_id": run_id,
            "role": "chat",
            "exit_code": exit_code,
            "stop_reason": "done" if exit_code == 0 else "failed",
            "turns": 1,
            "scope_estimate_json": json.dumps({"recommended_mode": mode}),
            "read_amplification": None,
            "acrr": acrr,
        }
    )


def test_cli_calibration_json_fields_and_gate_surfacing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import argparse

    from fa.cli import _cmd_stats_calibration
    from fa.inner_loop.global_history import GlobalHistoryStore, default_global_history_path

    monkeypatch.setenv("FA_STATE_ROOT", str(tmp_path))
    store = GlobalHistoryStore(db_path=default_global_history_path())
    # chat_direct: 8 ok, 4 failed (12 total -> rate 0.667 -> flagged if n>=10)
    for i in range(8):
        _export_mode(store, f"ok-{i}", "chat_direct", 0, acrr=2.0)
    for i in range(4):
        _export_mode(store, f"bad-{i}", "chat_direct", 1)

    args = argparse.Namespace(output="json")
    assert _cmd_stats_calibration(args) == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert "epsilon_used" in payload
    assert "min_flag_runs" in payload
    assert "chat_escalation_gate" in payload
    # gate default is OFF (Q25)
    assert payload["chat_escalation_gate"] is False
    table = {b["recommended_mode"]: b for b in payload["calibration"]}
    cd = table["chat_direct"]
    assert cd["runs_total"] == 12
    assert cd["runs_succeeded"] == 8
    assert abs(cd["success_rate"] - round(8 / 12, 4)) < 1e-9
    assert cd["below_reliability_target"] is True


def test_cli_calibration_all_failed_human_shows_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import argparse

    from fa.cli import _cmd_stats_calibration
    from fa.inner_loop.global_history import GlobalHistoryStore, default_global_history_path

    monkeypatch.setenv("FA_STATE_ROOT", str(tmp_path))
    store = GlobalHistoryStore(db_path=default_global_history_path())
    for i in range(12):
        _export_mode(store, f"f-{i}", "chat_direct", 1)

    args = argparse.Namespace(output="human")
    assert _cmd_stats_calibration(args) == 0
    err = capsys.readouterr().err
    assert "success_rate=0.00" in err
    assert "BELOW RELIABILITY TARGET" in err
    assert "chat_escalation_gate: off" in err


def test_cli_calibration_small_sample_not_flagged_human(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import argparse

    from fa.cli import _cmd_stats_calibration
    from fa.inner_loop.global_history import GlobalHistoryStore, default_global_history_path

    monkeypatch.setenv("FA_STATE_ROOT", str(tmp_path))
    store = GlobalHistoryStore(db_path=default_global_history_path())
    # 3 failures only — under min_flag_runs (10): shown, never flagged.
    for i in range(3):
        _export_mode(store, f"s-{i}", "chat_direct", 1)

    args = argparse.Namespace(output="human")
    assert _cmd_stats_calibration(args) == 0
    err = capsys.readouterr().err
    assert "success_rate=0.00" in err
    assert "BELOW RELIABILITY TARGET" not in err
