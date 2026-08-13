"""Install the local git hooks into ``.git/hooks/``.

The repository's ``.pre-commit-config.yaml`` defines fast commit-time checks,
and the ``pre-commit`` framework executes them. This installer puts all four
hook seats into the effective Git hooks directory: ``pre-commit`` (safe autofix
+ targeted restage), ``pre-push`` (``uv run --no-sync just check-deep``),
``prepare-commit-msg``, and ``commit-msg``.

Readiness prewarms framework environments before calling this installer. The
custom shell hooks then invoke project tools via ``uv run --no-sync`` so normal
hook execution cannot mutate dependency state.

The installer prefers symlinks (so the hook always reflects the
current source after a ``git pull``), but falls back to copying
on platforms where symlinks require elevated privileges (Windows
without Developer Mode).  This fallback ensures ``just install``
works reliably across all contributor environments.

Invoke via ``python -m fa.hygiene.hooks.install`` or programmatically via
:func:`install_hooks`. The workspace readiness engine is the primary lifecycle
caller and passes the checked-out hook source directory explicitly.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from fa.hygiene.hooks._util import HOOK_NAMES, resolve_hooks_dir, resolve_repo_root, scripts_dir


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
            raise FileExistsError(f"{target} exists and is not a symlink; pass force=True to overwrite.")
        target.unlink()

    # A symlink is executable only when its source is executable. Never repair a
    # checked-out source in place: doing so dirties the managed workspace and
    # changes the readiness fingerprint while admission is running. If an
    # archive/filesystem stripped the source mode, install an executable copy
    # instead. Windows also requires copies because Git for Windows may not
    # follow hook symlinks at execution time.
    copy_required = sys.platform == "win32" or not os.access(source, os.X_OK)
    if copy_required:
        shutil.copy2(source, target)
    else:
        try:
            os.symlink(source, target)
        except OSError:
            # Symlink failed (unusual filesystem or policy): preserve the
            # tracked source and fall back to an independently executable copy.
            shutil.copy2(source, target)

    # chmod on a symlink follows it and would mutate the tracked source. A
    # symlink was created only for an already-executable source, so chmod only
    # real copy targets. Fail explicitly on POSIX if Git would still skip it.
    if not target.is_symlink():
        current_mode = target.stat().st_mode
        target.chmod(current_mode | 0o111)
    if os.name != "nt" and not os.access(target, os.X_OK):
        raise PermissionError(f"installed hook is not executable: {target}")

    return target


def install_hooks(
    repo_root: Path | None = None,
    *,
    force: bool = False,
    hook_source_dir: Path | None = None,
) -> list[Path]:
    """Install the local FA hooks into ``<repo_root>/.git/hooks/``.

    Returns the list of installed hook paths. ``hook_source_dir`` selects an
    explicit checked-out script directory; omitting it preserves the imported
    package source. When ``force=True``, any existing file or symlink at the
    target path is replaced; otherwise an existing non-symlink file is preserved
    and the function raises :class:`FileExistsError`.
    """

    root = resolve_repo_root(repo_root or Path.cwd())
    hooks_dir = resolve_hooks_dir(root)
    if not hooks_dir.is_dir():
        raise SystemExit(f"fa.hygiene.hooks.install: {hooks_dir} does not exist; is this a git checkout?")

    src_dir = Path(hook_source_dir).expanduser().resolve() if hook_source_dir is not None else scripts_dir()
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
        description=("Install FA local hooks (pre-commit, pre-push, prepare-commit-msg, commit-msg) into .git/hooks/."),
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


__all__ = ["HOOK_NAMES", "install_hooks", "os"]
