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
from fa.execution.profiles import ExecutionProfile
from fa.execution.supervisor import SupervisorError
from fa.execution.types import Access, ExecutionContractError, GrantReply, ViewRef
from fa.execution.view_io import ReadResult, RootedViewIO
from fa.execution.workspace import WorkspaceAuthority
from fa.inner_loop.plan_admission import read_plan_snapshot
from fa.inner_loop.workflow_artifacts import _replace_private_bytes
from tests.test_execution_dispatch import profile
from tests.test_execution_workspace import ACTOR, OTHER, PEER, Site, ok, until
from tests.test_execution_workspace import site as site


def read_only_profile() -> ExecutionProfile:
    return replace(profile(), profile_id="reader", interactive=False)


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
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
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
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
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
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
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
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = ok(lambda: pin(owner, ids))
        with pytest.raises(SupervisorError) as failure:
            owner.release_unused_writer(
                PEER, ACTOR, workspace_id=ids["workspace_id"], capability=grant.capability, deadline=until()
            )
        assert failure.value.code == "UNAUTHORIZED"
        assert site.metadata(ids)["status"] == "AVAILABLE"


def test_reader_releases_only_itself_and_retains_data_record(site: Site) -> None:
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
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
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        old = ok(lambda: pin(owner, ids))
    before = record_path(site, old).read_bytes()
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
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
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
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
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
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
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = ok(lambda: pin(owner, ids))
        with pytest.raises(SupervisorError) as failure:
            read(owner, grant, path=path)
        assert failure.value.code == "PATH_DENIED"


def test_authorized_reader_primitive_is_really_readonly(site: Site) -> None:
    with site.owner(
        view_profile=replace(profile(), uid=os.getuid() or 1000, gid=os.getgid() or 1000),
        read_only_profile=read_only_profile(),
    ) as owner:
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
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
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
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
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
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
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
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
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
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
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
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
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
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
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
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
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
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        with pytest.raises(SupervisorError) as failure:
            pin(owner, ids, revision_id="rev-" + "f" * 32)
        assert failure.value.code == "STALE_REVISION"
        grant = ok(lambda: pin(owner, ids))
        assert ok(lambda: read(owner, grant))["content"] == "untracked"


def test_quarantined_old_writer_cannot_block_immutable_reader_or_renew_ownership(site: Site) -> None:
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        writer = ok(lambda: site.claim(owner, ids))
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
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

    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
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
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        tree = json.loads((site.revision(ids) / "tree.json").read_text())
        monkeypatch.setattr(secrets, "token_hex", lambda size: tree["tree_sha256"])
        with pytest.raises(SupervisorError) as failure:
            pin(owner, ids)
        assert failure.value.code == "INPUT_POLICY"
        assert list((site.state / "workspaces" / ids["workspace_id"] / "views").iterdir()) == []


