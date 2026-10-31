"""C0/C3 real UDS client with explicit fixture replies, not service/cell proof."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import socket
import struct
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from fa.execution.client import (
    ExecutionClient,
    ExecutionRejectedError,
    ExecutionTimedOutError,
    ExecutionUnavailableError,
    ExecutionUncertainError,
    ManagedBashExecutor,
)
from fa.execution.profiles import ExecutionProfile
from fa.execution.protocol import ERROR_CODES, DeadlineConnection, decode_request, encode_json, read_frame, write_frame
from fa.execution.types import Access, ExecutionContractError, GrantReply, NamespaceRef, Operation, ViewPurpose, ViewRef
from fa.inner_loop.plan_admission import snapshot_from_bytes
from fa.runtime.bash_executor import BashExecutor

NS = NamespaceRef("session-1", "run-1")
VIEW = ViewRef("ws-" + "1" * 32, "view-" + "2" * 32, "rev-" + "3" * 32, "run-1", 1, Access.WRITE, ViewPurpose.PROJECT)
SHA = "4" * 64
CAP = "5" * 64
SOURCE = snapshot_from_bytes("worklogs/demo/increments/increment-01-demo.md", b"# Existing plan\n")
CANDIDATE = snapshot_from_bytes("draft.md", b"# Repaired plan\n")
VIEW_BASE = "rev-" + "6" * 32
PUBLISHED = "rev-" + "7" * 32
CANDIDATE_VIEW = ViewRef(
    "ws-" + "1" * 32, "view-" + "8" * 32, VIEW_BASE, "run-1", 1, Access.READ, ViewPurpose.CANDIDATE
)


def profile() -> ExecutionProfile:
    # Explicit unit data, NOT an approved deployable syscall policy/host profile.
    return ExecutionProfile(
        "interactive",
        "example.invalid/fa@sha256:" + SHA,
        1000,
        1000,
        1_000_000_000,
        256 * 1024 * 1024,
        32,
        30_000,
        True,
        "fa-test.slice",
        json.dumps({"defaultAction": "SCMP_ACT_ERRNO", "syscalls": []}),
    )


def result(req: dict[str, Any]) -> dict[str, Any]:
    if req["op"] == "pty_control":
        return {"sessions": ["main"], "message": "control acknowledged"}
    return {
        "receipt": {
            "schema_version": 1,
            "operation_id": "op-" + req["request_id"],
            "namespace": NS.to_dict(),
            "workspace_id": VIEW.workspace_id,
            "view_id": VIEW.view_id,
            "owner_run_id": VIEW.owner_run_id,
            "generation": VIEW.generation,
            "revision_id": VIEW.base_revision,
            "original_revision_id": VIEW.base_revision,
            "input_tree_sha256": SHA,
            "plan_sha256": SHA,
            "profile_id": profile().profile_id,
            "image_digest": profile().image_digest,
            "state": "EXITED",
            "exit_code": 0,
            "timed_out": False,
            "stdout_tail": "stdout",
            "stderr_tail": "stderr",
            "truncated": False,
            "duration_ms": 10,
            "terminal_barrier": False,
        }
    }


@contextmanager
def endpoint(
    tmp_path: Path,
    handler: Callable[[dict[str, Any]], dict[str, Any] | None] = result,
    *,
    error_code: str | None = None,
    error_by_op: dict[str, str] | None = None,
    error_operation_id: str | None = None,
    retryable: bool = True,
) -> Iterator[tuple[ExecutionClient, list[dict[str, Any]]]]:
    """A literal reply fixture, deliberately no authority, journal or executor."""
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    path = directory / "control.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(path))
    path.chmod(0o660)
    listener.listen(4)
    listener.settimeout(0.05)
    stop = threading.Event()
    seen: list[dict[str, Any]] = []
    errors: list[BaseException] = []

    def serve() -> None:
        while not stop.is_set():
            try:
                connection, _ = listener.accept()
            except TimeoutError:
                continue
            except OSError:
                if stop.is_set():
                    break
                raise
            received = False
            try:
                with connection:
                    connection.settimeout(1)
                    req = decode_request(read_frame(connection))
                    received = True
                    seen.append(req)
                    body = handler(req)
                    if body is not None:
                        code = (error_by_op or {}).get(req["op"], error_code)
                        error = (
                            None
                            if code is None
                            else {"code": code, "retryable": retryable, "operation_id": error_operation_id}
                        )
                        write_frame(
                            connection,
                            encode_json(
                                {
                                    "protocol_version": 1,
                                    "request_id": req["request_id"],
                                    "status": "OK" if error is None else "ERROR",
                                    "result": body if error is None else None,
                                    "error": error,
                                }
                            ),
                        )
            except (OSError, ExecutionContractError) as error:
                if not stop.is_set() and received:
                    errors.append(error)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield ExecutionClient(path, server_uid=os.getuid(), rpc_timeout_ms=1000), seen
    finally:
        stop.set()
        listener.close()
        thread.join(2)
        assert not thread.is_alive()
        assert not errors


def view_grant() -> GrantReply:
    return GrantReply(Operation.CREATE_VIEW, CAP, VIEW, None, None)


def executor(client: ExecutionClient) -> ManagedBashExecutor:
    return ManagedBashExecutor(
        client,
        namespace=NS,
        view=VIEW,
        grant=view_grant(),
        profile=profile(),
        input_tree_sha256=SHA,
        plan_sha256=SHA,
        original_revision_id=VIEW.base_revision,
        controller_root=Path("/sessions/source"),
    )


def test_all_four_methods_use_only_one_udspath_and_keep_pty_contract(tmp_path: Path) -> None:
    with endpoint(tmp_path) as (client, seen):
        bash: BashExecutor = executor(client)
        outcome = bash.run("printf anything", timeout=100, workdir=Path("/sessions/source/src"), session_id="main")
        assert (outcome.stdout, outcome.exit_code, outcome.truncated, outcome.session_id, outcome.timed_out) == (
            "stdoutstderr",
            0,
            False,
            "main",
            False,
        )
        assert bash.send_ctrl_c("main") == "control acknowledged"
        bash.close("main")
        assert bash.list_sessions() == ["main"]
        assert [r["op"] for r in seen] == ["exec", "pty_control", "pty_control", "pty_control"]
        assert seen[0]["payload"] == {
            "operation_id": "op-" + seen[0]["request_id"],
            "profile_id": "interactive",
            "command": "printf anything",
            "cwd": "src",
            "timeout_ms": 30_000,
            "session_id": "main",
        }
        assert [r["payload"]["action"] for r in seen[1:]] == ["INTERRUPT", "CLOSE", "LIST"]
        assert len({r["request_id"] for r in seen}) == 4
        assert CAP not in repr(bash)


def test_the_client_takes_a_typed_grant_and_unwraps_it_once(tmp_path: Path) -> None:
    """producer-kill-check: keep the token as a string field, or drop the type guard."""
    with endpoint(tmp_path) as (client, seen):
        bash = executor(client)
        bash.run("printf anything", timeout=100, session_id="main")
        assert seen[0]["capability"] == CAP  # unwrapped at the transport, never stored beside it
        for holder in (client, bash):
            assert CAP not in repr(holder)
            assert all(CAP not in repr(value) for value in vars(holder).values())
        frames = len(seen)
        with pytest.raises(ExecutionContractError):
            client.request(
                Operation.CREATE_VIEW,
                request_id="a" * 32,
                namespace=NS,
                view=None,
                grant=CAP,  # type: ignore[arg-type]
                payload={},
            )
        assert len(seen) == frames  # refused before connecting: no frame exists, so nothing can be replayed


@pytest.mark.parametrize(
    "changes",
    [
        {"operation_id": "op-" + "f" * 32},
        {"namespace": {**NS.to_dict(), "run_id": "wrong"}},
        {"workspace_id": "ws-" + "f" * 32},
        {"view_id": "view-" + "f" * 32},
        {"owner_run_id": "wrong"},
        {"generation": 2},
        {"revision_id": "rev-" + "f" * 32},
        {"original_revision_id": "rev-" + "f" * 32},
        {"input_tree_sha256": "f" * 64},
        {"plan_sha256": "f" * 64},
        {"profile_id": "wrong"},
        {"image_digest": "sha256:" + "f" * 64},
    ],
)
def test_any_altered_reserved_binding_is_uncertain_not_success(tmp_path: Path, changes: dict[str, Any]) -> None:
    def changed(req: dict[str, Any]) -> dict[str, Any]:
        value = result(req)
        value["receipt"].update(changes)
        return value

    with endpoint(tmp_path, changed) as (client, seen):
        with pytest.raises(ExecutionUncertainError) as caught:
            executor(client).run("printf no replay")
        assert len(seen) == 1
        assert caught.value.operation_id == "op-" + seen[0]["request_id"]
        assert CAP not in str(caught.value)


@pytest.mark.parametrize(
    "state,error",
    [
        ("TIMED_OUT", ExecutionTimedOutError),
        ("UNKNOWN", ExecutionUncertainError),
        ("RUNNING", ExecutionUncertainError),
        ("LAUNCH_FAILED", ExecutionUnavailableError),
        ("CANCELLED", ExecutionUncertainError),
    ],
)
def test_uncertainty_timeout_and_backend_failure_never_become_exit_zero(
    tmp_path: Path, state: str, error: type[RuntimeError]
) -> None:
    def changed(req: dict[str, Any]) -> dict[str, Any]:
        value = result(req)
        value["receipt"].update(state=state, exit_code=None, timed_out=state == "TIMED_OUT")
        return value

    with endpoint(tmp_path, changed) as (client, seen):
        with pytest.raises(error):
            executor(client).run("printf exactly once")
        assert len(seen) == 1


def test_lost_reply_is_not_resent_and_preserves_inspection_key(tmp_path: Path) -> None:
    with endpoint(tmp_path, lambda _: None) as (client, seen):
        with pytest.raises(ExecutionUncertainError) as caught:
            executor(client).run("side effect")
        assert len(seen) == 1
        assert caught.value.operation_id == seen[0]["payload"]["operation_id"]


def test_invalid_cwd_and_payload_are_rejected_before_any_request(tmp_path: Path) -> None:
    with endpoint(tmp_path) as (client, seen):
        for cwd in [Path("/outside"), Path("../escape")]:
            with pytest.raises(ExecutionContractError):
                executor(client).run("not sent", workdir=cwd)
        assert seen == []


def test_wrong_peer_identity_is_rejected_before_send(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def wrong_peer(self: socket.socket, level: int, option: int, size: int) -> bytes:
        assert (level, option, size) == (socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        return struct.pack("3i", os.getpid(), os.getuid() + 1, os.getgid())

    with endpoint(tmp_path) as (client, seen):
        monkeypatch.setattr(socket.socket, "getsockopt", wrong_peer)
        with pytest.raises(ExecutionUnavailableError):
            executor(client).run("not sent")
        assert seen == []


def test_missing_endpoint_and_invalid_client_config_are_structured(tmp_path: Path) -> None:
    client = ExecutionClient(tmp_path / "missing.sock", server_uid=os.getuid(), rpc_timeout_ms=100)
    with pytest.raises(ExecutionUnavailableError, match="execution_unavailable"):
        executor(client).run("not sent")
    for uid, timeout in [(-1, 100), (True, 100), (1, 0)]:
        with pytest.raises(ExecutionContractError):
            ExecutionClient(tmp_path / "missing.sock", server_uid=uid, rpc_timeout_ms=timeout)


@pytest.mark.parametrize(
    "changes",
    [
        {"image": "image:latest"},
        {"uid": 0},
        {"gid": True},
        {"nano_cpus": 0},
        {"memory_bytes": -1},
        {"pids_limit": False},
        {"max_command_ms": 0},
        {"interactive": 1},
        {"profile_id": "bad/path"},
        {"cgroup_parent": "../escape"},
        {"seccomp_json": "unconfined"},
        {"seccomp_json": '{"defaultAction":"SCMP_ACT_ALLOW","syscalls":[]}'},
    ],
)
def test_profile_rejects_weak_or_unpinned_configuration(changes: dict[str, Any]) -> None:
    with pytest.raises(ExecutionContractError):
        replace(profile(), **changes)


@pytest.mark.parametrize("access", list(Access))
def test_fixed_cell_create_body_has_no_control_mounts_or_ambient_environment(access: Access) -> None:
    spec = profile().create_spec(
        operation_id="op-" + "a" * 32,
        view=replace(VIEW, access=access),
        source=Path("/protected/views/source"),
        scratch=Path("/protected/scratch/job"),
        cache=Path("/opt/approved-cache"),
    )
    body, host = spec["body"], spec["body"]["HostConfig"]
    assert spec["name"] == "fa-job-" + "a" * 32
    assert body["Image"].endswith("@sha256:" + SHA) and body["User"] == "1000:1000"
    assert host["NetworkMode"] == "none" and body["NetworkDisabled"] is True
    assert host["Privileged"] is False and host["CapDrop"] == ["ALL"] and host["ReadonlyRootfs"] is True
    assert host["SecurityOpt"][0] == "no-new-privileges:true"
    assert json.loads(host["SecurityOpt"][1].removeprefix("seccomp="))["defaultAction"] == "SCMP_ACT_ERRNO"
    assert (host["PidMode"], host["IpcMode"], host["CgroupnsMode"]) == ("", "private", "private")
    assert (host["NanoCpus"], host["Memory"], host["PidsLimit"]) == (1_000_000_000, 256 * 1024 * 1024, 32)
    assert [m["Target"] for m in host["Mounts"]] == ["/workspace", "/scratch", "/opt/toolchain-cache"]
    assert [m["ReadOnly"] for m in host["Mounts"]] == [access is Access.READ, False, True]
    assert all(m["BindOptions"] == {"Propagation": "rprivate"} for m in host["Mounts"])
    assert set(body["Env"]) == {"HOME=/scratch/home", "TMPDIR=/scratch/tmp", "PYTHONDONTWRITEBYTECODE=1"}
    assert body["Entrypoint"] == ["/opt/fa-venv/bin/python", "-I", "-m", "fa.execution.cell_worker"]
    changed = copy.deepcopy(spec)
    changed["body"]["HostConfig"]["Privileged"] = True
    assert (
        profile().create_spec(
            operation_id="op-" + "a" * 32, view=VIEW, source=Path("/a"), scratch=Path("/b"), cache=Path("/c")
        )["body"]["HostConfig"]["Privileged"]
        is False
    )


@pytest.mark.parametrize(
    "paths", [("relative", "/b", "/c"), ("/", "/b", "/c"), ("/a/../b", "/b", "/c"), ("/a", "/a/scratch", "/c")]
)
def test_mount_renderer_refuses_ambiguous_or_overlapping_paths(paths: tuple[str, str, str]) -> None:
    with pytest.raises(ExecutionContractError):
        profile().create_spec(
            operation_id="op-" + "a" * 32,
            view=VIEW,
            source=Path(paths[0]),
            scratch=Path(paths[1]),
            cache=Path(paths[2]),
        )


def test_server_rejection_is_typed_and_retryable_flag_does_not_resend(tmp_path: Path) -> None:
    with endpoint(tmp_path, error_code="UNAUTHORIZED") as (client, seen):
        with pytest.raises(ExecutionRejectedError) as caught:
            executor(client).run("not authorized")
        assert caught.value.code == "UNAUTHORIZED"
        assert caught.value.operation_id is None
        assert len(seen) == 1


def test_determinate_nonzero_exit_is_preserved_as_command_failure_data(tmp_path: Path) -> None:
    def nonzero(req: dict[str, Any]) -> dict[str, Any]:
        value = result(req)
        value["receipt"].update(exit_code=7, truncated=True)
        return value

    with endpoint(tmp_path, nonzero) as (client, seen):
        outcome = executor(client).run("unit fixture, not executed")
        assert outcome.exit_code == 7 and outcome.truncated is True and outcome.timed_out is False
        assert len(seen) == 1


@pytest.mark.parametrize("interactive", [True, False])
def test_fixed_profile_selects_persistent_or_one_shot_worker(interactive: bool) -> None:
    configured = replace(profile(), interactive=interactive)
    spec = configured.create_spec(
        operation_id="op-" + "a" * 32,
        view=VIEW,
        source=Path("/protected/source"),
        scratch=Path("/protected/scratch"),
        cache=Path("/approved/cache"),
    )
    assert spec["body"]["Cmd"] == ["--max-command-ms", "30000"] + ([] if interactive else ["--one-shot"])


def test_command_reply_can_outlive_control_budget_without_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C0/C3 native UDS fixture; logical elapsed clock, not a real command/backend."""
    now = [0.0]
    monkeypatch.setattr("fa.execution.protocol.time.monotonic", lambda: now[0])

    input_budgets: list[float] = []

    def observe_send(connection: DeadlineConnection, raw: bytes) -> None:
        input_budgets.append(connection.remaining())
        write_frame(connection, raw)

    def elapsed_reply(connection: DeadlineConnection) -> bytes:
        now[0] = 1.1  # Only reply waiting borrows command time, never connect/request.
        return read_frame(connection)

    monkeypatch.setattr("fa.execution.client.write_frame", observe_send)
    monkeypatch.setattr("fa.execution.client.read_frame", elapsed_reply)
    with endpoint(tmp_path) as (client, seen):
        value = None
        error = None
        try:
            value = executor(client).run("fixture response", timeout=2)
        except ExecutionUncertainError as exc:
            error = exc
        assert error is None and value is not None
        assert value.exit_code == 0 and value.stdout == "stdoutstderr"
        assert len(seen) == 1 and seen[0]["payload"]["timeout_ms"] == 2000
        assert input_budgets == [1.0]


