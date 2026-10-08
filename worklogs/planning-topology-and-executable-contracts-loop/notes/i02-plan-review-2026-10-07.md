# Adversarial review — Increment 02, 2026-10-07

Reviewed at `158b610` against the code it touches. Every finding carries `file:line` evidence
and was executed, not reasoned about. **Seven confirmed defects, three of them severe enough
to have shipped an inverted gate.** All are now fixed in the plan.

---

## 0. Trajectory

**It advances the roadmap where it matters.** I02's reason to exist is register row **D1** —
`workflow_controller.py` read `.slices` for the whole life of I01 and silently no-opped
because real planner output carried none (E52). I02 creates the first production consumer of
`commands_for`, which also discharges D3, D4 and D5.

**One honest narrowing, now stated in the plan.** The roadmap's one-liner reads *"a **slice**
is gated by a planner-authored, non-vacuous test the harness runs"*. There is **no per-slice
dispatch in the controller** (§D2 below), so I02 delivers *plan-level gating with per-slice
attribution*: after the single coder stage, every declared slice is verified and results are
keyed by slice. True per-slice dispatch is I03's. The previous wording implied a loop that
does not exist.

**Scope creep: one real tension, reduced but not eliminated.** `SIMPLIFICATION-the-elegant-path.md`
§5 sized this work as *"one new function, one call site, plus tests"*. The kill-check adds an
AST layer and a sandbox, which is more. The operator chose that trade deliberately (E122), and
this review cut the sandbox from a git-worktree subsystem to a 10 ms directory copy (§I1), but
I02 is still the largest thing this roadmap has attempted. **Recommend shipping SLICE1–SLICE3
and SLICE6 first and treating SLICE4–SLICE5 as the second PR**, so the plain command gate — the
part that closes D1 — lands even if the kill-check needs another pass.

**Premature abstraction: one found and deleted.** See §I1.

---

## 1. Confirmed defects

### D1 — CRITICAL: the kill-check would have been invisible, inverting the gate

**Evidence (executed).** With a package installed so an absolute path is on `sys.path` — which
is how `fa` is installed; `pyproject.toml:100` packages `src/fa` and `pyproject.toml:218` puts
only the repo root on pytest's path — running a test with `cwd` set to a mutated copy still
imports the **original**:

```
A) cwd = copy, no PYTHONPATH   -> resolved /tmp/kc/orig/src/demo/__init__.py   producer() = "ORIGINAL"
B) cwd = copy, PYTHONPATH=copy -> resolved /tmp/kc/scratch/src/demo/__init__.py producer() = None
```

**Consequence.** The original plan's SLICE4 ran the contract's test with `cwd` in the worktree
and said nothing about `PYTHONPATH`. Every kill-check would have executed against unmutated
code, every test would have passed, and every contract would have been reported **`VACUOUS`**.
The gate would not have been broken — it would have been **inverted**: blocking every correct
slice while never once detecting a weak test.

**Fix.** `PYTHONPATH=<overlay>/src` (CT61) **plus a mandatory provenance probe** (CT62) that
asserts the target module resolves inside the overlay and returns `ERROR` if it does not.
Relying on `PYTHONPATH` silently is the same fragility that produced the bug; the probe is what
makes it safe.

### D2 — CRITICAL: `_run_stage` has no slice, so CT71/74/75 were unbuildable

**Evidence.** `workflow_controller.py:511` —
`_run_stage(ctx, role, *, fresh, progress, transition_reason, run_stage_fn) -> StageResult`.
No slice parameter. `grep` for a per-slice loop finds only `validate_slice_ids` (`:281`), which
is **post-hoc eval validation**, and the eval prompt at `:461`. One coder stage covers the whole
plan; the roadmap assigns the per-slice loop to I03.

**Consequence.** "after a coder stage returns, `_run_stage` calls `verify_slice` for **that
slice**" named a thing that does not exist. An agent would have had to invent a dispatch loop —
i.e. silently build I03.

**Fix.** CT71 rewritten: verify **every** declared slice after the coder stage, returning a
`PlanVerification`. CT76 replaces the meaningless "another slice's commands did not run" with
the assertion that actually has content: **commands are attributed to the slice that declares
them**, and `commands_for(None)` runs exactly once.

### D3 — CRITICAL: `drive_session` is the wrong harness and cannot prove the gate

**Evidence.** `cli.py:1460` passes `run_stage_fn=_cmd_run` into the controller; `_cmd_run` is
what calls `drive_session` (`cli.py:2408`). So `drive_session` sits **below** `_run_stage` and
can never exercise it. The only end-to-end precedent is
`tests/test_workflow_global_history.py:123-141`, which calls `run_workflow(…,
run_stage_fn=_cmd_run, transport=_StubTransport())`.

**Consequence.** CT74 as written would have produced a green test that proves nothing about
the gate — precisely the `VACUOUS` class the increment exists to detect, shipped inside the
increment that detects it. (I01 shipped the same shape once: a dead `_slice_sections` inside
the slice that orphaned it, E89.)

**Fix.** CT75 rewritten onto the `run_workflow` + `_cmd_run` + stub-transport template, with
the file and line of the precedent named.

### D4 — MAJOR: `remove-call` saw 1 call site in 4

