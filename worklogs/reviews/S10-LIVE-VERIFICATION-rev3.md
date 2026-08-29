# Complexity-Aware Execution — live verification rev3 (slices S1–S10.9)

**Feature:** chat role + deterministic scope estimation + evidence-driven workflow
escalation + E3 cost/calibration + S10.9 hardening.
**Plan:** `worklogs/implementation-plans/PLAN-complexity-aware-execution-chat-role.md`
(parent S1–S11), `PLAN-scope-control-S10-final.md` (S10 detail, operator workspace),
`PLAN-scope-control-S10.9-hardening.md` (S10.9).
**Date:** 2026-08-29 · **Base:** branch with S10.9 applied (`fa` 0.1.0).

Two parts:

1. **Offline verification — run a script.** The deterministic, no-provider engine checks
   ship as a runnable, gated harness (`scripts/verify_complexity_aware_execution.py`,
   151 assertions) plus a real-CLI calibration smoke. No LLM, no token spend.
2. **Live verification — run the real agent.** A shell driver
   (`scripts/run_live_expansion_trial.sh`) and copy/paste rows below run a provider-backed
   chat session and surface the engine's durable footprint.

| Property | How it is enforced |
|---|---|
| No LLM cost for offline checks | the harness calls the shipped engine directly; no provider, no mocks |
| Offline checks never write your real `~/.fa` | every seeded-DB check uses a throwaway `FA_STATE_ROOT` |
| Offline checks never edit your config | toggle checks parse temp text through the real loader |
| Idempotent / repeatable | each block makes its own temp root; the harness has no side effects |
| Cannot silently "pass" | every offline check ends with an explicit pass/fail count and non-zero exit on failure |
| **Driver (2.1) is isolated** | throwaway `git worktree` workspace + unique `--run-id` + temp `FA_STATE_ROOT` — your checkout and history are untouched (enforced by the script, with a loud confirm-before-in-repo fallback) |
| **Rows L1–L4 write your REAL `~/.fa` — intentionally** | L4's target IS the durable history; trial runs therefore appear in `fa stats --calibration` (record the `cae-*` run-ids below so S11 can exclude trials when fitting constants) |
| **Rows L2/L3 run a live agent with write tools** | L2 runs in a throwaway worktree; L3 edits the real repo **by design** (the staged defect) — both carry mandatory pre/post procedures below |

> **Part 2 requires bash** (the rows use `PIPESTATUS`, a bash array — in zsh it expands
> to empty and the EXIT check silently lies). Paste each row as a unit into bash, or run
> `bash` first. **Prerequisite for live rows:** `~/.fa/models.yaml` needs a top-level
> `chat:` key (the driver preflights this; the manual rows assume it).

> **Where the signals live (rev3 oracle fix).** `scope_expansion` /
> `expansion_observed` / `expansion_exhausted` are durable **event-log** rows:
> `~/.fa/session-log/<run-id>/events.jsonl` (or `$FA_STATE_ROOT/session-log/...` under
> the driver). The console shows one-line mirrors for `scope_expansion` /
> `expansion_exhausted` only. **Grep the JSONL** — console greps for these signals are
> not oracles and were the rev2 defect.

---

# PART 1 — offline deterministic verification (no provider)

## 1.1 Run the engine harness (one command)

```bash
cd "$(git rev-parse --show-toplevel)"
uv run python scripts/verify_complexity_aware_execution.py   # full S1–S10.9
echo "EXIT=$?"
```

Expected tail:

```
================================================================
  151/151 checks passed  — ALL GREEN
================================================================
```

`EXIT=0` means every assertion passed. Single slice: `--only <substring>`, e.g.
`--only check_s10_calibration` or `--only check_s8_cost_model`.

What it asserts, by slice (S10.9 additions marked ✦):

