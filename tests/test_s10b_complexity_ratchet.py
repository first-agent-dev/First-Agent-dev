"""S10b.1 — the C901 complexity ratchet (GAP5 / CT2).

Plan: ``worklogs/implementation-plans/PLAN-cli-trace-S10b-cli-decomposition.md``

**What this module protects.** ``pyproject.toml`` sets
``[tool.ruff.lint.mccabe] max-complexity = 15`` with the comment *"Do not raise
this; lower it as waivers retire."* That instruction had no enforcement: a
future agent could raise the threshold, or add a nineteenth-plus
``# noqa: C901``, and every gate would stay green. An unenforced instruction in
a comment is a wish. This module turns the direction of travel into a
deterministic gate — the budget may only shrink.

**ruff is the authority, and it is not the only opinion.** ``mccabe`` (the
standalone package) scores the same functions **+1 per ``try`` statement**;
measured on a five-line fixture during S10a preflight, the delta equals the
``try`` count in every divergent function (``_cmd_workflow`` 15 vs 17,
``_resolve_task`` 11 vs 15). A gate built on mccabe's number would disagree
with CI permanently, so every number here comes from ruff.

**Measuring TRUE complexity without editing files.** ``ruff check --select
C901`` reports **nothing** today, because the ``# noqa: C901`` comments
suppress it. Asking "is the codebase under the threshold?" therefore requires
seeing past the waivers, which ``ruff check --ignore-noqa`` does directly. That
avoids the alternative (copy the tree, ``sed`` the comments out, re-run), which
is slower and can silently measure a stale copy — a failure mode this
workstream has already hit.

Test class: **C1** (static-quality / configuration contract).
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from tests._capabilities import requires_posix_paths

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_FA = REPO_ROOT / "src" / "fa"

# The C901 waiver budget. This number may ONLY go DOWN.
#
# Lower it in the SAME commit that retires a waiver, so the ratchet and the
# refactor land together and a reviewer sees both halves in one diff. Raising
# it to make a red gate green defeats the entire purpose of the file; if a new
# function genuinely cannot be written under 15, that is a design discussion,
# not a number edit.
_C901_WAIVER_BUDGET = 15

# Liveness control. A census that silently matched nothing would satisfy
# "count <= budget" vacuously — the most common way a gate in this workstream
# has been found inert.
#
# Kept STRICTLY BELOW the budget on purpose (S10b.5). It was briefly equal to
# it at 15, which is a trap: the next legitimate retirement anywhere under
# src/fa would drop the census to 14 and fail the liveness check, and the
# obvious "fix" is to edit the floor down — training exactly the reflex this
# file exists to prevent. A floor below the budget still catches a broken
# census (which yields 0, verified) while leaving room for the ratchet to move.
_C901_CENSUS_FLOOR = 13

_MAX_COMPLEXITY_CEILING = 15

_NOQA_C901 = re.compile(r"#\s*noqa:[^\n]*\bC901\b")


def _waiver_census() -> list[tuple[Path, int, str]]:
    """Every ``# noqa: C901`` under ``src/fa``, as (path, line number, text)."""
    found: list[tuple[Path, int, str]] = []
    for py_file in sorted(SRC_FA.rglob("*.py")):
        for lineno, line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), start=1):
            if _NOQA_C901.search(line):
                found.append((py_file.relative_to(REPO_ROOT), lineno, line.strip()))
    return found


