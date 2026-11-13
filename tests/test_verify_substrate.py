"""R24/Q142: the gate pins a READ view over the admitted revision, never the host.

The unit under test is the *choice* and *isolation*: unmanaged runs keep their
host tree; managed runs pin a READ view at the current revision and fail closed
(recording ``ERROR`` / ``baseline-unavailable`` with zero host subprocesses) if
the non-interactive READ profile or pinned substrate is missing or refused.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, override

import pytest

from fa.execution import composition
from fa.execution.cell_worker import serve_once
from fa.execution.client import ExecutionClient, ExecutionRejectedError
from fa.execution.composition import ExecutionBinding, managed_execution_for_run
from fa.execution.primitives import ExecutionContractError
from fa.execution.profiles import ExecutionProfile
from fa.execution.protocol import MAX_TAIL_BYTES
from fa.execution.service import SupervisorService, read_config_file
from fa.execution.types import Access, GrantReply, NamespaceRef, Operation, ViewPurpose, ViewRef
from fa.inner_loop import slice_verification, workflow_controller
from fa.inner_loop.plan_admission import PlanRef
from fa.inner_loop.plan_ids import extract_plan_ids
from fa.inner_loop.slice_verification import SliceVerdict, verify_plan
from fa.inner_loop.workflow_controller import (
    WorkflowContext,
    _capture_stage_baseline,
    _pinned_verify_substrate,
    workflow_artifact_paths,
)
from fa.runtime.pty_pool import PtyPool, PtySession
from fa.session.manager import RunContext
from tests.test_execution_backend import UPGRADE, CountingWorker, MuxWorker
from tests.test_execution_composition import _configs, _document, _serving_supervisor
from tests.test_execution_docker import Endpoint, Reply
from tests.test_execution_service import _registered
from tests.test_execution_views import native_profile, read_only_profile
from tests.test_execution_workspace import Site
from tests.test_execution_workspace import site as site

_PLAN_TEXT = """## SLICE1: verify in pinned revision
CONTRACTS:
  CT1 [FUNCTIONAL]: double returns twice the input.
    kill: neutralise src/demo_calc.py::double
TESTS: tests/test_demo_calc.py
```verify
python -m pytest tests/test_demo_calc.py -q
```
"""


def _ctx(tmp_path: Path, *, managed: Any = None, workspace: Path | None = None) -> WorkflowContext:
    return WorkflowContext(
        run_id="run-verify-substrate",
        base_task="prove the substrate choice",
        per_role_task={},
        artifact_paths=workflow_artifact_paths("run-verify-substrate", base_dir=tmp_path / "logs"),
        config=object(),  # type: ignore[arg-type]
        workspace=tmp_path if workspace is None else workspace,
        max_turns=1,
        output_mode="quiet",
        verify_gate_mode="enforce",
        managed_execution=managed,
    )


def test_an_unmanaged_run_yields_no_substrate_and_pins_nothing(tmp_path: Path) -> None:
    """C0 — the host is not a fallback, it is the substrate an unmanaged run already is."""
    with _pinned_verify_substrate(_ctx(tmp_path)) as substrate:
        assert substrate is None


class _NoProfile:
    """A managed execution whose read-only profile was never configured."""

    client = object()
    binding = object()
    current_revision_id = "rev-" + "3" * 32
    read_only_profile: ExecutionProfile | None = None


def test_a_managed_run_without_a_non_interactive_read_only_profile_refuses_host_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1/R24 — missing or interactive read-only profile fails closed with zero host subprocesses."""
    with pytest.raises(ExecutionContractError):
        with _pinned_verify_substrate(_ctx(tmp_path, managed=_NoProfile())):
            pass

    interactive_profile = replace(_profile(), interactive=True)
    with pytest.raises(ExecutionContractError):
        with _pinned_verify_substrate(_ctx(tmp_path, managed=_Managed(object(), interactive_profile))):
            pass

    host_calls: list[object] = []
    monkeypatch.setattr(slice_verification, "run_commands", lambda *a, **k: host_calls.append((a, k)) or ())
    plan_ids = extract_plan_ids(_PLAN_TEXT)
    ctx = _ctx(tmp_path, managed=_NoProfile())
    baseline = _capture_stage_baseline(ctx, plan_ids)

    assert host_calls == []
    assert baseline.nodeids_by_slice == {"SLICE1": None}
    assert baseline.errors and "ExecutionContractError" in baseline.errors[0]
    payload = json.loads(ctx.artifact_paths.verify_baseline.read_text(encoding="utf-8"))
    assert payload["slices"] == {"SLICE1": {"nodeids": None, "test_paths": ["tests/test_demo_calc.py"]}}