| Slice | Checks |
|---|---|
| **S1** estimator | L1/L2/L3 cue mapping, confidence in (0,1], cue-free heavy wording under-scopes, RU classifies, blank task raises |
| **S2** chat registry | chat exposes the generalist set via the real `specs()` API (✦ dead `all_specs` branch removed) |
| **S3** seed mapping | `difficulty_to_level` total + unknown raises |
| **S4** tool + K | K=2 → ok/ok/denied; ✦ **K=0 → first call denied as disabled-by-config, runner untouched**; K read from context; no-context → `workflow_unavailable`; child run id rules |
| **S5** ACRR + history | ACRR formula, read amplification, history round-trip |
| **S7** routing gate | gate **off** ⇒ never withhold; on + confident workflow_linear ⇒ withhold; chat-only; None fails open |
| **S8** cost model | fitted weights, C arithmetic, self-referential floor |
| **S10 CT1** expansion | clean/bulk-silent/read-arm→L2/write→L3/verify-failed→L3/medium-silent/workflow_linear-silent; ceiling-3; verify_failed dominates; skill select; ✦ **near-miss truth table** (bulk reads / medium write / high-read-while-armed) |
| **S10 CT3** path tiers | tier anchors; unknown→medium; boundary; MAX combine; config additivity + warning; ✦ **segment-anchored globs** (`gen/*` ≠ deep match) and **dot-directory survival** (`.ci` ≠ `ci`) |
| **S10 CT4** observations | rebuild-not-append; L3 replaces L2; body never in text; posture lines; exhausted terminal; 1800-char cap |
| **S10 CT6** handoff | sections + caps; ✦ **Modified ≤ 15 with `(+N more)` marker, ≤30 entries under 40 writes**; ✦ **malformed risk_config degrades to goal-only** |
| **S10 CT8** calibration | reliability counts ALL runs; ACRR successes-only; n<10 never flagged; rate exactly 1−ε not flagged; gate surfaces **off** |
| **S10 F4** log kinds | `scope_expansion`/`expansion_exhausted` registered **and console-mirrored** ✦; `expansion_observed` registered, **not** mirrored ✦; `scope_tripwire` dormant, no producer |
| **S10 G10** two-layer | 8 cue-free tasks (EN + terse RU) under-scope yet evidence escalates |

## 1.2 Real-CLI calibration smoke (no provider)

```bash
cat > /tmp/cae_cal.sh <<'SHEOF'
#!/usr/bin/env bash
set -uo pipefail
export FA_STATE_ROOT="$(mktemp -d)"; trap 'rm -rf "$FA_STATE_ROOT"' EXIT
# Repo venv CLI ONLY. On operator hosts, `fa` on PATH is scripts/fa — a
# docker-compose wrapper that executes inside the agent container and would
# read the CONTAINER's history, not the FA_STATE_ROOT seeded below. Same
# precedence as run_live_expansion_trial.sh; no silent fallback.
FA="${FA:-./.venv/bin/fa}"
[ -x "$FA" ] || { echo "ERROR: .venv/bin/fa missing — run 'uv sync' in the repo root first" >&2; exit 1; }
uv run python - <<'PY'
import json
from fa.inner_loop.global_history import GlobalHistoryStore, default_global_history_path
s = GlobalHistoryStore(db_path=default_global_history_path())
def row(rid, ec, acrr=None):
    s.export_run({"run_id":rid,"role":"chat","exit_code":ec,"stop_reason":"done" if ec==0 else "failed",
                  "turns":1,"scope_estimate_json":json.dumps({"recommended_mode":"chat_direct"}),
                  "read_amplification":None,"acrr":acrr})
for i in range(8): row(f"ok{i}",0,2.0)
for i in range(4): row(f"bad{i}",1)
PY
"$FA" stats --calibration --output json 2>/dev/null | tee "$FA_STATE_ROOT/cal.json"
uv run python - "$FA_STATE_ROOT/cal.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1])); cd={b["recommended_mode"]:b for b in d["calibration"]}["chat_direct"]
ok = (d["chat_escalation_gate"] is False and cd["runs_total"]==12 and cd["runs_succeeded"]==8
      and cd["success_rate"]==round(8/12,4) and cd["acrr_mean"]==2.0 and cd["below_reliability_target"] is True)
print("  [PASS] real-CLI calibration (gate off, reliability counts all runs)" if ok else "  [FAIL] calibration smoke")
sys.exit(0 if ok else 1)
PY
SHEOF
bash /tmp/cae_cal.sh; echo "EXIT=$?"
```

