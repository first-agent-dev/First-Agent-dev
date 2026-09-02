"""S12.7 (CT7/GAP8) — followable artifacts: ArtifactStore.get + read_file artifact_id.

Conventions per knowledge/skills/tests-writing: C0 (store unit), C1 (handler +
projection offline). P8 matrix: valid / unknown / foreign / traversal / oversize
window.

Guard complex under test (artifacts.py get()):
  G1 id shape gate  — ^tool-result-[0-9a-f]{16}$; rejects traversal/absolute
                     ids by construction, zero disk access;
  G2 containment    — resolved path must stay under the store root;
  G3 fail-closed    — missing/corrupt -> None (+WARNING), never a raise.

Resolution under test (read_file._artifact_stores): BOTH session-owned roots
(``session.artifact_store`` = workspace/.fa/artifacts AND the per-run
projection store from ``ArtifactStore.from_event_log(session.log)``); anything
else is foreign.
"""

from __future__ import annotations

import json
from pathlib import Path

from fa.inner_loop.artifacts import ArtifactStore
from fa.inner_loop.context import reset_current_session, set_current_session
from fa.inner_loop.projection import project_for_model
from fa.inner_loop.registry import DEFAULT_TOOL_CONTEXT_BYTES
from fa.inner_loop.state import EventLog, SessionState
from fa.inner_loop.tools.read_file import build_read_file_tool

# ---------------------------------------------------------------------------
# C0 — ArtifactStore.get
# ---------------------------------------------------------------------------


def test_s127_store_get_roundtrip_str_and_mapping(tmp_path: Path) -> None:
    """producer-kill-check: remove get() -> this fails (CT7)."""
    store = ArtifactStore(tmp_path / "artifacts")
    as_str = store.put("line1\nline2\nline3\n")
    as_map = store.put({"stdout": "x" * 10, "returncode": 0})

    assert store.get(as_str) == "line1\nline2\nline3\n"
    assert store.get(as_map) == {"stdout": "x" * 10, "returncode": 0}
    # put is idempotent/content-addressed: same payload -> same id, one file.
    assert store.put({"stdout": "x" * 10, "returncode": 0}) == as_map
    assert len(list((tmp_path / "artifacts").glob("*.json"))) == 2


def test_s127_store_get_rejects_malformed_ids_without_disk(tmp_path: Path) -> None:
    """G1: traversal / absolute / wrong-shape / non-str ids -> None.

    The store root does not even exist here — proving these never touch disk
    (no exception, no implicit creation).
    """
    store = ArtifactStore(tmp_path / "does-not-exist")
    malformed = [
        "../../etc/passwd",
        "../../../etc/passwd.json",
        "/etc/passwd",
        "/abs/tool-result-0000000000000000",
        "tool-result-abc",  # too short
        "tool-result-" + "0" * 17,  # too long
        "tool-result-" + "z" * 16,  # non-hex
        "TOOL-RESULT-" + "0" * 16,  # case
        "tool-result-" + "0" * 15 + " ",  # trailing space
        " tool-result-" + "0" * 16,
        "",
        "tool-result-0000000000000000\n/../x",
    ]
    for bad in malformed:
        assert store.get(bad) is None, f"malformed id must return None: {bad!r}"
    assert store.get(123) is None  # type: ignore[arg-type] # non-str
    assert not (tmp_path / "does-not-exist").exists()

    # Escape traps (mutation-hardening): files that WOULD be reached if the
    # shape/containment guard were stripped — traversal and absolute ids must
    # not leak them.
    (tmp_path / "secret.json").write_text('{"leaked": true}', encoding="utf-8")
    assert store.get("../secret") is None, "traversal id must not reach a sibling file"
    assert store.get(str(tmp_path / "secret")) is None, "absolute id must not reach an arbitrary file"


def test_s127_store_get_unknown_and_foreign_return_none(tmp_path: Path) -> None:
    """G1/G3: well-shaped but absent (here or in a foreign root) -> None."""
    mine = ArtifactStore(tmp_path / "mine")
    foreign = ArtifactStore(tmp_path / "foreign")
    foreign_id = foreign.put({"secret": "not yours"})

    assert mine.get(foreign_id) is None, "foreign-run id must not resolve"
    assert mine.get("tool-result-" + "0" * 16) is None, "unknown id must not resolve"


