"""
Unit tests for ADR-17 Context Management & Compaction.
Verifies ContextBudget, PinnedBuffer, ObservationMasker, and FullLLMCompactor.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from fa.inner_loop.compaction.compactor import FullLLMCompactor, ObservationMasker
from fa.inner_loop.state import TraceEvent
from fa.memory.context_budget import ContextBudget
from fa.memory.pinned_buffer import PinnedBuffer


def test_context_budget_gates() -> None:
    # 1. Test thresholds: Limit = 100k
    budget = ContextBudget(limit_tokens=100000)
    assert budget.threshold == 80000  # 80% of 100k, as 80k < 150k

    # Below 70% -> allow
    res = budget.check(current_tokens=50000)
    assert res["action"] == "allow"
    assert "healthy" in res["message"]

    # 70% to 90% -> warn
    res = budget.check(current_tokens=75000)
    assert res["action"] == "warn"
    assert "warning" in res["message"]

    # 90%+ -> require_compaction
    res = budget.check(current_tokens=95000)
    assert res["action"] == "require_compaction"
    assert "CRITICAL" in res["message"]


def test_context_budget_dynamic_fallback() -> None:
    # 2. Test dynamic threshold limit: Limit = 300k
    budget = ContextBudget(limit_tokens=300000)
    assert budget.threshold == 150000  # min(80% of 300k=240k, 150k) -> 150k


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
    # Write synthetic constraints
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
            tool_name="fs.read_file",
            tool_call_id="tc-1",
            content={"params": {"path": "large.py"}},
        ),
        TraceEvent(
            event_id="ev-002",
            ts="2026-07-14",
            run_id="run-1",
            actor="tool",
            kind="tool_result",
            tool_name="fs.read_file",
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
            tool_name="fs.run_bash",
            tool_call_id="tc-2",
            content={"params": {"command": "test"}},
        ),
        TraceEvent(
            event_id="ev-004",
            ts="2026-07-14",
            run_id="run-1",
            actor="tool",
            kind="tool_result",
            tool_name="fs.run_bash",
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
    assert "Omitted tool result" in masked[1].content["summary"]
    assert masked[1].content["artifact_id"] is None

    # Turn 2 tool result remains verbatim (recent window)
    assert masked[3].content["result"]["stdout"].startswith("success")


def test_full_llm_compactor_fallback_truncate() -> None:
    compactor = FullLLMCompactor(compactor_chain=None)
    long_text = "\n".join([f"Line {i}" for i in range(150)])

    summary = compactor.compact(long_text)
    assert "PREVIOUSLY" in summary
    assert "Local Fallback Truncation" in summary
    assert "CURRENT" in summary
    assert "NEXT ACTION" in summary


def test_full_llm_compactor_calls_chain_success() -> None:
    mock_chain = MagicMock()
    mock_response = MagicMock()
    mock_response.text = (
        "## PREVIOUSLY\nAnalyzed repo.\n\n## PARKED\nNone.\n\n"
        "## CURRENT\nTask ongoing.\n\n## NEXT ACTION\nRun pytest."
    )
    mock_chain.request.return_value = (mock_response, "call-123", [])

    compactor = FullLLMCompactor(compactor_chain=mock_chain)
    summary = compactor.compact("History content")

    assert "PREVIOUSLY" in summary
    assert "Analyzed repo" in summary
    assert "NEXT ACTION" in summary
    assert "Run pytest" in summary


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

    total = estimate_tokens(messages, tools_schema={"name": "schema"})
    assert total > 0