**Evidence (executed).** On a function containing `a = emit(ctx)`, `emit(ctx)`, `if emit(ctx):`
and a comprehension: deleting only `ast.Expr` statements whose value is a `Call` finds
**1 of 4**.

**Consequence.** A producer invoked as an assignment yields `hits == 0` → a false
`PRODUCER_ABSENT`, i.e. the gate reports "the feature was never wired" about a wired feature.
Mixed forms yield partial removal, so the test may still pass → false `VACUOUS`.

**Fix.** CT56 now **replaces every `ast.Call` to the callee with `ast.Constant(None)`**.
Re-measured: `hits = 4`, absent target still `hits = 0`. Uniform across all call forms and a
truer simulation of "the producer never ran".

### D5 — MAJOR: the "byte-identical" invariant in CT55 is false

**Evidence (executed).** `ast.unparse(ast.parse(src)) == src` is `False`; comments and layout
are discarded.

**Fix.** CT55 now compares against `ast.unparse(ast.parse(source))`, the round-trip baseline.

### D6 — MAJOR: the synthetic report would have been silently discarded

**Evidence.** `_run_initial_roles:886` loops roles and does
`if result.eval_report is not None: eval_report = result.eval_report` (`:908-909`), returning
the **last** one. The repair branch at `:944` reads only that value.

**Consequence.** A verification failure attached to the coder stage is overwritten by the eval
stage's own report. The route is lost and the run finishes green with a failed verification —
the exact silent pass this project exists to remove. The wasted LLM call is the lesser harm.

**Fix.** New CT73: `_run_initial_roles` stops the role loop on a blocking coder report, with
the kill-check aimed at the `_is_blocking` call, and a DoD line requiring it be asserted on the
**stage count**, not a log line.

### D7 — MINOR: three stale references

| Plan said | Truth |
| --- | --- |
| `repair_round` at `workflow_artifacts.py:277` | that is `FlowState`'s **mirror**; the governing counter is `WorkflowProgress.repair_round`, `workflow_controller.py:188`, capped at `:944-957` |
| `_run_stage` at `:310` (inherited from S6) | `:511` |
| "mark the report harness-origin" | **no provenance field exists** on `EvalReport` (`workflow_artifacts.py:201`) — an agent would have had to invent one |

**Fix.** Ground-truth block rewritten; harness origin carried in `evaluation_id` prefixed
`harness-verify-` plus a finding, explicitly without widening `EvalReport`.

---

## 2. High-ROI improvement implemented

### I1 — deleted the git-worktree subsystem (a premature abstraction)

The original SLICE4 built a scratch **git worktree**: `git worktree add --detach`, pipe
`git diff HEAD` into `git apply`, then separately copy untracked files because the
planner-authored test is new, then `git worktree remove --force`, all exception-safe.

Replaced by `shutil.copytree(root/"src")`. **Measured: 2.4 MB, 162 files, ~7 ms.**

What this buys beyond simplicity:
- **Tests become structurally immutable.** Only `src/` is copied, so a kill-check *cannot*
  rewrite its own oracle. The worktree version copied tests too.
- The untracked-file trap disappears rather than being handled.
- No dependency on git state (this checkout is shallow), no leftover worktree entries, no
  `git apply` failure mode.
- `git status --porcelain` equality becomes structurally true instead of asserted.

Five contracts' worth of git mechanics became four contracts of directory copy and the
provenance probe that D1 proved is mandatory.

---

## 3. Suspicions — not confirmed, flagged for the implementer

- **S1 — overlay staleness under compiled artifacts.** `copytree` will copy `__pycache__` if
  present; a stale `.pyc` whose mtime/size matches could shadow the mutated `.py`. Unverified.
  Cheap guard: `ignore=shutil.ignore_patterns("__pycache__")`, and run the probe anyway.
- **S2 — `ast.unparse` on files using `from __future__ import annotations`.** Round-trip should
  preserve it, but `plan_ids.py` and friends lean on `typing.override`; a round-trip of a file
  with decorators-as-strings is worth one smoke test before trusting SLICE3 broadly.
- **S3 — cost.** One extra test run per `FUNCTIONAL` contract. I02's own plan has 21
  directives; a real increment with 40 contracts pays 40 extra runs. CT69 scopes each to the
  contract's own test, which should hold it to seconds, but it is unmeasured.

## 4. Checked and genuinely fine

- The three `contract-reference-undeclared` WARNs are cross-increment citations (CT26/CT37 as
  near-miss precedent, CT10b in Out of scope) — exactly what CT27 is a WARN for.
- `commands_for(None)` returns `()` on this plan: command ownership is total.
- `EvalVerdict` already contains `REPAIR_REQUIRED` and `RouteDecision` already contains
  `return_to_coder` (`workflow_artifacts.py:48-49`), so Q10(a) needs no new constant.
- `_deadline_exceeded` is already called at the top of `_run_stage` (`:536`), so CT47's
  between-command check is at the right, lower level and does not duplicate it.
- `tests/fixtures/session_wiring.py` exists and exports `make_mock_chain` / `make_session_state`.
- The kill-directive convention survives the shipped parser unchanged: `precheck` returns
  `ok=True` on the revised plan, 21 directives parse, zero validator problems.