class _Client(ExecutionClient):
    """A real client subclass: the executors prove ``isinstance`` before trusting a pin."""

    def __init__(self, *, grant: Any) -> None:
        self.grant = grant
        self.pin_calls: list[dict[str, Any]] = []
        self.stop_calls: list[dict[str, Any]] = []

    @override
    def pin_reader(
        self,
        binding: object,
        revision_id: str,
        *,
        plan_ref: PlanRef | None = None,
        deadline: float | None = None,
    ) -> GrantReply:
        self.pin_calls.append({"binding": binding, "revision_id": revision_id, "plan_ref": plan_ref})
        return self.grant

    @override
    def stop_view(
        self, namespace: NamespaceRef, *, view: ViewRef, grant: GrantReply, deadline: float | None = None
    ) -> bool:
        self.stop_calls.append({"namespace": namespace, "view": view})
        return True


def _namespace() -> NamespaceRef:
    return NamespaceRef(session_id="session-1", run_id="run-" + "1" * 16, parent_run_id=None)


def _binding(*, workspace_id: str = "ws-" + "1" * 32) -> Any:
    return ExecutionBinding(_namespace(), workspace_id)


class _Managed:
    def __init__(self, client: Any, profile: Any, *, workspace_id: str = "ws-" + "1" * 32) -> None:
        self.client = client
        self.binding = _binding(workspace_id=workspace_id)
        self.current_revision_id = "rev-" + "3" * 32
        self.read_only_profile = profile


def _profile() -> ExecutionProfile:
    return ExecutionProfile(
        "reader",
        "unit.invalid/cell@sha256:" + "5" * 64,
        1000,
        1000,
        1_000_000_000,
        128 * 1024**2,
        64,
        1000,
        False,
        "fa-exec.slice",
        '{"defaultAction":"SCMP_ACT_ERRNO","syscalls":[]}',
    )


def _view(*, access: Access = Access.READ, workspace_id: str = "ws-" + "1" * 32) -> ViewRef:
    return ViewRef(
        workspace_id, "view-" + "2" * 32, "rev-" + "3" * 32, "run-" + "1" * 16, 1, access, ViewPurpose.PROJECT
    )


def _grant(
    *,
    view: ViewRef,
    operation: Operation = Operation.PIN_READER,
    input_tree_sha256: str | None = "a" * 64,
) -> GrantReply:
    return GrantReply(operation, "c" * 64, view, None, None, input_tree_sha256=input_tree_sha256)


def test_a_grant_for_anything_but_a_matching_read_pin_is_refused(tmp_path: Path) -> None:
    """C1 — the substrate verifies operation, READ/PROJECT access, owner, workspace, and tree sha."""
    client = _Client(grant=_grant(view=_view(), operation=Operation.CREATE_VIEW))
    with pytest.raises(ExecutionContractError):
        with _pinned_verify_substrate(_ctx(tmp_path, managed=_Managed(client, _profile()))):
            pass

    wrong_ws = _Client(grant=_grant(view=_view(workspace_id="ws-" + "9" * 32)))
    with pytest.raises(ExecutionContractError):
        with _pinned_verify_substrate(_ctx(tmp_path, managed=_Managed(wrong_ws, _profile()))):
            pass

    missing_tree = _Client(grant=_grant(view=_view(), input_tree_sha256=None))
    with pytest.raises(ExecutionContractError):
        with _pinned_verify_substrate(_ctx(tmp_path, managed=_Managed(missing_tree, _profile()))):
            pass


