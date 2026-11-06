"""Legacy host discovery, managed refusal, explicit read outcomes, no host Git.

C1/C3 local positive discovery uses real host trees and indexes, not granted
views. Managed cell-local parity is not established by these tests; until its
supplier is connected the port-bound registry must refuse host indexing.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import override

import pytest

from fa.inner_loop.artifacts import ArtifactStore
from fa.inner_loop.context import reset_current_session, set_current_session
from fa.inner_loop.profiles import build_registry_for_role
from fa.inner_loop.state import EventLog, SessionState
from fa.inner_loop.tools import build_baseline_registry
from fa.inner_loop.tools.fs_reach import build_fs_reach_tool
from fa.inner_loop.tools.fs_search import build_fs_search_tool
from fa.inner_loop.tools.read_file import build_read_file_tool
from fa.inner_loop.tools.workspace_port import (
    PORT_READ_MAX_BYTES,
    PortRead,
    PortWrite,
    WorkspacePortError,
    index_db,
)

_HOST_GIT_TOOLS = ("fs_checkpoint", "fs_undo", "fs_diff")


class _CachePort:
    """Minimal port: a private cache home and no IO the tests rely on."""

    def __init__(self, cache_dir: Path | None) -> None:
        self.cache_dir = cache_dir
        self.reads: list[str] = []

    def read_file(self, path: str, *, offset_bytes: int = 0, max_bytes: int = PORT_READ_MAX_BYTES) -> PortRead:
        self.reads.append(path)
        raise AssertionError(f"unexpected read of {path!r}")

    def write_file(self, path: str, content: str, *, expected_sha256: str | None = None) -> PortWrite:
        raise AssertionError("unexpected write")


class _RefusingPort(_CachePort):
    """Every read is refused with one closed code."""

    def __init__(self, cache_dir: Path | None, code: str) -> None:
        super().__init__(cache_dir)
        self.code = code

    @override
    def read_file(self, path: str, *, offset_bytes: int = 0, max_bytes: int = PORT_READ_MAX_BYTES) -> PortRead:
        self.reads.append(path)
        raise WorkspacePortError(self.code)


class _EofShortPort(_CachePort):
    def __init__(self, cache_dir: Path | None) -> None:
        super().__init__(cache_dir)

    @override
    def read_file(self, path: str, *, offset_bytes: int = 0, max_bytes: int = PORT_READ_MAX_BYTES) -> PortRead:
        self.reads.append(path)
        return PortRead(content="x" * 10, sha256="0" * 64, eof=False)


class _ExplodingPort(_CachePort):
    """Any IO at all is a bug: used where the tool must not touch the view."""

    def __init__(self) -> None:
        super().__init__(None)

    @override
    def read_file(self, path: str, *, offset_bytes: int = 0, max_bytes: int = PORT_READ_MAX_BYTES) -> PortRead:
        raise AssertionError("the port must not be consulted on this path")

    @override
    def write_file(self, path: str, content: str, *, expected_sha256: str | None = None) -> PortWrite:
        raise AssertionError("the port must not be consulted on this path")


def _tree(tmp_path: Path, name: str, files: dict[str, str]) -> Path:
    root = tmp_path / name
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    return root


# ---------------------------------------------------------------------------
# C1 — index placement for fs_search
# ---------------------------------------------------------------------------


def test_legacy_search_indexes_at_the_configured_location(tmp_path: Path) -> None:
    """Legacy positive control uses the host root and explicitly configured database."""
    root = _tree(tmp_path, "view", {"pkg/alpha.py": "def alpha():\n    return 1\n"})
    cache = tmp_path / "cell-cache"
    tool = build_fs_search_tool(cache / "search.db", root)

    result = tool.handler({"query": "alpha", "output_mode": "files"})

    assert result.error is None, result.error
    assert "pkg/alpha.py" in json.dumps(result.result)
    assert not (root / ".fa").exists(), "a managed tool wrote an index into the view"
    assert (cache / "search.db").exists()


def test_a_managed_search_without_a_cache_home_refuses_instead_of_indexing_the_view(tmp_path: Path) -> None:
    """producer-kill-check: treat a missing cache home as 'just index in place'."""
    root = _tree(tmp_path, "view", {"pkg/alpha.py": "def alpha():\n    return 1\n"})
    tool = build_fs_search_tool(root / ".fa" / "fts.db", root, workspace_io=_CachePort(None))

    result = tool.handler({"query": "alpha", "output_mode": "files"})

    assert result.error is not None
    assert result.error.code == "search_failed"
    assert result.error.retryable is False
    assert "index" in result.error.message.lower()
    assert not (root / ".fa").exists()


def test_a_cache_home_inside_the_view_is_refused(tmp_path: Path) -> None:
    """Managed discovery refuses even when a purported cache sits inside the root."""
    root = _tree(tmp_path, "view", {"pkg/alpha.py": "def alpha():\n    return 1\n"})
    tool = build_fs_search_tool(root / ".fa" / "fts.db", root, workspace_io=_CachePort(root / ".fa"))

    result = tool.handler({"query": "alpha", "output_mode": "files"})

    assert result.error is not None
    assert result.error.code == "search_failed"
    assert not (root / ".fa").exists(), "the containment check let the index into the view"


# ---------------------------------------------------------------------------
# C1 — index placement for fs_reach
# ---------------------------------------------------------------------------


def test_legacy_reach_indexes_at_the_configured_location(tmp_path: Path) -> None:
    """Legacy positive control retains the real structural-index behavior."""
    root = _tree(
        tmp_path,
        "view",
        {
            # One file: v1 resolution is in-file only, so the edge must be local.
            "pkg/chain.py": "def caller():\n    return alpha()\n\n\ndef alpha():\n    return 1\n",
        },
    )
    cache = tmp_path / "cell-cache"
    tool = build_fs_reach_tool(root, scratch_db=cache / "structural.db")

    result = tool.handler({"symbol": "alpha", "direction": "up"})

    assert result.error is None, result.error
    assert result.result is not None
    assert result.result["status"] == "ok"
    callers = [row["qualname"] for row in result.result["callers"]]
    assert callers == ["caller"], callers
    assert not (root / ".fa").exists(), "fs_reach indexed the view"
    assert (cache / "structural.db").exists()


def test_a_managed_reach_without_a_cache_home_refuses(tmp_path: Path) -> None:
    """producer-kill-check: fall back to root/.fa when cache_dir is None."""
    root = _tree(tmp_path, "view", {"pkg/alpha.py": "def alpha():\n    return 1\n"})
    tool = build_fs_reach_tool(root, workspace_io=_CachePort(None))

    result = tool.handler({"symbol": "alpha"})

    assert result.error is not None
    assert result.error.code == "reach_failed"
    assert result.error.retryable is False
    assert not (root / ".fa").exists()


# ---------------------------------------------------------------------------
# C3 — independent legacy host roots and indexes
# ---------------------------------------------------------------------------


def test_separate_legacy_roots_use_separate_indexes(tmp_path: Path) -> None:
    """Local host roots are not authority-granted active/pinned views."""
    pinned = _tree(tmp_path, "pinned", {"pkg/alpha.py": "def alpha():\n    return 1\n"})
    active = _tree(
        tmp_path,
        "active",
        {
            "pkg/alpha.py": "def alpha():\n    return 1\n",
            "pkg/beta.py": "def beta():\n    return 2\n",
        },
    )

    pinned_tool = build_fs_search_tool(tmp_path / "c1" / "search.db", pinned)
    active_tool = build_fs_search_tool(tmp_path / "c2" / "search.db", active)

    active_hit = active_tool.handler({"query": "beta", "output_mode": "files"})
    pinned_hit = pinned_tool.handler({"query": "beta", "output_mode": "files"})

    assert active_hit.error is None, active_hit.error
    assert pinned_hit.error is None, pinned_hit.error
    assert "pkg/beta.py" in json.dumps(active_hit.result)
    assert "pkg/beta.py" not in json.dumps(pinned_hit.result)
    assert not (pinned / ".fa").exists()
    assert not (active / ".fa").exists()


# ---------------------------------------------------------------------------
# C1 — explicit read outcomes through the port
# ---------------------------------------------------------------------------


def test_a_pdf_read_is_refused_by_name_before_any_io(tmp_path: Path) -> None:
    """producer-kill-check: restore the unconditional _read_file_text host path."""
    root = _tree(tmp_path, "view", {"doc.pdf": "%PDF-1.4 not really\n"})
    port = _ExplodingPort()
    tool = build_read_file_tool(root, workspace_io=port)

    result = tool.handler({"path": "doc.pdf"})

    assert result.error is not None
    assert result.error.code == "read_failed"
    assert result.error.retryable is False
    assert "PDF" in result.error.message
    assert "managed" in result.error.message.lower() or "view" in result.error.message.lower()


def test_binary_content_is_named_rather_than_a_generic_refusal(tmp_path: Path) -> None:
    """producer-kill-check: map input_policy to the generic 'refused the read' message."""
    root = _tree(tmp_path, "view", {"blob.bin": "binary-ish\n"})
    port = _RefusingPort(None, "input_policy")
    tool = build_read_file_tool(root, workspace_io=port)

    result = tool.handler({"path": "blob.bin"})

    assert result.error is not None
    assert result.error.code == "read_failed"
    assert result.error.retryable is False
    assert "binary" in result.error.message.lower()
    assert port.reads == ["blob.bin"]


def test_an_oversized_managed_read_names_the_bound(tmp_path: Path) -> None:
    """producer-kill-check: treat a non-eof read as a complete file."""
    root = _tree(tmp_path, "view", {"big.txt": "x\n"})
    tool = build_read_file_tool(root, workspace_io=_EofShortPort(None))

    result = tool.handler({"path": "big.txt"})

    assert result.error is not None
    assert result.error.code == "read_failed"
    assert str(PORT_READ_MAX_BYTES) in result.error.message


# ---------------------------------------------------------------------------
# C3 — artifacts keep their controller path while a port is bound
# ---------------------------------------------------------------------------


def test_artifacts_still_resolve_through_the_controller_store(tmp_path: Path) -> None:
    """Kills routing artifacts through the workspace port."""
    root = _tree(tmp_path, "view", {"pkg/alpha.py": "def alpha():\n    return 1\n"})
    tool = build_read_file_tool(root, workspace_io=_ExplodingPort())
    run = "run-7"
    log = EventLog(tmp_path / run / "events.jsonl")
    state = SessionState(workspace_root=root, run_id=run, log=log)
    state.artifact_store = ArtifactStore(tmp_path / run / "fa-artifacts")
    artifact_id = state.artifact_store.put("alpha\nbeta\n")

    token = set_current_session(state)
    try:
        result = tool.handler({"artifact_id": artifact_id})
    finally:
        reset_current_session(token)

    assert result.error is None, result.error
    assert result.result is not None
    assert result.result["content"] == "alpha\nbeta\n"


# ---------------------------------------------------------------------------
# C3 — the managed composition ships no host-Git tool
# ---------------------------------------------------------------------------


def test_a_managed_registry_ships_no_host_git_tools(tmp_path: Path) -> None:
    """producer-kill-check: keep include_pair=True under a bound port."""
    cache = tmp_path / "cell-cache"
    managed = build_baseline_registry(tmp_path, workspace_io=_CachePort(cache))
    host = build_baseline_registry(tmp_path)

    assert any(name in host.names() for name in _HOST_GIT_TOOLS), host.names()
    for name in _HOST_GIT_TOOLS:
        assert name not in managed.names(), f"{name} can run host git under a managed view"
    assert "fs_read_file" in managed.names()


def test_a_managed_registry_still_registers_search_and_reach(tmp_path: Path) -> None:
    """The omission must be limited to host-Git tools, not to the whole extras set."""
    managed = build_registry_for_role("implementer", tmp_path, workspace_io=_CachePort(tmp_path / "cache"))

    assert "fs_search" in managed.names()
    assert "fs_reach" in managed.names()


@pytest.mark.parametrize(
    ("name", "params", "filename"),
    [
        ("fs_search", {"query": "alpha", "output_mode": "files"}, "search.db"),
        ("fs_reach", {"symbol": "alpha"}, "structural.db"),
    ],
)
def test_a_managed_registry_refuses_host_indexing(
    tmp_path: Path, name: str, params: dict[str, object], filename: str
) -> None:
    """Dropping the port at the composition root would expose host content."""
    root = _tree(tmp_path, "view", {"pkg/alpha.py": "def alpha():\n    return 1\n"})
    cache = tmp_path / "cell-cache"
    registry = build_baseline_registry(root, workspace_io=_CachePort(cache))
    tool = next(spec for spec in registry.specs() if spec.name == name)

    result = tool.handler(params)

    assert result.error is not None and result.error.code == (
        "search_failed" if name == "fs_search" else "reach_failed"
    )
    assert result.error.retryable is False
    assert not (root / ".fa").exists()
    assert not (cache / filename).exists()


@pytest.mark.parametrize("name", ["fs_search", "fs_reach"])
def test_managed_search_tools_never_mention_host_paths(tmp_path: Path, name: str) -> None:
    """A managed tool result must not leak the host view path to the model."""
    root = _tree(tmp_path, "view", {"pkg/alpha.py": "def alpha():\n    return 1\n"})
    cache = tmp_path / "cell-cache"
    registry = build_registry_for_role("implementer", root, workspace_io=_CachePort(cache))
    tool = next(spec for spec in registry.specs() if spec.name == name)

    result = tool.handler({"query": "alpha"} if name == "fs_search" else {"symbol": "alpha"})

    assert result.error is not None
    assert str(root) not in result.error.message
    assert result.result is None


# ---------------------------------------------------------------------------
# C0 — the placement helper itself
# ---------------------------------------------------------------------------


def test_index_db_keeps_the_host_location_without_a_port(tmp_path: Path) -> None:
    """producer-kill-check: make index_db ignore its ``port is None`` case."""
    fallback = tmp_path / "ws" / ".fa" / "fts.db"

    assert index_db(None, tmp_path / "ws", "search.db", fallback) == fallback


def test_index_db_maps_a_port_to_its_cache_home(tmp_path: Path) -> None:
    """One rule for both tools: cache home, outside the searched tree."""
    assert index_db(_CachePort(tmp_path / "cache"), tmp_path / "ws", "structural.db", Path("x")) == (
        tmp_path / "cache" / "structural.db"
    )


@pytest.mark.parametrize("cache", [None, "inside"])
def test_index_db_refuses_an_unusable_cache_home(tmp_path: Path, cache: str | None) -> None:
    """producer-kill-check: return the fallback instead of refusing."""
    root = tmp_path / "ws"
    home = None if cache is None else root / ".fa"
    with pytest.raises(WorkspacePortError) as err:
        index_db(_CachePort(home), root, "search.db", root / ".fa" / "fts.db")
    assert err.value.code == "unavailable"


# ---------------------------------------------------------------------------
# C3 — a managed search runs no host-git subprocess
# ---------------------------------------------------------------------------


def test_a_managed_search_runs_no_host_git_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Managed refusal prevents host Git even when subprocess failures degrade."""
    invocations: list[list[str]] = []

    def _record(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        invocations.append(list(argv))
        return subprocess.CompletedProcess(list(argv), 0, stdout="")

    monkeypatch.setattr("fa.memory._safe_walk.subprocess.run", _record)
    root = _tree(tmp_path, "view", {"pkg/alpha.py": "def alpha():\n    return 1\n"})
    tool = build_fs_search_tool(root / ".fa" / "fts.db", root, workspace_io=_CachePort(tmp_path / "cache"))

    result = tool.handler({"query": "alpha", "output_mode": "files"})

    assert result.error is not None and result.error.code == "search_failed"
    assert result.error.retryable is False
    assert invocations == [], f"a managed search shelled out: {invocations}"
