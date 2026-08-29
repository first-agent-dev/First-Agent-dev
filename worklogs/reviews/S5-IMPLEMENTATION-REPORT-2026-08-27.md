# S5 Implementation Report — ACRR Proxy + RK8 Role Allowlist

**Date:** 2026-08-27
**Branch:** `fa/20260826-cae-defect-fixes`
**Commits:** `44d4ef1` (implementation), `579ebc1` (mutation-driven test)
**Target liveness:** L0 → L3 · **Status: COMPLETE**

---

## What shipped

### 1. `compute_acrr_proxy` — NEW `src/fa/inner_loop/acrr.py`

Pure function, `(files_read, files_changed) -> float | None`. Per CT6:
`(5,5)→1.0`, `(20,2)→10.0`, `(10,0)→None`, `(0,0)→None`, negatives raise
`ValueError`.

The `None` return is the load-bearing decision. Dividing by
`max(files_changed, 1)` would make the metric's most pathological input — ten
files read, nothing changed, i.e. pure unproductive exploration — numerically
identical to a healthy run that read ten and changed one. The one condition
ACRR exists to surface would be the one it cannot express.

### 2. Distinct-path counting — `global_history.py`

Added to the **existing** `tool_call` branch of `_extract_telemetry_from_log`;
no second pass over the event log. Two `set[str]` accumulators keyed on the
`path` param that `state.py:record_tool_call` already records.

Sets, not counters: reading one file five times costs one file's worth of
context, and counting calls would report over-reading that never happened.

Tool groups are module-level constants beside the row they feed:
`_READ_TOOLS = {fs_read_file}`, `_CHANGE_TOOLS = {fs_write_file, fs_edit_file}`.

Malformed events (no content, no params, empty path) contribute nothing and
never raise — this is the export hot path, and one bad event must not destroy a
run's whole projection.

### 3. Schema + migration

`GlobalRunRow` gains `files_read`, `files_changed`, `acrr_proxy` (23 fields).
`build_export_row` computes the ratio at **export** time and stores it, because
the stats renderer reads only this projection and never reopens an event log.

The migration is the part that would have broken deployed installs.
`CREATE TABLE IF NOT EXISTS` is a no-op against an existing file, so a pre-S5 DB
would keep the old column set and every insert would fail with
`table runs has no column named files_read`. **Reproduced before writing the
fix.** Remediation reads `PRAGMA table_info(runs)` and issues
`ALTER TABLE runs ADD COLUMN` for whatever is missing — additive, idempotent,
safe on every open.

`acrr_proxy` is deliberately NULLable **with no DEFAULT**. `DEFAULT 0.0` would
claim every historical run had a perfect ratio; NULL is the storage form of the
same "no denominator" that the function expresses as `None`. `None` is
preserved through the insert rather than coerced (`float(None)` raises and
`float(0)` fabricates data).

### 4. Stats display — `_cmd_stats_global_history`

An additive second line per run. The original packet named `_cmd_stats`, which
**S10b.3 had already split into three renderers** — that line would have landed
in a function that never sees a global-history row (preflight finding P1).

Printed to **stderr**, matching the neighbour line. That renderer's stdout is
reserved for `--output json`; a stray human-readable line there would corrupt
the JSON contract that `test_s10b_stats_parity_global_history_*` pins.

Renders `ACRR proxy: 10.00 (files_read=20, files_changed=2)` or
`ACRR proxy: n/a (no files changed)`.

### 5. RK8 — workflow role allowlist (folded into S5, operator-approved)

**The live defect, confirmed by execution before the fix:**
`--roles planner,chat,eval`, `--roles chat`, `--roles bogus_role` and
`--roles researcher,coder` all parsed and ran. `cli.py` split `--roles` on
commas with no membership test, and `status_for_role()` silently returns
`'CODING'` for any unknown role, so nothing downstream ever objected.

`WORKFLOW_STAGE_ROLES: Final = frozenset({"planner", "coder", "eval"})` in
`workflow_controller.py`, exported via `__all__`, enforced in `_cmd_workflow`
immediately after the split and **before any run_id allocation**, so a rejected
invocation leaves no state on disk (pinned by a test).

An allowlist, not a `chat` denial: a denylist accepts every typo and every
future role by default, which is precisely why `bogus_role` ran. The constant is
derived from nothing — **not** from `PROFILES_RAW`, because this is a policy
statement about pipeline stages, not a restatement of which profiles exist.
`chat` is a real profile and must stay absent.

Why the CLI rather than a runtime guard: stages run in separate call frames with
their own registries, so S4b's thread-local re-entrancy guard cannot observe a
`chat` *stage* constructing its own `invoke_workflow`. Excluding `chat` at the
boundary is what makes that blind spot unreachable. This closes the second
recursion axis that `_make_workflow_ctx_provider`'s docstring already claimed.

