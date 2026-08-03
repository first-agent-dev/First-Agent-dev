"""Gate scripts must survive a non-UTF-8 console (Windows cp1251 and friends).

**The incident this closes.** `just check` failed on a Windows 11 host with a
Russian locale::

    File "scripts/check_dependency_contract.py", line 105, in main
        print("  \\u2705 All pyproject.toml deps are in the contract")
    UnicodeEncodeError: 'charmap' codec can't encode character '\\u2705'

The dependency contract was **satisfied**. The script crashed printing its own
success line, exited 1, and blocked a push. Four of the five `just check`
script gates had the same defect, so fixing them one at a time would have meant
four more failed pushes.

Linux and macOS default to UTF-8, so CI and the authoring machine never saw it.
That is exactly why this needs a test rather than a fixed round of edits: the
bug is invisible on the platforms where the code is written.

Test classes: **C1** (static source contract) and **C2** (the scripts actually
executed against a cp1251 console).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"

# Scripts that are pure library helpers or have no console output worth
# guarding. Everything else under scripts/ is checked.
_EXEMPT = {"_console.py", "__init__.py"}


def _script_files() -> list[Path]:
    return sorted(p for p in SCRIPTS.rglob("*.py") if p.name not in _EXEMPT)


def _prints_non_ascii(text: str) -> bool:
    return any(ord(ch) > 127 for ch in text)


def _non_cp1251_chars(text: str) -> set[str]:
    """Characters that a cp1251 console cannot encode."""
    bad = set()
    for ch in set(text):
        if ord(ch) < 128:
            continue
        try:
            ch.encode("cp1251")
        except UnicodeEncodeError:
            bad.add(ch)
    return bad


def test_scripts_with_non_ascii_output_force_utf8() -> None:
    """C1: any script containing non-ASCII must call ``force_utf8_stdio()``.

    This is the part that prevents recurrence. Fixing the seven known scripts
    solves today's push; this assertion is what stops an eighth from shipping a
    checkmark and rediscovering the bug on someone's Windows box.

    Deliberately keyed on "contains non-ASCII" rather than on a hand-maintained
    list — a list is another thing to forget to update.

    Oracle: source text contains a non-cp1251 character AND does not import the
    helper.
    Kill-check target: remove the ``force_utf8_stdio()`` call from any patched
    script → this fails naming it.
    """
    offenders: dict[str, str] = {}
    for path in _script_files():
        text = path.read_text(encoding="utf-8")
        bad = _non_cp1251_chars(text)
        if not bad:
            continue
        if "force_utf8_stdio" in text:
            continue
        sample = " ".join(sorted(bad)[:6])
        offenders[str(path.relative_to(REPO_ROOT))] = sample

    assert not offenders, (
        "these scripts print characters a cp1251 console cannot encode but do not "
        "call force_utf8_stdio() — they will crash on a non-UTF-8 Windows host, "
        "possibly WHILE REPORTING SUCCESS:\n"
        + "".join(f"  - {name}: {chars}\n" for name, chars in offenders.items())
        + "\nFix: add `from _console import force_utf8_stdio` + `force_utf8_stdio()` "
        "after the imports (see scripts/_console.py)."
    )


def test_the_check_is_live() -> None:
    """C1 liveness: the scan actually sees scripts, and at least one is non-ASCII.

    Without this, a broken glob or a renamed directory would make the test above
    pass vacuously — the failure mode this workstream has hit repeatedly. If the
    repo ever legitimately drops all non-ASCII output, this is the test that
    says so out loud rather than letting the guard quietly become decoration.
    """
    files = _script_files()
    assert len(files) >= 10, f"only {len(files)} scripts found — the scan is broken"

    with_non_ascii = [p for p in files if _prints_non_ascii(p.read_text(encoding="utf-8"))]
    assert with_non_ascii, (
        "no script contains non-ASCII any more. If that is deliberate, this guard "
        "is now vacuous — delete it or re-scope it, do not leave it passing."
    )


@pytest.mark.parametrize(
    "script",
    [
        "check_dependency_contract.py",
        "check_log_kind_contract.py",
        "check_no_mocked_dataclasses.py",
        "check_producer_consumer_contract.py",
        "check_tcb_stdlib.py",
    ],
)
def test_gate_scripts_survive_a_cp1251_console(script: str) -> None:
    """C2: each `just check` gate runs to completion with a cp1251 console.

    The static test above proves the helper is *called*; this proves it
    *works*, by running the real script the way the operator did.
    ``PYTHONIOENCODING=cp1251`` reproduces the original traceback exactly on an
    unpatched tree — verified before the fix.

    Oracle: no ``UnicodeEncodeError``, and the exit code is the gate's real
    verdict (0 here, since the repo is healthy) rather than an encoding
    accident.
    Kill-check target: ``force_utf8_stdio()`` in that script → this fails with
    the original traceback.
    """
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1251"

    result = subprocess.run(
        [sys.executable, str(SCRIPTS / script)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        env=env,
        check=False,
    )

    assert "UnicodeEncodeError" not in result.stderr, f"{script} crashed on a cp1251 console:\n{result.stderr[-1500:]}"
    assert result.returncode == 0, (
        f"{script} exited {result.returncode} under cp1251 — the gate's verdict must "
        f"not depend on the console encoding.\nstderr: {result.stderr[-1000:]}"
    )


def test_force_utf8_stdio_is_idempotent_and_never_raises() -> None:
    """C0p: the helper is safe to call twice and on an already-UTF-8 console.

    It runs at import time in seven scripts, some of which may be imported by
    tests or by each other. A helper that throws on a second call, or on a
    stream it cannot reconfigure, would turn a formatting concern into an
    outage — the precise inversion this whole fix exists to undo.

    Oracle: two consecutive calls complete and stdout is still usable.
    Kill-check target: the ``try/except`` in ``_reconfigure``.
    """
    from scripts._console import force_utf8_stdio

    force_utf8_stdio()
    force_utf8_stdio()
    print("")  # stdout still works


# ── The READ side (added after a second Windows failure) ────────────────────
#
# The first version of this module guarded only console OUTPUT. The very next
# gate then failed on the same machine for the mirror-image reason:
#
#     source = py_file.read_text()
#     UnicodeDecodeError: 'charmap' codec can't decode byte 0x98 ...
#
# `Path.read_text()` with no `encoding=` uses the LOCALE encoding, so a gate
# that reads UTF-8 source files explodes on any non-UTF-8 host. Same root
# cause, opposite direction — and a reminder that fixing the reported symptom
# is not the same as fixing the class.


def _bare_text_io_calls(path: Path) -> list[tuple[int, str]]:
    """AST-locate `read_text`/`write_text`/text-mode `open` without `encoding=`.

    AST rather than a regex: this workstream has manufactured a fictional
    finding from a regex over source before, and `open(..., "rb")` must not be
    flagged while `open(...)` must be.
    """
    import ast

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:  # pragma: no cover - a script that does not parse
        return []

    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            name = node.func.attr
        elif isinstance(node.func, ast.Name):
            name = node.func.id
        else:
            continue
        if name not in {"read_text", "write_text", "open"}:
            continue
        if any(kw.arg == "encoding" for kw in node.keywords):
            continue
        if name == "open":
            mode = None
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                mode = node.args[1].value
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = kw.value.value
            # Binary mode has no encoding, and `os.open` takes an int flag.
            if mode is None or "b" in str(mode):
                continue
        hits.append((node.lineno, name))
    return hits


def test_scripts_declare_encoding_on_text_io() -> None:
    """C1: no gate script reads or writes text without an explicit encoding.

    **The second Windows failure, and the one the first fix missed.**
    `check_producer_consumer_contract.py` called `py_file.read_text()` on the
    repo's own UTF-8 test files; on a cp1251 host that raised
    `UnicodeDecodeError` at byte 0x98 and failed the gate.

    Output encoding and input encoding are independent failure modes with the
    same root cause. Guarding one and not the other is how the second bug
    reached the same operator on the next command they ran.

    Oracle: AST scan for `read_text`/`write_text`/text-mode `open` with no
    `encoding=` keyword.
    Kill-check target: drop `encoding="utf-8"` from any call in
    `scripts/check_producer_consumer_contract.py` → this fails naming file and
    line.
    """
    offenders: dict[str, list[str]] = {}
    for path in _script_files():
        hits = _bare_text_io_calls(path)
        if hits:
            offenders[str(path.relative_to(REPO_ROOT))] = [f"line {ln}: {fn}()" for ln, fn in hits]

    assert not offenders, (
        "these scripts do text I/O without an explicit encoding and will use the "
        "LOCALE encoding — they crash on a non-UTF-8 host (cp1251 Windows):\n"
        + "".join(f"  - {name}: {', '.join(calls)}\n" for name, calls in offenders.items())
        + '\nFix: pass encoding="utf-8" explicitly. Repo source is UTF-8; the '
        "platform default is not."
    )


@pytest.mark.parametrize(
    "script",
    [
        "check_dependency_contract.py",
        "check_log_kind_contract.py",
        "check_no_mocked_dataclasses.py",
        "check_producer_consumer_contract.py",
        "check_tcb_stdlib.py",
    ],
)
def test_gate_scripts_survive_a_non_utf8_locale(script: str) -> None:
    """C2: each gate runs to completion when the LOCALE is not UTF-8.

    The sibling of the cp1251-console test above, for the read side.
    ``LC_ALL=C`` with UTF-8 mode disabled makes `Path.read_text()` default to
    ASCII, which reproduces the operator's `UnicodeDecodeError` on an unpatched
    tree — verified before the fix.

    Oracle: no `UnicodeDecodeError`/`UnicodeEncodeError`, exit code is the
    gate's real verdict.
    Kill-check target: remove `encoding="utf-8"` from a `read_text` call in
    that script.
    """
    env = dict(os.environ)
    env.update(LC_ALL="C", LANG="C", PYTHONCOERCECLOCALE="0", PYTHONUTF8="0")
    env.pop("PYTHONIOENCODING", None)

    result = subprocess.run(
        [sys.executable, str(SCRIPTS / script)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        env=env,
        check=False,
    )

    for err in ("UnicodeDecodeError", "UnicodeEncodeError"):
        assert err not in result.stderr, f"{script} raised {err} under a non-UTF-8 locale:\n{result.stderr[-1500:]}"
    assert result.returncode == 0, (
        f"{script} exited {result.returncode} under LC_ALL=C — a gate's verdict must "
        f"not depend on the host locale.\nstderr: {result.stderr[-1000:]}"
    )
