# S13 live-execution sheet — multi-provider conformance confirmation

*Style: S11-controlled-deployment sheet. Copy-paste into a terminal on the deployed box
(`fa@fa-HP`, the `first-agent` container). Every step writes evidence to `$EVID` and has an
`**Expect:**`. No source edits during execution.*

> **Purpose.** Confirm the S13 closed-core payoff on the real box:
> (1) the tool-name dot→underscore fix (no more `fs.checkpoint` 400),
> (2) the prompt-cache `supports_prompt_cache` fix (no more NVIDIA 400 on `prompt_cache_key`),
> (3) the I-50/I-52 composition fixes (workflow completes past stage 2),
> (4) sampling now OMITS temperature/top_p by default (thinking-first),
> (5) live cache-hit ≥ 74% (R1 gate).

---

## 0. Preconditions and environment

```bash
# Deployed box. Run INSIDE the agent container (or via compose exec).
# If the sheet is for the container, prefix every `fa ...` with:
#   docker compose -f /srv/first-agent/repo/First-Agent-dev/docker-compose.fa.yml exec -T first-agent
# (adjust the compose path to the operator's layout — S11 used this exact path).

# Evidence dir (one per run — do NOT reuse across runs).
export EVID=/tmp/s13-evidence-$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$EVID"
echo "EVIDENCE DIR: $EVID"
```

**Expect:** the dir is created and the path printed. Keep it for the bundle step (§S13.10).

**Instrument checks (S13-session rule — verify before trusting any measurement):**

```bash
uv run python -c "import fa; print(fa.__file__)"   # MUST be <repo>/src/fa/__init__.py
uv run which pytest                                 # MUST resolve inside .venv/
fa --version | tee "$EVID/00-version.txt"
```

**Expect:** `import fa` resolves to the repo `src/fa/__init__.py`; `pytest` resolves inside
`.venv/`; `fa --version` prints a version. If these drift, the deployed image is not the slice
under test — STOP.

---

## 1. Run-id namespace this sheet uses

| run-id | Step | Purpose |
|---|---|---|
| `s13-probe` | S13.1 | `fa probe --all-roles` — real provider path |
| `s13-conf-<provider>-<ts>` | S13.2 | `fa conformance --provider <name>` (run-id minted by the runner) |
| `s13-run-a` | S13.3 | `fa run` coder, minimal task, bodies OFF |
| `s13-run-bodies` | S13.3b | `fa run` coder with `FA_DEBUG_LLM_BODIES=1` — sampling-omission on the wire |
| `s13-wf-a` | S13.4 | `fa workflow planner,coder,eval` — the closed-core payoff |
| `s13-wf-b` | S13.5 | `fa workflow planner,coder,eval` again — cache-hit evidence |
| — | S13.6 | cache-hit ratio read from session.db |
| — | S13.7 | same-family eval adversarial stance (K9) |
| — | S13.7b | `fa routing-check` — config deploy gate (S10c.1) |
| — | S13.7c | `fa stats --run-id <s13-wf-b>` — per-run usage/tokens |
| — | S13.7d | `fa selfcheck --role coder` — proxy seam, no provider call |
| `s13-run-shape` | S13.9b | provoke `request_shape` error — I-51 error surfacing |
| `s13-conf-resume` | S13.9c | induce 429 mid-matrix, re-run — K8 resume |

> The live conformance runner mints its own `conf-<provider>-<epoch>` run-id; the operator does
> not need to. The `s13-*` ids here are for the other commands.

---

## Step S13.1 — `fa probe` — real provider path, per role

```bash
fa probe --all-roles --timeout 60 2>&1 | tee "$EVID/01-probe.txt"
echo "PROBE_EXIT=${PIPESTATUS[0]}" | tee -a "$EVID/01-probe.txt"
```

**Expect:** exit 0 and an `OK` line per configured role (`planner`, `coder`, `eval`). This is the
first real provider call. If any role is missing or a role 400s, STOP — a role cannot even probe.

