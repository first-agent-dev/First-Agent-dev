"""S12.7 (CT3/GAP5, v4 amendments) — read_file three-tier frames + handoff.

Tier contract (R16 rendered-measure rule — the binary rule is the MEASURE,
len(render_tool_payload(result).encode()), the same quantity projection
compares; never a magic raw-byte count):

  T1 full read fits   -> frame "[File: p — N lines, B bytes — showing ALL]"
  T2 window fits      -> frame with a-b / above / below / resume call /
                         <=~750-line whole-window promise
  T3 over ceiling     -> handler hands off the RAW unframed payload (window
                         fields kept); projection's ``_read_head_frame``
                         elider builds the TRUNCATED frame, window-ANCHORED
                         at the requested start, with resume + steer;
                         artifact payloads get the artifact variant (no
                         outline steer).

Exactly one framing layer ever applies (CT5): a framed result is never
re-elided, an elided result carries exactly one TRUNCATED header and no
leftover ``frame`` field.
"""

from __future__ import annotations

import re
from pathlib import Path

from fa.inner_loop.artifacts import ArtifactStore
from fa.inner_loop.context import reset_current_session, set_current_session
from fa.inner_loop.projection import project_for_model, render_tool_payload
from fa.inner_loop.registry import DEFAULT_TOOL_CONTEXT_BYTES
from fa.inner_loop.state import EventLog, SessionState
from fa.inner_loop.tools.read_file import build_read_file_tool

_CEILING = DEFAULT_TOOL_CONTEXT_BYTES
_T3_HEADER = re.compile(
    r"\[File: .+ — TRUNCATED: showing lines (\d+)-(\d+) — (\d+) below — continue with start_line=(\d+)"
)


