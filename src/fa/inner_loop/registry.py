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
from typing import Any, Literal, NoReturn

import fastjsonschema  # type: ignore[import-untyped]

ToolPermission = Literal["read", "workspace"]
ToolHandler = Callable[[Mapping[str, object]], "ToolResult"]
ToolElider = Callable[[Any, int], str]

# ADR-7 §2: ``"full"`` is reserved for a future ADR (full-system access
# tier). v0.1 ships read + workspace only.
_VALID_PERMISSIONS: frozenset[str] = frozenset({"read", "workspace"})

_PORTABLE_SCHEMA_TYPES: frozenset[str] = frozenset({"object", "array", "string", "integer", "number", "boolean"})
_MISSING = object()
_PORTABLE_SCHEMA_KEYS: frozenset[str] = frozenset(
    {
        "type",
        "properties",
        "required",
        "items",
        "enum",
        "description",
        "default",
        "minLength",
        "maxLength",
        "minimum",
        "maximum",
        "additionalProperties",
    }
)


class ToolSchemaPortabilityError(ValueError):
    """A locally valid tool schema is outside the provider-portable profile."""

    def __init__(self, tool_name: str, path: str, reason: str) -> None:
        self.tool_name = tool_name
        self.path = path or "/"
        self.reason = reason
        super().__init__(f"non-portable tool schema: tool={tool_name} path={self.path} reason={reason}")


def _pointer(path: str, token: object) -> str:
    escaped = str(token).replace("~", "~0").replace("/", "~1")
    return f"{path}/{escaped}" if path else f"/{escaped}"


def _portable_error(tool_name: str, path: str, reason: str) -> NoReturn:
    raise ToolSchemaPortabilityError(tool_name, path, reason)


def _value_matches_type(value: object, schema_type: str) -> bool:
    if schema_type == "object":
        return isinstance(value, Mapping)
    if schema_type == "array":
        return isinstance(value, list)
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if schema_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if schema_type == "boolean":
        return isinstance(value, bool)
    return False


def _validate_schema_header(
    tool_name: str,
    schema: Mapping[str, object],
    *,
    path: str,
    root: bool,
) -> str:
    for key in sorted(schema, key=str):
        if not isinstance(key, str) or key not in _PORTABLE_SCHEMA_KEYS:
            _portable_error(tool_name, _pointer(path, key), "unsupported_keyword")
    schema_type = schema.get("type")
    type_path = _pointer(path, "type")
    if not isinstance(schema_type, str) or schema_type not in _PORTABLE_SCHEMA_TYPES:
        _portable_error(tool_name, type_path, "unsupported_type")
    if root and schema_type != "object":
        _portable_error(tool_name, type_path, "root_not_object")
    description = schema.get("description", _MISSING)
    if description is not _MISSING and not isinstance(description, str):
        _portable_error(tool_name, _pointer(path, "description"), "invalid_description")
    return schema_type


def _validate_schema_properties(
    tool_name: str,
    schema: Mapping[str, object],
    *,
    path: str,
    schema_type: str,
) -> set[str]:
    properties_value = schema.get("properties", _MISSING)
    if properties_value is _MISSING:
        return set()
    properties_path = _pointer(path, "properties")
    if schema_type != "object" or not isinstance(properties_value, Mapping):
        _portable_error(tool_name, properties_path, "invalid_properties")
    property_names: set[str] = set()
    for property_name in sorted(properties_value, key=str):
        property_schema = properties_value[property_name]
        if not isinstance(property_name, str) or not isinstance(property_schema, Mapping):
            _portable_error(tool_name, properties_path, "invalid_properties")
        property_names.add(property_name)
        _validate_portable_schema_node(
            tool_name,
            property_schema,
            path=_pointer(properties_path, property_name),
            root=False,
        )
    return property_names


def _validate_schema_required(
    tool_name: str,
    schema: Mapping[str, object],
    *,
    path: str,
    schema_type: str,
    property_names: set[str],
) -> None:
    required_value = schema.get("required", _MISSING)
    if required_value is _MISSING:
        return
    required_path = _pointer(path, "required")
    if schema_type != "object" or not isinstance(required_value, list):
        _portable_error(tool_name, required_path, "invalid_required")
    seen_required: set[str] = set()
    for index, required_name in enumerate(required_value):
        item_path = _pointer(required_path, index)
        if not isinstance(required_name, str) or required_name in seen_required:
            _portable_error(tool_name, item_path, "invalid_required")
        if required_name not in property_names:
            _portable_error(tool_name, item_path, "required_unknown_property")
        seen_required.add(required_name)


