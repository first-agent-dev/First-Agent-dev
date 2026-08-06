"""S13.10 — tool-name canonical map tests (S13.10.0, CT5).

Plan: ``worklogs/implementation-plans/PLAN-cli-trace-S13.10-tool-name-sanitization.md``
§S13.10.0.

**Why.** The canonical map (`fa/inner_loop/tool_names.py`) is the single source of
truth for wire tool names after the dot→underscore rename. These tests pin it:
every new name matches the provider-standard pattern `^[a-zA-Z0-9_-]{1,64}$`
(CT1), and the map is complete against the actual ToolSpec definitions in
`tools/*.py` (CT5 — a dotted name reintroduced, or a canonical name missing, fails).

**Legacy-ledger pruning (2026-08-06).** The former `LEGACY_TO_NEW` migration ledger
and `legacy_to_new` helper were removed (completed one-time rename artifact; not
used by production code). The two tests that exercised them
(`test_all_legacy_names_are_dotted`, `test_legacy_to_new_identity_for_non_legacy`)
were deleted with the ledger. The remaining tests enforce the real invariants.

**Tests labelled per tests-writing skill:** C0p (pure map properties) + C1
(composition against the real ToolSpec definitions).

**Kill-checks:**
- a tool name missing from `TOOL_NAMES` → `test_map_covers_all_tool_spec_names` fails;
- a dotted name reintroduced in `tools/*.py` → the coverage test fails.
"""

from __future__ import annotations

import re
from pathlib import Path

from fa.inner_loop.tool_names import TOOL_NAMES, is_valid_wire_name

_SRC = Path(__file__).parent.parent / "src" / "fa" / "inner_loop" / "tools"

# The canonical ToolSpec.name= set, scraped from the tool modules.
_TOOLSPEC_NAME_RE = re.compile(r'name="((?:fs|pr)_[a-z_]+)"')


def _scrape_tool_spec_names() -> set[str]:
    """Collect every `name="fs_x"` / `name="pr_x"` literal in tools/*.py (new wire names)."""
    found: set[str] = set()
    for path in _SRC.glob("*.py"):
        for match in _TOOLSPEC_NAME_RE.finditer(path.read_text(encoding="utf-8")):
            found.add(match.group(1))
    return found


# --- C0p: map properties -----------------------------------------------------


def test_all_new_names_match_wire_pattern() -> None:
    """C0p (CT1) — every canonical new name matches `^[a-zA-Z0-9_-]{1,64}$`."""
    for name in TOOL_NAMES:
        assert is_valid_wire_name(name), f"{name!r} violates the wire-name pattern"


def test_no_new_name_contains_a_dot() -> None:
    """C0p — no canonical name has a dot (the whole point of the rename)."""
    for name in TOOL_NAMES:
        assert "." not in name, f"{name!r} still contains a dot"


# --- C1: composition against the real ToolSpec defs (CT5) ---------------------


def test_no_dotted_tool_spec_names_remain() -> None:
    """C1 (CT1) — no dotted `name="fs.x"` literal remains in any tool module.

    This is the S13.10.1 wire-rename DoD, pinned: a dotted name reintroduced in a
    tool module fails here.
    """
    dotted = 0
    for path in _SRC.glob("*.py"):
        dotted += len(re.findall(r'name="(?:fs|pr)\.[a-z_]+"', path.read_text(encoding="utf-8")))
    assert dotted == 0, f"{dotted} dotted ToolSpec name(s) remain in tools/"


def test_map_covers_all_tool_spec_names() -> None:
    """C1 (CT5) — every ToolSpec.name in tools/*.py is a canonical (underscore) name.

    Kill-check: a non-canonical ToolSpec name (not in TOOL_NAMES) fails here —
    proving the map is the complete source of truth and no tool name drifted.
    """
    names = _scrape_tool_spec_names()
    assert names, "expected at least one underscore ToolSpec name (the scrape works)"
    unknown = names - set(TOOL_NAMES)
    assert not unknown, f"ToolSpec names not in canonical TOOL_NAMES: {unknown}"
