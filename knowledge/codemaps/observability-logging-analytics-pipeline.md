# Observability, Logging, and Analytics Pipeline

> Codemap ID: `Observability_Logging_Analytics_Pipeline_20260624_143000`

Three-layer architecture for session observability: **Layer 1** — `EventLog`
writes append-only JSONL audit trail to disk (`events.jsonl`); **Layer 2** —
`EventBus` + `ConsoleRenderer` emit live progress to stderr during `fa run`;
**Layer 3** — `fa stats` reads finished sessions from disk for post-hoc
analytics.  Supporting modules: `SecretRedactor` masks secrets before writing,
`CostGuardian` accumulates per-call cost observations, `formatting.py` provides
shared display helpers.

Each layer has distinct lifetime, sink, and consumers:

| Layer | Module | Lifetime | Sink | Consumer |
|-------|--------|----------|------|----------|
| 1 — Audit | `state.py` (EventLog) | Per-session, durable | JSONL file | `fa stats`, WebUI, replay |
| 2 — Live | `output.py` (EventBus) | Per-session, ephemeral | stderr | Operator terminal |
| 3 — Analytics | `stats.py` | On-demand, read-only | stderr / JSON stdout | Operator, WebUI API |

---

## Component Inventory

| Component | File | Type | Purpose |
|-----------|------|------|---------|
| `TraceEvent` | `state.py:96` | `@dataclass(frozen)` | One JSONL row — ADR-7 §7 schema |
| `EventLog` | `state.py:116` | Class | Append-only JSONL writer + reader |
| `SessionState` | `state.py:223` | `@dataclass` | Per-run state (workspace, run_id, log, observations) |
| `OutputEvent` | `output.py:56` | `@dataclass(frozen, slots)` | Single display event for live output |
| `EventBus` | `output.py:69` | Class | Sync fan-out to renderer listeners |
| `ConsoleRenderer` | `output.py:106` | Class | Human-readable stderr output |
| `QuietRenderer` | `output.py:251` | Class | No-op renderer (final answer to stdout only) |
| `SessionAnalytics` | `stats.py:110` | `@dataclass` | Complete analytics for one session |
| `TurnTokens` | `stats.py:48` | `@dataclass(frozen)` | Per-turn token breakdown |
| `ToolUsage` | `stats.py:63` | `@dataclass(frozen)` | Tool call count |
| `FileAccess` | `stats.py:71` | `@dataclass(frozen)` | File read/write counts |
| `BashCommand` | `stats.py:80` | `@dataclass(frozen)` | Bash command execution record |
| `ProviderHealth` | `stats.py:88` | `@dataclass(frozen)` | Provider reliability metrics |
| `GuardActivity` | `stats.py:100` | `@dataclass(frozen)` | Per-hook allow/deny/warn counts |
| `SecretRedactor` | `redaction.py:21` | Class | Mask secrets (raw, base64, hex, URL-encoded) |
| `CostGuardian` | `cost_guardian.py:175` | `GuardMiddleware` | Per-call cost accumulation + budget gate |
| `CostObservation` | `cost_guardian.py:80` | `@dataclass(frozen)` | Single cost sample |
| `CostRollup` | `cost_guardian.py:108` | `@dataclass(frozen)` | Rolling session-level cost totals |
| `fmt_tokens` | `formatting.py:15` | Function | Shared token-count formatter (`1200 → "1.2k"`) |

---

## Event Kind Registry

All `kind` values written to `events.jsonl`. Writer column shows where
`log.append(kind=...)` is called.

