# PLAN — two-mode thinking toggle (`--thinking_mode`) with sampling unlock

**Slice:** S13.x (extends S13 message/sampling normalization work).
**Status:** READY for review.
**Author date:** 2026-08-06.
**Goal:** a global, on-the-fly two-mode switch (thinking on / no-thinking) that is as
simple and robust as possible, is CLI-accessible today, and maps to a webui
button/checkbox later. In **thinking** mode (default) sampling knobs are not sent;
in **no-thinking** mode the operator's declared off-signal is sent and
`sampling.temperature/top_p` are unlocked.

---

## 0. Decisions locked with the operator

- **Flag:** `--thinking_mode {thinking,no-thinking}`, default **`thinking`** (explicit, verbose).
- **Default:** thinking mode. `fa run "hello"` keeps every default including `--thinking_mode thinking`.
- **Scope:** **global** (whole invocation — all roles under one mode). Simplest robust.
- **No in-flight stripping / no per-model capability matrix.** (This is what broke LiteLLM —
  see issues #27351/#26444/#21911 in the 2026 research.) Instead: the operator declares the
  exact wire bytes for each mode in config; FA only *selects* which block to send and whether
  sampling applies. Reliability comes from the operator pasting provider-verified bytes, not
  from FA guessing a registry.

---

## 1. Current behaviour (source-verified)

- `RequestInfo` (src/fa/providers/base.py:38-55): `temperature: float | None = None`,
  `top_p: float | None = None`, `extras: Mapping` — no concept of a reasoning mode.
- `drive_session` (src/fa/inner_loop/coder_loop.py:301) takes `temperature: float = DEFAULT_TEMPERATURE`
  (0.0) and builds `RequestInfo(... temperature=..., extras=dict(request_extras))` at coder_loop.py:1209.
- `_cmd_run` (src/fa/cli.py:2437) sets `session_temperature = DEFAULT_CODER_TEMPERATURE if coder else DEFAULT_TEMPERATURE`
  (cli.py:2546) and passes it to `drive_session(... temperature=session_temperature)` (cli.py:2639).
- `ProviderChain.request()` (src/fa/providers/chain.py:299) resolves
  `effective_temperature/top_p` from `request` → role `sampling:` (chain.py:331-333), merges each
  entry's `provider_params` into `extras` (chain.py:353), then runs the S13.4 conformance finalizer
  `validate_and_normalize` (chain.py:368) before the wire.
- `ChainEntry` (src/fa/providers/chain.py:89-121): fields incl. `provider_params: Mapping` (sent to
  that entry only). Entries parsed in chain.py:560-585.
- Reasoning today is static config in `provider_params` (e.g. NVIDIA deepseek:
  `provider_params: {chat_template_kwargs: {thinking: true, reasoning_effort: high}}`).
- Workflow `_run_stage` builds `stage_kwargs` dict (cli.py:1308-1329) and calls `_cmd_run(stage_args,...)`
  (cli.py:1335), so a field added there threads to every role automatically.

---

## 2. Contract / gap IDs

- **GAP-TM-1:** `RequestInfo` has no reasoning-mode field → the chokepoint cannot branch on mode.
- **GAP-TM-2:** FA *forces* `temperature` (0.2/0.0) for every role, even reasoning models where it is
  inert (DeepSeek thinking) or **rejected 400** (OpenAI GPT-5.x/5.6). See research brief
  `research-temperature-topsampling.md` §4 and `research-simple-thinking-lane.md`.
- **GAP-TM-3:** no on-the-fly switch; mode is baked into config/CLI defaults only.
- **GAP-TM-4:** no per-entry block for the no-thinking off-signal; a toggle can't reliably express
  "turn reasoning off" without operator-supplied wire bytes.

**Non-goals (keep out):** no in-flight param-stripping registry; no per-model `MessageRules`
matrix expansion; no new `MessageRules` flags. The design intentionally uses **operator-declared
config blocks** + a **request-mode field** + one gating decision at the existing chokepoint.

---

## 3. Design (simplest robust)

**A. One request-level mode field.**
`RequestInfo` gains `thinking_mode: Literal["thinking","no-thinking"] = "thinking"`. It travels with
every request through the single `chain.py:299` chokepoint. Default `thinking` = backward compatible.

**B. One per-entry optional off-block (operator-declared, reliable).**
`ChainEntry` gains `provider_params_no_thinking: Mapping = {}`. Existing `provider_params` stays the
thinking/base block (merged always, backward compatible). In no-thinking mode the
`provider_params_no_thinking` block is merged **on top** so its keys override the base (operator puts
the exact off-signal bytes there, e.g. `chat_template_kwargs: {thinking: false}` for NVIDIA/DeepSeek,
`reasoning_effort: none` for OpenAI).

**C. One gating decision at the chokepoint.**
In `ProviderChain.request()` per entry:
- resolve `effective_temperature/top_p` as today (chain.py:331-333);
- **thinking** mode → force `temperature=None`, `top_p=None` (do **not** send sampling knobs);
- **no-thinking** mode → keep `temperature/top_p` (from `sampling:`/request) and merge
  `provider_params_no_thinking` on top of `provider_params` into `extras`.

**D. One global CLI flag, threaded globally.**
Add `--thinking_mode` to `run` and `workflow` parsers. `_cmd_run` reads `args.thinking_mode`
(default `thinking`) → `drive_session(thinking_mode=...)` → `RequestInfo(thinking_mode=...)`.
`_run_stage` adds `"thinking_mode": ctx.args.thinking_mode` to `stage_kwargs` (cli.py:1308) so the
workflow threads it to every role.

**E. Warn, don't silently mislead.**
If no-thinking mode is requested but an entry has **no** `provider_params_no_thinking` block, emit a
clear warning (that provider's "off" can't be guaranteed) rather than silently sending sampling that
may be ignored/rejected. This is the anti-surprise guard; it is a warning, not a hard fail, because
some models cannot disable reasoning at all (gpt-oss, Grok 3-mini/4.5, deepseek-r1) and the operator
may be knowingly testing.

---

## 4. Files allowed to edit

- `src/fa/providers/base.py` — `RequestInfo.thinking_mode` field.
- `src/fa/providers/chain.py` — `ChainEntry.provider_params_no_thinking`; parse it in the entries
  builder (chain.py:560-585); gating in `request()`.
- `src/fa/inner_loop/coder_loop.py` — `drive_session(thinking_mode=...)` → `RequestInfo`.
- `src/fa/cli.py` — `run`/`workflow` parser flag; `_cmd_run` read + pass; `_run_stage` stage_kwargs.
- `src/fa/cli_help.py` — `COMMANDS` entries for the new arg (`run` + `workflow`).
- `src/fa/providers/examples/models-*.yaml` — document the new block + flag (docs only).
- `tests/` — new test file `tests/test_thinking_mode_toggle.py`.
- `knowledge/adr/ADR-9-*.md` — short amendment note (docs).
- This PLAN file.

**Not touched:** `message_rules.py`, `registry.py`, `conformance.py`, `live_runner.py`,
`prompt_composer.py` — no capability matrix, no stripping logic.

---

## 5. Edit list (per-edit: intent / current→target / mechanism / rationale / failure / DoD / tests)

### E1 — `RequestInfo.thinking_mode` field
- **Intent:** give every request a mode the chokepoint can branch on.
- **Current→target:** add `thinking_mode: Literal["thinking","no-thinking"] = "thinking"` to the
  frozen dataclass (base.py:38-55). Default keeps all existing callers (probe, conformance,
  compaction) on thinking mode unchanged.
- **Mechanism:** dataclass field with `field(default="thinking")`. Literal type for mypy.
- **Rationale:** single request-level carrier; no new call signatures elsewhere.
- **Failure:** type error if a caller passes a non-`Literal` value — mypy catches.
- **DoD:** field present, default `"thinking"`, mypy clean.
- **Tests:** construct `RequestInfo()` with no arg → `.thinking_mode == "thinking"`; with
  `thinking_mode="no-thinking"` → preserved (C0p).

### E2 — `ChainEntry.provider_params_no_thinking` + parse
- **Intent:** operator-declared off-signal, per entry, merged only in no-thinking mode.
- **Current→target:** add `provider_params_no_thinking: Mapping[str, Any] = field(default_factory=dict)`
  to `ChainEntry` (chain.py:89-121); parse `dict(row.get("provider_params_no_thinking") or {})` in the
  entries builder (chain.py:560-585).
- **Mechanism:** same pattern as existing `provider_params` parse.
- **Rationale:** reliability = operator supplies verified bytes; FA only selects.
- **Failure:** absent → `{}` → E5 warning path; no crash.
- **DoD:** field parsed from YAML; missing key → empty dict; mypy clean.
- **Tests:** `ChainConfig` built from a YAML dict with `provider_params_no_thinking` → value present;
  without → `{}` (C1). Loader accepts the new key (C1).

### E3 — chokepoint gating in `ProviderChain.request()`
- **Intent:** make the mode decide what reaches the wire.
- **Current→target:** after computing `effective_temperature/top_p` (chain.py:331-333) and
  `entry_extras` (chain.py:353), branch on `request.thinking_mode`:
  - `thinking` → `effective_temperature = None`, `effective_top_p = None`;
  - `no-thinking` → merge `entry.provider_params_no_thinking` into `entry_extras` (after
    `entry_extras.update(entry.provider_params)`), keep temp/top_p, and if the entry has no
    `provider_params_no_thinking`, append a warning to the caller-visible warning channel.
- **Mechanism:** local variables + `replace(request, ...)` already used at chain.py:357; warn via a
  per-request `warnings` list or `logger.warning`.
- **Rationale:** single chokepoint (already the conformance finalizer site) = one place to get right.
- **Failure:** a bad mode value → validate_and_normalize still runs; mode is typed so unreachable.
- **DoD:** thinking mode sends no `temperature`/`top_p`; no-thinking sends them + off block.
- **Tests (C1 wire-body, kill-check):**
  - thinking mode → `RequestInfo` produced by chain has `temperature is None and top_p is None`
    (via a fake transport capturing the wire body — no `temperature`/`top_p` keys).
  - no-thinking + `provider_params_no_thinking` → wire body has the off block **and** the
    `sampling` temp/top_p values.
  - no-thinking + empty off block → a warning is emitted (kill-check: assert warning present).

### E4 — `drive_session(thinking_mode=...)` → `RequestInfo`
- **Intent:** carry the mode into the request object.
- **Current→target:** add `thinking_mode: str = "thinking"` kwarg to `drive_session`
  (coder_loop.py:301); pass `thinking_mode=thinking_mode` into `RequestInfo(...)` (coder_loop.py:1209).
- **Mechanism:** signature kwarg + field pass-through.
- **Failure:** default keeps existing tests calling `drive_session` unchanged.
- **DoD:** mode reaches `RequestInfo`.
- **Tests:** `drive_session(..., thinking_mode="no-thinking")` (with a stub chain) → resulting
  `RequestInfo.thinking_mode == "no-thinking"` (C1).

### E5 — CLI flag + global threading
- **Intent:** on-the-fly toggle, global across roles.
- **Current→target:** add `--thinking_mode` with `choices=("thinking","no-thinking")`, default
  `"thinking"`, to `run_parser` (cli.py:446+) and `workflow_parser` (cli.py:539+); `_cmd_run`
  reads `args.thinking_mode` and passes to `drive_session(... thinking_mode=args.thinking_mode)`
  (cli.py:2639); `_run_stage` adds `"thinking_mode": getattr(ctx.args, "thinking_mode", "thinking")`
  to `stage_kwargs` (cli.py:1308-1329).
- **Rationale:** workflow already routes every role through `_cmd_run` via `stage_kwargs`, so one
  field there = global.
- **Failure:** missing attribute on legacy direct-Namespace tests → `getattr(..., default)` guard.
- **DoD:** `fa run --thinking_mode no-thinking ...` and `fa workflow --thinking_mode no-thinking ...`
  parse; default is thinking.
- **Tests (C2):** `build_parser()` has the flag with both choices + default; workflow stage_kwargs
  forwards the mode (mock `_cmd_run` and assert it's called with `thinking_mode`).

### E6 — docs: cli_help + example yaml + ADR note
- **Intent:** operators can discover the flag and the config block.
- **DoD:** `fa help run` / `fa help workflow` mention `--thinking_mode`; models yaml example shows
  `provider_params_no_thinking`; ADR-9 amendment notes the two-mode contract.

---

## 6. Kill-checks (must fail if the design is removed)

1. **Thinking mode must not send sampling knobs** — a fake-transport C1 test asserting the wire body
   has no `temperature`/`top_p` when `thinking_mode="thinking"`. Removing E3's drop → fails.
2. **No-thinking unlocks sampling + off block** — C1 test asserting wire has both the off block and
   `sampling` temp/top_p. Removing the merge or the keep → fails.
3. **Warn on missing off-block** — test asserts a warning when no-thinking with empty
   `provider_params_no_thinking`. Removing the guard → fails.
4. **Flag default is thinking** — parser test asserting `default="thinking"`. Changing default → fails.
5. **Global threading** — workflow test asserting `_cmd_run` receives `thinking_mode` for each role.

**Negative proof / anti-theater:** each test targets PRODUCTION behaviour (wire body via the real
chain chokepoint), not a mock of the feature. No test asserts "no exception" alone; each asserts an
observable wire/config/CLI outcome.

---

## 7. Tests to write (tests-writing skill classes)

- `tests/test_thinking_mode_toggle.py`:
  - C0p: `RequestInfo.thinking_mode` default + preservation; `ChainEntry` parse present/absent.
  - C1: wire-body via real `ProviderChain.request` + fake transport — thinking strips temp/top_p;
    no-thinking adds off block + sampling values; no-thinking empty off block warns.
  - C1: `drive_session` passes mode to `RequestInfo`.
  - C2: parser flag shape/default; workflow `stage_kwargs` forwards mode.
  - Kill-checks §6.

---

## 8. DoD (falsifiable)

- `just check` green (incl. ruff, mypy, full suite, cli-coverage-floor).
- Wire body verified by tests for both modes.
- `fa run "hello"` behaves as thinking mode (no temp/top_p sent) with no config change.
- `fa run --thinking_mode no-thinking "hello"` unlocks `sampling` and sends the off block when
  declared; warns when not.
- `fa workflow --thinking_mode no-thinking ...` applies the mode to every role (verified by test).
- No changes to `message_rules.py` / `registry.py` (no capability matrix added).

---

## 9. READY gate / risks

- **Compatibility:** default thinking + `getattr` guards keep all existing tests and direct-Namespace
  callers green. Re-run full suite; update `check_cli_coverage_floor.py` only if the new CLI branch
  drops `_cmd_run`/`_cmd_workflow` coverage below floor (verify, don't assume).
- **Known model limits (documented, not solved here):** gpt-oss / Grok 3-mini / Grok 4.5 / deepseek-r1
  cannot truly disable reasoning; the operator-declared off-block is best-effort there and FA warns.
- **Webui:** the same `thinking_mode` value becomes a checkbox/dropdown later; core unchanged.
