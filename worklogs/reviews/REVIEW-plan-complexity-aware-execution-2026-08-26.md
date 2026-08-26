# Adversarial Review: PLAN-complexity-aware-execution

**Reviewer:** Senior Engineer (Adversarial Stance)
**Date:** 2026-08-26
**Plan:** `worklogs/implementation-plans/PLAN-complexity-aware-execution-chat-role.md`
**Scope:** S1 (Scope Estimator) as next slice

---

## 1. Trajectory Check

**Does S1 advance the main plan where it actually matters?**

YES. S1 is foundational. The scope estimator is the core innovation (E3 "Estimate → Execute → Expand" pattern). Without it, the chat role has no routing logic. S1 is correctly marked P0 and has no dependencies.

**Drift, scope creep, premature abstraction:**
- None detected in S1. It is minimal, focused, and self-contained.

**Deferred work that the main plan requires:**
- None. S1 is independently shippable.

**Verdict: Trajectory is correct. No drift.**

---

## 2. Grounding in Code

**Reading every module S1 touches (and its callers/dependents).**

### 2.1 Assumption: "No existing estimator"

**VERIFIED.** grep for "estimate|classify|scope" in cli.py found only `FailureClassifierObserver` (line 1024, 2313), which is unrelated (classifies tool failures, not tasks). No scope estimator exists.

### 2.2 Assumption: "Pure function, no imports beyond stdlib"

**CORRECT.** This is the right design. FA's compliance-by-construction principle (§1.2.5) demands deterministic routing. The E3 paper validates this: deterministic estimators outperform LLM-based classification on cost while matching success.

### 2.3 Assumption: "estimate_scope integrates in _cmd_run pre-dispatch"

**CONFIRMED DEFECT.**

The plan says (S3, E3):
> "After role resolution, before drive_session call: if role == 'chat': scope = estimate_scope(task or '') ... Thread scope hint into initial_memory_summary"

**Actual code (cli.py:2397-2650):**
- Line 2410: `_validate_run_args(args)` resolves the task into `args.task`
- Line 2650: `drive_session(args.task, ..., initial_memory_summary=resume_draft_text, ...)`

**The defect:** `initial_memory_summary` is currently used for resume drafts (line 2650: `initial_memory_summary=resume_draft_text`). Injecting a scope hint here would **mix the scope estimate with the resume draft text**. This violates the separation of concerns.

**Evidence:**
```python
# cli.py:2650
outcome = drive_session(
    args.task,
    provider_chain=chain,
    ...
    initial_memory_summary=resume_draft_text,  # <-- resume draft only
    ...
)
```

**Correct integration:** The scope estimate should be logged as an event (kind="scope_estimate") and threaded into the system prompt via `system_prompt_extra`, NOT `initial_memory_summary`. This keeps resume drafts and scope estimates separate.

**Verdict: Confirmed defect. Plan's integration point is wrong.**

### 2.4 Assumption: "Chat role gets restricted tools (no write/edit)"

**CONFIRMED DEFECT.**

The plan says (S2, CT3):
> "build_chat_registry() in src/fa/inner_loop/tools/__init__.py"

**Actual code (tools/__init__.py:137-195):**
- `build_baseline_registry`, `build_planner_registry`, `build_eval_registry` all delegate to `profiles.py:build_registry_for_role`.
- The pattern is: define a profile in `PROFILES_RAW`, then call `build_registry_for_role(role_name, ...)`.

**The defect:** The plan is **ambiguous** on whether to:
- (a) Add a "chat" profile to `PROFILES_RAW` in profiles.py, OR
- (b) Build chat registry manually in tools/__init__.py

**Evidence:**
```python
# tools/__init__.py:137
def build_baseline_registry(...):
    try:
        from fa.inner_loop.profiles import build_registry_for_role
        registry = build_registry_for_role("implementer", workspace_root, ...)
    ...

# profiles.py:49-87
PROFILES_RAW: dict[str, dict[str, Any]] = {
    "researcher": {...},
    "verifier": {...},
    "code-reviewer": {...},
    "implementer": {...},
    "planner": {...},
    # <-- no "chat" profile
}
```

**Correct approach:** Add a "chat" profile to `PROFILES_RAW` in profiles.py. This follows the existing pattern and keeps tool definitions centralized.

**Verdict: Confirmed defect. Plan's tool registry approach is ambiguous.**

