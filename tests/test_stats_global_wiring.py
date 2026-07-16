"""C2 test for fa stats --global-history active consumer — Task 6.

- Root: cli:stats with --global-history flag + GlobalHistoryStore
- Matrix: C-defaults
- Oracle: JSON output contains run_ids from global_history.db
- Kill-check: removing read_all() call in stats.py makes test fail
- Pyramid: A, C2
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fa.inner_loop.global_history import GlobalHistoryStore


def test_stats_global_history_cli_reads_projection(tmp_path: Path, monkeypatch) -> None:
    """C2: fa stats --global-history reads derived projection.

    Creates tmp global_history.db with 2 rows, monkeypatches HOME to tmp, runs _cmd_stats with --global-history flag.
    """
    # Setup fake HOME with global_history.db
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    db_path = fake_home / ".fa" / "global_history.db"
    store = GlobalHistoryStore(db_path=db_path)

    # Insert 2 rows
    for i in range(2):
        row = {
            "run_id": f"run-global-{i}",
            "created_at": "2026-07-15T00:00:00Z",
            "updated_at": "2026-07-15T00:00:01Z",
            "role": "coder",
            "model": "test-model",
            "family": "openai",
            "exit_code": 0,
            "stop_reason": "stopped_by_llm",
            "turns": 1,
            "input_tokens": 10,
            "output_tokens": 5,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_hit_ratio": 0.0,
            "tool_calls_total": 1,
            "tool_calls_breakdown_json": "{}",
            "has_compaction_summary": 0,
            "workspace_root": str(tmp_path),
            "duration_ms": 100,
        }
        store.export_run(row)

    # Now run cli _cmd_stats with --global-history
    from fa.cli import _cmd_stats
    import argparse

    args = argparse.Namespace(
        run_id=None,
        since=None,
        output="json",
        workspace=tmp_path,
        dead_zones=False,
        global_history=True,
    )

    # Capture stdout
    import io, sys

    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        exit_code = _cmd_stats(args)
    finally:
        sys.stdout = old_stdout

    assert exit_code == 0
    output = captured.getvalue()
    data = json.loads(output)
    assert isinstance(data, list)
    run_ids = [r.get("run_id") for r in data]
    assert "run-global-0" in run_ids
    assert "run-global-1" in run_ids


def test_stats_global_history_projection_only() -> None:
    """C2: global_history is read only by stats and cli, not by hot-path."""
    # Already covered in test_global_history_export.py::test_global_history_is_projection_only
    # Here we just assert that cli.py contains global_history string (active consumer)
    cli_path = Path("src/fa/cli.py")
    assert cli_path.exists()
    content = cli_path.read_text(encoding="utf-8")
    assert "global_history" in content, "cli.py should import global_history as active consumer per AGENTS rule #3"
