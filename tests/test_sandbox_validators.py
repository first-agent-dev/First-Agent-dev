"""Tests for ``fa.sandbox.validators``.

Each validator is exercised with exact ValidationResult assertions across
positive (allow) and negative (deny) cases, plus malformed-input controls.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from fa.sandbox.validators import (
    ValidationResult,
    _grants_world_write,
    validate_chmod,
    validate_command,
    validate_git,
    validate_rm,
)

# ---------- validate_rm ----------


def test_validate_rm_allows_workspace_file(tmp_path: Path) -> None:
    (tmp_path / "to-delete.txt").write_text("x")
    result = validate_rm("rm to-delete.txt", workspace_root=tmp_path)
    assert result == ValidationResult(allow=True, reason="validator_rm: ok")


def test_validate_rm_ignores_flags_and_denies_no_target(tmp_path: Path) -> None:
    result = validate_rm("rm -f", workspace_root=tmp_path)
    assert result == ValidationResult(allow=False, reason="validator_rm: no target argument")
    (tmp_path / "file.txt").touch()
    res_ok = validate_rm("rm -f file.txt", workspace_root=tmp_path)
    assert res_ok == ValidationResult(allow=True, reason="validator_rm: ok")


def test_validate_rm_denies_root(tmp_path: Path) -> None:
    result = validate_rm("rm /", workspace_root=tmp_path)
    assert result == ValidationResult(
        allow=False,
        reason="validator_rm: target '/' is a system directory (always denied)",
    )


def test_validate_rm_denies_etc(tmp_path: Path) -> None:
    result = validate_rm("rm /etc/passwd", workspace_root=tmp_path)
    base_str = str(tmp_path.resolve())
    expected_reason = (
        "validator_rm: target '/etc/passwd' not contained in workspace "
        f"(resolved path /etc/passwd is outside base {base_str})"
    )
    assert result == ValidationResult(
        allow=False,
        reason=expected_reason,
    )


def test_validate_rm_denies_home(tmp_path: Path) -> None:
    result = validate_rm("rm ~", workspace_root=tmp_path)
    assert result == ValidationResult(
        allow=False,
        reason="validator_rm: target '~' is the user home directory",
    )
    home_path = str(Path("~").expanduser())
    result_expanded = validate_rm(f"rm {home_path}", workspace_root=tmp_path)
    assert result_expanded == ValidationResult(
        allow=False,
        reason=f"validator_rm: target {home_path!r} is the user home directory",
    )


def test_validate_rm_denies_traversal(tmp_path: Path) -> None:
    result = validate_rm("rm ../escape", workspace_root=tmp_path)
    assert result.allow is False
    assert "validator_rm: target '../escape' not contained in workspace" in result.reason


def test_validate_rm_denies_absolute_outside_workspace(tmp_path: Path) -> None:
    result = validate_rm("rm /opt/foo", workspace_root=tmp_path)
    assert result.allow is False
    assert "validator_rm: target '/opt/foo' not contained in workspace" in result.reason


def test_validate_rm_denies_with_no_target(tmp_path: Path) -> None:
    result = validate_rm("rm", workspace_root=tmp_path)
    assert result == ValidationResult(
        allow=False,
        reason="validator_rm: no target argument",
    )


def test_validate_rm_rejects_wrong_head(tmp_path: Path) -> None:
    result = validate_rm("ls foo", workspace_root=tmp_path)
    assert result == ValidationResult(
        allow=False,
        reason="validator_rm: expected `rm`, got ['ls']",
    )


# ---------- _grants_world_write edge cases ----------


def test_grants_world_write_numeric_and_symbolic_edge_cases() -> None:
    assert _grants_world_write("") is True
    assert _grants_world_write("000") is False
    assert _grants_world_write("0602") is True
    assert _grants_world_write("070") is False
    assert _grants_world_write("+w") is True
    assert _grants_world_write("z+w") is True
    assert _grants_world_write("u+w,,g+w") is True
    assert _grants_world_write("ugo") is True
    assert _grants_world_write("a-w,o+w") is True
    assert _grants_world_write("u+r,o+w") is True


# ---------- validate_chmod ----------


def test_validate_chmod_allows_644(tmp_path: Path) -> None:
    (tmp_path / "file").touch()
    result = validate_chmod("chmod 644 file", workspace_root=tmp_path)
    assert result == ValidationResult(allow=True, reason="validator_chmod: ok")


def test_validate_chmod_denies_empty_mode(tmp_path: Path) -> None:
    result = validate_chmod('chmod "" file', workspace_root=tmp_path)
    assert result.allow is False


def test_validate_chmod_denies_777(tmp_path: Path) -> None:
    result = validate_chmod("chmod 777 file", workspace_root=tmp_path)
    assert result == ValidationResult(
        allow=False,
        reason="validator_chmod: mode '777' grants world-write (denied)",
    )


def test_validate_chmod_denies_o_plus_w(tmp_path: Path) -> None:
    result = validate_chmod("chmod o+w file", workspace_root=tmp_path)
    assert result == ValidationResult(
        allow=False,
        reason="validator_chmod: mode 'o+w' grants world-write (denied)",
    )


def test_validate_chmod_denies_a_plus_w(tmp_path: Path) -> None:
    result = validate_chmod("chmod a+w file", workspace_root=tmp_path)
    assert result == ValidationResult(
        allow=False,
        reason="validator_chmod: mode 'a+w' grants world-write (denied)",
    )


def test_validate_chmod_denies_666(tmp_path: Path) -> None:
    result = validate_chmod("chmod 666 file", workspace_root=tmp_path)
    assert result == ValidationResult(
        allow=False,
        reason="validator_chmod: mode '666' grants world-write (denied)",
    )


@pytest.mark.parametrize(
    "mode",
    [
        "a+rw",
        "o+rw",
        "ugo+rw",
        "a=rwx",
        "go=rw",
        "u=rwx,go+rw",
    ],
)
def test_validate_chmod_denies_compound_world_write(mode: str, tmp_path: Path) -> None:
    (tmp_path / "file").touch()
    result = validate_chmod(f"chmod {mode} file", workspace_root=tmp_path)
    assert result == ValidationResult(
        allow=False,
        reason=f"validator_chmod: mode {mode!r} grants world-write (denied)",
    )


@pytest.mark.parametrize(
    "mode",
    [
        "u+w",
        "g+w",
        "u=rwx",
        "a-w",
        "755",
        "644",
    ],
)
def test_validate_chmod_allows_non_world_write(mode: str, tmp_path: Path) -> None:
    (tmp_path / "file").touch()
    result = validate_chmod(f"chmod {mode} file", workspace_root=tmp_path)
    assert result == ValidationResult(allow=True, reason="validator_chmod: ok")


def test_validate_chmod_denies_outside_workspace(tmp_path: Path) -> None:
    result = validate_chmod("chmod 644 /etc/passwd", workspace_root=tmp_path)
    base_str = str(tmp_path.resolve())
    expected_reason = (
        "validator_chmod: target '/etc/passwd' not contained in workspace "
        f"(resolved path /etc/passwd is outside base {base_str})"
    )
    assert result == ValidationResult(
        allow=False,
        reason=expected_reason,
    )


def test_validate_chmod_rejects_missing_args(tmp_path: Path) -> None:
    result = validate_chmod("chmod 644", workspace_root=tmp_path)
    assert result == ValidationResult(
        allow=False,
        reason="validator_chmod: missing mode or target argument",
    )


def test_validate_chmod_rejects_wrong_head(tmp_path: Path) -> None:
    result = validate_chmod("ls 644 file", workspace_root=tmp_path)
    assert result == ValidationResult(
        allow=False,
        reason="validator_chmod: expected `chmod`, got ['ls']",
    )


# ---------- validate_git ----------


def test_validate_git_allows_commit(tmp_path: Path) -> None:
    result = validate_git("git commit -m foo", workspace_root=tmp_path)
    assert result == ValidationResult(allow=True, reason="validator_git: ok")


def test_validate_git_allows_local_config(tmp_path: Path) -> None:
    result = validate_git("git config core.editor vim", workspace_root=tmp_path)
    assert result == ValidationResult(allow=True, reason="validator_git: ok")


def test_validate_git_denies_user_email(tmp_path: Path) -> None:
    cmd = "git --no-pager config user.email evil@example.com"
    result = validate_git(cmd, workspace_root=tmp_path)
    assert result == ValidationResult(
        allow=False,
        reason="validator_git: writing `git config user.email` rewrites git identity (denied)",
    )


def test_validate_git_denies_user_name(tmp_path: Path) -> None:
    result = validate_git("git config user.name evil", workspace_root=tmp_path)
    assert result == ValidationResult(
        allow=False,
        reason="validator_git: writing `git config user.name` rewrites git identity (denied)",
    )


def test_validate_git_denies_global_and_system_config(tmp_path: Path) -> None:
    result_global = validate_git("git config --global core.editor vim", workspace_root=tmp_path)
    assert result_global == ValidationResult(
        allow=False,
        reason="validator_git: `git config --global/--system` writes outside the workspace",
    )
    result_system = validate_git("git config --system core.editor vim", workspace_root=tmp_path)
    assert result_system == ValidationResult(
        allow=False,
        reason="validator_git: `git config --global/--system` writes outside the workspace",
    )


def test_validate_git_denies_force_push_to_main(tmp_path: Path) -> None:
    result1 = validate_git("git push --force origin main", workspace_root=tmp_path)
    assert result1 == ValidationResult(
        allow=False,
        reason="validator_git: force-push to `main`/`master` is denied",
    )
    result2 = validate_git("git push --force main", workspace_root=tmp_path)
    assert result2 == ValidationResult(
        allow=False,
        reason="validator_git: force-push to `main`/`master` is denied",
    )


def test_validate_git_denies_force_with_lease_to_master(tmp_path: Path) -> None:
    result = validate_git(
        "git push --force-with-lease origin master",
        workspace_root=tmp_path,
    )
    assert result == ValidationResult(
        allow=False,
        reason="validator_git: force-push to `main`/`master` is denied",
    )


def test_validate_git_allows_force_push_to_feature_branch(tmp_path: Path) -> None:
    result = validate_git("git push --force origin feature-branch", workspace_root=tmp_path)
    assert result == ValidationResult(allow=True, reason="validator_git: ok")


def test_validate_git_rejects_wrong_head(tmp_path: Path) -> None:
    result = validate_git("ls status", workspace_root=tmp_path)
    assert result == ValidationResult(
        allow=False,
        reason="validator_git: expected `git`, got ['ls']",
    )


# ---------- validate_command dispatcher ----------


def test_validate_command_dispatches_rm(tmp_path: Path) -> None:
    result = validate_command("rm /etc/passwd", workspace_root=tmp_path)
    base_str = str(tmp_path.resolve())
    expected_reason = (
        "validator_rm: target '/etc/passwd' not contained in workspace "
        f"(resolved path /etc/passwd is outside base {base_str})"
    )
    assert result == ValidationResult(
        allow=False,
        reason=expected_reason,
    )


def test_validate_command_dispatches_chmod(tmp_path: Path) -> None:
    result = validate_command("chmod 777 .", workspace_root=tmp_path)
    assert result == ValidationResult(
        allow=False,
        reason="validator_chmod: mode '777' grants world-write (denied)",
    )


def test_validate_command_dispatches_chmod_containment(tmp_path: Path) -> None:
    result = validate_command("chmod 644 /etc/passwd", workspace_root=tmp_path)
    assert result is not None
    assert result.allow is False


def test_validate_command_dispatches_git(tmp_path: Path) -> None:
    result = validate_command("git config user.email x@y.z", workspace_root=tmp_path)
    assert result == ValidationResult(
        allow=False,
        reason="validator_git: writing `git config user.email` rewrites git identity (denied)",
    )


def test_validate_command_returns_none_for_other(tmp_path: Path) -> None:
    assert validate_command("ls -la", workspace_root=tmp_path) is None
    assert validate_command("touch foo", workspace_root=tmp_path) is None


def test_validate_command_denies_empty(tmp_path: Path) -> None:
    result = validate_command("", workspace_root=tmp_path)
    assert result == ValidationResult(
        allow=False,
        reason="validator: command is empty or unparseable",
    )


def test_validation_result_is_frozen() -> None:
    result = ValidationResult(allow=True, reason="ok")
    with pytest.raises(FrozenInstanceError):
        result.allow = False  # type: ignore[misc]
