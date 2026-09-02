"""C1 composition-root kill-check: fs_run_bash elide-callable regression (S12.7 rewrite).

History (kept): PR #58's pylint-dedup wired ``elide=truncate_for_preview``
directly; ``ToolElider`` is ``Callable[[value, max_context_bytes], str]``
called POSITIONALLY, so the budget bound to ``preview_len`` — an oversized
marker-less preview. That regression class (adapter-protocol mismatch) is
why the elide seam keeps a live composition-root test.

S12.7 (CT4) moved the contract: the handler retains stdout TAIL-biased at
30k (full executor-delivered output to the artifact), and the elider is
``_bash_tail_frame`` for over-ceiling envelopes. The live retention/
inline/artifact assertions now live in tests/test_s127_bash_frame.py
(test_run_bash_tail_retention_and_inline_envelope); this file keeps the
historical fixture pair — over-budget shape + small-output matrix — under
the NEW contract, at the registered spec (no dataclasses.replace: the
registered budget 32,768 is exercised for real).
"""

from __future__ import annotations

from pathlib import Path

from fa.inner_loop.artifacts import ArtifactStore
from fa.inner_loop.projection import project_for_model
from fa.inner_loop.tools.run_bash import build_run_bash_tool
from tests._capabilities import requires_posix_shell

_HEAD_MARKER = "HEADMARK"
_TAIL_MARKER = "TAILMARK"


def _large_output_command(filler_len: int) -> str:
    return f"python3 -c \"print('{_HEAD_MARKER}' + 'x' * {filler_len} + '{_TAIL_MARKER}')\""


@requires_posix_shell
def test_run_bash_over_budget_output_keeps_tail_shape(tmp_path: Path) -> None:
    """root=build_run_bash_tool (composition root) claim (CT4): over-budget
    stdout is retained tail-biased and renders INLINE with the artifact_id
    pointer — head dropped, tail kept, no projection re-elision (one framing
    layer). Detailed assertions: tests/test_s127_bash_frame.py."""

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifact_store = ArtifactStore(tmp_path / "artifacts")
    tool = build_run_bash_tool(workspace)

    result = tool.handler({"command": _large_output_command(40_000)})
    assert result.error is None, f"command failed: {result.error}"
    env = result.result
    assert env["truncated"] is True
    assert str(env["stdout"]).endswith(_TAIL_MARKER)
    assert _HEAD_MARKER not in str(env["stdout"])

    rendered = project_for_model(tool, result, artifact_store)
    assert "[artifact:" not in rendered, "retained envelope renders inline"
    assert "TRUNCATED: showing last" not in rendered, "no double frame at the registered budget"
    assert _TAIL_MARKER in rendered
    assert len(rendered.encode("utf-8")) <= 32_768 + 200


@requires_posix_shell
def test_run_bash_elide_leaves_small_output_untouched(tmp_path: Path) -> None:
    """Matrix complement: output under the retention target is NOT trimmed —
    no truncation flag, whole stdout, artifactless."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifact_store = ArtifactStore(tmp_path / "artifacts")
    tool = build_run_bash_tool(workspace)

    result = tool.handler({"command": "echo short-output"})
    assert result.error is None, f"command failed: {result.error}"

    rendered = project_for_model(tool, result, artifact_store)
    assert "short-output" in rendered
    assert result.result["truncated"] is False
    assert "[artifact: tool-result-" not in rendered
