# FA workflow — operator/maintainer next-actions memo (2026-06-30)

## Purpose of this memo

This memo is **not** the primary design or implementation record.
It is a compact operational bridge for a future session that needs to answer:

- what is already landed and trustworthy,
- what is intentionally deferred,
- what should not be broadened casually,
- what realistic next actions remain,
- what stress tasks are worth running against the updated harness.

### Important reading contract

This memo is **self-explanatory for operators/maintainers**, but it is **not a
replacement** for the full design and hardening notes. A future session should
normally read it **paired with**:

1. `knowledge/research/fa-workflow-loop-implementation-plan-2026-06-29.md`

Use this memo as the **fast operational overlay**; use the implementation plan
as the **source of deeper rationale and the canonical deferred-items register**.
This memo already incorporates the useful outcomes of the Session-H review and
the next-session handoff block, so those separate artifacts are no longer
required for repository use.

## Current landed state

The workflow sprint completed the following chain in disciplined order:

1. prompt-contract tightening,
2. structured eval artifact,
3. FlowState MVP,
4. bounded repair loop,
5. bounded adaptive planner re-entry,
6. hardening/subtraction review.

### What the runtime can do now

#### `fa run`

- Still acts as the **single-role invoker**.
- Supports role-driven sessions for `planner`, `coder`, and `eval`.
- Remains separate from multi-role orchestration semantics.

#### `fa workflow`

Supports three routing strategies:

- `linear`
  - one pass through the requested role list;
  - fail-fast on stage exit;
  - records eval truth if eval ran.

- `repair`
  - one initial pass through the requested role list;
  - then bounded canonical `coder -> eval` loops when eval emits
    `route_decision=return_to_coder`;
  - planner re-entry is **not** performed in this mode.

- `adaptive`
  - one initial pass through the requested role list;
  - then canonical loop normalization:
    - `return_to_coder -> coder -> eval`
    - `return_to_planner -> planner -> coder -> eval`
  - bounded by both repair and replan budgets.

### Machine-readable controller truth

The workflow no longer depends on prose-only interpretation.

#### `eval_report.json`

- machine-readable evaluator verdict,
- machine-readable route decision,
- plan version recorded with the eval result,
- persisted under the session-log run directory.

#### `flow_state.json`

- machine-readable workflow controller state,
- current/terminal status,
- active role,
- `active_plan_version`,
- `repair_round`,
- `replan_round`,
- transition reason,
- last route decision.

### Current important invariants

1. `EvalReport` route semantics drive loop transitions.
2. `FlowState` is controller truth; `pr_draft.md` remains narrative-only.
3. Adaptive mode is bounded, not open-ended.
4. `active_plan_version` is now semantically real, not decorative.
5. Non-canonical role ordering is accepted for the **first pass only**; loop
   transitions normalize to canonical order afterward.

## What was intentionally *not* added

The following items are still deliberately deferred:

- dedicated replanner prompt,
- generic transition engine,
- persisted-state-driven workflow resume,
- `workflow inspect/status` command,
- separate plan identity from `run_id`,
- structured execution-evidence artifact,
- gate-density axis implementation (`phase-gated` / `step-gated`),
- any parallel/debate/micro-cycle orchestration,
- repo-level `RUF001` resolution for Russian strings,
- conversational ask/chat mode under `fa run -a`.

## Why these items are deferred

This sprint optimized for **foundation-first orchestration correctness**.
Adding the deferred items now would have expanded surface area faster than the
controller semantics stabilized.

### High-level defer rationale

- If an item has **no concrete machine consumer**, do not persist/build it yet.
- If an item adds **new UX surface**, do not add it until current workflow
  semantics are stable and operator pain is demonstrated.
- If an item introduces **framework-like abstraction**, do not add it merely for
  elegance; add it only when repeated duplication proves the need.

## What not to touch casually

### 1. Do not overload `fa run`

`fa run` is still the single-role invoker.
Do not casually merge conversational/chat semantics into it.
If chat mode is explored later, a **separate subcommand** (`fa ask`, `fa chat`)
is a cleaner direction than `fa run -a`.

### 2. Do not turn FlowState into resumable execution truth prematurely

The artifacts exist, but resumed orchestration semantics are not fully specified.
Do not “just continue from JSON” without a state-by-state resume contract.

### 3. Do not split planner/replanner prompts yet

The current planner prompt remains adequate.
A split should only happen if real usage shows measurable overload.

### 4. Do not add inspect/status surface just because artifacts exist

Artifact existence alone is not enough reason to broaden the CLI.
A future inspect/status command should answer repeated real operator friction.

## Known residual design debt

### D-1 — `active_plan_id=run_id`

- Today this is an acceptable bootstrap placeholder.
- It becomes insufficient only when true plan lineage or multi-plan-per-run
  semantics become necessary.

### D-2 — Terminal summaries are still mostly prose

- Acceptable now because persisted JSON is the real machine truth.
- Could matter later if CLI summaries need to be machine-consumable too.

### D-3 — `RUF001` on Russian strings

- This is **not** a workflow correctness problem.
- It **is** a repo-level lint-policy problem.
- Future sessions should treat it as policy/hardening work, not orchestration work.

## Verification status of the landed slice

At the end of the sprint slice:

- relevant pytest scope: **112 passed**,
- `mypy --strict`: green,
- doc links: green.

Residual lint noise is limited to repo-level `RUF001` on Russian strings.

## Handoff block for the next session

### Current state in one screen

The workflow sprint is functionally complete through Session H:
- prompt contracts tightened,
- eval artifact landed,
- FlowState landed,
- bounded repair loop landed,
- bounded adaptive planner re-entry landed,
- hardening/subtraction review outcomes folded back into this memo and the plan.

### Safe things to touch next

