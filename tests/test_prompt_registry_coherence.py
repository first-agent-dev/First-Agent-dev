"""A role's system prompt and its registered tool set must agree (D9/D10).

**Why this module exists.** Nothing tied the tool set a role prompt *describes*
to the tool set the registry actually *builds*. The two drifted, and the drift
was live on main:

- ``CHAT_SYSTEM_PROMPT`` stated "You do NOT have ``fs_write_file``,
  ``fs_edit_file``, or ``fs_spawn_subagent`` ... Do not attempt to write files"
  while the chat profile registered all three (they were granted by the D1/D3/D8
  fix in ``a638253``, which updated the profile but not the prose).
- It advertised ``invoke_workflow``, which is not registered on this branch.
- It never mentioned ``fs_exploration_metrics``, which is registered.

Both directions matter, for different reasons. A tool named in the prompt but
absent from the registry invites the model to emit a call that cannot be
dispatched — the orphaned-reference failure Manus describes, where the model
hallucinates a call and the harness returns a schema violation. A tool present
but declared *unavailable* is worse than silence: it is an explicit instruction
not to use a capability the operator deliberately granted, so the role
underperforms its own configuration.

**Design.** The oracle is the live registry (``build_registry_for_role``), not a
hand-maintained list — a hardcoded expected set would be one more thing to drift.
Tool mentions are parsed from the prompt's own structured sections, so the test
tracks the document the model actually reads.

Test class: **C1** — real prompt constant against the real registry builder.

**Kill-checks:**
- re-add a "Tools you do NOT have" section naming a registered tool →
  ``test_chat_prompt_does_not_deny_a_registered_tool`` fails;
- name a tool in the prompt that no builder produces →
  ``test_chat_prompt_only_advertises_registered_tools`` fails.
"""

from __future__ import annotations

import re
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from fa.inner_loop.profiles import PROFILES_RAW, build_registry_for_role
from fa.inner_loop.prompt import CHAT_SYSTEM_PROMPT
from fa.inner_loop.registry import ToolResult, ToolSpec

# ── Known-pending exemptions ────────────────────────────────────────────────
#
# EMPTY, and that is the point. ``invoke_workflow`` was the sole entry while its
# builder was unwritten; S4b registered it, so the exemption is retired and the
# coherence assertion below is now live enforcement for every tool the prompt
# names. Re-adding an entry here is a deliberate, reviewable act.
_PENDING_REGISTRATION: frozenset[str] = frozenset()


def _chat_tools() -> set[str]:
    """The tool set the chat role ACTUALLY receives in production.

    Q15=A — standardise on the live corpus. There are THREE composition layers,
    and each earlier one is a strict subset of the next:

    1. ``build_registry_for_role("chat", ...)`` — the profile (9 tools);
    2. ``build_chat_registry`` — adds ``fs_chronicle_search`` and ``fs_usage``
       via ``_register_extra_tools`` (11);
    3. ``cli._build_run_tool_registry`` — adds ``pr_prepare`` and, for chat,
       ``invoke_workflow`` (13).

    Only layer 3 is what a live ``fa run --role chat`` ships, so only layer 3
    can answer "does the prompt describe the tools the model actually has".
    Asserting against layer 1 or 2 would let the prompt name a tool added by a
    later layer -- or, as S4b showed, let a CLI-seam-registered tool sit
    permanently exempted while being fully live.
    """
    from tests._chat_registry_fixture import build_live_chat_registry

    workspace = Path(tempfile.mkdtemp())
    return {spec.name for spec in build_live_chat_registry(workspace).specs()}


def _chat_profile_tools() -> set[str]:
    """Only the profile layer — used where the profile itself is the subject."""
    workspace = Path(tempfile.mkdtemp())
    return set(build_registry_for_role("chat", workspace).names())


def _mentioned_tools(prompt: str) -> set[str]:
    """Every backticked identifier in the prompt that looks like a tool name.

    Matches the ``fs_*``/``pr_*`` namespaces plus the explicit control-flow
    tools, rather than all backticked text, so that prose like `AGENTS.md` or
    `regex` is not mistaken for a tool.
    """
    candidates = set(re.findall(r"`([a-z][a-z0-9_]*)`", prompt))
    return {name for name in candidates if name.startswith(("fs_", "pr_")) or name in {"invoke_workflow"}}


def test_chat_prompt_only_advertises_registered_tools() -> None:
    """C1 (kill-check) — no orphaned tool reference in the chat prompt.

    A tool the prompt names but the registry lacks produces an undispatchable
    call. ``_PENDING_REGISTRATION`` carries the sanctioned exceptions.
    """
    mentioned = _mentioned_tools(CHAT_SYSTEM_PROMPT)
    orphaned = mentioned - _chat_tools() - _PENDING_REGISTRATION
    assert not orphaned, (
        f"chat prompt names tools that are not registered: {sorted(orphaned)}. "
        "Either register them or stop advertising them."
    )


