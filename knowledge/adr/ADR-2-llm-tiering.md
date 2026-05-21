# ADR-2 — LLM tiering & access

- **Status:** accepted
- **Date:** 2026-04-27
- **Deciders:** project owner (`0oi9z7m1z8`), Devin (drafting)

## Context

FA's value proposition (see
[`project-overview.md`](../project-overview.md) §1) includes
**routing different agent roles to different LLM tiers** instead of
defaulting one model to everything. The user has stated a budget
mix of approximately:

- 60 % top-tier OSS (GLM 5.1 / Kimi 2.6 / Xiaomi Mimo 2.5)
- 30 % mid-tier OSS (Nemotron 3 Super / Qwen 3.6 27B)
- 10 % elite (Anthropic Claude latest available)

We need to decide **how roles map to tiers**, **how access is
configured**, and **what fallback behaviour** is acceptable.

User answers in PR-#17 follow-up (Q2 + Q3):

- Q2 (role routing): "Multi-LLM static routing: Planner=top-tier OSS,
  Coder=mid-tier OSS, Debug/elite=Claude — config-driven, всегда так."
- Q3 (access): "Mix: per-model в config (некоторые local, некоторые
  через OpenRouter, elite через Anthropic)."

## Options considered

### Option A — Single-LLM, role by prompt

- Pros: simplest; one provider; predictable cost.
- Cons: cannot leverage tier mix; loses FA's stated value.

### Option B — Static role routing (chosen)

Each role pinned to a tier in config; never auto-escalates.

- Pros:
  - Predictable cost: a Coder turn never silently calls Anthropic.
  - Predictable behaviour: same role + same input → same provider.
  - Simple to debug — rerun a turn against its known tier.
- Cons:
  - No graceful degradation when the pinned model is down (must be
    handled by per-role fallback chain in config).
  - Hard tasks routed to Coder fail loudly instead of escalating.
    User-stated preference accepts this.

### Option C — Hybrid dynamic routing with hard-task detector

Mid-tier by default, escalate to top-tier or elite on a detector
signal (e.g. complexity heuristic, stuck-loop detector).

- Pros: cost-optimised; auto-recovery for hard cases.
- Cons: detector reliability is a research problem of its own; not
  appropriate for v0.1; costs become unpredictable.

## Decision

We will choose **Option B (static role routing)** with the following
concrete mapping for v0.1:

| Role | Tier | Default model | Provider |
|---|---|---|---|
| **Planner** | top-tier OSS | GLM 5.1 (or Kimi 2.6 / Mimo 2.5 — config-pickable) | AnyProvider API key / OpenRouter |
| **Coder** | mid-tier OSS | Nemotron 3 Super (or Qwen 3.6 27B) | AnyProvider API key / OpenRouter |
| **Debug / elite** | top tier | DIFFERENT top-tier OSS / top tier from AnyProvider API key | AnyProvider API key / OpenRouter |
| **Eval (LLM-as-judge)** | top-tier OSS | DIFFERENT model ; isolated config slot so judge can be version-pinned | AnyProvider API key / OpenRouter |

Configuration lives in a single YAML/TOML file (e.g.
`~/.fa/models.yaml`) with one block per role:

```yaml
planner:
  primary:   { provider: openrouter, model: "z-ai/glm-5.1" }
  fallback:  { provider: AnyProvider, model: "GLM-5.1-Air" }
coder:
  primary:   { provider: AnyProvider, model: "Nemotron-3-Super-49B" }
  fallback:  { provider: openrouter, model: "qwen/qwen3-coder-27b" }
debug:
  primary:  { provider: any, model: "claude-opus-4-7-20260301" }
  fallback: { provider: any, model: "claude-sonnet-4-7-20260301" }
judge:
  primary: { provider: openrouter, model: "z-ai/kimi 2.6", pinned: true }
```

> **Note on model slugs.** The strings above (`z-ai/glm-5.1`,
> `claude-opus-4-7-20260301`, etc.) are illustrative of the
> *shape* of the config, not authoritative slugs at any given
> date. Provider catalogs change; pick the actual current slug
> from OpenRouter / Anthropic / vLLM at config time. The
> *decision* is the table above (which tier each role lives in
> and how `primary → fallback` chains); the *implementation*
> resolves slugs to whatever is current.

- "primary → fallback" chain per role; **no cross-tier escalation**
  on failure.
- Anthropic is the only mandatory remote in v0.1 (for Debug). Coder
  is preferentially local (vLLM); Planner can be either. This matches
  the user's "remote API ≈ 99 %" tolerance while leaving headroom
  for local-only Coder if vLLM is configured.

