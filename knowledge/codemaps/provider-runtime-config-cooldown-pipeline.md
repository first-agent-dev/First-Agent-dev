# Provider Runtime, Config, and Cooldown Pipeline

> Codemap ID: `Provider_Runtime_Config_and_Cooldown_Pipeline_20260627_000001`

This codemap covers the full provider path from `fa run` down to the HTTP transport and back. It focuses on the parts that matter when debugging `chain_exhausted`, cooldown timing, Fireworks transient failures, `Retry-After`, and the `models.yaml` knobs that influence runtime behavior.

The stack has six layers. The CLI resolves the acting role and loads `~/.fa/models.yaml`. The config loader parses YAML into typed chain objects. The registry maps provider names like `fireworks` to adapter categories. The adapter translates between FA’s canonical request/response shape and the provider wire shape. The transport performs the real HTTP call and parses transport-level metadata like `Retry-After`. Finally, `ProviderChain` applies retry classification and cooldown bookkeeping, and `drive_session()` in the inner loop consumes the result.

---

## Component inventory

| Component | File | Role in pipeline |
| --- | --- | --- |
| `load_models_config_from_path()` | `src/fa/providers/config.py` | Reads `~/.fa/models.yaml` and materializes typed per-role config |
| `chain_from_mapping()` | `src/fa/providers/chain.py` | Attaches defaults for optional chain-entry knobs |
| `ChainEntry` | `src/fa/providers/chain.py` | One provider route row for a role |
| `ProviderChain` | `src/fa/providers/chain.py` | Ordered fallback dispatcher + cooldown ledger |
| `PROVIDERS` / `build_provider()` | `src/fa/providers/registry.py` | Maps provider names to adapter categories |
| `OpenAICompatProvider` | `src/fa/providers/openai_compat.py` | Adapter for Fireworks and other OpenAI-shaped providers |
| `UrllibTransport` | `src/fa/providers/transport.py` | Production HTTP POST transport |
| `parse_transport_response()` | `src/fa/providers/base.py` | Maps transport status into canonical success or typed errors |
| `ProviderTransientError` | `src/fa/providers/errors.py` | Carries transient status, kind, and parsed retry hint |
| `drive_session()` | `src/fa/inner_loop/coder_loop.py` | Calls the chain and decides how long to sleep before retrying the logical LLM turn |

---

## Trace 1: `fa run` bootstraps the provider stack

The CLI entrypoint lives in `src/fa/cli.py`. The `run` command resolves `--config`, loads the models file with `load_models_config_from_path()`, selects the requested role such as `planner`, and then constructs a `ProviderChain` for that role. In production wiring it also constructs a `UrllibTransport` and passes it into `build_provider()` so each chain entry can materialize the correct adapter.

This is the stage where `models.yaml` becomes typed runtime state. No network call has happened yet. The output of this stage is a `ChainConfig` containing one or more `ChainEntry` rows.

---

## Trace 2: YAML shape and optional knobs

The required chain-entry fields are `provider`, `slug`, `base_url`, and `api_key_env`. In addition, the loader already supports optional knobs even if an older example template omitted them.

The optional knobs currently supported by `chain_from_mapping()` are `cooldown_seconds`, `timeout_seconds`, `httpx_retries`, and `extra_headers`.

The defaults are defined in `src/fa/providers/chain.py`:

```python
DEFAULT_COOLDOWN_SECONDS = 90
DEFAULT_HTTPX_RETRIES = 1
DEFAULT_TIMEOUT_SECONDS = 15
```

The loader applies them here:

```python
cooldown_seconds=int(
    row["cooldown_seconds"]
    if row.get("cooldown_seconds") is not None
    else DEFAULT_COOLDOWN_SECONDS
)
httpx_retries=int(
    row["httpx_retries"]
    if row.get("httpx_retries") is not None
    else DEFAULT_HTTPX_RETRIES
)
timeout_seconds=int(
    row["timeout_seconds"]
    if row.get("timeout_seconds") is not None
    else DEFAULT_TIMEOUT_SECONDS
)
extra_headers=dict(row.get("extra_headers") or {})
```

That means the YAML contract already accepts these fields today.

---

