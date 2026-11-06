"""Safe file iterator for memory-layer indexes (FTS, structural).

§I-S14b-4: Single source of truth for enumerating indexable files. Both
``fa.memory.search_index.SearchIndex`` and
``fa.memory.structural_index.StructuralIndex`` (S16) use this helper so
exclude-dirs, symlink containment, size-caps, and .gitignore handling stay
in lockstep.

Design (v2.1 G-2, G-4, G-6, G-10):

* **Fast path:** ``git ls-files --cached --others --exclude-standard``
  respects ``.gitignore`` out of the box — build artifacts, ``*.egg-info``,
  ``htmlcov/``, ``.mypy_cache/`` etc. are pruned by git itself without
  bloating our EXCLUDE_DIRS set.
* **Fallback:** raw ``os.walk`` with in-place dir prune, used when the
  workspace is not a git repo or the subprocess fails (timeout, missing
  git, permission error). Fail-degraded (BLE001 pattern): log WARNING and
  keep going — indexes are best-effort.
* **Symlink safety (INV-S14b-1):** every yielded path is
  ``fp.resolve().is_relative_to(root_resolved)``. A symlink to
  ``/etc/passwd`` or anywhere outside workspace root is silently skipped.
* **Size cap:** files larger than ``max_file_size`` bytes are skipped
  (prevents indexing giant minified bundles / generated artifacts).
* **Tests filter:** when ``include_tests=False``, files whose relpath
  starts with ``tests/`` or whose path contains ``/tests/`` are skipped.

This module imports only stdlib + ``fa.memory.fts_index.EXCLUDE_DIRS`` to
avoid circular imports with higher layers.
"""

from __future__ import annotations

import fnmatch
import logging
import os
import shutil
import stat
import subprocess
from collections import deque
from collections.abc import Iterator
from pathlib import Path
from typing import Self

from fa.memory.fts_index import EXCLUDE_DIRS as _BASE_EXCLUDE_DIRS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exclude configuration (v2.1 G-4, G-10)
# ---------------------------------------------------------------------------

#: Directory basenames excluded IN ADDITION to fts_index.EXCLUDE_DIRS.
#: Keep small; prefer .gitignore coverage whenever possible.
EXTRA_EXCLUDE_DIRS: frozenset[str] = frozenset(
    {
        ".tox",
        ".pytest_cache",
        ".ruff_cache",
        ".nox",
        "htmlcov",
    }
)

#: Basename glob patterns for directories/files to exclude. Applied via
#: ``fnmatch.fnmatch(basename, pat)`` against each path component. Covers
#: cases like ``first_agent.egg-info/`` that can't be enumerated as a
#: literal basename.
EXCLUDE_DIR_GLOBS: frozenset[str] = frozenset(
    {
        "*.egg-info",
        "*.egg",
    }
)