def test_chat_prompt_does_not_deny_a_registered_tool() -> None:
    """C1 (kill-check) — the prompt must not forbid a granted capability.

    The exact regression that shipped: the profile granted write tools while
    the prompt kept a "Tools you do NOT have" section listing them, so the
    chat role was instructed away from its own configuration.
    """
    registered = _chat_tools()
    denial_headings = [
        "## Tools you do NOT have",
        "## Tools you don't have",
        "## Unavailable tools",
    ]
    for heading in denial_headings:
        if heading not in CHAT_SYSTEM_PROMPT:
            continue
        start = CHAT_SYSTEM_PROMPT.index(heading)
        rest = CHAT_SYSTEM_PROMPT[start + len(heading) :]
        end = rest.index("\n## ") if "\n## " in rest else len(rest)
        denied = _mentioned_tools(rest[:end])
        contradiction = denied & registered
        assert not contradiction, (
            f"section {heading!r} denies tools that ARE registered for chat: {sorted(contradiction)}"
        )


def test_pending_tools_are_still_actually_missing() -> None:
    """C1 — the exemption self-retires.

    Fails as soon as a pending tool becomes registered, forcing
    ``_PENDING_REGISTRATION`` to be emptied instead of quietly masking a tool
    that no longer needs the exemption.
    """
    registered = _chat_tools()
    no_longer_pending = _PENDING_REGISTRATION & registered
    assert not no_longer_pending, (
        f"{sorted(no_longer_pending)} is now registered — remove it from "
        "_PENDING_REGISTRATION in this file so the coherence test enforces it."
    )


def test_write_tools_are_registered_for_chat() -> None:
    """C1 — pins the Q1 decision the prompt rewrite depends on.

    Chat writes are unrestricted by design (the deterministic scope estimator
    routes heavy work to the workflow, so small edits anywhere are intended).
    If this ever regresses, the rewritten prompt would start lying in the
    other direction.
    """
    registered = _chat_tools()
    for tool in ("fs_write_file", "fs_edit_file"):
        assert tool in registered, f"{tool} missing from the chat profile"


@pytest.mark.parametrize("role", sorted(PROFILES_RAW))
def test_every_registered_tool_has_a_portable_wire_name(role: str) -> None:
    """C1 (CT1) — no role can ship a provider-rejectable tool name.

    Parametrised over ``PROFILES_RAW`` itself rather than a written-out list,
    so a newly added role is covered without touching this test. Note the
    profile roles are ``implementer``/``verifier``, not the CLI's
    ``coder``/``eval``.
    """
    from fa.inner_loop.tool_names import is_valid_wire_name

    workspace = Path(tempfile.mkdtemp())
    offenders = [n for n in build_registry_for_role(role, workspace).names() if not is_valid_wire_name(n)]
    assert not offenders, f"role {role} registers non-portable names: {offenders}"


def test_pending_tools_are_declared_in_the_canonical_ledger() -> None:
    """C1 — a pending tool must still be a canonical name.

    ``TOOL_NAMES`` is the single source of truth for wire names. A tool the
    chat prompt actively instructs the model to call has to be in it even
    before its builder exists, otherwise the ledger disagrees with the
    contract the model is being handed.

    Added after mutation testing: deleting ``"invoke_workflow"`` from
    ``TOOL_NAMES`` survived the D9/D10 suite, because every other test
    reasons about tools that are *built* and this one is not yet.
    """
    from fa.inner_loop.tool_names import TOOL_NAMES

    missing = _PENDING_REGISTRATION - set(TOOL_NAMES)
    assert not missing, f"pending tools absent from the canonical TOOL_NAMES ledger: {sorted(missing)}"


def test_prompt_mentioned_tools_are_all_canonical() -> None:
    """C1 — every tool the chat prompt names is a canonical wire name.

    Catches a typo'd or invented tool reference in the prompt even when the
    tool happens to be pending rather than registered.
    """
    from fa.inner_loop.tool_names import TOOL_NAMES

    unknown = _mentioned_tools(CHAT_SYSTEM_PROMPT) - set(TOOL_NAMES)
    assert not unknown, f"chat prompt names tools absent from TOOL_NAMES: {sorted(unknown)}"


# ── D12: the fail-closed guard must survive the fallback wrappers ────────────


def _noop_handler(_params: Mapping[str, object]) -> ToolResult:
    """A correctly-typed handler; these fixtures never invoke it."""
    return ToolResult(summary="")


