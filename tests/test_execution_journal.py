"""C0/C3 real protected-file journal; no Docker/ownership/completion attestation."""

from __future__ import annotations

import fcntl
import json
import os
import stat
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from fa.execution.journal import JournalError, OperationJournal
from fa.execution.types import Access, ExecutionContractError, GrantReply, NamespaceRef, Operation, ViewPurpose, ViewRef

RID = "1" * 32
OID = "op-" + RID
CAP = "2" * 64
CID = "3" * 64
SHA = "4" * 64
NS = NamespaceRef("session-1", "run-1")
VIEW = ViewRef("ws-" + "5" * 32, "view-" + "6" * 32, "rev-" + "7" * 32, "run-1", 1, Access.WRITE, ViewPurpose.PROJECT)


def request() -> dict[str, Any]:
    return {
        "protocol_version": 1,
        "request_id": RID,
        "op": "exec",
        "namespace": NS.to_dict(),
        "view_ref": VIEW.to_dict(),
        "capability": CAP,
        "payload": {
            "operation_id": OID,
            "profile_id": "interactive",
            "command": "unit fixture, never executed",
            "cwd": ".",
            "timeout_ms": 1000,
            "session_id": "main",
        },
    }


def result() -> dict[str, Any]:
    return {
        "receipt": {
            "schema_version": 1,
            "operation_id": OID,
            "namespace": NS.to_dict(),
            "workspace_id": VIEW.workspace_id,
            "view_id": VIEW.view_id,
            "owner_run_id": "run-1",
            "generation": 1,
            "revision_id": VIEW.base_revision,
            "original_revision_id": VIEW.base_revision,
            "input_tree_sha256": SHA,
            "plan_sha256": SHA,
            "profile_id": "interactive",
            "image_digest": "sha256:" + SHA,
            "state": "EXITED",
            "exit_code": 0,
            "timed_out": False,
            "stdout_tail": "unit result",
            "stderr_tail": "",
            "truncated": False,
            "duration_ms": 1,
            "terminal_barrier": False,
        }
    }


def journal(tmp_path: Path) -> OperationJournal:
    return OperationJournal(tmp_path / "operations", lock_timeout_ms=2000)


def test_durable_reservation_precedes_claim_and_start_cannot_be_reclaimed(tmp_path: Path) -> None:
    owner = journal(tmp_path)
    admission = owner.reserve(request())
    path = tmp_path / "operations" / (OID + ".json")
    assert admission.fresh is True
    assert json.loads(path.read_bytes()) == admission.record
    assert admission.record["state"] == "RESERVED"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert CAP.encode() not in path.read_bytes() and b"never executed" not in path.read_bytes()
    assert owner.reserve(request()).fresh is False
    owner.begin(OID, NS)
    with pytest.raises(JournalError):
        owner.begin(OID, NS)
    owner.record_container(OID, NS, CID)
    with owner.start_once(OID, NS) as container:
        assert container == CID
        assert json.loads(path.read_bytes())["state"] == "UNKNOWN"  # BEFORE the hypothetical bounded RPC.
    with pytest.raises(JournalError):
        with owner.start_once(OID, NS):
            pytest.fail("a second start claim was issued")
    owner.complete(OID, NS, result(), original_proof=CAP)
    observed = owner.lookup(OID, NS)
    assert observed is not None and observed["state"] == "DONE" and observed["result"] == result()
    original = path.read_bytes()
    owner.complete(OID, NS, result(), original_proof=CAP)
    assert path.read_bytes() == original
    assert owner.reserve(request()).fresh is False


