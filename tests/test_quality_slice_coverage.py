from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import fastjsonschema  # type: ignore[import-untyped]
import pytest

import fa.inner_loop.tools as tool_module
from fa.blackboard.blackboard import Blackboard, BlackboardEntry
from fa.inner_loop.registry import ToolRegistry, ToolResult, ToolSpec
from fa.inner_loop.state import EventLog, SessionState
from fa.inner_loop.subagent_runner import SubagentRunner
from fa.stats import aggregate_sessions, parse_session, render_session_json


def _spec(name: str) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=name,
        input_schema={"type": "object"},
        permission="read",
        handler=lambda _: ToolResult.ok(""),
    )


def test_extra_tool_registration_failures_and_duplicates_are_observable(tmp_path: Path, caplog: Any) -> None:
    """S14b.1: Every optional registration branch fails independently and remains retry-safe.

    Mocks the module-level builder callables (build_fs_search_tool,
    build_usage_tool, build_spawn_subagent_tool, ...) to simulate failures;
    asserts surviving tools register, failed ones are absent, duplicates
    are suppressed on the second call, and WARNINGs are observable.
    """
    import logging

    names = (
        "build_fs_search_tool",
        "build_chronicle_search_tool",
        "build_usage_tool",
        "build_list_tasks_tool",
        "build_checkpoint_tool",
        "build_undo_tool",
        "build_diff_tool",
        "build_send_ctrl_c_tool",
        "build_spawn_subagent_tool",
    )
    original = {name: getattr(tool_module, name) for name in names}
    try:
        # fs_search succeeds → present
        tool_module.build_fs_search_tool = lambda *_a, **_kw: _spec("fs_search")
        tool_module.build_chronicle_search_tool = lambda: _spec("fs_chronicle_search")
        # usage fails → absent
        tool_module.build_usage_tool = lambda: (_ for _ in ()).throw(RuntimeError("usage broken"))
        tool_module.build_list_tasks_tool = lambda: _spec("fs_list_tasks")
        tool_module.build_checkpoint_tool = lambda _: _spec("fs_checkpoint")
        tool_module.build_undo_tool = lambda _: _spec("fs_undo")
        tool_module.build_diff_tool = lambda _: _spec("fs_diff")
        tool_module.build_send_ctrl_c_tool = lambda: _spec("fs_send_ctrl_c")
        # spawn fails → absent
        tool_module.build_spawn_subagent_tool = lambda _: (_ for _ in ()).throw(RuntimeError("spawn broken"))

        caplog.set_level(logging.WARNING)
        registry = ToolRegistry()
        tool_module._register_extra_tools(
            registry,
            tmp_path,
            include_pair=True,
            include_observability=True,
        )
        # Second call must be idempotent (dedupe guard)
        tool_module._register_extra_tools(
            registry,
            tmp_path,
            include_pair=True,
            include_observability=True,
        )
    finally:
        for name, value in original.items():
            setattr(tool_module, name, value)

    registered = set(registry.names())
    assert {
        "fs_search",
        "fs_chronicle_search",
        "fs_list_tasks",
        "fs_checkpoint",
        "fs_undo",
        "fs_diff",
        "fs_send_ctrl_c",
    } <= registered
    # Failed builders must NOT register their tools.
    assert "fs_usage" not in registered
    assert "fs_spawn_subagent" not in registered
    # Old tool names must be gone.
    for old in ("fs_glob", "fs_grep", "fs_instant_grep"):
        assert old not in registered
    # No duplicates: set size equals list size.
    assert len(registry.names()) == len(registered)
    assert any("usage" in record.message.lower() for record in caplog.records)
    assert any("spawn" in record.message.lower() for record in caplog.records)


def test_baseline_registry_fallback_is_live_when_profiles_fail(tmp_path: Path, caplog: Any) -> None:
    with patch(
        "fa.inner_loop.profiles.build_registry_for_role",
        side_effect=RuntimeError("profiles unavailable"),
    ):
        registry = tool_module.build_baseline_registry(tmp_path)

    assert {"fs_read_file", "fs_write_file", "fs_run_bash"} <= set(registry.names())
    assert any("fallback baseline" in record.message for record in caplog.records)