def test_plan_validation_expiry_cannot_begin_retention(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    from fa.execution.plans import ProtectedPlanContext

    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
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
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
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


def test_acceptance_inventory_names_exact_pinned_subtree_not_host(site: Site) -> None:
    root = site.source / "worklogs" / "demo" / "acceptance"
    (root / "tests").mkdir(parents=True)
    (root / "pytest.ini").write_text("[pytest]\n")
    (root / "tests" / "test_a.py").write_text("old\n")
    (root / "tests" / "link.py").symlink_to("test_a.py")
    (site.source / "worklogs" / "demo" / "acceptance-other").mkdir()
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = ok(lambda: pin(owner, ids))
        (root / "tests" / "test_a.py").write_text("new\n")
        (root / "tests" / "extra.py").write_text("new\n")
        result = owner.inventory_acceptance(
            PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, project_slug="demo", deadline=until()
        )
        assert result["revision_id"] == ids["revision_id"]
        assert result["tree_sha256"] == grant.input_tree_sha256
        assert result["entries"] == [
            {"path": "pytest.ini", "type": "file", "size": 9, "sha256": hashlib.sha256(b"[pytest]\n").hexdigest()},
            {"path": "tests", "type": "directory", "size": 0, "sha256": None},
            {"path": "tests/link.py", "type": "symlink", "size": 9, "sha256": hashlib.sha256(b"test_a.py").hexdigest()},
            {"path": "tests/test_a.py", "type": "file", "size": 4, "sha256": hashlib.sha256(b"old\n").hexdigest()},
        ]


def test_acceptance_inventory_requires_authorized_live_reader(site: Site) -> None:
    (site.source / "worklogs" / "demo" / "acceptance").mkdir(parents=True)
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = ok(lambda: pin(owner, ids))

        def invoke(**kwargs: Any) -> dict[str, Any]:
            return owner.inventory_acceptance(
                kwargs.get("peer", PEER),
                kwargs.get("namespace", ACTOR),
                view_ref=ref(grant),
                capability=kwargs.get("capability", grant.capability),
                project_slug=kwargs.get("slug", "demo"),
                deadline=until(),
            )

        for arguments in ({"capability": "f" * 64}, {"namespace": OTHER}, {"slug": "../demo"}, {"slug": "missing"}):
            with pytest.raises(SupervisorError) as error:
                invoke(**arguments)
            assert error.value.code in {"UNAUTHORIZED", "INPUT_POLICY"}
        assert ok(lambda: release(owner, grant)) == {"released": True}
        with pytest.raises(SupervisorError) as error:
            invoke()
        assert error.value.code in {"UNAUTHORIZED", "VIEW_CLOSED"}


def test_acceptance_inventory_refuses_over_limit_instead_of_truncating(site: Site) -> None:
    root = site.source / "worklogs" / "demo" / "acceptance"
    root.mkdir(parents=True)
    for i in range(4097):
        (root / f"f{i:04}").write_bytes(b"")
    with site.owner(view_profile=profile(), read_only_profile=read_only_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = ok(lambda: pin(owner, ids))
        with pytest.raises(SupervisorError) as error:
            owner.inventory_acceptance(
                PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, project_slug="demo", deadline=until()
            )
        assert error.value.code == "INPUT_POLICY"


def _register_acceptance_fixture(site: Site, owner: WorkspaceAuthority) -> dict[str, str]:
    """Synthetic origin for component checks; real BOOTSTRAP edge is tested separately."""
    ids = site.register(owner)
    binding = owner._binding(ids["workspace_id"])
    for slug in ("demo", "seals"):
        owner._record_acceptance_origin(
            binding,
            {
                "target_relative": f"worklogs/{slug}",
                "workspace_id": ids["workspace_id"],
                "operation_id": "op-" + "a" * 32,
                "next_revision": ids["revision_id"],
            },
        )
    return ids


def _acceptance_store_case(site: Site) -> tuple[Any, Any]:
    """Build a real registered revision and a controller-minted matching seal."""
    from fa.inner_loop.plan_admission import PlanRef
    from tests.test_ai_native_acceptance_collection import _PLAN_BYTES, _tree

    root = _tree(site.source)
    path = "worklogs/demo/increments/increment-01-demo.md"
    plan = site.source / path
    plan.parent.mkdir(parents=True)
    plan.write_bytes(_PLAN_BYTES)
    return root, PlanRef(path, "EXPLICIT", hashlib.sha256(_PLAN_BYTES).hexdigest())


def test_authority_stores_acceptance_seal_in_private_project_scope(site: Site) -> None:
    from fa.inner_loop.acceptance_bundle import seal_bytes
    from fa.inner_loop.acceptance_seal_store import SealStore
    from tests.test_ai_native_acceptance_collection import _mint

    root, plan_ref = _acceptance_store_case(site)
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        arguments = {
            "capability": grant.capability,
            "project_slug": "demo",
            "plan_ref": plan_ref,
            "seal_record": seal_bytes(bundle),
            "deadline": until(),
        }
        assert owner.store_acceptance_seal(PEER, ACTOR, **arguments) == bundle.seal_sha256
        assert owner.store_acceptance_seal(PEER, ACTOR, **arguments) == bundle.seal_sha256
        private = site.state / "workspaces" / ids["workspace_id"] / "acceptance" / "demo"
        assert SealStore(private).current() == bundle
        assert private.stat().st_mode & 0o077 == 0
        assert not (site.source / ".fa" / "seal-current.json").exists()
        assert site.metadata(ids)["status"] == "OWNED"


@pytest.mark.parametrize(
    "tamper", ["grant", "revision", "plan", "closure", "extra", "link", "slug", "size", "mode", "supersede"]
)
def test_authority_refuses_unbound_acceptance_seal_without_writing(site: Site, tamper: str) -> None:
    from fa.inner_loop.acceptance_bundle import seal_bytes
    from tests.test_ai_native_acceptance_collection import _mint

    root, plan_ref = _acceptance_store_case(site)
    if tamper == "extra":
        (root / "extra.py").write_text("extra")
    if tamper == "link":
        (root / "link").symlink_to("pytest.ini")
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        if tamper == "extra":
            (root / "extra.py").unlink()
        if tamper == "link":
            (root / "link").unlink()
        bundle = _mint(root, revision_id="rev-" + "1" * 32 if tamper == "revision" else ids["revision_id"])
        if tamper == "closure":
            (root / "pytest.ini").write_text("[pytest]\n")
            bundle = _mint(root, revision_id=ids["revision_id"])
        if tamper == "size":
            files = list(bundle.closure.files)
            files[0] = replace(files[0], size=files[0].size + 1)
            bundle = replace(bundle, closure=replace(bundle.closure, files=tuple(files)))
        if tamper == "mode":
            files = list(bundle.closure.files)
            files[0] = replace(files[0], mode=0o777)
            bundle = replace(bundle, closure=replace(bundle.closure, files=tuple(files)))
        if tamper == "supersede":
            bundle = replace(bundle, supersedes_sha256="a" * 64)
        if tamper == "plan":
            plan_ref = replace(plan_ref, sha256="0" * 64)
        with pytest.raises(SupervisorError) as error:
            owner.store_acceptance_seal(
                PEER,
                ACTOR,
                capability="0" * 64 if tamper == "grant" else grant.capability,
                project_slug="other" if tamper == "slug" else "demo",
                plan_ref=plan_ref,
                seal_record=seal_bytes(bundle),
                deadline=until(),
            )
        assert error.value.code == (
            "UNAUTHORIZED" if tamper == "grant" else "STALE_REVISION" if tamper == "revision" else "INPUT_POLICY"
        )
        assert not (site.state / "workspaces" / ids["workspace_id"] / "acceptance").exists()


def test_authority_seal_refuses_corrupt_predecessor_without_reconstruction(site: Site) -> None:
    from fa.inner_loop.acceptance_bundle import seal_bytes
    from tests.test_ai_native_acceptance_collection import _mint

    root, plan_ref = _acceptance_store_case(site)
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        args = {
            "capability": grant.capability,
            "project_slug": "demo",
            "plan_ref": plan_ref,
            "seal_record": seal_bytes(bundle),
            "deadline": until(),
        }
        owner.store_acceptance_seal(PEER, ACTOR, **args)
        private = site.state / "workspaces" / ids["workspace_id"] / "acceptance" / "demo" / ".fa"
        pointer_before = (private / "seal-current.json").read_bytes()
        record = private / "seals" / f"{bundle.seal_sha256}.json"
        record.unlink()
        with pytest.raises(SupervisorError) as error:
            owner.store_acceptance_seal(PEER, ACTOR, **args)
        assert error.value.code == "DURABILITY_UNKNOWN"
        assert not record.exists() and (private / "seal-current.json").read_bytes() == pointer_before
        assert not owner.ready


def test_authority_seal_refuses_while_write_view_unsettled(site: Site) -> None:
    from fa.inner_loop.acceptance_bundle import seal_bytes
    from tests.test_ai_native_acceptance_collection import _mint
    from tests.test_execution_views import create, native_profile

    root, plan_ref = _acceptance_store_case(site)
    with site.owner(view_profile=native_profile()) as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        create(owner, ids, grant)
        with pytest.raises(SupervisorError) as error:
            owner.store_acceptance_seal(
                PEER,
                ACTOR,
                capability=grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                seal_record=seal_bytes(bundle),
                deadline=until(),
            )
        assert error.value.code == "WORKSPACE_BUSY"
        assert not (site.state / "workspaces" / ids["workspace_id"] / "acceptance").exists()


def test_authority_seal_does_not_follow_private_directory_symlink(site: Site, tmp_path: Path) -> None:
    from fa.inner_loop.acceptance_bundle import seal_bytes
    from tests.test_ai_native_acceptance_collection import _mint

    root, plan_ref = _acceptance_store_case(site)
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        private = site.state / "workspaces" / ids["workspace_id"] / "acceptance" / "demo"
        private.mkdir(parents=True, mode=0o700)
        private.parent.chmod(0o700)
        outside = tmp_path / "outside"
        outside.mkdir()
        (private / ".fa").symlink_to(outside, target_is_directory=True)
        with pytest.raises(SupervisorError) as error:
            owner.store_acceptance_seal(
                PEER,
                ACTOR,
                capability=grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                seal_record=seal_bytes(bundle),
                deadline=until(),
            )
        assert error.value.code == "DURABILITY_UNKNOWN"
        assert list(outside.iterdir()) == []


def test_authority_keeps_two_projects_seal_pointers_independent(site: Site) -> None:
    import shutil
    from datetime import date

    from fa.inner_loop.acceptance_bundle import mint_seal, seal_bytes
    from fa.inner_loop.acceptance_seal_store import SealStore
    from fa.inner_loop.plan_admission import PlanRef, bind_dispositions
    from fa.inner_loop.plan_v2 import parse_plan
    from tests.test_ai_native_acceptance_collection import _COLLECTED, _PLAN_BYTES, _mint
    from tests.test_ai_native_plan_v2 import _ROADMAP, grant_declarations

    root, first_ref = _acceptance_store_case(site)
    other_root = site.source / "worklogs" / "seals" / "acceptance"
    shutil.copytree(root, other_root)
    other_plan = _PLAN_BYTES.replace(b"worklogs/demo/", b"worklogs/seals/")
    other_path = "worklogs/seals/increments/increment-01-demo.md"
    (site.source / other_path).parent.mkdir(parents=True)
    (site.source / other_path).write_bytes(other_plan)
    declarations = tuple(
        replace(
            item,
            evidence=replace(item.evidence, target=item.evidence.target.replace("worklogs/demo/", "worklogs/seals/")),
        )
        for item in grant_declarations()
    )
    graph = bind_dispositions(
        parse_plan(roadmap=_ROADMAP, increment=other_plan.decode()), declarations, today=date(2026, 11, 20)
    )
    other_ref = PlanRef(other_path, "EXPLICIT", hashlib.sha256(other_plan).hexdigest())
    collected = {
        key.replace("worklogs/demo/", "worklogs/seals/"): [
            node.replace("worklogs/demo/", "worklogs/seals/") for node in values
        ]
        for key, values in _COLLECTED.items()
    }
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        first = _mint(root, revision_id=ids["revision_id"])
        second = mint_seal(
            graph=graph,
            plan_bytes=other_plan,
            revision_id=ids["revision_id"],
            sealed_root="worklogs/seals/acceptance",
            acceptance_root=other_root,
            collected=collected,
        )
        for slug, plan, bundle in (("demo", first_ref, first), ("seals", other_ref, second)):
            assert (
                owner.store_acceptance_seal(
                    PEER,
                    ACTOR,
                    capability=grant.capability,
                    project_slug=slug,
                    plan_ref=plan,
                    seal_record=seal_bytes(bundle),
                    deadline=until(),
                )
                == bundle.seal_sha256
            )
        private = site.state / "workspaces" / ids["workspace_id"] / "acceptance"
        assert SealStore(private / "demo").current() == first
        assert SealStore(private / "seals").current() == second


def test_authority_seal_readback_failure_is_uncertain_not_success(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    from fa.inner_loop.acceptance_bundle import AcceptanceBundleError, seal_bytes
    from fa.inner_loop.acceptance_seal_store import SealStore
    from tests.test_ai_native_acceptance_collection import _mint

    root, plan_ref = _acceptance_store_case(site)
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])

        original_current = SealStore.current
        calls = 0

        def fail_readback(store: SealStore) -> Any:
            nonlocal calls
            calls += 1
            if calls == 1:
                return original_current(store)
            raise AcceptanceBundleError("seal-pointer-unreadable")

        monkeypatch.setattr(SealStore, "current", fail_readback)
        with pytest.raises(SupervisorError) as error:
            owner.store_acceptance_seal(
                PEER,
                ACTOR,
                capability=grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                seal_record=seal_bytes(bundle),
                deadline=until(),
            )
        assert error.value.code == "DURABILITY_UNKNOWN" and not owner.ready
        pointer = site.state / "workspaces" / ids["workspace_id"] / "acceptance/demo/.fa/seal-current.json"
        assert pointer.exists(), "a failed readback cannot be reported as an effect-free refusal"


def test_authority_seal_survives_release_and_service_restart(site: Site) -> None:
    from fa.inner_loop.acceptance_bundle import seal_bytes
    from fa.inner_loop.acceptance_seal_store import SealStore
    from tests.test_ai_native_acceptance_collection import _mint

    root, plan_ref = _acceptance_store_case(site)
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        owner.store_acceptance_seal(
            PEER,
            ACTOR,
            capability=grant.capability,
            project_slug="demo",
            plan_ref=plan_ref,
            seal_record=seal_bytes(bundle),
            deadline=until(),
        )
        site.release(owner, ids, grant)
    with site.owner() as recovered:
        assert site.register(recovered) == ids
        grant = site.claim(recovered, ids)
        assert (
            recovered.store_acceptance_seal(
                PEER,
                ACTOR,
                capability=grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                seal_record=seal_bytes(bundle),
                deadline=until(),
            )
            == bundle.seal_sha256
        )
        private = site.state / "workspaces" / ids["workspace_id"] / "acceptance" / "demo"
        assert SealStore(private).current() == bundle


@pytest.mark.parametrize("remnant", ["record", "temporary-pointer", "unexpected-entry"])
def test_authority_refuses_missing_pointer_with_evidence_of_prior_write(site: Site, remnant: str) -> None:
    from fa.inner_loop.acceptance_bundle import seal_bytes
    from tests.test_ai_native_acceptance_collection import _mint

    root, plan_ref = _acceptance_store_case(site)
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        args = {
            "capability": grant.capability,
            "project_slug": "demo",
            "plan_ref": plan_ref,
            "seal_record": seal_bytes(bundle),
            "deadline": until(),
        }
        owner.store_acceptance_seal(PEER, ACTOR, **args)
        private = site.state / "workspaces" / ids["workspace_id"] / "acceptance/demo/.fa"
        pointer = private / "seal-current.json"
        record = private / "seals" / f"{bundle.seal_sha256}.json"
        pointer.unlink()
        if remnant != "record":
            record.unlink()
            (private / (".seal-current-interrupted" if remnant == "temporary-pointer" else "unexpected")).write_bytes(
                b"evidence"
            )
        before = {str(p.relative_to(private)): p.read_bytes() for p in private.rglob("*") if p.is_file()}
        with pytest.raises(SupervisorError) as error:
            owner.store_acceptance_seal(PEER, ACTOR, **args)
        assert error.value.code == "DURABILITY_UNKNOWN"
        assert not owner.ready and not pointer.exists()
        assert {str(p.relative_to(private)): p.read_bytes() for p in private.rglob("*") if p.is_file()} == before


def test_authority_refuses_remint_after_project_metadata_loss_and_restart(site: Site) -> None:
    import shutil

    from fa.inner_loop.acceptance_bundle import seal_bytes
    from tests.test_ai_native_acceptance_collection import _mint

    root, plan_ref = _acceptance_store_case(site)
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        owner.store_acceptance_seal(
            PEER,
            ACTOR,
            capability=grant.capability,
            project_slug="demo",
            plan_ref=plan_ref,
            seal_record=seal_bytes(bundle),
            deadline=until(),
        )
        site.release(owner, ids, grant)
    binding = site.state / "workspaces" / ids["workspace_id"]
    assert (binding / "acceptance-started-demo").is_file()
    shutil.rmtree(binding / "acceptance" / "demo")
    with site.owner() as owner:
        assert site.register(owner) == ids
        grant = site.claim(owner, ids)
        with pytest.raises(SupervisorError) as error:
            owner.store_acceptance_seal(
                PEER,
                ACTOR,
                capability=grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                seal_record=seal_bytes(bundle),
                deadline=until(),
            )
        assert error.value.code == "DURABILITY_UNKNOWN" and not owner.ready
        private = binding / "acceptance" / "demo" / ".fa"
        assert not (private / "seal-current.json").exists()
        assert list((private / "seals").iterdir()) == []


def test_authority_persists_mint_started_before_store_write(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    from fa.inner_loop.acceptance_bundle import AcceptanceBundleError, seal_bytes
    from fa.inner_loop.acceptance_seal_store import SealStore
    from tests.test_ai_native_acceptance_collection import _mint

    root, plan_ref = _acceptance_store_case(site)
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        marker = site.state / "workspaces" / ids["workspace_id"] / "acceptance-started-demo"

        def interrupt(_store: SealStore, _bundle: Any) -> Any:
            assert marker.is_file() and marker.stat().st_size == 0
            raise AcceptanceBundleError("injected-before-write")

        monkeypatch.setattr(SealStore, "store", interrupt)
        with pytest.raises(SupervisorError) as error:
            owner.store_acceptance_seal(
                PEER,
                ACTOR,
                capability=grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                seal_record=seal_bytes(bundle),
                deadline=until(),
            )
        assert error.value.code == "DURABILITY_UNKNOWN" and not owner.ready
        assert marker.is_file()
        assert not (marker.parent / "acceptance/demo/.fa/seal-current.json").exists()


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "content"])
def test_authority_rejects_invalid_history_marker(site: Site, tmp_path: Path, kind: str) -> None:
    from fa.inner_loop.acceptance_bundle import seal_bytes
    from tests.test_ai_native_acceptance_collection import _mint

    root, plan_ref = _acceptance_store_case(site)
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        marker = site.state / "workspaces" / ids["workspace_id"] / "acceptance-started-demo"
        outside = tmp_path / "outside-marker"
        outside.write_bytes(b"safe")
        outside.chmod(0o600)
        if kind == "symlink":
            marker.symlink_to(outside)
        elif kind == "hardlink":
            os.link(outside, marker)
        else:
            marker.write_bytes(b"invalid")
            marker.chmod(0o600)
        with pytest.raises(SupervisorError) as error:
            owner.store_acceptance_seal(
                PEER,
                ACTOR,
                capability=grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                seal_record=seal_bytes(bundle),
                deadline=until(),
            )
        assert error.value.code == "DURABILITY_UNKNOWN" and not owner.ready
        assert outside.read_bytes() == b"safe"
        assert not (marker.parent / "acceptance/demo/.fa/seal-current.json").exists()


