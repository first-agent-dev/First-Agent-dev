---
compiled: 2026-07-23
applies_to:
  - "AGENTS.md §Judgment rules (pylint duplicate-code waiver discipline)"
  - "knowledge/ci-guardrails-reference.md §Layer (pylint gap-profile, R0801 blocking gate)"
  - "knowledge/research/llm-agent-failure-modes-guardrails-2026-06.md row 1a (duplication — 'covered')"
  - "knowledge/skills/tests-writing/SKILL.md §16 (static-quality and configuration-contract patterns)"
  - "Any Callable/Protocol-typed hook, adapter, or dependency-injection slot"
status: accepted
evidence: commits cc71698, 5129072, 7cd362f (first-agent-dev/First-Agent-dev)
---

# AP-006 — Protocol-adapter collapsed as duplicate-code

> A thin wrapper exists ONLY to adapt a shared function's parameter
> semantics to a caller's `Callable[...]`-typed slot. An LLM session
> chasing a pylint `duplicate-code` (R0801) finding judges the wrapper
> "redundant," deletes it, and points the slot directly at the shared
> function. Every static gate stays green — mypy strict, pyrefly, ruff,
> pylint 10.00/10, ~1900 tests — because a `Callable[[A, B], C]` type
> is purely positional-arity-and-type; nothing checks that the callee's
> 2nd parameter *means* the same thing the slot's contract promises.

## §Symptom

A tool/hook/handler registry accepts a callback under a generic
`Callable[[T1, T2], R]` type alias (an "elide" callback, an
`on_event` hook, a DI-injected strategy function — any slot where the
caller invokes the callback *positionally*, per the type alias, not
by keyword). The registered callback is currently a small, named
wrapper (`_adapter(value, budget)`) whose only job is to call a
shared utility with the RIGHT keyword mapped in — often deliberately
IGNORING one of its own positional parameters, because the wrapped
function's contract does not need it (e.g. a fixed preview length
that must not scale with the caller's variable budget).

Pylint's `duplicate-code` checker flags the wrapper as near-identical
across two call sites (because it usually is — the adaptation logic
is a one-liner). A cleanup pass "de-duplicates" by deleting the
wrapper and passing the shared function straight into the slot.

## §Wrong shape

```python
# BEFORE (correct): thin adapter fixes preview_len, ignores max_bytes
def _elide_500_preview(value: Any, max_bytes: int) -> str:
    """Elide to 500-char preview + marker, for token efficiency."""
    return truncate_for_preview(value, preview_len=500)


ToolSpec(..., max_context_bytes=8000, elide=_elide_500_preview)
```

```python
# AFTER ("de-duplicated" — WRONG): wrapper deleted as "redundant"
ToolSpec(..., max_context_bytes=8000, elide=truncate_for_preview)
```

`ToolElider = Callable[[Any, int], str]`. The projection layer calls
`elider(result, spec.max_context_bytes)` — POSITIONALLY. But
`truncate_for_preview`'s own 2nd positional parameter is
`preview_len`, not `max_bytes`. The "de-duplicated" call silently
binds the tool's context budget (8000) into the fixed 500-char
preview length, producing an oversized, marker-less preview — a
~10x token-budget blowup in exactly the code whose whole job is
token efficiency. Full incident: `cc71698` ("dedub pyling") deletes
the wrapper; `5129072` ("agent work") ships the direct reference;
`7cd362f` (session review) reverts to a named adapter and adds a
composition-root kill-check that reproduces the exact regression.

## §Right shape

Never point a `Callable`-typed slot directly at a shared utility
function unless the utility's own signature IS the slot's contract,
parameter-for-parameter, by position. If an adapter exists to fix,
reorder, or drop a parameter, KEEP the adapter — it is not
duplicate code, it is the load-bearing seam between two independent
call conventions. Name it for what it does:

```python
def _bash_run_elide(value: Any, _max_bytes: int) -> str:
    """Adapt truncate_for_preview to the ToolElider protocol.

    ToolElider is Callable[[value, max_context_bytes], str], called
    POSITIONALLY. truncate_for_preview's own 2nd positional parameter
    is preview_len, not max_bytes — passing it directly would silently
    bind the caller's budget into the fixed preview length. `_max_bytes`
    is intentionally unused: this tool's preview is a fixed constant,
    not proportional to its overall budget.
    """
    return truncate_for_preview(value, preview_len=500)
```

If pylint still flags the adapter as `duplicate-code` against a
sibling adapter (e.g. two providers calling the same
`make_authenticated_request` helper with matching parameter names),
that is the interface working as intended — waive with
`# pylint: disable=duplicate-code` + a rationale naming the shared
interface, per AGENTS.md §Judgment rules. Do not delete the seam to
silence the finding.

