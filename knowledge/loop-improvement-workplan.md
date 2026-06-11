# Loop Improvement Workplan

Last updated: 2026-06-11

This is the active implementation tracker for the cache/context loop-optimization plan. It supersedes the earlier free-form chat plan as the durable checklist for future sessions.

## Non-negotiable invariants

1. **Cache discipline beats token cutting.** Do not mutate stable request prefixes for marginal token savings.
2. **Audit log and model context are sibling sinks.** They may differ in content, but not in ordering, pairing, or completeness invariants.
3. **Tool-use/tool-result pairing is a provider invariant.** Every request assembly or compaction strategy must preserve complete pairs.

## Landed in the loop-foundation PR

### Tier 0 — instrumentation foundation

Status: **LANDED**

- `ResponseInfo.cache_read_input_tokens`
- `ResponseInfo.cache_creation_input_tokens`
- Anthropic adapter cache-counter extraction
- OpenAI-compatible adapter cached-token extraction
- Per-response `usage` rows in `events.jsonl`
- Terminal `session_summary` row
- `cache_hit_ratio` calculation
- Recorded transcript cache SLO test: `cache_hit_ratio >= 0.7` once `n_turns >= 5`

### Pairing invariant

Status: **LANDED**

- `_assert_tool_pairing_invariant(messages)` in `src/fa/inner_loop/coder_loop.py`
- Runs under `__debug__` before every `provider_chain.request()`
- Handles OpenAI-shaped history and Anthropic-style content-block history
- Canonicalizes fallback tool-call ids for malformed provider emissions before adding assistant tool-call history

### Tier 1.1 — canonical tool serialization

Status: **LANDED**

- `render_tool_specs()` sorts by `ToolSpec.name`
- Payloads round-trip through canonical JSON:
  - `sort_keys=True`
  - `separators=(",", ":")`
- Regression test asserts order independence

### Tier 2.1 / 2.3 — tool projection chokepoint foundation

Status: **LANDED**

- `ToolSpec.max_context_bytes: int = 4096`
- `ToolSpec.elide: Callable[[Any, int], str] | None`
- Negative budget rejection
- `ArtifactStore` for content-addressed elided payloads
- `project_for_model(spec, result, artifact_store)` single chokepoint
- Direct provider-message `result.summary` append replaced by `project_for_model(...)`
- `SessionState.record_tool_result()` records full successful `ToolResult.result` payloads in `events.jsonl`

## Remaining work — next implementation order

### 1. Tier 2.2 — per-category elision strategies

Status: **NEXT**

Implement and test strategy callables:

- file reads: head + tail
- test/build output: tail-only
- grep/search: first N hits + count of remainder
- diffs: full if within budget; otherwise file/hunk summary
- HTTP responses: headers/head + content length / remainder size

Notes:

- The current default is generic head/tail only.
- Do not apply head/tail blindly to test/build/search output.
- Wire concrete built-in tools to appropriate strategies where categories are known.

### 2. Tier 2.5 — summary helper module

Status: **NEXT AFTER ELISION**

Add `src/fa/inner_loop/summarize.py` with helpers such as:

- `summarize.file_read(...)`
- `summarize.test_run(...)`
- `summarize.grep(...)`
- `summarize.shell(...)`

Goal: make correct short summaries cheap for handler authors so the model does not lose high-signal context when raw output is elided.

### 3. Tier 2.6 — internal_error context leak fix

Status: **NEXT AFTER SUMMARIES**

Move unexpected handler exception handling out of `ToolRegistry.dispatch()` and into `run_session()` where `state.log` is in scope.

Required behavior:

- Full traceback to `state.log` as `kind="tool_crash"`
- Model-visible error clipped to `str(exc)[:500]`
- Preserve paired `tool_call` / `tool_result` audit rows
- Keep `ToolRegistry` as a pure validation + dispatch surface

### 4. Tier 5 — request assembly seam

Status: **DEFER UNTIL AFTER TIER 2.6**

Add:

- `LifecyclePoint.BEFORE_REQUEST_ASSEMBLY`
- `AssemblyPayload(messages, tools, usage_last_turn)`
- dispatch in `drive_session`, not `run_session`
- hard tools-immutability guard
- pairing invariant check on assembled messages

Ship no middleware initially. This is only the seam for future compaction.

### 5. Tier 1.3 — provider cache-control markers

Status: **DEFERRED / ADAPTER-SPECIFIC**

Implement only after instrumentation data is available and adapter design is reviewed.

Potential work:

- Anthropic cache-control TTL layout:
  - tools/system/static context: `ttl="1h"`
  - tail: `ttl="5m"`
- OpenAI-compatible `prompt_cache_key` where supported

Caution: provider-specific cache controls can easily perturb request shape. Guard with tests.

### 6. Tier 6 — threshold-driven compaction

Status: **DEFERRED UNTIL METRICS JUSTIFY**

Do not implement until `session_summary` data shows sessions regularly exceed ~40k input tokens.

Rules when implemented:

- trigger only on threshold, not per-turn
- supersession first
- replace tool-result content, never remove envelopes
- log compaction rows with hashes of replaced spans
- never orphan tool calls/results
- never mutate tool payload

### 7. Tier 2.4 — `read_artifact` tool

Status: **DEFERRED**

Add only if metrics or user traces show the model needs to pull elided payloads back into context.

### 8. Tier 7 — broader tool-surface work

Status: **DEFERRED**

- role-scoped frozen tool sets are partially present already
- do not add mid-session dynamic tool toggling
- defer progressive disclosure / dynamic tools until tool count and metrics justify complexity

## Explicitly skipped in the loop-foundation PR

- Compaction
- Assembly middleware
- Cache TTL markers
- `read_artifact`
- Per-category elision
- Summary helper module
- Internal-error traceback relocation

Reason: the foundation PR intentionally landed observability, pairing safety, canonical tools, and projection chokepoint first. Later changes should now be measurable and safer to review.

## Validation baseline from landed PR

Sandbox validation performed during the loop-foundation session:

- full test suite with repo coverage addopts disabled: `1074` tests passing at time of implementation
- ruff clean for touched Python files
- mypy clean for touched Python files/tests

Run full project CI on the host/CI environment before merge, including pytest-cov, Docker compose config, and image build where available.
