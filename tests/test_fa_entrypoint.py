from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from fa.hygiene.hooks._util import HOOK_NAMES
from tests._capabilities import requires_posix_paths

_ENTRYPOINT = Path(__file__).resolve().parents[1] / "scripts" / "fa-entrypoint.sh"
_CANONICAL_PUSH_URL = "git@github.com:first-agent-dev/First-Agent-dev.git"


def _git(cwd: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *arguments],
        check=check,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _add_source_remote(repo: Path, push_url: str = _CANONICAL_PUSH_URL) -> None:
    _git(repo, "remote", "add", "origin", push_url)


def _render_entrypoint(repo: Path, sessions: Path, destination: Path) -> None:
    original = _ENTRYPOINT.read_text(encoding="utf-8")
    modified = original.replace('"/repo/.git"', f'"{repo}/.git"')
    modified = modified.replace("file:///repo", repo.resolve().as_uri())
    modified = modified.replace("/repo ", f"{repo} ")
    modified = modified.replace('"/repo"', f'"{repo}"')
    modified = modified.replace('"/sessions/', f'"{sessions}/')
    destination.write_text(modified, encoding="utf-8")
    destination.chmod(0o755)


def _add_readiness_sources(repo: Path) -> None:
    (repo / "knowledge").mkdir()
    (repo / "knowledge" / "llms.txt").write_text("workspace marker\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "entrypoint-fixture"\nrequires-python = ">=3.13"\n',
        encoding="utf-8",
    )
    (repo / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (repo / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
    hook_source = repo / "src" / "fa" / "hygiene" / "hooks"
    hook_source.mkdir(parents=True)
    for name in HOOK_NAMES:
        script = hook_source / name
        script.write_text(f"#!/bin/sh\necho entrypoint-{name}\n", encoding="utf-8")
        script.chmod(0o755)
    (hook_source / "install.py").write_text("# fingerprint installer\n", encoding="utf-8")
    (hook_source / "status.py").write_text("# fingerprint status\n", encoding="utf-8")


def _make_source_repository(
    repo: Path,
    *,
    push_url: str = _CANONICAL_PUSH_URL,
    readiness_sources: bool = False,
) -> None:
    repo.mkdir()
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(repo)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    (repo / "src" / "fa").mkdir(parents=True)
    (repo / "src" / "fa" / "__init__.py").write_text("", encoding="utf-8")
    if readiness_sources:
        _add_readiness_sources(repo)
    _git(repo, "add", ".")
    commit_environment = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "dummy@first-agent.local",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "dummy@first-agent.local",
    }
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "init"],
        check=True,
        capture_output=True,
        text=True,
        env=commit_environment,
        timeout=30,
    )
    _add_source_remote(repo, push_url)


def _base_env(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    status = tmp_path / "entrypoint-status.txt"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "FA_WORKSPACE": str(workspace),
            "FA_STATUS_FILE": str(status),
            "PATH": f"{bin_dir}:{env.get('PATH', '')}",
            "PYTHONPATH": "",
            "PYTHON": sys.executable,
            # Disable the image-venv PATH prepend so the test's `fa` stub in
            # bin_dir wins. Without this, when the suite runs INSIDE the agent
            # container the real /opt/fa-venv/bin/fa shadows the stub and the
            # auto-run assertions never see the stub's call log.
            "FA_VENV_BIN": "",
        }
    )
    return env, status, bin_dir


def _write_readiness_uv_stub(bin_dir: Path) -> None:
    uv = bin_dir / "uv"
    uv.write_text(
        f"""#!{sys.executable}
import os
from pathlib import Path
import sys

if sys.argv[1:] == ["--version"]:
    print("uv entrypoint-test")
    raise SystemExit(0)
if "--check" in sys.argv[1:]:
    raise SystemExit(0)
bin_dir = Path.cwd() / ".venv" / "bin"
bin_dir.mkdir(parents=True, exist_ok=True)
python = bin_dir / "python"
if python.exists() or python.is_symlink():
    python.unlink()
python.symlink_to(Path(os.environ["FA_TEST_PYTHON"]))
precommit = bin_dir / "pre-commit"
precommit.write_text("#!" + os.environ["FA_TEST_PYTHON"] + "\\nraise SystemExit(0)\\n", encoding="utf-8")
precommit.chmod(0o755)
""",
        encoding="utf-8",
    )
    uv.chmod(0o755)


