# FA Workflow — Reliable Use Strategies & Reference (2026-08-26)

> **Purpose:** Operator-facing strategy guide for `fa workflow`, grounded in
> verified code evidence. Every claim is referenced to the actual source.
> Commands are copy-pasteable to the host terminal.

---

## 0. What `fa workflow` Actually Is

`fa workflow` is a **multi-role state-machine controller** that advances a task
through the FA role protocol (planner → coder → eval) over a shared run-id,
workspace, and session. It is NOT a convenience macro for three `fa run` calls.

**Code evidence:**
- Controller entry: `src/fa/cli.py` → `_cmd_workflow()` (line 1859)
- State machine transitions: `_run_linear()`, `_run_repair()`, `_run_adaptive()` (lines 1718, 1751, 1578)
- Structured artifacts: `src/fa/inner_loop/workflow_artifacts.py` (EvalReport, FlowState, parse_eval_report)

**Boundary rule:** `fa run` = single-role invoker; `fa workflow` = multi-role state-machine advancer.
*(Code: `_cmd_workflow` docstring, line 1862)*

---

## 1. Three Modes — What Each Does (Code-Verified)

### 1.1 Linear (default) — One pass, fail-fast

**What happens:** Runs each role in order. If any stage returns non-zero exit, stops immediately.
After all stages, reads the eval's machine-readable verdict and sets the terminal `FlowState.status`.

**Code path:** `_run_linear()` → iterates roles, calls `_run_stage()` for each, writes terminal state.

**Exit code contract (S10c.2):**
- `0` = eval verdict was PASS (terminal status DONE)
- `1` = ran to completion but eval rejected (REPAIR_REQUIRED / REPLAN_REQUIRED / BLOCKED)
- `2` = usage/configuration error (e.g., missing role, bad mode name)

*(Code: `_workflow_exit_code()`, line 1831)*

### 1.2 Repair — One pass + bounded coder→eval loops

**What happens:** Runs the initial role list once. Then, while eval emits `route_decision=return_to_coder`
and the repair budget remains, re-runs `coder → eval` (canonical order).

**Does NOT do:** Planner re-entry. If eval says `return_to_planner` or `blocked`, those are recorded in
`flow_state.json` but the loop stops.

**Budget:** `--max-repairs` (default 2, hard ceiling 3).

**Precondition:** Roles must include both `coder` and `eval`.

**Code path:** `_run_repair()` → `_run_initial_roles()` then `while` loop on `return_to_coder`.

### 1.3 Adaptive — Full state machine with planner re-entry

**What happens:** Runs the initial role list once. Then normalizes loops to canonical routes:
- `return_to_coder` → `coder → eval` (repair round)
- `return_to_planner` → `planner → coder → eval` (replan round, bumps `active_plan_version`)

Any other route (`complete`, `blocked`) stops the loop.

**Budget:** `--max-repairs` (default 2, ceiling 3) + `--max-replans` (default 1, ceiling 2).

**Precondition:** Roles must include `planner`, `coder`, AND `eval`. Otherwise exits with code 2.

**Code path:** `_run_adaptive()` → `_run_initial_roles()` then `while True` loop branching on `eval_report.route_decision`.

**Important invariant:** After the initial pass, loop transitions use **canonical order**
(`_canonical_loop_roles()`, line 1551), NOT the user's input order. The initial pass
preserves the user's order; all subsequent rounds normalize.

---

## 2. Command Syntax — Complete Reference

```text
fa workflow <roles> <task> [options]
```

