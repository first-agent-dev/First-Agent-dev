"""Tests for Mistral-related changes in chain config and family extraction.

Verifies:
- ChainEntry.provider_params is populated from YAML (per-entry, ADR-9
  §Amendment 2026-07-23 — was role-level ChainConfig.extras before the
  amendment; moved because role-level extras were broadcast unconditionally
  to every chain entry regardless of provider)
- Mistral family extraction from model slugs
- Mistral added to KNOWN_FAMILIES
- Family-disjoint check works with mistral family
"""

from __future__ import annotations

import pytest

from fa.providers.chain import chain_from_mapping
from fa.roles import KNOWN_FAMILIES, check_eval_disjoint, extract_family

# ── ChainEntry.provider_params ──────────────────────────────────────


class TestChainEntryProviderParams:
    """Test that ChainEntry.provider_params is populated from YAML."""

    def test_provider_params_parsed_from_yaml(self) -> None:
        """Per-entry provider_params are parsed from the YAML mapping."""
        raw = {
            "name": "mistral-medium-2604",
            "family": "mistral",
            "chain": [
                {
                    "provider": "mistral",
                    "model": "mistral-medium-2604",
                    "base_url": "https://api.mistral.ai/v1",
                    "api_key_env": "MISTRAL_API_KEY",
                    "provider_params": {
                        "reasoning_effort": "high",
                        "prompt_cache_key": "planner-v1",
                        "response_format": {
                            "type": "json_schema",
                            "json_schema": {
                                "name": "summary",
                                "schema": {"type": "object", "properties": {"points": {"type": "array"}}},
                            },
                        },
                    },
                }
            ],
        }
        config = chain_from_mapping("planner", raw)
        entry = config.chain[0]
        assert entry.provider_params["reasoning_effort"] == "high"
        assert entry.provider_params["prompt_cache_key"] == "planner-v1"
        assert entry.provider_params["response_format"]["type"] == "json_schema"

    def test_provider_params_missing_defaults_empty(self) -> None:
        """No provider_params field yields empty dict."""
        raw = {
            "name": "gpt-4",
            "family": "openai",
            "chain": [
                {
                    "provider": "openrouter",
                    "model": "openai/gpt-4",
                    "base_url": "https://openrouter.ai/api/v1",
                    "api_key_env": "OPENROUTER_API_KEY",
                }
            ],
        }
        config = chain_from_mapping("coder", raw)
        assert config.chain[0].provider_params == {}

    def test_provider_params_null_defaults_empty(self) -> None:
        """provider_params: null yields empty dict."""
        raw = {
            "name": "gpt-4",
            "family": "openai",
            "chain": [
                {
                    "provider": "openrouter",
                    "model": "openai/gpt-4",
                    "base_url": "https://openrouter.ai/api/v1",
                    "api_key_env": "OPENROUTER_API_KEY",
                    "provider_params": None,
                }
            ],
        }
        config = chain_from_mapping("coder", raw)
        assert config.chain[0].provider_params == {}

    def test_provider_params_prediction_field(self) -> None:
        """Prediction field in provider_params is preserved."""
        raw = {
            "name": "mistral-medium-2604",
            "family": "mistral",
            "chain": [
                {
                    "provider": "mistral",
                    "model": "mistral-medium-2604",
                    "base_url": "https://api.mistral.ai/v1",
                    "api_key_env": "MISTRAL_API_KEY",
                    "provider_params": {
                        "prediction": {
                            "type": "content",
                            "content": "Previous summary text",
                        },
                    },
                }
            ],
        }
        config = chain_from_mapping("planner", raw)
        entry = config.chain[0]
        assert entry.provider_params["prediction"]["type"] == "content"
        assert entry.provider_params["prediction"]["content"] == "Previous summary text"

    def test_provider_params_does_not_leak_to_sibling_entry(self) -> None:
        """Regression (the bug this amendment fixed): a Mistral entry's
        provider_params must not appear on a sibling OpenRouter entry's
        provider_params — the two are independent per-entry dicts, unlike
        the historical role-level `extras` which was shared/broadcast."""
        raw = {
            "name": "mistral-small-2603",
            "family": "mistral",
            "chain": [
                {
                    "provider": "mistral",
                    "model": "mistral-small-2603",
                    "base_url": "https://api.mistral.ai/v1",
                    "api_key_env": "MISTRAL_API_KEY",
                    "provider_params": {"reasoning_effort": "high"},
                },
                {
                    "provider": "openrouter",
                    "model": "mistralai/mistral-small",
                    "base_url": "https://openrouter.ai/api/v1",
                    "api_key_env": "OPENROUTER_API_KEY",
                },
            ],
        }
        config = chain_from_mapping("coder", raw)
        assert config.chain[0].provider_params == {"reasoning_effort": "high"}
        assert config.chain[1].provider_params == {}


# ── Family extraction ───────────────────────────────────────────────


