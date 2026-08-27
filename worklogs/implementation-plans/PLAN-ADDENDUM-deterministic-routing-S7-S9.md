# PLAN ADDENDUM: Deterministic Routing + Full E3 Cost Model
**Plan-ID:** PLAN-deterministic-routing-S7-S9
**Status:** READY   **Depth:** P2 (cross-module: CLI + loop + config + schema)
**Revision:** v2   **Changed-since-last:** adversarial self-audit against source.
Five confirmed defects in v1, three of them unexecutable-as-written:
(1) CT10's injection channel did not exist — `state.observations` is read by
nothing; corrected to `turn_context`. (2) The S7 "hoist" was impossible —
`state` is built after the registry; replaced by the CT8b split. (3)
`compute_cost_floor` needed paths that telemetry discards; S8 now threads them.
(4) The "capability not compliance" claim was false — `fs_run_bash` evades the
gate; now RK-G, stated openly rather than papered over. (5) v1 would have built
a duplicate file counter; `record_tool_call` already maintains one.
**Parent plan:** `PLAN-complexity-aware-execution-chat-role.md` (S1–S5 DONE, S6 pending)
**Date:** 2026-08-27

Extends the parent plan with **S7** (deterministic escalation), **S8** (full E3
cost model + calibration), **S9** (live verification sheet). S6 (ADR-16 + docs)
is re-sequenced to run last so it records settled decisions once.

---

## Preflight log

```text
roots checked:
  - fa.cli._cmd_run                       (real CLI root; registry build @1923, scope estimate @2010)
  - fa.cli._build_run_tool_registry@1444  (role tool corpus; signature has NO scope param today)
  - fa.cli._estimate_scope_for_chat@1718  (scope producer; returns hint str, logs event, writes blackboard)
  - fa.inner_loop.coder_loop.drive_session@298 (turn loop @655 `while turn < max_turns`)
  - fa.inner_loop.global_history          (projection store; S5 columns live)

greps/reads -> findings (v2 — five claims in v1 were WRONG, corrected here):
  - ORDERING (v1 claim REVISED): registry @cli.py:1923, hooks @cli.py:1981,
    `state = SessionState(...)` @cli.py:1993, scope estimate @cli.py:2010.
    v1 said "hoist _estimate_scope_for_chat above the registry". IMPOSSIBLE:
    that function takes `state`, which does not exist until 1993. The fix is a
    SPLIT, not a hoist (see CT8/S7 step 2).
  - `estimate_scope(task)` (scope_estimator.py:133) is PURE — "No LLM calls, no
    I/O, no imports beyond stdlib", verified by execution. It can be called at
    line ~1900 with nothing but `args.task`. This is what makes the split work.
  - `_estimate_scope_for_chat` (cli.py:1718-1795) returns a HINT STRING, not an
    OperatingPoint. The gate needs the typed point, so the split must surface it.
  - state.observations (state.py:356) is `list[str]`, written in 7 places
    (coder_loop.py:1611, loop.py:277/291/305/311/350/441) and READ BY NOTHING
    in the drive_session path. v1's CT10 was built on a false premise.
  - The `observations=` parameter of build_prompt_parts_v2
    (prompt_composer.py:90) is `list[dict[str, Any]]` and is bound to
    `conversation_history` (coder_loop.py:768) — message history, NOT
    state.observations. Different type, different object.
  - THE REAL INJECTION CHANNEL is `turn_context` (coder_loop.py:421), a
    never-reassigned local of `_drive_session_inner` read as a closure free
    variable INSIDE the turn loop (coder_loop.py:749). cache_key is
    `f"fa-{role_id}-{hash_tools}-{hash_map}-{hash_always}"`
    (prompt_composer.py:121) — turn_context is provably NOT in it, and its
    docstring (prompt_composer.py:101-105) names the chat scope estimate as its
    intended consumer. D7-safe by construction.
  - COUNTERS ALREADY EXIST. `state.record_tool_call` (state.py:739-748) already
    calls add_read for fs_read_file and add_write for fs_write_file/fs_edit_file
    — the exact S5 groups. `state.transaction` is auto-created (verified by
    execution: NOT None by default), and `transaction.read_set`/`write_set` are
    deduped lists. v1 step 7 would have built a redundant second counter.
  - GATE BYPASS (most serious v1 defect): the live chat corpus is 13 tools and
    includes `fs_run_bash` (verified by executing build_live_chat_registry).
    Removing fs_write_file/fs_edit_file does NOT make chat read-only —
    `echo x > f.py` and `sed -i` still work. v1's claim "determinism comes from
    capability, not compliance" was FALSE as written.
  - BUT the mechanism to close it already exists: `evaluate_bash(...,
    allow_general_write: bool = True)` (bash_gate.py:78) and
    `SandboxHook.allow_general_write` (builtin.py:101). Verified by execution:
    with False, `echo x > out.py` and `sed -i` -> allow=False category
    general_write, while `cat`/`ls` stay allow=True category read_only.
    TRADEOFF (measured): `pytest -q` is ALSO classified general_write and
    denied. See RK-G — this is why the gate withholds tools but leaves bash.
  - `_extract_telemetry_from_log` (global_history.py:288) DISCARDS paths at its
    return boundary — it returns `len(read_paths)`/`len(changed_paths)` only
    (global_history.py:372-373). v1's compute_cost_floor(changed_paths, ...) was
    unimplementable. `build_export_row` DOES take `workspace_root`
    (global_history.py:385), so threading the paths through fixes it.
  - `_build_run_hook_registry` @cli.py:1479 (called @1981) constructs
    `SandboxHook(workspace)` @1544 with the flag defaulted — the seam for RK-G.

gold patterns mirrored:
  - S5 PRAGMA-guarded ALTER migration (global_history.py:184-196) — reuse verbatim.
  - RK8 CLI validation block (cli.py:1146-1163) — the "validate at the boundary,
    exit 2, name the permitted set" shape.
  - tests/_chat_registry_fixture.py — live registry assembly for C1 tests.

conflicts/invariants:
  - Q1 (chat writes UNRESTRICTED) is PARTIALLY REVERSED by S7 Layer 1, with
    operator approval 2026-08-27. Narrow: high-confidence workflow_linear only.
  - D7: scope hint must NOT travel on system_prompt_extra (cache-key pollution,
    measured). Tripwire text goes to `turn_context`, which is outside the cache
    key (prompt_composer.py:121) and is the composer's designated channel for
    per-request advisory text (prompt_composer.py:101-105) — D7-safe.
  - `turn_context` ALREADY carries the S3 scope hint (cli.py:2010 ->
    drive_session). The tripwire APPENDS; it must not overwrite (RK-H).
  - S10b stats stream split (json->stdout, human->stderr) still binding.

current liveness: S7 L0 · S8 L0 · S9 L0
unresolved -> Q#: none blocking. Q20/Q21/Q22 resolved by operator below.
```