| Argument | Type | Description |
|---|---|---|
| `<roles>` | positional, required | Comma-separated: `planner,coder,eval` |
| `<task>` | positional, required | Task text (shared) — OR use per-role `--task-<role>` |
| `--task-planner` | optional | Override task for planner only |
| `--task-coder` | optional | Override task for coder only |
| `--task-eval` | optional | Override task for eval only |
| `--mode` / `-m` | optional | `linear` (default) \| `repair` \| `adaptive` |
| `--max-repairs` | optional | Max coder→eval repair rounds (default 2, ceiling 3) |
| `--max-replans` | optional | Max planner re-entry rounds (default 1, ceiling 2) |
| `--run-id` / `-i` | optional | Shared run_id (auto-generated if omitted) |
| `--workspace` / `-w` | optional | Shared workspace root |
| `--config` / `-c` | optional | Path to models.yaml |
| `--max-turns` / `-n` | optional | LLM-turn cap per role |
| `--output-mode` | optional | `console` (default) \| `quiet` |

*(Code evidence: argparse setup in `_cmd_workflow` args, lines 541-631)*

---

## 3. Machine-Readable Artifacts — What Gets Written Where

After every workflow run, two JSON artifacts are persisted under
`~/.fa/session-log/<run-id>/`:

### 3.1 `flow_state.json` — Controller Truth

| Field | Type | Meaning |
|---|---|---|
| `run_id` | string | Run identifier |
| `task` | string | Task text |
| `status` | enum | `INIT\|PLANNING\|PLAN_READY\|CODING\|CODER_BLOCKED\|EVALUATING\|REPAIR_REQUIRED\|REPLAN_REQUIRED\|DELTA_PLANNING\|DONE\|FAILED` |
| `active_role` | string | Current/last role |
| `active_plan_version` | int | Bumped on each planner re-entry |
| `repair_round` | int | Current repair round (0-based) |
| `replan_round` | int | Current replan round (0-based) |
| `last_actor` | string | Who made the last transition |
| `last_transition_reason` | string | Human-readable reason |
| `last_route_decision` | string | Eval's route: `complete\|return_to_coder\|return_to_planner\|blocked` |
| `blocked_reason` | string | Set when verdict is BLOCKED |

*(Code: `FlowState` dataclass, `workflow_artifacts.py` lines 259-304)*

### 3.2 `eval_report.json` — Evaluator Verdict

| Field | Type | Meaning |
|---|---|---|
| `verdict` | enum | `PASS\|REPAIR_REQUIRED\|REPLAN_REQUIRED\|BLOCKED` |
| `route_decision` | enum | `complete\|return_to_coder\|return_to_planner\|blocked` |
| `plan_version` | int | Which plan version was evaluated |
| `summary` | string | One-line summary |
| `step_results` | array | Per-step verdicts |
| `findings` | array | Typed findings with severity/class/route |
| `eval_independence` | object? | S13.4c stance record |

**How it's generated:** The parser `parse_eval_report()` reads the eval role's final
message and extracts the verdict from the `## Verification Summary` block. It is
**fail-closed**: unparseable output → `BLOCKED/blocked`.

*(Code: `parse_eval_report()`, `workflow_artifacts.py` lines 434-496)*

### 3.3 Verdict → Route Mapping (Hardcoded)

| Verdict | Default Route | Terminal FlowState Status |
|---|---|---|
| `PASS` | `complete` | `DONE` |
| `REPAIR_REQUIRED` | `return_to_coder` | `REPAIR_REQUIRED` |
| `REPLAN_REQUIRED` | `return_to_planner` | `REPLAN_REQUIRED` |
| `BLOCKED` | `blocked` | `FAILED` |

*(Code: `_VERDICT_TO_ROUTE`, `workflow_artifacts.py` line 372;
`_EVAL_VERDICT_TO_TERMINAL_STATUS`, `cli.py` line 1160)*

### 3.4 How to Inspect After a Run

```bash
# On host — inspect the artifacts:
cat ~/.fa/session-log/<run-id>/flow_state.json | python3 -m json.tool
cat ~/.fa/session-log/<run-id>/eval_report.json | python3 -m json.tool

# Find the most recent run-id:
ls -lt ~/.fa/session-log/ | head -5

# Or use fa stats:
fa stats --run-id <run-id>
fa stats --global-history
```

---

