# Production-patterns review of the session proposals — 2026-10-06

Study note for the operator. Self-review of the three session proposals (ASK#-01,
G1 substrate, mutation staging) against production-grade patterns senior engineers
use for similar tasks — with precedents, verdicts, and high-ROI upgrades (U1–U11).

Relationship to other notes: `plan-edit-2026-10-06-rationale.md` records what
landed in the plans on 2026-10-06; this file reviews *the reasoning behind it* and
improves the recommendations. Nothing here is applied to the plans yet — §5 lists
landing pointers for the operator to approve.

## §0 Verdict in one table

| Proposal | Production-grade? | Closest precedent | Change after review |
|---|---|---|---|
| (b′) planner emits §4 + `## Grounding`, code stamps | Yes | K8s admission webhooks; Terraform plan/apply; compiler IRs | Reframed translator→**admission**; + hash-link provenance (U2); + conformance ladder L0/L1/L2 (U3) |
| keep-md + loud pre-check + pivot trigger | Yes, **as a staged decision** | Gradual typing (mypy-strict-on-TCB); strangler fig; SRE error budgets | Named the patterns; + zero-budget metric (U4); + golden corpus + differential fuzz (U5); + strangler map (U6) |
| G2 positional + freeze + suffix | Partial (small-scale prod) | Natural keys with append-only discipline; K8s name+UID | + tombstones (U7); stated scale envelope |
| E24 no-shim removal | Yes, conditionally | Stripe/K8s deprecation policy | Stated the 3 conditions explicitly |
| Staged mutation (a)+ | Yes | Google mutation-at-scale | Posture shift: findings-not-scores (U8); top-K + arid (U9); pre-registered rule (U10); dual-use corpus (U11) |

## §1 ASK#-01: two plan formats, one truth

### 1.1 Problem recap

