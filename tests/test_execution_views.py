"""C0/C3 actual PROJECT view ownership/FS IO; not tool/PTY/service C1 or terminality."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from fa.execution import workspace
from fa.execution.profiles import ExecutionProfile
from fa.execution.protocol import encode_json
from fa.execution.supervisor import SupervisorError
from fa.execution.types import Access, GrantReply, ViewPurpose
from fa.execution.view_io import _DIRECTORY, RootedViewIO, WriteResult
from fa.execution.workspace import WorkspaceAuthority
from fa.inner_loop.plan_admission import read_plan_snapshot
from fa.inner_loop.workflow_artifacts import _private_artifact_directory, _replace_private_bytes
from tests.test_execution_dispatch import profile
from tests.test_execution_readers import pin, read, record_path, ref
from tests.test_execution_workspace import ACTOR, OTHER, PEER, Site, ok, until
from tests.test_execution_workspace import site as site


def native_profile() -> ExecutionProfile:
    # Native C0 creation must really reach chown/rename. No deployed approval claim.
    return replace(profile(), uid=os.getuid() or 1000, gid=os.getgid() or 1000)


def create(owner: WorkspaceAuthority, ids: dict[str, str], lease: GrantReply, **kwargs: Any) -> GrantReply:
    grant = owner.create_view(
        kwargs.get("peer", PEER),
        kwargs.get("namespace", ACTOR),
        workspace_id=ids["workspace_id"],
        capability=kwargs.get("capability", lease.capability),
        purpose=kwargs.get("purpose", ViewPurpose.PROJECT),
        access=kwargs.get("access", Access.WRITE),
        candidate_scope=kwargs.get("candidate_scope"),
        plan_ref=kwargs.get("plan_ref"),
        formal_evidence=kwargs.get("formal", False),
        deadline=kwargs.get("deadline", until()),
    )
    # Producer proof BEFORE any consumers: no missing-file/runtime mutation credit.
    root = owner._state / "workspaces" / ref(grant).workspace_id / "views" / ref(grant).view_id
    assert (root / "view.json").is_file(), "grant before durable view installation"
    assert json.loads((root / "view.json").read_text())["view_ref"] == ref(grant).to_dict()
    assert (root / "source/untracked.txt").is_file(), "grant without actual input materialization"
    assert (root / "source/untracked.txt").read_bytes() == b"untracked"
    return grant


def source(site: Site, grant: GrantReply) -> Path:
    return record_path(site, grant).parent / "source"


def write(owner: WorkspaceAuthority, grant: GrantReply, **kwargs: Any) -> WriteResult:
    return owner.write_file(
        kwargs.get("peer", PEER),
        kwargs.get("namespace", ACTOR),
        view_ref=kwargs.get("view_ref", ref(grant)),
        capability=kwargs.get("capability", grant.capability),
        path=kwargs.get("path", "untracked.txt"),
        content=kwargs.get("content", "changed"),
        expected_sha256=kwargs.get("sha", hashlib.sha256(b"untracked").hexdigest()),
        deadline=kwargs.get("deadline", until()),
    )


def test_materialized_dirty_bytes_logical_modes_cell_ownership_and_nonsecret_retention(site: Site) -> None:
    (site.source / "bin").mkdir(mode=0o750)
    (site.source / "bin/script").write_bytes(b"#!/bin/false\n")
    (site.source / "bin/script").chmod(0o751)
    (site.source / "link").symlink_to("bin/script")
    (site.source / ".env").write_text("excluded secret")
    before = (site.source.stat(), (site.source / "bin").stat(), (site.source / ".git/index").read_bytes())
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = ok(lambda: create(owner, ids, lease))
        root = source(site, grant)
        assert ref(grant).access is Access.WRITE and ref(grant).purpose is ViewPurpose.PROJECT
        assert ref(grant).generation == lease.generation and grant.capability != lease.capability
        assert (root / "dirty.txt").read_bytes() == (site.source / "dirty.txt").read_bytes()
        assert (root / "bin/script").read_bytes() == b"#!/bin/false\n"
        assert (root / "bin/script").stat().st_mode & 0o777 == 0o751
        assert (root / "bin").stat().st_mode & 0o777 == 0o750
        assert os.readlink(root / "link") == "bin/script"
        assert (root / "bin/script").stat().st_ino != (site.revision(ids) / "data/bin/script").stat().st_ino
        for item in [root, root.parent / "scratch", root / "bin", root / "bin/script"]:
            assert (item.stat().st_uid, item.stat().st_gid) == (native_profile().uid, native_profile().gid)
        assert not (root / ".git").exists() and not (root / ".env").exists()
        assert (root.parent / "scratch").stat().st_mode & 0o777 == 0o755
        raw = record_path(site, grant).read_text()
        record = json.loads(raw)
        assert lease.capability not in raw and grant.capability not in raw
        assert record["plan_ref"] is record["candidate_scope"] is record["sealed_manifest_id"] is None
        assert record["operation_ids"] == [] and record["state"] == "OPEN"
        assert record["input_tree_sha256"] == json.loads((site.revision(ids) / "tree.json").read_text())["tree_sha256"]
        assert list((site.state / "pending").iterdir()) == []
    assert before == (site.source.stat(), (site.source / "bin").stat(), (site.source / ".git/index").read_bytes())


def test_actual_rooted_write_read_your_writes_external_private_edit_and_old_reader_bytes(site: Site) -> None:
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        old = ok(lambda: pin(owner, ids))
        lease = ok(lambda: site.claim(owner, ids))
        grant = ok(lambda: create(owner, ids, lease))
        result = ok(lambda: write(owner, grant))
        # Authoritative bytes FIRST, before mirrors/read consumers.
        assert (source(site, grant) / "untracked.txt").read_bytes() == b"changed"
        assert result == {"sha256": hashlib.sha256(b"changed").hexdigest(), "bytes": 7}
        assert ok(lambda: read(owner, grant))["content"] == "changed"
        (source(site, grant) / "untracked.txt").write_text("external private-tree edit")
        assert ok(lambda: read(owner, grant))["content"] == "external private-tree edit"
        assert ok(lambda: read(owner, old))["content"] == "untracked"
        assert (site.source / "untracked.txt").read_text() == "untracked"
        assert (site.revision(ids) / "data/untracked.txt").read_text() == "untracked"
        with pytest.raises(SupervisorError) as failure:
            site.release(owner, ids, lease)
        assert failure.value.code == "WORKSPACE_BUSY"


@pytest.mark.parametrize(
    "kind", ["principal", "namespace", "token", "owner-token", "ref-purpose", "ref-access", "ref-run"]
)
def test_view_proof_denies_reads_and_writes_before_effects(site: Site, kind: str) -> None:
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = ok(lambda: create(owner, ids, lease))
        args: dict[str, Any] = {}
        if kind == "principal":
            args["peer"] = replace(PEER, gid=PEER.gid + 1)
        elif kind == "namespace":
            args["namespace"] = OTHER
        elif kind == "token":
            args["capability"] = "f" * 64
        elif kind == "owner-token":
            args["capability"] = lease.capability
        elif kind == "ref-purpose":
            args["view_ref"] = replace(ref(grant), purpose=ViewPurpose.PROVISIONING)
        elif kind == "ref-access":
            args["view_ref"] = replace(ref(grant), access=Access.READ)
        else:
            args["view_ref"] = replace(ref(grant), owner_run_id="other-run")
        with pytest.raises(SupervisorError) as failure:
            write(owner, grant, **args)
        assert failure.value.code == "UNAUTHORIZED"
        with pytest.raises(SupervisorError) as failure:
            read(owner, grant, **args)
        assert failure.value.code == "UNAUTHORIZED"
        assert (source(site, grant) / "untracked.txt").read_text() == "untracked"


@pytest.mark.parametrize("kind", ["principal", "namespace", "token", "reader-token"])
def test_owner_creation_proof_before_any_materialization(site: Site, kind: str) -> None:
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        reader = ok(lambda: pin(owner, ids))
        lease = ok(lambda: site.claim(owner, ids))
        args: dict[str, Any] = {}
        if kind == "principal":
            args["peer"] = replace(PEER, gid=PEER.gid + 1)
        elif kind == "namespace":
            args["namespace"] = OTHER
        else:
            args["capability"] = reader.capability if kind == "reader-token" else "f" * 64
        before = sorted(record_path(site, reader).parent.parent.iterdir())
        with pytest.raises(SupervisorError) as failure:
            create(owner, ids, lease, **args)
        assert failure.value.code == "UNAUTHORIZED"
        assert sorted(record_path(site, reader).parent.parent.iterdir()) == before
        assert list((site.state / "pending").iterdir()) == []


@pytest.mark.parametrize("path", [".git/index", ".fa/x", ".env", "../escape", "/absolute"])
def test_project_writes_deny_protected_control_and_escape_paths(site: Site, path: str) -> None:
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = ok(lambda: create(owner, ids, lease))
        with pytest.raises(SupervisorError) as failure:
            write(owner, grant, path=path, sha=None)
        assert failure.value.code == "PATH_DENIED"
        assert (site.source / ".git/index").read_bytes() == b"canonical index sentinel"


def test_new_nested_file_expected_absence_and_stale_sha_preserve_actual_bytes(site: Site) -> None:
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = ok(lambda: create(owner, ids, lease))
        reply = ok(lambda: write(owner, grant, path="new/a.txt", sha=None))
        assert (source(site, grant) / "new/a.txt").is_file()
        assert (source(site, grant) / "new/a.txt").read_bytes() == b"changed"
        assert reply["sha256"] == hashlib.sha256(b"changed").hexdigest()
        for sha in [None, "f" * 64]:
            with pytest.raises(SupervisorError) as failure:
                write(owner, grant, path="new/a.txt", sha=sha)
            assert failure.value.code == "STALE_REVISION"
        assert (source(site, grant) / "new/a.txt").read_text() == "changed"
        assert not (site.source / "new").exists()


@pytest.mark.parametrize("formal", [False, True])
def test_actual_plan_binding_and_post_creation_plan_recheck(site: Site, formal: bool) -> None:
    (site.source / "plan.md").write_text("# Actual admitted plan\n")
    admitted = read_plan_snapshot(site.source, Path("plan.md")).ref
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = ok(lambda: create(owner, ids, lease, plan_ref=admitted, formal=formal))
        assert json.loads(record_path(site, grant).read_text())["plan_ref"]["sha256"] == admitted.sha256
        with pytest.raises(SupervisorError) as failure:
            write(owner, grant, path="plan.md", sha=admitted.sha256)
        assert failure.value.code == "PATH_DENIED"
        (source(site, grant) / "plan.md").write_text("private shell changed plan")
        with pytest.raises(SupervisorError) as failure:
            write(owner, grant)
        assert failure.value.code == "INPUT_POLICY"
        assert (source(site, grant) / "untracked.txt").read_text() == "untracked"


@pytest.mark.parametrize("kind", ["formal-null", "wrong-plan"])
def test_invalid_plan_rejected_before_install(site: Site, kind: str) -> None:
    (site.source / "plan.md").write_text("# Plan\n")
    admitted = read_plan_snapshot(site.source, Path("plan.md")).ref
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        with pytest.raises(SupervisorError) as failure:
            create(
                owner,
                ids,
                lease,
                formal=True,
                plan_ref=None if kind == "formal-null" else replace(admitted, sha256="f" * 64),
            )
        assert failure.value.code == "INPUT_POLICY"
        assert list((site.state / "workspaces" / ids["workspace_id"] / "views").iterdir()) == []
        assert list((site.state / "pending").iterdir()) == []


@pytest.mark.parametrize("kind", ["generation", "actor", "state", "record", "view-directory", "source-directory"])
def test_stale_lifecycle_and_protected_identity_substitution_deny(site: Site, kind: str) -> None:
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = ok(lambda: create(owner, ids, lease))
        view = owner._projects[ref(grant).view_id]
        if kind == "generation":
            owner._bindings[ids["workspace_id"]].metadata["generation"] += 1
        elif kind == "actor":
            owner._bindings[ids["workspace_id"]].metadata["active_actor"] = OTHER.to_dict()
        elif kind == "state":
            view.record["state"] = "STOPPING"
            _replace_private_bytes(view.directory, "view.json", encode_json(view.record))
        elif kind == "record":
            _replace_private_bytes(view.directory, "view.json", encode_json({**view.record, "state": "STOPPING"}))
        else:
            target = source(site, grant) if kind == "source-directory" else record_path(site, grant).parent
            target.rename(target.with_name(target.name + "-old"))
            target.mkdir(mode=0o700)
            if kind == "view-directory":
                # Exact valid metadata + original source name so other guards cannot mask identity deletion.
                fd = os.open(target, _DIRECTORY)
                try:
                    _replace_private_bytes(fd, "view.json", encode_json(view.record))
                finally:
                    os.close(fd)
                (target.with_name(target.name + "-old") / "source").rename(target / "source")
        with pytest.raises(SupervisorError) as failure:
            write(owner, grant)
        assert failure.value.code == (
            "STALE_REVISION"
            if kind in {"generation", "actor"}
            else "VIEW_CLOSED"
            if kind == "state"
            else "CORRUPT_STATE"
        )
        assert (site.source / "untracked.txt").read_text() == "untracked"


def test_restart_preserves_working_view_but_cannot_reconstruct_grant_or_release_writer(site: Site) -> None:
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = ok(lambda: create(owner, ids, lease))
        ok(lambda: write(owner, grant))
    with site.owner(view_profile=native_profile()) as owner:
        assert site.metadata(ids)["status"] == "QUARANTINED"
        with pytest.raises(SupervisorError) as failure:
            write(owner, grant)
        assert failure.value.code == "UNAUTHORIZED"
        with pytest.raises(SupervisorError) as failure:
            site.claim(owner, ids)
        assert failure.value.code == "WORKSPACE_BUSY"
        assert (source(site, grant) / "untracked.txt").read_text() == "changed"


@pytest.mark.parametrize("kind", ["expired-create", "expired-write", "canonical-changed"])
def test_original_deadline_and_canonical_conflict_no_returned_view_or_write(site: Site, kind: str) -> None:
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        if kind == "expired-write":
            grant = ok(lambda: create(owner, ids, lease))
            with pytest.raises(SupervisorError) as failure:
                write(owner, grant, deadline=time.monotonic() - 1)
            assert failure.value.code == "BACKEND_UNAVAILABLE"
            assert (source(site, grant) / "untracked.txt").read_text() == "untracked"
        else:
            if kind == "canonical-changed":
                (site.source / "untracked.txt").write_text("TCB maintenance conflict")
            with pytest.raises(SupervisorError) as failure:
                create(owner, ids, lease, deadline=time.monotonic() - 1 if kind == "expired-create" else until())
            assert failure.value.code == ("BACKEND_UNAVAILABLE" if kind == "expired-create" else "DURABILITY_UNKNOWN")
            assert list((site.state / "workspaces" / ids["workspace_id"] / "views").iterdir()) == []


@pytest.mark.parametrize("fault", ["metadata-write", "install-rename", "installed-reread"])
def test_retention_faults_fence_no_ack_and_only_owned_uninstalled_stage_cleanup(
    site: Site, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        original_write = _replace_private_bytes
        original_read = workspace._read_json

        def bad_write(fd: int, name: str, raw: bytes) -> None:
            if name == "view.json":
                raise OSError("injected")
            original_write(fd, name, raw)

        def bad_read(*args: Any, **kwargs: Any) -> dict[str, Any]:
            result = original_read(*args, **kwargs)
            return {**result, "state": "STOPPING"} if args[1] == "view.json" else result

        if fault == "metadata-write":
            monkeypatch.setattr(workspace, "_replace_private_bytes", bad_write)
        elif fault == "install-rename":

            def bad_rename(*args: Any) -> None:
                raise OSError("injected")

            monkeypatch.setattr(workspace, "_rename_directory", bad_rename)
        else:
            monkeypatch.setattr(workspace, "_read_json", bad_read)
        before = len(list(Path("/proc/self/fd").iterdir()))
        with pytest.raises(SupervisorError) as failure:
            create(owner, ids, lease)
        assert failure.value.code == "DURABILITY_UNKNOWN" and not owner._healthy
        assert len(list(Path("/proc/self/fd").iterdir())) == before
        assert list((site.state / "pending").iterdir()) == []
        assert (site.source / "untracked.txt").read_text() == "untracked"
        retained = list((site.state / "workspaces" / ids["workspace_id"] / "views").iterdir())
        assert len(retained) == (1 if fault == "installed-reread" else 0)


def test_native_write_handler_blocks_owner_shutdown_until_real_io_finishes(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered, proceed, closing = threading.Event(), threading.Event(), threading.Event()
    original = RootedViewIO.write_file

    def paused(self: RootedViewIO, path: str, content: str, *, expected_sha256: str | None) -> WriteResult:
        entered.set()
        assert proceed.wait(5)
        return original(self, path, content, expected_sha256=expected_sha256)

    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = ok(lambda: create(owner, ids, lease))
        monkeypatch.setattr(RootedViewIO, "write_file", paused)

        def close() -> None:
            closing.set()
            owner.__exit__(None, None, None)

        with ThreadPoolExecutor(max_workers=2) as pool:
            writer = pool.submit(write, owner, grant)
            try:
                assert entered.wait(2)
                closer = pool.submit(close)
                assert closing.wait(2)
                with pytest.raises(TimeoutError):
                    closer.result(timeout=0.05)
            finally:
                proceed.set()
            assert ok(lambda: writer.result(timeout=3))["sha256"] == hashlib.sha256(b"changed").hexdigest()
            closer.result(timeout=3)
        assert (source(site, grant) / "untracked.txt").read_text() == "changed"
        with pytest.raises(SupervisorError) as failure:
            write(owner, grant)
        assert failure.value.code == "CORRUPT_STATE"


def test_no_approved_profile_cannot_create_a_project_view(site: Site) -> None:
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        with pytest.raises(SupervisorError) as failure:
            create(owner, ids, lease)
        assert failure.value.code == "UNAPPROVED_PROFILE"
        assert list((site.state / "workspaces" / ids["workspace_id"] / "views").iterdir()) == []


def test_reader_grant_never_authorizes_rooted_writes(site: Site) -> None:
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        reader = ok(lambda: pin(owner, ids))
        with pytest.raises(SupervisorError) as failure:
            write(owner, reader)
        assert failure.value.code == "UNAUTHORIZED"
        assert (site.revision(ids) / "data/untracked.txt").read_text() == "untracked"


def test_secret_disguised_as_plan_path_cannot_be_retained(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    hidden = "f" * 64
    (site.source / hidden).write_text("# Plan\n")
    admitted = read_plan_snapshot(site.source, Path(hidden)).ref
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        monkeypatch.setattr(secrets, "token_hex", lambda n: hidden)
        with pytest.raises(SupervisorError) as failure:
            create(owner, ids, lease, plan_ref=admitted)
        assert failure.value.code == "INPUT_POLICY"
        assert list((site.state / "workspaces" / ids["workspace_id"] / "views").iterdir()) == []


def test_deadline_after_views_open_cannot_rename_or_ack(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        opened = os.open
        budget = workspace._budget
        expired = False

        def open_then_expire(path: Any, *args: Any, **kwargs: Any) -> int:
            nonlocal expired
            result = opened(path, *args, **kwargs)
            if path == "views":
                expired = True
            return result

        def checked(deadline: float) -> None:
            if expired:
                raise SupervisorError("BACKEND_UNAVAILABLE")
            budget(deadline)

        monkeypatch.setattr(os, "open", open_then_expire)
        monkeypatch.setattr(workspace, "_budget", checked)
        with pytest.raises(SupervisorError) as failure:
            create(owner, ids, lease)
        assert failure.value.code == "BACKEND_UNAVAILABLE"
        assert not owner._projects
        assert list((site.state / "workspaces" / ids["workspace_id"] / "views").iterdir()) == []
        assert list((site.state / "pending").iterdir()) == []


@pytest.mark.parametrize("fault", ["deadline", "context-close", "parent-fsync"])
def test_post_write_uncertainty_retains_effects_and_fences_owner(
    site: Site, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = ok(lambda: create(owner, ids, lease))
        original_write = RootedViewIO.write_file
        budget = workspace._budget
        completed = False

        def observed_write(self: RootedViewIO, path: str, content: str, *, expected_sha256: str | None) -> WriteResult:
            nonlocal completed
            result = original_write(self, path, content, expected_sha256=expected_sha256)
            completed = True
            return result

        def checked(deadline: float) -> None:
            if completed:
                raise SupervisorError("BACKEND_UNAVAILABLE")
            budget(deadline)

        if fault == "deadline":
            monkeypatch.setattr(RootedViewIO, "write_file", observed_write)
            monkeypatch.setattr(workspace, "_budget", checked)
        elif fault == "context-close":
            original_exit = RootedViewIO.__exit__

            def bad_exit(self: RootedViewIO, *args: Any) -> None:
                original_exit(self, *args)
                raise OSError("injected context close")

            monkeypatch.setattr(RootedViewIO, "__exit__", bad_exit)
        else:
            original_fsync = os.fsync
            identity = source(site, grant).stat().st_ino

            def bad_fsync(fd: int) -> None:
                if os.fstat(fd).st_ino == identity:
                    raise OSError("injected parent fsync")
                original_fsync(fd)

            monkeypatch.setattr(os, "fsync", bad_fsync)
        with pytest.raises(SupervisorError) as failure:
            write(owner, grant)
        assert failure.value.code == "DURABILITY_UNKNOWN" and not owner._healthy
        assert (source(site, grant) / "untracked.txt").read_text() == "changed"
        assert (site.source / "untracked.txt").read_text() == "untracked"


def test_repeated_io_and_authority_shutdown_release_project_descriptors(site: Site) -> None:
    before = len(list(Path("/proc/self/fd").iterdir()))
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = ok(lambda: create(owner, ids, lease))
        active = len(list(Path("/proc/self/fd").iterdir()))
        for _ in range(3):
            assert ok(lambda: read(owner, grant))["content"] == "untracked"
        assert len(list(Path("/proc/self/fd").iterdir())) == active
    assert len(list(Path("/proc/self/fd").iterdir())) == before
    assert (source(site, grant) / "untracked.txt").read_text() == "untracked", "shutdown is not view GC"


def test_stage_context_exit_failure_after_install_closes_transient_view_fd(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))

        @contextmanager
        def bad_stage_exit(path: Path) -> Generator[int]:
            with _private_artifact_directory(path) as fd:
                yield fd
            if path.parent.name == "pending":
                raise OSError("injected stage context exit")

        monkeypatch.setattr(workspace, "_private_artifact_directory", bad_stage_exit)
        before = len(list(Path("/proc/self/fd").iterdir()))
        with pytest.raises(SupervisorError) as failure:
            create(owner, ids, lease)
        assert failure.value.code == "DURABILITY_UNKNOWN" and not owner._healthy
        assert len(list(Path("/proc/self/fd").iterdir())) == before
        assert not owner._projects
        assert len(list((site.state / "workspaces" / ids["workspace_id"] / "views").iterdir())) == 1
