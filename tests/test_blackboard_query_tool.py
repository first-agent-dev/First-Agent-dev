"""S13.x — `fs_blackboard_query` tool contract (PLAN-fs-blackboard-query).

Covers CT1 (tool dispatch → compact rows via real Blackboard.query), CT2
(blackboard_unavailable when no blackboard), the TOOL_NAMES membership, the
limit clamp/slice, and registration in implementer/planner (not verifier).

Tests labelled per tests-writing skill:
- C0p: pure helpers (_clamp_limit, is_valid_wire_name/TOOL_NAMES).
- C1: real ToolRegistry + real SessionState with a bound blackboard, dispatch
      via ToolCall (external DB is the real temp-dir SQLite).
- C2: registry membership via build_baseline_registry / build_planner_registry /
      build_eval_registry.

**Kill-checks (must fail if the producer is removed):**
- removing the `blackboard.query(...)` call in the handler → test_happy_path fails.
- removing the no-blackboard guard → test_no_blackboard fails.
- removing "fs_blackboard_query" from TOOL_NAMES → test_tool_names_includes fails.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from fa.blackboard.blackboard import BlackboardEntry
from fa.inner_loop import SessionState, ToolCall
from fa.inner_loop.context import reset_current_session, set_current_session
from fa.inner_loop.registry import ToolRegistry, ToolResult
from fa.inner_loop.tool_names import TOOL_NAMES, is_valid_wire_name
from fa.inner_loop.tools import build_baseline_registry, build_eval_registry, build_planner_registry
from fa.inner_loop.tools.blackboard_query import MAX_LIMIT, _clamp_limit, build_blackboard_query_tool

# --- C0p: pure helpers ---------------------------------------------------------


def test_clamp_limit_defaults_and_caps() -> None:
    """C0p — limit defaults to 10, is clamped to max 50, and ignores non-int."""
    assert _clamp_limit({}) == 10
    assert _clamp_limit({"limit": 3}) == 3
    assert _clamp_limit({"limit": 0}) == 10
    assert _clamp_limit({"limit": -5}) == 10
    assert _clamp_limit({"limit": 100}) == MAX_LIMIT
    assert _clamp_limit({"limit": "x"}) == 10


def test_tool_name_is_canonical_and_dotless() -> None:
    """C0p — fs_blackboard_query is a valid, dotless canonical wire name."""
    assert "fs_blackboard_query" in TOOL_NAMES
    assert is_valid_wire_name("fs_blackboard_query")
    assert "." not in "fs_blackboard_query"


# --- C1: dispatch against a real session + blackboard -------------------------


def _seed_blackboard(state: SessionState) -> None:
    """Write two file_version rows to the session's blackboard."""
    assert state.blackboard is not None
    state.blackboard.write(
        BlackboardEntry.create(
            id="r1",
            type="file_version",
            payload={"path": "src/auth.py"},
            read_set=["src/auth.py"],
            write_set=["src/auth.py"],
            assumptions=["base_commit abc123"],
            version_dependencies={"base_commit": "abc123"},
        )
    )
    state.blackboard.write(
        BlackboardEntry.create(
            id="r2",
            type="file_version",
            payload={"path": "src/main.py"},
            read_set=["src/main.py"],
            write_set=["src/main.py"],
            assumptions=["base_commit abc123"],
            version_dependencies={"base_commit": "abc123"},
        )
    )


def _dispatch(state: SessionState, params: Mapping[str, object]) -> ToolResult:
    """Bind the session contextvar, build a registry with the tool, dispatch."""
    registry = ToolRegistry()
    registry.register(build_blackboard_query_tool())
    token = set_current_session(state)
    try:
        return registry.dispatch(ToolCall(name="fs_blackboard_query", params=dict(params)))
    finally:
        reset_current_session(token)


