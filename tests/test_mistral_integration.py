"""Tests for Mistral-related changes in chain config and family extraction.

Verifies:
- ChainConfig.extras field is populated from YAML
- Role-level extras merge with prompt-composer extras in RequestInfo
- Mistral family extraction from model slugs
- Mistral added to KNOWN_FAMILIES
- Family-disjoint check works with mistral family
"""

from __future__ import annotations

import pytest

from fa.providers.chain import chain_from_mapping
from fa.roles import KNOWN_FAMILIES, check_eval_disjoint, extract_family

# ── ChainConfig.extras ──────────────────────────────────────────────


class TestChainConfigExtras:
    """Test that ChainConfig.extras is populated from YAML."""

    def test_extras_parsed_from_yaml(self) -> None:
        """Role-level extras are parsed from the YAML mapping."""
        raw = {
            "model": "mistral-medium-2604",
            "family": "mistral",
            "chain": [
                {
                    "provider": "mistral",
                    "slug": "mistral-medium-2604",
                    "base_url": "https://api.mistral.ai/v1",
                    "api_key_env": "MISTRAL_API_KEY",
                }
            ],
            "extras": {
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
        config = chain_from_mapping("planner", raw)
        assert config.extras["reasoning_effort"] == "high"
        assert config.extras["prompt_cache_key"] == "planner-v1"
        assert config.extras["response_format"]["type"] == "json_schema"

    def test_extras_missing_defaults_empty(self) -> None:
        """No extras field yields empty dict."""
        raw = {
            "model": "gpt-4",
            "family": "openai",
            "chain": [
                {
                    "provider": "openrouter",
                    "slug": "openai/gpt-4",
                    "base_url": "https://openrouter.ai/api/v1",
                    "api_key_env": "OPENROUTER_API_KEY",
                }
            ],
        }
        config = chain_from_mapping("coder", raw)
        assert config.extras == {}

    def test_extras_null_defaults_empty(self) -> None:
        """extras: null yields empty dict."""
        raw = {
            "model": "gpt-4",
            "family": "openai",
            "chain": [
                {
                    "provider": "openrouter",
                    "slug": "openai/gpt-4",
                    "base_url": "https://openrouter.ai/api/v1",
                    "api_key_env": "OPENROUTER_API_KEY",
                }
            ],
            "extras": None,
        }
        config = chain_from_mapping("coder", raw)
        assert config.extras == {}

    def test_extras_prediction_field(self) -> None:
        """Prediction field in extras is preserved."""
        raw = {
            "model": "mistral-medium-2604",
            "family": "mistral",
            "chain": [
                {
                    "provider": "mistral",
                    "slug": "mistral-medium-2604",
                    "base_url": "https://api.mistral.ai/v1",
                    "api_key_env": "MISTRAL_API_KEY",
                }
            ],
            "extras": {
                "prediction": {
                    "type": "content",
                    "content": "Previous summary text",
                },
            },
        }
        config = chain_from_mapping("planner", raw)
        assert config.extras["prediction"]["type"] == "content"
        assert config.extras["prediction"]["content"] == "Previous summary text"

    def test_extras_non_mapping_ignored(self) -> None:
        """Non-mapping extras (e.g. string) is treated as empty."""
        raw = {
            "model": "gpt-4",
            "family": "openai",
            "chain": [
                {
                    "provider": "openrouter",
                    "slug": "openai/gpt-4",
                    "base_url": "https://openrouter.ai/api/v1",
                    "api_key_env": "OPENROUTER_API_KEY",
                }
            ],
            "extras": "invalid",
        }
        config = chain_from_mapping("coder", raw)
        assert config.extras == {}


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
  model: "mistral-medium-2604"
  family: "mistral"
  chain:
    - provider: mistral
      slug: "mistral-medium-2604"
      base_url: "https://api.mistral.ai/v1"
      api_key_env: MISTRAL_API_KEY
  extras:
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
        assert config.roles["planner"].extras["reasoning_effort"] == "high"

    def test_mistral_agents_role_loads(self) -> None:
        """A mistral_agents role config loads without errors."""
        from fa.providers.config import load_models_config

        yaml_text = """
coder:
  model: "mistral-medium-2604"
  family: "mistral"
  chain:
    - provider: mistral_agents
      slug: "mistral-medium-2604"
      base_url: "https://api.mistral.ai/v1"
      api_key_env: MISTRAL_API_KEY
  extras:
    mistral_tools:
      - type: web_search
"""
        config = load_models_config(
            yaml_text,
            env={"MISTRAL_API_KEY": "test-key"},
            require_api_keys=True,
        )
        assert "coder" in config.roles
        assert config.roles["coder"].extras["mistral_tools"][0]["type"] == "web_search"

    def test_mixed_mistral_openai_config(self) -> None:
        """Mixed Mistral + OpenAI config loads and family-disjoint passes."""
        from fa.providers.config import load_models_config

        yaml_text = """
planner:
  model: "mistral-medium-2604"
  family: "mistral"
  chain:
    - provider: mistral
      slug: "mistral-medium-2604"
      base_url: "https://api.mistral.ai/v1"
      api_key_env: MISTRAL_API_KEY
coder:
  model: "deepseek-v3"
  family: "deepseek"
  chain:
    - provider: openrouter
      slug: "deepseek/deepseek-chat-v3"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: OPENROUTER_API_KEY
eval:
  model: "gpt-4o"
  family: "openai"
  chain:
    - provider: openrouter
      slug: "openai/gpt-4o"
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
