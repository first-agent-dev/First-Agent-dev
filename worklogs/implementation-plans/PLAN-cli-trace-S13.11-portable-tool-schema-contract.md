# PLAN: S13.11 — portable generic-provider tool-schema contract

Plan-ID: `PLAN-cli-trace-S13.11-portable-tool-schema-contract`

**Status:** READY

**Depth:** P2 — cross-module provider/tool contract repair; no service,
dependency, state migration, or deployment-topology change.

**Revision:** v2 (2026-08-15)

**Changed since v1:** adversarial review removed the speculative derived wire
schema and the unrelated event-type migration. V2 keeps one portable
`ToolSpec.input_schema` authority, deletes the ignored `fs_search.types`
parameter, removes optional nullable unions at their source, adds a closed
provider-schema authoring gate, fixes exact provider selection in live
conformance, shares the production tool-registry assembly with CONF-8, and
repairs the existing nested-tool cache-key bug.

**Parent context:**
[`PLAN-cli-trace-S13-multi-provider-conformance.md`](./PLAN-cli-trace-S13-multi-provider-conformance.md)
and
[`PLAN-cli-trace-S13.10-tool-name-sanitization.md`](./PLAN-cli-trace-S13.10-tool-name-sanitization.md).

**Main-plan trajectory:** managed-workspace readiness is already live-verified.
This slice repairs the first downstream provider request so a natural default
coder task can run, then hands control back to the workspace-readiness closure
task. It does not reopen readiness design or PR/governance ceremony.

**Production evidence:** deployed merge
`3c5145bde67fb80623a2bb9322202ec131eecba2`; default coder route
`aigate/gemini-3-flash-preview`.

---

## Preflight and adversarial-review log

### Source authority

The exact deployed merge archive was compared byte-for-byte with the local
planning workspace. Every source/test file examined for this slice was
identical, including `registry.py`, `prompt.py`, `prompt_composer.py`,
`profiles.py`, `tools/__init__.py`, `fs_search.py`, provider adapters,
conformance, CLI, coder loop, output, and their named tests.

### Composition roots read

- Host delegation: `scripts/fa:_delegate_to_agent`.
- Natural run: `src/fa/cli.py:_cmd_run`.
- Role selection: `src/fa/cli.py:_build_role_registry`.
- Production tool assembly: `_cmd_run` builds a role registry at
  `cli.py:2564`, then adds `pr_prepare` at `cli.py:2566-2589`.
- Registry/local validation: `src/fa/inner_loop/registry.py:ToolSpec`,
  `ToolRegistry.register`, `ToolRegistry.validate`, `ToolRegistry.dispatch`.
- Profile/tool builders: `src/fa/inner_loop/profiles.py:_build_tool_builders`,
  `build_registry_for_role`; `src/fa/inner_loop/tools/__init__.py` registry
  builders and `_register_extra_tools`.
- Provider-visible tool emitter:
  `src/fa/inner_loop/prompt.py:render_tool_specs`.
- Prompt/cache consumer:
  `src/fa/inner_loop/prompt_composer.py:_hash_tool_defs_stable`,
  `build_prompt_parts_v2`.
- Session loop consumer: `src/fa/inner_loop/coder_loop:_drive_session_inner`.
- Provider config/chain/adapters:
  `src/fa/providers/config.py:load_models_config_from_path`,
  `src/fa/providers/chain.py:ChainConfig.validate`, `ProviderChain.request`,
  `openai_compat.py`, `anthropic.py`, `mistral.py`, and
  `mistral_conversations.py`.
- Tool-aware provider qualification target:
  `src/fa/providers/conformance.py` and
  `src/fa/cli.py:_run_live_conformance`.
- Existing runner: `src/fa/providers/live_runner.py:run_matrix`.
- Connectivity-only probe: `src/fa/cli.py:_cmd_probe`.
- Egress boundary: `src/fa/egress_proxy/server.py` forwards request-body bytes
  unchanged.

### Direct callers/dependents read

- `render_tool_specs` has one production caller:
  `coder_loop.py:421`; its other callers are tests.
- `build_baseline_registry`, `build_planner_registry`, and
  `build_eval_registry` feed `_build_role_registry`; many tests also use them.
- `RequestInfo.tools` is passed unchanged by OpenAI and Mistral adapters;
  Anthropic and Mistral Conversations rename only the envelope.
- `default_cases()` feeds both offline conformance and live `run_matrix`.
- `_case_to_request` currently composes tool-free requests.
- The live runner indexes durable completion by case position; appending case 8
  preserves existing CONF-1..7 identities.

### Gold tests read

- `tests/test_inner_loop_registry.py` and
  `tests/test_inner_loop_validation.py` — schema definition and dispatch
  validation.
- `tests/test_fs_search.py` — current handler behavior and missing schema
  portability coverage.
- `tests/test_prompt.py` — byte-stable verbatim tool rendering.
- `tests/test_prompt_caching_per_role.py` and
  `tests/test_s10c_composer_extras_contract.py` — cache and real tool block.
- `tests/test_cli.py` — actual `_cmd_run` transport body, session, and readiness
  ordering.
- `tests/test_quality_slice_coverage.py` — optional-tool failure/fallback
  behavior.
- `tests/conformance/test_offline_matrix.py`,
  `test_live_executor.py`, and `test_live_runner.py` — case identity,
  transport calls, proxy rewrite, result persistence, and exit authority.
- `tests/test_s13_strict_transport.py` — positive-control transport pattern.

### Live evidence

| Run | Shell form | Task | Upstream result | FA result |
|---|---|---|---|---|
| L1 | single quoted | plan closure | 400 names `exclude_dirs` beside `any_of` | request_shape, in/out=0 |
| L2 | double quoted | same, shell-expanded | 400 names `types` beside `any_of` | request_shape, in/out=0 |
| L3 | single quoted | explicitly use `fs_search` | 400 names `types` beside `any_of` | request_shape, 62.8s, in/out=0 |

L3 removes shell quoting as a causal explanation. The complete coder tool set is
sent before the model can choose `fs_search`.

### Confirmed defects

1. **CD1 — incompatible source schema.** The only production `type: [...]`
   declarations are `fs_search.glob`, `types`, and `exclude_dirs`
   (`fs_search.py:123-135`). The two array unions are independently rejected
   live.
2. **CD2 — dead provider parameter.** `types` is described as reserved,
   accepted, and ignored (`fs_search.py:83-85,125-129,580-583`). It adds tokens
   and one live failure with no product behavior.
3. **CD3 — no portable authoring contract.** `ToolRegistry.register` checks only
   whether `fastjsonschema` can compile the schema
   (`registry.py:135-146`). Valid broad JSON Schema can still be provider-invalid.
4. **CD4 — contract errors can be swallowed.** Profile registration logs and
   skips any builder/register exception (`profiles.py:289-294`); extra and
   fallback registry paths catch broad `Exception`
   (`tools/__init__.py:100-188,198-241`).
5. **CD5 — conformance omits tools.** `_compose` and `_case_to_request` pass
   `tool_defs=[]`, and `RequestInfo.tools` remains empty
   (`conformance.py:71-87,254-284`).
