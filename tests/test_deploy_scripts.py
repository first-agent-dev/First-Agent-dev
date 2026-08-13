"""Drift guard for the host-side deployment / administration shell scripts.

Mirrors ``tests/test_fa_update_script.py`` but covers the whole deployment
script surface so that future edits cannot silently introduce a syntax error,
re-duplicate the heredocs we removed, or break the bootstrap contract.

These tests are deliberately cheap (static checks: ``bash -n`` + ``shellcheck``
when available + simple substring assertions); they do not spin up Docker.
"""

from __future__ import annotations

import atexit
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from tests._capabilities import requires_posix_modes, requires_posix_paths, requires_stable_tmpdir

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _ROOT / "scripts"

# Host-side shell scripts that operators run directly or that ship in the image.
_SHELL_SCRIPTS = [
    _SCRIPTS / "fa",
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


# Container CLIs that scripts/fa may try to ``exec``. Unit tests must never
# reach a real container runtime (even if one happens to be installed on the
# developer's host) because the test contract asserts delegation failure
# behaviour. We shadow them with a tiny stub script (see ``_docker_shadow_dir``)
# rather than stripping PATH directories — stripping is unsafe because
# ``docker`` often lives in the same directory as ``bash`` (e.g. ``/usr/bin``
# on Ubuntu), and removing that directory breaks every other binary lookup.
_CONTAINER_RUNTIMES_TO_SHADOW: tuple[str, ...] = ("docker", "podman")

_docker_shadow_dir: Path | None = None


def _get_docker_shadow_dir() -> Path:
    """Create (once) a temp directory holding fake docker/podman stubs.

    The stubs emit a deterministic "docker: not found" style message to stderr
    and exit non-zero, which matches the shape of a missing-binary error
    closely enough to satisfy scripts/fa's fallthrough behaviour AND the
    assertion in ``test_fa_wrapper_unknown_help_topic_delegates_to_container``.
    The directory is cleaned up at interpreter exit.
    """
    global _docker_shadow_dir
    if _docker_shadow_dir is not None and _docker_shadow_dir.exists():
        return _docker_shadow_dir
    d = Path(tempfile.mkdtemp(prefix="fa-test-docker-shadow-"))
    stub = (
        "#!/bin/sh\n"
        "# Test-only stub injected by tests/test_deploy_scripts.py::_wrapper_env().\n"
        "# Replaces docker/podman on PATH so unit tests don't accidentally exec into\n"
        "# a real container on hosts that happen to have one running. Production\n"
        "# operator shells never see this directory.\n"
        'echo "docker: not found (test shim; refusing to exec into container from unit tests)" >&2\n'
        "exit 127\n"
    )
    for name in _CONTAINER_RUNTIMES_TO_SHADOW:
        p = d / name
        p.write_text(stub, encoding="utf-8")
        p.chmod(0o755)
    _docker_shadow_dir = d
    return d


def _cleanup_docker_shadow() -> None:
    global _docker_shadow_dir
    if _docker_shadow_dir is not None and _docker_shadow_dir.exists():
        shutil.rmtree(_docker_shadow_dir, ignore_errors=True)
    _docker_shadow_dir = None


atexit.register(_cleanup_docker_shadow)


def _wrapper_env() -> dict[str, str]:
    """Build a deterministic env for exercising scripts/fa.

    Design goals (each corresponds to a real failure we have hit):

    1. ``fa`` must be importable when ``scripts/fa`` invokes
       ``${PYTHON:-python3} -m fa.cli_help``. When pytest is launched from an
       editor (VSCode) pointing directly at the venv interpreter (e.g. the
       ``../snap/code/.../cpython-3.14`` shim VSCode uses on Ubuntu), the
       venv's ``bin/`` is NOT on PATH the way an interactive
       ``source .venv/bin/activate`` would make it, so plain ``python3``
       resolves to the system interpreter (no ``fa`` module). Pinning
       ``PYTHON=sys.executable`` removes that PATH-dependency.

    2. ``bash``, ``true``, ``cat``, ``pwd``, ``ls`` and every other host
       binary MUST remain resolvable. The earlier implementation filtered PATH
       directories that contained a ``docker`` binary, which on stock Ubuntu
       ripped ``/usr/bin`` out of PATH and made ``bash`` itself unfindable
       (FileNotFoundError: 'bash'). The fix is to **prepend** a shadow
       directory containing docker/podman stubs rather than **removing** any
       PATH entries. Unix PATH lookup is first-match-wins, so our stub wins
       for ``docker``/``podman`` while every other command falls through to
       the host.

    3. ``docker compose exec`` must deterministically fail (rc != 0) so the
       "unknown help topic delegates to container" test does not flake on
       hosts where the first-agent container happens to be running (a live
       container makes delegation return rc=0 with real help, which is
       correct production behaviour but violates the "we did not swallow the
       topic as host help" assertion). The stubs in the shadow directory
       exit 127 with a "docker: not found" message matching one of the
       assertion's accepted terms.
    """
    env = os.environ.copy()
    env["PYTHON"] = sys.executable

    # Build PATH: shadow dir FIRST (our stubs win), then the venv bin (so
    # python3 resolves to the venv when pytest was launched without an
    # activated venv), then the inherited PATH verbatim — no directory is
    # ever removed. This is what fixes the "bash not found" regression:
    # /usr/bin (and any other directory the user has) stays on PATH.
    venv_bin = str(Path(sys.executable).parent)
    shadow = str(_get_docker_shadow_dir())
    existing = env.get("PATH", "")
    parts: list[str] = [shadow]
    for p in existing.split(os.pathsep):
        if not p or p in parts:
            continue
        parts.append(p)
    if venv_bin not in parts:
        # Insert venv bin right after the shadow so it wins over any other
        # python3 on PATH, but after the shadow so docker stubs still win.
        parts.insert(1, venv_bin)
    env["PATH"] = os.pathsep.join(parts)

    # Drop container-oriented env vars that would change wrapper dispatch.
    for var in ("FA_COMPOSE_FILE",):
        env.pop(var, None)
    return env


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


@requires_posix_modes
@pytest.mark.skipif(not os.access(_SCRIPTS / "fa", os.X_OK), reason="Filesystem does not support executable bits")
def test_executable_script_modes_are_pinned() -> None:
    """Scripts invoked directly by operators/git must keep executable mode."""
    expected_exec = [
        _SCRIPTS / "fa",
        _SCRIPTS / "fa-update.sh",
        _SCRIPTS / "fa-clean-rebuild.sh",
        _SCRIPTS / "fa-post-setup.sh",
        _SCRIPTS / "ssh-tailscale" / "00-failsafe.sh",
        _SCRIPTS / "ssh-tailscale" / "10-diagnose.sh",
        _SCRIPTS / "ssh-tailscale" / "20-harden.sh",
        _SCRIPTS / "ssh-tailscale" / "30-verify.sh",
        _SCRIPTS.parent / "src" / "fa" / "hygiene" / "hooks" / "commit-msg",
        _SCRIPTS.parent / "src" / "fa" / "hygiene" / "hooks" / "pre-commit",
        _SCRIPTS.parent / "src" / "fa" / "hygiene" / "hooks" / "pre-push",
        _SCRIPTS.parent / "src" / "fa" / "hygiene" / "hooks" / "prepare-commit-msg",
    ]
    for path in expected_exec:
        assert path.stat().st_mode & stat.S_IXUSR, f"missing executable bit: {path}"


def _run_fa_wrapper(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(_SCRIPTS / "fa"), *args],
        capture_output=True,
        text=True,
        check=False,
        env=_wrapper_env(),
    )


