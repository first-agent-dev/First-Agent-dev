"""S13.1 — ``StrictScriptedTransport``: the message-ordering oracle.

Plan: ``worklogs/implementation-plans/PLAN-cli-trace-S13-multi-provider-conformance.md``
§S13.1.

**Why this module exists (D5a / the S11 lesson).** S8's ``_ScriptedTransport``
(``tests/test_cli.py:300``) accepts *any* message order — it only records the
outbound body and returns canned responses. That is exactly how a P1 defect
(I-50) shipped: the resumed workflow stage sent an ``assistant`` message **last**
and Mistral rejected it (``400 code=3230``) while every local test stayed green.

This module builds the oracle that would have caught it and **proves it catches
the real live shape** (S13.0 fixture, ``llm_bodies.json`` entry [6]) before the
S13.3 fix lands.

**The oracle is a pure function** ``validate_message_order(messages) -> list[str]``
over a provider-visible message list, enforcing (per the plan):

- **last role ∈ {user, tool}** (Mistral/Anthropic reject a trailing assistant
  for a non-prefix completion);
- **no ``user`` whose immediate predecessor is a ``tool``** (the second half of
  Mistral 3230, CONF-6);
- **tool pairing** — every ``tool`` result resolves to a declared assistant
  ``tool_calls`` id and vice-versa (the existing
  ``_assert_tool_pairing_invariant`` semantics from ``coder_loop.py:176``),
  which also catches a **dangling tool** (CT5): an assistant carrying an
  unresolved ``tool_calls`` id.

``StrictScriptedTransport`` is a drop-in test transport with the same ``post()``
signature as ``_ScriptedTransport`` (``tests/test_cli.py:315``); it applies the
validator and **fails fast** on a violation — the offline stand-in for the
provider's 400. It is a test helper, **not** production code (the production
conformance finalizer is S13.4).

**Tests labelled per tests-writing skill:**
- **C0p** — ``validate_message_order`` property matrix (assistant-final,
  user-after-tool, dangling-tool, orphan-tool, valid tool-final, fresh).
- **C0p** — the oracle genuinely rejects the live fixture (D5a rule 2: *shown to
  fail before it is trusted*). This one is GREEN and proves the oracle is not
  vacuous.
- **C1 gate (negative proof)** — the real composition root
  ``build_prompt_parts_v2`` + the S13.0 fixture's observations produce an
  assistant-final list on **today's code**, so this test is **RED**. It is the
  S13.1 gate and flips GREEN in S13.3. It is intentionally the only red test.
- **C1 positive control** — a valid tool-final transcript passes unchanged
  (K3 identity): distinguishes "passed" from "never ran".
- **C1 transport fail-fast** — the transport raises on the fixture's shape before
  "HTTP" (CT5 local-fail); passes on a valid transcript.

**Kill-checks:**
- **K1** — revert S13.3 ⇒ the C1 gate test fails.
- **K2** — the oracle is config-independent: no ``allows_trailing_assistant=True``
  can silence an assistant-last rejection (validator has no such knob).
- **K3** — a valid tool-final list is a no-op (no false positive).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import pytest

from fa.inner_loop.prompt_composer import build_prompt_parts_v2
from fa.providers.base import TransportResponse

_FIXTURE = Path(__file__).parent / "fixtures" / "i50_resumed_assistant_last.json"


class MessageOrderError(ValueError):
    """Raised by StrictScriptedTransport when a message list violates ordering."""


def validate_message_order(messages: Sequence[Mapping[str, Any]]) -> list[str]:
    """Return a list of ordering violations (empty ⇒ valid).

    Pure function over a provider-visible message list. Enforces the S13.1 oracle
    rules. No mutation of ``messages``.
    """
    violations: list[str] = []
    if not messages:
        return violations

    last_role = messages[-1].get("role")
    if last_role not in ("user", "tool"):
        violations.append(f"last role must be user or tool for serving, got {last_role!r}")

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


class StrictScriptedTransport:
    """Drop-in test transport enforcing the S13.1 ordering oracle.

    Same ``post()`` signature as ``_ScriptedTransport`` (tests/test_cli.py:315)
    so it can be swapped in wherever a scripted transport is accepted. Records
    each outbound ``json_body`` and raises :class:`MessageOrderError` on an
    ordering violation — the offline stand-in for the provider's 400 (CT5).
    """

    def __init__(self, bodies: list[Mapping[str, Any]] | None = None) -> None:
        self._bodies = list(bodies or [])
        self.calls: list[Mapping[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout_seconds: float,
        transport_retries: int,
    ) -> TransportResponse:
        del url, headers, timeout_seconds, transport_retries
        self.calls.append(dict(json_body))
        messages = json_body.get("messages", [])
        violations = validate_message_order(messages)
        if violations:
            raise MessageOrderError("; ".join(violations))
        if not self._bodies:
            return TransportResponse(status=503, body={})
        return TransportResponse(status=200, body=self._bodies.pop(0))


# --- fixtures / helpers ------------------------------------------------------


def _load_fixture() -> list[dict[str, Any]]:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return cast(list[dict[str, Any]], data)


def _stop_body(text: str = "done") -> Mapping[str, Any]:
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": text, "tool_calls": []},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }


def _tool_call(call_id: str, name: str = "fs.read") -> Mapping[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": "{}"},
    }


# --- C0p: validator matrix ----------------------------------------------------


@pytest.mark.parametrize(
    "label,messages,expected_fragment",
    [
        ("assistant-final (plain text)", [{"role": "user"}, {"role": "assistant"}], "last role"),
        (
            "assistant-final with unresolved tool_calls",
            [{"role": "user"}, {"role": "assistant", "tool_calls": [_tool_call("a1")]}],
            "last role",
        ),
        (
            "user-after-tool",
            [
                {"role": "user"},
                {"role": "assistant", "tool_calls": [_tool_call("a1")]},
                {"role": "tool", "tool_call_id": "a1"},
                {"role": "user"},
            ],
            "user-after-tool",
        ),
        (
            "dangling tool_call (not last)",
            [
                {"role": "user"},
                {"role": "assistant", "tool_calls": [_tool_call("a1")]},
                {"role": "assistant"},
            ],
            "dangling tool_calls",
        ),
        (
            "orphan tool result",
            [{"role": "user"}, {"role": "tool", "tool_call_id": "ghost"}],
            "orphaned tool results",
        ),
    ],
)
def test_validate_rejects_violations(label: str, messages: list[dict[str, Any]], expected_fragment: str) -> None:
    """C0p — each broken shape must be flagged."""
    violations = validate_message_order(messages)
    assert any(expected_fragment in v for v in violations), f"[{label}] got {violations}"


def test_validate_accepts_valid_tool_final() -> None:
    """C0p — a valid tool-final transcript is a no-op (K3 identity)."""
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": "t"},
        {"role": "assistant", "tool_calls": [_tool_call("a1")], "content": ""},
        {"role": "tool", "tool_call_id": "a1", "content": "r"},
    ]
    assert validate_message_order(messages) == []


def test_validate_accepts_fresh_user() -> None:
    """C0p — a fresh (empty-history) request ending on user is valid."""
    assert validate_message_order([{"role": "user", "content": "t"}]) == []


# --- C0p: oracle rejects the live fixture (D5a rule 2, not vacuous) ----------


def test_oracle_flags_live_fixture_assistant_last() -> None:
    """C0p — the oracle genuinely rejects the real I-50 shape.

    The S13.0 fixture is the live coder-stage request that returned code=3230.
    A validator that does NOT flag it is measuring nothing (D5a rule 2: every
    case must be shown to fail before it is trusted). This test is GREEN and is
    the "the instrument works" proof that makes the C1 gate trustworthy.
    """
    fixture = _load_fixture()
    assert fixture[-1]["role"] == "assistant"  # the fixture is the failing shape
    violations = validate_message_order(fixture)
    assert any("last role" in v for v in violations), violations


# --- C1 gate (negative proof) — RED on today's code ---------------------------


def test_composition_resumes_assistant_last__s13_gate() -> None:
    """C1 — negative proof / the S13.1 gate. RED on today's code, GREEN in S13.3.

    Feeds the S13.0 fixture's resumed observations through the **real**
    composition root (``build_prompt_parts_v2``), as the workflow resume path
    does, and asserts the resulting provider-visible message list satisfies the
    ordering oracle.

    On today's code ``build_prompt_parts_v2`` appends the task as ``user`` then
    extends observations, so the list ends on the prior stage's ``assistant`` →
    the validator flags it → ``assert violations == []`` FAILS. That is the
    "reproduces the 400 before the fix" gate. S13.3 (terminal-role-conditional
    task placement) flips this test GREEN.

    Kill-check K1: revert S13.3 ⇒ this fails again.
    """
    fixture = _load_fixture()
    task_msg = fixture[3]
    task = str(task_msg["content"]).removeprefix("Task: ")
    observations = fixture[4:]

    parts, _cache_key = build_prompt_parts_v2(
        base_system="placeholder base system",
        agents_md_map="placeholder agents map",
        tool_defs=[],
        role_id="coder",
        task=task,
        observations=observations,
    )
    messages = list(parts.cacheable) + list(parts.non_cacheable)

    violations = validate_message_order(messages)
    assert violations == [], f"composed resumed transcript violates message ordering (I-50): {violations}"


# --- C1 positive control (K3 identity) ----------------------------------------


def test_composition_fresh_history_task_first_is_valid() -> None:
    """C1 — fresh (empty-history) composition ends on user ⇒ oracle passes.

    Positive control for the fresh path (standalone ``fa run`` / planner stage 1):
    a request whose only non-system message is the task is valid. Guards the
    oracle against over-rejecting the normal case.
    """
    parts, _ = build_prompt_parts_v2(
        base_system="sys",
        agents_md_map="map",
        tool_defs=[],
        role_id="coder",
        task="add a docstring",
        observations=[],
    )
    messages = list(parts.cacheable) + list(parts.non_cacheable)
    assert messages[-1]["role"] == "user"
    assert validate_message_order(messages) == []


def test_transport_passes_valid_tool_final_and_records_call() -> None:
    """C1 — StrictScriptedTransport accepts a valid tool-final transcript.

    Positive control for the transport itself: it must distinguish "passed" from
    "never ran" (D5a rule 1), record the call unchanged (K3 no-op), and return
    the canned 200.
    """
    valid: Mapping[str, Any] = {
        "messages": [
            {"role": "user", "content": "t"},
            {"role": "assistant", "tool_calls": [_tool_call("a1")], "content": ""},
            {"role": "tool", "tool_call_id": "a1", "content": "r"},
        ]
    }
    transport = StrictScriptedTransport([_stop_body("ok")])
    resp = transport.post(
        "http://x",
        headers={},
        json_body=valid,
        timeout_seconds=1,
        transport_retries=0,
    )
    assert resp.status == 200
    assert transport.calls == [valid]


# --- C1 transport fail-fast (CT5 local-fail) ----------------------------------


def test_transport_raises_on_fixture_assistant_last_before_http() -> None:
    """C1 — the transport fails fast on the live I-50 shape (CT5, K2).

    The oracle is config-independent: there is no ``allows_trailing_assistant``
    knob that could make an assistant-last request pass. The failure is raised
    locally, before any "HTTP" round-trip (the bodies list is never consumed).
    """
    fixture = _load_fixture()
    transport = StrictScriptedTransport([_stop_body("must not be served")])
    with pytest.raises(MessageOrderError, match="last role"):
        transport.post(
            "http://x",
            headers={},
            json_body={"messages": fixture},
            timeout_seconds=1,
            transport_retries=0,
        )
    # No HTTP round-trip happened: the single canned body was not consumed.
    assert transport._bodies == [_stop_body("must not be served")]
