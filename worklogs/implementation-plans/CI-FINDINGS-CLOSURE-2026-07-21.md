# CI-findings closure implementation plan

**Branch:** `guardrails+mistral-support`
**Baseline commit:** `db6fd88` (`full`)
**Date:** 2026-07-21
**Owner:** First-Agent maintenance session
**Status:** Baseline complete; closure work not yet started

## 0. Executive decision brief

The branch does not currently have a green CI-equivalent baseline. The first
blocking defect was pytest import-path configuration. A narrowly scoped fix was
applied in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
```

This is retained because it makes the repository's existing `tests.*` and
`scripts.*` namespace imports deterministic under `uv run just check`, without
adding package-marker files or changing test imports.

The remaining failures are not one bug. They are five separate closure tracks:

1. test infrastructure/import identity and optional dependency/type surface;
2. stale/dead feature-flag contract (`context_compaction_enabled`);
3. missing `.fa/dependency_contract.toml` and stale documentation links;
4. broken observability compaction/circuit-breaker live paths;
5. authoring export contract plus broad lint debt and coverage ratchet.

No blanket lint suppression, coverage-threshold reduction, test deletion, or
`continue-on-error` expansion is acceptable as closure.

## 1. Reproduction baseline

### Environment

- Python 3.13.13
- uv 0.11.30
- just 1.57.0
- `uv sync --frozen --extra dev`: PASS
- editable `fa` resolves to `src/fa`: PASS
- Docker, shellcheck, gitleaks, and semgrep are not installed in the local
  environment.

Use `uv run just ...` for CI-equivalent execution. Bare `just ...` can resolve
host tools instead of the project environment; in this environment bare
`just test` invoked a system pytest without pytest-cov.

### Commands and results

| Check | Result | Evidence |
|---|---:|---|
| `uv lock --locked` | PASS | lock resolves 77 packages |
| `uv run pytest --collect-only -q` | PASS after `pythonpath` fix | 1,793 tests collected |
| `uv run just test` | FAIL | 1,766 passed, 14 failed, 13 skipped; 76.80% coverage vs 86% gate |
| `uv run just lint` | FAIL | Ruff reports 366 before fix; 140 after mechanical fix |
| `uv run just typecheck` | FAIL | 8 mypy errors |
| `uv run just authoring-check` | FAIL | 5 HARD-BLOCK export diagnostics in `src/fa/stats.py` |
| `uv run just contract-check` | PASS | 14 EventTypes, 13 active producer contracts covered |
| `uv run just no-mocked-dataclasses` | PASS | no violations |
| `uv run pip-audit` | PASS with local-package skip | no known vulnerabilities |
| container smoke tests | NOT RUN | Docker unavailable locally |
| gitleaks | NOT RUN | binary/CI action unavailable locally |
| Semgrep | NOT RUN | binary/uvx scan not run in baseline |
| mutation | NOT RUN | advisory/slow; execute after C1 fixes |

## 2. Tests-writing contract for all closure work

This plan follows `knowledge/skills/tests-writing/SKILL.md`.

### Required proof levels

- **C0/C0p:** pure checker/parser/policy logic only.
- **C1:** default for product behavior; boot `drive_session` or the real
  composition root with mocked provider I/O and real registries/hooks/logs.
- **C2:** CLI-only behavior (`fa ...`) and exit-code/output contracts.
- **C3:** adversarial security boundary cases.
- **C4:** mutation follow-up after C1 behavior is green.

For every event/wiring change:

- enumerate every producer path and consumer handler;
- test both producer and consumer;
- target the producer emit call in the kill-check;
- assert structured events/outcomes/call counts rather than free text;
- verify dual writes (`EventLog` and `EventBus`) where the path requires both;
- cover relevant flag/provider matrices explicitly;
- assert early-stop provider call counts where a guard should stop work.

Every implementation PR must state `TEST-EDITS` for test changes and retain
real typed fixtures (`HookRegistry()`, real `EventLog`, tuple tool calls, real
config dataclasses). Do not use `MagicMock` for dataclass configuration.

## 3. Prioritized closure backlog

### P0-A — Make test and type import topology explicit

**Finding.** Before the fix, pytest collection failed with 21 import errors:
`tests.*` and `scripts.*` were not importable. After adding pytest
`pythonpath = ["."]`, pytest collection passes. Mypy still reports:

```text
Source file found twice under different module names:
"session_wiring" and "tests.fixtures.session_wiring"
```

**Implementation.** Keep the pytest `pythonpath` correction. Resolve mypy's
identity mismatch in one deliberate way, preferably by making the test helper
package explicit (`tests/fixtures/__init__.py`, and if needed `tests/__init__.py`)
and configuring mypy with `explicit_package_bases = true` or an equivalent
repository-root mapping. Do not solve this by excluding all tests from mypy.

**Tests-writing proof.** C0 configuration/infrastructure proof:

- `uv run pytest --collect-only -q` succeeds with no environment variables;
- `uv run mypy` no longer reports duplicate module identity;
- one small import smoke test may assert `tests.fixtures.session_wiring` and
  `scripts.check_dead_flags` resolve from the checkout, but do not add a
  redundant test if config-level verification covers it.

**DoD.** `uv run just typecheck` progresses past duplicate identity and all
fixture imports remain usable under pytest.

**Verification.**

```bash
uv run pytest --collect-only -q
uv run just typecheck
uv run just test
```

### P0-B — Restore required optional runtime/type dependencies

**Finding.** Mypy cannot find imports used by shipped modules:

- `fitz`, `pdfminer.high_level`, `pypdf` in `src/fa/inner_loop/tools/read_file.py`;
- `fastapi`, `pydantic` in `src/fa/runtime/server.py`;
- `fastjsonschema` has no usable stubs/`py.typed` marker under strict mypy.

The modules are in the source tree but their dependencies are absent from the
runtime/dev dependency contract.

**Implementation.** First determine intended product surface from imports,
README, Dockerfile, and tests. Then choose one of two explicit contracts per
module:

1. add the runtime dependencies (and lock them) if the module is shipped and
   imported by supported runtime paths; or
2. make the integration genuinely optional with a typed adapter boundary and
   deterministic operator-visible failure, while keeping the core import path
   valid.

For third-party packages without stubs, use a narrow, justified `ignore`
covering the actual error code or add a local typed protocol/stub boundary;
do not silence the whole module.

**Tests-writing proof.** C1/C2 for shipped paths, C0 for import adapters:

- PDF reader supported-format path and missing-backend path;
- runtime server import/CLI help smoke path if it is supported;
- adversarial malformed/unsupported input must fail closed and visibly;
- no API keys or live provider calls.

**DoD.** strict mypy passes these modules; supported runtime imports work in a
fresh `uv sync --frozen --extra dev` environment; lockfile and dependency
contract agree; tests assert structured error behavior.

### P0-C — Repair or remove the stale compaction flag contract

**Finding.** Dead-flag tests report `context_compaction_enabled` with zero
production references, while tests and logs still construct it. The checker
also expects 13 fields but sees 14 (the branch added `max_chain_retries`).

This is a real contract decision, not a test edit:

- `FeatureFlags.context_compaction_enabled` is documented as deprecated and
  code appears to derive behavior from `compaction_threshold`/other state;
- the current tests still pass it as if it controls the live path.

**Implementation.** Decide the single source of truth. Preferred direction:
remove the deprecated field only in a compatibility-conscious change if the
public/config surface allows it; otherwise retain it and add a real production
compatibility read that deterministically maps it to the new compaction policy,
then update the dead-flag inventory/count expectations to the actual schema.
Do not add a fake reference solely to satisfy the detector.

**Tests-writing proof.** C1 live-path flag matrix:

- A: budget on, compaction disabled/default;
- B: budget on, explicit legacy compatibility value enabled;
- C: `FeatureFlags()` defaults;
- compaction success, stage-3 residual pressure, and circuit-breaker paths;
- assert `context_warn`, `compaction_end`, stop reason, and provider
  `call_count` as applicable.

Add a C0 checker test only for the declared-field accounting. The product test
must boot `drive_session` and kill-check the producer event call.

**DoD.** dead-flag checker exits 0 for the intended public schema; no field is
counted as used only because a test constructs it; legacy behavior is either
removed and documented or proven on the live path.

### P0-D — Restore the dependency contract artifact

**Finding.** `scripts/check_dependency_contract.py` fails because
`.fa/dependency_contract.toml` is absent. Three tests fail from the same missing
contract file.

**Implementation.** Locate the intended contract source in history/docs (the
checker, `.fa` ignore rules, and `knowledge` references). Restore or generate
the contract as a tracked, deterministic artifact if it is part of the repo
contract. If `.fa` is intentionally runtime state, change the checker and tests
to consume a tracked contract path rather than silently requiring untracked
state. The artifact must list every core dependency and reject unknown
production dependencies.

**Tests-writing proof.** C0 checker tests:

- clean repository contract exits 0;
- unknown dependency is rejected;
- malformed/missing contract has an explicit diagnostic;
- parsed dependency set matches pyproject/lock according to the stated policy.

Use a temp checkout/file fixture for negative cases; do not mutate the real
`pyproject.toml` in tests.

**DoD.** `uv run just contract-check` remains green and all three
`test_s15_dependency_contract.py` tests pass without generated local state.

### P0-E — Fix documentation link inventory

**Finding.** 12 links point to removed root `HANDOFF.md`, including links in
`knowledge/BACKLOG.md`, `knowledge/MAINTENANCE.md`, `knowledge/architecture.md`,
and `knowledge/pr-notes/README.md`. The current handoff lives under
`worklogs/HANDOFF.md`.

**Implementation.** Update every stale target to the canonical path, or remove
links that refer to intentionally archived material. Run the strict anchor
checker; preserve valid anchors rather than changing the checker to ignore
missing files.

**Tests-writing proof.** C0 checker plus documentation contract tests already
exist. Add no new test unless a new link policy is needed.

**DoD.** Both repository-wide and strict instruction/pr-notes link checks pass;
all links resolve to tracked files and anchors.

### P0-F — Repair observability compaction/circuit-breaker live paths

**Finding.** Three C1 tests fail in `tests/test_observability_edge_cases.py`:

- compaction stage 3 residual pressure does not emit the expected warning;
- circuit-breaker compaction-end event is missing or path is not reached;
- circuit-breaker context warning is missing.

Captured behavior shows a key interaction defect: the test sets
`context_compaction_enabled=True`, but the live code logs that compaction is
disabled and stops at stage 2. This overlaps P0-C and must be fixed as one
behavioral contract, not with isolated event-only patches.

**Implementation.** Trace `coder_loop.py` from budget check through compaction
selection, circuit-breaker accounting, `EventLog.append`, and `output.emit`.
Make the authoritative compaction decision deterministic. Ensure every intended
path dual-writes the structured log and console event, with event fields that
identify `action`, `stage`, and stop reason. Preserve no-provider-call early
stop where budget/circuit breaker fires.

**Tests-writing proof.** Existing tests are the C1 producer tests and must be
made green without weakening their assertions. Add/adjust only where a path
inventory shows a missing branch:

| Path | Matrix | Oracle |
|---|---|---|
| stage-2 warning, no compaction | A/C | `context_warn`, outcome, request count |
| compaction succeeds | B | `compaction_start/end`, projected history |
| residual stage-3 pressure | B | stage-3 `context_warn`, stop reason |
| circuit breaker | B | `compaction_end`, warning, hard-stop outcome |

Kill-check the production `output.emit(OutputEvent(...))` producer call, not
only the renderer handler. Add an adversarial oversized-context case if the
security/availability boundary is not already covered.

**DoD.** all three existing tests pass; contract checker remains green; all
producer paths have consumers and C1 tests; structured log and console mirror
agree.

### P1-A — Close authoring export completeness

**Finding.** `uv run just authoring-check` reports five HARD-BLOCK diagnostics in
`src/fa/stats.py`: `ToolError`, `CompactionRecord`, `SubagentRecord`,
`ContextBudgetEvent`, and `CompactionStartRecord` are public definitions absent
from `__all__`.

**Implementation.** Determine whether each symbol is intentionally public. If
public, export it in the module's explicit `__all__` in deterministic order. If
internal, rename with a leading underscore and update imports/tests accordingly.
Do not weaken the authoring rule.

**Tests-writing proof.** C0 authoring-rule tests plus a wiring/import check:

- `fa authoring-check` clean tree has no hard blocks;
- explicit public API import test for symbols retained as public;
- kill-check the export list or symbol rename so the rule catches a regression.

**DoD.** authoring check exits 0 and parity/exports tests remain green.

### P1-B — Resolve Ruff judgment debt in scoped batches

**Finding.** Ruff reports 140 findings after `just fix`'s 204 mechanical fixes
were reverted. The findings include real design signals (complexity, mutable
class state, broad exception swallowing, long lines, naming) and test cleanup.

**Implementation order:**

1. production `BLE/S110`, complexity, and mutable-state findings;
2. scripts/checkers that are themselves CI authority;
3. import/style/test hygiene;
4. intentional exceptions only with narrow rule codes and one-line rationale.

For each batch, run focused tests first. Do not use `# noqa`, global ignores,
or a raised complexity threshold as the default closure mechanism. The
`justfile` documented fix sequence should be run per batch, with diff review.

