# What to take from the research note — adoption plan for the first-agent harness

*Source: `PRODUCTION-NOTE-planning-big-tasks-for-ai-agents.md` (1,623 lines, ~60 cited
papers). I read it in full. Verification posture: I cross-checked every claim it makes
about **our** system against the code I've read this session (`plan_ids.py`,
`workflow_controller.py`, the injection machinery, the planning skills); I did **not**
re-verify the ~60 arXiv papers — I'm adopting the **mechanisms**, which converge across
independent sources, and treating the exact numbers as the note's (it grades them A/B/C
and maps each to a check-strength in its §10). Spot-check any specific paper on request.*

---

## 1. The headline

The research converges on one thesis that matches everything we've designed:

> **The harness, not the model, is the binding constraint** (F1: harness-only changes
> move hard benchmarks up to 15 points; StateM hit 95.3% on Terminal-Bench through
> harness engineering alone). And the field's unified response to long-horizon failure
> is to **manufacture denser step-level signal** — which is exactly what per-slice
> `verify` blocks are.

Our topology sits at the field's center of gravity. §5 of the note checks our six
locked decisions and rates **all six "supported."** So this is not a redirect — it's a
confirmation plus a ranked list of upgrades. The question is only **which upgrades, in
what order, and which to refuse.**

---

## 2. The single highest-value upgrade: make contracts executable (item #1)

If you adopt nothing else, adopt this. The note calls it "the single highest-value
upgrade in the backlog," and the evidence is the strongest in the document:

- **SWE-Gate (2609.04167):** of 644 patches that *passed the functional tests*, **221
  (34.3%) violated the acceptance constraints** derived from real PR review comments.
  Tests passing ≠ accepted.
- **The principle (SDD, 2609.00252, verbatim):** *"a constraint that no tool can enforce
  is a wish rather than a constraint."*