## Trace 3: What each optional knob means

`cooldown_seconds` is the local cooldown floor configured by the operator. It says how long FA should keep a `(provider, slug)` tuple in cooldown after a transient failure if the provider does not demand an even longer delay.

`timeout_seconds` is the per-request HTTP timeout passed to the provider adapter and then to the transport.

`httpx_retries` is a reserved transport-layer retry knob from ADR-9. The current production transport is `UrllibTransport`, not `httpx`, and the current stdlib transport does not yet consume this field directly. The field remains in the schema so a future transport retry implementation can use it without changing `models.yaml`.

`extra_headers` is a mapping of additional HTTP headers to send for that chain entry.

---

## Trace 4: Fireworks request path

Fireworks is registered in `src/fa/providers/registry.py` as an OpenAI-compatible provider. That means a Fireworks chain entry does not have its own adapter file. Instead, `build_provider("fireworks", transport=...)` returns `OpenAICompatProvider`.

`OpenAICompatProvider.request()` constructs a `POST` to:

```text
{base_url}/chat/completions
```

It sends the canonical `RequestInfo` fields as an OpenAI-style JSON body and passes the request down to the transport.

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

The chain stores the result in a `CooldownRow`, including `retry_after_hint_ms`, so later debugging can distinguish a plain local cooldown floor from a provider-supplied retry hint.

---

## Trace 7: Why `retry in 0s` happened before the fix

The provider stack itself was not the root cause of the `retry in 0s` symptom. The provider chain was already creating cooldown rows correctly. The bug was in `src/fa/inner_loop/coder_loop.py`, where the session driver collapsed long waits to `0.01` outside of tests whenever `wait_s > 60`.

That meant the provider ledger could say “this route is cooling down for a while”, but the runtime loop would still sleep for almost nothing, retry immediately, and exhaust again.

After the bugfix, the runtime loop respects the real cooldown ledger in production and only uses the near-zero sleep shim under pytest.

---

## Trace 8: What `httpx_retries` means today

The name is historical. It came from ADR-9’s transport design, where per-entry transport retries were expected to be a transport concern and to happen before the chain falls through to the next provider.

Today, the production transport is `UrllibTransport`, which does not yet implement a retry loop keyed off `httpx_retries`. So this field is best understood as part of the accepted config schema and future transport contract, not as an actively consumed runtime knob in the current stdlib transport.

This is a documentation and naming debt worth cleaning up later. The highest-ROI cleanup would be either renaming the field to a transport-neutral name like `transport_retries`, or implementing the missing transport retry behavior and keeping a backward-compatible alias.

---

## Minimal single-provider Fireworks policy

For a single-provider Fireworks setup where the goal is short in-loop retries after transient failures, the most important knob is `cooldown_seconds`.

A concise example is:

```yaml
planner:
  model: "glm-5p2"
  family: "glm"
  chain:
    - provider: fireworks
      slug: "accounts/fireworks/models/glm-5p2"
      base_url: "https://api.fireworks.ai/inference/v1"
      api_key_env: FIREWORKS_API_KEY
      cooldown_seconds: 3
      timeout_seconds: 15
      httpx_retries: 1
```

With that config, if Fireworks returns a transient `502` and does not supply a longer `Retry-After`, the provider entry cools down for about three seconds, and the runtime loop can retry the same logical turn after that short delay.

---

## High-ROI follow-up improvements

The biggest documentation debt in this module is the name `httpx_retries`. It suggests a behavior that the current stdlib transport does not visibly implement. That makes debugging harder and can mislead operators into believing the production transport already performs per-entry HTTP retries.

The biggest observability improvement would be to surface `retry_after_hint_ms` more explicitly in provider-attempt or live-output rows, so an operator can tell whether a wait came from local config or a provider-supplied header.

Another high-ROI improvement would be to add a first-party template or comments block for `models.yaml` that documents all supported optional knobs in one place, because the loader already supports more than the minimal examples show.

---

## One-line summary

The provider stack already supports configurable cooldown floors, already ingests `Retry-After` from live HTTP responses, and the practical knob that matters for your current single-provider Fireworks retry behavior is `cooldown_seconds`, not `httpx_retries`.
