#!/usr/bin/env python3
"""Dependency Contract Check for FA supply-chain (G12, ADR-11-I7).

Verifies that all dependencies in pyproject.toml are accounted for in
.fa/dependency_contract.toml. Unknown packages are HARD-BLOCK (exit 1).
Missing packages from the contract are advisory (exit 0 with warning).

Run as: python scripts/check_dependency_contract.py
Exit 1 if contract violations found. Exit 0 if satisfied.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any

# UTF-8 console: this script prints non-ASCII (checkmarks / box drawing) and
# crashed with UnicodeEncodeError on a Windows host whose console was cp1251 —
# while REPORTING SUCCESS. See scripts/_console.py for the full rationale.
if __package__ in (None, ""):  # invoked as a file, not as scripts.<name>
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._console import force_utf8_stdio

force_utf8_stdio()

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = REPO_ROOT / ".fa" / "dependency_contract.toml"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


def _parse_toml_simple(path: Path) -> dict[str, Any]:
    """Parse a simple TOML file using stdlib tomllib (ADR-11-I1 compliant)."""
    with path.open("rb") as f:
        return tomllib.load(f)


def extract_contract_packages(contract: dict[str, Any]) -> set[str]:
    """Extract all package names from the dependency contract."""
    packages: set[str] = set()
    for section_key in (
        "packages.core",
        "packages.security_critical",
        "packages.dev",
        "packages.optional.runtime",
    ):
        # Handle nested keys
        parts = section_key.split(".")
        section = contract
        for part in parts:
            section = section.get(part, {})
        packages.update(section.keys())
    return packages


def extract_pyproject_deps(pyproject: dict[str, Any]) -> set[str]:
    """Extract package names from pyproject.toml [project.dependencies]."""
    deps = pyproject.get("project", {}).get("dependencies", [])
    names = set()
    for dep in deps:
        # Extract name from "package>=1.0" or "package==1.0" etc.
        name = ""
        for char in dep:
            if char in ">=<!=~[ ;@":
                break
            name += char
        if name:
            names.add(name.lower().replace("-", "_"))
    return names


def normalize_name(name: str) -> str:
    """Normalize package name for comparison (PEP 503)."""
    return name.lower().replace("-", "_").replace(".", "_")


def main() -> None:
    print("DEPENDENCY CONTRACT CHECK")
    print("=" * 72)

    if not CONTRACT_PATH.exists():
        print(f"FAIL: Contract file not found: {CONTRACT_PATH}")
        sys.exit(1)

    if not PYPROJECT_PATH.exists():
        print(f"FAIL: pyproject.toml not found: {PYPROJECT_PATH}")
        sys.exit(1)

    contract = _parse_toml_simple(CONTRACT_PATH)
    pyproject = _parse_toml_simple(PYPROJECT_PATH)

    contract_packages = {normalize_name(p) for p in extract_contract_packages(contract)}
    pyproject_packages = extract_pyproject_deps(pyproject)

    print(f"Contract packages: {len(contract_packages)}")
    print(f"pyproject.toml deps: {len(pyproject_packages)}")
    print()

    failures = 0

    # CHECK 1: Every pyproject dep must be in contract
    print("CHECK 1: pyproject.toml deps are in contract")
    print("-" * 72)
    unknown = pyproject_packages - contract_packages
    if unknown:
        for pkg in sorted(unknown):
            print(f"  ❌ {pkg!r} — in pyproject.toml but NOT in dependency_contract.toml")
        failures += 1
    else:
        print("  ✅ All pyproject.toml deps are in the contract")

    # CHECK 2: Security-critical packages are in pyproject.toml
    print()
    print("CHECK 2: Security-critical contract packages exist in pyproject.toml")
    print("-" * 72)
    security = {normalize_name(p) for p in contract.get("packages", {}).get("security_critical", {})}
    missing_security = security - pyproject_packages
    if missing_security:
        for pkg in sorted(missing_security):
            print(f"  ❌ {pkg!r} — in security_critical contract but NOT in pyproject.toml")
        failures += 1
    else:
        print("  ✅ All security-critical packages are in pyproject.toml")

    # CHECK 3: No unknown keys in contract
    print()
    print("CHECK 3: Contract structure is valid")
    print("-" * 72)
    allowed_top = {"kernel", "packages", "registries"}
    unknown_keys = set(contract.keys()) - allowed_top
    if unknown_keys:
        for key in sorted(unknown_keys):
            print(f"  ❌ Unknown top-level key: {key!r}")
        failures += 1
    else:
        print("  ✅ Contract structure is valid")

    # Summary
    print()
    print("=" * 72)
    if failures:
        print(f"FAIL: {failures} contract violation(s) found")
        sys.exit(1)
    else:
        print("PASS: Dependency contract satisfied")
        sys.exit(0)


if __name__ == "__main__":
    main()
