# Findings register — plan-edit session 2026-10-06

**What this is.** Every actionable finding from the four inputs, with a stable ID so we can walk
them one by one and not lose any. **Not a plan** — no finding here is adopted until its `Status`
says so.

**Inputs:**
- **[MINE]** — dogfooding the shipped extractor + re-verifying every anchor @ `2f6b8c1` (this session).
- **[BRIDGE]** — `notes/first-agent-bridge.md` (R1–R8, ASK#-01, proposed diffs, E49–E57).
- **[REV]** — `notes/REVIEW-planning-big-tasks-for-ai-agents.md` (citation audit + production review).
- **[ARCH]** — `notes/ARCHITECTURE-REVIEW.md` (claim ledger + G1–G15 + T1–T4 + per-item verdicts).

**Status vocabulary:** `OPEN` (not discussed) · `DECIDED-TAKE` · `DECIDED-BANK` (ledger/notes, not
scheduled) · `DECIDED-DROP` · `NEEDS-OPERATOR`.

**Both reviews were produced on 2026-09-11 against the same research note, independently.**
Where they disagree, see §F — those are the highest-value items to settle, because a disagreement
between two careful reviewers is exactly where our own judgement has to do the work.

---

## A. Repo-vs-plan drift and extractor defects (verified this session)

| ID | Finding | Source | Verified | Lands where (proposal) | Status |
|---|---|---|---|---|---|
| **A1** | I01/SLICE1 is **shipped** (commit `c0a8f429` in PR #69) but `increment-01` still says `status: READY` with every `STEP#` box unticked. Schema §6 says ticks are harness-owned and the harness is I03 work — so this drift is structural, not sloppiness, and will recur for SLICE2–4. | MINE + BRIDGE | ✅ | increment-01 frontmatter + ledger FACT; decide the interim tick policy | OPEN |
| **A2** | Ledger E1 / E22 / E29 / E30 describe a `plan_ids.py` and `test_plan_ids.py` that no longer exist. Append-only means they stay, but they need `supersedes:` successors or the next planner reads them as current. | MINE | ✅ | ledger append (E49–E51 in BRIDGE cover part of this) | OPEN |
| **A3** | **Last-slice section span over-captures.** `_slice_sections` ends a section at the next `SLICE` heading or EOF, so SLICE4 swallows `## Increment definition of done`, `## Out of scope` and `## Hand-off to I02` (50 lines). Effects: the coder's scoped brief for the final slice leaks the whole increment tail, and the tail's CT mentions become phantom contracts of that slice (SLICE4 gains `CT8`, `CT11`). Contradicts CT4's own wording ("heading through the line before the next `## SLICE` heading"). | MINE | ✅ dogfooded | new CT in I01/SLICE2 — or a pre-check WARN. **Three candidate fixes, see §G** | OPEN |
| **A4** | **`CT#` tokens in prose become contracts of the slice.** `_section_contracts` scans every line with `\bCT(\d+[a-z]?)\b`, so CT2's illustrative text ("`CT3 [CONSTRAINT]: …` parses with class CONSTRAINT") gives SLICE1 a contract `CT3` classed `CONSTRAINT`, while SLICE2 declares the real `CT3` as `FUNCTIONAL`. **The same CT ID carries two different classes in one increment** — so a `contract_class("CT3")` accessor is ambiguous today. Exact twin of the CT13 verify-fence trap, for CT IDs. | MINE | ✅ dogfooded | same decision as A3 (convention / parser / WARN) | OPEN |
| **A5** | **Schema §7 promises an API that no `CT#` covers.** §7's read API lists `commands_for`, `section`, `contract_class`, `tests_for`, `steps_mode`, `precheck`. increment-01/SLICE2 contracts only `commands_for` (CT3) and `section` (CT4); SLICE3 contracts pre-check *behaviour* but names no function. Three accessors would ship uncovered or absent. | MINE | ✅ | add CTs to SLICE2, or trim schema §7 | OPEN |
| **A6** | `roadmap.md` §Sources cites `PLANNING-TOPOLOGY-EXPLAINED.md`; **no such file exists in the repo.** (Its content survives as PRODUCTION-NOTE §2, which says it "condenses" that doc.) | MINE | ✅ | roadmap one-line fix | OPEN |
| **A7** | increment-01/SLICE1/STEP3 names `tests/test_plan_ids.py:34,:38,:63,:159,:181,:202,:212,:258`. Those are pre-migration coordinates; the file is now 367 lines and the anchors moved (`:213`, `:264`). Harmless (step is done) but a trap if re-read as instructions. | MINE | ✅ | mark the step done, or re-anchor | OPEN |

---

## B. The emitter / two-formats gap — the live blocker

| ID | Finding | Source | Verified | Lands where (proposal) | Status |
|---|---|---|---|---|---|
| **B1** | `grep -c SLICE src/fa/inner_loop/prompt.py` → **0**. The planner prompt emits no `SLICE#`, no `STEP#`, no `CT# [CLASS]`, no `TESTS:`. Combined with the `SLICE#`-only extractor, **a freshly authored plan parses to empty `.slices`, so `workflow_controller.py:332` early-returns and the coverage gate silently no-ops.** E23 is not archival — it is live. | BRIDGE (E51/E52) | ✅ | **BRIDGE R1: new `## SLICE1b: Emitters write the new grammar`, DEPS SLICE1** | OPEN |
| **B2** | **Two plan formats with no defined transform.** (1) the planner's runtime format (`prompt.py:171-245`): `Class/Goal/Evidence/Scope/Assumptions/Constraints/Plan/Verification/Risks`, steps `S1.` with `intent:`/`deps:`/`do:`/`accept:`/`verify:`, plan-level `focused:`/`regression:`. (2) the durable increment grammar (schema §4). Nothing says how one becomes the other. Until it is settled, "every `CT#` has a test" cannot be enforced on plans the planner actually writes. | BRIDGE §5 (E56) | ✅ | **ASK#-01**; roadmap `assumed:` + ledger `GAP`; blocks SLICE4 | NEEDS-OPERATOR |
| **B3** | **Refinement of B2 (new this session):** the planner's `S1.` items are **step-sized** (they carry `accept:`/`verify:`, one mechanical predicate each), not commit-sized. So the honest mapping is `S#` → **`STEP#`**, which leaves `SLICE#` with no source in the runtime format at all. A "compile the runtime plan into the increment grammar" step must therefore *invent* the slice tier (group steps into commits) — that is a judgement, not a transform. This is the real content of ASK#-01 and it decides between BRIDGE's option (a) and (b). | MINE | ✅ `prompt.py:216-232` | feeds ASK#-01 | OPEN |
| **B4** | The eval prompt (`prompt.py:~866`) still mandates `- S1: PASS` prose, and `validate_slice_ids` canonicalises `S1`→`SLICE1`. So the eval's `S#` vocabulary is simultaneously the planner's *step* vocabulary and the controller's *slice* vocabulary. E7's original "`### Step S#` conflates slice and step" survives in the prompts even though the plan grammar renamed. | MINE + BRIDGE | ✅ | banked in `role-prompts-conformance.md`; owner = I03 per E47 | OPEN |

---

## C. BRIDGE recommendations R1–R8

| ID | Finding | Source | Lands where (as proposed) | Status |
|---|---|---|---|---|
| **C1** | **R1 — reorder I01: insert `SLICE1b` "Emitters write the new grammar"** right after SLICE1; retarget SLICE4's `DEPS: SLICE1, SLICE2, SLICE3` → `DEPS: SLICE1b, SLICE3`. New CT16/CT17/CT18, new `tests/test_skill_grammar_emit.py`. Rationale: the path planner-writes → extractor-parses → controller-sees needs only SLICE1, and it is the cheapest thing that restores the controller's hearing. | BRIDGE | increment-01 | OPEN |
| **C2** | **R2 — new `SLICE5`: pinned invariants, byte-stable, re-injected every call.** CT19; `tests/test_injection_pins.py`; one `InjectionSpec` row + one `FeatureFlags` field. Verified cheap: the channel exists and holds exactly one spec today. Also protects the role prompt-cache prefix. | BRIDGE (adoption #7) | increment-01 | OPEN |
| **C3** | **R3 — role-prompt edits** (coder: drop duplicated gate, add recon budget + stop conditions; eval: L1 in code; planner: mechanical self-check items move into the pre-check). Full insert text in BRIDGE §8A. | BRIDGE | stay **banked** in `role-prompts-conformance.md`; implement in owning increment (E47) | OPEN |
| **C4** | **R4 — attempt counter keyed by `STEP#`/`CT#`/`accept:`.** Verified gap: `AttemptHistory.attempt_count(tool_name, params_hash)` keys on *tool signature*; `LoopGuard` explicitly treats distinct params as progress ("Distinct params are progress, not thrash" — its own docstring, after S12.7 removed the thrash detector). So "three different failed fixes for one contract" is invisible. No `stall` anywhere in the controller. | BRIDGE | I02 (beside the gate) | OPEN |
| **C5** | **R5 — distilled failure packet (≤15 lines), never the raw transcript.** Verified: `coder_loop.py:600-649` rebuilds full history from the log DB on retry — exactly the F3 self-conditioning shape. Packet template in BRIDGE §8B. | BRIDGE (adoption #6) | I03 | OPEN |
| **C6** | **R6 — GIVEN compiler from the ledger** (FACT entries → "already verified, do not re-derive" prompt block). Note the real wrinkle BRIDGE flags: ledger anchors are heterogeneous (`@ arena/01a0762b` is a *branch*, `@ 0e08ece` a *commit*) → resolve branch→SHA, skip unresolvable. Template in BRIDGE §8C. | BRIDGE (adoption #4/#7) | I04 | OPEN |
| **C7** | **R7 — tie `STEPS: prescriptive\|outcome` to the existing TRIVIAL/STANDARD/LARGE classifier** (`prompt.py:93-109`). No new slice needed — fold into SLICE4/STEP2, which already says "add authoring guidance for … `STEPS:` mode". | BRIDGE (adoption #3) | increment-01 SLICE4 | OPEN |
| **C8** | **R8 — keep the cacheable prompt part byte-stable; measure hit rate.** Verified: `build_prompt_parts_v2` already returns `(cacheable, non_cacheable)` with key `fa-{role_id}-{hash_tools}-{hash_map}-{hash_always}`, and its own docstring warns that per-task variation destroys prefix reuse. Extend `tests/test_prompt_caching_per_role.py`. | BRIDGE | — (standing constraint) | OPEN |
| **C9** | **BRIDGE §6.3 — ledger appends E49–E57** (shipped state, emitters, no-op gate, cache, injection channel, attempt counting, the two-formats GAP, the reorder DECIDED). All nine re-verified by me this session. | BRIDGE | ledger.md | OPEN |
| **C10** | **BRIDGE §6.2 — roadmap edits**: extend I02/I03/I04 one-liners; add the `assumed:` standing decision for the two-formats transform; add a Deferred row for prompt-side effort routing (`reasoning.effort` per slice class — "a different lever from prose; must be measured in its own arm"). | BRIDGE | roadmap.md | OPEN |
| **C11** | **BRIDGE §6.4 — new `notes/plan-edit-…-rationale.md`** to hold the reorder rationale, because E48/schema §1 forbid rationale inside plan bodies and the ledger. | BRIDGE | notes/ | OPEN |
| **C12** | BRIDGE §3 warns: new files in `notes/` may trip the two **deliberately-red** doc gates (`test_doc_links`, `test_historical_workspace_docs_have_top_level_superseded_banner`, E19). Warn the operator, never "fix" them. | BRIDGE | standing constraint | OPEN |

---

## D. REVIEW (citation + production review) — findings

### D-a. Problems in the research note itself (would change what we build on)

| ID | Finding | Status |
|---|---|---|
| **D1** | **F1's "harness changes move benchmarks up to 15 points" does not exist in 2608.23953.** The paper is a qualitative N=3 case study with no benchmark claims. The *thesis* ("this layer, not the model, is the binding constraint") is verbatim in the abstract; the **number is invented**. F1 is the finding that sets the whole "invest in the harness" priority. (ARCH independently corroborates the magnitude from outside: LangChain harness rebuild +13.7pp same-model.) | OPEN |
| **D2** | **The architecture census (§4D) is a faithful transcription of a superseded version** (2506.17208**v1**). In v3, G3 (scripted multi-agent) has both the highest median (63.4%) and max (75.2%); the note's conclusion "minimal roles plus strong scaffolding wins on medians" is **contradicted**. Also: the p=0.0070 result was never a G4-vs-G5 pair even in v1, and in v3 the Lite board is not significant (p=0.0579). **The corrected data still supports our design** (planner→coder→eval with a code-owned controller *is* G3) — but for the opposite reason. | OPEN |
| **D3** | **MAST percentages match no version of 2503.13657.** FM-2.2 "unasked assumptions" — the primary justification for the ASK# channel (#13) and the `GUESS`→`ASK#` rule — is **6.80%** in v3, not 11.7%. ⚠️ **ARCH disagrees** (says 11.65% confirmed in v2 body text) → see **F1**. | OPEN |
| **D4** | **METR's "8.1 points per messiness factor" is a mischaracterisation.** It is b = −0.081 with **R² = 0.251** on a 16-factor composite, explicitly footnoted as a rough linear approximation. Not a per-factor planning coefficient. | OPEN |
| **D5** | **SWE-bench Pro "~23% best" is ~2× too low** per 2509.16941**v2** (Sonnet 4.5 43.6%). ⚠️ **ARCH confirms the 23% against v1** → see **F2**. | OPEN |
| **D6** | Two smaller errors: AWM's +24.6% is **Mind2Web** not WebArena; ReWOO is **5× token efficiency (≈80% cut)**, not 64%. | OPEN |
| **D7** | **Systematic A-grade inflation on out-of-domain evidence** (MAST, 2402.01817's 12%, HoH ablations, SWE-agent layout, TDP, VeriMAP should all be B). ARCH proposes the same fix mechanically as **"A⁻ (transfer)"** — see E19. | OPEN |
| **D8** | **Root cause + rule:** the note cites arXiv IDs **without version or retrieval date**. Proposed standing rule for every future research note: cite `{id}v{N}, retrieved {date}`; mark each claim abstract/body/table; quote the *exact sentence* for any claim that drives a locked decision; put a 90-day re-check date on benchmark-derived claims. Six of eight errors would have been caught by the quote rule. | OPEN |
| **D9** | **The §8 goalposts table is already stale** (SWE-bench Verified ~96% saturated; the frontier moved to Pro / Terminal-Bench 4.0 at ~57.9%). Demote §8 from "goalposts" to "context"; judge on pass^k over our **own** held-out slice-regression set. | OPEN |

### D-b. Production problems the note is silent on

| ID | Finding | Status |
|---|---|---|
| **D10** | **No reliability budget.** `s = 1 − (1−p)(1−q)²`; a 20-slice feature at s=0.900 completes autonomously **12%** of the time; 90% feature-completion at 20 slices needs **s = 0.995 per slice**. Backed by METR's own Jan-2026 follow-up ("reliability-critical tasks require 98%+ success probabilities"). Three asks: declare a target and instrument against it; make slice *count* a controlled variable derived from the budget (it dominates — and it pulls **against** F7's sizing cliff, which the note never notices); budget human touches explicitly. | OPEN |
| **D11** | **Verification integrity is a security problem, treated as a grammar problem.** Nothing stops the coder editing the planner's test file. Evidence: UC Berkeley agent scored 100% on three benchmarks without solving a task; SWE-bench Pro Verified's four hacking channels (−171/731 passes under controls); Cursor's 63%-retrieval-not-derivation finding (sealing git+egress: 87.1%→73.0%); RewardHackingAgents (tampering and leakage are *independent*, partial defences fail). **Five controls:** read-only `TESTS:` paths · verify in a sandbox the coder cannot write · hash the verification surface at baseline and re-check at the gate · seal `.git`+egress for benchmark runs · a derivation-vs-retrieval telemetry category. ⚠️ **ARCH says exactly the same (G5 + item 1(b)) — this is the strongest convergence between the two reviews.** | OPEN |
| **D12** | **N-version repair cites the wrong side of a settled argument.** 2411.17501 (Stroebl/Kapoor/Narayanan) proves resampling against an **imperfect** verifier cannot reduce false-positive probability; optimal K often ≤5 and K=0 when a false positive costs 10× a true positive; false positives also show "poor adherence to coding style conventions" — i.e. the same population SWE-Gate measured at 34.3%. **Re-specify as N-version *diagnosis*:** keep parallelism for divergence information, drop verify-pass as the selection rule; if selecting, rank on CONSTRAINT satisfaction first; cap k=3. ⚠️ **ARCH partially disagrees** (keeps selection, adds an eval-L2/L3 Goodhart guard) → see **F3**. | OPEN |
| **D13** | **Review capacity is never priced.** Google Cloud CTO (Apr 2026): the constraint moved downstream to human review; AI PRs average ~1.7× more issues; volume 3–5× against a fixed review rate. Asks: a **PR-brief artifact as a first-class output** (the single biggest lever on human gate latency — the note has one line, "HARNESS composes the PR from the tracker"); a human-throughput model in the scheduler; a shared-file serialisation guard; **do not build parallel slices (#11) until human gate latency is measured**. | OPEN |
| **D14** | **Add mutation-based non-vacuity to item 1.** Fail-before/pass-after proves the test is sensitive to *the change*, not to *the behaviour*. Evidence: a 22,374-task study found >99% of tests that failed on mutated code passed on the original; MutGen 53%→89.5%; Gemini 2.5 Pro 87% mutation score with full context vs a 44% practitioner baseline; all evaluated LLMs "systematically omit robustness tests for special values (None, inf, NaN)" → the pre-check should require ≥1 boundary test per FUNCTIONAL contract. ⚠️ **ARCH calls full per-slice mutation "overkill"** → see **F4**. **Note: this repo already has mutation tooling** (`scripts/run_slice_mutmut.py`, `count_mutants.py`, `mutation_sweep.py`) — the cost argument is weaker here than in general. | OPEN |
| **D15** | **Make the ≤3-slice fast path first-class.** "The tiers collapse gracefully" is the weakest sentence in §2 — field evidence (Böckeler on Kiro/Spec Kit/Tessl; 2026 Kiro review) says ceremony is **fixed-cost**, not proportional. A ≤3-slice feature should get one flat plan with contracts and no increment layer. | OPEN |
| **D16** | **Add a "decision surface" to each slice brief** — the small set of choices this slice may *not* make unilaterally, drawn from the roadmap ADR tier and prior slices' ledger FACTs. This is the answer to the strongest objection to scoped context (Cognition: "actions carry implicit decisions, and conflicting decisions carry bad results"; concretely: SLICE2 picks an error envelope, SLICE3 picks another, both pass their own contracts). ~20 lines in the brief template. | OPEN |
| **D17** | **Add a 4th reason the planner writes the steps: recoverability.** "A plan the harness can parse is a plan the harness can resume." Reasons 1–3 are about auditability; this one is operational and survives model upgrades. | OPEN |
| **D18** | **Flake classification must be measured, not defined.** "A pytest command with fixed input does not flake by definition" is false in real repos. Run the verify command k times at baseline and record observed variance — one line in the pre-check, and it turns item 12's definitional claim into a measurement. | OPEN |
| **D19** | **Judge calibration + family error direction.** AgentRewardBench: best LLM judges ~70% precision (≈30% of "successful" trajectories were failures); rule-based 83.8%/55.9%. MobileJudgeBench: GPT-family judges over-produce **false negatives**, Qwen-family over-produce **false positives** — switching family changes the *direction* of the error, it does not remove it. Also: the self-preference citation (2410.21819) attributes bias to **perplexity** regardless of self-generation; use 2404.13076 for the family argument instead. ⚠️ Convergent with ARCH G10. | OPEN |
| **D20** | **Pre-check additions** (REVIEW promotes item 5 from #5 to #2): (a) `TESTS:` paths are not in the coder's writable set; (b) predicted file sets of parallel slices do not intersect; (c) baseline flake measurement (D18). | OPEN |
| **D21** | **Cap artifact volume per slice** — a hard token budget (~1.5–2K of instruction, excluding file views). If the planner can't express a slice in it, the slice is too big → the budget becomes a **sizing mechanism**, not a style rule. And: do not rely on prose compliance; everything that must be true about the plan should be a machine assertion (the note's own principle 13, applied to its own artifacts). | OPEN |
| **D22** | **Production hazards from Phoenix that the note drops:** provider WAF content-filtering on long tracebacks (directly hits the failure-packet design — strip tracebacks, summarise fenced blocks); auth-token expiry during multi-hour runs; CI permission boundaries; per-installation concurrency lock. Plus: **no prompt-injection threat model** — the coder reads repo content, issue text, dependency READMEs and test output, all attacker-controlled. | OPEN |
| **D23** | **REVIEW's three-phase build plan with exit criteria and mandatory ablations.** Phase 1 exit: on 20 hand-written slices, the gate rejects ≥95% of patches that pass functional tests but violate a stated constraint (a direct measurement against SWE-Gate's 34.3%). Phase 2 exit: 10 real features, reported against the reliability budget — *the target is calibration, not a success rate*. Phase 3 exit for parallelism: zero merge conflicts, zero isolation collisions, human gate time no worse than serial. And the governing rule: **ablate before granting permanence**. | OPEN |
| **D24** | **The decision REVIEW would revisit at the end of phase 2:** whether four tiers is right at all. If measured per-slice success lands near 0.90, the arithmetic says fewer, larger slices with more human checkpoints — not more structure. "Be willing to be wrong about locked decision #1." | OPEN |

---

## E. ARCHITECTURE-REVIEW — findings

### E-a. Corrections to the research note

| ID | Finding | Status |
|---|---|---|
| **E1** | **`2206.10498` is PlanBench, not "LLM-Modulo."** The note writes "LLM-Modulo (2206.10498 and its companion 2402.01817)" — reversed; the framework is introduced in 2402.01817. One-line fix, no evidentiary damage. | OPEN |
| **E2** | **MAST version drift**: arXiv v1 (1600+ traces, "MAST-Data") vs NeurIPS camera-ready (1000+, renamed MAD). A body excerpt shows step repetition at **37.17%** in a per-system figure vs the note's 17.1%. Needs a pinned-version PDF recheck. | OPEN |
| **E3** | **StateM's 95.3% is a tuned-system ceiling**, above the public Terminal-Bench 2.1 max (~91.9%): "raw accuracy across 445 trials" with benchmark-specific runbooks — arguably task knowledge, not harness. Treat as an *existence proof of harness headroom*, not a transferable expectation. The F1 conclusion survives via independent evidence (LangChain +13.7pp same model). | OPEN |
| **E4** | **"The coder never writes its own acceptance" is overstated once the planner authors both spec and tests.** Principle 8 (separate authorship from acceptance *at every level*) is then violated at the **planner** level. ARCH calls this its most important methodological correction. | OPEN |
| **E5** | **A⁻ (transfer) grading rule** — mechanically re-render environment-transferred A grades (Plan-and-Act, TDP, Context-folding, More Agents) as `A⁻ (transfer)`; native-SWE evidence (HoH, SWE-Gate, SWE-bench Live, Agentless, Phoenix, τ-bench, MAST, SWE-agent) keeps `A`. Nothing changes except honesty — **and the ablation priority: A⁻ items get measured first.** | OPEN |

### E-b. Cross-cutting production gaps G1–G15

| ID | Gap | Note for *our* repo | Status |
|---|---|---|---|
| **E6** | **G1 — markdown-regex is not a storage substrate** *(ARCH's highest-risk item and its "highest-leverage engineering change")*. Fix: source of truth = validated structured records (schema'd JSONL/SQLite), with `roadmap.md` / `increment-*.md` as rendered **projections**; LLM roles emit against the schema with validation + one repair retry. Accept: property-test the record→render→parse→record round trip + a fuzz corpus of observed planner outputs; **zero silent mis-parses**. ⚠️ **This directly challenges the premise of I01** (which is a regex extractor over markdown) — and findings **A3/A4 are live instances of exactly the failure class G1 predicts.** | OPEN |
| **E7** | **G2 — positional numbering rots cross-references.** `SLICE2`/`STEP3` are positions, but item 9 rewrites sections and DEPS/ledger/ASK# link by name. Fix: stable keys frozen at creation (`I1-S2`), ordinal display-only, foreign-key validation in the pre-check. *Partially mitigated already:* the grammar allows letter suffixes (`SLICE1b`), which is exactly what BRIDGE R1 uses to insert without renumbering. | OPEN |
| **E8** | **G3 — no plan-vs-tree freshness check.** Planner-once assumes the tree at slice time equals the tree at plan time. Fix: record `tree_hash + HEAD SHA + touched-paths hash` at plan time, re-check at slice start, scoped re-ground or STALE-SPEC on mismatch. | OPEN |
| **E9** | **G4 — the controller itself is not durable.** Artifacts are durable; controller progress (which slice, which ladder rung, streaks) is not. Fix: event-sourced controller state, idempotency keys on every side effect. Accept: `kill -9` at five phases, resume completes exactly once. *Our repo has `session.db` as per-run authority — partially present, worth checking before adopting.* | OPEN |
| **E10** | **G5 — planner-authored verify commands are unaudited RCE.** The `verify` block is LLM-authored shell the harness runs with repo + network + secret access, and repo content is itself prompt-injection surface. Fix: sandbox exec (no network by default, secret-less env, CPU/mem/time limits) + an item-5 command policy (allowlisted runners, repo-contained paths, deny network/privilege/outside-worktree writes/test-file writes) + a provenance log. *Our repo already has the egress proxy (ADR-12), workspace isolation (ADR-13) and the bash IntentGuard — so this may be largely covered; **needs an explicit check**.* ⚠️ Convergent with D11. | OPEN |
| **E11** | **G6 — planner-authors-tests breaks authorship/acceptance separation.** Fix: (a) **eval-held-out tests** — a small coder-blind suite per slice, authored on the eval's model family from INTENT+CT#, run only at the gate (20–30% of planner-test count, focused on CONSTRAINT + composition edges); (b) **`TEST-DEFECT` route** — "the test is wrong" must be a first-class verdict with its own budget, not something that burns repair attempts (defect-driven-gaming research shows hacking concentrates on tasks with defective test infra); (c) CONSTRAINT rationale lines (one line per test: what wrong implementation it catches). Accept: the held-out suite catches ≥1 planner blind spot per feature. | OPEN |
| **E12** | **G7 — parallel safety must be verified, not planner-asserted** (disjoint write-paths incl. TESTS and migrations/registries; tree-hash-pinned bases; dependency-ordered merges with per-merge verify). Convergent with D13's serialisation guard. | OPEN |
| **E13** | **G8 — the ledger will eat the context window it was built to save.** Fix: bounded reads (full read ≤~8K tokens, else top-k retrieval + all PRESERVE + all open GUESS/GAP) + a GC policy (FACT→ADR promotion at feature close; FAILED expiry; GUESS must resolve or escalate) + enforced write permissions (coder proposes, never writes). Context-rot evidence makes unbounded ledger reads a **reliability bug**. *Our ledger is at E48 and already 168 lines.* | OPEN |
| **E14** | **G9 — planner-declared RISK is optimistic by construction.** Harness-enforced rule-based floor: auth/crypto/permissions/billing/migrations/network-policy → ≥elevated regardless of tag; planner may escalate, never de-escalate. | OPEN |
| **E15** | **G10 — the eval is uncalibrated.** k=2 agreement measures stability, not validity. Fix: human-labelled calibration set (≥100 verdicts, quarterly), precision/recall tracked on REPAIR/REPLAN, re-calibrate on any eval-model change. Gate: eval precision on REPAIR ≥0.8 before k=2 verdicts can auto-merge routine slices. Convergent with D19. | OPEN |
| **E16** | **G11 — skill-registry rot** (versioning, usage counting, deprecation/GC, retrieval-precision measurement before the registry is load-bearing). Relevant to this repo's `knowledge/skills/` and the Pillar-4 self-authored-skills goal. | OPEN |
| **E17** | **G12 — human concurrency policy.** Per-increment integration branch, rebase-at-close with re-verify, "a human touched my paths" notification. | OPEN |
| **E18** | **G13 — no cost/latency model.** The design is eval-heavy *by principle* (frontier different-family eval × k=2 × per-slice + objective + regression + N-version + planner-premium). Publish a €/$-per-slice model and a graceful degradation order (N-version → retry; k=2 → k=1+samples; frontier → cheap), ledger-logged, never silent. | OPEN |
| **E19** | **G14 — secrets/PII flow through prompts and records** (diffs → eval prompts → a *second vendor's* API = data egress to another processor; diffs+prompts → the permanent record). Fix: redaction pass on record writes, eval-context minimisation, vendor/DPA review for the eval family. *Our repo has gitleaks + the egress proxy + ADR-12 secret isolation — likely strong already; the new surface is the cross-family eval.* | OPEN |
| **E20** | **G15 — buy-vs-build.** GitHub Spec Kit (111k stars, 30+ integrations) ships the *shallow* SDD stack. Build only the deep half nobody ships (contract classes + non-vacuity, stall-state controller, provenance ledger, pass^k, hash-anchored records, co-evolving verifiers); adopt ecosystem seams (constitution≈ADR, hooks, MCP, CI gates, `gen_ai.*` telemetry) for the rest. Revisit yearly; delete anything the ecosystem commoditises. | OPEN |

### E-c. Internal tensions T1–T4 and locked-decision guardrails

| ID | Finding | Status |
|---|---|---|
| **E21** | **T1 — reflection playback vs self-conditioning.** Resolution: *facts* persist (ledger-typed; FACT needs a verification ref), *prose* archives to the run record and is **never replayed into prompts**. Reflexion's own bound: reflections are only as good as the failure signal, so untyped persistence of a confabulated lesson is the failure mode. | OPEN |
| **E22** | **T2 — planner authorship.** Resolved by E11 (held-out tests + TEST-DEFECT + calibration). Enforceable form of principle 8: *no role's output is accepted solely on artifacts that role authored.* | OPEN |
| **E23** | **T3 — "no LLM deciding" vs semantic triggers.** STALE-SPEC "contradiction detection" and stall "loop detection" are stated semantically; an LLM judging either *is* an LLM deciding. Resolution: **syntactic-first triggers** (path/symbol/tree-hash overlap; canonicalised failure-signature match), semantic detection stays log-only until it proves precision/recall. | OPEN |
| **E24** | **P5b — compat shim for the `S#`→`SLICE#` rename**: parse old, warn, don't fail, for one quarter. ⚠️ **This contradicts E24-in-the-ledger ("SLICE#-only, no dual grammar"), which is already shipped and pinned by a test** (`extract_plan_ids("### Step S1: legacy").slices == ()`). | OPEN |
| **E25** | **P1c / item 3 — `(auto)` steps default to harness-executed.** Any `STEP#` whose exit criterion is a pure function of repo state (file exists, migration applied, formatter clean) should be harness-run unless the planner justifies LLM execution. Agentless economics at step granularity. | OPEN |
| **E26** | **P1b — over-slicing detector:** if slice count > 7 **and** median verify time < 60s → "probably over-sliced: merge candidates" warning in the pre-check. (Pairs with D10's "slice count dominates the reliability budget".) | OPEN |
| **E27** | **Item 1(e) — baselines must be hermetic and cheap.** A full suite baseline per slice is O(slices × suite-time). Production form: baseline once per increment, cache by tree hash, scope per-slice baselining to touched paths + `TESTS:` (affected-test selection). **Directly relevant to the I02 verify-gate design, which currently says "run the slice's commands once on the untouched tree".** | OPEN |
| **E28** | **Item 5 — the pre-check must return *all* violations at once** (the planner is the expensive role; minimise round trips) and the check list itself must be **versioned** (the run record notes which pre-check version passed the plan). | OPEN |
| **E29** | **Item 2(b) — `signature_hash` needs a canonicalisation spec** (strip timestamps/PIDs/durations/abs paths, sort lines, hash; optional embedding-similarity fallback ≥0.92). Without it "identical failure twice" never fires and the skip-ahead optimisation is dead code. Shared dependency with the N-version ladder. | OPEN |
| **E30** | **Item 2(c) — flake quarantine, not just budget-burn**: pass-on-rerun → classify flake, burn budget, **and** quarantine (exclude from pass^k streaks until 3 clean passes; if it is a *planner-authored* test, that is a planner defect). | OPEN |
| **E31** | **Item 12 — resettability requirement**: any suite counted toward pass^k must run from deterministic fixtures (seeded RNG, frozen clock, isolated state), or k measures environment entropy. Also: **streak resets on any gate-input change** (new diff, new TESTS version, tree change) — a stale streak is a false VERIFIED. | OPEN |
| **E32** | **Item 8(c) — L2 verdicts must cite test IDs, not hunks** (`CT3 PASS via tests/test_x.py::test_identical_401`). Hunk citations rot on rebase; test IDs are stable and re-runnable. | OPEN |
| **E33** | **Item 4(d) / item 13 — cap blocking `ASK#` per increment** (≤5; overflow becomes `assumed:`-with-flag), and auto-promote only GUESSes a contract depends on. Prevents human-spam from an anxious planner. | OPEN |
| **E34** | **D3 guardrail — make "major drift is a REPLAN" a predicate, not a vibe:** *trivial = the diff touches only paths listed in the slice's plan section AND all CT# stay PASS AND no new file outside the listed set.* Anything else is auto-REPLAN. Harness-detectable, no LLM judgement. | OPEN |
| **E35** | **P2b — increment merge policy must be explicit: additive-only mid-feature**; breaking changes need a roadmap-level decision + human ack. **P2c** — cross-increment STALE-SPEC needs a path (the finisher's "refine roadmap" step needs the same scoped-refinement skill + `supersedes:` across files). **P6d** — the chat finisher needs a 5-item checklist, not a vibe. | OPEN |
| **E36** | **ARCH's revised build order**: Phase 0 **Substrate** (G1 schema-first + G2 stable IDs + hashed record + sandbox + telemetry schema) *before* any LLM-facing work; then the trustworthy slice loop; then the increment; then throughput; then compounding. Note this puts **G1 ahead of everything we have planned**. | OPEN |

---

## F. Where the two reviews disagree — settle these first

| ID | Conflict | Why it matters | Status |
|---|---|---|---|
| **F1** | **MAST FM-2.2.** REV: 6.80% in v3, and "none of the six numbers appear in either version". ARCH: 11.65% "confirmed in body text" of v2. | Sizes the ASK# channel (#13) and the `GUESS`→`ASK#` rule. | **RESOLVED — both reviewers are right about different versions; see below** |
| **F2** | **SWE-bench Pro best score.** REV: "~23% is ~2× too low", citing v2 (Sonnet 4.5 43.6%). ARCH: ✅ confirmed, citing v1 (GPT-5 23.3%). | Both are right *about different versions* — which is itself D8's whole point, demonstrated live. Same mechanism as F1; resolve only if the number ever drives a decision (it drives none — §8 is being demoted anyway, D9). | OPEN (low priority) |
| **F3** | **N-version.** REV: drop verify-based **selection** entirely (imperfect-verifier ceiling, 2411.17501). ARCH: keep selection, add an eval-L2/L3 Goodhart guard on the passing candidates. | Both are deferred items (#10) so it is cheap to settle on paper now and expensive to get wrong later. | OPEN |
| **F4** | **Mutation testing.** REV: add mutation-based non-vacuity to item 1 — fail-before/pass-after is "necessary and far from sufficient". ARCH: full per-slice mutation is "overkill"; use rationale lines + held-out tests + periodic hack-checks. | This is the core of the I02 gate design. **Our repo already owns mutation tooling**, which weakens ARCH's cost objection. | OPEN |
| **F5** | **Citation count.** REV: 83 unique IDs. ARCH: 84. | Trivial, but a one-command tiebreak and a sanity check on both reviewers' rigour. | **RESOLVED — see below** |
| **F6** | **Emphasis.** REV's #1 structural criticism is "this is a pipeline design, not a system design" (no cross-slice interference model, no human model, no harness failure taxonomy, no partial-value handling). ARCH's #1 is "the substrate is wrong" (G1 markdown-regex). | They are not contradictory, but they imply **different first moves**: REV says build the gate right; ARCH says rebuild the artifact layer first. Our I01 is squarely in ARCH's line of fire. | OPEN |

### F1 — resolved against primary text (2026-10-06)

**Both reviewers verified correctly, against different versions. The research note is pinned to
v1/v2 throughout.**

| Figure | v1 / v2 (`ar5iv.labs.arxiv.org/html/2503.13657`, "200+ traces") | v3 (26 Oct 2025 + NeurIPS D&B camera-ready, "1642 traces") | The note says |
|---|---|---|---|
| FM-2.2 fail-to-ask-for-clarification | **11.65%** | **6.80%** | 11.7% |
| FC1 / FC2 / FC3 category split | **41.77 / 36.94 / 21.30** | **44.2 / 32.3 / 23.5** | 41.8 / 36.9 / 21.3 |
| FM-2.3 task derailment | 7.15% | 7.40% | — |
| FM-2.1 conversation reset | 2.33% | 2.20% | — |
| trace count | 200+ | 1642 | — |

Consequences:
1. **ARCH is right** that 11.65% appears in body text (v1/v2). **REV is right** that the current
   version says 6.80% and that the note's six numbers match no *current* version. Neither
   reviewer erred; each checked a different revision and neither said which.
2. **REV's design conclusion stands:** the live justification for the `ASK#` channel (#13) and the
   `GUESS`→`ASK#` rule is **6.80%, roughly 1.7× smaller** than the note claims. Still a real
   failure mode; do not size effort around 11.7%.
3. **ARCH's "step repetition 37.17%" flag was a false alarm** — that figure is a per-system rate
   from a later table. v3's Figure 1 gives 15.7% against the note's 17.1% (v1/v2 value
   unconfirmed, same drift pattern).
4. **This is the second confirmed instance of D2's mechanism** (the Dissecting census is the
   first): the note faithfully transcribed a preprint that was later revised. **D8 (version-pinned
   citations) is therefore not a hygiene nicety — it is the single root cause behind the two most
   consequential errors found by either reviewer.** Adopt it.

### F5 — resolved (2026-10-06)

`84` unique IDs matching `2\d{3}\.\d{4,5}`; `83` matching `2[3-9]\d{2}\.\d{4,5}`. The single
difference is **`2206.10498`** — which is precisely the citation ARCH found misattributed (E1:
it is PlanBench, not LLM-Modulo).

So REV's count is an artifact of its own extraction regex (its §2 Step 1 command hard-codes
`2[3-9]`), and the ID it silently dropped is the one real misattribution in the bibliography.
**Neither review is sufficient alone** — a useful calibration on how much to trust each. It also
means REV's "83/83 resolved, 0 missing" never tested the one bad citation.

---

## G. Immediate design question raised by A3/A4 — three candidate answers

The operator asked to settle *what the correct behaviour is* before deciding where it lands.

| Option | A3 (section span) | A4 (CT# in prose) | Cost | Argument for | Argument against |
|---|---|---|---|---|---|
| **1 — convention** | author rule: the last slice must be followed by nothing, or trailing sections move into a sibling file | author rule: never write a `CT#` token outside its own `CONTRACTS:` block | zero code | matches the existing CT13 precedent (the verify-fence trap is fixed by convention + a pinning test, explicitly "more machinery than the risk warrants") | the plan we already wrote violates both rules, and prose cross-references (`(exit: CT11 green.)`) are genuinely useful to a human reader |
| **2 — parser** | end a section at the next heading of the **same or shallower level**, not only at the next `SLICE` heading | parse contracts **only** from the `CONTRACTS:` block (prose mentions become non-declaring references) | ~15 lines in `plan_ids.py` + tests | removes a whole silent-mis-parse class rather than documenting it; makes `contract_class()` well-defined (A5); it is exactly the "zero silent mis-parses" standard ARCH/G1 asks for | adds parser surface to a module whose stated virtue is being total and dumb; the `CONTRACTS:`-block rule needs its own boundary definition |
| **3 — pre-check WARN** | WARN when a slice section contains a non-`SLICE` `##` heading | WARN when a `CT#` appears in a slice that does not declare it | lives in SLICE3, already planned | keeps the parser dumb; surfaces the trap to the author at $0; consistent with "pre-check forgiving, verify gate strict" | a WARN on *correct, useful* prose becomes noise the author learns to ignore — and it does not fix the phantom contracts that `commands_for`/`contract_class` will actually return |

**My reading:** these are not mutually exclusive, and they are not symmetric. A3 is a plain
off-by-one in the span definition with no legitimate use case for the current behaviour — option 2.
A4 has a legitimate use case (human cross-references) — option 2 for the *declaration* rule
(`CONTRACTS:` block only) plus option 3's WARN for an undeclared reference. Both deserve
contracts in SLICE2, which is unimplemented and whose accessors (A5) are ill-defined until this
is settled.

---

## H. Scope warning (carry into every decision below)

`RESEARCH-ADOPTION-PLAN.md` §5 quotes the research note against itself: *"More structure is not
more success"* — MAST found 3 of 14 failure modes are **created by** multi-agent structure, and
the meta-recommendation is to **ablate each component before granting it permanence**.

The two reviews add roughly **55 findings** to a project whose own governing principle is
minimalism-first (`project-overview.md` §1.2: a 5-question test before any new component). Both
reviewers also say this explicitly — REV §9 makes "ablate before permanence" the *governing rule*
of its build plan; ARCH §10 says "measure the compounding claim or drop it."

So the output of walking this register should be a **small** set of plan edits plus a large set of
honestly-recorded, explicitly-deferred ledger entries — not 55 new slices.

---

## P. Parallel-agent review — `production-patterns-review-2026-10-06.md` `[PARALLEL]`

Fetched from `origin/main` @ `b02b890`. Self-review of three session proposals (ASK#-01, G1
substrate, mutation staging) against production precedent. Eleven upgrades U1–U11. Three of
these **supersede my own framings** — noted inline.

| ID | Finding | Status |
|---|---|---|
| P1 | **(b′) for ASK#-01**: planner emits schema §4 *plus* a free-form `## Grounding` block (conventions / scope-out / assumptions / risks, unparsed); code does not translate. Supersedes the bridge's (a)-vs-(b) binary — keeps Evidence/Risks alive with no schema churn and no translator | → **Q6** |
| P2 | **U1 admission framing**: stop saying "compiler". The step is `parse → validate → default/stamp → persist`, ~100 lines, with one load-bearing **no-inference rule** — anything not derivable by rule fails loudly back to the planner. Precedents: Terraform plan/apply, K8s admission webhooks ("webhooks don't invent spec"), LLVM frontends→one IR | → **Q6** |
| P3 | **U2 hash-link provenance**: stamp `source_plan_sha` + `admission_version` into increment frontmatter; the runtime plan stays in the session log (schema §1 already permits). ~5 lines; makes "planner or admission?" attribution a re-read | → **Q6, Q26** |
| P4 | **U3 conformance ladder L0/L1/L2**: L0 parses (extractor total, never raises) · L1 lints (pre-check names file:line + rule) · L2 admits (floors, hashes, TRIVIAL fold). Each level independently testable; the planner learns the cheapest level first | → **Q6, Q21** |
| P5 | **keep-md is production-grade only as a *staged* decision with a trigger** — "without the trigger it is tech debt with a story". G1's end-state is right, its timing is wrong. Supersedes my accept/reject framing of E6 | → **Q21** |
| P6 | **U4 zero-budget metric**: `plan_extract_silent_misparse_total` (counter, alert >0) + `plan_precheck_first_pass_rate` (SLI, floor 0.80 by end of I03). Burn ⇒ freeze features, substrate sprint, revisit G1. "Silent" is operationalised by golden corpus + differential property + E23-shape probes | → **Q21** |
| P7 | **U5 golden drift corpus + near-miss lint + differential fuzz**: `tests/data/plan-drift-corpus/`, one file per observed drift, each asserting loud failure; lint `^#{2,4}\s+SLI?CE?\s*\d` → rustc-style *"did you mean `## SLICE2:`? (line 41)"*. **This combination is G1's accept criterion, implemented on markdown** | → **Q21**; also the test asset for **Q2/Q3** |
| P8 | **U6 strangler-fig map**: ledger records (I04) → slice records → rendered increments. Markdown becomes render-only when the trigger fires; no flag day. Turns G1 from "whether" into "when" | → **Q21**, dissolves **F6** |
| P9 | **U7 tombstone sections**: `## SLICE3: [retired] — superseded by SLICE3a, <reason>` — parseable, unrunnable; `DEPS:` refs fail loudly via CT10 instead of silently re-pointing. Zero schema change; the ledger's `supersedes:` applied to slices. Partial answer to G2 | → **Q22** |
| P10 | **G2 scale envelope stated honestly**: positional+freeze+suffix is natural-keys-with-append-only-discipline, production-grade to ~100s of slices; beyond that, surrogate keys | → **Q22** |
| P11 | **E24's three conditions made auditable**: zero-deprecation removal is acceptable iff (1) no live consumers, (2) corpus small/archived/mechanically migratable, (3) migration note shipped. All three hold today; if any fails → P5b warn-and-remove. Write the conditions next to the decision so a reader knows when it expires | → **Q23** |
| P12 | **U8 findings-not-scores**: Google's mutation-at-scale — changed lines only, survivors as review findings routed to the test's author (here the **planner**), never a gate, never a score. `MUTANT: <file:line> \| <operator> \| survived <test-id> \| contract <CT#>`. **Dissolves conflict F4** — REVIEW and ARCH were arguing about gating | → **Q18** |
| P13 | **U9 top-K + measured arid list**: cap findings per slice (K=5, CONSTRAINT-first — a planner attention budget); suppress mutant classes the ablation shows are never productively killed. Measured, not assumed. Three dismissals of one operator class nominate it for the arid list | → **Q18** |
| P14 | **U10 pre-registered graduation rule**: write the shadow→gate rule *before* the ablation runs, e.g. "precision ≥ 0.8 AND +10pp rejection on the calibration set, else stay shadow". Prevents moving goalposts | → **Q18** |
| P15 | **U11 one corpus, two consumers**: the 20-slice calibration set as versioned SWE-Gate-style pairs under `tests/data/` — serves the I02 ablation today, becomes the item-12 held-out regression set tomorrow | → **Q18, Q20/D23** |
| P16 | **§4 six principles**: loud>silent · shadow>gate · measured>assumed · reversible>optimal · findings>scores · every artifact has a consumer. Candidate roadmap standing decisions — compact, and each one is traceable to a finding in this register | → **Q28** |
| P17 | **Divergence risk**: the note references `plan-edit-2026-10-06-rationale.md` and ledger entries to **E63**, neither of which exists on `main`. Its intro says edits landed; its §5 says "nothing is applied yet". `roadmap.md` / `ledger.md` / `increment-01` on `main` are byte-identical to this branch, so most likely nothing landed — but **CT#/E# numbering may collide** | → **Q0** |

**Assessment.** P1/P5/P12 are better than what I had and I have adopted them. P7 is the single
most reusable item: the drift corpus is simultaneously G1's accept criterion, the test asset for
my A3/A4 parser fixes, and the measurement behind P6's budget. The one thing the note does **not**
cover: none of its three subjects are the extractor defects I found by dogfooding (A3/A4), so the
two sets of findings are complementary rather than overlapping.

---

## S. Existing substrate the reviews did not know about `[VERIFIED 2026-10-06]`

Found by inspecting `src/` after the operator said *"сейчас уже есть сильная система логирования
blackboard и event_bus, велосипед не изобретай, проверяй по факту, что уже построено."*
**None of the four input documents mentions any of this.** Both reviews, the bridge and the
parallel agent all reason as if the harness has no typed durable substrate.

| ID | What exists | Verified at |
|---|---|---|
| S1 | **`Blackboard`** — typed entries persisted via `SessionDatabase`, with `content_hash` (sha256 of sorted-key JSON), `parent_id` lineage, `read_set` / `write_set`, `assumptions`, `version_dependencies: dict[str,str]`, `toolchain_digest`, `schema_version`, `run_id`, `timestamp` | `src/fa/blackboard/blackboard.py` 389 ln |
| S2 | **`detect_conflict`** — full write/write, read/write and write/read overlap detection **plus `_assumption_violated`**; `_should_check_conflict` uses `parent_id` as a happens-before link; `_is_same_writer` distinguishes own prior entries from concurrent writers | same, `:95–:181`, `:348` |
| S3 | **`TelemetryLogger`** — append-only event log with **secret-key detection and value elision** built in | `src/fa/telemetry/telemetry.py` |
| S4 | **`EventBus`** — presentation/renderer bus (console + quiet renderers), *not* a durable log. Do not confuse with S3 | `src/fa/output.py`, used in `cli.py`, `coder_loop.py` |
| S5 | **`ArtifactIndex`** — indexes `knowledge/` files into the blackboard under logical IDs with revision physical IDs and file hashes | `src/fa/blackboard/artifact_index.py` 292 ln |

### Consequences — mechanisms we were about to specify that already exist

| Proposal | Already built as |
|---|---|
| R5 "typed `AttemptRecord`" (Q12-R) | `BlackboardEntry(type="attempt")` with `parent_id` chaining attempts |
| E29 `signature_hash` canonicalisation spec | `content_hash` = sha256 over `json.dumps(sort_keys=True)` — the canonicalisation already exists; what is missing is only *what payload* an attempt entry carries |
| P3 / U2 hash-link provenance (`source_plan_sha`, `admission_version`) | `content_hash` + `parent_id` + `schema_version` + `toolchain_digest` |
| G3 freshness stamp (`tree_hash`, `HEAD`) — Q26 | `version_dependencies: dict[str,str]` is literally this field |
| R6 stale-FACT re-verification (my `verified_by:` proposal) | `assumptions` + `version_dependencies` + `_assumption_violated` in `detect_conflict` **is** the stale-fact detector |
| G7 parallel-slice safety verified syntactically (E12) — deferred #11 | `read_set` / `write_set` overlap detection, already implemented and tested |
| G4 durable resume (Q26) | blackboard is SQLite-backed through `SessionDatabase` |
| D22 secret/PII redaction in records | `TelemetryLogger._is_secret_key` / `_elide_value` |
| Q17 `TESTS:` paths not coder-writable | expressible as a `write_set` assertion, not a new mechanism |

**Assessment.** This is the strongest possible evidence for §H's scope warning. Four documents
produced ~55 findings recommending mechanisms, and a substantial fraction of the *hard* parts —
content hashing, lineage, conflict detection, assumption invalidation, secret elision, durable
persistence — are already built, tested and unused by the planning loop. The correct output of
several decisions below is therefore **"wire the plan artifacts into the Blackboard"**, not
"design a record format".

**Corollary risk (the real gap):** `plan_ids.py` and the planning loop do **not** touch the
blackboard at all. So the defect is not a missing substrate — it is a **missing integration**, which
is the same shape as E2/E3/E5 (`.commands`: built, zero readers) and exactly what **SD-B** exists to
prevent.

---

## Next step

All findings above are reorganised as decidable questions in
**`decisions-qa-2026-10-06.md`** (Q0–Q30, grouped A→F, each with options and a recommendation).
Every ID in this register maps to exactly one question; nothing is dropped.
