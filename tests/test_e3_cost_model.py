"""S8 / CT11 + CT12 — full E3 cost model, projection columns, calibration view.

Plan: ``worklogs/implementation-plans/PLAN-ADDENDUM-deterministic-routing-S7-S9.md``
§S8.

**What is under test.** ``C = alpha*T_lat + beta*N_tok + gamma*N_tool + delta*N_file``
(E3 Eq. 1), a deterministic floor for a run's own change-set, and
``ACRR = (C_act - C_min)/C_min`` (E3 Eq. 3) — plus the projection columns and the
``fa stats --calibration`` view that make the numbers observable.

**Tests labelled per tests-writing skill:** C0 (cost arithmetic, pure) and C1
(real sqlite file, real schema, real export path — no mocked store).

**Oracles are exact floats, not ranges.** Every expected value below is computed
by hand in the test body from the weights actually in force, so a change to a
coefficient fails loudly instead of drifting inside a tolerance. Where a
constant is the thing under test it is ALSO pinned literally (see
``test_default_weights_are_the_fitted_values``), because a test that derives its
expectation from the constant it is checking cannot fail when that constant
moves — the exact flaw S7's mutation round M7 exposed.
"""

from __future__ import annotations

import dataclasses
import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from fa.inner_loop.acrr import (
    BYTES_PER_TOKEN,
    DEFAULT_WEIGHTS,
    CostWeights,
    compute_acrr,
    compute_cost,
    compute_cost_floor,
    compute_read_amplification,
)

# A deliberately round weight set so hand-computed expectations stay readable.
# Using the paper's numbers here is intentional: the arithmetic must be correct
# for ANY weights, and reusing DEFAULT_WEIGHTS would couple these tests to the
# fitted values that a separate test pins on purpose.
ROUND = CostWeights(alpha=1.0, beta=0.02, gamma=0.5, delta=1.5)


# --------------------------------------------------------------------------
# C0 — Eq. 1 arithmetic
# --------------------------------------------------------------------------


def test_compute_cost_matches_hand_computed_eq1() -> None:
    """C0 — every axis contributes exactly its weighted term."""
    got = compute_cost(10.0, 100, 4, 2, weights=ROUND)
    expected = 1.0 * 10.0 + 0.02 * 100 + 0.5 * 4 + 1.5 * 2  # 10 + 2 + 2 + 3
    assert got == expected == 17.0


def test_file_axis_materially_affects_cost() -> None:
    """T31 (C0) — the delta*N_file term is real.

    Kill-check: delete the ``delta * files`` term from ``compute_cost`` and this
    fails. The assertion is a strict inequality on the DIFFERENCE, so a term
    that is present but multiplied by zero also fails.
    """
    without = compute_cost(0.0, 0, 0, 0, weights=ROUND)
    with_one_file = compute_cost(0.0, 0, 0, 1, weights=ROUND)
    assert with_one_file - without == 1.5


@pytest.mark.parametrize(
    ("axis", "kwargs"),
    [
        ("latency", {"latency_s": -1.0, "tokens": 0, "tool_calls": 0, "files": 0}),
        ("tokens", {"latency_s": 0.0, "tokens": -1, "tool_calls": 0, "files": 0}),
        ("tool_calls", {"latency_s": 0.0, "tokens": 0, "tool_calls": -1, "files": 0}),
        ("files", {"latency_s": 0.0, "tokens": 0, "tool_calls": 0, "files": -1}),
    ],
)
def test_negative_inputs_raise(axis: str, kwargs: dict[str, float]) -> None:
    """C0 — a negative axis would subtract from cost and could invert ACRR's sign."""
    with pytest.raises(ValueError, match="cannot be negative"):
        compute_cost(**kwargs)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# C0 — the fitted weights themselves
# --------------------------------------------------------------------------


