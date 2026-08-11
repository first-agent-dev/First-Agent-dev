"""C2 wiring tests for the dependency-contract quality gate."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _recipe_body(justfile_text: str, recipe_name: str) -> str:
    """Return the body of *recipe_name* from *justfile_text* (lines up to next recipe or EOF)."""
    lines = justfile_text.splitlines()
    in_recipe = False
    body: list[str] = []
    for line in lines:
        if line.startswith(f"{recipe_name}:"):
            in_recipe = True
            continue
        if in_recipe:
            # Recipe ends at the next non-comment, non-indented, non-blank line
            # that looks like a new recipe header (matches `name:` at column 0).
            stripped = line.rstrip()
            if stripped and not stripped.startswith((" ", "#")) and ":" in stripped and not stripped.startswith("\t"):
                # Possible new recipe header (e.g. "foo:" or "_foo:").
                break
            body.append(line)
    return "\n".join(body)


def test_dependency_contract_recipe_is_authoritative_check_member() -> None:
    """The tracked dependency contract must run from the blocking check chain.

    After the 6-public-recipe consolidation (S14b.2), individual contract
    scripts are bundled under the `_contracts` private recipe rather than
    exposed as flat public recipes. Assert that `check:` invokes `_contracts`
    and that `_contracts` in turn invokes this checker.
    """
    justfile = (ROOT / "justfile").read_text(encoding="utf-8")
    assert "check_dependency_contract.py" in justfile
    check_body = _recipe_body(justfile, "check")
    assert check_body, "`check` recipe not found or empty"
    assert "_contracts" in check_body, f"check must invoke the contracts bundle:\n{check_body}"
    contracts_body = _recipe_body(justfile, "_contracts")
    assert "check_dependency_contract.py" in contracts_body, (
        f"_contracts bundle must invoke check_dependency_contract.py:\n{contracts_body}"
    )


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
