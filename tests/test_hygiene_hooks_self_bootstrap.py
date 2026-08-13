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
        ("COMMIT_MSG", "hook"),
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
