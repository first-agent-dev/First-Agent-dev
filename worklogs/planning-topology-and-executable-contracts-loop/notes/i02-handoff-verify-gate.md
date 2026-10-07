# I02 hand-off — the verify gate, grounded context bank

**Not a plan.** Per the staleness rule (plans go stale at the increment boundary), I02 is
*reviewed* when I01 lands. This file exists so that review refines against **evidence**, not
memory. It banks what is known (verified @ tip `0e08ece`, 2026-09-07) and lists what is still
open, so the I02 review has material instead of re-deriving it.

Companion artifacts:
- `notes/verify-block-design.svg` — the picture (four tiers, ritual, seven-row truth table).
- `notes/verify-block-design.md` — the reasoning in prose, with research citations.
- `RESEARCH` note: F8 / F11 / F12 / §4E / §7 items 1 & 5 are the source of the design.

## 1. Grounded facts (verified at tip, re-verify at I02 review time)

- `extract_plan_ids` has exactly two external callers, `workflow_controller.py:332` and
  `:461`, and both read only `.slices`. `.commands` has **zero readers** (only mention is
  `is_empty`, `plan_ids.py:109`). ⇒ the gate does not exist yet; I02 is what creates it.
- `_VERIFY_BLOCK_RE` at `plan_ids.py:85` matches a ```verify fence to the next fence; a
  nested example (````text wrapper) is still extracted as real commands (`test:225`). The
  I01 pre-check turns this into a WARN on orphan fences; I02 must not "fix" it by parsing
  fence depth (rejected as more machinery than the risk warrants).
- `_extract_commands` (`plan_ids.py:123`) drops blanks/`#` comments, preserves the rest
  verbatim, no validation, no per-slice attribution. **I01/SLICE1-2 adds** `slice_records`
  and `commands_for(slice)` — the interface I02's runner will consume.
- `_git_output` (`workflow_controller.py:401`) collapses OSError/SubprocessError → `None`.
  That is the opposite of fail-loud. I02 needs a runner with a **three-state** result
  (PASS/FAIL/ERROR); reusing `_git_output` as-is would let "couldn't run" read as "passed".
- The repo already has mutation tooling (`scripts/run_slice_mutmut.py`, `count_mutants.py`,
  `mutation_sweep.py`) — the deferred verifier-co-evolution story (I06) can build on it; it
  is not part of I02's core.

## 2. What I01 delivers that I02 consumes (the contract boundary)

- `commands_for("SLICEn")` — the slice's verify commands only (CT3).
- `section("SLICEn")` — the coder's scoped brief (CT4); I02 runs commands in the slice's
  scope, the coder never sees the rest of the plan.
- `TESTS: <path> (NEW)` — the marker I02's fail-before filter keys on. **At 2f6b8c1 it does not
  reach I02 at all**: `_test_paths` (`plan_ids.py:212`) stops at the first `(` and discards the
  annotation, so this row described an interface that did not exist. I01/CT33 now preserves the
  raw string as `SliceRecord.tests_note` and deliberately gives it **no** meaning. Open question
  2 below is unchanged in substance and now has data to decide on (ledger E75).
- `SliceRecord.test_paths` — per-slice test paths (renamed from `.tests` to avoid colliding
  with the flat `PlanIds.tests` `T#`-ID field).

## 3. The design I02 must refine (already agreed in review, banked here)

Ritual per slice: **pre-check → baseline → fail-before → pass-after**, then the seven-row
truth table (see the SVG). Only `NEW test: RED→GREEN` is PROVEN; `NEW test: GREEN` is
rejected as vacuous; `existing: GREEN→RED` blocks as regression; `existing: RED→RED` is
advisory; `ERROR` is never PASS. Two postures: pre-check forgiving, verify gate strict.

## 4. Open questions — resolve at the I02 review, not before

1. **Granularity.** The truth table is per-command, but `pytest <file>` covers many tests at
   once, so per-command RED is coarse. Decide: run each `NEW` test file **alone** for the
   fail-before phase (fine-grained), while the pass-after phase may run the slice's commands
   as written.
2. **The `NEW` marker.** Prose `(NEW)` vs a machine-readable token on `TESTS:`. Prose is
   forgiving for authors; a token is checkable. The tension is exactly the pre-check's. I01
   delivers the raw annotation in `SliceRecord.tests_note`; I02 chooses the semantics. Note the
   third option the two-sided framing hides: derive NEW-ness from the repository — a path absent
   from `HEAD` *is* new — and treat the annotation as an authoring hint the pre-check cross-checks
   rather than as the source of truth. That removes the marker from the trust path entirely.
3. **Baseline storage.** Must be ephemeral (session-log root), never in the project folder
   (schema rule). Since it only needs to live within a run, decide the exact path + lifetime.
4. **Result shape + home.** A frozen three-state dataclass; where it lives (new
   `verify.py` vs `plan_ids.py`) — `plan_ids.py` is currently pure-parsing; a runner with
   subprocess belongs elsewhere.
5. **Timeouts.** Per-command wall-clock budget; a hang is ERROR, never a stall, never PASS.
6. **The S16 collision.** The tip itself proposes removing `.commands` ("no consumers").
   I02 *is* the consumer. If S16 lands before I02, `.commands`/`commands_for` must be
   re-justified against I02, not silently reverted (ledger E37).
7. **Regression attribution across slices.** If slice B's baseline shows a RED caused by
   slice A's merged change, that is pre-existing for B — confirm the per-run baseline (not a
   global one) is the right scope.

