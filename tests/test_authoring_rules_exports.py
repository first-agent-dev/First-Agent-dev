"""Tests for V2 (__all__ completeness) Level-1 rule.

Fixture pattern: each test materialises a minimal repo skeleton under
``tmp_path`` (knowledge/llms.txt + a target src/ file), runs the
authoring kernel through :func:`run_all`, and asserts the diagnostic
shape. Inline string fixtures keep ``catch-corpus/`` out of this PR
(per ADR-11 §"active consumer" — corpus dir lands when its consumer
in PR 4 lands).
"""

from __future__ import annotations

from pathlib import Path

from fa.authoring_rules import EXPORTS_COMPLETENESS
from fa.authoring_tcb import RuleContext, run_all


def _make_workspace(root: Path) -> Path:
    (root / "knowledge").mkdir(parents=True)
    (root / "knowledge" / "llms.txt").write_text("# routing\n", encoding="utf-8")
    (root / "README.md").write_text("# sample\n", encoding="utf-8")
    return root


def _write_src(root: Path, rel: str, body: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")


# --- happy path -----------------------------------------------------------


def test_module_without_dunder_all_is_ignored(tmp_path: Path) -> None:
    """V2 is opt-in: modules that never declare ``__all__`` are not inspected."""
    _make_workspace(tmp_path)
    _write_src(
        tmp_path,
        "src/fa_demo/uncurated.py",
        "def public_name():\n    pass\n\ndef _private():\n    pass\n",
    )
    report = run_all(tmp_path, rules=(EXPORTS_COMPLETENESS,))
    assert report.diagnostics == ()


def test_module_with_complete_dunder_all_is_clean(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = (
        '"""m."""\nfrom __future__ import annotations\n\n'
        '__all__ = ["alpha", "Beta"]\n\n'
        "def alpha():\n    pass\n\n"
        "class Beta:\n    pass\n"
    )
    _write_src(tmp_path, "src/fa_demo/complete.py", body)
    report = run_all(tmp_path, rules=(EXPORTS_COMPLETENESS,))
    assert report.diagnostics == ()


def test_future_annotations_import_is_not_a_re_export(tmp_path: Path) -> None:
    """Regression: ``from __future__ import annotations`` must NOT count.

    Counting unaliased imports as re-exports produced 52 false positives
    on the live repo during the PR-2 self-review.
    """
    _make_workspace(tmp_path)
    body = (
        "from __future__ import annotations\nimport re\nfrom pathlib import Path\n\n"
        '__all__ = ["work"]\n\n'
        'def work(p: Path) -> str:\n    return re.sub(r"x", "y", str(p))\n'
    )
    _write_src(tmp_path, "src/fa_demo/imports.py", body)
    report = run_all(tmp_path, rules=(EXPORTS_COMPLETENESS,))
    assert report.diagnostics == ()


def test_conventional_logger_name_is_not_flagged(tmp_path: Path) -> None:
    """Module-level ``LOGGER = logging.getLogger(...)`` is universal idiom
    and must never be flagged as a missing export."""
    _make_workspace(tmp_path)
    body = (
        "from __future__ import annotations\nimport logging\n\n"
        '__all__ = ["work"]\n\n'
        "LOGGER = logging.getLogger(__name__)\n\n"
        "def work() -> None:\n    LOGGER.info('hi')\n"
    )
    _write_src(tmp_path, "src/fa_demo/with_logger.py", body)
    report = run_all(tmp_path, rules=(EXPORTS_COMPLETENESS,))
    assert report.diagnostics == ()


def test_explicit_redundant_alias_counts_as_re_export(tmp_path: Path) -> None:
    """PEP 8 redundant-alias idiom ``from .x import foo as foo`` is the
    only AST-detectable opt-in for re-exports, and must be recognised."""
    _make_workspace(tmp_path)
    _write_src(
        tmp_path,
        "src/fa_demo/sub.py",
        "from __future__ import annotations\n\ndef helper() -> None:\n    pass\n",
    )
    body = (
        "from __future__ import annotations\n"
        "from fa_demo.sub import helper as helper\n\n"
        '__all__ = ["helper"]\n'
    )
    _write_src(tmp_path, "src/fa_demo/facade.py", body)
    report = run_all(tmp_path, rules=(EXPORTS_COMPLETENESS,))
    assert report.diagnostics == ()


# --- detection -----------------------------------------------------------


def test_missing_public_function_is_flagged(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = (
        "from __future__ import annotations\n\n"
        '__all__ = ["kept"]\n\n'
        "def kept():\n    pass\n\n"
        "def forgotten():\n    pass\n"
    )
    _write_src(tmp_path, "src/fa_demo/missing_fn.py", body)
    report = run_all(tmp_path, rules=(EXPORTS_COMPLETENESS,))
    assert len(report.diagnostics) == 1
    diag = report.diagnostics[0]
    assert diag.code == "FA-AUTHORING-V2-EXPORTS-COMPLETENESS"
    assert diag.severity.label == "HARD-BLOCK"
    assert diag.path == "src/fa_demo/missing_fn.py"
    assert diag.line is not None and diag.line >= 6
    assert "forgotten" in diag.message
    assert diag.rule_input_hash.startswith("sha256:")


def test_missing_public_class_is_flagged(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = (
        "from __future__ import annotations\n\n"
        '__all__ = ["Kept"]\n\n'
        "class Kept:\n    pass\n\n"
        "class Forgotten:\n    pass\n"
    )
    _write_src(tmp_path, "src/fa_demo/missing_cls.py", body)
    report = run_all(tmp_path, rules=(EXPORTS_COMPLETENESS,))
    codes = [d.code for d in report.diagnostics]
    assert codes == ["FA-AUTHORING-V2-EXPORTS-COMPLETENESS"]
    assert "Forgotten" in report.diagnostics[0].message


def test_underscore_prefixed_symbol_is_ignored(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = (
        "from __future__ import annotations\n\n"
        '__all__ = ["public"]\n\n'
        "def public():\n    pass\n\n"
        "def _private_helper():\n    pass\n"
    )
    _write_src(tmp_path, "src/fa_demo/private.py", body)
    report = run_all(tmp_path, rules=(EXPORTS_COMPLETENESS,))
    assert report.diagnostics == ()


def test_class_methods_do_not_count_as_top_level(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = (
        "from __future__ import annotations\n\n"
        '__all__ = ["Container"]\n\n'
        "class Container:\n"
        "    def public_method(self):\n        pass\n"
        "    def another(self):\n        pass\n"
    )
    _write_src(tmp_path, "src/fa_demo/cls.py", body)
    report = run_all(tmp_path, rules=(EXPORTS_COMPLETENESS,))
    assert report.diagnostics == ()


# --- scope ---------------------------------------------------------------


def test_test_tree_files_are_ignored(tmp_path: Path) -> None:
    """V2 scopes to src/ only — test modules' __all__ is uninteresting."""
    _make_workspace(tmp_path)
    body = (
        "from __future__ import annotations\n\n"
        '__all__ = ["kept"]\n\n'
        "def kept():\n    pass\n\n"
        "def forgotten():\n    pass\n"
    )
    _write_src(tmp_path, "tests/test_demo.py", body)
    report = run_all(tmp_path, rules=(EXPORTS_COMPLETENESS,))
    assert report.diagnostics == ()


def test_catch_corpus_is_excluded(tmp_path: Path) -> None:
    """Fixtures intentionally violating the rule (when corpus dir exists)
    must not trip the rule during the regular kernel run."""
    _make_workspace(tmp_path)
    body = (
        "from __future__ import annotations\n\n"
        '__all__ = ["kept"]\n\n'
        "def kept():\n    pass\n\ndef forgotten():\n    pass\n"
    )
    _write_src(tmp_path, "catch-corpus/F-2/fixture.py", body)
    # Even though the corpus dir would be enumerated, V2 must skip it.
    report = run_all(tmp_path, rules=(EXPORTS_COMPLETENESS,))
    assert report.diagnostics == ()


# --- rule context shape --------------------------------------------------


def test_rule_returns_sequence_of_rule_results(tmp_path: Path) -> None:
    """Direct rule-call test: bypasses run_all to pin the Rule protocol shape."""
    _make_workspace(tmp_path)
    body = "from __future__ import annotations\n\n__all__ = []\n\ndef public():\n    pass\n"
    _write_src(tmp_path, "src/fa_demo/direct.py", body)
    ctx = RuleContext(
        repo_root=tmp_path.resolve(),
        files=("src/fa_demo/direct.py",),
        manifest=None,
    )
    results = EXPORTS_COMPLETENESS(ctx)
    assert len(results) == 1
    assert results[0].code == "FA-AUTHORING-V2-EXPORTS-COMPLETENESS"
