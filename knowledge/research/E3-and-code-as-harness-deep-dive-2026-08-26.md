# Deep Research: E3 & Code-as-Harness — Mapping to First-Agent

> **Sources:**
> - E3: "Do AI Agents Know When a Task Is Simple?" (arxiv 2607.13034, Jul 2026)
> - CaH: "Code as Agent Harness" (arxiv 2605.18747, May 2026; 197-paper survey)
>
> **Purpose:** Extract actionable insights, map to FA architecture, identify
> implementation opportunities. For future feature development context.
>
> **Method:** Full-text reading of both papers (sections 1-10 of E3; complete
> survey summary of CaH). Every claim below is evidence-backed from the papers.

---

## Part I: E3 — Estimate, Execute, Expand

### 1. Core Thesis (Verbatim from Paper)

> "Truly efficient intelligence is not only the ability to solve hard problems
> but also the ability to recognize when a problem is easy — and to act
> accordingly. The aim is not to think less for its own sake but to judge the
> task correctly first."

> "A competent agent, like a competent solver, should not search an unstructured
> state space exhaustively. It should exploit task structure, observable
> environment state, and verifiable checks to anchor itself in a reasonable
> initial operating region, and expand computation only when the evidence
> demands it."

### 2. The Problem: Maximum-Context-First

The paper names the disease that FA's `fa run` can suffer from:

**Maximum-Context-First (MCF)** — the agent re-reads files and dependencies
it has already seen, turning a one-line edit into a small codebase audit.

**Concrete example from the paper:** A home page has two email links. Task:
"replace the second icon with the markup used by the first." A frontier agent
spends several minutes: re-reading the icon library, re-browsing the site
directory, re-analyzing project architecture, re-confirming dependencies —
before making a two-line change. The edit is correct but the *path* is
grossly over-provisioned.

**Why this matters for FA:** When a user types `fa run -r coder "fix typo in
README.md"`, the coder may spend 20+ turns reading project structure, searching
for files, exploring the workspace — when the task requires exactly one
`fs_edit_file` call. This is the MCF pattern.

### 3. Formal Framework

#### 3.1 Trajectory Cost Function

```
C(π) = α·T_latency + β·N_tokens + γ·N_tool_calls + δ·N_files_inspected
```

Where:
- `α=1.0` per second (wall-clock)
- `β=0.02` per token
- `γ=0.5` per tool call
- `δ=1.5` per fully inspected file (the "canonical unit of redundancy")

**FA mapping:** These map directly to `fa stats` metrics. FA already tracks
all four axes. The insight is that `δ` (files pulled into context) is the
**dominant** cost axis — reading an irrelevant file charges on three axes at
once (time + tokens + file count).

#### 3.2 Minimum-Sufficient Execution (π*)

The cheapest trajectory that meets a reliability target:

```
π* = argmin C(π)  s.t.  P(success|π,τ) ≥ 1-ε
```

**FA mapping:** This is what a well-tuned `fa run` should produce. The gap
between FA's actual cost and π* is the optimization target.

#### 3.3 Agent Cognitive Redundancy Ratio (ACRR)

```
ACRR(τ) = (C_actual(τ) - C_min(τ)) / C_min(τ)
```

- ACRR = 0 → optimally lean
- ACRR = 4 → agent spent 5× the necessary cost (400% redundancy)
- Defined only for successful runs (cheap failure ≠ efficiency)

**Key finding: ACRR is HIGHEST on the SIMPLEST tasks.**

| Task Level | MCF ACRR | E3 ACRR |
|---|---|---|
| Level 1 (single-file) | 22.1 | 0.64 |
| Level 2 (cross-file) | 11.0 | 0.26 |
| Level 3 (repo-level) | 5.4 | 0.73 |

**FA mapping:** This means FA's overhead is most wasteful for small, routine
tasks — exactly the tasks users run most frequently. A `fa run -r coder` on a
simple bug fix may have ACRR > 10 without scope estimation.

#### 3.4 The Initial Operating Point (x₀)

