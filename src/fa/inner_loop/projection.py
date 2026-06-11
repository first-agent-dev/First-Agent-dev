"""Single boundary from full ``ToolResult`` to model-visible text."""

from __future__ import annotations

import json
from typing import Any

from fa.inner_loop.artifacts import ArtifactStore
from fa.inner_loop.registry import ToolResult, ToolSpec

_ERROR_MESSAGE_CHARS = 500
_ELISION_MARKER = "\n... [elided] ...\n"


def render_tool_payload(value: Any) -> str:
    """Render a tool payload deterministically for inclusion in context."""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=repr)


def _clip_utf8(text: str, max_bytes: int) -> str:
    if max_bytes <= 0:
        return ""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def default_head_tail(value: Any, max_bytes: int) -> str:
    """Default elision strategy: keep head and tail within ``max_bytes``."""
    if max_bytes <= 0:
        return ""
    rendered = render_tool_payload(value)
    encoded = rendered.encode("utf-8")
    if len(encoded) <= max_bytes:
        return rendered
    marker_bytes = _ELISION_MARKER.encode("utf-8")
    if max_bytes <= len(marker_bytes) + 2:
        return _clip_utf8(_ELISION_MARKER, max_bytes)
    remaining = max_bytes - len(marker_bytes)
    head_bytes = remaining // 2
    tail_bytes = remaining - head_bytes
    head = encoded[:head_bytes].decode("utf-8", errors="ignore")
    tail = encoded[-tail_bytes:].decode("utf-8", errors="ignore")
    return f"{head}{_ELISION_MARKER}{tail}"


def project_for_model(spec: ToolSpec, result: ToolResult, artifact_store: ArtifactStore) -> str:
    """Project one full tool result into the provider-visible string.

    This is the sole intended chokepoint between the audit-complete
    ``ToolResult`` and the LLM message stream. The audit log records the
    full result separately; this function enforces each tool's context
    budget and writes an artifact when raw payload is elided.
    """
    if result.error is not None:
        message = result.error.message[:_ERROR_MESSAGE_CHARS]
        return f"ERROR[{result.error.code}]: {message}"

    if result.result is None:
        return result.summary

    rendered = render_tool_payload(result.result)
    if spec.max_context_bytes > 0 and len(rendered.encode("utf-8")) <= spec.max_context_bytes:
        return f"{result.summary}\n\n{rendered}"

    artifact_id = artifact_store.put(result.result)
    if spec.max_context_bytes == 0:
        return f"{result.summary}\n\n[artifact: {artifact_id}]"

    elider = spec.elide or default_head_tail
    elided = _clip_utf8(elider(result.result, spec.max_context_bytes), spec.max_context_bytes)
    return f"{result.summary}\n\n{elided}\n\n[artifact: {artifact_id}]"


__all__ = ["default_head_tail", "project_for_model", "render_tool_payload"]
