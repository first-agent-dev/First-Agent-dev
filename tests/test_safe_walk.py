"""C3 adversarial tests for fa.memory._safe_walk (symlink escape, dot-dir
pruning, size caps, tests/ filtering, git-ls-files fast path, os.walk fallback).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from fa.memory._safe_walk import (
    DEFAULT_PATTERNS,
    EXCLUDE_DIR_GLOBS,
    EXTRA_EXCLUDE_DIRS,
    RootedFileReader,
    RootedReadError,
    iter_searchable_files,
)
from tests._capabilities import requires_symlinks


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


@requires_symlinks
def test_iter_searchable_files_symlink_escape_blocked(tmp_path: Path) -> None:
    _mk(tmp_path, "src/a.py", "x")
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("SECRET", encoding="utf-8")
    link = tmp_path / "src" / "escape.py"
    link.symlink_to(outside)
    rels = sorted(rel for _, rel, _, _ in iter_searchable_files(tmp_path, DEFAULT_PATTERNS))
    # escape.py is a symlink resolving outside root → must be skipped
    assert "src/escape.py" not in rels
    assert rels == ["src/a.py"]


@requires_symlinks
def test_iter_searchable_files_symlink_inside_root_deduped(tmp_path: Path) -> None:
    """Symlinks pointing inside the root are allowed, but we deduplicate by
    resolved path so the same underlying inode is not yielded twice
    (once via its real name, once via the symlink). Either the link path
    OR the real path may appear — the guarantee is exactly-once yield per
    inode, and containment is enforced."""
    real = _mk(tmp_path, "src/real.py", "x")
    link = tmp_path / "src" / "link.py"
    link.symlink_to(real)
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


def test_rooted_file_reader_reads_only_bounded_relative_regular_files(tmp_path: Path) -> None:
    _mk(tmp_path, "src/mod.py", "def safe():\n    return 1\n")
    with RootedFileReader(tmp_path) as reader:
        assert reader.read_bytes("src/mod.py", max_bytes=100) == b"def safe():\n    return 1\n"
        with pytest.raises(RootedReadError, match="invalid_path"):
            reader.read_bytes("../outside.py", max_bytes=100)
        with pytest.raises(RootedReadError, match="file_too_large"):
            reader.read_bytes("src/mod.py", max_bytes=4)


@requires_symlinks
def test_rooted_file_reader_resolves_in_root_file_and_directory_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "view"
    target = _mk(root, "real/mod.py", "def safe():\n    pass\n")
    (root / "alias.py").symlink_to("real/mod.py")
    (root / "linkdir").symlink_to("real", target_is_directory=True)
    with RootedFileReader(root) as reader:
        assert reader.read_bytes_with_path("alias.py", max_bytes=100) == (
            "real/mod.py",
            b"def safe():\n    pass\n",
        )
        assert reader.read_bytes_with_path("linkdir/mod.py", max_bytes=100) == (
            "real/mod.py",
            b"def safe():\n    pass\n",
        )
        (root / "absolute.py").symlink_to(target)
        assert reader.read_bytes_with_path("absolute.py", max_bytes=100)[0] == "real/mod.py"


@requires_symlinks
def test_rooted_file_reader_refuses_escaping_symlink(tmp_path: Path) -> None:
    target = _mk(tmp_path, "outside/secret.py", "def escaped_secret():\n    pass\n")
    root = tmp_path / "view"
    root.mkdir()
    (root / "alias.py").symlink_to(target)
    with RootedFileReader(root) as reader:
        with pytest.raises(RootedReadError, match="symlink_escape"):
            reader.read_bytes("alias.py", max_bytes=100)


def test_rooted_file_reader_refuses_replaced_parent_directory(tmp_path: Path) -> None:
    root = tmp_path / "view"
    _mk(root, "src/mod.py", "def safe():\n    pass\n")
    outside = _mk(tmp_path, "outside/mod.py", "def escaped_secret():\n    pass\n")
    with RootedFileReader(root) as reader:
        (root / "src").rename(root / "src-old")
        (root / "src").symlink_to(outside.parent, target_is_directory=True)
        with pytest.raises(RootedReadError):
            reader.read_bytes("src/mod.py", max_bytes=100)


def test_rooted_file_reader_refuses_hardlinks(tmp_path: Path) -> None:
    source = _mk(tmp_path, "view/source.py", "def linked():\n    pass\n")
    alias = tmp_path / "view" / "alias.py"
    try:
        os.link(source, alias)
    except OSError as exc:
        pytest.skip(f"hardlinks unavailable: {exc}")
    with RootedFileReader(tmp_path / "view") as reader:
        with pytest.raises(RootedReadError, match="hardlinked_file"):
            reader.read_bytes("alias.py", max_bytes=100)


@requires_symlinks
def test_rooted_file_reader_refuses_symlink_replacement_during_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "view"
    _mk(root, "real/mod.py", size=100_000)
    outside = _mk(tmp_path, "outside/mod.py", "def escaped_secret():\n    pass\n")
    alias = root / "alias.py"
    alias.symlink_to("real/mod.py")
    with RootedFileReader(root) as reader:
        original_read = os.read
        replaced = False

        def read_then_replace(fd: int, size: int) -> bytes:
            nonlocal replaced
            chunk = original_read(fd, size)
            if not replaced:
                replaced = True
                alias.unlink()
                alias.symlink_to(outside)
            return chunk

        monkeypatch.setattr(os, "read", read_then_replace)
        with pytest.raises(RootedReadError, match="path_changed"):
            reader.read_bytes_with_path("alias.py", max_bytes=200_000)


def test_rooted_file_reader_rejects_identity_drift_during_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _mk(tmp_path, "view/mod.py", size=100_000)
    with RootedFileReader(tmp_path / "view") as reader:
        original_read = os.read
        mutated = False

        def read_then_mutate(fd: int, size: int) -> bytes:
            nonlocal mutated
            chunk = original_read(fd, size)
            if not mutated:
                mutated = True
                source.write_bytes(b"b" * 100_000)
            return chunk

        monkeypatch.setattr(os, "read", read_then_mutate)
        with pytest.raises(RootedReadError, match="file_changed"):
            reader.read_bytes("mod.py", max_bytes=200_000)


def test_strict_walker_keeps_oversized_source_as_refusal_candidate(tmp_path: Path) -> None:
    _mk(tmp_path, "src/large.py", "x" * 20)
    walked = list(iter_searchable_files(tmp_path, max_file_size=4, strict_paths=True, use_git_ls_files=False))
    assert [rel for _, rel, _, _ in walked] == ["src/large.py"]


def test_strict_walker_emits_alias_and_target_candidates(tmp_path: Path) -> None:
    real = _mk(tmp_path, "src/real.py", "def target():\n    pass\n")
    alias = tmp_path / "src" / "alias.py"
    try:
        alias.symlink_to(real)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    rels = sorted(
        rel for _, rel, _, _ in iter_searchable_files(tmp_path, strict_paths=True, use_git_ls_files=False)
    )
    assert rels == ["src/alias.py", "src/real.py"]
