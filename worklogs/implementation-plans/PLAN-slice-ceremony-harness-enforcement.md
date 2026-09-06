# PLAN: Harness-enforced per-slice implementation ceremony    Plan-ID: PLAN-slice-ceremony-harness-enforcement
Status: READY                                   Depth: P2
Revision: v3   Changed-since-v2: review pass 2 — D6 (`should_load_skill` would silently disable the ceremony), D7 (readiness text is role-agnostic), D8/D9/D10 resolved, D11 closed by new S6b (harness-derived draft). 12→13 steps. Delivery split into three PRs.   Changed-since-v1: adversarial self-review. **5 confirmed defects fixed** — D1 the injection site is chat-gated dead code for `coder` (S5 rewritten, S5a added); D2 the skill body rides `skills_conditional`, not `turn_context` (CT3/T4 oracle corrected); D3 `INJECT.md` without frontmatter loses its header/description (S1 corrected); D4 the controller cannot execute bash (S6 re-seated); D5 edit packets were never persisted, so the PR body had no source (S6a added). Step count 10→12.
**Delivery (operator decision, review pass 2): three sequenced PRs, not one.**
PR #68 keeps the S12.7 F1/F4/F7/F8/F9 fixes and merges on its own. Then:
**PR-A = S1–S4** (two docs, one defaulted kwarg, one pure module, one flag — no behaviour change,
independently verifiable); **PR-B = S5a, S5, S6a, S6, S6b, S7** (the wiring and the enforcement);
**PR-C = S8, S9, S10** (chat removal, docs, publication). This supersedes the earlier
"fold everything into #68" instruction, which predated the plan reaching 13 steps.

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
| `_is_chat_role` | `coder_loop.py:605` = `role == "chat" and bool(scope_mode)`. **Gates the entire boundary block at `:745`.** |
| `stage_kwargs` | `workflow_controller.py:272-284` — **no `scope_mode` key**, so a workflow stage always has `scope_mode=""`. |
| `skill_block` routing | `observations.py:168` → `ObservationRender.skill_block`; `coder_loop.py:802` → `skill_block_for_request` → `:961` `skills_conditional`. **Body never enters `turn_context`.** |
| `skills_conditional` placement | `prompt_composer.py:141-148` — appended to **`non_cacheable`**. Injection is therefore cache-safe (D7 satisfied). |
| `build_skill_block` | `_inject.py:163-190` — header/description come from **frontmatter**; `_ARGUMENT_HINT:62` keys on skill name. |
| controller imports | `workflow_controller.py:12-43` — no `subprocess`, no tool imports. **Cannot execute a command.** |
| edit-packet persistence | grep `packet` in `src/fa/` → **zero hits.** Model prose is not stored anywhere. |
| `_MISSING_DRAFT_REASON` | `intent_guard.py:138-141` — literally instructs "call `pr_prepare`". |

**Gold patterns mirrored**
- `tests/test_skill_injection.py:184-197` (`test_read_skill_from_temp_fixture`) — tmp-tree fixture,
  asserts frontmatter stripped and body present. The exact shape S2's tests mirror.
- `scripts/run_live_check.sh:569-588` — `s127_row` + `s127_expect` + `s127_finish` triad. New live
  rows mirror `cmd_s127_advancing` / `s127_assert_advancing`.

**Conflicts / invariants found**
0. **(D1, plan-breaking)** The L2 injection site is inside `if _is_chat_role:` (`coder_loop.py:745`), and
   `_is_chat_role` requires `role == "chat"` **and** a non-empty `scope_mode` (`:605`). The controller
   never passes `scope_mode` (`workflow_controller.py:272-284`). **v1's S5 targeted code the coder role
   never executes.** → S5 rewritten, S5a added.
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
| Producers/consumers | producer `read_skill_for_injection:216`; consumer `build_observation_block:105` → `skills_conditional` (`prompt_composer.py:141`). **Fires once per run, at L2 entry, planner skills only, and only when `_is_chat_role` (`coder_loop.py:605,745`)** |
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
| GAP3 | coder stage never injects a ceremony — the site is **chat-gated dead code** for `coder` (`coder_loop.py:605,745`) | S5a, S5 / T4 |
| GAP3b | `stage_kwargs` (`workflow_controller.py:272-284`) carries no signal a stage could use to enable ceremony injection | S5a / T4c |
| GAP4 | `tests-writing` never injected by any path | S5 / T5 |
| GAP4b | `should_load_skill:119` still has zero production callers — **explicitly NOT closed here** (D6); backlogged | S9 (backlog row) |
| GAP5 | verification is model-narrated; no harness execution | S6 / T6 |
| GAP6 | no files-allowed scope signal | S7 / T7 |
| GAP7 | `pr_prepare` registered for all roles (`cli.py:1625`) incl. chat | S8 / T8 |
| GAP8 | `_MISSING_DRAFT_REASON:138` names a tool chat will no longer have ⇒ deadlock | S8 / T9 |
| GAP9 | no plan-ID extraction | S3 / T3 |
| GAP10 | no PR publication path; `gh` not whitelisted (`bash_intent.py:62-99`) | S10 / T10 |
| GAP11 | `skill-writing:63` forbids the sibling file this plan adds | S1 / T2b |
| GAP12 | edit packets are never persisted (grep `packet` → 0 hits), so CT8's PR body has **no source data** | S6a / T14 |
| GAP13 | `workflow_controller.py:12-43` imports no executor; it cannot run a verification command | S6 / T6 |

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
- **SHAPE (D3, corrected):** `INJECT.md` **MUST carry minimal frontmatter** (`name:` + one-line
  `description:`). `build_skill_block` (`_inject.py:163-190`) derives the injected `# <name> — <desc>`
  header from frontmatter; `split_frontmatter` (`_inject.py:84-105`) returns `("", text)` for a file
  without it, so `description` would be empty and the header degenerate. v1's "no frontmatter" rule
  was wrong.
