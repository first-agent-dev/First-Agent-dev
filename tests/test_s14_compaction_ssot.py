"""C1/source-contract tests for compaction enablement SSoT.

The numeric ``ChainConfig.compaction_threshold`` is the only enablement
surface: presence enables compaction, absence disables it. The former
``FeatureFlags.context_compaction_enabled`` key is legacy input only and
must be warned/ignored by the feature-flag loader.
"""

from __future__ import annotations

from pathlib import Path

from fa.feature_flags import FeatureFlags, load_feature_flags
from fa.providers.chain import ChainConfig


def test_compaction_enablement_uses_threshold_presence() -> None:
    """The production decision must be derived from threshold presence."""
    content = Path("src/fa/inner_loop/coder_loop.py").read_text(encoding="utf-8")
    assert "compaction_enabled = compaction_threshold is not None" in content


def test_legacy_compaction_flag_is_not_a_current_feature_field() -> None:
    """The redundant boolean is absent from the frozen current config."""
    field_names = {field.name for field in FeatureFlags.__dataclass_fields__.values()}
    assert "context_compaction_enabled" not in field_names
    assert "context_compaction_enabled" not in FeatureFlags().as_dict()


def test_legacy_compaction_flag_warns_and_is_ignored() -> None:
    result = load_feature_flags("feature_flags:\n  context_compaction_enabled: true\n  context_budget_enabled: true\n")
    assert result.flags.context_budget_enabled is True
    assert any(
        warning.key == "context_compaction_enabled" and "deprecated" in warning.detail and "ignored" in warning.detail
        for warning in result.warnings
    )


def test_threshold_is_the_chain_config_surface() -> None:
    disabled = ChainConfig(
        role="coder",
        name="test-model",
        family="openai",
        chain=(),
        context_limit=100_000,
        compaction_threshold=None,
    )
    enabled = ChainConfig(
        role="coder",
        name="test-model",
        family="openai",
        chain=(),
        context_limit=100_000,
        compaction_threshold=80_000,
    )
    assert disabled.compaction_threshold is None
    assert enabled.compaction_threshold == 80_000