> Paste-safe: `fa probe` prints role/model/family and `OK`/error — no keys, no bodies.

---

## Step S13.2 — `fa conformance --provider <name>` — the live matrix

This is the direct confirmation that the **tool-name 400** and the **prompt-cache 400** are gone.
Run for NVIDIA first (the observed breakage), then for any other configured provider.

```bash
# NVIDIA (the originally-broken provider)
fa conformance --provider nvidia_build --config ~/.fa/models.yaml 2>&1 \
  | tee "$EVID/02-conformance-nvidia.txt"
echo "CONF_NVIDIA_EXIT=${PIPESTATUS[0]}" | tee -a "$EVID/02-conformance-nvidia.txt"

# Repeat for any other provider the operator configured (e.g. mistral):
# fa conformance --provider mistral --config ~/.fa/models.yaml 2>&1 | tee "$EVID/02-conformance-mistral.txt"
```

**Expect (the fix payoff):**
- NO `request_shape_error: ... invalid name "fs.checkpoint"` (the old 400).
- NO `Unsupported parameter(s)` prompt-cache 400.
- Each CONF-1..7 row prints `OK` or a recorded `FAIL` **with a diagnosable reason**
  (`request_shape:`, `chain_exhausted:`, or a raw provider body) — NOT an opaque `FAIL`.
- If a row still FAILs, capture the exact reason verbatim; it is the next finding, not a shrug.

> The prior failing all-7 `chain_exhausted` was the `fs.` tool-name 400. If all 7 now pass or fail
> for a *different*, identifiable reason, that is the confirmation this step exists for.

**If it 429s (free tier):** the runner resumes on re-invocation with the same run-id; prior rows are
preserved. Re-run the same command — it should print `resumed prior run`.

---

## Step S13.3 — `fa run` — minimal task through coder on the real path

```bash
fa run --task "Reply with the single word: pong" \
       --run-id s13-run-a --role coder --max-turns 1 \
       --output-mode console 2>&1 | tee "$EVID/03-run-a.txt"
echo "RUN_A_EXIT=${PIPESTATUS[0]}" | tee -a "$EVID/03-run-a.txt"
```

**Expect:** exit 0; the model replies `pong`; the `session_summary` line or final text is present.
No `fs.*` invalid-name 400, no `prompt_cache_key` 400. This confirms a *single* coder turn on the
deployed path.

> Check the wire body for sampling omission (only if `fa run` captured a body; the default does not
> print one). The offline CONF-7/CONF-8 already assert temperature/top_p are omitted; here we only
> need the call to succeed.

---

## Step S13.3b — Sampling omission on the wire (thinking-first, bodies ON)

**Why this exists.** S13's core sampling change is that FA **omits `temperature`/`top_p` by default**
(thinking-first) so reasoning models don't reject or ignore them. This is the single most important
S13 claim that is only *offline*-tested (CONF-7/CONF-8). This step captures the actual request body on
the box and asserts neither key is present — the thinking-first default, live.