## Consequences

- **Positive:** Cost predictability — a Coder turn cannot silently
  hit Anthropic. Token-efficiency metric in
  [`project-overview.md`](../project-overview.md) §3 becomes
  meaningful.
- **Positive:** Per-role evaluation is straightforward — swap one
  block of config to A/B-test models on a role.
- **Positive:** The `judge:` role being version-pinned mitigates
  R5 (eval baseline drift) from `project-overview.md` §7.
- **Negative:** No auto-escalation means a Coder failure on a hard
  task surfaces as a hard error; the **user must explicitly invoke
  Debug** (or rewrite the prompt). v0.2 may revisit this if the
  pattern shows real friction.
- **Negative:** Three providers (Anthropic + OpenRouter + local vLLM)
  triples auth surface area and failure modes (R3 in
  `project-overview.md` §7). Mitigated by per-role fallback chain.
- **Follow-up work this unlocks:**
  - `src/fa/llm/router.py` — minimal role-based dispatcher reading
    `~/.fa/models.yaml`.
  - Provider adapters: `provider_client.py`, `openrouter_client.py`,
    `vllm_local_client.py` (one thin wrapper per provider).
  - Secrets policy: `~/.fa/secrets.env` (chmod 600), never committed.
  - Decision deferred to a future ADR: how to express token / cost
    budgets per role in the same config.

## Amendments

### Amendment 2026-04-29 — `tool_protocol` field + native-by-default; v0.1 inner-loop without Critic

**Source.** Cross-reference review
[`research/cross-reference-ampcode-sliders-to-adr-2026-04.md`](../research/cross-reference-ampcode-sliders-to-adr-2026-04.md)
§3.3, §9.6, §10 R-1 / R-7 — the ADR's per-role `primary →
fallback` chain does not specify how the tools are wired into
each model. Native-tool models (Anthropic, OpenAI, Qwen 3.6,
Kimi 2.6, GLM-5.1) and prompt-only models accept tool calls in
**different shapes**. A silent fallback from native to
prompt-only would break the inner-loop. The user has confirmed
that the current model picks (Qwen 3.6 / Kimi 2.6 / Claude
latest) all support native tool-calling, so native is the
default.

Independently, ADR-2 §Decision lists Planner / Coder / Debug /
Eval but does not name a separate **Critic / Reflector** role.
[`research/agent-roles.md`](../research/agent-roles.md) §5.1
proposes Planner / Executor / Critic as the minimum trio.
Cross-reference §3.4 / §9.7 confirm v0.1 explicitly does
**not** include a Critic (no reflection / self-correction loop).
Eval (offline LLM-as-judge) is not a Critic — it judges
finished work, not in-loop turns. This amendment fixes the
terminology so a v0.2 implementer does not silently introduce a
Critic.

**Decision (additive to the original Decision section).**

1. **`tool_protocol` field per-role in `~/.fa/models.yaml`.**
   Allowed values: `native` | `prompt-only`. Default for **any
   role that calls tools** is `native`. Default for the `judge`
   role (LLM-as-judge, no tool calls) is irrelevant — set to
   `native` for shape consistency, the inner-loop ignores it.

   ```yaml
   coder:
     primary:   { provider: AnyProvider, model: "Nemotron-3-Super-49B", tool_protocol: native }
     fallback:  { provider: openrouter, model: "qwen/qwen3-coder-27b", tool_protocol: native }
   ```

2. **No mixing of `native` and `prompt-only` within a single
   role's `primary → fallback` chain.** The `models.yaml` loader
   enforces this at startup; mixed configurations are a hard
   error, not a warning. Rationale: silent shape changes mid-
   session corrupt the conversation accumulator (see ADR-3
   `hot.md` invariant).

3. **Loop adapts to the role's `tool_protocol`, not to the
   model.** This isolates the tool-shape decision from model
   choice — swapping `coder.primary` to a different native model
   is one-line; switching the whole role to `prompt-only` is
   one-line; mixing within a chain is forbidden.

4. **`prompt-only` is supported but not used in the v0.1
   reference config.** Kept as an option for forks that pin to
   models without native tool-calling (older OSS releases, some
   self-hosted vLLM models). Implementation must include the
   prompt-only path so swapping is config-only, never code.

5. **v0.1 inner-loop has no Critic / Reflector role.** The roles
   are exactly: Planner, Coder, Debug (manual escalation only —
   see original `## Consequences` §«No auto-escalation»), Eval
   (offline judge, out-of-band). Reflection / self-correction
   loops are **v0.2** material; design is in-flight (user note,
   Apr 2026) and will land as a separate ADR. The ADR-2
   no-auto-escalation clause means "no cross-tier escalation",
   not "no intra-role retry-loop"; an intra-role retry-loop
   (e.g. Coder retrying after a failed `edit_file` validation)
   stays allowed in v0.1 — see cross-reference §9.7.

