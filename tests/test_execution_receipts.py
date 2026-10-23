"""E279 — `ExecutionReceipt` v1 over the admitted backend and real observations.

Classes (knowledge/skills/tests-writing):
  C3 — real `WorkspaceAuthority`, real journal on disk, literal HTTP Docker peer
       (`Endpoint`), real local PTY worker for the interactive case, real cgroup
       directory for the barrier;
  C1 — the one-shot cell uses the existing `FakeWorkerStream` double, because a
       real one-shot container needs an approved Docker host;
  C0 — the tail bound and the state mapping.

What must stay true (each test names the producer it kills):
  * `EXITED` needs the container's own exit to agree with the command's and, for
    a one-shot cell, a positive cgroup barrier;
  * an unobservable, mismatched, still-running or unpopulated cell is
    `EXECUTION_UNKNOWN`, never exit 0 and never a receipt;
  * `inspect` replays a DONE record without touching the daemon and never sends
    a RUN;
  * `inspect`/`cancel` refuse another view's operation;
  * a cancel receipt can never be `EXITED`, keeps the cancel operation's own id,
    and reports "no cell can appear" as a journal fact;
  * the receipt the issuer returns is accepted by the journal's completion and
    by the closed wire decoder.
"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from fa.execution.backend import CellBackend
from fa.execution.protocol import decode_reply, encode_json
from fa.execution.receipts import CommandReceipts, bounded_tail
from fa.execution.supervisor import SupervisorError
from fa.execution.types import ExecutionReceipt, NamespaceRef, Operation, ViewRef
from tests.test_execution_backend import (
    CID,
    Backend,
    FakeWorkerStream,
    ObservedEngine,
    claim,
    exec_request,
    native_profile,
)
from tests.test_execution_backend import backend as backend
from tests.test_execution_docker import Endpoint, Reply
from tests.test_execution_workspace import ACTOR, PEER, Site, until
from tests.test_execution_workspace import site as site

RECEIPT_KEYS = {
    "schema_version",
    "operation_id",
    "namespace",
    "workspace_id",
    "view_id",
    "owner_run_id",
    "generation",
    "revision_id",
    "original_revision_id",
    "input_tree_sha256",
    "plan_sha256",
    "profile_id",
    "image_digest",
    "state",
    "exit_code",
    "timed_out",
    "stdout_tail",
    "stderr_tail",
    "truncated",
    "duration_ms",
    "terminal_barrier",
}


def exited_observation(operation_id: str, view_id: str, *, exit_code: int = 0) -> dict[str, Any]:
    """A literal daemon answer for a stopped cell; nothing is inferred from it here."""
    profile = native_profile()
    return {
        "Id": CID,
        "Name": "/fa-job-" + operation_id.removeprefix("op-"),
        "Image": profile.image_digest,
        "Config": {
            "Image": profile.image,
            "Labels": {"fa.execution.operation_id": operation_id, "fa.execution.view_id": view_id},
        },
        "State": {
            "Status": "exited",
            "Running": False,
            "Paused": False,
            "Restarting": False,
            "Dead": False,
            "OOMKilled": False,
            "Pid": 0,
            "ExitCode": exit_code,
        },
    }


def running_observation(operation_id: str, view_id: str) -> dict[str, Any]:
    profile = native_profile()
    return {
        "Id": CID,
        "Name": "/fa-job-" + operation_id.removeprefix("op-"),
        "Image": profile.image_digest,
        "Config": {
            "Image": profile.image,
            "Labels": {"fa.execution.operation_id": operation_id, "fa.execution.view_id": view_id},
        },
        "State": {
            "Status": "running",
            "Running": True,
            "Paused": False,
            "Restarting": False,
            "Dead": False,
            "OOMKilled": False,
            "Pid": 4242,
            "ExitCode": 0,
        },
    }


def populated(cgroup_root: Path, *, value: int, container_id: str = CID) -> None:
    """Write the kernel's own answer for this cell."""
    directory = cgroup_root.joinpath(*native_profile().cgroup_parent.split("/")) / container_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "cgroup.events").write_text(f"populated {value}\nfrozen 0\n")


def issued(case: Backend, tmp_path: Path) -> CommandReceipts:
    return CommandReceipts(case.authority, case.owner(), case.docker(), cgroup_root=tmp_path, poll_interval_s=0.01)


