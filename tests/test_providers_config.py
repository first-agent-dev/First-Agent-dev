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
              transport_retries: 2
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
    assert entry.transport_retries == 2
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


def test_load_models_config_normalises_family_case_for_disjoint_check() -> None:
    # Regression test for the Agent Review finding on PR #52: a YAML
    # ``family: "DeepSeek"`` (mixed case) on planner and
    # ``family: "deepseek"`` (lowercase) on eval would silently bypass
    # ``check_eval_disjoint`` because ``ChainConfig.family`` stores the
    # raw YAML string verbatim and the disjoint check does a
    # case-sensitive ``==`` comparison. The loader must
    # ``.strip().lower()`` before calling ``check_eval_disjoint`` so
    # the safety-critical rule from ADR-2 §Amendment 2026-05-20
    # cannot be bypassed by a casing typo.
    text = textwrap.dedent(
        """\
        planner:
          model:  "deepseek-v3"
          family: "DeepSeek"
          chain:
            - provider: openrouter
              slug:     "deepseek-planner"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
        coder:
          model:  "kimi-k2"
          family: "kimi"
          chain:
            - provider: openrouter
              slug:     "kimi-coder"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
        eval:
          model:  "deepseek-v3-eval"
          family: "deepseek"
          chain:
            - provider: openrouter
              slug:     "deepseek-eval"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
        """
    )
    with pytest.raises(EvalFamilyConflictError) as info:
        load_models_config(text, env=_env_with_keys("OPENROUTER_API_KEY"))
    msg = str(info.value)
    assert "planner" in msg
    # The error must surface the conflict even though the raw YAML
    # families differ in case. The normalised value (lowercase)
    # appears in the error message because the loader passes the
    # lowercased forms to ``check_eval_disjoint``.
    assert "deepseek" in msg


def test_load_models_config_normalises_whitespace_for_disjoint_check() -> None:
    # Same regression contract as the case test, but for whitespace
    # padding (``family: "  deepseek  "``). The loader's
    # ``.strip().lower()`` covers both axes; this test pins the strip
    # behaviour so a future refactor cannot regress only the case
    # half.
    text = textwrap.dedent(
        """\
        planner:
          model:  "deepseek-v3"
          family: "  deepseek  "
          chain:
            - provider: openrouter
              slug:     "deepseek-planner"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
        coder:
          model:  "kimi-k2"
          family: "kimi"
          chain:
            - provider: openrouter
              slug:     "kimi-coder"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
        eval:
          model:  "deepseek-v3-eval"
          family: "deepseek"
          chain:
            - provider: openrouter
              slug:     "deepseek-eval"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
        """
    )
    with pytest.raises(EvalFamilyConflictError):
        load_models_config(text, env=_env_with_keys("OPENROUTER_API_KEY"))


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
    # Two-role config: hard family check is a no-op when ``eval`` is
    # absent — the rule is eval-anchored, nothing to be disjoint from.
    # ``planner=coder=kimi`` is legal in isolation; we just verify the
    # loader does not synthesise an eval role to compare against AND
    # does not emit a partial-config WARNING (no ``eval`` declared →
    # ``_partial_disjoint_warning`` returns ``None``).
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
    # Eval is absent → no partial-disjoint warning.
    for warning in config.warnings:
        assert "family-disjoint" not in warning.lower()


def test_load_models_config_skips_family_check_when_planner_missing() -> None:
    # eval+coder is a legal two-role shape; the loader's HARD gate
    # does not fire (planner missing) — but ADR-2 §Amendment 2026-05-20
    # rule 1 («eval disjoint from planner AND coder») still applies
    # pairwise to the declared actor. The loader surfaces this gap by
    # appending a partial-config WARNING to ``ModelsConfig.warnings``
    # (PR-#13 follow-up «F1»). Hard enforcement is intentionally
    # deferred to the caller — see :func:`_partial_disjoint_warning`
    # docstring for the rationale.
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
    # Partial-config warning is present and names both the declared
    # actor and the missing one (see dedicated content-shape test
    # below for the full assertion shape).
    partial_warnings = [w for w in config.warnings if "'eval'" in w and "'coder'" in w]
    assert len(partial_warnings) == 1, (
        f"expected exactly one partial-disjoint warning naming "
        f"eval+coder; got warnings={config.warnings!r}"
    )


# ----- Partial-config disjoint warning (PR-#13 follow-up «F1») -----
#
# The hard ``check_eval_disjoint`` gate at the loader's call site
# fires only when all three of planner / coder / eval are declared.
# When ``eval`` is declared alongside *exactly one* actor (planner
# XOR coder), the rule «eval-vs-<that-actor> disjoint» from ADR-2
# §Amendment 2026-05-20 rule 1 still applies pairwise — but the
# loader's hard gate is silent. The loader surfaces this gap via
# ``ModelsConfig.warnings`` so the caller (inner-loop runtime) can
# log it. The five tests below pin every shape the helper recognises.