---

## 0. Executive intent

### Goals

| G# | Goal | Closes |
|---|---|---|
| G7 | Chat **cannot** hand-edit its way through a task the estimator confidently calls repo-scale | GAP7 |
| G8 | A run that outgrows its estimate is **mechanically detected** and told, mid-run | GAP8 |
| G9 | Routing quality is **measurable and observable** (db + blackboard), not anecdotal | GAP9 |
| G10 | The escalation gate is **operator-toggleable** without a code change | GAP10 |

### Non-goals (explicit)

- Making the estimator itself smarter. It is 60% accurate; S7/S8 make its
  errors *survivable and visible*, they do not fix it. A labelled test set was
  considered and **declined by the operator** — Layer 3 calibration supplies the
  data instead.
- Oracle-grade ACRR (replay benchmark over gold patches). Deferred, unblocked.
- Auto-invoking the workflow on tripwire (rejected — no rollback from a
  half-edited tree; see Q21).
- Any change to the simple-task path. Measured 0 over-scopes; adding machinery
  there could only regress it.

### Minimal mechanism

Three layers, each the smallest thing that produces its guarantee:

1. **Layer 1** — one boolean condition at registry-build time. Not a prompt
   directive; the write tools are *absent from the corpus*. Determinism comes
   from capability, not compliance.
2. **Layer 2** — a counter and a threshold in an existing per-turn hook,
   appending to an existing observations list. No new channel.
3. **Layer 3** — arithmetic over columns we already store, plus one new stats view.

### Proof sketch

A C1 test builds the **real** chat registry via the live path with a
high-confidence `workflow_linear` estimate and asserts `fs_write_file` is
absent; flipping the threshold constant restores it and the test fails. A C1
test drives a **real** session past the file threshold and asserts the tripwire
sentence appears in the **composed request body** — the oracle is the built
request, not an append to an intermediate list, because v1's chosen list was
read by nothing and every mock-based test would still have passed. A C0 test
pins each cost axis.

---

## 1. Current state → target state

| GAP# | Current (source-verified) | Target | S# |
|---|---|---|---|
| GAP7 | `_build_run_tool_registry` ignores scope entirely; chat always gets write tools (profiles.py:158-167) | Write tools withheld when `workflow_linear` ∧ `confidence>=0.8` ∧ toggle on | S7 |
| GAP8 | No mid-run scope check anywhere. `invoke_workflow` fires only if the model elects to call it | Per-turn distinct-file counters; threshold crossing appends an observation | S7 |
| GAP9 | `read_amplification` only; no cost model, no calibration view, no blackboard entry | `cost_actual`/`cost_floor`/`acrr` columns + `fa stats --calibration` + blackboard | S8 |
| GAP10 | No config knob for routing | `chat_escalation_gate` in runtime_limits | S7 |

---

## 2. Contracts

### CT8: escalation gate (function)

```text
CT8: should_withhold_write_tools TYPE:function/module
PRODUCER: NEW src/fa/inner_loop/routing.py:should_withhold_write_tools
ROOTS/CALLERS: fa.cli._build_run_tool_registry (via _cmd_run)
INPUTS:  point: OperatingPoint | None, role: str, gate_enabled: bool
OUTPUTS: bool
SIDE EFFECTS: none (pure)
INVARIANTS:
  - role != "chat"                      -> False  (never gate other roles)
  - point is None                       -> False  (no estimate -> no gate; fail-open)
  - gate_enabled is False               -> False  (operator override wins)
  - mode != "workflow_linear"           -> False
  - confidence < GATE_MIN_CONFIDENCE    -> False
  - workflow_linear AND conf >= 0.8 AND on -> True
RATIONALE (measured 2026-08-27, 15 realistic tasks):
  accuracy by confidence: 0.8 -> 4/4 (100%), 0.6 -> 3/5, 0.3 -> 2/6.
  All 6 errors were UNDER-scopes; zero over-scopes.
BOUNDARY (verified by execution, scope_estimator.py:147-148): confidence is one
  of exactly {0.8, 0.6, 0.3}. `>= 0.8` and `> 0.6` select the same set TODAY,
  so the comparison operator is not observable by the estimator's current
  outputs. Use `>=` and pin the constant at 0.8; T21 asserts the 0.6 bucket is
  ungated so the boundary is still nailed down if the estimator ever emits 0.7.
FAIL-OPEN: every ambiguous input returns False.
KILL-CHECK: set GATE_MIN_CONFIDENCE = 0.0 -> T21 fails
```