@pytest.mark.parametrize(
    "tamper", ["test-id", "contract", "selector", "nodeid", "attested-contract", "invariant", "scope", "probe"]
)
def test_authority_rejects_self_consistent_seal_with_foreign_plan_semantics(site: Site, tamper: str) -> None:
    from fa.inner_loop.acceptance_bundle import load_seal, seal_bytes
    from tests.test_ai_native_acceptance_collection import _mint

    root, plan_ref = _acceptance_store_case(site)
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        selector = bundle.selectors[0]
        attestation = bundle.attestations[0]
        if tamper == "test-id":
            bundle = replace(bundle, selectors=(replace(selector, test_id="TEST-9.9"),))
        elif tamper == "contract":
            bundle = replace(bundle, selectors=(replace(selector, ct_id="CT-9.9"),))
        elif tamper == "selector":
            bundle = replace(
                bundle, selectors=(replace(selector, selector=selector.selector.replace("test_publish", "test_extra")),)
            )
        elif tamper == "nodeid":
            bundle = replace(
                bundle, selectors=(replace(selector, nodeid=selector.nodeid.replace("test_publish", "test_extra")),)
            )
        elif tamper == "attested-contract":
            foreign = "CT-9.9"
            bundle = replace(
                bundle,
                attested=(foreign,),
                pending=(foreign,) if bundle.pending else (),
                attestations=(replace(attestation, contract_id=foreign),),
            )
        elif tamper == "invariant":
            bundle = replace(bundle, attestations=(replace(attestation, invariant_id="INV-9"),))
        elif tamper == "scope":
            bundle = replace(bundle, attestations=(replace(attestation, scope_sha256="0" * 64),))
        else:
            bundle = replace(
                bundle,
                attestations=(
                    replace(attestation, artifact="probe:worklogs/demo/acceptance/probes/missing.sh@host:w4-ubuntu"),
                ),
            )
        raw = seal_bytes(bundle)
        assert load_seal(raw).seal_sha256, "forgery must pass the record's own digest and shape checks"
        with pytest.raises(SupervisorError) as error:
            owner.store_acceptance_seal(
                PEER,
                ACTOR,
                capability=grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                seal_record=raw,
                deadline=until(),
            )
        assert error.value.code == "INPUT_POLICY"
        binding = site.state / "workspaces" / ids["workspace_id"]
        assert not (binding / "acceptance").exists()
        assert not (binding / "acceptance-started-demo").exists()
        assert owner.ready