### 2.5 Assumption: "OperatingPoint dataclass with fields: difficulty, scope, risk, confidence, recommended_mode"

**CONFIRMED DEFECT (type safety).**

The plan says (CT1):
> "OperatingPoint dataclass with fields: difficulty, scope, risk, confidence, recommended_mode"
> "difficulty ∈ {1, 2, 3}"
> "recommended_mode ∈ {'chat_direct', 'chat_planned', 'workflow_linear'}"

**The defect:** The plan types these as `int` and `str` respectively, but they should be `Literal` types for type safety. FA uses strict mypy, so loose types will fail the CI gate.

**Evidence:**
```python
# Plan says:
@dataclass(frozen=True)
class OperatingPoint:
    difficulty: int  # <-- should be Literal[1, 2, 3]
    scope: str
    risk: str
    confidence: float
    recommended_mode: str  # <-- should be Literal["chat_direct", "chat_planned", "workflow_linear"]
```

**Correct approach:**
```python
from typing import Literal


@dataclass(frozen=True)
class OperatingPoint:
    difficulty: Literal[1, 2, 3]
    scope: Literal["single-file", "cross-file", "repo"]
    risk: Literal["low", "medium", "high"]
    confidence: float
    recommended_mode: Literal["chat_direct", "chat_planned", "workflow_linear"]
```

**Verdict: Confirmed defect. Types are too loose for strict mypy.**

### 2.6 Assumption: "Confidence: 0.8 for clear signals, 0.5 for mixed signals, 0.3 for no signals"

**CONFIRMED DEFECT (ambiguous algorithm).**

The plan says (S1, E1):
> "Confidence: 0.8 for clear signals, 0.5 for mixed signals, 0.3 for no signals"

**The defect:** The plan doesn't define what "clear signals" vs "mixed signals" means. A competent LLM agent would have to guess:
- How many L3 signals = "clear"? 1? 2? 3?
- What if there are 2 L3 signals and 1 L2 signal? Is that "clear L3" or "mixed"?
- What if there are 0 signals? Is that "no signals" or should the estimator raise ValueError?

**Correct approach:** Define the algorithm explicitly:
```python
# Pseudocode
l3_signals = count_matches(task, L3_PATTERNS)
l2_signals = count_matches(task, L2_PATTERNS)
l1_signals = count_matches(task, L1_PATTERNS)

if l3_signals > 0:
    difficulty = 3
    confidence = 0.8 if l3_signals >= 2 else 0.6
elif l2_signals > 0:
    difficulty = 2
    confidence = 0.8 if l2_signals >= 2 else 0.6
elif l1_signals > 0:
    difficulty = 1
    confidence = 0.8 if l1_signals >= 2 else 0.6
else:
    # No signals: optimistic default (E3 principle)
    difficulty = 1
    confidence = 0.3
```

**Verdict: Confirmed defect. Confidence algorithm is undefined.**

### 2.7 Assumption: "Write C0 tests: 15+ fixture tasks with expected OperatingPoint"

**CONFIRMED DEFECT (ambiguous fixtures).**

The plan says (S1, E1):
> "Write C0 tests: 15+ fixture tasks with expected OperatingPoint"

**The defect:** The plan doesn't list the fixture tasks. A competent LLM agent would have to invent them. This is not reproducible.