```bash
# Run a minimal coder task with body capture ON. Writes llm_bodies.jsonl under the run dir.
FA_DEBUG_LLM_BODIES=1 fa run --task "Reply with the single word: pong" \
   --run-id s13-run-bodies --role coder --max-turns 1 \
   --output-mode console 2>&1 | tee "$EVID/03b-run-bodies.txt"
echo "RUN_BODIES_EXIT=${PIPESTATUS[0]}" | tee -a "$EVID/03b-run-bodies.txt"

BODY_DIR="$HOME/.fa/session-log/s13-run-bodies"
test -f "$BODY_DIR/llm_bodies.jsonl" && echo "llm_bodies.jsonl present" \
  || { echo "MISSING llm_bodies.jsonl — FA_DEBUG_LLM_BODIES not honored?"; }

# Assert no temperature/top_p in any captured request body. Paste-safe: prints keys only.
python3 - "$BODY_DIR/llm_bodies.jsonl" <<'PY' | tee "$EVID/03b-sampling-omitted.txt"
import json, sys
path = sys.argv[1]
bodies = []
with open(path) as f:
    for line in f:
        row = json.loads(line)
        if "request_body" in row:
            bodies.append(row["request_body"])
if not bodies:
    print("no_request_bodies=0"); raise SystemExit(1)
# Expect: thinking-first default => temperature/top_p absent on every request.
bad = [b for b in bodies if "temperature" in b or "top_p" in b]
print(f"request_bodies={len(bodies)}")
print(f"bodies_with_temperature_or_top_p={len(bad)}")
print(f"GATE_sampling_omitted={'PASS' if not bad else 'FAIL'}")
for i, b in enumerate(bodies):
    print(f"body[{i}] keys={sorted(b.keys())}")
PY
```

**Expect:** `GATE_sampling_omitted=PASS` — zero request bodies carry `temperature`/`top_p`. If it
prints `FAIL`, the thinking-first default is not on the deployed path (or a role has an explicit
`sampling:` block); STOP and report, do not continue.

> Paste-safe: prints body key names and a PASS/FAIL line — never key values or prose. The
> `llm_bodies.jsonl` file is NOT bundled in §S13.10 (raw prose), only its derived key-count.

---

## Step S13.4 — `fa workflow planner,coder,eval` — the closed-core payoff

This is the **S13 DoD's live gate**: does the workflow complete past stage 2 (the I-50/I-52 fixes)?

```bash
# NOTE: workflow takes the task POSITIONALLY (roles then task). --task is ambiguous
# (conflicts with --task-planner/--task-coder/--task-eval) and fails at argparse.
fa workflow planner,coder,eval \
   "Write a one-line docstring for a function named add(a, b)." \
   --run-id s13-wf-a --workspace /tmp/s13-wf-a 2>&1 | tee "$EVID/04-workflow-a.txt"
echo "WF_A_EXIT=${PIPESTATUS[0]}" | tee -a "$EVID/04-workflow-a.txt"
```

**Expect:**
- `fa workflow: planner` completes → `coder` completes → `eval` runs.
- The workflow **completes past stage 2** (planner done, coder done, eval yields a verdict), OR the
  first *fail-fast* stage prints a clear reason. The S13 DoD is "completes past stage 2" — a
  clean `planner → coder → eval` with an `eval verdict=` line is the positive result.
- `eval_report.json` exists under the run dir and, if same-family, records the adversarial stance
  (`eval_independence`) — S13.4c.

> The `--workspace` should be a clean scratch dir under `/tmp` (the workflow mutates it). Do not
> point it at the repo.

---

## Step S13.5 — Repeat workflow — cache-hit evidence

A second workflow run reuses the same cacheable prefix, so it is the one that demonstrates cache
hits. Run the same task again:

```bash
fa workflow planner,coder,eval \
   "Write a one-line docstring for a function named add(a, b)." \
   --run-id s13-wf-b --workspace /tmp/s13-wf-a 2>&1 | tee "$EVID/05-workflow-b.txt"
echo "WF_B_EXIT=${PIPESTATUS[0]}" | tee -a "$EVID/05-workflow-b.txt"
```

**Expect:** exit 0; completes past stage 2. This run feeds the cache-hit calculation in S13.6.

---

## Step S13.6 — Live cache-hit ratio (R1 gate, ≥ 74%)

The runner persists per-turn `usage` events and a `session_summary` in each run's `session.db`.
The ratio is `cache_read / (cache_read + cache_creation + uncached_input)` per turn.

