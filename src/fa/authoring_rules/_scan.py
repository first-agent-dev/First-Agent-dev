"""Shared helpers for Level-1 rules (ADR-11; src/fa/authoring_rules).

Internal-only: not exported from the package. Centralises the
file-iteration + parse + scope-filter preamble that every AST-based
rule otherwise duplicates, satisfying the strict pylint
``duplicate-code`` gate while keeping each rule module focused on its
own diagnostic logic.
"""

from __future__ import annotations

import ast
import hashlib
from collections.abc import Iterator
from pathlib import Path

from fa.authoring_tcb import RuleContext

# Corpora directories holding fixtures that intentionally violate the
# rules (catch-corpus) or known-clean diffs the rules must NOT flag
# (fp-corpus, blueprint Appendix B PR 4). Skip them in every Level-1
# rule so a fixture cannot fail the regular kernel run.
_CORPUS_PREFIXES: tuple[str, ...] = ("catch-corpus/", "fp-corpus/")

# Top-level path prefixes Level-1 rules consume.  Hoisted here so all
# rule packs reference one definition; the rule modules import these
# instead of re-declaring private copies.  PR-14-deferred manifest
# integration (backlog I-12-bis) will let `.fa/session.toml [scope]`
# override these defaults; until then they are the v0.1 contract.
SRC_SCOPE: tuple[str, ...] = ("src/",)
TEST_SCOPE: tuple[str, ...] = ("tests/",)


def sha256(data: bytes) -> str:
    """Return the canonical ``sha256:<hex>`` form used in
    :attr:`fa.authoring_tcb.RuleResult.rule_input_hash`."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def iter_python_files(
    context: RuleContext,
    *,
    included_prefixes: tuple[str, ...],
) -> Iterator[tuple[str, bytes, ast.Module]]:
    """Yield ``(rel, source_bytes, tree)`` for each in-scope ``.py`` file.

    A file is in scope when (a) it ends in ``.py``, (b) its repo-relative
    POSIX path starts with one of ``included_prefixes``, and (c) it does
    NOT start with a corpus prefix (:data:`_CORPUS_PREFIXES`). Files
    that fail to parse are silently skipped — other tooling (ruff /
    mypy) reports syntax errors so the authoring kernel must not
    double-up the signal.
    """
    for rel in context.files:
        if not rel.endswith(".py"):
            continue
        if any(rel.startswith(prefix) for prefix in _CORPUS_PREFIXES):
            continue
        if not any(rel.startswith(prefix) for prefix in included_prefixes):
            continue
        source_bytes = (context.repo_root / Path(rel)).read_bytes()
        try:
            tree = ast.parse(source_bytes, filename=rel)
        except SyntaxError:
            continue
        yield rel, source_bytes, tree


def node_input_hash(source_bytes: bytes, node: ast.AST) -> str:
    """Hash the exact bytes the rule consumed (ADR-11-I2 / §9.2).

    Uses :func:`ast.get_source_segment` to extract the substring backing
    ``node``; falls back to a whole-file hash when position info is
    insufficient (e.g. synthetic nodes).
    """
    try:
        segment = ast.get_source_segment(source_bytes.decode("utf-8"), node)
    except (UnicodeDecodeError, ValueError):
        segment = None
    if segment is None:
        return sha256(source_bytes)
    return sha256(segment.encode("utf-8"))
