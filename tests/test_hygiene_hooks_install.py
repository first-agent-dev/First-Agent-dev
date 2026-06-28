"""Tests for fa.hygiene.hooks.install and fa.hygiene.hooks.status.

This module was previously shipped with 0% coverage. The installer has real
branching logic (workspace resolution, missing-dir guards, the force/no-force
overwrite rules, the missing-script guard, symlink/copy fallback) that is
exactly the kind of code an LLM agent writes confidently but never exercises.
These tests pin each branch.

The status module is also tested here: it is the deterministic verification
path that both humans and agents use to confirm the local hook chain is active.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import fa.hygiene.hooks as hooks_pkg
from fa.hygiene.hooks.install import HOOK_NAMES, install_hooks
from fa.hygiene.hooks.status import check_hooks


def _make_workspace(tmp_path: Path, *, with_git: bool = True) -> Path:
    """Build a minimal First-Agent workspace fixture under tmp_path."""

    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "llms.txt").write_text("marker\n", encoding="utf-8")
    if with_git:
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
    return tmp_path


# ---------------------------------------------------------------------------
# install_hooks tests
# ---------------------------------------------------------------------------


def test_install_hooks_happy_path(tmp_path: Path) -> None:
    root = _make_workspace(tmp_path)

    installed = install_hooks(repo_root=root)

    assert [p.name for p in installed] == list(HOOK_NAMES)
    for path in installed:
        # The installer prefers symlinks but may fall back to copies.
        assert path.exists()
        # Content must match the shipped script next to the installer.
        source = Path(hooks_pkg.install.__file__).resolve().parent / path.name
        assert path.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")


def test_install_hooks_is_idempotent_replacing_own_symlinks(tmp_path: Path) -> None:
    root = _make_workspace(tmp_path)

    first = install_hooks(repo_root=root)
    # Running again must not raise: existing symlinks (ours) get replaced.
    second = install_hooks(repo_root=root)

    assert [p.name for p in first] == [p.name for p in second]
    for path in second:
        assert path.exists()


def test_install_hooks_is_idempotent_replacing_own_copies(tmp_path: Path) -> None:
    """When the first install produced copies (fallback), re-install with force works."""

    root = _make_workspace(tmp_path)
    first = install_hooks(repo_root=root)

    # If the first install was via symlink, force the target to be a
    # regular file to simulate the copy fallback, then re-install.
    for path in first:
        if path.is_symlink():
            content = path.read_text(encoding="utf-8")
            path.unlink()
            path.write_text(content, encoding="utf-8")

    # Re-install with force replaces the copies (this is how the
    # justfile calls it: ``uv run python -m fa.hygiene.hooks.install --force``).
    second = install_hooks(repo_root=root, force=True)
    assert [p.name for p in second] == list(HOOK_NAMES)


def test_install_hooks_refuses_to_clobber_real_file_without_force(
    tmp_path: Path,
) -> None:
    root = _make_workspace(tmp_path)
    # A pre-existing *real* hook file (not a symlink) must be protected.
    existing = root / ".git" / "hooks" / HOOK_NAMES[0]
    existing.write_text("#!/bin/sh\necho mine\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        install_hooks(repo_root=root)

    # The user's file is untouched.
    assert existing.read_text(encoding="utf-8") == "#!/bin/sh\necho mine\n"


def test_install_hooks_force_overwrites_real_file(tmp_path: Path) -> None:
    root = _make_workspace(tmp_path)
    existing = root / ".git" / "hooks" / HOOK_NAMES[0]
    existing.write_text("#!/bin/sh\necho mine\n", encoding="utf-8")

    installed = install_hooks(repo_root=root, force=True)

    assert existing.exists()
    assert [p.name for p in installed] == list(HOOK_NAMES)


def test_install_hooks_rejects_non_workspace(tmp_path: Path) -> None:
    # No knowledge/llms.txt marker => not a First-Agent workspace.
    (tmp_path / ".git" / "hooks").mkdir(parents=True)

    with pytest.raises(SystemExit) as exc:
        install_hooks(repo_root=tmp_path)
    assert "not a First-Agent workspace" in str(exc.value)


def test_install_hooks_requires_git_hooks_dir(tmp_path: Path) -> None:
    root = _make_workspace(tmp_path, with_git=False)

    with pytest.raises(SystemExit) as exc:
        install_hooks(repo_root=root)
    assert "does not exist" in str(exc.value)


def test_install_hooks_errors_when_script_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _make_workspace(tmp_path)
    # Point the installer at an empty scripts dir so the source scripts are gone.
    empty = tmp_path / "empty_scripts"
    empty.mkdir()
    monkeypatch.setattr(install_mod, "scripts_dir", lambda: empty)

    with pytest.raises(SystemExit) as exc:
        install_hooks(repo_root=root)
    assert "missing hook script" in str(exc.value)


def test_main_prints_installed_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _make_workspace(tmp_path)
    monkeypatch.chdir(root)

    rc = install_mod._main([])

    assert rc == 0
    out = capsys.readouterr().out
    for name in HOOK_NAMES:
        assert "installed" in out
        assert f"{root / '.git' / 'hooks' / name}" in out


def test_main_force_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_workspace(tmp_path)
    existing = root / ".git" / "hooks" / HOOK_NAMES[0]
    existing.write_text("#!/bin/sh\necho mine\n", encoding="utf-8")
    monkeypatch.chdir(root)

    rc = install_mod._main(["--force"])

    assert rc == 0
    assert existing.exists()


def test_install_one_symlink_fallback_to_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When os.symlink raises OSError, _install_one falls back to copy."""

    root = _make_workspace(tmp_path)
    src_dir = Path(install_mod.__file__).resolve().parent
    source = src_dir / HOOK_NAMES[0]
    target = root / ".git" / "hooks" / HOOK_NAMES[0]

    # Monkey-patch os.symlink to always fail.
    original_symlink = install_mod.os.symlink
    monkeypatch.setattr(
        install_mod.os,
        "symlink",
        staticmethod(lambda *_args, **_kw: (_ for _ in ()).throw(OSError("no symlink"))),
    )

    result = install_mod._install_one(source, target, force=True)

    assert result == target
    assert target.exists()
    assert not target.is_symlink()
    # Content matches the source.
    assert target.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")

    # Restore so subsequent tests are not affected.
    monkeypatch.setattr(install_mod.os, "symlink", original_symlink)


