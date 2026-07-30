"""LogKind typing contracts — behavioural, not source-text (S6.4c / S6-F5).

What this file guards
---------------------
1. ``EventLog.append(kind=...)`` is typed ``LogKind``, not ``str`` — the
   annotation *is* the enforcement mechanism, checked by pyright/mypy at lint
   time.
2. ``TraceEvent.kind`` stays ``str`` for JSONL round-trip compatibility.
3. The ``compaction_warning`` producer fires on both branches.
4. ``spawn_subagent``'s dynamic completion kind resolves to real ``LogKind``
   values.

History — why this file was rewritten (S6-F5)
---------------------------------------------
Five of the seven original tests asserted on the **source text** of production
files (``CODER_LOOP_PATH.read_text()`` plus ``assert '...' in content``).
Measured: commenting out the real ``kind="compaction_warning"`` producer and
leaving a dead comment that still contains the literal left **all 7 passing**,
while the genuine C1 suite ``test_compaction_c1_wiring.py`` **failed 2 of 5**.

A source-text assertion pins the implementation's *spelling*, not its
behaviour: it blocks refactors while permitting deletions — exactly inverted. It
also passes on code that no longer parses (the same sub-finding S3 recorded for
the regex checker).

The two ``inspect``-based tests are kept: they assert a **signature**, reachable
through the imported module object, which is a structural fact with no
behavioural equivalent. That is the line this file now draws — assert on the
module, never on its text.

Test classes: C0 (typing/signature facts) + C1 (producer behaviour).
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
from pathlib import Path
from typing import get_args

from fa.inner_loop import EventLog
from fa.inner_loop.state import TraceEvent
from fa.output import LogKind

# ── C0: the annotation IS the enforcement mechanism ────────────────────────


def test_append_kind_parameter_is_log_kind() -> None:
    """``EventLog.append(kind=...)`` must be ``LogKind``, not ``str``.

    Asserted via ``inspect.signature`` on the imported callable — a fact about
    the loaded object, not about how the file happens to be written.
    """
    param = inspect.signature(EventLog.append).parameters.get("kind")

    assert param is not None, "kind parameter not found on EventLog.append"
    assert "LogKind" in str(param.annotation), f"expected LogKind, got {param.annotation!r}"
    assert param.annotation is not str, "kind is still typed str — the contract is unenforced"


def test_trace_event_kind_is_str() -> None:
    """``TraceEvent.kind`` stays ``str`` for JSONL round-trip compatibility.

    The durable row is written and re-read as text; narrowing this field would
    make an old log with a retired kind unreadable.
    """
    fields = {f.name: f for f in dataclasses.fields(TraceEvent)}

    assert "kind" in fields, "TraceEvent.kind field not found"
    assert str(fields["kind"].type) == "str", (
        f"TraceEvent.kind must stay str for round-trip, got {fields['kind'].type!r}"
    )


def test_state_module_exposes_log_kind_symbol() -> None:
    """``state`` must actually import ``LogKind`` for the annotation to bind.

    Replaces a ``"from fa.output import LogKind" in content`` substring check.
    The module attribute is the fact that matters: an import that was moved,
    aliased or re-exported still satisfies the contract, whereas the old test
    would have failed on a harmless reformat and passed on a commented-out
    import.
    """
    import fa.inner_loop.state as state_module

    assert getattr(state_module, "LogKind", None) is LogKind, (
        "state.py does not expose the LogKind it annotates append() with"
    )


# ── C1: the compaction_warning producer, asserted by behaviour ─────────────


def test_compaction_warning_producer_is_reachable_in_the_real_loop() -> None:
    """C1: the ``compaction_warning`` producer exists as a live call site.

    **Why this is an AST assertion and not a driven path.** The three source-text
    tests this replaces claimed to check the producer. The honest replacement is
    either (a) drive ``drive_session`` and observe the row — which
    ``test_compaction_c1_wiring.py`` already does properly, so duplicating it
    here would add a second oracle for one behaviour — or (b) assert the call
    site is *live code*, which is the part the old tests got wrong: they matched
    the literal inside a comment.

    This takes (b) and does it correctly: the producer must be a real
    ``log.append(kind="compaction_warning")`` **Call node**, so a commented-out
    or stringified occurrence no longer satisfies it. Behavioural coverage
    stays where it belongs.

    Kill-check target: comment out the producer — this fails, where the five
    removed source-text tests all passed.
    """
    tree = ast.parse((Path("src/fa/inner_loop/coder_loop.py")).read_text(encoding="utf-8"))
    sites = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "append"
        and any(
            kw.arg == "kind" and isinstance(kw.value, ast.Constant) and kw.value.value == "compaction_warning"
            for kw in node.keywords
        )
    ]

    assert sites, (
        "no live log.append(kind='compaction_warning') call site in coder_loop.py — "
        "a commented-out or stringified occurrence does not count"
    )


def test_subagent_completion_kinds_are_valid_log_kinds() -> None:
    """The dynamic completion kind resolves to real ``LogKind`` members.

    ``spawn_subagent.py:71`` picks between two literals in a ternary. The old
    test grepped for both strings; this asserts the property that matters —
    whatever it picks is a member of the union ``EventLog.append`` accepts.
    """
    valid = set(get_args(LogKind))

    assert {"subagent_spawn_done", "subagent_spawn_fail"} <= valid, (
        "the subagent completion kinds are no longer valid LogKind members"
    )


def test_subagent_completion_kind_is_produced_for_both_outcomes(tmp_path: Path) -> None:
    """C1: success and failure each reach the durable log.

    Drives ``_record_subagent_completion`` — the real producer — rather than
    inspecting its source, so a rename or refactor of the ternary is fine while
    deleting the append is not.

    Kill-check target: delete the ``session.log.append`` in
    ``_record_subagent_completion``.
    """
    from types import SimpleNamespace

    from fa.inner_loop.state import SessionState
    from fa.inner_loop.tools.spawn_subagent import _record_subagent_completion

    state = SessionState(workspace_root=tmp_path, run_id="subagent-kinds")
    log = state.log
    assert log is not None
    before = len(log.read_all())

    for exit_code in (0, 1):
        _record_subagent_completion(
            state,
            task_id=f"t{exit_code}",
            role="verifier",
            envelope=SimpleNamespace(
                exit_code=exit_code,
                duration_ms=1,
                verification=f"exit_code={exit_code}",
            ),
        )

    kinds = [e.kind for e in log.read_all()[before:]]
    assert "subagent_spawn_done" in kinds, "success outcome produced no durable row"
    assert "subagent_spawn_fail" in kinds, "failure outcome produced no durable row"


# ── Guard: this file must not regress into source-text assertions ──────────


def test_this_file_contains_no_source_text_assertions() -> None:
    """C0 (S6-F5): the anti-pattern must not creep back in here.

    A test that reads a production file and asserts on a substring passes when
    the code is commented out and fails when it is merely reformatted. Having
    removed five of them, this stops the sixth from being added quietly.

    Scoped to this file on purpose: ~10 other files still carry the pattern and
    are recorded as backlog in §11.3 rather than swept in silently.
    """
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))

    # AST, so prose in docstrings (this one discusses the pattern at length)
    # cannot trip it, and a renamed variable cannot hide it.
    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "read_text"
        # reading THIS file is how the guard works; reading production files is the anti-pattern
        # Reading a file is fine; asserting on its TEXT is not. The two
        # remaining reads both feed ``ast.parse`` (this file's own guard, and
        # the producer-liveness check), which is resolution, not substring
        # matching. A bare ``assert "..." in content`` has no ast.parse and is
        # what this catches.
        and not _feeds_ast_parse(tree, node)
    ]

    assert not offenders, (
        f"source-text assertion(s) reintroduced at line(s) {offenders}; "
        "assert on the imported module, or parse with ast — never on raw text"
    )


def _feeds_ast_parse(tree: ast.Module, read_call: ast.Call) -> bool:
    """True when a ``read_text()`` result is handed straight to ``ast.parse``."""
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "parse"
            and any(arg is read_call for arg in node.args)
        ):
            return True
    return False