- **NAME COLLISION (D3b):** `name:` must be unique per condensate (`feature-planning-inject`,
  `tests-writing-inject`) — `build_skill_block` uses it for the header and `_ARGUMENT_HINT`
  (`_inject.py:62`) keys on it. Both new names need `_ARGUMENT_HINT` entries or they silently fall
  back to the generic hint.
- DETERMINISTIC MECHANISM: parity test T2 — every field label in `INJECT.md` appears in `SKILL.md`.
- FAILURE SURFACE: missing/empty `INJECT.md` ⇒ `SkillInjectionResult.warning`, run proceeds (CT1).

**CT3 — ceremony injection** *(signal, §6.2, TWO-SIDED)*
- PRODUCER: new `_ceremony_block_for_turn` branch in `coder_loop.py`, **outside** the `_is_chat_role`
  gate (D1), when `role == "coder"` ∧ `slice_ceremony.mode != off`. Paths P1, P2, P3.
- CONSUMER (D2, corrected): the **body** travels `ObservationRender.skill_block` (`observations.py:168`)
  → `skill_block_for_request` (`coder_loop.py:802`) → `skills_conditional` (`:961`) →
  `prompt_composer.py:141-148`, which appends it to **`non_cacheable`**. Only the short *anchor* is
  `turn_context`. **v1 asserted the body lands in `turn_context`; it does not.**
- CACHE SAFETY: because `skills_conditional` is non-cacheable (`prompt_composer.py:139-148`), D7 is
  satisfied structurally — no separate mitigation needed.
- MULTI-SKILL: `skills_conditional` is a **list** (`coder_loop.py:961`); v1's `[render.skill_block]`
  single-element construction (`:802`) must become a list of two condensates.
- DUAL-WRITE: `skills_conditional` (live) **and** event log (durable) written in the same branch.
- KILL-CHECK: remove the producer call at the S5 site ⇒ **T4** fails.
- SHIP RULE: producer proof before shipped.

**CT4 — harness-run verification** *(signal, §6.2, TWO-SIDED)*
- PRODUCER (D4, corrected): `run_verification(commands, workspace) -> tuple[VerificationResult, ...]`
  in **new** `src/fa/inner_loop/verification.py`, calling `_run_subprocess_fallback`
  (`tools/run_bash.py:219`). Invoked from `_run_stage` (`workflow_controller.py:310`) **after** the
  coder stage returns. Payload `{command, exit_code, stdout_tail, stderr_tail, duration_ms}`.
