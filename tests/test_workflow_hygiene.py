"""C1/C2 tests for scripts/check_workflow_hygiene.py.

Covers:
- The original path-filter detection (replaces naive grep per ADR-11-I6).
- The new if:-bypass detection (literal-false / expr-false / draft-ok
  annotations / advisory-job exemption / step-level if exemption).
- C2 CLI smoke against real workflows, plus JSON output parity.

Skill: tests-writing, Pyramid A, C1/C2.
Root: scripts/check_workflow_hygiene.py
Oracle: exit code + structured result dict + JSON output.
Kill-check: removing either detector (path-filter OR if-bypass) makes a
test case here fail.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_workflow_hygiene import (
    _BLOCKING_FALSE_EXPR,
    _BLOCKING_FALSE_LITERALS,
    _DRAFT_GUARD_EXPR,
    _DRAFT_OK_COMMENT,
    _find_bypass_if,
    _scan_draft_ok_annotations,
    check_workflow,
    main,
)

# ---------------------------------------------------------------------------
# Unit tests on check_workflow() — path-filter detection
# ---------------------------------------------------------------------------


class TestPathFilterDetection:
    """Path-filter detection (original behavior retained)."""

    def test_no_path_filter_passes(self, tmp_path: Path) -> None:
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
        assert result["has_bypass_if"] is False
        assert result["filter_keys_found"] == []
        assert result["error"] is None

    def test_paths_key_detected(self, tmp_path: Path) -> None:
        wf = tmp_path / "wf.yml"
        wf.write_text(
            """
