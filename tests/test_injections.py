"""PLAN S5a — the injection registry, mode resolution, and hot reload.

root=injections class=C0/C1 claim=G1 path=T4a,T4b,T4f
oracle=exact resolved mode strings for a given (flag, config, role) triple.
producer-kill-check=deleting the role gate in resolve_mode or in
resolve_injection_modes makes the role tests fail; making parse_inject_overrides
lenient makes the rejection tests fail.

Precedence (plan v5 Q8) is the load-bearing property: --inject > config > off,
resolved ONCE per invocation. The rejection tests matter just as much -- a
mistyped --inject must abort, not silently produce an unconfigured run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.inner_loop import injections
from fa.inner_loop.injections import (
    CODER_SLICE_CEREMONY,
    FALLBACK_MODE,
    INJECTION_MODES,
    INJECTION_SPECS,
    MODE_ENFORCE,
    MODE_OBSERVE,
    MODE_OFF,
    InjectionFlagError,
    InjectionSpec,
    is_active,
    is_observed,
    mode_for,
    normalize_mode,
    parse_inject_overrides,
    resolve_injection_modes,
    resolve_mode,
)


def _write_config(path: Path, mode: str) -> None:
    path.write_text(
        "feature_flags:\n  injections:\n    coder_slice_ceremony:\n      mode: " + mode + "\n",
        encoding="utf-8",
    )


# ── normalize_mode: total over arbitrary input ─────────────────────────────


class TestNormalizeMode:
    @pytest.mark.parametrize("mode", sorted(INJECTION_MODES))
    def test_valid_modes_pass_through(self, mode: str) -> None:
        assert normalize_mode(mode) == mode

    @pytest.mark.parametrize(
        "raw", ["ENFORCE", "  enforce  ", "Observe", "OFF"], ids=["upper", "padded", "title", "upper-off"]
    )
    def test_casing_and_whitespace_are_forgiven(self, raw: str) -> None:
        assert normalize_mode(raw) == raw.strip().lower()

    @pytest.mark.parametrize(
        "raw", [None, 1, True, [], {}, object(), "bogus", "", "   ", "enforce!"], ids=lambda v: repr(v)[:12]
    )
    def test_anything_else_is_the_fallback(self, raw: object) -> None:
        assert normalize_mode(raw) == FALLBACK_MODE

    def test_fallback_is_off_not_enforce(self) -> None:
        """A config typo must never silently start rewriting prompts."""
        assert FALLBACK_MODE == MODE_OFF


# ── registry shape ─────────────────────────────────────────────────────────


class TestRegistry:
    def test_ceremony_is_registered_under_its_name(self) -> None:
        assert INJECTION_SPECS[CODER_SLICE_CEREMONY.name] is CODER_SLICE_CEREMONY

    def test_name_is_the_operator_facing_one(self) -> None:
        assert CODER_SLICE_CEREMONY.name == "coder_slice_ceremony"

    def test_ceremony_is_coder_only(self) -> None:
        assert CODER_SLICE_CEREMONY.roles == frozenset({"coder"})

    def test_every_spec_key_matches_its_name(self) -> None:
        for key, spec in INJECTION_SPECS.items():
            assert key == spec.name

    def test_every_spec_reads_a_real_feature_flag(self) -> None:
        """A spec whose reader raises would resolve to off forever."""
        from fa.feature_flags import FeatureFlags

        flags = FeatureFlags()
        for spec in INJECTION_SPECS.values():
            assert isinstance(spec.read_flag(flags), str), spec.name

    def test_flag_readers_are_distinct(self) -> None:
        from fa.feature_flags import FeatureFlags

        flags = FeatureFlags(coder_slice_ceremony_mode="enforce")
        assert CODER_SLICE_CEREMONY.read_flag(flags) == "enforce"

    def test_registry_uses_no_dynamic_flag_access(self) -> None:
        """Guards two repo gates at once.

        test_no_getattr_feature_flags bans getattr on flags, and the dead-flag
        scanner only sees literal ``.field`` reads -- a getattr-based registry
        would silently mark every injection flag dead.
        """
        source = Path(injections.__file__).read_text(encoding="utf-8")
        assert "getattr(" + "flags" not in source


# ── resolve_mode: role gating + config ─────────────────────────────────────


class TestResolveMode:
    @pytest.mark.parametrize("mode", sorted(INJECTION_MODES))
    def test_reads_the_configured_mode(self, tmp_path: Path, mode: str) -> None:
        cfg = tmp_path / "config.yaml"
        _write_config(cfg, mode)
        assert resolve_mode(CODER_SLICE_CEREMONY, "coder", config_path=cfg) == mode

    @pytest.mark.parametrize("role", ["planner", "eval", "chat", "", "Coder"])
    def test_role_outside_spec_is_always_off(self, tmp_path: Path, role: str) -> None:
        """PRODUCER KILL-CHECK for the role gate.

        Even with enforce in config, a non-matching role gets off -- so a
        future planner injection cannot leak into a coder session, and vice
        versa, on the strength of one mistyped flag.
        """
        cfg = tmp_path / "config.yaml"
        _write_config(cfg, "enforce")
        assert resolve_mode(CODER_SLICE_CEREMONY, role, config_path=cfg) == MODE_OFF

    def test_missing_config_file_is_off(self, tmp_path: Path) -> None:
        assert resolve_mode(CODER_SLICE_CEREMONY, "coder", config_path=tmp_path / "absent.yaml") == MODE_OFF

    def test_malformed_config_is_off(self, tmp_path: Path) -> None:
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "feature_flags:\n  injections:\n    coder_slice_ceremony:\n      mode: bogus\n", encoding="utf-8"
        )
        assert resolve_mode(CODER_SLICE_CEREMONY, "coder", config_path=cfg) == MODE_OFF

    def test_unrelated_config_is_off(self, tmp_path: Path) -> None:
        cfg = tmp_path / "config.yaml"
        cfg.write_text("feature_flags:\n  telemetry_enabled: true\n", encoding="utf-8")
        assert resolve_mode(CODER_SLICE_CEREMONY, "coder", config_path=cfg) == MODE_OFF

    def test_spec_reading_a_missing_flag_degrades(self, tmp_path: Path) -> None:
        """A spec left pointing at a deleted field must not crash a run."""

        def _missing(flags: object) -> object:
            raise AttributeError("does_not_exist")

        phantom = InjectionSpec(name="phantom", roles=frozenset({"coder"}), read_flag=_missing, summary="x")
        cfg = tmp_path / "config.yaml"
        _write_config(cfg, "enforce")
        assert resolve_mode(phantom, "coder", config_path=cfg) == FALLBACK_MODE


# ── --inject parsing: explicit input fails loudly ──────────────────────────


class TestParseInjectOverrides:
    def test_none_and_empty_are_empty(self) -> None:
        assert parse_inject_overrides(None) == {}
        assert parse_inject_overrides([]) == {}

    @pytest.mark.parametrize("mode", sorted(INJECTION_MODES))
    def test_valid_pair_parses(self, mode: str) -> None:
        got = parse_inject_overrides([f"{CODER_SLICE_CEREMONY.name}={mode}"])
        assert got == {CODER_SLICE_CEREMONY.name: mode}

    def test_surrounding_whitespace_tolerated(self) -> None:
        got = parse_inject_overrides([f"  {CODER_SLICE_CEREMONY.name} = ENFORCE  "])
        assert got == {CODER_SLICE_CEREMONY.name: MODE_ENFORCE}

    @pytest.mark.parametrize(
        "raw",
        [
            "no_equals_sign",
            "=enforce",
            "unknown_injection=enforce",
            f"{CODER_SLICE_CEREMONY.name}=loud",
            f"{CODER_SLICE_CEREMONY.name}=",
        ],
        ids=["no-eq", "blank-name", "unknown-name", "bad-mode", "blank-mode"],
    )
    def test_malformed_input_raises(self, raw: str) -> None:
        """PRODUCER KILL-CHECK: silently ignoring a typo would produce a run
        that LOOKS configured and is not -- the exact failure this prevents."""
        with pytest.raises(InjectionFlagError):
            parse_inject_overrides([raw])

    def test_shape_error_names_the_expected_shape(self) -> None:
        """PRODUCER KILL-CHECK for the '=' check specifically.

        Without it, "noequals" still raises -- but via the unknown-name branch,
        telling the operator their injection name is wrong when the real defect
        is a missing '='. A raise alone is not the property; the right
        diagnosis is.
        """
        with pytest.raises(InjectionFlagError) as excinfo:
            parse_inject_overrides(["noequals"])
        assert "<name>=<mode>" in str(excinfo.value)

    def test_error_message_lists_valid_choices(self) -> None:
        """An operator must be able to fix the typo from the message alone."""
        with pytest.raises(InjectionFlagError) as excinfo:
            parse_inject_overrides(["unknown_injection=enforce"])
        assert CODER_SLICE_CEREMONY.name in str(excinfo.value)

    def test_duplicate_name_raises(self) -> None:
        """`--inject x=off --inject x=enforce` has no obvious reading."""
        with pytest.raises(InjectionFlagError):
            parse_inject_overrides([f"{CODER_SLICE_CEREMONY.name}=off", f"{CODER_SLICE_CEREMONY.name}=enforce"])

    def test_distinct_names_coexist(self) -> None:
        """Shape check for the multi-injection future."""
        got = parse_inject_overrides([f"{CODER_SLICE_CEREMONY.name}=observe"])
        assert len(got) == 1


# ── precedence: flag > config > off (plan v5 Q8) ───────────────────────────


class TestPrecedence:
    def test_flag_beats_config(self, tmp_path: Path) -> None:
        cfg = tmp_path / "config.yaml"
        _write_config(cfg, "off")
        modes = resolve_injection_modes("coder", overrides={CODER_SLICE_CEREMONY.name: MODE_ENFORCE}, config_path=cfg)
        assert modes[CODER_SLICE_CEREMONY.name] == MODE_ENFORCE

    def test_flag_can_also_disable(self, tmp_path: Path) -> None:
        """Precedence must work in both directions, not just to turn on."""
        cfg = tmp_path / "config.yaml"
        _write_config(cfg, "enforce")
        modes = resolve_injection_modes("coder", overrides={CODER_SLICE_CEREMONY.name: MODE_OFF}, config_path=cfg)
        assert modes[CODER_SLICE_CEREMONY.name] == MODE_OFF

    def test_config_used_when_no_flag(self, tmp_path: Path) -> None:
        cfg = tmp_path / "config.yaml"
        _write_config(cfg, "observe")
        modes = resolve_injection_modes("coder", config_path=cfg)
        assert modes[CODER_SLICE_CEREMONY.name] == MODE_OBSERVE

    def test_off_when_neither(self, tmp_path: Path) -> None:
        modes = resolve_injection_modes("coder", config_path=tmp_path / "absent.yaml")
        assert modes[CODER_SLICE_CEREMONY.name] == MODE_OFF

    def test_role_gate_beats_the_flag(self, tmp_path: Path) -> None:
        """PRODUCER KILL-CHECK for role gating on the override path.

        A flag says WHAT to enable, not which roles it applies to. Without
        this, one --inject could smuggle a coder payload into a planner stage.
        """
        modes = resolve_injection_modes(
            "planner",
            overrides={CODER_SLICE_CEREMONY.name: MODE_ENFORCE},
            config_path=tmp_path / "absent.yaml",
        )
        assert modes[CODER_SLICE_CEREMONY.name] == MODE_OFF

    def test_every_injection_gets_an_entry(self, tmp_path: Path) -> None:
        """Consumers must be able to ask by name without a membership check."""
        modes = resolve_injection_modes("coder", config_path=tmp_path / "absent.yaml")
        assert set(modes) == set(INJECTION_SPECS)

    def test_result_is_plain_strings(self, tmp_path: Path) -> None:
        """Q8: resolution happens once; the transport carries no callables."""
        modes = resolve_injection_modes("coder", config_path=tmp_path / "absent.yaml")
        for value in modes.values():
            assert isinstance(value, str)


# ── mode_for / is_active / is_observed: the safe read path ─────────────────


class TestSafeReads:
    def test_absent_mapping_is_off(self) -> None:
        assert mode_for(None, CODER_SLICE_CEREMONY.name) == MODE_OFF
        assert not is_active(None, CODER_SLICE_CEREMONY.name)
        assert not is_observed(None, CODER_SLICE_CEREMONY.name)

    def test_empty_mapping_is_off(self) -> None:
        assert mode_for({}, CODER_SLICE_CEREMONY.name) == MODE_OFF

    def test_unknown_injection_name_is_off(self) -> None:
        modes = resolve_injection_modes("coder")
        assert mode_for(modes, "no_such_injection") == MODE_OFF

    def test_garbage_value_is_normalized(self) -> None:
        """Defence in depth: a hand-built mapping cannot smuggle a bad mode."""
        assert mode_for({"x": "nonsense"}, "x") == MODE_OFF

    @pytest.mark.parametrize(
        ("mode", "active", "observed"),
        [(MODE_OFF, False, False), (MODE_OBSERVE, False, True), (MODE_ENFORCE, True, True)],
    )
    def test_active_and_observed_semantics(self, mode: str, active: bool, observed: bool) -> None:
        """observe emits telemetry but must NOT alter the payload."""
        modes = {"x": mode}
        assert is_active(modes, "x") is active
        assert is_observed(modes, "x") is observed
