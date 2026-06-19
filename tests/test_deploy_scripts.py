"""Drift guard for the host-side deployment / administration shell scripts.

Mirrors ``tests/test_fa_update_script.py`` but covers the whole deployment
script surface so that future edits cannot silently introduce a syntax error,
re-duplicate the heredocs we removed, or break the bootstrap contract.

These tests are deliberately cheap (static checks: ``bash -n`` + ``shellcheck``
when available + simple substring assertions); they do not spin up Docker.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"

# Host-side shell scripts that operators run directly or that ship in the image.
_SHELL_SCRIPTS = [
    _SCRIPTS / "setup-fa-desktop.sh",
    _SCRIPTS / "fa-post-setup.sh",
    _SCRIPTS / "fa-update.sh",
    _SCRIPTS / "fa-clean-rebuild.sh",
    _SCRIPTS / "backup-fa.sh",
    _SCRIPTS / "fa-normalize-env.sh",
    _SCRIPTS / "fa-entrypoint.sh",
    _SCRIPTS / "ssh-tailscale" / "00-failsafe.sh",
    _SCRIPTS / "ssh-tailscale" / "10-diagnose.sh",
    _SCRIPTS / "ssh-tailscale" / "20-harden.sh",
    _SCRIPTS / "ssh-tailscale" / "30-verify.sh",
]


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
@pytest.mark.parametrize("script", _SHELL_SCRIPTS, ids=lambda p: p.name)
def test_shell_script_has_valid_syntax(script: Path) -> None:
    assert script.is_file(), f"missing script: {script}"
    subprocess.run(["bash", "-n", str(script)], check=True)


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck not installed")
@pytest.mark.parametrize("script", _SHELL_SCRIPTS, ids=lambda p: p.name)
def test_shell_script_passes_shellcheck(script: Path) -> None:
    # -S warning: ignore purely stylistic INFO/STYLE notes.
    result = subprocess.run(
        ["shellcheck", "-S", "warning", str(script)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_executable_script_modes_are_pinned() -> None:
    """Scripts invoked directly by operators/git must keep executable mode."""
    expected_exec = [
        _SCRIPTS / "fa-update.sh",
        _SCRIPTS / "fa-clean-rebuild.sh",
        _SCRIPTS / "fa-post-setup.sh",
        _SCRIPTS / "ssh-tailscale" / "00-failsafe.sh",
        _SCRIPTS / "ssh-tailscale" / "10-diagnose.sh",
        _SCRIPTS / "ssh-tailscale" / "20-harden.sh",
        _SCRIPTS / "ssh-tailscale" / "30-verify.sh",
        _SCRIPTS.parent / "src" / "fa" / "hygiene" / "hooks" / "commit-msg",
        _SCRIPTS.parent / "src" / "fa" / "hygiene" / "hooks" / "prepare-commit-msg",
    ]
    for path in expected_exec:
        assert path.stat().st_mode & stat.S_IXUSR, f"missing executable bit: {path}"


def test_bootstrap_script_is_self_contained() -> None:
    """setup-fa-desktop.sh must NOT source a sibling file.

    knowledge/instructions/01-install.md Phase 4 Option B documents downloading *only* this
    file to /tmp and running it; the repo is cloned later, by the script itself.
    A `source ./lib/...` at startup would die before the clone exists. This test
    pins that contract so the DRY refactor that broke it cannot return.
    """
    text = (_SCRIPTS / "setup-fa-desktop.sh").read_text(encoding="utf-8")
    # No `source`/`.` of a path relative to the script's own directory.
    assert "SCRIPT_DIR" not in text, "bootstrap must not resolve its own dir to source helpers"
    assert not re.search(r"^\s*(\.|source)\s+\S*lib/", text, re.MULTILINE), (
        "bootstrap must not source a helper library — it runs before the repo is cloned"
    )


def test_setup_installs_fa_service_from_cloned_repo_not_script_dir() -> None:
    """fa.service is installed from the clone path, which exists in both run modes."""
    text = (_SCRIPTS / "setup-fa-desktop.sh").read_text(encoding="utf-8")
    # Reads the template from the cloned repo (works standalone AND from-repo).
    assert "repo/First-Agent-dev/scripts/fa.service" in text


def test_setup_script_has_no_inline_duplicates() -> None:
    """Guard the de-duplication: no inline systemd unit / restic heredoc."""
    text = (_SCRIPTS / "setup-fa-desktop.sh").read_text(encoding="utf-8")
    # No re-inlined restic command (that lives only in scripts/backup-fa.sh now).
    assert text.count("restic -r") == 0
    # No inline systemd unit heredoc (installed from scripts/fa.service instead).
    assert "[Unit]\nDescription=First-Agent" not in text
    # backup-fa.sh is copied from the cloned repo, not regenerated inline.
    assert "repo/First-Agent-dev/scripts/backup-fa.sh" in text


def test_fa_service_is_a_valid_user_unit() -> None:
    """A systemd *user* unit must not depend on the docker *system* unit."""
    unit = (_SCRIPTS / "fa.service").read_text(encoding="utf-8")
    assert "Requires=docker.service" not in unit
    assert "docker compose -f docker-compose.fa.yml up -d" in unit


def test_post_setup_ensures_unified_routing_before_start() -> None:
    """B: fa-post-setup.sh must prepare the single routing file before compose up.

    The proxy no longer reads a separate proxy/models.yaml copy. Both containers
    mount /srv/first-agent/routing/models.yaml read-only, so post-setup must
    create or migrate that file before Docker sees the file bind mount.
    """
    text = (_SCRIPTS / "fa-post-setup.sh").read_text(encoding="utf-8")
    assert "/srv/first-agent/routing/models.yaml" in text
    assert "ensure_routing_models" in text
    assert "PROXY_MODELS_FILE" not in text
    assert "Syncing proxy routing config" not in text


def test_fa_update_targets_the_agent_service_not_first_listed() -> None:
    """F-3: never pick the first `config --services` entry (order not guaranteed).

    Alphabetically 'fa-egress-proxy' sorts before 'first-agent'; selecting the
    proxy would point health/smoke/pytest at a container with no /workspace.
    """
    text = (_SCRIPTS / "fa-update.sh").read_text(encoding="utf-8")
    assert "config --services 2>/dev/null | head -n1" not in text, (
        "must not blindly take the first service from `config --services`"
    )
    # Explicitly resolves to the agent service.
    assert "grep -qx 'first-agent'" in text


def test_fa_update_probes_the_llm_path() -> None:
    """F-4: update must verify the egress proxy / agent→proxy reachability."""
    text = (_SCRIPTS / "fa-update.sh").read_text(encoding="utf-8")
    assert "fa-egress-proxy" in text
    assert "/healthz" in text
    assert "check_proxy_path" in text



def test_compose_up_scripts_validate_file_mount_sources() -> None:
    for name in ("fa-update.sh", "fa-post-setup.sh", "fa-clean-rebuild.sh"):
        text = (_SCRIPTS / name).read_text(encoding="utf-8")
        assert "routing/models.yaml" in text
        assert "fa_proxy_token" in text
        assert "github_deploy_key" in text
        assert "known_hosts" in text
        assert "Mount source is a DIRECTORY" in text or "validate_file_mount_sources" in text


def test_setup_downloads_host_installers_with_retry_and_without_pipe_to_root_shell() -> None:
    text = (_SCRIPTS / "setup-fa-desktop.sh").read_text(encoding="utf-8")
    assert "curl -fsSL https://tailscale.com/install.sh | sudo sh" not in text
    assert "https://download.docker.com/linux/ubuntu/gpg" in text
    assert "https://tailscale.com/install.sh" in text
    assert "--retry" in text
    assert "--retry-all-errors" in text
    assert "mktemp" in text


def test_post_setup_does_not_interpolate_remote_or_branch_inside_docker_exec_shell() -> None:
    text = (_SCRIPTS / "fa-post-setup.sh").read_text(encoding="utf-8")
    assert "git ls-remote ${REPO_SSH_URL}" not in text
    assert "git push origin --delete $TEST_BRANCH" not in text
    assert "git push origin $TEST_BRANCH" not in text
    assert "-e REPO_SSH_URL=" in text
    assert "-e TEST_BRANCH=" in text



def _write_env_templates(repo: Path) -> None:
    (repo / "secrets").mkdir(parents=True)
    (repo / ".env.fa.template").write_text(
        "# First-Agent NON-SECRET runtime controls.\n"
        "# API KEYS DO NOT GO HERE.\n"
        "# FA_AUTO_RUN=0\n",
        encoding="utf-8",
    )
    (repo / "secrets" / "fa.env.template").write_text(
        "# First-Agent LLM API KEYS — consumed ONLY by the fa-egress-proxy container.\n"
        "# OPENROUTER_API_KEY=sk-or-v1-CHANGEME\n"
        "# FIREWORKS_API_KEY=fw-CHANGEME\n",
        encoding="utf-8",
    )


def _run_normalizer(
    repo: Path, env_fa: Path, secrets_env: Path, backup_dir: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(_SCRIPTS / "fa-normalize-env.sh")],
        env={
            "PATH": os.environ.get("PATH", ""),
            "FA_NORMALIZE_USE_SUDO": "0",
            "REPO_DIR": str(repo),
            "ENV_FA": str(env_fa),
            "SECRETS_ENV": str(secrets_env),
            "BACKUP_DIR": str(backup_dir),
        },
        capture_output=True,
        text=True,
        check=False,
    )


def test_normalize_env_replaces_legacy_comment_only_env_and_preserves_fa_controls(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_env_templates(repo)
    env_fa = repo / ".env.fa"
    env_fa.write_text(
        "# Convention separation:\n"
        "# - LLM API keys -> .env.fa (container runtime, loaded by compose)\n"
        "# OPENROUTER_API_KEY=sk-or-v1-CHANGEME\n"
        "FA_AUTO_RUN=1\n",
        encoding="utf-8",
    )
    secrets_env = tmp_path / "secrets" / "fa.env"

    result = _run_normalizer(repo, env_fa, secrets_env, tmp_path / "backups")

    assert result.returncode == 0, result.stdout + result.stderr
    env_text = env_fa.read_text(encoding="utf-8")
    assert "LLM API keys -> .env.fa" not in env_text
    assert "API KEYS DO NOT GO HERE" in env_text
    assert "FA_AUTO_RUN=1" in env_text
    assert "FIREWORKS_API_KEY" in secrets_env.read_text(encoding="utf-8")


def test_normalize_env_migrates_active_secret_lines_out_of_env_fa(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_env_templates(repo)
    env_fa = repo / ".env.fa"
    env_fa.write_text(
        "OPENROUTER_API_KEY=sk-real\n"
        "FA_ROLE=coder\n",
        encoding="utf-8",
    )
    secrets_env = tmp_path / "secrets" / "fa.env"
    secrets_env.parent.mkdir()
    secrets_env.write_text("FIREWORKS_API_KEY=fw-existing\n", encoding="utf-8")

    result = _run_normalizer(repo, env_fa, secrets_env, tmp_path / "backups")

    assert result.returncode == 0, result.stdout + result.stderr
    env_text = env_fa.read_text(encoding="utf-8")
    secret_text = secrets_env.read_text(encoding="utf-8")
    assert "OPENROUTER_API_KEY" not in env_text
    assert "FA_ROLE=coder" in env_text
    assert "OPENROUTER_API_KEY=sk-real" in secret_text
    assert "FIREWORKS_API_KEY=fw-existing" in secret_text
    assert "First-Agent LLM API KEYS" in secret_text


def test_normalize_env_replaces_changeme_secret_with_real_legacy_value(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_env_templates(repo)
    env_fa = repo / ".env.fa"
    env_fa.write_text("OPENROUTER_API_KEY=sk-real\n", encoding="utf-8")
    secrets_env = tmp_path / "secrets" / "fa.env"
    secrets_env.parent.mkdir()
    secrets_env.write_text("OPENROUTER_API_KEY=sk-CHANGEME\n", encoding="utf-8")

    result = _run_normalizer(repo, env_fa, secrets_env, tmp_path / "backups")

    assert result.returncode == 0, result.stdout + result.stderr
    env_text = env_fa.read_text(encoding="utf-8")
    secret_text = secrets_env.read_text(encoding="utf-8")
    assert "OPENROUTER_API_KEY" not in env_text
    assert "OPENROUTER_API_KEY=sk-real" in secret_text
    assert "OPENROUTER_API_KEY=sk-CHANGEME" not in secret_text
    backups = list((tmp_path / "backups").glob("fa.env.pre-adr12-normalize.*.bak"))
    assert backups, "fa.env should be backed up before replacing a placeholder"


def test_normalize_env_does_not_overwrite_existing_real_secret(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_env_templates(repo)
    env_fa = repo / ".env.fa"
    env_fa.write_text("OPENROUTER_API_KEY=sk-other\n", encoding="utf-8")
    secrets_env = tmp_path / "secrets" / "fa.env"
    secrets_env.parent.mkdir()
    secrets_env.write_text("OPENROUTER_API_KEY=sk-existing\n", encoding="utf-8")

    result = _run_normalizer(repo, env_fa, secrets_env, tmp_path / "backups")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "OPENROUTER_API_KEY" not in env_fa.read_text(encoding="utf-8")
    secret_text = secrets_env.read_text(encoding="utf-8")
    assert "OPENROUTER_API_KEY=sk-existing" in secret_text
    assert "OPENROUTER_API_KEY=sk-other" not in secret_text


def test_normalize_env_combined_secret_and_legacy_comments_keeps_original_backup(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_env_templates(repo)
    env_fa = repo / ".env.fa"
    env_fa.write_text(
        "# LLM API keys -> .env.fa\n"
        "OPENROUTER_API_KEY=sk-real\n"
        "FA_ROLE=coder\n",
        encoding="utf-8",
    )
    secrets_env = tmp_path / "secrets" / "fa.env"

    result = _run_normalizer(repo, env_fa, secrets_env, tmp_path / "backups")

    assert result.returncode == 0, result.stdout + result.stderr
    env_text = env_fa.read_text(encoding="utf-8")
    assert "LLM API keys -> .env.fa" not in env_text
    assert "FA_ROLE=coder" in env_text
    assert "OPENROUTER_API_KEY=sk-real" in secrets_env.read_text(encoding="utf-8")
    backup_texts = [
        path.read_text(encoding="utf-8")
        for path in (tmp_path / "backups").glob(".env.fa.pre-adr12-normalize.*.bak")
    ]
    assert any(
        "LLM API keys -> .env.fa" in text and "OPENROUTER_API_KEY=sk-real" in text
        for text in backup_texts
    )


def test_normalize_env_provider_placeholder_append_is_idempotent(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_env_templates(repo)
    env_fa = repo / ".env.fa"
    env_fa.write_text("# clean non-secret file\n", encoding="utf-8")
    secrets_env = tmp_path / "secrets" / "fa.env"
    secrets_env.parent.mkdir()
    secrets_env.write_text("FIREWORKS_API_KEY=fw-existing\n", encoding="utf-8")

    first = _run_normalizer(repo, env_fa, secrets_env, tmp_path / "backups")
    second = _run_normalizer(repo, env_fa, secrets_env, tmp_path / "backups")

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    secret_text = secrets_env.read_text(encoding="utf-8")
    assert secret_text.count("Provider placeholders from secrets/fa.env.template") == 1


def test_post_setup_normalizes_env_before_validating_keys() -> None:
    text = (_SCRIPTS / "fa-post-setup.sh").read_text(encoding="utf-8")
    assert text.index("fa-normalize-env.sh") < text.index("Validate the LLM API keys")


def test_deploy_scripts_run_fa_selfcheck() -> None:
    """D-1: post-setup and update must run `fa selfcheck` (route/key drift).

    /healthz reachability alone cannot catch routing/key drift — the real cause
    of "both healthy but chain_exhausted". `fa selfcheck` validates the proxy's
    route table against the agent's models.yaml and key presence. Warn-only.
    """
    for name in ("fa-post-setup.sh", "fa-update.sh"):
        text = (_SCRIPTS / name).read_text(encoding="utf-8")
        assert "fa selfcheck" in text, f"{name} must run `fa selfcheck`"
        # The cheaper reachability probe stays as a first-line check.
        assert "/healthz" in text, f"{name} must keep the /healthz probe"


def test_post_setup_health_wait_is_configurable() -> None:
    """D-3: fa-post-setup must honor HEALTH_TIMEOUT_SECONDS, not a fixed 60."""
    text = (_SCRIPTS / "fa-post-setup.sh").read_text(encoding="utf-8")
    assert "HEALTH_TIMEOUT_SECONDS" in text
    assert "for _ in {1..60}" not in text, (
        "hard-coded {1..60} loop must use HEALTH_TIMEOUT_SECONDS"
    )


def test_health_timeout_default_is_consistent() -> None:
    """D-4: the three deploy scripts default HEALTH_TIMEOUT_SECONDS to 90."""
    for name in ("fa-post-setup.sh", "fa-update.sh", "fa-clean-rebuild.sh"):
        text = (_SCRIPTS / name).read_text(encoding="utf-8")
        assert 'HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-90}"' in text, (
            f"{name} should default HEALTH_TIMEOUT_SECONDS to 90"
        )


def test_env_template_does_not_hardcode_fa_config_models_path() -> None:
    """D-5: drop the stale FA_CONFIG=...models.yaml hint (now a read-only mount)."""
    text = (_SCRIPTS.parent / ".env.fa.template").read_text(encoding="utf-8")
    assert "# FA_CONFIG=/home/fa/.fa/models.yaml" not in text


def test_legacy_routing_migration_blocks_have_sunset_notes() -> None:
    """D-6: every legacy routing-migration block carries a dated sunset note."""
    for name in (
        "setup-fa-desktop.sh",
        "fa-post-setup.sh",
        "fa-update.sh",
        "fa-clean-rebuild.sh",
    ):
        text = (_SCRIPTS / name).read_text(encoding="utf-8")
        assert "LEGACY_STATE_MODELS" in text  # block still present
        assert "SUNSET (remove after" in text, f"{name} needs a sunset note"


def test_fa_update_extract_active_fa_vars_survives_commented_only_template(
    tmp_path: Path,
) -> None:
    """Regression: `extract_active_fa_vars` on a template whose FA_* lines are
    ALL commented must not abort fa-update.sh under `set -Eeuo pipefail`.

    `grep` exits 1 on no-match; without the `|| true` guard that status
    propagates out of the command substitution and trips the ERR trap, killing
    the deploy at STEP 3 (the field-observed failure). The function is expected
    to return an empty result here, which the caller handles.
    """
    template = tmp_path / ".env.fa.template"
    template.write_text(
        "# non-secret controls\n# FA_AUTO_RUN=0\n# FA_ROLE=coder\n",
        encoding="utf-8",
    )
    script = _SCRIPTS / "fa-update.sh"
    # Source only the function out of the script and invoke it the same way the
    # script does (inside a command substitution) under the same shell options.
    snippet = (
        "set -Eeuo pipefail\n"
        "trap 'exit 42' ERR\n"
        f"source <(sed -n '/^extract_active_fa_vars()/,/^}}/p' {script!s})\n"
        f'out=$(extract_active_fa_vars "{template!s}")\n'
        'printf "RESULT=[%s]\\n" "$out"\n'
    )
    proc = subprocess.run(
        ["bash", "-c", snippet], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, (
        f"extract_active_fa_vars aborted under pipefail (rc={proc.returncode}); "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    assert "RESULT=[]" in proc.stdout, proc.stdout
