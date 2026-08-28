# Complexity-Aware Execution — live verification (slices S1–S10)

**Feature:** chat role + deterministic scope estimation + evidence-driven workflow
escalation + E3 cost/calibration.
**Plan:** `worklogs/implementation-plans/PLAN-complexity-aware-execution-chat-role.md`
(parent S1–S11) and `PLAN-scope-control-S10-final.md` (S10 detail, operator workspace).
**Date:** 2026-08-29 · **Base:** branch with S10 merged (`fa` 0.1.0).

This is the operator checklist for the chat/contour work. It has two parts:

1. **Offline verification — run a script.** The deterministic, no-provider engine checks
   ship as a runnable, gated harness (`scripts/verify_complexity_aware_execution.py`,
   ~130 assertions) plus a real-CLI calibration smoke. It exercises every slice S1–S10
   with no LLM and no token spend.
2. **Live verification — run the real agent.** A shell driver
   (`scripts/run_live_expansion_trial.sh`) and copy/paste rows below run a provider-backed
   chat session in an isolated workspace and surface the engine's durable footprint.

| Property | How it is enforced |
|---|---|
| No LLM cost for offline checks | the Python harness mocks nothing LLM-side; it calls the shipped engine directly |
| Never writes your real `~/.fa/global_history.db` | every seeded-DB check uses a throwaway `FA_STATE_ROOT` |
| Never edits your real `~/.fa/config.yaml` / `models.yaml` | toggle checks parse temp text through the real loader |
| Idempotent / repeatable | each block makes its own temp root; the offline harness has no side effects |
| Cannot silently "pass" | every offline check ends with an explicit pass/fail count and non-zero exit on failure |
| Live runs are isolated | a unique `--run-id`, a temp `FA_STATE_ROOT`, and (by default) your repo as read-mostly workspace |

> **Prerequisite for live rows only:** `~/.fa/models.yaml` needs a top-level `chat:` key.
> The offline harness and the CLI calibration smoke need no provider at all.

---

# PART 1 — offline deterministic verification (no provider)

## 1.1 Run the engine harness (one command)

Covers every shipped slice with runtime-computed oracles:

```bash
cd "$(git rev-parse --show-toplevel)"
python scripts/verify_complexity_aware_execution.py        # full S1–S10
echo "EXIT=$?"
```

Expected tail:

```
=== S10-G10 — two-layer premise (wording under-scopes, evidence escalates) ===
  [PASS] evidence engine caught every cue-free high-tier task (EN+RU)
================================================================
  133/133 checks passed  — ALL GREEN
================================================================
```

`EXIT=0` means every assertion passed. Run a single slice with `--only <substring>`
(the substring matches a checker function):

```bash
python scripts/verify_complexity_aware_execution.py --only check_s10_calibration
python scripts/verify_complexity_aware_execution.py --only check_s8_cost_model
```

What it asserts, by slice:

| Slice | Checks |
|---|---|
| **S1** estimator | L1/L2/L3 cue mapping, confidence in (0,1], cue-free heavy wording under-scopes to L1, non-English (RU) classifies, blank task raises |
| **S2** chat registry | chat role exposes `fs_read_file`, `fs_write_file`, `fs_run_bash`, `fs_search` (generalist set; write tools are withheld at the gate, not absent) |
| **S3** seed mapping | `difficulty_to_level`: chat_direct→1, chat_planned→2, workflow_linear→3; unknown raises |
| **S4** tool + K | K=2 → ok/ok/`workflow_budget_exhausted`; the denied call never reaches the runner; K read from context (K=3 runs a third); no-context → `workflow_unavailable`; child run id derived, distinct, ≤128 chars |
| **S5** ACRR + history | ACRR = (actual−floor)/floor (0 at floor, None when floor≤0); read amplification; global-history insert/replace round-trip on run_id |
| **S7** routing gate | gate **off** ⇒ never withhold; on + confident workflow_linear + chat ⇒ withhold; only chat role gated; `None` estimate fails open; confidence floor 0.8 |
| **S8** cost model | fitted weights α1.0 / β≈0.000415 / γ0.1 / δ1.5; `C` arithmetic; floor = 0 with no change set, >0 with a real file; floor derives from the run's **own** paths (self-referential) |
| **S10 CT1** expansion | clean/bulk-silent/read-arm→L2/write→L3/verify-failed→L3/medium-silent/workflow_linear-silent; L2 no re-arm; ceiling-3; verify_failed dominates; warm/cold skill select |
| **S10 CT3** path tiers | src/hooks/manifests/`.github`→high; tests/knowledge/scripts→medium; archive→safe; unknown→medium; `src-legacy` boundary; read/write split; empty→0 not "safe"; MAX combine; config additivity + warning |
| **S10 CT4** observations | clean L1 empty; L3 replaces L2 (no stale skill line); full skill body never in text (rides `skills_conditional`); medium→targeted-test nudge; exhausted terminal; 1800-char cap |
| **S10 CT6** handoff | sections Goal/Start here/Observed/Modified/Leads/“Do exactly”; Start here ≤5, leads ≤10, total ≤30; empty facts omit the file map |
| **S10 CT8** calibration | runs_total counts **all** runs; success_rate = ok/total; ACRR successes-only; all-failed → 0.0 flagged; n<10 not flagged; rate exactly 1−ε not flagged; gate surfaces **off** |
| **S10 F4** log kinds | `scope_expansion`/`expansion_exhausted` registered; `scope_tripwire` retained as dormant alias with **no** producer |
| **S10 G10** two-layer | 8 cue-free tasks (EN + terse RU) under-scope to chat_direct yet the evidence engine escalates to L2/L3 |

