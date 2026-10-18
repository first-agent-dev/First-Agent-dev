"""C0/C3 real authority/journal/FS dispatch scopes; no Docker/C1/terminality claim."""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from fa.execution import workspace
from fa.execution.journal import JournalError
from fa.execution.supervisor import PeerIdentity, SupervisorError
from fa.execution.types import ExecutionContractError, GrantReply
from fa.execution.workspace import WorkspaceAuthority
from fa.inner_loop.plan_admission import PlanRef, read_plan_snapshot
from fa.inner_loop.workflow_artifacts import _replace_private_bytes
from tests.test_execution_readers import pin, read, record_path, ref, release
from tests.test_execution_views import create, native_profile, write
from tests.test_execution_workspace import ACTOR, OTHER, PEER, Site, ok, until
from tests.test_execution_workspace import site as site


@contextmanager
def setup(
    site: Site, *, reader: bool = False, cache: bool = True, plan_ref: PlanRef | None = None, formal: bool = False
) -> Generator[tuple[WorkspaceAuthority, GrantReply]]:
    approved = site.state.parent / "approved-cache"
    approved.mkdir(mode=0o755)
    with WorkspaceAuthority(
        site.state,
        approved_roots={"projects": site.roots},
        controller_uids=frozenset({PEER.uid}),
        lock_timeout_ms=1000,
        view_profile=native_profile(),
        approved_cache=approved if cache else None,
    ) as owner:
        ids = ok(lambda: site.register(owner))
        if reader:
            grant = ok(lambda: pin(owner, ids, plan_ref=plan_ref, formal=formal))
        else:
            lease = ok(lambda: site.claim(owner, ids))
            grant = ok(lambda: create(owner, ids, lease, plan_ref=plan_ref, formal=formal))
        yield owner, grant


def request(grant: GrantReply, **changes: Any) -> dict[str, Any]:
    rid = uuid4().hex
    req: dict[str, Any] = {
        "protocol_version": 1,
        "request_id": rid,
        "op": "exec",
        "namespace": ACTOR.to_dict(),
        "view_ref": ref(grant).to_dict(),
        "capability": grant.capability,
        "payload": {
            "operation_id": "op-" + rid,
            "profile_id": native_profile().profile_id,
            "command": "printf never-sent-by-authority",
            "cwd": "src",
            "timeout_ms": 500,
            "session_id": "main",
        },
    }
    req.update(changes)
    return req


def claim(owner: WorkspaceAuthority, req: dict[str, Any]) -> None:
    assert owner.journal.reserve(req).fresh
    owner.journal.begin(req["payload"]["operation_id"], ACTOR)


def journal_record(owner: WorkspaceAuthority, req: dict[str, Any]) -> dict[str, Any]:
    record = owner.journal.lookup(req["payload"]["operation_id"], ACTOR)
    assert record is not None
    return record


def attempt_admit(owner: WorkspaceAuthority, peer: PeerIdentity, req: dict[str, Any], *, deadline: float) -> None:
    # Negative probes retire an unexpectedly returned scope before their oracle fails.
    # No destructor/GC cleanup, leaked tickets or teardown timeout mutation credit.
    scope = owner.admit(peer, req, deadline=deadline)
    scope.close()


def close(owner: WorkspaceAuthority, grant: GrantReply) -> None:
    ok(lambda: owner.close_admission(PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until()))


def drain(owner: WorkspaceAuthority, grant: GrantReply, deadline: float | None = None) -> None:
    if deadline is not None:
        owner.drain(PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=deadline)
    else:
        ok(lambda: owner.drain(PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until()))