def test_authority_rejects_plan_consistent_selector_outside_sealed_closure(site: Site) -> None:
    from fa.inner_loop.acceptance_bundle import load_seal, seal_bytes
    from tests.test_ai_native_acceptance_collection import _PLAN_BYTES, _mint

    root, plan_ref = _acceptance_store_case(site)
    old = "worklogs/demo/acceptance/tests/test_publish.py"
    foreign = "tests/test_foreign.py"
    raw_plan = _PLAN_BYTES.replace(old.encode(), foreign.encode())
    assert raw_plan != _PLAN_BYTES
    (site.source / plan_ref.workspace_relative_path).write_bytes(raw_plan)
    plan_ref = replace(plan_ref, sha256=hashlib.sha256(raw_plan).hexdigest())
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        row = bundle.selectors[0]
        forged = replace(
            bundle,
            plan_sha256=plan_ref.sha256,
            selectors=(
                replace(row, selector=row.selector.replace(old, foreign), nodeid=row.nodeid.replace(old, foreign)),
            ),
        )
        raw = seal_bytes(forged)
        assert load_seal(raw).plan_sha256 == plan_ref.sha256
        with pytest.raises(SupervisorError) as error:
            owner.store_acceptance_seal(
                PEER,
                ACTOR,
                capability=grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                seal_record=raw,
                deadline=until(),
            )
        assert error.value.code == "INPUT_POLICY"
        assert not (site.state / "workspaces" / ids["workspace_id"] / "acceptance").exists()


