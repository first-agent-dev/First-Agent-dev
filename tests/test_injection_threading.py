"""PLAN S5a — thread injection modes controller -> _cmd_run -> drive_session.

root=stage-plumbing class=C1 claim=G1 path=T4c,T4d
oracle=the exact value received at each hop, captured from a real call.
producer-kill-check=removing the "injection_modes" stage_kwargs key makes
test_stage_kwargs_carries_the_modes fail; dropping the drive_session ->
_drive_session_inner forward makes test_value_reaches_the_inner_loop fail.

C1, not C0: the claim is that a value SURVIVES three hops of real production
plumbing (WorkflowContext -> stage_kwargs -> argparse.Namespace -> _cmd_run ->
drive_session). A C0 on each hop in isolation would pass even if the hops were
not connected, which is precisely the defect this slice exists to prevent
(the L2 site at coder_loop.py:745 is unreachable for a workflow coder stage).

Q7: the workflow owns the switch (WorkflowContext.inject_overrides, empty by
default). Q8: modes are resolved ONCE per stage dispatch (--inject > config >
off), not per turn. These tests pin the transport and the default;
fa.inner_loop.injections owns mode semantics.
"""

from __future__ import annotations

import argparse
import inspect
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop import coder_loop
from fa.inner_loop.injections import (
    CODER_SLICE_CEREMONY,
    MODE_ENFORCE,
    MODE_OBSERVE,
    MODE_OFF,
    is_active,
    mode_for,
)
from fa.inner_loop.workflow_controller import WorkflowContext


class _StopProbeError(Exception):
    """Sentinel: abort drive_session once the inner call is observed."""


class _MinimalState:
    """Just enough SessionState for drive_session's preamble.

    drive_session raises ValueError when ``state.log`` is None (coder_loop.py
    :430) and registers the state in a contextvar, so the probe needs a real
    attribute rather than None.
    """

    log = object()
    transaction = None
    workspace_root = Path("/tmp")


# ── T4c — the modes mapping reaches the stage ──────────────────────────────


class TestControllerCarriesTheSignal:
    def test_context_defaults_to_no_overrides(self) -> None:
        """Every existing construction site omits this field."""
        ctx = _make_context(Path("/tmp"))
        assert ctx.inject_overrides == {}

    def test_default_context_resolves_to_observe(self, tmp_path: Path) -> None:
        """Default path: telemetry only, payload untouched."""
        seen = _capture_stage_args(tmp_path)
        assert mode_for(seen.injection_modes, CODER_SLICE_CEREMONY.name) == MODE_OBSERVE

    def test_stage_kwargs_carries_the_modes(self, tmp_path: Path) -> None:
        """PRODUCER KILL-CHECK for the stage_kwargs key."""
        seen = _capture_stage_args(tmp_path, inject_overrides={CODER_SLICE_CEREMONY.name: MODE_ENFORCE})
        assert seen.injection_modes is not None
        assert CODER_SLICE_CEREMONY.name in seen.injection_modes

    def test_override_reaches_the_stage(self, tmp_path: Path) -> None:
        """The whole point: --inject on the CLI changes what a stage sees."""
        seen = _capture_stage_args(tmp_path, inject_overrides={CODER_SLICE_CEREMONY.name: MODE_ENFORCE})
        assert mode_for(seen.injection_modes, CODER_SLICE_CEREMONY.name) == MODE_ENFORCE

    def test_stage_args_is_a_namespace_with_the_attribute(self, tmp_path: Path) -> None:
        """_cmd_run reads via getattr, so the attribute must actually exist."""
        seen = _capture_stage_args(tmp_path)
        assert isinstance(seen, argparse.Namespace)
        assert hasattr(seen, "injection_modes")

    def test_modes_are_resolved_strings(self, tmp_path: Path) -> None:
        """Q8: resolution is once-per-dispatch, so no callables cross the hop."""
        seen = _capture_stage_args(tmp_path, inject_overrides={CODER_SLICE_CEREMONY.name: MODE_ENFORCE})
        for value in seen.injection_modes.values():
            assert isinstance(value, str)

    def test_role_gating_survives_the_hop(self, tmp_path: Path) -> None:
        """PRODUCER KILL-CHECK: a coder-only injection stays off for planner,
        even when the operator passed --inject explicitly."""
        seen = _capture_stage_args(
            tmp_path,
            inject_overrides={CODER_SLICE_CEREMONY.name: MODE_ENFORCE},
            role="planner",
        )
        assert mode_for(seen.injection_modes, CODER_SLICE_CEREMONY.name) == MODE_OFF


# ── T4c — _cmd_run -> drive_session ────────────────────────────────────────


