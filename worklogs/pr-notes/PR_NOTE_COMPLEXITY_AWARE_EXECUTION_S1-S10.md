# Complexity-aware execution — chat role, deterministic routing, E3 cost model, and evidence-driven scope expansion (S1–S10)

Target branch: **`New-main-role-chat-and-complexity-aware-workflow-execution`**.
Patch: **`S10-complexity-aware-execution-2026-08-29.patch`** (`git apply`, 32 files,
+5358/−585). The patch base is the branch tip (`79153e9`); it applies cleanly to a fresh
checkout of that branch (`git apply --check` OK) and, once applied, the offline harness
runs green from the patch alone.

---

## Why

FA has two execution modes — direct `fa run` and multi-role `fa workflow` — and the
operator had to choose by hand for every task. That over-provisions simple tasks (the
largest token waste in E3) and under-provisions cross-file refactors. We land an automatic
routing layer built on the E3 paper's **Estimate → Execute → Expand** pattern, but with a
correction the evidence forced on us: **routing cannot depend on task wording** — the
lexical estimator reliably under-scopes genuinely heavy tasks phrased without cue words
(including the operator's terse Russian style). The safety net is therefore a second,
*evidence-driven* layer that escalates on what the run actually reads/writes, not on what
it said.

## What shipped (slices)

- **S1** — lexical scope estimator (`scope_estimator.py`): pure-Python, <1ms, no LLM call;
  cue words → `OperatingPoint(difficulty, scope, risk, confidence, recommended_mode)`.
- **S2** — chat role registry (`tools.build_chat_registry`): generalist read/write/edit/
  bash/search toolset; write tools are *withheld* only by the gate (never silently missing).
- **S3 / S3.5** — estimator wired into the CLI; `scope_estimate` observability to stats /
  blackboard / global history.
- **S4** — workflow controller extraction + **`invoke_workflow` tool**: escalates to the
  shared planner→coder→eval pipeline with a derived child run id; **K budget enforced in
  the tool only** — the (K+1)th call returns `workflow_budget_exhausted`.
- **S5** — **ACRR proxy** + global-history persistence (`runs_total`, `runs_succeeded`,
  ACRR, read amplification).
- **S7** — deterministic routing gate (`routing.should_withhold_write_tools`), fail-open,
  gated on confident `workflow_linear` estimates for the chat role only.
- **S8** — full E3 cost model (`acrr.py`): `C = α·T + β·tokens + γ·tools + δ·files` with
  fitted weights **α1.0 / β0.000415 / γ0.1 / δ1.5** (β fit so a median file's token cost
  is half its file cost; latency excluded for determinism); self-referential cost floor
  (**ACRR measures redundancy, never correctness**); calibration projection.
- **S10** — evidence-driven scope control:
  - **S10.1** `expansion.py` — three-level posture state machine (`next_level`): monotone,
    idempotent, ceiling 3. High-tier **write** → level 3; a failed **verify** command
    (`VERIFY_ONLY` via `bash_intent`) → level 3; high-tier **read** arms level 2; bulk
    counters fire only when a high tier is present (a large safe change stays silent).
  - **S10.2** `path_risk.py` — positional risk tiers (`src/` + root manifests = high;
    `tests/knowledge/scripts` = medium; `worklogs/...` = safe); unknown prefix → **medium**
    (fail safe); `MAX` combines lexical+path; config-driven with structured warnings.
  - **S10.3** `_inject.py` — deterministic L2 planner-skill injection (warm
    `feature-planning` / cold `plan-authoring`; full body on the entry turn only).
  - **S10.4** `observations.py` — per-turn advisory rebuilt by assignment (no stale L2
    line survives L3), tier-keyed verification posture, named eviction under the 1800-char
    cap, terminal budget-exhausted line.
  - **S10.5** workflow tool — live **planner handoff** from session facts (Goal / Start
    here ≤5 / Observed / Modified / Candidate leads ≤10 / positive "Do exactly"; ≤30
    paths; missing facts → goal-only, never a crash).
  - **S10.6** `calibration.py` — reliability view: **success_rate over ALL runs**, ACRR
    over successes only; `below_reliability_target` gated on `n ≥ min_flag_runs (10)` and
    `rate < 1−ε (ε=0.05)`; the auto-escalation gate **defaults OFF** (display-only,
    operator-toggleable).
  - **S10.7** — R1 held-out wording (14 pairs, EN + RU) and R2 deceptive-task suites prove
    the two-layer design: text under-scopes, evidence catches it.
  - **S10.8** — hand-applied mutation sweep: **all mutants killed, zero survivors**.
  - Log kinds: `scope_expansion` + `expansion_exhausted` added; the S7 `scope_tripwire`
    producer is retired but the enum member is kept as a **dormant alias** (the S8/S9
    projection still keys on it).

## Verification (all deterministic, no LLM)

- **`scripts/verify_complexity_aware_execution.py`** — new offline harness, **133
  assertions across S1–S10**, exit-nonzero on failure; `--only <slice>` available.
- **`scripts/run_live_expansion_trial.sh`** — provider-backed live driver: isolated temp
  state root + unique run id; reports the engine's durable footprint (`scope_expansion`
  events, evidence names, escalation/handoff/K signals).