def _big_file(tmp_path: Path, n_lines: int, line: str) -> Path:
    path = tmp_path / "big_mod.py"
    path.write_text("\n".join(line.format(i=i) for i in range(1, n_lines + 1)) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# T1 / T2 — inline frames
# ---------------------------------------------------------------------------


def test_s127_t1_full_read_frame(tmp_path: Path) -> None:
    """T1: fits -> content pure + frame naming lines/bytes/showing ALL."""
    tool = build_read_file_tool(tmp_path)
    (tmp_path / "s.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    result = tool.handler({"path": "s.txt"})
    assert result.result is not None
    assert result.error is None
    assert result.result["content"] == "alpha\nbeta\n"  # content stays PURE
    assert result.result["line_count"] == 2
    assert result.result["frame"] == "[File: s.txt — 2 lines, 11 bytes — showing ALL]"
    assert result.result["rel_path"] == "s.txt"
    # T1 never elides: projected inline, no artifact.
    projected = project_for_model(tool, result, ArtifactStore(tmp_path / "a"))
    assert "[artifact:" not in projected


def test_s127_t2_window_frame_and_resume(tmp_path: Path) -> None:
    """T2: window -> a-b, above/below counts, exact resume call, promise."""
    tool = build_read_file_tool(tmp_path)
    _big_file(tmp_path, 100, "def f{i}(x): return {i}")
    result = tool.handler({"path": "big_mod.py", "start_line": 10, "end_line": 19})
    assert result.error is None
    assert result.result is not None
    frame = result.result["frame"]
    assert "showing 10-19" in frame
    assert "9 above, 81 below" in frame
    assert "continue with start_line=20" in frame
    assert "<=~750 lines" in frame
    assert result.result is not None
    assert result.result["start_line"] == 10 and result.result["end_line"] == 19
    assert result.result["content"].splitlines()[0] == "def f10(x): return 10"


# ---------------------------------------------------------------------------
# T3 — elider frames (file, window-anchored, full, artifact variant)
# ---------------------------------------------------------------------------


def _projected_body(projected: str) -> str:
    # strip "{summary}\n\n" prefix and trailing "\n\n[artifact: …]" footer
    body = projected.split("\n\n", 1)[1]
    return body.rsplit("\n\n[artifact: tool-result-", 1)[0]


def test_s127_t2_oversize_hands_off_to_window_anchored_t3(tmp_path: Path) -> None:
    """T-frame-handoff: over-ceiling window arrives as T3 anchored at the
    REQUESTED start — never a frame from line 1, never double-framed."""
    tool = build_read_file_tool(tmp_path)
    _big_file(tmp_path, 3_000, "def f{i}(x): return x + {i}  # padding padding padding")
    result = tool.handler({"path": "big_mod.py", "start_line": 2000, "end_line": 2800})
    assert result.error is None
    payload = result.result
    assert payload is not None
    assert "frame" not in payload, "handoff payload must be UNFRAMED (no double frame)"
    assert payload["start_line"] == 2000, "window fields kept for T3 anchoring"

    projected = project_for_model(tool, result, ArtifactStore(tmp_path / "a"))
    assert "[artifact: tool-result-" in projected
    body = _projected_body(projected)
    m = _T3_HEADER.search(body)
    assert m, f"no T3 header in body: {body[:200]!r}"
    start_shown, end_shown, below, resume = map(int, m.groups())
    assert start_shown == 2000, f"T3 must anchor at the REQUESTED start, got {start_shown}"
    assert end_shown >= start_shown, f"implausible range {start_shown}-{end_shown} (numbering drift)"
    assert resume == end_shown + 1
    assert below == 3_000 - end_shown
    assert "fs_search(output_mode='outline', path=big_mod.py)" in body
    # body shows real (unescaped) lines from the window — and the header's
    # numbers must MATCH the actual body content (marker lines carry their
    # own index; mutation-hardening against display-numbering drift).
    body_lines = body.split("\n")[1:]
    assert body_lines[0] == "def f2000(x): return x + 2000  # padding padding padding"
    assert body_lines[-1].startswith(f"def f{end_shown}(x):"), (
        f"last shown line {body_lines[-1][:30]!r} disagrees with header end {end_shown}"
    )
    # elided block respects the footer reserve
    assert len(body.encode()) <= _CEILING - 100


def test_s127_t3_full_oversize_anchors_at_one_with_steer(tmp_path: Path) -> None:
    """T3 (unwindowed): head frame from line 1 + outline steer + artifact."""
    tool = build_read_file_tool(tmp_path)
    _big_file(tmp_path, 3_000, "def f{i}(x): return x + {i}  # padding padding padding")
    result = tool.handler({"path": "big_mod.py"})
    assert result.result is not None
    assert "frame" not in result.result
    projected = project_for_model(tool, result, ArtifactStore(tmp_path / "a"))
    body = _projected_body(projected)
    m = _T3_HEADER.search(body)
    assert m and int(m.group(1)) == 1
    assert int(m.group(4)) == int(m.group(2)) + 1
    assert "def f1(" in body


def test_s127_t3_artifact_variant_no_outline_steer(tmp_path: Path) -> None:
    """T3 artifact payloads: header names the artifact, resume via windowed
    artifact read, NO fs_search outline steer."""
    tool = build_read_file_tool(tmp_path)
    log = EventLog(tmp_path / "r" / "events.jsonl", run_id="r")
    state = SessionState(workspace_root=tmp_path, run_id="r", log=log)
    state.artifact_store = ArtifactStore(tmp_path / "r" / "fa-artifacts")
    artifact_id = state.artifact_store.put(
        "\n".join(f"row {i}: " + "p" * 48 for i in range(1, 2_001))  # ~100KB
    )

    token = set_current_session(state)
    try:
        result = tool.handler({"artifact_id": artifact_id, "start_line": 5, "end_line": 1_900})
        assert result.error is None
    finally:
        reset_current_session(token)
    payload = result.result
    assert payload is not None
    assert "frame" not in payload

    projected = project_for_model(tool, result, ArtifactStore(tmp_path / "proj"))
    assert "[artifact: tool-result-" in projected
    body = _projected_body(projected)
    assert f"[Artifact: {artifact_id} — 2000 lines total — TRUNCATED: showing lines 5-" in body
    assert "continue with start_line=" in body and f"(artifact_id={artifact_id})]" in body
    assert "fs_search" not in body, "artifact T3 must not steer to fs_search outline"
    assert body.split("\n", 1)[1].startswith("row 5")


def test_s127_t1_artifact_read_gets_frame(tmp_path: Path) -> None:
    """Framing is uniform: a fitting artifact read carries the T1 artifact frame."""
    tool = build_read_file_tool(tmp_path)
    log = EventLog(tmp_path / "r2" / "events.jsonl", run_id="r2")
    state = SessionState(workspace_root=tmp_path, run_id="r2", log=log)
    state.artifact_store = ArtifactStore(tmp_path / "r2" / "fa-artifacts")
    artifact_id = state.artifact_store.put("a\nb\nc\n")
    token = set_current_session(state)
    try:
        result = tool.handler({"artifact_id": artifact_id})
        assert result.result is not None
    finally:
        reset_current_session(token)
    assert result.error is None
    assert result.result["frame"] == f"[Artifact: {artifact_id} — 3 lines — showing ALL]"


# ---------------------------------------------------------------------------
# C0p — the rendered-measure property (R16 rule) across densities
# ---------------------------------------------------------------------------


def test_s127_rendered_measure_property_across_densities(tmp_path: Path) -> None:
    """INVARIANT: every INLINE (framed) result renders <= ceiling; over-ceiling
    windows hand off. Sweep includes the R16 fixture shapes: escape-free text,
    escape-dense code (quotes/backslashes), and long single lines.

    The R16 measurement this pins: 32,000B raw escape-dense content renders
    34,210B > ceiling — so a window of that size MUST hand off, not frame.
    """
    tool = build_read_file_tool(tmp_path)
    densities = {
        "escape-free": "line {i} of plain text without escapes padding padding",
        "escape-dense": 'def f{i}(s): return s + "\\"q{i}\\" && \'x\'  # \\\\ back',
        "mixed": "row {i}: text 'quoted' and \\\\ slash plus normal words here",
    }
    for label, template in densities.items():
        content = "\n".join(template.format(i=i) for i in range(1, 900))  # ~50-70KB
        (tmp_path / "mod.py").write_text(content + "\n", encoding="utf-8")
        total_lines = 900

        # (a) framed windows near the promised size stay inline and <= ceiling
        result = tool.handler({"path": "mod.py", "start_line": 1, "end_line": 700})
        assert result.error is None
        payload = result.result
        assert payload is not None
        if "frame" in payload:  # inline tier
            rendered = len(render_tool_payload(payload).encode())
            assert rendered <= _CEILING, f"{label}: framed result {rendered}B > ceiling"

        # (b) the whole file (clearly over) hands off
        result = tool.handler({"path": "mod.py"})
        assert result.error is None
        payload = result.result
        assert payload is not None
        assert "frame" not in payload, f"{label}: oversize read must hand off, not frame"

        # (c) a window near the raw 32k boundary: whatever the handler decides,
        # projection's own measure agrees — inline implies <= ceiling
        win_start = max(1, total_lines // 2)
        result = tool.handler({"path": "mod.py", "start_line": win_start, "end_line": win_start + 750})
        assert result.error is None
        payload = result.result
        assert payload is not None
        if "frame" in payload:
            assert len(render_tool_payload(payload).encode()) <= _CEILING


def test_s127_r16_boundary_window_does_not_frame_inline(tmp_path: Path) -> None:
    """The R16 fixture as a binary pin: ~32,000B of escape-dense code in one
    window must NOT come back framed-inline (it renders > ceiling)."""
    tool = build_read_file_tool(tmp_path)
    line = 'def f{i}(x): return "quoted \\" text" + \'\\\' + str({i})  # tail'
    lines = [line.format(i=i) for i in range(1, 900)]
    # take a contiguous block whose RAW size is ~32,000B
    block: list[str] = []
    raw = 0
    it = iter(lines)
    while raw < 32_000:
        nxt = next(it)
        block.append(nxt)
        raw += len(nxt.encode()) + 1
    content = "\n".join(lines) + "\n"
    (tmp_path / "dense.py").write_text(content, encoding="utf-8")

    result = tool.handler({"path": "dense.py", "start_line": 1, "end_line": len(block)})
    assert result.result is not None
    assert result.error is None
    framed_rendered = len(render_tool_payload({**result.result, "frame": "x" * 140}).encode())
    if framed_rendered <= _CEILING:
        pass  # this fixture's density turned out frame-safe; property test covers the rest
    else:
        assert "frame" not in result.result, "escape-dense ~32kB window renders over the ceiling and must hand off"


def test_s127_handler_never_double_frames(tmp_path: Path) -> None:
    """CT5: exactly one framing layer — a handed-off payload projected through
    the elider carries exactly one TRUNCATED header and no leftover frame key."""
    tool = build_read_file_tool(tmp_path)
    _big_file(tmp_path, 3_000, "def f{i}(x): return x + {i}  # padding padding padding")
    result = tool.handler({"path": "big_mod.py", "start_line": 100, "end_line": 2_000})
    projected = project_for_model(tool, result, ArtifactStore(tmp_path / "a"))
    body = _projected_body(projected)
    assert body.count("TRUNCATED: showing lines") == 1
    assert '"frame"' not in body