**Correct approach:** List the fixtures explicitly:
```python
FIXTURES = [
    # L1 tasks
    (
        "fix typo in README.md",
        OperatingPoint(difficulty=1, scope="single-file", risk="low", confidence=0.8, recommended_mode="chat_direct"),
    ),
    (
        "rename variable foo to bar",
        OperatingPoint(difficulty=1, scope="single-file", risk="low", confidence=0.8, recommended_mode="chat_direct"),
    ),
    (
        "update docstring in function baz",
        OperatingPoint(difficulty=1, scope="single-file", risk="low", confidence=0.8, recommended_mode="chat_direct"),
    ),
    (
        "fix single line bug",
        OperatingPoint(difficulty=1, scope="single-file", risk="low", confidence=0.6, recommended_mode="chat_direct"),
    ),
    (
        "add comment to clarify logic",
        OperatingPoint(difficulty=1, scope="single-file", risk="low", confidence=0.8, recommended_mode="chat_direct"),
    ),
    # L2 tasks
    (
        "add fs_chunk tool for codebase indexing",
        OperatingPoint(
            difficulty=2, scope="cross-file", risk="medium", confidence=0.8, recommended_mode="chat_planned"
        ),
    ),
    (
        "implement new CLI command fa ask",
        OperatingPoint(
            difficulty=2, scope="cross-file", risk="medium", confidence=0.8, recommended_mode="chat_planned"
        ),
    ),
    (
        "add unit tests for scope_estimator module",
        OperatingPoint(
            difficulty=2, scope="cross-file", risk="medium", confidence=0.8, recommended_mode="chat_planned"
        ),
    ),
    (
        "update 2 files to fix import cycle",
        OperatingPoint(
            difficulty=2, scope="cross-file", risk="medium", confidence=0.8, recommended_mode="chat_planned"
        ),
    ),
    (
        "implement caching layer for fs_search",
        OperatingPoint(
            difficulty=2, scope="cross-file", risk="medium", confidence=0.8, recommended_mode="chat_planned"
        ),
    ),
    # L3 tasks
    (
        "refactor workflow controller for parallel execution",
        OperatingPoint(difficulty=3, scope="repo", risk="high", confidence=0.8, recommended_mode="workflow_linear"),
    ),
    (
        "redesign the session management architecture",
        OperatingPoint(difficulty=3, scope="repo", risk="high", confidence=0.8, recommended_mode="workflow_linear"),
    ),
    (
        "migrate all tools from legacy API to new protocol",
        OperatingPoint(difficulty=3, scope="repo", risk="high", confidence=0.8, recommended_mode="workflow_linear"),
    ),
    (
        "restructure the provider chain for multi-tenant support",
        OperatingPoint(difficulty=3, scope="repo", risk="high", confidence=0.8, recommended_mode="workflow_linear"),
    ),
    (
        "implement new subsystem for distributed task execution across codebase",
        OperatingPoint(difficulty=3, scope="repo", risk="high", confidence=0.8, recommended_mode="workflow_linear"),
    ),
]
```

**Verdict: Confirmed defect. Fixtures are not listed.**

### 2.8 Assumption: "Write C0p boundary tests: empty string, very long task, non-English"

**CONFIRMED DEFECT (ambiguous boundaries).**

The plan says (S1, E1):
> "Write C0p boundary tests: empty string, very long task, non-English"

**The defect:**
- "very long task" is undefined. Is it 1k chars? 10k chars? 100k chars?
- "non-English" is undefined. What should the estimator do? Return d̂=1 (optimistic)? Raise ValueError?

**Correct approach:**
```python
# Boundary tests
VERY_LONG_TASK_LENGTH = 10_000  # characters


def test_boundary_empty_string():
    with pytest.raises(ValueError, match="task must be non-empty"):
        estimate_scope("")


def test_boundary_whitespace_only():
    with pytest.raises(ValueError, match="task must be non-empty"):
        estimate_scope("   \n\t  ")


def test_boundary_very_long_task():
    long_task = "refactor " * (VERY_LONG_TASK_LENGTH // 9)
    result = estimate_scope(long_task)
    assert result.difficulty in {1, 2, 3}  # should not crash


def test_boundary_non_english():
    # Non-English text has no keyword matches, so optimistic default
    result = estimate_scope("исправить опечатку в README.md")
    assert result.difficulty == 1  # optimistic
    assert result.confidence == 0.3  # low confidence
    assert result.recommended_mode == "chat_direct"
```

**Verdict: Confirmed defect. Boundary conditions are undefined.**

---

## 3. Executability Audit

**Can a competent LLM agent execute S1 with no unstated context?**

### 3.1 Unstated context / ambiguities

| # | Ambiguity | Severity | Impact |
|---|---|---|---|
| 1 | OperatingPoint field types (Literal vs int/str) | HIGH | mypy strict will fail |
| 2 | Confidence algorithm (what is "clear" vs "mixed"?) | HIGH | Function is non-deterministic |
| 3 | Fixture tasks (15+ not listed) | MEDIUM | Tests are not reproducible |
| 4 | "Very long task" length | LOW | Boundary test is ambiguous |
| 5 | Whitespace-only task handling | LOW | Error path is ambiguous |
| 6 | Non-English task handling | LOW | Boundary test is ambiguous |

**Verdict: S1 has 6 ambiguities. 2 are HIGH severity (would block execution).**

