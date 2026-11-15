"""C1: durable publication receipts and forward-only recovery on disposable roots."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from fa.execution.client import ExecutionRejectedError, ExecutionUncertainError
from fa.execution.types import NamespaceRef, Operation
from tests.integration._host import ExecutionHostRuntime

pytestmark = pytest.mark.execution_host


def _workspace_artifacts(runtime: ExecutionHostRuntime, workspace_id: str) -> Path:
    return runtime.service_config.state_root / "workspaces" / workspace_id


def test_exact_publish_replay_returns_the_committed_receipt_without_a_second_revision(
    host_runtime: ExecutionHostRuntime,
) -> None:
    workspace = host_runtime.register_workspace(files={"src/publish.py": b"VERSION = 0\n"})
    workspace.acquire_writer()
    view = workspace.open_write_view()
    port = workspace.port(view)
    before = port.read_file("src/publish.py")
    port.write_file("src/publish.py", "VERSION = 1\n", expected_sha256=before.sha256)

    publication = workspace.publish(view)
    publish_event = next(
        event
        for event in reversed(host_runtime.events)
        if event.get("operation") == Operation.PUBLISH.value and event.get("outcome") == "OK"
    )
    result = host_runtime.client.request(
        Operation.PUBLISH,
        request_id=publish_event["request_id"],
        namespace=workspace.namespace,
        view=view.view_ref,
        grant=view.grant,
        payload=publish_event["payload"],
    )

    workspace_dir = _workspace_artifacts(host_runtime, workspace.workspace_id)
    current = json.loads((workspace_dir / "current.json").read_text(encoding="utf-8"))
    assert result["revision_id"] == publication.revision_id == current["revision_id"]
    assert result["operation_id"] == "op-" + publish_event["request_id"]
    assert result["projection_complete"] is True
    assert not (workspace_dir / "intent.json").exists()
    view_path = workspace_dir / "views" / view.view_ref.view_id / "view.json"
    assert json.loads(view_path.read_text(encoding="utf-8"))["state"] == "PUBLISHED"
    assert (workspace.root / "src/publish.py").read_text(encoding="utf-8") == "VERSION = 1\n"

    intruder = NamespaceRef(workspace.namespace.session_id, workspace.namespace.run_id + "-intruder")
    with pytest.raises(ExecutionRejectedError) as busy:
        host_runtime.request(
            Operation.ACQUIRE_WRITER,
            namespace=intruder,
            payload={"workspace_id": workspace.workspace_id},
        )
    assert busy.value.code == "WORKSPACE_BUSY"
    assert host_runtime.assert_owned_cells_terminal() == 0


def test_restart_forwards_a_committed_pointer_and_quarantines_the_old_owner(
    host_runtime: ExecutionHostRuntime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = b"VALUE = 'before recovery'\n"
    recovered = b"VALUE = 'recovered revision'\n"
    workspace = host_runtime.register_workspace(files={"src/recovery.py": original})
    workspace.acquire_writer()
    view = workspace.open_write_view()
    host_runtime_port = workspace.port(view)
    host_runtime_port.write_file("src/recovery.py", recovered.decode("utf-8"))

    real_replace = os.replace
    injected: list[str] = []

    def fail_once_during_projection(source: Any, destination: Any = None, **kwargs: Any) -> None:
        if not injected and isinstance(source, str) and source.endswith(".publish") and destination == "recovery.py":
            injected.append("after-pointer-commit")
            raise OSError(5, "injected disposable projection fault")
        real_replace(source, destination, **kwargs)

    monkeypatch.setattr(os, "replace", fail_once_during_projection)

    with pytest.raises(ExecutionUncertainError) as uncertain:
        workspace.publish(view)

    assert uncertain.value.code == "DURABILITY_UNKNOWN"
    assert injected == ["after-pointer-commit"]
    workspace_dir = _workspace_artifacts(host_runtime, workspace.workspace_id)
    intent = json.loads((workspace_dir / "intent.json").read_text(encoding="utf-8"))
    current = json.loads((workspace_dir / "current.json").read_text(encoding="utf-8"))
    view_path = workspace_dir / "views" / view.view_ref.view_id / "view.json"
    assert intent["phase"] == "PROJECTING"
    assert intent["base_revision"] == view.view_ref.base_revision
    assert current["revision_id"] == intent["next_revision"]
    assert current["revision_id"] != view.view_ref.base_revision
    assert json.loads(view_path.read_text(encoding="utf-8"))["state"] == "SEALED"
    assert (workspace.root / "src/recovery.py").read_bytes() == original

    # The same real authority startup path consumes the durable intent. It does
    # not reuse the old in-memory owner grant or create a second publication.
    host_runtime.restart_after_unsettled_publication()

    recovered_current = json.loads((workspace_dir / "current.json").read_text(encoding="utf-8"))
    recovered_metadata = json.loads((workspace_dir / "workspace.json").read_text(encoding="utf-8"))
    recovered_view = json.loads(view_path.read_text(encoding="utf-8"))
    assert recovered_current == current
    assert recovered_metadata["status"] == "QUARANTINED"
    assert recovered_view["state"] == "PUBLISHED"
    assert not (workspace_dir / "intent.json").exists()
    assert (workspace.root / "src/recovery.py").read_bytes() == recovered
    assert host_runtime.assert_owned_cells_terminal() == 0

    with pytest.raises(ExecutionRejectedError) as quarantined:
        host_runtime.request(
            Operation.ACQUIRE_WRITER,
            namespace=workspace.namespace,
            payload={"workspace_id": workspace.workspace_id},
        )
    assert quarantined.value.code == "WORKSPACE_BUSY"
