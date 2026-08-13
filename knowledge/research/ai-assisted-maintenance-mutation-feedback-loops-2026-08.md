---
title: "AI-assisted code maintenance and mutation-survivor avoidance"
status: draft-research-note
compiled: 2026-08-13
purpose: |
  Preserve the S3 readiness-engine mutation case study, working hypotheses,
  source ratings, and candidate process controls for later re-research and a
  dedicated implementation plan. This note is not an accepted ADR or current
  implementation authority.
local_case:
  plan: worklogs/implementation-plans/PLAN-session-workspace-readiness-bootstrap.md
  slice: S3
  initial_mutation: 816 killed / 1291 total; 475 survived
  final_mutation: 866 killed / 874 total; 8 equivalent
source_classes:
  - official project/tool documentation
  - DORA/Google engineering research
  - peer-reviewed or accepted empirical software-engineering research
  - preprints and industry telemetry, explicitly caveated
---

## 0. Status and intended use

This is a **draft research note**, not a final recommendation, ADR, skill update,
or approved implementation plan.

It exists to support a later research pass on this question:

> How should an AI-assisted production workflow constrain implementation shape,
> test seams, mutation feedback, and tooling so that correctness feedback arrives
> before generated code becomes expensive to simplify?

The immediate evidence comes from First-Agent's S3 readiness implementation.
External literature is used to frame hypotheses, not to generalize one local case
into a universal law.

Expected later consumers:

- a finalized research synthesis;
- revisions to `feature-planning`, `tests-writing`, and `mutation-clearing`;
- a mutation-runner/tooling implementation plan;
- a possible permanent mutation gate for critical new modules.

---

## 1. Executive brief

### 1.1 Main finding

The S3 cleanup cost was not primarily caused by missing requirements. The plan
specified behavior thoroughly, and live-path tests correctly proved manager,
CLI, and entrypoint producers. The expensive gap was **mutation-aware design and
feedback timing**.

The first readiness engine reached 833 production lines before its first
mutation run. It encoded repeated combinations of status, reason, stage, argv,
return code, fingerprint, timeout, platform path, and serializer options. Mutmut
then explored each syntactic degree of freedom independently.

The first run produced:

```text
1,291 total mutants
816 killed
475 survived
0 timeout/error/suspicious
```

After survivor clustering, structural compression, and focused tests:

```text
874 total mutants
866 killed
8 equivalent
0 timeout/error/suspicious
```

The effective non-equivalent score became:

```text
866 / (874 - 8) = 100%
```

### 1.2 Important distinction

Three quantities must not be conflated:

1. **mutants generated** — syntactic mutation opportunities in production code;
2. **mutants survived** — variants not distinguished by selected tests;
3. **cleanup cost** — time to stage, run, decode, classify, refactor, test, and
   rerun.

A high mutant count is not itself a high bug count. A high count can indicate a
large or syntax-rich implementation. A high number of **non-equivalent
survivors**, however, indicates missing behavioral discrimination, weak test
seams, or excessive independently mutable policy.

### 1.3 Proposed missing control

The working proposal is a combined gate:

```text
small implementation batch
  → first green behavior
  → design compression
  → targeted mutation immediately
  → survivor cluster review
  → only then wire the next producer/consumer
```

The missing piece is not “more tests at the end.” It is **C4 mutation feedback
shifted left into implementation design**.

---

## 2. Local S3 case study

### 2.1 Scope

S3 implemented:

- a stdlib readiness state machine;
- process execution and timeout mapping;
- fingerprinting;
- lock/log/marker/sentinel I/O;
- hook installation and validation;
- manager new/attach producers;
- CLI fail-open adapter;
- entrypoint readiness producer.

This is unusually mutation-dense code because it combines state transitions,
security boundaries, filesystem authority, subprocess policy, telemetry, and
platform branches.

### 2.2 Initial survivor concentration

The first 475 survivors were concentrated as follows:

| Function/area | Initial survivors | Interpretation |
| --- | ---: | --- |
| `_ensure_locked` | 93 | transaction repeated paths, reasons, strictness, and telemetry |
| `_read_python_minor` | 69 | platform branch, strict/soft behavior, process metadata |
| `_uv_executable` | 46 | repeated command, timeout, reason, cwd, and argv policy |
| `_uv_check` | 26 | strictness and process projection |
| `ensure_workspace_ready` | 26 | normalization and fallback projection |
| `_run_process` | 21 | missing/timeout/nonzero metadata |
| `_record_locked` | 21 | degraded marker and observability behavior |
| `_append_log` | 20 | NDJSON fields, append flags, encoding, serialization |
| `_install_workspace_hooks` | 19 | exact source/force delegation and failure map |

The top three functions accounted for 208 survivors, approximately 44% of the
initial set. This was a design signal: the policy was concentrated in large
functions but repeated through many mutable arguments.

### 2.3 Structural changes that reduced mutant generation

The readiness module was reduced from 833 to 684 lines. More importantly, it
removed independently supplied, derivable state.

Before simplification, failures could carry separately mutable fields:

```text
status
reason_code
stage
argv
return_code
fingerprint
```

After simplification:

```text
reason_code → derives status
reason_code → derives stage
reason_code → derives safe argv projection
return_code and fingerprint remain event-specific evidence
```

Other reductions:

- platform paths moved to module-level policy;
- repeated command argv moved to constants;
- redundant JSON options were deleted;
- redundant mkdir/mode arguments were removed where authoritative chmod occurs
  before content creation;
- atomic writes reused the private no-follow opener;
- fingerprint schema received one golden digest test;
- error normalization was centralized.

Result:

- production lines fell by about 18%;
- mutation opportunities fell by about 32%;
- non-equivalent survivors fell to zero.

This suggests that mutation count can serve as a **design feedback signal**, not
only a test score.

### 2.4 Test changes that killed meaningful survivors

Useful additions asserted contracts rather than arbitrary implementation lines:

- exact process `cwd`, timeout, environment, and failure projection;
- strict versus soft interpreter validation;
- every declared fingerprint input and one stable golden digest;
- exact per-reason NDJSON stage/argv/status/return-code projection;
- two sequential log records to prove append behavior;
- marker/sentinel private mode and active-state distrust;
- stale, missing, non-executable, and wrong-target hooks;
- symlinked state/log/lock rejection;
- marker removal and log write failure behavior;
- exact repair transaction order;
- CLI parser/path/exit/JSON/stderr;
- manager, CLI, and entrypoint producer-removal kill-checks.

### 2.5 Test patterns that initially underperformed

The following patterns produced green tests but weak mutation discrimination:

1. **High-level internal monkeypatching.** Replacing `_ensure_locked` or
   `_hooks_current` proved top-level mapping while bypassing lower-level argument
   plumbing.
2. **Permissive fakes.** `**kwargs` fakes accepted mutated cwd, timeout,
   fingerprint, and strictness.
3. **Broad assertions.** Allowing either `None` or a fingerprint concealed
   dropped diagnostic context.
4. **Single-write tests.** A log opened without append could overwrite its first
   record and still satisfy a one-row oracle.
5. **Parsed-only serialization tests.** Semantically equivalent serializer
   options survived; the better response was deleting redundant options.
6. **One-platform execution.** Linux cannot distinguish inactive Windows branch
   string variants; these require platform tests, policy centralization, or an
   equivalent ledger.

---

## 3. Causal model

### 3.1 What creates many mutants

Mutant generation rises with eligible AST operations, especially:

- repeated literals and enum-like strings;
- Boolean expressions;
- comparisons and boundary constants;
- optional/default arguments;
- repeated keyword-heavy function calls;
- duplicated error mapping;
- serialization options;
- platform conditionals;
- defensive branches;
- large functions coordinating multiple policies.

One line can produce several mutants. A call with eight independently mutable
arguments can produce more mutation opportunities than several lines of simple
business logic.

### 3.2 What causes meaningful survivors

A non-equivalent survivor usually indicates one of these:

- an unasserted branch or fallback;
- dropped telemetry/audit context;
- a permissive fake or mock at the wrong boundary;
- parameter drift not reflected in output for the chosen test input;
- broad assertions that admit multiple states;
- missing sequential/concurrency behavior;
- a production consumer not wired to the tested helper;
- dead or unreachable defensive code.

