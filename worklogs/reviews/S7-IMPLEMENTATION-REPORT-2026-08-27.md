# S7 Implementation Report — Deterministic Escalation (Layers 1 + 2)

**Date:** 2026-08-27
**Commits:** `3b8c241` (implementation) · `f4a98eb` (mutation hardening)
**Plan:** `worklogs/implementation-plans/PLAN-ADDENDUM-deterministic-routing-S7-S9.md`
**Status:** ✅ COMPLETE — all exit criteria met, all kill-checks discriminate

---

## 1. What shipped

| Layer | Mechanism | Site |
|---|---|---|
| **L1 — capability gate (CT8/CT9)** | `workflow_linear` ∧ `confidence >= 0.8` ∧ toggle on → chat corpus built WITHOUT `fs_write_file`, `fs_edit_file`, `fs_spawn_subagent` | `cli.py::_apply_escalation_gate` |
| **L2 — scope tripwire (CT10)** | Latched, once per run: >10 distinct reads or >3 distinct changes on a chat-sized estimate → one observation naming `invoke_workflow` appended to `turn_context` | `coder_loop.py` turn loop |
| **Config (GAP10)** | `runtime_limits.chat_escalation_gate`, default `true` | `runtime_limits.py` |
| **CT8b — ordering split** | `_resolve_scope_point` (pure, pre-registry) + `_publish_scope_estimate` (side effects, post-`SessionState`) | `cli.py` |

**Measured behaviour:** gated chat corpus is **13 → 10 tools**; `invoke_workflow` always survives.

---

## 2. Why the gate binds only the 0.8 bucket

| Confidence | Correct | Accuracy |
|---|---|---|
| 0.8 | 4/4 | **100%** |
| 0.6 | 3/5 | 60% |
| 0.3 | 2/6 | 33% |

15 realistic tasks, **zero over-scopes**, six under-scopes. Gating a lower
bucket would withhold write tools from tasks that need them. The "don't
interfere when simple" half of the requirement needed **no code** — zero
over-scopes means the simple path was never at risk.

---

## 3. Plan defects found during implementation

The plan was audited before this slice, and implementation still surfaced two
things the audit missed. Both were caught by tooling, not by inspection.

**D-S7-1 — `turn_context` became a loop variable (ruff B023).**
Appending to `turn_context` inside the turn loop made the composer closure a
late-binding hazard. Fixed by binding it as a default argument
(`turn_context_value: str = turn_context`), matching the two values already
beside it (`base_system_value`, `pinned_text_value`). Verified by probe that
the default re-binds each turn, so propagation still works.

**D-S7-2 — `scope_tripwire` needed a `LogKind` decision.**
mypy rejected the new `kind=` immediately (closed `Literal`), and two repo
guards then required an explicit classification. Recorded in `UNPARSED_KINDS`
with its reason — its consumer is the S8 calibration view, which reads the
`global_history` projection, not per-session analytics.

---

## 4. Verification

### Kill-checks — 10/10 discriminate

| # | Mutation | Result |
|---|---|---|
| KC1 | remove the gate call | 3 fail |
| KC2 | `GATE_MIN_CONFIDENCE` → 0.0 | 3 fail |
| KC3 | ignore `gate_enabled` | 1 fail |
| KC4 | drop the `role != "chat"` guard | 4 fail |
| KC5 | remove the `turn_context` append | 2 fail |
| KC6 | remove the latch | 1 fail ← **was vacuous, fixed** |
| KC7 | `TRIPWIRE_READ_LIMIT` → 999 | 1 fail ← **was vacuous, fixed** |
| KC8 | remove the WARNING | 1 fail |
| KC9 | drop the `transaction is None` guard | 1 fail |
| KC10 | drop the `log.append` producer | 2 fail |

**Two kill-checks passed on first run and were fixed, not accepted:**

- **KC6** — the latch test passed `max_turns=3`, but a text-only mock ends the
  loop after turn 1, so it never tested a second turn. Fixed by scripting tool
  calls per turn and asserting `chain.request.call_count >= 2`.
