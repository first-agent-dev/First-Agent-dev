# Inner Loop Hooks and Runtime: Middleware Pipeline Architecture

> Codemap ID: `Inner_Loop_Hooks_and_Runtime__Middleware_Pipeline_Architecture_20260608_092335`

The inner loop defines five lifecycle points: `BETWEEN_ROUNDS`, `BEFORE_LLM_CALL`, `AFTER_LLM_CALL`, `BEFORE_TOOL_EXEC`, `AFTER_TOOL_EXEC`. This codemap focuses on the three tool-execution points (`BETWEEN_ROUNDS`, `BEFORE_TOOL_EXEC`, `AFTER_TOOL_EXEC`); the LLM-call points are documented in ADR-8 §1. Core flow starts at `[1b]` `run_session` loop, dispatches through `[2a]` `HookRegistry`, validates with `[3b]` `SandboxHook`, and records via `[1g]` event log. Specialized guards include `[4c]` `LoopGuard` detection and `[5b]` blocker pattern matching.

---

## Component Inventory

| Component | Type | Attaches To | Purpose |
| --- | --- | --- | --- |
| `PauseGuard` | `GuardMiddleware` | `BETWEEN_ROUNDS` | Session-level pause gate (e.g. sentinel file) |
| `CapabilityGuard` | `GuardMiddleware` | `BEFORE_TOOL_EXEC` | Enforces tool permission tiers |
| `ApprovalHook` | `GuardMiddleware` | `BEFORE_TOOL_EXEC` | Write-approval stub (HITL deferred to v0.2) |
| `VerifierObserver` | `ObserverMiddleware` | `AFTER_TOOL_EXEC` | DSV contract verification checker |
| `AuthExpiredBlocker` | `BlockerMiddleware` | `AFTER_TOOL_EXEC` | Detects auth-expired patterns (observe-only by default) |

---

## Trace 1: Tool Call Execution Through Runtime Loop

**Core runtime in `src/fa/inner_loop/loop.py`** — orchestrates the full lifecycle from tool call to result recording through three hook dispatch points.

```text
run_session() - Tool Execution Loop <-- loop.py:48
├── Setup hook event sink <-- loop.py:66
├── for iteration, call in enumerate(calls) <-- 1a
│   ├── Check iteration limit <-- loop.py:71
│   ├── hooks.dispatch(BETWEEN_ROUNDS) <-- 1b
│   │   └── (PauseGuard, LoopGuard gate here)
│   ├── state.record_tool_call(call) <-- 1c
│   │   └── Emit tool_call event to events.jsonl <-- state.py:183
│   ├── hooks.dispatch(BEFORE_TOOL_EXEC) <-- 1d
│   │   └── (SandboxHook, CapabilityGuard gate)
│   ├── effective_call = payload.tool_call <-- 1d1
│   │   ├── if effective_call is None <-- 1d2
│   │   │   └── result = ToolResult.fail("invalid_payload", ...) <-- 1d2a
│   │   └── else registry.dispatch(effective_call) <-- 1e
│   │       ├── Validate params against schema <-- registry.py:173
│   │       └── Execute tool handler <-- registry.py:186
│   ├── payload.with_tool_result(result) <-- 1e1
│   ├── hooks.dispatch(AFTER_TOOL_EXEC) <-- 1f
│   │   ├── (AuditHook, LearningObserver record)
│   │   └── if PermissionError caught <-- 1f1
│   │       └── post_exec_denied = exc; record result then break <-- 1f1a
│   └── state.record_tool_result(...) + results.append(result) <-- 1g
│       └── Emit tool_result event to events.jsonl <-- state.py:193
└── Cleanup hook event sink <-- loop.py:142
```

