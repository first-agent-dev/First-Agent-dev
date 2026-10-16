"""C0/C3 real UDS client with explicit fixture replies, not service/cell proof."""

from __future__ import annotations

import copy
import json
import os
import socket
import struct
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
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
from fa.execution.protocol import decode_request, encode_json, read_frame, write_frame
from fa.execution.types import Access, ExecutionContractError, NamespaceRef, ViewPurpose, ViewRef
from fa.runtime.bash_executor import BashExecutor

NS = NamespaceRef("session-1", "run-1")
VIEW = ViewRef("ws-" + "1" * 32, "view-" + "2" * 32, "rev-" + "3" * 32, "run-1", 1, Access.WRITE, ViewPurpose.PROJECT)
SHA = "4" * 64
CAP = "5" * 64


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
                        error = (
                            None
                            if error_code is None
                            else {"code": error_code, "retryable": True, "operation_id": None}
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


def executor(client: ExecutionClient) -> ManagedBashExecutor:
    return ManagedBashExecutor(
        client,
        namespace=NS,
        view=VIEW,
        capability=CAP,
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