**Notes.**

- The `tool_protocol` field is consumed by `src/fa/llm/router.py`
  + the inner-loop module specified in
  [ADR-7](./ADR-7-inner-loop-tool-registry.md). The implementer
  may stub a single `native`-only inner-loop and mark
  `prompt-only` as `NotImplemented`; the field still goes into
  the schema so the config never has to be re-written. ADR-7
  §Consequences notes that prompt-only adapters MUST translate
  to the same internal `request` / `response` shape pinned in
  this ADR §Amendment 2026-05-01.
- Verified model coverage (user, Apr 2026): Qwen 3.6, Kimi 2.6,
  GLM 5.1, Claude latest, Nemotron 3 Super — all native-tool.
  Mid-tier OSS prompt-only fallbacks remain possible for
  budget-constrained forks.

**Consequence.** `models.yaml` schema gains a required
`tool_protocol` field per role (with `native` as the default if
unset, to keep current configs valid). The validator added in
the implementation PR refuses `primary` and `fallback` blocks
that disagree on `tool_protocol`. Rejecting the config at startup
is a hard error: this matches the original ADR's "fails loudly"
posture for hard-task escalation.

## Amendment 2026-05-01 — MCP forward-compat tool-shape convention

**Context.** Three independent sources surveyed in
[`research/semi-autonomous-agents-cross-reference-2026-05.md`](../research/semi-autonomous-agents-cross-reference-2026-05.md)
§2.3-A and §3.3-B (deep-research-report on agent
architectures, semi-autonomous-agents research, and the
`nextlevelbuilder/goclaw` README) call the **Model Context
Protocol (MCP)** the de-facto industry standard for the
agent ↔ tools boundary as of 2026. MCP defines a
JSON-RPC-shaped contract between an MCP host (the agent)
and one or more MCP servers (which expose tools, resources,
and prompts).

The original Decision and the 2026-04-29 amendment fix the
agent ↔ LLM contract (`tool_protocol: native | prompt-only`).
They say nothing about the **agent ↔ tools** contract — i.e.
how the inner-loop calls a tool function, whether locally
in-process or eventually via an MCP server. Without this
explicit convention, the inner loop now pinned by
[ADR-7](./ADR-7-inner-loop-tool-registry.md) might have
designed a tool-shape that is **not** JSON-RPC-shaped, which would force
re-design when v0.2 wants to expose internal tools as MCP
servers (so other MCP hosts — Claude Desktop, third-party
agents — can use them, or so heavy tools like `mcp-runner` /
`mcp-web` can be moved to separate processes).

This amendment fixes the convention now, at zero
implementation cost, because native function-calling APIs
(Anthropic, OpenAI, Qwen-native) already deliver
JSON-shaped tool inputs and outputs.

**Decision (additive to the original Decision section and
the 2026-04-29 amendment).**

1. **MCP-shaped tool signatures.** All v0.1 tools — including
   the in-process Python functions used by the inner-loop —
   expose a JSON-RPC-shaped surface:

   ```text
   request:  { name: str, params: dict[str, Any] }
   response: { result: Any | None, error: { code: str | int, message: str } | None }
   ```

   Tools are invoked through a single dispatcher that
   accepts and returns these shapes; tool-specific Python
   code does not appear in the LLM-facing protocol. Tool
   parameters are described by **JSON Schema** (parsed from
   Python type hints + Pydantic models or hand-written),
   which is the MCP-spec shape. Tool errors carry a `code`
   field (see §4 dual-mode below — `str` internally for
   agent ergonomics, `int` on the JSON-RPC wire) and a
   string message, matching JSON-RPC `error` semantics.

2. **Stable tool-name policy.** Tool names are stable strings
   (`repo.read`, `repo.search`, `git.status`, …) — not
   Python function objects. Renaming a tool is a v-bump
   event (semantic versioning of the tool catalogue). This
   matches the way MCP servers identify tools by name.

3. **No `mcp` package dependency in v0.1.** This amendment
   defines a **convention**, not a dependency. The agent does
   not `pip install mcp` in v0.1; it implements an in-process
   dispatcher whose **shape** is MCP-compatible. Adding the
   real `mcp` Python package, spawning external mcp-servers,
   exposing internal tools as remote MCP services, etc. — all
   v0.2 work, gated by a follow-up ADR.