This aligns with the local `mutation-clearing` four-archetype taxonomy, but the
workflow must apply that taxonomy earlier.

### 3.3 What causes equivalent survivors

The final S3 equivalents came from:

- create-mode omission followed by immediate authoritative `fchmod(0600)` before
  use;
- Linux-inactive changes to the Windows platform token;
- error-code mutations normalized by a later boundary to the same externally
  observed result.

Equivalent mutation is a real research/tooling problem, not evidence that every
survivor needs another test. Later research should distinguish:

- semantic equivalence for all valid inputs;
- equivalence only under a platform/configuration;
- upstream-invariant or unreachable defensive branches;
- test-environment equivalence that would differ elsewhere.

### 3.4 What increases cleanup cost without increasing mutant count

Operational contributors in S2/S3 included:

- temporary mutation configuration;
- untracked-file scope discovery;
- missing staged dependencies (`also_copy`);
- tmpfs exhaustion from repeated pytest temporary trees;
- large ungrouped result output;
- manual AST/diff decoding;
- full regeneration after structural changes;
- inability to apply a repository-wide type filter because baseline Pyrefly is
  not green.

These are internal-platform problems. Better tests alone do not solve them.

---

## 4. Assessment of the current skills

### 4.1 `feature-planning`

Strengths:

- source verification;
- contract and gap traceability;
- path/matrix inventory;
- producer kill-checks;
- failure behavior and rollback.

Missing controls:

- mutation-surface estimate;
- implementation WIP/batch limit;
- single-authority map for derivable state;
- mandatory design-compression review;
- interim C4 checkpoint before the next edit packet.

### 4.2 `tests-writing`

Strengths:

- C1/C2 live-path preference;
- producer proof;
- exact structured oracles;
- zero-provider-call checks;
- failure observability;
- anti-theater discipline.

Missing or under-emphasized controls:

- mock-seam audit for state machines;
- restrictive fake signatures;
- sibling plumbing tests when an internal helper is fault-injected;
- sequential-state checks for append/cache/transaction behavior;
- mutation before the whole slice is complete.

### 4.3 `mutation-clearing`

Strengths:

- useful survivor taxonomy;
- equivalent-mutant criteria;
- warning against implementation-mirroring tests;
- structural-refactor escalation.

Missing control:

- its trigger is reactive. It should load **before the first mutation run for a
  new critical module**, not only when survivors already exist.

### 4.4 Working hypothesis

The three skills currently form a mostly serial pipeline:

```text
plan → tests → implementation → mutation cleanup
```

The proposed system is interleaved:

```text
plan
  → micro-contract
  → test
  → minimal implementation
  → refactor/compress
  → mutate/classify
  → next micro-contract
```

---

## 5. Candidate process controls

These are draft controls for later validation, not adopted policy.

### 5.1 Mutation-aware small-batch gate

Suggested heuristic:

```text
Stop and mutate when either threshold is reached:
- 150–200 new production lines in one packet, or
- approximately 250 generated mutants.
```

The thresholds are intended as WIP controls, not universal quality metrics.
Critical exception: a cohesive generated data table may exceed line limits while
having low decision complexity.

### 5.2 Single-authority declaration

Before coding, list each policy-bearing value and its authority.

Example:

| Projection | Authority | Independent input allowed? |
| --- | --- | --- |
| readiness status | reason code | no |
| log stage | reason code | no |
| safe argv projection | reason code/command spec | no |
| process return code | completed process | yes |
| fingerprint | computed input digest | yes |
| venv path | one platform policy | no |

Rule candidate:

> Do not pass or store a value independently when it is a deterministic
> projection of another closed value.

### 5.3 Design-compression gate

After first green and before wiring the next consumer, ask:

1. Which arguments can be derived?
2. Which literals are repeated?
3. Which states can disagree but should not?
4. Which explicit defaults are redundant?
5. Which branches are platform policy rather than local logic?
6. Can production LOC or mutation opportunities fall materially without losing
   a contract?
7. Is one failure represented in multiple layers?

### 5.4 Survivor cluster stop rule

Candidate rule:

```text
Stop before the next packet when:
- any non-equivalent survivor is known;
- more than 20 survivors are unclassified; or
- 3+ survivors share the same repeated field/literal/argument shape.
```