## 4. Copy-Paste Strategies — Progressive Difficulty

### Strategy 1: Linear Smoke Test (Simplest Possible)

**Goal:** Verify the full pipeline works end-to-end with a trivial read-only task.

```bash
fa workflow planner,coder,eval \
  "Прочитай AGENTS.md и создай краткое саммари основных правил проекта в виде markdown-файла. Не редактируй существующие файлы."
```

**What to observe:**
- Three stages run in order: `planner → coder → eval`
- Terminal summary: `fa workflow: accepted (verdict=PASS)` or rejection with verdict
- `flow_state.json` shows `status: DONE` or other terminal status
- Exit code: `echo $?` should be `0` for PASS, `1` for rejection

**Diagnostic if something fails:**
```bash
fa selfcheck            # verify config/routes
fa probe --role planner # test planner model (~10 tokens)
fa probe --role coder   # test coder model
fa probe --role eval    # test eval model
```

### Strategy 2: Linear with Per-Role Tasks

**Goal:** Give different instructions to each role for better control.

```bash
fa workflow planner,coder,eval \
  --task-planner "Проанализируй src/fa/cli_help.py и составь план добавления команды 'fa workflow-status' которая читает flow_state.json и печатает human-readable статус. Выведи план в pr_draft.md." \
  --task-coder "Реализуй план из pr_draft.md. Добавь команду workflow-status в cli.py и cli_help.py. Минимальный change-set." \
  --task-eval "Проверь реализацию по acceptance criteria из pr_draft.md. Оцени каждый шаг. Verdict в ## Verification Summary." \
  "Добавить команду fa workflow-status"
```

**Why per-role tasks:** The planner sees a planning instruction, the coder sees an implementation
instruction, and eval sees a verification instruction. The shared positional task acts as a
fallback/theme.

*(Code: `per_role_task` dict, `_cmd_workflow` line 1923; `task_for()` method, `_WorkflowContext` line 1233)*

### Strategy 3: Repair Mode — Self-Healing on Local Defects

**Goal:** Let the workflow automatically fix implementation-local issues found by eval.

```bash
fa workflow coder,eval \
  "Добавь функцию is_valid_run_id(s: str) -> bool в src/fa/cli.py которая валидирует run_id по паттерну [A-Za-z0-9_.-]{1,128}. Добавь тесты в tests/test_cli_ergonomics.py." \
  --mode repair \
  --max-repairs 2
```

**What to observe:**
1. First pass: `coder → eval`
2. If eval says `return_to_coder`: repair round 1: `coder → eval` again
3. If eval says `return_to_coder` again: repair round 2: `coder → eval`
4. If still failing after round 2: budget exhausted, workflow stops

**Key insight:** `--max-repairs 2` means up to 2 *additional* coder→eval cycles after the initial pass.
Total possible eval runs: 3 (1 initial + 2 repairs).

**Note:** `planner` is optional in repair mode — only `coder` and `eval` are required.

### Strategy 4: Adaptive Mode — Full State Machine

**Goal:** Enable planner re-entry when eval identifies plan-level issues.

```bash
fa workflow planner,coder,eval \
  "Рефакторинг: вынести workflow-контроллер из cli.py в отдельный модуль src/fa/workflow.py. Сохрани всё существующее поведение, все тесты должны проходить." \
  --mode adaptive \
  --max-repairs 2 \
  --max-replans 1
```

**What to observe:**
1. Initial pass: `planner → coder → eval`
2. If eval says `return_to_coder`: repair round (coder → eval)
3. If eval says `return_to_planner`: replan round (planner → coder → eval, plan_version bumped to 2)
4. Budgets: max 2 repair rounds AND max 1 replan round
5. Adaptive loops always use canonical order regardless of input order

**Critical precondition:** All three roles must be present. Otherwise:
```text
fa workflow: --mode adaptive requires roles to include planner and coder and eval (got coder,eval)
```
*(Code: precondition check, `_cmd_workflow` line ~1938)*

