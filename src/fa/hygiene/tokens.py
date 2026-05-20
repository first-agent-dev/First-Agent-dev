"""Conservative classifier for backticked tokens in agent docs (R-13).

Ports Gortex ``internal/audit/tokens.go`` (156 LOC) — conservative
rules to keep false-positive rate low on tool names (``search_symbols``)
and option keys (``older_than``) inside agent-facing documentation.

A backticked token is one of:

- **identifier** — a name worth checking against the source tree
  (e.g. ``MyClass``, ``namespace::Func``, ``do_thing()``). Identifiers
  trigger dead-reference audits.
- **shell_verb** — a hard-skip list of common shell utilities
  (``grep``, ``ls``, ``git``, ``cat``, …). Never treated as
  identifiers even when uppercased.
- **prose** — everything else (lowercase one-word backticked terms
  without ``::`` qualifier or ``()`` suffix).

A token qualifies as ``identifier`` when AT LEAST ONE of the
following holds (Gortex rule):

1. Contains an uppercase ASCII letter — e.g. ``MyClass``, ``ADR-7``.
2. Contains a ``::`` qualifier — e.g. ``ns::func``.
3. Ends with an explicit ``()`` suffix — e.g. ``do_thing()``.

Empty strings or strings entirely outside ``[A-Za-z0-9_:.()-]`` are
classified as ``prose``.
"""

from __future__ import annotations

import re
from enum import StrEnum

_HARD_SKIP_SHELL_VERBS: frozenset[str] = frozenset(
    {
        "awk",
        "bash",
        "cat",
        "cd",
        "chmod",
        "chown",
        "cp",
        "curl",
        "echo",
        "find",
        "git",
        "grep",
        "head",
        "less",
        "ls",
        "make",
        "mkdir",
        "more",
        "mv",
        "npm",
        "ps",
        "pwd",
        "rg",
        "rm",
        "sed",
        "sh",
        "sort",
        "ssh",
        "tail",
        "tar",
        "touch",
        "uniq",
        "wc",
        "wget",
        "which",
        "yarn",
        "zsh",
    }
)

_TOKEN_BODY = re.compile(r"`([^`\n]+)`")
_VALID_IDENTIFIER_CHARS = re.compile(r"^[A-Za-z0-9_:.()\-/]+$")
_HAS_UPPER = re.compile(r"[A-Z]")
_QUALIFIER = re.compile(r"::")
_CALL_SUFFIX = re.compile(r"\(\s*\)$")


class TokenKind(StrEnum):
    """Three exhaustive token kinds returned by :func:`classify_token`."""

    IDENTIFIER = "identifier"
    SHELL_VERB = "shell_verb"
    PROSE = "prose"


def classify_token(token: str) -> TokenKind:
    """Classify a single backticked ``token`` body (no surrounding
    backticks).

    Conservative — defaults to ``PROSE`` for anything ambiguous so
    audit pressure does not spike on plain-English docs.
    """

    candidate = token.strip()
    if not candidate:
        return TokenKind.PROSE
    if not _VALID_IDENTIFIER_CHARS.fullmatch(candidate):
        return TokenKind.PROSE
    # Case-folded lookup so capitalised variants (`Git`, `GREP`, `Ls`)
    # are also skipped — the docstring promises "Never treated as
    # identifiers even when uppercased". Devin Review finding
    # 2026-05-20 on PR #18.
    if candidate.lower() in _HARD_SKIP_SHELL_VERBS:
        return TokenKind.SHELL_VERB
    if _HAS_UPPER.search(candidate):
        return TokenKind.IDENTIFIER
    if _QUALIFIER.search(candidate):
        return TokenKind.IDENTIFIER
    if _CALL_SUFFIX.search(candidate):
        return TokenKind.IDENTIFIER
    return TokenKind.PROSE


def classify_tokens(text: str) -> dict[TokenKind, list[str]]:
    """Extract backticked tokens from ``text`` and bucket them by kind.

    The text is scanned in source order; duplicates are preserved
    so callers can compute frequency without an extra pass. Inline
    code spans crossing line boundaries are skipped (the regex
    forbids embedded newlines, matching Gortex).
    """

    buckets: dict[TokenKind, list[str]] = {
        TokenKind.IDENTIFIER: [],
        TokenKind.SHELL_VERB: [],
        TokenKind.PROSE: [],
    }
    for match in _TOKEN_BODY.finditer(text):
        body = match.group(1)
        buckets[classify_token(body)].append(body)
    return buckets


__all__ = ["TokenKind", "classify_token", "classify_tokens"]