6. **CD6 — `--provider` does not select a provider.** The CLI validates the
   whole config/key set, loads the whole coder chain, and uses the argument only
   as a runner label; no chain-entry filter exists
   (`config.py:303-305`; `cli.py:3017-3041,3075-3084`).
7. **CD7 — no shared exact tool-corpus producer.** `_cmd_run` adds `pr_prepare`
   after role-registry construction. An independent conformance reconstruction
   can silently omit it (`cli.py:2564-2589`).
8. **CD8 — cache key ignores real tool names/schemas.** The hash reads flat
   `name` and `input_schema` (`prompt_composer.py:33-43`), while production
   supplies nested `function.name` and `function.parameters`
   (`prompt.py:947-966`). Two different rendered tools both produced hash
   `42d472d1` in a controlled probe.
9. **CD9 — existing live evidence cannot close natural-run usability.** Probe is
   intentionally `tools=()` (`cli.py:3226-3231`); a tool-aware provider request
   and one natural `fa run` remain required.

### Confirmed v1 plan defects

1. **PD1 — premature abstraction.** V1 introduced a full→wire projector and
   silently stripped defaults, bounds, and `additionalProperties` without a live
   rejection for those keywords.
2. **PD2 — wrong default semantics.** `ToolRegistry.validate` validates a copied
   dict and discards the default-filled return (`registry.py:164-175`). Handler
   defaults come from handler code, not from schema defaults.
3. **PD3 — false cache premise.** V1 assumed schema bytes already affected the
   cache key; CD8 proves they do not.
4. **PD4 — incomplete operator-event repair.** `api_retry` has four producers.
   Both request-shape failure (`coder_loop.py:617-644`) and terminal chain
   exhaustion (`coder_loop.py:1416-1445`) claim a retry that does not happen.
   Renaming one site leaves the same invariant broken.
5. **PD5 — guessed corpus assembly.** V1 required conformance to reconstruct
   production tools rather than sharing the production assembly function.
6. **PD6 — false provider attribution.** V1’s provider matrix trusted the
   `--provider` label without fixing CD6.
7. **PD7 — excessive blast radius.** V1 planned 26 implementation artifacts,
   including four adapter test suites, a new EventType, contract-checker counts,
   two ADR amendments, and observability tests before the blocking request could
   be retried.

### Suspicions, not promoted to defects

- **SP1:** Gemini/Aigate may reject the current dynamic map
  `fs_spawn_subagent.env` after the nullable unions are fixed. No live evidence
  yet; CONF-8 is the oracle. Do not redesign `env` preemptively.
- **SP2:** a provider may reject empty-object parameters such as
  `fs_list_tasks`. No live evidence yet; CONF-8 is the oracle. Do not add dummy
  arguments.
- **SP3:** other registered providers may have narrower schema subsets. They
  remain `UNVERIFIED` until their tool-aware live case passes.

### Sound decisions retained

- One provider-neutral tool-schema profile, no provider-name branch.
- `fa probe` remains tool-free connectivity/auth liveness.
- HTTP 400/422 remains fail-fast.
- Proxy remains byte-transparent.
- Tool-aware provider acceptance belongs in conformance.
- A natural default-coder run is the final product smoke.

### Primary references

- OpenAI function calling:
  <https://platform.openai.com/docs/guides/function-calling>.
- Anthropic client tools:
  <https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/implement-tool-use>.
- Mistral function calling:
  <https://docs.mistral.ai/capabilities/function_calling>.
- Gemini function declarations:
  <https://ai.google.dev/gemini-api/docs/function-calling>.
- Matching Gemini union failure:
  <https://github.com/langchain-ai/langchain-google/issues/1216>.

### Current liveness

| Capability | Liveness | Evidence |
|---|---:|---|
| Local input validation | L3 | registry/dispatch tests |
| Byte-stable tool rendering | L3 | `tests/test_prompt.py` |
| Provider-portable authoring profile | L0 | absent |
| `fs_search` provider acceptance | L2→FAIL | three live 400s |
| Exact tool-aware conformance | L0 | tool-free CONF-1..7 |
| Provider-specific conformance selection | L1 | label only, no filter |
| Tool-definition cache identity | L1→wrong | controlled equal-hash probe |
| Natural default coder | L2→FAIL | first provider request rejected |

No blocking policy question remains. Exact provider behavior beyond the observed
keywords is empirical and owned by CONF-8 stop conditions.

---

## 0. Executive intent

**IDEA:** Make every provider-visible FA tool use one small, explicit, portable
source-schema profile; fix the three incompatible `fs_search` fields at their
source; and make the live conformance command send the exact production coder
tools to the provider selected by the operator.

**PROJECT MEANING:** `ToolSpec.input_schema` remains the single local and wire
authority. Tool authors receive a deterministic portability gate rather than a
second derived schema they must reason about.

### Goals

- **G1:** The default Aigate/Gemini coder’s first request is accepted; no
  `fs_search` nullable union reaches the wire.
- **G2:** Every provider-visible ToolSpec satisfies Portable Tool Schema v1
  (`PTS-v1`) at registration; a source contract error cannot be logged and
  silently omitted.
- **G3:** `fs_search.types` is deleted because it has no behavior; optional
  `glob` and `exclude_dirs` use omission, not explicit nullability.
- **G4:** CONF-8 sends the exact tool set assembled by `_cmd_run`, including
  `pr_prepare`, through the exact provider requested by `--provider`.
- **G5:** Tool name/schema changes affect `prompt_cache_key`; stable identical
  tool sets retain stable keys.
- **G6:** One post-deployment tool-aware conformance row and one natural fresh
  default-coder run prove the repaired path, then work returns to main-plan
  closure.

**NON-GOALS:** no full→wire schema projector; no provider-specific schema fork;
no native Gemini adapter; no `strict: true`; no dynamic-map or empty-object
redesign without a live failure; no change to HTTP 400/422 policy; no EventType
migration; no shell-quoting, `gh`, PR-creation, workspace-readiness, or
provider-cost work; no guarantee for an untested vendor.

**INTENT:** A tool schema accepted into a role registry must be simple enough to
advertise unchanged to every generic adapter, and provider qualification must
exercise the actual tools rather than a tool-free approximation.

**MECHANISM:** simplify `fs_search._INPUT_SCHEMA` → validate every registered
schema against PTS-v1 → render the same schema unchanged → share one
`_build_run_tool_registry` producer between `_cmd_run` and CONF-8 → filter the
live chain to the requested provider → send CONF-8 → natural `fa run` smoke.
The cache hash is corrected to read the rendered nested tool shape.

**PROOF:** tests first pin the exact source schema, registry error propagation,
production tool corpus, provider selection, and nested cache hash. A strict
injected transport rejects empty/raw-union CONF-8. Live Aigate CONF-8 and a
paired `fs_search` call/result close the product path.

**SIZE:** M, reduced from v1: seven source modules, focused tests, and contract
documentation; no new runtime component or dependency.

---

## 1. Non-goals and minimal-mechanism decision

### Why one source schema is sufficient now