- **`worklogs/reviews/S10-LIVE-VERIFICATION-rev2.md`** — the copy/paste operator sheet
  (offline harness + live rows incl. the staged doc-defect full-cycle trial).
- Full `just check` toolchain green: ruff + ruff-format, deptry, pylint (10.00/10),
  mypy `--strict` (403 files, 0 errors), pyrefly (0 errors), authoring, all contract
  scripts (dependency / producer-consumer / log-kind / no-mocked-dataclasses / dead-flags),
  shell syntax. Full pytest **3614 passed at ~85.8% coverage** (floor 80%).
- Stale-floor fix included: `check_cli_coverage_floor.py` no longer references
  `_run_adaptive`, which the S4a controller extraction moved out of `cli.py`.

## Known gaps / deliberately not in this PR

- **The escalation gate ships OFF** (Q25): mechanism + measurement are live; an
  auto-blocking policy stays display-only until live-contour data supports enabling it.
- ADR-16 stays **`Status: proposed`** until the live (provider-backed) contour validates
  the seeded constants (ε, K, tier prefixes, caps, fitted weights) in slice S11.
- **Two doc-integrity gates are intentionally left red** as a live-trial fixture: the
  flattened `worklogs/archive` broken links and the moved `knowledge/pr-notes/
  workspace-isolation.md` banner. Both are pre-existing and are the staged defect for the
  L3 live row.

## Main plans & docs used

- Plan: `worklogs/implementation-plans/PLAN-complexity-aware-execution-chat-role.md`
  (parent, S1–S11; the S10 index + S11 entry live here).
- Plan addendum: `worklogs/implementation-plans/PLAN-ADDENDUM-deterministic-routing-S7-S9.md`.
- S10 detail plan: operator workspace `PLAN-scope-control-S10-final.md` (SSOT for
  contracts CT1–CT11 / DP-1…DP-9 / Q22/Q25/Q26; not in-repo).
- ADR: `knowledge/adr/ADR-16-complexity-aware-execution.md` (updated with the shipped
  S7–S10 architecture addendum + the tuned-constants table).
- Verification sheet: `worklogs/reviews/S10-LIVE-VERIFICATION-rev2.md`.
- Research grounding: `knowledge/research/E3-and-code-as-harness-deep-dive-2026-08-26.md`
  (E3, arXiv 2607.13034; Code-as-Agent-Harness, arXiv 2605.18747), cited in ADR-16.

## Apply

```sh
git checkout New-main-role-chat-and-complexity-aware-workflow-execution
git apply --whitespace=nowarn S10-complexity-aware-execution-2026-08-29.patch
python scripts/verify_complexity_aware_execution.py   # expect 133/133 ALL GREEN
```