- **Our own example proves it:** `CT3` ("IDENTICAL 401 for unknown email vs wrong
  password") is, today, a **wish** — nothing in the plan guarantees a test exists for it.

**The mechanism:** the **planner writes each slice's test file**; the `verify` block
points at it; the harness **proves non-vacuity** (fail-before/pass-after against the
pre-slice baseline — Agentless's filter). Contracts get **classes** (`FUNCTIONAL` /
`CONSTRAINT` / `PRESERVATION`) so the gate can fail on the right thing. Contract and
proof become one artifact, and "the coder never writes its own acceptance" holds in its
strongest form (VeriMAP, AgentCoder).

**Why it's the top pick for us:** it directly upgrades the verify-gate we already
designed (S16). The `verify` block stops being "a command the planner typed" and becomes
"a planner-authored test, proven to actually test something." It also raises the planner
to the "premium role" the evidence says it should be (F4: plan quality dominates; spend
the best model there).

**The honest cost the note understates:** the planner now writes *test files*, not just
prose. That's a real skill upgrade — but your `feature-planning` skill already mandates
producer kill-checks, so the discipline exists; this makes it load-bearing and
harness-enforced.

---

## 3. The adoption set, ranked for *our* system

The note has 18 items in 3 tiers. Filtered through our codebase and our prior decisions,
here is the order I'd actually build, with what each maps to:

| # | Item | Why it matters for us | Maps to (our code / prior work) | When | Cost |
|---|---|---|---|---|---|
| **1** | **Executable contracts** (planner writes the test; harness proves non-vacuity; contract classes) | turns every `CT#` from wish→check; the 34.3% false-accept killer | upgrades the verify-gate (S16); `plan_ids` grows `TESTS:` | **foundation** | med |
| **5** | **Plan pre-check** (pure-code lint before any coder token) | catches plan errors for $0; enforces #1's "every CT# has a test" | extends `plan_ids.py` (exists) | **foundation** | low ("an afternoon") |
| **4** | **EVIDENCE ledger** (3rd durable artifact, provenance grammar) | makes the loop *compound* — HoH: −6.28 pts without it; substrate for #9/#13/#15 | new file + parser; planner reads, eval appends | **foundation** | low |
| **7** | **Pin invariants + re-inject every call** | compaction silently evicts standing policies; "cheapest insurance in the list" | **builds on your existing injection machinery** (InjectionSpec / `fa inject`) | **foundation** | trivial |
| **3** | **`STEPS: prescriptive \| outcome` tag** (+ `(auto)` for mechanical steps) | **closes our open dial** with evidence: detail level = predictability | one grammar field + plan-authoring guidance | **foundation** | low |
| **6** | **Retry hygiene: distilled failure packets** (never raw transcripts) | anti-self-conditioning (F3, the dominant execution poison); brief layout is measured | the gate's failure object + retry/brief templates | foundation | low-med |
| **2** | **Stall counter** (≤2, then reflect→ledger→scoped replan, contexts cleared) | automates our manual "flaky→halt"; PlanBench-XL: failure *handling* is the cliff (51.9%→11.4%) | pure controller state + one REFLECT prompt | next | low |
| **8** | **Three-level eval** (L1 mechanical / L2 contract / L3 intent), different family, blind | the objective-level check is **+15.6 pts** (MAST); self-preference bias is real | restructures the eval role we already discussed | next | med |
| **12** | **pass^k in the tracker** (stochastic gates only; k=1 for deterministic tests) | "VERIFIED" stops meaning one green run; consistency is the metric | trivial tracker arithmetic | next | low |
| **17** | **Telemetry schema** (log runs in a stable schema *now*; attribution loop later) | "cheap now, expensive later"; makes every other item measurable | a run logger | next (schema only) | low now |
| **9** | **STALE-SPEC propagation + `supersedes:` fields** | makes rolling-wave *cheaper* (TDP: −82% tokens vs full replan); the `password_hash` case | harness flag + a planner scoped-refinement pass; reads the ledger | next | med |
| **13** | **ASK# clarification channel** (plan time; auto-seeded from ledger `GUESS`es) | agents rarely ask (11.7% of failures); your "halt for human" instinct, formalized | planner emits ASK#; chat resolves with the human | later | med |
| **14** | **Graduated autonomy** (`RISK:` tag = human-checkpoint density) | ambiguity→human, execution-failure→auto-repair; keeps an autonomous loop shippable | one tag + gate routing | later | low |

**Defer (optimizations / compounding — not foundational):**

| # | Item | Why defer |
|---|---|---|
| **11** | Slice DAG + parallel git worktrees | most seductive, most premature; you already deferred parallel-search; sequential first; the worktree+runtime-isolation plumbing is real work |
| **10** | Escalation ladder / N-version repair | needs the parallel runner (shared with #11); do after the stall counter proves the simple loop |
| **15** | Post-feature distillation ritual | pays off over *many* features, not one; adopt after several increments exist |
| **16** | Hash-anchored tamper-evident run record | nice audit property; not load-bearing yet |
| **18** | Model tiering (planner-tagged) | conditional on #17 telemetry existing; premature tiering corrupts the data it saves on |

---

## 4. What each role gains (your "role-based loop" view)

- **Planner** (the premium role): writes the **test files** (#1), declares
  **`STEPS:` mode** (#3), emits **`ASK#`** (#13), **reads the ledger** at increment start
  (#4), runs **scoped spec-refinement** on `STALE-SPEC` slices (#9).
- **Coder**: gets a **scoped brief** in the measured layout (contracts top, intent
  restated at the bottom — #6), and on retry a **distilled failure packet**, never its
  own failed transcript (#6).
- **Eval**: becomes **three-level, different model family, blind to authorship**,
  emitting **machine-readable verdicts** (#8); **appends to the ledger** per slice (#4).
- **Controller (code)**: runs the **plan pre-check** before any token (#5), **runs verify
  + proves non-vacuity** (#1), keeps the **stall counter** (#2), tracks **pass^k** (#12),
  **pins + re-injects invariants** every call (#7), **logs telemetry** (#17).
- **Chat**: resolves **blocking `ASK#`** with the human before the run (#13), and later
  runs the **distillation ritual** (#15).

---

## 5. The meta-discipline — the most important caveat in the note

The note warns against itself, and you should hold it to that:

> **"More structure is not more success."** MAST found **3 of 14 failure modes are
> *created by* multi-agent structure**; over-decomposition misaligns guidance from
> execution need. The meta-recommendation: **ablate your own harness** — on/off deltas
> per component — *before granting any component permanence.*

This is exactly your "simple system" + scope-discipline instinct, with evidence behind
it. So: **do not build all 18.** Build the foundation (the six Tier-1 items), ship a real
increment, measure, and let each later item *earn its place* in telemetry. The note's own
logic forbids adopting its whole backlog on faith.

Two more caveats worth carrying: (1) **verifiers get gamed and must co-evolve** (a frozen
test suite is a target, not a guarantee) — the eval rubric and constraint tests are
*living* artifacts; (2) much of the 2026 evidence is **preprints** — the mechanisms
transfer, the exact gains may not, so trust the direction, not the decimals.

---

## 6. The first build (a concrete foundation increment)

If you want one coherent first PR/increment that captures most of the leverage:

1. **Grammar:** add `TESTS:` (planner-authored test path), contract **classes**, and
   `STEPS: prescriptive|outcome` to the increment-plan grammar; rename `S#`→`SLICE#`,
   steps→`STEP#` (we already agreed). Update both skills + the `plan_ids` extractor.
2. **`plan_ids` + pre-check (#5):** the new accessors (`commands_for`, `section`,
   `TESTS:`) + the symbolic assertions (every `CT#` has a test; every prescriptive
   `STEP#` has an exit criterion; `verify` dry-runs; slice count 4–7).
3. **Non-vacuity gate (#1):** the verify runner does fail-before/pass-after against the
   pre-slice baseline.
4. **EVIDENCE ledger (#4):** the file + the provenance grammar (`FACT/DERIVED/LOOKUP/
   GUESS/FAILED/GAP/PRESERVE`); planner reads, eval appends; `GUESS`→`ASK#` candidate.
5. **Pinned invariants (#7):** assemble the standing-decisions preamble from the roadmap +
   ledger; re-inject every role call (reuse your injection machinery).
6. **Failure packets + brief layout (#6):** the structured failure object; the U-shaped
   brief.

That is the trustworthy-and-compounding core. The stall counter (#2), three-level eval
(#8), pass^k (#12), and the telemetry schema (#17) are the natural second increment.

---

## 7. One-paragraph version

The research confirms our topology (all six locked decisions "supported") and says the
harness is the lever, not the model. The one upgrade that dwarfs the rest is **making
contracts executable** — the planner writes each slice's test, the harness proves it's
non-vacuous, because 34.3% of test-passing patches still violate review constraints and
"a constraint no tool can enforce is a wish." Around it, the foundation is: a pure-code
**plan pre-check**, an **EVIDENCE ledger** that makes the loop compound, **pinned
invariants** re-injected every call, the **`STEPS:` dial** that closes our open question,
and **distilled failure packets** instead of raw retry transcripts. Then failure-handling
as a first-class state (stall counter, three-level eval, pass^k) and a telemetry schema.
Defer the seductive optimizations — parallel worktrees, N-version, model tiering,
distillation — and obey the note's own warning: **ablate each component before granting
it permanence.** Build the foundation, ship one real increment, measure, earn the rest.
