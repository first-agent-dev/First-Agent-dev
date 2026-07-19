---
name: plan-authoring
description: |
  Implementation Plan Authoring skill for agent harnesses. Produces
  ordered, grounded, falsifiable implementation plans that an executing
  agent can follow without guessing, a reviewer can verify against
  reality (file:line, not vibes), and that terminate in a negative-proof
  Definition of Done. Converts intent into code, contracts, artifacts,
  and verification.
status: active
last-reviewed: 2026-07-19
triggers:
  - "authoring or updating an implementation plan"
  - "converting research notes or gap analysis into an executable plan"
  - "writing a plan that must survive contact with an executor"
  - "planning work across multiple phases, steps, or PRs"
  - "deriving a READY-gated plan from intent, research, and codebase state"
globs:
  - "knowledge/research/PLAN-*.md"
  - "knowledge/research/*plan*.md"
alwaysApply: false
---

# SKILL — Implementation Plan Authoring (Agent Harness, AI Age)

You write implementation plans, not essays. A plan is a direct instruction
set an executing agent can follow without guessing, that a reviewer can
verify against reality (file:line, not vibes), and that terminates in a
falsifiable Definition of Done. It converts intent into code, contracts,
artifacts, and verification — and it survives contact with an executor
that will skip anything not nailed down.

INPUTS you receive: chat/context, research notes (may be partial, wrong,
or aspirational), and read access to the codebase.

OUTPUT you produce: one ordered plan in the shape defined in §9, gated by
a status of DRAFT | READY | BLOCKED.

═══════════════════════════════════════════════════════════════════════
CENTRAL LAWS (non-negotiable)
═══════════════════════════════════════════════════════════════════════

Central law (triad): A plan is done only when every intent item maps to
(1) a concrete code change site, (2) a contract, (3) an artifact/state
transition, and (4) a verification step that FAILS if the change is
absent. Any item missing one leg is incomplete — a wish, cargo-cult code,
or a test in search of a feature.

Central law (grounding before generation): No file, function, type, or
event name may appear in the plan unless it was VERIFIED by reading/
grepping the repo, or explicitly marked NEW. An unverified reference is
a hallucination risk the executor will inherit. Preflight (§2) is
mandatory and its results are recorded in the plan, not silently assumed.

Central law (notes are inputs, not authority): Research notes and chat
context are fallible. Every substantive suggestion in them gets a verdict
— Accept / Reject / Rewrite / Defer — checked against the actual codebase,
existing invariants, and whether it is kill-checkable (§8). Copying a note
into a plan without this check is planning theater.

Central law (no vacuous Done): "Done" that passes because the feature was
never wired is VACUOUS. Every product claim needs a kill-check: removing
the PRODUCER call site must make the verification fail. A plan whose DoD
would still pass with the feature deleted is not a plan, it's a decoration.

Central law (two-sided contract): For every observable signal the plan
touches or introduces (event, API, CLI flag, tool, hook, log line, FS
write) BOTH producer (who creates the signal) and consumer (who acts on
it) must be specified and verified. One-sided plans describe a class
nobody instantiates, or a call to a function that doesn't exist.

Central law (path sensitivity): One feature may land on multiple paths —
flags, happy/error, CLI vs library, provider families, multiple call
sites. Enumerate every path; plan and verify each. Covering one path does
not ship the others.

Central law (minimal mechanism): Prefer the smallest change that satisfies
the intent over speculative architecture. Non-goals exist to stop scope
creep, not to be apologized for. If a "nice to have" isn't in the intent,
it isn't in the plan.

Central law (assume theater): Treat every step as skippable and every
claim as possibly gamed until proven otherwise. Force compliance with
existence pre-checks, explicit file:symbol sites, ranked oracles, matrix
coverage, and a self-check gate (§11) before a plan may be marked READY.

═══════════════════════════════════════════════════════════════════════
0. QUICK DECISION TREE (read this first)
═══════════════════════════════════════════════════════════════════════

