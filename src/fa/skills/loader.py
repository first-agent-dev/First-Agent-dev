"""Skill loader with globs and alwaysApply — Phase 1 Foundation.

Implements should_load_skill() per ADR-15 skill globs frontmatter alwaysApply false.
Uses yaml.safe_load (pyyaml already dep from providers/config.py) with graceful fallback.

Current files source = transaction.read_set + write_set + instant_grep(task, limit=10) precise 5-15 files,
not git ls-files all tracked (100s) which would cause token bloat.

Prior art: Cursor Rules globs + alwaysApply false.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any


def _parse_frontmatter_yaml(path: Path) -> dict[str, Any]:
    """Parse SKILL.md frontmatter between --- delimiters.

    Uses yaml.safe_load if available, fallback to hand-rolled for globs/triggers/alwaysApply.
    Returns dict with keys: name, globs, alwaysApply, triggers.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - file read best-effort
        print(f"WARNING: Failed to read skill file {path}: {exc}")
        return {}

    # Extract frontmatter between first two ---
    if not text.startswith("---"):
        return {}

    try:
        # Find second ---
        end = text.find("\n---", 3)
        if end == -1:
            return {}
        frontmatter_raw = text[3:end].strip()

        # Try yaml.safe_load
        try:
            import yaml  # type: ignore

            data = yaml.safe_load(frontmatter_raw)
            if isinstance(data, dict):
                return data
        except ImportError:
            print("WARNING: yaml not available, using hand-rolled frontmatter parser for skill loader")
        except Exception as exc:  # noqa: BLE001 - yaml parse may fail
            print(f"WARNING: yaml.safe_load failed for {path}: {exc}, fallback hand-rolled")

        # Fallback hand-rolled parser for simple cases
        return _handrolled_parse(frontmatter_raw)

    except Exception as exc:  # noqa: BLE001 - graceful
        print(f"WARNING: Frontmatter parse failed for {path}: {exc}")
        return {}


def _handrolled_parse(raw: str) -> dict[str, Any]:
    """Minimal parser for globs list, alwaysApply bool, triggers list."""
    result: dict[str, Any] = {}
    globs: list[str] = []
    triggers: list[str] = []
    current_list: str | None = None

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("globs:"):
            current_list = "globs"
            # Inline list? globs: ["a", "b"]
            if "[" in stripped and "]" in stripped:
                # Very simple inline parse
                inner = stripped.split("[", 1)[1].split("]", 1)[0]
                for item in inner.split(","):
                    item = item.strip().strip('"').strip("'")
                    if item:
                        globs.append(item)
                current_list = None
            continue
        if stripped.startswith("triggers:"):
            current_list = "triggers"
            continue
        if stripped.startswith("alwaysApply:"):
            val = stripped.split(":", 1)[1].strip().lower()
            result["alwaysApply"] = val in ("true", "yes", "on", "1")
            current_list = None
            continue
        if stripped.startswith("name:"):
            result["name"] = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            current_list = None
            continue
        if stripped.startswith("- ") and current_list:
            item = stripped[2:].strip().strip('"').strip("'")
            if current_list == "globs":
                globs.append(item)
            elif current_list == "triggers":
                triggers.append(item)
            continue
        # End of list
        if not line.startswith(" ") and not line.startswith("\t"):
            current_list = None

    if globs:
        result["globs"] = globs
    if triggers:
        result["triggers"] = triggers
    return result


def should_load_skill(
    skill_path: Path,
    current_files: list[str],
    task_text: str,
) -> bool:
    """Return True if skill should be loaded based on globs and triggers.

    - alwaysApply True -> always load
    - globs match any current_files (fnmatch + Path.match for ** support)
    - triggers match task_text via word boundaries
    """
    try:
        fm = _parse_frontmatter_yaml(skill_path)
    except Exception as exc:  # noqa: BLE001 - graceful
        print(f"WARNING: should_load_skill parse failed for {skill_path}: {exc}")
        return False

    if fm.get("alwaysApply") is True:
        return True

    globs = fm.get("globs", [])
    if globs:
        for pattern in globs:
            # Normalize pattern: remove leading spaces
            pat = pattern.strip()
            for f in current_files:
                try:
                    # fnmatch for simple patterns, Path.match for ** recursive
                    if fnmatch.fnmatch(f, pat):
                        return True
                    # Path.match handles ** in Python 3.10+
                    if Path(f).match(pat):
                        return True
                    # Also try matching basename if pattern has no /
                    if "/" not in pat:
                        if fnmatch.fnmatch(Path(f).name, pat):
                            return True
                except Exception:
                    continue

    triggers = fm.get("triggers", [])
    task_lower = task_text.lower()
    for trig in triggers:
        try:
            # Word boundary regex to avoid "pr" matching "prepare"
            pattern = r"\b" + re.escape(trig.lower()) + r"\b"
            if re.search(pattern, task_lower):
                return True
            # Also substring fallback for multi-word triggers
            if trig.lower() in task_lower:
                # For multi-word, substring is okay
                if len(trig.split()) > 1:
                    return True
        except Exception:
            continue

    return False


def get_current_files_for_skill_loader(
    session_state: Any = None,
    workspace_root: Path | None = None,
    task_text: str = "",
    limit: int = 10,
) -> list[str]:
    """Get precise current files for skill loader: transaction read/write + instant_grep.

    Production-grade: not git ls-files all tracked (100s files -> token bloat),
    but 5-15 precise files: what agent touched + relevant to task via instant_grep.
    """
    files: list[str] = []

    # 1. From transaction if available (most precise, what agent touched)
    try:
        if session_state is not None:
            txn = getattr(session_state, "transaction", None)
            if txn is not None:
                files.extend(list(txn.read_set))
                files.extend(list(txn.write_set))
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: Failed to get transaction files for skill loader: {exc}")

    # 2. From instant_grep for task relevance (structured websearch pattern)
    if task_text and workspace_root is not None:
        try:
            from fa.memory.fts_index import InstantGrepIndex

            db_path = workspace_root / ".fa" / "fts.db"
            if db_path.exists():
                index = InstantGrepIndex(db_path)
                # Query from task: extract keywords (simple: split task into words >3 chars)
                keywords = [w for w in re.findall(r"\w+", task_text) if len(w) > 3][:3]
                for kw in keywords[:2]:  # limit 2 keywords to avoid too many files
                    try:
                        paths = index.instant_grep(kw, limit=limit)
                        files.extend(paths)
                    except Exception:
                        continue
                try:
                    index.close()
                except Exception:
                    pass
        except Exception as exc:  # noqa: BLE001 - FTS may not exist yet
            print(f"WARNING: instant_grep for skill loader failed: {exc}")

    # Deduplicate, keep order, limit
    seen: set[str] = set()
    deduped: list[str] = []
    for f in files:
        if f not in seen:
            seen.add(f)
            deduped.append(f)
        if len(deduped) >= limit * 2:
            break

    return deduped[: limit * 2]


__all__ = ["get_current_files_for_skill_loader", "should_load_skill"]
