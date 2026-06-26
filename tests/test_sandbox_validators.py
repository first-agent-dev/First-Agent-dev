"""Tests for ``fa.sandbox.validators``.

Each validator is exercised with at least one positive (allow) and
two negative (deny) cases, plus a malformed-input control to confirm
the validator fails closed.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from fa.sandbox.validators import (
    ValidationResult,
    validate_chmod,
    validate_command,
    validate_git,
    validate_rm,
)

# ---------- validate_rm ----------


def test_validate_rm_allows_workspace_file(tmp_path: Path) -> None:
    (tmp_path / "to-delete.txt").write_text("x")
    result = validate_rm("rm to-delete.txt", workspace_root=tmp_path)
    assert result.allow is True


def test_validate_rm_denies_root(tmp_path: Path) -> None:
    result = validate_rm("rm /", workspace_root=tmp_path)
    assert result.allow is False
    assert "system" in result.reason


def test_validate_rm_denies_etc(tmp_path: Path) -> None:
    result = validate_rm("rm /etc/passwd", workspace_root=tmp_path)
    assert result.allow is False


def test_validate_rm_denies_home(tmp_path: Path) -> None:
    result = validate_rm("rm ~", workspace_root=tmp_path)
    assert result.allow is False
    assert "home" in result.reason


def test_validate_rm_denies_traversal(tmp_path: Path) -> None:
    result = validate_rm("rm ../escape", workspace_root=tmp_path)
    assert result.allow is False
    assert "traversal" in result.reason or "outside" in result.reason


def test_validate_rm_denies_absolute_outside_workspace(tmp_path: Path) -> None:
    result = validate_rm("rm /opt/foo", workspace_root=tmp_path)
    assert result.allow is False


def test_validate_rm_denies_with_no_target(tmp_path: Path) -> None:
    result = validate_rm("rm", workspace_root=tmp_path)
    assert result.allow is False
    assert "no target" in result.reason


def test_validate_rm_rejects_wrong_head(tmp_path: Path) -> None:
    result = validate_rm("ls foo", workspace_root=tmp_path)
    assert result.allow is False


# ---------- validate_chmod ----------


def test_validate_chmod_allows_644(tmp_path: Path) -> None:
    (tmp_path / "file").touch()
    result = validate_chmod("chmod 644 file", workspace_root=tmp_path)
    assert result.allow is True


def test_validate_chmod_denies_777(tmp_path: Path) -> None:
    result = validate_chmod("chmod 777 file", workspace_root=tmp_path)
    assert result.allow is False
    assert "world-write" in result.reason


def test_validate_chmod_denies_o_plus_w(tmp_path: Path) -> None:
    result = validate_chmod("chmod o+w file", workspace_root=tmp_path)
    assert result.allow is False


def test_validate_chmod_denies_a_plus_w(tmp_path: Path) -> None:
    result = validate_chmod("chmod a+w file", workspace_root=tmp_path)
    assert result.allow is False


def test_validate_chmod_denies_666(tmp_path: Path) -> None:
    result = validate_chmod("chmod 666 file", workspace_root=tmp_path)
    assert result.allow is False


@pytest.mark.parametrize(
    "mode",
    [
        # Compound symbolic modes that the original substring-match
        # implementation missed — Agent Review finding 2026-05-20.
        "a+rw",
        "o+rw",
        "ugo+rw",
        "a=rwx",
        "go=rw",
        "u=rwx,go+rw",  # comma-chained clause where second clause grants o+w.
    ],
)
def test_validate_chmod_denies_compound_world_write(mode: str, tmp_path: Path) -> None:
    (tmp_path / "file").touch()
    result = validate_chmod(f"chmod {mode} file", workspace_root=tmp_path)
    assert result.allow is False
    assert "world-write" in result.reason


@pytest.mark.parametrize(
    "mode",
    [
        "u+w",  # owner-only write.
        "g+w",  # group-only write.
        "u=rwx",  # owner-only RWX, no other / all scope.
        "a-w",  # explicit remove cannot grant world-write.
        "755",  # group/other = r-x.
        "644",  # baseline.
    ],
)
def test_validate_chmod_allows_non_world_write(mode: str, tmp_path: Path) -> None:
    (tmp_path / "file").touch()
    result = validate_chmod(f"chmod {mode} file", workspace_root=tmp_path)
    assert result.allow is True


def test_validate_chmod_denies_outside_workspace(tmp_path: Path) -> None:
    result = validate_chmod("chmod 644 /etc/passwd", workspace_root=tmp_path)
    assert result.allow is False


def test_validate_chmod_rejects_missing_args(tmp_path: Path) -> None:
    result = validate_chmod("chmod 644", workspace_root=tmp_path)
    assert result.allow is False


# ---------- validate_git ----------


def test_validate_git_allows_commit(tmp_path: Path) -> None:
    result = validate_git("git commit -m foo", workspace_root=tmp_path)
    assert result.allow is True


def test_validate_git_allows_local_config(tmp_path: Path) -> None:
    result = validate_git("git config core.editor vim", workspace_root=tmp_path)
    assert result.allow is True


def test_validate_git_denies_user_email(tmp_path: Path) -> None:
    result = validate_git("git config user.email evil@example.com", workspace_root=tmp_path)
    assert result.allow is False
    assert "identity" in result.reason


def test_validate_git_denies_user_name(tmp_path: Path) -> None:
    result = validate_git("git config user.name evil", workspace_root=tmp_path)
    assert result.allow is False


def test_validate_git_denies_global_config(tmp_path: Path) -> None:
    result = validate_git("git config --global core.editor vim", workspace_root=tmp_path)
    assert result.allow is False
    assert "global" in result.reason


def test_validate_git_denies_force_push_to_main(tmp_path: Path) -> None:
    result = validate_git("git push --force origin main", workspace_root=tmp_path)
    assert result.allow is False
    assert "force-push" in result.reason


def test_validate_git_denies_force_with_lease_to_master(
    tmp_path: Path,
) -> None:
    result = validate_git(
        "git push --force-with-lease origin master",
        workspace_root=tmp_path,
    )
    assert result.allow is False


def test_validate_git_allows_force_push_to_feature_branch(
    tmp_path: Path,
) -> None:
    result = validate_git("git push --force origin feature-branch", workspace_root=tmp_path)
    assert result.allow is True


# ---------- validate_command dispatcher ----------


def test_validate_command_dispatches_rm(tmp_path: Path) -> None:
    result = validate_command("rm /etc/passwd", workspace_root=tmp_path)
    assert result is not None
    assert result.allow is False


def test_validate_command_dispatches_chmod(tmp_path: Path) -> None:
    result = validate_command("chmod 777 .", workspace_root=tmp_path)
    assert result is not None
    assert result.allow is False


def test_validate_command_dispatches_git(tmp_path: Path) -> None:
    result = validate_command("git config user.email x@y.z", workspace_root=tmp_path)
    assert result is not None
    assert result.allow is False


def test_validate_command_returns_none_for_other(tmp_path: Path) -> None:
    """Commands without a per-command validator return None."""
    assert validate_command("ls -la", workspace_root=tmp_path) is None
    assert validate_command("touch foo", workspace_root=tmp_path) is None


def test_validate_command_denies_empty(tmp_path: Path) -> None:
    result = validate_command("", workspace_root=tmp_path)
    assert result is not None
    assert result.allow is False


def test_validation_result_is_frozen() -> None:
    """Result type is immutable so the audit log is replay-safe."""
    result = ValidationResult(allow=True, reason="ok")
    with pytest.raises(FrozenInstanceError):
        result.allow = False  # type: ignore[misc]
