"""Inner-loop session state + ``events.jsonl`` writer (ADR-7 §7).

Each ``run_session`` invocation owns a :class:`SessionState`. The state
holds the workspace root, the ``run_id`` used in the events file path
and in every event payload, the per-session :class:`EventLog`, and the
``observations`` tail used by the deterministic loop for follow-up
prompting.

Extension for Stage 0.5 — Formal Blackboard + Structured Telemetry:
- Transaction object with read_set/write_set accumulated via add_read/add_write
- Blackboard: content-hashed, queryable, detect_conflict before write_file
- Telemetry: structured TelemetryEvent per tool call, offload full outputs to ArtifactStore
- FeatureFlags: loader from ~/.fa/config.yaml for blackboard.enabled, telemetry.enabled, etc.

The event schema matches ADR-7 §7 verbatim: ``ts`` (ISO-8601 UTC),
``run_id``, ``harness_id``, ``actor``, ``kind``, ``tool_name``,
``tool_call_id``, ``parent_event_id``, ``content``. The ``kind`` field
is an open enumeration — the value is appended verbatim by writers,
no validation. ADR-7 §7 lists the core kinds; subsequent R-N PRs
have introduced additional kinds wired into specific hooks.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fa.inner_loop.registry import ToolCall, ToolResult

if TYPE_CHECKING:
    from fa.observability.redaction import SecretRedactor

DEFAULT_STATE_ROOT = Path.home() / ".fa" / "session-log"
HARNESS_ID = "fa-inner-loop@0.1.0"


def _now_iso_z() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_safe(value: object) -> object:
    """Return a JSON-serializable projection without dropping structure."""
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return repr(value)


@dataclass(frozen=True)
class TraceEvent:
    """One row written to ``~/.fa/session-log/<run_id>/events.jsonl``.

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

    Thread-safe for Phase 2 tool batching: parallel read-only tools
    with Lock sequential log write.
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
        self._next_id = self._initial_next_id(path)
        self._redactor = redactor
        self._lock = threading.Lock()

    @staticmethod
    def _initial_next_id(path: Path) -> int:
        if not path.exists():
            return 1
        try:
            return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line) + 1
        except OSError:
            return 1

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
        with self._lock:
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
    """Session state with Formal Blackboard + Telemetry + Transaction for Stage 0.5/1.

    Holds:
    - workspace_root, run_id, log, observations (existing)
    - transaction: accumulated read_set/write_set via add_read/add_write
    - blackboard: typed append-only content-hashed (if enabled)
    - telemetry: structured minimal telemetry (if enabled)
    - artifact_store: content-addressed offload for full outputs
    - feature_flags: loaded from ~/.fa/config.yaml with defaults
    - pty_pool: optional PtyPool injected via DI (Phase 3)
    """

    workspace_root: Path
    run_id: str = field(default_factory=lambda: f"run-{os.getpid()}")
    log: EventLog | None = None
    observations: list[str] = field(default_factory=list)
    # Stage 0.5 extensions
    transaction: Any | None = None  # Transaction, avoid circular import at runtime
    blackboard: Any | None = None  # Blackboard
    telemetry: Any | None = None  # TelemetryLogger
    feature_flags: Any | None = None  # FeatureFlags
    artifact_store: Any | None = None  # ArtifactStore
    pty_pool: Any | None = None  # PtyPool
    worktree_manager: Any | None = None  # WorktreeManager
    turn: int = 0
    subagent_spawns: int = 0
    _subagent_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        self.workspace_root = self.workspace_root.resolve()
        if self.log is None:
            self.log = EventLog(
                DEFAULT_STATE_ROOT / self.run_id / "events.jsonl",
                run_id=self.run_id,
            )
        elif not self.log.run_id:
            self.log.run_id = self.run_id

        # FeatureFlags loader with graceful degradation
        if self.feature_flags is None:
            try:
                from fa.feature_flags import load_feature_flags_from_path

                result = load_feature_flags_from_path()
                self.feature_flags = result.flags
                if result.warnings:
                    for w in result.warnings:
                        print(f"WARNING: feature_flags {w.key}: {w.detail}")
            except Exception as exc:
                print(f"WARNING: Failed to load feature_flags: {exc}, using defaults")
                try:
                    from fa.feature_flags import FeatureFlags

                    self.feature_flags = FeatureFlags()
                except Exception:
                    self.feature_flags = None

        # Transaction always present
        if self.transaction is None:
            try:
                from fa.inner_loop.transaction import Transaction

                self.transaction = Transaction(id=self.run_id)
            except Exception as exc:
                print(f"WARNING: Failed to init Transaction: {exc}")

        # ArtifactStore for offloading full outputs
        if self.artifact_store is None:
            try:
                from fa.inner_loop.artifacts import ArtifactStore

                # Store under .fa/telemetry or session log artifacts?
                # Use workspace_root/.fa/artifacts for token-efficient offload
                self.artifact_store = ArtifactStore(self.workspace_root / ".fa" / "artifacts")
            except Exception as exc:
                print(f"WARNING: Failed to init ArtifactStore: {exc}")

        # Blackboard if enabled
        if self.blackboard is None:
            enabled = True
            try:
                if self.feature_flags is not None:
                    enabled = getattr(self.feature_flags, "blackboard_enabled", True)
            except Exception:
                enabled = True
            if enabled:
                try:
                    from fa.blackboard.blackboard import Blackboard

                    self.blackboard = Blackboard(self.workspace_root / ".fa" / "blackboard")
                except Exception as exc:
                    print(f"WARNING: Failed to init Blackboard: {exc}, continuing without")
                    self.blackboard = None

        # Telemetry if enabled
        if self.telemetry is None:
            enabled = True
            try:
                if self.feature_flags is not None:
                    enabled = getattr(self.feature_flags, "telemetry_enabled", True)
            except Exception:
                enabled = True
            if enabled:
                try:
                    from fa.telemetry.telemetry import TelemetryLogger

                    self.telemetry = TelemetryLogger(self.workspace_root / ".fa" / "telemetry")
                except Exception as exc:
                    print(f"WARNING: Failed to init TelemetryLogger: {exc}, continuing without")
                    self.telemetry = None

        # WorktreeManager via Factory from flags (Phase 1)
        if self.worktree_manager is None:
            try:
                from fa.workspace.worktree_manager import WorktreeManagerFactory

                flags = self.feature_flags
                # For v0.1, repo_root is workspace_root (assumes git repo)
                # For Docker, workspace_root is /workspace which is git clone --local
                self.worktree_manager = WorktreeManagerFactory.from_flags(
                    flags, session_root=self.workspace_root, repo_root=self.workspace_root, run_id=self.run_id
                )
            except Exception as exc:
                print(f"WARNING: Failed to init WorktreeManager: {exc}, using SharedDir fallback")
                try:
                    from fa.workspace.worktree_manager import SharedDirWorktreeManager

                    self.worktree_manager = SharedDirWorktreeManager(self.workspace_root, run_id=self.run_id)
                except Exception:
                    self.worktree_manager = None

    # Transaction helpers
    def add_read(self, path: str) -> None:
        try:
            if self.transaction is not None:
                self.transaction.add_read(path)
        except Exception as exc:  # noqa: BLE001 - best-effort
            print(f"WARNING: add_read failed for {path}: {exc}")

    def add_write(self, path: str) -> None:
        try:
            if self.transaction is not None:
                self.transaction.add_write(path)
        except Exception as exc:  # noqa: BLE001 - best-effort
            print(f"WARNING: add_write failed for {path}: {exc}")

    def increment_subagent_spawns(self) -> int:
        """Thread-safe increment for subagent spawn limit (Phase 1)."""
        with self._subagent_lock:
            self.subagent_spawns += 1
            return self.subagent_spawns

    def get_subagent_spawns(self) -> int:
        with self._subagent_lock:
            return self.subagent_spawns

    def create_subagent_workspace(self, task_id: str, base_branch: str = "main") -> Path:
        """Create subagent workspace via WorktreeManager, declares write_set for transaction."""
        try:
            if self.worktree_manager is not None:
                ws = self.worktree_manager.create_subagent_workspace(task_id, base_branch=base_branch)
                # Declare transaction write for worktree path
                try:
                    self.add_write(str(ws))
                except Exception:
                    pass
                return ws
        except Exception as exc:
            print(f"WARNING: create_subagent_workspace failed for {task_id}: {exc}, fallback to session_root")
        return self.workspace_root

    def cleanup_subagent_workspace(self, path: Path) -> None:
        try:
            if self.worktree_manager is not None:
                self.worktree_manager.cleanup(path)
        except Exception as exc:
            print(f"WARNING: cleanup_subagent_workspace failed for {path}: {exc}")

    def record_tool_call(self, call: ToolCall) -> TraceEvent:
        assert self.log is not None  # noqa: S101
        self.turn += 1
        # Track read for transaction if read_file
        try:
            if call.name == "fs.read_file":
                p = call.params.get("path")
                if isinstance(p, str):
                    self.add_read(p)
            elif call.name in ("fs.write_file", "fs.edit_file"):
                p = call.params.get("path")
                if isinstance(p, str):
                    self.add_write(p)
        except Exception:
            pass

        return self.log.append(
            actor="coder",
            kind="tool_call",
            content={"params": dict(call.params)},
            tool_name=call.name,
            tool_call_id=call.call_id,
        )

    def record_tool_result(self, call: ToolCall, result: ToolResult) -> TraceEvent:
        assert self.log is not None  # noqa: S101
        content: dict[str, object] = {
            "summary": result.summary,
            "artifacts": list(result.artifacts),
            "ok": result.error is None,
        }
        if result.result is not None:
            content["result"] = _json_safe(result.result)
        if result.error is not None:
            content["error"] = asdict(result.error)

        # Offload full output to ArtifactStore if large, keep artifact_id in telemetry
        artifact_id: str | None = None
        try:
            if self.artifact_store is not None:
                # If result summary or result dict large, offload
                threshold = 8000
                try:
                    if self.feature_flags is not None:
                        threshold = getattr(self.feature_flags, "offload_threshold", 8000)
                except Exception:
                    pass
                full_output = json.dumps(content, ensure_ascii=False, default=str)
                if len(full_output) > threshold:
                    artifact_id = self.artifact_store.put(content)
                    # Also ensure artifact listed in content for projection
                    content["artifact_id"] = artifact_id
                    content["preview"] = full_output[:500] + "...[offloaded]"
        except Exception as exc:
            print(f"WARNING: Artifact offload failed: {exc}")

        # Structured telemetry logging
        try:
            if self.telemetry is not None:
                from fa.telemetry.telemetry import TelemetryEvent

                # Sanitize handled inside logger
                tool_args = dict(call.params)
                # Truncate long args for telemetry
                for k, v in list(tool_args.items()):
                    if isinstance(v, str) and len(v) > 500:
                        tool_args[k] = v[:500] + "...[truncated]"

                # Determine test_result heuristic
                test_result = "PASS" if result.error is None else "FAIL"

                event = TelemetryEvent(
                    run_id=self.run_id,
                    turn=self.turn,
                    prompt_tokens=0,
                    completion_tokens=0,
                    cost_usd=0.0,
                    model_id="",
                    tool_name=call.name,
                    tool_args=tool_args,
                    permission_tier=getattr(call, "permission", "unknown") if hasattr(call, "permission") else "unknown",
                    edited_files=[p for p in [call.params.get("path")] if isinstance(p, str)],
                    test_result=test_result,
                    cache_hit=False,
                    latency_ms=0,
                    branch_decision="",
                    rejected_alternatives=[],
                    human_approval=None,
                    artifact_id=artifact_id,
                )
                self.telemetry.log(event)

                # Also log to EventLog as telemetry kind for audit
                self.log.append(
                    actor="telemetry",
                    kind="telemetry",
                    content={
                        "tool_name": call.name,
                        "ok": result.error is None,
                        "artifact_id": artifact_id or "",
                        "turn": self.turn,
                    },
                    tool_name=call.name,
                    tool_call_id=call.call_id,
                )
        except Exception as exc:
            print(f"WARNING: Telemetry logging failed: {exc}")

        # Original tool_result event for ADR-7 paired rows
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
