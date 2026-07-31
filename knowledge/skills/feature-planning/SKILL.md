---
name: feature-planning
description: |
  Source-grounded implementation planning and execution skill for large code
  features and new projects. Forces concrete plans, live-path tests,
  producer kill-checks, path/matrix coverage, mutation handoff, and senior
  minimal-code discipline for Python, web/API/UI, CLI, workers, data, and
  multilayer systems.
status: active
last-reviewed: 2026-07-31
triggers:
  - "create an implementation plan"
  - "plan this feature"
  - "build a new project"
  - "implement this feature safely"
  - "write production-ready code"
  - "add tests for this feature"
  - "agentic harness code implementation"
  - "MAX effort mode"
  - "force a concrete plan"
  - "/production-feature-planning"
argument-hint: "[plan|execute|slice|new-project|audit]"
globs:
  - "**/*.py"
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
  - "**/*.go"
  - "**/*.rs"
  - "**/*.java"
  - "**/*.cs"
  - "**/*.sql"
  - "**/*.md"
  - "src/**"
  - "app/**"
  - "packages/**"
  - "tests/**"
  - "e2e/**"
  - "migrations/**"
alwaysApply: false
---

# Skill — Production Feature Planning & Live-Path Implementation

Use this for **large features**, serious bug fixes, multilayer changes, new
projects, security/data boundaries, and any implementation where fake-green tests
would be costly. It combines:

- `plan-authoring`: preflight, contracts, ID traceability, READY/BLOCKED gate.
- `tests-writing`: C0/C0p/C1/C2/C3/C4, live-path proof, producer kill-checks.
- `ponytail`: understand first, then choose the smallest safe production diff.

For trivial edits, use the compact P0 rule at the end. Do not run full ceremony
for typos, formatting, or docs-only changes unless the user requests it.

---

## 0. Central laws

1. **Read before plan; plan before risky code.** No symbol, file, route, table,
   flag, event, or test helper may appear unless verified by read/grep or marked
   `NEW`.
2. **Every goal closes a verified gap.** Each `G#` maps to `GAP#`, `CT#`, `S#`,
   `T#`, and an artifact or explicit non-goal.
3. **Producer proof is primary.** Product behavior ships only when a test that
   boots the real root fails if the production producer/write/render/gate is
   removed.
4. **Two-sided observable contracts.** Producers and consumers are both named and
   verified for events, APIs, DB rows, queues, files, CLI output, UI DOM, logs,
   metrics, hooks, migrations, and generated artifacts.
5. **Path/matrix coverage is enforced.** Happy, error, disabled, empty,
   malformed, permission, provider, browser, migration, concurrency, and rollback
   paths are tested or explicitly non-goals.
6. **No “no exception” theater.** Use ranked oracles: typed result/schema,
   status+fields, DB state, DOM state, trajectory, call count, FS content,
   structured deny reason, metrics/log fields. Free text is secondary only.
7. **Spec decisions belong in code.** Aim for compliance-by-construction:
   deterministic validators, schemas, closed enums, DB constraints, exit codes,
   state machines, or gates enforce the contract. Failures surface as structured
   warnings/errors/results that tests can assert; never as silent skips.
8. **Stop on policy.** New product, security, compatibility, retention,
   migration, dependency, pricing, UX, or public API decisions become `Q#`; stop
   if blocking.
9. **Minimal mechanism after real comprehension.** Reuse existing code, then
   stdlib/native/platform, then installed dependencies, then minimum new code.
   Never simplify away validation, security, accessibility, data-loss protection,
   rollback, or live-path tests.

---

## 1. Large-feature operating mode

| Mode | Use when | Output |
|---|---|---|
| `plan` | user asks for design/implementation plan | one READY/DRAFT/BLOCKED plan |
| `execute` | user asks to implement | plan gate, then `S#` slices |
| `slice` | plan exists | before/per/after edit gate for bounded slice |
| `new-project` | greenfield | runnable vertical slice, not scaffold theater |
| `audit` | assess plan/code | gap report with missing proof |

