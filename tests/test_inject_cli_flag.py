"""PLAN S5a / Q8 — the ``--inject NAME=MODE`` CLI surface.

root=cli class=C1 claim=G1 path=T4g
oracle=parsed argparse Namespace + the modes _cmd_run would resolve from it.
producer-kill-check=deleting the run_parser/workflow_parser --inject argument
makes the registration tests fail; making _cmd_workflow ignore a malformed
value makes test_workflow_rejects_bad_inject fail.

C1, not C0: the claim is that an operator-typed shell argument survives
argparse and reaches the resolution the session will actually use. A C0 on
parse_inject_overrides alone would pass even if the flag were never registered
on a parser -- which is precisely the defect that makes a documented flag a lie.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from fa.cli import _resolved_injection_modes, build_parser
from fa.inner_loop.injections import (
    CODER_SLICE_CEREMONY,
    MODE_ENFORCE,
    MODE_OBSERVE,
    MODE_OFF,
)

NAME = CODER_SLICE_CEREMONY.name


# ── registration on both parsers ───────────────────────────────────────────


class TestFlagIsRegistered:
    def test_run_accepts_inject(self) -> None:
        args = build_parser().parse_args(["run", "--inject", f"{NAME}=enforce", "task"])
        assert args.inject == [f"{NAME}=enforce"]

    def test_workflow_accepts_inject(self) -> None:
        args = build_parser().parse_args(["workflow", "planner,coder", "task", "--inject", f"{NAME}=observe"])
        assert args.inject == [f"{NAME}=observe"]

    def test_flag_is_repeatable(self) -> None:
        """append action: the surface must scale to several injections."""
        args = build_parser().parse_args(["run", "--inject", f"{NAME}=off", "--inject", f"{NAME}=enforce", "task"])
        assert args.inject == [f"{NAME}=off", f"{NAME}=enforce"]

    def test_absent_flag_is_none(self) -> None:
        """The default must be falsy so `fa run` is unchanged."""
        assert build_parser().parse_args(["run", "task"]).inject is None

    def test_unknown_injection_is_not_rejected_by_argparse(self) -> None:
        """Validation belongs to parse_inject_overrides, which can name the
        valid choices; argparse would only say 'invalid value'."""
        args = build_parser().parse_args(["run", "--inject", "bogus=enforce", "task"])
        assert args.inject == ["bogus=enforce"]


# ── _cmd_run resolution seam ───────────────────────────────────────────────


class TestResolvedInjectionModes:
    def test_flag_reaches_resolution(self) -> None:
        """The end-to-end claim: a typed argument changes the resolved mode."""
        args = build_parser().parse_args(["run", "--inject", f"{NAME}=enforce", "task"])
        modes = _resolved_injection_modes(args, "coder")
        assert modes[NAME] == MODE_ENFORCE

    def test_no_flag_resolves_off(self) -> None:
        args = build_parser().parse_args(["run", "task"])
        assert _resolved_injection_modes(args, "coder")[NAME] == MODE_OFF

    def test_role_gate_applies_at_the_cli_seam(self) -> None:
        args = build_parser().parse_args(["run", "--inject", f"{NAME}=enforce", "task"])
        assert _resolved_injection_modes(args, "planner")[NAME] == MODE_OFF

    def test_controller_value_wins_untouched(self) -> None:
        """PRODUCER KILL-CHECK for the precomputed branch.

        The workflow controller resolves modes per stage; _cmd_run must not
        re-resolve and override them from its own (absent) --inject.
        """
        precomputed = {NAME: MODE_OBSERVE}
        args = argparse.Namespace(injection_modes=precomputed)
        assert _resolved_injection_modes(args, "coder") is precomputed

    def test_controller_value_wins_over_a_flag(self) -> None:
        args = build_parser().parse_args(["run", "--inject", f"{NAME}=enforce", "task"])
        args.injection_modes = {NAME: MODE_OFF}
        assert _resolved_injection_modes(args, "coder")[NAME] == MODE_OFF

    def test_malformed_flag_degrades_rather_than_raising(self) -> None:
        """By this point the session is being built, so aborting would be a
        crash mid-construction; _cmd_workflow rejects bad input up front where
        a clean non-zero exit is still possible."""
        args = build_parser().parse_args(["run", "--inject", "bogus=enforce", "task"])
        assert _resolved_injection_modes(args, "coder") == {}

    def test_namespace_without_the_attribute_is_safe(self) -> None:
        """A hand-built Namespace (tests, conformance harness) must not crash."""
        assert _resolved_injection_modes(argparse.Namespace(), "coder")[NAME] == MODE_OFF


# ── _cmd_workflow rejects bad input up front ───────────────────────────────


class TestWorkflowRejectsBadInject:
    @pytest.mark.parametrize("bad", ["bogus=enforce", f"{NAME}=loud", "noequals"], ids=["name", "mode", "shape"])
    def test_workflow_exits_2_on_bad_inject(self, bad: str, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
        """PRODUCER KILL-CHECK: a typo must not yield a run that LOOKS
        configured and silently is not."""
        from fa.cli import _cmd_workflow

        args = build_parser().parse_args(
            ["workflow", "planner,coder", "task", "--inject", bad, "--workspace", str(tmp_path)]
        )
        assert _cmd_workflow(args) == 2
        assert "inject" in capsys.readouterr().err.lower()
