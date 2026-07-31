# PLAN: S7-container — operator live-verification sheet

Plan-ID: `PLAN-cli-trace-S7-container-verification`

Status: **READY FOR OPERATOR EXECUTION** (run after deploying the S7 branch)

Depth: **P1** — evidence-gathering on a live deployment. **No source edits.**

Parent plan:
[`cli-trace-substrate-rebaseline-2026-07-25.md`](./cli-trace-substrate-rebaseline-2026-07-25.md) §Step S7 Do #10

Local half: [`PLAN-cli-trace-S7-direct-run-vertical-slice.md`](./PLAN-cli-trace-S7-direct-run-vertical-slice.md)

Prior protocol this mirrors:
[`PLAN-cli-trace-S4-direct-container-baseline.md`](./PLAN-cli-trace-S4-direct-container-baseline.md)

---

## 0. Scope and execution boundary

### IDEA

S7's local half proves the `fa run` composition against a mocked transport. The
parent's §Do-not is explicit: *"do not mark the slice L3 based on local fake
transport alone."* This sheet is the deployed counterpart — it converts three
S7 exit criteria (container DB/events/body metadata, redaction evidence,
source/image drift) from PENDING to evidence.

It also carries one thing S4 could not: S7 changes `inner-loop-smoke` (S4-F1),
so **S7.C6 is a regression check on the exact artifact S4 found in production.**

### CONCRETE INTENT

Answer with recorded output, not inference:

```text
Is the running image built from the S7 commit?
Does one `fa run` still produce exactly one run dir and one authoritative DB?
Do DB counts and the JSONL mirror agree on the deployed path?
Does FA_DEBUG_LLM_BODIES gate body capture in BOTH states, by count only?
Does --detail debug leave body capture OFF? (matrix cell C, the coupling risk)
Does --output-mode quiet keep stderr clean while the DB still fills?
Is the S4-F1 session-less session.db gone, and is the smoke DB now labelled?
Do run_id / event_id / tool_call_id correlate on real data?
```

### GOALS

- **S7C-G1** — record deployment identity; rule out source/image drift.
- **S7C-G2** — prove the debug-body gate in both states, counts only.
- **S7C-G3** — prove `--detail debug` is not the body gate (matrix C).
- **S7C-G4** — prove quiet mode's stdout/stderr contract on the real path.
- **S7C-G5** — prove S4-F1 is closed on the deployment that exhibited it.
- **S7C-G6** — prove correlation joins on real trace rows.

### NON-GOALS

- No edits under `src/`, `tests/`, `scripts/` during execution.
- No fixes for anything found — record and classify, as in S4.
- **Never print `llm_bodies.jsonl` contents, prompt text, or key values.**
  Counts, byte sizes and key *names* only (ADR-12).
- No `scripts/fa` wrapper — use `docker compose exec` directly (parent §Do-not).
- No workflow runs (S8), no stats projections (S9).

### STOP RULE

If any step's ACTUAL differs from EXPECTED, **record and continue** unless it
blocks the next step. Do not fix. If a command would print body content, stop
and report instead.

---

## 1. Preconditions

```bash
# Set once per session. Adjust if your paths differ.
export COMPOSE=/srv/first-agent/repo/First-Agent-dev/docker-compose.fa.yml
export SERVICE=first-agent

# Sanity: compose file resolves and the service is up.
docker compose -f "$COMPOSE" ps
```

**Expect:** the service listed and running. If not, start it the usual way
before continuing.

---

## Step S7.C0 — Deployment identity (rule out drift)

Traces-to: S7C-G1.

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  echo "--- in-container source revision"
  cd /repo 2>/dev/null && git rev-parse --short HEAD 2>/dev/null || echo "no /repo git"
  echo "--- installed fa resolves to"
  python -c "import fa,sys; sys.stdout.write(fa.__file__+chr(10))"
  echo "--- /workspace/src shadowing?"
  [ -d /workspace/src/fa ] && echo "SHADOW PRESENT: /workspace/src/fa" || echo "no shadow"
  echo "--- fa version/help sanity"
  fa --help >/dev/null 2>&1 && echo "fa OK" || echo "fa FAILED"
