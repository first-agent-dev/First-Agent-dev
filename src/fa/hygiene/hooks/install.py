"""Install the PR-intent git hooks into ``.git/hooks/``.

The repository's ``.pre-commit-config.yaml`` covers the
``pre-commit`` stage (ruff, markdownlint, …) but does not install
``prepare-commit-msg`` or ``commit-msg`` hook types by default. This
installer fills that gap by symlinking the two shell scripts
shipped under :mod:`fa.hygiene.hooks` into the repo's
``.git/hooks/`` directory.

Bare symlinks (rather than ``pre-commit install --hook-type
prepare-commit-msg ...``) keep the PR-B diff strictly inside
``src/fa/hygiene/**`` per the M-6 BACKLOG row's scope-fence,
without modifying ``.pre-commit-config.yaml``. The deferred
decision in BACKLOG.md §M-6 (pre-commit framework vs. bare
symlinks) is resolved in favour of bare symlinks for that
reason; switching to the framework remains a future CHORE PR
when the repo's hook-discipline conventions evolve.

Invoke via ``python -m fa.hygiene.hooks.install`` or programmatically
via :func:`install_hooks`.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HOOK_NAMES: tuple[str, ...] = ("prepare-commit-msg", "commit-msg")


def _scripts_dir() -> Path:
    """Return the directory holding the bash hook scripts."""

    return Path(__file__).resolve().parent


def _resolve_repo_root(start: Path) -> Path:
    """Anchor-on-cwd workspace resolution per AGENTS.md (no walk-up)."""

    if (start / "knowledge" / "llms.txt").is_file():
        return start
    raise SystemExit(
        "fa.hygiene.hooks.install: not a First-Agent workspace (no knowledge/llms.txt at cwd)"
    )


def install_hooks(
    repo_root: Path | None = None,
    *,
    force: bool = False,
) -> list[Path]:
    """Symlink the PR-intent hooks into ``<repo_root>/.git/hooks/``.

    Returns the list of installed hook paths. When ``force=True``,
    any existing file or symlink at the target path is replaced;
    otherwise an existing non-symlink file is preserved and the
    function raises :class:`FileExistsError`.
    """

    root = _resolve_repo_root(repo_root or Path.cwd())
    hooks_dir = root / ".git" / "hooks"
    if not hooks_dir.is_dir():
        raise SystemExit(
            f"fa.hygiene.hooks.install: {hooks_dir} does not exist; is this a git checkout?"
        )

    src_dir = _scripts_dir()
    installed: list[Path] = []
    for name in HOOK_NAMES:
        source = src_dir / name
        if not source.is_file():
            raise SystemExit(f"fa.hygiene.hooks.install: missing hook script {source}")
        target = hooks_dir / name
        if target.exists() or target.is_symlink():
            if not force and not target.is_symlink():
                raise FileExistsError(
                    f"{target} exists and is not a symlink; pass force=True to overwrite."
                )
            target.unlink()
        os.symlink(source, target)
        # Ensure the script is executable (symlink target permissions
        # come from the source file, but a freshly-checked-out source
        # may not have the bit set on every platform / git mode).
        try:
            current_mode = source.stat().st_mode
            source.chmod(current_mode | 0o111)
        except OSError:
            pass
        installed.append(target)
    return installed


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m fa.hygiene.hooks.install",
        description=(
            "Symlink the PR-intent hooks (prepare-commit-msg, commit-msg) into .git/hooks/."
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
        sys.stdout.write(f"installed: {path}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests.
    raise SystemExit(_main())