def test_authority_applies_canonical_closure_rules_to_revision(site: Site) -> None:
    from fa.inner_loop.acceptance_bundle import load_seal, seal_bytes
    from fa.inner_loop.acceptance_closure import ClosureFile, closure_digest
    from tests.test_ai_native_acceptance_collection import _mint

    root, plan_ref = _acceptance_store_case(site)
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
    # Construct a revision containing a prohibited nested conftest, and a record
    # whose hashes and sizes nevertheless match every actual file.
    raw_conftest = b"# hidden fixture policy\n"
    (root / "tests/conftest.py").write_bytes(raw_conftest)
    # Register the modified source as a fresh independent workspace.
    fresh = Site(state=site.state.parent / "fresh-state", roots=site.roots, source=site.source)
    fresh.state.mkdir(mode=0o700)
    with fresh.owner() as owner:
        ids = _register_acceptance_fixture(fresh, owner)
        grant = fresh.claim(owner, ids)
        files = tuple(
            sorted(
                (
                    *bundle.closure.files,
                    ClosureFile(
                        "tests/conftest.py",
                        hashlib.sha256(raw_conftest).hexdigest(),
                        len(raw_conftest),
                        bundle.closure.files[0].mode,
                    ),
                ),
                key=lambda item: item.path,
            )
        )
        closure = replace(
            bundle.closure,
            files=files,
            total_bytes=sum(item.size for item in files),
            digest=closure_digest((item.path, item.sha256) for item in files),
        )
        forged = replace(bundle, revision_id=ids["revision_id"], closure=closure)
        raw = seal_bytes(forged)
        assert load_seal(raw).closure.digest == closure.digest
        with pytest.raises(SupervisorError) as error:
            owner.store_acceptance_seal(
                PEER,
                ACTOR,
                capability=grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                seal_record=raw,
                deadline=until(),
            )
        assert error.value.code == "INPUT_POLICY"
        assert not (fresh.state / "workspaces" / ids["workspace_id"] / "acceptance").exists()


def test_real_bootstrap_origin_allows_seal_but_lost_state_forbids_remint(site: Site, tmp_path: Path) -> None:
    import shutil

    from fa.inner_loop.acceptance_bundle import seal_bytes
    from fa.inner_loop.plan_admission import PlanRef
    from tests.test_ai_native_acceptance_collection import _PLAN_BYTES, _mint, _tree

    staging = tmp_path / "author"
    root = _tree(staging)
    plan_path = "worklogs/demo/increments/increment-01-demo.md"
    files = {
        f"worklogs/demo/acceptance/{p.relative_to(root).as_posix()}": p.read_bytes()
        for p in root.rglob("*")
        if p.is_file()
    }
    files[plan_path] = _PLAN_BYTES
    plan_ref = PlanRef(plan_path, "EXPLICIT", hashlib.sha256(_PLAN_BYTES).hexdigest())
    with site.owner() as owner:
        ids = site.register(owner)
        grant = site.claim(owner, ids)
        prepared = owner.store_bundle(
            PEER,
            ACTOR,
            capability=grant.capability,
            project_slug="demo",
            increment_slug="demo",
            files=files,
            expected_base_revision=ids["revision_id"],
            operation_id="op-" + "1" * 32,
            deadline=until(),
        )
        installed = owner.install_project(
            PEER,
            ACTOR,
            capability=grant.capability,
            validated_bundle_id=prepared["validated_bundle_id"],
            project_slug="demo",
            deadline=until(),
        )
        origin = site.state / "workspaces" / ids["workspace_id"] / "acceptance-origin-demo.json"
        record = json.loads(origin.read_bytes())
        assert (record["workspace_id"], record["revision_id"], record["operation_id"]) == (
            ids["workspace_id"],
            installed["revision_id"],
            installed["operation_id"],
        )
        bundle = _mint(site.source / "worklogs/demo/acceptance", revision_id=installed["revision_id"])
        assert (
            owner.store_acceptance_seal(
                PEER,
                ACTOR,
                capability=grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                seal_record=seal_bytes(bundle),
                deadline=until(),
            )
            == bundle.seal_sha256
        )
        assert (
            owner.read_acceptance_seal(
                PEER,
                ACTOR,
                capability=grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                expected_revision=installed["revision_id"],
                deadline=until(),
            )
            == bundle
        )
        site.release(owner, ids, grant)
    shutil.rmtree(site.state)
    with site.owner() as restored:
        ids = site.register(restored)
        grant = site.claim(restored, ids)
        bundle = _mint(site.source / "worklogs/demo/acceptance", revision_id=ids["revision_id"])
        with pytest.raises(SupervisorError) as error:
            restored.store_acceptance_seal(
                PEER,
                ACTOR,
                capability=grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                seal_record=seal_bytes(bundle),
                deadline=until(),
            )
        assert error.value.code == "INPUT_POLICY"
        binding = site.state / "workspaces" / ids["workspace_id"]
        assert not (binding / "acceptance").exists()
        assert not (binding / "acceptance-started-demo").exists()


@pytest.mark.parametrize("damage", ["missing", "wrong-workspace", "symlink", "oversize"])
def test_authority_refuses_invalid_bootstrap_origin_without_seal_writes(site: Site, damage: str) -> None:
    from fa.inner_loop.acceptance_bundle import seal_bytes
    from tests.test_ai_native_acceptance_collection import _mint

    root, plan_ref = _acceptance_store_case(site)
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        path = site.state / "workspaces" / ids["workspace_id"] / "acceptance-origin-demo.json"
        if damage == "missing":
            path.unlink()
        elif damage == "symlink":
            path.unlink()
            path.symlink_to(site.source / "base.txt")
        elif damage == "oversize":
            path.write_bytes(b"x" * (workspace._ACCEPTANCE_ORIGIN_MAX_BYTES + 1))
        else:
            record = json.loads(path.read_bytes())
            record["workspace_id"] = "ws-" + "0" * 32
            path.write_text(json.dumps(record))
        with pytest.raises(SupervisorError) as error:
            owner.store_acceptance_seal(
                PEER,
                ACTOR,
                capability=grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                seal_record=seal_bytes(bundle),
                deadline=until(),
            )
        assert error.value.code in ("INPUT_POLICY", "CORRUPT_STATE")
        assert not (path.parent / "acceptance").exists()
        assert not (path.parent / "acceptance-started-demo").exists()


