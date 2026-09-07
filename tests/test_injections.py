"""PLAN S5a — the injection registry, mode resolution, and hot reload.

root=injections class=C0/C1 claim=G1 path=T4a,T4b,T4f
oracle=exact resolved mode strings for a given (spec, role, config) triple.
producer-kill-check=deleting the role gate in resolve_mode makes
test_role_outside_spec_is_always_off fail; replacing the resolver mapping with
eagerly-resolved strings makes test_config_edit_is_observed_without_restart fail.

The hot-reload tests are the load-bearing ones: a future WebUI toggle writes
config and expects a RUNNING agent to follow. That property is invisible to a
signature test and is exactly what a "resolve once at startup" refactor would
silently destroy, so it is pinned against a real file on disk.
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
    InjectionSpec,
    build_injection_modes,
    is_active,
    is_observed,
    mode_for,
    normalize_mode,
    reset_flag_cache,
    resolve_mode,
)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """The module caches config reads; tests must not inherit each other's."""
    reset_flag_cache()


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


# ── hot reload (the WebUI-toggle requirement) ──────────────────────────────


class TestHotReload:
    def test_config_edit_is_observed_without_restart(self, tmp_path: Path) -> None:
        """PRODUCER KILL-CHECK for laziness.

        The whole point of threading resolvers instead of strings. If a
        refactor resolves modes once at session start, this fails: the second
        read would still report the first value.
        """
        cfg = tmp_path / "config.yaml"
        _write_config(cfg, "off")
        modes = build_injection_modes("coder", config_path=cfg)
        assert mode_for(modes, CODER_SLICE_CEREMONY.name) == MODE_OFF

        _write_config(cfg, "enforce")
        reset_flag_cache()  # stands in for the TTL expiring
        assert mode_for(modes, CODER_SLICE_CEREMONY.name) == MODE_ENFORCE

    def test_toggle_back_off_also_takes_effect(self, tmp_path: Path) -> None:
        """A toggle that only turns on would be a trap."""
        cfg = tmp_path / "config.yaml"
        _write_config(cfg, "enforce")
        modes = build_injection_modes("coder", config_path=cfg)
        assert is_active(modes, CODER_SLICE_CEREMONY.name)

        _write_config(cfg, "off")
        reset_flag_cache()
        assert not is_active(modes, CODER_SLICE_CEREMONY.name)

    def test_building_the_mapping_reads_no_config(self, tmp_path: Path) -> None:
        """Resolvers are lazy: a session that never asks never pays."""
        missing = tmp_path / "never-created.yaml"
        modes = build_injection_modes("coder", config_path=missing)
        assert set(modes) == set(INJECTION_SPECS)
        assert not missing.exists()


# ── mode_for / is_active / is_observed: the safe read path ─────────────────


class TestSafeReads:
    def test_absent_mapping_is_off(self) -> None:
        assert mode_for(None, CODER_SLICE_CEREMONY.name) == MODE_OFF
        assert not is_active(None, CODER_SLICE_CEREMONY.name)
        assert not is_observed(None, CODER_SLICE_CEREMONY.name)

    def test_empty_mapping_is_off(self) -> None:
        assert mode_for({}, CODER_SLICE_CEREMONY.name) == MODE_OFF

    def test_unknown_injection_name_is_off(self) -> None:
        modes = build_injection_modes("coder")
        assert mode_for(modes, "no_such_injection") == MODE_OFF

    def test_raising_resolver_degrades_to_off(self) -> None:
        """An advisory feature must never crash a run."""

        def _boom() -> str:
            raise RuntimeError("config exploded")

        assert mode_for({"x": _boom}, "x") == MODE_OFF

    def test_resolver_returning_garbage_is_normalized(self) -> None:
        assert mode_for({"x": lambda: "nonsense"}, "x") == MODE_OFF

    @pytest.mark.parametrize(
        ("mode", "active", "observed"),
        [(MODE_OFF, False, False), (MODE_OBSERVE, False, True), (MODE_ENFORCE, True, True)],
    )
    def test_active_and_observed_semantics(self, mode: str, active: bool, observed: bool) -> None:
        """observe emits telemetry but must NOT alter the payload."""
        modes = {"x": lambda m=mode: m}
        assert is_active(modes, "x") is active
        assert is_observed(modes, "x") is observed