def test_default_weights_are_the_fitted_values() -> None:
    """C0 — literal anchor on the fitted constants.

    Derived 2026-08-27 from a measured property of this repo: median
    ``src/*.py`` is 7234 B ~= 1808 tokens, and beta is set so a median file's
    token cost is half its file cost (``0.5 * 1.5 / 1808``).

    Pinned LITERALLY and not recomputed from the formula. A test that asserts
    ``beta == 0.5 * delta / 1808`` passes for any delta, so it would not notice
    the axis balance changing — which is the entire point of the fit.
    """
    assert DEFAULT_WEIGHTS.alpha == 1.0
    assert DEFAULT_WEIGHTS.beta == 0.000415
    assert DEFAULT_WEIGHTS.gamma == 0.1
    assert DEFAULT_WEIGHTS.delta == 1.5
    assert BYTES_PER_TOKEN == 4


def test_weights_are_frozen() -> None:
    """C0 — a cost model mutable mid-comparison is not a cost model."""
    with pytest.raises(dataclasses.FrozenInstanceError, match="cannot assign to field"):
        DEFAULT_WEIGHTS.delta = 99.0  # type: ignore[misc]


def test_fitted_weights_keep_the_file_axis_material() -> None:
    """C0 — the fit's actual purpose, asserted as behaviour.

    The paper's defaults put the file axis at 0.43-2.17% of C on real
    change-sets, numerically erasing "the canonical unit of redundancy". This
    pins that our weights do not. Kill-check: restore beta=0.02 and this fails.
    """
    # A median-sized single-file change, floor-style (no latency).
    tokens, tools, files = 1808, 3, 1
    parts = {
        "tok": DEFAULT_WEIGHTS.beta * tokens,
        "tool": DEFAULT_WEIGHTS.gamma * tools,
        "file": DEFAULT_WEIGHTS.delta * files,
    }
    total = sum(parts.values())
    file_share = parts["file"] / total
    token_share = parts["tok"] / total
    assert file_share > 0.25, f"file axis erased: {file_share:.1%}"
    assert token_share > 0.05, f"token axis erased: {token_share:.1%}"


# --------------------------------------------------------------------------
# C0 — the floor
# --------------------------------------------------------------------------


def test_floor_matches_hand_computed_value() -> None:
    """C0 — floor = beta*(bytes/4 + out) + gamma*(2f+1) + delta*f."""
    workspace = Path(tempfile.mkdtemp())
    (workspace / "a.py").write_bytes(b"x" * 400)  # 400 B -> 100 tokens
    got = compute_cost_floor(["a.py"], workspace, 50, weights=ROUND)
    expected = 0.02 * (100 + 50) + 0.5 * (2 * 1 + 1) + 1.5 * 1
    assert got == expected == 6.0


def test_floor_excludes_latency() -> None:
    """T37 (C0) — the floor has no latency axis at all.

    Kill-check: add ``weights.alpha * something`` to ``compute_cost_floor`` and
    this fails. Asserted structurally — the function takes no latency argument —
    because a floor that moved with wall-clock time would not be deterministic.
    """
    import inspect

    params = set(inspect.signature(compute_cost_floor).parameters)
    assert "latency_s" not in params
    assert "latency" not in params
    # And behaviourally: alpha cannot influence the result.
    workspace = Path(tempfile.mkdtemp())
    (workspace / "a.py").write_bytes(b"x" * 400)
    slow = CostWeights(alpha=1000.0, beta=0.02, gamma=0.5, delta=1.5)
    assert compute_cost_floor(["a.py"], workspace, 50, weights=slow) == compute_cost_floor(
        ["a.py"], workspace, 50, weights=ROUND
    )


def test_absolute_and_relative_paths_resolve_identically() -> None:
    """C0 — recorded params may be either form; both must price the same file."""
    workspace = Path(tempfile.mkdtemp())
    target = workspace / "a.py"
    target.write_bytes(b"x" * 400)
    assert compute_cost_floor([str(target)], workspace, 0, weights=ROUND) == compute_cost_floor(
        ["a.py"], workspace, 0, weights=ROUND
    )


def test_deleted_path_contributes_zero_tokens_and_does_not_crash() -> None:
    """C0 — a file changed then deleted still counts as a file, prices as 0 tokens."""
    workspace = Path(tempfile.mkdtemp())
    got = compute_cost_floor(["gone.py"], workspace, 50, weights=ROUND)
    expected = 0.02 * 50 + 0.5 * 3 + 1.5 * 1  # no content bytes
    assert got == expected


