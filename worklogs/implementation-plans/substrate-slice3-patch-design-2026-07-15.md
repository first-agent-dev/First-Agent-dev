# Slice 3 Patch Design — Stage C Correctness Pass

**Date:** 2026-07-15  
**Scope:** Slice 3 only  
**Purpose:** make Stage C semantically correct at runtime and truthful at the provider boundary.

---

## 1. Slice 3 scope

Slice 3 addresses the still-open Stage C defects:

1. **threshold/state-machine collapse**
2. **configured compactor role not actually used as provider model slug**
3. **prompt-cache metadata dying before provider boundary**
4. **local Stage 3 fallback not always honoring the 4-header contract**

Slice 3 does **not** take on:
- Slice 4 governance-plane separation (`PinnedBuffer` vs mutable resume context)
- Slice 5 subagent hardening
- Slice 6 PTY/bash truthfulness
- Slice 9 global export

---

## 2. Locked expectations for Stage C

### 2.1 State machine expectation

The intended runtime behavior should be explicit:

- **Warn zone** — around 70%
- **Stage 2 zone** — around 80% (mask older bulky tool outputs)
- **Stage 3 zone** — around 90% (LLM compaction if still necessary)
- **Hard stop** — only when:
  - compaction is disabled and usage is already in the Stage 3 zone, or
  - compaction attempts leave usage still in the Stage 3 zone, or
  - circuit breaker trips

### 2.2 Dynamic threshold expectation

The existing locked dynamic fallback remains valid for Stage 2:

- `stage2_threshold = configured_threshold or min(int(context_limit * 0.80), 150000)`

Stage 3 must then be distinct and derived from the model limit rather than reusing Stage 2.

### 2.3 Provider-boundary truth expectation

If prompt caching / cache anchors are claimed, they must survive to the actual provider request body.

That means:
- OpenAI-compatible family must receive prompt-cache fields in its outbound JSON body.
- Anthropic family must receive cache-control information in a body form that survives system-row hoisting.

### 2.4 Compactor role expectation

If CLI loads a `compactor` role and builds a `compactor_chain`, the Stage 3 request must use the configured model identity, not a hardcoded placeholder slug.

---

## 3. Proposed Stage C state machine

### 3.1 Threshold definitions

For a given `context_limit` and optional configured Stage 2 threshold:

- `warn_threshold = min(int(context_limit * 0.70), int(stage2_threshold * 0.875))`
- `stage2_threshold = configured_threshold or min(int(context_limit * 0.80), 150000)`
- `stage3_threshold = min(max(stage2_threshold + 1, int(context_limit * 0.90)), context_limit)`

Notes:
- `stage3_threshold` is guaranteed to be strictly above `stage2_threshold`.
- If `context_limit` is small, `stage3_threshold` clamps to `context_limit` as needed.

### 3.2 `ContextBudget.check()` contract

Return values should become:
- `allow`
- `warn`
- `stage2`
- `stage3`

Not a single collapsed `require_compaction` action.

### 3.3 Caller policy in `drive_session()`

#### If action == `warn`
- log warning
- continue

#### If action == `stage2`
- if compaction enabled:
  - run Stage 2
  - recompute usage
  - if new action is still `stage3`, escalate to Stage 3
  - if new action remains `stage2`, continue (Stage 2 already applied)
- if compaction disabled:
  - warn only
  - continue

#### If action == `stage3`
- if compaction enabled:
  - still run Stage 2 first (deterministic cheap reduction first)
  - recompute usage
  - if still `stage3`, run Stage 3
  - recompute usage
  - if still `stage3`, hard stop
- if compaction disabled:
  - hard stop immediately

#### Circuit breaker
Unchanged in principle, but now it is clearly part of the Stage 3 post-compaction hard-stop path.

---

## 4. Code-facing patch map

### 4.1 `src/fa/memory/context_budget.py`

**Needed changes:**
1. keep `estimate_tokens()` unchanged
2. replace the collapsed `check()` logic with explicit stage outputs
3. expose `stage2_threshold` and `stage3_threshold` in returned diagnostics
4. keep circuit-breaker accounting unchanged unless implementation reveals a bug

**Expected outcome:**
- thresholds are explicit,
- state-machine inputs are explicit,
- tests can assert exact stage boundaries.

---

### 4.2 `src/fa/inner_loop/coder_loop.py`

**Needed changes:**
1. stop branching on one `require_compaction` action
2. add a small helper for provider request payload extraction so:
   - `messages_payload` is built once per prompt build
   - request extras are preserved for OpenAI-compatible providers
3. apply Stage 2 / Stage 3 logic according to the new action values
4. set hard-stop semantics only in the Stage 3 zone or circuit-breaker path
5. preserve logging and event rows with corrected threshold semantics

