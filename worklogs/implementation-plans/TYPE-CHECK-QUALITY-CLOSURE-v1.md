# Type-check and quality-gate closure — implementation plan v1

**Plan ID:** `PLAN-TYPE-QUALITY-CLOSURE-V1`
**Status:** `READY` — scope locked; execute in S0–S9 order
**Depth:** P2 (cross-module quality/control plane; no intended product architecture change)
**Branch:** `guardrails+mistral-support`
**Baseline commit:** `db6fd88`
**Date:** 2026-07-21
**Skills:** `plan-authoring`, `tests-writing`
**Primary roots:** `fa.inner_loop.coder_loop.drive_session`, `fa.inner_loop.loop.run_session`, CLI `fa.cli`, tool registry builders, hook `IntentGuard`, CI `uv run just check`

---

## 0. Executive intent

### IDEA

Turn the current misleading/fragmented static-quality state into a truthful,
production-grade gate: one canonical mypy source mapping, production typing
closed before test typing, explicit optional-dependency policy, Ruff findings
resolved by design rather than global suppression, and coverage raised through
live-path tests.

### PROJECT MEANING

In First-Agent, static quality is not cosmetic. The project treats the LLM as
an untrusted compiler and uses deterministic checks to prevent an agent from
shipping code that merely imports, executes a line, or makes a test green. This
plan therefore closes the quality gates at their real composition roots while
preserving the project’s minimalism-first and pair-over-autonomy principles.

### GOALS

- **G1 — Truthful typing gate:** establish one canonical module mapping and
  close strict typing in `src/fa` before expanding strict test typing.
- **G2 — Truthful dependency contract:** every runtime import is either a
  declared supported dependency or an explicitly typed optional integration
  with a deterministic missing-backend contract.
- **G3 — Maintainable Ruff gate:** remove design findings by decomposition or
  narrow reviewed waivers; do not globally suppress E501/security/complexity.
- **G4 — SSoT compaction contract:** deprecated flag compatibility, dead-flag
  detection, and `compaction_threshold` derivation agree and cannot drift.
- **G5 — Coverage as live-path evidence:** raise coverage from 76.84% to the
  configured 86% without line-execution theater or threshold reduction.
- **G6 — Agent-safe execution:** preserve C1 producer/consumer tests, test-edit
  declarations, security adversarial cases, and CI/local lifecycle contracts.

### NON-GOALS

- No new provider, model, retrieval, or orchestration capability.
- No global Ruff rule disable or coverage-threshold reduction.
- No exclusion of `tests/` from mypy merely to make the command green.
- No replacement of strict mypy with advisory pyrefly.
- No addition of PDF/FastAPI dependencies until the operator decides whether
  those surfaces are supported in v0.1.
- No replacement of the log-kind checker with a larger framework unless a
  smaller AST/parser correction cannot satisfy the contract.
- No automatic Git hook execution at clone time.
- No removal of the deprecated `FeatureFlags.context_compaction_enabled` field
  without a backward-compatibility decision.
- No change to the human emergency merge override.

### INTENT

Whenever a quality check reports a failure, the repository must either fix the
underlying production contract, explicitly model an intentional compatibility
boundary, or surface a narrowly scoped reviewed exception. It must never make
the check green by hiding the path from the checker.

### MECHANISM SKETCH

`just agent-bootstrap` establishes the environment → `uv run just check` runs
lock/lint/type/authoring/contract/test gates → C1 tests exercise `drive_session`
and CLI roots → structured event/outcome/FS/security oracles prove behavior →
GitHub required checks and CODEOWNER review control normal merge → maintainer
retains explicit emergency override.

### PROOF SKETCH

Each behavioral step names a root, producer, consumer, path matrix, and
kill-check. Static steps have command-level negative proofs: removing the
config/dependency/annotation/contract causes the relevant checker or focused
test to fail.

---

## 1. PREFLIGHT LOG

### Roots checked

- `src/fa/inner_loop/coder_loop.py::drive_session` — budget/compaction/event
  producer root.
- `src/fa/inner_loop/loop.py::run_session` — session/tool lifecycle root.
- `src/fa/cli.py` — shipped CLI composition root.
- `src/fa/inner_loop/hooks/intent_guard.py::IntentGuard.handle` — harness
  mutation gate.
- `src/fa/hygiene/pr_intent.py::validate_test_edits` — shared test-edit
  policy.
- `justfile::check` — local/CI authority: `lock-check lint typecheck
  authoring-check contract-check no-mocked-dataclasses test`.
- `.github/workflows/advisory.yml::sanity-check` — CI execution of
  `uv run just check`.

### Greps/checks run → findings

| Search/check | Finding |
|---|---|
| `find knowledge/skills ...` | `plan-authoring` and `tests-writing` are active. |
| project-overview Pillars 1–4 | implementation-first reference; pragmatic UC1/UC3 product; token/tool efficiency; iteration via measurement. |
| package markers | `tests/__init__.py`, `tests/fixtures/__init__.py`, `scripts/__init__.py` absent. |
| Ruff config | `ignore = []`; E501 is active; tests only exempt from S. |
| deptry config | only dev-tool DEP002 ignores; no fitz/pdfminer/pypdf/fastapi/pydantic/requests policy. |
| `check_dead_flags.py` | `_DEPRECATED_FIELDS` set contains `context_compaction_enabled`; field output carries `is_deprecated`. |
| S14 tests | production source-of-truth assertion requires `compaction_threshold is not None`; production must not read deprecated flag outside `feature_flags.py`. |
| log-kind checker | passes, but `extract_console_mirror_kinds()` uses regex and `KIND_TO_EVENT_TYPE` remains uppercase in a function. |
| sandbox enum tests | 16 tests pass; uppercase enum members already match production. |
| dependency contract | checker passes; `.fa/dependency_contract.toml` is present and explicitly unignored. |
| full pytest | 1,780 passed, 13 environment skips; coverage 76.84% vs 86% gate. |
| Ruff | 366 findings in current unformatted baseline; includes E501, C901, N806/N814, RUF012, and broad test/style findings. |
| mypy | standard run is blocked first by duplicate module identity; `mypy src` independently exposes 113 errors in 17 files. |
| hooks | `just agent-bootstrap` now emits `FA_AGENT_READY=1` only after frozen sync/install/status. |

### Gold patterns mirrored

- `tests/test_pr1_wiring.py` — C1 composition-root/provider mock pattern.
- `tests/test_event_type_c1_producers.py` — producer/consumer event contract.
- `tests/test_s14_compaction_ssot.py` — source-of-truth kill-check.
- `tests/test_test_edit_protection.py` — `TEST-EDITS` and two-seat protection.
- `tests/test_hygiene_hooks_install.py` — hook installer/status behavior.
- `tests/test_mistral_integration.py` — provider-family integration pattern.

### Conflicts/invariants found

- ADR-11 treats the LLM author as an untrusted compiler and requires CI as
  authority; local hooks are convenience only.
- S14 explicitly forbids production reads of the deprecated compaction flag.
- Project overview says PDF/binary extraction is out of scope for v0.1;
  `read_file.py` nevertheless contains optional PDF backend imports. This is a
  policy decision, not merely a missing annotation.
- `tests-writing` requires C1 for product/session claims, C3 for security,
  producer kill-checks for events, path inventory, matrix coverage, and honest
  fixtures.
- `plan-authoring` requires this plan remain DRAFT while executor policy
  questions are unresolved.

### As-is liveness

| Contract | Liveness | Evidence |
|---|---:|---|
| compaction SSoT | L3 | production derivation + S14 tests + C1 edge tests pass |
| dead-flag checker | L2/L3 | runs and passes, but deprecated metadata is duplicated in checker |
| log-kind contract | L2 | script and tests pass; parser remains heuristic |
| sandbox enum contract | L3 | 16 focused tests pass |
| dependency contract | L2/L3 | checker passes; deptry still reports 9 issues |
| authoring exports | L3 | authoring-check passes after export fix |
| PTY Ctrl+C lifecycle | L3 | exact proxy+PTY sequence passes after producer/read-race fix |
| full coverage gate | L2 | all tests pass but fail-under fails |
| strict mypy | L1/L2 | first module-mapping barrier prevents full verdict |
| Ruff | L1/L2 | command executes but current baseline fails 366 findings |

### Unresolved → promoted to questions

- Q1: Which optional integrations are supported in v0.1: PDF extraction,
  FastAPI runtime server, or neither?
- Q2: Should strict mypy cover all tests immediately, or should a staged
  `mypy src` gate land first while test typing is completed in a bounded plan?
- Q3: Is `context_compaction_enabled` allowed to remain a compatibility field
  with zero production reads, and should deprecated metadata live in one shared
  source rather than a checker-local set?