### CT8b: scope resolution ordering (function) — REPLACES v1's "hoist"

```text
CT8b: _resolve_scope_point / _publish_scope_estimate TYPE:function/module
PRODUCER: fa.cli — SPLIT of the existing _estimate_scope_for_chat (cli.py:1718)
WHY A SPLIT AND NOT A HOIST (v1 defect): the gate needs the estimate at the
  registry build (cli.py:1923), but _estimate_scope_for_chat takes `state`,
  and `state = SessionState(...)` is not constructed until cli.py:1993. The
  v1 instruction "hoist the call above the registry build" is IMPOSSIBLE.
  `estimate_scope` itself is pure (verified), so the pure part can move early
  while the side effects stay where `state` exists.

  _resolve_scope_point(role, task) -> OperatingPoint | None
      PURE. role != "chat" -> None. estimate_scope raises ValueError on an
      empty task -> None. No logging, no blackboard, no state. Called ONCE at
      cli.py ~1900, BEFORE the registry build.

  _publish_scope_estimate(point, task, log, state, run_id) -> str
      ALL the side effects of today's function, unchanged: the scope_estimate
      event append and the blackboard write, in that order. Returns the hint
      string. Called at today's site (cli.py:2010) with the ALREADY-COMPUTED
      point. point is None -> return "" and write nothing.

INVARIANT (the one that matters): estimate_scope is evaluated EXACTLY ONCE per
  run, and exactly ONE scope_estimate event is appended. Two calls would
  double-emit and corrupt the S3.5 projection, which reads
  `elif ev.kind == "scope_estimate"` (global_history.py:346) and would keep the
  LAST one silently.
BEHAVIOUR PRESERVED: for a non-chat role or an empty task the pair must produce
  byte-identical observable output to today's single function.
KILL-CHECK: call estimate_scope a second time in _publish -> T40 fails
            (asserts exactly one scope_estimate event)
```

### CT9: withheld-write chat registry (signal)

```text
CT9: gated chat corpus TYPE:signal
PRODUCER: fa.cli._build_run_tool_registry — skips fs_write_file / fs_edit_file /
          fs_spawn_subagent when CT8 returns True
CONSUMER: the LLM's tool-call surface; operator sees a WARNING line
LIVE CORPUS (verified by executing build_live_chat_registry against a real dir):
  13 tools = fs_blackboard_query, fs_chronicle_search, fs_edit_file,
  fs_exploration_metrics, fs_reach, fs_read_file, fs_run_bash, fs_search,
  fs_spawn_subagent, fs_usage, fs_write_file, invoke_workflow, pr_prepare.
  Gated -> 10 tools. invoke_workflow MUST remain (escalation must stay possible).
SCOPE OF THE GUARANTEE — state it honestly, do not overclaim:
  This removes the DECLARED write affordances. It does NOT make chat
  incapable of writing: fs_run_bash remains and `echo x > f.py` / `sed -i`
  still work (verified). The honest claim is "the model is not offered a
  write tool and must either escalate or go out of its way", NOT "writes are
  impossible". v1 asserted capability-level determinism; that was false.
  Closing the bash path is possible (allow_general_write=False) but denies
  `pytest` too — deliberately NOT done here; see RK-G.
STATE: decided ONCE at registry-build time, never mutated mid-session.
PATHS/MATRIX: P30-P34 / M10-M12
PRODUCER KILL-CHECK: remove the skip -> T20 fails
CONSUMER KILL-CHECK: remove the WARNING emit -> T22 fails
```

### CT10: scope tripwire (signal) — MECHANISM CORRECTED

```text
CT10: mid-run scope tripwire TYPE:signal
PRODUCER: NEW src/fa/inner_loop/routing.py:check_scope_tripwire, called inside
          the turn loop of _drive_session_inner (coder_loop.py:655)
CONSUMER: the `turn_context` closure variable (coder_loop.py:421, read at :749)
          -> build_prompt_parts_v2(turn_context=...) -> the NON-CACHEABLE block

v1 DEFECT, CORRECTED: v1 routed this through `state.observations`, claiming it
  "ALREADY flows into build_prompt_parts_v2". It does not. state.observations
  is list[str] and is read by NOTHING in the drive_session path; the composer's
  `observations` parameter is list[dict] bound to conversation_history
  (coder_loop.py:768). Appending there would have been a silent no-op that
  every mock-based test would still have passed.

MECHANISM: `turn_context` is a plain local of _drive_session_inner, never
  reassigned today (only reads at :397 and :749), and it is read as a closure
  free variable on every turn. Appending one line to it inside the loop is
  therefore visible on the NEXT request. Needs `nonlocal`/local rebinding at
  the loop level — confirm the enclosing scope when editing.
D7-SAFE BY CONSTRUCTION: cache_key = f"fa-{role_id}-{hash_tools}-{hash_map}-
  {hash_always}" (prompt_composer.py:121). turn_context is not a component.
  The composer docstring (prompt_composer.py:101-105) explicitly designates
  this parameter as the channel for per-request advisory text.

COUNTER SOURCE (already exists — do NOT build a second one):
  state.record_tool_call (state.py:739-748) already calls add_read for
  fs_read_file and add_write for fs_write_file/fs_edit_file. Read
  `len(state.transaction.read_set)` and `len(state.transaction.write_set)`.
  Verified by execution: transaction is auto-created (not None), and both
  sets are deduped. If transaction is None (defensive), the tripwire is a
  no-op — never raise from telemetry.
TRIGGER: distinct reads > TRIPWIRE_READ_LIMIT or distinct writes >
  TRIPWIRE_CHANGE_LIMIT, for a chat run whose estimate was chat_direct/chat_planned.
PAYLOAD: one plain sentence naming the counts and `invoke_workflow`.
FIRES: at most ONCE per run (latched).
DUAL-WRITE: turn_context (live) + a `scope_tripwire` event row (durable).
PATHS/MATRIX: P35-P38
PRODUCER KILL-CHECK: remove the turn_context append -> T25 fails
CONSUMER KILL-CHECK: assert the text reaches the composed request -> T26 fails
```