Have you read/grepped the actual code yet?

  NO  → STOP. Run Preflight (§2) before writing a single step.

What's the blast radius?

  Single function/file, no new contract         → Depth P0

  One contained new capability                   → Depth P1

  Cross-module/service, migration/rollout         → Depth P2

  Architectural/ADR-level, reverses a prior decision → Depth P3

  (Declare depth AFTER preflight, not before. Re-declare if scope grows.)

Is the approach itself unknown?                  → Spike plan: time-boxed,
                                                     decision criteria stated,
                                                     no "shipped" claim.

Is this a pure refactor, no behavior change?      → Structural plan; DoD =
                                                     "observable behavior
                                                     invariant" proof.

What kind of verification does this need?

  Wiring / control-flow / security / efficiency   → Pyramid A (CI, C0–C3)

  Subjective quality / model behavior              → Pyramid B (evals; keep
                                                     separate, never gates A)

  Session/product/loop claim                       → C1 (or C2 if CLI-only)

  Pure helper                                       → C0/C0p — necessary,
                                                     never sufficient alone

  Security boundary                                 → ≥1 adversarial case (C3)

Does this introduce/change an EventType, API, CLI flag, hook, or any
observable signal?                                 → Contract Card required
                                                     (§6), both sides named.

Could more than one call site trigger this?         → Path/flag matrix
                                                     required (§7).

═══════════════════════════════════════════════════════════════════════
1. TRACEABILITY & ID CONVENTIONS
═══════════════════════════════════════════════════════════════════════

Every plan uses these ID prefixes consistently so sections can cross-
reference each other without ambiguity:

  G#    Goal / intent item           (from Executive Intent, §3)

  CT#   Contract                     (function, signal, data, or invariant)

  S#    Step / task card             (§8)

  Q#    Open question                (§10)

  RN#   Research-note disposition row (§11a)

  RK#   Risk                         (§10... risks table)

Rule (plan self-lint): every ID referenced anywhere in the plan MUST
resolve to a row that actually exists. Dangling references (a step citing
CT7 that was never defined) are a planning defect — fix before READY.

═══════════════════════════════════════════════════════════════════════
2. PREFLIGHT (mandatory, recorded, run before drafting steps)
═══════════════════════════════════════════════════════════════════════

Before writing intent or steps, do — and log the results of — all of:

  1. Locate composition roots relevant to this change (e.g. main loop,
     CLI entrypoints, API routers, cron/worker entry points).

  2. Grep for existing symbols/types/events/flags related to the intent —

     do not assume something is new without checking.

  3. Read 1–2 "gold" existing tests/patterns that resemble what you're
     about to ask for (naming conventions, fixture style, wiring style).

  4. Check for conflicting ADRs, invariants, or naming collisions.

  5. Estimate current liveness level per relevant signal (§4 scale).

  6. Note anything that could not be resolved by reading — these become
     Q# (open questions), not silent assumptions.

Record as:

  PREFLIGHT LOG:

    roots checked: ...

    greps run → findings: <pattern> → <hit summary, or "no hits — NEW">

    gold patterns mirrored: <file>

    conflicts/invariants found: ...

    as-is liveness: <signal>: L?

    unresolved: → promoted to Q#

Staleness rule: if execution is happening in a session materially later/
different from preflight (long-running agent harness, other PRs landed),
re-run the relevant greps before trusting the plan's file:line references.

═══════════════════════════════════════════════════════════════════════
3. EXECUTIVE INTENT (8–15 lines)
═══════════════════════════════════════════════════════════════════════

  IDEA:          <plain language, what is being asked for>

  PROJECT MEANING: In <subsystem>, this becomes <integration point> —

                   why does this belong here, not elsewhere?

  GOAL (G1..Gn): <measurable outcome per intent item, numbered>

  NON-GOALS:     <explicit out-of-scope list — scope-creep firewall>

  INTENT:        Code should ensure <invariant/behavior> whenever

                 <condition>. (the "why" behind the mechanism)

  MECHANISM SKETCH: <entry point> → <decision> → <signal/state produced>

                 → <consumed/displayed>. One short paragraph.

  PROOF SKETCH:  <root> observes <oracle>; kill-check removes <producer
                 site>.

  SIZE:          S | M | L (rough effort signal for triage; optional)

