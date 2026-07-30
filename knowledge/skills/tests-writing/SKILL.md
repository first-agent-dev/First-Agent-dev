---
name: tests-writing
description: |
  Production-grade rulebook for testing an LLM agent harness and AI-authored
  changes to it. Dual pyramid (deterministic harness vs model evals), live-path
  composition-root DoD, anti-theater, two-sided contract verification,
  type-safe fixtures, flag matrices, path inventory, dual-write consistency,
  fault/efficiency signals, security boundaries, and mutation handoff.
status: active
last-reviewed: 2026-07-19
triggers:
  - "writing or changing tests under tests/"
  - "IMPLEMENT or FIX touching src/fa/ that claims product behavior"
  - "closing an audit finding about unwired / dormant / test-theater modules"
  - "adding ContextBudget, compaction, hooks, tools, providers, or other loop surfaces"
  - "unsure whether a unit test is enough for a harness feature"
  - "designing evals vs pytest for agent quality"
  - "tests fail typecheck / Pylance on fixtures"
  - "AI-authored tests look green but may be theater"
  - "adding a new EventType, event kind, or observable signal to the harness"
  - "verifying that a producer emit and consumer handler are both wired"
globs:
  - "tests/**/*.py"
  - "src/fa/**/*.py"
alwaysApply: false
---

# Skill — Tests writing (agent harness, AI age)

> **Central law (live path):** *Harness behavior is done when a test that boots
> the real session path fails if the production PRODUCER call site is removed.*
> A kill-check that passes because the call site was never written is VACUOUS —
> the feature is not shipped.
>
> **Central law (two-sided contract):** *For every EventType (any observable
> signal), BOTH the producer (`output.emit()` — code that creates the signal)
> AND the consumer (`_handle_X()` — code that handles it) must exist and be
> verified. Consumer-only proof is incomplete — it proves a dead handler works.*
>
> **Central law (AI systems):** *Prefer properties, schemas, trajectories, events,
> and side effects as oracles; free-text model output is secondary only.*
>
> **Central law (AI-authored tests):** *Assume oracles can be weakened; use
> kill-check, type honesty, and mutation after C1 as forcing functions.*
>
> **Central law (path sensitivity):** *A single EventType may be emitted from
> multiple code paths. Testing one path does not prove the others work.
> Enumerate all paths; test each.*

---

## Quick decision tree (read this first)

1. **Pyramid A or B?** Wiring / control-flow / security / efficiency → **A** (CI). Subjective quality → **B** (evals; scheduled).
2. **Session / product / loop claim?** → **C1** (or **C2** if CLI-only). Pure helper → **C0 / C0p**.
3. **Root?** Prefer `drive_session` (+ factories used by shipped CLI). Add C2 when CLI builds objects differently.
4. **Two-sided contract?** If adding or verifying an EventType → enumerate PRODUCER emit paths AND consumer handlers. Both must exist. **Producer proof before consumer proof.**
5. **Kill-check?** Test fails when the PRODUCTION EMIT CALL is removed — `output.emit(OutputEvent(type="X"))` in loop/tools, not the `_handle_X()` handler. If the emit call doesn't exist yet, NOT shipped — vacuous kill-check.
6. **Existence pre-check?** Grep for the emit call site in production code. If it doesn't exist, NOT wired. Vacuous kill-check = theater.
7. **Path inventory?** Enumerate ALL code paths that should emit the event. At least one test per path.
8. **Matrix coverage?** For every flag combination, at least one test MUST exist. Naming a matrix is necessary but NOT sufficient.
9. **Dual-write?** If the system writes to both `log.append()` and `output.emit()`, verify BOTH on every code path. Missing `output.emit()` = operator sees nothing.
10. **Oracle rank?** Event `kind`+fields → `SessionOutcome` → tool trajectory → provider `call_count`/token band → FS → free text.
11. **Types honest?** `tool_calls=()`, `_require_log`, real `HookRegistry()`.
12. **Security?** ≥1 adversarial case (C3).
13. **Early-stop?** Assert low/zero `request.call_count` when a gate fires first.
14. **AI-authored?** Anti-theater + `TEST-EDITS` under FIX; hand off to `mutation-clearing` after C1.
15. **Third copy of same mocks?** Extract shared fixture module.

