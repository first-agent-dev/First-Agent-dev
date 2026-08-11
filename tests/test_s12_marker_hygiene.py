"""C2 (S12.4 / CT3) — skip hygiene across the whole test suite.

Three properties, enforced by AST over every file in ``tests/``:

1. **No unconditional skips.** ``@pytest.mark.skip`` / ``pytest.skip(...)``
   hide a test permanently. The authoring TCB already HARD_BLOCKs these
   (``FA-AUTHORING-V4-PYTEST-SKIP``); this test is the fast local mirror so an
   agent sees the failure from ``pytest`` rather than only from
   ``fa authoring-check``.
2. **No non-strict xfail.** A non-strict xfail passes silently when the bug is
   fixed by accident, so the record of the gap rots (ADR-11-I5).
3. **Every skip reason names a capability, not a platform.** ``pytest -rs`` is
   the operator's only signal about what is *not* verified on their machine.
   "skipped on windows" tells them nothing actionable; "needs POSIX permission
   bits that survive chmod" tells them exactly what is untested and why.

Why AST and not regex (ADR-11-I4): the string ``@pytest.mark.skipif(...)``
appears inside docstrings and inside fixture literals — notably
``tests/test_authoring_rules_tests.py``, which embeds a skipif decorator as
*test data* for the V4 rule's own corpus. A regex would flag that file; the AST
sees it as a string constant and moves on.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import override

import pytest

_TESTS_DIR = Path(__file__).resolve().parent

# Platform words that must never be the whole story in a skip reason. A reason
# may *mention* Windows for context, but it must also state the capability.
_PLATFORM_WORDS = ("windows", "win32", "darwin", "macos", "linux", "platform")

# Capability vocabulary: a reason is actionable if it says what is required or
# what is missing. Kept deliberately small so a lazy reason cannot slip past.
_CAPABILITY_MARKERS = (
    "needs ",
    "requires ",
    "not installed",
    "not available",
    "does not support",
    "unavailable",
    "is deferred",
    "does not allow",
    "semantics only",
)


def _test_files() -> list[Path]:
    return sorted(p for p in _TESTS_DIR.rglob("test_*.py") if "__pycache__" not in p.parts)


def _reason_bearing_files() -> list[Path]:
    """Files that may define a skip reason.

    Wider than :func:`_test_files` on purpose. All six ``requires_*`` reasons
    live in ``tests/_capabilities.py``, which does **not** match ``test_*.py``,
    so scanning only test modules left the ~85 capability skips — the entire
    output of this slice — unchecked by CT3. Proven by sabotage: setting
    ``posix_paths_reason = "skipped on windows"`` passed all 13 hygiene tests.
    """
    extra = [p for p in _TESTS_DIR.glob("_*.py") if "__pycache__" not in p.parts]
    return sorted(set(_test_files()) | set(extra))


def test_the_scanner_sees_the_suite() -> None:
    """Guard against a vacuous pass.

    If the glob broke, every assertion below would hold trivially over an empty
    list. Board lesson: *simplification can silently convert a live check into
    a vacuous one.*
    """
    files = _test_files()
    assert len(files) > 150, f"expected the full suite, found {len(files)} files"


def _iter_decorators(tree: ast.AST) -> list[ast.expr]:
    out: list[ast.expr] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.extend(node.decorator_list)
    return out


def _attr_chain(node: ast.expr) -> str:
    """Render ``pytest.mark.skipif`` from an attribute/call node."""
    target = node.func if isinstance(node, ast.Call) else node
    parts: list[str] = []
    while isinstance(target, ast.Attribute):
        parts.append(target.attr)
        target = target.value
    if isinstance(target, ast.Name):
        parts.append(target.id)
    return ".".join(reversed(parts))


def _is_in_conditional_scope(node: ast.AST, tree: ast.AST) -> bool:
    """Return True if *node* is lexically nested inside a runtime guard.

    Distinguishes *unconditional* ``pytest.skip(...)`` calls (banned) from
    legitimate runtime-conditional skips: inside an ``except`` handler
    (``try: ...; except OSError: pytest.skip(...)``) or inside an ``if``
    block whose test is a capability/environment probe (not a constant).

    S14b.1's symlink-guard tests and the "running inside the repo" layout
    probe are the first in this repo to need these patterns; without this
    scope check the hygiene AST treated any ``pytest.skip(...)`` call as a
    banned top-level skip, producing false positives on legitimate
    guarded skips.
    """

    class Visitor(ast.NodeVisitor):
        def __init__(self, target: ast.AST) -> None:
            self.target = target
            self.stack: list[ast.AST] = []
            self.found = False

        @override
        def generic_visit(self, node: ast.AST) -> None:
            if node is self.target:
                for frame in self.stack:
                    if isinstance(frame, ast.ExceptHandler):
                        self.found = True
                        return
                    if isinstance(frame, ast.If) and not _is_constant(frame.test):
                        self.found = True
                        return
                return
            self.stack.append(node)
            super().generic_visit(node)
            self.stack.pop()

    v = Visitor(node)
    v.visit(tree)
    return v.found


def _is_constant(test: ast.AST) -> bool:
    """Return True for trivially-constant if-tests (``if True: ...``)."""
    return isinstance(test, ast.Constant) and bool(test.value)


def test_no_unconditional_skip_markers() -> None:
    """Property 1 — mirrors FA-AUTHORING-V4-PYTEST-SKIP.

    ``pytest.mark.skip`` decorators are ALWAYS unconditional (the marker is
    applied at collection time). Imperative ``pytest.skip(...)`` calls are
    banned only when they are NOT lexically inside an ``except`` handler;
    runtime-conditional skips such as
    ``try: os.symlink(...); except OSError: pytest.skip(...)`` remain allowed.
    """
    offenders: list[str] = []
    for path in _test_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for dec in _iter_decorators(tree):
            if _attr_chain(dec) == "pytest.mark.skip":
                offenders.append(f"{path.name}:{dec.lineno}")
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _attr_chain(node) == "pytest.skip":
                if not _is_in_conditional_scope(node, tree):
                    offenders.append(f"{path.name}:{node.lineno} (pytest.skip call)")
    assert not offenders, (
        f"unconditional skips hide tests from the suite; use a capability-based skipif or fix the test: {offenders}"
    )


def test_no_non_strict_xfail() -> None:
    """Property 2 — a non-strict xfail can pass silently (ADR-11-I5)."""
    offenders: list[str] = []
    for path in _test_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for dec in _iter_decorators(tree):
            if _attr_chain(dec) != "pytest.mark.xfail":
                continue
            strict = False
            if isinstance(dec, ast.Call):
                strict = any(
                    kw.arg == "strict" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                    for kw in dec.keywords
                )
            if not strict:
                offenders.append(f"{path.name}:{dec.lineno}")
    assert not offenders, f"@pytest.mark.xfail requires strict=True: {offenders}"


def _skipif_reasons() -> list[tuple[str, int, str]]:
    """Every skip reason in ``tests/``, wherever it is written.

    Two forms are collected, because this repo uses both:

    * ``reason=`` passed inline to ``pytest.mark.skipif(...)`` — the classic
      form, e.g. ``reason="shellcheck not installed"``;
    * a module-level ``*_reason = "..."`` constant referenced by a marker —
      the form ``tests/_capabilities.py`` uses for all six capability markers.

    Collecting only the first form made CT3 blind to every reason this slice
    introduced.
    """
    found: list[tuple[str, int, str]] = []
    for path in _reason_bearing_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for dec in _iter_decorators(tree):
            if not isinstance(dec, ast.Call) or _attr_chain(dec) != "pytest.mark.skipif":
                continue
            for kw in dec.keywords:
                if kw.arg == "reason" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    found.append((path.name, dec.lineno, kw.value.value))
        for node in tree.body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
                continue
            if not isinstance(node.value.value, str):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.endswith("_reason"):
                    found.append((path.name, node.lineno, node.value.value))
    return found


def test_skipif_reasons_are_present_and_non_empty() -> None:
    """A skip with no reason is invisible in ``-rs`` output."""
    missing: list[str] = []
    for path in _test_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for dec in _iter_decorators(tree):
            if not isinstance(dec, ast.Call) or _attr_chain(dec) != "pytest.mark.skipif":
                continue
            reasons = [kw for kw in dec.keywords if kw.arg == "reason"]
            if not reasons:
                missing.append(f"{path.name}:{dec.lineno}")
    assert not missing, f"skipif without reason=: {missing}"


def test_skip_reasons_name_a_capability_not_only_a_platform() -> None:
    """Property 3 — CT3, the contract this slice adds.

    A reason may mention a platform for context, but naming *only* a platform
    is not actionable: it tells the operator where the test does not run, not
    what is unverified.
    """
    offenders: list[str] = []
    for name, lineno, reason in _skipif_reasons():
        lowered = reason.lower()
        says_capability = any(token in lowered for token in _CAPABILITY_MARKERS)
        names_platform = any(word in lowered for word in _PLATFORM_WORDS)
        if names_platform and not says_capability:
            offenders.append(f"{name}:{lineno} -> {reason!r}")
    assert not offenders, (
        f"these skip reasons name a platform but not the missing capability; say what is required instead: {offenders}"
    )


def test_reason_scan_is_not_vacuous() -> None:
    """The reason scan must actually find reasons.

    Without this, a bug in ``_skipif_reasons`` would make the CT3 test above
    pass over an empty list — the exact "check that cannot fail" failure mode.
    """
    reasons = _skipif_reasons()
    # Measured 2026-08-02: 20 literal skipif reasons across the suite. The floor
    # is a vacuity guard, not a ratchet — it only has to prove the scan works.
    assert len(reasons) >= 15, f"expected many skipif reasons across the suite, found {len(reasons)}"


@pytest.mark.parametrize(
    "reason",
    [
        "skipped on windows",
        "win32 only",
        "platform not supported",
    ],
)
def test_ct3_predicate_rejects_platform_only_reasons(reason: str) -> None:
    """Kill-check for the CT3 predicate itself.

    Proves the rule can fail. A hygiene test whose predicate silently accepts
    everything is theatre; this pins the discriminator with known-bad inputs.
    """
    lowered = reason.lower()
    says_capability = any(token in lowered for token in _CAPABILITY_MARKERS)
    names_platform = any(word in lowered for word in _PLATFORM_WORDS)
    assert names_platform and not says_capability, f"{reason!r} should be rejected by CT3"


@pytest.mark.parametrize(
    "reason",
    [
        "needs POSIX permission bits that survive chmod (NTFS reports 0o666/0o777)",
        "shellcheck not installed",
        "Windows does not allow dot-only filenames",
        "POSIX execute-bit semantics only",
    ],
)
def test_ct3_predicate_accepts_capability_reasons(reason: str) -> None:
    """The converse: real reasons in this repo must pass, including ones that
    mention Windows while still naming the capability."""
    lowered = reason.lower()
    says_capability = any(token in lowered for token in _CAPABILITY_MARKERS)
    names_platform = any(word in lowered for word in _PLATFORM_WORDS)
    assert says_capability or not names_platform, f"{reason!r} should be accepted by CT3"
