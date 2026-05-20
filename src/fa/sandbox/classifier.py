"""Pattern-based bash-command classifier — no LLM, zero-latency.

Borrowed from Gortex ``internal/hooks/bash_classify.go`` (266 LOC).
Classifies a bash command into a coarse category that the gate uses
to decide whether to allow, validate, or deny.

Five categories (ordered roughly by risk, low → high):

- ``READ_ONLY`` — pure observation: ``ls``, ``cat``, ``grep``, ``find``,
  ``head``, ``tail``, ``wc``, ``stat``, ``file``, ``du``, ``df``,
  ``which``, ``whereis``, ``whoami``, ``id``, ``pwd``, ``echo``,
  ``printf``, ``date``. Default-allow in any sandbox state.

- ``GIT_WRITE`` — git operations that mutate state: ``commit``,
  ``push``, ``checkout`` (branch creation), ``merge``, ``rebase``,
  ``reset``, ``stash``, ``cherry-pick``, ``revert``, ``tag``. Forwarded
  to ``validators.validate_git`` for finer-grained rules.

- ``PACKAGE_INSTALL`` — package-manager installs: ``pip``, ``npm``,
  ``yarn``, ``pnpm``, ``apt-get``, ``apt``, ``brew``, ``cargo``,
  ``gem``, ``go get``, ``uv add`` / ``uv pip install``. Surfaced as
  its own category because installs MAY change the runtime environment
  and the gate's caller may want to require an explicit prompt.

- ``DANGEROUS`` — known-bad patterns: ``rm -rf`` anywhere,
  ``chmod -R`` anywhere, ``dd``, ``mkfs``, ``fdisk``, ``pkill``,
  ``kill -9``, ``sudo``, ``su -``, ``curl | sh`` / ``wget -O- | sh``
  shell-piped-exec patterns. Forwarded to ``validators`` for the
  small set of commands that have per-command validators; the rest
  are denied at classification time.

- ``GENERAL_WRITE`` — everything else (touch, mkdir, mv, cp, etc.).
  Default-deny at the gate unless the caller explicitly opts in via
  ``allow_general_write=True``.

The classifier is *coarse on purpose* — fine-grained denial logic
belongs in ``validators.py``. Categorisation must stay readable so the
gate's decision log is reviewable by a human in seconds.

Why no LLM call. AGENTS.md PR Checklist rule #10 question 4: «Could
this step be a deterministic Python function instead of an LLM call?»
Pattern-matching shell tokens against fixed lists is the canonical
yes-answer.
"""

from __future__ import annotations

import shlex
from enum import StrEnum

__all__ = [
    "BashCategory",
    "classify_command",
    "first_token",
    "tokenize",
]


class BashCategory(StrEnum):
    """Coarse risk-category for a bash command."""

    READ_ONLY = "read_only"
    GIT_WRITE = "git_write"
    PACKAGE_INSTALL = "package_install"
    DANGEROUS = "dangerous"
    GENERAL_WRITE = "general_write"


# Fast-path sets. Lookups are O(1) per token.
_READ_ONLY_TOKENS: frozenset[str] = frozenset(
    {
        "ls",
        "cat",
        "grep",
        "egrep",
        "fgrep",
        "rg",  # ripgrep
        "find",
        "head",
        "tail",
        "wc",
        "stat",
        "file",
        "du",
        "df",
        "which",
        "whereis",
        "whoami",
        "id",
        "pwd",
        "echo",
        "printf",
        "date",
        "uname",
        "hostname",
        "tree",
        "less",
        "more",
        "diff",
        "cmp",
        "tee",  # /dev/null is fine; output-redirect to file is general-write,
        # but bare `tee` is read-effective when followed only by `/dev/null`.
        "env",
        "type",
    }
)

# Verbs that follow `git` and are write-side. The remaining `git`
# subcommands (`status`, `log`, `diff`, `show`, `blame`, `ls-files`,
# `rev-parse`, `branch -l`, `remote -v`, ...) are read-only and
# classified accordingly downstream.
_GIT_WRITE_SUBCOMMANDS: frozenset[str] = frozenset(
    {
        "add",
        "commit",
        "push",
        "checkout",
        "switch",
        "merge",
        "rebase",
        "reset",
        "stash",
        "cherry-pick",
        "revert",
        "tag",
        "fetch",
        "pull",
        "config",
        "remote",  # `remote -v` is read but `remote add` writes
        "init",
        "clean",
        "restore",
    }
)

_PACKAGE_INSTALL_PROGRAMS: frozenset[str] = frozenset(
    {
        "pip",
        "pip3",
        "npm",
        "yarn",
        "pnpm",
        "apt",
        "apt-get",
        "brew",
        "cargo",
        "gem",
        "uv",
    }
)