| Priority | Prescription |
| :--- | :--- |
| **Must** | C1/C2 + kill-check on PRODUCER + existence pre-check + honest types + ranked oracle + explicit matrix + path inventory + two-sided contract + dual-write consistency |
| **Should** | Fault injection; efficiency `call_count`; shared factories; C0p on pure math/policy; provider-family param; automated contract check |
| **Prefer instead** | Structured oracles over free-text; real registries over mocks; mocked I/O over live keys; thresholds from source; kill-check over coverage %; real `drive_session` over mocked root |

---

### 0. Two pyramids (keep them separate)

```text
PYRAMID A — Deterministic harness (every PR)
  C2 CLI smoke → C1 composition-root → C3 security → C0/C0p unit+properties
  Oracles: events, outcomes, call counts, schemas, token bands, FS, deny reasons
  LLM: mocked or absent

PYRAMID B — Model / agent quality (scheduled)
  Human spot → scenarios → golden+judge → deterministic output props
  Oracles: task success, faithfulness, trajectory quality, safety
  LLM: real or recorded; non-determinism managed
```

| Question | Pyramid |
| :--- | :--- |
| Is feature X **wired** into the loop? | **A** (C1) |
| Does the model solve tasks well? | **B** |
| Does a security gate deny correctly? | **A** (C3) |
| Was feature X *invoked*? vs is its *output useful*? | **A** vs **B** |

---

### 1. Taxonomy (Pyramid A)

| Class | Boots | Use when | Product proof? |
| :--- | :--- | :--- | :--- |
| **C0 Unit** | Isolation | Pure helpers, parsers, estimators | Incomplete alone |
| **C0p Property** | Many inputs | Thresholds, containment, parse robustness | Pair with C1 |
| **C1 Composition-root** | `drive_session` / real factories | **Default for product behavior** | Yes (kill-check on PRODUCER) |
| **C2 CLI smoke** | `fa` / `_cmd_*` | Argv→factory wiring, exit codes | Yes for CLI-only claims |
| **C3 Security** | Gate + adversarial inputs | Sandbox, secrets, permissions | Yes with adversarial cases |
| **C4 Mutation** | Per `mutation-clearing` | After mutmut survivors | Adequacy layer after C1 |

**Split rule:** mock **LLM I/O** (`ProviderChain.request`); exercise real registry,
hooks, budget, and prompt assembly under test.

---

### 2. Composition roots and L1–L3

| Root | Symbol | Role |
| :--- | :--- | :--- |
| Session loop | `fa.inner_loop.coder_loop.drive_session` | Primary path |
| Registry builders | builders used by `fa run` | Tools registered |
| Hook chain | registration used by `fa run` | Middleware attached |
| CLI drivers | `fa.cli` session commands | CLI wires chains/flags |

| Level | Meaning | Product DoD? |
| :--- | :--- | :--- |
| L1 Import-reachable | Something imports the symbol | Incomplete |
| L2 Call-reachable | Root invokes / registers it | Incomplete |
| L3 Behavior + kill-check on PRODUCER | Boots root; side effect; fails when EMIT CALL is removed | **Yes** |

**L3 refinement:** Kill-check targets the PRODUCER call site (the
`output.emit()` or `log.append()` call), NOT the consumer handler.
If the producer call doesn't exist, the feature is at L0 (not wired).

---

### 3. Anti-theater checklist (C1 — all apply)

1. **Existence pre-check** — the PRODUCER emit call site EXISTS in production
   code. Grep for `output.emit(OutputEvent(type="X"))` in loop/tools. If not
   found: NOT shipped. Vacuous kill-check = not shipped.
2. **Kill-check on PRODUCER** — removing `output.emit(OutputEvent(type="X"))`
   fails this test. Target the producer, not the consumer handler.
3. **Observable side effect** — event `kind`+fields, `SessionOutcome`, provider
   `call_count`, or FS effect — not just "no exception."
4. **Live-path proof** — exercise the real composition root; class construction
   alone is incomplete.
5. **Flag honesty** — explicit `FeatureFlags(...)`; name matrix A/B/C.
6. **Mock boundary** — mock `ProviderChain.request`; keep `drive_session` real.
7. **Real registry types** — `hooks=HookRegistry()` (empty OK) for wiring.
8. **Type-honest fixtures** — §5; match production types exactly.
9. **Thresholds from source** — read from `ContextBudget`, not magic numbers.
10. **Deterministic** — offline; sort where needed; fixed clocks.
11. **Tight AST guard (should)** — root imports/calls symbol precisely.
12. **Early-stop efficiency (should)** — `request.call_count == 0` when gate fires.
13. **Two-sided contract** — for every EventType, BOTH producer and consumer
    verified. Consumer-only = incomplete.
