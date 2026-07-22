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
import logging
import os
import threading
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fa.inner_loop.registry import ToolCall, ToolResult
from fa.inner_loop.session_db import SessionDatabase
from fa.output import LogKind, OutputEvent

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from fa.blackboard.blackboard import Blackboard
    from fa.feature_flags import FeatureFlags
    from fa.inner_loop.artifacts import ArtifactStore
    from fa.inner_loop.transaction import Transaction
    from fa.observability.redaction import SecretRedactor
    from fa.output import EventBus
    from fa.runtime.bash_executor import BashExecutor
    from fa.telemetry.telemetry import TelemetryLogger
    from fa.workspace.worktree_manager import WorktreeManager

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
        self.path = Path(path)
        self.run_id = run_id
        self._next_id = self._initial_next_id(path)
        self._redactor = redactor
        self._lock = threading.Lock()
        # S9: Incremental event counting for guardrail metrics (G9).
        # Updated inside append() under the existing _lock for thread safety.
        self.kind_counts: dict[str, int] = {}
        # S9: Dedicated counter for chain exhaustion events (user Q2:
        # not derived from kind_counts — precise metric for retry logic).
        self.chain_exhaustion_count: int = 0
        try:
            self.session_db: SessionDatabase | None = SessionDatabase(self.path.parent / "session.db")
        except RuntimeError as exc:
            logger.warning("EventLog authority database unavailable for %s: %s", self.path, exc)
            self.session_db = None
        self._init_db()

    def _init_db(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # SessionDatabase owns authoritative schema creation. Construction may
        # intentionally degrade to None for non-writable/special paths used by
        # tests; append() becomes the enforcement point.

    @staticmethod
    def _initial_next_id(path: Path) -> int:
        """Seed _next_id from the authoritative DB, falling back to JSONL.

        Per the dual-write discipline (session.db = authority, JSONL = mirror),
        the event_id counter must be seeded from session.db COUNT(*) rather
        than the JSONL line count. If JSONL writes fail but DB writes succeed
        (e.g. during a workflow where each stage creates a new EventLog on the
        same session.db), the JSONL count would undercount and produce
        duplicate event_id values (LOGIC-1).
        """
        # Try DB first — it's the authority per dual-write discipline.
        db_path = path.parent / "session.db"
        try:
            import sqlite3

            conn = sqlite3.connect(str(db_path), timeout=5.0)
            try:
                cur = conn.execute("SELECT COUNT(*) FROM event_log")
                count = int(cur.fetchone()[0])
                return count + 1
            finally:
                conn.close()
        except Exception as exc:  # noqa: BLE001 — DB bootstrap may be unavailable; JSONL fallback remains explicit
            logger.warning("EventLog DB counter unavailable, using JSONL fallback: %s", exc)
        # Fallback to JSONL mirror for brand-new sessions without a DB yet.
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
        kind: LogKind,
        content: Mapping[str, object] | None = None,
        tool_name: str = "",
        tool_call_id: str = "",
        parent_event_id: str = "",
    ) -> TraceEvent:
        redacted_content: dict[str, object] = {}
        if content is not None:
            redacted_content = {k: self._redact_value(v) for k, v in content.items()}
        with self._lock:
            # S9: Incremental kind counting under existing lock (thread-safe).
            self.kind_counts[str(kind)] = self.kind_counts.get(str(kind), 0) + 1

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
            self.path.parent.mkdir(parents=True, exist_ok=True)

            # 1. Authoritative write to the per-run SessionDatabase.
            if self.session_db is None:
                raise RuntimeError(f"event_log_authority_unavailable: {self.path.parent / 'session.db'}")
            self.session_db.append_event_row(asdict(event))

            # 2. Advance logical id only after authoritative commit succeeds.
            self._next_id += 1

            # 3. Best-effort JSONL mirror for audit/diffability.
            try:
                line = json.dumps(asdict(event), ensure_ascii=False, sort_keys=True)
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
            except Exception as exc:  # noqa: BLE001 # mirror-only degradation
                logger.warning("Failed to write EventLog JSONL mirror: %s", exc)

            return event

    def read_all(self) -> tuple[TraceEvent, ...]:
        try:
            if self.session_db is not None:
                rows = self.session_db.read_event_rows()
                if rows:
                    return tuple(
                        TraceEvent(
                            event_id=str(row["event_id"]),
                            ts=str(row["ts"]),
                            run_id=str(row.get("run_id", "")),
                            actor=str(row["actor"]),
                            kind=str(row["kind"]),
                            content=dict(row.get("content", {})),
                            harness_id=str(row["harness_id"]),
                            tool_name=str(row.get("tool_name", "")),
                            tool_call_id=str(row.get("tool_call_id", "")),
                            parent_event_id=str(row.get("parent_event_id", "")),
                        )
                        for row in rows
                    )
        except Exception as exc:  # noqa: BLE001 # legacy/degraded fallback
            logger.warning("Failed to read events from authoritative SessionDatabase: %s", exc)

        if not self.path.exists():
            return ()
        events = []
        try:
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
        except Exception as exc2:  # noqa: BLE001 - legacy JSONL fallback must not crash readers
            logger.warning("Fallback JSONL reading failed: %s", exc2)
            return ()


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
    # Stage 0.5 extensions — typed for pyright narrowing (S11).
    # All use TYPE_CHECKING imports to avoid circular deps at runtime.
    # pty_pool remains Any | None because fa.runtime is optional.
    transaction: Transaction | None = None
    blackboard: Blackboard | None = None
    telemetry: TelemetryLogger | None = None
    feature_flags: FeatureFlags | None = None
    artifact_store: ArtifactStore | None = None
    pty_pool: Any | None = None  # PtyPool — optional module, keep Any
    bash_executor: BashExecutor | None = None  # Protocol from fa.runtime.bash_executor (user Q1)
    worktree_manager: WorktreeManager | None = None
    session_db: SessionDatabase | None = None
    # The CLI wires this after bootstrap; pending events are flushed on attach.
    output_bus: EventBus | None = None
    _pending_output_events: list[OutputEvent] = field(default_factory=list, init=False, repr=False)
    turn: int = 0
    subagent_spawns: int = 0
    _subagent_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def require_log(self) -> EventLog:
        """Return the authoritative session log or fail closed."""
        if self.log is None:
            raise ValueError("SessionState.log must be initialized before session execution")
        return self.log

    def attach_output_bus(self, output_bus: EventBus) -> None:
        """Attach the display bus and flush warnings queued during bootstrap."""
        self.output_bus = output_bus
        pending = tuple(self._pending_output_events)
        self._pending_output_events.clear()
        for event in pending:
            output_bus.emit(event)

    def _record_config_warning(self, *, line_no: int, key: str, detail: str) -> None:
        """Persist and expose a config warning without losing early bootstrap events."""
        content = {"line_no": line_no, "key": key, "detail": detail}
        if self.log is not None:
            self.log.append(actor="config", kind="config_warning", content=content)
        event = OutputEvent(type="config_warning", data=content)
        if self.output_bus is None:
            self._pending_output_events.append(event)
        else:
            self.output_bus.emit(OutputEvent(type="config_warning", data=content))

    def __post_init__(self) -> None:  # noqa: C901 -- complexity from FeatureFlags + Transaction + Blackboard + Telemetry + WorktreeManager init, DI via SessionState, graceful degradation
        self.workspace_root = self.workspace_root.resolve()
        if self.log is None:
            self.log = EventLog(
                DEFAULT_STATE_ROOT / self.run_id / "events.jsonl",
                run_id=self.run_id,
            )
        elif not self.log.run_id:
            self.log.run_id = self.run_id

        # Unified per-run authority DB for hot-path runtime state.
        if self.session_db is None and self.log is not None:
            self.session_db = self.log.session_db

        # FeatureFlags loader with graceful degradation
        if self.feature_flags is None:
            try:
                from fa.feature_flags import load_feature_flags_from_path

                result = load_feature_flags_from_path()
                self.feature_flags = result.flags
                if result.warnings:
                    for w in result.warnings:
                        logger.warning(f"feature_flags {w.key}: {w.detail}")
                        self._record_config_warning(line_no=w.line_no, key=w.key, detail=w.detail)
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                logger.warning(f"Failed to load feature_flags: {exc}, using defaults")
                try:
                    from fa.feature_flags import FeatureFlags

                    self.feature_flags = FeatureFlags()
                except Exception:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                    self.feature_flags = None

        # Transaction always present
        if self.transaction is None:
            try:
                from fa.inner_loop.transaction import Transaction

                self.transaction = Transaction(id=self.run_id)
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                logger.warning(f"Failed to init Transaction: {exc}")

        # ArtifactStore for offloading full outputs
        if self.artifact_store is None:
            try:
                from fa.inner_loop.artifacts import ArtifactStore

                # Store under .fa/telemetry or session log artifacts?
                # Use workspace_root/.fa/artifacts for token-efficient offload
                self.artifact_store = ArtifactStore(self.workspace_root / ".fa" / "artifacts")
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                logger.warning(f"Failed to init ArtifactStore: {exc}")

        # Blackboard if enabled
        if self.blackboard is None:
            # S13: FAIL-OPEN — blackboard_enabled defaults to True (convenience)
            enabled = self.feature_flags.blackboard_enabled if self.feature_flags is not None else True
            if enabled:
                if self.session_db is None:
                    logger.warning(
                        "SessionState blackboard disabled because authoritative session_db is unavailable"
                    )
                    self.blackboard = None
                else:
                    try:
                        from fa.blackboard.blackboard import Blackboard

                        self.blackboard = Blackboard(
                            self.workspace_root / ".fa" / "blackboard",
                            session_db=self.session_db,
                            run_id=self.run_id,
                        )
                    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                        logger.warning(f"Failed to init Blackboard: {exc}, continuing without")
                        self.blackboard = None

        # Telemetry if enabled
        if self.telemetry is None:
            # S13: FAIL-OPEN — telemetry_enabled defaults to True (convenience)
            enabled = self.feature_flags.telemetry_enabled if self.feature_flags is not None else True
            if enabled:
                try:
                    from fa.telemetry.telemetry import TelemetryLogger

                    self.telemetry = TelemetryLogger(self.workspace_root / ".fa" / "telemetry")
                except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                    logger.warning(f"Failed to init TelemetryLogger: {exc}, continuing without")
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
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                logger.warning(f"Failed to init WorktreeManager: {exc}, using SharedDir fallback")
                try:
                    from fa.workspace.worktree_manager import SharedDirWorktreeManager

                    self.worktree_manager = SharedDirWorktreeManager(self.workspace_root, run_id=self.run_id)
                except Exception:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                    self.worktree_manager = None

        # PtyPool — FIND-007 fix: stateful shell wired into live session by default
        if self.pty_pool is None:
            try:
                from fa.runtime import PtyPool

                # S13: FAIL-OPEN — pty_pool_max_size defaults to 2
                max_size = self.feature_flags.pty_pool_max_size if self.feature_flags is not None else 2
                self.pty_pool = PtyPool(max_size=max_size, base_cwd=self.workspace_root, run_id=self.run_id)
            except Exception as exc:  # noqa: BLE001 # graceful degradation, fallback to stateless subprocess
                logger.warning(f"Failed to init PtyPool: {exc}, fallback to subprocess")
                self.pty_pool = None

    # Transaction helpers
    def add_read(self, path: str) -> None:
        try:
            if self.transaction is not None:
                self.transaction.add_read(path)
        except Exception as exc:  # noqa: BLE001 - best-effort
            logger.warning(f"add_read failed for {path}: {exc}")

    def add_write(self, path: str) -> None:
        try:
            if self.transaction is not None:
                self.transaction.add_write(path)
        except Exception as exc:  # noqa: BLE001 - best-effort
            logger.warning(f"add_write failed for {path}: {exc}")

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
                except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
                    pass
                return ws
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            logger.warning(f"create_subagent_workspace failed for {task_id}: {exc}, fallback to session_root")
        return self.workspace_root

    def cleanup_subagent_workspace(self, path: Path) -> None:
        try:
            if self.worktree_manager is not None:
                self.worktree_manager.cleanup(path)
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            logger.warning(f"cleanup_subagent_workspace failed for {path}: {exc}")

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
        except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
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
                # S13: FAIL-OPEN — offload_threshold defaults to 8000
                threshold = self.feature_flags.offload_threshold if self.feature_flags is not None else 8000
                full_output = json.dumps(content, ensure_ascii=False, default=str)
                if len(full_output) > threshold:
                    artifact_id = self.artifact_store.put(content)
                    # Also ensure artifact listed in content for projection
                    content["artifact_id"] = artifact_id
                    content["preview"] = full_output[:500] + "...[offloaded]"
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            logger.warning(f"Artifact offload failed: {exc}")

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
                    permission_tier=getattr(call, "permission", "unknown")
                    if hasattr(call, "permission")
                    else "unknown",
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
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            logger.warning(f"Telemetry logging failed: {exc}")

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