def _rogue_builders(monkeypatch: pytest.MonkeyPatch, bad_name: str, *, poison: str = "fs_read_file") -> None:
    """Make the builder table produce one non-portable tool name.

    ``poison`` names the builder key to corrupt; it must be a tool the role
    under test actually requests, otherwise the guard is never reached (the
    ``verifier`` profile, for example, requests only ``fs_run_bash``).
    """
    from fa.inner_loop import profiles as profiles_mod

    real = profiles_mod._build_tool_builders

    def rogue(workspace_root: Path, *, bash_timeout: int = 30) -> dict[str, Callable[[], ToolSpec]]:
        builders = dict(real(workspace_root, bash_timeout=bash_timeout))

        def _rogue_spec() -> ToolSpec:
            return ToolSpec(
                name=bad_name,
                description="d",
                input_schema={"type": "object"},
                permission="read",
                handler=_noop_handler,
            )

        builders[poison] = _rogue_spec
        return builders

    monkeypatch.setattr(profiles_mod, "_build_tool_builders", rogue)


@pytest.mark.parametrize(
    ("builder_name", "poison"),
    [
        ("build_chat_registry", "fs_read_file"),
        ("build_baseline_registry", "fs_read_file"),
        ("build_planner_registry", "fs_read_file"),
        ("build_eval_registry", "fs_run_bash"),
    ],
)
def test_wire_name_error_is_not_swallowed_by_the_fallback(
    builder_name: str, poison: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1 (kill-check, D12) — the guard must reach the real entry points.

    ``build_registry_for_role`` raises ``ToolWireNameError``, but every public
    wrapper in ``tools/__init__.py`` wraps it in ``except Exception`` and
    degrades to a reduced fallback registry, re-raising only
    ``ToolSchemaPortabilityError``. That swallowed the new guard: measured,
    ``build_chat_registry`` returned a 6-tool fallback instead of raising —
    dropping ``fs_write_file`` and ``fs_edit_file``, the very tools the D9
    prompt tells the chat role it has.

    A wire-name failure is a correctness failure like a non-portable schema,
    not an optional-builder availability failure, so it must propagate.
    """
    from fa.inner_loop import tools as tools_mod
    from fa.inner_loop.registry import ToolWireNameError

    # Asserted, not skipped: all four builders are unconditional module-level
    # functions. A skip here would silently retire the regression the moment a
    # builder was renamed — exactly when the guard needs re-checking.
    build = getattr(tools_mod, builder_name, None)
    assert build is not None, f"{builder_name} is no longer exported from fa.inner_loop.tools"

    _rogue_builders(monkeypatch, "fs.bad_name", poison=poison)
    with pytest.raises(ToolWireNameError) as excinfo:
        build(Path(tempfile.mkdtemp()))
    assert excinfo.value.tool_name == "fs.bad_name"


def test_fallback_still_degrades_for_ordinary_builder_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C1 (converse guard) — D12 must not turn every failure into a crash.

    The fallback exists for a genuinely broken/missing optional builder. That
    behaviour has to survive, otherwise the fix trades a silent degradation for
    an unnecessary hard failure.
    """
    from fa.inner_loop import profiles as profiles_mod
    from fa.inner_loop.tools import build_chat_registry

    real = profiles_mod._build_tool_builders

    def exploding(workspace_root: Path, *, bash_timeout: int = 30) -> dict[str, Callable[[], ToolSpec]]:
        builders = dict(real(workspace_root, bash_timeout=bash_timeout))

        def boom() -> ToolSpec:
            raise RuntimeError("optional builder unavailable")

        builders["fs_reach"] = boom
        return builders

    monkeypatch.setattr(profiles_mod, "_build_tool_builders", exploding)
    registry = build_chat_registry(Path(tempfile.mkdtemp()))
    assert "fs_read_file" in registry.names(), "fallback/degradation path must still work"


# ── The prompt asserts runtime facts; those facts must stay true ─────────────


def test_prompt_concurrency_claim_matches_the_scheduler() -> None:
    """C1 — "up to five at a time" is a load-bearing number, not prose.

    The D9 prompt tells the model to batch independent read-only calls and
    names the concurrency limit. If ``_MAX_TOOL_WORKERS`` changes, the prompt
    starts lying and the model's batching strategy is mistuned.
    """
    from fa.inner_loop.loop import _MAX_TOOL_WORKERS

    assert _MAX_TOOL_WORKERS == 5, f"prompt says 'up to five at a time' but _MAX_TOOL_WORKERS is {_MAX_TOOL_WORKERS}"
    assert "five at a time" in CHAT_SYSTEM_PROMPT


def test_prompt_batching_claims_match_classify_batches() -> None:
    """C1 — the batching advice the prompt gives is what the scheduler does.

    Pins the three concrete claims: independent reads batch, a search batches
    with a non-colliding read, and writes/bash serialise regardless.
    """
    from fa.inner_loop.loop import classify_batches
    from fa.inner_loop.registry import ToolCall
    from fa.inner_loop.tools import build_chat_registry

    registry = build_chat_registry(Path(tempfile.mkdtemp()))

    def group(calls: list[ToolCall]) -> list[list[str]]:
        return [[c.name for c in batch] for batch in classify_batches(calls, registry)]

    reads = [ToolCall(name="fs_read_file", params={"path": f"{x}.py"}, call_id=x) for x in "abc"]
    assert group(reads) == [["fs_read_file"] * 3], "independent reads must batch"

    mixed = [
        ToolCall(name="fs_search", params={"query": "x"}, call_id="s"),
        ToolCall(name="fs_read_file", params={"path": "a.py"}, call_id="r"),
    ]
    assert len(group(mixed)) == 1, "a search and a non-colliding read must batch"

    with_bash = [
        ToolCall(name="fs_read_file", params={"path": "a.py"}, call_id="r"),
        ToolCall(name="fs_run_bash", params={"command": "ls"}, call_id="b"),
    ]
    assert len(group(with_bash)) == 2, "fs_run_bash must not share a batch"

    with_write = [
        ToolCall(name="fs_read_file", params={"path": "a.py"}, call_id="r"),
        ToolCall(name="fs_write_file", params={"path": "b.py", "content": "x"}, call_id="w"),
    ]
    assert len(group(with_write)) == 2, "writes must not share a batch"


def test_prompt_names_every_scope_estimator_mode() -> None:
    """C1 — the prompt must give the model an instruction for every mode.

    The estimator's ``recommended_mode`` is a closed ``Literal``. A mode added
    there without a corresponding branch here would be injected into the
    prompt as a verdict the model was never told how to act on.
    """
    import typing

    from fa.inner_loop import scope_estimator as scope_mod

    hints = typing.get_type_hints(scope_mod.OperatingPoint)
    modes = typing.get_args(hints["recommended_mode"])
    assert modes, "expected recommended_mode to be a Literal with members"
    missing = [m for m in modes if f"`{m}`" not in CHAT_SYSTEM_PROMPT]
    assert not missing, f"scope-estimator modes with no instruction in the chat prompt: {missing}"


def test_chat_prompt_is_static_and_cacheable() -> None:
    """C0p — the cacheable prefix carries nothing per-turn.

    A stray ``{}`` placeholder or interpolated timestamp here would break
    prefix caching for every chat request — the D7 failure mode, reintroduced
    one layer up.
    """
    stripped = CHAT_SYSTEM_PROMPT.replace("{{", "").replace("}}", "")
    assert "{" not in stripped and "}" not in stripped, "prompt contains a format placeholder"
    assert "Task Scope Estimate\nDifficulty:" not in CHAT_SYSTEM_PROMPT, (
        "a rendered scope estimate is baked into the static prompt"
    )


def test_wire_name_error_propagates_from_the_optional_tool_layer() -> None:
    """C1 (kill-check, D12 second layer) — mutant M2.1.

    ``_register_extra_tools`` adds tools (``fs_search``, ``fs_usage``,
    ``fs_chronicle_search``, ``fs_spawn_subagent``, ...) through
    ``_register_optional_tool``, which has its own degrade-on-``Exception``
    fallback. Poisoning a profile builder never reaches it, so reverting the
    fix *only there* survived the rest of this file's tests. A malformed wire
    name is just as unshippable whether the tool came from the profile or from
    the optional layer.
    """
    from fa.inner_loop.registry import ToolRegistry, ToolWireNameError
    from fa.inner_loop.tools import _register_optional_tool

    def rogue_builder() -> ToolSpec:
        return ToolSpec(
            name="fs.optional_tool",
            description="d",
            input_schema={"type": "object"},
            permission="read",
            handler=_noop_handler,
        )

    with pytest.raises(ToolWireNameError) as excinfo:
        _register_optional_tool(ToolRegistry(), "fs_optional_tool", rogue_builder)
    assert excinfo.value.tool_name == "fs.optional_tool"


def test_optional_tool_layer_still_degrades_on_ordinary_failures() -> None:
    """C1 (converse guard) — an unavailable optional builder must not crash."""
    from fa.inner_loop.registry import ToolRegistry
    from fa.inner_loop.tools import _register_optional_tool

    def boom() -> ToolSpec:
        raise RuntimeError("optional builder unavailable")

    registry = ToolRegistry()
    _register_optional_tool(registry, "fs_optional_tool", boom)
    assert "fs_optional_tool" not in registry.names()
