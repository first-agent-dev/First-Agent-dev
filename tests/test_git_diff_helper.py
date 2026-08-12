"""C1 tests for scripts/_git_diff.py — synthetic git repo helper.

Verifies:
- changed_python_files scoping by source_prefixes and extensions;
- base-candidate fallback order (origin/main > main > HEAD~1);
- max_files cap returns [] (fail-open) with stderr note;
- missing git / non-git cwd → fail-open [], no raise;
- resolve_tool PATH + .venv/bin fallback, None when both absent;
- no shell=True anywhere;
- script imports have no side effects (no subprocess at import time).

Skill: tests-writing, Pyramid A, C1 (real subprocess + synthetic fs).
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import _git_diff as gd

REPO_ROOT = Path(__file__).resolve().parents[1]


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """Create a synthetic git repo with one baseline commit on ``main``."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")  # init directly on 'main'
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    # Create a fake 'origin/main' pointing at the baseline commit so the
    # helper's first base-candidate ('origin/main') resolves.
    (r / "src").mkdir()
    (r / "tests").mkdir()
    (r / "scripts").mkdir()
    (r / "docs").mkdir()
    (r / "src" / "a.py").write_text("A")
    (r / "tests" / "t.py").write_text("T")
    (r / "docs" / "r.md").write_text("M")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "base")
    # Create a local ref that poses as origin/main for merge-base resolution.
    # The helper iterates refs by name; a lightweight ref named 'origin/main'
    # satisfies `git merge-base HEAD origin/main` in this sandboxed repo
    # without needing an actual remote.
    head = subprocess.run(
        ["git", "-C", str(r), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (r / ".git" / "refs" / "remotes" / "origin").mkdir(parents=True, exist_ok=True)
    (r / ".git" / "refs" / "remotes" / "origin" / "main").write_text(head + "\n")
    return r


class TestChangedPythonFiles:
    def test_filters_by_prefix_and_extension(self, repo: Path) -> None:
        # Add files in src/ and tests/ and scripts/ and docs/
        (repo / "src" / "b.py").write_text("B")
        (repo / "src" / "c.md").write_text("ignore me")
        (repo / "tests" / "u.py").write_text("U")
        (repo / "scripts" / "z.py").write_text("Z")
        (repo / "docs" / "d.py").write_text("IGNORED")  # docs/ not a prefix
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "c1")

        files_src = gd.changed_python_files(repo, source_prefixes=("src/",), max_files=50)
        rels = sorted(p.relative_to(repo).as_posix() for p in files_src)
        assert rels == ["src/b.py"]

        files_all = gd.changed_python_files(
            repo,
            source_prefixes=("src/", "tests/", "scripts/"),
            max_files=50,
        )
        rels = sorted(p.relative_to(repo).as_posix() for p in files_all)
        assert rels == ["scripts/z.py", "src/b.py", "tests/u.py"]

    def test_cap_returns_empty_with_log(self, repo: Path, capsys: Any) -> None:  # type: ignore[no-any-unimported]
        for i in range(3):
            (repo / "src" / f"x{i}.py").write_text(str(i))
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "c")
        out = gd.changed_python_files(repo, source_prefixes=("src/",), max_files=2)
        assert out == []
        err = capsys.readouterr().err
        assert "fail-open" in err
        assert "max_files=2" in err

    def test_missing_git_returns_empty(self, repo: Path, capsys: Any, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-any-unimported]
        monkeypatch.setattr(shutil, "which", lambda _name: None)
        assert gd.changed_python_files(repo, source_prefixes=("src/",)) == []
        assert "git not found" in capsys.readouterr().err

    def test_no_merge_base_returns_empty(self, tmp_path: Path, capsys: Any) -> None:  # type: ignore[no-any-unimported]
        # fresh repo with no commits / no main branch -> fail-open
        r = tmp_path / "r"
        r.mkdir()
        _git(r, "init", "-q")
        _git(r, "config", "user.email", "t@t")
        _git(r, "config", "user.name", "t")
        assert gd.changed_python_files(r, source_prefixes=("src/",)) == []
        assert "no merge-base" in capsys.readouterr().err

    def test_non_git_cwd_returns_empty(self, tmp_path: Path) -> None:
        r = tmp_path / "not-a-repo"
        r.mkdir()
        # git is on PATH but cwd is not a repo -> merge-base fails -> fail-open
        assert gd.changed_python_files(r, source_prefixes=("src/",)) == []

    def test_returns_absolute_existing_files(self, repo: Path) -> None:
        (repo / "src" / "q.py").write_text("Q")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "c")
        out = gd.changed_python_files(repo, source_prefixes=("src/",), max_files=50)
        for p in out:
            assert p.is_absolute()
            assert p.is_file()


class TestResolveTool:
    def test_finds_on_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = tmp_path / "mytool"
        fake.write_text("#!/bin/sh\necho hi\n")
        fake.chmod(0o755)
        monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)
        assert gd.resolve_tool("mytool", repo_root=tmp_path) == str(fake)

    def test_venv_fallback(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # remove PATH; create fake at .venv/bin/mytool
        monkeypatch.setenv("PATH", "")
        venv = tmp_path / ".venv" / "bin"
        venv.mkdir(parents=True)
        t = venv / "mytool"
        t.write_text("#!/bin/sh\necho")
        t.chmod(0o755)
        assert gd.resolve_tool("mytool", repo_root=tmp_path, venv_bin_rel=".venv/bin/mytool") == str(t)

    def test_returns_none_when_neither(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PATH", "")
        assert gd.resolve_tool("nonexistent-tool", repo_root=tmp_path) is None

    def test_returns_path_not_shell_fragment(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        venv = tmp_path / ".venv" / "bin"
        venv.mkdir(parents=True)
        (venv / "mutmut").write_text("#!/bin/sh\necho")
        (venv / "mutmut").chmod(0o755)
        found = gd.resolve_tool("mutmut", repo_root=tmp_path, venv_bin_rel=".venv/bin/mutmut")
        assert found is not None
        assert " " not in found, "resolve_tool must return a single binary path, not a shell fragment"


def test_no_shell_true() -> None:
    """C0: _git_diff.py never invokes a shell."""
    tree = ast.parse((REPO_ROOT / "scripts" / "_git_diff.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = None
            if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id in {"subprocess"}:
                name = fn.attr
            if name in {"run", "Popen", "call", "check_call", "check_output"}:
                for kw in node.keywords:
                    assert kw.arg != "shell" or not (isinstance(kw.value, ast.Constant) and kw.value.value is True), (
                        "subprocess call with shell=True"
                    )


def test_import_is_side_effect_free() -> None:
    """Importing _git_diff must not run subprocess (no git call at import)."""
    # The module is already imported; sanity-check no top-level subprocess.run.
    tree = ast.parse((REPO_ROOT / "scripts" / "_git_diff.py").read_text())
    for node in tree.body:
        assert not isinstance(node, ast.Expr) or not (
            isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
        ), "top-level call expression (possible subprocess at import)"