class RootedReadError(OSError):
    """A source file could not be read without leaving its pinned root."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class RootedFileReader:
    """Read a regular, single-link file beneath a pinned directory descriptor.

    Symlink targets are expanded component-by-component and accepted only when
    they remain beneath the pinned root. Every opened component is descriptor-
    relative with ``O_NOFOLLOW``; links, directories and the final file are
    identity-checked around the bounded, double-captured read.
    """

    _CHUNK_BYTES = 64 * 1024

    def __init__(self, root: Path) -> None:
        if not isinstance(root, Path):
            raise RootedReadError("invalid_root")
        required_flags = ("O_NOFOLLOW", "O_DIRECTORY", "O_CLOEXEC")
        if (
            any(not hasattr(os, name) for name in required_flags)
            or not hasattr(os, "supports_dir_fd")
            or os.open not in os.supports_dir_fd
            or not hasattr(os, "supports_follow_symlinks")
            or os.stat not in os.supports_follow_symlinks
            or os.readlink not in os.supports_dir_fd
        ):
            raise RootedReadError("descriptor_nofollow_unavailable")
        resolved = root.resolve(strict=True)
        before = resolved.stat(follow_symlinks=False)
        if not stat.S_ISDIR(before.st_mode):
            raise RootedReadError("root_not_directory")
        self.root = resolved
        self._root_fd = self._open_directory_chain(resolved)
        try:
            opened = os.fstat(self._root_fd)
            if (
                not stat.S_ISDIR(opened.st_mode)
                or (opened.st_dev, opened.st_ino, opened.st_mode) != (before.st_dev, before.st_ino, before.st_mode)
            ):
                raise RootedReadError("root_changed")
            self._root_identity = (opened.st_dev, opened.st_ino)
            self._root_device = opened.st_dev
            self._assert_root_identity()
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _identity(info: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
        return (
            info.st_dev,
            info.st_ino,
            info.st_mode,
            info.st_nlink,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        )

    @staticmethod
    def _open_directory_chain(root: Path) -> int:
        """Open an absolute path one no-follow directory component at a time."""
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        current = os.open(os.sep, flags)
        try:
            for component in root.parts[1:]:
                if component in ("", ".", ".."):
                    raise RootedReadError("invalid_root")
                child = os.open(component, flags, dir_fd=current)
                previous = current
                current = child
                os.close(previous)
            return current
        except BaseException:
            os.close(current)
            raise

    def _assert_root_identity(self) -> None:
        try:
            current = self.root.stat(follow_symlinks=False)
            opened = os.fstat(self._root_fd)
        except OSError as exc:
            raise RootedReadError("root_changed") from exc
        if (
            not stat.S_ISDIR(current.st_mode)
            or (current.st_dev, current.st_ino) != self._root_identity
            or (opened.st_dev, opened.st_ino) != self._root_identity
        ):
            raise RootedReadError("root_changed")

    @staticmethod
    def _relative_parts(rel: str) -> tuple[str, ...]:
        if not isinstance(rel, str) or not rel or rel.startswith("/") or "\x00" in rel:
            raise RootedReadError("invalid_path")
        parts = tuple(rel.split("/"))
        if any(part in ("", ".", "..") for part in parts):
            raise RootedReadError("invalid_path")
        return parts

    @staticmethod
    def _node_identity(info: os.stat_result) -> tuple[int, int, int]:
        return (info.st_dev, info.st_ino, info.st_mode)

    def _symlink_target_parts(self, target: str) -> tuple[bool, tuple[str, ...]]:
        if target.startswith(os.sep):
            target_parts = Path(target).parts
            root_parts = self.root.parts
            if target_parts[: len(root_parts)] != root_parts:
                raise RootedReadError("symlink_escape")
            return True, target_parts[len(root_parts) :]
        return False, tuple(part for part in target.split(os.sep) if part not in ("", "."))

    def _read_link_target(
        self,
        name: str,
        parent_fd: int,
        parent_index: int,
        named: os.stat_result,
        verified: list[tuple[int, str, tuple[int, ...], str | None]],
    ) -> tuple[bool, tuple[str, ...]]:
        try:
            target = os.readlink(name, dir_fd=parent_fd)
            after_link = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except OSError as exc:
            raise RootedReadError("path_changed") from exc
        if self._identity(named) != self._identity(after_link):
            raise RootedReadError("path_changed")
        verified.append((parent_index, name, self._identity(named), target))
        return self._symlink_target_parts(target)

    def _open_directory_component(
        self, name: str, parent_fd: int, named: os.stat_result
    ) -> int:
        try:
            child_fd = os.open(
                name,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent_fd,
            )
        except OSError as exc:
            raise RootedReadError("path_changed") from exc
        try:
            child_stat = os.fstat(child_fd)
            if (
                self._node_identity(named) != self._node_identity(child_stat)
                or child_stat.st_dev != self._root_device
            ):
                raise RootedReadError("path_changed")
            return child_fd
        except BaseException:
            os.close(child_fd)
            raise

    def _open_regular_component(
        self, name: str, parent_fd: int, named: os.stat_result
    ) -> tuple[int, os.stat_result]:
        try:
            file_fd = os.open(
                name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | getattr(os, "O_NONBLOCK", 0),
                dir_fd=parent_fd,
            )
        except OSError as exc:
            raise RootedReadError("path_changed") from exc
        try:
            opened = os.fstat(file_fd)
            if self._node_identity(named) != self._node_identity(opened):
                raise RootedReadError("path_changed")
            if not stat.S_ISREG(opened.st_mode) or opened.st_dev != self._root_device:
                raise RootedReadError("not_regular_file")
            if opened.st_nlink != 1:
                raise RootedReadError("hardlinked_file")
            return file_fd, opened
        except BaseException:
            os.close(file_fd)
            raise

    def _open_relative_file(
        self, parts: tuple[str, ...]
    ) -> tuple[int, list[int], list[tuple[int, str, tuple[int, ...], str | None]], str, os.stat_result]:
        """Resolve safe symlinks and open the final file without path-based authority."""
        directory_fds = [os.dup(self._root_fd)]
        active = [0]
        resolved: list[str] = []
        verified: list[tuple[int, str, tuple[int, ...], str | None]] = []
        pending = deque(parts)
        file_fd = -1
        symlink_count = 0
        try:
            while pending:
                component = pending.popleft()
                if component in ("", "."):
                    continue
                if component == "..":
                    if len(active) == 1:
                        raise RootedReadError("symlink_escape")
                    active.pop()
                    resolved.pop()
                    continue

                parent_index = active[-1]
                parent_fd = directory_fds[parent_index]
                try:
                    named = os.stat(component, dir_fd=parent_fd, follow_symlinks=False)
                except OSError as exc:
                    raise RootedReadError("path_changed") from exc
                if stat.S_ISLNK(named.st_mode):
                    symlink_count += 1
                    if symlink_count > 40:
                        raise RootedReadError("symlink_loop")
                    absolute, target_parts = self._read_link_target(
                        component, parent_fd, parent_index, named, verified
                    )
                    if absolute:
                        active = [0]
                        resolved.clear()
                    pending.extendleft(reversed(target_parts))
                    continue
                if pending:
                    if not stat.S_ISDIR(named.st_mode):
                        raise RootedReadError("not_directory")
                    child_fd = self._open_directory_component(component, parent_fd, named)
                    verified.append((parent_index, component, self._node_identity(named), None))
                    directory_fds.append(child_fd)
                    active.append(len(directory_fds) - 1)
                    resolved.append(component)
                    continue

                file_fd, opened = self._open_regular_component(component, parent_fd, named)
                verified.append((parent_index, component, self._identity(named), None))
                canonical_rel = "/".join((*resolved, component))
                return file_fd, directory_fds, verified, canonical_rel, opened

            raise RootedReadError("not_regular_file")
        except BaseException:
            if file_fd >= 0:
                os.close(file_fd)
            for directory_fd in reversed(directory_fds):
                os.close(directory_fd)
            raise

    def read_bytes_with_path(self, rel: str, *, max_bytes: int) -> tuple[str, bytes]:
        """Read a stable bounded file and return its canonical root-relative path."""
        if type(max_bytes) is not int or max_bytes < 0:
            raise RootedReadError("invalid_limit")
        parts = self._relative_parts(rel)
        self._assert_root_identity()
        file_fd = -1
        directory_fds: list[int] = []
        try:
            file_fd, directory_fds, verified, canonical_rel, before = self._open_relative_file(parts)
            if before.st_size > max_bytes:
                raise RootedReadError("file_too_large")

            first = self._read_pass(file_fd, max_bytes)
            os.lseek(file_fd, 0, os.SEEK_SET)
            second = self._read_pass(file_fd, max_bytes)
            if first != second:
                raise RootedReadError("file_changed")

            after = os.fstat(file_fd)
            if self._identity(before) != self._identity(after) or len(first) != after.st_size:
                raise RootedReadError("file_changed")
            for parent_index, name, expected, link_target in verified:
                parent_fd = directory_fds[parent_index]
                named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                current = self._identity(named) if len(expected) > 3 else self._node_identity(named)
                if current != expected:
                    raise RootedReadError("path_changed")
                if link_target is not None and os.readlink(name, dir_fd=parent_fd) != link_target:
                    raise RootedReadError("path_changed")
            self._assert_root_identity()
            return canonical_rel, first
        except RootedReadError:
            raise
        except (OSError, ValueError) as exc:
            raise RootedReadError("path_refused") from exc
        finally:
            if file_fd >= 0:
                os.close(file_fd)
            for directory_fd in reversed(directory_fds):
                os.close(directory_fd)

    def read_bytes(self, rel: str, *, max_bytes: int) -> bytes:
        """Read a stable bounded file beneath the pinned root."""
        return self.read_bytes_with_path(rel, max_bytes=max_bytes)[1]

    def _read_pass(self, fd: int, max_bytes: int) -> bytes:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, min(self._CHUNK_BYTES, max_bytes - total + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise RootedReadError("file_too_large")
            chunks.append(chunk)
        return b"".join(chunks)

    def close(self) -> None:
        fd = getattr(self, "_root_fd", -1)
        if fd >= 0:
            self._root_fd = -1
            os.close(fd)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


#: Default file-extension patterns (matches globs in fts_index.py:115 area).
DEFAULT_PATTERNS: tuple[str, ...] = (
    "*.py",
    "*.md",
    "*.txt",
    "*.rst",
    "*.json",
    "*.yaml",
    "*.yml",
    "*.toml",
    "*.ini",
    "*.cfg",
    "*.html",
    "*.css",
    "*.js",
    "*.ts",
    "*.tsx",
    "*.jsx",
    "*.sh",
)


def _path_is_excluded(
    rel_parts: tuple[str, ...],
    extra_exclude: frozenset[str] | None = None,
) -> bool:
    """Return True if any path component matches an exclude rule.

    ``extra_exclude`` is a frozenset of additional directory basenames
    supplied by the caller (union with base excludes). This function is
    invoked for *every* git-ls-files result and for defense-in-depth in
    the os.walk path; it must stay O(depth * patterns).
    """
    effective: set[str] = set(_BASE_EXCLUDE_DIRS) | set(EXTRA_EXCLUDE_DIRS)
    if extra_exclude:
        effective = effective | set(extra_exclude)
    for part in rel_parts:
        if part in effective:
            return True
        for pat in EXCLUDE_DIR_GLOBS:
            if fnmatch.fnmatch(part, pat):
                return True
        # Dot-dirs (other than "."/"..") are pruned by os.walk already;
        # defense-in-depth for the git-ls-files path (which can return
        # dotfiles if force-added).
        if part.startswith(".") and part not in (".", "..") and part in effective:
            return True
    return False


def _matches_any_pattern(rel: str, basename: str, patterns: tuple[str, ...]) -> bool:
    """Return True if relpath or basename matches any fnmatch pattern."""
    for pat in patterns:
        if fnmatch.fnmatch(basename, pat) or fnmatch.fnmatch(rel, pat):
            return True
    return False


def _git_ls_files(root: Path, timeout: float = 5.0) -> list[str] | None:
    """Return list of relpaths from git, or None on any failure.

    Resolves ``git`` to an absolute path via ``shutil.which`` to satisfy
    bandit S607 (no partial-executable-path subprocess invocation).
    Uses ``--cached --others --exclude-standard`` which is the same flag
    set used by ``glob.py``'s ``git_ls_files`` helper in the existing
    codebase (cross-checked in preflight).
    """
    # A root with no ``.git`` cannot be enumerated by git (a managed view never
    # carries one: ``.git`` is excluded from projections). Skip the subprocess
    # instead of paying a guaranteed exit-128 plus a WARNING on every walk —
    # this is also what keeps a managed search free of host Git invocations.
    if not (root / ".git").exists():
        logger.debug("no .git under %s; using os.walk", root)
        return None
    git_bin = shutil.which("git")
    if git_bin is None:
        logger.debug("git binary not found on PATH; using os.walk fallback")
        return None
    try:
        res = subprocess.run(  # noqa: S603 - argv list, git_bin resolved via shutil.which
            [
                git_bin,
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if res.returncode != 0:
            logger.warning(
                "git ls-files exited %d: %s; falling back to os.walk",
                res.returncode,
                res.stderr.strip()[:200],
            )
            return None
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("git ls-files failed (%s); falling back to os.walk", exc)
        return None


def _walk_fallback(
    root_resolved: Path,
    patterns: tuple[str, ...],
    effective_exclude: set[str],
    max_file_size: int,
    *,
    strict_paths: bool = False,
) -> Iterator[tuple[Path, str, float, int]]:
    """os.walk-based fallback when git is unavailable.

    Legacy callers receive resolved, contained paths with symlink escapes and
    duplicate targets filtered here. ``strict_paths`` callers receive lexical
    candidate names only; their rooted reader owns containment, symlink
    resolution, identity checks and refusal behavior.
    """
    seen_resolved: set[Path] = set()
    for dirpath, dirnames, filenames in os.walk(root_resolved, followlinks=False):
        # In-place prune (critical — mutates dirnames to prevent descent).
        dirnames[:] = [
            d
            for d in dirnames
            if d not in effective_exclude
            and not d.startswith(".")
            and not any(fnmatch.fnmatch(d, g) for g in EXCLUDE_DIR_GLOBS)
        ]
        dp = Path(dirpath)
        for fname in filenames:
            fp = dp / fname
            try:
                rel = str(fp.relative_to(root_resolved))
                if not _matches_any_pattern(rel, fname, patterns):
                    continue
                if strict_paths:
                    # The name is only a candidate. RootedFileReader resolves
                    # symlinks, enforces type/size limits and reads fail-closed.
                    yield (fp, rel, 0.0, 0)
                    continue
                resolved = fp.resolve()
                if not resolved.is_relative_to(root_resolved):
                    continue
                if resolved in seen_resolved:
                    continue
                # Legacy callers retain their resolved-path behavior. Managed
                # callers opt into strict_paths and never consume this Path.
                st = resolved.stat()
                if not resolved.is_file():
                    continue
                if max_file_size > 0 and st.st_size > max_file_size:
                    continue
                seen_resolved.add(resolved)
                yield (resolved, rel, st.st_mtime, st.st_size)
            except (OSError, ValueError) as exc:
                logger.warning("skipping %s during walk: %s", fp, exc)
                continue


def _iter_git_searchable_files(
    root: Path,
    files: list[str],
    patterns: tuple[str, ...],
    *,
    extra_exclude_dirs: frozenset[str] | None,
    include_tests: bool,
    max_file_size: int,
    strict_paths: bool,
) -> Iterator[tuple[Path, str, float, int]]:
    """Filter git's relative-path inventory, leaving strict reads to the caller."""
    for rel in files:
        rel_norm = rel.replace("\\", "/")
        parts = tuple(rel_norm.split("/"))
        if not rel_norm or rel_norm.startswith("/") or any(part in ("", ".", "..") for part in parts):
            continue
        if _path_is_excluded(parts, extra_exclude=extra_exclude_dirs):
            continue
        if not include_tests and "tests" in parts:
            continue
        fname = parts[-1] if parts else ""
        if not _matches_any_pattern(rel_norm, fname, patterns):
            continue
        fp = root / rel_norm
        try:
            if strict_paths:
                # Git supplies only candidate names; rooted open is authoritative.
                yield (fp, rel_norm, 0.0, 0)
                continue
            resolved = fp.resolve()
            if not resolved.is_relative_to(root) or not resolved.is_file():
                continue
            st = resolved.stat()
            if max_file_size > 0 and st.st_size > max_file_size:
                continue
            yield (resolved, rel_norm, st.st_mtime, st.st_size)
        except (OSError, ValueError) as exc:
            logger.warning("skipping %s from git ls-files: %s", fp, exc)