### Strategy 5: Adaptive with Explicit Run-ID (for Debugging)

**Goal:** Use a known run-id so you can easily find artifacts afterward.

```bash
fa workflow planner,coder,eval \
  -i debug-workflow-001 \
  "Создай README-секцию для fa workflow с примерами использования." \
  --mode adaptive --max-repairs 1 --max-replans 1

# After completion, inspect:
cat ~/.fa/session-log/debug-workflow-001/flow_state.json | python3 -m json.tool
cat ~/.fa/session-log/debug-workflow-001/eval_report.json | python3 -m json.tool
```

**Run-id validation:** Must match `[A-Za-z0-9_.-]{1,128}`.
*(Code: `_valid_run_id()` check, `_cmd_workflow` line ~1914)*

### Strategy 6: Quiet Mode for Scripting

**Goal:** Suppress progress output, capture only the exit code and final answer.

```bash
# In a script:
fa workflow planner,coder,eval "Fix the bug in X" --output-mode quiet
if [ $? -eq 0 ]; then
    echo "Workflow accepted"
else
    echo "Workflow rejected — check eval_report.json"
fi
```

**Exit code semantics:**
- `0` = PASS (work accepted)
- `1` = ran but rejected (REPAIR_REQUIRED / REPLAN_REQUIRED / BLOCKED)
- `2` = usage error

*(Code: `_workflow_exit_code()`, line 1831)*

---

## 5. Known Quirks & Gaps (Discovered from Code)

### Q-1: `active_plan_id` is always `run_id`

**Current behavior:** `active_plan_id` in FlowState is hardcoded to the `run_id`.
This is a deliberate bootstrap simplification.

**Code evidence:** Every `FlowState()` construction in `cli.py` sets `active_plan_id=ctx.run_id`.
*(e.g., `_write_terminal_state`, line 1438)*

**Impact:** No plan lineage tracking across replans. Plan version is tracked, but plan identity
is the same as run identity. Documented as D-1 in the operator memo.

### Q-2: Resume from persisted FlowState is NOT implemented

**Current behavior:** If a workflow is interrupted (Ctrl+C, OOM, server reboot),
you cannot resume from where it stopped. The `flow_state.json` records the last state,
but the controller does not read it back to continue.

**Code evidence:** No code path reads `flow_state.json` to resume a workflow. The only
read-back is `_read_back_terminal_state()` which reads the terminal state for exit code
derivation (line 1459), not for resumption.

**Workaround:** Re-run the workflow from scratch. Use `--run-id` to keep artifacts under
a known ID.

### Q-3: Repair mode does NOT re-enter planner

**Current behavior:** In `--mode repair`, if eval emits `return_to_planner`, the workflow
records it in `flow_state.json` but does NOT loop back to planner. The workflow stops.

**Code evidence:** `_run_repair()` only loops on `return_to_coder` (line 1755):
```python
while (
    eval_report is not None
    and eval_report.route_decision == "return_to_coder"
    and progress.repair_round < max_repairs
):
```

**Implication:** Use `--mode adaptive` if plan-level failures are expected.

### Q-4: Fail-fast on any non-zero stage exit

**Current behavior:** If ANY stage (planner, coder, or eval) returns non-zero, the entire
workflow stops immediately. There is no retry on infrastructure failures (e.g., API timeout).

**Code evidence:** Both `_run_linear()` and `_run_initial_roles()` check `result.exit_code != 0`
and return immediately.

**Workaround:** Re-run the workflow. The retry logic only applies to eval verdict-driven
repair/replan loops, not infrastructure failures.

### Q-5: Eval report parsing is fail-closed

**Current behavior:** If the eval role's final message doesn't contain a recognizable
`## Verification Summary` block with a verdict token, the parser defaults to
`BLOCKED/blocked`. This means the workflow will NOT pass even if the eval wrote
positive prose but didn't follow the output contract.

