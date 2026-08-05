# PLAN: S13 — multi-provider conformance (open-scope)

**Status:** DRAFT — awaiting review
**Author:** agent, 2026-08-03 (v2, restructured after operator scope decision)
**Parent:** `cli-trace-substrate-rebaseline-2026-07-25.md`
**Closes:** **I-50 (P1)**, **I-52 (P2)**, **I-51 (P2)**. Unblocks S11.7 / Q35b.
**Ceremony:** lean
**Supersedes:** `PLAN-cli-trace-S13-message-normalization.md` (v1, narrow scope)

---

## 0. Scope decision and what changed

The operator answered the two open questions and widened the slice:

- **Q59 → fix FA's own composition bug first**, then build on that.
- **Q60 → fix the history rebuild** (I-52), not defer it.
- **New goal:** exercise **providers that do not exist in the config today** —
  no adapter, no registry entry, no `models.yaml` mention.

That makes S13 **open-scope by design**. This plan therefore splits into a
**closed core** (S13.0–S13.4, fully specified, fixed DoD) and an **open
exploration** (S13.5+, bounded by a protocol rather than a list). The core must
land and stay green regardless of how the exploration goes.

**Why this ordering is not negotiable:** every new provider is a new source of
truth about our request shape. Onboarding providers *before* the composition
bug is fixed means each one reports the same known defect and we learn nothing
new. Fix the emitter, then let new providers tell us what else is wrong.

---

## 1. Preflight — source-verified

### 1.1 Two defects, one emitter

| # | site | defect |
|---|---|---|
| I-50 | `prompt_composer.py:123-125` | task appended as `user`, **then** `observations` — a resumed session ends on `assistant` |
| I-52 | `coder_loop.py:450-490` | rebuild maps only `model_msg`→`assistant`, `tool_result`→`tool`; **`user_msg` rows are never replayed** |

They are the same emitter seen twice: FA's history reconstruction is neither
**faithful** (I-52) nor **ordered** (I-50). Fixing only ordering would make an
invalid request valid while leaving the model without the instruction its
inherited turns were answering.

### 1.2 The chokepoint is genuinely single

`grep` across `src/`: exactly one call site reaches a provider —
`chain.py:368 provider.request(...)`. No module outside `chain.py` constructs a
provider. Any conformance pass placed there is unbypassable.

### 1.3 Adding a provider is already nearly free

`registry.py:40-58` maps **18 provider names** onto **4 adapters**; 14 already
share `_OPENAI_COMPAT`. So a new OpenAI-compatible provider is *one line* today.

**But that is exactly the trap.** Groq, Cerebras, NVIDIA NIM and OpenRouter are
all "OpenAI-compatible" and all diverge in practice — the S11 evidence shows
Mistral rejecting orderings OpenAI accepts. A registry entry claims
compatibility; only a conformance run proves it.

### 1.4 Eval independence: blocking → adversarial (operator decision, 2026-08-03)

**Today (source-verified).** `roles.py:186 check_eval_disjoint` **raises**
`EvalFamilyConflictError` when the eval family equals planner's or coder's. It
is called from `config.py:316-321`, guarded by
`if _FAMILY_DISJOINT_ROLES.issubset(roles.keys())` — so it fires only when all
three roles are declared. `EvalFamilyConflictError` is caught in **four**
`cli.py` sites (2039, 2651, 2833, 2901) and surfaces as **exit 2**.

**Operator decision: change from blocking to adversarial.** Same-family eval is
no longer a configuration error. It becomes a **recorded risk** plus an
**adversarial posture on the eval role itself**.

**Why this is the better design, not merely a relaxation.** The blocking rule
enforced a *proxy* for the real goal. ADR-2's evidence is about **error
correlation** (~+0.6 same-family vs ~−0.05 cross-family) — the family string was
a cheap stand-in for independence. Three problems with the proxy:

1. **It is trivially satisfiable without being satisfied.** The live deployment
   runs `mistral-small-2603` in all three roles and passes the gate, because the
   YAML says `family: "mistral"` for coder and `family: "mistral_eval"` for eval.
   The gate is green; the independence is fictional. **A gate that a string edit
   defeats is not protecting anything.**
2. **It blocks the free-tier reality.** Groq, Cerebras and NVIDIA NIM serve
   largely the *same open-weight families* (Llama, Qwen, DeepSeek). Requiring a
   disjoint family can make a legitimate multi-provider setup unloadable — the
   config fails to parse rather than warning.
3. **It punishes honesty.** An operator who labels families accurately is
   blocked; one who fudges the string is not.

**Adversarial replacement — two mechanisms, both required:**

