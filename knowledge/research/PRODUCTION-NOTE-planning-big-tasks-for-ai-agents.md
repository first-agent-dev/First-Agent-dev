# Planning Big Tasks for AI Agents — Research Note

**What this is.** Research context for one job: deciding exactly how to implement the
planning system described in §2. The note covers what the literature says about planning,
verification, context, and control for long-horizon agent work, and turns each finding into
concrete mechanisms for that system. It is written to be read alone: the system spec is
embedded in §2, so no other document is required.

**Conventions.**

- arXiv IDs appear in parentheses after each claim. Every ID in this note resolves against
  the arXiv API with a matching title.
- Evidence grades: **A** = causal ablation or large-N benchmark that tests the mechanism
  directly; **B** = verified mechanism from a single system, or convergence of several
  sources; **C** = survey-mediated or extrapolated — adopt, but watch the telemetry.
- The implementation ideas in §7 each state: what it is, how it works, the evidence,
  what changes in the system, and the cost.

**How to read this note.** §3 is the findings — what the field knows, and what each fact
means for the system. §4 is the detailed paper notes, organized by research thread. §5 is
what the evidence says about the six locked decisions plus the open dial. §6 lists the
distilled principles. §7 is the implementation backlog, ordered by leverage over cost —
this is the section an implementation plan will draw from; it ends with the options that
were considered and not adopted, and why. §8 is the frontier benchmark numbers (goalposts)
for judging whether the system is doing well. §9 is the honest caveats. §10 maps the
load-bearing claims to their sources and how firmly each was checked. §11 is the full
reference list.

---

## 2. The system (spec, condensed)

This section is the ground truth the research is grounded in. It condenses the design doc
"Planning topology explained" (feature → increment → `SLICE#` → `STEP#`).

### 2.1 The problem and the four levels

Nobody builds "user authentication" in one sitting. It is too big to hold in one head — and
for an agent it is worse, because the context window is finite and stateless. The universal
answer is decomposition, done at exactly four levels:

| Level | What it is | The size test | Who executes it |
|---|---|---|---|
| **Feature** | the whole goal | "Can I describe it in one sentence?" | nobody — it is the destination |
| **Increment** | a **shippable** piece of the feature | "Could I merge this and stop, and still have something that works?" | one workflow **run** |
| **Slice** (`SLICE#`) | one **commit**: a coherent change with its own proof | "Is this one reviewable diff with a passing test?" | one coder→verify→eval turn |
| **Step** (`STEP#`) | one **atomic action** inside a slice | "Is this one edit a human could check off?" | the coder, within the slice |

The slice is the hinge of the whole system, for two reasons:

- it carries the **contracts** (`CT#`) — the acceptance criteria it must satisfy;
- it carries a **`verify` block** — the commands that prove it works (an exit code).

A slice is the smallest thing the harness can declare **done by itself**, without asking
anyone's opinion. That is the fact-versus-judgment split from the eval design, appearing at
planning level: the verify exit code is a fact; the eval verdict is a judgment.

### 2.2 Rolling wave: detail the near-term, outline the far-term

Plan the increment being built **now** in full detail (slices, contracts, verify blocks,
steps). Keep later increments as one-line outlines. Re-plan the next increment when you
reach it, with the previous increment's lessons in hand.

Why: detail goes stale. The worked example — while building I1 (sign-in), you discover the
`users` table needs a `password_hash` column (bcrypt) and a `created_at` timestamp. That
fact changes I2 (sign-up): sign-up must now write that exact schema. If I2's detailed steps
had been written before building I1, they are now wrong. So you plan the right horizon in
detail and keep the rest as a map. The ADR log already is the far-term outline: durable
decisions and direction ("we use bcrypt", "sessions are cookies, not JWT").

Where the staleness line sits: at the **increment** boundary, not the slice boundary.
Inside one small increment (4–7 slices, planned just now, against code just read), the steps
are accurate enough to write up front.

### 2.3 Who writes what

| Artifact | Written by | When | Detail |
|---|---|---|---|
| **Roadmap** (increments, order, ADR-level decisions) | **planner** (with the human) | once per feature, refined as it goes | outline |
| **Increment plan** (slices + contracts + verify + **steps**) | **planner** | just-in-time, when the increment's run starts | **full** |
| **Tracker** (contract statuses, step checkboxes) | **harness (code)** | continuously, during the run | mechanical |
| **The code** | **coder** | per slice | — |
| **The verdict** | **eval** | per slice | — |

**The planner does the heavy lifting** — roadmap, increments, slices, and steps. The coder
*executes* the steps within firm contracts. It may adapt a trivial detail when reality
differs (anchored by the contracts); major drift is a `REPLAN` back to the planner. Three
reasons the planner, not the coder, writes the steps:

1. **A plan you can read before it runs is the whole point.** The planning skills exist to
   produce a reviewable artifact. If the coder improvises steps live, there is nothing to
   audit before work happens.
2. **The coder should not design its own contract.** That is the self-grading problem one
   level up. The planner sets the acceptance; the coder meets it.
3. **The harness parses the steps to track them.** Steps in the plan are boxes the harness
   can tick. Steps improvised in a model's head are nothing to track.

### 2.4 Two files, one source of truth

**File 1 — the roadmap** (one per feature; the stable map). Shallow: it lists the
increments and the durable decisions, and is refined as reality teaches.

```markdown
# ROADMAP: User Authentication          Roadmap-ID: RM-auth
Status: IN PROGRESS

## Increments
- [ ] I1  Sign in            (RM-auth-I1)   ← current
- [ ] I2  Sign up            (RM-auth-I2)   outline only
- [ ] I3  Password reset     (RM-auth-I3)   outline only
- [ ] I4  Sessions & logout  (RM-auth-I4)   outline only

## Standing decisions (ADR-level)
- passwords: bcrypt, cost 12
- sessions: http-only cookie, not JWT
```

**File 2 — the increment plan** (one per run; the detailed instructions). Grammar:

```markdown
# INCREMENT I1: Sign in                 Increment-ID: RM-auth-I1
Status: READY        slices: 4

## SLICE1: the login form
INTENT: a user can enter email + password and submit.
CONTRACTS: CT1 (form posts to /login), CT2 (no password in URL)
```verify
uv run pytest tests/test_login_form.py -q
```
STEPS:
- [ ] STEP1: add LoginForm component, wire onSubmit → POST /login
- [ ] STEP2: client-side required-field validation

## SLICE2: the POST /login endpoint
INTENT: verify credentials and start a session.
CONTRACTS:
  CT3: unknown email and wrong password return an IDENTICAL 401 (no user enumeration)
  CT4: the password is never logged
```verify
uv run pytest tests/test_login_endpoint.py -q
```
STEPS:
- [ ] STEP1: add route skeleton, wire into the router (exit: route resolves)
- [ ] STEP2: parse + validate the request body (exit: malformed → 400)
- [ ] STEP3: look up user by email (exit: unknown → 401, same shape as CT3)
- [ ] STEP4: call verify_password (exit: wrong → 401)
- [ ] STEP5: on success, hand off to SLICE4's session issuance (exit: 200 + cookie)
```

The slice brief is a **view** — one section of the increment plan — not a separate file
that can drift out of sync. The harness parses the plan in code: a pure extractor
(`plan_ids.py`) already pulls slices and verify commands out of a plan; it grows two small
accessors — `plan.slices`, `plan.commands_for("SLICE2")`, and `plan.section("SLICE2")`
(the slice's text block, which becomes the coder's scoped brief).

What this gives every consumer:

- **The human** can read SLICE2 and audit it before any code is written.
- **The coder** gets *only* SLICE2 — the harness scopes its context to that section. A
  tight instruction, not the whole feature.
- **The harness** parses `SLICE2`, its `CT3/CT4`, its `verify` command, and its `STEP#`
  boxes; it runs the command and ticks the boxes from the result.
- **The eval** gets SLICE2's diff + `CT3/CT4` + the verify output. Scoped, no prose heap.

### 2.5 Run shape: the code-owned controller

```
CHAT (orchestrator)
  "Next shippable increment is I1: sign in."  → kicks off a workflow run
        │
        ▼
PLANNER  (runs ONCE for this run)
  writes  plans/RM-auth-I1.md  — SLICE1..4, each with CT#, ```verify, STEP#
        │
        ▼
┌─────────────────── the controller loops, in code, no LLM deciding ───────────────────┐
│  for SLICE# in [SLICE1, SLICE2, SLICE3, SLICE4]:                                       │
│     CODER    implements SLICE# from its scoped brief (its STEP#s), commits             │
│     HARNESS  runs SLICE#'s ```verify command → exit code        [FACT]                 │
│     EVAL     reviews SLICE#'s small diff vs its CT#             [JUDGMENT]             │
│     GATE     exit≠0 or verdict=REPAIR → re-run coder on THIS slice (budgeted)          │
│              verify flaky → surface, halt for the human                                │
│              pass → HARNESS ticks SLICE#'s STEP# boxes, flips its CT# → VERIFIED       │
└────────────────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
HARNESS  composes the PR from the tracker (all CT# VERIFIED)        [CODE]
        │
        ▼
CHAT (finisher)  ships I1, marks it done on the roadmap, picks I2 → next run
```

Read the cost: the **planner runs once**; the only per-slice LLM calls are **coder +
eval**; the **controller (code)** drives the loop and ticks the tracker. The roadmap (I2,
I3, I4) is closed by the **chat role** starting a new run per increment — each planned
just-in-time, on the previous increment's shipped base. If the whole feature is small
(4–7 slices total), the roadmap has one increment, and one run closes it: the tiers
collapse gracefully, so you do not pay for structure you do not need.

### 2.6 The locked decisions and the open dial

Six decisions are locked:

1. **Four tiers:** feature → increment (one run, shippable) → `SLICE#` (one commit,
   contracts + verify) → `STEP#` (one atomic action).
2. **Rolling wave:** full detail for the current increment; one-line outline for later
   increments. Staleness is managed at the increment boundary. The ADRs are the far-term
   outline.
3. **Planner does the heavy lifting:** roadmap, increment plan, slices, and steps —
   just-in-time per increment. The coder executes steps within firm contracts; it does not
   author them.
4. **Two files:** one shallow roadmap, one detailed increment plan. The slice brief is a
   section (a view), not a separate document.
5. **Naming:** `SLICE#` for the commit-sized unit, `STEP#` for the atomic action, so the
   anchors are unambiguous and machine-parseable.
6. **Run shape:** planner once → controller-driven per-slice loop (coder→verify→eval→
   gate→tick) → PR → chat ships and picks the next increment.

One question is left open on purpose: **how much step detail the planner writes per slice**
(terse checkboxes versus full edit-packets). It is a dial, not a fork — it can be tuned per
slice complexity once the structure exists. §5.7 gives the evidence and a recommended
default rule for the dial.

---
## 3. Findings — what the field knows, and what it means for this system

Twelve findings carry the rest of this note. Each states the fact, the mechanism behind
it, the key numbers, and the consequence for the system.

### F1. The harness, not the model, is the binding constraint

With the model held fixed, changing the wrapping harness (the loop structure and what is
carried between iterations) moves hard benchmarks by up to 15 points (2608.23953). StateM
reached 95.3% on Terminal-Bench 2.1 through harness engineering alone (2608.15089) — the
clearest single demonstration that harness work, not model work, moved a hard benchmark.
The dominant 2026 survey (Horizon Gap, 2608.06663, 1,547 papers) finds one unified pattern
across planning, memory, execution, training, and evaluation: **outcome-only signals stop
carrying information as horizons lengthen, and the field's response is to manufacture
denser step-level signal.** The per-slice `verify` blocks in this system *are* dense
step-level signal — the design sits at the field's center of gravity.

**For the system:** invest in the controller, the gates, and the evidence channels.
Model upgrades are the secondary lever.

### F2. Wrapping an existing coder in a plan→code→test loop with carried evidence is the best-validated intervention for big tasks

