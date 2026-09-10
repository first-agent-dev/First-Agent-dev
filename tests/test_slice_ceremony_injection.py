"""PLAN S5 — the coder-stage slice ceremony reaches the model.

root=coder_loop class=C0/C1 claim=G1,G2/CT3 path=T4,T4b,T4e,T5
oracle=the composer-ready blocks produced for a turn, and the payload the
prompt composer builds from them.
producer-kill-check=deleting the `_ceremony_blocks` call at the injection
site makes test_entry_turn_injects_both_condensates fail; changing the
`turn == 1` guard to inject every turn makes test_later_turns_inject_nothing
fail; re-gating the site on `_is_chat_role` makes the role tests fail.

Why the payload assertions live here and not only at the plumbing layer:
S5a already pinned that a MODE arrives at the loop. The claim THIS slice
makes is different -- that a mode of `enforce` changes the bytes sent to the
provider. A test that stopped at "the helper returned two dicts" would pass
even if nothing ever placed them in the request, which is exactly the
Stage-C failure ADR-11-I9 names (module + unit tests + docs, never attached
to the composition root).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop.coder_loop import (
    CEREMONY_SKILLS,
    _ceremony_blocks,
    should_inject_ceremony,
)
from fa.inner_loop.injections import (
    CODER_SLICE_CEREMONY,
    MODE_ENFORCE,
    MODE_OBSERVE,
    MODE_OFF,
    is_active,
    is_observed,
)
from fa.inner_loop.prompt_composer import (
    build_prompt_parts_v2,
    to_anthropic_request_v2,
    to_openai_request_v2,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


# ── C0: the condensate reader ──────────────────────────────────────────────


class TestCeremonyBlocks:
    def test_reads_both_condensates(self) -> None:
        """T5/GAP4: tests-writing ships alongside feature-planning."""
        blocks = _ceremony_blocks(REPO_ROOT)
        assert len(blocks) == len(CEREMONY_SKILLS) == 2

    def test_order_is_stable(self) -> None:
        """Prompt order must be deterministic across runs (ADR-10-I6)."""
        names = [b["name"] for b in _ceremony_blocks(REPO_ROOT)]
        assert names == ["feature-planning-inject", "tests-writing-inject"]

    def test_blocks_are_composer_shaped(self) -> None:
        for block in _ceremony_blocks(REPO_ROOT):
            assert set(block) >= {"name", "description", "instruction", "body"}
            assert block["body"].strip()

    def test_injects_the_condensate_not_the_full_skill(self) -> None:
        """CT1: the whole point is a ~60-line payload, not a ~970-line one.

        Pinned as an upper bound rather than an exact length so editing the
        condensate does not break the test, while a regression to reading
        SKILL.md (643 and 828 lines) fails loudly.
        """
        for block in _ceremony_blocks(REPO_ROOT):
            assert len(block["body"].splitlines()) < 150

    def test_missing_condensates_degrade_to_empty(self, tmp_path: Path) -> None:
        """G8: advisory. A moved markdown file must not fail a real run."""
        assert _ceremony_blocks(tmp_path) == []

    def test_unreadable_workspace_does_not_raise(self) -> None:
        assert _ceremony_blocks(Path("/nonexistent/workspace")) == []


# ── C1: the gate decides injection from (role, turn, mode) ─────────────────


def _should_inject(role: str, turn: int, mode: str) -> bool:
    """Call the PRODUCTION predicate, never a copy of it.

    An earlier revision re-implemented the condition here. Mutation testing
    proved that worthless: flipping `is_active` to `is_observed` in production
    left every test green, because the tests were grading their own mirror.
    """
    return should_inject_ceremony(role, turn, {CODER_SLICE_CEREMONY.name: mode})


class TestInjectionGate:
    @pytest.mark.parametrize(
        ("role", "turn", "mode", "expected"),
        [
            ("coder", 1, MODE_ENFORCE, True),
            ("coder", 2, MODE_ENFORCE, False),
            ("coder", 1, MODE_OBSERVE, False),
            ("coder", 1, MODE_OFF, False),
            ("planner", 1, MODE_ENFORCE, False),
            ("eval", 1, MODE_ENFORCE, False),
            ("chat", 1, MODE_ENFORCE, False),
        ],
        ids=[
            "coder-entry-enforce",
            "coder-later-turn",
            "coder-observe",
            "coder-off",
            "planner",
            "eval",
            "chat",
        ],
    )
    def test_gate_truth_table(self, role: str, turn: int, mode: str, expected: bool) -> None:
        assert _should_inject(role, turn, mode) is expected

    def test_observe_records_without_injecting(self) -> None:
        """ADR-10-I6 clause 4, at the decision level.

        `observe` must reach the telemetry branch but not the payload branch.
        """
        modes = {CODER_SLICE_CEREMONY.name: MODE_OBSERVE}
        assert is_observed(modes, CODER_SLICE_CEREMONY.name) is True
        assert is_active(modes, CODER_SLICE_CEREMONY.name) is False


# ── C1: the payload actually reaches the composed request ──────────────────


def _compose(skill_blocks: list[dict[str, Any]] | None, family: str = "anthropic") -> str:
    """Build the REAL provider request body and return its serialized text.

    Deliberately goes all the way to `to_*_request_v2` rather than stopping at
    PromptParts: the claim is about bytes sent to the provider, and a block
    that PromptParts holds but the serializer drops would satisfy the weaker
    oracle while the model still never sees the ceremony.
    """
    parts, cache_key = build_prompt_parts_v2(
        base_system="sys",
        agents_md_map="",
        tool_defs=[],
        role_id="coder",
        memory_summary="",
        task="implement the slice",
        observations=[],
        turn_context="",
        skills_conditional=skill_blocks,
    )
    to_request = to_anthropic_request_v2 if family == "anthropic" else to_openai_request_v2
    return repr(to_request(parts, cache_key))


class TestPayloadReachesTheModel:
    @pytest.mark.parametrize("family", ["anthropic", "openai"])
    def test_entry_turn_injects_both_condensates(self, family: str) -> None:
        """T4 + PRODUCER KILL-CHECK for the injection call itself.

        Both provider families, because the request serializers are separate
        code paths and the harness picks one at runtime.
        """
        payload = _compose(_ceremony_blocks(REPO_ROOT), family)
        assert "feature-planning-inject" in payload
        assert "tests-writing-inject" in payload

    def test_ceremony_text_is_present_not_just_the_name(self) -> None:
        """A block whose body was dropped would still carry its name."""
        payload = _compose(_ceremony_blocks(REPO_ROOT))
        assert "BEFORE EDITING GATE" in payload

    def test_no_blocks_means_no_ceremony_text(self) -> None:
        """T4e: the non-entry-turn payload must not carry the bodies."""
        payload = _compose(None)
        assert "feature-planning-inject" not in payload
        assert "BEFORE EDITING GATE" not in payload

    def test_later_turns_inject_nothing(self) -> None:
        """T4e, stated as the production guard sees it."""
        blocks = _ceremony_blocks(REPO_ROOT) if _should_inject("coder", 2, MODE_ENFORCE) else None
        assert blocks is None
        assert "BEFORE EDITING GATE" not in _compose(blocks)


# ── C1: the site is reachable for a workflow coder (the D1 regression) ─────


class TestSiteIsNotChatGated:
    def test_injection_site_is_outside_the_is_chat_role_block(self) -> None:
        """PRODUCER KILL-CHECK for plan defect D1.

        The v1 plan put this inside `if _is_chat_role:`, where it is dead code
        for a workflow coder stage. Asserting on source text is crude, but the
        alternative -- booting a full session -- is covered by the e2e rows,
        and this catches the specific regression cheaply and unambiguously.
        """
        source = (REPO_ROOT / "src" / "fa" / "inner_loop" / "coder_loop.py").read_text(encoding="utf-8")
        site = source.index('if role == "coder" and turn == 1')
        chat_gate = source.index("if _is_chat_role:", site - 4000)
        assert site < chat_gate, "ceremony must be injected BEFORE the chat-only branch"

    def test_chat_path_appends_rather_than_replaces(self) -> None:
        """T4b + PLAN S5 step 1: the two producers must COEXIST.

        They are mutually exclusive today (ceremony needs role=="coder", the
        chat block needs role=="chat"), so a bare assignment loses nothing --
        but it would be correct only by accident, and the accident ends the
        moment a chat-role injection is registered. The plan therefore
        required append; this pins it.
        """
        source = (REPO_ROOT / "src" / "fa" / "inner_loop" / "coder_loop.py").read_text(encoding="utf-8")
        assert "skill_block_for_request = [*(skill_block_for_request or []), render.skill_block]" in source
        assert "skill_block_for_request = [render.skill_block]" not in source


# ── C1: the call site attaches what the gate authorised ────────────────────


class TestCallSiteAttachesTheBlocks:
    """PRODUCER KILL-CHECK for the assignment itself.

    `should_inject_ceremony` returning True is worthless if the call site
    never puts the blocks on `skill_block_for_request`. Mutation testing
    caught exactly that hole: replacing the assignment with `None` left the
    whole suite green, because nothing asserted on the variable that the
    prompt composer actually reads.
    """

    def test_site_assigns_the_blocks_to_the_composer_variable(self) -> None:
        source = (REPO_ROOT / "src" / "fa" / "inner_loop" / "coder_loop.py").read_text(encoding="utf-8")
        assert "skill_block_for_request = list(ceremony_blocks)" in source

    def test_site_reads_the_condensate_file(self) -> None:
        source = (REPO_ROOT / "src" / "fa" / "inner_loop" / "coder_loop.py").read_text(encoding="utf-8")
        assert 'file_name="INJECT.md"' in source

    def test_gate_and_payload_agree_on_enforce(self) -> None:
        """End-to-end at the decision level: enforce authorises, and the
        authorised payload is non-empty and composes into the request."""
        modes = {CODER_SLICE_CEREMONY.name: MODE_ENFORCE}
        assert should_inject_ceremony("coder", 1, modes) is True
        blocks = _ceremony_blocks(REPO_ROOT)
        assert blocks
        assert "BEFORE EDITING GATE" in _compose(blocks)

    def test_observe_authorises_nothing(self) -> None:
        modes = {CODER_SLICE_CEREMONY.name: MODE_OBSERVE}
        assert should_inject_ceremony("coder", 1, modes) is False
        blocks = _ceremony_blocks(REPO_ROOT) if should_inject_ceremony("coder", 1, modes) else None
        assert "BEFORE EDITING GATE" not in _compose(blocks)


# ── L3: the REAL loop, the REAL request a provider receives ────────────────
#
# Everything above stops at the composer. These tests boot `drive_session`
# against a fake provider and assert on `RequestInfo` -- the object a real
# provider would serialize and send. This is the ADR-11-I9 live-path claim:
# remove the production call site and these fail, because nothing else puts
# the ceremony into a request.


def _run_coder_turn(tmp_path: Path, workspace: Path, mode: str | None) -> list[Any]:
    """Drive one real coder session; return the provider's observed requests."""
    from fa.inner_loop.coder_loop import drive_session
    from fa.inner_loop.hooks import HookRegistry, SandboxHook
    from fa.inner_loop.state import EventLog, SessionState
    from fa.providers.chain import ChainConfig, ChainEntry, ProviderChain
    from tests.test_coder_loop import FakeProvider, _make_response, _registry_with_dummy_tool

    provider = FakeProvider([_make_response(text="done", finish_reason="stop")])
    entry = ChainEntry(
        provider="openrouter",
        model="test/model",
        base_url="https://example.invalid/v1",
        api_key_env="TEST_KEY",
        cooldown_seconds=300,
    )
    chain = ProviderChain(
        ChainConfig(role="coder", name="test-model", family="", chain=(entry,)),
        provider_factory=lambda _e: provider,
        env={"TEST_KEY": "k"},
    )
    hooks = HookRegistry()
    hooks.register(SandboxHook(tmp_path))
    log = EventLog(tmp_path / "events.jsonl", run_id="t")
    state = SessionState(workspace_root=workspace, run_id="t", log=log)

    modes = None if mode is None else {CODER_SLICE_CEREMONY.name: mode}
    drive_session(
        "implement the slice",
        provider_chain=chain,
        registry=_registry_with_dummy_tool(),
        hooks=hooks,
        state=state,
        role="coder",
        injection_modes=modes,
    )
    return provider.calls