### CT11: E3 cost model (function)

```text
CT11: compute_cost / compute_cost_floor / compute_acrr TYPE:function/module
PRODUCER: src/fa/inner_loop/acrr.py (EXTEND — module exists from S5)
INPUTS:  compute_cost(latency_s, tokens, tool_calls, files, *, weights)
         compute_cost_floor(changed_paths, workspace, output_tokens)
         compute_acrr(cost_actual, cost_floor) -> float | None
OUTPUTS: float; compute_acrr returns None when floor <= 0
FORMULA: C = α·T_lat + β·N_tok + γ·N_tool + δ·N_file        (E3 Eq. 1)
         ACRR = (C_act − C_floor) / C_floor                  (E3 Eq. 3)
INVARIANTS:
  - ACRR == 0.0 when actual == floor (optimally lean)
  - ACRR > 0 when actual > floor; NEGATIVE is possible and is NOT clamped
    (a run cheaper than its own floor means the floor model is wrong — that is
     a signal worth seeing, not an error to hide)
  - floor EXCLUDES latency: machine/provider dependent and non-deterministic.
    The paper does exactly this in LLM-Case §7.7: "the measured wall-clock
    latency is omitted here so that C_min stays deterministic."
  - negative inputs -> ValueError (as compute_acrr_proxy already does)
WEIGHTS: NOT the paper's (1.0, 0.02, 0.5, 1.5). Measured 2026-08-27: at our
  token scale those put tokens at 89-93% of C and the file axis under 3%,
  numerically erasing the axis E3 calls "the canonical unit of redundancy".
  Fitted values recorded in ADR-16 (S6) with the derivation. Configurable.
  Safe per E3 §7.5: ordering stable in 99.8% of 4000 random weightings.
KILL-CHECK: drop the δ·N_file term -> T31 fails
```

### CT12: calibration projection (data)

```text
CT12: routing calibration TYPE:data
SCHEMA: additive. runs gains cost_actual REAL, cost_floor REAL, acrr REAL(NULL-able);
        acrr_proxy RENAMED read_amplification (free: 0 occurrences on main)
READ/WRITE: build_export_row writes; _cmd_stats_global_history + NEW
            _cmd_stats_calibration read
AUTHORITY: global_history.db is a DERIVED projection; EventLog stays authority
MIGRATION: PRAGMA table_info guard + ALTER TABLE ADD COLUMN, reusing the S5
  pattern verbatim (global_history.py:184-196). acrr/cost_floor NULLable with
  NO DEFAULT — NULL means "not computed", 0.0 would assert a perfect run.
BLACKBOARD: routing outcome also written to the session blackboard, matching
  the S3.5 scope_estimate precedent, so it is observable in-session.
FIXTURE HONESTY: C1 tests use a real sqlite file and the real schema.
KILL-CHECK: drop the migration -> T33 fails on a pre-S8 DB
```

---

## 3. Path / matrix inventory

| P# | Trigger | Behavior | S# | T# |
|---|---|---|---|---|
| P30 | chat + workflow_linear + conf 0.8 + gate on | write tools absent; WARNING emitted | S7 | T20,T22 |
| P31 | chat + workflow_linear + conf 0.6 | writes PRESENT (below threshold) | S7 | T21 |
| P32 | chat + chat_direct + conf 0.8 | writes present | S7 | T21 |
| P33 | gate toggled off in config | writes present even at conf 0.8 | S7 | T23 |
| P34 | role=coder, any estimate | never gated | S7 | T24 |
| P35 | chat_direct run reads 11 distinct files | observation appended once | S7 | T25 |
| P36 | same run, turn 12 | NOT appended again (latched) | S7 | T27 |
| P37 | run stays under threshold | no observation | S7 | T28 |
| P38 | tripwire fires, model ignores it | run continues normally (advisory) | S7 | T29 |
| P39 | successful run, floor computable | acrr stored | S8 | T30 |
| P40 | failed run | acrr stored, NOT displayed | S8 | T34 |
| P41 | run changed 0 files | cost_floor 0 -> acrr NULL | S8 | T32 |
| P42 | pre-S8 DB opened | three columns added, insert succeeds | S8 | T33 |
| P43 | changed file deleted before export | floor skips it, no crash | S8 | T35 |

| M# | Matrix row | Coverage |
|---|---|---|
| M10 | gate on (default) | T20 |
| M11 | gate off | T23 |
| M12 | no scope estimate (task empty) | T21 — fail-open |
| M13 | workflow role stages | N/A — RK8 allowlist already bars chat as a stage |

---

## 4. Artifacts

