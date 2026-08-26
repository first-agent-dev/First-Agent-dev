> **Status:** archived 2026-08-25 — moved per b_full, verification reports exist (S1-S4) / code-proven IMPLEMENTED (S14b)

# PLAN: S4 — Direct-Container Baseline

Plan-ID: `PLAN-cli-trace-S4-direct-container-baseline`

Status: **READY FOR OPERATOR EXECUTION**

Depth: **P1** — evidence-gathering slice on a live deployment. No source edits.

Parent plan:
`worklogs/implementation-plans/cli-trace-substrate-rebaseline-2026-07-25.md` §Step S4

Prior evidence:

- `worklogs/implementation-plans/cli-trace-S2-verification-report.md`
- `worklogs/implementation-plans/cli-trace-substrate-liveness-audit-2026-07-25.md` (S3)

## 0. Scope and execution boundary

### IDEA

Every liveness claim from S1–S3 is **local**. S3 capped all deployment rows at
`PARTIAL / L2 PENDING` on purpose: a green local suite is not proof that the
shipped container writes the trace the operator will debug from. S4 raises the
direct `fa run` path from L2 to L3 for the metadata/count surface, and does it
on a **clean rebuild** that contains the S1–S3 fixes.

### CONCRETE INTENT

Answer, with recorded command output rather than inference:

```text
What image/source revision is actually running?
Does the container create the Candidate A session namespace?
Is session_id separate from run_id at the entrypoint and in the DB?
Does one fa run produce exactly one run directory and one authoritative DB?
Do event counts in session.db agree with the JSONL mirror?
Does FA_DEBUG_LLM_BODIES gate body capture, by count only?
Does the proxy path work with no provider key inside the agent container?
```

### GOALS

- **S4-G1** — record deployment identity (image digest, source revision, mount
  topology, `/workspace/src` shadowing state).
- **S4-G2** — prove the S2 session/run identity split on the live path.
- **S4-G3** — prove authority/mirror agreement by counts, never by content.
- **S4-G4** — prove the debug-body gate in both states, counts only.
- **S4-G5** — prove the egress-proxy boundary holds (no key in agent container).
- **S4-G6** — classify every mismatch before any code change is proposed.

### NON-GOALS

- No edits under `src/`, `tests/`, or `scripts/` during S4.
- No fixes for anything S4 discovers — findings are recorded and assigned.
- No `scripts/fa` wrapper; S4 uses `docker compose exec` directly.
- No printing of `llm_bodies.jsonl` contents, prompts, or key values.
- No workflow/multi-stage runs (that is S8), no subagent paths (S7).
- No image rebuild *during* S4 — the rebuild happens once, as Step S4.0.

### STOP RULE

Stop and report before continuing if:

- the deployed source revision does not contain the S1–S3 fixes;
- a command would print body/prompt/key material;
- the container writes outside the expected session namespace;
- a step's actual output does not match its stated expectation and the
  difference is not explainable from recorded evidence.

## 1. Preconditions

| # | Precondition | How to confirm |
|---|---|---|
| 1 | Gap-closure PR merged to the deployed branch | `git log --oneline -1` on the host repo |
| 2 | Clean rebuild completed | Step S4.0 below |
| 3 | Egress proxy up with real keys | `docker compose ps` shows `fa-egress-proxy` healthy |
| 4 | No provider key inside the agent container | S4.5 verifies this |
| 5 | Operator has a one-turn throwaway task | e.g. "Reply with the single word: pong" |

**Host paths — VERIFIED on fa-HP 2026-07-27:**

```text
compose project : first-agent-dev  (running, 2 services)
COMPOSE         : /srv/first-agent/repo/First-Agent-dev/docker-compose.fa.yml
SERVICE         : first-agent
REPO_DIR        : /srv/first-agent/repo/First-Agent-dev
```

Confirmed via `docker compose ls` and the container's own compose labels
(`com.docker.compose.project.config_files` / `.service`), not assumed.

Set them once per shell. **Every S4 command depends on these being exported —
run this block first, in the same shell, before anything else:**

