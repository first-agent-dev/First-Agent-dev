from __future__ import annotations

import json
from pathlib import Path

import pytest

from fa.inner_loop.profiles import build_registry_for_role, estimate_tokens, get_profile
from fa.inner_loop.session_db import SessionDatabase
from fa.inner_loop.tools.edit_file import build_edit_file_tool
from fa.inner_loop.tools.read_file import build_read_file_tool


def test_read_file_live_handler_windows_and_failures(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("one\ntwo\nthree\n", encoding="utf-8")
    tool = build_read_file_tool(tmp_path)

    result = tool.handler({"path": "notes.txt", "start_line": 2, "end_line": 3})
    assert result.error is None
    assert result.result == {
        "path": str(path),
        "content": "two\nthree",
        "line_count": 3,
    }

    invalid = tool.handler({"path": "notes.txt", "start_line": 3, "end_line": 2})
    assert invalid.error is not None
    assert invalid.error.code == "invalid_params"

    missing = tool.handler({"path": "missing.txt"})
    assert missing.error is not None
    assert missing.error.code == "read_failed"

    bad_params = tool.handler({"path": 42})
    assert bad_params.error is not None
    assert bad_params.error.code == "invalid_params"


def test_edit_file_live_handler_exact_fuzzy_and_containment(tmp_path: Path) -> None:
    path = tmp_path / "edit.txt"
    path.write_text("alpha\n    beta\ngamma\n", encoding="utf-8")
    tool = build_edit_file_tool(tmp_path)

    exact = tool.handler({"path": "edit.txt", "old_string": "alpha", "new_string": "ALPHA"})
    assert exact.error is None
    assert path.read_text(encoding="utf-8").startswith("ALPHA")

    fuzzy = tool.handler({"path": "edit.txt", "old_string": "beta", "new_string": "BETA"})
    assert fuzzy.error is None
    assert "BETA" in path.read_text(encoding="utf-8")

    absent = tool.handler({"path": "edit.txt", "old_string": "not present", "new_string": "x"})
    assert absent.error is not None
    assert absent.error.code == "edit_failed"

    outside = tool.handler({"path": "../outside.txt", "old_string": "x", "new_string": "y"})
    assert outside.error is not None
    assert outside.error.code == "invalid_params"


def test_profiles_build_real_role_registries_and_planner_allowlist(tmp_path: Path) -> None:
    researcher = build_registry_for_role("researcher", tmp_path)
    assert {"fs.read_file", "fs.glob", "fs.grep"}.issubset(set(researcher.names()))
    assert "fs.run_bash" not in researcher.names()

    planner = build_registry_for_role("planner", tmp_path)
    write_tool = planner.lookup("fs.write_file")
    assert write_tool is not None
    denied = write_tool.handler({"path": "src/nope.py", "content": "x"})
    assert denied.error is not None
    assert denied.error.code == "path_denied"

    allowed = write_tool.handler({"path": "knowledge/research/note.md", "content": "x"})
    assert allowed.error is None
    assert get_profile("planner").stateless is True
    assert estimate_tokens(planner) > 0

    with pytest.raises(ValueError, match="Unknown role"):
        build_registry_for_role("unknown", tmp_path)


def test_session_database_all_authority_facades_and_queries(tmp_path: Path) -> None:
    db = SessionDatabase(tmp_path / "session.db")
    event = {
        "event_id": "e1",
        "ts": "2026-01-01T00:00:00Z",
        "run_id": "run-1",
        "actor": "runtime",
        "kind": "tool_call",
        "tool_name": "fs.read_file",
        "tool_call_id": "call-1",
        "parent_event_id": "",
        "content": {"path": "a.py"},
        "harness_id": "h1",
    }
    db.append_event_row(event)
    assert db.read_event_rows()[0]["content"] == {"path": "a.py"}

    board = {
        "id": "plan-1",
        "run_id": "run-1",
        "type": "plan",
        "content_hash": "hash",
        "toolchain_digest": "toolchain",
        "schema_version": "1",
        "parent_id": None,
        "read_set": ["a.py"],
        "write_set": ["b.py"],
        "assumptions": ["clean"],
        "version_dependencies": {"base": "abc"},
        "timestamp": "2026-01-01T00:00:00Z",
        "payload": {"goal": "coverage"},
    }
    db.write_blackboard_row(board)
    assert db.read_blackboard_row("missing") is None
    assert db.read_blackboard_row("plan-1")["payload"]["goal"] == "coverage"  # type: ignore[index]
    assert db.query_blackboard_rows(entry_type="plan", key="coverage")[0]["id"] == "plan-1"
    assert db.query_blackboard_rows(entry_type="other") == []

    db.set_meta("count", 3, "2026-01-01T00:00:00Z")
    assert db.get_meta("count") == 3
    assert db.get_meta("missing") is None

    with pytest.raises(RuntimeError, match="event_log_write_failed"):
        db.append_event_row({"event_id": "broken"})

    # Ensure JSON payload matching also handles non-dict payloads.
    board["id"] = "scalar"
    board["payload"] = "plain coverage value"
    db.write_blackboard_row(board)
    assert db.query_blackboard_rows(key="coverage")[0]["id"] == "plan-1"
    assert any(row["id"] == "scalar" for row in db.query_blackboard_rows(key="coverage"))
    assert json.loads(db.read_event_rows()[0]["content"] and json.dumps({"ok": True})) == {"ok": True}
