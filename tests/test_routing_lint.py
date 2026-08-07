"""Shift-left ``models.yaml`` routing lint (fa.providers.routing_lint).

Regression coverage for the incident that motivated this module: a
``models.yaml`` chain entry with a typo'd ``base_url``
(``https://api.mistral.ai/vl`` instead of ``.../v1``) went undetected by
every existing static check (YAML parse, ChainConfig.validate's https-only
scheme guard, provider-name allowlist) and only surfaced as a Docker
``fa-egress-proxy`` crash-loop / "container is unhealthy" failure at
deploy time — 2+ minutes and a full image rebuild after the typo was
introduced.

Two independent checks are exercised:

- the cross-role route-conflict check (a pre-existing capability inside
  :func:`fa.egress_proxy.routing.build_route_table`, now surfaced offline
  instead of only at container-start time);
- the new same-provider near-miss base_url heuristic, which is the ONLY
  check that catches a typo in a *lone* chain entry with no conflicting
  sibling to disagree with — the exact shape that would defeat check #1
  alone.
"""

from __future__ import annotations

from pathlib import Path

from _pytest.capture import CaptureFixture

from fa.cli import build_parser
from fa.providers.config import ModelsConfig, load_models_config
from fa.providers.routing_lint import CANONICAL_PROVIDER_BASE_URLS, lint_models_config


def _models(text: str) -> ModelsConfig:
    return load_models_config(text, env={}, require_api_keys=False)


def _run_routing_check_cli(config_path: Path) -> int:
    parser = build_parser()
    args = parser.parse_args(["routing-check", "--config", str(config_path)])
    result: int = args.func(args)
    return result


class TestRouteConflictDetection:
    """Cross-role conflict check — mirrors build_route_table's own contract."""

    def test_flags_conflicting_upstreams_across_roles(self) -> None:
        models = _models(
            """
planner:
  name: mistral-small
  family: mistral
  chain:
    - provider: mistral
      model: "mistral-small-2603"
      base_url: "https://api.mistral.ai/vl"
      api_key_env: MISTRAL_API_KEY
coder:
  name: mistral-small
  family: mistral
  chain:
    - provider: mistral
      model: "mistral-small-2603"
      base_url: "https://api.mistral.ai/v1"
      api_key_env: MISTRAL_API_KEY
"""
        )
        findings = lint_models_config(models)
        conflict = [f for f in findings if f.category == "route_conflict"]
        assert len(conflict) == 1
        assert "conflicting upstreams" in conflict[0].message
        assert "api.mistral.ai/vl" in conflict[0].message
        assert "api.mistral.ai/v1" in conflict[0].message
        # Regression: the finding must cite WHICH chain entries collided,
        # not just the abstract route name — the operator needs to know
        # where in models.yaml to look.
        assert "role 'planner' chain[0]" in conflict[0].message
        assert "role 'coder' chain[0]" in conflict[0].message

    def test_flags_identical_base_url_with_different_api_key_env(self) -> None:
        # Regression for the real-world incident: a "multi-key rotation"
        # models.yaml shape (several chain entries for the same
        # (provider, slug) pair, each with a DIFFERENT api_key_env, intended
        # as per-provider key rotation). The base_urls are byte-identical,
        # so the message must name api_key_env as the actual differing
        # field instead of misleadingly printing "url vs url".
        models = _models(
            """
coder:
  name: mistral-small
  family: mistral
  chain:
    - provider: mistral
      model: "mistral-small-2603"
      base_url: "https://api.mistral.ai/v1"
      api_key_env: MISTRAL_API_KEY
    - provider: mistral
      model: "mistral-small-2603"
      base_url: "https://api.mistral.ai/v1"
      api_key_env: MISTRAL_API_KEY_1
    - provider: mistral
      model: "mistral-small-2603"
      base_url: "https://api.mistral.ai/v1"
      api_key_env: MISTRAL_API_KEY_2
"""
        )
        findings = lint_models_config(models)
        conflict = [f for f in findings if f.category == "route_conflict"]
        assert len(conflict) == 1
        message = conflict[0].message
        assert "conflicting upstreams" not in message  # not a URL mismatch
        assert "api_key_env" in message
        assert "MISTRAL_API_KEY" in message
        assert "MISTRAL_API_KEY_1" in message
        assert "role 'coder' chain[0]" in message
        assert "role 'coder' chain[1]" in message
        assert "role 'coder' chain[2]" in message

    def test_matching_duplicate_route_is_not_a_conflict(self) -> None:
        # Same (provider, slug, base_url) reused across roles collapses to
        # one route with no complaint — this is the normal "share a model
        # across roles" shape, not a misconfiguration.
        models = _models(
            """
planner:
  name: llama
  family: llama
  chain:
    - provider: openrouter
      model: "meta-llama/llama-3.1-8b"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: OPENROUTER_API_KEY
coder:
  name: llama
  family: llama
  chain:
    - provider: openrouter
      model: "meta-llama/llama-3.1-8b"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: OPENROUTER_API_KEY
"""
        )
        assert lint_models_config(models) == []