| Kind | Actor | Writer | Description |
|------|-------|--------|-------------|
| `user_msg` | `user` | `coder_loop.py:360` | User task text |
| `run_started` | `runtime` | `coder_loop.py:361` | Session metadata (role, max_turns, temperature) |
| `model_msg` | `model` | `coder_loop.py:627` | LLM response (text, tool_calls, tokens, finish_reason) |
| `usage` | `runtime` | `coder_loop.py:387` | Per-turn token usage (in/out/cache_read/cache_creation) |
| `provider_attempt` | `provider` | `coder_loop.py:482,536` | Per-entry chain attempt (status, ms, error) |
| `tool_call` | `coder` | `state.py:242` | Tool call params (via `SessionState.record_tool_call`) |
| `tool_result` | `tool` | `state.py:253` | Tool result (ok, summary, artifacts, error) |
| `hook_decision` | `hook` | `loop.py:32` | Middleware decision (middleware, point, decision, reason) |
| `audit` | `hook` | `builtin.py:189` | AuditHook tool execution record |
| `verification` | `hook` | `builtin.py:257` | VerifierObserver DSV contract trip |
| `recovery_action` | `hook` | `recovery_observers.py:80` | FailureClassifier category + action |
| `loop_guard_warn` | `hook` | via `warn_sink` callback | LoopGuard soft threshold crossed |
| `cost_observation` | `hook` | `cost_guardian.py:252` | Per-call cost sample + rollup snapshot |
| `run_stopped` | `runtime` | `coder_loop.py:*,loop.py:*` | Abnormal session termination (reason, detail) |
| `session_summary` | `runtime` | `coder_loop.py:398` | Run-level token totals + cache hit ratio |

---

## Trace 1: EventLog Write Path (Layer 1 — Audit)

**Core writer in `src/fa/inner_loop/state.py`** — append-only JSONL emitter
with secret redaction and monotonic event IDs.

```
EventLog.append() <-- state.py:166
├── Build TraceEvent <-- state.py:180
│   ├── event_id = f"ev-{next_id:06d}" <-- 1a
│   ├── ts = _now_iso_z() <-- state.py:80
│   ├── run_id from EventLog.run_id <-- 1b
│   └── content redacted via _redact_value() <-- 1c
│       └── SecretRedactor.redact() <-- redaction.py:97
│           ├── Raw string replacement <-- 1c1
│           ├── Base64-encoded replacement <-- 1c2
│           ├── Hex-encoded replacement <-- 1c3
│           ├── URL-encoded replacement <-- 1c4
│           ├── Reversed-string replacement <-- 1c5
│           └── Decoded-window backstop scan <-- 1c6
├── Increment _next_id <-- state.py:186
├── Ensure parent directory exists <-- state.py:187
└── Append JSON line to events.jsonl <-- 1d
    └── json.dumps(asdict(event), sort_keys=True) <-- state.py:189
```

| Location | Title | Description | File:Line |
|:---------|:------|:------------|:----------|
| `1a` | Monotonic event ID | Continues from existing line count on `--resume` | `state.py:138` |
| `1b` | Run ID stamping | Every row tagged with session `run_id` per ADR-7 §7 | `state.py:183` |
| `1c` | Content redaction | `SecretRedactor` applied to all content values before write | `state.py:168` |
| `1c1-6` | Multi-encoding redaction | Raw, base64, hex, URL-encoded, reversed, decoded-window | `redaction.py:97-141` |
| `1d` | Atomic line append | `open("a")` + single `write(line + "\n")` per event | `state.py:188` |

---

## Trace 2: EventLog Read Path (Layer 1 → Layer 3 bridge)

**Reader in `src/fa/inner_loop/state.py`** — parses JSONL back into
`TraceEvent` tuples. Used by `fa stats` and potential future replay.

```
EventLog.read_all() <-- state.py:197
├── Read file as text <-- 2a
├── For each non-empty line <-- state.py:201
│   └── json.loads(raw) <-- 2b
│       └── Construct TraceEvent from dict <-- 2c
│           ├── Mandatory: event_id, ts, actor, kind, harness_id
│           └── Optional: run_id, content, tool_name, tool_call_id
└── Return tuple[TraceEvent, ...] <-- 2d
```

| Location | Title | Description | File:Line |
|:---------|:------|:------------|:----------|
| `2a` | File read | `path.read_text(encoding="utf-8")` — entire file in memory | `state.py:201` |
| `2b` | JSON parse per line | One `json.loads` per JSONL line; corrupt lines raise | `state.py:204` |
| `2c` | TraceEvent construction | Defensive `str()` casts on all fields | `state.py:205` |
| `2d` | Immutable return | Returns `tuple`, not `list` — callers cannot mutate | `state.py:216` |

---

## Trace 3: Live Output Emit Path (Layer 2 — Display)

**Emitter in `src/fa/inner_loop/coder_loop.py`**, bus+renderers in
`src/fa/output.py` — fires `OutputEvent` at 7 call sites in `drive_session`,
parallel to (not replacing) `EventLog.append`.

