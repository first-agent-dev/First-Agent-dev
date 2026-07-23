"""C1 composition-root kill-check: fs.run_bash elide-callable regression.

Context (regression history): PR #58's pylint-dedup follow-up commit
removed the ``_elide_500_preview`` wrapper in both ``run_bash.py`` files
and wired ``elide=truncate_for_preview`` directly. ``ToolElider`` is
``Callable[[value, max_context_bytes], str]`` and the projection layer
calls it POSITIONALLY (``elider(result.result, spec.max_context_bytes)``).
``truncate_for_preview``'s own second positional parameter is
``preview_len`` — so the tool's ``max_context_bytes`` (8000) was silently
bound to ``preview_len`` instead of the fixed 500 the feature promises,
producing an oversized preview with no tail and no truncation notice.

Neither mypy strict nor pyrefly catches this: ``Callable[[Any, int], str]``
is a purely positional-arity/type contract and cannot express "the second
argument must mean max_bytes, not preview_len". Only a live composition-root
test that renders the actual model-visible string catches it.
"""

from __future__ import annotations

from pathlib import Path

from fa.inner_loop.artifacts import ArtifactStore
from fa.inner_loop.projection import project_for_model
from fa.inner_loop.tools.run_bash import build_run_bash_tool

_HEAD_MARKER = "HEAD_MARKER"
_TAIL_MARKER = "TAIL_MARKER"


def _large_output_command(filler_len: int) -> str:
    """A command whose stdout embeds head/tail markers around ``filler_len`` filler chars."""
    return f"python3 -c \"print('{_HEAD_MARKER}' + 'x' * {filler_len} + '{_TAIL_MARKER}')\""


def test_run_bash_elide_preserves_fixed_preview_shape_over_budget(tmp_path: Path) -> None:
    """root=build_run_bash_tool (composition root: real ToolSpec.elide wiring)

    claim: fs.run_bash previews large stdout as a FIXED 500+200-char shape
    with a truncation notice, regardless of the tool's max_context_bytes
    budget (8000) — the promise stated in the tool's own description
    ("500-character preview").

    Trigger scenario: stdout at exactly 7999 chars is NOT pre-truncated by
    the tool's own internal >8000 cap (it stays under it), but the
    JSON-serialized result dict (with returncode/stderr/artifact_id/
    session_id/truncated fields added) exceeds max_context_bytes=8000 due
    to serialization overhead. This is precisely the scenario where
    projection.py's ``elider = spec.elide or default_head_tail`` fires —
    proven empirically: encode(json_dump({"stdout": "H"*7999, ...})) is
    8097 bytes, 97 over budget.

    kill-check: removing the ``_bash_run_elide`` adapter and wiring
    ``elide=truncate_for_preview`` directly (the shipped regression) makes
    this test fail — the rendered length balloons toward max_context_bytes
    and the tail marker + truncation notice are lost.

    oracle: the actual model-visible string returned by project_for_model
    (the real composition-root chokepoint between ToolResult and the LLM
    message stream — see projection.py's own docstring).

    path-inventory: path 1 of 2 (subprocess fallback path, no PtyPool
    session active in a bare test process — _resolve_execution_context
    returns executor=None so build_run_bash_tool's handler falls through
    to _run_subprocess_fallback).
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifact_store = ArtifactStore(tmp_path / "artifacts")
    tool = build_run_bash_tool(workspace)

    filler_len = 7999 - len(_HEAD_MARKER) - len(_TAIL_MARKER)
    result = tool.handler({"command": _large_output_command(filler_len)})
    assert result.error is None, f"command failed: {result.error}"
    assert result.result is not None
    raw_stdout_len = len(str(result.result["stdout"]))
    assert raw_stdout_len <= 8000, (
        f"fixture stdout ({raw_stdout_len} chars) must stay under the tool's own "
        "internal >8000 pre-truncation cap so spec.elide is what's under test, "
        "not the internal preview_stdout branch"
    )

    rendered = project_for_model(tool, result, artifact_store)

    # The fixed-shape preview must stay far under the tool's max_context_bytes
    # (8000); the regression produced a rendering close to that budget.
    assert len(rendered) < 2000, (
        f"rendered length {len(rendered)} suggests max_context_bytes leaked "
        "into the preview length (elide-callable regression)"
    )
    assert _HEAD_MARKER in rendered
    assert _TAIL_MARKER in rendered, "tail marker missing: preview lost its 200-char tail"
    assert "...[truncated" in rendered, "truncation notice missing from preview"
    assert "[artifact: tool-result-" in rendered, "full output must still be recoverable via artifact"


def test_run_bash_elide_leaves_small_output_untouched(tmp_path: Path) -> None:
    """root=build_run_bash_tool matrix=B (small output, no truncation needed)

    claim: output under the fixed preview_len (500 chars) is NOT elided —
    the elide-callable is a no-op below its own threshold. Matrix
    complement to the over-budget case above (two combos: over/under the
    fixed preview length, per tests-writing skill matrix coverage gate).
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifact_store = ArtifactStore(tmp_path / "artifacts")
    tool = build_run_bash_tool(workspace)

    result = tool.handler({"command": "echo short-output"})
    assert result.error is None, f"command failed: {result.error}"

    rendered = project_for_model(tool, result, artifact_store)

    assert "short-output" in rendered
    assert "...[truncated" not in rendered
    assert "[artifact: tool-result-" not in rendered
