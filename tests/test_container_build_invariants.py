"""Structural guards for the container build/run surface.

These lock in the fixes from the container-build closeout review so a future edit
cannot silently re-introduce a deploy-breaking regression (HOME, uid mismatch,
world-readable interpreter, crash-loop restart, SSH hang, capability over-grant).
They parse the files as text/YAML — no Docker required — so they run anywhere.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_DOCKERFILE = _ROOT / "Dockerfile.fa"
_COMPOSE = _ROOT / "docker-compose.fa.yml"
_SETUP = _ROOT / "scripts" / "setup-fa-desktop.sh"
_POST_SETUP = _ROOT / "scripts" / "fa-post-setup.sh"
_CLEAN_REBUILD = _ROOT / "scripts" / "fa-clean-rebuild.sh"
_UPDATE = _ROOT / "scripts" / "fa-update.sh"


def _compose() -> dict[str, Any]:
    result: dict[str, Any] = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    return result


# --- Dockerfile -----------------------------------------------------------
def test_home_is_pinned_for_numeric_user() -> None:
    """B1: compose runs the container as numeric 1000:1000, for which Docker may
    not derive HOME. The image must pin HOME so Path.home() resolves correctly."""
    text = _DOCKERFILE.read_text(encoding="utf-8")
    assert "ENV HOME=/home/fa" in text, "Dockerfile must pin HOME=/home/fa"


def test_home_is_set_after_build_time_tools() -> None:
    """Regression: `ENV HOME=/home/fa` must come AFTER the uv installer RUN.

    The uv install.sh honors $HOME; if HOME is pinned to /home/fa before that
    step (which runs as root), uv installs to /home/fa/.local and the build
    breaks. HOME must be set only once all root build steps have run."""
    text = _DOCKERFILE.read_text(encoding="utf-8")
    home_pos = text.index("ENV HOME=/home/fa")
    uv_install_pos = text.index("astral.sh/uv/install.sh")
    assert home_pos > uv_install_pos, (
        "ENV HOME must be placed AFTER the uv installer (and other root build "
        "steps), otherwise it perturbs build-time tools that key off $HOME"
    )


def test_uv_install_does_not_depend_on_home() -> None:
    """Regression: install uv via UV_INSTALL_DIR, not `mv /root/.local/bin/...`
    (which breaks the moment HOME is changed)."""
    text = _DOCKERFILE.read_text(encoding="utf-8")
    assert "UV_INSTALL_DIR=/usr/local/bin" in text
    assert "/root/.local/bin/uv" not in text, (
        "do not mv uv from /root/.local; use UV_INSTALL_DIR (HOME-independent)"
    )


def test_dockerfile_uses_retrying_downloads_for_apt_and_uv() -> None:
    """Clean AIO rebuilds must tolerate transient apt/installer network failures."""
    text = _DOCKERFILE.read_text(encoding="utf-8")
    assert "Acquire::Retries" in text
    assert 'SHELL ["/bin/bash", "-o", "pipefail", "-c"]' in text
    assert "--retry 5" in text
    assert "--retry-all-errors" in text
    assert "/tmp/uv-install.sh" in text
    assert "| env UV_INSTALL_DIR=/usr/local/bin" not in text


def test_runtime_image_installs_just_from_apt_not_github_releases() -> None:
    """Keep just, but do not fetch it from just.systems/GitHub Releases."""
    text = _DOCKERFILE.read_text(encoding="utf-8")
    assert "just.systems/install.sh" not in text
    assert "casey/just/releases" not in text
    assert re.search(r"apt-get install[\s\S]*\bjust\b", text)
    assert "just --version" in text


def test_dockerfile_does_not_set_workspace_pythonpath_globally() -> None:
    """Only the entrypoint may add /workspace/src, and only when it exists."""
    text = _DOCKERFILE.read_text(encoding="utf-8")
    assert "ENV PYTHONPATH=/workspace/src" not in text


def test_python_installed_in_world_readable_location() -> None:
    """B2: the uv-managed interpreter must NOT live under root-only /root/.local;
    install it to a shared dir and make it world-traversable/executable."""
    text = _DOCKERFILE.read_text(encoding="utf-8")
    assert "UV_PYTHON_INSTALL_DIR=/opt/uv-python" in text
    assert "chmod -R a+rX /opt/uv-python" in text
    assert "chmod -R a+rX /opt/fa-venv" in text


# --- docker-compose -------------------------------------------------------
def test_git_ssh_command_is_non_interactive() -> None:
    """B5: headless container — ssh must not fall back to an interactive prompt
    that hangs git push/fetch on a host-key change."""
    agent = _compose()["services"]["first-agent"]
    git_ssh = next(
        (e for e in agent["environment"] if str(e).startswith("GIT_SSH_COMMAND")),
        "",
    )
    assert "BatchMode=yes" in git_ssh
    assert "StrictHostKeyChecking=accept-new" in git_ssh


def test_agent_has_no_runtime_capabilities() -> None:
    """B6: the non-root agent needs no added Linux capabilities at runtime."""
    agent = _compose()["services"]["first-agent"]
    assert agent.get("cap_drop") == ["ALL"]
    assert not agent.get("cap_add"), "agent must not add runtime capabilities"


def test_proxy_self_heals_on_a_247_box() -> None:
    """R2-4: now that the startup-crash bug (image perms/HOME) is fixed, a
    correctly-built proxy won't crash-loop, and `unless-stopped` is the right
    unattended policy — it self-heals transient faults (slow boot, brief config
    edit) instead of staying permanently dead after N failures. The healthcheck
    still surfaces `unhealthy` if it genuinely can't serve."""
    proxy = _compose()["services"]["fa-egress-proxy"]
    assert proxy.get("restart") == "unless-stopped"