### 6. T14, moved from S4b

A nested workflow gets its own `global_history` row, driven through the real
`invoke_workflow` handler with the real `run_stage_fn` seam. S4b marked this
covered, but its tests inject a fake `run_workflow`, so no row was ever written.
It is an S5 premise: ACRR is per-row, and a child reusing the parent's `run_id`
would collapse both under `INSERT OR REPLACE`, silently overwriting the parent's
file counts.

---

## Verification

| Gate | Result |
|---|---|
| `ruff check` (7 changed files) | ✅ All checks passed |
| `ruff format --check` | ✅ 7 files already formatted |
| `mypy` | ✅ no new errors (1 pre-existing `TransportResponse` attr-defined) |
| `pylint` R0801 (duplicate-code) | ✅ none |
| 4 contract scripts | ✅ all PASS |
| **Full suite** | **3403 passed / 7 failed** |

The 7 failures are the unchanged, environment-caused baseline set (missing
`semgrep`, `shellcheck`, `pyrefly`): `test_deploy_scripts`, `test_doc_links`,
`test_pyrefly_import_topology`, `test_semgrep_pin`×2, `test_slice_mutmut`,
`test_targeted_gates_smoke`. Zero new failures. Passing count 3371 → 3403 (+32).

### Tests added (32)

`tests/test_acrr.py` (22) · `tests/test_workflow_role_allowlist.py` (10) ·
`test_nested_workflow_produces_two_rows` in the existing global-history module.

### Kill-checks — all six discriminate

| Kill-check | Effect |
|---|---|
| revert zero case to `max(files_changed, 1)` | 3 fail |
| count calls instead of distinct paths | `test_files_read_is_distinct` fails |
| drop the PRAGMA migration | 2 fail |
| drop the ACRR stats line | 2 fail |
| delete the allowlist check | 5 fail |
| **add `chat` to the allowlist** | 3 fail — binds to the ROLE, not to the mere presence of a check |

### Mutation testing — 15 applied, 14 killed, 1 equivalent

Killed: inverted zero-guard, swapped numerator/denominator, dropped negative
guard, dropped `fs_edit_file`, `None`→`0.0` coercion, inverted allowlist,
`return 0` instead of `2`, first-role-only validation, forced `n/a`, stats line
to stdout, partial migration, `DEFAULT 0.0` column, hardcoded `None` ratio,
`files_changed` reading the wrong set.

**M4 — equivalent mutant.** Adding `fs_read_file` to `_CHANGE_TOOLS` is
unobservable: the inner branch tests `_READ_TOOLS` first, so a read can never
fall through to the change set.

**M5 — genuine survivor, fixed.** Dropping `fs_edit_file` from `_CHANGE_TOOLS`
left the suite green, because `test_write_and_edit_on_same_path` already counted
1 from the write alone. Added `test_edit_alone_counts_as_a_change` (`579ebc1`);
verified it fails under the mutant.

**M6 — false survivor.** Appeared to survive, but the sed target was stale after
`ruff format` joined the line; re-applied correctly, it kills 2 tests. (Same
trap as the M15 false survivor recorded during the D-pass — always verify the
mutant actually landed.)

### Two oracles strengthened

Mutation revealed `test_rk8_chat_alone_rejected` and
`test_rk8_unknown_role_rejected` passing **vacuously**: with the allowlist
deleted, those commands still exit 2 and still print the role name, because
workspace bootstrap fails later and echoes it. Both now assert the specific
`"unsupported stage role"` message. Deleting the check went from killing 3 tests
to killing 5.

---

## Plan corrections made during preflight

- **P1** — `_cmd_stats` → `_cmd_stats_global_history` (`cli.py:2805`), plus the
  stderr/stdout stream contract.
- **P2** — T14 moved S4b → S5 with the reason recorded.
- **P3** — ADR-16 already exists (276 lines, status `proposed`); S6 **edits** it
  rather than creating it. Four references corrected.

## Deferred, by design

Full E3 cost model `C(pi)`; EventLog reads from stats; any change to existing
stats output format. `status_for_role()`'s `'CODING'` default for unknown roles
is untouched — it has other callers and was explicitly out of RK8's scope fence.

## Next

**S6** — ADR-16 (edit, flip `proposed → accepted`, reconcile with what S1–S5
actually shipped), `knowledge/llms.txt`, `knowledge/instructions/02-operations.md`,
`AGENTS.md`, plus the carried task: revise `CHAT_SYSTEM_PROMPT` and the chat tool
set using the researched variant, per the standing instruction.
