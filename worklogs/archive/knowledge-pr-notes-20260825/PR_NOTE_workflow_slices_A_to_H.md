# PR note — FA workflow sprint landing (slices A→H, distilled from plan + landed code)

## Executive summary

This PR lands the full current vertical workflow-orchestration sprint for the
First-Agent runtime, moving `fa workflow` from a simple multi-role convenience
wrapper toward a bounded, contract-driven controller with machine-readable
artifacts and adaptive routing.

The work was intentionally sequenced in disciplined slices so each phase built
on a stable foundation rather than broadening orchestration prematurely.

## Scope of this PR note

This note covers the landed work across the workflow sprint slices A→H as they
exist in the working tree relative to the baseline represented by local commit
`7618fc7` (recorded earlier as representing origin `1674eb9`).

The note is distilled from:
- landed code changes,
- landed tests,
- workflow implementation plan,
- Session-H hardening/subtraction review,
- operator-facing docs updates.

## Problem this sprint solved

Before this sprint, the repository had:
- strong role prompts in isolation,
- a `fa run` single-role entrypoint,
- a thin `fa workflow` pipeline concept,
- no persisted machine-readable evaluator verdict artifact,
- no persisted machine-readable flow-state contract,
- no bounded repair/replan controller semantics.

This sprint closes that gap by giving the workflow controller durable routing
truth (`eval_report.json`), durable controller state (`flow_state.json`), and a
bounded adaptive loop that can re-enter planner only under explicit route
semantics.

## Landing order by slice

### Slice A / B — semantic freeze + source-of-truth freeze

Landed in docs/research form:
- workflow semantics frozen before broad runtime growth,
- explicit split between narrative and controller truth,
- temporary physical representation chosen:
  - plan: human-readable,
  - eval report: machine-readable JSON,
  - FlowState: machine-readable JSON,
  - draft/work log: narrative-only.

Why this matters:
- prevented controller growth from collapsing back into prose parsing,
- made later runtime work target explicit artifact contracts.

### Slice C — prompt-contract tightening

Landed in prompt/runtime docs:
- evaluator semantics tightened around contract adjudication and route authority,
- coder semantics tightened around evidence and deviation discipline,
- planner minimally extended for replan triggers and handoff contract,
- prompt copies kept aligned between prompt source and prompt docs.

Why this matters:
- adaptive orchestration required route-clean evaluator output,
- planner re-entry needed explicit trigger semantics before runtime support.

### Slice D — structured eval artifact

Landed in code:
- new module `src/fa/inner_loop/workflow_artifacts.py`,
- `EvalReport`, `EvalFinding`, `StepResult`,
- atomic JSON persistence,
- deterministic parser translating evaluator final output into `eval_report.json`,
- fail-closed boundary validation on load.

Why this matters:
- workflow routing no longer depends on prose-only interpretation,
- evaluator route semantics became durable controller input.

### Slice E — FlowState MVP

Landed in code:
- `FlowState` artifact and atomic persistence,
- canonical artifact paths under `~/.fa/session-log/<run_id>/`,
- terminal state now reflects eval verdict truth rather than always claiming success.

Why this matters:
- state transitions became inspectable,
- later repair/replan logic could persist counters and terminal outcomes.

### Slice F — bounded repair loop

Landed in code:
- `fa workflow --mode repair`,
- `--max-repairs` budget (default 2, hard ceiling 3),
- controller decomposition into small helpers,
- bounded canonical `coder -> eval` loop driven by machine-readable
  `route_decision=return_to_coder`,
- planner re-entry intentionally still deferred at this slice.

Landed in tests:
- loop-until-pass,
- budget exhaustion,
- zero budget,
- no-loop on `return_to_planner`,
- role preconditions,
- mode validation,
- parser checks.

Why this matters:
- first end-to-end proof that routing from persisted eval truth works.

### Slice G — adaptive planner re-entry

Landed in code:
- `fa workflow --mode adaptive`,
- `--max-replans` budget (default 1, hard ceiling 2),
- canonical adaptive routing after initial pass:
  - `return_to_coder -> coder -> eval`
  - `return_to_planner -> planner -> coder -> eval`
- strict adaptive config requirement: roles must include `planner`, `coder`, `eval`,
- semantically real `active_plan_version`, `repair_round`, `replan_round`,
- parser mode choices deduplicated through canonical `_WORKFLOW_MODES`.

