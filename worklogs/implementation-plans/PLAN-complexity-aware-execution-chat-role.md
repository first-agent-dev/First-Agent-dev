# PLAN: Complexity-Aware Execution — Chat Role, Workflow Escalation, Efficiency Tracking

**Plan-ID:** PLAN-complexity-aware-execution
**Status:** DRAFT   **Depth:** P2   **Revision:** v1
**Changed-since-last:** initial
**Upstream context:** E3 paper (arxiv 2607.13034), Code-as-Harness survey (arxiv 2605.18747),
`knowledge/research/E3-and-code-as-harness-deep-dive-2026-08-26.md`,
`knowledge/research/fa-workflow-escalation-research-2026-08-26.md`

---

## Preflight Log

```
roots checked:
  CLI entry:            src/fa/cli.py  → _cmd_run, _cmd_workflow, _cmd_stats
  Role prompts:         src/fa/inner_loop/prompt.py → _ROLE_PROMPTS dict (planner,coder,eval)
  Role tool registries: src/fa/inner_loop/tools/__init__.py → build_*_registry()
  Role→registry router: src/fa/cli.py:_build_role_registry (security boundary)
  Models config:        src/fa/providers/config.py → ModelsConfig.roles mapping
  Global history:       src/fa/inner_loop/global_history.py → GlobalHistoryStore
  Workflow controller:  src/fa/cli.py → _run_linear, _run_repair, _run_adaptive
  Workflow artifacts:   src/fa/inner_loop/workflow_artifacts.py → EvalReport, FlowState
  ADR index:           knowledge/adr/ → 14 ADRs, ADR-16 absent (gap)
  ADR template:        knowledge/adr/ADR-template.md

greps/reads → findings:
  _ROLE_PROMPTS          → 3 entries (planner, coder, eval); chat=NEW
  build_system_message() → falls back to CODER_SYSTEM_PROMPT for unknown roles
  _build_role_registry() → security boundary: planner=readonly, eval=verifier, else=baseline
  build_baseline_registry() → full read+write+bash+search+blackboard+pair
  build_planner_registry() → readonly+search+blackboard+observability
  build_eval_registry()    → verifier (bash only)+read+observability
  _cmd_workflow()         → takes argparse.Namespace; NOT callable as internal function
  _run_linear/repair/adaptive → internal functions, already decomposed
  global_history schema   → run_id, role, model, family, tokens, tool_count, duration, stop_reason
  fa stats --global-history → reads global_history.db, renders table or JSON
  ModelsConfig.roles      → Mapping[str, ChainConfig] — role name is dict key
  models.yaml.example    → planner/coder/eval sections; compactor optional; chat=NEW

gold patterns mirrored:
  Role addition:         compactor role (ADR-17) — optional role with models.yaml entry
  Tool registry:         build_planner_registry → build_chat_registry (NEW)
  CLI subcommand:        _cmd_workflow pattern for internal dispatch
  Stats extension:       _cmd_stats_global_history pattern for new metrics

conflicts/invariants:
  I-7.1 Pair-over-Autonomy: chat is pair mode, not autonomous
  I-6.3 Substrate Formality: simple chain first, topology last
  ADR-2 eval-disjoint: chat family may share with coder (not eval)
  ADR-7 tool registry: chat registry must be registered in profiles or __init__.py
  ADR-11 TCB: chat role must not weaken authoring guardrails
  ADR-12 secrets: chat role inherits proxy mode, no key access
  ADR-13 workspace: chat operates in managed workspace clone

current liveness:
  chat role system prompt:     L0 (absent)
  chat tool registry:          L0 (absent)
  scope estimator function:    L0 (absent)
  invoke_workflow tool:        L0 (absent)
  run_workflow():              L3 (SHIPPED S4a in workflow_controller.py;
                               the plan originally called this
                               _run_workflow_internal in cli.py — that symbol
                               was never created)
  ACRR metric in fa stats:     L0 (absent)
  ADR-16:                      L0 (absent)
  models.yaml chat entry:      L0 (absent)

unresolved → Q#:
  Q1 (non-blocking): Should chat role support --resume for multi-turn conversation
     within a session? Default: YES, reuse existing session infrastructure.
  Q2 (non-blocking): Should the estimator be configurable via config.yaml
     (e.g., custom keyword lists)? Default: NO for v1; hardcoded keywords,
     promote to config if real usage shows need.
```

---

## 0. Executive Intent

**IDEA:** Add complexity-aware execution to First-Agent: a chat role that
estimates task scope before dispatching, handles simple tasks directly,
and escalates complex tasks to the workflow pipeline via a tool call.
Track efficiency with an ACRR proxy metric.

**PROJECT MEANING:** This closes the gap between FA's two execution modes
(`fa run` for single-role, `fa workflow` for multi-role) by adding an
**automatic routing layer** that decides which to use. This is the E3
"Estimate → Execute → Expand" pattern applied to FA's orchestration.

**GOALS:**
- **G1:** Operator types `fa run -r chat "task"` and the harness automatically
  routes to direct execution (L1/L2) or workflow escalation (L3).
- **G2:** Scope estimation costs zero LLM tokens — deterministic Python function.
- **G3:** Efficiency is measurable and tracked via ACRR proxy in `fa stats`.
- **G4:** Architecture is captured in ADR-16 for future reference.

**NON-GOALS:**
- Parallel subagents or DAG orchestration (substrate formality first, §1.2.6)
- Learned routing classifier (requires benchmark data; defer to v2)
- Conversational multi-turn chat mode (separate future feature, `fa ask`)
- Automatic workflow mode selection (linear vs adaptive) — operator chooses
- Modifying existing planner/coder/eval role behavior

**MECHANISM SKETCH:**
`fa run -r chat "task"` → deterministic `estimate_scope(task)` → if L1/L2:
chat role handles directly with restricted tools; if L3: chat role calls
`invoke_workflow` tool → `run_workflow()` (workflow_controller.py) → workflow pipeline
runs in shared session.

**PROOF SKETCH:** C1 test on `estimate_scope()` with fixture tasks; C1 test
on `invoke_workflow` tool calling `run_workflow()`; C2 test on
`fa run -r chat` routing; C1 test on ACRR computation in `fa stats`.

**SIZE:** L (3 slices, new role, new ADR, CLI changes, tool registration)

---

## 1. Current State → Target State

### AS-IS (source-verified)

| Dimension | Finding |
|---|---|
| Roles | 3 roles in `_ROLE_PROMPTS`: planner, coder, eval |
| Chat role | absent after grep |
| Scope estimator | absent after grep |
| invoke_workflow tool | absent after grep |
| ACRR metric | absent after grep in global_history.py |
| Workflow callability | `_cmd_workflow` takes `argparse.Namespace`, not internally callable |
| ADR-16 | absent — gap in ADR numbering |
| models.yaml | 3 roles + optional compactor; no chat |

### TO-BE (machine-checkable)

- **GAP1:** No chat role exists → add system prompt, tool registry, models.yaml entry
- **GAP2:** No scope estimator exists → add `estimate_scope()` function
- **GAP3:** No workflow escalation tool exists → add `invoke_workflow` tool
- **GAP4:** `_cmd_workflow` is not internally callable → refactor to `run_workflow()` ✅ CLOSED in S4a (extracted to workflow_controller.py, not cli.py)
- **GAP5:** No efficiency metric exists → add ACRR proxy to `fa stats` and `global_history.db`
- **GAP6:** No ADR captures the architecture → write ADR-16

---

## 2. Contracts

### CT1: Scope Estimator Function

```
CT1: estimate_scope() TYPE:function/module (REVISED — types tightened)
PRODUCER: NEW src/fa/inner_loop/scope_estimator.py:estimate_scope
ROOTS/CALLERS: src/fa/cli.py:_cmd_run (pre-dispatch), chat system prompt
INPUTS: task: str → OperatingPoint dataclass
OUTPUTS: OperatingPoint(
           difficulty: Literal[1, 2, 3],
           scope: Literal["single-file", "cross-file", "repo"],
           risk: Literal["low", "medium", "high"],
           confidence: float,
           recommended_mode: Literal["chat_direct", "chat_planned", "workflow_linear"]
         )
ERRORS: ValueError("task must be non-empty") on empty or whitespace-only task
SIDE EFFECTS: none (pure function)
INVARIANTS:
  - difficulty ∈ {1, 2, 3} (enforced by Literal type)
  - scope ∈ {"single-file", "cross-file", "repo"} (enforced by Literal type)
  - risk ∈ {"low", "medium", "high"} (enforced by Literal type)
  - recommended_mode ∈ {"chat_direct", "chat_planned", "workflow_linear"} (enforced by Literal type)
  - confidence ∈ [0.0, 1.0]
  - confidence = 0.8 if winning level has ≥2 matches, 0.6 if 1 match, 0.3 if 0 matches
  - Security signals boost difficulty by +1 (capped at 3)
  - No LLM call, no I/O, no imports beyond stdlib
  - No Unicode normalization performed (documented)
KILL-CHECK: removing estimate_scope call in _cmd_run → T3 fails (routing test)
```

### CT2: Chat Role System Prompt

```
CT2: CHAT_SYSTEM_PROMPT TYPE:signal
PRODUCER: src/fa/inner_loop/prompt.py:CHAT_SYSTEM_PROMPT constant
CONSUMER: build_system_message(role="chat") → injected into LLM system message
TRIGGER: fa run -r chat
PAYLOAD: System prompt — pair programming partner, scope-aware, knows about
         the invoke_workflow tool, uses fs_search and fs_read_file for
         codebase exploration, and writes/edits files directly for work it
         sizes as small.
REVISED 2026-08-26 (operator decision Q1): the earlier payload said chat
         "does NOT have write/edit tools directly". That is no longer true and
         was never a security boundary — see CT3. Chat holds fs_write_file and
         fs_edit_file with no path allowlist. The split the prompt teaches is
         a JUDGEMENT (small change -> do it here; large change -> escalate),
         not a capability the registry enforces.
CONTENT SOURCE: the prompt body is the researched variant, not the S2
         scaffold. Ships in S6.
DUAL-WRITE: N/A (prompt is single-source)
KILL-CHECK: removing "chat" from _ROLE_PROMPTS → T5 fails (chat role test)
```

### CT3: Chat Tool Registry

```
CT3: build_chat_registry() TYPE:function/module (REVISED — profiles.py approach)
PRODUCER: NEW src/fa/inner_loop/tools/__init__.py:build_chat_registry
          + src/fa/inner_loop/profiles.py:PROFILES_RAW["chat"]
ROOTS/CALLERS: src/fa/cli.py:_build_role_registry when role=="chat"
INPUTS: workspace_root: Path, bash_timeout_seconds: int
OUTPUTS: ToolRegistry with: fs_read_file, fs_write_file, fs_edit_file,
         fs_search, fs_blackboard_query, fs_run_bash (stateful PTY),
         fs_exploration_metrics, fs_reach, fs_spawn_subagent,
         + invoke_workflow (added in S4b)
         + pr_prepare (appended for every role by _build_run_tool_registry)
SIDE EFFECTS: none
INVARIANTS:
  - Chat profile defined in PROFILES_RAW with tools list
  - build_chat_registry delegates to build_registry_for_role("chat", ...)
  - INCLUDES fs_write_file and fs_edit_file, with NO path allowlist
  - bash_impl == "stateful" (cd/env/venv persist across turns, ADR-14)
  - Every tool the profile declares has a builder: the set difference
    {declared} - {built} MUST be empty at the profile layer
  - DOES include invoke_workflow (added in S4b, registered post-profile)
  - Pattern mirrors build_planner_registry (tools/__init__.py:168)
REVISED 2026-08-26 (operator decision Q1/Q2/Q4b, shipped in a638253):
  Chat previously declared 6 read-only tools. Withholding write tools was
  described as a security boundary; it was not one. Chat's bash was never
  restricted (see RK5), so a read-only registry only forced file mutation to
  happen through a less observable channel. Scope discipline is the scope
  estimator's job. Note also that fs_spawn_subagent was ALREADY registered for
  every role unconditionally by _register_extra_tools (tools/__init__.py) —
  declaring it in the chat profile documents reality rather than granting new
  capability.
KILL-CHECK: removing invoke_workflow from chat registry → T7 fails
KILL-CHECK: removing fs_write_file from the chat profile → the profile/registry
  parity test fails (tests/test_chat_role.py)
```

### CT4: invoke_workflow Tool