@pytest.mark.parametrize("action", ["send_ctrl_c", "close", "list_sessions"])
def test_controls_do_not_borrow_a_command_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str) -> None:
    now = [0.0]
    monkeypatch.setattr("fa.execution.protocol.time.monotonic", lambda: now[0])

    def delayed(req: dict[str, Any]) -> dict[str, Any]:
        now[0] = 1.1
        return result(req)

    with endpoint(tmp_path, delayed) as (client, seen):
        bash = executor(client)
        uncertain = None
        try:
            if action == "list_sessions":
                bash.list_sessions()
            elif action == "close":
                bash.close("main")
            else:
                bash.send_ctrl_c("main")
        except ExecutionUncertainError as exc:
            uncertain = exc
        assert uncertain is not None
        assert len(seen) == 1 and seen[0]["op"] == "pty_control"


_ERROR_TYPES: dict[str, type[RuntimeError]] = {
    "INVALID_REQUEST": ExecutionRejectedError,
    "UNAUTHORIZED": ExecutionRejectedError,
    "UNAPPROVED_PROFILE": ExecutionRejectedError,
    "WORKSPACE_BUSY": ExecutionRejectedError,
    "STALE_GENERATION": ExecutionRejectedError,
    "STALE_REVISION": ExecutionRejectedError,
    "VIEW_CLOSED": ExecutionRejectedError,
    "BACKEND_UNAVAILABLE": ExecutionUnavailableError,
    "EXECUTION_UNKNOWN": ExecutionUncertainError,
    "TERMINALITY_UNKNOWN": ExecutionUncertainError,
    "PATH_DENIED": ExecutionRejectedError,
    "INPUT_POLICY": ExecutionRejectedError,
    "COLLISION": ExecutionRejectedError,
    "DURABILITY_UNKNOWN": ExecutionUncertainError,
    "CORRUPT_STATE": ExecutionUncertainError,
}


