"""Mutation run for TEST-2.8 / CT-2.7 / CT-2.2 / D-V2-9.8 (E594-E597): the repair path must be real.

Three of these exist because a cheaper test once survived them. `test_the_bound_repair_
path_runs_both_stages_and_binds_the_result` was written after M3 survived the hand-built
sibling: assembling the second stage by hand proves repair is *possible*, never that the
bound path does it. A survivor here means the bank proves less than it claims.

M5 (budget) is killed by `test_a_create_new_repair_is_budgeted_and_never_overwrites_on_
collision`, not by the bound-path test -- recorded so the next reader does not "fix" a
bank that is already covered.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/user/First-Agent-dev")
PY = str(ROOT / ".venv" / "bin" / "python")
CONTROLLER = ROOT / "src/fa/inner_loop/workflow_controller.py"
CLI = ROOT / "src/fa/cli.py"
TOOL = ROOT / "src/fa/inner_loop/tools/workflow_tool.py"

_BANK = "tests/test_ai_native_bootstrap.py"

BOUND = [f"{_BANK}::test_the_bound_repair_path_runs_both_stages_and_binds_the_result"]
E2E = [f"{_BANK}::test_metadata_table_and_parse_refusal_block_coder_then_repair_rewrites_published_file"]
BUDGET = [f"{_BANK}::test_a_create_new_repair_is_budgeted_and_never_overwrites_on_collision"]
COLLISION = [f"{_BANK}::test_create_over_existing_directory_is_project_exists_and_unchanged"]
_TOOL_BANK = "tests/test_invoke_workflow_tool.py"
SLUG = [
    f"{_TOOL_BANK}::test_an_invalid_slug_is_refused_before_any_child_exists",
    f"{_TOOL_BANK}::test_a_slug_without_a_create_route_is_refused_before_any_child_exists",
    f"{_TOOL_BANK}::test_an_unknown_project_action_is_refused_before_any_child_exists",
]

MUTANTS: list[tuple[str, Path, str, str, list[str]]] = [
    (
        "M1 the metadata cross-check never refuses (D-V2-9.3 gone)",
        CONTROLLER,
        "        check_project_metadata({roadmap_path: roadmap.content, increment_path: increment.content})",
        "        pass  # MUTANT",
        E2E,
    ),
    (
        "M2 the repair stage is seeded with the scaffold again (D-V2-9.9 regression)",
        CLI,
        "    if planner_dispatch.repair_allowlist is not None:\n        # D-V2-9.9",
        "    if False and planner_dispatch.repair_allowlist is not None:\n        # D-V2-9.9",
        E2E,
    ),
    (
        "M3 the repair runs with no narrowed scope",
        CONTROLLER,
        "        repair_allowlist=_repair_allowlist(root),",
        "        repair_allowlist=None,",
        BOUND,
    ),
    (
        "M4 the bound path never dispatches a repair",
        CONTROLLER,
        "    if run_stage_fn is not None and progress is not None and _may_repair_authored_project(ctx, refusal):",
        "    if False:  # MUTANT",
        BOUND,
    ),
    (
        "M6 the create-collision check never runs (CT-2.7: overwrite allowed)",
        CONTROLLER,
        "    if slug in substrate.project_names or slug in substrate.incomplete_names:",
        "    if False:  # MUTANT",
        COLLISION,
    ),
    (
        "M7 an incomplete project directory is treated as free (CT-2.7)",
        CONTROLLER,
        "    if slug in substrate.project_names or slug in substrate.incomplete_names:",
        "    if slug in substrate.project_names:  # MUTANT",
        COLLISION,
    ),
    (
        "M8 the scaffold overwrites instead of creating (CT-2.7)",
        CLI,
        "        workspace_io.write_file(path, body, expected_sha256=None)",
        "        workspace_io.write_file(path, body, expected_sha256='0' * 64)  # MUTANT",
        COLLISION,
    ),
    (
        "M9 the slug pattern is not enforced (CT-2.2: traversal reaches the child)",
        TOOL,
        '        if not _PROJECT_SLUG_RE.fullmatch(slug or "") or len(slug) > _PROJECT_SLUG_MAX:',
        "        if not slug:  # MUTANT",
        SLUG,
    ),
    (
        "M10 a slug without a create route is silently dropped (CT-2.2)",
        TOOL,
        "    elif slug:",
        "    elif False:  # MUTANT",
        SLUG,
    ),
    (
        "M11 an unknown action falls through to the default (CT-2.2)",
        TOOL,
        "    if action not in _PROJECT_ACTIONS:",
        "    if False:  # MUTANT",
        SLUG,
    ),
    (
        "M5 a repair is not budgeted (killed by BUDGET, not BOUND)",
        CONTROLLER,
        "    return ctx.authored_repairs < ctx.replans_allowed",
        "    return True  # MUTANT",
        BUDGET,
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
            print(f"SKIP     {name} (pattern found {count} times, expected 1)")
            continue
        path.write_text(original.replace(old, new, 1))
        try:
            survived = run_once(tests)
        finally:
            path.write_text(original)
            if path.read_text() != original:
                raise RuntimeError(f"restore failed for {path}")
        print(f"{'SURVIVED' if survived else 'KILLED  '} {name}")
        if not survived:
            killed += 1
    total = len(MUTANTS)
    print(f"\nkilled {killed}/{total}")
    return 0 if killed == total else 1


if __name__ == "__main__":
    sys.exit(main())
