> **Status:** archived 2026-08-25 — moved from implementation-plans per 30-day rule

# PLAN: S7-container — operator live-verification sheet

Plan-ID: `PLAN-cli-trace-S7-container-verification`

Status: **EXECUTED 2026-07-30** — all eight steps run on `6262e7d`; see §3
Execution record. Four findings raised (I-36…I-39), zero fixes applied.

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

> **Corrected 2026-07-30, during operator execution.** The first version of
> this step passed `--session-id s7-verify` on the *first* run and failed with
> `unknown_session` (exit 2). That was a defect in this sheet, not in the CLI.
>
> `--session-id` **attaches to an existing session; it never creates one** —
> `manager.py:286` reads `if session_id is not None: return self._attach_session(...)`,
> and `--help` says "Attach to an existing persistent session; omit to create a
> new session." Session ids are always auto-generated as `session-<uuid4hex>`,
> so the id cannot be chosen. `--run-id` **is** free-form, and every later step
> keys on it.
>
> Corrected flow: create by **omitting** `--session-id`, capture the generated
> id into `$SID`, and attach with `$SID` from C4 onward.

```bash
# 1a. Collision check — the run ids this sheet uses must not already exist.
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  for d in /home/fa/.fa/session-log/s7-run-a /home/fa/.fa/session-log/s7-run-b \
           /home/fa/.fa/session-log/s7-run-c /home/fa/.fa/session-log/s7-run-d; do
    [ -e "$d" ] && echo "COLLISION: $d — run §Rollback first" || echo "clear: $d"
  done
'

# 1b. THE RUN — matrix cell A. No --session-id: this CREATES the session.
docker compose -f "$COMPOSE" exec -T \
  -e FA_DEBUG_LLM_BODIES=0 \
  "$SERVICE" \
  fa run --task "Reply with the single word: pong" \
         --run-id s7-run-a \
         --role coder \
         --max-turns 1 \
         --output-mode console
echo "EXIT_CODE=$?"

# 1c. Capture the generated session id — every later step needs it.
SID=$(docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
python - <<PY
import json, pathlib, sqlite3
best = None
for m in sorted(pathlib.Path("/home/fa/.fa/sessions").glob("*/manifest.json")):
    d = json.loads(m.read_text())
    if d.get("status") != "active":
        continue
    db = m.parent / "session.db"
    try:
        n = sqlite3.connect(db).execute(
            "SELECT COUNT(*) FROM event_log WHERE run_id=?", ("s7-run-a",)).fetchone()[0]
    except Exception:
        n = 0
    if n:
        best = d["session_id"]
print(best or "")
PY' | tr -d "\r" | tail -1)
export SID
echo "SID=$SID"

# 1d. Topology after the run.
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc "
  echo '--- session dir'; ls -lh /home/fa/.fa/sessions/$SID
  echo '--- run dir';     ls -lh /home/fa/.fa/session-log/s7-run-a
  echo '--- body file present?'
  [ -f /home/fa/.fa/session-log/s7-run-a/llm_bodies.jsonl ] \
    && echo 'PRESENT  <-- unexpected for cell A' || echo 'absent   <-- expected'
"
```

**Expect:** exit 0; `SID` non-empty, shaped `session-<32 hex>`; `manifest.json`
+ `session.db` in the session dir; a run dir; **no** `llm_bodies.jsonl`.

`SID` is resolved by finding the active session whose `session.db` actually
holds `s7-run-a` rows, so a pre-existing session from earlier experimentation
cannot be picked up by mistake. **If `SID` is empty, stop** — every later step
depends on it.

---

## Step S7.C2 — Authority vs mirror agreement (counts only)

Traces-to: S7C-G2, S7C-G6. Depends-on: S7.C1.