4. **Inner-loop ADR** inherits the convention. ADR-7's tool-registry contract uses
   this request/response shape (§2 ToolSpec / ToolResult).
   The ADR-7 author MAY add fields (e.g. an id for streaming tool-calls, a metadata block)
   but MUST NOT change the existing two fields (name, params for request; result, error for response)
   without a separate amendment to this ADR-2. Tool errors match JSON-RPC error semantics,
   carrying a string message and a code field that operates in a dual-mode approach:
   ADR-7 agents internally produce and consume the code as ergonomic domain-specific strings
   (str, e.g., "invalid_params", "sandbox_deny", "no_unique_match"),
   while the JSON-RPC wire format requires standard integers (int).
   To preserve wire compatibility while improving agent-facing error handling,
   implementations MUST map between these str and int representations at the transport boundary.

5. **`tool_protocol` field semantics extended.** The existing
   `tool_protocol: native | prompt-only` field per role
   (2026-04-29 amendment) describes only the **agent ↔ LLM**
   side. The **agent ↔ tools** side is fixed by this
   amendment as JSON-RPC-shaped regardless of `tool_protocol`
   value. A `prompt-only` role still emits JSON-shaped
   tool-calls (just embedded in text it has to parse) and
   the dispatcher still receives JSON-shaped requests.

**Notes.**

- This amendment is a **forward-compat convention**, not a
  constraint that changes any v0.1 implementation surface
  visible to the user. The tool-call cost is zero new code:
  every native function-calling provider (Anthropic, OpenAI,
  Qwen-native, Kimi, GLM, Nemotron) already produces
  JSON-shaped tool-call objects, and any prompt-only
  fallback would have to parse JSON from the LLM output
  anyway.
- The MCP spec (`https://modelcontextprotocol.io`) is still
  evolving (transport layer changes between 2024 and
  2025-2026 — added HTTP+SSE alongside STDIO). Pinning to a
  specific transport in v0.1 would be premature; we only
  pin to **shape**.
- ADR-6 sandbox check is the canonical pre-tool hook in this
  shape: it intercepts the dispatcher's request, validates
  the path argument against the allow-list, and either
  forwards the request or returns an `error` response. This
  is the same shape ADR-7 will use when it formalises
  hooks (cross-reference R-1 input from 2026-05-01 note
  §7.1).

**Consequence.** Tool registry implementation (deferred to
ADR-7 / Phase M PR) must produce a JSON-RPC-shaped dispatcher
even though tools are in-process Python functions in v0.1.
This costs no extra code (native function-calling produces
the right shape natively), buys zero v0.1 user-visible
features, and keeps v0.2 MCP-server distribution as a
config-only / wrapper-only change.

### Amendment 2026-05-20 — Eval-role family-disjoint + primary-source citation

