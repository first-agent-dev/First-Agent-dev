"""Tests for scripts/check_protected_paths.py (ADR-11-I7 / R-15).

The script lives under scripts/ (outside the importable package), so it
is loaded by file path. It is governance tooling, not Level-0 kernel, so
it may shell out to git.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

from _pytest.capture import CaptureFixture

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_protected_paths.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_protected_paths", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cpp = _load()


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Tester")
    (repo / "README.md").write_text("# r\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "base")


# --- is_protected / protected_hits ----------------------------------------


def test_is_protected_exact_and_prefix(tmp_path: Path) -> None:
    assert cpp.is_protected("src/fa/authoring_tcb.py", tmp_path)
    assert cpp.is_protected("./src/fa/authoring_tcb.py", tmp_path)
    assert cpp.is_protected("src/fa/authoring_rules/exports.py", tmp_path)
    assert cpp.is_protected(".github/CODEOWNERS", tmp_path)


def test_is_protected_rejects_unrelated(tmp_path: Path) -> None:
    assert not cpp.is_protected("src/fa/cli.py", tmp_path)
    assert not cpp.is_protected("README.md", tmp_path)


def test_is_protected_catches_symlink_alias(tmp_path: Path) -> None:
    target = tmp_path / "src" / "fa" / "authoring_tcb.py"
    target.parent.mkdir(parents=True)
    target.write_text("x\n", encoding="utf-8")
    alias = tmp_path / "alias.py"
    alias.symlink_to(target)
    assert cpp.is_protected("alias.py", tmp_path)


def test_protected_hits_sorted_and_deduped(tmp_path: Path) -> None:
    hits = cpp.protected_hits(
        [
            "src/fa/authoring_rules/b.py",
            "src/fa/authoring_rules/a.py",
            "README.md",
            "./src/fa/authoring_rules/a.py",
        ],
        tmp_path,
    )
    assert hits == ["src/fa/authoring_rules/a.py", "src/fa/authoring_rules/b.py"]


# --- changed_paths ---------------------------------------------------------


def test_changed_paths_lists_diff(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "src" / "fa").mkdir(parents=True)
    (tmp_path / "src" / "fa" / "authoring_tcb.py").write_text("k\n", encoding="utf-8")
    _git(tmp_path, "checkout", "-b", "feature")
    _git(tmp_path, "add", "src/fa/authoring_tcb.py")
    _git(tmp_path, "commit", "-m", "touch tcb")
    changed = cpp.changed_paths("main", tmp_path)
    assert "src/fa/authoring_tcb.py" in changed


# --- main ------------------------------------------------------------------


def test_main_flags_protected_path_non_blocking(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "check_protected_paths.py").write_text("x\n", encoding="utf-8")
    _git(tmp_path, "checkout", "-b", "feature")
    _git(tmp_path, "add", "scripts/check_protected_paths.py")
    _git(tmp_path, "commit", "-m", "touch script")

    exit_code = cpp.main(["--base", "main", "--repo-root", str(tmp_path)])
    captured = capsys.readouterr()
    assert exit_code == 0  # non-blocking flag by default
    assert "::warning" in captured.out
    assert "scripts/check_protected_paths.py" in captured.err


def test_main_fail_on_touch(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "src" / "fa").mkdir(parents=True)
    (tmp_path / "src" / "fa" / "authoring_tcb.py").write_text("k\n", encoding="utf-8")
    _git(tmp_path, "checkout", "-b", "feature")
    _git(tmp_path, "add", "src/fa/authoring_tcb.py")
    _git(tmp_path, "commit", "-m", "touch tcb")

    exit_code = cpp.main(
        ["--base", "main", "--repo-root", str(tmp_path), "--fail-on-touch"]
    )
    assert exit_code == 1


def test_main_clean_diff_reports_ok(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    _init_repo(tmp_path)
    (tmp_path / "docs.md").write_text("d\n", encoding="utf-8")
    _git(tmp_path, "checkout", "-b", "feature")
    _git(tmp_path, "add", "docs.md")
    _git(tmp_path, "commit", "-m", "docs only")

    exit_code = cpp.main(["--base", "main", "--repo-root", str(tmp_path)])
    assert exit_code == 0
    assert "no protected/TCB paths touched" in capsys.readouterr().out


def test_main_fails_open_on_diff_error(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    # Not a git repo -> git diff errors -> fail-open (exit 0), never block.
    exit_code = cpp.main(["--base", "main", "--repo-root", str(tmp_path)])
    assert exit_code == 0
    assert "could not compute diff" in capsys.readouterr().err
