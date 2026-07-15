from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from fa.blackboard.blackboard import Blackboard, BlackboardEntry
from fa.inner_loop.context import reset_current_session, set_current_session
from fa.inner_loop.state import EventLog, SessionState
from fa.inner_loop.tools.write_file import build_write_file_tool


def test_event_log_authority_roundtrip(tmp_path: Path) -> None:
    log = EventLog(tmp_path / "events.jsonl", run_id="run-1")

    log.append(actor="runtime", kind="first", content={"n": 1})
    log.append(actor="runtime", kind="second", content={"n": 2})

    events = log.read_all()
    assert [e.kind for e in events] == ["first", "second"]
    assert log.session_db.path == tmp_path / "session.db"
    assert (tmp_path / "events.jsonl").read_text(encoding="utf-8").count("\n") == 2


def test_event_log_db_failure_does_not_create_split_brain(tmp_path: Path) -> None:
    log = EventLog(tmp_path / "events.jsonl", run_id="run-1")
    log.append(actor="runtime", kind="first", content={"n": 1})

    db_path = tmp_path / "session.db"
    os.chmod(db_path, stat.S_IREAD)
    try:
        with pytest.raises(RuntimeError, match="event_log_write_failed"):
            log.append(actor="runtime", kind="second", content={"n": 2})
    finally:
        os.chmod(db_path, stat.S_IWRITE | stat.S_IREAD)

    # Authoritative read remains consistent and the JSONL mirror is not ahead.
    events = log.read_all()
    assert [e.kind for e in events] == ["first"]
    assert (tmp_path / "events.jsonl").read_text(encoding="utf-8").count("\n") == 1


def test_session_state_blackboard_uses_same_per_run_db(tmp_path: Path) -> None:
    state = SessionState(workspace_root=tmp_path, run_id="run-1")

    assert state.log is not None
    assert state.blackboard is not None
    assert state.session_db is not None
    assert state.log.session_db.path == state.session_db.path
    assert state.blackboard._session_db.path == state.session_db.path  # type: ignore[attr-defined]


def test_blackboard_authority_roundtrip(tmp_path: Path) -> None:
    session_db_log = EventLog(tmp_path / "events.jsonl", run_id="run-1")
    blackboard = Blackboard(
        tmp_path / ".fa" / "blackboard",
        session_db=session_db_log.session_db,
        run_id="run-1",
    )

    entry = BlackboardEntry.create(
        id="plan-1",
        type="plan",
        payload={"goal": "fix auth"},
        read_set=["src/auth.py"],
        write_set=[],
        assumptions=["main branch is main"],
        version_dependencies={"base_commit": "abc123"},
    )
    blackboard.write(entry)

    read_back = blackboard.read("plan-1")
    assert read_back is not None
    assert read_back.id == "plan-1"
    assert read_back.content_hash == entry.content_hash


def test_blackboard_db_failure_does_not_create_split_brain(tmp_path: Path) -> None:
    session_db_log = EventLog(tmp_path / "events.jsonl", run_id="run-1")
    blackboard_root = tmp_path / ".fa" / "blackboard"
    blackboard = Blackboard(blackboard_root, session_db=session_db_log.session_db, run_id="run-1")

    entry1 = BlackboardEntry.create(id="1", type="plan", payload={"a": 1})
    blackboard.write(entry1)

    db_path = tmp_path / "session.db"
    os.chmod(db_path, stat.S_IREAD)
    try:
        entry2 = BlackboardEntry.create(id="2", type="plan", payload={"a": 2})
        with pytest.raises(RuntimeError, match="blackboard_write_failed"):
            blackboard.write(entry2)
    finally:
        os.chmod(db_path, stat.S_IWRITE | stat.S_IREAD)

    assert blackboard.read("1") is not None
    assert blackboard.read("2") is None
    assert blackboard_root.joinpath("blackboard.jsonl").read_text(encoding="utf-8").count("\n") == 1


def test_session_state_blackboard_does_not_create_workspace_authority_db(tmp_path: Path) -> None:
    state = SessionState(workspace_root=tmp_path, run_id="run-1")

    assert state.session_db is not None
    assert state.log is not None
    assert state.session_db.path == state.log.path.parent / "session.db"
    assert state.blackboard is not None
    assert not (tmp_path / ".fa" / "blackboard" / "session.db").exists()


def test_write_file_conflict_uses_per_run_blackboard_authority(tmp_path: Path) -> None:
    state = SessionState(workspace_root=tmp_path, run_id="run-1")
    assert state.blackboard is not None

    existing = BlackboardEntry.create(
        id="existing-write",
        type="file_version",
        payload={"path": "conflict.txt"},
        read_set=[],
        write_set=["conflict.txt"],
        assumptions=[],
        version_dependencies={"base_commit": "unknown"},
    )
    state.blackboard.write(existing)

    tool = build_write_file_tool(tmp_path)
    token = set_current_session(state)
    try:
        result = tool.handler({"path": "conflict.txt", "content": "hello\n"})
    finally:
        reset_current_session(token)

    assert result.error is not None
    assert result.error.code == "conflict_detected"
    assert not (tmp_path / "conflict.txt").exists()