```bash
docker compose -f "$COMPOSE" exec -T -e SID="$SID" "$SERVICE" sh -lc '
python - <<PY
import json, sqlite3, pathlib
db = pathlib.Path("/home/fa/.fa/sessions/$SID/session.db")
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
docker compose -f "$COMPOSE" exec -T -e SID="$SID" "$SERVICE" sh -lc '
python - <<PY
import sqlite3
con = sqlite3.connect("/home/fa/.fa/sessions/$SID/session.db")
cols = [r[1] for r in con.execute("PRAGMA table_info(event_log)")]
print("event_log columns:", cols)
print()
print("run_id | event_id | tool_call_id | kind   (first 12 rows, ids only)")
for r in con.execute(
    "SELECT run_id, event_id, tool_call_id, kind FROM event_log "
    "WHERE run_id=? ORDER BY event_id LIMIT 12", ("s7-run-a",)):
    print("  ", r)
total = con.execute("SELECT COUNT(*) FROM event_log").fetchone()[0]
orphan = con.execute(
    "SELECT COUNT(*) FROM event_log WHERE run_id IS NULL OR run_id=\"\"").fetchone()[0]
by_run = con.execute(
    "SELECT run_id, COUNT(*) FROM event_log GROUP BY run_id ORDER BY run_id").fetchall()
sid_mix = con.execute("SELECT DISTINCT session_id FROM event_log").fetchall()
print()
print("rows in table (all runs):", total)
print("rows missing run_id    :", orphan, " (expect 0)")
print("rows per run_id        :", by_run)
print("distinct session_id    :", sid_mix, " (expect exactly one, non-empty)")
PY
'
```

**Expect:** every row carries the run id; `tool_call_id` present on tool rows
and empty on non-tool rows (that is the documented non-join, not a defect).
**Only identifiers are printed — no content.**

> **Sheet defect found during execution (2026-07-30), corrected above.**
> The original orphan query was
> `WHERE run_id=? AND (run_id IS NULL OR run_id="")` — a contradiction that
> returns `0` on *every* database, including one full of orphans (verified
> against an in-memory table seeded with 3 real orphans: the query still
> printed `0`). It proved nothing. The replacement counts orphans over the
> whole table with no run predicate, and adds a per-`run_id` histogram plus a
> `session_id` cardinality check so the zero is falsifiable.

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
         --session-id "$SID" \
         --run-id s7-run-c \
         --role coder --max-turns 1 --detail debug
echo "EXIT_CODE_C=$?"

# 4b. Cell B — env gate ON. Body capture must appear.
docker compose -f "$COMPOSE" exec -T \
  -e FA_DEBUG_LLM_BODIES=1 \
  "$SERVICE" \
  fa run --task "Reply with the single word: pong" \
         --session-id "$SID" \
         --run-id s7-run-b \
         --role coder --max-turns 1
echo "EXIT_CODE_B=$?"

# 4c. Compare — COUNTS AND SIZES ONLY. Never cat these files.
#     Each absence is reported WITH its positive control, so "absent" cannot
#     be confused with "the run never happened".
docker compose -f "$COMPOSE" exec -T -e SID="$SID" "$SERVICE" sh -lc '
python - <<PY
import pathlib, sqlite3
con = sqlite3.connect("/home/fa/.fa/sessions/$SID/session.db")
for r in ("s7-run-c", "s7-run-b"):
    d = pathlib.Path("/home/fa/.fa/session-log") / r
    f = d / "llm_bodies.jsonl"
    ev = d / "events.jsonl"
    rows = con.execute(
        "SELECT COUNT(*) FROM event_log WHERE run_id=?", (r,)).fetchone()[0]
    llm = con.execute(
        "SELECT COUNT(*) FROM event_log WHERE run_id=? AND kind=?",
        (r, "llm_call")).fetchone()[0]
    state = (
        f"PRESENT lines={sum(1 for _ in f.open())} bytes={f.stat().st_size}"
        if f.exists() else "absent"
    )
    print(f"{r}: bodies={state}")
    print(f"{r}:   control -> run_dir={d.is_dir()} events.jsonl={ev.exists()} "
          f"db_rows={rows} llm_call_rows={llm}")