def _invoke(bash: ManagedBashExecutor, method: str) -> object:
    if method == "run":
        return bash.run("command-body-must-not-appear-in-errors")
    if method == "interrupt":
        return bash.send_ctrl_c("main")
    if method == "close":
        bash.close("main")
        return None
    return bash.list_sessions()


def test_error_matrix_covers_closed_wire_codes() -> None:
    assert set(_ERROR_TYPES) == set(ERROR_CODES)


@pytest.mark.parametrize("code", ERROR_CODES)
@pytest.mark.parametrize("method", ["run", "interrupt", "close", "list"])
@pytest.mark.parametrize("retryable", [False, True])
def test_every_error_code_is_typed_through_all_executor_methods_without_resend(
    tmp_path: Path,
    code: str,
    method: str,
    retryable: bool,
) -> None:
    with endpoint(tmp_path, error_code=code, retryable=retryable) as (client, seen):
        with pytest.raises(RuntimeError) as caught:
            _invoke(executor(client), method)
        error = caught.value
        assert type(error) is _ERROR_TYPES[code]
        assert isinstance(error, (ExecutionUncertainError, ExecutionUnavailableError, ExecutionRejectedError))
        assert error.code == code
        assert len(seen) == 1
        expected = "op-" + seen[0]["request_id"] if type(error) is ExecutionUncertainError else None
        assert error.operation_id == expected
        assert (seen[0]["op"] == "exec") == (method == "run")
        if method != "run":
            assert seen[0]["payload"]["action"] == {"interrupt": "INTERRUPT", "close": "CLOSE", "list": "LIST"}[method]
        for private in (CAP, "command-body-must-not-appear-in-errors", str(tmp_path)):
            assert private not in str(error) and private not in repr(error)