- Q4: Should E501 remain blocking for source/tests, with narrowly scoped
  per-line waivers for prompts/assertions, or should a reviewed per-file policy
  exist for selected generated/long-string files?
- Q5: Which GitHub check names and emergency-merge permissions are configured
  outside the repository? This plan must not silently assume branch protection.

---

## 2. CLAIM-BY-CLAIM REVIEW OF THE OTHER AGENT REPORT

| Report claim | Verified verdict | Evidence / required disposition |
|---|---|---|
| Add `compaction_threshold=80000` to observability tests | **Accept; present** | Three `make_mock_chain(context_limit=100000, compaction_threshold=80_000)` calls now exist; 21 compaction/dead-flag tests pass. |
| Add deprecated flag to allowed-dead list | **Rewrite** | `_DEPRECATED_FIELDS` exists and tests pass, but this is duplicated policy. Replace with explicit metadata/contract or keep only after Q3 accepts the compatibility model. |
| Regex fixed for multiline `frozenset` | **Reject as current-state claim** | Current checker regex is `frozenset\(\{(.*?)\}\)`; it passes current formatting but is still fragile. Add parser regression fixtures for multiline/annotation/comment changes before calling robust. |
| Rename `KIND_TO_EVENT_TYPE` | **Not present** | Ruff still reports N806 at `scripts/check_log_kind_contract.py:122`. Include in a narrow checker cleanup step. |
| Add global E501 ignore | **Not present and not recommended** | `ignore = []`; E501 is active. Do not accept global suppression without Q4; current plan defaults to preserve blocking line length. |
| Add `ClassVar` to compaction stages | **Not present** | `src/fa/inner_loop/compaction/foundation.py:29` still reports RUF012. Decide whether immutable tuple/`ClassVar` is the correct design and add focused tests for stage order/selection. |
| Rename N806/N814 variables | **Not present** | `KIND_TO_EVENT_TYPE`, `MIN_CONTEXT_LIMIT`, `_SO`, and other findings remain. Handle in focused Ruff batches. |
| Add package markers | **Not present** | No `tests/__init__.py` or `tests/fixtures/__init__.py`. Adding them previously exposed broader strict debt; do not apply without canonical mapping strategy. |
| Add `-> None` to 50+ tests | **Not present** | Test strictness remains unclosed behind module identity. Type tests after package mapping is chosen. |
| Add `type: ignore[import-untyped]` | **Partially present / inaccurate** | Some optional import comments exist; missing modules produce DEP001 and mypy codes must match actual diagnostics. Suppression is not dependency policy. |
| Add deptry ignores for optional/transitive imports | **Not present** | Current `[tool.deptry.per_rule_ignores]` only covers dev tools; `uv run deptry src/` reports 9 issues. Resolve through Q1, then declare or isolate optional adapters. |
| Sandbox enum capitalization changes | **Already true in baseline** | Production and tests use uppercase enum members; 16 focused tests pass. No implementation step. |
| Create dependency contract | **Accept; present** | `.fa/dependency_contract.toml` exists, is trackable, and checker passes. Add parity/format tests only if schema evolves. |

**RN1 disposition:** the report is useful as a lead list, not authority. Accept
verified changes; reject claims contradicted by code; rewrite architectural
shortcuts; defer policy-dependent changes behind Q1–Q4.

---

## 3. PROJECT-AXIS ALIGNMENT

| Goal/axis | Plan contribution | Guard against overreach |
|---|---|---|
| Pillar 1: implementation-first reference | make gates and contracts executable, reproducible, and reviewable | no speculative framework; use stdlib/pytest/Ruff/mypy already present |
| Pillar 2: pragmatic UC1/UC3 product | protect real session/CLI/provider paths and optional boundaries | PDF/FastAPI support is decided explicitly; no accidental v0.2 expansion |
| Pillar 3: token/tool efficiency | preserve C1 efficiency assertions and avoid test-only execution; maintain typed tool contracts | no new LLM calls; no topology changes |
| Pillar 4: measurement | coverage, mutation handoff, structured oracles, and failure evidence become truthful | coverage threshold stays; no line-count theater |
| minimalism-first | prefer local refactors, narrow adapters, and existing checkers | no global ignores, no new framework, no test exclusions |
| compliance-by-construction | deterministic type/dependency/authoring/event checks | every exception gets a contract and negative proof |
| pair-over-autonomy | preserve manual approval and explicit emergency merge override | agent never receives human bypass rights |

---

## 4. CONTRACT CARDS

### CT1 — Canonical Python module mapping

**Type:** build/type-check contract.
**Current producer:** mypy file discovery from `[tool.mypy] files = ["src", "tests"]`.
**Current failure:** `tests/fixtures/session_wiring.py` discovered as both
`session_wiring` and `tests.fixtures.session_wiring`.
**Target:** one module identity for every file; no duplicate-source error; no
package-resolution regression to installed `fa`/untyped modules.
**Consumer:** `uv run mypy` in `just typecheck` and CI sanity-check.
**Negative proof:** remove the chosen mapping/package/config correction and
mypy must reproduce the duplicate identity error or a dedicated mapping test
must fail.

### CT2 — Optional integration dependency contract

**Type:** runtime import/dependency/type contract.
**Sites:** `src/fa/inner_loop/tools/read_file.py::_read_pdf_text`;
`src/fa/runtime/server.py` FastAPI import fallback;
`src/fa/runtime/__init__.py` `app=None` fallback.
**Target:** each supported optional backend has declared dependency metadata;
each unsupported/deferred backend has a typed adapter and structured warning or
result; deptry and mypy agree.
**Consumer:** `deptry src/`, mypy, read-file/runtime tests.
**Negative proof:** remove a declaration or optional fallback and the focused
missing-backend/deptry test must fail.

### CT3 — Compaction SSoT/deprecation contract

**Producer/state:** `FeatureFlags.context_compaction_enabled` declaration and
`ChainConfig.compaction_threshold`; `coder_loop.py` derives
`compaction_enabled = compaction_threshold is not None`.
**Consumer:** compaction branch, dead-flag checker, config loader, operator
warnings, S14 tests.
**Target:** deprecated field retained or removed according to Q3; no production
read of deprecated field if retained; checker cannot silently classify
intentional compatibility as dead.
**Negative proof:** change derivation to the deprecated field → S14 kill-check
fails; remove deprecated metadata → dead-flag compatibility test fails.

### CT4 — LogKind/console mirror contract

**Producer:** `EventLog.append(kind=...)` and `output.emit(OutputEvent(...))`
call sites in `src/fa`.
**Consumer:** `ConsoleRenderer` handlers and `CONSOLE_MIRROR_KINDS`.
**Target:** parser recognizes the actual AST/data shape or fails closed with a
structured diagnostic; all mirror kinds have producer and consumer evidence.
**Negative proof:** remove a mirror producer or alter the declaration fixture;
contract test must fail.

### CT5 — Ruff policy contract

**Producer:** source/test code and explicit waiver comments.
**Consumer:** `ruff check`, `ruff format --check`, suppression scanner,
human review.
**Target:** no global E501 bypass; production complexity/security findings are
fixed or locally justified; intentional `noqa` includes a reason and is
visible to review.
**Negative proof:** remove a required decomposition or waiver and the focused
Ruff command must fail.

### CT6 — Coverage/live-path contract

**Producer:** shipped roots (`drive_session`, `run_session`, CLI, tools,
providers, runtime).
**Consumer:** pytest/coverage gate and operator-visible structured oracles.
**Target:** >=86% branch/line gate with meaningful C1/C2/C3 tests.
**Negative proof:** remove a producer call/event or security gate and its
kill-check must fail; coverage alone is not sufficient.

### CT7 — Test-edit exception contract

**Producer:** `pr.prepare` trusted draft with `TEST-EDITS`; classifier derives
intent; `IntentGuard.handle` and commit hook call validator.
**Consumer:** mutation tool admission and commit admission.
**Target:** justified test modifications remain possible; delete/rename cannot
be excused; typed intent cannot disarm classifier intent.
**Negative proof:** remove `TEST-EDITS` from a declared existing-test edit and
C1 harness/validator tests must deny.

---

## 5. ORDERED IMPLEMENTATION STEPS

### S0 — Baseline freeze and claim evidence

**Depends on:** none.
**Goal links:** G1–G6.
**Files:** no product change; workplan/evidence logs only.

**Do:**

1. Run `uv run just agent-bootstrap` and capture the ready marker.
2. Capture `uv lock --locked`, focused gates, `uv run just test`, Ruff, deptry,
   and mypy outputs.
3. Store the exact baseline in the implementation PR notes.
4. Verify no other agent’s broad unreviewed diff is silently mixed into the
   slice.

**Exit:** reproducible evidence exists; worktree ownership is clear.