@pytest.mark.parametrize("reader", [False, True])
def test_actual_admission_retains_trusted_inputs_and_operation_before_bounded_effect(site: Site, reader: bool) -> None:
    with setup(site, reader=reader) as (owner, grant):
        req = request(grant)
        claim(owner, req)
        with ok(lambda: owner.admit(PEER, req, deadline=until())) as scope:
            assert len(owner._gates[ref(grant).view_id].active) == 1
            record = json.loads(record_path(site, grant).read_text())
            assert record["operation_ids"] == [req["payload"]["operation_id"]]
            assert scope.inputs.source.is_dir() and scope.inputs.scratch.is_dir() and scope.inputs.cache.is_dir()
            assert (scope.inputs.source / "untracked.txt").read_bytes() == b"untracked"
            assert scope.input_tree_sha256 == record["input_tree_sha256"]
            assert scope.inputs.context.plan_ref is None
            with scope.effect():
                (scope.inputs.scratch / "native-effect").write_text("one bounded dispatch effect")
            assert (scope.inputs.scratch / "native-effect").read_text() == "one bounded dispatch effect"
            spec = scope.profile.create_spec(
                operation_id=req["payload"]["operation_id"],
                view=ref(grant),
                source=scope.inputs.source,
                scratch=scope.inputs.scratch,
                cache=scope.inputs.cache,
            )
            assert spec["body"]["HostConfig"]["Mounts"][0]["ReadOnly"] is reader
        assert not owner._gates[ref(grant).view_id].active
        assert journal_record(owner, req)["state"] == "EXECUTING"
        assert (site.source / "untracked.txt").read_text() == "untracked"


@pytest.mark.parametrize("kind", ["principal", "namespace", "capability", "purpose"])
def test_forged_admission_has_no_active_registration_or_inputs(site: Site, kind: str) -> None:
    with setup(site) as (owner, grant):
        req = request(grant)
        peer = PEER
        if kind == "principal":
            peer = replace(PEER, gid=PEER.gid + 1)
        elif kind == "namespace":
            req["namespace"] = OTHER.to_dict()
        elif kind == "capability":
            req["capability"] = "f" * 64
        else:
            req["view_ref"]["purpose"] = "PROVISIONING"
        with pytest.raises(SupervisorError) as failure:
            attempt_admit(owner, peer, req, deadline=until())
        assert failure.value.code == "UNAUTHORIZED"
        assert not owner._inputs and not any(g.active for g in owner._gates.values())


@pytest.mark.parametrize("kind", ["missing", "reserved-only", "unknown", "cancelled", "different-input"])
def test_durable_original_journal_claim_required_before_admission(site: Site, kind: str) -> None:
    with setup(site) as (owner, grant):
        req = request(grant)
        if kind != "missing":
            owner.journal.reserve(req)
            if kind != "reserved-only":
                owner.journal.begin(req["payload"]["operation_id"], ACTOR)
            if kind == "unknown":
                owner.journal.mark_unknown(req["payload"]["operation_id"], ACTOR)
            if kind == "cancelled":
                owner.journal.request_cancel(req["payload"]["operation_id"], ACTOR)
            if kind == "different-input":
                req["payload"]["command"] = "different"
        with pytest.raises(SupervisorError) as failure:
            attempt_admit(owner, PEER, req, deadline=until())
        assert failure.value.code == "EXECUTION_UNKNOWN"
        assert not owner._inputs
        assert json.loads(record_path(site, grant).read_text())["operation_ids"] == []


@pytest.mark.parametrize("kind", ["profile", "timeout", "mode", "cache"])
def test_approved_profile_and_cache_are_required_not_inferred(site: Site, kind: str) -> None:
    with setup(site, cache=kind != "cache") as (owner, grant):
        req = request(grant)
        if kind == "profile":
            req["payload"]["profile_id"] = "other-profile"
        elif kind == "timeout":
            req["payload"]["timeout_ms"] = native_profile().max_command_ms + 1
        elif kind == "mode":
            req["payload"]["session_id"] = None
        claim(owner, req)
        with pytest.raises(SupervisorError) as failure:
            attempt_admit(owner, PEER, req, deadline=until())
        assert failure.value.code == "UNAPPROVED_PROFILE" and not owner._inputs


def test_original_scope_can_continue_after_start_unknown_but_second_admission_never_can(site: Site) -> None:
    with setup(site) as (owner, grant):
        req = request(grant)
        claim(owner, req)
        oid = req["payload"]["operation_id"]
        with ok(lambda: owner.admit(PEER, req, deadline=until())) as scope:
            with pytest.raises(SupervisorError) as failure:
                attempt_admit(owner, PEER, req, deadline=until())
            assert failure.value.code == "EXECUTION_UNKNOWN"
            owner.journal.record_container(oid, ACTOR, "a" * 64)
            with owner.journal.start_once(oid, ACTOR) as cid:
                assert cid == "a" * 64
            assert journal_record(owner, req)["state"] == "UNKNOWN"
            with scope.effect():
                (scope.inputs.scratch / "after-start").write_text("original only")
            assert (scope.inputs.scratch / "after-start").read_text() == "original only"
        with pytest.raises(SupervisorError) as failure:
            attempt_admit(owner, PEER, req, deadline=until())
        assert failure.value.code == "EXECUTION_UNKNOWN"


