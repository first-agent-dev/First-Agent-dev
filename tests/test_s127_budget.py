"""S12.7 (CT2/GAP4) — tool context budget ceiling: constant, boundary, scatter.

Conventions per knowledge/skills/tests-writing: pyramid C0p (property/offline).

The ceiling single-source is ``DEFAULT_TOOL_CONTEXT_BYTES`` in
``fa.inner_loop.registry`` (defined beside ``ToolSpec`` — a module-scope
import from ``runtime_limits`` would close the cycle
registry → runtime_limits → recovery → registry, verified S12.7 R14).
The per-tool scatter TABLE (tool, value, reason) lives in
``runtime_limits.py``'s docstring; test_s127_scatter_table_matches_registry
keeps the table and the code from rotting apart.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fa.inner_loop import runtime_limits as runtime_limits_module
from fa.inner_loop.artifacts import ArtifactStore
from fa.inner_loop.projection import project_for_model
from fa.inner_loop.registry import DEFAULT_TOOL_CONTEXT_BYTES, ToolResult, ToolSpec
from fa.inner_loop.tools import build_baseline_registry


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


# ---------------------------------------------------------------------------
# T-budget — the ceiling and the exact elision boundary
# ---------------------------------------------------------------------------


def test_s127_ceiling_constant_is_32768_and_is_the_tool_spec_default() -> None:
    """Absolute anchor (CT2 kill-check: lower the constant → this fails).

    32_768 is not arbitrary: src/ .py fit@32KB = 149/160 = 93.1% at
    @612400c, so in-ceiling results stay inline (RD-1: full raw inline
    always) and only true oversize payloads pay the artifact round-trip.
    """
    assert DEFAULT_TOOL_CONTEXT_BYTES == 32_768
    assert _spec().max_context_bytes == DEFAULT_TOOL_CONTEXT_BYTES, (
        "ToolSpec default must BE the imported constant, not a re-typed literal"
    )


def test_s127_budget_boundary_exact(tmp_path: Path) -> None:
    """root=project_for_model matrix=A claim=elide iff payload > budget.

    At exactly 32,768 payload bytes → inline, NO artifact. At 32,769 →
    elided + artifact reference, and the elided block itself stays within
    the budget (default_head_tail clips to max_bytes).
    """
    store = ArtifactStore(Path("/tmp/s127-budget-boundary/artifacts"))
    spec = _spec(max_context_bytes=DEFAULT_TOOL_CONTEXT_BYTES)

    at_budget = project_for_model(spec, ToolResult.ok("sum", result="x" * DEFAULT_TOOL_CONTEXT_BYTES), store)
    assert "[artifact:" not in at_budget, "payload == budget must stay inline (boundary is >, not >=)"
    assert "x" * 32_768 in at_budget

    over_budget = project_for_model(spec, ToolResult.ok("sum", result="x" * (DEFAULT_TOOL_CONTEXT_BYTES + 1)), store)
    assert "[artifact:" in over_budget, "payload == budget+1 must elide (boundary is >, not >=)"


# ---------------------------------------------------------------------------
# T-elision-edge — the boundary property across ALL registered spec values
# ---------------------------------------------------------------------------


def test_s127_elision_edge_property_across_registered_specs(tmp_path: Path) -> None:
    """C0p property, spec values READ FROM SOURCE (the live baseline registry):

    for every registered spec with ``max_context_bytes > 0``:
      - payload of exactly ``max_context_bytes`` ASCII bytes → inline, no artifact;
      - payload of ``max_context_bytes + 1`` bytes → elided + artifact reference.

    ASCII strings render byte-for-byte (``render_tool_payload`` passes str
    through), so payload lengths are exact byte lengths.
    """
    registry = build_baseline_registry(tmp_path)
    specs = sorted(registry.specs(), key=lambda s: s.name)
    assert len(specs) >= 15, f"baseline registry unexpectedly small: {[s.name for s in specs]}"

    for spec in specs:
        budget = spec.max_context_bytes
        assert budget > 0, f"{spec.name}: zero/negative budget not expected in the baseline set"
        store = ArtifactStore(tmp_path / "artifacts" / spec.name)

        at_budget = project_for_model(spec, ToolResult.ok("sum", result="x" * budget), store)
        assert "[artifact:" not in at_budget, f"{spec.name}: payload == budget ({budget}) must stay inline"

        over_budget = project_for_model(spec, ToolResult.ok("sum", result="x" * (budget + 1)), store)
        assert "[artifact:" in over_budget, (
            f"{spec.name}: payload == budget+1 ({budget + 1}) must elide with an artifact reference"
        )


# ---------------------------------------------------------------------------
# Scatter-table pin — the docstring table and the registry cannot rot apart
# ---------------------------------------------------------------------------

_EXPECTED_SCATTER: dict[str, int] = {
    # ceiling tier (S12.7 CT2/GAP4)
    "fs_read_file": 32_768,
    "fs_write_file": 32_768,
    "fs_spawn_subagent": 32_768,
    "fs_exploration_metrics": 32_768,
    "fs_search": 32_768,
    "fs_reach": 32_768,
    "fs_run_bash": 32_768,
    # deliberate small outliers (kept, with reason — see runtime_limits docstring)
    "fs_edit_file": 4_000,
    "fs_chronicle_search": 4_000,
    "fs_diff": 4_000,
    "fs_blackboard_query": 2_048,
    "fs_usage": 2_000,
    "fs_list_tasks": 2_000,
    "fs_checkpoint": 1_000,
    "fs_undo": 1_000,
    "fs_send_ctrl_c": 1_000,
}


def test_s127_scatter_table_matches_registry(tmp_path: Path) -> None:
    """Anti-rot pin: the live registry equals the documented scatter EXACTLY,
    and every tool appears in runtime_limits' docstring table.

    kill-checks: reverting any spec site (fs_search→30_000, run_bash→8000,
    registry default→4096) or editing a tool's budget without updating the
    table fails here.
    """
    registry = build_baseline_registry(tmp_path)
    actual = {spec.name: spec.max_context_bytes for spec in registry.specs()}
    assert actual == _EXPECTED_SCATTER, (
        f"registry scatter drifted from the documented table; diff: "
        f"{ {k: (actual.get(k), v) for k, v in _EXPECTED_SCATTER.items() if actual.get(k) != v} }"
    )

    doc = runtime_limits_module.__doc__ or ""
    for name in _EXPECTED_SCATTER:
        assert name in doc, f"{name} missing from the runtime_limits budget table (docstring rot)"
