"""Single source of truth for where FA keeps its state (S5.4.5 / Q17).

Why this module exists
----------------------
``scripts/fa-entrypoint.sh`` has always honoured ``FA_STATE_ROOT``::

    local state_root="${FA_STATE_ROOT:-${HOME}/.fa}"

and passes it to ``fa.session.manager provision --state-root``. No Python code
read the variable: the root was independently re-derived as
``Path.home() / ".fa"`` in fifteen places. With ``FA_STATE_ROOT`` set, the
entrypoint provisioned one directory while the run resolved another — a
split-brain session in which ``fa run`` cannot see what was provisioned for it.

Design
------
Call-time resolution with an environment override is the standard shape for CLI
state directories (XDG; ``platformdirs``; Poetry's ``POETRY_CONFIG_DIR``). The
anti-pattern it replaces — a module-level constant bound at import — is exactly
what made the V10 session-log leak invisible, so nothing here may be cached at
import time.

Stdlib only, deliberately: the repo has neither ``platformdirs`` nor an XDG
helper, and minimalism-first argues against a dependency for one resolver.

Relative and blank overrides are **ignored** rather than resolved against the
current working directory. A state root that moves with the CWD is a quiet
data-loss hazard (a run started from a different directory silently gets a
different, empty state tree), and ignoring them follows the XDG convention.
"""

from __future__ import annotations

import os
from pathlib import Path

STATE_ROOT_ENV_VAR = "FA_STATE_ROOT"
_STATE_DIR_NAME = ".fa"


def fa_state_root() -> Path:
    """Return the FA state root, honouring ``FA_STATE_ROOT``.

    Resolution order:

    1. ``FA_STATE_ROOT`` when it is set to an **absolute** path;
    2. otherwise ``~/.fa`` — byte-identical to the historical default, so
       existing installs need no migration.

    Resolved on every call so a caller that reconfigures its environment (an
    embedder, a test, the container entrypoint) is honoured rather than
    silently ignored.
    """
    override = os.environ.get(STATE_ROOT_ENV_VAR, "").strip()
    if override:
        candidate = Path(override)
        if candidate.is_absolute():
            return candidate
    return Path.home() / _STATE_DIR_NAME


def fa_session_log_root() -> Path:
    """Return the per-run session-log root (``<state root>/session-log``)."""
    return fa_state_root() / "session-log"


__all__ = ["STATE_ROOT_ENV_VAR", "fa_session_log_root", "fa_state_root"]
