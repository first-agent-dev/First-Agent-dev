"""Tool registry + ToolSpec / ToolResult / ToolCall contract (ADR-7 §2, §5).

Inner-loop substrate. `ToolRegistry.dispatch` validates ``call.params``
against ``ToolSpec.input_schema`` (JSON Schema Draft 2020-12) before
running the handler, per
[ADR-7 §5 «Input validation»](../../knowledge/adr/ADR-7-inner-loop-tool-registry.md).
Validation failures produce a structured `ToolResult` with
``error.code = "invalid_params"`` and ``retryable = true`` so the model
can correct and retry.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

import fastjsonschema

ToolPermission = Literal["read", "workspace"]
ToolHandler = Callable[[Mapping[str, object]], "ToolResult"]

# ADR-7 §2: ``"full"`` is reserved for a future ADR (full-system access
# tier). v0.1 ships read + workspace only.
_VALID_PERMISSIONS: frozenset[str] = frozenset({"read", "workspace"})


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
        # ADR-7 §2 / Acceptance criterion 2: reject reserved permission tier early.
        # ``"full"`` is reserved for a future ADR; explicit named check produces
        # the canonical message documented in the ADR. Compare via ``cast`` to
        # ``str`` because the dataclass ``Literal`` would otherwise reject the
        # runtime path for callers that bypass the type checker (tests).
        permission_value = str(self.permission)
        if permission_value == "full":
            raise ValueError("permission 'full' is reserved for a future ADR")
        if permission_value not in _VALID_PERMISSIONS:
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
    """Per-process tool registry; one instance lives on the loop driver.

    Owns the ``name -> ToolSpec`` map and the JSON-Schema validator
    cache. ``register()`` validates each spec's ``input_schema`` once at
    insert time so a malformed schema fails fast at session start rather
    than at first tool call. ``dispatch()`` validates per-call params
    via the cached validator and delegates to the spec's handler.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        # fastjsonschema.compile() returns a callable; the signature is
        # ``(data: Any) -> Any`` (returns the validated & coerced data).
        self._validators: dict[str, Callable[[Any], Any]] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        # ADR-7 §5: schemas are loaded ``once per ToolSpec at registry
        # init`` and reused per-call; ``fastjsonschema.compile`` rejects
        # malformed schemas (e.g. ``"type": "strin"`` typos) at registration.
        try:
            compiled = fastjsonschema.compile(spec.input_schema)
        except fastjsonschema.JsonSchemaDefinitionException as exc:
            raise ValueError(f"invalid input_schema for tool {spec.name}: {exc}") from exc
        self._tools[spec.name] = spec
        self._validators[spec.name] = compiled

    def lookup(self, name: str) -> ToolSpec:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"tool is not registered: {name}") from exc

    def validate(self, call: ToolCall) -> ToolResult | None:
        """Validate ``call.params`` against the tool's ``input_schema``.

        Returns ``None`` when params validate cleanly; returns a populated
        ``ToolResult`` with ``error.code = "invalid_params"`` otherwise.
        Exposed so the runtime loop can re-validate after a
        ``Decision.modify`` mutation per ADR-7 §1 step 5 / §5
        \u00abRe-validation after pre_tool mutation\u00bb without going through
        ``dispatch()``.
        """
        try:
            self._validators[call.name](dict(call.params))
        except KeyError as exc:
            raise KeyError(f"tool is not registered: {call.name}") from exc
        except fastjsonschema.JsonSchemaValueException as exc:
            path = "/".join(str(part) for part in exc.path) or "<root>"
            return ToolResult.fail(
                "invalid_params",
                f"{exc.message} at {path}",
                retryable=True,
            )
        return None

    def dispatch(self, call: ToolCall) -> ToolResult:
        validation_failure = self.validate(call)
        if validation_failure is not None:
            return validation_failure
        # Tool handlers MUST catch their own expected exceptions
        # (``OSError`` / ``PermissionError`` / ``ValueError`` /
        # ``subprocess.TimeoutExpired``) and return a structured
        # ``ToolResult``. Anything that escapes that contract is by
        # definition an internal-error path: a crashing handler must
        # not propagate past ``run_session`` and lose the paired
        # ``tool_result`` audit row (ADR-7 \u00a710 Acceptance criterion 8).
        # Catch ``Exception`` (not ``BaseException``) so KeyboardInterrupt
        # / SystemExit still propagate.
        try:
            return self._tools[call.name].handler(call.params)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # Intentional resilience boundary (ADR-7 §10): a crashing tool
            # handler becomes a structured ToolResult.fail so the paired
            # audit row is preserved. Exception (not BaseException) is caught
            # so KeyboardInterrupt / SystemExit still propagate.
            return ToolResult.fail(
                "internal_error",
                f"tool handler raised {type(exc).__name__}: {exc}",
                retryable=False,
            )

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