Harness-of-Harness (HoH, 2609.01481) wraps an existing coding-agent harness instead of
replacing it. Each iteration does three things: it re-plans the remaining work, it feeds
the execution evidence from the last iteration into that re-plan, and it warm-starts from
the current artifact. Numbers: +52.25% average relative gain across 3 harness×model pairs,
persisting over 10 iterations (22% → 72.7% on FrontierSWE); a 70-loop multi-day run built a
playable game from a PRD. Ablations show all three ingredients are essential: dropping the
evidence-feeding costs 6.28 points; freezing the plan (no re-planning) costs 8.1 points.
The gain is not explained by extra tokens — it is the loop structure, not the compute.

**Mechanism detail:** the wrapper keeps the inner coder harness untouched. Around it, a
second loop collects, after each iteration, a compact evidence summary (what was tried,
what failed, what changed) and appends it to the next planning call, along with the
artifact's current state. The planner sees *outcomes*, not transcripts.

**For the system:** the run shape in §2.5 is exactly this pattern — planner once per
increment, per-slice loop with the eval verdict and verify output feeding back. The
EVIDENCE ledger (§7 item 4) is the evidence-carrying channel, and the plan must stay
living (§7 item 9), never frozen mid-increment.

### F3. Long-horizon failure is mostly an execution problem, and the dominant execution poison is self-conditioning

The per-step error rate *rises* when the model's own prior errors are in context. Scaling
the model does not fix it. Thinking models and *removing error-laden history* do
(2509.09677). Published systems already act on this: Magentic-One "force[s] all agents to
clear their contexts and reset their states after each plan update" (2411.04468, verbatim).
The long-context numbers are harsh: 1M–2M-token-window models degrade by more than 50%
already at ~100K tokens (2512.02445); injecting irrelevant history (25K–150K tokens) drops
web-agent success from 40–50% to under 10%, and the failures are dominated by two named
modes — *getting stuck in loops* and *losing track of the original objective*
(2512.04307). Those two modes are exactly what a stall counter and objective re-injection
counter.

**For the system:** fresh, scoped context per work unit is the core reliability
mechanism — the "coder gets only its `SLICE#`" design is directly validated. Retry
contexts must be distilled (structured failure packets, §7 item 6), never raw transcripts.
On replan, contexts are cleared and reset, not appended to (§7 item 2).

### F4. Plan quality dominates execution quality

An untrained executor with an excellent dynamic plan scores 34 points higher than the same
executor with a poor plan (2503.09572). Scaling the planner capacity moves results about
as much as scaling the whole system (2605.02168). More executor training data moves about
nothing, relative to plan quality (2503.09572).

The strongest concrete instance is **VeriMAP** (2510.17109). Its mechanism: the planner
decomposes the task, models the dependencies between subtasks, and writes each subtask's
passing criteria *as Python verification functions*. The executors then work on one
subtask at a time and never see the global task; handoffs use structured, named inputs and
outputs. Result: +4.05% on BigCodeBench-Hard and +9.8% on Olympiad benchmarks versus the
next-best ReAct baseline, and the setup enables iterative refinement without any external
labels — because the verification functions are executable.

**For the system:** spend the best model and the most careful prompts on the planning
role. The planner's authorship extends beyond prose: it extends to the *test files*
(§7 item 1).

### F5. LLMs cannot guarantee plan correctness and cannot reliably self-critique — correctness must come from external deterministic verifiers, and the verifiers must be hardened and evolved

The numbers: on formal planning domains, only about 12% of the plans the best LLM (GPT-4)
generates are actually executable and goal-reaching (2402.01817, verbatim); obfuscated
domain names collapse the figure further, for every model tested (details in §4A).
Self-critique can be *worse* than no critique, because the model fails to recognize its
own correct solutions (2310.01798). And reasoning models do not fix the justification
problem: o1 "gaslights" — creative but nonsensical justifications for wrong plans
(2409.13373).

The constructive pattern is **LLM-Modulo** (2206.10498 and its companion 2402.01817): the
LLM generates and reformulates, while soundness is inherited from external critics —
*hard* critics (executable, model-based, deterministic) and *soft* critics (LLM judgment)
— with a plain-code controller that compiles the critiques into the next prompt. This
system's fact(verify exit code)/judgment(eval) split is exactly that hard/soft split.

Two 2026 results sharpen the defensive posture. First, agents reward-hack: on
Hack-Verifiable Terminal Bench (2608.22103), agents "satisfy a task's checks while
violating its intent," and prompting mitigates known hacks but not unknown ones. Second, a
frozen verifier is a ceiling: ASL (2510.14253) states in its abstract, verbatim, that
"GRM verification capacity is the main bottleneck: if frozen, it induces reward hacking
and stalls progress," and that continual verifier training on the evolving data
distribution mitigates it and "raises the performance ceiling."

**For the system:** never let "let the model reflect on the diff" replace a test. The eval
rubric and the constraint tests are *living* artifacts, revised in the harness telemetry
loop (§7 item 17). The eval sits on a different model family than the coder, blind to
authorship (§7 item 8).

### F6. Decomposition should be scoped-context and DAG-shaped, with replanning confined to the failed node — and the plan-first economics are now measured

