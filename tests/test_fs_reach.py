"""S16 (CT-6): fs_reach — C1 tests against the real tool builder.

Paths covered (plan P-matrix):
  P14  lazy structural build on first call (thread-safe)        (T26/T27 implicit)
  P15  in-file symbol resolution + BFS distances                (T26, T27)
  P16  non-Python workspace → structured unavailable            (T28)
  P17  § anchor resolution                                      (T28)
  T29  registry/corpus wiring: presence in 4 profiles, absence from eval

Kill-check targets (producers, not consumers):
  - BFS depth expansion in StructuralIndex.reachable → T26 fails
  - DROP TABLE calls → T27 fails
  - honest unresolved classification → T27b fails
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop.hooks import HookRegistry
from fa.inner_loop.tools.fs_reach import build_fs_reach_tool

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


CHAIN = """\
def d() -> str:
    return "d"


def c() -> str:
    return d()


def b() -> str:
    return c()


def a() -> str:
    return b()
"""


@pytest.fixture
def reach_tool(tmp_path: Path) -> Any:
    _write(tmp_path / "chain.py", CHAIN)
    return build_fs_reach_tool(tmp_path)


def _invoke(spec: Any, params: dict[str, Any]) -> Any:
    return spec.handler(params)


# ── T26: down-direction BFS with depth cut ──────────────────────────────────


def test_fs_reach_down_depth_cut(reach_tool: Any) -> None:
    result = _invoke(reach_tool, {"symbol": "a", "direction": "down", "depth": 2})
    assert result.error is None, result.error
    payload = result.result
    assert payload["status"] == "ok"
    assert payload["resolved_to"]["qualname"] == "a"
    callees = [(r["qualname"], r["distance"]) for r in payload["callees"]]
    assert callees == [("b", 1), ("c", 2)]  # d is distance 3 — cut
    assert payload["truncated"] is False
    assert payload["unresolved"] == 0


def test_fs_reach_down_full_chain(reach_tool: Any) -> None:
    result = _invoke(reach_tool, {"symbol": "a", "direction": "down", "depth": 5})
    payload = result.result
    assert [(r["qualname"], r["distance"]) for r in payload["callees"]] == [
        ("b", 1),
        ("c", 2),
        ("d", 3),
    ]


# ── T27: up-direction BFS ───────────────────────────────────────────────────


def test_fs_reach_up_callers(reach_tool: Any) -> None:
    result = _invoke(reach_tool, {"symbol": "c", "direction": "up", "depth": 3})
    assert result.error is None, result.error
    payload = result.result
    assert payload["resolved_to"]["qualname"] == "c"
    assert [(r["qualname"], r["distance"]) for r in payload["callers"]] == [
        ("b", 1),
        ("a", 2),
    ]
    # direction=up must not run the down BFS (unresolved stays 0, callees empty)
    assert payload["callees"] == []
    assert payload["unresolved"] == 0


# ── T27b: unresolved honesty ────────────────────────────────────────────────


def test_fs_reach_unresolved_honesty(tmp_path: Path) -> None:
    _write(tmp_path / "m.py", "import os\n\n\ndef f() -> str:\n    return os.path.join('a', 'b')\n")
    spec = build_fs_reach_tool(tmp_path)
    result = _invoke(spec, {"symbol": "f", "direction": "down", "depth": 2})
    assert result.error is None, result.error
    payload = result.result
    assert payload["resolved_to"]["qualname"] == "f"
    assert payload["callees"] == []  # unresolved values are never symbol rows
    assert payload["unresolved"] == 1


# ── T28: not-found, non-Python, anchor, param validation ────────────────────


def test_fs_reach_not_found_lists_candidates(reach_tool: Any) -> None:
    result = _invoke(reach_tool, {"symbol": "nonexistent"})
    assert result.error is None
    payload = result.result
    assert payload["resolved_to"] is None
    assert payload["candidates"] == []
    assert payload["callers"] == []
    assert payload["callees"] == []


def test_fs_reach_non_python_unavailable(tmp_path: Path) -> None:
    _write(tmp_path / "app.js", "console.log(1)\n")
    _write(tmp_path / "README.md", "# hi\n")
    spec = build_fs_reach_tool(tmp_path)
    result = _invoke(spec, {"symbol": "x"})
    assert result.error is None
    payload = result.result
    assert payload["status"] == "unavailable"
    assert payload["resolved_to"] is None
    assert "Python-only" in payload["reason"]
    assert set(payload["detected_languages"]) == {".js", ".md"}


def test_fs_reach_anchor_resolves(tmp_path: Path) -> None:
    _write(tmp_path / "m.py", "# §I-42: the answer\n\ndef f() -> int:\n    return 42\n")
    spec = build_fs_reach_tool(tmp_path)
    result = _invoke(spec, {"symbol": "§I-42", "direction": "down", "depth": 1})
    assert result.error is None, result.error
    payload = result.result
    assert payload["resolved_to"] is not None
    assert payload["resolved_to"]["qualname"] == "§I-42"
    assert payload["resolved_to"]["kind"] == "doc_anchor"
    assert payload["resolved_to"]["line"] == 1


def test_fs_reach_invalid_params(reach_tool: Any) -> None:
    r1 = _invoke(reach_tool, {"symbol": "   "})
    assert r1.error is not None and r1.error.code == "invalid_params"
    r2 = _invoke(reach_tool, {"symbol": "a", "direction": "sideways"})
    assert r2.error is not None and r2.error.code == "invalid_params"
    r3 = _invoke(reach_tool, {"symbol": "a", "depth": "deep"})
    assert r3.error is not None and r3.error.code == "invalid_params"
    r4 = _invoke(reach_tool, {"symbol": "a", "kind": "class"})
    assert r4.error is not None and r4.error.code == "invalid_params"
    # clamps are valid (not errors): depth 99 → 5, limit 0 → 1
    r5 = _invoke(reach_tool, {"symbol": "a", "direction": "down", "depth": 99, "limit": 0})
    assert r5.error is None
    assert r5.result["resolved_to"]["qualname"] == "a"


# ── T29: registry wiring (presence in 4 profiles, absence from eval) ────────


def test_fs_reach_registration_surface(tmp_path: Path) -> None:
    from fa.inner_loop.profiles import build_registry_for_role

    _write(tmp_path / "m.py", "def f():\n    return 1\n")
    for role in ("researcher", "code-reviewer", "implementer", "planner"):
        registry = build_registry_for_role(role, tmp_path)
        names = registry.names()
        assert "fs_reach" in names, f"{role}: {names}"
    eval_names = build_registry_for_role("verifier", tmp_path).names()
    assert "fs_reach" not in eval_names  # verifier stays bash-only (R-3)


def test_fs_reach_tool_names_composition() -> None:
    from fa.inner_loop.tool_names import TOOL_NAMES

    assert "fs_reach" in TOOL_NAMES


# ── S22 LIVE-PATH: in-file oracle against the real FA source ────────────────


def _real_repo_available() -> bool:
    """True when the git-tracked FA source tree is the repo root.

    The live oracle's contract is "runs against actual FA source"; under
    mutation staging (mutants/ sits inside the repo but its files are
    untracked, so the walker's git fast-path yields nothing) the oracle is
    not exercisable — skip honestly instead of failing environmentally.
    """
    import subprocess

    root = Path(__file__).resolve().parents[1]
    try:
        proc = subprocess.run(
            ["git", "ls-files", "src/fa/cli.py"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0 and bool(proc.stdout.strip())


@pytest.mark.skipif(
    not _real_repo_available(),
    reason="live oracle requires the git-tracked FA source tree (skipped under mutation staging)",
)
def test_reach_live_on_fa_repo() -> None:
    """fs_reach over the actual FA repo: `_register_search_result_paths`
    (unique to fs_search.py) resolves with caller `_handle` at distance 1
    (IN-FILE oracle — v1 resolution is in-file only, review D-S16-2).

    Qualnames are scope-chain only (S18 semantics): the module path is NOT
    baked into the qualname — the ``path`` column carries file identity and
    the suffix lookup + total order disambiguates (Q-S16-2 default; the
    module-qualified form in the §2.2 schema example was aspirational).
    """
    from fa.inner_loop import SessionState, ToolCall, run_session
    from fa.inner_loop.registry import ToolRegistry
    from fa.inner_loop.runtime_limits import RuntimeLimits

    repo_root = Path(__file__).resolve().parents[1]
    spec = build_fs_reach_tool(repo_root)
    registry = ToolRegistry()
    registry.register(spec)
    state = SessionState(workspace_root=repo_root, run_id="t-live-reach")

    result = run_session(
        (
            ToolCall(
                name="fs_reach",
                params={"symbol": "_register_search_result_paths", "direction": "up", "depth": 2},
                call_id="tc-1",
            ),
        ),
        registry=registry,
        hooks=HookRegistry(),
        state=state,
        role="coder",
        limits=RuntimeLimits(max_iterations=3),
    )
    assert len(result) == 1
    assert result[0].error is None, result[0].error
    payload = result[0].result
    assert payload is not None
    assert payload["status"] == "ok"
    assert payload["resolved_to"]["qualname"] == "_register_search_result_paths"
    assert payload["resolved_to"]["path"].endswith("src/fa/inner_loop/tools/fs_search.py")
    caller_qualnames = [r["qualname"] for r in payload["callers"]]
    assert "_handle" in caller_qualnames
    for r in payload["callers"]:
        if r["qualname"] == "_handle":
            assert r["distance"] == 1
            assert r["path"].endswith("src/fa/inner_loop/tools/fs_search.py")


# ── S17 (CT-7): seed anchors resolve + are findable ─────────────────────────


SEED_ANCHORS = {
    "§I-56-1": "src/fa/blackboard/blackboard.py",
    "§I-S15-1": "src/fa/inner_loop/state.py",
    "§I-S14b-2": "src/fa/inner_loop/runtime_limits.py",
    "§I-S14b-3": "src/fa/inner_loop/loop.py",
    "§I-S14b-4": "src/fa/memory/fts_index.py",
    "§I-S16-1": "src/fa/memory/structural_index.py",
}


@pytest.mark.skipif(
    not _real_repo_available(),
    reason="seed anchors live in the git-tracked FA tree (skipped under mutation staging)",
)
def test_seed_anchors_resolve_and_are_findable() -> None:
    """T31: every seed anchor resolves via fs_reach as kind=doc_anchor at the
    right file:line, and fs_search finds the anchor id by content."""
    from fa.inner_loop import SessionState, ToolCall, run_session
    from fa.inner_loop.registry import ToolRegistry
    from fa.inner_loop.runtime_limits import RuntimeLimits
    from fa.inner_loop.tools.fs_search import build_fs_search_tool

    repo_root = Path(__file__).resolve().parents[1]

    # fs_reach resolution for all six seeds (one index build, amortized).
    reach_spec = build_fs_reach_tool(repo_root)
    registry = ToolRegistry()
    registry.register(reach_spec)
    state = SessionState(workspace_root=repo_root, run_id="t-s17-anchors")
    for anchor_id, expected_path in SEED_ANCHORS.items():
        result = run_session(
            (
                ToolCall(
                    name="fs_reach",
                    params={"symbol": anchor_id, "direction": "down", "depth": 1},
                    call_id=f"tc-{anchor_id}",
                ),
            ),
            registry=registry,
            hooks=HookRegistry(),
            state=state,
            role="coder",
            limits=RuntimeLimits(max_iterations=3),
        )
        assert len(result) == 1 and result[0].error is None, (anchor_id, result[0].error)
        payload = result[0].result
        assert payload is not None
        assert payload["resolved_to"] is not None, anchor_id
        assert payload["resolved_to"]["qualname"] == anchor_id
        assert payload["resolved_to"]["kind"] == "doc_anchor"
        assert payload["resolved_to"]["path"] == expected_path, anchor_id
        assert payload["resolved_to"]["line"] >= 1

    # fs_search content match (one query; the search index builds lazily).
    search_spec = build_fs_search_tool(repo_root / ".fa" / "fts.db", repo_root)
    search_registry = ToolRegistry()
    search_registry.register(search_spec)
    search_state = SessionState(workspace_root=repo_root, run_id="t-s17-search")
    search_result = run_session(
        (ToolCall(name="fs_search", params={"query": "§I-56-1"}, call_id="tc-s1"),),
        registry=search_registry,
        hooks=HookRegistry(),
        state=search_state,
        role="coder",
        limits=RuntimeLimits(max_iterations=3),
    )
    assert len(search_result) == 1 and search_result[0].error is None, search_result[0].error
    found_paths = [row.get("path") for row in (search_result[0].result or {}).get("files", [])]
    assert "src/fa/blackboard/blackboard.py" in found_paths