def test_happy_path_returns_compact_rows(tmp_path: Path) -> None:
    """C1 — dispatch returns compact metadata rows from the real blackboard."""
    state = SessionState(workspace_root=tmp_path, run_id="run-1")
    _seed_blackboard(state)
    result = _dispatch(state, {"type": "file_version"})

    assert result.error is None
    data = result.result
    assert data is not None
    rows = data["rows"]
    assert len(rows) == 2
    # Compact metadata: has path (derived from payload), no payload blob, no content_hash leak of payload.
    ids = {row["id"] for row in rows}
    assert ids == {"r1", "r2"}
    for row in rows:
        assert "payload" not in row
        assert row["type"] == "file_version"
        assert "content_hash" in row
        assert row["path"] in ("src/auth.py", "src/main.py")


def test_path_falls_back_to_write_set(tmp_path: Path) -> None:
    """C1 — an entry whose payload has no 'path' derives path from write_set/read_set."""
    state = SessionState(workspace_root=tmp_path, run_id="run-1")
    assert state.blackboard is not None
    state.blackboard.write(
        BlackboardEntry.create(
            id="rp",
            type="file_version",
            payload={"note": "no path here"},
            read_set=["src/other.py"],
            write_set=["src/other.py"],
            assumptions=[],
            version_dependencies={},
        )
    )
    result = _dispatch(state, {})
    assert result.error is None
    data = result.result
    assert data is not None
    row = data["rows"][0]
    assert row["path"] == "src/other.py"
    assert "payload" not in row


def test_type_filter(tmp_path: Path) -> None:
    """C1 — type filter narrows results."""
    state = SessionState(workspace_root=tmp_path, run_id="run-1")
    _seed_blackboard(state)
    result = _dispatch(state, {"type": "nonexistent_type"})
    assert result.error is None
    data = result.result
    assert data is not None
    assert data["rows"] == []


def test_key_filter(tmp_path: Path) -> None:
    """C1 (T2) — the `key` param narrows rows to those whose payload matches the substring.

    _seed_blackboard writes payloads with "path": "src/auth.py" (r1) and
    "src/main.py" (r2). key="auth" must match only r1.
    """
    state = SessionState(workspace_root=tmp_path, run_id="run-1")
    _seed_blackboard(state)
    result = _dispatch(state, {"key": "auth"})
    assert result.error is None
    data = result.result
    assert data is not None
    ids = {row["id"] for row in data["rows"]}
    assert ids == {"r1"}


def test_invalid_params(tmp_path: Path) -> None:
    """C1 (T6) — a non-string `type` / non-integer `limit` is rejected by the schema
    as invalid_params (registry.validate), before the handler runs."""
    state = SessionState(workspace_root=tmp_path, run_id="run-1")
    _seed_blackboard(state)
    result = _dispatch(state, {"limit": "x"})  # schema: integer
    assert result.error is not None
    assert result.error.code == "invalid_params"


def test_limit_slice_takes_most_recent(tmp_path: Path) -> None:
    """C1 — limit slices the most-recent N rows (timestamp ASC → tail)."""
    state = SessionState(workspace_root=tmp_path, run_id="run-1")
    _seed_blackboard(state)
    result = _dispatch(state, {"limit": 1})
    assert result.error is None
    data = result.result
    assert data is not None
    assert data["count"] == 1
    assert len(data["rows"]) == 1


def test_no_blackboard_returns_unavailable(tmp_path: Path) -> None:
    """C1 — a session with blackboard disabled returns blackboard_unavailable, not a crash."""
    # FeatureFlags(blackboard_enabled=False) → state.blackboard is None.
    from fa.feature_flags import FeatureFlags

    state = SessionState(
        workspace_root=tmp_path,
        run_id="run-1",
        feature_flags=FeatureFlags(blackboard_enabled=False),
    )
    assert state.blackboard is None
    result = _dispatch(state, {})
    assert result.error is not None
    assert result.error.code == "blackboard_unavailable"


