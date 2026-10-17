"""C0/C3 real Linux descriptor/FS tests, not admission, tool/PTY C1 or host acceptance."""

from __future__ import annotations

import errno
import hashlib
import os
import stat
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from fa.execution import view_io
from fa.execution.protocol import MAX_TEXT_BYTES
from fa.execution.view_io import RootedViewIO, ViewIOError, WriteResult


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_reply(io: RootedViewIO, path: str, content: str, *, expected_sha256: str | None) -> WriteResult:
    # Closed domain failures are observable outcomes, not infrastructure failures.
    # Unexpected exceptions still propagate; successful byte/metadata oracles remain below.
    observed: WriteResult | ViewIOError
    try:
        observed = io.write_file(path, content, expected_sha256=expected_sha256)
    except ViewIOError as error:
        observed = error
    assert isinstance(observed, dict), f"expected successful write reply, observed {observed}"
    return observed


@dataclass
class Tree:
    root: Path
    stage: Path
    canonical: Path

    @property
    def uid(self) -> int:
        return os.getuid() or 1000

    @property
    def gid(self) -> int:
        return os.getgid() or 1000

    def put(self, path: str, raw: bytes, mode: int = 0o644) -> Path:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        os.chown(target, self.uid, self.gid)
        target.chmod(mode)
        return target

    def open(
        self,
        *,
        writable: bool = True,
        max_file_bytes: int = 64 * 1024 * 1024,
        max_depth: int = 64,
        protected_paths: tuple[str, ...] = ("plans/active.md",),
        excluded_paths: tuple[str, ...] = ("secrets",),
        uid: int | None = None,
        gid: int | None = None,
    ) -> RootedViewIO:
        root = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        stage = os.open(self.stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            return RootedViewIO(
                root,
                stage,
                uid=self.uid if uid is None else uid,
                gid=self.gid if gid is None else gid,
                writable=writable,
                max_file_bytes=max_file_bytes,
                max_depth=max_depth,
                protected_paths=protected_paths,
                excluded_paths=excluded_paths,
            )
        finally:
            # Each returned object must own duplicates, not these reused FD numbers.
            os.close(root)
            os.close(stage)


@pytest.fixture
def tree(tmp_path: Path) -> Generator[Tree]:
    root, stage, canonical = (tmp_path / p for p in ("view", "private-stage", "canonical"))
    root.mkdir()
    stage.mkdir(mode=0o700)
    canonical.mkdir()
    (canonical / "sentinel").write_bytes(b"user dirty source")
    (canonical / "index").write_bytes(b"staged index bytes")
    fixture = Tree(root, stage, canonical)
    yield fixture
    assert (canonical / "sentinel").read_bytes() == b"user dirty source"
    assert (canonical / "index").read_bytes() == b"staged index bytes"
    assert list(stage.iterdir()) == []


def test_complete_hash_large_file_windows_and_exact_eof(tree: Tree) -> None:
    raw = b"a" * (MAX_TEXT_BYTES + 17) + "éé".encode()
    tree.put("large.txt", raw)
    with tree.open() as io:
        first = io.read_file("large.txt", offset_bytes=0, max_bytes=MAX_TEXT_BYTES)
        tail = io.read_file("large.txt", offset_bytes=MAX_TEXT_BYTES, max_bytes=21)
        assert first == {"content": "a" * MAX_TEXT_BYTES, "sha256": sha(raw), "eof": False}
        assert tail == {"content": "a" * 17 + "éé", "sha256": sha(raw), "eof": True}
        for offset in (len(raw), len(raw) + 100):
            assert io.read_file("large.txt", offset_bytes=offset, max_bytes=1) == {
                "content": "",
                "sha256": sha(raw),
                "eof": True,
            }


def test_empty_file_and_default_complete_file_limit(tree: Tree) -> None:
    target = tree.put("empty", b"")
    with tree.open() as io:
        assert io.read_file("empty", offset_bytes=0, max_bytes=1) == {
            "content": "",
            "sha256": sha(b""),
            "eof": True,
        }
        with target.open("r+b") as stream:
            stream.truncate(64 * 1024 * 1024 + 1)
        with pytest.raises(ViewIOError, match="INPUT_POLICY"):
            io.read_file("empty", offset_bytes=0, max_bytes=1)


@pytest.mark.parametrize("length,allowed", [(16, True), (17, True), (18, False)])
def test_trusted_input_limit_boundary(tree: Tree, length: int, allowed: bool) -> None:
    tree.put("file", b"x" * length)
    with tree.open(max_file_bytes=17) as io:
        if allowed:
            assert io.read_file("file", offset_bytes=0, max_bytes=1)["sha256"] == sha(b"x" * length)
        else:
            with pytest.raises(ViewIOError, match="INPUT_POLICY"):
                io.read_file("file", offset_bytes=0, max_bytes=1)


@pytest.mark.parametrize("raw", [b"ab\xff", b"ab\x00", b"ab\xc3"])
def test_entire_text_is_validated_outside_returned_window(tree: Tree, raw: bytes) -> None:
    tree.put("file", raw)
    with tree.open() as io, pytest.raises(ViewIOError, match="INPUT_POLICY"):
        io.read_file("file", offset_bytes=0, max_bytes=1)


@pytest.mark.parametrize("offset,size", [(0, 1), (1, 1), (1, 2)])
def test_split_utf8_boundary_is_explicit(tree: Tree, offset: int, size: int) -> None:
    tree.put("file", "éz".encode())
    with tree.open() as io:
        assert io.read_file("file", offset_bytes=0, max_bytes=2)["content"] == "é"
        assert io.read_file("file", offset_bytes=2, max_bytes=1)["content"] == "z"
        with pytest.raises(ViewIOError, match="INPUT_POLICY"):
            io.read_file("file", offset_bytes=offset, max_bytes=size)


@pytest.mark.parametrize(
    "offset,size", [(-1, 1), (True, 1), (0, 0), (0, -1), (0, True), (0, MAX_TEXT_BYTES + 1), ("0", 1)]
)
def test_window_argument_validation(tree: Tree, offset: Any, size: Any) -> None:
    tree.put("file", b"a")
    with tree.open() as io, pytest.raises(ViewIOError, match="INVALID_REQUEST"):
        io.read_file("file", offset_bytes=offset, max_bytes=size)


@pytest.mark.parametrize("path", ["", ".", "..", "/etc/passwd", "a/../x", "a//x", "a/./x", "a/", "a\x00b"])
def test_path_shape_denies_read_and_write_without_effects(tree: Tree, path: str) -> None:
    with tree.open() as io:
        with pytest.raises(ViewIOError, match="PATH_DENIED"):
            io.read_file(path, offset_bytes=0, max_bytes=1)
        with pytest.raises(ViewIOError, match="PATH_DENIED"):
            io.write_file(path, "not installed", expected_sha256=None)
    assert list(tree.root.iterdir()) == []


@pytest.mark.parametrize("path", [".git/config", "x/.fa/state", ".env", ".venv/lib", "secrets/token"])
def test_control_and_configured_exclusions(tree: Tree, path: str) -> None:
    target = tree.put(path, b"private")
    with tree.open() as io:
        for method in (
            lambda: io.read_file(path, offset_bytes=0, max_bytes=1),
            lambda: io.write_file(path, "new", expected_sha256=sha(b"private")),
        ):
            with pytest.raises(ViewIOError, match="PATH_DENIED"):
                method()
    assert target.read_bytes() == b"private"


def test_planref_write_and_ancestor_protection_but_read_and_sibling_allowed(tree: Tree) -> None:
    plan = tree.put("plans/active.md", b"admitted plan")
    with tree.open() as io:
        assert io.read_file("plans/active.md", offset_bytes=0, max_bytes=20)["content"] == "admitted plan"
        for path in ("plans/active.md", "plans", "plans/active.md/child"):
            with pytest.raises(ViewIOError, match="PATH_DENIED"):
                io.write_file(path, "bad", expected_sha256=sha(b"admitted plan") if path == "plans/active.md" else None)
        assert write_reply(io, "plans/sibling.md", "ordinary", expected_sha256=None)["bytes"] == 8
    assert plan.read_bytes() == b"admitted plan"


def test_exclusion_ancestor_cannot_be_created_as_regular_file(tree: Tree) -> None:
    with tree.open(excluded_paths=("keys/token",)) as io:
        with pytest.raises(ViewIOError, match="PATH_DENIED"):
            io.write_file("keys", "bad", expected_sha256=None)
        assert write_reply(io, "keys/ordinary", "data", expected_sha256=None)["bytes"] == 4


@pytest.mark.parametrize("kind", ["leaf-symlink", "parent-symlink", "hardlink", "fifo", "directory"])
def test_alias_and_nonregular_targets_denied_without_touching_canonical(tree: Tree, kind: str) -> None:
    path = "alias"
    target = tree.root / path
    if kind == "leaf-symlink":
        target.symlink_to(tree.canonical / "sentinel")
    elif kind == "parent-symlink":
        target.symlink_to(tree.canonical, target_is_directory=True)
        path += "/sentinel"
    elif kind == "hardlink":
        os.link(tree.canonical / "sentinel", target)
    elif kind == "fifo":
        os.mkfifo(target)
    else:
        target.mkdir()
    with tree.open() as io:
        with pytest.raises(ViewIOError, match="PATH_DENIED"):
            io.read_file(path, offset_bytes=0, max_bytes=1)
        with pytest.raises(ViewIOError, match="PATH_DENIED"):
            io.write_file(path, "bad", expected_sha256=sha(b"user dirty source"))


@pytest.mark.parametrize("mode", [0o4644, 0o2644, 0o1644])
def test_special_file_modes_denied(tree: Tree, mode: int) -> None:
    target = tree.put("file", b"old", mode)
    with tree.open() as io:
        with pytest.raises(ViewIOError, match="PATH_DENIED"):
            io.read_file("file", offset_bytes=0, max_bytes=10)
        with pytest.raises(ViewIOError, match="PATH_DENIED"):
            io.write_file("file", "new", expected_sha256=sha(b"old"))
    assert target.read_bytes() == b"old"


def test_write_replace_and_create_preserve_cell_metadata_and_existing_parents(tree: Tree) -> None:
    target = tree.put("kept/file", b"old", 0o640)
    parent = target.parent
    parent.chmod(0o700)
    before = parent.stat()
    with tree.open() as io:
        assert write_reply(io, "kept/file", "énew", expected_sha256=sha(b"old")) == {
            "sha256": sha("énew".encode()),
            "bytes": 5,
        }
        assert io.read_file("kept/file", offset_bytes=0, max_bytes=10)["content"] == "énew"
        assert write_reply(io, "new/sub/file", "created", expected_sha256=None) == {
            "sha256": sha(b"created"),
            "bytes": 7,
        }
    assert stat.S_IMODE(parent.stat().st_mode) == stat.S_IMODE(before.st_mode) == 0o700
    assert (parent.stat().st_uid, parent.stat().st_gid) == (before.st_uid, before.st_gid)
    for path, mode in (
        (target, 0o640),
        (tree.root / "new", 0o755),
        (tree.root / "new/sub", 0o755),
        (tree.root / "new/sub/file", 0o644),
    ):
        info = path.stat()
        assert stat.S_IMODE(info.st_mode) == mode
        assert (info.st_uid, info.st_gid) == (tree.uid, tree.gid)
    assert target.read_bytes() == "énew".encode()


@pytest.mark.parametrize("expected", [None, "0" * 64])
def test_expected_absence_and_sha_conflict_preserve_existing_file(tree: Tree, expected: str | None) -> None:
    target = tree.put("file", b"old", 0o640)
    before = target.stat()
    with tree.open() as io, pytest.raises(ViewIOError, match="STALE_REVISION"):
        io.write_file("file", "bad", expected_sha256=expected)
    assert target.read_bytes() == b"old"
    # Reading may update atime on the deployment filesystem; it is not a write conflict.
    after = target.stat()
    for field in (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_nlink",
        "st_uid",
        "st_gid",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    ):
        assert getattr(after, field) == getattr(before, field)


def test_expected_existing_file_missing_does_not_create_parents(tree: Tree) -> None:
    with tree.open() as io, pytest.raises(ViewIOError, match="STALE_REVISION"):
        io.write_file("missing/sub/file", "bad", expected_sha256=sha(b"old"))
    assert list(tree.root.iterdir()) == []


@pytest.mark.parametrize("field", ["uid", "gid"])
def test_wrong_existing_owner_is_not_privileged_replacement(tree: Tree, field: str) -> None:
    target = tree.put("file", b"old")
    with tree.open(uid=tree.uid + (field == "uid"), gid=tree.gid + (field == "gid")) as io:
        with pytest.raises(ViewIOError, match="PATH_DENIED"):
            io.write_file("file", "bad", expected_sha256=sha(b"old"))
    assert target.read_bytes() == b"old"


def test_readonly_denies_before_any_directory_or_file_creation(tree: Tree) -> None:
    tree.put("file", b"readable")
    with tree.open(writable=False) as io:
        assert io.read_file("file", offset_bytes=0, max_bytes=20)["content"] == "readable"
        with pytest.raises(ViewIOError, match="PATH_DENIED"):
            io.write_file("new/sub/file", "bad", expected_sha256=None)
    assert not (tree.root / "new").exists()


@pytest.mark.parametrize(
    "content,expected",
    [("x", "bad"), ("x", True), ("\ud800", None), ("a\x00b", None), ("é" * (MAX_TEXT_BYTES // 2 + 1), None)],
    ids=["invalid-sha", "invalid-sha-type", "surrogate", "nul", "utf8-byte-cap"],
)
def test_invalid_write_payload_is_rejected_before_effects(tree: Tree, content: str, expected: Any) -> None:
    with tree.open() as io, pytest.raises(ViewIOError, match="INVALID_REQUEST"):
        io.write_file("new/file", content, expected_sha256=expected)
    assert list(tree.root.iterdir()) == []


def test_write_exact_byte_cap_empty_content_and_trusted_smaller_limit(tree: Tree) -> None:
    content = "é" * (MAX_TEXT_BYTES // 2)
    with tree.open() as io:
        assert write_reply(io, "cap", content, expected_sha256=None) == {
            "sha256": sha(content.encode()),
            "bytes": MAX_TEXT_BYTES,
        }
        assert write_reply(io, "empty", "", expected_sha256=None) == {"sha256": sha(b""), "bytes": 0}
    with tree.open(max_file_bytes=2) as io, pytest.raises(ViewIOError, match="INPUT_POLICY"):
        io.write_file("new/file", "abc", expected_sha256=None)
    assert not (tree.root / "new").exists()


def test_depth_and_path_utf8_byte_limits(tree: Tree) -> None:
    with tree.open(max_depth=2) as io:
        assert write_reply(io, "one/file", "ok", expected_sha256=None)["bytes"] == 2
        for path in ("a/b/c", "é" * (MAX_TEXT_BYTES // 2 + 1)):
            with pytest.raises(ViewIOError, match="INPUT_POLICY"):
                io.write_file(path, "bad", expected_sha256=None)


def test_duplicate_descriptor_lifetime_and_close_are_explicit(tree: Tree) -> None:
    tree.put("file", b"pinned")
    before = len(list(Path("/proc/self/fd").iterdir()))
    io = tree.open()
    moved = tree.root.with_name("moved")
    tree.root.rename(moved)
    tree.root.mkdir()
    tree.put("file", b"new binding")
    # FD pinning only: the real authority must independently reject root rebind.
    assert io.read_file("file", offset_bytes=0, max_bytes=20)["content"] == "pinned"
    io.close()
    io.close()
    with pytest.raises(ViewIOError, match="VIEW_CLOSED"):
        io.read_file("file", offset_bytes=0, max_bytes=1)
    with pytest.raises(ViewIOError, match="VIEW_CLOSED"):
        io.write_file("file", "bad", expected_sha256=None)
    assert len(list(Path("/proc/self/fd").iterdir())) == before


@pytest.mark.parametrize("problem", ["stage-mode", "stage-in-source", "stage-equals-source", "root-file"])
def test_invalid_descriptor_layout_fails_without_fd_leaks(tree: Tree, problem: str) -> None:
    root_path, stage_path = tree.root, tree.stage
    if problem == "stage-mode":
        tree.stage.chmod(0o755)
    elif problem == "stage-in-source":
        stage_path = tree.root / "stage"
        stage_path.mkdir(mode=0o700)
    elif problem == "stage-equals-source":
        tree.root.chmod(0o700)
        stage_path = tree.root
    else:
        root_path = tree.put("file", b"regular")
    root, stage = os.open(root_path, os.O_RDONLY), os.open(stage_path, os.O_RDONLY)
    before = len(list(Path("/proc/self/fd").iterdir()))
    try:
        with pytest.raises(ViewIOError, match="INPUT_POLICY"):
            RootedViewIO(root, stage, uid=tree.uid, gid=tree.gid, writable=True, protected_paths=(), excluded_paths=())
        assert len(list(Path("/proc/self/fd").iterdir())) == before
    finally:
        os.close(root)
        os.close(stage)


def test_stale_parent_replacement_before_publication_is_not_followed(
    tree: Tree, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = tree.put("dir/file", b"old")
    original_stage = RootedViewIO._stage_file

    @contextmanager
    def substitute(self: RootedViewIO, raw: bytes, mode: int) -> Generator[Any]:
        with original_stage(self, raw, mode) as staged:
            original.parent.rename(tree.root / "detached")
            tree.put("dir/file", b"replacement")
            yield staged

    monkeypatch.setattr(RootedViewIO, "_stage_file", substitute)
    with tree.open() as io, pytest.raises(ViewIOError, match="STALE_REVISION"):
        io.write_file("dir/file", "bad", expected_sha256=sha(b"old"))
    assert (tree.root / "detached/file").read_bytes() == b"old"
    assert original.read_bytes() == b"replacement"


def test_same_bytes_leaf_replacement_still_conflicts(tree: Tree, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tree.put("file", b"same")
    original_stage = RootedViewIO._stage_file

    @contextmanager
    def substitute(self: RootedViewIO, raw: bytes, mode: int) -> Generator[Any]:
        with original_stage(self, raw, mode) as staged:
            replacement = tree.put("other", b"same")
            os.replace(replacement, target)
            yield staged

    monkeypatch.setattr(RootedViewIO, "_stage_file", substitute)
    with tree.open() as io, pytest.raises(ViewIOError, match="STALE_REVISION"):
        io.write_file("file", "bad", expected_sha256=sha(b"same"))
    assert target.read_bytes() == b"same"


def test_leaf_create_race_is_no_clobber_not_overwrite(tree: Tree, monkeypatch: pytest.MonkeyPatch) -> None:
    original = os.link

    def race(*args: Any, **kwargs: Any) -> None:
        tree.put("file", b"racing writer")
        original(*args, **kwargs)

    monkeypatch.setattr(os, "link", race)
    with tree.open() as io, pytest.raises(ViewIOError, match="STALE_REVISION"):
        io.write_file("file", "bad", expected_sha256=None)
    assert (tree.root / "file").read_bytes() == b"racing writer"


def test_parent_create_race_preserves_existing_directory_mode(tree: Tree, monkeypatch: pytest.MonkeyPatch) -> None:
    original = view_io._rename_directory

    def race(source: int, name: str, destination: int, leaf: str) -> None:
        (tree.root / leaf).mkdir(mode=0o700)
        original(source, name, destination, leaf)

    monkeypatch.setattr(view_io, "_rename_directory", race)
    with tree.open() as io:
        assert write_reply(io, "dir/file", "ok", expected_sha256=None)["bytes"] == 2
    assert stat.S_IMODE((tree.root / "dir").stat().st_mode) == 0o700


def test_short_writes_are_completed(tree: Tree, monkeypatch: pytest.MonkeyPatch) -> None:
    original = os.write
    calls = []

    def short(fd: int, raw: Any) -> int:
        calls.append(len(raw))
        return original(fd, raw[:3])

    monkeypatch.setattr(os, "write", short)
    with tree.open() as io:
        assert write_reply(io, "file", "abcdefghij", expected_sha256=None)["sha256"] == sha(b"abcdefghij")
    assert (tree.root / "file").read_bytes() == b"abcdefghij"
    assert calls == [10, 7, 4, 1]


def test_zero_write_is_failure_with_no_project_effects(tree: Tree, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "write", lambda fd, raw: 0)
    with tree.open() as io, pytest.raises(ViewIOError, match="BACKEND_UNAVAILABLE"):
        io.write_file("file", "data", expected_sha256=None)
    assert list(tree.root.iterdir()) == []


@pytest.mark.parametrize("phase", ["staged-file", "staging-directory", "target-directory", "new-parent"])
def test_fsync_faults_distinguish_before_effect_and_possible_effect(
    tree: Tree, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    target = tree.put("file", b"old")
    original = os.fsync
    destination = tree.root.stat().st_ino
    staging = tree.stage.stat().st_ino

    def fault(fd: int) -> None:
        info = os.fstat(fd)
        if (
            (phase == "staged-file" and stat.S_ISREG(info.st_mode))
            or (phase == "staging-directory" and info.st_ino == staging)
            or (phase in {"target-directory", "new-parent"} and info.st_ino == destination)
        ):
            raise OSError(errno.EIO, "injected fsync")
        original(fd)

    monkeypatch.setattr(os, "fsync", fault)
    code = "BACKEND_UNAVAILABLE" if phase == "staged-file" else "DURABILITY_UNKNOWN"
    with tree.open() as io, pytest.raises(ViewIOError, match=code):
        if phase == "new-parent":
            io.write_file("new/file", "new", expected_sha256=None)
        else:
            io.write_file("file", "new", expected_sha256=sha(b"old"))
    assert target.read_bytes() == (b"old" if phase in {"staged-file", "new-parent"} else b"new")
    if phase == "new-parent":
        assert (tree.root / "new").is_dir()
        assert not (tree.root / "new/file").exists()


@pytest.mark.parametrize("phase", ["leaf", "parent"])
def test_ambiguous_publish_error_preserves_unknown_not_cleanup_error(
    tree: Tree, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    if phase == "leaf":
        original = os.replace
        tree.put("file", b"old")

        def replaced(*args: Any, **kwargs: Any) -> None:
            original(*args, **kwargs)
            raise OSError(errno.EIO, "ambiguous publish")

        monkeypatch.setattr(os, "replace", replaced)
    else:
        original_parent = view_io._rename_directory

        def parent_replaced(*args: Any, **kwargs: Any) -> None:
            original_parent(*args, **kwargs)
            raise OSError(errno.EIO, "ambiguous publish")

        monkeypatch.setattr(view_io, "_rename_directory", parent_replaced)
    with tree.open() as io, pytest.raises(ViewIOError, match="DURABILITY_UNKNOWN"):
        io.write_file(
            "file" if phase == "leaf" else "new/file", "new", expected_sha256=sha(b"old") if phase == "leaf" else None
        )
    if phase == "leaf":
        assert (tree.root / "file").read_bytes() == b"new"
    else:
        assert (tree.root / "new").is_dir()
        assert not (tree.root / "new/file").exists()


def test_post_publication_modification_is_unknown_and_not_rolled_back(
    tree: Tree, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tree.put("file", b"old")
    original = os.replace

    def race(*args: Any, **kwargs: Any) -> None:
        original(*args, **kwargs)
        target.write_bytes(b"shell after publish")

    monkeypatch.setattr(os, "replace", race)
    with tree.open() as io, pytest.raises(ViewIOError, match="DURABILITY_UNKNOWN"):
        io.write_file("file", "new", expected_sha256=sha(b"old"))
    assert target.read_bytes() == b"shell after publish"


def test_read_changes_during_capture_are_stale(tree: Tree, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tree.put("file", b"original")
    original = os.read
    changed = False

    def race(fd: int, size: int) -> bytes:
        nonlocal changed
        data = original(fd, size)
        if not changed:
            changed = True
            target.write_bytes(b"different")
        return data

    monkeypatch.setattr(os, "read", race)
    with tree.open() as io, pytest.raises(ViewIOError, match="STALE_REVISION"):
        io.read_file("file", offset_bytes=0, max_bytes=2)
    assert target.read_bytes() == b"different"


def test_read_leaf_unlinked_during_capture_is_stale(tree: Tree, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tree.put("file", b"original")
    original = os.read
    changed = False

    def race(fd: int, size: int) -> bytes:
        nonlocal changed
        data = original(fd, size)
        if not changed:
            changed = True
            target.unlink()
        return data

    monkeypatch.setattr(os, "read", race)
    with tree.open() as io, pytest.raises(ViewIOError, match="STALE_REVISION"):
        io.read_file("file", offset_bytes=0, max_bytes=2)


def test_growth_during_capture_respects_complete_file_bound(tree: Tree, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tree.put("file", b"a")
    original = os.read
    changed = False

    def race(fd: int, size: int) -> bytes:
        nonlocal changed
        data = original(fd, size)
        if not changed:
            changed = True
            target.write_bytes(b"b" * 30)
        return data

    monkeypatch.setattr(os, "read", race)
    with tree.open(max_file_bytes=17) as io, pytest.raises(ViewIOError, match="INPUT_POLICY"):
        io.read_file("file", offset_bytes=0, max_bytes=1)


def test_post_capture_parent_substitution_blocks_read_data(tree: Tree, monkeypatch: pytest.MonkeyPatch) -> None:
    tree.put("dir/file", b"captured")
    original = RootedViewIO._snapshot

    def race(self: RootedViewIO, parent: int, leaf: str) -> view_io._Snapshot:
        captured = original(self, parent, leaf)
        (tree.root / "dir").rename(tree.root / "detached")
        tree.put("dir/file", b"substitute")
        return captured

    monkeypatch.setattr(RootedViewIO, "_snapshot", race)
    with tree.open() as io, pytest.raises(ViewIOError, match="STALE_REVISION"):
        io.read_file("dir/file", offset_bytes=0, max_bytes=1)


def test_last_post_publish_parent_check_is_required(tree: Tree, monkeypatch: pytest.MonkeyPatch) -> None:
    tree.put("dir/file", b"old")
    original = RootedViewIO._snapshot

    def race(self: RootedViewIO, parent: int, leaf: str) -> view_io._Snapshot:
        captured = original(self, parent, leaf)
        if captured.raw == b"new":
            (tree.root / "dir").rename(tree.root / "detached")
            tree.put("dir/file", b"substitute")
        return captured

    monkeypatch.setattr(RootedViewIO, "_snapshot", race)
    with tree.open() as io, pytest.raises(ViewIOError, match="DURABILITY_UNKNOWN"):
        io.write_file("dir/file", "new", expected_sha256=sha(b"old"))
    assert (tree.root / "detached/file").is_file()
    assert (tree.root / "dir/file").is_file()
    assert (tree.root / "detached/file").read_bytes() == b"new"
    assert (tree.root / "dir/file").read_bytes() == b"substitute"


def test_missing_noreplace_primitive_has_no_fallback(tree: Tree, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(view_io, "_RENAME_NOREPLACE", None)
    with tree.open() as io, pytest.raises(ViewIOError, match="BACKEND_UNAVAILABLE"):
        io.write_file("new/file", "bad", expected_sha256=None)
    assert list(tree.root.iterdir()) == []


def test_partial_constructor_failure_closes_duplicate_fd(tree: Tree) -> None:
    root = os.open(tree.root, os.O_RDONLY | os.O_DIRECTORY)
    before = len(list(Path("/proc/self/fd").iterdir()))
    try:
        with pytest.raises(ViewIOError, match="BACKEND_UNAVAILABLE"):
            RootedViewIO(root, -1, uid=tree.uid, gid=tree.gid, writable=True, protected_paths=(), excluded_paths=())
        assert len(list(Path("/proc/self/fd").iterdir())) == before
    finally:
        os.close(root)


@pytest.mark.parametrize("problem", ["device", "owner"])
def test_stage_filesystem_and_service_owner_checks(tree: Tree, monkeypatch: pytest.MonkeyPatch, problem: str) -> None:
    original = os.fstat
    inode = tree.stage.stat().st_ino

    def mismatch(fd: int) -> os.stat_result:
        metadata = original(fd)
        if metadata.st_ino == inode:
            values = list(metadata)
            index = 2 if problem == "device" else 4
            values[index] += 1
            return os.stat_result(values)
        return metadata

    monkeypatch.setattr(os, "fstat", mismatch)
    with pytest.raises(ViewIOError, match="INPUT_POLICY"):
        tree.open()


@pytest.mark.parametrize("field", ["uid", "gid"])
@pytest.mark.parametrize("value", [0, -1, True, 2**32 - 1, 2**32])
def test_native_owner_bounds_are_rejected_before_effects(tree: Tree, field: str, value: int) -> None:
    before = len(list(Path("/proc/self/fd").iterdir()))
    kwargs: dict[str, Any] = {field: value}
    with pytest.raises(ViewIOError, match="INVALID_REQUEST"):
        handle = tree.open(**kwargs)
        handle.close()
    assert list(tree.root.iterdir()) == []
    assert len(list(Path("/proc/self/fd").iterdir())) == before
