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
  _run_workflow_internal():    L0 (absent; _cmd_workflow is CLI-only)
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
`invoke_workflow` tool → `_run_workflow_internal()` → workflow pipeline
runs in shared session.

**PROOF SKETCH:** C1 test on `estimate_scope()` with fixture tasks; C1 test
on `invoke_workflow` tool calling `_run_workflow_internal()`; C2 test on
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
- **GAP4:** `_cmd_workflow` is not internally callable → refactor to `_run_workflow_internal()`
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
PAYLOAD: Minimal system prompt — pair programming partner, scope-aware,
         knows about invoke_workflow tool, uses fs_search and fs_read_file
         for codebase exploration, does NOT have write/edit tools directly
         for L3 tasks
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
OUTPUTS: ToolRegistry with: fs_read_file, fs_search, fs_blackboard_query,
         fs_run_bash (stateless, read-only exploration), fs_reach,
         invoke_workflow (added in S4)
SIDE EFFECTS: none
INVARIANTS:
  - Chat profile defined in PROFILES_RAW with tools list
  - build_chat_registry delegates to build_registry_for_role("chat", ...)
  - Does NOT include fs_write_file, fs_edit_file (chat cannot mutate directly for L3)
  - DOES include fs_run_bash (stateless bash for exploration only)
  - DOES include invoke_workflow (added in S4, not in profile yet)
  - Pattern mirrors build_planner_registry (tools/__init__.py:168)
KILL-CHECK: removing invoke_workflow from chat registry → T7 fails
```

### CT4: invoke_workflow Tool

```
CT4: invoke_workflow TYPE:function (tool)
PRODUCER: NEW src/fa/inner_loop/tools/workflow_tool.py:build_invoke_workflow_tool
CONSUMER: chat role LLM calls it when scope=3
INPUTS: {task: str, mode: str="linear", roles: str="planner,coder,eval",
         max_repairs: int=2, max_replans: int=1}
OUTPUTS: ToolResult with workflow terminal summary (verdict, route, stages ran)
SIDE EFFECTS: calls _run_workflow_internal() which runs the workflow pipeline
              in the shared session context
INVARIANTS:
  - Shares session context (same session_id, run_context, session_db)
  - Does NOT create a new session
  - Returns structured result, not raw exit code
  - mode ∈ {"linear", "adaptive"}
KILL-CHECK: removing invoke_workflow from chat registry → T7 fails
```

### CT5: _run_workflow_internal() Refactor

```
CT5: _run_workflow_internal() TYPE:function
PRODUCER: src/fa/cli.py:_run_workflow_internal (refactored from _cmd_workflow)
ROOTS/CALLERS: _cmd_workflow (CLI wrapper), invoke_workflow tool
INPUTS: roles, task, mode, max_repairs, max_replans, run_id, workspace,
        config, session_context, run_context, session_db
OUTPUTS: tuple[int, FlowState | None] (exit_code, terminal_state)
SIDE EFFECTS: writes flow_state.json, eval_report.json, events.jsonl
INVARIANTS:
  - No argparse dependency (pure structured params)
  - _cmd_workflow becomes thin wrapper: parse args → call _run_workflow_internal
  - Existing behavior byte-identical (no test changes for existing workflow tests)
KILL-CHECK: if _run_workflow_internal is bypassed by _cmd_workflow → T8 fails
```

### CT6: ACRR Proxy Metric

```
CT6: compute_acrr_proxy() TYPE:function/module
PRODUCER: NEW src/fa/inner_loop/acrr.py:compute_acrr_proxy
CONSUMER: fa stats (per-run), global_history.db (cross-run projection)
INPUTS: files_read: int, files_changed: int
OUTPUTS: float (ACRR proxy = files_read / max(files_changed, 1))
SIDE EFFECTS: none (pure function)
INVARIANTS:
  - ACRR = 1.0 when files_read == files_changed (optimal)
  - ACRR > 1.0 when files_read > files_changed (over-reading)
  - ACRR is never negative
  - Division by zero protected (max(files_changed, 1))
KILL-CHECK: removing ACRR from stats output → T10 fails
```

### CT7: ADR-16

```
CT7: ADR-16 TYPE:document
PRODUCER: NEW knowledge/adr/ADR-16-complexity-aware-execution.md
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
| A5 | `src/fa/cli.py` — _run_workflow_internal, _build_role_registry, _cmd_run | EDIT | S4 |
| A6 | `src/fa/inner_loop/acrr.py` | ADD | S5 |
| A7 | `src/fa/cli.py` — _cmd_stats | EDIT | S5 |
| A8 | `src/fa/inner_loop/global_history.py` — schema extension | EDIT | S5 |
| A9 | `knowledge/adr/ADR-16-complexity-aware-execution.md` | ADD | S6 |
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
  - Give chat role fs_write_file or fs_edit_file
  - Give chat role fs_spawn_subagent
  - Make chat role mandatory in models.yaml (optional, falls back to coder)
  - Build registry manually in tools/__init__.py (use profiles.py pattern)