def test_origin_prevents_remint_when_store_and_marker_are_both_lost(site: Site) -> None:
    import shutil

    from fa.inner_loop.acceptance_bundle import seal_bytes
    from tests.test_ai_native_acceptance_collection import _mint

    root, plan_ref = _acceptance_store_case(site)
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        args = {
            "capability": grant.capability,
            "project_slug": "demo",
            "plan_ref": plan_ref,
            "seal_record": seal_bytes(bundle),
            "deadline": until(),
        }
        owner.store_acceptance_seal(PEER, ACTOR, **args)
        site.release(owner, ids, grant)
    binding = site.state / "workspaces" / ids["workspace_id"]
    origin = binding / "acceptance-origin-demo.json"
    before = origin.read_bytes()
    assert json.loads(before)["seal_state"] == "started"
    shutil.rmtree(binding / "acceptance" / "demo")
    (binding / "acceptance-started-demo").unlink()
    with site.owner() as owner:
        assert site.register(owner) == ids
        grant = site.claim(owner, ids)
        args.update(capability=grant.capability, deadline=until())
        with pytest.raises(SupervisorError) as error:
            owner.store_acceptance_seal(PEER, ACTOR, **args)
        assert error.value.code == "DURABILITY_UNKNOWN" and not owner.ready
        assert origin.read_bytes() == before
        assert not (binding / "acceptance/demo/.fa/seal-current.json").exists()
        assert not (binding / "acceptance-started-demo").exists()