def test_s127_store_get_corrupt_file_fails_closed(tmp_path: Path) -> None:
    """G3: corrupt payload -> None (WARNING logged), never a raise."""
    store = ArtifactStore(tmp_path / "artifacts")
    artifact_id = store.put({"ok": True})
    (tmp_path / "artifacts" / f"{artifact_id}.json").write_text("{not json", encoding="utf-8")
    assert store.get(artifact_id) is None


# ---------------------------------------------------------------------------
# C1 — read_file artifact_id (P8 matrix)
# ---------------------------------------------------------------------------


def _session_with(tmp_path: Path, run: str) -> tuple[SessionState, ArtifactStore, ArtifactStore]:
    """Session owning BOTH roots: a .fa-style store and the run-log store."""
    log = EventLog(tmp_path / run / "events.jsonl", run_id=run)
    state = SessionState(workspace_root=tmp_path, run_id=run, log=log)
    state.artifact_store = ArtifactStore(tmp_path / run / "fa-artifacts")
    log_store = ArtifactStore.from_event_log(log)
    return state, state.artifact_store, log_store


def test_s127_read_file_resolves_artifact_from_session_store(tmp_path: Path) -> None:
    """P8 valid: full payload + line_count, resolved via session.artifact_store."""
    tool = build_read_file_tool(tmp_path)
    state, owned, _ = _session_with(tmp_path, "r1")
    artifact_id = owned.put("alpha\nbeta\ngamma\n")

    token = set_current_session(state)
    try:
        result = tool.handler({"artifact_id": artifact_id})
    finally:
        reset_current_session(token)

    assert result.error is None, result.error
    assert result.result["content"] == "alpha\nbeta\ngamma\n"
    assert result.result["line_count"] == 3
    assert result.result["artifact_id"] == artifact_id
    assert result.summary == f"read artifact {artifact_id}"


def test_s127_read_file_resolves_artifact_from_projection_store(tmp_path: Path) -> None:
    """P8 valid (second root): the per-run projection store's [artifact: …]
    refs — the ones project_for_model mints — must be followable too."""
    tool = build_read_file_tool(tmp_path)
    state, _, log_store = _session_with(tmp_path, "r2")
    artifact_id = log_store.put({"stdout": "projection-elided output\nsecond line"})

    token = set_current_session(state)
    try:
        full = tool.handler({"artifact_id": artifact_id})
        first_line = tool.handler({"artifact_id": artifact_id, "start_line": 1, "end_line": 1})
    finally:
        reset_current_session(token)

    assert full.error is None, full.error
    # dict payload renders via render_tool_payload (pretty JSON, sort_keys).
    assert "projection-elided output" in full.result["content"]
    assert "second line" in full.result["content"]
    assert full.result["line_count"] == 3  # { / \stdout\: … / } — embedded \n stays escaped
    # windowing applies over the RENDERED lines: line 1 of the JSON is '{'.
    assert first_line.result["content"] == "{"
    assert first_line.result["line_count"] == full.result["line_count"]


def test_s127_read_file_windowed_artifact_semantics(tmp_path: Path) -> None:
    """P8 window: identical semantics to file reads (shared _validated_window)."""
    tool = build_read_file_tool(tmp_path)
    state, owned, _ = _session_with(tmp_path, "r3")
    artifact_id = owned.put("\n".join(f"line{i}" for i in range(1, 51)))

    token = set_current_session(state)
    try:
        windowed = tool.handler({"artifact_id": artifact_id, "start_line": 10, "end_line": 19})
        end_only = tool.handler({"artifact_id": artifact_id, "end_line": 3})
        invalid = tool.handler({"artifact_id": artifact_id, "start_line": 0, "end_line": 5})
        inverted = tool.handler({"artifact_id": artifact_id, "start_line": 9, "end_line": 4})
    finally:
        reset_current_session(token)

    assert windowed.result["content"] == "\n".join(f"line{i}" for i in range(10, 20))
    assert windowed.result["line_count"] == 50
    assert end_only.result["content"] == "line1\nline2\nline3"
    assert invalid.error.code == "invalid_params" and "window" in invalid.error.message
    assert inverted.error.code == "invalid_params"