Exit criteria:
  - [ ] "chat" in _ROLE_PROMPTS → True
  - [ ] "chat" in PROFILES_RAW → True
  - [ ] build_chat_registry returns registry with fs_search, fs_read_file, fs_run_bash
  - [ ] build_chat_registry does NOT include fs_write_file, fs_edit_file
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

### S4b: invoke_workflow Tool

**Traces-to:** G1, GAP3, CT4
**Depends-on:** S4a (run_workflow exists in workflow_controller.py)
**Target liveness:** L0→L3

```
EDIT PACKET E4b / S4b
What: Add invoke_workflow tool that chat role uses to escalate L3 tasks.
AS-IS: chat role has no way to escalate to workflow pipeline
TO-BE: chat role calls invoke_workflow tool → run_workflow() in shared session

Exact code mechanism:
  1. NEW src/fa/inner_loop/tools/workflow_tool.py:
     - build_invoke_workflow_tool(run_workflow_fn, session_ctx_factory) → ToolSpec
     - Handler: parse params → call run_workflow() → return ToolResult
  2. src/fa/inner_loop/tools/__init__.py:
     - Register invoke_workflow in build_chat_registry
  3. src/fa/cli.py:
     - Wire run_workflow from workflow_controller into chat registry build

Allowed files:
  src/fa/inner_loop/tools/workflow_tool.py (NEW)
  src/fa/inner_loop/tools/__init__.py (EDIT)
  src/fa/cli.py (EDIT — wire tool into chat registry)
  tests/test_invoke_workflow_tool.py (NEW)

Do:
  1. Implement build_invoke_workflow_tool with input_schema:
     {task: str(required), mode: str(default="linear"),
      roles: str(default="planner,coder,eval"),
      max_repairs: int(default=2), max_replans: int(default=1)}
  2. Tool handler: validate params, call run_workflow(), format result
  3. Register in build_chat_registry
  4. Write C1 test: invoke_workflow tool with mock transport → returns summary
  5. Write C1 test: tool registered in chat registry

Do-not:
  - Change workflow controller logic
  - Add new workflow modes
  - Give invoke_workflow to non-chat roles

Exit criteria:
  - [ ] invoke_workflow tool schema is valid (ToolSpec.input_schema)
  - [ ] invoke_workflow registered in chat registry
  - [ ] invoke_workflow NOT in coder/planner/eval registries
  - [ ] Tool callable from ToolRegistry with mock run_workflow
  - [ ] C1 tests pass: pytest tests/test_invoke_workflow_tool.py -v

Kill-check:
  - removing invoke_workflow from chat registry → test_invoke_workflow_registered fails

Test class: C1
Oracle: tool execution result + registry membership
```

### S5: ACRR Proxy in fa stats

**Traces-to:** G3, GAP5, CT6
**Depends-on:** none (independent of S1-S4)
**Target liveness:** L0→L3

