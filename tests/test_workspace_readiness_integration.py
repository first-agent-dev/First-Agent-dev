"""C2/C3 integrated authority for a clean managed S1-S6 candidate."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from fa.hygiene.hooks._util import HOOK_NAMES
from fa.session.workspace import provision_git_workspace

REPO_ROOT = Path(__file__).resolve().parents[1]
_CANONICAL_PUSH = "git@github.com:first-agent-dev/First-Agent-dev.git"


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = _run(["git", *args], cwd=repo, env=env)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _bootstrap_log_tail(workspace: Path, *, limit_bytes: int = 8192) -> str:
    """Return a bounded tail of the structured readiness log for failure diagnosis."""
    log_path = workspace / ".fa" / "bootstrap.log"
    if log_path.is_symlink() or not log_path.is_file():
        return "<readiness log unavailable>"
    with log_path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        handle.seek(max(0, handle.tell() - limit_bytes))
        return handle.read(limit_bytes).decode("utf-8", errors="replace")


def _require_execution_host_preflight() -> None:
    """Require explicit W4 host selection and the same real Docker/cgroup preflight."""
    from tests.integration._host import (
        ExecutionHostPreflightError,
        load_and_probe_execution_host,
        require_execution_host_opt_in,
    )

    try:
        require_execution_host_opt_in(os.environ.get("FA_REQUIRE_EXECUTION_HOST"))
        load_and_probe_execution_host()
    except ExecutionHostPreflightError as error:
        pytest.fail(str(error), pytrace=False)


def _candidate_ignore(directory: str, names: list[str]) -> set[str]:
    if Path(directory).name == ".fa":
        return set(names) - {"dependency_contract.toml"}
    excluded = {
        ".coverage",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "coverage.json",
        "coverage.xml",
        "dist",
        "mutants",
        "node_modules",
    }
    return set(names) & excluded


@pytest.mark.execution_host
def test_clean_candidate_real_readiness_commit_and_local_publication(request: pytest.FixtureRequest) -> None:
    """C2/C3 W4 T22: real Git→readiness→hooks→commit→local-push host path; no skip/fallback."""

    _require_execution_host_preflight()
    missing_tools = [command for command in ("uv", "git", "bash") if shutil.which(command) is None]
    assert not missing_tools, f"Ubuntu/POSIX readiness acceptance requires installed tools: {missing_tools}"

    scratch = Path(tempfile.mkdtemp(prefix=".tmp-s65-integration-", dir=REPO_ROOT.parent))
    request.addfinalizer(lambda: shutil.rmtree(scratch, ignore_errors=True))
    source = scratch / "candidate source"
    shutil.copytree(REPO_ROOT, source, ignore=_candidate_ignore)
    assert not (source / ".venv").exists(), "the candidate source must not inherit the checkout venv"
    _git(source, "init", "--quiet", "--initial-branch=main")
    _git(source, "config", "user.name", "Candidate Builder")
    _git(source, "config", "user.email", "candidate@example.invalid")
    _git(source, "add", "-f", "-A")
    _git(source, "commit", "--quiet", "-m", "candidate baseline")
    _git(source, "remote", "add", "origin", _CANONICAL_PUSH)
    source_head = _git(source, "rev-parse", "HEAD")
    source_status = _git(source, "status", "--porcelain=v1", "--untracked-files=all")

    target = scratch / "managed target"
    state = provision_git_workspace(source, target, "s65-integration", _CANONICAL_PUSH)
    assert not (target / ".venv").exists(), "the managed clone must be prepared from a genuinely empty venv state"

    assert state.branch == "agent/s65-integration"
    assert state.fetch_url == source.resolve().as_uri()
    assert state.push_url == _CANONICAL_PUSH
    assert state.author_name == "First Agent"
    assert state.author_email == "agent@first-agent.local"
    assert _git(target, "status", "--porcelain=v1", "--untracked-files=all") == ""

    env = os.environ.copy()
    env["PRE_COMMIT_HOME"] = str(scratch / "pre-commit-home")
    ready = _run(
        [
            sys.executable,
            str(target / "scripts" / "bootstrap" / "workspace.py"),
            "ensure",
            "--workspace",
            str(target),
        ],
        cwd=target,
        env=env,
        timeout=1200,
    )
    project_python = target / ".venv" / "bin" / "python"
    probed_python = (
        _run(
            [
                str(project_python),
                "-I",
                "-c",
                "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
            ],
            cwd=target,
            timeout=30,
        )
        if project_python.is_file()
        else None
    )
    project_python_version_text: str | None = None
    if probed_python is not None and probed_python.returncode == 0:
        project_python_version_text = probed_python.stdout.strip()
        request.node.user_properties.append(("target_project_python", project_python_version_text))
    python_diagnostic = (
        "<target .venv Python was not created>"
        if probed_python is None
        else (
            f"exit={probed_python.returncode}, version={project_python_version_text!r}, "
            f"stderr={probed_python.stderr[-2048:]!r}"
        )
    )
    readiness_diagnostics = (
        f"stdout:\n{ready.stdout}\nstderr:\n{ready.stderr}\n"
        f"target project Python: {python_diagnostic}\n"
        f"structured bootstrap log tail (max 8 KiB):\n{_bootstrap_log_tail(target)}"
    )
    assert ready.returncode == 0, readiness_diagnostics
    ready_payload = json.loads(ready.stdout)
    assert ready_payload["status"] == "ready", readiness_diagnostics
    assert ready_payload["reason_code"] == "ready_repaired", readiness_diagnostics
    assert ready_payload["repaired"] is True, readiness_diagnostics
    assert project_python.is_file(), readiness_diagnostics
    assert probed_python is not None
    assert probed_python.returncode == 0, probed_python.stdout + probed_python.stderr
    assert project_python_version_text is not None
    project_python_version = tuple(int(part) for part in project_python_version_text.split("."))
    assert project_python_version >= (3, 13), (
        f"uv sync selected an unsupported project interpreter; expected >=3.13, got {project_python_version_text!r}"
    )
    for name in HOOK_NAMES:
        assert os.access(target / ".git" / "hooks" / name, os.X_OK)

    clean_env = env.copy()
    empty_home = scratch / "empty-home"
    empty_home.mkdir()
    clean_env["HOME"] = str(empty_home)
    for name in (
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
        "VIRTUAL_ENV",
        "VIRTUAL_ENV_PROMPT",
        "CONDA_PREFIX",
        "UV_PROJECT_ENVIRONMENT",
        "UV_PYTHON",
        "PYTHONHOME",
    ):
        clean_env.pop(name, None)
    (target / "integration-proof.txt").write_text("ready\n", encoding="utf-8")
    _git(target, "add", "integration-proof.txt", env=clean_env)
    committed = _run(
        ["git", "commit", "-m", "test: integrated managed commit"],
        cwd=target,
        env=clean_env,
        timeout=600,
    )
    assert committed.returncode == 0, committed.stdout + committed.stderr

    publication = scratch / "publication.git"
    initialized = _run(["git", "init", "--quiet", "--bare", str(publication)], cwd=scratch)
    assert initialized.returncode == 0, initialized.stderr
    push_env = clean_env.copy()
    push_env.update(
        {
            "FA_HOOK_SKIP_FULL_CHECK": "1",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": f"url.{publication.resolve().as_uri()}.insteadOf",
            "GIT_CONFIG_VALUE_0": _CANONICAL_PUSH,
        }
    )
    pushed = _run(
        ["git", "push", "origin", "agent/s65-integration"],
        cwd=target,
        env=push_env,
        timeout=180,
    )
    assert pushed.returncode == 0, pushed.stdout + pushed.stderr
    target_head = _git(target, "rev-parse", "HEAD")
    published_head = _git(publication, "rev-parse", "refs/heads/agent/s65-integration")
    assert published_head == target_head
    assert _git(source, "rev-parse", "HEAD") == source_head
    assert _git(source, "status", "--porcelain=v1", "--untracked-files=all") == source_status
