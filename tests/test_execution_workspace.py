"""C0/C3 real workspace ownership/FS/process tests; not composed service/host acceptance."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import pytest

from fa.execution import workspace
from fa.execution.supervisor import PeerIdentity, SupervisorError
from fa.execution.types import ExecutionContractError, GrantReply, NamespaceRef
from fa.execution.workspace import InputLimits, WorkspaceAuthority
from fa.inner_loop.workflow_artifacts import _replace_private_bytes

PEER = PeerIdentity(os.getpid(), os.getuid(), os.getgid())
ACTOR = NamespaceRef("session-a", "run-a")
OTHER = NamespaceRef("session-b", "run-b")


def until() -> float:
    return time.monotonic() + 10


def ok[T](call: Callable[[], T]) -> T:
    # A closed domain rejection is an observable result, not an infrastructure
    # exception. Unexpected OS/runtime/collection errors remain uncaught.
    observed: T | SupervisorError
    try:
        observed = call()
    except SupervisorError as error:
        observed = error
    assert not isinstance(observed, SupervisorError), f"expected successful domain outcome; observed {observed.code}"
    return observed


@dataclass
class Site:
    state: Path
    roots: Path
    source: Path

    def owner(self, **kwargs: Any) -> WorkspaceAuthority:
        return WorkspaceAuthority(
            self.state,
            approved_roots={"projects": self.roots},
            controller_uids=frozenset({PEER.uid}),
            lock_timeout_ms=25,
            **kwargs,
        )

    def register(
        self, owner: WorkspaceAuthority, relative: str = "project", peer: PeerIdentity = PEER
    ) -> dict[str, str]:
        return owner.register_existing(peer, ACTOR, root_id="projects", relative_root=relative, deadline=until())

    def metadata(self, ids: dict[str, str]) -> dict[str, Any]:
        value = json.loads((self.state / "workspaces" / ids["workspace_id"] / "workspace.json").read_text())
        assert isinstance(value, dict)
        return value

    def revision(self, ids: dict[str, str]) -> Path:
        return self.state / "workspaces" / ids["workspace_id"] / "revisions" / ids["revision_id"]

    def claim(self, owner: WorkspaceAuthority, ids: dict[str, str], actor: NamespaceRef = ACTOR) -> GrantReply:
        return owner.acquire_writer(PEER, actor, workspace_id=ids["workspace_id"], deadline=until())

    def release(
        self, owner: WorkspaceAuthority, ids: dict[str, str], grant: GrantReply, **kwargs: Any
    ) -> dict[str, bool]:
        return owner.release_unused_writer(
            kwargs.get("peer", PEER),
            kwargs.get("actor", ACTOR),
            workspace_id=ids["workspace_id"],
            capability=grant.capability,
            deadline=until(),
        )


@pytest.fixture
def site(tmp_path: Path) -> Site:
    roots = tmp_path / "projects"
    source = roots / "project"
    source.mkdir(parents=True)
    (source / "dirty.txt").write_bytes(b"dirty staged and unstaged\x00binary\xff")
    (source / "untracked.txt").write_text("untracked")
    (source / ".git").mkdir()
    (source / ".git" / "index").write_bytes(b"canonical index sentinel")
    return Site(tmp_path / "protected", roots, source)


def test_registers_real_dirty_r0_and_preserves_index_modes(site: Site) -> None:
    before = (site.source.stat().st_mode, (site.source / ".git/index").read_bytes())
    (site.source / "executable").write_bytes(b"#!/bin/false\n")
    (site.source / "executable").chmod(0o755)
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        tree = json.loads((site.revision(ids) / "tree.json").read_text())
        assert tree["tree_sha256"] == hashlib.sha256(workspace._canonical(tree["entries"])).hexdigest()
        assert {e["path"] for e in tree["entries"]} == {"dirty.txt", "untracked.txt", "executable"}
        assert next(e["mode"] for e in tree["entries"] if e["path"] == "executable") == 0o755
        assert (site.revision(ids) / "data/dirty.txt").read_bytes() == (site.source / "dirty.txt").read_bytes()
        assert site.register(owner) == ids
        assert not (site.revision(ids) / "data/.git").exists()
        assert not (site.revision(ids) / "data/deleted.txt").exists()
        assert site.metadata(ids)["generation"] == 1 and site.metadata(ids)["status"] == "AVAILABLE"
        assert before == (site.source.stat().st_mode, (site.source / ".git/index").read_bytes())
        assert list((site.state / "pending").iterdir()) == []


@pytest.mark.parametrize("name", [".env", ".fa", ".venv", "secrets/key"])
def test_excluded_sources_never_enter_retained_tree(site: Site, name: str) -> None:
    target = site.source / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("not approved")
    with site.owner(excluded_paths=("secrets",)) as owner:
        ids = ok(lambda: site.register(owner))
        assert not (site.revision(ids) / "data" / name).exists()


@pytest.mark.parametrize(
    "kind", ["fifo", "hardlink", "absolute-link", "escape-link", "cycle", "protected-link", "setid"]
)
def test_unsafe_input_rejected_without_registration_or_canonical_cleanup(site: Site, kind: str) -> None:
    target = site.source / "unsafe"
    if kind == "fifo":
        os.mkfifo(target)
    elif kind == "hardlink":
        os.link(site.source / "dirty.txt", target)
    elif kind == "setid":
        target.write_text("unsafe mode")
        target.chmod(0o4755)
    else:
        target.symlink_to(
            {
                "absolute-link": "/etc/passwd",
                "escape-link": "../outside",
                "cycle": "unsafe",
                "protected-link": ".git/index",
            }[kind]
        )
    index = (site.source / ".git/index").read_bytes()
    with site.owner() as owner:
        with pytest.raises(SupervisorError, match="execution_request_rejected") as failure:
            site.register(owner)
        assert failure.value.code == "INPUT_POLICY"
        assert list((site.state / "workspaces").iterdir()) == []
        assert list((site.state / "pending").iterdir()) == []
    assert os.path.lexists(target) and (site.source / ".git/index").read_bytes() == index


def test_safe_relative_link_chain_is_copied_as_data(site: Site) -> None:
    (site.source / "sub").mkdir()
    (site.source / "link").symlink_to("untracked.txt")
    (site.source / "sub/link").symlink_to("../link")
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        assert os.readlink(site.revision(ids) / "data/sub/link") == "../link"
        grant = ok(lambda: site.claim(owner, ids))
        assert grant.generation == 2


@pytest.mark.parametrize(
    "limits",
    [
        InputLimits(max_entries=1),
        InputLimits(max_file_bytes=1),
        InputLimits(max_total_bytes=2),
        InputLimits(max_depth=1),
        InputLimits(max_manifest_bytes=1),
    ],
)
def test_input_limits_leave_no_partial_registered_revision(site: Site, limits: InputLimits) -> None:
    (site.source / "sub").mkdir()
    (site.source / "sub/deep").write_text("deep")
    with site.owner(limits=limits) as owner:
        with pytest.raises(SupervisorError) as failure:
            site.register(owner)
        assert failure.value.code == "INPUT_POLICY"
        assert list((site.state / "workspaces").iterdir()) == []
        assert list((site.state / "pending").iterdir()) == []
    assert (site.source / "sub/deep").read_text() == "deep"


@pytest.mark.parametrize("value", [True, 0, -1, 1.5])
def test_bad_limits_are_not_accepted(value: Any) -> None:
    with pytest.raises(ExecutionContractError):
        InputLimits(max_entries=value)


@pytest.mark.parametrize("relative", ["../project", "/project", ".", "project/.", "project//nested"])
def test_bad_root_selection_does_not_create_canonical_paths(site: Site, relative: str) -> None:
    with site.owner() as owner:
        with pytest.raises(SupervisorError) as failure:
            site.register(owner, relative)
        assert failure.value.code == "PATH_DENIED"
        assert list((site.state / "workspaces").iterdir()) == []


@pytest.mark.parametrize("ancestor_first", [True, False])
def test_nested_registrations_do_not_create_second_workspace_identity(site: Site, ancestor_first: bool) -> None:
    (site.source / "nested").mkdir()
    with site.owner() as owner:
        first = "project" if ancestor_first else "project/nested"
        second = "project/nested" if ancestor_first else "project"
        ids = ok(lambda: site.register(owner, first))
        with pytest.raises(SupervisorError) as failure:
            site.register(owner, second)
        assert failure.value.code == "PATH_DENIED"
        assert [p.name for p in (site.state / "workspaces").iterdir()] == [ids["workspace_id"]]


def test_configured_alias_of_same_root_is_not_new_workspace(site: Site) -> None:
    with WorkspaceAuthority(
        site.state,
        approved_roots={"projects": site.roots, "alias": site.roots},
        controller_uids=frozenset({PEER.uid}),
        lock_timeout_ms=25,
    ) as owner:
        ids = ok(lambda: site.register(owner))
        with pytest.raises(SupervisorError) as failure:
            owner.register_existing(PEER, ACTOR, root_id="alias", relative_root="project", deadline=until())
        assert failure.value.code == "PATH_DENIED" and site.metadata(ids)["generation"] == 1


@pytest.mark.parametrize("approved_root", [True, False])
def test_directory_rebind_is_not_silently_accepted(site: Site, approved_root: bool) -> None:
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        path = site.roots if approved_root else site.source
        path.rename(path.with_name(path.name + "-original"))
        path.mkdir()
        with pytest.raises(SupervisorError) as failure:
            site.claim(owner, ids)
        assert failure.value.code == "CORRUPT_STATE"
        assert site.metadata(ids)["generation"] == 1


def test_two_actor_claims_have_one_durable_grant_and_no_disk_secret(site: Site) -> None:
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))

        def claim(actor: NamespaceRef) -> GrantReply | str:
            try:
                return site.claim(owner, ids, actor)
            except SupervisorError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(claim, [ACTOR, OTHER]))
        grants = [result for result in outcomes if isinstance(result, GrantReply)]
        assert len(grants) == 1 and outcomes.count("WORKSPACE_BUSY") == 1
        grant = grants[0]
        metadata = site.metadata(ids)
        assert grant.generation == metadata["generation"] == 2 and metadata["status"] == "OWNED"
        assert metadata["owner_namespace"] == metadata["active_actor"] and grant.view_ref is None
        assert all(grant.capability.encode() not in p.read_bytes() for p in site.state.rglob("*.json"))
        assert grant.capability not in repr(grant) and grant.capability not in repr(owner)


def test_release_and_reacquire_advance_generation_and_retire_token(site: Site) -> None:
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        first = ok(lambda: site.claim(owner, ids))
        assert ok(lambda: site.release(owner, ids, first)) == {"released": True}
        second = ok(lambda: site.claim(owner, ids))
        assert second.generation == site.metadata(ids)["generation"] == 3
        assert first.capability != second.capability
        with pytest.raises(SupervisorError) as failure:
            site.release(owner, ids, first)
        assert failure.value.code == "UNAUTHORIZED"


@pytest.mark.parametrize("wrong", ["principal", "actor", "token"])
def test_unused_release_is_exact_principal_namespace_and_grant_bound(site: Site, wrong: str) -> None:
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        grant = ok(lambda: site.claim(owner, ids))
        kwargs = (
            {"peer": PeerIdentity(PEER.pid, PEER.uid, PEER.gid + 1)}
            if wrong == "principal"
            else {"actor": OTHER}
            if wrong == "actor"
            else {}
        )
        proof = grant if wrong != "token" else GrantReply(grant.operation, "a" * 64, None, 1, grant.revision_id)
        with pytest.raises(SupervisorError) as failure:
            site.release(owner, ids, proof, **kwargs)
        assert failure.value.code == "UNAUTHORIZED" and site.metadata(ids)["status"] == "OWNED"


@pytest.mark.parametrize("pending", ["view", "intent"])
def test_used_owner_cannot_be_released_by_unused_release_api(site: Site, pending: str) -> None:
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        grant = ok(lambda: site.claim(owner, ids))
        root = site.state / "workspaces" / ids["workspace_id"]
        (root / "views/view-placeholder").mkdir() if pending == "view" else (root / "intent.json").write_text(
            "unfinished"
        )
        with pytest.raises(SupervisorError) as failure:
            site.release(owner, ids, grant)
        assert failure.value.code == "WORKSPACE_BUSY" and site.metadata(ids)["status"] == "OWNED"


def test_restart_quarantines_old_ownership_and_never_renews_grants(site: Site) -> None:
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        grant = ok(lambda: site.claim(owner, ids))
    with site.owner() as recovered:
        assert site.metadata(ids)["status"] == "QUARANTINED"
        assert site.metadata(ids)["generation"] == 2
        with pytest.raises(SupervisorError) as failure:
            site.claim(recovered, ids)
        assert failure.value.code == "WORKSPACE_BUSY"
        with pytest.raises(SupervisorError) as failure:
            site.release(recovered, ids, grant)
        assert failure.value.code == "UNAUTHORIZED"


def test_available_restart_preserves_identity_revision_and_writer_lock_cleanup(site: Site) -> None:
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        assert (site.revision(ids) / "data/dirty.txt").read_bytes() == (site.source / "dirty.txt").read_bytes()
    with site.owner() as owner:
        assert ok(lambda: site.register(owner)) == ids
        grant = ok(lambda: site.claim(owner, ids))
        lock = os.open(site.state / "workspaces" / ids["workspace_id"] / "writer.lock", os.O_RDWR)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            assert ok(lambda: site.release(owner, ids, grant)) == {"released": True}
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(lock)


@pytest.mark.parametrize("change", ["source", "revision", "metadata"])
def test_conflicting_or_corrupt_bytes_cannot_produce_new_writer(site: Site, change: str) -> None:
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        if change == "source":
            (site.source / "untracked.txt").write_text("maintenance mutation")
        elif change == "revision":
            (site.revision(ids) / "data/untracked.txt").write_text("corrupt retention")
        else:
            (site.revision(ids) / "tree.json").write_text('{"schema_version":1,"schema_version":2}')
        with pytest.raises(SupervisorError) as failure:
            site.claim(owner, ids)
        assert failure.value.code == "CORRUPT_STATE" and site.metadata(ids)["generation"] == 1


def test_unknown_peer_or_expired_budget_has_no_registration_effect(site: Site) -> None:
    with site.owner() as owner:
        peer = PeerIdentity(1, PEER.uid + 1, PEER.gid)
        with pytest.raises(SupervisorError) as failure:
            site.register(owner, peer=peer)
        assert failure.value.code == "UNAUTHORIZED"
        with pytest.raises(SupervisorError) as failure:
            owner.register_existing(PEER, ACTOR, root_id="projects", relative_root="project", deadline=0)
        assert failure.value.code == "BACKEND_UNAVAILABLE"
        assert list((site.state / "workspaces").iterdir()) == []


def test_generation_fsync_failure_returns_no_grant_and_fences_owner(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        original = _replace_private_bytes

        def fail(fd: int, name: str, raw: bytes) -> None:
            original(fd, name, raw)
            if name == "workspace.json":
                raise OSError("injected_post_replace_fsync_loss")

        monkeypatch.setattr(workspace, "_replace_private_bytes", fail)
        with pytest.raises(SupervisorError) as failure:
            site.claim(owner, ids)
        assert failure.value.code == "DURABILITY_UNKNOWN"
        monkeypatch.setattr(workspace, "_replace_private_bytes", original)
        with pytest.raises(SupervisorError) as failure:
            site.claim(owner, ids, OTHER)
        assert failure.value.code == "CORRUPT_STATE" and site.metadata(ids)["generation"] == 2


def test_short_writes_are_completed_without_touching_canonical_data(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = os.write

    def short(fd: int, raw: Any) -> int:
        return original(fd, raw[:3])

    with site.owner() as owner:
        with monkeypatch.context() as patch:
            patch.setattr(os, "write", short)
            ids = ok(lambda: site.register(owner))
        assert (site.revision(ids) / "data/dirty.txt").read_bytes() == (site.source / "dirty.txt").read_bytes()


def test_real_process_cannot_own_same_journal_and_authority_root(site: Site) -> None:
    code = """