def _write_python_readiness_stub(
    bin_dir: Path,
    *,
    active_file: Path,
    called_file: Path,
    readiness_rc: int,
) -> Path:
    wrapper = bin_dir / "python-readiness-stub"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'if [[ "${1:-}" == "-m" && "${2:-}" == "fa.workspace_bootstrap" && "${3:-}" == "ensure" ]]; then\n'
        f"  [[ ! -e {str(active_file)!r} ]] || exit 93\n"
        f"  printf 'called\\n' > {str(called_file)!r}\n"
        f"  printf '[WORKSPACE_BOOTSTRAP] forced test degradation\\n' >&2\n"
        f"  exit {readiness_rc}\n"
        "fi\n"
        'exec "$FA_TEST_REAL_PYTHON" "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    return wrapper


def _write_fa_stub(bin_dir: Path, env: dict[str, str], exit_code: int = 0) -> Path:
    """Create a stub ``fa`` that logs calls and exits with *exit_code*.

    Two mechanisms ensure the stub wins in every environment:

    1. **File stub** in *bin_dir* (prepended to ``$PATH`` by ``_base_env``).
       Works outside Docker where ``/tmp`` allows ``exec()``.

    2. **Bash-function export** via ``BASH_FUNC_fa%%`` in *env*.
       Inside the Docker container ``/tmp`` is a ``noexec`` tmpfs — the kernel
       blocks ``exec()`` on scripts there and bash silently falls through to
       the real ``fa`` in the image venv.  An exported bash function is
       resolved *before* any ``$PATH`` lookup and never calls ``exec()``,
       so it works regardless of mount flags.
    """
    calls = bin_dir / "fa-calls.txt"

    # — mechanism 1: file on disk (PATH-based) —
    stub = bin_dir / "fa"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        'printf \'%q \' "$@" >> "$FA_STUB_CALLS"\n'
        "printf '\\\\n' >> \"$FA_STUB_CALLS\"\n"
        f"exit {exit_code}\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)

    # — mechanism 2: exported bash function (noexec-safe) —
    env["BASH_FUNC_fa%%"] = (
        f'() {{ printf \'%q \' "$@" >> "$FA_STUB_CALLS"; printf \'\\n\' >> "$FA_STUB_CALLS"; exit {exit_code}; }}'
    )

    return calls


def _wait_for_status(status: Path, expected: str, proc: subprocess.Popen[str]) -> str:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if status.exists():
            text = status.read_text(encoding="utf-8")
            if expected in text:
                return text
        if proc.poll() is not None:
            break
        time.sleep(0.05)
    if status.exists():
        pytest.fail(f"status file never contained {expected!r}: {status.read_text()}")
    pytest.fail(f"status file was not written; proc exit={proc.poll()}")


def _terminate(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)


def test_entrypoint_standby_does_not_autorun_when_only_task_is_set(tmp_path: Path) -> None:
    env, status, bin_dir = _base_env(tmp_path)
    calls = _write_fa_stub(bin_dir, env)
    env.update({"FA_TASK": "do work", "FA_STUB_CALLS": str(calls)})

    proc = subprocess.Popen(["bash", str(_ENTRYPOINT)], env=env, text=True)
    try:
        text = _wait_for_status(status, "status=STANDBY", proc)
    finally:
        _terminate(proc)

    assert "FA_AUTO_RUN is not enabled" in text
    assert not calls.exists()


def test_entrypoint_autorun_runs_child_once_and_writes_success(tmp_path: Path) -> None:
    env, status, bin_dir = _base_env(tmp_path)
    calls = _write_fa_stub(bin_dir, env, exit_code=0)
    env.update(
        {
            "FA_AUTO_RUN": "1",
            "FA_TASK": "implement the plan",
            "FA_ROLE": "planner",
            "FA_MAX_TURNS": "7",
            "FA_SESSION_ID": "docker-test-session",
            "FA_RUN_ID": "docker-test-run",
            "FA_RESUME": "1",
            "FA_STUB_CALLS": str(calls),
        }
    )

    proc = subprocess.Popen(["bash", str(_ENTRYPOINT)], env=env, text=True)
    try:
        text = _wait_for_status(status, "status=SUCCESS", proc)
    finally:
        _terminate(proc)

    assert "exit_code=0" in text
    assert "role=planner" in text
    assert "run_id=docker-test-run" in text
    call_text = calls.read_text(encoding="utf-8")
    assert "run" in call_text
    assert "--task" in call_text
    assert "--workspace" in call_text
    assert "--role" in call_text
    assert "--max-turns" in call_text
    assert "--resume" in call_text


