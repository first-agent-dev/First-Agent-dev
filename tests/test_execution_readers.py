"""C0/C3 actual reader owner + retained FS + rooted IO; not service/PTY C1/C2.

Paths: fresh/owned/quarantined registration; exact/mismatched/revoked/restarted proof;
ordinary/formal plan; immutable bytes/identity/hash; durable retain/release faults;
native handler/release/shutdown lock ordering and original deadlines.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import Any

import pytest

from fa.execution import workspace
from fa.execution.supervisor import SupervisorError
from fa.execution.types import Access, ExecutionContractError, GrantReply, ViewRef
from fa.execution.view_io import ReadResult, RootedViewIO
from fa.execution.workspace import WorkspaceAuthority
from fa.inner_loop.plan_admission import read_plan_snapshot
from fa.inner_loop.workflow_artifacts import _replace_private_bytes
from tests.test_execution_dispatch import profile
from tests.test_execution_workspace import ACTOR, OTHER, PEER, Site, ok, until
from tests.test_execution_workspace import site as site


def pin(owner: WorkspaceAuthority, ids: dict[str, str], **kwargs: Any) -> GrantReply:
    grant = owner.pin_reader(
        kwargs.get("peer", PEER),
        kwargs.get("namespace", ACTOR),
        workspace_id=ids["workspace_id"],
        revision_id=kwargs.get("revision_id", ids["revision_id"]),
        plan_ref=kwargs.get("plan_ref"),
        formal_evidence=kwargs.get("formal", False),
        deadline=kwargs.get("deadline", until()),
    )
    # Authoritative retention must exist before any consumer can use the grant.
    assert grant.view_ref is not None
    retained = (
        owner._state / "workspaces" / grant.view_ref.workspace_id / "views" / grant.view_ref.view_id / "view.json"
    )
    assert retained.is_file(), "pin acknowledgement preceded durable retention"
    assert json.loads(retained.read_text())["view_ref"] == grant.view_ref.to_dict()
    return grant


def ref(grant: GrantReply) -> ViewRef:
    assert grant.view_ref is not None
    return grant.view_ref


def read(owner: WorkspaceAuthority, grant: GrantReply, **kwargs: Any) -> ReadResult:
    return owner.read_file(
        kwargs.get("peer", PEER),
        kwargs.get("namespace", ACTOR),
        view_ref=kwargs.get("view_ref", ref(grant)),
        capability=kwargs.get("capability", grant.capability),
        path=kwargs.get("path", "untracked.txt"),
        offset_bytes=kwargs.get("offset", 0),
        max_bytes=kwargs.get("max_bytes", 1024),
        deadline=kwargs.get("deadline", until()),
    )


def release(owner: WorkspaceAuthority, grant: GrantReply, **kwargs: Any) -> dict[str, bool]:
    return owner.release_reader(
        kwargs.get("peer", PEER),
        kwargs.get("namespace", ACTOR),
        view_ref=kwargs.get("view_ref", ref(grant)),
        capability=kwargs.get("capability", grant.capability),
        deadline=kwargs.get("deadline", until()),
    )


def record_path(site: Site, grant: GrantReply) -> Path:
    return site.state / "workspaces" / ref(grant).workspace_id / "views" / ref(grant).view_id / "view.json"


def test_fresh_genesis_has_durable_nonsecret_reader_without_writer(site: Site) -> None:
    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = ok(lambda: pin(owner, ids))
        record = json.loads(record_path(site, grant).read_text())
        assert record["view_ref"] == ref(grant).to_dict()
        assert record["actor_namespace"] == ACTOR.to_dict()
        assert record["state"] == "OPEN" and record["operation_ids"] == []
        assert record["plan_ref"] is record["candidate_scope"] is record["sealed_manifest_id"] is None
        assert ref(grant).access is Access.READ and ref(grant).generation == 1
        assert site.metadata(ids)["generation"] == 1 and site.metadata(ids)["status"] == "AVAILABLE"
        assert site.metadata(ids)["owner_namespace"] is site.metadata(ids)["active_actor"] is None
        assert all(grant.capability.encode() not in p.read_bytes() for p in site.state.rglob("*.json"))
        assert grant.capability not in repr(grant) and grant.capability not in repr(owner._readers)
        assert record_path(site, grant).stat().st_mode & 0o777 == 0o600
        assert ok(lambda: read(owner, grant)) == {
            "content": "untracked",
            "sha256": hashlib.sha256(b"untracked").hexdigest(),
            "eof": True,
        }
        assert (site.source / ".git/index").read_bytes() == b"canonical index sentinel"


def test_pin_does_not_follow_canonical_bytes_and_survives_writer_epoch_advance(site: Site) -> None:
    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = ok(lambda: pin(owner, ids))
        first = ok(lambda: site.claim(owner, ids))
        assert first.generation == 2
        assert ok(lambda: site.release(owner, ids, first)) == {"released": True}
        second = ok(lambda: site.claim(owner, ids))
        assert second.generation == 3 and ref(grant).generation == 1
        assert ok(lambda: site.release(owner, ids, second)) == {"released": True}
        (site.source / "untracked.txt").write_text("canonical maintenance changed")
        assert ok(lambda: read(owner, grant))["content"] == "untracked"
        assert ok(lambda: release(owner, grant)) == {"released": True}


@pytest.mark.parametrize(
    "which",
    ["namespace", "principal", "capability", "owner-cap", "generation", "revision", "access", "run", "workspace"],
)
def test_wrong_reader_identity_denies_read_and_release(site: Site, which: str) -> None:
    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = ok(lambda: pin(owner, ids))
        kwargs: dict[str, Any] = {}
        if which == "namespace":
            kwargs["namespace"] = OTHER
        elif which == "principal":
            kwargs["peer"] = replace(PEER, gid=PEER.gid + 1)
        elif which == "capability":
            kwargs["capability"] = "f" * 64
        elif which == "owner-cap":
            writer = ok(lambda: site.claim(owner, ids))
            kwargs["capability"] = writer.capability
        else:
            key, value = {
                "generation": ("generation", ref(grant).generation + 1),
                "revision": ("base_revision", "rev-" + "f" * 32),
                "access": ("access", Access.WRITE),
                "run": ("owner_run_id", "different-run"),
                "workspace": ("workspace_id", "ws-" + "f" * 32),
            }[which]
            changes: dict[str, Any] = {key: value}
            kwargs["view_ref"] = replace(ref(grant), **changes)
        calls: list[Callable[[], object]] = [
            lambda: read(owner, grant, **kwargs),
            lambda: release(owner, grant, **kwargs),
        ]
        for call in calls:
            with pytest.raises(SupervisorError) as failure:
                call()
            assert failure.value.code == "UNAUTHORIZED"
        assert ok(lambda: read(owner, grant))["content"] == "untracked"


def test_reader_cannot_release_writer_and_owner_cannot_read_with_reader_ids(site: Site) -> None:
    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = ok(lambda: pin(owner, ids))
        with pytest.raises(SupervisorError) as failure:
            owner.release_unused_writer(
                PEER, ACTOR, workspace_id=ids["workspace_id"], capability=grant.capability, deadline=until()
            )
        assert failure.value.code == "UNAUTHORIZED"
        assert site.metadata(ids)["status"] == "AVAILABLE"


def test_reader_releases_only_itself_and_retains_data_record(site: Site) -> None:
    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        one = ok(lambda: pin(owner, ids))
        two = ok(lambda: pin(owner, ids, namespace=OTHER))
        assert ok(lambda: release(owner, one)) == {"released": True}
        assert json.loads(record_path(site, one).read_text())["state"] == "REJECTED"
        assert (site.revision(ids) / "data/untracked.txt").read_text() == "untracked"
        with pytest.raises(SupervisorError) as failure:
            read(owner, one)
        assert failure.value.code == "UNAUTHORIZED"
        assert ok(lambda: read(owner, two, namespace=OTHER))["content"] == "untracked"
        with pytest.raises(SupervisorError) as failure:
            release(owner, one)
        assert failure.value.code == "UNAUTHORIZED"


def test_restart_keeps_retention_but_never_reconstructs_capability(site: Site) -> None:
    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        old = ok(lambda: pin(owner, ids))
    before = record_path(site, old).read_bytes()
    with site.owner(view_profile=profile()) as owner:
        with pytest.raises(SupervisorError) as failure:
            read(owner, old)
        assert failure.value.code == "UNAUTHORIZED"
        assert record_path(site, old).read_bytes() == before
        assert (site.revision(ids) / "data/untracked.txt").read_text() == "untracked"
        fresh = ok(lambda: pin(owner, ids))
        assert fresh.capability != old.capability and ref(fresh) != ref(old)
        writer = ok(lambda: site.claim(owner, ids))
        assert ok(lambda: site.release(owner, ids, writer)) == {"released": True}


@pytest.mark.parametrize("formal", [False, True])
def test_actual_pinned_plan_context_is_bound_and_rechecked(site: Site, formal: bool) -> None:
    (site.source / "plan.md").write_text("# Admitted actual plan\n")
    admitted = read_plan_snapshot(site.source, Path("plan.md")).ref
    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = ok(lambda: pin(owner, ids, plan_ref=admitted, formal=formal))
        assert json.loads(record_path(site, grant).read_text())["plan_ref"]["sha256"] == admitted.sha256
        assert ok(lambda: read(owner, grant))["content"] == "untracked"
        (site.revision(ids) / "data/plan.md").write_text("changed protected plan")
        with pytest.raises(SupervisorError) as failure:
            read(owner, grant)
        assert failure.value.code == "INPUT_POLICY"
        # Denying fresh work must not prevent revoking this exact capability.
        assert ok(lambda: release(owner, grant)) == {"released": True}


@pytest.mark.parametrize("kind", ["missing-formal", "wrong-hash", "missing-plan"])
def test_plan_mismatch_denies_pin_before_retention(site: Site, kind: str) -> None:
    (site.source / "plan.md").write_text("# Admitted plan\n")
    admitted = read_plan_snapshot(site.source, Path("plan.md")).ref
    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        plan = (
            None
            if kind == "missing-formal"
            else replace(admitted, sha256="f" * 64)
            if kind == "wrong-hash"
            else replace(admitted, workspace_relative_path="missing.md")
        )
        with pytest.raises(SupervisorError) as failure:
            pin(owner, ids, plan_ref=plan, formal=True)
        assert failure.value.code == "INPUT_POLICY"
        assert list((site.state / "workspaces" / ids["workspace_id"] / "views").iterdir()) == []


def test_unconfigured_profile_and_invalid_uid_are_not_guessed(site: Site) -> None:
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        with pytest.raises(SupervisorError) as failure:
            pin(owner, ids)
        assert failure.value.code == "UNAPPROVED_PROFILE"
    with pytest.raises(ExecutionContractError):
        site.owner(view_profile=replace(profile(), uid=2**32 - 1))


@pytest.mark.parametrize("path", ["../untracked.txt", ".git/index", ".env", "/untracked.txt"])
def test_reader_rooted_path_denials_have_no_fallback(site: Site, path: str) -> None:
    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = ok(lambda: pin(owner, ids))
        with pytest.raises(SupervisorError) as failure:
            read(owner, grant, path=path)
        assert failure.value.code == "PATH_DENIED"


def test_authorized_reader_primitive_is_really_readonly(site: Site) -> None:
    with site.owner(view_profile=replace(profile(), uid=os.getuid() or 1000, gid=os.getgid() or 1000)) as owner:
        ids = ok(lambda: site.register(owner))
        grant = ok(lambda: pin(owner, ids))
        with pytest.raises(SupervisorError) as failure:
            with owner._reader_io(PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until()) as (
                io,
                _,
            ):
                io.write_file("new-file", "forbidden", expected_sha256=None)
        assert failure.value.code == "PATH_DENIED"
        assert not (site.revision(ids) / "data/new-file").exists()


@pytest.mark.parametrize("kind", ["bytes", "manifest", "data-root", "view-root", "record"])
def test_retained_source_and_record_identity_changes_are_rejected(site: Site, kind: str) -> None:
    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = ok(lambda: pin(owner, ids))
        revision = site.revision(ids)
        if kind == "bytes":
            (revision / "data/untracked.txt").write_text("tampered private bytes")
        elif kind == "manifest":
            path = revision / "tree.json"
            path.write_bytes(path.read_bytes() + b" ")
        elif kind == "data-root":
            (revision / "data").rename(revision / "old-data")
            (revision / "data").mkdir()
        elif kind == "view-root":
            path = record_path(site, grant).parent
            retained = (path / "view.json").read_bytes()
            path.rename(path.with_name("old-view"))
            path.mkdir(mode=0o700)
            (path / "view.json").write_bytes(retained)
            (path / "view.json").chmod(0o600)
        else:
            path = record_path(site, grant)
            value = json.loads(path.read_text())
            value["view_ref"]["generation"] += 1
            path.write_text(json.dumps(value))
        with pytest.raises(SupervisorError) as failure:
            read(owner, grant)
        assert failure.value.code == "CORRUPT_STATE"


@pytest.mark.parametrize("phase", ["replace", "install", "fsync", "reread"])
def test_retention_failure_never_returns_grant_and_closes_all_fds(
    site: Site, phase: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        before = len(list(Path("/proc/self/fd").iterdir()))
        original_replace = _replace_private_bytes
        original_fsync = os.fsync

        def replace_record(fd: int, name: str, raw: bytes) -> None:
            if name == "view.json" and phase == "replace":
                raise OSError("injected retention failure")
            if name == "view.json" and phase == "reread":
                value = json.loads(raw)
                value["view_ref"]["generation"] += 1
                raw = json.dumps(value).encode()
            original_replace(fd, name, raw)

        def fail_install(*args: Any) -> None:
            raise OSError("injected no-clobber failure")

        def fsync(fd: int) -> None:
            if phase == "fsync":
                raise OSError("injected native fsync failure")
            original_fsync(fd)

        with monkeypatch.context() as patch:
            patch.setattr(workspace, "_replace_private_bytes", replace_record)
            patch.setattr(os, "fsync", fsync)
            if phase == "install":
                patch.setattr(workspace, "_rename_directory", fail_install)
            with pytest.raises(SupervisorError) as failure:
                pin(owner, ids)
            assert failure.value.code == "DURABILITY_UNKNOWN"
        assert owner._readers == {}
        assert len(list(Path("/proc/self/fd").iterdir())) == before
        assert list((site.state / "pending").iterdir()) == []
        assert (site.source / "untracked.txt").read_text() == "untracked"


def test_expiry_after_retention_returns_no_grant_and_keeps_uncertain_reference(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        original = WorkspaceAuthority._retain_reader
        end = time.monotonic() + 0.1

        def retain(this: WorkspaceAuthority, *args: Any) -> int:
            fd = original(this, *args)
            while time.monotonic() <= end:
                time.sleep(0.002)
            return fd

        monkeypatch.setattr(WorkspaceAuthority, "_retain_reader", retain)
        with pytest.raises(SupervisorError) as failure:
            pin(owner, ids, deadline=end)
        assert failure.value.code == "BACKEND_UNAVAILABLE"
        assert owner._readers == {}
        assert len(list((site.state / "workspaces" / ids["workspace_id"] / "views").iterdir())) == 1


@pytest.mark.parametrize("action", ["release", "shutdown"])
def test_native_read_handler_keeps_descriptors_until_release_or_shutdown_drains(
    site: Site, action: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = ok(lambda: pin(owner, ids))
        entered, allow, close_started = threading.Event(), threading.Event(), threading.Event()
        original = RootedViewIO.read_file

        def paused(io: RootedViewIO, *args: Any, **kwargs: Any) -> ReadResult:
            entered.set()
            assert allow.wait(5)
            return original(io, *args, **kwargs)

        monkeypatch.setattr(RootedViewIO, "read_file", paused)

        def close() -> object:
            close_started.set()
            return release(owner, grant) if action == "release" else owner.__exit__(None, None, None)

        with ThreadPoolExecutor(max_workers=2) as pool:
            running = pool.submit(lambda: ok(lambda: read(owner, grant)))
            assert entered.wait(5)
            closing = pool.submit(close)
            try:
                assert close_started.wait(5)
                with pytest.raises(TimeoutError):
                    closing.result(timeout=0.05)
            finally:
                allow.set()
            assert running.result(timeout=5)["content"] == "untracked"
            closing.result(timeout=5)
        with pytest.raises(SupervisorError) as failure:
            read(owner, grant)
        assert failure.value.code in {"UNAUTHORIZED", "CORRUPT_STATE"}


@pytest.mark.parametrize("kind", ["large", "split-utf8", "binary", "empty-window"])
def test_real_reader_windows_hash_complete_retained_file(site: Site, kind: str) -> None:
    raw = (
        b"a" * (1024 * 1024 + 19)
        if kind == "large"
        else "aéz".encode()
        if kind == "split-utf8"
        else b"bad\x00binary"
        if kind == "binary"
        else b"untracked"
    )
    (site.source / "window").write_bytes(raw)
    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = ok(lambda: pin(owner, ids))
        if kind in {"binary", "split-utf8"}:
            with pytest.raises(SupervisorError) as failure:
                read(owner, grant, path="window", offset=2 if kind == "split-utf8" else 0)
            assert failure.value.code == "INPUT_POLICY"
        else:
            result = ok(lambda: read(owner, grant, path="window", offset=1024 * 1024 if kind == "large" else 1000))
            assert result["content"] == ("a" * 19 if kind == "large" else "")
            assert result["sha256"] == hashlib.sha256(raw).hexdigest()
            assert result["eof"] is True


@pytest.mark.parametrize("phase", ["before", "after", "reread"])
def test_release_fsync_failure_revokes_token_and_preserves_retention(
    site: Site, phase: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = ok(lambda: pin(owner, ids))
        original = _replace_private_bytes

        def fail(fd: int, name: str, raw: bytes) -> None:
            if phase == "before":
                raise OSError("injected before release effect")
            if phase == "reread":
                raw = json.dumps(owner._readers[ref(grant).view_id].record | {"state": "OPEN"}).encode()
            original(fd, name, raw)
            if phase == "after":
                raise OSError("injected lost release acknowledgement")

        with monkeypatch.context() as patch:
            patch.setattr(workspace, "_replace_private_bytes", fail)
            with pytest.raises(SupervisorError) as failure:
                release(owner, grant)
            assert failure.value.code == "DURABILITY_UNKNOWN"
        assert owner._readers[ref(grant).view_id].capability is None
        assert json.loads(record_path(site, grant).read_text())["state"] == ("REJECTED" if phase == "after" else "OPEN")
        assert (site.revision(ids) / "data/untracked.txt").read_text() == "untracked"
        with pytest.raises(SupervisorError) as failure:
            read(owner, grant)
        assert failure.value.code == "CORRUPT_STATE"


def test_expired_reader_requests_have_zero_read_or_release_effects(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = ok(lambda: pin(owner, ids))
        calls: list[str] = []
        original = RootedViewIO.read_file

        def observe(io: RootedViewIO, path: str, **kwargs: Any) -> ReadResult:
            calls.append(path)
            return original(io, path, **kwargs)

        monkeypatch.setattr(RootedViewIO, "read_file", observe)
        actions: list[Callable[[], object]] = [
            lambda: read(owner, grant, deadline=time.monotonic() - 1),
            lambda: release(owner, grant, deadline=time.monotonic() - 1),
        ]
        for call in actions:
            with pytest.raises(SupervisorError) as failure:
                call()
            assert failure.value.code == "BACKEND_UNAVAILABLE"
        assert calls == []
        assert json.loads(record_path(site, grant).read_text())["state"] == "OPEN"
        assert ok(lambda: read(owner, grant))["content"] == "untracked"


def test_read_queued_past_original_deadline_does_not_run_late(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = ok(lambda: pin(owner, ids))
        calls: list[str] = []
        original = RootedViewIO.read_file

        def observe(io: RootedViewIO, path: str, **kwargs: Any) -> ReadResult:
            calls.append(path)
            return original(io, path, **kwargs)

        monkeypatch.setattr(RootedViewIO, "read_file", observe)
        outcomes: list[str] = []
        started = threading.Event()

        def wait_read() -> None:
            started.set()
            try:
                read(owner, grant, deadline=time.monotonic() + 0.05)
            except SupervisorError as error:
                outcomes.append(error.code)

        with owner._mutex:
            worker = threading.Thread(target=wait_read)
            worker.start()
            assert started.wait(5)
            worker.join(timeout=0.5)
            assert not worker.is_alive(), "expired request remained queued on authority lock"
        worker.join(timeout=5)
        assert outcomes == ["BACKEND_UNAVAILABLE"] and calls == []


def test_missing_revision_is_determinate_denial_without_poisoning_owner(site: Site) -> None:
    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        with pytest.raises(SupervisorError) as failure:
            pin(owner, ids, revision_id="rev-" + "f" * 32)
        assert failure.value.code == "STALE_REVISION"
        grant = ok(lambda: pin(owner, ids))
        assert ok(lambda: read(owner, grant))["content"] == "untracked"


def test_quarantined_old_writer_cannot_block_immutable_reader_or_renew_ownership(site: Site) -> None:
    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        writer = ok(lambda: site.claim(owner, ids))
    with site.owner(view_profile=profile()) as owner:
        assert site.metadata(ids)["status"] == "QUARANTINED"
        grant = ok(lambda: pin(owner, ids))
        assert ref(grant).generation == writer.generation
        assert ok(lambda: read(owner, grant))["content"] == "untracked"
        with pytest.raises(SupervisorError) as failure:
            site.claim(owner, ids)
        assert failure.value.code == "WORKSPACE_BUSY"


def test_native_retention_collision_never_overwrites_original_pin_or_renews_token(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uuid import UUID

    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        monkeypatch.setattr(workspace, "uuid4", lambda: UUID(int=1))
        grant = ok(lambda: pin(owner, ids))
        before = record_path(site, grant).read_bytes()
        with pytest.raises(SupervisorError) as failure:
            pin(owner, ids)
        assert failure.value.code == "DURABILITY_UNKNOWN"
        assert record_path(site, grant).read_bytes() == before
        assert list(owner._readers) == [ref(grant).view_id]
        assert list((site.state / "pending").iterdir()) == []


def test_known_issued_secret_cannot_hide_in_retained_metadata(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        tree = json.loads((site.revision(ids) / "tree.json").read_text())
        monkeypatch.setattr(secrets, "token_hex", lambda size: tree["tree_sha256"])
        with pytest.raises(SupervisorError) as failure:
            pin(owner, ids)
        assert failure.value.code == "INPUT_POLICY"
        assert list((site.state / "workspaces" / ids["workspace_id"] / "views").iterdir()) == []


def test_plan_validation_expiry_cannot_begin_retention(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    from fa.execution.plans import ProtectedPlanContext

    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        end = time.monotonic() + 0.05
        original = WorkspaceAuthority._retain_reader
        calls: list[str] = []

        def recheck(ctx: ProtectedPlanContext) -> None:
            while time.monotonic() <= end:
                time.sleep(0.002)

        def retain(this: WorkspaceAuthority, *args: Any) -> int:
            calls.append("retain")
            return original(this, *args)

        monkeypatch.setattr(ProtectedPlanContext, "recheck", recheck)
        monkeypatch.setattr(WorkspaceAuthority, "_retain_reader", retain)
        with pytest.raises(SupervisorError) as failure:
            pin(owner, ids, deadline=end)
        assert failure.value.code == "BACKEND_UNAVAILABLE"
        assert calls == [] and owner._readers == {}
        assert list((site.state / "workspaces" / ids["workspace_id"] / "views").iterdir()) == []


def test_completed_releases_retire_descriptors_and_heavy_maps_without_gc_or_fd_reuse(site: Site) -> None:
    with site.owner(view_profile=profile()) as owner:
        ids = ok(lambda: site.register(owner))
        before = len(list(Path("/proc/self/fd").iterdir()))
        grants: list[GrantReply] = []
        for _ in range(3):
            grant = ok(lambda: pin(owner, ids))
            grants.append(grant)
            assert ok(partial(release, owner, grant)) == {"released": True}
            assert record_path(site, grant).is_file()
        assert len(list(Path("/proc/self/fd").iterdir())) == before
        assert all(owner._readers[ref(g).view_id].entries == {} for g in grants)
        sentinel = os.open(site.source / "untracked.txt", os.O_RDONLY)
        try:
            owner.__exit__(None, None, None)
            assert os.read(sentinel, 100) == b"untracked", "shutdown closed a reused FD number"
        finally:
            os.close(sentinel)
        assert (site.revision(ids) / "data/untracked.txt").read_text() == "untracked"