class TestNearMissBaseUrlHeuristic:
    """Catches a typo'd base_url even with no conflicting sibling entry."""

    def test_flags_lone_typo_with_no_conflicting_sibling(self) -> None:
        # This is the case route-conflict detection alone CANNOT catch:
        # exactly one chain entry, so there is nothing to conflict with.
        models = _models(
            """
coder:
  name: mistral-small
  family: mistral
  chain:
    - provider: mistral
      model: "mistral-small-2603"
      base_url: "https://api.mistral.ai/vl"
      api_key_env: MISTRAL_API_KEY
"""
        )
        findings = lint_models_config(models)
        near_miss = [f for f in findings if f.category == "near_miss_base_url"]
        assert len(near_miss) == 1
        assert "api.mistral.ai/vl" in near_miss[0].message
        assert "api.mistral.ai/v1" in near_miss[0].message
        assert near_miss[0].role == "coder"
        # Regression: must cite the exact chain index, not just the role,
        # so the operator can find the right block when a role has
        # multiple chain entries.
        assert "chain[0]" in near_miss[0].message

    def test_exact_canonical_match_is_clean(self) -> None:
        models = _models(
            """
coder:
  name: mistral-small
  family: mistral
  chain:
    - provider: mistral
      model: "mistral-small-2603"
      base_url: "https://api.mistral.ai/v1"
      api_key_env: MISTRAL_API_KEY
"""
        )
        assert lint_models_config(models) == []

    def test_trailing_slash_on_canonical_is_not_flagged(self) -> None:
        models = _models(
            """
coder:
  name: llama
  family: llama
  chain:
    - provider: openrouter
      model: "meta-llama/llama-3.1-8b"
      base_url: "https://openrouter.ai/api/v1/"
      api_key_env: OPENROUTER_API_KEY
"""
        )
        assert lint_models_config(models) == []

    def test_deliberately_different_gateway_is_not_flagged(self) -> None:
        # A genuinely different host (self-hosted/local gateway) must not be
        # treated as a typo of the canonical cloud endpoint — the heuristic
        # is scoped to same-host comparisons only.
        models = _models(
            """
coder:
  name: custom
  family: custom
  chain:
    - provider: mistral
      model: "custom-model"
      base_url: "http://localhost:8080/v1"
      api_key_env: LOCAL_KEY
"""
        )
        assert lint_models_config(models) == []

    def test_mistral_and_mistral_agents_share_host_but_different_shapes_ok(self) -> None:
        # Regression guard for the adapter-specific base_url shape: mistral
        # (.../v1, generic OpenAI-compatible-ish chat) and mistral_agents
        # (bare host, /v1/conversations appended internally) legitimately
        # differ even though both target api.mistral.ai. Keying the
        # canonical table by provider name (not host) must not cross-flag
        # one shape as a near-miss of the other's canonical URL.
        models = _models(
            """
coder:
  name: mistral-small
  family: mistral
  chain:
    - provider: mistral
      model: "mistral-small-2603"
      base_url: "https://api.mistral.ai/v1"
      api_key_env: MISTRAL_API_KEY
planner:
  name: mistral-medium
  family: mistral
  chain:
    - provider: mistral_agents
      model: "mistral-medium"
      base_url: "https://api.mistral.ai"
      api_key_env: MISTRAL_API_KEY
"""
        )
        assert lint_models_config(models) == []

    def test_unregistered_canonical_provider_is_never_flagged(self) -> None:
        # A provider with no entry in CANONICAL_PROVIDER_BASE_URLS (e.g. a
        # pure-aggregator platform with no single fixed endpoint) must be
        # silently skipped by the heuristic, not flagged for "no match".
        models = _models(
            """
coder:
  name: whatever
  family: whatever
  chain:
    - provider: alistaitsacle
      model: "whatever-model"
      base_url: "https://some.completely.unrelated.host/v9"
      api_key_env: ALISTAITSACLE_API_KEY
"""
        )
        assert "alistaitsacle" not in CANONICAL_PROVIDER_BASE_URLS
        assert lint_models_config(models) == []

    def test_aigate_and_anymodel_canonical_base_urls(self) -> None:
        assert CANONICAL_PROVIDER_BASE_URLS["aigate"] == ("https://api.aigate.shop/v1",)
        assert CANONICAL_PROVIDER_BASE_URLS["anymodel"] == ("https://anymodel.org/v1",)


