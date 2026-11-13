"""C1 end-to-end and contract tests closing execution-workspace gaps #1-#3.

Gap #1: Non-ordinary planner stages (`ACQUISITION`, `ADMISSION_REPAIR`,
        `EVAL_REPLAN`) and `eval` run on `PIN_READER` + `ReadOnlyManagedBashExecutor`
        without creating or publishing `WRITE/PROJECT` views.
Gap #2: `ADMISSION_REPAIR` reads the candidate seed through `fs_read_file` via
        `CandidateWorkspacePort` (stale->seed fallback without touching host FS)
        and later reads back newly written `CANDIDATE` bytes cleanly.
Gap #3: Discarded `WRITE/PROJECT` views settle via `STOP_VIEW` + view-scoped
        `RELEASE` -> `"REJECTED"`, so subsequent `HANDOFF` / writer `RELEASE`
        never fail with `WORKSPACE_BUSY`.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from fa import cli
from fa.execution import composition
from fa.execution.client import ExecutionClient, ExecutionUnavailableError
from fa.execution.composition import (
    ExecutionBinding,
    ManagedExecution,
    managed_execution_for_run,
)
from fa.execution.protocol import Operation
from fa.execution.publication import render_bundle
from fa.execution.service import SupervisorService, read_config_file
from fa.execution.types import ExecutionContractError, GrantReply, NamespaceRef
from fa.inner_loop.coder_loop import SessionOutcome
from fa.inner_loop.registry import ToolRegistry
from fa.inner_loop.session_db import SessionDatabase
from fa.inner_loop.tools import build_read_file_tool
from fa.inner_loop.tools.workspace_port import PortRead, WorkspacePortError
from fa.paths import fa_state_root
from fa.providers.base import ResponseInfo
from fa.providers.chain import ProviderChain
from fa.providers.secret_store import SecretStore
from fa.session.manager import RunContext, SessionContext, SessionManager
from fa.session.provisioning import ProvisionedWorkspace
from fa.workspace_bootstrap import ReadyState, ReadyStatus
from tests.test_execution_composition import (
    Endpoint,
    _configs,
    _configure_local_cell_backend,
    _document,
    _serving_supervisor,
    _watch_managed_child_host_execution,
    local_cell_peer,
    native_profile,
    read_only_profile,
)
from tests.test_execution_service import _config as _service_config
from tests.test_execution_service import _error, _plant_cell, _registered, _view, _writer, exchange
from tests.test_execution_workspace import Site, install_environment_artifact, site

__all__ = ["local_cell_peer", "site"]

_SLUG = "planning-topology-and-executable-contracts-loop"
_PLAN_RELATIVE = f"worklogs/{_SLUG}/increments/increment-01-foundation.md"


def _tool_reply(call_id: str, name: str, arguments: dict[str, Any], tag: str) -> tuple[ResponseInfo, str, list[Any]]:
    call = {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }
    return ResponseInfo("", 1, 1, "tool_calls", (call,)), tag, []


def _stop_reply(text: str, tag: str) -> tuple[ResponseInfo, str, list[Any]]:
    return ResponseInfo(text, 1, 1, "stop"), tag, []


def _tool_names(request: Any) -> set[str]:
    return {
        str(tool.get("function", {}).get("name", ""))
        for tool in request.tools
        if isinstance(tool.get("function"), dict)
    }


def _system_text(request: Any) -> str:
    return "\n".join(str(m.get("content", "")) for m in request.messages if m.get("role") == "system")


def _write_models_config(root: Path) -> Path:
    models = root / "models.yaml"
    models.write_text(
        """chat:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: K