```
x₀ = f(q, E, M) = (d̂, ŝ, r̂, ĉ)
```

Where:
- `d̂` = estimated difficulty (L1/L2/L3)
- `ŝ` = estimated scope (files/sites to touch)
- `r̂` = estimated risk (low/medium/high)
- `ĉ` = confidence in the estimate

**The power-flow analogy:** A Newton-Raphson solver doesn't enumerate the state
space. It computes a structured initial operating point (flat start or DC
estimate) and refines. A good initial point is rarely the exact answer, but it
makes convergence fast and stable. The paper measured this on a real 3-bus
power system: good initial points converge in 3 iterations with 100% reliability;
distant guesses diverge to 0% reliability.

**FA mapping:** The chat role's classifier IS the initial operating point
estimator. `invoke_workflow` is the expansion mechanism. The estimate should be
cheap and optimistic, with verification as the safety net.

### 4. The E3 Algorithm

```
Algorithm 1: E3: Estimate, Execute, Expand
Require: task τ=(q,E,V), estimator f, max expansions K

1: x₀ ← f(q,E,M)           ▷ Estimate: ≤1 cheap probe
2: ℓ ← d̂;  ℋ ← cached search hits
3: ok ← Execute(τ, ℓ, x₀, ℋ)
4: k ← 0
5: while ¬ok and ℓ < 3 and k < K do
6:     ℓ ← ℓ + 1;  k ← k + 1    ▷ Expand one scope level
7:     ok ← Execute(τ, ℓ, x₀, ℋ)
8: end while
9: return ok
```

**Three scope levels:**
- **Level 1:** Localize single site, edit it (keyword locate-and-replace)
- **Level 2:** Reuse cached search hits, read them, edit direct sites
- **Level 3:** Follow imports (dependency_trace), inspect importer files

**The estimator is deliberately imperfect:** Some tasks that read as local
hide an indirect dependency. The Expand stage exists to recover these cases,
so the estimator can be cheap and optimistic rather than exhaustive.

**FA mapping:**
```
Level 1 → handle directly in chat (single file, simple edit)
Level 2 → plan briefly + code in chat (2-3 files)
Level 3 → invoke_workflow (multi-file, architectural)
```

### 5. Estimation: How It Works

The estimator uses **lexical cues + one optional structural probe:**

1. **Explicit file references** + localized verbs ("replace ... in index.html")
   → single-file edit (Level 1)
2. **Broad-scope cues** ("refactor across the codebase", "every call site")
   → repository-level change (Level 3)
3. **Otherwise:** one search for the salient token, count occurrences to
   distinguish local from cross-file work (Level 1 or 2)
4. **When wording and structure conflict** (localized phrasing but multiple
   occurrences) → lower confidence ĉ, flag for expansion

**FA implementation pattern:**
```python
def estimate_scope(task: str) -> OperatingPoint:
    # Lexical cues (no tool call)
    file_refs = count_file_references(task)
    has_broad_cues = any(
        w in task.lower() for w in ["refactor", "migrate", "across", "every call site", "all modules", "codebase-wide"]
    )
    has_security_cues = any(w in task.lower() for w in ["auth", "permission", "secret", "sandbox", "security"])
    has_architectural_cues = any(w in task.lower() for w in ["redesign", "restructure", "new subsystem", "protocol"])

    if has_broad_cues or has_architectural_cues:
        return OperatingPoint(d=3, s="repo", r="high", c=0.7)
    elif file_refs <= 1 and not has_security_cues:
        return OperatingPoint(d=1, s="single-file", r="low", c=0.8)
    else:
        return OperatingPoint(d=2, s="cross-file", r="medium", c=0.6)
```

### 6. Results — What the Numbers Actually Say

#### 6.1 Capability-Controlled Simulator (MSE-Bench, 121 tasks)