def test_concurrent_duplicate_reservations_have_exactly_one_fresh_winner(tmp_path: Path) -> None:
    owner = journal(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as workers:
        admissions = list(workers.map(lambda _: owner.reserve(request()), range(16)))
    assert sum(a.fresh for a in admissions) == 1
    assert all(a.record["input_sha256"] == admissions[0].record["input_sha256"] for a in admissions)


def test_collision_namespace_and_command_changes_never_get_fresh_admission(tmp_path: Path) -> None:
    owner = journal(tmp_path)
    owner.reserve(request())
    for changed in [
        {**request(), "namespace": {**NS.to_dict(), "run_id": "other"}},
        {**request(), "payload": {**request()["payload"], "command": "changed"}},
    ]:
        with pytest.raises(JournalError) as caught:
            owner.reserve(changed)
        assert caught.value.code == "COLLISION"
    with pytest.raises(JournalError) as caught:
        owner.lookup(OID, NamespaceRef("session-1", "other"))
    assert caught.value.code == "UNAUTHORIZED"
    # Credentials are excluded from dedup input, NOT accepted as authorization:
    # only the real authority/cached-reply gate can decide whether to return data.
    assert owner.reserve({**request(), "capability": "a" * 64}).fresh is False


@pytest.mark.parametrize("after_begin", [False, True])
def test_cancel_before_start_persists_and_prevents_late_start(tmp_path: Path, after_begin: bool) -> None:
    owner = journal(tmp_path)
    owner.reserve(request())
    if after_begin:
        owner.begin(OID, NS)
        owner.record_container(OID, NS, CID)
    owner.request_cancel(OID, NS, view=VIEW)
    record = owner.lookup(OID, NS)
    assert record is not None and record["cancel_requested"] is True
    with pytest.raises(JournalError):
        if after_begin:
            with owner.start_once(OID, NS):
                pytest.fail("persisted cancellation permitted start")
        else:
            owner.begin(OID, NS)


def test_cancel_intent_requires_the_exact_operation_view(tmp_path: Path) -> None:
    owner = journal(tmp_path)
    owner.reserve(request())
    owner.begin(OID, NS)
    before = owner.lookup(OID, NS)
    foreign_view = ViewRef(
        VIEW.workspace_id,
        "view-" + "9" * 32,
        VIEW.base_revision,
        VIEW.owner_run_id,
        VIEW.generation,
        VIEW.access,
        VIEW.purpose,
    )
    with pytest.raises(JournalError) as caught:
        owner.request_cancel(OID, NS, view=foreign_view)
    assert caught.value.code == "UNAUTHORIZED"
    assert owner.lookup(OID, NS) == before
    owner.request_cancel(OID, NS, view=VIEW)
    record = owner.lookup(OID, NS)
    assert record is not None and record["cancel_requested"] is True


@pytest.mark.parametrize("after_begin", [False, True])
def test_restart_marks_unfinished_unknown_and_never_returns_fresh(tmp_path: Path, after_begin: bool) -> None:
    owner = journal(tmp_path)
    owner.reserve(request())
    if after_begin:
        owner.begin(OID, NS)
        owner.record_container(OID, NS, CID)
    restarted = journal(tmp_path)
    with restarted.single_supervisor():
        assert restarted.recover_uncertain() == 1
        assert restarted.recover_uncertain() == 0
    record = restarted.lookup(OID, NS)
    assert record is not None and record["state"] == "UNKNOWN" and record["result"] is None
    assert record["container_id"] == (CID if after_begin else None)
    assert restarted.reserve(request()).fresh is False
    with pytest.raises(JournalError):
        restarted.begin(OID, NS)


def test_owned_cell_inventory_includes_done_exec_records_but_unfinished_does_not(tmp_path: Path) -> None:
    owner = journal(tmp_path)
    owner.reserve(request())
    owner.begin(OID, NS)
    owner.record_container(OID, NS, CID)
    owner.complete(OID, NS, result(), original_proof=CAP)
    record = owner.lookup(OID, NS)
    assert record is not None and record["state"] == "DONE"
    assert owner.unfinished() == []
    assert owner.owned_cells() == [record]


def test_grant_completion_persists_only_projection_never_secret(tmp_path: Path) -> None:
    owner = journal(tmp_path)
    req = {
        **request(),
        "op": "handoff",
        "view_ref": None,
        "payload": {"target_namespace": NamespaceRef("session-1", "child", "run-1").to_dict()},
    }
    owner.reserve(req)
    owner.begin(OID, NS)
    grant = GrantReply(Operation.HANDOFF, "b" * 64, None, 1, VIEW.base_revision)
    owner.complete(OID, NS, grant, original_proof=CAP)
    raw = (tmp_path / "operations" / (OID + ".json")).read_bytes()
    assert CAP.encode() not in raw and grant.capability.encode() not in raw
    assert json.loads(raw)["result"] == {"view_ref": None, "generation": 1, "revision_id": VIEW.base_revision}
    assert "capability" not in json.loads(raw)["result"]


@pytest.mark.parametrize(
    "change",
    [
        {"operation_id": "op-" + "a" * 32},
        {"view_id": "view-" + "a" * 32},
        {"generation": 2},
        {"state": "UNKNOWN", "exit_code": None},
    ],
)
def test_wrong_or_indeterminate_receipt_cannot_be_journaled_done(tmp_path: Path, change: dict[str, Any]) -> None:
    owner = journal(tmp_path)
    owner.reserve(request())
    owner.begin(OID, NS)
    owner.record_container(OID, NS, CID)
    with pytest.raises((JournalError, ExecutionContractError)):
        owner.complete(OID, NS, {"receipt": {**result()["receipt"], **change}}, original_proof=CAP)
    record = owner.lookup(OID, NS)
    assert record is not None and record["state"] == "EXECUTING" and record["result"] is None


def test_fsync_failure_never_returns_successful_admission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    owner = journal(tmp_path)
    # Ensure directory/lock exist before injecting the publication durability fault.
    assert owner.lookup(OID, NS) is None
    real_fsync = os.fsync

    def fail_directory(fd: int) -> None:
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("private diagnostic must not escape")
        real_fsync(fd)

    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", fail_directory)
        with pytest.raises(JournalError) as caught:
            owner.reserve(request())
        assert caught.value.code == "DURABILITY_UNKNOWN"
        assert "private diagnostic" not in str(caught.value)
    # Replace may be visible already; a subsequent request still cannot get a
    # second fresh reservation. No successful admission was returned during fault.
    assert owner.reserve(request()).fresh is False


@pytest.mark.parametrize("alias", ["symlink", "hardlink", "corrupt"])
def test_aliased_or_corrupt_state_fails_closed_without_overwrite(tmp_path: Path, alias: str) -> None:
    owner = journal(tmp_path)
    owner.reserve(request())
    path = tmp_path / "operations" / (OID + ".json")
    witness = tmp_path / "witness"
    if alias == "corrupt":
        path.write_bytes(b"{bad json")
    else:
        witness.write_bytes(b"unchanged witness")
        witness.chmod(0o600)
        path.unlink()
        if alias == "symlink":
            path.symlink_to(witness)
        else:
            os.link(witness, path)
    before = path.read_bytes()
    with pytest.raises(JournalError):
        owner.reserve(request())
    assert path.read_bytes() == before
    if alias != "corrupt":
        assert witness.read_bytes() == b"unchanged witness"


def test_failed_start_rpc_retains_uncertainty_and_never_reclaims(tmp_path: Path) -> None:
    owner = journal(tmp_path)
    owner.reserve(request())
    owner.begin(OID, NS)
    owner.record_container(OID, NS, CID)
    attempts = 0
    with pytest.raises(JournalError) as caught:
        with owner.start_once(OID, NS):
            attempts += 1
            raise OSError("fixture lost start reply")
    assert caught.value.code == "DURABILITY_UNKNOWN" and attempts == 1
    record = owner.lookup(OID, NS)
    assert record is not None and record["state"] == "UNKNOWN" and record["container_id"] == CID
    with pytest.raises(JournalError):
        with owner.start_once(OID, NS):
            attempts += 1
    assert attempts == 1


@pytest.mark.parametrize("corruption", ["identity", "active-as-done", "extra-secret-key"])
def test_cross_field_or_extra_corrupt_record_never_looks_like_durable_done(tmp_path: Path, corruption: str) -> None:
    owner = journal(tmp_path)
    owner.reserve(request())
    owner.begin(OID, NS)
    owner.record_container(OID, NS, CID)
    owner.complete(OID, NS, result(), original_proof=CAP)
    path = tmp_path / "operations" / (OID + ".json")
    record = json.loads(path.read_bytes())
    if corruption == "identity":
        record["result"]["receipt"]["generation"] = 2
    elif corruption == "active-as-done":
        record["result"]["receipt"].update(state="UNKNOWN", exit_code=None)
    else:
        record["capability"] = CAP
    path.write_text(json.dumps(record))
    before = path.read_bytes()
    with pytest.raises(JournalError) as caught:
        owner.lookup(OID, NS)
    assert caught.value.code == "CORRUPT_STATE" and path.read_bytes() == before


def test_only_one_supervisor_holds_startup_recovery_scope(tmp_path: Path) -> None:
    owner = OperationJournal(tmp_path / "operations", lock_timeout_ms=10)
    second = OperationJournal(tmp_path / "operations", lock_timeout_ms=10)
    owner.reserve(request())
    with pytest.raises(JournalError):
        owner.recover_uncertain()
    with owner.single_supervisor():
        with pytest.raises(JournalError):
            with second.single_supervisor():
                pytest.fail("second supervisor acquired the live ownership lock")
        assert owner.recover_uncertain() == 1
    with second.single_supervisor():
        assert second.recover_uncertain() == 0
    with pytest.raises(JournalError):
        second.recover_uncertain()


def test_create_once_persists_uncertainty_before_callback_and_cid_before_start(tmp_path: Path) -> None:
    journal = OperationJournal(tmp_path / "ops", lock_timeout_ms=1000)
    reserved = journal.reserve(request())
    journal.begin(OID, NS)
    observed: list[dict[str, Any]] = []

    def create() -> str:
        observed.append(json.loads((tmp_path / "ops" / (OID + ".json")).read_text()))
        return CID

    assert journal.create_once(OID, NS, input_sha256=reserved.record["input_sha256"], create=create) == CID
    assert len(observed) == 1 and observed[0]["state"] == "UNKNOWN" and observed[0]["container_id"] is None
    record = journal.lookup(OID, NS)
    assert record is not None and record["state"] == "EXECUTING" and record["container_id"] == CID
    with pytest.raises(JournalError):
        journal.create_once(OID, NS, input_sha256=reserved.record["input_sha256"], create=create)
    assert len(observed) == 1


@pytest.mark.parametrize("bad", ["lost-reply", "invalid-cid", "cancel", "input"])
def test_uncertain_or_denied_create_claim_never_regains_permission(tmp_path: Path, bad: str) -> None:
    journal = OperationJournal(tmp_path / "ops", lock_timeout_ms=1000)
    reserved = journal.reserve(request())
    journal.begin(OID, NS)
    calls: list[str] = []

    def create() -> str:
        calls.append("called")
        if bad == "lost-reply":
            raise RuntimeError("opaque daemon diagnostic")
        return "invalid"

    if bad == "cancel":
        journal.request_cancel(OID, NS, view=VIEW)
    digest = "9" * 64 if bad == "input" else reserved.record["input_sha256"]
    with pytest.raises((RuntimeError, ExecutionContractError)):
        journal.create_once(OID, NS, input_sha256=digest, create=create)
    if bad in {"lost-reply", "invalid-cid"}:
        record = journal.lookup(OID, NS)
        assert record is not None and record["state"] == "UNKNOWN"
        with pytest.raises(JournalError):
            journal.create_once(OID, NS, input_sha256=digest, create=create)
    assert len(calls) == (0 if bad in {"cancel", "input"} else 1)


def test_failed_cid_persistence_keeps_unknown_and_cannot_retry_create(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = journal(tmp_path)
    admission = owner.reserve(request())
    owner.begin(OID, NS)
    original = owner._write
    calls: list[str] = []

    def write(fd: int, record: dict[str, Any]) -> None:
        if record["container_id"] is not None:
            raise JournalError("EXECUTION_UNKNOWN")  # Fault at CID durability boundary, not a Docker fault.
        original(fd, record)

    def create() -> str:
        calls.append("create")
        return CID

    monkeypatch.setattr(owner, "_write", write)
    with pytest.raises(JournalError):
        owner.create_once(OID, NS, input_sha256=admission.record["input_sha256"], create=create)
    record = owner.lookup(OID, NS)
    assert record is not None and record["state"] == "UNKNOWN"
    with pytest.raises(JournalError):
        owner.create_once(OID, NS, input_sha256=admission.record["input_sha256"], create=create)
    assert calls == ["create"]


def test_deadline_expiring_on_journal_lock_is_backend_unavailable_before_create(tmp_path: Path) -> None:
    owner = journal(tmp_path)
    admission = owner.reserve(request())
    owner.begin(OID, NS)
    assert owner.lookup(OID, NS) is not None  # Create the lock file before holding it.
    lock_path = tmp_path / "operations" / ".admission.lock"
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CLOEXEC)
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    calls: list[str] = []
    deadline = time.monotonic() + 0.05

    def create() -> str:
        calls.append("create")
        return CID

    try:
        with pytest.raises(JournalError) as caught:
            owner.create_once(
                OID,
                NS,
                input_sha256=admission.record["input_sha256"],
                create=create,
                deadline=deadline,
            )
        assert caught.value.code == "BACKEND_UNAVAILABLE"
        assert calls == []
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
    record = owner.lookup(OID, NS)
    assert record is not None and record["state"] == "EXECUTING" and record["container_id"] is None


def test_concurrent_create_claims_share_one_durable_permission(tmp_path: Path) -> None:
    first, second = journal(tmp_path), journal(tmp_path)
    admission = first.reserve(request())
    first.begin(OID, NS)
    calls: list[str] = []

    def create() -> str:
        calls.append("create")
        return CID

    def claim(owner: OperationJournal) -> str:
        try:
            return owner.create_once(OID, NS, input_sha256=admission.record["input_sha256"], create=create)
        except JournalError:
            return "denied"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(claim, (first, second)))
    assert sorted(outcomes) == [CID, "denied"] and calls == ["create"]
