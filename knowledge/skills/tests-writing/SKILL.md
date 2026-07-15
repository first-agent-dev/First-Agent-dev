---
name: tests-writing
description: |
  Production-grade rulebook for testing an LLM agent harness and AI-authored
  changes to it. Dual pyramid (deterministic harness vs model evals), live-path
  composition-root DoD (ADR-11-I9), anti-theater, type-safe fixtures, flag
  matrices, trajectories, fault/efficiency signals, security boundaries, and
  mutation handoff. Load before writing/changing tests or claiming src/fa/
  product behavior.
status: active
last-reviewed: 2026-07-16
triggers:
  - "writing or changing tests under tests/"
  - "IMPLEMENT or FIX touching src/fa/ that claims product behavior"
  - "closing an audit finding about unwired / dormant / test-theater modules"
  - "adding ContextBudget, compaction, hooks, tools, providers, or other loop surfaces"
  - "unsure whether a unit test is enough for a harness feature"
  - "designing evals vs pytest for agent quality"
  - "tests fail typecheck / Pylance on fixtures"
  - "AI-authored tests look green but may be theater"
globs:
  - "tests/**/*.py"
  - "src/fa/**/*.py"
alwaysApply: false
---

# Skill — Tests writing (agent harness, AI age)

> **Purpose.** Make First-Agent’s *authoring* and *runtime* quality legible:
> green CI means the **harness** is correct and wired; evals (later UC5) mean the
> **model path** is good enough. This skill **steers** agents writing tests.
> **Authority remains pytest inside `just check` / CI** (ADR-11-I6).
> **Contract for product surfaces:** ADR-11-I9.
>
> **Central law (live path):** *Harness behavior is done when a test that boots
> the real session path fails if the production call site is removed.*
>
> **Central law (AI systems):** *Prefer properties, schemas, trajectories, events,
> and side effects as oracles; free-text model output is secondary only.*
>
> **Central law (AI-authored tests):** *Assume oracles can be weakened; use
> kill-check, type honesty, and mutation after C1 as forcing functions.*

---

## Quick decision tree (read this first)

1. **Pyramid A or B?** Wiring / control-flow / security / harness efficiency → **A** (CI). Subjective “did the model solve it?” → **B** (UC5; scheduled / when prompts change).
2. **Session / product / loop claim?** → **C1** (or **C2** if CLI-only). Pure helper → **C0 / C0p**. Product claims use C1 as the proof class.
3. **Root?** Prefer `drive_session` (+ factories used by shipped CLI). Add C2 when CLI builds objects the unit path injects differently.
4. **Kill-check?** The test fails when the production call site / registration is removed. Otherwise rewrite until that holds.
5. **Oracle rank?** Event `kind`+fields → `SessionOutcome` → tool trajectory → provider shape/`call_count`/token band → FS → full deny dataclass. Free-text prose only as a secondary signal.
6. **Matrix?** Name **A** (gates only) / **B** (full cascade) / **C** (defaults); add provider family when cache/payload differs.
7. **Types honest?** Use `tool_calls=()`, `_require_log`, real `HookRegistry()`; fix contracts until the checker is happy (prefer real types over suppressions).
8. **Security claim?** Include ≥1 adversarial case (C3).
9. **Early-stop / efficiency claim?** Assert low or zero `request.call_count` when hard-stop/deny should fire first.
10. **AI-authored?** Run anti-theater + declare `TEST-EDITS` when changing existing tests under FIX; hand off to `mutation-clearing` after C1.
11. **Third copy of the same mocks?** Extract `tests/fixtures/session_wiring.py` (or conftest helpers).

| Priority | Prescription |
| :--- | :--- |
| **Must** (product claim) | C1/C2 + kill-check + honest types + ranked oracle + explicit matrix |
| **Should** | Fault injection; efficiency `call_count`; shared factories after duplication; `test_invariant_adr…` for ADR-binding clauses; C0p on pure math/policy; provider-family param when relevant |
| **Prefer instead** | Events/outcomes/trajectories over sole free-text equality; `hooks=HookRegistry()` over MagicMock for wiring; mocked LLM I/O over live API keys in Pyramid A; thresholds read from `ContextBudget` (and peers); kill-check over coverage % as DoD; real `drive_session` over mocking the composition root |