```bash
export COMPOSE=/srv/first-agent/repo/First-Agent-dev/docker-compose.fa.yml
export SERVICE=first-agent
export REPO_DIR=/srv/first-agent/repo/First-Agent-dev

# Guard: fail loudly instead of letting compose read the wrong path.
# An unset $COMPOSE makes `-f ""` resolve to the CWD and produces the
# confusing error `read /home/fa: is a directory`.
[ -f "$COMPOSE" ] || { echo "COMPOSE not set or missing: '$COMPOSE'"; return 2>/dev/null || exit 1; }
echo "COMPOSE=$COMPOSE"
echo "SERVICE=$SERVICE"
```

Round-trip check — if this prints a version, every later S4 command will work:

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" fa --version
```

**If you open a new terminal, re-run the export block.** Shell variables do not
survive across sessions, and the failure mode is misleading rather than obvious.

## 2. Expected topology (what "correct" looks like)

From `src/fa/session/manager.py:81-82` and the entrypoint, a correct run
produces exactly this shape inside the container:

```text
/sessions/<session-id>/                 <- git clone workspace (entrypoint)
/sessions/.active                       <- pointer to the active workspace
/home/fa/.fa/sessions/<session-id>/manifest.json
/home/fa/.fa/sessions/<session-id>/session.db      <- authority
/home/fa/.fa/session-log/<run-id>/                 <- per-run trace dir
/home/fa/.fa/session-log/<run-id>/events.jsonl     <- best-effort mirror
/home/fa/.fa/session-log/<run-id>/llm_bodies.jsonl <- only when debug enabled
```

**Key invariant under test:** `<session-id>` and `<run-id>` are different
identities. Before S2 they were the same value (V26). If you see the run-id
used as the session directory name, that is a V26 regression — stop.

**State persistence (verified from `docker-compose.fa.yml:85-88`).**
`/home/fa/.fa` is a **host bind mount** of `/srv/first-agent/state`, and
`/sessions` binds `/srv/first-agent/sessions`. Two consequences for S4:

1. Session/run artifacts **survive the rebuild** — pre-existing directories from
   earlier runs are expected and are not a defect. S4.2's pre/post inventory is
   therefore a *diff*, not an absolute-emptiness check.
2. Anything S4 writes lands on the host. The §6 rollback removes exactly the
   three S4 directories and nothing else.

`/home/fa/.fa/models.yaml` is a nested **read-only** mount over that directory —
if a step ever reports it as writable, that is an R2-2 violation; stop.

---

## Step S4.0 — Rebuild and record deployment identity

Traces-to: S4-G1. Depends-on: preconditions 1–3.

```bash
# 0a. Confirm what source the host repo is on BEFORE rebuilding
cd /srv/first-agent/repo/First-Agent-dev
git log --oneline -3
git rev-parse HEAD
git status --short

# 0b. Clean rebuild (use the project's own script)
bash scripts/fa-clean-rebuild.sh 2>&1 | tail -40

# 0c. Record image + container identity
docker compose -f "$COMPOSE" images
docker inspect --format '{{.Image}} {{.Config.Image}}' first-agent
docker image inspect fa-image:latest --format '{{.Id}} {{.Created}}' 2>/dev/null \
  || docker compose -f "$COMPOSE" images --quiet

# 0d. Record the source revision INSIDE the container (this is the one that matters)
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  echo "--- fa version"; fa --version
  echo "--- installed source revision"; python -c "import fa,os;print(os.path.dirname(fa.__file__))"
  echo "--- git rev inside container (if repo mounted)"; git -C /repo rev-parse HEAD 2>/dev/null || echo "no /repo git"
  echo "--- /workspace/src shadowing?"; ls -la /workspace/src 2>/dev/null || echo "no /workspace/src (good)"
  echo "--- PYTHONPATH"; echo "${PYTHONPATH:-<unset>}"
