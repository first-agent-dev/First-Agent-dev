# Runtime IntentGuard retirement — operator decision

**Date:** 2026-11-06  
**Status:** Q130 policy selected; R19 Arena-local W0 row CLOSED by E473 after the named production-caller oracle and both temporary mutants passed/killed. Global W0 remains OPEN under Q113; W1 has not started. No Docker, deployed-host, or live-host acceptance is claimed.  
**Scope:** All production `fa run` paths, including managed workflow stages and managed child sessions. This note does not claim that IntentGuard's component implementation is correct, close I03, close global W0, or authorize W1.

## Decision

The runtime IntentGuard is not a policy gate for any production `fa run` session. It is intentionally retired from all production `fa run` callers because the existing design needs redesign and is not a current priority.

- No `pr_prepare` call is a precondition for the first or any later workspace mutation.
- `pr_prepare` remains available as an optional human-readable PR/work note. Its content, successful persistence, and same-process provenance do not authorize writes.
- Absence or failure of this optional note does not deny a tool mutation or make an otherwise successful scoped stage fail.
- Do not add an active-view snapshot API, empty-snapshot fallback, or controller Git/canonical-path probe to support the retired runtime gate.
- The operator consciously accepts loss of IntentGuard's pre-commit runtime test-edit protection. No replacement runtime test-edit policy is authorized now.
- Existing Workspace Authority, plan/admission, role-scoped tools, verification/evaluation, publication controls, human review, and commit-msg hook validation remain in force where applicable. This policy does not imply that every direct `fa run` path has the full workflow admission/verify/eval sequence.
- Shared PR-intent classification and test-edit validation at the commit-msg hook remain intact and must retain their negative tests.

A future plan-bound test-edit policy may be designed after I03. It must bind actual changed test paths to admitted-plan evidence; a free-form agent-authored explanation is not authority. It is deferred, is not an I03 prerequisite, and is not authorized for implementation by this decision.

## Source audit and migration obligations

The best-effort source audit found:

- `cli._cmd_run` builds the common production hook registry through `_build_run_hook_registry`; workflow stages reuse this run path.
- `tools/managed_subagent.py` separately registered an observe-only IntentGuard, which still reached the controller Git/path classifier.
- The coder prompt, readiness announcement, `pr_prepare` tool description, and resume comments described the draft as mandatory or as mutation authorization.
- `intent_guard.mode` was a fail-closed feature flag and was printed by live-check setup, although its production enforcement seat is being retired.
- Failed `pr_prepare` was included in scoped-stage failure classification; this must not make the optional note a workflow precondition.
- The existing `commit-msg` hook calls the shared PR-intent validator, including `validate_test_edits`. This hook path is separate from runtime IntentGuard and must remain active.

Implementation must remove IntentGuard registration from every production `fa run` caller, remove the active mode setting or make legacy config use explicitly observable as retired/ignored, update current prompts/docs/tool descriptions, and keep `pr_prepare` callable. Keep the component and its component tests only if still useful; they are not production/security-authority evidence. Preserve unrelated dirty worktree changes and make only the R19-scoped edits.

## R19 W0 oracle and kill checks

The managed production-caller oracle must drive parsed `fa run --role coder` through `_cmd_run`, managed registry construction, `drive_session`, a real local UDS supervisor/WorkspaceAuthority, and an admitted PROJECT view. The deterministic provider's first mutation is `fs_write_file` without calling `pr_prepare`.

It must prove all of the following:

1. The write reaches the managed `WorkspacePort` and records exactly one authority `WRITE_FILE` operation.
2. Canonical project bytes remain unchanged while the provider is live and change only after successful managed publication.
3. The IntentGuard `_default_git_runner` and `_project_call` producers are called zero times; the canonical `.git/index` sentinel is unchanged.
4. The note tool remains callable but is not a permit; commit-msg hook validation remains covered independently.

**Producer kill target:** temporarily re-register `IntentGuard` in `_build_run_hook_registry`. The no-`pr_prepare` write oracle must fail at the denied/missing `WRITE_FILE` effect or the trapped producer assertion.

**EDGE KILL-CHECK:** route the managed registry edge through the host-only builder (`workspace_io=None` / no managed executor), or restore the managed-child registration. The exact production oracle must fail because the authority `WRITE_FILE`/publication boundary or canonical-before-publication invariant is broken, or because a trapped IntentGuard producer runs.

The R19 row closes only after the named production test passes and both temporary mutants are killed/restored. This is Arena-local W0 evidence only: no Docker, deployed-host, live-host, or global W0 acceptance follows from it.
