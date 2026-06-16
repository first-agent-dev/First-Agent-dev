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


def test_compose_agent_container_has_no_llm_key_mount() -> None:
    """ADR-12 Option C: the AGENT container must NOT mount the LLM keys file
    and must NOT carry FA_SECRETS_FILE — keys live only in the proxy."""
    import yaml

    doc = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    agent = doc["services"]["first-agent"]
    # No /run/secrets/fa.env mount on the agent.
    for vol in agent.get("volumes", []):
        if isinstance(vol, dict):
            assert vol.get("target") != "/run/secrets/fa.env", (
                "agent container must not mount the LLM keys file"
            )
    # No FA_SECRETS_FILE env on the agent.
    env = agent.get("environment", [])
    assert not any(str(e).startswith("FA_SECRETS_FILE") for e in env)
    # Agent targets the proxy instead.
    assert any("FA_EGRESS_PROXY_URL=" in str(e) for e in env)


def test_compose_proxy_service_holds_the_keys_and_no_workspace() -> None:
    """The egress-proxy service mounts the keys ro and has NO agent /workspace
    write mount (it is the boundary, not an agent)."""
    import yaml

    doc = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    assert "fa-egress-proxy" in doc["services"], "proxy service must exist"
    proxy = doc["services"]["fa-egress-proxy"]
    targets = {
        v.get("target"): v for v in proxy.get("volumes", []) if isinstance(v, dict)
    }
    assert "/run/secrets/fa.env" in targets, "proxy must mount the LLM keys"
    assert targets["/run/secrets/fa.env"].get("read_only") is True
    # If the proxy mounts /workspace at all, it must be read-only (no agent rw).
    if "/workspace" in targets:
        assert targets["/workspace"].get("read_only") is True
    # The agent depends on the proxy being healthy.
    assert doc["services"]["first-agent"]["depends_on"]["fa-egress-proxy"][
        "condition"
    ] == "service_healthy"


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