### S1 — Decide and implement canonical mypy mapping

**Depends on:** Q2.
**Goal links:** G1.
**Files:** `pyproject.toml`, `tests/fixtures/session_wiring.py`, possibly
`tests/__init__.py`/`tests/fixtures/__init__.py` as NEW; tests for mapping if
needed.

**Preferred design:** explicit package identity with the smallest configuration
that preserves editable `src/fa` resolution. Test package markers are acceptable
only if they do not cause the repository to resolve `fa` as installed/untyped.
Do not use `--explicit-package-bases` blindly; verify package roots first.

**Do:**

1. Choose one package topology and document why it maps both `tests.*` imports
   and `src/fa` to the checkout.
2. Add only the package markers/config required by that topology.
3. Add a C0 import/mapping check only if ordinary mypy output cannot prove the
   contract clearly.
4. Run mypy in a clean `.venv`, not against stale installed artifacts.

**Exit:** duplicate identity is gone; `uv run python -c` resolves `fa` to
`src/fa`; no broad installed-package errors appear solely because of mapping.

**Kill-check:** remove the package/config mapping and the dedicated typecheck
command must fail with the duplicate identity error.

### S2 — Close production mypy in batches

**Depends on:** S1.
**Goal links:** G1, G2, G6.
**Files:** only touched files from the current `mypy src` report. Initial
clusters:

- `src/fa/inner_loop/coder_loop.py` — narrow `EventLog | None` at composition
  root, not repeated `# type: ignore`;
- `src/fa/inner_loop/loop.py` — payload/result narrowing;
- `src/fa/inner_loop/tools/run_bash.py` — typed subprocess result protocol;
- `src/fa/inner_loop/tools/__init__.py` — optional builder typing;
- `src/fa/runtime/pty_pool.py` — server narrowing and pexpect boundary;
- `src/fa/runtime/server.py`/`runtime/bash_executor.py` — fallback adapter
  types and `Any` containment;
- `src/fa/inner_loop/tools/observability.py`, `edit_file.py`, `profiles.py`,
  `instant_grep.py`, `spawn_subagent.py`, `subagent_envelope.py` — annotations,
  event-kind typing, and unused ignores;
- `src/fa/blackboard/blackboard.py`, `skills/loader.py` — local annotation and
  stale ignore.

**Do:**

1. Group changes by seam, not by all-file formatter pass.
2. Introduce small `Protocol`/typed adapter boundaries where external APIs
   are genuinely untyped.
3. Narrow `Optional` values at the composition root once, then pass a concrete
   value downstream.
4. Replace dynamic string event kinds with the existing `LogKind` contract or
   a validated conversion function.
5. Remove unused ignores; each retained ignore names the exact error code and
   rationale.

**Tests-writing proof:** every session/loop behavior change gets C1 tests using
real `EventLog`, `HookRegistry`, and mocked provider I/O. Event changes require
producer + consumer and path inventory. Runtime/security changes require C3
adversarial cases.

**Exit:** `uv run mypy src` passes for the current production scope; no blanket
`ignore_errors`, `follow_imports=skip`, or test exclusion is introduced.

### S3 — Resolve optional integration policy and deptry

**Depends on:** Q1, S2 as needed.
**Goal links:** G2, Pillar 2.
**Files:** `pyproject.toml`, `src/fa/inner_loop/tools/read_file.py`,
`src/fa/runtime/server.py`, `src/fa/runtime/__init__.py`, dependency contract,
focused tests.

**Decision branches:**

- If PDF is v0.1-supported: declare `pymupdf`/`pdfminer.six`/`pypdf` according
  to the actual supported fallback set, lock them, and test each supported
  backend path.
- If PDF is v0.2/deferred: remove or isolate the dormant extractor from the
  v0.1 dependency scan, emit a deterministic `unsupported_format` result, and
  do not pretend the feature is supported.
- If FastAPI runtime is v0.1-supported: declare it and pydantic; add C2 help/
  import and C3 endpoint boundary tests.
- If deferred: move the server behind an explicit optional extra/module boundary
  with a typed `app: object | None` contract and a visible unavailable status.
- For `requests`: either declare it directly because `bash_executor.py` uses
  it, or replace the direct import with the project’s existing transport layer;
  do not suppress DEP003 merely because another package happens to install it.

**Exit:** `uv run deptry src/` passes for a principled reason; lock, dependency
contract, runtime imports, and tests agree.

### S4 — Close SSoT/dead-flag contract

**Depends on:** Q3.
**Goal links:** G4.
**Files:** `src/fa/feature_flags.py`, `scripts/check_dead_flags.py`,
`tests/test_s14_compaction_ssot.py`, `tests/test_dead_flags.py`, config tests.

**Preferred design:** define deprecation metadata in one authoritative place
or derive checker treatment from the field declaration/config schema. A checker-
local allowlist is acceptable only if its parity is tested and documented as a
compatibility exception.

**Do:**

1. Pin field status: active, deprecated-retained, or removed.
2. Ensure config loader accepts legacy input if compatibility is retained.
3. Ensure production never reads deprecated compaction flag.
4. Ensure dead-flag output distinguishes deprecated-retained from active-dead.
5. Cover `FeatureFlags()` defaults, legacy config, threshold present/absent,
   and all compaction paths.

**Tests-writing proof:** C0 checker schema tests plus C1 `drive_session` matrix:
compaction threshold absent, present, successful reclaim, residual stage 3,
and circuit breaker. Producer kill-checks target `output.emit` and log writes.

**Exit:** S14, dead-flag, observability edge tests, and contract check pass;
removing the SSoT derivation fails.

### S5 — Repair log-kind checker robustness and Ruff findings

**Depends on:** S2.
**Goal links:** G3, G6.
**Files:** `scripts/check_log_kind_contract.py`,
`tests/test_check_log_kind_contract.py`, `src/fa/output.py` only if the
contract declaration itself needs a minimal structural normalization.

**Do:**

1. Rename function-local `KIND_TO_EVENT_TYPE` to `kind_to_event_type`.
2. Add parser fixtures for multiline `frozenset`, typed annotations, comments,
   trailing commas, and format changes.
3. Prefer a small AST literal extractor for `CONSOLE_MIRROR_KINDS`; if regex is
   retained, document exact accepted syntax and fail closed on unsupported
   syntax.
4. Preserve dual-write and producer/consumer checks.

**Exit:** current 23 focused tests pass; parser mutation/format fixtures fail
when the declaration cannot be understood; no false “pass” on an empty match.

### S6 — Ruff production-risk batches

**Depends on:** S2–S5.
**Goal links:** G3, Pillar 1.

**Batch order:**

1. `BLE001`, `S110`, `C901`, `RUF012` in production control/runtime paths;
2. event/log and checker code;
3. optional dependency adapters;
4. imports/naming/test mechanics;
5. line-length cleanup.

**Policy:**

- no global E501 ignore;
- long prompts/string literals may use local formatting or a narrowly scoped
  line-local waiver with rationale;
- broad exception handling must catch the narrowest known exception or carry a
  precise reason explaining why observability/fail-open semantics require it;
- decompose functions above complexity 15 where behavior can remain stable;
- use `ClassVar[tuple[...]]` or immutable tuple for immutable compaction stages;
- run `just fix` only on the touched slice and inspect its diff.

**Exit:** Ruff passes with no unreviewed blanket suppressions; each waiver is
reported by protected-path suppression review and has a rationale.

### S7 — Canonical test package/fixture typing

**Depends on:** S1, S2.
**Goal links:** G1, G6.
**Files:** `tests/fixtures/session_wiring.py`, package markers/config selected by
S1, then test files in bounded groups.

**Do:**

1. Type fixture factories first: real `ChainConfig`, `ProviderChain` mock
   boundary, `SessionState`, `EventLog`, tool-call tuples.
2. Add return annotations to test functions in touched groups.
3. Parameterize generic containers and use structured result types instead of
   `object`.
4. Replace incompatible monkeypatches with typed test doubles/protocols.
5. Fix synthetic event kinds through the production event contract; do not add
   arbitrary `LogKind` values solely for tests.

**Tests-writing proof:** fixtures remain type-honest; no mocked frozen dataclass
configs; C1 roots remain real and provider I/O remains mocked.

**Exit:** full `uv run mypy` passes without excluding tests. Run in groups to
keep diffs reviewable and rollbackable.

### S8 — Coverage closure through live paths

**Depends on:** S2–S7.
**Goal links:** G5, Pillars 3–4.
**Files:** coverage-selected modules; likely low-coverage runtime/tools/stats
surfaces shown by `coverage.xml`. Exact file list is generated after S0/S2,
not guessed now.

**Do:**