def _validate_schema_children(
    tool_name: str,
    schema: Mapping[str, object],
    *,
    path: str,
    schema_type: str,
) -> None:
    items_value = schema.get("items", _MISSING)
    items_path = _pointer(path, "items")
    if schema_type == "array":
        if not isinstance(items_value, Mapping):
            _portable_error(tool_name, items_path, "invalid_items")
        _validate_portable_schema_node(tool_name, items_value, path=items_path, root=False)
    elif items_value is not _MISSING:
        _portable_error(tool_name, items_path, "invalid_items")

    additional_value = schema.get("additionalProperties", _MISSING)
    if additional_value is _MISSING:
        return
    additional_path = _pointer(path, "additionalProperties")
    if schema_type != "object":
        _portable_error(tool_name, additional_path, "invalid_additional_properties")
    if isinstance(additional_value, Mapping):
        _validate_portable_schema_node(tool_name, additional_value, path=additional_path, root=False)
    elif not isinstance(additional_value, bool):
        _portable_error(tool_name, additional_path, "invalid_additional_properties")


def _validate_schema_values(
    tool_name: str,
    schema: Mapping[str, object],
    *,
    path: str,
    schema_type: str,
) -> None:
    enum_value = schema.get("enum", _MISSING)
    if enum_value is not _MISSING:
        enum_path = _pointer(path, "enum")
        if schema_type in {"object", "array"} or not isinstance(enum_value, list) or not enum_value:
            _portable_error(tool_name, enum_path, "invalid_enum")
        for index, enum_item in enumerate(enum_value):
            if not _value_matches_type(enum_item, schema_type):
                _portable_error(tool_name, _pointer(enum_path, index), "invalid_enum")

    default_value = schema.get("default", _MISSING)
    if default_value is not _MISSING and not _value_matches_type(default_value, schema_type):
        _portable_error(tool_name, _pointer(path, "default"), "invalid_default")


def _validate_schema_bounds(
    tool_name: str,
    schema: Mapping[str, object],
    *,
    path: str,
    schema_type: str,
) -> None:
    min_length = schema.get("minLength", _MISSING)
    max_length = schema.get("maxLength", _MISSING)
    for keyword, value in (("minLength", min_length), ("maxLength", max_length)):
        invalid = value is not _MISSING and (
            schema_type != "string" or not isinstance(value, int) or isinstance(value, bool) or value < 0
        )
        if invalid:
            _portable_error(tool_name, _pointer(path, keyword), "invalid_bound")
    if isinstance(min_length, int) and isinstance(max_length, int) and min_length > max_length:
        _portable_error(tool_name, _pointer(path, "maxLength"), "invalid_bound")

    minimum = schema.get("minimum", _MISSING)
    maximum = schema.get("maximum", _MISSING)
    for keyword, value in (("minimum", minimum), ("maximum", maximum)):
        invalid = value is not _MISSING and (
            schema_type not in {"integer", "number"} or not isinstance(value, (int, float)) or isinstance(value, bool)
        )
        if invalid:
            _portable_error(tool_name, _pointer(path, keyword), "invalid_bound")
    if (
        isinstance(minimum, (int, float))
        and not isinstance(minimum, bool)
        and isinstance(maximum, (int, float))
        and not isinstance(maximum, bool)
        and minimum > maximum
    ):
        _portable_error(tool_name, _pointer(path, "maximum"), "invalid_bound")


def _validate_portable_schema_node(
    tool_name: str,
    schema: Mapping[str, object],
    *,
    path: str,
    root: bool,
) -> None:
    schema_type = _validate_schema_header(tool_name, schema, path=path, root=root)
    property_names = _validate_schema_properties(tool_name, schema, path=path, schema_type=schema_type)
    _validate_schema_required(
        tool_name,
        schema,
        path=path,
        schema_type=schema_type,
        property_names=property_names,
    )
    _validate_schema_children(tool_name, schema, path=path, schema_type=schema_type)
    _validate_schema_values(tool_name, schema, path=path, schema_type=schema_type)
    _validate_schema_bounds(tool_name, schema, path=path, schema_type=schema_type)


def validate_tool_schema_portability(tool_name: str, schema: Mapping[str, object]) -> None:
    """Fail closed when a provider-visible ToolSpec is outside PTS-v1."""

    _validate_portable_schema_node(tool_name, schema, path="", root=True)


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
    max_context_bytes: int = 4096
    elide: ToolElider | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("tool name is required")
        if not self.description:
            raise ValueError("tool description is required")
        if not self.input_schema:
            raise ValueError("tool input_schema is required")
        if self.max_context_bytes < 0:
            raise ValueError("max_context_bytes must be >= 0")
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
        validate_tool_schema_portability(spec.name, spec.input_schema)
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
        # Waiver: resilience boundary (ADR-7 §10) — handler crash becomes a
        # structured ToolResult.fail.
        except Exception as exc:  # noqa: BLE001
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
    "ToolElider",
    "ToolError",
    "ToolHandler",
    "ToolPermission",
    "ToolRegistry",
    "ToolResult",
    "ToolSchemaPortabilityError",
    "ToolSpec",
    "validate_tool_schema_portability",
]