14. **Path inventory** — ALL code paths that emit the signal enumerated and tested.
15. **Matrix coverage gate** — ≥1 test per flag combination. Naming ≠ covering.
16. **Dual-write consistency** — `log.append()` + `output.emit()` both present
    on every code path that should write.

---

### 4. Flag / provider matrix

| Matrix | Example | Proves |
| :--- | :--- | :--- |
| **A — primary** | budget on, compaction off | Primary path works |
| **B — full cascade** | both on | Cascade / interaction paths |
| **C — defaults** | `FeatureFlags()` | Operator-facing path |
| **P — provider family** | openai vs anthropic | Backend-specific behavior |

**Matrix coverage gate:** ≥1 C1 test per combination MUST exist before "shipped."
Naming in docstring is necessary but NOT sufficient. Verify: for each combo,
is there a test that sets those flags and asserts expected behavior?

---

### 5. Type-honest fixtures

| Production type | Fixture must use | NOT |
| :--- | :--- | :--- |
| `tool_calls: tuple[…]` | `tool_calls=()` | `tool_calls=[]` |
| `log: EventLog | None` | real `EventLog(tmp_path / …)` | mocked EventLog |
| `hooks: HookRegistry` | `hooks=HookRegistry()` | `MagicMock` for wiring |
| `output: EventBus` | real `EventBus()` + capture listener | `MagicMock` |
| `state: SessionState` | real `SessionState(log=…)` | mock with `.log` |
| `provider_chain` | `MagicMock(spec=ProviderChain)` — mock I/O only | mock the root |
| `feature_flags` | explicit `FeatureFlags(...)` | `MagicMock` |

**Narrowing Optional:** if production narrows `X | None` → `X`, mirror that in
fixture. Don't `# type: ignore` to paper over fixture gaps.

---

### 6. Ranked oracles (with assertion patterns)

| Rank | Oracle | Assertion pattern |
| :--- | :--- | :--- |
| 1 | Event `kind`+fields | `events = [e for e in capture if e.type == "X"]; assert len(events) >= 1; assert events[0].data["key"] == "val"` |
| 2 | `SessionOutcome` | `assert outcome.stop_reason == "context_budget_hard_stop"; assert outcome.exit_code == 1` |
| 3 | Tool trajectory | `assert [tc["function"]["name"] for tc in calls] == ["read", "write"]` |
| 4 | Provider `call_count` / tokens | `assert mock_chain.request.call_count == 0  # early-stop` |
| 5 | FS effects | `assert (tmp_path / "file").exists()` |
| 6 | Deny reason dataclass | `assert result.error.code == "sandbox_violation"` |
| 7 | Free-text `in`/`==` | Secondary only; never sole oracle for wiring |

---

### 7. Two-sided contract verification

For every **EventType** (any observable signal) in `output.py`:

```
PRODUCER (output.emit() in loop/tools)  ←→  CONSUMER (_handle_X() in ConsoleRenderer)
```

Both sides must exist and be verified. Consumer-only proof is incomplete.

**Producer proof (C1 — mandatory before "shipped"):** Test exercises
`drive_session` and asserts the EventType is emitted. Kill-check: removing
the `output.emit()` call makes the test fail.

**Consumer proof (C0 or C1 — necessary but insufficient alone):** Test
verifies `_handle_X()` processes the event correctly. Must be paired with
producer proof.

**Contract check (automated — CI gate):**
`scripts/check_producer_consumer_contract.py` verifies all EventTypes have
both producer and consumer. Any gap = FAIL (exit 1). Wired into `just check`.

**Ordering rule:** Producer proof BEFORE "shipped":
1. Write the `output.emit()` call → 2. Write C1 producer test →
3. Write handler → 4. Write consumer test → 5. Contract check PASS → 6. Shipped.

**Two kill-checks for EventType claims:**
(1) Remove `output.emit()` from production → C1 producer test fails.
(2) Remove `_handle_X()` from renderer → C0/C1 consumer test fails.
Both must hold. Producer kill-check is PRIMARY.

