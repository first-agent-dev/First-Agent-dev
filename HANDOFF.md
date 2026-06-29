# HANDOFF.md — for the next agent / session

> **Read this first when starting a new session on this repository.**
> Canonical routing surface: [`knowledge/llms.txt`](./knowledge/llms.txt)
> §MUST READ FIRST. If the two disagree, llms.txt wins.

## 60-second bootstrap

1. Follow [`knowledge/llms.txt`](./knowledge/llms.txt) §MUST READ FIRST (5 files, in order).
2. Return here — read **§Current state**, then **§Next**.

## §Current state

Overwritten each session! Details live at the pointer, not here.

**As of:** 2026-06-25 — Workspace Isolation (ADR-13) implemented. The agent container now mounts the host git checkout as a read-only `/repo` and writable per-session clones inside `/sessions`. The entrypoint creates a `git clone --local` per session, completely isolating agent writes from the host worktree. `docker-compose.fa.yml` and `fa-entrypoint.sh` updated. `scripts/fa` host-wrapper handles dynamic execution paths. Tests verify clone creation, `fa` execution, and path invariants.

**As of:** 2026-06-22 — Live per-turn console output (branch
`live-output`): EventBus architecture emits OutputEvent at 8 call sites
in `drive_session` alongside existing EventLog writes. ConsoleRenderer
shows per-turn progress on stderr (model timing, tokens, cache hit ratio,
tool actions with agent-style verbs). 4 detail levels: minimal/standard/
verbose/debug. Respects NO_COLOR + TERM=dumb. QuietRenderer suppresses all
progress. CLI: `--output-mode`, `--detail`, `--no-color`. Foundation for
Phase 2 JsonLineWriter (WebUI NDJSON), config.yaml output section,
`fa replay`. 0 new runtime deps. 10 new tests + 66 related pass.
Prior: 2026-06-21 — deploy script fixes.

**As of:** 2026-06-20 — Hot tests with live api key concluded. Loop works,
agent writes to the file in workspace folder per session. Intested: does the
rest of the harness work as intended, does agent read the repo before execution?

**As of:** 2026-06-16 — API-key isolation hardened to an egress-injection proxy
([ADR-12](./knowledge/adr/ADR-12-secret-isolation.md), Option C in v0.1). A
blocking review found Option B leaked: `fs.run_bash` READ_ONLY commands bypassed
path-containment (could `cat /run/secrets/fa.env` + the deploy key) and the
model-facing channel was unredacted. **Boundary now:** LLM keys live ONLY in a
separate `fa-egress-proxy` container (`src/fa/egress_proxy/`, `fa egress-proxy`
CLI); the agent container holds no key in any file/env/memory and reaches
providers via the proxy (`FA_EGRESS_PROXY_URL`, base_url→`/route/<name>`, non-key
`X-FA-Proxy-Token`); the proxy strips caller auth + injects the real header.
Container separation is the boundary (works with agent as unprivileged `fa`, no
root). **Defense-in-depth + deploy key:** fail-closed bash-gate deny of secret-path
reads (`src/fa/sandbox/secret_paths.py`); single model-egress redaction chokepoint
(`coder_loop._redact`, raw/base64/hex/url/reversed); private `SecretStore`,
env-scrub, `SecretGuard` retained. Two-container `docker-compose.fa.yml`;
`setup-fa-desktop.sh` generates the proxy token; `fa-update.sh` hashes
keys+token+models (hash file moved to state dir). Proven by `test_egress_proxy.py`,
`test_proxy_wiring_cli.py`, `test_sandbox_secret_paths.py`,
`test_model_egress_redaction.py`, `test_secret_exfiltration.py`,
`test_secret_isolation_invariants.py`. Docs (`01-install`, `02-operations` §🔒,
DIGEST, llms.txt, exploration_log Q-18) updated. Residual + proxy egress allowlist
→ BACKLOG I-24. Prior: 2026-06-15 — docs IA restructure.

