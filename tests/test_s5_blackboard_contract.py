"""S5.3 — Blackboard append-only semantics and non-expiring conflict detection.

Plan: `worklogs/implementation-plans/PLAN-cli-trace-S5-authority-correctness.md`
§S5-CT3, paths S5-P5, S5-P6, S5-P9.

Contract source: **ADR-16 I-6.2/I-6.3** (`knowledge/adr/DIGEST.md:733`) —
*"blackboard append-only content-hashed queryable detect_conflict()"* and
*"no silent overwrite -> fail code conflict_detected"*.

Two defects are covered, and they fail independently:

* **V6** — `write_blackboard_row` used `INSERT OR REPLACE`, so writing an entry
  whose `id` already existed silently overwrote the prior row. Under an
  append-only contract that is exactly the "silent overwrite" I-6.3 forbids:
  conflict lineage is erased with no diagnostic.
* **S3-F10** — `_should_check_conflict` returned ``new_base == old_base``, so
  once *any* commit landed, every pre-commit entry was treated as "serialized"
  and skipped. Since coding agents commit routinely, the formal guarantee
  expired mid-session. Measured in S3: agent B blocked at HEAD1, one commit
  lands, agent C writes the same file and is allowed.

The `parent_id` happens-before rule is deliberately preserved and asserted
below: it is the legitimate way to express "this entry supersedes that one",
and removing it would over-reject correct linear chains.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from fa.blackboard.blackboard import Blackboard, BlackboardEntry
from fa.inner_loop.session_db import SessionDatabase, SessionDatabaseError

_SESSION = "s5-bb-session"


def _blackboard(tmp_path: Path) -> tuple[Blackboard, SessionDatabase]:
    """Real Blackboard on a real session-bound authority — no mocks (C1)."""
    db = SessionDatabase(tmp_path / "session.db", session_id=_SESSION)
    board = Blackboard(tmp_path / ".fa" / "blackboard", session_db=db, session_id=_SESSION)
    return board, db


def _entry(
    entry_id: str,
    *,
    base_commit: str | None = "commit-aaa",
    write_set: tuple[str, ...] = ("shared.py",),
    read_set: tuple[str, ...] = (),
    parent_id: str | None = None,
    payload: dict[str, object] | None = None,
) -> BlackboardEntry:
    return BlackboardEntry.create(
        id=entry_id,
        type="file_version",
        payload=payload if payload is not None else {"path": "shared.py"},
        read_set=list(read_set),
        write_set=list(write_set),
        assumptions=[],
        version_dependencies={"base_commit": base_commit} if base_commit else {},
        parent_id=parent_id,
    )


def test_same_base_commit_conflict_denied(tmp_path: Path) -> None:
    """S5-P5: two concurrent writers on one base must conflict.

    Positive control for the S5-P6 fix: this already passes today, and it must
    keep passing. If a change to `_should_check_conflict` broke this, conflict
    detection would be off entirely rather than merely expiring.
    """
    board, _db = _blackboard(tmp_path)
    board.write(_entry("agent-a", base_commit="commit-aaa"))

    conflicts = board.detect_conflict(_entry("agent-b", base_commit="commit-aaa"))

    assert conflicts, "write/write overlap on the same base_commit must be detected"
    assert conflicts[0].conflicting_entry_id == "agent-a"
    assert "shared.py" in conflicts[0].read_write_overlap


def test_conflict_denied_across_intervening_commit(tmp_path: Path) -> None:
    """S5-P6 / S3-F10: a commit must not disable detection against older entries.

    This is the regression the slice exists to close. `agent-a` recorded a write
    at `commit-aaa`; a commit then moved HEAD to `commit-bbb`. `agent-c` writing
    the same path is still a genuine write/write overlap — a different
    `base_commit` means "later", not "safe".
    """
    board, _db = _blackboard(tmp_path)
    board.write(_entry("agent-a", base_commit="commit-aaa"))

    conflicts = board.detect_conflict(_entry("agent-c", base_commit="commit-bbb"))

    assert conflicts, (
        "an intervening commit must not disable conflict detection: differing base_commit means later, not serialized"
    )
    assert conflicts[0].conflicting_entry_id == "agent-a"


def test_parent_id_chain_still_suppresses_conflict(tmp_path: Path) -> None:
    """S5-P6 guard: the legitimate happens-before signal must survive the fix.

    Without this, a fix for S3-F10 could over-reject by treating an explicit
    linear chain (`parent_id` -> predecessor) as a concurrent conflict, which
    would deny correct sequential edits.
    """
    board, _db = _blackboard(tmp_path)
    board.write(_entry("agent-a", base_commit="commit-aaa"))

    child = _entry("agent-a-child", base_commit="commit-bbb", parent_id="agent-a")

    assert board.detect_conflict(child) == [], (
        "an entry that declares its predecessor via parent_id happens-after it and must not be reported as a conflict"
    )


def test_non_overlapping_write_sets_do_not_conflict(tmp_path: Path) -> None:
    """S5-R3 positive case: the fix must not deny legitimate independent writes."""
    board, _db = _blackboard(tmp_path)
    board.write(_entry("agent-a", base_commit="commit-aaa", write_set=("alpha.py",)))

    conflicts = board.detect_conflict(
        _entry("agent-b", base_commit="commit-bbb", write_set=("beta.py",), payload={"path": "beta.py"})
    )

    assert conflicts == [], "disjoint write_sets must never conflict, regardless of base_commit"


def test_blackboard_duplicate_id_semantics_explicit(tmp_path: Path) -> None:
    """S5-P9 / V6: re-writing an existing id must fail loudly, not overwrite.

    ADR-16 I-6.3 forbids silent overwrite. Before this slice `INSERT OR REPLACE`
    replaced the row in place, erasing the prior entry's content_hash, write_set
    and lineage with no diagnostic. The assertion checks BOTH halves: a
    structured error is raised, and the original row is still intact.
    """
    board, db = _blackboard(tmp_path)
    board.write(_entry("dup-id", base_commit="commit-aaa", payload={"version": 1}))

    with pytest.raises(SessionDatabaseError) as excinfo:
        db.write_blackboard_row(
            {
                "id": "dup-id",
                "session_id": _SESSION,
                "run_id": "",
                "type": "file_version",
                "content_hash": "deadbeef",
                "toolchain_digest": "",
                "schema_version": "v1",
                "parent_id": None,
                "read_set": [],
                "write_set": ["shared.py"],
                "assumptions": [],
                "version_dependencies": {"base_commit": "commit-bbb"},
                "timestamp": "2026-07-28T00:00:00Z",
                "payload": {"version": 2},
            }
        )

    assert excinfo.value.code == "blackboard_duplicate_id", (
        f"duplicate id must surface a named error, got {excinfo.value.code!r}"
    )

    surviving = [entry for entry in board.query() if entry.id == "dup-id"]
    assert len(surviving) == 1, "the original row must remain exactly once"
    assert surviving[0].payload == {"version": 1}, "the prior entry must not be overwritten"


def test_session_meta_last_write_wins_unchanged(tmp_path: Path) -> None:
    """C0 regression guard (risk S5-R6): session_meta must stay overwrite-capable.

    `session_meta` is deliberately last-write-wins — `coder_loop` re-writes the
    `kind_counts` rollup on every turn. A grep-and-replace of `INSERT OR REPLACE`
    across all three sites in `session_db.py` would break that, so this pins the
    distinction between the two tables.
    """
    db = SessionDatabase(tmp_path / "session.db", session_id=_SESSION)

    db.set_meta("kind_counts", {"usage": 1}, "2026-07-28T00:00:00Z")
    db.set_meta("kind_counts", {"usage": 2}, "2026-07-28T00:00:01Z")

    assert db.get_meta("kind_counts") == {"usage": 2}, "session_meta must remain last-write-wins"


def test_blackboard_table_has_no_replace_semantics(tmp_path: Path) -> None:
    """C0: the authority itself must reject a duplicate blackboard id.

    Asserted at the SQL layer so the guarantee does not depend on the Python
    caller checking first. This is the backstop; in correct operation the
    explicit pre-check raises before SQLite is asked to insert.
    """
    db = SessionDatabase(tmp_path / "session.db", session_id=_SESSION)
    row: dict[str, Any] = {
        "id": "raw-dup",
        "session_id": _SESSION,
        "run_id": "",
        "type": "note",
        "content_hash": "h",
        "toolchain_digest": "",
        "schema_version": "v1",
        "parent_id": None,
        "read_set": [],
        "write_set": [],
        "assumptions": [],
        "version_dependencies": {},
        "timestamp": "2026-07-28T00:00:00Z",
        "payload": {},
    }
    db.write_blackboard_row(row)

    conn = sqlite3.connect(db.path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO blackboard (id, session_id, run_id, type, content_hash, "
                "toolchain_digest, schema_version, parent_id, read_set, write_set, "
                "assumptions, version_dependencies, timestamp, payload) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("raw-dup", _SESSION, "", "note", "h2", "", "v1", None, "[]", "[]", "[]", "{}", "t", "{}"),
            )
            conn.commit()
    finally:
        conn.close()