---

### 8. Path inventory

A single EventType may be emitted from **multiple code paths**, each triggered
by different conditions and flag combinations. Testing one path does NOT prove
the others work.

**Rule:** Before writing tests for an EventType, enumerate ALL production paths
that should emit it. For each path: triggering condition, file:line, flag
combination. Write at least one test per path. Document in test module docstring.

**How to build:**
1. `grep -rn 'type="X"' src/fa/`
2. Trace backward from each emit to enclosing `if`/`elif`/`except`
3. Cross-reference with feature flags
4. Document in a table

---

### 9. Dual-write consistency

The system has two write paths: **EventLog** (`log.append`) → session.db +
JSONL, and **EventBus** (`output.emit`) → ConsoleRenderer. Every code path
that writes to one MUST also write to the other. Missing `output.emit()` =
operator sees nothing at the console.

**Verify:** For every `log.append()` in a code path, check that a
corresponding `output.emit(OutputEvent(type="X"))` exists in the same
`if`/`elif`/`except` block.

---

### 10. C0 consumer-only: the false-confidence trap

C0 consumer-only tests are necessary but NEVER sufficient. A test that verifies
`_handle_X()` processes an event correctly does NOT prove the event is ever
emitted. It proves a dead handler works.

**Rule:** Every C0 consumer test for an EventType MUST be paired with a C1
producer test. Without this, the C0 test is theater.

**Prevention:** In test module docstring, label tests as C1-producer,
C1-consumer, or C0-consumer-only. Audit for unpaired C0-consumer-only tests.

---

### 11. Security boundaries

| Boundary | Minimum proof |
| :--- | :--- |
| Sandbox containment | Exec denied outside workspace (C3) |
| Secret leakage | Secret NOT in model-facing messages (C3) |
| IntentGuard | Deny without trusted draft + allow with (C3) |
| Tool permission model | `read` tool cannot write (C3) |
| Path containment | `../` denied |
| Egress / proxy | Agent side carries proxy token only |

Pair happy-path with adversarial. Prefer parametrized edges.

---

### 12. Pyramid B boundary

| Eval (B) | Deterministic test (A) |
| :--- | :--- |
| "Is the output useful?" | "Was the feature invoked and event written?" |
| "Did the agent solve it?" | "Did agent get the right tools?" |

Design A for B: keep A fixtures exportable (structured logs/trajectories).
Gate merges on A; promote B judges only when calibrated.

---

### 13. Mutation handoff + AI-author patterns

| After C1 green | Next |
| :--- | :--- |
| Live path proven | Load `mutation-clearing` |
| Coverage high, mutants live | Strengthen oracles |

| Prefer | Instead of |
| :--- | :--- |
| Real assertions on events/outcomes | `assert True` / placeholders |
| Strict xfail with issue | Open-ended skip / non-strict xfail |
| Ranked structured oracles | Sole free-text equality |
| Real `drive_session` + mocked provider | Mocking the composition root |
| Thresholds from `ContextBudget` | Invented magic numbers |
| `hooks=HookRegistry()` | MagicMock for wiring |
| `TEST-EDITS` under FIX | Silent weakening of C1 |
| C1 producer test for every EventType | C0 consumer-only "shipped" proof |
| Kill-check on PRODUCER emit call | Kill-check on consumer handler |
| Path inventory for all emit sites | Single-path test |
| Matrix coverage gate | Matrix name in docstring only |
| Dual-write consistency check | Single-write verification |

---

### 14. Gold files

| File | Proves |
| :--- | :--- |
| `tests/test_pr1_wiring.py` | Budget C1 pattern: warn, hard-stop with `call_count==0`, `HookRegistry`, `_require_log`, `tool_calls=()` |
| `tests/test_coder_loop.py` | Mature `HookRegistry` + trajectory patterns |
| `tests/test_event_type_c1_producers.py` | C1 producer tests for all EventTypes |

---

### 15. Naming, isolation, CI

| Practice | Guidance |
| :--- | :--- |
| Filenames | `test_<feature>_wiring.py`; `test_invariant_adrN_…` for ADR bindings |
| Docstring | root + matrix + claim + kill-check target + path inventory |
| Authority | Normal pytest; `just check` is authority |
| CI gates | `just check` → pytest + coverage + typecheck + contract check |
| Test edits | `validate_test_edits` / IntentGuard under FIX |
| Isolation | `tmp_path`; freeze time; mock LLM always in A |
| Determinism | Offline; sort unstable collections |
| Subprocess env | Shadow-bin dirs on PATH (see §15.1); **never filter PATH directories** |

