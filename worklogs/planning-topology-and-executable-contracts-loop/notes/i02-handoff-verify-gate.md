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
- `TESTS: <path> (NEW)` — the marker I02's fail-before filter keys on. **It is prose today;
  I02 must decide whether to make it machine-parseable** (open Q).
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
   forgiving for authors; a token is checkable. The tension is exactly the pre-check's.
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
