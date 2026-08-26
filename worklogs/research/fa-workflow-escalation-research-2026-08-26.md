# Research: Task Classification & Workflow Escalation Patterns (2026-08-26)

> **Research question:** What are the verified, reliable patterns for automatic
> task complexity classification and workflow escalation in LLM coding agents?
> Focus: "chat → classify → escalate to workflow" architecture.
>
> **Method:** 4-pass web research across arxiv papers (2025-2026), production
> agent systems, and trusted community sources.

---

## 0. Executive Summary

The problem you're solving — automatic task triage with escalation to heavier
orchestration — is an **active research frontier** in mid-2026. Multiple papers
and production systems are converging on the same pattern: **estimate before
committing budget.** The strongest evidence comes from three independent sources:

1. **E3 framework** (arxiv 2607.13034) — 85% cost reduction with matching success
2. **AdaptOrch** (arxiv 2602.16873) — 12-23% accuracy improvement via topology routing
3. **Claude Code Dynamic Workflows** (Anthropic, May 2026) — production-proven
   "ultracode" auto-escalation pattern

**Key finding for FA:** Your existing architecture (shared conversation + role-specific
prompts + structured artifacts) is **validated** by the "Code as Agent Harness" survey
(arxiv 2605.18747), which found that "topology complexity inversely correlates with
harness-state formality" — exactly your §1.2.6 Substrate Formality Principle.

---

## 1. Most Relevant Papers (Ranked by Applicability)

### 1.1 E3: Estimate, Execute, Expand (arxiv 2607.13034, July 2026)

**The single most relevant paper for your problem.**

**Core thesis:** LLM agents follow a "maximum-context-first" strategy — re-reading
files and dependencies they've already seen — turning a one-line edit into a
small codebase audit. The missing capability is **task-aware execution-scope
estimation**: judging difficulty, information needs, and shortest reliable path
**before** committing budget.

**The E3 algorithm:**
```
1. ESTIMATE: Produce initial operating point x₀ = (difficulty, scope, risk, confidence)
   using ≤1 cheap probe (lexical + one tool call)
2. EXECUTE: Run minimum viable path sized to x₀
3. EXPAND: Only if verification fails, widen scope (≤K expansions)
```

