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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TypeGuard

from fa.authoring_rules._scan import TEST_SCOPE, iter_python_files, node_input_hash
from fa.authoring_tcb import RuleContext, RuleResult, Severity

__all__ = ["PLACEHOLDER_ASSERTION", "TEST_SEMANTIC_DECAY"]


# --- V4 — test semantic decay (skip / xfail / focus) -----------------------


@dataclass(frozen=True)
class _PytestAliases:
    """Per-file import-alias map (I-13 evasion closure).

    ``modules`` — local names bound to the pytest module itself
    (``import pytest`` → ``pytest``; ``import pytest as pt`` → ``pt``).
    ``attrs`` — local names bound to a pytest attribute via
    ``from pytest import X [as Y]`` (``{local_name: canonical_attr}``;
    e.g. ``from pytest import skip as s`` → ``{"s": "skip"}``).

    Shadowing rule (conservative, per ADR-11 §12.4 «raise the cost of
    bypass»): a ``from pytest import`` binding is dropped from ``attrs``
    when the file ALSO defines a function/class/assignment of the same
    name anywhere — a local ``def skip(...)`` is the common legitimate
    pattern and must not flag. An adversary combining a pytest import
    WITH a same-name decoy definition is out of scope here; the V4
    catch-corpus measurement loop owns that residual.
    """

    modules: frozenset[str]
    attrs: Mapping[str, str]


_PYTEST_ATTRS_OF_INTEREST: frozenset[str] = frozenset({"skip", "mark"})


def _pytest_aliases(tree: ast.Module) -> _PytestAliases:
    modules: set[str] = set()
    attrs: dict[str, str] = {}
    shadowed: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pytest":
                    modules.add(alias.asname or "pytest")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "pytest" and node.level == 0:
                for alias in node.names:
                    if alias.name in _PYTEST_ATTRS_OF_INTEREST:
                        attrs[alias.asname or alias.name] = alias.name
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            shadowed.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    shadowed.add(target.id)
    for name in shadowed:
        attrs.pop(name, None)
    return _PytestAliases(modules=frozenset(modules), attrs=attrs)


def _is_pytest_call(node: ast.AST, attr: str, aliases: _PytestAliases) -> TypeGuard[ast.Call]:
    """Match ``pytest.<attr>(...)`` in every import shape (I-13).

    Covered shapes: ``pytest.skip(...)``, ``pt.skip(...)`` (module
    alias), ``skip(...)`` / ``s(...)`` (``from pytest import skip
    [as s]``).
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return (
            isinstance(func.value, ast.Name)
            and func.value.id in aliases.modules
            and func.attr == attr
        )
    if isinstance(func, ast.Name):
        return aliases.attrs.get(func.id) == attr
    return False


def _pytest_mark_attr(decorator: ast.expr, aliases: _PytestAliases) -> str | None:
    """If ``decorator`` is ``<pytest>.mark.<X>`` / ``mark.<X>`` (bare or
    called), return ``<X>``; otherwise ``None``. Honours module aliases
    (``pt.mark.skip``) and ``from pytest import mark`` (I-13)."""
    node: ast.expr = decorator
    if isinstance(node, ast.Call):
        node = node.func
    if not isinstance(node, ast.Attribute):
        return None
    inner = node.value
    # ``<module-alias>.mark.<X>``
    if isinstance(inner, ast.Attribute) and inner.attr == "mark":
        base = inner.value
        if isinstance(base, ast.Name) and base.id in aliases.modules:
            return node.attr
        return None
    # ``mark.<X>`` after ``from pytest import mark [as m]``
    if isinstance(inner, ast.Name) and aliases.attrs.get(inner.id) == "mark":
        return node.attr
    return None


def _xfail_has_strict_true(decorator: ast.expr) -> bool:
    """Return True iff ``decorator`` is ``pytest.mark.xfail(..., strict=True, ...)``."""
    if not isinstance(decorator, ast.Call):
        # Bare ``@pytest.mark.xfail`` (no call) cannot carry strict=True.
        return False
    for kw in decorator.keywords:
        if kw.arg == "strict" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
            return True
    return False


def _all_decorators(tree: ast.Module) -> list[ast.expr]:
    """Return every decorator expression in ``tree`` — module-level,
    nested-class, closure, comprehension-internal — by walking the
    entire AST. The function flattens; callers iterate the returned
    list. The name reflects this (was ``_iter_decorated`` but the
    function neither iterates lazily nor restricts to a single level).
    """
    decorators: list[ast.expr] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            decorators.extend(node.decorator_list)
    return decorators


def _module_scope_skip_calls(tree: ast.Module, aliases: _PytestAliases) -> set[int]:
    """Return ``{id(call_node)}`` for every ``pytest.skip(..., allow_module_level=True)``
    call appearing at module body or inside an ``If``/``Try``/``With``/``AsyncWith``
    at module body (i.e., NOT inside any ``FunctionDef`` / ``AsyncFunctionDef`` /
    ``ClassDef`` chain).

    pytest's ``allow_module_level=True`` kwarg only takes effect at module scope;
    inside a test function it is silently ignored by pytest. The exemption
    therefore requires both (a) the literal kwarg ``allow_module_level=True``
    (``ast.Constant(value=True)`` — not ``1`` or ``1.0``), and (b) the call to
    actually be at module scope.
    """
    exempt: set[int] = set()
    _walk_module_scope(tree.body, exempt, aliases)
    return exempt


def _walk_module_scope(stmts: list[ast.stmt], exempt: set[int], aliases: _PytestAliases) -> None:
    for stmt in stmts:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue  # do not recurse — calls inside functions/classes are NOT module-scope
        if isinstance(stmt, (ast.If, ast.Try, ast.With, ast.AsyncWith)):
            # Recurse into bodies that are still module-scope.
            _walk_module_scope(list(stmt.body), exempt, aliases)
            if isinstance(stmt, ast.If):
                _walk_module_scope(list(stmt.orelse), exempt, aliases)
            elif isinstance(stmt, ast.Try):
                for handler in stmt.handlers:
                    _walk_module_scope(list(handler.body), exempt, aliases)
                _walk_module_scope(list(stmt.orelse), exempt, aliases)
                _walk_module_scope(list(stmt.finalbody), exempt, aliases)
            continue
        # For other statements, scan the expression tree for pytest.skip calls
        # with the exemption kwarg.
        for inner in ast.walk(stmt):
            if _is_pytest_call(inner, "skip", aliases) and _has_allow_module_level_true(inner):
                exempt.add(id(inner))


def _has_allow_module_level_true(call: ast.Call) -> bool:
    for kw in call.keywords:
        if (
            kw.arg == "allow_module_level"
            and isinstance(kw.value, ast.Constant)
            and kw.value.value is True
        ):
            return True
    return False


class _TestSemanticDecayRule:
    """V4 family — see module docstring."""

    __name__ = "test_semantic_decay_rule"

    def __call__(self, context: RuleContext) -> Sequence[RuleResult]:
        results: list[RuleResult] = []
        for rel, source_bytes, tree in iter_python_files(context, included_prefixes=TEST_SCOPE):
            # pytest.skip(...) call expressions (anywhere in the file)
            aliases = _pytest_aliases(tree)
            exempt = _module_scope_skip_calls(tree, aliases)
            for node in ast.walk(tree):
                if _is_pytest_call(node, "skip", aliases):
                    if id(node) in exempt:
                        continue
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
            for dec in _all_decorators(tree):
                attr = _pytest_mark_attr(dec, aliases)
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
        for rel, source_bytes, tree in iter_python_files(context, included_prefixes=TEST_SCOPE):
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
