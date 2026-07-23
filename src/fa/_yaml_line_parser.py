"""Shared YAML-like line parsing utilities.

This module contains common line iteration logic used by multiple configuration
parsers to avoid duplication and ensure consistent handling of YAML-like formats.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedLine:
    """Parsed information about a single non-blank, non-comment YAML-like line.

    Blank lines and comment lines are filtered by :func:`iter_yaml_lines`
    before being yielded, so every ``ParsedLine`` instance represents a
    content line.
    """

    line_no: int
    raw: str
    stripped: str
    indent: int
    is_top_level: bool


def iter_yaml_lines(text: str) -> Iterator[ParsedLine]:
    """Iterate over YAML-like text, yielding parsed line information.

    Skips blank lines and comments, tracks indentation, and identifies
    top-level keys (indent == 0).

    Args:
        text: YAML-like configuration text.

    Yields:
        :class:`ParsedLine` for every content (non-blank, non-comment) line,
        with 1-based ``line_no`` matching the source text.

    Example:
        >>> text = '''
        ... # Comment
        ... capabilities:
        ...   flag1: true
        ...   flag2: false
        ... '''
        >>> for line in iter_yaml_lines(text):
        ...     if line.is_top_level:
        ...         print(f"Section: {line.stripped}")
        Section: capabilities:
    """
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()

        # Skip blank lines
        if not line.strip():
            continue

        # Skip comments
        if line.lstrip().startswith("#"):
            continue

        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        is_top_level = indent == 0

        yield ParsedLine(
            line_no=line_no,
            raw=line,
            stripped=stripped,
            indent=indent,
            is_top_level=is_top_level,
        )


__all__ = ["ParsedLine", "iter_yaml_lines"]
