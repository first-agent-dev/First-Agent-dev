> **SUPERSEDED 2026-08-03 by
> [`PLAN-cli-trace-S13-multi-provider-conformance.md`](./PLAN-cli-trace-S13-multi-provider-conformance.md).**
> The operator answered Q59 (*fix FA's own composition bug first*) and Q60
> (*fix the history rebuild too*), and widened the slice to exercise providers
> that have no config presence at all. This file is retained because its §2
> research (opencode, LiteLLM, LibreChat, crush, pydantic-ai) is still the
> evidence base for the design; the scope and step list are obsolete.

# PLAN: S13 — provider-agnostic message normalization (closes I-50)

**Status:** DRAFT — awaiting review
**Author:** agent, 2026-08-03
**Parent:** `cli-trace-substrate-rebaseline-2026-07-25.md`
**Closes:** **I-50 (P1)**, **I-51 (P2)**. Partially unblocks **S11.7 / Q35b**.
**Ceremony:** lean
**Blast radius:** `src/fa/providers/` + `tests/`. No CLI, no session, no schema.

---

## 0. One-paragraph statement

`fa workflow` cannot complete a `planner→coder→eval` pipeline against Mistral: the
resumed stage sends a message list ending in an `assistant` message and the
provider rejects it with HTTP 400 `code=3230 invalid_request_message_order`. FA
composes one canonical message list and hands it to whichever adapter the chain
selected, so any per-provider ordering rule is currently unenforced. This slice
adds a **normalization pass at the single chokepoint every provider request
already passes through** (`chain.py:368`), driven by a small per-adapter
capability record. It is the pattern used by opencode, LiteLLM and LibreChat for
exactly this error, and it keeps the operator's goal intact: swap provider or
model with **zero** schema edits.

---

## 1. Preflight — source-verified

### 1.1 The defect, from the provider's own words

Recovered from `events.jsonl` on the deployed box (S11.7):

```
status=400 code=3230 type=invalid_request_message_order
"Expected last role User or Tool (or Assistant with prefix True)
 for serving but got assistant"
```

### 1.2 Mechanism — three lines of source

| # | site | behaviour |
|---|---|---|
| 1 | `prompt_composer.py:123-125` | appends the task as `user`, **then** `non_cacheable.extend(observations)` — history lands *after* the task |
| 2 | `coder_loop.py:450-490` | rebuilds history from the session DB as `assistant` / `tool` messages only; **never replays `user_msg`** |
| 3 | `cli.py:1248` | `_run_stage` passes `"resume": not fresh`, so stage 2 inherits stage 1's transcript |

The planner ends `stopped_by_llm` on a text turn, so the tail is a `model_msg`
with no tool call. Net: `[system ×3, user "Task: …", …history…, assistant]`.

### 1.3 It explains every observation

| scenario | history | last role | live result |
|---|---|---|---|
| standalone `fa run` | empty | `user` | **200** |
| planner, stage 1 (`fresh`) | empty | `user` | **200** |
| coder, stage 2 (`resume`) | planner's turns | **`assistant`** | **400** |
| turn 2+ within one session | ends in tool result | `tool` | **200** |

Not model-specific (I-48 was a *different* 400) and not role-specific.

### 1.4 The chokepoint already exists

`grep` for provider entry points returns **one** call site:

```
src/fa/providers/chain.py:368    response = provider.request(entry_request, ...)
```

No module outside `chain.py` constructs a provider. So a normalization pass
placed immediately before that line is **unconditionally** on the path of every
request FA makes — nothing can bypass it.

### 1.5 Registry already maps family → adapter

`registry.py:35-38` defines `ProviderSpec(factory=…, adapter="openai_compat" |
"anthropic" | "mistral" | "mistral_agents")`. The `adapter` string is the
natural key for a capability record — it already exists and is already the thing
that determines wire format.

---

## 2. How production harnesses solve this

Researched before designing. This is a **well-known, cross-ecosystem** class,
not a Mistral quirk:

| project | symptom | their fix |
|---|---|---|
| **opencode** [#19517](https://github.com/anomalyco/opencode/issues/19517) | Azure Claude: *"does not support assistant message prefill"* | maintainer-recommended **Option A: strip/repair trailing assistant in `normalizeMessages()`**, driven by "a provider-level capability flag" |
| **opencode** [#6346](https://github.com/anomalyco/opencode/issues/6346) | Devstral via LiteLLM: identical `3230` | same normalization layer |
| **LiteLLM** [#17761](https://github.com/BerriAI/litellm/issues/17761) | `Unexpected role 'user' after role 'tool'` | `litellm.modify_params` — a documented **message-sanitization** layer that inserts synthetic messages |
| **LibreChat** [#12429](https://github.com/danny-avila/LibreChat/issues/12429) | same `3230` after a tool call | insert a bridge assistant message between `tool` → `user` |
| **crush** [#279](https://github.com/charmbracelet/crush/issues/279) | `Unexpected role 'tool' after role 'user'` | same class |
| **pydantic-ai** [#3733](https://github.com/pydantic/pydantic-ai/issues/3733) | `Unexpected tool call id … in tool results` | history sanitization |

**Two things every mature harness converged on**, and both are load-bearing here:

1. **A canonical internal message format, normalized *per provider* at the
   boundary.** strongdm's unified-LLM spec states it directly: *"the unified SDK
   abstracts over these different APIs so that callers write provider-agnostic
   code, but internally each adapter speaks the provider's native protocol."*
   The alternative — a lowest-common-denominator shape — *"loses access to
   provider-specific capabilities like reasoning tokens, extended thinking,
   prompt caching."* FA already relies on prompt caching (74–99% live hit
   rates), so LCD is not an option.
2. **Capability flags, not provider name checks.** opencode's own issue lists
   "provider ID contains `azure_ai`" as a *detection criterion* and then notes a
   capability flag is the better form. Same lesson as S12: probe the capability,
   don't hardcode the platform.

**What we deliberately do NOT copy:** LibreChat's *"insert an assistant message
saying `Understood.`"* — injecting invented assistant text into an agent
transcript pollutes the context the model reasons over and costs tokens on every
subsequent turn. For a coding agent that is worse than the bug.

---

## 3. Design

### D1 — One canonical list, normalized at the boundary

FA keeps composing a single provider-neutral message list. `ProviderChain`
normalizes it **per adapter** immediately before `provider.request(...)`. No
caller changes; no role, session or CLI code is touched.

### D2 — Capability record keyed on the existing `adapter` string

```python
@dataclass(frozen=True)
class MessageRules:
    allows_trailing_assistant: bool = True  # OpenAI-style prefill tolerated
    allows_user_after_tool: bool = True  # Mistral rejects this too (3230)
    requires_tool_result_pairing: bool = True
```

Attached to `ProviderSpec` in `registry.py`. Adding a provider stays **one
line**, which is the operator's stated goal.

### D3 — Repair by *reordering FA's own content*, never by inventing content

The trailing-assistant case is repaired by **moving the task `user` message to
the end**, not by appending filler. The task text is already in the request; the
current order is simply wrong for a resumed session. This is strictly better
than both alternatives:

- it adds **zero** tokens (vs. LibreChat's synthetic `"Understood."`);
- it is **semantically more correct** — a new instruction should follow the
  inherited context it refers to, not precede it.

Only if no `user` message exists at all does the pass fall back to a minimal
synthetic continuation, and that path is logged.

### D4 — Fail loudly when normalization cannot fix it

If the rules cannot be satisfied (e.g. a dangling `tool_call_id`), raise a
typed error **before** the HTTP call rather than letting the provider 400. A
local error naming the offending index beats a remote error naming nothing.

### D5 — Prompt-cache safety is a measured constraint, not an afterthought

Moving the task message changes the tail of the message list. The cacheable
prefix (`system` ×3 + AlwaysSkills) is **unchanged** — `prompt_composer.py:96-110`
puts all cacheable content first and the task is already in `non_cacheable`.
**DoD requires measuring the live cache-hit rate before and after**; a
regression below the 74% floor is a stop condition.

### D6 — Fix I-51 in the same slice

Root-causing I-50 took three live runs *because* the console prints
`(unknown/0)` and discards the provider's message. One-line-each fix in
`coder_loop.py` + `output.py`. Cheap, and it is the difference between a
five-minute diagnosis and a three-run one.

---

## 4. Contracts

**CT1 — every outbound request satisfies its adapter's rules.**
Enforced at `chain.py:368`; no bypass exists (§1.4).

**CT2 — normalization never invents assistant content.**
Repair reorders existing messages. Asserted by a test that diffs the multiset of
message contents before/after: it must be unchanged for the reorder path.

**CT3 — token-neutral for the common case.**
The reorder path adds no messages and no characters. Test asserts equal total
content length before/after.

**CT4 — cacheable prefix is byte-identical after normalization.**
Guards the 74–99% live cache-hit rate (D5).

**CT5 — an unfixable list fails locally, not remotely.**
A dangling `tool_call_id` raises before the HTTP call.

**CT6 — adding a provider is one line.**
A new `ProviderSpec` with default `MessageRules` needs no other edit.

---

## 5. Steps

### S13.0 — Pin behaviour (no edits)

Record the exact failing message shape from the live `events.jsonl` as a test
fixture. **DoD:** fixture committed; a test reproduces the 400 shape against a
scripted transport that *enforces* Mistral's rule. **Class:** C0.

### S13.1 — A transport that enforces provider rules (the missing oracle)

**The root reason the suite missed I-50:** S8's scripted transport accepts any
message order. Add `StrictScriptedTransport` that rejects the orderings real
providers reject.

**DoD:** the new transport, pointed at *today's* code, **reproduces the 400**.
Negative proof — if it passes on unfixed code the oracle is wrong.
**Class:** C1. **Kill-check:** revert the fix → this test fails.

### S13.2 — `MessageRules` + `normalize_messages`

New `src/fa/providers/message_rules.py`. Pure function,
`(messages, rules) -> messages`, no I/O, fully unit-testable.
**DoD:** table-driven tests per rule; each rule proven to fire *and* to be a
no-op when already satisfied. **Class:** C1.

### S13.3 — Wire into `ProviderChain`

One call before `chain.py:368`; `MessageRules` onto `ProviderSpec`.
**DoD:** `git diff` shows no change outside `providers/`; full suite green.
**Class:** C0p.

### S13.4 — I-51: surface the provider's error

Carry real `provider`/`status`; render `reason`.
**DoD:** a C1 test asserts the rendered line contains the provider's message;
kill-check reverting either half loses it. **Class:** C1.

### S13.5 — Mutation sweep over the new module

**Class:** C3. Survivors are questions, not verdicts.

---

## 6. Kill-checks

| # | force | expected |
|---|---|---|
| K1 | revert the reorder | S13.1 strict transport fails with the 3230 shape |
| K2 | `allows_trailing_assistant=True` for Mistral | strict transport fails |
| K3 | already-valid list | normalization is a **no-op** (identity), proving it does not churn healthy requests |
| K4 | dangling `tool_call_id` | raises locally, before HTTP (CT5) |
| K5 | revert either half of the I-51 fix | rendered line loses the provider message |
| K6 | new `ProviderSpec`, no rules | defaults apply, suite green (CT6) |

K3 is the quiet one: a normalizer that rewrites healthy requests would silently
invalidate every prompt-cache entry.

---

## 7. Risks

| # | risk | mitigation |
|---|---|---|
| R1 | **prompt-cache regression** | CT4 + D5; live before/after measurement is a DoD item, 74% is a stop condition |
| R2 | reordering changes model behaviour | task-after-context is the more natural order; S11.7 re-run is the live proof |
| R3 | rules wrong for an untested provider | defaults are permissive (today's behaviour); a wrong rule can only *add* a repair, and K3 proves no-op on valid input |
| R4 | hides a real upstream bug | D4 fails loudly instead of silently repairing; the `coder_loop.py:450-490` history-rebuild gap is recorded separately as I-52 |

---

## 8. Definition of Done

- [ ] Strict transport reproduces the 400 on unfixed code (S13.1 negative proof)
- [ ] `normalize_messages` unit-tested per rule, both directions
- [ ] K1–K6 executed with real output
- [ ] Linux suite unchanged except the new tests; coverage ≥ 83.22%
- [ ] `git diff --numstat` touches only `src/fa/providers/` and `tests/`
- [ ] Zero `noqa`
- [ ] **Live:** `fa workflow planner,coder,eval` completes past stage 2
- [ ] **Live:** cache-hit rate ≥ 74% (R1)
- [ ] I-51 verified live: a 400 prints the provider's message
- [ ] S11.7 re-run; Q35b exit-1 path attempted

---

## 9. Open questions

**Q59 — repair or reject?** This plan **repairs** (reorders). The alternative is
to reject and force the caller to compose correctly. Repair is right for
`trailing_assistant` (FA's own composition bug, invisible to the operator) but
arguably wrong for a dangling `tool_call_id` (a real state bug worth surfacing).
Current split: repair ordering, **reject** pairing violations. Confirm.

**Q60 — fix the history rebuild too?** `coder_loop.py:450-490` never replays
`user_msg` rows, so a resumed transcript is not a faithful replay. Normalization
makes the request *valid*; it does not make the history *complete*. Larger blast
radius → recorded as **I-52**, not fixed here. Confirm deferral.

---

## 10. Anti-theatre checklist

- [x] Researched how production harnesses solve this **before** designing
- [x] Rejected LibreChat's synthetic-message approach with a stated reason
- [x] Verified the chokepoint is genuinely single (`grep`, one call site)
- [x] Reused the existing `adapter` key rather than inventing a taxonomy
- [x] The oracle gap (permissive test transport) is fixed **first**, in S13.1
- [x] Prompt-cache impact is a measured DoD item, not an assumption
- [ ] READY — pending operator review
