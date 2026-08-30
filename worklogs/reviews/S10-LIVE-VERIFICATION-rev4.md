# Complexity-Aware Execution — live verification rev4 (slices S1–S10.9)

*Supersedes `S10-LIVE-VERIFICATION-rev3.md` (kept as evidence). Rev4 measures the
PRODUCTION mechanism exactly as documented in `worklogs/DEPLOYMENT-ANATOMY.md`:
host wrapper `fa` → `docker compose exec first-agent fa` → keys injected by
`fa-egress-proxy`. Rev3's eight live-only defects all came from machinery sitting
between the operator and the engine — rev4 removes every layer, including the
host-venv shortcut an earlier rev4 draft used.*

**Principles (each earned):**

1. **Production path only** — `./scripts/fa` (same file as `/usr/local/bin/fa`);
   config is the read-only bind of `/srv/first-agent/routing/models.yaml`; LLM keys
   exist **only inside the proxy** (ADR-12 Option C) and are never copied anywhere.
2. **Logic lives in committed scripts** — `scripts/run_live_check.sh`, pinned by
   `tests/test_live_check_script.py` and exercised end-to-end by
   `scripts/adversarial_battery_live_check.sh` (stub deployment: 16 checks + 6
   regression probes, no provider needed). One short command per row.
3. **Guarded oracles** — a missing `events.jsonl` is a FAIL, never a PASS; a nonzero
   `fa` exit is announced before any verdict; run ids are PID-unique and the events
   path is cleared pre-run, so no row can be scored against another row's events.
4. **Auto-ledger** — every row appends its CSV line + `events.jsonl` copy under
   `worklogs/reviews/live-trial-data/` (host side; rows themselves never touch the
   host checkout — they run in the container's session clone `/sessions/<id>`).

---

## §0 — prerequisites (nothing to copy)

- Stack healthy: `fa status` shows `first-agent` and `fa-egress-proxy` up.
- Run from the deployment checkout: `/srv/first-agent/repo/First-Agent-dev`
  (apply the rev4 patch there; base commit `8799d4e`. Host-side scripts only —
  no `fa update` / rebuild needed).
- **Security cleanup:** if an earlier rev4 draft left `~/.fa/.env` (real API keys)
  or a copied `~/.fa/models.yaml` in the host home, delete both — the deployment
  never reads them, and keys must not live outside the proxy.

## §1 — preflight

```bash
scripts/run_live_check.sh setup
```

Checks: wrapper + docker present, `chat:` role in the routing file, stack status,
**`fa probe` (proxy + providers — fails fast before tokens are spent)**,
routing-check (container view), history schema (fix6), stale-session scan
(report-only; production state is never swept), ledger initialized.

## §2 — rows (one command each; no git steps between rows)

```bash
scripts/run_live_check.sh l1        # docs-only negative control: expect 0 escalations
scripts/run_live_check.sh l2        # src/ task (session clone): expect scope_expansion
scripts/run_live_check.sh l3        # doc-defect full cycle, 40 turns (session clone)
scripts/run_live_check.sh l4        # durable history + calibration (container state)
scripts/run_live_check.sh ledger    # the S11 data feed, formatted
```

Each row prints its RID, the oracles, and captures automatically. l2/l3 edits
happen inside the per-session clone — the host checkout stays clean; there is
nothing to review-discard on the host. IntentGuard making the model draft a PR
intent before mutating is the guardrail working, not a trial defect.

## §3 — reading the results

| Signal | Meaning |
|---|---|
| l1 `[PASS] no escalation` | negative control holds: safe docs task stays chat_direct |
| l2/l3 `[PASS] scope_expansion fired` | evidence engine escalates on high-tier paths |
| `[NOTE] model finished in chat` | advice not taken — legitimate; record in ledger notes |
| `[OBS] K budget exhausted` | escalation budget spent → operator-report path |
| `[FAIL] fa exited N` | the run itself failed — verdicts below are diagnostics only |
| `expansion_observed` counts | near-miss telemetry feeding S11 constant tuning |
| l4 rows `cae-*` | trial rows inside durable history; calibration buckets updated |

**Sign-off:** commit `worklogs/reviews/live-trial-data/` (ledger + captured
events) = Part 2 complete; feeds S11 constant closure (ε, K, tier prefixes, caps).

## Deprecated by rev4 (do not use)

- `scripts/run_live_expansion_trial.sh` driver (worktree + temp state isolation).
- Rev3's manual capture blocks, dual-root L4, inline multiline row commands.
- The earlier rev4 draft's host-venv path (`./.venv/bin/fa`) and its §0
  `sudo cp` of `models.yaml`/`fa.env` into the host home — wrong anatomy: the
  container never reads host `~/.fa`, and keys belong only in the proxy.