TDP (2601.07577) structures the plan as a DAG. Each node gets its own scoped context.
When a node fails, only that node is re-planned — the rest of the plan is untouched — and
facts discovered at one node propagate to the specs of downstream nodes ("Self-Revision").
Result: up to 82% fewer output tokens versus a global-replanning Plan-and-Act baseline, at
equal or better accuracy. The Horizon Gap survey independently reports full-horizon
planning with on-demand replanning *matching* interleaved step-by-step accuracy at 2–3×
fewer tokens, for well-specified tasks (2608.06663 §3, survey-mediated; consistent with
TDP's primary-source number).

For parallel branches, the published isolation mechanism is the **git worktree**: a
private working directory, index, and branch per agent, sharing one object store. The
SDD-for-Agentic-SE paper calls it "the cornerstone for parallel agentic work during 2026"
(2609.00252, verbatim). One caution: worktrees isolate *code*, not *processes* — runtime
isolation (ports, databases, temp dirs) must be arranged per worktree separately.

**For the system:** slice DAG with `DEPS:` tags and worktree-isolated parallel slices
(§7 item 11); within-increment fact propagation via scoped spec-refinement instead of full
replans (§7 item 9).

### F7. Slice sizing has an empirical basis — and failure handling, not just size, is the cliff

SWE-bench Live (2505.23419, verbatim): a single-file patch that changes fewer than five
lines is solved almost one time in two (48%). Once the patch edits three or more files, or
spans more than one hundred lines, the success rate falls below ten percent. Patches that
touch seven or more files are never solved. METR (2503.14499): the length of completable
tasks doubles approximately every seven months, and each "messiness" factor (ambiguous
spec, messy repo, unclear acceptance) costs about 8.1 points of success — planning
artifacts that remove messiness literally buy success probability. PlanBench-XL
(2606.22388): GPT-5.4 scores 51.90% on 327 tool-use tasks when nothing blocks, but
collapses to 11.36% when tools fail, miss, or distract. The paper's own words: agents are
"especially vulnerable when failures lack explicit error signals or when recovery
requires longer alternative tool-use paths."

**For the system:** 4–7 slices per increment is the sizing prior. Sizing rules must
include *recovery path length* — how long the alternate route is when a step fails. And
gates must emit explicit, structured failure signals, not bare exit codes (§7 items 2, 6,
10).

### F8. Verification must be multi-level, baseline-aware, planner-authored, and non-vacuous

MAST (2503.13657, 1,600+ traces): adding one high-level objective check to the loop gave
+15.6 points — the largest design-only intervention measured there. Agentless validates
its reproduction tests by requiring fail-before/pass-after: a test that does not fail on
the broken state is discarded (2407.01489). Phoenix takes a baseline first, because 10 of
11 real repos have pre-existing test failures — without a baseline you cannot attribute
which failure is yours (2606.20243).

The hard number for "tests pass ≠ accepted": **SWE-Gate** (2609.04167). It built 303
repo-level instances with *separate* functional tests and review-constraint tests, the
constraints derived from real PR review comments. Of 644 patches that passed the
functional tests, 221 (34.3%) violated the acceptance constraints. The constraint classes
in the wild: backward compatibility, error-shape identity, convention compliance,
no-new-dependencies, API shape.

The unifying design principle is named in SDD-for-Agentic-SE (2609.00252, verbatim):
**"a constraint that no tool can enforce is a wish rather than a constraint."** The same
paper establishes that acceptance criteria are testable — Given–When–Then is the canonical
form, and Gherkin scenarios are validated as the requirements-to-code bridge.

**For the system:** the `CT#` grammar currently does not distinguish constraint classes,
and the gates currently cannot fail on them. In this system's own worked example, CT3
("IDENTICAL 401 for unknown email vs wrong password") is currently a *wish* — nothing in
the plan guarantees a test exists for it. The fix: contracts get classes
(FUNCTIONAL / CONSTRAINT / PRESERVATION), the planner authors the test file, and the
harness proves non-vacuity (§7 item 1).

### F9. Plans must be living, evidence-fed artifacts — and the controller needs a stall counter

Dynamic replanning beat static planning by 10.3 points; facts carried in the plan double
as memory (2503.09572). Freezing the plan cost HoH 8.1 points (2609.01481). AdaPlanner
formalizes the policy split: refine *within* the plan when possible, revise *the plan
itself* only when the plan is wrong (2305.16653).

The missing published detail in this system's gate is Magentic-One's **stall counter**
(2411.04468): the orchestrator keeps a counter for how long the team has been stuck,
increments it on a detected loop or a lack of forward progress, keeps going while the
counter is at most 2, and on breach runs reflection → task-ledger update → revised plan →
fresh inner loop with **all contexts cleared**. The task ledger has four categories —
*given or verified facts*, *facts to look up*, *facts to derive*, and *educated guesses*,
the last required to be "expressed in a guarded or qualified manner." The full two-loop
controller mechanics (the design to imitate) are in §4C.

**For the system:** this system's "verify flaky → surface, halt" is the manual version of
this mechanism. Automate it: stall counting, ledger-grounded reflection, and forced
context reset become first-class controller states, not human reflexes (§7 item 2). The
four ledger categories become the entry grammar of the EVIDENCE ledger (§7 item 4).

### F10. Context management is a first-class capability — compaction is a governance hazard, and layout is measurable

Context-folding (2510.11967): the agent branches into a sub-trajectory for a subtask and
folds it back on completion, collapsing the intermediate steps into a summary. A 36B model
with a 32K active window beat its *own* 327K-window ReAct configuration. Two cautions:
folding summaries must retain fine-grained constraints, or the folded-away detail is lost
forever (2601.18285); and compaction silently evicts standing policies — the agents obey
rules while they are visible in context, and stop obeying them once compaction removes
them (2606.22528). Fix: pin ADRs and invariants outside the compactable channel and
re-inject them into every role prompt at every invocation.

Layout is measurable, from SWE-agent's interface ablations (2405.15793, Table 3): the
100-line file-viewer window is the best configuration; a 30-line window and the whole
file both cost points; keeping only the last 5 observations beats carrying the full
history (stale observations actively hurt); removing the structured edit command costs
7.7 points — guard-railed edits suppress cascading errors. And position matters:
information in the middle of the context is used worst (Lost-in-the-Middle,
2307.03172) — contracts at the top of the brief, recap at the bottom. The full numbers
are in the §4B table. LOCA-bench (2602.07962) confirms the recovery side: success decays
with controlled context growth, and context-management strategies (pruning stale outputs,
memory tools) recover much of it.

**For the system:** the slice run is a fold; retry contexts are distilled, not raw;
governance is pinned and re-injected (§7 item 7); the brief has a measured layout
contract (§7 item 6).

### F11. Contracts must be executable, planner-authored, and class-typed

The published system closest to this design (VeriMAP, 2510.17109) has the *planner* write
the verification code. SWE-Gate (2609.04167) proves functional tests alone leave a 34.3%
false-accept rate against review-derived constraints. SDD (2609.00252) names the
principle (wishes versus constraints). Constitutional SDD (2602.02584) applies it to
security — constraints enforced by construction at plan time, which is precisely this
system's CT3/CT4 class of contract. AgentCoder (2312.13010) established test authorship
independent of implementation (96.3% HumanEval with an independent test-designer model).

In this topology the mechanism is concrete: **the planner writes each slice's test file;
the `verify` block points at it; the harness proves non-vacuity by requiring
fail-before/pass-after against the pre-slice baseline.** Contract and proof become one
artifact, and authorship/acceptance separation is preserved in its strongest form — the
coder never writes its own acceptance.

**For the system:** this is the single highest-value upgrade available (§7 item 1).

### F12. "Great results" is consistency under failure injection, not one green run

τ-bench (2406.12045): gpt-4o scores 61.2% pass@1 on the retail domain, but pass^8 — eight
consecutive successes on the same task — is under 25%. One green run is a sample, not a
result. The goalpost table (§8) has the full picture: PlanBench-XL collapses under
blocking, PaperBench still sits below human PhDs on open-ended work, and SWE-bench Pro
(best ~23%, as-reported) versus SWE-bench Verified (leaderboard high-70s/80s) shows the
function-level gap nearly closed while the acceptance-level gap is not.

**For the system:** in the tracker, VERIFIED means *pass^k* for stochastic gates (eval
verdicts, flaky-prone verifies), and k=1 for deterministic tests — where the exit code
already gives the guarantee for free. The system-level metric is pass^k over a held-out
slice-regression set, never one green feature (§7 item 12, §8).

---

## 4. Evidence by thread

Detailed notes on the papers, organized by thread. The research map shows which paper
answers which question; the per-thread sections give the mechanisms and numbers.

| Thread | Question | Key papers |
|---|---|---|
| A. Planning capability & limits | Can LLMs plan/verify plans autonomously? | 2402.01817, 2409.13373, 2206.10498, 2310.01798, 2304.11477 (LLM+P), 2311.05772 (ADaPT), 2502.11221 (PlanGenLLMs survey) |
| B. Long-horizon execution & context | Why do agents fail as tasks get long? | 2503.14499 (METR), 2509.09677, 2510.11967, 2601.18285, 2512.22733, 2512.02445, 2512.04307, 2602.07962 (LOCA), 2307.03172 (Lost-in-Middle), 2405.15793 (ACI ablations) |
| C. Plan–execute separation | Who plans, who acts, where to spend compute? | 2503.09572, 2605.02168, 2601.07577 (TDP), 2305.16653 (AdaPlanner), 2312.04511 (LLMCompiler), 2305.18323 (ReWOO), 2411.04468 (Magentic-One), 2510.17109 (VeriMAP), 2504.16563 (GoalAct), 2608.06663 (Horizon Gap §3) |
| D. Big-task coding systems & frontier | What do working systems look like; what's the frontier? | 2609.01481 (HoH), 2407.01489 (Agentless), 2606.20243 (Phoenix), 2403.17927 (Magis), 2507.06229 (Agent KB), 2405.15793 (SWE-agent), 2312.13010 (AgentCoder), 2505.23419 (SWE-bench Live), 2412.14161 (TheAgentCompany), 2506.17208 (Dissecting), 2608.15089 (StateM), 2509.16941 (SWE-bench Pro), 2606.22388 (PlanBench-XL), 2601.11868 (Terminal-Bench), 2607.08964 (LH-Terminal-Bench), 2502.12115 (SWE-Lancer) |
| E. Verification & feedback | What makes gates trustworthy? | 2402.01817, 2303.11366 (Reflexion), 2305.11738 (CRITIC), 2305.20050 (PRM), 2312.08935 (Math-Shepherd), 2605.10325 (VPR), 2605.20061, 2310.01798, 2503.13657 (MAST), 2609.04167 (SWE-Gate), 2510.17109 (VeriMAP), 2406.12045 (τ-bench), 2608.22103 (HVTB), 2510.14253 (ASL), 2410.21819 (self-preference) |
| F. Memory, context, reuse | How to survive long runs & learn across runs? | 2310.08560, 2409.07429 (AWM), 2305.16291 (Voyager), 2308.10144 (ExpeL), 2504.07079 (SkillWeaver), 2606.22528 (Governance Decay), 2304.03442 (Generative Agents), 2406.02818, 2507.13334, 2608.06663 §4 |
| G. Multi-agent failure modes | What breaks role systems? | 2503.13657 (MAST), 2506.17208 (Dissecting), 2308.00352 (MetaGPT), 2402.05120 (More Agents) |
| H. Harness architecture & spec-driven development | What is the harness layer converging on? | 2605.18747 (survey), 2608.23953 (Empire), 2606.06324 (HarnessFix), 2410.10762 (AFlow), 2609.00252 (SDD), 2604.05278 (Spec Kit), 2608.20341 (SDAD), 2602.00180, 2602.02584 (Constitutional SDD), 2608.25202 (SpecMine), 2603.25697 (Kitchen Loop) |
| I. Ambiguity & clarification | When should agents ask? | 2507.21285, 2605.09698 (Ambig-DS), 2605.17324 (ASPI), 2505.11814 (ChatHTN), 2411.04468 (facts/guesses ledger) |
| J. Cost & model allocation | Where to spend which model? | 2305.05176 (FrugalGPT), 2402.05120 (More Agents), 2410.21819 (self-preference), 2503.14499 (METR cost headroom) |

### A. What LLMs can and cannot do in planning

Vanilla LLM plans are about 12% executable on IPC-style planning domains; obfuscated
domain names collapse GPT-4 below 5% — the model is retrieving familiar plans
approximately, not planning (2402.01817, 2206.10498). Self-critique is unreliable
(2310.01798). o1-preview: 97.8% on small Blocksworld, 52.8% obfuscated, 23.6% at 20–40
steps, with "creative but nonsensical" justifications when wrong (2409.13373).

Two constructive lines push in this system's direction. **LLM+P** (2304.11477): the LLM
translates the task to PDDL, a sound classical planner solves it, and the output is
translated back — the soundness-critical step lives outside the model. **ADaPT**
(2311.05772): decompose *as needed* — recurse only when the executor fails, not eagerly.
The surveys (PlanGenLLMs 2502.11221; 2505.19683; 2502.12435) classify hierarchical
decomposition plus external verification as the field's default architecture.

**Architectural insight:** treat every plan as a hypothesis; its value is proportional to
how much of it is machine-checkable. Grounding is existential — plans written against the
actual repository behave like solvable Blocksworld; plans written from memory behave like
the obfuscated version.

### B. Long-horizon execution: compounding, self-conditioning, context

The compounding law: task success ≈ p/(1−p) per-step reliability — small per-step error
rates compound into long-horizon collapse (2509.09677). Each messiness factor costs about
8.1 points (2503.14499). The named long-context results, in one place:

| Phenomenon | Number | Source |
|---|---|---|
| Window size lies: 1M–2M-token models degrade | >50% drop already at ~100K tokens | 2512.02445 |
| Noisy history is poison | web-agent success 40–50% → <10% with 25K–150K irrelevant tokens; failures = loops + lost objective | 2512.04307 |
| Layout: file-viewer window | 100 lines = 18.0% (best); 30 lines −3.7pp; full file −5.3pp | 2405.15793 |
| Layout: observation history | last-5 = 18.0%; full history = 15.0% | 2405.15793 |
| Layout: structured edit command | removing it −7.7pp (18.0 → 10.3) | 2405.15793 |
| Layout: position | U-shaped — middle of context used worst | 2307.03172 |
| Recovery is real | pruning stale outputs + memory tools recover much of the decay | 2602.07962 |

**Architectural insight:** the slice run is a fold. Retry contexts must be distilled, not
raw. Standing decisions are pinned and re-injected. The brief has a layout contract:
`CT#` first, `INTENT` second, `STEPS` third, recap of prior-slice outcomes last; file
views windowed to about 100 lines; stale observations collapsed; the objective restated
at the bottom, where attention is strongest.

### C. Plan–execute separation: the strongest cross-domain consensus

| System | What it contributes | Numbers |
|---|---|---|
| Plan-and-Act (2503.09572) | plan/exec separation; dynamic replan; plan-carried facts as memory | +10.3pp dynamic vs static; +34pp plan quality; executor data ≈ nothing |
| Planner Matters (2605.02168) | scaling the planner ≈ scaling the whole system | planner coefficient ≈ all-modules coefficient |
| TDP (2601.07577) | DAG plan; node-scoped contexts; local replan; Self-Revision fact propagation | up to −82% output tokens vs global replan, equal-or-better accuracy |
| LLMCompiler (2312.04511) | DAG dispatch of parallel steps | 3.7× latency, 6.7× cost reduction where parallelism exists |
| ReWOO (2305.18323) | shared slot-memory across steps | 64% token cut |
| AdaPlanner (2305.16653) | in-plan refinement vs out-of-plan revision as a formal policy | — |
| VeriMAP (2510.17109) | planner-authored Python verification functions per subtask; executors scoped away from the global task; structured named I/O at handoffs | +4.05% BigCodeBench-Hard; +9.8% Olympiads |
| GoalAct (2504.16563) | global planning + hierarchical execution, same shape, weaker evidence | listed for completeness |

**Magentic-One (2411.04468) — the full controller mechanics, the mechanism to imitate.**
Two nested loops. The *outer loop* owns the **task ledger**: "given or verified facts,
facts to look up, facts to derive, and educated guesses," with guesses required to be
expressed "in a guarded or qualified manner." On every plan update: "we force all agents
to clear their contexts and reset their states." The *inner loop* owns the **progress
ledger** (which agent speaks next, with what instruction, and whether the task is
progressing, stalled, or complete) and the **stall counter**: incremented when a loop is
detected or forward progress stops; the paper's implementation continues while the counter
is at most 2; above that → reflection → ledger update → revised plan → fresh inner loop
with all contexts cleared. This system's controller loop is the same shape. The three
states the current gate lacks: stall counting, ledger-grounded reflection, forced context
reset.

**Architectural insight:** plan granularity should follow *predictability*, not taste —
which gives the §2.6 dial a default rule (§5.7). The replan trigger must be first-class
controller state (stall counter + gate outcomes), not an LLM decision. Replans must reset
contexts (Magentic-One) and carry reflection text back into the plan and ledger
(Reflexion, at plan granularity).

### D. What working big-task coding systems look like — and what the frontier scores

Working systems share seven properties: deterministic orchestration; role separation with
asymmetric authority; frozen candidate-bound evaluation; baseline-awareness; bounded
retries with distilled feedback; cross-iteration evidence state; and scope discipline
beating agent cleverness. The systems: HoH (2609.01481, the loop wrapper, §F2), Agentless
(2407.01489: localization → repair → validation, majority vote over normalized patches,
won SWE-bench Lite at $0.70/task), Phoenix (2606.20243: baseline-aware, ≤2 structured
retries then human), Magis (2403.17927), Agent KB (2507.06229: +18.7pp GAIA pass@3,
+4.0pp SWE-bench pass@1), SWE-agent (2405.15793: the ACI design ablations, §B), AgentCoder
(2312.13010: independent test-designer model).

**The leaderboard architecture census (Dissecting, 2506.17208).** The paper classifies
submissions from both leaderboards into eight architecture groups (Table 9 of the paper)
and tests the differences (rank-based Kruskal–Wallis test). The Verified-board medians:

| Group | # entries | Median | Max |
|---|---|---|---|
| G4 scaffolded single-agent | 7 | **55%** | 65.4% |
| G5 scaffolded multi-agent | 13 | 40.6% | 53.2% |
| G7 emergent multi-agent | 4 | 54.5% | 62.2% |
| G3 fixed multi-agent | 3 | 50% | **63.4%** (single highest G3 entry) |

The highest median is G4's 55%; the group differences are statistically significant on
both boards (Lite: p = 0.0070). The census max on Verified was 68.2% (NVIDIA
Nemotron-CORTEXA, May 2025).

**Safe reading:** minimal roles plus strong scaffolding is the reliable regime — it wins
on medians, where reliability lives. Elaborate free-form multi-agent chat is not. And a
small number of tightly-scripted pipelines can produce top single entries (the 63.4% G3
max came from a scripted fixed pipeline, n=3) — so do not add roles without a named
failure mode each addresses (MAST: 3 of 14 failure modes are *created* by multi-agent
structure), and do not dogmatically forbid scripted pipelines. This system's
planner/coder/eval plus code controller is the defensive, median-favoring choice.

**StateM (2608.15089):** 95.3% raw accuracy on Terminal-Bench 2.1 via harness engineering
(§F1). **Frontier goalposts:** §8. The pattern: function-level benchmarks are nearly
saturated; acceptance-level, long-horizon, and consistency metrics are where agents
collapse. This system's whole design — contracts, gates, dense verification, scoped
contexts — targets exactly that gap.

### E. Verification: making gates trustworthy

The base design, stable across the literature: hard versus soft critics (executable
checks versus LLM judgment); three verification levels — step correctness, increment
objective, feature intent (MAST: +15.6pp for the objective level); verify-the-verifier
(fail-before/pass-after; baseline snapshots); process signals beat outcome signals
(PRM, 2305.20050); reflection works *because* it is grounded in external tool-sourced
signal (Reflexion 2303.11366, CRITIC 2305.11738); and termination by verification, not
by model confidence.

The measured additions:

- **False-accept rate:** SWE-Gate — 221 of 644 functionally-passing patches (34.3%) fail
  constraint validation (full detail in §F8).
- **Contracts-as-code is a published design:** VeriMAP's planner-written verification
  functions; SDD's executability discipline ("a constraint no tool can enforce is a
  wish…"); Gherkin validated as the requirements-to-code bridge; Constitutional SDD
  (2602.02584) enforcing security constraints by construction — the published name for
  the CT3/CT4 pattern.
- **Dense process rewards generalized beyond math:** Math-Shepherd (2312.08935, step-level
  verification without human annotation), VPR (2605.10325, verifiable process rewards for
  agentic reasoning), consistency-guided credit assignment (2605.20061). These are the
  training-side mirror of per-slice gates.
- **Consistency as the acceptance metric:** τ-bench pass^k — §F12 has the numbers; one
  green run is a sample, not a result.
- **Verifiers get gamed and must co-evolve:** HVTB (2608.22103) — agents satisfy checks
  while violating intent; prompting mitigates known hacks, not unknown ones. ASL
  (2510.14253) — generative reward models beat rigid rule-based rewards for open-domain
  work, and co-evolving the verifier with the policy raises performance further; the
  paper's own words are in §F5. Consequence: the eval rubric and constraint tests are
  *living* artifacts, revised in the harness telemetry loop (§7 item 17), never a frozen
  suite.
- **Judge bias is measured:** GPT-4 as judge shows significant self-preference,
  correlated with low-perplexity (self-familiar) outputs (2410.21819). The eval role sits
  on a different model family than the coder, blind to authorship.

### F. Memory, context, reuse across runs

The base design: progressive disclosure; the filesystem as memory; AWM's induced
workflows (2409.07429: +24.6%/+51.1% relative on WebArena, and they *outperform* the
human-expert-authored SteP workflows); Voyager's skill library (2305.16291); store
decision-relevant folds, not narrative logs.

The measured additions:

- **Distillation is now a measured ritual.** ExpeL (2308.10144) extracts natural-language
  insights and recalls past experiences without any parameter updates. SkillWeaver
  proposes a skill, practices it, and distills it
  into a reusable API, honing until it passes: +31.8% relative success on WebArena,
  +39.8% on real sites, and skills transferred to weaker agents improve them by up to
  54.3% on WebArena (2504.07079).
- **The investment rule has a name.** SDD's durability asymmetry (2609.00252, verbatim):
  the technical harness is transient and depreciates as models improve, whereas the
  methodological harness — the team's intent, norms, and accumulated decisions —
  appreciates over time; "teams should invest preferentially in the durable harness."
  In this system: the roadmap/ADR tier plus the skill registry is the appreciating layer;
  the harness code is the depreciating layer. Budget attention accordingly.
- **Memory interference is the named risk of a long-lived roadmap.** Multi-target
  interference benchmarks give 7 representative memory systems (long-context LLMs, RAG,
  memory frameworks) only 27.9% average accuracy, worst on questions requiring
  aggregation of multiple facts, with degradation compounding (2608.06663 §4).
  Superseded facts — like the `password_hash` discovery rewriting I2 in the §2.2 example —
  are the interference source. Fix: make supersession a *field*, not prose
  (`supersedes: RM-auth-D3`), the way Generative Agents' memory stream scores
  recency/importance (2304.03442).
- **Fact/guess provenance.** Magentic-One's four ledger categories (verified / to-look-up /
  to-derive / educated-guess, the last "guarded or qualified") become the entry grammar
  of the EVIDENCE ledger and the provenance tags on roadmap decisions (`decided:` vs
  `assumed:`). This directly attacks MAST failure mode FM-2.2 (proceeding on wrong
  assumptions, 11.7% of failures): visible assumptions can be asked about — feeding the
  ASK# channel (§7 item 13).