@pytest.mark.parametrize(
    "code", ["EXECUTION_UNKNOWN", "DURABILITY_UNKNOWN", "TERMINALITY_UNKNOWN", "CORRUPT_STATE", "BACKEND_UNAVAILABLE"]
)
@pytest.mark.parametrize("method", ["run", "interrupt", "close", "list"])
def test_typed_service_failure_retains_supplied_reference_and_never_issues_recovery_rpc(
    tmp_path: Path,
    code: str,
    method: str,
) -> None:
    reference = "op-" + "a" * 32  # Opaque observation/replay reference, not authority.
    with endpoint(tmp_path, error_code=code, error_operation_id=reference) as (client, seen):
        with pytest.raises(RuntimeError) as caught:
            _invoke(executor(client), method)
        error = caught.value
        assert type(error) is _ERROR_TYPES[code]
        assert isinstance(error, (ExecutionUncertainError, ExecutionUnavailableError))
        assert error.operation_id == reference and error.code == code
        assert len(seen) == 1  # No inspect/cancel/control/reconnect/RUN synthesized.


def test_failure_constructor_compatibility_keeps_old_transport_call_sites() -> None:
    unavailable = ExecutionUnavailableError()
    unknown = ExecutionUncertainError("op-" + "b" * 32)
    assert unavailable.code == "BACKEND_UNAVAILABLE" and unavailable.operation_id is None
    assert unknown.code == "EXECUTION_UNKNOWN" and unknown.operation_id == "op-" + "b" * 32
    assert str(unavailable) == "execution_unavailable" and str(unknown) == "execution_unknown"


