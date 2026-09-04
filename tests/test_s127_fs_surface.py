"""S12.7 S7b (§A6 v7) — fs_search locked-surface pins: merged matches, files
sizes + skip report, removed-mode steering, leniency, path-absorbs-glob.

P-matrix coverage: P14 (T-lenient), P17 (T-merge/T-dense), P18
(T-files-sizes), P19 (T-steer-mode). C1: real tool on real tmp workspaces.
"""

from __future__ import annotations

from pathlib import Path

from fa.inner_loop.registry import ToolSpec
from fa.inner_loop.tools.fs_search import MAX_RESPONSE_BYTES, build_fs_search_tool


def _mk(tmp_path: Path) -> ToolSpec:
    return build_fs_search_tool(tmp_path / ".fa" / "fts.db", tmp_path)


# ---------------------------------------------------------------------------
# P17 / T-merge — gap threshold, marking, region shape
# ---------------------------------------------------------------------------


def test_s127_merge_gap_threshold(tmp_path: Path) -> None:
    """Gap <= 2 merges; gap 3 splits (fixed constant — R22)."""
    src = tmp_path / "g.py"
    src.write_text(
        "needle\n"  # 1
        "filler\n"  # 2
        "needle\n"  # 3   gap 2 -> merges with 1
        "filler\n"  # 4
        "filler\n"  # 5
        "needle\n"  # 6   gap 3 from 3 -> NEW region
        "needle\n",  # 7  gap 1 -> merges with 6
        encoding="utf-8",
    )
    tool = _mk(tmp_path)
    r = tool.handler({"query": "needle", "output_mode": "matches", "limit": 10})
    assert r.result is not None
    assert r.error is None
    regions = [m for m in r.result["matches"] if m["path"] == "g.py"]
    assert len(regions) == 2, f"expected 2 regions (gap<=2 merges, gap 3 splits); got {regions}"
    first, second = regions
    assert first["match_lines"] == [1, 3] and first["start_line"] == 1 and first["end_line"] == 4
    assert second["match_lines"] == [6, 7] and second["start_line"] == 5 and second["end_line"] == 7
    for m in regions:
        assert set(m.keys()) == {"path", "start_line", "end_line", "match_lines", "match_count", "snippet"}
        assert m["match_count"] == len(m["match_lines"])


def test_s127_merge_marking_hits_and_context(tmp_path: Path) -> None:
    src = tmp_path / "m.py"
    src.write_text("a\nNEEDLE\nb\n", encoding="utf-8")
    tool = _mk(tmp_path)
    r = tool.handler({"query": "needle", "output_mode": "matches"})  # ci always
    assert r.result is not None
    assert r.error is None and len(r.result["matches"]) == 1
    assert r.result["matches"][0]["snippet"] == ["1-a", "2:NEEDLE", "3-b"], (
        "grep marking: N: hits, N- context (1 fixed context line per side)"
    )


# ---------------------------------------------------------------------------
# P17 / T-dense — per-region byte bound + trailer; limit caps REGIONS
# ---------------------------------------------------------------------------


