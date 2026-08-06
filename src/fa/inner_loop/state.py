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
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fa.inner_loop.registry import ToolCall, ToolResult
from fa.inner_loop.session_db import SessionDatabase
from fa.output import LogKind, OutputEvent
from fa.paths import fa_session_log_root, private_opener

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


def default_state_root() -> Path:
    """Resolve the session-log root at CALL time, not import time (V10).

    ``DEFAULT_STATE_ROOT`` above is bound when this module is first imported, so
    any later change to ``HOME`` — an embedder reconfiguring itself, or a test
    isolating its filesystem — is silently ignored and writes land in the real
    user's ``~/.fa``. That is how ten tests came to share
    ``~/.fa/session-log/<run_id>/`` instead of their own ``tmp_path``: the leak
    was invisible while the Blackboard used ``INSERT OR REPLACE`` (it overwrote
    the previous run's row), and became a hard failure once S5.3 made writes
    append-only.

    Resolving here keeps one behaviour for production (``HOME`` is stable, so
    the value is identical) while making the root honestly reconfigurable. The
    module-level constant is retained for backward compatibility with any
    caller that imports it (parent Do#9 — preserve public facades).
    """
    return fa_session_log_root()


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
    session_id: str = ""

    @classmethod
    def from_row(
        cls,
        row: Mapping[str, object],
        *,
        default_run_id: str = "",
        default_session_id: str = "",
    ) -> TraceEvent:
        """Project one ``event_log`` DB row into a typed ``TraceEvent``.

        Both :meth:`EventLog.read_all` and :func:`fa.stats.parse_session_db`
        materialise rows from the same ``session.db`` schema; the two copies of
        this projection were byte-similar enough for pylint to flag R0801.
        Keeping one constructor means a schema column added in one reader can
        never be silently missing from the other.

        The two call sites differ only in their fallbacks for absent
        ``run_id`` / ``session_id`` (``EventLog`` uses the empty string, stats
        substitutes the values it queried with), so those stay parameters
        rather than being hard-coded here.
        """
        # ``content`` arrives as ``object`` from the row mapping. Validate it at
        # this boundary instead of asserting a type: a malformed row yields an
        # empty mapping rather than a TypeError deep inside a consumer, and the
        # isinstance check narrows the type for the checker without an ignore.
        raw_content = row.get("content")
        content: Mapping[str, object] = raw_content if isinstance(raw_content, Mapping) else {}
        return cls(
            event_id=str(row["event_id"]),
            ts=str(row["ts"]),
            run_id=str(row.get("run_id", default_run_id)),
            actor=str(row["actor"]),
            kind=str(row["kind"]),
            content=dict(content),
            harness_id=str(row["harness_id"]),
            tool_name=str(row.get("tool_name", "")),
            tool_call_id=str(row.get("tool_call_id", "")),
            parent_event_id=str(row.get("parent_event_id", "")),
            session_id=str(row.get("session_id", default_session_id)),
        )


