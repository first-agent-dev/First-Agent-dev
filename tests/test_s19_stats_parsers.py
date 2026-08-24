"""S19: Kill-check tests for missing log-kind parsers in fa stats.

root=parse_session matrix=C claim=all LogKinds visible to fa stats
kill-check=removing an elif branch for a new kind → UNPARSED_KINDS contract
  check or missing field in SessionAnalytics makes test fail
path-inventory: 6 new elif paths in parse_session

Covers:
- compaction_warning → CompactionWarningRecord
- compaction_circuit_breaker → CircuitBreakerRecord
- compaction_stage2_start / compaction_stage3_start → CompactionStartRecord
- model_msg → model_msg_count
- user_msg → user_msg_count
- UNPARSED_KINDS completeness: all LogKinds accounted for
"""

from __future__ import annotations

import ast
import io
import json
import sys
import typing
from pathlib import Path
from typing import Any

import pytest

from fa.output import LogKind
from fa.stats import (
    PARSED_KINDS,
    UNPARSED_KINDS,
    SessionAnalytics,
    parse_session,
    render_aggregate,
    render_session,
)


def _write_events_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    """Write synthetic events.jsonl for stats parsing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for ev in events:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")


def _base_event(run_id: str = "test-run", kind: str = "run_started", **extra: object) -> dict[str, Any]:
    return {
        "event_id": "ev-000001",
        "ts": "2026-07-20T00:00:00Z",
        "run_id": run_id,
        "harness_id": "fa-inner-loop@0.1.0",
        "actor": "runtime",
        "kind": kind,
        "content": extra,
        "tool_name": "",
        "tool_call_id": "",
        "parent_event_id": "",
    }


# ── Kill-check: compaction_warning parsed ──────────────────────────────


def test_compaction_warning_parsed(tmp_path: Path) -> None:
    """kill-check: removing compaction_warning elif → record not in analytics."""
    events_path = tmp_path / "events.jsonl"
    _write_events_jsonl(
        events_path,
        [
            _base_event(kind="run_started", role="coder"),
            _base_event(kind="compaction_warning", action="stage2", compaction_enabled=True, ratio=0.75, threshold=0.7),
            _base_event(
                kind="session_summary",
                n_turns=1,
                input_tokens=100,
                output_tokens=50,
                cache_hit_ratio=0.5,
                output_tokens_total=50,
            ),
        ],
    )
    result = parse_session(events_path)
    assert result is not None
    assert len(result.compaction_warnings) == 1
    assert result.compaction_warnings[0].action == "stage2"
    assert result.compaction_warnings[0].compaction_enabled is True
    assert result.compaction_warnings[0].ratio == 0.75


# ── Kill-check: compaction_circuit_breaker parsed ──────────────────────


def test_circuit_breaker_parsed(tmp_path: Path) -> None:
    """kill-check: removing circuit_breaker elif → record not in analytics."""
    events_path = tmp_path / "events.jsonl"
    _write_events_jsonl(
        events_path,
        [
            _base_event(kind="run_started", role="coder"),
            _base_event(kind="compaction_circuit_breaker", message="anti-thrashing loop locked"),
            _base_event(kind="session_summary", n_turns=1, input_tokens=100, output_tokens=50, cache_hit_ratio=0.5),
        ],
    )
    result = parse_session(events_path)
    assert result is not None
    assert len(result.circuit_breaker_events) == 1
    assert "anti-thrashing" in result.circuit_breaker_events[0].message


# ── Kill-check: compaction_stage*_start parsed ─────────────────────────


def test_compaction_start_parsed(tmp_path: Path) -> None:
    """kill-check: removing stage2/3 start elif → record not in analytics."""
    events_path = tmp_path / "events.jsonl"
    _write_events_jsonl(
        events_path,
        [
            _base_event(kind="run_started", role="coder"),
            _base_event(kind="compaction_stage2_start", tokens_before=120000, threshold=0.7),
            _base_event(kind="compaction_stage3_start", tokens_before=130000, threshold=0.85),
            _base_event(kind="session_summary", n_turns=1, input_tokens=100, output_tokens=50, cache_hit_ratio=0.5),
        ],
    )
    result = parse_session(events_path)
    assert result is not None
    assert len(result.compaction_starts) == 2
    assert result.compaction_starts[0].stage == 2
    assert result.compaction_starts[0].tokens_before == 120000
    assert result.compaction_starts[1].stage == 3


# ── Kill-check: model_msg / user_msg counted ───────────────────────────


def test_model_user_msg_counted(tmp_path: Path) -> None:
    """kill-check: removing model_msg/user_msg elif → counts stay 0."""
    events_path = tmp_path / "events.jsonl"
    _write_events_jsonl(
        events_path,
        [
            _base_event(kind="run_started", role="coder"),
            _base_event(kind="user_msg", text="hello"),
            _base_event(kind="model_msg", text="world", tool_calls=[], finish_reason="stop"),
            _base_event(kind="user_msg", text="hello2"),
            _base_event(kind="model_msg", text="world2", tool_calls=[], finish_reason="stop"),
            _base_event(kind="session_summary", n_turns=2, input_tokens=200, output_tokens=100, cache_hit_ratio=0.5),
        ],
    )
    result = parse_session(events_path)
    assert result is not None
    assert result.user_msg_count == 2
    assert result.model_msg_count == 2


# ── Kill-check: UNPARSED_KINDS completeness ────────────────────────────


def test_unparsed_kinds_complete() -> None:
    """C1 (S9.4 / CT4, restructured by F3): the kind partition is the expected size.

    Oracle: exact cardinalities of ``LogKind``, ``PARSED_KINDS`` and
    ``UNPARSED_KINDS``.

    **What changed and why the old assertion had to go (F3, 2026-08-01).**
    ``PARSED_KINDS`` used to be a 23-name literal in ``stats.py``, so
    ``PARSED_KINDS | UNPARSED_KINDS == set(LogKind)`` was a real question. F3
    removed that literal — ``PARSED_KINDS`` is now *derived* as
    ``set(LogKind) - UNPARSED_KINDS`` — which makes the union identity **true
    by construction**. Measured before editing: with the derivation in place,
    adding a fictional ``LogKind`` with no parser left the old union assertion
    **passing**. Keeping it would have converted a live check into the eighth
    "check that cannot fail" in this workstream, and it would have looked like
    coverage while providing none.

    So the union assertion is deleted rather than reworded, and what remains is
    the part derivation cannot make true for free: the **counts**. A new
    ``LogKind`` shifts ``len(LogKind)`` and ``len(PARSED_KINDS)`` together and
    trips this test, forcing an explicit decision — write a parser, or excuse
    the kind in ``UNPARSED_KINDS``.

    The behavioural guard is ``test_s9_parsed_kinds_matches_dispatch`` below,
    which AST-walks the real parser. That test — not the deleted literal — was
    always the thing that caught a removed ``elif``; verified by re-running it
    against the derivation.
    """
    all_kinds = set(typing.get_args(LogKind))

    # Exact counts, not loose bounds. A ">= 20" style assertion is precisely
    # how six digit-bearing kinds (compaction_stage2/3_*) went unnoticed
    # during S9 planning: a regex with no digits in its character class made
    # LogKind look 6 members smaller than it is.
    # S15: file_read added to LogKind and excused in UNPARSED_KINDS (consumed
    # by fs_exploration_metrics via direct log read, not by fa stats).
    # (TEST-EDITS declared in PR.)
    assert len(all_kinds) == 34, (
        f"LogKind changed size: {len(all_kinds)} != 34. A kind was added or removed — "
        f"decide whether fa stats parses it (add an `elif` in _parse_events) or not "
        f"(add it to UNPARSED_KINDS with a reason), then update this count."
    )
    assert len(UNPARSED_KINDS) == 11, f"UNPARSED_KINDS changed size: {len(UNPARSED_KINDS)} != 11"
    assert len(PARSED_KINDS) == 23, f"PARSED_KINDS changed size: {len(PARSED_KINDS)} != 23"

    # Derivation sanity: disjointness is NOT free. UNPARSED_KINDS is written by
    # hand and could name something outside LogKind (a typo, or a kind deleted
    # from output.py); subtraction would silently ignore it and the counts
    # above would still balance. Assert every excused kind is real.
    stray = set(UNPARSED_KINDS) - all_kinds
    assert not stray, f"UNPARSED_KINDS names kinds that are not LogKind members: {sorted(stray)}"
    assert not (set(PARSED_KINDS) & set(UNPARSED_KINDS)), "a kind cannot be both parsed and unparsed"


def _dispatched_kinds_from_source() -> set[str]:
    """AST-extract the kinds ``_parse_events`` compares against.

    Deliberately AST rather than a regex over source: S9 planning produced a
    confident, entirely fictional finding because a ``[a-z_]+`` character
    class silently dropped every kind containing a digit. Parsing the code the
    interpreter parses is the only honest way to ask "what does this dispatch
    on".
    """
    tree = ast.parse(Path("src/fa/stats.py").read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_parse_events")
    kinds: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == "kind":
            for op, comparator in zip(node.ops, node.comparators, strict=True):
                if (
                    isinstance(op, ast.Eq)
                    and isinstance(comparator, ast.Constant)
                    and isinstance(comparator.value, str)
                ):
                    kinds.add(comparator.value)
    return kinds


def test_s9_parsed_kinds_matches_dispatch() -> None:
    """C1 (S9.4 / CT4): ``PARSED_KINDS`` equals what ``_parse_events`` dispatches on.

    This is the test the old hardcoded list could not be. Removing an
    ``elif kind == "..."`` branch used to leave the contract test green,
    because the test's own literal still claimed the kind was parsed. Now the
    claim is derived from the parser itself, so deletion is detected.

    Oracle: AST-derived set == the module's declared frozenset.
    Kill-check target: delete any ``elif kind == "<name>"`` branch in
    ``_parse_events`` — verified during S9 execution, not assumed.
    """
    dispatched = _dispatched_kinds_from_source()

    # Liveness control: an AST walk that silently returned nothing would make
    # the equality below vacuous against an empty PARSED_KINDS.
    assert len(dispatched) == 23, f"AST derivation found {len(dispatched)} kinds, expected 23"

    assert dispatched == set(PARSED_KINDS), (
        f"PARSED_KINDS drifted from _parse_events. "
        f"declared-not-dispatched={sorted(set(PARSED_KINDS) - dispatched)} "
        f"dispatched-not-declared={sorted(dispatched - set(PARSED_KINDS))}"
    )


# ── Kill-check: UNPARSED_KINDS are valid LogKind members ───────────────


def test_unparsed_kinds_are_valid_logkinds() -> None:
    """Every member of UNPARSED_KINDS must be a valid LogKind."""
    valid = set(typing.get_args(LogKind))
    invalid = set(UNPARSED_KINDS) - valid
    assert not invalid, f"UNPARSED_KINDS contains invalid LogKind values: {sorted(invalid)}"


def _make_analytics(run_id: str = "i41-run") -> SessionAnalytics:
    """Minimal renderable analytics object for the I-41 stream tests."""
    return SessionAnalytics(
        run_id=run_id,
        role="coder",
        start_ts="2026-08-01T00:00:00Z",
        stop_reason="stopped_by_llm",
        ok=True,
        turns=1,
    )


# ── I-41: import-time stream binding (third instance of the class) ──────────


def test_i41_render_session_resolves_stderr_at_call_time(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """FIX-regression (I-41): the default stream is resolved per CALL, not per import.

    degree-of-freedom-closed: before, ``stream: TextIO = sys.stderr`` was
    evaluated once at **import** time, so the module permanently held whichever
    object ``sys.stderr`` happened to be during the first import. Any later
    rebinding — pytest's ``capsys``, a CLI that redirects, a test harness, a
    daemon reopening its logs — was ignored. Now the parameter defaults to
    ``None`` and resolves ``sys.stderr`` inside the body, so there is no window
    in which a stale stream can be captured.

    deterministic-mechanism: the test rebinds ``sys.stderr`` to a fresh buffer
    **after** ``fa.stats`` is already imported, then asserts the render lands in
    the new buffer. Nothing about timing or ordering is left to chance.

    sibling-callers-checked: ``render_aggregate`` had the identical signature
    and is covered by the sibling test below. A repo-wide grep for
    ``= sys.stderr``/``= sys.stdout`` in a ``def`` line found exactly these two
    sites; both are fixed.

    mutation: restore ``stream: TextIO = sys.stderr`` → this test fails because
    the write goes to the import-time object rather than the rebound one.

    **This was a live defect, not a style point.** It surfaced as
    ``ValueError: I/O operation on closed file`` from ``src/fa/stats.py:663``
    when an S10b parity test ran after another test that had already exercised
    the renderer: the module was writing to a capsys buffer that pytest had
    since closed. Passing alone and failing in the suite is evidence about the
    module, not the suite. Third instance after V10 (``state.py``) and S8.8
    (``global_history.py``).

    Class: C0p. Oracle: the rebound stream receives the report.
    Kill-check target: the ``stream if stream is not None else sys.stderr``
    resolution.
    """
    analytics = _make_analytics()

    replacement = io.StringIO()
    monkeypatch.setattr(sys, "stderr", replacement)
    render_session(analytics)

    assert "Session: i41-run" in replacement.getvalue(), (
        "render_session wrote to the import-time stderr, not the current one"
    )


def test_i41_render_aggregate_resolves_stderr_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """FIX-regression (I-41): ``render_aggregate`` has the same fix as its sibling.

    degree-of-freedom-closed: same import-time binding, same resolution.
    deterministic-mechanism: rebind ``sys.stderr`` post-import, assert the
    report lands there.
    sibling-callers-checked: this IS the sibling of ``render_session``; the two
    were the only occurrences of the pattern in ``src/fa``.
    mutation: restore the old default → fails.

    Class: C0p. Oracle: the rebound stream receives the aggregate header.
    Kill-check target: the stream resolution in ``render_aggregate``.
    """
    replacement = io.StringIO()
    monkeypatch.setattr(sys, "stderr", replacement)
    render_aggregate([_make_analytics()])

    assert "sessions" in replacement.getvalue()


def test_i41_explicit_stream_still_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """FIX-regression (I-41): passing ``stream=`` explicitly still overrides the default.

    The positive control. Without it, "resolves at call time" could be
    satisfied by a fix that ignored the parameter entirely and always wrote to
    ``sys.stderr`` — which would silently break ``fa stats``'s own callers.

    degree-of-freedom-closed: pins that the ``None`` sentinel means "use the
    current default", not "ignore the argument".
    deterministic-mechanism: an explicit buffer distinct from a rebound
    ``sys.stderr``; the assertion separates the two.
    mutation: change the body to always use ``sys.stderr`` → this fails.

    Class: C0p. Oracle: the explicit stream gets the output; the ambient one
    stays empty.
    """
    ambient = io.StringIO()
    explicit = io.StringIO()
    monkeypatch.setattr(sys, "stderr", ambient)

    render_session(_make_analytics(), stream=explicit)

    assert "Session: i41-run" in explicit.getvalue()
    assert ambient.getvalue() == "", "an explicit stream must not also write to sys.stderr"
