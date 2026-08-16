# PLAN: S13.11 — portable generic-provider tool-schema contract

Plan-ID: `PLAN-cli-trace-S13.11-portable-tool-schema-contract`

**Status:** READY

**Depth:** P2 — cross-module provider/tool contract repair; no service,
dependency, state migration, or deployment-topology change.

**Revision:** v4 (2026-08-16)

**Changed since v3:** adversarial review of every remaining slice resolved the
parent S13 CONF-8 naming collision by preserving sampling and extending it to an
exact production request profile; added an exact S5b ratchet regression; made
pre-push non-vacuous; completed ADR/doc-maintenance artifacts; defined
path/SHA-independent deployment parity; replaced console-only smoke claims with
stats/session-DB authority; and made parent readiness closure an explicit S6c
step rather than an unspecified follow-up.

**Retained from v3:** post-S4 S5 grounding, selected-before-secrets ordering,
selected-only redaction, exact schema-only registry bindings, tool-call response
success, both public-help owners, separate C901 synchronization, and explicit
deferral of the pre-existing live-conformance artifact concurrency defect.

**Retained from v2:** one portable `ToolSpec.input_schema` authority; deletion of
the ignored `fs_search.types`; optional omission instead of nullable unions; a
closed provider-schema authoring gate; selected-provider live conformance; one
production tool-registry assembler; and nested-tool cache identity.

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

V2's initial baseline was the deployed merge
`3c5145bde67fb80623a2bb9322202ec131eecba2`. That byte-equality statement is now
historical: the current worktree contains the reviewed S1–S4 implementations.
V3 re-read the current source and tests instead of reusing the baseline prose.
Current focused authority before S5 is:

```text
S1=PASS
S2=PASS
S3=PASS
S4=PASS
S5_BASELINE=2 failed, 48 passed
S5=PASS_LOCAL
S5_LIVE_EXECUTOR_TESTS=22 passed
S5_COMPATIBILITY_TESTS=217 passed
S1_S5_REGRESSION=312 passed
S5_MUTATIONS_KILLED=10/10
S5b=PASS_LOCAL
T13_COMPLEXITY_RATCHET=8 passed
MU7_KILLED=2/2
S6A_DOCS=PASS
S6A_FOCUSED=320 passed
S6A_REAL_READINESS_INTEGRATION=PASS
S6A_JUST_CHECK=PASS
S6A_FULL_SUITE=3052 passed, 14 skipped, 1 expected xfail
S6A_COVERAGE=84.87%
S6A_MUTATIONS=MU1-MU7_KILLED_AND_RESTORED
S6A_DOC_MUTATION_KILLED=1/1
S6A_Q6=RESOLVED_FORMATTER_FIX_NO_WAIVER
NEXT=S6B_FEATURE_BRANCH_PUBLICATION
C901_CENSUS=12
C901_BUDGET=14
C901_FLOOR=12
```

The S5 review read the current `conformance.py`, `_run_live_conformance`, config
and chain validation, secret store/redactor, runner, tool-registry builders,
`RequestInfo`/`ResponseInfo`, public CLI-help registry, OpenAI/Mistral pass-through
adapters, Anthropic/Mistral-Conversations envelope adapters, and all named S5
tests.

### Composition roots read

- Host delegation: `scripts/fa:_delegate_to_agent`.
- Natural run: `src/fa/cli.py:_cmd_run`.
- Role selection: `src/fa/cli.py:_build_role_registry`.
- Production tool assembly: `src/fa/cli.py:_build_run_tool_registry`
  (`cli.py:2214-2225`) calls `_build_role_registry`, appends exactly one
  `pr_prepare`, and is consumed by `_cmd_run` at `cli.py:2583-2590`.
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
- `SecretRedactor.from_models_config` scans every entry under every supplied
  role; selected-only key scope therefore requires a selected `ModelsConfig`
  projection, not only a filtered local `ChainConfig`.
- `ConfCase` has no tools; `build_prompt_parts_v2` accepts a list of dicts while
  `RequestInfo.tools` stores a tuple of mappings. S5 must name the conversion.
- `ResponseInfo` permits tool-call-only success, but `make_live_executor` checks
  only response text and currently marks such a 200 response false.
- Registry construction is schema-safe against an isolated state-root path:
  `fs_search` opens/indexes lazily and `PrDraftStore` does not write on
  construction. No deployment checkout is required.
- Public conformance help has two owners: parser description in `cli.py` and the
  bilingual `COMMANDS` record in `cli_help.py`.
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

### Confirmed v2 S5 plan defects

1. **PD8 — secret resolution ordering was underspecified.** Current code resolves
   `effective_secrets` before structural config load/selection
   (`cli.py:3029-3036`). Saying only “load with `require_api_keys=False`” permits
   the executor to retain that wrong precedence.
2. **PD9 — filtered chain was not a filtered redaction authority.** Current
   redaction receives the full `ModelsConfig` (`cli.py:3073-3079`), and
   `SecretRedactor.from_models_config` iterates all role entries
   (`redaction.py:147-162`). V2 did not require a selected-config projection.
3. **PD10 — CONF-8 data shapes were incomplete.** `ConfCase` had no named tools
   type/conversion even though the composer takes `list[dict]` and
   `RequestInfo.tools` takes `tuple[Mapping]`.
4. **PD11 — valid tool-call-only responses could fail conformance.** The live
   executor uses `bool(response.text)` only (`conformance.py:370-376`) even though
   `ResponseInfo.tool_calls` is canonical success data (`base.py:60-69`).
