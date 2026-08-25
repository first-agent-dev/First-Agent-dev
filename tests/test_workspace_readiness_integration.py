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


@pytest.mark.skipif(os.name == "nt", reason="real hook shell and local Git transport require POSIX")
@pytest.mark.skipif(
    any(shutil.which(command) is None for command in ("uv", "git", "bash")),
    reason="real uv, git, and bash are required",
)
def test_clean_candidate_real_readiness_commit_and_local_publication(request: pytest.FixtureRequest) -> None:
    """C2/C3 T22: real Git→readiness→hooks→commit→local-push path; producer removals fail state or rc."""

    scratch = Path(tempfile.mkdtemp(prefix=".tmp-s65-integration-", dir=REPO_ROOT.parent))
    request.addfinalizer(lambda: shutil.rmtree(scratch, ignore_errors=True))
    source = scratch / "candidate source"
    shutil.copytree(REPO_ROOT, source, ignore=_candidate_ignore)
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
    assert ready.returncode == 0, ready.stderr
    ready_payload = json.loads(ready.stdout)
    assert ready_payload["status"] == "ready"
    assert ready_payload["reason_code"] == "ready_repaired"
    assert (target / ".venv" / "bin" / "python").is_file()
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
