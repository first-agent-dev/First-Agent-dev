"""S12.7 (CT6/GAP7) — single offload path + audit-complete events (RD-1).

Invariants under test:
  I1 projection is the ONLY in-loop offload path (state's threshold-8000
     block deleted; zero premature artifacts);
  I2 events carry the FULL raw result always — logged ⊇ model-visible at
     every size; no ``preview`` / injected ``artifact_id`` event fields;
  I3 a config still carrying ``offload_threshold`` gets an OBSERVABLE
     unknown-flag warning and the value is ignored (field removed);
  I4 compaction masking keeps working with no event artifact_id (self-store
     fallback — pinned in test_compaction_sota.py, cross-referenced here).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from fa.inner_loop.artifacts import ArtifactStore
from fa.inner_loop.projection import project_for_model
from fa.inner_loop.registry import ToolCall, ToolResult
from fa.inner_loop.state import EventLog, SessionState
from fa.inner_loop.tools.read_file import build_read_file_tool


def _record(tmp_path: Path, payload_size: int) -> tuple[SessionState, dict[str, Any]]:
    log = EventLog(tmp_path / "events.jsonl", run_id="audit")
    state = SessionState(workspace_root=tmp_path, run_id="audit", log=log)
    state.record_tool_result(
        ToolCall(name="demo.tool", params={}, call_id="c1"),
        ToolResult.ok("sum", result={"data": "x" * payload_size}),
    )
    rows = log.read_all()
    event = [e for e in rows if e.kind == "tool_result"][-1]
    return state, cast("dict[str, Any]", dict(event.content))


# ---------------------------------------------------------------------------
# I1 + I2 — no premature artifacts; full raw always
# ---------------------------------------------------------------------------


def test_s127_no_premature_artifact_and_no_preview(tmp_path: Path) -> None:
    """T-no-premature: a 9k result (under the 32k ceiling, never elided)
    produces NO artifact file anywhere, and the event carries the full raw
    with no preview/artifact_id fields (the deleted block's fingerprints).

    kill-check: re-adding any threshold offload to record_tool_result
    fails the artifact-file scan or the key assertions.
    """
    _state, content = _record(tmp_path, 9_000)

    assert "preview" not in content, "preview field must not exist (deleted with the offload block)"
    assert "artifact_id" not in content, "state must not inject artifact_id (projection owns artifacts)"
    assert content["result"]["data"] == "x" * 9_000, "event must carry the FULL raw result"
    assert content["ok"] is True and content["summary"] == "sum"

    artifacts = list(tmp_path.rglob("tool-result-*.json"))
    assert artifacts == [], f"premature artifacts for a never-elided payload: {artifacts}"
    store_files = list((tmp_path / ".fa" / "artifacts").glob("*.json")) if (tmp_path / ".fa").exists() else []
    assert store_files == []


def test_s127_audit_superset_across_sizes(tmp_path: Path) -> None:
    """T-audit-superset: at 8k / 32k / 40k payload sizes the event holds the
    EXACT full payload, and whatever the model saw (inline, or elided-frame
    + artifact) reconstructs to that same payload — the model never sees
    anything the log lacks, and the log never lies about what existed.
    """
    tool = build_read_file_tool(tmp_path)  # a real ceiling-tier tool
    for size in (8_000, 32_000, 40_000):
        log = EventLog(tmp_path / f"e{size}" / "events.jsonl", run_id=f"a{size}")
        state = SessionState(workspace_root=tmp_path / f"e{size}", run_id=f"a{size}", log=log)
        payload = {"artifact_id": "tool-result-" + "0" * 16, "content": "x" * size, "line_count": 1}
        result = ToolResult.ok("read", result=payload)
        state.record_tool_result(ToolCall(name="fs_read_file", params={}, call_id="c"), result)

        event = [e for e in log.read_all() if e.kind == "tool_result"][-1]
        assert event.content["result"] == payload, f"{size}: event raw must be the exact payload"

        projected = project_for_model(tool, result, ArtifactStore(tmp_path / f"p{size}"))
        if "[artifact:" not in projected:
            assert "x" * 100 in projected  # inline: model saw the payload itself
        else:
            import re

            artifact_id = re.findall(r"tool-result-[0-9a-f]{16}", projected)[-1]
            stored = ArtifactStore(tmp_path / f"p{size}").get(artifact_id)
            assert stored == payload, f"{size}: model-followable artifact must equal the logged raw"


def test_s127_state_has_no_offload_call_sites() -> None:
    """I1 structural pin: record_tool_result's offload is gone — state.py
    contains no ArtifactStore.put call outside the lazy bootstrap."""
    source = Path("src/fa/inner_loop/state.py").read_text(encoding="utf-8")
    assert "artifact_store.put" not in source, "state must not offload (projection owns artifacts)"
    assert ".put(content)" not in source


# ---------------------------------------------------------------------------
# I3 — legacy flag warn-and-ignore
# ---------------------------------------------------------------------------


def test_s127_offload_threshold_config_warns_and_is_ignored(tmp_path: Path) -> None:
    """T-legacy-flag: a config still carrying ``offload_threshold`` gets an
    observable unknown-flag warning naming the key; the value is ignored
    (no field exists to consume it)."""
    from fa.feature_flags import load_feature_flags

    text = """\
feature_flags:
  telemetry_enabled: true
  offload_threshold: 12345
"""
    result = load_feature_flags(text)
    flagged = [w for w in result.warnings if "offload_threshold" in w.key]
    assert flagged, f"legacy offload_threshold must produce a warning; got {[w.key for w in result.warnings]}"
    assert not hasattr(result.flags, "offload_threshold"), "the field must not exist"
    assert result.flags.telemetry_enabled is True  # sibling keys still parse


# ---------------------------------------------------------------------------
# I4 — compaction masking with NO event artifact_id: self-store fallback
# ---------------------------------------------------------------------------


def test_s127_compaction_mask_uses_self_store_without_event_artifact_id(tmp_path: Path) -> None:
    """T-compaction-no-artifact-id (CT6/CD2): with state's injected
    artifact_id gone, ObservationMasker.mask_history masks a large
    tool_result by writing the payload to its OWN store — the masked
    pointer references a real tool-result id and the full content is
    recoverable.

    This pin was MISSING (the card assumed test_compaction_sota:236 covered
    it — that test exercises project_messages_after_mask, a different
    function, and the existing ObservationMasker test passes store=None).
    kill-check: removing the fallback (``if not artifact_id and
    artifact_store is not None:``) fails here.
    """
    from fa.inner_loop.compaction.compactor import ObservationMasker
    from fa.inner_loop.state import TraceEvent

    full_content = {"summary": "ok", "result": {"stdout": "y" * 5_000}, "ok": True}
    events = [
        TraceEvent(
            event_id="ev-1",
            ts="2026-09-02",
            run_id="r",
            actor="coder",
            kind="tool_call",
            tool_name="fs_run_bash",
            tool_call_id="tc-1",
            content={"params": {}},
        ),
        TraceEvent(
            event_id="ev-2",
            ts="2026-09-02",
            run_id="r",
            actor="tool",
            kind="tool_result",
            tool_name="fs_run_bash",
            tool_call_id="tc-1",
            content=full_content,
        ),
        TraceEvent(
            event_id="ev-3",
            ts="2026-09-02",
            run_id="r",
            actor="coder",
            kind="tool_call",
            tool_name="fs_run_bash",
            tool_call_id="tc-2",
            content={"params": {}},
        ),
    ]
    store = ArtifactStore(tmp_path / "mask-artifacts")
    masker = ObservationMasker(recent_turns_to_keep=1)
    masked = masker.mask_history(events, artifact_store=store)

    masked_row = next(e for e in masked if e.kind == "tool_result")
    referenced = masked_row.content.get("artifact_id")
    assert isinstance(referenced, str) and referenced.startswith("tool-result-"), (
        f"masked pointer must reference a self-stored artifact; got {referenced!r}"
    )
    stored = store.get(referenced)
    assert stored is not None and stored == full_content, "stored payload must equal the full masked content"