def test_no_duplicate_pythonpath_on_agent() -> None:
    """B7: PYTHONPATH is owned by the entrypoint; setting it in compose too
    produces /workspace/src:/workspace/src."""
    agent = _compose()["services"]["first-agent"]
    assert not any(str(e).startswith("PYTHONPATH=") for e in agent.get("environment", [])), (
        "drop PYTHONPATH from compose; the entrypoint sets it"
    )


# --- setup script ---------------------------------------------------------


def test_setup_seeds_provider_secrets_from_fa_env_template() -> None:
    """secrets/fa.env must be seeded from the provider-key template, not .env.fa."""
    text = _SETUP.read_text(encoding="utf-8")
    assert "knowledge/templates/fa.env.template" in text
    assert not re.search(
        r"^\s*TEMPLATE=\"\$FA_DIR/repo/First-Agent-dev/\.env\.fa\.template\"",
        text,
        re.MULTILINE,
    )
    assert "fa-normalize-env.sh" in text
    assert "Migrating API keys from repo .env.fa" not in text


def test_post_setup_checks_changeme_only_on_active_secret_lines() -> None:
    text = _POST_SETUP.read_text(encoding="utf-8")
    assert "grep -qiE" in text
    assert "^[[:space:]]*[A-Z0-9_]+(API_KEY|_TOKEN|_SECRET)" in text
    assert "grep -qi 'CHANGEME'" not in text


def test_setup_chowns_state_to_container_uid() -> None:
    """B3: bind-mounted state/secrets must be owned by the container's uid (1000),
    not the host username (which may be a different uid)."""
    text = _SETUP.read_text(encoding="utf-8")
    assert "chown -R 1000:1000" in text, (
        "setup must chown FA_DIR to numeric 1000:1000 to match the container uid"
    )


def test_setup_normalizes_secret_ownership_after_creation() -> None:
    """A1: secret files are created AFTER the early global chown (and without
    sudo → operator-owned). There must be a final pass that re-chowns the secrets
    dir to uid 1000, otherwise the container can't read keys/token/deploy-key on
    a host whose operator uid != 1000."""
    text = _SETUP.read_text(encoding="utf-8")
    # The normalization chown must appear AFTER the deploy-key creation.
    chown_pos = text.rfind('chown -R 1000:1000 "$FA_DIR/secrets"')
    deploykey_pos = text.index("ssh-keygen -t ed25519 -f")
    assert chown_pos != -1, "setup must re-chown secrets/ to 1000 after creating them"
    assert chown_pos > deploykey_pos, (
        "the secret-ownership normalization must run AFTER the deploy key (and all "
        "other secret files) are created"
    )