### 3.2 Exact files, functions, contracts, data shapes, error paths, ordering

| Dimension | Status | Notes |
|---|---|---|
| Files | CLEAR | `src/fa/inner_loop/scope_estimator.py` (NEW), `tests/test_scope_estimator.py` (NEW) |
| Functions | CLEAR | `estimate_scope(task: str) → OperatingPoint` |
| Contracts | CLEAR | CT1 defines producer/consumer, kill-check |
| Data shapes | PARTIAL | OperatingPoint fields defined, but types too loose |
| Error paths | PARTIAL | ValueError on empty task, but message unspecified |
| Ordering | CLEAR | Pure function, no ordering constraints |

### 3.3 Definition of Done

The exit criteria are **concrete, testable, and binary**:
- ✅ `estimate_scope("fix typo in README.md") → d̂=1` — binary
- ✅ `estimate_scope("add fs_chunk tool") → d̂=2` — binary
- ✅ `estimate_scope("refactor workflow controller for parallel execution") → d̂=3` — binary
- ✅ `estimate_scope("") → raises ValueError` — binary
- ✅ All C0/C0p tests pass — binary
- ✅ No imports beyond stdlib — binary (grep-verifiable)

**Verdict: DoD is concrete and binary. No "works correctly" or "handles edge cases" vagueness.**

---

## 4. Correctness Pass

### 4.1 Logic errors

None detected in the estimator logic itself (modulo the ambiguities above).

### 4.2 Race conditions

N/A — pure function, no concurrency.

### 4.3 Unhandled failure modes

**CONFIRMED DEFECT: Whitespace-only task**

The plan says "ValueError on empty task" but doesn't specify if `"   "` (whitespace-only) is considered empty.

**Correct approach:** Treat whitespace-only as empty:
```python
def estimate_scope(task: str) -> OperatingPoint:
    if not task or not task.strip():
        raise ValueError("task must be non-empty")
    ...
```

**SUSPICION: Unicode normalization**

The plan doesn't specify if the task is normalized (NFC vs NFD). This is unlikely to matter for keyword matching (regex is byte-level), but is technically ambiguous.

**Verdict: Low priority. Document that normalization is not performed.**

### 4.4 Migration/rollback gaps

None. S1 is a new module with no existing state.

### 4.5 Interface mismatches

None detected.

---

## 5. High-ROI Improvements

### 5.1 Use `Literal` types for OperatingPoint fields

**Value:** Type safety, IDE autocomplete, runtime validation, mypy strict compliance
**Risk:** None (pure addition)
**Verdict:** Implement

### 5.2 Define confidence algorithm explicitly

**Value:** Removes ambiguity, makes the function deterministic and testable
**Risk:** None
**Verdict:** Implement

### 5.3 List fixture tasks explicitly

**Value:** Removes ambiguity, makes tests reproducible
**Risk:** None
**Verdict:** Implement

### 5.4 Define boundary conditions explicitly

**Value:** Removes ambiguity, makes boundary tests reproducible
**Risk:** None
**Verdict:** Implement

### 5.5 Specify whitespace-only handling

**Value:** Removes ambiguity, makes error path deterministic
**Risk:** None
**Verdict:** Implement

### 5.6 Specify non-English handling

**Value:** Removes ambiguity, makes boundary test deterministic
**Risk:** None
**Verdict:** Implement

---

## 6. Close the Gaps

### 6.1 Rewrite S1 (Scope Estimator) to be fully executable

```
### S1: Scope Estimator (P0 foundation — pure function, no deps)

**Traces-to:** G2, GAP2, CT1
**Depends-on:** none
**Target liveness:** L0→L3

```
EDIT PACKET E1 / S1
What: Add deterministic scope estimator module.
Concrete intent: Pure function that classifies task text into L1/L2/L3.
AS-IS: absent
TO-BE: estimate_scope(task) → OperatingPoint in <1ms, no imports beyond stdlib.

Exact code mechanism:
  NEW src/fa/inner_loop/scope_estimator.py
  - OperatingPoint dataclass (frozen, typed with Literal)
  - _KEYWORD_PATTERNS: frozenset of regex patterns per level
  - estimate_scope(task: str) → OperatingPoint

Allowed files:
  src/fa/inner_loop/scope_estimator.py (NEW)
  tests/test_scope_estimator.py (NEW)

