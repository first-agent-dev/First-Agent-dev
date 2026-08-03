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
import stat
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


# Artifact posture (S10c.3 / I-36). The FA state root holds the most sensitive
# data the system writes — `llm_bodies.jsonl` carries raw prompt and response
# prose, and `session.db` stores the same content as event rows. `SecretRedactor`
# masks known key *values*; it cannot mask prose. Under the default `umask 0022`
# every one of those was created `0644` while the session manifest was already
# `0600`, i.e. the most sensitive artifacts were the most permissive.
PRIVATE_FILE_MODE = 0o600
PRIVATE_DIR_MODE = 0o700


def private_opener(path: str, flags: int) -> int:
    """``open()`` opener that creates files `0600`, with no world-readable window.

    Pass to the **builtin** ``open()``, not ``Path.open()`` — the pathlib method
    does not accept ``opener`` and raises ``TypeError`` (measured on 3.13).

    Setting the mode in the ``os.open`` syscall is what makes this correct:
    ``chmod``-ing after creation leaves a window in which the file exists and is
    world-readable, which is the defect, not the fix. The mode applies only when
    this call *creates* the file; an existing file keeps its mode, which is why
    :func:`tighten_fa_artifact_modes` exists.
    """
    return os.open(path, flags, PRIVATE_FILE_MODE)


def tighten_fa_artifact_modes(root: Path) -> int:
    """Tighten over-permissive modes under an existing FA state root. Returns the count.

    Retroactive half of I-36 (operator decision Q56: *"do tighten pre-existing
    0644 artifacts — comprehensive tightening pass"*). Creating new files
    privately does nothing for deployments that already have `0644` artifacts on
    disk, and claiming the item is resolved while those files sit there would be
    false.

    Three properties are load-bearing, each verified by a test:

    * **Symlinks are skipped.** ``os.chmod`` FOLLOWS symlinks, and
      ``follow_symlinks=False`` raises ``NotImplementedError`` on Linux
      (``os.chmod not in os.supports_follow_symlinks``). Without an explicit
      skip, a crafted ``session-log/x/evil -> /etc/passwd`` inside the root
      would have its *target's* mode rewritten.
    * **Directories get `0700`, not `0600`.** Stripping the execute bit from a
      directory makes it untraversable and would lock the agent out of its own
      state root.
    * **Tighten only, never widen.** A deliberately stricter mode (e.g. `0400`)
      is preserved; only the group/other bits are cleared.

    Best-effort by design: a mode we cannot change is not worth failing a run
    over, and the caller is a normal command, not a security tool.
    """
    if not root.is_dir():
        return 0
    tightened = 0
    for path in root.rglob("*"):
        # Skipped BEFORE any stat/chmod: see the symlink note above.
        if path.is_symlink():
            continue
        try:
            current = stat.S_IMODE(path.lstat().st_mode)
            if not current & 0o077:
                continue
            path.chmod(current & ~0o077)
            tightened += 1
        except OSError:  # pragma: no cover - unreadable/vanished entries are not fatal
            continue
    return tightened


__all__ = [
    "PRIVATE_DIR_MODE",
    "PRIVATE_FILE_MODE",
    "STATE_ROOT_ENV_VAR",
    "fa_session_log_root",
    "fa_state_root",
    "private_opener",
    "tighten_fa_artifact_modes",
]