- Explicit null is not required for an optional object property; omission means
  unset.
- No current caller/test sends `null` for `glob` or `exclude_dirs`.
- `types` is ignored and has no consumer.
- Current non-union schema keywords were accepted far enough for the upstream
  validator to name the nested union fields; no evidence justifies stripping
  them all.
- Local handlers already own defaults/clamping. Schema defaults are provider
  hints and validator-copy annotations, not handler state.

### Rejected mechanisms

| Mechanism | Verdict | Reason |
|---|---|---|
| Change only `types` | Reject | `exclude_dirs` was also rejected; `glob` has the same nullable pattern |
| Derived full→wire schema | Reject | Premature dual semantics; strips useful constraints without evidence |
| Hand-authored local and wire schemas | Reject | Two authorities drift |
| Provider-name branches | Reject | Mixed chains and S13 D2 require provider-neutral behavior |
| New schema dependency | Reject | PTS-v1 is a small recursive stdlib validation rule |
| Change `fa probe` | Reject | Preserve cheap connectivity contract |
| Rename only one `api_retry` producer | Reject | Leaves terminal chain-exhaustion lie; separate complete slice |
| Duplicate production tool assembly in conformance | Reject | Shared helper is smaller and drift-proof |
| Repeat schema fixture in every adapter suite | Reject | Two adapter envelope shapes plus exact C2 body are sufficient |

---

## 2. Current state → target state

### Target facts

1. `ToolSpec.input_schema` remains the exact object rendered to providers and
   compiled for local validation.
2. `fs_search` has no `types` property, no nullable type list, and no
   `default: None` on optional `glob`/`exclude_dirs`.
3. `ToolRegistry.register` rejects schemas outside PTS-v1 after normal JSON
   Schema compilation.
4. Profile/extra/fallback builders re-raise `ToolSchemaPortabilityError`; they
   retain existing warning/degradation behavior for non-contract runtime or
   import failures.
5. One `_build_run_tool_registry` function owns role registry plus `pr_prepare`.
6. `_cmd_run` and live CONF-8 call that same helper.
7. Live conformance loads structural config without global key enforcement,
   filters the coder chain to `entry.provider == args.provider`, validates only
   selected direct-mode keys, and exits 2 before network on selection/key error.
8. Offline CONF-1..7 remain unchanged. Live cases append CONF-8 with exact tools.
9. `_hash_tool_defs_stable` reads nested `function.name` and
   `function.parameters`; flat legacy test fixtures are either deliberately
   supported or migrated in the same step, never silently hashed as `None`.
10. A successful natural run returns provider usage and a paired
    `fs_search` tool call/result.

### GAP ledger

| GAP | Current→target gap | Owner | Verification |
|---|---|---|---|
| GAP1 | Three nullable type lists make `fs_search` provider-invalid | S0/S1 | T1/T2/T9 |
| GAP2 | Ignored `types` consumes schema budget and causes a live 400 | S1 | T1/T2 |
| GAP3 | Registry validates broad JSON Schema, not portable provider profile | S0/S2 | T3/T4 |
| GAP4 | Builder catches can silently omit schema-contract failures | S2 | T4 |
| GAP5 | Production role registry and `pr_prepare` have no shared assembler | S3 | T5/T6 |
| GAP6 | CONF-1..7 and `_case_to_request` send no tools | S4 | T6/T7 |
| GAP7 | `--provider` labels but does not select the chain entry | S4 | T8 |
| GAP8 | Cache hash reads the wrong rendered-tool shape | S3 | T9/T10 |
| GAP9 | No live tool-aware/default-coder proof exists | S6 | T11/T12 |

### State transitions

```text
STATE tool_schema
BEFORE: broad local JSON Schema is copied to wire without portability policy
AFTER: one PTS-v1 source schema is compiled locally and rendered unchanged

STATE fs_search_schema
BEFORE: types ignored; glob/types/exclude_dirs nullable unions
AFTER: types absent; glob string optional; exclude_dirs array optional

STATE tool_corpus
BEFORE: _cmd_run builds role tools, then independently adds pr_prepare
AFTER: _build_run_tool_registry owns both for _cmd_run and conformance

STATE provider_conformance
BEFORE: --provider is a label; CONF-1..7 tools=()
AFTER: selected provider entries only; CONF-8 exact production tools

STATE cache_identity
BEFORE: nested tools hash as name=None/schema=None
AFTER: rendered function name/parameters are hash authority
```

---

## 3. Contracts

### CT1 — Portable Tool Schema v1 (PTS-v1)

**Authority:** `ToolSpec.input_schema`.

**Producer:** tool builders.

**Consumers:** `ToolRegistry.register/validate`, `render_tool_specs`, prompt
composer, and provider adapters.

**Root contract:**

- schema is a mapping with root `type: "object"`;
- root `properties` is absent or a mapping;
- `required`, when present, is a duplicate-free string list and every name
  exists in `properties`;
- all nested schemas satisfy the same closed rules.

**Allowed keywords:**

```text
type, properties, required, items, enum, description, default,
minLength, maxLength, minimum, maximum, additionalProperties
```

**Type contract:** `type` is one scalar member of:

```text
object, array, string, integer, number, boolean
```

**Nested contract:**

- `properties` values are schemas;
- array `items` is one schema;
- `additionalProperties` is a boolean or one PTS-v1 schema;
- `enum` is a non-empty homogeneous primitive list compatible with scalar type;
- descriptions are strings;
- numeric/string bounds have the expected primitive type.

**Forbidden:** type arrays, `null`, `anyOf`, `oneOf`, `allOf`, `not`,
conditionals, `$ref`, `$defs`, tuple/prefix items, and unknown keywords.

**Failure:** NEW `ToolSchemaPortabilityError` with
`tool=<name> path=<JSON pointer> reason=<closed reason>`.

Closed reasons:

```text
root_not_object, unsupported_keyword, unsupported_type,
invalid_properties, invalid_required, required_unknown_property,
invalid_items, invalid_enum, invalid_description, invalid_default,
invalid_bound, invalid_additional_properties
```

Bounds are non-negative integers for lengths and non-boolean int/float values
for numeric limits; `minimum <= maximum` when both exist. A default is absent or
a JSON value compatible with the declared scalar/array/object type. Boolean is
not accepted as integer/number. Enum values are JSON primitives compatible with
the declared scalar type.

**No projection:** provider bytes equal the source schema. Any future need for a
richer local-only construct is a new measured decision, not silent stripping.

**Kill-check:** reintroduce `type: ["array", "null"]` → T3/T4 fail before
provider I/O.

### CT2 — `fs_search` schema subtraction

**Site:** `src/fa/inner_loop/tools/fs_search.py:_TOOL_DESCRIPTION`,
`_INPUT_SCHEMA`, `_handle`.

**Required shape:**

```json
{
  "glob": {"type": "string"},
  "exclude_dirs": {
    "type": "array",
    "items": {"type": "string"}
  }
}
```

Both properties remain optional because neither is in root `required`.

**Delete completely:** `types` description, schema property, result note branch,
and any test/doc assertion that advertises it.