class TestUnknownProviderParamsKey:
    """Catches a typo'd provider_params key (e.g. reasoning_efort) that
    body.setdefault(key, value) would otherwise silently swallow with no
    error anywhere — the provider simply never receives the intended field.
    """

    def test_flags_typo_in_mistral_provider_params(self) -> None:
        models = _models(
            """
coder:
  name: mistral-small
  family: mistral
  chain:
    - provider: mistral
      model: "mistral-small-2603"
      base_url: "https://api.mistral.ai/v1"
      api_key_env: MISTRAL_API_KEY
      provider_params:
        reasoning_efort: "high"
"""
        )
        findings = lint_models_config(models)
        unknown = [f for f in findings if f.category == "unknown_provider_params_key"]
        assert len(unknown) == 1
        assert "reasoning_efort" in unknown[0].message
        assert "reasoning_effort" in unknown[0].message  # known-keys list must name the likely intended key
        assert "chain[0]" in unknown[0].message
        assert unknown[0].role == "coder"

    def test_known_mistral_key_is_not_flagged(self) -> None:
        models = _models(
            """
coder:
  name: mistral-small
  family: mistral
  chain:
    - provider: mistral
      model: "mistral-small-2603"
      base_url: "https://api.mistral.ai/v1"
      api_key_env: MISTRAL_API_KEY
      provider_params:
        reasoning_effort: "high"
        safe_prompt: false
"""
        )
        assert lint_models_config(models) == []

    def test_known_mistral_agents_key_is_not_flagged(self) -> None:
        # mistral_agents (Conversations API) has a DIFFERENT recognised-key
        # set than mistral (chat completions) — mistral_tools/store/agent_id
        # are valid here but would be unknown for the plain mistral adapter.
        models = _models(
            """
coder:
  name: mistral-medium
  family: mistral
  chain:
    - provider: mistral_agents
      model: "mistral-medium-2604"
      base_url: "https://api.mistral.ai"
      api_key_env: MISTRAL_API_KEY
      provider_params:
        mistral_tools:
          - type: web_search
        store: true
        agent_id: "agt-123"
"""
        )
        assert lint_models_config(models) == []

    def test_mistral_agents_key_is_flagged_on_plain_mistral_provider(self) -> None:
        # Regression guard for the two adapters' DIFFERENT key sets: a key
        # valid for mistral_agents (mistral_tools) must still be flagged as
        # unknown when used on the plain mistral (chat-completions) entry.
        models = _models(
            """
coder:
  name: mistral-small
  family: mistral
  chain:
    - provider: mistral
      model: "mistral-small-2603"
      base_url: "https://api.mistral.ai/v1"
      api_key_env: MISTRAL_API_KEY
      provider_params:
        mistral_tools:
          - type: web_search
"""
        )
        findings = lint_models_config(models)
        unknown = [f for f in findings if f.category == "unknown_provider_params_key"]
        assert len(unknown) == 1
        assert "mistral_tools" in unknown[0].message

    def test_unrestricted_adapter_is_never_flagged(self) -> None:
        # openai_compat-category providers (openrouter, fireworks, ...) and
        # anthropic do unrestricted body.setdefault passthrough with no
        # fixed key set — there is nothing to validate against, so ANY
        # provider_params content must be silently accepted, not flagged.
        models = _models(
            """
coder:
  name: deepseek-v3
  family: deepseek
  chain:
    - provider: openrouter
      model: "deepseek/deepseek-chat-v3"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: OPENROUTER_API_KEY
      provider_params:
        some_totally_made_up_field: "x"
"""
        )
        assert lint_models_config(models) == []

    def test_no_provider_params_is_never_flagged(self) -> None:
        models = _models(
            """
coder:
  name: mistral-small
  family: mistral
  chain:
    - provider: mistral
      model: "mistral-small-2603"
      base_url: "https://api.mistral.ai/v1"
      api_key_env: MISTRAL_API_KEY
"""
        )
        assert lint_models_config(models) == []


