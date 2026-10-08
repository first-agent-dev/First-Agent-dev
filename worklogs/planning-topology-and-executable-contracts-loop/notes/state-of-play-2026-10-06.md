# State of play — session 2026-10-06 (context bank, working note)

**Purpose.** My reading notes + verified drift report for this session. Not a plan.
Everything below marked `[verified @ HEAD]` was re-run against
`2f6b8c15e94ef361f35382f76115dc7cac77e79a` (merge of PR #69, 2026-09-10) in this sandbox.

---

## 1. What the project is (one screen)

**First-Agent (FA)** — a locally orchestrated, mixed-tier LLM coding agent for a single
power-user. Deterministic harness, zero-trust LLM isolation (API keys live only in the
`fa-egress-proxy` container), repo mounted read-only, work happens in managed git clones.
Per-run state authority = SQLite `session.db`; JSONL is a mirror. Roles: **planner /
coder / eval**, plus a **chat** orchestrator role; the loop is driven by a **code-owned
controller** (`src/fa/inner_loop/workflow_controller.py`).

**This project (`RM-planning-topology`)** rebuilds that role loop around:
- a locked four-tier planning topology — feature → increment → `SLICE#` → `STEP#`;
- **executable contracts** — the planner authors each slice's test; the harness proves it
  non-vacuous (fail-before / pass-after);
- a **deterministic verify gate** — exit code = fact, eval verdict = judgment;
- an append-only **EVIDENCE ledger** so each increment is smarter than the last.

It **supersedes** `worklogs/implementation-plans/PLAN-slice-ceremony-harness-enforcement.md`
(27 chapters, ~198 KB), which collapsed at its S15 eval-verification roadblock.

Theory source: `knowledge/research/PRODUCTION-NOTE-planning-big-tasks-for-ai-agents.md`
(1,623 lines, ~60 cited papers; findings F1–F12, backlog of 18 items in 3 tiers, §5 rates
all six locked decisions "supported"). Adoption filter:
`notes/RESEARCH-ADOPTION-PLAN.md` (13 adopted & ranked, 5 deferred).

---

## 2. Document map (what each file is for)

| File | Role | Key content |
|---|---|---|
| `roadmap.md` | index | 6 increments I01–I06, 9 standing decisions, 5 deferred items, absorbed-from-superseded mapping |
| `ledger.md` | EVIDENCE, append-only | E1–E48; 4 waves: original facts (E1–E21), I01 review (E22–E28), readiness pass (E29–E37), verify-gate bank (E38–E40), operator conformance round (E41–E48) |
| `increments/increment-01-plan-grammar-and-extractor.md` | the only detailed increment | 4 slices, 18 CT#s, status `READY` |
| `notes/artifact-schema-and-grammar.md` | canonical grammar | §1 artifacts+ownership, §2 roadmap, §3 increment, §4 slice grammar, §5 ledger grammar, §6 status vocabularies, §7 extractor surface |
| `notes/verify-block-design.{md,svg}` | I02 design | four-phase ritual (pre-check → baseline → fail-before → pass-after) + seven-row truth table + two postures |
| `notes/i02-handoff-verify-gate.md` | I02 context bank | grounded facts, the I01→I02 contract boundary, **7 open questions**, "must not leak" list |
| `notes/role-prompts-conformance.md` | prompt deltas | exact insert text, banked not merged; planner→I01, coder→I03, eval→I04 |
| `notes/RESEARCH-ADOPTION-PLAN.md` | adoption ranking | 18 research items filtered to 13 + 5 deferred; §5 "more structure is not more success" caveat |

**Increment map:** I01 grammar+extractor · I02 executable contracts + verify gate ·
I03 per-slice loop/tracker/3-level eval · I04 ledger + pinned invariants + retry hygiene ·
I05 rolling-wave, ASK#, autonomy, chat orchestration · I06 telemetry + distillation.
Deferred: #10 escalation ladder, #11 slice DAG + worktrees, #15 distillation ritual,
#16 hash-anchored run record, #18 model tiering.

---

## 3. Verified repo state @ HEAD (the drift)

HEAD = `2f6b8c1`, merge of PR #69 (`arena/01a0762b`), merged 2026-09-10. The PR's **last
commit is `c0a8f429 "planning-topology-and-executable-contracts-loop I01 Slice1"`** — so
I01/SLICE1 **shipped** with the planning docs.

**Implementation status of I01:**

| Slice | Status @ HEAD | Evidence |
|---|---|---|
| SLICE1 — grammar tokens + `slice_records` | **IMPLEMENTED** | `plan_ids.py:55` `_SLICE_RE = ^#{2,4}\s+SLICE(\d+[a-z]?)\s*:`; `_STEP_RE`, `_CONTRACT_CLASS_RE`, `_STEPS_MODE_RE`, `_TESTS_LINE_RE`, `_INTENT_LINE_RE` all present; `SliceRecord` frozen dataclass at `:107`; `PlanIds.slice_records` at `:143`; `tests/test_plan_ids.py` grew 279 → 367 lines, all `### Step S#` gone, `test_workflow_controller_reader_input_resolves` + the CT13 grammar-collision test exist |
| SLICE2 — per-slice accessors | **NOT STARTED** | no `commands_for` / `section` / `contract_class` / `tests_for` / `steps_mode` anywhere in `src/` or `tests/` |
| SLICE3 — plan pre-check | **NOT STARTED** | `grep -rn precheck src tests` → empty; `tests/test_plan_precheck.py` absent |
| SLICE4 — skill migration | **NOT STARTED** | `knowledge/skills/plan-authoring/SKILL.md:430` still writes `### Step S#:`; `feature-planning/SKILL.md` has no slice grammar at all; `tests/test_skill_conformance.py` absent |

**Artifact drift:** `increment-01` still says `status: READY` and **every SLICE1 `STEP#`
box is unticked**, though SLICE1 landed. Per schema §6 ticks are harness-owned — and the
harness that ticks them is I03 work, so the drift is structural, not sloppiness. It still
means *the plan no longer describes reality* and a fresh reader is misled.

**Ledger staleness:** E1, E22, E29, E30 are now tombstone-worthy (they describe pre-SLICE1
`plan_ids.py` / `test_plan_ids.py`). E2/E3/E5/E39 (flat commands, zero readers, `_git_output`
collapses to `None`) are **still true** — re-verified below.

**Line anchors re-verified @ HEAD (all still correct):**
- `workflow_controller.py:332` and `:461` — the only two external `extract_plan_ids`
  callers; both read `.slices` only. `.commands` still has **zero readers**.
- `workflow_controller.py:401` `_git_output` — still collapses every failure to `None`.
- `workflow_controller.py:913` `_run_adaptive` — still loops on the whole plan.
- `prompt.py:45 / :533 / :685` — PLANNER / CODER / EVAL system prompts.
- `prompt.py:648` — coder still told to "mark it `[x]` / `[>]` / `[ ]`" (E44 delta unmerged).
- `prompt.py:~866` — judge prompt still mandates `- S1: PASS` prose (E6; the `S#` vocabulary
  survives here even though the plan grammar renamed to `SLICE#`).

---

## 4. Findings from dogfooding the extractor on increment-01 (new, this session)

Ran the shipped `extract_plan_ids` against the live increment file.

```
slices: ('SLICE1','SLICE2','SLICE3','SLICE4')
SLICE1 cts: CT1/F CT2/F CT3/CONSTRAINT CT5/F CT6/F CT7/F CT11/PRES CT12/PRES CT13/CONSTRAINT
SLICE2 cts: CT3/FUNCTIONAL CT4/F CT4b/CONSTRAINT CT4c/PRES
SLICE3 cts: CT8 CT9 CT10 /CONSTRAINT, CT10b/FUNCTIONAL
SLICE4 cts: CT14/F CT15/PRES  + CT8/F + CT11/F   ← phantom
SLICE4 section = 50 lines, runs to EOF (swallows DoD / Out-of-scope / Hand-off)
```

**F-A — last-slice section span over-captures.** `_slice_sections` ends a section at the
next **`SLICE` heading** or EOF, so the final slice swallows every trailing `##` section
(`Increment definition of done`, `Out of scope`, `Hand-off to I02`). Consequences: the
coder's scoped brief for the last slice leaks the whole increment tail, and the tail's CT
mentions become phantom contracts of that slice. Contradicts schema §4/CT4's intent
("exactly SLICE2's block"). Fix shape: end a section at the next heading of the same or
shallower level, not only at the next `SLICE` heading.

**F-B — CT IDs mentioned in prose become contracts of the slice.** `_section_contracts`
scans every line for `\bCT(\d+[a-z]?)\b`, so:
- SLICE1 acquires `CT3` with class `CONSTRAINT` purely from CT2's illustrative text
  ("`CT3 [CONSTRAINT]: …` parses with class CONSTRAINT");
- `CT3` therefore has **two different classes** in the same increment (CONSTRAINT in
  SLICE1, FUNCTIONAL in SLICE2) — so a `contract_class("CT3")` accessor is ambiguous today;
- `(exit: CT11 green.)` style step text re-declares contracts.
This is the exact twin of the CT13 grammar-collision trap (a documented example being read
as real), but for CT IDs rather than verify fences. Unresolved: is the fix a convention
(declare contracts only under `CONTRACTS:`), a parser change (only parse the `CONTRACTS:`
block), or a pre-check WARN?

**F-C — schema §7 promises an API that I01 does not contract.** §7's read API lists
`contract_class`, `tests_for`, `steps_mode`, and `precheck`. increment-01/SLICE2 only
contracts `commands_for` (CT3) and `section` (CT4); SLICE3 contracts pre-check *behaviour*
but names no function. So three of the five accessors would ship uncovered, or not at all.

**F-D — dangling source reference.** `roadmap.md` §Sources cites
`PLANNING-TOPOLOGY-EXPLAINED.md`; **no such file exists in the repo**
(`PRODUCTION-NOTE…` §2 says it "condenses" that design doc, so the content survives, but
the pointer is dead).

**F-E — stale line anchors inside increment-01.** SLICE1/STEP3 names
`tests/test_plan_ids.py:34, :38, :63, :159, :181, :202, :212, :258`. Those were pre-SLICE1
coordinates; the migrated file is 367 lines and the anchors moved (`:213`
`test_this_plan_is_conforming`, `:264` `test_real_plan_yields_its_own_verification_commands`).
Harmless now (the step is done) but a trap if the file is re-read as instructions.

---

## 5. Open questions already banked (do not re-derive)

`notes/i02-handoff-verify-gate.md` §4 — 7 questions for the I02 review: (1) per-command vs
per-test granularity; (2) `(NEW)` prose marker vs machine token; (3) baseline storage path +
lifetime; (4) result dataclass shape and home (`verify.py` vs `plan_ids.py`); (5) per-command
timeout; (6) the S16 `.commands`-removal collision (E37); (7) per-run vs global baseline for
regression attribution.

Schema §7 defers one grammar decision to I02: per-`CT#` test attribution
(`CT3 [CONSTRAINT] (test: test_identical_401): …`) — E27.

---

## 6. The three documents from the previous session (fetched from `origin/main` @ `aeb025f`)

Commit `aeb025f "review notes upload"`, +1,423 lines, three new files in `notes/`, nothing else
changed. Cherry-picked onto this branch.

### 6.1 `REVIEW-planning-big-tasks-for-ai-agents.md` (571 ln, 2026-09-11)

An independent **citation audit + production review** of the research note. 83/83 arXiv IDs
resolve; of 42 load-bearing claims checked against primary text: 27 exact, 5 with scope caveats,
7 wrong or misleading, 1 misattributed, 1 unlocatable. Verdict: *"the architecture is sound and
I would build most of it"* — all six locked decisions survive, four clean keeps, two need
structural additions.

Four production problems the note is silent on: **no reliability budget** · **no
adversarial-integrity model** · **N-version cites the rebutted side of a settled argument** ·
**review capacity never priced**. One methodological root cause: arXiv IDs cited **without
versions** — the most load-bearing table is a faithful transcription of a *superseded* preprint
whose current version reverses the conclusion.

### 6.2 `ARCHITECTURE-REVIEW.md` (443 ln, 2026-09-11)

A second independent review, same subject, same date, different reviewer. 84/84 IDs resolve;
verification worked from abstracts + 16 outside searches rather than full texts. Verdict: *"adopt
the architecture, change the substrate."* Endorses 5 of 6 locked decisions unqualified. Adds
**G1–G15** cross-cutting production gaps and **T1–T4** internal tensions. Its headline:
**G1 — markdown-regex is not a storage substrate** (schema-first records, markdown as a rendered
projection) — which is aimed squarely at what I01 is.

Three changes it calls non-negotiable before production: schema-first artifacts (G1),
eval-held-out tests + `TEST-DEFECT` route (G6), sandboxing + test immutability (G5).

### 6.3 `first-agent-bridge.md` (409 ln, Russian)

The operator's **working brief for this session**: project map, a verified "promised vs actual"
table, the editing rules for these artifacts, eight recommendations **R1–R8**, one open question
(**ASK#-01**, two plan formats), a concrete proposed diff (`SLICE1b`, `SLICE5`, roadmap rows,
ledger E49–E57, a rationale note), an acceptance checklist, and ready-to-use prompt blocks for
coder / failure-packet / GIVEN.

Stated session output: *a unified diff over `worklogs/…`, audit-ready against the code.*

**I re-verified every row of its §2 table against the tip — all correct**, including the ones I
had not checked: `grep -c SLICE src/fa/inner_loop/prompt.py` → **0**;
`build_prompt_parts_v2` returns `(cacheable, non_cacheable)` with key
`fa-{role_id}-{hash_tools}-{hash_map}-{hash_always}`; `INJECTION_SPECS` holds exactly one spec
(`coder_slice_ceremony`); `AttemptHistory.attempt_count(tool_name, params_hash)` keys on the tool
signature and `LoopGuard`'s own docstring says *"Distinct params are progress, not thrash"*; no
`stall` anywhere in `workflow_controller.py`; `coder_loop.py:600-649` rebuilds full history from
the log DB on retry.

## 7. Working register

All findings — mine, BRIDGE R1–R8, REVIEW's and ARCHITECTURE-REVIEW's — are enumerated with
stable IDs in **`notes/findings-register-2026-10-06.md`**, including a §F listing the six places
where the two reviews disagree, and a §G with three candidate answers to the A3/A4 extractor
defects.

---

## 8. Tooling note

`uv` is not installed in this sandbox and the system Python is 3.11 (the project targets
3.13 — `src/fa/inner_loop/loop.py` imports `typing.override`). A local `.venv` (gitignored)
with pytest exists, but the package does not import under 3.11. `plan_ids.py` is stdlib-only
and can be exercised standalone via `importlib.util.spec_from_file_location` (must register
the module in `sys.modules` before `exec_module`, or the frozen dataclass fails). That is how
§4 above was produced. Full `verify` blocks cannot be run here.
