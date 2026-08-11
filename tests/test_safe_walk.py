"""C3 adversarial tests for fa.memory._safe_walk (symlink escape, dot-dir
pruning, size caps, tests/ filtering, git-ls-files fast path, os.walk fallback).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.memory._safe_walk import (
    DEFAULT_PATTERNS,
    EXCLUDE_DIR_GLOBS,
    EXTRA_EXCLUDE_DIRS,
    iter_searchable_files,
)


def _mk(root: Path, rel: str, content: str = "x", size: int | None = None) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if size is not None:
        p.write_bytes(b"a" * size)
    else:
        p.write_text(content, encoding="utf-8")
    return p


def test_iter_searchable_files_basic_inclusion(tmp_path: Path) -> None:
    _mk(tmp_path, "src/a.py", "hello")
    _mk(tmp_path, "src/b.md", "hello")
    _mk(tmp_path, "tests/test_a.py", "hello")
    rels = sorted(rel for _, rel, _, _ in iter_searchable_files(tmp_path, DEFAULT_PATTERNS))
    assert rels == ["src/a.py", "src/b.md", "tests/test_a.py"]


def test_iter_searchable_files_include_tests_false(tmp_path: Path) -> None:
    _mk(tmp_path, "src/a.py", "x")
    _mk(tmp_path, "tests/test_a.py", "x")
    rels = sorted(
        rel
        for _, rel, _, _ in iter_searchable_files(
            tmp_path,
            DEFAULT_PATTERNS,
            include_tests=False,
        )
    )
    assert rels == ["src/a.py"]


def test_iter_searchable_files_excludes_node_modules_and_dot_dirs(tmp_path: Path) -> None:
    _mk(tmp_path, "src/a.py", "x")
    _mk(tmp_path, "node_modules/foo.js", "x")
    _mk(tmp_path, ".git/HEAD", "x")
    _mk(tmp_path, "__pycache__/foo.cpython-313.pyc", "x")
    rels = sorted(rel for _, rel, _, _ in iter_searchable_files(tmp_path, DEFAULT_PATTERNS))
    assert rels == ["src/a.py"]


def test_iter_searchable_files_excludes_extra_dirs(tmp_path: Path) -> None:
    for d in (".tox", ".pytest_cache", ".ruff_cache", ".nox", "htmlcov"):
        _mk(tmp_path, f"{d}/a.py", "x")
    _mk(tmp_path, "src/a.py", "x")
    rels = sorted(rel for _, rel, _, _ in iter_searchable_files(tmp_path, DEFAULT_PATTERNS))
    assert rels == ["src/a.py"]
    # sanity: EXTRA_EXCLUDE_DIRS actually names these
    for d in (".tox", ".pytest_cache", ".ruff_cache", ".nox", "htmlcov"):
        assert d in EXTRA_EXCLUDE_DIRS


def test_iter_searchable_files_excludes_egg_info_glob(tmp_path: Path) -> None:
    _mk(tmp_path, "fa.egg-info/PKG-INFO", "x")
    _mk(tmp_path, "fa.egg-info/SOURCES.txt", "x")
    _mk(tmp_path, "src/a.py", "x")
    rels = sorted(
        rel
        for _, rel, _, _ in iter_searchable_files(
            tmp_path,
            (*DEFAULT_PATTERNS, "*.txt", "PKG-INFO"),
        )
    )
    # src/a.py is included; fa.egg-info/** is pruned
    assert "src/a.py" in rels
    assert not any(".egg-info" in r for r in rels)
    assert "*.egg-info" in EXCLUDE_DIR_GLOBS


def test_iter_searchable_files_size_cap(tmp_path: Path) -> None:
    _mk(tmp_path, "src/small.py", size=100)
    _mk(tmp_path, "src/big.py", size=1_000_000)  # 1 MB, over 200 KB cap
    rels = sorted(
        rel
        for _, rel, _, _ in iter_searchable_files(
            tmp_path,
            DEFAULT_PATTERNS,
            max_file_size=200_000,
        )
    )
    assert rels == ["src/small.py"]


def test_iter_searchable_files_symlink_escape_blocked(tmp_path: Path) -> None:
    _mk(tmp_path, "src/a.py", "x")
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("SECRET", encoding="utf-8")
    link = tmp_path / "src" / "escape.py"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    rels = sorted(rel for _, rel, _, _ in iter_searchable_files(tmp_path, DEFAULT_PATTERNS))
    # escape.py is a symlink resolving outside root → must be skipped
    assert "src/escape.py" not in rels
    assert rels == ["src/a.py"]


def test_iter_searchable_files_symlink_inside_root_deduped(tmp_path: Path) -> None:
    """Symlinks pointing inside the root are allowed, but we deduplicate by
    resolved path so the same underlying inode is not yielded twice
    (once via its real name, once via the symlink). Either the link path
    OR the real path may appear — the guarantee is exactly-once yield per
    inode, and containment is enforced."""
    real = _mk(tmp_path, "src/real.py", "x")
    link = tmp_path / "src" / "link.py"
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("symlinks unavailable")
    rels = sorted(rel for _, rel, _, _ in iter_searchable_files(tmp_path, DEFAULT_PATTERNS))
    # Exactly one entry (dedup) — and it must be a .py file under src/.
    assert len(rels) == 1, f"expected exactly one deduped entry; got {rels}"
    assert rels[0].endswith(".py")
    assert rels[0].startswith("src/")
    # No duplicates
    assert len(rels) == len(set(rels))


def test_iter_searchable_files_falls_back_to_walk_when_not_git_repo(tmp_path: Path) -> None:
    _mk(tmp_path, "src/a.py", "x")
    # tmp_path is NOT a git repo; iter_searchable_files should still find the
    # file via os.walk after git ls-files fails.
    rels = sorted(
        rel
        for _, rel, _, _ in iter_searchable_files(
            tmp_path,
            DEFAULT_PATTERNS,
            use_git_ls_files=True,
        )
    )
    assert rels == ["src/a.py"]


def test_iter_searchable_files_respects_extra_exclude_dirs(tmp_path: Path) -> None:
    _mk(tmp_path, "buildout/a.py", "x")
    _mk(tmp_path, "src/a.py", "x")
    rels = sorted(
        rel
        for _, rel, _, _ in iter_searchable_files(
            tmp_path,
            DEFAULT_PATTERNS,
            extra_exclude_dirs=frozenset({"buildout"}),
        )
    )
    assert rels == ["src/a.py"]