def test_entrypoint_invalid_blank_task_writes_status_without_child(tmp_path: Path) -> None:
    env, status, bin_dir = _base_env(tmp_path)
    calls = _write_fa_stub(bin_dir, env)
    env.update({"FA_AUTO_RUN": "1", "FA_TASK": " \n\t", "FA_STUB_CALLS": str(calls)})

    proc = subprocess.Popen(["bash", str(_ENTRYPOINT)], env=env, text=True)
    try:
        text = _wait_for_status(status, "status=INVALID_CONFIG", proc)
    finally:
        _terminate(proc)

    assert "Task is empty" in text
    assert not calls.exists()


def test_entrypoint_autorun_accepts_task_file_inside_workspace(tmp_path: Path) -> None:
    env, status, bin_dir = _base_env(tmp_path)
    calls = _write_fa_stub(bin_dir, env, exit_code=0)
    task_file = tmp_path / "workspace" / "tasks" / "plan.md"
    task_file.parent.mkdir()
    task_file.write_text("S1. inspect\nS2. implement\n", encoding="utf-8")
    env.update(
        {
            "FA_AUTO_RUN": "1",
            "FA_TASK_FILE": "tasks/plan.md",
            "FA_STUB_CALLS": str(calls),
        }
    )

    proc = subprocess.Popen(["bash", str(_ENTRYPOINT)], env=env, text=True)
    try:
        text = _wait_for_status(status, "status=SUCCESS", proc)
    finally:
        _terminate(proc)

    assert "task_source=file:" in text
    assert "task_sha256=" in text
    assert "S1. inspect" in text
    assert calls.exists()


@requires_posix_paths
def test_entrypoint_task_file_must_stay_inside_workspace(tmp_path: Path) -> None:
    env, status, bin_dir = _base_env(tmp_path)
    calls = _write_fa_stub(bin_dir, env)
    outside = tmp_path / "outside-task.md"
    outside.write_text("do work\n", encoding="utf-8")
    env.update(
        {
            "FA_AUTO_RUN": "1",
            "FA_TASK_FILE": str(outside),
            "FA_STUB_CALLS": str(calls),
        }
    )

    proc = subprocess.Popen(["bash", str(_ENTRYPOINT)], env=env, text=True)
    try:
        text = _wait_for_status(status, "status=INVALID_CONFIG", proc)
    finally:
        _terminate(proc)

    assert "inside workspace" in text
    assert not calls.exists()


