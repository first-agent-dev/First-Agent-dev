"""S5.4.1 — conflict detection must be scoped to writer identity (Q18).

Contract under test
-------------------
``Blackboard.detect_conflict`` answers the question ADR-16 I-6.3 actually asks:
*did **another** agent touch this path without coordination?* An agent's own
prior entry is its own history, not a conflict with itself.

Why these tests exist (plan §6.0.1 — legacy tests are inputs, not authority)
---------------------------------------------------------------------------
Measured on pristine HEAD ``9ae07f4`` with an isolated ``HOME``: the second
``write_file`` to the same path in the same run is denied by the entry the
*first* ``write_file`` wrote. ``detect_conflict`` had no notion of a writer, so
it could not distinguish "someone else raced me" from "that was me a moment
ago". The existing S5-P5 green signal was produced by that defect rather than
by genuine two-agent detection, so it is re-authored here with two *distinct*
writers.

Industry corroboration for the predicate (recorded in plan §11 Q18): opencode
keys its staleness guard by ``sessionID`` (``FileTime.read``/``FileTime.assert``);
Claude Code's most-reported Edit defect (#48390) is precisely a guard firing on
the agent's own prior edit. Every shipped harness scopes the guard to
"changed by someone other than me".

Test classes: C0 (predicate semantics), C1 (tool-level, real substrate).
"""

from __future__ import annotations

from pathlib import Path

from fa.blackboard.blackboard import Blackboard, BlackboardEntry
from fa.inner_loop import EventLog
from fa.inner_loop.context import reset_current_session, set_current_session
from fa.inner_loop.session_db import SessionDatabase
from fa.inner_loop.state import SessionState
from fa.inner_loop.tools.write_file import build_write_file_tool


def _entry(entry_id: str, path: str) -> BlackboardEntry:
    """A ``file_version`` entry shaped exactly like the one write_file emits."""
    return BlackboardEntry.create(
        id=entry_id,
        type="file_version",
        payload={"path": path},
        read_set=[],
        write_set=[path],
        assumptions=[],
        version_dependencies={"base_commit": "unknown"},
    )


# ---------------------------------------------------------------------------
# C0 — predicate semantics at the Blackboard seam
# ---------------------------------------------------------------------------


def test_entry_carries_writer_run_id_when_read_back(tmp_path: Path) -> None:
    """C0: run_id survives the write->read round trip.

    The ``blackboard`` table has always had a ``run_id`` column and
    ``Blackboard.write`` has always populated it, but ``Blackboard.query``
    dropped it when rebuilding ``BlackboardEntry`` (no such field). Without
    identity on the read path no writer-scoped predicate is expressible.
    """
    db = SessionDatabase(tmp_path / "session.db", session_id="s-1")
    bb = Blackboard(tmp_path / "bb", session_db=db, run_id="run-A", session_id="s-1")

    bb.write(_entry("e1", "f.txt"))

    (read_back,) = bb.query(type="file_version")
    assert read_back.run_id == "run-A", (
        "entry read back from the authority lost its writer identity; "
        "detect_conflict cannot tell self from other without it"
    )


def test_same_run_prior_entry_is_not_a_conflict(tmp_path: Path) -> None:
    """C0: an agent's own earlier entry for the same path must not conflict.

    This is the Q18 defect stated as a contract.
    """
    db = SessionDatabase(tmp_path / "session.db", session_id="s-1")
    bb = Blackboard(tmp_path / "bb", session_db=db, run_id="run-A", session_id="s-1")

    bb.write(_entry("mine-first", "f.txt"))

    conflicts = bb.detect_conflict(_entry("mine-second", "f.txt"))

    assert conflicts == [], (
        "own prior write reported as a conflict — this is the defect that "
        f"blocks iterative editing; got {[c.conflicting_entry_id for c in conflicts]}"
    )


def test_different_run_same_path_still_conflicts(tmp_path: Path) -> None:
    """C0: the guarantee the guard exists for must survive the fix.

    Negative-proof partner of the test above: scoping by writer must not
    degrade into "never conflict". A *different* run touching the same path is
    exactly the write/write overlap ADR-16 I-6.3 requires to fail.
    """
    db = SessionDatabase(tmp_path / "session.db", session_id="s-1")
    bb_a = Blackboard(tmp_path / "bb", session_db=db, run_id="run-A", session_id="s-1")
    bb_b = Blackboard(tmp_path / "bb", session_db=db, run_id="run-B", session_id="s-1")

    bb_a.write(_entry("from-a", "shared.txt"))

    conflicts = bb_b.detect_conflict(_entry("from-b", "shared.txt"))

    assert [c.conflicting_entry_id for c in conflicts] == ["from-a"], (
        "cross-run write/write overlap was not reported — the substrate's core guarantee has been lost"
    )


