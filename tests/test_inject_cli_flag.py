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

from fa.cli import _cmd_inject, _resolved_injection_modes, build_parser
from fa.inner_loop.injections import (
    CODER_SLICE_CEREMONY,
    INJECTION_SPECS,
    MODE_ENFORCE,
    MODE_OBSERVE,
    MODE_OFF,
    SOURCE_DEFAULT,
    SOURCE_FLAG,
    SOURCE_ROLE_GATED,
    explain_injection_modes,
    resolve_injection_modes,
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

    def test_no_flag_resolves_to_the_default(self) -> None:
        args = build_parser().parse_args(["run", "task"])
        assert _resolved_injection_modes(args, "coder")[NAME] == MODE_OBSERVE

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

    def test_malformed_flag_degrades_to_the_default(self) -> None:
        """By this point the session is being built, so aborting would be a
        crash mid-construction; _cmd_workflow rejects bad input up front where
        a clean non-zero exit is still possible.

        The degraded result is a full all-off mapping rather than an empty one:
        the shape a caller gets must not depend on whether the operator made a
        typo, or a consumer's `modes[name]` starts raising KeyError only on the
        error path.
        """
        args = build_parser().parse_args(["run", "--inject", "bogus=enforce", "task"])
        modes = _resolved_injection_modes(args, "coder")
        assert modes == {NAME: MODE_OBSERVE}

    def test_namespace_without_the_attribute_is_safe(self) -> None:
        """A hand-built Namespace (tests, conformance harness) must not crash."""
        assert _resolved_injection_modes(argparse.Namespace(), "coder")[NAME] == MODE_OBSERVE


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


# ── S5d / G9: `fa inject` introspection ─────────────────────────────────────


class TestExplainInjectionModes:
    """root=injections class=C0 claim=CT17/CT18 path=S5d

    oracle=the winning input for each (role, overrides, config) triple.
    producer-kill-check=hardcoding source to any single value fails the
    attribution tests; breaking the projection fails test_projection_matches.
    """

    def test_flag_source(self) -> None:
        st = explain_injection_modes("coder", overrides={NAME: MODE_ENFORCE})[NAME]
        assert (st.mode, st.source) == (MODE_ENFORCE, SOURCE_FLAG)

    def test_default_source(self, tmp_path: Path) -> None:
        st = explain_injection_modes("coder", config_path=tmp_path / "absent.yaml")[NAME]
        assert (st.mode, st.source) == (MODE_OBSERVE, SOURCE_DEFAULT)

    def test_config_off_is_attributed_to_config_not_default(self, tmp_path: Path) -> None:
        """Attribution must test DECLARATION, not value.

        Once the default became `observe`, inferring the source from "the mode
        differs from the fallback" would report an explicit `off` -- the one
        setting a cautious operator is most likely to write -- as `default`.
        """
        cfg = tmp_path / "config.yaml"
        cfg.write_text("feature_flags:\n  coder_slice_ceremony_mode: off\n", encoding="utf-8")
        st = explain_injection_modes("coder", config_path=cfg)[NAME]
        assert st.mode == MODE_OFF
        assert str(cfg) in st.source

    def test_absent_config_is_default_even_though_mode_is_the_fallback(self, tmp_path: Path) -> None:
        """PRODUCER KILL-CHECK for _config_declares.

        Pairs with the test above. `config: off` is attributed correctly by
        BOTH the declaration check and the old value-inference heuristic, so
        that case alone cannot detect a regression. This case separates them:
        with no config file the mode IS the fallback, and only a declaration
        check can still say `default`. Together the two pin the real rule.
        """
        st = explain_injection_modes("coder", config_path=tmp_path / "absent.yaml")[NAME]
        assert st.mode == MODE_OBSERVE
        assert st.source == SOURCE_DEFAULT

    def test_config_matching_the_default_value_is_not_claimed_as_config(self, tmp_path: Path) -> None:
        """Documented limitation, pinned so it stays deliberate.

        A config that writes exactly the default value is reported as
        `default`. The effective mode is identical either way, so no operator
        is misled about behaviour -- but if this ever needs to change, this
        test is the record that the current answer was chosen, not missed.
        """
        cfg = tmp_path / "config.yaml"
        cfg.write_text("feature_flags:\n  coder_slice_ceremony_mode: observe\n", encoding="utf-8")
        st = explain_injection_modes("coder", config_path=cfg)[NAME]
        assert st.mode == MODE_OBSERVE
        assert st.source == SOURCE_DEFAULT

    def test_role_gated_is_distinct_from_default(self, tmp_path: Path) -> None:
        """CT17: 'you disabled it' and 'it does not apply here' must not look
        identical -- that ambiguity is what made the Q9 bug invisible."""
        st = explain_injection_modes("planner", overrides={NAME: MODE_ENFORCE}, config_path=tmp_path / "absent.yaml")[
            NAME
        ]
        assert (st.mode, st.source) == (MODE_OFF, SOURCE_ROLE_GATED)
        assert st.source != SOURCE_DEFAULT

    def test_config_source_names_the_file(self, tmp_path: Path) -> None:
        cfg = tmp_path / "config.yaml"
        cfg.write_text("feature_flags:\n  coder_slice_ceremony_mode: enforce\n", encoding="utf-8")
        st = explain_injection_modes("coder", config_path=cfg)[NAME]
        assert st.mode == MODE_ENFORCE
        assert str(cfg) in st.source

    def test_every_injection_is_explained(self) -> None:
        assert set(explain_injection_modes("coder")) == set(INJECTION_SPECS)

    @pytest.mark.parametrize("role", ["coder", "planner", "eval", "chat"])
    @pytest.mark.parametrize("override", [None, MODE_OFF, MODE_OBSERVE, MODE_ENFORCE])
    def test_projection_matches_resolution(self, role: str, override: str | None) -> None:
        """CT18: the table can never disagree with what a real run does."""
        overrides = {} if override is None else {NAME: override}
        explained = explain_injection_modes(role, overrides=overrides)
        assert {k: v.mode for k, v in explained.items()} == resolve_injection_modes(role, overrides=overrides)


class TestInjectCommand:
    def test_prints_a_row_per_injection(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = build_parser().parse_args(["inject", "status", "--role", "coder"])
        assert _cmd_inject(args) == 0
        out = capsys.readouterr().out
        assert "INJECTION" in out and "SOURCE" in out
        for name in INJECTION_SPECS:
            assert name in out

    def test_subcommand_defaults_to_status(self) -> None:
        assert build_parser().parse_args(["inject"]).subcommand == "status"

    def test_list_and_status_are_both_accepted(self) -> None:
        for sub in ("list", "status"):
            assert build_parser().parse_args(["inject", sub]).subcommand == sub

    def test_flag_is_reflected_in_the_table(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = build_parser().parse_args(["inject", "--role", "coder", "--inject", f"{NAME}=enforce"])
        assert _cmd_inject(args) == 0
        out = capsys.readouterr().out
        assert MODE_ENFORCE in out and SOURCE_FLAG in out

    def test_bad_inject_exits_2(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = build_parser().parse_args(["inject", "--inject", "bogus=enforce"])
        assert _cmd_inject(args) == 2
        assert "inject" in capsys.readouterr().err.lower()

    def test_unreadable_config_does_not_raise(self, tmp_path: Path) -> None:
        """An introspection command must never traceback on bad config."""
        bad = tmp_path / "broken.yaml"
        bad.write_text("feature_flags: [unclosed\n", encoding="utf-8")
        args = build_parser().parse_args(["inject", "--config", str(bad)])
        assert _cmd_inject(args) == 0