## 1.3 Repository gates (full suite)

```bash
just check                 # lint + mypy + pyrefly + contracts + full pytest w/ coverage
```

Expected: everything green **except** the two intentionally-staged doc-gate reds
(`test_doc_links`, `test_historical_workspace_docs_have_top_level_superseded_banner`) —
they are row L3's exercise material and stay red until L3 runs.

---

# PART 2 — live verification (provider-backed; bash; consumes tokens)

**Binary pinning:** every command below uses `./.venv/bin/fa`. On operator hosts, `fa`
on PATH is `scripts/fa` — the docker-compose wrapper — which would run the row *inside
the agent container* (state under `/srv/first-agent/state/...`, blind to host paths).

**Host bootstrap (once, operator hosts).** Host-side `fa` reads routes from
`~/.fa/models.yaml` and keys from a FILE-ONLY secret store (`~/.fa/.env`; no env-var
fallback by design). Production copies live in the compose volume — adjust paths:

```bash
sudo cp /srv/first-agent/secrets/fa.env ~/.fa/.env
sudo chown "$(id -un):" ~/.fa/.env && chmod 600 ~/.fa/.env
sudo cp /srv/first-agent/state/models.yaml ~/.fa/models.yaml
sudo chown "$(id -un):" ~/.fa/models.yaml
# no chat role in the production config? clone the coder chain (identical routes
# are deduped by fa routing-check, so sharing provider+model is safe):
grep -q '^chat:' ~/.fa/models.yaml || { echo "chat:"; sed -n '/^coder:/,/^[a-z_]*:$/{/^coder:/d;/^[a-z_]*:$/d;p;}' ~/.fa/models.yaml; } >> ~/.fa/models.yaml
grep -A2 '^chat:' ~/.fa/models.yaml    # sanity: role present
```

If the production models.yaml has no `coder:` role either, add a `chat:` block by hand
per `knowledge/templates/models.yaml.example`. The driver exports `FA_SECRETS_FILE`
automatically once `~/.fa/.env` exists (its isolated `FA_STATE_ROOT` hides the default
location from fa).

**Capture setup (run once per session — the S11 data feed):**

```bash
LEDGER="worklogs/reviews/live-trial-data"
mkdir -p "$LEDGER"
[ -f "$LEDGER/ledger.csv" ] || echo "run_id,date,row,recommended_mode,level_path,expansion_n,observed_n,exhausted,exit_code,notes" > "$LEDGER/ledger.csv"
```

After EVERY row below, capture (the ROW sets `$RID` — capture never runs first).
Driver rows (2.1) print their own run id and an isolated state root; for those export
`EVENTS="<driver-state-path>/session-log/$RID/events.jsonl"` before this block:

```bash
[ -n "${RID:-}" ] || { echo "ERROR: capture runs AFTER a row — set RID from that row's output first" >&2; exit 1; }
EVENTS="${EVENTS:-$HOME/.fa/session-log/$RID/events.jsonl}"
[ -f "$EVENTS" ] || { echo "ERROR: no events at $EVENTS — did the row actually run?" >&2; exit 1; }
cp "$EVENTS" "$LEDGER/$RID.events.jsonl"
MODE=$(grep -o '"recommended_mode": "[a-z_]*"' "$EVENTS" | head -1 | cut -d'"' -f4)
LEVELS=$(grep -o '"level_from": [0-9], "level_to": [0-9]' "$EVENTS" | sed 's/"level_from": //; s/, "level_to": />/' | tr '\n' ';')
printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,\n' "$RID" "$(date +%F)" "L1" "${MODE:-?}" "${LEVELS:-none}" \
  "$(grep -c '"kind": "scope_expansion"' "$EVENTS" || true)" \
  "$(grep -c '"kind": "expansion_observed"' "$EVENTS" || true)" \
  "$(grep -c '"kind": "expansion_exhausted"' "$EVENTS" || true)" "0" >> "$LEDGER/ledger.csv"
```

