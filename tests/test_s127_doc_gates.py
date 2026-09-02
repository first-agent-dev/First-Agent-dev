"""S12.7 S8 (CT12 / GAP12-14) — doc gates: no stale mode teachers, cross-steering,
by-mode examples, discovery ladder.

T-no-stale-modes (C1 doc-gate): NO live ``src/fa`` string teaches the removed
``regions``/``counts`` modes. Sanctioned survivors are removal NOTICE lines
(P19 steering, leniency table, fold comments) — every such line must carry a
removal marker, so re-teaching a removed mode anywhere fails here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SRC_FA = Path(__file__).resolve().parents[1] / "src" / "fa"

_REMOVAL_MARKERS = re.compile(r"no longer exists|folded|removed|S12\.7|legacy", re.IGNORECASE)
_QUOTED_MODE = re.compile(r"['\"](?:regions|counts)['\"]")
_MODE_BULLET = re.compile(r"(?:^|\s)[*-]\s+(?:regions|counts)\b")


def _stale_teachers() -> list[str]:
    offenders: list[str] = []
    for py in sorted(SRC_FA.rglob("*.py")):
        for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), start=1):
            teaches = _QUOTED_MODE.search(line) or _MODE_BULLET.search(line)
            if teaches and not _REMOVAL_MARKERS.search(line):
                offenders.append(f"{py.relative_to(SRC_FA)}:{lineno}: {line.strip()[:100]}")
    return offenders


def test_s127_no_stale_mode_teachers_in_src() -> None:
    """GAP12/CT12: removed modes must not be taught anywhere in src/fa."""
    offenders = _stale_teachers()
    assert not offenders, "stale regions/counts teachers (add a removal marker or purge):\n" + "\n".join(offenders)


def test_s127_registry_live_surfaces_teach_current_modes(tmp_path: Path) -> None:
    """Live registry check: no ToolSpec description or schema enum offers
    regions/counts (belt to the src grep — this is what models actually see)."""
    from fa.inner_loop.tools import build_baseline_registry

    registry = build_baseline_registry(tmp_path)
    offenders: list[str] = []
    for spec in registry.specs():
        if _QUOTED_MODE.search(spec.description) and not _REMOVAL_MARKERS.search(spec.description):
            offenders.append(f"{spec.name}: description")
        enums = re.findall(r'"enum"\s*:\s*\[([^\]]*)\]', str(spec.input_schema))
        for enum_body in enums:
            if _QUOTED_MODE.search(enum_body):
                offenders.append(f"{spec.name}: enum [{enum_body}]")
    assert not offenders, f"live tool surfaces teach removed modes: {offenders}"


def test_s127_fs_search_description_examples_per_mode() -> None:
    """GAP14: one example line per mode (files/outline/matches)."""
    from fa.inner_loop.tools.fs_search import _TOOL_DESCRIPTION

    for mode in ("files", "outline", "matches"):
        assert f'"output_mode": "{mode}"' in _TOOL_DESCRIPTION, f"missing example for mode {mode}"


def test_s127_fs_search_description_ladder_and_heuristic() -> None:
    """CT12: discovery ladder files->outline(~500 lines)->matches->read_file."""
    from fa.inner_loop.tools.fs_search import _TOOL_DESCRIPTION

    assert "files (find candidates) -> outline" in _TOOL_DESCRIPTION
    assert "~500 lines" in _TOOL_DESCRIPTION, "outline-payoff heuristic from files rows' lines"
    assert "-> fs_read_file (read the exact lines)" in _TOOL_DESCRIPTION


def test_s127_cross_steering_both_ways(tmp_path: Path) -> None:
    """GAP13: fs_reach <-> fs_search outline companions, both descriptions."""
    from fa.inner_loop.tools.fs_reach import _DESCRIPTION
    from fa.inner_loop.tools.fs_search import _TOOL_DESCRIPTION

    assert "output_mode='outline'" in _DESCRIPTION, "fs_reach must steer structure queries to outline"
    assert "fs_reach" in _TOOL_DESCRIPTION, "fs_search must steer symbol-reference queries to fs_reach"


def test_s127_blackboard_query_mentions_current_modes() -> None:
    """GAP12: blackboard_query docstring names the current mode set only."""
    doc = (
        Path(__file__).resolve().parents[1] / "src" / "fa" / "inner_loop" / "tools" / "blackboard_query.py"
    ).read_text(encoding="utf-8")
    module_doc = doc.split('"""')[1]
    assert '"outline"' in module_doc and '"matches"' in module_doc
    assert '"regions"' not in module_doc


def test_s127_fs_search_module_docstring_current() -> None:
    """The module docstring (maintainer-facing) teaches the 3-mode set."""
    import fa.inner_loop.tools.fs_search as fss

    doc = fss.__doc__
    assert doc is not None
    assert "three" in doc.lower() and "outline" in doc
    assert not _MODE_BULLET.search(doc.replace("* outline", "").replace("* files", "").replace("* matches", "")), (
        "module docstring must not carry removed-mode bullets"
    )


@pytest.mark.parametrize(
    "path", ["src/fa/inner_loop/tools/fs_search.py", "src/fa/inner_loop/tools/blackboard_query.py"]
)
def test_s127_no_regions_teacher_in_key_descriptions(path: str) -> None:
    """Targeted pin: the two historically-stale files stay clean (GAP12)."""
    text = (Path(__file__).resolve().parents[1] / path).read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _QUOTED_MODE.search(line) and not _REMOVAL_MARKERS.search(line):
            pytest.fail(f"{path}:{lineno} teaches a removed mode: {line.strip()[:100]}")