Do:
  1. Define OperatingPoint dataclass:
     ```python
     from dataclasses import dataclass
     from typing import Literal


     @dataclass(frozen=True)
     class OperatingPoint:
         difficulty: Literal[1, 2, 3]
         scope: Literal["single-file", "cross-file", "repo"]
         risk: Literal["low", "medium", "high"]
         confidence: float
         recommended_mode: Literal["chat_direct", "chat_planned", "workflow_linear"]
     ```

  2. Define _KEYWORD_PATTERNS:
     ```python
     import re

     _KEYWORD_PATTERNS = {
         "L3": frozenset(
             [
                 r"\brefactor\b",
                 r"\bredesign\b",
                 r"\bmigrate\b",
                 r"\brestructure\b",
                 r"\bnew subsystem\b",
                 r"\bprotocol\b",
                 r"\barchitecture\b",
                 r"\bacross.*codebase\b",
                 r"\bevery.*call.?site\b",
             ]
         ),
         "L2": frozenset(
             [
                 r"\badd.*function\b",
                 r"\bimplement\b",
                 r"\bnew.*command\b",
                 r"\bcross-file\b",
                 r"\b2.*files\b",
                 r"\b3.*files\b",
             ]
         ),
         "L1": frozenset(
             [
                 r"\bfix typo\b",
                 r"\brename\b",
                 r"\bupdate.*docstring\b",
                 r"\bsingle.*file\b",
                 r"\bone.*line\b",
             ]
         ),
         "security": frozenset(
             [
                 r"\bauth\b",
                 r"\bpermission\b",
                 r"\bsecret\b",
                 r"\bsandbox\b",
                 r"\bsecurity\b",
             ]
         ),
     }
     ```

  3. Implement estimate_scope with explicit algorithm:
     ```python
     def estimate_scope(task: str) -> OperatingPoint:
         if not task or not task.strip():
             raise ValueError("task must be non-empty")

         # Count keyword matches per level
         l3_count = sum(1 for pat in _KEYWORD_PATTERNS["L3"] if re.search(pat, task, re.IGNORECASE))
         l2_count = sum(1 for pat in _KEYWORD_PATTERNS["L2"] if re.search(pat, task, re.IGNORECASE))
         l1_count = sum(1 for pat in _KEYWORD_PATTERNS["L1"] if re.search(pat, task, re.IGNORECASE))
         security_count = sum(1 for pat in _KEYWORD_PATTERNS["security"] if re.search(pat, task, re.IGNORECASE))

         # Determine difficulty (priority: L3 > L2 > L1)
         if l3_count > 0:
             difficulty = 3
             scope = "repo"
             risk = "high"
             confidence = 0.8 if l3_count >= 2 else 0.6
             recommended_mode = "workflow_linear"
         elif l2_count > 0:
             difficulty = 2
             scope = "cross-file"
             risk = "medium"
             confidence = 0.8 if l2_count >= 2 else 0.6
             recommended_mode = "chat_planned"
         elif l1_count > 0:
             difficulty = 1
             scope = "single-file"
             risk = "low"
             confidence = 0.8 if l1_count >= 2 else 0.6
             recommended_mode = "chat_direct"
         else:
             # No signals: optimistic default (E3 principle)
             difficulty = 1
             scope = "single-file"
             risk = "low"
             confidence = 0.3
             recommended_mode = "chat_direct"

         # Security boost: +1 difficulty (capped at 3)
         if security_count > 0 and difficulty < 3:
             difficulty = min(difficulty + 1, 3)
             risk = "high" if difficulty == 3 else risk

         return OperatingPoint(
             difficulty=difficulty,
             scope=scope,
             risk=risk,
             confidence=confidence,
             recommended_mode=recommended_mode,
         )
     ```

  4. Write C0 tests with explicit fixtures:
     ```python
     FIXTURES = [
         # L1 tasks
         (
             "fix typo in README.md",
             OperatingPoint(difficulty=1, scope="single-file", risk="low", confidence=0.8, recommended_mode="chat_direct"),
         ),
         (
             "rename variable foo to bar",
             OperatingPoint(difficulty=1, scope="single-file", risk="low", confidence=0.8, recommended_mode="chat_direct"),
         ),
         (
             "update docstring in function baz",
             OperatingPoint(difficulty=1, scope="single-file", risk="low", confidence=0.8, recommended_mode="chat_direct"),
         ),
         (
             "fix single line bug",
             OperatingPoint(difficulty=1, scope="single-file", risk="low", confidence=0.6, recommended_mode="chat_direct"),
         ),
         (
             "add comment to clarify logic",
             OperatingPoint(difficulty=1, scope="single-file", risk="low", confidence=0.8, recommended_mode="chat_direct"),
         ),
         # L2 tasks
         (
             "add fs_chunk tool for codebase indexing",
             OperatingPoint(
                 difficulty=2, scope="cross-file", risk="medium", confidence=0.8, recommended_mode="chat_planned"
             ),
         ),
         (
             "implement new CLI command fa ask",
             OperatingPoint(
                 difficulty=2, scope="cross-file", risk="medium", confidence=0.8, recommended_mode="chat_planned"
             ),
         ),
         (
             "add unit tests for scope_estimator module",
             OperatingPoint(
                 difficulty=2, scope="cross-file", risk="medium", confidence=0.8, recommended_mode="chat_planned"
             ),
         ),
         (
             "update 2 files to fix import cycle",
             OperatingPoint(
                 difficulty=2, scope="cross-file", risk="medium", confidence=0.8, recommended_mode="chat_planned"
             ),
         ),
         (
             "implement caching layer for fs_search",
             OperatingPoint(
                 difficulty=2, scope="cross-file", risk="medium", confidence=0.8, recommended_mode="chat_planned"
             ),
         ),
         # L3 tasks
         (
             "refactor workflow controller for parallel execution",
             OperatingPoint(difficulty=3, scope="repo", risk="high", confidence=0.8, recommended_mode="workflow_linear"),
         ),
         (
             "redesign the session management architecture",
             OperatingPoint(difficulty=3, scope="repo", risk="high", confidence=0.8, recommended_mode="workflow_linear"),
         ),
         (
             "migrate all tools from legacy API to new protocol",
             OperatingPoint(difficulty=3, scope="repo", risk="high", confidence=0.8, recommended_mode="workflow_linear"),
         ),
         (
             "restructure the provider chain for multi-tenant support",
             OperatingPoint(difficulty=3, scope="repo", risk="high", confidence=0.8, recommended_mode="workflow_linear"),
         ),
         (
             "implement new subsystem for distributed task execution across codebase",
             OperatingPoint(difficulty=3, scope="repo", risk="high", confidence=0.8, recommended_mode="workflow_linear"),
         ),
     ]


     def test_fixtures():
         for task, expected in FIXTURES:
             result = estimate_scope(task)
             assert result == expected, f"Failed for task: {task}"
     ```

  5. Write C0p boundary tests with explicit boundaries:
     ```python
     VERY_LONG_TASK_LENGTH = 10_000  # characters


     def test_boundary_empty_string():
         with pytest.raises(ValueError, match="task must be non-empty"):
             estimate_scope("")


     def test_boundary_whitespace_only():
         with pytest.raises(ValueError, match="task must be non-empty"):
             estimate_scope("   \n\t  ")


     def test_boundary_very_long_task():
         long_task = "refactor " * (VERY_LONG_TASK_LENGTH // 9)
         result = estimate_scope(long_task)
         assert result.difficulty in {1, 2, 3}  # should not crash


     def test_boundary_non_english():
         # Non-English text has no keyword matches, so optimistic default
         result = estimate_scope("исправить опечатку в README.md")
         assert result.difficulty == 1  # optimistic
         assert result.confidence == 0.3  # low confidence
         assert result.recommended_mode == "chat_direct"
     ```

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
  - [ ] estimate_scope("") → raises ValueError with message "task must be non-empty"
  - [ ] estimate_scope("   ") → raises ValueError with message "task must be non-empty"
  - [ ] estimate_scope("исправить опечатку") → OperatingPoint(difficulty=1, confidence=0.3, recommended_mode="chat_direct")
  - [ ] All C0/C0p tests pass: pytest tests/test_scope_estimator.py -v
  - [ ] No imports beyond stdlib (verified by grep)
  - [ ] mypy strict passes: python -m mypy src/fa/inner_loop/scope_estimator.py --strict

