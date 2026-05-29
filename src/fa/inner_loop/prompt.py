"""System prompt + OpenAI-shape tool projection for the M-8 coder driver.

The coder system prompt and the function-tool list projection are
A-bucket residue per the FA-ABC synthesis deep-dive §3 I-2: pure
deterministic functions that run BEFORE the LLM call, never
themselves LLM-driven. The prompt body is a constant string; the
tool list is mechanically projected from
:class:`fa.inner_loop.registry.ToolSpec` instances supplied by the
caller-owned :class:`fa.inner_loop.registry.ToolRegistry`.

Determinism guarantee: :func:`render_tool_specs` and
:func:`build_system_message` are referentially transparent — the
same inputs yield byte-identical outputs across runs. The driver
relies on this so two replays of the same task against the same
provider stub produce byte-identical request bodies (modulo per-call
UUIDs that the chain stamps).

References:
- knowledge/research/fa-abc-synthesis-deep-dive-2026-05.md §3 I-2.
- knowledge/adr/ADR-9-llm-provider-client.md §5 (canonical request shape).
- knowledge/adr/ADR-7-inner-loop-tool-registry.md §2 (ToolSpec contract).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fa.inner_loop.registry import ToolSpec

CODER_SYSTEM_PROMPT = """You are the First-Agent coder.

You drive a deterministic harness. Every response either invokes
one or more tools via the function-calling interface OR signals
task completion with a final natural-language message.

Rules:
- Emit tool calls via the function-calling interface; do not write
  tool invocations as code blocks in prose.
- Each tool's input schema is authoritative. Match field names and
  types exactly; the harness rejects malformed params before the
  tool runs.
- Tool output is mechanical: a `summary` string plus optional
  artifacts. Read it carefully; the same summary surfaces to the
  next turn whether the call succeeded, was denied, or failed.
- When the task is finished, emit one final assistant message
  with no tool calls. The harness ends the session on that turn.
- The harness enforces a turn cap. Plan accordingly; do not retry
  the same failing call without varying the params.
"""


def render_tool_specs(specs: tuple[ToolSpec, ...]) -> tuple[Mapping[str, Any], ...]:
    """Project a ToolSpec tuple into the OpenAI function-tool wire shape.

    Returns a tuple of dicts matching the canonical request-side shape
    consumed by every adapter in :mod:`fa.providers`:

    .. code-block:: python

        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.input_schema,
            },
        }

    The Anthropic adapter re-projects to its native ``input_schema``
    shape at request-build time (see :func:`fa.providers.anthropic._tool_schema`);
    the driver never has to know which adapter is in use.

    Determinism: output ordering matches input ordering; no extra
    fields, no whitespace normalisation, no schema rewriting.
    """
    return tuple(
        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": dict(spec.input_schema),
            },
        }
        for spec in specs
    )


def build_system_message(extra: str = "") -> str:
    """Compose the system prompt, optionally appending ``extra`` text.

    ``extra`` is appended after a blank line. Used by the CLI to inject
    workspace metadata or task-specific context without touching the
    base prompt. Empty ``extra`` returns the canonical prompt verbatim
    so the byte-identity property of the A-bucket layer is preserved
    for tests that exercise the default path.
    """
    if not extra:
        return CODER_SYSTEM_PROMPT
    return f"{CODER_SYSTEM_PROMPT}\n\n{extra}"


__all__ = ["CODER_SYSTEM_PROMPT", "build_system_message", "render_tool_specs"]
