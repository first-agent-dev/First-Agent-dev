"""C2 test for protected-path governance parity — Task 1.

Proves CODEOWNERS and check_protected_paths.py list same TCB paths.

- Root: protected-path governance (ADR-11-I7)
- Matrix: C-defaults
- Oracle: set equality of TCB paths
- Kill-check: adding a new TCB path to one file but not the other fails test
- Pyramid: A, C2
"""

from __future__ import annotations

import ast
from fnmatch import fnmatchcase
from pathlib import Path


def _parse_codeowners_patterns(codeowners_path: Path) -> set[str]:
    """Return every normalized path pattern from CODEOWNERS."""

    patterns: set[str] = set()
    for raw_line in codeowners_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            patterns.add(line.split()[0].lstrip("/"))
    return patterns


def _parse_check_protected_paths_tcb(script_path: Path) -> tuple[set[str], set[str]]:
    """Return literal `_TCB_PATHS` and `_TCB_PREFIXES` without importing TCB code."""

    tree = ast.parse(script_path.read_text(encoding="utf-8"))
    values: dict[str, set[str]] = {"_TCB_PATHS": set(), "_TCB_PREFIXES": set()}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            names = {target.id for target in node.targets if isinstance(target, ast.Name)}
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            names = {node.target.id}
            value = node.value
        else:
            continue
        for name in names & values.keys():
            values[name].update(
                child.value.lstrip("/")
                for child in ast.walk(value)
                if isinstance(child, ast.Constant) and isinstance(child.value, str)
            )
    return values["_TCB_PATHS"], values["_TCB_PREFIXES"]


def _codeowners_covers(path: str, pattern: str) -> bool:
    if pattern.endswith("/"):
        return path.startswith(pattern)
    return fnmatchcase(path, pattern)


def test_codeowners_and_check_protected_paths_same_tcb() -> None:
    """C2: current repository files have identical semantic TCB coverage in both authorities.

    Kill-check: remove ``scripts/run_slice_mutmut.py`` from either CODEOWNERS or
    ``_TCB_PATHS`` and the symmetric coverage assertion fails.
    """

    root = Path(__file__).resolve().parents[1]
    patterns = _parse_codeowners_patterns(root / ".github" / "CODEOWNERS")
    exact, prefixes = _parse_check_protected_paths_tcb(root / "scripts" / "check_protected_paths.py")
    repository_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.parts and ".venv" not in path.parts
    }
    script_covered = exact | {path for path in repository_files if any(path.startswith(prefix) for prefix in prefixes)}
    codeowners_covered = {
        path for path in repository_files | exact if any(_codeowners_covers(path, pattern) for pattern in patterns)
    }

    assert exact
    assert prefixes
    assert patterns
    missing_in_codeowners = script_covered - codeowners_covered
    missing_in_script = codeowners_covered - script_covered
    assert not missing_in_codeowners, f"protected paths missing CODEOWNERS coverage: {sorted(missing_in_codeowners)}"
    assert not missing_in_script, f"CODEOWNERS TCB paths missing script coverage: {sorted(missing_in_script)}"


def test_authoring_guardrails_workflow_no_paths_filter() -> None:
    """C2: authoring-guardrails.yml must have no paths: filter (always-run per ADR-11-I6)."""
    workflow_path = Path(".github/workflows/authoring-guardrails.yml")
    assert workflow_path.exists(), "authoring-guardrails workflow must exist"

    lines = workflow_path.read_text(encoding="utf-8").splitlines()
    # Look for YAML key "paths:" that is not inside a comment
    # A real paths filter would be a line with optional indent + "paths:" at start (not preceded by #)
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue  # comment, ignore
        if stripped.startswith("paths:"):
            raise AssertionError(
                "authoring-guardrails.yml must not contain paths: filter per ADR-11-I6 "
                "(always-run, no path skip). Found YAML key 'paths:' in workflow line: "
                f"{line!r}"
            )
