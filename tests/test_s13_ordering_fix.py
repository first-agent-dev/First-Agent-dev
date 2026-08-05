"""S13.3 — I-50: terminal-role-conditional task placement at composition.

Plan: ``worklogs/implementation-plans/PLAN-cli-trace-S13-multi-provider-conformance.md``
§S13.3.

**Why.** A resumed stage inherits the prior stage's history and must not end the
request on an ``assistant`` message (Mistral/Anthropic reject that shape,
400/3230). But a blanket "task after observations" would place a ``user``
directly after a ``tool`` on turn 2+ within a stage (CONF-6). The correct rule,
implemented in ``build_prompt_parts_v2``:

- history empty → task first → final role ``user``;
- history ends ``assistant`` (plain, no tool_calls) → **task last** → final role ``user``;
- history ends ``tool`` → task first → final role ``tool``;
- history ends ``assistant`` carrying unresolved ``tool_calls`` → **fail locally**
  (dangling tool, CT5/K4) — never mask by reordering.

**Tests labelled per tests-writing skill:** C0p matrix (pure composition
function) + a C1 assertion that the live S13.0 fixture's resumed observations now
compose to a final ``user`` role, plus the CT4 cacheable-prefix byte-equality
property.

**Kill-checks:** K1 (revert S13.3 ⇒ assistant-final composes to a trailing
``assistant`` and these tests fail); CT4 (a normalizer that rewrote the cacheable
prefix would break the byte-equality test and silently invalidate every
prompt-cache entry).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from fa.inner_loop.prompt_composer import build_prompt_parts_v2

_FIXTURE = Path(__file__).parent / "fixtures" / "i50_resumed_assistant_last.json"

_BASE = "placeholder base system"
_MAP = "placeholder agents map"


def _load_fixture() -> list[dict[str, Any]]:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return cast(list[dict[str, Any]], data)


def _compose(task: str, observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parts, _ = build_prompt_parts_v2(
        base_system=_BASE,
        agents_md_map=_MAP,
        tool_defs=[],
        role_id="coder",
        task=task,
        observations=observations,
    )
    return list(parts.cacheable) + list(parts.non_cacheable)


def _obs(
    role: str,
    content: str = "",
    tool_calls: Any = None,
    tool_call_id: str | None = None,
) -> dict[str, Any]:
    m: dict[str, Any] = {"role": role, "content": content}
    if tool_calls is not None:
        m["tool_calls"] = tool_calls
    if tool_call_id is not None:
        m["tool_call_id"] = tool_call_id
    return m


# --- C0p: terminal-role matrix -------------------------------------------------


def test_assistant_final_plain__task_last() -> None:
    """assistant-final (no tool_calls) → task last, final role user (the I-50 fix)."""
    history = [_obs("user", "prior instruction"), _obs("assistant", "# Plan: done")]
    msgs = _compose("new task", history)
    assert msgs[-1]["role"] == "user"
    assert msgs[-1]["content"] == "Task: new task"
    # the task now FOLLOWS the assistant observation (resume shape)
    assert msgs[-2] == history[-1]


def test_tool_final__task_first() -> None:
    """tool-final (turn 2+ after a tool round) → task first, final role tool.

    Guards CONF-6: a user must not be injected directly after a tool.
    """
    history = [
        _obs("user", "prior"),
        _obs("assistant", "", tool_calls=[{"id": "a1", "function": {"name": "f", "arguments": "{}"}}]),
        _obs("tool", "result", tool_call_id="a1"),
    ]
    msgs = _compose("next task", history)
    assert msgs[-1]["role"] == "tool"
    # the task appears BEFORE the history (task-first) so it never sits after a tool
    assert msgs[3]["role"] == "user" and msgs[3]["content"] == "Task: next task"


def test_empty__task_first() -> None:
    """fresh (empty history) → task first, final role user."""
    msgs = _compose("do thing", [])
    assert msgs[-1]["role"] == "user"
    assert msgs[-1]["content"] == "Task: do thing"


def test_user_final__task_first() -> None:
    """history ending user → task first (keeps the task before prior turns)."""
    history = [_obs("user", "prior")]
    msgs = _compose("new", history)
    assert msgs[-1]["role"] == "user"
    assert msgs[3]["role"] == "user" and msgs[3]["content"] == "Task: new"


# --- C1: live fixture now composes to a valid final role -----------------------


def test_live_fixture_composes_to_user_last() -> None:
    """C1 — the S13.0 live I-50 fixture now composes to a final `user` role.

    This is the DoD's central assertion: the exact live shape that returned
    400/3230 must, after S13.3, produce a request ending on `user`.
    """
    fixture = _load_fixture()
    # role sequence: [system x3, user(task), assistant, tool, ..., assistant]
    assert fixture[0]["role"] == "system"
    assert fixture[3]["role"] == "user"
    task = str(fixture[3]["content"]).removeprefix("Task: ")
    observations = fixture[4:]

    msgs = _compose(task, observations)
    assert msgs[-1]["role"] == "user"
    assert msgs[-1]["content"] == f"Task: {task}"


# --- C0p: dangling assistant-with-tool_calls fails locally (CT5/K4) -------------


def test_dangling_assistant_tool_calls_fails_locally() -> None:
    """assistant-final carrying unresolved tool_calls → raise locally (CT5/K4).

    Raised as MessageRulesError (a ProviderRequestShapeError) so the loop routes
    it to the graceful `request_shape` exit-2, not an uncaught traceback.
    """
    from fa.providers.message_rules import MessageRulesError

    history = [
        _obs("user", "prior"),
        _obs("assistant", "", tool_calls=[{"id": "a1", "function": {"name": "f", "arguments": "{}"}}]),
    ]
    with pytest.raises(MessageRulesError, match="dangling tool"):
        _compose("new task", history)


# --- CT4: cacheable prefix is byte-identical regardless of task placement -------


def test_ct4_cacheable_prefix_byte_identical() -> None:
    """CT4 — moving the task within non_cacheable leaves cacheable byte-identical.

    The cache key and the cacheable slice must not depend on task/observations
    ordering, or every prompt-cache entry would be invalidated by the S13.3 fix.
    """
    parts_a, key_a = build_prompt_parts_v2(
        base_system=_BASE,
        agents_md_map=_MAP,
        tool_defs=[{"name": "fs.read"}],
        role_id="coder",
        task="alpha",
        observations=[_obs("assistant", "history text")],
    )
    parts_b, key_b = build_prompt_parts_v2(
        base_system=_BASE,
        agents_md_map=_MAP,
        tool_defs=[{"name": "fs.read"}],
        role_id="coder",
        task="beta",  # different task text
        observations=[],  # different history
    )
    # same composition inputs ⇒ same cacheable prefix (byte-identical JSON) and key
    assert json.dumps(parts_a.cacheable, sort_keys=True) == json.dumps(parts_b.cacheable, sort_keys=True)
    assert key_a == key_b