---

### 15.1 Subprocess isolation: shadow-bins (PATH overlay)

When a test invokes a production script that calls out to an external CLI
(`docker`, `podman`, `kubectl`, `gh`, `cargo`, `npm`, …) via `subprocess.run`
or by exec'ing a shell script, follow these rules:

1. **Use `env=` on `subprocess.run`/`Popen` — never mutate `os.environ`.**
2. **Pin interpreters explicitly.** If the script uses `${PYTHON:-python3}`,
   set `env["PYTHON"] = sys.executable` so the subprocess imports the code
   under test instead of whatever `python3` happens to resolve on the host
   (VSCode launches pytest via the venv binary without activating the venv
   on PATH, so bare `python3` resolves to the system interpreter →
   `ModuleNotFoundError: fa`).
3. **Shadow unwanted CLIs with a temp bin directory, don't filter PATH.**
   Append a *prepend* directory (created once via `tmp_path_factory` or a
   module-scoped `tempfile.mkdtemp` + `atexit` cleanup) containing small
   executable shim scripts named after the CLI you want to block. Make the
   shim print a recognisable stderr line and exit non-zero (e.g.
   `exit 127` with `"docker: not found (test shim)"`). Unix PATH lookup is
   first-match-wins, so your shim intercepts the target name while *every
   other host binary* (`bash`, `sh`, `true`, `cat`, `ls`, `pwd`, `python3`,
   `coreutils`, …) continues to resolve through the inherited PATH
   unchanged.

   Rationale: Docker Desktop, Snap installs, Nix, Homebrew, and distro
   packages routinely place CLIs in the *same* directory as core utilities
   (`/usr/bin`, `/usr/local/bin`, `/snap/bin`). Filtering PATH entries by
   "contains a docker binary" removes `/usr/bin` from PATH and breaks
   `bash`/`sh`/`ls` resolution for the subprocess. We have watched this
   regression happen in real life (PR #58 pre-push fix cycle,
   `FileNotFoundError: 'bash'`). Shadowing is surgically narrow; filtering
   is semantically broken on Unix.

   Pattern:

   ```python
   _SHADOW_DIR: Path | None = None


   def _shadow_dir() -> Path:
       global _SHADOW_DIR
       if _SHADOW_DIR is None:
           d = Path(tempfile.mkdtemp(prefix="fa-test-shadow-"))
           for name in ("docker", "podman"):
               p = d / name
               p.write_text(
                   '#!/bin/sh\necho "docker: not found (test shim)" >&2\nexit 127\n',
                   encoding="utf-8",
               )
               p.chmod(0o755)
           atexit.register(lambda: shutil.rmtree(d, ignore_errors=True))
           _SHADOW_DIR = d
       return _SHADOW_DIR


   def _script_env() -> dict[str, str]:
       env = os.environ.copy()
       env["PYTHON"] = sys.executable
       venv_bin = str(Path(sys.executable).parent)
       parts = [str(_shadow_dir()), venv_bin]
       for p in env.get("PATH", "").split(os.pathsep):
           if p and p not in parts:
               parts.append(p)
       env["PATH"] = os.pathsep.join(parts)
       return env
   ```

4. **Always assert the contract, not the implementation.** If the production
   code should fall back/error when Docker is absent, assert the production
   behaviour (e.g. `result.returncode != 0` AND one of several acceptable
   failure strings: `"exec: docker"`, `"docker:"`, `"service not running"`)
   so the test doesn't pin to a single host's exact errno/wording.
5. **Kill-check (C1/C2 only):** If you're shadowing to prevent a real
   side effect (container exec, network call, deploy), the test must fail
   if the shim weren't there (i.e. the script *would* have called the real
   binary). Mutate the shim to `exit 0` and confirm the test catches the
   resulting success path as a failure — this proves the shim is on the
   live path and not bypassed.