'
```

**Expect:** container `git rev-parse HEAD` equals the merged gap-closure commit.
`/workspace/src` should not exist (its presence means the image source is being
shadowed by a mount, which invalidates every later claim about *which* code ran).

**Exit criteria:** image id/digest, container source revision, and shadowing
state are all recorded.

**Post the full output of 0a and 0d.**

---

## Step S4.1 — Session workspace and identity split

Traces-to: S4-G2. Depends-on: S4.0.

```bash
# 1a. What session workspace exists, and what is active?
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  echo "--- /sessions"; ls -la /sessions
  echo "--- .active"; cat /sessions/.active 2>/dev/null || echo "no .active"
  echo "--- entrypoint status"; cat /workspace/.fa/entrypoint-status.txt 2>/dev/null \
     || cat "$(cat /sessions/.active)/.fa/entrypoint-status.txt" 2>/dev/null \
     || echo "no status file"
'

# 1b. Environment identity as the AGENT PROCESS sees it
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  echo "FA_SESSION_ID=${FA_SESSION_ID:-<unset>}"
  echo "FA_RUN_ID=${FA_RUN_ID:-<unset>}"
  echo "FA_WORKSPACE=${FA_WORKSPACE:-<unset>}"
  echo "FA_AUTO_RUN=${FA_AUTO_RUN:-<unset>}"
  echo "HOME=$HOME"
'
```

**Expect:** `/sessions/<session-id>/.git` exists; `.active` points at it. If
`FA_SESSION_ID` is unset the entrypoint generated one — record the generated
value, that is valid.

**V26 check:** if a directory named after the *run* id appears under
`/sessions/`, stop and report.

**Post output of 1a and 1b.**

---

## Step S4.2 — One real `fa run` (debug OFF)

Traces-to: S4-G2, S4-G3. Depends-on: S4.1.

This is matrix row **A** (`FA_DEBUG_LLM_BODIES=0`, provider success).

```bash
# 2a. Pre-run inventory. /home/fa/.fa is a host bind mount, so PRE-EXISTING
#     entries from earlier runs are normal. What matters is the DIFF in 2c.
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  echo "--- sessions before"; ls -1 /home/fa/.fa/sessions 2>/dev/null || echo none
  echo "--- runs before";     ls -1 /home/fa/.fa/session-log 2>/dev/null || echo none
  echo "--- s4 ids must NOT already exist:"
  for d in /home/fa/.fa/sessions/s4-baseline /home/fa/.fa/session-log/s4-run-a; do
    [ -e "$d" ] && echo "  COLLISION: $d exists — run the section-6 rollback first" || echo "  clear: $d"
  done
'

# 2b. THE RUN — explicit identities, debug disabled, one turn.
docker compose -f "$COMPOSE" exec -T \
  -e FA_DEBUG_LLM_BODIES=0 \
  "$SERVICE" \
  fa run --task "Reply with the single word: pong" \
         --session-id s4-baseline \
         --run-id s4-run-a \
         --role coder \
         --max-turns 1
echo "EXIT_CODE=$?"

# 2c. Post-run inventory
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  echo "--- sessions after"; ls -1 /home/fa/.fa/sessions
  echo "--- runs after";     ls -1 /home/fa/.fa/session-log
  echo "--- session dir";    ls -lh /home/fa/.fa/sessions/s4-baseline
  echo "--- run dir";        ls -lh /home/fa/.fa/session-log/s4-run-a
