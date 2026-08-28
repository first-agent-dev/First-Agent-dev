# ADR-16 — Complexity-Aware Execution (Chat Role, Scope Estimation, Workflow Escalation)

- **Status:** proposed
  - *2026-08-26:* Option B (below) proposed and accepted as the architecture direction.
  - *2026-08-28 (S10 addendum):* the full Estimate→Execute→Expand loop has now been
    **implemented and mutation-tested** (slices S7–S10). The addendum at
    [§ Addendum 2026-08-28](#addendum-2026-08-28--shipped-architecture-s7s10) below records
    what shipped, the places where the shipped mechanism differs from the original proposal
    (the routing decision is evidence-driven, not keyword-driven), and the set of tuned
    constants that await live-contour validation in slice S11. This ADR is **deliberately
    not flipped to Accepted until S11 closes**: per "never assert beyond verified", the
    numeric constants (ε, K, tier prefixes, caps, fitted cost weights) are code variables
    seeded to documented values, not yet calibrated against the live chat contour.
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

## Addendum 2026-08-28 — Shipped architecture (S7–S10)

> This addendum records the system **as built and tested**, not as first proposed.
> The Option B architecture above was the direction; the slices that landed
> (S1 estimator, S2 chat role, S3 CLI integration, S3.5 observability, S4 workflow
> controller + `invoke_workflow` tool, S5 ACRR proxy, S7 deterministic routing, S8 full
> cost model, S9 live-verification sheet, **S10 scope control / evidence-driven
> expansion**) sharpened one load-bearing fact that changes how the whole thing must be
> read.

### A. The load-bearing revision: routing is evidence-driven, not keyword-driven

The original proposal (Option B) framed the estimator as "optimistic, with the workflow
as a safety net for under-estimates." Implementation and measurement proved the framing
needed to be stronger: the lexical estimator is **expected to be wrong on the hardest
tasks**, and correctness therefore cannot depend on the words in the task. We call this
the **two-layer design**:

1. **Layer 1 — the lexical estimator** (`estimate_scope`, pure Python, <1 ms, no LLM
   call) reads the task *text* and maps a handful of cue words to a seed posture
   (`chat_direct` → level 1, `chat_planned` → level 2, `workflow_linear` → level 3). It
   is the cheap, fast path for the common case. It is deliberately weak.
2. **Layer 2 — the evidence engine** (S10) runs at every turn boundary on the *actual*
   observed read/write behaviour and escalates regardless of what the words said.

Why two layers: held-out tests showed simple, genuinely-cross-file tasks phrased with
**none** of the estimator's cue words — and in the operator's real **terse Russian style**
— score `chat_direct` at confidence 0.3. Example task wording that scores *direct* but
must still escalate: *"simplify the main function"*, *"clean up a small thing in the
cli"*, *"убери лишнее из главной функции"*, *"поправь проверку перед пушем"*. If routing
relied on the text these would silently run as single-pass chat tasks; they do not,
because the escalation reads evidence, not wording.

**Consequence for readers of this ADR:** the estimator decides *initial* posture and
cost; the evidence engine decides *whether the run outgrew its posture*. The mid-run
evidence path is **observe-only** — it never removes a tool or kills a turn (Q25); it
attaches advisory text to the next request and (for L3) recommends `invoke_workflow`.
No tool is ever taken away mid-run.

### B. Expansion as a three-level posture state machine (S10.1, `expansion.py`)

Postures are **levels**, not tool sets:

| Level | Posture | Meaning |
|---|---|---|
| 1 | `chat_direct` | work the task directly in chat |
| 2 | `chat_planned` | **arm** the planner-skill injection (L2) |
| 3 | `workflow` | recommend `invoke_workflow` (the escalation) |

The pure decision function `next_level(state, *, files_read, files_changed, write_tier,
read_tier_high, verify_failed, assumed_linear)` returns an `ExpansionDecision(level_to,
evidence, observation_key)` or `None`. Properties (all mutation-tested):

- **Monotone & idempotent** — decisions only move strictly up; re-evaluating the same
  state+evidence returns the same answer.
- **Ceiling 3** — `next_level` at level 3 returns `None`; nothing is ever advised above
  the ceiling (`LEVEL_CEILING = 3`).
- **No K argument here.** The escalation budget K is enforced structurally in the tool
  (§E), because level 3 *is* the `invoke_workflow` call.

Trigger policy (strongest evidence first, so the emitted trigger name is unambiguous):

| Evidence (trigger name) | Required condition | Effect |
|---|---|---|
| `verify_failed` | a `VERIFY_ONLY` bash command (pytest/ruff/mypy), classified by `bash_intent`, exited non-zero on the previous turn | → level 3 |
| `high_tier_write` | `write_tier == TIER_HIGH (5)` for a modified path | → level 3 |
| `read_high_arm` | a high-tier path was **read** (`read_tier_high`) and level < 2 | → arm level 2 |
| (silence) | bulk counters alone | no escalation |

Critical gating (R1/DP-1): **bulk counters never escalate without a high tier present.**
A large but *safe* change — e.g. fixing doc links across 15 archived files, or editing
only `tests/`/`knowledge/` — stays silent. The inherited S7 thresholds
(`READ_LIMIT = 10`, `CHANGE_LIMIT = 3`) are still accepted and validated as inputs, but
they are tier-gated so safe bulk work does not nag. A run seeded `workflow_linear` is
never re-escalated (RK-I — the advice would duplicate the seed).

L2 skill selection is deterministic (`select_l2_skill`): a plan/research artifact
already in context (**warm**) → the lighter, context-rich `feature-planning` skill;
otherwise (**cold**) → the full `plan-authoring` skill.

### C. The positional risk model: where, not what (S10.2, `path_risk.py`)

Escalation evidence comes from **path tiers**, because *which files* the run touches is
a stronger signal than the words in the task (Q26). Paths are classed into three tiers
from a configurable `scope_risk_tiers:` config block:

- **safe (1)** — `worklogs/archive`, `worklogs/research`, `worklogs/reviews`,
  `worklogs/pr-notes`, `worklogs/implementation-plans`: never escalate.
- **medium (3)** — `knowledge/`, `tests/`, `scripts/`: a write here is a
  *verification-posture* change only (it nudges targeted tests), **never a scope
  escalation**; a read is silent. Editing `tests/**` is a medium/high *posture* matter
  for the agent's own discipline, not an auto-workflow trigger.
- **high (5)** — `src/` plus repo-root manifests (`pyproject.toml`, `justfile`,
  `Dockerfile`, `.github/`, lockfiles, …): a read **arms** level 2, a write
  **escalates** to level 3.

Rules, each pinned by tests:

- **Unknown prefix → medium, not high** (RK-J). Failing safe means "ask for more process"
  rather than "stay casual inside production code" — but a novel *docs* tree must not
  force workflow. Medium is the deliberate midpoint.
- **`MAX` combines signals** (`combine_tiers = max(lexical, path_based)`): a
  lexically-easy task (1) touching `src/` (5) ends high, never averaged down. MAX is
  associative/commutative/idempotent and keeps the strongest signal.
- **Config lists are additive to defaults** and a bad/missing config degrades to defaults
  **plus a structured warning** — never a crash, never silence (`ScopeRiskWarning`;
  failure-observable). The high default (`src`) cannot be silently dropped.
- `observed_tiers(reads, writes, cfg)` returns per-set maxima; an empty set is
  `TIER_NO_EVIDENCE (0)`, distinct from a *safe* observation, so "no writes this turn"
  never reads as "wrote safely."

### D. Mid-run observations: rebuilt, capped, tier-keyed (S10.4, `observations.py`)

Each turn boundary the loop renders a fresh advisory block. Rendering rules (DP-8), all
kill-checked:

- **Rebuilt per turn by assignment — never appended.** A stale L2 ("planner skill
  active") line cannot survive an L3 escalation: the block is a keyed dict
  `{skill, escalation, verification, exhausted}` reassigned each turn.
- **Eviction order under a fixed token budget** (`OBSERVATION_CAP_CHARS = 1800`,
  ≈ a conservative 500-token ceiling): `exhausted` (4) > `escalation` (3) >
  `verification` (2) > `skill` (1). Lowest-priority entries are dropped first; the
  terminal line always wins space.
- **The full skill body never enters this string.** On the L2 entry turn the body travels
  via the separate `skills_conditional` channel; the observation carries only a short
  anchor.
- **Verification posture is tier-keyed and advisory** (never changes level): no writes →
  nothing; medium-tier writes → "consider targeted tests for what you edited"; high-tier
  writes → "Risk tier high … run <command> and confirm green before reporting done."
- A positive-imperative checklist (**"Do exactly:"**), never negative instructions —
  see §F.

### E. The workflow escalation: K budget + live handoff (S10.5, `workflow_tool.py`)

The chat role escalates by calling a registered `invoke_workflow` tool that invokes the
shared workflow pipeline (`planner → coder → eval`) with a **child** run id derived from
the parent (distinct, ≤128 chars). Two structures keep escalation bounded and useful:

**Escalation budget K (audit F1).** K is enforced **only in the tool**, not in the pure
expansion core. The tool holds an `invocation_count` closure; `_check_budget` denies the
(K+1)-th call with a structured error:

```
code:   workflow_budget_exhausted
message: workflow escalation budget of K invocation(s) used;
         finish with an operator report instead of escalating again
```

K defaults to `max_workflow_invocations = 2` and is read from `RuntimeLimits`
(`limits.max_workflow_invocations`), so it is a config knob, not a hardcoded constant.
A budget denial latches in the loop and renders the terminal `expansion_exhausted`
observation (the `exhausted` key above) — the agent finishes the task with its current
tools and reports state. The loop also emits a durable `expansion_exhausted` log event.

**The planner handoff (handoff payload).** Because the chat role assembles prompts
mechanically at runtime (the agent never self-selects a skill unless explicitly told),
the handoff task is built from **live session facts** via a provider closure
(`session_facts_provider`, wired in the CLI from the live `SessionState`). Sections:

1. **`Goal:`** — the model-supplied task, verbatim (trimmed).
2. **`Start here:`** — the top HIGH-tier read paths, **cap 5** (the actionable entry
   points).
3. **`Observed (already read):`** — read paths grouped by tier with counts (the map;
   tells the planner what *not* to re-search).
4. **`Modified:`** — the write paths.
5. **`Candidate leads:`** — search/grep paths not already read, **cap 10**.
6. **`Do exactly:`** — a 3-step positive checklist for the planner.

Caps: Start-here ≤ 5, leads ≤ 10, **total paths ≤ 30**, paths only (no snippets, no
file:line in v1). When paths exceed the total budget, the *Observed* section (the most
derivable) is trimmed first; Start-here and Leads are the actionable ones. A missing or
raising facts provider **degrades to the bare goal** — escalation still runs, never
crashes; the blackboard mirror (`type: workflow_handoff`) is best-effort.

### F. Positive-imperative harness instructions (prompt-assembly lesson)

A recurring failure: an agent told what *not* to do ("don't list files", "don't
re-search") does not reliably comply, and the harness must not depend on the model
remembering a prohibition. Both escalation seams therefore use numbered, positive
**"Do exactly:"** checklists — for the chat side ("1) Call invoke_workflow with the
current goal. 2) The harness attaches a file map and handoff; start from its 'Start
here' list. 3) Continue the chat task only if you finish without it.") and for the
planner handoff ("Start from 'Start here'; use Observed/Candidate leads as your map; do
not re-search them"). The composition is mechanical (code assembles tool call → goal →
harness-attached file map); the agent is given positive steps, not constraints.

### G. Reliability calibration (S10.6, `calibration.py`)

The efficiency view is extended with a **reliability** view so that a mode cannot look
good while failing. `fa stats --calibration` builds `build_calibration_report(rows, *,
epsilon, min_flag_runs, gate_enabled)` from `global_history.db`:

- **Reliability counts every run.** `runs_total` = all runs in a mode bucket;
  `runs_succeeded` = `exit_code == 0`; `success_rate = succeeded / total`
  (0.0 for an all-failed mode). **Failed runs drag the rate down.**
- **ACRR aggregates successes only** (Q22): a cheap failure is not an efficiency.
  Failed runs contribute no ACRR (see the self-referential-floor caveat below).
- **`below_reliability_target`** fires only when `runs_total ≥ min_flag_runs` **and**
  `success_rate < 1 − epsilon`. Defaults: `calibration_epsilon = 0.05`,
  `min_flag_runs = 10`. A rate *exactly* at `1 − ε` is not flagged; a sample below the
  minimum is never flagged (no wolf-crying on n=2).
- Both ε and `min_flag_runs` are code variables on `RuntimeLimits`, toggleable; the gate
  can be silenced by setting `min_flag_runs` above the available sample.

**The escalation gate defaults OFF (`chat_escalation_gate = False`, Q25).** The
*mechanism* (levels, observation blocks, K enforcement) is fully shipped and measured;
the *policy* of auto-blocking/auto-routing on a low reliability flag is display-only for
now — it surfaces `BELOW RELIABILITY TARGET` and the gate state in both JSON and human
output, and can be enabled later by config. No mid-run tool removal ever happens.

### H. Log-kind evolution (S10, F4)

Two new durable event kinds join `LogKind`: **`scope_expansion`** (the per-turn boundary
event — evidence, level change) and **`expansion_exhausted`** (terminal K denial). The
S7 one-shot mid-flight **`scope_tripwire`** kind is **retired as an emitted event**
(replaced by the per-turn `scope_expansion` boundary) but **kept in the `LogKind` enum as
a dormant alias**, because the S8/S9 routing-calibration projection still keys on the
historical name. It is registered in the contract checker's `KNOWN_DORMANT_KINDS` with
the reason, and is to be dropped from the enum once that projection migrates.

### I. The cost model as shipped (S8) — supersedes the §Architecture ACRR sketch

The original `ACRR_proxy = files_read / files_changed` sketch was the v1 proxy. S8
shipped the fuller E3 cost model `C(π) = α·T + β·tokens + γ·tools + δ·files` with fitted
weights and a cost floor. The mandatory caveat — reproduced **verbatim** below because it
is easy to over-trust the calibration table — is:

> "The floor is self-referential: it derives from the run's own change-set, so a run that
> changed the WRONG files still scores well. ACRR measures redundancy, never correctness."

Additional S8 facts this ADR must record:

- **Fitted weights:** α = 1.0, β = 0.000415, γ = 0.1, δ = 1.5. Derivation: the median
  `src/*.py` file is ~7234 B ≈ 1808 tokens; β is set so a median file's token cost is
  half its file cost. The paper's default weights were measured and put the file axis at
  0.43–2.17% of C; they were rejected as too weak for FA's file-dominated workload.
- **The floor EXCLUDES latency**, per E3 LLM-Case 7.7, to stay deterministic (wall-clock
  is not reproducible across machines).
- **ACRR is recorded for every run and filtered at display** (Q22), because a cheap
  failure is not an efficiency: an unsuccessful run reports no flattering ACRR, which is
  also why `fa stats --calibration` draws ACRR from successful runs only.
- **E3 §7.2 monotonicity caveat:** the paper's authors concede the cost/success
  monotonicity is "partly mechanical"; present it as a descriptive signature, **not a
  scaling law**.

### J. Validation evidence (S10.6 / S10.7)

- **C0/C1/C2 tests** across pure cores (`expansion`, `path_risk`, `observations`,
  `calibration`) and wired seams (CLI provider, coder loop, workflow tool), plus C2
  real-CLI tests driving `fa stats --calibration` against a temp `FA_STATE_ROOT`.
- **R1 — held-out wording (14 pairs):** 8 English tasks with cue-free vocabulary + 6
  Russian operator-style phrasings; asserts the evidence engine escalates on identical
  high-tier evidence *regardless of wording* (high-tier write → L3; high-tier read → L2),
  and records (not gates) the estimator's under-scope rate — a high rate is the premise
  of the two-layer design, not a failure.
- **R2 — deceptive tasks (6):** e.g. the CLI's own *"simplify the main function"* and a
  force-push via `src/fa/hygiene/hooks/pre-push` (EN + RU). Verifies stable **one-level**
  arming/escalation (read-high arms exactly L2, then write-high escalates exactly L3),
  `verify_failed → L3` even mid-level, and that high-tier paths (`src/fa/cli.py`,
  `pre-push`, `workflow_tool.py`, `prompt_composer.py`) all classify tier 5 against the
  *real* baseline registry and trajectory.
- **Mutation sweep (S10.8):** 20–21 hand-applied mutants (ceiling removal, bulk-fires
  without tier, MAX→min, unknown→high, `tests/**`→high, read/write swap, stale L2
  accumulation, cap/eviction removal, K-check removal, goal-only handoff, blackboard
  removal, hardcoded K, calibration failed-run pre-filter, ε/min-sample removal,
  rate-denominator errors) — **all killed, zero survivors**, with byte-identical
  restore after each mutant.
- **Full gate:** `just check` toolchain green on ruff, ruff-format, deptry, pylint
  (10.00/10), mypy `--strict` (src + tests, 0 errors), pyrefly (0 errors), authoring,
  all contract scripts (dependency, producer-consumer, log-kind, no-mocked-dataclasses,
  dead-flags), shell-syntax; full suite 3614 passed at **85.85%** coverage (floor 80%).

### K. Tuned constants awaiting live validation (S11 input)

These are code variables seeded to documented values and **not yet calibrated** against
the live chat contour; S11 revisits them with real data and records the outcome here:

| Constant | Default | Location | Open question for live runs |
|---|---|---|---|
| Calibration tolerance ε | 0.05 | `runtime_limits.calibration_epsilon` | Does 5% below-perfect flag too eagerly / too late on real mode volumes? |
| Minimum flag sample | 10 | `runtime_limits.min_flag_runs` | Is n=10 enough to separate noise from a real regression? |
| Escalation budget K | 2 | `runtime_limits.max_workflow_invocations` | Do legitimately hard tasks need a 3rd escalation? Does K=2 ever trap a task? |
| Tier prefixes | safe/medium/high defaults | `scope_risk_tiers:` config | Do real repos need extra medium/high prefixes? Is unknown→medium right? |
| Observation cap | 1800 chars | `observations.OBSERVATION_CAP_CHARS` | Does the advisory ever crowd real context, or get evicted too aggressively? |
| Handoff caps | 5 / 10 / 30 paths | `workflow_tool` caps | Are Start-here=5 / Leads=10 / total=30 the right map size for the planner? |
| Cost weights | α1.0 β0.000415 γ0.1 δ1.5 | S8 cost model | Confirmed on synthetic data; validate ordering on live runs. |
| `chat_escalation_gate` | **off** | `runtime_limits` | Flip to on only after live reliability data supports an auto-policy. |

S11 also performs the remaining documentation updates (`llms.txt` routing index,
`instructions/02-operations.md` chat section, `AGENTS.md` roles, models.yaml example),
flips this ADR to **Accepted** with a dated Live-validation note, and closes the parent
plan.

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
