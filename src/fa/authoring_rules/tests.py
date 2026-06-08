"""V4 + V11 — test semantic-decay lock (ADR-11-I5; src/fa/authoring_rules).

Two Level-1 rules implementing the HARD-BLOCK items of ADR-11-I5
("test semantic decay lock"). Both inspect Python files under
``tests/`` via stdlib :mod:`ast` (ADR-11-I4: AST, never regex) and
return zero or more :class:`~fa.authoring_tcb.RuleResult` entries.

V4 — :data:`TEST_SEMANTIC_DECAY` — emits one of three diagnostic
codes per offending node:

* ``FA-AUTHORING-V4-PYTEST-SKIP`` — ``pytest.skip(...)`` call or
  ``@pytest.mark.skip`` decorator (NOT ``skipif``: cross-platform
  conditional skips are a legitimate pattern and the codebase uses
  them extensively for ``shutil.which("bash")``-style guards).
* ``FA-AUTHORING-V4-NON-STRICT-XFAIL`` — ``@pytest.mark.xfail``
  decorator without an explicit ``strict=True`` keyword. Per
  ADR-11-I5 a non-strict xfail can silently pass and hide a bug
  that was "fixed by accident".
* ``FA-AUTHORING-V4-FOCUS-MARKER`` — ``@pytest.mark.focus`` /
  ``@pytest.mark.only`` decorators. Pytest itself has no ``.only``
  builtin; this is defensive against third-party plugin patterns
  that would silently shrink the test suite.

V11 — :data:`PLACEHOLDER_ASSERTION` — emits
``FA-AUTHORING-V11-PLACEHOLDER-ASSERT`` for tautological assertions
that compile to "obviously true": ``assert True``, ``assert <literal>
== <same literal>`` (``assert 1 == 1``), ``assert True is True``,
``assert False is False``, and the named-variable identity check
``assert x == x`` (where both sides are bare :class:`ast.Name` nodes
with the same ``id``). The rule deliberately does **not** flag
``assert f() == f()`` — calling the same function twice and comparing
results is a meaningful purity / determinism check.

V11 additionally emits ``FA-AUTHORING-V11-CONTRADICTORY-ASSERT`` for
self-contradictory comparisons ``assert X is not X`` (same atom on both
sides): structurally a placeholder too, but it always *fails* when run,
so a distinct code lets the remediation name the real error.

Catch-corpus mapping (ADR-11 §Verification): V11 is the consumer of
historical omission **F-9** ("test weakened from ``==`` to ``in``").
"""

from __future__ import annotations

import ast
from collections.abc import Sequence
from typing import TypeGuard

from fa.authoring_rules._scan import iter_python_files, node_input_hash
from fa.authoring_tcb import RuleContext, RuleResult, Severity

__all__ = ["PLACEHOLDER_ASSERTION", "TEST_SEMANTIC_DECAY"]

# Top-level path prefixes the rules scan. Excludes ``src/`` (decay
# rules are about test semantics) and the corpora directories where
# fixtures intentionally violate the rule.
_INCLUDED_PREFIXES: tuple[str, ...] = ("tests/",)


# --- V4 — test semantic decay (skip / xfail / focus) -----------------------


