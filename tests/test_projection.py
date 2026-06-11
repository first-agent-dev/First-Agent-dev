from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fa.inner_loop.artifacts import ArtifactStore
from fa.inner_loop.projection import project_for_model
from fa.inner_loop.registry import ToolResult, ToolSpec


def _handler(_params: Mapping[str, object]) -> ToolResult:
    return ToolResult.ok("unused")


def _spec(**kwargs: Any) -> ToolSpec:
    return ToolSpec(
        name="demo.tool",
        description="Demo tool.",
        input_schema={"type": "object"},
        permission="read",
        handler=_handler,
        **kwargs,
    )


def test_project_for_model_includes_payload_when_under_budget(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    projected = project_for_model(
        _spec(max_context_bytes=4096),
        ToolResult.ok("read demo", result={"content": "hello"}),
        store,
    )

    assert projected.startswith("read demo\n\n")
    assert '"content": "hello"' in projected
    assert not (tmp_path / "artifacts").exists()


def test_project_for_model_elides_and_writes_artifact_when_over_budget(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    projected = project_for_model(
        _spec(max_context_bytes=20),
        ToolResult.ok("read demo", result="abcdefghijklmnopqrstuvwxyz" * 10),
        store,
    )

    assert projected.startswith("read demo\n\n")
    assert "[artifact: tool-result-" in projected
    artifacts = list((tmp_path / "artifacts").glob("tool-result-*.json"))
    assert len(artifacts) == 1
    assert "abcdefghijklmnopqrstuvwxyz" in artifacts[0].read_text(encoding="utf-8")


def test_project_for_model_clips_errors_without_artifact(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    projected = project_for_model(
        _spec(max_context_bytes=20),
        ToolResult.fail("internal_error", "x" * 700),
        store,
    )

    assert projected == f"ERROR[internal_error]: {'x' * 500}"
    assert not (tmp_path / "artifacts").exists()
