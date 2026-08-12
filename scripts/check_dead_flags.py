#!/usr/bin/env python3
"""Detect dead FeatureFlags fields and phantom getattr flags (HR3).

A "dead flag" is a FeatureFlags dataclass field with zero production references
in `src/fa/` (excluding tests and the definition itself).

A "phantom flag" is a string literal used in `getattr(feature_flags, "name")`
or `getattr(ff, "name")` that is NOT declared in the FeatureFlags dataclass.
These are runtime-accessed flags with no schema entry — potential bugs or
undocumented features.

Exit codes:
    0 — no dead flags found (phantom flags are warnings, not errors)
    1 — dead flags found
    2 — usage error

This file is itself a regression guard per ADR-11 HR3.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any

# scripts/ is not a pip-installed package; shim sys.path when invoked as a file,
# matching the pattern used by check_workflow_hygiene.py.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._console import (
    add_output_arg,
    add_repo_root_arg,
    force_utf8_stdio,
    resolve_repo_root,
)

# --- Configuration ---

_FEATURE_FLAGS_MODULE = "src/fa/feature_flags.py"
_SEARCH_ROOTS = ("src/fa",)
_EXCLUDE_DIRS: frozenset[str] = frozenset({"__pycache__", "tests"})


def _get_declared_fields(repo_root: Path) -> list[str]:
    """Extract field names from FeatureFlags dataclass via import."""
    sys.path.insert(0, str(repo_root / "src"))
    try:
        from fa.feature_flags import FeatureFlags

        return [f.name for f in fields(FeatureFlags)]
    finally:
        sys.path.pop(0)


def _collect_py_files(repo_root: Path) -> list[Path]:
    """Collect .py files under search roots, excluding test/cache dirs."""
    py_files: list[Path] = []
    for root_name in _SEARCH_ROOTS:
        root = repo_root / root_name
        if not root.is_dir():
            continue
        for py in root.rglob("*.py"):
            rel = py.relative_to(repo_root)
            # Skip files in excluded dirs
            parts = rel.parts
            if any(p in _EXCLUDE_DIRS for p in parts):
                continue
            # Skip the definition file itself
            if str(rel) == _FEATURE_FLAGS_MODULE:
                continue
            py_files.append(py)
    return py_files


def _count_field_usage(field_name: str, py_files: list[Path]) -> list[dict[str, Any]]:
    """Find production references to a FeatureFlags field name.

    Searches for:
    - Direct attribute access: `.field_name` after feature_flags/ff/flags
    - getattr patterns: `getattr(*, "field_name"`
    """
    refs: list[dict[str, Any]] = []
    # Pattern: attribute access like .field_name (not inside string)
    # We use AST for precision on getattr, regex for quick attribute scan.
    attr_pattern = re.compile(
        rf"""
        \.({re.escape(field_name)})\b       # .field_name
        |
        getattr\s*\([^)]*['\"]({re.escape(field_name)})['\"]  # getattr(..., "field_name")
        """,
        re.VERBOSE,
    )
    for py_file in py_files:
        try:
            text = py_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in attr_pattern.finditer(text):
            line_no = text[: match.start()].count("\n") + 1
            refs.append({"file": str(py_file), "line": line_no})
    return refs


def _find_regex_phantom_flags(
    text: str,
    py_file: Path,
    declared: set[str],
) -> list[dict[str, Any]]:
    """Find undeclared flag names using the tolerant source-text scan."""
    pattern = re.compile(
        r"""getattr\s*\(\s*
        (?:[\w.]*feature_flags|ff|flags)\s*,\s*
        ['"]([^'"]+)['"]""",
        re.VERBOSE,
    )
    results: list[dict[str, Any]] = []
    for match in pattern.finditer(text):
        name = match.group(1)
        if name not in declared:
            results.append({"name": name, "file": str(py_file), "line": text[: match.start()].count("\n") + 1})
    return results


def _is_feature_flags_getattr(node: ast.Call) -> bool:
    """Whether an AST getattr call targets a likely FeatureFlags object."""
    if len(node.args) < 2:
        return False
    first = node.args[0]
    if isinstance(first, ast.Name):
        return first.id in {"ff", "flags", "feature_flags"}
    return isinstance(first, ast.Attribute) and first.attr == "feature_flags"


def _find_ast_phantom_flags(
    text: str,
    py_file: Path,
    declared: set[str],
) -> list[dict[str, Any]]:
    """Find undeclared flag names using precise AST inspection."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    results: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "getattr":
            continue
        if not _is_feature_flags_getattr(node):
            continue
        second = node.args[1]
        if not isinstance(second, ast.Constant) or not isinstance(second.value, str):
            continue
        name = second.value
        if name in declared:
            continue
        results.append({"name": name, "file": str(py_file), "line": node.lineno})
    return results


def _find_phantom_getattr_flags(py_files: list[Path], declared: set[str]) -> list[dict[str, Any]]:
    """Find undeclared ``getattr`` FeatureFlags accesses using regex and AST scans."""
    phantom: list[dict[str, Any]] = []
    for py_file in py_files:
        try:
            text = py_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        candidates = _find_regex_phantom_flags(text, py_file, declared)
        candidates.extend(_find_ast_phantom_flags(text, py_file, declared))
        for candidate in candidates:
            if not any(
                existing["name"] == candidate["name"] and existing["file"] == candidate["file"] for existing in phantom
            ):
                phantom.append(candidate)
    return phantom


def check_dead_flags(repo_root: Path) -> dict[str, Any]:
    """Main check: find dead flags and phantom flags."""
    declared = _get_declared_fields(repo_root)
    py_files = _collect_py_files(repo_root)

    field_results: list[dict[str, Any]] = []
    dead_count = 0
    for name in declared:
        refs = _count_field_usage(name, py_files)
        is_dead = len(refs) == 0
        if is_dead:
            dead_count += 1
        field_results.append(
            {
                "name": name,
                "usage_count": len(refs),
                "is_deprecated": False,
                "is_dead": is_dead,
                "refs": refs[:5],  # Cap at 5 for brevity
            }
        )

    phantom = _find_phantom_getattr_flags(py_files, set(declared))

    return {
        "declared_fields": field_results,
        "dead_count": dead_count,
        "phantom_flags": phantom,
        "phantom_count": len(phantom),
    }


def main(argv: list[str] | None = None) -> int:
    force_utf8_stdio()
    parser = add_output_arg(
        add_repo_root_arg(
            argparse.ArgumentParser(
                prog="check_dead_flags",
                description="Detect dead FeatureFlags fields and phantom getattr flags.",
            )
        )
    )
    args = parser.parse_args(argv)
    repo_root = resolve_repo_root(args)

    result = check_dead_flags(repo_root)

    if args.output == "json":
        json.dump(result, sys.stdout, indent=2)
        print()
    else:
        for f in result["declared_fields"]:
            status = "DEAD" if f["is_dead"] else "ok"
            print(f"  {f['name']}: {f['usage_count']} refs [{status}]")
        if result["phantom_flags"]:
            print("\nPhantom getattr flags (accessed but not declared):")
            for p in result["phantom_flags"]:
                print(f"  {p['name']} (in {p['file']}:{p['line']})")
        if result["dead_count"] == 0 and result["phantom_count"] == 0:
            print("\nAll active FeatureFlags fields have production consumers. No phantom flags.")

    return 1 if result["dead_count"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