5. **PD12 — schema-registry bindings were left to guesswork.** V2 did not choose
   the workspace, runtime timeout, or draft-store path required by
   `_build_run_tool_registry`; an executor could bind handlers to the deployment
   checkout.
6. **PD13 — public help ownership was incomplete.** S5 said “CLI help text” but
   omitted `src/fa/cli_help.py`, the bilingual source used by parser summaries and
   `fa help`.
7. **PD14 — planned offline test editing was unnecessary.** The existing test
   already pins length seven and IDs `[1..7]`
   (`tests/conformance/test_offline_matrix.py:23-29`). It is a verification input,
   not an edit target.
8. **PD15 — exact-corpus proof was weaker than the contract.** The current RED
   test checks count/names only (`test_live_executor.py:305-310`), not equality of
   every rendered tool mapping and parameter-schema byte shape.
9. **PD16 — known full-gate failure had no owner.** S2 retired one C901 waiver;
   the real census is 12 while the ratchet floor remains 13
   (`test_s10b_complexity_ratchet.py:55-67,118-150`).
10. **PD17 — CONF-8 had two meanings.** The parent S13 plan already defines
    CONF-8 as the deployed sampling profile (`PLAN-cli-trace-S13-multi-provider-
    conformance.md:178-206`). Reusing the ID for a tool-only case would corrupt
    stable historical semantics. S13.11 must preserve sampling and extend the
    same case to the exact production request profile, including tools.
11. **PD18 — pre-push could pass vacuously.** The shipped pre-push exits 0 without
    running `check-deep` when readiness is unavailable (`pre-push:50-58`). A
    successful `git push` is not gate evidence unless output proves the deep gate
    actually ran.
12. **PD19 — S6 omitted mandatory documentation dependents.** ADR amendment
    maintenance requires `knowledge/trace/exploration_log.md`; PTS-v1 introduces
    a reference term; session closure requires `worklogs/HANDOFF.md`.
13. **PD20 — live proof lacked a deterministic reader.** Console text alone
    cannot prove fresh session identity or exact `tool_call_id` pairing. The
    authoritative `session.db` rows expose kind/tool/call-id and must be read
    after a unique explicit run ID with no session ID.
14. **PD21 — parent closure was ambiguous and currently corrupt.** The readiness
    parent has historical PASS tokens plus a later PENDING authority and malformed
    trailing text (`PLAN-session-workspace-readiness-bootstrap.md:5628-5640`).
    “Rerun a small closure task” is not executable.
15. **PD22 — T13 did not force exact ratchet updates.** The existing budget test
    accepts a range; S5b needs a named exact census/budget/floor regression so a
    future waiver retirement cannot leave constants stale again.

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
| Provider-portable authoring profile | L3 local | S2 registry gate + mutation kills |
| `fs_search` provider acceptance | L2→PENDING | source repaired; selected live CONF-8 not rerun |
| Exact tool-aware conformance | L0/RED | tool-free CONF-1..7; CONF-8 test fails |
| Provider-specific conformance selection | L1/RED | label only; two-provider C2 test fails |
| Tool-definition cache identity | L3 local | S4 T9/T10 + MU6 killed |
| Natural default coder | L2→PENDING | deployed first request failed; repaired local path not deployed |

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

**SIZE:** M, reduced from v1: eight source modules (the eighth is help metadata),
focused tests, one mechanical quality-ratchet edit, and contract documentation;
no new runtime component or dependency.

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
7. Live conformance selects the requested coder entries before secret resolution,
   validates direct keys through the selected `ChainConfig`, rewrites only the
   selected proxy chain, builds redaction from a selected-only `ModelsConfig`, and
   exits 2 before artifacts/network on selection/key error.
8. Offline CONF-1..7 remain unchanged. Live cases append CONF-8 with exact tools;
   text or tool calls are accepted as a successful canonical response.
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
| GAP6 | CONF-1..7 and `_case_to_request` send no tools | S5 | T6/T7 |
| GAP7 | `--provider` labels but does not select the chain entry | S5 | T8 |
| GAP8 | Cache hash reads the wrong rendered-tool shape | S4 | T9/T10 |
| GAP9 | No live tool-aware/default-coder proof exists | S6 | T11/T12 |
| GAP10 | C901 census fell to 12 but ratchet floor remains 13 | S5b | T13 |

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

**Conformance bindings:** `_run_live_conformance` uses its already-created
checkout-isolated preflight `run_log_dir` as the schema-only `workspace`,
`load_runtime_limits_from_path().limits.bash_timeout_seconds` as the timeout,
and `PrDraftStore(run_log_dir / "pr_draft.md")` as the draft store. Registry
construction does not dispatch a tool: `fs_search` opens its index lazily and
`PrDraftStore` does not write on construction. The deployment checkout is never
the conformance workspace.

**Invariant:** production and CONF-8 call the same helper and render the returned
`registry.specs()` exactly once. Handler-bound paths may differ; provider-visible
names/descriptions/parameter schemas may not. The C2 test compares the complete
rendered mappings, not only names/counts, and spies that the shared helper is
called exactly once.

**Kill-check:** omit `pr_prepare`, independently rebuild conformance tools, or
bypass `_build_run_tool_registry` → T5/T6 fail exact corpus/call-count proof.

### CT5 — CONF-8 exact production request profile

**Existing offline cases:** `default_cases()` remains exactly CONF-1..7.

**Data shape:** add this field to `ConfCase` without freezing the existing
mutable scenario object:

```python
tools: tuple[Mapping[str, Any], ...] = ()
```

The tuple is the immutable outer request corpus required by `RequestInfo`; the
nested mappings remain the canonical objects returned by `render_tool_specs`.
Do not add a second deep-freeze/projector.

