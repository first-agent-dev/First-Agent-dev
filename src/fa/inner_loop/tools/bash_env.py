"""Allowlist-scrubbed environment for ``fs.run_bash`` (secret-isolation, ADR-12).

Defense-in-depth layer 3: even though API keys are no longer placed in
``os.environ`` (Phase 2), the ``fs.run_bash`` child process is given an
**allowlisted** environment so that, should any secret-bearing variable ever
re-enter the parent environment, the agent's shell (and anything it spawns)
still inherits nothing sensitive.

Two-stage filter:
1. **Allowlist** — only names in :data:`DEFAULT_BASH_ENV_ALLOWLIST` (plus
   optional operator additions) pass through.
2. **Fail-closed secret filter** — :data:`SECRET_NAME_RE` is applied AFTER the
   allowlist, so even an allowlisted/operator-added name is dropped if it looks
   like a credential. The allowlist can only ever *add non-secret* names.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

__all__ = [
    "DEFAULT_BASH_ENV_ALLOWLIST",
    "SECRET_NAME_RE",
    "build_scrubbed_env",
]

# Names the agent's shell legitimately needs. Deliberately minimal.
DEFAULT_BASH_ENV_ALLOWLIST: frozenset[str] = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "SHELL",
        "PWD",
        "TERM",
        "TZ",
        "LANG",
        # FA runtime needs (set by the image/compose, not secret):
        "PYTHONPATH",
        "PYTHONUNBUFFERED",
        "PYTHONDONTWRITEBYTECODE",
        "UV_CACHE_DIR",
        "FA_WORKSPACE",
        # Git push uses the deploy key, which lives OUTSIDE the sandbox (ro mount
        # at /run/secrets) — the command string is not a secret value.
        "GIT_SSH_COMMAND",
    }
)

# Prefixes that are always allowed (locale family). Checked in addition to the
# exact allowlist above.
_ALLOWED_PREFIXES: tuple[str, ...] = ("LC_", "GIT_")

# Fail-closed: drop anything whose NAME looks like a credential, even if it was
# allowlisted or added by an operator override. Case-insensitive.
SECRET_NAME_RE = re.compile(
    r"(?i)(API[_-]?KEY|ACCESS[_-]?KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL|"
    r"_KEY$|^KEY$|PRIVATE)"
)


def _is_allowed_name(name: str, extra: frozenset[str]) -> bool:
    if name in DEFAULT_BASH_ENV_ALLOWLIST or name in extra:
        return True
    return any(name.startswith(p) for p in _ALLOWED_PREFIXES)


def build_scrubbed_env(
    source: Mapping[str, str],
    *,
    extra_allow: Iterable[str] = (),
) -> dict[str, str]:
    """Return a scrubbed copy of ``source`` safe to hand to the agent shell.

    Keeps only allowlisted names, then drops any name matching
    :data:`SECRET_NAME_RE` (fail-closed). ``extra_allow`` lets an operator add
    *non-secret* names; the secret filter still applies on top, so a credential
    name can never be re-exposed via the override.
    """
    extra = frozenset(extra_allow)
    out: dict[str, str] = {}
    for name, value in source.items():
        if not _is_allowed_name(name, extra):
            continue
        if SECRET_NAME_RE.search(name):
            continue  # fail-closed: never pass a credential-looking name
        out[name] = value
    return out