- **KC7** — every threshold test derived its input from the constant
  (`TRIPWIRE_READ_LIMIT + 1`), so widening the limit to 999 left the file
  green. Fixed with literal anchor tests.

### Mutation testing — 12 applied, 12 killed

Four survivors required test strengthening:

| # | Mutant | Why it survived | Fix |
|---|---|---|---|
| M7 | drop `fs_edit_file` from the withheld set | assertions written in terms of that set shrank with it | literal set anchor |
| M8 | hardcode `role="chat"` at the gate call | tests build registries directly, never exercise `_cmd_run` plumbing | C2 AST test |
| M9 | constant `scope_mode` | same | C2 AST test |
| M10 | replace `turn_context` instead of appending | RK-H test asserted on words the tripwire text also contains | unique sentinel |

M8 is the one that mattered most: it would have gated **coder and eval** runs.

One false survivor (M10, first attempt) came from my own shell-escaping error —
the mutation never applied. Re-run correctly, it was a genuine survivor.

### Gates

```
ruff check + format ........ PASS (7 files)
mypy ....................... PASS (6 src files)
check_log_kind_contract .... PASS
check_producer_consumer .... PASS
check_dead_flags ........... PASS
check_no_mocked_dataclasses  PASS
authoring __all__ gate ..... exit 0, 0 diagnostics
full suite ................. 3447 passed / 8 failed
```

The 8 failures are the unchanged env-caused set (`pyrefly`, `semgrep`,
`vulture` absent). **+45 tests, zero regressions.**

Complexity was held without a waiver: the bool-parse branch pushed
`load_runtime_limits` to 17 (ceiling 15), so it was extracted to
`_accept_bool_key` rather than suppressed.

---

## 5. Scope of the guarantee — stated plainly

Layer 1 removes the **declared** write affordances. It does **not** make writes
impossible: `fs_run_bash` remains in the corpus and `echo x > f.py` still works.

The honest claim is *"the model is not handed a write tool and must either
escalate or go out of its way"* — not *"writes are prevented"*.

Closing that path means `allow_general_write=False`, which **this repo already
tried and reverted**: it denied 8/10 realistic verifier commands including
`pytest` and `mypy` (Q19; standing xfail in
`tests/test_s5_isolation_boundary.py`). RK-G is therefore the same unsolved
boundary as Q19, not a new question, and S7 does not re-litigate it.

---

## 6. New policy choices promoted

**None.** Every decision this slice needed was already settled as Q20–Q23. The
one judgment call — where to put `scope_tripwire` in the `LogKind` taxonomy —
follows directly from the plan's S8 sequencing and is recorded in-code with
its reason and its reversal condition.

---

## 7. Files changed

| File | Change |
|---|---|
| `src/fa/inner_loop/routing.py` | **NEW** — `should_withhold_write_tools`, `check_scope_tripwire`, 3 calibrated constants |
| `src/fa/cli.py` | CT8b split; `_apply_escalation_gate`; gate + `scope_mode` wiring |
| `src/fa/inner_loop/coder_loop.py` | `scope_mode` param; tripwire + latch; B023 default-arg binding; `_scope_tripwire_text` |
| `src/fa/inner_loop/runtime_limits.py` | `chat_escalation_gate` (first bool key); `_accept_bool_key`; `__all__` |
| `src/fa/output.py` | `scope_tripwire` LogKind |
| `src/fa/stats.py` | classify `scope_tripwire` as UNPARSED, with reason |
| `tests/test_chat_escalation_gate.py` | **NEW** — 25 tests |
| `tests/test_scope_tripwire.py` | **NEW** — 20 tests |
| `tests/test_s19_stats_parsers.py` | paired LogKind counts 35→36, 11→12 |

---

## 8. Next

**S8** — full E3 cost model + calibration. Its first task is the data gap this
plan already records: `_extract_telemetry_from_log` discards `changed_paths` at
its return boundary (`global_history.py:372-373`), so `compute_cost_floor`
cannot stat file sizes until those paths are threaded through.