---

## Trigger

Load when **any** of:

1. Adding or editing `tests/**`.
2. IMPLEMENT/FIX under `src/fa/` claims session/CLI/product behavior.
3. Audit tags **DEAD / PARTIAL / TEST-THEATER**.
4. Tempted to mark a plan “shipped” because unit tests or coverage look good.
5. Designing how much to mock vs call `drive_session`.
6. Pylance/mypy complaints on fixtures (Optional log, list vs tuple, etc.).
7. Reviewing AI-authored tests for theater or decay (ADR-11-I5).

**Load scope:** test changes and/or `src/fa/` logic that claims product behavior.
Pure docs-only PRs stay outside this skill.

---

## Reference

### 0. Two pyramids (keep them separate)

```text
PYRAMID A — Deterministic harness (this skill’s home; every PR)
  C2 CLI smoke → C1 composition-root → C3 security → C0/C0p unit+properties
  Oracles: events, outcomes, call counts, schemas, token bands, FS, deny reasons
  LLM: mocked or absent

PYRAMID B — Model / agent quality (UC5; scheduled / model-prompt changes)
  Human spot → scenarios → golden+judge → deterministic output props
  Oracles: task success, faithfulness, trajectory quality, safety
  LLM: real or recorded; non-determinism managed
```

| Question | Pyramid |
| :--- | :--- |
| Is budget/compaction/hooks **wired** into the loop? | **A** (C1) |
| Does the coder model solve UC1 well? | **B** |
| Does IntentGuard deny without a trusted draft? | **A** (C3) |
| Was Stage3 *invoked* and logged? vs is the summary *useful*? | **A** vs **B** |

**v0.1 default:** A is mandatory in CI. B is Pillar 4 / UC5 — keep A fixtures
exportable (event logs / trajectories) so B can attach later. Treat kill-check
and ranked oracles as proof of correctness; treat coverage as a secondary metric.

---

### 1. Taxonomy (Pyramid A)

| Class | Boots | Use when | Complete product proof? |
| :--- | :--- | :--- | :--- |
| **C0 Unit** | Isolation | Pure helpers, parsers, estimators, redactors | Incomplete alone for session claims |
| **C0p Property** | Many inputs | Thresholds, containment, redaction, parse robustness | Complements examples; pair with C1 for product claims |
| **C1 Composition-root** | `drive_session` / real factories | **Default for `src/fa/` product behavior** | Yes (with kill-check) |
| **C2 CLI smoke** | `fa` / `_cmd_*` | Argv→factory wiring, exit codes | Yes for CLI-only claims; pair with C1 for deep loop |
| **C3 Security** | Gate + adversarial inputs | Sandbox, secrets, IntentGuard, bash, egress | Yes when adversarial cases included |
| **C4 Mutation** | Per `mutation-clearing` | After mutmut survivors | Adequacy layer after C1 |

**Default:** session → **C1** (+ C0/C0p for pure helpers).  
**Refactor-only:** keep existing C1 green; add C1 only when a new product surface
or behavior claim appears; use `TEST-EDITS` when changing existing tests under FIX.  
**Split rule:** mock **LLM I/O** (`ProviderChain.request`); exercise real registry,
hooks, budget, and prompt assembly under test.

**C0p (should):** property-style checks on pure deterministic surfaces (budget bands,
path containment, redaction). Prefer stdlib loops when Hypothesis is absent; keep
pure and free of session I/O.

---

### 2. Composition roots and L1–L3

| Root | Symbol (verify on tree) | Role |
| :--- | :--- | :--- |
| Session loop | `fa.inner_loop.coder_loop.drive_session` | Primary UC1 path |
| Registry builders | builders used by `fa run` | Tools registered |
| Hook chain | registration used by `fa run` | Middleware attached |
| Shipped CLI session drivers | `fa.cli` session commands (`run`, `workflow`, …) | CLI wires chains/flags |

Inspect-only CLIs (e.g. `fa chunk`) are roots for claims about those commands only.