class TestCmdRunForwards:
    def test_drive_session_accepts_injection_modes(self) -> None:
        """PRODUCER KILL-CHECK: deleting the parameter makes this fail."""
        sig = inspect.signature(coder_loop.drive_session)
        assert "injection_modes" in sig.parameters
        assert sig.parameters["injection_modes"].default is None

    def test_inner_accepts_injection_modes(self) -> None:
        sig = inspect.signature(coder_loop._drive_session_inner)
        assert "injection_modes" in sig.parameters
        assert sig.parameters["injection_modes"].default is None

    def test_parameter_is_keyword_only(self) -> None:
        sig = inspect.signature(coder_loop.drive_session)
        assert sig.parameters["injection_modes"].kind is inspect.Parameter.KEYWORD_ONLY

    def test_cli_reads_the_attribute_with_a_none_default(self) -> None:
        """A bare `fa run` Namespace has no such attribute.

        argparse never defines it, so the getattr default is the only thing
        standing between the default invocation and an AttributeError.
        """
        source = (Path(coder_loop.__file__).parent.parent / "cli.py").read_text(encoding="utf-8")
        assert 'getattr(args, "injection_modes", None)' in source

    def test_value_reaches_the_inner_loop(self) -> None:
        """PRODUCER KILL-CHECK for the forwarding line.

        Signature tests alone cannot see a dropped forward: both functions
        would still DECLARE the parameter while the value silently reverted
        to the default in between.
        """
        sentinel = {CODER_SLICE_CEREMONY.name: MODE_ENFORCE}
        seen = _spy_on_inner(injection_modes=sentinel)
        assert seen.get("injection_modes") is sentinel

    def test_default_reaches_the_inner_loop_as_none(self) -> None:
        seen = _spy_on_inner()
        assert seen.get("injection_modes") is None


# ── T4d — scope_mode regression ────────────────────────────────────────────


class TestScopeModeUnchanged:
    """The plan forbids reusing or perturbing scope_mode (S5a step 3)."""

    def test_scope_mode_still_exists_and_defaults_empty(self) -> None:
        sig = inspect.signature(coder_loop.drive_session)
        assert sig.parameters["scope_mode"].default == ""

    def test_injection_modes_is_a_distinct_parameter(self) -> None:
        sig = inspect.signature(coder_loop.drive_session)
        assert sig.parameters["scope_mode"] is not sig.parameters["injection_modes"]

    def test_is_chat_role_predicate_not_widened(self) -> None:
        """S5a 'Do-not': _is_chat_role must still be chat-only.

        If a future edit widens this to include the ceremony, a workflow coder
        stage would start running chat scope machinery (observed_tiers,
        escalation events) as a side effect.
        """
        source = Path(coder_loop.__file__).read_text(encoding="utf-8")
        assert '_is_chat_role = role == "chat" and bool(scope_mode)' in source
        assert "_is_chat_role = role" in source
        # the ceremony must not appear in the predicate line itself
        line = next(ln for ln in source.splitlines() if ln.strip().startswith("_is_chat_role ="))
        assert "injection" not in line

    def test_stage_kwargs_has_no_scope_mode(self, tmp_path: Path) -> None:
        """Regression: the controller must not start setting scope_mode."""
        seen = _capture_stage_args(tmp_path)
        assert not hasattr(seen, "scope_mode") or getattr(seen, "scope_mode", "") == ""


# ── Inertness (Q7) ─────────────────────────────────────────────────────────


def test_default_run_leaves_the_payload_untouched(tmp_path: Path) -> None:
    """Absent an explicit --inject, no injection may ALTER the request.

    The default is `observe`, so this is no longer "every mode is off" -- the
    invariant that actually matters is that nothing reaches `enforce`.
    """
    seen = _capture_stage_args(tmp_path)
    assert not any(is_active(seen.injection_modes, n) for n in seen.injection_modes)


# ── helpers ────────────────────────────────────────────────────────────────


def _spy_on_inner(**kwargs: Any) -> dict[str, Any]:
    """Call drive_session with _drive_session_inner replaced by a spy."""
    seen: dict[str, Any] = {}

    def _spy(_task: str, **inner_kwargs: Any) -> Any:
        seen.update(inner_kwargs)
        raise _StopProbeError

    original = coder_loop._drive_session_inner
    coder_loop._drive_session_inner = _spy  # type: ignore[assignment]
    try:
        with pytest.raises(_StopProbeError):
            coder_loop.drive_session(
                "task",
                provider_chain=None,  # type: ignore[arg-type]
                registry=None,  # type: ignore[arg-type]
                hooks=None,  # type: ignore[arg-type]
                state=_MinimalState(),  # type: ignore[arg-type]
                **kwargs,
            )
    finally:
        coder_loop._drive_session_inner = original  # type: ignore[assignment]
    return seen


def _make_context(tmp_path: Path, **overrides: Any) -> WorkflowContext:
    from fa.inner_loop.workflow_controller import workflow_artifact_paths

    base: dict[str, Any] = {
        "run_id": "test-run",
        "base_task": "do the thing",
        "per_role_task": {},
        "artifact_paths": workflow_artifact_paths("test-run", base_dir=tmp_path / "artifacts"),
        "config": tmp_path / "models.yaml",
        "workspace": tmp_path / "ws",
        "max_turns": 3,
        "output_mode": "plain",
    }
    base.update(overrides)
    return WorkflowContext(**base)


def _capture_stage_args(tmp_path: Path, **overrides: Any) -> argparse.Namespace:
    """Run the controller's real _run_stage, capturing the stage Namespace.

    Uses the production dispatcher so the assertion is against the actual
    stage_kwargs literal, not a reimplementation of it.
    """
    from fa.inner_loop import workflow_controller as wc

    role = overrides.pop("role", "coder")
    ctx = overrides.pop("ctx", None) or _make_context(tmp_path, **overrides)
    ctx.artifact_paths.base_dir.mkdir(parents=True, exist_ok=True)
    captured: dict[str, argparse.Namespace] = {}

    def _fake_stage(stage_args: argparse.Namespace, **_kw: Any) -> int:
        captured["args"] = stage_args
        return 0

    wc._run_stage(
        ctx,
        role,
        fresh=True,
        progress=wc.WorkflowProgress(),
        transition_reason="test",
        run_stage_fn=_fake_stage,
    )
    assert "args" in captured, "controller never dispatched a stage"
    return captured["args"]
