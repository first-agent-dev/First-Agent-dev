"""Mutation run for P1-1/P1-2: verdict strength may not exceed evidence strength (E585).

Two defects, one root: a claim can be *reported* stronger than what backs it.

* P1-1 -- ``ATTESTED`` was graded from the plan's request. After R1 a ``reason`` is
  only a request; the grant is the caller's ``owner``/``evidence_ref``. An unbound
  graph therefore named a contract as attested that nobody granted, and the grant
  the controller did check before the install was dropped before the read-back.
* P1-2 -- the grant is keyed by reason, so two invariants naming one reason were
  both authorised by a single declaration: one decision, two claims.

Each mutant is a real weakening of a production rule. A survivor means the bank
proves less than it claims, so it is a diagnosis rather than a number to tune.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/user/First-Agent-dev")
PY = str(ROOT / ".venv" / "bin" / "python")
PLAN_V2 = ROOT / "src/fa/inner_loop/plan_v2.py"
CONTROLLER = ROOT / "src/fa/inner_loop/workflow_controller.py"

PLAN_TESTS = ["tests/test_ai_native_plan_v2.py"]
GRADING_TESTS = ["tests/test_ai_native_plan_v2.py", "tests/test_ai_native_acceptance_bundle.py"]
READBACK_TESTS = ["tests/test_ai_native_plan_v2.py", "tests/test_ai_native_bootstrap.py"]
SEAM_TESTS = ["tests/test_s5p1_acquisition_substrate.py"]

#: ``_authorised_graph`` and its mutants are gone with the install path (D-V2-9): the
#: authoring route parses the published bytes once and binds the caller's grant to that
#: same graph, so there is no carried grant and no read-back to reconcile.
EQUIVALENT_MUTANTS: list[tuple[str, str]] = []

MUTANTS: list[tuple[str, Path, str, str, list[str]]] = [
    (
        "M1 ATTESTED is graded from the request, not from the bound grant",
        PLAN_V2,
        (
            "    granted = {\n"
            "        item.id for item in graph.invariants"
            ' if item.evidence == "NON_EXECUTABLE" and item.owner is not None\n'
            "    }"
        ),
        '    granted = {item.id for item in graph.invariants if item.evidence == "NON_EXECUTABLE"}',
        GRADING_TESTS,
    ),
    (
        "M2 the grant's presence is not required at all (any NON_EXECUTABLE attests)",
        PLAN_V2,
        "            elif contract.inv in granted:",
        '            elif {item.id for item in graph.invariants if item.evidence == "NON_EXECUTABLE"}:',
        GRADING_TESTS,
    ),
    (
        "M3 a reason may be spent by two invariants",
        PLAN_V2,
        '    if len(set(reasons)) != len(reasons):\n        raise PlanV2Error("disposition-reason-reused")',
        "    pass",
        PLAN_TESTS,
    ),
    (
        "M4 the reuse rule is really the cluster rule (wrong diagnosis)",
        PLAN_V2,
        '        raise PlanV2Error("disposition-reason-reused")',
        '        raise PlanV2Error("disposition-covers-several-contracts")',
        PLAN_TESTS,
    ),
]


def run_once(tests: list[str]) -> bool:
    result = subprocess.run(
        [PY, "-m", "pytest", *tests, "-x", "-q"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return result.returncode == 0


def main() -> int:
    killed = 0
    for name, path, old, new, tests in MUTANTS:
        original = path.read_text()
        count = original.count(old)
        if count != 1:
            print(f"SKIP    {name} (pattern found {count} times, expected 1)")
            continue
        path.write_text(original.replace(old, new))
        try:
            survived = run_once(tests)
        finally:
            path.write_text(original)
        status = "SURVIVED" if survived else "KILLED  "
        if not survived:
            killed += 1
        print(f"{status} {name}")
    total = len(MUTANTS)
    print(f"\nkilled {killed}/{total}")
    for name, why in EQUIVALENT_MUTANTS:
        print(f"EQUIVALENT (not counted) {name}: {why}")
    return 0 if killed == total else 1


if __name__ == "__main__":
    sys.exit(main())