'
```

**Expect:** the revision matches the S7 commit you deployed; `fa.__file__`
resolves where you expect; shadowing state recorded either way.

**Record the revision — every later step is only as good as this line.**

---

## Step S7.C1 — Matrix A: debug OFF, console (baseline run)

Traces-to: S7C-G2. Depends-on: S7.C0.

```bash
# 1a. Collision check — these ids must not already exist.
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  for d in /home/fa/.fa/sessions/s7-verify /home/fa/.fa/session-log/s7-run-a; do
    [ -e "$d" ] && echo "COLLISION: $d — run §Rollback first" || echo "clear: $d"
  done
'

# 1b. THE RUN — matrix cell A.
docker compose -f "$COMPOSE" exec -T \
  -e FA_DEBUG_LLM_BODIES=0 \
  "$SERVICE" \
  fa run --task "Reply with the single word: pong" \
         --session-id s7-verify \
         --run-id s7-run-a \
         --role coder \
         --max-turns 1 \
         --output-mode console
echo "EXIT_CODE=$?"

# 1c. Topology after the run.
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  echo "--- session dir"; ls -lh /home/fa/.fa/sessions/s7-verify
  echo "--- run dir";     ls -lh /home/fa/.fa/session-log/s7-run-a
  echo "--- body file present?"
  [ -f /home/fa/.fa/session-log/s7-run-a/llm_bodies.jsonl ] \
    && echo "PRESENT  <-- unexpected for cell A" || echo "absent   <-- expected"
'
```

**Expect:** exit 0; `manifest.json` + `session.db` in the session dir; a run
dir; **no** `llm_bodies.jsonl`.

---

## Step S7.C2 — Authority vs mirror agreement (counts only)

Traces-to: S7C-G2, S7C-G6. Depends-on: S7.C1.

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
python - <<PY
import json, sqlite3, pathlib
db = pathlib.Path("/home/fa/.fa/sessions/s7-verify/session.db")
mirror = pathlib.Path("/home/fa/.fa/session-log/s7-run-a/events.jsonl")

con = sqlite3.connect(db)
rows = con.execute("SELECT COUNT(*) FROM event_log").fetchone()[0]
scoped = con.execute(
    "SELECT COUNT(*) FROM event_log WHERE run_id=?", ("s7-run-a",)).fetchone()[0]
empty_sid = con.execute(
    "SELECT COUNT(*) FROM event_log WHERE session_id=\"\"").fetchone()[0]
dupes = con.execute(
    "SELECT COUNT(*) FROM (SELECT event_id FROM event_log "
    "GROUP BY session_id,event_id HAVING COUNT(*)>1)").fetchone()[0]
kinds = con.execute(
    "SELECT kind, COUNT(*) FROM event_log WHERE run_id=? GROUP BY kind ORDER BY 2 DESC",
    ("s7-run-a",)).fetchall()

mirror_lines = sum(1 for _ in mirror.open()) if mirror.exists() else -1
print("db rows total        :", rows)
print("db rows for run      :", scoped)
print("jsonl mirror lines   :", mirror_lines)
print("rows w/ EMPTY sid    :", empty_sid, "  (expect 0)")
print("duplicate event_ids  :", dupes, "  (expect 0)")
print("kinds                :", kinds)
PY
'
```

**Expect:** `db rows for run == jsonl mirror lines`; **0** empty-`session_id`
rows; **0** duplicate ids. Kinds are metadata — safe to paste.

---

## Step S7.C3 — Correlation joins on real data

Traces-to: S7C-G6. Depends-on: S7.C2.

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
python - <<PY
import sqlite3
con = sqlite3.connect("/home/fa/.fa/sessions/s7-verify/session.db")
cols = [r[1] for r in con.execute("PRAGMA table_info(event_log)")]
print("event_log columns:", cols)
print()
print("run_id | event_id | tool_call_id | kind   (first 12 rows, ids only)")
for r in con.execute(
    "SELECT run_id, event_id, tool_call_id, kind FROM event_log "
    "WHERE run_id=? ORDER BY event_id LIMIT 12", ("s7-run-a",)):
    print("  ", r)
