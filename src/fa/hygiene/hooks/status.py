"""Report the installation status of local commit hooks.

Deterministic, zero-API-call verification that the three local
hook seats are active in the current clone.  Run after ``just
install`` or at any time to confirm the local hook chain is
active.  Invoke via ``python -m fa.hygiene.hooks.status`` or
``just hooks-status``.

All three hooks — ``pre-commit``, ``prepare-commit-msg``,
``commit-msg`` — are installed by our custom installer
(``fa.hygiene.hooks.install``).  For each hook, the checker
verifies that the installed file content matches the shipped
source, so stale hooks (after a ``git pull`` that changed the
source but no re-install) are flagged.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fa.hygiene.hooks._util import resolve_repo_root, scripts_dir

# All three hook seats that should be active after ``just install``.
ALL_HOOK_NAMES: tuple[str, ...] = (
    "pre-commit",
    "prepare-commit-msg",
    "commit-msg",
)


def check_hooks(repo_root: Path | None = None) -> int:
    """Check and report hook installation status.  Returns exit code.

    Returns 0 if all hooks are installed and current, 1 if any are
    missing or stale.  Output is human-readable and also parseable
    by agents.
    """

    root = resolve_repo_root(repo_root or Path.cwd())
    hooks_dir = root / ".git" / "hooks"

    if not hooks_dir.is_dir():
        sys.stdout.write("✗ .git/hooks/ not found — not a git checkout?\n")
        return 1

    all_ok = True
    stale_hooks: list[str] = []

    for name in ALL_HOOK_NAMES:
        target = hooks_dir / name

        if not target.exists() and not target.is_symlink():
            sys.stdout.write(f"✗ {name}: NOT INSTALLED\n")
            all_ok = False
            continue

        # All hooks are managed by our installer — verify content
        # matches the shipped source.
        source = scripts_dir() / name
        if not source.is_file():
            # Source script missing — can't verify content, but
            # the hook file exists.
            sys.stdout.write(f"✓ {name}: installed (source unavailable for verify)\n")
            continue

        if target.is_symlink():
            # Symlink — check where it points.
            resolved = target.resolve()
            source_resolved = source.resolve()
            if resolved == source_resolved:
                sys.stdout.write(f"✓ {name}: installed (symlink → source)\n")
            else:
                sys.stdout.write(
                    f"⚠ {name}: symlink points to {resolved}, expected {source_resolved}\n"
                )
                all_ok = False
            continue

        # Plain file (copy) — compare content with source.
        try:
            target_text = target.read_text(encoding="utf-8")
            source_text = source.read_text(encoding="utf-8")
        except OSError:
            sys.stdout.write(f"✓ {name}: installed (content unreadable)\n")
            continue

        if target_text == source_text:
            sys.stdout.write(f"✓ {name}: installed and current\n")
        else:
            sys.stdout.write(f"⚠ {name}: installed but STALE (differs from source)\n")
            stale_hooks.append(name)
            all_ok = False

    # Summary line.
    sys.stdout.write("\n")
    if all_ok:
        sys.stdout.write("All commit hooks active — local commits are guarded.\n")
    else:
        sys.stdout.write("Some hooks missing or stale — run `just install` to fix.\n")
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