A cluster should trigger production refactoring before test expansion.

### 5.5 Mock-seam rule

For product/state-machine claims:

- mock process, network, clock, or filesystem boundaries;
- do not replace the state transition under test;
- if an internal helper must be replaced to force an OS fault, add a sibling
  exact input/output projection test;
- avoid `**kwargs`-only fakes for security/lifecycle contracts;
- record relevant cwd, timeout, environment overrides, strictness, authority
  path, return code, and diagnostic context.

### 5.6 Final mutation acceptance

Candidate final gate for a new critical module:

```text
zero non-equivalent survivors
zero unclassified survivors
equivalents documented with exact diff and rationale
zero timeout/error/suspicious results
producer-removal checks restored and rerun
```

Raw 100% should not be required when proven equivalents remain.

---

## 6. Candidate tooling work

### 6.1 Slice mutation runner

Proposed internal tool:

```text
scripts/run_slice_mutmut.py
```

Candidate interface:

```text
--source <new-or-tracked production file>
--tests <one-or-more test files>
--also-copy <dependency roots>
--tmp-root <root-backed path>
--result-json <artifact path>
--diff-report <artifact path>
```

Required behavior:

- supports untracked source/tests;
- does not leave `pyproject.toml` modified;
- uses root-backed `TMPDIR` by default;
- stages declared dependencies;
- preserves reusable mutant state when source identities remain stable;
- runs clean tests and forced-fail liveness checks;
- groups survivors by function and mutation operator;
- exports exact unified diffs;
- records killed/survived/timeout/error/suspicious counts;
- fails on unclassified survivors, not merely on a raw percentage.

### 6.2 Type-invalid mutant filtering

Mutmut supports a `type_check_command`. A later experiment should measure how
many `None`/deleted-argument mutants can be filtered by a scoped Mypy or Pyrefly
command before pytest.

Constraints:

- use a changed-module scope because repository-wide Pyrefly has known baseline
  failures;
- record filtered counts separately from killed/equivalent counts;
- do not allow type filtering to hide dynamically meaningful mutants;
- confirm the type checker runs inside the mutant staging tree.

### 6.3 Covered-line filtering

Mutmut also supports covered-line filtering. This should be evaluated carefully:

- benefit: less noise and faster runs;
- risk: uncovered critical code disappears from mutation results;
- prerequisite candidate: explicit coverage authority for the target module;
- recommendation for research: compare full versus covered-line runs on the same
  module before adopting.

### 6.4 Permanent scope and baseline

The readiness module was mutation-tested via temporary configuration. A later
plan should decide whether to permanently add:

```text
src/fa/workspace_bootstrap.py
tests/test_workspace_bootstrap.py
also_copy = ["src/fa"]
```

to the repository mutation gate.

Evaluate CI runtime, staging size, and interaction with the current protected
mutation scope before editing permanent configuration.

---

## 7. Metrics and proposed experiments

### 7.1 Metrics worth collecting

Per production packet:

- production LOC added/removed;
- function count and maximum function length;
- branch count/cyclomatic complexity;
- repeated policy literal count;
- mutants generated;
- mutants per production LOC;
- initial killed/survived/equivalent counts;
- survivor clusters by function/operator;
- time to first mutation feedback;
- time spent in test additions versus production refactoring;
- final non-equivalent score;
- mutation infrastructure failures;
- test LOC added during survivor clearing.

### 7.2 Local baseline hypotheses

| Hypothesis | Proposed test |
| --- | --- |
| Earlier mutation reduces cleanup time | Compare S4 micro-packets with S3 retrospective timing |
| Single-authority design lowers mutant density | Implement equivalent small state projections both ways in a disposable fixture |
| Type filtering removes low-value mutants | Run S3 final source with and without scoped type filter |
| Restrictive fakes improve mutation score | Compare permissive `**kwargs` fake versus exact recording fake |
| Compression reduces mutation count faster than tests | Record counts before/after refactor with tests held constant |
| One mutant per changed line improves actionability | Sample all-mutant versus one-per-line survivor review |

### 7.3 Questions for later research

1. What interim survivor threshold balances feedback speed and rigor?
2. Should mutant count be treated as a maintainability metric or only a testing
   cost metric?
