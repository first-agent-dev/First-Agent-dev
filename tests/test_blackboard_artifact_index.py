"""S14 / I-56 — artifact indexer tests (PLAN-cli-trace-S14-blackboard-substrate-completion).

Tests per §4 contracts and §5 path/flag matrix of the plan:
- C0p: pure helpers (deterministic id, layout check, title extraction).
- C1: real SessionState + Blackboard (temp-dir SQLite), real ToolRegistry dispatch.
  Uses tmp_path workspaces with populated knowledge/ trees; no provider calls.

**Kill-checks (must fail if the producer is removed):**
- removing ``blackboard.write(entry)`` in artifact_index.ensure_artifacts_indexed
  → test_indexing_populates_skill_adr_rows / test_query_tool_lazy_indexes_on_first_artifact_call fail.
- removing the ``ensure_artifacts_indexed(...)`` call in the handler
  → test_query_tool_lazy_indexes_on_first_artifact_call returns [] rows.
- removing the type-scoped filter in ``Blackboard.detect_conflict``
  → test_artifact_entries_do_not_trigger_file_version_conflict fires false positive.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

import pytest

from fa.blackboard import artifact_index
from fa.blackboard.artifact_index import (
    ARTIFACT_ROOTS,
    ARTIFACT_TYPES,
    ArtifactIndexStats,
    _logical_id,
    _title_from_content,
    ensure_artifacts_indexed,
)
from fa.blackboard.blackboard import Blackboard, BlackboardEntry
from fa.inner_loop import SessionState, ToolCall
from fa.inner_loop.context import reset_current_session, set_current_session
from fa.inner_loop.registry import ToolRegistry, ToolResult
from fa.inner_loop.tools.blackboard_query import build_blackboard_query_tool
from tests._capabilities import requires_symlinks

# --- fixtures ------------------------------------------------------------------


def _write_knowledge(ws: Path, files: dict[str, str]) -> None:
    """Create ``files`` under ws/knowledge/. Keys are relpaths, values are content."""
    k = ws / "knowledge"
    for rel, content in files.items():
        p = k / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def _small_knowledge() -> dict[str, str]:
    """Return a minimal knowledge tree covering 3 skills + 4 adrs + 1 research + BACKLOG."""
    return {
        "skills/plan-authoring/SKILL.md": "# Plan Authoring Skill\nBody of plan-authoring.",
        "skills/tests-writing/SKILL.md": "# Tests Writing Skill\nBody of tests-writing.",
        "skills/feature-planning/SKILL.md": "# Feature Planning Skill\nBody of feature-planning.",
        "adr/ADR-10-deterministic-harness-invariants.md": "# ADR-10 Deterministic Harness\n...",
        "adr/ADR-16-conflict-detection.md": "# ADR-16 Conflict Detection\n...",
        "adr/ADR-7-blackboard.md": "# ADR-7 Blackboard\n...",
        "adr/DIGEST.md": "# ADR Digest\n...",
        "research/test-note.md": "# A Research Note\nBody of research.",
        "BACKLOG.md": "# Backlog\nBacklog contents.",
    }


def _dispatch(state: SessionState, params: Mapping[str, object]) -> ToolResult:
    registry = ToolRegistry()
    registry.register(build_blackboard_query_tool())
    token = set_current_session(state)
    try:
        return registry.dispatch(ToolCall(name="fs_blackboard_query", params=dict(params)))
    finally:
        reset_current_session(token)


# --- C0p: pure helpers ---------------------------------------------------------


def test_det_id_is_deterministic() -> None:
    """C0p — _logical_id is stable across calls and length-bounded."""
    a = _logical_id("skill", "skills/plan-authoring/SKILL.md")
    b = _logical_id("skill", "skills/plan-authoring/SKILL.md")
    assert a == b
    assert a.startswith("skill:")
    # hash portion = 12 hex chars + "skill:" (6) = 18 chars
    assert len(a) == 6 + 12


def test_artifact_roots_layout_matches_live_tree() -> None:
    """C0p — every ARTIFACT_ROOTS subdir exists in the real knowledge/ tree in-repo.

    Guards against accidental rename of a knowledge/ subdir without updating
    the indexer constants.
    """
    repo_root = Path(__file__).resolve().parents[1]
    knowledge_root = repo_root / "knowledge"
    # This test only makes sense running against the live checkout (it
    # asserts the constants match the repo layout). Running the suite from
    # outside a First-Agent checkout is not a supported configuration;
    # fail loudly instead of silently skipping so a truncated checkout is
    # visible.
    assert knowledge_root.is_dir(), (
        f"knowledge/ directory not found at {knowledge_root}; tests must run inside a First-Agent checkout"
    )
    for _type, sub in ARTIFACT_ROOTS.items():
        assert (knowledge_root / sub).is_dir(), f"ARTIFACT_ROOTS[{_type!r}]={sub!r} but knowledge/{sub} is missing"


def test_title_from_content_extracts_h1() -> None:
    """C0p — _title_from_content picks the first ATX H1 (``# ``); falls back to
    first non-empty line (heading prefix stripped by [2:] is a happy accident we
    don't rely on — the doc says H1); else fallback arg."""
    assert _title_from_content("# Hello World\nbody", "fb") == "Hello World"
    # A line starting with "##" is not "# ", so first H1 (# Hello) is "Hello".
    assert _title_from_content("## H2\n\n# Hello\nbody", "fb") == "Hello"
    # No H1 anywhere → first non-empty line, stripped of any leading "#" via s[:200].
    assert _title_from_content("no heading\nbody line", "fb") == "no heading"
    assert _title_from_content("\n\n  \n", "fallback") == "fallback"


# --- C1: indexer against a real Blackboard ------------------------------------


def test_indexing_populates_skill_adr_rows(tmp_path: Path) -> None:
    """C1 T1 — ensure_artifacts_indexed populates typed rows for skill/adr/research/BACKLOG."""
    _write_knowledge(tmp_path, _small_knowledge())
    state = SessionState(workspace_root=tmp_path, run_id="run-1")
    assert state.blackboard is not None

    stats = ensure_artifacts_indexed(state.blackboard, tmp_path)
    assert stats.added == 3 + 4 + 1 + 1  # skills + adrs + research + BACKLOG
    assert stats.updated == 0
    assert stats.skipped_unchanged == 0
    assert stats.errors == []
    assert stats.indexed_types == {"skill", "adr", "research"}

    skill_rows = state.blackboard.query(type="skill")
    assert len(skill_rows) == 3
    adr_rows = state.blackboard.query(type="adr")
    assert len(adr_rows) == 4
    research_rows = state.blackboard.query(type="research")
    # 1 research file + BACKLOG.md (root special) = 2
    assert len(research_rows) == 2

    # Paths and titles are present in compact projection.
    for e in skill_rows:
        assert isinstance(e.payload, dict)
        assert e.payload["path"].startswith("skills/")
        assert e.payload["title"]
        assert e.payload["file_hash"]
        assert e.write_set == [e.payload["path"]]
        assert e.read_set == []
        assert e.assumptions == []
        assert e.parent_id is None  # first revision


def test_indexing_is_idempotent(tmp_path: Path) -> None:
    """C1 T2 — double call is a no-op; no duplicate rows."""
    _write_knowledge(tmp_path, _small_knowledge())
    state = SessionState(workspace_root=tmp_path, run_id="run-1")
    assert state.blackboard is not None

    s1 = ensure_artifacts_indexed(state.blackboard, tmp_path)
    counts_after_first = {t: len(state.blackboard.query(type=t)) for t in ARTIFACT_TYPES}

    s2 = ensure_artifacts_indexed(state.blackboard, tmp_path)
    counts_after_second = {t: len(state.blackboard.query(type=t)) for t in ARTIFACT_TYPES}

    assert s2.added == 0
    assert s2.updated == 0
    assert s2.skipped_unchanged == s1.added
    assert counts_after_first == counts_after_second


def test_query_tool_lazy_indexes_on_first_artifact_call(tmp_path: Path) -> None:
    """C1 T3 — dispatching fs_blackboard_query(type='skill') triggers lazy indexing
    and returns rows with the additive 'indexed' metadata."""
    _write_knowledge(tmp_path, _small_knowledge())
    state = SessionState(workspace_root=tmp_path, run_id="run-1")

    result = _dispatch(state, {"type": "skill"})
    assert result.error is None
    data = result.result
    assert data is not None
    rows = data["rows"]
    assert len(rows) == 3
    assert "indexed" in data, "first artifact call must report 'indexed' stats"
    # type=skill limits indexing to skills only (no cross-type indexing on
    # targeted queries; efficient; wildcard indexes all).
    assert data["indexed"]["added"] == 3
    assert data["indexed"]["types"] == ["skill"]
    # Titles are surfaced in compact rows.
    titles = {r.get("title") for r in rows}
    assert titles == {"Plan Authoring Skill", "Tests Writing Skill", "Feature Planning Skill"}

    # Second call: no new additions.
    result2 = _dispatch(state, {"type": "skill"})
    data2 = result2.result
    assert data2 is not None
    assert data2["indexed"]["added"] == 0
    assert data2["indexed"]["skipped"] == 3


def test_query_tool_wildcard_indexes_all_artifact_types(tmp_path: Path) -> None:
    """C1 T4 — wildcard (no type) triggers indexing across all ARTIFACT_TYPES present
    and returns rows covering ≥3 distinct types."""
    files = {
        "skills/a/SKILL.md": "# Skill A\n",
        "adr/ADR-1.md": "# ADR-1\n",
        "research/r.md": "# R\n",
        "prompts/p.md": "# P\n",
        "instructions/i.md": "# I\n",
        "codemaps/c.md": "# C\n",
        "anti-patterns/ap.md": "# AP\n",
        "BACKLOG.md": "# Backlog\n",
    }
    _write_knowledge(tmp_path, files)
    state = SessionState(workspace_root=tmp_path, run_id="run-1")

    result = _dispatch(state, {})
    assert result.error is None
    data = result.result
    assert data is not None
    types_returned = {r["type"] for r in data["rows"]}
    # skill + adr + research (includes BACKLOG) + prompt + instruction + codemap + antipattern
    assert types_returned >= {"skill", "adr", "research", "prompt", "instruction", "codemap", "antipattern"}


def test_artifact_entries_do_not_trigger_file_version_conflict(tmp_path: Path) -> None:
    """C1 T5 — SAFETY-CRITICAL: after indexing artifacts, a synthetic file_version
    write (representative of mutation_guard's pre-write check) does NOT trigger
    false-positive conflicts against artifact rows.

    Invariant: detect_conflict filters by new_entry.type, so same-write_set
    overlap across TYPES is not treated as a conflict.
    """
    _write_knowledge(tmp_path, _small_knowledge())
    state = SessionState(workspace_root=tmp_path, run_id="run-1")
    assert state.blackboard is not None
    ensure_artifacts_indexed(state.blackboard, tmp_path)

    # Synthetic file_version write overlapping an artifact path via read_set.
    new_entry = BlackboardEntry.create(
        id="fv-test",
        type="file_version",
        payload={"path": "src/foo.py"},
        read_set=["adr/ADR-10-deterministic-harness-invariants.md"],
        write_set=["src/foo.py"],
        assumptions=["base_commit abc"],
        version_dependencies={"base_commit": "abc"},
    )
    conflicts = state.blackboard.detect_conflict(new_entry)
    assert conflicts == [], f"artifact entries must not conflict with file_version; got {conflicts!r}"


def test_query_tool_does_not_index_on_file_version_query(tmp_path: Path) -> None:
    """C1 T6 — type='file_version' must NOT invoke the indexer (fast path)."""
    _write_knowledge(tmp_path, _small_knowledge())
    state = SessionState(workspace_root=tmp_path, run_id="run-1")
    assert state.blackboard is not None
    # Seed a file_version row directly so the query has something to return.
    state.blackboard.write(
        BlackboardEntry.create(
            id="fv1",
            type="file_version",
            payload={"path": "src/foo.py"},
            read_set=["src/foo.py"],
            write_set=["src/foo.py"],
        )
    )
    # Spy on ensure_artifacts_indexed. Signature matches the target so
    # mypy/pyrefly strict do not widen *a/**k to object.
    calls = {"n": 0}
    original = artifact_index.ensure_artifacts_indexed

    def _spy(
        blackboard: Blackboard,
        workspace_root: Path,
        types: set[str] | None = None,
    ) -> ArtifactIndexStats:
        calls["n"] += 1
        return original(blackboard, workspace_root, types)

    from fa.blackboard import artifact_index as ai_mod

    ai_mod.ensure_artifacts_indexed = _spy  # monkeypatch
    try:
        result = _dispatch(state, {"type": "file_version"})
    finally:
        ai_mod.ensure_artifacts_indexed = original  # monkeypatch

    assert result.error is None
    data = result.result
    assert data is not None
    assert calls["n"] == 0, "file_version queries must not trigger indexing"
    assert "indexed" not in data
    assert len(data["rows"]) == 1


def test_indexing_missing_knowledge_dir_is_noop(tmp_path: Path) -> None:
    """C1 T7 — workspace without knowledge/ → stats zero, no raise."""
    state = SessionState(workspace_root=tmp_path, run_id="run-1")
    assert state.blackboard is not None
    stats = ensure_artifacts_indexed(state.blackboard, tmp_path)
    assert stats.scanned == 0
    assert stats.added == 0
    assert stats.errors == []


def test_indexing_skips_oversized_files(tmp_path: Path) -> None:
    """C1 T8 — files over _MAX_FILE_BYTES are skipped with a too_large error."""
    k = tmp_path / "knowledge" / "skills"
    k.mkdir(parents=True)
    big = k / "big.md"
    big.write_bytes(b"# Big\n" + b"x" * (artifact_index._MAX_FILE_BYTES + 1))
    # small control file
    (k / "small.md").write_text("# Small\n", encoding="utf-8")

    state = SessionState(workspace_root=tmp_path, run_id="run-1")
    assert state.blackboard is not None
    stats = ensure_artifacts_indexed(state.blackboard, tmp_path)
    assert stats.added == 1
    assert any("too_large" in e for e in stats.errors)
    # Only the small file is present.
    rows = state.blackboard.query(type="skill")
    assert len(rows) == 1
    assert rows[0].payload["title"] == "Small"


def test_indexing_continues_past_per_file_io_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C1 T9 — a read failure on one file does not abort indexing of other files."""
    _write_knowledge(
        tmp_path,
        {
            "skills/a/SKILL.md": "# A\n",
            "skills/b/SKILL.md": "# B\n",
            "skills/c/SKILL.md": "# C\n",
        },
    )
    state = SessionState(workspace_root=tmp_path, run_id="run-1")
    assert state.blackboard is not None

    # Make read_bytes raise on one specific path.
    original_read_bytes = Path.read_bytes
    target = tmp_path / "knowledge" / "skills" / "b" / "SKILL.md"

    def _throttled(self: Path, *a: object, **k: object) -> bytes:
        if self.resolve() == target.resolve():
            raise OSError("permission denied")
        return original_read_bytes(self, *a, **k)

    monkeypatch.setattr(Path, "read_bytes", _throttled)
    stats = ensure_artifacts_indexed(state.blackboard, tmp_path)
    assert stats.added == 2  # a + c
    assert any("permission denied" in e for e in stats.errors)
    assert len(state.blackboard.query(type="skill")) == 2


def test_changed_file_creates_new_entry_with_parent_id(tmp_path: Path) -> None:
    """C1 T10 — modifying a file produces a NEW physical entry with parent_id set;
    old entry preserved (append-only)."""
    _write_knowledge(tmp_path, {"skills/a/SKILL.md": "# A v1\n"})
    state = SessionState(workspace_root=tmp_path, run_id="run-1")
    assert state.blackboard is not None
    s1 = ensure_artifacts_indexed(state.blackboard, tmp_path)
    assert s1.added == 1
    first_rows = state.blackboard.query(type="skill")
    assert len(first_rows) == 1
    first = first_rows[0]

    # Mutate the file.
    target = tmp_path / "knowledge" / "skills" / "a" / "SKILL.md"
    original = target.read_text()
    target.write_text(original + "changed\n", encoding="utf-8")
    # Force mtime to advance (some filesystems have coarse mtime).
    os.utime(target, None)

    s2 = ensure_artifacts_indexed(state.blackboard, tmp_path)
    assert s2.updated == 1
    assert s2.added == 0
    all_rows = state.blackboard.query(type="skill")
    assert len(all_rows) == 2, "append-only: must retain old entry"
    latest = next(e for e in all_rows if e.id != first.id)
    assert latest.parent_id == first.id
    assert isinstance(latest.payload, dict)
    assert isinstance(first.payload, dict)
    assert latest.payload["logical_id"] == first.payload["logical_id"]
    assert latest.payload["file_hash"] != first.payload["file_hash"]


def test_query_tool_fail_degraded_when_indexer_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C1 T11 — if the indexer raises at the top level, the handler logs and returns
    existing rows (ToolResult.ok), not a failure."""
    _write_knowledge(tmp_path, _small_knowledge())
    state = SessionState(workspace_root=tmp_path, run_id="run-1")

    from fa.blackboard import artifact_index as ai_mod

    def _boom(*a: object, **k: object) -> ArtifactIndexStats:
        raise RuntimeError("indexer exploded")

    monkeypatch.setattr(ai_mod, "ensure_artifacts_indexed", _boom)

    result = _dispatch(state, {"type": "skill"})
    assert result.error is None
    assert result.result is not None
    # Result rows may be empty (indexer blew before writing), but no crash.
    assert "rows" in result.result


@requires_symlinks
def test_indexer_respects_symlink_escape(tmp_path: Path) -> None:
    """C1 T9b — _is_within blocks a symlink pointing outside knowledge/.
    Recorded as 'escape' error; other files indexed normally."""
    _write_knowledge(tmp_path, {"skills/a/SKILL.md": "# A\n"})
    outside = tmp_path / "outside.txt"
    outside.write_text("# ESCAPED\nsecret content", encoding="utf-8")
    link = tmp_path / "knowledge" / "skills" / "evil.md"
    link.symlink_to(outside)
    state = SessionState(workspace_root=tmp_path, run_id="run-1")
    assert state.blackboard is not None
    stats = ensure_artifacts_indexed(state.blackboard, tmp_path)
    assert stats.added == 1  # only the legitimate skill
    assert any("escape" in e for e in stats.errors)
    # Ensure no entry references the outside path and no content leaked.
    all_rows = state.blackboard.query(type="skill")
    assert len(all_rows) == 1
    assert all_rows[0].payload["path"] == "skills/a/SKILL.md"
