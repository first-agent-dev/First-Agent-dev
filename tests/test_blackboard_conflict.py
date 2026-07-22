"""
Tests for Formal Blackboard with Content-Hashed + Transactional Semantics
Phase 0.5 — Formal Shared Harness Substrate
"""

import tempfile
from pathlib import Path


def test_blackboard_write_read() -> None:
    from fa.blackboard.blackboard import Blackboard, BlackboardEntry

    with tempfile.TemporaryDirectory() as tmp:
        bb = Blackboard(Path(tmp) / "blackboard")
        entry = BlackboardEntry.create(
            id="plan-1",
            type="plan",
            payload={"goal": "fix auth"},
            read_set=["src/auth.py"],
            write_set=[],
            assumptions=["main branch is main"],
            version_dependencies={"base_commit": "abc123"},
        )
        bb.write(entry)
        read_back = bb.read("plan-1")
        assert read_back is not None
        assert read_back.id == "plan-1"
        assert read_back.content_hash == entry.content_hash


def test_blackboard_conflict_detection() -> None:
    from fa.blackboard.blackboard import Blackboard, BlackboardEntry

    with tempfile.TemporaryDirectory() as tmp:
        bb = Blackboard(Path(tmp) / "blackboard")

        # First agent writes file src/auth.py
        entry1 = BlackboardEntry.create(
            id="exec-1",
            type="execution",
            payload={"file": "src/auth.py"},
            read_set=[],
            write_set=["src/auth.py"],
            assumptions=[],
            version_dependencies={"base_commit": "abc123"},
        )
        bb.write(entry1)

        # Second agent tries to write same file without coordination
        entry2 = BlackboardEntry.create(
            id="exec-2",
            type="execution",
            payload={"file": "src/auth.py"},
            read_set=[],
            write_set=["src/auth.py"],
            assumptions=[],
            version_dependencies={"base_commit": "abc123"},
        )

        conflicts = bb.detect_conflict(entry2)
        assert len(conflicts) > 0, "Should detect write/write conflict"
        assert any("src/auth.py" in c.read_write_overlap for c in conflicts)


def test_blackboard_append_only() -> None:
    from fa.blackboard.blackboard import Blackboard, BlackboardEntry

    with tempfile.TemporaryDirectory() as tmp:
        bb = Blackboard(Path(tmp) / "blackboard")
        entry1 = BlackboardEntry.create(id="1", type="plan", payload={"a": 1})
        entry2 = BlackboardEntry.create(id="2", type="plan", payload={"a": 2})

        bb.write(entry1)
        bb.write(entry2)

        # Both should exist, not overwritten
        assert bb.read("1") is not None
        assert bb.read("2") is not None
        all_entries = bb.query(type="plan")
        assert len(all_entries) == 2