**Tests-writing proof.** No behavior claim is complete on lint alone. For every
production refactor, retain/extend C1 tests and perform a producer kill-check
when event code moves. For checker refactors, run their direct tests and CLI
exit-code tests.

**DoD.** `uv run just lint` passes with only reviewed, line-local waivers whose
rationales are retained in the diff.

### P1-C — Restore coverage honestly

**Finding.** Full execution coverage is 76.80%, below the configured 86% gate.
The branch advertises/targets a stronger gate than the actual suite currently
achieves. Lowering `fail_under` is prohibited.

**Implementation.** After P0 behavioral and infrastructure fixes, inspect the
coverage report by module. Add meaningful tests for shipped live paths, with
priority on low-covered modules involved in the branch changes (`cli.py`,
inner-loop tools/runtime, stats/telemetry). Remove dead code only when product
scope confirms it is not shipped. Keep CLI integration tests separate from C1
loop tests.

**Tests-writing proof.** Coverage is a secondary signal; every new test must
have a structured oracle and anti-theater rationale. Use mutation after C1 is
green. Do not add tests that only execute lines without asserting events,
outcomes, call counts, filesystem effects, or security denials.

**DoD.** full `uv run just test` passes the 86% gate without exclusions except
those already justified in pyproject; coverage XML is produced.

