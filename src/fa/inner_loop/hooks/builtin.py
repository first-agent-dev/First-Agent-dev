from __future__ import annotations

import base64
import binascii
import os
import re
import urllib.parse
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import override

from fa.config import DEFAULT_CONFIG_PATH, load_capabilities_from_path
from fa.inner_loop.hooks.base import (
    Decision,
    GuardMiddleware,
    HookPayload,
    LifecyclePoint,
    ObserverMiddleware,
)
from fa.inner_loop.registry import ToolResult
from fa.inner_loop.state import EventLog
from fa.observability.redaction import SecretRedactor
from fa.orchestration.pause import PauseKind, is_paused
from fa.sandbox.bash_gate import evaluate_bash
from fa.sandbox.path_containment import is_contained
from fa.tools import DiscoveryEntry, record_discovery, record_gotcha
from fa.verifier import TraceEvent as VerifierTraceEvent
from fa.verifier import VerifierContract, verify_action

# ADR-7 §3 + §8 baseline filesystem tools that the SandboxHook arbitrates
# under the workspace root. ``fs.run_bash`` keeps the three-layer bash gate
# (classifier + validators + path containment); ``fs.read_file`` /
# ``fs.write_file`` use the path-containment layer directly because the
# bash gate is shaped around shell commands.
_FS_PATH_TOOLS: frozenset[str] = frozenset({"fs.read_file", "fs.write_file"})


@dataclass
class PauseGuard(GuardMiddleware):
    state_dir: Path
    name: str = "pause"
    attaches_to: tuple[LifecyclePoint, ...] = (LifecyclePoint.BETWEEN_ROUNDS,)

    @override
    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        del point, payload
        for kind in (PauseKind.RATE_LIMIT, PauseKind.AUTH):
            if is_paused(kind, state_dir=self.state_dir):
                return Decision.deny(f"pause sentinel active: {kind.value}")
        return Decision.allow()


@dataclass
class CapabilityGuard(GuardMiddleware):
    config_path: Path = DEFAULT_CONFIG_PATH
    name: str = "capabilities"
    attaches_to: tuple[LifecyclePoint, ...] = (LifecyclePoint.BEFORE_TOOL_EXEC,)

    @override
    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        del point
        call = payload.tool_call
        if call is None:
            return Decision.allow()
        caps = load_capabilities_from_path(self.config_path).capabilities
        if call.name.startswith("dynamic.") and not caps.ENABLE_DYNAMIC_TOOLS:
            return Decision.deny("ENABLE_DYNAMIC_TOOLS is false")
        if call.name.startswith("mcp.gateway.") and not caps.ENABLE_MCP_GATEWAY_MANAGEMENT:
            return Decision.deny("ENABLE_MCP_GATEWAY_MANAGEMENT is false")
        if call.name.startswith("mcp.server.") and not caps.ENABLE_DYNAMIC_MCP_SERVERS:
            return Decision.deny("ENABLE_DYNAMIC_MCP_SERVERS is false")
        if call.name == "fs.run_bash":
            command = call.params.get("command")
            if isinstance(command, str):
                # Cache the split once \u2014 the prior code called
                # ``command.split(maxsplit=1)`` twice per dispatch
                # (Devin-Review nit on PR #24). ``maxsplit=1`` keeps
                # the cost O(prefix-length) regardless of command size.
                head_tokens = command.split(maxsplit=1)
                if (
                    head_tokens
                    and head_tokens[0] in {"deploy", "restart", "scale"}
                    and not caps.ENABLE_SERVER_OPS
                ):
                    return Decision.deny("ENABLE_SERVER_OPS is false")
        return Decision.allow()


