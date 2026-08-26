# PR: Automatic Retry on Transient Provider Chain Exhaustion

**Intent:** FIX
**Goal Lens:** Close the operational gap where transient provider failures (e.g., HTTP 502/429) immediately terminate the coding session if no fallback providers are configured.

## Summary

Resolves a brittle failure mode where a single-entry `ProviderChain` throws a `ProviderChainExhaustedError` on the first transient network failure (e.g., `502 Bad Gateway` from Fireworks/OpenRouter). By implementing a non-blocking retry loop within `coder_loop.py`, the harness now intelligently waits out the provider's `cooldown` timer before aborting the entire turn, preserving hours of expensive context.

## Changes

1. **`coder_loop.py` (Local Retry Loop):**
   - Injected a `max_chain_retries = 3` loop inside `drive_session` wrapping `provider_chain.request(request)`.
   - On `ProviderChainExhaustedError`, the loop evaluates `provider_chain.cooldowns`. Instead of immediately returning `exit_code=2` (which discards all session messages), it calculates the shortest active `expires_at` timer across all providers.
   - Triggers a precise `time.sleep(wait_s)`, emitting real-time `OutputEvent(type="api_retry")` logs to the `ConsoleRenderer`, notifying the operator of the delay.
   - If the error persists after 3 retries, the loop breaks and raises the `ProviderChainExhaustedError` up to the standard terminal abort path, fulfilling the `ADR-9` fail-fast semantics safely.

## Subtraction Evaluated
- Removing what makes this redundant: none.
- What capability is lost: immediate aborts on transient drops when operators have not configured fallback providers.
- Open-source agent-stack precedent: automatic backoff/retries on LLM endpoints.