def denied(code: str, call: Any) -> None:
    """A refusal must be an ASSERTION about the closed code, never a leak."""
    try:
        call()
    except SupervisorError as error:
        assert error.code == code, f"expected {code}; observed {error.code}"
        return
    raise AssertionError(f"expected {code}; observed success")


# ---------------------------------------------------------------------------
# C0 — the tail rule
# ---------------------------------------------------------------------------


def test_tails_keep_the_last_64_kib_and_never_split_a_codepoint() -> None:
    """producer-kill-check: cut at a character offset, or keep the head."""
    assert bounded_tail("short") == "short"
    # A distinctive head makes "kept the head" a different answer, not just a
    # different length: only the exact last 64 KiB satisfies both assertions.
    assert bounded_tail("HEAD" + "x" * 70_000) == "x" * (64 * 1024)
    text = "a" + "é" * 40_000  # 80 KB of two-byte characters
    tail = bounded_tail(text)
    assert len(tail.encode("utf-8")) == 64 * 1024
    assert tail == "é" * (64 * 1024 // 2) and "\ufffd" not in tail


# ---------------------------------------------------------------------------
# exec
# ---------------------------------------------------------------------------


def test_exec_issues_a_bound_receipt_the_journal_and_the_wire_accept(backend: Backend, tmp_path: Path) -> None:
    """producer-kill-check: fabricate identity, or skip the binding self-check."""
    request = exec_request(backend.grant, "1" * 32, "printf receipt")
    claim(backend.authority, request)
    operation_id = request["payload"]["operation_id"]
    backend.peer.replies.extend(backend.episode_replies(operation_id))
    backend.peer.replies.append(Reply(200, running_observation(operation_id, backend.view.view_id)))

    result = issued(backend, tmp_path).execute(PEER, request, deadline=until())
    receipt = result["receipt"]

    assert set(receipt) == RECEIPT_KEYS
    assert receipt["state"] == "EXITED" and receipt["exit_code"] == 0
    assert receipt["timed_out"] is False and receipt["truncated"] is False
    # An interactive shell stays alive by design: the barrier is stop_view's.
    assert receipt["terminal_barrier"] is False
    assert receipt["operation_id"] == operation_id
    assert receipt["namespace"] == ACTOR.to_dict()
    assert receipt["workspace_id"] == backend.view.workspace_id
    assert receipt["view_id"] == backend.view.view_id
    assert receipt["owner_run_id"] == backend.view.owner_run_id
    assert receipt["generation"] == backend.view.generation
    assert receipt["revision_id"] == backend.view.base_revision
    assert receipt["original_revision_id"] == backend.view.base_revision
    assert receipt["profile_id"] == native_profile().profile_id
    assert receipt["image_digest"] == native_profile().image_digest
    assert receipt["plan_sha256"] is None
    assert len(receipt["input_tree_sha256"]) == 64
    assert receipt["duration_ms"] >= 0
    assert "receipt" in receipt["stdout_tail"]

    # The two consumers that matter: the journal's completion and the wire codec.
    backend.authority.journal.complete(
        operation_id, NamespaceRef(**request["namespace"]), result, original_proof=request["capability"]
    )
    reply = decode_reply(
        encode_json(
            {
                "protocol_version": 1,
                "request_id": "1" * 32,
                "status": "OK",
                "result": result,
                "error": None,
            }
        ),
        operation=Operation.EXEC,
        request_id="1" * 32,
    )
    assert reply["result"]["receipt"]["operation_id"] == operation_id


def test_the_receipt_is_self_checked_before_it_is_sent(
    backend: Backend, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: build a receipt and return it without the binding check."""
    request = exec_request(backend.grant, "d" * 32, "printf checked")
    claim(backend.authority, request)
    operation_id = request["payload"]["operation_id"]
    backend.peer.replies.extend(backend.episode_replies(operation_id))
    backend.peer.replies.append(Reply(200, running_observation(operation_id, backend.view.view_id)))
    checked: list[dict[str, Any]] = []
    original = ExecutionReceipt.require_binding

    def spy(self: ExecutionReceipt, **kwargs: Any) -> None:
        checked.append(kwargs)
        original(self, **kwargs)

    monkeypatch.setattr(ExecutionReceipt, "require_binding", spy)
    issued(backend, tmp_path).execute(PEER, request, deadline=until())
    assert len(checked) == 1, "the receipt was returned without the binding self-check"
    assert checked[0]["view"] == backend.view and checked[0]["namespace"] == ACTOR


def test_the_input_tree_and_plan_come_from_the_view_record(
    backend: Backend, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: take the tree from the request or the worker."""
    request = exec_request(backend.grant, "2" * 32, "printf identity")
    claim(backend.authority, request)
    operation_id = request["payload"]["operation_id"]
    backend.peer.replies.extend(backend.episode_replies(operation_id))
    backend.peer.replies.append(Reply(200, running_observation(operation_id, backend.view.view_id)))

    seen: dict[str, Any] = {}
    original = backend.authority.execution_identity

    def spy(peer: Any, namespace: Any, **kwargs: Any) -> Any:
        seen["called"] = True
        return original(peer, namespace, **kwargs)

    monkeypatch.setattr(backend.authority, "execution_identity", spy)
    receipt = issued(backend, tmp_path).execute(PEER, request, deadline=until())["receipt"]
    assert seen.get("called") is True
    record = backend.authority.journal.lookup(operation_id, ACTOR)
    view_record = json.loads(
        (
            backend.authority._state
            / "workspaces"
            / backend.view.workspace_id
            / "views"
            / backend.view.view_id
            / "view.json"
        ).read_text()
    )
    assert receipt["input_tree_sha256"] == view_record["input_tree_sha256"]
    # The issuer issues a receipt; it never completes the operation. The start
    # write-ahead leaves the record durably UNKNOWN until the supervisor does.
    assert record is not None and record["state"] in {"EXECUTING", "UNKNOWN"}


def _one_shot(case_site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Backend, list[Any]]:
    """A noninteractive episode: fresh one-shot cell, null session, fake worker."""
    profile = replace(native_profile(), profile_id="verification", interactive=False)
    case = Backend(case_site, tmp_path, profile_override=profile)
    private = tmp_path / "private-one-shot"
    private.mkdir(mode=0o700)
    peer = Endpoint(private / "engine.sock")
    engine = ObservedEngine(peer.path, daemon_uid=os.getuid(), api_version="1.45", rpc_timeout_ms=1000)
    case.peer = peer
    case.engine = engine
    case.backend = CellBackend(case.authority, engine, case.authority.journal)
    streams: list[FakeWorkerStream] = []

    def attach(container_id: str, *, deadline: float) -> FakeWorkerStream:
        stream = FakeWorkerStream()
        streams.append(stream)
        return stream

    monkeypatch.setattr(case.engine, "attach", attach)
    return case, streams


def _one_shot_request(case: Backend, rid: str) -> dict[str, Any]:
    request = exec_request(case.grant, rid, "printf one-shot")
    request["payload"].update(profile_id=case.profile.profile_id, session_id=None)
    claim(case.authority, request)
    return request


def _close_one_shot(case: Backend) -> None:
    case.close()
    case.peer.close()


def test_a_one_shot_cell_is_exited_only_with_a_proven_barrier(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: report EXITED from the exit code alone."""
    case, streams = _one_shot(site, tmp_path, monkeypatch)
    try:
        request = _one_shot_request(case, "3" * 32)
        operation_id = request["payload"]["operation_id"]
        case.peer.replies.extend(
            [
                Reply(201, {"Id": CID, "Warnings": []}),
                Reply(204),
                Reply(200, running_observation(operation_id, case.view.view_id)),
                Reply(200, exited_observation(operation_id, case.view.view_id, exit_code=0)),
            ]
        )
        cgroup_root = tmp_path / "cgroup"
        populated(cgroup_root, value=0)
        receipt = CommandReceipts(
            case.authority, case.owner(), case.docker(), cgroup_root=cgroup_root, poll_interval_s=0.01
        ).execute(PEER, request, deadline=until())["receipt"]
        assert receipt["state"] == "EXITED" and receipt["exit_code"] == 0
        assert receipt["terminal_barrier"] is True
        assert len(streams) == 1 and streams[0].closed
    finally:
        _close_one_shot(case)


@pytest.mark.parametrize(
    ("barrier", "expected"),
    [(1, "EXECUTION_UNKNOWN"), (None, "EXECUTION_UNKNOWN")],
    ids=["populated", "unreadable"],
)
def test_a_one_shot_cell_without_an_empty_cgroup_is_never_exited(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, barrier: int | None, expected: str
) -> None:
    """producer-kill-check: accept the daemon's exit as the whole receipt."""
    case, _streams = _one_shot(site, tmp_path, monkeypatch)
    try:
        request = _one_shot_request(case, "4" * 32)
        operation_id = request["payload"]["operation_id"]
        case.peer.replies.extend(
            [
                Reply(201, {"Id": CID, "Warnings": []}),
                Reply(204),
                Reply(200, running_observation(operation_id, case.view.view_id)),
                Reply(200, exited_observation(operation_id, case.view.view_id, exit_code=0)),
            ]
        )
        cgroup_root = tmp_path / "cgroup"
        if barrier is not None:
            populated(cgroup_root, value=barrier)
        receipts = CommandReceipts(
            case.authority, case.owner(), case.docker(), cgroup_root=cgroup_root, poll_interval_s=0.01
        )
        denied(expected, lambda: receipts.execute(PEER, request, deadline=until()))
    finally:
        _close_one_shot(case)


def test_the_container_exit_must_agree_with_the_command_exit(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: let either side name the exit code."""
    case, _streams = _one_shot(site, tmp_path, monkeypatch)
    try:
        request = _one_shot_request(case, "5" * 32)
        operation_id = request["payload"]["operation_id"]
        case.peer.replies.extend(
            [
                Reply(201, {"Id": CID, "Warnings": []}),
                Reply(204),
                Reply(200, running_observation(operation_id, case.view.view_id)),
            ]
        )
        # The fake worker always claims 0; the daemon answers 7 for this cell.
        case.peer.replies.append(Reply(200, exited_observation(operation_id, case.view.view_id, exit_code=7)))
        cgroup_root = tmp_path / "cgroup"
        populated(cgroup_root, value=0)
        receipts = CommandReceipts(
            case.authority, case.owner(), case.docker(), cgroup_root=cgroup_root, poll_interval_s=0.01
        )
        denied("EXECUTION_UNKNOWN", lambda: receipts.execute(PEER, request, deadline=until()))
    finally:
        _close_one_shot(case)


def test_a_still_running_one_shot_cell_is_not_a_finished_command(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: map a live one-shot cell to EXITED because RUN returned."""
    case, _streams = _one_shot(site, tmp_path, monkeypatch)
    try:
        request = _one_shot_request(case, "6" * 32)
        operation_id = request["payload"]["operation_id"]
        case.peer.replies.extend(
            [
                Reply(201, {"Id": CID, "Warnings": []}),
                Reply(204),
                Reply(200, running_observation(operation_id, case.view.view_id)),
                Reply(200, running_observation(operation_id, case.view.view_id)),
            ]
        )
        populated(tmp_path / "cgroup", value=0)
        receipts = CommandReceipts(
            case.authority, case.owner(), case.docker(), cgroup_root=tmp_path / "cgroup", poll_interval_s=0.01
        )
        denied("EXECUTION_UNKNOWN", lambda: receipts.execute(PEER, request, deadline=until()))
    finally:
        _close_one_shot(case)


def test_a_timed_out_command_reports_no_exit_code(site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """producer-kill-check: reuse the worker's exit for a timeout."""
    case, streams = _one_shot(site, tmp_path, monkeypatch)
    try:
        request = _one_shot_request(case, "7" * 32)
        operation_id = request["payload"]["operation_id"]

        def timed_out(self: FakeWorkerStream, raw: bytes, *, deadline: float) -> None:
            from fa.execution.cell_protocol import decode_cell_request

            record = decode_cell_request(raw)
            self.requests.append(record)
            self._replies.put(
                encode_json(
                    {
                        "version": 1,
                        "request_id": record["request_id"],
                        "result": {
                            "stdout": "partial",
                            "exit_code": 137,
                            "truncated": False,
                            "session_id": None,
                            "timed_out": True,
                        },
                        "error": None,
                    }
                )
            )

        monkeypatch.setattr(FakeWorkerStream, "write_frame", timed_out)
        case.peer.replies.extend(
            [
                Reply(201, {"Id": CID, "Warnings": []}),
                Reply(204),
                Reply(200, running_observation(operation_id, case.view.view_id)),
            ]
        )
        populated(tmp_path / "cgroup", value=1)
        receipt = CommandReceipts(
            case.authority, case.owner(), case.docker(), cgroup_root=tmp_path / "cgroup", poll_interval_s=0.01
        ).execute(PEER, request, deadline=until())["receipt"]
        assert receipt["state"] == "TIMED_OUT"
        assert receipt["exit_code"] is None and receipt["timed_out"] is True
        assert len(case.peer.seen) == 3, "a spent budget still asked the daemon for a verdict"
        assert receipt["terminal_barrier"] is False
        assert streams and streams[0].closed
    finally:
        _close_one_shot(case)


def test_an_unobservable_cell_is_never_a_receipt(site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """producer-kill-check: treat a lost daemon answer as a finished command."""
    case, _streams = _one_shot(site, tmp_path, monkeypatch)
    try:
        request = _one_shot_request(case, "a" * 32)
        operation_id = request["payload"]["operation_id"]
        case.peer.replies.extend(
            [
                Reply(201, {"Id": CID, "Warnings": []}),
                Reply(204),
                Reply(200, running_observation(operation_id, case.view.view_id)),
            ]
        )
        populated(tmp_path / "cgroup", value=0)
        receipts = CommandReceipts(
            case.authority, case.owner(), case.docker(), cgroup_root=tmp_path / "cgroup", poll_interval_s=0.01
        )
        denied("EXECUTION_UNKNOWN", lambda: receipts.execute(PEER, request, deadline=until()))
    finally:
        _close_one_shot(case)


def test_a_foreign_daemon_answer_is_a_refusal_not_a_receipt(backend: Backend, tmp_path: Path) -> None:
    """producer-kill-check: accept whatever the daemon names as the cell."""
    request = exec_request(backend.grant, "b" * 32, "printf foreign-cell")
    claim(backend.authority, request)
    operation_id = request["payload"]["operation_id"]
    backend.peer.replies.extend(backend.episode_replies(operation_id))
    # Same container id, but the daemon labels the cell with another view.
    backend.peer.replies.append(Reply(200, exited_observation(operation_id, "view-" + "c" * 32)))
    denied("PATH_DENIED", lambda: issued(backend, tmp_path).execute(PEER, request, deadline=until()))


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------


def test_inspect_replays_the_durable_receipt_without_touching_the_daemon(backend: Backend, tmp_path: Path) -> None:
    """producer-kill-check: observe (or re-run) instead of replaying a DONE record."""
    request = exec_request(backend.grant, "8" * 32, "printf replay")
    claim(backend.authority, request)
    operation_id = request["payload"]["operation_id"]
    backend.peer.replies.extend(backend.episode_replies(operation_id))
    backend.peer.replies.append(Reply(200, running_observation(operation_id, backend.view.view_id)))
    receipts = issued(backend, tmp_path)
    result = receipts.execute(PEER, request, deadline=until())
    backend.authority.journal.complete(
        operation_id, NamespaceRef(**request["namespace"]), result, original_proof=request["capability"]
    )
    before = len(backend.peer.seen)

    inspected = receipts.inspect(
        PEER,
        {
            **request,
            "request_id": "9" * 32,
            "payload": {"operation_id": operation_id},
        },
        deadline=until(),
    )
    assert inspected["receipt"] == result["receipt"]
    assert len(backend.peer.seen) == before, "inspect contacted the daemon for a DONE operation"


def test_inspect_observes_a_live_operation_without_ever_sending_a_run(backend: Backend, tmp_path: Path) -> None:
    """producer-kill-check: make inspect send a RUN or invent an exit."""
    request = exec_request(backend.grant, "a" * 32, "printf running")
    claim(backend.authority, request)
    operation_id = request["payload"]["operation_id"]
    backend.authority.journal.record_container(operation_id, ACTOR, CID)
    backend.peer.replies.append(Reply(200, running_observation(operation_id, backend.view.view_id)))
    runs = backend.worker.runs

    receipt = issued(backend, tmp_path).inspect(
        PEER,
        {**request, "request_id": "b" * 32, "payload": {"operation_id": operation_id}},
        deadline=until(),
    )["receipt"]
    assert receipt["state"] == "RUNNING"
    assert receipt["exit_code"] is None and receipt["terminal_barrier"] is False
    assert receipt["operation_id"] == operation_id
    assert backend.worker.runs == runs, "inspect sent a command"


def test_inspect_refuses_another_views_operation(backend: Backend, tmp_path: Path) -> None:
    """producer-kill-check: answer another view's operation with a receipt.

    Two independent proofs refuse it: the journal record must name this exact
    view, and the grant proof behind `execution_identity` must be this view's.
    The refusal code is asserted, so a weaker comparison that reaches a
    different code still fails this test.
    """
    request = exec_request(backend.grant, "c" * 32, "printf foreign")
    claim(backend.authority, request)
    other = ViewRef.from_dict({**backend.view.to_dict(), "view_id": "view-" + "d" * 32})
    receipts = issued(backend, tmp_path)
    denied(
        "UNAUTHORIZED",
        lambda: receipts.inspect(
            PEER,
            {
                **request,
                "request_id": "e" * 32,
                "view_ref": other.to_dict(),
                "payload": {"operation_id": request["payload"]["operation_id"]},
            },
            deadline=until(),
        ),
    )


def test_inspect_of_an_unknown_operation_is_unknown(backend: Backend, tmp_path: Path) -> None:
    """producer-kill-check: answer a receipt for an operation nobody reserved."""
    request = exec_request(backend.grant, "f" * 32, "printf absent")
    denied(
        "EXECUTION_UNKNOWN",
        lambda: issued(backend, tmp_path).inspect(
            PEER,
            {**request, "payload": {"operation_id": "op-" + "1" * 32}},
            deadline=until(),
        ),
    )


def test_inspect_of_a_cancelled_operation_without_a_cell_is_empty(backend: Backend, tmp_path: Path) -> None:
    """producer-kill-check: treat 'no cell yet' as an unknown outcome."""
    request = exec_request(backend.grant, "2" * 32, "printf cancelled-early")
    claim(backend.authority, request)
    operation_id = request["payload"]["operation_id"]
    backend.authority.journal.request_cancel(operation_id, ACTOR, view=backend.view)
    receipt = issued(backend, tmp_path).inspect(
        PEER, {**request, "payload": {"operation_id": operation_id}}, deadline=until()
    )["receipt"]
    assert receipt["state"] == "CANCELLED" and receipt["exit_code"] is None
    assert receipt["terminal_barrier"] is True


def test_a_missing_cell_is_unknown_never_exited(backend: Backend, tmp_path: Path) -> None:
    """producer-kill-check: an absent container becomes a successful receipt."""
    request = exec_request(backend.grant, "3" * 32, "printf gone")
    claim(backend.authority, request)
    operation_id = request["payload"]["operation_id"]
    backend.authority.journal.record_container(operation_id, ACTOR, CID)
    backend.peer.replies.append(Reply(404, {}))
    receipt = issued(backend, tmp_path).inspect(
        PEER, {**request, "payload": {"operation_id": operation_id}}, deadline=until()
    )["receipt"]
    assert receipt["state"] == "UNKNOWN" and receipt["exit_code"] is None
    assert receipt["terminal_barrier"] is False


# ---------------------------------------------------------------------------
# cancel
# ---------------------------------------------------------------------------


def test_cancel_persists_intent_then_reports_what_the_stop_observed(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: report CANCELLED before the intent, or skip the stop."""
    case, _streams = _one_shot(site, tmp_path, monkeypatch)
    try:
        request = _one_shot_request(case, "4" * 32)
        operation_id = request["payload"]["operation_id"]
        case.authority.journal.record_container(operation_id, ACTOR, CID)
        # force_stop_owned: inspect -> kill -> inspect, then the receipt observes once.
        case.peer.replies.extend(
            [
                Reply(200, running_observation(operation_id, case.view.view_id)),
                Reply(204),
                Reply(200, exited_observation(operation_id, case.view.view_id, exit_code=137)),
                Reply(200, exited_observation(operation_id, case.view.view_id, exit_code=137)),
            ]
        )
        populated(tmp_path / "cgroup", value=0)

        observed: list[str] = []
        case.observe(lambda path: observed.append(path))
        cancel_request = {
            **request,
            "op": "cancel",
            "request_id": "5" * 32,
            "payload": {"operation_id": operation_id},
        }
        receipt = CommandReceipts(
            case.authority, case.owner(), case.docker(), cgroup_root=tmp_path / "cgroup", poll_interval_s=0.01
        ).cancel(PEER, cancel_request, deadline=until())["receipt"]

        assert receipt["state"] == "CANCELLED"
        assert receipt["operation_id"] == "op-" + "5" * 32  # the cancel operation's own id
        assert receipt["exit_code"] == 137
        assert receipt["terminal_barrier"] is True
        assert sum(1 for path in observed if path.endswith("/kill?signal=SIGKILL")) == 1
        record = case.authority.journal.lookup(operation_id, ACTOR)
        assert record is not None and record["cancel_requested"] is True
    finally:
        _close_one_shot(case)


def test_a_cancel_receipt_is_accepted_by_the_journal_but_can_never_be_exited(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: label a cancel EXITED, or invent the exit a lost cell did not answer.

    The stop observed the cell exit with 137, but the cancel receipt's own
    observation finds nothing: the honest receipt keeps `CANCELLED`, no exit
    code and no barrier, and the journal still accepts it as a completed cancel.
    """
    case, _streams = _one_shot(site, tmp_path, monkeypatch)
    try:
        request = _one_shot_request(case, "6" * 32)
        operation_id = request["payload"]["operation_id"]
        case.authority.journal.record_container(operation_id, ACTOR, CID)
        cancel_request = {
            **request,
            "op": "cancel",
            "request_id": "7" * 32,
            "payload": {"operation_id": operation_id},
        }
        # A cancel names the command it stops, so its own record is `op-<rid>`.
        assert case.authority.journal.reserve(cancel_request).fresh
        case.authority.journal.begin("op-" + "7" * 32, ACTOR)
        case.peer.replies.extend(
            [
                Reply(200, running_observation(operation_id, case.view.view_id)),
                Reply(204),
                Reply(200, exited_observation(operation_id, case.view.view_id, exit_code=137)),
                Reply(404, {}),
            ]
        )
        result = CommandReceipts(
            case.authority, case.owner(), case.docker(), cgroup_root=tmp_path / "cgroup", poll_interval_s=0.01
        ).cancel(PEER, cancel_request, deadline=until())
        case.authority.journal.complete(
            "op-" + "7" * 32, NamespaceRef(**cancel_request["namespace"]), result, original_proof=request["capability"]
        )
        stored = case.authority.journal.lookup("op-" + "7" * 32, ACTOR)
        assert stored is not None and stored["state"] == "DONE"
        assert stored["result"]["receipt"]["state"] == "CANCELLED"
        assert stored["result"]["receipt"]["exit_code"] is None
        assert stored["result"]["receipt"]["terminal_barrier"] is False
    finally:
        _close_one_shot(case)


def test_cancel_without_a_cell_proves_none_can_appear(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: contact the daemon for an operation that never created a cell."""
    case, _streams = _one_shot(site, tmp_path, monkeypatch)
    try:
        request = _one_shot_request(case, "8" * 32)
        operation_id = request["payload"]["operation_id"]
        before = len(case.peer.seen)
        receipt = CommandReceipts(
            case.authority, case.owner(), case.docker(), cgroup_root=tmp_path / "cgroup", poll_interval_s=0.01
        ).cancel(
            PEER,
            {
                **request,
                "op": "cancel",
                "request_id": "9" * 32,
                "payload": {"operation_id": operation_id},
            },
            deadline=until(),
        )["receipt"]
        assert receipt["state"] == "CANCELLED" and receipt["terminal_barrier"] is True
        assert receipt["exit_code"] is None
        assert len(case.peer.seen) == before, "a cell-less cancel contacted the daemon"
        record = case.authority.journal.lookup(operation_id, ACTOR)
        assert record is not None and record["cancel_requested"] is True
    finally:
        _close_one_shot(case)
