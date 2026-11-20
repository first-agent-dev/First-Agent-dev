"""Controller-side validation for one typed, view-bound project-tool EXEC."""

from __future__ import annotations

from typing import Any, Protocol

from fa.execution.client import (
    ExecutionRejectedError,
    ExecutionTimedOutError,
    ExecutionUnavailableError,
    ExecutionUncertainError,
)
from fa.execution.primitives import ExecutionContractError
from fa.execution.protocol import MAX_PROJECT_TOOL_ENVELOPE_BYTES, _loads
from fa.inner_loop.registry import ToolResult


class ManagedProjectToolPort(Protocol):
    """Narrow production capability; it exposes no shell or path controls."""

    def execute(self, tool: str, params: dict[str, Any], *, timeout: int = 25) -> str: ...


def dispatch_managed_project_tool(
    executor: ManagedProjectToolPort,
    tool: str,
    params: dict[str, Any],
) -> ToolResult:
    """Dispatch once and validate the complete cell envelope before returning it."""
    try:
        encoded = executor.execute(tool, params)
    except ExecutionTimedOutError:
        return ToolResult.fail("command_timeout", "managed project tool timed out", retryable=False)
    except ExecutionUnavailableError:
        return ToolResult.fail("execution_unavailable", "managed project tool backend unavailable", retryable=False)
    except ExecutionUncertainError:
        return ToolResult.fail("execution_unknown", "managed project tool result is uncertain", retryable=False)
    except ExecutionRejectedError as exc:
        return ToolResult.fail("execution_rejected", f"managed project tool rejected ({exc.code})", retryable=False)
    except Exception:  # noqa: BLE001 - fail closed; never retry or run on the host
        return ToolResult.fail("project_tool_failed", "managed project tool failed", retryable=False)

    try:
        value = _loads(encoded.encode("ascii"), max_bytes=MAX_PROJECT_TOOL_ENVELOPE_BYTES)
    except (AttributeError, TypeError, UnicodeError, ExecutionContractError):
        return _invalid_envelope()
    if not isinstance(value, dict) or set(value) != {"summary", "result", "error", "artifacts"}:
        return _invalid_envelope()
    summary, result, error, artifacts = value["summary"], value["result"], value["error"], value["artifacts"]
    if not isinstance(summary, str) or not summary or not isinstance(artifacts, list) or artifacts:
        return _invalid_envelope()
    if error is None:
        if not isinstance(result, dict):
            return _invalid_envelope()
        return ToolResult.ok(summary, result=result)
    if (
        result is not None
        or not isinstance(error, dict)
        or set(error) != {"code", "message", "retryable"}
        or not isinstance(error["code"], str)
        or not error["code"]
        or not isinstance(error["message"], str)
        or not error["message"]
        or type(error["retryable"]) is not bool
    ):
        return _invalid_envelope()
    return ToolResult.fail(error["code"], error["message"], retryable=error["retryable"], summary=summary)


def _invalid_envelope() -> ToolResult:
    return ToolResult.fail("project_tool_failed", "managed project tool returned an invalid envelope", retryable=False)