## 1.2 Real-CLI calibration smoke (no provider)

Drives the actual `fa stats --calibration` command against an isolated state root and
asserts the JSON the CLI really emits. Copy/paste:

```bash
cat > /tmp/cae_cal.sh <<'SHEOF'
#!/usr/bin/env bash
set -uo pipefail
export FA_STATE_ROOT="$(mktemp -d)"; trap 'rm -rf "$FA_STATE_ROOT"' EXIT
FA="${FA:-$(command -v fa || echo ./.venv/bin/fa)}"
python - <<'PY'
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
python - "$FA_STATE_ROOT/cal.json" <<'PY'
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

The same checks run in CI via `just check`; the offline engine portion is also covered by
the pytest suite (`tests/test_expansion.py`, `test_path_risk.py`, `test_observations_builder.py`,
`test_skill_injection.py`, `test_scope_expansion_wiring.py`, `test_handoff_payload.py`,
`test_calibration_success_rate.py`, `test_r1_heldout_wording.py`, `test_r2_deceptive_variants.py`).

```bash
just check                 # lint + mypy + pyrefly + contracts + full pytest w/ coverage
# or just the S10 targets:
python -m pytest tests/test_expansion.py tests/test_path_risk.py tests/test_observations_builder.py \
  tests/test_scope_expansion_wiring.py tests/test_handoff_payload.py \
  tests/test_calibration_success_rate.py tests/test_r1_heldout_wording.py \
  tests/test_r2_deceptive_variants.py -q
```

---

# PART 2 — live verification (provider-backed)

These run the real chat role. They cannot self-oracle the model's choices; they assert
deterministic scaffolding and point you at the durable signals (the `scope_expansion` event
and the rendered advisory). Live rows consume provider tokens.

## 2.1 Live trial driver (recommended)

Runs an isolated chat session and prints the engine's deterministic footprint:

```bash
scripts/run_live_expansion_trial.sh "simplify the main function in src/fa/cli.py without changing behaviour" 20
```

It creates a throwaway `FA_STATE_ROOT`, a unique run-id, runs `fa run --role chat
--detail verbose`, then reports: number of `scope_expansion` events, the evidence names
seen (`read_high_arm` / `high_tier_write` / `verify_failed`), whether escalation advice /
a high-tier verification line / a planner handoff map appeared, and whether the K budget
was exhausted. The full log is kept in a printed temp dir; pass `--clean` to remove it.

## 2.2 Row L1 — simple safe task must NOT be escalated

```bash
RID="cae-l1-$(date +%s)"
fa run --role chat --run-id "$RID" --max-turns 8 --detail verbose \
  --task "Add a one-line comment to worklogs/reviews/README.md noting the live sheet was checked." \
  2>&1 | tee /tmp/cae_l1.log
echo "fa EXIT=${PIPESTATUS[0]}"
grep -q "scope_expansion" /tmp/cae_l1.log \
  && echo "  [NOTE] unexpected scope_expansion for a docs-only task" \
  || echo "  [PASS] no escalation on a safe docs task"
```

Expect: a couple of turns, only the doc touched, no workflow.

## 2.3 Row L2 — deceptive wording on a HIGH-tier path arms/escalates

Cue-free wording, but the task really touches `src/`. Expect a `scope_expansion` event
(read arm to level 2, or write/verify to level 3) and — if the model accepts the advice —
an `invoke_workflow` call whose handoff carries a **Start here** map.

```bash
RID="cae-l2-$(date +%s)"
fa run --role chat --run-id "$RID" --workspace "$(pwd)" --max-turns 20 --detail verbose \
  --task "simplify the main function in src/fa/cli.py — make _cmd_stats a bit shorter without changing behaviour" \
  2>&1 | tee /tmp/cae_l2.log