**Preserve:** query requirement, filters, defaults/clamping in handlers,
`additionalProperties: false`, output modes, containment, and response cap.

**Compatibility:** explicit `null` becomes invalid at registry validation;
omission is the supported unset representation. No current caller/test depends
on explicit null.

**Kill-checks:** restore `types` or either type list → T1/T2/T3 fail.

### CT3 — fail-closed schema registration

**Producer:** `ToolRegistry.register` invokes PTS-v1 validation after normal
schema compilation and before storing the spec/validator.

**Consumers:** profile and top-level registry builders.

**Policy:**

- `ToolSchemaPortabilityError` is a source contract defect and must propagate;
- missing optional imports/backends and ordinary optional builder failures keep
  their current warning/degraded behavior;
- duplicate registration behavior remains unchanged.

**Implementation constraint:** centralize repeated extra-tool registration only
if doing so reduces the catch matrix without changing which tools are optional.
Do not turn all optional-tool failures into hard failures.

**Kill-check:** inject a nonportable schema through profile and extra-tool paths;
T4 must see the named exception, not a missing tool plus warning.

### CT4 — exact production run-tool registry

**NEW function:** `src/fa/cli.py:_build_run_tool_registry`.

**Inputs:**

```text
role: str
workspace: Path
bash_timeout_seconds: int
draft_store: PrDraftStore
```

**Output:** `ToolRegistry`.

**Mechanism:** call `_build_role_registry`, register exactly one
`build_prepare_pr_tool(draft_store)`, return registry.

**Consumers:** `_cmd_run` and `_run_live_conformance` only.

**Ordering:** `_cmd_run` creates `draft_path`/`PrDraftStore` before calling the
helper; resume-draft trust/reset behavior remains after store construction and
before hook execution.

**Invariant:** for the same role/workspace/limits, production and CONF-8 tool
names/schema bytes are identical. Handler-bound paths may differ only through
the supplied isolated draft store.

**Kill-check:** omit `pr_prepare` or independently rebuild conformance tools →
T5/T6 fail corpus equality.

### CT5 — CONF-8 exact tool-schema case

**Existing offline cases:** `default_cases()` remains exactly CONF-1..7.

**NEW constructor:** `production_tool_schema_case(tools)` returns case 8 with:

- `tools` stored as an immutable tuple on `ConfCase`;
- minimal user task requesting a short text response without a tool call;
- no observations;
- `record_sizes=False`.

**Composition:** `_compose` includes case tools in the cacheable tool-definition
block; `_case_to_request` sets `RequestInfo.tools=case.tools`.

**Live case list:**

```python
[*default_cases(), production_tool_schema_case(render_tool_specs(registry.specs()))]
```

**Positive controls:** CONF-8 tools are non-empty, contain `fs_search` and
`pr_prepare`, contain no type arrays/combinators, and equal CT4 production
corpus bytes.

**Offline command:** remains CONF-1..7 and tool-free; its current tests and
meaning remain stable.

**Kill-check:** set CONF-8 tools empty or omit `pr_prepare` → T6/T7 fail before a
canned transport 200 can count.

### CT6 — exact live provider selection

**Site:** `src/fa/cli.py:_run_live_conformance`.

Load the full config with `require_api_keys=False`, then before proxy
rewrite/provider-chain construction:

```text
selected = tuple(entry for entry in coder.chain if entry.provider == requested)
```

- zero matches → stderr names requested provider and configured provider names;
  exit 2; zero transport calls;
- one or more matches → replace chain with selected entries preserving order;
- every selected entry must have the requested provider;
- in direct/non-proxy mode, validate API-key presence only for selected entries;
  a missing unselected-provider key cannot block the requested run;
- selected-key absence → stderr names only the environment-variable name, never
  its value; exit 2; zero transport calls;
- proxy mode skips agent-side key presence exactly as today;
- proxy rewrite happens after selection and selected-key validation;
- runner label and actual chain provider therefore agree.

Multiple same-provider entries are allowed and retain chain fallback order.

**Kill-check:** config contains OpenRouter then Aigate; request Aigate; any
OpenRouter URL/attempt makes T8 fail.

### CT7 — rendered tool cache identity

**Site:** `src/fa/inner_loop/prompt_composer.py:_hash_tool_defs_stable`.

For canonical nested tools, hash exactly:

```text
function.name
function.parameters
```

Descriptions remain excluded. Sort by normalized function name. A malformed
internal tool object raises a deterministic error or is rejected by a named
validation helper; it must not silently contribute `None`.

Flat internal fixtures remain supported deliberately: read `name` and
`input_schema`, normalize an absent flat schema to `{}`, and test that path.
Nested production tools remain the primary oracle. Any tool without a non-empty
string name raises `ValueError` instead of hashing `None`.

**Oracles:**

- different names → different hash;
- same name, different schema → different hash;
- description-only change → same hash;
- reversed tool/property insertion order → same hash;
- real `render_tool_specs` output is used in at least one test.

**Deployment:** expected one-time cache-key rollover; stable thereafter.

**Kill-check:** restore flat `.get("name")/.get("input_schema")` on nested tools
→ T9/T10 fail.

### CT8 — probe and production-acceptance boundary

- `fa probe` remains `tools=()` and proves only connectivity/auth/model
  availability.
- CONF-8 proves selected-provider acceptance of exact tool definitions.
- Fresh natural `fa run` proves default coder can receive a response and execute
  `fs_search`.
- Unknown/unexercised providers remain `UNVERIFIED`.
- Only after CONF-8 and natural run pass may the operator return to the main
  readiness-plan closure task.

---

## 4. Path and provider matrix

### Runtime paths

| Path | Trigger | Producer/consumer | Owner | Verification |
|---|---|---|---|---|
| P1 | default coder role | CT4 → `drive_session` | S3/S5 | T5/T10 |
| P2 | planner/researcher/code-reviewer with `fs_search` | profile registry | S2 | T3/T4 |
| P3 | eval/verifier without `fs_search` | eval registry | S2 | T3 |
| P4 | direct ToolRegistry registration | CT1/CT3 | S2 | T3/T4 |
| P5 | `fs_search` optional fields omitted | CT2 | S1 | T1/T2 |
| P6 | `fs_search` explicit null | local validation deny | S1/S2 | T2 |
| P7 | `_cmd_run` exact 15-tool corpus | CT4 | S3 | T5 |
| P8 | offline conformance | CONF-1..7 unchanged | S5 | T7 |
| P9 | live conformance requested provider absent | CT6 deny | S5 | T8 |
| P10 | live conformance selected provider | CT6 + CONF-8 | S5 | T8/T11 |
| P11 | OpenAI/Mistral passthrough | adapter consumes source schema | S5 | T6/T8 |
| P12 | Anthropic/Mistral Conversations envelope rename | adapter conversion | S5 | T6 |
| P13 | cache key after tool schema change | CT7 | S4 | T9/T10 |
| P14 | connectivity probe | tools empty by contract | S6 | T11 |
| P15 | natural fresh default run | managed run → provider → tool | S6 | T12 |

### Provider matrix