| Location | Title | Description | File:Line |
| :--- | :--- | :--- | :--- |
| `1a` | Runtime loop iteration starts | Each tool call enters the loop with iteration tracking and limit enforcement | `loop.py:70` |
| `1b` | `BETWEEN_ROUNDS` hook dispatch | Session-level gates (`PauseGuard`, `LoopGuard`) fire before each iteration | `loop.py:74` |
| `1c` | Tool call recorded to audit log | Emits `tool_call` event to `events.jsonl` for replay surface | `loop.py:92` |
| `1d` | `BEFORE_TOOL_EXEC` hook dispatch | Guards (`SandboxHook`, `CapabilityGuard`) gate execution; can deny or modify params | `loop.py:94` |
| `1d1` | Effective call extraction | `payload.tool_call` is read after `BEFORE_TOOL_EXEC` guards complete | `loop.py:105` |
| `1d2` | Guard dropped `tool_call` | If a modifying guard sets `tool_call` to `None`, `effective_call` becomes `None` | `loop.py:107` |
| `1d2a` | Invalid payload failure | `ToolResult.fail("invalid_payload", ...)` when `effective_call is None` | `loop.py:108` |
| `1e` | Tool handler execution | Registry validates schema and invokes handler with potentially modified params | `loop.py:115` |
| `1e1` | Result attached to payload | `payload.with_tool_result(result)` runs for BOTH branches before `AFTER_TOOL_EXEC` | `loop.py:117` |
| `1f` | `AFTER_TOOL_EXEC` hook dispatch | Observers (`AuditHook`, `LearningObserver`, `VerifierObserver`) record outcomes | `loop.py:118` |
| `1f1` | Post-exec guard deny | If a guard denies at `AFTER_TOOL_EXEC`, the exception is caught and stored | `loop.py:120` |
| `1f1a` | Result recorded then break | The tool result is still recorded; a `run_stopped` row is emitted and the loop breaks | `loop.py:141` |
| `1g` | Tool result recorded to audit log | Paired `tool_result` event completes the audit trail per ADR-7 §10 | `loop.py:129` |

---

## Trace 2: HookRegistry Middleware Dispatch Chain

**Core registry in `src/fa/inner_loop/hooks/base.py`** — executes ordered middleware chain with first-deny short-circuit, one-mutation limit, and observer error swallowing.

```text
HookRegistry Middleware Dispatch Chain
├── dispatch(point, payload) entry <-- 2a
│   ├── while run_index < len(chain) <-- base.py:156
│   │   ├── GuardMiddleware path <-- base.py:158
│   │   │   ├── middleware.handle() <-- 2b
│   │   │   ├── decision.action == "deny" <-- base.py:172
│   │   │   │   └── raise PermissionError <-- 2c
│   │   │   ├── decision.action == "modify" <-- base.py:174
│   │   │   │   ├── mutated = True <-- base.py:179
│   │   │   │   ├── current = decision.payload <-- base.py:180
│   │   │   │   └── for replayed in chain[:run_index] <-- 2d
│   │   │   │       └── replayed.handle() (revalidate) <-- base.py:191
│   │   │   └── decision.action == "allow" <-- base.py:169
│   │   │       └── run_index += 1 <-- base.py:170
│   │   └── ObserverMiddleware path <-- base.py:210
│   │       ├── try: <-- base.py:211
│   │       │   └── middleware.observe() <-- 2e
│   │       └── except Exception: <-- base.py:222
│   │           └── _record(observer_error_swallowed) <-- 2f
│   └── _record(record, payload) <-- base.py:160
│       └── self._event_sink(record, payload) <-- 2g
└── return current (final payload) <-- base.py:241
```

| Location | Title | Description | File:Line |
| :--- | :--- | :--- | :--- |
| `2a` | Dispatch entry point | Runs all middleware registered for the given lifecycle point in order | `base.py:151` |
| `2b` | Guard middleware invocation | `GuardMiddleware` can return allow, deny, or modify decisions | `base.py:159` |
| `2c` | Deny short-circuits chain | First deny stops execution and propagates to runtime loop | `base.py:173` |
| `2d` | Mutation triggers revalidation | After `Decision.modify`, replay ONLY guards with `revalidates_after_modify=True` (e.g. `SandboxHook`); others do NOT re-run | `base.py:186` |
| `2d1` | One-mutation limit | Raises `RuntimeError` if a second guard returns `modify` in the same dispatch | `base.py:175` |
| `2d2` | Modify without payload | Raises `RuntimeError` if a guard returns `modify` but `decision.payload` is `None` | `base.py:177` |
| `2d3` | Mutation flag set | Sets `mutated = True` after accepting a `Decision.modify` payload; a second modify triggers the one-mutation limit above | `base.py:179` |
| `2e` | Observer middleware invocation | `ObserverMiddleware` runs read-only side effects | `base.py:212` |
| `2f` | Observer errors swallowed | Exceptions in observers logged but don't break tool execution | `base.py:228` |
| `2g` | Hook decision event emission | Each middleware step emits `hook_decision` row to `events.jsonl` | `base.py:248` |

