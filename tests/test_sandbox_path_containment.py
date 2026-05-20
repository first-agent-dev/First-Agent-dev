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


def test_containment_result_is_frozen() -> None:
    """Result type is immutable so the audit log is replay-safe."""
    result = ContainmentResult(
        contained=True,
        canonical_target=Path("/tmp"),
        reason="ok",
    )
    with pytest.raises(FrozenInstanceError):
        result.contained = False  # type: ignore[misc]
