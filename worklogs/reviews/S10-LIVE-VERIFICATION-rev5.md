# S10 Live Verification — operator runbook (rev5)

**Authoritative doc for live-verifying the `fa` harness on the production
deployment.** Self-contained: follow it top to bottom; no knowledge of earlier
revisions is needed (history: §10).

**What rev5 adds over rev4.** S12.7 (read budget / framing / guard / fs_search
restructure) is now merged. rev4's `l2` row historically died on a LoopGuard
path-thrash (`LoopGuard: path 'src/fa/cli.py' thrashed across 5 distinct
attempts`) — the defect S12.7 was built to close (D10 / GAP1). rev5 therefore:
1. adds an **S12.7 gate** (§4) — run it FIRST; it proves the gaps that blocked
   `l2`/`l3` are closed *and* that every module S12.7 touched serves its
   function under real agent behaviour;
2. **updates the `l2`/`l3` expectations and triage** — a LoopGuard stop on
   *advancing* reads is now a REGRESSION (fail), not a known finding to route
   around (§5, §8);
3. turns on a **model tool-UX self-report** and **full model text every turn**
   (§6) so the capable model surfaces residual gaps you would otherwise miss.

Everything runs through ONE committed script — `scripts/run_live_check.sh` —
pinned by `tests/test_live_check_script.py`. You paste one short command per
row; the script prints the verdicts and captures the evidence.

---

## 1. What the script does (deployment anatomy in one paragraph)

`fa` on this host is the wrapper `./scripts/fa` → `docker compose exec
first-agent fa …` (see `worklogs/DEPLOYMENT-ANATOMY.md`). The agent container
holds **no LLM keys** — `fa-egress-proxy` injects them; config inside the
container is the read-only bind of `/srv/first-agent/routing/models.yaml`.
Rows execute inside the container's per-session workspace clone
(`/sessions/<id>` from `/repo`), so **the host checkout is never modified**.
The script reads run events from the host side of the state bind
(`/srv/first-agent/state/session-log/<run_id>/events.jsonl`) and appends every
row to the ledger under `worklogs/reviews/live-trial-data/`.

There is nothing to copy, configure, or clean up beforehand. Never copy
`fa.env` or `models.yaml` anywhere; keys live only in the proxy.

## 2. Prerequisites

- **S12.7 merged and the live host updated.** The gate rows test S12.7
  behaviour; against a pre-S12.7 build they will (correctly) fail. Confirm the
  container engine carries the slice: `fa update` after the merge, then
  `scripts/run_live_check.sh setup`.
- Stack up: `fa status` shows `first-agent` and `fa-egress-proxy` healthy.
- Run from any checkout that contains these scripts — the ledger is written
  there; commit the evidence there. Rows always execute the container engine,
  built from and cloning `/srv/first-agent/repo/First-Agent-dev` (absolute
  binds). To measure updated engine code: update that checkout, `fa update`.
- **Pinned single model** for comparability (the rows are behavioural; mixing
  models mid-suite muddies the signal). Re-runs use the same pin.

## 3. Preflight

```bash
scripts/run_live_check.sh setup
```

Healthy output ends with `READY.` and shows: stack status (both services
`Up (healthy)`); `fa probe: OK`; `fa routing-check: OK`; history schema OK;
session-manifest audit (`[BLOCK]` lines abort — see §8); the S12.4
`intent_guard.mode` and S12.6 `tool_batching.enabled` flag states; and the
ledger path. Setup aborts (exit 2, `ERROR:`) if anything is unhealthy — fix it
first; rows cost tokens and must not run against a broken stack.

## 4. S12.7 gate — run FIRST (goals 1 + 2)

Each row is one bounded live session. The script asserts structural signals
over `events.jsonl` (tool-call params, artifacts, guard events), the tool-call
*sequence* (ladder / resume-follow / artifact-follow), and the model's own
`TOOL_FEEDBACK` block (§6). A row exits `0` (objective met) or `3` (objective
missed — a finding, flagged in the ledger notes). List them any time with
`scripts/run_live_check.sh s127-list`.

```bash
scripts/run_live_check.sh s127-advancing          # ← headline: D10/GAP1 closure
scripts/run_live_check.sh s127-repeat
scripts/run_live_check.sh s127-pingpong
scripts/run_live_check.sh s127-read-small
scripts/run_live_check.sh s127-read-oversize
scripts/run_live_check.sh s127-read-window
scripts/run_live_check.sh s127-artifact-follow
scripts/run_live_check.sh s127-artifact-unknown
scripts/run_live_check.sh s127-bash-tail
scripts/run_live_check.sh s127-bash-stderr
scripts/run_live_check.sh s127-bash-small
scripts/run_live_check.sh s127-outline
scripts/run_live_check.sh s127-search-modes
scripts/run_live_check.sh s127-search-leniency
scripts/run_live_check.sh s127-search-removed-mode
```

