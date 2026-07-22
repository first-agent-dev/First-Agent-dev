"""C2 test for protected-path governance parity — Task 1.

Proves CODEOWNERS and check_protected_paths.py list same TCB paths.

- Root: protected-path governance (ADR-11-I7)
- Matrix: C-defaults
- Oracle: set equality of TCB paths
- Kill-check: adding a new TCB path to one file but not the other fails test
- Pyramid: A, C2
"""

from __future__ import annotations

import re
from pathlib import Path


def _parse_codeowners_tcb_paths(codeowners_path: Path) -> set[str]:
    """Extract TCB paths from .github/CODEOWNERS.

    CODEOWNERS lines are like: /src/fa/authoring_tcb.py @MondayInRussian
    We extract the first token that starts with /.
    """
    paths: set[str] = set()
    for line in codeowners_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # First token is path pattern
        parts = line.split()
        if not parts:
            continue
        pattern = parts[0]
        # Only keep authoring-related TCB paths, not all CODEOWNERS
        if any(
            marker in pattern
            for marker in (
                "authoring",
                "CODEOWNERS",
                "check_protected_paths",
                "authoring-guardrails",
                "dependency_contract",
            )
        ):
            # Normalize: remove leading / and keep as repo-relative
            norm = pattern.lstrip("/")
            paths.add(norm)
    return paths


def _parse_check_protected_paths_tcb() -> set[str]:
    """Extract _TCB_PATHS from scripts/check_protected_paths.py.

    The script defines _TCB_PATHS as a set/frozenset/tuple of paths.
    We parse via regex + ast for determinism, not import (to avoid side effects).
    """
    import ast

    script_path = Path("scripts/check_protected_paths.py")
    if not script_path.exists():
        return set()

    source = script_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    tcb_paths: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_TCB_PATHS":
                    # Value should be set/list/tuple
                    try:
                        # Try to get source segment for the value
                        seg = ast.get_source_segment(source, node.value)
                        if seg:
                            # Extract quoted strings
                            for m in re.finditer(r'"([^"]+)"|\'([^\']+)\'', seg):
                                path = m.group(1) or m.group(2)
                                if path:
                                    # Normalize: lstrip / and keep
                                    tcb_paths.add(path.lstrip("/"))
                    except (TypeError, ValueError, re.error):
                        continue
    return tcb_paths


def test_codeowners_and_check_protected_paths_same_tcb() -> None:
    """C2: CODEOWNERS and check_protected_paths.py must list same TCB paths.

    This is part of the governance bundle per ADR-11-I7. If they diverge,
    protected-path edits might not be flagged for human review.

    Kill-check: adding a new TCB file to one but not the other makes test fail.
    """
    codeowners_path = Path(".github/CODEOWNERS")
    assert codeowners_path.exists(), ".github/CODEOWNERS must exist for protected-path governance"

    codeowners_tcb = _parse_codeowners_tcb_paths(codeowners_path)
    script_tcb = _parse_check_protected_paths_tcb()

    # Both should be non-empty
    assert len(codeowners_tcb) >= 3, f"CODEOWNERS TCB set too small: {codeowners_tcb}"
    assert len(script_tcb) >= 3, f"check_protected_paths _TCB_PATHS too small: {script_tcb}"

    # CODEOWNERS may list a directory covering a file.
    # So we check that every path in script_tcb is covered by some CODEOWNERS pattern (exact or prefix)
    def is_covered(path: str, patterns: set[str]) -> bool:
        # Exact match
        if path in patterns:
            return True
        # Directory prefix match: pattern ends with / and path starts with pattern
        for pat in patterns:
            if pat.endswith("/") and path.startswith(pat):
                return True
        return False

    missing_in_codeowners = {p for p in script_tcb if not is_covered(p, codeowners_tcb)}
    assert not missing_in_codeowners, (
        f"_TCB_PATHS contains paths not covered by CODEOWNERS: {missing_in_codeowners}. "
        f"CODEOWNERS={codeowners_tcb}, script={script_tcb}. "
        f"Keep them in sync per ADR-11-I7 and README in authoring_rules."
    )

    # For reverse, we check that every CODEOWNERS authoring path is covered by script_tcb (exact or prefix)
    # Since CODEOWNERS may have directory pattern, and script may have file, we need reverse check too
    # For simplicity, each file pattern must be in script_tcb or under a script directory.
    # script_tcb contains files, so each CODEOWNERS file pattern must be present.
    # If CODEOWNERS pattern is directory, it should have at least one file in script_tcb under it
    missing_in_script = set()
    for pat in codeowners_tcb:
        if pat.endswith("/"):
            # directory pattern: check if any script_tcb path starts with it
            if not any(p.startswith(pat) for p in script_tcb):
                missing_in_script.add(pat)
        else:
            if pat not in script_tcb:
                # Script lists files, so this check intentionally requires an exact match.
                missing_in_script.add(pat)

    assert not missing_in_script, (
        f"CODEOWNERS contains authoring TCB paths not covered by _TCB_PATHS: {missing_in_script}. Keep them in sync."
    )


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
