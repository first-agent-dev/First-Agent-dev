"""Inner-loop session state + ``events.jsonl`` writer (ADR-7 §7).

Each ``run_session`` invocation owns a :class:`SessionState`. The state
holds the workspace root, the ``run_id`` used in the events file path
and in every event payload, the per-session :class:`EventLog`, and the
``observations`` tail used by the deterministic loop for follow-up
prompting.

The event schema matches ADR-7 §7 verbatim: ``ts`` (ISO-8601 UTC),
``run_id``, ``harness_id``, ``actor``, ``kind``, ``tool_name``,
``tool_call_id``, ``parent_event_id``, ``content``. The ``kind`` field
is an open enumeration — the value is appended verbatim by writers,
no validation. ADR-7 §7 lists the core kinds; subsequent R-N PRs
have introduced additional kinds wired into specific hooks.

Core kinds (ADR-7 §7):
``user_msg | model_msg | tool_call | tool_result | hook_decision |
audit | approval | error | stop``.

Extension kinds (added by Wave-2 R-Ns; each line names the originating
writer + the R-N anchor):

- ``run_stopped`` — :func:`fa.inner_loop.loop.run_session` when a
  ``BETWEEN_ROUNDS`` or ``AFTER_TOOL_EXEC`` guard denies via
  ``PermissionError`` (PR #24 BUG-0001 / BUG-0003).
- ``loop_guard_warn`` —
  :class:`fa.inner_loop.hooks.loop_guard.LoopGuard` warn channel
  (R-2; PR #25 ``loop_guard.py``).
- ``recovery_action`` —
  :class:`fa.inner_loop.hooks.recovery_observers.FailureClassifierObserver`
  (R-3; PR #25 ``recovery_observers.py``).
- ``verification`` —
  :class:`fa.inner_loop.hooks.builtin.VerifierObserver` failure-row
  emitter (PR #26 wiring of R-5 DSV).
- ``cost_observation`` —
  :class:`fa.observability.cost_guardian.CostGuardian` per-call cost
  sample + rolling rollup (R-45). One row per recognised
  ``cost=…`` artifact in :attr:`ToolResult.artifacts`; baseline
  M-1 tools never emit the artifact, so the kind is dormant until
  the T-2 LLM driver lands.
- ``provider_attempt`` —
  :func:`fa.inner_loop.coder_loop.drive_session` logs each
  :class:`fa.providers.chain.ChainAttemptRecord` returned by
  :meth:`ProviderChain.request` (ADR-9 §4 Tier-1 observability).

Filesystem-canon observers such as
:class:`fa.inner_loop.hooks.builtin.LearningObserver` (R-8) do not add
event kinds here: they write side-effect artifacts under
``knowledge/trace/`` rather than rows in this ``EventLog``.

New writers MUST add their ``kind`` value to this list in the same
commit (AGENTS.md PR Checklist; matches ADR-7 §7 «schema
discoverability» intent).
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from fa.inner_loop.registry import ToolCall, ToolResult

if TYPE_CHECKING:
    from fa.observability.redaction import SecretRedactor

DEFAULT_STATE_ROOT = Path.home() / ".fa" / "state" / "runs"
HARNESS_ID = "fa-inner-loop@0.1.0"


def _now_iso_z() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class TraceEvent:
    """One row written to ``~/.fa/state/runs/<run_id>/events.jsonl``.

    Field names track ADR-7 §7 exactly: ``ts`` (not ``timestamp``),
    ``run_id`` stamped on every row, ``harness_id`` for cross-version
    replay refusal.
    """

    event_id: str
    ts: str
    run_id: str
    actor: str
    kind: str
    content: Mapping[str, object] = field(default_factory=dict)
    harness_id: str = HARNESS_ID
    tool_name: str = ""
    tool_call_id: str = ""
    parent_event_id: str = ""


class EventLog:
    """Append-only JSONL writer for one ``run_id``.

    The writer is intentionally simple: it tracks the next event id
    monotonically and serialises each :class:`TraceEvent` via
    ``json.dumps(sort_keys=True)`` so the line order is the byte order
    of the file and replay diffs stay deterministic.
    """

    def __init__(
        self,
        path: Path,
        *,
        run_id: str = "",
        redactor: SecretRedactor | None = None,
    ) -> None:
        self.path = path
        self.run_id = run_id
        self._next_id = 1
        self._redactor = redactor

    def _redact_value(self, value: object) -> object:
        if self._redactor is None:
            return value
        if isinstance(value, str):
            return self._redactor.redact(value)
        if isinstance(value, dict):
            return {k: self._redact_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._redact_value(v) for v in value]
        if isinstance(value, tuple):
            return tuple(self._redact_value(v) for v in value)
        return value

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
        redacted_content: dict[str, object] = {}
        if content is not None:
            redacted_content = {k: self._redact_value(v) for k, v in content.items()}
        event = TraceEvent(
            event_id=f"ev-{self._next_id:06d}",
            ts=_now_iso_z(),
            run_id=self.run_id,
            actor=actor,
            kind=kind,
            content=redacted_content,
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
                    ts=str(parsed["ts"]),
                    run_id=str(parsed.get("run_id", "")),
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
    log: EventLog | None = None
    observations: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.workspace_root = self.workspace_root.resolve()
        if self.log is None:
            self.log = EventLog(
                DEFAULT_STATE_ROOT / self.run_id / "events.jsonl",
                run_id=self.run_id,
            )
        elif not self.log.run_id:
            # Caller-supplied logs (tests, custom drivers) inherit the
            # session ``run_id`` so events.jsonl rows are still tagged
            # per ADR-7 §7.
            self.log.run_id = self.run_id

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