@requires_posix_paths
def test_entrypoint_creates_session_clone(tmp_path: Path) -> None:
    env, status, _bin_dir = _base_env(tmp_path)
    # Session-clone tests must NOT set FA_WORKSPACE — its absence is what
    # triggers the session-clone path in the entrypoint.
    env.pop("FA_WORKSPACE", None)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, check=True)
    (repo_dir / "src" / "fa").mkdir(parents=True)
    (repo_dir / "src" / "fa" / "__init__.py").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    git_env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "dummy@first-agent.local",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "dummy@first-agent.local",
    }
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, check=True, env=git_env)
    _add_source_remote(repo_dir)

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()

    test_entrypoint = tmp_path / "fa-entrypoint-test.sh"
    _render_entrypoint(repo_dir, sessions_dir, test_entrypoint)

    env.update({"FA_SESSION_ID": "test-session-123", "FA_AUTO_RUN": "0"})

    proc = subprocess.Popen(["bash", str(test_entrypoint)], env=env, text=True)
    try:
        _wait_for_status(status, "status=STANDBY", proc)
    finally:
        _terminate(proc)

    session_workspace = sessions_dir / "test-session-123"
    assert session_workspace.exists()
    assert (session_workspace / ".git").exists()

    active_file = sessions_dir / ".active"
    assert active_file.exists()
    assert active_file.read_text(encoding="utf-8").strip() == str(session_workspace)
    assert _git(session_workspace, "branch", "--show-current").stdout.strip() == "agent/test-session-123"
    assert _git(session_workspace, "remote", "get-url", "origin").stdout.strip() == repo_dir.resolve().as_uri()
    assert _git(session_workspace, "remote", "get-url", "--push", "origin").stdout.strip() == _CANONICAL_PUSH_URL
    assert _git(session_workspace, "config", "--local", "--get", "user.name").stdout.strip() == "First Agent"
    assert _git(session_workspace, "config", "--local", "--get", "user.email").stdout.strip() == (
        "agent@first-agent.local"
    )

    commit_environment = os.environ.copy()
    for name in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        commit_environment.pop(name, None)
    empty_home = tmp_path / "empty-home"
    empty_home.mkdir()
    commit_environment["HOME"] = str(empty_home)
    (session_workspace / "first-agent-commit.txt").write_text("ready\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(session_workspace), "add", "first-agent-commit.txt"],
        check=True,
        env=commit_environment,
        timeout=30,
    )
    subprocess.run(
        ["git", "-C", str(session_workspace), "commit", "-m", "first managed commit"],
        check=True,
        capture_output=True,
        text=True,
        env=commit_environment,
        timeout=30,
    )


def test_entrypoint_failed_clone_does_not_launch_override_or_child(tmp_path: Path) -> None:
    """C2 negative proof: clone failure transitions to INVALID_CONFIG standby."""
    env, status, bin_dir = _base_env(tmp_path)
    calls = _write_fa_stub(bin_dir, env)
    env.pop("FA_WORKSPACE", None)
    env.update({"FA_SESSION_ID": "failed-clone", "FA_AUTO_RUN": "1", "FA_TASK": "work", "FA_STUB_CALLS": str(calls)})

    fake_repo = tmp_path / "fake-repo"
    fake_repo.mkdir()
    (fake_repo / ".git").mkdir()
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    test_entrypoint = tmp_path / "fa-entrypoint-failed-clone.sh"
    _render_entrypoint(fake_repo, sessions_dir, test_entrypoint)

    proc = subprocess.Popen(["bash", str(test_entrypoint)], env=env, text=True)
    try:
        text = _wait_for_status(status, "status=INVALID_CONFIG", proc)
    finally:
        _terminate(proc)

    assert "clone/checkout failed" in text
    assert not calls.exists()
    assert not (sessions_dir / "failed-clone").exists()