def _make_two_role_text(*, role_a: str, family_a: str, role_b: str, family_b: str) -> str:
    """Build a minimal two-role YAML for partial-config WARNING tests."""

    return textwrap.dedent(
        f"""\
        {role_a}:
          model:  "synthetic-{role_a}"
          family: "{family_a}"
          chain:
            - provider: openrouter
              slug:     "{family_a}-{role_a}"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
        {role_b}:
          model:  "synthetic-{role_b}"
          family: "{family_b}"
          chain:
            - provider: openrouter
              slug:     "{family_b}-{role_b}"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
        """
    )


def test_load_models_config_warns_on_partial_disjoint_coder_plus_eval() -> None:
    # Bot's exact case: 2-role config (coder + eval) where same family
    # would silently pass the hard gate today. Loader emits a WARNING
    # that names eval, names the declared actor (coder), and names the
    # missing actor (planner) so the caller knows which pairwise
    # check is un-enforced.
    text = _make_two_role_text(role_a="coder", family_a="kimi", role_b="eval", family_b="kimi")
    config = load_models_config(text, env=_env_with_keys("OPENROUTER_API_KEY"))
    partial = [w for w in config.warnings if "'eval'" in w and "'coder'" in w]
    assert len(partial) == 1
    warning = partial[0]
    assert "'planner'" in warning
    assert "ADR-2" in warning
    assert "eval-vs-coder" in warning


def test_load_models_config_warns_on_partial_disjoint_planner_plus_eval() -> None:
    # Mirror case: 2-role config (planner + eval). Loader emits a
    # WARNING naming eval, planner (declared actor), and coder
    # (missing actor).
    text = _make_two_role_text(role_a="planner", family_a="kimi", role_b="eval", family_b="kimi")
    config = load_models_config(text, env=_env_with_keys("OPENROUTER_API_KEY"))
    partial = [w for w in config.warnings if "'eval'" in w and "'planner'" in w]
    assert len(partial) == 1
    warning = partial[0]
    assert "'coder'" in warning
    assert "ADR-2" in warning
    assert "eval-vs-planner" in warning


def test_load_models_config_no_partial_warning_when_all_three_declared() -> None:
    # Full config: the HARD ``check_eval_disjoint`` call site fires
    # (or returns cleanly when families are disjoint). The partial-
    # config WARNING is suppressed because the gap it surfaces does
    # not apply — there is no un-checked pairwise rule.
    text = _make_three_role_text(planner_family="kimi", coder_family="deepseek", eval_family="qwen")
    config = load_models_config(text, env=_env_with_keys("OPENROUTER_API_KEY"))
    for warning in config.warnings:
        assert "loader's hard family-disjoint gate" not in warning, (
            f"unexpected partial-config warning on full 3-role config: {warning!r}"
        )


def test_load_models_config_no_partial_warning_when_eval_alone() -> None:
    # Eval-only config: no actor declared, so the pairwise rule is
    # vacuously satisfied (nothing to be disjoint from). The helper
    # returns ``None`` for this shape; no warning is appended.
    text = textwrap.dedent(
        """\
        eval:
          model:  "qwen-3-32b"
          family: "qwen"
          chain:
            - provider: openrouter
              slug:     "qwen/qwen-3-32b"
              base_url: "https://openrouter.ai/api/v1"
              api_key_env: OPENROUTER_API_KEY
        """
    )
    config = load_models_config(text, env=_env_with_keys("OPENROUTER_API_KEY"))
    for warning in config.warnings:
        assert "loader's hard family-disjoint gate" not in warning, (
            f"unexpected partial-config warning on eval-only config: {warning!r}"
        )


def test_load_models_config_no_partial_warning_when_no_eval_declared() -> None:
    # Planner+coder, no eval: the rule is eval-anchored, so absence
    # of eval means absence of the rule. The helper returns ``None``;
    # no warning is appended. Re-asserts the same negative case the
    # eval-missing skip test above covers, framed from the
    # warning-helper's point of view.
    text = _make_two_role_text(role_a="planner", family_a="kimi", role_b="coder", family_b="kimi")
    config = load_models_config(text, env=_env_with_keys("OPENROUTER_API_KEY"))
    for warning in config.warnings:
        assert "loader's hard family-disjoint gate" not in warning, (
            f"unexpected partial-config warning on planner+coder (no eval) config: {warning!r}"
        )


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
