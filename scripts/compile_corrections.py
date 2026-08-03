#!/usr/bin/env python3
"""TRACE correction compiler — aggregates .fa/corrections.jsonl.

Reads the human-mediated correction log and produces a summary:
- Group by code, count occurrences
- Suggest candidate Level-1 rule specifications (for human review)
- NEVER auto-commits — output to stdout only (AGENTS.md rule #1).

Exit codes:
  0 — summary produced (or no corrections found)
  1 — corrections.jsonl is missing or unreadable

Cross-reference: knowledge/trace/gotchas.md for guardrail correction
patterns; .fa/corrections.jsonl is separate (TCB-protected, not replacing
knowledge/trace/).

Stdlib-only (ADR-11-I1).
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# UTF-8 console: this script prints non-ASCII (checkmarks / box drawing) and
# crashed with UnicodeEncodeError on a Windows host whose console was cp1251 —
# while REPORTING SUCCESS. See scripts/_console.py for the full rationale.
if __package__ in (None, ""):  # invoked as a file, not as scripts.<name>
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._console import force_utf8_stdio

force_utf8_stdio()


def _find_corrections_path() -> Path:
    """Resolve corrections.jsonl relative to repo root."""
    # Walk up from this script's location to find .fa/corrections.jsonl
    here = Path(__file__).resolve().parent
    for parent in [here, *here.parents]:
        candidate = parent / ".fa" / "corrections.jsonl"
        if candidate.exists():
            return candidate
    return Path(".fa") / "corrections.jsonl"  # fallback


def load_corrections(path: Path) -> list[dict[str, Any]]:
    """Parse corrections.jsonl, skipping comment lines."""
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            entry = json.loads(stripped)
            if isinstance(entry, dict):
                entries.append(entry)
        except json.JSONDecodeError as exc:
            print(f"WARN: line {line_no}: invalid JSON: {exc}", file=sys.stderr)
    return entries


def compile_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate correction entries by code.

    Returns dict with:
      - total: total number of entries
      - by_code: dict mapping code → {count, remediations, paths}
      - suggested_rules: list of candidate rule specs (for human review)
    """
    if not entries:
        return {"total": 0, "by_code": {}, "suggested_rules": []}

    by_code: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "remediations": [], "paths": []})

    for entry in entries:
        code = str(entry.get("code", "UNKNOWN"))
        by_code[code]["count"] += 1
        remediation = entry.get("remediation", "")
        if remediation:
            by_code[code]["remediations"].append(str(remediation))
        path = entry.get("path", "")
        if path:
            by_code[code]["paths"].append(str(path))

    # Deduplicate
    for code_data in by_code.values():
        code_data["remediations"] = sorted(set(code_data["remediations"]))
        code_data["paths"] = sorted(set(code_data["paths"]))

    # Suggest candidate rules for codes that appear ≥2 times
    suggested_rules: list[dict[str, Any]] = []
    for code, data in sorted(by_code.items()):
        if data["count"] >= 2:
            suggested_rules.append(
                {
                    "code": code,
                    "occurrences": data["count"],
                    "candidate_rule": f"AUTO-SUGGEST: Consider creating a Level-1 rule for {code} "
                    f"(seen {data['count']}x). Remediation pattern: "
                    f"{data['remediations'][0] if data['remediations'] else 'none'}",
                }
            )

    return {
        "total": len(entries),
        "by_code": dict(by_code),
        "suggested_rules": suggested_rules,
    }


def render_summary(summary: dict[str, Any]) -> str:
    """Render summary as human-readable text."""
    lines: list[str] = []

    total = summary["total"]
    by_code = summary["by_code"]
    suggested = summary["suggested_rules"]

    if total == 0:
        return "No corrections logged. .fa/corrections.jsonl is empty or missing."

    lines.append(f"TRACE Correction Summary: {total} entries, {len(by_code)} unique codes")
    lines.append("")

    for code, data in sorted(by_code.items()):
        lines.append(f"  {code}: {data['count']}x")
        if data["remediations"]:
            lines.append(f"    remediations: {', '.join(data['remediations'][:3])}")
        if data["paths"]:
            lines.append(f"    paths: {', '.join(data['paths'][:5])}")

    if suggested:
        lines.append("")
        lines.append("Suggested rule candidates (≥2 occurrences, for human review):")
        for rule in suggested:
            lines.append(f"  {rule['candidate_rule']}")

    return "\n".join(lines)


def main() -> int:
    path = _find_corrections_path()
    entries = load_corrections(path)
    summary = compile_summary(entries)
    print(render_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