def test_subagent_filtered_history_includes_real_blackboard_plans(tmp_path: Path) -> None:
    from fa.feature_flags import FeatureFlags
    from fa.inner_loop.context import reset_current_session, set_current_session

    state = SessionState(
        workspace_root=tmp_path,
        run_id="history-plans",
        log=EventLog(tmp_path / "events.jsonl", run_id="history-plans"),
        feature_flags=FeatureFlags(
            subagent_spawning_enabled=True,
            blackboard_filtered_history_include_plans=True,
        ),
    )
    assert state.blackboard is not None
    state.blackboard.write(
        BlackboardEntry.create(
            id="plan-1",
            type="plan",
            payload={"Goal": "test filtered history"},
            assumptions=["workspace is clean"],
        )
    )
    token = set_current_session(state)
    try:
        history = SubagentRunner(tmp_path)._build_filtered_history("find the plan")
    finally:
        reset_current_session(token)

    assert any(item["role"] == "system" and "plan-1" in item["content"] for item in history)
    assert any("test filtered history" in item["content"] for item in history)


def test_subagent_validation_failure_is_structured(tmp_path: Path) -> None:
    runner = SubagentRunner(tmp_path)

    def reject(_: object) -> None:
        raise fastjsonschema.JsonSchemaValueException("invalid envelope", {}, "envelope", {}, "type")

    runner.validator = reject
    envelope = runner.run_stateless("validation", "printf ok", workdir=tmp_path)
    assert envelope.exit_code == -1
    assert envelope.next_action == "retry"
    assert "validation failed" in envelope.summary.lower()
    assert not (tmp_path / ".fa" / "subagents" / "validation.json").exists()


def test_subagent_artifact_and_worklog_failures_are_best_effort(tmp_path: Path, caplog: Any) -> None:
    runner = SubagentRunner(tmp_path)
    with (
        patch("fa.inner_loop.subagent_runner.write_envelope_artifact", side_effect=OSError("artifact full")),
        patch.object(runner, "_append_to_worklog", side_effect=OSError("worklog full")),
    ):
        envelope = runner.run_stateless("best-effort", "printf ok", workdir=tmp_path)

    assert envelope.exit_code == 0
    assert any("artifact" in record.message.lower() for record in caplog.records)


def test_subagent_limits_fallback_to_instance_after_session_error(tmp_path: Path) -> None:
    runner = SubagentRunner(tmp_path, limits=SimpleNamespace(max_subagent_spawns_per_session=1))
    with patch(
        "fa.inner_loop.context.get_current_session",
        side_effect=RuntimeError("context unavailable"),
    ):
        runner._check_spawn_limit()
        with pytest.raises(RuntimeError, match="Subagent spawn limit"):
            runner._check_spawn_limit()
    assert runner._instance_spawn_count == 1


def test_blackboard_conflict_matrix_and_linear_parent_policy(tmp_path: Path) -> None:
    # S5.4.1: the prior entry must come from a DIFFERENT writer. This test
    # covers the read/write overlap matrix and the parent_id linear-chain
    # policy; it previously wrote both entries from one Blackboard, so the
    # conflict it asserted was the agent colliding with itself (Q18) rather
    # than the cross-writer overlap the matrix is about. Same root => same
    # authority DB, so both writers share one blackboard table.
    bb_other = Blackboard(tmp_path / ".fa" / "blackboard", run_id="other-agent")
    bb = Blackboard(tmp_path / ".fa" / "blackboard", run_id="conflict")
    old = BlackboardEntry.create(
        id="old",
        type="plan",
        payload={"version": 1},
        read_set=["read.py"],
        write_set=["shared.py"],
        version_dependencies={"base_commit": "abc"},
    )
    bb_other.write(old)

    new = BlackboardEntry.create(
        id="new",
        type="plan",
        payload={"version": 2},
        read_set=["shared.py"],
        write_set=["read.py"],
        assumptions=["base_commit abc is current"],
        version_dependencies={"base_commit": "abc"},
    )
    conflicts = bb.detect_conflict(new)
    assert len(conflicts) == 1
    assert {"shared.py", "read.py"} <= set(conflicts[0].read_write_overlap)
    assert "read/write" in conflicts[0].reason
    assert "write/read" in conflicts[0].reason

    child = BlackboardEntry.create(
        id="child",
        type="plan",
        payload={"version": 3},
        write_set=["shared.py"],
        parent_id="old",
        version_dependencies={"base_commit": "abc"},
    )
    assert bb.detect_conflict(child) == []