### P1-D — Complete optional CI environment verification

**Finding.** Local host lacks Docker, shellcheck, gitleaks, and Semgrep. These
are not yet classified as product failures.

**Implementation.** Use CI or install pinned/appropriate local tools in a
separate environment. Verify:

- Dockerfile build and numeric-1000 read-only smoke tests;
- egress-proxy help smoke;
- `/repo` read-only + `/sessions` writable topology;
- shellcheck-backed deploy script tests;
- gitleaks with repository config and full history;
- Semgrep advisory workflow;
- mutation workflow using the pyproject mutmut scope.

The container workflow currently includes `sudo chown`; confirm the GitHub
runner supports this assumption and document if a portable alternative is
needed.

**DoD.** each CI-only job has a recorded PASS/FAIL with log evidence; no local
skip is presented as a green result.

## 4. Suggested execution sequence

### Slice 1 — unblock deterministic tooling

1. Keep pytest `pythonpath` fix.
2. Resolve test package/mypy module identity.
3. Decide and implement optional dependency contract.
4. Restore tracked dependency contract artifact.
5. Fix stale doc links.
6. Run focused tests and typecheck.

### Slice 2 — restore feature/loop semantics

1. Decide legacy compaction flag authority.
2. Implement live compaction/circuit-breaker behavior.
3. Add/adjust C1 matrix and producer kill-checks.
4. Run observability and inner-loop focused suites.
5. Run contract/no-mocked guards.

