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

from fa.authoring_rules._scan import iter_python_files, sha256
from fa.authoring_tcb import RuleContext, RuleResult, Severity

__all__ = ["EXPORTS_COMPLETENESS"]

_CODE = "FA-AUTHORING-V2-EXPORTS-COMPLETENESS"

# Module-private-by-convention identifiers that authors universally
# omit from ``__all__`` even though they are technically ALL-CAPS
# "public". Restricting this list keeps the rule honest: every other
# public-named symbol must be either in ``__all__`` or renamed with a
# leading underscore.
_CONVENTIONAL_PRIVATE: frozenset[str] = frozenset({"LOGGER", "logger", "log"})

# Top-level path prefixes the rule scans. Excludes test trees (where
# ``__all__`` is meaningless) and the corpora directories where
# fixtures intentionally violate the rule.
_INCLUDED_PREFIXES: tuple[str, ...] = ("src/",)


def _extract_all(tree: ast.Module) -> set[str] | None:
    """Return the set of names in ``__all__``, or ``None`` if undeclared.

    Recognises ``__all__ = [...]`` / ``__all__ = (...)`` assignments
    and the augmented form ``__all__ += [...]``. Non-literal members
    (e.g. ``*VAR``) are silently dropped: the rule cannot reason about
    them and emitting a phantom diagnostic for a dynamic re-export
    would be noise.
    """
    collected: set[str] | None = None
    for node in tree.body:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    targets.append(target)
                    value = node.value
        elif (
            isinstance(node, ast.AugAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "__all__"
        ):
            targets.append(node.target)
            value = node.value
        if not targets or value is None:
            continue
        if collected is None:
            collected = set()
        if isinstance(value, (ast.List, ast.Tuple)):
            for elt in value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    collected.add(elt.value)
    return collected


def _public_symbols(tree: ast.Module) -> dict[str, int]:
    """Return ``{name: lineno}`` for every public top-level symbol.

    "Public top-level" means: (a) the body of the module (no recursion
    into class bodies or ``if TYPE_CHECKING:`` blocks); (b) the name
    does not start with ``_``; (c) the symbol is either **defined**
    (``def`` / ``async def`` / ``class`` / ``X = ...`` / ``X: T = ...``)
    or **explicitly re-exported** with PEP 8 redundant-alias idiom
    ``from .x import foo as foo``.

    Bare ``import`` / ``from x import y`` statements are NOT counted
    as re-exports because the AST cannot distinguish an internal
    "imported to use" from an intentional "imported to re-export";
    the redundant-alias idiom is the codified opt-in.
    """
    symbols: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                symbols.setdefault(node.name, node.lineno)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and not target.id.startswith("_")
                    and target.id not in _CONVENTIONAL_PRIVATE
                ):
                    symbols.setdefault(target.id, node.lineno)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
            if (
                not name.startswith("_")
                and name not in _CONVENTIONAL_PRIVATE
                and node.value is not None
            ):
                symbols.setdefault(name, node.lineno)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if (
                    alias.asname is not None
                    and alias.asname == alias.name
                    and not alias.asname.startswith("_")
                ):
                    symbols.setdefault(alias.asname, node.lineno)
    return symbols


class _ExportsCompletenessRule:
    """Level-1 rule callable; see module docstring for contract."""

    __name__ = "exports_completeness_rule"

    def __call__(self, context: RuleContext) -> Sequence[RuleResult]:
        results: list[RuleResult] = []
        for rel, source_bytes, tree in iter_python_files(
            context, included_prefixes=_INCLUDED_PREFIXES
        ):
            declared = _extract_all(tree)
            if declared is None:
                continue
            public = _public_symbols(tree)
            file_hash = sha256(source_bytes)
            for name in sorted(set(public) - declared):
                results.append(
                    RuleResult(
                        severity=Severity.HARD_BLOCK,
                        code=_CODE,
                        path=rel,
                        line=public[name],
                        message=f"public symbol {name!r} is defined but not in __all__",
                        remediation=(
                            f"add {name!r} to __all__ in {rel}, "
                            f"or rename it _{name} if it is module-private"
                        ),
                        rule_input_hash=file_hash,
                    )
                )
        return results


EXPORTS_COMPLETENESS = _ExportsCompletenessRule()
