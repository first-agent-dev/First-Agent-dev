"""C2 wiring tests for the dependency-contract quality gate."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_dependency_contract_recipe_is_authoritative_check_member() -> None:
    """The tracked dependency contract must run from the blocking check chain."""
    justfile = (ROOT / "justfile").read_text(encoding="utf-8")
    assert "dependency-contract-check:" in justfile
    assert "python scripts/check_dependency_contract.py" in justfile
    check_line = next(line for line in justfile.splitlines() if line.startswith("check:"))
    assert "dependency-contract-check" in check_line


def test_optional_runtime_extra_declares_deferred_import_distributions() -> None:
    """Direct deferred imports map to explicit optional distributions."""
    import tomllib

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    runtime = set(pyproject["project"]["optional-dependencies"]["runtime"])
    names = {item.split(">=")[0].split("==")[0].strip().lower() for item in runtime}
    assert {"pymupdf", "pdfminer.six", "pypdf", "fastapi", "pydantic", "requests"} <= names


def test_dependency_contract_script_and_artifact_are_tracked_surfaces() -> None:
    """The gate cannot depend on an ignored/generated-only contract artifact."""
    contract = ROOT / ".fa" / "dependency_contract.toml"
    script = ROOT / "scripts" / "check_dependency_contract.py"
    assert contract.is_file()
    assert script.is_file()
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "!.fa/dependency_contract.toml" in gitignore
