"""C0-C3 for the isolated discovery supplier; no Docker claim."""

from __future__ import annotations

import base64
import json
import threading
from pathlib import Path
from typing import Any

import pytest

from fa.execution import project_tools
from fa.inner_loop.registry import ToolResult
from fa.inner_loop.tools.fs_reach import build_fs_reach_tool
from fa.inner_loop.tools.fs_search import build_fs_search_tool
from fa.memory.search_index import SearchIndex, _refresh_state
from fa.memory.structural_index import StructuralIndex


def _encoded(value: Any) -> str:
    return base64.b64encode(json.dumps(value).encode()).decode()


def _tree(tmp_path: Path, name: str, content: str) -> tuple[Path, Path]:
    root = tmp_path / name
    root.mkdir()
    (root / "chain.py").write_text(content)
    scratch = tmp_path / f"{name}-scratch"
    scratch.mkdir()
    return root, scratch


def test_real_search_and_reach_stay_on_each_distinct_view(tmp_path: Path) -> None:
    active, active_cache = _tree(
        tmp_path, "active", "def alpha():\n    return 1\n\ndef caller():\n    return alpha()\n"
    )
    pinned, pinned_cache = _tree(tmp_path, "pinned", "def alpha():\n    return 1\n")
    (active / "activeonly.py").write_text("# activeonly\n")
    search = {"query": "activeonly", "output_mode": "files"}
    for root, scratch, found in ((active, active_cache, True), (pinned, pinned_cache, False)):
        result = project_tools._dispatch("fs_search", search, root=root, scratch=scratch)
        assert result.error is None, result.error
        assert ("activeonly.py" in json.dumps(result.result)) is found
        reach = project_tools._dispatch("fs_reach", {"symbol": "alpha", "direction": "up"}, root=root, scratch=scratch)
        assert reach.error is None, reach.error
        assert reach.result is not None
        assert [row["qualname"] for row in reach.result["callers"]] == (["caller"] if found else [])
        assert list(scratch.iterdir()) == []
        assert not (root / ".fa").exists()


def test_existing_reach_default_still_uses_legacy_db(tmp_path: Path) -> None:
    root, _scratch = _tree(tmp_path, "legacy", "def alpha():\n    return 1\n")
    result = build_fs_reach_tool(root).handler({"symbol": "alpha"})
    assert result.error is None
    assert (root / ".fa" / "structural.db").is_file()


@pytest.mark.parametrize("kind", ["same", "inside", "ancestor", "alias", "missing"])
def test_invalid_scratch_fails_closed_without_index(tmp_path: Path, kind: str) -> None:
    root, scratch = _tree(tmp_path, "view", "def alpha():\n    return 1\n")
    if kind == "same":
        scratch = root
    elif kind == "inside":
        scratch = root / "cache"
        scratch.mkdir()
    elif kind == "ancestor":
        scratch = tmp_path
    elif kind == "alias":
        scratch = tmp_path / "link"
        scratch.symlink_to(root, target_is_directory=True)
    else:
        scratch = tmp_path / "missing"
    result = project_tools._dispatch("fs_search", {"query": "alpha"}, root=root, scratch=scratch)
    assert result.error is not None and result.error.code == "project_tool_failed"
    assert not (root / ".fa").exists() and not (root / "search.db").exists()


def test_unknown_tool_and_invalid_schema_are_not_executed(tmp_path: Path) -> None:
    root, scratch = _tree(tmp_path, "view", "def alpha():\n    return 1\n")
    bad_tool = project_tools._dispatch("fs_run_bash", {"command": "touch host"}, root=root, scratch=scratch)
    assert bad_tool.error is not None and bad_tool.error.code == "project_tool_failed"
    bad_params = project_tools._dispatch("fs_search", {"query": ["alpha"]}, root=root, scratch=scratch)
    assert bad_params.error is not None and bad_params.error.code == "invalid_params"
    extra = project_tools._dispatch("fs_search", {"query": "alpha", "unexpected": True}, root=root, scratch=scratch)
    assert extra.error is not None and extra.error.code == "invalid_params"
    assert not (root / "host").exists() and list(scratch.iterdir()) == []


@pytest.mark.parametrize(
    "value",
    [
        {"tool": "fs_search", "params": {}, "root": "/host"},
        {"tool": "fs_search", "params": {}, "capability": "secret"},
        {"tool": "fs_search", "params": []},
        {"tool": "fs_run_bash", "params": {}},
        {"tool": "fs_search"},
    ],
)
def test_parse_refuses_unknown_authority_or_bad_shape(value: Any) -> None:
    assert project_tools._parse(_encoded(value)) is None


