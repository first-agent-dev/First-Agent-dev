"""D1b — the plan grammar the model is *shown* is the grammar the harness can read.

root=``drive_session`` class=C1 claim=D1b/D3 path=live
oracle=the bytes that actually crossed the ``ProviderChain.request`` boundary.

**Why this exists.** Every parser test to date — including the live one at
``tests/test_slice_id_validation.py:199`` — feeds the parser a *fixture* plan.
That proves the parser works on text we wrote. It does not prove the text the
*model* is taught to write is text the parser accepts. I02's verify gate reads
a slice's commands from a model-authored plan, so if those two texts ever drift
the gate silently finds no commands and no-ops — the exact defect I01 was built
to kill, one storey up (ledger E146).

**What is NOT asserted, and why.** The request payload itself does not parse,
by design: the skill body is embedded as JSON-escaped text (``\\n`` literals,
``\\u00a7`` for §), so no ``## SLICE`` heading ever sits at a line start. That is
correct — the parser's input is the markdown plan the model *writes*, never the
prompt it reads. Asserting the payload parses would be asserting a falsehood.
The real risk is drift, so the oracle is identity: the skeleton that crossed the
wire is byte-for-byte the skeleton the parser accepts.

Kill-check target: the ``read_skill_for_injection`` call in
``coder_loop.py``'s L2 block (~:895). Remove it and the payload loses the
skeleton, failing ``test_the_live_payload_carries_the_planning_skill``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from fa.cli import _build_provider_chain
from fa.inner_loop import EventLog, SessionState
from fa.inner_loop.coder_loop import drive_session
from fa.inner_loop.hooks import HookRegistry
from fa.inner_loop.plan_ids import extract_plan_ids
from fa.inner_loop.registry import ToolCall, ToolRegistry
from fa.providers import ProviderChain, UrllibTransport
from tests.fixtures.session_wiring import make_test_chain_config, mock_success_response

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "knowledge" / "skills"

_SKELETON_RE = re.compile(r"PLAN-SKELETON:BEGIN -->\n(.*?)<!-- PLAN-SKELETON:END", re.S)


def _skeleton_of(skill: str) -> str:
    """The ``PLAN-SKELETON`` body of *skill*, exactly as it sits on disk."""
    text = (SKILLS_ROOT / skill / "SKILL.md").read_text(encoding="utf-8")
    match = _SKELETON_RE.search(text)
    assert match is not None, f"{skill}/SKILL.md no longer embeds a PLAN-SKELETON block"
    return match.group(1)


def _live_payload(workspace: Path, *, warm: bool) -> str:
    """Boot the real ``drive_session`` and return the text actually sent upstream.

    Only ``ProviderChain.request`` is mocked (SD-C). A ``src/`` read with no
    write arms expansion level 2, which is the condition under which
    ``coder_loop.py`` performs L2 skill injection; the skills tree is symlinked
    into the workspace because ``default_skills_root`` resolves it from
    ``state.workspace_root``, exactly as production does.
    """
    (workspace / "knowledge").mkdir()
    (workspace / "knowledge" / "skills").symlink_to(SKILLS_ROOT, target_is_directory=True)

    state = SessionState(
        workspace_root=workspace,
        run_id="d1b-live",
        log=EventLog(workspace / "events.jsonl", run_id="d1b-live"),
    )
    state.record_tool_call(ToolCall(name="fs_read_file", params={"path": "src/fa/state.py"}, call_id=""))

    if warm:
        state.record_tool_call(ToolCall(name="fs_read_file", params={"path": "worklogs/PLAN-d3.md"}, call_id="warm"))
    chain = _build_provider_chain(
        make_test_chain_config(role="chat", context_limit=100_000, compaction_threshold=None),
        transport=UrllibTransport(),
        secrets={},
    )
    with patch.object(ProviderChain, "request", return_value=mock_success_response("done")) as request:
        drive_session(
            "d1b live chain",
            provider_chain=chain,
            registry=ToolRegistry(),
            hooks=HookRegistry(),
            state=state,
            role="chat",
            max_turns=1,
            scope_mode="chat_direct",
        )
    assert request.call_count == 1, "the session never reached the provider"
    parts: list[str] = []
    for call in request.call_args_list:
        for message in call.args[0].messages:
            content = message.get("content")
            parts.append(content if isinstance(content, str) else str(content))
    return "\n".join(parts)


@pytest.fixture(scope="module", params=["plan-authoring", "feature-planning"])
def payload(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> tuple[str, str]:
    skill = str(request.param)
    return skill, _live_payload(tmp_path_factory.mktemp("d3-wire"), warm=skill == "feature-planning")


def test_the_live_payload_carries_the_planning_skill(payload: tuple[str, str]) -> None:
    """Non-vacuity: without this, every oracle below would pass over nothing.

    The whole file is worthless if expansion never armed level 2 — the
    assertions would scan a payload that never contained a skill at all and
    report green. This pins that the live path really did inject.
    """
    skill, wire = payload
    assert "ConditionalSkills" in wire, "L2 never armed; the rest of this file would be vacuous"
    assert skill in wire, "the warm/cold planning skill must be selected on the real path"


def test_the_skeleton_the_model_is_shown_is_the_text_the_parser_accepts(payload: tuple[str, str]) -> None:
    """D1b — identity between the taught grammar and the readable grammar.

    The skeleton is compared in its **JSON-encoded** form because that is how it
    crosses the wire; encoding the known-good text and searching for it is the
    assertion that survives the transport without pretending the transport does
    not exist.
    """
    skill, wire = payload
    skeleton = _skeleton_of(skill)
    on_the_wire = json.dumps(skeleton)[1:-1]

    assert on_the_wire in wire, (
        "the skeleton reaching the model is not the skeleton on disk — "
        "the parser's conformance tests are proving something the model never sees"
    )


def test_the_taught_skeleton_yields_slices_carrying_verify_commands(payload: tuple[str, str]) -> None:
    """D1b — and that text is not merely present, it is *useful* to the gate.

    I02's verify gate reads `commands_for(slice)`. A skeleton that parses into
    slices but declares no commands would leave the gate with nothing to run,
    which is a silent no-op wearing a green badge.
    """
    skill, wire = payload
    skeleton = _skeleton_of(skill)
    assert json.dumps(skeleton)[1:-1] in wire, "precondition: this is the text the model was shown"

    ids = extract_plan_ids(skeleton)

    assert ids.slices, "the taught skeleton parses to zero slices; the coverage gate would no-op"
    commands = {slice_id: ids.commands_for(slice_id) for slice_id in ids.slices}
    assert any(commands.values()), f"no slice declares a verify command: {commands}"


@pytest.mark.parametrize("skill", ["plan-authoring", "feature-planning"])
def test_both_selectable_skills_teach_a_readable_grammar(skill: str) -> None:
    """``select_l2_skill`` picks by warmth, so both branches must be readable.

    The live fixture above exercises both branches through the real session.
    This independent static check pins each skill's readable skeleton as well,
    so a payload failure is distinguishable from malformed source grammar.
    """
    ids = extract_plan_ids(_skeleton_of(skill))

    assert ids.slices, f"{skill} teaches a skeleton the parser cannot read"
    assert any(ids.commands_for(s) for s in ids.slices), f"{skill} teaches no verify command"