═══════════════════════════════════════════════════════════════════════
4. CURRENT STATE → TARGET STATE (liveness-scored)
═══════════════════════════════════════════════════════════════════════

Liveness scale (used for BOTH current-state assessment and target DoD bar):

  L0  Not present

  L1  Import-reachable only                          NOT shippable

  L2  Call-reachable from a real root, unverified     NOT shippable

  L3  Behavior + kill-check on PRODUCER holds         Shippable

AS-IS (verified via preflight, not assumed):

  Dimension                  | Finding

  Entry points                | ...

  Existing types/schemas      | ...

  Existing producers/consumers| file:line, or "absent"

  State stores                | DB / JSONL / memory / FS

  Flags/defaults               | ...

  Tests today                  | which class exists; gaps

  Liveness per signal          | L0–L3

TO-BE (machine-checkable facts, not adjectives):

  - New/changed types, fields, EventTypes, APIs, CLI flags

  - State transitions (STATE: <name> — AS-IS: ... → TO-BE: ...)

  - Operator-visible behavior change

  - Default flag values; error/deny behavior

  - Performance/efficiency constraints (e.g. early-stop call_count==0)

  - Target liveness per signal: must be L3 for anything called "shipped"

═══════════════════════════════════════════════════════════════════════
5. NON-GOALS & MINIMAL-MECHANISM CHECK
═══════════════════════════════════════════════════════════════════════

  - Explicit list of what this plan does NOT attempt.

  - For each design choice: could a smaller change satisfy the same
    intent? If yes and rejected, say why (P2+/P3 requires this; P0/P1
    may state "trivially minimal").

═══════════════════════════════════════════════════════════════════════
6. CONTRACTS (hard center of the plan) — every applicable subtype, IDed CT#
═══════════════════════════════════════════════════════════════════════

6.1 Function/API contract

  CT#: <module.symbol>

  PRE / POST / IN (types) / OUT (types) / ERRORS / PURE?(y/n)

  SIDE EFFECTS: log.append / emit / FS / network / none

6.2 Signal contract (event, API, CLI flag, hook) — TWO-SIDED, mandatory

  CT#: <SignalName>

  PRODUCER: site (file:symbol, or "TO ADD"); trigger conditions + flags;
            payload schema {field: type}; paths [P1, P2, ...] (see §7)

  CONSUMER: site (handler/renderer); behavior on receipt

  DUAL-WRITE: if the system has two channels (e.g. durable log +
            live event bus), state whether both must write on this path,
            and confirm they live in the same if/elif/except block

  KILL-CHECK: remove PRODUCER call → named verification fails
              remove CONSUMER handler → named consumer verification fails
              (producer kill-check is PRIMARY; consumer alone is
              incomplete — a dead handler proves nothing)

  SHIP RULE: producer proof BEFORE "shipped"; consumer-only ≠ shipped

6.3 Data/schema contract

  CT#: schema name, shape, additive vs breaking, Optional-narrowing rules
       mirrored in fixtures/tests

6.4 Invariant (plan-local, distinct from skill invariants below)

  CT#: <sentence> — enforced at <module> — verified by <test class>

6.5 Security contract (if applicable)

  CT#: boundary (sandbox / secrets / permissions / path containment /
       egress) — REQUIRES ≥1 adversarial example in DoD (C3)

Rule: a signal contract with a PRODUCER and no CONSUMER (or vice versa)
is incomplete. Either complete it or explicitly defer the missing side
as a stated non-goal with a follow-up reference — never leave it silent.