def test_a_refused_pin_raises_and_capture_stage_baseline_records_error_without_host_exec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1/R24 — a refused pin never falls back to the controller host for T0 or T1."""

    class _Refusing:
        def pin_reader(self, *_args: Any, **_kwargs: Any) -> Any:
            raise ExecutionRejectedError("INPUT_POLICY", "op-1")

    managed = _Managed(_Refusing(), _profile())
    with pytest.raises(ExecutionRejectedError):
        with _pinned_verify_substrate(_ctx(tmp_path, managed=managed)):
            pass

    host_calls: list[object] = []
    monkeypatch.setattr(slice_verification, "run_commands", lambda *a, **k: host_calls.append((a, k)) or ())
    plan_ids = extract_plan_ids(_PLAN_TEXT)
    ctx = _ctx(tmp_path, managed=managed)
    baseline = _capture_stage_baseline(ctx, plan_ids)

    assert host_calls == []
    assert baseline.nodeids_by_slice == {"SLICE1": None}
    assert baseline.errors and "INPUT_POLICY" in baseline.errors[0]


def test_the_pin_names_the_current_revision_and_keeps_cache_out_of_workspace(tmp_path: Path) -> None:
    """C1 — the view pins the current revision and places read cache under artifact_paths.base_dir."""
    view = _view()
    client = _Client(grant=_grant(view=view))
    ws = tmp_path / "ws"
    ws.mkdir()
    ctx = _ctx(tmp_path, managed=_Managed(client, _profile()), workspace=ws)

    with _pinned_verify_substrate(ctx) as substrate:
        assert substrate is not None
        assert substrate.port is not None
        port_cache_dir = substrate.port.cache_dir
        assert isinstance(port_cache_dir, Path)
        assert ctx.artifact_paths.base_dir in port_cache_dir.parents
        assert not (ws / ".fa").exists()

    assert client.pin_calls and client.pin_calls[0]["revision_id"] == "rev-" + "3" * 32
    assert client.pin_calls[0]["plan_ref"] is ctx.managed_plan_ref
    assert len(client.stop_calls) == 1


def test_capture_stage_baseline_uses_pinned_substrate_when_managed_and_host_when_unmanaged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1 — unmanaged T0 runs with executor=None; managed T0 pins a READ view and stops it."""
    seen: list[tuple[object, object]] = []
    real = workflow_controller.capture_test_nodeids

    def spy(*_args: object, **kwargs: object) -> object:
        seen.append((kwargs.get("executor"), kwargs.get("port")))
        return real(*_args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(workflow_controller, "capture_test_nodeids", spy)
    plan_ids = extract_plan_ids(_PLAN_TEXT)

    _capture_stage_baseline(_ctx(tmp_path, managed=None), plan_ids)
    assert seen == [(None, None)]

    seen.clear()
    client = _Client(grant=_grant(view=_view()))
    _capture_stage_baseline(_ctx(tmp_path, managed=_Managed(client, _profile())), plan_ids)
    assert len(seen) == 1
    assert seen[0][0] is not None and seen[0][1] is not None
    assert len(client.stop_calls) == 1


def test_managed_verify_and_kill_check_run_against_pinned_service_revision_not_stale_host(
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C1 (R24) — full UDS SupervisorService + MuxWorker + CellWorker + PtyPool proof.

    The admitted git revision holds working code and passing tests; the controller
    workspace path holds a deliberately broken copy that fails both tests and kill
    mutation. Every phase (T0 baseline, T1 snapshot, slice commands, and inband
    scratch kill-check) must succeed against the service-pinned revision and leave
    ``.fa`` untouched in the controller workspace.
    """
    (site.source / "src").mkdir(exist_ok=True)
    (site.source / "src" / "demo_calc.py").write_text(
        "def double(x: int) -> int:\n    return x * 2\n",
        encoding="utf-8",
    )
    (site.source / "tests").mkdir(exist_ok=True)
    (site.source / "tests" / "test_demo_calc.py").write_text(
        "from demo_calc import double\n\ndef test_double():\n    assert double(3) == 6\n",
        encoding="utf-8",
    )
    (site.source / "worklogs" / "demo" / "increments").mkdir(parents=True, exist_ok=True)
    (site.source / "worklogs" / "demo" / "increments" / "increment-01-demo.md").write_text(
        _PLAN_TEXT,
        encoding="utf-8",
    )

    private = tmp_path / "local-docker-peer"
    private.mkdir(mode=0o700)
    peer = Endpoint(private / "engine.sock")
    try:
        document = _document(site)
        cell_profile = replace(native_profile(), uid=os.getuid(), gid=os.getgid(), max_command_ms=10_000)
        reader_profile = replace(read_only_profile(), uid=os.getuid(), gid=os.getgid(), max_command_ms=10_000)
        document["profiles"] = [asdict(cell_profile), asdict(reader_profile)]
        document["view_profile_id"] = cell_profile.profile_id
        document["read_only_profile_id"] = reader_profile.profile_id
        cgroup_root = tmp_path / "cgroups"
        approved_cache = tmp_path / "approved-cache"
        approved_cache.mkdir(mode=0o755)
        document["approved_cache"] = str(approved_cache)
        document["rpc_timeout_ms"] = 10_000
        document.update(
            {
                "docker_socket": str(peer.path),
                "docker_daemon_uid": os.getuid(),
                "docker_api_version": "1.45",
                "docker_timeout_ms": 5_000,
                "cgroup_root": str(cgroup_root),
            }
        )

        scratch_counter = 0
        worker_exit_codes: dict[str, int] = {}
        exit_events: dict[str, threading.Event] = {}
        create_records: list[tuple[str, dict[str, Any], Path]] = []

        class _LocalCellPool(PtyPool):
            def __init__(self, *, env: dict[str, str], **kwargs: Any) -> None:
                super().__init__(**kwargs)
                self._cell_env = env

            @override
            def acquire(self, session_id: str, workdir: str | None = None) -> PtySession:
                target = Path(workdir).resolve() if workdir is not None else self.base_cwd
                with self.lock:
                    if session_id not in self.sessions:
                        self.sessions[session_id] = PtySession(
                            session_id,
                            target,
                            server=self._server,
                            env=dict(self._cell_env),
                            run_id=self.run_id,
                            output_limit=self._output_limit,
                        )
                        self._lru[session_id] = None
                    return self.sessions[session_id]

        def create_reply(seen: dict[str, Any]) -> dict[str, Any]:
            cid = f"{len(create_records) + 1:064x}"
            cgroup = cgroup_root / reader_profile.cgroup_parent / cid
            cgroup.mkdir(parents=True, exist_ok=True)
            (cgroup / "cgroup.events").write_text("populated 0\nfrozen 0\n", encoding="utf-8")
            mounts = seen["body"]["HostConfig"]["Mounts"]
            ws_source = next(Path(m["Source"]) for m in mounts if m.get("Target") == "/workspace")
            exit_events[cid] = threading.Event()
            create_records.append((cid, seen["body"].get("Labels", {}), ws_source))
            return {"Id": cid, "Warnings": []}

        def attach_worker(connection: socket.socket) -> None:
            nonlocal scratch_counter
            scratch_counter += 1
            cid, _labels, sealed_workspace = create_records[-1]
            cell_scratch = tmp_path / f"cell-scratch-{scratch_counter}"
            cell_scratch.mkdir(parents=True, exist_ok=True)
            # Supply the same container-level PATH/TMPDIR/PYTHONPATH that profiles.py + entrypoint inject.
            cell_env = {
                "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', os.defpath)}",
                "TMPDIR": str(cell_scratch),
                "PYTHONPATH": str(sealed_workspace / "src"),
            }
            worker = CountingWorker(
                _LocalCellPool(env=cell_env, base_cwd=sealed_workspace, output_limit=MAX_TAIL_BYTES),
                workspace=sealed_workspace,
                max_command_ms=reader_profile.max_command_ms,
                one_shot=True,
            )
            mux = MuxWorker(connection)
            try:
                worker_exit_codes[cid] = serve_once(worker, mux)
            finally:
                exit_events[cid].set()

        def inspect_reply(status: str) -> Reply:
            def _obs(seen: dict[str, Any]) -> dict[str, Any]:
                cid_match = next(
                    (rec for rec in create_records if rec[0] in seen["path"]),
                    create_records[-1],
                )
                cid, labels, _ = cid_match
                if status == "exited":
                    exit_events[cid].wait(timeout=5.0)
                operation_id = labels.get("fa.execution.operation_id", "op-" + "0" * 32)
                running = status == "running"
                return {
                    "Id": cid,
                    "Name": "/fa-job-" + operation_id.removeprefix("op-"),
                    "Image": reader_profile.image_digest,
                    "Config": {"Image": reader_profile.image, "Labels": labels},
                    "State": {
                        "Status": status,
                        "Running": running,
                        "Paused": False,
                        "Restarting": False,
                        "Dead": False,
                        "OOMKilled": False,
                        "Pid": 123 if running else 0,
                        "ExitCode": worker_exit_codes.get(cid, 0),
                    },
                }

            return Reply(200, _obs)

        def _enqueue_exec_replies() -> None:
            peer.replies.extend(
                [
                    Reply(201, create_reply),
                    Reply(204),
                    inspect_reply("running"),
                    Reply(raw=UPGRADE, upgraded=attach_worker),
                    inspect_reply("exited"),
                ]
            )

        # View 1 (T0 baseline): 1 one-shot EXEC followed by STOP_VIEW inspecting that 1 cell.
        _enqueue_exec_replies()
        peer.replies.append(inspect_reply("exited"))
        # View 2 (T1 + slice command + inband kill-check): 3 one-shot EXECs + STOP_VIEW inspecting 3 cells.
        for _ in range(3):
            _enqueue_exec_replies()
        for _ in range(3):
            peer.replies.append(inspect_reply("exited"))

        service_path, config_path = _configs(tmp_path, document)
        monkeypatch.setattr(composition, "DEFAULT_CONFIG_PATH", config_path)

        # Separate stale host tree: if ANY phase reads or runs on ctx.workspace, it breaks.
        stale_host = tmp_path / "stale-controller-workspace"
        (stale_host / "src").mkdir(parents=True)
        (stale_host / "src" / "demo_calc.py").write_text(
            "def double(x: int) -> int:\n    return -999\n", encoding="utf-8"
        )
        (stale_host / "tests").mkdir()
        (stale_host / "tests" / "test_demo_calc.py").write_text(
            "def test_stale_host():\n    assert False, 'controller host must never execute'\n",
            encoding="utf-8",
        )

        # Register the admitted site root in the authority, then point ctx.workspace at stale_host.
        admit_run = RunContext("run-verify-c1", "session-1", site.source, tmp_path / "s.db", tmp_path / "logs")
        plan_ids = extract_plan_ids(_PLAN_TEXT)

        with SupervisorService(read_config_file(service_path)) as service:
            _registered(service)
            with _serving_supervisor(service):
                managed = managed_execution_for_run(admit_run, config_path=config_path)
                assert managed is not None
                try:
                    ctx = _ctx(tmp_path, managed=managed, workspace=stale_host)
                    baseline = _capture_stage_baseline(ctx, plan_ids)
                    assert baseline.errors == ()
                    assert baseline.nodeids_by_slice == {"SLICE1": {"tests/test_demo_calc.py::test_double": True}}

                    with _pinned_verify_substrate(ctx) as substrate:
                        assert substrate is not None
                        assert substrate.port is not None
                        cache_dir = substrate.port.cache_dir
                        now = workflow_controller._capture_nodeids_by_slice(
                            plan_ids, root=ctx.workspace, execution=substrate
                        )
                        verification = verify_plan(
                            plan_ids,
                            root=ctx.workspace,
                            baseline_by_slice=baseline.nodeids_by_slice,
                            now_by_slice=now.nodeids_by_slice,
                            executor=substrate.executor,
                            port=substrate.port,
                        )
                finally:
                    assert managed.close()
    finally:
        peer.close()

    assert verification.blocking is False
    assert len(verification.slice_verifications) == 1
    sv = verification.slice_verifications[0]
    assert sv.verdict is SliceVerdict.PROVEN
    assert len(sv.kill_checks) == 1
    assert sv.kill_checks[0][1].verdict is SliceVerdict.PROVEN
    assert not (stale_host / ".fa").exists()
    assert cache_dir is not None and ctx.artifact_paths.base_dir in cache_dir.parents
