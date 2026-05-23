"""``~/.fa/models.yaml`` loader contract — offline tests (T-4).

Covers ADR-9 §1 schema parse (happy path, ADR-9 §1 example
verbatim), ADR-2 §Amendment 2026-05-20 rule 1 family-disjoint
enforcement (eval=planner / eval=coder reject; planner=coder OK),
empty / null / malformed YAML structure handling, and missing-file
behaviour for the path-based loader.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from fa.providers.chain import ChainConfig
from fa.providers.config import (
    DEFAULT_MODELS_YAML_PATH,
    ModelsConfig,
    load_models_config,
    load_models_config_from_path,
)
from fa.providers.errors import ConfigurationError
from fa.roles import EvalFamilyConflictError


def _env_with_keys(*key_names: str) -> dict[str, str]:
    """Build a synthetic env-mapping that satisfies the validator's
    `api_key_env` non-empty check for every key name in ``key_names``.
    Tests never use real provider API keys."""

    return dict.fromkeys(key_names, "test-key")


# ----- Happy-path parse (ADR-9 §1 example verbatim) ----------------


def test_load_models_config_parses_three_role_example() -> None:
    text = textwrap.dedent(
        """\
        coder:
          model:  "deepseek-v3"
          family: "deepseek"
          chain:
            - provider: openrouter
              slug:     "deepseek/deepseek-chat-v3"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
            - provider: fireworks
              slug:     "accounts/fireworks/models/deepseek-v3"
              base_url: "https://api.fireworks.ai/inference/v1"
              api_key_env: FIREWORKS_API_KEY
        planner:
          model:  "kimi-k2"
          family: "kimi"
          chain:
            - provider: openrouter
              slug:     "moonshotai/kimi-k2"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
        eval:
          model:  "qwen-3-32b"
          family: "qwen"
          chain:
            - provider: openrouter
              slug:     "qwen/qwen-3-32b-instruct"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
        """
    )
    env = _env_with_keys("OPENROUTER_API_KEY", "FIREWORKS_API_KEY")
    config = load_models_config(text, env=env)
    assert isinstance(config, ModelsConfig)
    assert set(config.roles) == {"coder", "planner", "eval"}
    assert isinstance(config.roles["coder"], ChainConfig)
    assert config.roles["coder"].model == "deepseek-v3"
    assert config.roles["coder"].family == "deepseek"
    assert len(config.roles["coder"].chain) == 2
    assert config.roles["coder"].chain[0].provider == "openrouter"
    assert config.roles["planner"].family == "kimi"
    assert config.roles["eval"].family == "qwen"
    # Warnings list MUST be a tuple (frozen-snapshot contract);
    # specific entries are allowed because the coder chain's
    # Fireworks slug (``accounts/fireworks/models/deepseek-v3``)
    # does not match any family regex in `fa.roles`, so the
    # validator's best-effort heuristic emits a «cannot infer
    # family from slug» warning. That is the documented behaviour;
    # only hard errors raise, soft heuristics warn.
    assert isinstance(config.warnings, tuple)


def test_load_models_config_preserves_chain_entry_optional_fields() -> None:
    text = textwrap.dedent(
        """\
        coder:
          model:  "deepseek-v3"
          family: "deepseek"
          chain:
            - provider: openrouter
              slug:     "deepseek/deepseek-chat-v3"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
              cooldown_seconds: 120
              httpx_retries: 2
              timeout_seconds: 30
              extra_headers:
                HTTP-Referer: "https://example.com"
                X-Title: "First-Agent"
        """
    )
    env = _env_with_keys("OPENROUTER_API_KEY")
    config = load_models_config(text, env=env)
    entry = config.roles["coder"].chain[0]
    assert entry.cooldown_seconds == 120
    assert entry.httpx_retries == 2
    assert entry.timeout_seconds == 30
    assert dict(entry.extra_headers) == {
        "HTTP-Referer": "https://example.com",
        "X-Title": "First-Agent",
    }


# ----- Empty / null / scalar root --------------------------------


def test_load_models_config_empty_text_yields_empty_config() -> None:
    # Empty file is a legal v0.1 state — the inner-loop decides
    # whether absence is fatal for its workflow.
    config = load_models_config("")
    assert config == ModelsConfig(roles={})


def test_load_models_config_whitespace_only_yields_empty_config() -> None:
    # Tabs are not valid YAML indentation per the YAML 1.2 spec, so
    # this test uses spaces / blank lines only. ``yaml.safe_load``
    # on this body returns ``None`` (same as empty file).
    config = load_models_config("   \n   \n")
    assert config == ModelsConfig(roles={})


def test_load_models_config_yaml_null_root_yields_empty_config() -> None:
    # ``~`` is YAML for ``null``; ``yaml.safe_load("~")`` returns
    # ``None``. The loader treats it the same as empty file.
    config = load_models_config("~")
    assert config == ModelsConfig(roles={})


def test_load_models_config_yaml_list_root_raises() -> None:
    text = textwrap.dedent(
        """\
        - planner
        - coder
        - eval
        """
    )
    with pytest.raises(ConfigurationError) as info:
        load_models_config(text)
    assert "must be a mapping" in str(info.value)


def test_load_models_config_yaml_scalar_root_raises() -> None:
    with pytest.raises(ConfigurationError) as info:
        load_models_config('"just-a-string"')
    assert "must be a mapping" in str(info.value)


# ----- Malformed role entries ------------------------------------


def test_load_models_config_role_value_null_raises() -> None:
    text = textwrap.dedent(
        """\
        coder:
        """
    )
    with pytest.raises(ConfigurationError) as info:
        load_models_config(text)
    msg = str(info.value)
    assert "coder" in msg
    assert "null" in msg


def test_load_models_config_role_value_scalar_raises() -> None:
    text = textwrap.dedent(
        """\
        coder: "deepseek-v3"
        """
    )
    with pytest.raises(ConfigurationError) as info:
        load_models_config(text)
    assert "must be a mapping" in str(info.value)


def test_load_models_config_role_value_list_raises() -> None:
    text = textwrap.dedent(
        """\
        coder:
          - deepseek
          - kimi
        """
    )
    with pytest.raises(ConfigurationError) as info:
        load_models_config(text)
    assert "must be a mapping" in str(info.value)


# ----- chain-level validation surfaces from ChainConfig.validate ---


def test_load_models_config_propagates_empty_chain_error() -> None:
    text = textwrap.dedent(
        """\
        coder:
          model: "deepseek-v3"
          family: "deepseek"
          chain: []
        """
    )
    with pytest.raises(ConfigurationError) as info:
        load_models_config(text)
    assert "empty chain" in str(info.value)


def test_load_models_config_propagates_missing_api_key_env_error() -> None:
    text = textwrap.dedent(
        """\
        coder:
          model: "deepseek-v3"
          family: "deepseek"
          chain:
            - provider: openrouter
              slug:     "deepseek/deepseek-chat-v3"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
        """
    )
    # env intentionally empty so ``api_key_env`` lookup fails.
    with pytest.raises(ConfigurationError) as info:
        load_models_config(text, env={})
    assert "OPENROUTER_API_KEY" in str(info.value)


def test_load_models_config_propagates_unknown_provider_error() -> None:
    text = textwrap.dedent(
        """\
        coder:
          model: "deepseek-v3"
          family: "deepseek"
          chain:
            - provider: not_a_real_provider
              slug:     "deepseek-v3"
              base_url: "https://example.com/v1"
              api_key_env: SOME_KEY
        """
    )
    with pytest.raises(ConfigurationError) as info:
        load_models_config(text, env=_env_with_keys("SOME_KEY"))
    assert "unknown provider" in str(info.value)


def test_load_models_config_accumulates_warnings_from_chain_validator() -> None:
    # Slug whose extracted family disagrees with the role's declared
    # family — the chain validator emits a WARNING (not error). The
    # loader must surface it via ``ModelsConfig.warnings``.
    text = textwrap.dedent(
        """\
        coder:
          model:  "deepseek-v3"
          family: "qwen"
          chain:
            - provider: openrouter
              slug:     "deepseek/deepseek-chat-v3"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
        """
    )
    config = load_models_config(text, env=_env_with_keys("OPENROUTER_API_KEY"))
    assert config.roles["coder"].family == "qwen"
    assert any("slug family 'deepseek' != role family 'qwen'" in w for w in config.warnings)


# ----- Family-disjoint enforcement -------------------------------


def _make_three_role_text(*, planner_family: str, coder_family: str, eval_family: str) -> str:
    # Tiny helper that emits a syntactically-clean three-role YAML
    # body parameterised by the families under test. ``model`` and
    # ``slug`` are deliberately neutral so the chain validator's
    # slug-family heuristic does not fire on top of the eval-vs-actor
    # disjointness path we're exercising.
    return textwrap.dedent(
        f"""\
        planner:
          model:  "synthetic-planner"
          family: "{planner_family}"
          chain:
            - provider: openrouter
              slug:     "{planner_family}-planner"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
        coder:
          model:  "synthetic-coder"
          family: "{coder_family}"
          chain:
            - provider: openrouter
              slug:     "{coder_family}-coder"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
        eval:
          model:  "synthetic-eval"
          family: "{eval_family}"
          chain:
            - provider: openrouter
              slug:     "{eval_family}-eval"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
        """
    )


def test_load_models_config_rejects_eval_family_matching_planner() -> None:
    text = _make_three_role_text(planner_family="kimi", coder_family="deepseek", eval_family="kimi")
    with pytest.raises(EvalFamilyConflictError) as info:
        load_models_config(text, env=_env_with_keys("OPENROUTER_API_KEY"))
    msg = str(info.value)
    assert "planner" in msg
    assert "kimi" in msg


def test_load_models_config_rejects_eval_family_matching_coder() -> None:
    text = _make_three_role_text(
        planner_family="kimi", coder_family="deepseek", eval_family="deepseek"
    )
    with pytest.raises(EvalFamilyConflictError) as info:
        load_models_config(text, env=_env_with_keys("OPENROUTER_API_KEY"))
    msg = str(info.value)
    assert "coder" in msg
    assert "deepseek" in msg


def test_load_models_config_allows_planner_and_coder_same_family() -> None:
    # ADR-2 §Decision routing table allows a single «coder-tier»
    # model to back both planner and coder; only eval-vs-actor
    # disjointness is enforced.
    text = _make_three_role_text(
        planner_family="deepseek", coder_family="deepseek", eval_family="qwen"
    )
    config = load_models_config(text, env=_env_with_keys("OPENROUTER_API_KEY"))
    assert config.roles["planner"].family == "deepseek"
    assert config.roles["coder"].family == "deepseek"
    assert config.roles["eval"].family == "qwen"


def test_load_models_config_skips_family_check_when_eval_missing() -> None:
    # Two-role config: family check is a no-op. The collision
    # ``planner=coder=kimi`` is legal in isolation; we just verify
    # the loader does not synthesise an eval role to compare against.
    text = textwrap.dedent(
        """\
        planner:
          model:  "kimi-k2"
          family: "kimi"
          chain:
            - provider: openrouter
              slug:     "moonshotai/kimi-k2"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
        coder:
          model:  "kimi-k2-coder"
          family: "kimi"
          chain:
            - provider: openrouter
              slug:     "moonshotai/kimi-k2"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
        """
    )
    config = load_models_config(text, env=_env_with_keys("OPENROUTER_API_KEY"))
    assert set(config.roles) == {"planner", "coder"}


def test_load_models_config_skips_family_check_when_planner_missing() -> None:
    # eval+coder is also a legal two-role shape; no check fires.
    text = textwrap.dedent(
        """\
        coder:
          model:  "kimi-k2"
          family: "kimi"
          chain:
            - provider: openrouter
              slug:     "moonshotai/kimi-k2"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
        eval:
          model:  "kimi-k2-eval"
          family: "kimi"
          chain:
            - provider: openrouter
              slug:     "moonshotai/kimi-k2"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
        """
    )
    config = load_models_config(text, env=_env_with_keys("OPENROUTER_API_KEY"))
    assert set(config.roles) == {"coder", "eval"}


def test_load_models_config_accepts_debug_role_alongside_three() -> None:
    # ADR-2 §Decision recognises four roles (planner / coder /
    # debug / eval). The loader must accept arbitrary role names
    # without altering the family-disjoint check, which only
    # constrains the planner/coder/eval triad.
    text = _make_three_role_text(
        planner_family="kimi", coder_family="deepseek", eval_family="qwen"
    ) + textwrap.dedent(
        """\
        debug:
          model:  "claude-3-5-sonnet"
          family: "anthropic"
          chain:
            - provider: anthropic
              slug:     "claude-3-5-sonnet-20240620"
              base_url: "https://api.anthropic.com"
              api_key_env: ANTHROPIC_API_KEY
        """
    )
    env = _env_with_keys("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY")
    config = load_models_config(text, env=env)
    assert set(config.roles) == {"planner", "coder", "eval", "debug"}
    assert config.roles["debug"].family == "anthropic"


# ----- Path-based variant ----------------------------------------


def test_load_models_config_from_path_reads_file(tmp_path: Path) -> None:
    path = tmp_path / "models.yaml"
    path.write_text(
        textwrap.dedent(
            """\
            coder:
              model:  "deepseek-v3"
              family: "deepseek"
              chain:
                - provider: openrouter
                  slug:     "deepseek/deepseek-chat-v3"
                  base_url: "https://openrouter.ai/api/v1"
                  api_key_env: OPENROUTER_API_KEY
            """
        ),
        encoding="utf-8",
    )
    env = _env_with_keys("OPENROUTER_API_KEY")
    config = load_models_config_from_path(path, env=env)
    assert config.roles["coder"].model == "deepseek-v3"


def test_load_models_config_from_path_missing_file_returns_empty(tmp_path: Path) -> None:
    # Match the deny-by-default policy that ``fa.config`` uses for
    # ``~/.fa/config.yaml``: missing file is a legal state, caller
    # decides whether to warn.
    missing = tmp_path / "does-not-exist.yaml"
    config = load_models_config_from_path(missing)
    assert config == ModelsConfig(roles={})


def test_default_models_yaml_path_points_at_user_home() -> None:
    # The default path must resolve under the user's home dir per
    # ADR-9 §1 («Configuration in ``~/.fa/models.yaml``»). We do
    # not assert the file exists — the loader handles missing paths
    # gracefully — only the location.
    assert DEFAULT_MODELS_YAML_PATH == Path.home() / ".fa" / "models.yaml"