def test_install_one_copy_fallback_target_is_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Copy-fallback target must have the execute bit set (git requirement)."""

    root = _make_workspace(tmp_path)
    src_dir = Path(hooks_pkg.install.__file__).resolve().parent
    source = src_dir / HOOK_NAMES[0]
    target = root / ".git" / "hooks" / HOOK_NAMES[0]

    # Force the source to have NO execute bit (simulates Windows
    # checkout with core.fileMode=false).
    source.chmod(source.stat().st_mode & ~0o111)

    # Force symlink failure.
    original_symlink = hooks_pkg.install.os.symlink
    monkeypatch.setattr(
        hooks_pkg.install.os,
        "symlink",
        staticmethod(lambda *_args, **_kw: (_ for _ in ()).throw(OSError("no symlink"))),
    )

    hooks_pkg.install._install_one(source, target, force=True)

    # Target must be executable — git skips hooks without the bit.
    assert target.stat().st_mode & 0o111, "copy-fallback target must be executable"

    # Restore.
    monkeypatch.setattr(hooks_pkg.install.os, "symlink", original_symlink)
    source.chmod(source.stat().st_mode | 0o111)  # restore source too


# ---------------------------------------------------------------------------
# Lazy import (package __init__.py) tests
# ---------------------------------------------------------------------------


def test_lazy_import_hook_names() -> None:
    """HOOK_NAMES is accessible through the lazy __getattr__."""

    assert hooks_pkg.HOOK_NAMES == ("pre-commit", "prepare-commit-msg", "commit-msg")


def test_lazy_import_install_hooks() -> None:
    """install_hooks is accessible through the lazy __getattr__."""

    assert callable(hooks_pkg.install_hooks)


def test_lazy_import_check_hooks() -> None:
    """check_hooks is accessible through the lazy __getattr__."""

    assert callable(hooks_pkg.check_hooks)


def test_lazy_import_unknown_attribute_raises() -> None:
    """Accessing an undefined attribute raises AttributeError."""

    with pytest.raises(AttributeError, match="has no attribute"):
        _ = hooks_pkg.nonexistent_thing  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# check_hooks (status) tests
# ---------------------------------------------------------------------------


def test_check_hooks_all_installed(tmp_path: Path) -> None:
    """When all hooks are present and current, check_hooks returns 0."""

    root = _make_workspace(tmp_path)
    # Install all hooks (including pre-commit, now managed by our installer).
    install_hooks(repo_root=root)

    rc = check_hooks(repo_root=root)

    assert rc == 0


def test_check_hooks_missing_pre_commit(tmp_path: Path) -> None:
    """When the pre-commit hook is missing, check_hooks returns 1."""

    root = _make_workspace(tmp_path)
    # Install only the commit-msg hooks, delete the pre-commit hook.
    install_hooks(repo_root=root)
    (root / ".git" / "hooks" / "pre-commit").unlink()

    rc = check_hooks(repo_root=root)

    assert rc == 1


def test_check_hooks_missing_custom_hook(tmp_path: Path) -> None:
    """When a custom hook is missing, check_hooks returns 1."""

    root = _make_workspace(tmp_path)
    # Install all hooks, then delete one custom hook.
    install_hooks(repo_root=root)
    (root / ".git" / "hooks" / HOOK_NAMES[1]).unlink()

    rc = check_hooks(repo_root=root)

    assert rc == 1


def test_check_hooks_stale_copy(tmp_path: Path) -> None:
    """When a copied hook differs from source, check_hooks flags it stale."""

    root = _make_workspace(tmp_path)
    install_hooks(repo_root=root)

    # Simulate a stale copy by overwriting the installed hook with
    # different content.
    hook = root / ".git" / "hooks" / HOOK_NAMES[1]  # prepare-commit-msg
    if hook.is_symlink():
        content = hook.read_text(encoding="utf-8")
        hook.unlink()
        hook.write_text(content + "# stale\n", encoding="utf-8")
    else:
        hook.write_text(hook.read_text(encoding="utf-8") + "# stale\n", encoding="utf-8")

    rc = check_hooks(repo_root=root)

    assert rc == 1


def test_check_hooks_no_git_dir(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """When .git/hooks is missing, check_hooks prints error and returns 1."""

    root = _make_workspace(tmp_path, with_git=False)

    rc = check_hooks(repo_root=root)

    assert rc == 1
    out = capsys.readouterr().out
    assert "not found" in out


def test_check_hooks_rejects_non_workspace(tmp_path: Path) -> None:
    """When not in a First-Agent workspace, check_hooks raises SystemExit."""

    (tmp_path / ".git" / "hooks").mkdir(parents=True)

    with pytest.raises(SystemExit) as exc:
        check_hooks(repo_root=tmp_path)
    assert "not a First-Agent workspace" in str(exc.value)
