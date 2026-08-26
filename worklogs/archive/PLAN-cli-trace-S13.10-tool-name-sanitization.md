> **Status:** archived 2026-08-25 — moved from implementation-plans per 30-day rule

# PLAN: S13.10 — Tool-name sanitization (dot → underscore, repo-wide rename)

**Status:** COMPLETE (2026-08-05/06) — every `fs.` / `pr.` tool name migrated to `fs_` / `pr_`;
canonical `TOOL_NAMES` frozenset in `src/fa/inner_loop/tool_names.py` with
`is_valid_wire_name()` gate; registry, hooks, tests, AGENTS.md, and
knowledge docs aligned; all strict-OpenAI providers (NVIDIA/Anthropic) accept
the wire shape. S13 conformance + workflow runs (s13-7-wf3-*) verified live
2026-08-09 without dotted-name 400s.
**Author:** agent, 2026-08-05
**Depth:** P2 (cross-module migration/rollout — reverses a naming decision, touches registry, wire, hooks, tests, docs)
**Parent:** `cli-trace-substrate-rebaseline-2026-07-25.md`
**Skill:** `knowledge/skills/plan-authoring`
**Closes:** the provider-interop blocker found in S13 (NVIDIA/OpenAI/Anthropic reject dotted tool names)

---

## 0. Why this exists (grounded)

FA's tool names use `namespace.name` (`fs_read_file`, `pr_prepare`). The
OpenAI-standard tool-name pattern is `^[a-zA-Z0-9_-]{1,64}$` — **no dots, max 64
chars** — enforced by OpenAI, Anthropic (64-char), NVIDIA, and Gemini (all verified
mid-2026). So any strict OpenAI-compatible provider rejects FA's tool definitions
with a 400 (the live NVIDIA error: `Function at index 0 has an invalid name:
"fs_checkpoint"`). For a harness "aimed to be utilized by any models", the tool-name
schema must be provider-standard.

**Operator decision (2026-08-05): Option A — full repo-wide rename**
`fs_read_file` → `fs_read_file`, etc. (dot → underscore), preserving the `fs_` /
`pr_` namespace prefix for grouping. Cleanest long-term; matches opencode/Hermes.

---

## 1. Preflight — verified facts (all by grep/read, not assumed)

### 1.1 The canonical wire names (16 `ToolSpec.name=` definitions) — MUST change
```
fs_checkpoint  fs_chronicle_search  fs_diff  fs_edit_file  fs_glob  fs_grep
fs_instant_grep  fs_list_tasks  fs_read_file  fs_run_bash  fs_send_ctrl_c
fs_spawn_subagent  fs_undo  fs_usage  fs_write_file  pr_prepare
```
Source: `grep -rhoE 'name="(fs|pr)\.[a-z_]+"' src/fa/inner_loop/tools/*.py` →
16 unique. These are the **wire names** sent to providers and used as the registry
key + returned in `tool_calls` for routing.

### 1.2 Secondary names participating in the scheme (must be mapped consistently)
- **`fs_write_file_limited`** — a real builder key in `profiles.py:216,285`
  (a derived/limited write tool). NOT a standalone ToolSpec.
- **`fs_apply_patch`** — **NOT a registered tool** (no ToolSpec, no module); only
  in `intent_guard.py` logic + docs as a conceptual mutating name. Decision needed
  (§5, Q-1).
- **`fs_read`** — a fixture tool name in `conformance.py:136` (test scenario).
- **`fs_spawn_subagent` / `fs_run_bash`** — referenced in `intent_guard.py:206`
  logic frozenset.

### 1.3 The name is load-bearing in BOTH directions (correctness-critical)
- **Registry key:** `registry.py:145-146` `self._tools[spec.name]`,
  `self._validators[spec.name]`.
- **Response routing:** provider returns `function.name` in `tool_calls` →
  `coder_loop.py:_build_tool_calls` reads `call.name` → `registry.lookup(call.name)`.
- **So the wire name must equal the registry key.** Rename must be **atomic and
  consistent** — a mismatch breaks tool routing silently.

