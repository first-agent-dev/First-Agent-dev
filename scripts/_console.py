#!/usr/bin/env python3
"""UTF-8 console output + shared CLI helpers for gate scripts.

Two concerns live here so gate scripts do not re-invent them:

1. ``force_utf8_stdio()`` — make stdout/stderr UTF-8 capable everywhere
   (see the historical note below about the Windows cp1251 failure mode).
2. Shared argparse fragments for scripts that share the same CLI surface
   (``--repo-root``, ``--output text|json``). Centralising these kills
   the ``duplicate-code`` (R0801) cross-file warning between gate
   scripts that all end up with the same 8-line argparse boilerplate.

Stdlib-only by construction — this sits next to ``check_tcb_stdlib.py``
and is imported by TCB-adjacent gates.

Why force_utf8_stdio exists
---------------------------
``just check`` failed on a Windows 11 host with a Russian locale::

    File "scripts/check_dependency_contract.py", line 105, in main
        print("  \\u2705 All pyproject.toml deps are in the contract")
    UnicodeEncodeError: 'charmap' codec can't encode character '\\u2705'

**The check had PASSED.** It crashed while printing its own success message,
exited 1, and blocked the push. A gate that fails when the thing it guards is
healthy is worse than no gate: it trains people to bypass it.

Root cause: on Windows, Python still derives ``sys.stdout``'s encoding from the
ANSI code page (``cp1251`` for a Russian install), not UTF-8. Every ``✅``,
``❌``, ``─`` and ``→`` in a gate script is therefore an unencodable character
waiting for a non-UTF-8 host. Linux and macOS default to UTF-8, so CI and the
authoring machine never saw it — the failure is invisible until someone runs
the gate on Windows.

Why this shape
--------------
Three alternatives were considered and rejected for the UTF-8 helper:

1. **Set ``PYTHONUTF8=1`` / ``PYTHONIOENCODING`` in the justfile.** Fixes the
   ``just`` path only. The same scripts are invoked by git hooks, by CI, and
   by hand; each would need the variable, and a missed path fails exactly the
   way this bug already did. An environment fix cannot be enforced by a test.
2. **Strip the non-ASCII characters.** Bulletproof, but it rewrites ~420
   box-drawing characters and loses the scanability the output was designed
   for. It also does not stop the next author typing ``✅``.
3. **``reconfigure()`` inline in each script.** Correct, but duplicated seven
   times with nothing keeping the copies in step.

This module is the shared version of (3), and ``tests/test_console_encoding.py``
enforces that every script printing non-ASCII actually calls it — so an eighth
script cannot reintroduce the bug silently.

``errors="replace"`` rather than ``"strict"``
---------------------------------------------
If reconfiguration is somehow impossible, a gate must still be able to report
its verdict. Losing a tick mark to ``?`` is acceptable; losing the exit code to
a traceback is not. The whole defect was a diagnostic crashing on decoration.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO


def force_utf8_stdio() -> None:
    """Make ``sys.stdout``/``sys.stderr`` UTF-8 capable, idempotently.

    Call once, at the top of ``main()`` or immediately after the imports, in
    any script that may print non-ASCII. Safe to call repeatedly and safe on
    platforms that are already UTF-8 (it is then a no-op in effect).

    Never raises: a console that refuses reconfiguration must not take the
    gate's exit code with it.
    """
    for stream in (sys.stdout, sys.stderr):
        _reconfigure(stream)


def _reconfigure(stream: TextIO | None) -> None:
    if stream is None:  # pragma: no cover - pythonw / detached console
        return
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:  # pragma: no cover - a non-TextIOWrapper stream
        return
    try:
        reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):  # pragma: no cover
        # Detached console, a closed stream, or an object that only pretends to
        # be a TextIOWrapper. Degrade silently: the caller's verdict matters
        # more than its formatting.
        return


# ---------------------------------------------------------------------------
# Shared argparse fragments for gate scripts
# ---------------------------------------------------------------------------
#
# R0801 (duplicate-code) fires when several gate scripts each define the same
# ``--repo-root`` and ``--output`` arguments. Centralising the add_argument
# calls here keeps the CLI surface consistent AND eliminates the duplicate.
# Functions return the parser back so callers can chain or add further args.


def add_repo_root_arg(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Add the standard ``--repo-root`` argument (default: ``Path.cwd()``)."""
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root (default: current directory).",
    )
    return parser


def add_output_arg(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Add the standard ``--output {text,json}`` argument (default: ``text``)."""
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text).",
    )
    return parser


def resolve_repo_root(args: argparse.Namespace) -> Path:
    """Resolve ``args.repo_root`` to an absolute path (shorthand helper)."""
    repo_root = args.repo_root
    if not isinstance(repo_root, Path):
        raise TypeError("args.repo_root must be a pathlib.Path")
    return repo_root.resolve()


__all__ = [
    "add_output_arg",
    "add_repo_root_arg",
    "force_utf8_stdio",
    "resolve_repo_root",
]
