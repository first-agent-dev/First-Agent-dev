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
# Reviewed duplicate-code waiver: overlaps with
# fa.inner_loop.bash_intent._READ_ONLY_COMMANDS, but the two sets
# intentionally differ (bash_intent includes shell builtins `:`, `[`,
# `test`, `true`, `false`; this set includes `env`, `type`) because they
# classify at different layers. Do NOT blindly merge; if unifying, keep a
# shared core set plus per-layer extensions.
# pylint: disable=duplicate-code
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
        # `tee` deliberately omitted: it copies stdin to one or more *files*
        # in addition to stdout (e.g. ``tee /etc/sudoers``), so it is a write
        # command. It falls through to GENERAL_WRITE where the gate can route
        # it through path-containment / validator checks. The earlier
        # "bare `tee` to /dev/null is read-effective" rationale is true but
        # not enough to mark every `tee` invocation read-only — Agent Review
        # finding 2026-05-20 on PR #20.
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
        "go",  # `go get`/`go install` — _INSTALL_SUBCOMMANDS already lists
        # `get` and `install`; the program name was missing.
        # Agent Review finding 2026-05-20 on PR #20.
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
    """Return the install verb after the package program, or ''.

    Scans **all** non-flag tokens after the head and returns the first one
    that matches :data:`_INSTALL_SUBCOMMANDS`. Falls back to the first
    non-flag token if no install verb is found.

    Why scan instead of taking ``tokens[1]``: package managers like ``uv``
    nest the install verb behind a sub-program name — ``uv pip install
    requests`` has ``pip`` as the first non-flag token, but the real
    install verb is two levels deep at ``install``. Taking only the first
    non-flag token misclassifies ``uv pip install ...`` as
    :attr:`BashCategory.READ_ONLY` and bypasses the package-install gate
    — Agent Review finding 2026-05-20 on PR #23.

    Non-install reads (``pip list``, ``npm ls``) still return their first
    non-flag token (``list`` / ``ls``), which is not in
    ``_INSTALL_SUBCOMMANDS``, so the downstream classifier falls through
    to :attr:`BashCategory.READ_ONLY` unchanged.
    """
    if len(tokens) < 2:
        return ""
    non_flag = [token for token in tokens[1:] if not token.startswith("-")]
    if not non_flag:
        return ""
    # Prefer any token in the install set — catches nested verbs like
    # `uv pip install`.
    for token in non_flag:
        if token in _INSTALL_SUBCOMMANDS:
            return token
    # Fallback: first non-flag token preserves prior behaviour for
    # non-install invocations.
    return non_flag[0]


# Shell control operators that ``shlex.split`` happens to tokenize as
# regular strings but bash interprets as compound-command / redirection
# / pipe markers. Their presence anywhere in the token stream means the
# command head alone cannot describe the command's effect — e.g.
# ``echo evil > /etc/passwd`` has head ``echo`` (READ_ONLY) but writes
# to ``/etc/passwd``. The classifier demotes such commands to
# :attr:`BashCategory.GENERAL_WRITE` (or higher if a danger marker is
# present anywhere). Agent Review finding 2026-05-20 on PR #23.
_SHELL_OPERATOR_TOKENS: frozenset[str] = frozenset(
    {";", "&&", "||", "|", ">", ">>", "<", "<<", "&"}
)


def _has_shell_operator(tokens: list[str]) -> bool:
    """True if any token is a shell compound/redirection/pipe operator."""
    return any(token in _SHELL_OPERATOR_TOKENS for token in tokens)


def _scan_tokens_for_danger(tokens: list[str]) -> BashCategory | None:
    """Scan **all** tokens for DANGEROUS markers, regardless of position.

    Used when a compound command is detected so the chained tail
    (``ls && rm -rf /``) cannot smuggle a danger past the head-only
    dispatch. Returns :attr:`BashCategory.DANGEROUS` on match, ``None``
    otherwise.
    """
    for token in tokens:
        if token in _DANGEROUS_TOKENS:
            return BashCategory.DANGEROUS
        if token.startswith("mkfs."):
            return BashCategory.DANGEROUS
    if "rm" in tokens and any(flag in tokens for flag in ("-rf", "-fr", "-r", "-R", "--recursive")):
        return BashCategory.DANGEROUS
    if "chmod" in tokens and any(flag in tokens for flag in ("-R", "--recursive")):
        return BashCategory.DANGEROUS
    if "kill" in tokens and "-9" in tokens:
        return BashCategory.DANGEROUS
    return None


# C901-baseline waiver (16>15): flat token-dispatch ladder, intentionally
# exhaustive.
def classify_command(command: str) -> BashCategory:  # noqa: C901
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

    # Compound / redirection / pipe — head token is no longer sufficient.
    # Scan the full token stream for danger markers first; otherwise
    # demote to GENERAL_WRITE so the head is never trusted blindly.
    if _has_shell_operator(tokens):
        danger = _scan_tokens_for_danger(tokens)
        if danger is not None:
            return danger
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
        # `go run`/`go build`/`go test`/`go vet` compile-and-execute and
        # so cannot be considered read-only; fall back to GENERAL_WRITE.
        # Other package managers' read subcommands (``pip list``, ``npm ls``)
        # are genuinely read-only.
        if head == "go":
            return BashCategory.GENERAL_WRITE
        return BashCategory.READ_ONLY

    if head in _READ_ONLY_TOKENS:
        return BashCategory.READ_ONLY

    return BashCategory.GENERAL_WRITE