═══════════════════════════════════════════════════════════════════════
7. PATH & FLAG MATRIX
═══════════════════════════════════════════════════════════════════════

7.1 Path inventory (built via preflight, not guessed):

  P#  | Trigger condition | File:line/symbol | Flag state | Covering S#

  Coverage gate: every path has ≥1 covering step and ≥1 verification.
  Uncovered paths are explicit non-goals, never silent gaps.

7.2 Flag/provider matrix:

  ID  | Flags/env               | Proves

  A   | primary config           | main path works

  B   | full cascade              | interaction/compounding paths

  C   | defaults (out of the box) | operator-facing default path

  P-x | provider/backend family   | backend-specific behavior

  Matrix coverage gate: naming the matrix is NOT sufficient. Each row
  needs a covering step and a named verification, or an explicit
  "N/A — because <reason>".

═══════════════════════════════════════════════════════════════════════
8. STEP-BY-STEP IMPLEMENTATION (task cards)
═══════════════════════════════════════════════════════════════════════

Default ordering (adapt, never skip the rationale for reordering):

  discover/confirm as-is → types/schemas → producer call sites →
  consumer handlers → root wiring (L2→L3) → dual-write completeness →
  producer verification + kill-check → paired consumer verification →
  path/matrix completion → adversarial cases if security → contract/CI
  gate → docs/ADR if invariant-level.

Template — use for every step, no exceptions:

### Step S#: <title>

Traces-to: G# (intent), CT# (contract(s))

Depends-on: S# | none          Parallelizable-with: S# | none

Target liveness: L?→L?

Edit:

  - path: <file>      symbol: <fn/class>      change: <precise, one line>

Do:

  1. <concrete edit/command>

  2. ...

Do-not:

  - <specific scope-creep or failure mode to avoid here>

Example (real types/names, illustrative sketch, not full impl):

  ...

Exit criteria (must be independently checkable):

  - [ ] existence check: grep confirms the new site exists in prod code

  - [ ] type/compile check passes

  - [ ] behavioral assertion: <what observable thing is now true>