def writer_grant(revision_id: str = "rev-" + "5" * 32) -> GrantReply:
    return GrantReply(Operation.ACQUIRE_WRITER, "7" * 64, None, 2, revision_id)


def candidate_saga(*, already_published: bool = False) -> tuple[Callable[[dict[str, Any]], dict[str, Any]], list[str]]:
    """Literal replies for one publication; the view mints a base the grant does not carry."""
    written: list[str] = []

    def handler(req: dict[str, Any]) -> dict[str, Any]:
        if req["op"] == "create_view":
            return {"view_ref": CANDIDATE_VIEW.to_dict(), "capability": "6" * 64}
        if req["op"] == "write_file":
            written.append(req["payload"]["content"])
            raw = written[-1].encode()
            return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        if req["op"] == "stop_view":
            return {"view_id": req["view_ref"]["view_id"], "terminal": True}
        if req["op"] == "publish":
            sha = hashlib.sha256(written[-1].encode()).hexdigest()
            return {
                "workspace_id": req["view_ref"]["workspace_id"],
                "revision_id": PUBLISHED,
                "tree_sha256": SHA,
                "operation_id": "op-" + req["request_id"],
                "projection_complete": True,
                "plan_ref": {
                    "workspace_relative_path": SOURCE.ref.workspace_relative_path,
                    "source_kind": SOURCE.ref.source_kind,
                    "sha256": sha,
                },
                "already_published": already_published,
            }
        return {}

    return handler, written


