"""Smoke tests for build_suggestions + default_config_paths (R-13)."""

from __future__ import annotations

from pathlib import Path

from fa.hygiene import AuditReport, build_suggestions, default_config_paths


def test_suggestions_clean_default() -> None:
    report = AuditReport(stale_symbol_refs=0, bloat_score=0, probed_paths=5)
    assert build_suggestions(report) == ["Config looks clean."]


def test_suggestions_stale_refs_first() -> None:
    report = AuditReport(stale_symbol_refs=3, bloat_score=10, probed_paths=5)
    assert build_suggestions(report) == ["Remove stale symbol references"]


def test_suggestions_bloat_threshold_inclusive() -> None:
    report = AuditReport(stale_symbol_refs=0, bloat_score=60, probed_paths=5)
    assert build_suggestions(report) == ["Config files are bloated (score >=60)"]


def test_suggestions_bloat_below_threshold_silent() -> None:
    report = AuditReport(stale_symbol_refs=0, bloat_score=59, probed_paths=5)
    assert build_suggestions(report) == ["Config looks clean."]


def test_suggestions_stale_and_bloat_combine() -> None:
    report = AuditReport(stale_symbol_refs=2, bloat_score=80, probed_paths=5)
    assert build_suggestions(report) == [
        "Remove stale symbol references",
        "Config files are bloated (score >=60)",
    ]


def test_default_config_paths_returns_paths() -> None:
    paths = default_config_paths()
    assert isinstance(paths, tuple)
    assert all(isinstance(path, Path) for path in paths)


def test_default_config_paths_includes_agents_and_claude() -> None:
    paths = default_config_paths()
    names = [path.name for path in paths]
    assert "AGENTS.md" in names
    assert "CLAUDE.md" in names
    assert ".cursorrules" in names


def test_default_config_paths_is_deterministic() -> None:
    assert default_config_paths() == default_config_paths()