- **Declared risk, not refusal.** Same-family eval loads with a
  `ModelsConfig.warnings` entry (the soft channel already exists,
  `config.py:176`) and a `config_warning` event (already wired,
  `state.py:390-399`). The operator is told the ensemble-error correlation they
  are accepting, with the ADR-2 figures, and the run proceeds.
- **Adversarial eval stance.** When the eval family is *not* disjoint, the eval
  role is instructed to actively seek disconfirming evidence rather than
  ratify. Correlated priors are countered by an opposing objective instead of a
  config error. Cross-family eval keeps today's neutral stance.

**What must NOT be lost.** The correlation risk is real and measured — this is a
change of *mechanism*, not a claim the risk is gone. Three guards:

- the warning must be **impossible to miss** (structured event + stderr, not a
  buried log line);
- the eval verdict must **record which stance produced it**, so a `DONE` from a
  same-family adversarial eval is distinguishable in `eval_report.json` from a
  `DONE` by a disjoint neutral eval;
- ADR-2 must be **amended, not contradicted** — the amendment records the
  decision and its rationale.

**Consequence for this slice.** Removing the hard gate is what makes the S13.7+
matrix runnable at all: three providers over the same open-weight families can
now be exercised. It also removes a false-confidence signal — a green gate that
a `family:` string satisfies.

### 1.5 Free tiers with tool calling (researched 2026-08-03)

Candidates that are OpenAI-compatible, need no card, and support tool use:

| provider | free limit | tool calling | notes |
|---|---|---|---|
| **Groq** | 30 RPM, ~14.4k RPD | yes | LPU, sub-second; Llama/Qwen/Kimi/GPT-OSS |
| **Cerebras** | 30 RPM, 1M TPD | yes | Qwen3, Llama 3.3 70B |
| **NVIDIA NIM** | ~40 RPM, 1k credits | yes | 120+ open-weight incl. DeepSeek, GLM, Qwen |
| **OpenRouter** | 20 RPM, ~50–200 RPD | model-dependent | already in the registry |
| **Google AI Studio** | 15 RPM, 1.5k RPD | yes | **not** OpenAI-shaped — real adapter work |
| **Z.AI (GLM)** | 1 concurrent | yes | `glm` family already named in `config.py` |

Groq, Cerebras and NVIDIA NIM are already **registry names** but have never been
exercised. Gemini is the genuinely new *adapter* and is the honest test of "how
hard is a new provider".

**Rate limits are a first-class design input, not a footnote.** At 30 RPM a
three-role workflow with 6 turns per role is ~18 requests — one run is fine, a
matrix of 6 providers × 3 roles is not. S13.6 addresses this explicitly.

---

## 2. Design

### D1 — Fix the emitter, then conform at the boundary

Two layers, deliberately separate:

1. **Composition** (`prompt_composer.py`, `coder_loop.py`) — produce a
   *correct, faithful, provider-neutral* message list. Fixes I-50 + I-52 at
   source.
2. **Conformance** (`chain.py:368`) — enforce per-adapter rules on the way out,
   for divergences FA cannot know about centrally.

Layer 1 is the fix. Layer 2 is the **safety net and the discovery instrument** —
it is what will catch the *next* provider's quirk without a live outage.

### D2 — Capability records, never provider-name branching

`MessageRules` attached to `ProviderSpec`. Adding a provider = one line; adding a
*quirk* = one field. Same lesson as S12's probes: describe the capability, not
the platform.

### D3 — Repair by reordering FA's own content