def test_closed_queued_scope_cannot_emit_effect_and_drain_does_not_release_writer(site: Site) -> None:
    with setup(site) as (owner, grant):
        req = request(grant)
        claim(owner, req)
        scope = ok(lambda: owner.admit(PEER, req, deadline=until()))
        try:
            close(owner, grant)
            close(owner, grant)
            assert json.loads(record_path(site, grant).read_text())["state"] == "STOPPING"
            with pytest.raises(SupervisorError) as failure:
                with scope.effect():
                    (scope.inputs.scratch / "late").write_text("must not happen")
            assert failure.value.code == "VIEW_CLOSED" and not (scope.inputs.scratch / "late").exists()
            with pytest.raises(SupervisorError) as failure:
                drain(owner, grant, time.monotonic() + 0.03)
            assert failure.value.code == "BACKEND_UNAVAILABLE"
            assert owner._bindings[ref(grant).workspace_id].writer is not None
        finally:
            scope.close()
        drain(owner, grant)
        assert not owner._gates[ref(grant).view_id].active
        assert owner._bindings[ref(grant).workspace_id].metadata["status"] == "OWNED"


def test_cancellation_after_admit_blocks_send_without_reclaim_or_reexecution(site: Site) -> None:
    with setup(site) as (owner, grant):
        req = request(grant)
        claim(owner, req)
        with ok(lambda: owner.admit(PEER, req, deadline=until())) as scope:
            owner.journal.request_cancel(req["payload"]["operation_id"], ACTOR)
            with pytest.raises(SupervisorError) as failure:
                with scope.effect():
                    (scope.inputs.scratch / "cancelled-effect").write_text("must not happen")
            assert failure.value.code == "EXECUTION_UNKNOWN"
            assert not (scope.inputs.scratch / "cancelled-effect").exists()
            assert journal_record(owner, req)["cancel_requested"]


@pytest.mark.parametrize("reader", [False, True])
def test_same_close_gate_denies_file_io_and_preserves_other_view(site: Site, reader: bool) -> None:
    with setup(site, reader=reader) as (owner, grant):
        other = ok(
            lambda: pin(owner, {"workspace_id": ref(grant).workspace_id, "revision_id": ref(grant).base_revision})
        )
        assert ref(other).view_id != ref(grant).view_id
        close(owner, grant)
        with pytest.raises(SupervisorError) as failure:
            read(owner, grant)
        assert failure.value.code == "VIEW_CLOSED"
        if not reader:
            with pytest.raises(SupervisorError) as failure:
                write(owner, grant)
            assert failure.value.code == "VIEW_CLOSED"
        else:
            assert ok(lambda: release(owner, grant)) == {"released": True}
        assert ok(lambda: read(owner, other))["content"] == "untracked"
        assert (site.source / "untracked.txt").read_text() == "untracked"


def test_live_effect_blocks_close_then_scoped_dispatch_blocks_drain_until_retired(site: Site) -> None:
    with setup(site) as (owner, grant):
        req = request(grant)
        claim(owner, req)
        scope = ok(lambda: owner.admit(PEER, req, deadline=until()))
        entered, proceed, closing = threading.Event(), threading.Event(), threading.Event()

        def effect() -> None:
            with scope.effect():
                entered.set()
                assert proceed.wait(4)
                (scope.inputs.scratch / "effect").write_text("done")

        def closing_gate() -> None:
            closing.set()
            close(owner, grant)

        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                future = pool.submit(effect)
                try:
                    assert entered.wait(2)
                    closing_future = pool.submit(closing_gate)
                    assert closing.wait(2)
                    with pytest.raises(TimeoutError):
                        closing_future.result(timeout=0.03)
                finally:
                    proceed.set()
                future.result(timeout=3)
                closing_future.result(timeout=3)
                draining = pool.submit(drain, owner, grant)
                try:
                    with pytest.raises(TimeoutError):
                        draining.result(timeout=0.03)
                finally:
                    scope.close()
                assert draining.result(timeout=3) is None
            assert (scope.inputs.scratch / "effect").read_text() == "done"
        finally:
            proceed.set()
            scope.close()


