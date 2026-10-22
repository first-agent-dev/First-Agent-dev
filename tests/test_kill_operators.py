"""The two mutation operators: AST-level, pure, and counted. (I02/SLICE3)

What these oracles are defending, in one line each:

* a kill directive must change **exactly** what it names and nothing else;
* "the producer is missing" must stay distinguishable from "the test is weak",
  which is the slice's whole reason to exist;
* a result that was not safely applied must be impossible to run by accident.

Textual comparison is always against ``ast.unparse(ast.parse(source))`` rather
than against the source: ``ast.unparse`` drops comments and normalises layout,
so a diff against the original text would fail for reasons unrelated to any
mutation (CT55).
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

from fa.inner_loop import slice_verification
from fa.inner_loop.slice_verification import (
    KillApplication,
    KillDirective,
    KillOperator,
    apply_kill,
)


def _directive(
    operator: KillOperator,
    symbol: str,
    callee: str | None = None,
    *,
    path: str = "src/fa/example.py",
) -> KillDirective:
    return KillDirective(operator=operator, path=path, symbol=symbol, callee=callee, line=1)


def _neutralise(symbol: str) -> KillDirective:
    return _directive(KillOperator.NEUTRALISE, symbol)


def _remove_call(symbol: str, callee: str) -> KillDirective:
    return _directive(KillOperator.REMOVE_CALL, symbol, callee)


def _src(text: str) -> str:
    return textwrap.dedent(text).lstrip("\n")


def _normalised(source: str) -> str:
    """The source as the operators will render it, mutation aside."""
    return ast.unparse(ast.parse(source))


def _function(source: str, qualified: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """The one definition with this qualified name, from rendered source."""
    targets = slice_verification._resolve_targets(ast.parse(source), qualified)
    assert len(targets) == 1, f"{qualified!r} resolved to {len(targets)} definitions"
    return targets[0]


_TWO_FUNCTIONS = _src(
    """
    def keeper(a, b):
        # a comment, which ast.unparse will drop
        total = a + b
        return total

    def doomed(x):
        y = x * 2
        return y
    """
)


# --------------------------------------------------------------------------
# neutralise
# --------------------------------------------------------------------------


def test_neutralise_replaces_the_named_body_with_return_none() -> None:
    """CT55: the body goes, and what remains is `return None`."""
    result = apply_kill(_TWO_FUNCTIONS, _neutralise("doomed"))

    assert result.source is not None
    assert ast.unparse(_function(result.source, "doomed")) == "def doomed(x):\n    return None"


def test_neutralise_leaves_every_other_definition_byte_identical() -> None:
    """CT55: measured against `ast.unparse(ast.parse(source))`, not the source."""
    result = apply_kill(_TWO_FUNCTIONS, _neutralise("doomed"))

    assert result.source is not None
    before = ast.unparse(_function(_TWO_FUNCTIONS, "keeper"))
    assert ast.unparse(_function(result.source, "keeper")) == before
    assert "total = a + b" in result.source


def test_neutralise_keeps_the_signature_the_decorators_and_async() -> None:
    """A neutralised function must still be callable in every way, and only stop working.

    Deleting the `def` line instead would make the caller fail with
    `NameError` at import, which reddens the tests for a reason that has
    nothing to do with the behaviour under test.
    """
    source = _src(
        """
        import functools

        @functools.cache
        async def fetch(url, *, retries=3):
            return await get(url)
        """
    )

    result = apply_kill(source, _neutralise("fetch"))

    assert result.source is not None
    assert ast.unparse(_function(result.source, "fetch")) == (
        "@functools.cache\nasync def fetch(url, *, retries=3):\n    return None"
    )


def test_neutralise_reaches_a_method_by_its_qualified_name() -> None:
    """The case CT50b was created for: three directives name `_Silence.visit_Call`."""
    source = _src(
        """
        class Silence:
            def visit_Call(self, node):
                return node

            def leave(self, node):
                return node
        """
    )

    result = apply_kill(source, _neutralise("Silence.visit_Call"))

    assert (result.targets, result.edits) == (1, 1)
    assert result.source is not None
    assert ast.unparse(_function(result.source, "Silence.visit_Call")) == (
        "def visit_Call(self, node):\n    return None"
    )
    assert "def leave(self, node):\n        return node" in result.source


def test_neutralise_reaches_a_nested_function_by_its_qualified_name() -> None:
    source = _src(
        """
        def outer(x):
            def inner(y):
                return y + 1
            return inner(x)
        """
    )

    result = apply_kill(source, _neutralise("outer.inner"))

    assert (result.targets, result.edits) == (1, 1)
    assert result.source is not None
    assert "return inner(x)" in result.source


# --------------------------------------------------------------------------
# remove_call, including the four call forms
# --------------------------------------------------------------------------


_FOUR_CALL_FORMS = _src(
    """
    def producer(values):
        captured = emit(values)
        emit(values)
        if emit(values):
            captured = None
        return [emit(v) for v in values], captured
    """
)


def test_remove_call_sees_all_four_call_forms() -> None:
    """CT56/STEP2b: assignment, bare statement, condition, comprehension.

    Measured: deleting only `ast.Expr` statements sees 1 of these 4. The
    number is asserted exactly, because "some of them" is the failure mode --
    a half-removed producer still runs and the kill-check reports nonsense.
    """
    result = apply_kill(_FOUR_CALL_FORMS, _remove_call("producer", "emit"))

    assert result.edits == 4
    assert result.source is not None
    assert "emit" not in result.source


def test_remove_call_replaces_the_call_rather_than_deleting_the_statement() -> None:
    """The assignment must survive with `None` on the right-hand side.

    Deleting the statement would take `captured` out of scope and raise
    `NameError` at the `return` -- a red test, but red for the wrong reason.
    """
    result = apply_kill(_FOUR_CALL_FORMS, _remove_call("producer", "emit"))

    assert result.source is not None
    assert "captured = None" in result.source
    assert ast.parse(result.source) is not None


def test_remove_call_matches_a_method_call_written_through_self() -> None:
    """STEP2: an undotted directive names the attribute being called."""
    source = _src(
        """
        class Walker:
            def visit(self, node):
                self.generic_visit(node)
                return node
        """
    )

    result = apply_kill(source, _remove_call("Walker.visit", "generic_visit"))

    assert result.edits == 1
    assert result.source is not None
    assert "generic_visit" not in result.source


def test_remove_call_honours_a_dotted_callee_exactly() -> None:
    """A dotted directive is a narrower claim and must not match a bare name."""
    source = _src(
        """
        def producer(x):
            log.emit(x)
            emit(x)
            return x
        """
    )

    result = apply_kill(source, _remove_call("producer", "log.emit"))

    assert result.edits == 1
    assert result.source is not None
    assert "log.emit" not in result.source
    assert "emit(x)" in result.source


def test_remove_call_discards_the_arguments_of_the_silenced_call() -> None:
    """ "The producer never ran" means its arguments were never evaluated either."""
    source = _src(
        """
        def producer(x):
            emit(expensive(x), other(x))
            return x
        """
    )

    result = apply_kill(source, _remove_call("producer", "emit"))

    assert result.source is not None
    assert "expensive" not in result.source
    assert "other" not in result.source


def test_remove_call_ignores_a_call_whose_callee_is_neither_a_name_nor_an_attribute() -> None:
    """A dispatch table is not a producer.

    `handlers[0](x)` and `make()(x)` call something the directive cannot have
    named. Treating an unrecognised callee as a match would let one directive
    silence every indirect call in the function -- removing code the contract
    says nothing about, and reporting an `edits` count no reader can verify.
    """
    source = _src(
        """
        def producer(x):
            handlers[0](x)
            make()(x)
            emit(x)
            return x
        """
    )

    result = apply_kill(source, _remove_call("producer", "emit"))

    assert result.edits == 1
    assert result.source is not None
    assert "handlers[0](x)" in result.source
    assert "make()(x)" in result.source


def test_remove_call_leaves_identical_calls_outside_the_named_symbol_alone() -> None:
    """The directive names one enclosing symbol; the rest of the module is not its business.

    Two neighbours, one before and one after the target, because a scan that
    stops at the first match passes a fixture that only has one.
    """
    source = _src(
        """
        def before(x):
            return emit(x)

        def producer(x):
            return emit(x)

        def after(x):
            return emit(x)
        """
    )

    result = apply_kill(source, _remove_call("producer", "emit"))

    assert result.edits == 1
    assert result.source is not None
    assert ast.unparse(_function(result.source, "before")) == "def before(x):\n    return emit(x)"
    assert ast.unparse(_function(result.source, "after")) == "def after(x):\n    return emit(x)"


def test_remove_call_silences_every_call_after_the_first_one() -> None:
    """A transformer that stopped early would still satisfy a one-call fixture."""
    source = _src(
        """
        def producer(x):
            emit(1)
            emit(2)
            emit(3)
            return x
        """
    )

    result = apply_kill(source, _remove_call("producer", "emit"))

    assert result.edits == 3


# --------------------------------------------------------------------------
# resolution: absent, ambiguous, never guessed
# --------------------------------------------------------------------------


def test_an_absent_symbol_reports_zero_targets_and_no_source() -> None:
    result = apply_kill(_TWO_FUNCTIONS, _neutralise("never_written"))

    assert (result.targets, result.edits, result.source) == (0, 0, None)


def test_an_underqualified_symbol_is_absent_rather_than_a_near_match() -> None:
    """Q47: resolution is the exact qualified name, anchored at the module root.

    A bare `visit_Call` must not silently select `Silence.visit_Call`. Being
    wrong here is worse than being unhelpful: the gate would report a result
    for a symbol the plan did not name.
    """
    source = _src(
        """
        class Silence:
            def visit_Call(self, node):
                return node
        """
    )

    result = apply_kill(source, _neutralise("visit_Call"))

    assert (result.targets, result.source) == (0, None)


def test_a_doubly_defined_symbol_is_ambiguous_and_nothing_is_mutated() -> None:
    """CT57: `targets > 1` is a refusal, not a choice.

    Reachable through a `try/except ImportError` fallback or a
    platform-conditional `def`. Mutating either one would prove something
    about a function the plan did not single out.
    """
    source = _src(
        """
        def producer(x):
            return x

        def producer(x, y):
            return x + y
        """
    )

    result = apply_kill(source, _neutralise("producer"))

    assert (result.targets, result.edits, result.source) == (2, 0, None)


def test_a_class_is_not_a_kill_target() -> None:
    """ "Neutralise this class" is not a mutation the two operators can express."""
    source = _src(
        """
        class Producer:
            def run(self):
                return 1
        """
    )

    result = apply_kill(source, _neutralise("Producer"))

    assert (result.targets, result.source) == (0, None)


def test_a_present_symbol_with_no_matching_call_is_absent_not_applied() -> None:
    """The contract claims a call site. If it is not there, the claim is what is wrong."""
    source = _src(
        """
        def producer(x):
            return x + 1
        """
    )

    result = apply_kill(source, _remove_call("producer", "emit"))

    assert (result.targets, result.edits, result.source) == (1, 0, None)


def test_a_remove_call_directive_with_no_callee_matches_nothing() -> None:
    """The grammar makes `-> callee` optional because `neutralise` has none.

    A `remove-call` that reached here without one names no call site, so it
    reports absent rather than quietly removing something else.
    """
    result = apply_kill(_FOUR_CALL_FORMS, _directive(KillOperator.REMOVE_CALL, "producer", None))

    assert (result.targets, result.edits, result.source) == (1, 0, None)


# --------------------------------------------------------------------------
# the result object: two counts, and a source that cannot be run by accident
# --------------------------------------------------------------------------


def test_the_two_counts_answer_two_different_questions() -> None:
    """Q47: `targets` is a search result, `edits` is a transformation count.

    The regression this pins is the original single `hits`: under it the
    four-call sample reports 4 and is rejected as an ambiguous target, so the
    slice's headline behaviour cannot pass its own gate.
    """
    applied = apply_kill(_FOUR_CALL_FORMS, _remove_call("producer", "emit"))

    assert applied.targets == 1, "one enclosing symbol was found"
    assert applied.edits == 4, "four call sites inside it were silenced"
    assert applied.targets != applied.edits


@pytest.mark.parametrize(
    ("directive", "source"),
    [
        pytest.param(_neutralise("never_written"), _TWO_FUNCTIONS, id="absent"),
        pytest.param(_remove_call("doomed", "emit"), _TWO_FUNCTIONS, id="no_such_call"),
    ],
)
def test_source_is_none_whenever_the_result_is_not_safe_to_run(directive: KillDirective, source: str) -> None:
    """The guard against the worst available misreport.

    Running the slice's tests against unmutated source shows them passing,
    which the caller would record as VACUOUS -- a sound test accused of being
    weak, when the producer was simply missing.
    """
    assert apply_kill(source, directive).source is None


def test_the_result_refuses_to_claim_a_kill_it_did_not_make() -> None:
    """The invariant is enforced by the constructor, not by convention."""
    with pytest.raises(ValueError, match="must be present"):
        KillApplication(source=None, targets=1, edits=1)


def test_the_result_refuses_to_carry_source_it_must_not_offer() -> None:
    with pytest.raises(ValueError, match="must be None"):
        KillApplication(source="def f(): ...", targets=0, edits=0)


def test_a_mutated_source_is_always_parseable() -> None:
    """Whatever comes back must be loadable, or the overlay fails at import."""
    for directive in (_neutralise("producer"), _remove_call("producer", "emit")):
        result = apply_kill(_FOUR_CALL_FORMS, directive)
        assert result.source is not None
        ast.parse(result.source)


# --------------------------------------------------------------------------
# structural constraints
# --------------------------------------------------------------------------


def test_the_operators_touch_neither_the_filesystem_nor_a_subprocess() -> None:
    """CT58: a helper that could be pointed at the working tree would be.

    Read the AST rather than the text: the docstrings here legitimately
    mention `mutation_overlay` and writing files, and a substring scan would
    fail on the prose explaining the rule.
    """
    module = ast.parse(Path(slice_verification.__file__).read_text(encoding="utf-8"))
    forbidden = {
        "open",
        "read_text",
        "write_text",
        "mkdir",
        "unlink",
        "rmtree",
        "copytree",
        "mkdtemp",
        "run",
        "Popen",
        "check_output",
        "system",
    }
    pure = {"apply_kill", "_resolve_targets", "_neutralise_body", "_callee_matches", "_dotted_text"}

    called: set[str] = set()
    for node in ast.walk(module):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name not in pure:
            continue
        body = node.body[1:] if ast.get_docstring(node) else node.body
        for inner in body:
            for call in ast.walk(inner):
                if isinstance(call, ast.Call):
                    name = call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, "id", "")
                    called.add(name)

    assert called, "the scan found no calls at all, so it proves nothing"
    assert called.isdisjoint(forbidden), sorted(called & forbidden)


def test_exactly_two_operators_exist() -> None:
    """CT59: the guard against a mutation DSL growing one operator at a time."""
    assert len(KillOperator) == 2
    assert {op.value for op in KillOperator} == {"neutralise", "remove-call"}