**NEW constructor:**

```python
production_request_profile_case(
    tools: tuple[Mapping[str, Any], ...],
) -> ConfCase
```

It returns `case=8`, name `"CONF-8 exact production request profile"`, role
`"coder"`, task `"Reply with exactly OK. Do not call a tool."`, no observations,
`record_sizes=False`, and the exact tools tuple. The request retains the existing
production sampling contract: `max_tokens=64000`, `temperature=None`, and
`top_p=None`; S13.11 extends—not replaces—the parent S13 CONF-8 meaning. Before
returning, it raises
`ValueError` if tools are empty or if canonical nested names omit either
`fs_search` or `pr_prepare`; the message names CONF-8 and the missing names.
This is the runtime positive control—an empty/incomplete case must not produce a
false live PASS.

**Composition:** both composer call sites convert only the outer container:

```python
tool_defs = [dict(tool) for tool in case.tools]
```

`_case_to_request` additionally sets `RequestInfo.tools=case.tools`. No schema
copy, rewrite, or description stripping occurs.

**Live case list:** render once and append once:

```python
rendered_tools = render_tool_specs(registry.specs())
live_cases = [*default_cases(), production_request_profile_case(rendered_tools)]
```

**Response success:** `make_live_executor` treats a canonical response as
successful when `response.text` is non-empty **or** `response.tool_calls` is
non-empty. A 200 tool-call-only response proves the provider accepted the tool
schema and must not become a false CONF-8 failure. A 200 with neither remains
`ok=False`. Every live success/failure row carries both stable `case` and `name`
so JSON evidence can identify the exact profile rather than infer by position.

**Positive controls:** CONF-8 tools are non-empty, contain `fs_search` and
`pr_prepare`, contain no PTS-v1-forbidden type arrays/combinators, and equal CT4
production corpus mappings. Its request retains `max_tokens=64000` while omitting
`temperature` and `top_p`. The injected C2 transport asserts all of these before
returning its canned 200.

**Offline command:** remains CONF-1..7 and tool-free. The existing
`test_matrix_runs_all_7_cases_offline` already pins length and IDs and is run
unchanged.

**Kill-check:** set CONF-8 tools empty, omit `pr_prepare`, omit
`RequestInfo.tools`, or restore text-only success → named T6/T7 tests fail before
a canned transport 200 can create a false acceptance claim.

### CT6 — exact live provider selection

**Site:** `src/fa/cli.py:_run_live_conformance`.

**Required ordering:** the executor must implement these boundaries in order;
changing the order is a contract change:

1. Resolve `config_path`, `proxy_url`, and `proxy_mode`; do **not** load a secret
   store or create conformance artifact directories yet.
2. Load the complete structural config with
   `load_models_config_from_path(config_path, require_api_keys=False)`. Structural
   errors anywhere remain hard errors; only global key presence is deferred.
3. Resolve role `coder`; preserve its existing missing-role exit-2 message.
4. Compute
   `selected = tuple(entry for entry in coder.chain if entry.provider == provider)`.
5. Zero matches → print exactly one stderr diagnostic containing requested
   provider and `sorted({entry.provider for entry in coder.chain})`; return 2.
   No secret loading, proxy-token read, state directory creation, registry build,
   provider-chain construction, or transport call occurs.
6. Build `selected_chain = replace(coder, chain=selected)` and
   `selected_models = replace(models, roles={"coder": selected_chain})`.
   Preserve same-provider entry order.
7. Only now resolve `effective_secrets`: use the injected mapping when supplied;
   otherwise `SecretStore({})` in proxy mode or `_load_secret_store()` in direct
   mode.
8. Direct mode: call
   `selected_chain.validate(effective_secrets, require_api_keys=True)` and catch
   `ConfigurationError` into the existing `fa conformance: configuration error:`
   exit-2 path. This reuses the canonical non-empty/whitespace key check instead
   of inventing a second validator. Error text may name selected environment
   variable names; it must never contain values. Missing keys for unselected
   entries/roles cannot block.
9. Proxy mode: skip agent-side provider-key validation exactly as today. Rewrite
   **selected_chain only** with `_proxy_rewrite_chain` after selection. A missing
   proxy token remains exit 2 before network.
10. Build `SecretRedactor.from_models_config` with `selected_models`, not the
    full config; retain `allow_empty=proxy_mode` and proxy extras. Then wrap the
    transport and build `ProviderChain` from the selected/re-written chain.
11. Only after all preflight gates create the checkout-isolated conformance
    directory, build CT4 tools, append CT5, and invoke `run_matrix`.

**Postconditions:** every chain entry used by the run has
`entry.provider == provider`; runner/output provider label equals the requested
provider; request URLs and request-body model slugs come only from selected
entries. Multiple same-provider entries retain fallback order.

**C2 matrix:**

- OpenRouter first + Aigate second; request Aigate → only Aigate URL/model.
- Unknown provider → exit 2, requested/configured names on stderr, zero calls.
- Direct selected key present + unselected key absent → eight selected calls.
- Direct selected key absent → exit 2, selected key name but no value on stderr,
  zero calls.
- Two selected entries separated by another provider; first selected returns
  401 and second 200 → attempt order is selected-A then selected-B for every
  case, never the intervening provider.
- Spy on redactor construction → supplied config contains only role `coder` and
  only selected-provider entries.

**Kill-check:** retain whole-chain validation, filter after proxy rewrite, pass
full `models` to the redactor, or build the unfiltered chain → a named T8 matrix
cell fails.

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

### CT9 — C901 ratchet synchronization

