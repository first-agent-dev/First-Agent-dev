"""Tests for fa.hygiene.hooks.install.

This module was previously shipped with 0% coverage. The installer has real
branching logic (workspace resolution, missing-dir guards, the force/no-force
overwrite rules, the missing-script guard) that is exactly the kind of code an
LLM agent writes confidently but never exercises. These tests pin each branch.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.hygiene.hooks import install as install_mod
from fa.hygiene.hooks.install import HOOK_NAMES, install_hooks


def _make_workspace(tmp_path: Path, *, with_git: bool = True) -> Path:
    """Build a minimal First-Agent workspace fixture under tmp_path."""
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "llms.txt").write_text("marker\n", encoding="utf-8")
    if with_git:
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
    return tmp_path


def test_install_hooks_happy_path(tmp_path: Path) -> None:
    root = _make_workspace(tmp_path)

    installed = install_hooks(repo_root=root)

    assert [p.name for p in installed] == list(HOOK_NAMES)
    for path in installed:
        assert path.is_symlink()
        # Symlink must resolve to the shipped script next to the installer.
        assert path.resolve().parent == Path(install_mod.__file__).resolve().parent


def test_install_hooks_is_idempotent_replacing_own_symlinks(tmp_path: Path) -> None:
    root = _make_workspace(tmp_path)

    first = install_hooks(repo_root=root)
    # Running again must not raise: existing symlinks (ours) get replaced.
    second = install_hooks(repo_root=root)

    assert [p.name for p in first] == [p.name for p in second]
    for path in second:
        assert path.is_symlink()


def test_install_hooks_refuses_to_clobber_real_file_without_force(tmp_path: Path) -> None:
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

    assert existing.is_symlink()
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
    monkeypatch.setattr(install_mod, "_scripts_dir", lambda: empty)

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
        assert f"installed: {root / '.git' / 'hooks' / name}" in out


def test_main_force_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_workspace(tmp_path)
    existing = root / ".git" / "hooks" / HOOK_NAMES[0]
    existing.write_text("#!/bin/sh\necho mine\n", encoding="utf-8")
    monkeypatch.chdir(root)

    rc = install_mod._main(["--force"])

    assert rc == 0
    assert existing.is_symlink()
