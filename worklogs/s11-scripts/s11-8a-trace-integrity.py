"""S11.8a — trace integrity on the deployed box (read-only).

Run inside the agent container, with ``SID`` exported:

    docker compose -f "$COMPOSE" exec -T -e SID="$SID" "$SERVICE" \
      python - < worklogs/s11-scripts/s11-8a-trace-integrity.py

Three guards, each closing a defect this sheet already hit:

* **R16** — an empty ``SID`` collapses the path to
  ``sessions/session.db`` and ``sqlite3.connect()`` *creates* that file, so a
  later ``COUNT(*)`` would return 0 and read as "clean". The script refuses to
  run without a ``SID``, refuses when the database does not already exist, and
  opens ``mode=ro`` so a stray connect can never fabricate one.
* **Vacuity** — every count is printed next to a positive control
  (``runs found``, ``total rows``), so "0 orphans" is distinguishable from
  "read nothing at all".
* **Read-only** — this is a verification step on live infrastructure; it must
  not be able to mutate state.
"""

from __future__ import annotations

import os
import pathlib
import sqlite3
import sys
import tempfile

# Roots scanned for stray authorities. `/tmp` is deliberate: a session.db there
# is exactly the anomaly this check exists to surface, so the path is data to be
# *inspected*, never a location this script writes to.
# ``tempfile.gettempdir()`` rather than a "/tmp" literal: same directory, and
# it follows TMPDIR on a host that relocates it — so the scan cannot miss a
# stray authority that landed in a non-default temp root.
_SCAN_ROOTS = ("/home/fa", "/sessions", tempfile.gettempdir())

_STATE = pathlib.Path("/home/fa/.fa")


def main() -> int:
    sid = os.environ.get("SID", "").strip()
    if not sid:
        print("STOP: SID is empty. sqlite3.connect() would CREATE an empty db and")
        print("      every query would fail with 'no such table: event_log'.")
        return 2
    if not sid.startswith("session-"):
        print(f"STOP: SID={sid!r} is not shaped 'session-<id>'; refusing.")
        return 2

    db = _STATE / "sessions" / sid / "session.db"
    if not db.is_file():
        print(f"STOP: no session.db at {db}")
        print("      (connect() would create one and every count would read 0)")
        return 2

    print(f"db: {db} bytes: {db.stat().st_size}")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)

    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    print(f"tables: {tables}")
    if "event_log" not in tables:
        print("STOP: event_log absent — wrong db or an empty file")
        return 2

    print("=== rows per run (authority) ===")
    rows = list(con.execute("SELECT run_id, COUNT(*) FROM event_log GROUP BY run_id ORDER BY run_id"))
    for run, n in rows:
        print(f"  {run}: {n}")
    print(f"  (positive control) runs found: {len(rows)}")

    print("=== authority vs JSONL mirror ===")
    for run, n in rows:
        mirror = _STATE / "session-log" / str(run) / "events.jsonl"
        if mirror.is_file():
            with mirror.open(encoding="utf-8") as handle:
                seen: int | str = sum(1 for line in handle if line.strip())
            verdict = "MATCH" if seen == n else "MISMATCH"
        else:
            seen, verdict = "NO_MIRROR", "MISSING"
        print(f"  {run}: db={n} jsonl={seen} {verdict}")

    print("=== orphan check ===")
    orphans = con.execute("SELECT COUNT(*) FROM event_log WHERE run_id IS NULL OR run_id=''").fetchone()[0]
    total = con.execute("SELECT COUNT(*) FROM event_log").fetchone()[0]
    print(f"  orphans: {orphans}")
    print(f"  (positive control) total rows: {total}")

    print("=== session_id stamping (S4-F1) ===")
    session_ids = con.execute("SELECT DISTINCT session_id FROM event_log").fetchall()
    print(f"  distinct session_id: {session_ids}")

    print("=== correlation ===")
    correlated = con.execute(
        "SELECT COUNT(*) FROM event_log WHERE tool_call_id IS NOT NULL AND tool_call_id<>''"
    ).fetchone()[0]
    print(f"  with tool_call_id: {correlated}")

    print("=== stray authorities on disk ===")
    for base in _SCAN_ROOTS:
        root = pathlib.Path(base)
        if not root.is_dir():
            print(f"  {base}: PATH ABSENT")
            continue
        hits = sorted(root.rglob("session.db"))
        print(f"  {base}: {len(hits)} session.db")
        for hit in hits[:10]:
            print(f"    {hit}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
