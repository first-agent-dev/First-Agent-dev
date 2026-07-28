"""S5.1 — event identity must be unique AND lossless under concurrency (V1).

Plan: `worklogs/implementation-plans/PLAN-cli-trace-S5-authority-correctness.md`
§S5-CT1, §3.1, paths S5-P1, S5-P2, S5-P17, S5-P21, S5-P22.

Why these tests exist
---------------------
`EventLog` seeds ``_next_id`` from ``event_count() + 1`` once at construction
(``state.py:171``) and never refreshes it. Two ``EventLog`` instances created
before either writes therefore allocate the same ids. S3 classified this latent;
S4 analysis proved it reachable through the real production root
(``SessionManager.create_or_attach_session -> begin_run -> EventLog``).

Two properties are asserted separately because they fail independently:

* **uniqueness** — no two persisted rows share ``(session_id, event_id)``.
* **no loss** — every attempted append is persisted.

Adding a UNIQUE constraint alone satisfies uniqueness by *dropping* the losing
writer's event, which is strictly worse than the original defect: the event
vanishes from the audit trail. A test that only checks uniqueness would pass
that regression, so the no-loss assertions below are the load-bearing ones.

The multiprocess case (S5-P22) is mandatory and not redundant with the thread
case: an in-process ``threading.Lock`` passes the thread test and still loses
events across processes (plan §3.1(d) measured 6/150 lost). Threads alone cannot
falsify a process-local locking design, and the shipped topology runs separate
``docker compose exec ... fa run`` processes against one ``session.db``.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

from fa.inner_loop.session_db import SessionDatabase
from fa.inner_loop.state import EventLog

# Deterministic, offline, no sleeps in the assertion path. Thread counts are
# small enough to stay fast but large enough that a single-slot race is
# reproducible; the barrier — not timing — is what forces the overlap.
_THREADS = 4
_APPENDS_PER_WORKER = 5
_PROCESSES = 4


def _open_session_db(tmp_path: Path, session_id: str = "s5-session") -> SessionDatabase:
    return SessionDatabase(tmp_path / "session.db", session_id=session_id)


def _persisted(db_path: Path) -> tuple[int, int]:
    """Return (row_count, duplicate_group_count) straight from the authority."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT COUNT(*) FROM event_log").fetchone()[0]
        dupes = conn.execute(
            "SELECT COUNT(*) FROM ("
            "SELECT session_id, event_id FROM event_log "
            "GROUP BY session_id, event_id HAVING COUNT(*) > 1)"
        ).fetchone()[0]
        return int(rows), int(dupes)
    finally:
        conn.close()


def test_sequential_runs_allocate_unique_event_ids(tmp_path: Path) -> None:
    """S5-P2: the S4.4 shape — a second EventLog built after the first finished.

    This passes on current code. It is a regression guard, not a V1 probe: run B
    re-reads the count at construction, so 0 duplicates here is structurally
    guaranteed and must never be cited as evidence that V1 is fixed.
    """
    db = _open_session_db(tmp_path)
    first = EventLog(tmp_path / "events.jsonl", run_id="run-a", session_db=db, session_id="s5-session")
    ids = [first.append(actor="t", kind="usage", content={}).event_id for _ in range(3)]

    second = EventLog(tmp_path / "events.jsonl", run_id="run-b", session_db=db, session_id="s5-session")
    ids += [second.append(actor="t", kind="usage", content={}).event_id for _ in range(3)]

    assert len(set(ids)) == len(ids), f"sequential runs must not collide: {ids}"
    rows, dupes = _persisted(tmp_path / "session.db")
    assert rows == 6
    assert dupes == 0


def test_concurrent_runs_allocate_unique_event_ids(tmp_path: Path) -> None:
    """S5-P1: two EventLogs constructed at the same instant must not collide.

    The barrier is the mechanism under test. Without it the threads serialise by
    startup jitter and the assertion passes against the broken allocator
    (measured: natural concurrency produced 0 duplicates, barrier produced 3).
    """
    db = _open_session_db(tmp_path)
    barrier = threading.Barrier(2)
    collected: dict[str, list[str]] = {}
    errors: list[BaseException] = []

    def worker(run_id: str) -> None:
        try:
            barrier.wait(timeout=10)
            log = EventLog(
                tmp_path / "events.jsonl",
                run_id=run_id,
                session_db=db,
                session_id="s5-session",
            )
            collected[run_id] = [log.append(actor="t", kind="usage", content={}).event_id for _ in range(3)]
        except BaseException as exc:  # noqa: BLE001 — surfaced below, never swallowed
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(f"run-{i}",)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not errors, f"worker raised: {errors!r}"
    allocated = [event_id for ids in collected.values() for event_id in ids]
    assert len(set(allocated)) == len(allocated), f"concurrent allocation collided: {collected}"

    rows, dupes = _persisted(tmp_path / "session.db")
    assert dupes == 0, "duplicate (session_id, event_id) rows reached the authority"
    assert rows == 6


