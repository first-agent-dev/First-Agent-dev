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

import os
import subprocess
import sys
from pathlib import Path

import pytest

import fa.hygiene.hooks as hooks_pkg
import fa.hygiene.hooks.install as install_mod
import fa.hygiene.hooks.status as status_mod

HOOK_NAMES = install_mod.HOOK_NAMES
install_hooks = install_mod.install_hooks
check_hooks = status_mod.check_hooks


def _make_workspace(tmp_path: Path, *, with_git: bool = True) -> Path:
    """Build a minimal First-Agent workspace fixture under tmp_path."""

    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "llms.txt").write_text("marker\n", encoding="utf-8")
    if with_git:
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
    return tmp_path


def _make_worktree_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Build a minimal First-Agent workspace using a git-worktree .git file."""

    root = _make_workspace(tmp_path, with_git=False)
    gitdir = root / ".git-worktree"
    (gitdir / "hooks").mkdir(parents=True)
    (root / ".git").write_text("gitdir: .git-worktree\n", encoding="utf-8")
    return root, gitdir


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o755)


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
        source = Path(install_mod.__file__).resolve().parent / path.name
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

    for path in first:
        if path.is_symlink():
            content = path.read_text(encoding="utf-8")
            path.unlink()
            path.write_text(content, encoding="utf-8")

    second = install_hooks(repo_root=root, force=True)
    assert [p.name for p in second] == list(HOOK_NAMES)


def test_install_hooks_refuses_to_clobber_real_file_without_force(tmp_path: Path) -> None:
    root = _make_workspace(tmp_path)
    existing = root / ".git" / "hooks" / HOOK_NAMES[0]
    existing.write_text("#!/bin/sh\necho mine\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        install_hooks(repo_root=root)

    assert existing.read_text(encoding="utf-8") == "#!/bin/sh\necho mine\n"


def test_install_hooks_force_overwrites_real_file(tmp_path: Path) -> None:
    root = _make_workspace(tmp_path)
    existing = root / ".git" / "hooks" / HOOK_NAMES[0]
    existing.write_text("#!/bin/sh\necho mine\n", encoding="utf-8")

    installed = install_hooks(repo_root=root, force=True)

    assert existing.exists()
    assert [p.name for p in installed] == list(HOOK_NAMES)


def test_install_hooks_rejects_non_workspace(tmp_path: Path) -> None:
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
    assert target.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")

    monkeypatch.setattr(install_mod.os, "symlink", original_symlink)


def test_install_one_copy_fallback_target_is_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Copy-fallback target must have the execute bit set (git requirement)."""

    root = _make_workspace(tmp_path)
    src_dir = Path(install_mod.__file__).resolve().parent
    source = src_dir / HOOK_NAMES[0]
    target = root / ".git" / "hooks" / HOOK_NAMES[0]

    source.chmod(source.stat().st_mode & ~0o111)

    original_symlink = install_mod.os.symlink
    monkeypatch.setattr(
        install_mod.os,
        "symlink",
        staticmethod(lambda *_args, **_kw: (_ for _ in ()).throw(OSError("no symlink"))),
    )

    install_mod._install_one(source, target, force=True)

    assert target.stat().st_mode & 0o111, "copy-fallback target must be executable"

    monkeypatch.setattr(install_mod.os, "symlink", original_symlink)
    source.chmod(source.stat().st_mode | 0o111)


def test_install_hooks_uses_worktree_gitdir(tmp_path: Path) -> None:
    """Installer resolves hooks dir through a .git file in worktree layouts."""

    root, gitdir = _make_worktree_workspace(tmp_path)
    installed = install_hooks(repo_root=root)

    assert [p.parent for p in installed] == [gitdir / "hooks"] * len(HOOK_NAMES)
    assert [p.name for p in installed] == list(HOOK_NAMES)


# ---------------------------------------------------------------------------
# Package export tests
# ---------------------------------------------------------------------------