## §Why the wrong shape dominates

1. **The type checker actively lies here.** `mypy --strict` and
   `pyrefly` both accept `elide=truncate_for_preview` with zero
   errors, because `Callable[[Any, int], str]` only checks arity and
   types, never parameter semantics. An agent trusting "green
   typecheck = correct refactor" has no signal at all that anything
   changed. This is the single most dangerous property of the bug:
   it is invisible to every static tool in this repo's gate.
2. **`duplicate-code` findings look categorically bad.** AGENTS.md's
   own Judgment rules and this project's research note
   (`llm-agent-failure-modes-guardrails-2026-06.md` row 1a) treat
   pylint `duplicate-code` as the "#1 LLM-agent smell" — correct in
   the general case, but the rule has no carve-out for "this
   duplication IS the interface contract, not copy-paste drift."
   An agent under a scope-reduction mandate ("close all R0801
   findings") reads every match as a defect to remove.
3. **Existing tests provided false confidence.** Every unit test for
   `truncate_for_preview` called it directly with the keyword arg
   (`preview_len=500`) — never through the actual protocol call site
   (`elider(value, max_context_bytes)`, positional, via the real
   `ToolSpec.elide` wiring). ~1900 tests stayed green because none of
   them exercised the live composition root; see
   [tests-writing skill §Anti-theater checklist item 4](../skills/tests-writing/SKILL.md#3-anti-theater-checklist-c1--all-apply)
   ("Live-path proof... class construction alone is incomplete").

## §Detection

1. **Before deleting any function used as a `Callable`-typed default
   or registered value** (`elide=`, `on_event=`, `key=`, any DI slot),
   grep every call site of the SLOT'S type alias (not the function
   being deleted) and confirm how it is invoked — positional vs
   keyword, and with which real runtime values. If the slot is called
   positionally and the candidate-for-deletion function's own
   parameter names differ in meaning from the slot's declared
   parameter roles, the wrapper is load-bearing.
2. **A C1 composition-root test that exercises the real call site**
   (not a direct unit call to the wrapped function) is the only
   forcing function that catches this — see
   [tests-writing skill §3 Anti-theater checklist](../skills/tests-writing/SKILL.md#3-anti-theater-checklist-c1--all-apply),
   item "Live-path proof." `tests/test_run_bash_tool_projection.py`
   (added in `7cd362f`) is the worked C1 kill-check example: it boots
   `build_run_bash_tool` → `project_for_model`, the actual chokepoint,
   and asserts the rendered string stays under budget with the tail
   marker intact — not just that `truncate_for_preview()` returns the
   right string when called directly.
3. **Rating-based pylint output is not the gate.** This repo's
   `[tool.pylint] fail-on = ["duplicate-code", "cyclic-import"]` is a
   binary presence/absence gate — "10.00/10" is cosmetic and can
   coexist with an open R0801 finding elsewhere; do not read a high
   score as "duplication was resolved correctly," only "some
   duplication was removed."

## §Linked-ADR

- [ADR-7 §2 ToolSpec](../adr/ADR-7-inner-loop-tool-registry.md) — the
  `elide: ToolElider | None` field whose contract this incident
  violated.
- [knowledge/research/llm-agent-failure-modes-guardrails-2026-06.md](../research/llm-agent-failure-modes-guardrails-2026-06.md)
  row 1a — asserts duplication is "covered" by the pylint gate;
  this entry is the counter-evidence that the gate has a
  false-positive mode requiring human/agent judgment, not blind
  compliance.
- [tests-writing skill §16](../skills/tests-writing/SKILL.md) — static-quality
  and configuration-contract patterns; this entry adds §16.7.

## §Evidence

- `cc71698` "dedub pyling" — deletes `_elide_500_preview` in both
  `src/fa/inner_loop/run_bash.py` and
  `src/fa/inner_loop/tools/run_bash.py`, replaces with
  `elide=truncate_for_preview`.
- `5129072` "agent work" — ships the same change as part of a
  broader pylint-R0801 closure pass; PR description claims "Pylint
  Rating: 10.00/10", "mypy strict passes (0 errors)", "1906 tests
  pass" — all true, none of which caught the regression.
- `7cd362f` "fix(pylint-work): repair fs_run_bash elide contract +
  close sqlite dedup test gap" — reproduction: `truncate_for_preview(value, 8000)`
  (simulating the real positional call) returns an 8286-char preview
  with no tail marker and no truncation notice, vs. the intended
  786-char preview with both, for the same input; fix restores a
  named adapter in both files; kill-check test added and verified to
  fail when the adapter is reverted to a direct reference.
