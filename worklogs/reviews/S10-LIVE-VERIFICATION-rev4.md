# S10 Live Verification — operator runbook

**Authoritative doc for live-verifying complexity-aware execution (slices S1–S10.9)
on the production deployment.** Self-contained: follow it top to bottom; no
knowledge of earlier revisions is needed (history: §7).

Everything runs through ONE committed script — `scripts/run_live_check.sh` —
pinned by `tests/test_live_check_script.py` and exercised end-to-end by
`scripts/adversarial_battery_live_check.sh`. You paste one short command per
step; the script prints the verdicts and captures the evidence.

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

- Stack up: `fa status` shows `first-agent` and `fa-egress-proxy` healthy.
- Run from any checkout that contains these scripts — the ledger is written
  there; commit the evidence there. Your checkout location does not change
  what is measured: rows always execute the container engine, which is built
  from and clones `/srv/first-agent/repo/First-Agent-dev` (absolute binds).
  To measure updated engine code: update that checkout, `fa update`.

## 3. Preflight

```bash
scripts/run_live_check.sh setup
```

Healthy output ends with `READY.` and shows:

| Line | Meaning |
|---|---|
| stack status: both services `Up (healthy)` | containers running |
| `fa probe: OK` | proxy + at least one provider per chain reachable (a `⚠️ 429` on `chain[0]` with a green `chain[1]` is failover working — fine) |
| `fa routing-check: OK` | mounted routing config parses; `chat` role required |
| `history schema OK` / `migrated OK` | `global_history.db` usable (pre-S3.5 dbs are migrated automatically on open — additive, idempotent) |
| `sessions: 0 blocking, N pruned-workspace` | session-manifest audit; **pruned is informational**. `[BLOCK]` lines abort setup — see §6 |
| `intent_guard.mode: enforce (default)` / `observe (from …)` | S12.4 flag state read from the container config before tokens are spent. `observe` = IntentGuard evaluates and logs would-be denials but allows (no draft ceremony); `off` = guard not registered. Set via `feature_flags: intent_guard.mode:` in the container `~/.fa/config.yaml` |
| `tool_batching.enabled: true (default)` | S12.6 flag printout, same source |

Setup aborts (exit 2, `ERROR:` line) if anything above is unhealthy. Fix that
first; rows cost tokens and must not run against a broken stack.

## 4. Rows — one command each, in order

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
| `smoke` | 2-turn "reply OK, no tools" (cheap) | `[PASS] chat chain end-to-end`. **`setup`'s probe tests the `coder` chain — smoke is what proves the `chat` chain + session mechanics before expensive rows** |
| `env` | S12: readiness handoff (6 turns) — run `pytest --version` in the session workspace | `[PASS] venv pytest reachable without archaeology`. The version oracle reads the captured **events** (the console shows only the tool summary, never command stdout — S12.6b). The v4.4 l2 failure (D15: 12/20 turns burned hunting for pytest) must not recur: `command not found` or `No module named pytest` anywhere in events/transcript is a finding — `[FAIL] env probe`, **exit 3**, flag `ENV_PROBE_FAILED` |
| `pty` | S12: pty timeout recovery (6 turns) — `sleep 35` (times out by design), then `echo RECOVERED` | `[PASS] pane reclaimed after timeout; next command clean (pty preamble x0 or x1)`. The timed-out sleep may log ONE `PtyPool executor timeout` fallback; more than one (or a missing `RECOVERED`) means the dirty-pane tax is back (D16) — `[FAIL] pty probe`, **exit 3**, flag `PTY_RECOVERY_FAILED` |
| `l1` | docs-only note (8-turn cap) — negative control | `fa EXIT=0` + `[PASS] no escalation on a safe docs task`. Any `scope_expansion` here is a finding: `[FAIL] UNEXPECTED…`, **exit 3**, ledger flag `NEGATIVE_CONTROL_FAILED`. `[OBS] IntentGuard denials: N` is the ceremony cost (S12.6); `N>1` prints `[NOTE]` — friction to record, never a row failure |
| `l2` | shorten `_cmd_stats` in `src/fa/cli.py` (20 turns) | `[PASS] scope_expansion fired (N): 1>2;` + `[PASS] expansion evidence names present`. No escalation on a clean run = missed objective: `[FAIL] expected escalation never fired`, **exit 3**, flag `NO_ESCALATION_WHERE_EXPECTED` (near-miss telemetry present means the policy deliberately declined — S11 data, still exit 3) |
| `l3` | fix broken doc links, full cycle (40 turns) | same escalation signals as l2 (no escalation is NOT a failure here — the doc path is safe); IntentGuard making the model draft a PR intent first is the guardrail working, not a defect |
| `l4` | durable history + calibration | `rows visible: N` + a `this trial (cae-*): N row(s)` section; calibration buckets printed |
| `ledger` | — | the capture table, formatted |

Exit codes: `0` objective met · `1` run failure (`fa rc!=0` / no events) ·
`2` preflight/usage error · `3` run completed but the row objective was
missed (a finding — always flagged in the ledger `notes`).