def test_migration_backup_not_left_in_workspace() -> None:
    """A2: key-bearing .env.fa backups must live outside the agent workspace."""
    setup_text = _SETUP.read_text(encoding="utf-8")
    normalizer_text = (_ROOT / "scripts" / "fa-normalize-env.sh").read_text(encoding="utf-8")
    # The old in-workspace backup form must not return.
    assert 'cp "$ENV_FA" "$ENV_FA.pre-secret-migration.bak"' not in setup_text
    assert 'cp "$ENV_FA" "$ENV_FA.pre-secret-migration.bak"' not in normalizer_text
    # The normalizer backs up under BACKUP_DIR, which deploy callers set to
    # /srv/first-agent/secrets (host-only, not /workspace).
    assert 'BACKUP_DIR="${BACKUP_DIR:-/srv/first-agent/secrets}"' in normalizer_text
    assert ".env.fa.pre-adr12-normalize" in normalizer_text


# --- deploy scripts leave the stack UP + in stand-by --------------------------
def test_post_setup_does_not_teardown_to_hand_off_to_systemd() -> None:
    """fa-post-setup must NOT `docker compose down` and then rely on
    `systemctl --user start` (which silently no-ops without a user D-Bus/linger
    session) — that would leave the stack DOWN. Compose is the authoritative
    bring-up; systemd is only armed for reboot autostart."""
    text = _POST_SETUP.read_text(encoding="utf-8")
    assert "systemctl --user start fa.service" not in text, (
        "post-setup must not START via systemd (no-ops without a user session); "
        "use docker compose up -d"
    )
    assert "docker compose -f docker-compose.fa.yml up -d" in text, (
        "post-setup must bring the stack up via compose"
    )


def test_clean_rebuild_brings_up_via_compose_not_systemd_start() -> None:
    """fa-clean-rebuild must bring the stack up with `docker compose up -d`
    (authoritative), not `systemctl --user start` which can silently no-op."""
    text = _CLEAN_REBUILD.read_text(encoding="utf-8")
    assert 'docker compose -f "${COMPOSE_FILE}" up -d' in text
    # It may still `enable` for reboot, but must not depend on `start` to run.
    assert 'systemctl --user start "${SERVICE}"' not in text, (
        "clean-rebuild must not rely on systemctl start to run the stack"
    )


# --- unified routing file (ADR-12 Option C / R2-2) ----------------------------
def _volume_by_target(service: dict[str, Any], target: str) -> dict[str, Any]:
    return next(
        vol
        for vol in service.get("volumes", [])
        if isinstance(vol, dict) and vol.get("target") == target
    )


def test_compose_uses_single_routing_source_for_agent_and_proxy() -> None:
    """Both containers read the same routing file read-only; no copy exists."""
    doc = _compose()
    agent = doc["services"]["first-agent"]
    proxy = doc["services"]["fa-egress-proxy"]
    agent_routing = _volume_by_target(agent, "/home/fa/.fa/models.yaml")
    proxy_routing = _volume_by_target(proxy, "/etc/fa/models.yaml")

    assert agent_routing.get("source") == proxy_routing.get("source")
    assert agent_routing.get("source") == "/srv/first-agent/routing/models.yaml"
    assert agent_routing.get("read_only") is True
    assert proxy_routing.get("read_only") is True


def test_routing_source_is_not_agent_writable_state_or_legacy_proxy_copy() -> None:
    """Active compose mounts must not use the old split-brain files."""
    forbidden = {
        "/srv/first-agent/state/models.yaml",
        "/srv/first-agent/proxy/models.yaml",
    }
    for service in _compose()["services"].values():
        for vol in service.get("volumes", []):
            if isinstance(vol, dict):
                assert vol.get("source") not in forbidden


def test_agent_routing_file_mount_order() -> None:
    """Nested ro routing file mount must come after the rw state dir mount."""
    agent = _compose()["services"]["first-agent"]
    vols = agent.get("volumes", [])
    state_idx = next(
        i
        for i, vol in enumerate(vols)
        if isinstance(vol, dict) and vol.get("target") == "/home/fa/.fa"
    )
    routing_idx = next(
        i
        for i, vol in enumerate(vols)
        if isinstance(vol, dict) and vol.get("target") == "/home/fa/.fa/models.yaml"
    )
    assert routing_idx > state_idx


