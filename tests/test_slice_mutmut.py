"""C0/C1/C3/C4 authority for the S3.5 slice mutation runner.

The suite treats mutmut/Pyrefly as process boundaries, boots the shipped runner
in synthetic repositories, and includes one tiny real-tool integration on POSIX.
Tests are always pytest oracles; no test path may become mutation source.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import time
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pytest

from scripts import _git_diff
from scripts.run_slice_mutmut import SliceRequest, SliceResult

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "run_slice_mutmut.py"
TARGETED = REPO_ROOT / "scripts" / "run_targeted_mutmut.py"
PYPROJECT = REPO_ROOT / "pyproject.toml"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tests.yml"
CODEOWNERS = REPO_ROOT / ".github" / "CODEOWNERS"
PROTECTED_PATHS = REPO_ROOT / "scripts" / "check_protected_paths.py"


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _base_pyproject() -> str:
    return """\
[tool.pytest.ini_options]
pythonpath = ["src"]

[tool.pyrefly]
python-version = "3.13.0"
search-path = ["src"]

[tool.mutmut]
source_paths = ["src/old.py"]
pytest_add_cli_args_test_selection = ["tests/test_old.py"]
timeout_multiplier = 15.0
timeout_constant = 1.0
"""


def _make_repo(tmp_path: Path, *, exact_test: bool = True) -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "src").mkdir()
    (repo / "tests").mkdir()
    shutil.copy2(RUNNER, repo / "scripts" / RUNNER.name)
    (repo / "src" / "probe.py").write_text(
        'def answer() -> str:\n    value: str = "foo"\n    return value\n',
        encoding="utf-8",
    )
    assertion = 'answer() == "foo"' if exact_test else "answer()"
    (repo / "tests" / "test_probe.py").write_text(
        f"from probe import answer\n\ndef test_answer() -> None:\n    assert {assertion}\n",
        encoding="utf-8",
    )
    (repo / "tests" / "conftest.py").write_text("# shared oracle support\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text(_base_pyproject(), encoding="utf-8")
    return repo


_FAKE_MUTMUT = r"""#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

args = sys.argv[1:]
if args == ["--version"]:
    print(os.environ.get("FAKE_MUTMUT_VERSION", "mutmut, version 3.6.0"))
    raise SystemExit(0)
if args and args[0] == "run":
    if os.environ.get("FAKE_REQUIRE_PYREFLY_ON_PATH") == "1" and shutil.which("pyrefly") is None:
        raise SystemExit(12)
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["tool"]["mutmut"]
    record = os.environ.get("FAKE_MUTMUT_RECORD")
    if record:
        Path(record).write_text(json.dumps(config, sort_keys=True), encoding="utf-8")
    child_pid_path = os.environ.get("FAKE_MUTMUT_CHILD_PID")
    if child_pid_path:
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        Path(child_pid_path).write_text(str(child.pid), encoding="utf-8")
    sleep = float(os.environ.get("FAKE_MUTMUT_SLEEP", "0"))
    if sleep:
        time.sleep(sleep)
    Path("mutants").mkdir(exist_ok=True)
    raise SystemExit(int(os.environ.get("FAKE_MUTMUT_RUN_RC", "0")))
if args == ["results"]:
    print(os.environ.get("FAKE_MUTMUT_RESULTS", ""), end="")
    raise SystemExit(int(os.environ.get("FAKE_MUTMUT_RESULTS_RC", "0")))
if args == ["export-cicd-stats"]:
    Path("mutants").mkdir(exist_ok=True)
    stats = json.loads(os.environ["FAKE_MUTMUT_STATS"])
    Path("mutants/mutmut-cicd-stats.json").write_text(json.dumps(stats), encoding="utf-8")
    raise SystemExit(int(os.environ.get("FAKE_MUTMUT_EXPORT_RC", "0")))
if args and args[0] == "show" and len(args) == 2:
    print(f"--- original\n+++ {args[1]}\n@@\n-return 1\n+return 2")
    raise SystemExit(int(os.environ.get("FAKE_MUTMUT_SHOW_RC", "0")))
raise SystemExit(f"unexpected mutmut argv: {args!r}")
"""

_FAKE_PYREFLY = r"""#!/usr/bin/env python3
import sys
if sys.argv[1:] == ["--version"]:
    print("pyrefly 1.1.1")
    raise SystemExit(0)