If user says **MAX effort mode**, increase preflight depth, edge inventory,
matrix rows, and mutation scrutiny. Do not add speculative architecture.

Depth after preflight:

| Depth | Use | Minimum proof |
|---|---|---|
| `P0` | one helper/file, no public contract | mini-plan + C0/C0p/static |
| `P1` | contained product capability | full plan + C1 + path matrix |
| `P2` | cross-module/API/DB/config/rollout | P1 + rollback/migration + C2 as needed |
| `P3` | architecture/public API/security model | P2 + ADR/monitoring/rollout plan |

If scope grows, stop and re-declare depth before editing further.

---

## 2. IDs and liveness

| ID | Meaning |
|---|---|
| `G#` | user goal / intent |
| `GAP#` | verified current→target gap |
| `CT#` | contract: function, signal, data, UI, security, performance |
| `P#` | runtime path / edge condition |
| `M#` | matrix row: flag/env/provider/browser/role/config |
| `A#` | artifact: file/module/table/route/page/config/doc/migration |
| `S#` | implementation slice |
| `T#` | test/static/mutation verification |
| `Q#` | open question, blocking or non-blocking with default |
| `RK#` | risk/mitigation |
| `RN#` | research note / past claim disposition |

Liveness: `L0` absent, `L1` import-reachable only, `L2` call-reachable but
unverified, `L3` behavior proven with producer kill-check. “Shipped” requires
`L3` for product claims.

---

## 3. Preflight

Record preflight before drafting or editing.

Existing repo:

1. identify real roots: CLI, API router, app bootstrap, page, worker, cron,
   package public API, migration runner, script `main`, test root;
2. grep/read related symbols, routes, tables, flags/env, events, config, tests,
   docs, migrations, ADRs;
3. state current behavior with file:symbol or “absent after grep”;
4. read 1–2 gold implementation/test patterns;
5. record liveness and unresolved `Q#`.

New project:

- choose or confirm runtime/framework, package/test commands, primary user path,
  persistence, config/env, security boundary, dependency policy, deployment
  target, and first runnable vertical slice.
- If choice is policy-sensitive, block as `Q#`; otherwise label assumption.

Preflight log shape:

```text
roots checked:
greps/reads -> findings:
gold patterns mirrored:
conflicts/invariants:
current liveness:
unresolved -> Q#:
```

---

## 4. Required plan skeleton

```text
# PLAN: <name>  Plan-ID: PLAN-<slug>
Status: DRAFT | READY | BLOCKED   Depth: P0|P1|P2|P3
Revision: v<N>   Changed-since-last: <initial|summary>

## Preflight log
## 0. Executive intent: G# goals, non-goals, minimal mechanism, proof sketch
## 1. Current state -> target state: source facts + GAP# ledger
## 2. Contracts: CT# cards
## 3. Path, edge, and matrix inventory: P# + M# coverage
## 4. Artifacts inventory: A# path/action/owner S#
## 5. Step-by-step implementation: S# edit packets
## 6. Verification plan: T# tests/static/mutation + LIVE-PATH PROOF
## 7. Risks, rollback, open questions: RK#, rollback, Q#
## 8. Research-note / claim disposition: RN# accept/reject/rewrite/defer
## 9. Definition of Done and READY gate evidence
```

`READY` requires no blocking `Q#`. `BLOCKED` means a policy/product question
prevents dependent steps. `DRAFT` means proof/research is incomplete.

---

## 5. Contract cards

Every behavior-changing goal needs at least one `CT#`.

### Function/module

```text
CT#: <name> TYPE:function/module
PRODUCER: <file:symbol or NEW>  ROOTS/CALLERS: <who invokes it>
INPUTS/OUTPUTS/ERRORS: <types, schema, ranges, exceptions/results>
SIDE EFFECTS: FS/DB/network/cache/log/event/none
INVARIANTS:
KILL-CHECK: changing/removing <producer logic> makes <T#> fail
```