```bash
# Locate the run's session.db. Default layout: ~/.fa/session-log/<run_id>/session.db
# (workflow artifacts also live there). If FA_STATE_ROOT differs, adjust the path.
RUN_DIR="$HOME/.fa/session-log/s13-wf-b"
ls -la "$RUN_DIR" | tee "$EVID/06-run-dir.txt"
test -f "$RUN_DIR/session.db" && echo "session.db present" || echo "session.db MISSING — locate it"

# If the default path is wrong, find it (counts only, safe):
# find "$HOME/.fa" -name session.db -path "*s13-wf-b*" 2>/dev/null

python3 - "$RUN_DIR" <<'PY' | tee "$EVID/06-cache-hit.txt"
import json, sqlite3, sys, pathlib
db = pathlib.Path(sys.argv[1]) / "session.db"
con = sqlite3.connect(db)
rows = con.execute(
    "SELECT content FROM event_log WHERE kind='usage' ORDER BY id"
).fetchall()
tot = {"cache_read_input_tokens":0,"cache_creation_input_tokens":0,"input_tokens":0}
n=0
for (content,) in rows:
    d=json.loads(content); n+=1
    for k in tot: tot[k]+=d.get(k,0)
uncached = max(tot["input_tokens"]-tot["cache_read_input_tokens"]-tot["cache_creation_input_tokens"],0)
den = tot["cache_read_input_tokens"]+tot["cache_creation_input_tokens"]+uncached
ratio = (tot["cache_read_input_tokens"]/den) if den else 0.0
print(f"usage_events={n}")
print(f"input_tokens={tot['input_tokens']} cache_read={tot['cache_read_input_tokens']} cache_creation={tot['cache_creation_input_tokens']} uncached={uncached}")
print(f"cache_hit_ratio={ratio:.3f}")
print(f"GATE_>=0.74={'PASS' if ratio>=0.74 else 'FAIL'}")
PY
```

**Expect:** `GATE_>=0.74=PASS`. If it prints `FAIL`, that is the R1 stop condition from the S13
plan (CT4 offline is green; the live confirmation is the second half). Record the numbers verbatim.

> Paste-safe: prints token counts and a PASS/FAIL line only — no prose, no keys, no bodies.

---

## Step S13.7 — Optional: same-family eval adversarial stance (K9)

Only if the operator's `models.yaml` declares `eval` from the same family as planner/coder:

```bash
grep -A6 '^eval:' ~/.fa/models.yaml | tee "$EVID/07-eval-config.txt"
```

**Expect:** either (a) the eval family differs from planner/coder → nothing to do here (K10, neutral),
or (b) same-family → the S13.4c `eval_independence` field is present in `eval_report.json` from
S13.4 with stance `adversarial`, and the loader emitted exactly one warning. Both are covered by the
offline K9/K10 tests; this is the live confirmation.

---

## Step S13.7b — `fa routing-check` — the config deploy gate (S10c.1)

**Why this exists.** `routing-check` is the S10c.1 deploy gate that validates `models.yaml` and aborts
on a bad config. S13 touches `providers/config.py` (eval-independence), so this confirms the deployed
config actually loads under the S13 rules. It is the config-load surface S13 modified.

```bash
fa routing-check --config ~/.fa/models.yaml 2>&1 | tee "$EVID/07b-routing-check.txt"
echo "ROUTING_EXIT=${PIPESTATUS[0]}" | tee -a "$EVID/07b-routing-check.txt"
```

**Expect:** exit **0** (clean config) with `fa routing-check: OK (N role(s) checked, no issues found)`.
If it exits 1 (ISSUES FOUND) or 2 (config error), the S13 config changes or the eval-independence
warnings are mis-loading on the box — report the exact findings.

> Negative control (optional): `fa routing-check --config /nonexistent.yaml` → exit 2 with
> `ERROR: config not found`. Proves the gate is live, not a silent pass (R23/S11 lesson).

---

## Step S13.7c — `fa stats --run-id <s13-wf-b>` — per-run usage/tokens