---

## Trace 3: SandboxHook Workspace Containment Validation

**Built-in guard in `src/fa/inner_loop/hooks/builtin.py`** — enforces workspace boundaries for `fs.run_bash`, `fs.read_file`, `fs.write_file` with revalidation after param mutations.

```text
SandboxHook Workspace Containment Validation <-- builtin.py:86
├── handle() entry point <-- 3a
│   ├── Route by tool name
│   │   ├── fs.run_bash path <-- 3b
│   │   │   └── _handle_bash() <-- builtin.py:117
│   │   │       └── evaluate_bash() <-- 3c
│   │   │           ├── bash_gate classifier
│   │   │           ├── validators
│   │   │           └── path containment
│   │   └── fs.read_file/write_file path <-- builtin.py:113
│   │       └── _handle_path() <-- builtin.py:130
│   │           └── is_contained() <-- 3d
│   │               └── workspace boundary check
│   └── Return Decision (allow/deny) <-- builtin.py:115
└── Class attributes
    └── revalidates_after_modify=True <-- 3e
        └── Triggers replay in HookRegistry <-- base.py:186
            after Decision.modify
```

| Location | Title | Description | File:Line |
| :--- | :--- | :--- | :--- |
| `3a` | SandboxHook handle entry | Routes to bash gate or path containment check based on tool name | `builtin.py:106` |
| `3b` | Bash command routing | Three-layer bash gate evaluates command safety | `builtin.py:111` |
| `3c` | Bash gate evaluation | Classifier + validators + path containment for shell commands | `builtin.py:120` |
| `3d` | Path containment check | Validates `fs.read_file`/`fs.write_file` paths stay within workspace | `builtin.py:133` |
| `3e` | Revalidation flag set | Ensures sandbox re-runs after any `Decision.modify` mutation | `builtin.py:103` |

---

## Trace 4: LoopGuard Non-Progress Detection

**Specialized guard in `src/fa/inner_loop/hooks/loop_guard.py`** — detects identical call repeats and same-path thrash patterns across a sliding window to prevent infinite loops.

```text
LoopGuard Non-Progress Detection Flow
├── handle() entry point <-- 4a
│   ├── if BEFORE_TOOL_EXEC branch <-- loop_guard.py:190
│   │   └── _record() observation capture <-- loop_guard.py:191
│   │       └── append to _observations deque <-- 4b
│   └── if BETWEEN_ROUNDS branch <-- loop_guard.py:193
│       └── _scan() detector execution <-- 4c
│           ├── Detector 1: Identical calls <-- loop_guard.py:127 (detector code begins after the comment at `:126`)
│           │   ├── count by (tool, hash) <-- 4c
│           │   └── if count >= breaker <-- loop_guard.py:133
│           │       └── Decision.deny() <-- 4d
│           └── Detector 2: Path thrash <-- loop_guard.py:152
│               ├── count distinct hashes/path <-- 4e
│               └── if distinct >= breaker <-- loop_guard.py:159
│                   └── Decision.deny() <-- 4f
```

| Location | Title | Description | File:Line |
| :--- | :--- | :--- | :--- |
| `4a` | LoopGuard handle routing | Records at `BEFORE_TOOL_EXEC`, scans at `BETWEEN_ROUNDS` | `loop_guard.py:189` |
| `4b` | Observation recorded to window | Captures `tool_name`, `params_hash`, and `path_hint` for each call | `loop_guard.py:118` |
| `4c` | Detector 1: Identical call repeat | Counts same (`tool_name`, `params_hash`) signatures in window | `loop_guard.py:131` |
| `4d` | Circuit breaker denial | Denies when identical calls exceed threshold (default 10) | `loop_guard.py:133` |
| `4e` | Detector 2: Same-path thrash | Counts distinct `params_hashes` per path (different attempts on same file) | `loop_guard.py:156` |
| `4f` | Thrash pattern denial | Denies when same path hit by multiple distinct attempts | `loop_guard.py:159` |
| `4g` | Two-threshold system | `repeat_warn` (soft warn) vs `circuit_breaker` (hard deny) thresholds | `loop_guard.py:71` |
| `4h` | Warn emission sink | `_emit_warn` is best-effort; errors are swallowed to avoid crashing the loop | `loop_guard.py:181` |
| `4i` | Warn deduplication | `_warned` set deduplicates warn emissions so each crossing fires exactly once | `loop_guard.py:103` |

