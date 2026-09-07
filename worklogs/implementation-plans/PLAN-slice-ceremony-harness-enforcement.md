# PLAN: Harness-enforced per-slice implementation ceremony    Plan-ID: PLAN-slice-ceremony-harness-enforcement
Status: READY                                   Depth: P2
Revision: v7   Changed-since-v6: review pass 6 — default mode for ALL injections is `observe` (restores §2 l.179, which S5a had drifted from); source attribution switched from value-inference to declaration; ADR-10 Amendment 2026-09-07 (I-6) seats injected prompt payloads normatively.   Changed-since-v5: review pass 5 — Q9 resolved (b): chat-nested pipelines inherit `--inject` through `WorkflowInvocationContext`; G9 promoted from deferred into scope as `fa inject list/status` with source attribution. New steps S5c, S5d; new contracts CT16, CT17, CT18.   Changed-since-v3: external adversarial review — F-1 (verification commands had no producer; added ```verify grammar), F-2 (pinned the draft-extraction contract; INTENT never guessed), F-3 (late-binding placement), F-4 (honest L3 scoping), F-5a (no private-function reuse), F-5b (refuted — `fa run` defaults to coder). **S10 removed from scope (D-1).** 13 steps → 12 in scope.   Changed-since-v2: review pass 2 — D6 (`should_load_skill` would silently disable the ceremony), D7 (readiness text is role-agnostic), D8/D9/D10 resolved, D11 closed by new S6b (harness-derived draft). 12→13 steps. Delivery split into three PRs.   Changed-since-v1: adversarial self-review. **5 confirmed defects fixed** — D1 the injection site is chat-gated dead code for `coder` (S5 rewritten, S5a added); D2 the skill body rides `skills_conditional`, not `turn_context` (CT3/T4 oracle corrected); D3 `INJECT.md` without frontmatter loses its header/description (S1 corrected); D4 the controller cannot execute bash (S6 re-seated); D5 edit packets were never persisted, so the PR body had no source (S6a added). Step count 10→12.
**Delivery (operator decision, review pass 2): three sequenced PRs, not one.**
PR #68 keeps the S12.7 F1/F4/F7/F8/F9 fixes and merges on its own. Then:
**PR-A = S1–S4** (two docs, one defaulted kwarg, one pure module, one flag — no behaviour change,
independently verifiable); **PR-B = S5a, S5, S6a, S6, S6b, S7** (the wiring and the enforcement);
**PR-C = S8 + S9** (chat removal + docs). **S10 (PR publication) is REMOVED from this plan** —
see §13 D-1. This supersedes the earlier "fold everything into #68" instruction, which predated the
plan reaching 13 steps.

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
(backlogged); **PR publication (G7/CT8/S10 — moved to its own plan, D-1);** replacing the git-hook commit validator; changing `pr_intent.py` validation logic;
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
- New feature flag `injections.coder_slice_ceremony.mode` = `off | observe | enforce`, **default `observe`**.
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
- PRODUCER: new `should_inject_ceremony`/`_ceremony_blocks` branch in `coder_loop.py`, **outside** the `_is_chat_role`
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
- **COMMAND SOURCE (F-1, option (a)):** `PlanIds` carries a new field
  `commands: tuple[str, ...]`, extracted by CT6 from a **fenced `verify` block** in the plan's §6
  (verification) section. Grammar, pinned here and mirrored into both planning skills (S9):

  ````text
  ```verify
  uv run pytest tests/test_plan_ids.py -q
  uv run mypy src/fa/inner_loop/plan_ids.py
  ```
  ````

  Rationale: `T#` is a **taxonomy label** (`feature-planning:267-278` — C0/C0p/C1/C2/C3/C4), not a
  runnable string, and no existing plan carries a command column (verified: zero `uv run` hits in
  `PLAN-complexity-aware-execution-chat-role.md`). Extracting `T#` IDs and hoping they are commands
  was a producer-less consumer — the same defect class as D5.
- PRODUCER (D4, corrected): `run_verification(commands, workspace) -> tuple[VerificationResult, ...]`
  in **new** `src/fa/inner_loop/verification.py`, calling `_run_subprocess_fallback`
  (`tools/run_bash.py:219`). Invoked from `_run_stage` (`workflow_controller.py:_run_stage`) **after** the
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
- SHIP RULE: **L3 for plans carrying a ```verify block.** (F-4, honest scoping.) A plan without one
  yields `commands=()` → `skipped: true`, so end-to-end plan→verify is **not** proven for
  non-conforming plans. T6e proves the real path (plan text → extract → execute); T6's seeded list
  proves only the executor. Stated here rather than claiming an unqualified L3.

**CT5 — files-allowed scope warning** *(signal, §6.2)*
- PRODUCER: new `ScopeWarnHook` at `BEFORE_TOOL_EXEC` (**TO ADD**, S7). Emits `scope_warning`
  `{path, allowed: tuple[str,...]}` when a write path ∉ allowed set. **Always `Decision.allow`.**
- CONSUMER: event log + live-check assertion.
- KILL-CHECK: remove the emit ⇒ **T7** fails.
- INVARIANT: never returns `deny`. Asserted directly by T7b (operator decision Q-op4).

**CT6 — plan ID extraction** *(function, §6.1)*
- `extract_plan_ids(text: str) -> PlanIds` where `PlanIds` is a frozen dataclass of
  `slices/gaps/contracts/tests: tuple[str, ...]` **plus `commands: tuple[str, ...]`** (F-1).
- `commands` come from fenced ```verify blocks only. **No command is ever inferred from prose** —
  an un-fenced plan yields `commands=()` and S6 records `skipped: true` (P5), never a guess.
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

**CT7b — `pr_prepare` retained for `coder` is load-bearing, not dead weight** *(invariant, F-5)*
- The reviewer suspected it survives only for a path that may not exist. **Verified: it does exist.**
  `fa run --role` **defaults to `coder`** (`cli.py:542-546`), so `fa run` with no `--role` is a
  standalone coder session with no workflow controller and therefore no S6b deriver. Removing the
  tool there would reintroduce the CT9 deadlock on the default invocation.
- Confirmed by T8 (present for `coder`) and T8b (readiness clause retained for non-chat roles).

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
2. `extract_plan_ids(text)` — patterns for `### S<n>:`, `GAP<n>`, `CT<n>`, `T<n>`, **and fenced
   ```verify blocks → `commands`** (F-1). No FS, no LLM.
3. Unparseable/empty input ⇒ all-empty `PlanIds`. **Never raise.**
4. Measurement script: run over every file in `worklogs/implementation-plans/`, print a per-plan
   pass/fail table **split conforming (post-skill) vs legacy**, and a summary rate.

Do-not: do not call an LLM. Do not read the FS from the module. Do not fail the build on a low rate —
legacy misses are expected (operator decision Q-op5) and recorded, not gating.

Exit criteria:
- [ ] `python3 scripts/measure_plan_id_extraction.py` prints the split table
- [ ] measured rate on **conforming** plans recorded in this plan's §7 Q1 row
- [ ] T3 green including the empty-input and garbage-input cases
- [ ] T3b green: a plan with no ```verify block yields `commands=()` (and S6 then skips, never guesses)

Kill-check: deleting the `### S<n>:` pattern makes **T3** fail.

---

### Step S4: Feature flag `injections.coder_slice_ceremony.mode`

Traces-to: G1, G8 · CT3 · matrix C, D
Depends-on: none    Parallelizable-with: S1–S3
Target liveness: L0→L2

Edit:
- path: `src/fa/feature_flags.py` symbol: `FeatureFlags` (beside `intent_guard_mode`) change: add `coder_slice_ceremony_mode: str = "observe"`; register in the config mapping (key `injections.coder_slice_ceremony.mode`), the defaults list, the type map, and the loader — **SHIPPED**: `feature_flags.py:57,74,111`

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
- path: `src/fa/inner_loop/coder_loop.py` symbol: new `should_inject_ceremony`/`_ceremony_blocks` helper + call site **outside** the `if _is_chat_role:` block at `:745` change: when `role == "coder"` ∧ `slice_ceremony != "off"`, read both condensates and extend `skill_block_for_request`
- path: `src/fa/inner_loop/coder_loop.py` symbol: `:802` change: `skill_block_for_request` becomes a **list of N blocks**, not `[render.skill_block]`

Degree of freedom closed: which protocol text reaches the model at implementation time was the
operator's manual choice (paste or forget); it becomes a deterministic function of role, stage, and
turn index.

Deterministic mechanism: `src/fa/inner_loop/coder_loop.py` `should_inject_ceremony`/`_ceremony_blocks` — condensates
read via `read_skill_for_injection(..., file_name="INJECT.md")` (CT1), appended to
`skill_block_for_request`, which `:961` passes as `skills_conditional`.

**Placement (F-3 — pinned, not left to the implementer).** `_compose_request_payload` is
re-defined **every turn** inside the turn loop, and `skills_conditional_value` is bound as a
**default arg** at definition time (`coder_loop.py:958-961`, the documented B023 late-binding
pattern). So the assignment must happen **inside the per-turn loop, before
`_compose_request_payload` is re-defined** — "outside the `_is_chat_role` block" is necessary but
not sufficient. It must also **reset to `None` on non-entry turns**, mirroring the chat block's
"None on every non-entry turn" comment (`:959-960`); otherwise the full body is re-sent every turn.

Do:
1. Declare `skill_block_for_request` (`:744`) as a list and **append** rather than replace, so the
   existing chat L2 block and the new ceremony blocks can coexist without either clobbering the other.
1b. Assign inside the turn loop before the `_compose_request_payload` re-definition; reset to `None`
   on non-entry turns (F-3).
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
- [ ] the injection call is **not** inside the `_is_chat_role` block, **and** sits inside the turn
      loop above the `_compose_request_payload` definition (`:955`) — F-3
- [ ] T4e: on a non-entry turn `skills_conditional` is `None`/absent (no per-turn body resend)
- [ ] T4 asserts **two** entries in `skills_conditional` on the entry turn, anchor-only on turn 2
- [ ] T5 asserts the `tests-writing-inject` body is one of them
- [ ] T4b: a chat L2 run still receives its planner skill block (no regression from the list change)

Kill-check: removing the `should_inject_ceremony`/`_ceremony_blocks` call makes **T4** fail.

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
- path: `src/fa/inner_loop/workflow_controller.py` symbol: `_run_stage` change: **call site** — after a coder stage completes, append the packet

**Producer seam (gap found in review).** v7 defined the writer but never said
who calls it, so `append_slice_packet` would have shipped with zero callers and
S6b/S10 would still have had no input. The packet text is the model's own
turn output, and the controller already has it: the outcome sink is populated
for **every** role (`workflow_controller.py:315`, "D5: the sink is passed for
EVERY role"), and the eval path already reads `sink[-1].final_text` (`:350`).
Both anchors re-verified at the tip after this review's own edits. S6a
uses the same accessor after a coder stage.

Consequences:
- Empty `final_text` (tool-only turn) ⇒ append nothing, no warning. This is the
  normal case for most turns, not an error.
- The packet is written **per coder stage**, not per edit, even though the
  ceremony asks for one packet per edit. This is a known lossy simplification:
  a multi-edit turn yields one blob. Recorded rather than hidden, because
  splitting prose into per-edit records would need the parser G8 forbids.

Degree of freedom closed: the record of what the model claimed to implement lived only in transient
chat history; it becomes a durable, append-only artifact keyed by run and slice.

Deterministic mechanism: `src/fa/inner_loop/workflow_artifacts.py` —
`slice_packets.jsonl`, one JSON object per line.

**⚠ CONFIRMED DEFECT (§24 D-2): the stated mechanism is impossible.** v7 said
"append-only JSONL written through the existing atomic-write helper
(`:510-549`)". The helper is `_write_json_atomic` at **`:539`** (not
`:510-549`) and it ends in `os.replace(temp_path, path)` — a whole-file
**overwrite**. Routing an append through it would truncate the file to the
newest packet on every call, silently destroying every earlier one, while
looking correct in any test that writes a single packet.

**Corrected mechanism.** Append with `open(path, "a", encoding="utf-8")` and
one `json.dumps(...) + "\n"` per record. On POSIX a single `write()` under
`O_APPEND` below `PIPE_BUF` is atomic, which is the right guarantee for an
append-only log; whole-file atomic replace is the wrong tool. Create the
parent directory first (`_write_json_atomic` does this and an appender must
too). Do **not** add a second atomic-write helper.

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
- [ ] the file is readable by S6b's `derive_draft_from_packet` without further parsing (S10 moved out under D-1, so S6b is the in-scope consumer)

Kill-check: removing the append call makes **T14** fail and leaves S6b with no input.

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
- path: `src/fa/inner_loop/verification.py` symbol: `VerificationResult`, `run_verification` change: **NEW** dedicated runner reusing `build_scrubbed_env` + timeout/decode policy (F-5); **not** `_run_subprocess_fallback`
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
2. **Do not call `_run_subprocess_fallback`** (F-5). It is module-private, tool-shaped, and carries
   side effects the verifier must not have — `transaction.add_write` from git-status
   (`run_bash.py:168`) and artifact offload (`:178-180`). Passing `None, None` would skip them but
   still couples a new module to a private function. Instead reuse the **policy pieces only**:
   `build_scrubbed_env` + the venv-PATH prepend + the same timeout/binary-decode handling
   (`run_bash.py:233-250`). ~15 lines, no private coupling, no unwanted side effects.
3. Enforce a per-command timeout (`bash_timeout_seconds`) **and** check the run deadline
   between commands (`workflow_controller.py:_deadline_exceeded`, reading
   `WorkflowContext.deadline_mono`); a hung verification must not consume the budget.
4. Inject `{command, exit_code, stdout_tail, stderr_tail}` into the next stage's context.
5. P5 (no commands) ⇒ record `skipped: true`, do **not** block (G8).
6. **Routing on failure — see the seam below.** A non-zero exit must NOT be
   reported as `REPAIR_REQUIRED` by this step, because no such route exists.

**⚠ Routing seam (defect found in review; blocks S6 as previously written).**
v7 said "non-zero ⇒ `REPAIR_REQUIRED` (`:50-55`)". Verified against the tip,
that is **not implementable as stated**:

- `REPAIR_REQUIRED` exists only as status-string constants
  (`workflow_controller.py:53,61`). Nothing branches on it.
- The repair loop's only trigger is
  `eval_report.route_decision == "return_to_coder"` (`:619`), and
  `route_decision` is produced by the **eval stage**, not by a coder stage.
- So a coder-stage verification failure has **no path into the repair loop**.
  Returning the constant would set a string nobody reads: the run would go
  green with a failed verification — the exact class of silent pass this plan
  exists to remove.

**Chosen route (R-1): verification failure is routed through the existing eval
contract, not around it.** `run_verification` returns a result; the coder stage
attaches it to its `StageResult`, and the controller synthesises an eval report
with `route_decision = "return_to_coder"` when `exit_code != 0`. Rationale:
reuses the one repair mechanism that already works and is already tested,
instead of adding a second, parallel routing concept that the eval stage would
then have to stay consistent with.

Consequences that must be honoured:
- `StageResult` (`:359`, currently `StageResult(role, exit_code, eval_report)`)
  gains the verification payload, OR the synthetic report is built inside
  `_run_stage` before the return. Prefer the latter — it keeps the dataclass
  shape stable.
- The repair-round counter (`WorkflowContext.repair_round`, `:152`) and its cap
  govern verification-driven repairs too. **A failing verification command must
  not be able to loop forever**; when the cap is hit the run ends non-`DONE`
  with the failure recorded (fail-closed, Q6).
- The synthetic report must be marked as harness-origin so it is never confused
  with a model-authored eval.

**This seam was a new policy choice, so per the operator's stop rule it was
promoted to `Q10`. ✅ ANSWERED 2026-09-07: option (a), with the refinement that
the harness synthesises `return_to_coder` ONLY — escalation to the planner
stays eval's privilege, because `REPLAN_REQUIRED` requires judging plan *shape*
(`prompt.py:804-812`). The `repair_round` cap covers verification-driven
repairs. **S6 IS UNBLOCKED.** Implementation detail lives in §19 S11b.**

> **Q10 (answered — retained for the reasoning) — how should a harness
> verification failure re-enter the loop?**
> (a) **R-1 above** — synthesise an eval report with `route_decision =
> "return_to_coder"` (reuses the tested path; the eval stage is no longer the
> sole author of routing).
> (b) Add a first-class `verification_failed` route the controller checks
> alongside `route_decision` (explicit and greppable; a second routing concept
> to keep in sync).
> (c) Do not route at all in this PR — record the failure, mark the run
> non-`DONE`, and let the operator act (smallest, weakest).
> Recommendation: **(a)**, with the repair-round cap explicitly covering it.

Do-not: do not let the model supply, extend, or edit the command list (T6c asserts this). Do not add
a new sandbox gate — exploration-log Q19 (`builtin.py:112-127`) showed a stricter gate denies 8/10
real verifier commands. Do not run commands for non-`coder` stages.

Exit criteria:
- [ ] `verification_ran` event carries a real integer `exit_code`
- [ ] T6: seeded failing command ⇒ the run re-enters the coder stage via the Q10 route, and the next turn's context contains the real stderr text
- [ ] T6e: a command that fails on **every** repair round terminates at the `repair_round` cap, non-`DONE` — it never loops forever
- [ ] T6b: P5 ⇒ `skipped: true`, run continues
- [ ] T6c: a command string present in model output but absent from the plan is **never** executed
- [ ] T6d: a command exceeding the timeout is killed and recorded as failed, not hung
- [ ] `grep -c "_run_subprocess_fallback\|transaction\|artifact_store" src/fa/inner_loop/verification.py` == 0 (F-5)

Kill-check: removing the `run_verification` call makes **T6** fail (no event, no exit code).

---

### Step S7: `ScopeWarnHook` — warn, never block

Traces-to: G4 · GAP6 · CT5 · P6, P7
Depends-on: S4, **S6a** (the allowed set's only source)    Parallelizable-with: S6
Target liveness: L0→L3

Edit:
- path: `src/fa/inner_loop/hooks/scope_warn.py` symbol: `ScopeWarnHook` change: **NEW** `BEFORE_TOOL_EXEC` observer
- path: `src/fa/cli.py` symbol: `_build_run_hook_registry` (**`:1807`** — v7's `:1716` is stale, §24) change: register it

Degree of freedom closed: writes outside the declared slice scope were invisible; they now emit a
typed event while remaining permitted, so scope drift is observable without becoming a new denial
surface.

Deterministic mechanism: `src/fa/inner_loop/hooks/scope_warn.py` — the hook returns
`Decision.allow` on **every** branch; there is no code path that can produce a deny.

**Producer gap (found in review).** The step compares writes against "the
allowed set", but **no such set exists anywhere in the codebase** — grep for
`allowed_paths` / `allowed_set` / `files_allowed` across `src/fa/` returns
zero hits, and no earlier step creates one. As written S7 would ship a hook
whose allowed set is always absent, which by rule 3 means it **never warns**:
dead code shaped like a control.

The set's only source is the ceremony's `Exact files allowed to change:` line
(`feature-planning/INJECT.md:14`). Note that line sits in the **BEFORE-EDITING
GATE**, not the edit packet (`INJECT.md:20+`), so S6a — which captures the
turn's prose — is what first puts it somewhere the harness can read. S7
therefore depends on **S6a**, not just S4.

Honesty limit that must be stated in the event and the docs: the allowed set is
**model-declared**, so `scope_warning` measures self-consistency ("you wrote
outside what you said you would touch"), *not* conformance to an
operator-authored scope. Without that framing it reads as a much stronger
guarantee than it is.

Do:
1. Read the allowed set from the captured slice packet (S6a). Absent or
   unparseable ⇒ no warnings, no error.
2. Compare the write path against it; emit `scope_warning` when outside.
3. Return `Decision.allow` unconditionally.

Do-not: **do not add a deny branch** (operator decision Q-op4, G8). Do not block on an unparseable set.

Exit criteria:
- [ ] `grep -c "Decision.deny" src/fa/inner_loop/hooks/scope_warn.py` == **0**
- [ ] T7: out-of-scope write ⇒ warning event **and** the write succeeds
- [ ] T7b: no allowed set ⇒ zero warnings
- [ ] T7c: the emitted event states the set is **model-declared**, not operator-authored

Kill-check: removing the emit makes **T7** fail.

---

### Step S8: Remove `pr_prepare` from chat + close the deadlock

Traces-to: G6 · GAP7, GAP8 · CT7, CT9 · P8, P9
Depends-on: none    Parallelizable-with: S5–S7
Target liveness: L3→L3 (chat), CT9 L0→L3

Edit:
- path: `src/fa/cli.py` symbol: `_build_run_tool_registry` (**`:1760`** — v7's `:1625` is stale, §24) change: register `build_prepare_pr_tool` **only when `role != "chat"`**. The function already takes `role` as its first positional argument, so no signature change is needed; both call sites (`:2305` run, `:2915` conformance-with-`"coder"`) are unaffected
- path: `src/fa/cli.py` symbol: `_READINESS_PROMPT_EXTRA` (**`:165`**), `_readiness_prompt_extra` (**`:173`**) — v7's `:159-164`/`:167` are stale (§24) change: **role-parameterise** (D7) — keep the `pr_prepare` clause for non-chat roles, omit it for chat. `cli.py:2251` appends this for **every** role, so an unconditional edit would strip the instruction from `coder`, which still has the tool
- path: `src/fa/inner_loop/prompt.py` symbol: `:525,571,645` change: remove `pr_prepare` instructions from the chat prompt only
- path: `src/fa/inner_loop/hooks/intent_guard.py` symbol: `IntentGuard.__init__` + the `_requires_draft` **call site** (`:304`) change: add `draft_tool_available: bool`; skip the draft requirement when False

  **§24 correction:** `_requires_draft` (`:226`) is a **module-level function**
  taking `(call, repo_root)`, not an `IntentGuard` method. It has no access to
  instance state, so the availability flag CANNOT be threaded "into
  `_requires_draft`" as v7 implies. Gate at the call site inside the hook
  (`:304`, guarding the `_MISSING_DRAFT_REASON` return at `:310`), or pass the
  flag as a third parameter. Do not make the module function read instance
  attributes.

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

### Step S10: PR publication — ⚠️ REMOVED FROM THIS PLAN (D-1)

> Moved to `PLAN-harness-pr-publication`. Retained below for transfer only; **not in scope for
> PR-A/B/C and not counted in the DoD.** The harness's first outbound-write capability needs its own
> threat review, not one step in an F6 plan.


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
| T3b | CT6 | C0 | fenced ```verify block → `commands`; absent ⇒ `()`; prose never yields a command | verify-block pattern | — |
| T4 | CT3 | **C1** | event `ceremony_injected` + **2 entries in `skills_conditional`** (D2) | `should_inject_ceremony`/`_ceremony_blocks` call | P1,P2,P3 |
| T4b | CT3 | C1 | chat L2 run still receives its planner block (list-change regression) | `:802` list build | — |
| T4c | CT3 | C1 | workflow coder stage receives `slice_ceremony="enforce"` | `stage_kwargs` key | P1 |
| T4d | CT3 | C1 | `scope_mode` unchanged for all existing callers | — | — |
| T4e | CT3 | C1 | non-entry turn ⇒ no body in `skills_conditional` (F-3 late-binding) | reset-to-None branch | P3 |
| T5 | CT3 | C1 | `tests-writing` body in context | second condensate read | P1 |
| T6 | CT4 | **C1** | event kind + real `exit_code` | verification exec call | P4 |
| T6b | CT4 | C1 | `skipped: true`, run continues | — | P5 |
| T6c | CT4 | **C3** | model-authored command never executed | plan-only command source | P4 |
| T6d | CT4 | C1 | timeout ⇒ recorded failure, not hang | timeout arg | P4 |
| T6e | CT4 | **C1** | **real path**: plan text with a ```verify block → extracted → executed → exit code recorded | extract→run seam | P4 |
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
| T17 | CT11 | **C3** | **malformed-but-present packet** ⇒ partial draft, no typed INTENT, not blocked by the deriver | label-omission branch | P4 |
| T18 | CT11 | C0 | derived draft never contains `<fill me>` or a fabricated citation | renderer | — |
| T14 | CT8 | C1 | `slice_packets.jsonl` written; malformed ⇒ WARNING only | append call | P10 |
| T12 | CT3 | C1 | `observe`: events yes, context unchanged | — | P12/C |
| T13 | CT3 | C1 | `off`: zero events, byte-identical | — | P12/D |

**Verification commands (the `verify` fence S6 consumes).** This block is the
plan's own command list. Until it existed, `extract_plan_ids` on this plan
returned only the two commands from the *grammar example* in §3 — so S6 would
have run S3's self-test and reported green while verifying nothing about the
slice under test. Confirmed by running the real extractor (2 commands, both
from the example block).

```verify
uv run pytest tests/test_injections.py tests/test_inject_cli_flag.py -q
uv run pytest tests/test_injection_threading.py tests/test_slice_ceremony_injection.py -q
uv run pytest tests/test_invoke_workflow_tool.py tests/test_scope_expansion_wiring.py -q
uv run pytest tests/test_live_check_script.py tests/test_s19_stats_parsers.py -q
uv run ruff check src/fa tests
```

**Grammar-collision hazard (must not regress).** The extractor cannot tell a
real fence from one inside a ````text example. S3's own grammar sample is
therefore indistinguishable from a command list. **T3c** (new) pins this: the
extractor run over THIS plan must return the commands above, and must NOT
return `uv run pytest tests/test_plan_ids.py -q` alone. Any future plan that
documents the grammar must nest the example one fence level deeper.

**C4 / mutation handoff.** After C1/C2 green: (a) remove the `should_inject_ceremony`/`_ceremony_blocks` call → T4 must fail; (a2) remove the `stage_kwargs` key → T4c must fail;
(b) invert the `slice_ceremony.mode != "off"` branch → T13 must fail; (c) remove the verification
exec → T6 must fail; (d) remove `draft_tool_available` → T9 must fail. A survivor blocks shipped.

**LIVE-PATH PROOF — G1 (ceremony injection)**
- root: `fa workflow --roles planner,coder,eval` · matrix: A
- test: `scripts/run_live_check.sh s127-ceremony-inject` · oracle: event kind + fields (**not** `turn_context` text — D2)
- kill-check: removing the `coder_loop.py` injection call fails the row
- producer: `coder_loop.py:should_inject_ceremony` · consumer: `skills_conditional` (`prompt_composer.py:141-148`, non-cacheable)
- paths-covered: 3/3 (P1,P2,P3) · contract-check: PASS required · pyramid: A

**LIVE-PATH PROOF — G3 (harness verification)**
- root: same · matrix: A
- test: `scripts/run_live_check.sh s127-harness-verify` · oracle: real `exit_code` in `verification_ran`
- kill-check: removing the exec call fails the row
- producer: `verification.py:run_verification` called from `workflow_controller.py:_run_stage` · consumer: verdict routing `:50-55` + next turn context
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
| RK14 | Ceremony injected but models still emit unparseable packets ⇒ F6 persists behind a new mechanism | **no unit test can prove this**; only the live re-run settles it (D-2). DoD says so plainly | live re-run |
| RK13 | Deleting chat tests erases a documented decision | reversal recorded in exploration_log + replacement docstring cites this plan (D8) | S8 exit criteria |
| RK11 | `skill_block_for_request` list change clobbers the existing chat L2 block | append, never replace; T4b is the regression guard | T4b |

**ROLLBACK (P2+ required).** Flag `injections.coder_slice_ceremony.mode` — default `observe`, set `off` for a
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

**DONE when:** G1, G2, G4, G6 at **L3** (G7 deferred, D-1); **G3 at L3 for plans carrying a ```verify block, and explicitly not proven end-to-end for plans without one** (F-4); G5 at its contract L3 (advisory end-to-end); G8 holds
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

**Extraction contract (F-2 — pinned, because this step decides whether a mutation is blocked).**
S6a stores the packet verbatim; S6b reads **labelled lines** out of it. The two are consistent: the
*artifact* is prose, the *deriver* reads a small fixed label set. The labels are exactly the ones
`INJECT.md` already asks for (S1), so a compliant packet is parseable by construction:

| draft field | packet label (case-insensitive, line-anchored) | if missing |
|---|---|---|
| `INTENT:` | `Concrete intent:` → mapped via `classify_intent` if unlabelled | **omit the line** |
| `CLASS:` | `Tests-writing class:` | omit |
| `INVARIANT:` | `Definition of Done` / `DoD:` | omit |
| `DEGREE-OF-FREEDOM CLOSED:` | `Degree of freedom closed:` | omit |
| `DETERMINISTIC MECHANISM:` | `Producer kill-check target:` (a `path:line`) | omit |

**Incomplete-extraction behaviour — the F6 trap, closed explicitly.** A partially-parseable packet
must NOT produce a new denial path. Therefore:
1. The deriver emits **only the fields it could extract**, never `<fill me>` placeholders.
2. **`INTENT:` is never guessed from prose.** If no intent label is found, the deriver omits the
   typed line entirely, and `IntentGuard` falls back to `classify_intent(projected)` — the
   staged-diff classifier (`intent_guard.py:328-331`), which is the *safer* authority anyway. This
   closes F-2's point 3: a mis-read regex can no longer forge a typed D-5 override, because the
   deriver never writes one it is not certain of.
3. If the derived draft would be **empty of all fields**, write nothing → the guard behaves exactly
   as today. This is denial-as-today, not a new denial (see G8 note below).

**G8 reconciliation (F-2 point 2, and the reviewer is right to press on it).** G8 says "no field may
be rejected for absence". S6b honours it *within the ceremony*: no ceremony field is ever rejected,
and a sloppily-formatted packet still yields a usable partial draft. What remains is the
**pre-existing** `IntentGuard` gate, unchanged by this plan. The honest statement is in §9 DoD:
the F6 fix is not *proven* until the live re-run shows models producing parseable packets without a
retry loop.

Do:
1. Render the commit-note fields from the packet per the label table above. `DETERMINISTIC MECHANISM`
   maps from the packet's kill-check target (a `path:line`), satisfying the citation rule by
   construction.
2. Write via `PrDraftStore.write_text` (`pr_draft.py:68`) — never touch `_current_digest` directly.
3. **No packet ⇒ write nothing.** The guard then denies exactly as today (fail-closed).
4. Pipeline coder stages only. Chat is untouched (it has no tool after S8 and no ceremony).

Do-not: do not pass the packet's typed intent to `validate_test_edits` (`pr_intent.py:519-526`). Do
not synthesise a draft when the packet is absent. Do not modify `pr_intent.py` (CT10).

Exit criteria:
- [ ] a pipeline coder slice mutates the workspace with **zero** `pr_prepare` tool calls
- [ ] T15: a packet declaring `IMPLEMENT` while the diff deletes a test is **still blocked**
- [ ] T16: absent packet ⇒ guard denies as today (fail-closed, no bypass)
- [ ] **T17 (F-2, the realistic failure): packet present but labels absent/reworded** ⇒ partial draft
      emitted, **no typed `INTENT:` line**, classifier intent governs, and the slice is **not**
      blocked by the deriver
- [ ] T18: no derived draft ever contains `<fill me>` or an invented `path:line`
- [ ] `grep -c "pr_intent" src/fa/inner_loop/verification.py` == 0 (validators untouched)

Kill-check: removing the `write_text` call makes **T16**'s counterpart (the zero-`pr_prepare` slice) fail.

---

**CT11 — harness-derived draft** *(security, §6.5 — adversarial case required)*
- BOUNDARY: draft provenance and the test-protection rule.
- INVARIANT: a harness-written draft satisfies `IntentGuard` **without** weakening
  `validate_test_edits`, which stays keyed on classifier intent from the staged diff.
- ADVERSARIAL CASE (C3, **T15**): packet claims `IMPLEMENT`; diff deletes `tests/test_x.py`.
  Must be **blocked** (`pr_intent.py:508-512`).
- ADVERSARIAL CASE (C3, **T17**): packet present but labels reworded. Must degrade to a partial
  draft with **no typed `INTENT:`**, so the staged-diff classifier governs. A mis-derived
  `INTENT: IMPLEMENT` would be a bypass; omission cannot be.


---

## 13. Review pass 3 — external adversarial review (findings F-1…F-5, D-1, D-2)

A second reviewer audited v3. **Six findings accepted, one partially refuted.** All fixes are in the
sections above; this section records the reasoning.

| # | verdict | resolution |
|---|---|---|
| **F-1** | **Accepted — blocking, and the best catch in the review.** `T#` is a *taxonomy label* (`feature-planning:267-278`), not a runnable string; zero existing plans carry commands (verified against `PLAN-complexity-aware-execution-chat-role.md`). `run_verification(commands, …)` had **no producer** — the same defect class as D5. | Option **(a)**: `PlanIds.commands` extracted from a fenced ```verify block; grammar pinned in CT4 and mirrored into both planning skills (S9). Chose (a) over (b) because a fixed command set cannot express per-slice verification and would quietly weaken G3. New tests T3b, T6e. |
| **F-2** | **Accepted — blocking.** S6a said "do not parse"; S6b had to parse. The unspecified half was the *security-critical* half. | Extraction contract pinned as a label table in S6b. **Key decision: `INTENT:` is never guessed.** If unlabelled, the deriver omits the typed line and the staged-diff classifier governs (`intent_guard.py:328-331`) — a mis-read regex can no longer forge a D-5 override, which was F-2's sharpest point. New tests T17 (C3, malformed-but-present) and T18. |
| **F-3** | **Accepted.** Verified at `coder_loop.py:958-961`: `skills_conditional_value` is a **default arg** bound at each turn's re-definition of `_compose_request_payload`. "Outside `_is_chat_role`" was necessary but insufficient. | Placement pinned in S5: inside the turn loop, above the re-definition, reset to `None` on non-entry turns. New test T4e (no per-turn body resend). |
| **F-4** | **Accepted.** G3's unqualified L3 rested on a seeded command list. | DoD now scopes it honestly: **L3 for plans carrying a ```verify block; explicitly not proven end-to-end for plans without one.** T6e proves the real path. |
| **F-5a** | **Accepted.** `_run_subprocess_fallback` is private and side-effectful (`run_bash.py:168` `transaction.add_write`, `:178-180` artifact offload). | S6 now reuses **policy only** (`build_scrubbed_env` + timeout/decode), ~15 lines, no private coupling. Exit criterion greps to enforce it. |
| **F-5b** | **Partially refuted.** The suspicion that `pr_prepare`-for-`coder` is dead weight is **wrong**: `fa run --role` **defaults to `coder`** (`cli.py:542-546`), so bare `fa run` is a standalone coder session with no controller and no S6b deriver. Removing it there reintroduces the CT9 deadlock on the *default* invocation. | Recorded as **CT7b** with the evidence, so the question is not re-litigated. |

**D-1 — Scope pushback: accepted, and it is the right call.**
S10 (`fa` publishes a PR) is the harness's **first outbound-write capability**. Bundling it into a
ceremony-friction fix is scope creep, and it deserves its own threat review rather than one step and
one risk row. **S10 is removed from this plan** and becomes `PLAN-harness-pr-publication` (to author
separately). Consequences applied: G7 and CT8 are **deferred non-goals**; S6a survives because the
packet artifact is independently useful (it is S6b's input); T10/T10a move with S10.
This also shrinks the F6 fix to what it actually is: **PR-A + PR-B**, with PR-C (chat removal + docs)
as cleanup.

**D-2 — G8-vs-fail-closed tension: accepted as stated, not resolved by argument.**
The reviewer is right that "no packet ⇒ deny as today" is still a denial-for-absence, and that the
fix's success depends on a *behavioural* property no unit test can prove: that the injected ceremony
actually causes models to emit parseable packets without a retry loop. Recorded plainly in §9 DoD
rather than argued away. The live re-run is the only oracle, and until it is green **this plan
claims a mechanism, not a cure.**

## 14. Review pass 4 — injection control surface (Q7, Q8; operator, 2026-09)

Status: **DECIDED — no code written against this section yet.** Recorded before
implementation per the operator's "lock in decisions first" instruction.

### 14.1 Q7 — who owns the injection switch → **(A) the workflow**

`WorkflowContext.injections_enabled` (default `False`) grants a stage permission
to consult config; the per-injection mode decides what actually happens. Two
independent switches, so enabling the pipeline flag alone changes zero prompts.
Rationale: injections are about *executing a planned slice*, which is the
pipeline's job; a standalone `fa run` is often a one-off where a protocol
payload is noise. (A) is strictly narrower than (B) — easy to widen later, hard
to walk back. **Already implemented** (`d0781dc`).

### 14.2 Q8 — control surface: CLI flag vs config file vs live re-read

**Operator's correction (accepted).** The `d0781dc` design assumed toggles might
change *while an agent is mid-loop*, and paid for that with per-turn resolution
plus a 2s TTL cache. The operator's actual model is: **toggles are tweaked
between `fa run` invocations, not during one.** Under a future WebUI, the UI
knobs become CLI arguments and config edits at launch time; the chat window is
a front-end over invocations, not a live control plane into a running loop.

**Fact-check performed before deciding** (line-exact, current tip):

| Claim | Verified |
|---|---|
| A workflow run is ONE process spanning many stages/turns | ✅ `cli.py:1303,1533` — `run_stage_fn=_cmd_run` is called in-process per stage |
| IntentGuard already models "explicit override wins, else config" | ✅ `cli.py:182-197` `_resolve_intent_guard_mode(override)` |
| IntentGuard exposes **no** CLI flag; it is config-only + programmatic override | ✅ only caller is `cli.py:1735`, param `intent_guard_mode: str \| None = None` at `:1653` |

**Consequence — the hot-reload machinery is over-engineering.** Because one
`fa workflow` invocation is a single long process, "per-turn re-read" only buys
mid-run toggling, which is explicitly NOT wanted. What the operator wants is
*per-invocation* configuration, which a plain value resolved once at startup
already delivers.

**DECISION Q8 — hybrid, mirroring the IntentGuard precedent:**

1. **CLI flag is the primary surface.** `--inject <name>=<mode>` (repeatable) on
   `run` and `workflow`. Explicit, greppable in shell history, and exactly what a
   WebUI knob maps onto — the UI sets an argument, it does not mutate a running
   process.
2. **Config file is the persistent default** for operators who always want it on,
   read when no CLI override is supplied.
3. **Precedence: CLI flag > config > `off`.** Identical in shape to
   `_resolve_intent_guard_mode`, so there is one resolution idiom in the codebase
   rather than two competing ones.
4. **Resolve ONCE per invocation, at startup.** The mode becomes a plain `str`
   again in the transport.

**What this retracts from `d0781dc`:** the `ModeResolver` callable transport, the
`_FlagCache` TTL cache, `reset_flag_cache()`, and the hot-reload tests. The
registry, role gating, the closed enum, `normalize_mode`, fail-to-`off`
polarity, and the two-switch split all **survive unchanged** — those were about
extensibility, which is still wanted.

**Cost of the retraction:** small and bounded. `injections.py` loses ~60 lines
(cache + laziness); `InjectionSpec`, `INJECTION_SPECS`, and `resolve_mode`'s
signature are untouched. The transport type narrows from
`Mapping[str, Callable[[], str]]` to `Mapping[str, str]`, which simplifies every
consumer. RK15 below records the one thing genuinely lost.

**RK15 (accepted).** Dropping live re-read means an operator who wants to change
an injection mode must start a new invocation. Accepted because that is the
stated workflow; if a future WebUI ever needs mid-run toggling, the resolver
transport is re-introducible behind the same `mode_for()` call site, which is
why that indirection is being kept.

### 14.3 Deferred, explicitly not now

- ~~**G9 — `fa inject list/status`**~~ — **PROMOTED INTO SCOPE**, see §15.2.
- Chat-role and planner-role injections: registry rows only, no specs authored yet.

---

## 15. Review pass 5 — inheritance + introspection (Q9, G9; operator, 2026-09-07)

Both items below were raised by the stop rule during S5a implementation and
decided by the operator. §14 is unchanged by them; this section is additive.

### 15.1 Q9 — do chat-nested pipelines inherit `--inject`? → **(b) yes, inherit**

**Source-verified defect.** `invoke_workflow`
(`src/fa/inner_loop/tools/workflow_tool.py:453-472`) calls `run_workflow_fn(...)`
with fourteen keyword arguments and `inject_overrides` is not among them. The
parameter defaults to `None` → `dict(None or {})` → `{}`
(`workflow_controller.py:797,850`). So a pipeline the model launches from a chat
session resolves EVERY injection to `off`, even when the operator started that
chat with `--inject coder_slice_ceremony=enforce`.

Concretely: `fa run --role chat --inject coder_slice_ceremony=enforce`, then ask
the chat agent to run planner→coder. The coder stage of that nested pipeline
gets no ceremony payload and says nothing about it. The flag appears to do
nothing — the worst failure class for a control surface, because it is silent.

| Option | Verdict |
|---|---|
| (a) leave as-is; flag only affects `fa workflow` | **Rejected.** Two invocation paths with different injection semantics and no signal telling them apart. |
| **(b) inherit through `WorkflowInvocationContext`** | **CHOSEN.** Matches "the operator configured THIS invocation": everything downstream of that process inherits it, nested or not. |
| (c) tool schema parameter, model decides | **Rejected.** Hands the model control over enforcement of its own protocol. A model that finds the ceremony inconvenient can decline it. |

**Mechanism.** `WorkflowInvocationContext` gains
`inject_overrides: Mapping[str, str] = field(default_factory=dict)` — a frozen
dataclass, so the default must be a factory, and every existing construction
site (`cli.py:1591`, `tests/test_handoff_payload.py:27,189`,
`tests/test_invoke_workflow_tool.py:156`) keeps working untouched. The provider
factory `_make_workflow_ctx_provider` (`cli.py:1531`) takes the already-parsed
overrides as a keyword argument and the tool forwards `ctx.inject_overrides` in
its `run_workflow_fn(...)` call.

**Parsed once, at the CLI seam.** The chat session's `--inject` is parsed by
`_cmd_run` and handed to the provider as a mapping. The tool never sees raw
`NAME=MODE` strings, so it cannot re-derive or re-interpret them, and a
malformed value has already been rejected before any session exists.

**Role gating is unaffected and still authoritative.** Inheritance passes
OVERRIDES, not modes. The nested pipeline's coder stage re-resolves through
`resolve_injection_modes(role, overrides=...)`, so a chat session carrying
`coder_slice_ceremony=enforce` still yields `off` for its planner stage. One
inherited flag cannot smuggle a payload into the wrong role — the property §14
established, preserved across the new hop.

**CT16 (contract).** Given a `WorkflowInvocationContext` with
`inject_overrides={coder_slice_ceremony: enforce}`, the `run_workflow_fn` call
made by `invoke_workflow` receives `inject_overrides` equal to that mapping;
given the default context, it receives `{}`.

### 15.2 G9 — `fa inject` introspection → **IN SCOPE (folded in)**

Rationale for promoting it: Q9 was a silent-misconfiguration bug that existed
because there is no way to ask the harness what it will actually do. Shipping a
control surface with three inputs (flag, config, default) and no way to read
back the effective state reproduces that blind spot by construction. G9 is the
observability half of §14's control half.

**Surface.** `fa inject list` and `fa inject status` — `status` is the default
when the subcommand is omitted, and both accept `--inject NAME=MODE` and
`--role` so an operator can preview a specific invocation.

```
$ fa inject status --role coder --inject coder_slice_ceremony=enforce
INJECTION              ROLE    MODE      SOURCE
coder_slice_ceremony   coder   enforce   --inject flag
```

**The SOURCE column is the whole point** — "enforce" alone does not tell an
operator whether their flag took effect or the config did. Sources are exactly
four: `--inject flag`, `config (<path>)`, `default (off)`, and
`role-gated (off)` — the last distinguishing "you disabled it" from "this
injection does not apply to this role", which is precisely the Q9 confusion.

**Mechanism — one new function, no duplicated precedence logic.**
`explain_injection_modes(role, *, overrides, config_path) -> dict[str, InjectionStatus]`
in `injections.py`, where `InjectionStatus` is a frozen dataclass
`(name, role, mode, source, summary)`. `resolve_injection_modes` is then
re-expressed as a thin projection over it (`{k: v.mode for ...}`) so the
precedence rule has exactly one implementation and the table can never disagree
with what a run actually does. That equivalence is itself asserted (CT18).

**Read-only and side-effect free.** `fa inject` starts no session, writes no
artifact, and touches no run directory; it reads config and prints. Unreadable
config degrades to `default (off)` rows plus the existing warning, never a
traceback. A malformed `--inject` exits 2 with the same message as
`fa workflow`, since both are up-front operator input.

**CT17 (contract).** Every row's `source` correctly identifies the winning
input; a role-gated injection reports `role-gated (off)` and never
`default (off)`.
**CT18 (contract).** For all `(role, overrides, config)`,
`{name: st.mode for name, st in explain_injection_modes(...).items()}` equals
`resolve_injection_modes(...)`.

### 15.3 Steps (appended to §5)

**S5c — inherit overrides into nested pipelines (Q9).**
Files: `src/fa/inner_loop/tools/workflow_tool.py`, `src/fa/cli.py`,
`tests/test_invoke_workflow_tool.py`.
DoD: CT16 holds; the default context still sends `{}`; existing construction
sites unmodified. Negative proof: deleting the forwarding line fails a test that
asserts the mapping arrives, not merely that the key exists.
Tests: C1 (tool→controller boundary with a spy `run_workflow_fn`).
Kill-check: drop `inject_overrides=ctx.inject_overrides` from the tool call →
inheritance test fails.

**S5d — `fa inject list/status` (G9).**
Files: `src/fa/inner_loop/injections.py`, `src/fa/cli.py`,
`src/fa/cli_help.py`, `tests/test_inject_cli_flag.py` (or a new
`tests/test_inject_introspection.py`).
DoD: CT17 + CT18 hold; `fa inject` exits 0 and prints one row per known
injection; bad `--inject` exits 2. Negative proof: a source-attribution test
that fails if every row is hardcoded to one source.
Tests: C0 (`explain_injection_modes` source attribution across the four cases),
C1 (CLI invocation, exit codes, row count).
Kill-check: make `explain_injection_modes` always report `default (off)` →
attribution tests fail; break the projection equivalence → CT18 test fails.

**Docs (folds into S9).** `knowledge/instructions/02-operations.md` gains the
`--inject` flag and the `fa inject` command with the worked example above;
`cli_help.py` carries EN+RU entries for both.

---

## 16. Review pass 6 — default mode + ADR seat (operator, 2026-09-07)

### 16.1 Default mode for ALL injections is `observe`

**Operator decision.** The default tier of the Q8 precedence chain
(`--inject` > config > default) is **`observe`**, not `off`, and this is a
property of the injection framework, not of one injection.

Note this RESTORES the plan's own §2 line 179 ("default `observe`") and
§7 RK9 rollback line 950, which the S5a implementation had silently drifted
away from by defaulting every tier to `off`. Recorded here so the drift is
not re-introduced by someone reading §5 in isolation.

**Why it is safe.** Only `enforce` alters the request payload. `observe`
records that a trigger fired and leaves the prompt byte-identical, so an
unconfigured or misconfigured harness still cannot have its context
rewritten — it just reports what it *would* have injected. Defaulting to
`off` instead makes the feature invisible until someone edits config, which
is how a control surface rots unnoticed.

**Three places carry the default**, all now `observe`:
`FeatureFlags.coder_slice_ceremony_mode`, the loader default in
`load_feature_flags`, and `injections.FALLBACK_MODE`.

**Two boundaries deliberately stay `off`:**

| Case | Mode | Why |
|---|---|---|
| Role outside the spec's `roles` | `off` | A planner stage must not emit coder telemetry. Role gating outranks every tier. |
| `mode_for` on an absent mapping / unknown name | `off` | Means "this call site was never wired" or "no such injection" — neither has anything to observe. Distinct from a KNOWN injection left unconfigured, which is `observe`. |

**Consequence — source attribution had to change.** `explain_injection_modes`
previously inferred "came from config" as *mode ≠ fallback*. With the default
at `observe`, an explicit `config: off` — the setting a cautious operator is
most likely to write — would have been mislabelled `default`. Attribution now
tests DECLARATION (`_config_declares`: parsed flags vs dataclass defaults).
Documented limitation: a config that writes exactly the default value reports
as `default`; the effective mode is identical, so nobody is misled.

**Honest test-strength note.** With one three-valued injection,
`_config_declares` is currently behaviourally EQUIVALENT to the old
heuristic, so the mutant swapping them survives. Kept anyway because the
equivalence is an accident of today's registry: add an injection whose flag
default differs from `FALLBACK_MODE` and value-inference starts lying.
Recorded rather than papered over.

### 16.2 ADR seat — ADR-10 Amendment 2026-09-07 (I-6)

Injected prompt payloads now have a normative home:
`knowledge/adr/ADR-10-deterministic-harness-invariants.md`, **Amendment
2026-09-07 — ADR-10-I6**. ADR-10 is the correct seat because it governs
runtime determinism around the LLM call (I-1 single-source classifier, I-4
loop-owned state), whereas ADR-11 governs authoring-time admission.

I-6 makes five clauses normative, each already implemented: (1) registered,
never ad hoc; (2) resolved once per invocation, mid-run re-read forbidden;
(3) role-gated first and unconditionally; (4) defaults to `observe`, never
`enforce`, with the fail-loud/fail-quiet asymmetry between CLI input and
config; (5) introspectable without running the model (`fa inject`).


---

## 17. S5b implementation record + e2e plan (2026-09-07)

### 17.1 What shipped

`coder_loop.py` gained `should_inject_ceremony(role, turn, injection_modes)`
and `_ceremony_blocks(workspace_root)`, plus a call site placed inside the turn
loop, **above** the `_compose_request_payload` re-definition and **outside**
`if _is_chat_role:` (plan D1 / F-3, both verified by test).

Verified end-to-end in-process: with `enforce`, the composed **provider request
body** grows 337 → 6182 bytes (anthropic) / 311 → 6156 (openai) and contains
`BEFORE EDITING GATE`. That is the L3 claim — bytes to the provider, not merely
a populated dataclass.

New `LogKind` member `ceremony_injected`, emitted in the same branch that builds
the payload (CT3 dual-write) and under `observe` too, where `blocks: 0` records
the counterfactual. Declared in `UNPARSED_KINDS` with a reason.

**Test-theater defect found and fixed by mutation testing.** The first revision
of `tests/test_slice_ceremony_injection.py` re-implemented the gate condition
locally. Mutants M22 (`is_active` → `is_observed`, i.e. `observe` starts
rewriting prompts) and M24 (blocks read but never attached) both **survived** —
the tests were grading their own mirror. Fixed by extracting the real predicate
into production and asserting against it. All 7 mutants now die.

### 17.2 e2e rows for the live host (NOT yet added to the script)

**Blocking constraint, source-verified:** `row_run` (`scripts/run_live_check.sh`
:284-315) hardcodes `--role chat`. Every existing `s127-*` row is therefore a
chat row. The ceremony is a **coder-role** feature gated on `--inject`, so these
rows cannot reuse `row_run` as written. Adding them requires either a
`row_run_role` variant taking role + extra flags, or a dedicated
`ceremony_row` helper. That is a script change with its own blast radius, so it
is scoped as its own step rather than smuggled into S5b.

Planned rows, each asserting on `events.jsonl` like the existing hooks:

| Row | Invocation | Assertions |
|---|---|---|
| `s127-ceremony-enforce` | `fa run --role coder --inject coder_slice_ceremony=enforce` | `"kind": "ceremony_injected"` present with `"mode": "enforce"`; `"blocks": 2`; the model's turn-1 request carries `BEFORE EDITING GATE` |
| `s127-ceremony-observe` | same, `=observe` | `ceremony_injected` present with `"mode": "observe"` and `"blocks": 0`; ceremony text **absent** from the request — the inertness claim, on the live host |
| `s127-ceremony-off` | same, `=off` | no `ceremony_injected` event at all |
| `s127-ceremony-role-gate` | `--role planner --inject coder_slice_ceremony=enforce` | no `ceremony_injected`; proves one flag cannot smuggle a payload into the wrong role |
| `s127-inject-status` | `fa inject status --role coder --inject ...=enforce` | exit 0; stdout has the row and `--inject flag` in SOURCE; no session directory created (read-only claim) |
| `s127-inject-bad-flag` | `fa inject --inject bogus=enforce` | exit 2; stderr names the valid choices |

The last two need no model call, so they are cheap and should run on every
battery pass; the first four are token-costing rows.

### 17.2b Correction — S5 step 1 (append) was initially missed

The first S5b revision used `skill_block_for_request = [render.skill_block]`
on the chat path (the pre-existing line) while the ceremony branch above
ASSIGNED the same variable. The plan's step 1 required append precisely so the
two producers coexist. The clobber was unreachable today -- the ceremony branch
needs `role=="coder"`, the chat branch needs `role=="chat"` -- but correct only
by accident, and the accident ends the moment a chat-role injection is
registered. Now `[*(skill_block_for_request or []), render.skill_block]`, pinned
by a test that also asserts the old form is gone.

Found by re-reading the loop under operator challenge, not by the test suite:
every test passed both before and after, because no test exercised a role that
reaches both branches. Recorded as a coverage gap, not just a fixed typo.

### 17.2c Verification strength — corrected

The original S5b claim ("337 -> 6182 bytes") came from calling
`build_prompt_parts_v2` DIRECTLY from the test, not from running the loop. That
proves the composer serializes blocks it is handed; it does NOT prove the loop
hands them over, which is the actual claim. `tests/test_slice_ceremony_injection.py`
now boots `drive_session` against the `FakeProvider` harness from
`tests/test_coder_loop.py` and asserts on the `RequestInfo` a provider receives:

- `enforce` -> the request carries `BEFORE EDITING GATE` and both block names;
- `observe` -> the request is **byte-identical** to `off` (the inertness claim,
  stated as full-request equality rather than "no gate text", so `observe`
  cannot be altering context by another route);
- unconfigured (`injection_modes=None`) -> identical to `off`;
- a guard test asserting `enforce != off`, so the equality tests cannot pass
  vacuously.

Mutation re-run against these: M24 (blocks read but never attached) and M22
(`observe` injects) now die at the live path, not only at the mirror.

### 17.3 Follow-up (not blocking S5b)

- **S5e:** teach `run_live_check.sh` a role/flag-parameterised row helper, then
  land the six rows above.
- Turn-2 anchor text (plan S5 step 2, "anchor only on later turns") is **not**
  implemented: today later turns inject nothing at all. That is the safe half of
  the requirement. The short `turn_context` anchor is deferred and should be its
  own slice, since it touches `observations.py` capping behaviour.


---

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
| workflow controller | `src/fa/inner_loop/workflow_controller.py:_run_stage/stage_kwargs` | edit | S5a,S6,S10 |
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

---

## §18 Adversarial plan review — 2026-09-07 (post-S5b, at tip `3bfa4c9`)

Full review of trajectory, code grounding, and executability. Every finding was
checked against the tip; nothing below is inferred from the plan alone.

### 18.1 Confirmed defects, now fixed in this revision

| # | Defect | Evidence | Fix |
|---|---|---|---|
| R1 | **§6 had no `verify` fence.** S6's premise ("commands come from the plan") was vacuous: running the real extractor on this plan returned **2** commands, both from the *grammar example* in §3. | `extract_plan_ids` on the live file | Real fence added to §6; all 5 commands executed and green |
| R2 | **S6's failure route did not exist.** "Non-zero ⇒ `REPAIR_REQUIRED`" — but that constant is never branched on (`workflow_controller.py:53,61`); repair is driven solely by `eval_report.route_decision == "return_to_coder"`, authored by the **eval** stage. A coder verification failure had no path into repair. | grep + `:619` | Routing seam written; promoted to **Q10** (blocking); **T6e** added for the repair-round cap |
| R3 | **S6a had no producer.** `append_slice_packet` was defined with no caller, so S6b/S10 would still have had no input. | grep `append_slice_packet` → 1 hit (the definition) | Call site named: coder stage, `sink[-1].final_text` (`:350`; sink populated for every role, `:315`) |
| R4 | **S7's allowed set had no source.** `allowed_paths`/`allowed_set`/`files_allowed` → **0 hits** in `src/fa/`. The hook would never warn: dead code shaped like a control. | grep | Source named (`INJECT.md:14`, in the *gate*, not the packet); dependency on S6a added; model-declared honesty limit recorded (**T7c**) |
| R5 | **Symbol drift plan↔code.** `_ceremony_block_for_turn` → **0 hits**; shipped names are `should_inject_ceremony` / `_ceremony_blocks`. Flag was `slice_ceremony_mode`; shipped is `coder_slice_ceremony_mode`. Kill-checks naming absent symbols cannot fail loudly. | grep | 13 replacements; S4's flag packet re-pointed to verified `feature_flags.py:57,74,111` |
| R6 | **Stale citations.** `workflow_controller.py:310` (mid-`stage_kwargs`) and `:345` (eval-report block) — both shifted by my own S5a/S5c edits. | read the cited lines | Re-anchored to symbols (`_run_stage`, `_deadline_exceeded`) rather than line numbers |
| R7 | **Stale comment in shipped code.** `workflow_controller.py:296` cited `coder_loop.py:613` for `_is_chat_role`; actual `:681`. | grep | Rewritten to quote the predicate — immune to line drift |
| R8 | **Dangling S10 references** in S6a's exit criteria and kill-check, though S10 was removed under D-1. | grep `S10` | Re-pointed to S6b, the in-scope consumer |

### 18.2 Checked and found sound — no action

- **S6's F-5 argument** (reuse `run_bash.py`'s env/timeout policy, not the private
  `_run_subprocess_fallback`) is correct: `:233-250` really is the policy, and
  `:168` really is the `transaction.add_write` side effect to avoid.
- **`plan_ids.py`** and `_VERIFY_BLOCK_RE` extract correctly. R1 was a plan
  defect, not a code defect.
- **T4b has a real behavioral test** — `test_scope_expansion_wiring.py::
  test_high_tier_read_arms_l2_and_injects_skill_block` drives `drive_session`
  and asserts the chat L2 planner block reaches the request. Not a source-text
  mirror.

### 18.3 Honest limitation carried forward

The S5b **append** fix (`[*(skill_block_for_request or []), render.skill_block]`)
is **not observable by any test today**, and reverting it to the old clobber
leaves all 16 scope-expansion tests green. The ceremony branch and the chat L2
branch are mutually exclusive at present (`_is_chat_role` requires
`scope_mode`), so nothing can currently hold both blocks. The append is
defensive correctness for when those paths converge — recorded as such rather
than claimed as a verified fix. **M28 kills only at the unit level.**

### 18.4 Methodology corrections adopted

- `grep -c '```verify'` counts *lines mentioning* the pattern, not fences. It
  reported 11; there was **1**. Count structural constructs with the production
  regex.
- "Citation points past EOF" is a near-useless staleness check — it found 0
  problems while `:310` and `:345` were both wrong. Staleness means: read the
  cited line, compare it to what the plan *claims* is there.
- **Landing a slice rots the next slice's citations.** S5a/S5b shifted both
  files; S6's anchors and a shipped comment both rotted. Prefer symbol anchors;
  re-verify downstream citations after every slice.

### 18.5 Blocking questions

- **Q10 (new, blocks S6)** — how a harness verification failure re-enters the
  loop. Recommendation **(a)**: synthesise an eval report with
  `route_decision = "return_to_coder"`, with the repair-round cap covering it.
- **Q-slice-entry (still unanswered)** — "slice entry" is currently implemented
  as **turn 1 of the coder stage**.

**S6 and S7 are blocked pending Q10; S6a is unblocked and is now the critical
path (S6b and S7 both depend on it).**

---

## §19 Completion-gate hardening — new steps S11–S14 (operator-approved 2026-09-07)

Source: `worklogs/reviews/AUDIT-completion-measurement.md`. These close the gap
between *"the model asserted done"* and *"the harness observed done"*. Without
them, S6 lands as instrumentation whose result nothing acts on.

**Operator decisions folded in:** Q10 refinement accepted (harness synthesises
`return_to_coder` only); Q11 = yes (require harness evidence); Q12 = yes,
validate in harness code, missing slice ⇒ WARN; Q13 = not now (eval keeps no
ceremony injection until Q11 is measured).

### F1 answered precisely — the eight `step_results` occurrences

The audit's "zero consumers" claim, enumerated. Every occurrence in `src/`:

| # | Site | Kind |
|---|---|---|
| 1 | `prompt.py:829` | prose in the eval prompt: "structure them so they map to `step_results[]`" |
| 2 | `workflow_artifacts.py:196` | `EvalReport` field declaration |
| 3 | `:218` | `to_json_dict` — **serialise** |
| 4 | `:240` | `from_json_dict` — **deserialise** |
| 5 | `:409` | `_scan_step_results` — **produce** (regex over eval prose) |
| 6 | `:456` | assigned inside `parse_eval_report` |
| 7 | `:467` | passed to the fail-closed `BLOCKED` report |
| 8 | `:488` | passed to the normal report |

All eight are **produce / store / reload**. Not one is a **read that changes a
decision**: no branch, comparison, aggregation, or routing input anywhere reads
`step_results`. `tests/test_workflow_artifacts.py` asserts round-trip fidelity
only — it proves the field survives JSON, not that it means anything.

That is the exact sense of "zero consumers": **the data is complete, correct,
and inert.** S11/S12 give it a consumer.

---

### Step S11: Reconcile the verdict against harness observation (Q11)

> **SPLIT in §21 (C-1) — do not execute as one step.** **S11a** (F6: unjudged
> never means DONE) has **no dependencies** and runs before S6. **S11b** (the
> reconciliation rows below) needs S6's observations. T19* belong to S11a;
> T15* to S11b.

Traces-to: G3 · CT4 · new CT19
Depends-on: **S6** for S11b only; **S11a has none**    Blocks: nothing
Target liveness: L0→L3

**Why.** Today `EVAL_VERDICT_TO_TERMINAL_STATUS["PASS"] = "DONE"`
(`workflow_controller.py:52`) makes a model-typed token the sole cause of
success. Probed at the tip: the single word `PASS` yields
`verdict=PASS route=complete steps=[]` and exits 0.

Edit:
- path: `src/fa/inner_loop/workflow_artifacts.py` symbol: new `reconcile_verdict` change: **NEW** pure function `(claimed: EvalReport, observed: VerificationOutcome|None) -> EvalReport`
- path: `src/fa/inner_loop/workflow_controller.py` symbol: after the eval stage in `_run_stage` change: route on the **effective** report

Degree of freedom closed: a PASS could previously coexist with a red
verification in the same run and nothing compared them; the two facts are now
reconciled at one point, with the observation dominant.

Deterministic mechanism: a pure function with a four-row truth table; the
controller routes on its output, so there is no path from a claimed PASS to
`DONE` while an observed command is non-zero.

| observed | claimed | effective | why |
|---|---|---|---|
| all exit 0 | PASS | `DONE` | agreement |
| any non-zero | PASS | **`REPAIR_REQUIRED`** | **the only new authority** |
| all exit 0 | REPAIR_REQUIRED | `REPAIR_REQUIRED` | eval may see what commands cannot |
| no commands ran | any | claimed, tagged `evidence: none` | honest degradation (G8) |

Do:
1. Keep BOTH facts in `eval_report.json` — add `harness_verification`
   `{ran, commands, failures, exit_codes}` beside `verdict`. An override must be
   **auditable**, never silent.
2. When overriding, rewrite `summary` to name the failing command.
3. Q10 refinement: the harness synthesises **`return_to_coder` only**. A failing
   command is by definition an implementation defect; `REPLAN_REQUIRED` requires
   judging plan *shape* (`prompt.py:804-812`) — reading comprehension the
   harness does not have. Escalation to planner stays eval's privilege.

Do-not: do not let a green verification **upgrade** a claimed
REPAIR_REQUIRED/BLOCKED to PASS (row 3). Observation may only ever be *more*
conservative — otherwise the harness starts overruling a judge that read the
diff.

Exit criteria:
- [ ] T15: observed failure + claimed PASS ⇒ terminal `REPAIR_REQUIRED`, exit 1
- [ ] T15b: observed green + claimed PASS ⇒ `DONE` (no false positive)
- [ ] T15c: no commands ⇒ claimed verdict honoured, `evidence: none` recorded
- [ ] T15d: green observation never upgrades a non-PASS claim
- [ ] `eval_report.json` records both the claim and the observation

Kill-check: delete the override branch ⇒ **T15** fails (run goes `DONE` green).

---

### Step S12: Validate slice IDs against the plan (Q12)

Traces-to: G5 · CT6 · new CT20
Depends-on: **S3** (`extract_plan_ids`, shipped but imported by nothing) + **S12a** (§21 C-3: the harness has no plan path today)
Target liveness: L0→L2

**Why.** `_STEP_LINE_RE` (`workflow_artifacts.py:371`) accepts any
`S\d+[A-Za-z0-9_.-]*`. Probed: `- S99: PASS` and `- S404: PASS` are accepted as
real slices with `claimed_pass=True` (field renamed from `acceptance_matched`
by S14; `_scan_step_results` at `:438`, assignment at `:455`).

**Anchors re-verified 2026-09-07 (§24).** Three claims in v7 were stale:
`_STEP_LINE_RE` is at `:371` not `:342`; the field is `claimed_pass` not
`acceptance_matched`; and `plan_ids` is **no longer** unimported — S12a wired
`extract_plan_id` at `workflow_controller.py:25`. S3's *plural*
`extract_plan_ids` is still unused, which is what this step fixes.

Edit:
- path: `src/fa/inner_loop/workflow_controller.py` symbol: new `_validate_slice_ids(report, plan_text) -> tuple[EvalReport, list[str]]` change: **NEW** pure adjuster
- path: same file symbol: `_run_stage` eval branch change: `build_eval_report -> _validate_slice_ids -> write_eval_report`

**Seam (§24 D-1 — do not deviate).** `emit_eval_report` used to parse AND write
in one call, so any post-processing meant rewriting `eval_report.json` after
the fact. §24 split out **`build_eval_report`** (parse only). S12 MUST use
`build -> adjust -> write`, never `emit -> rewrite`: three planned steps (S12,
S13, S11b) adjust the same report, and re-writing would give three writes of
one file plus a last-writer-wins ordering dependency between them.

Do:
1. Claimed ID ∉ plan ⇒ **WARNING**, and drop it from `step_results` — it is
   noise, not evidence.
2. Plan slice with **no verdict** ⇒ **WARNING** (operator: warn, not block).
   Record as `unreported_slices` on `EvalReport`.
3. No plan resolvable (`ctx.plan_text() is None`, or `extract_plan_ids`
   returns `slices == ()`) ⇒ return the report **unchanged**, emit nothing.
   Legacy plans failing extraction is expected and is NOT a kill signal.

**Data shape (was unspecified — an executing agent would have had to guess).**
`EvalReport` is `@dataclass(frozen=True)` (`workflow_artifacts.py:200`), so
"drop it from `step_results`" means `dataclasses.replace(report, ...)`, not
mutation. `unreported_slices` is a **new field**:
`unreported_slices: tuple[str, ...] = ()`, added to `to_json_dict` and
`from_json_dict` (absent key ⇒ `()`), matching how S11a added `judged` and
S12a added `plan_path`.

**Comparison is exact-match, case-sensitive.** `extract_plan_ids` yields
`("S1","S5a","S11b",...)` and `_STEP_LINE_RE` captures the same token shape.
Do **not** normalise case or strip suffixes: `S5` and `S5a` are different
slices, and folding them would silently mark a real omission as reported.

Do-not: do not block on either condition yet. Revisit only after real-run
coverage data exists.

**Note the asymmetry, deliberately:** invention (`S404`) is cosmetic; the real
risk is **omission** — dropping `S7` from the list yields a clean PASS. Rule 2
is the one that matters.

Exit criteria:
- [ ] T16: `S404: PASS` ⇒ warning, dropped from `step_results`
- [ ] T16b: plan slice absent from eval output ⇒ warning + `unreported_slices`
- [ ] T16c: unresolvable plan ⇒ report returned unchanged, no warnings, no exception
- [ ] T16d: `S5` and `S5a` are never conflated (exact match, both directions)
- [ ] T16e: `eval_report.json` is written **once** per eval stage (S12 adjusts before the write, never after)
- [ ] `grep -c "extract_plan_ids" src/fa/inner_loop/workflow_controller.py` > 0 (S3's plural extractor alive)

Kill-check: remove the cross-check ⇒ **T16** fails.

---

### Step S13: Give eval the plan, the diff, and the related docs

Traces-to: G3 · new CT21
Depends-on: **S12a** (plan path) + **S12** (slice IDs) — see §21 C-2/C-3; NOT dependency-free as first written
Target liveness: L0→L3

**Why — the strongest finding in the audit.** The eval prompt is good: it is
told to judge "whether the coder satisfied the planner's execution contract"
using "repo-native verification commands." But:

- **PARTLY FIXED BY S12a.** `plan_path` now exists on `WorkflowContext`
  (`workflow_controller.py:148`) with `plan_text()` (`:154`) and
  `plan_identity()` (`:164`). What is still missing is the **delivery**: eval
  receives only `ctx.task_for(role)` (`:319`) — a task string. The plan is
  reachable by the harness and still never reaches the judge.
- No diff is produced anywhere in the controller.
- `fresh=index == 0` (`:583`, `:747`): only stage 0 is fresh, so **eval resumes
  the coder's session** and reads the coder's own success narration as context.

So the judge is asked to check code against a contract it was never handed,
while sitting inside the defendant's transcript.

Edit:
- path: `src/fa/inner_loop/workflow_controller.py` symbol: eval `stage_kwargs` change: append a harness-built evidence preamble to the eval task
- path: `src/fa/inner_loop/workflow_controller.py` symbol: new `_eval_evidence_block` change: **NEW**

Do:
1. Supply, as text the harness controls: the **plan path**, the **slice IDs**
   (from `extract_plan_ids`, shared with S12), a **`git diff --stat` + full
   diff** of the run's changes, and links to related docs (ADR index, the
   plan's own `## Artifacts` table).
2. Truncate the diff at a bounded size with an explicit
   `[diff truncated — N files, use fs_read_file]` marker. Never silently drop.
3. Paths, not pasted file bodies, for docs — eval has `fs_read_file`.

**Git invocation contract (was unspecified — three real hazards).**
- **Do NOT reuse `pr_intent._run_git`** (`pr_intent.py:817`): it passes
  `check=True` and raises on non-zero. The plan is advisory input, so a repo
  in any unexpected state (not a git repo, detached, git absent) must degrade
  to "no diff available", never fail the run. Use `subprocess.run(...,
  check=False)` and treat a non-zero return as an empty diff.
- **Diff WHAT, exactly?** `git diff` (unstaged) misses staged work and
  `--cached` misses unstaged. Use `git diff HEAD` so both are captured; a
  coder that staged nothing and a coder that staged everything then produce
  the same evidence.
- **Untracked files are invisible to `git diff HEAD`.** A slice whose entire
  contribution is a new file would show an EMPTY diff — the judge would see
  nothing and could still pass it. Append `git status --porcelain` so new
  files are at least named. State this limitation in the block itself.
- Bound the subprocess with a timeout; a hung `git` must not consume the run
  deadline.

Do-not: do not paste the whole plan inline (it is 1600+ lines and would evict
the diff). Do not remove the coder transcript in this step.

**`fresh=True` for eval — Q15 ANSWERED (§21.2).** Operator decision:
`--eval-fresh` toggle, **default = inherit the coder context** (today's
`fresh=index == 0`). The evidence block is required in BOTH modes: under the
default the judge still never receives the contract, and under `--eval-fresh`
this block is its only context.

Exit criteria:
- [ ] T17: the eval request contains the plan path and a non-empty diff
- [ ] T17b: an oversized diff is truncated with the marker, never dropped
- [ ] T17c: with no changes, the block says so explicitly (not an empty string)
- [ ] T17d: a workspace that is **not a git repo** yields the block minus the diff, run continues, no exception
- [ ] T17e: a run whose only change is an **untracked new file** still names that file in the block
- [ ] T17f: no `--plan` ⇒ the block omits plan lines rather than emitting empty headings

Kill-check: remove the preamble ⇒ **T17** fails.

---

### Step S14: `acceptance_matched` → `claimed_pass` (truth in naming)

Traces-to: G8 · CT4
Depends-on: none    Parallelizable-with: all
Target liveness: L0→L1

**Why.** `workflow_artifacts.py:426` computes
`acceptance_matched = verdict == "pass"` — literally `x = (x == "pass")`. The
name asserts an acceptance predicate was matched; the value restates the
model's claim. A reader of `eval_report.json` is actively misled. This is the
in-repo proof of the ceremony's own risk: a senior-sounding label with no
falsifiable content behind it.

Edit:
- path: `src/fa/inner_loop/workflow_artifacts.py` symbol: `StepResult.acceptance_matched` change: rename to `claimed_pass` (field, `to_json_dict`, `from_json_dict`, `:426`)
- path: `tests/test_workflow_artifacts.py` change: 4 assertion sites

Blast radius verified at tip: **3 src sites, 4 test sites, 0 other callers**;
no `eval_report.json` exists on disk and the artifact carries no
`schema_version`, so no migration is required.

Do:
1. Rename. Do **not** try to make it "real" here — that is S11's job, and a
   real acceptance check needs per-slice command attribution the plan does not
   yet define.
2. Once S11 lands, `claimed_pass` sits beside the observation and the pair is
   self-documenting.

Exit criteria:
- [ ] `grep -rc "acceptance_matched" src/ tests/` == 0
- [ ] T18: round-trip still passes with the new key

Kill-check: n/a (pure rename; the round-trip test is the guard).

---

### §19.1 Sequencing — ⚠️ SUPERSEDED by §21.1

> Verified against the tip in §21: S11 depends on S6, S13 depends on S12, and
> both S12/S13 need a plan path that does not exist. **Use §21.1's order:**
> S14 → S11a → S12a → S12 → S13 → S6 → S11b.

Original (kept for transfer): **S14 → S13 → S12 → S11.** Rationale: S14 is a free rename; S13 is independent
and probably the biggest quality win per line; S12 revives S3 and produces the
slice list S11 reports against; S11 needs S6's observations and is the actual
gate. S6 remains blocked on Q10 — now answered (harness synthesises
`return_to_coder` only), so **S6 is unblocked**.

### §19.2 Q15 — CLOSED (operator, 2026-09-07)

> **Q15 — should the eval stage run fresh?** Today `fresh=index == 0` seats eval
> in the coder's transcript. **ANSWERED: toggleable, inheriting the coder
> context by default.** `--eval-fresh` opts into a fresh session; absent, the
> behaviour is byte-identical to today. Rationale: independence is measurable
> only against a stable baseline, and the default must not silently change the
> cost/quality profile of existing runs. Detail + tests in §21.2.

---

## §20 Flow chart re-verified against §19 — and one new gap it exposed

Re-walked `workflow_controller.py` at the tip after writing S11–S14. The §6
chart in the audit was **correct but incomplete**: it drew the eval path and
omitted the no-eval path. Verifying it found F6.

### F6 (NEW) — a workflow with no eval stage reports `DONE` unconditionally

`_write_terminal_state:467-470`:

```python
if eval_report is not None:
    status = EVAL_VERDICT_TO_TERMINAL_STATUS.get(eval_report.verdict, "FAILED")
else:
    status = "DONE"          # <-- no judge ran, yet the run is a success
```

`--roles` is free-form over `WORKFLOW_STAGE_ROLES`, so `fa workflow --roles
coder` is legal and terminates `DONE`, exit 0, with **nothing having judged
anything**. `_run_adaptive:610-617` has the same shape ("adaptive workflow
completed without eval stage" → `return 0`).

Two further conditions narrow when a report exists at all — `_run_stage:336`
requires `role == "eval" AND code == 0 AND sink`. So an eval stage that exits
non-zero also yields `eval_report=None`; that case is caught earlier by the
stage-failure branch (`_run_initial_roles:588`), but the **empty-sink** case
(eval produced no final message) falls through to `DONE`.

**This is the same class of defect as F2/F3 and arguably the worst: absence of
evidence is read as evidence of success.** It is invisible in the default
planner→coder→eval pipeline, which is why it survived.

**Fix (folded into S11, no new step):** `reconcile_verdict` must treat "no eval
report" as its own row, and the terminal writer must distinguish *judged* from
*unjudged*:

| eval report | observations | terminal |
|---|---|---|
| present | per §19 S11 table | as tabled |
| **absent, eval was in `--roles`** | any | **`FAILED`** (the judge was asked for and did not answer) |
| **absent, eval not in `--roles`** | all exit 0 | `DONE` + `judged: false` recorded |
| **absent, eval not in `--roles`** | any non-zero | **`REPAIR_REQUIRED`** |

Rationale for row 3: the operator may legitimately run `--roles coder` as a
scratch pipeline; forcing `FAILED` would break a valid use. But the artifact
must say `judged: false` so no reader mistakes it for a verified run. Row 4 is
S11's whole point — an observed failure outranks the absence of a judge.

- [ ] T19: `--roles coder` with a failing verify command ⇒ `REPAIR_REQUIRED`
- [ ] T19b: `--roles coder` all green ⇒ `DONE` **and** `judged: false`
- [ ] T19c: eval in roles but empty sink ⇒ `FAILED`, not `DONE`

### §20.1 Corrected chart (verified line-by-line at the tip)

```
fa workflow --roles A,B,C --mode {linear|adaptive}
   │
   ├─ _run_stage:263  deadline check (single choke point, 4 call sites)
   │
   ├─ per stage: fresh = (index == 0)        :583 / :747
   │     └─ ONLY stage 0 is fresh; eval RESUMES the coder session   (F4 -> Q15)
   │
   ├─ coder stage ends
   │     ├─ S6a  capture packet        sink[-1].final_text
   │     └─ S6   run plan verify cmds  -> observations            [NEW]
   │
   ├─ eval stage ends
   │     ├─ :336  guard: role==eval AND code==0 AND sink
   │     │         -> else eval_report stays None  ................ F6
   │     ├─ parse_eval_report:433   claimed verdict + step_results
   │     ├─ S13  eval was given plan path + diff + doc links      [NEW]
   │     ├─ S12  validate slice IDs vs extract_plan_ids  -> WARN  [NEW]
   │     └─ S11  reconcile(observed, claimed) -> EFFECTIVE verdict[NEW]
   │
   ├─ route on the EFFECTIVE verdict
   │     linear   (:738): run to end; first non-zero exit stops
   │     adaptive (:596): return_to_coder  -> repair_round+1  (cap :621)
   │                      return_to_planner-> replan_round+1  (:707)
   │                      complete/blocked -> terminal
   │
   └─ _write_terminal_state:464
         eval_report present -> EVAL_VERDICT_TO_TERMINAL_STATUS
         absent              -> F6 table above (was: unconditional DONE)
```

**Invariant the chart now enforces:** every path to `DONE` passes through
either a judged verdict reconciled with observation (S11), or an explicit
`judged: false` record. There is no longer a silent path from "nothing ran" to
"success".

### §20.2 Where the operator's own rule now binds the harness

> *"never mark a slice complete from 'no exception'"*

| Actor | Bound by | Mechanism |
|---|---|---|
| coder | INJECT.md AFTER EDIT GATE | prompt nudge (non-falsifiable) |
| eval | eval system prompt | prompt nudge (non-falsifiable) |
| **harness** | **S11 + F6 fix** | **code: absence of evidence never yields DONE** |

Before §19 the rule bound only the two model roles — by prompt, i.e.
unfalsifiably. S11 and the F6 fix are the first places the *harness* is held to
it, in code, with kill-checks. That is the difference between a ceremony and a
contract.

---

## §21 Sequencing check for S14→S13→S12→S11 — plan does NOT yet support it

Operator proposal: close S14, S13, S12, S11 first, then return to S6. Verified
the dependency graph against the tip. **Two conflicts and one prerequisite gap.
The order is right in spirit; the plan as written cannot execute it.**

### C-1 — S11 declares `Depends-on: S6`, which the proposal inverts

S11's four-row table needs `observed` — produced by S6. As written, S11 cannot
precede S6.

**Resolution: split S11.** The F6 fix needs no observations at all; only the
reconciliation rows do.

Both halves are given real `### Step` headers below so a step scan cannot miss
them (the §19 S11 block stays as the shared rationale).

T19/T19b/T19c belong to **S11a**; T15* to **S11b**.

### Step S11a: Unjudged never means DONE (F6)

Traces-to: G3 · CT19    Depends-on: **none**    Blocks: nothing
Target liveness: L0→L3

**Highest-ROI item in §19–§21, and dependency-free.** Today
`_write_terminal_state:467` sets `status = "DONE"` whenever `eval_report is
None`, and `_run_adaptive:610-617` returns 0 with reason "adaptive workflow
completed without eval stage". `fa workflow --roles coder` therefore reports
success with nothing having judged anything.

Edit:
- path: `src/fa/inner_loop/workflow_controller.py` symbol: `_write_terminal_state` change: replace the unconditional `else: status = "DONE"`
- path: same symbol: `_run_adaptive` no-eval branch change: same rule
- path: `src/fa/inner_loop/workflow_artifacts.py` symbol: `FlowState`/report change: record `judged: bool`

Do:
1. eval WAS in `--roles` but no report (incl. empty sink, `_run_stage:336`
   guard) ⇒ **`FAILED`**. The judge was asked for and did not answer.
2. eval NOT in `--roles` ⇒ `DONE` **and** `judged: false` in the artifact. A
   scratch `--roles coder` run stays valid but is never mistakable for verified.
3. Once S6 lands, row 4 of §19's table (unjudged + observed failure ⇒
   `REPAIR_REQUIRED`) is added by **S11b**, not here.

Do-not: do not make eval mandatory in `--roles` — that breaks a legitimate
scratch pipeline. The fix is honest labelling, not forced ceremony.

Exit criteria:
- [ ] T19: eval in roles but report absent ⇒ `FAILED`, not `DONE`
- [ ] T19b: `--roles coder` all green ⇒ `DONE` **and** `judged: false`
- [ ] T19c: eval ran but empty sink ⇒ `FAILED`

Kill-check: restore `else: status = "DONE"` ⇒ **T19** fails.

### Step S11b: Reconcile claimed verdict vs harness observation

Traces-to: G3 · CT4 · CT19    Depends-on: **S6** (observations)
Target liveness: L0→L3

The remaining three rows of §19's table, `harness_verification` in
`eval_report.json`, and T15/T15b/T15c/T15d. Rationale, truth table, and the
"observation may only ever be more conservative" invariant are in §19 S11 and
are not restated here.

### C-2 — S13 consumes S12's output

S13 Do-1 says "the **slice IDs** (S12)". So S13 depends on S12, and the
proposed S13→S12 order is backwards. Two options:

- (a) reorder to **S12 → S13** (dependency-honest), or
- (b) drop slice IDs from S13's first cut — plan path + diff + doc links carry
  most of the value and need nothing from S12.

**Recommend (a).** S12 is small, and S13 is materially better with the slice
list in it.

### C-3 (prerequisite gap) — the harness has no plan path to give

Both S12 and S13 assume the harness can locate the plan. It cannot:

- `WorkflowArtifactPaths` (`workflow_controller.py:106-109`) has exactly three
  fields: `base_dir`, `eval_report`, `flow_state`. **No plan.**
- `emit_eval_report` is called with `plan_id=ctx.run_id` (`:352`), and
  `active_plan_id=ctx.run_id` at `:274,399,438,478`. **`plan_id` is the run ID
  wearing a plan's name** — the same class of defect as `acceptance_matched`
  (S14): a field whose name promises a plan reference and whose value is
  something else.
- `grep` for `plan` + `path|file|.md` in the controller ⇒ **zero hits**.

So S12 ("validate IDs against the plan") and S13 ("give eval the plan path")
both have an unstated prerequisite that does not exist.

**Resolution — new S12a, blocking both.**

### Step S12a: Give the workflow a plan reference

Traces-to: G5 · CT6 · CT21    Depends-on: none    Blocks: S12, S13
Target liveness: L0→L2

Edit:
- path: `src/fa/cli.py` symbol: `workflow` parser change: add `--plan PATH`
- path: `src/fa/inner_loop/workflow_controller.py` symbol: `WorkflowContext` change: add `plan_path: Path | None = None`
- path: same symbol: `emit_eval_report` call change: pass a real plan identity, not `ctx.run_id`

Do:
1. `--plan` is **optional**. Absent ⇒ `plan_path=None`; S12 and S13 degrade to
   today's behaviour with no warnings. Legacy/planner-authored runs must not
   break (standing operator rule: legacy plans failing extraction is expected
   and is NOT a kill signal).
2. Keep `plan_id` as-is for artifact compatibility, but populate it from the
   plan's own ID when a plan is supplied. Do not silently redefine the field.
3. Record `plan_path` in `flow_state` so a run is traceable to its contract.

Do-not: do not make `--plan` mandatory. Do not infer the plan by globbing
`worklogs/implementation-plans/` — guessing the contract is worse than not
having one.

Exit criteria:
- [ ] T20: `--plan P` ⇒ `ctx.plan_path == P`, recorded in `flow_state`
- [ ] T20b: no `--plan` ⇒ `None`, no warning, behaviour unchanged
- [ ] T20c: `--plan` pointing at a missing file ⇒ clear error before any stage runs

Kill-check: drop the wiring ⇒ **T20** fails and S12/S13 have no input.

### §21.1 Corrected order

```
S14  DONE (shipped 54bf663)
 │
 ├─ S11a  F6: unjudged never means DONE      no deps   <- do next, highest ROI
 ├─ S12a  --plan / plan_path                 no deps
 │    └─ S12   validate slice IDs            needs S12a + S3
 │         └─ S13   eval gets plan+diff+IDs  needs S12a, S12
 │
 └─ S6    harness runs verify commands       unblocked (Q10 answered)
      └─ S11b  reconcile claimed vs observed needs S6
```

**Answer to the operator's question: yes, close the new slices first — but as
S14 → S11a → S12a → S12 → S13 → S6 → S11b.** S11 splits around S6 rather than
sitting entirely before or after it. Everything up to S13 is dependency-free of
S6, so the intent of the proposal holds.

### §21.2 Q15 answered — eval freshness is toggleable, inherits by default

**Operator decision: `--eval-fresh` toggle, default = inherit the coder
context (today's `fresh=index == 0`).** Q15 is CLOSED.

Consequences for S13: the evidence block (plan path, diff, doc links) must be
supplied **regardless** of the toggle, because under the default the judge
still never receives the contract. Under `--eval-fresh` it becomes the eval
stage's *only* context, so it is load-bearing in both modes — S13 is not
obsoleted by the flag.

Placement note: per the standing operator rule, toggles are set **between**
`fa run` invocations, so this is a launch-time CLI flag resolved once — same
shape as `--inject`, no mid-loop reconfiguration.

- [ ] T21: `--eval-fresh` ⇒ eval stage starts a fresh session
- [ ] T21b: default (absent) ⇒ eval resumes, byte-identical to today

---

## §22 S11a implementation record — SHIPPED

**Status: COMPLETE.** F6 closed. `judged` is now a first-class artifact field.

### What shipped

| Edit | File |
|---|---|
| `terminal_status_without_eval(*, eval_requested)` — pure, exported | `workflow_controller.py` |
| `_write_terminal_state(..., eval_requested=False)`; `else` branch delegates | same |
| `judged=eval_report is not None` on the `FlowState` write | same |
| `eval_requested="eval" in roles` at the two None-capable call sites (`_run_adaptive`, `_run_linear`) | same |
| `FlowState.judged: bool = True` + serialise + `from_json_dict` (absent ⇒ True) | `workflow_artifacts.py` |
| 8 tests (2×C0 decision, 1×C0 compat, 5×C1 composition-root) | `tests/test_workflow_no_eval_terminal.py` (NEW) |

Only **2 of 7** `_write_terminal_state` call sites can pass `eval_report=None`;
the other five always hold a report. Threading a default-`False` keyword rather
than changing all seven kept the diff to +47/−4 in `src/`.

### Verification (actual output, not "no exception")

- `tests/test_workflow_no_eval_terminal.py` — **8 passed**
- controller/artifact suites — **57 passed** after re-scoping two deadline tests
- full suite — **9 failed, 3922 passed**; `comm -23` vs baseline **empty** (zero new)
- `ruff check src/fa tests` — All checks passed; `ruff format --check` clean
- `test_live_check_script.py` **28 passed**; battery **28 OK, 0 missed**
- authoring gate on a real workspace — **1 passed**

### Mutation battery (C4) — 4 run, 4 killed

| # | Mutation | Result |
|---|---|---|
| M1 | restore `return "DONE", ""` unconditionally (the original F6 bug) | **5 failed** ✅ |
| M2 | `judged=True` hard-coded | **3 failed** ✅ |
| M3 | `eval_requested=False` at both call sites | **3 failed** ✅ |
| M4 | `FlowState.judged` default `True`→`False` | **survived first**, then killed |

**M4 is the finding worth keeping.** The first compat test asserted only
`from_json_dict({...no judged...}).judged is True` — which passes under the
mutant because the deserialiser carries its *own* `data.get("judged", True)`.
Two independent defaults guard the same concept, and the test pinned the wrong
one. Fixed by additionally constructing a `FlowState` without the field. General
lesson: **when a default exists in two places, an oracle that exercises only one
of them is not a test of "the default".**

### Collateral: two deadline tests re-scoped, not weakened

`test_no_deadline_runs_the_full_pipeline` and
`test_generous_deadline_runs_the_full_pipeline` used `_RecordingStage`, which
returns 0 **without appending a `SessionOutcome`** — in production a successful
eval stage always appends one, so the fixture was unfaithful. Post-S11a their
`--roles planner,coder,eval` correctly yields `FAILED`.

Their real oracle is "every stage was dispatched", not "the work was accepted",
so both were re-scoped to `["planner","coder"]` and **strengthened** with
`assert state.judged is False`. The behaviour change is intended, and the
alternative (relaxing S11a so a silent judge passes) would have deleted the
feature to save a fixture.

### Not done here (correctly deferred)

Row 4 of §19's table — unjudged **and** an observed command failure ⇒
`REPAIR_REQUIRED` — needs S6's observations and belongs to **S11b**.

### No new Q#

No new policy choice surfaced. `eval_requested` is derived from `roles`, which
the caller already owns; `judged` defaults True purely for artifact
back-compatibility.

**Next per §21.1: S12a** (`--plan` / `plan_path`), which unblocks S12 and S13.

---

## §23 S12a implementation record — SHIPPED

**Status: COMPLETE.** The workflow now has a plan reference. S12 and S13 are unblocked.

### What shipped

| Edit | File |
|---|---|
| `_PLAN_ID_RE` + `extract_plan_id(text) -> str \| None`, exported | `plan_ids.py` |
| `WorkflowContext.plan_path: Path \| None = None`; `plan_text()`; `plan_identity()` | `workflow_controller.py` |
| `emit_eval_report(plan_id=ctx.plan_identity())` — was `ctx.run_id` | same |
| `run_workflow(..., plan_path=None)` threading | same |
| terminal `FlowState(plan_path=...)` | same |
| `FlowState.plan_path: str = ""` + serialise + parse | `workflow_artifacts.py` |
| `--plan PATH` + up-front existence check | `cli.py` |
| 11 tests (4×C0 extractor, 3×C0 identity, 2×C1 root, 2×C2 CLI) | `tests/test_plan_reference.py` (NEW) |

Diff: **+106/−1** across four `src/` files. Purely additive; every field
defaults to the pre-S12a value.

### Plan correction — Do-2 had no producer

S12a Do-2 said "populate `plan_id` from the plan's own ID", but `PlanIds`
exposes **no plan-ID field** — the instruction had no source. Not promoted to a
`Q#`: it is a missing producer for a decision already made, not a new policy
choice. Resolved by parsing the `Plan-ID:` convention that plans already use.

**Three real shapes exist in this repo** and all must parse:

```
Plan-ID: `PLAN-foo`      backticked (most common)
**Plan-ID:** PLAN-foo    bolded label
# PLAN: Title    Plan-ID: PLAN-foo    inline at end of H1 (this plan's own form)
```

Run against all 32 files in `worklogs/implementation-plans/`: **12 resolve**,
the rest return `None`. That is the expected outcome — legacy plans failing
extraction is not a kill signal.

### Verification (actual output)

- `tests/test_plan_reference.py` — **11 passed**
- `plan_ids` + `no_eval_terminal` + authoring gate — **42 passed**
- full suite — **9 failed, 3933 passed**; `comm -23` vs baseline **empty**
- `ruff check src/fa tests` — All checks passed; `format --check` clean
- `test_live_check_script.py` **28 passed**; battery **28 OK, 0 missed**

### Mutation battery (C4) — 5 run, 5 killed

| # | Mutation | Result |
|---|---|---|
| M1 | terminal `FlowState` never records `plan_path` (the kill-check) | 1 failed ✅ |
| M2 | `plan_identity()` always returns `run_id` | 1 failed ✅ |
| M3 | `extract_plan_id` always `None` | 4 failed ✅ |
| M4 | CLI drops the missing-file guard | 1 failed ✅ |
| M5 | regex handles only the tidy bare-line shape | 4 failed ✅ |

M5 is the one worth keeping: it is the mutant a naive test suite misses. Pinning
all three declaration shapes against real repo samples — rather than one
invented canonical form — is what kills it.

### Design notes

- **`--plan` is optional and never inferred.** No globbing of
  `worklogs/implementation-plans/`: guessing the contract is worse than having
  none, and a wrong plan would make S12's validation actively misleading.
- **Fail fast, leave nothing behind.** The existence check sits with the
  role-allowlist check, ahead of `run_id` allocation and any artifact write, so
  a mistyped path cannot produce a half-written session (T20c asserts the
  absence of `flow_state.json`).
- **The plan is advisory input, not a dependency.** `plan_text()` swallows
  `OSError` and warns; a plan deleted mid-run degrades to the `run_id` fallback
  rather than failing an otherwise healthy pipeline.

### No new Q#

No new policy choice surfaced.

**Next per §21.1: S12** (validate slice IDs against the plan) — its two inputs,
`extract_plan_ids` (S3) and `plan_path` (S12a), now both exist.

---

## §24 Adversarial review of ALL remaining slices — 2026-09-07 (tip `ce921f1`)

Remaining: **S12, S13, S6a, S6, S6b, S7, S11b, S8, S9**. Every finding below was
checked against code; nothing is inferred from the plan alone.

### 24.0 Trajectory — does the next slice advance what matters?

**Yes, and the ordering holds.** S12 → S13 both feed the completion gate, which
§18–§20 established as the weakest link (a model-typed `PASS` was the sole cause
of `DONE`). S12a shipped the prerequisite. No drift, no premature abstraction.

**One deferral the main plan requires and the remaining slices silently drop:**
§19 F1 established that `step_results` has **zero consumers** — parsed, stored,
never read by a decision. S12 adds *validation* of those results and S11b
overrides the *top-level* verdict, but **nothing makes a per-slice `FAIL` route
anything.** A run can end `DONE` with `S7: FAIL` in `step_results`. Recorded as
**Q16** below rather than silently carried.

### 24.1 CONFIRMED DEFECTS

| # | Defect | Evidence | Status |
|---|---|---|---|
| **D-1** | **`emit_eval_report` fuses parse + write**, but S12, S13 and S11b all must adjust the report before it persists. Each would have to rewrite `eval_report.json` after the fact: 3 writes of one file, a window where the artifact contradicts the routing decision, and a last-writer-wins ordering dependency between nominally independent steps. | `workflow_controller.py` `parse_eval_report(...)` then `write_eval_report(...)` in one body; single production caller at `:383` | **FIXED** — split out `build_eval_report` (parse only), exported. `build → adjust → write` is now the mandated pipeline. |
| **D-2** | **S6a's mechanism is impossible.** "Append-only JSONL through the existing atomic-write helper (`:510-549`)" — the helper is at `:539` and ends in `os.replace()`, a whole-file overwrite. It would truncate the log to the newest packet every call, destroying all prior packets, while passing any single-packet test. | `_write_json_atomic:539`, `os.replace(temp_path, path)` | **FIXED in plan** — corrected to `open(..., "a")` + one `json.dumps` per line. |
| **D-3** | **S8's IntentGuard edit targets the wrong symbol.** v7 says add `draft_tool_available` to "`_requires_draft:226`". That is a **module-level function** `(call, repo_root)` with no instance access — it cannot read a constructor flag. | `intent_guard.py:226` is `def _requires_draft(call, repo_root)`; hook call site `:304`, deny at `:310` | **FIXED in plan** — gate at the call site. |
| **D-4** | **Stale anchors across four steps.** S12: `_STEP_LINE_RE` `:342`→**`:371`**; field `acceptance_matched`→**`claimed_pass`** (renamed by S14); "`plan_ids` imported by nothing" is now **false** (S12a wired `extract_plan_id` at `:25`). S7: `_build_run_hook_registry` `:1716`→**`:1807`**. S8: `_build_run_tool_registry` `:1625`→**`:1760`**; `_READINESS_PROMPT_EXTRA` `:159`→**`:165`**; `_readiness_prompt_extra` `:167`→**`:173`**. S13: eval task arg `:283`→**`:319`**. | direct grep at tip | **FIXED in plan.** |
| **D-5** | **S12's data shape was unguessable.** "Drop it from `step_results`" / "record as `unreported_slices`" — but `EvalReport` is `@dataclass(frozen=True)` (`:200`) and has no such field. An agent would have had to invent mutation semantics and a schema. | `workflow_artifacts.py:200` | **FIXED in plan** — `dataclasses.replace`, new field with serialise/parse and absent-key default, matching the `judged`/`plan_path` precedent. |
| **D-6** | **S13's git contract was unspecified, with three real failure modes.** (a) The obvious helper `pr_intent._run_git:817` uses `check=True` and **raises** — fatal for advisory input. (b) `git diff` vs `--cached` each miss half the work. (c) **`git diff HEAD` cannot see untracked files**, so a slice that only ADDS files shows an empty diff and the judge sees nothing. | `pr_intent.py:817-829` | **FIXED in plan** — `check=False`, `git diff HEAD`, plus `git status --porcelain` for new files, with the limitation stated in the block. |

### 24.2 Suspicions (not confirmed — flagged, not acted on)

- **S6's `bash_timeout_seconds` reuse.** S6 says enforce "a per-command timeout
  (`bash_timeout_seconds`)". That budget was sized for *model-issued* commands;
  a plan's full test suite can legitimately exceed it. Not verified against the
  configured value, so not a defect — but S6 should state whether the
  verification budget is the same knob or its own.
- **S6b's label parsing vs G8.** S6b reads labelled lines out of prose packets.
  The label set matches `INJECT.md`, so a compliant packet parses — but a model
  that reformats slightly yields a silently emptier draft. The plan's
  "omit the field" rule handles it; the risk is that omission is invisible.

### 24.3 Verified sound — no action

- **S7's mechanism.** `BEFORE_TOOL_EXEC` exists (`hooks/base.py:28`), the hooks
  package is the right home, and "never returns deny" is checkable by grep.
  Only the registration anchor was stale.
- **S8's registry seam.** `_build_run_tool_registry` already takes `role` as its
  first positional arg, so role-conditional registration needs no signature
  change, and the conformance caller passes `"coder"` (`:2915`) so it keeps the
  tool. S8's D10 concern is correctly scoped.
- **S12a's output is genuinely reusable.** `ctx.plan_text()` / `plan_identity()`
  give S12 and S13 exactly what they need with no further plumbing.

### 24.4 New open question

> **Q16 — should a per-slice `FAIL` block completion?** Today `step_results` is
> inert (§19 F1): a run can end `DONE` while carrying `S7: FAIL`. S12 validates
> those IDs and S11b overrides the top-level verdict, but neither makes a
> per-slice failure route anything.
> (a) Any `FAIL` in `step_results` forces `REPAIR_REQUIRED` — strongest, and
> makes slice granularity real.
> (b) Warn only, like S12's `unreported_slices` — consistent with the current
> "warn, don't block" posture.
> (c) Leave inert; rely on the top-level verdict.
> Recommendation **(a)**, deferred to its own step after S11b lands, since it
> changes routing authority. **Not decided — do not implement inside S12.**

### 24.5 DoD tightening applied

S12 gained **T16d** (`S5` vs `S5a` never conflated — exact-match, both
directions) and **T16e** (`eval_report.json` written exactly once per eval
stage, i.e. the D-1 seam is respected). S13 gained **T17d** (non-git workspace
degrades), **T17e** (untracked-only change still named), **T17f** (no `--plan`
omits headings rather than emitting empty ones). All are binary and observable.

---

## §25 — S12 implementation record (shipped `4c5731a`)

**Contracts:** G5 · CT6 · CT20 · Q16. **Files touched:** `workflow_artifacts.py`,
`workflow_controller.py`, new `tests/test_slice_id_validation.py`. Classes C0 + C1.

### What shipped

`validate_slice_ids(report, plan_text) -> tuple[EvalReport, tuple[str, ...]]` and
`EvalReport.unreported_slices: tuple[str, ...] = ()`.

Order of operations (deliberate): Q16 fail-override **first** (plan-independent),
then `plan_text is None` ⇒ no-op, then `extract_plan_ids(...).slices` empty ⇒ no-op,
then drop invented IDs, then compute unreported.

| Defect closed | Before | After |
|---|---|---|
| Invented IDs | `- S404: PASS` parsed as a real slice, inflating coverage | dropped + warned |
| **Omission** | dropping `S7` yielded a clean `PASS` over unexamined work | recorded in `unreported_slices` + warned |
| Inert `step_results` (§19 F1) | run ends `DONE` carrying `S7: FAIL` | **Q16** ⇒ `REPAIR_REQUIRED` |

### Scope decisions (stated, not silent)

- Only the literal `fail` verdict blocks. `partial`/`not_evaluated` do not — neither
  asserts the slice is broken, and widening would turn "the evaluator was unsure"
  into a hard repair loop.
- The override is **one-directional**: it never upgrades a non-`PASS` verdict, so
  `BLOCKED`/`REPLAN_REQUIRED` survive intact.
- Q16 holds with no plan: a reported failure is a fact about the work, independent
  of whether the harness can see the contract.
- Matching is exact and case-sensitive. `S5a` must not satisfy `S5`.
- Legacy/unparseable plans ⇒ silent no-op (operator ruling: not a kill signal).

### D-1 compliance

The function is pure — no logging, no writes. The eval branch is now
`build_eval_report → validate_slice_ids → write_eval_report`: exactly one write,
already adjusted. Warnings surface via `logger.warning` + stderr at the call site.

### Negative proof (the part that counts)

Mutation battery **9/9 killed**, including the L3 kill-check (deleting the
`validate_slice_ids` call at the producer site in `_run_stage`). Also killed:
case-folded matching, prefix matching (`S5a` satisfying `S5`), Q16 widened to
`partial`, Q16 with the `PASS` guard dropped, Q16 skipped when no plan, dropped
serialisation, and **each of the two independent defaults** (dataclass and
`from_json_dict`) removed separately.

12 tests: 11 C0 on the pure adjuster, 1 C1 booting the real `run_workflow` and
asserting on the persisted `eval_report.json` — the file the repair loop actually
reads, not the in-memory return value.

### Verification actually run

`3947 passed`, same 9 pre-existing baseline failures, `comm -23` empty (no
regressions); `ruff check src/fa tests` clean; `test_live_check_script.py` 28
passed; adversarial battery `28 OK, 0 missed`; authoring gates 152 passed.

### Host finding (not a regression)

`tests/test_workspace_bootstrap.py` aborts this host's pytest run with
`INTERNALERROR: cannot instantiate 'WindowsPath'` at ~97%. **Reproduced at `HEAD`
with the S12 changes stashed**, so it is a python-3.11-host artifact, not a
regression. Excluded from the comparison run. The first full-suite result this
session was therefore *invalid* — the `comm` output was empty only because the run
had aborted. Flagged for S9/e2e: on the live host (python ≥3.13) this should be
re-checked rather than assumed.

**Remaining:** S13, S6, S6a, S6b, S7, S11b, S8, S9.

---

## §26 — S13 implementation record (shipped `f1043b9`)

**Contracts:** G3 · CT21 (consumes S12a `plan_path`, S12 `extract_plan_ids`).
**Files touched:** `workflow_controller.py`, new `tests/test_eval_evidence_block.py`.
Classes C0 + C1. **Kill-check:** the append at the eval `stage_kwargs` site.

### What shipped

`_eval_evidence_block(ctx, *, runner=None)` + `_git_output(...)`, appended to the
eval stage task **only**. Constants `EVAL_DIFF_MAX_CHARS` (60k),
`EVAL_GIT_TIMEOUT_SECONDS` (15), `EVAL_DOC_PATHS`, all exported.

The judge now receives, as harness-controlled text: plan path, declared slice IDs,
`git diff HEAD --stat`, a bounded diff, **named untracked files**, and doc paths.

### Plan corrections found during source verification

| Plan said | Truth at tip |
|---|---|
| link "the plan's own `## Artifacts` table" | **UNFOUNDED** — `grep -rln "^## Artifacts" worklogs/ knowledge/` returns nothing. No plan in this repo has one. Dropped; links the ADR index instead. |
| `_run_git` at `inner_loop/pr_intent.py:817` | It is at **`hygiene/pr_intent.py:817`** |
| — | `inner_loop/tools/pair_tools.py:28` already has a correct-shaped helper, but `workflow_controller` imports nothing from `tools/`; kept a local helper rather than add a layering edge. |

### D-6 verified empirically, not assumed

In a scratch repo: `git diff HEAD` on an untracked new file prints **nothing**,
while `git status --porcelain` shows `?? newfile.py`. An add-only slice would have
shown the judge an empty diff. The test asserts this precondition against real git
*before* asserting the block compensates.

### Degradation contract

Advisory input. `check=False` + timeout; non-git workspace, absent binary,
timeout, or non-zero exit each collapse to `None` and drop only their own section.
"No changes" is stated explicitly — an omitted section reads as "diff unavailable"
when the truth is "the coder changed nothing", itself a finding worth a FAIL.

### Negative proof

**11/11 mutants killed**: kill-check (append removed), `diff HEAD`→`diff`,
`diff HEAD`→`--cached`, untracked handling dropped, `check=True`, timeout removed,
silent truncation, no-changes message removed, role gate widened to coder, task
substituted instead of appended, slice IDs dropped, docs-existence filter removed.

**Two of my own tests were broken, and mutants found them, not review:**
1. `"STAGED_CONTENT"` is a **substring** of `"UNSTAGED_CONTENT"`, so the staged
   assertion passed on unstaged text and the `git diff` mutant survived.
2. The same fixture committed the file it meant to leave staged, so nothing was
   actually staged.
Both now use non-overlapping markers and assert preconditions against git first.
This is the fourth instance this session of *the check* being the broken thing.

### Verification actually run

Baseline **re-measured by stashing** rather than from notes (the session's recorded
baseline list turned out to be unreliable after a sandbox reset): `9 failed / 3947
passed` before, `9 failed / 3962 passed` after — identical failure sets, +15.
`ruff check src/fa tests` clean; `test_live_check_script.py` 28 passed; adversarial
battery `28 OK, 0 missed`; LogKind contract PASS.

### Deferred (not silently skipped)

`fresh=True` for eval is **Q15, already answered in §21.2**: an `--eval-fresh`
toggle defaulting to inherit. Not implemented here — S13's scope is delivery of
the evidence, and the block is required in both modes. The judge still resumes
the coder's session by default; that remains open.

**Remaining:** S6, S6a, S6b, S7, S11b, S8, S9.

---

# §27 — SLICE S15: close the two-pass audit findings (BLOCKING)

**Status: BLOCKING.** S6, S6a, S6b, S7, S11b, S8, S9 are **on hold** until S15
lands. Rationale: S12/S13 shipped the *evidence pipe* and one enforcement rule,
but two audit passes proved the pipe can be empty, mutable, and leaky. Building
S6+ on top would stack features on an unsound base — every later slice consumes
`eval_report.json` or the eval prompt, and both are currently untrustworthy.

Depth: **P2** (cross-module: controller + CLI + prompt + flags + ADR).
Mode: `plan`. MAX effort. Sources: `AUDIT-S12-S13-adversarial.md` (round 1),
`AUDIT-S12-S13-round2.md` (round 2).

## 27.0 Preflight log

```text
roots checked:  cli.py:_cmd_workflow(:1369 --plan, :1448 run_workflow)
                workflow_controller.py:_run_stage(:558 stage_task)
                coder_loop.py:drive_session(:651 user_msg log)
greps/reads -> findings:
  _redact              -> coder_loop.py:150 def, :2090 ONLY call (tool results)
  user_msg             -> coder_loop.py:651 task logged verbatim, unredacted
  plan_text()          -> workflow_controller.py:174,457,639,643 (4 reads/stage)
  _SLICE_RE            -> plan_ids.py:55 heading+colon only
  untracked line       -> workflow_controller.py:482 (uncapped)
  EVAL_DIFF_MAX_CHARS  -> :377 def, :488 use
  active_plan_id       -> :547,:691,:730,:793 all = ctx.run_id
  write_eval_report    -> :647 (1/stage, but N/loop, same path)
  INJECTION_SPECS      -> injections.py:123 (only coder_slice_ceremony)
  SecretRedactor       -> observability/redaction.py:21, .redact() pure, stdlib
  sha256 convention    -> authoring_tcb.py:264 "sha256:"+hexdigest
gold patterns mirrored: CODER_SLICE_CEREMONY spec (injections.py:114) +
                        its 5 coupled sites (flags dataclass, as_dict,
                        fail-open set, type map, loader)
conflicts/invariants:   ADR-12 (one redaction chokepoint), ADR-10 I-6
                        (registered/once/role-gated/observe-default/
                        introspectable), ADR-11 I5 (no placeholder asserts)
current liveness:       S12/S13 = L2 (call-reachable, behaviour WRONG on the
                        paths below), not L3
unresolved -> Q#:       Q17 (blocking), Q18, Q19
```

## 27.1 Executive intent

**G9** — the judge cannot be shown an empty, stale, or attacker-shaped picture
of the work.
**G10** — the contract being validated is immutable for the run's duration.
**G11** — no harness-composed prompt text can carry a secret to a provider.
**G12** — every injected payload is registered, gated, and introspectable.

Non-goals (explicit): `--eval-fresh` (Q15, separate slice); S6a's append-only
packet log (own slice, referenced by B-12); rewriting `_STEP_LINE_RE`'s grammar
(B-3 warns, does not re-parse); multi-repo/monorepo diff strategies.

Minimal mechanism: **one snapshot object** (`RunEvidence`) computed once per
run and carried as frozen data, plus **one redaction chokepoint** on the task,
plus **one registry entry**. No new subsystem.

## 27.2 GAP ledger — current → target

| GAP | Finding | Current (verified) | Target | Falsifiable proof |
|---|---|---|---|---|
| GAP20 | B-1 | `_redact` applied only at `coder_loop.py:2090` (tool results); task reaches provider + `events.jsonl` raw | every task redacted before dispatch | T30: secret in diff ⇒ absent from `args.task` at `drive_session` boundary AND from `events.jsonl` |
| GAP21 | A-1/B-6/B-7 | `git diff HEAD` at eval time; committed work invisible, worktree drift, monotonic growth | diff vs **run base commit**, captured at run start | T31: coder commits ⇒ work still visible; T32: base pinned at t0 |
| GAP22 | B-2 | `plan_text()` re-reads per call; plan writable in-workspace | read once at entry, hashed, frozen | T33: mutate plan mid-run ⇒ validation uses t0 text + warns |
| GAP23 | B-3 | `--plan` given but unparseable ⇒ zero warnings | structured warning naming the file | T34: em-dash plan ⇒ warning emitted, run continues |
| GAP24 | B-4/B-5 | untracked list uncapped (170k observed); `.fa/` reported as deliverable | capped + `.fa` excluded | T35: 5000 files ⇒ block ≤ budget; T36: `.fa/` absent |
| GAP25 | B-8 | truncation by git file order; filler evicts security hunk | per-file budget, no file evicts another | T37: 9000-line filler ⇒ `z_crit.py` hunk still present |
| GAP26 | A-2 | `unreported_slices` written, never read | coverage rule (Q17) | T38: 1-of-20 judged ⇒ not DONE |
| GAP27 | A-3 | repair coder re-run with identical task, no findings | findings appended to repair task | T39: round 2 task contains round 1 failure text |
| GAP28 | A-4 | block cites `fs_read_file`; eval registry lacks it | cite eval's real tools | T40: block tool names ⊆ eval registry |
| GAP29 | A-5 | `s1` parsed then dropped as invented | case-fold compare, `S5`≠`S5a` | T41: `s1` matches `S1`; T42: `S5a` ≠ `S5` |
| GAP30 | A-6 | Q16 can fire on an ID then delete its evidence | keep the fail record | T43: invented FAIL ⇒ cause visible in artifact |
| GAP31 | B-9 | S13 block unregistered, always-on, invisible | `InjectionSpec` + flag + `fa inject` row | T44: `fa inject` lists it; T45: `off` ⇒ byte-identical task |
| GAP32 | A-7/B-10 | coder text pasted unfenced; judge not told what is authoritative | fenced + prompt clause | T46: fence survives payload containing a fence |
| GAP33 | B-11 | `flow_state.active_plan_id` = run_id ≠ `eval_report.plan_id`; run_id collides at 1s | one identity; collision-resistant id | T47: both artifacts agree; T48: two same-second runs differ |
| GAP34 | B-12/A-10 | repair rounds overwrite one file; T16e never written | per-round retention + the missing test | T49: 3 rounds ⇒ 3 recoverable records; T50: exactly 1 write/stage |

## 27.3 Contract cards

```text
CT22: run_evidence_snapshot  TYPE:data
PRODUCER: workflow_controller.RunEvidence (NEW), built in run_workflow before stage 0
CONSUMER: _eval_evidence_block, validate_slice_ids, _write_terminal_state
SCHEMA: frozen dataclass {base_commit: str|None, plan_text: str|None,
        plan_sha256: str|None, plan_path: Path|None, plan_id: str|None}
AUTHORITY: source of truth for BOTH artifacts; nothing re-reads the plan or
        re-resolves HEAD after t0
SIDE EFFECTS: two subprocess reads + one file read, all at t0, all check=False
INVARIANTS: (1) computed exactly once per run_workflow call;
            (2) plan_sha256 == sha256(plan_text) when plan_text is not None;
            (3) base_commit is None only when HEAD does not resolve
KILL-CHECK: recompute mid-run instead of reusing ⇒ T33 fails
```

```text
CT23: task_redaction  TYPE:security
BOUNDARY: harness-composed prompt text → provider
ALLOW: text with no known secret substring (raw/b64/hex/url/reversed)
DENY:  n/a — this masks, it does not block (an advisory block must not fail a run)
FAIL POLARITY: fail-SAFE (mask). A redactor that errors must not emit raw text.
PRODUCER: cli.py `_cmd_run`, after redactor construction (:2244) and before
        drive_session (:2408) — the ONE point where both exist
OBSERVABLE: masked token in args.task and in events.jsonl user_msg
C3 REQUIRED: yes
KILL-CHECK: remove the redact call ⇒ T30 fails
```

```text
CT24: eval_evidence_injection  TYPE:signal
PRODUCER: InjectionSpec("eval_evidence_block", roles={"eval"},
          read_flag=lambda f: f.eval_evidence_block_mode, default "enforce"*)
CONSUMER: _run_stage eval branch
TRIGGER: role == "eval" AND mode == enforce
MODES: off (byte-identical task) | observe (telemetry, no payload change) | enforce
*DEVIATION FROM I-6 DEFAULT: see Q18 — I-6 mandates `observe` default; shipping
 S13 already enforces. Defaulting to observe is a silent behaviour REGRESSION of
 a landed slice. Operator decision required; do not choose unilaterally.
PRODUCER KILL-CHECK: remove append ⇒ T44/T45 fail
CONSUMER KILL-CHECK: n/a (payload is terminal)
```

```text
CT25: slice_coverage_rule  TYPE:function
PRODUCER: validate_slice_ids (extend)
INPUTS: EvalReport, RunEvidence
OUTPUTS: (EvalReport, warnings, coverage_gap: tuple[str, ...])
INVARIANTS: (1) never UPGRADES a verdict; (2) inert when no plan resolved;
            (3) inert when plan declared zero slices (B-3 warns separately);
            (4) FULL GATE per Q17 — one unreported slice weighs the same as
                all of them, no threshold;
            (5) the halt reason must be textually distinct from an
                evaluator-declared BLOCKED (prompt.py:814 = external obstacle)
KILL-CHECK: delete the coverage branch ⇒ T38 fails
```

## 27.4 Path / matrix inventory

| P# | Trigger | Target behaviour | S# | T# |
|---|---|---|---|---|
| P30 | coder commits its work | diff vs base still shows it | S15a | T31 |
| P31 | coder leaves work uncommitted | unchanged from today | S15a | T31b |
| P32 | untracked-only change | named AND in diff body | S15a | T35b |
| P33 | not a git repo / git absent | block minus diff, run continues | S15a | T17d (exists) |
| P34 | HEAD unresolvable (empty repo) | `base_commit=None`, degrade to `HEAD` semantics + warn | S15a | T31c |
| P35 | plan mutated mid-run | t0 text used; warning emitted | S15b | T33 |
| P36 | plan supplied, 0 slices extracted | warning, run continues | S15b | T34 |
| P37 | secret in tracked diff | masked in task and log | S15c | T30 |
| P38 | 5000 untracked files | block within budget | S15a | T35 |
| P39 | one 9000-line file + one critical file | both represented | S15a | T37 |
| P40 | eval judges 1 of 20 slices | re-ask eval once; still short ⇒ halt for operator | S15d | T38 |
| P44 | eval retry then reports all 20 | run continues normally, no halt | S15d | T52 |
| P45 | judge writes `**S1**: PASS` for every slice | normalised, coverage satisfied, NO false halt | S15d | T51 |
| P41 | repair round 2 | task carries round-1 findings | S15e | T39 |
| P42 | two runs, same task, same second | distinct artifact dirs | S15f | T48 |
| P43 | 3 repair rounds | 3 recoverable eval records | S15f | T49 |

| M# | Matrix row | Coverage |
|---|---|---|
| M20 | `eval_evidence_block=off` | T45 (byte-identical) |
| M21 | `=observe` | T45b (telemetry only) |
| M22 | `=enforce` | T44 |
| M23 | mode linear | T38 |
| M24 | mode adaptive + repairs | T39, T49 |
| M25 | `--plan` absent | T17f (exists) |
| M26 | redactor absent (`None`) | T30b — must not crash |

## 27.5 Implementation slices

Ordered by **blast radius descending**, so each later slice builds on a
verified base. Each is independently shippable and independently revertible.

### S15c — redact the task (SECURITY FIRST)
Traces-to: G11 · CT23 · GAP20. Liveness L0→L3. **Ship first.**
- `cli.py` `_cmd_run`: after the redactor exists (:2244) and before
  `drive_session` (:2408), `args.task = _redact(redactor, args.task)`.
- Placed in `_cmd_run`, **not** the controller: the controller has
  `secrets` (a mapping) but not a constructed `SecretRedactor`, and this seam
  covers operator-typed tasks and future composers too — one chokepoint, not
  one per producer (ADR-12's own argument).
- Failure: `redactor is None` ⇒ identity (M26). Never raises.
- Exit: T30 (masked in task), T30b (None-safe), T30c (masked in events.jsonl).
- Kill-check: remove the call ⇒ T30 fails.

### S15a — evidence from a pinned base, budgeted per file
Traces-to: G9 · CT22 · GAP21/24/25. L2→L3.
- `RunEvidence.base_commit` = `git rev-parse HEAD` at t0 (`check=False`).
- Diff via **temporary index** (verified read-only):
  `GIT_INDEX_FILE=<tmp> git read-tree <base>` → `git add -A -- . ':(exclude).fa'`
  → `git diff --cached <base>`. This captures committed + staged + unstaged +
  untracked in ONE diff, respects `.gitignore`, excludes the harness's own
  run dir, and **mutates nothing** (`git add -N` was rejected: it rewrites the
  coder's real index — proven).
- Per-file budget from `--numstat`: cap each file, then the whole block, so no
  single noisy file can evict another (B-8). Announce every truncation.
- Cap the untracked list (B-4) with `... and N more`.
- Exit: T31, T31b, T31c, T35, T35b, T36, T37. Kill-check: pin to `HEAD` ⇒ T31 fails.

### S15b — freeze the contract
Traces-to: G10 · CT22 · GAP22/23. L0→L3.
- Build `RunEvidence` once in `run_workflow`; `plan_text`/`plan_sha256` read at
  t0. `plan_text()`'s "read once" docstring becomes true, or the method is
  removed in favour of the snapshot.
- Re-hash at eval; digest mismatch ⇒ **warn, use t0 text** (do not fail: the
  plan is advisory, and failing would let a stray editor kill a run).
- `--plan` supplied + zero slices ⇒ structured warning naming the path (B-3).
- Exit: T33, T34. Kill-check: re-read at eval ⇒ T33 fails.

### S15d — enforce coverage  ✅ UNBLOCKED (Q17 = (d) re-ask once, then halt for operator)
Traces-to: CT25 · GAP26/29/30 · Q20. L1→L3.
- **Retry step.** On a non-empty coverage gap, re-run the *eval* stage exactly
  once, appending the missing IDs to the eval task ("you did not report on
  S2, S3 — report on those"). Budget `max_eval_retries = 1`, a module constant,
  NOT an operator flag (a new knob is a new policy choice ⇒ new Q#).
- **Halt step.** If the retry still leaves a gap: terminate for operator
  attention. Do NOT re-run the coder, do NOT escalate to the planner.
  Reason string must name the slices and the attempt count.
- **Full gate** (operator-confirmed): any single unreported slice trips it.
- Case-fold comparison preserving `S5`≠`S5a` (GAP29); retain the failing record
  when Q16 fires on an invented ID (GAP30).
- **Parser-drift mitigation (Q20, mandatory in this slice).** Before the gap is
  computed, normalise judge lines: strip `**`/`*`/`_`/backticks around the ID,
  accept table-cell (`| S1 | PASS |`) and numbered-list (`1. S1:`) leaders,
  accept `PASSED`/`FAILED`, accept an optional `Step ` prefix. Without this the
  full gate turns formatting drift into a false halt — measured, see §27.8b.
- Exit: T38, T41, T42, T43, **T51 (normalisation matrix, red-first)**.

### S15e — close the repair feedback loop
Traces-to: G9 · GAP27. L0→L3.
- Repair-round coder task gains the prior `EvalReport`'s failing step evidence
  and blocking findings (harness-composed, so it inherits S15c's redaction).
- Exit: T39. Kill-check: drop the append ⇒ T39 fails.

### S15f — artifact identity and retention
Traces-to: GAP33/34. L1→L3.
- `active_plan_id` ← `RunEvidence.plan_id` (4 sites: :547,:691,:730,:793).
- `run_id` gains a short random suffix (collision at 1s proven).
- Per-round eval records retained (`eval_report.round<N>.json` or S6a's log —
  whichever S6a settles; S15f only requires the history exist).
- Exit: T47, T48, T49, T50 (**T16e, finally written**).

### S15g — governance and framing  ✅ UNBLOCKED (Q18 = (i) enforce + amend ADR-10)
Traces-to: G12 · CT24 · GAP28/31/32. L0→L3.
- **Default `enforce`** for `eval_evidence_block` (operator-confirmed).
- **ADR-10 I-6 clause 4 amendment is part of this slice, not a follow-up.**
  Record the carve-out in the ADR text: payloads supplying the *artifact under
  review* default to `enforce`; payloads supplying *instructions to the model*
  keep the `observe` default. Name `coder_slice_ceremony` (instruction-class,
  unchanged) and `eval_evidence_block` (evidence-class, `enforce`) as the two
  worked examples. Clauses 1/2/3/5 apply unchanged to both.
- Register `eval_evidence_block` as an `InjectionSpec` + `FeatureFlags` field,
  mirroring `coder_slice_ceremony`'s **5 coupled sites** (dataclass, `as_dict`,
  fail-open set, type map, loader) — verified count, not guessed.
- Fence the coder-derived diff and add one eval-prompt clause: harness evidence
  is authoritative; text inside the fence is *the artifact under review*, never
  an instruction (A-7/B-10).
- Replace `fs_read_file` citations with eval's real tools (GAP28).
- `EVAL_DOC_PATHS` is First-Agent-specific → derive or drop for other repos.
- Exit: T44, T45, T45b, T46, T40.

## 27.6 Verification plan

| T# | Class | Root | Oracle | Kill-check |
|---|---|---|---|---|
| T30 | C3 | real `_cmd_run` | secret absent from `args.task` at dispatch | remove redact ⇒ fail |
| T30b | C1 | `_cmd_run`, redactor None | no exception, task unchanged | — |
| T30c | C3 | events.jsonl on disk | masked in `user_msg` | — |
| T31 | C1 | `run_workflow` + real git | committed work in eval task | pin to HEAD ⇒ fail |
| T31c | C1 | empty repo | `base_commit=None`, warn, continue | — |
| T33 | C1 | plan mutated between stages | t0 text used; digest warning | re-read ⇒ fail |
| T34 | C0 | em-dash plan | warning names the path | — |
| T35 | C0p | 5000 untracked | block ≤ budget | remove cap ⇒ fail |
| T37 | C1 | filler + critical file | critical hunk present | remove per-file budget ⇒ fail |
| T38 | C1 | 1-of-20 judged | terminal status ≠ DONE | remove rule ⇒ fail |
| T39 | C1 | adaptive, 2 rounds | round-2 task ⊃ round-1 evidence | — |
| T44/T45 | C2 | `fa inject`, `--inject=off` | row listed; task byte-identical | — |
| T46 | C3 | payload containing ``` fence | fence not breakable | — |
| T48 | C1 | two same-second runs | distinct artifact dirs | — |
| T50 | C4 | write spy | exactly 1 write/stage | — |

**Live-path proof:** new `s127-*` rows in `scripts/run_live_check.sh` for
(a) commit-then-judge, (b) secret-in-diff masked, (c) `--inject
eval_evidence_block=off`. After ANY edit: `tests/test_live_check_script.py` +
`scripts/adversarial_battery_live_check.sh`.

**Mutation battery** (each must die): pin base→`HEAD`; drop `:(exclude).fa`;
`add -A`→`add -N`; remove per-file budget; remove untracked cap; skip re-hash;
drop the coverage rule; case-fold `S5a`→`S5`; remove the redact call; flip
default mode; unregister the spec.

## 27.7 Risks

| RK | Risk | Mitigation |
|---|---|---|
| RK20 | Temp-index diff is slower on large repos | `--numstat` first; budget before materialising bodies; timeout already enforced |
| RK21 | Base commit wrong under `--resume` | Q19 |
| RK22 | Redacting the task masks a legitimately-similar string | Mask is exact-substring on known secrets only; same tradeoff already accepted for tool output |
| RK23 | Coverage rule turns partial judging into repair storms | Q17 must state the budget interaction |
| RK24 | S15g default-mode choice silently disables shipped behaviour | CLOSED: Q18=(i) `enforce`; ADR-10 amended in-slice |
| RK25 | Full gate + brittle regex ⇒ false halts on formatting drift | S15d normalisation matrix (T51); measured in §27.8b |
| RK26 | Q19 answer assumes a workflow resume path that does not exist | §27.8a; S15a persists the base, resume logic deferred to Q20 |

## 27.8 Open questions — ANSWERED by the operator

All three are closed. Recorded verbatim in intent; implementation notes follow
each.

- **Q17 — ANSWERED: option (d), re-ask the judge, then STOP FOR THE OPERATOR.**
  On detecting unreported slices, re-run the *eval* stage once with the missing
  IDs named in the task. If the second review still leaves slices unreported,
  **halt and surface to the operator** — do NOT escalate to the planner and do
  NOT re-run the coder. Operator's rationale, verbatim in intent: a further
  automated escalation "sounds loopy"; the pair-programmer model is that the
  human interferes at the point of confusion. Deeper automation is explicitly
  deferred to a later iteration.
  - **Sub-question — ANSWERED: full gate.** One unreported slice out of twenty
    is treated exactly like nineteen. No threshold, no proportional rule.
  - Budget: exactly one eval retry (`max_eval_retries = 1`, not operator-tunable
    in this slice — a new knob would be a new policy choice and thus a new Q#).
  - Terminal status on the second failure must be **distinguishable** from an
    evaluator-declared `BLOCKED` (which per `prompt.py:814` means an *external*
    obstacle). Use a distinct reason string, e.g.
    `evaluator did not report on slices S2, S3 after 2 attempts`.
- **Q18 — ANSWERED: option (i), `enforce` + amend ADR-10.** The evidence block
  defaults to `enforce`. Operator's rationale: evidence is important enough to
  be on by default. S15g therefore does BOTH: registers the block as a proper
  `InjectionSpec` with a flag (satisfying I-6 clauses 1, 2, 3, 5) and amends
  ADR-10 I-6 clause 4 to record the carve-out for evidence-class payloads.
  The amendment must state the distinction explicitly: payloads that supply the
  *artifact under review* default to `enforce`; payloads that supply
  *instructions to the model* keep the `observe` default. The existing
  `coder_slice_ceremony` injection is instruction-class and its default is
  unchanged.
- **Q19 — ANSWERED: the original run's starting point.** When a run resumes, the
  diff is measured from the base commit of the *original* run, not the resumed
  session's HEAD. Operator's rationale: both real resume scenarios ("it broke,
  continue" and "here is a correction, continue") are the *same run and the same
  chain of changes*, so the judge's frame of reference must not shift mid-chain.
  - **Implementation consequence:** the base commit must be **persisted** in the
    run artifact at t0 and **re-read** on resume, not recomputed. This upgrades
    Q19 from a defaulting decision to a storage requirement on CT22
    (`run_evidence_snapshot` gains a persist/reload path).
  - **See §27.8a — the premise needs correcting before this can be built.**

## 27.8a Q19 premise correction — `fa workflow` has no `--resume`

Discovered while implementing the operator's answers; verified at `87ea5e2`.

The Q19 question as I originally posed it presupposed that a workflow run can be
resumed. **It cannot.** Evidence, mechanically checked:

- `build_parser()` subcommand inspection: `run` has `--resume`; **`workflow`
  does not**.
- `run_workflow()` has **no `resume` parameter** in its signature
  (`workflow_controller.py`, `def run_workflow`).
- `_cmd_workflow` never reads `args.resume` in its call to `run_workflow`.
- The one `"resume"` key inside the controller (`workflow_controller.py:574`) is
  `"resume": not fresh` — a *per-stage* flag meaning "this is not stage 0, so
  keep the on-disk PR draft so the next role can read the previous role's work
  log". It is intra-run plumbing between stages, not run-level resume.
- `--resume` on `fa run` means, per `cli_help`: "Resume an existing session:
  preserve the on-disk PR draft so the previous role's work log can be read."
  That is *draft preservation*, not restoration of history or of a base commit.

So the operator's stated scenarios — "it broke, continue where we left off" and
"stop, here is a correction, continue" — **are not implemented for workflow runs
today**. The operator flagged exactly this uncertainty ("to be fair I never even
tried resume... no idea, actually") and was correct to.

**Disposition.** The answer to Q19 is recorded and correct *as a requirement for
whenever workflow resume exists*. S15a implements the half that is real now:
pin the base commit at t0 and **persist it in the run artifact** so it is
already durable when resume arrives. No resume-specific branch is written in
S15, because there is no resume path to branch on; writing one would be
unreachable code and untestable at the live path.

**New backlog item (not in S15):** design workflow-level resume, including
whether it restores the pinned base, the plan digest, and the repair/replan
counters. Promoted as **Q20** rather than assumed.

## 27.8b Q20 (NEW, non-blocking) — the eval output contract is regex-scraped

Raised by the operator's design challenge: "there is a notion that then a
developer needs to use regular expressions, something is wrong in design."

The concern is legitimate and is now measured. `_STEP_LINE_RE`
(`workflow_artifacts.py:378`) parses the judge's per-slice verdict lines. Tested
against realistic model formatting:

| Judge output | Parsed? |
|---|---|
| `- S1: PASS - ok` | yes |
| `- S1: PASS — em-dash` | yes |
| `* S2: FAIL: broken` | yes |
| `  - s3: pass - lowercase` | yes |
| `- S5a: PARTIAL - suffix` | yes |
| `- **S1**: PASS - bolded` | **NO** |
| `\| S1 \| PASS \| ok \|` (table) | **NO** |
| `- S1: PASSED - past tense` | **NO** |
| `1. S1: PASS - numbered` | **NO** |
| `- Step S1: PASS` | **NO** |

**This interacts directly with the Q17 full-gate answer.** Demonstrated:

```
plain markdown  parsed=['S1','S2']  unreported=[]
bolded IDs      parsed=[]           unreported=['S1','S2']
markdown table  parsed=[]           unreported=['S1','S2']
```

A judge that reviewed **every slice correctly** but wrote `**S1**` instead of
`S1` is indistinguishable, to the harness, from a judge that reviewed nothing.
Under the full gate that now halts the run for the operator, **formatting drift
becomes a false stop**. This is a real cost of the (d)+full-gate combination and
must be mitigated, not just noted.

**Mitigation shipped inside S15d (cheap, no architecture change):** normalise
the line before matching — strip markdown emphasis (`**`, `*`, `_`, backticks),
accept table-cell and numbered-list leaders, accept `PASSED`/`FAILED`, accept an
optional `Step ` prefix. Each becomes a T-row with a red-first test. This does
not make parsing sound; it removes the failure modes a competent model actually
produces.

**The architectural fix is deliberately NOT in S15.** Options, for a later
slice:

1. **Tool-call contract** — give the eval role a `submit_verdict` tool whose
   JSON schema the provider validates. All three provider adapters already send
   `tools` (`anthropic.py`, `openai_compat.py`, `mistral.py`), so this is
   portable. The judge "answers" by calling the tool; there is no prose to
   parse. This is the standard production answer and is the recommended target.
2. **Provider structured output** (`response_format: json_schema`) — the repo's
   own Mistral adapter documents **100% vs 64% schema conformance** for
   `json_schema` over `json_object` (`providers/mistral.py:22-26`). But
   `response_format` is implemented for **Mistral only** (16 refs) and for no
   other adapter, so choosing this would make the verdict contract
   provider-dependent. Rejected for that reason.
3. Keep regex as a **fallback** behind either of the above, since a model can
   still end its turn with prose instead of a tool call.

Recommendation: **(1) with (3) as fallback**, as its own slice after S15.
Not started; no code in S15 depends on it.

## 27.9 Definition of Done

- [ ] Every GAP20–GAP34 row has a passing `T#` **and** a killed mutant.
- [x] Q17/Q18/Q19 answered by the operator and recorded in §27.8.
- [ ] S15d ships the Q20 normalisation matrix; a bolded/tabled judge report does
      NOT produce a false halt (T51 watched red first).
- [ ] S15g amends ADR-10 I-6 clause 4 in the same commit as the `enforce` default.
- [ ] `fa inject` lists `eval_evidence_block`; `off` yields a byte-identical task.
- [ ] Secret probe: no known secret reaches `args.task` or `events.jsonl`.
- [ ] Commit-then-judge live row passes on the host.
- [ ] Full suite: no regression against a **stash-measured** baseline (not notes).
- [ ] ADR-10 I-6 amended or complied with — no third state.
- [ ] `AUDIT-S12-S13-*.md` findings each marked closed with the `T#` that proves it.