1. Use coverage report to select high-risk, low-covered shipped paths.
2. Prefer C1 `drive_session`/CLI tests over direct helper invocation for product
   claims.
3. Add C3 adversarial cases for sandbox, secrets, TCB, and proxy boundaries.
4. Assert structured events/outcomes/call counts/FS effects.
5. Run mutation only after C1 paths are green; survivors become follow-up
   strengthening tasks.

**Exit:** `uv run just test` passes at >=86%; no exclusions or threshold change;
coverage XML exists; every new test has a meaningful oracle and, for event
claims, a producer kill-check.

### S9 — Final CI/harness simulation

**Depends on:** S1–S8 and Q5.
**Goal links:** G1–G6.

**Do:**

1. fresh workspace setup via `just agent-bootstrap`; require
   `FA_AGENT_READY=1`;
2. simulate agent edit with `pr.prepare` and `TEST-EDITS` where needed;
3. run `just fix` only for changed slices;
4. run `uv run just check`;
5. verify pre-commit/pre-push/commit hooks and hook status;
6. verify CI workflow parsing, required check names, dependency contract, and
   authoring workflow no-path-filter test;
7. record emergency human merge override as external GitHub policy, not an
   agent capability.

**Exit:** all local blocking gates pass; CI-only jobs are separately classified;
no ready marker is emitted when bootstrap/status fails; final diff is scoped.

---

## 6. TEST PLAN BY PYRAMID

### Pyramid A — deterministic harness / CI

| ID | Class | Root/scope | Oracle | Negative proof |
|---|---|---|---|---|
| T1 | C0 | mypy module mapping | no duplicate module; `fa.__file__` under `src` | remove mapping |
| T2 | C0/C2 | deptry/optional imports | exit code + structured unavailable result | remove declaration/fallback |
| T3 | C0 | dead-flag schema | active/deprecated/dead classification | remove metadata |
| T4 | C1 | `drive_session` compaction matrix | event kind/fields, outcome, request count | remove producer emit/SSoT derivation |
| T5 | C0/C2 | log-kind checker | exit code + producer locations | alter declaration/parser fixture |
| T6 | C3 | TCB/sandbox/secret boundaries | deny code/reason; no provider call | remove gate |
| T7 | C1/C2 | PTY lifecycle | thread stopped, exit code, output | restore competing expect |
| T8 | C1/C2 | test-edit guard | allow declared edit; deny undeclared/delete | remove validator call |
| T9 | C2 | agent bootstrap | exact `FA_AGENT_READY=1` only on success | force hook-status failure |

### Pyramid B — model quality/evals

Not part of this plan’s blocking gate. No real provider calls are required.
Model-quality evals remain separate from deterministic wiring/static checks.

---

## 7. RISKS, ROLLBACK, AND CONTROLS

| ID | Risk | Mitigation | Rollback |
|---|---|---|---|
| RK1 | package markers alter import/install semantics | verify `fa` path and clean env before merging | revert S1 only |
| RK2 | optional dependency policy accidentally expands v0.1 | Q1; use explicit deferred adapter if unsupported | revert S3 |
| RK3 | global Ruff ignore hides AI defects | forbid global ignore; suppression scanner | revert config change |
| RK4 | checker regex silently passes empty declaration | fail closed + parser fixtures | revert S5 |
| RK5 | test edits weaken assertions | TEST-EDITS, C1 oracles, mutation follow-up | revert test slice |
| RK6 | coverage tests become line theater | structured oracles and producer kill-check | revert tests |
| RK7 | strict mypy scope grows beyond review capacity | batch S2/S7 and keep plan status DRAFT/blocked | revert batch |
| RK8 | human emergency merge bypass becomes agent bypass | GitHub permission separation; manual audit | revoke agent bypass |
| RK9 | bootstrap depends on unavailable `just`/`uv` | trusted runner preinstalls tools; bootstrap fails closed | no ready marker |

---

## 8. DEFINITION OF DONE

The implementation is not DONE until every checklist item below passes. The plan
is READY because policy decisions are resolved and all remaining work is
expressed as executable steps with contracts and negative proofs.

Final implementation DoD:

- [ ] `just agent-bootstrap` succeeds and emits `FA_AGENT_READY=1`.
- [ ] missing/stale hook status prevents readiness.
- [ ] canonical mypy mapping is documented and duplicate identity is gone.
- [ ] `uv run mypy src` passes.
- [ ] full `uv run mypy` passes without excluding tests or disabling strictness.
- [ ] optional imports have an explicit v0.1 support/defer policy.
- [ ] `uv run deptry src/` passes without unjustified ignores.
- [ ] SSoT/deprecated flag contract has one authoritative metadata source.
- [ ] S14 and compaction C1 path matrix pass.
- [ ] log-kind parser has negative fixtures and contract check passes.
- [ ] Ruff passes without global E501/security/complexity suppression.
- [ ] authoring check, producer/consumer contract, and no-mocked-dataclasses
      checks pass.
- [ ] full pytest has zero failures and coverage >=86%.
- [ ] C1 producer kill-checks cover all changed observable paths.
- [ ] C3 adversarial tests cover relevant security boundaries.
- [ ] mutation survivors are triaged after C1, not hidden by coverage.
- [ ] CI required-check names and emergency human override are verified in
      GitHub settings; agent has no bypass permission.
- [ ] final diff is scoped, no formatter churn remains, and all links/contracts
      pass.

### Final proof format required from executor

```text
LIVE-PATH PROOF:
- root: drive_session | run_session | cli:<subcommand> | just:agent-bootstrap
- test: tests/<file>.py::test_<name> or command
- matrix: <explicit rows covered>
- oracle: event:<kind> | outcome:<stop_reason> | call_count | deny code | FS
- kill-check: removing <producer/config/check> fails <named verification>
- producer: <file.py>:<line/symbol>
- consumer: <file.py>:<line/symbol or checker>
- paths-covered: N/M
- contract-check: PASS | FAIL
- efficiency: call_count=N | early-stop | n/a
- pyramid: A
```

---

## 9. HISTORICAL DECISION QUIZ — RESOLVED, RETAINED FOR AUDIT

These questions were answered during plan review. The original options remain
for auditability; the canonical decisions are recorded in §16 and supersede
these alternatives.

### Q1 — Optional integrations

Which is the intended v0.1 contract?

- **Q1-A:** PDF extraction and FastAPI runtime are supported now; add direct
  dependencies and lock them.
- **Q1-B:** Both are deferred; isolate them as explicit optional adapters and
  return structured `unsupported` diagnostics when unavailable.
- **Q1-C:** PDF is deferred, FastAPI is supported.
- **Q1-D:** PDF is supported, FastAPI is deferred.

### Q2 — Mypy rollout

Which merge policy do you want while the backlog is closed?

- **Q2-A:** Keep `just typecheck` blocking and close all production + tests in
  one large PR.
- **Q2-B:** Temporarily split the gate: `mypy src` blocking, full test typing
  advisory but tracked, then promote full strict mypy after S7.
- **Q2-C:** Keep full strict mypy blocking, but execute S2/S7 as multiple small
  PRs while the branch remains red between PRs.

Historical recommendation only; final decision is Q2-A (full strict mypy blocking).

### Q3 — Deprecated compaction flag

Should `context_compaction_enabled` remain in the public frozen config?

- **Q3-A:** Retain indefinitely for backward compatibility; classify it as
  deprecated-retained via one authoritative metadata source.
- **Q3-B:** Retain for one documented deprecation window, emit a warning when
  configured, then remove in a versioned migration.
- **Q3-C:** Remove now and migrate config/tests immediately.

Historical recommendation only; final decision is Q3-C-style reduced surface: remove the redundant boolean and use threshold presence as the SSoT enable switch.

### Q4 — Ruff E501

Which line-length policy is intended?

- **Q4-A:** Keep E501 blocking everywhere; wrap strings/prompts and use rare
  line-local waivers with rationale.
- **Q4-B:** Keep E501 blocking in production; allow a narrowly scoped per-file
  ignore for generated/prompts/tests, with suppression review.
- **Q4-C:** Disable E501 globally.

Historical recommendation only; final decision is Q4-B: production E501 remains blocking with narrow approved exceptions.

### Q5 — External GitHub controls

What is the current GitHub authority model?

- **Q5-A:** You are the only code owner/maintainer; agent account has PR-only
  rights and no bypass.
- **Q5-B:** There are multiple maintainers; provide the owner/team slug and
  required check names so CODEOWNERS/ruleset can be verified.
- **Q5-C:** GitHub settings are not yet configured; plan the settings checklist
  but do not claim merge protection.

Please also state whether the agent is allowed to modify `pyproject.toml`,
`justfile`, `.github/workflows/*`, and `.fa/dependency_contract.toml`, or must
stop with `manual_operator_approval_required` for some/all of them.