---

## Trace 5: BlockerMiddleware Pattern Detection and Suppression

**Wave-2 blockers in `src/fa/inner_loop/hooks/blockers.py`** — detect rate-limit, lockfile, auth-expired patterns at `AFTER_TOOL_EXEC` and suppress repeat calls at `BEFORE_TOOL_EXEC` with time-based windows.

```text
BlockerMiddleware Pattern Detection Flow
├── Runtime dispatches to blocker
│   └── handle() routes by lifecycle point <-- 5a
│       ├── AFTER_TOOL_EXEC path <-- blockers.py:174
│       │   └── _observe() checks result <-- blockers.py:142
│       │       ├── _detect() pattern match <-- 5b
│       │       │   ├── RateLimitBlocker <-- blockers.py:231
│       │       │   │   └── check code/message <-- 5e
│       │       │   └── LockfileBlocker <-- blockers.py:257
│       │       │       └── regex search <-- 5f
│       │       └── record timestamp <-- 5c
│       └── BEFORE_TOOL_EXEC path <-- blockers.py:172
│           └── _gate() checks suppression <-- blockers.py:153
│               ├── lookup observed_at map <-- blockers.py:158
│               ├── calculate elapsed time <-- 5d
│               └── deny if within window <-- blockers.py:165
└── Subclasses (RateLimitBlocker,
    LockfileBlocker, AuthExpiredBlocker)
    override _detect() for signatures <-- blockers.py:133
```

| Location | Title | Description | File:Line |
| :--- | :--- | :--- | :--- |
| `5a` | Blocker handle routing | Routes to gate (`BEFORE`) or observe (`AFTER`) based on lifecycle point | `blockers.py:171` |
| `5b` | Pattern detection invocation | Subclass `_detect` checks error code/message for signatures | `blockers.py:149` |
| `5c` | Observation timestamp recorded | Keyed by `tool_name` for per-tool suppression tracking | `blockers.py:151` |
| `5d` | Suppression window check | Calculates time since last observation for same tool | `blockers.py:161` |
| `5e` | RateLimitBlocker code detection | Matches `rate_limited`, `http_429`, `too_many_requests` codes | `blockers.py:252` |
| `5f` | LockfileBlocker message regex | Matches contention-specific patterns (could not get lock, etc.) | `blockers.py:286` |
| `5g` | `BlockerCategory` enum | Values: `RATE_LIMIT`, `LOCKFILE`, `AUTH_EXPIRED` | `blockers.py:37` |
| `5h` | `time_source` injectability | Tests pass a mock clock; production uses `time.time` | `blockers.py:52` |
| `5i` | Observe-only mode | `suppression_seconds == 0` makes `AuthExpiredBlocker` observe-only by default | `blockers.py:275` |

---

## Trace 6: Hook Registration and Validation

**Registry setup in `src/fa/inner_loop/hooks/base.py`** — validates middleware type, lifecycle points, and family-disjoint rules for LLM-using hooks before building per-point chains.

```text
Hook Registration and Validation Flow
└── HookRegistry <-- base.py:119
    ├── register(middleware, acting_family) <-- 6a
    │   ├── _validate_middleware() <-- 6b
    │   │   ├── Type check: Guard XOR Observer <-- 6c
    │   │   ├── Lifecycle points validation <-- base.py:258
    │   │   └── LLM family-disjoint check <-- 6d
    │   ├── Idempotency check (id in _registered) <-- base.py:145
    │   └── Build per-point chains <-- base.py:148
    │       └── _chains[point].append() <-- 6e
    └── dispatch(point, payload) <-- base.py:151
        └── Iterate _chains[point] <-- base.py:156
            ├── GuardMiddleware.handle() <-- base.py:159
            └── ObserverMiddleware.observe() <-- base.py:212
```

| Location | Title | Description | File:Line |
| :--- | :--- | :--- | :--- |
| `6a` | Registration entry point | Validates and adds middleware to per-point chains | `base.py:142` |
| `6b` | Middleware validation invocation | Checks type, lifecycle points, and LLM family constraints | `base.py:143` |
| `6c` | Type exclusivity check | Ensures middleware is either Guard or Observer, not both | `base.py:256` |
| `6d` | Family-disjoint enforcement | Prevents LLM-using hooks from matching the acting LLM family | `base.py:264` |
| `6e` | Chain building | Appends to per-lifecycle-point chains in registration order | `base.py:149` |

