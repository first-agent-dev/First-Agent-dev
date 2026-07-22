#!/usr/bin/env python3
"""ADR-11-I1 stdlib-only import check for authoring_tcb.py.

Verifies that ``src/fa/authoring_tcb.py`` imports only from the Python
standard library (``sys.stdlib_module_names``). This is the executable
check for ADR-11 invariant I1: the TCB kernel must not depend on any
third-party package.

Exit codes:
  0 — all imports are stdlib
  1 — non-stdlib import found

Stdlib-only (this script is itself TCB-adjacent).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

TCB_FILE = "src/fa/authoring_tcb.py"


def _repo_root() -> Path:
    here = Path(__file__).resolve().parent
    for parent in [here, *here.parents]:
        if (parent / "src" / "fa").is_dir():
            return parent
    return Path.cwd()


def check_stdlib_only(file_path: Path) -> list[str]:
    """Return list of non-stdlib top-level module names imported by file."""
    if not file_path.exists():
        return [f"{file_path} not found"]

    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    stdlib = sys.stdlib_module_names
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in stdlib and top != "__future__":
                    violations.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:  # skip relative imports
                top = node.module.split(".")[0]
                if top not in stdlib and top != "__future__":
                    violations.append(node.module)

    return violations


def main() -> int:
    repo_root = _repo_root()
    tcb_path = repo_root / TCB_FILE

    violations = check_stdlib_only(tcb_path)

    if violations:
        print(f"VIOLATION: {TCB_FILE} imports non-stdlib modules:", file=sys.stderr)
        for v in sorted(set(violations)):
            print(f"  - {v}", file=sys.stderr)
        print("ADR-11-I1 requires stdlib-only imports in the TCB kernel.", file=sys.stderr)
        return 1

    print(f"check_tcb_stdlib: {TCB_FILE} imports are stdlib-only ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