def _true_complexity_findings() -> list[dict[str, object]]:
    """C901 findings with waivers ignored — i.e. real complexity.

    ``--ignore-noqa`` makes ruff report what it *would* report if every
    ``# noqa`` were deleted, without touching the working tree.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--select",
            "C901",
            "--ignore-noqa",
            "--output-format",
            "json",
            str(SRC_FA),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    # ruff exits 1 when it reports findings, which is the normal case here.
    assert result.returncode in (0, 1), (
        f"ruff did not run (exit {result.returncode}); the measurement below would be "
        f"vacuous.\n  stderr: {result.stderr[-2000:]}"
    )
    parsed: list[dict[str, object]] = json.loads(result.stdout)
    return parsed


def test_s10b_c901_waiver_budget() -> None:
    """C1 (S10b.1 / CT2): the number of C901 waivers may only decrease.

    Oracle: a source census of ``# noqa: C901`` under ``src/fa`` compared to
    ``_C901_WAIVER_BUDGET``.

    This is the gate that gives ``pyproject.toml``'s *"lower it as waivers
    retire"* an enforcement seat. Before it, adding a waiver was free.

    Deliberately NOT failing on the existing 19 (plan Do-not): a gate that
    red-lights on the day it lands gets disabled or ignored, and then it
    protects nothing.

    Kill-check target: add a ``# noqa: C901`` anywhere under ``src/fa`` →
    census becomes 20 > 19 → this fails naming the new site.
    """
    census = _waiver_census()

    # Liveness: prove the census mechanism actually found the known waivers.
    # A typo'd regex or a wrong root directory yields an empty list, and
    # "0 <= 19" would pass while measuring nothing at all.
    assert len(census) >= _C901_CENSUS_FLOOR, (
        f"C901 census found only {len(census)} waivers under {SRC_FA}, below the "
        f"liveness floor of {_C901_CENSUS_FLOOR}. Either the census is broken "
        f"(wrong path / regex) or waivers were retired — if the latter, lower "
        f"both _C901_WAIVER_BUDGET and _C901_CENSUS_FLOOR deliberately."
    )

    assert len(census) <= _C901_WAIVER_BUDGET, (
        f"C901 waiver budget exceeded: {len(census)} > {_C901_WAIVER_BUDGET}.\n"
        + "".join(f"  {path}:{line}  {text}\n" for path, line, text in census)
        + "\n  Decompose the function instead of waiving it. This budget may only "
        "be LOWERED, and only in the commit that retires a waiver."
    )


def test_s10b_max_complexity_threshold_not_raised() -> None:
    """C1 (S10b.1 / CT2): ``max-complexity`` can never be raised to silence a failure.

    Oracle: the parsed ``[tool.ruff.lint.mccabe] max-complexity`` value.

    Without this, the cheapest way to make a C901 failure disappear is to edit
    one digit in ``pyproject.toml`` — which would retire every waiver at once
    and destroy the ratchet silently. Parsed from TOML rather than
    substring-matched, so a commented-out setting cannot satisfy it.

    Kill-check target: set ``max-complexity = 20`` → this fails.
    """
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        config = tomllib.load(handle)

    mccabe = config["tool"]["ruff"]["lint"]["mccabe"]
    threshold = mccabe["max-complexity"]

    assert threshold <= _MAX_COMPLEXITY_CEILING, (
        f"[tool.ruff.lint.mccabe] max-complexity is {threshold}, above the ceiling "
        f"of {_MAX_COMPLEXITY_CEILING}. pyproject.toml's own comment says 'Do not "
        f"raise this; lower it as waivers retire.' Raising the threshold retires "
        f"every waiver at once and hides real complexity growth."
    )


@requires_posix_paths
def test_s10b_every_c901_waiver_is_load_bearing() -> None:
    """C1 (S10b.1 / CT2): no waiver sits on a function that is already under threshold.

    Oracle: ruff's own ``--ignore-noqa`` finding set (true complexity) compared
    against the waiver census, matched by file and line.

    **Why this half matters as much as the budget.** A waiver on a simple
    function is dead weight that inflates the budget and makes the ratchet look
    further from done than it is. More importantly, it is how a decomposition
    silently fails to finish: an agent extracts helpers, drops the complexity
    to 12, forgets to delete the ``noqa``, and the budget never moves. This
    test turns that oversight into a failure.

    Verified at authoring time: all 19 waivers are load-bearing — ruff reports
    exactly 19 findings with ``--ignore-noqa``, one per waiver.

    Kill-check target: add ``# noqa: C901`` to a trivial function → it appears
    in the census with no matching finding → this fails.
    """
    findings = _true_complexity_findings()

    # Liveness: the four cli.py offenders are known to exist right now. An
    # empty finding set (bad path, changed CLI, JSON schema drift) would make
    # the subset check below pass vacuously.
    assert len(findings) >= 4, (
        f"ruff --ignore-noqa reported only {len(findings)} C901 findings under "
        f"{SRC_FA}; at least the 4 known cli.py offenders were expected. The "
        f"measurement is broken, not the code."
    )

    over_threshold: set[tuple[str, int]] = {
        (str(Path(str(f["filename"])).resolve().relative_to(REPO_ROOT)), int(f["location"]["row"]))  # type: ignore[index]
        for f in findings
    }

    dead_weight = [
        (path, lineno, text) for path, lineno, text in _waiver_census() if (str(path), lineno) not in over_threshold
    ]

    assert not dead_weight, (
        "these `# noqa: C901` waivers sit on functions that are ALREADY under the "
        "threshold — delete them and lower _C901_WAIVER_BUDGET:\n"
        + "".join(f"  {path}:{line}  {text}\n" for path, line, text in dead_weight)
    )


# Functions whose C901 waiver S10b has RETIRED. Add a name here in the same
# commit that deletes its waiver; never remove one (that would be a silent
# regression back to a waived function).
_RETIRED_WAIVERS = ("_cmd_run", "_cmd_stats", "_discover_stats_sources", "_cmd_selfcheck")


@pytest.mark.parametrize("function_name", _RETIRED_WAIVERS)
def test_s10b_retired_waiver_stays_retired(function_name: str) -> None:
    """C1 (S10b / T3): a retired function has NO waiver **and** is genuinely under 15.

    **Two parts, because either one alone is a check that cannot fail.**

    * *"ruff reports no C901 finding"* alone **passes today and passed before
      any refactor** — ruff emits zero findings while a ``# noqa: C901``
      suppresses them. Shipping that by itself would have been the S7.C3
      tautology for the fourth time in this workstream.
    * *"the waiver comment is absent"* alone passes on a function whose
      complexity is still 39 and whose waiver was merely deleted. CI would then
      fail — but only after merge-time review, which is exactly the feedback
      loop a local gate exists to shorten.

    Only the conjunction proves complexity actually **dropped below the
    threshold**, which is what GAP1 claims.

    Oracle: (a) the function's ``def`` line carries no ``# noqa: C901``, found
    by AST so a waiver on a *different* function cannot satisfy or break it;
    and (b) ruff with ``--ignore-noqa`` reports no C901 finding for it.
    Kill-check target: re-inline any helper extracted in S10b.2 → part (b)
    fails while the behavioural parity suite stays green. That divergence is
    the point: behaviour and structure are measured independently.
    """
    source = (SRC_FA / "cli.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()

    node = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == function_name),
        None,
    )
    assert node is not None, f"{function_name} not found in cli.py — renamed or deleted, not merely refactored"

    # Part 1: no waiver on the def line (or the parenthesised signature that
    # follows it, which is where a multi-line def carries its comment).
    signature_span = lines[node.lineno - 1 : (node.body[0].lineno - 1)]
    waived = [line for line in signature_span if _NOQA_C901.search(line)]
    assert not waived, f"{function_name} still carries a C901 waiver: {waived}"

    # Part 2: and it is genuinely under the threshold.
    offenders = {str(f["message"]).split("`")[1] for f in _true_complexity_findings() if "`" in str(f["message"])}
    assert function_name not in offenders, (
        f"{function_name} has no waiver but is STILL over the complexity threshold — "
        f"ruff --ignore-noqa reports it. The waiver was deleted without the "
        f"decomposition that justifies deleting it."
    )