```
drive_session() <-- coder_loop.py:280
├── output.emit(session_start) <-- 3a (coder_loop.py:371)
├── while turn < max_turns:
│   ├── output.emit(turn_start) <-- 3b (coder_loop.py:429)
│   ├── provider_chain.request() → response
│   │   ├── on success:
│   │   │   └── output.emit(llm_response) <-- 3c (coder_loop.py:498)
│   │   ├── on ProviderChainExhaustedError:
│   │   │   └── output.emit(api_retry) ×N <-- 3d (coder_loop.py:556)
│   │   └── on BEFORE_LLM_CALL deny:
│   │       └── output.emit(hook_deny) <-- 3e (coder_loop.py:452)
│   └── for call, result in tool_calls:
│       └── output.emit(tool_call) <-- 3f (coder_loop.py:727)
└── finish() → output.emit(session_end) <-- 3g (coder_loop.py:406)
```

```
EventBus.emit(event) <-- output.py:82
├── for listener in _listeners: <-- 3h
│   ├── try: listener.on_event(event) <-- 3i
│   └── except: print to stderr <-- 3j (never crash loop)
│
├── ConsoleRenderer.on_event(event) <-- output.py:141
│   └── getattr(self, f"_handle_{event.type}") <-- 3k
│       ├── _handle_session_start → model/role/max_turns <-- output.py:146
│       ├── _handle_turn_start → "[turn N/M]" <-- output.py:153
│       ├── _handle_llm_response → ms/tokens/cache% <-- output.py:158
│       ├── _handle_tool_call → verb/path/summary/ok <-- output.py:176
│       ├── _handle_hook_deny → ⛔ hook: reason <-- output.py:212
│       ├── _handle_api_retry → ⏳ retry in Ns <-- output.py:216
│       └── _handle_session_end → summary bar <-- output.py:223
│
└── QuietRenderer.on_event(event) <-- output.py:254
    └── pass (no-op)
```

| Location | Title | Description | File:Line |
|:---------|:------|:------------|:----------|
| `3a` | Session start emit | Model slug, role, family | `coder_loop.py:371` |
| `3b` | Turn start emit | Turn counter / max_turns | `coder_loop.py:429` |
| `3c` | LLM response emit | Elapsed ms, in/out tokens, cache%, tool_call_count | `coder_loop.py:498` |
| `3d` | API retry emit | Per failed attempt: provider, status, error | `coder_loop.py:556` |
| `3e` | Hook deny emit | Hook name, deny reason | `coder_loop.py:452` |
| `3f` | Tool call emit | Tool name, params, summary, ok/error | `coder_loop.py:727` |
| `3g` | Session end emit | Stop reason, turns, wall time, total tokens, cache ratio | `coder_loop.py:406` |
| `3h` | Fan-out dispatch | Iterates all listeners; crash in one doesn't stop others | `output.py:83` |
| `3i` | Listener invocation | `listener.on_event(event)` — duck-typed protocol | `output.py:85` |
| `3j` | Crash isolation | Catches all exceptions, prints to stderr | `output.py:86` |
| `3k` | Handler dispatch | `getattr(self, f"_handle_{event.type}")` dynamic dispatch | `output.py:142` |

---

## Trace 4: Post-hoc Analytics (Layer 3 — `fa stats`)

**Analytics engine in `src/fa/stats.py`** — reads `EventLog.read_all()`,
aggregates into typed dataclasses, renders to console or JSON.