'
```

**Expect:** exit 0; a session dir named `s4-baseline` containing
`manifest.json` + `session.db`; a run dir named `s4-run-a`; **no**
`llm_bodies.jsonl`.

**Post the run output (stdout+stderr) and 2c.**

---

## Step S4.3 — Authority vs mirror agreement (counts only)

Traces-to: S4-G3. Depends-on: S4.2.

This is the step that converts S3's local `read_all` evidence into deployed
evidence. It answers: does the DB the operator will debug from actually agree
with the mirror?

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  DB=/home/fa/.fa/sessions/s4-baseline/session.db
  RUN=/home/fa/.fa/session-log/s4-run-a

  echo "--- manifest (metadata only)"
  python - <<PY
import json
d=json.load(open("/home/fa/.fa/sessions/s4-baseline/manifest.json"))
for k in ("schema_version","session_id","created_at"):
    print(f"  {k} = {d.get(k)}")
print("  keys =", sorted(d))
PY

  echo "--- authoritative event counts"
  python - <<PY
import sqlite3
c=sqlite3.connect("$DB")
print("  total events      :", c.execute("SELECT COUNT(*) FROM event_log").fetchone()[0])
print("  distinct run_id   :", [r[0] for r in c.execute("SELECT DISTINCT run_id FROM event_log")])
print("  distinct session  :", [r[0] for r in c.execute("SELECT DISTINCT session_id FROM event_log")])
print("  duplicate event_id:", c.execute(
    "SELECT COUNT(*) FROM (SELECT event_id FROM event_log GROUP BY event_id HAVING COUNT(*)>1)").fetchone()[0])
print("  kinds             :")
for k,n in c.execute("SELECT kind,COUNT(*) FROM event_log GROUP BY kind ORDER BY 2 DESC"):
    print(f"    {k:32} {n}")
PY

  echo "--- mirror line count"
  wc -l "$RUN/events.jsonl" 2>/dev/null || echo "  no events.jsonl"

  echo "--- body file must NOT exist"
  ls -lh "$RUN/llm_bodies.jsonl" 2>/dev/null && echo "  UNEXPECTED: body file present with debug off" \
    || echo "  OK: no llm_bodies.jsonl"
'
```

**Expect:**
- `distinct run_id` = `['s4-run-a']` — exactly one.
- `distinct session_id` = `['s4-baseline']`.
- `duplicate event_id` = **0** (this is the live V1 check).
- DB total == mirror `wc -l`, or a recorded explanation if not.
- No body file.

**This is a real V1 probe on the deployed path.** S3 proved V1 is latent
locally; if `duplicate event_id` > 0 here, it is live and S5 priority changes.

**Post the whole block output.**

---

## Step S4.4 — Debug-body gate ON (counts only)

Traces-to: S4-G4. Depends-on: S4.3. Matrix row **B**.

```bash
docker compose -f "$COMPOSE" exec -T \
  -e FA_DEBUG_LLM_BODIES=1 \
  "$SERVICE" \
  fa run --task "Reply with the single word: pong" \
         --session-id s4-baseline \
         --run-id s4-run-b \
         --role coder \
         --max-turns 1
echo "EXIT_CODE=$?"

docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  RUN=/home/fa/.fa/session-log/s4-run-b
  echo "--- run dir"; ls -lh "$RUN"
  echo "--- body file line count (COUNT ONLY — never cat this file)"
  wc -l "$RUN/llm_bodies.jsonl" 2>/dev/null || echo "  MISSING: expected with debug on"
  echo "--- body file size"; du -h "$RUN/llm_bodies.jsonl" 2>/dev/null
  echo "--- second run must NOT pollute the first"
  ls -1 /home/fa/.fa/session-log
  echo "--- both runs share ONE session db"
  python - <<PY
import sqlite3
c=sqlite3.connect("/home/fa/.fa/sessions/s4-baseline/session.db")
print("  runs in db:", [r[0] for r in c.execute("SELECT DISTINCT run_id FROM event_log")])
print("  per-run counts:")
for r,n in c.execute("SELECT run_id,COUNT(*) FROM event_log GROUP BY run_id"):
    print(f"    {r:16} {n}")
print("  duplicate event_id across both runs:", c.execute(
    "SELECT COUNT(*) FROM (SELECT event_id FROM event_log GROUP BY event_id HAVING COUNT(*)>1)").fetchone()[0])
PY
'
```

**Expect:** `llm_bodies.jsonl` exists for run B only; both runs appear in the
**same** `session.db` under distinct `run_id`s (this is the P33 multi-run
contract); duplicate event_id still 0.

**Critical:** never `cat`/`head` the body file. Counts and sizes only.

**Post the output.**

---

## Step S4.5 — Proxy boundary and secret isolation

Traces-to: S4-G5. Depends-on: S4.2.

