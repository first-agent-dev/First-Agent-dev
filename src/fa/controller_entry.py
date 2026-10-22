"""Isolated installed-controller entry and pre-site installation audit.

The image builder runs this file with ``python -I -S ... --check-install VENV``
BEFORE starting Python with site enabled. The runtime assertion cannot undo
executable .pth or sitecustomize code that Python has already executed.
Immutable image construction, frozen dependencies and launch flags are TCB.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import sys
import sysconfig
from pathlib import Path

_ERROR = "fa: controller_import_closure_invalid"
_MAX_METADATA_BYTES = 64 * 1024


class ControllerImportError(RuntimeError):
    """Unsafe installation; never echo paths, metadata or exception bodies."""

    def __init__(self) -> None:
        super().__init__(_ERROR)


def _within(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def _read_install_text(path: Path, root: Path) -> str:
    if not path.is_file() or not _within(path, root):
        raise ControllerImportError
    with path.open("rb") as stream:
        raw = stream.read(_MAX_METADATA_BYTES + 1)
    if len(raw) > _MAX_METADATA_BYTES:
        raise ControllerImportError
    return raw.decode("utf-8-sig", errors="strict")


def _audit_pth(path: Path, site: Path) -> set[Path]:
    search_paths: set[Path] = set()
    for line in _read_install_text(path, site).splitlines():
        # Match site.addpackage: trailing whitespace is stripped, not leading.
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("import ", "import\t")) or not _within(site / line, site):
            raise ControllerImportError
        target = site / line
        # Approved wheel layout is unpacked directories, not .pth ZIP importers.
        if target.exists() and not target.is_dir():
            raise ControllerImportError
        if target.is_dir():
            search_paths.add(target.resolve())
    return search_paths


def _audit_customization(search_path: Path) -> None:
    for path in search_path.iterdir():
        if path.name.split(".", 1)[0] in {"sitecustomize", "usercustomize"}:
            raise ControllerImportError


def _audit_site(site: Path) -> None:
    search_paths = {site}
    for path in site.iterdir():
        if path.suffix == ".egg-link":
            raise ControllerImportError
        if path.suffix == ".pth":
            search_paths.update(_audit_pth(path, site))
    for search_path in search_paths:
        _audit_customization(search_path)
    # Wheels may not smuggle later package imports through an external symlink.
    for path in site.rglob("*"):
        if path.is_symlink() and not _within(path, site):
            raise ControllerImportError
    for path in site.glob("*.dist-info/direct_url.json"):
        try:
            data = json.loads(_read_install_text(path, site))
        except ValueError:
            raise ControllerImportError from None
        if not isinstance(data, dict):
            raise ControllerImportError
        info = data.get("dir_info", {})
        if not isinstance(info, dict) or info.get("editable", False) is not False:
            raise ControllerImportError


def _assert_installation(prefix: Path) -> Path:
    """Inspect install data only; works under -S without importing fa/dependencies."""
    if not prefix.is_absolute():
        raise ControllerImportError
    prefix = prefix.resolve()
    cfg = _read_install_text(prefix / "pyvenv.cfg", prefix)
    site_flags = [
        value.strip().lower()
        for line in cfg.splitlines()
        for key, sep, value in [line.partition("=")]
        if sep and key.strip().lower() == "include-system-site-packages"
    ]
    if site_flags != ["false"]:
        raise ControllerImportError
    site = prefix / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    if not site.is_dir() or not _within(site, prefix):
        raise ControllerImportError
    _audit_site(site)
    for name in ("__init__.py", "controller_entry.py", "cli.py"):
        path = site / "fa" / name
        if not path.is_file() or not _within(path, site):
            raise ControllerImportError
    distributions = list(site.glob("first_agent-*.dist-info"))
    if len(distributions) != 1 or not _within(distributions[0], site):
        raise ControllerImportError
    if importlib.metadata.PathDistribution(distributions[0]).metadata.get("Name") != "first-agent":
        raise ControllerImportError
    return site.resolve()


def _assert_controller_import_closure() -> None:
    """Gate CLI import; installed code and the base interpreter are trusted inputs."""
    if sys.platform != "linux" or sys.version_info < (3, 13) or not sys.flags.isolated or sys.flags.no_site:
        raise ControllerImportError
    if sys.prefix == sys.base_prefix:
        raise ControllerImportError
    site = _assert_installation(Path(sys.prefix))
    if Path(__file__).resolve() != site / "fa" / "controller_entry.py":
        raise ControllerImportError
    roots = (site, Path(sysconfig.get_path("stdlib")), Path(sysconfig.get_path("platstdlib")))
    stdlib_zip = roots[1].parent / f"python{sys.version_info.major}{sys.version_info.minor}.zip"
    for item in sys.path:
        if not item or not (Path(item).resolve() == stdlib_zip.resolve() or any(_within(Path(item), r) for r in roots)):
            raise ControllerImportError
    _assert_loaded_origins(roots)


def _assert_loaded_origins(roots: tuple[Path, ...]) -> None:
    for module in tuple(sys.modules.values()):
        spec = getattr(module, "__spec__", None)
        origin = getattr(spec, "origin", None)
        if origin is not None:
            if not isinstance(origin, str):
                raise ControllerImportError
            if origin not in {"built-in", "frozen"} and not any(_within(Path(origin), root) for root in roots):
                raise ControllerImportError
        for location in getattr(module, "__path__", ()):
            if not any(_within(Path(location), root) for root in roots):
                raise ControllerImportError


def _main() -> int:
    try:
        if sys.argv[1:2] == ["--check-install"]:
            if len(sys.argv) != 3 or not sys.flags.isolated or not sys.flags.no_site or sys.platform != "linux":
                raise ControllerImportError
            _assert_installation(Path(sys.argv[2]))
            return 0
        # §CT98.controller-import: no CLI/provider import before installed-closure admission.
        _assert_controller_import_closure()
        os.chdir(sys.prefix)
    except (ControllerImportError, OSError, ValueError):
        print(_ERROR, file=sys.stderr)
        return os.EX_CONFIG
    from fa.cli import main

    main()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