planner:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: K
coder:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: K
eval:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: K
""",
        encoding="utf-8",
    )
    return models


def _setup_managed_site(
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    local_cell_peer: Endpoint | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    monkeypatch.setenv("FA_STATE_ROOT", str(tmp_path / "fa-state"))
    monkeypatch.setenv("FA_WORKSPACE_ROOT", str(site.roots))
    models = _write_models_config(site.source)
    document = _document(site)
    if local_cell_peer is not None:
        _, reader_profile, _ = _configure_local_cell_backend(local_cell_peer, tmp_path, document)
        install_environment_artifact(Path(document["approved_cache"]), site.source, profile=reader_profile)
    else:
        cell_profile = native_profile()
        reader_profile = read_only_profile()
        document["profiles"] = [asdict(cell_profile), asdict(reader_profile)]
        document["view_profile_id"] = cell_profile.profile_id
        document["read_only_profile_id"] = reader_profile.profile_id
    service_path, service_config = _configs(tmp_path, document)
    monkeypatch.setattr(composition, "DEFAULT_CONFIG_PATH", service_config)
    return models, service_path, document


def _install_bundle(root: Path, *, include_tests: bool) -> dict[str, bytes]:
    tests_line = "TESTS: tests/test_managed_workflow_e2e.py\n" if include_tests else ""
    files = render_bundle(
        _SLUG,
        "foundation",
        "## Intent\n\nA project.\n\n## Out of scope\n\nOther work.\n",
        f"## SLICE1: Foundation\nCONTRACTS:\n  CT1 [CONSTRAINT]: initial.\n{tests_line}",
        created="2026-11-02",
    )
    for rel, raw in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    llms = root / "knowledge" / "llms.txt"
    llms.parent.mkdir(parents=True, exist_ok=True)
    llms.write_text("# project index\n", encoding="utf-8")
    return files


def _wire_session_contexts(
    site: Site,
    monkeypatch: pytest.MonkeyPatch,
    *,
    session_id: str,
    run_id: str,
) -> tuple[SessionContext, RunContext, SessionDatabase]:
    manager = SessionManager(
        state_root=fa_state_root(),
        workspace_root=site.roots,
        source_workspace=site.source,
        workspace_provisioner=lambda _req: ProvisionedWorkspace(True, "ws-" + "1" * 32, "rev-" + "2" * 32, None),
        workspace_preparer=lambda *_a: ReadyState(
            ReadyStatus.READY, None, "ready_fast_path", site.source / "ready.log", False, 1
        ),
    )
    session = manager.provision_entrypoint_session(session_id=session_id, workspace_override=site.source)
    run = manager.begin_run(session, requested_run_id=run_id)
    session_db = SessionDatabase.open_existing(session.session_db_path, session_id=session.session_id)
    orig_resolve_cli = cli._resolve_cli_run_context

    class _ManagedWorkspace:
        @staticmethod
        def resolve_workflow_workspace(**_kwargs: Any) -> Path:
            return site.source

    monkeypatch.setattr(
        cli,
        "_resolve_cli_run_context",
        lambda args: (
            orig_resolve_cli(args) if getattr(args, "_run_context", None) is not None else (session, run, session_db)
        ),
    )
    monkeypatch.setattr(cli, "_resolve_workflow_lifecycle", lambda _args, rid: (rid, session, run, session_db))
    monkeypatch.setattr(cli, "_session_manager_for_args", lambda _args: _ManagedWorkspace())
    return session, run, session_db


def _candidate_target_from_tools(request: Any) -> str | None:
    for tool in request.tools:
        fn = tool.get("function") or {}
        if fn.get("name") == "fs_write_file":
            enum = fn.get("parameters", {}).get("properties", {}).get("path", {}).get("enum")
            if isinstance(enum, list) and len(enum) == 1 and isinstance(enum[0], str):
                return enum[0]
    return None


def _track_managed(monkeypatch: pytest.MonkeyPatch) -> list[ManagedExecution]:
    managed_list: list[ManagedExecution] = []
    orig_managed = managed_execution_for_run

    def capture_managed(*a: Any, **kw: Any) -> ManagedExecution | None:
        m = orig_managed(*a, **kw)
        if m is not None:
            managed_list.append(m)
        return m

    monkeypatch.setattr(cli, "managed_execution_for_run", capture_managed)
    return managed_list


def _spy_operations(service: SupervisorService) -> list[tuple[Operation, dict[str, Any], dict[str, Any]]]:
    events: list[tuple[Operation, dict[str, Any], dict[str, Any]]] = []
    handlers: list[tuple[str, Operation]] = [
        ("_pin_reader", Operation.PIN_READER),
        ("_create_view", Operation.CREATE_VIEW),
        ("_write_file", Operation.WRITE_FILE),
        ("_read_file", Operation.READ_FILE),
        ("_seal", Operation.SEAL),
        ("_publish", Operation.PUBLISH),
        ("_stop_view", Operation.STOP_VIEW),
        ("_release", Operation.RELEASE),
        ("_handoff", Operation.HANDOFF),
        ("_exec", Operation.EXEC),
    ]
    for attr, op in handlers:
        original = getattr(service, attr)

        def make_wrapper(
            op_kind: Operation, fn: Callable[[Any, dict[str, Any], float], Any]
        ) -> Callable[[Any, dict[str, Any], float], Any]:
            def wrapper(peer: Any, request: dict[str, Any], deadline: float) -> Any:
                events.append((op_kind, dict(request), dict(request.get("payload") or {})))
                return fn(peer, request, deadline)

            return wrapper

        setattr(service, attr, make_wrapper(op, original))
    return events


def test_invoke_workflow_chat_acquisition_coder_eval_uses_pin_reader_and_releases(
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    local_cell_peer: Endpoint,
) -> None:
    """Gap #1 C1: chat -> invoke_workflow(planner,coder,eval) runs acquisition & eval on PIN_READER."""
    _install_bundle(site.source, include_tests=True)
    models, service_path, _ = _setup_managed_site(site, tmp_path, monkeypatch, local_cell_peer=local_cell_peer)
    _wire_session_contexts(site, monkeypatch, session_id="s-gap1", run_id="run-chat-1")
    _watch_managed_child_host_execution(monkeypatch)

    stage_turns: dict[str, int] = {"chat": 0, "planner": 0, "coder": 0, "eval": 0}
    eval_pass = (
        "## Verification Summary\n\n### Step results\n- SLICE1: PASS\n\n"
        "### Verdict\nPASS\n\n### Route decision\ncomplete\n"
    )
    selection = json.dumps({"kind": "SELECT_EXISTING", "project_slug": _SLUG, "increment_id": "I01"})

    def fake_request(
        _chain: Any, request: Any, *, logical_call_id: str | None = None
    ) -> tuple[ResponseInfo, str, list[Any]]:
        tools = _tool_names(request)
        system = _system_text(request)
        tag = logical_call_id or "test"
        if "invoke_workflow" in tools:
            role = "chat"
        elif "you are the first-agent evaluator" in system.lower():
            role = "eval"
        elif "fs_run_bash" in tools:
            role = "coder"
        else:
            role = "planner"
        turn = stage_turns[role]
        stage_turns[role] = turn + 1

        if role == "chat":
            if turn == 0:
                return _tool_reply(
                    "chat-1",
                    "invoke_workflow",
                    {"task": "implement feature", "roles": "planner,coder,eval"},
                    tag,
                )
            return _stop_reply("workflow done", tag)
        if role == "planner":
            if turn == 0:
                return _tool_reply("plan-search", "fs_search", {"output_mode": "files"}, tag)
            if turn == 1:
                return _tool_reply("plan-1", "fs_read_file", {"path": _PLAN_RELATIVE}, tag)
            return _stop_reply(selection, tag)
        if role == "coder":
            if turn == 0:
                return _tool_reply("code-1", "fs_write_file", {"path": "src/gap1.py", "content": "GAP1 = 1\n"}, tag)
            return _stop_reply("implemented src/gap1.py", tag)
        # eval role (verifier profile exposes fs_run_bash, not fs_read_file)
        if turn == 0:
            return _tool_reply("eval-1", "fs_run_bash", {"command": "printf eval-ok"}, tag)
        return _stop_reply(eval_pass, tag)

    monkeypatch.setattr(ProviderChain, "request", fake_request)
    managed_list = _track_managed(monkeypatch)
    args = cli.build_parser().parse_args(
        [
            "run",
            "--role",
            "chat",
            "--task",
            "implement via workflow",
            "--workspace",
            str(site.source),
            "--config",
            str(models),
            "--max-turns",
            "6",
        ]
    )

    with SupervisorService(read_config_file(service_path)) as service:
        ops = _spy_operations(service)
        with _serving_supervisor(service):
            exit_code = cli._cmd_run(args, secrets=SecretStore({"K": "sk-test-live"}))

    assert exit_code == 0
    assert (site.source / "src" / "gap1.py").read_text(encoding="utf-8") == "GAP1 = 1\n"
    assert stage_turns == {"chat": 2, "planner": 3, "coder": 2, "eval": 2}
    assert any("project_tool" in payload for op, _, payload in ops if op is Operation.EXEC)

    pin_ops = [payload for op, _, payload in ops if op is Operation.PIN_READER]
    create_project_write_ops = [
        (req, payload)
        for op, req, payload in ops
        if op is Operation.CREATE_VIEW and payload.get("access") == "WRITE" and payload.get("purpose") == "PROJECT"
    ]
    exec_ops = [payload for op, _, payload in ops if op is Operation.EXEC]
    publish_ops = [req for op, req, _ in ops if op is Operation.PUBLISH]
    # ACQUISITION and eval pinned READ/PROJECT views; parent chat (suspend + final) and coder wrote PROJECT views.
    assert len(pin_ops) >= 2
    assert len(create_project_write_ops) == 3
    assert len(exec_ops) == 2
    assert any("project_tool" in p and p.get("profile_id") == "reader" for p in exec_ops)
    assert any(
        p.get("command") == "printf eval-ok" and p.get("profile_id") == "reader" and p.get("session_id") is None
        for p in exec_ops
    )
    assert len(publish_ops) == 3
    assert len(managed_list) == 1
    assert site.metadata({"workspace_id": managed_list[0].binding.workspace_id})["status"] == "AVAILABLE"


