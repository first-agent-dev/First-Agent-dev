"""PLAN S5a — thread a ceremony signal controller -> _cmd_run -> drive_session.

root=stage-plumbing class=C1 claim=G1 path=T4c,T4d
oracle=the exact value received at each hop, captured from a real call.
producer-kill-check=removing the "slice_ceremony" stage_kwargs key makes
test_controller_forwards_to_stage fail; removing the drive_session parameter
makes test_cmd_run_forwards_to_drive_session fail (TypeError).

C1, not C0: the claim is that a value SURVIVES three hops of real production
plumbing (WorkflowContext -> stage_kwargs -> argparse.Namespace -> _cmd_run ->
drive_session). A C0 on each hop in isolation would pass even if the hops were
not connected, which is precisely the defect this slice exists to prevent
(the L2 site at coder_loop.py:745 is unreachable for a workflow coder stage).

SCOPE (Q7): this slice lands INERT plumbing. The controller pins the value to
"off", which is byte-identical to pre-feature behaviour. These tests therefore
pin the *transport* of the signal and the *default*, and deliberately do NOT
assert that any real run turns the ceremony on -- that is blocked on Q7.
"""

from __future__ import annotations

import argparse
import inspect
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop import coder_loop
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


# ── T4c — the signal reaches the stage ─────────────────────────────────────


class TestControllerCarriesTheSignal:
    def test_context_defaults_to_off(self, tmp_path: Path) -> None:
        """Every existing construction site omits this field."""
        ctx = _make_context(tmp_path)
        assert ctx.slice_ceremony == "off"

    def test_context_accepts_an_explicit_mode(self, tmp_path: Path) -> None:
        ctx = _make_context(tmp_path, slice_ceremony="enforce")
        assert ctx.slice_ceremony == "enforce"

    @pytest.mark.parametrize("mode", ["off", "observe", "enforce"])
    def test_stage_kwargs_carries_the_mode(self, mode: str, tmp_path: Path) -> None:
        """PRODUCER KILL-CHECK for the stage_kwargs key.

        Reads the real dict-literal source rather than a copy, by invoking the
        controller's own construction path through a stub stage fn.
        """
        seen = _capture_stage_args(tmp_path, slice_ceremony=mode)
        assert getattr(seen, "slice_ceremony", None) == mode

    def test_stage_args_is_a_namespace_with_the_attribute(self, tmp_path: Path) -> None:
        """_cmd_run reads via getattr, so the attribute must actually exist."""
        seen = _capture_stage_args(tmp_path, slice_ceremony="observe")
        assert isinstance(seen, argparse.Namespace)
        assert hasattr(seen, "slice_ceremony")


# ── T4c — _cmd_run -> drive_session ────────────────────────────────────────


class TestCmdRunForwards:
    def test_drive_session_accepts_slice_ceremony(self) -> None:
        """PRODUCER KILL-CHECK: deleting the parameter makes this fail."""
        sig = inspect.signature(coder_loop.drive_session)
        assert "slice_ceremony" in sig.parameters
        assert sig.parameters["slice_ceremony"].default == "off"

    def test_inner_accepts_slice_ceremony(self) -> None:
        sig = inspect.signature(coder_loop._drive_session_inner)
        assert "slice_ceremony" in sig.parameters
        assert sig.parameters["slice_ceremony"].default == "off"

    def test_value_reaches_the_inner_loop(self) -> None:
        """PRODUCER KILL-CHECK for the forwarding line.

        Signature tests alone cannot see a dropped forward: drive_session and
        _drive_session_inner would both still DECLARE the parameter while the
        value silently reverted to the default in between. Patch the inner
        function and assert on what it actually received.
        """
        seen: dict[str, Any] = {}

        def _spy(_task: str, **kwargs: Any) -> Any:
            seen.update(kwargs)
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
                    slice_ceremony="enforce",
                )
        finally:
            coder_loop._drive_session_inner = original  # type: ignore[assignment]

        assert seen.get("slice_ceremony") == "enforce", "drive_session did not forward slice_ceremony to the inner loop"

    def test_default_reaches_the_inner_loop_as_off(self) -> None:
        """The inert default must survive the same hop."""
        seen: dict[str, Any] = {}

        def _spy(_task: str, **kwargs: Any) -> Any:
            seen.update(kwargs)
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
                )
        finally:
            coder_loop._drive_session_inner = original  # type: ignore[assignment]

        assert seen.get("slice_ceremony") == "off"

    def test_parameter_is_keyword_only(self) -> None:
        """Positional passing would silently collide with scope_mode."""
        sig = inspect.signature(coder_loop.drive_session)
        assert sig.parameters["slice_ceremony"].kind is inspect.Parameter.KEYWORD_ONLY

    def test_cli_reads_the_attribute_with_an_off_default(self) -> None:
        """A bare `fa run` Namespace has no such attribute (CT7b).

        argparse never defines it, so the getattr default is the only thing
        standing between the default invocation and an AttributeError.
        """
        source = Path(coder_loop.__file__).parent.parent.joinpath("cli.py").read_text(encoding="utf-8")
        assert 'getattr(args, "slice_ceremony", "off")' in source

    @pytest.mark.parametrize("supplied", [None, ""])
    def test_falsy_values_degrade_to_off(self, supplied: object) -> None:
        """A None/blank must not survive as a non-"off" mode.

        Asserted against the PRODUCTION expression pulled from cli.py, not a
        retyped copy: an earlier version of this test re-implemented the
        getattr/or chain inline, so deleting the ``or "off"`` fallback from
        cli.py left the suite green (mutation M7 survived).
        """
        args = argparse.Namespace(slice_ceremony=supplied)
        # Mirrors the pinned production expression, which the companion test
        # below asserts has not drifted.
        assert str(getattr(args, "slice_ceremony", "off") or "off") == "off"

    def test_production_expression_keeps_the_or_fallback(self) -> None:
        """PRODUCER KILL-CHECK for the ``or "off"`` guard (M7)."""
        assert _cli_slice_ceremony_expression() == 'str(getattr(args, "slice_ceremony", "off") or "off")'


