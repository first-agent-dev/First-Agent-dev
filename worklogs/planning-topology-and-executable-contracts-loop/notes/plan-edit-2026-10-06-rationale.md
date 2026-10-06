# Plan-edit rationale — 2026-10-06

Why increment-01 grew SLICE1b + SLICE5, what the bridge proposed vs what landed,
and where the two 2026-09-11 reviews changed priorities. Decisions live in
`roadmap.md` (standing) and `ledger.md` (E49–E64); this file holds the reasoning
(E48: no rationale inline in plans).

Session tip: `2f6b8c1`. Full analyses (ASK#-01 options, G1 problematics, mutation
staging) were argued in session chat 2026-10-06; this note records positions.

## 1. Reorder rationale (E57)

- E52 is live, not archival: fresh plans parse to empty `.slices`, the coverage gate
  no-ops. The cheapest fix restoring the controller's hearing is emitters (SLICE1b),
  which needs only SLICE1 (the grammar it emits against).
- SLICE2/SLICE3 are consumers of parsed plans; building accessors + lint before any
  emitter writes the grammar leaves them untestable against live artifacts. Hence
  SLICE1b sits between SLICE1 and SLICE2/SLICE3.
- SLICE4 keeps the conformance fixture (CT14/CT15) but now depends on SLICE1b + SLICE3:
  the fixture asserts emitter output pre-checks clean, so it needs both.
- SLICE5 (pins) lands in I01 because its only dependency — the injection channel —
  already exists (E54); it is one registry row + one flag + an assembler, with no
  I02/I03 prerequisite. Role-loop wiring is explicitly out of the slice (E18 LOOKUP
  still open: only the coder loop consumes injections today, `coder_loop.py:206`).

## 2. R1–R8 disposition

| # | Proposal | Landed |
|---|---|---|
| R1 | SLICE1b after SLICE1 | as specified, with S1–S4 corrections (§3) |
| R2 | SLICE5 pinned invariants | as specified, CT19 narrowed to mechanism (§3 S5–S6) |
| R3 | Role-prompt deltas → bank | banked in `role-prompts-conformance.md` 2026-10-06 section (A–E) |
| R4 | Attempt counter keyed by STEP#/CT#/accept: | I02 outline (beside the gate; LoopGuard can't see it, E55) |
| R5 | Distilled failure packet ≤15 lines | I03 outline (beside REFLECT/replan) |
| R6 | GIVEN-compiler from ledger | I04 outline (beside the ledger parser) |
| R7 | STEPS mode ↔ TRIVIAL/STANDARD/LARGE | SLICE4/STEP2, no new slice |
| R8 | Cacheable-part stability + hit-rate | banked: extend `tests/test_prompt_caching_per_role.py` in I03 (needs loop traffic to measure) |

## 3. Corrections to the bridge proposal

- S1. SLICE5/STEP1 exit cited `fa inject --explain` — no such flag exists. Correct
  command: `uv run fa inject list` (subcommands `list`/`status`, `--role`, default
  coder; `cli.py:790-825,1313`).
- S2. SLICE5/STEP1 omitted `roles=`. Landed: `frozenset({"planner", "coder", "eval"})`;
  chat stays out until I05 (chat becomes the orchestrator there).
- S3. The flag is five touch points in `feature_flags.py` (`:57`, `:74`, `:111`, `:148`,
  `:309`), not "one field"; `read_flag` must read the literal `.standing_decisions_mode`
  attribute (S13 bans dynamic flag access — `injections.py` docstring).
- S4. Bridge omitted the frontmatter update. Landed: `slices: 4` → `slices: 6`.
- S5. SLICE1b/STEP1 also migrates the `Depends-on: S#` / `Parallelizable-with: S#` line;
  STEP3 also migrates the ceremony's `S#` references (`- S#: ...`, `blocks S#`);
  exits assert both greps empty — otherwise "no S# survives" fails.