### Observable signal

```text
CT#: <name> TYPE:signal
PRODUCER: <file:symbol/branch that creates observable behavior>
CONSUMER: <handler/client/UI/user-visible surface>
TRIGGER/PAYLOAD/STATE: <conditions, flags, schema, status, DOM, file shape>
DUAL-WRITE: durable + live channels both required? same branch?
PATHS/MATRIX: P# / M#
PRODUCER KILL-CHECK: remove producer -> <T#> fails
CONSUMER KILL-CHECK: remove handling -> <T#> fails
```

### Data/schema/migration

```text
CT#: <name> TYPE:data
SCHEMA/COMPATIBILITY: additive|breaking|migration required
READ/WRITE PATHS: <file:symbol>
AUTHORITY: source of truth / mirrors / derived projections / conflict winner
MIGRATION/ROLLBACK/BACKFILL:
FIXTURE HONESTY: tests use real schema/types
KILL-CHECK: remove schema/write/read/migration -> <T#> fails
```

### UI/web/security/performance add-ons

- UI: entry route/component, state source, user action, visible DOM result,
  loading/error/empty state, accessibility role/label, render kill-check.
- Security: boundary, allow, deny, fail-closed/open rationale, observable deny,
  C3 adversarial test, gate kill-check.
- Performance/reliability: budget, load/edge, timeout/retry/backpressure,
  observable metric/result, guard/cache/batching kill-check.
- Compliance: name the deterministic mechanism that decides the spec outcome;
  if it cannot decide, return a structured warning/error/result, not silence.

---

## 6. Path, edge, and matrix inventory

At minimum consider: happy, empty, malformed, boundary values, missing/invalid
config, unauth/authz denied, external timeout/rate-limit, persistence failure,
retry/idempotency, concurrency/race, disabled flag, legacy/rollback, UI
loading/error/empty/success.

Each `P#` row names trigger, source site, target behavior, covering `S#`, and
covering `T#`. Uncovered paths must be explicit non-goals.

Each `M#` row names flags/env/provider/browser/OS/role/API version/DB/deploy
mode. Naming a matrix is not coverage; each row needs a `T#` or `N/A — why`.

---

## 7. Verification taxonomy

Pyramid A is deterministic and gates merges. Pyramid B is subjective quality and
never replaces A.

| Class | Boots | Use | Product proof? |
|---|---|---|---|
| `C0` | isolated unit | pure helper/parser/validator | no alone |
| `C0p` | many inputs | properties/boundaries/schemas | pair with C1 |
| `C1` | real composition root, external I/O mocked | default product proof | yes |
| `C2` | CLI/API/browser/app e2e root | entrypoint/routing/packaging/UI | yes |
| `C3` | adversarial boundary | security/permissions/secrets/data loss | required |
| `C4` | mutation | adequacy after C1/C2 | strengthens proof |

Test docstring/description for product claims:

```text
root=<root> class=C0|C0p|C1|C2|C3|C4 claim=<G#/CT#>
matrix=<M#> path=<P#> oracle=<ranked oracle>
producer-kill-check=<exact producer/write/render/gate removal fails test>
consumer-kill-check=<if applicable>
```

Mock external I/O, not roots. Use real routers/app factories/config/state/DB
schema/event buses where wiring matters.

---

## 8. Execution protocol summary

Before using the detailed gates below, obey this compact sequence:

```text
Execution protocol summary:
Before edit -> per edit -> after edit -> mutation after chunk -> stop on Q#.
```

---

## 9. Mandatory before-edit gate

Before any edit, output this gate. If any blocking question remains, stop.

```text
BEFORE EDITING GATE
Current source-verified behavior:
- <file:symbol findings, or absent after grep>

Plan contract and gap IDs addressed by this slice:
- GAP#: ...
- CT#: ...
- S#: ...

Exact files allowed to change:
- <path>

Blocking questions:
- none
# or
- Q#: <question> blocks S# because <reason>

If blocking:
- STOP immediately.
- Append the Q# with full explanation to the active plan artifact if one exists.
- Include the same Q# and explanation in the response.
- Do not edit until resolved.

STOPPING: no edits until answered.
```