- **Why not "through SandboxHook" (v1's claim):** `SandboxHook` is a `BEFORE_TOOL_EXEC` middleware
  that gates *model-issued tool calls*; it is not an executor. The controller imports no subprocess
  facility at all (`workflow_controller.py:12-43`). v1's mechanism did not exist.
- **Why this is still safe:** the commands come from the operator's plan, not the model, so no
  model-controlled string reaches the shell. Exploration-log Q19 concerned *denying* model commands
  and does not apply — but the plan-sourced command list MUST be treated as trusted-input-only and
  never merged with model output (asserted by T6c).
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
- **INPUT (D5, corrected):** the body is folded from the `slice_packets.jsonl` artifact written by
  S6a. v1 said "fold accumulated edit packets" while nothing in the repo persists them
  (grep `packet` → 0 hits) — CT8 had no source data and was unbuildable as written.
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
3. **Add minimal frontmatter to each** (D3): `name:` + one-line `description:`. Names must be
   `feature-planning-inject` and `tests-writing-inject`. Without frontmatter `split_frontmatter`
   (`_inject.py:84-105`) yields an empty description and `build_skill_block` (`:181-183`) renders a
   degenerate `# <name> — <name>` header. **No `triggers:`/`globs:`** — those stay `SKILL.md`-only.
3b. Add `_ARGUMENT_HINT` entries (`_inject.py:62`) for both new names, else they fall back to the
   generic "Apply this skill to the current task now." hint.
4. Amend `skill-writing/SKILL.md:63` to: one `SKILL.md` **plus an optional derived `INJECT.md`**.

Do-not: do not paraphrase field names — parity is checked mechanically. Do not add `triggers:` or
`globs:`. Do not exceed 40 lines of **body** (frontmatter excluded).

Exit criteria:
- [ ] `test -f knowledge/skills/feature-planning/INJECT.md && test -f knowledge/skills/tests-writing/INJECT.md`
- [ ] `wc -l` ≤ 40 each
- [ ] each file starts with `---` and declares `name:` + `description:` (D3)
- [ ] `grep -n 'feature-planning-inject\|tests-writing-inject' src/fa/skills/_inject.py` shows both `_ARGUMENT_HINT` keys
- [ ] T2 parity passes; `grep -n "optional derived" knowledge/skills/skill-writing/SKILL.md` hits

---

### Step S2: Add the `file_name` parameter to the skill loader

Traces-to: G1 · GAP1 · CT1
Depends-on: none    Parallelizable-with: S1, S3
Target liveness: L1→L2

Edit:
- path: `src/fa/skills/_inject.py` symbol: `read_skill_for_injection:216` change: add `*, file_name: str = SKILL_FILE_NAME`; use it at `:224`
- path: `src/fa/skills/_inject.py` symbol: `_ARGUMENT_HINT:62` change: add hints for the two condensate names (S1 dependency)

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

### Step S5a: Carry a ceremony signal into the workflow stage (unblocks S5)

Traces-to: G1 · GAP3, GAP3b · CT3 · P1
Depends-on: S4    Parallelizable-with: S6a
Target liveness: L0→L2

**Why this step exists.** The L2 injection site sits inside `if _is_chat_role:`
(`coder_loop.py:745`), and `_is_chat_role` is `role == "chat" and bool(scope_mode)` (`:605`). The
controller's `stage_kwargs` (`workflow_controller.py:272-284`) has no `scope_mode`, so for a
workflow `coder` stage the flag is always False. **Without this step S5 edits code that never runs.**

Edit:
- path: `src/fa/inner_loop/workflow_controller.py` symbol: `_run_stage:272-284` change: add `"slice_ceremony": <mode>` to `stage_kwargs`
- path: `src/fa/cli.py` symbol: `_cmd_run` signature change: accept `slice_ceremony` and forward it to the coder loop
- path: `src/fa/inner_loop/coder_loop.py` symbol: `run_coder_loop` signature change: accept `slice_ceremony: str = "off"`

Degree of freedom closed: whether a stage receives ceremony context was implicitly tied to
`_is_chat_role`, a predicate about a *different* feature; it becomes an explicit stage argument.

Deterministic mechanism: `src/fa/inner_loop/workflow_controller.py:272-284` — an explicit
`stage_kwargs` key, defaulted `"off"`, so a caller that omits it gets today's behaviour exactly.

Do:
1. Thread the value controller → `_cmd_run` → `run_coder_loop`, mirroring how `scope_mode` is
   already threaded (`coder_loop.py:361,448,473`).
2. Default `"off"` at every hop; `argparse.Namespace` consumers use `getattr(args, "slice_ceremony", "off")`,
   mirroring the `resume` precedent (`cli.py:2161`).
3. Do **not** reuse or set `scope_mode` — that would switch on chat-only scope machinery
   (`observed_tiers`, `next_level`, escalation events) as a side effect.

Do-not: do not widen `_is_chat_role`. Do not make the coder stage look like a chat session.

Exit criteria:
- [ ] `grep -n "slice_ceremony" src/fa/inner_loop/workflow_controller.py src/fa/cli.py src/fa/inner_loop/coder_loop.py` hits all three
- [ ] T4c: a workflow coder stage receives `slice_ceremony="enforce"`; a chat run still receives `"off"`
- [ ] `scope_mode` is unchanged for every existing caller (T4d regression)

Kill-check: removing the `stage_kwargs` key makes **T4c** fail.

---

### Step S5: Inject the ceremony at coder-stage slice entry

Traces-to: G1, G2 · GAP3, GAP4 · CT3 · P1, P2, P3
Depends-on: S1, S2, S4, **S5a**    Parallelizable-with: none
Target liveness: L2→L3

Edit:
- path: `src/fa/inner_loop/coder_loop.py` symbol: new `_ceremony_block_for_turn` helper + call site **outside** the `if _is_chat_role:` block at `:745` change: when `role == "coder"` ∧ `slice_ceremony != "off"`, read both condensates and extend `skill_block_for_request`
- path: `src/fa/inner_loop/coder_loop.py` symbol: `:802` change: `skill_block_for_request` becomes a **list of N blocks**, not `[render.skill_block]`

Degree of freedom closed: which protocol text reaches the model at implementation time was the
operator's manual choice (paste or forget); it becomes a deterministic function of role, stage, and
turn index.

Deterministic mechanism: `src/fa/inner_loop/coder_loop.py` `_ceremony_block_for_turn` — condensates
read via `read_skill_for_injection(..., file_name="INJECT.md")` (CT1), appended to
`skill_block_for_request`, which `:961` passes as `skills_conditional`.

Do:
1. Declare `skill_block_for_request` (`:744`) as a list and **append** rather than replace, so the
   existing chat L2 block and the new ceremony blocks can coexist without either clobbering the other.
2. Full condensate bodies on the **slice-entry** turn (P1/P2); on later turns (P3) inject nothing
   into `skills_conditional` and emit only the short anchor via `turn_context`, mirroring
   `observations.py:152-158`.
3. Decide injection **directly** from `(role == "coder", slice_ceremony != "off", is_slice_entry)`.
   Do **not** route through `should_load_skill` (D6): it matches on `globs`/`triggers`
   (`loader.py:119-175`), and the condensates deliberately carry neither, so it would return
   **False** and the ceremony would never fire. GAP4 is closed by injecting `tests-writing-inject`
   directly, which is the outcome that was actually wanted.
4. Emit `ceremony_injected` in the **same branch** that appends the blocks — CT3 dual-write.
5. Wrap in `try/except` + `logger.warning`, mirroring `coder_loop.py:786-789`.
6. Plan absent (P2) ⇒ inject anyway with ID fields blank. **Never block** (G8).

Do-not: do not place the call inside `if _is_chat_role:` (D1 — it would never run for `coder`). Do
not add the body to `turn_context` (D2 — the body's channel is `skills_conditional`; `turn_context`
is capped at `OBSERVATION_CAP_CHARS` with eviction, `observations.py:171-184`, so a ~40-line body
would evict the verification and escalation lines). Do not inject on every turn.

Exit criteria:
- [ ] `grep -n 'file_name="INJECT.md"' src/fa/inner_loop/coder_loop.py`
- [ ] the injection call is **not** inside the `_is_chat_role` block: `awk 'NR>745 && /_ceremony_block_for_turn/' ` resolves outside that branch
- [ ] T4 asserts **two** entries in `skills_conditional` on the entry turn, anchor-only on turn 2
- [ ] T5 asserts the `tests-writing-inject` body is one of them
- [ ] T4b: a chat L2 run still receives its planner skill block (no regression from the list change)

Kill-check: removing the `_ceremony_block_for_turn` call makes **T4** fail.

---

### Step S6a: Persist edit packets (unblocks CT8)

Traces-to: G7 · GAP12 · CT8
Depends-on: S4    Parallelizable-with: S5a, S6
Target liveness: L0→L2

**Why this step exists.** CT8 folds "accumulated edit packets" into a PR body, but nothing in the
repo persists them — grep `packet` across `src/fa/` returns **zero hits**, and `StepResult`
(`workflow_artifacts.py:128-133`) has no field for model prose. v1's S10 had no input.

Edit:
- path: `src/fa/inner_loop/workflow_artifacts.py` symbol: new `SlicePacket` + `append_slice_packet` change: **NEW** append-only JSONL writer beside the existing artifacts

Degree of freedom closed: the record of what the model claimed to implement lived only in transient
chat history; it becomes a durable, append-only artifact keyed by run and slice.

Deterministic mechanism: `src/fa/inner_loop/workflow_artifacts.py` — `slice_packets.jsonl` written
through the existing atomic-write helper (`:510-549`), one JSON object per line.

Do:
1. `SlicePacket` frozen dataclass: `run_id`, `slice_id`, `turn`, `raw_text`, `verification`
   (the CT4 results for that slice).
2. Capture the model's packet **verbatim as text**. Do **not** parse it into fields — the packet is
   prose by design (rev 4), and a parser would recreate the F6 rejection surface (G8).
3. Append-only; a malformed or absent packet writes nothing and emits a WARNING. Never blocks.

Do-not: do not validate the packet's internal structure. Do not fail the slice when it is missing.

Exit criteria:
- [ ] `slice_packets.jsonl` exists after a coder slice, one line per packet
- [ ] T14: malformed packet ⇒ WARNING, run continues, no exception
- [ ] the file is readable by `build_pr_body` (S10) without further parsing

Kill-check: removing the append call makes **T14** fail and leaves S10's body empty.

---

### Step S6: Harness runs the verification commands

Traces-to: G3 · GAP5, GAP13 · CT4 · P4, P5
Depends-on: S3, S4    Parallelizable-with: S7, S6a
Target liveness: L0→L3

**Correction from v1 (D4).** v1 said "execute through the existing `SandboxHook` bash path". That
mechanism does not exist: `SandboxHook` (`builtin.py:87`) is a `BEFORE_TOOL_EXEC` middleware that
gates *model-issued tool calls*, not an executor, and `workflow_controller.py:12-43` imports no
subprocess facility.

Edit:
- path: `src/fa/inner_loop/verification.py` symbol: `VerificationResult`, `run_verification` change: **NEW** thin wrapper over `_run_subprocess_fallback` (`tools/run_bash.py:219`)
- path: `src/fa/inner_loop/workflow_controller.py` symbol: `_run_stage:310` change: after a `coder` stage returns, run the plan's commands and record results

Degree of freedom closed: whether a verification actually ran was the model's word — it could
narrate a green run it never executed; execution now happens in harness code the model cannot
reach, and the exit code is recorded verbatim.

Deterministic mechanism: `src/fa/inner_loop/verification.py:run_verification` — returns a typed
`VerificationResult` carrying the real integer `exit_code`; the controller records it and routes on
it, so no model-authored string can stand in for a result.

Do:
1. Commands come from the **plan** (extracted, S3) — never from model output. This is what makes the
   gate trustworthy: the operator authored them.
2. Reuse `_run_subprocess_fallback` (`tools/run_bash.py:219`) rather than a fresh `subprocess.run`,
   so timeout/decoding/CR-normalisation behaviour stays identical to the model-facing bash tool.
3. Enforce a per-command timeout (`bash_timeout_seconds`) **and** check the run deadline
   (`workflow_controller.py:345`) between commands; a hung verification must not consume the budget.
4. Inject `{command, exit_code, stdout_tail, stderr_tail}` into the next stage's context.
5. Non-zero ⇒ `REPAIR_REQUIRED` (`:50-55`). P5 (no commands) ⇒ record `skipped: true`, do **not**
   block (G8).

Do-not: do not let the model supply, extend, or edit the command list (T6c asserts this). Do not add
a new sandbox gate — exploration-log Q19 (`builtin.py:112-127`) showed a stricter gate denies 8/10
real verifier commands. Do not run commands for non-`coder` stages.

Exit criteria:
- [ ] `verification_ran` event carries a real integer `exit_code`
- [ ] T6: seeded failing command ⇒ `REPAIR_REQUIRED`, and the next turn's context contains the real stderr text
- [ ] T6b: P5 ⇒ `skipped: true`, run continues
- [ ] T6c: a command string present in model output but absent from the plan is **never** executed
- [ ] T6d: a command exceeding the timeout is killed and recorded as failed, not hung

Kill-check: removing the `run_verification` call makes **T6** fail (no event, no exit code).

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
- path: `src/fa/cli.py` symbol: `_READINESS_PROMPT_EXTRA:159-164`, `_readiness_prompt_extra:167` change: **role-parameterise** (D7) — keep the `pr_prepare` clause for non-chat roles, omit it for chat. `cli.py:2251` appends this for **every** role, so an unconditional edit would strip the instruction from `coder`, which still has the tool
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
3. Strip the chat-facing prompt sites only. **Leave coder/planner/eval prompts alone** — verified: `_readiness_prompt_extra` is role-agnostic today (`cli.py:2251`).
4. Re-check `prompt.py:20,22,24,822,854` — remove only chat-role text.

Do-not: do not delete `prepare_pr.py`. Do not touch `pr_intent.py` (CT10). Do not change the
`enforce` default.

Exit criteria:
- [ ] `pr_prepare ∉ chat registry names`; `∈ coder registry names` (T8)
- [ ] **T9 (C3 adversarial):** chat + `enforce` + `fs_write_file` ⇒ **not** denied with `_MISSING_DRAFT_REASON`
- [ ] `grep -c pr_prepare` on the chat prompt path == 0; **non-chat roles still receive it** (T8b)
- [ ] **Per-file test disposition (D9)** recorded for all ten files referencing `pr_prepare`: chat-specific assertions deleted, role-agnostic ones untouched, `coder`-side replacements added
- [ ] **D10 check:** conformance suite re-run and `tests/data/windows-baseline-2026-08-02.txt` confirmed unchanged (S8 keeps `pr_prepare` for `coder`)
- [ ] reversal recorded in `knowledge/trace/exploration_log.md` (S9), and the replacement test's docstring cites this plan
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
Depends-on: S1–S8, **S6a** (packet source)    Parallelizable-with: S9
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
1. `build_pr_body(packets, plan_links) -> str` — **pure**, deterministic fold over the
   `slice_packets.jsonl` rows written by S6a (D5). Frontmatter
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
| T4 | CT3 | **C1** | event `ceremony_injected` + **2 entries in `skills_conditional`** (D2) | `_ceremony_block_for_turn` call | P1,P2,P3 |
| T4b | CT3 | C1 | chat L2 run still receives its planner block (list-change regression) | `:802` list build | — |
| T4c | CT3 | C1 | workflow coder stage receives `slice_ceremony="enforce"` | `stage_kwargs` key | P1 |
| T4d | CT3 | C1 | `scope_mode` unchanged for all existing callers | — | — |
| T5 | CT3 | C1 | `tests-writing` body in context | second condensate read | P1 |
| T6 | CT4 | **C1** | event kind + real `exit_code` | verification exec call | P4 |
| T6b | CT4 | C1 | `skipped: true`, run continues | — | P5 |
| T6c | CT4 | **C3** | model-authored command never executed | plan-only command source | P4 |
| T6d | CT4 | C1 | timeout ⇒ recorded failure, not hang | timeout arg | P4 |
| T7 | CT5 | C1 | `scope_warning` event **+ write succeeded** | the emit | P6,P7 |
| T7b | CT5 | C0 | static: zero `Decision.deny` in the module | — | P7 |
| T8 | CT7 | C2 | registry `names()` per role | conditional registration | P9 |
| T9 | CT9 | **C3** | absence of `_MISSING_DRAFT_REASON` deny | `draft_tool_available` branch | P8 |
| T10 | CT8 | C1 | `pr_published` event + body file | `publish_pr` call | P10,P11 |
| T10a | CT8 | C0 | pure fold output | — | — |
| T8b | CT7 | C1 | non-chat roles still receive the `pr_prepare` readiness clause (D7) | role-parameterised extra | P9 |
| T11 | CT10 | C1 | existing `pr_intent` suite green | — | — |
| T15 | CT11 | **C3** | packet says IMPLEMENT + diff deletes a test ⇒ **blocked** | classifier-intent call site | P4 |
| T16 | CT11 | C1 | absent packet ⇒ guard denies as today (fail-closed) | `write_text` call | P4 |
| T14 | CT8 | C1 | `slice_packets.jsonl` written; malformed ⇒ WARNING only | append call | P10 |
| T12 | CT3 | C1 | `observe`: events yes, context unchanged | — | P12/C |
| T13 | CT3 | C1 | `off`: zero events, byte-identical | — | P12/D |

**C4 / mutation handoff.** After C1/C2 green: (a) remove the `_ceremony_block_for_turn` call → T4 must fail; (a2) remove the `stage_kwargs` key → T4c must fail;
(b) invert the `slice_ceremony.mode != "off"` branch → T13 must fail; (c) remove the verification
exec → T6 must fail; (d) remove `draft_tool_available` → T9 must fail. A survivor blocks shipped.

**LIVE-PATH PROOF — G1 (ceremony injection)**
- root: `fa workflow --roles planner,coder,eval` · matrix: A
- test: `scripts/run_live_check.sh s127-ceremony-inject` · oracle: event kind + fields (**not** `turn_context` text — D2)
- kill-check: removing the `coder_loop.py` injection call fails the row
- producer: `coder_loop.py:_ceremony_block_for_turn` · consumer: `skills_conditional` (`prompt_composer.py:141-148`, non-cacheable)
- paths-covered: 3/3 (P1,P2,P3) · contract-check: PASS required · pyramid: A

**LIVE-PATH PROOF — G3 (harness verification)**
- root: same · matrix: A
- test: `scripts/run_live_check.sh s127-harness-verify` · oracle: real `exit_code` in `verification_ran`
- kill-check: removing the exec call fails the row
- producer: `verification.py:run_verification` called from `workflow_controller.py:310` · consumer: verdict routing `:50-55` + next turn context
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
| RK9 | **S5a threads a new arg through 3 layers**; a missed hop silently disables the feature | default `"off"` at every hop + T4c asserts arrival at the coder loop, not just departure | T4c |
| RK10 | Harness-executed commands are a **new code-execution surface** not gated by SandboxHook | plan-sourced only, never model-sourced (T6c); per-command timeout (T6d); coder stage only | T6c, T6d |
| RK12 | Harness-derived draft is read as forging agent provenance | it asserts the *harness's* own provenance (`pr_draft.py:46-51`); test-protection stays keyed on the staged diff (`pr_intent.py:519-526`) | T15 |
| RK13 | Deleting chat tests erases a documented decision | reversal recorded in exploration_log + replacement docstring cites this plan (D8) | S8 exit criteria |
| RK11 | `skill_block_for_request` list change clobbers the existing chat L2 block | append, never replace; T4b is the regression guard | T4b |

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
- [x] Every G# maps to ≥1 CT#, ≥1 S#, ≥1 T# (G1→CT3/S5a,S5/T4,T4c · G2→CT3/S5/T5 · G3→CT4/S6/T6,T6c ·
      G4→CT5/S7/T7 · G5→CT6/S3/T3 · G6→CT7,CT9/S8/T8,T9 · G7→CT8/S6a,S10/T10,T14 · G8→S5,S6,S7/T6b,T7,T13)
