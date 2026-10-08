"""Make a scripts-root kill overlay win before pytest imports test modules.

This is loaded only for kill-checks targeting ``scripts/``. The normal
workspace remains the pytest cwd and supplies the tests; this hook installs a
narrow import finder for the copied ``scripts`` package and fails closed if the
exact mutated module did not come from that copy.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import importlib.util
import os
import sys
import typing
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import override
else:
    # The project targets Python 3.13, but `uv run --no-sync` in a bare
    # checkout can fall back to a 3.11 bootstrap interpreter. This decorator
    # is static-only, so an identity fallback preserves runtime behavior.
    override = getattr(typing, "override", lambda function: function)

_OVERLAY_PROVENANCE_ERROR_MARKER = "FA_MUTATION_OVERLAY_PROVENANCE_ERROR:"
_SCRIPTS_ROOT_ENV = "FA_MUTATION_OVERLAY_SCRIPTS_ROOT"
_TARGET_MODULE_ENV = "FA_MUTATION_OVERLAY_MODULE"


class _OverlayScriptsFinder(importlib.abc.MetaPathFinder):
    """Resolve ``scripts`` modules only from the selected overlay tree."""

    def __init__(self, scripts_tree: Path) -> None:
        self.scripts_tree = scripts_tree.resolve()

    @override
    def find_spec(
        self,
        fullname: str,
        path: object = None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        del path, target  # Ignore pytest's workspace-root package path on purpose.
        if fullname != "scripts" and not fullname.startswith("scripts."):
            return None
        relative_parts = fullname.split(".")[1:]
        module_path = self.scripts_tree.joinpath(*relative_parts)
        package_init = module_path / "__init__.py"
        if package_init.is_file():
            return importlib.util.spec_from_file_location(
                fullname,
                package_init,
                submodule_search_locations=[str(module_path)],
            )
        source_file = module_path.with_suffix(".py")
        if source_file.is_file():
            return importlib.util.spec_from_file_location(fullname, source_file)
        if module_path.is_dir():
            spec = importlib.machinery.ModuleSpec(fullname, loader=None, is_package=True)
            spec.submodule_search_locations = [str(module_path)]
            return spec
        return None


def _install_scripts_importer(scripts_tree: Path) -> None:
    """Install one overlay finder ahead of pytest's workspace import path."""
    resolved_tree = Path(scripts_tree).resolve()
    for finder in sys.meta_path:
        if isinstance(finder, _OverlayScriptsFinder) and finder.scripts_tree == resolved_tree:
            return
    sys.meta_path.insert(0, _OverlayScriptsFinder(resolved_tree))


def _fail(message: str) -> None:
    """Emit a recognizable harness failure so a test failure cannot prove a kill."""
    from pytest import UsageError

    raise UsageError(f"{_OVERLAY_PROVENANCE_ERROR_MARKER} {message}")


def _loaded_module_path(module: ModuleType) -> Path | None:
    origin = getattr(module, "__file__", None)
    if not isinstance(origin, str) or not origin:
        return None
    try:
        return Path(origin).resolve()
    except (OSError, RuntimeError, ValueError):
        return None


def _check_target_module(target: str, scripts_tree: Path, *, required: bool) -> None:
    module = sys.modules.get(target)
    if module is None:
        if required:
            _fail(f"target module {target!r} was not imported during test collection")
        return
    origin = _loaded_module_path(module)
    if origin is None or not origin.is_relative_to(scripts_tree):
        _fail(f"target module {target!r} resolved to {origin!s}, not {scripts_tree}")


def _prepend_overlay_before_collection() -> None:
    """Put the scripts overlay first, failing if another import already won."""
    overlay_value = os.environ.get(_SCRIPTS_ROOT_ENV)
    target = os.environ.get(_TARGET_MODULE_ENV)
    if not overlay_value or not target:
        return
    overlay_root = Path(overlay_value).resolve()
    scripts_tree = (overlay_root / "scripts").resolve()
    if not scripts_tree.is_dir():
        _fail(f"scripts overlay tree does not exist: {scripts_tree}")
    if target != "scripts" and not target.startswith("scripts."):
        _fail(f"target module {target!r} is not below the scripts package")

    # An earlier plugin/conftest import must not silently bind the workspace
    # copy before this hook runs. Refuse instead of evicting live modules.
    _check_target_module(target, scripts_tree, required=False)
    overlay_import_root = str(overlay_root)
    sys.path[:] = [
        overlay_import_root,
        *(
            entry
            for entry in sys.path
            if _resolved_entry(entry) != overlay_root
        ),
    ]
    _install_scripts_importer(scripts_tree)


def pytest_load_initial_conftests() -> None:
    """Install the exact scripts importer before pytest loads workspace tests."""
    _prepend_overlay_before_collection()


def pytest_configure() -> None:
    """Reassert the scripts importer and reject an already-bound workspace copy."""
    _prepend_overlay_before_collection()

def _resolved_entry(entry: str) -> Path | None:
    try:
        return Path(entry or os.curdir).resolve()
    except (OSError, RuntimeError, ValueError):
        return None


def pytest_collection_finish() -> None:
    """Require the exact producer module to be loaded from the mutation copy."""
    overlay_value = os.environ.get(_SCRIPTS_ROOT_ENV)
    target = os.environ.get(_TARGET_MODULE_ENV)
    if not overlay_value or not target:
        return
    scripts_tree = (Path(overlay_value).resolve() / "scripts").resolve()
    _check_target_module(target, scripts_tree, required=True)