| Do | Don't |
| :--- | :--- |
| Prepend a temp dir with same-named shims | Filter PATH dirs that contain a binary (removes bash, ls, etc.) |
| Set `PYTHON=sys.executable` for scripts that invoke `${PYTHON:-python3}` | Rely on the venv being activated in the developer's shell |
| Exit 127 with an identifiable "test shim" stderr string in the shim | Silently exit 0 (masks real delegation — theater) |
| Use `atexit` / module-scope fixture for the shadow dir | Create/delete the dir in every test (noisy, slow) |
| Assert a set of acceptable failure messages | Pin the exact `docker: command not found` wording (locale/errno vary) |

---

## Decision points

1. Pyramid A or B? Session claim → C1; pure helper → C0/C0p.
2. Two-sided contract? EventType → producer + consumer. Kill-check = PRODUCER.
3. Existence pre-check? Path inventory? Matrix coverage gate? Dual-write?
4. Oracle rank + kill-check holds? Types honest? Efficiency call_count?
5. TEST-EDITS under FIX. Extract fixtures after 3rd duplication.
6. Security → adversarial. After C1 → mutation-clearing.

---

## Output format

```text
LIVE-PATH PROOF:
- root: drive_session | cli:<subcommand>
- test: tests/<file>.py::test_<name>
- matrix: A | B | C | P-<family>
- oracle: event:<kind> | outcome:<stop_reason> | trajectory | call_count
- kill-check: removing <file.py:line emit call> fails the named test
- producer: <file.py>:<line> emit call site
- paths-covered: N/M paths
- contract-check: PASS | FAIL
- efficiency: call_count=N | early-stop
- pyramid: A
```

---

## Escalation

| Situation | Action |
| :--- | :--- |
| Greens when PRODUCER emit call removed | Rewrite until kill-check on PRODUCER holds |
| Kill-check passes but emit call doesn't exist | **Vacuous pass** — write the emit call first |
| Only C0 consumer tests for EventType | Add C1 producer test |
| Test covers one path but multiple emit sites | Add path inventory, test each |
| Matrix declared but not all combos tested | Add test per combo |
| `log.append()` but no `output.emit()` on same path | Add dual-write check |
| Only unit tests for a product claim | Add C1 |
| AI theater suspected | Kill-check on PRODUCER + path inventory + mutation |

---

## Worked examples

### C1 — producer kill-check for context_warn

```python
def test_context_warn_emitted_at_budget_warn(tmp_path: Path) -> None:
    """root=drive_session matrix=A claim=context_warn OutputEvent
    kill-check=removing output.emit(OutputEvent(type="context_warn"))
    from coder_loop.py budget-warn path makes this test fail
    path-inventory: path 1 of 3 (warn threshold, non-compaction)
    """
    state, bus, capture = _make_session_with_output(tmp_path)
    mock_chain = make_mock_chain(context_limit=100000)
    mock_chain.request.return_value = mock_success_response("warn path")
    task = "A" * 300000  # ~75k tokens → triggers warn

    drive_session(
        task,
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=state,
        max_turns=1,
        output=bus,
    )

    warn_events = [e for e in capture.events if e.type == "context_warn"]
    assert len(warn_events) >= 1
```

### C1 — hard-stop with zero provider calls (efficiency)

```python
assert outcome.stop_reason == "context_budget_hard_stop"
assert mock_chain.request.call_count == 0
```

### C0 consumer-only — theater without C1 producer pair

```python
def test_context_warn_visible_at_standard_detail(capsys) -> None:
    """C0 consumer-only: proves handler renders context_warn GIVEN an event.
    INCOMPLETE without C1 producer test that verifies the emit fires.
    """
    renderer = ConsoleRenderer(detail="standard")
    event = OutputEvent(type="context_warn", data={"pct": 85})
    renderer.on_event(event)
    captured = capsys.readouterr()
    assert "85%" in captured.err
    # ⚠️ Passes even if producer emit was never written. Must pair with C1.
```

### Path inventory example

```python
"""context_warn coverage.

Path inventory:
  Path 1: Budget > warn threshold (non-compaction) — coder_loop.py L515
  Path 2: Stage3 after compaction still exceeds — coder_loop.py L974
  Path 3: Circuit breaker fires — coder_loop.py L919
"""
```

---

## Invariants