### Slice 3 — authoring and lint

1. Close `stats.py` export diagnostics.
2. Refactor checker complexity and production broad catches.
3. Apply `just fix` only to the touched slice.
4. Run `just lint`, authoring-check, and direct checker tests.

### Slice 4 — coverage and CI-only gates

1. Use the new coverage report to target meaningful untested live paths.
2. Run full coverage gate.
3. Run audit, Semgrep, gitleaks, Docker, and mutation in CI-equivalent
   environments.
4. Perform final full `uv run just check` and record every result.

## 5. Final DoD checklist

- [ ] `uv lock --locked`
- [ ] `uv run just lint`
- [ ] `uv run just typecheck`
- [ ] `uv run just authoring-check`
- [ ] `uv run just contract-check`
- [ ] `uv run just no-mocked-dataclasses`
- [ ] `uv run just test` with coverage >= 86%
- [ ] repository and strict-anchor documentation checks
- [ ] `uv run pip-audit`
- [ ] Semgrep result classified and retained
- [ ] gitleaks result classified and retained
- [ ] Docker build + non-root read-only smoke tests
- [ ] mutation run; survivors triaged via
  `knowledge/mutation-survivors-workplan.md`
- [ ] final git diff is scoped; no formatter churn or silent gate weakening
- [ ] final report includes tests-writing LIVE-PATH PROOF for every behavioral
  change:

```text
LIVE-PATH PROOF:
- root: drive_session | cli:<subcommand>
- test: tests/<file>.py::test_<name>
- matrix: A | B | C | P-<family>
- oracle: event:<kind> | outcome:<stop_reason> | trajectory | call_count
- kill-check: removing <producer emit call> fails the named test
- producer: <file.py>:<line>
- paths-covered: N/M paths
- contract-check: PASS | FAIL
- efficiency: call_count=N | early-stop
- pyramid: A
```

## 6. Current working tree

Only the pytest import-path correction is intentionally retained at this
baseline checkpoint:

```text
 M pyproject.toml
```

The broad `just fix` mechanical diff was intentionally reverted because it
spanned 88 files and still left 140 judgment findings; it will be reapplied in
small reviewed slices during closure.

## 7. Lifecycle simulation findings (2026-07-21 follow-up)

### 7.1 PTY full-suite hang — CLOSED

The first full-suite rerun appeared stuck after `test_proxy_wiring_cli.py` at
`test_pty_persistence.py::test_ctrl_c`. Process inspection showed the pytest
process was still alive after the tool wait timed out; it was terminated
explicitly.

Reproduction:

```bash
timeout 90s uv run pytest -vv -s \
  tests/test_proxy_wiring_cli.py tests/test_pty_persistence.py
```

Root cause: `test_ctrl_c` runs `PtySession.run()` in a worker thread while
`send_ctrl_c()` performed a second concurrent `pexpect.expect()` on the same
child. Concurrent readers raced to consume the prompt/end sentinel, leaving a
non-daemon worker blocked. The isolated pty-only order did not expose the race;
the proxy-import order made it reproducible.

Implementation:

- `send_ctrl_c()` now sends the control character only;
- the active `run()` call remains the sole pexpect reader;
- the C1 test asserts the worker thread is stopped before cleanup.

Verification: proxy + pty sequence **11 passed in 3.19s**; full suite reached
completion with **1,780 passed, 13 skipped**.

The OS-level `timeout` remains a diagnostic safety boundary for CI simulation;
it is not used to turn a hang into a pass.

### 7.2 Current full-suite gate

After the focused fixes, `uv run just test` has no behavioral test failures:

- 1,780 passed
- 13 skipped (shellcheck/executable-bit environment skips)
- 76.84% coverage
- configured fail-under: 86%

The remaining test-gate work is meaningful coverage expansion. The threshold
must not be lowered. Prioritize low-covered live modules and assert structured
outcomes/events/FS/security behavior rather than line-execution theater.

### 7.3 Mypy debt boundary — clarified

The initial eight-error report was truncated by the duplicate module identity
error. The canonical run currently fails at:

```text
tests/fixtures/session_wiring.py: Source file found twice under different
module names: session_wiring and tests.fixtures.session_wiring
```

Experiments show:

- explicit package markers expose approximately 242 strict errors across the
  wider test/runtime tree;
- `--explicit-package-bases` changes import resolution and exposes approximately
  875 errors, including installed-package resolution problems;
- `uv run mypy src` independently exposes 113 errors in 17 production files.