Never inject invented assistant text (LibreChat's `"Understood."`). Zero added
tokens, and task-after-context is semantically more correct.

### D4 — A conformance suite, not a provider list

The open half is specified as a **protocol** any provider must pass, so adding
provider N+1 needs no plan edit:

```
CONF-1  minimal completion            (200, non-empty)
CONF-2  single tool call round-trip   (tool_calls -> tool result -> answer)
CONF-3  resumed transcript            (the I-50 shape: history then new task)
CONF-4  multi-turn tool chain         (2+ sequential calls)
CONF-5  trailing-assistant tolerance  (records the capability, does not require it)
CONF-6  user-after-tool tolerance     (Mistral 3230's other half)
CONF-7  prompt-cache + composition   (hit rate AND per-component request
                                       sizes; recorded, never pass/fail)
CONF-8  DEPLOYED sampling profile     (the role's real temperature/top_p/
                                       provider_params, not defaults)  <- I-48
CONF-9  oversized / truncation        (behaviour at the context limit)
```

**CONF-8 exists because of a measured near-miss.** I-48 is a live 400 from
`mistral-medium-2604`: *"top_p must be 1 when using greedy sampling"*. It needs
`temperature=0.0` **and** the model's server-side `top_p` default **and**
`provider_params: {reasoning_effort: "high"}` acting together. CONF-1's "minimal
completion" uses default sampling, so **the matrix as first written would have
marked that model green on CONF-1…7 while it remains unusable in production.**

A conformance suite that does not exercise the configuration the deployment
actually runs proves nothing about the deployment — the same error as S8's
scripted transport accepting any message order. CONF-8 therefore replays each
role's **real `models.yaml` entry**, including `provider_params`.

Output is a **capability matrix**, not a pass/fail verdict. A provider that
fails CONF-5 is not broken — it has a rule, and the rule goes in its
`MessageRules`.

### D5a — Harness discipline: the instrument is the likeliest defect

**S13 builds a new measuring instrument, and S11 just demonstrated what that
costs.** Of the ~26 defects S11 surfaced, **six were the instruments, not the
product**: R10 (gawk `strtonum` silently printed 0), R21 (`hits[:10]` truncated
away the strays the check existed to find), R23 (wrong `--output` flag made a
contract check pass on an argparse error), R24 (`pgrep "fa run"` matched its own
wrapper), R25 (`(expected )` — an empty comparand that could not fail), and the
8a `SID` guard (an empty variable fabricated an empty database).

**Every one produced confident, well-formed, wrong output.** None crashed. A
conformance matrix has exactly this shape — it prints a grid of green cells —
so three rules are binding on S13's harness:

1. **Every CONF case carries a positive control.** A case that cannot
   distinguish "passed" from "never ran" is not admitted. CONF-1 must assert a
   non-empty completion, not merely a 200.
2. **Every CONF case must be shown to FAIL before it is trusted.** S13.1 already
   requires this for the ordering oracle; it extends to all nine. If a case
   cannot be made to fail against a deliberately broken input, it is measuring
   nothing.
3. **No truncation in any output the matrix produces.** R21 is the direct
   precedent: the count was right and the list lied.

### D5 — Every conformance probe runs offline first

Each CONF case runs against `StrictScriptedTransport` in CI **and** optionally
against a live provider. CI is the ratchet; live is discovery. A CONF case that
cannot run offline is not admitted.

---

## 3. Contracts

**CT1** — resumed transcripts are *faithful*: a replayed history contains the
prior stage's user instruction (I-52).
**CT2** — every outbound request satisfies its adapter's `MessageRules` (I-50).
**CT3** — normalization never invents content; repair is reordering only.
**CT4** — the cacheable prefix is byte-identical after normalization
(protects the 74–99% live cache-hit rate).
**CT5** — unfixable lists (dangling `tool_call_id`) fail **locally**, before HTTP.
**CT6** — adding a provider is one registry line; adding a quirk is one field.
**CT7** — the conformance suite runs fully offline in CI.
**CT8** — same-family eval **loads with a loud warning** and runs with an
adversarial eval stance; disjoint eval warns not at all. A verdict records which
stance produced it.

---

## 4. Steps — CLOSED CORE (must land)

**Execution order.** S13.0 → S13.1 → S13.2 → S13.3 → S13.4, then the sub-steps in
dependency order: **S13.4a (I-51)** → **S13.4b (I-48)** → **S13.4c (eval
adversarial)** → **S13.4d (MessageRules hard gate)** as listed under S13.4. Do NOT
start S13.5+ until the closed core is green. S13.4c may proceed independently of
S13.4a/4b (they touch disjoint modules), but must land before the live matrix.

### S13.0 — Pin the failure (no edits)

Commit the live failing message shape as a fixture. **Source (verified):**
`llm_bodies.json` entry `[6]` from live `s11-wf-diag` — the coder-stage request
whose `response_body` is `code=3230`. `events.jsonl` carries only the error string
(`run_stopped`, reason `request_shape`); the **full 15-message array is in
`llm_bodies.json`**, not `events.jsonl`.

The fixture: a valid JSON array of **15 messages** with role sequence
`[system×3, user, assistant, tool, …, assistant]` ending on a **plain-text
`assistant`** (no `tool_calls`). Structure preserved; long content truncated to
first/last 60 chars; `tool_call_id`s and `tool_calls` ids kept verbatim so the
pairing invariant is testable.

**DoD:** fixture committed at `tests/fixtures/i50_resumed_assistant_last.json`;
a provenance record (source, run_id, session_id, provider/slug, the 3230 body) sits
beside it; the file parses as JSON and its last element's role is `assistant`.
**Class:** C0.

### S13.1 — `StrictScriptedTransport` — fix the oracle first

**The reason the suite missed a P1 defect:** S8's transport accepts any message
order. New transport enforces: **last role ∈ {user, tool}**; **no `user` whose
immediate predecessor is a `tool`** (Mistral 3230's other half); **every `tool`
message resolves to a declared `tool_call_id`**; and a trailing `assistant` that
carries unresolved `tool_calls` is treated as a **dangling-tool** failure (CT5),
not an ordering fix.

**Transport contract.** A drop-in `post(url, *, headers, json_body,
timeout_seconds, transport_retries) -> TransportResponse` (same signature as
`_ScriptedTransport` in `tests/test_cli.py:315`), recording each outbound
`json_body` and exposing a validator over its `messages` list. Lives in
`tests/test_s13_*` as a helper (Class C1 test substrate), not in production.

**DoD (negative proof + positive control):**
- **Negative:** pointed at **today's** unmodified composition path, feeding the
  S13.0 fixture as observations, the strict transport flags the **assistant-last**
  violation and the test **fails** (the offline stand-in for the 400). If it passes
  before the fix, the oracle is wrong and the slice stops.
- **Positive (D5a rule 1):** a **valid tool-final transcript passes unchanged**
  (the identity / K3 case) — proving the transport can distinguish "passed" from
  "never ran".
- **Live (per Q-C decision):** the same shape is verified by manual copy/paste on
  the live box (paste-safe block, positive control included) — see S13.5 harness.

**Class:** C1. **Kill-check:** revert S13.2/S13.3 → the negative test fails; set
`allows_trailing_assistant=True` on Mistral's rules → the strict transport still
flags assistant-last (a wrong config cannot override the provider's truth).

### S13.2 — I-52: faithful history rebuild

Replay `user_msg` rows in `coder_loop.py:450-490`, **chronologically** (each
`user_msg` precedes the `model_msg` it provoked in the event stream), so replay
cannot itself create a user-after-tool transition.

**Interactions, measured not assumed:**
- **Compaction:** replay is bounded by `latest_comp_idx` — `user_msg` rows written
  before a `compaction_stage3_done` live only inside the compaction summary and are
  **not** replayed (by design). The CT1 faithfulness test MUST use a
  **compaction-free fixture** so the prior stage's instruction is present and
  deterministic.
- **Token/cache cost:** extra messages per resumed request are measured and
  recorded (the workflow-propagated task is ~38 bytes per I-37, so duplication is
  negligible).

**Interaction with S13.3 (accepted, do not over-engineer):** in a workflow the
replayed prior-stage `user_msg` and S13.3's task-last carry the **same task text**.
That duplication is acceptable and intended — the replayed copy is the *prior
stage's* framing (satisfies CT1), the appended copy is the *current stage's*
directive (satisfies CT2). Do not try to dedupe; it would couple the two fixes.

**DoD:** C1 test asserts a resumed transcript contains the prior stage's user
instruction (compaction-free fixture); token delta measured and recorded.
**Class:** C1. **Kill-check:** revert replay → CT1 faithfulness test fails (K7).

### S13.3 — I-50: correct ordering at composition

**Target (terminal-role-conditional, NOT "task after history when non-empty"):**
in `build_prompt_parts_v2` (`prompt_composer.py:123-125`), emit the task message
**last iff the last observation is an `assistant` message with no unresolved
`tool_calls`**; otherwise emit it first. Rationale: a blanket "task after
observations" would place a `user` directly after a `tool` on turn 2+ within a
stage (history ends `tool`) — the second half of Mistral 3230 (CONF-6). The
terminal-role rule makes the final provider-visible message `user` in the I-50
resume case and leaves the already-valid tool-final/fresh cases untouched.

| last observation | placement | final role |
|---|---|---|
| none (fresh) | task first | `user` |
| `assistant`, no tool_calls (I-50 resume) | **task last** | `user` |
| `tool` (turn 2+ after a tool round) | task first | `tool` |
| `assistant` WITH unresolved tool_calls | **do not append task** — this is a dangling-tool (CT5/K4); fail locally | n/a |

**CT4 rationale (prove, don't assume):** the task and `observations` are **both**
in `non_cacheable`; moving the task within `non_cacheable` leaves `cacheable`
byte-identical, and the cache key (`role + hash_tools + hash_map + hash_always`)
does not include task/observations. CT4 therefore holds structurally; assert it
with a byte-equality test on the cacheable slice.

**Production hardening:** extend the `__debug__` invariant at `coder_loop.py:176`
to also assert, after `_compose_request_payload`, that the **composed** payload's
last role is `user` or `tool` (the current `_assert_tool_pairing_invariant` checks
pairing only; add a `_assert_final_role_invariant` on `messages_payload`). This
makes the loop fail fast in dev if the emitter regresses.

**DoD:** S13.1's transport passes the S13.0 fixture after the fix (last role
`user`); C1 test matrix covers assistant-final→task-last, tool-final→task-first,
empty→task-first, dangling-assistant→CT5 local-fail; CT4 byte-equality asserted.
**Class:** C1. **Kill-check:** revert → S13.1 negative test fails (K1).

### S13.4 — `MessageRules` + conformance pass at `chain.py:368`

**Design (concrete).**
- New module `src/fa/providers/message_rules.py` owning a frozen dataclass
  `MessageRules` with capability fields, defaulting to the strict-safe values:
  ```python
  @dataclass(frozen=True)
  class MessageRules:
      allows_trailing_assistant: bool = False      # OpenAI tolerates; Mistral/Anthropic do not
      requires_user_after_tool: bool = False        # False = reject user immediately after tool
      requires_top_p_one_when_greedy: bool = False  # Mistral reasoning models (I-48)
      # (tool-pairing validation is unconditional, not a flag — see CT5)
  ```
- `ProviderSpec` (`registry.py:25`) gains a `rules: MessageRules` field. Defaults
  (strict, `allows_trailing_assistant=False`) apply when unspecified (K6). Set per
  provider: `_OPENAI_COMPAT` gets `allows_trailing_assistant=True` (OpenAI-shaped
  endpoints tolerate a trailing assistant), `_MISTRAL`/`_ANTHROPIC` stay strict.
- The conformance pass is a pure function in `message_rules.py`:
  `validate_and_normalize(request_body: Mapping, rules: MessageRules, *, temperature: float|None)`
  → returns an (immutable) normalized body or raises a local
  `MessageRulesViolation` (before HTTP, per CT5). It **validates** ordering/pairing
  and **minimally normalises** sampling (the S13.4b `top_p` case). It never invents
  content (CT3) and never rewrites the cacheable prefix (CT4).
- `chain.py:368`, immediately before `provider.request(...)`, looks up the entry's
  `MessageRules` (via `PROVIDERS[entry.provider].rules`) and calls
  `validate_and_normalize(...)`. This is the single unbypassable chokepoint.

**DoD:** `MessageRules` module + `ProviderSpec.rules` + chain call-site land with
C0p unit tests (each flag's default and effect) and a C1 test that a strict-rule
provider **fails locally** on an assistant-last / dangling-tool request **before**
`provider.request` (assert no HTTP via a raising transport); production diff
touches only `providers/`; tests in `tests/test_s13_*`; K1–K6 green; suite
unchanged. **Class:** C1 + C0p.

**S13.4a — I-51: surface the provider's error (see section below).**
**S13.4b — I-48: sampling-shape conformance (see section below).**
**S13.4c — Eval independence: blocking → adversarial (see section below).**
**S13.4d — MessageRules hard gate:** once S13.4 + 4a + 4b are green, assert the
strict transport's rules and `MessageRules` for the same provider **agree** (the
S13.1 transport enforces Mistral-truth; the registry rules must not contradict it).
This is what makes K2 non-vacuous.

### S13.4a — I-51: surface the provider's error

**Source-verified (two sites).** `ProviderRequestShapeError`
(`errors.py:88-107`) has `.status` but **no `.provider`**; it is raised at
`base.py:126` and re-raised by `chain.py:376` (which stamps `.logical_call_id` but
not the provider, even though `entry.provider` is in scope). `coder_loop.py:1367-1379`
hardcodes `provider="unknown"`, `status=0` on the `api_retry` event, and
`output.py:347-352 _handle_api_retry` renders only `retry_after_s`, `provider`,
`status` — the real error sits in the event's `reason` and is **never printed**.

**Mechanism (two edits).**
1. Add `provider: str | None = None` to `ProviderRequestShapeError`; set it in
   `chain.py:376` (`exc.provider = entry.provider`) alongside the existing
   `logical_call_id` stamp.
2. `coder_loop.py:1373-1374` emit `exc.provider` / `exc.status` instead of
   `"unknown"`/`0`; and `output.py:_handle_api_retry` renders `reason` when
   present (append `d.get("reason")` to the line).

**DoD:** C1 test asserts the rendered console line contains the provider's message
(e.g. the `code=3230` detail) and the real provider/status, not `unknown/0`.
**Class:** C1. **Kill-check:** revert either half → the rendered line loses the
provider message (K5).

---

### S13.4b — I-48: sampling-shape conformance

**Source-verified.** FA never sends `top_p`: `RequestInfo.top_p` defaults to
`None` (`base.py:52`), `chain.py:332` fills it only from an explicit `sampling`
block, and every adapter emits it only when not-None. The operator's config has
no `sampling` block. So the `top_p` in the 400 is **server-side**, most likely
`reasoning_effort: "high"` putting the model into a greedy mode that conflicts
with the `temperature=0.0` FA sends.

**Why it belongs in S13 and not its own slice:** it is the same class as I-50 —
a provider-specific request-shape rule FA cannot know centrally — and it is
enforced at the same chokepoint by the same `MessageRules` mechanism, extended
to sampling.

**Mechanism.** Add to `MessageRules`:

```python
requires_top_p_one_when_greedy: bool = False   # Mistral reasoning models
```

When set and `temperature == 0`, the conformance pass (S13.4's
`validate_and_normalize`) sets `top_p=1` on the outgoing body **at the chain
chokepoint** (`chain.py:368`, before `provider.request`), rather than letting the
server apply a conflicting default.

**Do NOT "fix" this by omitting `top_p` in `mistral.py`** — FA already omits it.
That would patch code that is not at fault.

**DoD — offline mechanism test (required for closed-core independence, R3), plus
live confirmation:**
- **Offline (C1):** a unit test drives a request with `temperature=0` through
  `validate_and_normalize` with `requires_top_p_one_when_greedy=True` and asserts
  `top_p == 1` on the emitted body; a second case (flag False, or temperature≠0)
  asserts `top_p` is left absent. **Kill-check:** clear the flag → the offline
  test fails.
- **Live (CONF-8, verification not gate):** `mistral-medium-2604` reproduces the
  400 **before** the rule and passes after; the three discriminating probes in
  I-48 are run first to confirm the mechanism rather than assume it.

**Class:** C1. **Kill-check:** clear the flag → CONF-8 (live) and the offline
mechanism test both fail.

---

### S13.4c — Eval independence: blocking → adversarial

**Current source-verified behaviour.** `check_eval_disjoint` (`roles.py:186`)
raises `EvalFamilyConflictError`; called at `config.py:316-321`; caught at
`cli.py:{2039,2651,2833,2901}` → exit 2. Pinned by tests in
`test_roles.py`, `test_providers_config.py`, `test_providers_chain.py`,
`test_mistral_integration.py`, `test_s10b_cli_parity.py`,
`test_s10c_config_error_contract.py`.

**Files allowed to change:** `src/fa/roles.py`, `src/fa/providers/config.py`,
`src/fa/inner_loop/prompt.py` (**the eval system prompt `EVAL_SYSTEM_PROMPT` lives
here, `prompt.py:680`, and `_ROLE_PROMPTS` at `:895-898`** — NOT `profiles.py`;
`profiles.py` builds the tool registry and is out of scope), `src/fa/cli.py` (to
thread the stance / write `eval_report.json`), `knowledge/adr/ADR-2-*.md`, plus
the six test modules above.

**Mechanism.**

1. `check_eval_disjoint` → `assess_eval_independence(...) -> EvalIndependence`,
   a value object (`disjoint: bool`, `reason: str`, `stance: "neutral" |
   "adversarial"`). **It no longer raises.**
2. `config.py:316` appends to `ModelsConfig.warnings` when not disjoint —
   reusing the existing soft channel rather than inventing one.
3. **Stance threading (concrete):** the eval role's `ModelsConfig` carries the
   computed `stance`. At the point the workflow invokes the eval stage
   (`cli.py` → `_run_stage` → `drive_session(role="eval")`), the stance is
   appended to the eval system prompt via the existing `system_prompt_extra`
   parameter of `drive_session` (a standing directive added to the role prompt),
   e.g. an adversarial preamble instructing the evaluator to seek disconfirming
   evidence. It must be asserted on the **composed prompt**, not on a flag.
4. `eval_report.json` records `eval_independence: {disjoint, stance}` so a
   verdict carries its own provenance.

**Failure behaviour.** A malformed/unknown family still raises
`FamilyExtractionError` — this step relaxes the *disjointness* rule only, not
family validation. Do not widen it into "any family string is fine".

**Deprecation, not deletion.** Keep `EvalFamilyConflictError` exported and keep
the four `cli.py` handlers: removing a public exception is a separate breaking
change, and the handlers cost nothing. Mark it deprecated in the docstring.

**Test-update note (critical invariant preserved):**
`test_providers_chain.py:1035 test_invariant_adr2_eval_disjoint_uncircumventable_by_family_case`
asserts `check_eval_disjoint` **raises** on mixed-case families
(`"DeepSeek"`/`"deepseek"`) after `.strip().lower()`. Under the new contract its
target changes from "raises" to **"records non-disjoint despite case tricks"** —
i.e. the mixed-case pair must still be **detected as same-family** and yield
`disjoint=False` + adversarial stance. The family **normalisation** (`.strip()
.lower()`, `chain_from_mapping`) is what must not regress; update the assertion
target, not the invariant.

**DoD.**
- same-family config **loads**, emits exactly one warning naming both roles and
  the ADR-2 figures, and the run proceeds;
- disjoint config emits **zero** warnings (no false positives);
- eval stance is adversarial iff not disjoint — asserted on the composed prompt,
  not on a flag;
- `eval_report.json` carries `eval_independence`;
- the six pinning test modules are updated to assert the **new** contract, not
  deleted; the `test_providers_chain` invariant test target is changed per the
  note above;
- ADR-2 amended in the same commit.

**Tests-writing class:** C1 + C0p (contract change).
**Producer kill-check:** force `stance="neutral"` on a same-family config → the
adversarial-prompt assertion fails, naming the missing stance.

---

## 5. Steps — OPEN EXPLORATION (bounded by protocol)

### S13.5 — The conformance harness

`tests/conformance/` implementing CONF-1…7 against `StrictScriptedTransport`,
plus `fa conformance --provider <name>` for live runs.
**DoD:** all 7 run offline in CI; the command exists and is documented.
**Class:** C2.

### S13.6 — Rate-limit-aware live runner

At 30 RPM a full matrix will 429 (already observed in S11.4e). The runner needs
per-provider RPM config, sequential execution with backoff, and **resumability**
so a 429 does not discard completed results.
**Run identity.** S11 hit `run_id_reused` twice and the operator had to invent
`-2`, `-3` suffixes mid-run — which then defeated the sheet's static rollback
list (R26). The matrix runner must mint run-ids itself
(`conf-<provider>-<case>-<utc>`), never reuse, and clean up by **glob**, never
by an enumerated list.

**DoD:** a matrix run survives an induced 429 without losing prior rows; a
second run of the same matrix does not collide with the first; cleanup removes
every `conf-*` dir it created and nothing else.
**Class:** C1.

### S13.7 — Onboard registry-known-but-unexercised providers

**Groq, Cerebras, NVIDIA NIM** — already registry names, never run.
**DoD per provider:** CONF matrix recorded; `MessageRules` set from *measured*
behaviour, never assumed; deltas → BACKLOG.
**Class:** C3. **Stop rule:** a provider needing more than a `MessageRules`
field gets its own slice — do not grow adapters inside S13.

### S13.8 — One genuinely new adapter (Gemini)

Gemini is **not** OpenAI-shaped, so this measures the real cost of "add a
provider". It is the honest answer to the operator's question.
**DoD:** CONF matrix; **a measured line count** for the new adapter, recorded in
the parent plan as the true onboarding cost.
**Class:** C3. **Stop rule:** if it exceeds ~200 lines, stop and promote to its
own slice.

### S13.9 — Cross-family workflow (§1.4's real payoff)

Run `planner→coder→eval` with **genuinely different families** per role, which
is what `check_eval_disjoint` was written for.
**DoD:** one full workflow completes across ≥2 providers; ensemble behaviour
recorded. **Class:** C3.

---

## 6. Kill-checks

| # | force | expected |
|---|---|---|
| K1 | revert S13.3 | strict transport fails with the 3230 shape |
| K2 | flip `allows_trailing_assistant=True` for Mistral | strict transport still fails — a wrong config cannot override the provider's truth (S13.4d) |
| K3 | already-valid list | normalization is a **no-op** (identity) |
| K4 | dangling `tool_call_id` | raises locally, before HTTP |
| K5 | revert either half of S13.4a | rendered line loses the provider message |
| K6 | new `ProviderSpec`, no rules | defaults apply, suite green |
| K7 | revert S13.2 | the CT1 faithfulness test fails |
| K8 | induced 429 mid-matrix | runner resumes, prior rows intact |
| K9 | same-family config | **loads** (no exit 2), exactly one warning, adversarial stance in the composed eval prompt |
| K10 | disjoint config | **zero** warnings, neutral stance — proves K9 is not vacuous |

K3 is the quiet one: a normalizer that rewrites *healthy* requests would
silently invalidate every prompt-cache entry.

---

## 7. Risks

| # | risk | mitigation |
|---|---|---|
| R1 | **prompt-cache regression** | CT4; live before/after; **<74% is a stop condition** |
| R2 | I-52 raises token cost per resumed request | measured in S13.2, recorded; compaction interaction explicitly checked |
| R3 | **open scope never closes** | closed core is independently shippable; S13.5+ has per-provider stop rules |
| R4 | free-tier 429s make live results noisy | S13.6 is a prerequisite for S13.7+, not an afterthought |
| R5 | a new provider needs deep adapter work | stop rule: >~200 lines → own slice |
| R7 | **eval independence silently degrades** now that it does not block | CT8 + K9/K10; warning on the structured event bus, and `eval_report.json` records the stance so a correlated `DONE` is auditable after the fact |
| R8 | adversarial stance makes eval reject good work | S13.9 measures verdict distribution across both stances; a false-reject spike is a stop condition |
| R6 | ToS: free tiers are dev/test only | conformance runs are development testing; no production traffic, one account per provider |

---

## 8. Definition of Done

**Closed core (blocking):**

- [ ] S13.1 negative-proof (assistant-last) **fails on unfixed code**, and its
      positive-control (tool-final) passes
- [ ] K1–K7 executed with real output
- [ ] Linux suite green; coverage ≥ 83.22% (new terminal-role branches have
      explicit C1 tests, not incidental coverage)
- [ ] CT4 asserted offline (cacheable prefix byte-identical) — the offline gate;
      the **live ≥74%** check is the confirmation, not the only gate
- [ ] Zero `noqa`
- [ ] **Live:** `fa workflow planner,coder,eval` completes past stage 2
- [ ] **Live:** cache-hit ≥ 74%
- [ ] S11.7 re-run; Q35b exit-1 path attempted
- [ ] Same-family eval loads + warns + runs adversarial (K9); disjoint stays
      silent and neutral (K10)
- [ ] ADR-2 amended in the same commit as the behaviour change

**Open exploration (reported, not gated):**

- [ ] CONF-1…7 run offline in CI
- [ ] ≥3 providers with a recorded capability matrix
- [ ] ≥1 non-OpenAI-shaped adapter, with measured line count
- [ ] ≥1 cross-family workflow completed
- [ ] Every divergence found → BACKLOG with repro

---

## 9. Open questions

**Q61 — which providers, and who holds the keys?** S13.7/S13.8 need real
accounts. Groq + Cerebras + NVIDIA NIM cover three infrastructures with no card.
Confirm the list and who registers.

**Q62 — does the conformance matrix become a CI gate?** Recommend **no** for
live runs (flaky, rate-limited, costs tokens) and **yes** for the offline
`StrictScriptedTransport` half. Confirm.

**Q63 — `models.yaml` schema for multi-provider roles.** Cross-family roles may
want per-provider `sampling`. The current schema supports it via chain entries;
S13.9 will show whether that is ergonomic. Defer until measured.

---

**Q65 — does I-37 (context cost) belong in S13, or its own slice?**
S11.8c measured `AGENTS.md` at **55.4%** of a live request and the tool schemas
duplicated at **33.1%**, against a task payload of **0.1%**. That is the largest
single efficiency finding of the whole workplan, and the operator's stated goal
is *"a token-efficient chain suitable for many providers"* — so it is squarely
on-goal.

**Recommendation: keep it OUT of S13.** Reasons, in order of weight:
1. **It changes the cacheable prefix.** S13 already touches message ordering and
   must prove the 74–99% cache-hit rate survives (CT4/R1). Changing *what is in*
   the prompt at the same time as *what order it is in* makes a cache regression
   un-attributable to either.
2. **Different risk profile.** S13 is mechanical (ordering, capability flags);
   trimming `AGENTS.md` is a **behavioural** change — the agent may get worse at
   tasks. That needs task-quality measurement, which S13 has no apparatus for.
3. **S13 provides the instrument.** CONF-7 records cache behaviour and CONF-8
   replays real deployed configs. Running the context slice *after* S13 means it
   inherits a working multi-provider measurement harness instead of building one.

**But S13 should leave a hook:** CONF-7 must record **request composition sizes
per provider**, not just the cache-hit rate. Different providers may bill and
cache the same prompt differently, and that data is nearly free to collect while
the matrix is running. → folded into CONF-7's definition.

**Q64 — should the adversarial stance also apply to *cross-family* eval?**
Arguably an adversarial eval is better in general, and only its *necessity*
depends on family overlap. This plan keeps cross-family neutral so S13.9 can
measure the two stances against each other; making both adversarial would
remove the control group. Revisit once there is data.

## 10. Anti-theatre checklist

- [x] Researched production harnesses before designing (opencode #19517/#6346,
      LiteLLM #17761, LibreChat #12429, crush #279, pydantic-ai #3733)
- [x] Rejected LibreChat's synthetic-message fix with a stated reason
- [x] Verified the chokepoint is single by `grep`, not assumption
- [x] Verified 18 providers → 4 adapters, and named why that is a trap
- [x] Found the pre-existing architectural driver (`check_eval_disjoint`)
      rather than treating multi-provider as a new feature
- [x] Rate limits treated as a design input (S13.6 gates S13.7)
- [x] Open half bounded by a protocol + stop rules, so it can end
- [x] The eval-disjoint relaxation is justified by showing the **existing gate
      is already defeated by a string edit on the live box**, not by asserting
      the risk is gone; replacement mechanism + audit trail specified
- [ ] READY — pending operator review
