# ADR-10 — Deterministic-harness invariants (I-1..I-5)

- **Status:** proposed
- **Date:** 2026-05-25
- **Deciders:** project owner (`0oi9z7m1z8`), Devin (drafting)

## Context

[ADR-7](./ADR-7-inner-loop-tool-registry.md) §8 (mini hook pipeline),
[ADR-8](./ADR-8-hook-registry.md) (HookRegistry middleware-chain
contract), and [ADR-6](./ADR-6-tool-sandbox-allow-list.md)
§Amendment 2026-05-20 (three-layer bash sandbox) each install a
single piece of the deterministic harness around the LLM call. They
do not, between them, state the **cross-cutting invariants** every
B-bucket entry / A-tier prompt-block / future hook MUST satisfy to
remain compliance-by-construction. Without those invariants spelled
out as a named slate, the next harness component will drift along
one of the four axes the
[`research/fa-abc-synthesis-deep-dive-2026-05.md`](../research/fa-abc-synthesis-deep-dive-2026-05.md)
deep-dive catalogued across 9 OSS agent stacks (pi, gbrain,
hermes-agent, gortex, kronos-agent-os, dpc-messenger, rtk, grit, icm).

The research note was authored as the ADR-10 input note — it ships
**I-1..I-5** invariant candidates (§3 + §3a) keyed on the «verifiable
hook results + deterministic harness to control LLM» goal lens, plus
verbatim `file.ext:line` evidence for each. This ADR consumes that
input and lands the invariants as the harness-binding slate. The
research note's §0c jump-table positions §3 + §3a + §4 + §6 + §6b as
the action surface (~5 k tokens) for this ADR's author.