def test_unattributed_legacy_entries_still_conflict(tmp_path: Path) -> None:
    """C3: rows predating this change carry run_id='' and must fail closed.

    An empty writer id means "unknown writer", which cannot be proven to be
    self. Treating unknown as self would silently un-guard every legacy row in
    an existing session DB, so unknown must remain conflict-eligible.
    """
    db = SessionDatabase(tmp_path / "session.db", session_id="s-1")
    legacy = Blackboard(tmp_path / "bb", session_db=db, run_id="", session_id="s-1")
    legacy.write(_entry("legacy", "f.txt"))

    current = Blackboard(tmp_path / "bb", session_db=db, run_id="run-A", session_id="s-1")
    conflicts = current.detect_conflict(_entry("new", "f.txt"))

    assert [c.conflicting_entry_id for c in conflicts] == ["legacy"], (
        "entry with unknown writer was treated as self — legacy rows would become silently unguarded"
    )


def test_unattributed_writer_does_not_match_unattributed_entry(tmp_path: Path) -> None:
    """C3: unknown-vs-unknown must NOT be treated as the same writer.

    The fail-closed boundary. A naive predicate (``writer == old.run_id``)
    looks correct and passes every other test here, because they all use an
    *attributed* writer. It diverges only when an unattributed writer meets an
    unattributed row: ``"" == ""`` is True, so a legacy Blackboard reading
    legacy rows would treat every one of them as "me" and suppress all
    conflicts — silently disabling the guard on exactly the pre-existing data
    it is most needed for.

    Added after a kill-check (predicate relaxed to ``writer == old.run_id``)
    survived the rest of this file.
    """
    db = SessionDatabase(tmp_path / "session.db", session_id="s-1")
    unattributed = Blackboard(tmp_path / "bb", session_db=db, run_id="", session_id="s-1")
    unattributed.write(_entry("legacy-a", "f.txt"))

    conflicts = unattributed.detect_conflict(_entry("legacy-b", "f.txt"))

    assert [c.conflicting_entry_id for c in conflicts] == ["legacy-a"], (
        "an unknown writer was proven to be 'self' against an unknown row; "
        "identity must be proven, not assumed from two empty strings"
    )


# ---------------------------------------------------------------------------
# C1 — end to end through the real tool and the real substrate
# ---------------------------------------------------------------------------


def test_repeated_write_file_same_path_succeeds(tmp_path: Path) -> None:
    """C1: the user-visible symptom — iterative editing must work.

    Measured on HEAD: write #0 OK, #1 and #2 denied, file left at 'v0' with
    both later writes silently lost.
    """
    state = SessionState(workspace_root=tmp_path, run_id="run-iterative")
    tool = build_write_file_tool(tmp_path)

    token = set_current_session(state)
    try:
        results = [tool.handler({"path": "notes.txt", "content": f"v{i}\n"}) for i in range(3)]
    finally:
        reset_current_session(token)

    codes = [r.error.code if r.error is not None else "ok" for r in results]
    assert codes == ["ok", "ok", "ok"], f"sequential writes to one path were denied: {codes}"
    assert (tmp_path / "notes.txt").read_text(encoding="utf-8") == "v2\n", (
        "later writes did not reach disk — writes were lost, not merely denied"
    )


def test_concurrent_run_write_is_still_denied(tmp_path: Path) -> None:
    """C1: two runs, one path, one session DB — the real conflict still denies.

    Re-authors the plan's S5-P5 row with two *distinct* writers, since the
    original signal was produced by the self-conflict defect.
    """
    # One session authority shared by two runs — the S4.4 shape. The EventLog
    # must reference the same DB or SessionState's authority-identity check
    # (S5-P20) rejects the wiring.
    session_root = tmp_path / "session"
    db = SessionDatabase(session_root / "session.db", session_id="s-shared")
    bb_root = tmp_path / ".fa" / "blackboard"

    def _state(run_id: str) -> SessionState:
        return SessionState(
            workspace_root=tmp_path,
            run_id=run_id,
            session_id="s-shared",
            log=EventLog(
                session_root / run_id / "events.jsonl",
                run_id=run_id,
                session_db=db,
                session_id="s-shared",
            ),
            session_db=db,
            blackboard=Blackboard(bb_root, session_db=db, run_id=run_id, session_id="s-shared"),
        )

    state_a = _state("run-A")
    state_b = _state("run-B")
    tool = build_write_file_tool(tmp_path)

    token = set_current_session(state_a)
    try:
        first = tool.handler({"path": "shared.txt", "content": "from A\n"})
    finally:
        reset_current_session(token)
    assert first.error is None, f"first writer denied: {first.error}"

    token = set_current_session(state_b)
    try:
        second = tool.handler({"path": "shared.txt", "content": "from B\n"})
    finally:
        reset_current_session(token)

    assert second.error is not None, "concurrent cross-run write was allowed"
    assert second.error.code == "conflict_detected"
    assert (tmp_path / "shared.txt").read_text(encoding="utf-8") == "from A\n", "denied write still reached disk"