def test_lazy_import_hook_names() -> None:
    assert hooks_pkg.HOOK_NAMES == ("pre-commit", "prepare-commit-msg", "commit-msg")


def test_lazy_import_install_hooks() -> None:
    assert callable(hooks_pkg.install_hooks)


def test_lazy_import_check_hooks() -> None:
    assert callable(hooks_pkg.check_hooks)


def test_lazy_import_unknown_attribute_raises() -> None:
    with pytest.raises(AttributeError, match="has no attribute"):
        _ = hooks_pkg.nonexistent_thing  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# check_hooks (status) tests
# ---------------------------------------------------------------------------


def test_check_hooks_all_installed(tmp_path: Path) -> None:
    root = _make_workspace(tmp_path)
    install_hooks(repo_root=root)

    rc = check_hooks(repo_root=root)

    assert rc == 0


def test_check_hooks_missing_pre_commit(tmp_path: Path) -> None:
    root = _make_workspace(tmp_path)
    install_hooks(repo_root=root)
    (root / ".git" / "hooks" / "pre-commit").unlink()

    rc = check_hooks(repo_root=root)

    assert rc == 1


def test_check_hooks_missing_custom_hook(tmp_path: Path) -> None:
    root = _make_workspace(tmp_path)
    install_hooks(repo_root=root)
    (root / ".git" / "hooks" / HOOK_NAMES[1]).unlink()

    rc = check_hooks(repo_root=root)

    assert rc == 1


def test_check_hooks_stale_copy(tmp_path: Path) -> None:
    root = _make_workspace(tmp_path)
    install_hooks(repo_root=root)

    hook = root / ".git" / "hooks" / HOOK_NAMES[1]
    if hook.is_symlink():
        content = hook.read_text(encoding="utf-8")
        hook.unlink()
        hook.write_text(content + "# stale\n", encoding="utf-8")
    else:
        hook.write_text(hook.read_text(encoding="utf-8") + "# stale\n", encoding="utf-8")

    rc = check_hooks(repo_root=root)

    assert rc == 1


@pytest.mark.skipif(os.name == "nt", reason="POSIX execute-bit semantics only")
def test_check_hooks_non_executable_copy_is_unhealthy(tmp_path: Path) -> None:
    root = _make_workspace(tmp_path)
    install_hooks(repo_root=root)

    hook = root / ".git" / "hooks" / HOOK_NAMES[0]
    if hook.is_symlink():
        content = hook.read_text(encoding="utf-8")
        hook.unlink()
        hook.write_text(content, encoding="utf-8")
    hook.chmod(hook.stat().st_mode & ~0o111)

    rc = check_hooks(repo_root=root)

    assert rc == 1


