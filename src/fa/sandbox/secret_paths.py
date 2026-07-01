"""Fail-closed tripwire: deny ``fs.run_bash`` reads of known secret paths (ADR-12).

Security posture (read this before changing anything):

* This is a **tripwire + audit layer**, NOT the primary boundary. The real
  boundary for LLM provider keys is the egress-injection proxy (those keys do
  not exist in the agent container at all). This module's job is defense in
  depth and, specifically, to protect the GitHub **deploy key** which still
  lives in the agent container for ``git push``.
* It is deliberately fail-closed: an unparseable command that *mentions* a
  secret prefix anywhere is denied rather than allowed.

Why a tripwire and not a hard guarantee: ``fs.run_bash`` runs ``shell=True`` as
the same uid as the agent, so a sufficiently creative command (``cd`` into the
directory, shell variable indirection, etc.) can read a file the process can
open. We catch the direct and common indirect forms here and rely on the
model-egress redactor (so a read value cannot reach the LLM) and, for LLM keys,
on the proxy boundary. The airtight closure for the deploy key is the
constrained-git follow-up recorded in BACKLOG.
"""

from __future__ import annotations

import shlex
from collections.abc import Iterable
from pathlib import Path

__all__ = [
    "SECRET_PATH_PREFIXES",
    "command_reads_secret_path",
    "default_secret_prefixes",
]


def default_secret_prefixes() -> frozenset[str]:
    """Absolute path prefixes that must never be read by the agent shell.

    Resolved lazily so the user-home expansion reflects the runtime user
    (container ``fa`` → ``/home/fa/.fa/.env``; dev box → the dev user's home).
    """
    prefixes = {
        "/run/secrets",
        "/srv/first-agent/secrets",
    }
    # WSL/dev fallback location of the private key file.
    prefixes.add(str((Path.home() / ".fa").resolve()))
    return frozenset(prefixes)


# Snapshot for callers that want the static container locations without home
# expansion side effects. ``command_reads_secret_path`` always recomputes the
# home-expanded set so this constant is a convenience, not the source of truth.
SECRET_PATH_PREFIXES: frozenset[str] = frozenset({"/run/secrets", "/srv/first-agent/secrets"})


def _normalize(token: str) -> str:
    """Lexically normalize a path-like token to an absolute string.

    No filesystem access (pure lexical), so this is side-effect free and works
    in tests without the paths existing. Handles ``/proc/self/root`` rewriting
    (a common containment bypass) and leading ``~``.
    """
    t = token.strip()
    if not t:
        return ""
    # Strip a redirection target's surrounding quotes already handled by shlex.
    # Rewrite /proc/<pid>/root/<X> and /proc/self/root/<X> → /<X> so a secret
    # reached through the proc root view is still caught.
    for marker in ("/proc/self/root", "/proc/1/root"):
        if t.startswith(marker):
            t = t[len(marker) :] or "/"
    if t.startswith("~"):
        t = str(Path(t).expanduser())
    # Lexical absolute-ization + collapse of ``..`` / ``.`` without touching FS.
    p = Path(t)
    if not p.is_absolute():
        # Relative tokens are resolved against an UNKNOWN cwd; we cannot know it
        # lexically. The caller handles the ``cd <secretdir>`` form separately;
        # here we only resolve absolute references.
        return t
    return _lexical_abs(p)


def _lexical_abs(p: Path) -> str:
    """Collapse ``.`` and ``..`` in an absolute path lexically (no FS access)."""
    parts: list[str] = []
    for part in p.parts:
        if part == "/" or part == "":  # pragma: no mutate
            continue
        if part == ".":  # pragma: no mutate
            continue  # pragma: no mutate
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/" + "/".join(parts)


def _within(path_str: str, prefix: str) -> bool:
    if not path_str:
        return False
    a = path_str.rstrip("/")  # pragma: no mutate
    b = prefix.rstrip("/")  # pragma: no mutate
    return a == b or a.startswith(b + "/")


def command_reads_secret_path(
    command: str,
    *,
    extra_prefixes: Iterable[str] = (),
) -> bool:
    """Return True if ``command`` appears to read a known secret path.

    Fail-closed strategy:

    1. Tokenize with ``shlex``. For every token, lexically normalize it and
       check containment against the secret prefixes. (Catches
       ``cat /run/secrets/fa.env``, ``sed -n 1p /run/secrets/fa.env``,
       ``xxd /run/secrets/git_key``, ``cat /proc/self/root/run/secrets/...``.)
    2. Catch the ``cd <secretdir> && cat file`` form: if any token *is* a secret
       directory (the cwd would then be inside it), deny.
    3. If tokenization fails (unparseable / unterminated quote) but the raw
       string contains a secret prefix substring, deny (fail-closed).
    """
    prefixes = set(default_secret_prefixes()) | {str(p) for p in extra_prefixes}

    tokens = _safe_tokens(command)
    if tokens is None:
        # Unparseable: fail closed if the command text references a secret dir.
        return any(prefix in command for prefix in prefixes)

    # Defense-in-depth: raw substring check even if tokenization succeeds.
    # This prevents bypasses where a secret path is embedded inside a string
    # evaluated by another interpreter (e.g. `python -c "open('/run/secrets/...')"`).
    # Since there's no legitimate reason for an agent to mention a secret path
    # anywhere in a command string, we fail-closed if it's found at all.
    for pref in prefixes:
        if pref in command:
            return True

    for tok in tokens:
        for candidate in _path_candidates(tok):
            norm = _normalize(candidate)
            if not norm.startswith("/"):
                continue
            # Token resolves *inside* a secret prefix → a direct read.
            # ``cat /run/secrets/fa.env``, ``dd if=/run/secrets/fa.env``.
            if any(_within(norm, pref) for pref in prefixes):
                return True
            # Token *is* a secret directory → ``cd /run/secrets`` style, after
            # which a relative read would escape this lexical check. Deny the
            # whole command. Only an EXACT prefix match (not a mere ancestor
            # like ``/run``) so legitimate ``ls /run`` stays allowed.
            if any(norm.rstrip("/") == pref.rstrip("/") for pref in prefixes):  # pragma: no mutate
                return True  # pragma: no mutate

    return False


def _path_candidates(token: str) -> list[str]:
    """Yield path-like substrings from a token.

    Handles bare paths (``/run/secrets/fa.env``) and ``key=value`` operands
    such as ``if=/run/secrets/fa.env`` (``dd``) or ``--file=/run/secrets/x``.
    """
    out = [token]
    if "=" in token:
        out.append(token.split("=", 1)[1])
    return out


def _safe_tokens(command: str) -> list[str] | None:
    try:
        return shlex.split(command, posix=True)  # pragma: no mutate
    except ValueError:
        return None
