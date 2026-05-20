from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

ToolPermission = Literal["read", "workspace", "full"]
ToolHandler = Callable[[Mapping[str, object]], "ToolResult"]


@dataclass(frozen=True)
class ToolError:
    code: str
    message: str
    retryable: bool


@dataclass(frozen=True)
class ToolResult:
    summary: str
    result: Any | None = None
    error: ToolError | None = None
    artifacts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.summary:
            raise ValueError("tool result summary is required")
        if self.error is not None and self.result is not None:
            raise ValueError("tool result cannot contain both result and error")

    @classmethod
    def ok(
        cls,
        summary: str,
        *,
        result: Any | None = None,
        artifacts: tuple[str, ...] = (),
    ) -> ToolResult:
        return cls(summary=summary, result=result, artifacts=artifacts)

    @classmethod
    def fail(
        cls,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        summary: str | None = None,
    ) -> ToolResult:
        return cls(
            summary=summary if summary is not None else message,
            error=ToolError(code=code, message=message, retryable=retryable),
        )


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, object]
    permission: ToolPermission
    handler: ToolHandler
    tags: tuple[str, ...] = ()
    output_schema: dict[str, object] | None = None
    defer_loading: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("tool name is required")
        if not self.description:
            raise ValueError("tool description is required")
        if not self.input_schema:
            raise ValueError("tool input_schema is required")
        if self.permission == "full":
            raise ValueError("permission 'full' is reserved for a future ADR")
        if self.permission not in {"read", "workspace", "full"}:
            raise ValueError(f"unknown tool permission: {self.permission}")


@dataclass(frozen=True)
class ToolCall:
    name: str
    params: Mapping[str, object] = field(default_factory=dict)
    call_id: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("tool call name is required")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def lookup(self, name: str) -> ToolSpec:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"tool is not registered: {name}") from exc

    def dispatch(self, call: ToolCall) -> ToolResult:
        return self.lookup(call.name).handler(call.params)

    def names(self) -> tuple[str, ...]:
        return tuple(self._tools)

    def specs(self) -> tuple[ToolSpec, ...]:
        return tuple(self._tools.values())

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)


__all__ = [
    "ToolCall",
    "ToolError",
    "ToolHandler",
    "ToolPermission",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
]
