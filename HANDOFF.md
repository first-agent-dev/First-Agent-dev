# HANDOFF.md — for the next agent / session

> **Read this first when starting a new session on this repository.**
> Canonical routing surface: [`knowledge/llms.txt`](./knowledge/llms.txt)
> §MUST READ FIRST. If the two disagree, llms.txt wins.

## 60-second bootstrap

1. Follow [`knowledge/llms.txt`](./knowledge/llms.txt) §MUST READ FIRST (5 files, in order).
2. Return here — read **§Current state**, then **§Next**.

## § Current state

Overwritten each session! Details live at the pointer, not here.

**As of:** 2026-05-28 — PR B+C bug-fix pass (review-driven fixes)

### Landmarks (what landed)

| What | Date | Pointer |
| :--- | :--- | :--- |
| Bug-fix pass on PR B + PR C: `IntentGuard` re-export + `SQUASH_MSG` skip + `edit_file`/`apply_patch` mutating recognition + path normalisation + shared `parse_field` dedup + stale `Blocked-on` text fix. | 2026-05-28 | [`src/fa/hygiene/pr_intent.py`](./src/fa/hygiene/pr_intent.py), [`src/fa/inner_loop/hooks/intent_guard.py`](./src/fa/inner_loop/hooks/intent_guard.py), [`tests/test_intent_guard.py`](./tests/test_intent_guard.py), [`tests/test_pr_intent_snapshot.py`](./tests/test_pr_intent_snapshot.py) |
| PR C landed: `IntentGuard(GuardMiddleware)` on `BEFORE_TOOL_EXEC` reuses M-6's classifier + validator; closes M-7 (ADR-10 I-1: one validator, two consumers) | 2026-05-27 | [`intent_guard.py`](./src/fa/inner_loop/hooks/intent_guard.py), [`tests/test_intent_guard.py`](./tests/test_intent_guard.py) |
| PR B landed: `src/fa/hygiene/pr_intent.py` classifier + `prepare-commit-msg` / `commit-msg` hooks; snapshot test pins hook constants to skill §Output format (closes M-6) | 2026-05-27 | [`pr_intent.py`](./src/fa/hygiene/pr_intent.py), [`hooks/`](./src/fa/hygiene/hooks/), [`tests/test_pr_intent_snapshot.py`](./tests/test_pr_intent_snapshot.py) |
| PR A' landed: full PR-creation rulebook → loadable skill; AGENTS.md | 2026-05-26 | [`pr-creation/SKILL.md`](./knowledge/skills/pr-creation/SKILL.md) |
| `knowledge/skills/` directory established; `repo-audit` migrated (closes I-9b) | 2026-05-26 | [`skills/README.md`](./knowledge/skills/README.md) |
| PR C promoted to formal BACKLOG row M-7 (M-6 now closed) | 2026-05-26 | [`BACKLOG.md` §M-7](./knowledge/BACKLOG.md) |
| PR A: §PR Intent Classification (5 Level-1 intents) + anti-shallow-fix gate | 2026-05-25 | [`AGENTS.md` §Loadable skills](./AGENTS.md#loadable-skills) |
| ADR-10 proposed — deterministic-harness invariants I-1..I-5 | 2026-05-25 | [`ADR-10`](./knowledge/adr/ADR-10-deterministic-harness-invariants.md) |
| ABC synthesis deep-dive — 9-repo determinism patterns (ADR-10 input) | 2026-05-25 | [`fa-abc-synthesis-deep-dive`](./knowledge/research/fa-abc-synthesis-deep-dive-2026-05.md) |

### Gotchas (delete when resolved)

| Gotcha | Pointer |
| :--- | :--- |
| ≈26 files cite «AGENTS.md PR Checklist rule #N» — orphan refs from PR A' skill extraction; top-10 priority list in pointer | [`exploration_log.md` Q-15](./knowledge/trace/exploration_log.md) |
| Streaming chain semantics = v0.2 redesign, not v0.1 amendment | [`exploration_log.md` Q-13](./knowledge/trace/exploration_log.md) |

### Backlog (active milestones only)

| Slot | Scope | Status |
| :--- | :--- | :--- |
| — | (no active milestone; M-6 + M-7 closed) | — |

## § Next

Priority-ordered. Completed items deleted, not struck through.

1. **Orphan cross-ref sweep** — ≈26 files from PR A' extraction.
   Top-10: `llms.txt` (9), `MAINTENANCE.md` (7), `ADR-10` (6),
   `DIGEST.md` (4), `ADR-7` (4). Retarget «AGENTS.md PR Checklist
   rule #N» → [`pr-creation/SKILL.md` §PR Checklist](./knowledge/skills/pr-creation/SKILL.md).
2. **Wire `IntentGuard` into the loop driver** — PR C landed the
   middleware shape; session bootstrap still needs to `register()`
   it with a `draft_path` resolved to
   `~/.fa/state/runs/<run_id>/pr_draft.md`, plus the deferred
   `prepare-pr` tool / sub-agent that populates that file
   (M-7 row Q-N item).
3. **ADR-10 follow-ups** — I-5 FA-surface audit; A28 «LLM emits a
   number» audit; `[CODE]` namespace + A23 lint.

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