def test_shutdown_keeps_native_input_fds_until_scope_retires(site: Site) -> None:
    with setup(site) as (owner, grant):
        req = request(grant)
        claim(owner, req)
        scope = ok(lambda: owner.admit(PEER, req, deadline=until()))
        closing = threading.Event()

        def shutdown() -> None:
            closing.set()
            owner.__exit__(None, None, None)

        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(shutdown)
                try:
                    assert closing.wait(2)
                    with pytest.raises(TimeoutError):
                        future.result(timeout=0.03)
                    assert os.fstat(scope.inputs.source_fd).st_ino == scope.inputs.source.stat().st_ino
                finally:
                    scope.close()
                future.result(timeout=3)
            assert scope.inputs.source_fd == scope.inputs.scratch_fd == scope.inputs.cache_fd == -1
        finally:
            scope.close()


@pytest.mark.parametrize("path", ["source", "scratch", "cache"])
def test_substituted_trusted_execution_input_cannot_be_used(site: Site, path: str) -> None:
    with setup(site) as (owner, grant):
        req = request(grant)
        claim(owner, req)
        with ok(lambda: owner.admit(PEER, req, deadline=until())) as scope:
            target: Path = getattr(scope.inputs, path)
            target.rename(target.with_name(target.name + "-old"))
            target.mkdir(mode=0o755)
            with pytest.raises(SupervisorError) as failure:
                with scope.effect():
                    (scope.inputs.scratch / "bad").write_text("must not happen")
            assert failure.value.code == "CORRUPT_STATE"


def test_readonly_projection_is_not_cell_writable_and_privileged_tamper_is_rejected(site: Site) -> None:
    with setup(site, reader=True) as (owner, grant):
        req = request(grant)
        claim(owner, req)
        with ok(lambda: owner.admit(PEER, req, deadline=until())) as scope:
            source = scope.inputs.source / "untracked.txt"
            assert source.stat().st_mode & 0o222 == 0
            assert scope.inputs.source.stat().st_mode & 0o222 == 0
            with pytest.raises(PermissionError):
                source.write_text("tampered")
            # A privileged/host-authority edit must still be detected at the effect boundary.
            os.chmod(source, 0o644)
            source.write_text("tampered")
            with pytest.raises(SupervisorError) as failure:
                with scope.effect():
                    (scope.inputs.scratch / "bad").write_text("must not happen")
            assert failure.value.code == "CORRUPT_STATE"
            assert ok(lambda: read(owner, grant))["content"] == "untracked"
        with pytest.raises(SupervisorError) as failure:
            release(owner, grant)
        assert failure.value.code == "WORKSPACE_BUSY"
        assert record_path(site, grant).exists()


def test_closed_scope_and_expired_budget_cannot_be_reopened_or_loan_time(site: Site) -> None:
    with setup(site) as (owner, grant):
        req = request(grant)
        claim(owner, req)
        with pytest.raises(SupervisorError) as failure:
            attempt_admit(owner, PEER, req, deadline=time.monotonic() - 1)
        assert failure.value.code == "BACKEND_UNAVAILABLE"
        scope = ok(lambda: owner.admit(PEER, req, deadline=until()))
        scope.close()
        scope.close()
        with pytest.raises(SupervisorError) as failure:
            with scope.effect():
                raise AssertionError("closed scope admitted an effect")
        assert failure.value.code == "VIEW_CLOSED" and not owner._gates[ref(grant).view_id].active