| Row | Proves | Key verdict |
|---|---|---|
| `s127-advancing` | **The gap that blocked `l2` is closed.** Five *different* windows of `src/fa/cli.py` (154 KB, 74 symbols) are served with **no LoopGuard stop**; session ends normally. Pre-S12.7 this exact pattern tripped Detector-2 and killed the run. | `[PASS] no LoopGuard stop on 5 advancing reads`; a LoopGuard stop here = **exit 3, S12.7 regression** |
| `s127-repeat` | Detector-1 still guards: an *identical* read repeated warns then denies **in-band** with the `LoopGuard:` reason prefix (no zombie `run_stopped` after). | `[PASS] identical-repeat produced a guard signal` |
| `s127-pingpong` | Detector-3 (preventive): exact A-B alternation warns at 3 cycles, denies at 4. Field-driven — a miss is a `[NOTE]`, not a failure (confirm the model truly alternated via the timeline). | `[PASS]`/`[NOTE] ping-pong …` |
| `s127-read-small` | T1: a small file arrives whole and **inline** — no artifact minted. | `[PASS] small read stayed INLINE` |
| `s127-read-oversize` | T3 + CT6 audit: an oversize read elides to a followable artifact; **events keep the full raw, never a 500-char `preview`** (the deleted state.py path stays deleted). | `[PASS] … artifact` + `[PASS] … NOT a … preview` |
| `s127-read-window` | T2: a windowed read carries a resume line; following it returns the contiguous next block (≥2 reads). | `[PASS] resume was followed (>=2 …)` |
| `s127-artifact-follow` | CT7: an `[artifact: id]` pointer is followable to the full payload via `fs_read_file {artifact_id}`. | `[PASS] the artifact_id was followed` |
| `s127-artifact-unknown` | CT7 security: a fabricated id **fails closed** with `artifact_not_found` steering; the session continues (no crash, no existence oracle). | `[PASS] unknown id failed closed` |
| `s127-bash-tail` | CT4: >30 KB stdout is **tail-biased** (the end survives), flagged `truncated`, rest stored as an artifact. | `[PASS] … flagged truncated and/or stored` |
| `s127-bash-stderr` | CT4: stderr is preserved in the **last bytes** of the visible result (the error is what the model sees). | `[PASS] the failure was surfaced` |
| `s127-bash-small` | CT4 complement: small output is whole, unflagged, artifactless. | `[PASS] small output stayed inline` |
| `s127-outline` | CT9 + the discovery ladder: `output_mode='outline'` gives exact symbol ranges (`_cmd_stats`) that paste straight into a windowed read. | `[PASS] outline … _cmd_stats … range read back` |
| `s127-search-modes` | CT8: no-query `files` listing + `matches` grep return the current row shapes. | `[PASS] matches mode was exercised` |
| `s127-search-leniency` | CT11 + the operator's "forgiving tools" rule: all six removed knobs sent at once are **accepted-but-ignored with warnings**, not enum-rejected (no wasted turn). | `[PASS] … NOT rejected` |
| `s127-search-removed-mode` | GAP12: a removed mode (`regions`) **steers** (no silent alias); the model re-issues with a valid mode. | `[PASS] recovery: a valid mode was issued` |

**Gate criterion:** every row exits `0` (or a recorded, explained `3`). The
`s127-advancing` row is the one that must pass before you trust the `l2`/`l3`
re-run — it is the direct regression test for the defect that stopped rev4.

## 5. S10 rows — re-run in full (goal 3)

Only after the gate is green. One command each, in order:

```bash
scripts/run_live_check.sh smoke
scripts/run_live_check.sh env
scripts/run_live_check.sh pty
scripts/run_live_check.sh l1
scripts/run_live_check.sh l2
scripts/run_live_check.sh l3
scripts/run_live_check.sh l4
scripts/run_live_check.sh ledger
```