**As of:** 2026-06-15 (later) — Docs information-architecture restructure:
operator docs moved out of the cluttered repo root into a task-scoped home.
`DOCKER_USAGE_GUIDE.md` → `knowledge/instructions/02-operations.md`;
`knowledge/SETUP_AIO.md` → `knowledge/instructions/01-install.md`; new
`knowledge/instructions/README.md` is the human "start here" (linked from the
top of `README.md`). PR notes/bodies → `knowledge/pr-notes/` (+ index);
the timestamped inner-loop codemap → `knowledge/codemaps/`; `FINAL_DELIVERABLE.md`
pruned (unreferenced; superseded here + by the runtime PR note). De-overlap pass:
`01-install` owns the one-time bring-up, `02-operations` owns everything
recurring, SSH hardening single-sourced in `scripts/ssh-tailscale/README.md`.
Policy change: `knowledge/README.md` + `MAINTENANCE.md` now allow deliberate
pruning — the binding rule is **link integrity in the same PR**, not file
permanence; enforced by a new `markdown-link-check` pre-commit hook
(`.markdown-link-check.json`, local links only). All inbound refs re-pathed
(`llms.txt`, `ssh-tailscale/README.md`, code comments in `setup-fa-desktop.sh` +
`test_deploy_scripts.py`). Prior: 2026-06-15 — Docker deploy-script consolidation.

**As of:** 2026-06-15 — Docker deploy-script consolidation + Russian ops manual:
de-duplicated the host scripts without breaking the bootstrap contract.
`scripts/fa.service` template fixed to a valid systemd **user** unit (dropped the
invalid `Requires=docker.service`/`After=docker.service` — a user unit cannot
depend on a system unit; aligns the committed template with the 2026-06-10
decision and the unit actually installed). `setup-fa-desktop.sh` now installs
`fa.service` **and** `backup-fa.sh` from the cloned-repo copies (no inline
heredoc duplicates) — but stays **self-contained** (no sourced helper lib) so
`SETUP_AIO.md` Phase 4 Option B (download script alone to /tmp, it clones the
repo itself) still works. `DOCKER_USAGE_GUIDE.md` rewritten as a Russian operator
manual (install / auto+manual update / service admin / tasks / backup /
troubleshooting). Fixed a `.env.fa`-reload logic bug in the guide (`up -d
--force-recreate`, not `docker compose restart`). Fixed `SETUP_AIO.md` Phase 9
(credentials go in `secrets/backup.env`, not edited into the overwritten script).
Added `tests/test_deploy_scripts.py`: `bash -n` + `shellcheck` over all deploy
scripts + pins the self-contained-bootstrap + no-inline-duplicate + valid-user-
unit invariants. **All deploy scripts shellcheck-clean; 31 deploy/entrypoint/
update tests pass.** Prior: 2026-06-12 (later session) — Test-gaming hardening.

**As of:** 2026-06-12 (later session) — Test-gaming hardening (branch
`devin/2026-06-12-test-gaming-hardening`): closes guardrails-v2 deferred items R-6 +
R-7 + BACKLOG I-13. (A) Existing-test protection: `validate_test_edits` in
`pr_intent.py` (ADR-10 I-1: one function, two seats — git hook `_cli_validate` +
IntentGuard) — `D`/`R`/`C` on `tests/**.py` blocked under every intent, `M` under
FIX-shaped diffs needs a `TEST-EDITS: <path> — <reason>` draft declaration; keyed on
CLASSIFIER intent (typed D-5 override can NOT disarm — security invariant pinned by
test). Skill §Test-edit declaration + snapshot-test pin. (B) Mutation testing
resurrected: weekly `tests.yml` had been dead since adoption (mutmut-2.x CLI flag
removed in 3.x, error swallowed by `|| true`); config → 3.x keys
(`source_paths`/`pytest_add_cli_args_test_selection`), workflow emits stats to job
summary + artifact, `mutants/` excluded everywhere, `just mutation` recipe. First
honest baseline **633 mutants / 470 killed / 163 survived** →
`knowledge/mutation-survivors-workplan.md` (delete-on-completion flips workflow to
blocking; BACKLOG I-23). (C) I-13 closed: V4 alias-map (`from pytest import skip`,
`import pytest as pt`, renamed imports, bare `mark.<X>`) with shadowing negative;
TCB-path edit (`authoring_rules/tests.py`) — protected-path flag on PR is expected.
**1108 tests, 90.43 % cov, all gates green.** Prior: 2026-06-12 — CI guardrails v2.