The planner's runtime format (`prompt.py:166-240` — Class/Goal/Evidence/Scope/
Assumptions/Constraints/`S1.`-with-`accept:`/Verification/Risks/Open questions) and the
durable increment grammar (schema §4 — `SLICE#`/`CT# [CLASS]`/`TESTS:`/`STEPS:`/`DEPS:`
/` ```verify `) have no defined transform between them (E56). Options: (a) planner
emits §4 directly; (b) code compiles runtime→increment; (b′) planner emits §4 plus a
free-form `## Grounding` block, code validates + stamps only.

### 1.2 The three options on one example

Task: identical 401 for unknown email vs wrong password.

Under (a), the planner emits the increment section directly (Evidence/Assumptions/Risks
have nowhere to live — lost or schema-churn). Under (b), the planner emits the runtime
format and a ~500-line translator infers §4 from prose (two grammars, G1 irony).

Under (b′), the planner emits:

````text
## SLICE1: identical 401 for bad credentials
STEPS: prescriptive
DEPS: —
INTENT: login() rejects bad credentials without distinguishing unknown users.
CONTRACTS:
  CT1 [CONSTRAINT]: unknown email vs wrong password → identical 401 body
TESTS: tests/test_login.py
```verify
uv run pytest tests/test_login.py -q
```
- [ ] STEP1: add the check in login() (exit: test_identical_401 passes)

## Grounding (prose, not parsed)
- convention: identical error envelope @ src/fa/auth/errors.py:12
- scope-out: session management, rate limiting
- assumption: 401 envelope stays as in errors.py:12
- risk: timing side-channel distinguishes users → detection: compare response times
````

and code runs **admission**: parse → validate → default/stamp → persist. No inference.

### 1.3 Production precedents

- **Terraform plan/apply.** Humans author HCL; `terraform plan` produces a validated,
  reviewable artifact; `apply` executes *only the plan*. The plan file is exactly our
  increment file: machine-validated, human-readable, the sole execution input. `plan`
  failing loudly before anything runs is our pre-check + admission.
- **Kubernetes admission chain.** Mutating webhooks apply defaults, validating webhooks
  loudly reject, the object persists to etcd — and controllers reconcile **only from
  etcd**, never from YAML. Our controller reads only admitted increments, never runtime
  plans. The K8s rule "webhooks don't invent spec" is our "no inference" rule.
- **Compiler IRs (LLVM).** Multiple frontends (planner prompt versions, skills) lower to
  one stable IR (the increment file); multiple backends (controller, eval, telemetry)
  consume the IR. Frontends evolve freely; the IR evolves with versioning.

### 1.4 Verdict

(b′) is production-grade: it is the admission pattern with three decades of precedent.
(a) is production-grade only with structured emission (else G1 drift on long outputs).
Raw (b) is the weakest: a semantic translator between two LLM-adjacent grammars is the
component senior teams refuse to own — it accretes inference until it becomes a shadow
planner.

### 1.5 HIGH-ROI upgrades

- **U1. Admission framing (rename + shape).** Stop saying "compiler" — it invites a
  translator. The step is `parse → validate (pre-check) → default (risk floor, tree-hash
  stamp, fast-path fold) → persist`. ~100 lines. One load-bearing rule: **no inference** —
  anything the code cannot derive by rule fails loudly back to the planner.
- **U2. Hash-link provenance.** Stamp `source_plan_sha` + `admission_version` into the
  increment frontmatter; keep the runtime plan in the session log (schema §1 already
  allows: ephemeral run records live there). Cost: ~5 lines. Payoff: "planner or
  admission?" attribution becomes re-reading the linked input; the hash chain is the
  nucleus of item 16 later.
- **U3. Conformance ladder L0/L1/L2.** Graduated loud feedback instead of one "invalid":
  L0 parses (extractor stays total, never raises); L1 lints (pre-check failures name
  file:line + rule); L2 admits (floors applied, hashes stamped, TRIVIAL folded to flat
  plan). Each level independently testable; the planner learns the cheapest level first.
  Appendix A shows one drift travelling the ladder.

### 1.6 Recommendation (unchanged, strengthened)

(b′) provisional; (a) fallback; raw (b) rejected. Decide pre-SLICE4 (E56 stands).

## §2 G1 substrate: markdown-regex with a kill condition

### 2.1 Problem recap

LLM-emitted markdown drifts; each drift mode is a silent mis-parse (a slice the harness
can't see never runs; a mis-extracted verify block runs the wrong command). Concrete
drift strings against our `_SLICE_RE`:

```text
## SLICE 2: title        (space — no match, parses to empty)
## Slice 2:              (case — no match)
### SLICE2 — title       (unicode dash, no colon — no match)
"helpful" renumbering    (old SLICE2 becomes SLICE3 — DEPS:/ledger/ASK# silently re-point)
```verify inside INTENT prose  (extracted as a real command — CT13 pins this as convention)
```

Our live instance (verified 2026-10-06, E52): fresh plans parse to empty `.slices`,
`workflow_controller.py:332-334` returns early, the coverage gate no-ops **silently**.

### 2.2 Production precedents

- **Strict parsing for machine interfaces.** Go's `json.Decoder.DisallowUnknownFields`,
  protobuf field rejection, Stripe API versioning. Postel's law ("be liberal") is for
  humans; machines fail loudly. Our pre-check is `DisallowUnknownFields` for plans.
- **Gradual typing.** Python typed where it matters — this repo already runs mypy strict
  + pyrefly with the strictest rules on TCB paths. keep-md is the same posture for plans:
  dynamic authoring, strict checking at the boundary. Respectable, standard, mid-scale.
- **Strangler fig (Fowler).** The new system strangles the old incrementally — never a
  rewrite. Markdown now; structured records grow beside it (the I04 ledger parser is the
  first strangler shoot); markdown becomes a rendered view when the trigger fires. This
  names our trajectory and turns G1 from "whether" into "when".
- **SRE error budgets.** A zero budget for silent mis-parses with burn-rate consequences
  (burn → freeze features, fix substrate) is exactly how prod teams govern "temporary"
  solutions. Our pivot trigger IS an error budget — name it so the team treats it as one.
- **Golden corpora + differential fuzzing.** Every observed drift becomes a fixture;
  property tests assert mutated-valid-plans parse-identically-or-fail-loudly, never
  silently-change-meaning. Standard at Google/LLVM (libFuzzer corpora, FileCheck).

### 2.3 Verdict

keep-md is production-grade **as a staged decision with a trigger**; without the trigger
it is tech debt with a story. G1's end-state (schema-first) is correct; its timing
("now") is wrong for us — no live failure, I01 half-built, a strangler available.

### 2.4 HIGH-ROI upgrades

- **U4. Zero-budget metric, defined precisely.** `plan_extract_silent_misparse_total`
  (counter; alert on >0) + `plan_precheck_first_pass_rate` (SLI). "Silent" is
  operationalized, not philosophical: golden corpus + differential property + E23-shape
  probes (a fresh plan yielding empty `.slices` is a **loud event**, never a quiet
  return — the E23 early-return gains a counter when the input is slice-shaped). Consequence of burn: substrate sprint before features.
- **U5. Golden corpus + near-miss diagnostics + fuzz.** `tests/data/plan-drift-corpus/`:
  every drift mode a file, each asserting loud failure. The pre-check gains a near-miss
  lint (`^#{2,4}\s+SLI?CE?\s*\d` catches probable-intended headings) with rustc-style
  suggestion: `did you mean '## SLICE2:'? (line 41)`. Plus a stdlib-random differential
  property test. This combination *is* G1's accept criterion, implemented on markdown.
- **U6. Strangler map, named.** Ledger records (I04) → slice records → rendered
  increments; each increment visibly advances the strangler. When markdown is only ever
  rendered, never parsed for decisions, G1 is satisfied without a flag day.

### 2.5 G2 stable IDs — partial grade, cheap hardening

Precedent: surrogate keys (DB), K8s name (human) + UID (immutable). Our
positional+freeze+suffix is natural-keys-with-append-only-discipline: production-grade to
~100s of slices. Honest scale envelope, stated here: beyond that, surrogate keys.

- **U7. Tombstone sections.** A deleted slice leaves `## SLICE3: [retired] — superseded
  by SLICE3a, <reason>` (parseable, unrunnable). DEPS refs to it fail loudly via CT10
  instead of re-pointing. Zero schema change; the ledger's tombstone philosophy (§5
  `supersedes:`) applied to slices.

### 2.6 P5b vs E24 — conditional grade, auditable conditions

Precedent: Stripe versioning, K8s beta deprecation (serve-with-warning for N releases,
then remove). E24 (zero-deprecation removal) is production-acceptable **iff all three
hold**: (1) no live consumers of the old form; (2) corpus small, archived, mechanically
migratable; (3) migration note shipped for humans. All three hold today (SLICE4/STEP3
covers humans). If any fails later → P5b-style warn-and-remove. Write the conditions
next to the decision so a future reader knows when it expires.

## §3 Mutation staging: findings, not scores

### 3.1 Evidence recap

Fail-before/pass-after proves sensitivity *to the change*, not *to the behaviour*.
LLM-authored tests carry weak assertions; vanilla mutation score ~53% → ~89.5% with
feedback; 2026 frontier reaches 87% with full context; all models omit
`None/inf/NaN` tests. Our repo already owns slice-scoped mutation tooling
(`scripts/run_slice_mutmut.py`) and a kill-check protocol (feature-planning §12).

### 3.2 The production precedent: Google, "Mutation Testing at Scale"

Google runs mutation on **changed lines only**, surfaces surviving mutants as
**code-review findings** (not gates, not scores), suppresses unproductive mutants with
measured arid-node heuristics, and caps findings per changelist. Developers accept it
because signal≫noise. Meta/Chromium converge on the same posture. The key insight for
us: **nobody gates on mutation score** — survivors are routed to the test's author as
repair targets. Our roles map perfectly: the planner authors the tests, so the planner
receives the survivors.

### 3.3 Verdict

Staged (a)+ is production-grade and converges on Google's posture. (b) numeric-gate-now
is not — no prod team hard-gates on a noisy metric (equivalent mutants) without a
measured baseline; it wedges the loop and violates "never wedges". (c) I06-only delays
cheap signal (the tooling and the culture already exist here).

### 3.4 HIGH-ROI upgrades

- **U8. Findings-posture, not score-posture.** Survivors become planner repair targets
  (`MUTANT: <file:line> | <operator> | survived <test-id> | contract <CT#>`), each judged
  by the planner (or L3) individually. Equivalent-mutant noise dies structurally: a
  judged finding is either a real gap or one dismissed line — never a red number.
- **U9. Top-K cap + arid suppression.** Cap findings per slice (planner attention budget,
  start K=5, ranked CONSTRAINT-first). Suppress mutant classes the ablation shows are
  never productively killed — our arid list, **measured, not assumed**.
- **U10. Pre-registered graduation rule.** Write the decision rule *before* running the
  ablation, e.g.: "shadow→gate iff survivors-as-findings precision ≥ 0.8 AND +10pp
  rejection on the calibration set; else keep shadow." Experiment discipline that
  prevents moving goalposts — the senior touch REVIEW §9 asks for.
- **U11. One corpus, two consumers.** Build the 20-slice calibration set as versioned
  SWE-Gate-style pairs (merged patch + review comment → constraint test,
  known-good/known-bad labels) under `tests/data/`. It serves the ablation today and
  becomes the nucleus of the item-12 held-out regression set tomorrow. AGENTS.md rule 3
  (every write target has a consumer) satisfied twice over.

### 3.5 Staged recommendation (unchanged, strengthened)

I02: ablation + shadow + cheap stack (CONSTRAINT rationale lines, boundary-test rule,
held-out tests). Shadow→FAIL only on measured precision (U10). Full co-evolution in
I06 iff the data justifies. E63 GAP stands until the operator confirms.

## §4 The principles underneath (the wise part)

1. **Loud > silent.** Every silent failure becomes a loud error or a metric (U3–U5).
2. **Shadow > gate.** New signals earn gatehood by measured precision (U10).
3. **Measured > assumed.** Budgets, triggers, and graduation rules are numbers with
   dates — never vibes (U4, U9, U10).
4. **Reversible > optimal.** (b′) over (a)-forever; strangler over rewrite (U1, U6).
5. **Findings > scores.** Route signal to the author who can act, with an attention
   budget (U8, U9).
6. **Every artifact has a consumer.** Corpus→ablation+regression; hash-link→attribution;
   ladder→planner feedback (U2, U11).

## §5 Changelog vs session proposals + landing pointers (approve before applying)

| # | Upgrade | Changes vs 2026-10-06 session text | Lands in (pointer, not applied) |
|---|---|---|---|
| U1 | Admission framing | "Compiler" renamed; no-inference rule explicit | ASK#-01 decision pre-SLICE4; mechanism split: validation→I01/SLICE3, default/stamp→I03 controller |
| U2 | Hash-link provenance | New (5 lines) | Admission spec; nucleus of item 16 |
| U3 | Conformance ladder L0/L1/L2 | New structure on existing SLICE1+SLICE3 | I01 (names the levels in SLICE3); planner feedback copy |
| U4 | Zero-budget metric | Trigger made SRE-explicit | I01/SLICE3 (counter + SLI definition); I06 reporting |
| U5 | Golden corpus + near-miss + fuzz | New test data + one lint | I01/SLICE3 (corpus is pre-check test data — near-zero cost, highest ROI here) |
| U6 | Strangler map | Names the trajectory | Roadmap standing (one line); I04 parser is shoot #1 |
| U7 | Tombstones | New convention | Schema §4 (one line) + SLICE4 guidance |
| E24 | Auditable conditions | Conditions stated | Rationale §5 (append) or ledger |
| U8–U9 | Findings-posture + caps | Score→findings shift | I02 review inputs (extend `i02-handoff-verify-gate.md` §6) |
| U10 | Graduation rule | New discipline | I02 ablation spec |
| U11 | Dual-use corpus | One corpus, two consumers | `tests/data/` + I02 spec + item-12 seed note |

## Appendix A: one drift through the ladder

Input line 41: `## SLICE 2: login validation`.

```text
L0 parse:      total — yields no slice for line 41 (never raises, never guesses).
L1 lint:       FAIL — "line 41 looks like a slice heading but does not parse:
               did you mean '## SLICE2:'? (rule: near-miss-heading)". Planner fixes.
L2 admit:      not reached. Had L1 passed, admission would stamp risk-floor/tree-hash
               and persist; a TRIVIAL single-section plan would fold to the flat fast path.
```

Without the ladder: L0's empty result flows to the controller, E23 fires silently,
the coverage gate no-ops. The ladder converts silence to a diagnostic at the cheapest
possible level.

## Appendix B: admission sketch (~30 lines of shape, not code)

```text
admit(runtime_plan_text, repo_state) -> IncrementFile | AdmitError:
  1. sections = split_sections(text)            # L0: total, line-anchored
  2. failures = precheck(sections)              # L1: CT8/CT9/CT10 + near-miss + TESTS-contained
  3. if failures: return AdmitError(failures)   # loud, planner fixes in one pass
  4. apply risk_floor(section)                  # default, never below floor (G9)
  5. stamp tree_hash, HEAD, source_plan_sha     # provenance (U2)
  6. if trivial_single_section: fold to flat    # fast path (standing decision)
  7. persist increment file + return it         # L2: the controller reads ONLY this
Rule: step 4–6 derive by rule or fail. Nothing is inferred from prose.
```

## Appendix C: the error budget, written as an SLI

```text
SLI:  plan_precheck_first_pass_rate = admitted-first-try / submitted
Floor: pilots must clear 0.80 by end of I03, else planner-prompt work preempts features.
Hard budget: plan_extract_silent_misparse_total == 0, always.
  - measured by: golden corpus (U5) + differential property + E23-shape probes.
  - burn (any nonzero): freeze feature work, substrate sprint, G1 revisit immediately.
```

## Appendix D: a mutation finding, routed

```text
MUTANT: src/fa/auth/login.py:87 | comparison a==b → True | survived test_identical_401
contract: CT1 [CONSTRAINT] (identical 401 body)
planner action: strengthen the assertion (compare bodies byte-wise) or dismiss with reason.
ledger: dismissed mutants append GUESS→decided: with the reason; never silently dropped.
```

Top-K=5 per slice, CONSTRAINT-first. Dismissals are data: three dismissals of one
operator class nominate it for the arid list (U9).
