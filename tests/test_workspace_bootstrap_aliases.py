"""C1/C3 authority for S4 workspace bootstrap aliases and migration."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _make_wrapper_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "wrapper-repo"
    (repo / "scripts" / "bootstrap").mkdir(parents=True)
    (repo / "src" / "fa").mkdir(parents=True)
    shutil.copy2(
        Path(__file__).resolve().parents[1] / "scripts" / "bootstrap" / "workspace.py",
        repo / "scripts" / "bootstrap" / "workspace.py",
    )
    (repo / "src" / "fa" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "src" / "fa" / "workspace_bootstrap.py").write_text(
        "from __future__ import annotations\n"
        "import json, os\n"
        "from pathlib import Path\n"
        "def _main(argv=None):\n"
        "    Path(os.environ['FA_TEST_WRAPPER_RECORD']).write_text(\n"
        "        json.dumps({'argv': argv, 'module': __file__}), encoding='utf-8')\n"
        "    return int(os.environ.get('FA_TEST_WRAPPER_RC', '0'))\n",
        encoding="utf-8",
    )
    return repo


def test_workspace_wrapper_imports_checkout_source_and_forwards_argv(tmp_path: Path) -> None:
    """C1 S4: shipped wrapper reaches the checked-out CT3 CLI without uv."""

    repo = _make_wrapper_repo(tmp_path)
    record = tmp_path / "wrapper-record.json"
    env = os.environ.copy()
    env["FA_TEST_WRAPPER_RECORD"] = str(record)

    result = subprocess.run(
        [sys.executable, str(repo / "scripts" / "bootstrap" / "workspace.py"), "check", "--workspace", "."],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(record.read_text(encoding="utf-8"))
    assert payload["argv"] == ["check", "--workspace", "."]
    assert Path(payload["module"]).resolve() == (repo / "src" / "fa" / "workspace_bootstrap.py").resolve()


def _make_host_bootstrap_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "host-repo"
    bootstrap_dir = repo / "scripts" / "bootstrap"
    bootstrap_dir.mkdir(parents=True)
    source_root = Path(__file__).resolve().parents[1]
    shutil.copy2(source_root / "scripts" / "bootstrap" / "host_bootstrap.py", bootstrap_dir / "host_bootstrap.py")
    wrapper_record = tmp_path / "host-wrapper-record.json"
    (bootstrap_dir / "workspace.py").write_text(
        "from __future__ import annotations\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['FA_TEST_HOST_WRAPPER_RECORD']).write_text(\n"
        "    json.dumps(sys.argv[1:]), encoding='utf-8')\n"
        "raise SystemExit(int(os.environ.get('FA_TEST_HOST_WRAPPER_RC', '0')))\n",
        encoding="utf-8",
    )
    bin_dir = tmp_path / "host-bin"
    bin_dir.mkdir()
    uv_calls = tmp_path / "host-uv-calls.jsonl"
    _write_executable(
        bin_dir / "uv",
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "with Path(os.environ['FA_TEST_HOST_UV_CALLS']).open('a', encoding='utf-8') as handle:\n"
        "    handle.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "raise SystemExit(int(os.environ.get('FA_TEST_HOST_UV_RC', '0')))\n",
    )
    _write_executable(
        bin_dir / "just",
        f"#!{sys.executable}\nimport os\nprint('just ' + os.environ.get('FA_TEST_JUST_VERSION', '1.57.0'))\n",
    )
    return repo, wrapper_record, uv_calls


def _run_host_bootstrap(
    repo: Path,
    wrapper_record: Path,
    uv_calls: Path,
    *,
    wrapper_rc: int = 0,
    just_version: str = "1.57.0",
    include_uv: bool = True,
) -> subprocess.CompletedProcess[str]:
    bin_dir = uv_calls.parent / "host-bin"
    if not include_uv:
        (bin_dir / "uv").unlink()
    env = os.environ.copy()
    env.update(
        {
            "PATH": os.pathsep.join((str(bin_dir), "/usr/bin", "/bin")),
            "FA_TEST_HOST_WRAPPER_RECORD": str(wrapper_record),
            "FA_TEST_HOST_WRAPPER_RC": str(wrapper_rc),
            "FA_TEST_HOST_UV_CALLS": str(uv_calls),
            "FA_TEST_JUST_VERSION": just_version,
        }
    )
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / "bootstrap" / "host_bootstrap.py")],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def test_host_bootstrap_delegates_current_just_to_wrapper_and_emits_ready(tmp_path: Path) -> None:
    """C1 S4: current host tooling reaches wrapper before readiness signal."""

    repo, record, uv_calls = _make_host_bootstrap_repo(tmp_path)
    result = _run_host_bootstrap(repo, record, uv_calls)

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[-1] == "FA_AGENT_READY=1"
    assert json.loads(record.read_text(encoding="utf-8")) == ["ensure", "--workspace", str(repo)]
    assert not uv_calls.exists(), "current just must not trigger network-capable uv tool install"


def test_host_bootstrap_propagates_wrapper_degradation_without_ready_signal(tmp_path: Path) -> None:
    """C3 S4: wrapper degradation cannot be relabeled ready."""

    repo, record, uv_calls = _make_host_bootstrap_repo(tmp_path)
    result = _run_host_bootstrap(repo, record, uv_calls, wrapper_rc=75)

    assert result.returncode == 75
    assert "FA_AGENT_READY=1" not in result.stdout
    assert record.is_file()


def test_host_bootstrap_missing_uv_is_stable_and_does_not_call_wrapper(tmp_path: Path) -> None:
    """C3 S4: direct host recovery names missing uv and returns its stable rc."""

    repo, record, uv_calls = _make_host_bootstrap_repo(tmp_path)
    result = _run_host_bootstrap(repo, record, uv_calls, include_uv=False)

    assert result.returncode == 2
    assert "uv is required" in result.stderr
    assert not record.exists()
    assert "FA_AGENT_READY=1" not in result.stdout


def test_host_bootstrap_installs_only_wrong_just_then_delegates(tmp_path: Path) -> None:
    """C1 S4: host tool setup is separate and conditional."""

    repo, record, uv_calls = _make_host_bootstrap_repo(tmp_path)
    result = _run_host_bootstrap(repo, record, uv_calls, just_version="1.56.0")

    assert result.returncode == 0, result.stderr
    calls = [json.loads(line) for line in uv_calls.read_text(encoding="utf-8").splitlines()]
    assert calls == [
        ["tool", "install", "--force", "rust-just==1.57.0"],
        ["tool", "update-shell"],
    ]
    assert record.is_file()


def _just_recipe(text: str, name: str) -> str:
    lines = text.splitlines()
    start = lines.index(f"{name}:") + 1
    body: list[str] = []
    for line in lines[start:]:
        if line and not line.startswith((" ", "\t")):
            break
        body.append(line)
    return "\n".join(body)


def test_just_bootstrap_aliases_converge_and_doctor_is_read_only() -> None:
    """C1/static S4: public aliases have one readiness engine and no sync prelude."""

    root = Path(__file__).resolve().parents[1]
    text = (root / "justfile").read_text(encoding="utf-8")
    install = _just_recipe(text, "install")
    agent = _just_recipe(text, "agent-bootstrap")
    doctor = _just_recipe(text, "doctor")

    assert "python3 scripts/bootstrap/workspace.py ensure --workspace ." in install
    assert "uv sync" not in install
    assert "_install-hooks" not in install
    assert "_hooks-status" not in install
    assert "python3 scripts/bootstrap/host_bootstrap.py" in agent
    assert "uv run" not in agent
    assert "python3 scripts/bootstrap/workspace.py check --workspace ." in doctor
    assert "workspace.py ensure" not in doctor
    assert "uv run" not in doctor
    assert "\n_install-hooks:" not in text
    assert "\n_hooks-status:" not in text


def test_s4_marker_migration_and_vscode_convenience_contract() -> None:
    """C1/static S4: machine marker is untracked; VS Code remains non-authoritative."""

    root = Path(__file__).resolve().parents[1]
    ignore = (root / ".gitignore").read_text(encoding="utf-8")
    assert ".fa/*" in ignore
    assert "!.fa/dependency_contract.toml" in ignore
    assert "!.fa/host-bootstrap.json" not in ignore
    assert not (root / ".fa" / "host-bootstrap.json").exists()
    task = json.loads((root / ".vscode" / "tasks.json").read_text(encoding="utf-8"))
    bootstrap_task = task["tasks"][0]
    assert bootstrap_task["command"] == "uvx"
    assert bootstrap_task["args"] == ["--from", "rust-just==1.57.0", "just", "agent-bootstrap"]
    assert bootstrap_task["runOptions"] == {"runOn": "folderOpen"}


_ROOT = Path(__file__).resolve().parents[1]
_OPERATOR_CLONE = "~/First-Agent-dev"
_DEPLOYMENT_MIRROR = "/srv/first-agent/repo/First-Agent-dev"
_HOST_READY_COMMAND = "uvx --from rust-just==1.57.0 just agent-bootstrap"
_UV_INSTALL_DOC = "https://docs.astral.sh/uv/getting-started/installation/"


def _document(relative: str) -> str:
    return (_ROOT / relative).read_text(encoding="utf-8")


def _fenced_blocks(markdown: str) -> list[str]:
    parts = markdown.split("```")
    return [parts[index] for index in range(1, len(parts), 2)]


def test_s6_docs_define_operator_clone_and_deployment_mirror_roles() -> None:
    """C1/static T13: paths and recovery command are explicit; removing an authority statement fails."""

    agents = _document("AGENTS.md")
    install = _document("knowledge/instructions/01-install.md")
    operations = _document("knowledge/instructions/02-operations.md")

    for text in (agents, install, operations):
        assert _OPERATOR_CLONE in text
        assert _DEPLOYMENT_MIRROR in text
        assert _HOST_READY_COMMAND in text
    assert "operator development clone" in agents
    assert "clean deployment mirror" in agents
    assert "managed clones" in agents
    assert "arbitrary raw clones" in agents

    for relative, text in (
        ("knowledge/instructions/01-install.md", install),
        ("knowledge/instructions/02-operations.md", operations),
    ):
        unsafe = [block for block in _fenced_blocks(text) if _DEPLOYMENT_MIRROR in block and "git commit" in block]
        assert unsafe == [], f"{relative} tells the operator to commit in the deployment mirror"


def test_s6_missing_uv_recovery_and_vscode_non_authority_are_explicit() -> None:
    """C1/C3-static T13: missing-tool recovery exists and folderOpen is never the readiness authority."""

    agents = _document("AGENTS.md")
    install = _document("knowledge/instructions/01-install.md")
    operations = _document("knowledge/instructions/02-operations.md")
    combined = "\n".join((agents, install, operations))

    assert _UV_INSTALL_DOC in combined
    assert "best-effort convenience" in agents
    assert "VS Code" in agents
    assert "permission" in agents
    assert "folderOpen" in agents


def test_s6_guardrail_reference_uses_lifecycle_readiness_and_current_hook_commands() -> None:
    """C1/static T13: guardrail consumers describe shipped producers, not deleted bootstrap paths."""

    reference = _document("knowledge/ci-guardrails-reference.md")

    for stale in (
        "uv sync --frozen",
        ".fa/host-bootstrap.json",
        "just hooks-status",
        "agent runner MUST invoke `just agent-bootstrap`",
        "uv run pre-commit run",
        "uv run just check",
    ):
        assert stale not in reference
    assert "lifecycle readiness" in reference
    assert "scripts/bootstrap/workspace.py" in reference
    assert "`just doctor`" in reference
    assert "uv run --no-sync pre-commit run --hook-stage pre-commit" in reference
    assert "uv run --no-sync just check-deep" in reference
    assert "CI" in reference
    assert "local hook seats are not required" in " ".join(reference.split())