### G. Multi-agent failure modes — the warning label

MAST (2503.13657, 1,600+ traces): specification failures 41.8%, inter-agent misalignment
36.9%, verification 21.3%; step repetition 17.1%; reasoning–action mismatch 14.0%;
unasked assumptions 11.7%. Three of the fourteen failure modes are *created by* the
multi-agent structure itself. Design-only interventions that work: better role
specifications +9.4%, objective-level verification +15.6pp. This system's parsed-artifact
handoffs, written contracts, code-declared completion, and budgeted retries map one-to-one
onto the validated defenses. Residual risk: ambiguity resolved silently at plan time —
the ASK# channel (§7 item 13) is the counterweight.

### H. Harness architecture & spec-driven development

Five converged harness elements (2608.23953): a commoditized loop; an append-only,
replayable run record; model quirks treated as data; progressive disclosure; and
extension seams. Spec Kit Agents (2604.05278): discovery/validation hooks placed *outside*
the agent prompts (+0.15 quality, +1.7% SWE-bench Lite; main benefit is earlier detection
of compounding errors). SDAD (2608.20341): a spec-driven lifecycle with independent
verification and governance metrics. HarnessFix (2606.06324): an attribution loop that
maps failures to the responsible harness component and revises it — scoped,
regression-checked revisions of planner skills/prompts/gates, +6.3–18.4%.

The 2026 SDD cluster (2609.00252 plus SDD: Code to Contract 2602.00180, Constitutional
SDD 2602.02584, SpecMine's large corpus of SDD artifacts 2608.25202, Kitchen Loop's
user-spec-driven self-evolving codebase 2603.25697) establishes spec-driven development
as a durable methodology layer with its own research program. Three directly usable pieces
from 2609.00252: **worktree-isolated parallel agents** (§F6), the **appreciating /
depreciating split** (§F), and **graduated autonomy**: human-checkpoint density as a
per-slice risk dial — spec ambiguity escalates to the human (via ASK#), execution failure
auto-repairs within budget (§7 item 14).

### I. Ambiguity and clarification

Agents rarely ask when they should (Ambig-DS, 2605.09698; MAST FM-2.2 11.7%). Fine-tuned
clarification beats prompting. Users prefer clarify-first (2507.21285). One safety
constraint: keep questions in the human channel — the clarification state widens the
prompt-injection surface if answers can come from retrieved content (ASPI, 2605.17324).
Link to the design: the fact/guess ledger makes assumptions first-class — every `GUESS`
entry a contract depends on is a candidate `ASK#` (§7 item 13).

### J. Cost & model allocation

- **FrugalGPT (2305.05176):** an LLM cascade (route easy queries to cheap models, escalate
  on uncertainty) matches the best individual model at up to 98% cost reduction, or
  improves accuracy by 4% at matched cost. Caveat: the cascade is *learned* from
  query-level outcome data. This system does not have that data yet — hence the
  planner-tagged variant in §7 item 18, not a learned cascade.
- **More Agents (2402.05120):** sampling-and-voting performance scales with the candidate
  count, orthogonally to other methods, with gains correlated to task difficulty — the
  evidence base for N-version repair (§7 item 10) and sample-and-select on hard slices.
- **METR cost headroom (2503.14499):** over 80% of successful agent runs cost less than
  10% of the human time cost — parallel sampling usually stays economical.
- **Self-preference (2410.21819):** eval on a different family, blind to authorship
  (§7 item 8).

---
## 5. The six locked decisions — what the evidence says

Each locked decision from §2.6, with the evidence for it, the boundary conditions, and
what the implementation plan should note.

### 5.1 Four tiers (feature → increment → `SLICE#` → `STEP#`)

**Verdict: supported.** Hierarchical decomposition is the field's default architecture
(2502.11221, 2304.11477, 2311.05772). "Slice = one verifiable commit with its own
contracts" is a published unit: it is VeriMAP's subtask-plus-verification-function, and it
is HoH's bounded, locally-complete increment. Slice sizing matches SWE-bench Live's
success cliff (§F7): one commit, a few files, under a hundred lines.

**Boundary condition (implement this, not just the tiers):** granularity is a property of
task *uncertainty*, not a free efficiency gain. Over-decomposition misaligns the guidance a
step receives from what execution actually needs (2608.06663 §3); ADaPT decomposes only on
failure, not eagerly. So: 4–7 slices per increment is the prior, tuned per domain
familiarity. Do not over-slice.

### 5.2 Rolling wave; staleness managed at the increment boundary

**Verdict: supported.** Plan-first plus on-demand replan matches step-by-step accuracy at
2–3× fewer tokens for well-specified tasks (2608.06663 §3, survey-mediated; TDP's
primary-source number is up to −82% tokens for the same idea). The worked `password_hash`
example in §2.2 is textbook TDP Self-Revision: a fact discovered in I1 changes I2's spec.

**Implementation notes:** two gaps to close. First, add the cheap *within*-increment
fact-propagation path — a `STALE-SPEC` flag plus scoped spec-refinement, not a full
replan (§7 item 9). Second, make supersession a field (`supersedes:`), because a
long-lived roadmap is a memory-interference source (27.9% average accuracy on
aggregation questions, 2608.06663 §4).

### 5.3 Planner does the heavy lifting; coder executes

**Verdict: supported, and upgradeable.** Planner-centric scaling is the consensus
(2605.02168, 2503.09572). Planner-authored passing criteria with scoped executors beat
single- and multi-agent baselines (VeriMAP, +9.8% on hard sets). MAST adds the failure
evidence: disobeying the task specification is 11.0% of failures, and it is rooted in
pre-execution design — which is exactly what a planner-written, reviewable plan attacks.

**The upgrade:** the planner's authorship extends to the *test files* (§7 item 1). This
preserves the design's own rule — "the coder should not design its own contract" — in its
strongest form, and it matches AgentCoder's independent-test-designer principle
(2312.13010).

### 5.4 Two files (roadmap + increment plan); slice brief = a view

**Verdict: supported.** Durable external memory plus a scoped work unit; it avoids
artifact drift. The append-only, replayable record is the converged harness pattern
(2608.23953).

**Implementation notes:** three additions. (1) The EVIDENCE ledger becomes the *third*
durable artifact — the HoH ablation says evidence-carrying is essential, not optional
(−6.28 points without it; §7 item 4). (2) Roadmap standing decisions gain provenance tags
(`decided:` vs `assumed:`) and `supersedes:` fields (§7 items 4, 9). (3) The brief layout
follows the measured U-shape: contracts top, recap bottom (§7 item 6).

### 5.5 Naming: `SLICE#` / `STEP#`

**Verdict: supported.** Unambiguous, machine-parseable anchors are an interface-design
principle with measured cost when violated: SWE-agent's ablations show the interface
moves results (−7.7 points without the structured edit command). Ambiguous step identity
is also MAST's biggest single failure mode (step repetition, 17.1% of failures).
VeriMAP's "Structured & Named I/O" is the same idea at handoff granularity. Nothing in the
literature argues against explicit names.

**Implementation note:** this is a grammar change that ripples through both planning
skills, the `plan_ids` extractor's regexes, and any existing plans that use `S#`. Do it
once, with the extractor updated and a migration note for old plans. The other anchors
(`CT#`, `GAP#`, `T#`) are already unambiguous; only slice/step need the rename.

### 5.6 Run shape: planner once → code-owned per-slice loop → PR → chat picks next

**Verdict: supported, and at the frontier.** Deterministic orchestration is the converged
pattern (Phoenix, Agentless, HoH's runtime, Magentic-One's code-driven ledgers). The
Dissecting census favors minimal roles plus strong scaffolding on medians (§4D).
LLMCompiler and TDP provide the DAG extension for parallel branches.

**Implementation notes (upgrades, all in §7):** stall counter as controller state (item
2); a plan pre-check before any coder token is spent (item 5); `DEPS:` tags plus
worktree-isolated parallel slices (item 11); an escalation ladder replacing the flat
"re-run coder (budgeted)" (item 10); graduated autonomy for human checkpoints (item 14).
And some `STEP#`s can be pure code with no LLM call: mechanical steps (migrations,
formatting) are executed by the harness directly — that is Agentless's economics ($0.70
per task) applied to the step level, and it is consistent with the "controller in code"
philosophy.

