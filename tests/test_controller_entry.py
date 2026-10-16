"""CT98 C0/C2/C3: installed entry, real CLI and pre-site poison rejection.

These do NOT prove the Docker image, production launchers or project cells.
Wheel build/install are offline; only disposable test environments are changed.
"""

from __future__ import annotations

import importlib.machinery
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest

from fa.controller_entry import ControllerImportError, _assert_installation, _assert_loaded_origins

_ROOT = Path(__file__).resolve().parents[1]
_ENTRY = _ROOT / "src/fa/controller_entry.py"
_ERROR = "fa: controller_import_closure_invalid\n"


@dataclass(frozen=True)
class InstalledController:
    prefix: Path
    python: Path
    site: Path


@pytest.fixture(scope="module")
def installed_controller(tmp_path_factory: pytest.TempPathFactory) -> InstalledController:
    """Use the actual wheel and locked dependency cache, never an editable fa import."""
    uv = shutil.which("uv")
    assert uv is not None, "CT98 installed-entry tests require the project's uv tool"
    root = tmp_path_factory.mktemp("installed-controller")
    wheels = root / "wheels"
    _command([uv, "build", "--offline", "--wheel", "--out-dir", str(wheels)], cwd=_ROOT)
    (wheel,) = wheels.glob("*.whl")
    prefix = root / "venv"
    _command(
        [uv, "sync", "--offline", "--frozen", "--no-dev", "--no-editable", "--python", sys.executable],
        cwd=_ROOT,
        env={**os.environ, "UV_PROJECT_ENVIRONMENT": str(prefix)},
    )
    python = prefix / "bin/python"
    _command(
        [uv, "pip", "install", "--offline", "--no-deps", "--reinstall", "--python", str(python), str(wheel)],
        cwd=root,
    )
    site = prefix / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    assert (site / "fa/controller_entry.py").read_bytes() == _ENTRY.read_bytes()
    return InstalledController(prefix, python, site)


def _command(argv: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=120, check=False)
    assert result.returncode == 0, (argv, result.returncode, result.stdout, result.stderr)
    return result