def test_path_outside_workspace_is_not_statted() -> None:
    """C3-flavoured C0 — an escaping path contributes 0 and is never read.

    A recorded path is model-supplied input. The floor must never stat outside
    the workspace root just because a run wrote ``/etc/passwd`` into its params.
    """
    workspace = Path(tempfile.mkdtemp())
    outside = Path(tempfile.mkdtemp()) / "secret.txt"
    outside.write_bytes(b"y" * 8000)
    got = compute_cost_floor([str(outside)], workspace, 0, weights=ROUND)
    expected = 0.5 * 3 + 1.5 * 1  # file + tool axes only, zero tokens
    assert got == expected, "content outside the workspace leaked into the floor"


def test_parent_traversal_is_not_statted() -> None:
    """C3 — ``../`` cannot walk out of the workspace to price a file."""
    parent = Path(tempfile.mkdtemp())
    workspace = parent / "ws"
    workspace.mkdir()
    (parent / "outside.py").write_bytes(b"z" * 8000)
    got = compute_cost_floor(["../outside.py"], workspace, 0, weights=ROUND)
    assert got == 0.5 * 3 + 1.5 * 1


def test_duplicate_paths_collapse() -> None:
    """C0 — a path recorded twice must not inflate its own floor."""
    workspace = Path(tempfile.mkdtemp())
    (workspace / "a.py").write_bytes(b"x" * 400)
    assert compute_cost_floor(["a.py", "a.py"], workspace, 0, weights=ROUND) == compute_cost_floor(
        ["a.py"], workspace, 0, weights=ROUND
    )


def test_floor_rejects_negative_output_tokens() -> None:
    """C0 — same loud-failure contract as the other entry points."""
    with pytest.raises(ValueError, match="cannot be negative"):
        compute_cost_floor([], ".", -1)


# --------------------------------------------------------------------------
# C0 — Eq. 3
# --------------------------------------------------------------------------


def test_acrr_is_zero_when_actual_equals_floor() -> None:
    """C0 — the "optimally lean" identity."""
    assert compute_acrr(10.0, 10.0) == 0.0


def test_acrr_matches_hand_computed_ratio() -> None:
    """C0 — 5x the floor is an ACRR of 4."""
    assert compute_acrr(50.0, 10.0) == 4.0


def test_acrr_is_none_when_floor_is_zero() -> None:
    """C0 — no change-set means no denominator; None, never 0.0."""
    assert compute_acrr(5.0, 0.0) is None
    assert compute_acrr(5.0, -1.0) is None


def test_negative_acrr_is_not_clamped() -> None:
    """T36 (C0) — a sub-floor run is a modelling signal, not an error to hide.

    Kill-check: wrap the return in ``max(0.0, ...)`` and this fails.
    """
    assert compute_acrr(5.0, 10.0) == -0.5


# --------------------------------------------------------------------------
# C0 — read amplification (renamed in S8)
# --------------------------------------------------------------------------


def test_read_amplification_keeps_its_s5_contract() -> None:
    """C0 — the rename is a rename; behaviour is unchanged."""
    assert compute_read_amplification(20, 2) == 10.0
    assert compute_read_amplification(10, 0) is None
    with pytest.raises(ValueError, match="cannot be negative"):
        compute_read_amplification(-1, 1)


def test_old_proxy_name_is_gone() -> None:
    """C0 — no ``acrr_proxy`` identifier survives in the module surface."""
    import fa.inner_loop.acrr as acrr_mod

    assert not hasattr(acrr_mod, "compute_acrr_proxy")
    assert "compute_read_amplification" in acrr_mod.__all__
    assert "compute_acrr_proxy" not in acrr_mod.__all__


# --------------------------------------------------------------------------
# C1 — projection: real sqlite, real schema
# --------------------------------------------------------------------------