---

## 10. PLAN STATUS

`READY`. Q1–Q5 are resolved. Execute S0–S9 in order, re-running the relevant
preflight before each slice. Intermediate local red states are expected during
the single coordinated closure branch; the merge candidate must satisfy the
full DoD. External GitHub settings are an explicit S9 operator task, not an
unresolved product-policy question.

## 11. OPERATOR ANSWERS RECEIVED (historical review record)

- **Q1:** Defer PDF extraction and FastAPI runtime for v0.1. The FastAPI
  rationale is ADR-14 (named ADR-13 in its title): chosen EventStream Runtime
  architecture using FastAPI + libtmux/PtyPool for stateful bash, motivated by
  OpenHands/OpenCode-style persistent PTY execution. It is a real architectural
  decision but not required to make the v0.1 core coding/PR path depend on the
  server. S3 must isolate the deferred runtime and avoid accidental dependency
  promotion.
- **Q2:** Full strict mypy remains blocking. S1–S7 must be executed as one
  coherent closure change or one coordinated branch; intermediate red commits
  are acceptable during development but the merge candidate must pass the full
  gate. No test exclusion or strictness reduction is allowed.
- **Q3:** Remove `context_compaction_enabled` now. This supersedes the
  compatibility-retention branch in S4: implement an explicit config migration
  or deterministic rejection/warning for legacy input, remove the dataclass
  field and checker exception, update all construction sites/tests, and retain
  `compaction_threshold` as the sole source of truth. This is a potentially
  breaking public-config decision and must be verified before execution.
- **Q4:** Operator selected global E501 disable. This is recorded as a
  **red-flagged decision**, not accepted as safe by default: global suppression
  conflicts with the current Ruff drift-stop policy and removes a useful
  anti-sloppiness signal. Before implementation, the developer team must either
  explicitly accept the risk and update the policy/guardrail tests, or revise to
  Q4-A/Q4-B. No executor may silently add the global ignore merely because it
  appeared in the other agent's report.
- **Q5:** GitHub settings are not configured; there is currently one maintainer.
  The plan must include manual setup instructions and must not claim merge
  protection until settings are verified. The human emergency failed-CI merge
  override remains intentional; the agent account must have no equivalent
  bypass.

### Manual GitHub settings checklist to execute outside the repo

1. Settings → Rules → Rulesets (or Branch protection rules) → target `main`.
2. Require pull request before merge.
3. Require at least one approval and enable **Require review from Code Owners**.
4. Require exact checks after observing their actual GitHub names:
   `Advisory CI / sanity-check`, `Advisory CI / audit`,
   `Advisory CI / gitleaks`, and `Authoring Guardrails / authoring-check`.
5. Require branch up-to-date before merge and dismiss stale approvals.
6. Restrict bypass actors to the human maintainer; do not grant the agent
   account administrator/ruleset bypass or merge permission.
7. Keep the maintainer's explicit emergency override available and document
   every such override in the PR/merge record.
8. Confirm CODEOWNERS routes the protected workflow/TCB files to the maintainer.
9. Verify a test PR that changes `.github/workflows/authoring-guardrails.yml`
   requests the maintainer and cannot be merged by the agent.
10. Verify the maintainer can still intentionally override a failed required
    check when operationally necessary.

### Plan promotion condition

Q1–Q6 policy decisions are specified. The plan is `READY` for developer-team
review and execution. S0 requires a fresh preflight; S9 requires manual GitHub
ruleset verification. Those are implementation steps, not unresolved questions.


## 12. FINAL POLICY CLARIFICATIONS

- **Legacy `context_compaction_enabled`:** after removal from the frozen
  `FeatureFlags` public surface, legacy config keys are accepted only as an
  observable deprecation warning and ignored for behavior. They MUST NOT be
  mapped to an invented threshold. `compaction_threshold` is the sole SSoT.
  The warning must reach the existing config warning return surface and the
  current session observability path (log/event/session DB) without exposing a
  second runtime decision.
- **Ruff E501:** keep E501 blocking in production/checker code. Approved long
  text/test surfaces may use narrow, documented exceptions; no global ignore.
- **FastAPI/PDF:** deferred from v0.1; optional boundaries must remain
  import-safe and observable, while ADR-14 remains a future runtime capability
  rather than an accidental dependency of the core agent.
- **Mypy:** full strict mypy remains blocking for the merge candidate; no
  exclusion of tests or global strictness weakening.
- **GitHub merge:** normal required checks remain enforced; a human maintainer
  retains the explicit emergency failed-CI override; the agent has no bypass.

### Revised S4 contract

`FeatureFlags.context_compaction_enabled` removal is a migration, not a field
delete. The executor must:

1. remove the field from `FeatureFlags`, `as_dict`, known-key schema, and
   fail-open/closed categorization;
2. make the loader recognize the legacy key as deprecated input, omit it from
   resulting flags, and append a structured warning;
3. route that warning through the existing config/session observability path
   (warning surface → EventLog/session DB and OutputEvent where the current
   contract requires console mirroring);
4. preserve `compaction_threshold` as the only branch decision;
5. update all tests/config fixtures to use the threshold;
6. add a negative test proving legacy `true` and `false` values cannot alter
   compaction behavior;
7. add a producer kill-check for the warning/event path and a consumer check for
   its operator/session visibility.

The S4 step remains blocked until the executor verifies the exact warning/event
producer and consumer sites against the current source tree.

## 13. SUPERSEDED COMPACTION INTERPRETATION — RETAINED FOR AUDIT ONLY

The earlier S4/Q3 direction to remove `context_compaction_enabled` is
**superseded by verified operator intent**. The feature has not yet had a real
live test, and the intended product contract is an explicit operator switch.

### Current implementation defect

`context_compaction_enabled` is parsed and stored but never participates in the
compaction decision. The actual decision is currently:

```python
compaction_enabled = compaction_threshold is not None
```

This creates the verified truth table:

| `context_compaction_enabled` | `compaction_threshold` | Current behavior | Intended behavior |
|---:|---:|---|---|
| false | absent | off | off |
| true | absent | off | on using dynamic threshold |
| false | present | on | off |
| true | present | on | on using configured threshold |

### Corrected contract

- `context_compaction_enabled` is the **single enable/disable flag**.
- `compaction_threshold` is a **numeric tuning override**, not an enable
  surrogate.
- `context_budget_enabled` remains the outer budget-observation gate.
- Recommended defaults: budget enabled; compaction disabled unless explicitly
  enabled, because compaction changes conversation state and can invoke a
  model. This default must be confirmed against operator expectations before
  implementation.
- If compaction is enabled and threshold is absent, `ContextBudget` uses its
  existing dynamic default (`min(80% of context_limit, 150000)`).
- If compaction is disabled and a threshold is configured, the system must not
  compact; it should emit an explicit structured warning that the threshold is
  ignored because the feature is disabled.
- No legacy migration/removal is required for this flag because the intended
  API is to restore it as active behavior.

### Observability contract correction

`compaction_warning` is currently written to EventLog/session DB and parsed by
stats, but it is not in `CONSOLE_MIRROR_KINDS`, has no
`ConsoleRenderer._handle_compaction_warning`, and has no corresponding
`OutputEvent` producer. Therefore the explicit enable/disable fact is not
fully visible through the EventBus/operator console.

The corrected observable path is:

```text
FeatureFlags + ChainConfig
  → coder_loop enablement decision
  → EventLog.append(kind="compaction_warning", fields={enabled, threshold, action})
  → session.db event_log row + JSONL mirror
  → output.emit(OutputEvent(type="compaction_warning", same fields))
  → ConsoleRenderer._handle_compaction_warning
  → stats.parse_session / operator report
```

The producer and consumer must share the same structured fields. If the event
is not intended for normal console detail, the consumer may render it only at
standard/debug detail, but the EventBus contract must still exist and be
verified.

### Required C1 matrix

Use the real `drive_session` root, real `FeatureFlags`, real `ChainConfig`,
real `EventLog`, real `EventBus`, and mocked provider/compactor I/O:

| Row | Flag | Threshold | Required proof |
|---|---:|---:|---|
| C1-A | false | absent | no compaction start producer; warning says disabled; DB/log + EventBus agree |
| C1-B | false | present | threshold does not enable compaction; warning identifies ignored threshold |
| C1-C | true | absent | compaction start producer fires using dynamic threshold |
| C1-D | true | present | compaction fires using exact configured threshold |

Add the error/circuit-breaker path for both enabled rows and verify provider
call count/early-stop behavior. Add an adversarial case where a threshold is
present but the flag is false; this is the key regression against the current
implementation.

### Required producer/consumer tests

- **C1 producer:** removing the `output.emit(OutputEvent(type="compaction_warning"))`
  call fails the row-specific test.
