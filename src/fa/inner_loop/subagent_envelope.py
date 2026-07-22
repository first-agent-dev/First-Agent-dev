"""
SubagentEnvelope — structured JSON envelope for subagents, full schema.
Phase 1 Foundation: extracted from subagent_runner.py for clean foundation.

Prior art:
- OpenAI Sandbox Agents as Tools custom_output_extractor JSON
- Copilot CustomAgents isolated context
- LangChain subagents pattern supervisor maintains context, subagents stateless isolated

Validator cached at module load via fastjsonschema.compile (not per call).
Artifact write .fa/subagents/<id>.json per task completion.

Cheap deterministic use cases (Pair over Autonomy):
- researcher: structured websearch, input query, output {urls, snippets, summary} <500 tokens prompt
- verifier: simple function, input spec, output {file_path, test_result}
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import fastjsonschema  # type: ignore[import-untyped]

# Full schema chosen in Q&A: Goal, Verification, Risks
SUBAGENT_ENVELOPE_SCHEMA = {
    "type": "object",
    "required": ["task_id", "type", "goal", "exit_code", "summary", "verification"],
    "properties": {
        "task_id": {"type": "string"},
        "type": {
            "type": "string",
            "enum": ["researcher", "verifier", "code-reviewer", "implementer", "planner"],
        },
        "goal": {"type": "string"},
        "exit_code": {"type": "integer"},
        "summary": {"type": "string"},
        "verification": {"type": "string"},
        "files_changed": {"type": "array", "items": {"type": "string"}},
        "patch_diff": {"type": "string"},
        "risks": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "token_usage": {"type": "object"},
        "duration_ms": {"type": "integer"},
        "next_action": {"type": "string", "enum": ["none", "needs-human", "retry"]},
    },
}

# Cached validator at module load, not per call (token + time efficient)
validate_envelope = fastjsonschema.compile(SUBAGENT_ENVELOPE_SCHEMA)


@dataclass
class SubagentEnvelope:
    task_id: str
    type: str
    goal: str
    exit_code: int
    summary: str
    verification: str
    files_changed: list[str]
    patch_diff: str
    risks: list[str]
    open_questions: list[str]
    token_usage: dict[str, Any]
    duration_ms: int
    next_action: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @classmethod
    def from_verifier(
        cls, task_id: str, exit_code: int, stdout: str, duration_ms: int = 0, role: str = "verifier"
    ) -> SubagentEnvelope:
        passed = exit_code == 0
        # role is preserved as envelope type — both researcher and verifier run bash (stateless),
        # but type must reflect caller role (D10 role-bounded)
        envelope_type = (
            role
            if role in {"researcher", "verifier", "code-reviewer", "implementer", "planner"}
            else "verifier"
        )
        # Researcher summary should surface the actual output (source summary) for observability,
        # while verifier keeps PASS/FAIL short.
        if envelope_type == "researcher":
            summary = stdout[:500] if passed else f"FAIL: {stdout[:200]}"
            goal = f"Research {task_id}"
        else:
            summary = "PASS" if passed else f"FAIL: {stdout[:200]}"
            goal = f"Verify {task_id}"
        return cls(
            task_id=task_id,
            type=envelope_type,
            goal=goal,
            exit_code=exit_code,
            summary=summary,
            verification=f"exit_code={exit_code}",
            files_changed=[],
            patch_diff="",
            risks=[] if passed else ["test failure"],
            open_questions=[],
            token_usage={},
            duration_ms=duration_ms,
            next_action="none" if passed else "needs-human",
        )

    @classmethod
    def from_researcher(
        cls,
        task_id: str,
        query: str,
        urls: list[str],
        snippets: list[str],
        summary: str,
        duration_ms: int = 0,
    ) -> SubagentEnvelope:
        """Cheap deterministic researcher: structured websearch <500 tokens prompt."""
        return cls(
            task_id=task_id,
            type="researcher",
            goal=f"Research {query}",
            exit_code=0,
            summary=summary[:500],
            verification=f"found {len(urls)} urls",
            files_changed=[],
            patch_diff="",
            risks=[],
            open_questions=[],
            token_usage={"urls": len(urls), "snippets": len(snippets)},
            duration_ms=duration_ms,
            next_action="none",
        )


def write_envelope_artifact(envelope: SubagentEnvelope, session_root: Path) -> Path:
    """Write artifact .fa/subagents/<id>.json per task completion (Q&A)."""
    artifact_path = Path(session_root).resolve() / ".fa" / "subagents" / f"{envelope.task_id}.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(envelope.to_json(), encoding="utf-8")
    return artifact_path


__all__ = [
    "SUBAGENT_ENVELOPE_SCHEMA",
    "SubagentEnvelope",
    "validate_envelope",
    "write_envelope_artifact",
]