def _pre_s8_db(path: Path) -> None:
    """Create an S5-era ``runs`` table — the schema S8 must migrate."""
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE runs (
            run_id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, role TEXT,
            model TEXT, family TEXT, exit_code INTEGER, stop_reason TEXT, turns INTEGER,
            input_tokens INTEGER, output_tokens INTEGER, cache_read_input_tokens INTEGER,
            cache_creation_input_tokens INTEGER, cache_hit_ratio REAL, tool_calls_total INTEGER,
            tool_calls_breakdown_json TEXT, has_compaction_summary INTEGER, workspace_root TEXT,
            duration_ms INTEGER, scope_estimate_json TEXT, files_read INTEGER,
            files_changed INTEGER, acrr_proxy REAL)"""
    )
    conn.execute("INSERT INTO runs (run_id, acrr_proxy, files_read, files_changed) VALUES ('legacy-1', 7.5, 15, 2)")
    conn.commit()
    conn.close()


def test_pre_s8_db_gains_the_new_columns_and_inserts_succeed() -> None:
    """T33 (C1) — migration on a real pre-S8 database file.

    Kill-check: drop the four ``ALTER TABLE`` entries and this fails with
    "table runs has no column named acrr".
    """
    from fa.inner_loop.global_history import GlobalHistoryStore

    db = Path(tempfile.mkdtemp()) / "gh.db"
    _pre_s8_db(db)
    store = GlobalHistoryStore(db_path=db)

    cols = {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(runs)")}
    assert {"read_amplification", "cost_actual", "cost_floor", "acrr"} <= cols

    store.export_run(
        {"run_id": "new-1", "read_amplification": 2.0, "cost_actual": 10.0, "cost_floor": 5.0, "acrr": 1.0}
    )
    stored = {r["run_id"]: r for r in store.read_all()}
    assert stored["new-1"]["acrr"] == 1.0


def test_migration_backfills_read_amplification_from_the_legacy_column() -> None:
    """C1 — S5 rows keep their value under the new name.

    Kill-check: delete the ``RENAME COLUMN`` and this fails — the add-missing
    loop would create an empty ``read_amplification`` and strand the S5 value.
    """
    from fa.inner_loop.global_history import GlobalHistoryStore

    db = Path(tempfile.mkdtemp()) / "gh.db"
    _pre_s8_db(db)
    GlobalHistoryStore(db_path=db)

    cols = {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(runs)")}
    assert "acrr_proxy" not in cols, "the old column name must not survive the rename"
    assert "read_amplification" in cols

    value = sqlite3.connect(db).execute("SELECT read_amplification FROM runs WHERE run_id='legacy-1'").fetchone()[0]
    assert value == 7.5, "the S5 value must travel with the rename, not be dropped"


def test_null_acrr_survives_the_round_trip_as_none() -> None:
    """C1 — NULL means "not computed"; 0.0 would assert a perfect run."""
    from fa.inner_loop.global_history import GlobalHistoryStore

    db = Path(tempfile.mkdtemp()) / "gh.db"
    store = GlobalHistoryStore(db_path=db)
    store.export_run({"run_id": "r", "acrr": None, "cost_floor": None, "read_amplification": None})
    row = store.read_all()[0]
    assert row["acrr"] is None
    assert row["cost_floor"] is None
    assert row["read_amplification"] is None


# --------------------------------------------------------------------------
# C1 — the producer: EventLog -> row
# --------------------------------------------------------------------------


def _log_with_tool_calls(workspace: Path, calls: list[tuple[str, str]]) -> object:
    from fa.inner_loop.state import EventLog

    log = EventLog(path=workspace / "events.jsonl")
    for tool, path in calls:
        log.append(actor="agent", kind="tool_call", tool_name=tool, content={"name": tool, "params": {"path": path}})
    return log


class _Outcome:
    exit_code = 0
    stop_reason = "done"
    turns = 3
    final_text = ""


def test_telemetry_now_carries_changed_paths_not_just_counts() -> None:
    """C1 — the S8 blocker: the extractor used to discard the path strings.

    Kill-check: revert to returning only ``len(changed_paths)`` and this fails.
    """
    from fa.inner_loop.global_history import _extract_telemetry_from_log

    workspace = Path(tempfile.mkdtemp())
    log = _log_with_tool_calls(
        workspace, [("fs_edit_file", "b.py"), ("fs_write_file", "a.py"), ("fs_edit_file", "b.py")]
    )
    telemetry = _extract_telemetry_from_log(log)
    # Sorted and deduplicated, so the exported row is stable across runs.
    assert telemetry["changed_paths"] == ["a.py", "b.py"]
    assert telemetry["files_changed"] == 2


def test_build_export_row_populates_all_four_s8_columns() -> None:
    """C1 — full producer path with a hand-computed floor."""
    from fa.inner_loop.global_history import build_export_row

    workspace = Path(tempfile.mkdtemp())
    (workspace / "a.py").write_bytes(b"x" * 4000)  # 1000 tokens
    (workspace / "b.py").write_bytes(b"y" * 2000)  # 500 tokens
    log = _log_with_tool_calls(
        workspace,
        [
            ("fs_read_file", "a.py"),
            ("fs_read_file", "b.py"),
            ("fs_read_file", "a.py"),
            ("fs_edit_file", "a.py"),
            ("fs_write_file", "b.py"),
        ],
    )
    row = build_export_row(
        run_id="r1", outcome=_Outcome(), log=log, role="chat", workspace_root=workspace, duration_ms=12000
    )

    assert row["files_read"] == 2
    assert row["files_changed"] == 2
    assert row["read_amplification"] == 1.0
    # Floor: 6000 B / 4 = 1500 tokens, tools = 2*2+1 = 5, files = 2.
    expected_floor = DEFAULT_WEIGHTS.beta * 1500 + DEFAULT_WEIGHTS.gamma * 5 + DEFAULT_WEIGHTS.delta * 2
    assert row["cost_floor"] == pytest.approx(expected_floor)
    assert row["acrr"] == pytest.approx((row["cost_actual"] - expected_floor) / expected_floor)


def test_export_row_carries_only_the_new_name() -> None:
    """C1 — the rename is complete: no ``acrr_proxy`` key is produced.

    The dual-write compatibility layer was removed once the only live database
    was confirmed to hold two throwaway rows and no external reader. A row that
    still emitted both names would leave the old identifier alive forever.
    """
    from fa.inner_loop.global_history import build_export_row

    workspace = Path(tempfile.mkdtemp())
    (workspace / "a.py").write_bytes(b"x" * 400)
    log = _log_with_tool_calls(workspace, [("fs_read_file", "a.py"), ("fs_edit_file", "a.py")])
    row = build_export_row(run_id="r", outcome=_Outcome(), log=log, workspace_root=workspace, duration_ms=1000)
    assert row["read_amplification"] == 1.0
    assert "acrr_proxy" not in row


def test_run_that_changed_nothing_gets_null_acrr_not_zero() -> None:
    """C1 — pure exploration has no floor, so ACRR is undefined.

    Kill-check: return 0.0 instead of None from ``compute_acrr`` and this fails.
    """
    from fa.inner_loop.global_history import build_export_row

    workspace = Path(tempfile.mkdtemp())
    (workspace / "a.py").write_bytes(b"x" * 400)
    log = _log_with_tool_calls(workspace, [("fs_read_file", "a.py")])
    row = build_export_row(run_id="r", outcome=_Outcome(), log=log, workspace_root=workspace, duration_ms=1000)
    assert row["files_changed"] == 0
    assert row["read_amplification"] is None
    assert row["acrr"] is None


def test_acrr_is_recorded_for_failed_runs_too() -> None:
    """C1 — Q22: record always, filter at display.

    Filtering at write time would destroy the data needed to ask whether failed
    runs are less efficient, and could never be recovered retroactively.
    """
    from fa.inner_loop.global_history import build_export_row

    class Failed:
        exit_code = 2
        stop_reason = "error"
        turns = 1
        final_text = ""

    workspace = Path(tempfile.mkdtemp())
    (workspace / "a.py").write_bytes(b"x" * 400)
    log = _log_with_tool_calls(workspace, [("fs_read_file", "a.py"), ("fs_edit_file", "a.py")])
    row = build_export_row(run_id="r", outcome=Failed(), log=log, workspace_root=workspace, duration_ms=1000)
    assert row["acrr"] is not None


def test_changed_path_outside_workspace_does_not_crash_the_export() -> None:
    """C1 — a hostile recorded path must not break the derived export."""
    from fa.inner_loop.global_history import build_export_row

    workspace = Path(tempfile.mkdtemp())
    log = _log_with_tool_calls(workspace, [("fs_edit_file", "/etc/passwd")])
    row = build_export_row(run_id="r", outcome=_Outcome(), log=log, workspace_root=workspace, duration_ms=1000)
    assert row["files_changed"] == 1
    assert row["cost_floor"] is not None


# --------------------------------------------------------------------------
# C1 — the calibration view
# --------------------------------------------------------------------------


def _seed(store: object, run_id: str, mode: str, acrr: float, exit_code: int = 0) -> None:
    store.export_run(  # type: ignore[attr-defined]
        {
            "run_id": run_id,
            "exit_code": exit_code,
            "scope_estimate_json": json.dumps({"recommended_mode": mode}),
            "acrr": acrr,
            "cost_actual": 10.0,
            "cost_floor": 5.0,
            "read_amplification": 2.0,
        }
    )


def test_calibration_groups_by_recommended_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """T35 (C1) — the E3 §7.4b table, from a real database."""
    monkeypatch.setenv("FA_STATE_ROOT", str(tmp_path))
    from fa.cli import _cmd_stats_calibration
    from fa.inner_loop.global_history import GlobalHistoryStore, default_global_history_path

    store = GlobalHistoryStore(db_path=default_global_history_path())
    _seed(store, "a", "chat_direct", 3.0)
    _seed(store, "b", "chat_direct", 5.0)
    _seed(store, "c", "workflow_linear", 0.5)

    import argparse

    assert _cmd_stats_calibration(argparse.Namespace(output="json")) == 0
    payload = json.loads(capsys.readouterr().out)
    by_mode = {e["recommended_mode"]: e for e in payload["calibration"]}
    assert by_mode["chat_direct"]["runs"] == 2
    assert by_mode["chat_direct"]["acrr_mean"] == 4.0
    assert by_mode["workflow_linear"]["acrr_mean"] == 0.5


def test_calibration_excludes_failed_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """T34 (C1) — a cheap failure is not an efficiency.

    Kill-check: drop the ``exit_code != 0`` filter and this fails — the failed
    run's ACRR of 99.0 would drag the mean from 3.0 to 51.0.
    """
    monkeypatch.setenv("FA_STATE_ROOT", str(tmp_path))
    from fa.cli import _cmd_stats_calibration
    from fa.inner_loop.global_history import GlobalHistoryStore, default_global_history_path

    store = GlobalHistoryStore(db_path=default_global_history_path())
    _seed(store, "ok", "chat_direct", 3.0)
    _seed(store, "bad", "chat_direct", 99.0, exit_code=2)

    import argparse

    assert _cmd_stats_calibration(argparse.Namespace(output="json")) == 0
    payload = json.loads(capsys.readouterr().out)
    entry = payload["calibration"][0]
    assert entry["runs"] == 1
    assert entry["acrr_mean"] == 3.0
    assert payload["skipped_failed_runs"] == 1


def test_calibration_json_goes_to_stdout_and_human_to_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C1 — the S10b stream split is a contract, not a detail."""
    monkeypatch.setenv("FA_STATE_ROOT", str(tmp_path))
    from fa.cli import _cmd_stats_calibration
    from fa.inner_loop.global_history import GlobalHistoryStore, default_global_history_path

    store = GlobalHistoryStore(db_path=default_global_history_path())
    _seed(store, "a", "chat_direct", 3.0)

    import argparse

    _cmd_stats_calibration(argparse.Namespace(output="json"))
    captured = capsys.readouterr()
    json.loads(captured.out)  # stdout must be parseable on its own
    assert captured.err == ""

    _cmd_stats_calibration(argparse.Namespace(output="console"))
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Routing calibration" in captured.err


def test_calibration_flag_is_wired_into_the_parser() -> None:
    """C2 — the flag exists and dispatches; behaviour tests alone never prove wiring."""
    import ast

    source = Path("src/fa/cli.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    dispatches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_cmd_stats_calibration"
    ]
    assert dispatches, "no _cmd_stats_calibration dispatch found in fa.cli"
    assert '"--calibration"' in source