| Matrix | Provider/adapter | Required result |
|---|---|---|
| M1 | Aigate/Gemini default coder | CONF-8 200 + natural `fs_search` call/result |
| M2 | generic OpenAI-compatible | exact source schema in body; offline injected transport |
| M3 | Mistral chat | exact source schema passthrough |
| M4 | Anthropic | same schema under `input_schema` |
| M5 | Mistral Conversations | same schema under function parameters |
| M6 | future generic provider | PTS-v1 static pass + selected live CONF-8 before VERIFIED |
| M7 | unknown/unconfigured provider | explicit UNVERIFIED/selection error, never implied support |

Merge authority is deterministic/offline for M2–M5. M1 is the required
post-deployment proof for the reproduced production blocker.

---

## 5. Step-by-step implementation

### Step S0 — write failing regression tests first

**Traces-to:** G1–G5, GAP1–G8, CT1–CT7

**Depends-on:** none

**Edit:**

- NEW `tests/test_tool_schema_portability.py`.
- `tests/test_fs_search.py`.
- `tests/test_prompt_caching_per_role.py`.
- `tests/test_cli.py`.
- `tests/conformance/test_live_executor.py`.

**Do:**

1. Assert current `fs_search` provider schema has no `types`, no type arrays, and
   exact optional `glob`/`exclude_dirs` shapes. This test must fail on current
   source.
2. Add PTS-v1 positive/negative table tests using real `ToolSpec` and
   `ToolRegistry.register`.
3. Add a controlled nested rendered-tool cache test showing different schemas
   require different keys. It must fail with current equal hashes.
4. Add a two-provider conformance fixture showing `--provider aigate` must not
   call the earlier OpenRouter entry. It must fail on current source.
5. Add a CONF-8 positive-control test requiring exact production tools. It must
   fail because no such case exists.

**Do-not:** no source edits until each red test fails for its intended missing
producer, not fixture/import setup.

**Exit:** targeted red tests and reasons recorded.

### Step S1 — simplify `fs_search` at the source

**Traces-to:** G1/G3, GAP1/GAP2, CT2

**Depends-on:** S0

**Edit:**

- `src/fa/inner_loop/tools/fs_search.py`.
- `tests/test_fs_search.py`.

**Do:**

1. Delete `types` from `_TOOL_DESCRIPTION` and `_INPUT_SCHEMA`.
2. Delete the `_handle` note/result branch for `types`.
3. Set `glob` to optional scalar string with no `default: None`.
4. Set `exclude_dirs` to optional array-of-string with no `default: None`.
5. Preserve every functional search/filter/containment branch.
6. Add registry-level tests: omitted option accepted; explicit null rejected;
   valid string/list accepted.
7. Grep confirms zero provider-visible type arrays in `src/fa/inner_loop/tools`.

**Do-not:** do not redesign dynamic maps, empty tools, search behavior, or
handler clamping.

**Exit:** T1/T2 green; existing `fs_search` behavior suite unchanged.

**Kill-check:** restore any deleted union/`types` property → T1 fails.

### Step S2 — enforce PTS-v1 without breaking optional degradation

**Traces-to:** G2, GAP3/GAP4, CT1/CT3

**Depends-on:** S1

**Edit:**

- `src/fa/inner_loop/registry.py`.
- `src/fa/inner_loop/profiles.py`.
- `src/fa/inner_loop/tools/__init__.py`.
- NEW `tests/test_tool_schema_portability.py`.
- `tests/test_quality_slice_coverage.py`.

**Do:**

1. Add pure recursive `validate_tool_schema_portability(tool_name, schema)` and
   typed `ToolSchemaPortabilityError` to `registry.py`.
2. In `ToolRegistry.register`, compile normal JSON Schema first, validate PTS-v1
   second, then store. No partial `_tools`/`_validators` write on either failure.
3. In `profiles.build_registry_for_role`, re-raise the typed contract error;
   retain warning/skip for ordinary optional builder failures.
4. In `tools/__init__.py`, add one private zero-argument-builder helper that:
   skips an absent builder or already-registered name, registers the built spec,
   re-raises `ToolSchemaPortabilityError`, and logs/continues for every other
   ordinary builder exception using the existing tool name in the warning.
5. Route all nine `_register_extra_tools` branches through that helper. Do not
   change `include_pair`/`include_observability` membership conditions.
6. In `build_baseline_registry`, `build_planner_registry`, and
   `build_eval_registry`, explicitly re-raise `ToolSchemaPortabilityError`
   before their ordinary broad fallback branch.
7. Test profile-base, top-level fallback, and one extra-tool path with the typed
   error. Existing RuntimeError fallback/skip and duplicate-idempotency tests
   remain green.
8. Build every current role registry after S1 and assert all schemas pass.

**Do-not:** do not hard-fail missing optional imports/backends; do not alter role
membership; do not add provider names.

**Exit:** T3/T4 green and existing fallback tests green.

**Kill-check:** swallow typed error in profile or extra path → T4 fails.

### Step S3 — share exact run-tool assembly

**Traces-to:** G4, GAP5, CT4

**Depends-on:** S2

**Edit:**

- `src/fa/cli.py`.
- `tests/test_cli.py`.

**Do:**

1. Add `_build_run_tool_registry` with the CT4 signature and behavior.
2. Reorder `_cmd_run` locally so it creates `PrDraftStore` before the helper.
3. Replace separate `_build_role_registry` plus later `registry.register` with
   one helper call.
4. Preserve `_prepare_pr_draft` ordering, resume trust reset, hooks, and all
   run/session artifacts.
5. Add a C2 transport-body test asserting exact tool names include
   `fs_search` and `pr_prepare`, no duplicates, and all schemas pass PTS-v1.
6. Add one parametrized direct-helper test for `coder`, `planner`, and `eval`;
   each result contains the role’s existing tools plus exactly one `pr_prepare`.

**Do-not:** do not change unknown-role security behavior, role toolsets,
IntentGuard, draft path, or handler permissions.

**Exit:** T5 green; current `_cmd_run` tests unchanged.

**Kill-check:** omit `pr_prepare` in helper → exact C2 corpus test fails.

### Step S4 — repair tool-definition cache identity

**Traces-to:** G5, GAP8, CT7

**Depends-on:** S0; parallelizable with S1–S3

**Edit:**

- `src/fa/inner_loop/prompt_composer.py`.
- `tests/test_prompt_caching_per_role.py`.

**Do:**

1. Normalize each tool to name/schema from nested
   `function.name`/`function.parameters`.
2. Preserve the existing flat internal fixture shape explicitly: nested tools
   read `function.name`/`function.parameters`; flat tools read
   `name`/`input_schema`, with absent flat `input_schema` normalized to `{}`.
   Any shape without a non-empty string name raises `ValueError`.
3. Sort by normalized name and hash name+schema only.
4. In `tests/test_prompt_caching_per_role.py`, build a real baseline registry,
   call `render_tool_specs`, and run the CT7 matrix against those nested objects.
5. Keep one small synthetic nested pair to prove schema sensitivity directly.
6. Assert one intentional key change from old deployed behavior is documented;
   repeated current corpus is stable.

