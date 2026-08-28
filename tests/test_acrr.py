"""S5 — read amplification: pure function, distinct-path counting, migration, display.

Test classes:
  C0  compute_read_amplification in isolation (pure, exact oracles)
  C1  the real export path — real EventLog, real sqlite file, real renderer

The C1 tests deliberately avoid mocking the store or the log. The defects this
slice is guarding against (a no-op migration, non-distinct counting, a ratio
rendered from the wrong column) all live in the seams between those real
components, so a mock would test the wrong thing.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from fa.inner_loop.acrr import compute_read_amplification
from fa.inner_loop.global_history import (
    GlobalHistoryStore,
    _extract_telemetry_from_log,
    build_export_row,
)

# ─────────────────────────── C0: the pure function ───────────────────────────


def test_acrr_equal_counts_is_one() -> None:
    """Read exactly what you changed — the optimal case, ratio 1.0."""
    assert compute_read_amplification(5, 5) == 1.0


def test_acrr_over_reading() -> None:
    """20 files read to change 2 is a 10x over-read."""
    assert compute_read_amplification(20, 2) == 10.0


def test_acrr_zero_is_none() -> None:
    """KILL-CHECK anchor: read 10, changed nothing -> None, never 10.0.

    If this is ever reverted to ``max(files_changed, 1)``, pure unproductive
    exploration becomes numerically identical to a healthy run that changed one
    file, and the metric stops being able to express the one condition it
    exists to detect.
    """
    assert compute_read_amplification(10, 0) is None


def test_acrr_both_zero_is_none() -> None:
    """A run that touched nothing has no ratio, not a ratio of zero."""
    assert compute_read_amplification(0, 0) is None


@pytest.mark.parametrize("read,changed", [(-1, 1), (1, -1), (-1, -1)])
def test_acrr_negative_raises(read: int, changed: int) -> None:
    """A count of files cannot be negative; fail loudly rather than store noise."""
    with pytest.raises(ValueError, match="cannot be negative"):
        compute_read_amplification(read, changed)


def test_acrr_returns_float_not_int() -> None:
    """Guards against integer division sneaking in: 1/2 must be 0.5, not 0."""
    result = compute_read_amplification(1, 2)
    assert result == 0.5
    assert isinstance(result, float)


# ──────────────────── C1: distinct counting on a real log ────────────────────


class _Event:
    """Minimal stand-in matching the attributes EventLog rows expose."""

    def __init__(self, kind: str, tool_name: str = "", content: object = None) -> None:
        self.kind = kind
        self.tool_name = tool_name
        self.content = content
        self.ts = "2026-08-27T00:00:00Z"


class _Log:
    def __init__(self, events: list[_Event]) -> None:
        self._events = events

    def read_all(self) -> list[_Event]:
        return self._events


def _tool_call(name: str, path: str) -> _Event:
    """Shaped exactly like state.py:record_tool_call writes it."""
    return _Event("tool_call", tool_name=name, content={"params": {"path": path}})


def test_files_read_is_distinct() -> None:
    """KILL-CHECK anchor: 3 read calls over 2 unique paths -> files_read == 2.

    Reading one file three times costs one file's worth of context. Counting
    calls instead of paths would report over-reading that never happened.
    """
    log = _Log(
        [
            _tool_call("fs_read_file", "a.py"),
            _tool_call("fs_read_file", "a.py"),
            _tool_call("fs_read_file", "b.py"),
            _tool_call("fs_write_file", "c.py"),
        ]
    )
    telemetry = _extract_telemetry_from_log(log)
    assert telemetry["files_read"] == 2, "3 calls over 2 paths must count as 2"
    assert telemetry["files_changed"] == 1


def test_write_and_edit_on_same_path_is_one_change() -> None:
    """Both mutating tools feed one set, so write-then-edit is a single file."""
    log = _Log(
        [
            _tool_call("fs_write_file", "c.py"),
            _tool_call("fs_edit_file", "c.py"),
        ]
    )
    telemetry = _extract_telemetry_from_log(log)
    assert telemetry["files_changed"] == 1


def test_edit_alone_counts_as_a_change() -> None:
    """fs_edit_file is a mutation in its own right, with no write beside it.

    Added after mutation testing: dropping ``fs_edit_file`` from the change-tool
    set left the write-then-edit test green, because the write alone already
    produced a count of 1. Only an edit-ONLY log discriminates.
    """
    log = _Log([_tool_call("fs_edit_file", "only_edited.py")])
    telemetry = _extract_telemetry_from_log(log)
    assert telemetry["files_changed"] == 1, "an edit with no write must still count"


def test_non_file_tools_do_not_count() -> None:
    """A bash call is not a file read, even though it is a tool call."""
    log = _Log(
        [
            _tool_call("fs_read_file", "a.py"),
            _Event("tool_call", tool_name="bash", content={"params": {"cmd": "ls"}}),
        ]
    )
    telemetry = _extract_telemetry_from_log(log)
    assert telemetry["files_read"] == 1
    assert telemetry["tool_calls_total"] == 2, "both still count as tool calls"


def test_malformed_tool_call_does_not_crash_export() -> None:
    """A path-less or oddly-shaped call contributes nothing and never raises.

    Telemetry extraction is on the export hot path; a malformed event must not
    take down the run's whole projection.
    """
    log = _Log(
        [
            _Event("tool_call", tool_name="fs_read_file", content=None),
            _Event("tool_call", tool_name="fs_read_file", content={"params": {}}),
            _Event("tool_call", tool_name="fs_read_file", content={"params": {"path": ""}}),
            _tool_call("fs_read_file", "real.py"),
        ]
    )
    telemetry = _extract_telemetry_from_log(log)
    assert telemetry["files_read"] == 1


def test_build_export_row_computes_acrr() -> None:
    """The ratio is computed at export time and lands in the row."""
    log = _Log(
        [
            _tool_call("fs_read_file", "a.py"),
            _tool_call("fs_read_file", "b.py"),
            _tool_call("fs_read_file", "c.py"),
            _tool_call("fs_read_file", "d.py"),
            _tool_call("fs_write_file", "e.py"),
        ]
    )
    row = build_export_row(run_id="r1", outcome=object(), log=log, role="coder")
    assert row["files_read"] == 4
    assert row["files_changed"] == 1
    assert row["read_amplification"] == 4.0


def test_build_export_row_acrr_none_when_nothing_changed() -> None:
    """An exploration-only run stores NULL, not a fabricated ratio."""
    log = _Log([_tool_call("fs_read_file", "a.py")])
    row = build_export_row(run_id="r2", outcome=object(), log=log, role="chat")
    assert row["read_amplification"] is None


# ─────────────────────── C1: migration on a real sqlite ──────────────────────

_PRE_S5_SCHEMA = """
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    role TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT '',
    family TEXT NOT NULL DEFAULT '',
    exit_code INTEGER NOT NULL,
    stop_reason TEXT NOT NULL,
    turns INTEGER NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_input_tokens INTEGER NOT NULL DEFAULT 0,
    cache_creation_input_tokens INTEGER NOT NULL DEFAULT 0,
    cache_hit_ratio REAL NOT NULL DEFAULT 0.0,
    tool_calls_total INTEGER NOT NULL DEFAULT 0,
    tool_calls_breakdown_json TEXT NOT NULL DEFAULT '{}',
    has_compaction_summary INTEGER NOT NULL DEFAULT 0,
    workspace_root TEXT NOT NULL DEFAULT '',
    duration_ms INTEGER NOT NULL DEFAULT 0,
    scope_estimate_json TEXT NOT NULL DEFAULT '{}'
);
"""


def test_pre_s5_db_migrates(tmp_path: Path) -> None:
    """KILL-CHECK anchor: an already-deployed DB gains the three columns.

    ``CREATE TABLE IF NOT EXISTS`` is a no-op against an existing file, so
    without an explicit ALTER every insert on an upgraded install fails with
    "table runs has no column named files_read". Reproduced before the fix was
    written; this pins it shut.
    """
    db_path = tmp_path / "global_history.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_PRE_S5_SCHEMA)
        conn.execute(
            "INSERT INTO runs (run_id, created_at, updated_at, role, exit_code,"
            " stop_reason, turns) VALUES ('legacy', 'x', 'x', 'coder', 0, 'done', 1)"
        )

    store = GlobalHistoryStore(db_path=db_path)  # opening runs the migration

    with sqlite3.connect(db_path) as conn:
        cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(runs);").fetchall()}
    assert {"files_read", "files_changed", "read_amplification"} <= cols

    # and the insert that used to fail now succeeds
    store.export_run(
        {
            "run_id": "new",
            "role": "coder",
            "exit_code": 0,
            "stop_reason": "done",
            "turns": 1,
            "files_read": 4,
            "files_changed": 2,
            "read_amplification": 2.0,
        }
    )
    rows = {r["run_id"]: r for r in store.read_all()}
    assert rows["new"]["read_amplification"] == 2.0
    assert rows["legacy"]["files_read"] == 0, "legacy row backfills to the default"


def test_legacy_row_acrr_is_null_not_zero(tmp_path: Path) -> None:
    """A pre-S5 run has an UNKNOWN ratio, which is not the same as 0.0.

    ``read_amplification`` is NULLable with no DEFAULT for exactly this reason:
    a ``DEFAULT 0.0`` would claim every historical run had a perfect ratio.

    A pre-S5 schema has no ratio column at all, so S8's migration ADDs one; it
    must arrive NULL rather than invent a value.
    """
    db_path = tmp_path / "global_history.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_PRE_S5_SCHEMA)
        conn.execute(
            "INSERT INTO runs (run_id, created_at, updated_at, role, exit_code,"
            " stop_reason, turns) VALUES ('legacy', 'x', 'x', 'coder', 0, 'done', 1)"
        )
    GlobalHistoryStore(db_path=db_path)
    with sqlite3.connect(db_path) as conn:
        value = conn.execute("SELECT read_amplification FROM runs WHERE run_id='legacy'").fetchone()[0]
    assert value is None, "migration must not fabricate a ratio for a row that never had one"


def test_migration_is_idempotent(tmp_path: Path) -> None:
    """Opening the store repeatedly must not fail on duplicate columns."""
    db_path = tmp_path / "global_history.db"
    for _ in range(3):
        GlobalHistoryStore(db_path=db_path)
    with sqlite3.connect(db_path) as conn:
        cols = [str(r[1]) for r in conn.execute("PRAGMA table_info(runs);").fetchall()]
    assert cols.count("files_read") == 1


def test_none_acrr_round_trips_as_null(tmp_path: Path) -> None:
    """None must reach sqlite as NULL and come back as None, not 0.0."""
    store = GlobalHistoryStore(db_path=tmp_path / "gh.db")
    store.export_run(
        {
            "run_id": "explore",
            "role": "chat",
            "exit_code": 0,
            "stop_reason": "done",
            "turns": 1,
            "files_read": 7,
            "files_changed": 0,
            "read_amplification": None,
        }
    )
    row = store.read_all()[0]
    assert row["read_amplification"] is None
    assert row["files_read"] == 7


# ───────────────────────── C1: the stats render line ─────────────────────────


def test_acrr_in_stats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """KILL-CHECK anchor: `fa stats --global-history` prints the ACRR line."""
    import argparse

    from fa.cli import _cmd_stats_global_history

    monkeypatch.setenv("FA_STATE_ROOT", str(tmp_path))
    from fa.inner_loop.global_history import default_global_history_path

    store = GlobalHistoryStore(db_path=default_global_history_path())
    store.export_run(
        {
            "run_id": "run-a",
            "role": "coder",
            "exit_code": 0,
            "stop_reason": "done",
            "turns": 3,
            "files_read": 20,
            "files_changed": 2,
            "read_amplification": 10.0,
        }
    )
    args = argparse.Namespace(output="console", run_id=None, since=None)
    assert _cmd_stats_global_history(args) == 0

    err = capsys.readouterr().err
    assert "read amplification: 10.00" in err
    assert "files_read=20" in err
    assert "files_changed=2" in err


def test_acrr_na_rendering(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """A NULL ratio renders as explicit n/a text, never as 0.00 or 'None'."""
    import argparse

    from fa.cli import _cmd_stats_global_history
    from fa.inner_loop.global_history import default_global_history_path

    monkeypatch.setenv("FA_STATE_ROOT", str(tmp_path))
    store = GlobalHistoryStore(db_path=default_global_history_path())
    store.export_run(
        {
            "run_id": "run-b",
            "role": "chat",
            "exit_code": 0,
            "stop_reason": "done",
            "turns": 1,
            "files_read": 5,
            "files_changed": 0,
            "read_amplification": None,
        }
    )
    args = argparse.Namespace(output="console", run_id=None, since=None)
    assert _cmd_stats_global_history(args) == 0

    err = capsys.readouterr().err
    assert "read amplification: n/a (no files changed)" in err
    assert "0.00" not in err


def test_acrr_json_goes_to_stdout_not_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The S10b stream split still holds: JSON on stdout, carrying the new fields.

    The ACRR line is stderr-only, so it must not leak into the stdout JSON that
    downstream pipelines parse.
    """
    import argparse
    import json

    from fa.cli import _cmd_stats_global_history
    from fa.inner_loop.global_history import default_global_history_path

    monkeypatch.setenv("FA_STATE_ROOT", str(tmp_path))
    store = GlobalHistoryStore(db_path=default_global_history_path())
    store.export_run(
        {
            "run_id": "run-c",
            "role": "coder",
            "exit_code": 0,
            "stop_reason": "done",
            "turns": 2,
            "files_read": 6,
            "files_changed": 3,
            "read_amplification": 2.0,
        }
    )
    args = argparse.Namespace(output="json", run_id=None, since=None)
    assert _cmd_stats_global_history(args) == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload[0]["read_amplification"] == 2.0
    assert payload[0]["files_read"] == 6
    assert "read amplification:" not in captured.out, "the human line must stay on stderr"