| Metric | Max-Context-First | Adaptive Retrieval | E3 | Oracle |
|---|---|---|---|---|
| Success | 100% | 100% | 100% | 100% |
| Cost | 122.85 | 22.08 | 18.55 | 11.74 |
| ACRR | 12.90 | 1.21 | 0.55 | 0.00 |
| Files inspected | 8.4 | 1.99 | 0.66 | — |
| Tokens | 4421 | 4106 | 4037 | — |

**E3 vs MCF:** 85% cost reduction, 91% token reduction, 92% file reduction.
**E3 vs Adaptive Retrieval:** 16% cheaper at same success.

#### 6.2 Ablation: What Each Stage Does

| Variant | Success | Cost | ACRR |
|---|---|---|---|
| E3 (full) | 100% | 18.55 | 0.55 |
| − Expand | 85.1% | 14.88 | 0.47 |
| − Estimate | 100% | 22.21 | 0.71 |

**Without Estimate:** agent always starts minimal, pays for expansion on every
non-trivial task. Cost rises 20% overall, 36% on Level 3.
**Without Expand:** agent cannot recover under-estimated tasks. Success falls
to 85.1%.

**The insight:** Estimation cuts cost. Expansion preserves success. They are
**complementary** — estimation is the optimizer, expansion is the safety net.

#### 6.3 Real-Model Validation (LLM-Case, gpt-4o)

Five tasks over the real `toml` 0.10.2 package, three runs per cell:

- **Frontier models are more frugal than MCF assumes:** gpt-4o inspects only
  1-4 files even under "read everything first" instruction
- **E3 is the leanest and fastest policy overall:** 18% fewer real tokens
  than thorough agent, 4% fewer than ReAct
- **Aggressive over-reading carries an operational tax:** The highest-token
  trajectories are also the slowest and the ones that hit step/rate limits
  and fail
- **Level-3 deceptive tasks are stochastic:** The identity of the failing
  policy *moves* across runs — this is the honest finding

**Key honest caveat from the paper:**
> "E3's benefit relocates from 'always dramatically cheaper' (the simulation's
> headline) to 'the leanest policy overall, and one that does not spend itself
> into failure as hidden coupling grows.'"

### 7. What E3 Is NOT

The paper is explicit about this:

1. **Not routing.** Routing chooses *which engine* from a fixed menu. E3
   predicts *what scope the task needs* and constructs a minimum-viable plan.
2. **Not adaptive computation.** Adaptive computation dials *how much* to think.
   E3 asks *what to understand before thinking*.
3. **Not always cheaper on hard tasks.** On genuinely hard Level-3 tasks,
   a thorough adaptive agent is competitive. E3's advantage is concentrated
   on Level-1 and Level-2 tasks (45% and 43% cheaper than Adaptive Retrieval).

**FA implication:** E3 is not a replacement for FA's workflow. It's a
**front-end classifier** that decides whether to use `fa run` (simple) or
`fa workflow` (complex). The workflow itself remains the thorough agent for
hard tasks.

---

## Part II: Code as Agent Harness (CaH)

### 8. Core Thesis

> "Code is no longer only a target output. It increasingly serves as an
> operational substrate for agent reasoning, acting, environment modeling,
> and execution-based verification."

Code has three properties that make it uniquely suited as an agent substrate:

| Property | What It Means | FA Implementation |
|---|---|---|
| **Executability** | Model outputs become verifiable operations | `fs_run_bash`, `just check`, pytest |
| **Inspectability** | Intermediate computation exposed as structured traces | `events.jsonl`, `session.db`, `flow_state.json` |
| **Statefulness** | Task progress represented persistently | `session.db` (3 tables), blackboard, pr_draft.md |

**FA already implements all three properties.** This validates FA's architecture
as a correct instantiation of the code-as-harness pattern.

### 9. Three-Layer Framework — FA Mapping

#### Layer 1: Harness Interface

| Interface | CaH Definition | FA Implementation |
|---|---|---|
| **Reasoning** | Externalizes internal logic into verifiable computation | `fs_search` (FTS5 BM25), `fs_blackboard_query`, structural index |
| **Acting** | Generated programs as policies, tool calls, reusable skills | `fs_edit_file`, `fs_write_file`, `fs_run_bash` + IntentGuard |
| **Environment Modeling** | Repos, test suites as environment model | Workspace clone (`/sessions/<id>`), `just check` as feedback |

