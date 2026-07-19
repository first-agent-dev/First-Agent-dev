---
title: "FA workflow loop implementation plan: contract-driven planner/coder/eval orchestration"
source:
  - "knowledge/prompts/architect-fa.md"
  - "knowledge/prompts/architect-fa-compact.md"
  - "src/fa/inner_loop/prompt.py"
  - "https://developers.googleblog.com/developers-guide-to-multi-agent-patterns-in-adk/"
  - "https://arxiv.org/html/2605.18747v1"
  - "https://arxiv.org/html/2510.03902"
compiled: "2026-06-29"
chain_of_custody: |
  Primary repo-local facts come from the current role prompts in
  knowledge/prompts/ and src/fa/inner_loop/prompt.py. External workflow
  pattern claims are grounded in the cited URLs. This note is an
  implementation-planning artefact, not an ADR; if any normative rule is
  later accepted, promote it into an ADR or a code-enforced contract.
goal_lens: "design a multi-session implementation plan for FA's contract-driven planner/coder/eval workflow semantics, artifacts, and flow-state orchestration"
tier: stable
links:
  - "knowledge/research/cli-ergonomics-design-2026-06-29.md"
  - "knowledge/adr/ADR-2-llm-tiering.md"
  - "knowledge/adr/ADR-7-inner-loop-tool-registry.md"
  - "knowledge/adr/ADR-10-deterministic-harness-invariants.md"
mentions:
  - "fa workflow"
  - "planner"
  - "coder"
  - "eval"
  - "Delta Plan"
confidence: extracted
claims_requiring_verification:
  - "The existing runtime can absorb a first-class FlowState artefact without a larger session-log schema migration than planned here."
  - "A separate replanning planner prompt variant will outperform a single universal planner prompt enough to justify the extra surface area."
---

> **Status:** active. Decision-support note for a multi-session implementation effort.
>
> This note does two things at once: (1) it locks the target semantics for
> `fa workflow` and the planner/coder/eval loop, and (2) it decomposes the
> implementation into several sessions so the work can land incrementally
> without losing coherence.

## 0. Decision Briefing

### R-1 — Treat `fa workflow` as a flow-state orchestrator, not a three-call macro