orphan = con.execute(
    "SELECT COUNT(*) FROM event_log WHERE run_id=? AND (run_id IS NULL OR run_id=\"\")",
    ("s7-run-a",)).fetchone()[0]
print()
print("rows missing run_id:", orphan, " (expect 0)")
PY
'
```

**Expect:** every row carries the run id; `tool_call_id` present on tool rows
and empty on non-tool rows (that is the documented non-join, not a defect).
**Only identifiers are printed — no content.**

---

## Step S7.C4 — Matrix B and C: the body gate and the coupling risk

Traces-to: S7C-G2, S7C-G3. Depends-on: S7.C1.

This is the sharpest step. Preflight found `FA_DEBUG_LLM_BODIES` has **zero
references in `cli.py`** — the gate lives only in
`providers/debug_bodies.py:58,101`. Cell C proves `--detail debug` does **not**
turn body capture on.

```bash
# 4a. Cell C — debug RENDERING on, env gate OFF. Body capture must stay off.
docker compose -f "$COMPOSE" exec -T \
  -e FA_DEBUG_LLM_BODIES=0 \
  "$SERVICE" \
  fa run --task "Reply with the single word: pong" \
         --session-id s7-verify \
         --run-id s7-run-c \
         --role coder --max-turns 1 --detail debug
echo "EXIT_CODE_C=$?"

# 4b. Cell B — env gate ON. Body capture must appear.
docker compose -f "$COMPOSE" exec -T \
  -e FA_DEBUG_LLM_BODIES=1 \
  "$SERVICE" \
  fa run --task "Reply with the single word: pong" \
         --session-id s7-verify \
         --run-id s7-run-b \
         --role coder --max-turns 1
echo "EXIT_CODE_B=$?"

# 4c. Compare — COUNTS AND SIZES ONLY. Never cat these files.
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  for r in s7-run-c s7-run-b; do
    f=/home/fa/.fa/session-log/$r/llm_bodies.jsonl
    if [ -f "$f" ]; then
      echo "$r: PRESENT lines=$(wc -l < "$f") bytes=$(stat -c%s "$f")"
    else
      echo "$r: absent"
    fi
  done
'
```

**Expect:** `s7-run-c` **absent** (cell C — debug rendering is not the gate);
`s7-run-b` **PRESENT** with a non-zero line count (cell B).

**If `s7-run-c` is PRESENT, stop and report** — that is a real coupling defect,
and it is the specific regression this cell exists to catch.

---

## Step S7.C5 — Matrix D: quiet mode contract

Traces-to: S7C-G4. Depends-on: S7.C1.

```bash
docker compose -f "$COMPOSE" exec -T \
  -e FA_DEBUG_LLM_BODIES=0 \
  "$SERVICE" \
  fa run --task "Reply with the single word: pong" \
         --session-id s7-verify --run-id s7-run-d \
         --role coder --max-turns 1 \
         --output-mode quiet --no-color \
  >/tmp/s7d.out 2>/tmp/s7d.err
echo "EXIT_CODE_D=$?"

echo "--- stdout bytes: $(wc -c </tmp/s7d.out)   stderr bytes: $(wc -c </tmp/s7d.err)"
echo "--- stderr (first 20 lines, expected near-empty)"; head -20 /tmp/s7d.err
echo "--- did the DB still fill?"
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
python - <<PY
import sqlite3
con = sqlite3.connect("/home/fa/.fa/sessions/s7-verify/session.db")
print("rows for s7-run-d:",
      con.execute("SELECT COUNT(*) FROM event_log WHERE run_id=?", ("s7-run-d",)).fetchone()[0])
