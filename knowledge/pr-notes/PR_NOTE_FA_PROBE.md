# PR: `fa probe` + unified host CLI wrapper + chain_exhausted observability fix

## Intent: IMPLEMENT
## Invariant: Implements: `fa probe` provider liveness test, `scripts/fa` unified operator interface, chain_exhausted attempt logging

## Summary

### 1. `fa probe` — liveness test subcommand

Sends a minimal LLM request (`max_tokens: 1`, no system prompt, no tools)
through the full agent→proxy→provider chain path. Reports per-chain-entry
status, timing, and token count. ~10 tokens per probe.

```text
$ fa probe --role planner
fa probe: role=planner (model=glm-5p2, family=glm)
  chain[0] fireworks/glm-5p2       ✅ 200 (1847ms)
fa probe: OK (1847ms, in=8 out=1) reply="hello"
```

CLI: `fa probe [--role ROLE | --all-roles] [--config PATH] [--timeout N]`

Fills the gap between `fa selfcheck` (config validation, free, no API call)
and `fa run` (full inner loop, heavyweight). Operator workflow:
`selfcheck` → `probe` → `run`.

### 2. `scripts/fa` — unified host-side operator interface

Two layers behind one command:
- **Infrastructure verbs** (logs, proxy-logs, status, up, down, restart,
  rebuild, shell) run on the HOST via docker compose. Closed set.
- **Everything else** delegates to `fa` CLI inside the agent container.
  New Python subcommands work automatically — no wrapper change needed.

Symlink installed by `setup-fa-desktop.sh`, `fa-post-setup.sh`, and
`fa-update.sh`: `sudo ln -sf .../scripts/fa /usr/local/bin/fa`.

### 3. Observability fix — chain_exhausted attempt logging

`coder_loop.py` now logs `exc.attempts` as individual `provider_attempt`
rows when `ProviderChainExhaustedError` fires. Previously `events.jsonl`
showed only "all N chain entries failed" with no per-entry HTTP status,
error, or timing detail.

### 4. Deploy script integration

- `fa-update.sh`: chmod +x for `scripts/fa` (no .sh extension) + symlink
- `fa-post-setup.sh`: symlink installation + updated summary with wrapper commands
- `setup-fa-desktop.sh`: symlink installation after repo clone

## Files changed

| File | Change |
|------|--------|
| `src/fa/cli.py` | `probe` subparser + `_cmd_probe` + imports |
| `src/fa/inner_loop/coder_loop.py` | Log `exc.attempts` on chain_exhausted |
| `scripts/fa` | NEW — unified host wrapper (89 lines) |
| `scripts/fa-update.sh` | chmod + symlink for scripts/fa |
| `scripts/fa-post-setup.sh` | symlink install + updated summary |
| `scripts/setup-fa-desktop.sh` | symlink install |
| `tests/test_probe_cli.py` | NEW — 5 tests (fake transport) |
| `knowledge/instructions/02-operations.md` | probe docs, wrapper install, troubleshooting |
| `knowledge/llms.txt` | scripts/fa + test_probe_cli.py entries |
| `knowledge/BACKLOG.md` | I-26 (probe --all-entries), I-27 (fa help) |
| `knowledge/pr-notes/PR_NOTE_FA_PROBE.md` | This file |

## Tests

- 5 new tests in `test_probe_cli.py` (fake transport, no network)
- 132 existing related tests pass (cli, chain, selfcheck, coder_loop, deploy_scripts)

## Subtraction check

- **Removing what makes this redundant?** `selfcheck` validates config but
  not liveness. `fa run` tests liveness but is heavyweight. `scripts/fa`
  replaces ad-hoc `docker compose exec` typing.
- **What capability is lost if omitted?** Operator cannot diagnose "is the
  model/key/network alive?" without a full `fa run` turn.
- **OSS precedent?** Kubernetes has readinessProbe + livenessProbe. DDEV/Lando
  have CLI wrappers for docker exec. LangChain/Gortex have no probe equivalent.

## Deferred (BACKLOG)

- I-26: `fa probe --all-entries` — test every chain entry even after first success
- I-27: `fa help` — progressive disclosure / project-centric help