**Do-not:** do not hash descriptions, task text, provider, timestamp, or handler
state.

**Exit:** T9/T10 green.

**Kill-check:** restore flat-key reads → nested real-tool test yields equal hashes
and fails.

### Step S5 — add selected-provider CONF-8

**Traces-to:** G4, GAP6/GAP7, CT4/CT5/CT6

**Depends-on:** S3/S4

**Edit:**

- `src/fa/providers/conformance.py`.
- `src/fa/cli.py:_run_live_conformance` and CLI help text.
- `tests/conformance/test_live_executor.py`.
- `tests/conformance/test_offline_matrix.py` to pin unchanged CONF-1..7.
- `tests/test_providers_anthropic.py` — strengthen the existing tool conversion
  test to assert exact `input_schema` equality.
- `tests/test_mistral_conversations_provider.py` — strengthen the existing
  function-tool conversion test to assert exact `parameters` equality.

**Do in order:**

1. Load conformance config with `require_api_keys=False`, filter coder chain to
   the requested provider, and implement CT6 zero/multi-match behavior.
2. In direct mode validate only selected entries’ key names against
   `effective_secrets`; in proxy mode retain the current keyless agent contract.
3. Construct isolated conformance `PrDraftStore` under its run-log directory and
   call CT4 `_build_run_tool_registry` for role coder.
4. Render exact registry specs once.
5. Add immutable `tools` to `ConfCase` with default empty.
6. Pass case tools to `build_prompt_parts_v2` and `RequestInfo.tools`.
7. Keep `default_cases()` and offline matrix at CONF-1..7.
8. Add `production_tool_schema_case(tools)` as appended live case 8.
9. Strengthen injected transport: CONF-8 must be nonempty, contain exact corpus,
   and contain no PTS-v1 violation before canned 200.
10. Update live expected call count from seven to eight; preserve case IDs and
    runner resume semantics.
11. Assert selected-provider URLs/attempts and selected-key behavior only.

**Do-not:** do not force a model tool call in CONF-8; it proves request-schema
acceptance. Do not add provider-specific schema rewriting.

**Exit:** T6–T8 green; offline matrix remains seven cases.

**Kill-checks:** tools empty, `pr_prepare` omitted, or chain unfiltered → named
tests fail.

### Step S6 — documentation, gates, deployment, and natural smoke

**Traces-to:** G1–G6, GAP1–GAP9, CT1–CT8

**Depends-on:** S1–S5

**Edit:**

- `knowledge/adr/ADR-7-inner-loop-tool-registry.md` — short amendment naming
  PTS-v1 single-schema authority and fail-closed source-contract errors.
- `knowledge/adr/ADR-9-llm-provider-client.md` — generic-provider qualification
  requires selected-provider CONF-8.
- `knowledge/adr/DIGEST.md` — amendment summaries.
- `knowledge/instructions/02-operations.md` — probe versus CONF-8 versus natural
  run evidence.
- `worklogs/implementation-plans/PLAN-cli-trace-S13-multi-provider-conformance.md`
  — link S13.11 and correct “CONF exact production” scope.
- this plan — append execution evidence only after gates/live pass.

**Do:**

1. Run T1–T10 focused tests.
2. Run Ruff check/format, Mypy, Pyrefly, authoring/contract checks, then
   `just check`.
3. Execute mutations MU1–MU6 from §6; restore source after each.
4. Inspect exact diff and run `just check-deep` through normal pre-push.
5. Human review/merge/deploy.
6. Post-deploy `fa probe` as connectivity evidence only.
7. Run `fa conformance --provider aigate`; require selected provider and CONF-8
   OK.
8. Run a fresh natural default-coder task explicitly requiring `fs_search`;
   require first response 200, positive input usage, `fs_search` tool call, paired
   result, and no request-shape stop.
9. Then rerun the small plan-document closure task from the workspace-readiness
   main plan. PR creation remains host/human because `gh`/API authority is a
   separate boundary.

**Do-not:** no hook skip, direct-main push, provider key/body publication,
disposable PR ceremony, or readiness redesign.

**Exit:** T11/T12 and full DoD green.

---

## 6. Verification plan

### Verification items

| T | Class | Root/oracle | Covers | Kill target |
|---|---|---|---|---|
| T1 | C0 | exact `fs_search` ToolSpec schema | CT2 | deleted unions/`types` |
| T2 | C1 | registry dispatch optional/explicit-null matrix | CT2 | source schema type |
| T3 | C0p | PTS-v1 positive/negative recursive corpus | CT1 | portability validator branch |
| T4 | C1 | profile/fallback/extra typed-error propagation | CT3 | explicit re-raise |
| T5 | C2 | `_cmd_run` exact tool body and helper corpus | CT4 | shared helper/`pr_prepare` |
| T6 | C1 | CONF-8 corpus byte-equals CT4; envelope checks | CT4/CT5 | case tool assignment |
| T7 | C1 | offline remains 1..7; live appends case 8 | CT5 | live case append |
| T8 | C2 | requested provider only; absent provider zero calls | CT6 | chain filter |
| T9 | C0p | nested tool name/schema hash matrix | CT7 | nested extraction |
| T10 | C1 | real rendered corpus key stable/change-sensitive | CT7 | cache hash producer |
| T11 | live C2 | selected Aigate CONF-8 returns OK | CT5/CT6/CT8 | deployed schema producer |
| T12 | live product | fresh default coder paired `fs_search` trajectory | CT8 | complete run path |

### T1/T2 — source repair

- Build `fs_search` ToolSpec; inspect `input_schema` rather than private constant.
- Assert exact `glob` and `exclude_dirs` shapes.
- Assert `types` absent from description/schema/result behavior.
- Register tool and validate omitted, valid, and explicit-null inputs.
- Existing functional search tests remain unchanged.

### T3/T4 — authoring contract and propagation

PTS-v1 negative cases:

```text
type array, null type, anyOf/oneOf/allOf, ref/defs, unknown keyword,
required unknown property, malformed properties/items/additionalProperties,
heterogeneous enum, wrong bound primitive
```

Positive corpus includes every current role/tool schema, dynamic map, empty
object, enums, defaults, bounds, and nested arrays.

T4 distinguishes contract error from ordinary optional RuntimeError. Both sides
are required: contract re-raises; ordinary optional failure warns/skips/falls
back exactly as before.

### T5/T6 — exact production corpus

- C2 `_cmd_run` with injected transport captures actual body.
- Assert 15 distinct coder tool names after `pr_prepare` assembly.
- CONF-8 corpus equals captured names and parameter-schema bytes.
- OpenAI/Mistral passthrough needs no duplicate suite because C2 body equality
  already exercises the unchanged passthrough assignment.
- Anthropic and Mistral Conversations existing conversion tests assert exact
  schema equality after their distinct envelope renames.

### T7/T8 — conformance truth

- Offline `run_conformance_matrix` remains cases `[1..7]`.
- Live case list is `[1..8]`; eight transport calls on all-success fixture.
- Empty CONF-8 tools fail positive control.
- Two-provider config proves exact selection before proxy rewrite.
- Unknown/unconfigured provider exits 2 and makes zero transport calls.
- In direct mode, a missing key for an unselected provider does not block; a
  missing selected-provider key exits 2 with zero transport calls.