def _is_pytest_call(node: ast.AST, attr: str) -> TypeGuard[ast.Call]:
    """Match ``pytest.<attr>(...)`` call expressions, exact match on ``attr``."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "pytest"
        and func.attr == attr
    )


def _pytest_mark_attr(decorator: ast.expr) -> str | None:
    """If ``decorator`` is ``pytest.mark.<X>`` or ``pytest.mark.<X>(...)``,
    return ``<X>``; otherwise return ``None``."""
    node: ast.expr = decorator
    if isinstance(node, ast.Call):
        node = node.func
    if not isinstance(node, ast.Attribute):
        return None
    inner = node.value
    if not (isinstance(inner, ast.Attribute) and inner.attr == "mark"):
        return None
    base = inner.value
    if not (isinstance(base, ast.Name) and base.id == "pytest"):
        return None
    return node.attr


def _xfail_has_strict_true(decorator: ast.expr) -> bool:
    """Return True iff ``decorator`` is ``pytest.mark.xfail(..., strict=True, ...)``."""
    if not isinstance(decorator, ast.Call):
        # Bare ``@pytest.mark.xfail`` (no call) cannot carry strict=True.
        return False
    for kw in decorator.keywords:
        if kw.arg == "strict" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
            return True
    return False


def _iter_decorated(tree: ast.Module) -> Sequence[ast.expr]:
    """Yield every decorator expression attached to any function/class.

    Walks the whole tree (nested classes / closures included) so a
    ``@pytest.mark.skip`` on an inner helper isn't missed.
    """
    decorators: list[ast.expr] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            decorators.extend(node.decorator_list)
    return decorators


class _TestSemanticDecayRule:
    """V4 family — see module docstring."""

    __name__ = "test_semantic_decay_rule"

    def __call__(self, context: RuleContext) -> Sequence[RuleResult]:
        results: list[RuleResult] = []
        for rel, source_bytes, tree in iter_python_files(
            context, included_prefixes=_INCLUDED_PREFIXES
        ):
            # pytest.skip(...) call expressions (anywhere in the file)
            for node in ast.walk(tree):
                if _is_pytest_call(node, "skip"):
                    results.append(
                        RuleResult(
                            severity=Severity.HARD_BLOCK,
                            code="FA-AUTHORING-V4-PYTEST-SKIP",
                            path=rel,
                            line=node.lineno,
                            message=(
                                "pytest.skip(...) call hides a test from the suite; "
                                "fix the test or delete it"
                            ),
                            remediation=(
                                "remove the pytest.skip(...) call and address the "
                                "underlying failure, OR convert to "
                                "pytest.skipif(<env-condition>, ...) "
                                "if the skip is platform/dependency conditional"
                            ),
                            rule_input_hash=node_input_hash(source_bytes, node),
                        )
                    )

            # Decorator-style markers (skip / xfail / focus / only).
            for dec in _iter_decorated(tree):
                attr = _pytest_mark_attr(dec)
                if attr is None:
                    continue
                if attr == "skip":
                    results.append(
                        RuleResult(
                            severity=Severity.HARD_BLOCK,
                            code="FA-AUTHORING-V4-PYTEST-SKIP",
                            path=rel,
                            line=dec.lineno,
                            message=(
                                "@pytest.mark.skip decorator hides a test from the suite; "
                                "fix the test or delete it"
                            ),
                            remediation=(
                                "remove the @pytest.mark.skip decorator and address "
                                "the underlying failure, OR convert to "
                                "@pytest.mark.skipif(<env-condition>) if the skip is "
                                "platform/dependency conditional"
                            ),
                            rule_input_hash=node_input_hash(source_bytes, dec),
                        )
                    )
                elif attr == "xfail" and not _xfail_has_strict_true(dec):
                    results.append(
                        RuleResult(
                            severity=Severity.HARD_BLOCK,
                            code="FA-AUTHORING-V4-NON-STRICT-XFAIL",
                            path=rel,
                            line=dec.lineno,
                            message=(
                                "@pytest.mark.xfail without strict=True can silently pass; "
                                "ADR-11-I5 requires strict=True"
                            ),
                            remediation=(
                                "add strict=True to the xfail decorator so an "
                                "unexpected pass fails the suite"
                            ),
                            rule_input_hash=node_input_hash(source_bytes, dec),
                        )
                    )
                elif attr in ("focus", "only"):
                    results.append(
                        RuleResult(
                            severity=Severity.HARD_BLOCK,
                            code="FA-AUTHORING-V4-FOCUS-MARKER",
                            path=rel,
                            line=dec.lineno,
                            message=(
                                f"@pytest.mark.{attr} silently shrinks the test "
                                "suite; remove before commit"
                            ),
                            remediation=(
                                f"remove the @pytest.mark.{attr} decorator; "
                                "use the `-k` selector locally instead"
                            ),
                            rule_input_hash=node_input_hash(source_bytes, dec),
                        )
                    )
        return results


TEST_SEMANTIC_DECAY = _TestSemanticDecayRule()


# --- V11 — placeholder assertions ------------------------------------------


def _is_bare_true(expr: ast.expr) -> bool:
    return isinstance(expr, ast.Constant) and expr.value is True


def _is_trivial_self_compare(expr: ast.expr) -> bool:
    """Match ``X == X`` / ``X is X`` where both sides are the same ``ast.Name``
    or the same ``ast.Constant`` literal.

    Function calls and attribute accesses (``f() == f()``, ``a.b == a.b``)
    are deliberately NOT considered tautologies — those can legitimately
    assert determinism / purity.
    """
    if not isinstance(expr, ast.Compare):
        return False
    if len(expr.ops) != 1 or len(expr.comparators) != 1:
        return False
    if not isinstance(expr.ops[0], (ast.Eq, ast.Is)):
        return False
    return _is_same_atom(expr.left, expr.comparators[0])


def _is_contradictory_self_compare(expr: ast.expr) -> bool:
    """Match ``X is not X`` where both sides are the same atom.

    This is structurally a placeholder pattern too — the test will always
    fail when executed — but it merits a distinct diagnostic so the
    remediation text can name the actual error (the test is broken, not
    just trivial).
    """
    if not isinstance(expr, ast.Compare):
        return False
    if len(expr.ops) != 1 or len(expr.comparators) != 1:
        return False
    if not isinstance(expr.ops[0], ast.IsNot):
        return False
    return _is_same_atom(expr.left, expr.comparators[0])


def _is_same_atom(left: ast.expr, right: ast.expr) -> bool:
    """True if ``left`` and ``right`` are the same Name or same Constant literal."""
    if isinstance(left, ast.Name) and isinstance(right, ast.Name) and left.id == right.id:
        return True
    if (
        isinstance(left, ast.Constant)
        and isinstance(right, ast.Constant)
        and type(left.value) is type(right.value)
        and left.value == right.value
    ):
        return True
    return False


class _PlaceholderAssertionRule:
    """V11 — see module docstring."""

    __name__ = "placeholder_assertion_rule"

    def __call__(self, context: RuleContext) -> Sequence[RuleResult]:
        results: list[RuleResult] = []
        for rel, source_bytes, tree in iter_python_files(
            context, included_prefixes=_INCLUDED_PREFIXES
        ):
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assert):
                    continue
                test = node.test
                if _is_bare_true(test) or _is_trivial_self_compare(test):
                    results.append(_placeholder_finding(rel, source_bytes, node))
                elif _is_contradictory_self_compare(test):
                    results.append(_contradictory_finding(rel, source_bytes, node))
        return results


def _placeholder_finding(rel: str, source_bytes: bytes, node: ast.Assert) -> RuleResult:
    return RuleResult(
        severity=Severity.HARD_BLOCK,
        code="FA-AUTHORING-V11-PLACEHOLDER-ASSERT",
        path=rel,
        line=node.lineno,
        message=(
            "placeholder assertion asserts only a tautology; "
            "ADR-11-I5 requires every test assertion to validate dynamic behaviour"
        ),
        remediation=(
            "replace the assertion with one that exercises the code under test, "
            "or delete the test if it has no real coverage"
        ),
        rule_input_hash=node_input_hash(source_bytes, node),
    )


def _contradictory_finding(rel: str, source_bytes: bytes, node: ast.Assert) -> RuleResult:
    return RuleResult(
        severity=Severity.HARD_BLOCK,
        code="FA-AUTHORING-V11-CONTRADICTORY-ASSERT",
        path=rel,
        line=node.lineno,
        message=(
            "self-contradictory assertion will always fail when executed; "
            "the test is broken, not merely a placeholder"
        ),
        remediation=(
            "rewrite the assertion to compare distinct values, or delete "
            "the test if it should never run"
        ),
        rule_input_hash=node_input_hash(source_bytes, node),
    )


PLACEHOLDER_ASSERTION = _PlaceholderAssertionRule()