def publish(client: ExecutionClient, *, deadline: float | None = None):
    return client.publish_plan(
        SimpleNamespace(namespace=NS, workspace_id=VIEW.workspace_id),
        SOURCE,
        CANDIDATE,
        grant=writer_grant(),
        deadline=deadline,
    )


def test_publish_plan_runs_the_saga_and_cases_the_base_the_view_returned(tmp_path: Path) -> None:
    """producer-kill-check: cache a base revision on the client, or publish without a view's base."""
    handler, written = candidate_saga()
    with endpoint(tmp_path, handler) as (client, seen):
        publication = publish(client)
        assert [req["op"] for req in seen] == ["create_view", "write_file", "stop_view", "publish", "release"]
        assert seen[0]["payload"]["base_revision"] is None  # CANDIDATE opens on a null base
        assert seen[0]["payload"]["candidate_scope"]["plan_ref"] == {
            "workspace_relative_path": SOURCE.ref.workspace_relative_path,
            "source_kind": SOURCE.ref.source_kind,
            "sha256": SOURCE.ref.sha256,
        }
        # The CAS carries the view's base, never the writer grant's revision.
        assert seen[3]["payload"]["expected_base_revision"] == VIEW_BASE
        assert writer_grant().revision_id != VIEW_BASE
        # CT120: the scope is the plan identity alone, and the buffer's address is
        # the plan's canonical path — never a controller-invented alias.
        assert set(seen[0]["payload"]["candidate_scope"]) == {"plan_ref"}
        assert seen[0]["payload"]["candidate_scope"]["plan_ref"] == seen[0]["payload"]["plan_ref"]
        assert seen[1]["payload"]["path"] == SOURCE.ref.workspace_relative_path
        assert written == [CANDIDATE.text]
        assert publication.revision_id == PUBLISHED and publication.already_published is False
        assert publication.plan_ref == replace(SOURCE.ref, sha256=hashlib.sha256(CANDIDATE.utf8_bytes).hexdigest())

        assert publication.plan_ref == replace(SOURCE.ref, sha256=hashlib.sha256(CANDIDATE.utf8_bytes).hexdigest())