- [x] Every signal CT# (CT3,CT4,CT5,CT8) has BOTH producer and consumer named
- [x] Every kill-check targets the **PRODUCER**
- [x] Path inventory P1–P12: all covered (§4.1)
- [x] Matrix rows A–D: all have a covering step **and** a named verification
- [x] Dual-write (CT3: turn_context + event log) stated and same-branch
- [x] Real types at wiring boundaries (`SkillInjectionResult`, `FlowState`, `Decision`)
- [x] No vague verbs without a mechanism
- [x] Assumptions labeled (Q1, Q2 are measurements, not assertions)
- [x] Security contracts have adversarial cases: CT9→T9 (C3), CT4→T6c (C3, command-injection boundary)
- [x] All IDs resolve — G1–G8, GAP1–GAP13, CT1–CT10, S1–S10 + S5a/S6a (12 steps), T1–T14 (23 incl. a–d), P1–P12, Q1–Q4, RK1–RK11, RN1–RN13. Machine-linted; the only non-plan IDs are explicitly labelled external (`S12.4 (external)` flag precedent, `exploration-log Q19`, `operator decision Q-op1..6`)

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

**Post-review note.** v1 passed this same gate while containing 5 defects, three of which
(D1, D4, D5) would have made steps unimplementable as written. The gate is necessary, not
sufficient: it checks *internal* consistency, and every one of these defects was an *external*
mismatch with real code that only reading the callers exposed. The v2 additions (S5a, S6a) both
exist because a "wire it up" step assumed a seam that was not there.