def test_fa_update_hash_tracks_routing_file_not_proxy_copy() -> None:
    text = _UPDATE.read_text(encoding="utf-8")
    assert 'MODELS_YAML_FILE="${MODELS_YAML_FILE:-/srv/first-agent/routing/models.yaml}"' in text
    assert '"${MODELS_YAML_FILE}"' in text
    assert "PROXY_MODELS_FILE" not in text
    assert 'cp "${MODELS_YAML_FILE}"' not in text


def test_deploy_scripts_do_not_sync_proxy_models_copy() -> None:
    """Legacy proxy/models.yaml may be read for migration, never maintained."""
    for script in (_UPDATE, _POST_SETUP, _CLEAN_REBUILD):
        text = script.read_text(encoding="utf-8")
        assert "PROXY_MODELS_FILE" not in text
        assert 'cp "${MODELS_YAML_FILE}" "${PROXY_MODELS_FILE}"' not in text
        assert "Syncing proxy routing config" not in text


def test_fa_update_reexecs_after_git_pull_to_use_new_deploy_logic() -> None:
    """Updating deploy code and compose in one pull must run the updated script.

    Without a re-exec, the old in-memory fa-update.sh can pull a compose file
    that expects new host paths (for example routing/models.yaml) but keep using
    stale deploy logic that never creates them.
    """
    text = _UPDATE.read_text(encoding="utf-8")
    assert "_FA_UPDATE_REEXEC" in text
    assert 'exec bash "${REPO_DIR}/scripts/fa-update.sh" "$@"' in text
    assert "_FA_UPDATE_REEXEC_HEAD_CHANGED" in text


def test_clean_rebuild_wipe_state_ignores_legacy_models_when_recreating_routing() -> None:
    """WIPE_STATE=1 must reset routing, not migrate a stale legacy proxy copy."""
    text = _CLEAN_REBUILD.read_text(encoding="utf-8")
    assert 'LEGACY_STATE_MODELS=""' in text
    assert 'LEGACY_PROXY_MODELS=""' in text


def test_clean_rebuild_no_cache_and_progress_are_configurable() -> None:
    text = _CLEAN_REBUILD.read_text(encoding="utf-8")
    assert 'NO_CACHE="${NO_CACHE:-1}"' in text
    assert 'COMPOSE_BUILD_PULL="${COMPOSE_BUILD_PULL:-1}"' in text
    assert 'BUILD_PROGRESS="${BUILD_PROGRESS:-auto}"' in text
    assert "build_cmd+=(--no-cache)" in text
    assert 'build_cmd+=(--progress "${BUILD_PROGRESS}")' in text


def test_update_and_clean_rebuild_stash_failures_are_not_ignored() -> None:
    for script in (_UPDATE, _CLEAN_REBUILD):
        text = script.read_text(encoding="utf-8")
        push_idx = text.index("git stash push")
        fetch_idx = text.index("git fetch")
        assert "|| true" not in text[push_idx:fetch_idx]
        assert "git stash pop" in text
        assert "STASHED=0" in text


def test_clean_rebuild_guards_destructive_fa_dir_override() -> None:
    text = _CLEAN_REBUILD.read_text(encoding="utf-8")
    assert "assert_safe_fa_dir" in text
    assert "ALLOW_NONSTANDARD_FA_DIR" in text
    assert 'normalized_fa_dir="${FA_DIR%/}"' in text


def test_post_setup_validates_the_real_keys_file() -> None:
    """F1: the 'did you add keys' gate must check the secrets file the proxy
    actually reads (secrets/fa.env), not .env.fa (which holds non-secret FA_*)."""
    text = _POST_SETUP.read_text(encoding="utf-8")
    assert "/srv/first-agent/secrets/fa.env" in text, (
        "post-setup must validate the real LLM-keys file (secrets/fa.env)"
    )
    assert "nano " not in text, "use micro, not nano (repo standard)"