PY
'
```

**Expect:**

| run | env gate | `--detail` | `llm_bodies.jsonl` | control |
|---|---|---|---|---|
| `s7-run-c` | `0` | `debug` | **absent** | `db_rows>0`, `llm_call_rows>=1` |
| `s7-run-b` | `1` | default | **PRESENT**, lines ≥ 1 | `db_rows>0`, `llm_call_rows>=1` |

Read the two cells together: C has debug rendering **on** and no bodies, B has
debug rendering **off** and bodies. That makes `FA_DEBUG_LLM_BODIES` both
**necessary and sufficient**, and `--detail` **neither** — which is the whole
claim.

**If `s7-run-c` shows `PRESENT`, stop and report** — that is a real coupling
defect, and it is the specific regression this cell exists to catch.

```bash
# 4d. File mode of the body file — metadata only, never contents.
#     Added 2026-07-30: locally the file lands at 0644 while the session
#     manifest is written 0600 (manager.py:133). Confirm on the deployment.
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  f=/home/fa/.fa/session-log/s7-run-b/llm_bodies.jsonl
  echo "umask: $(umask)"
  stat -c "%a %U:%G %n" "$f" 2>/dev/null || echo "no body file"
  stat -c "%a %U:%G %n" "$(dirname "$f")"
  stat -c "%a %U:%G %n" /home/fa/.fa/sessions/*/manifest.json 2>/dev/null | head -1
'
```

**Expect (to be classified, not fixed):** if the body file is `644` while
`manifest.json` is `600`, record it as a finding — a Tier-3 file the module's
own docstring describes as carrying "UC5-sensitive context" is more permissive
than the session manifest beside it. Single-user container, so severity is low;
it matters for multi-tenant hosts and for anything that copies the directory
out.

**If `s7-run-c` shows `absent` but its control line shows `db_rows=0` or
`llm_call_rows=0`, the cell proved nothing** and must be re-run: a run that
never reached the provider cannot demonstrate that the provider path skipped
body capture. Same rule for `s7-run-b`. This positive control was added
2026-07-30 after S7.C3 shipped an unfalsifiable check (see the note in that
step); an absence assertion without a liveness witness is the same class of
mistake.

---

## Step S7.C4b — Request anatomy: what the provider actually receives

Traces-to: S7C-G2 (extension). Depends-on: S7.C4. **Added 2026-07-30** at
operator request, after the 58 KB body file for a one-word task.

The sheet proved *whether* bodies are captured. It never asked *what is in
them*. A 58 KB request for `Reply with the single word: pong` is a number that
deserves an explanation rather than a shrug.

**This step prints STRUCTURE AND SIZES ONLY — never content.** It reports key
names, byte counts per message, and tool *names*. It never prints prompt text,
response text, or any value. That keeps it inside §0 NON-GOALS and ADR-12.

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
python - <<PY
import json, pathlib
p = pathlib.Path("/home/fa/.fa/session-log/s7-run-b/llm_bodies.jsonl")
row = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
rb = row["request_body"]
total = len(json.dumps(rb))
print("top-level row keys :", sorted(row))
print("request_body keys  :", sorted(rb))
print("total request bytes:", f"{total:,}")
print()
print("--- messages (role, bytes) — NO CONTENT")
for i, m in enumerate(rb.get("messages", [])):
    c = m.get("content")
    n = len(c) if isinstance(c, str) else len(json.dumps(c))
    role = str(m.get("role"))
    print(f"  [{i}] role={role:9s} bytes={n:7,}  {n/total:5.1%}")
print()
tools = rb.get("tools") or []
tb = len(json.dumps(tools))
print(f"--- native tools array: {len(tools)} tools, {tb:,} bytes ({tb/total:.1%})")
print("    names:", [t.get("function", {}).get("name") or t.get("name") for t in tools])
print()
sysmsgs = [m for m in rb.get("messages", []) if m.get("role") == "system"]
inline = [m for m in sysmsgs if isinstance(m.get("content"), str)
          and m["content"].startswith("Tools for role")]
if inline:
    ib = len(inline[0]["content"])
    print(f"!!! INLINE tool listing ALSO present: {ib:,} bytes ({ib/total:.1%})")
    print(f"!!! tool schemas transmitted TWICE: {ib+tb:,} bytes = {(ib+tb)/total:.0%} of request")
else:
    print("no inline tool listing (only the native tools array)")
print()
print("--- response_body keys:", sorted(row.get("response_body", {})))
print("--- cache/meta fields :",
      {k: rb[k] for k in ("model", "max_tokens", "temperature",
                          "prompt_cache_key", "prompt_cache_retention") if k in rb})
PY
'
```

**Expect (predicted from the local capture — see BACKLOG I-37):** roughly
21% base system prompt, **43% an inline JSON tool listing**, **31% the native
`tools` array**, and a fraction of a percent for the actual task. The inline
listing and the native array carry the **same 16 schemas**, so ~73% of every
request is tool schemas sent twice.

`prompt_cache_key` should be present and stable across runs in this session —
that is what produced `cache=100%` on run B.

**This step classifies, it does not fix.** If the duplication is confirmed on
the deployment, it is recorded as **I-37** and addressed after S7 closes, behind
a feature flag with an eval-corpus A/B — deleting the inline block unmeasured
would be a silent change to prompt composition.

---

## Step S7.C5 — Matrix D: quiet mode contract

Traces-to: S7C-G4. Depends-on: S7.C1.

```bash
docker compose -f "$COMPOSE" exec -T \
  -e FA_DEBUG_LLM_BODIES=0 \
  "$SERVICE" \
  fa run --task "Reply with the single word: pong" \
         --session-id "$SID" --run-id s7-run-d \
         --role coder --max-turns 1 \
         --output-mode quiet --no-color \
  >/tmp/s7d.out 2>/tmp/s7d.err
echo "EXIT_CODE_D=$?"

echo "--- stdout bytes: $(wc -c </tmp/s7d.out)   stderr bytes: $(wc -c </tmp/s7d.err)"
echo "--- stderr (first 20 lines, expected near-empty)"; head -20 /tmp/s7d.err
echo "--- did the DB still fill?"
docker compose -f "$COMPOSE" exec -T -e SID="$SID" "$SERVICE" sh -lc '
python - <<PY
import sqlite3
con = sqlite3.connect("/home/fa/.fa/sessions/$SID/session.db")
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

- [x] S7.C0 deployment revision recorded (`6262e7d`), no `/workspace/src` shadow.
- [x] S7.C1 cell A: run completes, topology correct, no body file.
- [x] S7.C2 DB/mirror counts agree (7/7/7); 0 empty-`session_id`; 0 duplicate ids.
- [x] S7.C3 correlation joins hold on real rows; non-joins documented.
- [x] S7.C4 cell C absent **and** cell B present — the gate is the env var alone.
- [x] S7.C4b request anatomy recorded (added mid-execution; → I-37, I-39).
- [x] S7.C5 quiet suppresses the console while the DB still fills — **trace
      contract MATCH, stdout contract MISMATCH (34 B) → Q31 / I-38**.
- [x] S7.C6 S4-F1 closed on the live deployment; smoke DB labelled `cli-smoke`.
- [x] S7.C7 no stray authorities; repo not dirtied *(see C7 caveat)*.
- [x] Every mismatch classified with an owner; **zero fixes applied**.

### Execution record — operator, 2026-07-30

Run against deployment revision **`6262e7d`**, service `first-agent`, session
`session-b7be56181af34c5198edb3ff7edffa00`.

| Step | Verdict | Key evidence |
|---|---|---|
| S7.C0 | MATCH | `6262e7d`; `fa` resolves to `/opt/first-agent/src/fa/__init__.py`; no `/workspace/src` shadow |
| S7.C1 | MATCH | exit 0; `SID=session-b7be…fa00`; manifest `600` + `session.db`; **no** `llm_bodies.jsonl` |
| S7.C2 | MATCH | db 7 = run 7 = mirror 7; 0 empty sid; 0 dup ids; 7 distinct kinds |
| S7.C3 | MATCH | 12-col schema; all rows `s7-run-a`; orphans 0; `[('s7-run-a', 7)]`; one non-empty sid |
| S7.C4 | MATCH | `s7-run-c` **absent** (debug rendering on), `s7-run-b` **PRESENT** 58,095 B; both controls `llm_call_rows=1` |
| S7.C4b | RECORDED | 57,853 B request; AGENTS.md map 48.4%; tool schemas twice = 36%; `prompt_cache_retention` missing |
| S7.C5 | **PARTIAL** | stderr **0 B**, DB **7 rows** ✅ · stdout **34 B** ❌ vs docstring → **Q31 / I-38** |
| S7.C6 | MATCH | old `.fa/session.db` **absent**; `.fa/smoke/session.db` **present**; `session_id = [('cli-smoke',)]` |
| S7.C7 | MATCH* | exactly `s7-run-a/-b/-c/-d`; no stray `session.db`; repo undirtied |

\* **C7 caveat.** Its two silent checks are weaker than they look.
`find /workspace ... 2>/dev/null` and `cd /repo ... 2>/dev/null` print nothing
both when they find nothing *and* when the path does not exist (verified:
`find` on a missing path exits 0, silently). `docker-compose.fa.yml` mounts no
`/workspace` for this service — `fa-entrypoint.sh:160` clones to
`/sessions/<id>`, which is why C0 reported "no shadow". The conclusion holds
via C1–C3 (exactly one authority per session under `/home/fa/.fa/sessions/`),
but **the command should search `/sessions` and `/home/fa` and echo a sentinel
when a path is absent.** Third instance of the same class in this sheet.

**Findings raised, none fixed** (per §0 STOP RULE): **I-36** body-file mode
`0644` vs manifest `0600` · **I-37** tool schemas transmitted twice (+ the
AGENTS.md map at 48.4% of every request) · **I-38 / Q31** quiet-mode stdout
contract · **I-39** `prompt_cache_retention` dropped on Mistral routes.

**Two sheet defects were found and corrected during execution**, both of the
same class — a check that could not fail:

1. **S7.C3 orphan query** was `WHERE run_id=? AND (run_id IS NULL OR run_id="")`,
   a contradiction returning `0` on every database. Proven by seeding a table
   with 3 real orphans and watching it still print `0`. Replaced with an
   unconditional orphan count plus a per-run histogram.
2. **S7.C4** asserted an absence with no liveness witness — a crashed run would
   have printed the passing string. Added positive controls (`db_rows`,
   `llm_call_rows`) so `absent` cannot be confused with `never ran`.

Both were authoring defects in this sheet, not product defects. Recorded here
because the sheet's value depends on its checks being falsifiable, and two of
them were not.

### Negative proof

This sheet is invalid if any row is marked verified from a **local** test
rather than container output, or if body-file contents appear anywhere in the
record.

---

## 4. Rollback

All artifacts live inside the container.

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  rm -rf /home/fa/.fa/sessions/$SID \
         /home/fa/.fa/session-log/s7-run-a \
         /home/fa/.fa/session-log/s7-run-b \
         /home/fa/.fa/session-log/s7-run-c \
         /home/fa/.fa/session-log/s7-run-d \
         /tmp/s7-smoke
'
rm -f /tmp/s7d.out /tmp/s7d.err
```

No host state, no source, no image change.