| Level | Meaning | Product DoD? |
| :--- | :--- | :--- |
| L1 Import-reachable | Something imports the symbol | Incomplete |
| L2 Call-reachable | Root invokes / registers it | Incomplete |
| L3 Behavior + kill-check | Boots root; side effect; fails when call site removed | **Yes — DoD** |

---

### 3. Anti-theater checklist (C1 — all apply)

1. **Kill-check** — removing the production call site fails this test (missing event,
   wrong outcome, unexpected provider calls), using live behavior rather than a
   leftover string in an unused file.
2. **Observable side effect** — event `kind` (+ fields), `SessionOutcome`, provider
   `call_count`/payload, or product-owned FS effect.
3. **Live-path proof** — exercise the root that calls the surface; class construction
   in the test file alone is incomplete for product claims.
4. **Flag honesty** — explicit `FeatureFlags(...)`; name matrix A/B/C.
5. **Mock boundary** — mock `ProviderChain.request` / network; keep `drive_session`
   and the module under proof real.
6. **Real hook type** — `hooks=HookRegistry()` (empty OK) for wiring claims.
7. **Type-honest fixtures** — §5; resolve checker errors by matching production types.
8. **Thresholds from source** — read `ContextBudget` (and related) fields in the tree.
9. **Deterministic process** — offline; stable ordering (sort where needed); fixed clocks when time is involved.
10. **Tight AST guard (should for wiring claims)** — root still imports/calls the
    symbol under a precise pattern (module + intended attribute).
11. **Early-stop efficiency (should when claiming hard-stop/deny)** —
    `request.call_count == 0` (or expected low N).

---

### 4. Flag / provider matrix

| Matrix | Example | Proves |
| :--- | :--- | :--- |
| **A — gates only** | budget on, compaction off | Warn / stage2 allow / stage3 hard-stop before cascade |
| **B — full cascade** | both on | Stage2/3, circuit breaker, `compactor_chain` |
| **C — defaults** | `FeatureFlags()` | Operator path with stock flags |
| **P — provider family (should)** | openai vs anthropic | `cache_control` / family-specific payload |

“Stage C shipped” from **B** alone while defaults keep compaction **off** is a
**docs/review** claim (use prose/ADR; stock flags stay the operator truth until
changed). Name the matrix in the docstring; parametrize family when relevant.

---

### 5. Type-safe gold fixtures (Pylance / production honesty)

| Production contract | Use this |
| :--- | :--- |
| `ResponseInfo.tool_calls: tuple[Mapping[str, Any], ...]` | `tool_calls=()` or `tool_calls=({...},)` |
| `SessionState.log: EventLog \| None` | `log = _require_log(state); log.append(...)` |
| Event `content` values as `object` | `"x" in str(content.get("summary", ""))` |
| Hooks | `hooks=HookRegistry()` |

```python
def _require_log(state: SessionState) -> EventLog:
    """Fixtures always attach a log; narrow Optional for type checkers."""
    assert state.log is not None
    return state.log
```

```python
mock_chain = MagicMock(spec=ProviderChain)
mock_chain.config = MagicMock(spec=ChainConfig)
mock_chain.config.family = "openai"  # or "anthropic" for cache breakpoints
mock_chain.request.return_value = _mock_success_response("done")
# multi-turn: mock_chain.request.side_effect = [resp_with_tools, final_stop]
# assert mock_chain.request.call_count
```

**Factories:** after three suites copy the same mocks, extract
`tests/fixtures/session_wiring.py` (or conftest). Keep factories thin; still call
the real root. Use `tmp_path` for product-owned FS.

---

### 6. Oracles ranked (+ efficiency)

| Rank | Oracle | Good for |
| :--- | :--- | :--- |
| 1 | Session event `kind` + fields | Budget, compaction, lifecycle |
| 2 | `SessionOutcome` (`exit_code`, `stop_reason`) | Hard-stop, hook deny, exhaust |
| 3 | Tool trajectory (names, order, args schema, id pairing) | Registry + dispatch |
| 4 | Provider request shape + **`call_count`** | PromptComposer, pins, cache, **Pillar 3** |
| 5 | Token-estimate band / tools registered at start | Efficiency of harness path |
| 6 | Product-owned FS / DB rows | Artifacts, blackboard, export |
| 7 | Full deny reason / dataclass equality | C3 |
| 8 | Free-text model output | Secondary only in A |

