"""Mutation run for P0-1: the typed semantics payload and the one renderer (D-V2-7).

Every mutant is a *real* weakening of a production rule, not a cosmetic edit: a renderer that
pre-empts the slug, a self-check that skips admission, a payload field that stops being
validated, a selector that stops being expanded, and the controller wiring that could quietly
fall back to prose. A survivor means the bank proves less than it claims.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/user/First-Agent-dev")
PY = str(ROOT / ".venv" / "bin" / "python")
SEMANTICS = ROOT / "src/fa/inner_loop/plan_semantics.py"
CONTROLLER = ROOT / "src/fa/inner_loop/workflow_controller.py"
ACQUISITION = ROOT / "src/fa/inner_loop/managed_acquisition.py"

SEMANTICS_TESTS = ["tests/test_ai_native_plan_semantics.py"]
CONTROLLER_TESTS = [
    "tests/test_ai_native_bootstrap.py",
    "tests/test_ai_native_plan_semantics.py",
]
ACQUISITION_TESTS = [
    "tests/test_managed_acquisition.py",
    "tests/test_prompt_registry_coherence.py",
]

MUTANTS: list[tuple[str, Path, str, str, list[str]]] = [
    (
        "M1 the renderer accepts a selector that pre-empts the project slug",
        SEMANTICS,
        '    if not selector.startswith(_SELECTOR_ROOT) or "::" not in selector:',
        "    if '::' not in selector:",
        SEMANTICS_TESTS,
    ),
    (
        "M2 render_project returns bytes without proving admission accepts them",
        SEMANTICS,
        "    try:\n        parse_plan(roadmap=roadmap, increment=increment)\n    except PlanV2Error as error:\n"
        "        raise SemanticsError(error.rule) from None\n",
        "",
        SEMANTICS_TESTS,
    ),
    (
        "M3 a reason on a TEST_REQUIRED invariant is silently ignored",
        SEMANTICS,
        '        raise SemanticsError("invariant-reason-invalid")',
        "        pass",
        SEMANTICS_TESTS,
    ),
    (
        "M4 a pipe inside a value is accepted",
        SEMANTICS,
        '    if "|" in value:',
        "    if False:",
        SEMANTICS_TESTS,
    ),
    (
        "M5 the renderer stops validating the project slug",
        SEMANTICS,
        '    if _SLUG_RE.fullmatch(project_slug) is None:\n        raise SemanticsError("project-slug-invalid")\n',
        "",
        SEMANTICS_TESTS,
    ),
    (
        "M6 the renderer emits a second STEPS: header",
        SEMANTICS,
        '            f"STEPS: {planned.steps_mode}",',
        '            f"STEPS: {planned.steps_mode}",\n            "STEPS:",',
        SEMANTICS_TESTS,
    ),
    (
        "M7 from_graph keeps a selector from another project",
        SEMANTICS,
        '        raise SemanticsError("selector-outside-project")',
        "        pass",
        SEMANTICS_TESTS,
    ),
    (
        "M8 the controller installs the prose bodies on the V2 route",
        CONTROLLER,
        "    if plan_format != PLAN_V2:\n        return choice.roadmap_body, choice.increment_body",
        "    if True:\n        return choice.roadmap_body, choice.increment_body",
        CONTROLLER_TESTS,
    ),
    (
        "M9 the controller prepares bytes it did not validate",
        CONTROLLER,
        "            roadmap_text=roadmap_text,\n            increment_text=increment_text,",
        "            roadmap_text=choice.roadmap_body,\n            increment_text=choice.increment_body,",
        CONTROLLER_TESTS,
    ),
    (
        "M10 the wire lets a payload carry both the semantics and the retired Markdown",
        ACQUISITION,
        '    if set(value) != {"kind", "project_slug", "increment_slug", "semantics"}:\n        raise _malformed()',
        "    if not isinstance(value, Mapping):\n        raise _malformed()",
        ACQUISITION_TESTS,
    ),
    (
        "M11 a semantics payload of the wrong type is not refused",
        ACQUISITION,
        "    try:\n        semantics = parse_semantics(raw)",
        "    if not isinstance(raw, Mapping):\n        raise _malformed()\n"
        "    try:\n        semantics = parse_semantics(raw)",
        ACQUISITION_TESTS,
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
    return 0 if killed == total else 1


if __name__ == "__main__":
    sys.exit(main())
