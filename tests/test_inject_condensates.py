"""PLAN S1/S2 — INJECT.md condensates + the loader's file_name parameter.

root=skill-reader class=C0/C0p claim=G1,G2 path=T1,T2,T2b
oracle=exact SkillInjectionResult fields; parity of condensate labels against
the parent SKILL.md; the amended skill-writing invariant.
producer-kill-check=reverting _inject.py:read_skill_for_injection to the
hardcoded SKILL_FILE_NAME makes test_reads_named_sibling_file fail.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.skills._inject import (
    SKILL_FILE_NAME,
    SKILLS_RELATIVE_DIR,
    _ARGUMENT_HINT,
    default_skills_root,
    read_skill_for_injection,
    split_frontmatter,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / Path(*SKILLS_RELATIVE_DIR)
INJECT_FILE_NAME = "INJECT.md"

#: (skill directory, expected condensate frontmatter name)
CONDENSATES = [
    ("feature-planning", "feature-planning-inject"),
    ("tests-writing", "tests-writing-inject"),
]


# ── T1 — the loader parameter (C0) ─────────────────────────────────────────


class TestFileNameParameter:
    def test_default_is_unchanged(self, tmp_path: Path) -> None:
        """Back-compat: omitting file_name must still read SKILL.md."""
        skill_dir = tmp_path / Path(*SKILLS_RELATIVE_DIR) / "demo"
        skill_dir.mkdir(parents=True)
        (skill_dir / SKILL_FILE_NAME).write_text(
            "---\nname: demo\ndescription: d\n---\n\nBody.\n", encoding="utf-8"
        )
        result = read_skill_for_injection("demo", default_skills_root(tmp_path))
        assert result.warning is None
        assert result.block is not None
        assert "Body." in result.block["body"]

    def test_reads_named_sibling_file(self, tmp_path: Path) -> None:
        """PRODUCER KILL-CHECK for S2.

        Reverting :224 to the SKILL_FILE_NAME constant makes this fail: the
        sibling would not be found and block would be None.
        """
        skill_dir = tmp_path / Path(*SKILLS_RELATIVE_DIR) / "demo"
        skill_dir.mkdir(parents=True)
        (skill_dir / SKILL_FILE_NAME).write_text(
            "---\nname: demo\ndescription: full\n---\n\nFULL BODY\n", encoding="utf-8"
        )
        (skill_dir / INJECT_FILE_NAME).write_text(
            "---\nname: demo-inject\ndescription: short\n---\n\nSHORT BODY\n", encoding="utf-8"
        )
        result = read_skill_for_injection(
            "demo", default_skills_root(tmp_path), file_name=INJECT_FILE_NAME
        )
        assert result.warning is None
        assert result.block is not None
        assert "SHORT BODY" in result.block["body"]
        assert "FULL BODY" not in result.block["body"], "read the wrong file"
        assert result.block["name"] == "demo-inject"

    def test_missing_named_file_warns_with_that_name(self, tmp_path: Path) -> None:
        """A typo must be diagnosable from the warning, not silently skipped."""
        skill_dir = tmp_path / Path(*SKILLS_RELATIVE_DIR) / "demo"
        skill_dir.mkdir(parents=True)
        (skill_dir / SKILL_FILE_NAME).write_text("---\nname: demo\n---\n\nBody\n", encoding="utf-8")
        result = read_skill_for_injection(
            "demo", default_skills_root(tmp_path), file_name="TYPO.md"
        )
        assert result.block is None
        assert result.warning is not None
        assert "TYPO.md" in result.warning

    def test_file_name_is_keyword_only(self, tmp_path: Path) -> None:
        """Positional passing must be impossible: two path components in a
        row are exactly the pair a caller could transpose unnoticed."""
        with pytest.raises(TypeError):
            read_skill_for_injection("demo", default_skills_root(tmp_path), INJECT_FILE_NAME)  # type: ignore[misc]


# ── T2 — condensate shape + parity (C0p) ───────────────────────────────────


class TestCondensatesExist:
    @pytest.mark.parametrize(("skill", "expected_name"), CONDENSATES)
    def test_condensate_is_readable_and_named(self, skill: str, expected_name: str) -> None:
        result = read_skill_for_injection(skill, SKILLS_ROOT, file_name=INJECT_FILE_NAME)
        assert result.warning is None, result.warning
        assert result.block is not None
        assert result.block["name"] == expected_name

    @pytest.mark.parametrize(("skill", "expected_name"), CONDENSATES)
    def test_frontmatter_present_and_header_not_degenerate(
        self, skill: str, expected_name: str
    ) -> None:
        """D3: without frontmatter the header renders '# name — name'.

        The description must be a real sentence, not an echo of the name.
        """
        text = (SKILLS_ROOT / skill / INJECT_FILE_NAME).read_text(encoding="utf-8")
        frontmatter, body = split_frontmatter(text)
        assert frontmatter, "condensate must carry frontmatter"
        assert body.strip(), "condensate body must be non-empty"

        result = read_skill_for_injection(skill, SKILLS_ROOT, file_name=INJECT_FILE_NAME)
        assert result.block is not None
        description = result.block["description"]
        assert description and description != expected_name
        assert result.block["body"].startswith(f"# {expected_name} — {description}")

    @pytest.mark.parametrize(("skill", "expected_name"), CONDENSATES)
    def test_has_a_dedicated_argument_hint(self, skill: str, expected_name: str) -> None:
        """Without an entry the condensate silently gets the generic hint."""
        assert expected_name in _ARGUMENT_HINT
        result = read_skill_for_injection(skill, SKILLS_ROOT, file_name=INJECT_FILE_NAME)
        assert result.block is not None
        assert result.block["instruction"] == _ARGUMENT_HINT[expected_name]

    @pytest.mark.parametrize(("skill", "_name"), CONDENSATES)
    def test_no_triggers_or_globs(self, skill: str, _name: str) -> None:
        """A condensate is a payload, not a separately selectable skill."""
        frontmatter, _ = split_frontmatter(
            (SKILLS_ROOT / skill / INJECT_FILE_NAME).read_text(encoding="utf-8")
        )
        assert "triggers:" not in frontmatter
        assert "globs:" not in frontmatter

    @pytest.mark.parametrize(("skill", "_name"), CONDENSATES)
    def test_body_stays_small(self, skill: str, _name: str) -> None:
        """The whole point is cost: a condensate that grows is the wrong subset."""
        _, body = split_frontmatter(
            (SKILLS_ROOT / skill / INJECT_FILE_NAME).read_text(encoding="utf-8")
        )
        assert len(body.splitlines()) <= 60

    @pytest.mark.parametrize(("skill", "_name"), CONDENSATES)
    def test_condensate_is_much_smaller_than_parent(self, skill: str, _name: str) -> None:
        parent = (SKILLS_ROOT / skill / SKILL_FILE_NAME).read_text(encoding="utf-8")
        condensate = (SKILLS_ROOT / skill / INJECT_FILE_NAME).read_text(encoding="utf-8")
        assert len(condensate) * 4 < len(parent), "condensate is not buying enough"


class TestParityWithParentSkill:
    """CT2: the condensate must never state a rule its SKILL.md does not."""

    #: Field labels the ceremony depends on. Each must appear in the parent.
    FEATURE_PLANNING_LABELS = [
        "Degree of freedom closed",
        "Deterministic mechanism",
        "Production best practice",
        "Failure behavior",
        "Tests-writing class",
        "Producer kill-check target",
        "Concrete intent",
    ]
    TESTS_WRITING_LABELS = ["C0", "C0p", "C1", "C2", "C3", "C4"]

    @pytest.mark.parametrize("label", FEATURE_PLANNING_LABELS)
    def test_feature_planning_labels_exist_in_parent(self, label: str) -> None:
        parent = (SKILLS_ROOT / "feature-planning" / SKILL_FILE_NAME).read_text(encoding="utf-8")
        condensate = (SKILLS_ROOT / "feature-planning" / INJECT_FILE_NAME).read_text(
            encoding="utf-8"
        )
        assert label in condensate, "condensate dropped a required field"
        assert label.lower() in parent.lower(), f"condensate invented {label!r}"

    @pytest.mark.parametrize("label", TESTS_WRITING_LABELS)
    def test_tests_writing_classes_exist_in_parent(self, label: str) -> None:
        parent = (SKILLS_ROOT / "tests-writing" / SKILL_FILE_NAME).read_text(encoding="utf-8")
        condensate = (SKILLS_ROOT / "tests-writing" / INJECT_FILE_NAME).read_text(encoding="utf-8")
        assert label in condensate
        assert label in parent

    def test_condensates_name_their_source_section(self) -> None:
        """Traceability: a reader must be able to find the parent text."""
        for skill, _ in CONDENSATES:
            condensate = (SKILLS_ROOT / skill / INJECT_FILE_NAME).read_text(encoding="utf-8")
            assert "SKILL.md" in condensate


# ── T2b — the amended invariant (C0) ───────────────────────────────────────


def test_skill_writing_invariant_permits_inject_sibling() -> None:
    """GAP11: the condensates violate the old single-file rule.

    The rule had to be amended deliberately, not ignored.
    """
    text = (SKILLS_ROOT / "skill-writing" / SKILL_FILE_NAME).read_text(encoding="utf-8")
    assert "optional derived `INJECT.md`" in text
    assert "### Optional `INJECT.md` condensate" in text


def test_skill_writing_documents_the_frontmatter_requirement() -> None:
    """The D3 trap (no frontmatter -> degenerate header) must be written down."""
    text = (SKILLS_ROOT / "skill-writing" / SKILL_FILE_NAME).read_text(encoding="utf-8")
    section = text.split("### Optional `INJECT.md` condensate", 1)[1]
    assert "Frontmatter is **required**" in section
    assert "triggers:" in section
