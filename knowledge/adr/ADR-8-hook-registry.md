# ADR-8 — HookRegistry middleware chain (doc-first; runtime Phase-M)

- **Status:** accepted
- **Date:** 2026-05-20
- **Deciders:** project owner (`0oi9z7m1z8`), Agent (drafting)

## Context

[ADR-7](./ADR-7-inner-loop-tool-registry.md) §8 ships a deliberately
minimal hook pipeline in v0.1: two `pre_tool` hooks (`SandboxHook`,
`ApprovalHook`) plus one `post_tool` hook (`AuditHook`). The §8
footer reserves `pre_run` / `post_run` / `on_event` for future
amendment, and the
[ADR-7 §Amendment 2026-05-20](./ADR-7-inner-loop-tool-registry.md#amendment-2026-05-20--retry-budget-invariant-intra-role-t10-llm-using-hook-family-disjoint-rule)
already imposes invariants (retry-budget config-bounded,
`max_iterations=6`, T=1.0 intra-role retry, LLM-using-hook
family-disjoint) that **only make sense if there is a registry
to attach those hooks to**. Wave-2 work in
[`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
(R-2 `LoopGuard`, R-3 failure-classifier dispatcher, R-4
pre-tool blocker, R-22 PII redaction walker) also assumes the same
substrate.

Today FA does NOT have an inner-loop runtime — `src/fa/inner_loop/`
does not exist; the chunker package is the only landed feature
module. Landing a full runtime now would multiply scope for a Wave-1
PR and contradict the four-pillar discipline (PR-1 explicitly
shipped the Wave-0 standalone modules `verifier` / `tools` /
`hygiene` *inert* — same principle applies here).

This ADR therefore freezes the **HookRegistry contract** as
documentation. No code lands in this PR. The runtime implementation
is Phase-M scope and will land in a follow-up PR explicitly
referenced from
[`knowledge/BACKLOG.md`](../BACKLOG.md) (M-1 "inner-loop scaffolding").
That follow-up PR will:

1. Build `src/fa/inner_loop/registry.py` + `loop.py` against
   this contract.
2. Wire the three v0.1 hooks (`SandboxHook`, `ApprovalHook`,
   `AuditHook`) through it without changing their semantics.
3. Add the Wave-2 middlewares (R-2..R-5/R-22) one ADR-amendment
   at a time on top of the same registry shape.

Source (8-project convergence): `borrow-roadmap-2026-05.md` §R-1
+ `dpc-messenger-inspiration-2026-05.md` §0 R-1 (primary —
DPC `dpc_agent/hooks.py` 207 LOC + `dpc_agent/guards.py` 222 LOC)
+ `gortex-aperant-inspiration-2026-05.md` Addendum I (Gortex
`internal/hooks/dispatch.go` 38 LOC; convergence-only).

## Options considered

### Option A — Keep ADR-7 §8 mini-pipeline; add new hooks as one-off bullet entries

- Pros: zero new ADR; matches the deliberate minimalism of v0.1.
- Cons:
  - ADR-7 §Amendment 2026-05-20 already specifies cross-cutting
    invariants (retry-budget, family-disjoint, T=1.0) that
    do NOT fit the "one hook per bullet" shape — they apply
    to *classes* of hooks (LLM-using vs not, retry-loops vs
    not). A registry distinguishes those classes; the bullet
    list does not.
  - Wave 2 adds 4-5 new hooks (`LoopGuard`, failure classifier
    dispatcher, pre-tool blocker, PII redaction walker,
    `attempt_history.json` writer). Each one as a bullet
    would push ADR-7 §8 past 200 lines and lose readability.
  - DPC ADR-007 lists the same anti-pattern as a top-3 ADR
    regret: "we built guards inline; should have built a
    registry first".

### Option B — Full runtime now (registry + loop + dispatcher + first 4 middlewares)

- Pros: nothing inert; immediate value from `LoopGuard` (R-2)
  and failure-classifier dispatcher (R-3).
- Cons:
  - Pulls Wave-2 R-Ns into a Wave-1 PR. Bloats scope by ~600
    LOC and ties merge of the contract to the correctness of
    every middleware on top of it. Aperant TS hit this exact
    rake (see `gortex-aperant-inspiration-2026-05.md` Aperant
    item 11 "we wrote LoopGuard + registry as one PR; rolled
    back twice").
  - The user explicitly bounded Wave 1 to "5 R-Ns, ~2-3 weeks
    parallel" in
    [`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
    §3. Landing Wave-2 R-Ns here violates that envelope.
  - First-Agent's documented stance (rule #10 question 4)
    is that scaffolding without first writing the contract
    text amounts to step-as-LLM-call masquerading as
    step-as-function — the registry contract IS the function
    signature here.

### Option C — Doc-first ADR-8 with explicit Phase-M deferral (chosen)

Promote the mini hook-pipeline from ADR-7 §8 footer to a first-class
**registry contract** in this ADR. Specify:

1. Lifecycle points (5).
2. Middleware kinds (2; `GuardMiddleware` vs `ObserverMiddleware`).
3. Dispatcher shape (ordered chain; first-deny short-circuits;
   one mutation per dispatch; observer errors swallowed at DEBUG).
4. Error semantics + retry budgets (cross-ref to ADR-7 §Amendment
   2026-05-20).
5. Migration plan from current v0.1 inline hooks.
6. Test substrate (mock middlewares; deterministic dispatch trace).
7. Acceptance criteria.

No code in this PR. Runtime tracked in `BACKLOG.md` M-1.

- Pros:
  - The Wave-2 R-Ns (R-2/R-3/R-4/R-5/R-22) each get a tiny
    "add one `GuardMiddleware` subclass" PR shape — the contract
    is the merge surface, not the runtime.
  - Subtraction-first: ADR-7 §8 mini-pipeline shrinks to a
    cross-ref to this ADR after the runtime lands; net document
    growth is bounded.
  - Allows Wave-2 review to focus on individual middleware
    *behaviour*, not on dispatch mechanics that should be
    settled once and reused.
- Cons:
  - One more ADR to read at session start (mitigated by
    DIGEST.md row).
  - The doc-first approach risks "we wrote the contract but
    never built the runtime" rot. Mitigated by the explicit
    M-1 BACKLOG entry and the
    [`HANDOFF.md`](../../HANDOFF.md) §Next steps tracking.

## Decision

We will choose **Option C** because the registry contract is the
single artefact the four Wave-2 middlewares all need, and writing
it once now lets each middleware PR land as a ~100-LOC
`GuardMiddleware` subclass against a frozen shape.

### 1. Lifecycle points

Five named lifecycle points; middlewares attach at one or more
of them. Order is left-to-right in the loop body:

```text
session_start
   ↓
[BETWEEN_ROUNDS]  ← runs at the top of every loop iteration
   ↓
[BEFORE_LLM_CALL] ← about to dispatch a Planner/Coder/Eval turn
   ↓
LLM provider call
   ↓
[AFTER_LLM_CALL]  ← LLM returned; may contain tool calls
   ↓
   for each tool call in the LLM response:
     [BEFORE_TOOL_EXEC]  ← gates the exec; can deny / modify
        ↓
     tool handler runs
        ↓
     [AFTER_TOOL_EXEC]   ← gates the result; observation-only
   ↓
loop body completes; result appended to conversation
   ↓
session_end (no hook point in v0.1; lands with UC5)
```

Naming convention: ALL_CAPS_SNAKE — matches the borrow-roadmap
§R-1 nomenclature and DPC `dpc_agent/hooks.py:LIFECYCLE_POINTS`
verbatim. Stable: middlewares cite point names in their
`attaches_to` declaration; renaming a point is a breaking
contract change tracked by ADR amendment.

### 2. Middleware kinds

Two kinds; orthogonal axes:

- **`GuardMiddleware`** — may deny / modify / short-circuit.
  Errors thrown inside it propagate up the loop body and abort
  the current turn (matches ADR-2 "Coder fails loudly").
  Return shape: `Decision.allow()` | `Decision.deny(reason)` |
  `Decision.modify(new_payload)`. The dispatcher enforces
  ADR-7 §8 "one mutation per dispatch" — second `modify`
  return anywhere in the chain is a hard error
  (`error.code = "hook_double_mutation"`,
  `retryable = false`).
- **`ObserverMiddleware`** — read-only; errors thrown inside it
  are logged at DEBUG and **swallowed** so observation cannot
  break the turn. Return type is `None`. Matches DPC
  `dpc_agent/hooks.py:Observer` exactly; FA does not invent
  new return shapes.

A middleware MUST declare its kind in code (`class Foo(GuardMiddleware)`).
The registry refuses to register a class that does not subclass
exactly one of the two base classes.

### 3. Registry shape (in-memory; per-process)

```python
class HookRegistry:
    """Per-process registry; one instance lives on the loop driver."""

    def register(self, middleware: Middleware) -> None:
        """Validate kind + lifecycle points; append to the
        per-point chain in declaration order. Idempotent — registering
        the same instance twice is a no-op."""

    def dispatch(
        self,
        point: LifecyclePoint,
        payload: HookPayload,
    ) -> HookPayload:
        """Run the chain for `point` against `payload`. Returns the
        possibly-modified payload (Guard side) or the original
        (Observer side). Records each step into the trace via
        `events.jsonl` `kind == "hook_decision"`."""
```

Order of registration === order of execution; the registry does
NOT auto-sort middlewares. Insertion order ties to PR landing
order (later PR appends to the existing chain). When two
middlewares semantically conflict (e.g. two `BEFORE_TOOL_EXEC`
GuardMiddlewares both want to mutate params), the first-mutation-
wins rule from ADR-7 §8 applies.

### 4. Error semantics + retry budgets

Cross-reference to
[ADR-7 §Amendment 2026-05-20](./ADR-7-inner-loop-tool-registry.md#amendment-2026-05-20--retry-budget-invariant-intra-role-t10-llm-using-hook-family-disjoint-rule).
This ADR does NOT restate those invariants; it merely declares
the **enforcement points**:

- The dispatcher reads `retry_budget` per middleware from
  `~/.fa/config.yaml` (not hard-coded constants in middleware
  Python).
- The default `max_iterations = 6` lives on the loop driver,
  not on the registry — registries do not own retry caps.
- A middleware that itself issues an LLM call (e.g. failure-
  classifier dispatcher R-3, future LLM-judge guards) MUST
  set `attaches_to_role` to a **different family** than the
  acting role per the family-disjoint rule. The registry
  rejects middlewares that violate this at `register()` time.

### 5. Migration plan from v0.1 inline hooks

Once `src/fa/inner_loop/registry.py` lands (BACKLOG M-1), the
three v0.1 hooks change shape:

| v0.1 hook | New base class | Lifecycle point(s) |
|-----------|----------------|--------------------|
| `SandboxHook` | `GuardMiddleware` | `BEFORE_TOOL_EXEC` |
| `ApprovalHook` | `GuardMiddleware` | `BEFORE_TOOL_EXEC` |
| `AuditHook` | `ObserverMiddleware` | `AFTER_TOOL_EXEC` |

Semantics unchanged. ADR-7 §8 §"v0.1 ships exactly two hooks"
text becomes a cross-ref to ADR-8 §5 after migration; this
ADR-8 §5 row stays as the durable mapping.

### 6. Test substrate

The runtime PR (M-1) MUST land with:

- A `tests/test_hook_registry.py` covering registration order,
  first-deny short-circuit, observer error swallow, double-mutation
  hard error, family-disjoint rejection.
- A `MockGuard` / `MockObserver` pair (in `tests/conftest.py` or
  `src/fa/inner_loop/testing.py`) that records each call into
  a list — Wave-2 middleware tests reuse the same fixtures.

No tests in **this** PR (doc-only). The test specification above
is the merge gate for the runtime PR, not for ADR-8.

### 7. Acceptance criteria for the runtime PR (M-1)

Per [`pr-creation` skill §PR Checklist rule #10](../skills/pr-creation/SKILL.md#pr-checklist)
4-question minimalism-first test:

1. **Research-evidence:** 8-project convergence (DPC ADR-007,
   Gortex `internal/hooks`, Aperant `orchestration/hooks.ts`,
   Kronos `hooks.py`, four others cited in DPC ADR-007).
   `borrow-roadmap-2026-05.md` §R-1.
2. **OSS precedent that did NOT add a registry:** ampcode's
   inline if/elif (cited in
   [`research/how-to-build-an-agent-ampcode-2026-04.md`](../research/how-to-build-an-agent-ampcode-2026-04.md))
   — works for a 2-hook contract but degrades as soon as
   loop-guard / blocker / PII middlewares enter the picture.
3. **Capability lost if omitted:** Wave-2 middlewares each
   become a 100-LOC PR that touches inner_loop call-sites;
   review burden multiplies; ADR-7 §Amendment 2026-05-20
   invariants get re-implemented per middleware instead of
   enforced once at the registry boundary.
4. **Could the registry be a deterministic Python function
   instead of LLM call?** YES — the registry IS a pure Python
   function (a dispatcher). No LLM in the registry; LLM-using
   middlewares are application-level code on top of it (subject
   to the family-disjoint rule).

## Consequences

- **Positive:**
  - Wave-2 R-Ns (R-2/R-3/R-4/R-5/R-22) get a single merge
    surface — each lands as a 100-LOC `GuardMiddleware` /
    `ObserverMiddleware` subclass against this contract.
  - ADR-7 §8 mini-pipeline footer shrinks to a cross-ref
    after M-1 lands; net document growth is bounded.
  - ADR-7 §Amendment 2026-05-20 invariants get a concrete
    enforcement point (the `register()` family-disjoint check
    + the dispatcher retry-budget read).
- **Negative:**
  - One more ADR at session start (mitigated by DIGEST.md row
    and llms.txt routing entry).
  - Doc-first approach risks "wrote the contract; never built
    the runtime". Mitigated by BACKLOG.md M-1 entry +
    HANDOFF.md Next steps tracking.
- **Follow-up work this unlocks or requires:**
  - **M-1 (runtime):** Build `src/fa/inner_loop/registry.py`
    + `loop.py` against this contract.
  - **Wave 2:** R-2 (`LoopGuard`), R-3 (failure-classifier
    dispatcher), R-4 (pre-tool blocker), R-5 (DSV integration —
    currently Wave-0 standalone `src/fa/verifier/`).
  - **Wave 3:** R-22 (PII redaction walker as
    `ObserverMiddleware` on `AFTER_TOOL_EXEC`).
  - **AGENTS.md update at M-1:** add rule about declaring
    `attaches_to` + `attaches_to_role` in middleware classes.

## Amendment 2026-05-20a — sandbox re-check carve-out (`revalidates_after_modify`)

**Tension to resolve.** ADR-7 §5 + §8 require that after a
`Decision.modify`, both JSON-Schema validation AND sandbox path-
containment re-run on the mutated payload (so a hook cannot silently
rewrite `path` to escape the workspace root). ADR-8 §3 above states
"already-run hooks 1..N-1 do not re-run after a downstream modify".
These two rules genuinely conflict for the sandbox-on-modify case.

**Carve-out (now part of this ADR's contract).**

1. The base `Middleware` class carries one extra class-level flag:
   ```python
   revalidates_after_modify: bool = False  # default
   ```
2. A middleware sets it to `True` to declare "if any later guard in
   the same dispatch returns `Decision.modify`, the registry MUST
   replay my `handle()` against the mutated payload before continuing
   the chain". Only `SandboxHook` opts in today; future guards that
   need post-modify revalidation (e.g. a path-containment variant)
   add the flag too.
3. The "one mutation per dispatch" rule from §3 still holds:
   a replayed guard MAY NOT itself return `Decision.modify`. If it
   does, the registry raises `hook_double_mutation` immediately.
4. A `Decision.deny` from any replayed guard short-circuits the
   chain the same way an in-line deny would (raises `PermissionError`
   out of `HookRegistry.dispatch`; loop driver converts it to a
   `ToolResult.fail("hook_deny", ...)` for `BEFORE_TOOL_EXEC` denials,
   or to a `kind="run_stopped"` row for `BETWEEN_ROUNDS` denials).
5. The dispatch trace marks every replayed step with an `@replay`
   suffix on `DispatchRecord.middleware` so an operator can tell
   baseline vs revalidation rows apart in `events.jsonl`.

**Why this is a carve-out and not a general "always replay" rule.**

Auto-replaying every prior guard on every modify would silently
re-run side-effectful Observers and any guard whose handler is
expensive — and it would invite a footgun where a mutator + a
non-idempotent guard combine to make `dispatch` quadratic in
chain length. The explicit opt-in keeps replays bounded to the
guards that actually need them (today: one; tomorrow: possibly two
or three) and forces each opt-in to come with an integration test
covering the modify-then-replay path (see
`tests/test_inner_loop_validation.py::test_modify_to_escape_is_caught_by_sandbox_replay`).

**Forward-only.** Applies to M-1 onwards; no Wave-0 code paths
existed to migrate.

## Amendment 2026-05-20b — `BETWEEN_ROUNDS` fires before iteration 1 too

**Ambiguity to resolve.** §1 above shows `BETWEEN_ROUNDS` at the top
of each iteration in the ASCII diagram and notes «runs at the top of
every loop iteration», but neither the §1 enum nor the §3 dispatch
rules pinned down whether the first iteration counts as a "between
rounds" tick. The name reads as if it should only fire from
iteration 2 onward. Agent-Review surfaced the question on PR #24
(agent-ai-integration `loop.py:66-72`) — the implementation does
fire on iteration 1 today; this amendment codifies that semantics
so future agents and middlewares do not have to re-derive it.

**Codified rule.** `BETWEEN_ROUNDS` fires at the START of every
loop iteration, **including iteration 1**. Treat it as a
"before-round" gate rather than a strictly "between-rounds" gate.
Session-level guards (`PauseGuard`, `LoopGuard`, anything else
needing to block before any LLM/tool work happens) MUST attach
here so that an active pause sentinel or a tripped non-progress
counter prevents the very first tool call, not only the second
onward.

**Why we kept the name `BETWEEN_ROUNDS` rather than rename to
`BEFORE_ROUND`.** Prior Art entry §1 above maps the five
lifecycle-point names verbatim to DPC `dpc_agent/hooks.py:LIFECYCLE_POINTS`
and (with `OnBefore*` / `OnAfter*` casing) to Gortex
`internal/hooks/dispatch.go:Dispatch`. Renaming would (1) break that
verbatim alignment with the borrow-roadmap §R-1 nomenclature for a
purely-cosmetic gain, (2) churn every Wave-2 middleware PR that
already cites `BETWEEN_ROUNDS` in attaches_to, and (3) violate
[minimalism-first](../project-overview.md#12-enforceable-principle--minimalism-first)
— the subtraction-check fails «open-source agent-stack precedent
for *not* having the alignment with DPC/Gortex naming?». A doc
amendment is the bounded fix.

**Forward-only.** Applies to M-1 onwards. The §1 ASCII-diagram
caption ("runs at the top of every loop iteration") already
matched the implementation; this amendment just promotes the
caption to a contract clause.

## Prior Art

Per [`pr-creation` skill PR Checklist rule #10](../skills/pr-creation/SKILL.md#pr-checklist)
+ DPC AP8 / Prior-Art rule. Each prior-art entry maps a design
choice in this ADR to an existing project / paper, so reviewers
can verify FA is not re-inventing.

- **5 lifecycle points (§1):** DPC `dpc_agent/hooks.py:LIFECYCLE_POINTS`
  (verbatim names); Gortex `internal/hooks/dispatch.go:Dispatch`
  (same five names, different naming convention — `OnBefore*` /
  `OnAfter*` instead of `BEFORE_*` / `AFTER_*`).
- **2-tier middleware kinds (§2):** DPC `dpc_agent/hooks.py:Guard`
  + `dpc_agent/hooks.py:Observer`. The error-swallow vs
  error-propagate split is DPC's exact contract.
- **Ordered chain + first-deny short-circuit (§3):** Aperant
  `apps/desktop/src/main/ai/orchestration/hook-chain.ts` (147
  LOC); first-deny semantics identical.
- **One mutation per dispatch (§3):** ADR-7 §8 already specifies
  this; this ADR-8 §3 inherits the rule without restatement.
- **Family-disjoint rule at `register()` (§4):** New — applies
  the ADR-2 §Amendment 2026-05-20 + ADR-7 §Amendment 2026-05-20
  policy at a single enforcement point.
- **Doc-first deferral pattern (this ADR's overall shape):**
  matches FA's
  [ADR-7](./ADR-7-inner-loop-tool-registry.md) approach for the
  same reason — write the contract once before the v0.1 hooks
  ossify into their inline shape.

## References

- [ADR-7](./ADR-7-inner-loop-tool-registry.md) §8 — current
  mini-pipeline (will be cross-ref'd to ADR-8 §5 after M-1).
- [ADR-7 §Amendment 2026-05-20](./ADR-7-inner-loop-tool-registry.md#amendment-2026-05-20--retry-budget-invariant-intra-role-t10-llm-using-hook-family-disjoint-rule)
  — retry-budget invariant; family-disjoint rule applied at
  the registry enforcement point.
- [`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
  §R-1 — HookRegistry primary source; §§R-2/R-3/R-4/R-5/R-22 —
  middlewares that consume this contract.
- [`knowledge/BACKLOG.md`](../BACKLOG.md) M-1 — inner-loop
  scaffolding PR that builds the runtime.
- [`knowledge/research/dpc-messenger-inspiration-2026-05.md`](../research/dpc-messenger-inspiration-2026-05.md)
  §0 R-1 — DPC `dpc_agent/hooks.py` (207 LOC) +
  `dpc_agent/guards.py` (222 LOC) reference.
- [`knowledge/research/gortex-aperant-inspiration-2026-05.md`](../research/gortex-aperant-inspiration-2026-05.md)
  Addendum I — Gortex `internal/hooks/dispatch.go` (38 LOC)
  convergence.
