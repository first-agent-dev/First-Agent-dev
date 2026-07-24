# Provider Runtime, Config, and Cooldown Pipeline

> Codemap ID: `Provider_Runtime_Config_and_Cooldown_Pipeline_20260627_000001`
> **Refreshed 2026-07-24** against ADR-9 §Amendment 2026-07-23 (`models.yaml`
> schema hard-cutover — `slug:` renamed to `model:`, role-level `model:`
> renamed to `name:`, role-level `extras:` moved to per-entry
> `provider_params:`) and against current source for the `transport_retries`
> / default-value claims below, which were stale independent of that
> amendment (confirmed: `transport_retries` was already implemented in
> `UrllibTransport.post()` before this codemap's own original date).

This codemap covers the full provider path from `fa run` down to the HTTP transport and back. It focuses on the parts that matter when debugging `chain_exhausted`, cooldown timing, Fireworks transient failures, `Retry-After`, and the `models.yaml` knobs that influence runtime behavior.

The stack has six layers. The CLI resolves the acting role and loads `~/.fa/models.yaml`. The config loader parses YAML into typed chain objects. The registry maps provider names like `fireworks` to adapter categories. The adapter translates between FA's canonical request/response shape and the provider wire shape. The transport performs the real HTTP call and parses transport-level metadata like `Retry-After`. Finally, `ProviderChain` applies retry classification and cooldown bookkeeping, and `drive_session()` in the inner loop consumes the result.

---

## Component inventory

| Component | File | Role in pipeline |
| --- | --- | --- |
| `load_models_config_from_path()` | `src/fa/providers/config.py` | Reads `~/.fa/models.yaml` and materializes typed per-role config |
| `chain_from_mapping()` | `src/fa/providers/chain.py` | Attaches defaults for optional chain-entry knobs; rejects old (pre-amendment) field names with a migration-hint `ConfigurationError` |
| `ChainEntry` | `src/fa/providers/chain.py` | One provider route row for a role — `model` is the literal string sent as `"model"` to THIS provider; `provider_params` are body fields sent ONLY to this entry |
| `ProviderChain` | `src/fa/providers/chain.py` | Ordered fallback dispatcher + cooldown ledger; builds a PER-ENTRY request (own `model`, own `provider_params`, shared `sampling` defaults) before calling each provider |
| `PROVIDERS` / `build_provider()` | `src/fa/providers/registry.py` | Maps provider names to adapter categories |
| `OpenAICompatProvider` | `src/fa/providers/openai_compat.py` | Adapter for Fireworks and other OpenAI-shaped providers |
| `UrllibTransport` | `src/fa/providers/transport.py` | Production HTTP POST transport — DOES implement `transport_retries` (see Trace 8, corrected) |
| `parse_transport_response()` | `src/fa/providers/base.py` | Maps transport status into canonical success or typed errors |
| `ProviderTransientError` | `src/fa/providers/errors.py` | Carries transient status, kind, and parsed retry hint |
| `drive_session()` | `src/fa/inner_loop/coder_loop.py` | Calls the chain and decides how long to sleep before retrying the logical LLM turn |

---

## Trace 1: `fa run` bootstraps the provider stack

The CLI entrypoint lives in `src/fa/cli.py`. The `run` command resolves `--config`, loads the models file with `load_models_config_from_path()`, selects the requested role such as `planner`, and then constructs a `ProviderChain` for that role. In production wiring it also constructs a `UrllibTransport` and passes it into `build_provider()` so each chain entry can materialize the correct adapter.

This is the stage where `models.yaml` becomes typed runtime state. No network call has happened yet. The output of this stage is a `ChainConfig` containing one or more `ChainEntry` rows.

---

## Trace 2: YAML shape and optional knobs

The required chain-entry fields are `provider`, `model`, `base_url`, and `api_key_env`. (Pre-2026-07-23 field name: `slug` — now rejected at load time with a migration-hint `ConfigurationError` naming the replacement.) In addition, the loader already supports optional knobs even if an older example template omitted them.

The optional per-entry knobs currently supported by `chain_from_mapping()` are `cooldown_seconds`, `timeout_seconds`, `transport_retries`, `extra_headers`, and `provider_params` (provider-specific request-body fields sent ONLY to that entry — e.g. Mistral's `reasoning_effort`; pre-amendment this lived as role-level `extras:`, broadcast to every entry regardless of provider — that broadcast was a bug, not a feature, and is why it moved).

The role level also accepts an optional `sampling:` block (`temperature`, `max_tokens`, `top_p`) — sent identically to every chain entry unless the caller passes an explicit override. This did not exist before the 2026-07-23 amendment; the same three values were previously Python-hardcoded module constants with no `models.yaml`-configurable surface at all.

The defaults are defined in `src/fa/providers/chain.py`:

```python
DEFAULT_COOLDOWN_SECONDS = 15
DEFAULT_TRANSPORT_RETRIES = 2
DEFAULT_TIMEOUT_SECONDS = 300
```

(These values were previously documented here as 90 / 1 / 15 respectively — that was already wrong when this codemap was first written; corrected 2026-07-24 against current source, independent of the schema amendment.)

The loader applies them here:

```python
cooldown_seconds=int(
    row["cooldown_seconds"]
    if row.get("cooldown_seconds") is not None
    else DEFAULT_COOLDOWN_SECONDS
)
transport_retries=int(
    row["transport_retries"]
    if row.get("transport_retries") is not None
    else DEFAULT_TRANSPORT_RETRIES
)
timeout_seconds=int(
    row["timeout_seconds"]
    if row.get("timeout_seconds") is not None
    else DEFAULT_TIMEOUT_SECONDS
)
extra_headers=dict(row.get("extra_headers") or {})
provider_params=dict(row.get("provider_params") or {})
```

That means the YAML contract already accepts these fields today.

---

## Trace 3: What each optional knob means

`cooldown_seconds` is the local cooldown floor configured by the operator. It says how long FA should keep a `(provider, model)` tuple in cooldown after a transient failure if the provider does not demand an even longer delay. (Pre-amendment: `(provider, slug)` — same tuple shape, renamed field.)

`timeout_seconds` is the per-request HTTP timeout passed to the provider adapter and then to the transport.

`transport_retries` IS actively consumed by the current production transport — see Trace 8 below (corrected; a prior version of this codemap claimed otherwise).

`extra_headers` is a mapping of additional HTTP headers to send for that chain entry.

`provider_params` is a mapping of additional request-BODY fields (not headers) sent to that chain entry only — see Trace 2.

---

## Trace 4: Fireworks request path

Fireworks is registered in `src/fa/providers/registry.py` as an OpenAI-compatible provider. That means a Fireworks chain entry does not have its own adapter file. Instead, `build_provider("fireworks", transport=...)` returns `OpenAICompatProvider`.

`OpenAICompatProvider.request()` constructs a `POST` to:

```text
{base_url}/chat/completions
```

It sends the canonical `RequestInfo` fields as an OpenAI-style JSON body and passes the request down to the transport. As of the 2026-07-23 amendment, `RequestInfo.model_slug` for this call is `entry.model` (this specific chain entry's own model string) — never the role's `name` label and never another entry's `model` value.

---

## Trace 5: Where API response data becomes typed runtime state

The production transport lives in `src/fa/providers/transport.py`. `UrllibTransport.post()` performs the actual HTTP call and parses transport-level metadata.

On both success and `HTTPError`, it attempts to parse the `Retry-After` header:

```python
retry_after = _parse_retry_after(response.headers.get("Retry-After"))
```

or:

```python
retry_after = _parse_retry_after(exc.headers.get("Retry-After"))
```

That value is stored in `TransportResponse.retry_after_seconds`. This is runtime data from the API response, not config.

Then `parse_transport_response()` in `src/fa/providers/base.py` maps transport outcomes into typed FA errors. For `429` and `5xx`, it raises `ProviderTransientError` and forwards the parsed retry hint:

```python
raise ProviderTransientError(
    ...,
    retry_after_seconds=response.retry_after_seconds or 0.0,
)
```

So yes, the code already collects retry-hint data from live provider responses and stores it in typed runtime state.

---

## Trace 6: Cooldown computation

The cooldown ledger logic lives in `ProviderChain.request()`.

When a provider adapter raises `ProviderTransientError`, the chain computes:

```python
cooldown_until = max(
    now_after + entry.cooldown_seconds,
    now_after + exc.retry_after_seconds,
)
```

This is the key rule.

`entry.cooldown_seconds` is your local config floor from `models.yaml`.
`exc.retry_after_seconds` is the provider hint parsed from the HTTP response.

The real cooldown is the larger of the two.

This means `retry_after_seconds` is not a YAML field and should not be added to templates as one. It is dynamic response metadata.

The chain stores the result in a `CooldownRow`, keyed on `(provider, model)` (pre-amendment: `(provider, slug)`), including `retry_after_hint_ms`, so later debugging can distinguish a plain local cooldown floor from a provider-supplied retry hint.

---

## Trace 7: Why `retry in 0s` happened before the fix

The provider stack itself was not the root cause of the `retry in 0s` symptom. The provider chain was already creating cooldown rows correctly. The bug was in `src/fa/inner_loop/coder_loop.py`, where the session driver collapsed long waits to `0.01` outside of tests whenever `wait_s > 60`.

That meant the provider ledger could say "this route is cooling down for a while", but the runtime loop would still sleep for almost nothing, retry immediately, and exhaust again.

After the bugfix, the runtime loop respects the real cooldown ledger in production and only uses the near-zero sleep shim under pytest.

---

## Trace 8: What `transport_retries` means today (corrected 2026-07-24)

**A prior version of this codemap claimed `transport_retries` was an unconsumed, aspirational field ("the current stdlib transport does not yet consume this field directly"). This was checked against current source and found to be wrong** — `UrllibTransport.post()` (`src/fa/providers/transport.py`) DOES consume it:

```python
max_attempts = 1 + max(transport_retries, 0)
for attempt in range(max_attempts):
    ...
```

It retries the raw HTTP POST up to `transport_retries` additional times on network-level failure, entirely BELOW the `ProviderChain` cooldown/fallback layer — i.e. `transport_retries` governs retrying the SAME chain entry's SAME request before the chain gives up on that entry and falls through to the next one (or exhausts). This is a genuinely separate retry budget from `ProviderChain`'s cross-entry fallback walk; the two must not be confused when debugging a slow or repeatedly-failing call.

(If you are reading an even older cached copy of this file, or of ADR-9 §9 Q-2's "default v0.1 = 1 transport retry per chain entry" framing, treat both as historical — re-derive from current source before trusting either.)

---

## Minimal single-provider Fireworks policy

For a single-provider Fireworks setup where the goal is short in-loop retries after transient failures, the most important knob is `cooldown_seconds`.

A concise example is:

```yaml
planner:
  name: "glm-5p2"
  family: "glm"
  chain:
    - provider: fireworks
      model: "accounts/fireworks/models/glm-5p2"
      base_url: "https://api.fireworks.ai/inference/v1"
      api_key_env: FIREWORKS_API_KEY
      cooldown_seconds: 3
      timeout_seconds: 15
      transport_retries: 1
```

With that config, if Fireworks returns a transient `502` and does not supply a longer `Retry-After`, the provider entry cools down for about three seconds, and the runtime loop can retry the same logical turn after that short delay. Separately, `transport_retries: 1` means one immediate retry of the same POST happens inside `UrllibTransport` before that cooldown/fallback logic is even reached (see Trace 8).

---

## High-ROI follow-up improvements

The biggest observability improvement would be to surface `retry_after_hint_ms` more explicitly in provider-attempt or live-output rows, so an operator can tell whether a wait came from local config or a provider-supplied header.

`fa routing-check` (added 2026-07-23, `src/fa/providers/routing_lint.py`) now closes one class of `models.yaml` config-authoring error offline: cross-role route conflicts and near-miss `base_url` typos, in well under a second, before any deploy. It does not yet validate `sampling`/`provider_params` content shape — a config-author can still typo a field name inside `provider_params` (e.g. `reasoning_efort`) and it will be silently ignored by the adapter (`body.setdefault(key, value)` accepts any key). This remains an open gap, not covered by this codemap's scope.

BACKLOG `I-32` tracks a related, unimplemented gap: multi-key rotation for the same `(provider, model)` pair is not supported by either the `ProviderChain` cooldown ledger or the egress-proxy `RouteTable`, both of which key on `(provider, model)` alone.

---

## One-line summary

The provider stack already supports configurable cooldown floors, already ingests `Retry-After` from live HTTP responses, already retries the same request at the transport layer via `transport_retries` (a different budget from cooldown/fallback), and — as of 2026-07-23 — each chain entry gets its own `model` string and its own `provider_params`, not the role's shared values.
