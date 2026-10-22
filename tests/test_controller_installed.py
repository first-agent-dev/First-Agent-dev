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
