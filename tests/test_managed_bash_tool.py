"""Managed fs_run_bash never repeats a command on the host (STEP2b supplier)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fa.execution.client import ManagedBashExecutor
from fa.execution.types import Access, ViewPurpose
from fa.inner_loop.tools import run_bash
from fa.inner_loop.tools.run_bash import build_run_bash_tool
from tests.test_execution_client import NS, SHA, VIEW, endpoint, profile, result, view_grant
from tests.test_execution_client_port import _plan_ref, _served
from tests.test_execution_views import native_profile
from tests.test_execution_workspace import Site
from tests.test_execution_workspace import site as site


def _executor(client: Any, root: Path) -> ManagedBashExecutor:
    return ManagedBashExecutor(
        client,
        namespace=NS,
        view=VIEW,
        grant=view_grant(),
        profile=profile(),
        input_tree_sha256=SHA,
        plan_sha256=SHA,
        original_revision_id=VIEW.base_revision,
        controller_root=root,
    )


def _no_host(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    calls: list[object] = []

    def forbidden(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))
        raise AssertionError("host subprocess forbidden")

    monkeypatch.setattr(run_bash.subprocess, "run", forbidden)
    # Exercise the legacy git-status tracking path, without a host command.
    monkeypatch.setattr(
        run_bash, "_resolve_execution_context", lambda _root: run_bash._ExecutionContext(None, None, object())
    )
    return calls


def test_managed_success_is_one_wire_execution_without_host_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    host_calls = _no_host(monkeypatch)
    with endpoint(tmp_path) as (client, seen):
        tool = build_run_bash_tool(tmp_path, managed_executor=_executor(client, tmp_path))
        answer = tool.handler({"command": "printf ok"})
    assert answer.error is None
    assert answer.result["stdout"] == "stdoutstderr"
    assert [item["op"] for item in seen] == ["exec"]
    assert host_calls == []


@pytest.mark.parametrize(
    ("wire_code", "expected"),
    [
        ("BACKEND_UNAVAILABLE", "execution_unavailable"),
        ("EXECUTION_UNKNOWN", "execution_uncertain"),
        ("UNAUTHORIZED", "execution_rejected"),
    ],
)
def test_wire_failures_never_trigger_host_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    wire_code: str,
    expected: str,
) -> None:
    host_calls = _no_host(monkeypatch)
    with endpoint(tmp_path, error_code=wire_code) as (client, seen):
        answer = build_run_bash_tool(tmp_path, managed_executor=_executor(client, tmp_path)).handler(
            {"command": "touch host"}
        )
    assert answer.error is not None and answer.error.code == expected
    assert not answer.error.retryable
    assert [item["op"] for item in seen] == ["exec"]
    assert host_calls == [] and not (tmp_path / "host").exists()


def test_lost_reply_is_not_replayed_or_fallen_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host_calls = _no_host(monkeypatch)
    with endpoint(tmp_path, lambda _: None) as (client, seen):
        answer = build_run_bash_tool(tmp_path, managed_executor=_executor(client, tmp_path)).handler(
            {"command": "touch host"}
        )
    assert answer.error is not None and answer.error.code == "execution_uncertain"
    assert not answer.error.retryable
    assert [item["op"] for item in seen] == ["exec"]
    assert seen[0]["payload"]["operation_id"] in answer.error.message
    assert host_calls == [] and not (tmp_path / "host").exists()


def test_timeout_receipt_is_not_replayed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host_calls = _no_host(monkeypatch)

    def timed_out(req: dict[str, Any]) -> dict[str, Any]:
        reply = result(req)
        reply["receipt"].update(state="TIMED_OUT", exit_code=None, timed_out=True)
        return reply

    with endpoint(tmp_path, timed_out) as (client, seen):
        answer = build_run_bash_tool(tmp_path, managed_executor=_executor(client, tmp_path)).handler(
            {"command": "touch host"}
        )
    assert answer.error is not None and answer.error.code == "command_timeout"
    assert not answer.error.retryable
    assert [item["op"] for item in seen] == ["exec"] and host_calls == []


def test_live_supervisor_refusal_never_runs_host_command(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan_ref(site)
    host_calls = _no_host(monkeypatch)
    with _served(site, tmp_path) as managed:
        grant = managed.open_view(
            access=Access.WRITE, purpose=ViewPurpose.MUTATION, base_revision=managed.grant.revision_id, plan_ref=plan
        )
        assert grant.view_ref is not None
        executor = ManagedBashExecutor(
            managed.client,
            namespace=managed.binding.namespace,
            view=grant.view_ref,
            grant=grant,
            profile=native_profile(),
            input_tree_sha256=SHA,
            plan_sha256=plan.sha256,
            original_revision_id=grant.view_ref.base_revision,
            controller_root=site.source,
        )
        answer = build_run_bash_tool(site.source, managed_executor=executor).handler({"command": "touch host"})
        assert answer.error is not None and answer.error.code == "execution_unavailable"
        assert not answer.error.retryable
        assert host_calls == [] and not (site.source / "host").exists()


def test_missing_explicit_managed_executor_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host_calls = _no_host(monkeypatch)
    answer = build_run_bash_tool(tmp_path, managed_executor=None).handler({"command": "touch host"})
    assert answer.error is not None and answer.error.code == "execution_unavailable"
    assert not answer.error.retryable
    assert host_calls == [] and not (tmp_path / "host").exists()


def test_unexpected_executor_error_is_sanitized_and_never_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BrokenExecutor:
        def run(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("secret-must-not-escape")

        def send_ctrl_c(self, session_id: str) -> str:
            raise AssertionError("not called")

        def close(self, session_id: str) -> None:
            raise AssertionError("not called")

        def list_sessions(self) -> list[str]:
            raise AssertionError("not called")

    host_calls = _no_host(monkeypatch)
    answer = build_run_bash_tool(tmp_path, managed_executor=BrokenExecutor()).handler({"command": "touch host"})
    assert answer.error is not None and answer.error.code == "execution_failed"
    assert not answer.error.retryable and "secret-must-not-escape" not in answer.error.message
    assert host_calls == [] and not (tmp_path / "host").exists()