### 5.7 The open dial: how much step detail per slice

The question: terse checkboxes versus full edit-packets, per slice. The evidence does not
pick a global winner — it says the right detail level depends on *predictability*. The
recommended default rule:

- **`STEPS: prescriptive`** — the planner writes atomic edits plus exit criteria. Use it
  when the planner could have written the diff from what it read: deterministic,
  familiar-repo slices. This is the Plan-and-Act / ReWOO / LLMCompiler regime, where the
  plan is trustworthy precisely because the repo is known.
- **`STEPS: outcome`** — the plan writes contract checkpoints only; the coder owns the
  path. Use it when the slice's own verify results are what will teach the coder:
  unfamiliar subsystems, performance work, flaky integrations. This is HoH's
  constrain-outcomes-not-workflows, and it is how TDP and AdaPlanner handle deviation.

In both modes, deviation rights stay anchored to `CT#` (the contract, not the step, is
what the coder must satisfy), and major drift is still a `REPLAN`. The mode is a declared
per-slice property, and it is tuned per slice type from telemetry (§7 item 17) — which
keeps it a dial, as the design intends, with a reasoned default instead of a coin flip.

---

## 6. Fourteen distilled principles

The findings compressed into design rules. Each cites its anchor evidence.

1. **Structure beats scale.** Matched-compute loop structure plus evidence-carrying beats
   more passes of the same agent (HoH ablations; TDP −82% tokens; Horizon Gap 2–3×
   plan-first economics).
2. **Make planning the premium role.** Planner capacity is the dominant scaling axis
   (2605.02168, 2503.09572, VeriMAP).
3. **Every unit of work gets an external deterministic proof** (2402.01817, 2605.18747).
4. **Scope each context to one unit; fold everything else** (2509.09677, 2510.11967,
   2601.07577, 2512.02445, 2512.04307).
5. **Confine recovery to the failed scope** (TDP local replans; Magentic-One's
   inner-loop-local stall handling with outer-loop replan).
6. **Carry evidence, not transcripts** (HoH's per-iteration evidence; folding summaries
   must retain constraints, 2601.18285; Magentic-One's task ledger).
7. **Propagate discovered facts into future specs** (TDP Self-Revision; 2503.09572;
   `supersedes:` fields per 2608.06663 §4).
8. **Separate authorship from acceptance at every level** (HoH; AgentCoder; MAST;
   self-preference bias 2410.21819).
9. **Verify at three levels: step correctness, increment objective, feature intent**
   (MAST +15.6pp for the objective level; SWE-Gate's functional/constraint separation).
10. **Verify the verifiers — and keep evolving them.** Fail-before/pass-after; baseline
    snapshots; flake detection by rerun (Agentless, Phoenix). Verifiers get gamed
    (2608.22103), and a co-evolved verifier outperforms a frozen one (2510.14253).
11. **Pin governance outside the compactable channel** (compaction evicts standing
    policies, 2606.22528; pinned records, 2608.23953; U-shaped layout, 2307.03172).
12. **Treat the harness itself as a product with telemetry** (HarnessFix 2606.06324;
    harness survey 2605.18747).
13. **A constraint no tool can enforce is a wish.** Every `CT#` must compile to an
    executable check, authored at plan time by the planner; contract and proof are one
    artifact (2609.00252, 2510.17109, 2609.04167).
14. **Consistency under failure injection is the metric.** pass^k over stochastic gates;
    structured failure signals on every gate; recovery paths designed, not hoped for
    (2406.12045, 2606.22388, 2512.04307).

---
## 7. Implementation ideas — the backlog

Eighteen items in three tiers. Tier 1 is high leverage, low cost — do first, in the order
given. Tier 2 is high leverage, medium cost. Tier 3 is the compounding layer: it pays off
over many features, not one. Each item states what it is, how it works, the evidence
(compact — the numbers live in §3 and §10), what changes in the system, and the cost.

### Tier 1 — high leverage, low cost (do first, in this order)

**1. Contracts become executable: the planner authors the test file; the harness proves
non-vacuity.**

*What it is.* Every `CT#` gets a real test in the repo before the slice is accepted. The
planner writes that test; the harness checks the test is not vacuous. This is the single
highest-value upgrade in the backlog: it converts every contract from a wish into a
check, and it is the mechanism the closest published designs all converge on (§F8, §F11).

*How it works.* The increment plan grows one line per slice, `TESTS:`, pointing at the
planner-authored test file:

````
## SLICE2: the POST /login endpoint
INTENT: verify credentials and start a session.
CONTRACTS:
  CT3 [CONSTRAINT]:    unknown email and wrong password return an IDENTICAL 401
  CT4 [CONSTRAINT]:    the password is never logged
  CT5 [FUNCTIONAL]:    valid credentials → 200 + session cookie
  CT6 [PRESERVATION]:  existing /health and route tests stay green
TESTS: tests/test_login_endpoint.py        ← planner-authored, marked NEW
```verify
uv run pytest tests/test_login_endpoint.py -q
```
````

The harness runs four steps per slice. (a) **Baseline snapshot** before the coder starts:
run the repo's test suite and record what already fails — real repos have pre-existing
failures, so without a baseline you cannot tell which failure is the coder's. (b)
**Fail-before check:** the new tests must *fail* on the pre-slice state; a test that
passes before the work is done proves nothing. This is the reproduction-test filter from
Agentless, applied to every contract, not just bug fixes. (c) The **coder implements**.
(d) **Pass-after check** — the existing verify gate. Item 5's plan pre-check rejects any
`CT#` not covered by a test in `TESTS`.

The contract classes are not decoration. `FUNCTIONAL` proves the behavior works;
`CONSTRAINT` encodes the acceptance criteria functional tests miss (error shapes,
backward compatibility, conventions, no new dependencies) — this is the class where the
34.3% false-accept rate lives (§F8); `PRESERVATION` encodes "nothing you did broke what
already worked." Security-flavored contracts (CT3/CT4) are the published Constitutional
SDD pattern — enforced by construction at plan time, not reviewed afterward.

*Evidence:* A — 2609.04167, 2510.17109, 2407.01489, 2503.13657; B — 2609.00252,
2606.20243, 2312.13010. See §F8, §F11.

*What changes / cost:* plan grammar (`TESTS:` line, CT classes), the plan-authoring skill
(planner writes test files), ~a day of harness code. Highest leverage in the list.

**2. Stall counter + reflection + forced context reset (controller states, not events).**

*What it is.* The gate stops being "re-run the coder, a limited number of times." It
becomes a machine-readable budget that counts how long the slice has been stuck, and a
breach triggers a defined recovery sequence instead of a human interrupt.

*How it works.* The gate state is a budget triple: `(repair_attempts ≤ 2, stall_counter <
3, model_tier)`. The counter increments on objective signals: the identical failure
signature twice in a row, a commit with no diff, a verify loop (same command, same
result), or an eval REPAIR with no contract-status change. While below threshold, the
harness retries normally. On breach, a fixed sequence: (1) **REFLECT** — a short LLM call
that reads the failure packets and writes what went wrong and what was learned; the text
is appended to the increment plan and the EVIDENCE ledger (Reflexion, at plan
granularity); (2) a **scoped REPLAN** of the affected slice; (3) **all role contexts
cleared and reset** — the anti-self-conditioning mechanism, because the model's own
error-laden history is what compounds errors (§F3); (4) a fresh inner loop. A flaky
verify (passes on rerun) increments the counter instead of halting — a flake burns
budget instead of stopping the run. The human halt survives as the *post-breach*
escalation: the genuine last resort the design intended.

The trigger is controller state, not an LLM decision: "I'm stuck" from the model is
self-assessment, and self-assessment is exactly what the evidence says not to trust
(§F5). The reference implementation is Magentic-One, whose full loop mechanics are in
§4C; its published configuration continues while the counter is at most 2.

*Evidence:* B — 2411.04468 (mechanics, verbatim); A — 2512.04307 (loops + lost objective
are the measured dominant failure modes), 2503.13657 (step repetition 17.1%), 2509.09677
(history removal fixes self-conditioning).

*What changes / cost:* pure harness code — gate state machine plus one REFLECT prompt. No
planner or coder prompt changes. Low cost; converts the design's weakest moment (a wedged
slice waiting for a human) into a bounded, measurable one.

**3. `STEPS: prescriptive | outcome` — the step-detail dial becomes a declared tag.**

*What it is.* The §2.6 open question gets a concrete answer that keeps it a dial: the
planner declares, per slice, how prescriptive the steps are, using a rule about
predictability instead of taste. The full rule is in §5.7.

*How it works.* The slice header gains `STEPS: prescriptive` or `STEPS: outcome`.
Prescriptive slices carry atomic edits plus exit criteria (the §2.4 SLICE2 example, in
full) — use when the planner could have written the diff from what it read:
deterministic, familiar-repo slices. Outcome slices carry contract checkpoints and the
intent only; the coder owns the path, and the verify block decides whether it arrived —
use when the slice's own verify results are what will teach the coder: unfamiliar
subsystems, performance work, flaky integrations. In both modes, deviation rights are
anchored to `CT#` (the contract, not the step, is what the coder must satisfy), and major
drift is a REPLAN. Mechanical steps (a migration, a formatter run) may be tagged
`(auto)`: the harness executes them directly, no LLM call — the step-level application of
Agentless's per-task economics.

The tag, not the global choice, because the evidence splits by regime: the plan-first
systems (Plan-and-Act, ReWOO, LLMCompiler) win on *predictable* plans in known
environments; HoH's gains come from constraining *outcomes*, not workflows, when the path
is uncertain (§4C). A global "always terse" or "always detailed" policy is wrong in half
the slices. The tag also feeds telemetry (item 17): which mode wins per slice type becomes
measurable, so the default improves over time — which is what "a dial, not a fork" was
supposed to mean.

*Evidence:* A — 2503.09572, 2609.01481, 2601.07577, 2305.18323, 2312.04511; C —
2608.06663 §3 (over-decomposition caveat).

*What changes / cost:* one grammar field plus plan-authoring guidance. Low cost. It also
creates the tag that item 18 keys off — a prerequisite, not a convenience.

**4. EVIDENCE ledger — the third durable artifact, with a provenance grammar.**

*What it is.* An append-only log, per feature, of everything the run learned. The
roadmap and the increment plan are the two files; the ledger is the third durable
artifact. It is what makes the next increment's plan smarter than the last one's.

*How it works.* The planner reads the ledger at increment start; the eval appends per
slice. Entries carry a type tag — the four categories from Magentic-One's task ledger,
plus two system types:

```
E1  FACT      users.password_hash is bcrypt(12)          [verified: I1-S2 CT3]
E2  DERIVED   session cookie must set SameSite=Lax       [from E1 + CT4]
E3  LOOKUP    email validator library behavior on +tags
E4  GUESS     rate limiter is per-IP, not per-user       [assumed — ASK# candidate]
E5  FAILED    argon2 via passlib broke uv lock           [hypothesis, I1-S3]
E6  GAP       G#2 logout invalidation not covered by I1
E7  PRESERVE  CT3/CT4 of SLICE2 are security-critical
```

`FACT` entries must carry a verification reference (which slice's verify or test proved
them). `GUESS` entries are the danger class: an assumption written as a fact is how runs
fail quietly. The grammar rule: every `GUESS` a contract depends on is auto-promoted to
an ASK# candidate (item 13) — a visible assumption can be asked about; an invisible one
cannot. Roadmap standing decisions get the same treatment: `decided:` (chosen) versus
`assumed:` (never verified). Entries are appended, never rewritten; supersession is a
field (`supersedes: E3`), keeping the ledger queryable and preventing the
memory-interference failure mode — a long-lived roadmap is a memory system, and it needs
tombstones, not deletions (§4F).

*Why it matters:* the HoH ablation is the quantitative proof that evidence-carrying is
what makes the loop compound — removing it costs 6.28 points, and freezing the plan
costs 8.1 (§F2). The ledger is this system's version of that channel: it is why
iteration 10 is smarter than iteration 1, instead of just longer.

*Evidence:* A — 2609.01481 (ablation), 2503.13657 (unasked assumptions 11.7%); B —
2411.04468 (ledger categories, verbatim); C — 2608.06663 §4 (interference figure).

*What changes / cost:* one file, a parser, two role-prompt touchpoints. Low cost. It is
the substrate for items 9, 13, and 15 — they read from it, so it comes before them.

**5. Plan pre-check (lint + symbolic assertions), pure code, before any coder token.**

*What it is.* A static check of the increment plan, run in code, before the controller
loop starts. It catches plan errors that would otherwise burn entire slice runs to
discover.

*How it works.* It extends the existing `plan_ids.py` extractor with assertions. Each
check, and its published reason: every referenced path or symbol exists or is marked
`NEW` (ungrounded plans look right and fail — §F5); every `CT#` is covered by a test in
the slice's `TESTS:` line (item 1's wish-vs-constraint rule, enforced); every `STEP#` in
a prescriptive slice has an exit criterion (a step without one is untrackable — the
harness cannot tick it); the `DEPS:` graph is acyclic; no slice references an undefined
upstream slice or contract; every `verify` command is dry-run executable (a typo should
not cost a slice); the slice count is in the sane range (4–7 prior — warn, don't fail,
outside it); the fail-before check is scheduled for every NEW test. On failure, the
planner is shown the specific assertion that failed and fixes the plan — no coder
involved, no execution tokens spent.

