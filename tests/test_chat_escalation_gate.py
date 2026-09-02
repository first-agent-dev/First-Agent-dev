"""S7 / CT8 + CT9: the chat escalation gate.

The claim under test is that a *capability* changes, not that a prompt says
something. So the oracle everywhere here is the exact tool-name set of a
registry built through the same function ``fa run`` calls
(``_build_run_tool_registry``), never a substring of a description or a log
line standing in for behaviour.

Kill-checks (each verified to discriminate before this file was committed):
  - remove the ``_apply_escalation_gate`` call    -> test_gate_withholds_* fail
  - GATE_MIN_CONFIDENCE 0.8 -> 0.0                -> test_medium_confidence_* fails
  - ignore ``gate_enabled``                       -> test_operator_toggle_* fails
  - drop the ``role != "chat"`` guard             -> test_non_chat_roles_* fails
  - drop the WARNING                              -> test_gate_warns_* fails
  - withhold ``invoke_workflow`` too              -> test_escalation_path_* fails
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from fa.cli import _apply_escalation_gate, _build_run_tool_registry, _resolve_scope_point
from fa.inner_loop.pr_draft import PrDraftStore
from fa.inner_loop.routing import (
    GATE_MIN_CONFIDENCE,
    WITHHELD_WRITE_TOOLS,
    should_withhold_write_tools,
)
from fa.inner_loop.scope_estimator import OperatingPoint, estimate_scope

# A task the estimator rates workflow_linear at its top confidence. Asserted in
# test_fixture_tasks_still_produce_the_estimates_these_tests_assume so this file
# fails loudly if the estimator's classification drifts, rather than silently
# testing the ungated path forever after.
REPO_SCALE_TASK = "refactor the entire codebase to use async everywhere and migrate all tests"
SIMPLE_TASK = "fix a typo in README.md"
MEDIUM_TASK = "rename TomlDecoder everywhere"


def _build(
    workspace: Path,
    *,
    task: str = REPO_SCALE_TASK,
    role: str = "chat",
    gate_enabled: bool = True,
) -> tuple[str, ...]:
    """Build a registry through the live ``fa run`` path; return its tool names."""
    point = _resolve_scope_point(role, task)
    registry = _build_run_tool_registry(
        role,
        workspace,
        bash_timeout_seconds=30,
        draft_store=PrDraftStore(workspace / "pr_draft.md"),
        scope_point=point,
        gate_enabled=gate_enabled,
    )
    return tuple(sorted(registry.names()))


# ── Fixture honesty ────────────────────────────────────────────────────────


def test_fixture_tasks_still_produce_the_estimates_these_tests_assume() -> None:
    """C0: pin the estimator verdicts the rest of this file depends on.

    root=estimate_scope class=C0 claim=CT8 oracle=OperatingPoint fields
    Without this, a change to the keyword table would silently turn every gate
    test below into a test of the ungated path — passing, and proving nothing.
    """
    repo_scale = estimate_scope(REPO_SCALE_TASK)
    assert repo_scale.recommended_mode == "workflow_linear"
    assert repo_scale.confidence >= GATE_MIN_CONFIDENCE

    simple = estimate_scope(SIMPLE_TASK)
    assert simple.recommended_mode == "chat_direct"

    medium = estimate_scope(MEDIUM_TASK)
    assert medium.confidence < GATE_MIN_CONFIDENCE


# ── CT9: the capability change (P30) ───────────────────────────────────────


def test_gate_withholds_every_declared_write_tool(tmp_path: Path) -> None:
    """C1 (P30): a confident workflow_linear chat task loses its write tools.

    root=_build_run_tool_registry class=C1 claim=CT9 matrix=M10 path=P30
    oracle=exact tool-name set
    producer-kill-check=remove the _apply_escalation_gate call in
      _build_run_tool_registry -> the withheld tools reappear and this fails
    """
    names = _build(tmp_path)
    assert set(names).isdisjoint(WITHHELD_WRITE_TOOLS), (
        f"gate fired but write tools survived: {sorted(set(names) & WITHHELD_WRITE_TOOLS)}"
    )


def test_gate_preserves_every_non_write_tool(tmp_path: Path) -> None:
    """C1 (P30): the gate removes the write tools and nothing else.

    root=_build_run_tool_registry class=C1 claim=CT9 path=P30
    oracle=set difference between ungated and gated corpora
    A gate that quietly dropped read or search tools would look identical to a
    working gate in the test above, and would leave the model unable to gather
    the evidence it needs to decide whether to escalate.
    """
    ungated = set(_build(tmp_path, task=SIMPLE_TASK))
    gated = set(_build(tmp_path))
    assert ungated - gated == WITHHELD_WRITE_TOOLS & ungated
    assert not gated - ungated


def test_escalation_path_survives_the_gate(tmp_path: Path) -> None:
    """C1 (P30): ``invoke_workflow`` is never withheld.

    root=_build_run_tool_registry class=C1 claim=CT9 path=P30
    oracle=tool-name membership
    producer-kill-check=add "invoke_workflow" to WITHHELD_WRITE_TOOLS -> fails
    This is the load-bearing one. A gate that removed the escalation tool would
    strand the run with no write tools AND no way to hand off — strictly worse
    than not gating at all.
    """
    assert "invoke_workflow" not in WITHHELD_WRITE_TOOLS


def test_gate_warns_naming_the_disable_key(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """C1 (P30): gating emits one operator WARNING naming the config key.

    root=_build_run_tool_registry class=C1 claim=CT9 path=P30 oracle=log record
    producer-kill-check=delete the logger.warning in _apply_escalation_gate
    A capability that silently disappears is indistinguishable from a bug. The
    operator must be able to tell those apart, and to find the off switch,
    from the log alone.
    """
    with caplog.at_level(logging.WARNING, logger="fa.cli"):
        _build(tmp_path)
    gate_records = [r for r in caplog.records if "escalation gate" in r.getMessage()]
    assert len(gate_records) == 1, f"expected exactly one gate warning, got {len(gate_records)}"
    message = gate_records[0].getMessage()
    assert "chat_escalation_gate" in message
    assert "invoke_workflow" in message


# ── Fail-open paths (P31-P34, M11-M12) ─────────────────────────────────────


def test_simple_task_keeps_write_tools(tmp_path: Path) -> None:
    """C1 (P32): a chat_direct estimate is never gated.

    root=_build_run_tool_registry class=C1 claim=CT8 path=P32
    oracle=exact tool-name set
    Zero over-scopes were measured, so the "don't interfere" half of the
    requirement is proven by this staying green, not by new machinery.
    """
    names = _build(tmp_path, task=SIMPLE_TASK)
    assert WITHHELD_WRITE_TOOLS <= set(names)


def test_medium_confidence_task_keeps_write_tools(tmp_path: Path) -> None:
    """C1 (P31): below GATE_MIN_CONFIDENCE the estimator is not binding.

    root=_build_run_tool_registry class=C1 claim=CT8 path=P31
    oracle=exact tool-name set
    producer-kill-check=set GATE_MIN_CONFIDENCE = 0.0 -> this fails
    The 0.6 bucket measured 3/5 correct. Gating it would withhold write tools
    from a task that needs them two times in five.
    """
    names = _build(tmp_path, task=MEDIUM_TASK)
    assert WITHHELD_WRITE_TOOLS <= set(names)


def test_operator_toggle_disables_the_gate(tmp_path: Path) -> None:
    """C1 (P33, M11): ``chat_escalation_gate: false`` wins over the estimator.

    root=_build_run_tool_registry class=C1 claim=CT8 matrix=M11 path=P33
    oracle=exact tool-name set
    producer-kill-check=ignore gate_enabled in should_withhold_write_tools
    """
    names = _build(tmp_path, gate_enabled=False)
    assert WITHHELD_WRITE_TOOLS <= set(names)


@pytest.mark.parametrize("role", ["coder", "planner", "eval", "unknown-role"])
def test_non_chat_roles_are_never_gated(tmp_path: Path, role: str) -> None:
    """C0p (P34): only the chat role is ever gated.

    root=should_withhold_write_tools class=C0p claim=CT8 path=P34
    oracle=predicate return value
    producer-kill-check=drop the role guard -> fails
    Gating a workflow stage role would break the escalation target itself.
    """
    point = OperatingPoint(
        difficulty=3,
        scope="repo",
        risk="high",
        confidence=0.8,
        recommended_mode="workflow_linear",
    )
    assert should_withhold_write_tools(point, role=role, gate_enabled=True) is False


def test_missing_estimate_fails_open(tmp_path: Path) -> None:
    """C1 (P31, M12): no estimate means no gate.

    root=_build_run_tool_registry class=C1 claim=CT8 matrix=M12 path=P31
    oracle=exact tool-name set
    An empty task makes estimate_scope raise, which _resolve_scope_point turns
    into None. Fail-open is deliberate: a gate that misfires costs a capability
    the operator expected; failing open costs nothing beyond today's behaviour.
    """
    names = _build(tmp_path, task="")
    assert WITHHELD_WRITE_TOOLS <= set(names)


# ── C0p: the predicate's own boundaries ────────────────────────────────────


@pytest.mark.parametrize(
    ("mode", "confidence", "expected"),
    [
        ("workflow_linear", 0.8, True),
        ("workflow_linear", 0.6, False),
        ("workflow_linear", 0.3, False),
        ("chat_planned", 0.8, False),
        ("chat_direct", 0.8, False),
    ],
)
def test_gate_predicate_matrix(mode: str, confidence: float, expected: bool) -> None:
    """C0p: the full (mode x confidence) decision surface.

    root=should_withhold_write_tools class=C0p claim=CT8 oracle=return value
    producer-kill-check=change either condition in the predicate -> a row fails
    """
    point = OperatingPoint(
        difficulty=3,
        scope="repo",
        risk="high",
        confidence=confidence,
        recommended_mode=mode,  # type: ignore[arg-type]  # exercising the surface
    )
    assert should_withhold_write_tools(point, role="chat", gate_enabled=True) is expected


def test_withheld_set_is_pinned_to_its_exact_members() -> None:
    """C0: the withheld tool names, asserted as literals.

    root=fa.inner_loop.routing class=C0 claim=CT9 oracle=exact set
    producer-kill-check=add or remove a member of WITHHELD_WRITE_TOOLS

    Mutation M7 (dropping ``fs_edit_file`` from the set) survived the whole
    suite, because every other assertion in this file is written in terms of
    WITHHELD_WRITE_TOOLS and therefore shrinks with it. This literal is the
    anchor that makes the set's contents a reviewed decision.

    ``fs_spawn_subagent`` belongs here because a subagent inherits a
    write-capable corpus — withholding the direct write tools while leaving a
    way to spawn a writer would be a gate in name only.
    """
    assert WITHHELD_WRITE_TOOLS == {"fs_write_file", "fs_edit_file", "fs_spawn_subagent"}


def test_gated_corpus_has_the_exact_expected_membership(tmp_path: Path) -> None:
    """C1: the gated chat corpus, named tool by tool.

    root=_build_run_tool_registry class=C1 claim=CT9 oracle=exact tool-name set
    producer-kill-check=change which tools the gate withholds

    Complements the set-algebra assertions above with a concrete expectation,
    so a change to either the gate OR the underlying chat profile has to be
    acknowledged here rather than absorbed silently.
    """
    gated = set(_build(tmp_path))
    ungated = set(_build(tmp_path, task=SIMPLE_TASK))

    assert "fs_write_file" not in gated
    assert "fs_edit_file" not in gated
    assert "fs_spawn_subagent" not in gated
    assert "fs_read_file" in gated
    assert "fs_run_bash" in gated
    assert len(gated) == len(ungated) - 3


def test_gate_threshold_is_pinned_to_its_measured_value() -> None:
    """C0: the calibrated confidence threshold, asserted as a literal.

    root=fa.inner_loop.routing class=C0 claim=CT8 oracle=exact float
    producer-kill-check=change GATE_MIN_CONFIDENCE -> this fails

    The other tests derive from the constant, so they follow it wherever it
    goes. 0.8 is the estimator's top bucket and the only one that measured
    100% (4/4). Moving it down to 0.6 would bind a bucket measured 3/5 — this
    test makes that a reviewed decision rather than a one-character edit.
    """
    assert GATE_MIN_CONFIDENCE == 0.8


def test_cmd_run_passes_the_live_role_to_the_gate() -> None:
    """C2: ``_cmd_run`` forwards the REAL role, not a hardcoded "chat".

    root=fa.cli source class=C2 claim=CT8 oracle=AST of the call site
    producer-kill-check=hardcode role="chat" at the _apply_escalation_gate call

    Mutation M8 replaced the forwarded ``role`` with the literal ``"chat"`` and
    survived every behavioural test, because they all build a chat registry
    directly and never exercise _cmd_run's argument plumbing. A wrong role here
    would gate coder and eval runs — the exact roles the gate must never touch.
    """
    import ast
    import inspect

    import fa.cli as cli_module

    source = inspect.getsource(cli_module)
    tree = ast.parse(source)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_apply_escalation_gate"
    ]
    assert calls, "no _apply_escalation_gate call site found in fa.cli"
    for call in calls:
        role_kwargs = [kw for kw in call.keywords if kw.arg == "role"]
        assert role_kwargs, "the gate must be called with an explicit role="
        value = role_kwargs[0].value
        assert isinstance(value, ast.Name), (
            "role must be forwarded as a variable; a string literal would gate "
            "the wrong roles and no behavioural test would notice"
        )


def test_cmd_run_derives_scope_mode_from_the_live_estimate() -> None:
    """C2: ``scope_mode`` is derived from scope_point, not hardcoded.

    root=fa.cli source class=C2 claim=CT10 oracle=AST of the keyword value
    producer-kill-check=replace the expression with a constant

    Mutation M9 pinned ``scope_mode="chat_direct"`` and survived, which would
    arm the tripwire on every run including correctly-scoped workflow ones.
    """
    import ast
    import inspect

    import fa.cli as cli_module

    tree = ast.parse(inspect.getsource(cli_module))
    found = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg == "scope_mode":
                found = True
                assert not isinstance(kw.value, ast.Constant), (
                    "scope_mode must be derived from the run's own estimate; a "
                    "constant arms the tripwire on runs that were scoped correctly"
                )
    assert found, "no scope_mode= keyword found at any call site in fa.cli"


def test_gate_is_idempotent_when_it_does_not_fire(tmp_path: Path) -> None:
    """C0: the ungated path returns the SAME registry object.

    root=_apply_escalation_gate class=C0 claim=CT9 oracle=object identity
    Identity, not equality: it proves the ungated path is byte-for-byte the
    pre-S7 behaviour rather than a rebuilt lookalike that might have dropped a
    compiled validator on the way through.
    """
    from fa.inner_loop.tools import build_chat_registry

    registry = build_chat_registry(tmp_path, bash_timeout_seconds=30)
    result = _apply_escalation_gate(registry, role="chat", scope_point=None, gate_enabled=True)
    assert result is registry


def test_gated_registry_keeps_working_validators(tmp_path: Path) -> None:
    """C1: tools that survive the gate are still dispatchable.

    root=_build_run_tool_registry class=C1 claim=CT9 oracle=validate() result
    The gate rebuilds the registry, and ToolRegistry keeps a parallel map of
    compiled jsonschema validators. Re-registering restores them; reaching into
    ``_tools`` directly would not, and nothing else in this file would notice.
    """
    from fa.inner_loop.registry import ToolCall

    point = _resolve_scope_point("chat", REPO_SCALE_TASK)
    registry = _build_run_tool_registry(
        "chat",
        tmp_path,
        bash_timeout_seconds=30,
        draft_store=PrDraftStore(tmp_path / "pr_draft.md"),
        scope_point=point,
        gate_enabled=True,
    )
    # S12.7 (CT7) probe update: fs_read_file no longer schema-REQUIRES "path"
    # (path XOR artifact_id is enforced at handler level), so {} is now
    # schema-valid. The validator-presence probe uses a type-invalid payload
    # instead — same oracle (schema rejection), independent of the XOR move.
    bad_call = ToolCall(name="fs_read_file", params={"path": 123}, call_id="")
    rejected = registry.validate(bad_call)
    assert rejected is not None, "a surviving tool lost its schema validator"
    assert rejected.error is not None
