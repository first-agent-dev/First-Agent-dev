#!/usr/bin/env python3
"""Count pytest-gremlins mutants per module, exactly, without running them.

Why this exists
---------------
Capacity-planning a mutation run needs a mutant count, and the cheap way to get
one -- scaling by AST-node ratio -- is badly wrong. That method estimated
~26,600 mutants for ``src/fa``; the real number is ~4,713, because most AST
nodes are not mutable by any configured operator. The 5.6x error turned a
"whole-src is infeasible" conclusion into a "whole-src takes about an hour" one.

So this asks the actual operator classes, the same ones the plugin uses:
``can_mutate(node)`` then ``mutate(node)``, counting the variants returned.

Accuracy, measured against five real gremlins runs: exact on ``stats.py`` (164),
``session_db.py`` (73) and the subagent pair (73); +2 on ``state.py`` (96 vs 94)
and +7 on ``src/fa/session`` (127 vs 120). It is a slight over-count, because
the plugin skips a few nodes at runtime that this walk accepts. Quote it as
"~4,700, slight over-count", not as an exact figure.

Usage::

    python scripts/count_mutants.py                     # summary to stdout
    python scripts/count_mutants.py --json out.json     # per-module detail
    python scripts/count_mutants.py --top 20
"""

from __future__ import annotations

import argparse
import ast
import json
import logging
from collections import defaultdict
from pathlib import Path

from pytest_gremlins.operators import (
    ArithmeticOperator,
    BooleanOperator,
    BoundaryOperator,
    ComparisonOperator,
    ReturnOperator,
)

logger = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parent.parent

# Mirrors [tool.pytest-gremlins] operators in pyproject.toml. Keep in sync: a
# count taken with a different operator set is not comparable to a real run.
OPERATORS = (
    ("comparison", ComparisonOperator()),
    ("arithmetic", ArithmeticOperator()),
    ("boolean", BooleanOperator()),
    ("boundary", BoundaryOperator()),
    ("return", ReturnOperator()),
)


def _variants(operator: object, node: ast.AST) -> int:
    """How many mutants this operator yields for this node (0 if none).

    Operators raise on node shapes they do not handle, and the set of shapes is
    not part of their public contract, so the probe is defensive by necessity.
    The failure is logged at debug rather than swallowed silently: an operator
    that starts raising on everything would otherwise report a count of zero
    and look like "no mutants here".
    """
    try:
        if not operator.can_mutate(node):  # type: ignore[attr-defined]
            return 0
        mutated = operator.mutate(node)  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001 - third-party operators raise freely on unhandled shapes
        logger.debug("operator %r skipped %s: %s", operator, type(node).__name__, exc)
        return 0
    return len(mutated) if isinstance(mutated, (list, tuple)) else 1


def count_module(path: Path) -> dict[str, int]:
    """Per-operator mutant counts for one module."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError) as exc:
        logger.warning("skipping unparseable %s: %s", path, exc)
        return {}
    nodes = list(ast.walk(tree))
    counts = {name: sum(_variants(op, node) for node in nodes) for name, op in OPERATORS}
    counts["total"] = sum(counts.values())
    return counts


def scan(root: Path) -> dict[str, dict[str, int]]:
    rows: dict[str, dict[str, int]] = {}
    for path in sorted(root.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        counts = count_module(path)
        if counts:
            rows[str(path.relative_to(REPO))] = counts
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="src/fa", help="directory to scan (default: src/fa)")
    parser.add_argument("--json", default=None, help="write per-module detail to this path")
    parser.add_argument("--top", type=int, default=15, help="how many modules to list")
    args = parser.parse_args()

    root = (REPO / args.root).resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")

    rows = scan(root)
    total = sum(row["total"] for row in rows.values())
    print(f"modules: {len(rows)}   TOTAL MUTANTS: {total}")

    by_package: dict[str, int] = defaultdict(int)
    for name, row in rows.items():
        parts = name.split("/")
        by_package["/".join(parts[:3]) if len(parts) > 3 else "/".join(parts[:2])] += row["total"]

    print("\nBy package:")
    for name, count in sorted(by_package.items(), key=lambda kv: -kv[1]):
        print(f"  {count:6d}  {name}")

    print(f"\nTop {args.top} modules:")
    for name, row in sorted(rows.items(), key=lambda kv: -kv[1]["total"])[: args.top]:
        print(f"  {row['total']:6d}  {name}")

    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8")
        print(f"\nper-module detail written to {args.json}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    raise SystemExit(main())