**STATUS: READY**

---

---

## 12. Review pass 2 — findings (v3, awaiting operator decision on D8/D10/D11)

**Confirmed defects, fixed in place**

**D6 — `should_load_skill` is the wrong tool for S5, and wiring it is theater.**
`should_load_skill(skill_path, current_files, task_text)` (`loader.py:119-175`) decides *whether* a
skill matches, by glob/trigger/`alwaysApply`. But S5 already knows the answer deterministically:
role is `coder`, mode is on, so the ceremony applies. Routing a known decision through a
fuzzy matcher adds a failure mode (a trigger-phrase miss silently disables the ceremony) and buys
nothing. Worse, `INJECT.md` deliberately carries no `triggers:`/`globs:` (S1/D3), so
`should_load_skill` would return **False** for both condensates and the feature would never fire.
→ **S5 no longer calls `should_load_skill`.** GAP4 is closed by *injecting `tests-writing-inject`
directly*, not by wiring the matcher. Wiring it stays a separate backlog item, honestly labelled.

**D7 — `_READINESS_PROMPT_EXTRA` is not chat-only; S8 as written breaks every role.**
`cli.py:2251` appends `_readiness_prompt_extra(workspace)` to `system_prompt_extra` for **all**
roles — it is not role-conditional. v1/v2's S8 said "drop the `pr_prepare` sentence"; doing that
removes the instruction from `coder` too, which still has the tool and still needs it. → S8 now
makes the readiness text **role-parameterised**, keeping the `pr_prepare` clause for non-chat roles.