**Results:**
- Matches 100% success rate of strongest baseline
- Cuts cost by 85%, tokens by 91%, inspected files by 92%
- Beats adaptive retrieval baseline by 16%
- Redundancy is **largest on the simplest tasks** (the exact problem you're solving)

**Formalized concept — Agent Cognitive Redundancy Ratio (ACRR):**
The ratio of actual effort spent to minimum-sufficient effort. Current agents
have high ACRR because they over-gather context on simple tasks.

**Direct applicability to FA:**
Your "chat role with classifier" is essentially the E3 "Estimate" stage. The
`invoke_workflow` tool is the "Expand" stage. The key insight: **the estimate
should be cheap** (≤1 LLM call with lexical signals), not a full planning pass.

**Implementation pattern from E3:**
```python
def estimate_scope(task: str, workspace: Path) -> OperatingPoint:
    """≤1 cheap probe. Lexical signals + one grep."""
    signals = {
        "file_count_mentioned": count_file_refs(task),
        "has_architectural_keywords": bool(re.search(r"refactor|migrat|redesign", task)),
        "has_security_keywords": bool(re.search(r"auth|secret|permission|sandbox", task)),
        "task_length_words": len(task.split()),
    }
    # Transparent rule-based classifier (no extra LLM call)
    difficulty = classify_difficulty(signals)  # L1/L2/L3
    scope = estimate_scope(difficulty)  # files/tools needed
    risk = estimate_risk(signals)  # low/medium/high
    confidence = 0.7 if signals_are_clear(signals) else 0.4
    return OperatingPoint(difficulty, scope, risk, confidence)
```

### 1.2 AdaptOrch: Task-Adaptive Multi-Agent Orchestration (arxiv 2602.16873, Feb 2026)

**Core thesis:** When LLM capabilities converge, **orchestration topology** dominates
system performance over model selection. Tasks decompose into DAGs, and structural
properties (parallelism width ω, critical path depth δ, inter-subtask coupling γ)
predict optimal topology with high accuracy.

**The Topology Routing Algorithm (O(|V|+|E|)):**
```
Input: Task DAG with structural properties (ω, δ, γ)
If ω > θ_ω and γ < θ_γ → PARALLEL topology
If δ > θ_δ and γ > θ_γ → SEQUENTIAL topology
If ω > θ_ω and γ > θ_γ → HIERARCHICAL topology
Otherwise → HYBRID topology
```

**Results:**
- 12-23% improvement over static single-topology baselines
- Validated on SWE-bench (coding), GPQA (reasoning), RAG tasks
- Routing overhead: <50ms per task (Python, single CPU)

**Direct applicability to FA:**
Your three workflow modes (linear, repair, adaptive) map to AdaptOrch's topologies:
- **Linear** = Sequential (low coupling, simple dependency chain)
- **Repair** = Hybrid (sequential + feedback loop)
- **Adaptive** = Hierarchical (planner re-entry = hierarchy)

The paper validates that **routing to the right topology matters more than model
selection** — supporting your instinct that the workflow/orchestration layer is
the real differentiator, not the model.

**Key future work they identify (relevant to FA):**
1. Learned routing: lightweight classifier on (DAG features, optimal topology) pairs
2. Dynamic re-orchestration: topology changes mid-execution
3. Cost-aware routing: jointly optimize accuracy and API cost

### 1.3 DAAO: Difficulty-Aware Agent Orchestration (arxiv 2509.11079, Sep 2025)

**Core thesis:** A VAE-based difficulty estimator + modular operator allocator +
cost/performance-aware LLM router constructs custom per-query workflows.

**Architecture:**
```
Query → VAE difficulty estimator (latent z) → Operator allocator → LLM router → Workflow
```

**Results:**
- +11.21% accuracy over SOTA multi-agent systems
- Only 64% of their inference cost
- Validated across 6 benchmarks

**Direct applicability to FA:**
The VAE approach is overkill for your use case (single user, known codebase).
But the **three-module decomposition** maps cleanly:
1. Difficulty estimator → your "chat role classifier skill"
2. Operator allocator → your role selection (planner? coder? eval?)
3. LLM router → your existing models.yaml chain routing

### 1.4 TRACE-Router (arxiv 2607.22465, Jul 2026)

**Core thesis:** Task-level routing with contextual bandits. Assigns each task
to a model once at admission, **pins all subsequent LLM calls** to the selected
backend, updates policy from terminal reward.

**Key insight for FA:** "A single mid-task downgrade to the smaller model can
cause an otherwise successful execution to fail." This validates your approach
of choosing the orchestration level UP FRONT and sticking with it.

**Results:**
- Holds the interior of the accuracy-latency frontier
- 27.8 points more accurate than complexity router at identical latency
- Works with 4+ candidate models
- Cold-start capable (no training data needed)

**Implementation pattern:** Regex-based complexity classifier (easy/medium/hard)
from keyword patterns and length thresholds. "Deliberately minimal: no model
call, no embedding, no training data, no measurable latency at admission."

### 1.5 Triage: Routing SE Tasks via Code Quality Signals (arxiv 2604.07494, Apr 2026)

**Core thesis:** Code health metrics (maintainability indicators) can serve as
**routing signals** to assign each SE task to the cheapest model tier whose
output passes the same verification gate.

**The core asymmetry:** Clean, well-structured code can be modified by cheaper
models. Messy, complex code requires frontier models. This is exploitable for routing.

**Direct applicability to FA:**
Your existing tools (blackboard, fs_search, structural index) could provide
code health signals for the classifier:
- Files with high complexity → escalate to workflow
- Clean, well-tested files → handle directly in chat

### 1.6 OI-MAS: Confidence-Aware Routing (arxiv 2601.04861, Jan 2026)

**Core thesis:** State-dependent routing that selects both agent roles AND model
scales per reasoning step, with confidence-aware mechanism for complexity-adaptive
allocation.

**Results:** +12.88% accuracy, -79.78% cost vs baseline multi-agent systems.

**Key insight:** The "conductor" metaphor — one entity that allocates both role
and model scale simultaneously. This is what your `invoke_workflow` tool would
effectively be: a conductor that decides "this task needs planner+coder+eval
with their respective model tiers."

---

## 2. Production Systems (Verified Patterns)

### 2.1 Claude Code Dynamic Workflows (Anthropic, May 2026)

**The most important production reference for your escalation design.**

**How it works:**
1. Claude writes a JavaScript orchestration script on the fly
2. A separate runtime executes it in the background
3. The plan lives in **script variables**, NOT in Claude's context window
4. Up to 16 concurrent agents, 1000 total per run
5. Adversarial verification: agents try to refute findings
6. Progress is saved; interrupted runs resume

**Two activation modes:**
1. **Explicit:** Include "workflow" in the prompt → auto-triggers script generation
2. **Automatic:** `/effort ultracode` → combines xhigh reasoning + auto orchestration
   → Claude decides whether a task deserves a workflow

**Key architectural insight:** "The plan lives in code, not Claude's context window.
Intermediate results live in script variables. Only the final answer returns to
your session." This is your `flow_state.json` + `eval_report.json` pattern,
taken to the extreme.

**Direct mapping to FA:**
| Claude Code | FA equivalent |
|---|---|
| "workflow" keyword trigger | `invoke_workflow` tool call |
| `/effort ultracode` auto-mode | Chat role classifier skill |
| JavaScript orchestration script | Your workflow controller in Python |
| Script variables hold plan | `flow_state.json` + `pr_draft.md` |
| Adversarial verification | Your eval role with ADR-2 disjointness |
| 16 concurrent / 1000 total | Your single-threaded sequential model |

**What FA can learn:**
- The "ultracode" pattern validates your "chat → auto-escalate" idea
- Anthropic chose to make the escalation decision a **lightweight classifier**
  (keyword match or effort level), not a heavy planning pass
- The plan-as-code principle (plan lives in executable artifacts, not context)
  is exactly your structured artifacts approach

### 2.2 GitHub Copilot Agent Mode

**Pattern:** Issue-to-PR automation. Cloud agent turns a GitHub issue into a PR
inside Actions.

**Relevance:** Shows that "well-scoped tasks" work with simple orchestration.
Deep refactors require more. This maps to your P0-P3 depth system.

### 2.3 Open SWE / LangChain DeepAgents

**Pattern:** Composable coding-agent harness with ~15-tool limit, isolated sandbox
per task, AGENTS.md for repo conventions.

**Relevance:** The ~15-tool limit is interesting — they found that curated tool
sets at harness design time outperform dynamic tool selection. Validates your
role-specific tool registries.

---

## 3. The "Code as Agent Harness" Survey (arxiv 2605.18747)

**This is the survey that validates FA's entire architecture.**

From UIUC, Meta, Stanford (42 authors, 197 papers surveyed). Key findings
directly relevant to your project:

### Finding 1: Topology complexity inversely correlates with harness-state formality
> "When the substrate is formally represented and queryable, agents can coordinate
> through simple, transparent protocols. Systems WITHOUT formal shared state
> compensate with increasingly complex topologies — topology complexity is
> partially a symptom of missing formal substrate."

**This is your §1.2.6 Substrate Formality Principle, validated by a 197-paper survey.**

### Finding 2: The PEV (Plan-Execute-Verify) loop is the canonical harness control pattern
> "Planning as contract formation → Sandboxed execution → Verification through
> deterministic sensors." This is exactly your planner→coder→eval workflow.

### Finding 3: Shared-harness synchronization mechanisms
The survey identifies 5 mechanisms (matching your architecture):
1. **Sequential handoff** — your linear mode
2. **Blackboards** — your `session.db.blackboard` with content hashing
3. **Parallel branches with merge** — not yet in FA (deferred)
4. **Structured context scheduling** — your per-role conversation history
5. **Hierarchical memory** — your Mechanical Wiki + FTS5

### Finding 4: Agentic Harness Engineering (self-improving harnesses)
> "An evolution agent iteratively modifies harness components through
> edit-execute-evaluate loops." This is your Pillar 4 (iteration via measurement)
> and the skill-writing capability.

---

## 4. Synthesis: Recommended Architecture for FA

Based on all evidence, here's the converged pattern for your "chat → classify →
escalate" system:

### 4.1 The E3-Inspired Three-Stage Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  STAGE 1: ESTIMATE (Chat Role)                               │
│  ┌─────────────────────────────────────────────────────┐     │
│  │ 1. Lexical probe (no extra LLM call):               │     │
│  │    - file references count                          │     │
│  │    - architectural keywords                         │     │
│  │    - security/sandbox keywords                      │     │
│  │    - task length                                    │     │
│  │                                                     │     │
│  │ 2. Code health probe (1 tool call):                 │     │
│  │    - structural index for mentioned files           │     │
│  │    - complexity of affected modules                 │     │
│  │                                                     │     │
│  │ 3. Classification:                                  │     │
│  │    L1 (trivial) → handle in chat directly           │     │
│  │    L2 (medium)  → chat with planning discipline     │     │
│  │    L3 (complex) → invoke_workflow()                 │     │
│  └─────────────────────────────────────────────────────┘     │
│                          │                                    │
│              ┌───────────┼───────────┐                       │
│              ▼           ▼           ▼                       │
│         Handle      Plan+Code    invoke_workflow             │
│         Directly    in Chat      (tool call)                 │
│                                   │                          │
│                          ┌────────┴────────┐                 │
│                          ▼                 ▼                 │
│                    Linear mode        Adaptive mode          │
│                    (P1-P2 tasks)      (P3 tasks)             │
│                                                              │
│  STAGE 2: EXECUTE (Existing fa run / fa workflow)            │
│  STAGE 3: EXPAND (Only if verification fails)                │
│           → Escalate from linear to adaptive                 │
│           → Or: escalate from chat to workflow               │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 The `invoke_workflow` Tool Design

Based on E3, AdaptOrch, and Claude Code Dynamic Workflows:

```python
# Tool definition for the chat role
invoke_workflow = ToolSpec(
    name="invoke_workflow",
    description=(
        "Escalate the current task to a multi-role workflow pipeline. "
        "Use when the task requires architectural planning, touches 4+ files, "
        "changes public contracts, or involves security boundaries."
    ),
    parameters={
        "task": str,  # The task to execute
        "mode": str,  # "linear" | "adaptive"
        "roles": str,  # "planner,coder,eval" (default)
        "max_turns": int,  # Per-role turn cap (optional)
    },
    # The tool calls _cmd_workflow internally, sharing the session context
    # so the workflow sees the chat conversation history
)
```

**Key design decisions (evidence-backed):**

1. **Shared session** (from code analysis): The workflow inherits the chat
   conversation history. No information loss.

2. **Lightweight classifier** (from TRACE-Router, E3): The classification is
   lexical + one tool call, NOT an LLM planning pass. Cost: ~0.

3. **Pinned orchestration** (from TRACE-Router): Once escalated, the workflow
   runs to completion at the chosen mode. No mid-task downgrades.

4. **Expand on failure** (from E3): If linear workflow fails (eval verdict
   ≠ PASS), offer to re-run in adaptive mode. This is the "Expand" stage.

### 4.3 The Classifier Skill (Stripped-Down Plan-Authoring)

Based on E3's estimator and your existing plan-authoring skill:

```markdown
# Skill — Task Scope Classifier (Chat Role Only)

## Purpose
Classify the current task into one of three scope levels to determine
whether to handle directly or escalate to workflow.

## Classification Signals

### L1 — Handle Directly (Chat)
- Single file mentioned or implied
- No public contract changes
- No security/auth/permission implications
- Task is <50 words and clearly scoped
- Examples: "add a docstring", "rename variable X", "fix typo in Y"

### L2 — Plan + Code in Chat
- 2-3 files mentioned
- Minor contract changes (internal functions)
- Well-defined acceptance criteria
- Examples: "add a new helper function and its tests", "refactor X to use Y pattern"

### L3 — Escalate to Workflow
- 4+ files or cross-module changes
- Public API/CLI/contract changes
- Security/auth/permission boundary changes
- Architectural decisions needed
- Task is ambiguous or requires codebase exploration
- Examples: "add a new CLI command", "refactor the workflow controller",
  "implement feature X based on research note Y"

## Decision Rule
If any L3 signal is present → ESCALATE
If L2 signals present but no L3 → plan briefly, then code
If only L1 signals → just do it

## Output Format
```text
SCOPE: L1 | L2 | L3
SIGNALS: <which signals triggered the classification>
RECOMMENDATION: handle_directly | plan_then_code | invoke_workflow
```
```

---

## 5. Key Insights & Recommendations

### 5.1 The Estimator Should Be Cheap

E3, TRACE-Router, and Triage all converge on the same finding: **the task
complexity estimator should cost nearly nothing.** TRACE-Router uses a regex
classifier with "no model call, no embedding, no training data, no measurable
latency." E3 allows "≤1 cheap probe."

**Recommendation for FA:** Your classifier should be a deterministic Python
function + one `fs_search` call, NOT an LLM planning pass. The chat role
already has the task text — lexical analysis is free.

### 5.2 "Plan Lives in Code" Is the Winning Pattern

Claude Code Dynamic Workflows, E3, and the "Code as Agent Harness" survey all
converge: **the plan should live in executable artifacts, not in the model's
context window.**

Your `flow_state.json`, `eval_report.json`, and `pr_draft.md` are exactly
this pattern. This is a genuine architectural advantage over systems that
keep plans in conversation history.

### 5.3 Topology Routing > Model Selection

AdaptOrch's Performance Convergence Scaling Law formalizes what you already
intuited: when models converge in capability, **how you orchestrate matters
more than which model you pick.** Your multi-role workflow with role-specific
tools is the right architectural bet.

### 5.4 Progressive Expansion Beats Maximum-Context-First

E3's strongest finding: agents over-gather context on simple tasks, with
redundancy **largest on the simplest tasks.** The fix is Estimate → Execute →
Expand, not "always plan thoroughly."

### 5.5 Your Substrate Formality Principle Is Validated

The "Code as Agent Harness" survey (197 papers) independently discovered your
§1.2.6 principle: "Topology complexity inversely correlates with harness-state
formality." Your blackboard with read_set/write_set/detect_conflict() is the
right foundation. Adding parallel agents or complex topologies BEFORE this
substrate is solid would be solving the wrong problem.

---

## 6. Papers Reference Table

| Paper | arXiv | Date | Key Contribution | FA Applicability |
|---|---|---|---|---|
| E3: Estimate, Execute, Expand | 2607.13034 | Jul 2026 | Task-aware scope estimation, 85% cost reduction | **Highest** — direct blueprint for chat classifier |
| AdaptOrch | 2602.16873 | Feb 2026 | DAG-based topology routing, 12-23% gain | **High** — validates workflow mode selection |
| DAAO | 2509.11079 | Sep 2025 | VAE difficulty estimation + operator routing | **Medium** — three-module decomposition |
| TRACE-Router | 2607.22465 | Jul 2026 | Contextual bandit task-level routing | **High** — cheap classifier pattern |
| Triage | 2604.07494 | Apr 2026 | Code health as routing signal for SE | **Medium** — code complexity signals |
| OI-MAS | 2601.04861 | Jan 2026 | Confidence-aware role+model routing | **Medium** — conductor pattern |
| Code as Agent Harness | 2605.18747 | May 2026 | Survey: code as agent substrate (197 papers) | **Highest** — validates entire FA architecture |
| RL for MAS via Orch Traces | 2605.02801 | May 2026 | Orchestration traces as RL analysis framework | **Low** — future optimization direction |

---

## 7. What To Build First (Prioritized)

1. **Chat role with minimal system prompt** — `fa run -r chat` with lightweight
   tools (fs_search, fs_read_file, fs_blackboard_query, invoke_workflow)

2. **Lexical scope classifier** — Deterministic Python function in the chat
   system prompt or as a pre-processing step. No extra LLM call.

3. **`invoke_workflow` tool** — Wraps `_cmd_workflow` with shared session
   context. Linear mode default.

4. **Expand-on-failure** — If linear workflow fails, offer adaptive re-run.

5. **Measure** — Track: scope classification accuracy, escalation rate,
   token cost per scope level, task success rate per path.
