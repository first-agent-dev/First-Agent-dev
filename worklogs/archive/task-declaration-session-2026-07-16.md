# Task Declaration — Authoring Hardening Session 2026-07-16

**Branch:** main @ 8f3b35d (cloned)
**Parent plan:** `knowledge/research/authoring-hardening-workplan-v2-2026-07-16.md`
**Re-inventory:** `uploads/authoring-hardening-reinventory-2026-07-16.md`

---

## Subtask A — CI always-run / `paths:` structured checker (HR2)

### Intent

Agents (human or LLM) keep cargo-culting `grep -q "paths:" .github/workflows/authoring-guardrails.yml` to "verify" CI always-runs.
This is a **false oracle** because YAML comments mentioning `paths:` (like `# no paths: filter`) trigger the grep, producing a false FAIL.
The re-inventory explicitly identified this gap. We need a **deterministic structured checker** (Python script) that parses YAML properly,
ignoring comments, and asserts no `paths:` or `paths-ignore:` key exists at the `on:` trigger level. This is docs/script-only, not a CI product gap.

Additionally, a workplan note should be written so that future agents read it and use the proper script instead of naive grep.

### Translation to code (senior engineer in production)

1. **Create `scripts/check_workflow_no_path_filter.py`** — a ~60-line stdlib-only Python script:
   - Takes workflow file paths as args (default: all `.github/workflows/*.yml`)
   - Parses YAML using `yaml.safe_load` (already a dependency)
   - Walks the `on:` trigger section, checks for `paths:` / `paths-ignore:` keys
   - Exits 0 if no path filters found, exits 1 with diagnostic if found
   - Output is structured (JSON with `--output json`) for CI consumption
   - Comments are naturally ignored by YAML parser — this is the whole point

2. **Write a regression test** `tests/test_workflow_no_path_filter.py`:
   - C2 test: runs the checker script on the actual workflow files
   - Kill-check: temporarily inject a `paths:` key, assert test fails
   - Also tests against a synthetic YAML fixture with `# paths: in comment` to prove comment-insensitivity

3. **Update workplan note** in re-inventory or a short `knowledge/ci-guardrails-reference.md` addendum
   documenting that agents MUST use `scripts/check_workflow_no_path_filter.py` instead of `grep "paths:"`.

### Verification against intent

- `python scripts/check_workflow_no_path_filter.py .github/workflows/authoring-guardrails.yml` exits 0 (no path filters)
- `python scripts/check_workflow_no_path_filter.py .github/workflows/authoring-guardrails.yml --output json` outputs valid JSON with `{"has_path_filter": false, ...}`
- Test with a YAML file containing `# paths: filter` comment — exits 0 (comment ignored)
- Test with a YAML file containing actual `paths:` key — exits 1
- `pytest tests/test_workflow_no_path_filter.py -v` passes including kill-check
- Naive `grep -q "paths:" .github/workflows/authoring-guardrails.yml` would FAIL (there are comments mentioning paths), proving the script is strictly better

---

## Subtask B — Task 2: Import `tests.fixtures.session_wiring` from pr1–5 / slice / global_history tests

### Intent

The shared fixture module `tests/fixtures/session_wiring.py` already exists with canonical helpers:
- `require_log` — narrow Optional log
- `mock_success_response` — create success ResponseInfo tuple
- `mock_response_with_tools` — create tool_calls ResponseInfo tuple
- `make_tool_call` — create tool call dict
- `make_mock_chain` — create mock ProviderChain with ChainConfig
- `make_session_state` — create SessionState with EventLog