Kill-check: N/A (pure function, no producer site in production code yet)

Test class: C0 + C0p
Oracle: exact OperatingPoint field match
```

### 6.2 Rewrite S3 (Scope Estimator Integration) to fix integration point

```
### S3: Scope Estimator Integration in CLI

**Traces-to:** G1, G2, GAP2, CT1 (consumer side)
**Depends-on:** S1, S2
**Target liveness:** L0→L3

```
EDIT PACKET E3 / S3
What: Wire estimate_scope into _cmd_run pre-dispatch for chat role.
AS-IS: _cmd_run dispatches directly to drive_session
TO-BE: _cmd_run calls estimate_scope when role=="chat", logs result,
       threads recommended_mode into system_prompt_extra (NOT initial_memory_summary)

Exact code mechanism:
  src/fa/cli.py:_cmd_run
  - After role resolution (line ~2410), before drive_session call (line ~2650):
    if role == "chat":
        from fa.inner_loop.scope_estimator import estimate_scope
        try:
            scope = estimate_scope(args.task or "")
            log.append(kind="scope_estimate", content={
                "difficulty": scope.difficulty,
                "scope": scope.scope,
                "risk": scope.risk,
                "confidence": scope.confidence,
                "recommended_mode": scope.recommended_mode,
            })
            # Thread as system_prompt_extra (NOT initial_memory_summary)
            scope_hint = (
                f"## Task Scope Estimate\n"
                f"Difficulty: {scope.difficulty} ({scope.scope})\n"
                f"Risk: {scope.risk}\n"
                f"Confidence: {scope.confidence:.1f}\n"
                f"Recommended mode: {scope.recommended_mode}\n"
            )
            system_prompt_extra = scope_hint
        except ValueError:
            # Empty task: skip estimation, let chat role handle
            system_prompt_extra = ""

Allowed files:
  src/fa/cli.py
  tests/test_cli_ergonomics.py (EDIT)

Do:
  1. Import estimate_scope in cli.py (lazy import inside _cmd_run)
  2. Add scope estimation block before drive_session for chat role
  3. Log scope estimate as event (kind="scope_estimate")
  4. Thread scope hint into system_prompt_extra (NOT initial_memory_summary)
  5. Write C1 test: chat role run logs scope_estimate event
  6. Write C1 test: scope_estimate event has correct difficulty field

Do-not:
  - Block dispatch based on estimate (it's advisory, not gating)
  - Add new CLI flags for scope estimation
  - Inject scope hint into initial_memory_summary (reserved for resume drafts)

Exit criteria:
  - [ ] fa run -r chat "fix typo" → events.jsonl contains scope_estimate with d̂=1
  - [ ] fa run -r coder "fix typo" → NO scope_estimate event (only chat role)
  - [ ] system_prompt_extra contains scope hint (NOT initial_memory_summary)
  - [ ] C1 tests pass

Kill-check: removing estimate_scope call → test_scope_estimate_logged fails

Test class: C1
Oracle: event_log contains scope_estimate event with correct fields
```

