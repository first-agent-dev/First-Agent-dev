"""Git-hook shell scripts + installer for all local FA hooks.

The four scripts in this directory (``pre-commit``, ``pre-push``,
``prepare-commit-msg`` and ``commit-msg``) are thin wrappers installed into
the repo's effective hooks dir by the installer. All four invoke their
respective commands through ``uv run`` where appropriate, ensuring they work
reliably in uv-managed environments (including Windows/PowerShell) where bare
PATH lookups fail.

The ``pre-commit`` hook runs ``uv run pre-commit run --hook-stage pre-commit``,
which executes the safe autofix hooks defined in ``.pre-commit-config.yaml``.
The ``pre-push`` hook runs ``uv run just check`` as local CI parity before an
agent publishes a branch. The ``prepare-commit-msg`` and ``commit-msg`` hooks
invoke ``python -m fa.hygiene {prepare|validate}`` for the PR-intent gate.

:func:`install_hooks` installs the scripts into the effective hooks dir;
:func:`check_hooks` provides a deterministic status probe that verifies all
four local hook seats are installed and current.

Lazy imports are used for the callable exports so running
``python -m fa.hygiene.hooks.{install,status}`` does not pre-import
the target module and trigger ``RuntimeWarning``.
"""

from __future__ import annotations

from pathlib import Path

from fa.hygiene.hooks._util import HOOK_NAMES


def install_hooks(repo_root: Path | None = None, *, force: bool = False) -> list[Path]:
    """Lazy wrapper to avoid RuntimeWarning on ``-m`` invocation."""

    from fa.hygiene.hooks.install import install_hooks as _install_hooks

    return _install_hooks(repo_root=repo_root, force=force)


def check_hooks(repo_root: Path | None = None) -> int:
    """Lazy wrapper to avoid RuntimeWarning on ``-m`` invocation."""

    from fa.hygiene.hooks.status import check_hooks as _check_hooks

    return _check_hooks(repo_root=repo_root)


__all__ = ["HOOK_NAMES", "check_hooks", "install_hooks"]
