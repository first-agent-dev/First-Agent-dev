"""Mutation run for P2-2 / E586: the planner may not name what it does not own.

The wire used to carry ``project_slug`` and ``increment_slug``; the controller then
overwrote the project slug and let the increment slug reach ``render_bundle``, so a model
could choose the file admission later read. Each mutant is a real weakening of the closed
contract, not a cosmetic edit -- a survivor means the bank proves less than it claims.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/user/First-Agent-dev")
PY = str(ROOT / ".venv" / "bin" / "python")
ACQUISITION = ROOT / "src/fa/inner_loop/managed_acquisition.py"
CONTROLLER = ROOT / "src/fa/inner_loop/workflow_controller.py"

PARSER_TESTS = ["tests/test_managed_acquisition.py"]
CONTROLLER_TESTS = ["tests/test_ai_native_bootstrap.py", "tests/test_s5p1_acquisition_lifecycle.py"]
PROMPT_TESTS = ["tests/test_prompt_registry_coherence.py"]

MUTANTS: list[tuple[str, Path, str, str, list[str]]] = [
    (
        "M1 the wire accepts a planner-chosen project slug again",
        ACQUISITION,
        '    if set(value) != {"kind", "semantics"}:\n        raise _malformed()',
        '    if not {"kind", "semantics"} <= set(value):\n        raise _malformed()',
        PARSER_TESTS,
    ),
    (
        "M2 the wire quietly tolerates an increment slug",
        ACQUISITION,
        '    if set(value) != {"kind", "semantics"}:\n        raise _malformed()',
        '    if set(value) - {"increment_slug"} != {"kind", "semantics"}:\n        raise _malformed()',
        PARSER_TESTS,
    ),
    (
        "M3 the resolved choice takes the increment from anywhere but the harness",
        CONTROLLER,
        "        increment_slug=INITIAL_INCREMENT_SLUG,",
        "        increment_slug='planner-picks',",
        CONTROLLER_TESTS,
    ),
    (
        "M4 a proposal without a caller slug is installed under a fabricated one",
        CONTROLLER,
        "    if hint is None:\n        return None",
        "    if hint is None:\n        hint = 'default-project'",
        CONTROLLER_TESTS,
    ),
    (
        "M5 the earlier guard reports the wrong rule when no authority exists",
        CONTROLLER,
        (
            "                if ctx.managed_execution is None:\n"
            '                    rule, detail = "bootstrap-unavailable", _BootstrapFailure('
        ),
        (
            "                if False:\n"
            '                    rule, detail = "bootstrap-unavailable", _BootstrapFailure('
        ),
        CONTROLLER_TESTS,
    ),
    (
        "M6 the prompt teaches the planner to name its own project again",
        ROOT / "src/fa/inner_loop/prompt.py",
        "   below. **Do not name the project or the increment.**",
        "   below. Name the project and the increment if you know them.",
        PROMPT_TESTS,
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
            # Always restore, and prove the restore: a half-mutated tree has already
            # cost this session one scare.
            path.write_text(original)
            if path.read_text() != original:
                raise RuntimeError(f"restore failed for {path}")
        status = "SURVIVED" if survived else "KILLED  "
        if not survived:
            killed += 1
        print(f"{status} {name}")
    total = len(MUTANTS)
    print(f"\nkilled {killed}/{total}")
    return 0 if killed == total else 1


if __name__ == "__main__":
    sys.exit(main())
