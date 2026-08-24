"""S15 — exploration telemetry (CT-3/CT-4): file_read events + fs_exploration_metrics.

C1 tests against the real ``run_session`` composition root with real tool
builders and a real EventLog; C0p tests against the pure ``compute_metrics``
function. No mocks of SessionState, registry, or log.

Path coverage (plan P-matrix):
  P11/P12  whole-file + line-range read → file_read row        (T20)
  P13      attribution: earlier-batch search → search_result;  (T22, T22b)
           same-batch/pending → direct_reference
  failed read → NO file_read row                               (T21)
  compute_metrics exact formulas                               (T23, T24)
  live trajectory via fs_exploration_metrics tool              (T25)

Kill-check targets (producers, not consumers):
  - read_file.py record_file_read call        → T20/T22 fail
  - loop.py commit_search_paths call          → T22 fails
  - compute_metrics acc computation           → T23/T25 fail
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop import EventLog, SessionState, ToolCall, run_session
from fa.inner_loop.hooks import HookRegistry
from fa.inner_loop.registry import ToolRegistry
from fa.inner_loop.state import TraceEvent
from fa.inner_loop.tools.fs_exploration_metrics import (
    build_fs_exploration_metrics_tool,
    compute_metrics,
)
from fa.inner_loop.tools.fs_search import build_fs_search_tool
from fa.inner_loop.tools.read_file import build_read_file_tool
from fa.inner_loop.tools.write_file import build_write_file_tool
from fa.inner_loop.transaction import Transaction

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def _state(tmp_path: Path) -> SessionState:
    return SessionState(
        workspace_root=tmp_path,
        run_id="t-s15",
        log=EventLog(tmp_path / "events.jsonl"),
        transaction=Transaction(id="t-s15"),
    )


def _file_read_rows(state: SessionState) -> list[TraceEvent]:
    assert state.log is not None
    return [row for row in state.log.read_all() if row.kind == "file_read"]


def _call(name: str, params: dict[str, Any]) -> ToolCall:
    return ToolCall(name=name, params=params, call_id=f"tc-{name}-{len(str(params))}")


# ── T20 (P11/P12): file_read row shape ──────────────────────────────────────


def test_file_read_event_emitted_whole_file_and_range(tmp_path: Path) -> None:
    fixture = tmp_path / "a.txt"
    fixture.write_text("line one\nline two\nline three\n", encoding="utf-8")
    registry = ToolRegistry()
    registry.register(build_read_file_tool(tmp_path))
    state = _state(tmp_path)

    # P12: whole-file read
    run_session(
        (_call("fs_read_file", {"path": "a.txt"}),),
        registry=registry,
        hooks=HookRegistry(),
        state=state,
        role="coder",
    )
    rows = _file_read_rows(state)
    assert len(rows) == 1
    content = rows[0].content
    assert content["path"] == "a.txt"
    assert content["turn"] == 1  # batch_turn, not the per-tool-call counter
    assert content["start_line"] is None
    assert content["end_line"] is None
    assert content["surfaced_by"] == "direct_reference"
    bytes_read = content["bytes_read"]
    assert isinstance(bytes_read, int)
    assert bytes_read == len(b"line one\nline two\nline three\n")

    # P11: line-range read
    run_session(
        (_call("fs_read_file", {"path": "a.txt", "start_line": 2, "end_line": 3}),),
        registry=registry,
        hooks=HookRegistry(),
        state=state,
        role="coder",
    )
    rows = _file_read_rows(state)
    assert len(rows) == 2
    content = rows[1].content
    assert content["turn"] == 2
    assert content["start_line"] == 2
    assert content["end_line"] == 3


# ── T21: failed reads emit nothing ──────────────────────────────────────────


def test_no_file_read_event_for_failed_read(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("one\ntwo\n", encoding="utf-8")
    registry = ToolRegistry()
    registry.register(build_read_file_tool(tmp_path))
    state = _state(tmp_path)

    result = run_session(
        (_call("fs_read_file", {"path": "a.txt", "start_line": 10, "end_line": 2}),),
        registry=registry,
        hooks=HookRegistry(),
        state=state,
        role="coder",
    )
    assert len(result) == 1
    assert result[0].error is not None  # invalid line window
    assert _file_read_rows(state) == []


# ── T22 (P13): deterministic attribution ────────────────────────────────────


def test_surfaced_by_search_result_from_earlier_batch(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("needle one\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("other\n", encoding="utf-8")
    search_tool = build_fs_search_tool(tmp_path / ".fa" / "fts.db", tmp_path)
    read_tool = build_read_file_tool(tmp_path)
    state = _state(tmp_path)

    search_registry = ToolRegistry()
    search_registry.register(search_tool)
    read_registry = ToolRegistry()
    read_registry.register(read_tool)

    # Batch 1: search surfaces a.txt.
    search_result = run_session(
        (_call("fs_search", {"query": "needle"}),),
        registry=search_registry,
        hooks=HookRegistry(),
        state=state,
        role="coder",
    )
    assert len(search_result) == 1
    assert search_result[0].error is None

    # Batch 2: read of the surfaced file → search_result; batch 3: other → direct.
    run_session(
        (_call("fs_read_file", {"path": "a.txt"}),),
        registry=read_registry,
        hooks=HookRegistry(),
        state=state,
        role="coder",
    )
    run_session(
        (_call("fs_read_file", {"path": "b.txt"}),),
        registry=read_registry,
        hooks=HookRegistry(),
        state=state,
        role="coder",
    )
    rows = _file_read_rows(state)
    assert [row.content["path"] for row in rows] == ["a.txt", "b.txt"]
    assert rows[0].content["surfaced_by"] == "search_result"
    assert rows[0].content["turn"] == 2
    assert rows[1].content["surfaced_by"] == "direct_reference"


def test_pending_search_paths_are_not_attributable_until_commit(tmp_path: Path) -> None:
    """Two-set boundary: pending (mid-batch) paths do NOT attribute; committed do."""
    (tmp_path / "x.txt").write_text("payload\n", encoding="utf-8")
    read_tool = build_read_file_tool(tmp_path)
    registry = ToolRegistry()
    registry.register(read_tool)
    state = _state(tmp_path)

    # Simulate a search result landing mid-batch (pending only).
    state.add_search_result_paths(["x.txt"])

    run_session(
        (_call("fs_read_file", {"path": "x.txt"}),),
        registry=registry,
        hooks=HookRegistry(),
        state=state,
        role="coder",
    )
    rows = _file_read_rows(state)
    assert rows[0].content["surfaced_by"] == "direct_reference"  # not yet committed

    state.commit_search_paths()
    run_session(
        (_call("fs_read_file", {"path": "x.txt"}),),
        registry=registry,
        hooks=HookRegistry(),
        state=state,
        role="coder",
    )
    rows = _file_read_rows(state)
    assert rows[1].content["surfaced_by"] == "search_result"  # committed → attributable


# ── T23/T24: compute_metrics exact formulas ─────────────────────────────────


def _fr(path: str, turn: int, nbytes: int, idx: int) -> TraceEvent:
    return TraceEvent(
        event_id=f"ev-{idx}",
        ts="2026-08-17T00:00:00Z",
        run_id="t",
        actor="coder",
        kind="file_read",
        content={
            "path": path,
            "turn": turn,
            "start_line": None,
            "end_line": None,
            "surfaced_by": "direct_reference",
            "bytes_read": nbytes,
        },
    )


def test_compute_metrics_seeded_exact() -> None:
    rows = [
        _fr("A.py", turn=1, nbytes=100, idx=1),
        _fr("B.py", turn=2, nbytes=200, idx=2),
        _fr("gold.py", turn=3, nbytes=300, idx=3),
        _fr("C.py", turn=4, nbytes=400, idx=4),
        _fr("D.py", turn=5, nbytes=500, idx=5),
    ]
    metrics = compute_metrics(rows, search_count=3, write_set={"gold.py"}, gold_files={"gold.py"})
    assert metrics.acc_at_k == {"1": 0.0, "5": 1.0, "10": 1.0, "20": 1.0}
    assert metrics.first_useful_hit == 3
    assert metrics.ctx_efficiency == pytest.approx(300 / (100 + 200 + 300 + 400 + 500))
    assert metrics.n_reads == 5
    assert metrics.n_searches == 3
    assert metrics.gold_files == ["gold.py"]
    assert metrics.note == ""


def test_compute_metrics_multiple_gold() -> None:
    rows = [
        _fr("g1.py", turn=2, nbytes=100, idx=1),
        _fr("g2.py", turn=7, nbytes=100, idx=2),
    ]
    metrics = compute_metrics(rows, 0, None, {"g1.py", "g2.py"})
    assert metrics.acc_at_k["1"] == 0.5  # g1 read at index 1; g2 not yet
    assert metrics.acc_at_k["5"] == 1.0  # both within k=5
    assert metrics.acc_at_k["10"] == 1.0
    assert metrics.first_useful_hit == 2
    # g2 never appears in the write-set → its bytes do not count
    assert metrics.ctx_efficiency == 0.0


def test_compute_metrics_no_gold_and_empty() -> None:
    metrics = compute_metrics([], 0, None, None)
    assert metrics.acc_at_k == {"1": None, "5": None, "10": None, "20": None}
    assert metrics.first_useful_hit is None
    assert metrics.ctx_efficiency == 0.0
    assert metrics.n_reads == 0
    assert metrics.n_searches == 0
    assert metrics.gold_files is None
    assert "declare gold files" in metrics.note


# ── T25: live trajectory through the tool ───────────────────────────────────


def test_metrics_tool_live_search_read_write(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("needle payload\n", encoding="utf-8")
    state = _state(tmp_path)
    state.declare_gold_files(["a.txt"])

    search_registry = ToolRegistry()
    search_registry.register(build_fs_search_tool(tmp_path / ".fa" / "fts.db", tmp_path))
    read_registry = ToolRegistry()
    read_registry.register(build_read_file_tool(tmp_path))
    write_registry = ToolRegistry()
    write_registry.register(build_write_file_tool(tmp_path))
    metrics_registry = ToolRegistry()
    metrics_registry.register(build_fs_exploration_metrics_tool())

    # batch 1: search surfaces a.txt; batch 2: read it; batch 3: write it.
    run_session(
        (_call("fs_search", {"query": "needle"}),),
        registry=search_registry,
        hooks=HookRegistry(),
        state=state,
        role="coder",
    )
    run_session(
        (_call("fs_read_file", {"path": "a.txt"}),),
        registry=read_registry,
        hooks=HookRegistry(),
        state=state,
        role="coder",
    )
    run_session(
        (_call("fs_write_file", {"path": "a.txt", "content": "needle updated\n"}),),
        registry=write_registry,
        hooks=HookRegistry(),
        state=state,
        role="coder",
    )
    result = run_session(
        (_call("fs_exploration_metrics", {}),),
        registry=metrics_registry,
        hooks=HookRegistry(),
        state=state,
        role="coder",
    )

    assert len(result) == 1
    assert result[0].error is None
    payload = result[0].result
    assert isinstance(payload, Mapping)
    assert payload["acc_at_k"] == {"1": 1.0, "5": 1.0, "10": 1.0, "20": 1.0}
    assert payload["first_useful_hit"] == 2  # batch_turn of the read
    assert payload["ctx_efficiency"] == 1.0  # the only read file is in the write-set
    assert payload["n_reads"] == 1
    assert payload["n_searches"] == 1
    assert payload["gold_files"] == ["a.txt"]
    assert payload["note"] == ""
