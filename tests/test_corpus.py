"""Catch-corpus + fp-corpus regression harness (ADR-11 §Verification).

Each catch fixture is the smallest file reproducing a historical
omission (F-N) or an ADR-11-I5 HARD-BLOCK item; the test materialises
the fixture into a synthetic workspace under tmp_path (NOT under the
real corpus prefix — `iter_python_files` skips those) and asserts the
expected diagnostic code fires. fp fixtures assert the opposite:
patterns that look similar but are legitimate must NOT fire.

PR-12 seeds the structure with one fixture per V-code claimed in
PR-10. PR-4 (per ADR-11 Appendix B) expands to the full F-1..F-10
catch-corpus baseline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.authoring_rules import (
    EXPORTS_COMPLETENESS,
    PLACEHOLDER_ASSERTION,
    TEST_SEMANTIC_DECAY,
)
from fa.authoring_tcb import run_all

_REPO_ROOT = Path(__file__).resolve().parent.parent

# (fixture relative path, destination under tmp_path, target rule, expected code)
_CATCH_CASES = [
    ("catch-corpus/F-2/fixture.py",       "src/fa_demo/f2.py",        EXPORTS_COMPLETENESS, "FA-AUTHORING-V2-EXPORTS-COMPLETENESS"),
    ("catch-corpus/F-7/fixture.py",       "src/fa_demo/f7.py",        EXPORTS_COMPLETENESS, "FA-AUTHORING-V2-EXPORTS-COMPLETENESS"),
    ("catch-corpus/F-9/fixture.py",       "tests/test_f9.py",         PLACEHOLDER_ASSERTION, "FA-AUTHORING-V11-PLACEHOLDER-ASSERT"),
    ("catch-corpus/I-5-skip/fixture.py",  "tests/test_i5_skip.py",    TEST_SEMANTIC_DECAY,   "FA-AUTHORING-V4-PYTEST-SKIP"),
    ("catch-corpus/I-5-xfail/fixture.py", "tests/test_i5_xfail.py",   TEST_SEMANTIC_DECAY,   "FA-AUTHORING-V4-NON-STRICT-XFAIL"),
    ("catch-corpus/I-5-focus/fixture.py", "tests/test_i5_focus.py",   TEST_SEMANTIC_DECAY,   "FA-AUTHORING-V4-FOCUS-MARKER"),
]

_FP_CASES = [
    ("fp-corpus/skipif/fixture.py",        "tests/test_skipif.py",      TEST_SEMANTIC_DECAY),
    ("fp-corpus/pure-compare/fixture.py",  "tests/test_pure.py",        PLACEHOLDER_ASSERTION),
    ("fp-corpus/strict-xfail/fixture.py",  "tests/test_strict_xfail.py", TEST_SEMANTIC_DECAY),
]


def _make_workspace(root: Path) -> None:
    (root / "knowledge").mkdir(parents=True, exist_ok=True)
    (root / "knowledge" / "llms.txt").write_text("# routing\n", encoding="utf-8")
    (root / "README.md").write_text("# sample\n", encoding="utf-8")


def _install_fixture(tmp_path: Path, fixture_rel: str, dest_rel: str) -> None:
    body = (_REPO_ROOT / fixture_rel).read_text(encoding="utf-8")
    dest = tmp_path / dest_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(body, encoding="utf-8")


@pytest.mark.parametrize(
    ("fixture_rel", "dest_rel", "rule", "expected_code"),
    _CATCH_CASES,
    ids=[c[0] for c in _CATCH_CASES],
)
def test_catch_corpus_fixture_fires_expected_code(
    tmp_path: Path, fixture_rel: str, dest_rel: str, rule, expected_code: str
) -> None:
    _make_workspace(tmp_path)
    _install_fixture(tmp_path, fixture_rel, dest_rel)
    report = run_all(tmp_path, rules=(rule,))
    codes = [d.code for d in report.diagnostics]
    assert expected_code in codes, (
        f"catch fixture {fixture_rel} did not fire {expected_code}; got {codes}"
    )


@pytest.mark.parametrize(
    ("fixture_rel", "dest_rel", "rule"),
    _FP_CASES,
    ids=[c[0] for c in _FP_CASES],
)
def test_fp_corpus_fixture_does_not_fire(
    tmp_path: Path, fixture_rel: str, dest_rel: str, rule
) -> None:
    _make_workspace(tmp_path)
    _install_fixture(tmp_path, fixture_rel, dest_rel)
    report = run_all(tmp_path, rules=(rule,))
    assert report.diagnostics == (), (
        f"fp fixture {fixture_rel} should not fire any rule; got {report.diagnostics}"
    )