```
CT4: invoke_workflow TYPE:function (tool)
PRODUCER: NEW src/fa/inner_loop/tools/workflow_tool.py:build_invoke_workflow_tool
CONSUMER: chat role LLM calls it when the scope estimate says the work is large
INPUTS: {task: str (required), mode: str="linear",
         roles: str="planner,coder,eval",
         max_repairs: int=2, max_replans: int=1}
OUTPUTS: ToolResult.ok(summary, result={
           "run_id": str,        # the CHILD run_id, not the parent's
           "exit_code": int,
           "status": str,        # terminal FlowState.status; "" if unavailable
           "route": str,         # FlowState.last_route_decision; "" if unavailable
           "timed_out": bool,    # True when the deadline stopped the pipeline
         })
         NO "verdict" FIELD. run_workflow returns tuple[int, FlowState | None]
         and FlowState has no verdict attribute (fields: run_id, task, status,
         active_role, active_plan_id, active_plan_version, repair_round,
         replan_round, last_actor, last_transition_reason, last_route_decision,
         blocked_reason, completed_steps, invalidated_steps). The verdict lives
         on EvalReport, which is NOT returned. The status mapping is also lossy
         — EVAL_VERDICT_TO_TERMINAL_STATUS sends BLOCKED -> "FAILED"
         (workflow_controller.py:50-55) — so a verdict cannot be reconstructed
         from status either. Consumers that need the verdict read
         eval_report.json under the child run_id's directory.
SIDE EFFECTS: runs the full workflow pipeline; writes flow_state.json and
              eval_report.json under the CHILD run_id's own directory
permission: "workspace"

INVARIANTS (REVISED 2026-08-26 — see "run identity" below):
  - Shares session_context / session_db (same session_id: one conversation)
  - Allocates a NEW child run_id: f"{parent_run_id}-wf{n}", n starting at 1
    and incrementing per invocation within the session
  - Does NOT create a new SESSION (session_id is inherited)
  - Returns structured result, not raw exit code
  - mode ∈ {"linear", "adaptive"}
  - Re-entrancy: the tool is registered ONLY in the chat registry. If it is
    ever dispatched while a workflow is already running in this process, the
    handler MUST fail with code "workflow_reentrant" rather than recurse.

RUN IDENTITY — why the child gets its own run_id:
  The earlier invariant "shares session context, creates no new session" was
  implemented as "reuse the parent run_id". That is unsafe, and it was
  confirmed by execution rather than argued:
    1. workflow_artifact_paths(run_id) (workflow_controller.py:133) and
       _cmd_run's run_log_dir (cli.py:1766) resolve to the SAME directory, so
       parent and child share one events.jsonl. The parent's read_all() then
       returns the child's events, and _extract_telemetry_from_log
       (global_history.py:248) counts the child's usage/tool_call events as
       the parent's turns and tool totals.
    2. global_history.runs has run_id as PRIMARY KEY with INSERT OR REPLACE
       (global_history.py:140, :178). The child exports its aggregate during
       the tool call; the parent exports after drive_session returns
       (cli.py:1938). The parent's write lands second and ERASES the child's
       row, including its scope_estimate_json.
    3. A second invocation in the same session overwrites the first's
       flow_state.json and eval_report.json.
  A distinct child run_id fixes all three and makes the parent/child relation
  queryable (child run_ids are prefixed with the parent's).
  NOTE: control flow is NOT affected by (3) — _run_adaptive threads
  eval_report in memory (workflow_controller.py:467). The damage from (3) is
  to audit and external readers only.

KILL-CHECK: removing invoke_workflow from chat registry → T7 fails
KILL-CHECK: making the child reuse the parent run_id → T13 fails (two distinct
  global_history rows expected)
```

### CT5: run_workflow() — the shared controller entry point

> **CORRECTED 2026-08-26.** This contract named `_run_workflow_internal` in
> `src/fa/cli.py`. That symbol does not exist and never shipped:
> `grep -rn "_run_workflow_internal" src/` returns no matches. S4a extracted
> the controller to its own module instead. The contract below describes what
> is actually on main.

```
CT5: run_workflow() TYPE:function
PRODUCER: src/fa/inner_loop/workflow_controller.py:run_workflow  (SHIPPED S4a)
ROOTS/CALLERS: src/fa/cli.py:_cmd_workflow (cli.py:1201),
               invoke_workflow tool (S4b)
INPUTS (all keyword-only):
        roles: list[str], task: str | None,
        per_role_task: Mapping[str, str | None], mode: str,
        max_repairs: int, max_replans: int, run_id: str,
        config: Path, workspace: Path, max_turns: int,
        output_mode: str = "console",
        run_stage_fn: Callable[..., int],          # REQUIRED, no default
        transport: Transport | None = None,
        secrets: Mapping[str, str] | None = None,
        session_context: SessionContext | None = None,
        run_context: RunContext | None = None,
        session_db: SessionDatabase | None = None
OUTPUTS: tuple[int, FlowState | None] (exit_code, terminal_state)
SIDE EFFECTS: writes flow_state.json, eval_report.json, events.jsonl;
              exports one aggregate row to global_history
INVARIANTS:
  - No argparse dependency at the signature (pure structured params).
    NOTE: _run_stage internally BUILDS an argparse.Namespace to call
    run_stage_fn (workflow_controller.py:254). That is the injection
    contract, not a leak — run_stage_fn is _cmd_run, which reads args.
  - run_stage_fn is REQUIRED. The only production implementation is
    _cmd_run (cli.py:1213). Any caller must supply it; there is no default.
  - workflow_controller does NOT import fa.cli (verified). The dependency
    points one way: cli -> controller.
  - Existing behavior byte-identical (no test changes for existing tests)
KILL-CHECK: if _cmd_workflow bypasses run_workflow → existing workflow tests fail
```

### CT6: ACRR Proxy Metric

```
CT6: compute_acrr_proxy() TYPE:function/module
PRODUCER: NEW src/fa/inner_loop/acrr.py:compute_acrr_proxy
CONSUMER: fa stats (per-run), global_history.db (cross-run projection)
INPUTS: files_read: int, files_changed: int
OUTPUTS: float | None  — files_read / files_changed, or None when
         files_changed == 0
SIDE EFFECTS: none (pure function)
INVARIANTS:
  - ACRR == 1.0 when files_read == files_changed (optimal)
  - ACRR > 1.0 when files_read > files_changed (over-reading)
  - ACRR is never negative
  - files_changed == 0 returns None ("no denominator"), NOT a number
  - files_read == 0 and files_changed == 0 returns None
  - ValueError on negative inputs (a count cannot be negative)

REVISED 2026-08-26 — why None and not max(files_changed, 1):
  The original spec required compute_acrr_proxy(10, 0) == 10.0 via
  max(files_changed, 1). That makes the metric's most pathological input —
  read 10 files, changed nothing, i.e. pure unproductive exploration —
  numerically IDENTICAL to compute_acrr_proxy(10, 1), a perfectly healthy
  run. The sentinel is unfalsifiable: the one case RN9 says ACRR exists to
  detect is the one case it cannot express. Returning None keeps
  "undefined ratio" distinguishable from "ratio of 10", and forces the
  display layer to say so.
  Consumers render None as "n/a (no files changed)".

KILL-CHECK: removing ACRR from stats output → T10 fails
KILL-CHECK: changing the zero case back to max(files_changed, 1) → the
  C0 test asserting None for (10, 0) fails
```

### CT7: ADR-16

```
CT7: ADR-16 TYPE:document
PRODUCER: EDIT (file already exists, see S6 note) knowledge/adr/ADR-16-complexity-aware-execution.md
CONSUMER: future sessions, llms.txt routing, AGENTS.md reference
TRIGGER: architectural reference for chat role + escalation + efficiency
PAYLOAD: Decision record covering: chat role design, E3 estimator pattern,
         invoke_workflow tool, ACRR tracking, research backing
KILL-CHECK: N/A (document, not code)
```

---

## 3. Path & Flag Matrix

### Path Inventory

| P# | Trigger | Source Site | Target Behavior | S# | T# |
|---|---|---|---|---|---|
| P1 | L1 task (single file, simple) | estimate_scope → d̂=1 | Chat handles directly, no escalation | S2 | T3 |
| P2 | L2 task (cross-file, medium) | estimate_scope → d̂=2 | Chat plans briefly, then codes | S2 | T4 |
| P3 | L3 task (architectural, complex) | estimate_scope → d̂=3 | Chat calls invoke_workflow | S3 | T5,T7 |
| P4 | Ambiguous task (low confidence) | estimate_scope → ĉ<0.5 | Chat handles with caution, may escalate | S2 | T6 |
| P5 | Empty/malformed task | estimate_scope → ValueError | CLI returns exit 2 | S1 | T2 |
| P6 | invoke_workflow fails (stage error) | workflow pipeline | Tool returns error summary to chat | S4 | T8 |
| P7 | ACRR computation (normal run) | fa stats | Shows file_read/file_changed/ACRR | S5 | T10 |
| P8 | ACRR computation (no files changed) | fa stats | ACRR = files_read / 1 (protected) | S5 | T11 |

### Matrix

| M# | Config | Proves | T# |
|---|---|---|---|
| M1 | models.yaml with chat role declared | Chat role dispatches correctly | T5 |
| M2 | models.yaml without chat role | Falls back to coder (existing behavior) | T9 |
| M3 | Default config (no config.yaml) | Estimator uses hardcoded keywords | T3 |
| M4 | Proxy mode (FA_EGRESS_PROXY_URL set) | Chat inherits proxy rewrite | N/A — inherits from _cmd_run |

---

## 4. Artifacts Inventory

| A# | Path | Action | Owner S# |
|---|---|---|---|
| A1 | `src/fa/inner_loop/scope_estimator.py` | ADD | S1 |
| A2 | `src/fa/inner_loop/prompt.py` — CHAT_SYSTEM_PROMPT, _ROLE_PROMPTS | EDIT | S2 |
| A3 | `src/fa/inner_loop/tools/__init__.py` — build_chat_registry | EDIT | S3 |
| A4 | `src/fa/inner_loop/tools/workflow_tool.py` | ADD | S4 |
| A5 | `src/fa/cli.py` — _build_role_registry, _build_run_tool_registry, _cmd_run, _cmd_stats | EDIT | S4b, S5 |
| A5b | `src/fa/inner_loop/workflow_controller.py` — run_workflow | SHIPPED S4a | S4a |
| A6 | `src/fa/inner_loop/acrr.py` | ADD | S5 |
| A7 | `src/fa/cli.py` — _cmd_stats | EDIT | S5 |
| A8 | `src/fa/inner_loop/global_history.py` — schema extension | EDIT | S5 |
| A9 | `knowledge/adr/ADR-16-complexity-aware-execution.md` | EDIT | S6 |
| A10 | `knowledge/templates/models.yaml.example` — chat section | EDIT | S2 |
| A11 | `tests/test_scope_estimator.py` | ADD | S1 |
| A12 | `tests/test_chat_role.py` | ADD | S2,S3 |
| A13 | `tests/test_invoke_workflow_tool.py` | ADD | S4 |
| A14 | `tests/test_acrr.py` | ADD | S5 |
| A15 | `knowledge/llms.txt` — routing update | EDIT | S6 |
| A16 | `knowledge/instructions/02-operations.md` — chat role docs | EDIT | S6 |

---

## 5. Implementation Slices

### S1: Scope Estimator (P0 foundation — pure function, no deps) ✅ DONE 2026-08-26

> **Implementation:** 31 tests pass, mypy strict clean, ruff clean.
> **Report:** worklogs/reviews/S1-IMPLEMENTATION-REPORT-2026-08-26.md

**Traces-to:** G2, GAP2, CT1
**Depends-on:** none
**Target liveness:** L0→L3

