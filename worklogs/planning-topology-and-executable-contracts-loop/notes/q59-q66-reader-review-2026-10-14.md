# Reader’s guide to Q59–Q66

**Purpose:** explain the still-open choices in ordinary language, show what the repository does today, and offer viable production designs. This is a review aid so the operator can give informed feedback. **Recommendations below are not decisions.** The existing question tracker and I02 increment remain authoritative for the full requirements.

**Source snapshot:** branch `arena/ca4c996c-first-agent-dev`, remote HEAD `941d03e`, reviewed 2026-10-14.

## The short version

| Question | Plain-language version | Status | My recommendation, not ratified |
|---|---|---|---|
| Q59 | Should chat only *suggest* the workflow, or must some requests be forced into it? | Open | Keep normal chat flexible; add an explicit “must use workflow” mode if a guarantee is wanted. |
| Q60 | How does the planner choose an existing plan or safely start a new project? | Open | Return stable project/increment IDs; controller builds paths; ask rather than guess when ambiguous. |
| Q61 | How do we stop coder tools or shell commands from changing the plan that the workflow is verifying? | Open | Use one isolated write-view for all coder write tools; preserve the dirty worktree and import changes conflict-safely. Until then, remove arbitrary shell or use a constrained runner. |
| Q62 | What short, fixed code should be recorded for each admission failure? | Open | Closed rule lists per validator; never save free-form model text as a rule. |
| Q63 | What does a live test result mean, and who may set it? | Open | Keep four states; require a reason code for `BLOCKED`; keep local tests separate from live results. |
| Q66 | Does the nested planner actually receive the current chat context? | API decision settled; runtime proof open | No new tool field. Pass a bounded, controller-captured context snapshot internally and prove it reaches the first planner request. |

### Terms in plain English

- **Tool/capability:** an action the model can ask the application to perform—read a file, edit a file, run shell, or start a workflow.
- **PlanRef:** the controller’s reference to the canonical plan file being checked. If that file changes unexpectedly, a result based on the old text is not trustworthy.
- **Copy-on-write (COW) view:** a temporary work area that starts with the current workspace. The agent’s edits go into the temporary layer first; the controller decides which edits, if any, to copy back.
- **Admission:** the checks that must pass before a coder is dispatched.
- **Live result:** what happened on the deployed host. A local test pass is not a live result.

## Q59 — Should chat recommend the workflow, or guarantee it?

### The choice

A simple typo fix should be answerable directly in chat. A multi-file product change may be better handled by the planner/coder/eval workflow. The question is whether chat’s complexity estimate is a **hint** or a **hard route**.

### What the code does today

- `estimate_scope()` is a deterministic keyword/file-reference classifier, not an LLM judgment (`src/fa/inner_loop/scope_estimator.py:12-23, 54-100, 151-226`). `fa run` computes it once from the initial `args.task` before building the tool registry (`src/fa/cli.py:2066-2088, 2293-2311`), then sends the estimate in non-cacheable `turn_context` (`src/fa/cli.py:2091-2142, 2400-2404`). The prompt tells chat to call `invoke_workflow` for a `workflow_linear` estimate (`src/fa/inner_loop/prompt.py:1004-1023`).
- The general chat profile has direct write, edit, shell, and subagent tool entries (`src/fa/inner_loop/profiles.py:147-171`). The escalation gate is **off by default** (`src/fa/inner_loop/runtime_limits.py:154-159`).
- Even when enabled, the current withheld-tool set removes `fs_write_file`, `fs_edit_file`, and `fs_spawn_subagent`, but not `fs_run_bash` (`src/fa/inner_loop/routing.py:72-78`). The registry also adds `pr_prepare` before it adds `invoke_workflow` (`src/fa/cli.py:1794-1803`). So a prompt asking the model to use the workflow is not, by itself, a guarantee that it cannot edit or run commands directly.
- The gate’s comment says the confidence threshold’s top bucket was measured `4/4` correct (`routing.py:64-67`). That is a small exploratory sample, not a production-grade estimate of error rates. Keep it advisory unless and until representative calibration supports stronger claims; Q64 places that calibration in I06.