Allowed files are binding. If a new file is needed, stop and update the plan.
If current behavior cannot be verified, read more or mark `BLOCKED`.

---

## 10. Per-edit packet

For each edit, state one bounded packet.

```text
EDIT PACKET E# / S#
What idea is implemented now?
- <one concrete idea, not a bundle>

Concrete intent:
- <user/system outcome>

Current behavior -> target behavior:
- AS-IS: <source-verified behavior>
- TO-BE: <machine-checkable behavior>

Exact code mechanism:
- <file:symbol branch/call/schema/route/component>

Degree of freedom closed:
- <what could vary before and cause the bug/risk/scope leak>

Deterministic mechanism:
- <code/schema/gate/constraint that now makes the bad state impossible or observable>

Production best practice:
- <minimal safe mechanism; reuse/stdlib/native/dependency rationale>

Failure behavior:
- <errors, deny, fallback, rollback, idempotency, cleanup>

Definition of Done and negative proof:
- DoD: <observable state/artifact/contract>
- Negative proof: removing/changing <producer> makes <T#> fail

Tests-writing class:
- C0 | C0p | C1 | C2 | C3 | C4

Producer kill-check target:
- <exact production call site/branch/write/render source/gate>
```

Do not combine unrelated contracts unless inseparable.

---

## 11. Mandatory after-edit gate

After each edit, run and report:

```text
AFTER EDIT GATE
Targeted tests:
$ <command>
<actual output summary or full relevant output>

Static checks relevant to changed files:
$ <command>
<actual output>

Diff inspection:
$ git diff -- <files>   # or equivalent
<actual output/stat and notable hunks>

Contract status:
- GAP#: PASS/FAIL because <evidence>
- CT#: PASS/FAIL because <evidence>
- T#: PASS/FAIL because <oracle>

Not complete from “no exception”:
- <state the positive oracle and the negative proof target>
```

If tests fail, classify: implementation bug, test/oracle bug, plan mismatch,
stale preflight, or new blocking `Q#`.

Completion report for a chunk: files changed, mechanism, targeted tests, static
checks, diff, mutation/kill-check result, live-path proof, remaining gaps.

---

## 12. Mutation / kill-check protocol

After a big chunk, after C1/C2 are green, or before declaring shipped, run
mutation where feasible.

Tools: Python `mutmut`/`cosmic-ray`; JS/TS `stryker`; JVM PIT; PHP Infection;
Rust/Go targeted manual mutation.

Manual minimum:

1. remove/disable producer call/write/render/gate;
2. invert key branch or validation;
3. remove security deny gate if applicable;
4. remove consumer handler/render branch if applicable;
5. rerun named tests;
6. restore code;
7. report which tests failed.

Surviving mutation means weak oracle or non-live path; strengthen before ship.

---

## 13. Minimalism and stack checks

Minimalism ladder after tracing real flow: does it need to exist? reuse repo code;
stdlib; native platform/framework/DB/browser; installed dependency; one local
branch/adapter/schema edit; only then minimum new code.

Evidence gate for new components: before adding a tool/service/dependency/LLM
step/retrieval layer/subagent/topology, state what evidence or existing product
behavior proves need, what breaks if omitted, why existing code/config/stdlib/
native platform cannot replace it, whether deterministic code can do it without
an LLM call, and which metric or test proves it pays for itself. Weak answer ->
reject or defer.

Formal substrate before topology complexity: before adding subagents, DAGs,
worker pools, parallel orchestration, or workflow mutation, first make shared
state queryable/versioned enough for a simple chain to work; define write sets,
conflict behavior, and structured outputs. Topology is last resort.

Never add one-implementation interfaces, factories for one product, config no
one sets, unconsumed events, dependencies for trivial code, or test framework
complexity when a focused test proves the contract.