The checks live in code, not in a prompt, because this is the verification work the
planning literature says to move *out* of the model: LLMs are measurably bad at checking
their own plans (§F5), and symbolic checks are free. The pattern is Spec Kit's
discovery/validation hooks, placed outside the agent prompt.

*Evidence:* A — 2604.05278 (hooks outside the prompt; earlier detection of compounding
errors), 2402.01817; B — 2304.11477 (soundness from outside).

*What changes / cost:* five or six assertions in the extractor — an afternoon, given the
extractor exists. Build it as a list of pluggable checks; item 11's DAG checks join it
later.

**6. Retry hygiene: distilled failure packets with a structured schema — never raw transcripts.**

*What it is.* When a slice fails and the coder retries, the retry does not see the failed
trajectory. It sees a small, structured summary of what failed. The
anti-self-conditioning mechanism at the retry level.

*How it works.* The gate emits a failure object with a fixed schema: `{slice, step, ct_id,
exit_code, stderr_digest, attempt, signature_hash, prior_attempts[], ledger_refs[]}`. The
`signature_hash` is a hash of the normalized failure (same error, same location — what
"identical failure twice" means, and what increments the stall counter, item 2). The
retry prompt receives the slice brief, the relevant ledger entries, and the failure
packet. Not the transcript: the per-step error rate *rises* when the model's own prior
errors are in context, and removing the error-laden history is the measured fix (§F3).
The second requirement comes from PlanBench-XL's collapse under blocking: the failure
signal must be *explicit and structured*, because agents fail worst when failures lack
clear error signals (§F7).

The brief itself has a layout contract, because layout is measured (§F10): `CT#` at the
top, `INTENT` second, `STEPS` third, a recap of prior-slice outcomes at the bottom (the
U-shape says the middle of a context is used worst); file views windowed to about 100
lines; stale observations collapsed to the last 5 (full history measured worse); and the
slice's INTENT restated at the very bottom, where attention is strongest — "lost
objective" is a measured failure mode.

*Evidence:* A — 2509.09677, 2512.04307, 2606.22388, 2405.15793, 2307.03172; B —
2602.07962.

*What changes / cost:* the gate's failure object, the retry prompt template, the brief
template. Low-to-medium. Every retry in the system becomes cheaper in tokens *and* more
reliable.

**7. Pin invariants + constraint re-injection (governance outside the compactable channel).**

*What it is.* The rules the system must always obey — the roadmap's standing decisions,
the role contracts, the PRESERVATION entries — are re-injected into every role prompt at
every invocation by the harness. Never left to survive inside the conversation history,
because compaction evicts them: agents stop obeying a rule once the rule leaves the
context, even though they obeyed it perfectly while it was visible (governance decay,
§F10).

*How it works.* A fixed preamble, assembled by the harness from the roadmap and the
ledger, is prepended to each coder/eval/planner call: the standing `decided:` entries,
the current slice's contract classes, and the active PRESERVATION entries. A few hundred
tokens per call, and the rules are present regardless of what the context window did —
which matters at scale, because even 1M-token windows degrade past ~100K tokens.

*Evidence:* A — 2606.22528, 2512.02445; B — 2608.23953 (pinned records).

*What changes / cost:* one harness function that assembles the pinned preamble. Trivial
cost — the cheapest insurance in the list.

### Tier 2 — high leverage, medium cost

**8. Three-level eval, different family, blind, machine-readable.**

*What it is.* The eval role is restructured from "review this diff" into three explicit
levels, run by a model from a different family than the coder, emitting machine-readable
verdicts the gate can branch on.

*How it works.* Three levels, each with a distinct question. **L1 mechanical:** exit
code, lint, type checks — facts from the verify run; L1 records them. **L2 contract
verdicts:** for each `CT#`, does the diff plus the test evidence satisfy it? The eval
cites the specific test or diff hunk per verdict. **L3 intent judgment:** does the diff
do what INTENT says, not merely what the commands say — the level that catches
"implemented the commands, missed the point." The verdict format is fixed: `PASS |
REPAIR | REPLAN` plus which `CT#` and which level triggered it; the gate branches on
structure, not prose. Two placement rules: the eval model comes from a *different
family* than the coder and is blind to authorship (self-preference bias is measured —
judges favor their own family's low-perplexity, self-familiar outputs, §F5); and the eval
model is at least as strong as the coder (a weak judge silently passes a strong coder's
subtle errors). At increment end, before the PR: an objective-level pass against the
increment's user-visible intent ("can a user actually sign in?") plus a regression re-run
of *all* prior slices' verify commands. The objective level is the highest-value single
check in the loop — MAST measured it at +15.6 points — and it is the level most designs
skip.

*Evidence:* A — 2503.13657, 2410.21819, 2609.04167; B — 2609.01481, 2606.20243.

*What changes / cost:* the eval prompt (three levels, fixed verdict format) and the role
configuration (model family). Medium. The judgment half of the fact/judgment split, done
the way the evidence says.

**9. STALE-SPEC propagation + `supersedes:` fields.**

*What it is.* When the run discovers something that makes a *later* slice's plan wrong,
the fix is a scoped spec-refinement of that slice — not a full replan of the increment,
and not a silent drift.

*How it works.* Slice evidence — verify output, eval notes, a failure packet, a ledger
FACT — contradicts or enriches a downstream slice's spec. The harness flags that slice
`STALE-SPEC` (a tag in the increment plan). At the next natural pause, the planner runs a
*scoped* refinement pass on the flagged slices only: it rewrites their INTENT/STEPS/
TESTS to incorporate the new fact, appends the reason to the ledger, and touches nothing
else in the plan. When the rewrite supersedes a fact, the new entry carries
`supersedes: E0`; the old entry stays as a tombstone. This is TDP's Self-Revision — and
TDP measured the payoff: up to 82% fewer tokens than global replanning at equal or better
accuracy, because the part of the plan that was still correct is not regenerated
(§F6). The unsuperseded-fact case is the memory-interference case: a long-lived roadmap
with a rewritten fact, where the old fact is still readable and the new one is
elsewhere, is how "which password hashing do we use" gets answered wrong three
increments later.

*Evidence:* A — 2601.07577, 2503.09572; C — 2608.06663 §4; B — 2304.03442.

*What changes / cost:* harness flagging (detect contradiction, set the tag) plus a
planner skill (scoped refinement pass, fixed prompt). Medium. The mechanism that makes
rolling wave *cheaper*, not just safer.

**10. Escalation ladder (loop-breaker + N-version repair + stall counter, merged).**

*What it is.* The flat "re-run the coder (budgeted)" becomes a ladder with distinct
rungs, each a different tool. The run climbs it instead of repeating the same attempt.

*How it works.*

```
attempt 1   retry with the distilled failure packet (item 6)
attempt 2   N-version: k = 2–3 parallel coder attempts (different temperature /
            prompt framing), run each, verify results pick the winner;
            all candidates archived
breach      stall counter (item 2) → REFLECT → ledger → scoped REPLAN
            (a prescriptive slice may flip to outcome mode)
post-breach human halt — the existing "surface, halt", now genuinely last resort
```

Identical-failure-twice (matching `signature_hash`) skips straight to N-version —
repeating the same prompt at the same temperature is the most expensive way to get the
same error. The candidate archive is free telemetry for item 17: every archived attempt
is a labeled example of "what didn't work, and here was the working alternative."

N-version instead of plain retry, because sampling-and-voting performance scales with
the candidate count and the gains correlate with task difficulty — the hard slices, which
are exactly the ones failing, benefit most; Agentless proved the mechanism in the target
domain (voting over normalized patches won SWE-bench Lite at $0.70/task); and the cost is
bounded (over 80% of successful runs cost less than 10% of the human time cost, so 2–3×
parallel on the failing minority stays economical, §4J).

*Evidence:* A — 2402.05120, 2407.01489, 2503.13657; B — 2503.14499 (cost headroom).

*What changes / cost:* the gate state machine plus a parallel runner — which shares the
worktree plumbing with item 11; build the plumbing once. Medium. Turns the failure path
from a coin flip into a search with a budget.

**11. Slice DAG + parallel independent slices in git worktrees.**

*What it is.* Slices declare their dependencies; the harness schedules the independent
ones in parallel, each in its own git worktree.

*How it works.* One grammar line per slice: `DEPS: SLICE1`. The harness topologically
sorts: any slice whose `DEPS:` are all VERIFIED is ready. Each parallel coder gets a git
worktree — a private working directory, index, and branch, sharing the object store.
That is the published isolation mechanism for parallel agentic work ("the cornerstone
for parallel agentic work during 2026", §F6): cheap, atomic (real git commits on real
branches), and one failed slice cannot corrupt another coder's files. At the increment
boundary the harness merges branches in dependency order, gated by item 8's regression
re-run. Implement this explicitly: worktrees isolate *code*, not *processes* — runtime
isolation (ports, databases, temp directories) must be arranged per worktree, or two
parallel slices fight over a test database.

Parallelism pays where steps are independent: LLMCompiler measured 3.7× latency and 6.7×
cost reduction from dispatching independent steps in parallel (§4C). The parallelism
here is at the slice level, and the slice is already the unit with its own proof — which
is what makes parallel slices safe: each carries its own verify, so the merge check is
per-slice, not holistic.

*Evidence:* A — 2312.04511, 2601.07577; B — 2609.00252 (worktree passage, verbatim),
2506.17208.

*What changes / cost:* the `DEPS:` field, topological scheduling, the worktree runner
(shared with item 10), per-worktree runtime isolation. Medium. Start with two independent
slices in one real increment — enough to validate the plumbing without building the
general case.

**12. pass^k in the tracker — for stochastic gates only.**

*What it is.* "VERIFIED" stops meaning "one green run." For gates whose result is
stochastic, it means *k consecutive passes* — one green run of a stochastic gate is a
sample, and the sample rate is misleading (§F12).

*How it works.* By gate type. **k = 1 for deterministic tests** — a pytest command with
fixed input and environment does not flake by definition; if it appears to, that is a
flake-classification event feeding the stall counter (item 2), not a reason to rerun.
**k ≥ 2 for stochastic gates:** eval verdicts (LLM judgment is stochastic and
self-preference-biased — two independent passes with the same verdict is meaningful, one
is noise); any test touching time, the network, or concurrency; any slice whose repair
history includes a flake classification (it demonstrated non-determinism). The tracker
stores a per-slice pass-streak counter; the gate flips VERIFIED only when the streak
reaches the gate's k. The system-level metric: **pass^k over a held-out
slice-regression set** — a fixed set of representative slices that every completed
feature re-runs. The KPI is "the system still passes its old slices k times in a row,"
never "one green feature."

k only for stochastic gates, because that is what makes the metric affordable: τ-bench
shows why stochastic gates lie by repetition (at 61.2% pass@1, pass^8 is under 25%), but
deterministic gates do not — paying k× verify cost where the exit code already gives the
guarantee buys nothing.

*Evidence:* A — 2406.12045, 2606.22388; see §8 (goalposts).

*What changes / cost:* trivial tracker arithmetic plus a repeat-run policy. Low cost. The
difference between "the feature works" and "the system works."

**13. ASK# clarification channel at plan time.**

*What it is.* The planner gets a first-class way to say "the spec does not determine
this," and the human answers *before* the run starts — instead of the run discovering the
ambiguity three slices in.

*How it works.* The planner emits `ASK#` items at two severities. **Blocking:** the
feature spec underdetermines a contract — "IDENTICAL 401" is written, but the spec never
says whether a *throttled* request gets the 401 or a 429. The chat role resolves
blocking ASKs with the human before the run starts; the answer becomes a `decided:`
roadmap entry. **Non-blocking:** the planner records a default with its provenance
(`assumed:`) and proceeds. The channel is auto-seeded from the EVIDENCE ledger: every
`GUESS` a contract depends on (item 4) becomes an ASK# candidate automatically — the
assumption is already written down, so asking about it is cheap. One hard rule: questions
flow through the human channel *only* — an ASK# answered by retrieved or repo content is
an attack vector, not a clarification (the clarification state widens the
prompt-injection surface).

Plan time, not run time, because the measured failure is the *unasked* assumption —
11.7% of multi-agent failures, and agents systematically under-ask (§4I). Asking costs
one human round-trip at plan time; discovering the wrong assumption costs a failed slice,
a repair budget, and possibly a replan.

*Evidence:* A — 2503.13657 (FM-2.2), 2605.09698; B — 2507.21285, 2605.17324,
2411.04468.

*What changes / cost:* the `ASK#` grammar line, the chat role's prompt, the auto-seed
from ledger GUESS entries. Low. The cheapest reliability purchase per failure prevented:
it moves discovery cost to the cheapest point in the timeline.

**14. Graduated autonomy: human-checkpoint density as a per-slice risk dial.**

*What it is.* Not every slice gets the same human attention. The planner tags each
slice's risk; the human checkpoint density follows the tag, so human attention is spent
where the blast radius is large.

*How it works.* One header line: `RISK: routine | elevated | critical`. Defaults:
contracts touching security, data migrations, or external APIs are at least `elevated`;
everything else is `routine`. **Routine:** fully automatic within budget — the run
proceeds, the human sees the result. **Elevated:** the human sees the eval verdict
*before* the merge — one read, one approve. **Critical:** the human approves the *plan
section* — INTENT, CONTRACTS, TESTS — *before* the coder starts. Two escalation classes
stay strictly separate, and the separation is the design point: **spec ambiguity**
always escalates to the human via ASK# (item 13) — a human can fix a spec, and only a
human can; **execution failure** auto-repairs within budget (items 2, 10) — a human
cannot make a flaky test less flaky, and interrupting a bounded repair loop with a human
wait is pure cost.

*Evidence:* B — 2609.00252 (graduated autonomy, verified), 2606.20243; A — 2503.13657.

*What changes / cost:* one tag plus the gate's routing logic (which checkpoints fire at
which rung). Low. What keeps a fully autonomous loop *shippable* to a human who is not
watching it — the trust mechanism.