```
EDIT PACKET E5 / S5
What: Add ACRR proxy metric to fa stats and global_history.db.
AS-IS: fa stats shows tool usage, tokens, timing — no efficiency metric
TO-BE: fa stats shows files_read, files_changed, ACRR proxy per run

Exact code mechanism:
  1. NEW src/fa/inner_loop/acrr.py:
     - compute_acrr_proxy(files_read: int, files_changed: int) → float
  2. src/fa/cli.py:_cmd_stats:
     - Compute files_read from event_log (count distinct paths in fs_read_file events)
     - Compute files_changed from event_log (count distinct paths in fs_write_file/fs_edit_file events)
     - Compute ACRR proxy and display in stats output
  3. src/fa/inner_loop/global_history.py:
     - Add acrr_proxy column to global_history schema (additive, non-breaking)
     - Export acrr_proxy in export_session_to_global_history

Allowed files:
  src/fa/inner_loop/acrr.py (NEW)
  src/fa/cli.py (EDIT _cmd_stats)
  src/fa/inner_loop/global_history.py (EDIT schema + export)
  tests/test_acrr.py (NEW)

Do:
  1. Implement compute_acrr_proxy (pure function, 5 lines)
  2. Add files_read/files_changed extraction to _cmd_stats
  3. Add ACRR proxy line to stats console output
  4. Add acrr_proxy to global_history schema (ALTER TABLE or new column)
  5. Export acrr_proxy in global_history export function
  6. Write C0 test: compute_acrr_proxy(5, 5) == 1.0
  7. Write C0 test: compute_acrr_proxy(20, 2) == 10.0
  8. Write C0 test: compute_acrr_proxy(10, 0) == 10.0 (protected div-by-zero)
  9. Write C1 test: fa stats shows ACRR for a run with known file reads/changes

Do-not:
  - Implement full E3 cost model C(π) (defer to v2)
  - Add ACRR to workflow aggregate row (separate concern)
  - Change existing stats output format (additive only)

Exit criteria:
  - [ ] compute_acrr_proxy(5, 5) == 1.0
  - [ ] compute_acrr_proxy(20, 2) == 10.0
  - [ ] compute_acrr_proxy(10, 0) == 10.0
  - [ ] fa stats shows "ACRR proxy: X.XX (files_read=N, files_changed=M)"
  - [ ] global_history.db has acrr_proxy column after migration
  - [ ] C0 + C1 tests pass

Kill-check: removing compute_acrr_proxy call from _cmd_stats → test_acrr_in_stats fails

Test class: C0 + C1
Oracle: exact float value for C0; stats output contains ACRR line for C1
```

### S6: ADR-16 + Documentation

**Traces-to:** G4, GAP6, CT7
**Depends-on:** S1-S5 (captures decisions from implementation)
**Target liveness:** L0→L3

**Extra task (added 2026-08-26):** Revise CHAT_SYSTEM_PROMPT content and chat role tool set based on integration testing from S3–S5. Current S2 versions are minimal scaffolds.

```
EDIT PACKET E6 / S6
What: Write ADR-16 and update documentation.

Exact code mechanism:
  1. NEW knowledge/adr/ADR-16-complexity-aware-execution.md
  2. EDIT knowledge/llms.txt — add ADR-16 routing
  3. EDIT knowledge/instructions/02-operations.md — chat role section
  4. EDIT AGENTS.md — add chat role to role descriptions

Allowed files:
  knowledge/adr/ADR-16-complexity-aware-execution.md (NEW)
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
| T7 | C1 | invoke_workflow tool registered in chat registry | Tool name in registry | remove from registry | S4 |
| T8 | C1 | invoke_workflow tool calls _run_workflow_internal | Mock verification | remove delegation | S4 |
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
                  invoke_workflow, _run_workflow_internal, compute_acrr_proxy
pyramid: A (all deterministic)
```

---

## 7. Risks, Rollback, Open Questions

### Risks

| RK# | Risk | Mitigation | Detection |
|---|---|---|---|
| RK1 | Estimator keywords too narrow — misses real L3 tasks | Start optimistic (E3 principle); expand captures misses | Track escalation rate in ACRR |
| RK2 | invoke_workflow breaks session context sharing | Share session_context/run_context/session_db explicitly | C1 test with real session |
| RK3 | _run_workflow_internal refactor breaks existing tests | Regression gate: all existing workflow tests must pass | pytest test_cli_ergonomics |
| RK4 | ACRR proxy too coarse (file ratio misses token waste) | v1 is acknowledged proxy; full cost model in v2 | Research note: document limitation |
| RK5 | Chat role weakens security (bash access) | IntentGuard restricts to READ_ONLY; no write tools | C3 test: chat cannot write files |

### Rollback

- Each slice is independently revertable (separate commits)
- No data migration (ACRR column is additive)
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
- _run_workflow_internal callable from both CLI and tool — L3
- ACRR proxy in fa stats output and global_history.db — L3
- ADR-16 accepted and referenced — L3

**ARTIFACTS:**
- A1-A16 all exist per inventory above

**CONTRACTS:**
- CT1-CT7 all VERIFIED (kill-checks pass)

**Plan is DONE when:**
- All S1-S6 slices complete with after-edit gates green
- All T1-T12 tests pass
- `just check` passes (lint + mypy + tests)
- `fa run -r chat "fix typo in README"` works end-to-end
- `fa run -r chat "refactor workflow controller"` escalates to workflow
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
- [ ] Security: chat role does NOT get write tools (C3) ✓
- [ ] All ID references resolve ✓
- [ ] Blocking Q# set is EMPTY ✓
- [ ] Minimal-mechanism check: no new dependencies, no LLM calls for classification ✓
- [ ] Research notes fully dispositioned ✓

**Status: DRAFT → promote to READY after operator review of this plan**