name: Test
on:
  pull_request:
    paths: ['src/**']
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
        wf = tmp_path / "wf.yml"
        wf.write_text(
            """
name: Test
on:
  push:
    paths-ignore: ['docs/**']
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
        """Comments mentioning 'paths:' must NOT trigger a failure."""
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
        result = check_workflow(tmp_path / "nonexistent.yml")
        assert result["error"] is not None
        assert "not found" in result["error"]

    def test_both_paths_and_paths_ignore(self, tmp_path: Path) -> None:
        wf = tmp_path / "wf.yml"
        wf.write_text(
            """
name: Test
on:
  pull_request:
    paths: ['src/**']
    paths-ignore: ['docs/**']
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
# Unit tests on if:-bypass detection
# ---------------------------------------------------------------------------


class TestIfBypassDetection:
    """Constant-false if: guards on blocking jobs are flagged."""

    @pytest.mark.parametrize(
        ("literal", "expected_python"),
        [
            ("false", False),  # YAML bool -> Python False
            ("0", 0),  # int 0
            ("null", None),  # YAML null -> Python None
            ("~", None),  # YAML null alias
            ('""', ""),  # empty string (double-quoted)
            ("''", ""),  # empty string (single-quoted)
        ],
    )
    def test_literal_false_flagged(self, tmp_path: Path, literal: str, expected_python: object) -> None:
        wf = tmp_path / "wf.yml"
        wf.write_text(
            f"""
name: Test
on: [pull_request, push]
jobs:
  build:
    runs-on: ubuntu-latest
    if: {literal}
    steps:
      - run: echo hi
""",
            encoding="utf-8",
        )
        # Sanity: YAML parses the literal to the expected Python value.
        import yaml as _yaml

        parsed = _yaml.safe_load(wf.read_text())
        assert parsed["jobs"]["build"]["if"] == expected_python
        result = check_workflow(wf)
        assert result["has_bypass_if"] is True
        jobs = {f["job"]: f["reason"] for f in result["bypass_findings"]}
        assert "build" in jobs
        assert jobs["build"] == "literal-false"

    @pytest.mark.parametrize("expr", ["${{ false }}", "${{0}}", "${{ false }}", "${{ 0 }}"])
    def test_expr_false_flagged(self, tmp_path: Path, expr: str) -> None:
        wf = tmp_path / "wf.yml"
        wf.write_text(
            f"""
name: Test
on: [pull_request, push]
jobs:
  build:
    runs-on: ubuntu-latest
    if: "{expr}"
    steps:
      - run: echo hi
""",
            encoding="utf-8",
        )
        result = check_workflow(wf)
        assert result["has_bypass_if"] is True
        jobs = {f["job"]: f["reason"] for f in result["bypass_findings"]}
        assert jobs.get("build") == "expr-false"

    def test_draft_guard_without_annotation_flagged(self, tmp_path: Path) -> None:
        wf = tmp_path / "wf.yml"
        wf.write_text(
            """
name: Test
on: [pull_request, push]
jobs:
  build:
    runs-on: ubuntu-latest
    if: github.event.pull_request.draft == true
    steps:
      - run: echo hi
""",
            encoding="utf-8",
        )
        result = check_workflow(wf)
        assert result["has_bypass_if"] is True
        jobs = {f["job"]: f["reason"] for f in result["bypass_findings"]}
        assert jobs.get("build") == "draft-gate-no-annotation"

    def test_draft_guard_with_preceding_comment_passes(self, tmp_path: Path) -> None:
        wf = tmp_path / "wf.yml"
        wf.write_text(
            """
name: Test
on: [pull_request, push]
jobs:
  build:
    runs-on: ubuntu-latest
    # ci-hygiene: draft-ok
    if: github.event.pull_request.draft == false
    steps:
      - run: echo hi
""",
            encoding="utf-8",
        )
        result = check_workflow(wf)
        assert result["has_bypass_if"] is False
        assert "build" in result["draft_ok_jobs"]

    def test_draft_guard_with_inline_comment_passes(self, tmp_path: Path) -> None:
        wf = tmp_path / "wf.yml"
        wf.write_text(
            """
name: Test
on: [pull_request, push]
jobs:
  build:
    runs-on: ubuntu-latest
    if: github.event.pull_request.draft == false  # ci-hygiene: draft-ok
    steps:
      - run: echo hi
""",
            encoding="utf-8",
        )
        result = check_workflow(wf)
        assert result["has_bypass_if"] is False

    def test_advisory_job_with_if_passes(self, tmp_path: Path) -> None:
        """continue-on-error: true jobs are advisory; may have conditional if."""
        wf = tmp_path / "wf.yml"
        wf.write_text(
            """
name: Test
on: [pull_request, push]
jobs:
  scans:
    runs-on: ubuntu-latest
    continue-on-error: true
    if: failure()
    steps:
      - run: echo hi
""",
            encoding="utf-8",
        )
        result = check_workflow(wf)
        assert result["has_bypass_if"] is False

    def test_step_level_if_not_flagged(self, tmp_path: Path) -> None:
        """Step-level if (e.g. if: always() on upload) is legitimate."""
        wf = tmp_path / "wf.yml"
        wf.write_text(
            """
name: Test
on: [pull_request, push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: some/action
      - if: always()
        run: echo upload
""",
            encoding="utf-8",
        )
        result = check_workflow(wf)
        assert result["has_bypass_if"] is False

    def test_conditional_event_filter_passes(self, tmp_path: Path) -> None:
        """Non-constant conditionals (github.event_name) are legitimate."""
        wf = tmp_path / "wf.yml"
        wf.write_text(
            """
name: Test
on: [pull_request, push]
jobs:
  build:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - run: echo hi
""",
            encoding="utf-8",
        )
        result = check_workflow(wf)
        assert result["has_bypass_if"] is False

    def test_multiple_jobs_mixed(self, tmp_path: Path) -> None:
        wf = tmp_path / "wf.yml"
        wf.write_text(
            """
name: Test
on: [pull_request, push]
jobs:
  good:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
  bad:
    runs-on: ubuntu-latest
    if: false
    steps:
      - run: echo hi
  advisory:
    runs-on: ubuntu-latest
    continue-on-error: true
    if: failure()
    steps:
      - run: echo hi
""",
            encoding="utf-8",
        )
        result = check_workflow(wf)
        jobs = {f["job"]: f["reason"] for f in result["bypass_findings"]}
        assert "bad" in jobs
        assert jobs["bad"] == "literal-false"
        assert "good" not in jobs
        assert "advisory" not in jobs


# ---------------------------------------------------------------------------
# C2 smoke: run against real workflows
# ---------------------------------------------------------------------------


class TestRealWorkflowsSmoke:
    """Every workflow checked into .github/workflows/ is hygiene-clean."""

    def test_all_real_workflows_clean(self) -> None:
        workflow_dir = Path(".github/workflows")
        assert workflow_dir.is_dir()
        for wf_path in sorted(workflow_dir.glob("*.yml")):
            result = check_workflow(wf_path)
            assert result["error"] is None, f"{wf_path.name}: {result['error']}"
            assert result["has_path_filter"] is False, f"{wf_path.name} has path filter: {result['filter_keys_found']}"
            assert result["has_bypass_if"] is False, f"{wf_path.name} has bypass if: {result['bypass_findings']}"

    def test_authoring_guardrails_clean(self) -> None:
        wf = Path(".github/workflows/authoring-guardrails.yml")
        assert wf.exists()
        result = check_workflow(wf)
        assert result["has_path_filter"] is False
        assert result["has_bypass_if"] is False

    def test_cli_exit_code_no_finding(self) -> None:
        assert main([".github/workflows/authoring-guardrails.yml"]) == 0

    def test_cli_exit_code_with_finding(self, tmp_path: Path) -> None:
        wf = tmp_path / "bad.yml"
        wf.write_text(
            """
name: Bad
on:
  pull_request:
    paths: ['src/**']
jobs:
  build:
    if: false
    runs-on: ubuntu-latest
""",
            encoding="utf-8",
        )
        assert main([str(wf)]) == 1

    def test_cli_json_output(self, tmp_path: Path) -> None:
        wf = tmp_path / "bad.yml"
        wf.write_text(
            """
name: Bad
on: [pull_request]
jobs:
  build:
    if: false
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [sys.executable, "scripts/check_workflow_hygiene.py", "--output", "json", str(wf)],
            capture_output=True,
            text=True,
            check=False,
            cwd=Path.cwd(),
        )
        assert proc.returncode == 1
        data = json.loads(proc.stdout)
        assert data["has_finding"] is True
        assert any(f["reason"] == "literal-false" for f in data["workflows"][0]["bypass_findings"])


# ---------------------------------------------------------------------------
# Kill-check scaffolding: prove the detectors exist
# ---------------------------------------------------------------------------


class TestDetectorsGrounded:
    """Trivial invariants that pin the detector shapes so silent
    drift (e.g. a refactor that deletes the constant sets) gets caught.
    """

    def test_literal_set_contains_falsy_literals(self) -> None:
        assert False in _BLOCKING_FALSE_LITERALS
        assert 0 in _BLOCKING_FALSE_LITERALS
        assert None in _BLOCKING_FALSE_LITERALS
        assert "" in _BLOCKING_FALSE_LITERALS

    def test_expr_regex_matches_plain_false(self) -> None:
        assert _BLOCKING_FALSE_EXPR.match("${{ false }}")
        assert _BLOCKING_FALSE_EXPR.match("${{0}}")
        assert _BLOCKING_FALSE_EXPR.match("  ${{ false }}  ")
        assert not _BLOCKING_FALSE_EXPR.match("${{ false || true }}")

    def test_draft_guard_expr_matches(self) -> None:
        assert _DRAFT_GUARD_EXPR.search("github.event.pull_request.draft == true")
        assert not _DRAFT_GUARD_EXPR.search("github.actor == 'x'")

    def test_draft_ok_comment_regex_matches(self) -> None:
        assert _DRAFT_OK_COMMENT.search("# ci-hygiene: draft-ok")
        assert _DRAFT_OK_COMMENT.search("# ci-hygiene: draft-ok  (intentional)")
        assert not _DRAFT_OK_COMMENT.search("# not draft-ok")

    def test_scan_draft_ok_annotations_pure(self, tmp_path: Path) -> None:
        wf = tmp_path / "wf.yml"
        wf.write_text(
            """
name: t
on: [push]
jobs:
  a:
    runs-on: u
    # ci-hygiene: draft-ok
    if: github.event.pull_request.draft == false
    steps: [run: hi]
  b:
    runs-on: u
    if: github.event.pull_request.draft == true
    steps: [run: hi]
""",
            encoding="utf-8",
        )
        import yaml

        data = yaml.safe_load(wf.read_text())
        draft_ok = _scan_draft_ok_annotations(wf.read_text())
        assert draft_ok == {"a"}
        findings = _find_bypass_if(data, draft_ok)
        jobs = {f["job"]: f["reason"] for f in findings}
        assert jobs == {"b": "draft-gate-no-annotation"}
