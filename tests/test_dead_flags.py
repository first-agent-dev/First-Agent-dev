"""C2 test for check_dead_flags.py — proves dead flag detection and phantom flag detection.

Skill: tests-writing, C2 (script smoke), HR3.
Root: scripts/check_dead_flags.py
Oracle: exit code + JSON output fields
Kill-check: removing a FeatureFlags field makes script report it as dead
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from scripts.check_dead_flags import check_dead_flags, main


class TestDeadFlagsUnit:
    """Unit tests for check_dead_flags() against real repo."""

    def test_no_dead_flags_on_clean_tree(self) -> None:
        """All active FeatureFlags fields should have ≥1 production reference."""
        result = check_dead_flags(Path.cwd())
        assert result["dead_count"] == 0, (
            f"Dead flags found: {[f['name'] for f in result['declared_fields'] if f['is_dead']]}"
        )

    def test_all_current_fields_present(self) -> None:
        """FeatureFlags should expose the current 13-field schema."""
        result = check_dead_flags(Path.cwd())
        declared_names = [f["name"] for f in result["declared_fields"]]
        assert len(declared_names) == 13, f"Expected 13 fields, got {len(declared_names)}: {declared_names}"
        deprecated = [f["name"] for f in result["declared_fields"] if f["is_deprecated"]]
        assert deprecated == []

    def test_no_phantom_flags_on_clean_tree(self) -> None:
        """After declaring blackboard_filtered_history_include_plans, there should be no phantom flags."""
        result = check_dead_flags(Path.cwd())
        phantom_names = [p["name"] for p in result["phantom_flags"]]
        assert len(phantom_names) == 0, (
            f"Expected 0 phantom flags, got {phantom_names}"
        )

    def test_known_fields_not_phantom(self) -> None:
        """Declared fields should NOT appear in phantom list."""
        result = check_dead_flags(Path.cwd())
        declared = {f["name"] for f in result["declared_fields"]}
        phantom = {p["name"] for p in result["phantom_flags"]}
        overlap = declared & phantom
        assert not overlap, f"Declared fields incorrectly flagged as phantom: {overlap}"

    def test_each_field_has_usage(self) -> None:
        """Every declared field should have usage_count > 0."""
        result = check_dead_flags(Path.cwd())
        for f in result["declared_fields"]:
            if f["is_deprecated"]:
                assert f["usage_count"] == 0
            else:
                assert f["usage_count"] > 0, f"Field {f['name']} has 0 usage refs"


class TestDeadFlagsCLI:
    """CLI smoke tests."""

    def test_exit_code_zero_on_clean_tree(self) -> None:
        exit_code = main([])
        assert exit_code == 0

    def test_json_output_valid(self) -> None:
        """--output json produces valid JSON with expected keys."""
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = main(["--output", "json"])
        assert exit_code == 0
        data = json.loads(buf.getvalue())
        assert "declared_fields" in data
        assert "dead_count" in data
        assert "phantom_flags" in data
        assert data["dead_count"] == 0

    def test_text_output_no_dead(self) -> None:
        """Text output should show 'ok' for all fields."""
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            main([])
        output = buf.getvalue()
        assert "DEAD" not in output
        assert "ok" in output


class TestDeadFlagsKillCheck:
    """Kill-check: prove the script actually detects dead flags."""

    def test_kill_check_detects_missing_field(self, tmp_path: Path) -> None:
        """If a field is removed from FeatureFlags, it should be detected.

        We can't actually modify the dataclass, so we patch _get_declared_fields
        to return a superset that includes a fake name.
        """
        with patch("scripts.check_dead_flags._get_declared_fields", return_value=["fake_dead_flag"]):
            result = check_dead_flags(Path.cwd())
        # fake_dead_flag should be dead (0 refs)
        fake_field = [f for f in result["declared_fields"] if f["name"] == "fake_dead_flag"]
        assert len(fake_field) == 1
        assert fake_field[0]["is_dead"] is True
        assert fake_field[0]["usage_count"] == 0