#### Layer 2: Harness Mechanisms

| Mechanism | CaH Definition | FA Implementation |
|---|---|---|
| **Planning** | Decompose intent into executable steps | Planner role + plan-authoring skill + `pr_draft.md` |
| **Memory** | Context vs externally stored | Mechanical Wiki (FTS5), session.db, compactor role |
| **Tool Usage** | Typed schemas, sandboxes, verification | ADR-7 tool registry, bash intent analysis, path containment |
| **Iterative Debugging** | Execution failures → corrective actions | `just check` gate chain, pytest feedback loop |
| **Feedback-Driven Control** | Adaptive optimization | ADR-10 deterministic harness invariants, authoring guardrails |

#### Layer 3: Harness Scaling

| Dimension | CaH Definition | FA Implementation |
|---|---|---|
| **Role specialization** | Synthesizers, understanders, verifiers | planner, coder, eval (ADR-2 family disjointness) |
| **Interaction modes** | Collaboration, critique, debate | Workflow linear/repair/adaptive modes |
| **Workflow topologies** | Hierarchical, adaptive, execution-driven | `fa workflow` controller + FlowState |
| **State convergence** | Test-gated, consensus-based | eval verdict (PASS/REPAIR/REPLAN/BLOCKED) |

### 10. The Topology-Formality Finding (Most Important for FA)

> "Topology complexity inversely correlates with harness-state formality.
> Systems WITH formal shared state have simpler topologies. Systems WITHOUT
> formal shared state compensate with increasingly complex topologies —
> topology complexity is partially a symptom of missing formal substrate."

> "When the substrate is formally represented and queryable, agents can
> coordinate through simple, transparent protocols."

**This is FA's §1.2.6 Substrate Formality Principle, independently validated
by a 197-paper survey.** FA's blackboard with `read_set`/`write_set`/
`detect_conflict()` and content hashing is exactly the formal substrate the
survey identifies as enabling simpler topologies.

**FA implication:** FA should NOT add parallel agents, complex DAGs, or
multi-agent debate loops until the formal substrate (blackboard, session.db,
FlowState) is fully exploited. The current sequential planner→coder→eval
pipeline with strong artifacts IS the right topology for FA's substrate
formality level.

### 11. The PEV Loop (Plan-Execute-Verify)

The survey identifies the PEV loop as the **canonical harness control pattern:**

1. **Planning as Contract Formation** — the planner produces an execution
   contract (not just a to-do list)
2. **Sandboxed Execution** — the coder executes in an isolated workspace
3. **Verification through Deterministic Sensors** — the eval judges against
   the contract, not against vibes

**FA mapping:** This IS `fa workflow planner,coder,eval`. The planner produces
`pr_draft.md` (contract), the coder executes in `/sessions/<id>` (sandbox),
the eval produces `eval_report.json` (deterministic sensor). FA's implementation
is a textbook instantiation of the PEV loop.

### 12. Five Synchronization Mechanisms

The survey identifies five mechanisms for shared-harness synchronization:

| Mechanism | CaH Definition | FA Status |
|---|---|---|
| **Sequential handoff** | Roles pass artifacts in order | ✅ `fa workflow` linear mode |
| **Blackboards** | Shared state with conflict detection | ✅ `session.db.blackboard` with `detect_conflict()` |
| **Parallel branches with merge** | Multiple agents work simultaneously | ❌ Deferred (no parallel subagents yet) |
| **Structured context scheduling** | Per-role conversation management | ✅ Per-role system prompts + shared conversation history |
| **Hierarchical memory** | Multi-level persistent state | ✅ Mechanical Wiki + FTS5 + session.db |

**FA implication:** FA has 4/5 mechanisms implemented. The missing one
(parallel branches) is correctly deferred — adding it before the substrate is
fully exploited would be "topology complexity as symptom of missing formal
substrate."