This is not evidence for excluding tests or disabling strict mode. It requires
staged closure:

1. choose one canonical source/package mapping;
2. close production typing errors in `src/`;
3. type shared fixtures;
4. type tests in batches;
5. only then require strict mypy as a trustworthy full gate.

Optional integrations remain runtime-graceful (`fitz`, `pdfminer`, `pypdf`,
FastAPI), but their `type: ignore` codes must match actual mypy diagnostics and
must not become blanket suppression.

### 7.4 Hook bootstrap policy

Git cannot safely auto-execute repository code immediately after clone. The
mandatory trusted setup contract is:

```bash
uv sync --frozen --extra dev
just install-hooks
just hooks-status
```

The repository's `just install` already composes this sequence. The agent
runner must invoke `just install` before declaring the environment ready; `uv
sync` alone is not setup-complete. Local hooks remain bypassable by design and
CI remains authoritative.

### 7.5 TCB workflow protection policy

`CODEOWNERS` alone does not block edits. GitHub repository settings must enable:

- protected `main` branch/ruleset;
- required pull request;
- required status checks, including `Authoring Guardrails / authoring-check`
  and `Advisory CI / sanity-check`;
- Require review from Code Owners;
- no agent bypass permission;
- stale approval dismissal / up-to-date branch requirement.

For the desired “ask the operator” behavior, the harness should additionally
deny agent writes to ADR-11 TCB paths at `IntentGuard` mutation time with a
structured `manual_operator_approval_required` result. External GitHub
protection remains the merge authority because a modified workflow cannot be
trusted to protect itself.

## 8. Operator corrections and readiness contract

### Merge policy

Required checks are the normal merge gate, not an absolute prohibition on a
maintainer. A human maintainer may deliberately use GitHub's emergency/admin
override to merge with failed CI. The agent identity MUST not have that bypass
permission and MUST not be able to approve its own PR. Documentation now uses
this distinction explicitly.

### Existing-test edits

The supported exception is the existing `TEST-EDITS:` declaration in the
trusted current-session `pr.prepare` draft:

```text
TEST-EDITS: tests/test_pty_persistence.py — add worker-liveness assertion for Ctrl+C race
```

Rules remain:

- existing test modification during a classifier-FIX diff requires a declared
  path and non-empty reason;
- new test files are allowed;
- test deletion/rename/copy is always blocked;
- typed `INTENT:` cannot disarm this check because the classifier intent is
  passed separately;
- both IntentGuard and the git hook consume the same validator.

The current maintenance edits were operator-level edits, not simulated agent
calls; future agent simulations must use `pr.prepare` + `TEST-EDITS`.

### Deterministic readiness

Added the canonical just recipe:

```text
just agent-bootstrap
```

It runs `just install`, which performs frozen dependency sync, installs all
four hooks, and runs `hooks-status`. Only after all commands succeed does it
emit:

```text
FA_AGENT_READY=1
```

The harness startup process must treat absence of that exact marker as
not-ready and must not construct the LLM session. Git clone itself remains
side-effect-free by design; trusted setup orchestration owns the bootstrap.

## 25. EXECUTION UPDATE — FULL TEST-TREE MYPY / RUN_BASH RUFF / COVERAGE SMOKE

### Full test-tree mypy

The explicit package mapping and test typing pass are complete:

```text
uv run mypy
Success: no issues found in 269 source files
```

The source count increased by the new deferred-runtime coverage test module;
there are no remaining test-tree or production mypy errors.

### Ruff production batch

`run_bash.py` was decomposed into executor resolution, PTY execution, and
subprocess fallback helpers. Its scoped Ruff check is now clean. C1/C3 tests
for run-bash, sandbox, PTY, transaction, artifact, and timeout behavior pass.

The broader Ruff inventory remains open because other design functions still
need decomposition (`spawn_subagent`, `profiles`, `PtyPool.run`, loop/global
history, Mistral normalization). No global suppressions were added.

### Coverage expansion smoke

Added C2 coverage for the deferred FastAPI runtime boundary and confirmed full
behavior remains green:

```text
1793 passed, 13 skipped, 0 failures
coverage: 77.04% < 86% gate
```

This smoke slice did not materially move the aggregate percentage. The next
coverage work must target the report's large live-path gaps, especially PTY,
tool registry, runtime server, stats, and transaction/error branches, with C1/C3
oracles rather than execution-only tests.

## 26. EXECUTION UPDATE — SPAWN/PROFILES/PTY RUFF BATCH

Scoped the requested production Ruff batch and preserved behavior:

- `profiles.py`: optional FTS configuration fallback now has explicit
  failure-observable rationale;
- `spawn_subagent.py`: schema description lines wrapped; existing role/secret
  gating and event/cleanup paths unchanged;
- `PtyPool.run()` remains behaviorally covered and its complexity is retained
  as the next decomposition target rather than suppressed.

Current scoped findings are exactly four C901 design findings:

```text
profiles._build_tool_builders: 16 > 15
spawn_subagent.build_spawn_subagent_tool: 33 > 15
spawn_subagent.handler: 32 > 15
PtySession.run: 18 > 15
```

No C901 waiver was added.

Verification:

```text
mypy src: PASS — 129 source files
scoped spawn/profile/PTY tests: 37 passed
```

The remaining four findings require orchestration decomposition. They are not
safe to resolve with formatter churn or blanket suppression.

## 27. EXECUTION UPDATE — SPAWN/PROFILES/PTY DECOMPOSITION

### Decompositions completed

- `spawn_subagent.py`: extracted request parsing/secret filtering, centralized
  EventBus emission, completion recording, runner-error cleanup, and a thin
  ToolSpec factory.
- `profiles.py`: extracted optional builder registration from the main builder
  function, preserving role-specific tool availability and graceful import
  fallback.
- `PtyPool.run()`: split fallback pexpect execution and tmux execution into
  `_run_fallback` and `_run_tmux`, leaving a small lock/dispatch method.

### Contract-checker correction

Centralized subagent EventBus emission exposed a checker blind spot: the
log-kind checker only recognized direct `OutputEvent(type=...)` constructors.
It now verifies the typed `_emit_subagent_event(event_type: EventType, ...)`
helper and the expected subagent event literals. This is a real checker
improvement, not a test waiver.

### Verification

```text
scoped Ruff: PASS for spawn_subagent.py, profiles.py, pty_pool.py
mypy src: PASS — 129 source files
focused spawn/profile/PTY/contract tests: 48 passed
full pytest: 1793 passed, 13 skipped, 0 failures
log-kind contract: PASS
producer-consumer contract: PASS
git diff --check: PASS
```

Coverage remains the next open phase; the latest authoritative aggregate remains
approximately 77.04% against the 86% gate.

## 28. EXECUTION UPDATE — COVERAGE BATCH STARTED

The latest coverage report identified the highest-value low-covered modules:

```text
PtyPool                  33%
profiles                 45%
spawn_subagent            44%
tools/__init__            51%
stats                     69%
session_db                76%
```

Added C2 PTY helper tests for explicit missing-child and missing-pane failure
states after the `PtyPool.run()` decomposition. These assert structured
`PtyResult` failures rather than merely executing lines.

Verification:

```text
PTY helper/persistence suite: 8 passed
full behavioral suite before coverage additions: 1793 passed, 13 skipped
```

Coverage expansion remains active. The next tests should target profile-builder
fallback/registration, subagent runner-error cleanup, stats render/aggregate
branches, and session DB failure paths with C1/C2/C3 structured oracles.

## 29. EXECUTION UPDATE — ADVERSARIAL COVERAGE BATCH

Added `tests/test_coverage_failure_paths.py` with six structured failure/edge
contracts:

- optional profile builder import failure remains observable and registry-safe;
- subagent runner exception returns `runner_failed`, logs failure, and cleans
  the isolated workspace;
- stats aggregate/render/efficiency branches expose structured metrics;
- dead-zone detection handles missing workspaces and ignored cache files;
- session DB read failure falls back to the existing JSONL mirror deterministically;
- session DB initialization failure raises explicit `session_db_init_failed`.

Verification:

```text
coverage failure-path tests: 6 passed
full pytest: 1801 passed, 13 skipped, 0 failures
coverage: 77.73% < 86% gate
```

The stats module improved from approximately 69% to 82%, demonstrating that
these are meaningful analytics-path tests rather than line-execution theater.
Remaining high-value coverage gaps are primarily PTY failure branches,
profiles/tool-builder optional registration branches, subagent edge branches,
`session_db.py`, `runtime/server.py`, and low-covered tool modules.

## 30. EXECUTION UPDATE — COVERAGE BATCH 2

Expanded `tests/test_coverage_failure_paths.py` from six to ten structured
failure-path tests:

- all optional tool builders absent: registry remains valid and empty;
- secret-looking subagent environment key is denied before execution;
- missing subagent command returns structured invalid-params failure;
- PTY invalid workdir and max-size/main-pinning exhaustion are explicit.

Verification:

```text
coverage failure-path module: 10 passed
full pytest: 1805 passed, 13 skipped, 0 failures
coverage: 77.96% < 86% gate
```

The aggregate improved from 77.73% to 77.96%. Remaining largest measured
coverage gaps are now `PtyPool`, `tools/__init__`, `read_file/edit_file`,
`runtime/server`, and low branches in `stats`/session DB. The next batch should
prefer real PTY fake-server paths and file-tool failure/containment paths over
more synthetic aggregate tests.

## S6 execution update — source Ruff/contract hardening

- scoped source Ruff mechanical pass reduced source findings from 92 to 65;
- global-history B905 and broad projection-boundary exception findings were
  narrowed/documented;
- `spawn_subagent.py`, `profiles.py`, and `PtyPool.run()` decompositions remain
  behaviorally green;
- Ruff-formatted `CONSOLE_MIRROR_KINDS` exposed a checker regex fragility;
  the checker now accepts typed/multiline `frozenset({...})` declarations;
- focused contract tests: 15 passed;
- full pytest: 1806 passed, 13 skipped, 0 failures.

Remaining source Ruff findings are primarily CLI/loop/state/Mistral complexity,
long-line policy, and selected failure-boundary decisions. No global ignores or
blanket C901 waivers were added.

## 33. EXECUTION UPDATE — S6 MAJOR ITEMS 1–4