def test_ordinary_planning_keeps_write_project_while_eval_uses_pin_reader(
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gap #1 contrast: ORDINARY_PLANNING retains WRITE/PROJECT while eval uses PIN_READER."""
    _install_bundle(site.source, include_tests=True)
    models, service_path, _ = _setup_managed_site(site, tmp_path, monkeypatch)
    _wire_session_contexts(site, monkeypatch, session_id="s-ord", run_id="run-ord-1")
    eval_pass = (
        "## Verification Summary\n\n### Step results\n- SLICE1: PASS\n\n"
        "### Verdict\nPASS\n\n### Route decision\ncomplete\n"
    )
    turns = {"planner": 0, "coder": 0, "eval": 0}

    def fake_request(
        _chain: Any, request: Any, *, logical_call_id: str | None = None
    ) -> tuple[ResponseInfo, str, list[Any]]:
        tools = _tool_names(request)
        system = _system_text(request)
        tag = logical_call_id or "ord"
        if "you are the first-agent evaluator" in system.lower():
            role = "eval"
        elif "fs_run_bash" in tools:
            role = "coder"
        else:
            role = "planner"
        t = turns[role]
        turns[role] = t + 1
        if role == "planner":
            if t == 0:
                return _tool_reply(
                    "p-1",
                    "fs_write_file",
                    {"path": "knowledge/research/notes.md", "content": "# Plan Notes\n"},
                    tag,
                )
            return _stop_reply("planned", tag)
        if role == "coder":
            if t == 0:
                return _tool_reply("c-1", "fs_write_file", {"path": "src/ord.py", "content": "ORD = True\n"}, tag)
            return _stop_reply("coded", tag)
        return _stop_reply(eval_pass, tag)

    monkeypatch.setattr(ProviderChain, "request", fake_request)
    managed_list = _track_managed(monkeypatch)
    args = cli.build_parser().parse_args(
        [
            "workflow",
            "planner,coder,eval",
            "implement ordinary",
            "--plan",
            _PLAN_RELATIVE,
            "--workspace",
            str(site.source),
            "--session-id",
            "s-ord",
            "--run-id",
            "run-ord-1",
            "--config",
            str(models),
            "--max-turns",
            "4",
        ]
    )

    with SupervisorService(read_config_file(service_path)) as service:
        ops = _spy_operations(service)
        with _serving_supervisor(service):
            exit_code = cli._cmd_workflow(args, secrets=SecretStore({"K": "sk-test-live"}))

    assert exit_code == 0
    assert (site.source / "knowledge" / "research" / "notes.md").read_text(encoding="utf-8") == "# Plan Notes\n"
    assert (site.source / "src" / "ord.py").read_text(encoding="utf-8") == "ORD = True\n"
    write_project_views = [
        op
        for op, _, payload in ops
        if op is Operation.CREATE_VIEW and payload.get("access") == "WRITE" and payload.get("purpose") == "PROJECT"
    ]
    pin_views = [op for op, _, _ in ops if op is Operation.PIN_READER]
    assert len(write_project_views) == 2  # planner (ORDINARY_PLANNING) + coder; eval never opens WRITE/PROJECT
    assert len(pin_views) >= 1  # eval (plus read-only workflow substrates) pinned READ views
    assert site.metadata({"workspace_id": managed_list[0].binding.workspace_id})["status"] == "AVAILABLE"


def _repair_planner_step(
    turn: int,
    target: str,
    request: Any,
    repair_reads: list[str],
    *,
    draft_1: str,
    repaired_final: str,
    tag: str,
) -> tuple[ResponseInfo, str, list[Any]]:
    if turn == 0:
        return _tool_reply("rep-1", "fs_read_file", {"path": target}, tag)
    if turn == 1:
        repair_reads.append(str(request.messages[-1].get("content", "")))
        return _tool_reply("rep-2", "fs_write_file", {"path": target, "content": draft_1}, tag)
    if turn == 2:
        return _tool_reply("rep-3", "fs_read_file", {"path": target}, tag)
    if turn == 3:
        repair_reads.append(str(request.messages[-1].get("content", "")))
        return _tool_reply("rep-4", "fs_write_file", {"path": target, "content": repaired_final}, tag)
    return _stop_reply("repaired plan", tag)


def test_admission_repair_reads_seed_via_candidate_port_without_host_io_and_updates_candidate(
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gap #2 C1: ADMISSION_REPAIR reads seed on first fs_read_file (no host FS, no pre-write),
    writes repaired candidate, then reads the updated candidate bytes on second fs_read_file.
    """
    files = _install_bundle(site.source, include_tests=False)
    seed_text = files[_PLAN_RELATIVE].decode("utf-8")
    draft_1 = seed_text + "\nTESTS: missing-still-incomplete\n"
    repaired_final = seed_text + "TESTS: tests/test_managed_workflow_e2e.py\n"

    models, service_path, _ = _setup_managed_site(site, tmp_path, monkeypatch)
    _wire_session_contexts(site, monkeypatch, session_id="s-gap2", run_id="run-gap2-1")
    eval_pass = (
        "## Verification Summary\n\n### Step results\n- SLICE1: PASS\n\n"
        "### Verdict\nPASS\n\n### Route decision\ncomplete\n"
    )

    host_plan_reads: list[str] = []
    orig_read_bytes = Path.read_bytes

    def guarded_read_bytes(self: Path) -> bytes:
        s = str(self)
        if ".fa/admission" in s and s.endswith(".md"):
            host_plan_reads.append(s)
        return orig_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)

    repair_reads: list[str] = []
    repair_turn = 0
    ordinary_planner_done = False
    coder_turn = 0
    seen_candidate_targets: list[str] = []

    def fake_request(
        _chain: Any, request: Any, *, logical_call_id: str | None = None
    ) -> tuple[ResponseInfo, str, list[Any]]:
        nonlocal repair_turn, ordinary_planner_done, coder_turn
        tools = _tool_names(request)
        system = _system_text(request)
        tag = logical_call_id or "gap2"
        if "you are the first-agent evaluator" in system.lower():
            return _stop_reply(eval_pass, tag)
        if "fs_edit_file" in tools:
            t = coder_turn
            coder_turn += 1
            if t == 0:
                return _tool_reply("cd-1", "fs_write_file", {"path": "src/repaired.py", "content": "OK = True\n"}, tag)
            return _stop_reply("coded", tag)

        candidate_target = _candidate_target_from_tools(request)
        # Stage 1/3 is ORDINARY_PLANNING (no candidate enum) before pre-coder _admit_plan invokes ADMISSION_REPAIR.
        if not ordinary_planner_done and candidate_target is None:
            ordinary_planner_done = True
            return _stop_reply("ordinary planning complete", tag)

        assert candidate_target is not None and candidate_target.startswith(".fa/admission/")
        if not seen_candidate_targets:
            seen_candidate_targets.append(candidate_target)

        t = repair_turn
        repair_turn += 1
        return _repair_planner_step(
            t, candidate_target, request, repair_reads, draft_1=draft_1, repaired_final=repaired_final, tag=tag
        )

    monkeypatch.setattr(ProviderChain, "request", fake_request)
    managed_list = _track_managed(monkeypatch)
    args = cli.build_parser().parse_args(
        [
            "workflow",
            "planner,coder,eval",
            "repair and implement",
            "--plan",
            _PLAN_RELATIVE,
            "--workspace",
            str(site.source),
            "--session-id",
            "s-gap2",
            "--run-id",
            "run-gap2-1",
            "--config",
            str(models),
            "--max-turns",
            "8",
        ]
    )

    with SupervisorService(read_config_file(service_path)) as service:
        ops = _spy_operations(service)
        with _serving_supervisor(service):
            exit_code = cli._cmd_workflow(args, secrets=SecretStore({"K": "sk-test-live"}))

    assert exit_code == 0
    assert len(seen_candidate_targets) == 1
    assert host_plan_reads == []
    assert len(repair_reads) == 2
    assert "CT1 [CONSTRAINT]: initial." in repair_reads[0]
    assert "TESTS:" not in repair_reads[0]
    assert "TESTS: missing-still-incomplete" in repair_reads[1]

    candidate_writes = [
        (req.get("view_ref", {}).get("purpose"), payload.get("expected_sha256"))
        for op, req, payload in ops
        if op is Operation.WRITE_FILE and req.get("view_ref", {}).get("purpose") == "CANDIDATE"
    ]
    assert candidate_writes == [
        ("CANDIDATE", None),
        ("CANDIDATE", hashlib.sha256(draft_1.encode("utf-8")).hexdigest()),
        ("CANDIDATE", None),  # BoundPlanPublisher publishes repaired snapshot via a fresh CANDIDATE view.
    ]
    project_writes = [
        req
        for op, req, payload in ops
        if op is Operation.CREATE_VIEW and payload.get("purpose") == "PROJECT" and payload.get("access") == "WRITE"
    ]
    pin_readers = [op for op, _, _ in ops if op is Operation.PIN_READER]
    # ORDINARY_PLANNING + coder wrote PROJECT views; ADMISSION_REPAIR and eval both pinned READ views.
    assert len(project_writes) == 2
    assert len(pin_readers) >= 2
    assert (site.source / _PLAN_RELATIVE).read_text(encoding="utf-8") == repaired_final
    assert (site.source / "src" / "repaired.py").read_text(encoding="utf-8") == "OK = True\n"
    assert site.metadata({"workspace_id": managed_list[0].binding.workspace_id})["status"] == "AVAILABLE"


def test_aborted_write_stage_settles_rejected_so_handoff_and_writer_release_succeed(
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gap #3 C1: child coder hitting iteration_cap rejects its WRITE view before HANDOFF to chat."""
    _install_bundle(site.source, include_tests=True)
    models, service_path, _ = _setup_managed_site(site, tmp_path, monkeypatch)
    _wire_session_contexts(site, monkeypatch, session_id="s-gap3", run_id="run-chat-gap3")
    _watch_managed_child_host_execution(monkeypatch)

    selection = json.dumps({"kind": "SELECT_EXISTING", "project_slug": _SLUG, "increment_id": "I01"})
    turns = {"chat": 0, "planner": 0, "coder": 0}

    def fake_request(
        _chain: Any, request: Any, *, logical_call_id: str | None = None
    ) -> tuple[ResponseInfo, str, list[Any]]:
        tools = _tool_names(request)
        tag = logical_call_id or "gap3"
        if "invoke_workflow" in tools:
            t = turns["chat"]
            turns["chat"] = t + 1
            if t == 0:
                return _tool_reply(
                    "ch-1",
                    "invoke_workflow",
                    {"task": "fail coder at cap", "roles": "planner,coder"},
                    tag,
                )
            return _stop_reply("parent handled child abort cleanly", tag)
        if "fs_run_bash" not in tools:
            turns["planner"] += 1
            return _stop_reply(selection, tag)
        # Child coder writes across both turns without stopping -> max_turns=2 -> iteration_cap (exit_code=1)
        turns["coder"] += 1
        return _tool_reply(
            f"cd-{turns['coder']}",
            "fs_write_file",
            {"path": "src/aborted.py", "content": "ABORTED = True\n"},
            tag,
        )

    monkeypatch.setattr(ProviderChain, "request", fake_request)
    managed_list = _track_managed(monkeypatch)
    args = cli.build_parser().parse_args(
        [
            "run",
            "--role",
            "chat",
            "--task",
            "run child that hits iteration_cap",
            "--workspace",
            str(site.source),
            "--config",
            str(models),
            "--max-turns",
            "2",
        ]
    )

    with SupervisorService(read_config_file(service_path)) as service:
        ops = _spy_operations(service)
        with _serving_supervisor(service):
            exit_code = cli._cmd_run(args, secrets=SecretStore({"K": "sk-test-live"}))

    assert exit_code == 0
    assert turns == {"chat": 2, "planner": 1, "coder": 2}
    assert not (site.source / "src" / "aborted.py").exists()
    op_kinds = [op for op, _, _ in ops]
    # Child coder's WRITE view stopped and view-released (REJECTED) BEFORE return HANDOFF!
    # Look for a STOP_VIEW immediately followed by view-scoped RELEASE before the final HANDOFF.
    handoff_indices = [idx for idx, op in enumerate(op_kinds) if op is Operation.HANDOFF]
    assert len(handoff_indices) == 2
    stop_indices = [
        idx
        for idx, (op, req, _) in enumerate(ops)
        if op is Operation.STOP_VIEW and req.get("view_ref", {}).get("access") == "WRITE"
    ]
    # 3 WRITE stops: parent chat (suspend), child coder (aborted at cap), parent chat (final).
    assert len(stop_indices) == 3
    coder_stop_idx = stop_indices[1]
    assert op_kinds[coder_stop_idx + 1] is Operation.RELEASE
    assert ops[coder_stop_idx + 1][1].get("view_ref") is not None
    assert handoff_indices[1] > coder_stop_idx + 1
    assert site.metadata({"workspace_id": managed_list[0].binding.workspace_id})["status"] == "AVAILABLE"


def test_write_view_release_contract_enforces_stopping_and_terminality(site: Site) -> None:
    """Gap #3 C0/C1: authority rejects RELEASE on OPEN/unsettled WRITE view, accepts STOPPING+terminal."""
    with SupervisorService(_service_config(site)) as service:
        workspace_id = _registered(service)
        writer_cap, revision_id = _writer(service, workspace_id, request_id="1" * 32)
        view, view_cap = _view(service, workspace_id, revision_id, writer_cap, request_id="2" * 32)

        # OPEN WRITE view cannot be released.
        open_release = exchange(service, Operation.RELEASE, {}, request_id="3" * 32, view_ref=view, capability=view_cap)
        assert _error(open_release) == "VIEW_CLOSED"

        # Real STOP_VIEW settling cleanly (no cells) -> STOPPING + terminal.json -> RELEASE -> REJECTED.
        stopped = exchange(service, Operation.STOP_VIEW, {}, request_id="4" * 32, view_ref=view, capability=view_cap)
        assert stopped["status"] == "OK", stopped
        still_busy = exchange(service, Operation.RELEASE, {}, request_id="5" * 32, capability=writer_cap)
        assert _error(still_busy) == "WORKSPACE_BUSY"

        released_view = exchange(
            service, Operation.RELEASE, {}, request_id="6" * 32, view_ref=view, capability=view_cap
        )
        assert released_view["status"] == "OK", released_view
        assert released_view["result"] == {"released": True}
        view_json_path = site.state / "workspaces" / workspace_id / "views" / view["view_id"] / "view.json"
        assert json.loads(view_json_path.read_text(encoding="utf-8"))["state"] == "REJECTED"

        # Subsequent WRITE_FILE on rejected view fails closed.
        late_write = exchange(
            service,
            Operation.WRITE_FILE,
            {"path": "late.txt", "content_b64": "eA==", "expected_sha256": None},
            request_id="7" * 32,
            view_ref=view,
            capability=view_cap,
        )
        assert late_write["status"] == "ERROR"

        # Second WRITE view whose STOP_VIEW cannot prove terminality (STOPPING without terminal.json)
        # MUST fail view-scoped RELEASE with TERMINALITY_UNKNOWN.
        unproven_view, unproven_cap = _view(service, workspace_id, revision_id, writer_cap, request_id="a" * 32)
        _plant_cell(service, unproven_view, unproven_cap, request_id="b" * 32)
        failed_stop = exchange(
            service, Operation.STOP_VIEW, {}, request_id="c" * 32, view_ref=unproven_view, capability=unproven_cap
        )
        assert _error(failed_stop) == "BACKEND_UNAVAILABLE"
        unproven_release = exchange(
            service, Operation.RELEASE, {}, request_id="d" * 32, view_ref=unproven_view, capability=unproven_cap
        )
        assert _error(unproven_release) == "TERMINALITY_UNKNOWN"

        # Writer RELEASE stays blocked while an unproven view remains unsettled.
        writer_release_blocked = exchange(service, Operation.RELEASE, {}, request_id="e" * 32, capability=writer_cap)
        assert _error(writer_release_blocked) == "WORKSPACE_BUSY"


def test_writer_release_succeeds_after_rejected_write_view_on_fresh_workspace(site: Site) -> None:
    """Gap #3 C1: view-scoped RELEASE on a stopped empty WRITE view unblocks writer RELEASE."""
    with SupervisorService(_service_config(site)) as service:
        workspace_id = _registered(service)
        writer_cap, revision_id = _writer(service, workspace_id, request_id="1" * 32)
        view, view_cap = _view(service, workspace_id, revision_id, writer_cap, request_id="2" * 32)
        assert (
            exchange(service, Operation.STOP_VIEW, {}, request_id="3" * 32, view_ref=view, capability=view_cap)[
                "status"
            ]
            == "OK"
        )
        assert exchange(service, Operation.RELEASE, {}, request_id="4" * 32, view_ref=view, capability=view_cap)[
            "result"
        ] == {"released": True}
        writer_release = exchange(service, Operation.RELEASE, {}, request_id="5" * 32, capability=writer_cap)
        assert writer_release["status"] == "OK", writer_release
        assert site.metadata({"workspace_id": workspace_id})["status"] == "AVAILABLE"


def test_read_only_stage_and_candidate_seed_fail_closed(tmp_path: Path) -> None:
    """Gap #1 & #2 fail-closed guards: missing read_only_profile & non-stale candidate read error."""
    workspace = tmp_path / "project"
    workspace.mkdir()
    for bad_read_profile in (None, native_profile()):
        managed = ManagedExecution(
            client=ExecutionClient(tmp_path / "supervisor.sock", server_uid=os.getuid(), rpc_timeout_ms=100),
            binding=ExecutionBinding(NamespaceRef("s1", "r1"), "ws-" + "1" * 32),
            grant=GrantReply(Operation.ACQUIRE_WRITER, "a" * 64, None, 1, "rev-" + "2" * 32, None),
            view_profile=native_profile(),
            read_only_profile=None,
        )
        managed.read_only_profile = bad_read_profile
        with pytest.raises(ExecutionContractError):
            cli._drive_stage_with_managed_workspace(
                managed=managed,
                owns_writer=False,
                run_id="r1",
                run_log_dir=tmp_path / "logs",
                session_db=None,
                workspace=workspace,
                role="eval",
                plan_ref=None,
                build_registry=lambda *_a: ToolRegistry(),
                drive=lambda _r: SessionOutcome(0, "stop", 0, ""),
            )

    class _DeniedCandidate:
        def read_candidate(self, *, max_bytes: int = 1024 * 1024) -> PortRead:
            del max_bytes
            raise WorkspacePortError("denied")

    class _DummyPort:
        @property
        def cache_dir(self) -> None:
            return None

        def read_file(self, path: str, *, offset_bytes: int = 0, max_bytes: int = 1024) -> PortRead:
            raise AssertionError(f"host/project port must not read candidate target: {path}")

    spec = build_read_file_tool(
        workspace,
        workspace_io=_DummyPort(),  # type: ignore[arg-type]
        candidate_target=_PLAN_RELATIVE,
        candidate_io=_DeniedCandidate(),  # type: ignore[arg-type]
        candidate_seed_text="SEED_MUST_NOT_LEAK",
    )
    result = spec.handler({"path": _PLAN_RELATIVE})
    assert result.error is not None
    assert result.error.code == "read_failed"
    assert "SEED_MUST_NOT_LEAK" not in (result.summary or "")

    class _TruncatedCandidate:
        def read_candidate(self, *, max_bytes: int = 1024 * 1024) -> PortRead:
            del max_bytes
            return PortRead("PARTIAL_MUST_NOT_LEAK", "0" * 64, False)

    trunc_spec = build_read_file_tool(
        workspace,
        workspace_io=_DummyPort(),  # type: ignore[arg-type]
        candidate_target=_PLAN_RELATIVE,
        candidate_io=_TruncatedCandidate(),  # type: ignore[arg-type]
    )
    trunc_result = trunc_spec.handler({"path": _PLAN_RELATIVE})
    assert trunc_result.error is not None
    assert trunc_result.error.code == "read_failed"
    assert "PARTIAL_MUST_NOT_LEAK" not in (trunc_result.summary or "")


def test_read_only_stage_failed_stop_view_never_retries(
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adversary review fix: a failed STOP_VIEW on a read-only stage is never retried in except."""
    _, service_path, _ = _setup_managed_site(site, tmp_path, monkeypatch)
    with SupervisorService(read_config_file(service_path)) as service, _serving_supervisor(service):
        _, run, _ = _wire_session_contexts(site, monkeypatch, session_id="s-ro-stop", run_id="r-ro-stop")
        managed = managed_execution_for_run(run)
        assert managed is not None
        stop_calls: list[GrantReply] = []

        def fail_once(grant: GrantReply, *, deadline: float | None = None) -> bool:
            del deadline
            stop_calls.append(grant)
            return False

        monkeypatch.setattr(managed, "stop_view", fail_once)
        try:
            with pytest.raises(ExecutionUnavailableError):
                cli._drive_stage_with_managed_workspace(
                    managed=managed,
                    owns_writer=False,
                    run_id="r-ro-stop",
                    run_log_dir=tmp_path / "logs",
                    session_db=None,
                    workspace=site.source,
                    role="eval",
                    plan_ref=None,
                    build_registry=lambda *_a: ToolRegistry(),
                    drive=lambda _r: SessionOutcome(0, "stop", 0, ""),
                )
            assert len(stop_calls) == 1
        finally:
            assert managed.close()