def test_a_publish_reply_from_before_the_repeat_key_still_commits(tmp_path: Path) -> None:
    """C1: an upgraded client talking to a not-yet-restarted supervisor must not strand.

    The key was added without a protocol bump, and a server that never had the
    repeat path always committed - so a missing ``already_published`` means False,
    not "unknown". Reading it as uncertainty would refuse a commit that happened
    and leave the workspace unsettled on every run during an upgrade.
    """
    handler, _ = candidate_saga()

    def legacy(request: dict[str, Any]) -> dict[str, Any]:
        reply = handler(request)
        reply.pop("already_published", None) if request["op"] == "publish" else None
        return reply

    with endpoint(tmp_path, legacy) as (client, seen):
        publication = publish(client)
        assert publication.already_published is False
        assert publication.revision_id == PUBLISHED
        assert [req["op"] for req in seen][-1] == "release"  # determinate: the view is settled


def test_publish_plan_reports_a_repeat_and_still_releases(tmp_path: Path) -> None:
    """producer-kill-check: swallow already_published, or skip RELEASE on the repeat path."""
    handler, _ = candidate_saga(already_published=True)
    with endpoint(tmp_path, handler) as (client, seen):
        publication = publish(client)
        assert publication.already_published is True and publication.revision_id == PUBLISHED
        assert [req["op"] for req in seen].count("publish") == 1
        assert seen[-1]["op"] == "release"


