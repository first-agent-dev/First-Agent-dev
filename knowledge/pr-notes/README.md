# PR notes archive

Point-in-time PR notes / PR bodies, kept for history. These are **artifacts of a
specific PR**, not living docs — they are not maintained after merge. For current
state read [`HANDOFF.md`](../../HANDOFF.md); for durable design read the
[ADRs](../adr/README.md).

Newest first:

| Date | Note | Summary |
|------|------|---------|
| 2026-06-28 | [`PR_NOTE_HOOK_WORKFLOW_CLOSURE.md`](./PR_NOTE_HOOK_WORKFLOW_CLOSURE.md) | CHORE — hook workflow closure: bootstrap now verifies health (`uv sync --extra dev` + installer + `hooks-status`), `pre-commit` retry is real and narrowly restages only changed staged files, failing hook exit codes are preserved, installer/status honor `core.hooksPath` + git-worktree layouts, CI-surfaced lint/pyrefly nits are closed, and hook seat allows ordinary manual commits while keeping strict runtime enforcement in `pr.prepare` + `IntentGuard`. |
| 2026-06-15 | [`PR_NOTE_DOCS_IA_RESTRUCTURE.md`](./PR_NOTE_DOCS_IA_RESTRUCTURE.md) | CHORE — docs IA restructure: move operator guides to `knowledge/instructions/`, de-overlap install/ops, prune-allowing policy + offline link checker. |
| 2026-06-15 | [`PR_NOTE_DOCKER_DOCS_CONSOLIDATION.md`](./PR_NOTE_DOCKER_DOCS_CONSOLIDATION.md) | CHORE — consolidate Docker deploy scripts + Russian operator manual; `fa.service` user-unit fix; backup-doc fix. |
| 2026-06-12 | [`PR_BODY_GUARDRAILS_V2.md`](./PR_BODY_GUARDRAILS_V2.md) | CHORE — CI guardrails v2: align gates with empirical LLM-agent failure modes. |
| 2026-06-11 | [`PR_NOTE_LOOP_FOUNDATION.md`](./PR_NOTE_LOOP_FOUNDATION.md) | FIX — inner-loop foundation: cache-aware usage, session summary, tool projection chokepoint. |
| 2026-06-10 | [`PR_NOTE_DOCKER_RUNTIME.md`](./PR_NOTE_DOCKER_RUNTIME.md) | FIX — Dockerized FA runtime: stand-by default, explicit one-shot auto-run, restart-loop safety. |
| 2026-06-08 | [`PR_BODY.md`](./PR_BODY.md) | FIX — secrets hardening: runtime redaction, deploy docs, repo hygiene. |

> Adding a new PR note? Drop the file here and prepend a row above (per
> [`MAINTENANCE.md`](../MAINTENANCE.md)). Dates are approximate (PR landing).
