#!/usr/bin/env python3
"""Record every gate's output and compare two recordings by *finding*, not by count.

Why this exists (E608): a count cannot prove "no new red". Mid-S1 the mypy error
count went 83 -> 65 -> 62 while *three* of those errors were mine: four vanished
and three appeared, and only a set difference showed it. Counting failures answers
"how bad", and the question that decides a merge is "did I add any".

Two commands, both stdlib-only:

    gate_tracker.py record --label base --out notes/gates/2026-11-22-base
    gate_tracker.py record --label head --out notes/gates/2026-11-22-head
    gate_tracker.py compare notes/gates/2026-11-22-base notes/gates/2026-11-22-head

``record`` runs each gate, keeps the raw log beside a normalised finding list, and
writes ``summary.json``. ``compare`` prints and saves the new/gone sets per gate and
exits 1 when anything is new -- that exit code is the gate.

``--reuse`` ingests a log that already exists (a 25-minute suite should be run once),
and ``--cwd``/``--pythonpath`` record a *worktree* of another commit, which is how a
baseline is produced without touching the working tree.

Normalisation deliberately drops line and column numbers, because they drift with
every unrelated edit; a finding is ``file: message`` for mypy, ``file: CODE message``
for ruff, and the nodeid for pytest.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

# scripts/ is not a pip-installed package; shim sys.path when invoked as a file,
# matching check_dead_flags.py. The compare table draws box characters, so the
# stdio must be UTF-8 even on a cp1251 console (tests/test_console_encoding.py).
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._console import force_utf8_stdio

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


@dataclass(frozen=True)
class Gate:
    """One gate: how to run it, and how to turn its output into findings."""

    name: str
    argv: Callable[[Path], Sequence[str]]
    parse: Callable[[str], list[str]]


# ── parsers ───────────────────────────────────────────────────────────────────


def _parse_pytest(log: str) -> list[str]:
    """Failing and erroring nodeids.

    ``-rf`` puts one line per failure at the end; collection errors use ``ERROR``.
    The message after `` - `` is dropped: it embeds tmp paths and hash digests, and
    two runs of the same failing test rarely produce the same one.
    """
    findings: list[str] = []
    for line in _strip_ansi(log).splitlines():
        match = re.match(r"^(FAILED|ERROR) (\S+)", line)
        if match:
            findings.append(f"{match.group(1)} {match.group(2)}")
    return sorted(set(findings))


def _parse_mypy(log: str) -> list[str]:
    findings: list[str] = []
    for line in _strip_ansi(log).splitlines():
        match = re.match(r"^(?P<path>[^:]+\.py):\d+(?::\d+)?: error: (?P<msg>.*)$", line)
        if match:
            findings.append(f"{match.group('path')}: {match.group('msg')}")
    return sorted(findings)


_RUFF_CONCISE = re.compile(r"^(?P<path>[^:]+\.py):\d+:\d+: (?P<msg>[A-Z]+\d+.*)$")
_RUFF_CODE = re.compile(r"^(?P<msg>[A-Z]+\d+(?: \[\*\])? .*)$")
_RUFF_LOCATION = re.compile(r"^\s*--> (?P<path>[^:]+):\d+:\d+$")


def _parse_ruff(log: str) -> list[str]:
    """Recognise both of ruff's output shapes (E609).

    ``--output-format=concise`` puts the location on the line (``path:l:c: CODE msg``);
    the default *full* shape puts the code and message on one line and the location
    on the next (``F401 [*] msg`` / ``--> path:34:42``). Parsing only the first shape
    is how a recording reported "findings=0" while ruff exited 1 with an unused
    import -- the gate silently reading clean, which is the failure it exists to stop.
    """
    findings: list[str] = []
    pending: str | None = None
    for line in _strip_ansi(log).splitlines():
        concise = _RUFF_CONCISE.match(line)
        if concise:
            findings.append(f"{concise.group('path')}: {concise.group('msg')}")
            pending = None
            continue
        code = _RUFF_CODE.match(line)
        if code:
            pending = code.group("msg")
            continue
        location = _RUFF_LOCATION.match(line)
        if location and pending is not None:
            findings.append(f"{location.group('path')}: {pending}")
            pending = None
    return sorted(findings)


_RUFF_FORMAT_SUMMARY = re.compile(r"^Would reformat: (?P<path>\S+)$")


def _parse_ruff_format(log: str) -> list[str]:
    """The formatter's findings, in **both** shapes ruff prints them (E613).

    The first draft of this parser recognised only ``Would reformat: <path>`` and
    recorded ``findings=0`` while ruff exited 1 -- the same silent-clean failure as
    E609, reproduced in the very file that documents it. Ruff 0.16's ``--check``
    emits a diagnostic instead::

        unformatted: File would be reformatted
          --> tests/mutation/mut_step9.py:1:1

    so the marker line is paired with the location that follows it, and the older
    one-line summary shape is still accepted. The trailing "N files would be
    reformatted" summary is not a finding: a count is what this tool refuses.
    """
    findings: list[str] = []
    pending = False
    for line in _strip_ansi(log).splitlines():
        stripped = line.strip()
        if stripped.startswith("unformatted:"):
            pending = True
            continue
        if pending:
            location = _RUFF_LOCATION.match(line)
            if location:
                findings.append(f"{location.group('path')}: would-reformat")
            pending = False
            continue
        summary = _RUFF_FORMAT_SUMMARY.match(stripped)
        if summary:
            findings.append(f"{summary.group('path')}: would-reformat")
    return sorted(findings)


def _parse_authoring_check(log: str) -> list[str]:
    """The check reports counts, not per-item lines; the exit code is the finding."""
    text = _strip_ansi(log)
    diagnostics = re.search(r"diagnostics:\s*(\d+)", text)
    if diagnostics is None:
        return []
    if int(diagnostics.group(1)) == 0:
        return []
    return [f"diagnostics={diagnostics.group(1)}"]


# ── gates ─────────────────────────────────────────────────────────────────────


def _fa() -> str:
    """The console script beside this interpreter, so a venv's `fa` is the one used."""
    candidate = Path(sys.executable).parent / "fa"
    return str(candidate) if candidate.exists() else "fa"