echo "fa EXIT=${PIPESTATUS[0]}"
grep -q "scope_expansion" /tmp/cae_l2.log && echo "  [PASS] scope_expansion fired on high-tier evidence" || echo "  [NOTE] no scope_expansion (src/ not touched within turn cap)"
grep -qE "read_high_arm|high_tier_write|verify_failed" /tmp/cae_l2.log && echo "  [PASS] expansion evidence name present" || echo "  [NOTE] check --detail debug event log"
grep -q "Start here" /tmp/cae_l2.log && echo "  [PASS] planner handoff map reached the workflow" || echo "  [NOTE] no handoff (model finished in chat)"
grep -q "Risk tier high" /tmp/cae_l2.log && echo "  [PASS] high-tier verification posture shown" || true
```

## 2.4 Row L3 — staged doc-integrity defect (full-cycle capability trial)

A real defect is staged on purpose: the repo ships with broken internal doc links
(`scripts/check_doc_links.py`) and a moved historical doc. The request *sounds* like a docs
chore (text estimator under-scopes it) but a proper fix means reading `scripts/`, running
the checker, and working across the tree — a genuine escalation/triage exercise.

```bash
echo "-- staged defect (pre-run) --"; python scripts/check_doc_links.py 2>&1 | tail -2
RID="cae-l3-$(date +%s)"
fa run --role chat --run-id "$RID" --workspace "$(pwd)" --max-turns 40 --detail verbose \
  --task "The repo has broken internal documentation links (run scripts/check_doc_links.py). Investigate and fix what you can, verify with the checker, and report what you changed." \
  2>&1 | tee /tmp/cae_l3.log
echo "fa EXIT=${PIPESTATUS[0]}"
echo "scope_expansion events: $(grep -c scope_expansion /tmp/cae_l3.log)"
grep -q "invoke_workflow" /tmp/cae_l3.log && echo "  [OBS] agent accepted escalation to workflow" || echo "  [OBS] agent handled in chat"
grep -q "workflow_budget_exhausted" /tmp/cae_l3.log && echo "  [OBS] K budget exhausted -> operator-report path" || true
grep -q "Start here" /tmp/cae_l3.log && echo "  [OBS] planner received a handoff file map" || true
echo "-- after-run --"; python scripts/check_doc_links.py 2>&1 | tail -2
```

Judge (not auto-asserted): did it use the checker as the oracle rather than guess? Did it
distinguish **archived** links (a flattened-archive artifact) from live docs instead of
rewriting history destructively? Did any escalation carry a useful **Start here** map? Did
it stop at the K budget and report to the operator cleanly?

## 2.5 Row L4 — post-run durable history

```bash
fa stats --global-history --output json 2>/dev/null | python -c '
import json,sys
try: d=json.load(sys.stdin)
except Exception as e: print("  [NOTE] no global-history json:", e); sys.exit(0)
rows = d if isinstance(d,list) else d.get("runs") or d.get("rows") or []
print(f"  rows visible: {len(rows)}")
for r in rows[-6:]:
    print("   ", r.get("run_id"), "| role=", r.get("role"), "| exit=", r.get("exit_code"))
'
fa stats --calibration 2>&1 1>/dev/null | head -12
```

---

## Result ledger (fill in as you run)

| Check | What it proves | Result |
|---|---|---|
| 1.1 harness `EXIT=0` | off-LLM engine behaves to spec across S1–S10 | |
| 1.2 CLI calibration smoke | real `fa stats --calibration` JSON shape + gate off | |
| 1.3 `just check` | full repo gate (lint/types/contracts/tests) | |
| 2.1 live driver | footprints a real chat session | |
| 2.2 L1 safe task | no false escalation on a simple docs task | |
| 2.3 L2 deceptive high-tier | evidence (not wording) drives escalation | |
| 2.4 L3 doc-defect full cycle | triage → evidence → escalate/handoff discipline | |
| 2.5 L4 durable history | chat + nested workflow recorded; calibration updates | |

**Sign-off:** Part 1 `EXIT=0` on the live host = the shipped engine behaves to spec
off-LLM. Part 2 pasted back = the live-contour measurements that feed the final ADR-16
constant tuning and the slice-S11 closure.