def test_check_hooks_no_git_dir(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _make_workspace(tmp_path, with_git=False)

    rc = check_hooks(repo_root=root)

    assert rc == 1
    out = capsys.readouterr().out
    assert "not found" in out


def test_check_hooks_rejects_non_workspace(tmp_path: Path) -> None:
    (tmp_path / ".git" / "hooks").mkdir(parents=True)

    with pytest.raises(SystemExit) as exc:
        check_hooks(repo_root=tmp_path)
    assert "not a First-Agent workspace" in str(exc.value)


def test_check_hooks_uses_worktree_gitdir(tmp_path: Path) -> None:
    root, _gitdir = _make_worktree_workspace(tmp_path)
    install_hooks(repo_root=root)

    rc = check_hooks(repo_root=root)

    assert rc == 0


# ---------------------------------------------------------------------------
# Runtime warning and shell-hook behavior
# ---------------------------------------------------------------------------


def test_module_entrypoints_emit_no_runtime_warning(tmp_path: Path) -> None:
    """Running install/status as modules must not emit runpy RuntimeWarning."""

    root = _make_workspace(tmp_path)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent / "src")

    install_result = subprocess.run(
        [sys.executable, "-Wdefault", "-m", "fa.hygiene.hooks.install", "--help"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    status_result = subprocess.run(
        [sys.executable, "-Wdefault", "-m", "fa.hygiene.hooks.status"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert "RuntimeWarning" not in install_result.stderr
    assert "RuntimeWarning" not in status_result.stderr


def test_pre_commit_restages_only_modified_staged_files(tmp_path: Path) -> None:
    """Retry path must re-stage only previously staged files that hooks changed."""

    root = _make_workspace(tmp_path)
    hook = Path(install_mod.__file__).resolve().parent / "pre-commit"
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    log_path = tmp_path / "hook.log"
    count_path = tmp_path / "uv.count"

    uv_script = f'''#!/usr/bin/env bash
count=0
if [[ -f "{count_path}" ]]; then
  count=$(cat "{count_path}")
fi
count=$((count+1))
printf '%s' "$count" > "{count_path}"
printf 'uv %s\\n' "$*" >> "{log_path}"
if [[ "$count" -eq 1 ]]; then
  exit 1
fi
exit 0
'''
    git_script = f'''#!/usr/bin/env bash
printf 'git %s\\n' "$*" >> "{log_path}"
if [[ "$1" == diff && "$2" == --cached && "$3" == --name-only && "$4" == -z ]]; then
  printf 'tracked.py\\0'
  exit 0
fi
if [[ "$1" == diff && "$2" == --quiet && "$3" == -- && "$4" == tracked.py ]]; then
  exit 1
fi
if [[ "$1" == add ]]; then
  exit 0
fi
exit 0
'''
    _write_executable(fakebin / "uv", uv_script)
    _write_executable(fakebin / "git", git_script)

    env = dict(os.environ)
    env["PATH"] = f"{fakebin}:{env['PATH']}"

    result = subprocess.run(
        ["bash", str(hook)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    log = log_path.read_text(encoding="utf-8")
    assert result.returncode == 0
    assert "git add -- tracked.py" in log
    assert "git add -u" not in log


def test_pre_commit_does_not_stage_unrelated_unstaged_files(tmp_path: Path) -> None:
    """Retry path must not stage unrelated tracked files outside staged snapshot."""

    root = _make_workspace(tmp_path)
    hook = Path(install_mod.__file__).resolve().parent / "pre-commit"
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    log_path = tmp_path / "hook.log"
    count_path = tmp_path / "uv.count"

    uv_script = f'''#!/usr/bin/env bash
count=0
if [[ -f "{count_path}" ]]; then
  count=$(cat "{count_path}")
fi
count=$((count+1))
printf '%s' "$count" > "{count_path}"
printf 'uv %s\\n' "$*" >> "{log_path}"
if [[ "$count" -eq 1 ]]; then
  exit 1
fi
exit 0
'''
    git_script = f'''#!/usr/bin/env bash
printf 'git %s\\n' "$*" >> "{log_path}"
if [[ "$1" == diff && "$2" == --cached && "$3" == --name-only && "$4" == -z ]]; then
  printf 'tracked.py\\0'
  exit 0
fi
if [[ "$1" == diff && "$2" == --quiet && "$3" == -- && "$4" == tracked.py ]]; then
  exit 1
fi
if [[ "$1" == diff && "$2" == --quiet && "$3" == -- && "$4" == unrelated.py ]]; then
  exit 1
fi
if [[ "$1" == add ]]; then
  exit 0
fi
exit 0
'''
    _write_executable(fakebin / "uv", uv_script)
    _write_executable(fakebin / "git", git_script)

    env = dict(os.environ)
    env["PATH"] = f"{fakebin}:{env['PATH']}"

    result = subprocess.run(
        ["bash", str(hook)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    log = log_path.read_text(encoding="utf-8")
    assert result.returncode == 0
    assert "git add -- tracked.py" in log
    assert "git add -- unrelated.py" not in log