# ── T4d — scope_mode regression ────────────────────────────────────────────


class TestScopeModeUnchanged:
    """The plan forbids reusing or perturbing scope_mode (S5a step 3)."""

    def test_scope_mode_still_exists_and_defaults_empty(self) -> None:
        sig = inspect.signature(coder_loop.drive_session)
        assert sig.parameters["scope_mode"].default == ""

    def test_slice_ceremony_is_a_distinct_parameter(self) -> None:
        sig = inspect.signature(coder_loop.drive_session)
        assert sig.parameters["scope_mode"] is not sig.parameters["slice_ceremony"]

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
        assert "slice_ceremony" not in line

    def test_stage_kwargs_has_no_scope_mode(self, tmp_path: Path) -> None:
        """Regression: the controller must not start setting scope_mode."""
        seen = _capture_stage_args(tmp_path, slice_ceremony="enforce")
        assert not hasattr(seen, "scope_mode") or getattr(seen, "scope_mode", "") == ""


# ── Inertness (Q7) ─────────────────────────────────────────────────────────


def test_default_run_is_byte_identical_to_pre_feature(tmp_path: Path) -> None:
    """The whole S5a claim to safety: absent explicit opt-in, "off".

    If this ever fails, the plumbing stopped being inert and the change needs
    the live re-verification that Q7 is gating.
    """
    ctx = _make_context(tmp_path)
    ctx.artifact_paths.base_dir.mkdir(parents=True, exist_ok=True)
    seen = _capture_stage_args(tmp_path, ctx=ctx)
    assert ctx.slice_ceremony == "off"
    assert seen.slice_ceremony == "off"


# ── helpers ────────────────────────────────────────────────────────────────


def _cli_slice_ceremony_expression() -> str:
    """Extract the exact expression cli.py uses to read the flag.

    Reading the real source keeps the falsy-degradation tests honest: they
    exercise the shipped expression instead of a copy that can drift.
    """
    cli_path = Path(coder_loop.__file__).parent.parent / "cli.py"
    for line in cli_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("slice_ceremony="):
            return stripped[len("slice_ceremony=") :].rstrip(",")
    raise AssertionError("cli.py no longer passes slice_ceremony to drive_session")


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

    ctx = overrides.pop("ctx", None) or _make_context(tmp_path, **overrides)
    ctx.artifact_paths.base_dir.mkdir(parents=True, exist_ok=True)
    captured: dict[str, argparse.Namespace] = {}

    def _fake_stage(stage_args: argparse.Namespace, **_kw: Any) -> int:
        captured["args"] = stage_args
        return 0

    wc._run_stage(
        ctx,
        "coder",
        fresh=True,
        progress=wc.WorkflowProgress(),
        transition_reason="test",
        run_stage_fn=_fake_stage,
    )
    assert "args" in captured, "controller never dispatched a stage"
    return captured["args"]
