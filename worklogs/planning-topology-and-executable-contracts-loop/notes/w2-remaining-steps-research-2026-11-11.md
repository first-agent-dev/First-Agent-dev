# W2 remaining steps: R24, R26, S5P1–S5P3 (2026-11-11)

Research note written after E513 (R25) and the E509 step-6 cross-cutting oracle.
Scope: understand each remaining step well enough to start it, and name the
decisions that must not be guessed. Source-grounded; nothing here changes code.

## 0. The invariant all three steps serve

First-Agent is an LLM coding harness: a trusted **controller** drives
planner → coder → eval against a workspace, and the model sees only tools. I03's
execution authority exists so that the *only* way agent work touches a real
workspace is a supervised, journaled, CAS-guarded view — never a model-chosen
host path. Every W2 step is the same invariant applied to a different caller:

> No agent-visible action may reach the host filesystem or a host process except
> through a bound managed view, and every such action must be replayable or
> refusable from evidence the authority holds.

R24 = the *verify* caller. R25 = the *publish* caller (done). R26 = the *nested
child* caller. S5 = the *discovery/bootstrap* caller that produces the first
PlanRef at all.

The dependency is real, not bookkeeping: R24's verify command needs a view that
can execute; R26's child needs a PlanRef before its coder; S5 is the only producer
of that PlanRef for a workspace with no plan yet.

## 1. R24 / S4P3 — managed verification

**Current behavior (source-verified).** `slice_verification._run_one`
(`:330–353`) shells out with `subprocess.run(shell=True, cwd=…)` against the host
workspace. `run_commands` (`:355–398`) fans out over commands with a monotonic
deadline. The caller is `workflow_controller._run_stage` → `verify_plan` at
`:1348`, i.e. **the controller**, after a coder stage. No model grant is involved
and none should be invented.

**The blocker is architectural, and it is not the profile.** An earlier pass of
this note claimed the problem was that VERIFICATION is read-only while `EXEC`
needs a session. That was wrong, and the correction matters because it changes the
answer. Three source facts, in the order they bind:

1. `ManagedBashExecutor.__init__` refuses any view whose `access is not
   Access.WRITE` (`client.py:1059`, probed: the VERIFICATION view raises
   `ExecutionContractError` in the constructor, before any RPC).
2. `ViewPurpose.VERIFICATION` is `(Access.READ, requires_plan=True, …)`
   (`workspace.py:217`; the second element is `requires_plan`, **not** a profile
   flag), so it can never satisfy (1).
3. `_purpose_write_policy` refuses `PATH_DENIED` for VERIFICATION/CANDIDATE
   (`workspace.py:2747`), so a verification run cannot write scratch there either.

So "run verify in the VERIFICATION view" is not merely awkward — it is refused
twice, by access and by write policy. Meanwhile `MUTATION` is
`(Access.WRITE, requires_plan=True, …)`, interactive-capable, write-bearing and
confined to `_MUTATION_ROOTS = {"src", "scripts"}`. Probed end to end: a MUTATION
view constructs a `ManagedBashExecutor` successfully and reaches command
dispatch, failing only on `BACKEND_UNAVAILABLE` because this sandbox has no
Docker. That is the whole path working except the container.

**Live options (for the operator, Q-class).**

- **A — give VERIFICATION its own write-bearing semantics.** Widen the purpose so
  it can host a scratch subtree. Cost: changes a matrix that purpose tests pin,
  and duplicates what MUTATION already does.
- **B — run verify on a MUTATION view.** Already admitted, already write-bearing,
  already interactive-capable, already proven to reach dispatch. The open question
  is only whether `src`/`scripts` can contain the scratch a verify command needs,
  or whether the scratch belongs outside the canonical tree (in which case the
  command runs `cwd=workspace` but writes to a temp dir the tree never sees).
- **C — decompose `run_commands` to accept an injected executor** and keep host
  `subprocess.run` as today's default. No semantics chosen, no behaviour changed,
  but the seam R24 needs exists and is testable.

**Recommendation (engineering).** C first, unconditionally — it is the injection
point every other choice needs, and it is a no-op for current behavior. Then B,
because it reuses an admitted purpose and the probe already shows dispatch works;
prefer it over A, which would widen a pinned matrix to duplicate MUTATION.

## 2. R26 — nested child with a real authority