```bash
# 5a. Agent container must hold NO provider key
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  echo "--- key-shaped env vars in agent container (expect NONE with values)"
  env | grep -iE "api_key|token|secret|anthropic|openai|mistral" \
      | sed -E "s/=.{4,}/=<redacted-nonempty>/" || echo "  none found (good)"
  echo "--- proxy routing address"
  echo "FA_EGRESS_PROXY_URL=${FA_EGRESS_PROXY_URL:-<unset>}"
  echo "--- secrets file readable from agent? (expect NO)"
  cat /run/secrets/fa.env >/dev/null 2>&1 && echo "  UNEXPECTED: agent can read fa.env" || echo "  OK: not readable"
'

# 5b. Routing self-check (does not call providers)
docker compose -f "$COMPOSE" exec -T "$SERVICE" fa selfcheck; echo "EXIT=$?"

# 5c. Minimal liveness probe (~10 tokens) — proves the proxy path end to end
docker compose -f "$COMPOSE" exec -T "$SERVICE" fa probe --role coder; echo "EXIT=$?"
```

**Expect:** no key values in the agent env; `fa selfcheck: OK`; `fa probe`
succeeds through the proxy.

**Post the output** (the redaction `sed` keeps values out of the transcript —
if you see an actual key value, stop and tell me before pasting).

---

## Step S4.6 — Deterministic non-LLM control

Traces-to: S4-G1, S4-G3. Depends-on: S4.2. This is parent path **P19**.

Runs the loop with no provider involved, isolating harness behaviour from
provider behaviour.

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  cd "$(cat /sessions/.active)"
  fa inner-loop-smoke --input README.md --output /tmp/s4-smoke.txt 2>&1 | tail -20
  echo "EXIT=$?"
  echo "--- smoke artifacts"; ls -lh /tmp/s4-smoke.txt
  echo "--- did smoke dirty the session workspace?"; git status --short | head
'
```

**Expect:** exit 0; **clean `git status`**. S3-F9 predicts this root emits no
console events on a stop path — note whatever it prints, that is data for Q12.

**Post the output.**

---

## Step S4.7 — Post-run hygiene and classification

Traces-to: S4-G6. Depends-on: S4.2–S4.6.

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  echo "--- session workspace clean?"; cd "$(cat /sessions/.active)" && git status --short | head -20
  echo "--- state tree inventory"; find /home/fa/.fa -maxdepth 3 -type d | sort
  echo "--- anything written outside the expected namespace?"
  find /home/fa/.fa -maxdepth 2 -newer /home/fa/.fa/sessions -type f 2>/dev/null | head -20
'
# Host-side: container health after the runs
docker compose -f "$COMPOSE" ps
docker compose -f "$COMPOSE" logs --tail=40 "$SERVICE"
```

**Post the output.**

---

## 3. Evidence template

For each step, record:

```text
STEP:      S4.x
COMMAND:   <exact command run>
EXIT:      <code>
EXPECTED:  <from this plan>
ACTUAL:    <verbatim output, body files never printed>
VERDICT:   MATCH | MISMATCH | BLOCKED
IF MISMATCH: classify only — do not fix.
```

## 4. Definition of Done

- [ ] S4.0 deployment identity recorded (image + in-container source revision).
- [ ] S4.1 session workspace and identity split recorded; no V26 regression.
- [ ] S4.2 one-turn run completes; session/run dirs match §2 topology.
- [ ] S4.3 authority counts recorded; `duplicate event_id` value recorded.
- [ ] S4.4 debug gate proven in both states, counts only.
- [ ] S4.5 no provider key in agent container; proxy path works.
- [ ] S4.6 deterministic root runs clean.
- [ ] S4.7 no writes outside the expected namespace.
- [ ] Every mismatch classified with an owner slice; **zero fixes applied**.

### Negative proof

S4 is invalid if any row is marked verified from a *local* test rather than
container output, or if a body file's contents appear anywhere in the record.

## 5. What S4 unblocks

S5 formally `Depends-on: S2, S3, S4`. S4.3's duplicate-event-id count is the
single most decision-relevant number: S3 proved V1 latent locally, and S4
determines whether it is latent or live in production — which sets whether V1
stays rank 1 in the S5 register.

## 6. Rollback

S4 writes only session/run artifacts inside the container. To reset:

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  rm -rf /home/fa/.fa/sessions/s4-baseline /home/fa/.fa/session-log/s4-run-a /home/fa/.fa/session-log/s4-run-b
'
```

No host state, no source, no image change.