def test_s127_dense_cluster_trailer_and_byte_bound(tmp_path: Path) -> None:
    """200 adjacent long hit lines must NOT balloon: the region renders up to
    the per-region byte bound and reports elided hits in a trailer."""
    lines = [f"needle_{i} = '{'x' * 180}'" for i in range(200)]
    (tmp_path / "dense.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
    tool = _mk(tmp_path)
    r = tool.handler({"query": "needle_", "output_mode": "matches", "limit": 10})
    assert r.error is None
    matches = r.result
    assert matches is not None
    assert len(matches["matches"]) == 1, "adjacent hits (gap 1) merge into ONE region"
    region = matches["matches"][0]
    assert region["match_count"] == 200
    rendered = [s for s in region["snippet"] if not s.startswith("[")]
    trailer = [s for s in region["snippet"] if s.startswith("[")]
    assert len(rendered) < 200, "byte bound must cut the render"
    assert len(trailer) == 1 and "more hits in lines" in trailer[0], (
        f"elided hits must be trailer-reported, got {region['snippet'][-1]!r}"
    )
    import json as _json

    assert len(_json.dumps(region["snippet"])) < 4_400  # REGION_SNIPPET_MAX_BYTES + slack


def test_s127_limit_caps_regions_not_hits(tmp_path: Path) -> None:
    (tmp_path / "one.py").write_text("needle\nx\n\nneedle\n", encoding="utf-8")  # 1 region
    (tmp_path / "two.py").write_text("needle\n", encoding="utf-8")  # 1 region
    (tmp_path / "three.py").write_text("needle\n", encoding="utf-8")  # 1 region
    tool = _mk(tmp_path)
    r = tool.handler({"query": "needle", "output_mode": "matches", "limit": 2})
    assert r.result is not None
    assert r.error is None
    assert r.result["returned"] == 2 and r.result["truncated"] is True, "limit caps REGIONS; more regions existed"
    assert r.result["total"] == 3, "F9: matches must surface pre-limit region count"


# ---------------------------------------------------------------------------
# P18 / T-files-sizes — stat rows + skip report
# ---------------------------------------------------------------------------


def test_s127_files_rows_lines_bytes_and_skip_report(tmp_path: Path) -> None:
    (tmp_path / "small.py").write_text("needle\nx\ny\n", encoding="utf-8")
    big = tmp_path / "big.py"
    big.write_text("needle\n" + "# filler\n" * 60_000, encoding="utf-8")  # >200KB
    assert big.stat().st_size > 200_000
    tool = _mk(tmp_path)
    r = tool.handler({"query": "needle", "output_mode": "files"})
    assert r.result is not None
    assert r.error is None
    rows = r.result["files"]
    assert [f["path"] for f in rows] == ["small.py"], "big.py is over the cap: no row"
    row = rows[0]
    assert row["lines"] == 3 and row["bytes"] == (tmp_path / "small.py").stat().st_size
    assert r.result["skipped_large_files"] == 1, "skip must be SURFACED, not silent"
    # listing (no query) surfaces the same skip report
    lst = tool.handler({"output_mode": "files"})
    assert lst.result is not None
    assert lst.result["skipped_large_files"] == 1
    assert [f["path"] for f in lst.result["files"]] == ["small.py"]
    (tmp_path / "empty.py").write_text("", encoding="utf-8")
    empty = tool.handler({"output_mode": "files", "path": "empty.py"})
    assert empty.result is not None
    assert empty.result["files"] == [{"path": "empty.py", "lines": 0, "bytes": 0}], (
        "empty file: lines=0 (None is reserved for unreadable)"
    )


# ---------------------------------------------------------------------------
# P19 / T-steer-mode — removed modes error, no alias
# ---------------------------------------------------------------------------


def test_s127_removed_modes_steer(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("needle\n", encoding="utf-8")
    tool = _mk(tmp_path)
    for legacy in ("regions", "counts"):
        r = tool.handler({"query": "needle", "output_mode": legacy})
        assert r.error is not None and r.error.code == "invalid_params", legacy
        msg = r.error.message
        assert "matches" in msg and "files" in msg, f"steering must name replacements: {msg}"
        assert "outline" in msg, f"steering must list ALL valid modes: {msg}"
        assert "no longer exists" in msg, f"removed modes need fold guidance, not a bare enum error: {msg}"
        assert r.result is None, "no aliasing — removed modes never return results"


def test_s127_unknown_mode_lists_valid(tmp_path: Path) -> None:
    tool = _mk(tmp_path)
    r = tool.handler({"query": "x", "output_mode": "bogus"})
    assert r.error is not None
    assert r.error.code == "invalid_params"
    assert "files" in r.error.message and "matches" in r.error.message and "outline" in r.error.message


# ---------------------------------------------------------------------------
# P14 / T-lenient — absent query per mode, zero-hit, legacy knob warnings
# ---------------------------------------------------------------------------


def test_s127_lenient_absent_query_per_mode(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("needle\n", encoding="utf-8")
    tool = _mk(tmp_path)
    files_r = tool.handler({"output_mode": "files"})
    assert files_r.result is not None
    assert files_r.error is None and files_r.result["method"] == "walk_listing"
    assert files_r.result["total"] == 1 and files_r.result["files"][0]["path"] == "a.py"
    matches_r = tool.handler({"output_mode": "matches"})
    assert matches_r.error is not None
    assert matches_r.error.code == "invalid_params" and "matches" in matches_r.error.message
    outline_r = tool.handler({"output_mode": "outline", "path": "a.py"})
    assert outline_r.result is not None
    assert outline_r.error is None and outline_r.result["mode"] == "outline"


def test_s127_lenient_zero_hit_steers(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("needle\n", encoding="utf-8")
    tool = _mk(tmp_path)
    zero = tool.handler({"query": "definitely_not_present_token", "output_mode": "files"})
    assert zero.result is not None
    assert zero.error is None and zero.result["files"] == [], "zero hits: empty rows, never an error"
    assert zero.result.get("warnings", []) == [], "zero-hit adds no noise (honest empty)"


def test_s127_lenient_all_six_removed_params_warn(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("needle\n", encoding="utf-8")
    tool = _mk(tmp_path)
    r = tool.handler(
        {
            "query": "needle",
            "output_mode": "files",
            "order": "path",
            "include_tests": False,
            "glob": "*.py",
            "case_sensitive": True,
            "max_file_size": 10,
            "context_lines": 9,
        }
    )
    assert r.result is not None
    assert r.error is None, "legacy knobs must never fail the call (CT11 leniency)"
    warned = {w.split("'")[1] for w in r.result["warnings"] if "accepted but ignored" in w}
    assert warned == {"order", "include_tests", "glob", "case_sensitive", "max_file_size", "context_lines"}


def test_s127_path_absorbs_glob(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("needle\n", encoding="utf-8")
    (tmp_path / "src" / "y.md").write_text("needle\n", encoding="utf-8")
    tool = _mk(tmp_path)
    r = tool.handler({"query": "needle", "output_mode": "files", "path": "src/*.py"})
    assert r.result is not None
    assert r.error is None and [f["path"] for f in r.result["files"]] == ["src/x.py"]
    lst = tool.handler({"output_mode": "files", "path": "*.md"})
    assert lst.result is not None
    assert lst.error is None and [f["path"] for f in lst.result["files"]] == ["src/y.md"]


def test_s127_regex_casing_comes_from_pattern(tmp_path: Path) -> None:
    """R21/Q4: regex compiles with NO forced flags — an uppercase pattern must
    NOT match lowercase content; '(?i)' opts in."""
    (tmp_path / "r.py").write_text("needle_lower()\n", encoding="utf-8")
    tool = _mk(tmp_path)
    strict = tool.handler({"query": "NE[ED]+DLE", "output_mode": "matches", "regex": True})
    assert strict.result is not None
    assert strict.error is None and strict.result["matches"] == [], "no forced IGNORECASE on regex"
    ci = tool.handler({"query": "(?i)NE[ED]+DLE", "output_mode": "matches", "regex": True})
    assert ci.result is not None
    assert ci.error is None and len(ci.result["matches"]) == 1, "pattern-level (?i) opts in"


def test_s127_response_cap_is_32768() -> None:
    assert MAX_RESPONSE_BYTES == 32_768, "CT2 alignment: the read budget ceiling (S2/S4)"


def test_s127_f9_byte_cap_warning_names_total() -> None:
    """F9: byte-cap truncation must name the pre-cap match total once."""
    from fa.inner_loop.tools.fs_search import _enforce_response_cap

    rows = [{"path": f"f{i}.py", "lines": 1, "bytes": 1, "pad": "x" * 4000} for i in range(20)]
    result = {
        "returned": 20,
        "total": 62,
        "truncated": False,
        "files": rows,
        "warnings": [],
    }
    _enforce_response_cap(result)
    assert result["truncated"] is True
    assert result["returned"] < 20
    cap_warns = [w for w in result["warnings"] if "byte cap" in w]
    assert len(cap_warns) == 1
    assert "62 matched" in cap_warns[0]


def test_s127_files_stat_rows_is_the_sorting_authority(tmp_path: Path) -> None:
    """C0, deterministic: files rows are path-ordered regardless of input
    order (kill-pin for sort removal in files_stat_rows)."""
    from fa.memory.search_index import files_stat_rows

    for name in ("m.py", "a.py", "z.py", "b.py"):
        (tmp_path / name).write_text("x = 1\n", encoding="utf-8")
    rows = files_stat_rows(tmp_path, ["m.py", "z.py", "a.py", "b.py"], 10)
    assert [r["path"] for r in rows] == ["a.py", "b.py", "m.py", "z.py"]
    limited = files_stat_rows(tmp_path, ["m.py", "z.py", "a.py", "b.py"], 2)
    assert [r["path"] for r in limited] == ["a.py", "b.py"], "limit slices the SORTED set"


def test_s127_subagent_fts_files_survive_surface_lock(tmp_path: Path) -> None:
    """R25/F1 pin: _get_fts_files used the REMOVED SearchParams.include_tests
    kwarg — TypeError was swallowed by the best-effort blanket and file
    discovery silently degraded to []. Must return real files, tests excluded."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "mod.py").write_text("def pay_invoice():\n    return 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_pay.py").write_text("def test_pay_invoice():\n    assert 1\n", encoding="utf-8")
    from fa.inner_loop.subagent_prompts import _get_fts_files

    files = _get_fts_files(tmp_path, "pay_invoice", 10)
    assert "src/mod.py" in files, f"FTS discovery broken (masked-empty regression): {files}"
    assert not any(f.startswith("tests/") for f in files), f"tests must be excluded: {files}"


def test_s127_regex_flag_warns_in_outline_mode(tmp_path: Path) -> None:
    """R25/F2: regex=true is meaningless for outline (literal name filter) —
    must warn-and-ignore per CT11 philosophy, not pass silently."""
    (tmp_path / "o.py").write_text("def alpha():\n    pass\n", encoding="utf-8")
    tool = _mk(tmp_path)
    r = tool.handler({"path": "o.py", "output_mode": "outline", "query": "alp", "regex": True})
    assert r.result is not None
    assert r.error is None and [x["name"] for x in r.result["rows"]] == ["alpha"], "filter stays literal"
    assert any("'regex' is accepted but ignored in outline" in w for w in r.result["warnings"])


def test_s127_outline_ignores_scope_filters_with_warning(tmp_path: Path) -> None:
    """R26/G2: exclude_dirs is meaningless for outline (ONE file) — must
    warn-and-ignore like regex (CT11 observable-warnings philosophy)."""
    (tmp_path / "o.py").write_text("def alpha():\n    pass\n", encoding="utf-8")
    tool = _mk(tmp_path)
    r = tool.handler({"path": "o.py", "output_mode": "outline", "exclude_dirs": ["src"]})
    assert r.result is not None
    assert r.error is None and [x["name"] for x in r.result["rows"]] == ["alpha"]
    assert any("'exclude_dirs' is accepted but ignored in outline" in w for w in r.result["warnings"])