---

## Trace 7: Observer Middleware: Audit, Learning, and Recovery

**Observer implementations in `src/fa/inner_loop/hooks`** — record audit trails, write discovery/gotchas to `knowledge/trace`, classify failures, and track attempt history at `AFTER_TOOL_EXEC`.

```text
Observer Middleware Execution Flow
├── AFTER_TOOL_EXEC Lifecycle Point <-- base.py:29
│   ├── AuditHook Observer <-- builtin.py:157
│   │   ├── observe() entry <-- 7a
│   │   └── event_log.append() <-- 7b
│   │       └── writes "audit" kind to events.jsonl
│   ├── LearningObserver <-- builtin.py:301
│   │   ├── Success path
│   │   │   └── record_discovery() <-- 7c
│   │   │       └── writes to codebase_map.json
│   │   └── Failure path <-- builtin.py:337
│   │       └── record_gotcha() <-- 7d
│   │           └── writes to gotchas.md
│   ├── FailureClassifierObserver <-- recovery_observers.py:40
│   │   ├── classify_result() <-- 7e
│   │   │   └── determines recovery action
│   │   └── event_log.append() <-- 7f
│   │       └── writes "recovery_action" kind
│   └── AttemptHistoryObserver <-- recovery_observers.py:89
│       └── history.append() <-- 7g
│           └── writes to attempt_history.json
```

| Location | Title | Description | File:Line |
| :--- | :--- | :--- | :--- |
| `7a` | AuditHook observe entry | Records tool name, ok status, summary to in-memory events list | `builtin.py:172` |
| `7b` | Audit event emission | Writes audit row to `events.jsonl` when `event_log` is configured | `builtin.py:184` |
| `7c` | LearningObserver discovery write | Appends successful tool results to `knowledge/trace/codebase_map.json` | `builtin.py:346` |
| `7d` | LearningObserver gotcha write | Appends failed tool results to `knowledge/trace/gotchas.md` | `builtin.py:338` |
| `7e` | FailureClassifierObserver classification | Determines recovery action (retry, escalate, abort) from error | `recovery_observers.py:66` |
| `7f` | Recovery action event emission | Writes `recovery_action` row with category, action, retryable flag | `recovery_observers.py:80` |
| `7g` | AttemptHistoryObserver write | Appends failure to `attempt_history.json` for coder-recovery prompt | `recovery_observers.py:132` |

---

## Trace 8: Tool Registry Schema Validation and Handler Dispatch

**Tool execution in `src/fa/inner_loop/registry.py`** — validates params against JSON Schema, catches handler exceptions, and re-validates after hook mutations per ADR-7 §5.

```text
Tool Registry Dispatch Flow
└── ToolRegistry.dispatch(call) <-- 8a
    ├── validate(call) invocation <-- 8b
    │   └── fastjsonschema validator invocation per call <-- registry.py:160 (schema compilation at `:137`)
    │       ├── Success path: return None <-- registry.py:170
    │       └── JsonSchemaValueException <-- 8c
    │           └── ToolResult.fail("invalid_params") <-- registry.py:165
    └── Handler execution path
        ├── _tools[call.name].handler(params) <-- 8d
        │   ├── Success: return ToolResult.ok()
        │   └── Exception raised
        │       └── Catch Exception <-- 8e
        │           └── ToolResult.fail("internal_error")
        └── Return ToolResult to runtime loop
```

| Location | Title | Description | File:Line |
| :--- | :--- | :--- | :--- |
| `8a` | Registry dispatch entry | Validates and executes tool handler with exception resilience | `registry.py:172` |
| `8b` | Schema validation invocation | Runs `fastjsonschema` validator compiled at registration time | `registry.py:173` |
| `8c` | Validation error handling | Converts schema violations to `invalid_params` `ToolResult` | `registry.py:163` |
| `8d` | Handler invocation | Executes registered tool handler with validated params | `registry.py:186` |
| `8e` | Handler exception wrapping | Catches unexpected handler crashes as `internal_error` `ToolResult` | `registry.py:192` |

---

## Known Limitations (v0.1)

- `ApprovalHook` HITL integration: intentionally a stub in v0.1 (no stdin/TTY plumbing). Opt-in via config, off by default per ADR-7 §8.
- `LearningObserver` file-write concurrency: v0.1 assumes single-process sessions. No file locking until concurrent-session requirements arrive.
