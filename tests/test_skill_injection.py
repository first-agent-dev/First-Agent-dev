"""S10.3 — L2 skill-body injection reader (CT5).

root=skill-reader class=C0p/C0 claim=G6 path=T3
oracle=exact block dict fields, frontmatter/body split, warm predicate, warnings.
Wiring into skills_conditional is verified in S10.4 (producer kill-check there);
this slice proves the reader the wiring will call.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.inner_loop.expansion import select_l2_skill
from fa.skills._inject import (
    SKILL_FILE_NAME,
    SKILLS_RELATIVE_DIR,
    build_skill_anchor,
    build_skill_block,
    default_skills_root,
    parse_frontmatter,
    plan_artifact_present,
    read_skill_for_injection,
    split_frontmatter,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

FIXTURE_SKILL = """\
---
name: test-skill
description: |
  A test skill used to verify injection.
  Second line of description.
status: active
triggers:
  - "do a thing"
globs:
  - "tests/**"
---
# Body heading

Step one. Step two.
- bullet
"""

FIXTURE_NO_FRONTMATTER = "# Just a heading\n\nBody text without frontmatter.\n"


# ── split_frontmatter ──────────────────────────────────────────────────────


def test_split_frontmatter_separates_yaml_and_body() -> None:
    fm, body = split_frontmatter(FIXTURE_SKILL)
    assert "name: test-skill" in fm
    assert "triggers:" in fm
    # kill-check: frontmatter stripped — no YAML keys leak into body
    assert "triggers:" not in body
    assert "globs:" not in body
    assert "status: active" not in body
    assert body.startswith("# Body heading")


def test_split_frontmatter_without_frontmatter() -> None:
    fm, body = split_frontmatter(FIXTURE_NO_FRONTMATTER)
    assert fm == ""
    assert body.strip() == FIXTURE_NO_FRONTMATTER.strip()


def test_split_frontmatter_unterminated_gives_empty_body() -> None:
    fm, body = split_frontmatter("---\nname: x\ndescription: dangling")
    assert "name: x" in fm
    assert body == ""


# ── parse_frontmatter ──────────────────────────────────────────────────────


def test_parse_frontmatter_yaml_block_scalar() -> None:
    fm, _ = split_frontmatter(FIXTURE_SKILL)
    data = parse_frontmatter(fm)
    assert data["name"] == "test-skill"
    assert "A test skill used to verify injection." in str(data["description"])


def test_parse_frontmatter_handrolled_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force the hand-rolled path by making yaml import fail.
    import builtins
    from collections.abc import Sequence

    real_import = builtins.__import__

    def fake_import(
        name: str,
        globals: dict[str, object] | None = None,
        locals: dict[str, object] | None = None,
        fromlist: Sequence[str] | None = (),
        level: int = 0,
    ) -> object:
        if name == "yaml":
            raise ImportError("forced")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    fm, _ = split_frontmatter(FIXTURE_SKILL)
    data = parse_frontmatter(fm)
    assert data["name"] == "test-skill"
    assert "A test skill used to verify injection." in str(data["description"])


def test_parse_frontmatter_empty() -> None:
    assert parse_frontmatter("") == {}


# ── build_skill_block / anchor ─────────────────────────────────────────────


def test_build_skill_block_shape_and_header() -> None:
    block = build_skill_block("test-skill", "A test skill used to verify injection.", "Body text.")
    assert block is not None
    assert block["name"] == "test-skill"
    assert block["body"].startswith("# test-skill — A test skill used to verify injection.")
    assert "Body text." in block["body"]
    # positive instruction present, imperative
    assert block["instruction"]
    assert "now" in block["instruction"].lower()


def test_build_skill_block_empty_body_is_none() -> None:
    assert build_skill_block("x", "desc", "   \n") is None


def test_skill_hints_differ_between_warm_and_cold() -> None:
    warm = build_skill_block("feature-planning", "Planning and execution.", "body")
    cold = build_skill_block("plan-authoring", "Plan authoring.", "body")
    assert warm is not None and cold is not None
    assert warm["instruction"] != cold["instruction"]
    assert "current task" in warm["instruction"]


def test_build_skill_anchor_is_short_and_names_skill() -> None:
    anchor = build_skill_anchor("feature-planning", "knowledge/skills/feature-planning/SKILL.md")
    assert "feature-planning" in anchor
    assert "knowledge/skills/feature-planning/SKILL.md" in anchor
    assert len(anchor.splitlines()) <= 2


# ── warm predicate (CT5 selection) ─────────────────────────────────────────


def test_warm_predicate_cold_default() -> None:
    assert plan_artifact_present() is False
    assert plan_artifact_present(read_paths=["src/fa/cli.py"], blackboard_keys=["other_key"]) is False


def test_warm_predicate_plan_artifact_in_reads() -> None:
    assert plan_artifact_present(read_paths=["knowledge/research/PLAN-scope-control-S10.md"]) is True
    assert plan_artifact_present(read_paths=["PLAN-foo.md"]) is True
    # backslash separators normalised
    assert plan_artifact_present(read_paths=["knowledge\\research\\PLAN-x.md"]) is True


def test_warm_predicate_plan_like_names_do_not_falsely_match() -> None:
    assert plan_artifact_present(read_paths=["PLANNING.md"]) is False
    assert plan_artifact_present(read_paths=["notes/PLAN.txt"]) is False


def test_warm_predicate_blackboard_keys() -> None:
    assert plan_artifact_present(blackboard_keys=["workflow_handoff"]) is True
    assert plan_artifact_present(blackboard_keys=["plan"]) is True


def test_selection_end_to_end_warm_and_cold() -> None:
    warm = plan_artifact_present(read_paths=["knowledge/research/PLAN-x.md"])
    cold = plan_artifact_present(read_paths=["src/fa/cli.py"])
    assert select_l2_skill(plan_artifact=warm) == "feature-planning"
    assert select_l2_skill(plan_artifact=cold) == "plan-authoring"


# ── read_skill_for_injection (fixtures + real files read-only) ─────────────


def test_read_skill_from_temp_fixture(tmp_path: Path) -> None:
    skill_dir = tmp_path / Path(*SKILLS_RELATIVE_DIR) / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / SKILL_FILE_NAME).write_text(FIXTURE_SKILL, encoding="utf-8")
    result = read_skill_for_injection("test-skill", default_skills_root(tmp_path))
    assert result.warning is None
    assert result.block is not None
    assert result.block["name"] == "test-skill"
    # frontmatter removed from the injected body
    assert "triggers:" not in result.block["body"]
    assert result.block["body"].startswith("# test-skill —")
    assert "# Body heading" in result.block["body"]


def test_read_skill_missing_returns_structured_warning(tmp_path: Path) -> None:
    result = read_skill_for_injection("does-not-exist", default_skills_root(tmp_path))
    assert result.block is None
    assert result.warning is not None
    assert "does-not-exist" in result.warning


def test_read_skill_empty_body_warns(tmp_path: Path) -> None:
    skill_dir = tmp_path / Path(*SKILLS_RELATIVE_DIR) / "empty-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / SKILL_FILE_NAME).write_text("---\nname: empty-skill\n---\n", encoding="utf-8")
    result = read_skill_for_injection("empty-skill", default_skills_root(tmp_path))
    assert result.block is None
    assert result.warning is not None
    assert "empty body" in result.warning


def test_default_skills_root_layout(tmp_path: Path) -> None:
    root = default_skills_root(tmp_path)
    assert root == tmp_path / "knowledge" / "skills"


@pytest.mark.parametrize("skill_name", ["feature-planning", "plan-authoring"])
def test_read_real_shipped_skills_read_only(skill_name: str) -> None:
    skills_root = REPO_ROOT / Path(*SKILLS_RELATIVE_DIR)
    result = read_skill_for_injection(skill_name, skills_root)
    assert result.warning is None, result.warning
    assert result.block is not None
    assert result.block["name"] == skill_name
    # frontmatter fully stripped from injected body
    assert not result.block["body"].startswith("---")
    assert "triggers:" not in result.block["body"]
    assert "globs:" not in result.block["body"]
    # body carries real skill content (non-trivial)
    assert len(result.block["body"]) > 500