| Row | Task | Expected verdicts |
|---|---|---|
| `smoke` | 2-turn "reply OK, no tools" (cheap) | `[PASS] chat chain end-to-end`. Proves the `chat` chain + session mechanics before expensive rows. (The self-report suffix is inert here — smoke uses no tools.) |
| `env` | S12 readiness handoff (6 turns) — run `pytest --version` | `[PASS] venv pytest reachable without archaeology`. `command not found` / `No module named pytest` anywhere = `[FAIL] env probe`, exit 3, `ENV_PROBE_FAILED` |
| `pty` | S12 pty timeout recovery (6 turns) — `sleep 35` then `echo RECOVERED` | `[PASS] pane reclaimed … (pty preamble x0 or x1)`; >1 timeout preamble or missing `RECOVERED` = `[FAIL] pty probe`, exit 3 |
| `l1` | docs-only note (8-turn cap) — negative control | `[PASS] no escalation on a safe docs task`. Any `scope_expansion` = `[FAIL]`, exit 3, `NEGATIVE_CONTROL_FAILED`. `[OBS] IntentGuard denials: N` is ceremony cost, never a failure |
| `l2` | shorten `_cmd_stats` in `src/fa/cli.py` (20 turns) | `[PASS] scope_expansion fired`. **rev5 change:** the agent should now reach `_cmd_stats` via outline→window, *not* by thrashing the whole file. A `LoopGuard` stop on **advancing** reads here is a **regression** (D10 reopened) — see §8. No escalation on a clean run = `[FAIL]`, exit 3, `NO_ESCALATION_WHERE_EXPECTED` |
| `l3` | fix broken doc links, full cycle (40 turns) | same escalation signals as l2 (no escalation is NOT a failure — the doc path is safe); IntentGuard making the model draft a PR intent first is the guardrail working |
| `l4` | durable history + calibration | `rows visible: N` + a `this trial (cae-*): N row(s)` section; calibration buckets printed |
| `ledger` | — | the capture table, formatted |

Exit codes: `0` objective met · `1` run failure (`fa rc!=0` / no events) ·
`2` preflight/usage error · `3` run completed but the row objective was missed
(a finding — always flagged in the ledger `notes`).

Run ONE command at a time and review before the next. Each row prints
`RID=cae-<row>-<ts>-<pid>`, then a **turn timeline** (model latency per turn,
tools per turn, `✗:Guard` denials, `⤴` escalations, `loop:` warnings), each
turn's **full model text** as an indented `💬` block (§6), the model's
**`TOOL_FEEDBACK` self-report** (§6), and a closing `summary:` line. The ledger
row and a copy of `events.jsonl` are captured automatically under
`worklogs/reviews/live-trial-data/`; full stdout stays at
`/tmp/cae_<run-id>.log`.

## 6. Model self-report + full model text (new in rev5)

Two switches make the capable model an instrument for finding residual gaps:

- **Tool-UX self-report (on by default).** Every live task — gate rows *and*
  legacy rows — is appended with an instruction to end its final message with a
  `TOOL_FEEDBACK:` block grading the tools it used: *confusing output?
  truncated? lost context? worked as expected? anything that cost a turn?*
  This matters because the **model-visible framed string is not logged**
  (events keep the full raw, RD-1) — the model's own words are the only direct
  window into what it actually saw. The script extracts the block and prints it
  under `── model tool-UX self-report ──` with a `📝` prefix; `[NOTE] no
  TOOL_FEEDBACK block` means the model did not comply (record it). Disable with
  `CAE_SELFREPORT=0`.