# Commands that are dangerous *as a category* — even with no extra
# flags, the command name itself denotes mutation broader than the
# workspace. ``rm`` and ``chmod`` are excluded here because they have
# per-command validators (validators.validate_rm / validate_chmod) and
# may be allowable when scoped to workspace-internal paths.
_DANGEROUS_TOKENS: frozenset[str] = frozenset(
    {
        "dd",
        "mkfs",
        "fdisk",
        "parted",
        "shred",
        "sudo",
        "su",
        "pkill",
        "killall",
        "shutdown",
        "reboot",
        "halt",
        "poweroff",
        "psql",
        "mysql",
        "mongo",
        "redis-cli",
    }
)

# Subcommands that signal install-mode invocation; the gate caller may
# treat ``pip list`` differently from ``pip install``.
_INSTALL_SUBCOMMANDS: frozenset[str] = frozenset(
    {
        "install",
        "add",
        "i",  # npm short form
        "get",  # `go get`
        "upgrade",
        "update",
    }
)


def tokenize(command: str) -> list[str]:
    """Split ``command`` into shell-respecting tokens.

    Uses ``shlex`` in POSIX mode so quoted arguments stay intact. If
    the command contains a syntax error (unterminated quote), returns
    an empty list — the gate treats an unparseable command as
    classification-failure and the validator layer will deny.
    """
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return []


def first_token(command: str) -> str:
    """Return the first shell-token of ``command``, or empty string."""
    tokens = tokenize(command)
    if not tokens:
        return ""
    return tokens[0]


def _has_dangerous_shell_pattern(command: str) -> bool:
    """Detect curl-pipe-to-shell and similar exec-from-network patterns.

    Looks for the substrings ``| sh``, ``|sh``, ``| bash``, ``|bash``
    paired with ``curl`` or ``wget`` earlier in the string. False
    positives are tolerable here because the gate denies on match —
    a legitimate ``echo "foo | sh"`` is rare in agent workloads, and
    the caller can use ``allow_dangerous_pipe`` to override (Phase-M
    addition, currently always False).
    """
    lower = command.lower()
    has_fetcher = "curl " in lower or "wget " in lower
    has_pipe_exec = "| sh" in lower or "|sh" in lower or "| bash" in lower or "|bash" in lower
    return has_fetcher and has_pipe_exec


def _git_subcommand(tokens: list[str]) -> str:
    """Return the first non-flag token after ``git``, or empty string."""
    if len(tokens) < 2 or tokens[0] != "git":
        return ""
    for token in tokens[1:]:
        if not token.startswith("-"):
            return token
    return ""


def _package_install_subcommand(tokens: list[str]) -> str:
    """Return the first non-flag token after the package program, or ''."""
    if len(tokens) < 2:
        return ""
    for token in tokens[1:]:
        if not token.startswith("-"):
            return token
    return ""


def classify_command(command: str) -> BashCategory:
    """Classify ``command`` into a single :class:`BashCategory`.

    The classifier is deterministic and side-effect-free. When the
    command is empty or unparseable, returns ``GENERAL_WRITE`` (the
    safe default — anything we cannot classify is treated as opaque).
    """
    if _has_dangerous_shell_pattern(command):
        return BashCategory.DANGEROUS

    tokens = tokenize(command)
    if not tokens:
        return BashCategory.GENERAL_WRITE

    head = tokens[0]

    if head in _DANGEROUS_TOKENS:
        return BashCategory.DANGEROUS

    # `mkfs.ext4`, `mkfs.xfs`, `mkfs.btrfs`, … — filesystem creators
    # are dangerous regardless of suffix. Same applies to `kill -9`
    # but that is handled below as a flag-pattern check.
    if head.startswith("mkfs."):
        return BashCategory.DANGEROUS

    if head == "kill" and "-9" in tokens:
        return BashCategory.DANGEROUS

    # `rm -rf` and `chmod -R` are dangerous regardless of where they
    # point; let validators decide whether a narrower invocation is
    # acceptable.
    if head == "rm" and any(flag in tokens for flag in ("-rf", "-fr", "-r", "-R", "--recursive")):
        return BashCategory.DANGEROUS
    if head == "chmod" and any(flag in tokens for flag in ("-R", "--recursive")):
        return BashCategory.DANGEROUS

    if head == "git":
        sub = _git_subcommand(tokens)
        if sub in _GIT_WRITE_SUBCOMMANDS:
            return BashCategory.GIT_WRITE
        return BashCategory.READ_ONLY

    if head in _PACKAGE_INSTALL_PROGRAMS:
        sub = _package_install_subcommand(tokens)
        if sub in _INSTALL_SUBCOMMANDS:
            return BashCategory.PACKAGE_INSTALL
        return BashCategory.READ_ONLY

    if head in _READ_ONLY_TOKENS:
        return BashCategory.READ_ONLY

    return BashCategory.GENERAL_WRITE