Closed the four requested S6 production-risk areas:

- Mistral Conversations request-body construction decomposed into typed input,
  tool, and completion-argument helpers;
- Mistral response normalization decomposed into output-item normalization plus
  canonical response assembly;
- CLI observer/error boundaries now log observer failures, use specific parsing
  exceptions where known, and retain explicit CLI stats failure reporting;
- loop runtime assert replaced by explicit conditional handling;
- state EventLog DB-counter fallback now logs the failure before JSONL fallback;
- coder/loop long-line and naming findings resolved.

A centralized subagent EventBus helper exposed a producer-consumer checker blind
spot. The checker now recognizes typed helper emission for `subagent_start` and
`subagent_end` rather than requiring duplicated direct constructors.

Verification:

```text
mypy src: PASS — 129 source files
focused Mistral/CLI/loop/state tests: 100 passed
full pytest: 1806 passed, 13 skipped, 0 failures
producer-consumer contract: PASS
log-kind contract: PASS
authoring-check: PASS
git diff --check: PASS
```

Source Ruff inventory is now 37 findings, concentrated in remaining mechanical
long-text files, compaction foundation class-state handling, edit/search/tool
module style, and selected stale boundary comments. The four major S6 items
are closed without global suppressions.

## 34. EXECUTION UPDATE — SOURCE RUFF CLOSED / COVERAGE BATCH 3

### S6 source Ruff closure

Closed the remaining 37 production source Ruff findings without global ignores:

- `CompactionManager.stages` is now typed `ClassVar`, and the dead first
  threshold loop was removed; the live highest-stage selection loop remains;
- `SubagentRunner` import ordering and a feature-flag exception boundary were
  narrowed;
- long production descriptions/comments were rewritten as bounded strings;
- edit-file fuzzy variables were renamed from ambiguous `l` names;
- optional FTS registration now catches only expected optional-config failures.

Verification:

```text
uv run ruff check src: PASS
uv run mypy src: PASS — 129 source files
focused regression: 57 passed
```

### Coverage batch 3 and discovered product defect

Added live handler/authority tests in `tests/test_coverage_tools_batch.py`:

- read-file line windows, invalid windows, missing files, and invalid input;
- edit-file exact/fuzzy/missing/containment paths;
- real researcher/planner registries, planner write allowlist, token estimate;
- SessionDatabase event, blackboard, query, metadata, and write-failure paths.

The adversarial containment test initially exposed a product defect: `fs.edit_file`
allowed `PermissionError` from `resolve_workspace_path` to escape instead of
returning its structured `invalid_params` failure. The production handler now
maps both `ValueError` and `PermissionError` to that contract; the read handler
was aligned for the same boundary.

Added deferred-runtime C2 endpoint tests covering execute success, 400/404/500
HTTP failures, list, health, Ctrl+C, and kill. The tests pass when the optional
runtime extra is installed and remain explicitly skipped in the default
minimal environment.

Verification:

```text
21 focused tool/registry/security tests: PASS
uv run --extra runtime pytest tests/test_runtime_server_c1.py: 2 passed
uv run ruff check src tests/test_runtime_server_c1.py: PASS
uv run mypy src tests/test_runtime_server_c1.py: PASS
full pytest: 1810 passed, 13 skipped, 0 failures
coverage: 78.59% < 86% gate
```

The coverage gate remains intentionally unchanged and open. The next measured
high-value targets are PTY fake-server/failure branches, `tools/__init__`
optional registration paths, `subagent_runner`, and remaining stats/blackboard
branches. No claim of full CI closure is made.

## 36. EXECUTION UPDATE — PTY FAKE-TMUX COVERAGE / OPTIONAL-TYPING HARDENING

Added `tests/test_pty_tmux_fake.py` with a typed fake tmux server/pane that drives
`PtySession` through the production constructor and run path, rather than
calling only pure helpers. It verifies:

- tmux sentinel setup and exit-code parsing;
- pane command-send failure as structured `PtyResult`;
- Ctrl+C/no-pane/close paths;
- pinned-main `PoolExhaustedError` policy.

The measured PTY subset is now:

```text
21 tests passed
pty_pool.py: 70% line/branch report for the exercised subset
```

Installing the optional runtime extra exposed strict typing issues that are now
closed by dynamic optional imports with explicit narrow boundary ignores only
where FastAPI's dynamically typed decorators/base model require them. Both
minimal and optional environments remain verified:

```text
full mypy: PASS — 272 files
source Ruff: PASS
optional endpoint tests: 2 passed
```

Authoritative contract/TCB checks pass. `just typecheck` passes with the venv on
PATH. `just lint` remains red on the pre-existing repository-wide test/script
Ruff inventory (229 findings); source Ruff is clean and this pass did not
mechanically churn unrelated test debt. Coverage remains below gate at 78.59%
from the last full aggregate run; `just check` is therefore not green.

## 38. EXECUTION UPDATE — COVERAGE/ROBUSTNESS SLICE: PTY, REGISTRY, SUBAGENT, BLACKBOARD, STATS

Implemented the planned high-value coverage slice in
`tests/test_quality_slice_coverage.py` and extended fake-tmux coverage.