**As of:** 2026-06-12 — CI guardrails v2 (failure-mode hardening): ruff gains `S`
(security floor, src-blocking, tests exempt), `BLE` (blind-except), `C90`
(complexity ratchet, max 15, 4 baseline waivers), `PGH` (blanket-suppression
guard); pylint narrowed to gap-checks only (`duplicate-code` + `cyclic-import`,
explicit `fail-on`, binary gate) — `pylint.yml` workflow + `.pylintrc-tests`
deleted, pylint runs inside `just lint`; coverage flags moved from pytest
`addopts` to `just test` (bare `pytest` is gate-free for iteration);
`just fix` = `--fix-only` → `format` → `check` (format always runs);
`check_protected_paths.py` adds two non-blocking annotation tiers: dependency
manifests (slopsquatting review) and newly-added suppression markers
(waiver audit). 26 inline waivers (rationale-above + short `noqa`) document
every intentional S/BLE/C901 site. Research note:
[`llm-agent-failure-modes-guardrails-2026-06.md`](./knowledge/research/llm-agent-failure-modes-guardrails-2026-06.md)
(6 TAKEN / 2 DEFER — read-only `tests/**` sandbox policy and mutmut survivor
budget are the named next guardrails). **1083 tests, 90.42 % cov, mypy strict
(137 files), ruff/pylint/deptry/authoring-check clean, vulture wired
(`just deadcode`).** Prior: 2026-06-11 — Loop foundation + Docker untangling.

**As of:** 2026-06-11 — Loop foundation + Docker untangling (branch `untangling-fix`):
Docker conflict markers resolved; `scripts/fa-entrypoint.sh` is stand-by by default and
auto-runs only with explicit `FA_AUTO_RUN=1`; `scripts/fa.service` restores
`Requires=docker.service`. Loop foundation landed: cache-aware `ResponseInfo` fields,
per-turn `usage` rows, terminal `session_summary` with `cache_hit_ratio`, debug
`_assert_tool_pairing_invariant()` before provider calls, canonical sorted tool
serialization, `ToolSpec.max_context_bytes` / `elide`, `ArtifactStore`, and
`project_for_model()` as the sole provider-visible tool-result projection. Full
successful `ToolResult.result` payloads now enter `events.jsonl`; model context receives

budgeted projections. Added host-side `scripts/fa-update.sh` for AIO update/deploy with
review fixes (tracks `Dockerfile.fa`, ignores commented optional `FA_*` env rows, tests via
`uv run` in `/workspace`). Remaining plan is tracked in
`knowledge/loop-improvement-workplan.md`. Validation in sandbox:
`PYTHONPATH=src pytest -q -o addopts=''` → 1078 passed; ruff/mypy clean for touched Python files.