class TestLintReturnsBothFindingKindsTogether:
    def test_a_single_bad_config_can_surface_both_findings_at_once(self) -> None:
        # The motivating incident: one typo simultaneously creates a
        # near-miss (vs the canonical URL) AND a conflict (vs the sibling
        # role's correct entry). Both must be reported, not just the first.
        models = _models(
            """
planner:
  name: mistral-small
  family: mistral
  chain:
    - provider: mistral
      model: "mistral-small-2603"
      base_url: "https://api.mistral.ai/vl"
      api_key_env: MISTRAL_API_KEY
coder:
  name: mistral-small
  family: mistral
  chain:
    - provider: mistral
      model: "mistral-small-2603"
      base_url: "https://api.mistral.ai/v1"
      api_key_env: MISTRAL_API_KEY
"""
        )
        findings = lint_models_config(models)
        categories = {f.category for f in findings}
        assert categories == {"route_conflict", "near_miss_base_url"}


class TestRoutingCheckCliComposition:
    """C1 — boot through the real `fa routing-check` argparse entry point.

    A unit test against :func:`lint_models_config` alone would not catch a
    wiring break (e.g. the CLI silently swallowing findings, or exiting 0
    despite issues). This exercises the exact command-line surface an
    operator or a deploy-script preflight actually invokes.
    """

    def test_cli_reports_the_originally_reported_typo_and_exits_nonzero(
        self,
        tmp_path: Path,
        capsys: CaptureFixture[str],
    ) -> None:
        config_path = tmp_path / "models.yaml"
        config_path.write_text(
            """
planner:
  name: mistral-small
  family: mistral
  chain:
    - provider: mistral
      model: "mistral-small-2603"
      base_url: "https://api.mistral.ai/vl"
      api_key_env: MISTRAL_API_KEY
coder:
  name: mistral-small
  family: mistral
  chain:
    - provider: mistral
      model: "mistral-small-2603"
      base_url: "https://api.mistral.ai/v1"
      api_key_env: MISTRAL_API_KEY
""",
            encoding="utf-8",
        )
        exit_code = _run_routing_check_cli(config_path)
        out = capsys.readouterr().out
        assert exit_code == 1
        assert "ISSUES FOUND" in out
        assert "conflicting upstreams" in out
        assert "near_miss_base_url" in out

    def test_cli_exits_zero_on_a_clean_config(
        self,
        tmp_path: Path,
        capsys: CaptureFixture[str],
    ) -> None:
        config_path = tmp_path / "models.yaml"
        config_path.write_text(
            """
coder:
  name: llama
  family: llama
  chain:
    - provider: openrouter
      model: "meta-llama/llama-3.1-8b"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: OPENROUTER_API_KEY
""",
            encoding="utf-8",
        )
        exit_code = _run_routing_check_cli(config_path)
        out = capsys.readouterr().out
        assert exit_code == 0
        assert "OK" in out

    def test_cli_reports_a_malformed_yaml_config_error_distinctly(
        self,
        tmp_path: Path,
        capsys: CaptureFixture[str],
    ) -> None:
        config_path = tmp_path / "models.yaml"
        config_path.write_text(
            """
coder:
  name: llama
  family: llama
  chain:
    - provider: not_a_real_provider
      model: "x"
      base_url: "https://example.com/v1"
      api_key_env: X_API_KEY
""",
            encoding="utf-8",
        )
        exit_code = _run_routing_check_cli(config_path)
        out = capsys.readouterr().out
        assert exit_code == 2
        assert "ERROR" in out
