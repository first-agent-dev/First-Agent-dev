"""
Tests for Minimal Structured Telemetry + Governed Mutation Foundation
Phase 0.5 — Not 100k raw logs, but structured summaries + artifact_id
"""

import json
import tempfile
from pathlib import Path


def test_telemetry_structured_fields():
    from fa.telemetry.telemetry import TelemetryEvent, TelemetryLogger

    with tempfile.TemporaryDirectory() as tmp:
        logger = TelemetryLogger(Path(tmp) / "telemetry")

        event = TelemetryEvent(
            run_id="test-run-1",
            turn=1,
            prompt_tokens=1000,
            completion_tokens=200,
            cost_usd=0.01,
            model_id="claude-opus-4",
            tool_name="fs.read_file",
            tool_args={"path": "src/auth.py"},
            permission_tier="read",
            edited_files=[],
            test_result="PASS",
            cache_hit=True,
            latency_ms=100,
            branch_decision="choose grep over read 10 files",
            rejected_alternatives=["read 10 files"],
            human_approval=None,
            artifact_id="tool-result-abc123",
        )

        logger.log(event)

        # Read back
        queried = logger.query(tool_name="fs.read_file")
        assert len(queried) == 1
        assert queried[0].run_id == "test-run-1"
        assert queried[0].artifact_id == "tool-result-abc123"
        # Check structured fields present, not raw logs
        assert queried[0].prompt_tokens == 1000
        assert queried[0].cache_hit is True


def test_telemetry_no_raw_logs_drowning():
    from fa.telemetry.telemetry import TelemetryEvent, TelemetryLogger

    with tempfile.TemporaryDirectory() as tmp:
        logger = TelemetryLogger(Path(tmp) / "telemetry")

        # Simulate tool output that would be 100k raw logs if not offloaded
        large_output = "x" * 100000

        event = TelemetryEvent(
            run_id="test-run-2",
            turn=2,
            prompt_tokens=5000,
            completion_tokens=1000,
            cost_usd=0.05,
            model_id="gpt-5",
            tool_name="fs.run_bash",
            tool_args={"command": "cat large_file.txt"},
            permission_tier="workspace",
            edited_files=[],
            test_result="PASS",
            cache_hit=False,
            latency_ms=500,
            branch_decision="",
            rejected_alternatives=[],
            human_approval=None,
            artifact_id="artifact-large-output-id",  # Reference to full output offloaded to ArtifactStore, not raw log
        )

        logger.log(event)

        # Check file size <1k chars per line, not 100k
        log_path = Path(tmp) / "telemetry" / "telemetry.jsonl"
        lines = log_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        assert len(lines[0]) < 1500, f"Telemetry line should be <1k chars, got {len(lines[0])}"
        # Should contain artifact_id, not raw large_output
        assert "artifact-large-output-id" in lines[0]
        assert large_output not in lines[0]


def test_telemetry_sanitizes_secrets():
    from fa.telemetry.telemetry import TelemetryEvent, TelemetryLogger

    with tempfile.TemporaryDirectory() as tmp:
        logger = TelemetryLogger(Path(tmp) / "telemetry")

        event = TelemetryEvent(
            run_id="test-run-3",
            turn=1,
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.001,
            model_id="test",
            tool_name="fs.run_bash",
            tool_args={"command": "echo $API_KEY", "api_key": "sk-secret123"},
            permission_tier="workspace",
            edited_files=[],
            test_result="PASS",
            cache_hit=False,
            latency_ms=10,
            branch_decision="",
            rejected_alternatives=[],
            human_approval=None,
            artifact_id=None,
        )

        logger.log(event)

        queried = logger.query()
        # Secret should be redacted
        assert "***REDACTED***" in json.dumps(queried[0].tool_args) or "sk-secret123" not in json.dumps(
            queried[0].tool_args
        )
