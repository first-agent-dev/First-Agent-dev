# Mistral API Compatibility — Implementation Notes

**Date**: 2026-07-19
**Scope**: Add Mistral API support to FA's provider chain

## Review Suggestions Analysis

The user received three review suggestions. Here's how each was addressed:

### 1. "Требует перехода на /v1/conversations + Agents API"

**Reviewer's claim**: Your harness goes to `/v1/chat/completions`, they won't let you in.

**Assessment**: **Partially incorrect.** Mistral's `/v1/chat/completions` endpoint is fully production-ready and functional. The suggestion that "they won't let you in" is wrong — Mistral actively supports and documents the chat completions endpoint.

**However**, the reviewer is correct that:
- Built-in tools (`web_search`, `code_interpreter`, `document_library`) ONLY work via the Conversations/Agents API (`/v1/conversations`)
- `document_library` would be ideal for the 28K document use case — upload once, reference by ID

**Implementation**:
- `MistralProvider` (adapter=`mistral`) → uses `/v1/chat/completions` — covers the majority of use cases
- `MistralConversationsProvider` (adapter=`mistral_agents`) → uses `/v1/conversations` — covers built-in tools
- Both are registered in the provider registry and can coexist in a models.yaml

### 2. "prediction" Field Usage

**Reviewer's correction**: The `prediction` field should contain the *expected output*, NOT the input document.

**Original (incorrect) schema**:
```yaml
prediction:
  type: "content"
  content: "{{LONG_DOC_PLACEHOLDER}}"  # ← This is the input document!
```

**Correct pattern**:
```yaml
prediction:
  type: "content"
  content: "Old summary text here"  # ← Expected output (500 tokens)
# Meanwhile, the 28K input document goes in messages via prompt composer
```

**Implementation**:
- `_apply_prediction()` validates the prediction field and **warns when content exceeds 8192 chars** (heuristic for likely misuse)
- The warning explicitly says: "this field should contain the EXPECTED OUTPUT, NOT the input document"
- The prompt composer puts the input document in `messages` as normal
- `prompt_cache_key` handles caching of the large input document

### 3. Built-In Tools

**Reviewer's suggestion**: Use `document_library` for the 28K document.

**Assessment**: Valid for a document-heavy use case. `document_library` allows uploading the document once and referencing it by ID — no need to re-send the full 28K on every request.

**Implementation**:
- `MistralConversationsProvider` supports `mistral_tools` in extras
- Built-in tools are specified as:
  ```yaml
  extras:
    mistral_tools:
      - type: web_search
      - type: document_library
  ```
- Tool executions and references are captured in `ResponseInfo.extras`
- NOTE: The Conversations API is in beta; the adapter follows the documented shapes but may need updates as the API stabilizes

## Architecture

### Provider Hierarchy

```
Provider (Protocol)
├── OpenAICompatProvider   → /chat/completions (generic OpenAI-compatible)
├── AnthropicProvider      → /v1/messages (Anthropic native)
├── MistralProvider        → /chat/completions (Mistral-specific fields)
└── MistralConversationsProvider → /v1/conversations (built-in tools)
```

### Why a Separate MistralProvider (not just OpenAICompat)?

Mistral's chat completions endpoint IS OpenAI-compatible at the wire level. The generic `OpenAICompatProvider` already forwards all `request.extras` to the body. So why create a separate adapter?

1. **Validation**: `_apply_prediction()` validates prediction field usage and warns on likely misuse
2. **Auto-strict**: `_apply_response_format()` auto-adds `strict: true` for `json_schema` (100% vs 64% conformance)
3. **Discovery**: A dedicated adapter makes Mistral-specific features discoverable via code, docs, and registry
4. **Forward-compatibility**: Mistral may add more chat completions-specific fields that need structured handling
5. **Response parsing**: Captures `prediction_tokens` from usage for predicted output metrics

### Extras Pipeline

```
models.yaml (role-level extras)
    ↓ chain_from_mapping()
ChainConfig.extras: Mapping[str, Any]
    ↓ coder_loop.py (merge with prompt-composer extras)
RequestInfo.extras: Mapping[str, Any]
    ↓ MistralProvider.request()
_build_request_body() → validates + structures
    ↓ HTTP POST
Mistral API /v1/chat/completions
```

### Key Design Decisions

1. **ChainConfig.extras is merged AFTER prompt-composer extras** — role-level config wins on key conflict (user's explicit config > algorithmic defaults)

2. **prediction validation is a WARNING, not an error** — the heuristic (8192 char threshold) may have false positives; better to warn and continue than to block a valid use case

3. **json_schema strict auto-added** — Mistral's own docs and pydantic-ai stress tests show 100% vs 64% conformance; `strict: true` is the safe default, with `strict: false` available for explicit opt-out

4. **Conversations API uses separate provider name** (`mistral_agents`) — the request/response shapes are fundamentally different from chat completions; mixing them in one adapter would violate the single-responsibility principle

5. **Family extraction supports all Mistral model families** — `mistral-*`, `codestral-*`, `ministral-*`, `magistral-*` all extract to family `mistral`

## Files Changed

| File | Change |
|------|--------|
| `src/fa/providers/mistral.py` | NEW: MistralProvider adapter |
| `src/fa/providers/mistral_conversations.py` | NEW: Conversations API adapter |
| `src/fa/providers/registry.py` | Added `mistral` + `mistral_agents` providers |
| `src/fa/providers/chain.py` | Added `extras` field to `ChainConfig` + `chain_from_mapping` |
| `src/fa/providers/__init__.py` | Exported new adapters |
| `src/fa/inner_loop/coder_loop.py` | Merge ChainConfig.extras into RequestInfo.extras |
| `src/fa/roles.py` | Added `mistral` to KNOWN_FAMILIES + regex patterns |
| `tests/fixtures/session_wiring.py` | Added `extras` to `make_mock_chain` |
| `tests/test_roles.py` | Updated for Mistral family |
| `tests/test_mistral_provider.py` | NEW: 33 tests |
| `tests/test_mistral_conversations_provider.py` | NEW: 18 tests |
| `tests/test_mistral_integration.py` | NEW: 20 tests |
| `src/fa/providers/examples/models-mistral.yaml` | NEW: Sample config |

## Test Coverage

- **33 tests** for MistralProvider (request body, prediction validation, response format, response normalization, error mapping, registry)
- **18 tests** for MistralConversationsProvider (request body, built-in tools, response normalization, error mapping, URL)
- **20 tests** for integration (ChainConfig.extras, family extraction, config loader)
- **Total: 71 new tests** — all pass

## Usage

```yaml
# ~/.fa/models.yaml
planner:
  model: "mistral-medium-2604"
  family: "mistral"
  chain:
    - provider: mistral
      slug: "mistral-medium-2604"
      base_url: "https://api.mistral.ai/v1"
      api_key_env: MISTRAL_API_KEY
  extras:
    prompt_cache_key: "planner-v1"
    reasoning_effort: "high"
    response_format:
      type: "json_schema"
      json_schema:
        name: "summary"
        schema:
          type: "object"
          properties:
            points: {type: "array", items: {type: "string"}}
          required: ["points"]
    prediction:
      type: "content"
      content: "Previous summary here"  # expected output, NOT input doc!
```