3. Which mutmut operators generate the most equivalent or low-value mutants in
   this Python codebase?
4. Can AST patterns safely suppress standard-library-default and post-`fchmod`
   equivalents?
5. How should Linux-only CI classify Windows-inactive survivors?
6. Does scoped type filtering improve actionability without hiding runtime
   faults?
7. What packet size best predicts reviewability: LOC, mutant count, branches, or
   number of independent authorities?
8. Should critical modules require permanent mutation baselines in CI or
   PR-local evidence artifacts?
9. Can survivor clusters automatically recommend “refactor production” versus
   “add behavior test”?
10. How much test maintenance burden is introduced by exact plumbing tests?
11. Should mutation evidence be attached to PR review similarly to Google’s
    changed-line model?
12. What is the right policy for `# pragma: no mutate`: prohibit, narrow ledger,
    or AST-based centralized suppression?

---

## 8. Source evaluation rubric

Ratings in this note assess usefulness for **this research question**, not the
overall quality of an organization or publication.

| Rating | Meaning |
| --- | --- |
| **S** | Primary/official and directly actionable; read first |
| **A** | Strong empirical or peer-reviewed evidence; important follow-up |
| **B** | Useful evidence or synthesis with material limitations |
| **C** | Leads/context only; verify independently before use |

Dimensions considered:

- authority and provenance;
- peer review or official ownership;
- methodological transparency;
- direct relevance to mutation/AI maintenance;
- reproducibility/data availability;
- recency;
- external-validity limitations.

---

## 9. Rated source reading list

### S1 — Practical Mutation Testing at Scale: A View from Google

- **Rating:** S
- **URL:** <https://arxiv.org/pdf/2102.11378>
- **Why read:** Directly addresses scale and actionability. The approach mutates
  changed code, filters likely irrelevant/arid nodes, limits mutants per line,
  and uses historical operator performance. It reports evaluation over nearly
  17 million mutants and 760,000 changes.
- **Most relevant ideas:** incremental changed-line mutation; limited surfaced
  mutants; suppression of unproductive nodes; actionability over raw score.
- **Limitations:** Google’s languages, review platform, coverage infrastructure,
  and scale differ substantially from First-Agent and mutmut.
- **Follow-up:** Extract the exact definitions of productive/actionable mutant
  and compare their filtering heuristics with S3’s eight equivalents.

### S2 — State of Mutation Testing at Google

- **Rating:** S
- **URL:** <https://research.google.com/pubs/archive/46584.pdf>
- **Venue:** ICSE-SEIP 2018
- **Why read:** Primary industrial account of diff-based mutation integrated into
  code review, including operator survival and developer feedback.
- **Most relevant ideas:** one mutant per affected covered line; arid-node
  suppression; developer-facing actionability; language/operator differences.
- **Limitations:** older system snapshot; probabilistic surfacing is not directly
  equivalent to exhaustive local mutmut closure.
- **Follow-up:** Determine which Python default/telemetry/platform patterns Google
  treats as arid and whether those suppressions would be sound here.

### S3 — mutmut official documentation and repository

- **Rating:** S for tool mechanics; not a general mutation-testing theory source
- **URL:** <https://github.com/boxed/mutmut>
- **Why read:** Authoritative configuration and execution behavior for the actual
  tool in use.
- **Most relevant ideas:** targeted source/test selection; remembered incremental
  work; `also_copy`; `mutate_only_covered_lines`; `type_check_command`; narrow
  mutation suppression.
- **Limitations:** documents capability, not which policy is best for this
  repository.
- **Follow-up:** Prototype a clean temporary-config runner and scoped type filter;
  verify exact mutmut 3.7 behavior against untracked files.

### S4 — DORA AI Capabilities Model 2025

- **Rating:** S for organizational/process evidence
- **URL:** <https://services.google.com/fh/files/misc/2025_dora_ai_capabilities_model.pdf>
- **Why read:** Official DORA/Google synthesis based on survey and qualitative
  research. Frames AI as an amplifier and identifies working in small batches,
  strong version control, and quality internal platforms as enabling
  capabilities.
- **Most relevant ideas:** reduce work-item size; counteract AI’s tendency toward
  large unstable changes; invest in internal platform guardrails.
