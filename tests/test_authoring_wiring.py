"""C2 CLI smoke + composition-root wiring for authoring guardrails — Task 1 HR1.

Proves Level-0 kernel + Level-1 RULE_ALLOWLIST wiring is not theater.

- Root: fa.authoring_rules.RULE_ALLOWLIST + fa.authoring_tcb.run_all (used by fa authoring-check)
- Matrix: C-defaults (clean tree + F-2 fixture)
- Oracle: diagnostic code FA-AUTHORING-V2-EXPORTS-COMPLETENESS, severity HARD-BLOCK, exit_code 1
- Kill-check: removing EXPORTS_COMPLETENESS from RULE_ALLOWLIST must make the test fail.
- Pyramid: A, C2 (CLI authoring-check is the claim root).

Skill: tests-writing, ADR-11-I9

Live-path proof:
- root: cli:authoring-check via run_all(..., rules=RULE_ALLOWLIST)
- test: tests/test_authoring_wiring.py::test_authoring_check_catches_f2_via_default_allowlist
- matrix: C-defaults
- oracle: event:diagnostic code FA-AUTHORING-V2-EXPORTS-COMPLETENESS
- kill-check: removing EXPORTS_COMPLETENESS from RULE_ALLOWLIST fails test
- pyramid: A, C2
"""

from __future__ import annotations

from pathlib import Path

from fa.authoring_rules import EXPORTS_COMPLETENESS, RULE_ALLOWLIST
from fa.authoring_tcb import run_all

_REPO_ROOT = Path(__file__).resolve().parent.parent
_F2_FIXTURE = _REPO_ROOT / "catch-corpus" / "F-2" / "fixture.py"


def _make_workspace_with_f2(tmp_path: Path) -> None:
    """Create minimal workspace that satisfies authoring kernel pre-requisites + F-2 violation."""
    (tmp_path / "knowledge").mkdir(parents=True, exist_ok=True)
    (tmp_path / "knowledge" / "llms.txt").write_text("# routing\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# sample\n", encoding="utf-8")
    # Install F-2 fixture under src/fa_demo/f2.py — not under corpus prefix, so _scan will pick it
    dest = tmp_path / "src" / "fa_demo" / "f2.py"
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = _F2_FIXTURE.read_text(encoding="utf-8")
    dest.write_text(body, encoding="utf-8")


def test_authoring_check_catches_f2_via_default_allowlist(tmp_path: Path) -> None:
    """C2: fa authoring-check via default allowlist must catch F-2 fixture.

    This proves RULE_ALLOWLIST wiring: the production allowlist contains EXPORTS_COMPLETENESS,
    so a clean tree with F-2 fixture yields HARD-BLOCK diagnostic.
    """
    _make_workspace_with_f2(tmp_path)
    report = run_all(tmp_path, rules=RULE_ALLOWLIST)

    # Oracle: at least one diagnostic with expected code
    codes = [d.code for d in report.diagnostics]
    assert "FA-AUTHORING-V2-EXPORTS-COMPLETENESS" in codes, f"Expected V2 code in {codes}"

    # Severity and exit_code
    assert report.exit_code == 1
    # Deterministic sort: first diagnostic should be HARD-BLOCK
    assert report.diagnostics[0].severity.label == "HARD-BLOCK"


def test_authoring_allowlist_kill_check(tmp_path: Path) -> None:
    """C2 kill-check: removing EXPORTS_COMPLETENESS from allowlist must make F-2 invisible.

    If production removes the rule from RULE_ALLOWLIST, authoring-check would stop catching F-2.
    This test proves that our first test would fail if the call site were removed.
    """
    _make_workspace_with_f2(tmp_path)

    # Build allowlist without EXPORTS_COMPLETENESS
    allowlist_without_exports = tuple(r for r in RULE_ALLOWLIST if r is not EXPORTS_COMPLETENESS)

    # Sanity: allowlist_without_exports should be smaller
    assert len(allowlist_without_exports) == len(RULE_ALLOWLIST) - 1

    report_without = run_all(tmp_path, rules=allowlist_without_exports)
    codes_without = [d.code for d in report_without.diagnostics]

    # With rule removed, V2 code must NOT appear
    assert "FA-AUTHORING-V2-EXPORTS-COMPLETENESS" not in codes_without, (
        "Kill-check failed: diagnostic still present even after removing EXPORTS_COMPLETENESS from allowlist. "
        "This would mean test_authoring_check_catches_f2_via_default_allowlist does NOT prove allowlist wiring."
    )

    # And with full allowlist it does appear (redundant check for clarity)
    report_with = run_all(tmp_path, rules=RULE_ALLOWLIST)
    codes_with = [d.code for d in report_with.diagnostics]
    assert "FA-AUTHORING-V2-EXPORTS-COMPLETENESS" in codes_with


def test_authoring_check_clean_tree_no_hard_block(tmp_path: Path) -> None:
    """C2: clean tree with default allowlist must have 0 diagnostics (0 exit code)."""
    (tmp_path / "knowledge").mkdir(parents=True, exist_ok=True)
    (tmp_path / "knowledge" / "llms.txt").write_text("# routing\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# sample\n", encoding="utf-8")
    # Add a clean file under src/
    clean = tmp_path / "src" / "fa_demo" / "clean.py"
    clean.parent.mkdir(parents=True, exist_ok=True)
    clean.write_text('"""Clean module."""\n__all__ = ["foo"]\nfoo = 1\n', encoding="utf-8")

    report = run_all(tmp_path, rules=RULE_ALLOWLIST)
    assert report.exit_code == 0
    assert len(report.diagnostics) == 0
