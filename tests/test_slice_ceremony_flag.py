"""PLAN S4 — the slice_ceremony_mode feature flag.

root=feature-flags class=C0 claim=G4 path=T4
oracle=exact FeatureFlags field value / as_dict key / categorization membership.
producer-kill-check=deleting the loader line at feature_flags.py:~308 makes
test_loads_from_dotted_key fail; deleting the FAIL_OPEN_FLAGS entry makes both
test_is_categorized here and tests/test_s13_fail_closed_open.py fail.

Mirrors the established pattern in tests/test_intent_guard_mode.py:108.
"""

from __future__ import annotations

import pytest

from fa.feature_flags import (
    FAIL_CLOSED_FLAGS,
    FAIL_OPEN_FLAGS,
    SLICE_CEREMONY_FALLBACK_MODE,
    SLICE_CEREMONY_MODES,
    FeatureFlags,
    load_feature_flags,
)

FIELD = "slice_ceremony_mode"
DOTTED = "slice_ceremony.mode"


class TestDefault:
    def test_default_is_observe(self) -> None:
        """Telemetry-first rollout: the flag must not change behaviour until
        the operator opts in."""
        assert FeatureFlags().slice_ceremony_mode == "observe"

    def test_default_is_a_member_of_the_enum(self) -> None:
        assert FeatureFlags().slice_ceremony_mode in SLICE_CEREMONY_MODES

    def test_fallback_is_a_member_of_the_enum(self) -> None:
        assert SLICE_CEREMONY_FALLBACK_MODE in SLICE_CEREMONY_MODES

    def test_enum_is_the_documented_three_states(self) -> None:
        assert SLICE_CEREMONY_MODES == frozenset({"off", "observe", "enforce"})

    def test_fallback_is_not_enforce(self) -> None:
        """A malformed config must never silently start rewriting prompts."""
        assert SLICE_CEREMONY_FALLBACK_MODE != "enforce"


class TestLoading:
    @pytest.mark.parametrize("mode", sorted(SLICE_CEREMONY_MODES))
    def test_loads_from_dotted_key(self, mode: str) -> None:
        result = load_feature_flags(f"{DOTTED}: {mode}\n")
        assert result.flags.slice_ceremony_mode == mode

    @pytest.mark.parametrize("mode", sorted(SLICE_CEREMONY_MODES))
    def test_loads_from_underscore_alias(self, mode: str) -> None:
        result = load_feature_flags(f"{FIELD}: {mode}\n")
        assert result.flags.slice_ceremony_mode == mode

    def test_missing_key_yields_default(self) -> None:
        assert load_feature_flags("").flags.slice_ceremony_mode == "observe"

    def test_unknown_value_is_preserved_verbatim_at_load(self) -> None:
        """Load records what the operator wrote; the consumer corrects it.

        Normalising here would hide the typo from any diagnostic that prints
        the loaded config.
        """
        result = load_feature_flags(f"{DOTTED}: bogus\n")
        assert result.flags.slice_ceremony_mode == "bogus"
        assert result.flags.slice_ceremony_mode not in SLICE_CEREMONY_MODES


class TestRegistration:
    def test_exposed_in_as_dict(self) -> None:
        assert FeatureFlags().as_dict()[DOTTED] == "observe"

    def test_is_categorized(self) -> None:
        """Hard constraint from tests/test_s13_fail_closed_open.py:22."""
        assert FIELD in FAIL_CLOSED_FLAGS | FAIL_OPEN_FLAGS

    def test_is_fail_open_not_fail_closed(self) -> None:
        """This flag guards an advisory injection, not a safety boundary."""
        assert FIELD in FAIL_OPEN_FLAGS
        assert FIELD not in FAIL_CLOSED_FLAGS

    def test_categories_stay_disjoint(self) -> None:
        assert not (FAIL_CLOSED_FLAGS & FAIL_OPEN_FLAGS)
