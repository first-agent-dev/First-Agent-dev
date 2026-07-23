"""Tests for shared YAML-like line parser (fa._yaml_line_parser).

Verifies the extracted line iteration utility works correctly and handles edge cases.
"""

from __future__ import annotations

from fa._yaml_line_parser import iter_yaml_lines


class TestIterYamlLines:
    """Tests for iter_yaml_lines() generator."""

    def test_skips_blank_lines(self) -> None:
        """iter_yaml_lines skips blank lines."""
        text = """

        key: value

        """
        lines = list(iter_yaml_lines(text))
        assert len(lines) == 1
        assert lines[0].stripped == "key: value"

    def test_skips_comments(self) -> None:
        """iter_yaml_lines skips comment lines."""
        text = """# Comment
        key: value
        # Another comment
        """
        lines = list(iter_yaml_lines(text))
        assert len(lines) == 1
        assert lines[0].stripped == "key: value"

    def test_tracks_indentation(self) -> None:
        """iter_yaml_lines correctly tracks indentation level."""
        text = """top:
  nested: value
    deep: value
"""
        lines = list(iter_yaml_lines(text))
        assert len(lines) == 3
        assert lines[0].indent == 0
        assert lines[1].indent == 2
        assert lines[2].indent == 4

    def test_identifies_top_level_keys(self) -> None:
        """iter_yaml_lines identifies top-level keys (indent == 0)."""
        text = """section1:
  key: value
section2:
  key: value
"""
        lines = list(iter_yaml_lines(text))
        assert len(lines) == 4
        assert lines[0].is_top_level is True
        assert lines[1].is_top_level is False
        assert lines[2].is_top_level is True
        assert lines[3].is_top_level is False

    def test_provides_line_numbers(self) -> None:
        """iter_yaml_lines provides 1-based line numbers."""
        text = """# Comment
        key1: value1
        key2: value2
"""
        lines = list(iter_yaml_lines(text))
        assert lines[0].line_no == 2
        assert lines[1].line_no == 3

    def test_handles_empty_text(self) -> None:
        """iter_yaml_lines handles empty text gracefully."""
        lines = list(iter_yaml_lines(""))
        assert len(lines) == 0

    def test_handles_only_comments(self) -> None:
        """iter_yaml_lines handles text with only comments."""
        text = """# Comment 1
# Comment 2
"""
        lines = list(iter_yaml_lines(text))
        assert len(lines) == 0

    def test_preserves_raw_line(self) -> None:
        """iter_yaml_lines preserves the raw line content."""
        text = """  key: value
"""
        lines = list(iter_yaml_lines(text))
        assert lines[0].raw == "  key: value"
        assert lines[0].stripped == "key: value"

    def test_handles_mixed_content(self) -> None:
        """iter_yaml_lines handles mixed content correctly."""
        text = """# Header comment
section:
  # Inline comment
  key1: value1

  key2: value2
"""
        lines = list(iter_yaml_lines(text))
        assert len(lines) == 3
        assert lines[0].stripped == "section:"
        assert lines[0].is_top_level is True
        assert lines[1].stripped == "key1: value1"
        assert lines[1].indent == 2
        assert lines[2].stripped == "key2: value2"
        assert lines[2].indent == 2
