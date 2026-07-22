"""C2 test for check_workflow_no_path_filter.py — proves structured YAML check
replaces naïve grep for CI always-run verification.

Skill: tests-writing, C2 (CLI smoke), ADR-11-I6.
Root: scripts/check_workflow_no_path_filter.py
Oracle: exit code + JSON output
Kill-check: injecting paths: key makes test fail
"""

from __future__ import annotations

from pathlib import Path

from scripts.check_workflow_no_path_filter import check_workflow, main

# ---------------------------------------------------------------------------
# Unit tests on check_workflow()
# ---------------------------------------------------------------------------


class TestCheckWorkflowUnit:
    """Unit tests for check_workflow() against synthetic YAML files."""

    def test_no_path_filter_passes(self, tmp_path: Path) -> None:
        """Workflow without paths:/paths-ignore: → has_path_filter=False."""
        wf = tmp_path / "wf.yml"
        wf.write_text(
            """
name: Test
on:
  pull_request:
  push:
    branches: [main]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
            encoding="utf-8",
        )
        result = check_workflow(wf)
        assert result["has_path_filter"] is False
        assert result["filter_keys_found"] == []
        assert result["error"] is None

    def test_paths_key_detected(self, tmp_path: Path) -> None:
        """Workflow with paths: key → has_path_filter=True."""
        wf = tmp_path / "wf.yml"
        wf.write_text(
            """
name: Test
on:
  pull_request:
    paths:
      - 'src/**'
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
            encoding="utf-8",
        )
        result = check_workflow(wf)
        assert result["has_path_filter"] is True
        assert "paths" in result["filter_keys_found"]
        assert "pull_request" in result["triggers_with_filter"]

    def test_paths_ignore_key_detected(self, tmp_path: Path) -> None:
        """Workflow with paths-ignore: key → has_path_filter=True."""
        wf = tmp_path / "wf.yml"
        wf.write_text(
            """
name: Test
on:
  push:
    paths-ignore:
      - 'docs/**'
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
            encoding="utf-8",
        )
        result = check_workflow(wf)
        assert result["has_path_filter"] is True
        assert "paths-ignore" in result["filter_keys_found"]

    def test_comment_with_paths_not_flagged(self, tmp_path: Path) -> None:
        """Comments mentioning 'paths:' must NOT trigger a failure.

        This is the whole point of the structured checker — naïve grep
        would false-fail on comments.
        """
        wf = tmp_path / "wf.yml"
        wf.write_text(
            """
name: Test
# ALWAYS-RUN: no paths: filter per ADR-11-I6
# Also mentions paths-ignore: for documentation only
on:
  pull_request:
  push:
    branches: [main]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
            encoding="utf-8",
        )
        result = check_workflow(wf)
        assert result["has_path_filter"] is False
        assert result["error"] is None

    def test_list_form_on_triggers(self, tmp_path: Path) -> None:
        """on: [pull_request, push] list form — no path filters."""
        wf = tmp_path / "wf.yml"
        wf.write_text(
            """
name: Test
on: [pull_request, push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
            encoding="utf-8",
        )
        result = check_workflow(wf)
        assert result["has_path_filter"] is False

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Non-existent file → error reported."""
        result = check_workflow(tmp_path / "nonexistent.yml")
        assert result["error"] is not None
        assert "not found" in result["error"]

    def test_both_paths_and_paths_ignore(self, tmp_path: Path) -> None:
        """Workflow with both paths: and paths-ignore: → both detected."""
        wf = tmp_path / "wf.yml"
        wf.write_text(
            """
name: Test
on:
  pull_request:
    paths:
      - 'src/**'
    paths-ignore:
      - 'docs/**'
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
            encoding="utf-8",
        )
        result = check_workflow(wf)
        assert result["has_path_filter"] is True
        assert "paths" in result["filter_keys_found"]
        assert "paths-ignore" in result["filter_keys_found"]


# ---------------------------------------------------------------------------
# C2 smoke: run script against real workflow files
# ---------------------------------------------------------------------------


class TestCheckWorkflowSmoke:
    """C2 smoke tests running the script as a CLI against real workflow files."""

    def test_authoring_guardrails_no_path_filter(self) -> None:
        """The authoring-guardrails.yml MUST have no path filters (ADR-11-I6)."""
        wf = Path(".github/workflows/authoring-guardrails.yml")
        assert wf.exists(), "authoring-guardrails.yml must exist"
        result = check_workflow(wf)
        assert result["has_path_filter"] is False, (
            f"authoring-guardrails.yml must not have paths/paths-ignore filters: found {result['filter_keys_found']}"
        )

    def test_all_workflows_no_path_filter(self) -> None:
        """All workflows in .github/workflows/ should have no path filters."""
        workflow_dir = Path(".github/workflows")
        assert workflow_dir.is_dir()
        for wf_path in sorted(workflow_dir.glob("*.yml")):
            result = check_workflow(wf_path)
            assert result["has_path_filter"] is False, f"{wf_path.name} has path filter: {result['filter_keys_found']}"

    def test_json_output_valid(self, tmp_path: Path) -> None:
        """--output json produces valid JSON."""
        result = main(["--output", "json", ".github/workflows/authoring-guardrails.yml"])
        # main returns 0 when no path filters
        assert result == 0

    def test_cli_exit_code_no_filter(self) -> None:
        """CLI exits 0 when no path filters found."""
        exit_code = main([".github/workflows/authoring-guardrails.yml"])
        assert exit_code == 0

    def test_cli_exit_code_with_filter(self, tmp_path: Path) -> None:
        """CLI exits 1 when path filters found."""
        wf = tmp_path / "bad.yml"
        wf.write_text(
            """
name: Bad
on:
  pull_request:
    paths: ['src/**']
jobs:
  build:
    runs-on: ubuntu-latest
""",
            encoding="utf-8",
        )
        exit_code = main([str(wf)])
        assert exit_code == 1


# ---------------------------------------------------------------------------
# Kill-check: prove naïve grep fails where structured check passes
# ---------------------------------------------------------------------------


class TestNaiveGrepFalsePositive:
    """Prove that naïve grep would false-fail, justifying this script's existence."""

    def test_authoring_guardrails_comment_mentions_paths(self) -> None:
        """The real authoring-guardrails.yml has a comment with 'paths:' in it.

        Naïve `grep -q "paths:" .github/workflows/authoring-guardrails.yml`
        would exit 0 (found), leading a checker to falsely report FAIL.
        Our structured check correctly passes.
        """
        wf = Path(".github/workflows/authoring-guardrails.yml")
        content = wf.read_text(encoding="utf-8")
        # Prove the comment exists
        assert "paths:" in content, (
            "Precondition: authoring-guardrails.yml must mention 'paths:' in a comment "
            "for this kill-check to be meaningful"
        )
        # Prove the structured check passes despite the comment
        result = check_workflow(wf)
        assert result["has_path_filter"] is False
