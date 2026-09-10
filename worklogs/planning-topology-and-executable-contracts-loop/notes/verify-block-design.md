# The verification block — design note

Companion to `verify-block-design.svg`. Grounded at tip `0e08ece` (2026-09-07); research
citations are the paper IDs in `PRODUCTION-NOTE-planning-big-tasks-for-ai-agents.md`.

**Answer to "does the research note have this?": yes, and it is unusually direct.**
F8 ("multi-level, baseline-aware, planner-authored, non-vacuous"), F11 ("contracts must be
executable"), F12 (pass^k, one green run is a sample), §4E (gates get gamed and must be
trustworthy), and §7 items 1 & 5 are precisely the spec below. This note adds nothing the
note lacks; it only translates it into the code that exists at the tip.

## The one fact everything hangs on

At the tip, the verify block is **parsed and never run**. `extract_plan_ids` has two
external callers — `workflow_controller.py:332` and `:461` — and both read only `.slices`.
`PlanIds.commands` has **zero readers**. `_extract_commands` (`plan_ids.py:123`) drops
comments/blanks, preserves the rest verbatim, and returns a **flat** tuple — no per-slice
attribution, no validation. `_git_output` (`:401`) swallows failures to `None`, i.e. it is
the opposite of fail-loud. So the grammar exists and the gate does not. I02 builds the gate.

## Core idea: a verify block is a claim; the harness converts it into evidence

Keep the block a plain shell-command list. Do not invent a DSL — that is the "simple." The
discipline goes in code, never in the prompt (F5, §7 item 5): LLMs are measurably bad at
checking their own plans, and symbolic checks are free. The schema already carries
everything the discipline needs: `TESTS: path (NEW)` and per-slice `commands_for`.

### The ritual (four phases, one decision)

1. **Pre-check** (pure code, zero coder tokens): paths exist or are `NEW`; every `CT#` has a
   test in `TESTS:`; prescriptive `STEP#` has an exit criterion; `DEPS:` acyclic; an orphan
   ```verify fence outside any `## SLICE` → WARN (the grammar-collision trap, `test:225`).
2. **Baseline** — run the slice's commands once on the untouched tree; record `{cmd → RED|GREEN|ERROR}`.
3. **Fail-before** — every `NEW` test must be RED at baseline; a test that passes before the
   work proves nothing and is discarded (Agentless 2407.01489).
4. **Pass-after** — re-run; compare **per command** against the baseline.

### The truth table (no judgment calls)

| kind | baseline | after | verdict |
|---|---|---|---|
| NEW test | RED | GREEN | **PROVEN** (the only PROVEN state) |
| NEW test | GREEN | GREEN | **REJECT — vacuous** |
| existing | GREEN | GREEN | pass (PRESERVATION held) |
| existing | GREEN | RED | **REGRESSION → block** |
| existing | RED | RED | advisory (pre-existing; 10 of 11 repos — Phoenix 2606.20243) |
| existing | RED | GREEN | note → ledger (you fixed something unasked) |
| any | any | ERROR | **never PASS** |

## Why it is the right design

- **Elegant:** the author writes only commands + `NEW`; the harness derives expectation
  from (is it NEW?) × (baseline). Nothing for the author to get wrong.
- **Robust:** baseline-aware attribution kills both ghost-chasing and red-blindness;
  three-state outcome (PASS/FAIL/ERROR) means "couldn't run" can never masquerade as
  "passed"; regression is enforced by construction, covering the PRESERVATION class that
  SWE-Gate (2609.04167) shows functional tests miss (34.3% false-accept).
- **Simple:** four small additions to code that already exists — a runner over
  `commands_for`, a baseline snapshot, the seven-row compare, the fail-before filter. No
  new artifact, no DSL, no fence-depth parser.

## The tension, resolved

The two gates need opposite postures: the **pre-check is forgiving** (re-planning is cheap;
a wasted slice run is not — "too strict is a turn wasted"), while the **verify gate is
strict** (leniency here is how the 34.3% gets built, one forgiven red at a time). One tool
cannot be both; splitting them is the resolution. Above the gate everything stays
stochastic → pass^k, never one green run (F12).

## Open, deliberately deferred

Mutation / failure-injection proof (HVTB 2608.22103, F12) is the refinement for when the
verifier itself is suspected of being gamed; it belongs to telemetry (I06), not the core.
The `S16` tip proposal (`.commands` has no consumers) collides with I02: if S16 lands
first, `.commands` still gets a consumer in I02 — re-justify, don't silently revert (E37).
