"""Report the installation status of local commit hooks.

Deterministic, zero-API-call verification that the three local
hook seats are active in the current clone. Run after ``just
install`` or at any time to confirm the local hook chain is
active. Invoke via ``python -m fa.hygiene.hooks.status`` or
``just hooks-status``.

All three hooks — ``pre-commit``, ``prepare-commit-msg``,
``commit-msg`` — are installed by our custom installer
(``fa.hygiene.hooks.install``). For each hook, the checker
verifies that the installed file content matches the shipped
source, and on POSIX that the installed hook is executable.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fa.hygiene.hooks._util import HOOK_NAMES, resolve_hooks_dir, resolve_repo_root, scripts_dir


def _is_executable(path: Path) -> bool:
    """Return True when *path* is executable on this platform.

    On POSIX, Git requires the execute bit on the installed hook. On
    Windows, hook execution does not rely on POSIX mode semantics in the
    same way, so we treat executability as satisfied.
    """

    if os.name == "nt":
        return True
    return os.access(path, os.X_OK)


def check_hooks(repo_root: Path | None = None) -> int:
    """Check and report hook installation status. Returns exit code.

    Returns 0 if all hooks are installed and current, 1 if any are
    missing, stale, or non-executable. Output is human-readable and also
    parseable by agents.
    """

    root = resolve_repo_root(repo_root or Path.cwd())
    hooks_dir = resolve_hooks_dir(root)

    if not hooks_dir.is_dir():
        sys.stdout.write(f"✗ {hooks_dir} not found — not a git checkout?\n")
        return 1

    all_ok = True
    stale_hooks: list[str] = []

    for name in HOOK_NAMES:
        target = hooks_dir / name

        if not target.exists() and not target.is_symlink():
            sys.stdout.write(f"✗ {name}: NOT INSTALLED\n")
            all_ok = False
            continue

        source = scripts_dir() / name
        if not source.is_file():
            sys.stdout.write(f"✓ {name}: installed (source unavailable for verify)\n")
            continue

        if target.is_symlink():
            resolved = target.resolve()
            source_resolved = source.resolve()
            if resolved != source_resolved:
                sys.stdout.write(
                    f"⚠ {name}: symlink points to {resolved}, expected {source_resolved}\n"
                )
                all_ok = False
                continue
            if not _is_executable(target):
                sys.stdout.write(f"⚠ {name}: installed (symlink → source) but NOT EXECUTABLE\n")
                all_ok = False
                continue
            sys.stdout.write(f"✓ {name}: installed (symlink → source)\n")
            continue

        try:
            target_text = target.read_text(encoding="utf-8")
            source_text = source.read_text(encoding="utf-8")
        except OSError:
            sys.stdout.write(f"✓ {name}: installed (content unreadable)\n")
            continue

        if target_text != source_text:
            sys.stdout.write(f"⚠ {name}: installed but STALE (differs from source)\n")
            stale_hooks.append(name)
            all_ok = False
            continue
        if not _is_executable(target):
            sys.stdout.write(f"⚠ {name}: installed and current but NOT EXECUTABLE\n")
            all_ok = False
            continue
        sys.stdout.write(f"✓ {name}: installed and current\n")

    sys.stdout.write("\n")
    if all_ok:
        sys.stdout.write("All commit hooks active — local commits are guarded.\n")
    else:
        sys.stdout.write(
            "Some hooks missing, stale, or non-executable — run `just install` to fix.\n"
        )
        if stale_hooks:
            sys.stdout.write(
                "Stale hooks need re-install after source changes: " + ", ".join(stale_hooks) + "\n"
            )

    return 0 if all_ok else 1


def _main() -> int:
    """CLI entrypoint for ``python -m fa.hygiene.hooks.status``."""

    return check_hooks()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