@requires_posix_paths
def test_entrypoint_resumes_session_clone(tmp_path: Path) -> None:
    env, status, _bin_dir = _base_env(tmp_path)
    env.pop("FA_WORKSPACE", None)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, check=True)
    (repo_dir / "test.txt").write_text("hello", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    git_env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "dummy@first-agent.local",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "dummy@first-agent.local",
    }
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, check=True, env=git_env)
    _add_source_remote(repo_dir)

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()

    session_workspace = sessions_dir / "test-session-existing"
    subprocess.run(
        ["git", "clone", repo_dir.resolve().as_uri(), str(session_workspace)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    _git(session_workspace, "switch", "-c", "agent/test-session-existing")
    uncommitted = session_workspace / "operator-work.txt"
    uncommitted.write_text("preserve\n", encoding="utf-8")

    test_entrypoint = tmp_path / "fa-entrypoint-test.sh"
    _render_entrypoint(repo_dir, sessions_dir, test_entrypoint)

    env.update({"FA_SESSION_ID": "test-session-existing", "FA_AUTO_RUN": "0"})

    proc = subprocess.Popen(["bash", str(test_entrypoint)], env=env, text=True)
    try:
        _wait_for_status(status, "status=STANDBY", proc)
    finally:
        _terminate(proc)

    active_file = sessions_dir / ".active"
    assert active_file.exists()
    assert active_file.read_text(encoding="utf-8").strip() == str(session_workspace)
    assert _git(session_workspace, "branch", "--show-current").stdout.strip() == "agent/test-session-existing"
    assert _git(session_workspace, "remote", "get-url", "origin").stdout.strip() == repo_dir.resolve().as_uri()
    assert _git(session_workspace, "remote", "get-url", "--push", "origin").stdout.strip() == _CANONICAL_PUSH_URL
    assert _git(session_workspace, "config", "--local", "--get", "user.name").stdout.strip() == "First Agent"
    assert _git(session_workspace, "config", "--local", "--get", "user.email").stdout.strip() == (
        "agent@first-agent.local"
    )
    assert uncommitted.read_text(encoding="utf-8") == "preserve\n"


def test_entrypoint_git_invalid_session_id_fails_before_clone_or_child(tmp_path: Path) -> None:
    """class=C3 root=entrypoint path=P1 kill-check=remove check-ref-format producer."""

    env, status, bin_dir = _base_env(tmp_path)
    calls = _write_fa_stub(bin_dir, env)
    env.pop("FA_WORKSPACE", None)
    repo = tmp_path / "repo"
    _make_source_repository(repo)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    entrypoint = tmp_path / "entrypoint.sh"
    _render_entrypoint(repo, sessions, entrypoint)
    env.update(
        {
            "FA_SESSION_ID": "a..b",
            "FA_AUTO_RUN": "1",
            "FA_TASK": "must not run",
            "FA_STUB_CALLS": str(calls),
        }
    )

    proc = subprocess.Popen(["bash", str(entrypoint)], env=env, text=True)
    try:
        text = _wait_for_status(status, "status=INVALID_CONFIG", proc)
    finally:
        _terminate(proc)

    assert "valid Git branch" in text
    assert not (sessions / "a..b").exists()
    assert not (sessions / ".active").exists()
    assert not calls.exists()


def test_entrypoint_fresh_configuration_failure_removes_clone_before_publication(tmp_path: Path) -> None:
    """class=C3 root=entrypoint path=P1 kill-check=move adapter after active publication."""

    env, status, bin_dir = _base_env(tmp_path)
    calls = _write_fa_stub(bin_dir, env)
    env.pop("FA_WORKSPACE", None)
    repo = tmp_path / "repo"
    _make_source_repository(repo, push_url=(tmp_path / "local-push.git").resolve().as_uri())
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    entrypoint = tmp_path / "entrypoint.sh"
    _render_entrypoint(repo, sessions, entrypoint)
    env.update(
        {
            "FA_SESSION_ID": "bad-remote",
            "FA_AUTO_RUN": "1",
            "FA_TASK": "must not run",
            "FA_STUB_CALLS": str(calls),
        }
    )

    proc = subprocess.Popen(["bash", str(entrypoint)], env=env, text=True)
    try:
        text = _wait_for_status(status, "status=INVALID_CONFIG", proc)
    finally:
        _terminate(proc)

    assert "managed Git configuration failed" in text
    assert not (sessions / "bad-remote").exists()
    assert not (sessions / ".active").exists()
    assert not calls.exists()


def test_entrypoint_resumed_configuration_failure_preserves_workspace(tmp_path: Path) -> None:
    """class=C3 root=entrypoint path=P2 kill-check=delete resumed workspace on adapter failure."""

    env, status, _bin_dir = _base_env(tmp_path)
    env.pop("FA_WORKSPACE", None)
    repo = tmp_path / "repo"
    _make_source_repository(repo)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    workspace = sessions / "resume-mismatch"
    subprocess.run(
        ["git", "clone", repo.resolve().as_uri(), str(workspace)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    sentinel = workspace / "preserve.txt"
    sentinel.write_text("keep\n", encoding="utf-8")
    entrypoint = tmp_path / "entrypoint.sh"
    _render_entrypoint(repo, sessions, entrypoint)
    env.update({"FA_SESSION_ID": "resume-mismatch", "FA_AUTO_RUN": "0"})

    proc = subprocess.Popen(["bash", str(entrypoint)], env=env, text=True)
    try:
        text = _wait_for_status(status, "status=INVALID_CONFIG", proc)
    finally:
        _terminate(proc)

    assert "managed Git configuration failed" in text
    assert workspace.is_dir()
    assert sentinel.read_text(encoding="utf-8") == "keep\n"
    assert _git(workspace, "branch", "--show-current").stdout.strip() == "main"
    assert not (sessions / ".active").exists()


def test_entrypoint_preserves_custom_pushurl_and_repairs_identity(tmp_path: Path) -> None:
    """class=C2/C3 root=entrypoint path=P14 kill-check=remove adapter custom path."""

    env, status, _bin_dir = _base_env(tmp_path)
    env.pop("FA_WORKSPACE", None)
    repo = tmp_path / "repo"
    _make_source_repository(repo)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    workspace = sessions / "custom-remote"
    subprocess.run(
        ["git", "clone", repo.resolve().as_uri(), str(workspace)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    _git(workspace, "switch", "-c", "agent/custom-remote")
    custom_push = "git@github.com:operator/custom.git"
    _git(workspace, "remote", "set-url", "--push", "origin", custom_push)
    entrypoint = tmp_path / "entrypoint.sh"
    _render_entrypoint(repo, sessions, entrypoint)
    env.update({"FA_SESSION_ID": "custom-remote", "FA_AUTO_RUN": "0"})

    proc = subprocess.Popen(["bash", str(entrypoint)], env=env, text=True)
    try:
        _wait_for_status(status, "status=STANDBY", proc)
    finally:
        _terminate(proc)

    assert (sessions / ".active").read_text(encoding="utf-8").strip() == str(workspace)
    assert _git(workspace, "remote", "get-url", "--push", "origin").stdout.strip() == custom_push
    assert _git(workspace, "config", "--local", "--get", "user.name").stdout.strip() == "First Agent"
    assert _git(workspace, "config", "--local", "--get", "user.email").stdout.strip() == ("agent@first-agent.local")


def test_entrypoint_push_url_override_reaches_fresh_workspace(tmp_path: Path) -> None:
    """class=C2 root=entrypoint matrix=M8 kill-check=drop adapter environment override."""

    env, status, _bin_dir = _base_env(tmp_path)
    env.pop("FA_WORKSPACE", None)
    repo = tmp_path / "repo"
    _make_source_repository(repo)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    entrypoint = tmp_path / "entrypoint.sh"
    _render_entrypoint(repo, sessions, entrypoint)
    env.update(
        {
            "FA_SESSION_ID": "override-remote",
            "FA_AUTO_RUN": "0",
            "FA_REPO_PUSH_URL": "https://github.com/fork-owner/fork-repo",
        }
    )

    proc = subprocess.Popen(["bash", str(entrypoint)], env=env, text=True)
    try:
        _wait_for_status(status, "status=STANDBY", proc)
    finally:
        _terminate(proc)

    workspace = sessions / "override-remote"
    assert _git(workspace, "remote", "get-url", "--push", "origin").stdout.strip() == (
        "git@github.com:fork-owner/fork-repo.git"
    )


def test_entrypoint_readiness_runs_before_active_and_command_override(tmp_path: Path) -> None:
    """C2 P1: shipped shell readiness producer precedes publication and exec."""

    env, _status, bin_dir = _base_env(tmp_path)
    env.pop("FA_WORKSPACE", None)
    repo = tmp_path / "repo"
    _make_source_repository(repo)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    entrypoint = tmp_path / "entrypoint.sh"
    _render_entrypoint(repo, sessions, entrypoint)
    active = sessions / ".active"
    called = tmp_path / "readiness-called"
    python_stub = _write_python_readiness_stub(
        bin_dir,
        active_file=active,
        called_file=called,
        readiness_rc=0,
    )
    env.update(
        {
            "FA_SESSION_ID": "readiness-order",
            "PYTHON": str(python_stub),
            "FA_TEST_REAL_PYTHON": sys.executable,
            "READINESS_CALLED": str(called),
            "ACTIVE_FILE": str(active),
        }
    )

    completed = subprocess.run(
        [
            "bash",
            str(entrypoint),
            "bash",
            "-c",
            'test -f "$READINESS_CALLED" && test -f "$ACTIVE_FILE" && printf ordered',
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )

    assert completed.returncode == 0
    assert completed.stdout.endswith("ordered")
    assert called.read_text(encoding="utf-8") == "called\n"
    assert active.read_text(encoding="utf-8").strip() == str(sessions / "readiness-order")


def test_entrypoint_real_readiness_creates_artifacts_before_standby(tmp_path: Path) -> None:
    """C2 P1/T8: real engine prepares environment, seats, marker, and cache sentinel."""

    env, status, bin_dir = _base_env(tmp_path)
    env.pop("FA_WORKSPACE", None)
    repo = tmp_path / "repo"
    _make_source_repository(repo, readiness_sources=True)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    entrypoint = tmp_path / "entrypoint.sh"
    _render_entrypoint(repo, sessions, entrypoint)
    _write_readiness_uv_stub(bin_dir)
    precommit_home = tmp_path / "pre-commit-cache"
    env.update(
        {
            "FA_SESSION_ID": "real-readiness",
            "FA_AUTO_RUN": "0",
            "FA_TEST_PYTHON": sys.executable,
            "PRE_COMMIT_HOME": str(precommit_home),
        }
    )

    proc = subprocess.Popen(["bash", str(entrypoint)], env=env, text=True)
    try:
        _wait_for_status(status, "status=STANDBY", proc)
    finally:
        _terminate(proc)

    workspace = sessions / "real-readiness"
    marker = json.loads((workspace / ".fa" / "ready-state.json").read_text(encoding="utf-8"))
    assert marker["state"] == "ready"
    assert marker["schema"] == 2
    assert (workspace / ".venv" / "bin" / "python").is_file()
    assert (precommit_home / ".fa-ready" / marker["fingerprint"]).read_text(encoding="utf-8") == (
        marker["fingerprint"] + "\n"
    )
    for name in HOOK_NAMES:
        seat = workspace / ".git" / "hooks" / name
        source = workspace / "src" / "fa" / "hygiene" / "hooks" / name
        assert seat.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
        assert os.access(seat, os.X_OK)


def test_entrypoint_readiness_degradation_warns_and_continues(tmp_path: Path) -> None:
    """C2/C3 P1: bootstrap rc 75 is warn/fail-open, not command suppression."""

    env, _status, bin_dir = _base_env(tmp_path)
    env.pop("FA_WORKSPACE", None)
    repo = tmp_path / "repo"
    _make_source_repository(repo)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    entrypoint = tmp_path / "entrypoint.sh"
    _render_entrypoint(repo, sessions, entrypoint)
    active = sessions / ".active"
    called = tmp_path / "degraded-called"
    python_stub = _write_python_readiness_stub(
        bin_dir,
        active_file=active,
        called_file=called,
        readiness_rc=75,
    )
    env.update(
        {
            "FA_SESSION_ID": "degraded-readiness",
            "PYTHON": str(python_stub),
            "FA_TEST_REAL_PYTHON": sys.executable,
        }
    )

    completed = subprocess.run(
        ["bash", str(entrypoint), "bash", "-c", "printf continued"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )

    assert completed.returncode == 0
    assert completed.stdout.endswith("continued")
    assert "forced test degradation" in completed.stderr
    assert "readiness degraded (rc=75); continuing" in completed.stdout
    assert active.is_file()


@requires_posix_paths
def test_entrypoint_command_override_executes_inside_session_clone(tmp_path: Path) -> None:
    env, _status, _bin_dir = _base_env(tmp_path)
    env.pop("FA_WORKSPACE", None)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, check=True)
    (repo_dir / "src" / "fa").mkdir(parents=True)
    (repo_dir / "src" / "fa" / "__init__.py").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    git_env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "dummy@first-agent.local",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "dummy@first-agent.local",
    }
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, check=True, env=git_env)
    _add_source_remote(repo_dir)

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()

    test_entrypoint = tmp_path / "fa-entrypoint-test.sh"
    _render_entrypoint(repo_dir, sessions_dir, test_entrypoint)

    env.update(
        {
            "FA_SESSION_ID": "test-override",
        }
    )

    # Run with command override to print the working directory
    proc = subprocess.Popen(
        ["bash", str(test_entrypoint), "bash", "-c", "pwd"],
        env=env,
        stdout=subprocess.PIPE,
        text=True,
    )

    stdout, _ = proc.communicate(timeout=5)
    assert proc.returncode == 0

    session_workspace = sessions_dir / "test-override"
    assert session_workspace.exists()

    # stdout should contain the session directory because it executes there
    assert str(session_workspace) in stdout