Run ONE command at a time and review before the next. Each row prints
`RID=cae-<row>-<ts>-<pid>`, then after the run a **turn timeline**: one line
per active turn, headed by `[model latency]` — which chain model answered
that turn, how long the logical call took, and `failover xN` when N attempts
failed before success. Then tools per turn (turns delimited by model
responses — `[parallel xN]` when the model batched N tool calls in one turn),
`✗:IntentGuard` / `✗:LoopGuard` denials, `⤴` escalations, `near-miss`, and
`loop:` warnings — the tool-behaviour picture without reading the transcript.
Each turn's **full model text** is restored under the turn as an indented `💬`
block (S12.6c — the live console truncates model output to 200 chars; the
timeline does not): capped at 2000 chars per turn, `CAE_LLM_FULL=1` prints
the complete text.
A closing `summary:` line rolls up turns, wall time, tools, denials by guard,
escalations, near-misses, stop reason and tokens. An abnormal stop also
prints `[STOP] abnormal stop: <reason>` before the verdicts. For per-event ms
timing, prefix with `CAE_DETAIL=debug`. The ledger line (notes carry
`stop=<reason>`) and a copy of `events.jsonl` are captured automatically under
`worklogs/reviews/live-trial-data/`; full stdout stays at
`/tmp/cae_<run-id>.log` (unique per run — re-runs never clobber it).

## 5. Sign-off

1. `scripts/run_live_check.sh ledger` shows all rows with `exit_code=0` (or a
   recorded, explained failure).
2. Commit the evidence:

```bash
git add worklogs/reviews/live-trial-data && git commit -m "live: S10 verification ledger + events"
```

That commit = Part 2 complete. The ledger (`ledger.csv`: `run_id,date,row,
recommended_mode,level_path,expansion_n,observed_n,exhausted,exit_code,notes`
plus the captured `*.events.jsonl`) is the data feed for S11 constant closure
(ε, K, tier prefixes, caps).

## 6. Failure triage

| Signal | Meaning → action |
|---|---|
| `[FAIL] fa exited N` | the run itself failed (row exits `N`); printed verdicts are diagnostics only. Read `/tmp/cae_<run-id>.log` and `fa logs`. Re-run the row after fixing |
| `[STOP] abnormal stop: <reason>` | the engine stopped the run (`iteration_cap`, `chain_exhausted`, `context_budget_hard_stop`, `hook_deny:*`, …) — the reason is in the events and the ledger notes |
| row exits `3` | run completed but the row objective was missed (`NEGATIVE_CONTROL_FAILED` / `NO_ESCALATION_WHERE_EXPECTED` in ledger notes) — a finding to record, not a stack problem |
| `[FAIL] no events file` | session never started (stack/proxy/session problem). Run `setup` again; check `fa logs` |
| `[FAIL] interrupted` + ledger row `INTERRUPTED` | Ctrl-C mid-row; evidence was still captured. Re-run the row |
| `[NOTE] near-miss telemetry present (observed_n=N)` | escalation evidence existed but policy declined to escalate — this is S11 tuning data, not a failure |
| `[FAIL] env probe` (exit 3, `ENV_PROBE_FAILED`) | S12 readiness handoff broken: the agent could not run the venv pytest cleanly. Check the announcement reached the prompt (`grep readiness /tmp/cae_<run-id>.log`) and that the session clone has `.venv/bin/pytest`. P13 negative probe: with the venv removed this row MUST exit 3 — a pass there is the defect |
| `[FAIL] pty probe` (exit 3, `PTY_RECOVERY_FAILED`) | S12 pty reclaim broken: `RECOVERED` missing or >1 `PtyPool executor timeout` preambles. Read the log around the sleep; the C-c + sentinel path (pty_pool) should free the pane within ~5 s |
| `[NOTE] IntentGuard denials: N` on l1 | ceremony friction (draft flow not landing in ≤1 turn) — record it; to run rows without the ceremony set `intent_guard.mode: observe` (denials still logged as `would-deny(observe):`) |
| timeline shows `✗:LoopGuard` on repeated reads of one file | read truncation + path-thrash interplay (known finding D10) — note it, re-run with the file pre-read in one pass |
| `[BLOCK] <session>: …` at setup | a manifest that makes SessionManager refuse **every** new session (corrupt, non-`v1`, non-`active`, or workspace escaping `/sessions`). Quarantine the listed dir under `/srv/first-agent/state/sessions/`, re-run setup |
| `setup` dies on `fa probe failed` | stack/proxy/provider down — `fa status`, `fa logs`, fix before spending tokens |

Run ids are PID-unique and events are cleared pre-run, so a row can never be
scored against another row's events; a missing events file is always a FAIL,
never a silent PASS.

## 7. History (do not follow these)

- `S10-LIVE-VERIFICATION-rev3.md`: superseded; kept only as the evidence
  trail for the eight live-only defects that shaped this script. (An earlier
  rev2 sheet was removed from the tree at `48ef288`.)
- `scripts/run_live_expansion_trial.sh`: deprecated driver (git-worktree +
  temp state-root isolation) — kept in-tree for git history only.
- An early rev4 draft ran a host-local venv (`./.venv/bin/fa`) and copied
  `models.yaml`/`fa.env` into `~/.fa`: wrong anatomy — the container never
  reads host `~/.fa`, and keys belong only in the proxy. If such copies exist
  in the host home, delete them.