def iter_searchable_files(
    root: Path,
    patterns: tuple[str, ...] = DEFAULT_PATTERNS,
    *,
    extra_exclude_dirs: frozenset[str] | None = None,
    include_tests: bool = True,
    max_file_size: int = 200_000,
    use_git_ls_files: bool = True,
    strict_paths: bool = False,
) -> Iterator[tuple[Path, str, float, int]]:
    """Yield ``(absolute_path, relpath_str, st_mtime, st_size)`` for files
    that pass every filter.

    Parameters
    ----------
    root:
        Workspace root (resolved by the caller OR resolved here — both
        work; we always resolve internally for the is_relative_to check).
    patterns:
        fnmatch patterns for filenames/relpaths to include.
    extra_exclude_dirs:
        Additional directory basenames to exclude (union with
        ``_BASE_EXCLUDE_DIRS | EXTRA_EXCLUDE_DIRS``).
    include_tests:
        If False, any path whose relpath contains a ``tests`` directory
        component (or starts with ``tests/``) is skipped.
    max_file_size:
        Soft cap in bytes; files larger than this are skipped. ``0`` or
        negative means unlimited.
    use_git_ls_files:
        If True (default), tries ``git ls-files`` fast path first.
    strict_paths:
        If True, enumerate lexical source-name candidates without treating
        discovery metadata as authority. Consumers must read the returned
        relative path through ``RootedFileReader``; unsafe candidates refuse.
    """
    root_resolved = root.resolve()
    if not root_resolved.is_dir():
        raise NotADirectoryError(f"workspace root is not a directory: {root_resolved}")

    effective_exclude: set[str] = set(_BASE_EXCLUDE_DIRS) | set(EXTRA_EXCLUDE_DIRS)
    if extra_exclude_dirs:
        effective_exclude = effective_exclude | set(extra_exclude_dirs)
    if not include_tests:
        effective_exclude.add("tests")

    # --- Fast path: git ls-files -------------------------------------------
    files_from_git: list[str] | None = None
    if use_git_ls_files:
        files_from_git = _git_ls_files(root_resolved)

    if files_from_git is not None:
        yield from _iter_git_searchable_files(
            root_resolved,
            files_from_git,
            patterns,
            extra_exclude_dirs=extra_exclude_dirs,
            include_tests=include_tests,
            max_file_size=max_file_size,
            strict_paths=strict_paths,
        )
        return

    # --- Fallback: os.walk -------------------------------------------------
    yield from _walk_fallback(
        root_resolved,
        patterns,
        effective_exclude,
        max_file_size,
        strict_paths=strict_paths,
    )


__all__ = [
    "DEFAULT_PATTERNS",
    "EXCLUDE_DIR_GLOBS",
    "EXTRA_EXCLUDE_DIRS",
    "RootedFileReader",
    "RootedReadError",
    "iter_searchable_files",
]