```
EDIT PACKET E1 / S1 (REVISED — defects closed)
What: Add deterministic scope estimator module.
Concrete intent: Pure function that classifies task text into L1/L2/L3.
AS-IS: absent
TO-BE: estimate_scope(task) → OperatingPoint in <1ms, no imports beyond stdlib.

Exact code mechanism:
  NEW src/fa/inner_loop/scope_estimator.py
  - OperatingPoint dataclass (frozen, typed with Literal)
  - _KEYWORD_PATTERNS: frozenset of compiled regex patterns per level
  - estimate_scope(task: str) → OperatingPoint

Allowed files:
  src/fa/inner_loop/scope_estimator.py (NEW)
  tests/test_scope_estimator.py (NEW)

Do:
  1. Define OperatingPoint dataclass with Literal types (strict mypy compliance):
     @dataclass(frozen=True)
     class OperatingPoint:
         difficulty: Literal[1, 2, 3]
         scope: Literal["single-file", "cross-file", "repo"]
         risk: Literal["low", "medium", "high"]
         confidence: float
         recommended_mode: Literal["chat_direct", "chat_planned", "workflow_linear"]

  2. Define _KEYWORD_PATTERNS as compiled regexes (frozenset of re.Pattern):
     L3: r"\brefactor\b", r"\bredesign\b", r"\bmigrate\b", r"\brestructure\b",
         r"\bnew subsystem\b", r"\bprotocol\b", r"\barchitecture\b",
         r"\bacross.*codebase\b", r"\bevery.*call.?site\b"
     L2: r"\badd.*function\b", r"\bimplement\b", r"\bnew.*command\b",
         r"\bcross-file\b", r"\b2.*files\b", r"\b3.*files\b"
     L1: r"\bfix typo\b", r"\brename\b", r"\bupdate.*docstring\b",
         r"\bsingle.*file\b", r"\bone.*line\b"
     Security: r"\bauth\b", r"\bpermission\b", r"\bsecret\b",
               r"\bsandbox\b", r"\bsecurity\b"

  3. Implement estimate_scope with explicit algorithm:
     a. Reject empty/whitespace-only: if not task or not task.strip(): raise ValueError
     b. Count keyword matches per level (re.IGNORECASE)
     c. Determine difficulty (priority: L3 > L2 > L1):
        - l3_count > 0 → difficulty=3, scope="repo", risk="high", mode="workflow_linear"
        - l2_count > 0 → difficulty=2, scope="cross-file", risk="medium", mode="chat_planned"
        - l1_count > 0 → difficulty=1, scope="single-file", risk="low", mode="chat_direct"
        - else         → difficulty=1, scope="single-file", risk="low", mode="chat_direct"
     d. Confidence: 0.8 if count >= 2 for the winning level, 0.6 if count == 1,
        0.3 if no signals matched (optimistic default per E3 principle)
     e. Security boost: if security_count > 0 and difficulty < 3: difficulty += 1
     f. Return OperatingPoint with all fields populated

  4. Write C0 tests with 15 explicit fixtures (5 per level):
     L1: "fix typo in README.md", "rename variable foo to bar",
         "update docstring in function baz", "fix single line bug",
         "add comment to clarify logic"
     L2: "add fs_chunk tool for codebase indexing",
         "implement new CLI command fa ask",
         "add unit tests for scope_estimator module",
         "update 2 files to fix import cycle",
         "implement caching layer for fs_search"
     L3: "refactor workflow controller for parallel execution",
         "redesign the session management architecture",
         "migrate all tools from legacy API to new protocol",
         "restructure the provider chain for multi-tenant support",
         "implement new subsystem for distributed task execution across codebase"

  5. Write C0p boundary tests with explicit boundaries:
     - Empty string: raises ValueError("task must be non-empty")
     - Whitespace-only ("   \n\t  "): raises ValueError("task must be non-empty")
     - Very long task (10,000 chars): does not crash, returns valid OperatingPoint
     - Non-English ("исправить опечатку в README.md"): returns difficulty=1,
       confidence=0.3, mode="chat_direct" (optimistic default)
     - Security boost: "fix auth permission bug" → difficulty=2 (L1 + security boost)

Do-not:
  - Import any FA modules (pure stdlib function)
  - Use LLM for classification
  - Read files or make I/O calls
  - Add configuration (hardcoded for v1, see Q2)
  - Perform Unicode normalization (document that it's not performed)

Exit criteria:
  - [ ] estimate_scope("fix typo in README.md") → OperatingPoint(difficulty=1, scope="single-file", risk="low", confidence=0.8, recommended_mode="chat_direct")
  - [ ] estimate_scope("add fs_chunk tool") → OperatingPoint(difficulty=2, scope="cross-file", risk="medium", confidence=0.8, recommended_mode="chat_planned")
  - [ ] estimate_scope("refactor workflow controller for parallel execution") → OperatingPoint(difficulty=3, scope="repo", risk="high", confidence=0.8, recommended_mode="workflow_linear")
  - [ ] estimate_scope("") → raises ValueError("task must be non-empty")
  - [ ] estimate_scope("   ") → raises ValueError("task must be non-empty")
  - [ ] estimate_scope("исправить опечатку") → OperatingPoint(difficulty=1, confidence=0.3, recommended_mode="chat_direct")
  - [ ] All 15 C0 fixtures pass: pytest tests/test_scope_estimator.py -v
  - [ ] All 5 C0p boundary tests pass
  - [ ] No imports beyond stdlib (verified by grep)
  - [ ] mypy strict passes: python -m mypy src/fa/inner_loop/scope_estimator.py --strict

Kill-check: N/A (pure function, no producer site in production code yet)

Test class: C0 + C0p
Oracle: exact OperatingPoint field match
```

### S2: Chat Role (prompt + registry + models.yaml) ✅ DONE 2026-08-26

> **Implementation:** 27 tests pass (58 total with S1), mypy strict clean, ruff clean.
> **Report:** worklogs/reviews/S2-IMPLEMENTATION-REPORT-2026-08-26.md
> **Revision note:** CHAT_SYSTEM_PROMPT content and chat tool set will be revised in S6 (last slice) as extra task — current versions are minimal scaffolds sufficient for S3–S5 integration.

**Traces-to:** G1, GAP1, CT2, CT3
**Depends-on:** S1 (estimator exists)
**Target liveness:** L0→L2 (L3 requires S4 for invoke_workflow)

```
EDIT PACKET E2 / S2 (REVISED — registry approach clarified)
What: Add chat as first-class role with system prompt and tool registry.
AS-IS: 3 roles (planner, coder, eval)
TO-BE: 4 roles (planner, coder, eval, chat)

Exact code mechanism:
  1. src/fa/inner_loop/prompt.py:
     - Add CHAT_SYSTEM_PROMPT constant (minimal pair-programming prompt)
     - Add "chat": CHAT_SYSTEM_PROMPT to _ROLE_PROMPTS dict
  2. src/fa/inner_loop/profiles.py:
     - Add "chat" profile to PROFILES_RAW dict:
       "chat": {
           "description": "Pair programming partner with scope-aware routing",
           "tools": ["fs_read_file", "fs_search", "fs_blackboard_query",
                     "fs_run_bash", "fs_reach"],
           "max_tokens": 800,
           "stateless": True,
           "bash_impl": "stateless",  # read-only bash for exploration
       }
     - invoke_workflow tool added separately in S4 (not in profile yet)
  3. src/fa/inner_loop/tools/__init__.py:
     - Add build_chat_registry() that calls build_registry_for_role("chat", ...)
     - Pattern mirrors build_planner_registry (line 168)
  4. src/fa/cli.py:_build_role_registry:
     - Add `if role == "chat": return build_chat_registry(...)` branch
  5. knowledge/templates/models.yaml.example:
     - Add optional chat section with comment

Allowed files:
  src/fa/inner_loop/prompt.py
  src/fa/inner_loop/profiles.py
  src/fa/inner_loop/tools/__init__.py
  src/fa/cli.py
  knowledge/templates/models.yaml.example
  tests/test_chat_role.py (NEW)

Do:
  1. Write CHAT_SYSTEM_PROMPT (~800 words): pair programming partner,
     scope-aware, uses fs_search/fs_read_file for exploration,
     knows about invoke_workflow for complex tasks (added in S4),
     does NOT have write/edit tools (escalates instead)
  2. Register in _ROLE_PROMPTS
  3. Add "chat" profile to PROFILES_RAW in profiles.py
  4. Implement build_chat_registry() following build_planner_registry pattern:
     ```python
     def build_chat_registry(
         workspace_root: Path,
         *,
         bash_timeout_seconds: int = DEFAULT_BASH_TIMEOUT_SECONDS,
     ) -> ToolRegistry:
         """Chat = pair programming partner (read+search+bash+blackboard)."""
         try:
             from fa.inner_loop.profiles import build_registry_for_role
             registry = build_registry_for_role("chat", workspace_root, bash_timeout=bash_timeout_seconds)
         except ToolSchemaPortabilityError:
             raise
         except Exception as exc:
             logger.warning(f"Failed to build chat registry via profiles, fallback: {exc}")
             registry = ToolRegistry()
             registry.register(build_read_file_tool(workspace_root))
             registry.register(build_run_bash_tool(workspace_root, timeout_seconds=bash_timeout_seconds))
         # Note: invoke_workflow tool added in S4
         return registry
     ```
  5. Add chat branch to _build_role_registry in cli.py:
     ```python
     if role == "chat":
         return build_chat_registry(workspace, bash_timeout_seconds=bash_timeout_seconds)
     ```
  6. Add chat section to models.yaml.example (commented, optional)
  7. Write C1 test: fa run -r chat "fix typo" dispatches with chat prompt
  8. Write C1 test: build_chat_registry returns expected tool names

Do-not:
  - Give chat role fs_write_file or fs_edit_file   [REVERSED by Q1, 2026-08-26]
  - Give chat role fs_spawn_subagent               [REVERSED by Q2, 2026-08-26]
  - Make chat role mandatory in models.yaml (optional, falls back to coder)
  - Build registry manually in tools/__init__.py (use profiles.py pattern)

Exit criteria:
  - [ ] "chat" in _ROLE_PROMPTS → True
  - [ ] "chat" in PROFILES_RAW → True
  - [ ] build_chat_registry returns registry with fs_search, fs_read_file, fs_run_bash
  - [x] ~~build_chat_registry does NOT include fs_write_file, fs_edit_file~~
        SUPERSEDED 2026-08-26 by operator decision Q1 (commit a638253): chat
        now HAS fs_write_file + fs_edit_file with no allowlist. Left visible
        rather than deleted so the S2 record stays honest about what changed.
  - [ ] fa selfcheck --role chat works when chat declared in models.yaml
  - [ ] fa selfcheck --role chat falls back gracefully when not declared
  - [ ] C1 tests pass: pytest tests/test_chat_role.py -v

Kill-check: removing "chat" from _ROLE_PROMPTS → test_chat_role_prompt_registered fails

Test class: C1
Oracle: tool registry contents + system prompt identity + profile presence
```

### S3: Scope Estimator Integration in CLI ✅ DONE 2026-08-26

> **Implementation:** 4 new C1 tests in test_cli_ergonomics.py (97 total pass: 31 S1 + 27 S2 + 39 ergonomics).
> **mypy strict clean, no regressions in 35 pre-existing tests.**
> **Report:** worklogs/reviews/S3-IMPLEMENTATION-REPORT-2026-08-26.md
> **Extra file:** src/fa/output.py (added "scope_estimate" to LogKind — required prerequisite not in plan).

**Traces-to:** G1, G2, GAP2, CT1 (consumer side)
**Depends-on:** S1, S2
**Target liveness:** L0→L3

