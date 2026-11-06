"""C0/C3 strict cell-local helper request parsing, not Docker acceptance."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pytest

from fa.execution import project_tools
from fa.inner_loop.registry import ToolResult


def encoded(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


@pytest.mark.parametrize(
    "raw",
    [
        b'{"tool":"fs_reach","tool":"fs_search","params":{}}',
        b'{"tool":"fs_search","params":{"query":"a","query":"b"}}',
        b'{"tool":"fs_search","params":{"nested":[{"x":1,"x":1}]}}',
        b'{"tool":"fs_search","params":{"query":NaN}}',
        b'{"tool":"fs_search","params":{"query":"\xff"}}',
        b"[]",
    ],
)
def test_untrusted_noncanonical_json_is_refused(raw: bytes) -> None:
    assert project_tools._parse(encoded(raw)) is None


def test_duplicate_request_never_dispatches_and_returns_existing_refusal(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    calls: list[str] = []

    def dispatch(tool: str, params: dict[str, Any], *, root: Path, scratch: Path) -> ToolResult:
        calls.append(tool)
        return ToolResult.ok("must not run")

    monkeypatch.setattr(project_tools, "_dispatch", dispatch)
    request = b'{"tool":"fs_reach","tool":"fs_search","params":{}}'
    assert project_tools.main([encoded(request)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert calls == [] and result["result"] is None and result["error"]["code"] == "project_tool_failed"


def test_exact_decoded_byte_limit_and_valid_utf8_remain_compatible() -> None:
    raw = '{"tool":"fs_search","params":{"query":"ёж"}}'.encode()
    full = raw + b" " * (project_tools._MAX_REQUEST_BYTES - len(raw))
    assert project_tools._parse(encoded(full)) == ("fs_search", {"query": "ёж"})
    assert project_tools._parse(encoded(full + b" ")) is None


def test_noncanonical_base64_and_unknown_tool_are_not_requests() -> None:
    valid = encoded(b'{"tool":"fs_search","params":{}}')
    assert project_tools._parse(valid + "!") is None
    assert project_tools._parse(encoded(b'{"tool":"fs_run_bash","params":{}}')) is None
    assert project_tools._parse(encoded(b'{"tool":"fs_search","params":{},"root":"/host"}')) is None


def test_oversized_base64_rejected_before_decoding(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    original = project_tools.base64.b64decode

    def observe(data: str, *, validate: bool) -> bytes:
        calls.append(data)
        return original(data, validate=validate)

    monkeypatch.setattr(project_tools.base64, "b64decode", observe)
    too_large = "A" * (4 * ((project_tools._MAX_REQUEST_BYTES + 2) // 3) + 4)
    assert project_tools._parse(too_large) is None and calls == []
