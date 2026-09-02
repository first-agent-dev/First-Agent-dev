"""S12.7 (CT4/GAP6) — run_bash tail frames: retention, executor cap, frame, CT5 guard.

Contract (R16-amended CT4):
- HANDLER (both paths, pty + subprocess): stdout retained TAIL-biased at
  ``_RETAINED_TAIL_BYTES`` (30_000); FULL executor-delivered stdout goes to
  the artifact iff trimmed; ``truncated`` flags it. Envelope then renders
  under the 32_768 ceiling and stays INLINE.
- EXECUTOR (runtime/pty_pool.py): output retention tail-biased at
  ``_EXEC_RETAINED_BYTES`` == ``_RETAINED_TAIL_BYTES`` (pinned here) — was a
  head-biased [:8000] slice at three sites.
- PROJECTION: over-ceiling envelopes (huge stderr, escaping inflation) get
  ``_bash_tail_frame``: header + stdout tail + stderr block LAST
  (stderr-preserving), footer reserve, artifact footer appended by
  projection (single id source).
- CT5: a custom elider's output is never silently mutilated — a firing clip
  is a WARNING-observable contract violation; elision stays tied to
  rendered>budget (pinned repo-wide by tests/test_s127_budget.py).

Pty caveat (documented): the pty executor merges stderr into stdout and its
artifact holds the executor-delivered output (up to 30k), not the complete
process output — pre-existing pty limitation, recorded in the plan §15.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fa.inner_loop.artifacts import ArtifactStore
from fa.inner_loop.context import reset_current_session, set_current_session
from fa.inner_loop.projection import project_for_model
from fa.inner_loop.registry import DEFAULT_TOOL_CONTEXT_BYTES, ToolResult
from fa.inner_loop.state import EventLog, SessionState
from fa.inner_loop.tools._common import (
    _BASH_FRAME_RESERVE,
    _RETAINED_TAIL_BYTES,
    _bash_tail_frame,
    _retained_stdout,
    _utf8_tail,
)
from fa.inner_loop.tools.run_bash import build_run_bash_tool
from fa.runtime import pty_pool
from tests._capabilities import requires_posix_shell

_HEAD_MARKER = "HEADMARK"
_TAIL_MARKER = "TAILMARK"


def _large_output_command(filler_len: int) -> str:
    return f"python3 -c \"print('{_HEAD_MARKER}' + 'x' * {filler_len} + '{_TAIL_MARKER}')\""


# ---------------------------------------------------------------------------
# C0 — retention + frame primitives
# ---------------------------------------------------------------------------


def test_s127_retention_boundary() -> None:
    """Exactly 30,000B stays whole; 30,001 retains the tail."""
    exact = "x" * _RETAINED_TAIL_BYTES
    retained, truncated = _retained_stdout(exact)
    assert retained == exact and truncated is False
    over = "HEAD." + "x" * _RETAINED_TAIL_BYTES + ".TAIL"
    retained, truncated = _retained_stdout(over)
    assert truncated is True
    assert retained.endswith(".TAIL") and not retained.startswith("HEAD")
    assert len(retained.encode("utf-8")) <= _RETAINED_TAIL_BYTES


def test_s127_utf8_tail_never_splits_codepoints() -> None:
    text = "é" * 100  # 2 bytes each
    tail = _utf8_tail(text, 11)  # odd budget cannot end mid-codepoint
    assert tail.endswith("é") and len(tail.encode("utf-8")) <= 11


def test_s127_executor_and_tools_retention_lockstep() -> None:
    """The executor cap must equal the tools retention target (else the pty
    path would double-trim or deliver a head-biased slice)."""
    assert pty_pool._EXEC_RETAINED_BYTES == _RETAINED_TAIL_BYTES


def test_s127_tail_frame_matrix() -> None:
    """C0 frame: stderr LAST, stdout evicted at max 25%, reserve honored."""
    env = {"stdout": "S" * 40_000, "stderr": "E" * 8_000, "returncode": 0, "truncated": True}
    frame = _bash_tail_frame(env, DEFAULT_TOOL_CONTEXT_BYTES)
    assert frame.startswith("[cmd out — TRUNCATED: showing last")
    assert "[stderr — last" in frame
    assert frame.endswith("E" * 100), "stderr must be the frame's LAST bytes"
    assert "S" * 1000 in frame, "stdout tail must survive a large stderr"
    assert len(frame.encode("utf-8")) <= DEFAULT_TOOL_CONTEXT_BYTES - _BASH_FRAME_RESERVE + 10

    # giant stderr cannot evict stdout (stderr capped at usable//4)
    hostile = {"stdout": "S" * 40_000, "stderr": "E" * 200_000, "returncode": 1}
    frame2 = _bash_tail_frame(hostile, DEFAULT_TOOL_CONTEXT_BYTES)
    assert "S" * 500 in frame2 and frame2.endswith("E" * 100)

    # no stderr -> no block; non-Mapping -> str()
    quiet = {"stdout": "S" * 40_000, "stderr": "", "returncode": 0}
    frame3 = _bash_tail_frame(quiet, DEFAULT_TOOL_CONTEXT_BYTES)
    assert "[stderr" not in frame3 and frame3.endswith("S" * 100)
    assert _bash_tail_frame("not-a-mapping", 1000) == "not-a-mapping"

    # tiny budget still yields a header (never an empty string)
    tiny = _bash_tail_frame(quiet, 300)
    assert tiny.startswith("[cmd out")


# ---------------------------------------------------------------------------
# C1 — projection: over-ceiling envelope framed once, stderr last, no mutilation
# ---------------------------------------------------------------------------


def _synthetic_envelope() -> dict[str, object]:
    return {
        "returncode": 0,
        "stdout": "S" * 40_000,  # 40k: the FRAME itself must sit near the ceiling (clip-mutation oracle)
        "stderr": "E" * 13_500,  # rendered envelope ~33.6kB > ceiling -> elider path
        "truncated": False,
        "artifact_id": None,
    }


def test_s127_projection_frames_over_ceiling_envelope(tmp_path: Path) -> None:
    """The elider is reachable and correct: envelope with big stdout+stderr
    renders over the ceiling -> tail frame + artifact footer, stderr LAST,
    custom frame NOT mutilated by the clip (CT5)."""
    tool = build_run_bash_tool(tmp_path)
    store = ArtifactStore(tmp_path / "artifacts")
    projected = project_for_model(tool, ToolResult.ok("bash exited 0", result=_synthetic_envelope()), store)

    assert "[artifact: tool-result-" in projected
    body = projected.rsplit("\n\n[artifact: tool-result-", 1)[0]
    assert body.split("\n\n", 1)[1].startswith("[cmd out — TRUNCATED")
    assert body.endswith("E" * 100), "stderr must be the visible frame's last bytes"
    # mutation-hardening (CT5): a shrunken clip inside the E-tail must be
    # visible — the frame carries the FULL stderr budget (usable//4 = 8160B).
    assert "E" * 8_000 in body, "stderr tail was clipped short (frame mutilated)"
    assert "S" * 500 in body
    assert len(projected.encode("utf-8")) <= DEFAULT_TOOL_CONTEXT_BYTES + 200  # summary+footer slack
    # the artifact holds the full raw envelope (audit superset)
    import re

    artifact_id = re.findall(r"tool-result-[0-9a-f]{16}", projected)[-1]
    assert store.get(artifact_id) is not None and store.get(artifact_id)["stderr"] == "E" * 13_500


def test_s127_ct5_overshooting_elider_is_observable_not_silent(tmp_path: Path, caplog) -> None:
    """CT5 guard: a custom elider that overshoots gets clipped (runtime
    safety) AND the violation is WARNING-observable; a correct elider never
    triggers the warning."""

    def bad_elider(value: object, _max_bytes: int) -> str:  # contract violation
        return "z" * 40_000

    def good_elider(value: object, max_bytes: int) -> str:
        return "z" * (max_bytes - _BASH_FRAME_RESERVE)

    from collections.abc import Mapping

    from fa.inner_loop.registry import ToolSpec

    def handler(_params: Mapping[str, object]) -> ToolResult:
        return ToolResult.ok("x")

    big = "x" * 40_000
    for elider, expect_warning in ((bad_elider, True), (good_elider, False)):
        spec = ToolSpec(
            name="demo.tool",
            description="Demo.",
            input_schema={"type": "object"},
            permission="read",
            handler=handler,
            elide=elider,
        )
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="fa.inner_loop.projection"):
            store = ArtifactStore(tmp_path / f"a{int(expect_warning)}")
            projected = project_for_model(spec, ToolResult.ok("s", result=big), store)
        warned = any("overshot" in r.message for r in caplog.records)
        assert warned is expect_warning, f"warning observed={warned}, expected {expect_warning}"
        assert len(projected.encode("utf-8")) <= 32_768 + 200
    assert len(good_elider(None, DEFAULT_TOOL_CONTEXT_BYTES))  # static sanity


# ---------------------------------------------------------------------------
# C1 — live handler (POSIX shell): retention + artifact + inline envelope
# ---------------------------------------------------------------------------


@requires_posix_shell
def test_run_bash_tail_retention_and_inline_envelope(tmp_path: Path) -> None:
    """root=build_run_bash_tool (composition root) claim (CT4, rewritten from
    the 500+200-head-preview pinner): >30k stdout is retained TAIL-biased,
    the FULL executor-delivered output goes to the artifact, the envelope
    renders INLINE under the ceiling (no projection elision, no double
    frame), and the artifact_id field makes it followable (S3).

    kill-check: revert _retained_stdout to a head preview (or the executor
    cap to [:8000]) — the tail-marker assertions fail.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    log = EventLog(tmp_path / "events.jsonl", run_id="bash-tail")
    state = SessionState(workspace_root=workspace, run_id="bash-tail", log=log)
    state.artifact_store = ArtifactStore(tmp_path / "fa-artifacts")
    tool = build_run_bash_tool(workspace)

    token = set_current_session(state)
    try:
        result = tool.handler({"command": _large_output_command(40_000)})
    finally:
        reset_current_session(token)
    assert result.error is None, f"command failed: {result.error}"
    env = result.result

    assert env["truncated"] is True
    stdout = str(env["stdout"])
    assert stdout.endswith(_TAIL_MARKER), "retained stdout must be the TAIL"
    assert _HEAD_MARKER not in stdout, "retained stdout must drop the head"
    assert len(stdout) <= _RETAINED_TAIL_BYTES + 10

    artifact_id = env["artifact_id"]
    assert artifact_id, "trimmed stdout must produce an artifact (followable via S3)"
    stored = state.artifact_store.get(artifact_id)
    assert stored is not None and str(stored).endswith(_TAIL_MARKER)

    # The envelope renders under the ceiling: INLINE, no second frame, no
    # projection artifact — exactly one framing layer (CT5).
    projected = project_for_model(tool, result, ArtifactStore(tmp_path / "proj-artifacts"))
    assert "[artifact:" not in projected, "inline envelope must not be re-elided"
    assert "TRUNCATED: showing last" not in projected
    assert len(projected.encode("utf-8")) <= DEFAULT_TOOL_CONTEXT_BYTES + 200
    assert _TAIL_MARKER in projected


@requires_posix_shell
def test_run_bash_small_output_untouched(tmp_path: Path) -> None:
    """Matrix complement: small output stays whole, unflagged, artifactless."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tool = build_run_bash_tool(workspace)
    result = tool.handler({"command": "echo short-output"})
    assert result.error is None, f"command failed: {result.error}"
    assert result.result["truncated"] is False
    assert result.result["artifact_id"] is None
    assert "short-output" in str(result.result["stdout"])