**Primary oracles for product claims:** events, outcomes, trajectories, call counts,
and structured contracts. Coverage remains a secondary metric; import presence alone
is incomplete proof.

---

### 7. Trajectories (deterministic multi-step)

When claiming tool use / multi-step control:

1. Script `ProviderChain` with `side_effect` of `ResponseInfo` (tool_calls, then stop).
2. Assert tools run (events or registry), **tool_call_id pairing**, stop conditions.
3. When claiming multi-hook order, assert order explicitly.
4. Prefer structured trajectory oracles over identical English prose.

**State ownership (when claimed):** loop owns `SessionState`; middleware reads;
mutations stay within the documented contract (ADR-10 I-4 spirit).

---

### 8. Fault injection and efficiency (should for reliability claims)

Script failures; keep deterministic:

| Injection | Assert |
| :--- | :--- |
| Provider error / exhausted chain | `stop_reason` / events; clean stop |
| Malformed / unknown tool_calls | reject path + pairing integrity |
| Max-turns / circuit breaker / budget hard-stop | outcome correct; **`call_count` low** |
| Hook deny mid-path | stop; provider calls end |

Pillar 3: hard-stop and deny paths finish with the expected (usually minimal)
provider round-trips.

---

### 9. Security (C3)

Include ≥1 adversarial case per safety claim:

| Surface | Example |
| :--- | :--- |
| IntentGuard / pr.prepare | Mutate with missing trusted draft → deny |
| bash_intent | Opaque/exec classified for write/exec risk |
| Secret redaction | Secrets redacted on model-facing channel |
| Path containment | `../` denied |
| Egress / proxy | Agent side carries proxy token only (`test_proxy_wiring_cli.py`) |

Pair happy-path cases with adversarial ones. Prefer parametrized edges (see
`test_bash_intent.py` style).

---

### 10. Pyramid B boundary + UC5 attachment

| Eval / UC5 (B) | Pytest (A) |
| :--- | :--- |
| “Is the summary useful?” | “Was Stage3 invoked and event written?” |
| “Did the coder solve the bug?” | “Did coder get write tools?” |
| Hallucination rate | Schema-valid tool args |

**Attachment (design A for B):** prefer tests that leave inspectable session event
logs / trajectories. When UC5 lands: versioned goldens, calibrated judges,
cost/latency metrics. Gate merges on Pyramid A; promote B judges only when
calibrated and versioned.

---

### 11. Mutation handoff + AI-author patterns

| After C1 green | Next |
| :--- | :--- |
| Live path proven | Load **`mutation-clearing`** |
| Coverage high, mutants live | Strengthen oracles (that skill’s archetypes) |
| Start mutation | After C1 so mutants hit live code |

**Rewrite toward these patterns when AI-authored tests are weak:**

| Prefer | Instead of |
| :--- | :--- |
| Real assertions on events/outcomes | `assert True` / placeholders |
| Strict xfail with ADR/issue when needed | Open-ended skip / non-strict xfail |
| Ranked structured oracles | Sole free-text equality / loose prose `in` |
| Real `drive_session` + mocked provider | Mocking the composition root under proof |
| Thresholds from `ContextBudget` (source) | Invented magic ratios |
| `hooks=HookRegistry()` | MagicMock hooks for wiring claims |
| `TEST-EDITS` when changing existing tests under FIX | Silent weakening of C1 |
| Fix types to match production | `# type: ignore` on contracts |
| Adversarial + happy path for security | Happy-path-only C3 |
| C1 for product claims | C0-only “shipped” proof |

**Named invariants (should for ADR-binding clauses):**  
`test_invariant_adr11_i9_…`, `test_invariant_adr10_i4_…` — pin the contract; use
descriptive `test_*_wiring` names for ordinary live-path suites.

---

### 12. Gold files (re-read tree; copy shape)