**Site:** `tests/test_s10b_complexity_ratchet.py` only.

The S2 decomposition removed one real `# noqa: C901`; acceptance must lower both
ratchet constants by one in the same workstream. Target is budget `14`, floor
`12`, measured census `12`. Product source and complexity ceiling remain
unchanged. Restoring floor `13` must fail T13; lowering the floor below `12` or
leaving budget `15` fails exact-constant assertions/review.

---

## 4. Path and provider matrix

### Runtime paths

| Path | Trigger | Producer/consumer | Owner | Verification |
|---|---|---|---|---|
| P1 | default coder role | CT4 → `drive_session` | S3/S6 | T5/T12 |
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
| P16 | post-S2 quality gate | C901 census 12 within exact 12..14 ratchet | S5b | T13 |

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

### Step S5 — add selected-provider exact-tools CONF-8

**Traces-to:** G4, GAP6/GAP7, CT4/CT5/CT6

**Depends-on:** S3/S4

**Allowed implementation/test edits:**

- `src/fa/providers/conformance.py`.
- `src/fa/cli.py` — `_run_live_conformance`, conformance parser description,
  existing imports only.
- `src/fa/cli_help.py` — bilingual conformance summary/provider help only.
- `tests/conformance/test_live_executor.py`.
- `tests/test_providers_anthropic.py` — exact `input_schema` equality in the
  existing conversion test.
- `tests/test_mistral_conversations_provider.py` — exact `parameters` equality in
  the existing function-tool conversion test.
- `tests/test_cli_ergonomics.py` — public-help distinction only.

**Verification-only; do not edit:**

- `tests/conformance/test_offline_matrix.py` — already pins exactly `[1..7]`.
- `tests/test_cli.py` — existing `_cmd_run` corpus/helper producer proof.
- `tests/conformance/test_live_runner.py` — existing positional identity/resume
  contract; S5 does not change runner identity.

**Do in order:**

1. Load `/tests-writing`. Declare every existing test edit as strengthening or
   correcting stale setup; do not delete/skip/rename a protected test solely to
   obtain green.
2. Before product edits, expand `test_live_executor.py` with these named RED
   contracts:
   - `test_production_request_profile_case_rejects_empty_or_missing_required_tools`;
   - `test_case_to_request_carries_conf8_tools_into_composer_and_request`;
   - `test_live_executor_accepts_tool_call_only_response`;
   - strengthen
     `test_cmd_conformance_appends_exact_nonempty_production_tools_conf8` to
     compare every wire tool mapping with `render_tool_specs` from a real
     `_build_run_tool_registry` and spy that the helper is called once;
   - retain and strengthen
     `test_cmd_conformance_selects_requested_provider_before_proxy_rewrite`;
   - add `test_cmd_conformance_unknown_provider_exits_before_preflight`;
   - add `test_cmd_conformance_direct_mode_ignores_unselected_missing_key`;
   - add
     `test_cmd_conformance_direct_mode_rejects_missing_selected_key_without_leak`;
   - add `test_cmd_conformance_retains_selected_provider_fallback_order`;
   - add `test_cmd_conformance_redactor_receives_selected_models_only`.
3. Correct the stale direct-mode happy-path test: keep
   `test_cmd_conformance_live_provider_with_injected_secrets`, remove its proxy
   setup/proxy-aware subclass, keep proxy environment absent, inject one valid
   `TEST_KEY` value of at least eight characters, and require eight successful
   calls. The separate existing proxy-rewrite test remains the proxy happy path.
4. In `conformance.py`, implement CT5 exactly: import `Mapping`; add outer-tuple
   `ConfCase.tools`; add/export `production_request_profile_case`; pass outer-list
   copies to both composer calls; set `RequestInfo.tools`; and count either text
   or tool calls as canonical response success. Update module/docstrings from
   “offline half only” to offline 1..7 plus live-only case 8 without changing
   `default_cases()` or `run_conformance_matrix()`.
5. In `_run_live_conformance`, implement CT6 steps 1–10 in the stated order. Use
   `replace` already imported by `cli.py`; do not add a provider-selection helper
   unless line complexity forces it. Reuse `ChainConfig.validate` rather than
   hand-writing key validation. Pass `selected_models` to the redactor.
6. After selected-provider/key/proxy preflight succeeds, retain the existing
   checkout-isolated preflight `run_log_dir`; call
   `load_runtime_limits_from_path()`, create
   `PrDraftStore(run_log_dir / "pr_draft.md")`, call
   `_build_run_tool_registry("coder", run_log_dir, ...)`, render once, append the
   single CT5 case, and pass the resulting eight-case list to `run_matrix`.
   Registry construction must happen before provider execution and must not use
   `Path.cwd()` or the deployment checkout.
7. Update every live-test exact seven-call assertion/comment to eight. Do not
   change role-sequence heuristics such as `len(roles) >= 7`; that value describes
   message count, not case count.
8. Strengthen adapter envelope tests without changing adapter source:
   - Anthropic emitted `input_schema` equals the input nested `parameters` mapping;
   - Mistral Conversations emitted nested `parameters` equals the input mapping.
   OpenAI-compatible/Mistral-chat passthrough source remains unchanged.
9. Update both help authorities. Public wording must state: offline remains
   CONF-1..7; a selected live provider runs CONF-1..8 and case 8 carries exact
   production tools. `tests/test_cli_ergonomics.py` asserts both English help
   authorities contain that distinction; retain non-empty Russian text.
10. Run T6–T8 focused tests, unchanged offline and runner tests, existing
    `_cmd_run` producer tests, adapter tests, and changed-file Ruff/format/Mypy/
    Pyrefly. Inspect the exact diff.