- **C0/C1 consumer:** removing `_handle_compaction_warning` fails the renderer
  visibility test, paired with the producer test.
- **Dual-write:** removing `EventLog.append(kind="compaction_warning")` fails
  the session DB/log assertion.
- **Stats:** removing the parser branch fails the structured analytics test.
- **Config:** `FeatureFlags.as_dict()` and loader tests assert the flag value;
  no threshold-presence inference is permitted.

### Revised S4 implementation sequence

1. Restore the feature flag as active contract; remove `DEPRECATED` status and
   the checker exemption.
2. Resolve its default and fail-open/closed category consistently.
3. Change `coder_loop.py` to derive enablement from the flag and threshold only
   as tuning input.
4. Add/repair the `compaction_warning` EventBus producer and renderer consumer.
5. Verify EventLog → session DB and JSONL mirror consistency.
6. Update stats parsing/reporting to preserve enabled/disabled/threshold fields.
7. Replace static S14 tests that assert the flag is unread with live C1 matrix
   tests; retain a source-level negative test that threshold presence alone
   cannot enable compaction.
8. Run the real compaction path with a deterministic fake compactor/provider,
   then a manual live provider smoke test only after offline C1 passes.

This correction aligns with Pillar 2 (operator-usable coding product), Pillar 4
(measurement), and compliance-by-construction. It rejects the previous S14
interpretation because that interpretation contradicted the operator's actual
feature intent.

## 14. HIGH-ROI PLAN GAPS FOUND AND ADDED (CANONICAL)

### H1 — Plan must distinguish “configured” from “enabled”

The earlier plan treated `compaction_threshold` as an enable signal. Any plan
for a feature flag must specify which input is the decision and which inputs
are tuning. Truth tables are now mandatory in `tests-writing` and this plan.

### H2 — Warning-only logging is not enough

`logger.warning()` does not satisfy the session authority contract. A warning
claim must trace to EventLog/session DB and, where operator-visible behavior is
claimed, EventBus/renderer. The plan now requires producer, consumer, dual-write,
and stats verification.

### H3 — “Real compaction” was not proven

Existing tests mock `ContextBudget`/compactor branches. They prove branch
wiring but not the real configured flag behavior. C1 must use real config,
real budget, real log/bus, and only mock provider I/O/compactor network behavior.
A separate manual live-provider smoke test is non-blocking and follows offline
C1.

### H4 — Config loader warnings are not session-observable

`SessionState.__post_init__` currently logs feature-flag warnings with Python
`logger.warning()` but does not append a structured EventLog/session DB event.
Any future deprecation/unknown-flag work must close this gap or explicitly
state why config-load warnings are outside session authority.

### H5 — Deptry policy must not be replaced by ignore lists

The current nine deptry issues are useful signals: direct imports of fitz,
pdfminer, pypdf, FastAPI, Pydantic, and requests require a v0.1 support/defer
policy. The plan now requires a runtime adapter contract, not only a deptry
ignore.

### H6 — Gate policy must be tested as a system

A quality gate can be green while not running the intended code. Each gate plan
must include command invocation, clean pass, synthetic failure, and CI workflow
wiring. The claim “Ruff/mypy/coverage protect PRs” is incomplete without the
negative proof that removing the producer/config/check causes failure.

### H7 — Skills are now updated with executable examples

`knowledge/skills/tests-writing/SKILL.md` now includes examples for:

- typed composition-root boundaries and exact mypy ignores;
- optional dependency/runtime policy alignment;
- flag-vs-threshold truth-table tests;
- observable configuration migration;
- gate self-tests;
- live-path feature completion.

`knowledge/skills/plan-authoring/SKILL.md` now requires forensic verification of
past-tense agent claims before a plan can become READY.

### H8 — Dependency contract is not in the authoritative `just check` chain

`tests/test_s15_dependency_contract.py` and the standalone script exist, but
`justfile::check` currently invokes `contract-check` for the producer/consumer
EventType contract, not `scripts/check_dependency_contract.py`. Therefore a
future dependency contract drift can pass the named `just check` recipe unless
pytest happens to execute the S15 tests.

Required closure:

- add a distinct `dependency-contract-check` recipe with an unambiguous name;
- include it in `just check` after lock-check and before lint/type gates;
- invoke the same recipe in CI and test its workflow wiring;
- retain focused clean/unknown/missing-contract tests;
- ensure `.fa/dependency_contract.toml` is tracked and protected.

Negative proof: remove the contract entry or add an undeclared direct import;
`just check` must fail before the PR gate reports success.

### H9 — Stale gate documentation is a control-plane risk

`pyproject.toml` coverage comments still describe a temporary 89/90% history
while the active threshold is 86%. `knowledge/ci-guardrails-reference.md` also
contains historical gate language. This can cause an agent to follow the wrong
threshold or claim a gate is stronger than it is.

Required closure:

- make active threshold and rationale single-source in pyproject plus generated/
  checked documentation, or update docs in the same PR;
- add a test that reads `fail_under` and checks the documented gate value;
- add a workflow/justfile contract test proving the named gate is invoked;
- record ratchet policy and the next increase trigger explicitly.

Negative proof: alter `fail_under` or remove the recipe invocation; the policy
contract test must fail.

## 15. FINAL COMPACTION SSoT DECISION — REDUCED SURFACE

The operator clarified the final intent: do **not** retain a redundant
`context_compaction_enabled` flag. `compaction_threshold` presence is the
explicit enable switch and its value tunes the threshold. This is the preferred
minimalism-first design.

This supersedes the immediately preceding “restore active boolean flag” note.
The executor must not implement both controls.

### Final contract

```python
compaction_enabled = provider_chain.config.compaction_threshold is not None
```

| Threshold input | Behavior |
|---|---|
| absent | compaction disabled; no compaction producer; structured disabled/unconfigured observation |
| valid positive integer | compaction enabled; exact value controls Stage 2 threshold |
| zero/negative/above context limit | configuration validation fails or emits a structured diagnostic; never silently enables |
| legacy `context_compaction_enabled` key | warning emitted; key ignored; threshold remains sole decision |

### Required implementation

1. Remove `context_compaction_enabled` from `FeatureFlags`, `as_dict`,
   `_KNOWN_FLAGS`, fail-open/closed categorization, checker exemptions, and
   all fixtures/tests/docs that claim it is a current flag.
2. Retain legacy-key recognition only as a parser warning if backwards
   compatibility requires accepting old config files. The warning must be
   observable through the existing structured config/session path; the key
   must not affect `ChainConfig` or `ContextBudget`.
3. Add explicit comments at the `ChainConfig`/`ContextBudget` decision site and
   operator documentation: **`compaction_threshold` presence toggles the
   compaction module; the numeric value tunes the threshold.**
4. Verify the existing `ChainConfig.validate()` range rules are reached from
   every shipped config/CLI composition root; add a negative C2 test if an
   invalid threshold can currently bypass validation.
5. Add C1 tests for threshold absent/present and C3-style malformed/out-of-range
   config cases using real `drive_session`, EventLog, EventBus, and session DB.
6. Replace S14 tests asserting the deprecated field must remain with tests that
   prove no production code reads the legacy key and threshold presence is the
   only enablement source.
7. Preserve `compaction_warning` structured fields (`enabled`, `threshold`,
   `action`, `reason`) across EventLog/session DB/JSONL, EventBus, renderer, and
   stats. Add the missing producer/consumer mirror if the operator wants the
   enable/disable fact on the console.

The plan is now consistent with the operator’s clarified product goal: one
configuration surface, observable behavior, no redundant boolean.

## 16. CANONICAL RESOLUTION AND READINESS AUDIT

This section is authoritative when earlier historical sections conflict.

### Resolved decisions

- **Q1:** PDF extraction and FastAPI runtime are deferred from v0.1. Their
  optional boundaries remain import-safe and observable; ADR-14 remains future
  runtime architecture, not a core dependency.
- **Q2:** full strict mypy remains blocking; no exclusion of tests or global
  strictness weakening.
- **Q3:** `context_compaction_enabled` is removed as redundant surface. The
  presence of `compaction_threshold` is the sole enable switch and its value
  tunes the threshold. Legacy boolean input is warned/ignored if accepted.
- **Q4:** E501 remains blocking in production/checker code. Only narrow,
  documented exceptions may be used for approved long-text/test surfaces.
- **Q5:** GitHub settings are not yet verified. There is one maintainer; the
  agent has no bypass/merge permission; the maintainer retains an intentional
  emergency failed-CI merge override. GitHub settings are executed as S9.
- **Q6 (implicit default):** threshold absent means compaction disabled. No
  separate default boolean is needed.

### Canonical compaction contract

