"""S20: Kill-check tests for TRACE mechanism (corrections.jsonl + compiler).

root=compile_corrections.py matrix=C claim=TRACE correction log + compiler
kill-check=empty corrections → empty summary; populated → grouped output
path-inventory: 2 paths (empty file, populated file)

Covers:
- Empty corrections.jsonl → "No corrections logged"
- Populated corrections.jsonl → grouped by code with counts
- Repeated code ≥2 → suggested rule candidate
- Invalid JSON lines → warning, not crash
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.compile_corrections import compile_summary, load_corrections, render_summary


def test_empty_corrections(tmp_path: Path) -> None:
    """Empty corrections.jsonl → 'No corrections logged' summary."""
    path = tmp_path / "corrections.jsonl"
    path.write_text("# TRACE: empty\n")
    entries = load_corrections(path)
    assert entries == []
    summary = compile_summary(entries)
    assert summary["total"] == 0
    assert "No corrections" in render_summary(summary)


def test_single_correction(tmp_path: Path) -> None:
    """One entry → total=1, by_code has one key."""
    path = tmp_path / "corrections.jsonl"
    path.write_text(json.dumps({
        "ts": "2026-07-20T00:00:00Z",
        "code": "FA-AUTHORING-001",
        "remediation": "Add IntentGuard check",
        "path": "src/fa/coder_loop.py",
        "corrected_by": "human",
    }) + "\n")
    entries = load_corrections(path)
    assert len(entries) == 1
    summary = compile_summary(entries)
    assert summary["total"] == 1
    assert "FA-AUTHORING-001" in summary["by_code"]


def test_repeated_code_suggests_rule(tmp_path: Path) -> None:
    """Code appearing ≥2 times → suggested_rules entry."""
    path = tmp_path / "corrections.jsonl"
    entries_data = [
        {"ts": "2026-07-20T00:00:00Z", "code": "FA-AUTHORING-002",
         "remediation": "Fix getattr", "path": "a.py", "corrected_by": "human"},
        {"ts": "2026-07-20T01:00:00Z", "code": "FA-AUTHORING-002",
         "remediation": "Fix getattr again", "path": "b.py", "corrected_by": "human"},
        {"ts": "2026-07-20T02:00:00Z", "code": "FA-AUTHORING-003",
         "remediation": "One-off", "path": "c.py", "corrected_by": "human"},
    ]
    path.write_text("\n".join(json.dumps(e) for e in entries_data) + "\n")
    entries = load_corrections(path)
    summary = compile_summary(entries)
    assert summary["total"] == 3
    # FA-AUTHORING-002 appears 2x → suggested
    assert len(summary["suggested_rules"]) == 1
    assert summary["suggested_rules"][0]["code"] == "FA-AUTHORING-002"
    # FA-AUTHORING-003 appears 1x → not suggested
    assert all(r["code"] != "FA-AUTHORING-003" for r in summary["suggested_rules"])


def test_invalid_json_skipped(tmp_path: Path) -> None:
    """Invalid JSON line → warning, not crash."""
    path = tmp_path / "corrections.jsonl"
    path.write_text(
        '{"ts":"2026-07-20T00:00:00Z","code":"OK","remediation":"x",'
        '"path":"a.py","corrected_by":"human"}\n{invalid json}\n'
    )
    entries = load_corrections(path)
    assert len(entries) == 1  # only the valid line


def test_missing_file_returns_empty(tmp_path: Path) -> None:
    """Missing corrections.jsonl → empty list, no crash."""
    path = tmp_path / "nonexistent.jsonl"
    entries = load_corrections(path)
    assert entries == []