- **Limitations:** organizational association data, not controlled evidence that
  a specific mutation threshold or packet size improves Python code.
- **Follow-up:** Translate “small batches” and “quality internal platform” into
  measurable repository controls rather than citing DORA as a direct proof of a
  200-line threshold.

### A1 — Equivalent Mutants in the Wild

- **Rating:** A
- **URL:** <https://dl.acm.org/doi/10.1145/3650212.3680310>
- **Why read:** Recent ground-truth study of 1,992 mutants across real projects;
  classifies equivalent mutants and evaluates targeted suppression.
- **Most relevant ideas:** common structural patterns can explain many
  equivalents; equivalent prevalence is uneven; suppression can be targeted
  rather than broad.
- **Limitations:** Java-focused; tool/operator patterns may not transfer directly
  to mutmut/Python.
- **Follow-up:** Map its equivalent categories to S3: post-`fchmod` defaults,
  inactive platform branches, and downstream normalization.

### A2 — Human-Written vs. AI-Generated Code: A Large-Scale Study

- **Rating:** A-
- **URL:** <https://arxiv.org/abs/2508.21634>
- **Venue/status:** accepted to ISSRE 2025
- **Why read:** Large comparison across more than 500,000 Python and Java samples;
  reports distinct defect, repetition, unused-construct, debugging, complexity,
  and vulnerability profiles.
- **Most relevant ideas:** AI-generated code can be syntactically simpler yet
  repetitive and semantically shallow; quality controls may need an AI-specific
  profile.
- **Limitations:** generated samples and static-analysis labels may differ from
  agent-authored maintenance work in a live repository; “AI code” is not one
  homogeneous treatment.
- **Follow-up:** Read methodology and dataset construction before using any
  reported rates in policy.

### A3 — A Study of Equivalent and Stubborn Mutation Operators

- **Rating:** A-
- **URL:** <https://dl.acm.org/doi/10.1145/2568225.2568265>
- **Why read:** Manual analysis of 1,230 mutants across 18 programs; distinguishes
  equivalent from stubborn non-equivalent mutants and shows strong operator
  differences.
- **Most relevant ideas:** operator selection affects noise and value; surviving
  mutants should not be treated uniformly.
- **Limitations:** 2014 languages/tools and scale; not mutmut-specific.
- **Follow-up:** Compare mutmut’s string/default/argument operators with the
  paper’s equivalent/stubborn operator findings.

### A4 — To What Extent Does Agent-generated Code Require Maintenance?

- **Rating:** A- as a current empirical lead; verify final venue version
- **URL:** <https://arxiv.org/html/2605.06464v1>
- **Venue/status:** EASE 2026 manuscript/preprint
- **Why read:** Tracks agent-generated files and subsequent maintenance using
  real repositories and the AIDev dataset; reports that humans perform most
  observed maintenance.
- **Most relevant ideas:** generation and long-term maintenance are different
  capabilities; low observed modification frequency does not necessarily imply
  easy-to-maintain code.
- **Limitations:** short observation window, modest selected file set, agent
  identification limitations, and placeholder DOI in the accessed manuscript.
- **Follow-up:** Locate final proceedings version, replication package, inclusion
  criteria, and confounder controls before citing conclusions strongly.

### B1 — GitClear AI Copilot Code Quality 2025

- **Rating:** B
- **URL:** <https://gitclear-public.s3.us-west-2.amazonaws.com/GitClear-AI-Copilot-Code-Quality-2025.pdf>
- **Why read:** Very large industry telemetry base and concrete duplication,
  copy/paste, moved-line, and churn hypotheses.
- **Most relevant ideas:** measure maintenance behavior, not generated LOC or
  ticket throughput; track duplication/refactoring ratios.
- **Limitations:** proprietary dataset/classification, observational attribution,
  commercial publisher, and limited causal identification.
- **Follow-up:** Inspect methodology appendices, provenance inference, repository
  composition, and whether conclusions survive independent replication.

### B2 — Google Cloud: TDD and AI summary

- **Rating:** B+
- **URL:** <https://cloud.google.com/discover/how-test-driven-development-amplifies-ai-success>
- **Why read:** Concise official interpretation connecting DORA findings to TDD,
  small batches, automated testing, version control, and human review.