## 5. What must NOT leak into I02

- No DSL for verify blocks. The block stays a command list; discipline lives in code.
- No fence-depth parsing for the grammar-collision trap (pre-check WARN instead).
- No mutation/failure-injection proof in the core (that is the I06 verifier-co-evolution
  story).
- No `VERIFIED` status from I02 alone — `VERIFIED` needs I03's eval L2 on top (schema §6).

## 6. Banked from the 2026-10-06 review walk (decided; build in I02)

Rationale for each: `notes/decisions-qa-2026-10-06.md`. Ledger: E63–E66.

**6.1 What "the gate works" means — phase-1 exit criterion.** The gate rejects **≥95% of
patches that pass the functional tests but violate a stated constraint**, measured on a
20-slice calibration corpus of known-good / known-bad pairs under `tests/data/`. Nothing else
in this project defines gate success; without this, "the gate works" is an opinion. The same
corpus is the seed of the held-out regression set (backlog item 12) — one corpus, two
consumers.

**6.2 Baselines are hermetic and affected-path scoped.** §3's "run the slice's commands once on
the untouched tree" is O(slices × suite-time) and will not survive a real increment. Scope the
baseline to the paths the slice touches. (E66.)

**6.3 `TEST-DEFECT` is a first-class verdict** with its own budget. Today "the test is wrong" is
not an expressible outcome, so a wrong test burns the whole repair ladder and wedges the loop.
This is a liveness requirement, not a quality one. A flaky *planner-authored* test is a planner
defect, not an environment defect: quarantine it, do not merely re-run it.

**6.4 Non-vacuity = one scoped mutation run per slice, as a gate, with appeal.** Changed lines
only; tooling already exists (`scripts/run_slice_mutmut.py`, `count_mutants.py`,
`mutation_sweep.py`). A survivor blocks by default; the planner may dismiss it with a one-line
reason appended to the ledger via `GUESS→decided:`. No exception for refactor-only slices — a
refactor claims behaviour is preserved, so a survivor there is signal. Do **not** build a
findings format, a top-K ranker, a shadow phase or a graduation rule; if an arid list is ever
needed it derives from repeated dismissals. (E63.)

**6.5 Boundary coverage.** The pre-check requires at least one boundary or edge test per
`FUNCTIONAL` contract. Every evaluated model systematically omits `None`/`inf`/`NaN` cases.

**6.6 Attempt accounting keys on the work unit, not the tool signature.** `attempt_count` keys
on `(tool_name, params_hash)`, and LoopGuard deliberately treats distinct params as progress,
so three different failed fixes for one contract are invisible. Note before designing: per E60
`BlackboardEntry` already supplies the typed record and `content_hash` already canonicalises —
an attempt is `type="attempt"` chained by `parent_id`, not a new type.

**6.7 Verification integrity — banked whole, IntentGuard untouched this cycle.** Five controls:
`TESTS:` paths read-only to the coder; verify runs where the coder cannot write; hash the
verification surface at baseline and re-check at the gate; deny-list `conftest.py`, test config
and CI workflows; a derivation-vs-retrieval telemetry category. Per E60, four of the five are
**assertions over `BlackboardEntry.write_set`, not new machinery** — audit before building.
I01 supplies the input via `tests_for` (CT20). The diff-path assertion itself belongs here, not
in the pre-check: a pre-check is static and pre-coder, and there is no diff to inspect yet.

**6.8 Eval calibration before trust.** k=2 is not trustworthy until a labelled calibration set
(≥100 verdicts) exists. Family switching changes the *direction* of judge error, not its size.

## 7. The live gate I02 owes (SD-C, operator decision Q37, 2026-10-06)

I01 ships no live-path test and says so in its DoD. That is legitimate only because I02 is
named here as the increment that adds one — the same discipline SD-B applies to accessors.

**What I02 must prove, and why static conformance cannot.** I01's gates all answer "does this
string parse?". None answers "does anything call the parser?". The project has already produced
both failure modes this is aimed at: a dead `_slice_sections` shipped *inside* the slice that
orphaned it, caught only by a mutation sweep (E89); and the per-slice coverage gate at
`workflow_controller.py:332` silently no-opping for the entire life of I01 because real planner
output carried no slices (E52). Neither is visible to a fixture test, and both would survive an
agent reporting the work complete.

**Shape.** Boot the real composition root — `drive_session` with the shipped factories,
`hooks=HookRegistry()`, a real workspace in `tmp_path`; mock **only** `ProviderChain.request`,
returning a plan authored from the SLICE1b skill text. Then assert observable effects, not the
absence of an exception:

- the slice's own `commands_for(SLICE#)` commands ran, in order, and nothing else did;
- a command belonging to a *different* slice did **not** run — the per-slice scoping is the
  whole point, and a gate that runs everything passes a naive test;
- `commands_for(None)` ran at plan level exactly once;
- a non-zero exit routes to REPAIR_REQUIRED rather than PASS;
- `request.call_count` is 0 after the gate fires on a fail-before (early-stop efficiency).

**Producer kill-check, named in the test docstring:** deleting the `commands_for` call site in
the gate must fail the test. A kill-check aimed at the consumer or at `extract_plan_ids` does
not count — it would stay green with the gate unwired, which is precisely the condition this
exists to detect.

**`tests/fixtures/session_wiring.py`** already builds this harness for other suites; reuse it
rather than assembling a parallel one.