| File | Proves |
| :--- | :--- |
| `tests/test_pr1_wiring.py` | Budget live path; warn; stage3 hard-stop with `call_count==0`; AST guard; **HookRegistry**; `_require_log`; `tool_calls=()` |
| `tests/test_pr2_wiring.py` | Pins every turn / reload / missing file |
| `tests/test_pr3_wiring.py` | PromptComposer; cache_control when enabled |
| `tests/test_pr4_wiring.py` | Stage2 mask; tail protection; events |
| `tests/test_pr5_wiring.py` | Stage3 + `compactor_chain`; summary carry-forward; circuit breaker |
| `tests/test_proxy_wiring_cli.py` | C2 CLI/proxy; agent-side proxy token only |
| `tests/test_coder_loop.py` | Mature HookRegistry + trajectory patterns |
| `tests/test_bash_intent.py` | Parametrized adversarial / compound style |

Bind thresholds to **`ContextBudget`** fields from the tree.

---

### 13. Naming, isolation, CI

| Practice | Guidance |
| :--- | :--- |
| Filenames | `test_<feature>_wiring.py` or `test_prN_wiring.py`; `test_invariant_adrN_…` when binding ADR |
| Docstring | root + matrix + claim (+ kill-check target) |
| Collection | Normal pytest; **`just check` is authority** |
| Fast loop | `uv run pytest tests/test_*wiring*.py -q` (subset of the same suite) |
| Isolation | `tmp_path`; careful monkeypatch; freeze time when wall-clock is used |
| Determinism | Offline; sort unstable collections; mock LLM always in A |

---

### 14. Sibling skills and later work

| Topic | Where |
| :--- | :--- |
| Mutmut survivors | `mutation-clearing` |
| PR INTENT / TEST-EDITS headers | `pr-creation` |
| Deep structural audit | `repo-audit` |
| Import allowlists, CodeGraph as gate, new `fs.*` tools | Outside I9 v0 scope |
| Full UC5 eval platform | Future ADR / Pillar 4 |
| Human commit-msg vs IntentGuard | Seat asymmetry (hooks soft; runtime strict) |

---

### 15. Authority vs steering

| Seat | Mechanism | Role |
| :--- | :--- | :--- |
| Steering | This skill | How to write proofs |
| Authority | pytest in `just check` / CI | Merge bar for agents on pre-push |
| Deep hunt | repo-audit / hostile skill | On demand |
| Human merge | Review | Final |

---

## Decision points

1. Pyramid A or B?
2. Session claim → C1; pure helper → C0/C0p.
3. Root: `drive_session` vs CLI.
4. Matrix A/B/C (+ family if needed).
5. Oracle rank; kill-check holds?
6. Types honest? Efficiency `call_count` if early-stop claimed?
7. `TEST-EDITS` when changing existing tests under FIX?
8. Extract fixtures after third duplication?
9. Security → adversarial case?
10. ADR-binding → prefer `test_invariant_adr…`?
11. After C1 → mutation-clearing?

---

## Output format

```text
LIVE-PATH PROOF:
- root: drive_session | cli:<subcommand>
- test: tests/<file>.py::test_<name>
- matrix: A-gates-only | B-full-cascade | C-defaults | P-<family>
- oracle: event:<kind> | outcome:<stop_reason> | trajectory | provider_calls | payload
- kill-check: removing <module.symbol / call site> fails the named test
- efficiency: call_count=N | early-stop (if claimed)
- pyramid: A
```

Optional Pyramid B:

```text
EVAL NOTE:
- gated separately from just check
- dataset: <path or TBD>
- scorer: deterministic-props | llm-judge (calibrated?) | human
```

---

## What CI / hooks validate

| Check | Surface |
| :--- | :--- |
| Tests pass | `just check` → pytest + coverage |
| Meaningful asserts (I5) | ADR-11-I5 / authoring rules |
| Test path edits under policy | `validate_test_edits` / IntentGuard |
| Types | `just check` typecheck |

Product claims need C1/C2 green for ADR-11-I9 spirit.

---

## Escalation

| Situation | Action |
| :--- | :--- |
| Huge fixture for `drive_session` | Shared fixture module; still call real root |
| Behavior only on CLI | C2; unify forked logic when present |
| Greens when call site removed | Rewrite until kill-check holds |
| Only unit tests for a loop product claim | Add C1 before done |
| Mutants after C1 | `mutation-clearing` |
| Want model prose quality signal | Pyramid B or property oracles |
| Flaky | Mock LLM; sort; isolate FS; freeze time |
| Pylance Optional/list | §5 — match production types |
| AI theater suspected | Kill-check + prefer-table + mutation |
| Efficiency claim | Assert expected `call_count` / early-stop |

