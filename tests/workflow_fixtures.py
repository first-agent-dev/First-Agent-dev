"""Explicit disposable input for workflow routing/deadline regression fixtures."""

from pathlib import Path


def write_explicit_plan(tmp_path: Path) -> Path:
    # CT90: routing/history fixtures must supply an explicit workspace plan.
    plan = (
        tmp_path / "worklogs/planning-topology-and-executable-contracts-loop/increments/increment-99-cli-fixture.md"
    )
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(
        "Plan-ID: PLAN-cli-fixture\n\n## SLICE1: CLI routing fixture\n"
        "CONTRACTS:\n  CT9001 [CONSTRAINT]: fixture input remains present.\n"
        "TESTS: tests/test_fixture_contract.py\n",
        encoding="utf-8",
    )
    tests = tmp_path / "tests"
    tests.mkdir(exist_ok=True)
    (tests / "test_fixture_contract.py").write_text(
        "from pathlib import Path\n\ndef test_fixture_input():\n"
        f"    assert Path({str(plan.relative_to(tmp_path))!r}).is_file()\n",
        encoding="utf-8",
    )
    # A real runner for the disposable project, not a fake baseline report.
    venv = tmp_path / ".venv"
    if not venv.exists():
        venv.symlink_to(Path(__file__).resolve().parents[1] / ".venv", target_is_directory=True)
    return plan