raise SystemExit(f"unexpected pyrefly argv: {sys.argv[1:]!r}")
"""


def _fake_tools(tmp_path: Path) -> tuple[Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    mutmut = bin_dir / "mutmut"
    pyrefly = bin_dir / "pyrefly"
    _write_executable(mutmut, _FAKE_MUTMUT)
    _write_executable(pyrefly, _FAKE_PYREFLY)
    return bin_dir, mutmut


def _run_runner(
    repo: Path,
    tmp_path: Path,
    *,
    env_overrides: Mapping[str, str],
    extra_args: tuple[str, ...] = (),
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    bin_dir, _ = _fake_tools(tmp_path)
    env = os.environ.copy()
    env.update(env_overrides)
    env["PATH"] = os.pathsep.join((str(bin_dir), env.get("PATH", "")))
    return subprocess.run(
        [
            sys.executable,
            "scripts/run_slice_mutmut.py",
            "--source",
            "src/probe.py",
            "--test",
            "tests/test_probe.py",
            "--tmp-root",
            str(tmp_path / "scratch"),
            "--result-json",
            "mutants/result.json",
            "--diff-report",
            "mutants/diffs.md",
            "--max-children",
            "1",
            "--timeout-seconds",
            "20",
            *extra_args,
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _read_result(repo: Path) -> dict[str, Any]:
    raw = json.loads((repo / "mutants" / "result.json").read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return cast(dict[str, Any], raw)


def _stats(*, killed: int, survived: int, total: int) -> str:
    return json.dumps(
        {
            "killed": killed,
            "survived": survived,
            "total": total,
            "no_tests": 0,
            "skipped": 0,
            "suspicious": 0,
            "timeout": 0,
            "check_was_interrupted_by_user": 0,
            "segfault": 0,
        }
    )


def test_runner_turns_zero_rc_survivor_into_action_required_and_preserves_inputs(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    pyproject_before = (repo / "pyproject.toml").read_bytes()
    source_before = (repo / "src" / "probe.py").read_bytes()
    test_before = (repo / "tests" / "test_probe.py").read_bytes()
    record = tmp_path / "mutmut-config.json"

    run = _run_runner(
        repo,
        tmp_path,
        env_overrides={
            "FAKE_MUTMUT_RECORD": str(record),
            "FAKE_MUTMUT_RESULTS": "    probe.x_answer__mutmut_1: survived\n",
            "FAKE_MUTMUT_STATS": _stats(killed=0, survived=1, total=1),
        },
    )

    assert run.returncode == 1, run.stderr
    result = _read_result(repo)
    assert result["completed"] is True
    assert result["verdict"] == "action_required"
    assert result["counts"] == {
        "total": 1,
        "killed": 0,
        "type_invalid": 0,
        "survived": 1,
        "no_tests": 0,
        "timeout": 0,
        "suspicious": 0,
        "skipped": 0,
        "interrupted": 0,
        "segfault": 0,
        "not_checked": 0,
    }
    config = json.loads(record.read_text(encoding="utf-8"))
    assert config["source_paths"] == ["src/probe.py"]
    assert config["pytest_add_cli_args_test_selection"] == ["tests/test_probe.py"]
    assert config["type_check_command"] == [
        "pyrefly",
        "check",
        "src/probe.py",
        "--output-format=json",
        "--summary=none",
        "--progress-bar=no",
    ]
    assert "tests/test_probe.py" not in config["source_paths"]
    assert "probe.x_answer__mutmut_1" in (repo / "mutants" / "diffs.md").read_text(encoding="utf-8")
    assert (repo / "pyproject.toml").read_bytes() == pyproject_before
    assert (repo / "src" / "probe.py").read_bytes() == source_before
    assert (repo / "tests" / "test_probe.py").read_bytes() == test_before
    assert not list((tmp_path / "scratch").glob("mutmut-*"))


def test_runner_counts_type_invalid_separately_and_omits_it_from_diff_report(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    run = _run_runner(
        repo,
        tmp_path,
        env_overrides={
            "FAKE_MUTMUT_RESULTS": "    probe.x_answer__mutmut_1: caught by type check\n",
            "FAKE_MUTMUT_STATS": _stats(killed=2, survived=0, total=3),
        },
    )

    assert run.returncode == 0, run.stderr
    result = _read_result(repo)
    assert result["verdict"] == "clean"
    assert result["counts"]["killed"] == 2
    assert result["counts"]["type_invalid"] == 1
    assert result["counts"]["total"] == 3
    assert result["mutants"] == [{"name": "probe.x_answer__mutmut_1", "status": "type_invalid", "diff_anchor": None}]
    assert "probe.x_answer" not in (repo / "mutants" / "diffs.md").read_text(encoding="utf-8")


def test_runner_rejects_count_mismatch_as_infrastructure_failure(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    run = _run_runner(
        repo,
        tmp_path,
        env_overrides={
            "FAKE_MUTMUT_RESULTS": "    probe.x_answer__mutmut_1: survived\n",
            "FAKE_MUTMUT_STATS": _stats(killed=1, survived=1, total=9),
        },
    )

    assert run.returncode == 3
    result = _read_result(repo)
    assert result["completed"] is False
    assert result["verdict"] == "infrastructure_failure"
    assert result["reason"] == "result_identity_failed"


@pytest.mark.parametrize(
    "extra_args",
    [
        ("--source", "tests/test_probe.py"),
        ("--test", "src/probe.py"),
        ("--source", "src"),
    ],
)
def test_runner_rejects_wrong_role_or_overlapping_paths_before_mutmut(
    tmp_path: Path, extra_args: tuple[str, ...]
) -> None:
    repo = _make_repo(tmp_path)
    record = tmp_path / "must-not-exist.json"
    run = _run_runner(
        repo,
        tmp_path,
        env_overrides={
            "FAKE_MUTMUT_RECORD": str(record),
            "FAKE_MUTMUT_RESULTS": "",
            "FAKE_MUTMUT_STATS": _stats(killed=0, survived=0, total=0),
        },
        extra_args=extra_args,
    )

    assert run.returncode == 2
    assert not record.exists()
    assert not (repo / "mutants" / "result.json").exists()


def test_runner_rejects_wrong_mutmut_version_before_staging(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    record = tmp_path / "must-not-exist.json"
    run = _run_runner(
        repo,
        tmp_path,
        env_overrides={
            "FAKE_MUTMUT_VERSION": "mutmut, version 3.7.0",
            "FAKE_MUTMUT_RECORD": str(record),
            "FAKE_MUTMUT_RESULTS": "",
            "FAKE_MUTMUT_STATS": _stats(killed=0, survived=0, total=0),
        },
    )

    assert run.returncode == 3
    assert "3.6.0" in run.stderr
    assert not record.exists()


def test_runner_prepends_fallback_tool_directories_for_mutmut_type_check(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    bin_dir, _ = _fake_tools(tmp_path)
    venv_bin = repo / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    for name in ("mutmut", "pyrefly"):
        shutil.copy2(bin_dir / name, venv_bin / name)
    env = os.environ.copy()
    env.update(
        {
            "PATH": "/usr/bin:/bin",
            "FAKE_REQUIRE_PYREFLY_ON_PATH": "1",
            "FAKE_MUTMUT_RESULTS": "    probe.x_answer__mutmut_1: caught by type check\n",
            "FAKE_MUTMUT_STATS": _stats(killed=2, survived=0, total=3),
        }
    )
    run = subprocess.run(
        [
            sys.executable,
            "scripts/run_slice_mutmut.py",
            "--source",
            "src/probe.py",
            "--test",
            "tests/test_probe.py",
            "--tmp-root",
            str(tmp_path / "scratch"),
            "--result-json",
            "mutants/result.json",
            "--diff-report",
            "mutants/diffs.md",
            "--max-children",
            "1",
            "--timeout-seconds",
            "20",
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    assert run.returncode == 0, run.stderr
    assert _read_result(repo)["counts"]["type_invalid"] == 1


def test_runner_timeout_is_infrastructure_failure_and_cleans_stage(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    run = _run_runner(
        repo,
        tmp_path,
        env_overrides={
            "FAKE_MUTMUT_SLEEP": "10",
            "FAKE_MUTMUT_RESULTS": "",
            "FAKE_MUTMUT_STATS": _stats(killed=1, survived=0, total=1),
        },
        extra_args=("--timeout-seconds", "1"),
        timeout=20,
    )

    assert run.returncode == 3
    assert _read_result(repo)["reason"] == "mutation_timeout"
    assert not list((tmp_path / "scratch").glob("mutmut-*"))


def _process_is_running(pid: int) -> bool:
    proc_stat = Path(f"/proc/{pid}/stat")
    if proc_stat.is_file():
        fields = proc_stat.read_text(encoding="utf-8").split()
        return len(fields) > 2 and fields[2] != "Z"
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_runner_nonzero_parent_reaps_process_group_before_stage_cleanup(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    child_pid_path = tmp_path / "child.pid"
    run = _run_runner(
        repo,
        tmp_path,
        env_overrides={
            "FAKE_MUTMUT_CHILD_PID": str(child_pid_path),
            "FAKE_MUTMUT_RUN_RC": "9",
            "FAKE_MUTMUT_RESULTS": "",
            "FAKE_MUTMUT_STATS": _stats(killed=1, survived=0, total=1),
        },
    )

    assert run.returncode == 3
    assert _read_result(repo)["reason"] == "mutmut_run_failed"
    child_pid = int(child_pid_path.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 5
    while _process_is_running(child_pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _process_is_running(child_pid)
    assert not list((tmp_path / "scratch").glob("mutmut-*"))


def test_runner_unknown_status_is_infrastructure_failure(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    run = _run_runner(
        repo,
        tmp_path,
        env_overrides={
            "FAKE_MUTMUT_RESULTS": "    probe.x_answer__mutmut_1: magical\n",
            "FAKE_MUTMUT_STATS": _stats(killed=0, survived=1, total=1),
        },
    )

    assert run.returncode == 3
    assert _read_result(repo)["reason"] == "result_parse_failed"


def test_runner_rejects_symlink_source_before_mutmut(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    link = repo / "src" / "linked.py"
    link.symlink_to(repo / "src" / "probe.py")
    record = tmp_path / "must-not-exist.json"
    run = _run_runner(
        repo,
        tmp_path,
        env_overrides={
            "FAKE_MUTMUT_RECORD": str(record),
            "FAKE_MUTMUT_RESULTS": "",
            "FAKE_MUTMUT_STATS": _stats(killed=0, survived=0, total=0),
        },
        extra_args=("--source", "src/linked.py"),
    )

    assert run.returncode == 2
    assert not record.exists()


@pytest.mark.skipif(os.name != "posix", reason="mutmut 3 requires fork/POSIX")
@pytest.mark.skipif(
    not Path(shutil.which("mutmut") or REPO_ROOT / ".venv" / "bin" / "mutmut").is_file()
    or not Path(shutil.which("pyrefly") or REPO_ROOT / ".venv" / "bin" / "pyrefly").is_file(),
    reason="locked mutmut/Pyrefly executables are unavailable",
)
def test_real_mutmut_pyrefly_fixture_reports_two_killed_one_type_invalid(tmp_path: Path) -> None:
    venv_bin = REPO_ROOT / ".venv" / "bin"
    repo = _make_repo(tmp_path)
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join((str(venv_bin), env.get("PATH", "")))
    run = subprocess.run(
        [
            sys.executable,
            "scripts/run_slice_mutmut.py",
            "--source",
            "src/probe.py",
            "--test",
            "tests/test_probe.py",
            "--tmp-root",
            str(tmp_path / "scratch"),
            "--result-json",
            "mutants/result.json",
            "--diff-report",
            "mutants/diffs.md",
            "--max-children",
            "1",
            "--timeout-seconds",
            "120",
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )

    assert run.returncode == 0, run.stderr
    result = _read_result(repo)
    assert result["counts"] == {
        "total": 3,
        "killed": 2,
        "type_invalid": 1,
        "survived": 0,
        "no_tests": 0,
        "timeout": 0,
        "suspicious": 0,
        "skipped": 0,
        "interrupted": 0,
        "segfault": 0,
        "not_checked": 0,
    }


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def test_git_discovery_opt_in_includes_staged_unstaged_untracked_and_newline_names(tmp_path: Path) -> None:
    repo = tmp_path / "git-repo"
    (repo / "src").mkdir(parents=True)
    for name in ("staged.py", "unstaged.py"):
        (repo / "src" / name).write_text("value = 1\n", encoding="utf-8")
    _git(repo, "init", "--quiet", "--initial-branch=main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "add", ".")
    _git(repo, "commit", "--quiet", "-m", "base")
    (repo / "src" / "staged.py").write_text("value = 2\n", encoding="utf-8")
    _git(repo, "add", "src/staged.py")
    (repo / "src" / "unstaged.py").write_text("value = 3\n", encoding="utf-8")
    (repo / "src" / "untracked.py").write_text("value = 4\n", encoding="utf-8")
    newline_name = repo / "src" / "line\nbreak.py"
    newline_name.write_text("value = 5\n", encoding="utf-8")

    found = _git_diff.changed_python_files(
        repo,
        base_candidates=("HEAD",),
        source_prefixes=("src/",),
        include_worktree=True,
        include_untracked=True,
    )

    assert {path.relative_to(repo).as_posix() for path in found} == {
        "src/staged.py",
        "src/unstaged.py",
        "src/untracked.py",
        "src/line\nbreak.py",
    }
    assert _git_diff.changed_python_files(repo, base_candidates=("HEAD",), source_prefixes=("src/",)) == [], (
        "defaults must preserve committed-delta-only Semgrep behavior"
    )


def test_git_discovery_timeout_is_loud_fail_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(_git_diff, "resolve_tool", lambda *_args, **_kwargs: "/usr/bin/git")

    def timeout(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(cmd=["git"], timeout=30)

    monkeypatch.setattr("scripts._git_diff.subprocess.run", timeout)
    assert _git_diff.changed_python_files(tmp_path, base_candidates=("HEAD",)) == []
    assert "failed" in capsys.readouterr().err


def test_targeted_selector_never_admits_tests_as_mutation_source(tmp_path: Path) -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from scripts import run_targeted_mutmut as targeted

    repo = tmp_path / "repo"
    (repo / "src" / "fa" / "session").mkdir(parents=True)
    (repo / "tests").mkdir()
    source = repo / "src" / "fa" / "session" / "manager.py"
    test = repo / "tests" / "test_session_lifecycle.py"
    source.write_text("value = 1\n", encoding="utf-8")
    test.write_text("def test_x(): pass\n", encoding="utf-8")

    scoped = targeted._scope_to_changed(
        [source, test],
        repo_root=repo,
        source_roots=("src/fa/session",),
    )
    assert scoped == [source]


def test_targeted_main_propagates_action_required_executor_rc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import run_targeted_mutmut as targeted

    repo = tmp_path / "repo"
    source = repo / "src" / "fa" / "session" / "manager.py"
    source.parent.mkdir(parents=True)
    source.write_text("value = 1\n", encoding="utf-8")
    sentinel = cast(SliceRequest, object())
    observed: list[SliceRequest] = []

    monkeypatch.setattr(targeted, "REPO_ROOT", repo)
    monkeypatch.setattr(targeted, "_mutmut_installed", lambda: True)
    monkeypatch.setattr("scripts.run_targeted_mutmut.gd.changed_python_files", lambda *_args, **_kwargs: [source])
    monkeypatch.setattr(targeted, "_scope_to_changed", lambda _changed: [source])
    monkeypatch.setattr(targeted, "request_from_configured_scope", lambda *_args, **_kwargs: sentinel)

    def execute(request: SliceRequest) -> SliceResult:
        observed.append(request)
        return SliceResult(
            exit_code=1,
            payload={
                "reason": None,
                "counts": {"total": 1, "killed": 0, "type_invalid": 0, "survived": 1},
            },
        )

    monkeypatch.setattr(targeted, "run_slice", execute)
    assert targeted.main() == 1
    assert observed == [sentinel]


def test_permanent_mutation_configuration_includes_readiness_and_type_filter() -> None:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    mutmut = data["tool"]["mutmut"]
    gremlins = data["tool"]["pytest-gremlins"]
    source_paths = mutmut["source_paths"]
    assert source_paths[-1] == "src/fa/workspace_bootstrap.py"
    assert mutmut["pytest_add_cli_args_test_selection"][-1] == "tests/test_workspace_bootstrap.py"
    assert mutmut["also_copy"] == ["src/fa"]
    command = mutmut["type_check_command"]
    assert command[:2] == ["pyrefly", "check"]
    assert command[2 : 2 + len(source_paths)] == source_paths
    assert command[2 + len(source_paths) :] == [
        "--output-format=json",
        "--summary=none",
        "--progress-bar=no",
    ]
    assert gremlins["paths"] == source_paths


def test_weekly_workflow_uses_configured_runner_complete_artifacts_and_locked_sync() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "uv sync --locked --extra dev" in text
    assert "uv sync --frozen" not in text
    assert "scripts/run_slice_mutmut.py --configured-scope" in text
    assert "--timeout-seconds 18000" in text
    assert "uv run mutmut run" not in text
    assert "mutants/mutmut-slice-result.json" in text
    assert "mutants/mutmut-slice-diffs.md" in text
    assert "type_invalid" in text
    assert "continue-on-error: true" in text
    assert "retention-days: 90" in text


def test_new_runner_is_protected_by_both_tcb_authorities() -> None:
    assert "/scripts/run_slice_mutmut.py" in CODEOWNERS.read_text(encoding="utf-8")
    assert '"scripts/run_slice_mutmut.py"' in PROTECTED_PATHS.read_text(encoding="utf-8")


def test_targeted_wrapper_delegates_and_deletes_live_config_rewrite() -> None:
    text = TARGETED.read_text(encoding="utf-8")
    assert "run_slice(" in text
    assert "_rewrite_source_paths" not in text
    assert ".pre-targeted-mutmut.bak" not in text
    assert "MUTANT_TIMEOUT_SECONDS" not in text