### Production defects found and fixed

- `SubagentRunner._check_spawn_limit()` re-raised a `RuntimeError` from
  session-context lookup as an intentional spawn-limit violation. Context lookup
  now has its own fallback boundary; only an actual exhausted limit raises the
  limit error.
- `SubagentRunner.run_stateless()` protected artifact writes but not worklog
  aggregation. Worklog aggregation is now explicitly best-effort and cannot
  erase a valid subagent result.
- `aggregate_sessions([])` returned a partial schema. Empty aggregates now emit
  the same stable metric keys as non-empty aggregates, with zero/empty values.

### Live-path coverage added

- `PtyPool`/`PtySession`: tmux/fake-pane setup, command failure, Ctrl+C,
  close, pinned-main exhaustion, fallback lifecycle, and cleanup behavior.
- `tools/__init__`: optional builder failures, duplicate prevention, baseline
  profile fallback, FTS/extra registration paths.
- `SubagentRunner`: real blackboard-plan filtered history, schema-validation
  failure, artifact/worklog sink failures, and instance-limit fallback.
- `Blackboard`: read/write conflict matrix, linear parent policy, authoritative
  DB fallback to corrupt JSONL mirror, and mirror-write degradation.
- `stats`: empty/malformed/mixed event streams, unknown future kinds, JSON
  projection, and empty aggregate schema.

### Verification

```text
full pytest: 1826 passed, 13 skipped
aggregate coverage: 80.25% < configured 86% gate
full mypy: PASS — 274 source files
source Ruff: PASS
focused slice: 32 new/targeted tests passed
producer-consumer contract: PASS
log-kind/dependency/authoring/no-mocked-dataclasses checks: PASS
```

The coverage gate was intentionally not lowered. The measured target modules
now report approximately: `PtyPool 71%`, `tools/__init__ 75%`,
`SubagentRunner 80%`, `Blackboard 78%`, and `stats 83%` in the full suite.

### Ruff best-effort

Fixed four directly actionable guardrail-script findings (unused import,
import ordering, unnecessary f-string, and a long frozen-guard diagnostic).
Repository-wide Ruff reduced from 229 to 225 findings. Remaining repository
Ruff debt is concentrated in existing tests and one `check_dead_flags`
complexity finding; source Ruff remains clean. No broad ignores or coverage
threshold changes were introduced.

## 40. EXECUTION UPDATE — RUFF COMPLEXITY + UNUSED-IMPORT CLEANUP

### Complexity

Decomposed `scripts/check_dead_flags.py::_find_phantom_getattr_flags` into:

- `_find_regex_phantom_flags` for tolerant source-text detection;
- `_is_feature_flags_getattr` for the target-object predicate;
- `_find_ast_phantom_flags` for precise AST detection;
- a small coordinator that deduplicates both result streams.

This preserves both producer paths and their deduplication behavior. Existing
checker coverage remains green:

```text
tests/test_dead_flags.py: 9 passed
C901/F401 Ruff selection: PASS
```

### Unused imports

Ruff's standard safe F401 fixer removed 106 unused imports. The cleanup was
validated against the complete behavioral suite; no removed import was needed
for runtime registration or side effects:

```text
full pytest after F401 cleanup: 1826 passed, 13 skipped
full mypy: PASS — 274 source files
source Ruff: PASS
```

The safe I001/E401/C401/W291 cleanup removed 47 additional findings. Focused
regression after all cleanup passed 54 tests.

### Remaining Ruff inventory

Repository-wide Ruff is now at 70 findings, all outside the original source
production closure:

- 45 E501 long test comments/strings;
- 11 F841 unused test locals, requiring oracle review rather than deletion;
- 7 N806 test-local mock naming findings;
- 1 E401/C401/W291-class cleanup already addressed except no remaining selected
  findings;
- 1 N999 for the public operator script filename
  `scripts/fa_host_layout_audit.py`.

No C901 or F401 findings remain. The N999 filename is referenced by operator
knowledge and deployment documentation, so renaming it would be a public
operator-interface change; it remains explicitly open rather than hidden by a
blanket ignore.

## 42. EXECUTION UPDATE — REMAINING RUFF DEBT: F841/N806/E501/BLE/RUF

Continued repository-wide Ruff cleanup after complexity/F401 closure.

- Removed all 11 F841 test locals after reviewing each oracle; calls are now
  bare where EventLog/output side effects are asserted, and setup-only locals
  were removed.
- Renamed all 7 test-local N806 mock/constants without changing patch targets.
- Wrapped/factored all 45 E501 test comments, docstrings, fixture tuples, and
  assertion messages.
- Narrowed three test-only BLE001 boundaries to expected exception classes.
- Replaced three RUF015 single-element list slices with `next(...)` structured
  selection.

Verification:

```text
F841/N806: PASS
E501/BLE001/RUF015: PASS
source Ruff: PASS
full mypy: PASS — 274 files
focused affected tests: 17 passed
```

The only remaining repository Ruff finding is:

```text
N999 scripts/fa_host_layout_audit.py
```

This is a public operator-facing executable filename referenced by deployment
instructions and knowledge docs. It remains open rather than being hidden by a
per-file ignore or renamed without an interface migration plan.