class EventLog:
    """Per-run event facade with SQLite authority and a JSONL mirror.

    Thread-safe for Phase 2 tool batching: parallel read-only tools
    with Lock sequential log write.
    """

    def __init__(
        self,
        path: Path,
        *,
        run_id: str = "",
        redactor: SecretRedactor | None = None,
        session_db: SessionDatabase | None = None,
        session_id: str = "",
    ) -> None:
        self.path = Path(path)
        self.run_id = run_id
        self._redactor = redactor
        self._lock = threading.Lock()
        self._injected_session_db = session_db is not None
        self.session_db = session_db if session_db is not None else SessionDatabase(self.path.parent / "session.db")
        self.session_id = session_id or self.session_db.session_id
        if self.session_id and self.session_db.session_id and self.session_id != self.session_db.session_id:
            raise RuntimeError(
                "session_db_identity_mismatch: "
                f"EventLog session {self.session_id!r} != DB session {self.session_db.session_id!r}"
            )
        # S9: Incremental event counting for guardrail metrics (G9).
        # Updated inside append() under the existing _lock for thread safety.
        self.kind_counts: dict[str, int] = {}
        # S9: Dedicated counter for chain exhaustion events (user Q2:
        # not derived from kind_counts — precise metric for retry logic).
        self.chain_exhaustion_count: int = 0

        # SessionDatabase owns both the directory/schema bootstrap and the
        # authority identity. Construct/inject it before seeding the event id.
        # Retained for backward compatibility with callers/tests that read it
        # (parent Do#9 — preserve public facades). It is NO LONGER the
        # allocator: as of S5.1 the authority allocates inside the writing
        # transaction, because a per-instance counter cannot be correct when two
        # EventLog instances share one session.db. Treat this as a diagnostic
        # snapshot of "rows at construction + 1", not a source of truth.
        self._next_id = self._initial_next_id(self.session_db)

    @staticmethod
    def _initial_next_id(session_db: SessionDatabase) -> int:
        """Report the id the DB would allocate next, at construction time.

        JSONL is a best-effort mirror and therefore must never participate in
        event-id correctness. Any authority read failure propagates instead of
        silently creating a split-brain session.

        Superseded as the allocator by
        :meth:`SessionDatabase.append_event_row_allocating` (S5.1 / V1); kept
        because external callers read ``_next_id`` for diagnostics.
        """
        return session_db.event_count() + 1

    @property
    def redactor(self) -> SecretRedactor | None:
        """The configured secret redactor, or ``None``.

        Read-only accessor (S6.5): ``spawn_subagent`` needs the *same* redactor
        the trace already uses so subagent output is masked by the same policy,
        without constructing a second one or adding a new config surface. The
        setter is deliberately absent — the redactor is fixed at construction.
        """
        return self._redactor

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
            # S5.1 / V1 — the event id is allocated BY THE AUTHORITY, inside the
            # same transaction that inserts the row. The previous design seeded
            # a per-instance counter from ``event_count() + 1`` at construction,
            # so two EventLog instances created before either wrote allocated
            # identical ids. ``event_id`` is left empty here precisely so this
            # object cannot express an opinion about it.
            pending = TraceEvent(
                event_id="",
                ts=_now_iso_z(),
                run_id=self.run_id,
                actor=actor,
                kind=kind,
                content=redacted_content,
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                parent_event_id=parent_event_id,
                session_id=self.session_id,
            )
            self.path.parent.mkdir(parents=True, exist_ok=True)

            # 1. Authoritative allocate-and-write. Raises on failure; an event
            #    is never silently dropped.
            allocated_id = self.session_db.append_event_row_allocating(asdict(pending))
            event = replace(pending, event_id=allocated_id)

            # 2. S5.2 / V2-residual — counters advance only after the commit
            #    succeeds. Incrementing before the write let a failed append
            #    inflate ``kind_counts``, and ``coder_loop`` persists that map
            #    into ``session_meta``, so the drift became durable.
            self.kind_counts[str(kind)] = self.kind_counts.get(str(kind), 0) + 1

            # 3. Best-effort JSONL mirror for audit/diffability.
            try:
                line = json.dumps(asdict(event), ensure_ascii=False, sort_keys=True)
                # Builtin ``open`` + ``private_opener`` (I-36): event content is
                # the same prose the bodies file holds. ``Path.open`` rejects
                # ``opener``, so this must stay the builtin.
                with open(self.path, "a", encoding="utf-8", opener=private_opener) as handle:
                    handle.write(line + "\n")
            except Exception as exc:  # noqa: BLE001 # mirror-only degradation
                logger.warning("Failed to write EventLog JSONL mirror: %s", exc)

            return event

    def read_all(self) -> tuple[TraceEvent, ...]:
        try:
            rows = self.session_db.read_event_rows(run_id=self.run_id or None)
            db_events = tuple(TraceEvent.from_row(row) for row in rows)
            # An injected session DB is the current-format authority. Empty or
            # failed reads must not fall through to the mirror.
            if self._injected_session_db or db_events:
                return db_events
        except Exception as exc:  # legacy/degraded fallback
            logger.warning("Failed to read events from authoritative SessionDatabase: %s", exc)
            if self._injected_session_db:
                raise

        if not self.path.exists():
            return ()
        legacy_events: list[TraceEvent] = []
        try:
            for raw in self.path.read_text(encoding="utf-8").splitlines():
                if not raw:
                    continue
                parsed = json.loads(raw)
                legacy_events.append(
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
                        session_id=str(parsed.get("session_id", "")),
                    )
                )
            return tuple(legacy_events)
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
    session_id: str = ""
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
            # Call-time resolution (V10): see ``default_state_root``. Using the
            # import-time constant here made every ``SessionState`` built
            # without an explicit ``log=`` write into the real ``~/.fa``,
            # regardless of the caller's workspace.
            self.log = EventLog(
                default_state_root() / self.run_id / "events.jsonl",
                run_id=self.run_id,
            )
        elif not self.log.run_id:
            self.log.run_id = self.run_id

        # Unified session authority DB for hot-path runtime state.
        if self.session_db is None and self.log is not None:
            self.session_db = self.log.session_db
        if self.log is not None and self.session_db is not None:
            if self.log.session_db.path.resolve() != self.session_db.path.resolve():
                raise ValueError("SessionState.log and SessionState.session_db must reference the same authority")
            if self.session_id and self.log.session_id and self.session_id != self.log.session_id:
                raise ValueError("SessionState.session_id does not match EventLog.session_id")
            if self.session_id and self.session_db.session_id and self.session_id != self.session_db.session_id:
                raise ValueError("SessionState.session_id does not match SessionDatabase.session_id")
            if not self.session_id:
                self.session_id = self.log.session_id or self.session_db.session_id

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
                    logger.warning("SessionState blackboard disabled because authoritative session_db is unavailable")
                    self.blackboard = None
                else:
                    try:
                        from fa.blackboard.blackboard import Blackboard

                        self.blackboard = Blackboard(
                            self.workspace_root / ".fa" / "blackboard",
                            session_db=self.session_db,
                            run_id=self.run_id,
                            session_id=self.session_id,
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
            from fa.workspace.worktree_manager import WorktreeManagerFactory

            flags = self.feature_flags
            try:
                # For v0.1, repo_root is workspace_root (assumes git repo)
                # For Docker, workspace_root is /workspace which is git clone --local
                self.worktree_manager = WorktreeManagerFactory.from_flags(
                    flags, session_root=self.workspace_root, repo_root=self.workspace_root, run_id=self.run_id
                )
            except ValueError as exc:
                # V19: an unsupported worktree_mode is a CONFIG error, not a
                # runtime hiccup. Falling back to SharedDir here would restore
                # exactly the silent downgrade the factory now refuses — the
                # operator would ask for isolation, receive shared, and never
                # be told. Leave the manager unset and surface it where the
                # operator actually looks (event log + console).
                self.worktree_manager = None
                self._record_config_warning(line_no=0, key="worktree.mode", detail=str(exc))
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

    def try_reserve_subagent_spawn(self, max_spawns: int) -> bool:
        """Atomically claim one subagent slot. Returns False when exhausted.

        Compare-and-increment under one lock (V21). Splitting the check from
        the increment — as the caller used to — lets concurrent admissions all
        observe the same pre-increment count and all succeed; measured at 12
        admissions under a limit of 3 once the counter read was not
        instantaneous. Doing both here makes over-admission unrepresentable
        rather than unlikely.
        """
        with self._subagent_lock:
            if self.subagent_spawns >= max_spawns:
                return False
            self.subagent_spawns += 1
            return True

    def create_subagent_workspace(self, task_id: str, base_branch: str = "main") -> Path:
        """Return the per-task artifact root, or fail closed (V18, Q11-B Option A).

        ``<workspace_root>/.fa/subagents/<sanitized_task_id>/``.

        The previous implementation caught every exception and returned
        ``self.workspace_root``. That turned a failure on the isolation path
        into a **permission-boundary change**: an artifact-only task silently
        became a main-workspace mutator, on the code path least likely to be
        exercised or noticed. A subagent that cannot get its own directory is
        not one that should be allowed to write into the main tree, so this
        now raises.

        The path comes from :func:`subagent_artifact_root` so the sandbox gate
        and the executor share one derivation (the V24/V25 defect was two).
        """
        del base_branch  # Reserved for the isolated-worktree upgrade path (Q11-B Option C).
        from fa.workspace.worktree_manager import ensure_subagent_artifact_root

        try:
            workdir = ensure_subagent_artifact_root(self.workspace_root, task_id, run_id=self.run_id)
        except Exception as exc:
            raise RuntimeError(
                f"subagent_workspace_unavailable: cannot create an artifact root for task {task_id!r} ({exc}). "
                "Refusing the spawn rather than falling back to the main workspace."
            ) from exc

        try:
            self.add_write(str(workdir))
        except Exception as exc:  # noqa: BLE001 # bookkeeping only, failure-observable WARNING
            logger.warning("transaction add_write failed for subagent workspace %s: %s", workdir, exc)
        return workdir

    def cleanup_subagent_workspace(self, path: Path) -> None:
        """Remove a subagent artifact dir; surface failure (V20).

        A swallowed cleanup failure leaves the directory behind, and the next
        task with the same id reuses it — silently mixing two subagents' output
        into one artifact set. The caller needs to know.
        """
        import shutil

        from fa.workspace.worktree_manager import SUBAGENT_ARTIFACT_DIRNAME

        resolved = Path(path).resolve()
        artifact_tree = (self.workspace_root / ".fa" / SUBAGENT_ARTIFACT_DIRNAME).resolve()
        # Containment check first: cleanup takes a path, so it is the one place
        # a wrong value could delete something that matters.
        if resolved == artifact_tree or not resolved.is_relative_to(artifact_tree):
            raise RuntimeError(
                f"subagent_cleanup_refused: {resolved} is not a subagent artifact directory under {artifact_tree}"
            )

        # The artifact root is owned by this class, not by the WorktreeManager:
        # SharedDirWorktreeManager.cleanup only accepts its own session_root and
        # rejects anything else, so delegating here would fail on every call.
        # The manager is consulted only once real worktrees exist (Q11-B
        # Option C), at which point the write root becomes its path.
        try:
            shutil.rmtree(resolved, ignore_errors=False)
        except FileNotFoundError:
            return
        except Exception as exc:
            raise RuntimeError(f"subagent_cleanup_failed: could not remove {resolved} ({exc})") from exc

    def record_tool_call(self, call: ToolCall) -> TraceEvent:
        assert self.log is not None  # noqa: S101
        self.turn += 1
        # Track read for transaction if read_file
        try:
            if call.name == "fs_read_file":
                p = call.params.get("path")
                if isinstance(p, str):
                    self.add_read(p)
            elif call.name in ("fs_write_file", "fs_edit_file"):
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
    "default_state_root",
]