GATES: tuple[Gate, ...] = (
    Gate(
        "pytest",
        lambda _cwd: [
            sys.executable,
            "-m",
            "pytest",
            "tests",
            "-q",
            "-p",
            "no:cacheprovider",
            "--tb=no",
            "-rf",
        ],
        _parse_pytest,
    ),
    Gate("mypy", lambda _cwd: [sys.executable, "-m", "mypy"], _parse_mypy),
    # Concise output is the shape the parser reads best; both are accepted.
    Gate("ruff", lambda _cwd: [sys.executable, "-m", "ruff", "check", "--output-format=concise"], _parse_ruff),
    # E613: `just lint` checks the formatter too; a recording that skipped it
    # reported green while four files had drifted, so it is a recorded gate now.
    Gate(
        "ruff-format",
        lambda _cwd: [sys.executable, "-m", "ruff", "format", "--check", "."],
        _parse_ruff_format,
    ),
    Gate("authoring-check", lambda _cwd: [_fa(), "authoring-check"], _parse_authoring_check),
)


def _by_name(name: str) -> Gate:
    for gate in GATES:
        if gate.name == name:
            return gate
    raise SystemExit(f"unknown gate {name!r}; known: {', '.join(g.name for g in GATES)}")


def _env(pythonpath: Path | None) -> dict[str, str]:
    env = dict(os.environ)
    if pythonpath is not None:
        # An editable install would otherwise import the *main* tree's package, which
        # turns a baseline into a measurement of the wrong commit.
        env["PYTHONPATH"] = str(pythonpath)
    return env


