from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest

_ENTRYPOINT = Path(__file__).resolve().parents[1] / "scripts" / "fa-entrypoint.sh"


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
            # Disable the image-venv PATH prepend so the test's `fa` stub in
            # bin_dir wins. Without this, when the suite runs INSIDE the agent
            # container the real /opt/fa-venv/bin/fa shadows the stub and the
            # auto-run assertions never see the stub's call log.
            "FA_VENV_BIN": "",
        }
    )
    return env, status, bin_dir


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
        "() { "
        'printf \'%q \' "$@" >> "$FA_STUB_CALLS"; '
        "printf '\\n' >> \"$FA_STUB_CALLS\"; "
        f"exit {exit_code};"
        " }"
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

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()

    test_entrypoint = tmp_path / "fa-entrypoint-test.sh"
    original = _ENTRYPOINT.read_text(encoding="utf-8")
    modified = original.replace('"/repo/.git"', f'"{repo_dir}/.git"')
    modified = modified.replace("file:///repo", f"file://{repo_dir}")
    modified = modified.replace("/repo ", f"{repo_dir} ")
    modified = modified.replace('"/repo"', f'"{repo_dir}"')
    modified = modified.replace('"/sessions/', f'"{sessions_dir}/')
    test_entrypoint.write_text(modified, encoding="utf-8")
    test_entrypoint.chmod(0o755)

    env.update({"FA_RUN_ID": "test-session-123", "FA_AUTO_RUN": "0"})

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

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()

    session_workspace = sessions_dir / "test-session-existing"
    subprocess.run(["git", "clone", str(repo_dir), str(session_workspace)], check=True)

    test_entrypoint = tmp_path / "fa-entrypoint-test.sh"
    original = _ENTRYPOINT.read_text(encoding="utf-8")
    modified = original.replace('"/repo/.git"', f'"{repo_dir}/.git"')
    modified = modified.replace("file:///repo", f"file://{repo_dir}")
    modified = modified.replace("/repo ", f"{repo_dir} ")
    modified = modified.replace('"/repo"', f'"{repo_dir}"')
    modified = modified.replace('"/sessions/', f'"{sessions_dir}/')
    test_entrypoint.write_text(modified, encoding="utf-8")
    test_entrypoint.chmod(0o755)

    env.update({"FA_RUN_ID": "test-session-existing", "FA_AUTO_RUN": "0"})

    proc = subprocess.Popen(["bash", str(test_entrypoint)], env=env, text=True)
    try:
        _wait_for_status(status, "status=STANDBY", proc)
    finally:
        _terminate(proc)

    active_file = sessions_dir / ".active"
    assert active_file.exists()
    assert active_file.read_text(encoding="utf-8").strip() == str(session_workspace)


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

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()

    test_entrypoint = tmp_path / "fa-entrypoint-test.sh"
    original = _ENTRYPOINT.read_text(encoding="utf-8")
    modified = original.replace('"/repo/.git"', f'"{repo_dir}/.git"')
    modified = modified.replace("file:///repo", f"file://{repo_dir}")
    modified = modified.replace("/repo ", f"{repo_dir} ")
    modified = modified.replace('"/repo"', f'"{repo_dir}"')
    modified = modified.replace('"/sessions/', f'"{sessions_dir}/')
    test_entrypoint.write_text(modified, encoding="utf-8")
    test_entrypoint.chmod(0o755)

    env.update(
        {
            "FA_RUN_ID": "test-override",
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
