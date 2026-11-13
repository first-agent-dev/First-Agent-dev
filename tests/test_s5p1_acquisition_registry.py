"""S5P1 STEP2 — the acquisition planner cannot mutate the tree it is choosing.

The acquisition stage runs one planner to produce a typed choice
(`SELECT_EXISTING` / `BOOTSTRAP_NEW_PROJECT` / `NEEDS_CLARIFICATION`). It must be
able to read and search the pinned view and nothing else: no write, no edit, no
shell, no EXEC, no `pr_prepare`.

Classes (knowledge/skills/tests-writing):
  C0 — the declared boundary itself: the positive list, and the registry it
       builds, contain no mutator and no tool outside the list.
  C3 — the registry is built from the same builders every other role uses, so
       this is the real tool surface, not a mock.

What must stay true (each test names the producer it kills):
  * acquisition tools are exactly a positive list, never "planner minus writer";
  * no mutator reaches the registry even if the planner profile gains one;
  * a managed run refuses rather than degrading to host IO.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.inner_loop.profiles import (
    ACQUISITION_TOOLS,
    PROFILES_RAW,
    build_acquisition_registry,
    build_registry_for_role,
)

# Every tool name the product knows about that could change the tree. A positive
# list is only a boundary if the excluded set is stated as well as the included.
MUTATORS = frozenset(
    {
        "fs_write_file",
        "fs_write_file_limited",
        "fs_edit_file",
        "fs_run_bash",
        "pr_prepare",
    }
)


def test_the_acquisition_registry_is_exactly_the_declared_read_only_list(tmp_path: Path) -> None:
    """C0: the boundary is the list, and the registry is the list.

    Kills a producer that builds the registry from anything other than
    `ACQUISITION_TOOLS` — including one that reuses the planner profile.
    """
    registry = build_acquisition_registry(tmp_path)
    built = tuple(spec.name for spec in registry.specs())
    assert set(built) == set(ACQUISITION_TOOLS)
    assert len(built) == len(ACQUISITION_TOOLS), "no duplicates"


def test_no_mutator_reaches_the_acquisition_registry(tmp_path: Path) -> None:
    """C0: the four mutation surfaces named in §7 are absent by name."""
    registry = build_acquisition_registry(tmp_path)
    names = {spec.name for spec in registry.specs()}
    smuggled = names & MUTATORS
    assert not smuggled, f"acquisition registry exposes mutators: {sorted(smuggled)}"


def test_the_planner_profile_really_does_contain_a_writer_so_the_boundary_is_load_bearing(
    tmp_path: Path,
) -> None:
    """The contrast that makes the previous test mean something.

    If the planner profile stopped carrying `fs_write_file`, "no mutator in the
    acquisition registry" would be true for a trivial reason. This asserts the
    temptation exists and that acquisition refuses it anyway.
    """
    assert "fs_write_file" in PROFILES_RAW["planner"]["tools"]
    planner = build_registry_for_role("planner", tmp_path)
    assert "fs_write_file" in {spec.name for spec in planner.specs()}
    acquisition = build_acquisition_registry(tmp_path)
    assert "fs_write_file" not in {spec.name for spec in acquisition.specs()}


def test_a_new_planner_mutator_is_not_inherited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """EDGE kill-check: a future planner tool must not leak in by being adjacent.

    The acquisition registry reads a module-level constant, so widening the
    planner profile cannot widen acquisition. This is the reason the constant is
    positive rather than computed from the planner's list.
    """
    widened = dict(PROFILES_RAW["planner"])
    # Two shapes: one whose name says "write" and one whose name does not. A
    # producer that derives the list by filtering names would keep the second.
    widened["tools"] = [*widened["tools"], "pr_prepare", "fs_run_bash"]
    monkeypatch.setitem(PROFILES_RAW, "planner", widened)

    acquisition = build_acquisition_registry(tmp_path)
    names = {spec.name for spec in acquisition.specs()}
    assert "pr_prepare" not in names
    assert "fs_run_bash" not in names
    assert set(names) == set(ACQUISITION_TOOLS)


def test_the_declared_list_itself_contains_no_mutator() -> None:
    """C0: guard the constant, not only its use — this is the producer's input."""
    assert not set(ACQUISITION_TOOLS) & MUTATORS
    for name in ACQUISITION_TOOLS:
        assert "write" not in name and "edit" not in name and "bash" not in name


def test_the_acquisition_surface_is_identical_in_host_and_managed_modes(tmp_path: Path) -> None:
    """The boundary must not depend on how the run is executed.

    Measured: all five declared tools have a managed builder, so a managed run
    does not lose one and a host run does not gain one. If that ever changed, the
    acquisition planner would have a different capability depending on deployment,
    which is exactly the kind of silent difference this list exists to prevent.
    """
    host = {spec.name for spec in build_acquisition_registry(tmp_path).specs()}
    managed = {spec.name for spec in build_acquisition_registry(tmp_path, workspace_io=_StubPort()).specs()}
    assert host == managed == set(ACQUISITION_TOOLS)


def test_a_project_tool_executor_without_a_managed_port_is_refused(tmp_path: Path) -> None:
    """Failure behaviour: no host fallback for a managed-only capability."""
    with pytest.raises(ValueError, match="requires a managed workspace port"):
        build_acquisition_registry(tmp_path, project_tool_executor=object())


class _StubPort:
    """A workspace port that is present but unused during registry construction."""

    @property
    def cache_dir(self) -> None:
        return None

    def read_file(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("registry construction must not read")

    def list_project_names(self) -> object:
        raise AssertionError("registry construction must not list")

    def list_project_artifacts(self, _slug: str) -> object:
        raise AssertionError("registry construction must not list")

    def write_file(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("registry construction must not write")