**Current behavior (source-verified).** `workflow_tool._requires_acquisition`
returns `"coder" in roles` (`:400–402`), and the caller refuses every coder-containing
nested request with `acquisition_unavailable` (`:611–616`). So the entire
`handoff`/`return` composition is **dead in production**: only planner/eval-only
nested workflows can run. `ManagedExecution.handoff_to`/`reconcile_handoff`
(`composition.py:134–160`) are real and already exercised — but from the chat tool
(`workflow_tool.py:467, 498`), never from `ParentStageLease`.

**What is missing is not a second engine.** The handoff seam exists; what is
missing is (a) the gate removal that makes the coder path reachable, and (b) a
real-authority C1, because every HANDOFF assertion today runs against
`_RecordingHandoffClient`/`_RecordingParentLease`.

**The order matters and is easy to get wrong.** Removing the gate before S5 lands
means a nested coder workflow would admit a session and then have **no PlanRef**,
which is the exact state the gate exists to prevent. So R26 follows S5, or R26
must itself refuse pre-acquisition. The plan's order already says S5 last; this
note records *why*, so nobody "unblocks" R26 by deleting one predicate.

**No new policy needed** if the child's PlanRef comes from existing authority
(`handoff` already carries `expected_revision_id` and the target namespace). What
needs an operator decision is narrower: whether the child's **coder** may write
project files at all under Q61, or whether nested coder remains plan-staging only.
The DoD says "no child project write on denial", implying writes are allowed on
success — that should be confirmed once rather than inferred from a negative.

## 3. S5P1–S5P3 — acquisition, the largest and least defined

**What already exists (and it is more than the plan's wording suggests).**

| Piece | Where | State |
| --- | --- | --- |
| Strict choice parsing (3 kinds, dup/unknown-key rejection) | `managed_acquisition.parse_acquisition_choice:526` | complete |
| Inventory model | `managed_inventory` | complete |
| Existing-increment resolution, status rules | `resolve_existing_choice:442` | complete |
| Bundle **renderer** (controller owns all metadata) | `publication.render_bundle:534` | complete |
| Bundle store + wire op | `PREPARE_BUNDLE` → `publication.prepare_bundle:636` | complete |
| Install + receipt | `INSTALL_PROJECT` → `service._install_project:879` | complete |
| **Model-facing caller** | — | **absent** |

So S5 is not "build a bootstrap system". It is wiring four finished components
into a chat-only caller, in the order the spec fixes: inventory → strict choice →
clarification or select/bootstrap → exact read-back → `PlanSnapshot` **before**
coder → zero coder/provider effect on refusal.

**The v2 contract is decided, not open.** `i03-execution-workspace-spec:1260–1315`
fixes the three choices, the selectable-status rule (IN PROGRESS in both roadmap
and increment), the ACQUISITION cross-fields (EXISTING_SELECTION sets source/PlanRef
SHA and leaves candidate/promoted null; BOOTSTRAP sets those only after a
*committed verified install*), and the "blocked pre-selection has null PlanRef"
rule. Do not re-derive it; implement it.

**The one thing to watch.** `render_bundle` lives authority-side and the controller
sends prose only. That is the security property ("a model can never smuggle a
frontmatter field"), so the caller must pass raw prose through unchanged and must
not pre-validate in a way that lets it render locally. Any "convenience" copy of
the renderer in the controller would defeat the property.

## 4. What I would do next, and why

1. **R24 option C first** (inject the executor into `run_commands`, no behaviour
   change). It is small, it is needed by every remaining R24 choice, and it makes
   the managed cutover a one-line swap instead of a rewrite.
2. **S5 caller** next, because R26 depends on a PlanRef existing, and R24's real
   end-to-end needs an admitted managed plan.
3. **R26 last**, with the gate removed only once S5 can produce a PlanRef.

This inverts the plan's literal order (R24 → R26 → S5) on a dependency argument,
not a preference: R24's *oracle* can be built without S5 (a workspace with an
existing plan suffices), but R26's cannot.

## 5. Open decisions to raise, not guess

- **Q140 (R24 purpose):** verify runs on a MUTATION view (proven to reach
  dispatch), or does VERIFICATION gain write-bearing scratch semantics? The
  scratch-location half of this is the real question: inside `src`/`scripts`, or
  outside the canonical tree. Blocks R24's cutover, not R24's seam.
- **Q141 (R26 coder writes):** under Q61, may a nested child's coder write project
  files on success, or is nested coder plan-staging only? Blocks R26's gate removal.