- **Most relevant ideas:** red-green-refactor; trust but verify; AI output should
  enter guarded pipelines.
- **Limitations:** explanatory/marketing page, not the primary research report.
- **Follow-up:** Use as orientation only; cite the DORA report/model for final
  claims.

### B3 — PIT mutation testing guidance

- **Rating:** B+
- **URL:** <https://pitest.org/>
- **Why read:** Mature mutation-tool guidance emphasizing frequent mutation of
  changed code.
- **Most relevant ideas:** keep feedback close to the change; use incremental,
  focused analysis.
- **Limitations:** JVM bytecode ecosystem and PIT optimizations differ from Python
  source mutation.
- **Follow-up:** Compare PIT history/diff behavior with mutmut’s remembered state
  and design a Python-equivalent workflow.

---

## 10. Evidence cautions

1. **Do not infer causality from broad AI adoption correlations.** Team process,
   codebase age, task selection, model, language, review practice, and developer
   experience are confounders.
2. **Do not treat AI-generated code as one category.** Autocomplete, chat,
   autonomous agents, and human-edited drafts have different provenance.
3. **Do not equate fewer later edits with maintainability.** Code may be stable,
   unused, avoided, or difficult to modify.
4. **Do not equate mutant count with defects.** It measures mutation opportunity
   under a tool/operator set.
5. **Do not equate raw mutation score with test quality.** Equivalent, invalid,
   redundant, and low-value mutants distort the denominator.
6. **Do not import thresholds from Google/PIT unchanged.** Their infrastructure
   and economics differ.
7. **Local S3 is one case.** It is useful for mechanism discovery, not population
   inference.

---

## 11. Draft recommendation for the next plan

Before S4 or another large AI-authored production slice, consider a bounded
process/tooling slice with no runtime product change:

1. amend `feature-planning` with mutation-surface and small-batch gates;
2. amend `tests-writing` with mock-seam and sequential-state rules;
3. trigger `mutation-clearing` before first mutation, not only after survivors;
4. build a safe untracked-file-aware slice mutation runner;
5. benchmark scoped type filtering and covered-line filtering;
6. decide permanent readiness-module mutation scope;
7. define a reviewed equivalent-mutant ledger format;
8. run S4 in micro-packets and record time-to-feedback versus S3.

Candidate standing instruction:

> Work in mutation-gated micro-slices. Before coding, identify one authority for
> every policy-bearing value and prohibit independently supplied derivable
> fields. After each first-green production packet and before the next consumer,
> run targeted mutation testing. Stop on any non-equivalent survivor, more than
> 20 unclassified survivors, or a cluster of three repeated mutation shapes.
> Refactor production policy before adding implementation-mirroring tests. Final
> acceptance requires zero non-equivalent and zero unclassified survivors, with
> equivalent mutants explicitly proven.

---

## 12. Re-research checklist

A future researcher should:

- retrieve final versions/DOIs for 2025–2026 preprints;
- read methods and threats-to-validity, not abstracts only;
- locate replication packages where available;
- compare AI provenance definitions across studies;
- extract DORA’s exact small-batch measurement instrument;
- inspect Google’s arid-node and productivity definitions;
- inventory mutmut 3.7 operators against S3 equivalents;
- test type filtering on a clean isolated module;
- measure mutation runtime with cached versus fresh mutant trees;
- compare all-mutant, covered-line, changed-line, and one-per-line strategies;
- design a small First-Agent experiment before changing permanent CI policy;
- separate maintainability metrics from correctness/security outcomes;
- review whether new exact-plumbing tests create excessive refactor coupling.

---

## 13. Provisional conclusion

The S3 evidence supports a narrow conclusion:

> Thorough planning and live-path tests can prove that AI-authored code is wired
> and behaviorally correct while still allowing an unnecessarily large internal
> mutation surface. The best corrective mechanism is not simply more tests; it
> is earlier mutation feedback combined with design compression, single-source
> policy, restrictive test seams, and a reliable internal mutation platform.

Whether the proposed thresholds and permanent CI controls generalize beyond S3
remains an open empirical question for the next research and planning pass.