**Operator decisions (review pass 2)**

**D8/D9 — resolved: delete the chat-specific assertions.** `tests/test_chat_role.py:184-203` and the
chat-side assertions in `test_cli.py` assert *what is*, not *what should be*; the plan supersedes
them. **Mitigation for the one real cost** (a reviewer later cannot tell the reversal was
deliberate): the deletion is not silent — S8 records the reversal in
`knowledge/trace/exploration_log.md` (S9) and the replacement `coder`-side test carries a docstring
naming this plan. Per-file disposition is now an S8 exit criterion; ten files reference the tool and
most are role-agnostic and stay untouched.

**D10 — resolved as a check, not a change.** `cli.py:2734` builds a **`coder`** registry for the
conformance suite and S8 keeps `pr_prepare` for `coder`, so the pinned corpus
(`tests/data/windows-baseline-2026-08-02.txt`) should be unaffected. S8 must *re-run and confirm*
rather than assume — added as an exit criterion, not a code change.

**D11 — resolved: the harness derives the draft; the model never calls `pr_prepare` in the pipeline.**
This is the "derive, don't merge" principle (F6 rev 4 §5.5) finally applied to the enforcement seat.
After S6a captures the packet, the harness writes the draft itself via `PrDraftStore.write_text`
(`pr_draft.py:68`), which sets `_current_digest` and therefore satisfies
`read_current_text()` (`:75-91`) — `IntentGuard` is satisfied with **zero model turns**. → new **S6b**.

