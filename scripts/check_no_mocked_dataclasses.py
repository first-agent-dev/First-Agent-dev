#!/usr/bin/env python3
"""Guard: detect MagicMock(spec=<frozen_dataclass>) anti-pattern in tests.

Frozen dataclasses are pure data — no behavior, no side effects. Mocking
them with MagicMock(spec=...) creates latent regression bugs: when a new
field is added to the dataclass, the mock doesn't inherit it, so any
production code that accesses the new field raises AttributeError at runtime.

The correct pattern is to use real dataclass instances for config/value
objects, and only mock objects with behavior (methods, side effects).

This script exits 1 if it finds any violations, with file:line references.
It's wired into `just check` so CI catches the anti-pattern early.

Usage:
    python scripts/check_no_mocked_dataclasses.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import override

# UTF-8 console: this script prints non-ASCII (checkmarks / box drawing) and
# crashed with UnicodeEncodeError on a Windows host whose console was cp1251 —
# while REPORTING SUCCESS. See scripts/_console.py for the full rationale.
if __package__ in (None, ""):  # invoked as a file, not as scripts.<name>
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._console import force_utf8_stdio

force_utf8_stdio()

# Dataclasses that should NEVER be mocked with MagicMock(spec=...).
# These are pure value objects — use real instances instead.
PROTECTED_DATACLASSES = frozenset(
    {
        "ChainConfig",
        "ChainEntry",
        "CooldownRow",
        "ChainAttemptRecord",
        "RequestInfo",
        "ResponseInfo",
        "TransportResponse",
    }
)

# Directories to scan
SCAN_DIRS = ("tests",)

# File extension
SCAN_EXT = ".py"


class MagicMockDataclassVisitor(ast.NodeVisitor):
    """Walk AST to find MagicMock(spec=<ProtectedDataclass>) calls."""

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self.violations: list[tuple[int, str]] = []

    @override
    def visit_Call(self, node: ast.Call) -> None:
        # Check if this is MagicMock(spec=SomeProtectedClass)
        # or MagicMock(spec=SomeProtectedClass)
        if isinstance(node.func, ast.Name) and node.func.id == "MagicMock":
            for keyword in node.keywords:
                if keyword.arg == "spec":
                    spec_name = None
                    if isinstance(keyword.value, ast.Name):
                        spec_name = keyword.value.id
                    elif isinstance(keyword.value, ast.Attribute):
                        spec_name = keyword.value.attr
                    if spec_name and spec_name in PROTECTED_DATACLASSES:
                        self.violations.append(
                            (
                                node.lineno,
                                spec_name,
                            )
                        )
        self.generic_visit(node)


def check_file(filepath: Path) -> list[tuple[str, int, str]]:
    """Check one file for violations. Returns list of (file, line, class)."""
    source = filepath.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []  # skip files with syntax errors (not our job)

    visitor = MagicMockDataclassVisitor(str(filepath))
    visitor.visit(tree)
    return [(str(filepath), lineno, cls_name) for lineno, cls_name in visitor.violations]


def main() -> int:
    """Scan all test files and report violations."""
    violations: list[tuple[str, int, str]] = []

    for scan_dir in SCAN_DIRS:
        root = Path(scan_dir)
        if not root.is_dir():
            continue
        for filepath in root.rglob(f"*{SCAN_EXT}"):
            violations.extend(check_file(filepath))

    if not violations:
        print("✅ No MagicMock(spec=<dataclass>) violations found")
        return 0

    print("❌ FOUND MagicMock(spec=<dataclass>) — use real instances instead:")
    print()
    for violation_file, lineno, cls_name in violations:
        print(f"  {violation_file}:{lineno}  MagicMock(spec={cls_name})")
    print()
    print(f"  {len(violations)} violation(s) found.")
    print()
    print("  These frozen dataclasses are pure value objects — they have no")
    print("  behavior to mock. Use real instances via make_test_chain_config()")
    print("  or direct construction. When a new field is added to a dataclass,")
    print("  real instances inherit it via defaults; MagicMock does not.")
    print()
    print("  Rule: Mock objects with BEHAVIOR (ProviderChain, Transport).")
    print("        Never mock objects with only DATA (ChainConfig, RequestInfo).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