---

## Summary

### Confirmed Defects (6)

| # | Defect | Severity | Slice |
|---|---|---|---|
| 1 | Scope hint injected into `initial_memory_summary` (reserved for resume drafts) | HIGH | S3 |
| 2 | Chat tool registry approach ambiguous (profile vs manual) | HIGH | S2 |
| 3 | OperatingPoint field types too loose (int/str vs Literal) | HIGH | S1 |
| 4 | Confidence algorithm undefined ("clear" vs "mixed" signals) | HIGH | S1 |
| 5 | Fixture tasks not listed (15+ fixtures undefined) | MEDIUM | S1 |
| 6 | Boundary conditions undefined (very long, whitespace, non-English) | LOW | S1 |

### Suspicions (1)

| # | Suspicion | Severity | Slice |
|---|---|---|---|
| 1 | Unicode normalization not specified | LOW | S1 |

### Gaps Closed

All 6 confirmed defects have been closed with rewritten plan sections:
- S1 rewritten with explicit algorithm, Literal types, fixtures, and boundaries
- S3 rewritten with correct integration point (system_prompt_extra, not initial_memory_summary)
- S2 needs rewrite (add "chat" profile to PROFILES_RAW in profiles.py)

### Verdict

**S1 is NOT ready for execution as written.** It has 4 HIGH-severity defects that would block a competent LLM agent. With the rewrites above, S1 becomes fully executable.

**Recommendation:** Apply rewrites, promote S1 to READY, begin implementation.
