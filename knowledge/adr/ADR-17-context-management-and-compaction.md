# ADR-17 — Context Management & Compaction

- **Status:** proposed
- **Date:** 2026-07-14
- **Deciders:** Senior Systems Engineering Team & LLM Harness Architects

## Context

As First-Agent sessions grow in length, active context sizes can quickly exceed physical model context windows (typically 128k to 200k tokens) or degrade the model's reasoning capabilities well before hard limits are met.

Specifically:
1.  **Reasoning and Chain-of-Thought (CoT) Degradation:** Empirical evidence (*modarressi2025nolima*) shows that highly complex, multi-step logical reasoning and Chain-of-Thought (CoT) generation begin to degrade significantly as the active context window fills with distractor tokens—often starting as early as **1k to 8k tokens**.
2.  **Long-Context Code Reading Resilience:** In contrast, models can tolerate much larger filled contexts (up to **100k to 150k tokens**) during retrieval-heavy, passive tasks like code reading and repository navigation.
3.  **Instruction following Decline:** Beyond **150k to 200k tokens**, even elite frontier models (such as Claude 3.5 Sonnet) begin to exhibit noticeable degradation in strict instruction following and constraint adherence.
4.  **Governance Decay (Instruction Erasure):** Standard rolling compactions drop standing system instructions (such as `AGENTS.md` and role profiles) because they appear with low frequency in rolling conversations. This causes policy violation rates to jump from 0% to up to 59% (*2606.22528v2*).
5.  **Prompt-Cache Invalidation:** Compacting context dynamically on every turn alters prompt prefixes, completely invalidating the provider's prompt cache and causing 100% of the input context to be re-processed and billed, violating **Pillar 3 (Token Efficiency)**.
6.  **Proprioceptive Blindness:** Models are unable to see their own context size, remaining blind to context pressure until they hit hard truncation limits (*2606.30005v1*).

We need a structured, deterministic-first context management and compaction architecture that is cost-efficient, guarantees policy survival, maintains cache hit rates above 90%, and is model-aware.

---

## Options Considered

### Option A — Pure Conversational Compaction (Rolling Window / Sliding History)
Discard older messages or invoke an LLM summarizer to compress the entire history into a single paragraph whenever the context limit is approached.

*   **Pros:**
    *   Extremely simple to implement; requires no custom state tracking.
*   **Cons:**
    *   **Governance Decay:** High risk of the model forgetting critical standing policies (like path allowed lists, sandbox rules, and formatting rules).
    *   **Token-Inefficient:** LLM-based summarization calls are slow, expensive, and invalidate prompt caches on every turn.
    *   **Summary Rot:** Important file paths, previous trial outcomes, and errors are summarized out, causing the model to stall or repeat mistakes.

### Option B — Decoupled, Multi-Tiered "Memory" OS-Kernel & Progressive Compaction (Recommended)
Model the active context window as an Operating System Virtual Memory Page Table, separating state into different fidelity tiers:
1.  **FULL Resident Pages (PinnedBuffer):** ALWAYS exempt from compaction and re-injected verbatim, verified by SHA-256 content hashes (protects standing rules, `AGENTS.md`, and profiles).
2.  **COMPRESSED Pages (Observation Masking):** Large tool output payloads (>200 chars) outside a 4-turn active tail window are automatically replaced with a non-LLM, content-addressed reference pointer `[Omitted tool result of X lines, artifact_id = ...]`. Payload stays retrievable from SQLite `session.db` and the `ArtifactStore`.
3.  **STRUCTURED Pages (LLM Handoff Summary):** A dense status summary under 4 headers (`PREVIOUSLY`, `PARKED`, `CURRENT`, `NEXT ACTION`) with explicit `path:line-range` file-verbatim references, executed via a low-cost, dedicated `compactor` role model.
4.  **Prompt-Cache Anchoring:** Segmenting prompts using Claude-aligned breakpoints so that immutable sections remain permanently cached (preserving a 94%+ hit rate).
5.  **Model-Aware & Dynamic Thresholds:** Under our mixed-tier architecture, a smaller local model (e.g. Qwen-Coder 32B) may begin to degrade in instruction following past 16k-32k tokens, while an elite model (e.g. Claude 3.5 Sonnet) can maintain high-fidelity reasoning up to 150k-180k tokens. Hardcoding a single threshold is unsafe; we must allow configuring threshold per model role in `models.yaml`, defaulting dynamically to `min(80% of context_limit, 150k)` if unset.

*   **Pros:**
    *   **0% Governance Decay:** Verbatim pinning of constraints guarantees policy compliance across compactions.
    *   **High Performance:** Reduces costs by up to 90% via cache anchoring, and halves context size without any LLM API costs through deterministic observation masking.
    *   **Proprioceptive Awareness:** Injecting a context dashboard gives the model self-knowledge of its token usage, access histories, and remaining budget.
    *   **Model-Aware Flexibility:** Smaller local models are protected from context-blindness degradation, while elite long-context models are permitted to utilize their full reasoning scale.
*   **Cons:**
    *   Slightly higher codebase complexity (adding 4 deterministic modules).

---

## Decision

We will choose **Option B** because it is the only architecture that mathematically resolves **Governance Decay**, guarantees a **94%+ prompt cache hit rate** under context pressure, and strictly follows the **Minimalism-First (§1.2)** and **Compliance-by-Construction (§1.2.5)** principles by using deterministic Python operations (masking/pinning) before resorting to expensive LLM-based compaction.

---

## Consequences

*   **Positive:**
    *   Safeguards standing safety constraints (ConstraintRot) at a negligible cost of `<0.5%` of the context window.
    *   Prevents context overflows and infinite "doom-looping" compactions via a 3-strike circuit breaker.
    *   Drastically reduces prompt processing bills by up to 90% via separate cache-control breakpoints.
    *   Allows smaller local models and elite long-context models to each run at their optimal reasoning capacities.
*   **Negative:**
    *   Adds 4 new deterministic Python modules (`context_budget`, `pinned_buffer`, `compactor`, and prompt composer dashboard extensions).
*   **Follow-Up Work:**
    *   Define the `compactor` role in `models.yaml`.
    *   Implement Stage C modules and wire them into `drive_session()` within `src/fa/inner_loop/coder_loop.py`.

---

## References

1.  *ClawVM (2604.10352v1)*: Virtual memory page-table model for LLM context.
2.  *Governance Decay (2606.22528v2)*: Shows pinning standing instructions restores policy compliance to 100%.
3.  *VISTA (2606.30005v1)*: Untrained proprioceptive dashboards increase long-context browse scores.
4.  *Complexity Trap (2508.21433)*: Deterministic observation masking halves execution costs.