**Why this exists.** S13 touched `stats.py` (via the sampling/usage surface). This reads the global
history for the workflow run and reports per-role tokens/turns/cache — a *different* view than the raw
SQL in S13.6, and it exercises the `stats` command's run-id path on the box.

```bash
fa stats --run-id s13-wf-b --output json 2>&1 | tee "$EVID/07c-stats.txt"
echo "STATS_EXIT=${PIPESTATUS[0]}" | tee -a "$EVID/07c-stats.txt"
```

**Expect:** exit 0 and a JSON (or console) block for `s13-wf-b` with per-role rows:
`run_id`, `role`, `model`, `stop_reason`, `turns`, `input_tokens`, `output_tokens`. The `input_tokens`
should be consistent with the cache-hit numbers in S13.6 (same run). If exit 1
(`run 's13-wf-b' not found`), the run wasn't recorded as global history on the box — note it.

> Paste-safe: `fa stats` prints counts/tokens only, no bodies, no keys.

---

## Step S13.7d — `fa selfcheck --role coder` — the proxy seam

**Why this exists.** Confirms the box's egress-proxy wiring is intact before we trust any provider
result. It does **not** make a provider call (it's the seam check), so it isolates "proxy broken" from
"provider rejects shape" if later steps fail.

```bash
fa selfcheck --role coder --config ~/.fa/models.yaml 2>&1 | tee "$EVID/07d-selfcheck.txt"
echo "SELFCHECK_EXIT=${PIPESTATUS[0]}" | tee -a "$EVID/07d-selfcheck.txt"
```

**Expect:** exit 0 and `fa selfcheck: OK` with `/healthz reachable` (or equivalent) for the proxy,
and the config resolves. If the proxy is unreachable, STOP — later provider results would be
unattributable to S13.

---

## Step S13.9b — Request-shape error surfacing (I-51 / S13.4a), live

**Why this exists.** S13.4a made the provider's real error surface on a `request_shape` failure
(provider/status/reason, not `unknown/0`). This is only offline-tested (K5). Live, we provoke a
`request_shape` failure and confirm the rendered line shows the real provider + message.

**How to provoke one safely.** A `request_shape` error is raised locally by the conformance pass when
the composed messages violate a provider's `MessageRules` (e.g. a dangling tool / assistant-final that
a strict provider rejects). The simplest *live-safe* trigger that does not require crafting a bad
prompt: run a **single-turn coder** through a provider whose strict rules reject the shape. Since FA
now emits valid shapes by default, this may not fire on the happy path — so treat this step as
**conditional**: if `fa run` (S13.3) already exercised a request-shape failure, use that evidence.

```bash
# Attempt a minimal turn that would surface any request_shape failure (idempotent; may exit 0).
fa run --task "Reply with the single word: pong" \
   --run-id s13-run-shape --role coder --max-turns 1 \
   --output-mode console 2>&1 | tee "$EVID/09b-shape.txt"
echo "SHAPE_EXIT=${PIPESTATUS[0]}" | tee -a "$EVID/09b-shape.txt"
```

**Expect one of:**
- **exit 0** with `pong` → no request-shape error on the happy path (the normal S13 state; S13.4a is
  exercised only when a shape is invalid). Record "no request-shape failure on happy path".
- **exit 2** with `stop_reason=request_shape` → **confirm the rendered line carries the provider name
  and the real message** (S13.4a), NOT `provider=unknown status=0`. This is the K5 live proof.

> If exit 2 fires, the I-51 fix (provider/status/reason surfacing) is what we're validating. Capture
> the exact rendered line verbatim.

---

## Step S13.9c — Induced 429 + resume (K8), live

**Why this exists.** K8 (the runner resumes without losing prior rows) is offline-tested but the live
run-id minting + `resumed prior run` path is not. This induces a 429 (if the provider rate-limits) and
re-runs the same matrix to confirm resume.