```
EDIT PACKET E3 / S3 (REVISED — integration point corrected)
What: Wire estimate_scope into _cmd_run pre-dispatch for chat role.
AS-IS: _cmd_run dispatches directly to drive_session
TO-BE: _cmd_run calls estimate_scope when role=="chat", logs result,
       threads recommended_mode into system_prompt_extra (NOT initial_memory_summary)

Exact code mechanism:
  src/fa/cli.py:_cmd_run
  - After role resolution (line ~2410), before drive_session call (line ~2650):
    scope_hint = ""
    if role == "chat":
        from fa.inner_loop.scope_estimator import estimate_scope
        try:
            scope = estimate_scope(args.task or "")
            log.append(
                actor="harness",
                kind="scope_estimate",
                content={
                    "difficulty": scope.difficulty,
                    "scope": scope.scope,
                    "risk": scope.risk,
                    "confidence": scope.confidence,
                    "recommended_mode": scope.recommended_mode,
                    "task_preview": (args.task or "")[:120],
                },
            )
            scope_hint = (
                f"## Task Scope Estimate\n"
                f"Difficulty: {scope.difficulty} ({scope.scope})\n"
                f"Risk: {scope.risk} | Confidence: {scope.confidence:.1f}\n"
                f"Recommended mode: {scope.recommended_mode}\n"
            )
        except ValueError:
            pass  # empty task — let chat role handle normally

  - In drive_session call:
    system_prompt_extra=scope_hint,  # NOT initial_memory_summary
    # initial_memory_summary remains reserved for resume_draft_text

NOTE: initial_memory_summary is reserved for resume drafts
(cli.py:2650). Injecting scope hints there would mix concerns and
break resume functionality. system_prompt_extra is the correct seam —
it appends to the system prompt after the role prompt, which is where
advisory context belongs.

Allowed files:
  src/fa/cli.py
  tests/test_cli_ergonomics.py (EDIT)

Do:
  1. Import estimate_scope lazily inside _cmd_run (avoid module-level import cost)
  2. Add scope estimation block after role resolution, before drive_session
  3. Log scope estimate as event (kind="scope_estimate", actor="harness")
  4. Thread scope hint into system_prompt_extra (NOT initial_memory_summary)
  5. Handle ValueError gracefully (empty task → skip estimation)
  6. Write C1 test: chat role run logs scope_estimate event
  7. Write C1 test: scope_estimate event has correct difficulty field
  8. Write C1 test: system_prompt_extra contains scope hint (not initial_memory_summary)

Do-not:
  - Block dispatch based on estimate (it's advisory, not gating)
  - Add new CLI flags for scope estimation
  - Inject scope hint into initial_memory_summary (reserved for resume drafts)
  - Import estimate_scope at module level (lazy import preserves startup time)

Exit criteria:
  - [ ] fa run -r chat "fix typo" → events.jsonl contains scope_estimate with difficulty=1
  - [ ] fa run -r coder "fix typo" → NO scope_estimate event (only chat role)
  - [ ] system_prompt_extra contains "## Task Scope Estimate" (verified by test)
  - [ ] initial_memory_summary does NOT contain scope hint (verified by test)
  - [ ] Empty task does not crash (ValueError handled gracefully)
  - [ ] C1 tests pass

Kill-check: removing estimate_scope call → test_scope_estimate_logged fails

Test class: C1
Oracle: event_log contains scope_estimate event with correct fields + system_prompt_extra assertion
```

### S3.5: Scope Estimate Observability — stats + blackboard + global_history ✅ DONE 2026-08-26

> **Implementation:** 3 contract tests fixed, 2 new C1 tests added. 3192 total pass, 0 regressions.
> **mypy strict clean.** All stats/blackboard/global_history test suites green.
> **Report:** worklogs/reviews/S3.5-IMPLEMENTATION-REPORT-2026-08-26.md

**Traces-to:** G3, GAP5 (partial), CT1 (consumer side — full data path)
**Depends-on:** S3 (scope_estimate events exist in event_log)
**Target liveness:** L0→L3

> **Motivation:** S3 writes scope_estimate events to session.db event_log and
> events.jsonl, but three downstream consumers are blind to them:
> 1. `fa stats` — scope_estimate is in PARSED_KINDS (derived from LogKind minus
>    UNPARSED_KINDS) but has no dispatch branch in _parse_events, causing two
>    pre-existing contract tests to FAIL (test_s9_parsed_kinds_matches_dispatch,
>    test_unparsed_kinds_complete). This is a regression from S3.
> 2. Blackboard — scope_estimate goes to event_log table only, not blackboard
>    table. fs_blackboard_query cannot find scope estimates.
> 3. global_history.db — _extract_telemetry_from_log ignores scope_estimate
>    events. Cross-run analytics cannot see scope routing decisions.

```
EDIT PACKET E3.5 / S3.5
What: Wire scope_estimate events into all three observability consumers.
AS-IS: scope_estimate in event_log only; stats contract tests FAIL;
       blackboard blind; global_history blind
TO-BE: scope_estimate parsed by fa stats, written to blackboard,
       projected into global_history.db

Exact code mechanism:

  ── 1. fa stats integration (src/fa/stats.py) ─────────────────────────

  a. Add ScopeEstimateRecord dataclass:
     @dataclass(frozen=True)
     class ScopeEstimateRecord:
         difficulty: int
         scope: str
         risk: str
         confidence: float
         recommended_mode: str
         task_preview: str = ""

  b. Add field to SessionAnalytics:
     scope_estimates: list[ScopeEstimateRecord] = field(default_factory=list)

  c. Add elif branch in _parse_events dispatch:
     elif kind == "scope_estimate":
         scope_estimates.append(
             ScopeEstimateRecord(
                 difficulty=int(content.get("difficulty", 0)),
                 scope=str(content.get("scope", "")),
                 risk=str(content.get("risk", "")),
                 confidence=float(content.get("confidence", 0.0)),
                 recommended_mode=str(content.get("recommended_mode", "")),
                 task_preview=str(content.get("task_preview", "")),
             )
         )

  d. Add rendering in render_session (after Guards section):
     if a.scope_estimates:
         w("🎯 Scope estimates:\n")
         for se in a.scope_estimates:
             w(f"   d̂={se.difficulty} ({se.scope}) risk={se.risk} "
               f"conf={se.confidence:.1f} → {se.recommended_mode}\n")
             if se.task_preview:
                 w(f"   task: {se.task_preview[:80]}\n")
         w("\n")

  e. Add to __all__: "ScopeEstimateRecord"

  ── 2. Blackboard write (src/fa/cli.py) ──────────────────────────────

  In the scope estimation block (after log.append), add blackboard write:
    if state.blackboard is not None:
        from fa.blackboard.blackboard import BlackboardEntry
        state.blackboard.write(
            BlackboardEntry(
                type="scope_estimate",
                content_hash="",  # computed by Blackboard.write
                payload={
                    "difficulty": scope.difficulty,
                    "scope": scope.scope,
                    "risk": scope.risk,
                    "confidence": scope.confidence,
                    "recommended_mode": scope.recommended_mode,
                    "task_preview": (args.task or "")[:120],
                },
            )
        )

  NOTE: BlackboardEntry has many optional fields (toolchain_digest,
  schema_version, parent_id, read_set, write_set, assumptions,
  version_dependencies). For scope_estimate, all are empty/defaults —
  this is an advisory signal, not a tool output. The blackboard's
  write() method handles defaults correctly.

  ── 3. global_history projection (src/fa/inner_loop/global_history.py) ─

  a. Add scope_estimate_json column to runs table schema (additive):
     scope_estimate_json TEXT NOT NULL DEFAULT '{}'

  b. Add extraction in _extract_telemetry_from_log:
     scope_estimate: dict[str, Any] = {}
     ...
     elif ev.kind == "scope_estimate":
         c = ev.content if isinstance(ev.content, Mapping) else {}
         scope_estimate = {
             "difficulty": int(c.get("difficulty", 0)),
             "scope": str(c.get("scope", "")),
             "risk": str(c.get("risk", "")),
             "confidence": float(c.get("confidence", 0.0)),
             "recommended_mode": str(c.get("recommended_mode", "")),
         }
     ...
     return { ..., "scope_estimate_json": json.dumps(scope_estimate) }

  c. Add to build_export_row: pass through scope_estimate_json
  d. Add to export_run SQL: include scope_estimate_json in INSERT

  ── 4. Tests ──────────────────────────────────────────────────────────

  a. Fix existing contract tests (test_s19_stats_parsers.py):
     - test_s9_parsed_kinds_matches_dispatch: now passes (dispatch branch exists)
     - test_unparsed_kinds_complete: now passes (scope_estimate not in UNPARSED)

  b. New test in test_cli_ergonomics.py:
     - test_chat_role_scope_estimate_in_blackboard: verify blackboard entry
       written with type="scope_estimate" and correct payload

  c. New test in test_cli_ergonomics.py or test_global_history.py:
     - test_scope_estimate_in_global_history: verify scope_estimate_json
       column populated after chat role run

Allowed files:
  src/fa/stats.py (EDIT — dataclass + dispatch + render)
  src/fa/cli.py (EDIT — blackboard write in scope block)
  src/fa/inner_loop/global_history.py (EDIT — schema + extraction + export)
  tests/test_cli_ergonomics.py (EDIT — blackboard + global_history tests)
  tests/test_s19_stats_parsers.py (FIX — contract tests now pass)

Do:
  1. Add ScopeEstimateRecord dataclass and SessionAnalytics field to stats.py
  2. Add elif branch for scope_estimate in _parse_events
  3. Add rendering section in render_session
  4. Verify test_s9_parsed_kinds_matches_dispatch passes
  5. Verify test_unparsed_kinds_complete passes
  6. Add blackboard write to cli.py scope estimation block
  7. Add scope_estimate_json to global_history schema + extraction + export
  8. Write C1 test: blackboard contains scope_estimate after chat run
  9. Write C1 test: global_history has scope_estimate_json after chat run
  10. Run full test suite — zero regressions

Do-not:
  - Add scope_estimate to UNPARSED_KINDS (it IS actionable analytics)
  - Change BlackboardEntry schema (use defaults for optional fields)
  - Add migration script for global_history (ALTER TABLE ADD COLUMN is additive)
  - Block on blackboard write failure (best-effort, same as event_log)

Exit criteria:
  - [ ] test_s9_parsed_kinds_matches_dispatch PASSES (was FAILING)
  - [ ] test_unparsed_kinds_complete PASSES (was FAILING)
  - [ ] fa stats shows "🎯 Scope estimates:" section for chat role runs
  - [ ] fs_blackboard_query type=scope_estimate returns entries
  - [ ] global_history.db runs table has scope_estimate_json column
  - [ ] All existing tests pass (zero regressions)
  - [ ] New C1 tests pass

Kill-check:
  - removing scope_estimate elif branch → test_s9_parsed_kinds_matches_dispatch fails
  - removing blackboard write → test_chat_role_scope_estimate_in_blackboard fails
  - removing scope_estimate_json extraction → test_scope_estimate_in_global_history fails

Test class: C1 (integration)
Oracle: contract test pass + blackboard query + global_history column
```

### S4a: Extract Workflow Controller to Separate Module ✅ DONE 2026-08-26

> **Implementation:** 564 tests pass (all workflow/cli/scope/blackboard/global_history/stats tests).
> cli.py: 3965 → 3165 lines (−800). workflow_controller.py: 792 lines (NEW).
> **Report:** worklogs/reviews/S4a-IMPLEMENTATION-REPORT-2026-08-26.md

---

> **⏸ STOP POINT — 2026-08-26**
> S1 through S4a are complete and verified. Slices S1, S2, S3, S3.5, S4a
> are implemented, tested (564+ tests pass), and documented.
> Remaining slices: S4b (invoke_workflow tool), S5 (ACRR proxy), S6 (ADR-16 + docs).
> Patch file: `patches/P2-S1-S4a-stop-point.patch`

---

**Traces-to:** GAP4, CT5
**Depends-on:** S2 (chat registry exists), S3 (scope estimator integrated)
**Target liveness:** L0→L3

> **Motivation:** cli.py is 3965 lines. The workflow controller (~970 lines, 18
> functions + 3 dataclasses + 5 constants) is a self-contained subsystem that
> can be extracted to its own module. This reduces cli.py complexity, makes the
> workflow controller independently testable, and creates a clean foundation for
> S4b (invoke_workflow tool) and future iteration.

