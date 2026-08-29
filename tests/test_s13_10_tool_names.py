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

**D10 revision (2026-08-27).** The coverage test scraped tool names with
``re.compile(r'name="((?:fs|pr)_[a-z_]+)"')``. That regex is prefix-scoped, so
any tool whose name is not ``fs_*``/``pr_*`` was structurally invisible to it —
verified by execution: ``name="invoke_workflow"``, ``name="wf_run"`` and
``name="fs_readFile"`` all scrape to nothing and therefore could never fail the
coverage assertion. Enforcement is now layered:

1. **Runtime, fail-closed** — ``build_registry_for_role`` raises
   ``ToolWireNameError`` on a non-portable name. That is the production
   composition root: it can only emit tools from the builder table, so any name
   reaching it is one a real role will ship to a real provider. Prefix-agnostic
   by construction.
2. **Coverage, prefix-agnostic** — the builders in ``profiles.py`` are
   enumerated and their real ``ToolSpec.name`` values asserted against
   ``TOOL_NAMES``. No text scraping, so a renamed or new-prefix tool cannot
   hide.
3. **Regression pin** — the dotted-literal scan is kept as-is. It guards the
   specific S13.10 regression (a dotted name reappearing in source) and is
   cheap.

Three stricter placements were considered and rejected on measurement.
``ToolSpec.__post_init__`` (47 construction sites, 21 with dotted names),
``ToolRegistry.register`` (16 dotted sites) and ``render_tool_specs`` (11 tests
reach it via ``drive_session``) are all shared with fixtures that deliberately
use names like ``test.echo``, ``t.ok`` and ``demo.crash`` to exercise dispatch,
validation and stop-paths independently of naming policy. Enforcing at any of
them would have meant editing 44 literals across 12 test files whose intent has
nothing to do with tool naming — churn without signal. The composition root is
the tightest boundary that production traffic crosses and fixtures do not.

**Kill-checks:**
- a tool name missing from `TOOL_NAMES` → `test_builder_names_are_all_canonical` fails;
- a dotted name reintroduced in `tools/*.py` → `test_no_dotted_tool_spec_names_remain` fails;
- deleting the guard in `build_registry_for_role` → `test_composition_root_rejects_non_portable_name` fails.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from fa.inner_loop.registry import ToolResult, ToolSpec, ToolWireNameError
from fa.inner_loop.tool_names import TOOL_NAMES, is_valid_wire_name


def _never_called_handler(params: Mapping[str, object]) -> ToolResult:
    """A real ``ToolHandler`` for specs that exist only to be name-checked.

    These two tests drive ``build_registry_for_role``, which validates wire
    names while *building* specs and never invokes a handler. The handler is
    therefore required by the type only. It raises rather than returning a
    filler ``ToolResult`` so that if a future change does start executing
    these stubs, the test fails loudly instead of silently exercising a
    no-op tool and reporting a pass.
    """
    raise AssertionError(f"name-check stub handler was invoked with {dict(params)!r}")


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


# --- C1: prefix-agnostic coverage via the real builders (D10) ----------------


def _real_tool_spec_names() -> set[str]:
    """Build every tool the profile system knows about and return real names.

    Prefix-agnostic by construction: it asks ``profiles.py`` for its builder
    table and reads ``ToolSpec.name`` off the constructed objects, so a tool
    named ``invoke_workflow`` counts exactly like ``fs_read_file``.
    """
    import tempfile
    from pathlib import Path

    from fa.inner_loop.profiles import _build_tool_builders

    workspace = Path(tempfile.mkdtemp())
    names: set[str] = set()
    for build in _build_tool_builders(workspace, bash_timeout=30).values():
        names.add(build().name)
    return names


def test_builder_names_are_all_canonical() -> None:
    """C1 (CT5, kill-check) — every buildable tool's real name is in TOOL_NAMES.

    Replaces the prefix-scoped regex scrape. Because this reads the actual
    ToolSpec objects, a tool added under any prefix is covered automatically.
    """
    names = _real_tool_spec_names()
    assert names, "expected the builder table to produce at least one tool"
    unknown = names - set(TOOL_NAMES)
    assert not unknown, f"ToolSpec names not in canonical TOOL_NAMES: {sorted(unknown)}"


