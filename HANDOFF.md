# HANDOFF.md — for the next agent / session

> **Read this first when starting a new session on this repository.**
> Canonical routing surface: [`knowledge/llms.txt`](./knowledge/llms.txt)
> §MUST READ FIRST. If the two disagree, llms.txt wins.

## 60-second bootstrap

1. Follow [`knowledge/llms.txt`](./knowledge/llms.txt) §MUST READ FIRST (5 files, in order).
2. Return here — read **§Current state**, then **§Next**.

## § Current state

Overwritten each session! Details live at the pointer, not here.

**As of:** 2026-06-01 — ADR-11 (Authoring Guardrails) landed as a doc-only ADR-RULE decision (two-tier TCB, `ADR-11-I1..I8`); code rollout PR 1..PR 5 pending. Prior: M-6/M-7/M-8 landed; PR-intent enforcement loop closed.

### Landmarks (what landed)

| What | Date | Pointer |
| :--- | :--- | :--- |
| ADR-11 (Authoring Guardrails) landed (doc-only ADR-RULE): two-tier TCB (frozen stdlib Level-0 kernel + allowlisted Level-1 rules), `ADR-11-I1..I8` invariant slate, active-consumer table, enforcement-ceiling. SSOT = merged blueprint (R-1..R-18). Code ships across PR 1..PR 5. | 2026-06-01 | [`ADR-11`](./knowledge/adr/ADR-11-authoring-guardrails.md), [blueprint](./knowledge/research/ADR-11-Authoring-Guardrails-Blueprint.md), [`exploration_log.md` Q-16](./knowledge/trace/exploration_log.md) |
| Draft-first hardening (PR #24 follow-up): AST `fs.run_bash` analyzer + trusted session draft store; `IntentGuard` now gates shell writes (REPO_WRITE / INDEX_WRITE / OPAQUE_EXEC) and rejects stale / externally-fabricated drafts. | 2026-05-29 | [`bash_intent.py`](./src/fa/inner_loop/bash_intent.py), [`pr_draft.py`](./src/fa/inner_loop/pr_draft.py), [`intent_guard.py`](./src/fa/inner_loop/hooks/intent_guard.py) |
| PR E landed (M-7 §Q-N): `src/fa/inner_loop/tools/prepare_pr.py` (`pr.prepare`) + registry wiring in `_cmd_run`; closes the producer gap so `IntentGuard` bites on every mutating tool call. IntentGuard now wired into `fa run` bootstrap. | 2026-05-28 | [`prepare_pr.py`](./src/fa/inner_loop/tools/prepare_pr.py), [`tools/__init__.py`](./src/fa/inner_loop/tools/__init__.py), [`cli.py`](./src/fa/cli.py) |
| PR D landed: `src/fa/inner_loop/coder_loop.py` (`drive_session`) + `prompt.py` + `fa run --task` CLI + `UrllibTransport`; bridges `ProviderChain` and `run_session` so the harness is finally LLM-drivable (closes M-8). | 2026-05-28 | [`coder_loop.py`](./src/fa/inner_loop/coder_loop.py), [`prompt.py`](./src/fa/inner_loop/prompt.py), [`cli.py`](./src/fa/cli.py), [`transport.py`](./src/fa/providers/transport.py) |
| Bug-fix pass on PR B + PR C: `IntentGuard` re-export + `SQUASH_MSG` skip + `edit_file`/`apply_patch` mutating recognition + path normalisation + shared `parse_field` dedup + stale `Blocked-on` text fix. | 2026-05-28 | [`pr_intent.py`](./src/fa/hygiene/pr_intent.py), [`intent_guard.py`](./src/fa/inner_loop/hooks/intent_guard.py), [`tests/test_intent_guard.py`](./tests/test_intent_guard.py), [`tests/test_pr_intent_snapshot.py`](./tests/test_pr_intent_snapshot.py) |
| PR C landed: `IntentGuard(GuardMiddleware)` on `BEFORE_TOOL_EXEC` reuses M-6's classifier + validator; closes M-7 (ADR-10 I-1: one validator, two consumers) | 2026-05-27 | [`intent_guard.py`](./src/fa/inner_loop/hooks/intent_guard.py), [`tests/test_intent_guard.py`](./tests/test_intent_guard.py) |
| PR B landed: `src/fa/hygiene/pr_intent.py` classifier + `prepare-commit-msg` / `commit-msg` hooks; snapshot test pins hook constants to skill §Output format (closes M-6) | 2026-05-27 | [`pr_intent.py`](./src/fa/hygiene/pr_intent.py), [`hooks/`](./src/fa/hygiene/hooks/), [`tests/test_pr_intent_snapshot.py`](./tests/test_pr_intent_snapshot.py) |
| PR A' landed: full PR-creation rulebook → loadable skill; AGENTS.md | 2026-05-26 | [`pr-creation/SKILL.md`](./knowledge/skills/pr-creation/SKILL.md) |
| `knowledge/skills/` directory established; `repo-audit` migrated (closes I-9b) | 2026-05-26 | [`skills/README.md`](./knowledge/skills/README.md) |
| PR A: §PR Intent Classification (5 Level-1 intents) + anti-shallow-fix gate | 2026-05-25 | [`AGENTS.md` §Loadable skills](./AGENTS.md#loadable-skills) |

### Gotchas (delete when resolved)

| Gotcha | Pointer |
| :--- | :--- |
| ≈26 files cite «AGENTS.md PR Checklist rule #N» — orphan refs from PR A' skill extraction; top-10 priority list in pointer | [`exploration_log.md` Q-15](./knowledge/trace/exploration_log.md) |
| Streaming chain semantics = v0.2 redesign, not v0.1 amendment | [`exploration_log.md` Q-13](./knowledge/trace/exploration_log.md) |

### Backlog (active milestones only)

| Slot | Scope | Status |
| :--- | :--- | :--- |
| _(none in flight)_ | M-1..M-8 landed; next work is the live `fa run` smoke (§Next #1) | — |

## § Next

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
   `<workspace>/.fa/runs/<run_id>/`; the missing piece is the
   roll-up surface that Pillar-3 measurement depends on (lessons
   moving across sessions instead of being re-discovered).
3. **Orphan cross-ref sweep — ≈26 files** from PR A' extraction.
   Top-10: `llms.txt` (9), `MAINTENANCE.md` (7), `ADR-10` (6),
   `DIGEST.md` (4), `ADR-7` (4). Retarget «AGENTS.md PR Checklist
   rule #N» → [`pr-creation/SKILL.md` §PR Checklist](./knowledge/skills/pr-creation/SKILL.md).
4. **ADR-10 follow-ups** — I-5 FA-surface audit; A28 «LLM emits a
   number» audit; `[CODE]` namespace + A23 lint.
5. **ADR-11 rollout PR 1 — Level-0 TCB skeleton + protected-path
   governance** (`src/fa/authoring_tcb.py`, `src/fa/authoring_rules/__init__.py`,
   `scripts/check_protected_paths.py`, `.github/workflows/authoring-guardrails.yml`,
   `.github/CODEOWNERS`). Implements R-1/R-11/R-2/R-6/R-7/R-10/R-12/R-15
   per [ADR-11](./knowledge/adr/ADR-11-authoring-guardrails.md) + blueprint
   Appendix B. PR 2..PR 5 follow (teeth → parity/docs → seam/corpora →
   advisory tuning).

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
5. **Hard cap: ≤150 lines.** Over cap → drop Landmarks rows first,
   then compress Gotcha descriptions. KEEP §Next items.