Project-native commands are authority. If absent, run the smallest relevant
check and report that CI authority is absent.

| Stack | Targeted tests | Static checks |
|---|---|---|
| Python | `python -m pytest tests/path::test_name` | `ruff`, `mypy`/`pyright`, `compileall` |
| JS/TS | `vitest`/`jest`/`npm test -- <name>` | lint, `tsc --noEmit`, build if relevant |
| Web UI | component + Playwright/Cypress root path | typecheck, lint, accessibility if available |
| Go | `go test ./pkg -run TestName` | `go test ./...`, `go vet`, `gofmt` |
| Rust | `cargo test test_name` | `cargo fmt --check`, `cargo clippy` |
| SQL/data | migration apply/rollback | schema diff/linter if configured |

---

## 14. READY gate and DoD

A plan is `READY` only if all are true:

- preflight names actual source facts or `NEW`;
- depth matches scope;
- every `G#` maps to `GAP#`, `CT#`, `S#`, `T#`, and `A#` or non-goal;
- current and target behavior are concrete;
- contracts name producer, consumer if applicable, paths, matrix, kill-check;
- every `P#`/`M#` is tested or explicitly `N/A — why`;
- product claims have C1/C2 live-path proof;
- security boundaries have C3 adversarial allow/deny proof;
- non-trivial logic has C4/tool/manual mutation plan;
- P2/P3/data changes have rollback/migration plan;
- no blocking `Q#` remains; all IDs resolve;
- minimal-mechanism check rejected unnecessary abstractions;
- research notes/past claims are dispositioned as accept/reject/rewrite/defer.

Definition of Done: all goals reach target `L3`, artifacts exist, tests/static
checks/mutation evidence is reported, non-goals respected, and removing the
producer/write/render/gate fails the named proof.

---

## 15. Anti-patterns enforced

Use this table during planning, execution, review, and completion reporting. A
producer can be a write, render branch, API response builder, DB insert, queue
publish, file generation, security gate, migration, or any code path creating
observable behavior.

| Anti-pattern | Detection | Enforcement |
|---|---|---|
| Vacuous kill-check | Test passes when producer/write/render/gate removed | Existence pre-check + mutation |
| Consumer-only proof | Handler/UI/client tested but producer never runs | C1/C2 producer proof required |
| No-exception theater | Command exits 0 but no behavior oracle | Ranked oracle required |
| Matrix theater | Matrix named but rows untested | One `T#` per `M#` |
| Silent non-goal | Path omitted without rationale | `P#` must be tested or explicit non-goal |
| Static-only theater | Type/lint/build passes but behavior is unobserved | Add C1/C2 behavioral oracle |
| Mocked-root theater | Test mocks the root it claims to verify | Boot real root; mock external I/O only |
| Snapshot-only theater | Snapshot changes but no contract field asserted | Assert schema/status/DOM/state fields |
| Dependency theater | New dependency added for trivial code | Apply minimalism ladder |

If any anti-pattern remains, the slice is not complete.

---

## 16. Escalation table

| Situation | Action |
|---|---|
| Symbol/behavior not verified | read/grep or mark `NEW`/`BLOCKED` |
| Vague mechanism | rewrite with file:symbol and contract |
| Shallow fix | name degree of freedom closed + deterministic mechanism |
| Signal one-sided | add missing side or explicit defer |
| “Add tests” without oracle | define class, root, oracle, kill-check |
| Multiple paths, one planned | add `P#` inventory and tests |
| Matrix named, rows uncovered | add `T#` per `M#` or `N/A — why` |
| Static green, behavior untested | add live-path C1/C2 |
| New file outside allowed list | stop; update artifacts/plan |
| Policy choice discovered | stop; promote to blocking `Q#` |
| Topology/subagent proposed | run evidence gate + substrate check first |
| Adapter/wrapper looks duplicate | verify call-convention semantics with C1 |
| Durable state without user surface | add consumer/surface or explicit defer |