**Source.** Implementation roadmap
[`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
§R-19 / §R-27 part 1 (Wave 0, docs + cheap impl). Primary-source
evidence: correlated-LLM-errors note
[`research/correlated-llm-errors-and-ensembling-2026-05.md`](../research/correlated-llm-errors-and-ensembling-2026-05.md)
§0 R-1 / §3 / §6 R-1 / R-2 (Cornell P-1: Kim, Garg, Peng, Garg,
ICML 2025; Simula P-2: Vallecillos-Ruiz, Hort, Moonen, 2026 —
same-family ensembles show `ρ̂ ≈ +0.6` correlated errors; cross-
family ensembles show `ρ̂ ≈ −0.05`).

**Problem.** The original Decision (table line «Eval — local
hosted») and the §Amendment 2026-04-29 «no cross-tier auto-
escalation» rule both rely on the **assumption** that the Eval-
role check is independent of the Planner / Coder roles it
evaluates. This independence is silent in v0.1 because Eval is
still a one-line «output looks plausible?» check — but the
moment a real Eval role lands (ADR-7 Phase M), a same-family
choice (e.g. Planner=`glm-4.5-air`, Coder=`glm-4.5`,
Eval=`glm-4.5-air-thinking`) would replicate the **same** error
the acting-role made. The §«No cross-tier auto-escalation»
rule has only Ampcode/sliders as cited rationale, no primary-
source academic citation; weaker OSS LLMs (DeepSeek 4 / Kimi
2.6) discount the rule without one.

**Decision (additive to §Decision routing table; no shape change
to §Consequences / §Amendment 2026-04-29 / §Amendment 2026-05-01
/ §Amendment 2026-05-12).**

1. **Eval-role MUST be from a provider+family disjoint from
   Planner and Coder.** «Family» is interpreted at the
   training-distribution level: `glm-*`, `qwen*`, `deepseek-*`,
   `kimi-*`, `mimo-*`, `claude-*`, `gpt-*`, `gemini-*` are
   each separate families. The current FA workload (95% on
   Chinese-OSS LLMs from independent labs — see
   [`project-overview.md` §6](../project-overview.md))
   already satisfies this naturally; the rule is captured
   here so a future tier-bump (e.g. swapping Eval to a Qwen
   variant when Coder is also Qwen) cannot regress silently.
2. **Family extraction = regex slug pattern.** First-pass
   inference uses model-slug regex (`^glm-` → `glm`,
   `^qwen` → `qwen`, `^claude-` → `claude`, etc.); ambiguous
   slugs (e.g. `local-llama-finetune`) MUST be tagged in
   `~/.fa/models.yaml` with an explicit `family:` field. The
   regex extractor lives in the inner-loop scaffolding PR
   (HANDOFF §Next steps item 1) at ~30 LOC; «default-deny
   when family unknown» is the behaviour, matching ADR-6's
   sandbox stance.
3. **Primary-source citation strengthens «no cross-tier auto-
   escalation».** Per R-27 part 1: the §Decision /
   §Amendment 2026-04-29 «no auto-escalation» rule now
   cites Cornell P-1 (Kim et al. ICML 2025) + Simula P-2
   (Vallecillos-Ruiz et al. 2026) as primary sources. The
   original rationale was Ampcode/sliders (§Cross-reference)
   — sufficient for the elite-tier targeting it but not for
   FA's multi-tier scope. The new citations document the
   **mechanism**: same-family models share training-
   distribution biases; an auto-escalation across same-family
   tiers replicates the bias instead of decorrelating it.
   `ρ̂ ≈ +0.6` for same-family ensembles vs `ρ̂ ≈ −0.05`
   for cross-family — this is the quantitative anchor the
   Ampcode citation lacked.
4. **Cross-link to ADR-7 §Amendment 2026-05-20 rule 4.** The
   §8 Hook pipeline gains a parallel rule: «LLM-using hooks
   MUST use family ≠ acting-role». The two rules together
   make ADR-2's family-disjointness invariant across both
   the **role layer** (this ADR) and the **hook layer**
   (ADR-7) — a future LoopGuard middleware that asks a
   second model to grade loop-evidence cannot be from the
   acting-role family.

**Why one amendment for two R-Ns.** R-19 (family-disjointness)
and R-27 part 1 (Cornell/Simula citation) share the same
mechanism (correlated errors at training-distribution level)
and the same source-note batch
(`correlated-llm-errors-and-ensembling-2026-05.md` §6 R-1 /
R-2). Splitting them into two amendments would force readers
of either to re-derive the connection. The §Decision routing
table receives no edit — both rules are invariants on the
existing structure.

**Why not pin a `provider:` field in `~/.fa/models.yaml`
schema here.** The schema is still in flux (e.g.
§Amendment 2026-05-12 added `tool_protocol.error_code_dual_mode`).
Pinning a new field now would couple this amendment to the
schema PR. The behavioural rule is sufficient; the schema
field lands with the inner-loop scaffolding when the regex
extractor lands.

**Subtraction-check (AGENTS.md §Pre-flight Step 4 / rule #10).**

1. **Removing what makes this redundant?** None — the original
   §Decision table left family unspecified; §Amendment
   2026-04-29 forbade auto-escalation but did not name the
   mechanism (correlated errors).
2. **Capability lost if omitted?** A future Eval role from
   the same family as Coder replicates the Coder's error
   instead of catching it — `ρ̂ ≈ +0.6` of error-pairs match
   per the cited papers, so > 50 % of Eval «catches» are
   actually rubber-stamps of the Coder mistake.
3. **OSS precedent for not having it?** Ampcode «three bare
   functions» harness does not name family-disjointness — it
   targets a single tier (Claude). DPC mainline does not
   either — it routes everything through Sonnet. Both are
   single-family stacks; FA's multi-tier scope (per
   `project-overview.md` §6) makes the rule load-bearing
   here while it is vacuous there.
4. **Step-as-function?** YES for rule 2 (regex slug
   extraction is parsing — no LLM needed). Rules 1, 3, 4
   are invariants on existing surfaces, not new steps.

**Files changed (this PR, knowledge-layer only).**

- `knowledge/adr/ADR-2-llm-tiering.md` — this amendment block.
- `knowledge/adr/ADR-7-inner-loop-tool-registry.md` — §Amendment
  2026-05-20 rule 4 (LLM-using-hook family-disjoint;
  generalises this amendment to the hook layer).
- `knowledge/adr/DIGEST.md` — ADR-2 row amendments bullet.
- `knowledge/trace/exploration_log.md` — Q-2 amendment block.
- `AGENTS.md` — §PR Checklist rule #10 sub-citation:
  «prompt-diversity layer» as recognised anti-pattern (R-27
  part 2, lives in AGENTS.md rule #10, sibling of this
  amendment).
- `HANDOFF.md` — ADR-2 amendment line update.

**Re-evaluation triggers (this amendment).**

- **Tier line-up changes to put two roles in the same family
  by user choice.** Action: re-open the rule, document why
  the chosen tier-pair is exempt (e.g. measured `ρ̂`
  empirically on FA-workload eval shows family-disjoint
  prediction failed for this pair), and pin the exemption
  to a specific model-slug pair — not a category bypass.
- **A FA-workload eval (post-UC5) measures the Cornell P-1
  prediction `ρ̂ > 0.4` for the actively-routed family-pair
  and the gain from cross-family does not appear.** Action:
  weaken rule 1 to «MUST be family-disjoint when measured
  `ρ̂ > 0.3` on UC5 eval», with the measurement script
  landing as a separate ADR (post-UC5 scope).
- **Cornell P-1 / Simula P-2 are retracted or contradicted by
  a higher-N replication.** Action: re-evaluate the
  amendment's empirical anchor; keep rule 1 if Ampcode /
  DPC field experience continues to support it, drop it if
  the empirical case collapses.

### Sub-amendment 2026-05-21 — R-19 role-layer enforcement (regex extractor + disjoint check)

**Source.** Implementation roadmap
[`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
§R-19 (Wave 3 — role-layer runtime enforcement of the
2026-05-20 amendment above). The 2026-05-20 amendment landed
the *rule* but explicitly deferred the *enforcement code* to
the inner-loop scaffolding PR (§Amendment 2026-05-20 rule 2
«the regex extractor lives in the inner-loop scaffolding PR
… at ~30 LOC»); this sub-amendment records that landing.

**Problem.** The 2026-05-20 amendment text is enforceable only
if a runtime call site refuses configs that violate it. The
hook-layer call site landed in ADR-7 §Amendment 2026-05-20
rule 4 (cross-link target of the 2026-05-20 amendment) —
`HookRegistry._validate_middleware` raises `ValueError` when
an LLM-using middleware shares family with the acting role.
The role-layer call site (the `~/.fa/models.yaml` loader)
was still missing; without it, a user can pin Eval=`glm-4.5`
+ Coder=`glm-4.5` in the config and the rule is documentation
only.

**Decision (no shape change to §Decision routing table, no
shape change to the 2026-05-20 amendment).**

1. **`src/fa/roles.py`** ships the two pure functions the loader
   needs:
   - `extract_family(slug: str, *, override: str | None = None) -> str`
     — regex slug-to-family inference. Slugs lowercased once
     at the boundary; ordered regex table (most specific first)
     covers the families enumerated in the 2026-05-20 amendment
     rule 1. Returns the family string (member of
     `KNOWN_FAMILIES`); raises `FamilyExtractionError` when
     no row matches and no `override` is supplied — the
     «default-deny when family unknown» branch the 2026-05-20
     amendment specifies.
   - `check_eval_disjoint(*, planner_family, coder_family, eval_family)`
     — verifies eval_family ≠ planner_family and
     eval_family ≠ coder_family. Raises
     `EvalFamilyConflictError` (`ValueError` subclass) with
     both colliding roles named in the message so the user
     knows which override would fix the config. Planner and
     coder are permitted to share a family — the §Decision
     routing table allows a single coder-tier model to back
     both roles; only the eval-vs-actor disjointness is
     enforced.
2. **Loader call site lands with T-2.** The
   `~/.fa/models.yaml` loader itself is part of the T-2 LLM
   driver (`fa-0.1-release-gaps-2026-05.md` T-2); the loader
   PR will call `extract_family` per role and
   `check_eval_disjoint` once before returning the parsed
   config. The pure functions ship here so the loader has a
   tested dependency to consume.
3. **No `RoleConfig` dataclass yet.** YAGNI — every consumer
   in M-1 reads roles via the existing prompt-layer
   convention; the dataclass lands with the loader. The
   sub-amendment intentionally ships only the two functions.

**Subtraction-check (AGENTS.md §Pre-flight Step 4 / rule #10).**

1. **Removing what makes this redundant?** None — the
   2026-05-20 amendment landed the rule but explicitly
   deferred the enforcement code; this is the deferred code.
   The hook-layer call site (R-29) catches LLM-using hooks
   only, not role configs.
2. **Capability lost if omitted?** A user can configure
   Eval=`glm-4.5` + Coder=`glm-4.5` and the rule is
   documentation-only — `ρ̂ ≈ +0.6` correlated errors slip
   through silently per the 2026-05-20 amendment's primary
   sources.
3. **OSS precedent for not having it?** Ampcode «three bare
   functions» does not enforce because it targets a single
   tier; DPC mainline routes everything through Sonnet. Both
   are single-family stacks; FA's multi-tier scope makes the
   rule load-bearing — same as the 2026-05-20 amendment.
4. **Step-as-function?** YES — both `extract_family` and
   `check_eval_disjoint` are pure functions, no LLM call.
   The regex extractor is parsing; the disjoint check is
   three string comparisons.

**Files changed (this sub-amendment).**

- `src/fa/roles.py` — new module (`KNOWN_FAMILIES`,
  `_FAMILY_PATTERNS`, `FamilyExtractionError`,
  `EvalFamilyConflictError`, `extract_family`,
  `check_eval_disjoint`).
- `tests/test_roles.py` — five-test scope per the approved
  Wave-3 plan §M1.2 (extractor happy paths, ambiguous-slug
  default-deny, override honouring, disjoint allow, disjoint
  conflict on eval matching planner/coder; plus sync invariant
  that every regex row maps to a family in `KNOWN_FAMILIES`).
- `knowledge/adr/ADR-2-llm-tiering.md` — this sub-amendment
  block.
- `knowledge/adr/DIGEST.md` — ADR-2 row Amendments bullet
  extended with the 2026-05-21 sub-amendment.
- `knowledge/trace/exploration_log.md` — Q-2 amendment block
  appended.
- `knowledge/llms.txt` — new file routing entry for
  `src/fa/roles.py`.
- `docs/glossary.md` — «family extractor» row added.
- `HANDOFF.md` — ADR-2 amendment line extended with the
  2026-05-21 sub-amendment.

**Re-evaluation triggers (this sub-amendment).**

- **T-2 LLM driver lands the loader call site.** Action:
  delete this sub-amendment's «Loader call site lands with
  T-2» rule (now historical), and add a `RoleConfig`
  dataclass reference here pointing to the loader's location.
- **A new family is added to `KNOWN_FAMILIES`.** Action:
  add the matching regex row to `_FAMILY_PATTERNS` AND a
  parametrised happy-path case to `tests/test_roles.py`.
  The sync-invariant test will fail otherwise.

### Amendment 2026-05-20 (Wave-1) — Per-tier tool-shape registry + role-switch handoff one-liner

**Source.** Implementation roadmap
[`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
§R-18 (Wave 1 — independent of HookRegistry; «tool shape follows
the model's training distribution» rule).

**Problem.** §Amendment 2026-04-29 introduces the
`tool_protocol` field and the «native-by-default» rule, but
silently assumes one *family* of edit-shape is good enough for
all tiers. Empirically (per `borrow-roadmap-2026-05.md` §R-18
+ the *errors* axis of Cornell P-1 / Simula P-2 cited in the
§Amendment 2026-05-20 block above), tool shape follows the
model's training distribution:

- Anthropic family — string-replace edits + `tool_use` blocks.
- OpenAI / DeepSeek families — patch-based edits + function-
  calling.
- Qwen / GLM families — raw JSON tool calls + string-replace
  edits (the post-training distribution they were RL'd on).
- Kimi family — string-replace edits + OpenAI-compatible
  function-calling.

Maintaining one consolidated edit-shape for *all* tiers
degrades 5-15% on cross-family models per primary source.
This amendment makes the per-tier shape an explicit registry
plus a one-liner that fires on role-switch handoff.

**Decision.** Two rules:

1. **Per-tier tool-shape registry.**
   [`knowledge/prompts/tool-shapes.yaml`](../prompts/tool-shapes.yaml)
   ships ONE entry per family currently routed in the ADR-2
   tier table (anthropic / openai / qwen / deepseek / glm /
   kimi at the time of writing — see file header for the
   stability rule). Each entry has `family:`, `shape.edit:`,
   `shape.tool_call_format:`, and a quoted
   `handoff_one_liner:`. This is **NOT** a full provider
   translation layer — it is a lookup table the harness reads
   once per turn to know which edit-shape to ask for.
2. **Role-switch handoff one-liner.** When the inner loop
   switches roles (Planner → Coder, Coder → Eval, …), the
   harness MUST inject the **previous** role's
   `handoff_one_liner` into the next role's system prompt
   (rendered verbatim in English; one short paragraph). The
   one-liner template is: *"The previous role spoke as a
   `<family>`-family model using `<shape.edit>` edits and
   `<shape.tool_call_format>`. Ignore that shape; use the
   tool shape native to your own family."* Quoting the
   previous role's shape prevents the next role from cargo-
   culting it; the explicit «ignore that shape» is the bit
   that fires.

**Scope.** v0.1 ADR-2 tier picks (Eval / Planner / Coder /
Debug). When a new tier joins (e.g. UC5 Reflector), add ONE
row to `tool-shapes.yaml` and reference the family in this
amendment without rewriting the registry. Per-call
overrides (e.g. one-off model swap for benchmarking) MUST
edit `tool-shapes.yaml` rather than skip the registry —
audit trail tied to one file is the whole point.

**What this amendment does NOT do.**

- It does NOT translate function-call schemas across
  families. A Planner emitting an Anthropic `tool_use` block
  is not converted to an OpenAI function call for the next
  Coder turn — each role asks the LLM for its own native
  shape. The handoff one-liner is the cheap «do not copy»
  instruction; that is sufficient.
- It does NOT bind to a specific tool-call parser library.
  The harness still uses whichever parsing path it already
  has (per ADR-2 §Amendment 2026-04-29
  `protocol == "native"`); `tool-shapes.yaml` is read-only
  metadata.
- It does NOT replace ADR-2 §Amendment 2026-04-29 — that
  amendment still pins `protocol = "native"` as default;
  this one specifies *which* native shape per family.

**Subtraction-check (AGENTS.md §Pre-flight Step 4).**

- Removing what makes this redundant? — None. ADR-2
  §Amendment 2026-04-29 implies one native shape per tier
  but does not enumerate; no other registry covers the
  per-family shape mapping. The closest precedent is
  Aperant's per-model tool-call adapter (separate file in
  `apps/desktop/src/main/ai/providers/`), which is structurally
  identical but TS-side.
- Capability lost if omitted? — Sub-100k-token sessions on
  cross-family routings (current ADR-2 default) lose 5-15%
  accuracy on `string_replace` vs `patch` mismatches; no
  audit trail of which tier was asked for which shape.
- OSS precedent for not having it? — ampcode (single
  Anthropic family; no per-family registry needed) and DPC
  (single OpenAI-compatible family; same). Neither has
  FA's cross-family workload.

**Reversal triggers.**

- A future FA-workload eval (post-UC5) shows ≤2% gain from
  per-family tool-shape selection vs a single
  `string_replace + raw_json` baseline → drop the registry,
  keep the §Amendment 2026-04-29 native-by-default rule
  unchanged.
- A new provider's family does NOT fit the shape categories
  enumerated above (e.g. some future native MCP-only family)
  → add a row to `tool-shapes.yaml` and amend this section
  in the same PR.

## References

- [`project-overview.md`](../project-overview.md) §6 (key constraints — LLM providers).
- [`research/memory-architecture-design-2026-04-26.md`](../research/memory-architecture-design-2026-04-26.md) §1 bullet 2 (mixed-LLM design constraint).
- [`research/agent-roles.md`](../research/agent-roles.md) §5.1 (Planner / Executor / Critic minimum-set rationale; Coder maps to Executor here; v0.1 omits Critic — see 2026-04-29 amendment).
- [`research/cross-reference-ampcode-sliders-to-adr-2026-04.md`](../research/cross-reference-ampcode-sliders-to-adr-2026-04.md) §3.3 / §9.6 / §10 R-1 / R-7 — rationale for the 2026-04-29 amendment.
- [`research/how-to-build-an-agent-ampcode-2026-04.md`](../research/how-to-build-an-agent-ampcode-2026-04.md) §3.1 / §4 — native tool-calling shape.
- [`research/semi-autonomous-agents-cross-reference-2026-05.md`](../research/semi-autonomous-agents-cross-reference-2026-05.md) §2.3-A / §3.3-B / §7.1 — rationale for the 2026-05-01 MCP forward-compat amendment.
- MCP specification: [https://modelcontextprotocol.io](https://modelcontextprotocol.io) — JSON-RPC + STDIO/HTTP+SSE transport.
- PR #17 review (`https://github.com/GITcrassuskey-shop/First-Agent/pull/17`) — Q2 + Q3 verbatim answers.