One detail worth your feedback: the prompt says the harness classifies “each operator message,” while the CLI source computes one estimate from `args.task` per `fa run`. If the product has multiple operator messages inside one persistent run, confirm whether it should re-estimate on each message; do not assume the prompt wording proves that it does.

### Example

- “Fix the typo in `README.md`.” The classifier can recommend direct chat; the model edits the file and reports the change.
- “Change the public workflow API, update the CLI, and add tests.” The classifier can recommend workflow. With today’s default settings, that is still advice: the model may use `fs_run_bash` or another direct tool instead.
- “For this request, you must use the workflow.” If the product promises to honor that instruction, the controller—not the model’s willingness—must choose a restricted tool registry before the first provider call.

### Viable options

1. **Advisory default + manual invocation.** Keep ordinary chat flexible; the estimate suggests workflow, and the operator can ask for it. Lowest friction, but no guarantee.
2. **Automatic strict escalation.** A deterministic rule chooses workflow before the model sees tools. In that mode, remove every bypass path, including shell and other mutating tools. This can misclassify requests, so measure false positives and false negatives before making it the everyday default.
3. **Explicit guaranteed mode.** Keep option 1 as normal behavior, and add a user-selected “must use workflow” mode. In that mode, only the router/read tools and `invoke_workflow` are available. This is the clearest way to honor an explicit must-use instruction.

**Recommendation:** option 1 by default, with option 3 if you want a guarantee on request. Every route must preserve Q55/Q56: rejected pre-coder work does not run eval, and a successful coder still reaches eval. Do not call the estimator reliable merely because it is deterministic: determinism makes it repeatable, not necessarily accurate. The 20-slice/≥95% calibration criterion is deferred to I06, not an I02 gate.