### 13. Agentic Harness Engineering (Self-Improving Harnesses)

> "An evolution agent iteratively modifies harness components through
> edit-execute-evaluate loops while capturing versioned agent snapshots,
> budget-controlled evaluation, and structured execution traces."

The survey identifies seven orthogonal harness components that can be
independently evolved:
1. System prompts
2. Tool definitions
3. Retrieval/routing
4. Orchestration code
5. Guardrails
6. Memory management
7. Output formatting

**FA mapping:** FA's skill system (`SKILL.md` files) + plan-authoring +
tests-writing skills are exactly this pattern. The agent can write new skills
from completed tasks (Pillar 4: iteration via measurement). The `feature-planning`
skill is the harness engineering meta-skill.

### 14. Best Practices from CaH — FA Compliance Check

| Best Practice | FA Status | Notes |
|---|---|---|
| Route reasoning through code execution | ✅ | `just check`, pytest, bash intent analysis |
| Use code artifacts as persistent memory | ✅ | pr_draft.md, eval_report.json, flow_state.json |
| Use shared code artifacts for multi-agent coordination | ✅ | session.db blackboard, workspace clone |
| Build iterative debugging loops | ✅ | coder loop with tool feedback, repair mode |
| Represent environment state in code | ✅ | workspace clone, test suites |
| Expose tools via typed schemas | ✅ | ADR-7 tool registry with parameter validation |
| Governed harness mutation | ✅ | ADR-11 TCB, authoring guardrails, test-decay lock |

**FA scores 7/7 on the CaH best practices checklist.** This is strong validation.

---

## Part III: Synthesis — Ideas for First-Agent

### 15. The Chat Role as E3 Estimator

The E3 framework maps directly to FA's planned "chat" role:

```
User: "Fix typo in README.md"
     ↓
Chat Role (E3 Estimate stage):
  Lexical probe: single file mentioned, localized verb, no broad cues
  → x₀ = (d̂=1, ŝ=single-file, r̂=low, ĉ=0.9)
     ↓
Execute at Level 1:
  fs_read_file("README.md") → find typo → fs_edit_file → done
  → Total: 2 tool calls, ~500 tokens
     ↓
Verification:
  Read the edited section → looks correct → success
```

vs.

```
User: "Refactor the workflow controller to support parallel execution"
     ↓
Chat Role (E3 Estimate stage):
  Lexical probe: architectural cues ("refactor", "parallel execution"),
  broad scope ("controller" = cross-module)
  → x₀ = (d̂=3, ŝ=repo, r̂=high, ĉ=0.7)
     ↓
invoke_workflow(task, roles="planner,coder,eval", mode="adaptive")
     ↓
Workflow handles the complexity:
  Planner → reads codebase, produces plan
  Coder → implements changes
  Eval → verifies against plan contract
  → Expand to adaptive if eval says REPLAN_REQUIRED
```

### 16. ACRR as a First-Agent Metric

FA could track ACRR per session as a harness efficiency metric:

```python
def compute_acrr(session_outcome: SessionOutcome, oracle_cost: float) -> float:
    """Agent Cognitive Redundancy Ratio for this session."""
    actual_cost = (
        1.0 * session_outcome.latency_seconds
        + 0.02 * session_outcome.total_tokens
        + 0.5 * session_outcome.tool_calls
        + 1.5 * session_outcome.files_inspected
    )
    return (actual_cost - oracle_cost) / oracle_cost if oracle_cost > 0 else 0
```

**Practical challenge:** Computing `C_min` (the oracle minimum) requires
knowing the minimum-sufficient trajectory. For FA's self-development tasks,
this could be approximated by:
- Count of files actually changed in the final diff
- Minimum tool calls to make those changes
- Minimum tokens to read those files

This is computable post-hoc from the session's `events.jsonl`.

**FA implementation:** Add `acrr_estimate` to `fa stats` output. Start with
a simplified version: `files_read / files_changed` as a proxy for the file
axis of ACRR.