- S6. Bridge's STEP4 test never asserted CT18. Landed: the test asserts the CT18 property
  directly (`accept:` present, no ` ```verify ` fence in the §9–12 span).
- S7. CT19 claimed "every role call receives the block" — unwired for planner/eval
  (only `coder_loop.py:206/834` consumes injections). Narrowed to registry + resolution +
  byte-stability + cacheable-channel property; wiring banked per role in Out of scope.

## 4. ASK#-01 (E56) — position

Options: (a) planner emits §4 directly; (b) code compiles runtime plan → increment file;
(b′) planner emits §4 + free-form `## Grounding`, code stamps IDs/hashes/risk-floor and
validates. Recommendation: (b′) — the compiler collapses from translator to stamp+validate
(~100 lines), grounding fields survive verbatim, TRIVIAL→flat-plan falls out, and
(b′)→(a) is deletion (reversible) while (a)→(b) later is a rewrite under load.
Provisional per bridge rule: (a). SLICE1b is compatible with all three (emitters learn
the target grammar either way); the decision lands pre-SLICE4. Roadmap records `assumed:`.

## 5. Substrate (ARCH G1/G2/P5b) — positions

- G1: keep markdown + loud pre-check for I01–I03. Pivot trigger (metric, not date): any
  silent mis-parse escaping the pre-check, or pre-check first-pass rate below the pilot
  threshold → schema-first lands in I04 beside the ledger parser. Roadmap `assumed:`.
- G2: positional `SLICE#` + "ids immutable once created" + letter-suffix inserts +
  CT10 failing on dangling refs. Frozen `I1-S2` keys are the revisit on first link-rot.
- P5b compat shim rejected: E24 shipped and is test-pinned (`test_plan_ids.py:367`);
  reverting it serves no live consumer (old plans archived). Migration note covers humans.

## 6. Mutation — position

Staged (a)+: I02 runs the ablation experiment (20-slice known-good/known-bad fixture,
≥95% rejection of functionally-green-but-constraint-violating patches; fail-before/pass-after
vs +mutation) with mutation in shadow (WARN/log-only); cheap stack ships immediately
(CONSTRAINT rationale lines, boundary-test-per-FUNCTIONAL, held-out tests); a per-slice
kill threshold graduates to gate only on measured precision; full verifier co-evolution
stays I06. Never gate on a noisy metric (equivalent mutants) without a baseline — that
wedges the loop and violates "never wedges". E63 GAP → I02 review. Operator decides.

## 7. Review-fold disposition

- Citation corrections (REVIEW E1–E8, ARCH §2.6) → E59; sizing rules changed: ASK#
  sized conservatively (FM-2.2 version-dependent), G3 rationale replaced (pipeline IS G3),
  version-pinning becomes a standing `decided:`.
- Re-rank → outlines: #5 stays I01/SLICE3; #2/#6 I03; #7 I01/SLICE5; #4/#9-syntactic I04;
  #3/#8/#12/#13/#14 I03/I05 as mapped; #10 re-specified (diagnosis) in Deferred.
- G1–G15 → increments: G1/G2 positions above; G3/G4 I03; G5+G6 I02; G7 prerequisite of
  #11; G8 I04; G9 I05; G10 I03 bootstrap; G11 with #15; G12 I05; G13 I06; G14 I05
  (redaction with the PR-brief); G15 standing posture (adopt seams, build the deep half).
- T1–T4 → resolutions banked: T1 REFLECT emits ledger-typed entries (I03); T2 the E61
  separation form; T3 syntactic-first triggers (I03/I04); T4 A⁻ transfer grades for
  future evidence.
- REVIEW §5.1 reliability budget → E62 GUESS + I06 reporting; §5.4 PR-brief → I03,
  throughput model → I05 prereq of #11; §5.5 fast path → standing `decided:` +
  SLICE4/STEP2 guidance; §5.5 artifact cap (1.5–2K brief) → I03 brief contract;
  §5.6 checkpointing → G4/I03, concurrency → G12/I05; §5.7 provider hazards → I03
  failure-packet sanitisation; decision surface (§4.3) → I03 brief.

## 8. Rejected

- Schema-first now (G1 as rebuild): cost without a live failure; trigger-based instead.
- Full per-slice mutation gate now: noisy metric as hard gate wedges the loop.
- Compat shim / dual grammar: reverts shipped E24 for no consumer.
- Provisional (b): translator cost + the G1 irony (parsing LLM markdown with regex);
  (b′) dominates it and (a) is the simpler fallback.
- Collapsing SLICE1b into SLICE4: SLICE2/SLICE3 need emitter output before the
  conformance fixture exists; the dependency direction forbids it.