def _entry(
    installed: InstalledController, *, cwd: Path, env: dict[str, str] | None = None, isolated: bool = True
) -> subprocess.CompletedProcess[str]:
    flags = ["-I"] if isolated else []
    return subprocess.run(
        [str(installed.python), *flags, "-m", "fa.controller_entry", "--help"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _assert_denied(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == os.EX_CONFIG
    assert result.stdout == ""
    assert result.stderr == _ERROR


@pytest.fixture
def install_data(tmp_path: Path) -> Path:
    """Minimal install DATA for C0/C3 audit, not a runnable or claimed installed controller."""
    prefix = tmp_path / "install"
    site = prefix / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    (site / "fa").mkdir(parents=True)
    for name in ["__init__.py", "controller_entry.py", "cli.py"]:
        (site / "fa" / name).write_text("", encoding="utf-8")
    metadata = site / "first_agent-0.1.0.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text("Metadata-Version: 2.3\nName: first-agent\nVersion: 0.1.0\n", encoding="utf-8")
    (prefix / "pyvenv.cfg").write_text("include-system-site-packages = false\n", encoding="utf-8")
    return prefix


def _site(prefix: Path) -> Path:
    return prefix / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"


def test_install_audit_accepts_closed_data_and_internal_pth(install_data: Path) -> None:
    site = _site(install_data)
    (site / "internal").mkdir()
    (site / "internal.pth").write_text("\ufeff# allowed data, not Python\n\ninternal\n", encoding="utf-8")
    assert _assert_installation(install_data) == site.resolve()


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("editable.pth", "import os; raise RuntimeError('must not execute')\n"),
        ("tab.pth", "import\tos\n"),
        ("path.pth", "../../../project/src\n"),
        ("absolute.pth", "/unapproved/project/src\n"),
        ("editable.egg-link", "/project/src\n"),
        ("sitecustomize.py", "raise RuntimeError('must not execute')"),
        ("usercustomize.py", "raise RuntimeError('must not execute')"),
        ("sitecustomize.pyc", "untrusted bytecode"),
        ("first_agent-0.1.0.dist-info/direct_url.json", '{"dir_info":{"editable":true}}'),
        ("first_agent-0.1.0.dist-info/direct_url.json", "[]"),
        ("first_agent-0.1.0.dist-info/direct_url.json", '{"dir_info":null}'),
        ("first_agent-0.1.0.dist-info/direct_url.json", "not JSON"),
        ("bad.pth", "x" * (64 * 1024 + 1)),
    ],
)
def test_install_audit_rejects_unsafe_install_data(install_data: Path, name: str, content: str) -> None:
    (_site(install_data) / name).write_text(content, encoding="utf-8")
    with pytest.raises(ControllerImportError, match=r"^fa: controller_import_closure_invalid$"):
        _assert_installation(install_data)


@pytest.mark.parametrize(
    "config",
    [
        "",
        "include-system-site-packages=true\n",
        "include-system-site-packages=false\ninclude-system-site-packages=false\n",
    ],
)
def test_install_audit_rejects_ambient_or_ambiguous_site(install_data: Path, config: str) -> None:
    (install_data / "pyvenv.cfg").write_text(config, encoding="utf-8")
    with pytest.raises(ControllerImportError):
        _assert_installation(install_data)


def test_install_audit_rejects_symlink_to_project_code(install_data: Path, tmp_path: Path) -> None:
    target = tmp_path / "project.py"
    target.write_text("raise RuntimeError('untrusted')", encoding="utf-8")
    path = _site(install_data) / "fa/cli.py"
    path.unlink()
    path.symlink_to(target)
    with pytest.raises(ControllerImportError):
        _assert_installation(install_data)


def test_pre_site_audit_never_executes_pth(install_data: Path, tmp_path: Path) -> None:
    sentinel = tmp_path / "executed"
    (_site(install_data) / "poison.pth").write_text(
        f"import pathlib; pathlib.Path({str(sentinel)!r}).touch()\n", encoding="utf-8"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(_ENTRY), "--check-install", str(install_data)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    _assert_denied(result)
    assert not sentinel.exists()


def test_installed_real_cli_help(installed_controller: InstalledController) -> None:
    installed = installed_controller
    _command(
        [
            str(installed.python),
            "-I",
            "-S",
            str(installed.site / "fa/controller_entry.py"),
            "--check-install",
            str(installed.prefix),
        ],
        cwd=installed.prefix,
    )
    result = _entry(installed, cwd=installed.prefix)
    assert result.returncode == 0, result.stderr
    assert "usage: fa" in result.stdout
    assert "workflow" in result.stdout
    assert "selfcheck" in result.stdout
    assert result.stderr == ""


def test_installed_entry_ignores_project_and_user_import_poison(
    installed_controller: InstalledController, tmp_path: Path
) -> None:
    sentinel = tmp_path / "executed"
    poison = f"from pathlib import Path\nPath({str(sentinel)!r}).touch()\nraise RuntimeError('project code executed')\n"
    project = tmp_path / "project"
    (project / "fa").mkdir(parents=True)
    (project / "fa/__init__.py").write_text(poison, encoding="utf-8")
    for name in ["argparse.py", "sitecustomize.py", "json.py"]:
        (project / name).write_text(poison, encoding="utf-8")
    home = tmp_path / "home"
    user_site = home / ".local/lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    user_site.mkdir(parents=True)
    (user_site / "usercustomize.py").write_text(poison, encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(project), "HOME": str(home), "PYTHONUSERBASE": str(home / ".local")}
    result = _entry(installed_controller, cwd=project, env=env)
    assert result.returncode == 0, result.stderr
    assert "usage: fa" in result.stdout
    assert not sentinel.exists()


def test_installed_entry_rejects_nonisolated_launch(installed_controller: InstalledController) -> None:
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYTHON")}
    _assert_denied(_entry(installed_controller, cwd=installed_controller.prefix, env=env, isolated=False))


def test_installed_entry_producer_blocks_external_site_path(
    installed_controller: InstalledController, tmp_path: Path
) -> None:
    """CT98 kill oracle: remove _main's admission call and CLI help incorrectly succeeds."""
    external = tmp_path / "external"
    external.mkdir()
    path = installed_controller.site / "external.pth"
    path.write_text(str(external) + "\n", encoding="utf-8")
    try:
        _assert_denied(_entry(installed_controller, cwd=installed_controller.prefix))
    finally:
        path.unlink()


def test_pre_site_audit_rejects_nested_customization(install_data: Path, tmp_path: Path) -> None:
    sentinel = tmp_path / "executed"
    site = _site(install_data)
    (site / "internal").mkdir()
    (site / "internal.pth").write_text("internal\n", encoding="utf-8")
    (site / "internal/sitecustomize.py").write_text(
        f"from pathlib import Path\nPath({str(sentinel)!r}).touch()\n", encoding="utf-8"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(_ENTRY), "--check-install", str(install_data)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    _assert_denied(result)
    assert not sentinel.exists()


def test_install_audit_rejects_later_package_symlink(install_data: Path, tmp_path: Path) -> None:
    target = tmp_path / "project-package"
    target.mkdir()
    (target / "__init__.py").write_text("raise RuntimeError('untrusted')", encoding="utf-8")
    (_site(install_data) / "fa/delegated").symlink_to(target, target_is_directory=True)
    with pytest.raises(ControllerImportError):
        _assert_installation(install_data)


def test_install_audit_rejects_pth_archive_layout(install_data: Path) -> None:
    site = _site(install_data)
    (site / "code.zip").write_bytes(b"unsupported import archive")
    (site / "archive.pth").write_text("code.zip\n", encoding="utf-8")
    with pytest.raises(ControllerImportError):
        _assert_installation(install_data)


@pytest.mark.parametrize("namespace", [False, True])
def test_loaded_origin_audit_rejects_external_module_or_namespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, namespace: bool
) -> None:
    roots = (Path(sys.base_prefix), Path(sys.prefix), _ROOT)
    _assert_loaded_origins(roots)
    module = ModuleType("_ct98_probe")
    if namespace:
        module.__spec__ = importlib.machinery.ModuleSpec(module.__name__, loader=None)
        module.__dict__["__path__"] = [str(tmp_path)]
    else:
        module.__spec__ = importlib.machinery.ModuleSpec(module.__name__, loader=None, origin=str(tmp_path / "bad.py"))
    monkeypatch.setitem(sys.modules, module.__name__, module)
    with pytest.raises(ControllerImportError):
        _assert_loaded_origins(roots)


@pytest.mark.parametrize("namespace", [False, True])
def test_real_entry_rejects_injected_loaded_origin(
    installed_controller: InstalledController, tmp_path: Path, namespace: bool
) -> None:
    """Fault-inject module metadata, not provider or gate: exercise the actual entry root."""
    origin = None if namespace else str(tmp_path / "bad.py")
    locations = [str(tmp_path)] if namespace else []
    code = (
        "import sys,types,importlib.machinery; from fa import controller_entry; "
        "m=types.ModuleType('_ct98_probe'); "
        f"m.__spec__=importlib.machinery.ModuleSpec(m.__name__,loader=None,origin={origin!r}); "
        f"m.__dict__['__path__']={locations!r}; "
        "sys.modules[m.__name__]=m; sys.argv=['fa','--help']; "
        "raise SystemExit(controller_entry._main())"
    )
    result = subprocess.run(
        [str(installed_controller.python), "-I", "-c", code],
        cwd=installed_controller.prefix,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    _assert_denied(result)
