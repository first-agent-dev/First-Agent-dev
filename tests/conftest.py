"""Shared pytest fixtures.

Currently one concern: keeping the suite hermetic with respect to the real
user's ``~/.fa`` (CT11 — "tests may mutate only ``tmp_path``/temporary
fixtures").
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_fa_session_log_root(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Give every test its own session-log root instead of the real ``~/.fa``.

    Ten tests construct ``SessionState(workspace_root=tmp_path, run_id=...)``
    without an explicit ``log=``. That path falls back to the session-log root,
    so each was creating ``~/.fa/session-log/<run_id>/session.db`` on the
    developer's machine and reusing it on every subsequent run. Eight such
    directories were found during the S5.0 audit, their names matching those
    tests exactly.

    The leak was invisible while the Blackboard used ``INSERT OR REPLACE``: a
    stale row from the previous run was silently overwritten. S5.3 made writes
    append-only, at which point the reused row surfaced as
    ``blackboard_duplicate_id`` — the affected test passed once on a clean box
    and failed on every rerun.

    Fixing the ten call sites individually would treat the symptom; the next
    test written the same way reintroduces it. Patching this one seam closes the
    class.

    **Scope is deliberately narrow.** An earlier attempt patched ``Path.home``
    globally and broke 25 tests that legitimately assert home-relative constants
    (``DEFAULT_MODELS_YAML_PATH`` and friends), because those modules bind their
    own paths at import time and would then disagree with a moved ``$HOME``.
    Only the session-log root — the thing tests actually write to — is
    redirected here.

    **S5.4.5 update.** This now sets ``FA_STATE_ROOT`` rather than patching
    ``default_state_root`` directly. Since every production site derives from
    ``fa.paths.fa_state_root()``, the general contract subsumes the special
    case: the whole state tree moves together, and the fixture no longer has to
    know which function to stub. Patching the function would also hide the
    resolver from the very tests that verify it.
    """
    root = tmp_path_factory.mktemp("fa-state")
    monkeypatch.setenv("FA_STATE_ROOT", str(root))

    # A test that sets ``HOME`` itself is asserting home-relative behaviour on
    # purpose (26 do). ``FA_STATE_ROOT`` outranks ``HOME`` in the resolver, so
    # leaving it set would override that intent and make those tests measure
    # this fixture instead of the code. Drop the override the moment a test
    # takes control of ``HOME``, restoring the default derivation.
    real_setenv = monkeypatch.setenv

    def _setenv(name: str, value: str, prepend: str | None = None) -> None:
        real_setenv(name, value, prepend)
        if name == "HOME":
            monkeypatch.delenv("FA_STATE_ROOT", raising=False)

    monkeypatch.setattr(monkeypatch, "setenv", _setenv, raising=False)
