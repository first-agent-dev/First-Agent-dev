"""Scope-hint routing must not invalidate the cacheable prompt prefix (D7).

**Why this module exists.** ``_estimate_scope_for_chat`` produces a per-task
advisory hint. It was passed to ``drive_session(system_prompt_extra=...)``,
which reaches ``PinnedBuffer.extract_pinned_content(extra_instructions=...)``
(coder_loop.py) and lands in ``build_prompt_parts_v2(agents_md_map=...)``.
``agents_md_map`` is hashed into ``hash_map``, which is a component of the
cache key — so every distinct scope estimate produced a distinct cache key
and the cacheable prefix (base system + AGENTS map + tool defs, the largest
fixed cost in every request) was never reused across tasks.

Measured before the fix: three estimates -> three distinct cache keys.

The fix routes the hint through a dedicated ``turn_context`` parameter into
the NON-cacheable block, alongside ``memory_summary``. ``system_prompt_extra``
keeps carrying the eval adversarial preamble, which is static per role and
therefore correctly cacheable.

Test classes per the tests-writing skill:

- **C0p** — cache-key invariance over the composer's input space.
- **C1** — the live ``_cmd_run`` composition root, asserting on the actual
  provider request body.

**Kill-checks:**
- route ``turn_context`` into ``cacheable`` instead of ``non_cacheable`` →
  ``test_cache_key_is_stable_across_scope_estimates`` fails;
- restore ``system_prompt_extra=... + scope_hint`` in cli.py →
  ``test_live_agents_map_is_identical_across_estimates`` fails;
- drop the ``turn_context`` argument from the composer call in coder_loop →
  ``test_live_hint_reaches_the_model`` fails.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop.prompt_composer import build_prompt_parts_v2
from fa.providers import SecretStore
from fa.providers.base import TransportResponse

_TOOL_DEFS: list[dict[str, Any]] = [{"name": "fs_read_file", "description": "read", "input_schema": {"type": "object"}}]

_HINT_L1 = (
    "## Task Scope Estimate\nDifficulty: 1 (single-file)\nRisk: low | Confidence: 0.8\nRecommended mode: chat_direct\n"
)
_HINT_L3 = (
    "## Task Scope Estimate\nDifficulty: 3 (repo)\nRisk: high | Confidence: 0.8\nRecommended mode: workflow_linear\n"
)


def _key_for(turn_context: str) -> str:
    _parts, cache_key = build_prompt_parts_v2(
        base_system="BASE",
        agents_md_map="AGENTS",
        tool_defs=_TOOL_DEFS,
        role_id="chat",
        memory_summary="",
        task="a task",
        observations=[],
        turn_context=turn_context,
    )
    return cache_key


# ── C0p: cache-key invariance ────────────────────────────────────────────────


def test_cache_key_is_stable_across_scope_estimates() -> None:
    """C0p (kill-check) — the defect itself: differing hints, one cache key."""
    keys = {_key_for(""), _key_for(_HINT_L1), _key_for(_HINT_L3)}
    assert len(keys) == 1, f"scope hint leaked into the cache key: {keys}"


@pytest.mark.parametrize("hint", ["", _HINT_L1, _HINT_L3, "arbitrary per-turn text"])
def test_turn_context_never_changes_the_cache_key(hint: str) -> None:
    """C0p — invariance holds for any turn_context value, not just scope hints."""
    assert _key_for(hint) == _key_for("")


def test_turn_context_lands_in_non_cacheable() -> None:
    """C0p — the hint must still reach the model, in the varying block."""
    parts, _ = build_prompt_parts_v2(
        base_system="BASE",
        agents_md_map="AGENTS",
        tool_defs=_TOOL_DEFS,
        role_id="chat",
        memory_summary="",
        task="a task",
        observations=[],
        turn_context=_HINT_L1,
    )
    non_cacheable_text = "\n".join(str(m["content"]) for m in parts.non_cacheable)
    cacheable_text = "\n".join(str(m["content"]) for m in parts.cacheable)
    assert "Task Scope Estimate" in non_cacheable_text
    assert "Task Scope Estimate" not in cacheable_text


def test_turn_context_precedes_memory_summary() -> None:
    """C0p — ordering is part of the contract: turn framing before history."""
    parts, _ = build_prompt_parts_v2(
        base_system="BASE",
        agents_md_map="AGENTS",
        tool_defs=_TOOL_DEFS,
        role_id="chat",
        memory_summary="prior summary",
        task="a task",
        observations=[],
        turn_context=_HINT_L1,
    )
    blocks = [str(m["content"]) for m in parts.non_cacheable]
    hint_idx = next(i for i, b in enumerate(blocks) if "Task Scope Estimate" in b)
    mem_idx = next(i for i, b in enumerate(blocks) if "Memory summary" in b)
    assert hint_idx < mem_idx


def test_empty_turn_context_adds_no_block() -> None:
    """C0p — failure-observable: no hint means no empty system message."""
    parts, _ = build_prompt_parts_v2(
        base_system="BASE",
        agents_md_map="AGENTS",
        tool_defs=_TOOL_DEFS,
        role_id="chat",
        memory_summary="",
        task="a task",
        observations=[],
        turn_context="",
    )
    assert all(str(m["content"]).strip() for m in parts.non_cacheable)


def test_system_prompt_extra_still_reaches_the_cache_key() -> None:
    """C0p — the eval preamble path is unchanged and STAYS cacheable.

    Guards the other half of the split: static per-role guidance must keep
    landing in the cached prefix, otherwise this fix would have traded one
    cache defect for another.
    """
    base = _key_for("")
    _parts, with_extra = build_prompt_parts_v2(
        base_system="BASE",
        agents_md_map="AGENTS\n\n### STANDING PROFILE GUIDELINES\nadversarial stance",
        tool_defs=_TOOL_DEFS,
        role_id="chat",
        memory_summary="",
        task="a task",
        observations=[],
        turn_context="",
    )
    assert with_extra != base, "agents_md_map must still participate in the cache key"


# ── C1: live composition root ────────────────────────────────────────────────

_CHAT_MODELS_YAML = """\
chat:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: TEST_FA_RUN_KEY
"""

_SECRETS = SecretStore({"TEST_FA_RUN_KEY": "sk-test-x"})


class _CapturingTransport:
    """Records the request bodies a live run sends."""

    def __init__(self) -> None:
        self.bodies: list[dict[str, Any]] = []

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
        self.bodies.append(dict(json_body))
        return TransportResponse(
            status=200,
            body={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "done", "tool_calls": []},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    def system_messages(self) -> list[str]:
        msgs = self.bodies[0].get("messages", [])
        return [str(m.get("content", "")) for m in msgs if m.get("role") == "system"]


def _run_chat(task: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _CapturingTransport:
    from fa.cli import _cmd_run, build_parser

    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    config = workspace / "models.yaml"
    config.write_text(_CHAT_MODELS_YAML, encoding="utf-8")

    transport = _CapturingTransport()
    args = build_parser().parse_args(
        ["run", "-r", "chat", "--config", str(config), "--workspace", str(workspace), task]
    )
    assert _cmd_run(args, transport=transport, secrets=_SECRETS) == 0
    return transport


def test_live_hint_reaches_the_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C1 (kill-check) — the hint is still delivered on the real path.

    Asserted on a system message that is NOT the base role prompt: the chat
    prompt itself documents the mechanism with the literal string
    "## Task Scope Estimate" (prompt.py:927), so matching anywhere would pass
    even with the injection removed entirely.
    """
    transport = _run_chat("fix typo in README", tmp_path, monkeypatch)
    system_messages = transport.system_messages()
    injected = [m for m in system_messages[1:] if "Task Scope Estimate" in m]
    assert injected, f"scope hint absent from injected system messages: {len(system_messages)} blocks"
    assert "Recommended mode:" in injected[0]