Kill-check (if this step touches a CT# signal contract):

  - removing <site> makes <verification name, §9> fail

(Full anti-theater checklist lives once, at plan level — §11.2. Do not
repeat it per step; steps only need existence + kill-check pointers.)

Writing rules for steps:

  - file:symbol, not "the loop" or "somewhere in the handler."

  - Real types (tool_calls=(), HookRegistry(), not mocks) when the step
    concerns wiring, not test authoring.

  - No step may say only "add tests" — name test class, root, oracle,
    and kill-check target (link to §9).

  - If a step touches a signal contract, restate producer/consumer/
    dual-write status inline, don't make the executor cross-reference.

═══════════════════════════════════════════════════════════════════════
9. VERIFICATION PLAN (bridges to the Tests-Writing skill)
═══════════════════════════════════════════════════════════════════════

For each CT# signal/contract, specify — this is a spec for tests, not
the tests themselves:

  CT#: <name>

  Test class: C0 / C0p / C1 / C2 / C3 (or named manual/monitoring proxy
              if no automated oracle exists yet)

  Oracle (ranked, prefer top): event kind+fields > outcome/exit code >
              tool trajectory > provider call_count/tokens > FS effect >
              deny-reason code > free text (never sole oracle)

  Kill-check target: exact PRODUCER call site whose removal must fail it

  Two-sided: producer test AND paired consumer test both named

  Path coverage: which P# (§7) this verification covers

LIVE-PATH PROOF block (required once per product claim):

  root: <composition root>            matrix: A|B|C|P-<family>

  test: tests/<file>.py::test_<name>  oracle: <ranked oracle used>

  kill-check: removing <file:line> fails the named test

  producer: <file:line/symbol>        consumer: <file:line/symbol>

  paths-covered: N/M

  contract-check: PASS required in CI if signals were touched

  efficiency: call_count=N | early-stop (if relevant)

  pyramid: A (default) — if Pyramid B (quality/eval) applies, section it
  separately; it never gates Pyramid A merges.

═══════════════════════════════════════════════════════════════════════
10. RISKS, ROLLBACK, OPEN QUESTIONS
═══════════════════════════════════════════════════════════════════════

RISKS

  RK#  | Risk | Mitigation | How detected (test/metric)

ROLLBACK (required P2+)

  Feature flag name + default state | revert path | data migration
  reversibility (dual-read/backfill) | kill-switch if one exists

OPEN QUESTIONS

  BLOCKING (Q#) — executor must stop and get an answer before the
    dependent step; list exactly which S# is gated.

  NON-BLOCKING (Q#) — a default decision is recorded here; executor
    proceeds with the default and flags it in the handoff. Every
    non-blocking question MUST carry a default — "unresolved, proceed
    anyway with no default" is not permitted.

═══════════════════════════════════════════════════════════════════════
11. GATES
═══════════════════════════════════════════════════════════════════════

11a. RESEARCH-NOTE DISPOSITION (mandatory — every substantive item)

  RN# | Note item | Verdict (Accept/Reject/Rewrite/Defer) | Why
      (codebase fit? kill-checkable? conflicts with invariant?) | Anchor (S#/CT#)

  Reject: theater, unowned scope, unverifiable claims, or duplicates of
  existing L3 behavior. Rewrite: good idea, wrong mechanism/location.

11.2 ANTI-THEATER CHECKLIST (plan-level, all must hold for READY)

  [ ] Every referenced symbol verified via preflight or marked NEW

  [ ] Every G# maps to ≥1 CT# and ≥1 S# and ≥1 verification (no orphans)

  [ ] Every signal CT# has BOTH producer and consumer, or explicit defer

  [ ] Every kill-check targets the PRODUCER, never the consumer alone

  [ ] Path inventory (§7.1) has no uncovered path without explicit non-goal

  [ ] Matrix (§7.2) has ≥1 covering step per row or explicit "N/A — why"

  [ ] Dual-write channels (if present) verified consistent per path

  [ ] Fixtures/types in verification plan are honest (real types, not
      loosened mocks, at wiring boundaries)

  [ ] No vague verbs ("handle", "support", "integrate", "optimize")
      without a concrete mechanism attached

  [ ] Assumptions are labeled, not asserted as fact

  [ ] Security contracts have ≥1 adversarial case

  [ ] All ID references (§1) resolve — no dangling S#/CT#/G#/Q#/RN#/RK#

  This is a CONJUNCTION: all boxes must hold simultaneously. A plan that
  satisfies 90% is not "mostly ready" — it is NOT READY.

11.3 DEFINITION OF DONE (plan-level, falsifiable)

  STATE:      before/after system state + how to observe the after-state

  ARTIFACTS:  created / modified / deleted files, config, migrations, docs

  CONTRACTS:  every CT# with status PLANNED / IMPLEMENTED / VERIFIED

  Plan is DONE only when: all G# reach target liveness L3, all artifacts
  exist and are referenced, LIVE-PATH PROOF blocks are green under the
  project's CI authority, matrix/path coverage holds (or is waived with
  stated reason), non-goals were respected, and RN# items are all
  dispositioned.

11.4 READY GATE (self-check before marking plan status = READY)

  [ ] Preflight log present and non-trivial (not "skipped")

  [ ] Depth (P0–P3) declared and matches actual scope

  [ ] Executive intent, non-goals, current/target state all concrete

  [ ] All applicable contract subtypes (§6) present or explicitly N/A

  [ ] Path + matrix coverage gates satisfied (§7)

  [ ] Every step is file:symbol specific with exit criteria (§8)

  [ ] Verification plan + LIVE-PATH PROOF present for every product claim

  [ ] Anti-theater checklist (§11.2) fully holds

  [ ] Research notes fully dispositioned (§11a)

  [ ] BLOCKING open-question set is EMPTY (non-blocking ones have defaults)

  [ ] All IDs resolve (§1 lint)

  If any box fails → status = DRAFT (missing pieces) or BLOCKED
  (blocking question outstanding) with the specific reason named.

═══════════════════════════════════════════════════════════════════════
12. OUTPUT SKELETON (always this shape)
═══════════════════════════════════════════════════════════════════════

# PLAN: <short name>                        Plan-ID: PLAN-<slug>
Status: DRAFT | READY | BLOCKED             Depth: P0|P1|P2|P3
Revision: v<N>   Changed-since-last: <summary, or "initial">
Upstream context: <chat/issue/research refs>

## Preflight log                    (§2)

## 0. Executive intent               (§3)

## 1. Non-goals & minimal-mechanism  (§5)

## 2. Current state → Target state   (§4)

## 3. Contracts                      (§6)

## 4. Path & flag matrix             (§7)

## 5. Step-by-step implementation    (§8)

## 6. Verification plan              (§9)

## 7. Risks, rollback, open questions(§10)

## 8. Research-note disposition      (§11a)

## 9. Definition of Done             (§11.3)

## 10. Anti-theater + READY gate     (§11.2, §11.4)

## 11. Artifacts inventory

      Artifact | Path | Action (add/edit/delete) | Owner S#

═══════════════════════════════════════════════════════════════════════
13. ESCALATION TABLE
═══════════════════════════════════════════════════════════════════════

Situation                                          Action

Symbol referenced but not verified                  STOP; grep/read it;
                                                     mark NEW if absent

"Handle X properly" with no mechanism                Rewrite concretely or
                                                     go research it first

Signal has producer, no consumer (or reverse)        Complete it, or
                                                     defer as stated non-goal

No falsifiable DoD for a step                        Add State/Artifact/
                                                     Contract check

"Add tests" with no oracle/class named                Map to §9 explicitly

>1 call site exists, only one planned                 Run §7.1, add steps

Matrix named but rows uncovered                       Add step/test per row

Two write-channels, only one path covered             Add dual-write check

Scope grew past declared depth mid-write              STOP; re-declare
                                                     depth; add missing
                                                     sections for new depth

No rollback/non-goals on P2+ plan                     Add before READY

Notes conflict with code/ADR                          Code+ADR win; RN#
                                                     verdict = Reject/Rewrite

Security claim, no adversarial case                   Add C3 case

Executor would need a product/policy decision          → BLOCKING Q#, never
                                                     silently decided

Dangling ID reference found                            Fix before READY

═══════════════════════════════════════════════════════════════════════
14. RANKED ORACLES (reference table)
═══════════════════════════════════════════════════════════════════════

Rank  Oracle                    Notes

1     Event kind + fields       assert len([e for e in cap if e.type=="X"])>=1

2     SessionOutcome/exit code  assert outcome.stop_reason == "..."

3     Tool trajectory           assert [names] == [expected order]

4     Provider call_count/tok   assert mock.request.call_count == 0

5     FS effects                assert path.exists()

6     Deny-reason dataclass     assert result.error.code == "..."

7     Free text                 secondary only, never sole oracle

═══════════════════════════════════════════════════════════════════════
15. WORKED EXAMPLE (compact, Depth P1)
═══════════════════════════════════════════════════════════════════════

# PLAN: Operator warning at 80% context budget    Plan-ID: PLAN-ctx-warn
Status: READY   Depth: P1   Revision: v1

PREFLIGHT LOG:
  roots: drive_session (fa.inner_loop.coder_loop)
  greps: 'type="context_warn"' → no hits (NEW); ConsoleRenderer._handle_* →
         5 existing handlers, none for context_warn
  gold pattern mirrored: tests/test_pr1_wiring.py (budget C1 pattern)
  conflicts: none found
  as-is liveness: context_warn signal = L0 (not present)

## 0. Executive intent
  GOAL (G1): Operator sees a console warning before hitting hard-stop.
  NON-GOAL: No model-facing message rewriting; no new severity levels.
  INTENT: Never cross the warn threshold silently on the primary session path.
  MECHANISM: drive_session budget probe → output.emit(context_warn) +
             log.append → ConsoleRenderer._handle_context_warn.
  PROOF: C1 test on drive_session; kill-check removes the emit call in
         coder_loop's budget-warn path.

## 2. Current → Target
  AS-IS: budget probe exists (coder_loop.py:budget_check), computes pct,
         does nothing at warn threshold. Liveness L1 (probe exists,
         unreachable signal).
  TO-BE: probe emits context_warn (data={"pct": float}) via both
         output.emit and log.append at warn threshold, on all 3 paths
         (non-compaction, post-compaction, circuit-breaker). Liveness L3.

## 3. Contracts
  CT1 (signal): context_warn
    PRODUCER: coder_loop.py:budget_check — 3 paths (P1 non-compaction
      warn, P2 post-compaction still over, P3 circuit breaker) — payload
      {pct: float}
    CONSUMER: ConsoleRenderer._handle_context_warn — TO ADD, renders
      "{pct}% of context budget used" at stderr, standard detail level
    DUAL-WRITE: required — log.append(Event("context_warn",...)) AND
      output.emit(OutputEvent(type="context_warn",...)) in same branch
    KILL-CHECK: remove output.emit call at P1 → test_context_warn_p1 fails
    SHIP RULE: producer test must pass before consumer-only claim counts

## 4. Path & flag matrix
  P1: warn, non-compaction — coder_loop.py:budget_check L515 — flags: any — S2
  P2: post-compaction still over — coder_loop.py L974 — flags: compaction=on — S3
  P3: circuit breaker — coder_loop.py L919 — flags: any — S4
  Matrix: C (defaults) only — this feature is not flag-gated — N/A for A/B/P

## 5. Steps
  S1 [coder_loop.py:budget_check] Add dual-write emit at P1.
     Traces-to: G1, CT1. Depends-on: none.
     Do: emit OutputEvent(type="context_warn", data={"pct": pct}) +
         log.append(...) inside the existing `if pct >= WARN_THRESHOLD`
         branch.
     Do-not: touch the hard-stop branch (separate signal, out of scope).
     Exit: grep confirms emit call exists at L515; C1 test exists.
     Kill-check: removing the emit call → test_context_warn_p1 fails.

  S2/S3/S4: same pattern for P2/P3 (circuit breaker, post-compaction).

  S5 [ConsoleRenderer] Add _handle_context_warn consumer.
     Depends-on: S1 (needs a real event to test against).
     Exit: C0 consumer test passes AND is paired with S1's C1 producer test.

## 6. Verification
  CT1: C1 producer test per path (3 tests), oracle = event kind+fields,
  kill-check = producer emit removal. Paired C0 consumer test for
  renderer output. LIVE-PATH PROOF: root=drive_session, matrix=C,
  paths-covered=3/3, contract-check=PASS.

## 7. Risks/rollback/questions
  RISK: threshold constant duplicated across 3 sites → mitigate by
  reading from ContextBudget, not hardcoding. Rollback: revert commit,
  no flag needed (additive, non-breaking).
  Q1 (non-blocking): should warn re-fire if pct oscillates around
  threshold? Default: no, fire once per session (simplest, matches intent).

## 8. Research-note disposition
  RN1: "add a config flag to disable warnings" → Rejected — no prior
  request for this, adds surface area beyond G1; deferred as non-goal.

## 9. DoD: STATE (L0→L3 per path) / ARTIFACTS (coder_loop.py, console.py,
   3 new test files) / CONTRACTS (CT1: VERIFIED once S1–S5 land + tests green)

## 10. Anti-theater + READY gate: all boxes in §11.2/§11.4 checked; no
   blocking questions; status = READY.

═══════════════════════════════════════════════════════════════════════
16. INVARIANTS
═══════════════════════════════════════════════════════════════════════

I-IP-1  Every product claim ends at liveness L3 with a PRODUCER kill-check.

I-IP-2  Every goal item (G#) maps to ≥1 contract (CT#), ≥1 step (S#), and
        ≥1 verification — no orphans in either direction.

I-IP-3  Every observable signal has a two-sided contract (producer +
        consumer) or an explicitly stated, non-silent deferral.

I-IP-4  Path inventory and flag/provider matrix coverage are ENFORCED
        (a covering step/test exists), not merely declared in prose.

I-IP-5  No symbol, file, or type appears in a plan without preflight
        verification or an explicit NEW marker.

I-IP-6  Research notes are dispositioned (Accept/Reject/Rewrite/Defer)
        against the codebase — never copied in as ground truth.

I-IP-7  Pyramid A (wiring/security/efficiency) and Pyramid B (quality/
        eval) verification are planned separately; B never gates A.

I-IP-8  Definitions of Done are negative-proof capable: they fail if the
        underlying change is reverted.

I-IP-9  Dual-write / dual-channel consistency is planned wherever the
        system has two output channels for the same fact.

I-IP-10 Plan depth (P0–P3) is declared after preflight and re-declared
        if actual scope exceeds it mid-write.

I-IP-11 Status is READY only after the full gate (§11.4) holds as a
        conjunction — partial compliance is DRAFT or BLOCKED, not "close."

I-IP-12 Every ID referenced in the plan resolves to a defined row;
        dangling references are a defect, not a style nit.

I-IP-13 Blocking questions halt dependent steps explicitly; non-blocking
        questions always carry a stated default — never silent omission.

I-IP-14 Prefer the minimal mechanism that realizes the stated intent;
        unrequested scope is cut or logged as a separate follow-up plan.

I-IP-15 Assumptions are labeled ASSUMPTION and never presented as verified
        fact anywhere in the document.

═══════════════════════════════════════════════════════════════════════
17. OPERATOR USAGE WRAPPER
═══════════════════════════════════════════════════════════════════════

INPUTS:

  chat context: """ ... """

  research notes: """ ... """

  repo root / access: ...

  constraints: <time, safety, flag defaults, etc.>

TASK:

  1. Run Preflight (§2) against the real repo — do not skip.

  2. Declare Depth (P0–P3) based on verified scope.

  3. Author the plan in the exact shape of §12.

  4. Stress-test every research-note item against the code (§11a).

  5. Run the READY gate (§11.4). Set Status accordingly.

  6. If BLOCKED, list the exact blocking question(s) and stop —

     do not produce a plan that silently guesses at a policy decision.

  7. If READY, the plan must be executable by another agent, in step

     order, without that agent re-deriving intent or re-reading notes.

═══════════════════════════════════════════════════════════════════════
18. EXECUTOR HANDOFF CONTRACT (attach when handing a READY plan off)
═══════════════════════════════════════════════════════════════════════

- Follow steps in S# order; honor Depends-on and Parallelizable-with.

- After each step, run its Exit criteria; never mark a step complete on
  a partial pass.

- If a PRODUCER site is missing, implement it — do not "pass" a kill-check
  by weakening the test or targeting the consumer instead.

- Do not expand scope past the Artifacts inventory without updating the
  plan (new artifact = plan revision, not silent addition).

- If a step surfaces a new BLOCKING question, stop and escalate; do not
  invent a policy answer.

- Final message on completion: the DoD checklist (§11.3) with PASS/FAIL
  evidence — actual commands run and their output, not narrative claims.

- Defer to the project's CI authority (e.g. `just check` or equivalent)
  as the actual merge gate; this plan's DoD is necessary, not a substitute.
