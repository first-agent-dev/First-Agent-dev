# ADR-7 — Inner-loop & tool-registry contract for v0.1

- **Status:** accepted
- **Date:** 2026-05-12
- **Deciders:** project owner (`0oi9z7m1z8`), Devin (drafting)

## Context

[ADR-1](./ADR-1-v01-use-case-scope.md) §UC1 ships a Coder role
that edits files and opens PRs end-to-end.
[ADR-2](./ADR-2-llm-tiering.md) §Decision pins the role mix and
two §Amendments fix `tool_protocol` per role (2026-04-29) and an
MCP-shaped JSON-RPC convention for in-process dispatch
(2026-05-01). [ADR-6](./ADR-6-tool-sandbox-allow-list.md) §Tool
wiring lists the five v0.1 tools (`read_file`, `list_files`,
`edit_file`, `write_file`, `grep`) and the `Sandbox.check_*`
gate each of them passes through.

What ADR-1..6 do **not** pin is the **inner-loop boundary**
between the LLM and the harness: how a tool is registered, what
shape a request and a response take, where the sandbox and
audit hooks attach, which edit-shape the Coder writes against,
how input is validated, and how the system prompt is assembled
turn-after-turn. The ADR-6 Tool wiring table calls this out
explicitly: *"The inner-loop ADR (R-1, deferred) will fix the
exact exception type and the surface; for now the contract
is…"* — and then leaves a stub Python signature.

[`HANDOFF.md`](../../HANDOFF.md) §Next steps item 1 reserves
the ADR-7 slot and enumerates six surfaces to pin: tool-registry
contract, tool-call audit log shape, edit-format
(string-replace vs unified-diff), input JSON-Schema validation,
MCP-shaped request / response per ADR-2 §Amendment 2026-05-01,
and a minimal hook-pipeline primitive (pre-tool / post-tool;
pre-run / post-run / on-event deferred to v0.2). This ADR pins
those six. Prompt-assembly + prefix-cache (R-8) is added as a
§Loop invariant because the same runtime loop owns it and
splitting it into a separate ADR would force every tool PR to
straddle two specifications.

Inputs already resolved before this ADR:

- [`research/efficient-llm-agent-harness-2026-05.md`](../research/efficient-llm-agent-harness-2026-05.md)
  — single source-of-truth for the harness-research sweep
  under ADR-7 prep. §0 Decision Briefing resolves R-1..R-8
  (7 TAKE + 1 DEFER); R-9 (`harness_id` stamp) was added
  post-briefing per §11 Q-6 and is consumed by this ADR §7
  (Trace) — so `HANDOFF.md` §Current state «nine resolved
  recommendations (R-1..R-9; 8 TAKE + 1 DEFER)» is the
  cumulative count, while ADR-7 §Context references the
  formal Decision Briefing scope (R-1..R-8). §10 ADR-7
  contract sketch synthesises the resolved recommendations
  into a single ToolSpec / ToolResult / Trace pseudo-schema
  + runtime-loop + acceptance-block — this ADR is the
  canonical write-up of that sketch.
- [`research/cross-reference-ampcode-sliders-to-adr-2026-04.md`](../research/cross-reference-ampcode-sliders-to-adr-2026-04.md)
  §10 R-1 (inner-loop ADR scope), R-3 (string-replace edit-format
  fixture), R-7 (single-loop / no Critic in v0.1).
- [`research/semi-autonomous-agents-cross-reference-2026-05.md`](../research/semi-autonomous-agents-cross-reference-2026-05.md)
  §7.1 (R-1 input — MCP-shape, hook-pipeline primitive, ACI
  tool signatures), §7.3 (two edit-shapes), §8.4 (large-file
  two-stage read), §8.5 (mini-hook-system rationale —
  pre-tool / post-tool only, defer the rest).
- [`research/how-to-build-an-agent-ampcode-2026-04.md`](../research/how-to-build-an-agent-ampcode-2026-04.md)
  — Thorsten Ball / Amp inner-loop micro-architecture and the
  `read_file` / `list_files` / `edit_file` three-tool baseline
  mapped to ADR-1 / ADR-2.

## Options considered

### Option A — No formal inner-loop ADR; let each tool PR define its own contract

- Pros:
  - Zero documentation cost up-front.
  - Matches ampcode's *"three bare functions"* baseline
    (cross-reference §10 R-1, ampcode note §3.1).