11. Mutation/kill checks:
    - empty tools or omit `RequestInfo.tools`;
    - omit `pr_prepare`/bypass `_build_run_tool_registry`;
    - restore unfiltered chain or filter after proxy rewrite;
    - pass full `models` to redactor;
    - restore text-only response success;
    - remove selected `ChainConfig.validate`;
    - create artifacts before redactor success;
    - drop Anthropic or Mistral-Conversations schema assignment.
    Every named test must fail and source must be restored byte-for-byte.

**Do-not:** do not force a model tool call; CONF-8 proves request-schema
acceptance. Do not add provider-specific schema rewriting, a deep-freeze layer,
a new config/selection abstraction, or a live-runner identity change. Do not edit
the already-sufficient offline matrix test.

**Exit:** T6–T8 green; offline IDs remain `[1..7]`; live fake transport sees
exactly cases `[1..8]`; exact tools equal CT4; direct/proxy/zero/multi-match
matrix is green; help and adapter envelopes are exact; all S5 mutations are
killed.

### Step S5b — synchronize the retired C901 waiver ratchet

**Traces-to:** G6, GAP10

**Depends-on:** S2; run after S5 and before S6 full gates.

**Allowed edit:** `tests/test_s10b_complexity_ratchet.py` only.

**Do:**

1. Change `_C901_WAIVER_BUDGET` from `15` to `14` and
   `_C901_CENSUS_FLOOR` from `13` to `12`. This lowers both by exactly one for the
   one waiver retired by S2 and preserves the existing two-waiver budget/floor
   headroom.
2. Add
   `test_s13_11_c901_ratchet_tracks_retired_waiver` in the same file; assert
   `_waiver_census()` length is exactly `12`, budget is `14`, floor is `12`, and
   max-complexity ceiling remains `15`.
3. Rewrite the stale docstring references to historical `19/20`; describe the
   invariant symbolically (`census <= budget`, `census >= floor`) so the next
   retirement cannot leave false numbers.
4. Do not edit source, add a waiver, raise the complexity ceiling, or reduce the
   floor below the measured census.

**Exit / T13:** the named exact regression and the complete
`tests/test_s10b_complexity_ratchet.py` pass; restoring floor 13 makes
`test_s10b_c901_waiver_budget` fail with the measured 12-vs-13 diagnostic.

### Step S6 — documentation, gates, deployment, live proof, and parent closure

**Traces-to:** G1–G6, GAP1–GAP10, CT1–CT9

**Depends-on:** S1–S5b

#### S6a — policy/document synchronization and deterministic local gates

**Allowed documentation edits:**

- `knowledge/adr/ADR-7-inner-loop-tool-registry.md` — append an amendment before
  References: `ToolSpec.input_schema` is the single local/wire authority; PTS-v1
  is enforced after JSON-Schema compilation and before atomic registration;
  `ToolSchemaPortabilityError` is fail-closed while ordinary optional availability
  remains degraded.
- `knowledge/adr/ADR-9-llm-provider-client.md` — append an amendment before
  References: `fa probe` is connectivity only; generic-provider qualification
  requires selected-provider CONF-8 exact production request profile; untested
  providers remain UNVERIFIED.
- `knowledge/adr/DIGEST.md` — extend ADR-7 and ADR-9 amendment summaries, without
  creating replacement ADR sections.
- `knowledge/trace/exploration_log.md` — append Q-23 recording the one-source
  portable schema and selected exact-request conformance decision, rejected
  projector/provider-branch alternatives, and ADR-7/ADR-9 coupling.
- `knowledge/reference.md` — add one `Portable Tool Schema (PTS-v1)` term with the
  closed keyword/type profile and single-authority meaning.
- `knowledge/instructions/02-operations.md` — replace the diagnostic ladder with
  `selfcheck → probe → selected conformance → natural run`; document that offline
  conformance is 1..7, selected live conformance is 1..8, and CONF-8 preserves
  deployed sampling while adding exact production tools.
- `worklogs/implementation-plans/PLAN-cli-trace-S13-multi-provider-conformance.md`
  — link S13.11 and amend—not erase—the existing CONF-8 definition: deployed
  sampling profile becomes the exact production request profile
  (`max_tokens=64000`, temperature/top_p omitted, exact coder tools attached).
- this plan — execution evidence only after the corresponding command passes.

**Do in order:**

1. Load `/doc-maintenance`; make the ADR, digest, exploration-log, reference,
   operations, and parent-S13 edits as one documentation contract.
2. Run T1–T10 and T13 focused tests. T11/T12 remain post-deploy live proofs.
3. Run changed-file Ruff/format/Mypy/Pyrefly, authoring and contract scripts, then
   `uv run just check`. Success means exit 0 and the final summary says all
   blocking gates passed; a linter score or partial output is not evidence.
4. Execute MU1–MU7, including all MU5 subcases; record each required test failure,
   restore exact bytes/mode, and rerun its green control.
5. Inspect the complete diff, mode changes, untracked files, and
   `git diff --check`. Run `scripts/check_doc_links.py` after all doc edits.

**Exit:** T1–T10/T13 green, all mutations killed/restored, full local `just check`
PASS, docs linked, no file outside inventory, and no unresolved policy choice.

#### S6b — feature-branch publication, authoritative gates, and deployment

1. Load `/pr-creation` before commit/PR preparation. Preserve FIX/TEST-EDITS and
   AI-session trailer requirements.
2. Commit on a feature branch through normal hooks. No `--no-verify`, hook-skip
   variable, amend/rebase/reset/force, or direct-main push.