```bash
# Run the matrix once (may 429 on free tier). Capture the run-id from output.
fa conformance --provider nvidia_build --config ~/.fa/models.yaml 2>&1 \
  | tee "$EVID/09c-conf-first.txt"
echo "CONF_FIRST_EXIT=${PIPESTATUS[0]}" | tee -a "$EVID/09c-conf-first.txt"

# Re-run the SAME command immediately. If the first run 429'd, this should print "resumed prior run".
fa conformance --provider nvidia_build --config ~/.fa/models.yaml 2>&1 \
  | tee "$EVID/09c-conf-resume.txt"
echo "CONF_RESUME_EXIT=${PIPESTATUS[0]}" | tee -a "$EVID/09c-conf-resume.txt"
```

**Expect:** if the first run hit a 429, the second prints `resumed prior run conf-...` and does NOT
re-print the already-completed rows as fresh (it continues from the durable `results.jsonl`). If no
429 occurred (free tier is fast enough at ~20 RPM), the second run is a fresh matrix with a **new**
run-id (no collision with the first). Either is the K8 contract; record which happened.

> Paste-safe: prints run-id, per-CONF OK/FAIL-with-reason, and the resume line — no bodies, no keys.

---

## Step S13.10 — Bundle and close

```bash
# Bundle the evidence dir (counts + outputs only). Do NOT include raw llm_bodies.jsonl or keys.
tar -czf /tmp/s13-evidence-$(date -u +%Y%m%dT%H%M%SZ).tgz -C /tmp s13-evidence-*
echo "BUNDLE: $(ls -t /tmp/s13-evidence-*.tgz | head -1)"
```

**Expect:** a single `.tgz` produced. Share the console outputs from each step + this bundle with
the operator for evaluation.

---

## Stop rules

1. **No source edits during execution.** If a command surfaces a defect, record it (step, command,
   output, `**Expect**` vs actual) and stop — do not patch the box mid-sheet.
2. **Instrument drift** (`import fa` not resolving to repo, `pytest` not in `.venv`) → STOP.
3. **`fa probe` 400s on any role** → STOP (nothing downstream can succeed).
4. **Cache-hit < 74%** (S13.6) → this is the R1 stop condition; report, do not continue to claim
   S13 done.
5. **Sampling not omitted** (S13.3b `GATE_sampling_omitted=FAIL`) → STOP: the thinking-first default
   is not on the deployed path.
6. **`routing-check` exits ≠ 0** (S13.7b) → the S13 config changes are mis-loading; STOP.
7. **`selfcheck` fails** (S13.7d) → proxy broken; later provider results would be unattributable; STOP.

## Run book (fill as you go)

| Step | run-id | exit | PASS/FAIL | evidence file | note |
|---|---|---|---|---|---|
| S13.1 | s13-probe |  |  | 01-probe.txt | |
| S13.2 | conf-* |  |  | 02-conformance-*.txt | |
| S13.3 | s13-run-a |  |  | 03-run-a.txt | |
| S13.3b | s13-run-bodies |  |  | 03b-sampling-omitted.txt | gate: no temp/top_p |
| S13.4 | s13-wf-a |  |  | 04-workflow-a.txt | |
| S13.5 | s13-wf-b |  |  | 05-workflow-b.txt | |
| S13.6 | (db read) |  |  | 06-cache-hit.txt | gate ≥0.74 |
| S13.7 | (config) |  |  | 07-eval-config.txt | only if same-family |
| S13.7b | — |  |  | 07b-routing-check.txt | gate: exit 0 |
| S13.7c | s13-wf-b |  |  | 07c-stats.txt | per-run usage |
| S13.7d | — |  |  | 07d-selfcheck.txt | gate: exit 0 |
| S13.9b | s13-run-shape |  |  | 09b-shape.txt | exit 0 or 2 w/ provider msg |
| S13.9c | conf-* |  |  | 09c-conf-first/resume.txt | K8 resume |
| S13.10 | bundle |  |  | .tgz | |
