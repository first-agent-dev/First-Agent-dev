"""S5P1 STEP2 — one typed choice becomes exactly one prelude outcome.

The acquisition planner returns `SELECT_EXISTING`, `BOOTSTRAP_NEW_PROJECT` or
`NEEDS_CLARIFICATION`. The controller turns that into one of three mutually
exclusive outcomes, and the exclusivity is the point: a clarification that also
carried a snapshot would let a run admit itself while claiming to need context.

Classes (knowledge/skills/tests-writing):
  C0 — the outcome type cannot hold two answers.
  C1 — the three choices map onto the three outcomes through the real port.

What must stay true (each test names the producer it kills):
  * a selection resolves to a snapshot with the resolver's own source_kind;
  * a missing project is missing context, not an IO probe of a model-typed name;
  * bootstrap never fabricates a snapshot from submitted prose;
  * a clarification never carries one either.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from fa.inner_loop.managed_acquisition import (
    AcquisitionOutcome,
    BootstrapNewProjectChoice,
    NeedsClarificationChoice,
    SelectExistingChoice,
    resolve_acquisition_choice,
)
from fa.inner_loop.tools.workspace_port import (
    PortDirectoryEntry,
    PortProjectArtifactListing,
    PortRead,
    WorkspacePortError,
)


class _Port:
    """A pinned-view stand-in over explicit bytes; it does not discover paths."""

    def __init__(self, files: dict[str, bytes], *, listing: PortProjectArtifactListing | None = None) -> None:
        self.files = files
        self.listing = listing
        self.list_calls: list[str] = []
        self.read_calls: list[str] = []

    @property
    def cache_dir(self) -> None:
        return None

    def list_project_names(self) -> Any:
        raise AssertionError("resolution must use the slugs it was given")

    def list_project_artifacts(self, project_slug: str) -> PortProjectArtifactListing:
        self.list_calls.append(project_slug)
        if self.listing is None:
            raise WorkspacePortError("denied")
        return self.listing

    def read_file(self, path: str, *, offset_bytes: int = 0, max_bytes: int = 1024 * 1024) -> PortRead:
        self.read_calls.append(path)
        if path not in self.files:
            raise WorkspacePortError("denied")
        raw = self.files[path]
        eof = offset_bytes + max_bytes >= len(raw)
        return PortRead(
            raw[offset_bytes : offset_bytes + max_bytes].decode("utf-8"), hashlib.sha256(raw).hexdigest(), eof
        )

    def write_file(self, path: str, content: str, *, expected_sha256: str | None = None) -> Any:
        raise AssertionError("acquisition must be read-only")


def _rendered_files() -> dict[str, bytes]:
    from fa.execution.publication import render_bundle

    return render_bundle(
        "demo-project",
        "foundation",
        "## Intent\n\nA project.\n\n## Out of scope\n\nOther work.\n",
        "## SLICE1: Foundation\n\nImplement the foundation.\n",
        created="2026-11-02",
    )


def _port(*, missing_artifacts: bool = False) -> _Port:
    """`missing_artifacts` reports an existing project with no roadmap at all."""
    listing = (
        PortProjectArtifactListing("missing", "missing", "missing", ())
        if missing_artifacts
        else PortProjectArtifactListing(
            "directory",
            "file",
            "directory",
            (PortDirectoryEntry("increment-01-foundation.md", "file"),),
        )
    )
    return _Port(_rendered_files(), listing=listing)


# ── C0: the outcome cannot hold two answers ───────────────────────────────────


def test_an_outcome_with_two_answers_is_refused() -> None:
    """The type is the invariant: a clarification carrying a snapshot cannot exist.

    The snapshot is given *complete* metadata so the only thing left to reject it
    is the exclusivity rule. Measured: without them this test passed on the
    metadata rule instead, and a mutant that allowed two answers survived.
    """
    resolved = resolve_acquisition_choice(
        SelectExistingChoice("demo-project", "I01"),
        inventory_view=_port(),
        inventory_slugs=("demo-project",),
    )
    assert resolved.snapshot is not None and resolved.roadmap is not None and resolved.increment is not None

    with pytest.raises(ValueError):
        AcquisitionOutcome(
            snapshot=resolved.snapshot,
            roadmap=resolved.roadmap,
            increment=resolved.increment,
            clarification=NeedsClarificationChoice("MISSING_CONTEXT"),
        )


def test_an_outcome_with_no_answer_is_refused() -> None:
    with pytest.raises(ValueError):
        AcquisitionOutcome()


def test_a_snapshot_without_its_metadata_is_refused() -> None:
    """A resolved selection carries its roadmap/increment, or it is not resolved."""
    from fa.inner_loop.plan_admission import snapshot_from_bytes

    snap = snapshot_from_bytes("worklogs/x/increments/i.md", b"# I\n\n## SLICE1: S\n\nDo.\n")
    with pytest.raises(ValueError):
        AcquisitionOutcome(snapshot=snap)


# ── C1: the three choices, through the real port ─────────────────────────────


def test_an_existing_selection_resolves_to_a_snapshot_with_the_resolver_source_kind() -> None:
    """The S5P1 happy path: choice -> inventory -> snapshot, no host path anywhere."""
    outcome = resolve_acquisition_choice(
        SelectExistingChoice("demo-project", "I01"),
        inventory_view=_port(),
        inventory_slugs=("demo-project",),
    )

    assert outcome.snapshot is not None
    assert outcome.clarification is None and outcome.bootstrap is None
    assert outcome.snapshot.ref.source_kind == "EXISTING_SELECTION"
    assert outcome.snapshot.ref.workspace_relative_path.endswith("increment-01-foundation.md")
    assert outcome.roadmap is not None and outcome.increment is not None


def test_an_unknown_project_is_missing_context_and_is_never_read() -> None:
    """A name outside the pinned revision must not become an IO probe.

    The port records every call, so "no listing happened" is observable rather
    than assumed: a producer that read anyway would show up here.
    """
    port = _port()
    outcome = resolve_acquisition_choice(
        SelectExistingChoice("not-a-project", "I01"),
        inventory_view=port,
        inventory_slugs=("demo-project",),
    )

    assert outcome.clarification is not None
    assert outcome.clarification.reason == "MISSING_CONTEXT"
    assert outcome.snapshot is None
    assert port.list_calls == [] and port.read_calls == []


def test_a_listed_project_whose_artifacts_are_missing_is_also_missing_context() -> None:
    """Being named by the view is not the same as having a roadmap to admit."""
    outcome = resolve_acquisition_choice(
        SelectExistingChoice("demo-project", "I01"),
        inventory_view=_port(missing_artifacts=True),
        inventory_slugs=("demo-project",),
    )

    assert outcome.clarification is not None
    assert outcome.clarification.reason == "MISSING_CONTEXT"
    assert outcome.snapshot is None


def test_an_unknown_increment_is_a_clarification_not_a_snapshot() -> None:
    outcome = resolve_acquisition_choice(
        SelectExistingChoice("demo-project", "I99"),
        inventory_view=_port(),
        inventory_slugs=("demo-project",),
    )

    assert outcome.clarification is not None
    assert outcome.clarification.reason == "UNKNOWN_INCREMENT"
    assert outcome.snapshot is None


def test_a_clarification_passes_through_unchanged() -> None:
    choice = NeedsClarificationChoice("AMBIGUOUS_PROJECT")
    outcome = resolve_acquisition_choice(choice, inventory_view=_port(), inventory_slugs=("demo-project",))

    assert outcome.clarification is choice
    assert outcome.snapshot is None and outcome.bootstrap is None


def test_bootstrap_asks_for_installation_and_never_fabricates_a_snapshot() -> None:
    """The decision that keeps bootstrap honest.

    The plan a bootstrap run is admitted against is the file the authority
    installs and reads back. Building a snapshot from the submitted prose would
    admit a coder against text that is not in the workspace.
    """
    choice = BootstrapNewProjectChoice(
        "new-project",
        "foundation",
        "## Intent\n\nNew.\n\n## Out of scope\n\nNone.\n",
        "## SLICE1: Build\n\nDo it.\n",
    )
    outcome = resolve_acquisition_choice(choice, inventory_view=_port(), inventory_slugs=())

    assert outcome.bootstrap is choice
    assert outcome.snapshot is None and outcome.clarification is None


def test_a_selection_reads_only_the_project_it_was_told_about() -> None:
    """Bounded reads: one project listing, then its roadmap and increments."""
    port = _port()
    resolve_acquisition_choice(
        SelectExistingChoice("demo-project", "I01"),
        inventory_view=port,
        inventory_slugs=("demo-project",),
    )

    assert port.list_calls == ["demo-project"]
    assert all(path.startswith("worklogs/demo-project/") for path in port.read_calls)


def test_an_unknown_choice_type_is_a_closed_refusal() -> None:
    with pytest.raises(ValueError):
        resolve_acquisition_choice(object(), inventory_view=_port(), inventory_slugs=())  # type: ignore[arg-type]
