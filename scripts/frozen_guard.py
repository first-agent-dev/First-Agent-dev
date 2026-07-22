#!/usr/bin/env python3
"""Frozen integrity guard — AST scanner for frozen-dataclass mutation bypass.

Scans ``src/fa/`` for:
1. ``object.__setattr__`` calls that could bypass frozen dataclass immutability
2. Missing ``frozen=True`` on @dataclass in TCB files (authoring_tcb.py, feature_flags.py)
3. ``__post_init__`` on frozen dataclasses in TCB files (mutation bypass pattern)

Exit codes:
  0 — no violations found
  1 — violations found (prints diagnostics)

Produces ``.fa/frozen_integrity_report.md`` (best-effort, non-blocking).

Stdlib-only (ADR-11-I1).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# TCB files that MUST have frozen=True on all @dataclass
TCB_FILES = frozenset(
    {
        "src/fa/authoring_tcb.py",
        "src/fa/feature_flags.py",
    }
)

# Directories to exclude from scan (test fixtures, corpus)
EXCLUDE_PREFIXES = ("tests/", "catch-corpus/", "fp-corpus/")


def _repo_root() -> Path:
    """Find repo root by walking up from script location."""
    here = Path(__file__).resolve().parent
    for parent in [here, *here.parents]:
        if (parent / "src" / "fa").is_dir():
            return parent
    return Path.cwd()


def _is_object_setattr_call(node: ast.Call) -> bool:
    """Detect ``object.__setattr__(...)`` calls."""
    func = node.func
    if isinstance(func, ast.Attribute):
        # object.__setattr__
        if isinstance(func.value, ast.Name) and func.value.id == "object" and func.attr == "__setattr__":
            return True
    return False


def scan_object_setattr(src_dir: Path) -> list[tuple[str, int]]:
    """Find all ``object.__setattr__`` calls in src/fa/ Python files.

    Returns list of (file_path, line_number) tuples.
    """
    violations: list[tuple[str, int]] = []
    for py_file in sorted(src_dir.rglob("*.py")):
        rel = str(py_file.relative_to(src_dir.parent))
        if any(rel.startswith(p) for p in EXCLUDE_PREFIXES):
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_object_setattr_call(node):
                violations.append((rel, node.lineno))
    return violations


def scan_tcb_frozen(tcb_files: set[Path], repo_root: Path) -> list[tuple[str, str, str]]:
    """Check TCB files for missing frozen=True or __post_init__ on frozen dataclasses.

    Returns list of (file_path, class_name, issue) tuples.
    """
    violations: list[tuple[str, str, str]] = []
    for path in sorted(tcb_files):
        rel = str(path.relative_to(repo_root))
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except SyntaxError:
            continue

        # Find @dataclass classes
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            has_dataclass = any(
                (isinstance(dec, ast.Name) and dec.id == "dataclass")
                or (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == "dataclass")
                for dec in node.decorator_list
            )
            if not has_dataclass:
                continue

            # Check frozen=True
            frozen = False
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == "dataclass":
                    for kw in dec.keywords:
                        if kw.arg == "frozen" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            frozen = True

            if not frozen:
                violations.append((rel, node.name, "missing frozen=True"))

            # Check __post_init__ on frozen dataclass (mutation bypass pattern)
            if frozen:
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "__post_init__":
                        violations.append(
                            (
                                rel,
                                node.name,
                                "__post_init__ on frozen dataclass (potential mutation bypass)",
                            )
                        )

    return violations


def write_report(
    repo_root: Path, setattr_hits: list[tuple[str, int]], tcb_hits: list[tuple[str, str, str]]
) -> None:
    """Write .fa/frozen_integrity_report.md (best-effort)."""
    fa_dir = repo_root / ".fa"
    fa_dir.mkdir(parents=True, exist_ok=True)
    report_path = fa_dir / "frozen_integrity_report.md"

    lines = ["# Frozen Integrity Report\n"]
    if not setattr_hits and not tcb_hits:
        lines.append("**No violations found.** All frozen dataclasses are intact.\n")
    else:
        if setattr_hits:
            lines.append("## object.__setattr__ calls\n")
            for file_path, lineno in setattr_hits:
                lines.append(f"- `{file_path}:{lineno}`\n")
        if tcb_hits:
            lines.append("## TCB dataclass issues\n")
            for file_path, class_name, issue in tcb_hits:
                lines.append(f"- `{file_path}`: `{class_name}` — {issue}\n")

    try:
        report_path.write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        pass  # best-effort — never block the exit code


def main() -> int:
    repo_root = _repo_root()
    src_dir = repo_root / "src" / "fa"
    if not src_dir.is_dir():
        print("ERROR: src/fa/ not found", file=sys.stderr)
        return 1

    # Scan for object.__setattr__ calls
    setattr_hits = scan_object_setattr(src_dir)

    # Scan TCB files for frozen violations
    tcb_paths = {repo_root / p for p in TCB_PATHS if (repo_root / p).exists()}
    tcb_hits = scan_tcb_frozen(tcb_paths, repo_root)

    # Write report (best-effort)
    write_report(repo_root, setattr_hits, tcb_hits)

    # Print diagnostics
    if setattr_hits:
        print("VIOLATION: object.__setattr__ on frozen dataclass:", file=sys.stderr)
        for file_path, lineno in setattr_hits:
            print(f"  {file_path}:{lineno}", file=sys.stderr)

    if tcb_hits:
        print("VIOLATION: TCB dataclass issues:", file=sys.stderr)
        for file_path, class_name, issue in tcb_hits:
            print(f"  {file_path}: {class_name} — {issue}", file=sys.stderr)

    if not setattr_hits and not tcb_hits:
        print("frozen_guard: no violations found.")
        return 0

    return 1


# Alias for scan_tcb_frozen to use
TCB_PATHS = TCB_FILES

if __name__ == "__main__":
    raise SystemExit(main())