```python
compaction_enabled = provider_chain.config.compaction_threshold is not None
```

The executor MUST NOT restore a second boolean enable flag. It MUST remove the
legacy field/schema surface, warn and ignore legacy input, and prove the
threshold-absent/present/invalid matrix through real C1 composition-root tests.
The explicit enabled/disabled fact must be dual-written to EventLog/session DB
and EventBus/renderer where operator visibility is claimed, and remain present
in stats projection.

### Production-readiness audit

| Plan-authoring requirement | Status | Evidence |
|---|---|---|
| Every goal maps to code site | PASS | G1–G6 map to S1–S9 and named files/symbols. |
| Every goal maps to contract | PASS | CT1–CT7 plus H1–H9. |
| Every contract maps to verification | PASS | C0/C1/C2/C3 table and step exit criteria. |
| Negative proof/kill-check present | PASS | producer/config/check removal proofs specified. |
| Path/flag matrix present | PASS | compaction, optional integrations, event paths, typing gates. |
| Producer/consumer contract present | PASS | CT4 and compaction EventLog/EventBus/renderer/stats path. |
| Research/report claims dispositioned | PASS | claim table and RN1. |
| Open policy questions answered | PASS | Q1–Q6 canonical decisions above. |
| External prerequisites identified | PASS | GitHub settings are S9, not silently assumed. |
| No unresolved contradictory status | PASS | this section supersedes historical sections 9–15. |
| Fresh preflight requirement | PASS | S0 and executor handoff require it. |

**Final plan status: READY.** The plan is ready for developer-team review and
execution. It is not a claim that the implementation itself is complete; the
implementation becomes complete only when the DoD checklist passes.

## 17. EXECUTION UPDATE — S0 + COMPACTION C1

S0 baseline freeze completed in
`worklogs/implementation-plans/S0-baseline-2026-07-21.md` before compaction
edits. The compaction C1 slice then landed as a focused implementation:

- removed the redundant current `FeatureFlags.context_compaction_enabled` field;
- legacy config key is warned/ignored;
- threshold presence remains the sole enablement decision;
- added `compaction_warning` EventType producer/consumer dual-write;
- added console renderer consumer and log-kind mapping;
- added real-root C1 tests for threshold absent/present and C2 invalid values;
- added EventLog/session DB/EventBus/stats assertions;
- updated stale feature-flag test/config assumptions.

Verification:

```text
focused compaction/renderer tests: PASS
24 initial C1/C2 tests: PASS
full non-coverage pytest: 1786 passed, 13 skipped, 0 failed
just test: 1786 passed, 13 skipped; coverage 76.97% < 86% gate
authoring-check: PASS
log-kind contract: PASS
producer-consumer contract: PASS
no-mocked-dataclasses: PASS
```

The coverage gate and the pre-existing Ruff/mypy/deptry debt remain open and
are not silently reclassified as compaction failures.

## 18. EXECUTION UPDATE — STRUCTURED WARNING, DEPENDENCY GATE, TYPING BATCH 1

### Slice A — structured legacy-config warning

Implemented:

- `config_warning` added to `EventType` and `LogKind`;
- `SessionState._record_config_warning()` writes the authoritative EventLog/
  session DB row and queues an OutputEvent if CLI output is not wired yet;
- `SessionState.attach_output_bus()` flushes pending bootstrap warnings exactly
  once;
- CLI now attaches the bus through `attach_output_bus()`;
- `ConsoleRenderer._handle_config_warning()` consumes the event;
- log-kind and producer/consumer checkers include `state.py` as a producer path;
- C1 test proves the no-output-bus bootstrap window does not lose the warning;
- stats explicitly accounts for `config_warning` as operator-visible but not an
  analytics aggregate.

Verification:

```text
config warning/output/compaction focused tests: PASS
producer-consumer contract: PASS
log-kind contract: PASS
full pytest: 1791 passed, 13 skipped, 0 failures
```

### Slice B — dependency contract recipe wiring

Added:

```text
dependency-contract-check:
    python scripts/check_dependency_contract.py
```

and added it to the authoritative `just check` dependency chain immediately
after `lock-check`. Added C2 wiring tests proving the recipe, script, tracked
contract artifact, and check-chain membership agree.

Verification: recipe and wiring tests PASS.

### Slice C — production typing batch 1

Closed `src/fa/runtime/bash_executor.py` integration-boundary errors by adding
small structural protocols for the in-process pool/session and TypedDict casts
for the deferred remote response boundary. No global ignore or dependency
surface expansion was used.

Verification:

```text
mypy src/fa/runtime/bash_executor.py: PASS
PTY regression tests: PASS
```

Remaining production typing, Ruff, deptry, and coverage debt remains explicitly
open; no full-gate green claim is made.

## 19. EXECUTION UPDATE — TYPING BATCH 2

### Scope

Targeted the runtime/PTY boundary, the `run_bash.py` subprocess result
protocol, and nullable EventLog composition-root narrowing.

### Implementation

- Added `_PtySessionLike` and `_PtyPoolLike` protocols at the in-process
  executor boundary.
- Added typed remote response `TypedDict` projections and explicit casts in
  the deferred remote runtime adapter.
- Replaced `run_bash.py`'s dynamically-created empty `_Completed` class with a
  frozen slots dataclass carrying typed `stdout`, `stderr`, and `returncode`.
- Added `SessionState.require_log()` as the single fail-closed authority
  narrowing point.
- Narrowed EventLog once in `coder_loop.py` and `loop.py`, removing repeated
  nullable dereferences while preserving the existing `ValueError` contract
  for post-construction missing-log misuse.
- Narrowed parallel-loop payload/result locals to avoid mypy flow confusion and
  preserve denied/synthetic result behavior.
- Corrected the prompt-builder seam by converting the immutable rendered tool
  mapping tuple into the list-of-dicts type the prompt composer requires.

### Verification

```text
mypy targeted 4-file batch: PASS
  src/fa/runtime/bash_executor.py
  src/fa/inner_loop/tools/run_bash.py
  src/fa/inner_loop/coder_loop.py
  src/fa/inner_loop/loop.py

focused runtime/tool/loop tests: 41 passed
full pytest: 1791 passed, 13 skipped, 0 failures
dependency-contract-check: PASS
authoring-check: PASS
log-kind contract: PASS
producer-consumer contract: PASS
no-mocked-dataclasses: PASS
git diff --check: PASS
```

The remaining global quality debt is unchanged in category: full mypy still
has additional production files, Ruff remains red, deptry reports optional /
transitive dependency policy issues, and coverage remains below the 86% gate.
No global suppression or test exclusion was introduced.

## 20. EXECUTION UPDATE — TYPING BATCH 3

### Scope

Targeted the next production typing batch:

- `src/fa/runtime/pty_pool.py`;
- `src/fa/runtime/server.py`;
- `src/fa/inner_loop/tools/observability.py`;
- `src/fa/inner_loop/tools/edit_file.py`;
- `src/fa/inner_loop/tools/__init__.py`.

### Implementation

- Added tmux server/session capability protocols and narrowed the optional
  server reference after fallback checks.
- Removed an obsolete third-party import ignore at the PTY boundary.
- Added typed coercion for untrusted usage-event numeric payloads.
- Added a return type to the optional list-task DI helper.
- Typed edit-file session/blackboard helpers and removed inaccurate argument
  ignores.
- Declared lazy tool builders as optional callables with concrete signatures,
  preserving graceful import degradation while eliminating always-truthy and
  `None` assignment errors.
- Kept FastAPI/Pydantic optional and deferred from core dependencies; added
  typed endpoint return contracts and exact decorator boundary ignores only
  where the untyped optional framework requires them.

### Verification

```text
mypy targeted 5-file batch: PASS
focused runtime/tool/observability/edit tests: 79 passed
full pytest: 1791 passed, 13 skipped, 0 failures
dependency-contract-check: PASS
authoring-check: PASS
log-kind contract: PASS
producer-consumer contract: PASS
no-mocked-dataclasses: PASS
git diff --check: PASS
```

The global full mypy/Ruff/deptry/coverage gates remain open as tracked debt;
this batch introduces no test exclusions or blanket suppressions.

## 21. EXECUTION UPDATE — TYPING BATCH 4 / PRODUCTION MYPY CLOSED

### Scope

Closed the final production typing cluster:

- `src/fa/inner_loop/profiles.py`;
- `src/fa/inner_loop/tools/instant_grep.py`;
- `src/fa/blackboard/blackboard.py`;
- stale unused ignores in skills/runtime/subagent boundaries;
- `src/fa/inner_loop/tools/read_file.py` optional PDF return boundary;
- `src/fa/inner_loop/tools/spawn_subagent.py` typed `LogKind` emission.

### Implementation