But **0 test files** import from it. Instead, 8 modules define their own local copies:
- `test_pr1_wiring.py` — `_require_log`, `_mock_success_response`
- `test_pr2_wiring.py` — `_require_log`, `_mock_success_response`, `_mock_tool_call_response` (unique)
- `test_pr3_wiring.py` — `_require_log`, `_mock_success_response`
- `test_pr4_wiring.py` — `_require_log`, `_mock_success_response`, `_mock_tool_call_response` (unique)
- `test_pr5_wiring.py` — `_require_log`, `_mock_success_response`
- `test_global_history_export.py` — `_require_log`, `_mock_success_response`, `_mock_response_with_tools`, `_make_tool_call`
- `test_slice5_6_7_wiring.py` — `_require_log`, `_mock_success_response`, `_mock_response_with_tools`, `_make_tool_call`

Goal: refactor all 7 test files to import from `tests.fixtures.session_wiring` instead of defining local copies.
Done criterion from v2: **≤2 local copies** of same helper (ideally 0, but `make_mock_chain`/`make_session_state` not yet used locally).

### Translation to code (senior engineer in production)

**Step 1: Upgrade session_wiring.py if needed**
- The local `_mock_success_response` in pr1–5 uses `in_tokens=1000, out_tokens=100` (1000/100)
- The fixture uses `in_tokens=100, out_tokens=10` (100/10)
- The local in global_history uses `in_tokens=0, out_tokens=0` (0/0)
- These are **functionally equivalent** for the tests — the token values are never asserted on
- Solution: keep the fixture's existing signature with defaults, let callers override if they truly need specific token counts
- The fixture's `make_mock_chain` is NOT used by any test yet, but we can wire it up where appropriate

**Step 2: Add `mock_tool_call_response` to session_wiring.py**
- pr2 and pr4 define a unique `_mock_tool_call_response` that is a convenience wrapper
- Add this to session_wiring.py so pr2 and pr4 can import it too

**Step 3: Refactor each test file — one at a time, verify after each**
- Remove local `_require_log`, `_mock_success_response`, etc. definitions
- Add `from tests.fixtures.session_wiring import require_log, mock_success_response, ...`
- Rename all `_require_log(...)` → `require_log(...)` calls
- Rename all `_mock_success_response(...)` → `mock_success_response(...)` calls
- Rename all `_mock_response_with_tools(...)` → `mock_response_with_tools(...)` calls
- Rename all `_make_tool_call(...)` → `make_tool_call(...)` calls
- For `_mock_tool_call_response` → `mock_tool_call_response`
- Remove now-unused imports (if any became unused after refactor)

**Step 4: Verify**
- After each file refactor, run that specific test file and confirm all tests pass
- After all refactored, run the full suite of the 7 files
- Final verification: `grep -rn "def _require_log\|def _mock_success_response\|def _mock_response_with_tools\|def _make_tool_call" tests/*.py` must return 0 results (or ≤2 for legitimate exceptions)

### Verification against intent and development guidelines

1. **No local duplicates**: `grep -rn "def _require_log\|def _mock_success_response\|def _mock_response_with_tools\|def _make_tool_call" tests/*.py` returns 0 matches
2. **All imports from fixture**: `grep -rn "from tests.fixtures.session_wiring import" tests/test_pr*_wiring.py tests/test_global_history_export.py tests/test_slice5_6_7_wiring.py` returns ≥7 matches
3. **All 32 tests still pass**: `pytest tests/test_pr1_wiring.py tests/test_pr2_wiring.py tests/test_pr3_wiring.py tests/test_pr4_wiring.py tests/test_pr5_wiring.py tests/test_global_history_export.py tests/test_slice5_6_7_wiring.py -v` — 32 passed
4. **Type honesty**: `python -c "from tests.fixtures.session_wiring import require_log, mock_success_response, mock_response_with_tools, make_tool_call, make_mock_chain, make_session_state"` succeeds
5. **No behavioral change**: Tests produce identical results before and after refactor (same assertions, same logic)
6. **Per tests-writing skill**: fixture module remains "thin factories for composition-root wiring tests" — no test logic in the fixture

---

## Execution order

1. Subtask A (checker script + test + doc note) — independent, can be done first
2. Subtask B (fixture extraction) — 7 files, done one at a time with per-file verification

Both follow the declared workflow: declare intent → translate to code → verify against intent.
