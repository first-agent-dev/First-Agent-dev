"""C1/C3: loss after a real committed write must not invite an automatic retry."""

from __future__ import annotations

from pathlib import Path
from typing import Any, override

import pytest

from fa.execution.client import ExecutionUncertainError
from fa.execution.service import read_config_file
from fa.execution.tool_port import _code_name
from fa.execution.types import Operation
from fa.inner_loop.tools.edit_file import build_edit_file_tool
from fa.inner_loop.tools.write_file import build_write_file_tool
from tests.test_execution_client_port import _CountingClient, _mutation_port, _plan_ref, _served
from tests.test_execution_composition import _configs, _document
from tests.test_execution_workspace import Site
from tests.test_execution_workspace import site as site


class LoseWriteReply(_CountingClient):
    """Let the actual service commit, then simulate loss of its reply."""

    lose = False

    @override
    def request(self, operation: Operation, **kwargs: Any) -> dict[str, Any]:
        result = super().request(operation, **kwargs)
        if operation is Operation.WRITE_FILE and self.lose:
            raise ExecutionUncertainError("op-lost")
        return result


@pytest.mark.parametrize("tool", ["write", "edit"])
def test_lost_write_reply_is_unknown_and_not_retryable(site: Site, tmp_path: Path, tool: str) -> None:
    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        service_path, _ = _configs(tmp_path, _document(site))
        config = read_config_file(service_path)
        client = LoseWriteReply(config.socket_path, server_uid=next(iter(config.controller_uids)), rpc_timeout_ms=5000)
        port = _mutation_port(managed, plan, client=client)
        if tool == "edit":
            port.write_file("src/module.py", "BEFORE\n")
        client.sent.clear()
        client.lose = True
        if tool == "write":
            result = build_write_file_tool(site.source, workspace_io=port).handler(
                {"path": "src/module.py", "content": "AFTER\n"}
            )
        else:
            result = build_edit_file_tool(site.source, workspace_io=port).handler(
                {"path": "src/module.py", "old_string": "BEFORE", "new_string": "AFTER"}
            )
        assert result.error is not None and result.error.code == "write_failed"
        assert result.error.retryable is False
        assert "unknown" in result.error.message and "do not retry" in result.error.message
        assert client.sent.count(Operation.WRITE_FILE) == 1
        assert port.read_file("src/module.py").content == "AFTER\n"
        assert not (site.source / "src/module.py").exists()


def test_unknown_authority_result_is_not_reported_as_denial() -> None:
    assert _code_name("EXECUTION_UNKNOWN") == "unavailable"
    assert _code_name("UNAUTHORIZED") == "denied"