---

## Worked examples

### C1 — warn on live path

```python
def test_drive_session_budget_warn_event(mock_session_state: SessionState) -> None:
    """root=drive_session matrix=A claim=budget warn; kill-check=budget path in drive_session."""
    mock_chain = MagicMock(spec=ProviderChain)
    mock_chain.config = MagicMock(spec=ChainConfig)
    mock_chain.config.context_limit = 100_000
    mock_chain.config.family = "openai"
    mock_chain.request.return_value = _mock_success_response("ok")
    # Size task so estimate_tokens enters warn band per ContextBudget source fields.
    outcome = drive_session(
        huge_task,
        provider_chain=mock_chain,
        registry=ToolRegistry(),
        hooks=HookRegistry(),
        state=mock_session_state,
        max_turns=1,
    )
    assert outcome.exit_code == 0
    kinds = [e.kind for e in _require_log(mock_session_state).read_all()]
    assert "context_budget_warn" in kinds
```

### C1 — hard-stop with zero provider calls (efficiency)

```python
assert outcome.stop_reason == "context_budget_hard_stop"
assert mock_chain.request.call_count == 0
```

### C0 complete for class API; incomplete for loop product claim

```python
def test_context_budget_unit_stages() -> None:
    b = ContextBudget(limit_tokens=100)
    assert b.check(90)["action"] in {"stage2", "stage3", "warn"}
    # Pair with C1 before claiming the session loop enforces budget.
```

---

## Invariants (skill-local)

- **I-TW-1** Product session claims use C1 (or C2 if CLI-only) as the proof class.
- **I-TW-2** Authority is pytest in `just check`.
- **I-TW-3** Prefer pytest / `just check` over new inner-loop tools for wiring verification.
- **I-TW-4** Prefer human/docs for experimental status (v0); keep CI free of STATUS enums and allowlist files.
- **I-TW-5** Prefer events / outcomes / trajectories / efficiency signals as primary oracles.
- **I-TW-6** Flag (and provider, when relevant) matrix explicit in fixture or body.
- **I-TW-7** Fixtures match production types (tuples, Optional narrowing, real HookRegistry).
- **I-TW-8** Pyramid A uses mocked LLM I/O and offline runs.
- **I-TW-9** Security claims include ≥1 adversarial case.
- **I-TW-10** Kill-check is mandatory for C1.
- **I-TW-11** Prefer `test_invariant_adr…` for new ADR-binding clauses; use `*_wiring` for ordinary live-path suites.
- **I-TW-12** Early-stop / deny claims assert low provider `call_count` where applicable.
- **I-TW-13** AI-authored tests pass anti-theater; mutation after C1 for adequacy.

---

## Prior art (selected)

**In-repo:** gold `tests/test_pr{1..5}_wiring.py`, `test_proxy_wiring_cli.py`,
`test_coder_loop.py`, `test_bash_intent.py`; ADR-11-I5/I9; ADR-10; `mutation-clearing`;
project-overview §1.2 / §1.2.5.

**Industry (AI age):** dual / agent testing pyramid (deterministic base + evals);
mock LLM / test orchestration; trajectory oracles; property/schema checks; mutation
for AI-written test adequacy; eval discipline separate from harness wiring; oracle
outside the implementer for large AI-generated changes.

---

## References

- [`ADR-11`](../../adr/ADR-11-authoring-guardrails.md) — **I9** live-path DoD; **I5** test decay
- [`ADR-10`](../../adr/ADR-10-deterministic-harness-invariants.md) — runtime I-1..I-5
- [`mutation-clearing/SKILL.md`](../mutation-clearing/SKILL.md)
- [`pr-creation/SKILL.md`](../pr-creation/SKILL.md) — TEST-EDITS
- [`repo-audit/SKILL.md`](../repo-audit/SKILL.md)
- [`AGENTS.md`](../../../AGENTS.md) — `just check`, loadable skills
- [`project-overview.md`](../../project-overview.md) — Pillars 3–4, §1.2 / §1.2.5