def test_concurrent_appends_lose_no_events(tmp_path: Path) -> None:
    """S5-P21: uniqueness must not be bought with data loss.

    Kill-check for the wrong fix: adding UNIQUE(session_id, event_id) without
    allocating inside the insert transaction makes the losing writer raise
    IntegrityError and drop its event. This asserts the count, so that
    regression fails here even though uniqueness would still hold.
    """
    db = _open_session_db(tmp_path)
    barrier = threading.Barrier(_THREADS)
    errors: list[str] = []
    lock = threading.Lock()

    def worker(index: int) -> None:
        log = EventLog(
            tmp_path / "events.jsonl",
            run_id=f"run-{index}",
            session_db=db,
            session_id="s5-session",
        )
        barrier.wait(timeout=10)
        for _ in range(_APPENDS_PER_WORKER):
            try:
                log.append(actor="t", kind="usage", content={})
            except Exception as exc:  # noqa: BLE001 — a dropped event is the defect under test
                with lock:
                    errors.append(f"{type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(_THREADS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    expected = _THREADS * _APPENDS_PER_WORKER
    rows, dupes = _persisted(tmp_path / "session.db")
    assert not errors, f"appends raised instead of persisting: {errors}"
    assert rows == expected, f"expected {expected} persisted events, found {rows} — events were lost"
    assert dupes == 0, "duplicate (session_id, event_id) rows reached the authority"


_WORKER_SOURCE = textwrap.dedent(
    """
    import json, sys, time
    from pathlib import Path

    src, db_path, jsonl, run_id, gate, per = sys.argv[1:7]
    sys.path.insert(0, src)

    from fa.inner_loop.session_db import SessionDatabase
    from fa.inner_loop.state import EventLog

    db = SessionDatabase(Path(db_path), session_id="s5-session")
    log = EventLog(Path(jsonl), run_id=run_id, session_db=db, session_id="s5-session")

    # Barrier: every process finishes its imports and constructs its EventLog,
    # then waits. Releasing the gate forces the allocator overlap that startup
    # jitter would otherwise hide.
    gate_path = Path(gate)
    deadline = time.monotonic() + 30
    while not gate_path.exists() and time.monotonic() < deadline:
        time.sleep(0.001)

    ok, failed = 0, []
    for _ in range(int(per)):
        try:
            log.append(actor="t", kind="usage", content={})
            ok += 1
        except Exception as exc:
            failed.append(f"{type(exc).__name__}: {exc}")
    print(json.dumps({"ok": ok, "errors": failed}), flush=True)
    """
)


def test_concurrent_appends_across_processes_lose_no_events(tmp_path: Path) -> None:
    """S5-P22: the same invariant across processes — MANDATORY, not redundant.

    An in-process lock passes every thread test above and still loses events
    here, because ``threading.Lock`` does not span processes. The shipped
    topology is separate ``docker compose exec ... fa run`` processes sharing one
    ``session.db``, so this is the test that matches production.
    """
    db_path = tmp_path / "session.db"
    # Create the schema once up front so worker startup does not race on DDL;
    # the property under test is append allocation, not schema bootstrap.
    _open_session_db(tmp_path)

    worker_file = tmp_path / "s5_worker.py"
    worker_file.write_text(_WORKER_SOURCE, encoding="utf-8")
    gate = tmp_path / "GO"
    src_root = str(Path(__file__).resolve().parent.parent / "src")

    procs = [
        subprocess.Popen(  # fixed argv, no shell, test-local paths
            [
                sys.executable,
                str(worker_file),
                src_root,
                str(db_path),
                str(tmp_path / "events.jsonl"),
                f"proc-{i}",
                str(gate),
                str(_APPENDS_PER_WORKER),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for i in range(_PROCESSES)
    ]

    # Give every child time to import fa and construct its EventLog before the
    # gate opens. Generous, because an early release only weakens the test.
    time.sleep(3.0)
    gate.write_text("go", encoding="utf-8")

    reported_ok, reported_errors = 0, []
    for proc in procs:
        out, err = proc.communicate(timeout=90)
        assert proc.returncode == 0, f"worker exited {proc.returncode}: {err[-400:]}"
        payload = json.loads([line for line in out.strip().splitlines() if line.startswith("{")][-1])
        reported_ok += int(payload["ok"])
        reported_errors += list(payload["errors"])

    expected = _PROCESSES * _APPENDS_PER_WORKER
    rows, dupes = _persisted(db_path)
    assert not reported_errors, f"cross-process appends raised: {reported_errors}"
    assert reported_ok == expected, f"workers reported {reported_ok}/{expected} successful appends"
    assert rows == expected, f"expected {expected} persisted events, found {rows} — events were lost"
    assert dupes == 0, "duplicate (session_id, event_id) rows reached the authority"


def test_duplicate_event_id_rejected_by_constraint(tmp_path: Path) -> None:
    """S5-P1 (C0 DDL): the authority must refuse a duplicate (session_id, event_id).

    This is a backstop assertion. In correct operation the allocator never
    produces a duplicate, so this constraint should never fire at runtime — but
    without it, an allocator regression corrupts the trace silently.
    """
    db = _open_session_db(tmp_path)
    log = EventLog(tmp_path / "events.jsonl", run_id="run-a", session_db=db, session_id="s5-session")
    event = log.append(actor="t", kind="usage", content={})

    row = {
        "event_id": event.event_id,
        "ts": event.ts,
        "run_id": event.run_id,
        "actor": event.actor,
        "kind": event.kind,
        "content": {},
        "harness_id": event.harness_id,
        "tool_name": "",
        "tool_call_id": "",
        "parent_event_id": "",
        "session_id": "s5-session",
    }
    with pytest.raises(Exception, match=r"(?i)unique|constraint|duplicate"):
        db.append_event_row(row)