*Security review of this choice (it is the risky one, so it is argued explicitly):*
- The trust model is **not** weakened. `_current_digest` proves "this process wrote it and the file
  is unmodified" (`pr_draft.py:46-51`). A harness-written draft satisfies that honestly — the
  harness *is* the current process. This is not forging agent provenance; it is the harness
  asserting its own.
- **The test-protection rule stays armed.** `validate_test_edits` is called with
  `classify_intent(projected)` — the intent derived from the **staged diff**, never the draft's typed
  value (`intent_guard.py:341`, security invariant at `pr_intent.py:519-526`). A model that writes a
  misleading packet still cannot delete a test: deletion violates "under EVERY intent shape"
  (`pr_intent.py:508-512`), and the diff, not the packet, decides.
- **Residual risk (named, not hidden):** the packet's `INTENT:` becomes the typed D-5 override, which
  governs *shape* checks. A model could soften shape validation by mis-declaring intent — but that
  is exactly today's exposure with a model-authored `pr_prepare` call, so the change is
  risk-neutral, not risk-increasing. **T15** pins it.
- **Failure mode:** if the packet is missing/unparseable, the harness writes **no** draft and the
  guard behaves exactly as today (deny + `_MISSING_DRAFT_REASON`). Fail-closed, no new bypass.