| A# | Path | Action | S# |
|---|---|---|---|
| A20 | `src/fa/inner_loop/routing.py` | **NEW** — gate + tripwire predicates | S7 |
| A21 | `src/fa/cli.py` | EDIT — CT8b split (pure resolve @~1900 / publish @2010); gate; WARNING | S7 |
| A22 | `src/fa/inner_loop/runtime_limits.py` | EDIT — `chat_escalation_gate` bool key | S7 |
| A23 | `src/fa/inner_loop/coder_loop.py` | EDIT — tripwire in the turn loop @655; appends to `turn_context` | S7 |
| A24 | `tests/test_chat_escalation_gate.py` | **NEW** | S7 |
| A25 | `tests/test_scope_tripwire.py` | **NEW** | S7 |
| A26 | `src/fa/inner_loop/acrr.py` | EDIT — cost model | S8 |
| A27 | `src/fa/inner_loop/global_history.py` | EDIT — 3 columns + rename + migration | S8 |
| A28 | `src/fa/cli.py` | EDIT — `--calibration` view | S8 |
| A29 | `tests/test_e3_cost_model.py` | **NEW** | S8 |
| A30 | `worklogs/reviews/S9-LIVE-VERIFICATION-2026-08-27.md` | **NEW** | S9 |

---

## 5. Implementation slices

### S7 — Deterministic escalation (Layers 1 + 2) ✅ DONE 2026-08-27

**Shipped:** `3b8c241` (impl) · `f4a98eb` (mutation hardening).
**Report:** `worklogs/reviews/S7-IMPLEMENTATION-REPORT-2026-08-27.md`.
10/10 kill-checks discriminate (2 were vacuous and were fixed);
12 mutants applied, 12 killed (4 needed test strengthening).
Full suite 3447p/8f — env-caused failures only, +45 tests, no regressions.

**Traces-to:** G7, G8, G10 · **Depends-on:** S1, S2, S4b, S5 · **Liveness:** L0→L3

```text
EDIT PACKET E7 / S7   (v2 — v1's steps 2, 6, 7 were unexecutable)

Allowed files:
  src/fa/inner_loop/routing.py            (NEW)
  src/fa/cli.py                           (EDIT — split + gate + warning)
  src/fa/inner_loop/runtime_limits.py     (EDIT — one bool key)
  src/fa/inner_loop/coder_loop.py         (EDIT — tripwire in the turn loop)
  tests/test_chat_escalation_gate.py      (NEW)
  tests/test_scope_tripwire.py            (NEW)

Step 1 — routing.py (NEW, pure, no imports from fa.cli):
  GATE_MIN_CONFIDENCE: Final = 0.8
  TRIPWIRE_READ_LIMIT: Final = 10
  TRIPWIRE_CHANGE_LIMIT: Final = 3
  Each constant carries the measurement that justifies it in a comment
  (0.8 -> 4/4; 0.6 -> 3/5; 0.3 -> 2/6, 15 tasks, 2026-08-27).
  def should_withhold_write_tools(point, *, role, gate_enabled) -> bool   # CT8
  def check_scope_tripwire(*, reads, changes, mode) -> str | None         # CT10
      Returns the observation sentence, or None. PURE — the caller owns the
      latch and the append, so the predicate stays unit-testable.
  Both names in __all__ (FA-AUTHORING-V2-EXPORTS-COMPLETENESS).
  Import OperatingPoint under TYPE_CHECKING to avoid an import cycle.

Step 2 — cli.py, THE ORDERING SPLIT (CT8b). Read CT8b before editing.
  Do NOT "hoist _estimate_scope_for_chat" (v1's instruction): it takes `state`,
  constructed at cli.py:1993, which is AFTER the registry at 1923.
  a. Split cli.py:1718-1795 into _resolve_scope_point (pure) and
     _publish_scope_estimate (all side effects, unchanged order).
  b. Call _resolve_scope_point(role, args.task or "") once, before line ~1923.
  c. At today's line 2010, call _publish_scope_estimate(point, ...) and keep
     assigning the hint to `scope_hint` for drive_session(turn_context=...).
  d. estimate_scope must be evaluated EXACTLY ONCE per run (T40).

Step 3 — thread the point into the registry builder:
  _build_run_tool_registry gains keyword-only `scope_point: OperatingPoint |
  None = None`. Defaulted, so the second call site (cli.py:2496,
  _run_live_conformance) and tests/_chat_registry_fixture.py keep working
  unchanged. Verify both after editing.

Step 4 — the gate, inside the builder:
  When should_withhold_write_tools(...) is True, skip registering
  fs_write_file, fs_edit_file, fs_spawn_subagent. Emit ONE WARNING naming the
  reason and the config key, so an operator can tell a gate from a bug.
  invoke_workflow MUST still be registered.

Step 5 — runtime_limits: add `chat_escalation_gate`, default True.
  Three edits, all required: the dataclass field, _KNOWN_KEYS
  (runtime_limits.py:208), AND the constructor call in the loader — the loader
  enumerates every field, so adding the field alone silently does nothing
  (recorded trap). This is the FIRST bool key: every existing key is int/float,
  so the parser has no bool branch. Accept true/false/1/0 case-insensitively;
  warn-and-default on anything else (RK-A). Read the parsed value back in the
  test rather than trusting the write.

Step 6 — coder_loop tripwire (CT10). The mechanism v1 got wrong:
  Inject via `turn_context`, NOT state.observations (which nothing reads).
  Inside `while turn < max_turns` (coder_loop.py:655), before the request is
  composed, read len(state.transaction.read_set) / .write_set — these are
  already maintained by record_tool_call (state.py:739-748); build no new
  counter. On the first crossing, append the sentence to `turn_context` (it is
  a never-reassigned local read as a closure free variable at :749 — rebind it
  with the right scope) and append a `scope_tripwire` event. Latch so it fires
  once. If state.transaction is None, do nothing — telemetry must never raise.

Do-not:
  - Gate any role other than chat, or below 0.8 confidence.
  - Claim the gate makes writes impossible — fs_run_bash remains (CT9).
  - Mutate the registry mid-session.
  - Hard-stop or auto-invoke on tripwire (Q21).
  - Route tripwire text through system_prompt_extra (D7) or state.observations
    (dead channel).
  - Repeat the observation every turn.

Exit criteria (binary):
  - [ ] chat + workflow_linear + conf>=0.8 + gate on -> registry has exactly 10
        tools; fs_write_file, fs_edit_file, fs_spawn_subagent all absent
  - [ ] invoke_workflow present in every gated case
  - [ ] conf 0.6 -> 13 tools; chat_direct + conf 0.8 -> 13; gate off -> 13;
        role=coder -> ungated; no estimate -> 13 (fail-open)
  - [ ] exactly ONE scope_estimate event per run after the split (T40)
  - [ ] non-chat role / empty task: observable output byte-identical to pre-split
  - [ ] cli.py:2496 and _chat_registry_fixture.py still work unchanged
  - [ ] tripwire text appears in the NEXT composed request (not just appended)
  - [ ] fires once at 11 distinct reads; not again at turn 12
  - [ ] `scope_tripwire` event row written
  - [ ] state.transaction is None -> no exception
  - [ ] full suite: no new failures vs 3403p/7f

Kill-checks (each must be shown to discriminate):
  - remove the write-tool skip        -> T20 fails
  - GATE_MIN_CONFIDENCE 0.8 -> 0.0    -> T21 fails
  - remove the WARNING emit           -> T22 fails
  - ignore the config toggle          -> T23 fails
  - remove the turn_context append    -> T25 fails
  - remove the latch                  -> T27 fails
  - TRIPWIRE_READ_LIMIT -> 999        -> T25 fails
  - second estimate_scope call        -> T40 fails

Test class: C1 (real registry + real composed request) + C0 (pure predicates)
Oracle: exact tool-name SET (not count alone); exact substring in the composed
        request body; event row presence; parsed config value
```