def test_parse_rejects_bad_encoding_oversize_and_nonfinite_json() -> None:
    assert project_tools._parse("not base64!") is None
    assert project_tools._parse(_encoded({"tool": "fs_search", "params": {"query": "x" * 65536}})) is None
    assert project_tools._parse(base64.b64encode(b'{"tool":"fs_search","params":{"limit":NaN}}').decode()) is None
    assert project_tools._parse(_encoded({"tool": "fs_search", "params": {"query": "ok"}})) == (
        "fs_search",
        {"query": "ok"},
    )


def test_cli_uses_fixed_cell_mounts_and_never_input_paths(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    seen: list[tuple[Any, ...]] = []

    def dispatch(tool: str, params: dict[str, Any], *, root: Path, scratch: Path) -> ToolResult:
        seen.append((tool, params, root, scratch))
        return ToolResult.ok("ok", result={"value": 1})

    monkeypatch.setattr(project_tools, "_dispatch", dispatch)
    code = project_tools.main([_encoded({"tool": "fs_search", "params": {"path": "src"}})])
    assert code == 0
    assert seen == [("fs_search", {"path": "src"}, Path("/workspace"), Path("/scratch"))]
    assert json.loads(capsys.readouterr().out) == {
        "summary": "ok",
        "result": {"value": 1},
        "error": None,
        "artifacts": [],
    }
    assert project_tools.main([_encoded({"tool": "fs_search", "params": {}, "root": "/host"})]) == 0
    rejected = json.loads(capsys.readouterr().out)
    assert rejected["result"] is None and rejected["error"]["code"] == "project_tool_failed"
    assert len(seen) == 1


def test_envelope_never_returns_partial_oversize_nonjson_or_artifacts() -> None:
    cases = [
        ToolResult.ok("large", result={"value": "x" * 100000}),
        ToolResult.ok("nan", result={"value": float("nan")}),
        ToolResult.ok("artifact", result={}, artifacts=("secret",)),
    ]
    for case in cases:
        data = project_tools._envelope(case)
        result = json.loads(data)
        assert len(data.encode()) <= project_tools._MAX_ENVELOPE_BYTES
        assert result["result"] is None and result["error"]["code"] == "project_tool_failed"
        assert result["artifacts"] == []
    success = json.loads(project_tools._envelope(ToolResult.ok("ok", result={"text": "внутри"})))
    assert success["error"] is None and success["result"] == {"text": "внутри"}


def test_ascii_envelope_roundtrips_combining_marks_emoji_and_escaped_text() -> None:
    value = {"text": "a" + "\u0301" * 1000 + ' ё😀\n\\"'}
    encoded = project_tools._envelope(ToolResult.ok("ok", result=value))
    assert encoded.isascii()
    assert json.loads(encoded)["result"] == value


def test_unicode_outline_ascii_expansion_refuses_not_partial_success(tmp_path: Path) -> None:
    root, scratch = _tree(tmp_path, "unicode", "def alpha():\n    return 1\n")
    (root / "giant.md").write_text("# " + "я" * 20000 + "\n", encoding="utf-8")
    result = project_tools._dispatch(
        "fs_search", {"path": "giant.md", "output_mode": "outline"}, root=root, scratch=scratch
    )
    assert result.error is None and result.result is not None and result.result["truncated"] is False
    decoded = json.loads(project_tools._envelope(result))
    assert decoded["result"] is None and decoded["error"]["code"] == "project_tool_failed"


@pytest.mark.xfail(strict=True, reason="Q106: existing 60 KiB envelope cannot transport the legacy outline")
def test_q106_large_outline_parity_remains_open(tmp_path: Path) -> None:
    root, scratch = _tree(tmp_path, "outline-large", "def alpha():\n    return 1\n")
    (root / "giant.md").write_text("# " + "я" * 40000 + "\n", encoding="utf-8")
    result = project_tools._dispatch(
        "fs_search", {"path": "giant.md", "output_mode": "outline"}, root=root, scratch=scratch
    )
    assert result.error is None and result.result is not None and result.result["truncated"] is False
    assert json.loads(project_tools._envelope(result))["result"] == result.result


@pytest.mark.xfail(strict=True, reason="Q106: existing 60 KiB envelope cannot transport the legacy reach result")
def test_q106_large_reach_parity_remains_open(tmp_path: Path) -> None:
    root, scratch = _tree(tmp_path, "reach-large", "def alpha():\n    return 1\n")
    (root / "longname.py").write_text("def " + "a" * 80000 + "needle():\n    pass\n", encoding="utf-8")
    result = project_tools._dispatch("fs_reach", {"symbol": "needle", "direction": "up"}, root=root, scratch=scratch)
    assert result.error is None and result.result is not None and result.result["status"] == "ok"
    assert json.loads(project_tools._envelope(result))["result"] == result.result


def test_invalid_unicode_is_an_explicit_refusal() -> None:
    encoded = project_tools._envelope(ToolResult.ok("invalid", result={"text": "\ud800"}))
    assert json.loads(encoded)["error"]["code"] == "project_tool_failed"


@pytest.mark.parametrize(
    ("tool", "params", "db"),
    [("fs_search", {"query": "alpha"}, "search.db"), ("fs_reach", {"symbol": "alpha"}, "structural.db")],
)
def test_cell_scratch_index_symlink_cannot_mutate_source(
    tmp_path: Path, tool: str, params: dict[str, Any], db: str
) -> None:
    root, scratch = _tree(tmp_path, "view", "def alpha():\n    return 1\n")
    (scratch / db).symlink_to(root / "victim.db")
    result = project_tools._dispatch(tool, params, root=root, scratch=scratch)
    assert result.error is None, result.error
    assert not (root / "victim.db").exists()
    assert (scratch / db).is_symlink()


@pytest.mark.parametrize("tool", ["fs_search", "fs_reach"])
def test_memory_results_match_existing_disk_tool_and_rebuild_cleanly(tmp_path: Path, tool: str) -> None:
    root, scratch = _tree(tmp_path, "view", "def alpha():\n    return 1\n\ndef caller():\n    return alpha()\n")
    params = (
        {"query": "alpha", "output_mode": "matches"} if tool == "fs_search" else {"symbol": "alpha", "direction": "up"}
    )
    legacy = (
        build_fs_search_tool(tmp_path / "old-search.db", root)
        if tool == "fs_search"
        else build_fs_reach_tool(root, scratch_db=tmp_path / "old-reach.db")
    )
    expected = legacy.handler(params)
    assert expected.error is None
    for _ in range(3):
        actual = project_tools._dispatch(tool, params, root=root, scratch=scratch)
        assert actual.error is None, actual.error
        assert actual.result == expected.result
    assert list(scratch.iterdir()) == []
    assert not (root / ".fa").exists()


def test_shared_memory_reach_connections_are_scoped_and_temp_tables_in_memory(tmp_path: Path) -> None:
    root, _scratch = _tree(tmp_path, "view", "def alpha():\n    return 1\n\ndef caller():\n    return alpha()\n")
    index = StructuralIndex(tmp_path / "not-created.db", in_memory=True)
    try:
        assert index.ensure_indexed(root).available
        assert [row.qualname for row in index.find_symbols("alpha")] == ["alpha"]
        connection = index._connect()
        try:
            assert connection.execute("PRAGMA temp_store").fetchone() == (2,)
            assert connection.execute("PRAGMA journal_mode").fetchone() == ("memory",)
        finally:
            connection.close()
        second = StructuralIndex(tmp_path / "also-not-created.db", in_memory=True)
        try:
            connection = second._connect()
            try:
                assert connection.execute("SELECT count(*) FROM sqlite_master WHERE name='symbols'").fetchone() == (0,)
            finally:
                connection.close()
        finally:
            second.close()
    finally:
        index.close()
    assert not (tmp_path / "not-created.db").exists()


@pytest.mark.parametrize(
    "tool,db,params",
    [
        ("fs_search", "search.db", {"query": "alpha", "output_mode": "matches"}),
        ("fs_reach", "structural.db", {"symbol": "alpha"}),
    ],
)
def test_scratch_symlink_race_cannot_redirect_memory_index(
    tmp_path: Path, tool: str, db: str, params: dict[str, Any]
) -> None:
    root, scratch = _tree(tmp_path, "view", "def alpha():\n    return 1\n")
    victim = root / "victim.db"
    victim.write_bytes(b"untouched-source")
    link = scratch / db
    stop = threading.Event()
    started = threading.Event()
    count: list[int] = []

    def attacker() -> None:
        while not stop.is_set():
            link.unlink(missing_ok=True)
            link.symlink_to(victim)
            count.append(1)
            started.set()

    thread = threading.Thread(target=attacker)
    thread.start()
    try:
        assert started.wait(5)
        for _ in range(20):
            result = project_tools._dispatch(tool, params, root=root, scratch=scratch)
            assert result.error is None, result.error
            assert victim.read_bytes() == b"untouched-source"
    finally:
        stop.set()
        thread.join(timeout=5)
    assert not thread.is_alive() and count
    assert victim.read_bytes() == b"untouched-source"


def test_search_memory_temp_store_and_refresh_state_lifetime(tmp_path: Path) -> None:
    root, _scratch = _tree(tmp_path, "view", "def alpha():\n    return 1\n")
    index = SearchIndex(Path(":memory:"))
    key = index._state_key(root.resolve())
    try:
        assert index._conn is not None
        assert index._conn.execute("PRAGMA temp_store").fetchone() == (2,)
        assert index._conn.execute("PRAGMA journal_mode").fetchone() == ("memory",)
        index.ensure_indexed(root)
        assert key in _refresh_state
    finally:
        index.close()
    assert key not in _refresh_state
    assert not (root / ":memory:").exists()