(Adjust the row label and exit code per row; `notes` is free text — e.g. "agent accepted
escalation", "one-shot advice ignored".)

## 2.1 Live trial driver (recommended; fully isolated)

```bash
scripts/run_live_expansion_trial.sh "simplify the main function in src/fa/cli.py without changing behaviour" 20
```

Runs in a **throwaway git worktree** + temp `FA_STATE_ROOT` + unique run-id (enforced by
the script; if `git worktree` is unavailable it asks before touching your repo). Reports
the deterministic footprint **from events.jsonl**: `scope_expansion` count + evidence
names, `expansion_observed` (near-miss telemetry), `expansion_exhausted`, invoke_workflow
mentions, handoff map presence. Pass `--clean` to remove the trial dir and prune the
worktree.

## 2.2 Row L1 — simple safe task must NOT be escalated

```bash
RID="cae-l1-$(date +%s)"
./.venv/bin/fa run --role chat --run-id "$RID" --max-turns 8 --detail verbose \
  --task "Create worklogs/reviews/live-check-notes.md (or append one line to it) noting the live sheet was checked today." \
  2>&1 | tee /tmp/cae_l1.log
echo "fa EXIT=${PIPESTATUS[0]}"
EVENTS="$HOME/.fa/session-log/$RID/events.jsonl"
grep -q '"kind": "scope_expansion"' "$EVENTS" \
  && echo "  [NOTE] unexpected scope_expansion for a docs-only task — inspect $EVENTS" \
  || echo "  [PASS] no escalation on a safe docs task"
```

Expect: a couple of turns, only the safe-tier doc touched, no posture change. (`live-check-notes.md`
need not pre-exist; `worklogs/reviews/` is safe tier either way.)

## 2.3 Row L2 — deceptive wording on a HIGH-tier path arms/escalates (isolated worktree)

The task really touches `src/`, so run it where the agent cannot hurt your checkout:

```bash
WT="$(mktemp -d)/wt"
git worktree add --detach "$WT" HEAD
RID="cae-l2-$(date +%s)"
./.venv/bin/fa run --role chat --run-id "$RID" --workspace "$WT" --max-turns 20 --detail verbose \
  --task "simplify the main function in src/fa/cli.py — make _cmd_stats a bit shorter without changing behaviour" \
  2>&1 | tee /tmp/cae_l2.log
echo "fa EXIT=${PIPESTATUS[0]}"
EVENTS="$HOME/.fa/session-log/$RID/events.jsonl"
grep -q '"kind": "scope_expansion"' "$EVENTS" && echo "  [PASS] scope_expansion fired on high-tier evidence" || echo "  [NOTE] no scope_expansion (src/ not touched within turn cap)"
grep -qE 'read_high_arm|high_tier_write|verify_failed' "$EVENTS" && echo "  [PASS] expansion evidence name present" || echo "  [NOTE] no evidence names in $EVENTS"
grep -q "Start here" /tmp/cae_l2.log && echo "  [PASS] planner handoff map reached the workflow" || echo "  [NOTE] no handoff (model finished in chat)"
# cleanup (review the worktree diff first if you want the agent's edits):
git -C "$WT" diff --stat
git worktree remove --force "$WT"
```

## 2.4 Row L3 — staged doc-integrity defect (full cycle, REAL repo by design)

L3's point is fixing the staged defect **in place** (broken internal doc links + the
moved historical doc). Mandatory procedure:

```bash
# PRE: the working tree MUST be clean — abort otherwise.
[ -z "$(git status --porcelain)" ] || { echo "ABORT: commit or stash first (L3 edits the real repo)"; }
echo "-- staged defect (pre-run) --"; uv run python scripts/check_doc_links.py 2>&1 | tail -2
RID="cae-l3-$(date +%s)"
./.venv/bin/fa run --role chat --run-id "$RID" --workspace "$(pwd)" --max-turns 40 --detail verbose \
  --task "The repo has broken internal documentation links (run scripts/check_doc_links.py). Investigate and fix what you can, verify with the checker, and report what you changed." \
  2>&1 | tee /tmp/cae_l3.log
echo "fa EXIT=${PIPESTATUS[0]}"
EVENTS="$HOME/.fa/session-log/$RID/events.jsonl"
echo "scope_expansion events: $(grep -c '"kind": "scope_expansion"' "$EVENTS" || true)"
echo "near-miss observations: $(grep -c '"kind": "expansion_observed"' "$EVENTS" || true)"
grep -q '"kind": "expansion_exhausted"' "$EVENTS" && echo "  [OBS] K budget exhausted -> operator-report path" || true
grep -q "Start here" /tmp/cae_l3.log && echo "  [OBS] planner received a handoff file map" || true
echo "-- POST (mandatory): review what the agent changed, then keep or revert --"
git diff --stat
uv run python scripts/check_doc_links.py 2>&1 | tail -2
# keep:  git add -A && git commit   |   revert:  git restore . && git clean -fd
```

Judge (not auto-asserted): did it use the checker as the oracle rather than guess? Did it
distinguish **archived** links (a flattened-archive artifact) from live docs instead of
rewriting history destructively? Did any escalation carry a useful **Start here** map? Did
it stop at the K budget and report cleanly? **Was the one-shot escalation advice acted
on?** (F13 watch-item — note it in the ledger.)

## 2.5 Row L4 — post-run durable history

Two durable stores hold trial rows — check BOTH (bare `fa` on PATH is the compose
wrapper → would show the agent container's production history instead):

```bash
# (1) L1–L3 rows: default state root (~/.fa) — no FA_STATE_ROOT export here.
# (2) driver (2.1) rows: the trial state root the driver printed ("state: <path>").
for ROOT in "DEFAULT:$HOME/.fa" "TRIAL:<trial-state-path-from-driver-output>"; do
  LABEL="${ROOT%%:*}"; PATHV="${ROOT#*:}"
  echo "== $LABEL ($PATHV) =="
  FA_STATE_ROOT="$PATHV" ./.venv/bin/fa stats --global-history --output json 2>/dev/null | uv run python -c '
import json,sys
try: d=json.load(sys.stdin)
except Exception as e: print("  [NOTE] no global-history json:", e); sys.exit(0)
rows = d if isinstance(d,list) else d.get("runs") or d.get("rows") or []
print(f"  rows visible: {len(rows)}")
for r in rows[-6:]:
    print("   ", r.get("run_id"), "| role=", r.get("role"), "| exit=", r.get("exit_code"))
'
  FA_STATE_ROOT="$PATHV" ./.venv/bin/fa stats --calibration 2>&1 1>/dev/null | head -14
done
```

Note the `cae-*` / `s10-live-*` rows: they are trial data inside your real calibration
table — the ledger run-ids let S11 exclude them.

---

## Result ledger (fill in as you run)

| Check | What it proves | Result |
|---|---|---|
| 1.1 harness `EXIT=0` (151/151) | off-LLM engine behaves to spec across S1–S10.9 | |
| 1.2 CLI calibration smoke | real `fa stats --calibration` JSON shape + gate off | |
| 1.3 `just check` | full repo gate (only the 2 staged doc reds) | |
| 2.1 live driver | isolated session + JSONL footprint | |
| 2.2 L1 safe task | no false escalation on a safe docs task | |
| 2.3 L2 deceptive high-tier (worktree) | evidence (not wording) drives escalation | |
| 2.4 L3 doc-defect full cycle | triage → evidence → escalate/handoff discipline | |
| 2.5 L4 durable history | chat + nested workflow recorded; calibration updates | |
| capture | `live-trial-data/` holds events.jsonl per row + ledger.csv | |

**Sign-off:** Part 1 `EXIT=0` on the live host = the shipped engine behaves to spec
off-LLM. Part 2 pasted back + `live-trial-data/` committed = the live-contour
measurements that feed the final ADR-16 constant tuning and the slice-S11 closure.