### S8 — Full E3 cost model + calibration (Layer 3)

**Traces-to:** G9 · **Depends-on:** S5, S7 · **Target liveness:** L0→L3

```text
EDIT PACKET E8 / S8

Allowed files:
  src/fa/inner_loop/acrr.py               (EDIT)
  src/fa/inner_loop/global_history.py     (EDIT)
  src/fa/cli.py                           (EDIT — calibration view only)
  tests/test_e3_cost_model.py             (NEW)
  tests/test_acrr.py                      (EDIT — rename fallout)

Do:
  1. acrr.py: CostWeights frozen dataclass; compute_cost per Eq. 1;
     compute_cost_floor(changed_paths, workspace, output_tokens); compute_acrr.
     Keep compute_acrr_proxy, RENAMED compute_read_amplification.
  2. FIRST, fix the data gap v1 missed: _extract_telemetry_from_log
     (global_history.py:288) currently DISCARDS the paths — it returns only
     len(read_paths) / len(changed_paths) (global_history.py:372-373). The floor
     needs the paths themselves to stat file sizes. Add `changed_paths` (a
     SORTED list, for determinism) to the returned telemetry dict. Keep
     files_changed as-is; do not change its meaning.
  3. Floor derivation, stated honestly in the docstring: file axis = count of
     distinct changed paths; token axis = their on-disk byte size / 4 + the
     run's output tokens; tool axis = 2 per changed file + 1 verify; latency
     EXCLUDED (E3 §7.7 does the same to keep the floor deterministic).
     PATH RESOLUTION: recorded params come from the tool call, and read_file
     resolves via resolve_workspace_path(root, ...) — so a recorded path may be
     absolute OR workspace-relative. Resolve each against `workspace_root`
     (build_export_row already receives it, global_history.py:385) and, if the
     result is missing or outside the workspace, contribute 0 tokens. Never
     raise, never stat outside the root.
  4. Fit the four weights against real global_history rows; record the
     derivation as a comment and carry it into ADR-16. Configurable.
  5. global_history: rename acrr_proxy -> read_amplification (free — 0
     occurrences on main); add cost_actual, cost_floor, acrr. PRAGMA-guarded
     ALTER, reusing the S5 block verbatim.
  6. build_export_row populates all four. acrr computed for EVERY run
     (operator decision Q22: recorded always, filtered at display).
  7. Blackboard: write the routing outcome (recommended_mode, read_amplification,
     acrr) mirroring the S3.5 scope_estimate precedent — operator asked for
     blackboard observability, not just db.
  8. `fa stats --calibration`: realized ACRR grouped by recommended_mode — the
     E3 §7.4b estimator-calibration table. Successful runs only, with the
     paper's reason quoted at the call site ("a cheap failure is not an
     efficiency"). Respect the S10b stream split: json->stdout, human->stderr.

Do-not:
  - Clamp negative ACRR (it means the floor model is wrong — a real signal).
  - Adopt the paper's weights unmodified (measured: erases the file axis here).
  - Claim this is oracle ACRR. It is SELF-REFERENTIAL: the floor comes from the
    run's own change-set, so a run that changed the WRONG files scores well.
    ACRR measures redundancy, never correctness. Say so in ADR-16 verbatim.
  - Read EventLog from the stats renderer (S5 constraint holds).

Exit criteria (binary):
  - [ ] compute_cost matches a hand-computed Eq. 1 value exactly
  - [ ] ACRR == 0.0 when actual == floor
  - [ ] floor excludes latency (changing latency does not move the floor)
  - [ ] changed-0-files run -> acrr NULL, not 0.0
  - [ ] deleted changed path -> no crash, contributes 0
  - [ ] absolute AND relative recorded paths both resolve against workspace_root
  - [ ] a path outside the workspace contributes 0 and is not statted
  - [ ] pre-S8 DB gains 3 columns; insert succeeds
  - [ ] failed run: acrr stored but absent from display
  - [ ] --calibration groups by recommended_mode
  - [ ] blackboard carries the routing outcome
  - [ ] no `acrr_proxy` identifier remains anywhere

Kill-checks:
  - drop the δ·N_file term        -> T31 fails
  - clamp acrr at 0               -> T36 fails
  - drop the migration            -> T33 fails
  - include latency in the floor  -> T37 fails
  - show failed runs in stats     -> T34 fails

Test class: C0 (cost arithmetic) + C1 (real sqlite, real export path)
Oracle: exact floats; exact column values; exact grouping
```

