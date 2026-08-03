#!/usr/bin/env python3
"""UTF-8 console output for gate scripts, on every platform.

Why this exists
---------------
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
Three alternatives were considered and rejected:

1. **Set ``PYTHONUTF8=1`` / ``PYTHONIOENCODING`` in the justfile.** Fixes the
   ``just`` path only. The same scripts are invoked by git hooks, by CI, and by
   hand; each would need the variable, and a missed path fails exactly the way
   this bug already did. An environment fix cannot be enforced by a test.
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

Stdlib-only by construction — this sits next to ``check_tcb_stdlib.py`` and is
imported by TCB-adjacent gates.
"""

from __future__ import annotations

import sys
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


__all__ = ["force_utf8_stdio"]