import json,os,sys
from pathlib import Path, PurePosixPath
from fa.execution.workspace import WorkspaceAuthority
from fa.execution.supervisor import SupervisorError
try:
    owner = WorkspaceAuthority(
        Path(sys.argv[1]), approved_roots={'projects':Path(sys.argv[2])},
        controller_uids=frozenset({os.getuid()}), lock_timeout_ms=25)
    with owner:
        print(json.dumps({'owned':True}))
except SupervisorError as error:
    print(json.dumps({'owned':False,'code':error.code}))
"""
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        child = subprocess.run(
            [sys.executable, "-c", code, str(site.state), str(site.roots)],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        assert json.loads(child.stdout)["owned"] is False and child.stderr == ""
        assert site.metadata(ids)["generation"] == 1


def test_private_tree_parser_does_not_inherit_wire_frame_limit(tmp_path: Path) -> None:
    entry = {
        "path": "x" * 1000,
        "type": "file",
        "mode": 0o600,
        "size": 0,
        "sha256": hashlib.sha256(b"").hexdigest(),
        "deleted": False,
        "link_target": None,
    }
    raw = workspace._canonical(
        {"schema_version": 1, "revision_id": "rev-" + "1" * 32, "tree_sha256": "a" * 64, "entries": [entry] * 5000}
    )
    (tmp_path / "large.json").write_bytes(raw)
    (tmp_path / "large.json").chmod(0o600)
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        assert len(workspace._read_json(fd, "large.json", workspace._TREE, 6 * 1024**2)["entries"]) == 5000
    finally:
        os.close(fd)


@pytest.mark.parametrize("target", ["dir", "file"])
def test_copy_denies_nested_mount_crossing_before_reading_external_data(
    site: Site, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    # Counterfactual kernel-fact injection; actual bind-mount host proof stays live.
    name = site.source / "external"
    if target == "dir":
        name.mkdir()
        (name / "sentinel").write_text("external control data")
    else:
        name.write_text("external control data")
    foreign = {(name.stat().st_dev, name.stat().st_ino)}
    if target == "dir":
        leaf = name / "sentinel"
        foreign.add((leaf.stat().st_dev, leaf.stat().st_ino))
    original = workspace._mount_id

    def changed(fd: int) -> str:
        info = os.fstat(fd)
        return "foreign-mount" if (info.st_dev, info.st_ino) in foreign else original(fd)

    with site.owner() as owner, monkeypatch.context() as patch:
        patch.setattr(workspace, "_mount_id", changed)
        with pytest.raises(SupervisorError) as failure:
            site.register(owner)
        assert failure.value.code == "INPUT_POLICY"
        assert list((site.state / "workspaces").iterdir()) == []


def test_physical_ancestry_blocks_lexically_disjoint_bind_alias(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    (site.roots / "separate").mkdir()
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        original = workspace._location
        source_fd = os.open(site.source, os.O_RDONLY | os.O_DIRECTORY)
        try:
            source_location = original(source_fd, site.source)
        finally:
            os.close(source_fd)

        def alias(fd: int, path: Path) -> tuple[int, PurePosixPath]:
            if path == site.roots / "separate":
                return source_location[0], source_location[1] / "nested"
            return original(fd, path)

        monkeypatch.setattr(workspace, "_location", alias)
        with pytest.raises(SupervisorError) as failure:
            site.register(owner, "separate")
        assert failure.value.code == "PATH_DENIED"
        assert [p.name for p in (site.state / "workspaces").iterdir()] == [ids["workspace_id"]]


@pytest.mark.parametrize("fault", ["copy", "catalog-fsync"])
def test_registration_os_fault_never_grants_or_deletes_canonical_bytes(
    site: Site, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    original = os.fsync
    with site.owner() as owner:
        catalog = site.state / "workspaces"
        identity = (catalog.stat().st_dev, catalog.stat().st_ino)

        def fail(fd: int) -> None:
            info = os.fstat(fd)
            if fault == "copy" and not os.path.isdir(f"/proc/self/fd/{fd}"):
                raise OSError("injected_copy_fsync")
            if fault == "catalog-fsync" and (info.st_dev, info.st_ino) == identity:
                raise OSError("injected_catalog_fsync")
            original(fd)

        with monkeypatch.context() as patch:
            patch.setattr(os, "fsync", fail)
            with pytest.raises(SupervisorError) as failure:
                site.register(owner)
            assert failure.value.code == "DURABILITY_UNKNOWN"
        assert (site.source / "untracked.txt").read_text() == "untracked"
        with pytest.raises(SupervisorError) as failure:
            site.register(owner)
        assert failure.value.code == "CORRUPT_STATE"
        assert len(list(catalog.iterdir())) == (1 if fault == "catalog-fsync" else 0)


@pytest.mark.parametrize(
    "field,value",
    [
        ("generation", True),
        ("schema_version", True),
        ("root_ino", False),
        ("status", "INVALID"),
        ("owner_namespace", ACTOR.to_dict()),
    ],
)
def test_corrupt_workspace_metadata_blocks_startup(site: Site, field: str, value: Any) -> None:
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
    record = site.metadata(ids)
    record[field] = value
    path = site.state / "workspaces" / ids["workspace_id"] / "workspace.json"
    path.write_text(json.dumps(record))
    with pytest.raises(SupervisorError) as failure, site.owner():
        pytest.fail("corrupt protected metadata was accepted")
    assert failure.value.code == "CORRUPT_STATE"


@pytest.mark.parametrize("artifact", ["workspace.json", "current.json", "writer.lock"])
def test_control_artifact_alias_never_modifies_its_destination(site: Site, artifact: str) -> None:
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        path = site.state / "workspaces" / ids["workspace_id"] / artifact
        sentinel = site.source / "untracked.txt"
        if path.exists():
            path.unlink()
        path.symlink_to(sentinel)
        if artifact == "writer.lock":
            with pytest.raises(SupervisorError) as failure:
                site.claim(owner, ids)
            assert failure.value.code == "DURABILITY_UNKNOWN"
        assert sentinel.read_text() == "untracked"
    if artifact != "writer.lock":
        with pytest.raises(SupervisorError), site.owner():
            pytest.fail("aliased protected metadata was accepted")
    assert sentinel.read_text() == "untracked"


def test_shared_writer_flock_blocks_before_generation_claim(site: Site) -> None:
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        path = site.state / "workspaces" / ids["workspace_id"] / "writer.lock"
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with pytest.raises(SupervisorError) as failure:
                site.claim(owner, ids)
            assert failure.value.code == "WORKSPACE_BUSY" and site.metadata(ids)["generation"] == 1
        finally:
            os.close(fd)
        assert ok(lambda: site.claim(owner, ids)).generation == 2


@pytest.mark.parametrize("deadline", [True, float("nan"), float("inf")])
def test_invalid_deadline_is_not_lent_a_new_budget(site: Site, deadline: float) -> None:
    with site.owner() as owner:
        with pytest.raises(ExecutionContractError):
            owner.register_existing(PEER, ACTOR, root_id="projects", relative_root="project", deadline=deadline)
        assert list((site.state / "workspaces").iterdir()) == []


def test_copy_source_mutation_is_not_a_complete_revision(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    with site.owner() as owner:
        original = workspace._Capture._file

        def changed(
            capture: workspace._Capture, source: int, destination: int | None, name: str, expected: os.stat_result
        ) -> dict[str, Any]:
            (site.source / name).write_text("modified during capture")
            return original(capture, source, destination, name, expected)

        monkeypatch.setattr(workspace._Capture, "_file", changed)
        with pytest.raises(SupervisorError) as failure:
            site.register(owner)
        assert failure.value.code in {"INPUT_POLICY", "STALE_REVISION"}
        assert list((site.state / "workspaces").iterdir()) == []


def test_closed_owner_has_no_mutation_rights(site: Site) -> None:
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
    with pytest.raises(SupervisorError) as failure:
        site.claim(owner, ids)
    assert failure.value.code == "CORRUPT_STATE" and site.metadata(ids)["generation"] == 1


def test_real_other_process_writer_lock_blocks_generation_claim(site: Site) -> None:
    code = """