**Production practice:** give an agent only the capabilities needed for the selected mode, and enforce the route in the controller rather than relying on prompt compliance. This matches OWASP’s Excessive Agency guidance to minimize tool functionality and permissions [OWASP LLM06:2025](https://owasp.org/www-project-top-10-for-large-language-model-applications/2_0_vulns/LLM06_ExcessiveAgency.html).

**Feedback needed:** Is manual “use workflow” enough, or should there be a deterministic mode that guarantees it?

## Q60 — How should the planner select an existing plan or start a project?

### The choice

When chat invokes the workflow, the planner needs to pick an existing project/increment plan—or propose starting a new project. Should it return a file path, or identify the project and increment while the controller constructs the path?

### What the code does today

`invoke_workflow` accepts `task`, `mode`, `roles`, and repair/replan budgets; its schema has no plan-selection or bootstrap fields (`src/fa/inner_loop/tools/workflow_tool.py:164-196`). The handler adds live read/write/search-path facts to the task and then calls `run_workflow` (`workflow_tool.py:331-375, 463-484`). The typed existing-plan selection and new-project bundle described in CT96 are **planned**, not implemented.

### Example

The operator asks: “Add OAuth callback support to the account portal.” There are two plausible account-portal increments. A safe response is not “pick the first matching filename” and not “make a new project just in case.” The planner should return a stable choice such as:

```text
kind: SELECT_EXISTING
project_slug: account-portal
increment_id: I03
```

The controller checks that this exact pair exists and constructs the canonical path. If two increments still fit, the planner returns `NEEDS_CLARIFICATION` and chat asks which one. For a genuinely new project, a separate typed bundle can carry the project slug and proposed roadmap/increment content; the controller validates and publishes it with no-clobber semantics.

### Viable options

1. **Planner returns a workspace-relative path.** Constrained paths are safer than arbitrary absolute paths, but the model still chooses a filesystem location. The controller must validate containment, existence, symlinks, and that the path is a canonical increment.
2. **Planner returns stable IDs; controller constructs the path.** The model chooses from known identifiers, not paths. This makes path traversal and accidental file selection harder. Add `NEEDS_CLARIFICATION` for ambiguous matches. **Recommended.**
3. **Support existing plans first; defer new-project bootstrap.** This reduces scope, but does not deliver the full requested behavior.
4. **Accept model-written files and validate them.** Possible, but requires a real content/schema validator—not merely path and byte-size limits. CT96 notes that full roadmap/ledger content validation is not currently implemented.

**Example of the safety boundary:** if `project_slug=account-portal` already exists and the planner proposes creating it again, the controller must not overwrite it. Stage the bundle privately, validate it, then publish only if the target is still absent. A collision should return a clear result to chat.

Whatever selection/bootstrap shape is chosen, the controller creates the PlanRef and runs the same admission checks before coder dispatch; a missing or malformed choice must not fall through to coder.

**Production practice:** treat model output as an untrusted request. The application owns path construction, authorization, validation, and atomic publication. Do not interpret “the model supplied a plausible path” as authorization.

**Feedback needed:** Are stable IDs plus clarification acceptable? Should new projects be supported immediately, or should the first version select existing plans only?

## Q61 — How do we protect the plan while the coder runs?

### The choice

The workflow verifies a plan. Can the coder’s tools change that same plan while the verification is in progress? Today, yes: the profile includes file write/edit and shell tools, and there is no active-PlanRef write rule at those tool handlers.

### What the code does today

- The `implementer` profile includes `fs_write_file`, `fs_edit_file`, and `fs_run_bash` (`src/fa/inner_loop/profiles.py:117-131`). It does not include `fs_spawn_subagent`; the subagent tool itself is disabled unless its feature flag is enabled (`tools/spawn_subagent.py:139-154`). I02 need not implement child isolation while the workflow coder does not expose children.
- The in-process `SandboxHook` defaults `allow_general_write=True`; its path-tool set covers read/write, not `fs_edit_file`. Its Bash hook uses a command classifier, and the source explicitly says a command such as `echo pwn > ../../../src/app.py` is not confined by the working directory (`src/fa/inner_loop/hooks/builtin.py:87-145`).
- `fs_write_file` and `fs_edit_file` resolve a workspace path and write with `Path.write_text`; neither has a rule protecting the active PlanRef (`src/fa/inner_loop/tools/write_file.py:15-60`; `tools/edit_file.py:100-155`). `fs_run_bash` can use a persistent PTY and fall back to subprocess execution (`tools/run_bash.py:90-155, 210-318`).
- The workflow captures plan identifiers before coder dispatch and checks against that snapshot afterward. That can detect some changes, but it does not stop writes or make a stale snapshot trustworthy (`src/fa/inner_loop/workflow_controller.py:1053-1104`).

### Example: a worktree that is already dirty

Before the workflow starts, suppose the operator has:

- one staged edit to `src/auth.py`;
- an unstaged edit to `README.md`;
- an untracked `notes/draft.md`.

A safe temporary view must begin with all three. The coder adds `src/oauth.py` and attempts to rewrite the active increment plan. The controller may import the new source file after validating it, but it must reject a change to the protected plan. If the operator also edits `README.md` in the real worktree while the coder is running, the controller must detect the conflict rather than overwrite that newer edit.

This does **not** mean “make a clean Git worktree at HEAD.” That would lose the operator’s staged, unstaged, and untracked state. It means snapshot the actual workspace used by the workflow, let provider writes land in one isolated layer, and copy back only reviewed/allowed changes. New imports should normally become unstaged changes; do not silently rewrite the operator’s Git index.

### Viable options

1. **Shared per-stage COW workspace for every write-capable tool.** `fs_write_file`, `fs_edit_file`, shell/PTY, and descendants all see the same view, so a file written through one tool is visible to the next. The host PlanRef, `.fa/admission/`, `.git`, credentials, and controller state are not writable there. At stage end, the controller validates a change manifest, rejects protected paths/symlink or hard-link tricks/special files/path escapes, checks that the real destination has not changed since the snapshot, and imports only allowed changes. This best preserves both plan integrity and normal source editing, but it is real implementation work.
2. **Separate trusted controller and isolated worker.** Move provider tool execution behind an IPC/process boundary and mediate writes through the controller. This can make the trust boundary clearer, but is a larger orchestration refactor.
3. **Safe first step: remove arbitrary shell from workflow coder until option 1 or 2 exists.** Keep only tools that can enforce exact path rules, or provide a narrowly scoped test runner. This delays convenience but avoids pretending a command classifier is a sandbox. **Recommended if the full boundary is not ready.**

**Recommendation:** choose option 1 as the target design; if it is not feasible for the first delivery, use option 3 rather than an incomplete mix where file tools write the host worktree but shell sees an old snapshot. Do not rely on `chmod`, a single read-only bind mount, a string blacklist, or post-run hashes as the security boundary. Preserve Q55: if coder actually dispatched successfully, a plan-integrity error must block terminal success but must not suppress the required eval stage.

**Production references:** Bubblewrap is a tool for constructing a sandbox, not a ready-made policy; its documentation says the caller’s mount choices define what the sandbox can see [Bubblewrap README](https://github.com/containers/bubblewrap/blob/main/README.md). For direct file operations on Linux, `openat2` has `RESOLVE_BENEATH` and `RESOLVE_NO_SYMLINKS` controls that help anchor path resolution under a directory handle [Linux `openat2` UAPI](https://github.com/torvalds/linux/blob/master/include/uapi/linux/openat2.h). Neither link implements the required snapshot/import logic for this repository.

**Feedback needed:** Do you want the full shared COW boundary before arbitrary shell is available to the workflow coder? If not, is temporarily removing shell acceptable?

## Q62 — What fixed rule codes should admission records contain?

### The choice

When a validator rejects a plan, what short machine-readable reason should be stored? The artifact should not depend on whatever wording the model happened to produce.

### What the code and plan say today

The existing `PlanDiagnostic` has string fields for `rule`, `severity`, and `message` (`src/fa/inner_loop/plan_ids.py:675-699`). The precheck and kill-directive validators already emit stable rule names such as `slice-without-tests` and `kill-directive-missing` (`plan_ids.py:1230-1248`; `src/fa/inner_loop/slice_verification.py:679-785`). CT92 plans a new admission artifact, but the writer and its closed rule table are not implemented (`increment-02-verify-gate-and-kill-checks.md:680-702`).

### Example

For “the requested plan path escaped the workspace,” a record can store:

```json
{"validator":"plan-ref","rule":"path-escape","severity":"ERROR","line":null}
```

That means the same thing every time, regardless of whether the model explains it as “bad path,” “outside the repo,” or something else. A human-readable message can be generated from the code by trusted application code. Do not store a model-authored explanation or source snippet as the rule.

### Viable options

1. **One large global enum.** Every possible rule name appears in one list. Easy to see in one place, but can become a duplicated list of unrelated validators.
2. **Small closed list per validator.** Keep the existing `validator` field and define the allowed `rule` values for each validator. Example: `plan-ref` allows `path-escape` and `source-changed`; `promotion` allows `candidate-invalid` and `target-changed`. Unknown pairs fail closed. **Recommended.**
3. **Free-form strings.** Easy to extend, but consumers cannot reliably distinguish a typo from a new rule; untrusted model text may become persisted control data. Not recommended.

Keep the schema versioned. Validate the `(validator, rule)` pair and the rest of every complete artifact when writing and when reading it back. A new code requires a deliberate schema/table change; an unknown code is not silently accepted. The existing plan also calls for no raw plan text, absolute paths, secrets, or `PlanDiagnostic.message` in the admission artifact.

**Feedback needed:** Is the per-validator closed table acceptable, or do you prefer one global enum? This is a schema-design choice before CT92 implementation, not a request to choose product behavior.

## Q63 — What counts as a live pass, failure, or block?

### The choice

A local test may pass while the deployed-host scenario has never been run. The record must not turn “not tested here” into “works in production.”

### Proposed four states

CT88 proposes this vocabulary, separate local-proof/live-result fields, and an evidence reviewer; it is a plan requirement, not an implemented live-status writer (`../increments/increment-02-verify-gate-and-kill-checks.md:934-944`).

- **NOT RUN:** no live attempt has been made.
- **PASS:** the deployed scenario ran and the required observable evidence satisfies its acceptance check.
- **FAIL:** the scenario ran, but the observable did not meet its acceptance check.
- **BLOCKED:** the live attempt could not be completed or judged—for example, the deployment was unavailable or the safety precondition was not met.

`BLOCKED` is neither a product failure nor a pass. It should carry a required, closed reason code, for example `DEPLOYMENT_UNAVAILABLE`, `SAFETY_STOP`, or `EVIDENCE_MISSING`. A skipped or unobservable scenario must never be counted as `PASS`.

### Example

A local unit test for CT97 passes. That sets **local proof** only; the live result stays `NOT RUN`. Later, the host is unavailable, so the live attempt is `BLOCKED` with `DEPLOYMENT_UNAVAILABLE`. After deployment, if the coder changes the active plan and the host hash changes, the case is `FAIL`. Only when the exact deployed SHA, run ID, command, exit result, expected observable, and artifact evidence are all present and satisfy the case oracle may a reviewer assign `PASS`.

Each retry should append a new attempt rather than overwrite the earlier one. The harness can collect evidence; the current ownership rule assigns the live result to the operator or an LLM evaluating collected run evidence. In particular, a coder, test harness, or eval stage must not certify its own live `PASS`.

### Viable options

1. **Four states plus required `block_reason`.** Clear distinction between “not attempted,” “ran and failed,” and “could not be judged.” **Recommended.**
2. **Four states without a reason code.** Simpler, but leaves `BLOCKED` vague and hard to audit.
3. **Add `SKIPPED`.** Usually unnecessary: “not started” is `NOT RUN`; “attempted but preconditions/evidence prevented a verdict” is `BLOCKED`. Add another state only if a real workflow needs that distinction.

**Feedback needed:** Do you approve the four states? Should every `BLOCKED` entry require a closed reason code? The specific reason-code list can be finalized during schema work.

## Q66 — How should the nested planner inherit chat context?

### What is already decided

The public tool schema decision is closed: **do not add a `context` field to `invoke_workflow`**. `task` remains the explicit goal; context is controller-managed state. The implementation is still unproven.

### What the code does today

The tool schema accepts `task`, `mode`, `roles`, and budgets, and rejects additional properties (`src/fa/inner_loop/tools/workflow_tool.py:164-196`). At invocation, `_resolve_handoff_task()` adds live read/write/search-path facts to the task (`workflow_tool.py:331-375`). The passed `SessionContext` is a namespace containing session/workspace/database/manifest paths, not the conversation (`src/fa/session/manager.py:51-58`). The nested `drive_session` rebuilds conversation history from its run log (`src/fa/inner_loop/coder_loop.py:600-649`). The current path therefore does **not** prove that the parent’s prior messages reach the nested planner.

### Example

Earlier in chat, the operator says: “Do not change the public API.” Later they say: “Add validation to the workflow.” Chat invokes the workflow. The first planner request must receive both the new task and the still-active constraint. Passing only “Add validation…” plus paths read during exploration is not enough.

### Recommended implementation

At the tool-call boundary, the controller should capture a bounded, immutable snapshot of the parent’s current context—its active compacted summary and relevant retained messages—then supply that snapshot internally as planner input alongside the planner’s own role prompt and skills. Do not put it in the public tool schema. Do not copy the outer system prompt, outer tool definitions, or unrelated tool catalog into the planner context.

Before crossing to a nested provider, apply the configured provider/data-egress policy and secret redaction. Label repository and tool output as untrusted data, so text read from a file is not treated as a new instruction. Budget and compact the snapshot explicitly; keep the operator’s current constraints and decisions. Record actual child token usage, but do not duplicate raw parent text into admission/control artifacts; ordinary child conversation logs remain subject to their existing retention policy. OWASP’s prompt-injection guidance specifically recommends separating untrusted external content and adversarially testing that boundary [OWASP LLM01:2025](https://owasp.org/www-project-top-10-for-large-language-model-applications/2_0_vulns/LLM01_PromptInjection.html).

### What a convincing test looks like

A real outer-chat → `invoke_workflow` → nested-planner C1 test should:

1. Put a unique constraint phrase in an earlier parent user message and a different marker in a relevant tool result.
2. Invoke the real workflow tool and capture the first planner provider request.
3. Assert that both markers arrive, the planner’s own prompt/skills are present, and there is still no public `context` field.
4. Include a synthetic credential sentinel and assert that the configured redaction/egress policy removes it.
5. Prove the context is bounded/compacted, token usage is accounted for, and raw parent text is not duplicated into admission/control artifacts; existing child-run conversation logging follows its normal retention policy.

**Feedback needed:** The API shape is settled. Is this bounded, redacted, controller-captured snapshot the intended meaning of “inherit the current chat context,” or should the planner receive a summary-only version?

## Already settled—do not spend decision time here

- **Q64:** the 20-slice/≥95% calibration criterion is deferred to I06 and is not an I02 gate.
- **Q65/Q45:** keep the ratified I01 source-position fields and the retired I02 duplicate locator.
- **Q66 public API:** no separate `context` tool field. Only the runtime propagation proof remains open.

## Suggested feedback order

1. Q59: Is ordinary chat advisory by default, with an optional guaranteed-workflow mode?
2. Q60: Stable identifiers plus clarification on ambiguity; should new-project bootstrap be in v1?
3. Q61: Require a shared COW boundary before shell, or remove shell until it exists?
4. Q62: Per-validator closed rule tables?
5. Q63: Four states plus a required `block_reason` for `BLOCKED`?
6. Q66: Bounded, redacted context snapshot or summary-only?

You can reply with short answers using this template:

```text
Q59: advisory default / require a guaranteed mode / other:
Q60: stable IDs + clarification / other; bootstrap now / defer:
Q61: shared COW before shell / defer shell first / IPC worker / other:
Q62: per-validator rule tables / global enum / other:
Q63: four states + required block reason / other:
Q66: bounded context snapshot / summary only / other:
```

## Source and practice references

- Repository source and plan locations are cited inline above. The full question record is [`open-questions-2026-10-07.md`](open-questions-2026-10-07.md); CT96/CT97 and the SLICE7 live-result contract are in [`increment-02-verify-gate-and-kill-checks.md`](../increments/increment-02-verify-gate-and-kill-checks.md).
- [OWASP LLM06:2025 — Excessive Agency](https://owasp.org/www-project-top-10-for-large-language-model-applications/2_0_vulns/LLM06_ExcessiveAgency.html): minimize tool functionality, permissions, and autonomy.
- [OWASP LLM01:2025 — Prompt Injection](https://owasp.org/www-project-top-10-for-large-language-model-applications/2_0_vulns/LLM01_PromptInjection.html): separate untrusted content and test the trust boundary.
- [Bubblewrap README](https://github.com/containers/bubblewrap/blob/main/README.md): a namespace/mount construction tool, not a complete security policy; the caller defines what is visible.
- [Linux `openat2` UAPI](https://github.com/torvalds/linux/blob/master/include/uapi/linux/openat2.h): includes path-resolution controls such as `RESOLVE_BENEATH` and `RESOLVE_NO_SYMLINKS`.
