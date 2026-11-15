"""C1: immutable reader pins and disposable managed writer views over a real service."""

from __future__ import annotations

import hashlib

import pytest

from fa.inner_loop.tools.workspace_port import WorkspacePortError
from tests.integration._host import ExecutionHostRuntime

pytestmark = pytest.mark.execution_host


def test_old_reader_stays_pinned_while_a_managed_writer_publishes_a_new_revision(
    host_runtime: ExecutionHostRuntime,
) -> None:
    old_bytes = b"VALUE = 'revision zero'\n"
    new_text = "VALUE = 'revision one'\n"
    workspace = host_runtime.register_workspace(files={"src/pinned.py": old_bytes})
    original_revision = workspace.revision_id
    reader = workspace.pin_reader(revision_id=original_revision)
    reader_port = workspace.port(reader)
    old_read = reader_port.read_file("src/pinned.py")
    assert old_read.content.encode("utf-8") == old_bytes
    assert old_read.sha256 == hashlib.sha256(old_bytes).hexdigest()
    assert old_read.eof is True

    workspace.acquire_writer()
    writer_view = workspace.open_write_view(base_revision=original_revision)
    writer_port = workspace.port(writer_view)
    before = writer_port.read_file("src/pinned.py")
    assert before.sha256 == old_read.sha256
    write = writer_port.write_file("src/pinned.py", new_text, expected_sha256=before.sha256)
    assert write.sha256 == hashlib.sha256(new_text.encode("utf-8")).hexdigest()
    assert write.bytes == len(new_text.encode("utf-8"))
    assert writer_port.read_file("src/pinned.py").content == new_text
    assert (workspace.root / "src/pinned.py").read_bytes() == old_bytes

    # A stale compare-and-swap is rejected by the authority; it cannot overwrite
    # the bytes just written into this view or touch the canonical root.
    with pytest.raises(WorkspacePortError) as stale:
        writer_port.write_file("src/pinned.py", "VALUE = 'stale'\n", expected_sha256=before.sha256)
    assert stale.value.code == "stale"
    assert writer_port.read_file("src/pinned.py").content == new_text
    assert (workspace.root / "src/pinned.py").read_bytes() == old_bytes

    publication = workspace.publish(writer_view)
    assert publication.revision_id != original_revision
    assert workspace.revision_id == publication.revision_id
    assert (workspace.root / "src/pinned.py").read_text(encoding="utf-8") == new_text
    assert reader_port.read_file("src/pinned.py").content.encode("utf-8") == old_bytes

    current_reader = workspace.pin_reader(revision_id=publication.revision_id)
    current_read = workspace.port(current_reader).read_file("src/pinned.py")
    assert current_read.content == new_text
    assert current_read.sha256 == write.sha256
    assert current_read.eof is True
    assert host_runtime.assert_owned_cells_terminal() == 0


def test_read_pin_has_no_write_effect_and_recorded_transport_never_contains_capabilities(
    host_runtime: ExecutionHostRuntime,
) -> None:
    workspace = host_runtime.register_workspace(files={"src/readonly.py": b"READ_ONLY = True\n"})
    reader = workspace.pin_reader()
    port = workspace.port(reader)
    event_count = len(host_runtime.events)

    with pytest.raises(WorkspacePortError) as denied:
        port.write_file("src/readonly.py", "READ_ONLY = False\n")

    assert denied.value.code == "denied"
    assert len(host_runtime.events) == event_count, "the port denies before spending an RPC"
    assert (workspace.root / "src/readonly.py").read_bytes() == b"READ_ONLY = True\n"
    assert port.read_file("src/readonly.py").content == "READ_ONLY = True\n"
    raw_trace = str(host_runtime.events)
    assert reader.grant.capability not in raw_trace
    assert workspace.namespace.run_id in raw_trace
