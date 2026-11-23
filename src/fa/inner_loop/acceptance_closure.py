"""Sealed acceptance-closure inventory (STEP9A / Q-V2-ACC-1).

What the verifier may execute must be a closed, digestible set of bytes plus one
closed run configuration. The workspace ``pyproject.toml`` is coder-editable, so
it can never decide how an acceptance oracle runs: this module validates a sealed
``pytest.ini`` inside the closure and emits the harness-built argv that pins
``-c``/``--rootdir`` and disables the cache provider.

This module is inventory and policy only. It performs no I/O outside the given
acceptance root, writes nothing, and never raises outside its closed error type.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import stat
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "ACCEPTANCE_INI",
    "MAX_ACCEPTANCE_BYTES",
    "MAX_ACCEPTANCE_DEPTH",
    "MAX_ACCEPTANCE_FILES",
    "MAX_ACCEPTANCE_FILE_BYTES",
    "MAX_ACCEPTANCE_PATH_CHARS",
    "NODEID_PLUGIN",
    "AcceptanceClosure",
    "AcceptanceClosureError",
    "ClosureFile",
    "closure_digest",
    "collect_acceptance_closure",
    "parse_pytest_ini",
    "pytest_argv",
    "read_closure_payload",
    "shell_command",
    "validate_pytest_ini",
]

#: The one run configuration that belongs to the sealed bytes.
ACCEPTANCE_INI = "pytest.ini"
#: The nodeid adapter is installed image code, never planner or coder content.
NODEID_PLUGIN = "fa.inner_loop.junit_nodeid_plugin"

#: Budgets (Q-V2-ACC-1). Per-file mirrors the renderer's 4 MiB text bound; the
#: aggregate is 4x that; paths and depth reuse the authority's existing limits.
MAX_ACCEPTANCE_FILES = 512
MAX_ACCEPTANCE_ENTRIES = 4096  # The authority inventory uses the same subtree bound.
MAX_ACCEPTANCE_FILE_BYTES = 4 * 1024**2
MAX_ACCEPTANCE_BYTES = 16 * 1024**2
MAX_ACCEPTANCE_PATH_CHARS = 4096
MAX_ACCEPTANCE_DEPTH = 64
_SEALED_FILE_MODE = 0o644

#: ``pytest.ini`` keys a planner may set. Anything else is refused, so no
#: plugin, rootdir, ini and basetemp override can ride in through the file.
_ALLOWED_INI_KEYS = frozenset(
    {
        "python_files",
        "python_functions",
        "testpaths",
        "markers",
        "xfail_strict",
        "addopts",
        "filterwarnings",
    }
)
#: ``addopts`` tokens that keep the run quiet and strict but cannot redirect it.
_ALLOWED_ADDOPTS_EXACT = frozenset({"-q", "-x", "-ra", "-rf", "-rE", "--strict-markers", "--strict-config"})
_ALLOWED_ADDOPTS_PREFIXES = ("--tb=", "--durations=", "--maxfail=", "-r")


class AcceptanceClosureError(ValueError):
    """Closed diagnostic reason; never expose input paths or exception bodies."""

    def __init__(self, rule: str) -> None:
        self.rule = rule
        super().__init__(f"invalid acceptance closure: {rule}")


@dataclass(frozen=True, slots=True)
class ClosureFile:
    """One sealed file: acceptance-root-relative path, digest, size, fixed mode."""

    path: str
    sha256: str
    size: int
    mode: int


@dataclass(frozen=True, slots=True)
class AcceptanceClosure:
    """The complete inventory plus its canonical digest."""

    files: tuple[ClosureFile, ...]
    total_bytes: int
    digest: str


def _canonical(entries: Iterable[tuple[str, str]]) -> bytes:
    return json.dumps(sorted(entries), separators=(",", ":"), ensure_ascii=True).encode("ascii")


def closure_digest(entries: Iterable[tuple[str, str]]) -> str:
    """Digest the ordered set of ``(path, sha256)`` pairs, never the bytes again."""
    return hashlib.sha256(_canonical(entries)).hexdigest()


def _parts(path: str) -> tuple[str, ...]:
    if not isinstance(path, str) or not path or "\x00" in path or "\\" in path:
        raise AcceptanceClosureError("path-invalid")
    if len(path) > MAX_ACCEPTANCE_PATH_CHARS:
        raise AcceptanceClosureError("path-too-long")
    parts = tuple(part for part in path.split("/") if part)
    if not parts:
        raise AcceptanceClosureError("path-invalid")
    if any(part in {"", ".", ".."} for part in parts):
        raise AcceptanceClosureError("path-invalid")
    if any(part.startswith(".") for part in parts):
        raise AcceptanceClosureError("path-hidden-component")
    if len(parts) > MAX_ACCEPTANCE_DEPTH:
        raise AcceptanceClosureError("path-too-deep")
    return parts


def _validate_entry_name(relative: str, *, is_dir: bool) -> None:
    parts = _parts(relative)
    if not is_dir and parts[-1] == "conftest.py" and len(parts) > 1:
        # One sealed root conftest only: a nested conftest changes fixture
        # resolution for a subtree without appearing in the root's own bytes.
        raise AcceptanceClosureError("nested-conftest")
    if any(part == ACCEPTANCE_INI for part in parts[:-1]):
        raise AcceptanceClosureError("path-invalid")


def _read_regular_file(directory_fd: int, name: str, *, remaining_bytes: int) -> bytes:
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    try:
        fd = os.open(name, flags, dir_fd=directory_fd)
    except OSError:
        raise AcceptanceClosureError("unreadable-file") from None
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or metadata.st_uid != os.getuid():
            raise AcceptanceClosureError("unreadable-file")
        chunks: list[bytes] = []
        remaining = metadata.st_size
        if remaining > MAX_ACCEPTANCE_FILE_BYTES:
            raise AcceptanceClosureError("file-too-large")
        if remaining > remaining_bytes:
            raise AcceptanceClosureError("closure-too-large")
        while remaining:
            chunk = os.read(fd, min(remaining, 1024**2))
            if not chunk:
                raise AcceptanceClosureError("unreadable-file")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)
    except OSError:
        raise AcceptanceClosureError("unreadable-file") from None
    finally:
        os.close(fd)


def _walk(root: Path, *, directories: list[str] | None = None) -> list[tuple[str, bytes]]:
    """Collect ``(relative path, bytes)`` from a real directory tree, safely."""
    collected: list[tuple[str, bytes]] = []
    entry_count = 0
    total_bytes = 0
    try:
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        raise AcceptanceClosureError("root-unreadable") from None

    def _descend(directory_fd: int, prefix: str, depth: int) -> None:
        nonlocal entry_count, total_bytes
        if depth > MAX_ACCEPTANCE_DEPTH:
            raise AcceptanceClosureError("path-too-deep")
        try:
            names: list[str] = []
            with os.scandir(directory_fd) as scan:
                for entry in scan:
                    entry_count += 1
                    if entry_count > MAX_ACCEPTANCE_ENTRIES:
                        raise AcceptanceClosureError("too-many-entries")
                    names.append(entry.name)
            names.sort()
        except OSError:
            raise AcceptanceClosureError("root-unreadable") from None
        for name in names:
            relative = f"{prefix}/{name}" if prefix else name
            try:
                metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            except OSError:
                raise AcceptanceClosureError("unreadable-file") from None
            if stat.S_ISLNK(metadata.st_mode):
                raise AcceptanceClosureError("symlink-refused")
            if stat.S_ISDIR(metadata.st_mode):
                _validate_entry_name(relative, is_dir=True)
                if directories is not None:
                    directories.append(relative)
                try:
                    child = os.open(
                        name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory_fd
                    )
                except OSError:
                    raise AcceptanceClosureError("unreadable-file") from None
                try:
                    _descend(child, relative, depth + 1)
                finally:
                    os.close(child)
                continue
            if not stat.S_ISREG(metadata.st_mode):
                raise AcceptanceClosureError("unreadable-file")
            _validate_entry_name(relative, is_dir=False)
            if len(collected) >= MAX_ACCEPTANCE_FILES:
                raise AcceptanceClosureError("too-many-files")
            raw = _read_regular_file(directory_fd, name, remaining_bytes=MAX_ACCEPTANCE_BYTES - total_bytes)
            total_bytes += len(raw)
            collected.append((relative, raw))

    try:
        _descend(root_fd, "", 1)
    finally:
        os.close(root_fd)
    return collected


def collect_acceptance_inventory(root: Path) -> list[dict[str, object]]:
    """Walk complete host closure membership, including empty directories."""
    if not isinstance(root, Path):
        raise AcceptanceClosureError("root-invalid")
    directories: list[str] = []
    files = _walk(root, directories=directories)
    entries: list[dict[str, object]] = [
        {"path": path, "type": "directory", "size": 0, "sha256": None} for path in directories
    ]
    entries.extend(
        {"path": path, "type": "file", "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        for path, raw in files
    )
    entries.sort(key=lambda entry: str(entry["path"]))
    return entries


def collect_acceptance_closure(root: Path) -> AcceptanceClosure:
    """Inventory ``root`` as one sealed closure, or refuse with a closed rule."""
    if not isinstance(root, Path):
        raise AcceptanceClosureError("root-invalid")
    entries = _walk(root)
    if not entries:
        raise AcceptanceClosureError("empty-closure")
    if ACCEPTANCE_INI not in {path for path, _ in entries}:
        raise AcceptanceClosureError("missing-pytest-ini")
    total = 0
    files: list[ClosureFile] = []
    pairs: list[tuple[str, str]] = []
    for path, raw in sorted(entries, key=lambda item: item[0]):
        total += len(raw)
        if total > MAX_ACCEPTANCE_BYTES:
            raise AcceptanceClosureError("closure-too-large")
        digest = hashlib.sha256(raw).hexdigest()
        files.append(ClosureFile(path=path, sha256=digest, size=len(raw), mode=_SEALED_FILE_MODE))
        pairs.append((path, digest))
    ini_bytes = next(raw for path, raw in entries if path == ACCEPTANCE_INI)
    try:
        validate_pytest_ini(ini_bytes.decode("utf-8"))
    except UnicodeError:
        raise AcceptanceClosureError("pytest-ini-invalid") from None
    return AcceptanceClosure(files=tuple(files), total_bytes=total, digest=closure_digest(pairs))


def read_closure_payload(root: Path, closure: AcceptanceClosure) -> dict[str, bytes]:
    """Re-read ``root`` and prove it is still exactly ``closure``.

    This is the one reader the seal uses for the payload it hands to the
    authority: the record decides what the bytes must be, so a tree that gained,
    lost or changed a file never produces a payload.
    """
    if not isinstance(root, Path) or not isinstance(closure, AcceptanceClosure):
        raise AcceptanceClosureError("root-invalid")
    entries = dict(_walk(root))
    expected = {entry.path: entry.sha256 for entry in closure.files}
    missing = sorted(set(expected) - set(entries))
    if missing:
        raise AcceptanceClosureError("closure-missing-bytes")
    extra = sorted(set(entries) - set(expected))
    if extra:
        raise AcceptanceClosureError("closure-extra-bytes")
    for path, sha256 in expected.items():
        if hashlib.sha256(entries[path]).hexdigest() != sha256:
            raise AcceptanceClosureError("closure-drift")
    return entries


def parse_pytest_ini(text: str) -> Mapping[str, str]:
    """Parse the sealed ini strictly: one ``[pytest]`` section, flat ``key = value``."""
    if not isinstance(text, str) or "\x00" in text:
        raise AcceptanceClosureError("pytest-ini-invalid")
    section: str | None = None
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            if name != "pytest" or section is not None:
                raise AcceptanceClosureError("pytest-ini-invalid")
            section = name
            continue
        if section is None or "=" not in line:
            raise AcceptanceClosureError("pytest-ini-invalid")
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in values:
            raise AcceptanceClosureError("pytest-ini-invalid")
        values[key] = value.strip()
    if section is None:
        raise AcceptanceClosureError("pytest-ini-invalid")
    return values


def _validate_addopts(value: str) -> None:
    try:
        tokens = shlex.split(value)
    except ValueError:
        raise AcceptanceClosureError("pytest-ini-unsafe-addopts") from None
    for token in tokens:
        if token in _ALLOWED_ADDOPTS_EXACT:
            continue
        if token.startswith(_ALLOWED_ADDOPTS_PREFIXES):
            continue
        # Everything else — `-p`, `-c`, `-o`, `--rootdir`, `--basetemp`,
        # `--confcutdir`, `-n`, paths and unknown flags — is refused.
        raise AcceptanceClosureError("pytest-ini-unsafe-addopts")


def validate_pytest_ini(text: str) -> None:
    """Refuse any sealed ini that could redirect discovery, plugins or rootdir."""
    values = parse_pytest_ini(text)
    unknown = sorted(set(values) - _ALLOWED_INI_KEYS)
    if unknown:
        raise AcceptanceClosureError("pytest-ini-unknown-key")
    for key, value in values.items():
        if key == "addopts":
            _validate_addopts(value)
        elif key == "testpaths":
            for token in shlex.split(value):
                _parts(token)
        elif key == "markers":
            if not value.strip():
                raise AcceptanceClosureError("pytest-ini-invalid")


def pytest_argv(
    *,
    tests: Sequence[str],
    ini: str,
    rootdir: str,
    report: str,
) -> tuple[str, ...]:
    """The harness-built invocation: sealed config, sealed rootdir, no cache."""
    targets = tuple(tests)
    if not targets:
        raise AcceptanceClosureError("pytest-no-targets")
    for target in (*targets, ini, rootdir):
        _parts(target)
    if not report or "\x00" in report:
        raise AcceptanceClosureError("pytest-report-invalid")
    return (
        "python",
        "-m",
        "pytest",
        *targets,
        "-c",
        ini,
        "--rootdir",
        rootdir,
        "-p",
        NODEID_PLUGIN,
        "-p",
        "no:cacheprovider",
        f"--junitxml={report}",
        "-q",
    )


def shell_command(argv: Sequence[str]) -> str:
    """One shell-safe string for the existing string-based runners."""
    if not argv:
        raise AcceptanceClosureError("pytest-no-targets")
    return shlex.join(tuple(argv))
