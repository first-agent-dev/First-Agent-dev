"""Managed, read-only/scratch child sessions for production callers.

This module deliberately does not use ``SubagentRunner``: that legacy runner
starts a host subprocess and cannot own a supervisor-bound READ view. The only
execution path here is ``pin_reader`` + ``ReadOnlyManagedBashExecutor``; any
admission, transport, or cleanup uncertainty fails closed without retrying on
the controller.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

import fastjsonschema  # type: ignore[import-untyped]

from fa.execution.client import (
    ExecutionRejectedError,
    ExecutionUnavailableError,
    ExecutionUncertainError,
    ReadOnlyManagedBashExecutor,
)
from fa.execution.composition import ExecutionBinding, ManagedExecution
from fa.execution.tool_port import ClientWorkspacePort
from fa.execution.types import Access, NamespaceRef, Operation, ViewPurpose
from fa.feature_flags import FeatureFlags
from fa.inner_loop.coder_loop import SessionOutcome, drive_session
from fa.inner_loop.context import get_current_session
from fa.inner_loop.hooks.base import HookRegistry
from fa.inner_loop.hooks.builtin import SandboxHook
from fa.inner_loop.hooks.intent_guard import IntentGuard
from fa.inner_loop.plan_admission import PlanRef
from fa.inner_loop.pr_draft import PrDraftStore
from fa.inner_loop.registry import ToolRegistry, ToolResult, ToolSpec
from fa.inner_loop.state import EventLog, SessionState
from fa.inner_loop.tools.read_file import build_read_file_tool
from fa.inner_loop.tools.run_bash import build_run_bash_tool
from fa.providers.chain import ProviderChain

logger = logging.getLogger(__name__)

_MAX_TASK_BYTES = 16_000
_MAX_REPORT_CHARS = 8_000
_MAX_CHILD_TURNS = 4
_MAX_CHILD_TOKENS = 1_200
_CHILD_BASH_TIMEOUT_SECONDS = 30

_REPORT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": [
        "task_id",
        "parent_run_id",
        "parent_role",
        "exit_code",
        "terminal_state",
        "summary",
        "notes",
        "evidence",
        "risks",
        "open_questions",
        "artifact_refs",
        "token_usage",
        "duration_ms",
        "next_action",
        "files_changed",
        "patch_diff",
    ],
    "properties": {
        "task_id": {"type": "string", "maxLength": 128},
        "parent_run_id": {"type": "string", "maxLength": 128},
        "parent_role": {"type": "string", "enum": ["chat", "planner", "coder"]},
        "exit_code": {"type": "integer"},
        "terminal_state": {"type": "string", "maxLength": 256},
        "summary": {"type": "string", "maxLength": 1_000},
        "notes": {"type": "array", "maxItems": 4, "items": {"type": "string", "maxLength": 2_000}},
        "evidence": {"type": "array", "maxItems": 8, "items": {"type": "string", "maxLength": 600}},
        "risks": {"type": "array", "maxItems": 8, "items": {"type": "string", "maxLength": 400}},
        "open_questions": {"type": "array", "maxItems": 8, "items": {"type": "string", "maxLength": 400}},
        "artifact_refs": {"type": "array", "maxItems": 8, "items": {"type": "string", "maxLength": 256}},
        "token_usage": {"type": "object"},
        "duration_ms": {"type": "integer", "minimum": 0},
        "next_action": {"type": "string", "enum": ["none", "needs-human"]},
        "files_changed": {"type": "array", "maxItems": 0},
        "patch_diff": {"type": "string", "maxLength": 0},
    },
    "additionalProperties": False,
}
_validate_report = fastjsonschema.compile(_REPORT_SCHEMA)


@dataclass(frozen=True)
class SubagentReport:
    task_id: str
    parent_run_id: str
    parent_role: str
    exit_code: int
    terminal_state: str
    summary: str
    notes: list[str]
    evidence: list[str]
    risks: list[str]
    open_questions: list[str]
    artifact_refs: list[str]
    token_usage: dict[str, Any]
    duration_ms: int
    next_action: str
    files_changed: list[str]
    patch_diff: str

    def to_json(self) -> str:
        payload = asdict(self)
        _validate_report(payload)
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if len(encoded) > _MAX_REPORT_CHARS:
            raise ValueError("managed subagent report exceeds the 8,000-character bound")
        return encoded


def _redact(redactor: Any | None, text: str) -> str:
    if redactor is None:
        return text
    try:
        return redactor.redact(text)
    except Exception as exc:  # noqa: BLE001 - output must be withheld if masking fails
        logger.warning("Managed subagent report redaction failed; withholding output: %s", exc)
        return "[output withheld: redaction failed]"


def _bounded_tool_evidence(outcome: SessionOutcome, redactor: Any | None) -> list[str]:
    evidence: list[str] = []
    for result in outcome.tool_results:
        parts = [result.summary]
        if result.error is not None:
            parts.append(f"error={result.error.code}: {result.error.message}")
        if isinstance(result.result, dict):
            stdout = result.result.get("stdout")
            if isinstance(stdout, str) and stdout:
                parts.append(stdout)
        cleaned = _redact(redactor, " | ".join(parts)).strip()
        if cleaned:
            evidence.append(cleaned[:600])
        if len(evidence) == 8:
            break
    return evidence


def _make_report(
    outcome: SessionOutcome,
    *,
    child_run_id: str,
    parent_run_id: str,
    parent_role: str,
    duration_ms: int,
    redactor: Any | None,
) -> SubagentReport:
    final_text = _redact(redactor, outcome.final_text).strip()
    if not final_text:
        final_text = "[child produced no final message]"
    report = SubagentReport(
        task_id=child_run_id,
        parent_run_id=parent_run_id,
        parent_role=parent_role,
        exit_code=outcome.exit_code,
        terminal_state=outcome.stop_reason[:256],
        summary=final_text[:1_000],
        notes=[final_text[:2_000]],
        evidence=_bounded_tool_evidence(outcome, redactor),
        risks=[] if outcome.exit_code == 0 else [f"child exited {outcome.exit_code}"],
        open_questions=[],
        # Scratch is private to the child view and is not readable by the parent
        # after STOP_VIEW. Do not publish unverifiable host paths as artifacts.
        artifact_refs=[],
        token_usage={},  # SessionOutcome has no usage field; do not invent it.
        duration_ms=max(0, duration_ms),
        next_action="none" if outcome.exit_code == 0 else "needs-human",
        files_changed=[],
        patch_diff="",
    )
    # Trim only evidence first; preserve the actual final message and terminal
    # status. The report remains valid JSON under the documented wire bound.
    while True:
        try:
            report.to_json()
            return report
        except ValueError:
            if report.evidence:
                report = replace(report, evidence=report.evidence[:-1])
            elif report.notes and len(report.notes[0]) > 500:
                report = replace(report, notes=[report.notes[0][: max(500, len(report.notes[0]) - 500)]])
            else:
                raise


def _write_private_report(path: Path, report_json: str) -> None:
    """Create a report artifact with private mode; never write under workspace."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(report_json)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _failure(code: str, message: str, *, retryable: bool = False) -> ToolResult:
    return ToolResult.fail(code, message[:600], retryable=retryable)