1. repo-level `RUF001` policy cleanup,
2. inspect/status artifact reader,
3. persisted resume semantics (only if specified state-by-state first),
4. structured execution evidence (only if a machine consumer is named).

### Dangerous things to touch casually

1. turning `fa run` into a mixed role/chat entrypoint,
2. adding a generic transition engine “for elegance”,
3. splitting planner/replanner prompts without evidence,
4. making FlowState resumable without a full transition contract,
5. adding inspect/status plus resume plus evidence in one combined slice.

### Recommended first question for the next session

> Which single consumer/problem is highest priority now: lint policy, operator inspection, interrupted workflow resume, or execution evidence?

Do not start from implementation before answering that question.

## Practical next actions

Choose **one** of these as the next narrow slice; do not mix them casually.

### Option A — Repo-level lint policy cleanup

Good next slice if the goal is cleaner CI and less future noise.

Focus:
- decide how Russian help/operator strings should interact with `RUF001`,
- apply the policy coherently,
- avoid scattered ad hoc suppressions.

### Option B — Workflow inspect/status ergonomics

Good next slice if operators repeatedly need to inspect current workflow state.

Focus:
- narrow artifact-reader surface only,
- no new orchestration semantics,
- no resume semantics bundled into it.

### Option C — Persisted resume semantics

Good next slice only if interrupted workflows become a real pain point.

Focus:
- specify exact meaning of “resume” per persisted state,
- define legal transitions,
- add interruption/resume tests before broadening CLI behavior.

### Option D — Structured execution evidence

Good next slice only if a real machine consumer exists.

Focus:
- define who reads the artifact,
- keep v1 minimal,
- do not create evidence artifacts just for completeness aesthetics.

## Stress tasks worth running against the harness

These are deliberately chosen to pressure the current semantics.
Some are code-centric; some are intentionally off-axis to expose where the
harness is not optimized.

### A. `fa run` single-role stress tasks

#### A-1. Planner ambiguity stress

```bash
fa run -r planner "Составь исполнимый план миграции legacy-модуля, где часть требований противоречит другой части. Сначала выдели противоречия, потом предложи минимальный исполнимый контракт."
```

**Why this matters:** checks whether the planner resists fake certainty under
contradictory requirements.

#### A-2. Coder evidence/boundary stress

```bash
fa run -r coder "Внеси минимальный change-set, но если acceptance нельзя выполнить без смены плана — не переопределяй задачу молча, а явно зафиксируй блокер и границу применимости."
```

**Why this matters:** checks whether coder discipline holds when the easiest
path would be silent contract drift.

#### A-3. Eval route-discipline stress

```bash
fa run -r eval "Оцени дифф не как code review в общем, а как acceptance judge: если дефект локальный — route к coder, если acceptance недостижим без смены плана — route к planner."
```

**Why this matters:** checks whether evaluator semantics stay route-clean.

#### A-4. Philosophical/non-code planner stress

```bash
fa run -r planner "Построй исполнимый план ответа на философский вопрос: 'Можно ли минимизировать ложную уверенность в reasoning-системе без потери полезности?' Сделай это как контракт с acceptance criteria."
```

**Why this matters:** the harness is not optimized for this domain; this helps
surface where planner contract structure is robust and where it is code-biased.

### B. `fa workflow` / `adaptive` stress tasks

#### B-1. Contradictory spec migration

```bash
fa workflow planner,coder,eval "Перенеси модуль на новую API-форму, сохранив старое поведение, но сократив публичный surface; если acceptance несовместим — зафиксируй replan." --mode adaptive --max-repairs 2 --max-replans 1
```

**Why this matters:** likely to trigger planner → coder → eval → planner.

#### B-2. Test-green but contract-wrong stress

```bash
fa workflow planner,coder,eval "Сделай refactor с зелёными тестами, но не меняй наблюдаемое поведение и не расширяй scope. Если тесты зелёные, но acceptance нарушен — route не к complete, а по контракту." --mode adaptive --max-repairs 2 --max-replans 1
```

**Why this matters:** checks whether eval semantics remain contract-centric,
not test-centric.

#### B-3. Repair-then-replan stress

```bash
fa workflow planner,coder,eval "Исправь подсистему с заведомо смешанными локальными дефектами и одной ошибкой в исходном плане. Попробуй локальный repair first, но при plan-level finding вернись к planner." --mode adaptive --max-repairs 2 --max-replans 1
```

**Why this matters:** intentionally targets multiple transitions across roles.

#### B-4. Environment-drift stress

```bash
fa workflow planner,coder,eval "Доведи изменение до acceptance, но если среда/зависимости делают acceptance недостижимым в текущем виде, не имитируй успех: route according to blocker class." --mode adaptive --max-repairs 1 --max-replans 1
```

**Why this matters:** checks honesty around environment blockers.

#### B-5. Non-code conceptual orchestration stress

```bash
fa workflow planner,coder,eval "Разработай, реализуй и оцени аргументированную позицию по вопросу: 'Нужен ли отдельный replanner prompt в агентной системе?' Сначала сделай контракт на критерии качества аргумента, потом попытайся его удовлетворить." --mode adaptive --max-repairs 1 --max-replans 1
```

**Why this matters:** pushes the harness into a lower-grounding domain and may
expose hidden assumptions of the workflow controller.

## Recommendation on future ask/chat mode

Current recommendation:

- **do not** add `fa run -a` in a hurry,
- if the feature is pursued, prefer a **separate future subcommand** such as
  `fa ask` or `fa chat`,
- define a clear UX contract first: how conversational mode differs from
  single-role execution and how it avoids collision with coder/planner/eval UX.

## Bottom line

Use this memo to decide **where to go next** without reopening the whole design
problem. For the deeper “why” and explicit decision matrices, pair it with the
plan and the Session-H review.
