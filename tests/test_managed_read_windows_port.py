"""Q97: bounded byte-window port supplier; not model line-window or host proof."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from fa.execution.protocol import MAX_TEXT_BYTES
from fa.execution.tool_port import ClientWorkspacePort
from fa.execution.types import Access, Operation, ViewPurpose
from fa.inner_loop.tools.workspace_port import WorkspacePortError
from tests.test_execution_client_port import _plan_ref, _served, _socket_client
from tests.test_execution_tool_port import _port, _project_view
from tests.test_execution_views import native_profile
from tests.test_execution_views import source as view_source
from tests.test_execution_workspace import Site, ok
from tests.test_execution_workspace import site as site


def test_client_read_windows_bind_view_and_return_whole_file_hash(site: Site, tmp_path: Path) -> None:
    """C1: real UDS, existing large source, a changed private view and exact windows."""
    original = b"canonical"
    (site.source / "large.txt").write_bytes(original)
    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        grant = managed.open_view(
            access=Access.WRITE, purpose=ViewPurpose.PROJECT, base_revision=managed.grant.revision_id, plan_ref=plan
        )
        assert grant.view_ref is not None
        private = view_source(site, grant) / "large.txt"
        content = b"a" * (MAX_TEXT_BYTES - 3) + "🐈".encode() + b"end"
        private.write_bytes(content)
        client = _socket_client(site, tmp_path)
        port = ClientWorkspacePort(client, namespace=managed.binding.namespace, view=grant.view_ref, grant=grant)
        first = port.read_file("large.txt", max_bytes=MAX_TEXT_BYTES - 3)
        second = port.read_file("large.txt", offset_bytes=MAX_TEXT_BYTES - 3, max_bytes=7)
        assert first.content.encode() + second.content.encode() == content
        assert first.sha256 == second.sha256 == hashlib.sha256(content).hexdigest()
        assert first.eof is False and second.eof is True
        assert client.sent == [Operation.READ_FILE, Operation.READ_FILE]
        assert (site.source / "large.txt").read_bytes() == original
        with pytest.raises(WorkspacePortError) as split:
            port.read_file("large.txt", offset_bytes=MAX_TEXT_BYTES - 2, max_bytes=3)
        assert split.value.code == "input_policy"
        past_end = port.read_file("large.txt", offset_bytes=len(content) + 1, max_bytes=1)
        assert past_end.content == "" and past_end.eof is True and past_end.sha256 == first.sha256


def test_authority_read_offsets_and_snapshots(site: Site) -> None:
    """C1: in-process transport passes offsets through and exposes a changed digest."""
    (site.source / "f.txt").write_text("ab🐈xyz", encoding="utf-8")
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = _project_view(owner, ids)
        port = _port(owner, grant)
        first = port.read_file("f.txt", max_bytes=2)
        second = port.read_file("f.txt", offset_bytes=2, max_bytes=4)
        assert first.content == "ab" and second.content == "🐈"
        assert first.sha256 == second.sha256 and not first.eof and not second.eof
        port.write_file("f.txt", "ab🐈changed", expected_sha256=first.sha256)
        changed = port.read_file("f.txt", offset_bytes=6, max_bytes=7)
        assert changed.content == "changed" and changed.eof is True and changed.sha256 != first.sha256
        assert (site.source / "f.txt").read_text(encoding="utf-8") == "ab🐈xyz"
        with pytest.raises(WorkspacePortError) as split:
            port.read_file("f.txt", offset_bytes=3, max_bytes=1)
        assert split.value.code == "input_policy"


@pytest.mark.parametrize("offset", [-1, True, False, 1.5, "1", None])
def test_invalid_offsets_are_refused_before_client_send(site: Site, tmp_path: Path, offset: Any) -> None:
    """C3: no request/authorization side effect for invalid offsets."""
    plan = _plan_ref(site)
    with _served(site, tmp_path) as managed:
        grant = managed.open_view(
            access=Access.WRITE, purpose=ViewPurpose.PROJECT, base_revision=managed.grant.revision_id, plan_ref=plan
        )
        assert grant.view_ref is not None
        client = _socket_client(site, tmp_path)
        port = ClientWorkspacePort(client, namespace=managed.binding.namespace, view=grant.view_ref, grant=grant)
        with pytest.raises(WorkspacePortError) as rejected:
            port.read_file("f.txt", offset_bytes=offset)
        assert rejected.value.code == "invalid_request" and client.sent == []


@pytest.mark.parametrize("offset", [-1, True, False, 1.5, "1", None])
def test_invalid_offsets_are_refused_before_authority_read(
    site: Site, monkeypatch: pytest.MonkeyPatch, offset: Any
) -> None:
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = _project_view(owner, ids)
        authority_port = _port(owner, grant)

        def forbidden(*args: Any, **kwargs: Any) -> None:
            pytest.fail("invalid offset reached authority")

        monkeypatch.setattr(owner, "read_file", forbidden)
        with pytest.raises(WorkspacePortError) as rejected:
            authority_port.read_file("f.txt", offset_bytes=offset)
        assert rejected.value.code == "invalid_request"
