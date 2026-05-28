"""Git-hook shell scripts + installer for the PR-intent gate (PR B — M-6).

The two bash scripts in this directory (``prepare-commit-msg`` and
``commit-msg``) are thin wrappers that invoke
``python -m fa.hygiene.pr_intent {prepare,validate} <commit-msg-file>``.
The Python module owns every classifier / validator decision so the
git-hook seat and the future :class:`fa.inner_loop.hooks.intent_guard.IntentGuard`
harness-side middleware (PR C — M-7) share the same source of truth.

:func:`install_hooks` symlinks the scripts into ``.git/hooks/``;
the repository's existing ``pre-commit`` framework already covers
the ``pre-commit`` stage, so this installer adds only the
``prepare-commit-msg`` / ``commit-msg`` stages that pre-commit
does not register by default.
"""

from __future__ import annotations

from fa.hygiene.hooks.install import HOOK_NAMES, install_hooks

__all__ = ["HOOK_NAMES", "install_hooks"]
