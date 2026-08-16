# Agent Tooling Revamp — context for a future implementation plan

**Status:** backlog context; not an implementation plan

**Captured:** 2026-08-16

**Backlog:** [`I-57 — Agent tooling revamp`](../knowledge/BACKLOG.md#i-57--agent-tooling-revamp)

**Current in-flight boundary:** finish
[`S13.11 portable tool-schema contract`](./implementation-plans/PLAN-cli-trace-S13.11-portable-tool-schema-contract.md)
before combining any findings below with provider-schema work.

---

## 0. Purpose and use

This note preserves a source-grounded audit of the 15 tools currently exposed by
the default coder. It exists so a later `/plan-authoring` session can build one
or more bounded implementation plans without reconstructing the tool inventory,
mixing confirmed defects with suspicions, or treating cosmetic schema alignment
as more urgent than destructive execution boundaries.

This document does **not** authorize code edits. Finding IDs `ATR-F#` are audit
inputs, not plan GAP#/CT#/S#/T# contracts. A future plan must re-run source
preflight, disposition each finding, resolve `ATR-Q#`, and choose a small slice.

### Goal lens

Improve tool safety, provider portability, consistency, and model usability while
removing dead/no-op surfaces and preserving deterministic local validation.

### Non-goals for this note

- No immediate all-tools refactor.
- No source/test/config edits.
- No assertion that every uneven schema is defective.
- No redesign of provider adapters or S13.11.
- No promotion of unobserved risks into confirmed incidents.
- No new tool, dependency, service, or output channel.

---

## 1. Authority and evidence

### Code roots read

- `src/fa/inner_loop/registry.py` — `ToolSpec`, `ToolRegistry`.
- `src/fa/inner_loop/tools/{read_file,write_file,edit_file,run_bash,fs_search}.py`.
- `src/fa/inner_loop/tools/{blackboard_query,observability,pair_tools}.py`.
- `src/fa/inner_loop/tools/{spawn_subagent,prepare_pr}.py`.
- `src/fa/inner_loop/tools/__init__.py` and `profiles.py` — default role wiring.
- `src/fa/inner_loop/loop.py` — parallel-safety classifications.
- `src/fa/inner_loop/hooks/{builtin,intent_guard}.py` — sandbox, approval, and
  mutation authority.
- Existing tool tests and the S13.11 real-registry inventory probe.

### Backlog authority drift

`worklogs/BACKLOG.md` says it is canonical but currently stops at I-33.
`knowledge/BACKLOG.md` is the actively updated file and contains I-34 through
I-56; current HANDOFF and recent plans point there. I-57 is therefore appended
to `knowledge/BACKLOG.md`. A future documentation-maintenance pass should resolve
the dual-backlog authority; this note does not duplicate entries into both.

### Measured current inventory

```text
provider-visible tools in default coder corpus = 15
root schema type=object                       = 15/15
provider-visible type arrays after S13.11 S1 = 0
root additionalProperties:false              = 2/15
ToolSpec.output_schema populated             = 0/15
property-level descriptions                  ≈15/44
```

`additionalProperties: false` is currently set only by:

```text
fs_search
pr_prepare
```

The one dynamic-map schema is:

```text
fs_spawn_subagent.env: object with additionalProperties={type:string}
```

The one no-argument empty-object schema is:

```text
fs_list_tasks: {type:object, properties:{}}
```

---

## 2. Tool inventory and disposition baseline

| Tool | Permission | Current strength | Primary concern |
|---|---|---|---|
| `fs_read_file` | read | contained path, line windows, structured read failure | sparse schema guidance; PDF capability conditional |
| `fs_write_file` | workspace | conflict gate, path containment, write-set record | invalid params classified as `write_failed`; unknown args accepted |
| `fs_edit_file` | workspace | contained fuzzy edit, conflict gate, structured errors | transaction write recorded before filesystem success |
| `fs_run_bash` | workspace | sandbox/IntentGuard, PTY, timeout, output offload | stale nonexistent tool references; uncertain at-most-once fallback |
| `fs_search` | read | portable schema, containment, multiple backends, broad tests | PTS-v1 not enforced until S13.11 S2 |
| `fs_blackboard_query` | read | session authority, lazy index, compact bounded rows | some degraded failures only logged; unknown args accepted |
| `fs_chronicle_search` | read | session-aware bounded event search | broad catches; schema/handler validation style differs |
| `fs_usage` | read | authoritative usage rows and structured totals | loose schema; broad read-error boundary |
| `fs_list_tasks` | read | combines PTY/worktree/subagent views | empty schema; some failures silently suppressed |
| `fs_checkpoint` | workspace | serialized checkpoint attempts with fallbacks | stages/commits/stashes whole repo outside mutation/approval authority |
| `fs_undo` | workspace | can restore explicit branch/commit/stash | no-ID fallback performs destructive `reset --hard HEAD~1` outside guards |
| `fs_diff` | read | bounded read-only stat/diff, parallel-safe | sparse property descriptions; return schema unvalidated |
| `fs_send_ctrl_c` | workspace | structured API and bounded output | default registry supplies no PTY pool, so shipped tool is usually a no-op |
| `fs_spawn_subagent` | workspace | required args, enum, env secret checks | incomplete OS containment; dynamic-map compatibility unverified |
| `pr_prepare` | workspace | closed schema, downstream revalidation, fixed path | strong reference implementation; property descriptions could improve |

### Reference-quality tools

- `pr_prepare` is the strongest schema/handler/downstream-validation example.
- `fs_search` is now a strong provider-schema and search-contract example.
- `fs_read_file`/`fs_write_file`/`fs_edit_file` form a mostly coherent contained
  filesystem group, but error/bookkeeping details still drift.

### Weakest tool group

The pair-tool group is not one uniform quality tier:

- `fs_diff` is read-only and relatively safe.
- `fs_checkpoint` and `fs_undo` have direct destructive Git effects.
- `fs_send_ctrl_c` has a production wiring gap.

A future plan must not refactor these as one cosmetic “pair tools cleanup” batch.
Safety/authority comes before naming/schema polish.

---

## 3. Confirmed findings

### ATR-F1 — `fs_undo` has an unguarded destructive default path — P0

**Evidence:**

- `pair_tools.py:164-211`.
- With no usable `checkpoint_id`, handler executes
  `git reset --hard HEAD~1`, then may execute `git stash pop`.
- `intent_guard.py:_MUTATING_TOOL_NAMES` includes write/edit/apply-patch, not
  `fs_undo`.
- `SandboxHook` handles bash/spawn and path-scoped file tools, not `fs_undo`.
- `ApprovalHook` does not include `fs_undo`.
- `_NEVER_PARALLEL_TOOLS` serializes it but does not authorize or contain it.

**Impact:** a model-visible default tool can discard committed/uncommitted state
outside the normal draft/intent/approval boundary.

**Future-plan minimum:** decide whether to remove `fs_undo` from the baseline
immediately, require an explicit verified checkpoint ID, or route all Git
mutation through a dedicated authority. No silent `HEAD~1` fallback.

**Required negative proof:** without a trusted checkpoint/approval, provider
call trajectory reaches a structured deny and Git HEAD/index/worktree remain
byte-identical.

### ATR-F2 — `fs_checkpoint` mutates the whole Git index/history outside normal authority — P0

**Evidence:** `pair_tools.py:39-139`.

The handler runs:

```text
git add -A
git commit -m <generated checkpoint text>
git branch ...
git stash create/store
or git stash push
```

It is not in IntentGuard’s mutating set, SandboxHook’s mutation paths, or
ApprovalHook’s write set. A failed commit occurs after `git add -A`; index state
may remain changed before fallback logic.

**Impact:** unrelated files may be staged/committed, and hook/policy failure can
leave an index mutation even when the tool does not report a commit success.

**Future-plan minimum:** define checkpoint authority and atomicity before
changing implementation. Consider subtraction from the default registry until
safe behavior exists.

**Required negative proof:** induced commit/hook failure leaves HEAD, branch,
index, and worktree in the declared exact state.

### ATR-F3 — default `fs_send_ctrl_c` wiring is normally a no-op — P1

**Evidence:**

- `tools/__init__.py:_register_extra_tools` calls
  `build_send_ctrl_c_tool()` with no pool.
- `pair_tools.py:310-343` closes over that `None` and returns
  `status="no-pool"`.
- Unlike `fs_list_tasks`, it does not resolve `pty_pool` from current session.

**Impact:** model sees an interrupt tool that cannot interrupt the active PTY on
the normal baseline-registry path.

**Future-plan minimum:** inject the real pool from session composition or resolve
it via the same tested context authority as list-tasks. Remove the tool if no
live consumer can be wired.

### ATR-F4 — `fs_run_bash` description names unavailable tools — P1

**Evidence:** `run_bash.py:343-363` advertises:

```text
fs_run_bash_background
fs_read_terminal
fs_kill_task
```

These names are absent from the 15-tool registry and canonical `TOOL_NAMES`.

**Impact:** prompt/tool drift can cause the model to request nonexistent tools.

**Future-plan minimum:** subtract stale names or land real tools in a separately
justified slice; do not add tools merely to make prose true.

### ATR-F5 — `fs_edit_file` records transaction write before filesystem success — P1

**Evidence:**

- `edit_file.py:147-151` calls `transaction.add_write(rel_path)`.
- `edit_file.py:153-156` then calls `path.write_text`.
- `write_file.py:56-66` performs the write first and records transaction write
  afterward.

**Impact:** on write failure, transaction state can claim a write that did not
occur; sibling mutation tools disagree on ordering.

**Future-plan minimum:** filesystem mutation succeeds before transaction success
record, while conflict check remains before mutation. Add injected write-failure
proof.

### ATR-F6 — tool schemas are structurally common but semantically uneven — P2

**Evidence:** inventory metrics above.

- Only 2/15 reject unknown top-level arguments.
- Property-level descriptions are inconsistent.
- Defaults are inconsistently represented in schema vs handler.
- No output schema is populated.
- Error codes differ at sibling boundaries; e.g. malformed write-file input can
  become `write_failed`, while read/edit use `invalid_params`.

**Impact:** model guidance, hallucinated-argument handling, and downstream result
consumption vary by tool.

**Future-plan minimum:** after S13.11 PTS-v1 lands and CONF-8 is live, decide one
schema/error/output policy from measured provider behavior. Do not mass-add
`additionalProperties:false` before provider acceptance is proven.

### ATR-F7 — mutable schema can diverge from compiled validator — P2

**Evidence:**

- `ToolSpec` is frozen but `input_schema` is a mutable dict
  (`registry.py:75-85`).
- `ToolRegistry.register` compiles it once and stores the same ToolSpec
  (`registry.py:135-146`).
- Provider rendering later reads the mutable dict.

**Impact:** a post-registration mutation can change provider-visible schema while
local validation still uses the old compiled callable.

No current production mutator was found. This is a confirmed interface risk, not
a reproduced incident.

**Future-plan minimum:** decide deep-copy/freeze ownership at registration and
prove local validator/wire schema cannot diverge.

### ATR-F8 — `fs_run_bash` fallback lacks explicit at-most-once semantics — P1 risk

**Evidence:** `run_bash.py:331-339` catches any PTY executor exception and runs
the command through subprocess fallback.

**Impact:** if a mutating command executes and result collection then raises, the
fallback may execute it again.

The control-flow risk is confirmed; duplicate execution has not been reproduced.
A future plan must first build a fault-injection fixture that distinguishes
“not started” from “execution state unknown.”

### ATR-F9 — observability tools have uneven failure visibility — P2

**Evidence:**

- blackboard index failures are logged and query continues;
- list-tasks appends some subsystem errors but silently suppresses session and
  subagent discovery exceptions;
- broad catches use several unrelated error-code shapes.

**Impact:** partial results may appear complete unless the caller inspects Python
logs or embedded error rows.

**Future-plan minimum:** define partial-result metadata (`complete`, `warnings`,
or per-source status) before standardizing catches.

### ATR-F10 — subagent containment remains knowingly incomplete — existing P1/P2

**Evidence:** `SandboxHook` source comments explicitly state that cwd/path checks
do not provide an OS writable-mount boundary and general writes remain allowed
for realistic verifier commands. Existing backlog I-34 owns the OS-level
containment direction.

**Disposition:** cross-link, do not duplicate I-34. Tooling revamp should only
address schema/wiring surfaces not already owned there.

---

## 4. Suspicions and non-findings

### Suspicions requiring proof

- **ATR-S1:** A mutating PTY command can execute twice after transport/result
  failure. Needs fault injection before classification as a live defect.
- **ATR-S2:** generated checkpoint commit text may be rejected by current hygiene
  hooks. Needs an actual temporary Git commit through installed hooks.
- **ATR-S3:** dynamic map `fs_spawn_subagent.env` or empty-object
  `fs_list_tasks` may be rejected by a strict provider. CONF-8 owns this proof.
- **ATR-S4:** broad `additionalProperties` acceptance may materially increase
  hallucinated arguments. Needs trajectory evidence, not style preference.

### Things that are genuinely fine

- Different `max_context_bytes` values are intentional output-size policy, not
  inconsistency by themselves.
- Read-only vs workspace permissions broadly match tool effects, except that
  permission tier alone does not replace mutation authorization for pair tools.
- `fs_diff` being parallel-safe is consistent with its read-only Git commands.
- Handler-level validation duplicating registry validation is useful for direct
  calls and structured failure paths.
- `fa probe` being tool-free is correct; provider tool-schema acceptance belongs
  to CONF-8.

---

## 5. Recommended decomposition for future plans

Do not create one “revamp all tools” PR. Use ordered slices.

### Slice A — P0 Git mutation authority

Scope only:

```text
fs_checkpoint
fs_undo
IntentGuard/Sandbox/Approval/tool membership
temporary Git integration tests
```

Questions `ATR-Q1`–`ATR-Q3` must be answered first. Consider removing both tools
from default registry as the smallest safe interim state.

### Slice B — execution lifecycle and live wiring

Scope:

```text
fs_send_ctrl_c real PTY injection
fs_run_bash stale description
PTY fallback at-most-once contract
```

The fallback policy is a blocking design question; do not silently disable all
fallback or retry unknown-state commands.

### Slice C — mutation bookkeeping consistency

Scope:

```text
fs_edit_file transaction ordering
write/edit error taxonomy
injected filesystem failure tests
```

### Slice D — schema/result uniformity

Start only after S13.11 PTS-v1 and live CONF-8 pass.

Possible scope:

```text
unknown-argument policy
property descriptions/default guidance
output_schema decision
schema immutability
partial-result metadata/error taxonomy
```

Do not combine this cosmetic/contract work with P0 Git safety.

### Slice E — subagent boundary

Use existing I-34 and I-55 as authorities. Avoid a duplicate containment plan.

---

## 6. Future plan blocking questions

- **ATR-Q1:** Should `fs_checkpoint` and `fs_undo` be removed from the default
  registry until a guarded implementation exists?
- **ATR-Q2:** Must `fs_undo` require an explicit verified checkpoint ID, with all
  implicit `HEAD~1`/stash fallbacks deleted?
- **ATR-Q3:** Is checkpoint state a commit, a local ref, a stash object, or a
  harness-owned snapshot? One authority only.
- **ATR-Q4:** What exact PTY failure states permit subprocess fallback without
  violating at-most-once execution?
- **ATR-Q5:** Should every provider-visible object reject unknown properties, or
  remain non-strict for cross-provider compatibility?
- **ATR-Q6:** Are output schemas provider-facing, local-result validation only,
  or unnecessary overhead? Measure before adding 15 schemas.
- **ATR-Q7:** Which partial observability failures should fail the tool versus
  return `complete=false` with warnings?

A future plan must stop on unanswered Q1–Q4. Q5–Q7 may carry measured defaults
only after CONF-8/trajectory evidence.

---

## 7. Verification expectations for future plans

Every accepted finding must map to GAP#/CT#/S#/T# and include:

- C1/C2 composition-root proof with real ToolRegistry and HookRegistry;
- real temporary Git repository for checkpoint/undo;
- HEAD/index/worktree/branch/stash before/after oracle;
- guard deny and allow paths;
- zero side effect on denied/failed paths;
- structured ToolResult error code, not free-text-only assertion;
- provider-visible schema corpus test;
- producer kill-check;
- targeted mutation after C1/C2 green;
- normal `just check`/pre-push authority;
- one post-deployment natural task only when the slice changes live tool wiring.

### Minimum P0 negative proofs

```text
undo without explicit trusted checkpoint → denied; no Git state changes
checkpoint commit failure             → no index/HEAD/branch/stash drift
missing approval/draft                → denied before any Git process
concurrent invocation                 → serialized and state-exact
```

---

## 8. Relationship to current work

S13.11 remains narrowly responsible for:

```text
portable source schemas
PTS-v1 registration
exact provider selection
CONF-8 actual tool corpus
cache-key identity
natural fs_search smoke
```

Do not import ATR-F1–ATR-F10 into S13.11. After S13.11 is merged, deployed, and
live-verified, select Slice A first because destructive Git authority dominates
schema polish in value-to-risk ratio.

---

## 9. Handoff summary

```text
BACKLOG=I-57 Agent tooling revamp
FIRST_FUTURE_PLAN=Slice A — checkpoint/undo mutation authority
P0_FINDINGS=ATR-F1, ATR-F2
P1_FINDINGS=ATR-F3, ATR-F4, ATR-F5, ATR-F8
P2_FINDINGS=ATR-F6, ATR-F7, ATR-F9
EXISTING_AUTHORITY=ATR-F10 → I-34/I-55
DO_NOT_EXPAND_CURRENT_S13_11=yes
```