- **I-TW-1** Product session claims use C1 (or C2 if CLI-only).
- **I-TW-2** Authority is pytest in `just check`.
- **I-TW-3** Prefer `just check` over new inner-loop tools for wiring verification.
- **I-TW-4** Keep CI free of STATUS enums and allowlist files.
- **I-TW-5** Prefer events / outcomes / trajectories as primary oracles.
- **I-TW-6** Matrix coverage ENFORCED (≥1 test per combo), not just declared.
- **I-TW-7** Fixtures match production types (tuples, Optional narrowing, real registries).
- **I-TW-8** Pyramid A uses mocked LLM I/O and offline runs.
- **I-TW-9** Security claims include ≥1 adversarial case.
- **I-TW-10** Kill-check targets the PRODUCER emit call, not the consumer handler.
- **I-TW-11** `test_invariant_adr…` for ADR bindings; `*_wiring` for ordinary suites.
- **I-TW-12** Early-stop / deny claims assert low provider `call_count`.
- **I-TW-13** AI-authored tests pass anti-theater; mutation after C1.
- **I-TW-14** Two-sided contract: for every EventType, BOTH producer and consumer verified before "shipped."
- **I-TW-15** Existence pre-check: verify emit call site EXISTS. Vacuous kill-check = not shipped = theater.
- **I-TW-16** Path inventory: enumerate ALL emit paths. At least one test per path.
- **I-TW-17** CONSOLE_MIRROR_KINDS (in output.py) defines which log.append kinds MUST also emit an OutputEvent. Every kind in that set must have both a log.append producer and an output.emit producer on the same code path. The check_log_kind_contract.py script validates this.
- **I-TW-18** C0 consumer-only tests are theater without C1 producer pair.
- **I-TW-19** Contract check script MUST pass in CI for every PR touching EventTypes.
- **I-TW-20** Never mock dataclass config objects (ChainConfig, ChainEntry, CooldownRow, etc.). Use real instances via make_test_chain_config(). Only mock objects with behavior (ProviderChain, Provider, Transport). Guard: scripts/check_no_mocked_dataclasses.py
- **I-TW-21** Deleting a `Callable`-typed adapter/wrapper requires a C1 test at the real slot's calling convention, not a direct unit call to the wrapped function — mypy/pyrefly cannot catch positional parameter-semantics mismatches (AP-006, §16.7).

---

## 16. Static-quality and configuration-contract patterns

These patterns apply when an AI-authored change touches typing, dependencies,
feature flags, or quality-gate configuration. A green command is not enough;
the test must prove the intended contract and fail when the producer/config
source is removed.

### 16.1 Strict typing: type the boundary, not the symptom

Prefer a typed adapter or a narrowed composition-root value over a broad
`# type: ignore`.

```python
# Good: narrow once at the integration boundary.
log = state.log
if log is None:
    raise RuntimeError("session log is required before drive_session")

# Good: external untyped package is isolated and named.
from vendor import client  # type: ignore[import-not-found]  # optional backend; adapter below

# Bad: hides all downstream errors.
# mypy: ignore-errors
# type: ignore
```

Required proof for a strict-typing change:

1. run the type checker on the actual source tree, not installed package copies;
2. verify module identity exactly once (`module.__file__` under `src/`);
3. type shared fixtures before mass-editing tests;
4. use `Protocol`/typed result objects at untyped boundaries;
5. retain the exact error code on every ignore and a reason for the boundary;
6. add a negative check that removing the narrowing/adapter reintroduces the
   original type error.

### 16.2 Optional dependencies: runtime policy and deptry policy must agree

An import guarded by `try/except ImportError` is not automatically a valid
optional dependency. Choose and test one contract:

```python
try:
    import optional_backend
except ImportError:
    optional_backend = None

if optional_backend is None:
    return ToolResult.fail(
        "unsupported_backend",
        "PDF support is not installed; use a text format or install the approved extra",
        retryable=False,
    )
```

The dependency must then be either:

- declared in the supported extra and locked; or
- isolated behind an explicitly deferred adapter with a structured unavailable
  result and a deptry configuration/test that explains why it is absent.

Never suppress DEP001/DEP003 solely because a package is transitive or because
an import is inside `try`. Direct imports used by production code require a
first-party dependency decision.

### 16.3 Configuration thresholds: test the full matrix and the observable decision

A numeric threshold may intentionally be the feature's enable switch when
minimalism is the contract. Make that explicit and do not retain a redundant
boolean flag.