**Code evidence:** `parse_eval_report()`, line 434:
```python
if verdict is None:
    return EvalReport(..., verdict="BLOCKED", route_decision="blocked",
        summary="eval output did not contain a recognizable verdict token", ...)
```

**Practical tip:** If your eval model is weak and doesn't reliably emit the
`## Verification Summary` block, consider using `--mode linear` and manually
checking the eval output rather than relying on the automated verdict.

### Q-6: Per-role task override uses `--task-<role>` (dash, not underscore)

**Current behavior:** The CLI flag is `--task-planner`, `--task-coder`, `--task-eval`.
Internally, argparse stores these as `task_planner`, `task_coder`, `task_eval`.

**Code evidence:** `_cmd_workflow` reads `getattr(args, f"task_{role}", None)`.

### Q-7: Non-canonical role order is accepted for initial pass only

**Current behavior:** You can write `fa workflow eval,coder,planner "..."` and the initial
pass will run in that exact order. But in adaptive mode, all subsequent loops normalize
to canonical order (`coder→eval` for repair, `planner→coder→eval` for replan).

**Code evidence:** `_canonical_loop_roles()` (line 1551):
```python
def _canonical_loop_roles(roles, *, include_planner):
    canonical = ["planner", "coder", "eval"] if include_planner else ["coder", "eval"]
    return tuple(role for role in canonical if role in roles)
```

### Q-8: No `workflow status` or `workflow inspect` command exists yet

**Current behavior:** To inspect a workflow's state, you must manually read
`flow_state.json` and `eval_report.json` from the session-log directory.

**Code evidence:** No subcommand `workflow-status` is registered in the CLI parser.
This is explicitly listed in the deferred items register (operator memo, Option B).

---

## 6. Recommended Progression Path

### Phase A: Get Comfortable (Day 1-2)

1. **Smoke test** with Strategy 1 (linear, trivial task)
2. **Verify artifacts** — `cat` the `flow_state.json` and `eval_report.json`
3. **Test failure path** — give a task that's impossible to fully verify and watch
   how eval rejects it
4. **Check exit codes** — `echo $?` after each run

### Phase B: Productive Use (Day 3-5)

1. **Per-role tasks** with Strategy 2 for real implementation tasks
2. **Repair mode** with Strategy 3 for bug fixes and small features
3. **Use `fa stats`** to review token usage and tool patterns after each workflow

### Phase C: Advanced Patterns (Week 2+)

1. **Adaptive mode** with Strategy 4 for complex refactors
2. **Script integration** with Strategy 6 for CI-like automation
3. **Stress tasks** from the operator memo (§B-1 through B-5) to discover edge cases

### Phase D: Self-Development Loop (Ongoing)

1. Use `fa workflow` to develop features for First-Agent itself
2. After each workflow run, review `eval_report.json` for patterns
3. Track which types of tasks succeed on first pass vs. need repair
4. Identify model-specific quirks (e.g., eval model not emitting structured verdicts)

---

## 7. Pre-Flight Checklist Before First `fa workflow`

```bash
# 1. Verify stack is up:
fa status
# Expected: both containers healthy

# 2. Verify config:
fa selfcheck
# Expected: routes present, has_key=true for each

# 3. Verify each role's model:
fa probe --role planner
fa probe --role coder
fa probe --role eval
# Expected: OK for each (~10 tokens per probe)

# 4. Check your models.yaml has three distinct families:
cat /srv/first-agent/routing/models.yaml | grep -E "^(planner|coder|eval):" -A 3

# 5. Run the simplest workflow:
fa workflow planner,coder,eval "Прочитай README.md и создай краткое саммари."
```

---

## 8. Troubleshooting Quick Reference