Landed in tests:
- replan until pass,
- replan budget exhaustion,
- mixed repair → replan → pass,
- adaptive role preconditions,
- parser budget wiring.

Why this matters:
- `fa workflow` became a bounded adaptive controller rather than a thin sequencer.

### Slice H — hardening / subtraction pass

Landed in docs/review artifacts:
- explicit keep decisions,
- explicit do-not-add-now decisions,
- residual design debt matrix,
- controlled future work matrix,
- deferred-items register with unblock factors,
- operator/maintainer memo.

Why this matters:
- prevents future sessions from re-deriving the same architecture decisions,
- keeps feature growth disciplined after the first adaptive landing.

## Runtime/controller changes in more detail

### New artifact layer

`src/fa/inner_loop/workflow_artifacts.py` now provides:
- `EvalReport`
- `EvalFinding`
- `StepResult`
- `FlowState`
- deterministic `parse_eval_report(...)`
- atomic JSON writers/loaders
- fail-closed boundary validation

### Workflow controller changes in `src/fa/cli.py`

The workflow controller now includes:
- workflow artifact path resolution,
- `_WorkflowContext`,
- `_WorkflowProgress`,
- `_run_stage`,
- `_run_initial_roles`,
- `_run_linear`,
- `_run_repair`,
- `_run_adaptive`,
- max repair/replan budget resolution,
- canonical mode labeling,
- stricter mode-specific role validation.

### CLI help / ergonomics

Landed:
- `src/fa/cli_help.py` bilingual help registry,
- `fa help` / `fa help --json` support,
- docs/help coverage for `repair` and `adaptive` workflow modes,
- workflow parser support for `--mode`, `--max-repairs`, `--max-replans`.

## Documentation/research changes

Updated/added materials include:
- workflow implementation plan,
- Session-H review,
- operator/maintainer next-actions memo,
- glossary entry for `FlowState`,
- operations docs for repair/adaptive semantics,
- planner prompt docs and compact prompt alignment,
- `knowledge/llms.txt` index updates for the new files.

## Verification performed

Relevant verification passed during the sprint slice:
- focused pytest scope: 112 passed,
- strict mypy on workflow source files: green,
- doc links: green.

Residual lint noise remains limited to repo-level `RUF001` on Russian
operator/help strings. This is recorded as a separate policy/hardening topic,
not a workflow-correctness blocker.

## Design decisions intentionally preserved

### Kept

- `fa run` remains the single-role invoker.
- `fa workflow` remains the multi-role state-machine advancer.
- eval route remains routing authority.
- FlowState remains controller truth.
- adaptive mode normalizes loops to canonical order after the initial pass.

### Intentionally deferred

- dedicated replanner prompt,
- generic transition engine,
- persisted-state-driven workflow resume,
- inspect/status command,
- separate plan identity from `run_id`,
- structured execution-evidence artifact,
- gate-density axis implementation,
- parallel/debate/micro-cycle orchestration,
- `fa run -a` ask/chat overloading.

Each deferred item now has an explicit unblock factor in the workflow plan.

## Risk and debt status after landing

### Controlled debt that remains acceptable

1. `active_plan_id=run_id`
   - acceptable while only plan versioning is operationally consumed.

2. prose-heavy terminal summaries
   - acceptable because machine truth already exists in persisted JSON.

3. repo-level `RUF001` noise
   - acceptable as a policy topic, not a correctness topic.

### What this PR intentionally does not solve

- resume-from-persisted-state orchestration,
- richer machine-readable execution evidence,
- operator-facing inspect/status surface,
- conversational/chat mode entrypoint design.

## Minimal follow-up plan

If workflow work resumes, choose exactly **one** narrow next slice:

1. repo-level `RUF001` policy cleanup,
2. persisted-state resume semantics,
3. inspect/status ergonomics,
4. structured execution evidence.

Do not combine them casually; each has a different consumer and complexity
profile.

## References

Primary supporting docs:
- `knowledge/research/fa-workflow-loop-implementation-plan-2026-06-29.md`
- `knowledge/research/fa-workflow-session-h-review-2026-06-30.md`
- `knowledge/research/fa-workflow-operator-maintainer-next-actions-memo-2026-06-30.md`
- `knowledge/instructions/02-operations.md`
- `PR_NOTE_workflow_session_h.md` (shorter distilled companion note)