- Multiple entries for the requested provider retain order and never call another
  provider.

### T9/T10 — cache identity

Use actual nested `render_tool_specs` output. Assert name/schema sensitivity,
description insensitivity, order independence, and repeated-corpus stability.
The test must fail on deployed code’s equal hash, not merely inspect source.

### T11/T12 — live acceptance

Hard CONF-8 oracles:

```text
requested provider = aigate
CONF-8 status = OK
command exit = 0
request tools nonempty
fs_search + pr_prepare present
no request_shape
```

Hard natural-run oracles:

```text
fresh no-session-id managed run
first provider response accepted
input token usage > 0
fs_search tool_call exists
matching tool_result exists
session outcome is not request_shape
```

Free-text answer quality is secondary.

### Mutation handoff

| Mutation | Expected failure |
|---|---|
| MU1: restore nullable `exclude_dirs` | T1/T3 |
| MU2: restore ignored `types` | T1 |
| MU3: skip PTS-v1 validation | T3 |
| MU4: swallow typed contract error | T4 |
| MU5: CONF-8 tools empty or independently omit `pr_prepare` | T5/T6 |
| MU6: hash flat keys on nested rendered tools | T9/T10 |

Every mutation must be restored. A survivor blocks completion.

### LIVE-PATH PROOF LP1 — selected-provider exact tools

```text
root: fa conformance --provider aigate
producer: _build_run_tool_registry → render_tool_specs → CONF-8
consumer: filtered ProviderChain → OpenAICompatProvider → upstream
oracle: CONF-8 OK, exit 0, exact nonempty corpus
kill-check: tools=() or no provider filter fails T6/T8
paths: P7/P10/P11/P13
pyramid: A
```

### LIVE-PATH PROOF LP2 — natural default coder

```text
root: host fa run → managed _cmd_run → drive_session
producer: fs_search portable source ToolSpec
consumer: provider accepts tools → model calls fs_search → registry dispatch
oracle: provider response + paired tool_call/tool_result + non-request_shape end
kill-check: restore nullable union fails T1/T3 and live CONF-8
paths: P1/P5/P15
pyramid: A for wiring/request; model selection is final live product smoke
```

---

## 7. Risks, rollback, deferred confirmed defects, and questions

### Risks

| Risk | Impact | Mitigation |
|---|---|---|
| RK1: another current keyword is rejected after unions | second live 400 | CONF-8 stop; preserve evidence; revise PTS-v1 only from measured failure |
| RK2: PTS-v1 hard-fails an optional tool | run blocked | source-contract errors hard-fail; ordinary optional failures degrade |
| RK3: shared registry helper changes draft ordering | mutation denied/resume drift | CT4 ordering + existing `_cmd_run`/IntentGuard tests |
| RK4: provider label still differs from actual chain | false matrix | CT6 two-provider C2 test |
| RK5: cache-key fix causes cold request | one-time cost | expected rollover; T10 proves stable thereafter |
| RK6: old conformance resume has 1..7 rows | case 8 missing on reused run | CLI mints new run by default; never reuse old run for acceptance |
| RK7: dynamic map/empty object is next rejection | broader schema repair needed | SP1/SP2 stop condition, no speculative redesign |
| RK8: “all providers” overclaim | false support | M6/M7 VERIFIED vs UNVERIFIED distinction |
| RK9: unrelated dirty workspace masks edits | attribution error | exact path diff and clean implementation branch required |

### Rollback

- No migration or persistent schema change.
- Revert implementation PR and redeploy if a non-provider regression occurs.
- Revert restores the known default-coder blocker, so it is not an acceptable
  steady state; prefer forward correction for provider-only findings.
- No feature flag: two source-schema policies would undermine the standard.

### Deferred confirmed defects

- **DF1 — false retry output:** request-shape and final chain-exhaustion paths both
  emit `api_retry` without retrying. Fix both in one separate observability slice;
  do not rename only one producer here.
- **DF2 — shell task quoting UX:** docs favor double quotes for arbitrary task
  text; shell expansion happens before FA. Separate CLI/docs task-file/stdin
  slice.
- **DF3 — autonomous PR creation:** `gh` and GitHub API authority are absent;
  branch push remains the agent boundary. Separate security/policy decision.

None is required by the managed-workspace readiness contract or blocks the
schema repair; all are explicit rather than silently waived.

### Open questions

- **Q1 (NON-BLOCKING): Should PTS-v1 permit new keywords later?** Default: only
  through a measured provider case plus positive/negative tests; unknown keyword
  remains fail-closed.
- **Q2 (NON-BLOCKING): Should dynamic map `env` become key/value pairs?** Default:
  no unless CONF-8 proves current map rejected.
- **Q3 (NON-BLOCKING): Should empty-object tools receive dummy arguments?**
  Default: no; dummy parameters are forbidden unless a provider rejection and a
  separate contract justify them.
- **Q4 (NON-BLOCKING): Should `fa probe` gain tools?** Default: no; CONF-8 owns
  tool acceptance.
- **Q5 (NON-BLOCKING): Should DF1 join this patch?** Default: no; complete
  four-path event semantics need their own review and add no request acceptance.

Blocking question set: empty.

---

## 8. Evidence/research disposition

| RN | Item | Verdict | Reason |
|---|---|---|---|
| RN1 | Clean targeted `fs_search` run | Accept | Reproduces provider blocker without shell ambiguity |
| RN2 | Fix only `types` | Reject | `exclude_dirs` independently failed; `glob` shares pattern |
| RN3 | Delete ignored `types` | Accept | No consumer/behavior; best subtraction |
| RN4 | Derived full→wire projector | Reject | V1 premature abstraction; no measured need for dual schemas |
| RN5 | One PTS-v1 source schema | Accept | Smallest generic-provider authoring contract |
| RN6 | Strip defaults/bounds/additionalProperties | Reject | No live rejection; loses model guidance |
| RN7 | Tool-aware CONF-8 | Accept | Closes false-green conformance path |
| RN8 | Trust `--provider` label | Reject | CD6 proves no selection occurs |
| RN9 | Share production corpus helper | Accept | Removes `pr_prepare` drift freedom |
| RN10 | Cache identity already works | Reject | Controlled equal-hash probe proves CD8 |
| RN11 | Rename request-shape event only | Reject | Leaves terminal chain-exhaustion lie |
| RN12 | Tool-free probe proves readiness | Reject | Probe contract is connectivity only |
| RN13 | Guarantee unknown vendors | Reject | Unfalsifiable; M6/M7 qualify explicitly |
| RN14 | Native Gemini adapter now | Defer | OpenAI-compatible Aigate route only needs schema repair |

---

## 9. Definition of Done

### Binary state

