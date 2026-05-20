from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from fa.config import DEFAULT_CONFIG_PATH, load_capabilities_from_path
from fa.inner_loop.hooks.base import (
    Decision,
    GuardMiddleware,
    HookPayload,
    LifecyclePoint,
    ObserverMiddleware,
)
from fa.inner_loop.registry import ToolResult
from fa.orchestration.pause import PauseKind, is_paused
from fa.sandbox.bash_gate import evaluate_bash
from fa.tools import DiscoveryEntry, record_discovery, record_gotcha
from fa.verifier import TraceEvent as VerifierTraceEvent
from fa.verifier import VerifierContract, verify_action


@dataclass
class PauseGuard(GuardMiddleware):
    state_dir: Path
    name: str = "pause"
    attaches_to: tuple[LifecyclePoint, ...] = (LifecyclePoint.BETWEEN_ROUNDS,)

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
            if (
                isinstance(command, str)
                and command.split(maxsplit=1)
                and command.split(maxsplit=1)[0] in {"deploy", "restart", "scale"}
                and not caps.ENABLE_SERVER_OPS
            ):
                return Decision.deny("ENABLE_SERVER_OPS is false")
        return Decision.allow()


@dataclass
class SandboxHook(GuardMiddleware):
    workspace_root: Path
    allow_package_install: bool = False
    allow_general_write: bool = True
    name: str = "sandbox"
    attaches_to: tuple[LifecyclePoint, ...] = (LifecyclePoint.BEFORE_TOOL_EXEC,)

    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        del point
        call = payload.tool_call
        if call is None or call.name != "fs.run_bash":
            return Decision.allow()
        command = call.params.get("command")
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


@dataclass
class ApprovalHook(GuardMiddleware):
    require_write_approval: bool = False
    name: str = "approval"
    attaches_to: tuple[LifecyclePoint, ...] = (LifecyclePoint.BEFORE_TOOL_EXEC,)

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
    events: list[dict[str, object]] = field(default_factory=list)
    name: str = "audit"
    attaches_to: tuple[LifecyclePoint, ...] = (LifecyclePoint.AFTER_TOOL_EXEC,)

    def observe(self, point: LifecyclePoint, payload: HookPayload) -> None:
        call = payload.tool_call
        result = payload.tool_result
        self.events.append(
            {
                "point": point.value,
                "tool": "" if call is None else call.name,
                "ok": result is not None and result.error is None,
                "summary": "" if result is None else result.summary,
            }
        )


@dataclass
class VerifierObserver(ObserverMiddleware):
    contracts: Mapping[str, VerifierContract]
    failures: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)
    name: str = "verifier"
    attaches_to: tuple[LifecyclePoint, ...] = (LifecyclePoint.AFTER_TOOL_EXEC,)

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
        if not verification.passed:
            self.failures.append((call.name, verification.reasons))


@dataclass
class LearningObserver(ObserverMiddleware):
    codebase_map_path: Path
    gotchas_path: Path
    name: str = "learning"
    attaches_to: tuple[LifecyclePoint, ...] = (LifecyclePoint.AFTER_TOOL_EXEC,)

    def observe(self, point: LifecyclePoint, payload: HookPayload) -> None:
        del point
        call = payload.tool_call
        result = payload.tool_result
        if call is None or result is None:
            return
        if result.error is not None:
            record_gotcha(
                f"{call.name} failed",
                result.error.message,
                tags=("inner-loop", "tool-error"),
                path=self.gotchas_path,
            )
            return
        record_discovery(
            call.name.replace(".", "/"),
            DiscoveryEntry(
                summary=result.summary,
                pointers=tuple(result.artifacts),
                tags=("inner-loop",),
            ),
            path=self.codebase_map_path,
        )


def default_tool_result_for_denial(reason: str) -> ToolResult:
    return ToolResult.fail("hook_deny", reason, retryable=False)


__all__ = [
    "ApprovalHook",
    "AuditHook",
    "CapabilityGuard",
    "LearningObserver",
    "PauseGuard",
    "SandboxHook",
    "VerifierObserver",
    "default_tool_result_for_denial",
]
