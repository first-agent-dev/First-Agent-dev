"""V2 — ``__all__`` completeness rule (ADR-11; src/fa/authoring_rules).

If a module declares ``__all__`` it MUST list every public top-level
symbol it **defines** or **explicitly re-exports** (PEP 8 idiom
``from .x import foo as foo``).  Modules without ``__all__`` are not
inspected — the rule is opt-in by design so it never forces a churning
import policy on modules the author chose to leave un-curated.

The implementation walks the file once with stdlib :mod:`ast`
(ADR-11-I4: structural rules use AST, never regex) and emits one
:class:`~fa.authoring_tcb.RuleResult` per missing public name.

Catch-corpus mapping (ADR-11 §Verification): this rule is the consumer
of historical omissions **F-2** ("new middleware missing from
``__all__``") and **F-7** ("public helper missing from re-export").
"""

from __future__ import annotations

import ast
from collections.abc import Sequence

from fa.authoring_rules._scan import SRC_SCOPE, iter_python_files, node_input_hash
from fa.authoring_tcb import RuleContext, RuleResult, Severity

__all__ = ["EXPORTS_COMPLETENESS"]

_CODE = "FA-AUTHORING-V2-EXPORTS-COMPLETENESS"

# Module-private-by-convention identifiers that authors universally
# omit from ``__all__`` even though they are technically ALL-CAPS
# "public". Restricting this list keeps the rule honest: every other
# public-named symbol must be either in ``__all__`` or renamed with a
# leading underscore.
_CONVENTIONAL_PRIVATE: frozenset[str] = frozenset({"LOGGER", "logger", "log"})


def _literal_string_names(value: ast.expr) -> set[str] | None:
    """Return the set of string-literal names in ``value`` if it is a fully
    literal ``List`` or ``Tuple`` of ``Constant(str)``; otherwise ``None``.

    Centralises the literal-detection decision. Sets (``{"A", "B"}``) are
    rejected as opt-out: they are non-idiomatic for ``__all__`` and the
    rule cannot guarantee membership order.
    """
    if not isinstance(value, (ast.List, ast.Tuple)):
        return None
    names: set[str] = set()
    for elt in value.elts:
        if not (isinstance(elt, ast.Constant) and isinstance(elt.value, str)):
            return None  # any non-literal element makes the whole RHS unprovable
        names.add(elt.value)
    return names


_UNPROVABLE = object()  # sentinel distinct from set() and None


def _extract_all(tree: ast.Module) -> set[str] | None:
    """Return the set of names in ``__all__``, or ``None`` if the module
    declares no ``__all__`` or declares one the rule cannot fully reason
    about.

    Recognises four shapes (top-level only):

    * ``__all__ = [...]`` / ``__all__ = (...)``  (replaces working set)
    * ``__all__: list[str] = [...]``             (replaces working set;
      ignored entirely if ``value is None``)
    * ``__all__ += [...]``                       (unions into working set)

    Re-assignment is **last-wins** (matches Python). Any non-literal RHS
    on a replace operation, or any non-literal augmented operand once a
    working set exists, marks the module **unprovable** and the function
    returns ``None``.
    """
    working: set[str] | object | None = None  # None | set[str] | _UNPROVABLE
    saw_declaration = False
    for node in tree.body:
        # --- Assign: __all__ = ... ---
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    saw_declaration = True
                    names = _literal_string_names(node.value)
                    working = _UNPROVABLE if names is None else names
                    break  # multiple targets sharing __all__ in one Assign is pathological
        # --- AnnAssign: __all__: T = ... ---
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "__all__"
        ):
            if node.value is None:
                continue  # declaration without value; ignore (no runtime export set)
            saw_declaration = True
            names = _literal_string_names(node.value)
            working = _UNPROVABLE if names is None else names
        # --- AugAssign: __all__ += ... ---
        elif (
            isinstance(node, ast.AugAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "__all__"
        ):
            if working is None or working is _UNPROVABLE:
                # No prior working set OR already unprovable; the augmented
                # operation cannot make us provable. Mark unprovable if we
                # saw any declaration so far.
                if saw_declaration:
                    working = _UNPROVABLE
                continue
            names = _literal_string_names(node.value)
            if names is None:
                working = _UNPROVABLE
            else:
                # working is a set (narrowed by the conditions above)
                # Waiver: type-narrowing for mypy strict, not validation.
                assert isinstance(working, set)  # noqa: S101
                working = working | names
    if working is None or working is _UNPROVABLE:
        return None
    # Waiver: type-narrowing for mypy strict, not validation.
    assert isinstance(working, set)  # noqa: S101
    return working


# C901-baseline waiver (16>15): AST walk over many node kinds; split when
# next touched.
def _public_symbols(tree: ast.Module) -> dict[str, ast.stmt]:  # noqa: C901
    """Return ``{name: defining_node}`` for every public top-level symbol.

    "Public top-level" means: (a) the body of the module (no recursion
    into class bodies or ``if TYPE_CHECKING:`` blocks); (b) the name
    does not start with ``_``; (c) the symbol is either **defined**
    (``def`` / ``async def`` / ``class`` / ``X = ...`` / ``X: T = ...``
    / ``A, B = ...`` / ``A = B = ...``) or **explicitly re-exported**
    with PEP 8 redundant-alias idiom ``from .x import foo as foo``.

    Nested tuple unpacking (``(a, (b, c)) = ...``) is out of scope;
    backlog I-20. ``ast.Starred`` elements inside tuple unpacking are
    ignored. Bare ``import`` / ``from x import y`` statements are NOT
    counted as re-exports — the redundant-alias idiom is the codified
    opt-in.

    The returned node is the *statement* that introduces the binding;
    callers use it both for line reporting (``node.lineno``) and for
    per-finding hashing (``node_input_hash(source_bytes, node)``).
    """
    symbols: dict[str, ast.stmt] = {}

    def _register(name: str, node: ast.stmt) -> None:
        if name.startswith("_") or name in _CONVENTIONAL_PRIVATE:
            return
        symbols.setdefault(name, node)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            _register(node.name, node)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    _register(target.id, node)
                elif isinstance(target, (ast.Tuple, ast.List)):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name):
                            _register(elt.id, node)
                        # ast.Starred and nested ast.Tuple/List intentionally skipped
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                _register(node.target.id, node)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.asname is not None and alias.asname == alias.name:
                    _register(alias.asname, node)
    return symbols


class _ExportsCompletenessRule:
    """Level-1 rule callable; see module docstring for contract."""

    __name__ = "exports_completeness_rule"

    def __call__(self, context: RuleContext) -> Sequence[RuleResult]:
        results: list[RuleResult] = []
        for rel, source_bytes, tree in iter_python_files(context, included_prefixes=SRC_SCOPE):
            declared = _extract_all(tree)
            if declared is None:
                continue
            public = _public_symbols(tree)
            for name in sorted(set(public) - declared):
                defining = public[name]
                results.append(
                    RuleResult(
                        severity=Severity.HARD_BLOCK,
                        code=_CODE,
                        path=rel,
                        line=defining.lineno,
                        message=f"public symbol {name!r} is defined but not in __all__",
                        remediation=(
                            f"add {name!r} to __all__ in {rel}, "
                            f"or rename it _{name} if it is module-private"
                        ),
                        rule_input_hash=node_input_hash(source_bytes, defining),
                    )
                )
        return results


EXPORTS_COMPLETENESS = _ExportsCompletenessRule()
