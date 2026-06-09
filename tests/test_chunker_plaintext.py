"""Tests for :class:`fa.chunker.PlainTextChunker`."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from fa.chunker import PlainTextChunker


def test_plain_text_yields_single_chunk(tmp_path: Path) -> None:
    body = "alpha\nbeta\ngamma\n"
    path = tmp_path / "notes.txt"
    path.write_text(body, encoding="utf-8")

    chunks = PlainTextChunker().chunk_file(path)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.body == body
    assert chunk.line_start == 1
    assert chunk.line_end == 3
    assert chunk.byte_start == 0
    assert chunk.byte_end == len(body.encode("utf-8"))
    assert chunk.parent_title == "notes.txt"
    assert chunk.breadcrumb == ()
    assert chunk.lang == "text"
    assert chunk.topic is None


def test_lang_label_is_propagated(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("key: value\n", encoding="utf-8")

    chunks = PlainTextChunker(lang="yaml").chunk_file(path)

    assert chunks[0].lang == "yaml"


def test_empty_file_emits_one_minimal_chunk(tmp_path: Path) -> None:
    path = tmp_path / "blank.txt"
    path.write_text("", encoding="utf-8")

    chunks = PlainTextChunker().chunk_file(path)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.body == ""
    assert chunk.byte_start == 0
    assert chunk.byte_end == 0
    assert chunk.line_start == 1
    assert chunk.line_end == 1


def test_no_trailing_newline_counts_last_line(tmp_path: Path) -> None:
    body = "alpha\nbeta"
    path = tmp_path / "ragged.txt"
    path.write_text(body, encoding="utf-8")

    chunks = PlainTextChunker().chunk_file(path)

    chunk = chunks[0]
    assert chunk.line_end == 2
    assert chunk.byte_end == len(body.encode("utf-8"))


def test_anchor_is_dot_safe_filename_slug(tmp_path: Path) -> None:
    """ADR-5 Decision step 3: ``anchor = filename`` for config files.

    Regression: a naive ``slugify(path.name)`` strips the ``.`` because it
    is not a word character, collapsing ``config.yaml`` and ``config.yml``
    to indistinguishable ``configyaml``/``configyml`` slugs and dropping
    the extension from human-facing displays. The chunker now uses a
    dot-safe slug (``config.yaml`` -> ``config-yaml``).
    """

    cases = [
        ("config.yaml", "config-yaml"),
        ("config.yml", "config-yml"),
        ("foo.py", "foo-py"),
        ("Module.PSM1", "module-psm1"),
        ("data.tar.gz", "data-tar-gz"),
        ("My Config.toml", "my-config-toml"),
    ]
    for name, expected_anchor in cases:
        path = tmp_path / name
        path.write_text("k: v\n", encoding="utf-8")
        actual_anchor = PlainTextChunker(lang="text").chunk_file(path)[0].anchor
        msg = f"{name!r} -> {actual_anchor!r}, expected {expected_anchor!r}"
        assert actual_anchor == expected_anchor, msg


@pytest.mark.skipif(sys.platform == "win32", reason="Windows does not allow dot-only filenames")
def test_anchor_falls_back_to_chunk_for_dot_only_name(tmp_path: Path) -> None:
    """A pathological filename consisting solely of dots produces no
    retainable characters once dots are mapped to hyphens and slugified.
    The chunker must then fall through to the deterministic ``"chunk"``
    placeholder rather than producing an empty anchor.
    """

    path = tmp_path / "..."
    path.write_text("contents\n", encoding="utf-8")

    chunk = PlainTextChunker().chunk_file(path)[0]

    assert chunk.anchor == "chunk"