**As of:** 2026-06-08 — ADR-11 **PR-10 follow-up PR-11 landed** (merge `c1d046a`, PR #11): V2/V11/V4 rule-correctness pass + PR-12 scope-prep. V2 `_extract_all` rewritten around an `_UNPROVABLE` sentinel (closes pass-1 BLOCKER-1/2/3); `_public_symbols` now returns defining `ast.stmt` nodes with per-node `node_input_hash` (HIGH-1, P2-HIGH-C); V11 self-contradiction split into a distinct `FA-AUTHORING-V11-CONTRADICTORY-ASSERT` code (HIGH-4); V4 exempts module-scope `pytest.skip(..., allow_module_level=True)` (HIGH-5); `_iter_decorated`→`_all_decorators` (MEDIUM-2); `SRC_SCOPE`/`TEST_SCOPE` hoisted into `_scan.py` (PR-12 prep); BACKLOG I-20/I-21/I-12-bis filed. **995 tests, 91.28 % cov, mypy strict (74 src files), ruff + pylint clean, `fa authoring-check` 0 diagnostics.** `RULE_ALLOWLIST` unchanged (3 callables). Next: PR-12 (kernel audit/corpus/advisory) then PR-13 (V4 evasion closure). Prior: 2026-06-06 — ADR-11 PR-2 landed (Level-1 rule packs); 2026-06-04 — CI/QA tooling hardening (R-1..R-6, R-15; local-first `just check`, advisory CI except sanity-check/audit/gitleaks; `uv.lock` deferred).

**As of:** 2026-06-09 — Secrets Hardening PR (branch `agent/secrets-hardening`, residual fixes landed): Container integration, runtime redaction (`SecretRedactor` with base64/URL encoding detection + `SecretRedactorError` typed exception), `EventLog` redaction, `LearningObserver` redaction, `SecretGuard` v0.3 (base64/URL/interpolation detection), `~/.fa/.env` loader with specific exception handling (`_load_fa_dotenv`), deployment docs (Secrets Management subsection in SETUP_AIO.md + README), repo hygiene (expanded `.gitleaks.toml` allowlist + policy comments). **32 total tests** (18 redaction + 10 SecretGuard + 4 loader), all passing. ruff clean. All review warnings addressed: encoding bypass closed, typed error on empty secrets, graceful loader degradation, expanded test coverage.

**As of:** 2026-06-08 — Linux deployment suite v2 landed: cross-reference-verified against three independent LLM research passes. Major changes from v1: removed Portainer/TLP/auto-login, conservative pruning (mask tracker, don't purge), Docker from docker.com apt repo with version pin, power-profiles-daemon in power-saver, UFW binds SSH to tailscale0 only, restic → B2 S3-compatible endpoint, weekly docker prune cron, systemd user service, `GIT_SSH_COMMAND` with `IdentitiesOnly=yes`, GitHub Ed25519 host key pinned in known_hosts, branch protection on `main`, pids_limit: 512. Added: `scripts/fa.service`, `scripts/backup-fa.sh`, `knowledge/SETUP_AIO.md` (step-by-step bootstrap).
**As of:** 2026-06-11 — Multi-role workflow with PR Draft as Work Log (branch `agent/2026-06-11-multi-role-worklog`): Role-aware system prompts (`prompt.py`: planner/coder/eval); role-specific registries (`tools/__init__.py`: planner/eval read-only, coder full baseline); `--resume` flag on `fa run` preserves draft file across sessions; `drive_session()` passes `role` to `build_system_message()`. PR Draft (`pr_draft.md`) repurposed as living work log — planner writes plan, coder updates progress, eval appends verification. `scripts/fa-entrypoint.sh` fixes restart loop (child process, not exec). **Ready for multi-role orchestration smoke test.** Prior: 2026-06-10 — AIO deployment bootstrap follow-up (container healthy, `fa.service` active, git push verified).

### Landmarks (what landed)

| What | Date | Pointer |
| :--- | :--- | :--- |
| **Loop foundation + Docker untangling**: resolved Docker merge-conflict markers, explicit `FA_AUTO_RUN` entrypoint semantics preserved, `fa.service` Docker dependency restored, host update helper added; loop foundation adds cache-aware usage/session summaries, pairing invariant before provider calls, canonical tool serialization, budgeted `project_for_model()` projection, artifact store, and full tool-result audit payloads. Remaining phases tracked in workplan. | 2026-06-11 | [`coder_loop.py`](./src/fa/inner_loop/coder_loop.py), [`projection.py`](./src/fa/inner_loop/projection.py), [`artifacts.py`](./src/fa/inner_loop/artifacts.py), [`fa-update.sh`](./scripts/fa-update.sh), [`loop-improvement-workplan.md`](./knowledge/loop-improvement-workplan.md), [`PR_NOTE_LOOP_FOUNDATION.md`](./knowledge/pr-notes/PR_NOTE_LOOP_FOUNDATION.md) |
| **AIO deployment bootstrap follow-up** (branch `agent/2026-06-10-ssh-and-service-fixes`): Host `~/.ssh/config` auto-creation (append-only, fork-safe), `fa.service` removes `Requires=docker.service` system-unit dependency, `SETUP_AIO.md` Phase 6b SSH troubleshooting + clone URL fix + `fa-post-setup.sh` mention, `ssh-keygen -F` for known_hosts duplicate detection. **AIO operational: container healthy, service active, git push verified.** | 2026-06-10 | [`setup-fa-desktop.sh`](./scripts/setup-fa-desktop.sh), [`SETUP_AIO.md`](./knowledge/instructions/01-install.md) |
| **AIO live-deployment blocker fix** (branch `agent/2026-06-10-aio-live-deploy-fixes`, PR #15 merged): Compose schema v3 `pids` placement, Dockerfile UID-1000 collision + Python tmpfs visibility, setup script service enablement (`fail2ban`/`unattended-upgrades`), post-setup Tailscale check + fork-safe SSH URL + `systemctl --user` D-Bus fallback. | 2026-06-10 | [`docker-compose.fa.yml`](./docker-compose.fa.yml), [`Dockerfile.fa`](./Dockerfile.fa), [`setup-fa-desktop.sh`](./scripts/setup-fa-desktop.sh), [`fa-post-setup.sh`](./scripts/fa-post-setup.sh) |
| **Secrets Hardening PR** (branch `agent/secrets-hardening`): Container integration, runtime redaction (`SecretRedactor` + tests), agent self-protection (`SecretGuard`), deployment docs (`SETUP_AIO.md` Phase 7b), repo hygiene (`.gitignore`, `.dockerignore`, `.gitleaks.toml`). **1002 tests, ruff clean.** | 2026-06-08 | [`redaction.py`](./src/fa/observability/redaction.py), [`test_observability_redaction.py`](./tests/test_observability_redaction.py), [`SETUP_AIO.md`](./knowledge/instructions/01-install.md), [`docker-compose.fa.yml`](./docker-compose.fa.yml), [`setup-fa-desktop.sh`](./scripts/setup-fa-desktop.sh) |
| **ADR-11 PR-10 follow-up PR-11 landed** (PR #11, merge `c1d046a`): V2/V11/V4 correctness — `_extract_all` `_UNPROVABLE` opt-out, `_public_symbols` defining-node + per-node hash, V11 `CONTRADICTORY-ASSERT` split, V4 `allow_module_level=True` exemption, `_iter_decorated`→`_all_decorators`, `SRC_SCOPE`/`TEST_SCOPE` hoist; BACKLOG I-20/I-21/I-12-bis. **995 tests, 91.28 % cov.** | 2026-06-08 | [`exports.py`](./src/fa/authoring_rules/exports.py), [`tests.py`](./src/fa/authoring_rules/tests.py), [`_scan.py`](./src/fa/authoring_rules/_scan.py) |
| **Linux deployment suite v2 (cross-reference verified)**: Three-source consensus across 7 decision domains. Removed Portainer/TLP/auto-login. Conservative pruning (mask, don't purge tracker/evolution). Docker from docker.com apt repo. power-profiles-daemon. UFW → tailscale0 only. restic → B2 S3 endpoint. `GIT_SSH_COMMAND` + `IdentitiesOnly=yes` + pinned GitHub Ed25519 host key. Branch protection on `main`. pids_limit: 512. Added `knowledge/SETUP_AIO.md` bootstrap guide, `scripts/fa.service`, `scripts/backup-fa.sh`. | 2026-06-08 | [`First-Agent-ops-cross-reference.md`](./knowledge/research/First-Agent-ops-cross-reference.md), [`homelab-deployment-24-7-2026-06.md`](./knowledge/research/homelab-deployment-24-7-2026-06.md), [`SETUP_AIO.md`](./knowledge/instructions/01-install.md), [`setup-fa-desktop.sh`](./scripts/setup-fa-desktop.sh), [`fa.service`](./scripts/fa.service), [`backup-fa.sh`](./scripts/backup-fa.sh), [`docker-compose.fa.yml`](./docker-compose.fa.yml), [`Dockerfile.fa`](./Dockerfile.fa) |
| **ADR-11 PR-2 landed**: Level-1 rule packs `exports.py` (V2 `__all__` completeness, F-2/F-7) and `tests.py` (V4 `pytest.skip` / non-strict-xfail / focus markers; V11 placeholder-asserts, F-9) with `_scan.py` shared helper. All HARD-BLOCK. `RULE_ALLOWLIST` is now 3 callables (was empty in PR 1). One F-7-class real bug fixed in same PR: `TimeSource` Callable alias added to `src/fa/inner_loop/hooks/blockers.py.__all__`. **974 tests, 91.05 % cov, pylint 10.00/10, mypy strict on 127 files.** | 2026-06-06 | [`exports.py`](./src/fa/authoring_rules/exports.py), [`tests.py`](./src/fa/authoring_rules/tests.py), [`_scan.py`](./src/fa/authoring_rules/_scan.py) |
| ADR-11 (Authoring Guardrails) landed (doc-only ADR-RULE): two-tier TCB (frozen stdlib Level-0 kernel + allowlisted Level-1 rules), `ADR-11-I1..I8` invariant slate, active-consumer table, enforcement-ceiling. SSOT = merged blueprint (R-1..R-18). Code ships across PR 1..PR 5. **Amended same-day (contract freeze):** §Verification (catch/fp corpora + `F-1..F-10`), pinned `FA-AUTHORING-V<N>` code namespace, single `.fa/session.toml`, `rule_input_hash` source, `fail_under=90`/strict-`pylint` gate note. | 2026-06-01 | [`ADR-11`](./knowledge/adr/ADR-11-authoring-guardrails.md), [blueprint](./knowledge/research/ADR-11-Authoring-Guardrails-Blueprint.md), [`exploration_log.md` Q-16 + amendment](./knowledge/trace/exploration_log.md) |
| Draft-first hardening (PR #24 follow-up): AST `fs.run_bash` analyzer + trusted session draft store; `IntentGuard` now gates shell writes (REPO_WRITE / INDEX_WRITE / OPAQUE_EXEC) and rejects stale / externally-fabricated drafts. | 2026-05-29 | [`bash_intent.py`](./src/fa/inner_loop/bash_intent.py), [`pr_draft.py`](./src/fa/inner_loop/pr_draft.py), [`intent_guard.py`](./src/fa/inner_loop/hooks/intent_guard.py) |
| PR E landed (M-7 §Q-N): `src/fa/inner_loop/tools/prepare_pr.py` (`pr.prepare`) + registry wiring in `_cmd_run`; closes the producer gap so `IntentGuard` bites on every mutating tool call. IntentGuard now wired into `fa run` bootstrap. | 2026-05-28 | [`prepare_pr.py`](./src/fa/inner_loop/tools/prepare_pr.py), [`tools/__init__.py`](./src/fa/inner_loop/tools/__init__.py), [`cli.py`](./src/fa/cli.py) |
| PR D landed: `src/fa/inner_loop/coder_loop.py` (`drive_session`) + `prompt.py` + `fa run --task` CLI + `UrllibTransport`; bridges `ProviderChain` and `run_session` so the harness is finally LLM-drivable (closes M-8). | 2026-05-28 | [`coder_loop.py`](./src/fa/inner_loop/coder_loop.py), [`prompt.py`](./src/fa/inner_loop/prompt.py), [`cli.py`](./src/fa/cli.py), [`transport.py`](./src/fa/providers/transport.py) |
| Bug-fix pass on PR B + PR C: `IntentGuard` re-export + `SQUASH_MSG` skip + `edit_file`/`apply_patch` mutating recognition + path normalisation + shared `parse_field` dedup + stale `Blocked-on` text fix. | 2026-05-28 | [`pr_intent.py`](./src/fa/hygiene/pr_intent.py), [`intent_guard.py`](./src/fa/inner_loop/hooks/intent_guard.py), [`tests/test_intent_guard.py`](./tests/test_intent_guard.py), [`tests/test_pr_intent_snapshot.py`](./tests/test_pr_intent_snapshot.py) |
| PR C landed: `IntentGuard(GuardMiddleware)` on `BEFORE_TOOL_EXEC` reuses M-6's classifier + validator; closes M-7 (ADR-10 I-1: one validator, two consumers) | 2026-05-27 | [`intent_guard.py`](./src/fa/inner_loop/hooks/intent_guard.py), [`tests/test_intent_guard.py`](./tests/test_intent_guard.py) |
| PR B landed: `src/fa/hygiene/pr_intent.py` classifier + `prepare-commit-msg` / `commit-msg` hooks; snapshot test pins hook constants to skill §Output format (closes M-6) | 2026-05-27 | [`pr_intent.py`](./src/fa/hygiene/pr_intent.py), [`hooks/`](./src/fa/hygiene/hooks/), [`tests/test_pr_intent_snapshot.py`](./tests/test_pr_intent_snapshot.py) |

**Trade-off Noted:** Per-run artifacts (events.jsonl, pr_draft.md, attempt_history.json) now live under the persistent host root `~/.fa/session-log/<run_id>/`, not in the ephemeral per-session workspace clone (ADR-13 prunes those). `fa stats` therefore discovers sessions globally under `~/.fa/session-log/`; the `--workspace` flag now only scopes the dead-zone (`src/` reachability) scan, not session discovery. Cross-session aggregation roll-up is still pending (Next #3).

### Gotchas (delete when resolved)

| Gotcha | Pointer |
| :--- | :--- |
| ADR-11 PR-2 V2 rule scopes to `src/` only; V4/V11 to `tests/` only. `scripts/` and `verifiers/` are NOT authoring-guarded yet — small surface today, but a TCB-write regression in `scripts/check_protected_paths.py` would slip past `fa authoring-check`. | [`BACKLOG I-12`](./knowledge/BACKLOG.md#i-12--authoring-rules-scope-coverage-gap-scripts-verifiers) |
| ADR-11 PR-2 V4 rule is bound to the literal `pytest.skip` / `pytest.mark.skip` attribute chain; `from pytest import skip; skip(...)` slips past it. Decorator form unaffected. **Scheduled to close in PR-13** (PR-10 follow-up, `pr13-v4-evasion-closure`). | [`BACKLOG I-13`](./knowledge/BACKLOG.md#i-13--v4-import-alias-bypass-from-pytest-import-skip) |
| **PR-12 commit 9 of the PR-10 plan appends a NEW `I-14` (per-file decode caching), but `BACKLOG.md` already has a distinct `## I-14 — ADR-11 PR-3+ rule packs`.** Next agent MUST STOP at commit 9, classify as `plan-transcription error`, and renumber the new entries with the user before writing. | [`BACKLOG I-14`](./knowledge/BACKLOG.md) |
| ≈26 files cite «AGENTS.md PR Checklist rule #N» — orphan refs from PR A' skill extraction; top-10 priority list in pointer | [`exploration_log.md` Q-15](./knowledge/trace/exploration_log.md) |
| Streaming chain semantics = v0.2 redesign, not v0.1 amendment | [`exploration_log.md` Q-13](./knowledge/trace/exploration_log.md) |

### Backlog (active milestones only)

| Slot | Scope | Status |
| :--- | :--- | :--- |
| _(none in flight)_ | M-1..M-8 landed; AIO deployment operational. Next: open SSH/service follow-up PR (§Next #1). | — |

## §Next

Priority-ordered. Completed items deleted, not struck through.

1. **First real `fa run --task` smoke against OpenRouter / Fireworks.**
   The driver shipped in PR D + the `pr.prepare` producer landing
   in PR E together close the contract loop, but adapter
   response-shape coverage stays theoretical until this runs
   end-to-end against a live provider. Yellow→green conversion
   item; provider-specific adapter fixes likely (e.g., a vendor
   that returns `tool_calls` under a non-canonical key).
2. **Cross-session aggregation of `attempt_history.json` (R-10 /
   R-12).** Per-run history is already written under
   `~/.fa/session-log/<run_id>/`; the missing piece is the
   roll-up surface that Pillar-3 measurement depends on (lessons
   moving across sessions instead of being re-discovered).
3. **Orphan cross-ref sweep — ≈26 files** from PR A' extraction.
   Top-10: `llms.txt` (9), `MAINTENANCE.md` (7), `ADR-10` (6),
   `DIGEST.md` (4), `ADR-7` (4). Retarget «AGENTS.md PR Checklist
   rule #N» → [`pr-creation/SKILL.md` §PR Checklist](./knowledge/skills/pr-creation/SKILL.md).
4. **ADR-10 follow-ups** — I-5 FA-surface audit; A28 «LLM emits a
   number» audit; `[CODE]` namespace + A23 lint.
5. **ADR-11 rollout PR 3 — parity + docs rules.** PR-2 landed
   2026-06-06 (V2 exports / V4 test-decay / V11 placeholder-asserts).
   Next: `src/fa/authoring_rules/parity.py` (V3 — `SQUASH_MSG`
   Python↔Bash drift, F-3) + `src/fa/authoring_rules/docs.py` (V5 —
   stale BACKLOG / missing `llms.txt` row, F-5/F-6). Then PR 4
   (`seam.py` V6 + `catch-corpus/` + `fp-corpus/` consumers) →
   PR 5 (`messages.py` V12 + advisory tuning). V10 stays deferred
   indefinitely per [`I-14`](./knowledge/BACKLOG.md#i-14--adr-11-pr-3-rule-packs-v3-v5-v7-v10-v12-v14).
6. **Authoring-rules scope coverage** ([`I-12`](./knowledge/BACKLOG.md#i-12--authoring-rules-scope-coverage-gap-scripts-verifiers)).
   PR-2 V2 scopes only to `src/`; V4/V11 to `tests/`. Extend to
   `scripts/` and `verifiers/` once either tree grows beyond its
   current single-file footprint, OR a V2-class regression is
   detected manually there.
7. **V4 import-alias bypass** ([`I-13`](./knowledge/BACKLOG.md#i-13--v4-import-alias-bypass-from-pytest-import-skip)).
   `from pytest import skip; skip(...)` slips past `TEST_SEMANTIC_DECAY`
   today. Half-day fix (add an `ast` import-walker); land when an
   `fp-corpus` measurement (PR-4) shows a real bypass, or sooner if
   bandwidth allows.

## Session Protocol

**Rules for updating this file.** Apply at session close.

1. **§Current state is overwritten.** Replace tables with current
   truth. Delete resolved gotchas. Delete landed backlog rows.
   Sync remaining backlog rows with `BACKLOG.md`.
2. **§Next is rewritten.** Completed items deleted. New priorities
   inserted at correct rank. Sources: `BACKLOG.md` + session work.
3. **Landmarks capped at 10 rows.** When adding a row would exceed
   10 drop the oldest. Dropped content is already canonical in
   `DIGEST.md` + `exploration_log.md` + `git log`.
4. **Update the `As of:` line** with current date and commit hash
   or session ID.
5. **Hard cap: <200 lines.** Over cap → drop Landmarks rows first,
   then compress Gotcha descriptions. KEEP §Next items.