```
_cmd_stats(args) <-- cli.py:1090
├── Discover session dirs <-- 4a
│   ├── --run-id → single dir <-- cli.py:1111
│   └── default → all dirs with events.jsonl <-- cli.py:1117
├── Filter by --since (file mtime) <-- 4b
├── parse_session(events_path) per dir <-- 4c
│   └── See Trace 4a below
├── Render <-- 4d
│   ├── --output json → render_session_json() <-- cli.py:1148
│   └── console → render_session() / render_aggregate() <-- cli.py:1160
└── --dead-zones → find_dead_zones() <-- 4e

parse_session(events_path) <-- stats.py:137
├── EventLog(path).read_all() <-- 4c1
├── Event dispatch loop <-- stats.py:183
│   ├── run_started → extract role <-- 4c2
│   ├── tool_call → tool_counter + reads/writes/bash <-- 4c3
│   ├── usage → turn_tokens timeline <-- 4c4
│   ├── provider_attempt → provider_data dict <-- 4c5
│   ├── hook_decision → guard_data allow/deny <-- 4c6
│   ├── loop_guard_warn → LoopGuard warn++ <-- 4c7
│   ├── session_summary → totals + cache_hit_ratio <-- 4c8
│   └── run_stopped → stop_reason + ok flag <-- 4c9
├── Build typed results <-- stats.py:247
│   ├── ToolUsage sorted by count desc <-- 4c10
│   ├── FileAccess merged reads+writes <-- 4c11
│   ├── BashCommand sorted by count <-- 4c12
│   ├── ProviderHealth (ok/total, avg/max ms) <-- 4c13
│   ├── GuardActivity per hook <-- 4c14
│   └── Efficiency counters (redundant_reads, repeated_commands) <-- 4c15
└── Return SessionAnalytics <-- stats.py:299

aggregate_sessions(sessions) <-- stats.py:416
├── Sum total_in, total_out across sessions <-- 4f1
├── Count ok/failed sessions <-- 4f2
├── Most-read files across all sessions <-- 4f3
├── Stop reason distribution <-- 4f4
└── Average cache hit ratio <-- 4f5

find_dead_zones(workspace, sessions) <-- stats.py:485
├── Enumerate src/**/*.py <-- 4g1
├── Collect all accessed paths from sessions <-- 4g2
└── Return sorted(all_py - accessed) <-- 4g3

efficiency_warnings(analytics) <-- stats.py:507
├── Redundant file reads <-- 4h1
├── Repeated bash commands <-- 4h2
└── Late cache misses (after turn 2) <-- 4h3
```

| Location | Title | Description | File:Line |
|:---------|:------|:------------|:----------|
| `4a` | Session discovery | Scan `workspace/.fa/runs/*/events.jsonl` | `cli.py:1107` |
| `4b` | Age filter | `--since 7d` → compare dir `mtime` vs `time.time()` | `cli.py:1128` |
| `4c` | Session parsing | Single-pass event loop over `TraceEvent` rows | `stats.py:137` |
| `4c6` | Guard activity | ⚠ Reads `content["middleware"]` for hook name | `stats.py:222` |
| `4d` | Rendering | Console (stderr) or JSON (stdout) based on `--output` | `cli.py:1148` |
| `4e` | Dead zones | `src/` Python files never accessed across sessions | `stats.py:485` |

---

## Trace 5: CostGuardian Observation Pipeline

**Observer+guard in `src/fa/observability/cost_guardian.py`** — accumulates
per-call cost from `ToolResult.artifacts`, optionally denies when budget
exceeded.

```
CostGuardian <-- cost_guardian.py:175
├── handle(AFTER_TOOL_EXEC) → _observe() <-- 5a
│   ├── _extractor(result) → list[CostObservation] <-- 5b
│   │   └── default_cost_extractor() <-- cost_guardian.py:128
│   │       └── Parse "cost=tokens_in=N,tokens_out=N,usd=F" artifacts
│   ├── For each observation: <-- 5c
│   │   ├── self.rollup = rollup.add(observation) <-- 5d
│   │   └── _event_log.append(kind="cost_observation") <-- 5e
│   └── Decision.allow() always <-- 5f
│
├── handle(BEFORE_TOOL_EXEC) → _gate() <-- 5g
│   ├── budget_usd is None → allow (unbounded) <-- 5h
│   ├── budget_usd == 0.0 → allow (observe-only) <-- 5i
│   └── rollup.usd > budget_usd → deny <-- 5j
│
└── Dormant on M-1 baseline tools <-- 5k
    └── fs.read_file/write_file/run_bash emit no cost= artifacts
```

| Location | Title | Description | File:Line |
|:---------|:------|:------------|:----------|
| `5a` | Observe at AFTER_TOOL_EXEC | Extracts cost from ToolResult artifacts | `cost_guardian.py:237` |
| `5b` | Cost extraction | Parses `"cost=tokens_in=X,..."` artifact strings | `cost_guardian.py:128` |
| `5d` | Rollup accumulation | Immutable `CostRollup.add()` returns new instance | `cost_guardian.py:118` |
| `5e` | Cost event emission | Writes `cost_observation` kind with rollup snapshot | `cost_guardian.py:252` |
| `5g` | Gate at BEFORE_TOOL_EXEC | Budget check before next tool call | `cost_guardian.py:220` |
| `5j` | Budget denial | Denies when accumulated USD exceeds configured budget | `cost_guardian.py:232` |
| `5k` | Dormant status | Active only when T-2 LLM driver emits cost artifacts | Module docstring |