### 1.4 Hard-coded logic frozensets that MUST stay in sync (not just strings)
- `intent_guard.py:115` `_MUTATING_TOOL_NAMES = {"fs_write_file","fs_edit_file","fs_apply_patch"}`
- `intent_guard.py:206` `if call.name not in {"fs_run_bash","fs_spawn_subagent"}`
- `intent_guard.py:128,232` prompt text references `pr_prepare`
- `profiles.py:216,285` `fs_write_file_limited`
- **Name-keyed LOGIC (not prose) — must rename or behavior breaks:**
  - `stats.py:399-403` `if tool_name == "fs_read_file"` etc. (analytics keying)
  - `output.py:219-222` display-name map `{"fs_read_file": "Read", ...}`
  - `state.py:655,659` `if call.name == "fs_read_file"` (read/write tracking)
  - `cli.py`, `hooks/builtin.py`, `loop.py`, `recovery/classify.py`,
    `observability/cost_guardian.py`, `run_bash.py`, `subagent_prompts.py`

### 1.5 Blast radius (grep counts, corrected 2026-08-05 review)
- `src/`: **150** occurrences of dotted tool names, but only **~11 files** contain
  **code logic keyed on the name** (must change): `tools/*.py` (16 ToolSpec defs),
  `intent_guard.py`, `profiles.py`, `state.py`, `stats.py`, `output.py`, `cli.py`,
  `prompt.py`, `subagent_prompts.py`, `hooks/builtin.py`, `loop.py`,
  `recovery/classify.py`, `run_bash.py`, `cost_guardian.py`. The rest (a `-l` grep
  matched ~27 files) are **doc/comment-only** mentions — optional scrub, no code
  change (see S13.10.2).
- `tests/`: **341** references (all renamed in S13.10.3).
- Docs/prompts: many (ADR-6/7/11/12/15, BACKLOG, AGENTS.md, STAGE_*_VERIFICATION,
  architecture.md, etc.).

### 1.6 No single canonical constant exists
The `ToolSpec.name=` in each `tools/*.py` is the source of truth. There is **no**
`ALL_TOOL_NAMES` constant. This is a gap the rename should close (add one) so
future renames/audits are single-source.

---

## 2. Current state → Target state

**AS-IS:** 16 `ToolSpec.name` use dots (`fs_read_file`); provider-strict tools 400;
registry key = dotted name; hooks/test/docs reference dotted names; no single
canonical name constant.

**TO-BE:** all 16 canonical wire names use underscore (`fs_read_file`); registry,
hooks, tests, docs consistent; a canonical `TOOL_NAMES`/name-map exists; provider
requests pass strict tool-name validation; a negative-proof kill-check proves any
dotted name is rejected.

**Non-goals (stop scope creep):**
- Do NOT change the `fs_`/`pr_` namespace prefix scheme (only dot→underscore).
- Do NOT touch the Anthropic `cache_control` or prompt-caching work (separate slice).
- Do NOT rename handlers/functions/classes — only the *wire name* strings and
  anything keyed on them. (Rename the public string, not Python identifiers.)
- Do NOT convert `fs_apply_patch` to a real tool unless Q-1 resolves to "add it".

---

## 3. Contracts

- **CT1 — wire-name standard:** every provider-visible tool `name` matches
  `^[a-zA-Z0-9_-]{1,64}$`. Kill-check: a validator asserts this for every registered
  ToolSpec; a dotted name fails it.
- **CT2 — registry↔wire consistency:** `registry.lookup(wire_name)` resolves; the
  name returned by a provider in `tool_calls` equals the registry key. Kill-check:
  a tool-call with the *old* dotted name fails lookup with the "not registered"
  error (proving the rename took effect on routing).
- **CT3 — logic-set consistency:** `intent_guard` mutating/run-bash/spawn sets
  reference the NEW names. Kill-check: forcing the OLD name in `_MUTATING_TOOL_NAMES`
  breaks a mutating-tool guard test.
- **CT4 — two-sided:** the name is defined (producer: `ToolSpec.name`) and consumed
  (consumer: `registry.lookup`, hooks, **model-facing prompt text**, tests). Both
  sides updated.
- **CT5 — single source of truth (new):** a canonical name map/constant exists; a
  test asserts every `ToolSpec.name` is a member and no dotted name remains in
  `src/`.
- **CT6 — prompt↔wire atomicity (new, G2):** every tool-name reference in the
  **model-facing system prompts** (`prompt.py`, `subagent_prompts.py`) matches a
  registered `ToolSpec.name` and vice-versa. Kill-check: a prompt naming
  `fs_read_file` while the registry only has `fs_read_file` fails a
  prompt-registry consistency test (prevents instructing the model to call a
  nonexistent tool).

---