- **What:** Redefine the semantic meaning of `fa workflow` from "run planner,
  coder, eval in sequence" to "advance a task through the FA role protocol
  using explicit flow state, structured artifacts, and route decisions."
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (~1.5k–3k tokens saved per future session by avoiding repeated re-derivation of loop semantics)
  - (B) helps LLM find context when needed: YES (single canonical note for workflow semantics and implementation sequence)
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens "design a multi-session implementation plan for FA's contract-driven planner/coder/eval workflow semantics, artifacts, and flow-state orchestration": YES (this is the note's core objective)
- **Cost:** medium (1–4h)
- **Verdict:** TAKE
- **Alternative-if-rejected:** Keep `fa workflow` linear and rely on prose-only conventions, at the cost of later rework when repair/adaptive modes land.
- **Concrete first step (if TAKE):** Freeze the target state machine and artifact taxonomy in this note before touching prompts or code.

### R-2 — Make Eval report the first structured orchestration artifact after Plan

- **What:** Prioritize a first-class structured Eval report with explicit route semantics (`return_to_coder`, `return_to_planner`, `complete`, `blocked`) before expanding adaptive workflow logic.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (~1k–2k tokens saved by replacing narrative findings with typed findings)
  - (B) helps LLM find context when needed: YES (typed findings are easier to route and summarize than freeform review prose)
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens "design a multi-session implementation plan for FA's contract-driven planner/coder/eval workflow semantics, artifacts, and flow-state orchestration": YES (it is the pivotal routing primitive)
- **Cost:** medium (1–4h)
- **Verdict:** TAKE
- **Alternative-if-rejected:** Start with FlowState only and leave Eval narrative, but that makes adaptive routing brittle and pushes ambiguity into the controller.
- **Concrete first step (if TAKE):** Define Eval verdict and finding schemas in this note, then update the eval prompt and tests around them.

### R-3 — Split the work into sequenced landing phases, with a vertical-slice proof before full adaptive control

- **What:** Implement the new workflow model across sequenced phases: semantics + docs, source-of-truth and temporary storage freeze, prompt contracts, structured Eval artifact, FlowState MVP, minimal repair vertical slice, then adaptive workflow control.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (future sessions can load the next open phase rather than the whole design problem)
  - (B) helps LLM find context when needed: YES (each phase has a bounded file set and acceptance target)
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens "design a multi-session implementation plan for FA's contract-driven planner/coder/eval workflow semantics, artifacts, and flow-state orchestration": YES (this is the delivery mechanism)
- **Cost:** cheap (<1h) to define; expensive (>4h) to fully execute over several sessions
- **Verdict:** TAKE
- **Alternative-if-rejected:** Attempt a single large patch that changes prompts, runtime, CLI semantics, docs, and artifacts together; higher integration risk.
- **Concrete first step (if TAKE):** Adopt the four-phase session plan in §6 and tie each phase to a concrete verification set.

### R-4 — Keep the current strong planner prompt, but introduce a distinct replanning mode only if evidence warrants it

- **What:** Do not immediately fork the planner prompt into two production variants. First tighten the semantics around when replanning occurs; only add a dedicated replanning prompt if the current planner prompt proves too overloaded in practice.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (avoids premature prompt-surface growth)
  - (B) helps LLM find context when needed: PARTIAL (a second prompt could help later, but adds routing complexity now)
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens "design a multi-session implementation plan for FA's contract-driven planner/coder/eval workflow semantics, artifacts, and flow-state orchestration": YES (it keeps the first implementation minimal and evidence-driven)
- **Cost:** cheap (<1h)
- **Verdict:** TAKE
- **Alternative-if-rejected:** Immediately add `planner-replan.md`, but that increases prompt drift risk before the runtime semantics are stable.
- **Concrete first step (if TAKE):** In Phase 2, add replanning semantics and route triggers to the existing planner contract first; defer a separate replanning prompt behind an explicit trigger in §7.

### R-5 — Make `fa run` the role invoker and `fa workflow` the state-machine advancer

- **What:** Keep a clean boundary: `fa run` invokes a single role session; `fa workflow` owns multi-role routing, flow-state persistence, retry budgets, and future adaptive modes.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (fewer ambiguous entrypoints)
  - (B) helps LLM find context when needed: YES (clear "which layer do I inspect?" routing)
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens "design a multi-session implementation plan for FA's contract-driven planner/coder/eval workflow semantics, artifacts, and flow-state orchestration": YES (clean separation of concerns)
- **Cost:** medium (1–4h)
- **Verdict:** TAKE
- **Alternative-if-rejected:** Push workflow logic down into `fa run`, which couples single-role invocation semantics to orchestration state.
- **Concrete first step (if TAKE):** Keep `fa run` stable and implement new controller logic behind `fa workflow` only.

### Summary

| R-N | Verdict | Project-fit (A / B) | Goal-fit (C) | Cost | Alternative-if-rejected | User decision needed? |
|-----|---------|---------------------|--------------|------|--------------------------|------------------------|
| R-1 | TAKE | YES / YES | YES (semantic freeze) | medium | linear macro only | No (TAKE) |
| R-2 | TAKE | YES / YES | YES (routing primitive) | medium | FlowState-first, narrative eval | No (TAKE) |
| R-3 | TAKE | YES / YES | YES (delivery shape) | cheap to define / expensive to execute | one giant patch | No (TAKE) |
| R-4 | TAKE | YES / PARTIAL | YES (subtraction-first) | cheap | fork prompts now | No (TAKE) |
| R-5 | TAKE | YES / YES | YES (layer boundary) | medium | overload `fa run` | No (TAKE) |

## 1. TL;DR

- The current planner prompt is already the strongest part of the role stack; the next bottleneck is not planning quality but orchestration contract clarity.
- `fa workflow` should be treated as a state-machine controller over planner/coder/eval, not a convenience wrapper over three `fa run` calls.
- The first high-ROI runtime artefact to add is a structured Eval report with route semantics; this unlocks adaptive routing without requiring the full future system immediately.
- FlowState must become explicit if future sub-agents are a goal; otherwise retries, replans, and route decisions remain chat-conventional and fragile.
- Do not immediately split the planner prompt. First tighten runtime semantics and prompt contracts around replanning. Add a dedicated replanner prompt only if real usage proves the universal planner prompt overloaded.
- The implementation should land over several sessions in ordered phases: semantic freeze + docs, source-of-truth/storage freeze, prompt contracts, structured Eval artifact, FlowState MVP, minimal repair vertical slice, then adaptive controller modes.
- Each phase below has acceptance conditions so the work can pause safely between sessions.
- No adaptive routing logic should land before route decisions and state transitions are inspectable from persisted artifacts.

## 2. Scope, метод

- **Read:** current planner/coder/eval prompts from `knowledge/prompts/` and `src/fa/inner_loop/prompt.py`; current CLI ergonomics design note; selected external references on sequential pipelines, generator/critic loops, and stateful orchestrators.
- **Deliberately excluded:** full code-level implementation details of every runtime file; a patch in this note; any irreversible prompt split before the orchestration semantics are stabilized.
- **Method:** design review + gap analysis + implementation-roadmap synthesis.
- **Goal-lens (verbatim):** "design a multi-session implementation plan for FA's contract-driven planner/coder/eval workflow semantics, artifacts, and flow-state orchestration".

## 3. Key concepts

- **Execution contract:** the planner-produced artefact that specifies goal, scope, steps, acceptance predicates, and verification methods. In FA this is stronger than a casual plan.
- **Execution evidence:** coder-produced records of what changed, what commands ran, and what verifications passed or failed.
- **Acceptance judgment:** eval's task of deciding whether the execution contract has been satisfied, not whether the code could be nicer in a general sense.
- **Route semantics:** typed next-action guidance emitted by eval (repair vs replan vs done vs blocked).
- **FlowState:** the controller-owned machine-readable state for the current workflow (`PLANNING`, `CODING`, `EVALUATING`, etc.), including retry counters and active plan version.
- **Delta Plan:** planner-issued replacement for only the invalidated part of the plan after a plan-level or assumption-level failure.

## 4. Recommended target model

### 4.1 Canonical workflow semantics

Canonical loop for FA v0.1+:

```text
Planner emits executable contract
→ Coder executes against contract
→ Eval judges contract satisfaction, not “code quality in general”
→ bounded repair loop for implementation-local defects
→ Planner re-enters only on contract failure, ambiguity, or retry exhaustion
```

This is not a rejection of broad code quality controls. Broad quality remains covered by:
- strong system prompts,
- deterministic verification commands,
- AGENTS.md / repo rules,
- authoring guardrails,
- sandbox and hook enforcement,
- regression gates such as `just check`.

What changes is the **semantic role of Eval**: it becomes the contract adjudicator and route emitter, not an unconstrained reviewer.

### 4.2 State machine (recommended baseline)

```text
INIT
→ PLANNING
→ PLAN_READY
→ CODING
→ EVALUATING
→ DONE
```

Additional states:
- `CODER_BLOCKED`
- `REPAIR_REQUIRED`
- `REPLAN_REQUIRED`
- `DELTA_PLANNING`
- `FAILED`

Allowed transitions:

| From | To | Trigger |
|------|----|---------|
| `INIT` | `PLANNING` | workflow starts |
| `PLANNING` | `PLAN_READY` | planner emits valid execution contract |
| `PLANNING` | `FAILED` | blocking contradiction / missing hard precondition |
| `PLAN_READY` | `CODING` | controller invokes coder |
| `CODING` | `EVALUATING` | coder finishes current execution round |
| `CODING` | `CODER_BLOCKED` | coder detects hard blocker |
| `CODER_BLOCKED` | `CODING` | local blocker cleared without replan |
| `CODER_BLOCKED` | `REPLAN_REQUIRED` | blocker implies contract ambiguity / plan defect |
| `EVALUATING` | `DONE` | eval returns PASS |
| `EVALUATING` | `REPAIR_REQUIRED` | eval returns implementation-local failure |
| `EVALUATING` | `REPLAN_REQUIRED` | eval returns contract-level / plan-level failure |
| `REPAIR_REQUIRED` | `CODING` | repair round budget remains |
| `REPAIR_REQUIRED` | `REPLAN_REQUIRED` | repair budget exhausted |
| `REPLAN_REQUIRED` | `DELTA_PLANNING` | planner re-entry authorized |
| `DELTA_PLANNING` | `PLAN_READY` | delta plan emitted |
| `DELTA_PLANNING` | `FAILED` | no viable delta plan |

### 4.3 Artifact contract between roles

Minimal logical artefacts (whether or not they are separate files at first):

1. **Plan Artifact** — planner-owned execution contract.
2. **Execution Artifact** — coder-owned execution evidence.
3. **Evaluation Artifact** — eval-owned acceptance verdict + findings + route decision.
4. **FlowState Artifact** — controller-owned machine-readable state.

These do **not** all need to become separate physical files in Phase 1. But they must become explicit concepts now so later runtime work does not collapse into one overloaded markdown log.

### 4.3.1 Source-of-truth hierarchy (freeze before runtime work)

| Artifact | Owner | Human-readable? | Machine-readable? | Source of truth for |
|----------|-------|-----------------|-------------------|---------------------|
| Plan Artifact | Planner | YES | PARTIAL | Execution contract, step graph, acceptance targets |
| Execution Artifact | Coder | PARTIAL | YES | What was changed, what was run, deviations, unresolved issues |
| Evaluation Artifact | Eval | PARTIAL | YES | Verdict, findings, route decision |
| FlowState Artifact | Workflow controller | OPTIONAL | YES | Current state, budgets, next actor, transition audit |
| `pr.prepare` draft / work log | Shared narrative surface | YES | NO (controller must not treat it as authoritative) | Human-readable session story and operator review |

### 4.3.2 Temporary physical representation (first landing recommendation)

Until a later ADR or stronger runtime need changes the shape, use this temporary physical model:

- **Plan Artifact:** Markdown-first, carried by the planner output and mirrored in the draft/work-log surface.
- **Execution Artifact:** machine-readable JSON artefact, even if initially small.
- **Evaluation Artifact:** machine-readable JSON artefact; this is the first structured workflow artefact to land.
- **FlowState Artifact:** machine-readable JSON artefact, small and append-safe.
- **Draft / work log:** human-readable narrative companion only; not the controller source of truth.

This temporary shape is intentionally asymmetric: human-readable plan, machine-readable verdict/state. The asymmetry is a feature, not a bug.

### 4.4 `fa workflow` semantic meaning

Target meaning:

> Advance a task through the FA role protocol, preserving shared state and routing between planner/coder/eval according to flow state.

Entry-point boundary:
- `fa run` = invoke one role session.
- `fa workflow` = advance the multi-role state machine.

Future modes supported by design are best understood as two dimensions, not a flat list.

**Dimension A — routing strategy**
- `linear`: `planner -> coder -> eval`
- `repair`: `planner -> coder -> eval -> coder -> eval`
- `adaptive`: `planner -> coder -> eval -> (coder|planner)` based on `route_decision`

**Dimension B — gate density**
- `phase-gated` (default): eval runs at major phase boundaries / execution rounds
- `step-gated` (special): eval runs after smaller units for high-risk tasks only

`gated` therefore is not a sibling of `linear` / `repair` / `adaptive`; it is an orthogonal density choice applied to a routing strategy.

### 4.5 Eval report (first-class structured artefact)

Recommended top-level fields:

```text
run_id
plan_id
plan_version
evaluation_id
verdict                # PASS | REPAIR_REQUIRED | REPLAN_REQUIRED | BLOCKED
summary
step_results[]
findings[]
integration_checks[]
regression_checks[]
route_decision         # return_to_coder | return_to_planner | complete | blocked
confidence             # optional
```

Recommended finding fields:

```text
finding_id
severity               # critical | major | minor | info
class                  # implementation | plan | environment | scope | regression
blocking               # bool
route                  # coder | planner | human
step_id                # nullable
location               # file/line/command/artifact ref
claim
evidence
expected
actual
required_action
suggested_check        # optional
```

Initial v1 scope should keep the class taxonomy intentionally narrow. Candidate later extensions such as `security`, `docs`, or `verification` should arrive only after the controller already consumes the core routes reliably.

This is the single highest-ROI structured artefact to add first.

### 4.6 Retry and exit policy

Recommended default budgets:
- repair loop (`coder <-> eval`): 2 rounds, max 3
- delta replans: 1 by default, max 2
- same-command transient verification retry: 1

Planner re-entry should be stricter than the informal word "ambiguity" suggests. Recommended hard triggers:
- the current acceptance predicate cannot be satisfied without changing the plan;
- repair budget on the current plan version is exhausted;
- eval emits a blocking finding of class `plan` or `scope` with route=`planner`;
- environment drift invalidates an explicit planner assumption.

`DONE` only if all are true:
- eval verdict = `PASS`
- no blocking findings remain
- focused verification passed
- regression verification passed or explicitly waived by policy
- active plan not invalidated
- no unresolved contract contradiction remains

`FAILED` if any are true:
- planner cannot produce executable contract
- hard environment blocker persists
- repair rounds exhausted and no viable replan exists
- replan rounds exhausted
- unresolved contradictory requirements remain

## 5. Gap review after inspecting current prompts

### 5.1 Planner is already strong; do not churn it first

Current strength:
- bounded recon
- explicit blocker policy
- mechanical acceptance taxonomy
- step independence for weaker coder
- Delta Plan semantics
- anti-pattern discipline

Conclusion:
- The planner is not the immediate bottleneck.
- The next bottleneck is the **protocol around planner output**, not the planner's raw planning ability.

### 5.2 Eval is under-specified relative to its future load

Current eval prompt is systematic, but still reviewer-shaped.
Main issue: it mixes three concerns:
- acceptance judgment,
- broader review,
- planner-level escalation reasoning.

Needed change:
- turn Eval into an **acceptance judge with route authority**;
- separate blocking contract failures from non-blocking observations;
- emit machine-usable route semantics.

### 5.3 Coder lacks a strong evidence protocol

Current coder protocol is step execution plus a narrative work log.
Needed change:
- require per-step execution evidence fields;
- prevent silent contract redefinition by coder;
- capture deviations, assumptions introduced, and unresolved issues explicitly.

### 5.4 Runtime semantics lag behind planner sophistication

The planner already knows how to produce Delta Plans, keep valid subgraphs, and classify failures.
The runtime currently does not fully exploit that sophistication.
Needed change:
- add FlowState and structured route decisions before complex adaptive behavior.

### 5.5 One prompt vs two prompts for planner/replanner

Current recommendation:
- **do not** split immediately.
- first, add replanning triggers and delta-plan expectations to the current planner contract.
- only after usage evidence, decide whether a dedicated replanning prompt is worth the extra maintenance surface.

A dedicated replanner prompt becomes justified only if at least one of these is observed repeatedly:
- Delta Plan outputs are consistently too verbose or too broad;
- the main planner spends too many tokens re-stating initial assumptions during replans;
- prompt complexity degrades delta-plan reliability measurably.

## 6. Multi-session implementation plan

The plan below is intentionally phased so each session can stop on a clean boundary.

### Phase 1 — Semantic freeze + design landing

**Goal:** freeze the target workflow semantics before code growth.

**Deliverables:**
- this research note (or its evolved successor),
- updated docs language clarifying that `fa workflow` is evolving toward state-machine orchestration,
- explicit backlog / implementation checklist for the next phases.

**Primary files:**
- `knowledge/research/fa-workflow-loop-implementation-plan-2026-06-29.md`
- `knowledge/instructions/02-operations.md` (conceptual clarifications only)
- `knowledge/llms.txt`

**Acceptance:**
- a future session can read one note and know the target state machine, role boundaries, temporary physical model, and landing phases;
- no code changes required yet.

### Phase 1.5 — Source-of-truth + temporary storage freeze

**Goal:** decide the temporary physical representation early enough that prompts and runtime can target a real model instead of an abstract one.

**Subtasks:**
1. Freeze source-of-truth ownership per artefact.
2. Freeze temporary JSON-vs-Markdown placement.
3. Clarify how `pr.prepare` remains a narrative surface without becoming controller truth.
4. Capture any compatibility constraints from the current session-log layout.

**Primary files:**
- `knowledge/research/fa-workflow-loop-implementation-plan-2026-06-29.md`
- any targeted runtime note or lightweight code comments if needed

**Acceptance:**
- the next implementation session can answer: where does the controller read truth? where does the operator read narrative? what is duplicated and what is not?

### Phase 2 — Prompt-contract tightening

**Goal:** align planner/coder/eval prompts with the new protocol, while keeping runtime behavior mostly unchanged.

**Subtasks:**
1. Tighten Eval semantics around contract adjudication and route decisions.
2. Tighten Coder semantics around execution evidence and deviation reporting.
3. Add explicit wording that non-blocking improvement suggestions must not be emitted as blocking failures.
4. Update planner wording only where needed to clarify replanning triggers and delta-plan handoff expectations.
5. Keep the prompt obligations transitional: only fields that the runtime will soon persist or inspect should be treated as hard output obligations.

**Primary files:**
- `knowledge/prompts/architect-fa.md`
- `knowledge/prompts/architect-fa-compact.md`
- `src/fa/inner_loop/prompt.py`
- prompt-related tests (as needed)

**Acceptance:**
- prompt texts are internally consistent on: contract / evidence / verdict / route;
- prompt outputs do not promise runtime enforcement that does not exist yet;
- tests or deterministic render checks pass.

### Phase 3 — Structured Eval artefact

**Goal:** land the first machine-readable workflow artefact with route semantics.

**Subtasks:**
1. Define Eval verdict / finding / route schema.
2. Persist the Eval report in the temporary physical representation chosen in Phase 1.5.
3. Add tests for round-tripping verdicts and route decisions.
4. Keep the initial finding taxonomy intentionally narrow.

**Primary candidate files:**
- session-log artefact writers/readers
- `src/fa/cli.py` or adjacent workflow/runtime modules as needed
- tests for verdict parsing / persistence

**Acceptance:**
- eval can emit `route_decision` deterministically;
- a later controller can read verdict and route without parsing prose;
- tests prove schema round-trip stability.

### Phase 4 — FlowState MVP

**Goal:** land the minimum controller state required for bounded workflow advancement.

**Subtasks:**
1. Define and persist FlowState MVP.
2. Track `repair_round`, `replan_round`, `active_plan_version`, `last_actor`, and `last_transition_reason`.
3. Make state survive resume.
4. Keep every transition inspectable from persisted artifacts.

**Primary candidate files:**
- workflow/runtime state modules
- session-log artefact writers/readers
- tests for workflow / role routing / persistence

**Acceptance:**
- a workflow run can persist enough machine-readable state to know the next actor and remaining budget;
- state survives resume;
- transitions are inspectable without replaying the whole narrative log.

### Phase 5 — Minimal repair vertical slice

**Goal:** prove the first bounded adaptive behavior end-to-end before planner re-entry lands.

**Subtasks:**
1. Keep `linear` mode stable.
2. Add `repair` mode: `planner -> coder -> eval -> coder -> eval`.
3. Consume Eval `route_decision=return_to_coder` plus the repair budget.
4. Do **not** add planner re-entry yet in this phase.

**Primary candidate files:**
- `src/fa/cli.py`
- `tests/test_cli_ergonomics.py`
- runtime state/report readers as needed

**Acceptance:**
- the workflow controller can run one full repair loop based on machine-readable eval output;
- retry budgets are enforced;
- the path is end-to-end test-covered.

### Phase 6 — `fa workflow` adaptive controller

**Goal:** upgrade `fa workflow` from repair-capable controller to bounded adaptive state-machine advancer.

**Subtasks:**
1. Keep `linear` and `repair` modes stable.
2. Add `adaptive` planner re-entry on route decision.
3. Keep route triggers strict; do not escalate to planner on vague uncertainty alone.
4. Defer `step-gated` mode unless a concrete high-risk use-case is selected.
5. Update CLI help / docs / tests to reflect mode semantics.

**Primary candidate files:**
- `src/fa/cli.py`
- `src/fa/cli_help.py`
- `tests/test_cli_ergonomics.py`
- docs in `knowledge/instructions/02-operations.md`

**Acceptance:**
- `fa workflow` can advance FlowState rather than only call roles in sequence;
- route decisions determine the next actor;
- bounded failure exits are deterministic and test-covered.

## 7. Suggested session-by-session execution order

### Session A — Freeze semantics and patch docs minimally

- Finalize this design note.
- Make minimal doc changes so future readers do not mistake `fa workflow` for the finished semantics.
- Add an implementation checklist reference.

### Session B — Freeze source-of-truth and temporary storage shape

- Record the controller-vs-narrative source-of-truth hierarchy.
- Freeze the temporary JSON/Markdown placement for Plan / Execution / Eval / FlowState.
- Confirm `pr.prepare` remains narrative-only for controller purposes.

### Session C — Prompt-contract rewrite pass

- Rewrite Eval prompt first.
- Then strengthen Coder prompt output-evidence expectations.
- Touch planner only for replanning handoff clarity.
- Run prompt/render tests.

> **Progress note (2026-06-30):** Eval and Coder prompt tightening landed in
> `src/fa/inner_loop/prompt.py`. Planner-side minimal touch now landed too:
> a `### Replan triggers` block (aligned to the evaluator's
> `REPLAN_REQUIRED` / `return_to_planner` route) and a `### Handoff contract`
> block were added to `PLANNER_SYSTEM_PROMPT`, mirrored byte-for-byte into
> `knowledge/prompts/architect-fa.md`, with a compact variant added to
> `architect-fa-compact.md`. No churn to the existing strong planner structure.

### Session D — Structured Eval artefact + findings taxonomy

- Land Eval verdict / finding / route schema.
- Persist Eval reports in the chosen temporary storage shape.
- Add tests.

> **Progress note (2026-06-30):** foundational artifact module landed as
> `src/fa/inner_loop/workflow_artifacts.py` with `EvalReport`,
> `EvalFinding`, `StepResult`, atomic JSON persistence, and tests.
>
> **Update (2026-06-30, runtime emission):** `eval_report.json` is now emitted
> by the real `fa workflow` path. `parse_eval_report` deterministically
> translates the eval role's `## Verification Summary` final message into an
> `EvalReport` (step-as-function, no extra LLM call), and `_cmd_workflow`
> persists it after the eval stage via an `outcome_sink` seam on `_cmd_run`.
> The parser is fail-closed: missing/unparseable verdict → `BLOCKED`/`blocked`;
> a route token contradicting the verdict is overridden by the verdict default.
> `from_json_dict` loaders now validate-and-narrow JSON at the boundary
> (mypy-strict clean, fail-closed on malformed input).

### Session E — FlowState MVP

- Add state file / state persistence.
- Add counters (`repair_round`, `replan_round`) and active plan version.
- Add transition-audit fields and resume tests.

> **Progress note (2026-06-30):** `FlowState` dataclass + atomic JSON
> persistence landed in `src/fa/inner_loop/workflow_artifacts.py`, and
> canonical workflow artifact paths were wired into `fa workflow` for the
> current linear controller.
>
> **Update (2026-06-30, eval route as persisted truth):** the terminal
> `flow_state.json` write no longer always claims `DONE`. When an eval stage
> ran, the eval **verdict** now drives the terminal `status`
> (`PASS→DONE`, `REPAIR_REQUIRED→REPAIR_REQUIRED`,
> `REPLAN_REQUIRED→REPLAN_REQUIRED`, `BLOCKED→FAILED`) and
> `last_route_decision` records the eval route. The linear baseline still does
> **not** loop on a non-PASS verdict — it only records the route as controller
> truth so the bounded repair controller (next slice) can consume it. FlowState
> is therefore now *partly* read-driven at the terminal boundary; full
> mid-loop read-driven transitions remain pending.

### Session F — Minimal repair vertical slice

- Upgrade controller from linear to repair-capable.
- Consume `return_to_coder` route decisions.
- Keep planner re-entry out of this proof.
- Prove one full bounded repair loop end to end.

> **Progress note (2026-06-30): Phase 5 / Session F landed.** `fa workflow`
> now has a `--mode {linear,repair}` axis (default `linear`, byte-stable with
> the prior behavior) and a `--max-repairs` budget (default 2, hard ceiling 3,
> plan §4.6). The controller was decomposed into a `_WorkflowContext` +
> `_run_stage` / `_run_linear` / `_run_repair` so each path is small and
> testable. `_run_repair` drives a bounded `coder → eval` loop **purely from
> the machine-readable eval route** (`return_to_coder`); `return_to_planner` /
> `blocked` are recorded in `flow_state.json` but do **not** re-enter the
> planner (intentionally deferred to Session G). Budget is strictly enforced;
> the terminal `flow_state.json` records `repair_round` and the final eval
> route. End-to-end test coverage added in `tests/test_cli_ergonomics.py`
> (loop-until-pass, budget-cap, zero-budget, no-loop-on-return_to_planner,
> role-precondition, mode validation, arg parsing) via a deterministic
> role-aware fake transport. CLI help (`cli_help.py`) and operations docs
> updated. Still pending: planner re-entry / adaptive routing (Session G).

### Session G — Adaptive `fa workflow`

- Add adaptive planner re-entry.
- Keep `linear` and `repair` as baseline / fallback modes.
- Document the two-axis mode matrix.

> **Progress note (2026-06-30): Phase 6 / Session G landed.** `fa workflow` now
> supports `--mode adaptive` plus `--max-replans` (default 1, hard ceiling 2).
> After the initial role-list pass, the controller normalizes loops to canonical
> routes: `return_to_coder -> coder -> eval`, `return_to_planner -> planner -> coder -> eval`.
> `adaptive` is intentionally stricter than `repair`: it requires `planner`,
> `coder`, and `eval` in the workflow role set (invalid config -> exit 2).
> `active_plan_version` and `replan_round` are now semantically real: planner
> re-entry bumps both, and the latest `eval_report.json` persists the new
> `plan_version`. Session-G also closed the main high-ROI review gaps from the
> Session-F audit: parser mode choices now reuse canonical `_WORKFLOW_MODES`,
> docs now separate the implemented routing axis from the still-deferred gate
> density axis, glossary coverage for `FlowState` was added, and ordering
> semantics for non-canonical role lists were made explicit (initial pass is as
> requested; adaptive loops normalize to canonical order). End-to-end tests now
> cover replans-until-pass, replan-budget exhaustion, mixed repair→replan,
> adaptive role preconditions, and parser budget wiring.

- Close surfaced high-ROI gaps from the Session F review before / while landing adaptive mode:
  - remove duplicated mode enumerations so parser choices read from the canonical `_WORKFLOW_MODES`;
  - freeze an explicit adaptive test matrix before broadening the controller (repair→replan, replan budget exhaustion, planner absence, plan-version bumping);
  - make `replan_round` and `active_plan_version` semantically real rather than decorative once planner re-entry lands;
  - keep operator-visible terminal reasons aligned with persisted `FlowState.last_transition_reason`;
  - clarify/document the current-vs-target mode surface so the conceptual two-axis model does not outrun the shipped CLI;
  - add a glossary entry for `FlowState` once it becomes operator-facing in docs;
  - decide/document ordering semantics for non-canonical role lists in `repair` / `adaptive` modes instead of leaving them implicit.

### Session H — Review pass / hardening / subtraction pass

- Look for redundant artefacts or overgrowth.
- Re-evaluate whether a separate replanner prompt is still necessary.
- Add only the highest-value deferred pieces.

> **Integration note (2026-06-30):** the useful outputs of the Session-H review
> were folded back into this plan (deferred-items register, controlled future
> work, residual debt framing) and into the operator/maintainer memo. The
> standalone Session-H review note need not be kept in the repository if the
> plan + memo pair remains current.

### 7.1 Deferred items register + unblock factors

This section exists to keep deferred work explicit and audit-friendly. Every item
must have an unblock factor so future sessions do not re-derive why it is still
deferred.

| Item | Current state | Why deferred | Unblock factor | Earliest sensible phase |
|------|---------------|--------------|----------------|-------------------------|
| Dedicated replanner prompt | Deferred | Current planner contract is still sufficient; extra prompt surface would add maintenance and drift risk | Repeated evidence that delta replans are too verbose / unreliable / token-wasteful under the unified planner prompt | Session H+ only after real usage evidence |
| Full mid-loop read-driven transitions from persisted FlowState | Partially landed | Controller truth exists, but resume/re-entry semantics are not yet driven from persisted state alone | Need a concrete resume/inspect use-case and a deterministic transition policy that reads `flow_state.json` as primary state instead of in-memory progression | Post-Session H |
| Separate plan identity from `run_id` | Deferred bootstrap simplification | `active_plan_id=run_id` is adequate while only plan versioning matters operationally | Need either multi-plan-per-run semantics, plan lineage inspection, or user-visible plan identity | Post-Session H |
| Structured execution-evidence artifact | Transitional prompt-only discipline | Eval/FlowState were higher ROI first; execution evidence is not yet consumed by the controller | Need a consumer: either eval automation, workflow inspection, or regression triage that reads evidence mechanically | Post-Session H |
| Gate-density axis (`phase-gated` / `step-gated`) | Conceptual only | No concrete high-risk workflow selected yet; adding it now would broaden controller complexity prematurely | A selected use-case where phase boundaries are too coarse and per-step eval changes outcomes materially | Post-v0.1 / explicit operator need |
| `workflow status` / `workflow inspect` command | Deferred | Useful, but not necessary to land orchestration correctness first | Real operator pain reading `flow_state.json`/`eval_report.json` directly, or repeated debugging friction across sessions | Post-Session H |
| Broader eval finding taxonomy (`security`, `docs`, `verification`, etc.) | Intentionally narrow | Core route semantics needed to stabilize first | Repeated findings that cannot be represented cleanly by current classes and materially affect routing or audits | Post-Session H |
| Non-terminal `SUSPENDED` / `NEEDS_FOLLOWUP` state | Deferred | Speculative until real workflow runs show a stable need | Repeated terminal outcomes that are neither `FAILED` nor actionable `REPLAN_REQUIRED`/`REPAIR_REQUIRED`, plus an operator workflow that uses the distinction | Post-Session H |
| Parallel coders/evaluators / debate loops / micro-cycles | Explicit non-goal | Would violate subtraction-first and broaden the controller before single-threaded semantics are exhausted | Strong empirical evidence that linear/repair/adaptive controller is insufficient on target tasks | Out of first wave |
| Full Russian CLI/help lint policy (`RUF001`) resolution | Deferred hardening | Current semantics work; lint policy for Cyrillic strings should be solved coherently, not via ad hoc suppressions | Decide whether Russian help text is exempted/configured centrally or normalized in wording across files | Session H / repo-wide cleanup |

## 8. Verification strategy per phase

- **Phase 1:** doc links + llms index + coherence review.
- **Phase 1.5:** source-of-truth table present, temporary physical model explicit, no unresolved owner ambiguity.
- **Phase 2:** prompt render tests, prompt-source sync review, targeted role tests if present.
- **Phase 3:** schema tests, Eval-report persistence tests, verdict/route parsing tests.
- **Phase 4:** FlowState persistence tests, resume tests, transition-audit field tests.
- **Phase 5:** CLI parser tests + repair-loop controller tests + bounded retry assertions.
- **Phase 6/7:** full pytest relevant scope + docs + regression against earlier linear workflow behavior.

## 9. Risks and caveats

- **Over-design risk:** introducing too many separate artefacts at once could outpace what the runtime actually needs. Mitigation: Phase 3 defines the logical model first and chooses the smallest physical representation that preserves semantics.
- **Prompt drift risk:** changing prompt files and `src/fa/inner_loop/prompt.py` copies can diverge. Mitigation: update both in the same session and keep tests / diff review tight.
- **Controller complexity risk:** adaptive workflow could become hard to debug if landed before structured eval outputs. Mitigation: do Eval artefacts first, controller second.
- **Prompt-surface bloat risk:** adding a separate replanner prompt too early may increase maintenance without real quality lift. Mitigation: defer behind explicit trigger conditions.

## 10. Round-check of the whole plan

### What this plan gets right

- It respects subtraction-first by not forking the planner prompt immediately.
- It sequences work from semantics → prompts → artefacts → controller, which matches the actual dependency graph.
- It preserves a working linear baseline while building toward adaptive semantics.
- It identifies the true leverage point (structured eval outputs) rather than over-indexing on planner cleverness.

### What could still go wrong

1. **Storage shape indecision** could stall Phase 3. To avoid this, pick a temporary representation quickly (even if embedded in existing artefacts) as long as the schema is explicit.
2. **Eval schema too ambitious** could delay controller work. Keep v1 minimal: verdict, findings, route decision, step results.
3. **Prompt edits without tests** could create silent regressions. Every prompt-contract session must include at least deterministic render / sync verification.
4. **Adaptive mode before clear docs** could confuse users. Docs must make clear which workflow modes are MVP, experimental, or future.

### Improvement options discovered during the check

- Add a small glossary entry or docs phrase for `FlowState` once the term enters active use in user-facing docs.
- Consider a future dedicated `workflow status` or `workflow inspect` command after FlowState lands, but do **not** add it in the first implementation wave.
- If `fa help --json` remains the WebUI contract, extend it later with workflow-mode metadata rather than inventing a second help registry.
- Add a non-terminal `SUSPENDED` / `NEEDS_FOLLOWUP` state only if real workflow runs show a stable need for it; do not introduce it speculatively.

## 10.1 Explicit non-goals for the first implementation wave

The following are consciously deferred and should not be smuggled into the early patches:

- parallel coders or parallel evaluators
- multi-evaluator debate loops
- planner/eval alternating micro-cycles after every tiny step
- human-approval state machines beyond the existing project constraints
- a dedicated replanner prompt before evidence justifies it
- step-gated default mode
- a large explosion of new artifact files before the temporary physical model proves insufficient

## 11. Files used

- `knowledge/prompts/architect-fa.md`
- `knowledge/prompts/architect-fa-compact.md`
- `src/fa/inner_loop/prompt.py`
- `knowledge/research/cli-ergonomics-design-2026-06-29.md`
- `https://developers.googleblog.com/developers-guide-to-multi-agent-patterns-in-adk/`
- `https://arxiv.org/html/2605.18747v1`
- `https://arxiv.org/html/2510.03902`

## 12. Out of scope

- Full code implementation in this note.
- ADR text for any new normative contract.
- Immediate addition of a dedicated replanner prompt.
- Parallel / multi-coder orchestration.
- Human-in-the-loop approval workflow beyond the existing system constraints.
