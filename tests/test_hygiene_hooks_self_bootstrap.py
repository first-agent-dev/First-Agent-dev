"""C1/C3 authority for S5 git-hook readiness self-bootstrap."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK_DIR = REPO_ROOT / "src" / "fa" / "hygiene" / "hooks"
_BEGIN = "# BEGIN FA WORKSPACE READINESS"
_END = "# END FA WORKSPACE READINESS"


@dataclass(frozen=True)
class HookCase:
    name: str
    args: tuple[str, ...]
    stdin: str
    normal_argv: tuple[str, ...]


CASES = (
    HookCase(
        "pre-commit",
        (),
        "",
        ("run", "--no-sync", "pre-commit", "run", "--hook-stage", "pre-commit"),
    ),
    HookCase(
        "pre-push",
        (),
        "refs/heads/main deadbeef refs/heads/main cafebabe\n",
        ("run", "--no-sync", "just", "check-deep"),
    ),
    HookCase(
        "prepare-commit-msg",
        ("COMMIT_MSG",),
        "",
        ("run", "--no-sync", "python", "-m", "fa.hygiene", "prepare", "COMMIT_MSG"),
    ),
    HookCase(
        "commit-msg",
        ("COMMIT_MSG",),
        "",
        ("run", "--no-sync", "python", "-m", "fa.hygiene", "validate", "COMMIT_MSG"),
    ),
)


def _write_executable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _make_repo(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    repo = tmp_path / "repo with spaces"
    repo.mkdir()
    subprocess.run(["git", "init", "--quiet", "--initial-branch=main"], cwd=repo, check=True)
    (repo / "COMMIT_MSG").write_text("message\n", encoding="utf-8")
    sequence = tmp_path / "sequence.jsonl"
    uv_records = tmp_path / "uv-records.jsonl"
    wrapper = repo / "scripts" / "bootstrap" / "workspace.py"
    _write_executable(
        wrapper,
        f"#!{sys.executable}\n"
        "from __future__ import annotations\n"
        "import json, os, sys, time\n"
        "from pathlib import Path\n"
        "with Path(os.environ['FA_TEST_SEQUENCE']).open('a', encoding='utf-8') as handle:\n"
        "    handle.write(json.dumps({'phase': 'bootstrap', 'argv': sys.argv[1:]}) + '\\n')\n"
        "time.sleep(float(os.environ.get('FA_TEST_BOOTSTRAP_SLEEP', '0')))\n"
        "rc = int(os.environ.get('FA_TEST_BOOTSTRAP_RC', '0'))\n"
        "print(json.dumps({'status': 'ready' if rc == 0 else 'degraded_environment', "
        "'log_path': str(Path.cwd() / '.fa' / 'bootstrap.log')}))\n"
        "if rc:\n"
        "    print('[WORKSPACE_BOOTSTRAP] fake degraded; log=' + "
        "str(Path.cwd() / '.fa' / 'bootstrap.log'), file=sys.stderr)\n"
        "raise SystemExit(rc)\n",
    )
    fakebin = tmp_path / "bin"
    _write_executable(
        fakebin / "uv",
        f"#!{sys.executable}\n"
        "from __future__ import annotations\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "payload = {'argv': sys.argv[1:], 'stdin': sys.stdin.read()}\n"
        "with Path(os.environ['FA_TEST_UV_RECORDS']).open('a', encoding='utf-8') as handle:\n"
        "    handle.write(json.dumps(payload) + '\\n')\n"
        "with Path(os.environ['FA_TEST_SEQUENCE']).open('a', encoding='utf-8') as handle:\n"
        "    handle.write(json.dumps({'phase': 'normal', **payload}) + '\\n')\n"
        "raise SystemExit(int(os.environ.get('FA_TEST_NORMAL_RC', '0')))\n",
    )
    _write_executable(fakebin / "just", "#!/usr/bin/env bash\nexit 0\n")
    env = os.environ.copy()
    env.update(
        {
            "PATH": os.pathsep.join((str(fakebin), env.get("PATH", ""))),
            "FA_TEST_SEQUENCE": str(sequence),
            "FA_TEST_UV_RECORDS": str(uv_records),
            "FA_TEST_BOOTSTRAP_RC": "0",
            "FA_TEST_NORMAL_RC": "0",
        }
    )
    return repo, env


def _run(case: HookCase, repo: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(HOOK_DIR / case.name), *case.args],
        cwd=repo,
        env=env,
        input=case.stdin,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _rows(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _uv_argvs(path: Path) -> list[list[str]]:
    result: list[list[str]] = []
    for row in _rows(path):
        raw = row.get("argv")
        assert isinstance(raw, list)
        assert all(isinstance(item, str) for item in raw)
        result.append(raw)
    return result


def _git_process(
    repo: Path,
    *args: str,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _make_real_git_hook_repo(tmp_path: Path) -> tuple[Path, dict[str, str], Path]:
    """Create a real Git root whose hook tools delegate to checked-out FA code."""

    repo = tmp_path / "real git hook repo"
    repo.mkdir()
    assert _git_process(repo, "init", "--quiet", "--initial-branch=main").returncode == 0
    assert _git_process(repo, "config", "user.name", "First Agent").returncode == 0
    assert _git_process(repo, "config", "user.email", "agent@first-agent.local").returncode == 0

    (repo / "knowledge").mkdir()
    (repo / "knowledge" / "llms.txt").write_text("marker\n", encoding="utf-8")
    wrapper = repo / "scripts" / "bootstrap" / "workspace.py"
    _write_executable(wrapper, f'#!{sys.executable}\nprint(\'{{"status":"ready"}}\')\n')
    (repo / "baseline.txt").write_text("baseline\n", encoding="utf-8")
    assert _git_process(repo, "add", "-A").returncode == 0
    assert _git_process(repo, "commit", "--quiet", "-m", "baseline").returncode == 0

    hooks_dir = repo / ".git" / "hooks"
    for name in ("prepare-commit-msg", "commit-msg"):
        shutil.copy2(HOOK_DIR / name, hooks_dir / name)
        (hooks_dir / name).chmod(0o755)

    uv_records = tmp_path / "real-git-uv.jsonl"
    fakebin = tmp_path / "real-git-bin"
    _write_executable(
        fakebin / "uv",
        f"#!{sys.executable}\n"
        "from __future__ import annotations\n"
        "import json, os, subprocess, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "with Path(os.environ['FA_TEST_UV_RECORDS']).open('a', encoding='utf-8') as handle:\n"
        "    handle.write(json.dumps({'argv': args}) + '\\n')\n"
        "if args[:2] != ['run', '--no-sync']:\n"
        "    raise SystemExit(97)\n"
        "command = args[2:]\n"
        "if command and command[0] == 'python':\n"
        "    command = [sys.executable, *command[1:]]\n"
        "raise SystemExit(subprocess.run(command, env=os.environ, check=False).returncode)\n",
    )

    env = os.environ.copy()
    env["PATH"] = os.pathsep.join((str(fakebin), env.get("PATH", "")))
    env["PYTHONPATH"] = os.pathsep.join((str(REPO_ROOT / "src"), env.get("PYTHONPATH", "")))
    env["FA_TEST_UV_RECORDS"] = str(uv_records)
    for name in (
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
    ):
        env.pop(name, None)
    return repo, env, uv_records


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_ready_bootstrap_precedes_normal_body_and_preserves_contract(case: HookCase, tmp_path: Path) -> None:
    repo, env = _make_repo(tmp_path)

    result = _run(case, repo, env)

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    sequence = _rows(Path(env["FA_TEST_SEQUENCE"]))
    assert [row["phase"] for row in sequence] == ["bootstrap", "normal"]
    assert sequence[0]["argv"] == ["ensure", "--workspace", str(repo)]
    records = _rows(Path(env["FA_TEST_UV_RECORDS"]))
    assert records == [{"argv": list(case.normal_argv), "stdin": case.stdin}]


@pytest.mark.parametrize("source", ["message", "template", "squash", "merge", "commit"])
def test_prepare_generated_or_authored_sources_skip_template_injection(source: str, tmp_path: Path) -> None:
    """C1: declared Git source values bootstrap, then retain compatibility skip."""

    repo, env = _make_repo(tmp_path)
    case = HookCase(
        "prepare-commit-msg",
        ("COMMIT_MSG", source),
        "",
        ("run", "--no-sync", "python", "-m", "fa.hygiene", "prepare", "COMMIT_MSG"),
    )

    result = _run(case, repo, env)

    assert result.returncode == 0, result.stderr
    assert [row["phase"] for row in _rows(Path(env["FA_TEST_SEQUENCE"]))] == ["bootstrap"]
    assert not Path(env["FA_TEST_UV_RECORDS"]).exists()


def test_real_git_editor_commit_reaches_prepare_and_validate(tmp_path: Path) -> None:
    """root=git commit class=C2 claim=CT14 path=P25 matrix=M18.

    producer-kill-check: restoring the empty-source skip in the installed
    prepare-commit-msg seat leaves the editor without generated headers and
    makes this real Git commit fail.
    """

    repo, env, uv_records = _make_real_git_hook_repo(tmp_path)
    observed = tmp_path / "editor-observed.txt"
    editor = tmp_path / "git-editor"
    _write_executable(
        editor,
        f"#!{sys.executable}\n"
        "from __future__ import annotations\n"
        "import os, sys\n"
        "from pathlib import Path\n"
        "message = Path(sys.argv[1])\n"
        "prepared = message.read_text(encoding='utf-8')\n"
        "if 'INTENT: CHORE' not in prepared or 'INVARIANT: <fill me' not in prepared:\n"
        "    print('prepared PR-intent headers missing', file=sys.stderr)\n"
        "    raise SystemExit(91)\n"
        "Path(os.environ['FA_TEST_EDITOR_OBSERVED']).write_text(prepared, encoding='utf-8')\n"
        "message.write_text(\n"
        "    'test: actual Git prepare producer\\n\\n'\n"
        "    'INTENT: CHORE\\n'\n"
        "    'INVARIANT: n/a\\n\\n'\n"
        "    'AI-Session: actual-git-hook-test\\n',\n"
        "    encoding='utf-8',\n"
        ")\n",
    )
    env["GIT_EDITOR"] = str(editor)
    env["FA_TEST_EDITOR_OBSERVED"] = str(observed)
    proof = repo / "s9-disposable-proof.txt"
    proof.write_text("proof\n", encoding="utf-8")
    assert _git_process(repo, "add", proof.name, env=env).returncode == 0

    result = _git_process(repo, "commit", env=env)

    assert result.returncode == 0, result.stdout + result.stderr
    prepared = observed.read_text(encoding="utf-8")
    assert "INTENT: CHORE" in prepared
    assert "INVARIANT: <fill me" in prepared
    calls = _uv_argvs(uv_records)
    prepare_calls = [argv for argv in calls if "prepare" in argv]
    validate_calls = [argv for argv in calls if "validate" in argv]
    assert len(prepare_calls) == 1
    assert len(validate_calls) == 1
    assert prepare_calls[0][:5] == ["run", "--no-sync", "python", "-m", "fa.hygiene"]
    assert validate_calls[0][:5] == ["run", "--no-sync", "python", "-m", "fa.hygiene"]
    message = _git_process(repo, "log", "-1", "--pretty=%B", env=env).stdout
    assert message.startswith("test: actual Git prepare producer\n\nINTENT: CHORE\nINVARIANT: n/a\n")
    assert "AI-Session: actual-git-hook-test" in message
    changed = _git_process(
        repo,
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "-r",
        "HEAD",
        env=env,
    ).stdout.splitlines()
    assert changed == [proof.name]
    assert _git_process(repo, "status", "--porcelain=v1", env=env).stdout == ""


@pytest.mark.parametrize("message_mode", ["dash-m", "dash-F", "dash-F-stdin"])
def test_real_git_authored_message_sources_skip_prepare_but_validate(
    message_mode: str,
    tmp_path: Path,
) -> None:
    """C2 P26: authored message paths skip injection but still run commit-msg."""

    repo, env, uv_records = _make_real_git_hook_repo(tmp_path)
    proof = repo / f"proof-{message_mode}.txt"
    proof.write_text("proof\n", encoding="utf-8")
    assert _git_process(repo, "add", proof.name, env=env).returncode == 0
    expected_subject = f"test: {message_mode}"
    input_text: str | None = None
    if message_mode == "dash-m":
        args = ("commit", "-m", expected_subject)
    elif message_mode == "dash-F":
        message_file = tmp_path / "message.txt"
        message_file.write_text(expected_subject + "\n", encoding="utf-8")
        args = ("commit", "-F", str(message_file))
    else:
        args = ("commit", "-F", "-")
        input_text = expected_subject + "\n"

    result = _git_process(repo, *args, env=env, input_text=input_text)

    assert result.returncode == 0, result.stdout + result.stderr
    calls = _uv_argvs(uv_records)
    assert [argv for argv in calls if "prepare" in argv] == []
    assert len([argv for argv in calls if "validate" in argv]) == 1
    assert _git_process(repo, "log", "-1", "--pretty=%s", env=env).stdout.strip() == expected_subject
    assert _git_process(repo, "status", "--porcelain=v1", env=env).stdout == ""


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_degraded_bootstrap_warns_and_allows_without_normal_body(case: HookCase, tmp_path: Path) -> None:
    repo, env = _make_repo(tmp_path)
    env["FA_TEST_BOOTSTRAP_RC"] = "75"

    result = _run(case, repo, env)

    assert result.returncode == 0
    assert "[WORKSPACE_BOOTSTRAP] fake degraded" in result.stderr
    assert result.stderr.count("hook readiness unavailable (rc=75)") == 1
    assert f"log={repo / '.fa' / 'bootstrap.log'}" in result.stderr
    assert not Path(env["FA_TEST_UV_RECORDS"]).exists()
    assert [row["phase"] for row in _rows(Path(env["FA_TEST_SEQUENCE"]))] == ["bootstrap"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_normal_gate_failure_remains_blocking_after_readiness(case: HookCase, tmp_path: Path) -> None:
    repo, env = _make_repo(tmp_path)
    env["FA_TEST_NORMAL_RC"] = "7"

    result = _run(case, repo, env)

    assert result.returncode == 7
    assert [row["phase"] for row in _rows(Path(env["FA_TEST_SEQUENCE"]))] == ["bootstrap", "normal"]


def test_missing_wrapper_is_generic_warn_allow_and_never_runs_gate(tmp_path: Path) -> None:
    repo, env = _make_repo(tmp_path)
    (repo / "scripts" / "bootstrap" / "workspace.py").unlink()

    result = _run(next(case for case in CASES if case.name == "pre-push"), repo, env)

    assert result.returncode == 0
    assert "hook readiness unavailable (rc=2)" in result.stderr
    assert f"log={repo / '.fa' / 'bootstrap.log'}" in result.stderr
    assert not Path(env["FA_TEST_UV_RECORDS"]).exists()


def test_wrapper_command_not_found_is_warn_allow_and_never_runs_gate(tmp_path: Path) -> None:
    repo, env = _make_repo(tmp_path)
    fakebin = Path(env["PATH"].split(os.pathsep, 1)[0])
    _write_executable(fakebin / "python3", "#!/usr/bin/env bash\nexit 127\n")

    result = _run(next(case for case in CASES if case.name == "pre-push"), repo, env)

    assert result.returncode == 0
    assert "hook readiness unavailable (rc=127)" in result.stderr
    assert f"log={repo / '.fa' / 'bootstrap.log'}" in result.stderr
    assert not Path(env["FA_TEST_UV_RECORDS"]).exists()
    assert _rows(Path(env["FA_TEST_SEQUENCE"])) == []


def test_pre_push_explicit_skip_still_bootstraps_first(tmp_path: Path) -> None:
    repo, env = _make_repo(tmp_path)
    env["FA_HOOK_SKIP_FULL_CHECK"] = "1"

    result = _run(next(case for case in CASES if case.name == "pre-push"), repo, env)

    assert result.returncode == 0
    assert "skipping uv run --no-sync just check-deep" in result.stderr
    assert [row["phase"] for row in _rows(Path(env["FA_TEST_SEQUENCE"]))] == ["bootstrap"]
    assert not Path(env["FA_TEST_UV_RECORDS"]).exists()


def test_all_hook_preludes_are_identical_and_non_recursive() -> None:
    blocks: list[str] = []
    for case in CASES:
        text = (HOOK_DIR / case.name).read_text(encoding="utf-8")
        assert text.count(_BEGIN) == 1
        assert text.count(_END) == 1
        block = text.split(_BEGIN, 1)[1].split(_END, 1)[0]
        blocks.append(block)
        assert 'exec "$0"' not in text
        assert "git rev-parse --show-toplevel 2>/dev/null" in block
        assert "uv run " not in text.replace("uv run --no-sync ", "")
    assert len(set(blocks)) == 1


def test_real_wrapper_children_cannot_consume_pre_push_stdin(tmp_path: Path) -> None:
    """C1/C3 T23: real wrapper children see EOF; normal pre-push receives exact input."""

    repo = tmp_path / "real wrapper repo"
    repo.mkdir()
    subprocess.run(["git", "init", "--quiet", "--initial-branch=main"], cwd=repo, check=True)
    (repo / "knowledge").mkdir()
    (repo / "knowledge" / "llms.txt").write_text("marker\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='stdin-proof'\nversion='0'\n", encoding="utf-8")
    (repo / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (repo / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
    shutil.copytree(REPO_ROOT / "src" / "fa", repo / "src" / "fa")
    wrapper = repo / "scripts" / "bootstrap" / "workspace.py"
    wrapper.parent.mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "scripts" / "bootstrap" / "workspace.py", wrapper)

    core_records = tmp_path / "core-stdin.jsonl"
    normal_record = tmp_path / "normal-stdin.json"
    fakebin = tmp_path / "real-wrapper-bin"
    fakebin.mkdir()
    venv_child = tmp_path / "venv-child-probe"
    _write_executable(
        venv_child,
        f"#!{sys.executable}\n"
        "from __future__ import annotations\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "label = 'venv-python' if Path(sys.argv[0]).name == 'python' else 'pre-commit'\n"
        "payload = {'argv': [label, *sys.argv[1:]], 'stdin': sys.stdin.read()}\n"
        "with Path(os.environ['FA_TEST_CORE_STDIN']).open('a', encoding='utf-8') as handle:\n"
        "    handle.write(json.dumps(payload) + '\\n')\n"
        f"if label == 'venv-python': print('{sys.version_info.major}.{sys.version_info.minor}')\n",
    )
    child_script = (
        f"#!{sys.executable}\n"
        "from __future__ import annotations\n"
        "import json, os, shutil, stat, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "payload = {'argv': args, 'stdin': sys.stdin.read()}\n"
        "if args == ['run', '--no-sync', 'just', 'check-deep']:\n"
        "    Path(os.environ['FA_TEST_NORMAL_STDIN']).write_text(json.dumps(payload), encoding='utf-8')\n"
        "    raise SystemExit(0)\n"
        "with Path(os.environ['FA_TEST_CORE_STDIN']).open('a', encoding='utf-8') as handle:\n"
        "    handle.write(json.dumps(payload) + '\\n')\n"
        "if args == ['--version']:\n"
        "    print('uv 0.test')\n"
        "elif args and args[0] == 'sync':\n"
        "    bindir = Path.cwd() / '.venv' / 'bin'\n"
        "    bindir.mkdir(parents=True, exist_ok=True)\n"
        "    source = Path(os.environ['FA_TEST_VENV_CHILD'])\n"
        "    for path in (bindir / 'python', bindir / 'pre-commit'):\n"
        "        shutil.copy2(source, path)\n"
        "        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)\n"
    )
    _write_executable(fakebin / "uv", child_script)
    _write_executable(fakebin / "just", "#!/usr/bin/env bash\nexit 0\n")
    payload = "refs/heads/main a refs/heads/main b\nrefs/heads/topic c refs/heads/topic d\n"
    env = os.environ.copy()
    env.update(
        {
            "PATH": os.pathsep.join((str(fakebin), env.get("PATH", ""))),
            "PRE_COMMIT_HOME": str(tmp_path / "pre-commit-home"),
            "FA_TEST_CORE_STDIN": str(core_records),
            "FA_TEST_NORMAL_STDIN": str(normal_record),
            "FA_TEST_VENV_CHILD": str(venv_child),
        }
    )

    result = subprocess.run(
        ["bash", str(repo / "src" / "fa" / "hygiene" / "hooks" / "pre-push")],
        cwd=repo,
        env=env,
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    core = _rows(core_records)
    assert core
    assert all(row["stdin"] == "" for row in core)
    assert json.loads(normal_record.read_text(encoding="utf-8")) == {
        "argv": ["run", "--no-sync", "just", "check-deep"],
        "stdin": payload,
    }