### Tier 3 — the compounding layer

**15. Post-feature distillation ritual (make the appreciating layer actually appreciate).**

*What it is.* A fixed fifteen-minute step at feature close, run by the chat role, that
extracts the durable value from the finished run into the layers that compound. Without
it, every feature's lessons die with its tracker; with it, feature N+1 starts smarter
than feature N by construction.

*How it works.* Four extractions, each with a published pattern. (a) **3–5
natural-language insights → the ADR tier** — what did the run learn that the next run
should assume? The ExpeL pattern: extract insights, recall them, no parameter updates.
(b) **Recurring slice patterns → plan templates.** If three features in a row had an
"add an endpoint" slice with the same contract classes, that becomes a macro-slice
template: route skeleton → validation → handler → tests, with standard CT classes
pre-filled. The AWM pattern: workflows *induced* from successful runs beat
human-written ones, so the templates come from the run's own history, not from someone's
intuition about how endpoints are built. (c) **Verified snippets → a skill registry.**
Working code that passed its verifies, stored with docstrings, retrieved by embedding
when a future plan needs a similar operation. The Voyager/SkillWeaver pattern: propose →
practice → hone until the skill passes, then reuse — measured at +31.8%/+39.8%, with
transferred skills improving weaker agents by up to 54.3%. (d) **Sizing calibrations →
the priors.** The 4–7 slice prior and the prescriptive/outcome defaults (item 3) update
from item 17's telemetry: which slice sizes actually failed, which mode actually won per
slice type.