def test_origin_started_is_durable_before_any_seal_store_write(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    from fa.inner_loop.acceptance_bundle import AcceptanceBundleError, seal_bytes
    from fa.inner_loop.acceptance_seal_store import SealStore
    from tests.test_ai_native_acceptance_collection import _mint

    root, plan_ref = _acceptance_store_case(site)
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        origin = site.state / "workspaces" / ids["workspace_id"] / "acceptance-origin-demo.json"
        assert json.loads(origin.read_bytes())["seal_state"] == "fresh"

        def interrupted(_store: SealStore, _bundle: Any) -> Any:
            assert json.loads(origin.read_bytes())["seal_state"] == "started"
            raise AcceptanceBundleError("injected")

        monkeypatch.setattr(SealStore, "store", interrupted)
        with pytest.raises(SupervisorError) as error:
            owner.store_acceptance_seal(
                PEER,
                ACTOR,
                capability=grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                seal_record=seal_bytes(bundle),
                deadline=until(),
            )
        assert error.value.code == "DURABILITY_UNKNOWN" and not owner.ready
        assert json.loads(origin.read_bytes())["seal_state"] == "started"


def test_origin_fresh_with_existing_pointer_is_refused(site: Site) -> None:
    from fa.inner_loop.acceptance_bundle import seal_bytes
    from tests.test_ai_native_acceptance_collection import _mint

    root, plan_ref = _acceptance_store_case(site)
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        args = {
            "capability": grant.capability,
            "project_slug": "demo",
            "plan_ref": plan_ref,
            "seal_record": seal_bytes(bundle),
            "deadline": until(),
        }
        owner.store_acceptance_seal(PEER, ACTOR, **args)
        binding = site.state / "workspaces" / ids["workspace_id"]
        origin = binding / "acceptance-origin-demo.json"
        record = json.loads(origin.read_bytes())
        record["seal_state"] = "fresh"
        origin.write_text(json.dumps(record))
        pointer = binding / "acceptance/demo/.fa/seal-current.json"
        before = pointer.read_bytes()
        with pytest.raises(SupervisorError) as error:
            owner.store_acceptance_seal(PEER, ACTOR, **args)
        assert error.value.code == "DURABILITY_UNKNOWN" and not owner.ready
        assert pointer.read_bytes() == before


def test_interrupted_origin_transition_cannot_retry_as_fresh(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    from fa.inner_loop.acceptance_bundle import seal_bytes
    from tests.test_ai_native_acceptance_collection import _mint

    root, plan_ref = _acceptance_store_case(site)
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        args = {
            "capability": grant.capability,
            "project_slug": "demo",
            "plan_ref": plan_ref,
            "seal_record": seal_bytes(bundle),
            "deadline": until(),
        }
        replace = _replace_private_bytes

        def lose_reply(fd: int, name: str, raw: bytes) -> None:
            replace(fd, name, raw)
            if name == "acceptance-origin-demo.json":
                raise OSError(5, "injected post-replace failure")

        monkeypatch.setattr(workspace, "_replace_private_bytes", lose_reply)
        with pytest.raises(SupervisorError) as error:
            owner.store_acceptance_seal(PEER, ACTOR, **args)
        assert error.value.code == "DURABILITY_UNKNOWN" and not owner.ready
        monkeypatch.undo()
    binding = site.state / "workspaces" / ids["workspace_id"]
    assert json.loads((binding / "acceptance-origin-demo.json").read_bytes())["seal_state"] == "started"
    with site.owner() as owner:
        assert site.register(owner) == ids
        with pytest.raises(SupervisorError) as error:
            site.claim(owner, ids)
        # The interrupted writer remains fenced on restart; no automatic retry.
        assert error.value.code == "WORKSPACE_BUSY"
        assert not (binding / "acceptance/demo/.fa/seal-current.json").exists()


def test_private_seal_read_binds_plan_and_survives_code_only_publication(site: Site) -> None:
    from fa.inner_loop.acceptance_bundle import seal_bytes
    from tests.test_ai_native_acceptance_collection import _mint
    from tests.test_execution_views import native_profile
    from tests.test_workspace_publication import _publish, _seal, _source_root, _stop, _view

    root, plan_ref = _acceptance_store_case(site)
    # Identical plan bytes at a second path are not the same plan identity.
    alternate = site.source / "worklogs/demo/increments/increment-02-copy.md"
    alternate.write_bytes((site.source / plan_ref.workspace_relative_path).read_bytes())
    with site.owner(view_profile=native_profile()) as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        owner.store_acceptance_seal(
            PEER,
            ACTOR,
            capability=grant.capability,
            project_slug="demo",
            plan_ref=plan_ref,
            seal_record=seal_bytes(bundle),
            deadline=until(),
        )
        args = {
            "capability": grant.capability,
            "project_slug": "demo",
            "plan_ref": plan_ref,
            "expected_revision": ids["revision_id"],
            "deadline": until(),
        }
        assert owner.read_acceptance_seal(PEER, ACTOR, **args) == bundle
        view = _view(owner, ids, grant, plan_ref=plan_ref)
        source = _source_root(site, view)
        (source / "src").mkdir(exist_ok=True)
        (source / "src" / "feature.py").write_text("value = 1\n")
        _stop(owner, view)
        published = _publish(owner, view, _seal(owner, view))
        assert published.revision_id != bundle.revision_id
        args["expected_revision"] = published.revision_id
        args["deadline"] = until()
        assert owner.read_acceptance_seal(PEER, ACTOR, **args) == bundle
        with pytest.raises(SupervisorError) as stale:
            owner.read_acceptance_seal(PEER, ACTOR, **{**args, "expected_revision": ids["revision_id"]})
        assert stale.value.code == "STALE_REVISION"
        alternate_ref = replace(plan_ref, workspace_relative_path="worklogs/demo/increments/increment-02-copy.md")
        with pytest.raises(SupervisorError) as error:
            owner.read_acceptance_seal(PEER, ACTOR, **{**args, "plan_ref": alternate_ref})
        assert error.value.code == "INPUT_POLICY"


@pytest.mark.parametrize(
    "damage",
    [
        "missing-pointer",
        "missing-record",
        "pointer-symlink",
        "origin-missing",
        "missing-store",
        "missing-views",
        "foreign-grant",
    ],
)
def test_private_seal_read_fails_closed_without_writes(site: Site, tmp_path: Path, damage: str) -> None:
    import shutil

    from fa.inner_loop.acceptance_bundle import seal_bytes
    from tests.test_ai_native_acceptance_collection import _mint

    root, plan_ref = _acceptance_store_case(site)
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        owner.store_acceptance_seal(
            PEER,
            ACTOR,
            capability=grant.capability,
            project_slug="demo",
            plan_ref=plan_ref,
            seal_record=seal_bytes(bundle),
            deadline=until(),
        )
        binding = site.state / "workspaces" / ids["workspace_id"]
        pointer = binding / "acceptance/demo/.fa/seal-current.json"
        record = pointer.parent / "seals" / f"{bundle.seal_sha256}.json"
        if damage == "missing-pointer":
            pointer.unlink()
        elif damage == "missing-record":
            record.unlink()
        elif damage == "pointer-symlink":
            outside = tmp_path / "foreign"
            outside.write_bytes(pointer.read_bytes())
            pointer.unlink()
            pointer.symlink_to(outside)
        elif damage == "origin-missing":
            (binding / "acceptance-origin-demo.json").unlink()
        elif damage == "missing-store":
            shutil.rmtree(binding / "acceptance" / "demo")
        elif damage == "missing-views":
            shutil.rmtree(binding / "views")
        before = {
            str(p.relative_to(binding)): p.read_bytes()
            for p in binding.rglob("*")
            if p.is_file() and not p.is_symlink()
        }
        with pytest.raises(SupervisorError) as error:
            owner.read_acceptance_seal(
                PEER,
                ACTOR,
                capability="0" * 64 if damage == "foreign-grant" else grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                expected_revision=ids["revision_id"],
                deadline=until(),
            )
        assert error.value.code == (
            "UNAUTHORIZED"
            if damage == "foreign-grant"
            else "INPUT_POLICY"
            if damage in {"origin-missing", "missing-store"}
            else "CORRUPT_STATE"
        )
        assert {
            str(p.relative_to(binding)): p.read_bytes()
            for p in binding.rglob("*")
            if p.is_file() and not p.is_symlink()
        } == before
        if damage == "missing-store":
            assert not (binding / "acceptance" / "demo").exists()


@pytest.mark.parametrize("damage", ["changed", "added", "deleted", "mode", "empty-dir", "directory-mode", "plan"])
def test_private_seal_read_refuses_changed_published_closure_or_plan(site: Site, damage: str) -> None:
    from fa.inner_loop.acceptance_bundle import seal_bytes
    from tests.test_ai_native_acceptance_collection import _mint
    from tests.test_execution_views import native_profile
    from tests.test_workspace_publication import _publish, _seal, _source_root, _stop, _view

    root, plan_ref = _acceptance_store_case(site)
    with site.owner(view_profile=native_profile()) as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        owner.store_acceptance_seal(
            PEER,
            ACTOR,
            capability=grant.capability,
            project_slug="demo",
            plan_ref=plan_ref,
            seal_record=seal_bytes(bundle),
            deadline=until(),
        )
        # Diagnostic publication without a plan-bound fence, to produce a genuine
        # revision with drift; this is not permission for a coder to change a seal.
        view = _view(owner, ids, grant)
        source = _source_root(site, view)
        target = source / bundle.sealed_root / bundle.closure.files[0].path
        if damage == "changed":
            target.write_bytes(target.read_bytes() + b"\n# drift\n")
        elif damage == "added":
            (source / bundle.sealed_root / "new.py").write_text("extra\n")
        elif damage == "deleted":
            target.unlink()
        elif damage == "mode":
            target.chmod(0o755)
        elif damage == "empty-dir":
            (source / bundle.sealed_root / "empty-dir").mkdir()
        elif damage == "directory-mode":
            (source / bundle.sealed_root / "tests").chmod(0o700)
        else:
            path = source / plan_ref.workspace_relative_path
            path.write_bytes(path.read_bytes() + b"\n# drift\n")
        _stop(owner, view)
        candidate = _publish(owner, view, _seal(owner, view))
        pointer = site.state / "workspaces" / ids["workspace_id"] / "acceptance/demo/.fa/seal-current.json"
        before = pointer.read_bytes()
        with pytest.raises(SupervisorError) as error:
            owner.read_acceptance_seal(
                PEER,
                ACTOR,
                capability=grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                expected_revision=candidate.revision_id,
                deadline=until(),
            )
        assert error.value.code == "INPUT_POLICY"
        assert pointer.read_bytes() == before


def test_private_seal_replay_rejects_same_bytes_at_different_plan_path(site: Site) -> None:
    from fa.inner_loop.acceptance_bundle import seal_bytes
    from tests.test_ai_native_acceptance_collection import _mint

    root, plan_ref = _acceptance_store_case(site)
    alternate = site.source / "worklogs/demo/increments/increment-02-copy.md"
    alternate.write_bytes((site.source / plan_ref.workspace_relative_path).read_bytes())
    alternate_ref = replace(plan_ref, workspace_relative_path="worklogs/demo/increments/increment-02-copy.md")
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        args = {
            "capability": grant.capability,
            "project_slug": "demo",
            "plan_ref": plan_ref,
            "seal_record": seal_bytes(bundle),
            "deadline": until(),
        }
        owner.store_acceptance_seal(PEER, ACTOR, **args)
        binding = site.state / "workspaces" / ids["workspace_id"]
        origin = binding / "acceptance-origin-demo.json"
        pointer = binding / "acceptance/demo/.fa/seal-current.json"
        before = (origin.read_bytes(), pointer.read_bytes())
        with pytest.raises(SupervisorError) as error:
            owner.store_acceptance_seal(PEER, ACTOR, **{**args, "plan_ref": alternate_ref})
        assert error.value.code == "DURABILITY_UNKNOWN" and not owner.ready
        assert (origin.read_bytes(), pointer.read_bytes()) == before


def test_private_seal_read_refuses_unsettled_view(site: Site) -> None:
    from fa.inner_loop.acceptance_bundle import seal_bytes
    from tests.test_ai_native_acceptance_collection import _mint
    from tests.test_execution_views import create, native_profile

    root, plan_ref = _acceptance_store_case(site)
    with site.owner(view_profile=native_profile()) as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        owner.store_acceptance_seal(
            PEER,
            ACTOR,
            capability=grant.capability,
            project_slug="demo",
            plan_ref=plan_ref,
            seal_record=seal_bytes(bundle),
            deadline=until(),
        )
        create(owner, ids, grant)
        with pytest.raises(SupervisorError) as error:
            owner.read_acceptance_seal(
                PEER,
                ACTOR,
                capability=grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                expected_revision=ids["revision_id"],
                deadline=until(),
            )
        assert error.value.code == "WORKSPACE_BUSY"


def test_private_seal_read_does_not_initialize_fresh_storage(site: Site) -> None:
    from tests.test_execution_views import native_profile

    _, plan_ref = _acceptance_store_case(site)
    with site.owner(view_profile=native_profile()) as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        binding = site.state / "workspaces" / ids["workspace_id"]
        before = (binding / "acceptance-origin-demo.json").read_bytes()
        with pytest.raises(SupervisorError) as error:
            owner.read_acceptance_seal(
                PEER,
                ACTOR,
                capability=grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                expected_revision=ids["revision_id"],
                deadline=until(),
            )
        assert error.value.code == "INPUT_POLICY"
        assert (binding / "acceptance-origin-demo.json").read_bytes() == before
        assert not (binding / "acceptance").exists()
        assert not (binding / "acceptance-started-demo").exists()


def test_private_seal_read_rejects_self_consistent_foreign_mapping(site: Site) -> None:
    from fa.inner_loop.acceptance_bundle import load_seal, seal_bytes
    from tests.test_ai_native_acceptance_collection import _mint

    root, plan_ref = _acceptance_store_case(site)
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        owner.store_acceptance_seal(
            PEER,
            ACTOR,
            capability=grant.capability,
            project_slug="demo",
            plan_ref=plan_ref,
            seal_record=seal_bytes(bundle),
            deadline=until(),
        )
        forged = replace(bundle, selectors=(replace(bundle.selectors[0], ct_id="CT-9.9"),))
        raw = seal_bytes(forged)
        digest = load_seal(raw).seal_sha256
        private = site.state / "workspaces" / ids["workspace_id"] / "acceptance/demo/.fa"
        record = private / "seals" / f"{digest}.json"
        record.write_bytes(raw)
        record.chmod(0o600)
        pointer = private / "seal-current.json"
        pointer.write_text(json.dumps({"schema_version": 1, "seal_sha256": digest}))
        before = pointer.read_bytes()
        with pytest.raises(SupervisorError) as error:
            owner.read_acceptance_seal(
                PEER,
                ACTOR,
                capability=grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                expected_revision=ids["revision_id"],
                deadline=until(),
            )
        assert error.value.code == "INPUT_POLICY"
        assert pointer.read_bytes() == before and record.read_bytes() == raw


def test_seal_origin_handles_json_escaped_plan_path_before_starting(site: Site) -> None:
    """A valid filesystem component can expand substantially in JSON encoding."""
    from fa.inner_loop.acceptance_bundle import seal_bytes
    from tests.test_ai_native_acceptance_collection import _mint

    root, plan_ref = _acceptance_store_case(site)
    old = site.source / plan_ref.workspace_relative_path
    name = "\x01" * 180 + ".md"
    replacement = old.parent / name
    old.rename(replacement)
    plan_ref = replace(plan_ref, workspace_relative_path=f"worklogs/demo/increments/{name}")
    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        grant = site.claim(owner, ids)
        bundle = _mint(root, revision_id=ids["revision_id"])
        assert (
            owner.store_acceptance_seal(
                PEER,
                ACTOR,
                capability=grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                seal_record=seal_bytes(bundle),
                deadline=until(),
            )
            == bundle.seal_sha256
        )
        origin = site.state / "workspaces" / ids["workspace_id"] / "acceptance-origin-demo.json"
        assert len(origin.read_bytes()) > 1024
        assert json.loads(origin.read_bytes())["plan_relative"] == plan_ref.workspace_relative_path
        assert (
            owner.read_acceptance_seal(
                PEER,
                ACTOR,
                capability=grant.capability,
                project_slug="demo",
                plan_ref=plan_ref,
                expected_revision=ids["revision_id"],
                deadline=until(),
            )
            == bundle
        )


def test_origin_size_limit_refuses_before_durable_transition(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    from fa.inner_loop.acceptance_bundle import AcceptanceBundleError
    from fa.inner_loop.plan_admission import PlanRef

    with site.owner() as owner:
        ids = _register_acceptance_fixture(site, owner)
        binding = owner._binding(ids["workspace_id"])
        origin = site.state / "workspaces" / ids["workspace_id"] / "acceptance-origin-demo.json"
        before = origin.read_bytes()
        record = owner._require_acceptance_origin(binding, "demo")
        monkeypatch.setattr(workspace, "_ACCEPTANCE_ORIGIN_MAX_BYTES", 512)
        plan = PlanRef("worklogs/demo/increments/" + "\x01" * 180 + ".md", "EXPLICIT", "1" * 64)
        with pytest.raises(AcceptanceBundleError) as error:
            owner._advance_acceptance_origin(binding, "demo", record, False, plan)
        assert error.value.rule == "seal-origin-invalid"
        assert origin.read_bytes() == before
        assert json.loads(before)["seal_state"] == "fresh"
