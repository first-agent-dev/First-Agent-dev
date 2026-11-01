"""C1/C3: incomplete managed reads must never become whole-file replacements."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import cast

import pytest

from fa.execution.protocol import MAX_TEXT_BYTES
from fa.inner_loop.tools.edit_file import build_edit_file_tool
from fa.inner_loop.tools.workspace_port import PortRead, PortWrite
from tests.test_execution_tool_port import _port, _project_view
from tests.test_execution_views import native_profile
from tests.test_execution_views import source as view_source
from tests.test_execution_workspace import Site, ok
from tests.test_execution_workspace import site as site


def content(size: int) -> bytes:
    prefix = "anchor:ёж\n".encode()
    return prefix + b"x" * (size - len(prefix))


@pytest.mark.parametrize("size,complete", [(MAX_TEXT_BYTES, True), (MAX_TEXT_BYTES + 1, False)])
def test_authority_view_edit_requires_complete_snapshot(site: Site, size: int, complete: bool) -> None:
    original = content(size)
    (site.source / "large.txt").write_bytes(original)
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = _project_view(owner, ids)
        port = _port(owner, grant)
        observed = port.read_file("large.txt")
        assert observed.eof is complete and observed.sha256 == hashlib.sha256(original).hexdigest()
        target = view_source(site, grant) / "large.txt"
        result = build_edit_file_tool(site.source, workspace_io=port).handler(
            {"path": "large.txt", "old_string": "anchor", "new_string": "EDITED"}
        )
        if complete:
            assert result.error is None
            assert target.read_bytes() == original.replace(b"anchor", b"EDITED", 1)
        else:
            assert result.error is not None and result.error.code == "read_failed" and not result.error.retryable
            assert target.read_bytes() == original
        # Canonical source isn't the editable private view.
        assert (site.source / "large.txt").read_bytes() == original


@pytest.mark.parametrize("invalid_eof", [False, None, "true", 1])
def test_unconfirmed_eof_never_reaches_write(tmp_path: Path, invalid_eof: object) -> None:
    class Port:
        cache_dir = None
        writes = 0

        def read_file(self, path: str, *, max_bytes: int = MAX_TEXT_BYTES) -> PortRead:
            return PortRead("anchor", "0" * 64, cast(bool, invalid_eof))

        def write_file(self, path: str, content: str, *, expected_sha256: str | None = None) -> PortWrite:
            self.writes += 1
            return PortWrite("1" * 64, len(content.encode()))

    port = Port()
    result = build_edit_file_tool(tmp_path, workspace_io=port).handler(
        {"path": "f.txt", "old_string": "anchor", "new_string": "changed"}
    )
    assert result.error is not None and result.error.code == "read_failed"
    assert result.error.retryable is False and port.writes == 0


def test_unmanaged_edit_keeps_legacy_behavior(tmp_path: Path) -> None:
    path = tmp_path / "large.txt"
    original = content(MAX_TEXT_BYTES + 1)
    path.write_bytes(original)
    result = build_edit_file_tool(tmp_path).handler(
        {"path": "large.txt", "old_string": "anchor", "new_string": "EDITED"}
    )
    assert result.error is None and path.read_bytes() == original.replace(b"anchor", b"EDITED", 1)