- annotated profile builder factories, limited-write handler, and fallback
  containers with real `ToolSpec`/`ToolResult` signatures;
- annotated instant-grep fallback generator as `Iterator[Path]`;
- typed blackboard fallback query result list;
- removed unused ignores instead of replacing them with broader suppressions;
- cast the optional PDF extractor return at the external untyped boundary;
- typed dynamic subagent event kind as the existing `LogKind` union.

### Verification

```text
mypy src: PASS — 129 source files, zero errors
focused typing/security/tool tests: 61 passed
full pytest: 1791 passed, 13 skipped, 0 failures
authoring-check: PASS
dependency-contract-check: PASS
log-kind contract: PASS
producer-consumer contract: PASS
no-mocked-dataclasses: PASS
git diff --check: PASS
```

The production typing objective from S2 is now closed. Full test-tree mypy,
Ruff, deptry optional-dependency policy, and coverage remain separate quality
tracks; no global strictness weakening or test exclusion was used.

## 22. EXECUTION UPDATE — FULL TEST-TREE MYPY + RUFF SCOPED MECHANICS

### Full test-tree typing

Added explicit package markers for `tests`, `tests.fixtures`, and `scripts`,
removing the duplicate module identity barrier. Typed shared/test boundaries in
small groups:

- no-value test/helper return annotations;
- JSON/tool-wire fixtures with `Any` isolated at the data boundary;
- valid `LogKind` values in authority tests;
- typed `SessionDatabase`/EventLog assertions;
- `ToolResult.result` mapping narrowing;
- typed monkeypatch/callback seams with exact test-only ignores where needed.

Verification:

```text
uv run mypy: PASS — 268 source files, zero errors
```

No test exclusion, `ignore_errors`, or strictness reduction was used.

### Ruff production-risk preparation

Ran a scoped mechanical Ruff pass over the typing-batch production modules:

- 7 mechanical findings fixed;
- 9 files formatted;
- focused runtime tests: 62 passed;
- production mypy remains green.

Remaining scoped Ruff findings are judgment/design work, not auto-suppression:

- complexity in `run_bash.py`, `spawn_subagent.py`, `profiles.py`, and PTY run;
- broad exception boundaries requiring rationale/narrowing;
- assert/security and long-line findings;
- remaining targeted production decomposition.

Global Ruff and coverage remain open tracks. The next step is production
Ruff decomposition by highest-risk function, then coverage expansion against
the measured low-coverage live paths.

## 23. EXECUTION UPDATE — FULL TEST-TREE MYPY / RUFF PHASE STARTED

### Full test-tree mypy closure

Added explicit package markers for `tests`, `tests.fixtures`, and `scripts`,
then typed the shared/test boundaries without excluding tests or weakening
strictness. The final result is:

```text
Success: no issues found in 268 source files
```

The work included typed JSON/tool-wire boundaries, test helper return types,
valid LogKind fixture values, EventLog/session DB narrowing, and typed callback
seams. The suite remains behaviorally green.

### Ruff transition

A scoped mechanical Ruff pass over the touched production modules fixed 7
mechanical findings and formatted 9 files. Remaining production findings are
judgment work, led by `run_bash.py` complexity and exception boundaries.

The next Ruff slice must decompose `build_run_bash_tool`/`handler` into:

- executor/session resolution;
- PTY result normalization and transaction/artifact recording;
- subprocess fallback execution;
- final ToolResult projection.

Each helper needs focused tests or existing C1/C3 coverage before the
complexity finding is considered closed. No blanket C901/BLE001 suppression is
accepted.

## 24. EXECUTION UPDATE — RUN_BASH RUFF DECOMPOSITION / COVERAGE REMEASURE

### Ruff production slice

Refactored `src/fa/inner_loop/tools/run_bash.py` into explicit boundaries:

- `_resolve_execution_context`;
- `_run_pty_executor`;
- `_run_subprocess_fallback`;
- normalized `_Completed` result projection;
- small top-level handler decision tree.

The refactor preserved sandbox-admitted `shell=True`, PTY timeout fallback,
transaction write-set tracking, artifact offload, truncation, and structured
ToolResult failures.

Verification:

```text
run_bash.py mypy: PASS
run_bash.py Ruff: PASS
run_bash C1/C3 suite: 149 passed
full pytest: 1791 passed, 13 skipped, 0 failures
```

Global Ruff inventory moved from 366 findings at the broad baseline to 328
findings after scoped mechanical cleanup and this decomposition. Remaining
findings are still production-risk/style batches, not hidden by global ignores.

### Coverage remeasurement

Authoritative `just test` after the refactor:

```text
1791 passed, 13 skipped
coverage: 77.04%
fail-under: 86%
```

Coverage expansion is the next active slice. Select tests from the generated
coverage report, prioritizing runtime fallback/error/security paths rather than
adding assertions solely to execute lines.

## 35. EXECUTION UPDATE — SOURCE RUFF CLOSED / COVERAGE BATCH 3

Source Ruff is now clean without global ignores or blanket C901/BLE001 waivers.
The compaction foundation dead loop was removed, mutable class state was typed,
remaining long production strings were bounded, and the final exception/style
boundaries were narrowed. Source mypy remains clean (`129` files).

Coverage batch 3 used live `fs.read_file`/`fs.edit_file` handlers, real role
registries, and the authoritative SessionDatabase. The containment test found
and drove a real `PermissionError` boundary fix in edit/read tools. Deferred
FastAPI endpoint tests also cover the optional runtime when installed.

Verified:

```text
focused tool/registry/security tests: 21 passed
optional runtime endpoint tests: 2 passed
full pytest: 1810 passed, 13 skipped
coverage: 78.59% < 86% gate
```

Coverage remains the active open gate; PTY, optional registration, subagent,
and remaining analytics/blackboard branches are next.

## 37. EXECUTION UPDATE — PTY FAKE-TMUX COVERAGE / OPTIONAL-TYPING HARDENING

The PTY coverage batch now drives a fake tmux server through the live
`PtySession` constructor and `run()`/interrupt/close paths. Three new tests pass;
combined PTY-focused coverage reports 70% for `pty_pool.py` in that targeted
subset. Full mypy passes with optional runtime dependencies installed (`272`
files), and source Ruff remains clean.

The repository-wide `just lint` gate is still open because unrelated existing
scripts/tests emit 229 Ruff findings. This is recorded as pre-existing debt,
not hidden by a global ignore. Aggregate coverage remains 78.59% versus the
configured 86% gate; further coverage expansion and repository-wide lint debt
remain open before S9 final CI closure.

## 39. EXECUTION UPDATE — HIGH-VALUE COVERAGE/ROBUSTNESS SLICE

The requested PTY, optional registry, subagent, blackboard, and analytics slice
is implemented and verified. New tests are live-path/failure-path tests with
structured oracles. Three production defects were exposed and fixed: context
lookup versus spawn-limit exception conflation, unprotected worklog aggregation,
and unstable empty aggregate schema.

Verification:

```text
1826 passed, 13 skipped
coverage: 80.25% < 86% gate
mypy: PASS — 274 files
source Ruff: PASS
contracts/TCB/diff hygiene: PASS
```

The configured coverage threshold remains unchanged pending a later explicit
policy decision. Repository-wide Ruff best-effort reduced the inventory to 225
findings; remaining debt is mostly pre-existing tests plus one guardrail-script
complexity item, while all production source Ruff findings are closed.

## 41. EXECUTION UPDATE — RUFF COMPLEXITY + UNUSED-IMPORT CLEANUP

Closed the remaining complexity finding in `check_dead_flags.py` by separating
regex and AST phantom-flag detection and preserving deduplication. Removed 106
Ruff F401 imports using the standard safe fixer; full pytest verified no runtime
or test contract depended on them. Safe import/format cleanup removed 47 more
findings.

Verified:

```text
full pytest: 1826 passed, 13 skipped
focused regression: 54 passed
mypy: PASS — 274 files
source Ruff: PASS
C901/F401: PASS
```

Repository-wide Ruff remains at 70 findings, all test/style debt plus one
operator-facing legacy filename diagnostic. No production source C901/F401
findings remain; no broad ignores were introduced.

## 43. EXECUTION UPDATE — RUFF INVENTORY NEAR-CLOSED

Closed all remaining actionable test Ruff categories: F841, N806, E501,
BLE001, and RUF015. Each F841 was reviewed for oracle impact before removing
or converting the assignment. Focused affected tests pass (`17 passed`), full
mypy remains clean, and source Ruff remains clean.

Only one repository Ruff diagnostic remains: N999 for the legacy operator
filename `scripts/fa_host_layout_audit.py`. It is referenced by operator
instructions, so it is intentionally preserved pending an explicit interface
migration decision rather than hidden with an ignore.