@dataclass
class SandboxHook(GuardMiddleware):
    """ADR-6 §Policy gate at the ``BEFORE_TOOL_EXEC`` hook point.

    Routes each baseline ``fs.*`` tool through the appropriate sandbox
    layer: ``fs.run_bash`` enters the three-layer bash gate; ``fs.read_file``
    and ``fs.write_file`` go through the workspace-root path-containment
    check (ADR-6 §Path containment / Aperant port). Opts in to
    ``revalidates_after_modify`` so that a ``Decision.modify`` returned by
    any earlier guard cannot bypass the sandbox by mutating ``path`` /
    ``command`` to an out-of-workspace target.
    """

    workspace_root: Path
    allow_package_install: bool = False
    allow_general_write: bool = True
    name: str = "sandbox"
    attaches_to: tuple[LifecyclePoint, ...] = (LifecyclePoint.BEFORE_TOOL_EXEC,)
    revalidates_after_modify: bool = True

    @override
    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        del point
        call = payload.tool_call
        if call is None:
            return Decision.allow()
        if call.name == "fs.run_bash":
            return self._handle_bash(call.params.get("command"))
        if call.name in _FS_PATH_TOOLS:
            return self._handle_path(call.params.get("path"))
        return Decision.allow()

    def _handle_bash(self, command: object) -> Decision:
        if not isinstance(command, str):
            return Decision.deny("bash command must be a string")
        decision = evaluate_bash(
            command,
            workspace_root=self.workspace_root,
            allow_package_install=self.allow_package_install,
            allow_general_write=self.allow_general_write,
        )
        if decision.allow:
            return Decision.allow()
        return Decision.deny(decision.reason)

    def _handle_path(self, path: object) -> Decision:
        if not isinstance(path, str) or not path:
            return Decision.deny("path must be a non-empty string")
        containment = is_contained(path, self.workspace_root)
        if containment.contained:
            return Decision.allow()
        return Decision.deny(f"path escapes workspace: {containment.reason}")


@dataclass
class ApprovalHook(GuardMiddleware):
    require_write_approval: bool = False
    name: str = "approval"
    attaches_to: tuple[LifecyclePoint, ...] = (LifecyclePoint.BEFORE_TOOL_EXEC,)

    @override
    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        del point
        call = payload.tool_call
        if not self.require_write_approval or call is None:
            return Decision.allow()
        if call.name in {"fs.write_file", "fs.run_bash"}:
            return Decision.deny("write approval required")
        return Decision.allow()


@dataclass
class AuditHook(ObserverMiddleware):
    """In-memory + optional ``events.jsonl`` audit observer (ADR-7 §8).

    Mirrors each ``AFTER_TOOL_EXEC`` payload into ``events`` for in-process
    inspection. When ``event_log`` is provided the same payload is also
    persisted as an ``actor="hook", kind="audit"`` row — the durable
    projection that subsumes ``~/.fa/state/sandbox.jsonl`` per ADR-7 §7.
    """

    events: list[dict[str, object]] = field(default_factory=list)
    event_log: EventLog | None = None
    name: str = "audit"
    attaches_to: tuple[LifecyclePoint, ...] = (LifecyclePoint.AFTER_TOOL_EXEC,)

    @override
    def observe(self, point: LifecyclePoint, payload: HookPayload) -> None:
        call = payload.tool_call
        result = payload.tool_result
        record: dict[str, object] = {
            "point": point.value,
            "tool": "" if call is None else call.name,
            "ok": result is not None and result.error is None,
            "summary": "" if result is None else result.summary,
        }
        self.events.append(record)
        if self.event_log is None:
            return
        self.event_log.append(
            actor="hook",
            kind="audit",
            content=record,
            tool_name="" if call is None else call.name,
            tool_call_id="" if call is None else call.call_id,
        )


@dataclass
class VerifierObserver(ObserverMiddleware):
    """DSV post-tool gate (R-5).

    For each ``AFTER_TOOL_EXEC`` payload, look up a YAML-loaded
    :class:`VerifierContract` for ``call.name`` and run
    :func:`verify_action` against the trace events derived from the
    ``ToolResult``. In M-1 the only event types emitted are
    ``tool_result`` (always) and ``tool_result`` with the
    error code attached as a ``failure_condition`` (on failure); tool
    bodies will emit richer events when the LLM driver T-2 lands
    observation-event projection, at which point the contracts'
    ``required_trace_events`` lists can be populated without
    restructuring the observer.

    On every contract trip, append one ``kind="verification"`` row to
    ``event_log`` (when set) so the durable trace records *which*
    contract failed and *which* reasons fired — the audit-trail
    surface the future ``override_action: force_failure`` consumer
    reads. ``failures`` keeps an in-memory list for tests + the
    smoke CLI summary.
    """

    contracts: Mapping[str, VerifierContract]
    event_log: EventLog | None = None
    failures: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)
    name: str = "verifier"
    attaches_to: tuple[LifecyclePoint, ...] = (LifecyclePoint.AFTER_TOOL_EXEC,)

    @override
    def observe(self, point: LifecyclePoint, payload: HookPayload) -> None:
        del point
        call = payload.tool_call
        result = payload.tool_result
        if call is None or result is None:
            return
        contract = self.contracts.get(call.name)
        if contract is None:
            return
        events = [
            VerifierTraceEvent(event_type="tool_result", tool=call.name),
        ]
        if result.error is not None:
            events.append(
                VerifierTraceEvent(
                    event_type="tool_result",
                    tool=call.name,
                    failure_conditions=(result.error.code,),
                )
            )
        verification = verify_action(contract, events)
        if verification.passed:
            return
        self.failures.append((call.name, verification.reasons))
        if self.event_log is None:
            return
        # Cast reasons tuple to list so json.dumps serialises predictably;
        # ``override_action`` is copied verbatim from the contract for the
        # downstream force_failure consumer (T-2 LLM driver) to dispatch on.
        self.event_log.append(
            actor="hook",
            kind="verification",
            content={
                "tool": call.name,
                "override_action": verification.override_action,
                "reasons": list(verification.reasons),
                "contract_target": contract.target_action,
            },
            tool_name=call.name,
            tool_call_id=call.call_id,
        )


