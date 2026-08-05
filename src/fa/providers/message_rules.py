"""Per-provider message-shape conformance rules (S13.4, D2).

ADR-9 §5 + S13 plan ``MessageRules``: capability records attached to each
:class:`~fa.providers.registry.ProviderSpec`, never provider-name branching.
Each field describes a *capability* of the provider's serving surface — the same
lesson as S12's probes: describe the capability, not the platform.

The conformance pass is the single, unbypassable finalizer invoked at the chain
chokepoint (``chain.py:368``, immediately before ``provider.request``). It
**validates** message ordering/pairing and **minimally normalises** sampling
(the I-48 ``top_p`` case). It never invents content (CT3) and never rewrites the
cacheable prefix (CT4) — it only inspects/enforces the provider-visible message
list and, when a rule requires it, sets an explicit sampling field that FA was
otherwise omitting.

Design principles (from the S13 plan §D1/D2):
- **Composition** (``prompt_composer`` / ``coder_loop``) produces a correct,
  provider-neutral message list. **This finalizer** is the safety net and the
  discovery instrument — it catches a *next* provider's quirk without a live
  outage.
- Tool-pairing validation is **unconditional**, not a flag (CT5): a dangling
  ``tool_call_id`` is a real state bug and must fail locally, before HTTP.

Two capabilities that are *recorded* but whose enforcement lives at the chain
call-site via this module:

- ``allows_trailing_assistant`` — OpenAI-shaped endpoints tolerate a trailing
  ``assistant`` message; Mistral/Anthropic reject it (400/3230). FA's composition
  (S13.3) no longer *emits* assistant-final requests, so this rule is a guard:
  when ``False``, an assistant-final request is a violation that must never reach
  the wire.
- ``requires_user_after_tool`` — ``False`` (the default) means a ``user``
  immediately after a ``tool`` is a violation (Mistral 3230's other half, CONF-6).
- ``requires_top_p_one_when_greedy`` — when set and ``temperature == 0``, send
  ``top_p=1`` explicitly rather than letting the server apply a conflicting
  default (I-48 / ``mistral-medium-2604``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from fa.providers.base import RequestInfo
from fa.providers.errors import ProviderRequestShapeError


@dataclass(frozen=True)
class MessageRules:
    """Capability record for one provider's message/sampling surface.

    Defaults are the strict-safe values: every capability defaults to the
    behaviour a strict validator (Mistral/Anthropic) requires, so an unset or
    new provider cannot accidentally send a shape a strict provider rejects
    (K6). Each field is a capability, not a platform name.
    """

    allows_trailing_assistant: bool = False
    requires_user_after_tool: bool = False
    requires_top_p_one_when_greedy: bool = False


class MessageRulesError(ProviderRequestShapeError):
    """Raised when a request violates a provider's ``MessageRules``.

    Raised **locally, before HTTP** (CT5): the request must not reach the wire
    with a shape the provider will reject. Subclasses
    :class:`~fa.providers.errors.ProviderRequestShapeError` so it flows through
    the existing fail-fast path (the coder-loop maps ``ProviderRequestShapeError``
    to ``stop_reason="request_shape"`` / exit 2), while remaining a distinct type
    so tests can assert precisely that the *local* conformance gate — not the
    remote provider — rejected the request.
    """

    def __init__(self, message: str) -> None:
        # Local conformance failure: no HTTP status is meaningful. Status 400
        # keeps parity with the 400/422 fail-fast contract so downstream
        # rendering treats it as a request-shape error.
        super().__init__(f"message_rules_violation: {message}", status=400)


def validate_message_order(
    messages: Sequence[Mapping[str, Any]],
    *,
    allows_trailing_assistant: bool,
    requires_user_after_tool: bool = False,
) -> list[str]:
    """Return a list of ordering/pairing violations for ``messages`` (empty ⇒ valid).

    Pure and deterministic. Mirrors the S13.1 oracle rules (the strict scripted
    transport enforces the same ordering) so the CI oracle and the production
    finalizer can never disagree (S13.4d / K2). No mutation.

    ``requires_user_after_tool`` is the CONF-6 capability record: when True, the
    provider *requires* (and therefore tolerates) a ``user`` immediately after a
    ``tool`` result, so that transition is NOT flagged. Default False (the
    strict-safe value) keeps the rejection, matching Mistral/Anthropic.
    """
    violations: list[str] = []
    if not messages:
        return violations

    last_role = messages[-1].get("role")
    if last_role == "assistant" and not allows_trailing_assistant:
        violations.append(f"last role must be user or tool for serving, got {last_role!r}")
    elif last_role not in ("user", "tool", "assistant"):
        violations.append(f"unknown final role {last_role!r}")

    if not requires_user_after_tool:
        for i in range(1, len(messages)):
            if messages[i].get("role") == "user" and messages[i - 1].get("role") == "tool":
                violations.append(f"user at index {i} directly follows a tool message (user-after-tool)")

    declared: set[str] = set()
    resolved: set[str] = set()
    for msg in messages:
        role = msg.get("role")
        if role == "assistant":
            for call in msg.get("tool_calls") or ():
                declared.add(str(call.get("id") or ""))
        elif role == "tool":
            resolved.add(str(msg.get("tool_call_id") or ""))

    missing_result = declared - resolved
    orphan_result = resolved - declared
    if missing_result:
        violations.append(f"dangling tool_calls with no tool result: {sorted(missing_result)}")
    if orphan_result:
        violations.append(f"orphaned tool results with no declaring assistant tool_call: {sorted(orphan_result)}")

    return violations


def validate_and_normalize(
    request: RequestInfo,
    rules: MessageRules,
    *,
    effective_temperature: float | None = None,
    effective_top_p: float | None = None,
) -> RequestInfo:
    """Validate ``request.messages`` against ``rules`` and minimally normalise sampling.

    Returns a (possibly ``replace``-ed) :class:`RequestInfo` ready to be sent. The
    only mutation is setting an explicit ``top_p`` when a rule requires it and FA
    had omitted it; everything else is validation that either passes or raises
    :class:`MessageRulesError` locally.

    ``effective_temperature`` / ``effective_top_p`` are the chain-resolved values
    (role sampling defaults applied) so the finalizer sees the exact sampling the
    provider would receive, not just what the caller set.
    """
    violations = validate_message_order(
        request.messages,
        allows_trailing_assistant=rules.allows_trailing_assistant,
        requires_user_after_tool=rules.requires_user_after_tool,
    )
    if violations:
        raise MessageRulesError("; ".join(violations))

    normalized = request
    if rules.requires_top_p_one_when_greedy:
        temp = effective_temperature if effective_temperature is not None else request.temperature
        top_p = effective_top_p if effective_top_p is not None else request.top_p
        if temp == 0 and top_p is None:
            normalized = replace(normalized, top_p=1.0)
    return normalized
