# ADR-16 — Complexity-Aware Execution (Chat Role, Scope Estimation, Workflow Escalation)

- **Status:** proposed
- **Date:** 2026-08-26
- **Deciders:** Project Owner + Agent-Assisted Architecture Session

## Context

First-Agent has two execution modes: `fa run` (single-role, direct execution) and
`fa workflow` (multi-role planner→coder→eval pipeline). The operator must
manually choose between them for every task. This creates two failure modes:

1. **Over-orchestration:** Simple tasks (fix a typo, rename a variable) get the
   full workflow treatment — 30+ turns of planning, coding, and evaluation for
   a change that takes one tool call. Token waste is **largest on the simplest
   tasks** (E3 paper: ACRR 22.1 at Level 1 vs 5.4 at Level 3).

2. **Under-orchestration:** Complex tasks (cross-module refactors, architectural
   changes) get a single coder pass without planning discipline, missing the
   plan-authoring and verification rigor that the workflow provides.

The E3 framework (arxiv 2607.13034) formalizes this as the **maximum-context-first**
problem: agents follow a "gather everything, then eliminate risk" strategy that is
warranted on hard tasks but grossly over-provisioned on easy ones. Their solution —
**Estimate, Execute, Expand** — uses a cheap scope estimator before committing
budget, with verified progressive expansion as the safety net.

The "Code as Agent Harness" survey (arxiv 2605.18747, 197 papers) independently
validates FA's existing architecture: "topology complexity inversely correlates
with harness-state formality." FA's strong formal substrate (blackboard with
conflict detection, session.db authority, structured artifacts) means the right
next step is **exploiting the substrate better**, not adding topology complexity.

We need an automatic routing layer that:
- Handles simple tasks with minimal overhead (no LLM classification call)
- Escalates complex tasks to the workflow pipeline
- Measures efficiency so we can improve iteratively

---

## Options Considered

### Option A — LLM-Decides Escalation (Chat Role with Classifier Prompt)

Add a chat role whose system prompt instructs the LLM to classify task complexity
and call an `invoke_workflow` tool when needed. The LLM makes the routing decision.

- **Pros:**
  - Flexible: LLM can reason about ambiguous tasks
  - Natural UX: operator just talks to the agent
  - Claude Code's "ultracode" pattern validates this approach
- **Cons:**
  - **Costs 1 LLM turn for classification** (~2-5k tokens per task)
  - LLM classification is stochastic — may misclassify
  - Violates compliance-by-construction (§1.2.5): spec-bearing routing
    decision lives in LLM judgment, not deterministic code
  - E3 paper explicitly shows deterministic estimators outperform LLM-based
    classification on cost while matching success

### Option B — Deterministic Pre-Dispatch Estimator + Tool-Based Escalation

Add a chat role with a deterministic scope estimator (pure Python, no LLM call,
<1ms) that runs before dispatch. L1/L2 tasks are handled directly; L3 tasks
get an `invoke_workflow` tool call. The estimator is deliberately optimistic;
the workflow is the safety net for under-estimates.

- **Pros:**
  - **Zero LLM cost for classification** — pure Python, <1ms
  - Compliance-by-construction: routing is deterministic, testable, auditable
  - E3 paper validates: 85% cost reduction at matching success
  - Optimistic estimator + verified expansion is safe (E3 ablation proves it)
  - ACRR tracking measures whether the estimator is working
- **Cons:**
  - Less flexible on genuinely ambiguous tasks
  - Keyword-based estimator may misclassify edge cases
  - Requires refactoring `_cmd_workflow` into an internally callable function

### Option C — Harness-Level Routing (No Chat Role)

Add routing logic directly in the CLI before any role dispatch. `fa "task"`
automatically routes to `fa run -r coder` or `fa workflow` based on heuristics.

- **Pros:**
  - Simplest UX: operator doesn't think about modes at all
  - No new role surface area
