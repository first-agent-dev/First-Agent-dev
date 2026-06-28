"""Install the local commit hooks into ``.git/hooks/``.

The repository's ``.pre-commit-config.yaml`` defines which checks run
at commit time (ruff, gitleaks, markdownlint, uv-lock, etc.), and the
``pre-commit`` framework executes them.  This installer puts all three
hook seats into ``.git/hooks/`` — including the ``pre-commit`` hook
itself, which invokes the framework via ``uv run`` so it works
reliably on Windows/PowerShell where the framework's own generated
hook script cannot find the ``pre-commit`` executable in PATH.

The installer prefers symlinks (so the hook always reflects the
current source after a ``git pull``), but falls back to copying
on platforms where symlinks require elevated privileges (Windows
without Developer Mode).  This fallback ensures ``just install``
works reliably across all contributor environments.

Invoke via ``python -m fa.hygiene.hooks.install`` or programmatically
via :func:`install_hooks`.  The ``just install-hooks`` recipe
delegates here, so ``just`` and direct invocation share one code path.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from fa.hygiene.hooks._util import resolve_repo_root, scripts_dir

HOOK_NAMES: tuple[str, ...] = ("pre-commit", "prepare-commit-msg", "commit-msg")


def _install_one(
    source: Path,
    target: Path,
    *,
    force: bool = False,
) -> Path:
    """Link or copy a single hook script into ``.git/hooks/``.

    Prefers a symlink so the installed hook always reflects the
    current source (important after ``git pull``).  Falls back to a
    plain copy when symlinks are unavailable (Windows without
    Developer Mode).

    When ``force=True``, any existing file or symlink at *target*
    is replaced; otherwise an existing real (non-symlink) file is
    preserved and :class:`FileExistsError` is raised.
    """

    if target.exists() or target.is_symlink():
        if not force and not target.is_symlink():
            raise FileExistsError(
                f"{target} exists and is not a symlink; pass force=True to overwrite."
            )
        target.unlink()

    # On Windows, symlinks in .git/hooks/ may not be followed by
    # Git for Windows at hook-execution time (even though they
    # resolve correctly for reads).  Force copies on Windows to
    # ensure the hook script content is directly in .git/hooks/.
    if sys.platform == "win32":
        shutil.copy2(source, target)
    else:
        try:
            os.symlink(source, target)
        except OSError:
            # Symlink failed (unlikely on non-Windows, but possible
            # on unusual filesystems).  Fall back to a plain copy.
            shutil.copy2(source, target)

    # Ensure both the source script AND the installed target are
    # executable.  Symlink permissions come from the source file,
    # so chmod-ing the source is sufficient for symlink installs.
    # For copy fallback, copy2 preserves the source's permission
    # bits — so the target also needs chmod when the source was
    # checked out without the execute bit (common on Windows where
    # core.fileMode=false).  Without this, git silently skips the
    # hook because it checks executability before running any hook.
    for path in (source, target):
        try:
            current_mode = path.stat().st_mode
            path.chmod(current_mode | 0o111)
        except OSError:
            pass

    return target


def install_hooks(
    repo_root: Path | None = None,
    *,
    force: bool = False,
) -> list[Path]:
    """Install the PR-intent hooks into ``<repo_root>/.git/hooks/``.

    Returns the list of installed hook paths. When ``force=True``,
    any existing file or symlink at the target path is replaced;
    otherwise an existing non-symlink file is preserved and the
    function raises :class:`FileExistsError`.
    """

    root = resolve_repo_root(repo_root or Path.cwd())
    hooks_dir = root / ".git" / "hooks"
    if not hooks_dir.is_dir():
        raise SystemExit(
            f"fa.hygiene.hooks.install: {hooks_dir} does not exist; is this a git checkout?"
        )

    src_dir = scripts_dir()
    installed: list[Path] = []
    for name in HOOK_NAMES:
        source = src_dir / name
        if not source.is_file():
            raise SystemExit(f"fa.hygiene.hooks.install: missing hook script {source}")
        target = _install_one(source, hooks_dir / name, force=force)
        installed.append(target)
    return installed


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m fa.hygiene.hooks.install",
        description=(
            "Install the PR-intent hooks (prepare-commit-msg, commit-msg) into .git/hooks/."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing files / symlinks at the target paths",
    )
    args = parser.parse_args(argv)

    installed = install_hooks(force=args.force)
    for path in installed:
        method = "symlink" if path.is_symlink() else "copy"
        sys.stdout.write(f"installed ({method}): {path}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests.
    raise SystemExit(_main())
