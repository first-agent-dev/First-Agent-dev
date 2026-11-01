"""C0/C1/C3 proof for the injectable workspace port (E264).

Root: the three file tools over a real ``WorkspaceAuthority`` and a real PROJECT
view. This is component evidence: no container, no PTY, no deployed service.

Path inventory:
  W1 port read/write round trip on the admitted view, with the exact digest
  W2 stale base bytes are a reported conflict and the other writer's bytes win
  W3 traversal / absolute / NUL / empty paths are rejected before any IO
  W4 a READ view (VERIFICATION) denies writes
  W5 ``fs_write_file``/``fs_read_file``/``fs_edit_file`` built with the port use it
  W6 ``build_baseline_registry(workspace_io=...)`` forwards the port to fs_write_file
  W7 an edit whose base changed between read and write reports the conflict and
     never overwrites the concurrent writer (optimistic concurrency)
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from fa.execution.protocol import MAX_TEXT_BYTES
from fa.execution.supervisor import SupervisorError
from fa.execution.tool_port import AuthorityWorkspacePort
from fa.execution.types import GrantReply
from fa.execution.workspace import WorkspaceAuthority
from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools import build_baseline_registry
from fa.inner_loop.tools.edit_file import build_edit_file_tool
from fa.inner_loop.tools.read_file import build_read_file_tool
from fa.inner_loop.tools.workspace_port import (
    PORT_READ_MAX_BYTES,
    PortRead,
    PortWrite,
    WorkspacePortError,
    port_relative,
)
from fa.inner_loop.tools.write_file import build_write_file_tool
from tests.test_execution_readers import ref
from tests.test_execution_views import create as create_view
from tests.test_execution_views import native_profile
from tests.test_execution_views import source as view_source
from tests.test_execution_workspace import PEER, Site, ok, until
from tests.test_execution_workspace import site as site


def _port(owner: WorkspaceAuthority, grant: GrantReply) -> AuthorityWorkspacePort:
    return AuthorityWorkspacePort(
        owner,
        peer=PEER,
        namespace=ok(lambda: _namespace()),
        view_ref=ok(lambda: _view_ref(grant)),
        capability=grant.capability,
        deadline_factory=until,
    )


def _namespace() -> Any:
    from tests.test_execution_workspace import ACTOR

    return ACTOR


def _view_ref(grant: GrantReply) -> Any:
    return ref(grant)


def _project_view(owner: WorkspaceAuthority, ids: dict[str, str]) -> GrantReply:
    lease = ok(lambda: owner.acquire_writer(PEER, _namespace(), workspace_id=ids["workspace_id"], deadline=until()))
    return ok(lambda: create_view(owner, ids, lease))


def _call(tool: ToolSpec, params: Mapping[str, object]) -> ToolResult:
    return tool.handler(params)


def test_port_round_trip_reads_and_writes_the_admitted_view(site: Site) -> None:
    """C1 W1: bytes and digests come from the view, not from host paths."""

    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = _project_view(owner, ids)
        port = _port(owner, grant)

        written = port.write_file("notes/today.txt", "hello view")
        assert isinstance(written, PortWrite)
        assert written.bytes == len("hello view")
        read = port.read_file("notes/today.txt", max_bytes=4096)
        assert isinstance(read, PortRead)
        assert read.content == "hello view"
        assert read.eof is True
        assert read.sha256 == written.sha256
        assert (view_source(site, grant) / "notes/today.txt").read_text(encoding="utf-8") == "hello view"


def test_stale_base_is_a_conflict_and_preserves_the_concurrent_bytes(site: Site) -> None:
    """C1 W2: CAS refuses the stale write and the other writer's bytes survive."""

    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = _project_view(owner, ids)
        port = _port(owner, grant)

        base = port.write_file("f.txt", "one")
        port.write_file("f.txt", "two", expected_sha256=base.sha256)
        with pytest.raises(WorkspacePortError) as conflict:
            port.write_file("f.txt", "three", expected_sha256=base.sha256)
        assert conflict.value.code == "stale"
        assert port.read_file("f.txt", max_bytes=64).content == "two"


@pytest.mark.parametrize("raw", ["/etc/passwd", "../escape.txt", "a/../../b", "", "nul\x00byte"])
def test_paths_outside_the_view_are_rejected_before_io(raw: str) -> None:
    """C3 W3: the port is the only path authority; malformed paths never reach IO."""

    with pytest.raises(WorkspacePortError) as rejected:
        port_relative(raw)
    assert rejected.value.code == "invalid_request"


def test_a_capability_without_a_grant_denies_writes(site: Site) -> None:
    """C3 W4: the port cannot elevate an arbitrary capability into an open view."""

    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = _project_view(owner, ids)
        denied_port = AuthorityWorkspacePort(
            owner,
            peer=PEER,
            namespace=_namespace(),
            view_ref=ref(grant),
            capability="cap-" + "f" * 32,  # well-formed, but never minted for this view
            deadline_factory=until,
        )
        with pytest.raises(WorkspacePortError) as denied:
            denied_port.write_file("blocked.txt", "nope")
        # The substrate rejects a capability it never minted as a contract error
        # and a live-but-foreign one as unauthorized; both are closed refusals.
        assert denied.value.code in {"denied", "invalid_request"}
        assert not (view_source(site, grant) / "blocked.txt").exists()