def test_publish_plan_keeps_the_view_when_the_publish_is_indeterminate(tmp_path: Path) -> None:
    """producer-kill-check: release from a finally that cannot prove the writer is settled."""
    handler, _ = candidate_saga()
    with endpoint(tmp_path, handler, error_by_op={"publish": "EXECUTION_UNKNOWN"}) as (client, seen):
        with pytest.raises(ExecutionUncertainError) as caught:
            publish(client)
        assert caught.value.code == "EXECUTION_UNKNOWN"
        operations = [req["op"] for req in seen]
        assert operations.count("publish") == 1  # no retry and no second commit
        assert "release" not in operations  # the view stays open for recovery


def test_publish_plan_releases_after_a_determinate_refusal(tmp_path: Path) -> None:
    """producer-kill-check: keep the view on a refusal that provably committed nothing."""
    handler, _ = candidate_saga()
    with endpoint(tmp_path, handler, error_by_op={"publish": "INPUT_POLICY"}) as (client, seen):
        with pytest.raises(ExecutionRejectedError) as caught:
            publish(client)
        assert caught.value.code == "INPUT_POLICY"
        assert [req["op"] for req in seen][-1] == "release"


def test_publish_plan_refuses_a_binding_or_grant_it_cannot_prove(tmp_path: Path) -> None:
    """producer-kill-check: accept any object as a binding, or any grant as the writer grant."""
    with endpoint(tmp_path) as (client, seen):
        with pytest.raises(ExecutionContractError):
            client.publish_plan(
                SimpleNamespace(namespace=NS, workspace_id="ws-not-hex"), SOURCE, CANDIDATE, grant=writer_grant()
            )
        with pytest.raises(ExecutionContractError):
            client.publish_plan(
                SimpleNamespace(namespace="session-1/run-1", workspace_id=VIEW.workspace_id),
                SOURCE,
                CANDIDATE,
                grant=writer_grant(),
            )
        with pytest.raises(ExecutionContractError):
            client.publish_plan(
                SimpleNamespace(namespace=NS, workspace_id=VIEW.workspace_id), SOURCE, CANDIDATE, grant=view_grant()
            )
        assert seen == []


def test_publish_plan_treats_a_foreign_plan_ref_as_indeterminate(tmp_path: Path) -> None:
    """producer-kill-check: trust the reply's PlanRef without comparing it to the pinned one."""
    handler, written = candidate_saga()

    def lying(req: dict[str, Any]) -> dict[str, Any]:
        body = handler(req)
        if req["op"] == "publish":
            body["plan_ref"] = {**body["plan_ref"], "sha256": "0" * 64}
        return body

    with endpoint(tmp_path, lying) as (client, seen):
        with pytest.raises(ExecutionUncertainError) as caught:
            publish(client)
        assert caught.value.code == "DURABILITY_UNKNOWN"
        assert "release" not in [req["op"] for req in seen]
        assert written == [CANDIDATE.text]
