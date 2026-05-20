from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from fa.inner_loop.registry import ToolCall, ToolResult

DEFAULT_STATE_ROOT = Path.home() / ".fa" / "state" / "runs"
HARNESS_ID = "fa-inner-loop@0.1.0"


def _now_iso_z() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class TraceEvent:
    event_id: str
    timestamp: str
    actor: str
    kind: str
    content: Mapping[str, object] = field(default_factory=dict)
    harness_id: str = HARNESS_ID
    tool_name: str = ""
    tool_call_id: str = ""
    parent_event_id: str = ""


class EventLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._next_id = 1

    def append(
        self,
        *,
        actor: str,
        kind: str,
        content: Mapping[str, object] | None = None,
        tool_name: str = "",
        tool_call_id: str = "",
        parent_event_id: str = "",
    ) -> TraceEvent:
        event = TraceEvent(
            event_id=f"ev-{self._next_id:06d}",
            timestamp=_now_iso_z(),
            actor=actor,
            kind=kind,
            content={} if content is None else dict(content),
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            parent_event_id=parent_event_id,
        )
        self._next_id += 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(asdict(event), ensure_ascii=False, sort_keys=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        return event

    def read_all(self) -> tuple[TraceEvent, ...]:
        if not self.path.exists():
            return ()
        events: list[TraceEvent] = []
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            if not raw:
                continue
            parsed = json.loads(raw)
            events.append(
                TraceEvent(
                    event_id=str(parsed["event_id"]),
                    timestamp=str(parsed["timestamp"]),
                    actor=str(parsed["actor"]),
                    kind=str(parsed["kind"]),
                    content=dict(parsed.get("content", {})),
                    harness_id=str(parsed["harness_id"]),
                    tool_name=str(parsed.get("tool_name", "")),
                    tool_call_id=str(parsed.get("tool_call_id", "")),
                    parent_event_id=str(parsed.get("parent_event_id", "")),
                )
            )
        return tuple(events)


@dataclass
class SessionState:
    workspace_root: Path
    run_id: str = field(default_factory=lambda: f"run-{os.getpid()}")
    max_iterations: int = 6
    log: EventLog | None = None
    observations: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.workspace_root = self.workspace_root.resolve()
        if self.log is None:
            self.log = EventLog(DEFAULT_STATE_ROOT / self.run_id / "events.jsonl")

    def record_tool_call(self, call: ToolCall) -> TraceEvent:
        assert self.log is not None
        return self.log.append(
            actor="coder",
            kind="tool_call",
            content={"params": dict(call.params)},
            tool_name=call.name,
            tool_call_id=call.call_id,
        )

    def record_tool_result(self, call: ToolCall, result: ToolResult) -> TraceEvent:
        assert self.log is not None
        content: dict[str, object] = {
            "summary": result.summary,
            "artifacts": list(result.artifacts),
            "ok": result.error is None,
        }
        if result.error is not None:
            content["error"] = asdict(result.error)
        return self.log.append(
            actor="tool",
            kind="tool_result",
            content=content,
            tool_name=call.name,
            tool_call_id=call.call_id,
        )


__all__ = [
    "DEFAULT_STATE_ROOT",
    "HARNESS_ID",
    "EventLog",
    "SessionState",
    "TraceEvent",
]