- **Full model text every turn (on by default for the gate rows).** Within the
  `s127-*` rows, `CAE_LLM_FULL` defaults to `1`, so the timeline `💬` block
  prints each turn's complete model output instead of capping at 2000 chars.
  The legacy `smoke`→`l4` rows keep the S12.6c 2000-char default cap (the
  contract `tests/test_live_check_script.py`'s battery pins); prefix any of
  them with `CAE_LLM_FULL=1` to uncap it (e.g.
  `CAE_LLM_FULL=1 scripts/run_live_check.sh l2`). `CAE_LLM_FULL=0` forces the
  cap anywhere. For per-event ms timing as well, prefix a row with
  `CAE_DETAIL=debug`.

Read the `📝` blocks as data: a model that says "the read was cut but the frame
told me how to continue" is the framing contract working end-to-end; one that
says "I lost track of what I'd already read" is a residual gap to file.

## 7. Sign-off

1. The S12.7 gate (§4) is all `exit 0` (or explained `3`s) — **`s127-advancing`
   must be green.**
2. `scripts/run_live_check.sh ledger` shows all rows with `exit_code=0` (or a
   recorded, explained failure).
3. Commit the evidence:

```bash
git add worklogs/reviews/live-trial-data && git commit -m "live: S10 rev5 verification ledger + events (S12.7 gate + s10 rows)"
```

That commit = Part 2 complete. The ledger (`ledger.csv`: `run_id,date,row,
recommended_mode,level_path,expansion_n,observed_n,exhausted,exit_code,notes`
plus the captured `*.events.jsonl`) is the data feed for S11 constant closure
(ε, K, tier prefixes, caps).

## 8. Failure triage

| Signal | Meaning → action |
|---|---|
| `s127-advancing` exits 3 (`S127_ADVANCING_FAILED`) | **D10/GAP1 regression** — the guard tripped on advancing reads, or the reads were not served. This is the defect S12.7 closed; if it is back, stop and inspect the events (`grep LoopGuard <events>`) before running `l2`/`l3` |
| `[STOP] abnormal stop: LoopGuard: …` on `l2`/`l3` | **rev5: a regression, not a known finding.** Pre-S12.7 this was D10 ("re-run with the file pre-read") — that workaround is obsolete. A LoopGuard stop on *advancing* reads means the framing/outline path did not prevent the thrash; inspect the timeline (did the model use outline, or guess windows?) and file it |
| `✗:LoopGuard` on *identical* repeated reads | Correct (Detector-1). Not a finding |
| `[FAIL] fa exited N` | the run itself failed (row exits `N`); printed verdicts are diagnostics only. Read `/tmp/cae_<run-id>.log` and `fa logs`; re-run after fixing |
| row exits `3` | run completed but the objective was missed — a finding to record (flag in ledger notes), not a stack problem |
| `[FAIL] no events file` | session never started. Run `setup` again; check `fa logs` |
| `[NOTE] no TOOL_FEEDBACK block` | the model did not emit the self-report; record it, consider a stronger instruction or a different model pin |
| `[NOTE] near-miss telemetry present (observed_n=N)` | escalation evidence existed but policy declined — S11 tuning data, not a failure |
| `[FAIL] env probe` / `[FAIL] pty probe` (exit 3) | S12 readiness/pty-reclaim broken — see the row's oracle in §5; P13 negative probe (venv removed) MUST exit 3 |
| `[BLOCK] <session>: …` at setup | a manifest making SessionManager refuse every new session. Quarantine the listed dir under `/srv/first-agent/state/sessions/`, re-run setup |
| `setup` dies on `fa probe failed` | stack/proxy/provider down — `fa status`, `fa logs`, fix before spending tokens |

Run ids are PID-unique and events are cleared pre-run, so a row can never be
scored against another row's events; a missing events file is always a FAIL,
never a silent PASS.

## 9. Offline-pinned (NOT live rows)

These S12.7 contracts are deterministic and already pinned by the offline
suites (`tests/test_s127_*.py`, 90 tests green); they are not worth a live LLM
session. Spot-check them on the live checkout if you want belt-and-braces:

- **Registry budget scatter** (`test_s127_budget.py`): the name→budget map
  equals the §11 table (7×32,768 + the deliberate small-tier outliers). This is
  an offline pin — **do not try to introspect it from the host**: the fa venv
  (`/opt/fa-venv`) and imports live *inside* the container (DEPLOYMENT-ANATOMY),
  so a host-side `python3 -c "import fa"` has no dependencies and is not the
  production mechanism. The live ceiling is proven *behaviourally* by the gate
  rows instead: `s127-read-oversize` elides a 154 KB file at the 32,768 ceiling
  and `s127-read-small` stays inline. Confirm the live build carries the slice
  with `fa update` (then `setup`).
- **Description ladder / cross-steering** (`test_s127_doc_gates.py`): the
  `fs_search` spec carries the files→outline→matches→read ladder, the ~500-line
  heuristic, and the `fs_reach` steer.
- **PauseGuard scoping** (`test_s127_guard.py`): a PauseGuard BETWEEN_ROUNDS
  deny continues the session (prefix-disjoint from LoopGuard). Needs an injected
  pause sentinel — not a natural agent task, so it stays offline.
- **Compaction self-store fallback** (`test_s127_audit.py`): masked tool_result
  rows reference a real `artifact_id`. Only fires on a long-enough session to
  compact; observe it opportunistically in `l3`/`l4` if it happens.
- **>200 KB skip report** (`test_s127_fs_surface.py`): `files` mode surfaces
  `skipped_large_files`. Needs a >200 KB fixture in the workspace clone
  (`src/fa/cli.py` is 154 KB, just under) — observe opportunistically.
- **pty-vs-subprocess retention parity** (`test_s127_bash_frame.py`): same tail
  contract on both executor paths.
- **Subagent FTS discovery (F1)**: `subagent_spawning_enabled` stays False in
  this slice, so there is no live subagent path to exercise; pinned offline.

## 10. History (do not follow these)

- `S10-LIVE-VERIFICATION-rev4.md`: superseded by rev5 (the S12.7 gate + the
  corrected LoopGuard triage). Kept as the evidence trail for the eight
  live-only defects that shaped the script. Its `l2` triage line ("LoopGuard on
  repeated reads = known finding D10, re-run with the file pre-read") is
  **obsolete** — S12.7 closed D10; do not follow it.
- `S10-LIVE-VERIFICATION-rev3.md`: superseded; evidence trail only.
- `scripts/run_live_expansion_trial.sh`: deprecated driver, kept for git history.
