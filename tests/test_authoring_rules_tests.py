"""Tests for V4 (test semantic decay) + V11 (placeholder assertion) rules.

Fixture pattern: each test materialises a minimal repo under
``tmp_path`` with one tests/-prefixed Python file containing the
target pattern, runs the kernel, and asserts the diagnostic shape.
Inline string fixtures keep ``catch-corpus/`` out of this PR.
"""

from __future__ import annotations

from pathlib import Path

from fa.authoring_rules import PLACEHOLDER_ASSERTION, TEST_SEMANTIC_DECAY
from fa.authoring_tcb import run_all


def _make_workspace(root: Path) -> Path:
    (root / "knowledge").mkdir(parents=True)
    (root / "knowledge" / "llms.txt").write_text("# routing\n", encoding="utf-8")
    (root / "README.md").write_text("# sample\n", encoding="utf-8")
    return root


def _write_test(root: Path, rel: str, body: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")


def _codes(report) -> list[str]:  # type: ignore[no-untyped-def]
    return [d.code for d in report.diagnostics]


# =========================================================================
# V4 — pytest.skip / @pytest.mark.skip
# =========================================================================


def test_pytest_skip_call_is_hard_block(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = 'import pytest\n\ndef test_thing():\n    pytest.skip("not implemented yet")\n'
    _write_test(tmp_path, "tests/test_skip_call.py", body)
    report = run_all(tmp_path, rules=(TEST_SEMANTIC_DECAY,))
    assert _codes(report) == ["FA-AUTHORING-V4-PYTEST-SKIP"]
    diag = report.diagnostics[0]
    assert diag.severity.label == "HARD-BLOCK"
    assert diag.line is not None and diag.line >= 4


def test_pytest_mark_skip_decorator_is_hard_block(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = (
        "import pytest\n\n"
        '@pytest.mark.skip(reason="broken")\n'
        "def test_thing():\n    assert 0 == 0  # noqa: V11 — this is the OTHER finding\n"
    )
    # ^ that placeholder pattern would only fire under V11; we don't load V11 here.
    _write_test(tmp_path, "tests/test_skip_dec.py", body)
    report = run_all(tmp_path, rules=(TEST_SEMANTIC_DECAY,))
    assert _codes(report) == ["FA-AUTHORING-V4-PYTEST-SKIP"]


def test_pytest_mark_skipif_is_not_flagged(tmp_path: Path) -> None:
    """Cross-platform skipif is a legitimate pattern; the codebase uses 14
    instances of ``@pytest.mark.skipif(shutil.which("bash") is None, ...)``
    that must not be flagged."""
    _make_workspace(tmp_path)
    body = (
        "import pytest\nimport shutil\n\n"
        '@pytest.mark.skipif(shutil.which("bash") is None, reason="bash")\n'
        "def test_bash_only():\n    pass\n"
    )
    _write_test(tmp_path, "tests/test_skipif.py", body)
    report = run_all(tmp_path, rules=(TEST_SEMANTIC_DECAY,))
    assert report.diagnostics == ()


# =========================================================================
# V4 — xfail strict=True requirement
# =========================================================================


def test_non_strict_xfail_call_form_is_hard_block(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = (
        "import pytest\n\n"
        '@pytest.mark.xfail(reason="known bug")\n'
        "def test_thing():\n    raise AssertionError\n"
    )
    _write_test(tmp_path, "tests/test_xfail_no_strict.py", body)
    report = run_all(tmp_path, rules=(TEST_SEMANTIC_DECAY,))
    assert _codes(report) == ["FA-AUTHORING-V4-NON-STRICT-XFAIL"]


def test_bare_xfail_decorator_is_hard_block(tmp_path: Path) -> None:
    """``@pytest.mark.xfail`` without parens can't carry ``strict=True`` either."""
    _make_workspace(tmp_path)
    body = "import pytest\n\n@pytest.mark.xfail\ndef test_thing():\n    raise AssertionError\n"
    _write_test(tmp_path, "tests/test_xfail_bare.py", body)
    report = run_all(tmp_path, rules=(TEST_SEMANTIC_DECAY,))
    assert _codes(report) == ["FA-AUTHORING-V4-NON-STRICT-XFAIL"]


def test_strict_true_xfail_is_clean(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = (
        "import pytest\n\n"
        '@pytest.mark.xfail(strict=True, reason="known bug")\n'
        "def test_thing():\n    raise AssertionError\n"
    )
    _write_test(tmp_path, "tests/test_xfail_strict.py", body)
    report = run_all(tmp_path, rules=(TEST_SEMANTIC_DECAY,))
    assert report.diagnostics == ()


def test_xfail_strict_false_is_hard_block(tmp_path: Path) -> None:
    """Explicit ``strict=False`` is just as bad as omitting strict."""
    _make_workspace(tmp_path)
    body = (
        "import pytest\n\n"
        '@pytest.mark.xfail(strict=False, reason="known bug")\n'
        "def test_thing():\n    raise AssertionError\n"
    )
    _write_test(tmp_path, "tests/test_xfail_false.py", body)
    report = run_all(tmp_path, rules=(TEST_SEMANTIC_DECAY,))
    assert _codes(report) == ["FA-AUTHORING-V4-NON-STRICT-XFAIL"]


# =========================================================================
# V4 — focus / only markers
# =========================================================================


def test_pytest_mark_focus_is_hard_block(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = "import pytest\n\n@pytest.mark.focus\ndef test_thing():\n    pass\n"
    _write_test(tmp_path, "tests/test_focus.py", body)
    report = run_all(tmp_path, rules=(TEST_SEMANTIC_DECAY,))
    assert _codes(report) == ["FA-AUTHORING-V4-FOCUS-MARKER"]


def test_pytest_mark_only_is_hard_block(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = "import pytest\n\n@pytest.mark.only\ndef test_thing():\n    pass\n"
    _write_test(tmp_path, "tests/test_only.py", body)
    report = run_all(tmp_path, rules=(TEST_SEMANTIC_DECAY,))
    assert _codes(report) == ["FA-AUTHORING-V4-FOCUS-MARKER"]


# =========================================================================
# V4 — scope filtering
# =========================================================================


def test_v4_does_not_scan_src(tmp_path: Path) -> None:
    """V4 is a test-decay rule; src/ files use their own ``except`` patterns."""
    _make_workspace(tmp_path)
    body = 'import pytest\n\n@pytest.mark.skip(reason="x")\ndef helper(): pass\n'
    _write_test(tmp_path, "src/fa_demo/has_skip.py", body)
    report = run_all(tmp_path, rules=(TEST_SEMANTIC_DECAY,))
    assert report.diagnostics == ()


def test_v4_does_not_scan_catch_corpus(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = 'import pytest\n\n@pytest.mark.skip(reason="x")\ndef test_x(): pass\n'
    _write_test(tmp_path, "catch-corpus/I-5-skip/test_fixture.py", body)
    report = run_all(tmp_path, rules=(TEST_SEMANTIC_DECAY,))
    assert report.diagnostics == ()


# =========================================================================
# V11 — placeholder assertions
# =========================================================================


def test_assert_true_is_flagged(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = "def test_x():\n    assert True\n"
    _write_test(tmp_path, "tests/test_assert_true.py", body)
    report = run_all(tmp_path, rules=(PLACEHOLDER_ASSERTION,))
    assert _codes(report) == ["FA-AUTHORING-V11-PLACEHOLDER-ASSERT"]


def test_assert_true_is_true_is_flagged(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = "def test_x():\n    assert True is True\n"
    _write_test(tmp_path, "tests/test_assert_true_is_true.py", body)
    report = run_all(tmp_path, rules=(PLACEHOLDER_ASSERTION,))
    assert _codes(report) == ["FA-AUTHORING-V11-PLACEHOLDER-ASSERT"]


def test_assert_false_is_false_is_flagged(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = "def test_x():\n    assert False is False\n"
    _write_test(tmp_path, "tests/test_assert_false.py", body)
    report = run_all(tmp_path, rules=(PLACEHOLDER_ASSERTION,))
    assert _codes(report) == ["FA-AUTHORING-V11-PLACEHOLDER-ASSERT"]


def test_assert_int_equals_self_is_flagged(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = "def test_x():\n    assert 1 == 1\n"
    _write_test(tmp_path, "tests/test_assert_int.py", body)
    report = run_all(tmp_path, rules=(PLACEHOLDER_ASSERTION,))
    assert _codes(report) == ["FA-AUTHORING-V11-PLACEHOLDER-ASSERT"]


def test_assert_name_equals_self_is_flagged(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = "def test_x():\n    x = 5\n    assert x == x\n"
    _write_test(tmp_path, "tests/test_assert_name.py", body)
    report = run_all(tmp_path, rules=(PLACEHOLDER_ASSERTION,))
    assert _codes(report) == ["FA-AUTHORING-V11-PLACEHOLDER-ASSERT"]


# --- V11 contradiction split (commit 3) ----------------------------------


def test_assert_x_is_not_x_flagged_as_contradiction(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = "def test_x():\n    x = 5\n    assert x is not x\n"
    _write_test(tmp_path, "tests/test_contra_name.py", body)
    report = run_all(tmp_path, rules=(PLACEHOLDER_ASSERTION,))
    assert _codes(report) == ["FA-AUTHORING-V11-CONTRADICTORY-ASSERT"]


def test_assert_1_is_not_1_flagged_as_contradiction(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = "def test_x():\n    assert 1 is not 1\n"
    _write_test(tmp_path, "tests/test_contra_int.py", body)
    report = run_all(tmp_path, rules=(PLACEHOLDER_ASSERTION,))
    assert _codes(report) == ["FA-AUTHORING-V11-CONTRADICTORY-ASSERT"]


def test_assert_x_is_x_still_flagged_as_placeholder(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = "def test_x():\n    x = 5\n    assert x is x\n"
    _write_test(tmp_path, "tests/test_placeholder_is.py", body)
    report = run_all(tmp_path, rules=(PLACEHOLDER_ASSERTION,))
    assert _codes(report) == ["FA-AUTHORING-V11-PLACEHOLDER-ASSERT"]


def test_assert_x_eq_x_still_flagged_as_placeholder(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = "def test_x():\n    x = 5\n    assert x == x\n"
    _write_test(tmp_path, "tests/test_placeholder_eq.py", body)
    report = run_all(tmp_path, rules=(PLACEHOLDER_ASSERTION,))
    assert _codes(report) == ["FA-AUTHORING-V11-PLACEHOLDER-ASSERT"]


# --- V11 must NOT flag legitimate patterns -------------------------------


def test_assert_call_equals_call_is_not_flagged(tmp_path: Path) -> None:
    """`assert f() == f()` is a legitimate purity / determinism test
    (proven false positive: tests/test_hygiene_suggestions.py:53)."""
    _make_workspace(tmp_path)
    body = "def make() -> int:\n    return 1\n\ndef test_pure():\n    assert make() == make()\n"
    _write_test(tmp_path, "tests/test_assert_pure.py", body)
    report = run_all(tmp_path, rules=(PLACEHOLDER_ASSERTION,))
    assert report.diagnostics == ()


def test_assert_meaningful_compare_is_not_flagged(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = "def test_x():\n    x = 5\n    assert x == 5\n"
    _write_test(tmp_path, "tests/test_assert_meaningful.py", body)
    report = run_all(tmp_path, rules=(PLACEHOLDER_ASSERTION,))
    assert report.diagnostics == ()


def test_assert_attribute_equals_attribute_is_not_flagged(tmp_path: Path) -> None:
    """``a.x == a.x`` could be testing property determinism — be conservative."""
    _make_workspace(tmp_path)
    body = "class C:\n    x = 1\n\ndef test_x():\n    c = C()\n    assert c.x == c.x\n"
    _write_test(tmp_path, "tests/test_assert_attr.py", body)
    report = run_all(tmp_path, rules=(PLACEHOLDER_ASSERTION,))
    assert report.diagnostics == ()


def test_v11_does_not_scan_src(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = "def f():\n    assert True\n"
    _write_test(tmp_path, "src/fa_demo/with_assert.py", body)
    report = run_all(tmp_path, rules=(PLACEHOLDER_ASSERTION,))
    assert report.diagnostics == ()


def test_v11_does_not_scan_catch_corpus(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = "def test_x():\n    assert True\n"
    _write_test(tmp_path, "catch-corpus/F-9/test_fixture.py", body)
    report = run_all(tmp_path, rules=(PLACEHOLDER_ASSERTION,))
    assert report.diagnostics == ()


# =========================================================================
# Combined dispatch (both rules at once)
# =========================================================================


def test_skip_and_placeholder_in_same_file_yield_two_diagnostics(tmp_path: Path) -> None:
    _make_workspace(tmp_path)
    body = 'import pytest\n\n@pytest.mark.skip(reason="x")\ndef test_x():\n    assert True\n'
    _write_test(tmp_path, "tests/test_combined.py", body)
    report = run_all(tmp_path, rules=(TEST_SEMANTIC_DECAY, PLACEHOLDER_ASSERTION))
    codes = sorted(_codes(report))
    assert codes == [
        "FA-AUTHORING-V11-PLACEHOLDER-ASSERT",
        "FA-AUTHORING-V4-PYTEST-SKIP",
    ]