### S9 — Live verification sheet

**Traces-to:** G7-G10 · **Depends-on:** S7, S8 · **Target liveness:** L3 evidence

```text
EDIT PACKET E9 / S9

Allowed files:
  worklogs/reviews/S9-LIVE-VERIFICATION-2026-08-27.md   (NEW)

Do:
  1. Execute each row against the REAL CLI and paste actual output — same
     discipline as the prior implementation reports (measured values, not
     expected ones).
  2. Rows: gate fires · gate respects confidence · toggle off · coder ungated ·
     tripwire fires once · tripwire silent under threshold · escalation still
     reachable while gated · ACRR on a real run · calibration view · pre-S8 DB
     migration · full-suite delta.
  3. Re-measure estimator accuracy on the same 15 tasks and record it as the
     BASELINE the calibration view will supersede. Note explicitly that these
     are author-written tasks, not a labelled corpus.
  4. Record any row that fails as a defect with a D#, do not quietly fix.

Do-not:
  - Paste expected output. Every value must come from an executed command.

Exit criteria:
  - [ ] every row has real pasted output
  - [ ] full-suite delta stated against 3403p/7f
  - [ ] failures (if any) recorded as D# with disposition
```

---

## 6. Verification plan

| T# | Class | Claim | Oracle | Kill-check | S# |
|---|---|---|---|---|---|
| T20 | C1 | high-conf workflow_linear chat registry lacks write tools | tool-name set | remove skip | S7 |
| T21 | C1 | conf 0.6 / chat_direct / no-estimate keep write tools | tool-name set | GATE_MIN_CONFIDENCE=0.0 | S7 |
| T22 | C1 | gating emits an operator WARNING naming the toggle | log record | remove emit | S7 |
| T23 | C1 | `chat_escalation_gate: false` disables the gate | tool-name set | ignore toggle | S7 |
| T24 | C0p | non-chat roles never gated | predicate over roles | drop role check | S7 |
| T25 | C1 | tripwire appends one observation at the read limit | observations content | remove append | S7 |
| T26 | C1 | tripwire text reaches the **composed request body** | substring in request | stop passing turn_context | S7 |
| T27 | C1 | tripwire latches — fires at most once | append count == 1 | remove latch | S7 |
| T28 | C1 | under threshold -> no observation | observations empty | invert compare | S7 |
| T29 | C1 | run continues after tripwire (advisory) | exit code unchanged | hard-stop instead | S7 |
| T40 | C1 | exactly ONE scope_estimate event after the split | event count == 1 | add a 2nd estimate call | S7 |
| T41 | C1 | non-chat/empty task: output identical to pre-split | event+return equality | reorder side effects | S7 |
| T42 | C0p | tripwire no-ops when transaction is None | no exception | drop the guard | S7 |
| T30 | C0 | compute_cost == hand-computed Eq. 1 | exact float | drop an axis | S8 |
| T31 | C0 | file axis materially affects C | exact float | drop δ term | S8 |
| T32 | C1 | 0 changed files -> acrr NULL | column is NULL | default 0.0 | S8 |
| T33 | C1 | pre-S8 DB migrates | PRAGMA + insert | drop migration | S8 |
| T34 | C1 | failed runs stored but not displayed | stderr absence | show failures | S8 |
| T35 | C0p | deleted changed path -> 0 tokens, no raise | no exception | strict stat | S8 |
| T43 | C1 | changed_paths survive telemetry -> build_export_row | list present, sorted | return counts only | S8 |
| T44 | C0p | abs + relative paths resolve; outside-root -> 0 | exact floor | resolve naively | S8 |
| T36 | C0 | negative ACRR preserved | exact float | clamp at 0 | S8 |
| T37 | C0 | floor independent of latency | equal floors | include latency | S8 |
| T38 | C1 | blackboard carries routing outcome | blackboard entry | remove write | S8 |
| T39 | C1 | --calibration groups by recommended_mode | grouped rows | flatten | S8 |

### LIVE-PATH PROOF

```
root: fa.cli._cmd_run (real CLI) + coder_loop.drive_session (real turn loop)
matrix: M10 gate-on, M11 gate-off, M12 no-estimate
paths-covered: P30-P43 (14/14)
producer targets: should_withhold_write_tools, _build_run_tool_registry skip,
                  check_scope_tripwire, compute_cost, compute_cost_floor,
                  the PRAGMA migration, the calibration renderer
pyramid: A (deterministic); C4 mutation after S7 and after S8
```

---

## 7. Risks, rollback, open questions

