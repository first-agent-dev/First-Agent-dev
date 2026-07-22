"""End-to-end smoke tests for ``fa chunk <path>``."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from fa.chunker import CHUNKER_VERSION
from fa.cli import main


def _run_cli(monkeypatch: pytest.MonkeyPatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["fa", *argv])
    try:
        main()
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


def test_fa_chunk_text_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "doc.md"
    target.write_text("# Title\n\nbody\n", encoding="utf-8")

    code = _run_cli(monkeypatch, "chunk", str(target))

    assert code == 0
    captured = capsys.readouterr()
    assert "1 chunk(s)" in captured.out
    assert "[markdown]" in captured.out
    assert CHUNKER_VERSION in captured.out


def test_fa_chunk_json_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "doc.md"
    target.write_text("# Title\n\nbody\n", encoding="utf-8")

    code = _run_cli(monkeypatch, "chunk", str(target), "--output", "json")

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["chunker_version"] == CHUNKER_VERSION
    assert payload["path"] == str(target)
    assert len(payload["chunks"]) == 1
    chunk = payload["chunks"][0]
    assert chunk["anchor"] == "title"
    assert chunk["lang"] == "markdown"
    assert chunk["breadcrumb"] == []  # tuple → list in JSON


def test_fa_chunk_missing_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "does-not-exist.md"

    code = _run_cli(monkeypatch, "chunk", str(missing))

    assert code == 2
    assert "path not found" in capsys.readouterr().err


def test_fa_chunk_directory_argument_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _run_cli(monkeypatch, "chunk", str(tmp_path))

    assert code == 2
    assert "not a file" in capsys.readouterr().err


def test_fa_help_lists_chunk_subcommand(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _run_cli(monkeypatch)

    assert code == 0
    assert "chunk" in capsys.readouterr().out