class TestMistralFamilyExtraction:
    """Test that Mistral model slugs are recognized."""

    def test_mistral_in_known_families(self) -> None:
        """'mistral' is in KNOWN_FAMILIES."""
        assert "mistral" in KNOWN_FAMILIES

    def test_extract_mistral_medium(self) -> None:
        """mistral-medium-2604 extracts to 'mistral'."""
        assert extract_family("mistral-medium-2604") == "mistral"

    def test_extract_mistral_small(self) -> None:
        """mistral-small-latest extracts to 'mistral'."""
        assert extract_family("mistral-small-latest") == "mistral"

    def test_extract_mistral_large(self) -> None:
        """mistral-large-2411 extracts to 'mistral'."""
        assert extract_family("mistral-large-2411") == "mistral"

    def test_extract_codestral(self) -> None:
        """codestral-latest extracts to 'mistral'."""
        assert extract_family("codestral-latest") == "mistral"

    def test_extract_ministral(self) -> None:
        """ministral-8b-latest extracts to 'mistral'."""
        assert extract_family("ministral-8b-latest") == "mistral"

    def test_extract_magistral(self) -> None:
        """magistral-medium-latest extracts to 'mistral'."""
        assert extract_family("magistral-medium-latest") == "mistral"

    def test_extract_openrouter_mistralai(self) -> None:
        """mistralai/mistral-medium-latest (OpenRouter prefix) extracts to 'mistral'."""
        assert extract_family("mistralai/mistral-medium-latest") == "mistral"

    def test_extract_openrouter_mistralai_codestral(self) -> None:
        """mistralai/codestral-latest extracts to 'mistral'."""
        assert extract_family("mistralai/codestral-latest") == "mistral"

    def test_family_override_mistral(self) -> None:
        """Explicit family override works for 'mistral'."""
        assert extract_family("custom-model", override="mistral") == "mistral"

    def test_eval_disjoint_with_mistral(self) -> None:
        """Eval must be disjoint from planner/coder even when one is mistral."""
        # This should NOT raise (different families)
        check_eval_disjoint(
            planner_family="mistral",
            coder_family="openai",
            eval_family="deepseek",
        )

    def test_eval_conflict_with_mistral(self) -> None:
        """Eval matching mistral coder raises EvalFamilyConflictError."""
        from fa.roles import EvalFamilyConflictError

        with pytest.raises(EvalFamilyConflictError):
            check_eval_disjoint(
                planner_family="openai",
                coder_family="mistral",
                eval_family="mistral",
            )


# ── Config loader integration ───────────────────────────────────────


class TestMistralConfigLoader:
    """Test that Mistral configs load correctly via the full loader."""

    def test_mistral_role_loads(self) -> None:
        """A Mistral role config loads without errors."""
        from fa.providers.config import load_models_config

        yaml_text = """
planner:
  name: "mistral-medium-2604"
  family: "mistral"
  chain:
    - provider: mistral
      model: "mistral-medium-2604"
      base_url: "https://api.mistral.ai/v1"
      api_key_env: MISTRAL_API_KEY
      provider_params:
        reasoning_effort: "high"
        prompt_cache_key: "planner-v1"
"""
        config = load_models_config(
            yaml_text,
            env={"MISTRAL_API_KEY": "test-key"},
            require_api_keys=True,
        )
        assert "planner" in config.roles
        assert config.roles["planner"].family == "mistral"
        assert config.roles["planner"].chain[0].provider_params["reasoning_effort"] == "high"

    def test_mistral_agents_role_loads(self) -> None:
        """A mistral_agents role config loads without errors."""
        from fa.providers.config import load_models_config

        yaml_text = """
coder:
  name: "mistral-medium-2604"
  family: "mistral"
  chain:
    - provider: mistral_agents
      model: "mistral-medium-2604"
      base_url: "https://api.mistral.ai/v1"
      api_key_env: MISTRAL_API_KEY
      provider_params:
        mistral_tools:
          - type: web_search
"""
        config = load_models_config(
            yaml_text,
            env={"MISTRAL_API_KEY": "test-key"},
            require_api_keys=True,
        )
        assert "coder" in config.roles
        assert config.roles["coder"].chain[0].provider_params["mistral_tools"][0]["type"] == "web_search"

    def test_mixed_mistral_openai_config(self) -> None:
        """Mixed Mistral + OpenAI config loads and family-disjoint passes."""
        from fa.providers.config import load_models_config

        yaml_text = """
planner:
  name: "mistral-medium-2604"
  family: "mistral"
  chain:
    - provider: mistral
      model: "mistral-medium-2604"
      base_url: "https://api.mistral.ai/v1"
      api_key_env: MISTRAL_API_KEY
coder:
  name: "deepseek-v3"
  family: "deepseek"
  chain:
    - provider: openrouter
      model: "deepseek/deepseek-chat-v3"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: OPENROUTER_API_KEY
eval:
  name: "gpt-4o"
  family: "openai"
  chain:
    - provider: openrouter
      model: "openai/gpt-4o"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: OPENROUTER_API_KEY
"""
        config = load_models_config(
            yaml_text,
            env={"MISTRAL_API_KEY": "key1", "OPENROUTER_API_KEY": "key2"},
            require_api_keys=True,
        )
        assert len(config.roles) == 3
        # No family conflicts: mistral, deepseek, openai are all disjoint