| RK# | Risk | Mitigation |
|---|---|---|
| RK-A | `chat_escalation_gate` is the FIRST bool key in runtime_limits; the parser is int/float-shaped | Implement bool parsing explicitly; warn-and-default on unparseable; T23 covers it. Verify the loader constructor enumerates the new field — adding it to the dataclass alone is a known trap. |
| RK-B | The scope-estimate SPLIT (CT8b) could double-emit `scope_estimate` and corrupt the S3.5 projection, which keeps the last one silently (global_history.py:346) | T40 asserts exactly one event per run; T41 pins pre-split equivalence for the non-chat/empty paths |
| RK-C | Gate withholds writes on a task that genuinely needed a one-line edit | Only the 0.8 bucket (4/4 measured); `invoke_workflow` always remains; operator toggle; WARNING names the toggle |
| RK-D | Tripwire text nudges the model into escalating trivially | Fires once, phrased as an observation not an instruction; P38 asserts the run may ignore it |
| RK-E | Self-referential floor flatters a run that changed the wrong files | Documented in CT11 and ADR-16 in plain words; ACRR is gated to successful runs at display |
| RK-F | Fitted weights drift as usage changes | Weights configurable; derivation recorded; §7.5 shows ordering is weight-insensitive |
| RK-G | **The gate is evadable.** `fs_run_bash` stays in the gated corpus and `echo x > f.py` / `sed -i` still write (verified). Withholding the three write tools is a strong nudge, not a capability bound. | ACCEPTED, not mitigated, and stated plainly in CT9 + ADR-16. The mechanism to close it exists — `SandboxHook(allow_general_write=False)` (builtin.py:101, seam at cli.py:1544) — but it also denies `pytest -q` (same `general_write` category, verified), which would break the chat role's ability to verify anything. **PRECEDENT — this repo already tried it and reverted it:** Q19 option (a) denied general-write for spawns and was "measured to deny 8/10 realistic verifier commands (pytest, mypy, make test), so it was reverted" (tests/test_s5_isolation_boundary.py:447-449). The same finding concluded that real containment needs an OS-level writable-mount boundary (Q19 option (c)), and `test_subagent_write_outside_artifact_root_denied` is the standing xfail recording that gap. So RK-G is not a new question: it is the SAME unsolved boundary, and S7 must not re-litigate it. Deferred, with the xfail as the tracking marker. |
| RK-H | `turn_context` is currently a never-reassigned local; rebinding it inside the loop is a new mutation pattern and could collide with the S3 scope hint already occupying it | The tripwire APPENDS to the existing value, never replaces it. T26 asserts both the S3 hint and the tripwire sentence are present together. |

**Rollback:** S7 — set `chat_escalation_gate: false` (no deploy). Code revert
leaves no residue: routing.py is new, the cli change is one conditional.
S8 — reverting leaves the three columns in place; older readers select by name
and ignore them. No down-migration needed.

| Q# | Question | Resolution |
|---|---|---|
| Q20 | Hard gate vs tripwire-only, given Q1 unrestricted writes? | **RESOLVED (operator, 2026-08-27): hard gate, toggleable via config.** Narrow to the 100%-accuracy bucket. |
| Q21 | Tripwire: inject / hard-stop / auto-invoke? | **RESOLVED: inject-and-continue.** Auto-invoke rejected — no rollback from a half-edited tree. |
| Q22 | Labelled estimator test set? | **RESOLVED: no.** Layer 3 calibration supplies the evidence instead; must be observable in blackboard + db. |
| Q23 | Sequencing? | **RESOLVED: S7 → S8 → S9 → S6.** |

---

## 8. Research-note disposition

| RN# | Claim | Disposition |
|---|---|---|
| RN10 | E3 ACRR = `(C_act − C_min)/C_min`, 4 weighted axes | **ACCEPT** — CT11 |
| RN11 | Paper defaults α=1.0 β=0.02 γ=0.5 δ=1.5 | **REWRITE** — measured: erases the file axis at our token scale |
| RN12 | ACRR is successful-runs-only | **ACCEPT with amendment** — store always, display gated (operator Q22) |
| RN13 | E3 Expand fires on verification failure | **ACCEPT, adapted** — our trigger is a file-count threshold; we have no per-turn verifier |
| RN14 | Prior doc: chat is read-only with 6 tools | **REJECT** — stale; live profile has 13 incl. write tools |
| RN15 | Prior doc: prompt says "do NOT attempt directly" | **REJECT** — live prompt is judgment-based and better; S7 adds determinism in code, not prose |
| RN16 | Prior doc: "file axis is highest-signal single axis" | **PARTIALLY REJECT** — true for the paper's scale; at ours tokens dominate unless reweighted |
| RN17 | Manus: never mutate the tool set mid-session | **ACCEPT** — CT9 decides the corpus once at build time |

---

## 9. Definition of Done

- [ ] S7, S8 at L3 with every kill-check verified to discriminate
- [ ] S9 sheet complete with pasted real output
- [ ] ruff check + format, mypy, 4 contract scripts green on changed files
- [ ] full suite: no new failures vs 3403p/7f baseline
- [ ] mutation pass after S7 and after S8; survivors killed or ruled equivalent
- [ ] no `acrr_proxy` identifier remains
- [ ] ADR-16 (S6) records: the gate + threshold with its measurement, the
      tripwire, the fitted weights with derivation, and the self-referential
      caveat in plain words

## 10. READY gate

No blocking Q#. All four operator decisions recorded (Q20–Q23).

Every load-bearing claim in this revision was verified against source or by
execution, with file:line evidence in the preflight log. The v1 claims that
were WRONG are named there explicitly rather than quietly deleted, because the
same mistakes are easy to re-make: the two plausible-but-dead channels
(`state.observations`, the composer's `observations` param) are still sitting
in the code looking usable, and an implementer who skims will reach for them.

One deliberate non-mitigation is recorded: **RK-G**, the `fs_run_bash` bypass.
S7 ships a strong nudge, not a capability bound, and CT9 says so. Closing it
costs the chat role `pytest`; that tradeoff is the operator's to make, in its
own slice, with its own evidence.

**READY.**