PY
'
```

**Expect:** quiet mode suppresses the live renderer on stderr **while the DB
still fills** — silence on the console must never mean silence in the trace.

---

## Step S7.C6 — S4-F1 regression check (the artifact S4 found live)

Traces-to: S7C-G5. Depends-on: S7.C0.

S4 found `inner-loop-smoke` creating a second, **session-less** `session.db`.
S7.5 changes it to a labelled authority under `.fa/smoke/`. This step verifies
the fix on the deployment that exhibited the bug.

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  W=/tmp/s7-smoke; rm -rf "$W"; mkdir -p "$W"
  echo "hello" > "$W/in.txt"
  cd "$W" && fa inner-loop-smoke --workspace "$W" --input in.txt --output out.txt
  echo "SMOKE_EXIT=$?"

  echo "--- OLD artifact (must be ABSENT after the fix)"
  [ -f "$W/.fa/session.db" ] && echo "PRESENT  <-- S4-F1 NOT fixed" || echo "absent   <-- expected"

  echo "--- NEW labelled authority (must be PRESENT)"
  [ -f "$W/.fa/smoke/session.db" ] && echo "present  <-- expected" || echo "ABSENT   <-- fix not deployed"

  echo "--- identity on the smoke DB"
  python - <<PY
import sqlite3, pathlib
p = pathlib.Path("/tmp/s7-smoke/.fa/smoke/session.db")
if not p.exists():
    print("no smoke db to inspect"); raise SystemExit
con = sqlite3.connect(p)
try:
    sids = con.execute("SELECT DISTINCT session_id FROM event_log").fetchall()
    print("distinct session_id values:", sids, " (expect [(\"cli-smoke\",)], NOT [(\"\",)])")
except Exception as exc:
    print("query failed:", exc)
PY
'
```

**Expect:** old `.fa/session.db` **absent**; `.fa/smoke/session.db` present;
`session_id` = `cli-smoke`, **not** empty.

**Why this matters beyond tidiness:** an empty `session_id` disables the
write-identity guards (`if self.session_id and ...`), so the old artifact
accepted rows stamped for any session. Measured locally — see the S7 plan §9 Q28.

---

## Step S7.C7 — Post-run hygiene

Traces-to: S7C-G1.

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  echo "--- runs created (expect exactly the four s7-run-* ids)"
  ls -1 /home/fa/.fa/session-log | grep "^s7-run-" || echo none
  echo "--- stray session.db anywhere under the workspace?"
  find /workspace -name session.db 2>/dev/null | head
  echo "--- host repo cleanliness (should be unchanged by a run)"
  cd /repo 2>/dev/null && git status --short | head || echo "no /repo git"
'
```

**Expect:** exactly `s7-run-a`, `-b`, `-c`, `-d`; no stray `session.db` under
`/workspace`; the repo not dirtied by running.

---

## 2. Evidence template

For each step, record:

```text
STEP:      S7.Cx
COMMAND:   <exact command run>
EXIT:      <code>
EXPECTED:  <from this sheet>
ACTUAL:    <verbatim output; body files never printed>
VERDICT:   MATCH | MISMATCH | BLOCKED
IF MISMATCH: classify only — do not fix.
```

---

## 3. Definition of Done

- [ ] S7.C0 deployment revision recorded and matches the deployed S7 commit.
- [ ] S7.C1 cell A: run completes, topology correct, no body file.
- [ ] S7.C2 DB/mirror counts agree; 0 empty-`session_id` rows; 0 duplicate ids.
- [ ] S7.C3 correlation joins hold on real rows; non-joins documented.
- [ ] S7.C4 cell C absent **and** cell B present — the gate is the env var alone.
- [ ] S7.C5 quiet suppresses the console while the DB still fills.
- [ ] S7.C6 S4-F1 closed on the live deployment; smoke DB labelled `cli-smoke`.
- [ ] S7.C7 no stray authorities; repo not dirtied.
- [ ] Every mismatch classified with an owner; **zero fixes applied**.

### Negative proof

This sheet is invalid if any row is marked verified from a **local** test
rather than container output, or if body-file contents appear anywhere in the
record.

---

## 4. Rollback

All artifacts live inside the container.

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  rm -rf /home/fa/.fa/sessions/s7-verify \
         /home/fa/.fa/session-log/s7-run-a \
         /home/fa/.fa/session-log/s7-run-b \
         /home/fa/.fa/session-log/s7-run-c \
         /home/fa/.fa/session-log/s7-run-d \
         /tmp/s7-smoke
'
rm -f /tmp/s7d.out /tmp/s7d.err
```

No host state, no source, no image change.
