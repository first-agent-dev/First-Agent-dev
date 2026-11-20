"""Managed Blackboard mutation stamps must come only from complete view reads."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from fa.inner_loop.tools.mutation_guard import (
    BLACKBOARD_UNAVAILABLE,
    check_mutation_allowed,
    managed_version_dependencies,
)
from fa.inner_loop.tools.workspace_port import (
    PORT_READ_MAX_BYTES,
    PortProjectArtifactListing,
    PortProjectNames,
    PortRead,
    PortWrite,
    WorkspacePortError,
)

REVISION = "rev-" + "a" * 32
_CONTENT = "# Workspace map\n"
_SHA256 = hashlib.sha256(_CONTENT.encode("utf-8")).hexdigest()


class _Port:
    base_revision_id = REVISION

    def __init__(self, result: Any) -> None:
        self.result = result

    @property
    def cache_dir(self) -> Path | None:
        raise AssertionError("metadata lookup must not access a cache")

    def read_file(self, path: str, *, offset_bytes: int = 0, max_bytes: int = PORT_READ_MAX_BYTES) -> Any:
        assert path == "knowledge/llms.txt" and offset_bytes == 0 and max_bytes > 0
        if isinstance(self.result, Exception):
            raise self.result
        return self.result  # Intentionally includes malformed remote responses.

    def list_project_names(self) -> PortProjectNames:
        raise AssertionError("metadata lookup must not list project names")

    def list_project_artifacts(self, project_slug: str) -> PortProjectArtifactListing:
        raise AssertionError("metadata lookup must not list artifacts")

    def write_file(self, path: str, content: str, *, expected_sha256: str | None = None) -> PortWrite:
        raise AssertionError("metadata lookup must not write")


class _Blackboard:
    def __init__(self, root: Path, conflicts: list[Any] | None = None) -> None:
        self.root = root
        self.conflicts = conflicts or []
        self.entries: list[Any] = []

    def detect_conflict(self, entry: Any) -> list[Any]:
        self.entries.append(entry)
        return self.conflicts


def _session() -> Any:
    return SimpleNamespace(feature_flags=SimpleNamespace(blackboard_enabled=True))


@pytest.mark.parametrize(
    "port",
    [
        _Port(WorkspacePortError("denied")),
        _Port(PortRead(content=_CONTENT, sha256=_SHA256, eof=False)),
        _Port(PortRead(content=_CONTENT, sha256="bad-digest", eof=True)),
        _Port(PortRead(content="different bytes", sha256=_SHA256, eof=True)),
        _Port(object()),
    ],
)
def test_required_managed_metadata_failure_denies_blackboard_guarded_write(tmp_path: Path, port: _Port) -> None:
    versions = managed_version_dependencies(port)
    board = _Blackboard(tmp_path)

    denial = check_mutation_allowed(
        board,
        read_set=[],
        write_set=["src/new.py"],
        root=tmp_path,
        managed=True,
        session=_session(),
        managed_versions=versions,
    )

    assert versions is None
    assert denial is not None and denial.error is not None
    assert denial.error.code == BLACKBOARD_UNAVAILABLE
    assert board.entries == []


def test_managed_metadata_read_refusal_is_not_replaced_by_host_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("managed metadata used host filesystem or Git")

    monkeypatch.setattr("fa.inner_loop.tools.mutation_guard._base_commit", forbidden)
    monkeypatch.setattr("fa.inner_loop.tools.mutation_guard._file_hash", forbidden)
    port = _Port(WorkspacePortError("denied"))
    board = _Blackboard(tmp_path)

    versions = managed_version_dependencies(port)
    denial = check_mutation_allowed(
        board,
        read_set=[],
        write_set=["src/new.py"],
        root=tmp_path,
        managed=True,
        session=_session(),
        managed_versions=versions,
    )

    assert versions is None
    assert denial is not None and denial.error is not None
    assert denial.error.code == BLACKBOARD_UNAVAILABLE
    assert board.entries == []


def test_complete_managed_metadata_keeps_overlap_check_active(tmp_path: Path) -> None:
    port = _Port(PortRead(content=_CONTENT, sha256=_SHA256, eof=True))
    board = _Blackboard(tmp_path, conflicts=[SimpleNamespace(reason="overlap", conflicting_entry_id="prior")])

    denial = check_mutation_allowed(
        board,
        read_set=[],
        write_set=["src/new.py"],
        root=tmp_path,
        managed=True,
        session=_session(),
        managed_versions=managed_version_dependencies(port),
    )

    assert denial is not None and denial.error is not None
    assert denial.error.code == "conflict_detected"
    assert len(board.entries) == 1
    assert board.entries[0].assumptions == [f"base_revision {REVISION}"]
