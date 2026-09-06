# PLAN: Harness-enforced per-slice implementation ceremony    Plan-ID: PLAN-slice-ceremony-harness-enforcement
Status: READY                                   Depth: P2
Revision: v1   Changed-since-last: initial
Upstream context: `worklogs/reviews/F6-RESEARCH-intentguard-pr-prepare-friction.md` (rev 5, `7e50943`);
PR [#68](https://github.com/first-agent-dev/First-Agent-dev/pull/68); operator decisions rev 3–rev 5.

> **One-line intent.** The operator hand-pastes a ~30-line implementation ceremony before every
> slice. That ceremony already exists in the repo as `feature-planning/SKILL.md:306-441`. Make the
> harness deliver it, and make the harness — not the model — run the verification it demands.

---

## Preflight log (§2)

**Roots checked**
- `src/fa/inner_loop/coder_loop.py:773-800` — L2 skill-injection site. Reads a skill on the L2
  **entry turn only**, passes `skill_result` into `build_observation_block`.
- `src/fa/inner_loop/workflow_controller.py:257-271` — stage runner; writes `FlowState` before each
  stage, builds `stage_args`. The pipeline seat (operator decision Q-op2).
- `src/fa/cli.py:1595-1633` — `_build_run_tool_registry`; `registry.register(build_prepare_pr_tool(...))`
  at `:1625` is **unconditional** — every role gets `pr_prepare`.
- `src/fa/cli.py:1716-1737` — `_build_run_hook_registry`; `IntentGuard` registration, gated by
  `_resolve_intent_guard_mode` (`enforce|observe|off`).

**Greps run → findings**

| pattern | finding |
|---|---|
| `SKILL_FILE_NAME` | `_inject.py:47` = `"SKILL.md"`, consumed at `:224`. **Hardcoded** — cannot read a sibling file. |
| `def read_skill_for_injection` | `_inject.py:216`, signature `(skill_name, skills_root)`. No filename param. |
| `def build_observation_block` | `observations.py:105-115`; already has `skill_result`, `skill_name`, `verification_command` params. |
| `select_l2_skill` | `expansion.py:128-136`; warm→`feature-planning`, cold→`plan-authoring`. |
| `should_load_skill` | `loader.py:119`. **Zero production callers** (only `tests/test_prompt_caching_per_role.py:188` re-implements it). |
| `pr_prepare` in `cli.py` | `:72` import, `:162` readiness prompt text, `:1625` registration, `:2115`, `:2158`, `:2168`. |
| `pr_prepare` in `prompt.py` | `:20,22,24,525,571,645,822,854` — **8 sites across 4 role prompts**. |
| `gh pr create` repo-wide | only `knowledge/research/*deep-dive*.md:139,236`. **No PR-creation code anywhere.** |
| `_READ_ONLY_COMMANDS` | `bash_intent.py:62-99`; 33 verbs, **`gh` absent** → agent `gh` call ⇒ `OPAQUE_EXEC`. |
| `Each skill is single file` | `skill-writing/SKILL.md:63`. **Invariant that `INJECT.md` violates.** |
| `estimate_tokens` | two: `profiles.py:430` (registry), `memory/context_budget.py:18` (messages, `chars//4`). |
| `_DRAFT_REQUIRED_BASH_EFFECTS` | `intent_guard.py:121-127` — `INDEX_WRITE`, `REPO_WRITE`, `OPAQUE_EXEC`. |
| `_MISSING_DRAFT_REASON` | `intent_guard.py:138-141` — literally instructs "call `pr_prepare`". |

**Gold patterns mirrored**
- `tests/test_skill_injection.py:184-197` (`test_read_skill_from_temp_fixture`) — tmp-tree fixture,
  asserts frontmatter stripped and body present. The exact shape S2's tests mirror.
- `scripts/run_live_check.sh:569-588` — `s127_row` + `s127_expect` + `s127_finish` triad. New live
  rows mirror `cmd_s127_advancing` / `s127_assert_advancing`.

**Conflicts / invariants found**
1. **`skill-writing/SKILL.md:63`** forbids sibling files in a skill dir → must be amended (S1).
2. **Deadlock risk:** unregistering `pr_prepare` for chat while `IntentGuard` runs in `enforce`
   leaves `_MISSING_DRAFT_REASON` (`intent_guard.py:138`) instructing the model to call a tool that
   no longer exists ⇒ **unrecoverable chat session**. Governs S8/S9 ordering. → **CT9**.
3. **exploration-log Q19 constraint** (`builtin.py:112-127`): denying general-write for spawns denied 8/10 realistic
   verifier commands (`pytest -q`, `mypy src/`). Harness-run verification must not re-derive it.
4. **D7** (`cli.py:1942-1947`): per-task hints ride `turn_context`, never `system_prompt_extra`
   (cache identity). Governs S5.
5. **PTS-v1** (`registry.py:289,425`): no `if`/`then`/`dependentRequired` in tool schemas.
6. `prompt_composer.py:43-59`: cache identity = name + input_schema, **excludes** description.

**As-is liveness**
| signal | level |
|---|---|
| ceremony injected at coder stage | **L0** — absent |
| `tests-writing` injected anywhere | **L0** — never injected by any path |
| `should_load_skill` | **L1** — import-reachable, zero callers |
| harness-run verification | **L0** |
| files-allowed scope warning | **L0** |
| PR publication | **L0** |
| plan ID extraction | **L0** |
| `pr_prepare` in chat | **L3** — live, and the F6 turn-tax |

**Unresolved → promoted to Q#:** Q1 (extractor conformance rate — measured by S3, not guessed),
Q2 (condensate token cost — measured by S2).

---

## 0. Executive intent (§3)

**IDEA:** Stop the operator hand-pasting a per-slice implementation ceremony. The harness delivers
it at the right time, and runs the verification it demands instead of trusting the model's report.

**PROJECT MEANING:** In the `planner→coder→eval` pipeline, this becomes coder-stage turn context
plus a post-coder verification gate. It belongs there — not in chat — because that is where
implementation slices execute (operator decision Q-op2), and because `FlowState`
(`workflow_artifacts.py:250-301`) already carries the per-stage state a slice ceremony needs.

**GOALS**
- **G1** The ceremony reaches the model automatically at coder-stage slice entry. Operator pastes nothing.
- **G2** `tests-writing` guidance reaches the model whenever the ceremony demands a C0–C4 class.
- **G3** Verification commands are executed **by the harness**; real stdout/exit code enter context.
  The model cannot claim a green run that did not happen.
- **G4** Out-of-scope file writes surface as a WARNING event. Never blocked.
- **G5** Plan slice/contract IDs are extracted by script (no LLM) and offered advisory-only.
- **G6** `pr_prepare` is removed from the chat role — tool, prompt text, and description.
- **G7** The run's ceremony output is published as a PR body, branch→`main`, by the harness.
- **G8** No new rejection surface: no field may be denied for absence. (Anti-F6 clause.)

**NON-GOALS:** a `SliceContract` typed artifact (rev 3, retracted); the `ask_user` stop-rule tool
(backlogged); replacing the git-hook commit validator; changing `pr_intent.py` validation logic;
touching the eval or planner role's own prompts.

**INTENT:** Code should ensure that *whenever a coder stage begins an implementation slice*, the
ceremony is in context and its verification step is executed by the harness — not narrated by the model.

**MECHANISM SKETCH:** coder stage entry → `read_skill_for_injection(..., file_name="INJECT.md")` →
`build_observation_block` turn_context → model emits packet + edits → harness runs plan `T#` commands
→ real output injected → non-zero routes `REPAIR_REQUIRED` → on `DONE`, packets fold into a PR body.

**PROOF SKETCH:** the coder loop observes ceremony text in `turn_context`; kill-check removes the
`read_skill_for_injection` call at `coder_loop.py:783` and the named live-path test fails.

**SIZE:** L

---

## 1. Non-goals & minimal-mechanism check (§5)

**Could a smaller change satisfy the intent?**

| choice | smaller alternative | verdict |
|---|---|---|
| `INJECT.md` condensate files | inject `SKILL.md` body (already works) | **Rejected** — 643+828 lines/turn. Operator's 30-line prompt is empirical proof of sufficiency. |
| optional `file_name` param | new loader function | **Rejected** — one defaulted kwarg is smaller and keeps one read path. |
| reuse `build_observation_block` | new injection channel | **Accepted as minimal** — the param already exists. |
| harness runs verify via `SandboxHook` | new exec path | **Accepted as minimal** — Q19 forbids a second gate. |
| no new artifact type | `SliceContract` dataclass (rev 3) | **Rejected/retracted** — the packet is prose; no schema needed. |

**New component gate.** No new service/dependency/LLM step/queue. Two new **doc** files
(`INJECT.md` × 2), one new **pure module** (`plan_ids.py`), one new hook (scope warning). Everything
else is wiring existing symbols. Deterministic code does all of it without an LLM call — which is
the §"deterministic authority" central law, and the reason the extractor is script-only (operator decision Q-op5).

**Topology gate.** No subagents, no DAG, no parallelism. Strictly a chain inside the existing
stage sequencer.

---

## 2. Current state → target state (§4)

**AS-IS (verified)**

| dimension | finding |
|---|---|
| Entry points | `coder_loop.py:773` (L2 entry only), `workflow_controller.py:257` (stage runner) |
| Existing types | `SkillInjectionResult` (`_inject.py`), `FlowState`/`EvalReport` (`workflow_artifacts.py`) |
| Producers/consumers | producer `read_skill_for_injection:216`; consumer `build_observation_block:105`. **Fires once per run, at L2 entry, planner skills only** |
| State stores | JSONL event log; `~/.fa/session-log/<run_id>/pr_draft.md`; workflow artifacts dir |
| Flags/defaults | `intent_guard_mode` = `enforce`; no flag for ceremony injection yet |
| Tests today | `tests/test_skill_injection.py` (C0 on the read path). No coder-stage injection test. No harness-verification test |
| Liveness | ceremony L0 · `tests-writing` L0 · harness-verify L0 · scope-warn L0 · publish L0 · `pr_prepare`-in-chat L3 |

**TO-BE (machine-checkable)**

- `read_skill_for_injection(skill_name, skills_root, *, file_name="SKILL.md")` — additive kwarg.
- New files `knowledge/skills/{feature-planning,tests-writing}/INJECT.md`.
- New pure module `src/fa/inner_loop/plan_ids.py` → `extract_plan_ids(text) -> PlanIds`.
- New event kinds: `ceremony_injected`, `verification_ran`, `scope_warning`.
- `pr_prepare` absent from the chat registry; present for `coder`.
- New feature flag `slice_ceremony.mode` = `off | observe | enforce`, **default `observe`**.
- Target liveness **L3** for G1–G4, G6; **L3** for G7; G5 advisory (L3 on the extractor's own
  contract, L2 acceptable on end-to-end pre-fill since it is advisory by operator decision).

**GAP ledger**

| GAP# | verified gap | owner |
|---|---|---|
| GAP1 | loader cannot read any file but `SKILL.md` (`_inject.py:47,224`) | S2 / T1 |
| GAP2 | no condensed injectable ceremony exists | S1 / T2 |
| GAP3 | coder stage never injects a ceremony (`coder_loop.py:773` = L2-entry planner only) | S5 / T4 |
| GAP4 | `tests-writing` never injected; `should_load_skill:119` has zero callers | S5 / T5 |
| GAP5 | verification is model-narrated; no harness execution | S6 / T6 |
| GAP6 | no files-allowed scope signal | S7 / T7 |
| GAP7 | `pr_prepare` registered for all roles (`cli.py:1625`) incl. chat | S8 / T8 |
| GAP8 | `_MISSING_DRAFT_REASON:138` names a tool chat will no longer have ⇒ deadlock | S8 / T9 |
| GAP9 | no plan-ID extraction | S3 / T3 |
| GAP10 | no PR publication path; `gh` not whitelisted (`bash_intent.py:62-99`) | S10 / T10 |
| GAP11 | `skill-writing:63` forbids the sibling file this plan adds | S1 / T2b |

---

## 3. Contracts (§6)

**CT1 — `read_skill_for_injection` filename parameter** *(function, §6.1)*
- IN `(skill_name: str, skills_root: Path, *, file_name: str = "SKILL.md")` → OUT `SkillInjectionResult`.
- PRE: none. POST: reads `skills_root/<skill_name>/<file_name>`; **absent file ⇒ structured warning,
  never raises** (existing contract, `_inject.py:225-229`). PURE: n (one FS read). ERRORS: none raised.
- DETERMINISTIC MECHANISM: default-valued kwarg; every existing call site keeps `SKILL.md`.

**CT2 — `INJECT.md` condensate** *(data/authority, §6.3)*
- AUTHORITY: `SKILL.md` is SSOT for the protocol; `INJECT.md` is a **derived executable subset**.
  On disagreement, `SKILL.md` wins and `INJECT.md` is corrected.
- DETERMINISTIC MECHANISM: parity test T2 — every field label in `INJECT.md` appears in `SKILL.md`.
- FAILURE SURFACE: missing/empty `INJECT.md` ⇒ `SkillInjectionResult.warning`, run proceeds (CT1).

**CT3 — ceremony injection** *(signal, §6.2, TWO-SIDED)*
- PRODUCER: `coder_loop.py` slice-entry branch (**TO ADD**, S5), when role=`coder` ∧
  `slice_ceremony.mode != off`. Payload `{skill: str, body: str, turn: int}`. Paths P1, P2, P3.
- CONSUMER: `build_observation_block` (`observations.py:105`) → `turn_context` → model. Plus event
  `ceremony_injected` consumed by the live-check assertion.
- DUAL-WRITE: turn_context (live) **and** event log (durable) must both be written in the same
  branch — mirrors the existing `skill_result` handling.
- KILL-CHECK: remove the producer call at the S5 site ⇒ **T4** fails.
- SHIP RULE: producer proof before shipped.

**CT4 — harness-run verification** *(signal, §6.2, TWO-SIDED)*
- PRODUCER: post-coder verification step in `workflow_controller.py` (**TO ADD**, S6). Runs plan
  `T#` commands through the existing `SandboxHook` bash path. Payload
  `{command, exit_code, stdout_tail, stderr_tail, duration_ms}`.
- CONSUMER: (a) next coder turn's `turn_context` (real output); (b) verdict routing —
  non-zero ⇒ `REPAIR_REQUIRED` via `EVAL_VERDICT_TO_TERMINAL_STATUS` (`workflow_controller.py:50-55`, applied at `:445`).
- KILL-CHECK: remove the producer ⇒ **T6** fails (no `verification_ran` event, exit code absent).
- SHIP RULE: **must be L3.** This is G3, the operator's strongest requirement.

**CT5 — files-allowed scope warning** *(signal, §6.2)*
- PRODUCER: new `ScopeWarnHook` at `BEFORE_TOOL_EXEC` (**TO ADD**, S7). Emits `scope_warning`
  `{path, allowed: tuple[str,...]}` when a write path ∉ allowed set. **Always `Decision.allow`.**
- CONSUMER: event log + live-check assertion.
- KILL-CHECK: remove the emit ⇒ **T7** fails.
- INVARIANT: never returns `deny`. Asserted directly by T7b (operator decision Q-op4).

**CT6 — plan ID extraction** *(function, §6.1)*
- `extract_plan_ids(text: str) -> PlanIds` where `PlanIds` is a frozen dataclass of
  `slices/gaps/contracts/tests: tuple[str, ...]`.
- PURE: **y** — no FS, no LLM, no network. POST: unparseable input ⇒ **empty tuples, never raises**.
- DETERMINISTIC MECHANISM: compiled regexes over the ID grammar common to both planning skills
  (`feature-planning:120-132` ≡ `plan-authoring:161-181`).

**CT7 — chat role tool corpus** *(invariant, §6.4)*
- `pr_prepare ∉ build_run_tool_registry(role="chat").names()` ∧ `pr_prepare ∈ (role="coder")`.
- Enforced at `cli.py:1625`; verified by T8.

**CT8 — PR publication** *(signal, §6.2)*
- PRODUCER: publisher in `src/fa/hygiene/pr_publish.py` (**TO ADD**, S10), invoked only when the
  pipeline reaches `DONE`. Pushes the session branch and opens a PR to `main`.
- CONSUMER: GitHub; locally the emitted `pr_published` event + the written body file.
- KILL-CHECK: remove the producer call ⇒ T10 fails.

**CT9 — no-deadlock security/liveness contract** *(security, §6.5 — adversarial case required)*
- BOUNDARY: chat must never be told to call a tool it does not have.
- INVARIANT: if `pr_prepare ∉ registry` for a role, `IntentGuard` must not emit
  `_MISSING_DRAFT_REASON` for that role.
- DETERMINISTIC MECHANISM: `IntentGuard` gains `draft_tool_available: bool`; when False the
  draft requirement is **not applied** for that session.
- ADVERSARIAL CASE (C3, T9): chat session, `intent_guard_mode=enforce`, model attempts
  `fs_write_file`. Assert **not denied** with `_MISSING_DRAFT_REASON`. Without the fix this
  deadlocks the session permanently — the highest-severity risk in this plan.

**CT10 — `pr_intent.py` untouched** *(invariant)*
- The commit-message validator and its git-hook seat are unchanged. Verified by T11 (existing suite green).

---

## 4. Path & flag matrix (§7)

**4.1 Path inventory**

| P# | trigger | file:symbol | flag | covering S# |
|---|---|---|---|---|
| P1 | coder stage, slice entry, plan present | `coder_loop.py` slice branch (NEW) | `mode=enforce` | S5 |
| P2 | coder stage, slice entry, **no** plan | same | `mode=enforce` | S5 |
| P3 | coder stage, later turns (anchor only) | same | `mode=enforce` | S5 |
| P4 | verification commands present in plan | `workflow_controller.py` (NEW) | `mode=enforce` | S6 |
| P5 | verification commands absent | same | `mode=enforce` | S6 |
| P6 | write inside allowed set | `ScopeWarnHook` (NEW) | any | S7 |
| P7 | write outside allowed set | same | any | S7 |
| P8 | chat role mutation attempt, no `pr_prepare` | `IntentGuard._requires_draft:226` | `enforce` | S8 |
| P9 | coder role mutation attempt, `pr_prepare` present | same | `enforce` | S8 |
| P10 | pipeline reaches `DONE` | `pr_publish.py` (NEW) | `publish=on` | S10 |
| P11 | pipeline ends non-`DONE` | same | any | S10 |
| P12 | `mode=off` — nothing injected, no behaviour change | all NEW sites | `off` | S4 |

Coverage gate: every P# has a covering step and a verification (§6 table). No uncovered path.

**4.2 Flag matrix**

| ID | flags | proves | covering S#/T# |
|---|---|---|---|
| A | `slice_ceremony.mode=enforce` | main path works | S5,S6 / T4,T6 |
| B | `enforce` + `intent_guard_mode=enforce` + publish | full cascade, no deadlock | S8,S10 / T9,T10 |
| C | **defaults** (`mode=observe`) | out-of-the-box: events emitted, no context change | S4 / T12 |
| D | `mode=off` | zero-cost disable, byte-identical to today | S4 / T13 |

Matrix gate: all four rows have a covering step **and** a named verification.

---

## 5. Step-by-step implementation (§8)

Ordering follows the skill's default: docs/authority → types → producers → consumers → root wiring
→ verification → adversarial → publish.

> **Slice/commit granularity (operator decision Q-op1, hybrid):** before-gate once at slice entry; one edit
> packet per edit (`E# / S#`, no bundling per `feature-planning:386`); after-gate + harness
> verification once before the commit. **One S# below = one commit.**

---

### Step S1: Author the two `INJECT.md` condensates and amend the single-file invariant

Traces-to: G1, G2 · GAP2, GAP11 · CT2
Depends-on: none    Parallelizable-with: S2, S3
Target liveness: L0→L1

Edit:
- path: `knowledge/skills/feature-planning/INJECT.md` symbol: — change: **NEW**, ~30–40 ln, condensed from `SKILL.md:306-441`
- path: `knowledge/skills/tests-writing/INJECT.md` symbol: — change: **NEW**, ~20–30 ln, condensed from `SKILL.md:123-128,156`
- path: `knowledge/skills/skill-writing/SKILL.md` symbol: §Invariants:63 change: allow an optional derived `INJECT.md`
- path: `knowledge/skills/README.md` symbol: preamble change: one line describing the layout

Degree of freedom closed: authors could otherwise inject arbitrary ad-hoc prompt text that drifts
from the skill; the condensate is now a named file with a parity test binding it to its `SKILL.md`.

Deterministic mechanism: `tests/test_inject_condensates.py` (T2) — every field label in `INJECT.md`
must appear in the sibling `SKILL.md`.

Do:
1. Write `feature-planning/INJECT.md`: before-gate (current behavior · plan/gap IDs · files allowed ·
   blocking questions) → edit packet (idea · intent · AS-IS→TO-BE · mechanism · DoF closed ·
   deterministic mechanism · best practice · failure behavior · DoD + negative proof · test class ·
   kill-check target) → after-gate (targeted tests · static checks · diff · contract status ·
   "not complete from no exception") → stop rule (new policy choice ⇒ promote to Q#, STOP).
2. Write `tests-writing/INJECT.md`: C0/C0p/C1/C2/C3/C4 ladder, producer/consumer two-sided law,
   kill-check requirement, anti-theater minimum.
3. **No YAML frontmatter** in either file — only `SKILL.md` carries frontmatter/triggers.
4. Amend `skill-writing/SKILL.md:63` to: one `SKILL.md` **plus an optional derived `INJECT.md`**.

Do-not: do not paraphrase field names — parity is checked mechanically. Do not add frontmatter.
Do not exceed 40 lines in either file.

Exit criteria:
- [ ] `test -f knowledge/skills/feature-planning/INJECT.md && test -f knowledge/skills/tests-writing/INJECT.md`
- [ ] `wc -l` ≤ 40 each
- [ ] neither file starts with `---`
- [ ] T2 parity passes; `grep -n "optional derived" knowledge/skills/skill-writing/SKILL.md` hits

---

### Step S2: Add the `file_name` parameter to the skill loader

Traces-to: G1 · GAP1 · CT1
Depends-on: none    Parallelizable-with: S1, S3
Target liveness: L1→L2

Edit:
- path: `src/fa/skills/_inject.py` symbol: `read_skill_for_injection:216` change: add `*, file_name: str = SKILL_FILE_NAME`; use it at `:224`

Degree of freedom closed: the injected payload's filename was a hardcoded constant
(`_inject.py:47`), so no call site could choose a lighter payload; it is now a typed parameter with
a backward-compatible default.

Deterministic mechanism: `src/fa/skills/_inject.py:216` — defaulted keyword-only parameter; the
existing missing-file branch at `:225-229` already returns a structured warning, so a bad filename
degrades rather than raising.

Do:
1. Add the kwarg; replace `SKILL_FILE_NAME` at `:224` with it.
2. Include `file_name` in the not-found warning text so a typo is diagnosable.
3. Leave every existing call site untouched (they inherit the default).

Do-not: do not add a second read function. Do not make it positional. Do not raise on missing files.

Example:
```python
def read_skill_for_injection(
    skill_name: str, skills_root: Path, *, file_name: str = SKILL_FILE_NAME
) -> SkillInjectionResult:
    skill_path = skills_root / skill_name / file_name
```

Exit criteria:
- [ ] `grep -n "file_name: str = SKILL_FILE_NAME" src/fa/skills/_inject.py`
- [ ] mypy/pyrefly clean
- [ ] T1 green; `tests/test_skill_injection.py` unchanged tests still green (back-compat)

Kill-check: reverting `:224` to the constant makes **T1** fail.

---

### Step S3: New pure module `plan_ids.py` + conformance measurement

Traces-to: G5 · GAP9 · CT6
Depends-on: none    Parallelizable-with: S1, S2
Target liveness: L0→L2

Edit:
- path: `src/fa/inner_loop/plan_ids.py` symbol: `PlanIds`, `extract_plan_ids` change: **NEW** pure module
- path: `scripts/measure_plan_id_extraction.py` symbol: — change: **NEW** measurement harness

Degree of freedom closed: slice/contract identity was free text the model could invent; extraction
is now a pure regex function whose output is checked as a substring of the plan file.

Deterministic mechanism: `src/fa/inner_loop/plan_ids.py` — compiled `re` patterns over the ID
grammar shared by `feature-planning:120-132` and `plan-authoring:161-181`.

Do:
1. `PlanIds` frozen dataclass: `slices`, `gaps`, `contracts`, `tests` — all `tuple[str, ...]`.
2. `extract_plan_ids(text)` — patterns for `### S<n>:`, `GAP<n>`, `CT<n>`, `T<n>`. No FS, no LLM.
3. Unparseable/empty input ⇒ all-empty `PlanIds`. **Never raise.**
4. Measurement script: run over every file in `worklogs/implementation-plans/`, print a per-plan
   pass/fail table **split conforming (post-skill) vs legacy**, and a summary rate.

Do-not: do not call an LLM. Do not read the FS from the module. Do not fail the build on a low rate —
legacy misses are expected (operator decision Q-op5) and recorded, not gating.

Exit criteria:
- [ ] `python3 scripts/measure_plan_id_extraction.py` prints the split table
- [ ] measured rate on **conforming** plans recorded in this plan's §7 Q1 row
- [ ] T3 green including the empty-input and garbage-input cases

Kill-check: deleting the `### S<n>:` pattern makes **T3** fail.

---

### Step S4: Feature flag `slice_ceremony.mode`

Traces-to: G1, G8 · CT3 · matrix C, D
Depends-on: none    Parallelizable-with: S1–S3
Target liveness: L0→L2

Edit:
- path: `src/fa/feature_flags.py` symbol: `FeatureFlags:46` (beside `intent_guard_mode`) change: add `slice_ceremony_mode: str = "observe"`; register in the `:62` mapping, the `:76` defaults list, the `:129` type map, and the `:289` loader

Degree of freedom closed: a new always-on context injection could change every coder run with no
operator opt-out; the mode flag makes rollout explicit and reversible.

Deterministic mechanism: closed 3-state enum `{off, observe, enforce}` resolved fail-safe to
`observe`, mirroring `_resolve_intent_guard_mode` (`cli.py:182-197`) and `intent_guard_mode` (`feature_flags.py:46`).

Do:
1. Add the flag + resolver mirroring the `intent_guard_mode` precedent exactly — **all five sites** (`feature_flags.py:46,62,76,129,289`); missing one silently drops the flag at load time.
2. `off` ⇒ no injection, no events, byte-identical to today. `observe` ⇒ emit events, **do not**
   alter `turn_context`. `enforce` ⇒ full behaviour.
3. Default `observe` — telemetry first, per the S12.4 flag precedent (external).

Do-not: do not default to `enforce`. Do not fail closed on an unparseable value.

Exit criteria:
- [ ] `off` run produces zero `ceremony_injected` events (T13)
- [ ] `observe` run produces events but unchanged `turn_context` (T12)

---

### Step S5: Inject the ceremony at coder-stage slice entry

Traces-to: G1, G2 · GAP3, GAP4 · CT3 · P1, P2, P3
Depends-on: S1, S2, S4    Parallelizable-with: none
Target liveness: L2→L3

Edit:
- path: `src/fa/inner_loop/coder_loop.py` symbol: slice-entry branch near `:773-800` change: when role=`coder` ∧ mode≠`off`, read both `INJECT.md` condensates and pass into `build_observation_block`
- path: `src/fa/skills/loader.py` symbol: `should_load_skill:119` change: **wire it** — first production caller

Degree of freedom closed: which protocol text reaches the model at implementation time was entirely
the operator's manual choice (paste or forget); it is now a deterministic function of role, stage,
and turn index.

Deterministic mechanism: `src/fa/inner_loop/coder_loop.py` slice-entry branch — condensates read via
`read_skill_for_injection(..., file_name="INJECT.md")` (CT1) and emitted as `ceremony_injected`.

Do:
1. Full condensate body on **slice-entry** turn (P1/P2); short anchor via `build_skill_anchor` on
   later turns (P3) — mirrors the existing L2 entry/anchor split.
2. Route through `should_load_skill` (`loader.py:119`) so injection is trigger-based, giving that
   function its first production caller (GAP4).
3. Emit `ceremony_injected` **in the same branch** that writes `turn_context` — CT3 dual-write.
4. Wrap in `try/except` + `logger.warning`, mirroring `coder_loop.py:786-789`: an advisory must
   never crash a run.
5. Plan absent (P2) ⇒ inject the ceremony anyway with ID fields blank. **Never block** (G8).

Do-not: do not put any of this in `system_prompt_extra` — **D7** (`cli.py:1942-1947`), it would
break the prompt cache. Do not inject on every turn. Do not inject for chat/planner/eval.

Exit criteria:
- [ ] `grep -n 'file_name="INJECT.md"' src/fa/inner_loop/coder_loop.py`
- [ ] `grep -n "should_load_skill" src/fa/inner_loop/` returns a **production** hit
- [ ] T4 asserts ceremony text in `turn_context` on entry turn, anchor-only on turn 2
- [ ] T5 asserts the `tests-writing` condensate is present

Kill-check: removing the `read_skill_for_injection` call at this site makes **T4** fail.

---

### Step S6: Harness runs the verification commands

Traces-to: G3 · GAP5 · CT4 · P4, P5
Depends-on: S3, S4    Parallelizable-with: S7
Target liveness: L0→L3

Edit:
- path: `src/fa/inner_loop/workflow_controller.py` symbol: stage runner near `:257-271` change: after the coder stage, execute plan `T#` commands and inject real output

Degree of freedom closed: whether a verification actually ran was the model's word — it could
narrate a green run it never executed; execution now happens in harness code the model cannot reach,
and the exit code enters context verbatim.

Deterministic mechanism: `src/fa/inner_loop/workflow_controller.py` post-coder verification step —
real `exit_code` recorded in the `verification_ran` event and routed via
`EVAL_VERDICT_TO_TERMINAL_STATUS` (`:49-53`).

Do:
1. Take commands from the **plan** (extracted, S3) — never from model output. This is what makes
   the gate trustworthy: the operator authored them.
2. Execute through the existing `SandboxHook` bash path (`builtin.py:87-104`). **No second exec path**
   — exploration-log Q19 (`builtin.py:112-127`) showed a stricter gate denies 8/10 real verifier commands.
3. Inject `{command, exit_code, stdout_tail, stderr_tail}` as `turn_context`.
4. Non-zero ⇒ `REPAIR_REQUIRED`. P5 (no commands) ⇒ emit `verification_ran` with
   `skipped: true`, do **not** block (G8).
5. Bound by the existing wall-clock deadline (`workflow_controller.py:345`) and `bash_timeout_seconds`.

Do-not: do not let the model supply or edit the command list. Do not add a new sandbox gate. Do not
block when the plan names no commands.

Exit criteria:
- [ ] `verification_ran` event carries a real integer `exit_code`
- [ ] T6: seeded failing command ⇒ `REPAIR_REQUIRED` and the model's next turn sees the real stderr
- [ ] T6b: P5 ⇒ `skipped: true`, run continues

Kill-check: removing the execution call makes **T6** fail (no event, no exit code).

---

### Step S7: `ScopeWarnHook` — warn, never block

Traces-to: G4 · GAP6 · CT5 · P6, P7
Depends-on: S4    Parallelizable-with: S6
Target liveness: L0→L3

Edit:
- path: `src/fa/inner_loop/hooks/scope_warn.py` symbol: `ScopeWarnHook` change: **NEW** `BEFORE_TOOL_EXEC` observer
- path: `src/fa/cli.py` symbol: `_build_run_hook_registry:1716` change: register it

Degree of freedom closed: writes outside the declared slice scope were invisible; they now emit a
typed event while remaining permitted, so scope drift is observable without becoming a new denial
surface.

Deterministic mechanism: `src/fa/inner_loop/hooks/scope_warn.py` — the hook returns
`Decision.allow` on **every** branch; there is no code path that can produce a deny.

Do:
1. Compare the write path against the allowed set; emit `scope_warning` when outside.
2. Return `Decision.allow` unconditionally.
3. Empty/absent allowed set ⇒ no warnings at all (not "everything is a violation").

Do-not: **do not add a deny branch** (operator decision Q-op4, G8). Do not block on an unparseable set.

Exit criteria:
- [ ] `grep -c "Decision.deny" src/fa/inner_loop/hooks/scope_warn.py` == **0**
- [ ] T7: out-of-scope write ⇒ warning event **and** the write succeeds
- [ ] T7b: no allowed set ⇒ zero warnings

Kill-check: removing the emit makes **T7** fail.

---

### Step S8: Remove `pr_prepare` from chat + close the deadlock

Traces-to: G6 · GAP7, GAP8 · CT7, CT9 · P8, P9
Depends-on: none    Parallelizable-with: S5–S7
Target liveness: L3→L3 (chat), CT9 L0→L3

Edit:
- path: `src/fa/cli.py` symbol: `_build_run_tool_registry:1625` change: register `build_prepare_pr_tool` **only when `role != "chat"`**
- path: `src/fa/cli.py` symbol: `_READINESS_PROMPT_EXTRA:162` change: drop the `pr_prepare` sentence for chat
- path: `src/fa/inner_loop/prompt.py` symbol: `:525,571,645` change: remove `pr_prepare` instructions from the chat prompt only
- path: `src/fa/inner_loop/hooks/intent_guard.py` symbol: `IntentGuard.__init__`, `_requires_draft:226` change: add `draft_tool_available: bool`; skip the draft requirement when False

Degree of freedom closed: the guard assumed the draft tool was universally registered, so removing
it from one role would have produced a permanent deadlock; availability is now an explicit
constructor input rather than an implicit assumption.

Deterministic mechanism: `src/fa/inner_loop/hooks/intent_guard.py:226` — `_requires_draft` returns
False whenever `draft_tool_available` is False, so `_MISSING_DRAFT_REASON` is unreachable for a role
without the tool.

Do:
1. Make registration role-conditional at `cli.py:1625`.
2. Pass `draft_tool_available=(role != "chat")` into `IntentGuard` at `cli.py:1731-1736`.
3. Strip the 4 chat-facing prompt/description sites. **Leave coder/planner/eval prompts alone.**
4. Re-check `prompt.py:20,22,24,822,854` — remove only chat-role text.

Do-not: do not delete `prepare_pr.py`. Do not touch `pr_intent.py` (CT10). Do not change the
`enforce` default.

Exit criteria:
- [ ] `pr_prepare ∉ chat registry names`; `∈ coder registry names` (T8)
- [ ] **T9 (C3 adversarial):** chat + `enforce` + `fs_write_file` ⇒ **not** denied with `_MISSING_DRAFT_REASON`
- [ ] `grep -c pr_prepare` on the chat prompt path == 0
- [ ] chat registry `estimate_tokens` strictly lower than before

Kill-check: reverting `_requires_draft` makes **T9** fail (session deadlocks).

---

### Step S9: Docs — operator instructions and authority records

Traces-to: G1–G8 · CT2
Depends-on: S1–S8    Parallelizable-with: none
Target liveness: docs only

Edit: `knowledge/instructions/02-operations.md` (**operator instructions** — ceremony is automatic,
stop pasting it; document the three modes); `knowledge/skills/plan-authoring/SKILL.md` (port §9–§12
from `feature-planning` — §5.3 conformance gap); `knowledge/skills/pr-creation/SKILL.md`
(`pr_prepare` retired from the chat seat; commit gate unchanged); `knowledge/trace/exploration_log.md`
(new Q#: ceremony-as-skill finding + Q-15 amendment); `knowledge/adr/` (ADR: harness-run
verification + agent-tool retirement); `worklogs/BACKLOG.md` (I-58; `ask_user` row;
`should_load_skill` wired).

Do-not: do not mark the `ask_user` stop-rule tool as done — it is backlogged (operator decision Q-op6).

Exit criteria:
- [ ] `scripts/check_doc_links.py` passes
- [ ] operator instructions state the paste is no longer needed

---

### Step S10: PR publication

Traces-to: G7 · GAP10 · CT8 · P10, P11
Depends-on: S1–S8    Parallelizable-with: S9
Target liveness: L0→L3

Edit:
- path: `src/fa/hygiene/pr_publish.py` symbol: `build_pr_body`, `publish_pr` change: **NEW**
- path: `src/fa/inner_loop/workflow_controller.py` symbol: terminal branch change: invoke on `DONE` only

Degree of freedom closed: publishing had no owner, and an agent-issued `gh` call would classify as
`OPAQUE_EXEC` (`bash_intent.py:62-99`) — pushing the operator's token into model-reachable surface;
publication is now harness-side code gated on a terminal pipeline state.

Deterministic mechanism: `src/fa/hygiene/pr_publish.py` — `publish_pr` is called only from the
`DONE` branch of the stage runner and targets the session branch; `validators.py:251` already blocks
force-push to `main`.

Do:
1. `build_pr_body(packets, plan_links) -> str` — **pure**, deterministic fold. Frontmatter
   (plan/slices/contracts) + commit-note headers + per-slice sections carrying the **real** captured
   verification output (S6).
2. `publish_pr` — push the session branch, open a PR to `main`. Harness-side, never agent bash.
3. Gate strictly on `DONE` (P11 ⇒ no publish).
4. Write the body to a file **first**, then publish, so a publish failure still leaves the artifact.

Do-not: never push to `main` directly. Never expose the token to the model. Do not publish on a
non-terminal state.

Exit criteria:
- [ ] `build_pr_body` unit-tested pure (T10a)
- [ ] T10: `DONE` ⇒ body file written + `pr_published` event; P11 ⇒ neither
- [ ] `grep -n "main" src/fa/hygiene/pr_publish.py` shows `main` only as the PR **base**, never a push target

Kill-check: removing the `publish_pr` call from the `DONE` branch makes **T10** fail.

---

## 6. Verification plan (§9)

| T# | CT# | class | oracle (ranked) | kill-check target | P# |
|---|---|---|---|---|---|
| T1 | CT1 | C0 | return value + structured warning | `_inject.py:224` filename use | — |
| T2 | CT2 | C0p | parity: labels ⊆ `SKILL.md` | the `INJECT.md` files | — |
| T2b | CT2 | C0p | `skill-writing:63` amended text present | — | — |
| T3 | CT6 | C0 | returned `PlanIds` tuples | `### S<n>:` pattern | — |
| T4 | CT3 | **C1** | event `ceremony_injected` + `turn_context` content | injection call in `coder_loop.py` | P1,P2,P3 |
| T5 | CT3 | C1 | `tests-writing` body in context | second condensate read | P1 |
| T6 | CT4 | **C1** | event kind + real `exit_code` | verification exec call | P4 |
| T6b | CT4 | C1 | `skipped: true`, run continues | — | P5 |
| T7 | CT5 | C1 | `scope_warning` event **+ write succeeded** | the emit | P6,P7 |
| T7b | CT5 | C0 | static: zero `Decision.deny` in the module | — | P7 |
| T8 | CT7 | C2 | registry `names()` per role | conditional registration | P9 |
| T9 | CT9 | **C3** | absence of `_MISSING_DRAFT_REASON` deny | `draft_tool_available` branch | P8 |
| T10 | CT8 | C1 | `pr_published` event + body file | `publish_pr` call | P10,P11 |
| T10a | CT8 | C0 | pure fold output | — | — |
| T11 | CT10 | C1 | existing `pr_intent` suite green | — | — |
| T12 | CT3 | C1 | `observe`: events yes, context unchanged | — | P12/C |
| T13 | CT3 | C1 | `off`: zero events, byte-identical | — | P12/D |

**C4 / mutation handoff.** After C1/C2 green: (a) remove the ceremony injection call → T4 must fail;
(b) invert the `slice_ceremony.mode != "off"` branch → T13 must fail; (c) remove the verification
exec → T6 must fail; (d) remove `draft_tool_available` → T9 must fail. A survivor blocks shipped.

**LIVE-PATH PROOF — G1 (ceremony injection)**
- root: `fa workflow --roles planner,coder,eval` · matrix: A
- test: `scripts/run_live_check.sh s127-ceremony-inject` · oracle: event kind + fields
- kill-check: removing the `coder_loop.py` injection call fails the row
- producer: `coder_loop.py` slice branch · consumer: `observations.py:105` → `turn_context`
- paths-covered: 3/3 (P1,P2,P3) · contract-check: PASS required · pyramid: A

**LIVE-PATH PROOF — G3 (harness verification)**
- root: same · matrix: A
- test: `scripts/run_live_check.sh s127-harness-verify` · oracle: real `exit_code` in `verification_ran`
- kill-check: removing the exec call fails the row
- producer: `workflow_controller.py` post-coder step · consumer: verdict routing `:50-55` + next turn context
- paths-covered: 2/2 (P4,P5) · efficiency: bounded by `:345` deadline · pyramid: A

**LIVE-PATH PROOF — G6/CT9 (no chat deadlock)**
- root: `fa run --role chat` with `intent_guard_mode=enforce` · matrix: B
- test: `scripts/run_live_check.sh s127-chat-no-draft` · oracle: deny-reason **absent**, write succeeded
- kill-check: reverting `_requires_draft` fails the row
- producer: `intent_guard.py:226` · consumer: tool dispatch
- paths-covered: 2/2 (P8,P9) · pyramid: A

**Standing commands (operator runs on host, per repo rules).**
`uv sync --locked --extra dev`; `uv run pytest tests/test_skill_injection.py tests/test_intent_guard.py
tests/test_plan_ids.py tests/test_scope_warn.py tests/test_live_check_script.py`;
`scripts/adversarial_battery_live_check.sh`; then the three live rows above.
**After ANY edit:** `tests/test_live_check_script.py` + `scripts/adversarial_battery_live_check.sh`.

---

## 7. Risks, rollback, open questions (§10)

| RK# | risk | mitigation | detected by |
|---|---|---|---|
| RK1 | **Chat deadlock** if S8 lands partially (tool gone, guard still demanding) | CT9 + `draft_tool_available`; single commit | T9 (C3) |
| RK2 | `INJECT.md` drifts from `SKILL.md` | parity test | T2 |
| RK3 | Harness verification re-derives the exploration-log Q19 denial (8/10 commands blocked) | reuse `SandboxHook`, add no gate | T6 |
| RK4 | Ceremony injection bloats every coder turn | ~60 ln total; entry-turn full + anchor after | T4 + token check |
| RK5 | Extractor unreliable on legacy plans | advisory-only; blank ⇒ proceed | T3, S3 measurement |
| RK6 | Publication pushes to `main` or leaks the token | `DONE`-gated, session branch only, harness-side | T10 |
| RK7 | New injection breaks the prompt cache | `turn_context` only, never `system_prompt_extra` (D7) | T12 |
| RK8 | The plan recreates F6 (new rejection surface) | G8: no field rejected for absence; S5/S6/S7 all degrade to warnings | T6b, T7, T13 |

**ROLLBACK (P2+ required).** Flag `slice_ceremony.mode` — default `observe`, set `off` for a
byte-identical revert (T13 proves it). S8 is the only non-flagged change: revert = restore the
unconditional `registry.register` at `cli.py:1625` and the `IntentGuard` constructor arg. No data
migration; no persisted schema change.

**OPEN QUESTIONS — BLOCKING: none.**

| Q# | question | default (non-blocking) |
|---|---|---|
| Q1 | extractor conformance rate on conforming plans | Measured by S3 before S5 consumes it. Default: advisory-only regardless of rate; low rate ⇒ ID pre-fill dropped, ceremony still ships. |
| Q2 | condensate token cost | Measured in S1 via `context_budget.estimate_tokens`. Default: if either exceeds ~600 tokens, trim to the field skeleton. |
| Q3 | `awk` in the bash safe set (carried from F6 rev 2 C1) | Out of scope here; stays an independent defect (I-58). |
| Q4 | `ask_user` stop-rule tool | Backlogged (operator decision Q-op6). Seam only: `open_questions` + halt on blocking Q#. |

---

## 8. Research-note disposition (§11a)

| RN# | note item (source) | verdict | why | anchor |
|---|---|---|---|---|
| RN1 | Ceremony == `feature-planning:306-441` (F6 rev 4 §5.1) | **Accept** | Verified line-exact; all 7 elements map | S1 |
| RN2 | `SliceContract` typed artifact (F6 rev 3 §6.2) | **Reject** | Retracted rev 4; the packet is prose. Adds schema surface with no consumer | non-goal |
| RN3 | Commit fields derive from contract fields (rev 3 §5.5) | **Reject** | Refuted by `AP-003:152` — DoF-closed is per-change judgement, not derivable | §5.2 |
| RN4 | Force workflow onto `plan-authoring` only (operator) | **Reject** | ID grammars are identical (`feature-planning:120-132` ≡ `plan-authoring:161-181`); restriction would exclude the skill carrying the ceremony | CT6 |
| RN5 | `plan-authoring` lacks the gates (F6 rev 5 §5.3) | **Accept** | Verified: 1 grep hit total | S9 |
| RN6 | Inject full skills (rev 4 decision Q-op4) | **Rewrite** | Superseded by operator: `INJECT.md` condensates, ~60 ln vs ~970 | S1 |
| RN7 | Kill the extractor if any plan fails (rev 4 §5.7) | **Rewrite** | Operator: legacy non-conformance expected; measure, then decide | S3, Q1 |
| RN8 | fa publishes PRs (operator rev 5) | **Accept** | Harness-side, since `gh` ∉ whitelist | S10 |
| RN9 | Strip `pr_prepare` from chat (operator decision Q-op5) | **Accept** | Verified 8 prompt sites + 1 registration; **surfaced the CT9 deadlock** | S8 |
| RN10 | `should_load_skill` unwired (F6 rev 4) | **Accept** | Zero production callers confirmed | S5 |
| RN11 | Full re-verification each repair round | **Rewrite** | Targeted per round, full pass at slice boundary (agreed); `invalidated_steps` models it | S6 |
| RN12 | Rev 2 C1 bash safe-set widening | **Defer** | Independent defect I-58; not this plan | Q3 |
| RN13 | Rev 2 C2/C3/C4 (pre-fill, leniency, anchor-quality) | **Accept (absorbed)** | C2→S5, C3→G8, C4→S7 | S5,S7 |

---

## 9. Definition of Done (§11.3)

**STATE.** Before: operator pastes a ~30-line ceremony per slice; verification is model-narrated;
`pr_prepare` taxes chat; nothing publishes. After: with `mode=enforce`, a coder slice receives the
ceremony automatically, the harness executes the plan's verification commands and injects real
output, out-of-scope writes warn, chat carries no `pr_prepare`, and a completed pipeline publishes a
PR. Observe via the three live-check rows and the event log.

**ARTIFACTS.** See §11.

**CONTRACTS.** CT1–CT10 all `VERIFIED` (each has a T# and a kill-check).

**DONE when:** G1–G4, G6, G7 at **L3**; G5 at its contract L3 (advisory end-to-end); G8 holds
(T6b, T7, T13 prove degradation, not denial); all LIVE-PATH PROOF blocks green; matrix A–D covered;
non-goals respected; RN1–RN13 dispositioned; mutation handoff (a)–(d) shows no survivor.

---

## 10. Anti-theater + READY gate (§11.2, §11.4)

**Anti-theater checklist**
- [x] Every referenced symbol verified via preflight or marked **NEW**
- [x] Every G# maps to ≥1 CT#, ≥1 S#, ≥1 T# (G1→CT3/S5/T4 · G2→CT3/S5/T5 · G3→CT4/S6/T6 ·
      G4→CT5/S7/T7 · G5→CT6/S3/T3 · G6→CT7,CT9/S8/T8,T9 · G7→CT8/S10/T10 · G8→S5,S6,S7/T6b,T7,T13)
- [x] Every signal CT# (CT3,CT4,CT5,CT8) has BOTH producer and consumer named
- [x] Every kill-check targets the **PRODUCER**
- [x] Path inventory P1–P12: all covered (§4.1)
- [x] Matrix rows A–D: all have a covering step **and** a named verification
- [x] Dual-write (CT3: turn_context + event log) stated and same-branch
- [x] Real types at wiring boundaries (`SkillInjectionResult`, `FlowState`, `Decision`)
- [x] No vague verbs without a mechanism
- [x] Assumptions labeled (Q1, Q2 are measurements, not assertions)
- [x] Security contract CT9 has an adversarial case (T9, C3)
- [x] All IDs resolve — G1–G8, GAP1–GAP11, CT1–CT10, S1–S10, T1–T13 (17 incl. a/b), P1–P12, Q1–Q4, RK1–RK8, RN1–RN13. Machine-linted; the only non-plan IDs are explicitly labelled external (`S12.4 (external)` flag precedent, `exploration-log Q19`, `operator decision Q-op1..6`)

**READY gate**
- [x] Preflight log present and non-trivial
- [x] Depth **P2** declared (cross-module: skills, inner_loop, hooks, cli, hygiene; rollout-flagged)
- [x] Executive intent, non-goals, current/target state concrete
- [x] Contract subtypes: function (CT1,CT6) · signal (CT3,CT4,CT5,CT8) · data (CT2) ·
      invariant (CT7,CT10) · security (CT9) — all present
- [x] Path + matrix gates satisfied
- [x] Every step file:symbol specific with exit criteria
- [x] Verification plan + 3 LIVE-PATH PROOF blocks
- [x] Anti-theater checklist fully holds
- [x] Research notes dispositioned (RN1–RN13)
- [x] BLOCKING open questions: **EMPTY** (Q1–Q4 non-blocking, all carry defaults)
- [x] All IDs resolve

**STATUS: READY**

---

## 11. Artifacts inventory

| artifact | path | action | owner |
|---|---|---|---|
| ceremony condensate | `knowledge/skills/feature-planning/INJECT.md` | add | S1 |
| tests condensate | `knowledge/skills/tests-writing/INJECT.md` | add | S1 |
| single-file invariant | `knowledge/skills/skill-writing/SKILL.md:63` | edit | S1 |
| skills README | `knowledge/skills/README.md` | edit | S1 |
| skill loader | `src/fa/skills/_inject.py:216,224` | edit | S2 |
| skill trigger loader | `src/fa/skills/loader.py:119` | edit (wire) | S5 |
| plan ID extractor | `src/fa/inner_loop/plan_ids.py` | add | S3 |
| measurement script | `scripts/measure_plan_id_extraction.py` | add | S3 |
| feature flags | `src/fa/feature_flags.py:46,62,76,129,289` | edit | S4 |
| coder loop | `src/fa/inner_loop/coder_loop.py:773-800` | edit | S5 |
| workflow controller | `src/fa/inner_loop/workflow_controller.py:257-271` | edit | S6,S10 |
| scope hook | `src/fa/inner_loop/hooks/scope_warn.py` | add | S7 |
| intent guard | `src/fa/inner_loop/hooks/intent_guard.py:226` | edit | S8 |
| CLI wiring | `src/fa/cli.py:162,1625,1716` | edit | S7,S8 |
| chat prompts | `src/fa/inner_loop/prompt.py:525,571,645` | edit | S8 |
| PR publisher | `src/fa/hygiene/pr_publish.py` | add | S10 |
| operator instructions | `knowledge/instructions/02-operations.md` | edit | S9 |
| plan-authoring gates | `knowledge/skills/plan-authoring/SKILL.md` | edit | S9 |
| pr-creation skill | `knowledge/skills/pr-creation/SKILL.md` | edit | S9 |
| exploration log | `knowledge/trace/exploration_log.md` | edit | S9 |
| ADR | `knowledge/adr/ADR-<n>-slice-ceremony.md` | add | S9 |
| backlog | `worklogs/BACKLOG.md` | edit | S9 |
| tests | `tests/test_skill_injection.py`, `test_plan_ids.py`, `test_scope_warn.py`, `test_intent_guard.py`, `test_ceremony_injection.py`, `test_pr_publish.py` | add/edit | S2–S10 |
| live rows | `scripts/run_live_check.sh` (`s127-ceremony-inject`, `s127-harness-verify`, `s127-chat-no-draft`) | edit | S5,S6,S8 |