import fcntl,os,sys
fd=os.open(sys.argv[1],os.O_RDWR|os.O_CREAT,0o600)
fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
print('owned',flush=True)
sys.stdin.readline()
os.close(fd)
"""
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        path = site.state / "workspaces" / ids["workspace_id"] / "writer.lock"
        child = subprocess.Popen(
            [sys.executable, "-c", code, str(path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert child.stdout is not None and child.stdout.readline() == "owned\n"
            with pytest.raises(SupervisorError) as failure:
                site.claim(owner, ids)
            assert failure.value.code == "WORKSPACE_BUSY" and site.metadata(ids)["generation"] == 1
        finally:
            stdout, stderr = child.communicate("release\n", timeout=5)
        assert child.returncode == 0 and stdout == stderr == ""
        assert ok(lambda: site.claim(owner, ids)).generation == 2


def test_deadline_expiring_during_generation_durability_cannot_issue_grant(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        original = WorkspaceAuthority._claim_generation
        budget = workspace._budget
        persisted = False

        def claim(binding: workspace._Binding, namespace: NamespaceRef) -> None:
            nonlocal persisted
            original(binding, namespace)
            persisted = True

        def expired(deadline: float) -> None:
            if persisted:
                raise SupervisorError("BACKEND_UNAVAILABLE")
            budget(deadline)

        with monkeypatch.context() as patch:
            patch.setattr(WorkspaceAuthority, "_claim_generation", staticmethod(claim))
            patch.setattr(workspace, "_budget", expired)
            with pytest.raises(SupervisorError) as failure:
                site.claim(owner, ids)
            assert failure.value.code == "BACKEND_UNAVAILABLE" and persisted
        assert site.metadata(ids)["status"] == "OWNED" and site.metadata(ids)["generation"] == 2
        assert owner._bindings[ids["workspace_id"]].grant is None


def test_directory_enumeration_stops_at_entry_limit_before_unbounded_allocation(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    from collections.abc import Iterator
    from contextlib import contextmanager

    original = os.scandir
    source_identity = (site.source.stat().st_dev, site.source.stat().st_ino)
    visited = []

    @contextmanager
    def bounded(fd: int) -> Generator[Iterator[os.DirEntry[str]]]:
        with original(fd) as scan:
            info = os.fstat(fd)
            if (info.st_dev, info.st_ino) != source_identity:
                yield scan
                return

            def entries() -> Iterator[os.DirEntry[str]]:
                for entry in scan:
                    if entry.name != ".git":
                        visited.append(entry.name)
                    yield entry

            yield entries()

    with site.owner(limits=InputLimits(max_entries=1)) as owner:
        with monkeypatch.context() as patch:
            patch.setattr(os, "scandir", bounded)
            with pytest.raises(SupervisorError) as failure:
                site.register(owner)
            assert failure.value.code == "INPUT_POLICY"
        assert len(visited) == 2 and list((site.state / "workspaces").iterdir()) == []


def test_selected_root_cannot_cross_mount_into_private_control_tree(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    identity = (site.source.stat().st_dev, site.source.stat().st_ino)
    original = workspace._mount_id

    def mounted(fd: int) -> str:
        info = os.fstat(fd)
        return "foreign" if (info.st_dev, info.st_ino) == identity else original(fd)

    with site.owner() as owner:
        monkeypatch.setattr(workspace, "_mount_id", mounted)
        with pytest.raises(SupervisorError) as failure:
            site.register(owner)
        assert failure.value.code == "PATH_DENIED" and list((site.state / "workspaces").iterdir()) == []


def test_expired_queued_claim_returns_without_waiting_for_mutex_release(site: Site) -> None:
    import threading

    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        finished = threading.Event()
        outcome = []

        def queued() -> None:
            try:
                result: GrantReply | SupervisorError = owner.acquire_writer(
                    PEER, ACTOR, workspace_id=ids["workspace_id"], deadline=time.monotonic() + 0.05
                )
            except SupervisorError as error:
                result = error
            outcome.append(result)
            finished.set()

        with ThreadPoolExecutor(max_workers=1) as pool:
            owner._mutex.acquire()
            try:
                pending = pool.submit(queued)
                assert finished.wait(1), "expired queued claim waited for authority mutex release"
            finally:
                owner._mutex.release()
            pending.result(2)
        assert len(outcome) == 1 and isinstance(outcome[0], SupervisorError)
        assert outcome[0].code == "BACKEND_UNAVAILABLE" and site.metadata(ids)["generation"] == 1


def test_mount_fact_failure_does_not_leak_the_selected_root_fd(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    identity = (site.source.stat().st_dev, site.source.stat().st_ino)
    original = workspace._mount_id

    def count() -> int:
        matches = 0
        for name in os.listdir("/proc/self/fd"):
            try:
                info = os.fstat(int(name))
            except OSError:
                continue  # The directory enumeration's own already-closed FD.
            matches += (info.st_dev, info.st_ino) == identity
        return matches

    def missing(fd: int) -> str:
        info = os.fstat(fd)
        if (info.st_dev, info.st_ino) == identity:
            raise OSError("injected_fdinfo_failure")
        return original(fd)

    with site.owner() as owner:
        before = count()
        monkeypatch.setattr(workspace, "_mount_id", missing)
        with pytest.raises(SupervisorError) as failure:
            site.register(owner)
        assert failure.value.code == "DURABILITY_UNKNOWN"
        assert count() == before, "selected root FD escaped mount-fact failure cleanup"


@pytest.mark.parametrize("kind", ["filename", "link-target"])
def test_non_utf8_input_has_closed_policy_error_and_no_registered_tree(site: Site, kind: str) -> None:
    if kind == "filename":
        fd = os.open(os.fsencode(site.source) + b"/bad-\xff", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
    else:
        os.symlink(b"target-\xff", os.fsencode(site.source / "bad-link"))
    with site.owner() as owner:
        with pytest.raises(SupervisorError) as failure:
            site.register(owner)
        assert failure.value.code == "INPUT_POLICY"
        assert list((site.state / "workspaces").iterdir()) == []
        assert list((site.state / "pending").iterdir()) == []
    assert (site.source / ".git/index").read_bytes() == b"canonical index sentinel"


def test_valid_unicode_link_target_preserves_exact_utf8_bytes_and_hash(site: Site) -> None:
    target = "данные-ß.txt"
    (site.source / target).write_text("approved UTF8 input")
    (site.source / "link").symlink_to(target)
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        assert os.readlink(site.revision(ids) / "data/link") == target
        manifest = json.loads((site.revision(ids) / "tree.json").read_text())
        entry = next(e for e in manifest["entries"] if e["path"] == "link")
        assert entry["sha256"] == hashlib.sha256(target.encode()).hexdigest()
        assert entry["size"] == len(target.encode())


def legacy_genesis(site: Site, *, generation: int = 0, status: str = "AVAILABLE") -> dict[str, str]:
    """Retain actual R0; encode the prior on-disk epoch, never fabricate a grant."""
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
    metadata = site.metadata(ids)
    metadata.update(generation=generation, status=status)
    if status != "AVAILABLE":
        metadata.update(owner_namespace=ACTOR.to_dict(), active_actor=ACTOR.to_dict())
    fd = os.open(site.state / "workspaces" / ids["workspace_id"], os.O_RDONLY | os.O_DIRECTORY)
    try:
        _replace_private_bytes(fd, "workspace.json", json.dumps(metadata).encode())
    finally:
        os.close(fd)
    return ids


@contextmanager
def admitted_owner(site: Site) -> Generator[WorkspaceAuthority]:
    """Assert a successful closed-domain startup outcome; never catch OS/runtime errors."""
    with ExitStack() as stack:
        owner = ok(lambda: stack.enter_context(site.owner()))
        yield owner


def test_genesis_epoch_is_positive_without_writer_ownership(site: Site) -> None:
    from fa.execution.types import Access, ViewPurpose, ViewRef

    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        metadata = site.metadata(ids)
        assert metadata["generation"] == 1
        assert metadata["status"] == "AVAILABLE"
        assert metadata["owner_namespace"] is metadata["active_actor"] is None
        # Shape compatibility only: this is NOT an issued or authorized pin.
        ref = ViewRef(
            ids["workspace_id"],
            "view-" + "1" * 32,
            ids["revision_id"],
            ACTOR.run_id,
            1,
            Access.READ,
            ViewPurpose.PROJECT,
        )
        assert ref.generation == metadata["generation"]
        with pytest.raises(ExecutionContractError):
            ViewRef(
                ids["workspace_id"],
                "view-" + "1" * 32,
                ids["revision_id"],
                ACTOR.run_id,
                0,
                Access.READ,
                ViewPurpose.PROJECT,
            )
        grant = ok(lambda: site.claim(owner, ids))
        assert grant.generation == 2
        assert site.metadata(ids)["status"] == "OWNED"


def test_legacy_zero_initializes_durably_once_without_ownership_or_data_changes(site: Site) -> None:
    ids = legacy_genesis(site)
    revision = site.revision(ids)
    before = {str(p.relative_to(revision)): p.read_bytes() for p in revision.rglob("*") if p.is_file()}
    assert site.metadata(ids)["generation"] == 0
    with admitted_owner(site):
        assert site.metadata(ids)["generation"] == 1
        assert site.metadata(ids)["status"] == "AVAILABLE"
        assert site.metadata(ids)["owner_namespace"] is site.metadata(ids)["active_actor"] is None
    initialized = site.metadata(ids)
    with admitted_owner(site) as owner:
        assert site.metadata(ids) == initialized
        grant = ok(lambda: site.claim(owner, ids))
        assert grant.generation == 2
    assert {str(p.relative_to(revision)): p.read_bytes() for p in revision.rglob("*") if p.is_file()} == before
    assert (site.source / ".git/index").read_bytes() == b"canonical index sentinel"


@pytest.mark.parametrize("generation", [1, 2, 257])
def test_nonzero_available_epoch_is_never_initialized_or_rewritten(
    site: Site, generation: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = legacy_genesis(site, generation=generation)
    path = site.state / "workspaces" / ids["workspace_id"] / "workspace.json"
    before = path.read_bytes()
    writes: list[str] = []
    original = _replace_private_bytes

    def replace(fd: int, name: str, raw: bytes) -> None:
        writes.append(name)
        original(fd, name, raw)

    monkeypatch.setattr(workspace, "_replace_private_bytes", replace)
    with admitted_owner(site):
        assert path.read_bytes() == before
    assert writes == []


@pytest.mark.parametrize("status", ["OWNED", "QUARANTINED"])
def test_zero_epoch_with_ownership_is_not_initialized_or_renewed(site: Site, status: str) -> None:
    ids = legacy_genesis(site, status=status)
    before = site.metadata(ids)
    with pytest.raises(SupervisorError) as failure, site.owner():
        pass  # Entry must reject; otherwise pytest reports DID NOT RAISE.
    assert failure.value.code == "CORRUPT_STATE"
    assert site.metadata(ids) == before


@pytest.mark.parametrize("blocker", ["view", "intent", "symlink-lock", "hardlink-lock", "mode-lock"])
def test_unsafe_legacy_zero_retention_or_lock_blocks_initialization(site: Site, blocker: str) -> None:
    ids = legacy_genesis(site)
    path = site.state / "workspaces" / ids["workspace_id"]
    if blocker == "view":
        (path / "views" / ("view-" + "1" * 32)).mkdir()
    elif blocker == "intent":
        (path / "intent.json").write_text("unresolved")
    elif blocker == "symlink-lock":
        (path / "writer.lock").symlink_to(site.source / "untracked.txt")
    elif blocker == "hardlink-lock":
        (path / "writer.lock").write_text("lock")
        (path / "writer.lock").chmod(0o600)
        os.link(path / "writer.lock", path / "aliased-lock")
    else:
        (path / "writer.lock").write_text("lock")
        (path / "writer.lock").chmod(0o644)
    with pytest.raises(SupervisorError) as failure, site.owner():
        pass  # Entry must reject; otherwise pytest reports DID NOT RAISE.
    assert failure.value.code == "CORRUPT_STATE"
    assert site.metadata(ids)["generation"] == 0
    assert (site.source / "untracked.txt").read_text() == "untracked"


def test_legacy_zero_competing_native_writer_lock_blocks_initialization(site: Site) -> None:
    ids = legacy_genesis(site)
    fd = os.open(site.state / "workspaces" / ids["workspace_id"] / "writer.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(SupervisorError) as failure, site.owner():
            pass  # Entry must reject; otherwise pytest reports DID NOT RAISE.
        assert failure.value.code == "CORRUPT_STATE"
        assert site.metadata(ids)["generation"] == 0
    finally:
        os.close(fd)
    with admitted_owner(site):
        assert site.metadata(ids)["generation"] == 1


def test_legacy_zero_corrupt_retained_bytes_block_before_epoch_effect(site: Site) -> None:
    ids = legacy_genesis(site)
    (site.revision(ids) / "data/untracked.txt").write_text("tampered retained bytes")
    with pytest.raises(SupervisorError) as failure, site.owner():
        pass  # Entry must reject; otherwise pytest reports DID NOT RAISE.
    assert failure.value.code == "CORRUPT_STATE"
    assert site.metadata(ids)["generation"] == 0


@pytest.mark.parametrize("phase", ["before", "after", "wrong-reread"])
def test_genesis_persistence_fault_never_admits_or_issues_a_grant(
    site: Site, phase: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = legacy_genesis(site)
    original = _replace_private_bytes

    def replace(fd: int, name: str, raw: bytes) -> None:
        if name == "workspace.json":
            if phase == "before":
                raise OSError("injected pre-effect persistence fault")
            if phase == "wrong-reread":
                value = json.loads(raw)
                value["generation"] = 0
                raw = json.dumps(value).encode()
        original(fd, name, raw)
        if name == "workspace.json" and phase == "after":
            raise OSError("injected lost persistence acknowledgement")

    with monkeypatch.context() as patch:
        patch.setattr(workspace, "_replace_private_bytes", replace)
        with pytest.raises(SupervisorError) as failure, site.owner():
            pass  # Entry must reject; otherwise pytest reports DID NOT RAISE.
        assert failure.value.code == "CORRUPT_STATE"
    metadata = site.metadata(ids)
    assert metadata["generation"] == (1 if phase == "after" else 0)
    assert metadata["status"] == "AVAILABLE"
    assert metadata["owner_namespace"] is metadata["active_actor"] is None
    # A separate startup can safely initialize or validate what actually persisted;
    # it does not reconstruct a capability or turn the failed startup into success.
    with admitted_owner(site) as owner:
        assert site.metadata(ids)["generation"] == 1
        assert ok(lambda: site.claim(owner, ids)).generation == 2