**Expected outcome:**
- no more “80% does mask + compact + hard-stop” collapse,
- request extras finally reach `RequestInfo`.

---

### 4.3 `src/fa/inner_loop/compaction/compactor.py`

**Needed changes:**
1. use `compactor_chain.config.model` as the request model slug when available
2. make local fallback always return a valid 4-header block, even for short history
3. keep required-header validation on LLM output

**Expected outcome:**
- compactor role is real,
- fallback is contract-honest.

---

### 4.4 `src/fa/inner_loop/prompt_composer.py`

**Needed changes:**
1. preserve existing Anthropic message-level cache-control for stable cacheable system segments
2. additionally anchor the memory-summary system block (when present) so the compaction summary itself has a cache breakpoint
3. keep OpenAI-compatible `extra_body` contract stable so existing tests stay meaningful

**Expected outcome:**
- cache-control claim is stronger and closer to the plan’s stated architecture.

---

### 4.5 `src/fa/providers/anthropic.py`

**Needed changes:**
1. change system-row hoisting logic so cache-control on system rows survives
2. when no system row contains extra structure, preserve old plain-string behavior
3. when cache-control exists on system rows, emit `system` as structured content blocks rather than a joined string

**Expected outcome:**
- Anthropic cache anchors are no longer stripped out by the adapter.

---

### 4.6 `src/fa/providers/openai_compat.py`

Likely no code changes needed if `RequestInfo.extras` is populated correctly by `coder_loop`, because this adapter already forwards `request.extras` into the body.

---

## 5. Test plan

### 5.1 Update/add tests for threshold ladder

#### `tests/test_compaction_sota.py`
Add/adjust tests to assert:
- 70% => `warn`
- 80% => `stage2`
- 90% => `stage3`
- dynamic threshold still works for Stage 2
- Stage 3 threshold is distinct and above Stage 2

### 5.2 Add integration test for disabled compaction semantics

#### `tests/test_pr1_wiring.py`
Add a test like:
- usage in Stage 2 zone with compaction disabled → no hard stop
- usage in Stage 3 zone with compaction disabled → hard stop

This corrects the earlier theater-ish assumption that “compaction disabled => hard stop at 80”.

### 5.3 Add integration test for distinct Stage 2 vs Stage 3 behavior

#### `tests/test_pr5_wiring.py`
Add a test that proves:
- Stage 2 can trigger,
- reduce usage,
- and avoid Stage 3 when usage falls below the Stage 3 threshold.

### 5.4 Add provider-boundary cache tests

#### `tests/test_pr3_wiring.py`
Add a test that, for OpenAI-compatible family, `drive_session()` places prompt-cache metadata into `RequestInfo.extras`.

#### `tests/test_providers_openai_compat.py`
Add a test that `RequestInfo.extras={...}` reaches the outbound JSON body as top-level fields.

#### `tests/test_providers_anthropic.py`
Add a test that system rows with `cache_control` survive hoisting into a structured `system` field.

### 5.5 Add compactor model selection test

#### `tests/test_pr5_wiring.py`
Extend current Stage 3 test to assert:
- `compactor_req.model_slug == mock_compactor_chain.config.model`

### 5.6 Add fallback-header test for short history

#### `tests/test_compaction_sota.py`
Assert that short-history local fallback still contains all four headers.

---

## 6. Anti-theater rules for Slice 3

A test does **not** count as sufficient if it only:
- inspects prompt-composer output before `RequestInfo`
- inspects `RequestInfo.messages` while ignoring `RequestInfo.extras`
- checks “some compaction happened” without proving stage separation
- checks comments/docstrings instead of runtime decisions

At least one test per major defect must target the real boundary:
- provider-body or `RequestInfo.extras` path
- actual `ContextBudget.check()` output
- actual `drive_session()` transition behavior

---

## 7. Expected done definition

Slice 3 is done when all of the following are true:
1. Stage C thresholds are explicit and distinct
2. 80% and 90% no longer collapse into one action
3. compactor request uses configured model identity
4. OpenAI-compatible cache metadata reaches the request body path
5. Anthropic cache-control survives system hoisting
6. local compaction fallback always emits 4 headers
7. integration tests prove Stage 2 can happen without unnecessary Stage 3

---

## 8. Non-goals reminder

Even after Slice 3 lands, the following may still remain open legitimately:
- pinned-governance plane cleanup (Slice 4)
- subagent hardening (Slice 5)
- PTY/bash truthfulness (Slice 6)
- global export (Slice 9)

That is acceptable so long as Slice 3 itself becomes semantically correct and test-honest.