@pytest.mark.parametrize("operation", ["close", "admit"])
def test_durable_gate_and_operation_retention_faults_fence_owner(
    site: Site, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    with setup(site) as (owner, grant):
        req = request(grant)
        claim(owner, req)

        def broken(fd: int, name: str, raw: bytes) -> None:
            if name == "view.json":
                raise OSError("injected retention failure")
            _replace_private_bytes(fd, name, raw)

        monkeypatch.setattr(workspace, "_replace_private_bytes", broken)
        with pytest.raises(SupervisorError) as failure:
            if operation == "close":
                owner.close_admission(PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until())
            else:
                attempt_admit(owner, PEER, req, deadline=until())
        assert failure.value.code == "DURABILITY_UNKNOWN" and not owner._healthy
        assert not any(g.active for g in owner._gates.values())
        assert (site.source / "untracked.txt").read_text() == "untracked"


@pytest.mark.parametrize("kind", ["relative", "control", "project-root"])
def test_cache_is_explicit_private_configuration_never_a_project_or_control_mount(site: Site, kind: str) -> None:
    cache = Path("relative") if kind == "relative" else site.state if kind == "control" else site.roots
    with pytest.raises(ExecutionContractError):
        site.owner(view_profile=native_profile(), approved_cache=cache)


def test_bounded_run_send_serializes_native_cancel_before_ack(site: Site) -> None:
    with setup(site) as (owner, grant):
        req = request(grant)
        claim(owner, req)
        with ok(lambda: owner.admit(PEER, req, deadline=until())) as scope:
            entered, proceed, cancelling = threading.Event(), threading.Event(), threading.Event()

            def send() -> None:
                with scope.send():
                    entered.set()
                    assert proceed.wait(4)
                    (scope.inputs.scratch / "one-frame").write_bytes(b"one actual bounded send stand-in")

            def cancel() -> None:
                cancelling.set()
                owner.journal.request_cancel(req["payload"]["operation_id"], ACTOR)

            with ThreadPoolExecutor(max_workers=2) as pool:
                sending = pool.submit(send)
                try:
                    assert entered.wait(2)
                    cancelled = pool.submit(cancel)
                    assert cancelling.wait(2)
                    with pytest.raises(TimeoutError):
                        cancelled.result(timeout=0.03)
                finally:
                    proceed.set()
                sending.result(timeout=3)
                cancelled.result(timeout=3)
            assert (scope.inputs.scratch / "one-frame").read_bytes() == b"one actual bounded send stand-in"
            assert journal_record(owner, req)["cancel_requested"]
            with pytest.raises(SupervisorError) as failure:
                with scope.send():
                    raise AssertionError("cancelled command sent again")
            assert failure.value.code == "EXECUTION_UNKNOWN"


def test_untrusted_cache_fails_before_readonly_projection_is_installed(site: Site) -> None:
    with setup(site, reader=True) as (owner, grant):
        (site.state.parent / "approved-cache").chmod(0o777)
        req = request(grant)
        claim(owner, req)
        with pytest.raises(SupervisorError) as failure:
            attempt_admit(owner, PEER, req, deadline=until())
        assert failure.value.code == "PATH_DENIED"
        assert not (record_path(site, grant).parent / "execution").exists()
        assert not any(g.active for g in owner._gates.values())


def test_partial_send_failure_is_uncertain_and_fences_authority(site: Site) -> None:
    with setup(site) as (owner, grant):
        req = request(grant)
        claim(owner, req)
        with ok(lambda: owner.admit(PEER, req, deadline=until())) as scope:
            with pytest.raises(SupervisorError) as failure:
                with scope.send():
                    (scope.inputs.scratch / "partial-frame").write_bytes(b"partial")
                    raise OSError("simulated frame write lost acknowledgement")
            assert failure.value.code == "DURABILITY_UNKNOWN"
            assert (scope.inputs.scratch / "partial-frame").read_bytes() == b"partial"
            assert not owner._healthy, "uncertain send left fresh effects enabled"


@pytest.mark.parametrize("reader", [False, True])
def test_actual_plan_rechecked_at_effect_boundary_for_working_and_readonly_sources(site: Site, reader: bool) -> None:
    (site.source / "plan.md").write_text("# Admitted plan\n")
    admitted = read_plan_snapshot(site.source, Path("plan.md")).ref
    with setup(site, reader=reader, plan_ref=admitted, formal=True) as (owner, grant):
        req = request(grant)
        claim(owner, req)
        with ok(lambda: owner.admit(PEER, req, deadline=until())) as scope:
            assert scope.inputs.context.plan_ref == admitted
            plan = scope.inputs.source / "plan.md"
            if reader:
                assert plan.stat().st_mode & 0o222 == 0
                os.chmod(plan, 0o644)
            plan.write_text("changed plan")
            with pytest.raises(SupervisorError) as failure:
                with scope.effect():
                    (scope.inputs.scratch / "bad").write_text("must not happen")
            assert failure.value.code == "INPUT_POLICY"
            assert not (scope.inputs.scratch / "bad").exists()


def test_reused_readonly_inputs_keep_exact_fds_for_new_command_not_new_projection(site: Site) -> None:
    before = len(list(Path("/proc/self/fd").iterdir()))
    with setup(site, reader=True) as (owner, grant):
        req = request(grant)
        claim(owner, req)
        with ok(lambda: owner.admit(PEER, req, deadline=until())) as first:
            identities = (first.inputs.source_fd, first.inputs.scratch_fd, first.inputs.cache_fd)
        active = len(list(Path("/proc/self/fd").iterdir()))
        req2 = request(grant)
        claim(owner, req2)
        with ok(lambda: owner.admit(PEER, req2, deadline=until())) as second:
            assert identities == (second.inputs.source_fd, second.inputs.scratch_fd, second.inputs.cache_fd)
            with second.send():
                (second.inputs.scratch / "next-frame").write_bytes(b"not a command replay")
            assert (second.inputs.scratch / "next-frame").read_bytes() == b"not a command replay"
        assert len(list(Path("/proc/self/fd").iterdir())) == active
        assert json.loads(record_path(site, grant).read_text())["operation_ids"] == [
            req["payload"]["operation_id"],
            req2["payload"]["operation_id"],
        ]
    assert len(list(Path("/proc/self/fd").iterdir())) == before


def test_fresh_command_after_close_cannot_obtain_a_new_scope(site: Site) -> None:
    with setup(site) as (owner, grant):
        close(owner, grant)
        req = request(grant)
        claim(owner, req)
        with pytest.raises(SupervisorError) as failure:
            attempt_admit(owner, PEER, req, deadline=until())
        assert failure.value.code == "VIEW_CLOSED" and not owner._inputs


def test_journal_send_lock_wait_is_capped_by_original_absolute_deadline(site: Site) -> None:
    with setup(site) as (owner, grant):
        req = request(grant)
        claim(owner, req)
        digest = journal_record(owner, req)["input_sha256"]
        locked, proceed = threading.Event(), threading.Event()

        def hold() -> None:
            with owner.journal._transaction():
                locked.set()
                assert proceed.wait(4)

        with ThreadPoolExecutor(max_workers=1) as pool:
            holding = pool.submit(hold)
            try:
                assert locked.wait(2)
                started = time.monotonic()
                with pytest.raises(JournalError):
                    with owner.journal.send_guard(
                        req["payload"]["operation_id"],
                        ACTOR,
                        view=ref(grant),
                        input_sha256=digest,
                        deadline=started + 0.03,
                    ):
                        raise AssertionError("expired request acquired held send lock")
                assert time.monotonic() - started < 0.4, "journal borrowed its configured one-second budget"
            finally:
                proceed.set()
            holding.result(timeout=3)


def test_failed_readonly_projection_install_leaves_no_stale_copy_and_allows_retry(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    with setup(site, reader=True) as (owner, grant):
        req = request(grant)
        claim(owner, req)
        original = owner._validate_inputs
        calls = {"n": 0}

        def failing(ref: Any, inputs: Any, deadline: float) -> None:
            calls["n"] += 1
            if calls["n"] > 1:
                raise SupervisorError("CORRUPT_STATE")
            original(ref, inputs, deadline)

        monkeypatch.setattr(owner, "_validate_inputs", failing)
        with pytest.raises(SupervisorError) as failure:
            attempt_admit(owner, PEER, req, deadline=until())
        assert failure.value.code == "CORRUPT_STATE"
        projection = record_path(site, grant).parent / "execution"
        assert not projection.exists(), "failed install left a stale projection that blocks retry"
        monkeypatch.undo()
        with ok(lambda: owner.admit(PEER, req, deadline=until())) as scope:
            assert (scope.inputs.source / "untracked.txt").read_text() == "untracked"
