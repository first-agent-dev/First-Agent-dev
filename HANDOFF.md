# HANDOFF.md — for the next agent / session

> **Read this first when starting a new session on this repository.**
> Canonical routing surface: [`knowledge/llms.txt`](./knowledge/llms.txt)
> §MUST READ FIRST. If the two disagree, llms.txt wins.

## 60-second bootstrap

1. Follow [`knowledge/llms.txt`](./knowledge/llms.txt) §MUST READ FIRST (5 files, in order).
2. Return here — read **§Current state**, then **§Next**.

## § Current state

Overwritten each session! Details live at the pointer, not here.

**As of:** 2026-05-27 — PR D in flight (M-8 LLM-driven coder loop + `fa run`)

### Landmarks (what landed)

| What | Date | Pointer |
| :--- | :--- | :--- |
| PR D in flight: `src/fa/inner_loop/coder_loop.py` (`drive_session`) + `prompt.py` + `fa run --task` CLI + `UrllibTransport`; bridges `ProviderChain` and `run_session` so the harness is finally LLM-drivable (M-8) | 2026-05-27 | [`coder_loop.py`](./src/fa/inner_loop/coder_loop.py), [`prompt.py`](./src/fa/inner_loop/prompt.py), [`cli.py`](./src/fa/cli.py), [`transport.py`](./src/fa/providers/transport.py) |
| PR C open (not merged): `src/fa/inner_loop/hooks/intent_guard.py` shipped on `devin/1779959363-pr-c-intent-guard`; awaits review/merge before `IntentGuard` can wire into `fa run` (M-7) | 2026-05-27 | [`BACKLOG.md` §M-7](./knowledge/BACKLOG.md) |
| PR B landed: `src/fa/hygiene/pr_intent.py` classifier + `prepare-commit-msg` / `commit-msg` hooks; snapshot test pins hook constants to skill §Output format (closes M-6) | 2026-05-27 | [`pr_intent.py`](./src/fa/hygiene/pr_intent.py), [`hooks/`](./src/fa/hygiene/hooks/) |
| PR A' landed: full PR-creation rulebook → loadable skill; AGENTS.md | 2026-05-26 | [`pr-creation/SKILL.md`](./knowledge/skills/pr-creation/SKILL.md) |
| `knowledge/skills/` directory established; `repo-audit` migrated (closes I-9b) | 2026-05-26 | [`skills/README.md`](./knowledge/skills/README.md) |
| PR A: §PR Intent Classification (5 Level-1 intents) + anti-shallow-fix gate | 2026-05-25 | [`AGENTS.md` §Loadable skills](./AGENTS.md#loadable-skills) |
| ADR-10 proposed — deterministic-harness invariants I-1..I-5 | 2026-05-25 | [`ADR-10`](./knowledge/adr/ADR-10-deterministic-harness-invariants.md) |
| ABC synthesis deep-dive — 9-repo determinism patterns (ADR-10 input) | 2026-05-25 | [`fa-abc-synthesis-deep-dive`](./knowledge/research/fa-abc-synthesis-deep-dive-2026-05.md) |
| ADR-9 T-2 driver + T-4 loader landed; 594 tests | 2026-05-22 | [`ADR-9`](./knowledge/adr/ADR-9-llm-provider-client.md), [`DIGEST.md`](./knowledge/adr/DIGEST.md) |

### Gotchas (delete when resolved)

| Gotcha | Pointer |
| :--- | :--- |
| ≈26 files cite «AGENTS.md PR Checklist rule #N» — orphan refs from PR A' skill extraction; top-10 priority list in pointer | [`exploration_log.md` Q-15](./knowledge/trace/exploration_log.md) |
| Streaming chain semantics = v0.2 redesign, not v0.1 amendment | [`exploration_log.md` Q-13](./knowledge/trace/exploration_log.md) |

### Backlog (active milestones only)

| Slot | Scope | Status |
| :--- | :--- | :--- |
| M-7 | PR C: `IntentGuard` middleware | open (PR #22) — awaiting merge |
| M-8 | PR D: LLM-driven coder loop + `fa run` CLI + `UrllibTransport` | in flight (PR D, 2026-05-27) |

## § Next

Priority-ordered. Completed items deleted, not struck through.

1. **Wire `IntentGuard` into `fa run` bootstrap.** PR D ships the
   driver and `fa run` but does not register `IntentGuard` —
   integration is a small ~20 LOC follow-up once PR D + PR C are
   both on `main`. Adds a `~/.fa/state/runs/<run_id>/pr_draft.md`
   read seam so the guard has something to validate against; until
   then the guard's allow-on-no-draft branch keeps the harness from
   deadlocking. Tracked: M-7 row §Q-N amendment items.
2. **`prepare-pr` tool that populates `pr_draft.md`.** The producer
   side of the M-7 read seam. Likely a `ToolSpec` registered next
   to the baseline filesystem tools; sub-agent or LLM-side rule
   composes the header. Deferred from M-7 follow-ups; deferred
   again from M-8 (the deep-dive §10 says «not in M4 scope»).
3. **Orphan cross-ref sweep** — ≈26 files from PR A' extraction.
   Top-10: `llms.txt` (9), `MAINTENANCE.md` (7), `ADR-10` (6),
   `DIGEST.md` (4), `ADR-7` (4). Retarget «AGENTS.md PR Checklist
   rule #N» → [`pr-creation/SKILL.md` §PR Checklist](./knowledge/skills/pr-creation/SKILL.md).
4. **ADR-10 follow-ups** — I-5 FA-surface audit; A28 «LLM emits a
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