def test_s127_read_file_unknown_foreign_and_traversal_artifacts(tmp_path: Path) -> None:
    """P8 unknown/foreign/traversal: one structured artifact_not_found with
    steering; no existence oracle distinctions."""
    tool = build_read_file_tool(tmp_path)
    state, _, _ = _session_with(tmp_path, "r4")
    foreign = ArtifactStore(tmp_path / "foreign-run")
    foreign_id = foreign.put("other run payload")

    cases = {
        "unknown": "tool-result-" + "b" * 16,
        "foreign-run": foreign_id,
        "traversal": "../../etc/passwd",
        "absolute": "/etc/passwd",
        "wrong-shape": "tool-result-zzz",
    }
    token = set_current_session(state)
    try:
        results = {label: tool.handler({"artifact_id": aid}) for label, aid in cases.items()}
    finally:
        reset_current_session(token)

    for label, result in results.items():
        assert result.error is not None, f"{label}: must fail, got {result.result!r}"
        assert result.error.code == "artifact_not_found", f"{label}: {result.error.code}"
        assert "[artifact: tool-result-" in result.error.message, (
            f"{label}: steering to the reference syntax is required, got {result.error.message!r}"
        )
    assert not (tmp_path / "foreign-run").exists() or foreign_id  # foreign store intact


def test_s127_read_file_path_and_artifact_id_are_mutually_exclusive(tmp_path: Path) -> None:
    """XOR guard: both -> invalid_params; neither -> invalid_params."""
    tool = build_read_file_tool(tmp_path)

    both = tool.handler({"path": "some.txt", "artifact_id": "tool-result-" + "c" * 16})
    neither = tool.handler({})
    bad_type = tool.handler({"artifact_id": 42})

    assert both.error.code == "invalid_params" and "mutually exclusive" in both.error.message
    assert neither.error.code == "invalid_params" and ("path" in neither.error.message)
    assert bad_type.error.code == "invalid_params"


def test_s127_read_file_artifact_without_session_fails_structured(tmp_path: Path) -> None:
    """No session (bare call): nothing was ever projected -> not found, no raise."""
    tool = build_read_file_tool(tmp_path)
    result = tool.handler({"artifact_id": "tool-result-" + "d" * 16})
    assert result.error is not None and result.error.code == "artifact_not_found"


def test_s127_oversize_artifact_read_elides_via_projection(tmp_path: Path) -> None:
    """P8 oversize: handler returns FULL payload; projection (ceiling 32,768)
    elides it and mints a chained [artifact: …] ref — bounded, followable."""
    tool = build_read_file_tool(tmp_path)
    state, owned, _ = _session_with(tmp_path, "r5")
    artifact_id = owned.put("z" * 40_000)

    token = set_current_session(state)
    try:
        result = tool.handler({"artifact_id": artifact_id})
    finally:
        reset_current_session(token)

    assert result.error is None
    assert len(result.result["content"]) == 40_000  # full payload from the store

    projected = project_for_model(tool, result, ArtifactStore(tmp_path / "projection-artifacts"))
    assert "[artifact: tool-result-" in projected, "oversize read must elide with a chained ref"
    assert len(projected.encode("utf-8")) <= DEFAULT_TOOL_CONTEXT_BYTES + 300, (
        f"projected artifact read must stay near the ceiling, got {len(projected)} bytes"
    )
    # the chained artifact is itself followable (files are named {id}.json)
    import re

    chained_id = re.findall(r"tool-result-[0-9a-f]{16}", projected)[-1]
    chained = json.loads((tmp_path / "projection-artifacts" / f"{chained_id}.json").read_text(encoding="utf-8"))
    assert chained["content"] == "z" * 40_000