The investment rule is the SDD durability asymmetry, verbatim: the technical harness
depreciates as models improve; the methodological harness — intent, norms, accumulated
decisions — appreciates. The roadmap/ADR tier and the skill registry are the appreciating
layer; this ritual is the scheduled transfer of value from the depreciating layer (this
run's harness calls and tokens) into the durable one (§4F).

*Evidence:* A — 2409.07429, 2504.07079, 2507.06229; B — 2308.10144, 2305.16291,
2609.00252, 2505.11814.

*What changes / cost:* the ritual (a chat-role step with a fixed prompt) plus the
registry format (one directory, one index file, embedding retrieval). Low per feature;
value grows with the feature count — the definition of a compounding investment.

**16. Hash-anchored, tamper-evident run record.**

*What it is.* The tracker's history becomes something an outsider can verify without
trusting the runtime. Statuses change only by *appended* events, and each event carries
the hashes of what it claims to have observed.

*How it works.* Three rules. (1) Tracker statuses flip only by appended events
(`SLICE2 CT3: UNVERIFIED → VERIFIED, ref: run-412`), never by in-place edits —
append-only is also the converged harness pattern. (2) Each event hashes what it claims:
the verify output, the diff SHA, and the eval verdict are hashed into the ledger entry.
(3) The hash chain: each event includes the previous event's hash, so a modified entry
breaks the chain visibly. The payoff is audit: a reviewer — human or agent, this year or
next — can check that SLICE2's VERIFIED status corresponds to a verify run whose output
matches, without re-running anything or trusting the runtime that recorded it. It is
also the audit substrate for item 17: telemetry that can be tampered with is not
evidence. No surveyed harness has the top rungs of the verifiability ladder (records
checkable without trusting the runtime) — this is cheap differentiation.

*Evidence:* B — 2608.23953 (empty-top-rung finding; append-only convergence).

*What changes / cost:* the tracker's write path (append-only, hashed, chained). Medium,
one-time. The precondition for trusting any of the telemetry items.

**17. Harness telemetry + attribution loop.**

*What it is.* Every run is logged in a stable schema. Periodically, the logs are analyzed
to find which harness component is responsible for which failures, and that component is
revised in a scoped, regression-checked way. The harness becomes a product with a
measured defect rate, instead of a set of prompts that change by vibes.

*How it works.* The schema per run: `(brief, plan_hash, per-role tokens/cost, diffs,
verify results, eval verdicts, failure packets, stall events, pass^k streaks, mode tag,
risk tag, outcome)`. Two near-term uses, both published. **(a) Attribution → scoped
revisions** — the HarnessFix pattern: map each failure to the component that caused it
(the plan, the prompt, the gate, the brief layout) and revise *that component*, scoped,
regression-checked against the item-12 slice-regression set before it goes live; measured
gains +6.3–18.4%. This is where the dials get tuned: item 3's mode defaults and the
slice-sizing prior update from the data, not opinion. **(b) Co-evolving verifiers** —
the eval rubric and the constraint tests are revised on a schedule from the failure log,
because verifiers get gamed (agents satisfy checks while violating intent) and a
co-evolved verifier outperforms a frozen one (verification capacity is the measured
bottleneck; keeping it trained against the current policy raises the ceiling, §F5).
Periodically the test suite gets a hack-check: can a deliberate agent satisfy the tests
while violating a contract? If yes, the test is upgraded. One invariant from the start:
every loop keeps one independent signal — the tests, an external checker, or the
different-family eval — because a correlated planner/eval pair will pass each other's
biases, and the loop will certify its own errors.

*Scope note:* the same schema is the substrate for RL training data (the R1/SWE-Gym line
uses exactly this shape). This system is not training models, so the schema is adopted
for attribution now — and the optionality is free: if fine-tuning ever happens, the data
is already being collected in the right format.

*Evidence:* A — 2606.06324; B — 2510.14253, 2608.22103; C — R1/SWE-Gym substrate.

*What changes / cost:* the run logger plus a periodic attribution job. High ongoing cost,
but the schema decision is cheap now and expensive later — retrofitting a log format is
much harder than starting with one. This is the item that makes every other item
*measurable*.

**18. Model tiering — planner-tagged, not learned (conditional).**

*What it is.* Different slices get different coder models, chosen by the tags the
planner already writes — not by a learned router, because the data for a learned router
does not exist yet.

*How it works.* The routing rule uses the tags from items 3 and 14. `STEPS: prescriptive`
+ small + `RISK: routine` → the cheap, fast coder: the plan is fully prescriptive, the
coder is executing a known diff, and the verify gate catches any error the cheap model
makes. `STEPS: outcome`, any repair attempts, N-version candidates (item 10), or `RISK:
elevated`+ → the frontier coder: the path is unknown or the stakes are high. The eval is
always the different-family model at least as strong as the coder (item 8) — never
tiered down, because a weak judge is the one place where cost-cutting silently corrupts
every other gate. The condition: revisit a *learned* cascade (FrugalGPT's mechanism —
up to 98% cost reduction at matched performance, or +4% accuracy at matched cost, §4J)
once item 17's telemetry has a few hundred slices; at that point the query-level outcome
data a learned cascade is trained on will exist, and the routing can be measured instead
of tagged.

*Evidence:* A — 2305.05176 (mechanism), 2410.21819; B — 2510.17109 (small executors work
when the planner carries the context); C — extrapolation to tag-based routing.

*What changes / cost:* role configuration (model per tag) — the tags already exist after
items 3 and 14. Low config cost, but adopt *after* item 17 can measure whether tiering
hurt. Premature tiering is the one cost-cut that corrupts the data it is meant to save
on.

### Considered, not adopted

- **Pure-code steps as a separate upgrade.** Folded into item 3's `(auto)` tag. The
  mechanism is real (Agentless economics) but it is one tag, not an item.
- **Pairwise-comparison eval format.** A judge-literature technique: show the judge two
  diffs, ask which is better. Rejected for this system's shape: the gate judges one diff
  against its own contracts, and pairwise adds cost without a verified benefit in that
  shape. Blindness plus a different family already carry the measured bias reduction.
- **"Single-agent always beats multi-agent" as a rule.** The census does not support the
  dogma: minimal roles plus scaffolding wins *on medians* (G4 55% vs G5 40.6%), but a
  tightly-scripted fixed multi-agent pipeline posted the top single Verified entry
  (63.4%, from a group of only 3 entries). The right rule is the operational one: do not
  add a role without a named failure mode it addresses (MAST: 3 of 14 failure modes are
  created by the structure), and do not forbid scripted pipelines.
- **A learned model cascade now.** Deferred to the item-18 condition. FrugalGPT's
  cascade is learned from query-level outcome data; without that data, the tags are the
  honest proxy, and the telemetry decides when to switch.

---

## 8. Goalposts — what "great results" currently looks like (Sept 2026)

| Benchmark | What it measures | Frontier number | Implication |
|---|---|---|---|
| SWE-bench Verified | 500 repo issues, functional tests | leaderboard high-70s/80s (as-reported; the Dissecting census max was 68.2% in May 2025) | Function-level: solved-ish — do not optimize here |
| SWE-bench Pro (2509.16941) | 1,865 enterprise issues, held-out, hours-to-days tasks | ~23% best (as-reported; not in the abstract) | the long-horizon acceptance gap lives here |
| PlanBench-XL (2606.22388) | 327 tool-use tasks, 1,665 tools, with blocking failures | 51.90% → **11.36%** under severe blocking | failure *handling* is the cliff → items 2, 6, 10 |
| TheAgentCompany (2412.14161) | 175 multi-stage professional tasks | ~30.3% of provided tests | multi-stage + self-verification bottleneck |
| PaperBench (2504.01848) | replicate ICML papers | 21.0% best agent (full, standard protocol); 3-paper subset: o1 26.6% vs human ML PhDs 41.4% (best of 3, 48 h) | open-ended long-horizon work still human-superior |
| τ-bench (2406.12045) | policy-following tool agents | gpt-4o 61.2% pass@1 retail / 35.2% airline; **pass^8 <25%** | consistency is the metric → item 12 |
| Terminal-Bench 2.1 (2601.11868; 2608.15089) | hard CLI tasks | 95.3% via **harness scaling** | the harness is the lever → items 1–7 |
| SWE-Lancer (2502.12115) | $1M of real freelance work | small fraction completed (as-reported) | error compounding + verification at real stakes |

**The read:** the frontier gap between the function level and the acceptance/
consistency/long-horizon level is precisely the gap this system's contracts, gates, dense
verification, and scoped contexts are built to close. Function-level benchmarks are
nearly saturated; the middle rows of the table are acceptance, consistency, and
long-horizon numbers. Judge the system on pass^k over a held-out slice-regression set —
never on one green feature.

---

## 9. Honest caveats

- **Domain transfer.** The plan-quality results (Plan-and-Act, Planner Matters, TDP)
  come from web/GUI/tool agents; VeriMAP's verification functions were validated on
  single-file code-generation benchmarks, not repo-level SWE. The *mechanisms* transfer;
  the exact gains may not. The directly transferable set is the SWE evidence (HoH,
  Agentless, Phoenix, SWE-Gate, SWE-bench Live), and it agrees on structure.
- **More structure is not more success.** MAST: 3 of 14 failure modes are *created* by
  multi-agent structure; Horizon Gap §3: over-decomposition misaligns guidance from
  execution needs. Every item in §7 must earn its keep in item 17's telemetry. The
  meta-recommendation the evidence supports: **ablate your own harness** — on/off deltas
  per component — before granting any component permanence.
- **Verifiers get gamed and must co-evolve** (HVTB; ASL). A frozen test suite is a
  target, not a guarantee. The constraint tests and eval rubrics are living artifacts.
- **Survey-mediated numbers.** The 2–3× plan-first economics and the 27.9%
  memory-interference figure come from the Horizon Gap survey's synthesis; the survey's
  text was checked, not every underlying primary. Both are consistent with the primary
  sources read directly (TDP, Plan-and-Act), which raises confidence without replacing
  it.
- **Benchmarks flatter.** A substantial share of reported SWE-bench solves reflect
  test-suite weakness or leakage (the Horizon Gap validity thread). SWE-bench Pro is the
  de-flattened number; prefer it when comparing long-horizon ability.
- **Recency and replication.** HoH, TDP, StateM, SWE-Gate, VeriMAP, the SDD cluster, and
  most 2026 items are preprints without venue peer review; several are single-team
  reports. They are internally consistent with the older peer-reviewed line (Plan-and-Act
  ICML'25, the self-conditioning result ICLR'26, MAST NeurIPS'25, LLM-Modulo ICML'24,
  τ-bench, SWE-agent), which raises confidence but does not replace replication.
- **Self-correction research is contested** (qualified intrinsic capability under narrow
  conditions, 2024–25). The conservative reading — ground everything external — is what
  this architecture already does. The one line not to cross: "let the model reflect on
  the diff" must never replace a test.

---

## 10. Evidence appendix — where the load-bearing claims come from

Check strength: **full text** = read in the paper's body; **abstract** = taken from the
abstract; **verbatim** = quoted directly; **as-reported** = the paper's own reported
number, not independently re-derived.

| Claim | Source | Check |
|---|---|---|
| Dissecting: G4 median 55% (n=7), G5 40.6% (n=13), G3 max 63.4% (n=3, median 50); groups differ significantly (Lite p=0.0070); census max 68.2% | 2506.17208 | full text, Table 9 + body |
| SWE-agent: 18.0% baseline (GPT-4, Lite); no-edit 10.3 (−7.7pp); 30-line 14.3 (−3.7pp); full-file 12.7 (−5.3pp); last-5-obs 18.0 vs full history 15.0; no-search 15.7 | 2405.15793 | full text, Table 3 |
| τ-bench: gpt-4o 61.2% pass@1 retail / 35.2% airline; pass^8 <25% | 2406.12045 | full text |
| PaperBench: 21.0% best agent (full, standard protocol); o1 13.2% full / 26.6% 3-paper subset; human PhDs 41.4% subset (best of 3, 48 h) | 2504.01848 | full text |
| SWE-bench Live: 48% (1 file / <5 lines); <10% (≥3 files or >100 lines); never solved (≥7 files) | 2505.23419 | full text, verbatim |
| METR: ~8.1 points per messiness factor; completable-task length doubles ~every 7 months; >80% of successful runs cost <10% of human time cost | 2503.14499 | full text |
| ~12% of best-LLM plans executable and goal-reaching | 2402.01817 | full text, verbatim |
| FrugalGPT: cascade matches best model at up to 98% cost reduction, or +4% accuracy at matched cost | 2305.05176 | abstract, verbatim |
| SkillWeaver: +31.8% WebArena / +39.8% real sites relative; up to +54.3% on transfer to weaker agents | 2504.07079 | abstract |
| PlanBench-XL: 51.90% → 11.36% under blocking; "especially vulnerable when failures lack explicit error signals…" | 2606.22388 | abstract, verbatim |
| SWE-Gate: 221 of 644 functionally-passing patches (34.3%) fail constraint validation | 2609.04167 | full text |
| VeriMAP: planner-authored Python verification functions; +4.05% BigCodeBench-Hard / +9.8% Olympiads | 2510.17109 | full text |
| HoH: +52.25% avg relative gain (3 harness×model pairs); 22%→72.7% FrontierSWE over 10 iterations; ablations −6.28pp (evidence-feeding), −8.1pp (frozen plan) | 2609.01481 | full text |
| Horizon Gap: 1,547 papers; 27.9% memory-interference accuracy; 2–3× plan-first token economics (scoped to well-specified tasks) | 2608.06663 | abstract + full text (survey-mediated primaries) |
| 1M–2M-token models degrade >50% at ~100K tokens | 2512.02445 | abstract |
| Noisy history: web-agent success 40–50% → <10%; failures = loops + lost objective | 2512.04307 | abstract |
| Magentic-One: stall counter (implementation continues while counter ≤ 2), 4-category task ledger, "force all agents to clear their contexts and reset their states" | 2411.04468 | full text, verbatim |
| StateM: 95.3% Terminal-Bench 2.1 via harness scaling | 2608.15089 | title/abstract |
| SDD: "a constraint that no tool can enforce is a wish…"; worktree "cornerstone"; appreciates/depreciates; graduated autonomy; Given–When–Then/Gherkin | 2609.00252 | full text, verbatim |
| ASL: "GRM verification capacity is the main bottleneck… raises the performance ceiling"; GRM > rigid rules (open-domain); co-evolution boosts | 2510.14253 | abstract, verbatim |
| TheAgentCompany: ~30.3% of provided tests | 2412.14161 | full text |
| MAST: 41.8/36.9/21.3 failure split; step repetition 17.1%; unasked assumptions 11.7%; objective-level +15.6pp; role specs +9.4% | 2503.13657 | full text |
| Agentless: fail-before/pass-after reproduction filter; majority vote over normalized patches; $0.70/task Lite win | 2407.01489 | full text |
| Phoenix: 10/11 real repos have pre-existing failures; ≤2 structured retries then human | 2606.20243 | full text |
| Plan-and-Act: +10.3pp dynamic vs static; +34pp plan quality; executor data ≈ nothing | 2503.09572 | full text |
| TDP: DAG + node-scoped contexts + local replan + Self-Revision; up to −82% tokens | 2601.07577 | full text |
| Self-conditioning: per-step error rises with own prior errors in context; history-removal fixes | 2509.09677 | full text |
| HVTB: agents "satisfy checks while violating intent"; prompting mitigates known, not unknown, hacks | 2608.22103 | abstract |
| Self-preference: GPT-4 judge significantly self-preferring, correlated with low-perplexity outputs | 2410.21819 | abstract |
| More Agents: sampling-and-voting scales with k and with difficulty, orthogonal to other methods | 2402.05120 | abstract |
| SWE-bench Pro ~23% best; SWE-bench Verified high-70s/80s | 2509.16941; leaderboards | as-reported (not in abstracts) |
| All arXiv IDs cited in this note | arXiv API | resolve, titles match |

---

## 11. References

**Verification-aware planning & contracts:** 2510.17109 (VeriMAP) · 2609.04167
(SWE-Gate) · 2609.00252 (SDD for Agentic SE) · 2602.00180 (SDD: Code to Contract) ·
2602.02584 (Constitutional SDD) · 2608.25202 (SpecMine) · 2603.25697 (Kitchen Loop) ·
2406.12045 (τ-bench) · 2312.08935 (Math-Shepherd) · 2605.10325 (VPR) · 2605.20061
(consistency-guided credit assignment) · 2608.22103 (Hack-Verifiable Terminal Bench) ·
2510.14253 (ASL) · 2206.10498 (LLM-Modulo) · 2312.13010 (AgentCoder)

**Controller mechanics & orchestration:** 2411.04468 (Magentic-One) · 2402.05120 (More
Agents) · 2504.16563 (GoalAct) · 2308.00352 (MetaGPT) · 2311.05772 (ADaPT) ·
2304.11477 (LLM+P) · 2502.11221 (PlanGenLLMs) · 2505.19683, 2502.12435 (planning
surveys)

**Long-horizon benchmarks & goalposts:** 2608.06663 (Horizon Gap) · 2509.16941
(SWE-bench Pro) · 2606.22388 (PlanBench-XL) · 2601.11868 (Terminal-Bench) ·
2607.08964 (LH-Terminal-Bench) · 2608.15089 (StateM) · 2502.12115 (SWE-Lancer) ·
2506.17208 (Dissecting SWE-bench) · 2504.01848 (PaperBench) · 2412.14161
(TheAgentCompany) · 2505.23419 (SWE-bench Live)

**Long-context degradation:** 2512.02445 (When Refusals Fail) · 2512.04307
(long-context WebAgents) · 2602.07962 (LOCA-bench) · 2307.03172 (Lost in the Middle) ·
2512.22733

**Distillation & the durable layer:** 2308.10144 (ExpeL) · 2504.07079 (SkillWeaver) ·
2304.03442 (Generative Agents) · 2305.16291 (Voyager) · 2409.07429 (AWM) ·
2310.08560 · 2406.02818 · 2507.13334

**Cost, judges, ambiguity:** 2305.05176 (FrugalGPT) · 2410.21819 (Self-Preference Bias)
· 2507.21285 · 2605.09698 (Ambig-DS) · 2605.17324 (ASPI) · 2505.11814 (ChatHTN)

**Planning limits & self-correction:** 2402.01817 (LLMs Can't Plan / LLM-Modulo
companion) · 2409.13373 (LRMs on PlanBench) · 2310.01798 (self-correction limits) ·
2303.11366 (Reflexion) · 2305.11738 (CRITIC) · 2305.20050 (PRM)

**Harness & spec-driven development:** 2605.18747 (harness survey) · 2608.23953
(Empire) · 2606.06324 (HarnessFix) · 2410.10762 (AFlow) · 2604.05278 (Spec Kit Agents) ·
2608.20341 (SDAD) · 2606.22528 (Governance Decay) · 2609.01481 (HoH) · 2407.01489
(Agentless) · 2606.20243 (Phoenix) · 2403.17927 (Magis) · 2507.06229 (Agent KB) ·
2405.15793 (SWE-agent) · 2503.13657 (MAST) · 2503.09572 (Plan-and-Act) · 2605.02168
(Planner Matters) · 2601.07577 (TDP) · 2312.04511 (LLMCompiler) · 2305.18323 (ReWOO) ·
2305.16653 (AdaPlanner) · 2503.14499 (METR) · 2509.09677 (Illusion of Diminishing
Returns) · 2510.11967 (Context-Folding) · 2601.18285 (U-Fold)
