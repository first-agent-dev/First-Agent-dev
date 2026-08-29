#!/usr/bin/env python3
"""Per-function coverage floor gate for ``src/fa/cli.py`` (S10a.7).

Why this is a **script invoked by ``just``** and not a pytest test
-----------------------------------------------------------------
Coverage flags are deliberately excluded from ``[tool.pytest.ini_options]
addopts``. ``pyproject.toml`` states the reason:

    "A bare ``pytest tests/test_x.py`` must work for agents iterating on a
    single module (a partial run would always 'fail' the gate and teach agents
    to ignore red output)."

A pytest test that reads ``coverage.json`` therefore **fails on every bare
run** — which would re-introduce exactly the anti-pattern that note exists to
prevent. Measured during plan review: a one-line test asserting the file exists
was dropped into ``tests/`` and run bare, and it failed. So the gate lives here
and runs after ``just test`` has produced the artifact, matching the eight
other gates in the ``check`` chain.

Why **per-function** and not an aggregate
-----------------------------------------
An aggregate floor is satisfiable by covering ``build_parser`` harder while
``_cmd_probe`` stays dark — which is precisely the state S10a started from
(59% overall, six commands at 0-11%).

Which metric
------------
``percent_covered``, which is **branch-inclusive**. The repo sets
``branch = true`` ("branch coverage catches untested if/else paths"), so this
is the metric CI's own ``fail_under`` already enforces. The sibling field
``percent_statements_covered`` reads 1-2 points higher and choosing it would
make this gate quieter than the one already in place.

Floors may only be **raised**. Lowering one is how a ratchet becomes
decoration; if a refactor genuinely moves code between functions, move the
floor with a reason in the commit message.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COVERAGE_JSON = REPO_ROOT / "coverage.json"
TARGET_FILE_SUFFIX = "fa/cli.py"

# Minimum ``percent_covered`` per function. Established by S10a; see the plan's
# GAP ledger for why ``_cmd_selfcheck`` is best-effort rather than 80.
_FLOORS: dict[str, float] = {
    # S10b.2 extracted nine helpers from `_cmd_run`. Each carries its own floor
    # below, so the enforced surface GREW (11 functions -> 20) rather than
    # shrinking. `_cmd_run` itself stays at 80: it dipped to 75.7% mid-slice
    # when only five helpers existed, then recovered to 84.5% as extraction
    # continued, so no floor concession was needed in the end.
    "_cmd_run": 80.0,
    "_validate_run_args": 100.0,
    "_resolve_run_models": 100.0,
    "_build_compactor_chain": 85.0,
    "_build_role_registry": 100.0,
    "_build_run_hook_registry": 90.0,
    "_build_output_bus": 90.0,
    # Floored at their measured values and NOT rounded up. Extraction made
    # these gaps visible for the first time -- inline, their uncovered branches
    # were part of `_cmd_run`'s aggregate and invisible. S10b.2 adds direct
    # unit tests to lift them; the floors below are the ratchet's new starting
    # point, not a target.
    "_build_pty_pool": 50.0,
    "_prepare_pr_draft": 90.0,
    "_session_db_runtime_error_message": 100.0,
    "_cmd_stats": 80.0,
    # S10b.3 helpers. `_render_dead_zones` is floored at its measured 75: its
    # uncovered branch is the >15-entries truncation path, which needs a
    # workspace with 16+ untouched src/ files to reach. Floored honestly rather
    # than padded with a fixture that exists only to move a number.
    "_cmd_stats_global_history": 90.0,
    "_render_dead_zones": 75.0,
    "_cmd_probe": 80.0,
    # S13.5 conformance matrix CLI. Text + JSON branches are C2-tested in
    # tests/test_s13_message_rules.py; the live `--provider` path is a separate
    # S13.6 step and is not floored here.
    "_cmd_conformance": 90.0,
    "_cmd_routing_check": 80.0,
    "_cmd_chunk": 80.0,
    "_cmd_authoring_check": 80.0,
    "_cmd_egress_proxy": 80.0,
    # NOTE: `_run_adaptive` was floored here during S10b CLI decomposition but
    # does not live in cli.py: the S4a workflow-controller extraction moved it
    # to src/fa/inner_loop/workflow_controller.py, where its coverage is
    # exercised by tests/test_s8_workflow_controller.py and counted in the
    # global >=80% floor. Removed from this cli.py-only table (2026-08-28) — a
    # cli.py floor entry for a function the file no longer contains made the
    # gate fail vacuously.
    "_discover_stats_sources": 80.0,
    # S10b.4 helpers — the manifest validation matrix, now directly unit-tested
    # by error CODE (the operator contract) rather than only through the
    # command root.
    "_resolve_stats_session_dirs": 95.0,
    "_validate_session_manifest": 100.0,
    "_resolve_task": 80.0,
    # Best-effort (operator decision): the remaining lines are diagnostic
    # banner formatting. Every branch that decides an EXIT CODE is covered.
    "_cmd_selfcheck": 60.0,
    # S10b.5 helpers. The two pure ones are at 100 and floored there; the
    # prober is at 91 (its uncovered branch is the _SelfcheckNetworkError path
    # on /routes, which needs a transport that succeeds once then raises).
    "_selfcheck_proxy_preflight": 100.0,
    "_selfcheck_fetch_proxy_routes": 90.0,
    "_selfcheck_route_problems": 100.0,
}

# Liveness control. A parse that silently yields an empty function table would
# satisfy every floor vacuously — the failure mode this workstream has hit
# repeatedly. ``cli.py` had 59 functions when this gate was written.
_MIN_FUNCTIONS_IN_REPORT = 40


def main() -> int:
    if not COVERAGE_JSON.is_file():
        print(
            f"FAIL: {COVERAGE_JSON} not found.\n"
            f"  This gate reads the JSON coverage report. Run `just test` first "
            f"(it passes --cov-report=json), or invoke `just cli-coverage-floor` "
            f"after a full coverage run.",
            file=sys.stderr,
        )
        return 1

    try:
        report = json.loads(COVERAGE_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: cannot read {COVERAGE_JSON}: {exc}", file=sys.stderr)
        return 1

    files = report.get("files", {})
    matches = [key for key in files if key.replace("\\", "/").endswith(TARGET_FILE_SUFFIX)]
    if not matches:
        print(
            f"FAIL: no coverage entry for {TARGET_FILE_SUFFIX} in {COVERAGE_JSON}.\n"
            f"  Was the run scoped with --cov=fa (or --cov=fa.cli)?",
            file=sys.stderr,
        )
        return 1

    functions = files[matches[0]].get("functions", {})
    if len(functions) < _MIN_FUNCTIONS_IN_REPORT:
        print(
            f"FAIL: coverage report lists only {len(functions)} functions for "
            f"{TARGET_FILE_SUFFIX}; expected at least {_MIN_FUNCTIONS_IN_REPORT}.\n"
            f"  The report is truncated or the schema changed — the floors below "
            f"would pass vacuously, so this is treated as a failure.",
            file=sys.stderr,
        )
        return 1

    missing: list[str] = []
    below: list[tuple[str, float, float]] = []
    for name, floor in sorted(_FLOORS.items()):
        entry = functions.get(name)
        if entry is None:
            missing.append(name)
            continue
        actual = float(entry["summary"]["percent_covered"])
        if actual < floor:
            below.append((name, actual, floor))

    if missing:
        print(
            "FAIL: these functions are named in the floor table but absent from "
            "the coverage report — renamed, deleted, or never imported:\n"
            + "".join(f"  - {name}\n" for name in missing),
            file=sys.stderr,
        )
        return 1

    if below:
        print("FAIL: per-function coverage floors not met:", file=sys.stderr)
        for name, actual, floor in below:
            print(f"  - {name}: {actual:.1f}% < floor {floor:.1f}%", file=sys.stderr)
        print(
            "\n  Add tests for the uncovered branches. Do NOT lower a floor to "
            "make this pass — floors may only be raised.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {len(_FLOORS)} cli.py function coverage floors met ({len(functions)} functions scanned).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
