"""Git-hook shell scripts + installer for all local commit hooks.

The three scripts in this directory (``pre-commit``, ``prepare-commit-msg``
and ``commit-msg``) are thin wrappers installed into ``.git/hooks/`` by
the installer.  All three invoke their respective commands through
``uv run``, ensuring they work reliably in uv-managed environments
(including Windows/PowerShell) where bare PATH lookups fail.

The ``pre-commit`` hook runs ``uv run pre-commit run``, which executes
the checks defined in ``.pre-commit-config.yaml``.  The
``prepare-commit-msg`` and ``commit-msg`` hooks invoke
``python -m fa.hygiene {prepare|validate}`` for the PR-intent gate.

:func:`install_hooks` installs the scripts into ``.git/hooks/``;
:func:`check_hooks` provides a deterministic status probe that
verifies all three local hook seats are installed and current.

Lazy imports are used to avoid the ``RuntimeWarning`` that fires
when running a submodule via ``python -m fa.hygiene.hooks.{install,status}``
while the package's ``__init__`` has already imported it.
"""

from __future__ import annotations

from fa.hygiene.hooks.install import HOOK_NAMES


def __getattr__(name: str) -> object:
    """Lazy import to avoid RuntimeWarning on ``-m`` invocation."""

    if name == "install_hooks":
        from fa.hygiene.hooks.install import install_hooks

        return install_hooks
    if name == "check_hooks":
        from fa.hygiene.hooks.status import check_hooks

        return check_hooks
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["HOOK_NAMES", "check_hooks", "install_hooks"]