## 4. Steps — CLOSED CORE (must land, atomic rename)

### S13.10.0 — Canonical name map (no behavior change)
Add a single source of truth: a module (e.g. `fa/inner_loop/tool_names.py`) with
the old→new mapping and a `TOOL_NAMES` frozenset of new names.
- DoD: constant exists; a test asserts every dotted name in `tools/*.py` has a
  mapping and the target matches `^[a-zA-Z0-9_-]+$`. Class C0p.
- Kill-check: remove a mapping → the test fails.

### S13.10.1 — Rename the 16 `ToolSpec.name=` definitions (the wire names)
Change each `name="fs.x"` → `name="fs_x"` in the 16 tool modules (+ `pr_prepare` →
`pr_prepare`). This is the ONLY step that changes the wire contract.
- DoD: `grep -rhoE 'name="(fs|pr)\.[a-z_]+"' src/` returns **zero**; every ToolSpec
  name matches underscore. Class C1.
- Kill-check: revert one → a registry/wire test fails.

### S13.10.2 — Fix registry-key / logic references in `src/`

**CRITICAL — atomicity (G2).** Tool names are embedded in **model-facing system
prompts** (`prompt.py:521-574`, `subagent_prompts.py:18-25`) that the model reads
and echoes back as `tool_calls`. The **prompt text and the registered tool name
MUST change in the SAME commit**, atomically. If they drift (prompt says
`fs_read_file`, registry has `fs_read_file`), the model is instructed to call a
tool that no longer exists → silent routing failure. This is the highest-risk
coupling in the slice.

**MUST change (code logic keyed on the name):**
- `intent_guard.py:115,206` frozensets + prompt strings
- `profiles.py:216,285` (`fs_write_file_limited` → `fs_write_file_limited`)
- `state.py:655,659` (read/write tracking)
- `stats.py:399-403` (analytics keying)
- `output.py:219-222` (display-name map)
- `cli.py:1061-1068` (ToolCall construction)
- `prompt.py` + `subagent_prompts.py` (system-prompt text — atomic with S13.10.1)
- `hooks/builtin.py`, `loop.py`, `recovery/classify.py`, `run_bash.py`,
  `cost_guardian.py` (verified: code logic where present)

**Do NOT touch (doc/comment-only, optional scrub in S13.10.4):**
`pr_draft.py`, `runtime_limits.py`, `context.py`, `hooks/blockers.py`,
`secret_store.py`, `pty_pool.py`, `sandbox/classifier.py`,
`sandbox/secret_paths.py`, `authoring_rules/tests.py` — these mention the names
only in docstrings/comments (verified); no code change.

**Also change:** `conformance.py` fixture `fs_read` → `fs_read`.

- DoD: `grep -rn '"fs\.\|"pr\.' src/` returns **zero** (no dotted-name string
  literal in src code); `grep -c 'fs\.[a-z_]+'` in `prompt.py`/`subagent_prompts.py`
  returns zero (prompt text renamed atomically with the registry). Class C1.
- Kill-check: leave one old name in a frozenset OR one old name in prompt text →
  CT3 test (and a prompt-model coupling check) fails.

### S13.10.3 — Update tests (341 refs)
Update all test references to the new names. **Do NOT weaken assertions** — a test
that asserts a dotted name must now assert the underscore name (proving the rename
propagated).
- DoD: `grep -rn '"fs\.\|"pr\.' tests/` returns zero (excluding intentional
  negative fixtures). Full suite green. Class C1.
- Kill-check: a test asserting the old dotted name fails (proving it was updated).

### S13.10.4 — Docs & prompts
Update ADRs, BACKLOG, AGENTS.md, architecture, verification docs, templates.
- DoD: `grep -rlE 'fs\.read_file|fs\.write_file|fs\.checkpoint|pr\.prepare'
  --include="*.md" --include="*.yaml"` returns zero (excluding historical ADR
  records of the old convention, which may note "formerly fs_read_file").
  Class C0p.
- **Explicitly EXCLUDE (intentional, do NOT rename):**
  - `tests/fixtures/i50_resumed_assistant_last.json` — the S13 I-50 historical
    repro; must keep the original dotted names to preserve provenance.
  - `knowledge/trace/codebase_map.json` — a generated artifact (rebuilt by `fa`
    tooling), not a source of truth; regenerate, don't hand-edit.