# ``record_discovery`` rejects any key character outside
# ``[A-Za-z0-9_.\-/]`` (``fa.tools.record_discovery._KEY_PATTERN``).
# Tool params (``path``, ``call_id``) can legally contain spaces,
# semicolons, etc. — the smoke CLI itself uses
# ``"nested dir/smoke; no-inject.txt"``. Sanitise the freeform
# segment so the discovery key always matches the pattern; the
# substitution is lossless for the path-rerouting use case (the
# original path is still stored in ``DiscoveryEntry.pointers``).
_DISCOVERY_KEY_SAFE = re.compile(r"[^A-Za-z0-9_.\-/]")


def _learning_observer_key(call_name: str, params: Mapping[str, object], call_id: str) -> str:
    """Build a path-keyed discovery slug.

    Two-rule scheme designed so two calls to the same tool with
    different ``path`` parameters yield distinct entries — a flat
    ``tool_name`` key collapsed every call onto a single slot and
    defeated R-8's cross-session memory capability. See
    ADR-7 §Sub-amendment 2026-05-21b «path-keyed discovery key».

    1. If ``params["path"]`` is a string: ``"{tool/slug}/{path}"``
       — the natural shape for ``fs.read_file`` / ``fs.write_file``
       and any future tool that touches a workspace path.
    2. Else: ``"{tool/slug}/{call_id}"`` — coarse but cumulative,
       used by ``fs.run_bash`` and any tool without a workspace
       anchor.
    """

    slug = call_name.replace(".", "/")
    path_value = params.get("path")
    suffix = path_value if isinstance(path_value, str) and path_value else call_id
    return f"{slug}/{_DISCOVERY_KEY_SAFE.sub('_', suffix)}"


@dataclass
class LearningObserver(ObserverMiddleware):
    """Filesystem-canon observer (R-8).

    ``codebase_map_path`` / ``gotchas_path`` are the canonical
    ``<workspace>/knowledge/trace/`` artifacts: durable cross-session
    memory checked into the repo alongside ADRs and
    ``exploration_log.md``. The smoke CLI and the T-2 real runtime
    share this path (ADR-7 §Sub-amendment 2026-05-21b «single canon
    root»). The earlier ``.fa/knowledge/trace/`` relocation was
    rejected 2026-05-22 as a spec-bypassing workaround that broke
    the cross-session memory invariant — see exploration_log Q-7
    Rejected blocks.

    ``now`` injects a fixed ISO timestamp into both writers; the
    smoke CLI pins it to ``"2026-05-21T00:00:00Z"`` so repeated
    smoke runs produce byte-identical artifacts (paired with the
    seed baseline at ``knowledge/trace/codebase_map.json`` and the
    ``gotchas.md`` dedup, this keeps ``git status`` clean across
    smoke invocations). ``None`` falls through to the writer-side
    ``_now_iso_z()`` default — that is the T-2 real-runtime mode,
    where live timestamps are required for genuine provenance.
    """

    codebase_map_path: Path
    gotchas_path: Path
    name: str = "learning"
    attaches_to: tuple[LifecyclePoint, ...] = (LifecyclePoint.AFTER_TOOL_EXEC,)
    now: str | None = None
    redactor: SecretRedactor | None = None

    @override
    def observe(self, point: LifecyclePoint, payload: HookPayload) -> None:
        del point
        call = payload.tool_call
        result = payload.tool_result
        if call is None or result is None:
            return
        if result.error is not None:
            error_msg = (
                self.redactor.redact(result.error.message)
                if self.redactor is not None
                else result.error.message
            )
            record_gotcha(
                f"{call.name} failed",
                error_msg,
                tags=("inner-loop", "tool-error", call.name),
                path=self.gotchas_path,
                now=self.now,
            )
            return
        summary = (
            self.redactor.redact(result.summary) if self.redactor is not None else result.summary
        )
        record_discovery(
            _learning_observer_key(call.name, call.params, call.call_id),
            DiscoveryEntry(
                summary=summary,
                pointers=tuple(result.artifacts),
                tags=("inner-loop", call.name),
            ),
            path=self.codebase_map_path,
            now=self.now,
        )