def test_live_agents_map_is_identical_across_estimates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C1 (kill-check) — the cacheable AGENTS block does not vary with the task.

    This is the production-visible consequence of D7: the AGENTS.md map is
    hashed into the cache key, so if a differing scope estimate changes it,
    prefix caching is dead for the chat role.
    """
    t_small = _run_chat("fix typo in README", tmp_path / "a", monkeypatch)
    t_large = _run_chat(
        "refactor the entire authentication subsystem across all modules",
        tmp_path / "b",
        monkeypatch,
    )
    agents_small = t_small.system_messages()[1]
    agents_large = t_large.system_messages()[1]
    assert agents_small == agents_large, "AGENTS.md map varies with the scope estimate"
    assert "Task Scope Estimate" not in agents_small


# ── The Anthropic request path (D7 review follow-up) ────────────────────────


def test_anthropic_cache_key_is_stable_with_turn_context() -> None:
    """C0p — the invariant holds on the Anthropic builder too.

    ``to_anthropic_request_v2`` is a separate projection from the OpenAI one
    and was not exercised by the original D7 proof.
    """
    from fa.inner_loop.prompt_composer import to_anthropic_request_v2

    keys = set()
    for hint in ("", _HINT_L1, _HINT_L3):
        parts, cache_key = build_prompt_parts_v2(
            base_system="BASE",
            agents_md_map="AGENTS",
            tool_defs=_TOOL_DEFS,
            role_id="chat",
            memory_summary="prior",
            task="t",
            observations=[],
            turn_context=hint,
        )
        keys.add(to_anthropic_request_v2(parts, cache_key)["_cache_key"])
    assert len(keys) == 1, f"anthropic cache key varies with the scope hint: {keys}"


def test_anthropic_memory_anchor_survives_turn_context() -> None:
    """C0p — inserting turn_context must not displace the memory breakpoint.

    ``to_anthropic_request_v2`` anchors an ephemeral ``cache_control`` on the
    first non-cacheable system message whose content starts with
    ``"Memory summary:\\n"``. ``turn_context`` is inserted immediately before
    that message, so a positional (rather than content-based) anchor would
    land on the hint instead. Also asserts the breakpoint count stays within
    Anthropic's limit of four.
    """
    from fa.inner_loop.prompt_composer import to_anthropic_request_v2

    parts, cache_key = build_prompt_parts_v2(
        base_system="BASE",
        agents_md_map="AGENTS",
        tool_defs=_TOOL_DEFS,
        role_id="chat",
        memory_summary="prior",
        task="t",
        observations=[],
        turn_context=_HINT_L1,
    )
    messages = to_anthropic_request_v2(parts, cache_key)["messages"]
    anchored = [m for m in messages if "cache_control" in m]
    assert len(anchored) <= 4, f"Anthropic allows at most 4 cache breakpoints, got {len(anchored)}"
    memory_anchors = [m for m in anchored if str(m.get("content", "")).startswith("Memory summary:")]
    assert len(memory_anchors) == 1, "the memory-summary cache breakpoint was displaced by turn_context"