| Symptom | Likely Cause | Fix |
|---|---|---|
| `service "first-agent" is not running` | Stack not started | `fa up` |
| `chain_exhausted` | API key/route issue | `fa selfcheck` then `fa probe --role <role>` |
| Exit code 2, "no task for role" | Missing task text | Provide positional task or `--task-<role>` |
| Exit code 2, "requires roles" | Missing required role for mode | Add `planner,coder,eval` for adaptive; `coder,eval` for repair |
| Verdict BLOCKED unexpectedly | Eval output didn't match contract | Check eval's actual text in `events.jsonl`; model may not emit `## Verification Summary` |
| `eval_report.json` shows `confidence: parsed:none` | Eval output was unparseable | Eval model failed to follow output contract; try stronger eval model |
| Repair loop doesn't trigger | Eval said `return_to_planner` in repair mode | Use `--mode adaptive` instead |
| `flow_state.json` not where expected | Run-id different from assumed | `ls -lt ~/.fa/session-log/ \| head` to find latest |

---

## 9. Architecture Summary (One Diagram)

```text
fa workflow planner,coder,eval "task" --mode adaptive
         │
         ▼
┌─ _cmd_workflow() ──────────────────────────────────────┐
│  1. Parse args, validate roles/mode/budgets             │
│  2. Generate/validate run_id                           │
│  3. Resolve session lifecycle (managed workspace clone) │
│  4. Write initial FlowState (status=PLANNING)          │
│  5. Dispatch to _run_linear / _run_repair / _run_adaptive │
│                                                         │
│  ┌─ _run_adaptive() ─────────────────────────────────┐ │
│  │  Initial pass: planner → coder → eval              │ │
│  │  ┌─ while True: ────────────────────────────────┐  │ │
│  │  │  if return_to_coder + budget → coder → eval   │  │ │
│  │  │  if return_to_planner + budget → P→C→E        │  │ │
│  │  │  if complete/blocked → STOP                   │  │ │
│  │  │  if budget exhausted → STOP                   │  │ │
│  │  └──────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│  6. Read back terminal FlowState                        │
│  7. Derive exit code from status (0=DONE, 1=other)     │
│  8. Export aggregate row to global_history.db           │
│  9. Return exit code                                   │
└─────────────────────────────────────────────────────────┘

Artifacts written:
  ~/.fa/session-log/<run-id>/flow_state.json   ← controller truth
  ~/.fa/session-log/<run-id>/eval_report.json   ← evaluator verdict
  ~/.fa/session-log/<run-id>/events.jsonl       ← human-readable mirror
  ~/.fa/sessions/<session-id>/session.db        ← authoritative SQLite
```

---

## 10. Key Source Files Reference

| File | Purpose |
|---|---|
| `src/fa/cli.py` lines 541-631 | CLI argument parser for `fa workflow` |
| `src/fa/cli.py` lines 1109-1160 | Artifact paths, verdict→status mapping |
| `src/fa/cli.py` lines 1220-1555 | `_WorkflowContext`, `_run_stage`, state writers, terminal summary |
| `src/fa/cli.py` lines 1556-1830 | `_run_initial_roles`, `_run_adaptive`, `_run_linear`, `_run_repair` |
| `src/fa/cli.py` lines 1831-2060 | `_workflow_exit_code`, `_cmd_workflow` entry point |
| `src/fa/inner_loop/workflow_artifacts.py` | `EvalReport`, `FlowState`, `parse_eval_report`, atomic JSON I/O |
| `src/fa/inner_loop/prompt.py` | System prompts for planner, coder, eval roles |
| `knowledge/prompts/architect-fa.md` | Planner prompt (full version) |
| `knowledge/prompts/architect-fa-compact.md` | Planner prompt (compact version) |
| `knowledge/instructions/02-operations.md` §7 | Operations manual for running tasks |
| `knowledge/research/fa-workflow-loop-implementation-plan-2026-06-29.md` | Design rationale and phased plan |
| `knowledge/research/fa-workflow-operator-maintainer-next-actions-memo-2026-06-30.md` | Operator memo: landed state, deferred items |
| `worklogs/DEPLOYMENT-ANATOMY.md` | Host deployment layout and proxy architecture |