```
EDIT PACKET E4a / S4a
What: Extract workflow controller from cli.py to workflow_controller.py.
AS-IS: ~970 lines of workflow code in cli.py (3965 lines total)
TO-BE: workflow_controller.py (~970 lines), cli.py (~3000 lines)

Exact code mechanism:

  ── Dependency graph (no circular imports) ────────────────────────────

  workflow_controller.py does NOT import from cli.py.
  Instead, _run_stage receives run_stage_fn as a callable parameter.
  cli.py imports from workflow_controller.py (one-way dependency).

  cli.py ──imports──▶ workflow_controller.py
    │                        │
    │  _cmd_run              │  run_workflow()
    │  _eval_system_prompt_  │  _run_linear/repair/adaptive
    │    extra               │  _run_stage (takes run_stage_fn)
    │                        │  Context/Progress/Result types
    │                        │
    └──── passed as ────────▶│  run_stage_fn parameter

  ── Module: src/fa/inner_loop/workflow_controller.py (NEW) ───────────

  Move from cli.py:
    Constants:
      _EVAL_VERDICT_TO_TERMINAL_STATUS
      _WORKFLOW_STATUS_TO_STOP_REASON
      DEFAULT_MAX_REPAIRS, MAX_REPAIRS_CEILING
      DEFAULT_MAX_REPLANS, MAX_REPLANS_CEILING
      _WORKFLOW_MODES

    Dataclasses:
      _WorkflowArtifactPaths → WorkflowArtifactPaths (public)
      _WorkflowContext → WorkflowContext (public)
      _WorkflowProgress → WorkflowProgress (public)
      _StageResult → StageResult (public)

    Functions:
      _slugify_task → slugify_task (public)
      _workflow_artifact_paths → workflow_artifact_paths (public)
      _emit_eval_report → emit_eval_report (public)
      _eval_system_prompt_extra → eval_system_prompt_extra (public)
      _eval_independence_mapping (stays private)
      _status_for_role → status_for_role (public)
      _run_stage → _run_stage (private, takes run_stage_fn param)
      _write_stage_failure_state (private)
      _write_terminal_state (private)
      _read_back_terminal_state → read_back_terminal_state (public)
      _print_terminal_summary (private)
      _resolve_max_repairs (private)
      _resolve_max_replans (private)
      _render_mode_label (private)
      _canonical_loop_roles (private)
      _run_initial_roles (private)
      _run_adaptive (private)
      _run_linear (private)
      _run_repair (private)
      _workflow_exit_code → workflow_exit_code (public)
      _cmd_workflow body → run_workflow() (NEW public API, no argparse)

  ── run_workflow() signature (the internal API) ─────────────────────

  def run_workflow(
      *,
      roles: list[str],
      task: str | None,
      per_role_task: Mapping[str, str | None],
      mode: str,
      max_repairs: int,
      max_replans: int,
      run_id: str,
      workspace: Path,
      config: Path,
      max_turns: int,
      output_mode: str,
      run_stage_fn: Callable[..., int],  # _cmd_run or equivalent
      transport: Transport | None = None,
      secrets: Mapping[str, str] | None = None,
      session_context: SessionContext | None = None,
      run_context: RunContext | None = None,
      session_db: SessionDatabase | None = None,
  ) -> tuple[int, FlowState | None]:
      """Run the workflow pipeline. Callable from CLI and from tools."""

  ── _run_stage refactoring ──────────────────────────────────────────

  _run_stage currently calls _cmd_run directly. After extraction, it
  receives run_stage_fn as a parameter (dependency injection):

  def _run_stage(
      ctx: WorkflowContext,
      role: str,
      *,
      fresh: bool,
      progress: WorkflowProgress,
      transition_reason: str,
      run_stage_fn: Callable,  # NEW parameter
  ) -> StageResult:
      ...
      code = run_stage_fn(stage_args, transport=..., secrets=..., ...)
      ...

  ── cli.py changes ──────────────────────────────────────────────────

  1. Remove all moved functions/classes/constants
  2. Add imports from workflow_controller:
     from fa.inner_loop.workflow_controller import (
         run_workflow, workflow_exit_code, eval_system_prompt_extra,
         read_back_terminal_state, workflow_artifact_paths,
         DEFAULT_MAX_REPAIRS, DEFAULT_MAX_REPLANS,
         MAX_REPAIRS_CEILING, MAX_REPLANS_CEILING,
         _WORKFLOW_MODES,
     )
  3. _cmd_workflow becomes thin wrapper:
     def _cmd_workflow(args):
         ... parse args, resolve lifecycle ...
         code, terminal_state = run_workflow(
             roles=roles, task=base_task, ...,
             run_stage_fn=_cmd_run,
         )
         return workflow_exit_code(code, terminal_state)
  4. _cmd_run uses eval_system_prompt_extra from new module

Allowed files:
  src/fa/inner_loop/workflow_controller.py (NEW — ~970 lines)
  src/fa/cli.py (EDIT — remove ~970 lines, add imports + thin wrapper)
  tests/test_cli_ergonomics.py (EDIT — update imports if needed)

Do:
  1. Create workflow_controller.py with all moved code
  2. Refactor _run_stage to take run_stage_fn parameter
  3. Create run_workflow() as the public API (no argparse)
  4. Make _cmd_workflow a thin wrapper around run_workflow()
  5. Update cli.py imports
  6. Verify ALL existing workflow tests pass (regression gate)
  7. Verify cli.py line count drops by ~900+ lines

Do-not:
  - Change workflow controller logic (_run_linear, _run_repair, _run_adaptive)
  - Change FlowState or EvalReport schemas
  - Add new workflow modes
  - Import cli.py from workflow_controller.py (no circular deps)
  - Change any test assertions (pure refactor)

Exit criteria:
  - [ ] workflow_controller.py exists with ~970 lines
  - [ ] cli.py drops from ~3965 to ~3000 lines
  - [ ] No circular imports (verified by import test)
  - [ ] All existing workflow tests pass: pytest tests/test_cli_ergonomics.py -v
  - [ ] All existing cli tests pass (zero regressions)
  - [ ] _cmd_workflow delegates to run_workflow() (verified by code review)
  - [ ] run_workflow() callable without argparse (verified by direct call test)

Kill-check:
  - removing run_workflow delegation in _cmd_workflow → existing workflow tests fail
  - removing run_stage_fn parameter → _run_stage cannot call _cmd_run

Test class: C1 (regression)
Oracle: existing workflow test suite passes unchanged
```

### S4b: invoke_workflow Tool ✅ DONE 2026-08-27

> **Shipped.** `workflow_tool.py` (NEW), registered at the CLI seam for `chat`
> only; RK6 deadline in `workflow_controller` + `runtime_limits`;
> `tests/test_invoke_workflow_tool.py` (76) and `tests/test_workflow_deadline.py`
> (11). Suite 3371p/7f (7 = known env baseline). Mutation **18/18 killed**.
> Gates: ruff, mypy (6-error baseline), pylint 10.00/10, 7/7 contract scripts.
>
> **Q15 resolved = A (standardise).** `invoke_workflow` registers at the CLI
> seam, so `build_chat_registry` does not contain it and the Q12 self-retiring
> exemption would NOT have fired. The coherence oracle in
> `tests/test_prompt_registry_coherence.py` now reads the LIVE corpus
> (`cli._build_run_tool_registry`, 13 tools) instead of the profile layer, and
> `_PENDING_REGISTRATION` is **empty**: the chat prompt has zero
> advertised-but-unregistered tools.
>
> **Deviations from the packet, all verified:**
> - Non-chat caller is at `cli.py:2391` (packet said 2378) and is hardcoded
>   `"coder"`, so it can never reach the chat branch; it passes no context.
> - The context provider was extracted to a module-level
>   `_make_workflow_ctx_provider` because the inline closure pushed `_cmd_run`
>   past the C901 complexity ceiling (16 > 15).
> - `_write_stage_failure_state` gained a pass-through for
>   `WORKFLOW_DEADLINE_EXIT_CODE`; without it fail-fast overwrote the deadline's
>   terminal state with `stage exited 124` and `timed_out` reported False.
>   (Mutation M9 confirms.)
> - Five new public symbols had to be added to `__all__`
>   (`FA-AUTHORING-V2-EXPORTS-COMPLETENESS`).
> - `tests/_chat_registry_fixture.py` extracted at the third duplicate copy.
>
> **RK8 remains open** and is unchanged by this slice: `fa workflow --roles`
> accepts `chat` as a stage role, which the thread-local guard cannot see
> because that stage runs in a separate process.


**Traces-to:** G1, GAP3, CT4
**Depends-on:** S4a (run_workflow exists in workflow_controller.py)
**Target liveness:** L0→L3