```python
compaction_enabled = config.compaction_threshold is not None
threshold = config.compaction_threshold  # presence enables; value tunes
```

Minimum C1 matrix:

| Threshold | Required oracle |
|---:|---|
| absent | no compaction producer; structured warning says disabled/unconfigured |
| present and valid | compaction producer fires using the exact configured threshold |
| present but invalid/out of range | config fails or emits a structured diagnostic; no silent enable |

Assert EventLog/session DB and EventBus consistency. A test that only inspects
the final text or only constructs a config object is incomplete. If a legacy
boolean key exists, test that it is warned about and ignored, never used as a
second decision source.

### 16.4 Configuration migration: legacy input must be observable

When removing or renaming a configuration key:

1. test valid current input;
2. test legacy input;
3. define warn/ignore, fail, or deterministic migration behavior;
4. assert the structured warning/error reaches the operator/session authority;
5. prove the legacy value cannot silently change the new decision;
6. update schema, `as_dict`, fail-open/closed sets, fixtures, and docs together.

A parser warning that is only sent to a Python logger is not sufficient when
session DB/EventLog is the project authority.

### 16.5 Quality-gate configuration: test the gate itself

For every new or changed gate, add:

- a clean-tree pass test;
- a minimal synthetic violation test;
- a test proving the gate is invoked by `just check`/CI;
- a test proving a global suppression does not hide the violation, unless the
  suppression is an explicit reviewed policy decision;
- a report of advisory versus blocking semantics.

Do not turn a blocking finding into an ignore without recording the lost
capability and a replacement signal.

### 16.6 Live-path completion for “feature added but never run”

If a feature has never been exercised against the real composition root, its
status is L1/L2, not shipped. Add a deterministic offline C1 test that boots
`drive_session`, mocks only provider I/O, uses real `ContextBudget`, real
`EventLog`, real `EventBus`, and real `FeatureFlags`/`ChainConfig`. The test
must assert:

- the configuration decision;
- the producer event and its fields;
- the consumer-visible event;
- session DB/EventLog persistence;
- provider call count/early-stop where relevant;
- the negative path when the feature is disabled.

### 16.7 Callable/Protocol parameter collapse (AP-006)

When a "de-duplication" edit deletes a thin wrapper whose only job was
adapting a function to a `Callable[...]`-typed slot (a tool's `elide=`,
an `on_event=` hook, any dependency-injected strategy function) and
points the slot directly at the wrapped function, mypy strict and
pyrefly passing is NOT proof of correctness. `Callable[[A, B], C]` is a
purely positional-arity-and-type contract — nothing checks that the
callee's 2nd parameter *means* the same thing the slot's contract
promises. See [AP-006](../../anti-patterns/AP-006-protocol-adapter-collapsed-as-duplicate.md)
for the full incident (a ~10x token-budget blowup shipped through
green mypy, pyrefly, ruff, pylint 10.00/10, and ~1900 passing tests).

```python
# Deleted as "redundant" by a duplicate-code cleanup — WRONG.
# truncate_for_preview's 2nd positional param is preview_len, not
# max_bytes; the slot calls elider(value, max_context_bytes) POSITIONALLY.
ToolSpec(..., max_context_bytes=8000, elide=truncate_for_preview)


# Kept as a named adapter — RIGHT. The seam is the contract, not duplication.
def _bash_run_elide(value: Any, _max_bytes: int) -> str:
    return truncate_for_preview(value, preview_len=500)


ToolSpec(..., max_context_bytes=8000, elide=_bash_run_elide)
```

Required proof before deleting any such wrapper:

1. grep every call site of the SLOT's type alias (not the function being
   deleted) and confirm whether it is invoked positionally or by keyword;
2. if positional, diff the slot's declared parameter roles against the
   wrapped function's own parameter names/roles — a mismatch means the
   wrapper is load-bearing, not duplicate;
3. a C1 test that boots the REAL composition root and calls through the
   actual slot (e.g. `project_for_model` → `spec.elide`), not a direct
   unit call to the wrapped function with its own keyword arguments —
   direct-call tests are exactly what passed unnoticed in the AP-006
   incident;
4. if pylint still flags the retained adapter as `duplicate-code` against
   a sibling adapter using the same shared interface, waive with a
   rationale naming the interface (AGENTS.md §Judgment rules) — do not
   delete the seam to silence the finding.