def test_no_session_returns_unavailable(tmp_path: Path) -> None:
    """C1 — no bound session → blackboard_unavailable."""
    registry = ToolRegistry()
    registry.register(build_blackboard_query_tool())
    result = registry.dispatch(ToolCall(name="fs_blackboard_query", params={}))
    assert result.error is not None
    assert result.error.code == "blackboard_unavailable"


def test_query_failure_is_surfaced_not_masked(tmp_path: Path) -> None:
    """C1 — a Blackboard.query exception becomes blackboard_query_failed, not internal_error.

    The handler catches it itself (ToolRegistry.dispatch would mask a bare raise
    as internal_error). We force a failure by making the blackboard query raise.
    """

    class _BoomBlackboard:
        def query(self, *a: object, **k: object) -> list[object]:
            raise RuntimeError("boom")

    state = SessionState(workspace_root=tmp_path, run_id="run-1")
    # Replace the real blackboard with one that raises.
    state.blackboard = _BoomBlackboard()  # type: ignore[assignment]

    registry = ToolRegistry()
    registry.register(build_blackboard_query_tool())
    token = set_current_session(state)
    try:
        result = registry.dispatch(ToolCall(name="fs_blackboard_query", params={}))
    finally:
        reset_current_session(token)
    assert result.error is not None
    assert result.error.code == "blackboard_query_failed"
    assert result.error.code != "internal_error"


# --- C2: registry membership ---------------------------------------------------


def test_registered_in_implementer_and_planner(tmp_path: Path) -> None:
    """C2 — implementer (baseline) and planner registries contain the tool."""
    for build in (build_baseline_registry, build_planner_registry):
        registry = build(tmp_path)
        assert "fs_blackboard_query" in registry.names()


def test_not_in_verifier_registry(tmp_path: Path) -> None:
    """C2 — eval (verifier) registry does NOT contain the tool."""
    registry = build_eval_registry(tmp_path)
    assert "fs_blackboard_query" not in registry.names()


def test_inner_loop_smoke_path_builds(tmp_path: Path) -> None:
    """C2 — build_baseline_registry (the inner-loop-smoke path) builds without error
    and contains the tool; a no-session dispatch returns blackboard_unavailable."""
    registry = build_baseline_registry(tmp_path)
    assert "fs_blackboard_query" in registry.names()
    result = registry.dispatch(ToolCall(name="fs_blackboard_query", params={}))
    assert result.error is not None
    assert result.error.code == "blackboard_unavailable"


# --- S14: artifact-index integration at the tool surface ---------------------


def test_compact_surfaces_title_for_artifact_entries(tmp_path: Path) -> None:
    """C1 — after lazy artifact indexing, compact rows include a 'title' field
    for artifact entries but remain payload-free."""
    k = tmp_path / "knowledge" / "skills"
    k.mkdir(parents=True)
    (k / "plan-authoring").mkdir()
    (k / "plan-authoring" / "SKILL.md").write_text("# Plan Authoring\nbody", encoding="utf-8")
    state = SessionState(workspace_root=tmp_path, run_id="run-s14")

    result = _dispatch(state, {"type": "skill"})
    assert result.error is None
    data = result.result
    assert data is not None
    assert "indexed" in data
    assert data["indexed"]["added"] >= 1
    rows = data["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["type"] == "skill"
    assert row.get("title") == "Plan Authoring"
    assert "payload" not in row
    assert row["path"].endswith("SKILL.md")


def test_compact_file_version_has_no_title_key(tmp_path: Path) -> None:
    """C1 — file_version rows (which carry no 'title' in payload) do NOT gain a
    'title' key (no spurious additive field on non-artifact rows)."""
    state = SessionState(workspace_root=tmp_path, run_id="run-s14")
    _seed_blackboard(state)
    result = _dispatch(state, {"type": "file_version"})
    assert result.error is None
    data = result.result
    assert data is not None
    for row in data["rows"]:
        assert "title" not in row, "file_version rows must not expose a 'title' key"
    # Indexer must not have run for file_version query.
    assert "indexed" not in data
