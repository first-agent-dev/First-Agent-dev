"""L2 skill-body injection reader (S10.3 / CT5).

The planner skills (``plan-authoring`` cold, ``feature-planning`` warm) are
injected into the chat model's context deterministically by the harness —
the model never self-serves skills (SSOT decision: no reliance on the
glob loader's auto-selection). This module is the *reader* half of that
injection: it locates a skill's ``SKILL.md`` under the workspace
``knowledge/skills/`` tree, strips the YAML frontmatter, and produces

  * a **full-body block** (dict, JSON-serializable — the composer renders
    ``skills_conditional`` entries with ``json.dumps``) sent on the entry
    turn only; and
  * a short **anchor** string (name + path) for subsequent L2 turns, so the
    recurring cost is a line or two rather than the whole skill.

Pure + stdlib/PyYAML only; no session state, no loop imports. Every failure
(missing file, unparseable frontmatter, empty body) returns a structured
warning instead of raising — a turn-boundary advisory must never crash the
run, and the degraded path is observable.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "PLAN_ARTIFACT_PATTERN",
    "SKILLS_RELATIVE_DIR",
    "SKILL_FILE_NAME",
    "SkillInjectionResult",
    "build_skill_anchor",
    "build_skill_block",
    "default_skills_root",
    "parse_frontmatter",
    "plan_artifact_present",
    "read_skill_for_injection",
    "split_frontmatter",
]

SKILL_FILE_NAME = "SKILL.md"
SKILLS_RELATIVE_DIR = ("knowledge", "skills")

#: Plan artifacts that mark a run as "warm": any PLAN-*.md path observed in
#: the read set (the canonical location is knowledge/research/, but a plan
#: written anywhere in the workspace counts).
PLAN_ARTIFACT_PATTERN = re.compile(r"(^|/)PLAN-[^/]*\.md$", re.IGNORECASE)

#: Blackboard entries that prove a plan/handoff already exists.
_PLAN_BLACKBOARD_KEYS: frozenset[str] = frozenset({"workflow_handoff", "plan", "plan_artifact"})

#: One-line, positive instruction appended under the header. Kept short and
#: imperative (SSOT: positive checklists, no negative instructions); the
#: feature-planning skill gets an explicit "apply to the current task" hint
#: because it is the warm, execution-oriented variant.
_ARGUMENT_HINT: dict[str, str] = {
    "feature-planning": "Apply this skill directly to the current task in this workspace now.",
    "plan-authoring": "Follow this skill to author the implementation plan for the current task now.",
}


@dataclass(frozen=True)
class SkillInjectionResult:
    """Outcome of one skill read. ``block`` is None on any failure;
    ``warning`` carries the structured reason (never silent)."""

    block: dict[str, str] | None
    warning: str | None = None


def default_skills_root(workspace: Path) -> Path:
    """Resolve ``<workspace>/knowledge/skills`` the same way pinned content
    resolves its ``knowledge/`` paths (cli.py workspace joins)."""
    return workspace.joinpath(*SKILLS_RELATIVE_DIR)


def split_frontmatter(text: str) -> tuple[str, str]:
    """Split ``SKILL.md`` text into ``(frontmatter_raw, body)``.

    Frontmatter is delimited by the first ``---`` line and the next
    ``---`` line. A file without frontmatter returns ``("", text)``.
    The returned body never contains YAML keys (kill-check: frontmatter
    not stripped -> YAML leaks into the model context).
    """
    if not text.startswith("---"):
        return "", text.strip("\n")
    # First delimiter may be "---" alone or "---\r\n".
    first_end = text.find("\n")
    if first_end == -1:
        return "", ""
    second = text.find("\n---", first_end + 1)
    if second == -1:
        # Unterminated frontmatter: treat the whole thing as unusable.
        return text[first_end + 1 :], ""
    # End of the closing delimiter line.
    line_end = text.find("\n", second + 1)
    if line_end == -1:
        return text[first_end + 1 : second], ""
    return text[first_end + 1 : second].strip("\n"), text[line_end + 1 :].strip("\n")


def parse_frontmatter(frontmatter_raw: str) -> dict[str, Any]:
    """Parse frontmatter YAML into a dict (name/description/…).

    Uses PyYAML when available; falls back to a minimal hand-rolled parse
    for ``name:`` and a ``description:`` block/inline scalar so a missing
    yaml install never blocks injection. Never raises.
    """
    if not frontmatter_raw.strip():
        return {}
    try:
        import yaml

        data = yaml.safe_load(frontmatter_raw)
        if isinstance(data, dict):
            return {str(k): v for k, v in data.items()}
    except ImportError:
        logger.warning("yaml not available; using hand-rolled frontmatter parse for skill injection")
    except Exception as exc:  # noqa: BLE001 - malformed YAML degrades to hand-rolled
        logger.warning("yaml.safe_load failed during skill injection (%s); using hand-rolled parse", exc)

    # Minimal fallback: name: one-liner + description (inline or | block).
    result: dict[str, Any] = {}
    lines = frontmatter_raw.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("name:"):
            result["name"] = stripped.split(":", 1)[1].strip().strip("'\"")
        elif stripped.startswith("description:"):
            rest = stripped.split(":", 1)[1].strip()
            if rest in {"|", "|-", ">", ">-"}:
                block: list[str] = []
                i += 1
                while i < len(lines) and (lines[i].startswith("  ") or not lines[i].strip()):
                    block.append(lines[i].strip())
                    i += 1
                result["description"] = " ".join(part for part in block if part)
                continue
            result["description"] = rest.strip("'\"")
        i += 1
    return result


def _one_line_description(description: Any) -> str:
    """Collapse a (possibly block-scalar, multi-line) description to its
    first meaningful sentence line for the one-line header."""
    text = str(description or "").strip()
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def build_skill_block(name: str, description: str, body: str) -> dict[str, str] | None:
    """Assemble the composer-ready skill block.

    Shape (JSON-serializable; rendered inside ``ConditionalSkills:``):
    ``{"name", "description", "instruction", "body"}`` where ``body``
    starts with a one-line ``# <name> — <description>`` header plus the
    positive argument hint, then the full SKILL.md body (frontmatter
    already removed). Returns None when there is no body to inject.
    """
    body = body.strip()
    if not body:
        return None
    header_desc = _one_line_description(description) or name
    header = f"# {name} — {header_desc}"
    hint = _ARGUMENT_HINT.get(name, "Apply this skill to the current task now.")
    return {
        "name": name,
        "description": header_desc,
        "instruction": hint,
        "body": f"{header}\n{hint}\n\n{body}",
    }


def build_skill_anchor(name: str, skill_path: Path | str) -> str:
    """1-2 line anchor for subsequent L2 turns (cheap reminder; the full
    body was delivered on the entry turn and persists in history)."""
    return f"Skill {name} remains active (full instructions given earlier). Reference: {skill_path}"


def plan_artifact_present(
    read_paths: Iterable[str] | None = None,
    blackboard_keys: Iterable[str] | None = None,
) -> bool:
    """Warm predicate (CT5 selection).

    True iff the run already has a plan artifact in evidence:
      * any observed read path matching ``PLAN-*.md`` (canonically under
        ``knowledge/research/``, but any location counts), or
      * a plan/handoff blackboard entry.

    Pure and deterministic; the caller passes concrete signals so this
    never touches session state.
    """
    for path in read_paths or ():
        normalized = str(path).replace("\\", "/")
        if PLAN_ARTIFACT_PATTERN.search(normalized):
            return True
    for key in blackboard_keys or ():
        if str(key) in _PLAN_BLACKBOARD_KEYS:
            return True
    return False


def read_skill_for_injection(skill_name: str, skills_root: Path) -> SkillInjectionResult:
    """Read ``<skills_root>/<skill_name>/SKILL.md`` and build the block.

    Degraded paths return a result with ``block=None`` and a structured
    warning: unknown skill dir, unreadable file, missing/empty body, or a
    frontmatter lacking a name (name falls back to the directory name).
    """
    skill_dir = skills_root / skill_name
    skill_path = skill_dir / SKILL_FILE_NAME
    if not skill_path.is_file():
        return SkillInjectionResult(
            block=None,
            warning=f"skill {skill_name!r} not found at {skill_path} (L2 injection skipped)",
        )
    try:
        text = skill_path.read_text(encoding="utf-8")
    except OSError as exc:
        return SkillInjectionResult(
            block=None,
            warning=f"could not read {skill_path}: {exc} (L2 injection skipped)",
        )

    frontmatter_raw, body = split_frontmatter(text)
    fm = parse_frontmatter(frontmatter_raw)
    name = str(fm.get("name") or skill_name).strip() or skill_name
    description = str(fm.get("description") or "")
    block = build_skill_block(name, description, body)
    if block is None:
        return SkillInjectionResult(
            block=None,
            warning=f"skill {skill_name!r} at {skill_path} has an empty body (L2 injection skipped)",
        )
    return SkillInjectionResult(block=block)