```
EDIT PACKET E4b / S4b
What: Add invoke_workflow tool so the chat role can escalate large tasks.
AS-IS: chat role has no way to reach the workflow pipeline; the scope
       estimator's output has no consumer (S1/S3 sit at L2).
TO-BE: chat calls invoke_workflow -> run_workflow() under a CHILD run_id,
       sharing the session but not the run identity.

PREREQUISITE FACTS (verified on main, do not re-derive):
  - run_workflow lives in workflow_controller.py, NOT cli.py. See CT5.
  - run_workflow REQUIRES run_stage_fn; the only implementation is
    _cmd_run (cli.py:1213). Omitting it is a TypeError.
  - build_chat_registry delegates to build_registry_for_role("chat", ...),
    which builds from PROFILES_RAW. A profile-declared tool needs a builder
    in profiles.py taking only (root). invoke_workflow needs CLI-owned
    values, so it CANNOT be profile-declared. Register it post-profile.
  - _build_run_tool_registry (cli.py:1376) already appends pr_prepare after
    the role registry is built. That is the precedent and the seam to use.
  - permission MUST be "workspace" (the schema and wire-name were
    pre-validated: validate_tool_schema_portability passes,
    is_valid_wire_name("invoke_workflow") is True).
  - invoke_workflow does NOT need adding to _NEVER_PARALLEL_TOOLS to be
    safe: _should_parallelize_tool_batch falls through to "unknown tool ->
    serial" for any spec whose permission != "read" (loop.py:149-158,
    verified by execution). Add it anyway for intent, but do NOT claim it
    closes a hole.

Exact code mechanism:
  1. NEW src/fa/inner_loop/tools/workflow_tool.py:

     @dataclass(frozen=True)
     class WorkflowInvocationContext:
         """Everything run_workflow needs that the tool cannot invent."""
         parent_run_id: str
         config: Path
         workspace: Path
         max_turns: int
         session_context: SessionContext | None
         run_context: RunContext | None
         session_db: SessionDatabase | None
         transport: Transport | None
         secrets: Mapping[str, str] | None
         run_stage_fn: Callable[..., int]

     def build_invoke_workflow_tool(
         run_workflow_fn: Callable[..., tuple[int, FlowState | None]],
         ctx_provider: Callable[[], WorkflowInvocationContext],
     ) -> ToolSpec

     REPLACES the earlier "session_ctx_factory" parameter, which had no
     type, no return shape and no named caller.

  2. Child run_id allocation, inside the handler:
       counter starts at 0 in the closure; each successful admission does
       n += 1 and child_run_id = _child_run_id(ctx.parent_run_id, n).
       Rationale in CT4 "RUN IDENTITY".

     _child_run_id MUST respect the run_id grammar, which is validated in
     two places with the SAME effective limit:
       cli.py:125          ^[A-Za-z0-9_.-]{1,128}$
       session/manager.py  [A-Za-z0-9][A-Za-z0-9_.-]{0,127}   (128 total)
     Naive concatenation overflows: a 125-char parent yields a 129-char
     child that fails validation (verified by execution). Truncate the
     PARENT, never the suffix, so the discriminator always survives:

       def _child_run_id(parent: str, n: int) -> str:
           suffix = f"-wf{n}"
           head = parent[: 128 - len(suffix)]
           return f"{head}{suffix}"

     Import the pattern rather than re-typing it; assert the result matches
     before use and fail with code "invalid_child_run_id" if it does not.

  3. Re-entrancy guard: a module-level threading.local flag, set in a
     try/finally for the duration of the handler. If already set ->
     ToolResult.fail("workflow_reentrant", ...).

     threading.local is the correct primitive here, not a plain bool:
     read-only tool batches are dispatched on a ThreadPoolExecutor
     (loop.py:361-366), so a process-global flag could be observed across
     unrelated worker threads. invoke_workflow itself always runs serially
     (its permission is "workspace", so _should_parallelize_tool_batch
     refuses to batch it — loop.py:149-158), but the guard must not depend
     on that remaining true.

     What this guard does and does not cover, stated honestly:
       COVERS: the same thread re-entering invoke_workflow while a pipeline
         is already running on it — the recursion case.
       DOES NOT COVER: `fa workflow --roles planner,chat,eval`. Workflow
         roles are split from a raw string with no allowlist
         (cli.py:1136), so "chat" is accepted as a stage role today. That
         stage runs in a SEPARATE process (run_stage_fn -> _cmd_run), so
         thread-local state cannot see it.
       Mitigation for the uncovered case is a role allowlist in
       _cmd_workflow, which is OUT OF SCOPE for S4b and recorded as RK8.
       Do not silently widen this slice to fix it.

  4. src/fa/cli.py:_build_run_tool_registry — after the pr_prepare append,
     add: if role == "chat": registry.register(build_invoke_workflow_tool(...)).
     The ctx_provider closes over the local run_id/config/workspace/etc.
     already in scope at the _cmd_run call site.
     NOTE: _build_run_tool_registry's current signature does not carry these
     values. Extend it with one keyword-only parameter
     `workflow_ctx: Callable[[], WorkflowInvocationContext] | None = None`
     and pass None from the non-run caller (cli.py:2378). When None and
     role == "chat", skip registration and log a warning — a chat registry
     built outside a live run legitimately has no workflow to invoke.

RK6 DESIGN — nested-pipeline deadline (operator decision 2026-08-26: MUST
be handled in S4b, not deferred):

  THE PROBLEM, restated from evidence. Serial tool dispatch has no timeout:
  the only timeouts in loop.py are on the parallel branch (wait(...,
  timeout=30) at :367, fut.result(timeout=5) at :371). RuntimeLimits has no
  wall-clock session cap. So one invoke_workflow call can run planner ->
  coder -> eval plus up to MAX_REPAIRS_CEILING repair rounds and
  MAX_REPLANS_CEILING replan rounds with no upper bound on elapsed time,
  blocking the chat turn indefinitely.

  MECHANISM — cooperative deadline checked between stages.

  Chosen over the two alternatives on purpose:
    - signal.alarm / SIGALRM: main-thread only, does not compose with the
      ThreadPoolExecutor path, and interrupts at an arbitrary instruction
      leaving flow_state.json half-written. Rejected.
    - killing a subprocess: run_stage_fn is an in-process call
      (_cmd_run), not a subprocess. Nothing to kill. Rejected.
  A cooperative check cannot interrupt a stage already in flight, and that
  limit is stated rather than hidden: the effective worst case is
  deadline + one stage. That is acceptable because a single stage is
  already bounded by max_iterations and bash_timeout_seconds; the unbounded
  quantity is the NUMBER of stages, which is exactly what this caps.

  IMPLEMENTATION:
    1. runtime_limits.py: add "workflow_timeout_seconds" to _KNOWN_KEYS and
       to the RuntimeLimits dataclass, default
       DEFAULT_WORKFLOW_TIMEOUT_SECONDS = 1800 (30 min). Strictly positive,
       so it is NOT added to _ZERO_ALLOWED_KEYS and NOT added to the float
       keys — it parses as int like every other cap.
    2. workflow_controller.py: run_workflow gains
       `deadline_mono: float | None = None` (keyword-only, defaults None =
       no deadline, so every existing caller including _cmd_workflow is
       byte-identical).
    3. A single guard helper checked at the TOP of _run_stage — the one
       choke point every dispatch funnels through. Six call sites today
       (:443 _run_initial_roles, :505 and :545 _run_adaptive, :581
       _run_linear, :630 and :642 _run_repair); the last two disappear when
       _run_repair is removed per Q3, leaving four. Guarding inside
       _run_stage rather than at the call sites is what makes that churn
       irrelevant:

         def _deadline_exceeded(ctx) -> bool:
             return (ctx.deadline_mono is not None
                     and time.monotonic() >= ctx.deadline_mono)

       Put deadline_mono on WorkflowContext so it threads with the rest of
       the run state rather than through seven signatures.
    4. On expiry: do NOT raise. Write a terminal FlowState with
       status="FAILED" and last_transition_reason=
       f"workflow deadline exceeded after {elapsed}s", emit the aggregate
       global_history row as usual, and return a non-zero result code.
       The run stays observable and the artifacts stay well-formed — the
       same discipline as the existing budget-exhausted paths
       (_run_adaptive's "repair budget exhausted" branch).
    5. The tool sets timed_out=True in its result when the terminal
       reason carries the deadline marker, so the chat model can tell
       "the pipeline failed" from "the pipeline ran out of time" and
       respond differently.

  WHY NOT cap it in the tool alone: a deadline enforced only in the tool
  would have to abandon a still-running pipeline, orphaning its artifacts
  and its global_history row. Enforcing inside the controller means the
  pipeline stops itself cleanly and stays auditable.

Allowed files:
  src/fa/inner_loop/tools/workflow_tool.py (NEW)
  src/fa/cli.py (EDIT — _build_run_tool_registry signature + registration)
  src/fa/inner_loop/loop.py (EDIT — one line, _NEVER_PARALLEL_TOOLS)
  src/fa/inner_loop/workflow_controller.py (EDIT — deadline_mono param,
    WorkflowContext field, _run_stage guard; RK6)
  src/fa/inner_loop/runtime_limits.py (EDIT — workflow_timeout_seconds; RK6)
  tests/test_invoke_workflow_tool.py (NEW)
  tests/test_workflow_deadline.py (NEW — RK6)
  NOT tools/__init__.py: registration happens at the CLI seam, because the
  tool needs CLI-owned context. Editing build_chat_registry would force a
  cli import into the tools package.

Do:
  1. Implement the ToolSpec with input_schema:
     {"type": "object",
      "properties": {
        "task":        {"type": "string", "minLength": 1},
        "mode":        {"type": "string", "enum": ["linear", "adaptive"]},
        "roles":       {"type": "string"},
        "max_repairs": {"type": "integer", "minimum": 0,
                        "maximum": MAX_REPAIRS_CEILING},   # == 3
        "max_replans": {"type": "integer", "minimum": 0,
                        "maximum": MAX_REPLANS_CEILING}},  # == 2
      "required": ["task"],
      "additionalProperties": false}
     Defaults applied in the handler, not the schema: mode="linear",
     roles="planner,coder,eval", max_repairs=2, max_replans=1.
  2. Handler contract, in order:
     a. reentrancy guard -> fail "workflow_reentrant"
     b. ctx_provider() is None -> fail "workflow_unavailable"
     c. parse roles on "," , strip, drop empties; empty result ->
        fail "invalid_roles"
     d. mode not in {"linear","adaptive"} -> fail "invalid_mode"
        (schema also enforces this; the handler check is the fail-closed
        half for any caller that bypasses validation)
     e. allocate child run_id via _child_run_id; validate against the
        run_id pattern -> fail "invalid_child_run_id" on mismatch
     f. compute the deadline: monotonic() + ctx.workflow_timeout_seconds
        (see RK6 DESIGN below)
     g. call run_workflow_fn(..., run_id=child_run_id, per_role_task={},
        output_mode="quiet", run_stage_fn=ctx.run_stage_fn,
        deadline_mono=deadline)
     h. any exception from run_workflow -> fail "workflow_error" with
        str(exc); never propagate (a tool must not kill the chat session)
     i. success -> ToolResult.ok(summary, result={...}) per CT4 OUTPUTS,
        with timed_out reflecting whether the deadline fired
  3. Register at the CLI seam per mechanism step 4.
  4. Add "invoke_workflow" to _NEVER_PARALLEL_TOOLS (intent, not fix).

Do-not:
  - Change workflow controller logic
  - Add new workflow modes
  - Give invoke_workflow to non-chat roles
  - Reuse the parent run_id for the child workflow
  - Return "stages ran": run_workflow returns (exit_code, FlowState) and the
    stage count is local to _run_adaptive/_run_linear. It is NOT reachable
    from the return value. Dropped from CT4 rather than plumbed.

Exit criteria (all binary):
  - [ ] ToolSpec registers without raising (schema compiles via
        fastjsonschema + passes validate_tool_schema_portability)
  - [ ] "invoke_workflow" in {s.name for s in registry.specs()} for a chat
        registry built with a non-None workflow_ctx
  - [ ] "invoke_workflow" NOT in the coder/planner/eval registries
  - [ ] handler with {"task": "x"} calls run_workflow_fn exactly once with
        run_id != parent_run_id and run_id.startswith(parent_run_id)
  - [ ] two successive calls produce run ids ending "-wf1" and "-wf2"
  - [ ] handler with {"task": "x", "mode": "repair"} -> error code
        "invalid_mode"
  - [ ] handler with {"task": "x", "roles": " , "} -> error code
        "invalid_roles"
  - [ ] run_workflow_fn raising RuntimeError -> ToolResult.error.code ==
        "workflow_error" and no exception escapes the handler
  - [ ] re-entrant dispatch -> error code "workflow_reentrant"
  - [ ] a 125-char parent run_id yields a child that still matches
        [A-Za-z0-9][A-Za-z0-9_.-]{0,127} (length <= 128)
  - [ ] RK6: run_workflow with deadline_mono already in the past runs ZERO
        stages and returns non-zero
  - [ ] RK6: a deadline that expires after stage 1 stops the pipeline before
        stage 2; the recorded stage count is 1, not the full role list
  - [ ] RK6: on expiry, flow_state.json exists, status == "FAILED", and
        last_transition_reason contains "deadline exceeded"
  - [ ] RK6: deadline_mono=None (every existing caller) runs the full
        pipeline unchanged — existing workflow tests pass untouched
  - [ ] RK6: the tool's result carries timed_out=True on expiry and
        timed_out=False on a normal finish
  - [ ] pytest tests/test_invoke_workflow_tool.py tests/test_workflow_deadline.py passes

Kill-checks (each must be demonstrated to FAIL the named test):
  - remove invoke_workflow registration -> test_invoke_workflow_registered
  - reuse parent run_id for the child -> test_child_run_id_is_distinct
  - drop the reentrancy guard -> test_reentrant_call_is_refused
  - let run_workflow exceptions propagate -> test_workflow_error_is_contained
  - remove the _run_stage deadline guard -> test_deadline_stops_between_stages
  - make the deadline raise instead of writing terminal state ->
    test_deadline_writes_terminal_flow_state
  - concatenate the child run_id without truncating ->
    test_long_parent_run_id_stays_valid

Test class: C1 (composition root: _build_run_tool_registry), with C0p on
the roles/mode parsing.
Oracle: ranked — (1) structured ToolResult fields, (2) the run_id actually
passed to the injected run_workflow_fn, (3) registry membership.
Fixture honesty: run_workflow_fn is a REAL callable with run_workflow's
true keyword-only signature that records its kwargs — not a MagicMock.
```

### S5: ACRR Proxy in fa stats  ✅ DONE 2026-08-27 (incl. RK8 allowlist + T14)

**Traces-to:** G3, GAP5, CT6
**Depends-on:** S4b (child run_id must be distinct before per-run ratios mean
anything — see the packet body; the earlier "none" was wrong)
**Target liveness:** L0→L3