- **Cons:**
  - Removes operator control (can't override routing easily)
  - No conversational interaction for clarification
  - Violates Pair-over-Autonomy (§1.2.7): agent decides without pair input
  - TRACE-Router paper shows task-level routing benefits from interactive context

---

## Decision

We will choose **Option B** because it:
1. Follows **compliance-by-construction** (§1.2.5): the routing decision is a
   deterministic Python function, not LLM judgment
2. Is validated by **E3 paper results**: 85% cost reduction, 91% token reduction,
   with matching success on the hardest tasks
3. Respects **substrate formality** (§1.2.6): no topology complexity added;
   the existing sequential chain + structured artifacts are the foundation
4. Follows **minimalism-first** (§1.2): no new dependencies, no LLM calls for
   classification, reuses existing session infrastructure
5. Is **measurable**: ACRR proxy tracking lets us verify the estimator works
   and improve it iteratively (Pillar 4)

The estimator is deliberately **optimistic** (E3 principle): bias toward
under-estimating complexity, because over-estimating wastes tokens on simple
tasks (the main problem), and under-estimating is recovered by the workflow
escalation safety net.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  fa run -r chat "task"                                   │
│                          │                               │
│              estimate_scope(task)  ← pure Python, <1ms   │
│                    │                                     │
│         ┌──────────┼──────────┐                          │
│         ▼          ▼          ▼                          │
│     L1 (d̂=1)   L2 (d̂=2)   L3 (d̂=3)                    │
│     direct      plan+code    invoke_workflow tool        │
│     in chat     in chat      │                           │
│                               ▼                          │
│                    _run_workflow_internal()               │
│                    planner → coder → eval                │
│                    (shared session context)               │
│                               │                          │
│                    if linear fails:                      │
│                    expand to adaptive                    │
└─────────────────────────────────────────────────────────┘

Efficiency tracking:
  ACRR_proxy = files_read / max(files_changed, 1)
  Computed in fa stats, stored in global_history.db
```

### Scope Estimator (E3 §4.2)

```python
@dataclass(frozen=True)
class OperatingPoint:
    difficulty: int  # 1, 2, or 3
    scope: str  # "single-file", "cross-file", "repo"
    risk: str  # "low", "medium", "high"
    confidence: float  # 0.0 to 1.0
    recommended_mode: str  # "chat_direct", "chat_planned", "workflow_linear"
```

Signals (from E3 §4.2, adapted for FA):
- **L3:** "refactor", "redesign", "migrate", "restructure", "new subsystem",
  "protocol", "architecture", "across.*codebase", "every.*call.?site"
- **L2:** "add.*function", "implement", "new.*command", "cross-file"
- **L1:** "fix typo", "rename", "update.*docstring", "single.*file"
- **Security boost:** "auth", "permission", "secret", "sandbox" → +1 difficulty

### Chat Role

First-class role with:
- **System prompt:** Minimal pair-programming partner, scope-aware, knows about
  `invoke_workflow` tool
- **Tool registry:** fs_read_file, fs_search, fs_blackboard_query, fs_run_bash
  (READ_ONLY only), fs_reach, invoke_workflow
- **No write tools:** Chat cannot directly mutate files for L3 tasks — it
  escalates instead (security boundary, like planner's read-only tools)
- **models.yaml entry:** Optional; falls back to coder's model if not declared

### invoke_workflow Tool

A registered tool in the chat role's registry that calls
`_run_workflow_internal()` with shared session context. The workflow pipeline
runs in the same session, seeing the chat conversation history.

### ACRR Proxy

```
ACRR_proxy = files_read / max(files_changed, 1)
```

Where:
- `files_read` = distinct files pulled into context (from fs_read_file events)
- `files_changed` = distinct files mutated (from fs_write_file/fs_edit_file events)

This is an acknowledged simplification of E3's full cost model
`C(π) = α·T + β·tokens + γ·tools + δ·files`. The file ratio captures the
**dominant cost axis** (δ=1.5 per file in E3's model — pulling an irrelevant
file charges on three axes at once). Full cost model is deferred to v2.

---

## Consequences

### Positive

- **Eliminates manual mode selection** for routine tasks — the harness decides
- **Zero classification cost** — deterministic Python, no LLM tokens spent
- **Measurable efficiency** — ACRR proxy tracks whether the system is lean
- **Safe escalation** — optimistic estimator + workflow safety net (E3 validated)
- **Compliance-by-construction** — routing is deterministic and testable
- **No topology complexity** — reuses existing sequential chain + artifacts

### Negative

- **New role surface area** — chat role adds system prompt, tool registry, models.yaml entry
- **Keyword estimator is imperfect** — will misclassify edge cases (E3 ablation
  shows this is recoverable via expansion)
- **ACRR proxy is coarse** — file ratio misses token-level waste (acknowledged;
  full model in v2)
- **Refactoring risk** — `_cmd_workflow` must be decomposed into callable + wrapper
  without breaking existing tests

### Follow-up Work This Unlocks

1. **Learned routing classifier** (AdaptOrch §7.1) — train on (task features,
   optimal strategy) pairs once ACRR data accumulates
2. **Full E3 cost model** — implement `C(π) = α·T + β·tokens + γ·tools + δ·files`
   once per-axis tracking infrastructure matures
3. **Progressive expansion** — automatic upgrade from linear to adaptive workflow
   when linear fails (E3's Expand stage)
4. **Chat role conversation mode** — multi-turn interactive chat (separate feature,
   `fa ask` or `fa chat` subcommand)

### Follow-up Work This Requires

1. Update `knowledge/llms.txt` routing index with ADR-16
2. Update `knowledge/instructions/02-operations.md` with chat role documentation
3. Update `knowledge/templates/models.yaml.example` with optional chat section
4. Add ACRR proxy to `fa stats` output and `global_history.db` schema

---

## Prior Art

| System | Pattern | How FA Differs |
|---|---|---|
| E3 (arxiv 2607.13034) | Estimate→Execute→Expand with lexical probe | FA adopts the estimator pattern; differs in that expansion is workflow escalation, not scope widening |
| AdaptOrch (arxiv 2602.16873) | DAG-based topology routing | FA uses simpler deterministic rules; no DAG decomposition needed for sequential chain |
| TRACE-Router (arxiv 2607.22465) | Contextual bandit for task-level routing | FA uses deterministic rules (no training); bandit approach deferred to v2 |
| Claude Code "ultracode" | Auto-escalation based on effort level | FA uses tool-based escalation (invoke_workflow) vs Claude's script-based orchestration |
| DAAO (arxiv 2509.11079) | VAE difficulty estimation | FA rejects VAE as overkill for single-user; deterministic rules suffice |
| Triage (arxiv 2604.07494) | Code health as routing signal | FA uses task text signals (complementary; code health could augment in v2) |
| OI-MAS (arxiv 2601.04861) | Confidence-aware role+model routing | FA routes to orchestration level, not model scale (models.yaml handles scale) |

---

## Relation to Existing ADRs

- **ADR-2 (LLM Tiering):** Chat role may share family with coder (not eval).
  Eval disjointness rule still applies.
- **ADR-7 (Tool Registry):** Chat registry is a new role-specific registry,
  following the planner/coder/eval pattern.
- **ADR-11 (Authoring Guardrails):** Chat role inherits all guardrails.
  No weakening of TCB for chat convenience.
- **ADR-12 (Secret Isolation):** Chat role inherits proxy mode. No key access.
- **ADR-13 (Workspace Isolation):** Chat operates in managed workspace clone.
- **ADR-17 (Context Management):** Chat role benefits from compaction for
  longer conversations. No new compaction logic needed.

---

## References

1. E3: "Do AI Agents Know When a Task Is Simple?" — Yin & Feng, arxiv 2607.13034 (Jul 2026)
2. Code as Agent Harness — Ning et al., arxiv 2605.18747 (May 2026)
3. AdaptOrch — Yu, arxiv 2602.16873 (Feb 2026)
4. TRACE-Router — Raj et al., arxiv 2607.22465 (Jul 2026)
5. DAAO — arxiv 2509.11079 (Sep 2025)
6. Triage — Madeyski, arxiv 2604.07494 (Apr 2026)
7. OI-MAS — arxiv 2601.04861 (Jan 2026)
8. Claude Code Dynamic Workflows — Anthropic (May 2026)
9. FA research note: `knowledge/research/E3-and-code-as-harness-deep-dive-2026-08-26.md`
10. FA research note: `knowledge/research/fa-workflow-escalation-research-2026-08-26.md`