@dataclass
class SecretGuard(GuardMiddleware):
    """Prevent API key leakage via fs.write_file or fs.run_bash.

    Detects raw secrets, base64-encoded secrets, URL-encoded secrets,
    and common shell/env variable interpolation patterns.
    """

    secrets: frozenset[str] = field(default_factory=frozenset)
    name: str = "secret_guard"
    attaches_to: tuple[LifecyclePoint, ...] = (LifecyclePoint.BEFORE_TOOL_EXEC,)

    # Regex for candidate base64 words (minimum 10 chars to avoid false positives)
    _B64_RE = re.compile(r"[A-Za-z0-9+/=]{10,}")
    # Interpolation patterns: $VAR, ${VAR}, {{VAR}}
    _INTERP_RE = re.compile(
        r"\$[A-Za-z_][A-Za-z0-9_]*"
        r"|\$\{[A-Za-z_][A-Za-z0-9_]*\}"
        r"|\{\{[A-Za-z_][A-Za-z0-9_]*\}\}"
    )

    def _check_text(self, text: str) -> bool:
        """Return True if ``text`` contains a secret in any form."""
        for secret in self.secrets:
            # 1. Raw exact match
            if secret in text:
                return True
            # 2. Base64-encoded secret literal
            b64_secret = base64.b64encode(secret.encode()).decode()
            if b64_secret in text:
                return True
            # 3. URL-encoded secret literal
            url_secret = urllib.parse.quote(secret)
            if url_secret in text:
                return True
            # 4. URL-decoded text
            if secret in urllib.parse.unquote(text):
                return True

        # 5. Base64 substrings in text (non-literal encoding)
        for candidate in self._B64_RE.findall(text):
            try:
                decoded = base64.b64decode(candidate, validate=True).decode(
                    "utf-8", errors="replace"
                )
            except (ValueError, binascii.Error):
                continue
            for secret in self.secrets:
                if secret in decoded:
                    return True

        # 6. Interpolation resolved
        for match in self._INTERP_RE.finditer(text):
            raw = match.group()
            # Strip prefixes/suffixes to get bare variable name
            var_name = raw.strip("${}")
            resolved = os.environ.get(var_name, "")
            if resolved and resolved in self.secrets:
                return True

        return False

    @override
    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        del point
        call = payload.tool_call
        if call is None:
            return Decision.allow()
        if call.name == "fs.write_file":
            content = call.params.get("content", "")
            if isinstance(content, str) and self._check_text(content):
                return Decision.deny("secret leak detected in fs.write_file content")
        if call.name == "fs.run_bash":
            command = call.params.get("command", "")
            if isinstance(command, str):
                # Encoded / interpolated detection applies to ALL commands
                if self._check_text(command):
                    return Decision.deny("secret leak detected in fs.run_bash command")
                # Raw exact-match kept behind dangerous-keyword gate for
                # performance: only when the command explicitly references
                # env inspection.
                dangerous = {"printenv", "env", "echo $"}
                if any(d in command for d in dangerous):
                    for secret in self.secrets:
                        if secret in command:
                            return Decision.deny("secret leak detected in fs.run_bash command")
        return Decision.allow()


def default_tool_result_for_denial(reason: str) -> ToolResult:
    return ToolResult.fail("hook_deny", reason, retryable=False)


__all__ = [
    "ApprovalHook",
    "AuditHook",
    "CapabilityGuard",
    "LearningObserver",
    "PauseGuard",
    "SandboxHook",
    "SecretGuard",
    "VerifierObserver",
    "default_tool_result_for_denial",
]