3. Push normally. Acceptance requires pre-push output containing
   `pre-push: running uv run --no-sync just check-deep` and successful
   `check-deep`/targeted-semgrep/targeted-mutmut completion. A hook exit 0 with
   `[WORKSPACE_BOOTSTRAP] ... continuing without local gate` is **not** deep-gate
   evidence; in that case run `uv run just check-deep` directly and require PASS
   before publication can count.
4. Human/host creates or reuses the normal PR. GitHub required CI is the final
   code authority. Agent may prepare/push the branch but does not use merge APIs.
5. Human merges. Operator runs the normal auto-discovered update path (`fa update`
   or the wrapper-resolved `scripts/fa-update.sh`), which fast-forwards main,
   rebuilds when image revision differs, and recreates the service. Do not edit
   the deployment checkout.
6. Independently derive—never manually supply—the canonical host repo from
   `readlink -f "$(command -v fa)"`. Require equality of:
   - canonical host `git rev-parse HEAD`;
   - running container image label `org.opencontainers.image.revision`;
   - read-only `/repo` `git rev-parse HEAD` inside the container.
   Also require clean host deployment status and healthy service. Any mismatch
   blocks live tests.

#### S6c — structured live acceptance and parent-plan closure

1. Run `fa probe --role coder`; require exit 0 and positive input/output usage.
   Record it only as connectivity/auth/model evidence.
2. Run `fa conformance --provider aigate --json`; require exit 0, top-level
   `provider == "aigate"`, rows exactly cases 1..8, row 8 `ok == true`, no
   `request_shape`, and case 8 named exact production request profile. Exact tools
   are proven by T5/T6; do not enable or publish raw debug bodies for live proof.
3. Generate a unique run ID from current UTC time, but pass **no `--session-id`**.
   Run one fresh managed task using single-quoted shell text, for example:

   ```bash
   fa run --role coder --run-id "$run_id" \
     'Use fs_search to find the definition of ToolRegistry in this repository, then report one matching path. Do not edit files.'
   ```

   Require exit 0; do not retry the same run ID or weaken the task if the model
   omits the required tool call.
4. Run `fa stats --run-id "$run_id" --output json`; require one session,
   `total_in > 0`, an `fs_search` tool-usage count ≥1, Aigate provider health with
   at least one success, and stop reason not `request_shape`.
5. Run one read-only Python verifier through the deployed FA environment. Use
   `_discover_stats_sources(... selected_run_id=run_id)` to auto-discover exactly
   one session authority, then `SessionDatabase.read_event_rows(run_id=run_id)`.
   Require:
   - non-empty auto-created `session_id` and exact requested `run_id` binding;
   - at least one `llm_call` row with `in_tokens > 0` and an Aigate attempt;
   - an `fs_search` `tool_call` row;
   - an `fs_search` `tool_result` row with the same non-empty `tool_call_id` and
     `content.ok == true`;
   - a `session_summary` row;
   - no `run_stopped` row whose reason is `request_shape`.
   Print only closed PASS/count/ID fields; never task text, provider bodies,
   secrets, or tool-result content.
6. Only after T11/T12 pass, update:
   - this plan with command/exit/hash/count evidence;
   - `PLAN-session-workspace-readiness-bootstrap.md` by removing its malformed
     trailing text and appending one authoritative closure block with
     `S9_STATUS=PASS` and `FEATURE_PRODUCTION_READINESS=VERIFIED` while preserving
     historical evidence blocks;
   - `PLAN-session-workspace-readiness-live-closure.md` from historical PENDING to
     closed-by-parent evidence without rewriting its chronology;
   - `worklogs/HANDOFF.md` current state/next action per session protocol.
7. Run `/doc-maintenance` closure checks, document links, authoring gate, and a
   final status-token grep proving the newest authoritative blocks agree. No new
   model/provider call is needed for documentation-only closure.

**Do-not:** no hook skip, direct-main push, provider key/body publication,
disposable PR ceremony, hardcoded host path, manually supplied expected SHA,
partial live-runner concurrency fix, or readiness redesign.

**Exit:** revision parity PASS; T11/T12 structured live proofs PASS; parent/live-
closure/HANDOFF authorities agree; full DoD green.

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
| T6 | C1/C2 | ConfCase→request→adapter exact tools; tool-call success | CT4/CT5 | tool assignment/helper/response oracle |
| T7 | C1/C2 | offline remains 1..7; selected live path appends case 8 | CT5 | live case append/default isolation |
| T8 | C2 | direct/proxy/zero/multi-match provider/key/redactor matrix | CT6 | selection/order/scope |
| T9 | C0p | nested tool name/schema hash matrix | CT7 | nested extraction |
| T10 | C1 | real rendered corpus key stable/change-sensitive | CT7 | cache hash producer |
| T11 | live C2 | selected Aigate CONF-8 returns OK | CT5/CT6/CT8 | deployed schema producer |
| T12 | live product | fresh default coder paired `fs_search` trajectory | CT8 | complete run path |
| T13 | C0 quality gate | exact C901 census/budget/floor | CT9 | stale floor/budget |

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

### T5/T6 — exact production corpus and response oracle

- Existing C2 `_cmd_run` transport proof remains the production root and asserts
  15 distinct tools including `fs_search` and exactly one `pr_prepare`.
- S5 C2 spies `_build_run_tool_registry` is called exactly once, renders a real
  registry, and asserts the complete CONF-8 wire `tools` list equals
  `list(render_tool_specs(expected_registry.specs()))`; names-only equality is
  insufficient.