def _request_text(request: Any) -> str:
    return json.dumps(request.messages, ensure_ascii=False)


class TestLivePathRequest:
    def test_enforce_puts_the_ceremony_in_the_real_request(self, tmp_path: Path) -> None:
        """PRODUCER KILL-CHECK, live path: delete the call site and this fails.

        `state.workspace_root` is the repo so the real condensates resolve;
        the event log goes to tmp_path so nothing is written into the tree.
        """
        calls = _run_coder_turn(tmp_path, REPO_ROOT, MODE_ENFORCE)
        assert calls, "the loop never reached the provider"
        body = _request_text(calls[0])
        assert "BEFORE EDITING GATE" in body
        assert "feature-planning-inject" in body
        assert "tests-writing-inject" in body

    def test_observe_sends_a_byte_identical_request_to_off(self, tmp_path: Path) -> None:
        """The claim that makes `observe` a safe DEFAULT, on the live path.

        Not merely "no gate text": the ENTIRE request must match the `off`
        request, or `observe` would be altering model context by some other
        route while claiming to be inert.
        """
        observe = _request_text(_run_coder_turn(tmp_path / "a", REPO_ROOT, MODE_OBSERVE)[0])
        off = _request_text(_run_coder_turn(tmp_path / "b", REPO_ROOT, MODE_OFF)[0])
        assert observe == off

    def test_unconfigured_matches_off_too(self, tmp_path: Path) -> None:
        """A loop called with no modes at all must not inject."""
        none_modes = _request_text(_run_coder_turn(tmp_path / "c", REPO_ROOT, None)[0])
        off = _request_text(_run_coder_turn(tmp_path / "d", REPO_ROOT, MODE_OFF)[0])
        assert none_modes == off
        assert "BEFORE EDITING GATE" not in none_modes

    def test_enforce_actually_differs_from_off(self, tmp_path: Path) -> None:
        """Guards the two tests above: if every request were identical they
        would pass vacuously."""
        enforce = _request_text(_run_coder_turn(tmp_path / "e", REPO_ROOT, MODE_ENFORCE)[0])
        off = _request_text(_run_coder_turn(tmp_path / "f", REPO_ROOT, MODE_OFF)[0])
        assert enforce != off
        assert len(enforce) > len(off)