---

### Step S6b: Harness-derived PR draft (closes the double-ceremony, D11)

Traces-to: G3, G8 · CT4, CT11 · P4
Depends-on: S6a    Parallelizable-with: S7
Target liveness: L0→L3

Edit:
- path: `src/fa/inner_loop/verification.py` symbol: `derive_draft_from_packet` change: **NEW** pure `SlicePacket -> str` renderer producing `INTENT:`/`CLASS:`/`INVARIANT:` (+ FIX clauses)
- path: `src/fa/inner_loop/workflow_controller.py` symbol: post-coder step change: call `PrDraftStore.write_text` with the derived text before the coder stage's first mutation

Degree of freedom closed: the model could previously satisfy the mutation gate with a draft
unrelated to the work it was about to do (`invariant: "n/a"` passed — F6 evidence); the draft is now
**derived from the packet the ceremony already required**, so the two cannot disagree.

Deterministic mechanism: `src/fa/inner_loop/verification.py:derive_draft_from_packet` — a pure
function; the guard's own validators (`validate_commit_msg`, `validate_test_edits`) remain the
authority and are unchanged (CT10).

Do:
1. Render the commit-note fields from the packet. `DETERMINISTIC MECHANISM` maps from the packet's
   kill-check target (a `path:line`), satisfying the citation rule by construction.
2. Write via `PrDraftStore.write_text` (`pr_draft.py:68`) — never touch `_current_digest` directly.
3. **No packet ⇒ write nothing.** The guard then denies exactly as today (fail-closed).
4. Pipeline coder stages only. Chat is untouched (it has no tool after S8 and no ceremony).

Do-not: do not pass the packet's typed intent to `validate_test_edits` (`pr_intent.py:519-526`). Do
not synthesise a draft when the packet is absent. Do not modify `pr_intent.py` (CT10).

Exit criteria:
- [ ] a pipeline coder slice mutates the workspace with **zero** `pr_prepare` tool calls
- [ ] T15: a packet declaring `IMPLEMENT` while the diff deletes a test is **still blocked**
- [ ] T16: absent packet ⇒ guard denies as today (fail-closed, no bypass)
- [ ] `grep -c "pr_intent" src/fa/inner_loop/verification.py` == 0 (validators untouched)

Kill-check: removing the `write_text` call makes **T16**'s counterpart (the zero-`pr_prepare` slice) fail.

---

**CT11 — harness-derived draft** *(security, §6.5 — adversarial case required)*
- BOUNDARY: draft provenance and the test-protection rule.
- INVARIANT: a harness-written draft satisfies `IntentGuard` **without** weakening
  `validate_test_edits`, which stays keyed on classifier intent from the staged diff.
- ADVERSARIAL CASE (C3, **T15**): packet claims `IMPLEMENT`; diff deletes `tests/test_x.py`.
  Must be **blocked** (`pr_intent.py:508-512`).


## 11. Artifacts inventory

| artifact | path | action | owner |
|---|---|---|---|
| ceremony condensate | `knowledge/skills/feature-planning/INJECT.md` | add | S1 |
| tests condensate | `knowledge/skills/tests-writing/INJECT.md` | add | S1 |
| single-file invariant | `knowledge/skills/skill-writing/SKILL.md:63` | edit | S1 |
| skills README | `knowledge/skills/README.md` | edit | S1 |
| skill loader | `src/fa/skills/_inject.py:216,224` | edit | S2 |
| plan ID extractor | `src/fa/inner_loop/plan_ids.py` | add | S3 |
| measurement script | `scripts/measure_plan_id_extraction.py` | add | S3 |
| feature flags | `src/fa/feature_flags.py:46,62,76,129,289` | edit | S4 |
| coder loop | `src/fa/inner_loop/coder_loop.py:744,802,961` + new helper | edit | S5, S5a |
| verification runner | `src/fa/inner_loop/verification.py` | add | S6 |
| slice packet artifact | `src/fa/inner_loop/workflow_artifacts.py` | edit | S6a |
| workflow controller | `src/fa/inner_loop/workflow_controller.py:272-284,310` | edit | S5a,S6,S10 |
| scope hook | `src/fa/inner_loop/hooks/scope_warn.py` | add | S7 |
| intent guard | `src/fa/inner_loop/hooks/intent_guard.py:226` | edit | S8 |
| CLI wiring | `src/fa/cli.py:162,1625,1716` + `_cmd_run` signature | edit | S5a,S7,S8 |
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