# C901: keep reserve -> pin -> drive -> stop -> report ordering visible in one
# lifecycle. Splitting the finally-path across callbacks would obscure which
# failures retain the active-child slot and which are terminal.
def build_managed_subagent_tool(  # noqa: C901
    *,
    workspace_root: Path,
    run_log_dir: Path,
    managed: ManagedExecution,
    parent_state: SessionState,
    parent_role: str,
    chat_chain: ProviderChain | None,
    chat_compactor: ProviderChain | None,
    limits: Any,
    plan_ref: PlanRef | None,
    redactor: Any | None,
) -> ToolSpec:
    """Bind the task-only managed child capability into one production stage."""
    root = Path(workspace_root).resolve()
    parent_log_dir = Path(run_log_dir).resolve()
    try:
        parent_log_dir.relative_to(root)
    except ValueError:
        pass
    else:
        raise ValueError("managed subagent report directory must not be inside the project workspace")
    if parent_role not in {"chat", "planner", "coder"}:
        raise ValueError("managed subagent parent role must be chat, planner, or coder")

    def handler(params: Mapping[str, object]) -> ToolResult:  # noqa: C901
        current = get_current_session()
        if current is not parent_state or parent_state.managed_child:
            return _failure("no_active_session", "managed subagent requires its production parent session")
        task = params.get("task")
        if not isinstance(task, str) or not task.strip():
            return _failure("invalid_params", "task must be non-empty UTF-8 text within the 16,000-byte limit")
        try:
            task_bytes = len(task.encode("utf-8"))
        except UnicodeEncodeError:
            return _failure("invalid_params", "task must be valid UTF-8 text")
        if task_bytes > _MAX_TASK_BYTES:
            return _failure("invalid_params", "task must be non-empty UTF-8 text within the 16,000-byte limit")
        flags = parent_state.feature_flags
        if not isinstance(flags, FeatureFlags) or not flags.subagent_enabled_for(parent_role):
            return _failure("disabled", f"managed subagents are disabled for role {parent_role}")
        spawn_limit = flags.max_subagent_spawns_per_session
        if type(spawn_limit) is not int or spawn_limit < 0:
            return _failure("configuration_error", "managed child spawn limit is invalid")
        if chat_chain is None:
            return _failure("subagent_provider_unavailable", "no configured chat provider chain is available")
        profile = managed.read_only_profile
        if profile is None or profile.interactive:
            return _failure(
                "subagent_profile_unavailable",
                "managed child requires an approved non-interactive READ profile",
            )
        if not parent_state.session_id or parent_state.session_db is None:
            return _failure("session_unavailable", "managed child requires the parent's authoritative session DB")
        if not parent_state.try_reserve_subagent_spawn(spawn_limit):
            return _failure("spawn_limit", "managed child spawn limit reached")
        if not parent_state.try_reserve_active_subagent(max_active=1):
            return _failure("active_child", "a managed child is already active for this session")

        parent_run_id = managed.binding.namespace.run_id
        child_run_id = f"{parent_run_id[:64]}-subagent-{uuid4().hex[:16]}"
        child_namespace = NamespaceRef(
            session_id=parent_state.session_id,
            run_id=child_run_id,
            parent_run_id=parent_run_id,
        )
        child_binding = ExecutionBinding(child_namespace, managed.binding.workspace_id)
        child_dir = parent_log_dir / "subagents" / child_run_id
        grant = None
        port: ClientWorkspacePort | None = None
        executor: ReadOnlyManagedBashExecutor | None = None
        slot_must_remain = False
        pin_attempted = False
        report: SubagentReport | None = None
        report_json: str | None = None
        outcome_result: ToolResult | None = None
        started = time.monotonic()

        try:
            child_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
            event_log = EventLog(
                child_dir / "events.jsonl",
                run_id=child_run_id,
                redactor=redactor,
                session_db=parent_state.session_db,
                session_id=parent_state.session_id,
            )
            pin_attempted = True
            grant = managed.client.pin_reader(
                child_binding,
                revision_id=managed.current_revision_id,
                plan_ref=plan_ref,
                deadline=time.monotonic() + 30.0,
            )
            view = grant.view_ref
            if (
                grant.operation is not Operation.PIN_READER
                or view is None
                or view.access is not Access.READ
                or view.purpose is not ViewPurpose.PROJECT
                or view.owner_run_id != child_run_id
                or view.workspace_id != managed.binding.workspace_id
            ):
                slot_must_remain = True
                raise RuntimeError("supervisor returned an invalid child READ grant")
            port = ClientWorkspacePort(
                managed.client,
                namespace=child_namespace,
                view=view,
                grant=grant,
                cache_dir=child_dir / "read-cache",
            )
            executor = ReadOnlyManagedBashExecutor(
                managed.client,
                namespace=child_namespace,
                view=view,
                grant=grant,
                profile=profile,
                plan_ref=plan_ref,
                controller_root=root,
            )
            child_state = SessionState(
                workspace_root=root,
                session_id=parent_state.session_id,
                run_id=child_run_id,
                log=event_log,
                session_db=parent_state.session_db,
                feature_flags=parent_state.feature_flags,
                bash_executor=executor,
                workspace_io=port,
                managed_child=True,
            )
            child_registry = ToolRegistry()
            read_spec = build_read_file_tool(root, workspace_io=port)
            read_spec = replace(read_spec, description="Read UTF-8 project files from the child's pinned READ view.")
            bash_spec = build_run_bash_tool(
                root,
                timeout_seconds=min(_CHILD_BASH_TIMEOUT_SECONDS, max(1, int(limits.bash_timeout_seconds))),
                managed_executor=executor,
            )
            bash_spec = replace(
                bash_spec,
                description=(
                    "Run one stateless Bash command in the admitted read-only child view. "
                    "Project files are read-only; only private /scratch is writable. "
                    "No persistent shell, parent PTY, workflow, or nested child is available."
                ),
            )
            child_registry.register(read_spec)
            child_registry.register(bash_spec)

            child_hooks = HookRegistry()
            child_hooks.register(SandboxHook(root))
            # A READ view plus the two-tool registry is the mutation authority.
            # Observe-only avoids IntentGuard's host git subprocess and does not
            # reject legitimate private /scratch writes before supervisor EXEC.
            child_hooks.register(
                IntentGuard(
                    repo_root=root,
                    draft_store=PrDraftStore(child_dir / "pr_draft.md"),
                    mode="observe",
                )
            )
            outcome = drive_session(
                task,
                provider_chain=chat_chain,
                compactor_chain=chat_compactor,
                registry=child_registry,
                hooks=child_hooks,
                state=child_state,
                role="subagent",
                acting_family=chat_chain.config.family,
                limits=limits,
                max_turns=_MAX_CHILD_TURNS,
                system_prompt_extra="",
                initial_memory_summary="",
                max_tokens=_MAX_CHILD_TOKENS,
                redactor=redactor,
                output=None,
                pinned_buffer=None,
            )
            report = _make_report(
                outcome,
                child_run_id=child_run_id,
                parent_run_id=parent_run_id,
                parent_role=parent_role,
                duration_ms=int((time.monotonic() - started) * 1000),
                redactor=redactor,
            )
            report_json = report.to_json()
            summary = (
                "managed child completed"
                if outcome.exit_code == 0
                else "managed child returned a bounded failure report"
            )
            outcome_result = ToolResult.ok(summary, result=json.loads(report_json))
        except ExecutionUncertainError:
            # An ambiguous PIN with no grant may have created an unaddressable
            # reader, so retain the active slot. If a grant exists, STOP_VIEW in
            # finally can still prove terminality and safely release the slot.
            if grant is None:
                slot_must_remain = True
            outcome_result = _failure(
                "subagent_pin_uncertain" if grant is None else "subagent_execution_uncertain",
                "managed child authority outcome is uncertain; no host retry was attempted",
            )
        except (ExecutionUnavailableError, ExecutionRejectedError) as exc:
            outcome_result = _failure(
                "subagent_unavailable" if isinstance(exc, ExecutionUnavailableError) else "subagent_denied",
                "managed child was refused or unavailable; no host fallback was attempted",
            )
        except Exception as exc:  # noqa: BLE001 - child failures become bounded tool results
            logger.warning("Managed subagent failed: %s", exc)
            if pin_attempted and grant is None:
                # Unknown failure while PIN_READER was in flight: a reader may
                # exist even though no usable grant reached this process.
                slot_must_remain = True
            outcome_result = _failure("subagent_failed", "managed child failed; no host fallback was attempted")
        finally:
            terminal = grant is None and not slot_must_remain
            if grant is not None:
                if port is not None:
                    port.suspend()
                if executor is not None:
                    executor.suspend()
                if grant.operation is not Operation.PIN_READER or grant.view_ref is None:
                    terminal = False
                else:
                    try:
                        terminal = managed.client.stop_view(
                            child_namespace,
                            view=grant.view_ref,
                            grant=grant,
                            deadline=time.monotonic() + 30.0,
                        )
                    except Exception as exc:  # noqa: BLE001 - uncertainty retains the active slot
                        logger.warning("Managed child terminal cleanup failed: %s", exc)
                        terminal = False
            if terminal and not slot_must_remain:
                parent_state.release_active_subagent()
            else:
                slot_must_remain = True

        if slot_must_remain:
            return _failure(
                "subagent_terminality_unconfirmed",
                "managed child view could not be proven terminal; parent remains fail-closed",
            )
        if report_json is not None:
            try:
                _write_private_report(child_dir / "report.json", report_json)
            except OSError as exc:
                logger.warning("Managed child report persistence failed: %s", exc)
                return _failure("subagent_report_unavailable", "managed child report could not be persisted")
        return outcome_result or _failure("subagent_failed", "managed child produced no result")

    return ToolSpec(
        name="fs_spawn_subagent",
        description=(
            "Delegate one task to a stateless managed child with a pinned read-only project view and private scratch. "
            "The child cannot edit project files, use the parent shell, start workflows, or spawn children."
        ),
        input_schema={
            "type": "object",
            "required": ["task"],
            "properties": {"task": {"type": "string", "minLength": 1, "maxLength": _MAX_TASK_BYTES}},
            "additionalProperties": False,
        },
        permission="workspace",
        handler=handler,
        tags=("fs", "subagent", "managed"),
        max_context_bytes=16_384,
    )


__all__ = ["SubagentReport", "build_managed_subagent_tool"]