- Cons:
  - Ampcode targets exactly one tier (Anthropic Claude); FA
    targets four (Planner / Coder / Debug / Eval) plus a
    `tool_protocol: native | prompt-only` axis. No formal
    contract = each Coder model sees a different shape for
    the same tool, breaking the
    [ADR-2 §Amendment 2026-04-29](./ADR-2-llm-tiering.md#amendment-2026-04-29--tool_protocol-field--native-by-default-v01-inner-loop-without-critic)
    invariant that "loop adapts to the role's `tool_protocol`,
    not to the model."
  - ADR-2 §Amendment 2026-05-01 MCP-shape JSON-RPC convention
    has no concrete carrier — the convention floats free until
    the first tool PR lands, and that PR's shape becomes the
    de-facto spec.
  - ADR-6 §Tool wiring leaves an explicit stub
    `class Sandbox: def check_read(...): ...` that the
    inner-loop ADR is supposed to close; without ADR-7 the
    stub propagates into the first tool implementation as
    inline boilerplate, duplicating across each tool.
  - Forks reading the repo cannot tell which shape is
    intentional vs. legacy; minimalism-first
    ([`project-overview.md` §1.2](../project-overview.md#12-enforceable-principle--minimalism-first))
    relies on **enforceable** boundaries, not implicit ones.

### Option B — Formal inner-loop ADR with MCP-shaped tool contract, two edit-shapes, mini hook-pipeline (chosen)

- Pros:
  - Single source of truth for every tool PR (chunker
    indexer, search, edit, future `run_command`). The first
    implementation PR consumes the ADR; subsequent PRs cite it.
  - Closes ADR-2 §Amendment 2026-05-01 (MCP forward-compat
    JSON-RPC convention) and ADR-6 §Tool wiring (pre-tool gate
    placement) at the natural boundary — the inner-loop —
    rather than scattering each across each tool.
  - Allows the harness-research sweep
    ([`efficient-llm-agent-harness-2026-05.md`](../research/efficient-llm-agent-harness-2026-05.md)
    §10) to land its synthesis as a *decision*, not a *plan*:
    R-1 progressive tool-disclosure, R-2 trace separation,
    R-3 SQLite FTS5 reuse forward-compat, R-4 `[tool_groups]`
    extension to ADR-6, R-5 no-Critic in v0.1, R-7 4-question
    subtraction acceptance block, R-8 static layered prompt.
  - Mini hook-system (pre-tool + post-tool only, per
    semi-autonomous-agents §8.5) gives sandbox / audit / future
    HITL a documented attachment point at ~50 LoC marginal
    cost vs ampcode-style inlining at every tool.
- Cons:
  - Documentation cost up-front (~300 lines, this file).
  - Locks in shape decisions before the first end-to-end
    tool implementation PR proves them; mitigated by R-3
    fixture (HANDOFF §Next steps item 4) which empirically
    pins the edit-format default after ADR-7 lands, and by
    the explicit re-evaluation triggers in §Consequences.
  - Increases the surface a fork must adopt to be compatible
    (any prompt-only Coder tier must implement the same
    JSON-RPC-shaped dispatcher); accepted because ADR-2
    already requires this convention.

### Option C — Formal ADR + full hook pipeline (pre-run / post-run / on-event) + MCP transport in v0.1

- Pros:
  - Maximal extensibility — every concern (reflection,
    semantic-event triggers, multi-agent coordination) has a
    seat at the table from day one.
  - MCP transport (not just MCP-shape) lets external MCP
    servers (Bright Data, Cloudflare Code Mode) be wired in
    without an ADR-2 amendment.
- Cons:
  - Pre-run / post-run / on-event hooks are v0.2 reflection
    /  semi-autonomous territory; including them now imports
    UC5 (semi-autonomous research — deferred per
    [ADR-1 §Amendment 2026-05-01](./ADR-1-v01-use-case-scope.md#amendment-2026-05-01--uc5-added-to-deferred-list)
    + 2026-05-06) ahead of schedule.
  - MCP transport adds an `mcp` package dependency that
    [ADR-2 §Amendment 2026-05-01](./ADR-2-llm-tiering.md#amendment-2026-05-01--mcp-forward-compat-tool-shape-convention)
    explicitly excludes from v0.1 ("**No `mcp` package
    dependency in v0.1**"). It also adds OS-level sandbox
    concerns (code-execution-over-MCP per Anthropic Nov 2025
    blog) that
    [ADR-6 §Re-evaluation triggers](./ADR-6-tool-sandbox-allow-list.md#consequences)
    flags as out-of-scope for v0.1.
  - Harness-research R-6 explicitly defers code-execution-over-MCP
    per §0; choosing it here re-opens the resolved decision.

## Decision

We will choose **Option B** for v0.1 with the following concrete
shape. This subsumes the §10 contract sketch in the harness
research note; the per-§ heading order matches HANDOFF.md §Next
steps item 1 to make the mapping easy to audit.

### 1. Runtime loop

The inner loop runs Coder ↔ tools (thought → tool-call →
observation → next thought) with no Critic / Reflector role
(per [ADR-2 §Amendment 2026-04-29](./ADR-2-llm-tiering.md#amendment-2026-04-29--tool_protocol-field--native-by-default-v01-inner-loop-without-critic)
§point 5). One iteration:

1. Assemble the static prompt prefix **once** at session start
   (§9 Loop invariant — prompt assembly); freeze for the
   duration of the session.
2. Load dynamic repo / session context by pointers in the first
   user message — `hot.md` cite, current task, files of
   interest (tier-1 disclosure per §6).
3. Expose compact tool descriptors in the system prompt
   (tier-2: `name` + one-line description + tags); full input
   schema loaded on demand (tier-3) — see §6.
4. Receive model response.
5. If the response is a tool call: input JSON-Schema
   validation (§5) → `pre_tool` hook chain → tool handler →
   `post_tool` hook chain (§8). If any `pre_tool` hook returns
   `modify_params`, the dispatcher MUST re-run the same
   JSON-Schema validation **and** the ADR-6 sandbox checks on
   the mutated `params` before the handler executes — no
   exception. Hook re-entry is bounded (one re-validate per
   call); a second mutation by the same chain is a hard error.
6. Append one JSONL event per state transition to
   `~/.fa/state/runs/<run_id>/events.jsonl`; large payloads
   land under `~/.fa/state/runs/<run_id>/artifacts/` (§7).
7. Return the `ToolResult.summary` + `artifacts[]` paths back
   to the model; the full payload stays on disk (R-2
   trace-separation invariant).
8. Stop on explicit final answer, max iterations, hard error,
   or an explicit user approval gate.

Loop runs single-threaded per session. No intra-loop retry on
hook denial (the deny is a hard stop the model sees as an
error). Intra-role retry on tool execution failure
(`error.retryable == true`) is allowed; cross-tier escalation
remains forbidden per ADR-2 §Decision.

### 2. ToolSpec (registry entry)

Every tool registered in `src/fa/inner_loop/registry.py` is a
`ToolSpec` record. The shape is the **MCP-shaped JSON-RPC
convention** from
[ADR-2 §Amendment 2026-05-01](./ADR-2-llm-tiering.md#amendment-2026-05-01--mcp-forward-compat-tool-shape-convention)
§point 4 — the inner-loop dispatcher mirrors JSON-RPC; ADR-7
inherits the convention, MAY add fields, MUST NOT change
existing ones without an ADR-2 amendment.

```python
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

@dataclass(frozen=True)
class ToolSpec:
    name: str                                  # stable dotted string, e.g. "fs.read_file"
    description: str                           # one-line model-facing summary (tier-2)
    input_schema: dict                         # JSON Schema; loaded on demand (tier-3)
    permission: Literal["read", "workspace", "full"]  # ADR-6 sandbox scope
    handler: Callable[[dict], "ToolResult"]    # deterministic dispatcher entry
    tags: tuple[str, ...] = ()                 # used by [tool_groups] allow-list (forward-compat)
    output_schema: dict | None = None          # optional; documents ToolResult.result
    defer_loading: bool = False                # forward-compat for Anthropic tool-search
```

The v0.1 registry loader (`src/fa/inner_loop/registry.py::register`)
MUST reject a `ToolSpec` with `permission == "full"` or with any
missing required field (`name`, `description`, `input_schema`,
`permission`, `handler`). `full` exists only as an explicit future
registry value so implementers cannot smuggle privileged tools behind
an underspecified boolean — a future ADR / amendment that introduces
a privileged tool MUST also define its sandbox.

`ToolResult` is the canonical return shape for every handler **and**
the payload the dispatcher appends to the conversation:

```python
@dataclass(frozen=True)
class ToolError:
    code: str          # stable domain identifier (internal); ergonomic strings — e.g.
                       # "invalid_params", "sandbox_deny", "no_unique_match". Per
                       # ADR-2 §Amendment 2026-05-01 §4 dual-mode, this internal `str`
                       # maps to a JSON-RPC `int` code at the wire boundary; the
                       # mapping table lives next to the dispatcher.
    message: str       # human-readable; may include JSON-Schema error path
    retryable: bool    # if true, the model is free to retry with corrected params

@dataclass(frozen=True)
class ToolResult:
    summary: str                       # short model-facing text; ALWAYS present
    result: Any | None = None          # structured payload (JSON-RPC-compatible per ADR-2 §Amendment
                                       # 2026-05-01 §1 — `Any | None`; v0.1 in-process tools typically
                                       # return dict, but the type stays `Any` for v0.2 MCP forward-compat
                                       # where JSON-RPC results can be list / str / number / bool); when
                                       # `ToolSpec.output_schema` is set, the dispatcher validates against it.
    error: ToolError | None = None     # present iff the call failed; mutually exclusive with `result`
    artifacts: tuple[str, ...] = ()    # paths to large outputs under ~/.fa/state/runs/<run_id>/artifacts/
```

The model sees `summary` + `artifacts[]` paths back from the loop
(per §1 step 7). Large payloads stay on disk (R-2 trace-separation
invariant). Empty output is explicit (`result = None` or
`result = {}`), never silent.

**Naming.** Tool `name` uses dotted namespaces (`fs.read_file`,
`fs.list_files`, `fs.edit_file`, `fs.write_file`, `fs.grep`).
The namespace prefix is the group used by R-4 forward-compat
extension to ADR-6 (`[tool_groups] fs = ["read", "workspace"]`).
Renaming a tool requires an ADR-7 amendment because Coder
prompts and `events.jsonl` consumers grep on `name`.

### 3. Tool catalog v0.1

Exactly the five tools from
[ADR-6 §Tool wiring](./ADR-6-tool-sandbox-allow-list.md#tool-wiring),
registered at startup; **no other tools in v0.1**:

| name | permission | gate | edit-shape |
|---|---|---|---|
| `fs.read_file(path, start_line?, end_line?)` | read | `check_read` | n/a |
| `fs.list_files(path)` | read | `check_read` + filter | n/a |
| `fs.edit_file(path, old_string, new_string)` | workspace | `check_write` (implies `check_read` per ADR-6 §6) | string-replace |
| `fs.write_file(path, content)` | workspace | `check_write` | full-file |
| `fs.grep(pattern, path)` | read | `check_read` recursive | n/a |

A sixth, `fs.apply_patch(path, unified_diff)`, is **registered
but feature-flagged off by default** in v0.1; see §4. No
`run_command` tool, no `network.*` tool, no MCP transport in
v0.1 (ADR-6 §Re-evaluation triggers + ADR-2 §Amendment
2026-05-01 §"No `mcp` package dependency in v0.1").

`fs.read_file` accepts the optional `start_line` / `end_line`
window pattern from semi-autonomous-agents §8.4 (two-stage read
for files > a chunker-store-estimated threshold). v0.1 default
threshold: 4 000 lines (~80 KB) — small files round-trip in one
read; larger files require an explicit window. Threshold is
overridable in `~/.fa/inner_loop.toml`.

### 4. Edit-shapes (string-replace and apply_patch)

Two shapes are accepted; default is `fs.edit_file` (string-replace)
per cross-reference §10 R-3 and semi-autonomous §7.3.

1. **`fs.edit_file(path, old_string, new_string)` — single-edit
   string-replace.** Ampcode-style; simple mental model for the
   model. `old_string` must match **exactly once** in the
   target file (whitespace included); otherwise the call
   returns `error.code = "no_unique_match"` (retryable true —
   the model should widen the match window or use `apply_patch`).
   This is the default because cross-reference §10 R-3 already
   pinned it after the 5-10-edit fixture sweep across all five
   ADR-2 models.
2. **`fs.apply_patch(path, unified_diff)` — multi-edit
   unified-diff.** Atomic; validated through `git apply
   --check` before write. Off by default in v0.1; enabled per
   `~/.fa/inner_loop.toml` `[edit] apply_patch = true`. Reserved
   for multi-hunk edits where the model would otherwise need
   five sequential `edit_file` calls — and for Coder-tier models
   that empirically prefer unified-diff. The HANDOFF §Next steps
   item 4 fixture (5-10 string-replace + 5-10 unified-diff edits
   on each ADR-2 model) determines whether the default flips in
   ADR-7 §Amendment after the next sweep.

`fs.write_file` is full-file overwrite. Used only when the
caller deliberately replaces the file (new file, large
re-write). Not the default edit primitive; the model should
prefer `fs.edit_file`.

### 5. Input validation

Every tool call's `params` is validated against
`ToolSpec.input_schema` (JSON Schema Draft 2020-12) **before**
the hook chain runs. Validation failures produce a
`ToolResult` with `error.code = "invalid_params"`,
`retryable = true`, and the JSON-Schema error path in
`error.message`. The model sees a structured failure (not a
Python traceback) and may retry the call with corrected
parameters.

Implementation uses `jsonschema` (single new dependency at
this layer; ADR-2 §Amendment 2026-05-01 already implicitly
needs it for MCP-shape compat). The schema is loaded **once**
per `ToolSpec` at registry init; per-call validation is
~µs-level — the validation step itself has no token cost
(success emits no model-facing message). On failure §1 step 7
governs surfacing: the resulting `ToolResult` (with
`error.code = "invalid_params"`, `retryable = true`) is fed
back to the model exactly like any other `ToolResult`, so the
model can correct and retry. There is no silent-drop path:
every emitted `ToolResult` reaches the model per §1 step 7,
regardless of `retryable`.

**Re-validation after `pre_tool` mutation (§1 step 5).** If a
`pre_tool` hook returns `modify_params`, the dispatcher MUST
re-run this same JSON-Schema check against the mutated
`params` *and* re-run the ADR-6 sandbox check before the
handler executes. There is no "trusted hook output" path; a
hook cannot bypass validation by mutating a previously-valid
payload into an invalid one.

Schemas live alongside the handlers in
`src/fa/inner_loop/tools/<tool_name>.py` (one file per tool)
and are imported by `registry.py`. No global schema file —
the schema travels with its handler so that adding a tool is
one PR touching one file.

### 6. Tool disclosure (three tiers)

Per harness-research R-1, the registry surface is a
discriminated union of three disclosure tiers; the v0.1 loop
uses the first two and reserves the third for v0.2.

1. **Tier 1 — server-name list.** A list of tool *groups*
   (`fs`, future `git`, `gh`, `bm25`) exposed to the model in
   the user message at session start. v0.1 has one group:
   `fs`.
2. **Tier 2 — per-tool one-line descriptors.** `name` +
   `description` + `tags` for each tool in an enabled group,
   injected into the system-prompt **at the static-prefix
   layer** (per §9) — see the prompt-assembly invariant.
3. **Tier 3 — full input schema on demand.** The full
   `input_schema` is **not** in the system prompt. Instead the
   model receives schemas the first time it calls a tool in
   the session (lazy hydration), or via an explicit
   `fs.describe_tool(name)` tool that v0.1 does **not** ship
   but registers a placeholder for. Forward-compat for
   Anthropic `tool_search_tool_*_20251119` and BM25-based
   lookup (R-3 reuses SQLite FTS5) once the catalog grows
   past ~10 tools.

This three-tier shape is what makes the migration to a
larger v0.2 catalog config-only rather than code-only.

**Empirical backing for tier-3 lazy hydration** (added 2026-05-12 §Amendment).
[`bootstrap-cost-baseline-2026-05.md`](../research/bootstrap-cost-baseline-2026-05.md)
§3 records six independent ADR-7-prep sessions (3 Devin + 3 Arena.ai
harnesses, ≥4 distinct model selections) that all reached
«ready-to-draft» reading only **tier-1 + tier-2** material from the
6-file irreducible core (`HANDOFF.md`, `knowledge/llms.txt`,
`knowledge/adr/DIGEST.md`, `knowledge/adr/ADR-template.md`,
`knowledge/research/efficient-llm-agent-harness-2026-05.md`,
`knowledge/trace/exploration_log.md`) — none of the sessions hit
tier-3 full `input_schema`. v0.1 lazy hydration is therefore
consistent with observed agent behaviour across two distinct agent
harnesses.

### 7. Trace — events.jsonl ≠ hot.md

Per harness-research R-2 (anti-summary-rot invariant). Two
artefacts; the runtime loop writes to both, but only
`events.jsonl` is consumed by replay / eval / future
self-evolution.

```text
~/.fa/state/runs/<run_id>/events.jsonl     # append-only, JSONL, raw
~/.fa/state/runs/<run_id>/artifacts/<...>  # large tool outputs (diffs, file dumps)
~/.fa/state/runs/<run_id>/hot.md           # LLM/human-readable summary; overwritable
```

Every state transition emits one event; the schema is:

```json
{
  "ts": "2026-05-12T07:34:56Z",
  "run_id": "r-2026-05-12-a3f9",
  "harness_id": "fa-inner-loop@0.1.0",
  "actor": "coder|tool|hook|user",
  "kind": "user_msg|model_msg|tool_call|tool_result|hook_decision|approval|error|stop",
  "tool_name": "fs.edit_file",
  "tool_call_id": "tc-001",
  "parent_event_id": "ev-007",
  "content": { ... }
}
```

`harness_id` is stamped on every event so a v0.2 trace-replay
can refuse to compare runs across harness versions
(forward-compat per
[`efficient-llm-agent-harness-2026-05.md`](../research/efficient-llm-agent-harness-2026-05.md)
§11 Q-6).

**Future KPI consumption** (added 2026-05-12 §Amendment). The same
`events.jsonl` schema is the auto-collection source for
[BACKLOG I-7](../BACKLOG.md#i-7--bootstrap-cost-as-auto-collected-kpi-uc5-blocked)
once the UC5 eval-harness lands; the §6 baseline table in
[`bootstrap-cost-baseline-2026-05.md`](../research/bootstrap-cost-baseline-2026-05.md)
is the migration-source historical row.

**Invariant.** `hot.md` cites file paths into `artifacts/` and
event IDs into `events.jsonl`; `hot.md` **MUST NOT** be the
source for replay or self-evolution. This is the same shape
as the [ADR-3 Mechanical Wiki](./ADR-3-memory-architecture-variant.md)
canon-vs-cache split: canon (`events.jsonl`) wins; the
summary (`hot.md`) is a cheap-read overlay.

This trace shape also extends
[ADR-6 §Audit log](./ADR-6-tool-sandbox-allow-list.md#audit-log)
— the sandbox jsonl becomes a *projection* of `events.jsonl`
filtered to `kind == "hook_decision" && hook == "sandbox"`. A
follow-up implementation PR may collapse the two files or keep
the existing `~/.fa/state/sandbox.jsonl` for ADR-6 backward
compatibility; either is permitted by this ADR.

### 8. Hook pipeline (pre-tool / post-tool only)

A `Hook` is a callable `(event: dict) -> HookDecision`
attached at one of two points:

- **`pre_tool`** — runs after input-schema validation,
  before the handler. Returns `allow` | `deny(reason)` | `modify_params(new_params)`.
  Multiple `pre_tool` hooks run in order; the first `deny`
  short-circuits and is recorded in `events.jsonl` as
  `kind == "hook_decision"`.
  **Re-entry after `modify_params` (cross-ref §1 step 5).**
  When hook *N* returns `modify_params(new_params)`, the dispatcher
  re-runs JSON-Schema validation (§5) and the ADR-6 sandbox check
  on `new_params`, then **continues the chain from hook *N+1*** with
  the mutated payload. Already-run hooks `1..N-1` do **not** re-run
  (this bounds the chain to one pass over each hook and avoids
  repeating approval prompts / audit emissions). At most **one**
  mutation per dispatch is allowed across the entire chain — a
  second `modify_params` return by any hook is a hard error
  (`error.code = "hook_double_mutation"`, `retryable = false`).
  First-mutation-wins semantics keep the re-entry bounded and the
  audit trail linear.
- **`post_tool`** — runs after the handler, before
  `ToolResult` is appended to the conversation. Used for
  audit, redaction, artifact-write. Cannot deny (the tool
  already ran); may rewrite `ToolResult.summary` (e.g.
  truncate large outputs) but MUST NOT silently change
  `ToolResult.result` shape.

v0.1 ships exactly two hooks (both `pre_tool`):

1. `SandboxHook` — wraps
   [ADR-6 `Sandbox.check_read` / `check_write`](./ADR-6-tool-sandbox-allow-list.md#tool-wiring).
   Single resolution per invocation (ADR-6 §point 7).
2. `ApprovalHook` — opt-in via `~/.fa/inner_loop.toml`
   `[approval] write = "ask"`. When enabled, a `write` or
   `workspace` permission tool blocks for a user prompt.
   Off by default in v0.1.

And one `post_tool` hook:

3. `AuditHook` — appends a `kind == "tool_result"` event with
   the resolved path, decision, and (path-only) artifact
   reference. This is the
   [ADR-6 §Audit log](./ADR-6-tool-sandbox-allow-list.md#audit-log)
   projection that subsumes `~/.fa/state/sandbox.jsonl`.

`pre_run` / `post_run` / `on_event` hook points are **not
implemented in v0.1** per semi-autonomous-agents §8.5
("mini-hook-system… max-выгода"). They are reserved for the
future Reflection / UC5 ADR and may be added by amendment
without breaking the v0.1 contract.

**Registry-form contract.** The shape above (two `pre_tool`
hooks + one `post_tool` hook, first-deny short-circuit, one
mutation per dispatch) is the **doc-first** v0.1 form of the
HookRegistry middleware chain. The five-point lifecycle,
`GuardMiddleware` vs `ObserverMiddleware` split, and
`register()` family-disjoint enforcement are frozen as
documentation in [ADR-8](./ADR-8-hook-registry.md) (2026-05-20).
The runtime that builds the registry against ADR-8 is BACKLOG
M-1 (inner-loop scaffolding); after it lands, this §8
becomes a cross-ref to ADR-8 §5 "Migration plan from v0.1
inline hooks" and the §8 hook list collapses to that one
mapping row.

### 9. Loop invariant — prompt assembly

Per harness-research R-8 (Option (i), TAKE). The static layered
prompt is assembled **once** at session start and frozen for
the session:

```text
[layer 1] system  : AGENTS.md role-prompt body + ADR-2 role config
[layer 2] system  : tier-2 tool descriptors (this ADR §6)
[layer 3] system  : sandbox-policy summary (ADR-6 §Policy semantics)
[layer 4] user[0] : dynamic state — hot.md cite, current task, files of interest
```

Layers 1-3 are frozen for the session and cached by the
provider's prefix-cache (Anthropic implicit, OpenRouter
provider-variable, vLLM yes). Layer 4 is the single mutable
seam — anything that changes turn-to-turn (current file, last
tool call, partial plan) goes through `hot.md` and lands in
`user[0]` of the next session, **not** by rebuilding the
prefix.

**Implication.** If `AGENTS.md` or an ADR amendment lands
mid-session, the inner-loop does **not** hot-reload the
prefix; the user starts a new session. This is the same
"new session on canon change" pattern ADR-3 already uses.

Migration trigger for v0.2 two-segment assembly: a UC5
benchmark run shows ≥ N% degradation on staleness-sensitive
tasks (the threshold is set in the UC5 ADR, not here).

**Empirical context-budget evidence** (added 2026-05-12 §Amendment).
[`bootstrap-cost-baseline-2026-05.md`](../research/bootstrap-cost-baseline-2026-05.md)
§5 shows Devin sessions converging to ~80–95 K total context at
«feel-ready» across a 2.3× variance in files-count (Session A =
16 files / ~95 K vs Session B = 7 files / ~95 K — same total context,
different reading depth). Arena.ai sessions land in the 70–95 K
range. The static layered prefix shape above therefore lands within
the [AGENTS.md PR Checklist rule #11](../../AGENTS.md#pr-checklist)
≤100 K budget on every measured session — independent empirical
validation that the prefix-cache invariant is achievable on both
Devin and external harnesses.

### 10. Acceptance criteria & 4-question subtraction-first self-audit

**Part A — enforceable checklist.** Before the first
implementation PR (`src/fa/inner_loop/`) merges, the
following MUST hold:

1. `ToolSpec` loader (`registry.register`) raises on any tool
   missing `name`, `description`, `input_schema`,
   `permission`, or `handler`.
2. `ToolSpec` loader raises on `permission: "full"` in v0.1.
3. JSON-Schema validation rejects malformed `params` before
   the `pre_tool` chain runs (§5).
4. If a `pre_tool` hook returns `modify_params`, the
   dispatcher re-runs JSON-Schema validation **and** ADR-6
   sandbox checks on the mutated payload before the handler
   (§1 step 5 + §5 re-validation invariant).
5. ADR-6 `Sandbox.check_*` runs before any filesystem I/O
   inside every `fs.*` handler (§3 + ADR-6 §Tool wiring).
6. `fs.apply_patch` runs `git apply --check` before any
   filesystem write (§4 point 2).
7. Tool results with payload size > the artifact threshold
   (default 32 KiB) return paths in `ToolResult.artifacts`,
   not raw bytes in `result` (§7 trace-separation invariant).
8. `events.jsonl` records **both** successful and failed tool
   calls — `tool_call` always emitted; `tool_result` always
   emitted (with `error != None` on failure).
9. `fs.read_file` exposes the `start_line` / `end_line`
   bounded-window pattern (§3 — semi-autonomous-agents §8.4).
10. Both edit-shapes (`fs.edit_file` string-replace +
    `fs.apply_patch` unified-diff) are registered; the
    default is configurable via `~/.fa/inner_loop.toml`
    (§4).

**Part B — 4-question subtraction-first self-audit.**

Per harness-research R-7 + AGENTS.md PR Checklist rule #10
question 4. Every PR that **adds or amends a harness
component** (tool, hook, prompt-layer, retrieval-stage) under
this contract MUST include in its description explicit answers
to four questions. The check exists at this layer because the
inner-loop is the natural seat of step-as-function vs
step-as-LLM-call decisions:

1. **What is in the agent's context window that does not need
   to be there?** Look at the last N traces' average input
   token count; if a layer (system / tier-2 descriptors /
   `user[0]` state) consistently appears unused by the model,
   either remove it or write one paragraph justifying it.
2. **Which tools does the agent rarely use (over the latest N
   traces)?** A tool with < 1 % call rate over N ≥ 100 traces
   is a candidate for removal — its `input_schema` still pays
   tier-3 lookup cost in every session.
3. **Are there verification or search loops that might be
   hurting performance?** Per harness-research R-5 and the
   Tsinghua NLAH paper (`arXiv:2603.25723`), naive verifier
   loops in v0.1 are a known anti-pattern; the inner-loop's
   "no Critic" stance (ADR-2 §Amendment 2026-04-29 §point 5)
   captures this — adding any new loop must justify why this
   case is different.
4. **Is the control logic written in code, or in language
   (AGENTS.md / research notes / prompts), and which would be
   cheaper to change?** A control-flow step that is parsing,
   formatting, aggregation, fan-out, or file lookup is a
   deterministic Python function — an LLM call is justified
   only when the step needs reasoning that cannot be
   expressed deterministically.

A "yes / unclear" answer to any question requires either
removal of the named component or a one-paragraph
justification cited in ADR-7 §Notes (this section) at
amendment time. Part A is binary (pass/fail); Part B is the
minimalism-first review prompt every harness-component PR
citing ADR-7 inherits.

### 11. Forward-compat (deferred but shape-pinned)

The following are explicitly out of scope for v0.1 but the
shape is pinned so the migration is config-only:

- **R-3 SQLite FTS5 reuse for tool-search BM25.** When the
  v0.1 tool catalog passes ~10 tools, an
  `fs.describe_tool(name)` / `fs.search_tools(query)` pair can
  be added; the BM25 index reuses
  [ADR-4](./ADR-4-storage-backend.md) FTS5 with no new
  dependency. ADR-7 amendment.
- **R-4 `[tool_groups]` extension to ADR-6.** Add a
  `[tool_groups]` block to `~/.fa/sandbox.toml` so the user
  can disable a whole group (`fs.allow = false`) without
  editing the per-path allow-list. Lands as an ADR-6
  amendment in the same PR as the second tool group (`git.*`
  or `gh.*`). **Status 2026-05-13:** finer-grained variant
  (`[roles.<name>]` per-role tool whitelist) landed via
  [§Amendment 2026-05-13](#amendment-2026-05-13--declarative-per-role-tool-whitelist-b-new-1)
  before the second tool group; the `[tool_groups]` form
  remains shape-pinned as the coarser-grained convenience
  alternative.
- **R-6 code-execution-over-MCP.** Reserved per ADR-2
  §Amendment 2026-05-01 ("no `mcp` package dependency in
  v0.1") and ADR-6 §Re-evaluation triggers. The forward-compat
  surface is the MCP-shape `ToolSpec` / `ToolResult` already
  pinned in §2 — a future v0.2 MCP-server adapter consumes
  the same shape, no protocol churn at v0.1's clients.
- **R-9 cross-model harness transferability.** A future
  ADR-2 amendment may pin a `harness_id` ↔ model-tier
  compatibility matrix; the `harness_id` field in
  `events.jsonl` (§7) already exists. **Motivation**
  (added 2026-05-12 §Amendment):
  [`bootstrap-cost-baseline-2026-05.md`](../research/bootstrap-cost-baseline-2026-05.md)
  §1 `chain_of_custody` + §7 caveats show that agent self-report
  of `session_model` is empirically unreliable (Devin returns
  generic «Devin (Cognition AI)»; Arena.ai does not disclose
  the underlying model identity to the agent runtime).
  `harness_id` is the stable identity carrier the auto-KPI
  pipeline
  ([BACKLOG I-7](../BACKLOG.md#i-7--bootstrap-cost-as-auto-collected-kpi-uc5-blocked))
  will key on.

## Consequences

- **Positive — single source of truth for every tool PR.**
  The first implementation PR (inner-loop scaffolding,
  [HANDOFF §Next steps item 1](../../HANDOFF.md#next-steps-intended-order))
  consumes the contract verbatim — `src/fa/inner_loop/registry.py`,
  `loop.py`, `hooks/`, `tools/`, `trace.py` — and item 2
  (chunker indexer end-to-end) is the first downstream consumer of
  `fs.read_file` / `fs.list_files`. Subsequent PRs (search, edit,
  future `git.*`) cite ADR-7 §2-§4 instead of re-deriving shape.
- **Positive — closes two open amendments.** ADR-2 §Amendment
  2026-05-01 (MCP-shape convention) and ADR-6 §Tool wiring
  (sandbox-check placement) now have a concrete carrier
  rather than floating prose.
- **Positive — testable boundary.** The dispatcher
  (`src/fa/inner_loop/loop.py`) is a pure-function-ish wrapper
  around `ToolSpec.handler` + ordered hooks; unit tests can
  exercise the full request/response shape without spinning a
  real LLM.
- **Positive — minimal surface.** Five tools, two pre-tool
  hooks, one post-tool hook, two edit-shapes (one off by
  default), one full-file write, one mutable prompt layer.
  Subtraction-check (Step 4 of AGENTS.md §Pre-flight) holds:
  every artefact in this ADR is justified against an existing
  ADR amendment or research-note R-N recommendation.
- **Negative — locks in shapes before the first end-to-end
  tool PR.** Mitigated by the R-3 fixture (HANDOFF §Next steps
  item 4) which empirically validates the edit-format choice
  on each ADR-2 model and is allowed to flip the default in
  an ADR-7 amendment without rewriting the contract.
- **Negative — JSON-Schema dependency on `jsonschema`.** One
  new top-level dependency. Justified because ADR-2 §Amendment
  2026-05-01 already implicitly required it for the MCP-shape
  convention to be enforceable. Pinned in `pyproject.toml`
  alongside `markdown-it-py` and `pathspec`.
- **Negative — three-tier disclosure adds one tool-search
  abstraction (tier 3) that v0.1 does not exercise.**
  Justified because R-1 explicitly trades cheap shape-decision
  now against 1-2 days of config-only migration later vs days
  of breaking `models.yaml` and `sandbox.toml` consumers in
  v0.2 when the catalog grows.
- **Neutral — prompt-only Coder tier obligation.** Prompt-only
  models remain a supported ADR-2 shape (§Amendment 2026-04-29).
  This ADR specifies the native-tool dispatch path; any
  prompt-only adapter (e.g. a JSON-blob-in-content workaround)
  MUST translate the model output into the same internal
  `request` / `response` shape pinned in §2 before it reaches
  the registry. The translation lives in the adapter, not in
  per-tool handlers — handlers see a uniform `ToolResult`.
- **Re-evaluation triggers (when to revisit this ADR).**
  - **HANDOFF §Next steps item 4 fixture lands** and shows
    one of the five ADR-2 models clearly prefers
    `apply_patch` over `edit_file`. Action: ADR-7 §Amendment
    flipping the default edit-shape.
  - **Tool catalog passes 10 tools.** Action: implement
    `fs.search_tools` (R-3 BM25 reuse).
  - **Approval / HITL friction.** If the optional `ApprovalHook`
    is consistently set to `ask` and the user reports
    cognitive overhead, evaluate moving to a write-batching
    primitive (`post_run` hook) — that lands as a v0.2 amendment
    because it requires the `post_run` hook point currently
    deferred.
  - **`run_command` lands.** ADR-6 §Re-evaluation triggers
    already covers the sandbox half; ADR-7 amendment will add
    the tool to §3 catalog plus an `output_schema` for the
    stdout/stderr/exit-code shape.
  - **FA's own mid-tier inner-loop scaffolding ships (Phase M;
    [BACKLOG I-8](../BACKLOG.md#i-8--mid-tier--first-agents-own-harness-bootstrap-re-test))**
    (added 2026-05-12 §Amendment). Action: re-run the
    ADR-7-prep bootstrap prompt on FA's own harness per
    [`bootstrap-cost-baseline-2026-05.md`](../research/bootstrap-cost-baseline-2026-05.md)
    §9 trigger 5. Success criterion: the 6-file irreducible
    core reproduces on FA's own harness. Failure to reproduce
    re-opens routing-design proposals A / D / H (deferred per
    BACKLOG I-8 §First concrete step once unblocked).
- **Follow-up work this unlocks.**
  - `src/fa/inner_loop/registry.py` — `ToolSpec` dataclass,
    `register(spec)`, `lookup(name)`, lazy schema cache.
  - `src/fa/inner_loop/loop.py` — runtime loop (§1) +
    JSON-Schema validation (§5) + hook chain runner (§8).
  - `src/fa/inner_loop/hooks/` — `SandboxHook`,
    `ApprovalHook`, `AuditHook`.
  - `src/fa/inner_loop/tools/` — one file per tool from §3
    catalog.
  - `src/fa/inner_loop/trace.py` — `events.jsonl` writer +
    `hot.md` summariser (§7).
  - **HANDOFF §Next steps item 2 (chunker indexer end-to-end)**
    is now unblocked; the indexer is a `fs.*`-shaped tool the
    Coder runs via the registry rather than a stand-alone
    CLI module.
  - `docs/glossary.md` — add `Tool registry`, `ToolSpec`,
    `Hook (pre-tool / post-tool)`, `events.jsonl`, `hot.md`
    entries (some already present per AGENTS.md §Pre-flight
    Step 2 sweep — missing ones added by this PR).
  - **BACKLOG forward-references unblocked by this ADR**
    (added 2026-05-12 §Amendment).
    - [BACKLOG I-1](../BACKLOG.md#i-1--planner-picks-needed-skills--tool-calls-at-planning-stage)
      (Planner pre-selects tool-calls at planning stage) —
      unblock-trigger «ADR-7 merges **and**
      `src/fa/inner_loop/registry.py` module lands with a `ToolSpec`
      dataclass plus loader» is half-satisfied by this ADR;
      the other half lands in the chunker-indexer
      implementation PR.
    - [BACKLOG I-2](../BACKLOG.md#i-2--agent--sub-agents-for-context-load-reduction)
      (sub-agents for context-load reduction) — needs Phase M
      runner consuming this contract; the contract pre-defines
      the `ToolResult.artifacts[]` shape so a sub-agent
      merge-protocol can cite event IDs.
    - [BACKLOG I-3](../BACKLOG.md#i-3--dispatcher-llm-lazy-load-skills--collect-repo-parts-on-the-fly)
      (dispatcher LLM, lazy-load skills) — depends on I-1 +
      skills system (future ADR-8); §6 three-tier disclosure
      is the shape a dispatcher would key on.
    - All three are AGENTS.md PR Checklist rule #11
      mitigations (a) / (b) / (c) explicitly «tracked in
      BACKLOG.md until ADR-7 + ADR-8 land» — this ADR closes
      the ADR-7 half.

## Amendments

### Amendment 2026-05-12 — cross-reference bootstrap-cost-baseline measurement evidence

**Source.** Measurement-evidence note
[`research/bootstrap-cost-baseline-2026-05.md`](../research/bootstrap-cost-baseline-2026-05.md)
landed on `main` in PR #5 (initial 4-session Devin baseline)
and PR #7 (3-session Arena.ai extension + BACKLOG I-6/I-7/I-8)
**after** this ADR's draft was written. The bootstrap-cost
note is the readability-test measurement counterpart to this
ADR's contract design — it ran the same single-message
ADR-7-prep prompt across six independent sessions × two
agent harnesses (3 Devin + 3 Arena.ai) × ≥4 distinct model
selections and recorded calls / files / context tokens per
session. The original ADR-7 draft cited four research notes
but **not** the bootstrap-cost baseline, leaving the inner
loop's three-tier disclosure (§6), static layered prompt
(§9), `harness_id` field (§7), and re-evaluation triggers
(§Consequences) without empirical grounding.

**Change.** Six inline cross-references added to the ADR;
**no** shape decisions changed:

1. **§6 Tool disclosure** — empirical-backing paragraph
   citing baseline §3 (6-file irreducible core: all six
   bootstrap sessions reached «ready-to-draft» on tier-1 +
   tier-2 material alone; **none** loaded tier-3 schemas).
2. **§7 Trace** — future-KPI-consumption paragraph linking
   `events.jsonl` schema to
   [BACKLOG I-7](../BACKLOG.md#i-7--bootstrap-cost-as-auto-collected-kpi-uc5-blocked)
   (auto-collected bootstrap-cost KPI) as the downstream
   consumer once UC5 eval-harness lands.
3. **§9 Loop invariant** — empirical context-budget paragraph
   citing baseline §5 (Devin sessions converging to ~80–95 K
   total context, Arena.ai 70–95 K — all within the
   [AGENTS.md PR Checklist rule #11](../../AGENTS.md#pr-checklist)
   ≤100 K envelope).
4. **§11 R-9 cross-model harness transferability** — motivation
   block citing baseline §1 `chain_of_custody` + §7 caveats
   (agent self-report of `session_model` empirically
   unreliable — Devin returns generic «Devin (Cognition AI)»;
   Arena.ai does not disclose underlying model). `harness_id`
   is the stable identity carrier.
5. **§Consequences re-evaluation triggers** — 5th trigger
   added: «FA's own mid-tier inner-loop scaffolding ships
   (Phase M;
   [BACKLOG I-8](../BACKLOG.md#i-8--mid-tier--first-agents-own-harness-bootstrap-re-test))».
   Action: re-run ADR-7-prep bootstrap prompt on FA's own
   harness. Success criterion: 6-file irreducible core
   reproduces; failure re-opens routing proposals A / D / H.
6. **§Consequences follow-up work** — BACKLOG forward-
   references bullet listing I-1 / I-2 / I-3 (AGENTS.md rule
   #11 mitigations a / b / c, explicitly «tracked in BACKLOG
   until ADR-7 + ADR-8 land» — this ADR closes the ADR-7 half).

**Why not a shape change.** The baseline empirically validates
the v0.1 contract; it does not invalidate any decision. The
6-file irreducible core reproduces across two harnesses and
≥4 model selections — this is independent evidence that the
tier-1 + tier-2 routing surface works. The amendment is
documentation-only (no §3 catalog change, no §2 ToolSpec
shape change, no §8 hook pipeline change).

**Subtraction-check.** EXEMPT per AGENTS.md §Pre-flight
Step 4 (documentation-only amendment with no new artefact;
six new cross-references to an already-merged research note).

**Re-measurement.** Per `bootstrap-cost-baseline-2026-05.md`
§9 trigger 5 (= BACKLOG I-8), this ADR's amendment should be
revisited once FA's own mid-tier harness ships and the
bootstrap re-runs on it. If the 6-file irreducible core does
**not** reproduce on FA's own harness, the empirical-backing
paragraph in §6 must be qualified (works on external
harnesses; needs separate evidence for FA's own).

### Amendment 2026-05-13 — Declarative per-role tool whitelist (B-NEW-1)

**Source.** Inspiration note
[`research/soviet-code-inspiration-2026-05.md`](../research/soviet-code-inspiration-2026-05.md)
§0 R-1, §6.1, §3 Pattern #1 — deep-dive of
`Disentinel/soviet-code` (npm-published v1.964.0, systemd-in-prod
reference impl). The pattern ships 9 agent profiles × declarative
`allowed_tools` + `extra_dirs` blocks, passed verbatim as
`--allowedTools` / `--add-dir` to the Claude CLI subprocess.
FA-equivalent: per-role allow-list in `~/.fa/sandbox.toml`
enforced at the dispatcher boundary.

**Decision.** Extend `~/.fa/sandbox.toml` (defined by
[ADR-6](./ADR-6-tool-sandbox-allow-list.md), see
[ADR-6 §Amendment 2026-05-13](./ADR-6-tool-sandbox-allow-list.md#amendment-2026-05-13--roles-block-in-sandboxtoml))
with a `[roles.<name>]` block specifying tools each role may
invoke:

```toml
[roles.planner]
allowed_tools = ["fs.read_file", "fs.list_files", "fs.grep"]
allowed_dirs  = []  # empty = inherit ADR-6 sandbox-root

[roles.coder]
allowed_tools = ["fs.read_file", "fs.list_files", "fs.grep",
                 "fs.write_file", "fs.edit_file"]
allowed_dirs  = []

[roles.debug]
allowed_tools = ["fs.read_file", "fs.list_files", "fs.grep"]
allowed_dirs  = []

[roles.eval]
allowed_tools = ["fs.read_file", "fs.list_files"]
allowed_dirs  = []
```

The four role names match
[ADR-2](./ADR-2-llm-tiering.md) static tier-routing
(Planner / Coder / Debug / Eval). Role names are tier names; the
role-to-tier mapping is the ADR-2 contract, not this amendment.

**Backward-compat default.** If `[roles.<active_role>]` is
absent, the role inherits the full §3 tool catalog
(`fs.read_file`, `fs.list_files`, `fs.edit_file`, `fs.write_file`,
`fs.grep`). Existing `sandbox.toml` files without `[roles]`
blocks continue to work unchanged.

**Enforcement point.** The dispatcher
(`src/fa/inner_loop/loop.py`, lands with HANDOFF §Next steps
item 1) MUST check:

```text
if active_role in roles_config
   and tool_name not in roles_config[active_role].allowed_tools:
    return ToolResult(
        ok=False,
        error=ToolError(
            code="E_ROLE_WHITELIST",
            message=f"tool {tool_name!r} not in role {active_role!r} whitelist",
        ),
    )
```

BEFORE the `pre_tool` hook chain fires. On reject, no `pre_tool`
budget is consumed; the failure surfaces as one
`role_whitelist_reject` event in §7 trace.

**Why now (vs. defer to v0.2 multi-role).** Cheap to land:
~70 LOC across 6 files, 0 new dependencies, 0 production-code
changes (the impl ships with the inner-loop scaffolding PR per
HANDOFF §Next steps item 1). Empirically validated by
Soviet-Code v1.964.0 (npm-published, in-prod for months).
Closing §11 R-4 forward-compat: per-role is the natural
finer-grained extension of `[tool_groups]` and lands in a single
ADR amendment instead of two coordinated ones.

**Why not prompt-only.** Status quo enforces "Planner does not
write files" through prompt instructions to the Planner role.
This is not mechanically verifiable: any hallucinated
`fs.write_file` call from the Planner is currently caught only
by §8 `SandboxHook` (which guards the **path**, not the
**role-tool pairing**). Declarative role whitelist adds the
mechanical pairing check the prompt-only approach cannot.

**Subtraction-check (AGENTS.md §Pre-flight Step 4 / rule #10).**

1. **Does this duplicate an existing rule?** No. §11 R-4
   `[tool_groups]` was shape-pinned but not landed. §8
   `SandboxHook` enforces path, not (role, tool) pairing.
2. **Can the LLM do this without the rule?** Partial. Prompt
   instructions can ask Planner not to write, but the
   constraint is not mechanically verifiable.
3. **Is the rule narrow enough?** Yes. Single TOML block,
   single dispatcher check, zero runtime cost when `[roles]`
   absent (inherits full catalog).
4. **Will this rule have a reader?** Yes. Dispatcher
   (`src/fa/inner_loop/loop.py`) reads on every tool request;
   reject events documented in §7 trace; consumers are the
   inner-loop unit tests and the future eval-harness
   ([BACKLOG I-7](../BACKLOG.md#i-7--bootstrap-cost-as-auto-collected-kpi-uc5-blocked)).

**Files changed (this PR, knowledge-layer only).**

- `knowledge/adr/ADR-6-tool-sandbox-allow-list.md` —
  §Amendment 2026-05-13 with schema spec.
- `knowledge/adr/ADR-7-inner-loop-tool-registry.md` — this
  block + §11 R-4 status update.
- `knowledge/adr/DIGEST.md` — ADR-6 + ADR-7 row updates.
- `knowledge/trace/exploration_log.md` — Q-7 amendment block.
- `knowledge/BACKLOG.md` — I-7 + I-8 prior-art
  enforcement note (DPC ADR-015 cross-reference).
- `HANDOFF.md` — ADR-7 amendment line update.

**Re-evaluation triggers (this amendment).**

- **Single `E_ROLE_WHITELIST` rejection observed in production**
  on a path the user expected to be allowed. Action: investigate
  the user's mental model first (prompt error vs config error);
  only widen the role whitelist after the incident is
  understood.
- **v0.2 multi-role expands past ~6 roles** (e.g. Researcher,
  Reviewer added). Action: revisit `allowed_dirs = []` default
  (currently inherits ADR-6 sandbox-root); per-role path
  scoping may become worth the config-surface cost.
- **Soviet-Code reference impl deprecates the pattern.** Action:
  re-evaluate whether the FA adoption still holds. Unlikely
  (npm-published, systemd-in-prod for months) but documented.

### Amendment 2026-05-20 — Retry-budget invariant, intra-role T=1.0, LLM-using-hook family-disjoint rule

**Source.** Implementation roadmap
[`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
§R-7 / §R-28 / §R-29 / §R-30 (Wave 0, docs-only). Empirical
evidence: correlated-LLM-errors research note
[`research/correlated-llm-errors-and-ensembling-2026-05.md`](../research/correlated-llm-errors-and-ensembling-2026-05.md)
§4.1 (Nitarach P-3 finding: `T=1.0` decorrelates retry-sample
errors — `ρ̂≈−0.12` vs `T=0.0` `ρ̂≈+0.6`) + §6 R-7/R-8/R-9.

**Problem.** The original Decision pinned §1 step 8 «hard cap on
iterations to prevent runaway loops» but left the cap value and
the retry-sampling temperature as future-implementation decisions.
The accompanying ADR-2 §Amendment 2026-04-29 closed the «no
auto-escalation» question and left **intra-role** retries
allowed, but did not pin the retry parameters. Without explicit
invariants, the inner-loop scaffolding PR
([HANDOFF §Next steps item 1](../../HANDOFF.md#next-steps-intended-order))
would land magic-numbers in hook code, with no audit trail tying
the choice back to research evidence. The §8 Hook pipeline is
silent on whether a hook may itself call an LLM (e.g. a future
LoopGuard middleware asking a second model to grade loop-
evidence); §11 R-9 already flagged cross-model harness
transferability but did not pin the hook-internal LLM choice.

**Decision (additive to §1, §5, §8; no shape change to §2 /
§3 / §6 / §7).**

1. **Retry budget is config-bounded.** Every retry loop in the
   inner-loop (intra-role retry, tool-error retry, blocker
   retry-after-resume) reads its hard cap from
   `~/.fa/config.yaml` — never from a constant in hook code.
   The dispatcher (`src/fa/inner_loop/loop.py`, lands with
   inner-loop scaffolding) refuses to start a session when a
   required retry-cap key is missing rather than fall back to a
   silent default. This matches §1 step 8 «hard cap …
   prevent runaway loops» and gives the §7 trace an
   `events.jsonl` row tying every cap to a config version.
2. **`max_iterations` cap default = 6.** Per R-30 / YT-4
   empirical anchor: GPT-3.5 Turbo completed a multi-step Hacker
   News upvote task within 6 iterations when the harness was
   correct (DSV gate + login middleware). Without the harness,
   the same model hallucinated success on step 2. The cap is a
   default in `config.yaml`, not a hard-coded constant; user
   may raise it explicitly with a written justification in the
   session's `hot.md` opening block. Treat 6 as the «minimum
   non-trivial harness» anchor — raise it when measured, never
   when guessed.
3. **Intra-role retry temperature default `T=1.0`.** Per R-28 /
   Correlated §4.1 finding: retrying with the **same**
   temperature simply re-samples the same hypothesis-distribution
   peak. `T=1.0` forces sample diversity so the retry can
   propose a different candidate. Default applies only to the
   **retry sample** — first-attempt temperature stays at the
   role's configured value (`~/.fa/models.yaml`). Cross-tier
   escalation remains forbidden per ADR-2 §Decision and
   §Amendment 2026-04-29; this rule sits **inside** the
   ADR-2-permitted «intra-role retry-loop» envelope.
4. **LLM-using hooks MUST use family ≠ acting-role.** Generalises
   ADR-2 §Amendment-to-land (R-19 below: «Eval-role
   provider/family disjoint from Planner and Coder») to any
   §8 hook that calls an LLM. The rule is vacuous in v0.1
   because both `pre_tool` hooks (`SandboxHook` from ADR-6,
   optional `ApprovalHook`) and the lone `post_tool`
   `AuditHook` are deterministic Python functions — no LLM
   call inside a hook today. The rule **lands ahead of the
   first LLM-using hook** so future amendments (e.g. a v0.2
   `LoopGuard` middleware grading retry-evidence with a second
   model) inherit the family-disjoint constraint by default.
   Without it, a same-family judge replicates the same error
   the acting-role is being judged for (the Cornell P-1 +
   Simula P-2 finding: same-family ensembles have ρ̂ ≈ +0.6,
   defeating ensemble error-decorrelation).
5. **Sub-agent invocation rules (BACKLOG I-2 prep).** Cross-link
   to R-23 / Aperant item 7: when BACKLOG I-2 lands the
   sub-agent dispatch primitive, sub-agents MUST use
   `generateText` (not streaming) because output feeds the
   orchestrator's context not the UI; the sub-agent tool set
   MUST exclude any `SpawnSubAgent` tool (recursion); and
   `SUBAGENT_MAX_STEPS` MUST be ≤ 100. Captured here so the
   inner-loop scaffolding PR cannot accidentally diverge from
   the eventual sub-agent ADR; cross-referenced from
   [BACKLOG I-2](../BACKLOG.md#i-2--agent--sub-agents-for-context-load-reduction)
   so the constraint is visible at the read-side.

**Why these belong in one amendment.** All four rules govern
the **retry / hook-LLM** axis — they share the §8 hook
pipeline as enforcement surface, share the §1 step 8 «hard
cap» framing, and share the same source-note batch
(correlated-LLM-errors §6 R-7/R-8/R-9 + borrow-roadmap §R-7
/ §R-28 / §R-29 / §R-30). Splitting into four amendments
would force readers of any one to re-derive the others.

**Why not pin the v0.2 LLM-using-hook contract here.** §8
already says `pre_run` / `post_run` / `on_event` are deferred
to v0.2 — the LLM-using-hook contract is a v0.2 amendment
gated by the first concrete use-case (e.g. ADR-8
HookRegistry's `LoopGuard` or a `CriticHook` after the v0.2
Critic role lands). This amendment fixes the **family-
disjoint invariant** so the v0.2 amendment cannot regress.

**Subtraction-check (AGENTS.md §Pre-flight Step 4 / rule #10).**

1. **Removing what makes this redundant?** None — §1 step 8
   names the cap but not the value; §8 names hooks but not
   LLM-using hooks; ADR-2 §Amendment 2026-04-29 allows
   intra-role retry but not the retry temperature.
2. **Capability lost if omitted?** Magic-number retry budgets
   in hook code (no audit trail), `T=0.0` retries (no
   diversity), same-family LLM-judge of same-family acting-
   role (correlated errors), and a sub-agent dispatcher that
   re-derives invocation rules per first-use.
3. **OSS precedent for not having it?** Ampcode «three bare
   functions» harness does not pin retry temperature — it
   targets one tier (Claude) and accepts the elite-tier
   default. FA spans four tiers per ADR-2 and cannot inherit
   that elision.
4. **Step-as-function?** YES for rules 1 / 2 / 3 / 5 — all are
   config reads + arithmetic + dispatcher checks, no LLM
   needed. Rule 4 is the **negation** of step-as-function — it
   constrains the LLM-using-hook future case, not creating a
   new LLM call.

**Files changed (this PR, knowledge-layer only).**

- `knowledge/adr/ADR-7-inner-loop-tool-registry.md` — this
  amendment block.
- `knowledge/adr/ADR-2-llm-tiering.md` — §Amendment 2026-05-20
  (R-19 / R-27 part 1; family-disjointness for Eval-role and
  Cornell/Simula primary-source citation).
- `knowledge/adr/DIGEST.md` — ADR-7 row amendments bullet.
- `knowledge/trace/exploration_log.md` — Q-7 amendment block.
- `knowledge/BACKLOG.md` — I-2 sub-agent invocation rules
  paragraph (R-23 captured here for read-side discoverability).
- `HANDOFF.md` — ADR-7 amendment line update.

**Re-evaluation triggers (this amendment).**

- **First LLM-using hook PR lands.** Action: split rule 4 into
  a v0.2 amendment with explicit family-pair examples
  observed in eval traces.
- **A FA-on-FA bootstrap run hits `max_iterations = 6` cap on
  a task we expect to finish within budget.** Action:
  re-measure cap against the failing task; raise default
  only if new measurement shows ≥ 2× the previous anchor.
- **Intra-role retry with `T=1.0` shows worse pass-rate than
  `T=0.7` on UC1 eval (when UC5 lands).** Action: re-open the
  retry-temperature choice with the eval delta as evidence;
  the Correlated §4.1 finding holds in code-gen domain but
  remains pending replication in FA-specific workload.

### Sub-amendment 2026-05-21 — R-45 cost guardian + `cost_observation` event-kind

**Source.** Implementation roadmap
[`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
§R-45 (Wave 3 — observability + gating). Documentation-only
shape change to §7 «`events.jsonl`» event-kind enumeration;
no shape change to §1 inner-loop driver, §5 input
validation, §8 hook pipeline (R-45 is one
`GuardMiddleware` subclass following the existing contract
— ADR-8 is the contract anchor; this ADR's §7 is the
schema anchor).

**Decision (extension to §7 «`events.jsonl`» extension-kinds
enumeration).**

1. **New extension kind `cost_observation`** — one row per
   recognised `cost=…` artifact in `ToolResult.artifacts`.
   Emitted by `fa.observability.cost_guardian.CostGuardian`
   when an `EventLog` is wired into the constructor. `actor`
   = `"hook"`; `tool_name` / `tool_call_id` pin to the
   `ToolCall` the artifact came from; `content` carries the
   per-call `{tokens_in, tokens_out, usd}` triple AND the
   post-add `{rollup_tokens_in, rollup_tokens_out,
   rollup_usd, rollup_samples}` snapshot so a reader can
   reconstruct the budget trajectory without replaying.
2. **Baseline M-1 dormancy.** Baseline `fs.read_file` /
   `fs.write_file` / `fs.run_bash` never emit the
   `cost=…` artifact, so the kind is dormant until the T-2
   LLM driver lands the artifact emitter. The CostGuardian
   itself is wired into the smoke entrypoint (`fa
   inner-loop-smoke`) so the chain shape is stable across
   the T-2 cut-over.
3. **Cost-budget anchor.** `RuntimeLimits.cost_budget_usd`
   gains the tri-mode semantics — `None` = unbounded (no
   gating), `0.0` = observe-only (extractor still runs,
   gate never denies), `> 0` = hard cap. Default is `None`
   because the M-1 substrate has no cost signal on baseline
   tools; pinning a concrete USD default would silently
   shape the first T-2 runs before baseline USD is
   measured. The YAML loader parses `cost_budget_usd` as
   `float` (every other knob is an integer count); the
   `_FLOAT_KEYS` set in `runtime_limits.py` documents the
   per-key parse routing.

**Subtraction-check (AGENTS.md §Pre-flight Step 4 / rule #10).**

1. **Removing what makes this redundant?** None — no
   existing artefact accumulates per-call cost.
   `RuntimeLimits.max_iterations` caps round count, not
   USD; `LoopGuard` caps repetition, not spend. The
   cost-budget axis is unaddressed before this PR.
2. **Capability lost if omitted?** With the T-2 LLM
   driver landing next, a runaway loop or pricing change
   can burn arbitrary USD; the M-1 retry/blocker stack
   has no visibility into spend and cannot gate on it.
3. **OSS precedent for not having it?** Ampcode «three
   bare functions» harness has no spend gate (single-user,
   local, single-model). DPC mainline integrates spend
   via Anthropic's own usage headers — direct provider
   path. FA's multi-provider + multi-tier scope makes a
   harness-side gate load-bearing where a provider-side
   gate is sufficient for both OSS precedents.
4. **Step-as-function?** YES — extractor + accumulator
   are pure Python; the gate is one comparison. No LLM
   call introduced.

**Files changed (this sub-amendment).**

- `src/fa/observability/cost_guardian.py` — new module
  (`CostObservation`, `CostRollup`, `CostExtractor`,
  `default_cost_extractor`, `CostGuardian` subclass of
  `GuardMiddleware` attaching to both `BEFORE_TOOL_EXEC`
  and `AFTER_TOOL_EXEC`).
- `src/fa/observability/__init__.py` — public exports.
- `src/fa/inner_loop/runtime_limits.py` —
  `DEFAULT_COST_BUDGET_USD`, `cost_budget_usd` field on
  `RuntimeLimits`, `_FLOAT_KEYS` parse routing, YAML
  loader extension.
- `src/fa/inner_loop/state.py` — `cost_observation` row
  in §«Extension kinds» docstring.
- `src/fa/cli.py` — `CostGuardian` registration in
  `_cmd_inner_loop_smoke` (between the blocker chain and
  the VerifierObserver).
- `tests/test_cost_guardian.py` — 12-test scope
  (observation/rollup invariants, extractor parse paths,
  all three gate modes, end-to-end via `run_session`).
- `knowledge/adr/ADR-7-inner-loop-tool-registry.md` —
  this sub-amendment.
- `knowledge/adr/DIGEST.md` — ADR-7 row Amendments
  bullet extended.
- `knowledge/trace/exploration_log.md` — Q-7 amendment
  block appended.
- `knowledge/llms.txt` — routing entries for the two
  new files.
- `docs/glossary.md` — «cost guardian» row added.
- `HANDOFF.md` — Wave-3 stack #1 entry + §Current state
  ADR-7 amendments bullet.

**Re-evaluation triggers (this sub-amendment).**

- **T-2 LLM driver lands and emits `cost=…` artifacts on
  every LLM call.** Action: re-measure baseline USD per
  smoke run; consider pinning `DEFAULT_COST_BUDGET_USD` to
  a non-`None` value once enough sessions have a baseline.
- **A second observability middleware emerges (token
  meter, latency tracker, …).** Action: factor the
  `default_cost_extractor` artifact-parsing helper into a
  shared `fa.observability.artifacts` module so both
  middlewares share the same artifact-parsing contract.

## References

- [HANDOFF.md §Next steps item 1](../../HANDOFF.md#next-steps-intended-order) — the explicit six-surface scope this ADR pins.
- [`research/efficient-llm-agent-harness-2026-05.md`](../research/efficient-llm-agent-harness-2026-05.md) §0 (R-1..R-8) + §10 (contract sketch).
- [`research/bootstrap-cost-baseline-2026-05.md`](../research/bootstrap-cost-baseline-2026-05.md) §3 (6-file irreducible core), §5 (context-saturation), §6 (baseline range), §9 (re-measurement triggers) — measurement counterpart, cited from §6 / §7 / §9 / §11 / §Consequences in this ADR's §Amendment 2026-05-12.
- [`research/cross-reference-ampcode-sliders-to-adr-2026-04.md`](../research/cross-reference-ampcode-sliders-to-adr-2026-04.md) §10 R-1, R-3, R-7.
- [`research/semi-autonomous-agents-cross-reference-2026-05.md`](../research/semi-autonomous-agents-cross-reference-2026-05.md) §7.1, §7.3, §8.4, §8.5.
- [`research/how-to-build-an-agent-ampcode-2026-04.md`](../research/how-to-build-an-agent-ampcode-2026-04.md) — ampcode three-tool baseline.
- [ADR-2 §Amendment 2026-04-29](./ADR-2-llm-tiering.md#amendment-2026-04-29--tool_protocol-field--native-by-default-v01-inner-loop-without-critic) — `tool_protocol` field + no Critic in v0.1.
- [ADR-2 §Amendment 2026-05-01](./ADR-2-llm-tiering.md#amendment-2026-05-01--mcp-forward-compat-tool-shape-convention) — MCP-shaped JSON-RPC convention.
- [ADR-6 §Tool wiring](./ADR-6-tool-sandbox-allow-list.md#tool-wiring) — five-tool catalog + sandbox-gate placement.
- [`project-overview.md` §1.2](../project-overview.md#12-enforceable-principle--minimalism-first) — minimalism-first principle (the §10 acceptance block is its enforceable form at the inner-loop boundary).