def test_every_builder_name_is_provider_portable() -> None:
    """C1 (CT1) — every buildable tool would survive a strict provider."""
    offenders = sorted(n for n in _real_tool_spec_names() if not is_valid_wire_name(n))
    assert not offenders, f"non-portable tool names: {offenders}"


def test_builder_keys_match_the_names_they_build() -> None:
    """C1 — the profile key and the ToolSpec.name agree.

    ``PROFILES_RAW`` lists tools by builder key while the wire uses
    ``ToolSpec.name``. A divergence means a profile silently grants a
    differently-named tool. ``fs_write_file_limited`` is the one sanctioned
    exception: it is a restricted builder for ``fs_write_file`` (profiles.py
    swaps it in for the planner), so it intentionally builds under the base
    name.
    """
    import tempfile
    from pathlib import Path

    from fa.inner_loop.profiles import _build_tool_builders

    workspace = Path(tempfile.mkdtemp())
    mismatched = {
        key: build().name
        for key, build in _build_tool_builders(workspace, bash_timeout=30).items()
        if build().name != key and key != "fs_write_file_limited"
    }
    assert not mismatched, f"builder key != ToolSpec.name: {mismatched}"


# --- C1: the composition root fails closed (D10) ----------------------------


def test_composition_root_rejects_non_portable_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """C1 (kill-check) — a bad wire name cannot escape build_registry_for_role.

    Injects a rogue builder into the table the composition root reads, which
    is the only way a non-portable name could realistically appear: someone
    adds a tool whose name does not follow the convention.
    """
    import tempfile
    from pathlib import Path

    from fa.inner_loop import profiles as profiles_mod

    real = profiles_mod._build_tool_builders

    def rogue(workspace_root: Path, *, bash_timeout: int = 30) -> dict[str, Callable[[], ToolSpec]]:
        builders = dict(real(workspace_root, bash_timeout=bash_timeout))
        builders["fs_read_file"] = lambda: ToolSpec(
            name="fs.read_file",
            description="d",
            input_schema={"type": "object"},
            permission="read",
            handler=_never_called_handler,
        )
        return builders

    monkeypatch.setattr(profiles_mod, "_build_tool_builders", rogue)
    with pytest.raises(ToolWireNameError) as excinfo:
        profiles_mod.build_registry_for_role("chat", Path(tempfile.mkdtemp()))
    assert excinfo.value.tool_name == "fs.read_file"


def test_composition_root_accepts_a_non_fs_pr_prefixed_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """C1 — the guard is prefix-agnostic, not an fs_/pr_ allowlist.

    ``invoke_workflow`` is the motivating case: it carries neither namespace
    prefix and must build cleanly once S4b registers it.
    """
    import tempfile
    from pathlib import Path

    from fa.inner_loop import profiles as profiles_mod

    real = profiles_mod._build_tool_builders

    def with_workflow(workspace_root: Path, *, bash_timeout: int = 30) -> dict[str, Callable[[], ToolSpec]]:
        builders = dict(real(workspace_root, bash_timeout=bash_timeout))
        builders["fs_read_file"] = lambda: ToolSpec(
            name="invoke_workflow",
            description="d",
            input_schema={"type": "object"},
            permission="read",
            handler=_never_called_handler,
        )
        return builders

    monkeypatch.setattr(profiles_mod, "_build_tool_builders", with_workflow)
    registry = profiles_mod.build_registry_for_role("chat", Path(tempfile.mkdtemp()))
    assert "invoke_workflow" in registry.names()


@pytest.mark.parametrize("bad", ["fs.read_file", "pr.prepare", "bad name!", "x" * 65])
def test_wire_name_predicate_rejects_non_portable(bad: str) -> None:
    """C0p — the predicate the guard depends on."""
    assert not is_valid_wire_name(bad)