```
EDIT PACKET E5 / S5
What: Add an ACRR efficiency proxy to global_history and fa stats.
AS-IS: fa stats shows tool usage, tokens, timing — no efficiency metric.
TO-BE: each run records files_read / files_changed; fa stats renders ACRR.

DEPENDS-ON: S4b's child-run_id fix. NOT independent, despite the earlier
  "Depends-on: none". ACRR is computed per global_history row, and until
  invoke_workflow stops reusing the parent run_id, a chat row and its
  nested workflow row overwrite each other (CT4 RUN IDENTITY). Computing an
  efficiency ratio over a row that may describe a different execution is
  worse than not computing one.

CORRECTED ASSUMPTION — read this before touching _cmd_stats:
  The original packet said "Compute files_read from event_log ... in
  _cmd_stats". That renderer CANNOT do this, and its NAME HAS CHANGED.
  CORRECTED 2026-08-27 (S5 preflight): S10b.3 split _cmd_stats into three
  independent renderers. The global-history one is _cmd_stats_global_history
  (cli.py:2805) and its per-run print loop is at cli.py:2871. Its only data
  source is GlobalHistoryStore.read_all() (verified by execution: zero
  EventLog references in that function), and per-path detail is not
  projected into that table.
  The counting therefore happens at EXPORT time, where the events are
  already in hand:
    _extract_telemetry_from_log (global_history.py:248-313) already
    iterates every event and already branches on ev.kind == "tool_call".
    tool_call content carries {"params": {...}} including "path"
    (state.py:751-757). Add distinct-path counting to that existing loop.

Exact code mechanism:
  1. NEW src/fa/inner_loop/acrr.py:
     def compute_acrr_proxy(files_read: int, files_changed: int) -> float | None
     Per CT6: returns None when files_changed == 0; ValueError on negatives.
  2. src/fa/inner_loop/global_history.py:
     a. _extract_telemetry_from_log: inside the existing tool_call branch,
        collect distinct paths into two sets —
          read set:    tool_name == "fs_read_file"
          changed set: tool_name in {"fs_write_file", "fs_edit_file"}
        reading content["params"]["path"] when it is a str. Return
        "files_read": len(read_set), "files_changed": len(changed_set).
        (These names mirror SessionState.add_read/add_write, state.py:557/638,
        which track the same two tool groups for the transaction read-set.)
     b. GlobalRunRow: add files_read: int = 0, files_changed: int = 0,
        acrr_proxy: float | None = None. Defaults keep the dataclass
        backward-compatible with existing constructors.
     c. build_export_row: populate all three.
     d. _init_schema MIGRATION — REQUIRED, see below.
  3. src/fa/cli.py:_cmd_stats_global_history: render one additional line per
     run from the row's own columns, in the per-run loop at cli.py:2871. No
     event log access. NOTE the stream contract that function documents: the
     human report goes to STDERR and only --output json goes to stdout, so the
     new line must print to stderr like its neighbours.

MIGRATION (the original "ALTER TABLE or new column" was a guess-point):
  _init_schema uses CREATE TABLE IF NOT EXISTS (global_history.py:139), so an
  already-deployed DB will NOT gain the columns and every insert will fail
  with "table runs has no column named files_read". Implement explicitly:
    after the CREATE TABLE, read PRAGMA table_info(runs); for each of the
    three new columns not present, execute
      ALTER TABLE runs ADD COLUMN <name> <type> DEFAULT <default>
    Idempotent, additive, safe to run on every open.
  ROLLBACK: reverting the code leaves the three columns in place. Older
  readers select by name and ignore them, so rollback is safe and needs no
  down-migration. State this in Risks rather than implying "no migration".

Allowed files:
  src/fa/inner_loop/acrr.py (NEW)
  src/fa/inner_loop/global_history.py (EDIT — telemetry, row, schema)
  src/fa/cli.py (EDIT — _cmd_stats_global_history rendering + RK8 role
    validation in _cmd_workflow; no other behaviour)
  tests/test_acrr.py (NEW)
  tests/test_workflow_role_allowlist.py (NEW — RK8)

Do:
  1. compute_acrr_proxy per CT6.
  2. Distinct-path counting in _extract_telemetry_from_log.
  3. Three columns + the PRAGMA-guarded migration.
  4. Stats line.
  5. C0 tests: (5,5)->1.0 ; (20,2)->10.0 ; (10,0)->None ; (0,0)->None ;
     (-1,1) raises ValueError.
  6. C1 test: an EventLog containing two fs_read_file calls on the SAME path
     plus one on another, and one fs_write_file, exports files_read == 2
     (distinct, not 3) and files_changed == 1.
  7. C1 migration test: create a DB with the pre-S5 schema, open it with the
     new code, assert the three columns exist and an insert succeeds.
  8. RK8 — role allowlist (see the dedicated section below).
  9. T14 (moved here from S4b): a chat run whose nested workflow actually
     executes produces TWO global_history rows with different roles. S4b
     injected a fake run_workflow and so never wrote a real row; ACRR is a
     per-row quantity, so the two-row shape must be proven where it matters.

Do-not:
  - Implement the full E3 cost model C(pi) (defer to v2)
  - Read event logs from _cmd_stats
  - Change existing stats output format (additive lines only)
  - Count non-distinct paths
  - Widen the RK8 allowlist to silence a failing test — a role that legitimately
    belongs in a pipeline is added by editing the named constant on purpose
  - Validate roles anywhere except the CLI boundary (stages run in separate
    call frames with their own registries; a thread-local guard cannot see them)

Exit criteria (all binary):
  - [ ] compute_acrr_proxy(5, 5) == 1.0
  - [ ] compute_acrr_proxy(20, 2) == 10.0
  - [ ] compute_acrr_proxy(10, 0) is None
  - [ ] compute_acrr_proxy(0, 0) is None
  - [ ] compute_acrr_proxy(-1, 1) raises ValueError
  - [ ] distinct-path test: 3 read calls / 2 unique paths -> files_read == 2
  - [ ] a pre-S5 DB gains all three columns on open, and insert succeeds
  - [ ] fa stats prints "ACRR proxy: X.XX (files_read=N, files_changed=M)"
        and "ACRR proxy: n/a (no files changed)" when files_changed == 0
  - [ ] fa workflow --roles planner,chat,eval exits 2 with an "invalid role"
        message naming chat and listing the permitted roles
  - [ ] fa workflow --roles bogus_role exits 2 the same way
  - [ ] fa workflow --roles planner,coder,eval is UNCHANGED (exit 0 path)
  - [ ] a chat run + nested workflow yields 2 global_history rows (T14)
  - [ ] C0 + C1 tests pass

Kill-checks:
  - remove the compute_acrr_proxy call from the stats renderer ->
    test_acrr_in_stats fails
  - revert the zero case to max(files_changed, 1) -> test_acrr_zero_is_none
    fails
  - delete the allowlist membership check -> test_rk8_chat_rejected_as_stage_role
    fails
  - add "chat" to the allowlist constant -> the same test fails (proves the
    test binds to the ROLE, not merely to the presence of a check)
  - drop the PRAGMA migration -> test_pre_s5_db_migrates fails
  - count non-distinct paths -> test_files_read_is_distinct fails

Test class: C0 (pure) + C1 (export path, real EventLog, real sqlite file)
Oracle: exact float / None for C0; exact column values for C1
```

#### RK8 — role allowlist (folded into S5, operator-approved 2026-08-27)

VERIFIED LIVE 2026-08-27 by executing build_parser():
  `fa workflow --roles planner,chat,eval`, `--roles chat`, `--roles bogus_role`
  and `--roles researcher,coder` ALL parse and run today. cli.py:1141 splits
  --roles on commas with no membership check of any kind, and
  status_for_role() silently returns 'CODING' for chat, researcher and
  bogus_role alike. Nothing downstream ever rejects them.

WHY THIS IS THE RIGHT SHAPE. Two candidate fixes were considered and one
rejected. A thread-local re-entrancy guard CANNOT work: workflow stages run
in separate call frames, each building its own registry, so the guard set by
an outer chat run is not visible at the point a `chat` STAGE would construct
its own invoke_workflow tool. The defect is therefore an INPUT-VALIDATION
defect and belongs at the input boundary — the CLI — which is also the only
place where the operator's intent is still expressed as text.

An allowlist rather than a `chat`-specific denial. A denylist answers "is this
the one role we already know is dangerous", which is false confidence: it
accepts every typo and every future role by default, exactly as bogus_role is
accepted today. The allowlist answers "is this one of the roles this pipeline
knows how to run". New roles WILL emerge; each then arrives as a deliberate
one-line edit to a named constant with a test, which is the behaviour we want.

MECHANISM:
  WORKFLOW_STAGE_ROLES: Final = frozenset({"planner", "coder", "eval"})
    Module-level in cli.py beside WORKFLOW_MODES, exported via __all__
    (FA-AUTHORING-V2-EXPORTS-COMPLETENESS applies to new public symbols).
    Derive nothing from PROFILES_RAW: the allowlist is a POLICY statement
    about pipeline stages, not a restatement of which profiles exist. chat is
    a real profile and must still be absent here.
  Validation goes in _cmd_workflow immediately after the --roles split at
  cli.py:1141, mirroring the existing --mode block at cli.py:1146-1153 in
  both style and exit code:
    unknown = [r for r in roles if r not in WORKFLOW_STAGE_ROLES]
    if unknown: print an error naming the offending role(s) AND the permitted
    set, then return 2.
  Order matters: validate BEFORE any run_id allocation or artifact write, so a
  rejected invocation leaves no state behind.

WHY chat is excluded even though it is a valid profile: a chat stage would
construct its own invoke_workflow tool and could recurse into a fresh
workflow, and the S4b re-entrancy guard cannot observe it across call frames.
Excluding chat at the boundary is what makes that guard's blind spot
unreachable.

SCOPE FENCE: this is CLI input validation only. Do not touch status_for_role
(its 'CODING' default is reached by other callers and is out of scope), the
controller, or the stage loop.

### S7-S9: Deterministic routing + full E3 cost model — SEE ADDENDUM

**Added 2026-08-27 (operator-directed).** Three new slices are specified in a
companion plan: `PLAN-ADDENDUM-deterministic-routing-S7-S9.md`.

- **S7** — deterministic escalation: a pre-run capability gate (chat loses write
  tools when the estimator confidently says `workflow_linear`) plus a mid-run
  scope tripwire. Driven by a measurement taken this session: the estimator is
  60% accurate overall, ALL errors are under-scopes, and accuracy by confidence
  is 0.8 -> 100%, 0.6 -> 60%, 0.3 -> 33%. The gate therefore binds only the 0.8
  bucket.
- **S8** — the full E3 cost model (Eq. 1) and real ACRR (Eq. 3) against a
  self-referential floor, replacing the S5 file-ratio proxy, which is renamed
  `read_amplification` because it was never the paper's ACRR.
- **S9** — live verification sheet with pasted real output.

**S6 is re-sequenced to run LAST** (S7 -> S8 -> S9 -> S6) so ADR-16 records
settled decisions once rather than being amended twice.

### S6: ADR-16 + Documentation

**Traces-to:** G4, GAP6, CT7
**Depends-on:** S1-S5 (captures decisions from implementation)
**Target liveness:** L0→L3

**Extra task (added 2026-08-26):** Revise CHAT_SYSTEM_PROMPT content and chat role tool set based on integration testing from S3–S5. Current S2 versions are minimal scaffolds.

```
EDIT PACKET E6 / S6
What: Write ADR-16 and update documentation.

Exact code mechanism:
  0. CORRECTED 2026-08-27 (preflight): ADR-16 is NOT new. It already exists
     on disk at 276 lines with status "proposed", committed in the base
     revision 00c1c4a. S6 therefore EDITS it: flip Status proposed ->
     accepted, and reconcile its recorded decisions with what S1-S5 actually
     shipped (the operator confirmed ADR-16 is not immutable and its records
     may be changed to match the agreed design). Read the file before
     writing; do not recreate it from the plan's summary.
  1. EDIT knowledge/adr/ADR-16-complexity-aware-execution.md
  2. EDIT knowledge/llms.txt — add ADR-16 routing
  3. EDIT knowledge/instructions/02-operations.md — chat role section
  4. EDIT AGENTS.md — add chat role to role descriptions

Allowed files:
  knowledge/adr/ADR-16-complexity-aware-execution.md (EDIT — ALREADY EXISTS, 276 lines, status: proposed)
  knowledge/llms.txt (EDIT)
  knowledge/instructions/02-operations.md (EDIT)
  AGENTS.md (EDIT)

Do:
  1. Write ADR-16 following ADR-template.md with:
     - Status: Accepted
     - Context: E3 paper, CaH survey, FA's dual-mode problem
     - Decision: Chat role + deterministic estimator + invoke_workflow tool + ACRR
     - Consequences: new role surface, estimator is hardcoded (v1), ACRR is proxy
     - Prior Art: E3, AdaptOrch, TRACE-Router, Claude Code ultracode
  2. Update llms.txt BY-DEMAND INDEX with ADR-16
  3. Add chat role section to operations manual
  4. Add chat role to AGENTS.md role descriptions
  5. CARRIED FORWARD FROM S8 (operator instruction 2026-08-27). ADR-16 MUST
     record the self-referential-floor caveat VERBATIM, in the Consequences
     section, in these words:

       "The floor is self-referential: it derives from the run's own
       change-set, so a run that changed the WRONG files still scores well.
       ACRR measures redundancy, never correctness."

     Why this is mandatory and not editorial: cost_floor is computed from the
     paths the run itself modified, so a confidently-wrong run defines its own
     cheap baseline and reports a flattering ACRR. Anyone reading the
     calibration table without this sentence will over-trust it as a quality
     metric. It is an efficiency metric that presupposes success, which is
     also why `fa stats --calibration` shows successful runs only.

     Also record, from S8 as shipped:
     - the fitted weights (alpha=1.0, beta=0.000415, gamma=0.1, delta=1.5) WITH
       the derivation: median src/*.py = 7234 B ~= 1808 tokens, beta set so a
       median file's token cost is half its file cost; paper defaults measured
       to put the file axis at 0.43-2.17% of C and were rejected;
     - that the floor EXCLUDES latency, per E3 LLM-Case 7.7, to stay
       deterministic;
     - that ACRR is recorded for every run and filtered at display (Q22),
       quoting the reason: a cheap failure is not an efficiency;
     - the E3 7.2 monotonicity caveat: the authors concede it is "partly
       mechanical", so present it as a descriptive signature, not a scaling law.

Do-not:
  - Change any existing ADR text
  - Remove deferred items from operator memo

Exit criteria:
  - [ ] ADR-16 exists and follows template
  - [ ] llms.txt references ADR-16
  - [ ] 02-operations.md has chat role section
  - [ ] AGENTS.md mentions chat role
  - [ ] No broken doc links
  - [ ] CHAT_SYSTEM_PROMPT revised based on S3-S5 integration findings
  - [ ] Chat tool set revised based on S3-S5 integration findings
  - [ ] ADR-16 contains the self-referential-floor caveat VERBATIM (grep for
        "ACRR measures redundancy, never correctness")
  - [ ] ADR-16 records the fitted weights with their derivation
  - [ ] ADR-16 states the floor excludes latency and why

Kill-check: N/A (documentation)
Test class: static (doc link check)
```

---

## 6. Verification Plan

