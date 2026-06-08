"""Pin the KernelReport JSON wire shape (additive-only contract).

The schema lives in tests/_authoring_report.schema.json. The kernel
itself is stdlib-only (ADR-11-I1) and does NOT self-validate; this
test enforces the contract at test time using fastjsonschema (already
a project dependency for ToolRegistry params validation).
"""

from __future__ import annotations

import json
from pathlib import Path

import fastjsonschema

from fa.authoring_rules import RULE_ALLOWLIST
from fa.authoring_tcb import run_all

_SCHEMA_PATH = Path(__file__).resolve().parent / "_authoring_report.schema.json"


def _validator():
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return fastjsonschema.compile(schema)


def test_clean_tree_report_matches_schema(tmp_path: Path) -> None:
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "llms.txt").write_text("x")
    (tmp_path / "README.md").write_text("y")
    report = run_all(tmp_path, rules=RULE_ALLOWLIST)
    validate = _validator()
    validate(report.to_dict())  # raises JsonSchemaException on shape drift


def test_diagnostic_report_matches_schema(tmp_path: Path) -> None:
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "llms.txt").write_text("x")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_skip.py").write_text(
        "import pytest\n\ndef test_x():\n    pytest.skip('x')\n"
    )
    report = run_all(tmp_path, rules=RULE_ALLOWLIST)
    assert report.diagnostics, "fixture should produce at least one diagnostic"
    validate = _validator()
    validate(report.to_dict())
