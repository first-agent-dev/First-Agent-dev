"""
Unit tests for ADR-17 Context Management & Compaction.
Verifies ContextBudget, PinnedBuffer, ObservationMasker, and FullLLMCompactor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

from fa.inner_loop.artifacts import ArtifactStore
from fa.inner_loop.compaction.compactor import FullLLMCompactor, ObservationMasker, project_messages_after_mask
from fa.inner_loop.state import TraceEvent
from fa.memory.context_budget import ContextBudget
from fa.memory.pinned_buffer import PinnedBuffer


def test_context_budget_gates() -> None:
    budget = ContextBudget(limit_tokens=100000)
    assert budget.threshold == 80000
    assert budget.stage2_threshold == 80000
    assert budget.stage3_threshold == 90000

    res = budget.check(current_tokens=50000)
    assert res["action"] == "allow"
    assert "healthy" in res["message"]

    res = budget.check(current_tokens=75000)
    assert res["action"] == "warn"
    assert "warning" in res["message"]

    res = budget.check(current_tokens=85000)
    assert res["action"] == "stage2"
    assert "Stage 2" in res["message"]

    res = budget.check(current_tokens=95000)
    assert res["action"] == "stage3"
    assert "Stage 3" in res["message"]


def test_context_budget_dynamic_fallback() -> None:
    budget = ContextBudget(limit_tokens=300000)
    assert budget.threshold == 150000
    assert budget.stage2_threshold == 150000
    assert budget.stage3_threshold == 270000


def test_context_budget_uses_threshold_for_gate_and_warns_before_it() -> None:
    budget = ContextBudget(limit_tokens=300000)

    warn = budget.check(current_tokens=140000)
    assert warn["action"] == "warn"
    assert warn["threshold"] == 150000
    assert warn["warning_threshold"] == 131250

    stage2 = budget.check(current_tokens=150000)
    assert stage2["action"] == "stage2"
    assert "150000 tokens" in stage2["message"]

    stage3 = budget.check(current_tokens=270000)
    assert stage3["action"] == "stage3"
    assert "270000 tokens" in stage3["message"]


def test_context_budget_circuit_breaker() -> None:
    budget = ContextBudget(limit_tokens=100000)

    # 1st attempt: 100k -> 95k (5% reclaimed, <10%)
    ok = budget.record_compaction_attempt(tokens_before=100000, tokens_after=95000)
    assert ok is True
    assert budget.consecutive_compactions == 1

    # 2nd attempt: 95k -> 92k (3% reclaimed, <10%)
    ok = budget.record_compaction_attempt(tokens_before=95000, tokens_after=92000)
    assert ok is True
    assert budget.consecutive_compactions == 2

    # 3rd attempt: 92k -> 91k (1% reclaimed, <10%) -> circuit breaker triggers!
    ok = budget.record_compaction_attempt(tokens_before=92000, tokens_after=91000)
    assert ok is False
    assert budget.consecutive_compactions == 3


def test_pinned_buffer(tmp_path: Path) -> None:
    agents_file = tmp_path / "AGENTS.md"
    agents_file.write_text("Constraint 1: Never leak secrets.\n", encoding="utf-8")
    llms_file = tmp_path / "knowledge" / "llms.txt"
    llms_file.parent.mkdir(parents=True, exist_ok=True)
    llms_file.write_text("Constraint 2: No imports from L0 TCB.\n", encoding="utf-8")

    buffer = PinnedBuffer(tmp_path)
    content = buffer.extract_pinned_content(extra_instructions="Standing guidelines.")

    assert "STANDING PROFILE GUIDELINES" in content
    assert "Standing guidelines" in content
    assert "STANDING CONSTRAINT: AGENTS.md" in content
    assert "Never leak secrets" in content
    assert "STANDING CONSTRAINT: knowledge/llms.txt" in content
    assert "No imports from L0 TCB" in content


def test_pinned_buffer_drops_stale_deleted_files(tmp_path: Path) -> None:
    agents_file = tmp_path / "AGENTS.md"
    agents_file.write_text("Constraint 1: Never leak secrets.\n", encoding="utf-8")

    buffer = PinnedBuffer(tmp_path)
    first = buffer.extract_pinned_content()
    assert "STANDING CONSTRAINT: AGENTS.md" in first

    agents_file.unlink()
    second = buffer.extract_pinned_content()
    assert "STANDING CONSTRAINT: AGENTS.md" not in second


def test_observation_masker_reduces_large_tool_results() -> None:
    masker = ObservationMasker(recent_turns_to_keep=1)

    events = [
        # Turn 1: tool call + large result (outside window, should be masked)
        TraceEvent(
            event_id="ev-001",
            ts="2026-07-14",
            run_id="run-1",
            actor="coder",
            kind="tool_call",
            tool_name="fs_read_file",
            tool_call_id="tc-1",
            content={"params": {"path": "large.py"}},
        ),
        TraceEvent(
            event_id="ev-002",
            ts="2026-07-14",
            run_id="run-1",
            actor="tool",
            kind="tool_result",
            tool_name="fs_read_file",
            tool_call_id="tc-1",
            content={
                "summary": "ok",
                "result": {"stdout": "line 1\n" + "line 2\n" * 50},  # 51 lines, >200 chars
            },
        ),
        # Turn 2: tool call + large result (inside window, should remain FULL verbatim)
        TraceEvent(
            event_id="ev-003",
            ts="2026-07-14",
            run_id="run-1",
            actor="coder",
            kind="tool_call",
            tool_name="fs_run_bash",
            tool_call_id="tc-2",
            content={"params": {"command": "test"}},
        ),
        TraceEvent(
            event_id="ev-004",
            ts="2026-07-14",
            run_id="run-1",
            actor="tool",
            kind="tool_result",
            tool_name="fs_run_bash",
            tool_call_id="tc-2",
            content={
                "summary": "exit=0",
                "result": {"stdout": "success\n" * 50},  # large stdout
            },
        ),
    ]

    masked = masker.mask_history(events)

    assert len(masked) == 4
    # Turn 1 tool result was masked
    assert "Omitted tool result" in str(masked[1].content.get("summary", ""))
    assert masked[1].content.get("artifact_id") is None

    # Turn 2 tool result remains verbatim (recent window)
    result_content = cast(dict[str, Any], masked[3].content.get("result", {}))
    assert str(result_content.get("stdout", "")).startswith("success")


def test_full_llm_compactor_fallback_truncate() -> None:
    compactor = FullLLMCompactor(compactor_chain=None)
    long_text = "\n".join([f"Line {i}" for i in range(150)])

    summary = compactor.compact(long_text)
    assert "PREVIOUSLY" in summary
    assert "PARKED" in summary
    assert "Local Fallback Truncation" in summary
    assert "CURRENT" in summary
    assert "NEXT ACTION" in summary


def test_full_llm_compactor_short_history_fallback_still_has_headers() -> None:
    compactor = FullLLMCompactor(compactor_chain=None)
    summary = compactor.compact("line1\nline2")

    assert "## PREVIOUSLY" in summary
    assert "## PARKED" in summary
    assert "## CURRENT" in summary
    assert "## NEXT ACTION" in summary
    assert "line1" in summary


def test_full_llm_compactor_calls_chain_success() -> None:
    mock_chain = MagicMock()
    mock_response = MagicMock()
    mock_response.text = (
        "## PREVIOUSLY\nAnalyzed repo.\n\n## PARKED\nNone.\n\n## CURRENT\nTask ongoing.\n\n## NEXT ACTION\nRun pytest."
    )
    mock_chain.request.return_value = (mock_response, "call-123", [])

    compactor = FullLLMCompactor(compactor_chain=mock_chain)
    summary = compactor.compact("History content")

    assert "PREVIOUSLY" in summary
    assert "Analyzed repo" in summary
    assert "NEXT ACTION" in summary
    assert "Run pytest" in summary


def test_full_llm_compactor_invalid_shape_falls_back() -> None:
    mock_chain = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Free-form summary without the required headings"
    mock_chain.request.return_value = (mock_response, "call-123", [])

    compactor = FullLLMCompactor(compactor_chain=mock_chain)
    summary = compactor.compact("\n".join([f"Line {i}" for i in range(150)]))

    assert "## PREVIOUSLY" in summary
    assert "## PARKED" in summary
    assert "Local Fallback Truncation" in summary


def test_project_messages_after_mask_offloads_to_artifact_store(tmp_path: Path) -> None:
    artifact_store = ArtifactStore(tmp_path / "artifacts")
    messages = [
        {"role": "assistant", "content": "turn 1"},
        {"role": "tool", "tool_call_id": "tc-1", "content": "A" * 500},
        {"role": "assistant", "content": "turn 2"},
        {"role": "tool", "tool_call_id": "tc-2", "content": "short"},
    ]

    projected = project_messages_after_mask(messages, artifact_store=artifact_store, recent_turns_to_keep=1)

    masked = projected[1]
    assert masked["role"] == "tool"
    assert masked["tool_call_id"] == "tc-1"
    assert "artifact_id=tool-result-" in masked["content"]
    stored = list((tmp_path / "artifacts").glob("tool-result-*.json"))
    assert len(stored) == 1
    assert stored[0].read_text(encoding="utf-8").strip().startswith('"AAAA')


def test_estimate_tokens_block_content() -> None:
    from fa.memory.context_budget import estimate_tokens

    messages = [
        {"role": "system", "content": "Static prompt instructions"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "This is a block of text content."},
                {"type": "image", "content": "base64-image-stub"},
            ],
        },
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "tc-1", "type": "function", "function": {"name": "test"}}],
        },
    ]

    typed_messages = cast(list[dict[str, Any]], messages)
    total = estimate_tokens(typed_messages, tools_schema={"name": "schema"})
    assert total > 0