```text
BEFORE
fs_search advertises 3 nullable type arrays and ignored types
registry accepts provider-nonportable broad schemas
production tool corpus assembly is split
conformance sends no tools and does not select requested provider
tool cache hash ignores nested name/schema
default coder first request = 400 request_shape

AFTER
fs_search advertises optional string/array only; types deleted
all registered tool schemas satisfy one PTS-v1 source contract
one helper assembles exact role tools + pr_prepare
CONF-8 sends exact corpus through selected provider only
cache hash changes with nested rendered name/schema
Aigate CONF-8 = OK and natural fs_search run has paired call/result
```

### Falsifiable checklist

- [ ] T1/T2: exact `fs_search` schema and input matrix pass; `types` absent.
- [ ] T3/T4: every current tool passes PTS-v1; every forbidden shape and every
  swallowed-contract mutation fails.
- [ ] T5/T6: `_cmd_run` and CONF-8 tool names/schema bytes are identical and
  include `pr_prepare` exactly once.
- [ ] T7: offline matrix remains 1..7; live matrix is 1..8 with nonempty CONF-8.
- [ ] T8: requested provider is the only provider attempted; absent provider
  exits 2 before network.
- [ ] T9/T10: nested tool cache hash is name/schema-sensitive,
  description-insensitive, and deterministic.
- [ ] Focused Ruff/Mypy/Pyrefly/pytest and contract checks pass.
- [ ] `just check` and normal pre-push `just check-deep` pass.
- [ ] MU1–MU6 are killed and source restored.
- [ ] Post-deploy image/source revision equals merged revision.
- [ ] T11 selected Aigate CONF-8 is OK with exit 0.
- [ ] T12 fresh default-coder run has positive provider usage and paired
  `fs_search` call/result, with no request-shape stop.
- [ ] Main workspace-readiness plan is then closed with `gh`/PR creation recorded
  as a separate boundary, not conflated with this repair.
- [ ] No key, task body, raw provider body, or secret-bearing environment is
  committed as evidence.
- [ ] No file outside the artifact inventory is edited without revising this
  plan before the edit.

### Contract completion

| Contract | Implementation | Required proof |
|---|---|---|
| CT1 | S2 | T3/T4 |
| CT2 | S1 | T1/T2 |
| CT3 | S2 | T4 |
| CT4 | S3 | T5/T6 |
| CT5 | S5 | T6/T7 |
| CT6 | S5 | T8/T11 |
| CT7 | S4 | T9/T10 |
| CT8 | S6 | T11/T12 |

Plan completion requires every contract VERIFIED, all mutations killed, and both
live proofs green.

---

## 10. Anti-theater and READY gate

### Anti-theater checklist

- [x] All current symbols/paths were read from exact deployed bytes.
- [x] Every G maps to GAP/CT/S/T and an artifact.
- [x] The blocking producer is fixed at source before general policy work.
- [x] CONF-8 has nonempty/exact-corpus positive controls.
- [x] Provider label and actual chain are tested separately.
- [x] Cache identity uses actual production nested tool objects.
- [x] Optional degradation and source-contract failure are distinct test paths.
- [x] No provider-name branch, schema dependency, feature flag, service, or
  derived schema is added.
- [x] Suspicions SP1–SP3 are not promoted to implementation work.
- [x] Deferred confirmed defects are explicit and non-blocking.
- [x] Kill-checks target source schema, registration gate, shared corpus,
  provider selection, case tools, and cache producer.
- [x] Unknown providers remain UNVERIFIED rather than rhetorically supported.
- [x] Every ID and artifact path resolves.

### READY gate

- [x] Preflight and adversarial review are non-trivial.
- [x] Depth P2 matches the reduced cross-module scope.
- [x] Current/target state and source data shapes are exact.
- [x] Function/data/provider/cache contracts are complete.
- [x] Path/provider matrices cover every edited root.
- [x] Steps are ordered tests-first and name exact symbols.
- [x] DoD is binary and includes producer mutations.
- [x] No blocking question remains.
- [x] Main-plan return path is explicit.

**READY verdict:** v2 is executable without selecting between architectures or
reconstructing the production tool corpus.

---

## 11. Artifacts inventory

| A | Path | Action | Owner |
|---|---|---|---|
| A1 | `worklogs/implementation-plans/PLAN-cli-trace-S13.11-portable-tool-schema-contract.md` | plan/evidence | planning/S6 |
| A2 | `src/fa/inner_loop/tools/fs_search.py` | simplify source schema/delete ignored parameter | S1 |
| A3 | `src/fa/inner_loop/registry.py` | add PTS-v1 validator/error/gate | S2 |
| A4 | `src/fa/inner_loop/profiles.py` | propagate contract error only | S2 |
| A5 | `src/fa/inner_loop/tools/__init__.py` | centralize optional registration and propagate contract error | S2 |
| A6 | `src/fa/cli.py` | shared run-tool registry + provider selection + CONF-8 wiring | S3/S5 |
| A7 | `src/fa/inner_loop/prompt_composer.py` | fix nested tool hash | S4 |
| A8 | `src/fa/providers/conformance.py` | case tools + live CONF-8 constructor | S5 |
| A9 | `tests/test_fs_search.py` | exact schema/input regression | S0/S1 |
| A10 | `tests/test_tool_schema_portability.py` | NEW PTS-v1 corpus/role tests | S0/S2 |
| A11 | `tests/test_quality_slice_coverage.py` | contract-error vs optional-failure paths | S2 |
| A12 | `tests/test_cli.py` | exact production corpus/provider-selection C2 | S0/S3/S5 |
| A13 | `tests/test_prompt_caching_per_role.py` | nested synthetic + real-corpus cache matrix | S0/S4 |
| A14 | `tests/conformance/test_live_executor.py` | provider selection + CONF-8 C1/C2 | S0/S5 |
| A15 | `tests/conformance/test_offline_matrix.py` | pin unchanged 1..7 | S5 |
| A16 | `tests/test_providers_anthropic.py` | exact schema equality after envelope rename | S5 |
| A17 | `tests/test_mistral_conversations_provider.py` | exact schema equality after envelope rename | S5 |
| A18 | `knowledge/adr/ADR-7-inner-loop-tool-registry.md` | PTS-v1 amendment | S6 |
| A19 | `knowledge/adr/ADR-9-llm-provider-client.md` | selected CONF-8 qualification amendment | S6 |
| A20 | `knowledge/adr/DIGEST.md` | amendment summaries | S6 |
| A21 | `knowledge/instructions/02-operations.md` | evidence boundary | S6 |
| A22 | `worklogs/implementation-plans/PLAN-cli-trace-S13-multi-provider-conformance.md` | S13.11 link/correction | S6 |
| A23 | `knowledge/llms.txt` | existing plan index row only | planning |

No implementation file outside A2–A22 may be touched without revising this
inventory and READY gate first.

---

## Executor handoff

1. Re-run source identity and preflight against current `main`.
2. Execute S0→S6 in order; S4 may run in parallel after S0.
3. Stop if SP1/SP2 becomes a live confirmed defect; preserve exact non-secret
   evidence and revise CT1 rather than inventing an argument shape.
4. Never use probe-only 200 as tool readiness.
5. Final report includes focused/full gate output, MU1–MU6 kills, selected
   provider evidence, CONF-8 row, natural tool trajectory, merge/deploy SHA
   parity, and the §9 checklist.