def record(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cwd = Path(args.cwd).resolve()
    env = _env(Path(args.pythonpath).resolve() if args.pythonpath else None)
    gates_summary: dict[str, dict[str, object]] = {}
    summary: dict[str, object] = {"label": args.label, "cwd": str(cwd), "gates": gates_summary}
    for name in args.gate or [gate.name for gate in GATES]:
        gate = _by_name(name)
        log_path = out / f"{gate.name}.log"
        if args.reuse and gate.name in args.reuse:
            raw = Path(args.reuse[gate.name]).read_text(encoding="utf-8", errors="replace")
            log_path.write_text(raw, encoding="utf-8")
            findings = gate.parse(raw)
            code = None
        else:
            completed = subprocess.run(
                list(gate.argv(cwd)), cwd=cwd, env=env, capture_output=True, text=True, check=False
            )
            raw = completed.stdout + completed.stderr
            log_path.write_text(raw, encoding="utf-8")
            findings = gate.parse(raw)
            code = completed.returncode
        (out / f"{gate.name}.findings.txt").write_text(
            "\n".join(findings) + ("\n" if findings else ""), encoding="utf-8"
        )
        if code not in (None, 0) and not findings:
            # E609/E613: a gate that fails while the parser sees nothing is a parser
            # bug, not a clean gate. Naming it here is what stops a recording from
            # reporting "0 findings" beside a non-zero exit.
            findings = [f"{gate.name}: unrecognised failure (exit {code})"]
            (out / f"{gate.name}.findings.txt").write_text(findings[0] + "\n", encoding="utf-8")
        gates_summary[gate.name] = {"exit": code, "findings": len(findings), "log": log_path.name}
        print(f"{gate.name:16} exit={code} findings={len(findings)}", file=sys.stderr)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def _findings(directory: Path, gate: str) -> set[str]:
    path = directory / f"{gate}.findings.txt"
    if not path.exists():
        return set()
    return {line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def compare(args: argparse.Namespace) -> int:
    base = Path(args.base)
    head = Path(args.head)
    lines: list[str] = []
    new_total = 0
    for gate in GATES:
        before = _findings(base, gate.name)
        after = _findings(head, gate.name)
        recorded = ((base / f"{gate.name}.findings.txt").exists(), (head / f"{gate.name}.findings.txt").exists())
        if not any(recorded):
            continue
        if recorded != (True, True):
            # A gate recorded on one side only cannot be compared. Reporting its
            # findings as "gone" would read as a fix (E610: a cheap partial head
            # recording made pytest's two known failures look repaired), so it is
            # named as missing and excluded from the total instead.
            missing = base if not recorded[0] else head
            lines.append(f"## {gate.name}: not recorded in {missing} — skipped, not counted")
            lines.append("")
            continue
        new = sorted(after - before)
        gone = sorted(before - after)
        new_total += len(new)
        lines.append(f"## {gate.name}: {len(before)} known -> {len(after)} now, {len(new)} new, {len(gone)} gone")
        lines.extend(f"+ {item}" for item in new)
        lines.extend(f"- {item}" for item in gone)
        lines.append("")
    lines.append(f"NEW TOTAL: {new_total}")
    report = "\n".join(lines)
    print(report)
    (head / "compare.md").write_text(report + "\n", encoding="utf-8")
    (head / "compare.json").write_text(
        json.dumps({"new_total": new_total, "base": str(base), "head": str(head)}, indent=2) + "\n",
        encoding="utf-8",
    )
    return 1 if new_total else 0


def main(argv: Sequence[str] | None = None) -> int:
    force_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("record", help="run (or ingest) every gate and store its findings")
    rec.add_argument("--label", required=True, help="free-form name: base, head, after-fix-2 ...")
    rec.add_argument("--out", required=True, help="directory for logs, findings and summary.json")
    rec.add_argument("--cwd", default=".", help="tree to run in (a worktree records another commit)")
    rec.add_argument("--pythonpath", default=None, help="PYTHONPATH for that tree (editable installs lie otherwise)")
    rec.add_argument("--gate", action="append", help="restrict to these gates (repeatable)")
    rec.add_argument(
        "--reuse",
        action="append",
        default=None,
        metavar="GATE=LOG",
        help="ingest an existing log instead of running the gate, e.g. --reuse pytest=/tmp/suite.log",
    )
    rec.set_defaults(func=record)

    cmp_ = sub.add_parser("compare", help="diff two recordings; exit 1 when anything is new")
    cmp_.add_argument("base")
    cmp_.add_argument("head")
    cmp_.set_defaults(func=compare)

    args = parser.parse_args(argv)
    reuse: dict[str, str] = {}
    for item in (args.reuse or []) if args.command == "record" else []:
        if "=" not in item:
            raise SystemExit(f"--reuse wants GATE=LOG, got {item!r}")
        gate, _, log = item.partition("=")
        if gate not in {candidate.name for candidate in GATES}:
            raise SystemExit(f"--reuse names an unknown gate {gate!r}")
        reuse[gate] = log
    args.reuse = reuse
    handler: Callable[[argparse.Namespace], int] = args.func
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