| T# | Class | Claim | Oracle | Kill-check | S# |
|---|---|---|---|---|---|
| T1 | C0 | estimate_scope returns correct OperatingPoint for 15+ fixtures | Exact field match | N/A (pure) | S1 |
| T2 | C0p | estimate_scope boundary: empty, very long, non-English, all-keywords | Exception/value assertions | N/A (pure) | S1 |
| T3 | C1 | Chat role run with L1 task logs scope_estimate event | event_log kind+fields | remove estimate_scope call | S3 |
| T4 | C1 | Chat role run with L2 task → d̂=2 in scope_estimate | event_log fields | remove estimate_scope call | S3 |
| T5 | C1 | Chat role dispatches with CHAT_SYSTEM_PROMPT | System message content | remove "chat" from _ROLE_PROMPTS | S2 |
| T6 | C1 | Ambiguous task → ĉ<0.5 in scope_estimate | confidence field | N/A (data-driven) | S3 |
| T7 | C1 | invoke_workflow tool registered in chat registry | Tool name in registry | remove from registry | S4b |
| T8 | C1 | invoke_workflow calls run_workflow (workflow_controller) with an injected run_stage_fn | recorded kwargs on a real-signature fake | remove delegation | S4b |
| T13 | C1 | invoke_workflow allocates a CHILD run_id distinct from the parent | recorded run_id kwarg; startswith(parent) and != parent | reuse parent run_id | S4b |
| T14 | C1 | a chat run and its nested workflow produce TWO global_history rows | row count == 2, roles differ | reuse parent run_id | **S5** (moved 2026-08-27: S4b injected a fake run_workflow, so no real rows were ever written; this is an S5 concern because ACRR is per-row) |
| T15 | C0p | roles/mode parsing rejects empty roles and non-enum modes | error codes invalid_roles / invalid_mode | accept any string | S4b |
| T16 | C1 | pre-S5 global_history DB gains files_read/files_changed/acrr_proxy on open | PRAGMA table_info + successful insert | drop the migration | S5 |
| T17 | C1 | RK6: a deadline expiring after stage 1 stops the pipeline before stage 2 | recorded stage count == 1 | remove the _run_stage guard | S4b |
| T18 | C1 | RK6: on expiry flow_state.json is well-formed, status FAILED, reason contains "deadline exceeded" | parsed FlowState fields | make the deadline raise | S4b |
| T19 | C1 | RK6: deadline_mono=None leaves every existing caller byte-identical | existing workflow suite green | default to a finite deadline | S4b |
| T20 | C0p | a 125-char parent run_id yields a child <= 128 chars matching the run_id grammar | re.fullmatch against the real pattern | concatenate without truncating | S4b |
| T9 | C1 | models.yaml without chat → coder fallback | Role resolution | N/A (existing) | S2 |
| T10 | C1 | fa stats shows ACRR proxy | Output contains "ACRR" | remove ACRR computation | S5 |
| T11 | C0 | compute_acrr_proxy division-by-zero protected | Exact float | N/A (pure) | S5 |
| T12 | C1 | Existing workflow tests still pass after refactor | pytest exit 0 | N/A (regression) | S4 |

### LIVE-PATH PROOF

```
root: drive_session (real composition root)
matrix: M1 (chat declared), M2 (chat not declared)
paths-covered: P1-P8 (8/8)
producer targets: estimate_scope, CHAT_SYSTEM_PROMPT, build_chat_registry,
                  invoke_workflow, run_workflow, compute_acrr_proxy
pyramid: A (all deterministic)
```

---

## 7. Risks, Rollback, Open Questions

### Risks

| RK# | Risk | Mitigation | Detection |
|---|---|---|---|
| RK1 | Estimator keywords too narrow — misses real L3 tasks | Start optimistic (E3 principle); expand captures misses | Track escalation rate in ACRR |
| RK2 | invoke_workflow breaks session context sharing | Share session_context/run_context/session_db explicitly | C1 test with real session |
| RK3 | ~~_run_workflow_internal refactor breaks existing tests~~ **CLOSED in S4a** — the extraction shipped as `run_workflow` in workflow_controller.py with the full suite green | Regression gate: all existing workflow tests must pass | pytest test_cli_ergonomics |
| RK4 | ACRR proxy too coarse (file ratio misses token waste) | v1 is acknowledged proxy; full cost model in v2 | Research note: document limitation |
| RK5 | ~~Chat role weakens security (bash access)~~ **RETIRED 2026-08-26** | The stated mitigation was never implemented and the premise is now reversed. `_build_run_hook_registry` takes no `role` (cli.py:1389), `IntentGuard(repo_root, draft_store)` is role-blind (cli.py:1471), and `intent_guard.py` contains zero `role` references — chat's bash was never restricted to READ_ONLY. Since chat also now holds write tools by decision Q1, "chat cannot write files" is not a property to defend. | n/a — see RK6 |
| RK6 | A nested workflow runs unbounded inside one chat tool call | **RESOLVED 2026-08-26 — option (a), in scope for S4b.** Cooperative wall-clock deadline: `workflow_timeout_seconds` (default 1800) → `run_workflow(deadline_mono=...)` → checked at the top of `_run_stage`, the single choke point for all seven dispatch sites. On expiry the controller writes a terminal `FAILED` FlowState with reason "deadline exceeded", exports its global_history row, and returns non-zero — it does not raise. Full mechanism and rejected alternatives (SIGALRM, subprocess kill) in the S4b packet under "RK6 DESIGN". Known limit, stated not hidden: a stage already in flight is not interrupted, so the worst case is deadline + one stage. | `timed_out=True` in the tool result; `last_transition_reason` contains "deadline exceeded" |
| RK7 | Cost budgets do not compose across the escalation boundary | **ACCEPTED AS-IS 2026-08-26 (operator decision).** `CostGuardian(budget_usd=limits.cost_budget_usd)` is constructed per run (cli.py:1029, cli.py:1476), so a chat session with budget B that escalates can spend B (chat) + B × stages. Deliberately not fixed in S4b: the budget is a per-run guardrail, not a global ledger, and RK6's deadline now bounds the number of stages that can run. Revisit if observed spend justifies threading a remaining-budget value into the child. **This is a known, accepted multiplier — not an oversight.** | `fa stats` cost totals exceed the configured per-run budget |
| RK8 | `chat` is accepted as a workflow STAGE role, bypassing the re-entrancy guard | **FOLDED INTO S5 (operator decision 2026-08-27): role allowlist.** An allowlist is the fitting design precisely because new roles may emerge later — a closed, named set makes each addition a deliberate edit rather than an accident. Mechanism in the S5 packet under "RK8 — role allowlist". Original analysis: `_cmd_workflow` splits `--roles` from a raw string with no allowlist (cli.py:1136), so `fa workflow --roles planner,chat,eval` runs a chat stage that could itself call `invoke_workflow`. The thread-local guard cannot see it because each stage runs via `run_stage_fn` → `_cmd_run` in a separate call frame with its own registry. Mitigation: validate `--roles` against the known pipeline roles in `_cmd_workflow`. Small and self-contained, but it is a CLI-validation change, not part of the tool slice. | a chat stage appears in a workflow run's stage list |

### Rollback

- Each slice is independently revertable (separate commits)
- S5 DOES require a migration: `_init_schema` uses CREATE TABLE IF NOT EXISTS (global_history.py:139), so existing DBs need PRAGMA-guarded ALTER TABLE for the three new columns. Rollback is safe without a down-migration (name-based reads ignore extra columns).
- Chat role is optional in models.yaml — removing it reverts to pre-existing behavior
- invoke_workflow tool only appears in chat registry — removing it has no effect on other roles

### Open Questions

| Q# | Question | Blocking? | Default |
|---|---|---|---|
| Q1 | Should chat support --resume for multi-turn? | No | YES — reuse session infrastructure |
| Q2 | Should estimator keywords be configurable? | No | NO — hardcoded for v1 |
| Q3 | Should ACRR be per-file or aggregate? | No | Aggregate per run (simpler) |

---

## 8. Research-Note Disposition

| RN# | Note Item | Verdict | Anchor |
|---|---|---|---|
| RN1 | E3: "Estimate ≤1 cheap probe, no LLM call" | **Accept** | CT1, S1 — estimator is pure Python |
| RN2 | E3: "Optimistic estimator, expand as safety net" | **Accept** | CT4 — invoke_workflow is the expand stage |
| RN3 | E3: "ACRR = (C_actual - C_min) / C_min" | **Rewrite** | CT6 — use file ratio proxy (C_min not computable) |
| RN4 | CaH: "Topology complexity ∝ 1/harness-state formality" | **Accept** | Plan scope — no parallel agents, simple chain |
| RN5 | CaH: "Code artifacts as coordination surface" | **Accept** | CT4 — invoke_workflow returns structured result |
| RN6 | AdaptOrch: "DAG-based topology routing" | **Defer** | Non-goal for v1 (substrate first) |
| RN7 | TRACE-Router: "Contextual bandit for task routing" | **Defer** | Non-goal for v1 (no training data) |
| RN8 | Claude Code: "ultracode auto-escalation" | **Accept** | G1 — chat role auto-routes to workflow |
| RN9 | E3: "Redundancy worst on simplest tasks" | **Accept** | G3 — ACRR tracking measures this |
| RN10 | DAAO: "VAE difficulty estimator" | **Reject** | Overkill for single-user; deterministic rules suffice |

---

## 9. Definition of Done

**STATE:**
- 4 roles in _ROLE_PROMPTS (planner, coder, eval, chat) — L3
- estimate_scope() callable, tested, integrated — L3
- invoke_workflow tool registered in chat registry — L3
- run_workflow (workflow_controller.py) callable from both CLI and tool — L3
- ACRR proxy in fa stats output and global_history.db (files_read, files_changed, acrr_proxy columns) — L3
- ADR-16 accepted and referenced — L3

**ARTIFACTS:**
- A1-A16 all exist per inventory above

**CONTRACTS:**
- CT1-CT7 all VERIFIED (kill-checks pass)

**Plan is DONE when:**
- All S1-S6 slices complete with after-edit gates green
- All T1-T20 tests pass
- `just check` passes (lint + mypy + tests)
- `fa run -r chat "fix typo in README"` works end-to-end
- `fa run -r chat "refactor workflow controller"` escalates to workflow, and the escalation produces a SECOND global_history row under a child run_id
- `fa stats` shows ACRR proxy for completed runs
- ADR-16 is committed and referenced in llms.txt
- No blocking Q# remains

---

## 10. Anti-Theater + READY Gate

- [ ] Every referenced symbol verified via preflight or marked NEW ✓
- [ ] Every G# maps to ≥1 CT# and ≥1 S# and ≥1 T# ✓
- [ ] Every signal CT# has BOTH producer and consumer ✓
- [ ] Every kill-check targets the PRODUCER ✓
- [ ] Path inventory has no uncovered path without explicit non-goal ✓
- [ ] Matrix has ≥1 covering step per row ✓
- [ ] Fixtures/types are honest (real types, not loosened mocks) ✓
- [ ] No vague verbs without mechanism ✓
- [x] Security: chat role's boundary is the scope estimator, not tool withholding. Chat HAS write/edit tools (Q1, shipped a638253). The old gate line asserted the opposite and is retired; RK5 explains why it was never enforced anyway.
- [x] All ID references resolve — CT5 corrected 2026-08-26: it named `_run_workflow_internal`, which has no matches in src/. The real symbol is `run_workflow` in workflow_controller.py.
- [ ] Blocking Q# set is EMPTY ✓
- [ ] Minimal-mechanism check: no new dependencies, no LLM calls for classification ✓
- [ ] Research notes fully dispositioned ✓

**Status: S1–S4a SHIPPED. S4b/S5/S6 revised 2026-08-26 after an adversarial
review (`/home/user/plan-review-S4b-S6-2026-08-26.md`), then re-audited
against the code a second time (`/home/user/plan-edit-audit-2026-08-26.md`),
which found four defects in the first revision and corrected them.

Three original blocking assumptions were false and are fixed in-place: the
shared-run_id design (CT4), the `_run_workflow_internal` symbol (CT5), and
S5's event-log-in-`_cmd_stats` data source.

Operator decisions 2026-08-26: **RK6 (nested-pipeline timeout) is RESOLVED
and in scope for S4b** — cooperative deadline checked in `_run_stage`.
**RK7 (cost-budget composition) is ACCEPTED AS-IS.** RK8 (chat as a workflow
stage role) is newly recorded and OUT OF SCOPE.

S4b is READY to implement. No blocking Q# remains.**
