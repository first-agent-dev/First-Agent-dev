"""C2 actual frozen-wheel CLI + C3 pre-site audit; not Docker/host acceptance.

Runtime-only installation uses the existing frozen uv lock, never mocked CLI.
Requires the repository's uv/Python toolchain; missing tooling fails, not skips.
Rebuild first-agent each session so source mutations reach installed producers.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ERROR = "fa: controller_import_closure_invalid\n"


def clean_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key not in {"PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"}}


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    uv = shutil.which("uv")
    assert uv is not None, "repository uv toolchain required for actual installed-controller proof"
    prefix = tmp_path_factory.mktemp("installed-controller") / "venv"
    env = {**clean_env(), "UV_PROJECT_ENVIRONMENT": str(prefix), "UV_PYTHON_DOWNLOADS": "never"}
    run = subprocess.run(
        [
            uv,
            "sync",
            "--frozen",
            "--no-dev",
            "--no-editable",
            "--reinstall-package",
            "first-agent",
            "--python",
            sys.executable,
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    site = prefix / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    assert not list(site.glob("*.pth")) and not list(site.glob("*.egg-link"))
    # Never let uv's cached local-wheel heuristic hide an actual source mutation.
    for source in (ROOT / "src" / "fa").rglob("*.py"):
        assert (site / "fa" / source.relative_to(ROOT / "src" / "fa")).read_bytes() == source.read_bytes()
    return prefix


def invoke(
    prefix: Path, args: list[str], *, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(prefix / "bin" / "python"), *args],
        cwd=cwd,
        env=clean_env() if env is None else env,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )


def audit(prefix: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    entry = (
        prefix
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
        / "fa"
        / "controller_entry.py"
    )
    return invoke(prefix, ["-I", "-S", str(entry), "--check-install", str(prefix)], cwd=cwd)


def test_actual_installed_cli_help_ignores_project_cwd_pythonpath_and_venv(installed: Path, tmp_path: Path) -> None:
    marker = tmp_path / "project-code-ran"
    poison = (
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('unsafe')\nraise RuntimeError('project poison')\n"
    )
    (tmp_path / "fa").mkdir()
    (tmp_path / "fa" / "__init__.py").write_text(poison)
    (tmp_path / "sitecustomize.py").write_text(poison)
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "python").write_text(poison)
    env = {
        **clean_env(),
        "PYTHONPATH": str(tmp_path),
        "PYTHONHOME": str(tmp_path / "invalid-home"),
        "VIRTUAL_ENV": str(tmp_path / ".venv"),
    }
    assert audit(installed, tmp_path).returncode == 0
    run = invoke(installed, ["-I", "-m", "fa.controller_entry", "--help"], cwd=tmp_path, env=env)
    assert run.returncode == 0 and "First-Agent command-line entrypoint." in run.stdout
    assert "workflow" in run.stdout and "inner-loop-smoke" in run.stdout and "authoring-check" in run.stdout
    assert not marker.exists()


def test_actual_installed_entry_rejects_nonisolated_launch_before_cli(installed: Path, tmp_path: Path) -> None:
    run = invoke(installed, ["-m", "fa.controller_entry", "--help"], cwd=tmp_path)
    assert run.returncode == os.EX_CONFIG and run.stdout == "" and run.stderr == ERROR


@pytest.mark.parametrize("kind", ["executable-pth", "outside-pth", "editable-metadata"])
def test_actual_install_pre_site_audit_rejects_poison_without_execution(
    installed: Path, tmp_path: Path, kind: str
) -> None:
    site = installed / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    marker = tmp_path / "site-code-ran"
    path = (
        site / "poison.pth"
        if kind != "editable-metadata"
        else next(site.glob("first_agent-*.dist-info")) / "direct_url.json"
    )
    original = path.read_bytes() if path.exists() else None
    if kind == "editable-metadata":
        data = json.loads(original or b"{}")
        data["dir_info"] = {"editable": True}
        body = json.dumps(data)
    elif kind == "executable-pth":
        body = f"import pathlib; pathlib.Path({str(marker)!r}).write_text('unsafe')\n"
    else:
        body = str(tmp_path) + "\n"
    try:
        # Replace, don't modify any potentially hardlinked uv-cache inode.
        path.unlink(missing_ok=True)
        path.write_text(body)
        run = audit(installed, tmp_path)
        assert run.returncode == os.EX_CONFIG and run.stdout == "" and run.stderr == ERROR
        assert not marker.exists()
    finally:
        path.unlink()
        if original is not None:
            path.write_bytes(original)


def test_image_recipe_audits_noneditable_install_before_site_enabled_cli() -> None:
    text = (ROOT / "Dockerfile.fa").read_text()
    assert "uv sync --frozen --no-dev --no-editable" in text
    assert (
        "/opt/fa-venv/bin/python -I -S /opt/first-agent/src/fa/controller_entry.py --check-install /opt/fa-venv" in text
    )
    assert "/opt/fa-venv/bin/python -I -m fa.controller_entry --help" in text
    install = text.index("uv sync --frozen --no-dev --no-editable")
    pre_site = text.index(
        "/opt/fa-venv/bin/python -I -S /opt/first-agent/src/fa/controller_entry.py --check-install /opt/fa-venv"
    )
    cli = text.index("/opt/fa-venv/bin/python -I -m fa.controller_entry --help")
    assert install < pre_site < cli
    assert text[install:pre_site].rstrip().endswith("&& \\")
    assert text[pre_site:cli].rstrip().endswith("&& \\")


@pytest.mark.parametrize(
    ("args", "controller_args"),
    [
        ((), ()),
        (("--help",), ("--help",)),
        (("-h",), ("--help",)),
        (("-help",), ("--help",)),
        (("help",), ("--help",)),
        (("help", "run"), ("help", "run")),
        (("--help", "run"), ("run", "--help")),
        (("-h", "run"), ("run", "--help")),
        (("-help", "run"), ("run", "--help")),
        (("run", "--help"), ("run", "--help")),
        (("run", "-h"), ("run", "-h")),
        (("run", "-help"), ("run", "--help")),
        (("run", "task", "--help"), ("run", "task", "--help")),
    ],
)
def test_wrapper_product_help_invokes_installed_isolated_controller(
    installed: Path, tmp_path: Path, args: tuple[str, ...], controller_args: tuple[str, ...]
) -> None:
    """Exercise scripts/fa -> container exec shape -> installed controller, without Docker."""
    repo = tmp_path / "host" / "repo"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "fa", scripts / "fa")
    (repo / "docker-compose.fa.yml").write_text("services: {}\n", encoding="utf-8")
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    project = tmp_path / "active-project"
    project.mkdir()
    (sessions / ".active").write_text(f"{project.resolve()}\n", encoding="utf-8")
    marker = tmp_path / "project-code-ran"
    (project / "fa").mkdir()
    poison = f"from pathlib import Path\nPath({str(marker)!r}).touch()\nraise RuntimeError('project poison')\n"
    (project / "fa" / "__init__.py").write_text(poison, encoding="utf-8")
    (project / "sitecustomize.py").write_text(poison, encoding="utf-8")

    trusted_cwd = tmp_path / "image-workdir"
    trusted_cwd.mkdir()
    docker_bin = tmp_path / "bin"
    docker_bin.mkdir()
    argv_log = tmp_path / "docker-argv"
    docker = docker_bin / "docker"
    docker.write_text(
        "#!/bin/sh\n"
        'printf "%s\\0" "$@" > "$FA_WRAPPER_DOCKER_ARGV"\n'
        'while [ "$#" -gt 0 ] && [ "$1" != "/opt/fa-venv/bin/python" ]; do shift; done\n'
        '[ "$#" -gt 0 ] || { echo "controller command not found" >&2; exit 64; }\n'
        "shift\n"
        'cd "$FA_WRAPPER_TRUSTED_CWD"\n'
        'exec "$FA_WRAPPER_INSTALLED_PYTHON" "$@"\n',
        encoding="utf-8",
    )
    docker.chmod(0o755)
    env = {
        **clean_env(),
        "PATH": f"{docker_bin}:{os.environ.get('PATH', '')}",
        "PYTHONPATH": str(project),
        "PYTHONHOME": str(tmp_path / "invalid-python-home"),
        "FA_WRAPPER_DOCKER_ARGV": str(argv_log),
        "FA_WRAPPER_TRUSTED_CWD": str(trusted_cwd),
        "FA_WRAPPER_INSTALLED_PYTHON": str(installed / "bin" / "python"),
    }
    run = subprocess.run(
        ["bash", str(scripts / "fa"), *args],
        cwd=project,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    assert run.stdout.strip()
    assert not marker.exists()
    argv = argv_log.read_bytes().rstrip(b"\0").decode().split("\0")
    exec_index = argv.index("exec")
    assert argv[exec_index : exec_index + 7] == [
        "exec",
        "-T",
        "-w",
        "/opt/first-agent",
        "first-agent",
        "/opt/fa-venv/bin/python",
        "-I",
    ]
    assert argv[exec_index + 7 :] == ["-m", "fa.controller_entry", *controller_args]


def test_wrapper_product_command_uses_installed_controller_with_hostile_project_env(
    installed: Path, tmp_path: Path
) -> None:
    """R01 C2/C3: ordinary fa command crosses the real wrapper/installed boundary.

    The wrapper must carry `.active` explicitly while the controller starts from
    its trusted CWD. Project `fa`, sitecustomize, PYTHONPATH and a project venv
    are hostile; the read-only `inject` command must still execute from the
    installed wheel and leave every poison marker untouched.
    """
    repo = tmp_path / "host" / "repo"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "fa", scripts / "fa")
    (repo / "docker-compose.fa.yml").write_text("services: {}\n", encoding="utf-8")
    sessions = tmp_path / "sessions"
    sessions.mkdir()

    project = tmp_path / "active-project"
    (project / "fa").mkdir(parents=True)
    active_workspace = project.resolve()
    (sessions / ".active").write_text(f"{active_workspace}\n", encoding="utf-8")
    marker = tmp_path / "project-code-ran"
    poison = f"from pathlib import Path\nPath({str(marker)!r}).touch()\nraise RuntimeError('project poison')\n"
    (project / "fa" / "__init__.py").write_text(poison, encoding="utf-8")
    (project / "sitecustomize.py").write_text(poison, encoding="utf-8")
    (project / ".venv" / "bin").mkdir(parents=True)
    (project / ".venv" / "bin" / "python").write_text(poison, encoding="utf-8")

    trusted_cwd = tmp_path / "image-workdir"
    trusted_cwd.mkdir()
    docker_bin = tmp_path / "bin"
    docker_bin.mkdir()
    argv_log = tmp_path / "docker-argv"
    docker = docker_bin / "docker"
    docker.write_text(
        "#!/bin/sh\n"
        'printf "%s\\0" "$@" > "$FA_WRAPPER_DOCKER_ARGV"\n'
        'while [ "$#" -gt 0 ]; do\n'
        '  if [ "$1" = "-e" ]; then\n'
        '    case "$2" in\n'
        '      FA_WRAPPER_ACTIVE_WORKSPACE=*) export FA_WRAPPER_ACTIVE_WORKSPACE="${2#*=}" ;;\n'
        "    esac\n"
        "    shift 2\n"
        '  elif [ "$1" = "/opt/fa-venv/bin/python" ]; then\n'
        "    shift\n"
        "    break\n"
        "  else\n"
        "    shift\n"
        "  fi\n"
        "done\n"
        '[ "$#" -gt 0 ] || { echo "controller command not found" >&2; exit 64; }\n'
        'cd "$FA_WRAPPER_TRUSTED_CWD"\n'
        'exec "$FA_WRAPPER_INSTALLED_PYTHON" "$@"\n',
        encoding="utf-8",
    )
    docker.chmod(0o755)
    env = {
        **clean_env(),
        "PATH": f"{docker_bin}:{os.environ.get('PATH', '')}",
        "PYTHONPATH": str(project),
        "PYTHONHOME": sys.base_prefix,
        "VIRTUAL_ENV": str(project / ".venv"),
        "FA_WRAPPER_DOCKER_ARGV": str(argv_log),
        "FA_WRAPPER_TRUSTED_CWD": str(trusted_cwd),
        "FA_WRAPPER_INSTALLED_PYTHON": str(installed / "bin" / "python"),
    }
    run = subprocess.run(
        ["bash", str(scripts / "fa"), "inject", "status", "--inject", "coder_slice_ceremony=enforce"],
        cwd=project,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert not marker.exists(), "hostile project code executed through wrapper/controller"
    assert run.returncode == 0, run.stderr
    assert "coder_slice_ceremony" in run.stdout and "enforce" in run.stdout and "--inject flag" in run.stdout
    argv = argv_log.read_bytes().rstrip(b"\0").decode().split("\0")
    exec_index = argv.index("exec")
    assert argv[exec_index : exec_index + 8] == [
        "exec",
        "-T",
        "-e",
        f"FA_WRAPPER_ACTIVE_WORKSPACE={active_workspace}",
        "-w",
        "/opt/first-agent",
        "first-agent",
        "/opt/fa-venv/bin/python",
    ]
    assert argv[exec_index + 8 :] == [
        "-I",
        "-m",
        "fa.controller_entry",
        "inject",
        "status",
        "--inject",
        "coder_slice_ceremony=enforce",
    ]