- `_case_to_request` test asserts the same non-empty tuple reaches both the
  composer tool block and `RequestInfo.tools`, `max_tokens == 64000`, and
  `temperature is top_p is None` so the parent S13 sampling-profile contract is
  preserved.
- Constructor negative matrix: empty tuple, missing `fs_search`, missing
  `pr_prepare` → `ValueError` naming CONF-8/missing names before transport.
- C1 fake-chain response matrix: non-empty text/empty calls → OK; empty text/
  non-empty calls → OK; both empty → FAIL.
- OpenAI/Mistral chat passthrough assignments remain unchanged. Anthropic and
  Mistral Conversations existing conversion tests assert exact schema equality
  after their distinct envelope transforms.

### T7/T8 — conformance truth

- Unchanged offline `run_conformance_matrix` test remains cases `[1..7]` and all
  `ConfCase.tools == ()`; no S5 edit to that file.
- Live case list is `[1..8]`; eight transport calls on all-success fixtures; only
  request 8 has tools.
- Public English help in parser description and `COMMANDS` distinguishes offline
  1..7 from selected live 1..8; Russian entries remain non-empty.
- Two-provider proxy config proves exact selection before proxy rewrite by URL
  route and request-body model.
- Unknown provider exits 2 before secrets/proxy/artifacts and makes zero transport
  calls; stderr names requested and sorted configured providers.
- Direct missing-unselected-key succeeds; direct missing-selected-key exits 2,
  names only the selected key, never a sentinel secret value, and makes zero
  calls.
- Multiple same-provider entries retain order across a forced 401→200 fallback;
  intervening providers are never attempted.
- A redactor-construction spy sees `ModelsConfig.roles == {"coder"}` and only
  selected-provider entries.

### T9/T10 — cache identity

Use actual nested `render_tool_specs` output. Assert name/schema sensitivity,
description insensitivity, order independence, and repeated-corpus stability.
The test must fail on deployed code’s equal hash, not merely inspect source.

### T13 — quality-ratchet synchronization

- Assert `_waiver_census()` measures 12 on the S1–S5 source tree.
- Assert constants are exactly budget 14 and floor 12; max-complexity remains 15.
- Run the complete complexity-ratchet file.
- Manual mutation restores floor 13; the named waiver-budget test must fail with
  census 12 below floor 13; restore and rerun green.

### T11/T12 — live acceptance

Hard CONF-8 oracles:

```text
command = fa conformance --provider aigate --json
command exit = 0
top-level provider = aigate
row IDs = 1..8 exactly
CONF-8 name = exact production request profile
CONF-8 status = OK
request tools nonempty; fs_search + pr_prepare present (T5/T6 authority)
max_tokens=64000; temperature/top_p omitted (T6 authority)
no request_shape
```

Hard natural-run oracles:

```text
unique run_id; no --session-id; one auto-created session authority
run exit = 0
stats total_in > 0 and Aigate provider success > 0
fs_search tool_call exists
same non-empty tool_call_id has successful fs_search tool_result
session_summary exists
no run_stopped(reason=request_shape)
```

Console/free-text answer quality is secondary; stats and session DB are the
acceptance authorities.

### Mutation handoff

| Mutation | Expected failure |
|---|---|
| MU1: restore nullable `exclude_dirs` | T1/T3 |
| MU2: restore ignored `types` | T1 |
| MU3: skip PTS-v1 validation | T3 |
| MU4: swallow typed contract error | T4 |
| MU5a: CONF-8 tools empty / omit `pr_prepare` | T5/T6 |
| MU5b: bypass `_build_run_tool_registry` / omit `RequestInfo.tools` | T5/T6 |
| MU5c: restore unfiltered chain or filter after proxy rewrite | T8 |
| MU5d: pass full `models` to redactor | T8 |
| MU5e: restore text-only response success | T6 |
| MU5f: remove selected `ChainConfig.validate` | T8 |
| MU5g: create artifacts before redactor success | T8 |
| MU5h: drop Anthropic `input_schema` | T6 |
| MU5i: drop Mistral-Conversations `parameters` | T6 |
| MU6: hash flat keys on nested rendered tools | T9/T10 |
| MU7: restore C901 floor 13 | T13 |

Every mutation must be restored byte-for-byte. A survivor blocks completion.

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
| RK10: selected chain but full-config redactor | unselected secret scope/error names | selected `ModelsConfig` projection + T8 spy |
| RK11: provider returns tool-call-only 200 | false CONF-8 FAIL | canonical text-or-tool-call oracle + T6 matrix |
| RK12: conformance binds tools to checkout | accidental checkout state | preflight run-log workspace; no dispatch + T6 spy |

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
- **DF4 — live-conformance artifact identity concurrency:** `mint_run_id` uses
  second precision (`live_runner.py:75-82`) while `_run_live_conformance` uses a
  provider-constant preflight directory (`cli.py:3066-3068`). Concurrent or
  same-second runs can collide. S5 does not claim concurrent safety; fix runner
  identity and preflight relocation together in a separate slice rather than
  partially changing one path here.

DF1–DF4 are explicit and do not block the single selected-provider acceptance
run required by this repair. GAP10 is **not** deferred; S5b must clear it before
full gates.

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
- **Q6 (RESOLVED 2026-08-16): May S13.11 mechanically format the pre-existing
  readiness edit in `tests/test_deploy_scripts.py`?** Yes. The operator directed
  the simplest production response: fix the Ruff gate and proceed; do not add a
  waiver. A32 owns only the formatter-equivalent string-literal layout change.

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
- [ ] T8: direct/proxy/zero/multi-match matrix proves selected provider/key/
  redactor scope; absent provider/key exits 2 before artifacts/network and no
  secret value reaches stderr.
