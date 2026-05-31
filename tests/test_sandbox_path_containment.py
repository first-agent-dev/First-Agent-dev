"""Tests for ``fa.sandbox.path_containment``.

Covers the three failure modes the gate relies on:

- lexical ``..`` traversal rejection
- symlink-escape rejection (resolution outside base)
- non-existent-but-inside paths accepted (workspace files about to
  be created)
"""

from __future__ import annotations

import os
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from fa.sandbox.path_containment import (
    ContainmentResult,
    contains_traversal,
    contains_unresolved_variable,
    is_contained,
    resolve_against,
)


def test_contains_traversal_detects_double_dot() -> None:
    assert contains_traversal("../etc/passwd") is True
    assert contains_traversal("foo/../bar") is True
    assert contains_traversal("..") is True


def test_contains_traversal_ignores_legitimate_paths() -> None:
    assert contains_traversal("foo/bar") is False
    assert contains_traversal("foo.bar") is False
    assert contains_traversal("/abs/path/to/file") is False
    assert contains_traversal("..foo") is False  # token starts-with `..` but is not the parent ref


def test_resolve_against_returns_canonical(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "file.txt"
    resolved = resolve_against("nested/file.txt", tmp_path)
    assert resolved == target.resolve()


def test_resolve_against_returns_none_on_loop(tmp_path: Path) -> None:
    """Symlink loops should produce None, not raise."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    os.symlink(b, a)
    os.symlink(a, b)
    result = resolve_against("a", tmp_path)
    assert result is None


def test_is_contained_accepts_workspace_internal(tmp_path: Path) -> None:
    inner = tmp_path / "src" / "fa" / "file.py"
    inner.parent.mkdir(parents=True)
    inner.touch()
    result = is_contained("src/fa/file.py", tmp_path)
    assert result.contained is True
    assert result.canonical_target == inner.resolve()
    assert result.reason == "ok"


def test_is_contained_accepts_nonexistent_workspace_path(tmp_path: Path) -> None:
    """File about to be created — must pass containment."""
    result = is_contained("not_yet_created.txt", tmp_path)
    assert result.contained is True
    assert result.canonical_target is not None


def test_is_contained_rejects_double_dot(tmp_path: Path) -> None:
    result = is_contained("../escape", tmp_path)
    assert result.contained is False
    assert "traversal" in result.reason


def test_is_contained_rejects_absolute_outside(tmp_path: Path) -> None:
    result = is_contained("/etc/passwd", tmp_path)
    assert result.contained is False
    assert "outside" in result.reason


def test_is_contained_rejects_symlink_escape(tmp_path: Path) -> None:
    """Symlink pointing outside the workspace must be rejected."""
    outside = tmp_path.parent / "outside-target"
    outside.mkdir(exist_ok=True)
    link = tmp_path / "escape-link"
    os.symlink(outside, link)
    result = is_contained("escape-link", tmp_path)
    assert result.contained is False
    assert "outside" in result.reason


def test_is_contained_accepts_internal_symlink(tmp_path: Path) -> None:
    """Symlink whose target is inside the workspace must pass."""
    target = tmp_path / "real"
    target.mkdir()
    link = tmp_path / "via-link"
    os.symlink(target, link)
    result = is_contained("via-link", tmp_path)
    assert result.contained is True


def test_is_contained_rejects_tilde_escape(tmp_path: Path) -> None:
    """Tilde-prefixed targets must expand to ``$HOME`` BEFORE join.

    Before the fix, ``(workspace / "~/secret").expanduser()`` produced
    ``<workspace>/~/secret`` (because ``~`` was no longer at the start
    of the joined path) and containment would PASS — but bash would
    later expand the ``~`` to ``$HOME`` at execution time and write
    outside the workspace. The fix expands the raw target first.
    (Devin Review finding 2026-05-20 on PR #23.)
    """
    result = is_contained("~/secret", tmp_path)
    assert result.contained is False
    assert "outside" in result.reason or "traversal" in result.reason


def test_is_contained_rejects_explicit_home_when_workspace_elsewhere(
    tmp_path: Path,
) -> None:
    """``~`` alone resolves to ``$HOME`` and must be rejected.

    Sibling guard to the ``~/secret`` test: bare ``~`` must not be
    classified as inside the workspace unless the workspace happens to
    be ``$HOME``. The fix ensures ``~`` is expanded to the absolute
    home path before the containment comparison.
    """
    result = is_contained("~", tmp_path)
    assert result.contained is False


def test_is_contained_accepts_tilde_when_workspace_is_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the workspace IS the user's home directory, ``~/file`` passes.

    Regression guard for the tilde-expansion fix: the rejection above
    must not over-fire when the workspace coincidentally equals the
    user home. Builds a fake home and points the platform's
    home-resolution env vars at it.

    ``Path.expanduser()`` reads different env vars per platform — POSIX
    uses ``$HOME`` while Windows uses ``%USERPROFILE%`` (then
    ``%HOMEDRIVE%%HOMEPATH%``). Set all of them via ``monkeypatch`` so
    the test is platform-correct and auto-restores env state (raw
    ``os.environ`` assignment leaked across tests).
    """
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.setenv("HOMEDRIVE", fake_home.drive)
    monkeypatch.setenv("HOMEPATH", str(fake_home)[len(fake_home.drive) :])

    result = is_contained("~/inside.txt", fake_home)
    assert result.contained is True
    assert result.canonical_target is not None
    assert result.canonical_target.is_relative_to(fake_home.resolve())

def test_contains_unresolved_variable_detects_undefined(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``$UNDEFINED`` must leave a literal ``$`` after expandvars."""
    monkeypatch.delenv("FA_TEST_UNDEFINED_VAR", raising=False)
    assert contains_unresolved_variable("$FA_TEST_UNDEFINED_VAR/foo") is True
    assert contains_unresolved_variable("${FA_TEST_UNDEFINED_VAR}/foo") is True


def test_contains_unresolved_variable_accepts_defined(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Variables defined in the agent process must NOT trigger the guard.

    Their expansion is symmetric with what bash sees at execution time
    (same env passed through subprocess), so the path comparison can
    proceed via :func:`resolve_against` instead of being rejected
    upfront.
    """
    monkeypatch.setenv("FA_TEST_DEFINED_VAR", "/tmp")
    assert contains_unresolved_variable("$FA_TEST_DEFINED_VAR/foo") is False
    assert contains_unresolved_variable("${FA_TEST_DEFINED_VAR}/foo") is False


def test_contains_unresolved_variable_accepts_plain_path() -> None:
    """Paths without ``$`` markers always pass the guard."""
    assert contains_unresolved_variable("/etc/passwd") is False
    assert contains_unresolved_variable("foo/bar") is False
    assert contains_unresolved_variable("") is False


def test_is_contained_rejects_undefined_variable_expansion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``rm $UNDEFINED/escape`` must NOT pass containment.

    Before the fix, shlex tokenised this as
    ``["rm", "$UNDEFINED/escape"]`` and ``is_contained("$UNDEFINED/escape",
    workspace)`` joined to ``<workspace>/$UNDEFINED/escape`` (inside
    base, contained=True). But bash with ``shell=True`` expands the
    undefined variable to the empty string at execution time → the
    actual command becomes ``rm /escape`` → escapes the workspace.
    Sibling class to the tilde bypass.
    (Devin Review finding 2026-05-20 on PR #23.)
    """
    monkeypatch.delenv("FA_TEST_UNDEFINED_ESC", raising=False)
    result = is_contained("$FA_TEST_UNDEFINED_ESC/escape", tmp_path)
    assert result.contained is False
    assert "unresolved shell variable" in result.reason


def test_is_contained_rejects_defined_variable_expanding_outside(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``$HOME/secret`` must be rejected when workspace is elsewhere.

    Even when ``$HOME`` IS defined (and therefore the unresolved-variable
    guard passes), the expanded value lands outside the workspace and
    containment must report it as such. Asserts the canonical path
    comparison fires correctly after :func:`os.path.expandvars`.
    """
    monkeypatch.setenv("HOME", "/home/fake-user")
    result = is_contained("$HOME/secret", tmp_path)
    assert result.contained is False
    assert "outside" in result.reason


def test_is_contained_accepts_defined_variable_expanding_inside(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defined var pointing INTO the workspace must pass.

    Regression guard for the expansion path: if an env var legitimately
    resolves to a workspace-internal location, the gate must not
    over-reject. Sets a fake env var to a subdirectory under the
    workspace and verifies containment passes.
    """
    inside = tmp_path / "data"
    inside.mkdir()
    monkeypatch.setenv("FA_TEST_INSIDE_VAR", str(inside))
    result = is_contained("$FA_TEST_INSIDE_VAR/file.txt", tmp_path)
    assert result.contained is True
    assert result.canonical_target is not None
    assert result.canonical_target.is_relative_to(tmp_path.resolve())


def test_containment_result_is_frozen() -> None:
    """Result type is immutable so the audit log is replay-safe."""
    result = ContainmentResult(
        contained=True,
        canonical_target=Path("/tmp"),
        reason="ok",
    )
    with pytest.raises(FrozenInstanceError):
        result.contained = False  # type: ignore[misc]