**The forcing function carries forward.** Every invariant below
quotes the source `file.ext:line` from the deep-dive verbatim — the
line citations are the evidence chain; paraphrasing would break it
(see research note §0c forcing-function clause at
[`fa-abc-synthesis-deep-dive-2026-05.md:74-79`](../research/fa-abc-synthesis-deep-dive-2026-05.md#0c-how-to-read-this-doc-navigation-aid)).

**Companion §1.2.5 landing.** The deep-dive §6b placement decision
([`fa-abc-synthesis-deep-dive-2026-05.md:1945-1978`](../research/fa-abc-synthesis-deep-dive-2026-05.md#6b-125-placement-decision--compliance-by-construction))
resolves «compliance-by-construction, failure-observable» as
[`project-overview.md` §1.2.5](../project-overview.md#125--compliance-by-construction-failure-observable)
(NOT Pillar 5). Same PR lands §1.2.5 with the five KPI candidates so
the invariants below have a single named home in the construction-
discipline doc layer.

## Options considered

### Option A — Defer the invariants into ADR-7 / ADR-8 amendments (no new ADR file)

- Pros:
  - Zero new artefact under `knowledge/adr/`; subtraction-first.
  - Each invariant lands next to the harness layer it constrains
    (I-1/I-4 → ADR-8; I-2 → ADR-7 §Pre-flight; I-3 → ADR-7 §8 hook
    pipeline; I-5 → ADR-6 sandbox + future MCP layer).
- Cons:
  - The invariants cut **across** ADR-6 / ADR-7 / ADR-8 / future ADRs
    (any harness layer that runs before / after the LLM call). Splitting
    them five ways destroys the cross-cutting reading — exactly the
    drift the deep-dive's §3 + §3a were authored to prevent.
  - Future amendments cannot point at a single citable URL for «the
    invariant slate»; the cheap-read overlay in `DIGEST.md` cannot
    summarise a five-way-split rule set in one paragraph.
  - The deep-dive's §3a invariant I-5 spans rtk R8 (parsing call site)
    + icm IC1 (MCP layer boundary) — no single existing ADR is the
    right home.

### Option B — One micro-ADR per invariant (5 new ADR files)

- Pros:
  - Each invariant gets its own §Decision / §Consequences /
    §References block; clean per-rule provenance.
- Cons:
  - Five files for five rules of identical shape is artefact bloat;
    the DIGEST.md cheat-sheet would grow ~5 paragraphs for rules that
    share a single goal lens.
  - The minimalism-first subtraction-check (AGENTS.md §Pre-flight
    Step 4) fails: one ADR already covers the cross-cutting scope.

### Option C — Single ADR-10 with named invariants I-1..I-5, each grounded in §1.x line citations (chosen)

- Pros:
  - One file, five named rules, one citable URL per invariant
    (`ADR-10#i-1`, `ADR-10#i-2`, …) for future PRs to anchor on.
  - The invariant slate matches the deep-dive's §3 + §3a structure
    1-to-1; the cross-reference burden is minimal.
  - Each invariant carries the AGENTS.md §PR Checklist rule #10
    4-question evidence cell inline (per the ADR-10 binding
    constraint — see §References below).
  - DIGEST.md row stays a single paragraph; HANDOFF.md gets one
    bullet (rule #9 mirror).
- Cons:
  - Adds one new file under `knowledge/adr/`; offset by removing the
    drift risk Option A introduces.

### Option D — Inline I-1..I-5 directly into AGENTS.md as new PR Checklist rules

- Pros:
  - Maximally enforcement-adjacent; future PR descriptions cite the
    AGENTS.md rule number, not an ADR section.
- Cons:
  - AGENTS.md is procedural (how to author PRs); ADRs are
    architectural (what the harness MUST satisfy). Conflating the
    two erodes the existing «AGENTS.md = rules, knowledge/adr/ =
    decisions» separation.
  - Rule #10 already enforces the *evidence cells* for harness
    components; the invariants themselves belong in an ADR so future
    amendments (re-evaluation triggers, scope changes) follow the
    ADR amendment pattern, not the AGENTS.md amendment pattern.

## Decision

We will choose **Option C** (single ADR-10 with named invariants
I-1..I-5, each grounded in `file.ext:line` citations from the deep-
dive note) because:

1. The deep-dive's §3 + §3a authored the invariants as a single
   slate keyed on a single goal lens; splitting them inverts the
   author's framing.
2. Option C is the only shape that gives future PRs a single citable
   URL per invariant (`ADR-10#i-N`) — the rule #10 4-question
   evidence cell can point at one ADR section, not one of five.
3. The minimalism-first 4-question test clears: research-evidence
   (§3 + §3a deep-dive), open-source precedent (§1.x snippets from
   9 stacks), capability lost (each invariant's §3 rationale names
   a concrete failure mode), function-vs-LLM (the entire ADR-10 IS
   the deterministic-harness binding axis — every I-N captures one
   «replace LLM judgement with harness function» decision).

The invariants below are the harness-binding slate. They apply to
**every** A-tier prompt-block, B-bucket validator, hook, sandbox
layer, and future component in `src/fa/` that runs before or after
an LLM call.

## §1 The invariants (I-1..I-5)

Each invariant carries:

- **Rule** — the one-sentence constraint.
- **Source** — the deep-dive §1.x verbatim `file.ext:line` pattern
  the invariant abstracts from.
- **FA fit** — current FA component most at risk if the invariant is
  not enforced.
- **A/B-bucket cross-refs** — which §4 / §4a bucket entries
  instantiate or formalise the invariant.
- **Rule #10 4-question evidence** — per the AGENTS.md PR Checklist
  rule #10 minimalism-first binding constraint on harness-component
  PRs.

### I-1 — Single-source-of-truth classifier

**Rule.** When two B-bucket entries classify the *same* input shape
(e.g. «is this tool result a failure?»), exactly one MUST be the
canonical implementation; the other MUST delegate to it. Diverging
classifiers produce operator-visible / guardrail-invisible drift.

**Source.** hermes H3 — `hermes-agent/agent/tool_guardrails.py:189–221`
(`classify_tool_failure`); the docstring is the contract — «Mirrors
`agent.display._detect_tool_failure` exactly so the guardrail never
disagrees with the CLI's user-visible `[error]` tag.» See deep-dive
[`fa-abc-synthesis-deep-dive-2026-05.md` §1.3 H3 lines 855–915](../research/fa-abc-synthesis-deep-dive-2026-05.md#h3--single-source-of-truth-tool-failure-classifier).

**FA fit.** At-risk in `BashGate._classify_category` vs
`BashGate._validators_for_category` if a new category lands in one
but not the other (deep-dive §1.3 H3 FA-fit clause, lines 911–914).

**A/B-bucket cross-refs.** Extends v3 §0.4 classifier reject path
(deep-dive §5 C-3 lines 1898–1907 — «this B entry duplicates an
existing classifier without delegating → reject»). No new bucket
entry — this is an invariant on existing and future B-bucket entries.

**Rule #10 4-question evidence.**

1. *Research-evidence.* hermes H3 single-source-of-truth pattern at
   `tool_guardrails.py:189–221`; the contract is the docstring
   binding `classify_tool_failure` to `agent.display._detect_tool_failure`.
   Cited verbatim in deep-dive lines 855–895 (snippet) + lines 897–907
   (pattern + determinism-lens reading).
2. *Open-source precedent.* hermes-agent (NousResearch, Python)
   already enforces this discipline; the deep-dive surfaces the
   docstring-as-contract shape as the production pattern. The
   alternative — two B-bucket entries computing the same classification
   independently — is the failure mode hermes documented and removed.
3. *Capability lost if invariant omitted.* Operator-visible vs
   guardrail-invisible drift: the CLI shows `[ok]` while the
   guardrail counts the result as a failure (or vice-versa); the
   LLM sees one signal in scrollback and another in the next
   `BEFORE_TOOL_EXEC` hook fire, with no deterministic resolution.
4. *Could this be a deterministic Python function instead of an LLM
   call?* This IS the question — the invariant forces every
   classifier to be one such function with one canonical site. LLM
   judgement on «is this a failure» is forbidden when a
   deterministic classifier already exists.

### I-2 — Numbered MANDATORY workflows are A-bucket residue

**Rule.** Every numbered step in an agent-facing MANDATORY workflow
is a candidate for replacement by a harness function or a hook.
Steps that REMAIN in prose MUST be explicitly judgement-bound
(decision-making, not orchestration). Orchestration steps in prose
are a temporary harness gap, not a permanent design choice.

**Source.** gortex GX3 — `gortex/CLAUDE.md` MANDATORY workflow
(11 numbered steps) co-existing with `PreToolUse hooks deny
`Read` / `Grep` / `Glob` against indexed source; the deny message
names the right tool.` quoted in deep-dive
[`fa-abc-synthesis-deep-dive-2026-05.md` §1.4 GX3 lines 1157–1204](../research/fa-abc-synthesis-deep-dive-2026-05.md#gx3--mandatory-n-step-workflow-as-prose-a-tier-prompt-block).
The prose workflow is the **residue** of what the harness has not yet
mechanised (deep-dive lines 1183–1191).

**FA fit.** `AGENTS.md` §Pre-flight checklist (5 steps) — Steps 1-3
(recency-surface `git log`, term-expansion `grep glossary.md`,
symmetric-reading `grep -ril` over `knowledge/research/`) are
mechanisable; deep-dive v3 §3 A2 (`fa bootstrap`) is the harness-
level mechanisation. Steps 4-5 (subtraction-check + goal-lens
declaration) are judgement-bound and stay prose (deep-dive §1.4 GX3
FA-fit clause, lines 1193–1198).

**A/B-bucket cross-refs.** A2 (`fa bootstrap`, deep-dive v3
§3 — mechanises Pre-flight Steps 1-3); A21 (`fa lint-tools`,
deep-dive §4 lines 1814–1822 — same «numbered workflow → harness
linter» pattern applied to ToolSpec validation).

**Rule #10 4-question evidence.**

1. *Research-evidence.* gortex GX3 reverse-A pattern at
   `gortex/CLAUDE.md` (verbatim 11-step workflow quoted in deep-dive
   lines 1166–1173) + the `PreToolUse hooks deny ...` clause at
   lines 1180–1181 demonstrating the same prose-step → harness-rule
   conversion the invariant codifies.
2. *Open-source precedent.* gortex itself has migrated multiple
   workflow steps from prose to PreToolUse-hook denial (`Read` /
   `Grep` / `Glob` deny against indexed source). The remaining
   prose is the deliberate residue; the deep-dive's reverse-A
   reading at lines 1189–1191 frames every numbered MANDATORY step
   as a future A-bucket candidate.
3. *Capability lost if invariant omitted.* Prose workflows in
   agent-facing docs drift silently — weaker OSS LLMs (DeepSeek 4 /
   Kimi 2.6 per AGENTS.md target audience) paraphrase the steps,
   skip the trigger conditions, and re-derive workarounds. Without
   the invariant naming numbered prose as «temporary residue», the
   harness debt is invisible.
4. *Could this be a deterministic Python function instead of an LLM
   call?* For Steps 1-3 of AGENTS.md §Pre-flight, yes — `fa
   bootstrap` is the deterministic mechanisation. For Steps 4-5
   (subtraction-check + goal-lens declaration), no — these are
   judgement-bound. The invariant forces the dichotomy explicit at
   every numbered step.

### I-3 — Stable `[CODE]` prefix on every B-message

**Rule.** When a B-bucket entry produces text that re-enters the LLM
context (guard stop_message, validator rejection reason, retry
hint), that text MUST start with a `[CODE]` from a controlled
namespace, MUST quote the actual data (counts / limits / paths),
and MUST name the next action. Prose without structure produces
inconsistent LLM responses across providers.

**Source.** dpc D1 — five guard `stop_message()` implementations in
`dpc-messenger/dpc-client/core/dpc_client_core/dpc_agent/guards.py`:
`[ROUND_LIMIT]` at L40-44, `[TOOL_LIMIT]` at L69-75, `[RESEARCH_LIMIT]`
at L109-115, `[LOOP_GUARD]` at L167-174, `[BUDGET_LIMIT]` at
L208-213. Each follows the shape «`[STABLE_PREFIX]` data-shaped
explanation. concrete-next-action.» Quoted verbatim in deep-dive
[`fa-abc-synthesis-deep-dive-2026-05.md` §1.6 D1 lines 1541–1626](../research/fa-abc-synthesis-deep-dive-2026-05.md#d1--stable-code-prefix-on-every-guard-stop_message).

**FA fit.** `BashGate` and (future) `BudgetLimitGuard` already
partially follow this; the invariant formalises it for all B-bucket
entries. PR-4 / Wave-3 `CostGuardian` (R-45) emits
`cost=tokens_in=...` artifacts but its (future) gating message
needs the `[BUDGET_LIMIT]` prefix per D1.

**A/B-bucket cross-refs.** A23 — stable guard-message format
(deep-dive §4 lines 1835–1844 — formalises the namespace + lint).
Extends v3 B14 (output-validator regex) with the format invariant
the LLM-facing string must satisfy. Deep-dive §5 C-3 lines 1898–1907
classifies B-entries without `[CODE]` prefix as reject candidates.

**Rule #10 4-question evidence.**

1. *Research-evidence.* dpc-messenger five-guard stop_message
   convergence at `guards.py:40-44 / 69-75 / 109-115 / 167-174 /
   208-213` — verbatim Python snippets quoted in deep-dive lines
   1547–1597, all sharing the `[STABLE_PREFIX] data. action.` shape.
   The «A-tier prompt-injection format» reading is at lines 1608–1612.
2. *Open-source precedent.* dpc-messenger ships the pattern across
   five independent guard classes — the convergence is the evidence.
   Single-prefix or unprefixed messages are the silently-broken
   alternative; the deep-dive's determinism-lens reading at lines
   1601–1607 explains why structured prefixes win across providers.
3. *Capability lost if invariant omitted.* Unprefixed prose like
   «You called too many tools, please stop» produces inconsistent
   model responses across providers (Claude / DeepSeek / Kimi /
   Qwen) — see ADR-2 §Amendment 2026-05-20 family-disjoint rule's
   companion citation (Cornell Kim et al., ICML 2025) for why
   prompt-shape diversity across same-family models is sample-noise.
   Stable prefixes are the cross-provider stable signal.
4. *Could this be a deterministic Python function instead of an LLM
   call?* Yes — `stop_message()` is a deterministic format string.
   The LLM never composes guard messages. The invariant forces every
   guard to be such a function with a registered `[CODE]` namespace
   entry.

### I-4 — Typed loop-state ownership (loop OWNS, middleware READS)

**Rule.** State that middleware reads (round index, accumulated cost,
recent tool args) MUST live on a typed dataclass owned by the inner
loop; the loop updates it BEFORE firing hooks; middleware that needs
mutable counters keeps them on instance state, NEVER writes back to
the loop-owned dataclass.

**Source.** dpc D2 — `LoopState` dataclass in
`dpc-messenger/dpc-client/core/dpc_client_core/dpc_agent/hooks.py:44-66`
with the docstring «Mutation contract: the loop OWNS these fields
and updates them BEFORE calling `HookRegistry.fire()`; middleware
only reads them. Stale values at fire time produce wrong guard
decisions. Middleware that needs mutable counters keeps them on the
instance, not here.» Quoted verbatim in deep-dive
[`fa-abc-synthesis-deep-dive-2026-05.md` §1.6 D2 lines 1630–1672](../research/fa-abc-synthesis-deep-dive-2026-05.md#d2--typed-loop-state-ownership-re-cited-from-v3-28-sharpened).

**FA fit.** ADR-8 HookRegistry middleware-chain — `GuardMiddleware`
and `ObserverMiddleware` both receive a state object; the invariant
pins the ownership / mutation contract that ADR-8 §Decision (doc-
first BACKLOG M-1) does not yet name explicitly. Already absorbed
in deep-dive v3 §2.8 (re-cited at lines 1660–1664); re-stated here so
ADR-10 names it explicitly as a hook-pipeline binding constraint.

**A/B-bucket cross-refs.** No new bucket entry — the invariant
applies to all existing and future hook-pipeline middleware. Deep-
dive §5 C-3 lines 1898–1907 classifies «this entry writes to
LoopState from middleware → reject» as a classifier-reject path.

**Rule #10 4-question evidence.**

1. *Research-evidence.* dpc-messenger `LoopState` dataclass at
   `hooks.py:44-66` with the verbatim mutation-contract docstring
   quoted in deep-dive lines 1635–1658. The contract is in the
   docstring (lines 1639–1644), not in code — code-enforcement is
   the FA harness's job.
2. *Open-source precedent.* dpc-messenger demonstrates the
   loop-OWNS / middleware-READS pattern in a Python harness with
   multi-guard composition; the deep-dive v3 §2.8 absorbed it as a
   borrow target. The invariant elevates the docstring-only contract
   into a named ADR-10 rule.
3. *Capability lost if invariant omitted.* Middleware that mutates
   `LoopState` produces non-deterministic guard decisions: the next
   guard in the chain reads a state already mutated by the previous
   one, and the mutation order becomes part of the failure mode.
   Stale values at fire time produce wrong guard decisions
   (deep-dive lines 1641–1643 verbatim).
4. *Could this be a deterministic Python function instead of an LLM
   call?* Yes — `LoopState` is a `@dataclass`; the loop's update of
   it is a deterministic mutation, and middleware reads are
   side-effect-free. The invariant rules out any LLM-as-judge over
   loop state; the harness owns the data.

### I-5 — Layer-boundary fail-fast (validate at the outermost agent-facing surface)

**Rule.** When a request crosses multiple harness layers (CLI / MCP
surface → store / sandbox layer → SQLite / filesystem), validation
MUST occur at the *outermost* layer in the agent's path. Hard-limit
constants MUST carry a doc-comment naming the corresponding deeper-
layer constant. Locale / encoding MUST be normalised at the call
site, NEVER relied upon globally. Failure paths MUST NOT bubble a
SQLite / system error verbatim to the LLM — the error format is
implementation detail.

**Source.** rtk R8 (locale-stable parsing at the call site) at
`rtk/src/cmds/git/git.rs:14-50, 85-110` — the `git_cmd_c_locale`
helper forces `LC_ALL=C` *only* for internal parses where rtk depends
on English status phrases (deep-dive
[`fa-abc-synthesis-deep-dive-2026-05.md` §1.7 R8 lines 2268–2291](../research/fa-abc-synthesis-deep-dive-2026-05.md#r8--per-cmd-enum-gitcommand--locale-stabilising-helper)).
icm IC1 (MCP layer-boundary validation with comment-as-spec) at
`icm/crates/icm-mcp/src/tools.rs:15-32, 52-64` — the `MAX_TOPIC_LEN`
constant's doc-comment names the store-layer `MAX_TOPIC_BYTES` it
must stay ≤ (deep-dive
[`fa-abc-synthesis-deep-dive-2026-05.md` §1.9 IC1 lines 2547–2588](../research/fa-abc-synthesis-deep-dive-2026-05.md#ic1--mcp-layer-boundary-validation-with-comment-as-spec)).
Mapped explicitly as the §3a I-5 invariant at deep-dive lines
2936–2950.

**FA fit (at-risk surfaces per deep-dive §3a lines 2947–2950).**
- `BashGate` path-containment currently validates in-process; if FA
  grows MCP / external orchestrator surface, this needs an MCP-layer
  mirror with the relationship documented inline.
- DSV YAML parsing — locale-dependent? Re-check; the rtk R8 pattern
  is the call-site fix.
- Chunker — if external file paths reach the chunker, normalise
  encoding upfront, not at the SQLite layer.

**Detection rules (deep-dive §3a lines 2942–2945).** An entry
violates I-5 if:
- Its hard-limit constant lacks a doc-comment naming the
  corresponding deeper-layer constant.
- Its parsing helper does not pin locale at the call site.
- A failure path bubbles up a SQLite / system error verbatim to the
  LLM.

**A/B-bucket cross-refs.** B23 — fail-fast layer-boundary validation
(deep-dive §4a lines 3015–3019 — explicitly «Formalises ADR-10
invariant I-5»); A24 — exit-code-encoded hook protocol (deep-dive
§4a lines 2960–2964, related «outermost-layer-is-the-contract»
shape); A28 — enum-label + harness-derived weight (deep-dive §4a
lines 2984–2988 — same «outer schema is the agent contract, inner
weight is implementation detail» discipline).

**Rule #10 4-question evidence.**

1. *Research-evidence.* rtk R8 `git_cmd_c_locale` at
   `rtk/src/cmds/git/git.rs:41-48` and icm IC1 `MAX_TOPIC_LEN`
   doc-comment at `icm/crates/icm-mcp/src/tools.rs:15-32` — both
   quoted verbatim in deep-dive lines 2279–2285 and 2552–2566. The
   §3a synthesis (lines 2938–2950) abstracts the layer-boundary
   fail-fast pattern from the two snippets.
2. *Open-source precedent.* rtk-ai (rtk + icm) ships both the
   parsing-site fix and the MCP-layer constant convention; the
   deep-dive's «highest-leverage A-bucket pattern» reading for IC2
   (deep-dive lines 2635–2637) extends the same «outer surface is
   the contract» philosophy to I-5.
3. *Capability lost if invariant omitted.* (a) Locale-dependent
   parsing failures that surface as silent guardrail bypass when a
   user runs FA under a non-`C` locale; (b) MCP / external surface
   accepts inputs larger than the store layer, producing confusing
   storage-layer errors instead of agent-friendly schema rejections;
   (c) SQLite errors leak verbatim into LLM scrollback, breaking the
   `[CODE]` namespace contract from I-3.
4. *Could this be a deterministic Python function instead of an LLM
   call?* Yes — layer-boundary validation is a constant-comparison
   + locale-pin function. The LLM never decides whether an input
   passes a hard limit. The invariant pins this discipline at the
   outermost surface, removing any LLM degree-of-freedom on the
   limit-check.

## §2 Cross-cutting clauses

### §2.1 Re-evaluation triggers

The invariants apply to v0.1 under UC1 + UC3 single-user scope.
Re-evaluation triggers:

1. **UC5 lands (eval-driven harness iteration).** Per AGENTS.md
   PR Checklist rule #10 closing clause, KPI-delta on a
   reproducible benchmark replaces the 4-question evidence for
   measurably evaluated harness components. The invariants stay,
   but each I-N's «capability lost» clause should grow a measured
   KPI reference.
2. **MCP / external orchestrator surface lands.** I-5's «outermost
   layer» definition expands: today the CLI parser + sandbox is the
   outermost surface; an MCP server would make it the new outermost
   layer, and existing constants need the IC1-style cross-layer
   doc-comments.
3. **Second LLM-emitted numeric dimension surfaces** (e.g. an Eval
   role emits a confidence score). I-1 + I-3 + the deep-dive's A28
   («enum-label + harness-derived weight») compose: the dimension
   MUST be a closed enum, NOT a number, with a single classifier
   site (I-1) and a stable label namespace (I-3 prefix shape).
4. **First hook in `src/fa/inner_loop/hooks/` writes back to
   `LoopState`.** I-4 forbids this; the re-evaluation trigger is
   for a hook that NEEDS to track state across `HookRegistry.fire()`
   calls — the answer is instance state on the hook, not
   `LoopState`.
5. **A new B-bucket entry overlaps an existing classifier.** I-1
   forces delegation; the re-evaluation trigger is a B-entry whose
   classification logic is genuinely orthogonal (e.g. a future
   `classify_tool_safety` distinct from `classify_tool_failure`) —
   the invariant accepts the new entry but pins it as a separate
   canonical site.

### §2.2 Open questions (deep-dive §6 unresolved)

Deep-dive §6 ships five unresolved open questions (Q1-Q5 numbered
within the research note, NOT the `exploration_log.md` Q-N
numbering). Per the §6 «default proposal» clauses, they are
**unresolved** at ADR-10 acceptance time and **NOT** re-litigated
here:

1. Q1 — A16 (`fa doctor`) scoring weights (default: copy gbrain).
2. Q2 — A17 (`fa verify-state`) auto-heal scope (default:
   regenerate-only).
3. Q3 — A18 (`fa sanitize-tool-schemas`) urgency (default: defer).
4. Q4 — B19 (tool-call coerce-then-check) aggressiveness
   (default: yes, coerce JSON-string args).
5. Q5 — B21 (input-side shield) scope (default: spec-only until
   UC5).

Deep-dive §6a (lines 3023–3031) resolves Q6-Q9 (A24 deferred, A28
audit yes, A29 explicit-frontmatter category, I-5 audit deferred
until ADR-10 lands). §6b resolves Q10 (§1.2.5 vs Pillar 5 → §1.2.5).
**ADR-10 does NOT re-open Q6-Q10.**

## Consequences

- **Positive.**
  - Single named slate every future harness-component PR cites in
    its rule #10 4-question evidence cell (`see ADR-10#i-N`).
  - DIGEST.md grows by one row; HANDOFF.md grows by one bullet;
    `exploration_log.md` grows by one Q-N block. The cheap-read
    overlay scales linearly with ADR count.
  - The deep-dive's §3 + §3a evidence chain (9 OSS stacks ×
    verbatim `file.ext:line` citations) is now consumable by
    future-agent reading the ADR directly; no need to re-read the
    19 k-word deep-dive.
  - Compliance-by-construction principle has both a doc home
    ([`project-overview.md` §1.2.5](../project-overview.md#125--compliance-by-construction-failure-observable))
    and a rule-set home (this ADR's §1).

- **Negative.**
  - One new file under `knowledge/adr/`; offset by the cross-
    cutting reading the invariants enable.
  - Future harness-component PRs now MUST cite an `ADR-10#i-N`
    section in their rule #10 evidence — small friction at PR
    review time. Documented as a deliberate cost.

- **Follow-up work this unlocks or requires.**
  - **I-5 FA-surface audit** (deep-dive §6a Q4 resolved «defer
    until ADR-10 lands, then audit as one focused PR»). Audit:
    `fa` CLI parser, DSV YAML loader, chunker, BashGate. One PR.
  - **A28 audit** (deep-dive §6a Q2 resolved «yes, single-pass
    audit»). Audit FA today for «LLM emits a number» candidates.
    Single-pass; no obvious candidates expected per deep-dive line
    2987.
  - **I-3 namespace formalisation.** Register the `[CODE]`
    namespace (`[ROUND_LIMIT]`, `[TOOL_LIMIT]`, `[BUDGET_LIMIT]`,
    `[LOOP_GUARD]`, `[BASH_DENY]`, …) in a single constants module;
    add a pytest hook that lints every guard's `stop_message()`
    starts with a registered prefix.
  - **A23 lint** (deep-dive §4 lines 1835–1844). Tiny PR — adds
    the namespace + pytest hook that enforces I-3.

## Prior Art

Per [AGENTS.md §Cross-project anti-patterns rule
#4](../../AGENTS.md#cross-project-anti-patterns---learnt-from-precedents) (forward-only
from 2026-05-20). Each prior-art entry maps a design choice in
this ADR to an existing project / paper / FA prior decision, so
reviewers can verify FA is not re-inventing. Full audit evidence
lives in the input research note
[`fa-abc-synthesis-deep-dive-2026-05.md`](../research/fa-abc-synthesis-deep-dive-2026-05.md)
§1.x (9 OSS-stack survey, verbatim `file.ext:line` per pattern)
and §3 + §3a (synthesis lens). This section condenses the six
per-design-choice mappings into one readable block — answering
«What did we look at? Which projects already solved this? Why
are we not reusing them verbatim?».

- **§Decision Option C — single cross-cutting ADR carrying named
  invariants I-1..I-5 (chosen).** Looked at: dpc-messenger
  ADR-002 «AbstractLLMProvider» ABC + 5 provider files (single
  ADR carrying a multi-rule contract) cited via
  [`dpc-messenger-inspiration-2026-05.md`](../research/dpc-messenger-inspiration-2026-05.md)
  §2 + §6 AP8 prior-art clause; ADR-8 §1 «one ADR, multiple
  middleware kinds» (the in-repo precedent at
  [`ADR-8-hook-registry.md`](./ADR-8-hook-registry.md)
  §Decision). Why not reusing verbatim: dpc ships an
  *interface* contract (one ABC + per-provider files); FA
  ADR-10 ships a *cross-cutting invariant slate* — five named
  rules every harness layer must satisfy, no per-layer ADR
  proliferation. The «one ADR per cross-cutting concern»
  shape matches ADR-8's multi-middleware-kind pattern, not
  dpc's per-provider pattern. Options A (defer into
  ADR-6/7/8 amendments), B (5 micro-ADRs), D (inline into
  AGENTS.md PR Checklist) rejected per §Options considered
  with reasons therein; the deep-dive §3 + §3a authored the
  invariants as a single slate keyed on one goal lens, and
  splitting them inverts the author's framing.

- **§1 I-1 single-source-of-truth classifier (hermes H3).**
  Looked at: hermes-agent
  `hermes-agent/agent/tool_guardrails.py:189-221`
  `classify_tool_failure` (NousResearch, Python) — the
  docstring-as-contract pattern binding the guardrail
  classifier to `agent.display._detect_tool_failure`,
  verbatim in deep-dive
  [§1.3 H3 lines 855–915](../research/fa-abc-synthesis-deep-dive-2026-05.md#h3--single-source-of-truth-tool-failure-classifier).
  The reject path for «two B-bucket entries independently
  computing the same classification» is documented in deep-
  dive §5 C-3 (lines 1898–1907). Why not reusing verbatim:
  hermes' pattern is the production shape FA borrows; the
  ADR-10 lift abstracts the «docstring-as-contract»
  discipline into the invariant statement so it covers
  FA-specific sites (`BashGate._classify_category` vs
  `BashGate._validators_for_category` per §1 I-1 FA-fit
  clause + deep-dive §1.3 H3 lines 911–914) rather than
  re-implementing hermes' guardrail file 1:1. Hermes itself
  is closed-source for the surrounding harness; FA borrows
  the discipline, not the file.

- **§1 I-2 numbered MANDATORY workflows are A-bucket residue
  (gortex GX3).** Looked at: gortex `gortex/CLAUDE.md`
  11-step MANDATORY workflow co-existing with the
  `PreToolUse hooks deny `Read` / `Grep` / `Glob` against
  indexed source` clause — quoted verbatim in deep-dive
  [§1.4 GX3 lines 1157–1204](../research/fa-abc-synthesis-deep-dive-2026-05.md#gx3--mandatory-n-step-workflow-as-prose-a-tier-prompt-block)
  (snippet 1166–1181, reverse-A reading 1189–1191). Why not
  reusing verbatim: gortex *demonstrates* the prose-residue /
  hook-mechanisation dichotomy by historical accident
  (multiple workflow steps migrated to PreToolUse-hook
  denial over time, leaving the rest as prose). FA ADR-10
  lifts the dichotomy into a *forward* discipline — every
  numbered MANDATORY step is named as either «mechanisable
  → A-bucket candidate» or «judgement-bound → permanent
  prose» — so future PRs cannot accumulate orphan numbered
  prose. AGENTS.md §Pre-flight Steps 1-3 (mechanisable via
  `fa bootstrap` A2, deep-dive v3 §3 A2) vs Steps 4-5
  (judgement-bound: subtraction-check + goal-lens
  declaration) instantiates the dichotomy per §1 I-2 FA-fit
  clause + deep-dive §1.4 GX3 lines 1193–1198.

- **§1 I-3 stable `[CODE]` prefix on every B-message (dpc
  D1).** Looked at: dpc-messenger five-guard
  `stop_message()` convergence across
  `dpc-messenger/.../guards.py:40-44 / 69-75 / 109-115 /
  167-174 / 208-213` — five independent guard classes
  sharing the `[STABLE_PREFIX] data. action.` shape, quoted
  verbatim in deep-dive
  [§1.6 D1 lines 1541–1626](../research/fa-abc-synthesis-deep-dive-2026-05.md#d1--stable-code-prefix-on-every-guard-stop_message).
  The A-tier prompt-injection reading at lines 1608–1612
  (LLM never composes the guard text; the harness emits a
  deterministic format-string). The cross-provider noise
  motivation links back to ADR-2 §Amendment 2026-05-20
  family-disjoint rule + Cornell Kim et al., ICML 2025
  sample-noise across same-family models cited in
  [`correlated-llm-errors-and-ensembling-2026-05.md`](../research/correlated-llm-errors-and-ensembling-2026-05.md)
  §4.4. Why not reusing verbatim: dpc's `stop_message()`
  function bodies are domain-specific (round / tool /
  research / loop / budget limits); FA ADR-10 lifts the
  *format-string discipline* and the *registered-prefix
  namespace* requirement, not the function bodies. The A23
  lint (deep-dive §4 lines 1835–1844) is the FA-specific
  enforcement mechanism dpc does not have.

- **§1 I-4 typed loop-state ownership / loop OWNS, middleware
  READS (dpc D2).** Looked at: dpc-messenger `LoopState`
  dataclass at
  `dpc-messenger/.../hooks.py:44-66` with the verbatim
  mutation-contract docstring quoted in deep-dive
  [§1.6 D2 lines 1630–1672](../research/fa-abc-synthesis-deep-dive-2026-05.md#d2--typed-loop-state-ownership-re-cited-from-v3-28-sharpened)
  (snippet 1635–1658, contract clause 1639–1644). Already
  absorbed by deep-dive v3 §2.8 as a borrow target. ADR-8
  HookRegistry middleware-chain `GuardMiddleware` /
  `ObserverMiddleware` is the FA-side binding consumer
  ([`ADR-8-hook-registry.md`](./ADR-8-hook-registry.md)
  §Decision). Why not reusing verbatim: dpc's contract
  lives in a Python docstring (no code-enforcement); FA
  lifts the *named-invariant* shape so the rule is citable
  from future hook PRs (`see ADR-10#i-4`) instead of relying
  on every middleware author re-reading the dataclass
  docstring. Code-enforcement (pytest hook on middleware
  signatures) is FA-specific future work documented under
  §Consequences «Follow-up work this unlocks or requires».

- **§1 I-5 layer-boundary fail-fast (rtk R8 + icm IC1).**
  Looked at: rtk `git_cmd_c_locale` helper at
  `rtk/src/cmds/git/git.rs:14-50, 85-110` (locale-stable
  parsing pinned at the call site, NOT relied upon globally)
  + icm `MAX_TOPIC_LEN` constant doc-comment at
  `icm/crates/icm-mcp/src/tools.rs:15-32, 52-64` (the
  doc-comment names the deeper-layer store constant
  `MAX_TOPIC_BYTES` the outer constant must stay ≤). Both
  quoted verbatim in deep-dive
  [§1.7 R8 lines 2268–2291](../research/fa-abc-synthesis-deep-dive-2026-05.md#r8--per-cmd-enum-gitcommand--locale-stabilising-helper)
  and
  [§1.9 IC1 lines 2547–2588](../research/fa-abc-synthesis-deep-dive-2026-05.md#ic1--mcp-layer-boundary-validation-with-comment-as-spec).
  Synthesised at §3a lines 2936–2950 as the I-5 detection
  rule set (hard-limit constant must doc-link the
  deeper-layer constant; parsing helper must pin locale at
  call site; failure path MUST NOT bubble verbatim SQLite /
  system errors to the LLM). Why not reusing verbatim: rtk
  and icm ship the Rust patterns; FA lifts the *two
  detection-rule axes* (locale-pin call site + comment-as-
  spec on layer-boundary constants) plus the SQLite-leak
  forbidding clause that ties I-5 to I-3 (the verbatim
  error text would break the registered `[CODE]` namespace).
  The FA at-risk surfaces — `BashGate` path-containment,
  DSV YAML loader, chunker — are FA-specific per deep-dive
  §3a lines 2947–2950 and not covered by either rtk or icm
  directly.

## References

- [`knowledge/research/fa-abc-synthesis-deep-dive-2026-05.md`](../research/fa-abc-synthesis-deep-dive-2026-05.md)
  §3 + §3a (the invariant authoring source); §0c jump-table for the
  ≤ 5 k targeted-read order; §4 + §4a A12..A29 + B14..B23 bucket
  entries; §6 + §6a + §6b open-question state.
- [`knowledge/project-overview.md` §1.2.5](../project-overview.md#125--compliance-by-construction-failure-observable)
  — companion §1.2.5 landing decided per deep-dive §6b; carries the
  five KPI candidates the invariants instantiate.
- [`pr-creation` skill §PR Checklist rule #9](../skills/pr-creation/SKILL.md#pr-checklist)
  — exploration_log + DIGEST + HANDOFF same-PR enforcement.
- [`pr-creation` skill §PR Checklist rule #10](../skills/pr-creation/SKILL.md#pr-checklist)
  — 4-question minimalism-first evidence binding constraint on
  harness-component PRs; this ADR's §1 per-invariant evidence cells
  satisfy it for I-1..I-5.
- [`ADR-6`](./ADR-6-tool-sandbox-allow-list.md) — sandbox boundary
  (I-5 outermost-layer candidate).
- [`ADR-7`](./ADR-7-inner-loop-tool-registry.md) — inner-loop &
  tool-registry contract (I-2 Pre-flight residue + I-3 hook-pipeline
  consumer).
- [`ADR-8`](./ADR-8-hook-registry.md) — HookRegistry middleware-chain
  (I-1 + I-4 binding ADRs).
- [`ADR-9`](./ADR-9-llm-provider-client.md) — LLM provider client
  (cost+token accounting source, downstream consumer of I-3
  `[CODE]` prefix for CostGuardian gating).
- [`knowledge/trace/exploration_log.md` Q-14](../trace/exploration_log.md#q-14--what-deterministic-harness-invariants-does-the-adr-10-slate-carry-and-where-do-they-live-2026-05-25)
  — alternatives considered + rejected at ADR-10 decision time.
