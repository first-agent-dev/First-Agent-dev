"""Sealed acceptance collection and the pinned verifier run (STEP9A item 1).

The seal says *what* the oracle is. This module is what makes the verifier
execute exactly that: it derives the test targets from the sealed closure (never
from the plan's free text or from the mutable tree), builds the harness argv
with ``-c``/``--rootdir``/``no:cacheprovider`` pinned to the sealed root, runs
it, and reads the nodeids with the same JUnit parser the rest of the gate uses.

Two properties are the whole point:

* **The nodeid report comes from the sealed bytes.** The only way to obtain one
  is :func:`collect_sealed_nodeids`, which refuses when the tree no longer
  matches the record — a collection run against the coder's mutable copy cannot
  be passed in. This is what turns the seal's "captured from a collection run
  against the sealed bytes" from a caller obligation into an enforced step.
* **The verifier runs the pinned digest.** :func:`run_sealed_acceptance` checks
  plan bytes and revision before running, and refuses if any sealed selector's
  nodeid did not execute.

Nodeids are reported by pytest relative to ``--rootdir`` (the sealed root), so
they are re-prefixed to workspace-relative form before anyone compares them with
the plan's selectors, which are workspace-relative.
"""

from __future__ import annotations

import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .acceptance_bundle import AcceptanceBundle, verify_plan, verify_revision, verify_sealed_root
from .acceptance_closure import pytest_argv, shell_command
from .slice_verification import (
    CommandOutcome,
    VerifyCommandExecutor,
    parse_nodeid_report,
    run_commands,
)

__all__ = [
    "AcceptanceCollectionError",
    "SealedCollection",
    "SealedRun",
    "collect_sealed_nodeids",
    "run_sealed_acceptance",
    "sealed_collection_argv",
    "sealed_test_paths",
]


class AcceptanceCollectionError(ValueError):
    """Closed diagnostic reason; never expose input paths or exception bodies."""

    def __init__(self, rule: str) -> None:
        self.rule = rule
        super().__init__(f"invalid sealed collection: {rule}")


@dataclass(frozen=True, slots=True)
class SealedCollection:
    """What one sealed collection run produced."""

    argv: tuple[str, ...]
    nodeids: Mapping[str, tuple[str, ...]]
    outcomes: Mapping[str, bool]


@dataclass(frozen=True, slots=True)
class SealedRun:
    """The evidence of a pinned run: which seal, which revision, which nodeids."""

    seal_sha256: str
    revision_id: str
    closure_sha256: str
    argv: tuple[str, ...]
    nodeids: Mapping[str, tuple[str, ...]]
    outcomes: Mapping[str, bool]


def _is_sealed_test(path: str) -> bool:
    return path.startswith("tests/") and path.endswith(".py") and PurePosixPath(path).name.startswith("test_")


def sealed_test_paths(bundle: AcceptanceBundle) -> tuple[str, ...]:
    """The sealed test modules, workspace-relative and sorted.

    Derived from the closure record, not from the plan: a test the planner named
    but never sealed is not a target, and a sealed module the plan forgot is.
    """
    if not isinstance(bundle, AcceptanceBundle):
        raise AcceptanceCollectionError("seal-invalid")
    paths = sorted(
        f"{bundle.sealed_root}/{entry.path}" for entry in bundle.closure.files if _is_sealed_test(entry.path)
    )
    if not paths:
        raise AcceptanceCollectionError("no-sealed-tests")
    return tuple(paths)


def sealed_collection_argv(bundle: AcceptanceBundle, *, report: str) -> tuple[str, ...]:
    """The harness-built invocation: sealed targets, sealed config, sealed root."""
    return pytest_argv(
        tests=sealed_test_paths(bundle),
        ini=f"{bundle.sealed_root}/pytest.ini",
        rootdir=bundle.sealed_root,
        report=report,
    )