---

## 17. New-project vertical slice

Greenfield first slice must include one primary path from entrypoint to
observable result, run/test commands, dependency/lockfile policy, config/env,
error convention, logging minimum, security boundary, test pyramid, CI/static
check plan, and README only after commands work. Avoid speculative layers until
a second real use case exists.

---

## 18. Compact P0 mini-plan

For tiny changes only:

```text
P0 MINI-PLAN
Current source-verified behavior: <file:symbol>
G#/GAP#/CT#: <intent/gap/contract>
Allowed files: <paths>
Mechanism: <one edit>
Test class: C0/C0p/C1 as appropriate
Oracle: <not no-exception>
Producer kill-check target: <site or N/A for pure helper>
DoD: <positive oracle + negative proof>
Blocking Q#: none | <stop>
```

Promote to full plan if more than one contract/file/product path appears.

---

## 19. Executor handoff

Follow `S#` order, honor dependencies, and do not expand artifacts silently.
Pair over autonomy: checkpoint before destructive/risky P2+ edits, surface diffs
frequently, require human approval for permission/security/data-boundary changes,
and use subagents only for bounded structured facts, not autonomous ownership.
Finalize with PASS/FAIL evidence: commands, outputs, diff summary, live-path
proof, mutation result, and remaining `GAP#`/`Q#`/`RK#`.

---

## 20. Worked example — Generic P1 REST + DB + UI

Illustrative only. Mark file names `NEW` unless preflight verifies them.

```text
# PLAN: Saved reports list  Plan-ID: PLAN-saved-reports
Status: READY   Depth: P1   Revision: v1

Preflight: API router NEW; web page NEW; reports absent after grep; Q#: none.
G1: User saves a generated report and sees it on the reports page.
Non-goals: sharing, editing, background generation, custom pagination.
GAP1 no durable write; GAP2 no list API; GAP3 no UI consumer.

CT1 create API/data:
- PRODUCER: NEW app/api/reports.py POST /reports/save inserts report row.
- INPUTS: title <=120 non-empty, body_ref, authenticated user.
- OUTPUT: 201 {id,title,created_at}; ERRORS: 400, 401.
- KILL-CHECK: remove DB insert -> T1 fails on missing row/id.

CT2 list API/UI:
- PRODUCER: GET /reports returns current user's reports.
- CONSUMER: app/ui/reports_page.tsx renders accessible list item.
- KILL-CHECK: remove serializer/query -> T2/T3 fail; remove render -> T3 fails.

CT3 security:
- User A must not see User B reports; remove user_id filter -> T4 fails (C3).

Paths/matrix:
- P1 happy create/list/render -> T1/T2/T3.
- P2 empty title -> T5 validation 400.
- P3 unauthenticated -> T6 deny.
- P4 cross-user isolation -> T4.
- M1 local test DB/default auth fixture -> T1-T6.

Steps:
- S1 CT1/GAP1 add table/model + POST route.
- S2 CT2/CT3/GAP2 add user-scoped GET route.
- S3 CT2/GAP3 add reports page render.
- S4/S5 add API/UI tests using real app/router/test DB; mock external I/O only.

Verification:
- T1 C1 create: response schema + DB row; kill-check=remove insert.
- T2 C1 list: 200 + JSON fields; kill-check=remove query/serializer.
- T3 C2 UI: DOM list item with title; kill-check=remove render branch.
- T4 C3 isolation: B excludes A row; kill-check=remove user filter.
- T5 C1 validation: 400 structured error; kill-check=remove validator.
- T6 C3 auth deny: 401/redirect; kill-check=remove auth gate.

LIVE-PATH PROOF: root=app test client + web page root; matrix=M1;
paths-covered=4/4; producer targets=DB insert, GET query/filter, UI render,
auth/user filter; pyramid=A.
DoD: G1 reaches L3 across DB write, API list, UI display, validation, auth,
and isolation with positive oracles and negative proof.
```