### 17. Progressive Expansion for FA Workflow

E3's "expand only on failure" pattern maps to FA's workflow modes:

```
Level 1 (chat, direct) → fails? → escalate to Level 2
Level 2 (chat, plan+code) → fails? → escalate to Level 3
Level 3 (workflow, linear) → fails? → escalate to adaptive
Level 3 (workflow, adaptive) → fails? → report to user
```

This is the **E3 expansion ladder** applied to FA's orchestration levels.

**Implementation:**
```python
def run_with_expansion(task: str) -> SessionOutcome:
    # Level 1: try direct in chat
    outcome = run_chat_direct(task, scope="minimal")
    if outcome.verified:
        return outcome

    # Level 2: plan briefly, then code
    outcome = run_chat_direct(task, scope="planned")
    if outcome.verified:
        return outcome

    # Level 3: full workflow
    outcome = invoke_workflow(task, mode="linear")
    if outcome.eval_report.verdict == "PASS":
        return outcome

    # Expand: adaptive mode
    outcome = invoke_workflow(task, mode="adaptive")
    return outcome
```

### 18. The "Initial Operating Point" for FA Sessions

The power-flow analogy suggests FA should compute an initial operating point
for every session:

```python
@dataclass
class InitialOperatingPoint:
    difficulty: int  # 1, 2, or 3
    estimated_scope: list[str]  # files likely to change
    estimated_tools: list[str]  # tools likely needed
    risk: str  # low, medium, high
    confidence: float  # 0.0 to 1.0
    recommended_mode: str  # "chat_direct", "chat_planned", "workflow_linear", "workflow_adaptive"
```

This could be computed in <100ms by a deterministic function (no LLM call),
using:
- Lexical analysis of the task text
- Blackboard metadata (what files exist, their complexity)
- Session history (has this file been edited before?)
- Code health signals (from Triage paper: complexity of affected modules)

### 19. CaH Validation of FA's Design Decisions

The CaH survey validates several of FA's most distinctive design choices:

| FA Decision | CaH Validation |
|---|---|
| **Sequential planner→coder→eval** | "When substrate is formally represented, simple topologies work" (§4.4) |
| **Blackboard with conflict detection** | "Blackboard / shared-state representation" is the most formal harness substrate (§4.3.1) |
| **eval_report.json as machine truth** | "Code artifacts as coordination surface" prevents silent failures (§Best Practices) |
| **ADR-11 TCB (frozen stdlib kernel)** | "Governed harness mutation: changes to safety-critical boundaries require human approval" (§3.5.3) |
| **ADR-12 egress proxy** | "Sandboxed execution and permissioned state transition" (§3.4.3) |
| **Plan-authoring skill with kill-checks** | "Planning as contract formation" (§3.4.2) + "Verification through deterministic sensors" (§3.4.4) |
| **No parallel subagents yet** | "Topology complexity is symptom of missing formal substrate" (§4.4) |
| **session.db as authority** | "Statefulness: task progress represented persistently" (§1) |

### 20. Ideas for Future Development

Based on both papers, here are concrete, prioritized ideas:

#### High Priority (Validated by Both Papers)

**I-1: Chat role with E3 estimator**
- Deterministic scope classifier (lexical + blackboard probe)
- Maps to E3's x₀ estimation
- Routes to direct/plan/workflow based on difficulty
- Cost: ~0 (no LLM call for classification)

**I-2: `invoke_workflow` tool**
- Chat role can call workflow as a tool
- Shared session context (no information loss)
- Linear mode default, adaptive on failure
- Maps to E3's Expand stage

**I-3: ACRR tracking in `fa stats`**
- Post-hoc computation from session events
- `files_read / files_changed` as proxy metric
- Track over time to measure harness efficiency improvements
- Maps to E3's formal ACRR metric

#### Medium Priority (Validated by CaH)

**I-4: Structured execution-evidence artifact**
- Coder produces machine-readable evidence of what changed
- Eval reads evidence mechanically, not just prose
- Maps to CaH's "code artifacts as coordination surface"
- Currently deferred in FA's operator memo (Option D)