- [ ] T9/T10: nested tool cache hash is name/schema-sensitive,
  description-insensitive, and deterministic.
- [ ] T13: measured C901 census is 12, constants are exactly budget/floor 14/12,
  and the full complexity-ratchet file passes.
- [ ] Focused Ruff/Mypy/Pyrefly/pytest and contract checks pass.
- [ ] `just check` passes; pre-push proves it actually ran `check-deep` rather
  than taking readiness fail-open, or a direct `uv run just check-deep` passes.
- [ ] MU1–MU7 (including every MU5 subcase) are killed and source restored.
- [ ] Auto-discovered host HEAD, image revision label, and container `/repo` HEAD
  are equal after human merge/deploy; deployment checkout is clean and healthy.
- [ ] T11 `fa conformance --provider aigate --json` exits 0 with exact rows 1..8,
  selected provider, CONF-8 exact production request profile OK, and no
  request-shape result.
- [ ] T12 uses a unique run ID with no session ID; stats and authoritative DB
  read-back prove positive input usage and same-ID successful `fs_search`
  tool_call/tool_result pairing, with no request-shape stop.
- [ ] ADR-7/ADR-9, DIGEST, Q-23 exploration log, PTS-v1 reference term,
  operations, and parent S13 CONF-8 semantics agree.
- [ ] Parent readiness, child live-closure, and HANDOFF newest authority blocks
  close consistently only after T11/T12; historical evidence remains intact.
- [ ] `gh`/PR creation remains a separate host/human authority boundary.
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
| CT9 | S5b | T13 |

Plan completion requires every contract VERIFIED, all mutations killed, and both
live proofs green.

---

## 10. Anti-theater and READY gate

### Anti-theater checklist

- [x] V3 S5 symbols/paths were re-read from the current post-S4 worktree; merged-base evidence is labeled historical.
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
  provider/key/redactor selection, case tools, response oracle, cache producer,
  and quality-ratchet floor.
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

**READY verdict:** v4 is executable without selecting between architectures,
reconstructing the production tool corpus, guessing secret/registry bindings,
reusing CONF IDs inconsistently, or treating fail-open publication as a gate.

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
| A12 | `tests/test_cli.py` | exact production corpus/helper producer proof; verification-only in S5 | S0/S3 |
| A13 | `tests/test_prompt_caching_per_role.py` | nested synthetic + real-corpus cache matrix | S0/S4 |
| A14 | `tests/conformance/test_live_executor.py` | provider/key/redactor matrix + exact CONF-8 C1/C2 | S0/S5 |
| A15 | `tests/conformance/test_offline_matrix.py` | existing exact 1..7 proof; verification-only | S5 |
| A16 | `tests/test_providers_anthropic.py` | exact schema equality after envelope rename | S5 |
| A17 | `tests/test_mistral_conversations_provider.py` | exact schema equality after envelope rename | S5 |
| A18 | `knowledge/adr/ADR-7-inner-loop-tool-registry.md` | PTS-v1 amendment | S6 |
| A19 | `knowledge/adr/ADR-9-llm-provider-client.md` | selected CONF-8 qualification amendment | S6 |
| A20 | `knowledge/adr/DIGEST.md` | amendment summaries | S6 |
| A21 | `knowledge/instructions/02-operations.md` | evidence boundary | S6 |
| A22 | `worklogs/implementation-plans/PLAN-cli-trace-S13-multi-provider-conformance.md` | S13.11 link/correction | S6 |
| A23 | `knowledge/llms.txt` | existing plan index row only | planning |
| A24 | `src/fa/cli_help.py` | distinguish offline 1..7 from selected live 1..8 | S5 |
| A25 | `tests/test_cli_ergonomics.py` | pin both public conformance-help authorities | S5 |
| A26 | `tests/test_s10b_complexity_ratchet.py` | lower retired-waiver budget/floor and add exact retirement regression | S5b |
| A27 | `knowledge/trace/exploration_log.md` | Q-23 portable schema/qualification decision record | S6a |
| A28 | `knowledge/reference.md` | define PTS-v1 term and single-authority meaning | S6a |
| A29 | `worklogs/HANDOFF.md` | final current-state/next rewrite after live proof | S6c |
| A30 | `worklogs/implementation-plans/PLAN-session-workspace-readiness-bootstrap.md` | authoritative parent closure block + corrupt-tail repair | S6c |
| A31 | `worklogs/implementation-plans/PLAN-session-workspace-readiness-live-closure.md` | historical child closure reference | S6c |
| A32 | `tests/test_deploy_scripts.py` | Ruff-only formatting of pre-existing readiness producer assertion | S6a gate collateral |

No implementation/test/documentation file outside A2–A32 may be touched without
revising this inventory and READY gate first. A12, A15, and
`tests/conformance/test_live_runner.py` are explicitly verification-only for S5
and should not receive incidental edits.

---

## Executor handoff

1. Re-run source identity and S5 RED baseline against the current post-S4 tree.
2. Execute S5, then the separate mechanical S5b, then S6. S0–S4 are already
   locally implemented and must remain green.
3. Stop if SP1/SP2 becomes a live confirmed defect; preserve exact non-secret
   evidence and revise CT1 rather than inventing an argument shape.
4. Never use probe-only 200 as tool readiness.
5. Final report includes focused/full gate output, MU1–MU7 kills (all MU5
   subcases), selected provider/key/redactor evidence, CONF-8 row, natural tool
   trajectory, merge/deploy SHA parity, and the §9 checklist.