def _workspace_nodeids(bundle: AcceptanceBundle, outcomes: Mapping[str, bool]) -> dict[str, bool]:
    """Re-key pytest's rootdir-relative nodeids to workspace-relative ones.

    Every reported nodeid must address a file the closure holds; a report that
    escaped the sealed root (an absolute path, a ``..`` hop, a file outside the
    record) is refused rather than normalized.
    """
    paths = {entry.path for entry in bundle.closure.files}
    prefix = f"{bundle.sealed_root}/"
    keyed: dict[str, bool] = {}
    for nodeid, passed in outcomes.items():
        workspace_nodeid = f"{prefix}{nodeid}"
        if not workspace_nodeid.startswith(prefix) or workspace_nodeid[len(prefix) :].partition("::")[0] not in paths:
            raise AcceptanceCollectionError("collection-nodeid-outside-closure")
        keyed[workspace_nodeid] = passed
    return keyed


def _group_nodeids(nodeids: Mapping[str, bool]) -> Mapping[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for nodeid in nodeids:
        grouped.setdefault(nodeid.partition("::")[0], []).append(nodeid)
    return {path: tuple(sorted(entries)) for path, entries in sorted(grouped.items())}


def collect_sealed_nodeids(
    bundle: AcceptanceBundle,
    *,
    workspace: Path,
    deadline: float | None = None,
    executor: VerifyCommandExecutor | None = None,
) -> SealedCollection:
    """Collect nodeids by running the sealed acceptance bytes themselves.

    Only a substrate whose writes the caller can read afterwards is supported:
    a managed cell returns its report inside the exec receipt, and reporting that
    as an unsupported substrate is honest where running the *unpinned* command
    would be a silent downgrade of the oracle.
    """
    if not isinstance(bundle, AcceptanceBundle):
        raise AcceptanceCollectionError("seal-invalid")
    if executor is not None and not getattr(executor, "writes_are_visible", True):
        raise AcceptanceCollectionError("substrate-unsupported")
    sealed_root = Path(workspace) / bundle.sealed_root
    # A tree that no longer is the sealed closure never runs: the refusal is the
    # seal's own closed rule, so this module does not re-label it.
    verify_sealed_root(bundle, sealed_root)
    with tempfile.TemporaryDirectory(prefix="fa-sealed-collection-") as directory:
        report = Path(directory) / "results.xml"
        argv = sealed_collection_argv(bundle, report=str(report))
        (result,) = run_commands(
            (shell_command(argv),), workspace=Path(workspace), deadline=deadline, executor=executor
        )
        if result.outcome is CommandOutcome.ERROR:
            raise AcceptanceCollectionError("collection-error")
        try:
            raw = report.read_bytes()
        except OSError:
            raise AcceptanceCollectionError("collection-no-report") from None
    outcomes, _detail = parse_nodeid_report(raw)
    if outcomes is None:
        raise AcceptanceCollectionError("collection-report-invalid")
    if not outcomes:
        raise AcceptanceCollectionError("collection-empty")
    if result.exit_code not in {0, 1}:
        raise AcceptanceCollectionError("collection-unusable")
    keyed = _workspace_nodeids(bundle, outcomes)
    return SealedCollection(argv=argv, nodeids=_group_nodeids(keyed), outcomes=keyed)


def run_sealed_acceptance(
    bundle: AcceptanceBundle,
    *,
    workspace: Path,
    revision_id: str,
    plan_bytes: bytes,
    deadline: float | None = None,
    executor: VerifyCommandExecutor | None = None,
) -> SealedRun:
    """The pinned run: the seal's plan, the seal's revision, the seal's bytes.

    Refuses before executing anything when the plan or the revision moved, and
    refuses after it when a sealed selector did not execute — an oracle that was
    not part of the run cannot have proven the contract it is mapped to.
    """
    verify_plan(bundle, plan_bytes)
    verify_revision(bundle, revision_id)
    collection = collect_sealed_nodeids(bundle, workspace=workspace, deadline=deadline, executor=executor)
    missing = [selector.nodeid for selector in bundle.selectors if selector.nodeid not in collection.outcomes]
    if missing:
        raise AcceptanceCollectionError("sealed-test-missing")
    return SealedRun(
        seal_sha256=bundle.seal_sha256,
        revision_id=bundle.revision_id,
        closure_sha256=bundle.closure.digest,
        argv=collection.argv,
        nodeids=collection.nodeids,
        outcomes=collection.outcomes,
    )