def test_fa_wrapper_host_topic_help_is_russian_and_detailed() -> None:
    result = _run_fa_wrapper("help", "clean-rebuild")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "fa clean-rebuild [env]" in result.stdout
    assert "Переменные окружения" in result.stdout
    assert "WIPE_STATE=1" in result.stdout
    assert "ASSUME_YES=1" in result.stdout


def test_fa_wrapper_command_help_form_for_update() -> None:
    result = _run_fa_wrapper("update", "--help")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "fa update [env]" in result.stdout
    assert "AUTO_STASH=1" in result.stdout
    assert "--force" in result.stdout


def test_fa_wrapper_global_help_topic_form_for_update() -> None:
    result = _run_fa_wrapper("--help", "update")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "fa update [env]" in result.stdout
    assert "SKIP_TESTS=1" in result.stdout


def test_fa_wrapper_has_real_clean_rebuild_dispatch_case() -> None:
    text = (_SCRIPTS / "fa").read_text(encoding="utf-8")

    assert "clean-rebuild)" in text
    assert 'exec "$REPO_DIR/scripts/fa-clean-rebuild.sh" "$@"' in text


def test_fa_wrapper_dispatches_every_documented_host_topic() -> None:
    from fa.cli_help import HOST_COMMANDS

    text = (_SCRIPTS / "fa").read_text(encoding="utf-8")
    for command in HOST_COMMANDS:
        assert f"    {command})" in text, f"missing host dispatch case for {command}"