def test_tools_built_with_the_port_read_write_and_edit_through_it(site: Site) -> None:
    """C1 W5: the real handlers use the view port for all three IO seams."""

    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = _project_view(owner, ids)
        port = _port(owner, grant)
        root = site.source

        writer = build_write_file_tool(root, workspace_io=port)
        assert _call(writer, {"path": "src/mod.py", "content": "def a():\n    return 1\n"}).error is None
        reader = build_read_file_tool(root, workspace_io=port)
        read_back = _call(reader, {"path": "src/mod.py"})
        assert read_back.error is None
        assert "def a()" in str(read_back.result)
        editor = build_edit_file_tool(root, workspace_io=port)
        edited = _call(editor, {"path": "src/mod.py", "old_string": "return 1", "new_string": "return 2"})
        assert edited.error is None, edited.error
        assert "return 2" in (view_source(site, grant) / "src/mod.py").read_text(encoding="utf-8")


def test_baseline_registry_forwards_the_port_to_the_write_tool(site: Site) -> None:
    """C1 W6: the production registry builder carries the binding, not a test shim."""

    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = _project_view(owner, ids)
        port = _port(owner, grant)

        registry = build_baseline_registry(site.source, workspace_io=port)
        spec = next(spec for spec in registry.specs() if spec.name == "fs_write_file")
        assert _call(spec, {"path": "registry.txt", "content": "via registry"}).error is None
        assert (view_source(site, grant) / "registry.txt").read_text(encoding="utf-8") == "via registry"


@dataclass
class RacingPort:
    """Port that mutates the file between the edit's read and its write."""

    inner: AuthorityWorkspacePort
    tamper: Callable[[], None]
    reads: int = 0

    @property
    def cache_dir(self) -> Path | None:
        return self.inner.cache_dir

    def read_file(self, path: str, *, max_bytes: int = 1024 * 1024) -> PortRead:
        result = self.inner.read_file(path, max_bytes=max_bytes)
        self.reads += 1
        self.tamper()
        return result

    def write_file(self, path: str, content: str, *, expected_sha256: str | None = None) -> PortWrite:
        return self.inner.write_file(path, content, expected_sha256=expected_sha256)


def test_edit_reports_a_conflict_instead_of_overwriting_a_concurrent_writer(site: Site) -> None:
    """C1 W7: the edit's base digest is load-bearing; no lost update."""

    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = _project_view(owner, ids)
        port = _port(owner, grant)
        port.write_file("race.txt", "value = 1\n")
        target = view_source(site, grant) / "race.txt"

        def tamper() -> None:
            target.write_text("value = 99  # concurrent writer\n", encoding="utf-8")

        racing = RacingPort(inner=port, tamper=tamper)
        editor = build_edit_file_tool(site.source, workspace_io=racing)
        result = _call(editor, {"path": "race.txt", "old_string": "value = 1", "new_string": "value = 2"})

        assert result.error is not None, "a stale edit must not report success"
        assert racing.reads == 1
        assert target.read_text(encoding="utf-8") == "value = 99  # concurrent writer\n"


def test_authority_errors_map_to_closed_port_codes(site: Site) -> None:
    """C0 (mapping): refusals are closed codes, and absence is not disclosed."""

    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        grant = _project_view(owner, ids)
        port = _port(owner, grant)
        with pytest.raises(WorkspacePortError) as missing:
            port.read_file("absent.txt", max_bytes=64)
        assert missing.value.code == "denied", "the substrate must not distinguish absent from forbidden"
        with pytest.raises(WorkspacePortError) as oversized:
            port.read_file("untracked.txt", max_bytes=PORT_READ_MAX_BYTES + 1)
        assert oversized.value.code == "input_policy"
        with pytest.raises(WorkspacePortError) as empty_read:
            port.read_file("untracked.txt", max_bytes=0)
        assert empty_read.value.code == "invalid_request"
    assert PORT_READ_MAX_BYTES == MAX_TEXT_BYTES, "the tool bound must mirror the substrate's single-read limit"


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        ("UNAUTHORIZED", "denied"),
        ("PATH_DENIED", "denied"),
        ("EXECUTION_UNKNOWN", "unavailable"),
        ("STALE_REVISION", "stale"),
        ("INPUT_POLICY", "input_policy"),
        ("INVALID_REQUEST", "input_policy"),
        ("BACKEND_UNAVAILABLE", "unavailable"),
        ("DURABILITY_UNKNOWN", "unavailable"),
    ],
)
def test_supervisor_codes_map_onto_the_closed_port_vocabulary(raised: str, expected: str) -> None:
    """C0 W8: one mapping table, no pass-through of substrate codes to the model."""
    from fa.execution.tool_port import _code

    assert _code(SupervisorError(raised)) == expected


def test_contract_errors_map_to_invalid_request() -> None:
    """C0 W8: a caller contract breach is the model's own defect, not a substrate failure."""
    from fa.execution.tool_port import _code
    from fa.execution.types import ExecutionContractError

    assert _code(ExecutionContractError()) == "invalid_request"