def test_blackboard_authority_fallback_reads_and_queries_corrupt_mirror(tmp_path: Path) -> None:
    root = tmp_path / ".fa" / "blackboard"
    bb = Blackboard(root, run_id="fallback")
    entry = BlackboardEntry.create(id="mirror", type="note", payload={"needle": True})
    bb.write(entry)
    bb.path.write_text(
        bb.path.read_text(encoding="utf-8") + "not-json\n",
        encoding="utf-8",
    )
    with patch.object(bb._session_db, "read_blackboard_row", side_effect=RuntimeError("db down")):
        assert bb.read("mirror") is not None
    with patch.object(bb._session_db, "query_blackboard_rows", side_effect=RuntimeError("db down")):
        results = bb.query(type="note", key="needle")
    assert [item.id for item in results] == ["mirror"]


def test_blackboard_mirror_failure_does_not_hide_authoritative_write(tmp_path: Path) -> None:
    bb = Blackboard(tmp_path / ".fa" / "blackboard", run_id="mirror")
    entry = BlackboardEntry.create(id="authoritative", type="note", payload={"ok": True})
    with patch("builtins.open", side_effect=OSError("mirror unavailable")):
        bb.write(entry)
    assert bb.read("authoritative") is not None


def _event(path: Path, kind: str, content: dict[str, Any] | None = None) -> None:
    row = {
        "event_id": f"{kind}-1",
        "ts": "2026-07-21T00:00:00Z",
        "run_id": "stats-edge",
        "harness_id": "test",
        "actor": "runtime",
        "kind": kind,
        "content": content or {},
        "tool_name": "fs_read_file" if kind in {"tool_call", "tool_result"} else "",
        "tool_call_id": "",
        "parent_event_id": "",
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def test_stats_empty_malformed_and_mixed_event_streams(tmp_path: Path) -> None:
    empty = tmp_path / "empty.jsonl"
    empty.touch()
    assert parse_session(empty) is None

    malformed = tmp_path / "malformed.jsonl"
    malformed.write_text("not json\n", encoding="utf-8")
    assert parse_session(malformed) is None

    mixed = tmp_path / "mixed.jsonl"
    _event(mixed, "run_started", {"role": "coder", "model": "test"})
    _event(mixed, "unknown_future_kind", {"opaque": True})
    _event(mixed, "tool_call", {"tool_call_id": "c1"})
    _event(mixed, "tool_result", {"ok": True})
    _event(mixed, "session_summary", {"n_turns": 1, "input_tokens": 2, "output_tokens": 1})
    parsed = parse_session(mixed)
    assert parsed is not None
    assert parsed.run_id == "stats-edge"
    assert parsed.turns == 1
    assert parsed.tool_usage[0].name == "fs_read_file"
    assert render_session_json(parsed)["run_id"] == "stats-edge"
    aggregate = aggregate_sessions([parsed])
    assert aggregate["sessions"] == 1


def test_stats_aggregate_empty_is_structured() -> None:
    aggregate = aggregate_sessions([])
    assert aggregate["sessions"] == 0
    assert aggregate["total_turns"] == 0
    assert aggregate["ok"] == 0