---

## Trace 6: SecretRedactor Integration Points

**Redaction in `src/fa/observability/redaction.py`** — masks API keys in
multiple encoding forms. Integrated at two chokepoints.

```
SecretRedactor integration
├── EventLog chokepoint (input to disk) <-- 6a
│   └── EventLog._redact_value(content) <-- state.py:153
│       └── SecretRedactor.redact(string_value) <-- redaction.py:97
│
├── LLM chokepoint (input to provider) <-- 6b
│   └── _redact(redactor, tool_result_text) <-- coder_loop.py:121
│       └── SecretRedactor.redact(text) <-- redaction.py:97
│
└── LearningObserver chokepoint <-- 6c
    └── redactor.redact(result.summary|error.message)
        └── builtin.py:329,335
```

| Location | Title | Description | File:Line |
|:---------|:------|:------------|:----------|
| `6a` | Disk write chokepoint | Content redacted before JSONL serialization | `state.py:168` |
| `6b` | LLM input chokepoint | Tool result text redacted before next model turn | `coder_loop.py:121` |
| `6c` | Learning artifact chokepoint | Discovery/gotcha entries redacted before fs write | `builtin.py:329` |

---

## Data Flow Diagram

```
                         drive_session()
                        ┌──────────────────────────────────────────┐
                        │  per turn:                                │
                        │                                          │
  ┌─────────────────────┤  1. state.log.append(kind)     ──────┐   │
  │                     │     (14 call sites)                  │   │
  │  SecretRedactor ◄───┤                                      │   │
  │  (mask before       │  2. output.emit(OutputEvent)  ───┐   │   │
  │   write)            │     (7 call sites)               │   │   │
  │                     │                                  │   │   │
  │                     └──────────────────────────────────┼───┼───┘
  │                                                        │   │
  ▼                                                        ▼   ▼
┌──────────────┐                                    ┌──────────────┐
│ events.jsonl │ (durable, append-only)             │   stderr     │
│ JSONL file   │                                    │   (live)     │
│              │                                    │              │
│ TraceEvent   │                                    │ OutputEvent  │
│ rows         │                                    │ → Renderer   │
└──────┬───────┘                                    └──────────────┘
       │
       │ EventLog.read_all()
       ▼
┌──────────────┐
│  fa stats    │ (post-hoc, read-only)
│              │
│ parse_session│ → SessionAnalytics
│              │   (typed dataclass)
│              │
│ render_*()   │ → stderr (console)
│              │ → stdout (JSON)
└──────────────┘
```

---

## Dual-Write Correspondence

Each `drive_session` event has a paired write to both Layer 1 and Layer 2.
The table below shows the correspondence:

| Event | EventLog kind | OutputEvent type | Notes |
|-------|---------------|------------------|-------|
| Session start | `user_msg` + `run_started` | `session_start` | EventLog gets 2 rows, output gets 1 |
| LLM response | `model_msg` + `usage` | `llm_response` | EventLog captures full text; output shows summary |
| Provider attempt | `provider_attempt` | (part of `llm_response`) | EventLog per-attempt; output aggregates |
| Tool execution | `tool_call` + `tool_result` | `tool_call` | EventLog via SessionState; output after result |
| Hook deny | `run_stopped` | `hook_deny` | EventLog records reason; output shows emoji |
| Chain exhausted | `run_stopped` + `provider_attempt`×N | `api_retry`×N | EventLog captures all; output per-attempt |
| Session end | `session_summary` | `session_end` | Both have token totals + cache ratio |

---

## Known Limitations (v0.1)

- **EventLog.read_all() loads entire file** (`state.py:201`): fine for
  sub-1000-event sessions; will need streaming for multi-thousand-event
  sessions or aggregate analysis across hundreds of runs.
- **No session_summary for abnormal exits**: if `drive_session` crashes before
  `finish()`, no `session_summary` event lands. `fa stats` falls back to
  summing individual `usage` events (via `turn_tokens` timeline).
- **Cost tracking dormant**: `CostGuardian` wired but no baseline tool emits
  `cost=` artifacts. Active when T-2 LLM driver lands.
- **`--files` / `--tokens` flags**: declared in argparser but not yet wired
  to section-selective rendering (stub for I-29 backlog item).