**I-5: `workflow status` command**
- Read `flow_state.json` + `eval_report.json` and present human-readable summary
- Maps to CaH's "inspectability" property
- Currently deferred in FA's operator memo (Option B)

**I-6: Harness self-evaluation loop**
- Track which skill/strategy was used per task
- Measure success rate and ACRR per strategy
- Feed back into the classifier's decision thresholds
- Maps to CaH's "agentic harness engineering" (§3.5)

#### Lower Priority (Interesting but Premature)

**I-7: Learned routing classifier**
- Train on (task features, optimal strategy) pairs
- AdaptOrch §7.1 future work
- Requires benchmark data first (I-3 must land first)

**I-8: Parallel branches with merge**
- Only after substrate is fully exploited
- CaH says: "topology complexity is symptom of missing formal substrate"
- FA's substrate is strong but not yet fully exploited

**I-9: Dynamic re-orchestration mid-execution**
- Change topology during workflow based on partial results
- AdaptOrch §7.1 future work
- Complex, risky, premature for FA's current maturity

---

## Part IV: Principles Extracted

### 21. Engineering-Grounded AI (EGAI)

From E3:
> "An agent's reasoning and action should be anchored in the physical,
> model-based, and procedural reality of the task rather than in
> unconstrained search."

**FA principle:** FA's tools are already anchored in engineering reality
(bash intent analysis, path containment, AST-based authoring checks, FTS5
retrieval). The E3 paper says this anchoring should extend to **effort
allocation** — the agent should estimate task scope from engineering signals
before committing compute.

### 22. The Optimistic Estimator Principle

From E3:
> "The estimator should be optimistic and inexpensive, with verified expansion
> as the safety net that makes such optimism safe."

**FA principle:** The chat classifier should bias toward UNDER-estimating
complexity (optimistic), because:
1. Over-estimating wastes tokens on simple tasks (the main problem)
2. Under-estimating is recovered by the Expand stage (workflow escalation)
3. The cost of a false positive (unnecessary workflow) is higher than a
   false negative (one expansion round)

### 23. The Complementary Stages Principle

From E3 ablation:
> "Estimation reduces cost. Expansion protects reliability. The two stages
> are complementary."

**FA principle:** Do NOT choose between "smart routing" and "thorough workflow."
Both are needed:
- Smart routing (Estimate) → saves tokens on simple tasks
- Thorough workflow (Expand) → catches what routing missed
- Without routing → waste on simple tasks
- Without workflow → fail on complex tasks

### 24. The Formal Substrate Principle

From CaH:
> "Topology complexity inversely correlates with harness-state formality."

**FA principle:** Invest in substrate (blackboard, session.db, artifacts)
BEFORE investing in topology (parallel agents, debate loops, DAG orchestration).
FA's current substrate is strong. The next investment should be exploiting it
better (classifier, ACRR tracking), not adding topology complexity.

### 25. The Code-as-Coordination Principle

From CaH:
> "Prose handoffs between agents cause silent failures. Use shared code
> artifacts as the coordination surface."

**FA principle:** FA's `eval_report.json` and `flow_state.json` are the right
pattern. Never let the workflow controller parse prose to make routing
decisions. The eval role's machine-readable verdict IS the routing signal.

---

## 26. Summary: What FA Should Build Next

Based on thorough reading of both papers, the highest-value next steps are:

1. **Chat role with E3-style estimator** (I-1) — deterministic, cheap,
   validated by E3's 85% cost reduction
2. **`invoke_workflow` tool** (I-2) — the escalation mechanism, validated
   by Claude Code's "ultracode" and E3's Expand stage
3. **ACRR tracking** (I-3) — measure what you want to improve, validated
   by E3's formal framework

These three form a coherent unit: **estimate → execute → expand**, implemented
as **chat → code → workflow**.

Everything else (parallel agents, learned routing, dynamic re-orchestration)
is correctly deferred until these foundations are measured and proven.
