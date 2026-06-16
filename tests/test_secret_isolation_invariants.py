"""Structural CI guards for the secret-isolation invariant (ADR-12).

These assert the *deployment* surface keeps keys out of the agent's reach, so a
future refactor that re-introduces a leak (e.g. injecting keys as container env,
or dropping the bash env-scrub) fails CI rather than silently regressing.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_COMPOSE = _ROOT / "docker-compose.fa.yml"
_RUN_BASH = _ROOT / "src" / "fa" / "inner_loop" / "tools" / "run_bash.py"
_CLI = _ROOT / "src" / "fa" / "cli.py"


def test_compose_mounts_secrets_readonly_outside_workspace() -> None:
    text = _COMPOSE.read_text(encoding="utf-8")
    # API keys mounted read-only at /run/secrets/fa.env (outside /workspace).
    assert "/run/secrets/fa.env" in text
    assert "FA_SECRETS_FILE=/run/secrets/fa.env" in text


def test_compose_does_not_inject_api_keys_as_container_env() -> None:
    """env_file may carry FA_* controls, but NOT API keys.

    We can't see operator key values here, but we assert the mount-based path
    exists and FA_SECRETS_FILE is a PATH (not a key value).
    """
    text = _COMPOSE.read_text(encoding="utf-8")
    # The secrets mount is the key-delivery mechanism, not env injection.
    assert "source: /srv/first-agent/secrets/fa.env" in text
    assert "target: /run/secrets/fa.env" in text


def test_run_bash_passes_scrubbed_env() -> None:
    text = _RUN_BASH.read_text(encoding="utf-8")
    # subprocess must receive an explicit scrubbed env, never inherit implicitly.
    assert "build_scrubbed_env(os.environ" in text
    assert "env=build_scrubbed_env" in text


def test_cli_reads_keys_from_store_not_environ() -> None:
    text = _CLI.read_text(encoding="utf-8")
    # The key-read sites must use the private store, not os.environ.
    assert "load_models_config_from_path(" in text
    assert "config_path, env=secrets" in text
    assert "SecretRedactor.from_models_config(" in text
    assert "secrets=secrets" in text
    # The old import-time os.environ mutation must be gone (function deleted).
    assert "_load_fa_dotenv" not in text


def test_cli_supports_egress_proxy_mode() -> None:
    text = _CLI.read_text(encoding="utf-8")
    # Proxy mode: provider keys live in the proxy, not this process.
    assert "FA_EGRESS_PROXY_URL" in text
    assert "_apply_proxy_mode" in text
    # In proxy mode the chain's key store is empty (no provider keys on fa side).
    assert "SecretStore({}) if proxy_mode" in text