### S13.10.5 — Add a registry-name invariant test (CT5 ratchet)
A test that (a) every registered ToolSpec name matches `^[a-zA-Z0-9_-]{1,64}$`
and (b) no dotted name exists in `src/` — so a future dotted-name reintroduction
fails CI.
- DoD: new test; full suite green. Class C0p + C1. Kill-check: reintroduce a
  dotted name → the invariant test fails.

---

## 5. Open questions — RESOLVED (2026-08-05, operator)

**Q-1 — `fs_apply_patch`:** RESOLVED — rename in prose/reference only (to
`fs_apply_patch`). It is NOT a real tool (no ToolSpec, no module); do NOT create
one. Update `intent_guard.py` frozenset + docstrings accordingly.

**Q-2 — namespace prefix `fs_` / `pr_`:** RESOLVED — KEEP the prefix. Target
`fs_read_file`, `pr_prepare`, etc. (dot → underscore, prefix preserved).

**Q-3 — historical docs:** RESOLVED — scrubbed clean (no "formerly" annotation).
Keep the naming-convention ADR accurate to the new names.

**Q-4 — on-disk artifacts / session DBs:** RESOLVED — keep as is. Historical
`tool_name` rows carry old names (inert audit data); no migration. New runs record
new names.

---
## 6. Kill-checks (anti-theater, each verified with real output)

| # | force | expected |
|---|---|---|
| K1 | a dotted name reintroduced | CT5 invariant test fails; provider wire-name validator fails |
| K2 | revert one `ToolSpec.name` | registry/routing test fails (old name can't be looked up) |
| K3 | leave old name in `_MUTATING_TOOL_NAMES` | CT3 guard test fails |
| K4 | a test still asserts a dotted name | that test fails (proving it was updated) |
| K5 | full suite | green; coverage ≥ baseline |

---

## 7. Risks

| # | risk | mitigation |
|---|---|---|
| R1 | **silent tool-routing break** (wire name ≠ registry key) | CT2 + K2: a tool-call with the new name must route; old name must fail lookup |
| R2 | **missed logic frozenset** (intent_guard, profiles) breaks a guard | CT3 + K3 + full suite |
| R3 | docs drift (old name in prose) | CT5 grep + S13.10.4 scrub |
| R4 | rename is a big diff, review burden | one atomic slice; definition-driven, not blind sed; canonical map first (S13.10.0) |
| R5 | **prompt↔wire drift** — model instructed to call `fs_read_file` while registry has `fs_read_file` (silent routing failure) | CT6 + atomic S13.10.1+S13.10.2 in one commit; prompt-registry consistency test |

---

## 8. Definition of Done

**Closed core (blocking):**
- [ ] S13.10.0 canonical map exists (CT5)
- [ ] S13.10.1–S13.10.2: zero dotted names in `src/` (CT1)
- [ ] S13.10.2: registry + intent_guard + profiles + **model-facing prompts** reference
      new names (CT2/CT3/CT6 — prompt↔wire atomicity)
- [ ] S13.10.3: tests updated (no dotted-name assertions), full suite green, coverage ≥ baseline
- [ ] S13.10.4: docs scrubbed (with "formerly" note per Q-3); fixture + generated map excluded
- [ ] S13.10.5: registry-name invariant test present + green (CT5 ratchet) + prompt-registry
      consistency test (CT6)
- [ ] K1–K5 executed with real output
- [ ] Zero `noqa`; ruff/mypy/pyrefly clean
- [ ] **Live (verification not gate):** `fa workflow planner,coder,eval` on NVIDIA
      no longer 400s on tool names (needs deployed box)

**Open (reported):** none beyond Q-1..Q-4 resolution.

---

## 9. DoD (condensed)

STATE: all 16 wire names + secondary names renamed dot→underscore, atomically;
registry/hooks/tests/docs consistent; a canonical name map + CT5 invariant test
prevent regression. ARTIFACTS: new `tool_names.py`, updated tool modules, hooks,
profiles, tests, docs, `PLAN-cli-trace-S13.10-*`. CONTRACTS: CT1–CT5 all verified.

## 10. Anti-theater + READY gate
- [x] Preflight by grep (16 canonical + 3 secondary names, ~11 code-logic files, 341 test refs, logic frozensets, prompt-text coupling)
- [x] No unverified file:symbol references (all grounded)
- [x] Kill-checks K1–K5 defined, producer-targeted
- [x] Q-1..Q-4 resolved by operator (2026-08-05)
- [x] READY
