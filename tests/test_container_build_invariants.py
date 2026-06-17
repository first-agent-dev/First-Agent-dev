"""Structural guards for the container build/run surface.

These lock in the fixes from the container-build closeout review so a future edit
cannot silently re-introduce a deploy-breaking regression (HOME, uid mismatch,
world-readable interpreter, crash-loop restart, SSH hang, capability over-grant).
They parse the files as text/YAML — no Docker required — so they run anywhere.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_DOCKERFILE = _ROOT / "Dockerfile.fa"
_COMPOSE = _ROOT / "docker-compose.fa.yml"
_SETUP = _ROOT / "scripts" / "setup-fa-desktop.sh"


def _compose() -> dict:
    return yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))


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
    assert not any(
        str(e).startswith("PYTHONPATH=") for e in agent.get("environment", [])
    ), "drop PYTHONPATH from compose; the entrypoint sets it"


# --- setup script ---------------------------------------------------------
def test_setup_chowns_state_to_container_uid() -> None:
    """B3: bind-mounted state/secrets must be owned by the container's uid (1000),
    not the host username (which may be a different uid)."""
    text = _SETUP.read_text(encoding="utf-8")
    assert "chown -R 1000:1000" in text, (
        "setup must chown FA_DIR to numeric 1000:1000 to match the container uid"
    )