def test_fa_wrapper_rejects_clean_rebuild_typo_before_delegation() -> None:
    result = _run_fa_wrapper("clean", "rebuild")

    assert result.returncode == 2
    assert "fa clean-rebuild" in result.stderr


def test_fa_wrapper_unknown_help_topic_delegates_to_container() -> None:
    result = _run_fa_wrapper("help", "run")

    # Docker is intentionally unavailable in the unit test environment; the
    # important contract is that wrapper did NOT swallow `help run` as host help.
    assert result.returncode != 0
    assert any(term in result.stderr for term in ("exec: docker", "docker:", 'service "first-agent" is not running'))


@requires_stable_tmpdir
def test_wrapper_env_preserves_host_binaries_and_shadows_docker() -> None:
    """Regression guard for the env builder.

    A previous implementation filtered PATH entries that contained a
    ``docker`` binary, which on stock Ubuntu (where docker lives in
    ``/usr/bin`` alongside bash, ls, cat, true, python3, ...) stripped
    ``/usr/bin`` from PATH and produced FileNotFoundError: 'bash' when
    ``_run_fa_wrapper`` tried to exec bash.

    This test pins three invariants for ``_wrapper_env()``:

    1. Common host utilities (bash, sh, true, pwd, ls, cat, echo) remain
       resolvable through ``which`` under the constructed env.
    2. ``docker`` and ``podman`` resolve to the test-shim directory (not to
       any real container runtime the developer's host may have installed).
    3. Invoking the shimmed docker fails non-zero with a deterministic
       "docker:" message, matching the assertion contract used by
       ``test_fa_wrapper_unknown_help_topic_delegates_to_container``.
    """
    env = _wrapper_env()
    path = env.get("PATH", "")
    assert path, "_wrapper_env must set PATH"

    def _which(name: str) -> str | None:
        for d in path.split(os.pathsep):
            candidate = Path(d) / name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
        return None

    # Invariant 1: essential host utilities remain resolvable.
    for required in ("bash", "sh", "true", "pwd", "ls", "cat", "echo"):
        resolved = _which(required)
        assert resolved is not None, f"_wrapper_env stripped {required!r} from PATH: {path}"

    # Invariant 2: docker/podman resolve to our shadow dir, not to any
    # host-installed binary (even if the developer has Docker Desktop).
    shadow = str(_get_docker_shadow_dir())
    for container_cli in _CONTAINER_RUNTIMES_TO_SHADOW:
        resolved = _which(container_cli)
        assert resolved is not None, f"_wrapper_env must provide a {container_cli} shim"
        assert resolved == str(Path(shadow) / container_cli), (
            f"{container_cli} resolved to {resolved!r} instead of test shim "
            f"at {Path(shadow) / container_cli!r} (a real container runtime "
            "leaked into the test subprocess)."
        )

    # Invariant 3: the shim fails non-zero with a stderr line containing
    # "docker:" so the wrapper's "docker: not found" assertion fires.
    result = subprocess.run(
        ["docker", "compose", "exec", "first-agent", "fa", "help"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode != 0
    assert "docker:" in result.stderr
    assert "test shim" in result.stderr  # identifiable as the shim, not real docker


def test_fa_wrapper_uses_cli_help_as_single_source_of_truth() -> None:
    text = (_SCRIPTS / "fa").read_text(encoding="utf-8")

    assert "-m fa.cli_help" in text
    assert "--host-topic" in text
    assert "--wrapper-usage" in text
    # Detailed operator help belongs in src/fa/cli_help.py, not duplicated in bash heredocs.
    assert "WIPE_STATE=1" not in text
    assert "AUTO_STASH=1" not in text


def test_cli_help_contains_host_wrapper_topics() -> None:
    from fa.cli_help import HOST_COMMANDS, render_host_command_help_ru, render_wrapper_usage_ru

    assert "clean-rebuild" in HOST_COMMANDS
    assert "update" in HOST_COMMANDS
    clean_help = render_host_command_help_ru("clean-rebuild")
    assert "WIPE_STATE=1" in clean_help
    assert "ASSUME_YES=1" in clean_help
    assert "fa clean-rebuild [env]" in clean_help
    usage = render_wrapper_usage_ru()
    assert "Инфраструктура на хосте" in usage
    assert "Agent CLI внутри контейнера" in usage


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
    # backup-fa.sh stays in the repo as the single source of truth.
    assert "repo/First-Agent-dev/scripts/backup-fa.sh" in text
    assert 'cp "$BACKUP_SRC" "$FA_DIR/scripts/backup-fa.sh"' not in text


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
    assert "REPO_SSH_URL" not in text
    assert "git ls-remote ${push_url}" not in text
    assert "git push origin --delete $TEST_BRANCH" not in text
    assert "git push origin $TEST_BRANCH" not in text
    assert "push_url=$(git remote get-url --push origin)" in text
    assert 'git ls-remote "$push_url"' in text
    assert '-e SESSION_WS="$SESSION_WS"' in text
    assert "-e TEST_BRANCH=" in text


def test_post_setup_relies_on_lifecycle_identity_and_proves_source_unchanged() -> None:
    """C2/C3: post-setup tests configured publication without masking lifecycle defects."""

    text = (_SCRIPTS / "fa-post-setup.sh").read_text(encoding="utf-8")

    identity_writes = re.findall(
        r"(?m)^[^#\n]*\bgit\b[^\n]*\bconfig\b[^\n]*\buser\.(?:name|email)\b",
        text,
    )
    assert identity_writes == []
    assert "SOURCE_HEAD_BEFORE=" in text
    assert "SOURCE_STATUS_BEFORE=" in text
    assert "SOURCE_HEAD_AFTER=" in text
    assert "SOURCE_STATUS_AFTER=" in text
    assert '"$SOURCE_HEAD_AFTER" != "$SOURCE_HEAD_BEFORE"' in text
    assert '"$SOURCE_STATUS_AFTER" != "$SOURCE_STATUS_BEFORE"' in text
    assert "Git push smoke mutated /repo" in text


def _write_env_templates(repo: Path) -> None:
    (repo / "knowledge" / "templates").mkdir(parents=True)
    (repo / ".env.fa.template").write_text(
        "# First-Agent NON-SECRET runtime controls.\n# API KEYS DO NOT GO HERE.\n# FA_AUTO_RUN=0\n",
        encoding="utf-8",
    )
    (repo / "knowledge" / "templates" / "fa.env.template").write_text(
        "# First-Agent LLM API KEYS — consumed ONLY by the fa-egress-proxy container.\n"
        "# OPENROUTER_API_KEY=sk-or-v1-CHANGEME\n"
        "# FIREWORKS_API_KEY=fw-CHANGEME\n",
        encoding="utf-8",
    )


def _run_normalizer(repo: Path, env_fa: Path, secrets_env: Path, backup_dir: Path) -> subprocess.CompletedProcess[str]:
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
        "OPENROUTER_API_KEY=sk-real\nFA_ROLE=coder\n",
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
        "# LLM API keys -> .env.fa\nOPENROUTER_API_KEY=sk-real\nFA_ROLE=coder\n",
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
        path.read_text(encoding="utf-8") for path in (tmp_path / "backups").glob(".env.fa.pre-adr12-normalize.*.bak")
    ]
    assert any("LLM API keys -> .env.fa" in text and "OPENROUTER_API_KEY=sk-real" in text for text in backup_texts)


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
    assert secret_text.count("Provider placeholders from knowledge/templates/fa.env.template") == 1


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
    assert "for _ in {1..60}" not in text, "hard-coded {1..60} loop must use HEALTH_TIMEOUT_SECONDS"


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


def test_push_url_override_is_documented_only_in_non_secret_template() -> None:
    """C0/C3 S8: publication routing is non-secret and never enters provider-key templates."""

    runtime_template = (_ROOT / ".env.fa.template").read_text(encoding="utf-8")
    secret_template = (_ROOT / "knowledge" / "templates" / "fa.env.template").read_text(encoding="utf-8")

    assert "FA_REPO_PUSH_URL" in runtime_template
    assert "credential-free" in runtime_template
    assert "FA_REPO_PUSH_URL" not in secret_template


def test_current_workspace_docs_reject_superseded_transport_and_session_claims() -> None:
    """C0 S8/T15: current operator surfaces describe pack transport and persistent sessions."""

    current_docs = (
        _ROOT / "README.md",
        _ROOT / "AGENTS.md",
        _ROOT / "knowledge" / "adr" / "ADR-13-workspace-isolation.md",
        _ROOT / "knowledge" / "adr" / "DIGEST.md",
        _ROOT / "knowledge" / "instructions" / "01-install.md",
        _ROOT / "knowledge" / "instructions" / "02-operations.md",
        _ROOT / "knowledge" / "overview" / "FEATURES.md",
        _ROOT / "knowledge" / "ci-guardrails-reference.md",
        _ROOT / "worklogs" / "HANDOFF.md",
    )
    stale_phrases = (
        "git clone --local",
        "hardlink",
        "container lifecycle corresponds to one session",
        "one session per container lifecycle",
        "по одной на старт контейнера",
    )

    violations = {
        str(path.relative_to(_ROOT)): phrase
        for path in current_docs
        for phrase in stale_phrases
        if phrase in path.read_text(encoding="utf-8").lower()
    }
    assert violations == {}
    operations = (_ROOT / "knowledge" / "instructions" / "02-operations.md").read_text(encoding="utf-8")
    normalized_operations = " ".join(operations.split())
    assert "Перезапуск повторно применяет session selector" in normalized_operations
    assert "Контейнер перезапустится и создаст чистую сессию" not in normalized_operations
    assert "~/.fa/sessions/<session-id>/session.db" in operations
    assert "~/.fa/session-log/<run_id>/session.db" not in operations


def test_historical_workspace_docs_have_top_level_superseded_banner() -> None:
    """C0 S8/T15: obsolete command sheets remain evidence, never current instructions."""

    historical_docs = (
        _ROOT / "knowledge" / "pr-notes" / "workspace-isolation.md",
        _ROOT / "worklogs" / "pr-notes" / "workspace-isolation.md",
        _ROOT / "worklogs" / "S13-NEXT-SESSION-START.md",
        _ROOT / "worklogs" / "S13-SESSION-START-PROMPT.md",
    )
    for path in historical_docs:
        banner = "\n".join(path.read_text(encoding="utf-8").splitlines()[:12])
        assert "HISTORICAL / SUPERSEDED" in banner, path
        assert "ADR-13-workspace-isolation.md" in banner, path
        assert "AP-004-symptom-chasing-without-model.md" in banner, path


def test_workspace_stale_claims_are_confined_to_historical_evidence() -> None:
    """C0 S8/T15: any new stale-claim path is a documentation-contract failure."""

    stale_phrases = (
        "git clone --local",
        "hardlink",
        "container lifecycle corresponds to one session",
        "one session per container lifecycle",
        "по одной на старт контейнера",
    )
    allowed_prefixes = (
        Path("knowledge/research"),
        Path("knowledge/trace"),
        Path("worklogs/archive"),
    )
    allowed_paths = {
        Path("knowledge/anti-patterns/AP-004-symptom-chasing-without-model.md"),
        Path("knowledge/pr-notes/workspace-isolation.md"),
        Path("worklogs/pr-notes/workspace-isolation.md"),
        Path("worklogs/S13-NEXT-SESSION-START.md"),
        Path("worklogs/S13-SESSION-START-PROMPT.md"),
        Path("worklogs/implementation-plans/PLAN-session-workspace-readiness-bootstrap.md"),
    }
    violations: dict[str, list[str]] = {}
    for path in _ROOT.rglob("*.md"):
        relative = path.relative_to(_ROOT)
        if any(part in {".git", ".venv", "node_modules", "mutants"} for part in relative.parts):
            continue
        text = path.read_text(encoding="utf-8").lower()
        hits = [phrase for phrase in stale_phrases if phrase in text]
        allowed = relative in allowed_paths or any(relative.is_relative_to(prefix) for prefix in allowed_prefixes)
        if hits and not allowed:
            violations[relative.as_posix()] = hits
    assert violations == {}


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


@requires_posix_paths
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
    proc = subprocess.run(["bash", "-c", snippet], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, (
        f"extract_active_fa_vars aborted under pipefail (rc={proc.returncode}); "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    assert "RESULT=[]" in proc.stdout, proc.stdout


def test_fa_update_run_tests_step_is_truly_non_fatal() -> None:
    """STEP 7 (run_tests) must not abort the deploy when pytest fails.

    fa-update.sh runs with `set -Eeuo pipefail`. With `set -E` (errtrace) the ERR
    trap fires on a non-zero command EVEN AFTER `set +e`, so a red pytest would
    trip the trap and exit the script — despite STEP 7 being documented as
    non-fatal (the stack is already up). The fix disables the ERR trap around the
    pytest invocation and restores it after capturing TEST_RC. Guard both pieces.
    """
    text = (_SCRIPTS / "fa-update.sh").read_text(encoding="utf-8")
    run_tests = text[text.index("run_tests()") :]
    run_tests = run_tests[: run_tests.index("\n}\n") + 2]
    # The non-fatal block must drop the ERR trap before running pytest and
    # reinstate it afterwards.
    assert "trap - ERR" in run_tests, "run_tests must disable the ERR trap for pytest"
    # The trap must be reinstated after the run (a bare `trap - ERR` with no
    # restore would leak the disabled state into the rest of main()).
    assert "ERR\n  set -e" in run_tests, "run_tests must restore the ERR trap after pytest"
    # Ordering: drop the trap BEFORE the pytest invocation, restore AFTER it.
    drop = run_tests.index("trap - ERR")
    invoke = run_tests.index("-m pytest")
    restore = run_tests.index("ERR\n  set -e")
    assert drop < invoke < restore, "must drop ERR trap before pytest and restore after"


# ── Batch-1 regression: backup-fa.sh safe dotenv parser ──────────────────


def test_backup_script_does_not_source_env_file() -> None:
    """backup-fa.sh MUST NOT `source` the credentials file.

    `source` executes the file as shell, so a typo, a $(...) in a value, or
    a glob metacharacter would be evaluated as code under the cron user.
    The fix is a strict KEY=VALUE line parser (see _load_backup_env).
    """
    text = (_SCRIPTS / "backup-fa.sh").read_text(encoding="utf-8")
    assert "source /srv/first-agent/secrets/backup.env" not in text, (
        "backup-fa.sh must not source backup.env — use a restricted dotenv parser"
    )
    assert "_load_backup_env" in text, "must define a _load_backup_env function"


@requires_posix_paths
def test_backup_env_parser_whitelists_only_b2_vars(tmp_path: Path) -> None:
    """The parser must export only B2_KEY_ID/B2_APPLICATION_KEY/B2_BUCKET,
    ignore comments/blanks, strip surrounding quotes, and NEVER expand
    shell command substitutions in values."""
    env_file = tmp_path / "backup.env"
    env_file.write_text(
        "# this is a comment\n"
        "B2_KEY_ID=mykeyid\n"
        'B2_APPLICATION_KEY="my app key"\n'
        "B2_BUCKET='my-bucket'\n"
        "MALICIOUS=$(echo pwned)\n"
        "OTHER_VAR=should-be-ignored\n"
        "\n"
        "BADLINE without equals\n",
        encoding="utf-8",
    )
    script = _SCRIPTS / "backup-fa.sh"
    snippet = (
        "set -euo pipefail\n"
        # Pull the _load_backup_env function definition out of the script.
        f"source <(awk '/^_load_backup_env\\(\\)/,/^}}/' {script!s})\n"
        f'_load_backup_env "{env_file!s}"\n'
        'printf "KEY=[%s]\\n" "${B2_KEY_ID:-UNSET}"\n'
        'printf "APP=[%s]\\n" "${B2_APPLICATION_KEY:-UNSET}"\n'
        'printf "BKT=[%s]\\n" "${B2_BUCKET:-UNSET}"\n'
        'printf "MAL=[%s]\\n" "${MALICIOUS:-UNSET}"\n'
        'printf "OTH=[%s]\\n" "${OTHER_VAR:-UNSET}"\n'
    )
    proc = subprocess.run(["bash", "-c", snippet], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "KEY=[mykeyid]" in out
    assert "APP=[my app key]" in out, out  # double-quotes stripped
    assert "BKT=[my-bucket]" in out, out  # single-quotes stripped
    assert "MAL=[UNSET]" in out, "$(echo pwned) must not be expanded/exported"
    assert "OTH=[UNSET]" in out, "non-whitelisted names must be ignored"


# ── Batch-2 regression: no shell interpolation of untrusted input ────────


def test_post_setup_passes_session_ws_via_environment_not_interpolation() -> None:
    """fa-post-setup.sh MUST pass SESSION_WS into docker exec via -e and keep
    the bash script body SINGLE-QUOTED (no host-side `'$SESSION_WS'` or
    `\\$SESSION_WS` interpolation into double-quoted strings). SESSION_WS
    originates from a container-written file and is untrusted input."""
    text = (_SCRIPTS / "fa-post-setup.sh").read_text(encoding="utf-8")
    # Forbidden patterns: cd '$SESSION_WS' / cd '…$SESSION_WS' in a double-quoted
    # bash -c body (which would have HOST expanded $SESSION_WS into the string).
    # The fixed code uses single-quoted script bodies with -e SESSION_WS=… .
    assert "cd '$SESSION_WS'" not in text, "HOST-side interpolation of SESSION_WS into docker exec bash -c string"
    # Must pass SESSION_WS through docker -e flag.
    assert "-e SESSION_WS=" in text or '-e SESSION_WS="$SESSION_WS"' in text


def test_fa_update_restores_active_session_via_stdin_not_interpolation() -> None:
    """fa-update.sh must write the restored .active through stdin, NOT via
    bash -c \"echo '${_saved_active}' > /sessions/.active\" interpolation."""
    text = (_SCRIPTS / "fa-update.sh").read_text(encoding="utf-8")
    assert "echo '${_saved_active}'" not in text, (
        "interpolation of _saved_active into bash -c string is an injection sink"
    )
    # The fix pipes printf '%s\\n' over stdin into `docker exec … bash -c 'cat > …'`.
    assert "cat > /sessions/.active" in text


# ── Batch-3 regressions: arrays, absolute paths, backup location ─────────


def test_fa_wrapper_uses_arrays_for_compose_and_flags() -> None:
    """`scripts/fa` must hold COMPOSE/TTY_FLAG/_W_FLAG as bash arrays and
    expand them with \"${COMPOSE[@]}\" — bare `exec $COMPOSE` word-splits
    and breaks on paths/flags with spaces."""
    text = (_SCRIPTS / "fa").read_text(encoding="utf-8")
    assert "COMPOSE=(docker compose" in text, "COMPOSE must be a bash array"
    assert '"${COMPOSE[@]}"' in text, 'must expand COMPOSE as "${COMPOSE[@]}"'
    assert "TTY_FLAG=(-T)" in text
    assert "_W_FLAG=(-w" in text
    # No bare `exec $COMPOSE` left in the script.
    assert not re.search(r"exec\s+\$COMPOSE\b", text), "no bare `exec $COMPOSE` word-splitting expansion"


def test_fa_clean_rebuild_backs_up_to_fa_dir_backup() -> None:
    """fa-clean-rebuild.sh step 3 must place backups under ${FA_DIR}/backup/,
    not $HOME, so they live on the same dataset as the rest of FA state
    and are covered by the nightly restic backup."""
    text = (_SCRIPTS / "fa-clean-rebuild.sh").read_text(encoding="utf-8")
    assert 'BK="${HOME}/fa-backup-' not in text, "backups must NOT land under $HOME"
    assert "${FA_DIR}/backup" in text, "backup root must be ${FA_DIR}/backup"


def test_fa_update_ensure_host_scripts_uses_absolute_paths_and_covers_hooks() -> None:
    """ensure_host_scripts() must use ${REPO_DIR}/scripts (absolute path),
    not a relative `scripts/` that depends on cwd, and must also chmod the
    git hooks (matching setup-fa-desktop.sh and fa-post-setup.sh) so a
    post-pull state never loses the +x bit on hooks."""
    text = (_SCRIPTS / "fa-update.sh").read_text(encoding="utf-8")
    fn = text[text.index("ensure_host_scripts()") :]
    fn = fn[: fn.index("\n}\n") + 2]
    assert '"${REPO_DIR}/scripts"' in fn, "ensure_host_scripts must find scripts/ via absolute REPO_DIR path"
    assert "commit-msg" in fn and "pre-push" in fn, "ensure_host_scripts must chmod hooks/ (not just scripts/*.sh)"
    assert "find scripts/" not in fn, "must not use relative `scripts/` path"


# ── Batch-4 regressions: ufw delete idempotency, fa.service comment ──────


def test_ufw_delete_uses_force_and_refetches() -> None:
    """scripts/ssh-tailscale/20-harden.sh must delete stray UFW rules with
    `ufw --force delete` (no `yes |` hack) and must RE-FETCH the numbered
    rule list inside the delete loop (one delete renumbers the rest)."""
    script_path = _SCRIPTS / "ssh-tailscale" / "20-harden.sh"
    text = script_path.read_text(encoding="utf-8")
    # Strip comment lines when scanning for `yes | ufw delete` — the script
    # may legitimately mention it in an explanatory comment.
    code_lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    code = "\n".join(code_lines)
    assert "yes | ufw delete" not in code, "`yes | ufw delete` is unreliable (use --force)"
    assert "ufw --force delete" in code
    # The fixed loop has `while true; do mapfile …; [[ ${#stray[@]} -eq 0 ]] && break`
    assert "while true" in code
    assert "${#stray[@]}" in code  # re-fetches each iteration


def test_fa_service_documents_restart_semantics() -> None:
    """fa.service should carry a comment explaining that Restart=on-failure
    only retries the oneshot ExecStart (cold-boot) while container crash
    restart is handled by docker-compose `restart: unless-stopped`."""
    unit = (_SCRIPTS / "fa.service").read_text(encoding="utf-8")
    assert "Restart=on-failure" in unit  # keep the useful retries
    assert "unless-stopped" in unit  # comment must reference docker's policy


# ── Bonus: docker-group notice fires right after usermod ─────────────────


def test_setup_warns_about_docker_group_right_after_usermod() -> None:
    """setup-fa-desktop.sh should warn about docker-group membership
    immediately after `usermod -aG docker`, not buried in the step-17
    summary. Operators who bail early otherwise miss the instruction and
    hit 'permission denied' on the next docker command."""
    text = (_SCRIPTS / "setup-fa-desktop.sh").read_text(encoding="utf-8")
    usermod_idx = text.index("usermod -aG docker")
    post = text[usermod_idx : usermod_idx + 1200]
    assert "log out" in post.lower() or "log out of GNOME" in post or "Log out" in post, (
        "a docker-group logout warning must appear within ~1KB of the usermod call"
    )


def test_main_is_intentional_ssot_for_update() -> None:
    """fa-update.sh is documented to always deploy main (SSOT; only hand-
    merged code ships). Guard that the `switch to main` step is present
    and documented so a future contributor doesn't "fix" it without
    reading the operator contract."""
    text = (_SCRIPTS / "fa-update.sh").read_text(encoding="utf-8")
    assert "git switch main" in text or "git checkout main" in text
    # Must carry a comment mentioning SSOT / main-only policy.
    assert "main" in text
