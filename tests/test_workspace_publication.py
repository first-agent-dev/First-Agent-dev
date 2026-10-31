"""SLICE3 STEP1 (part 1) — CT104 terminal barrier over the real authority.

Classes (knowledge/skills/tests-writing):
  C0 — `WorkspaceAuthority.record_terminal` as the single durable receipt write;
  C3 — `ViewStopper.stop_view` orchestration against real view records on disk,
       with the *external* descendant observation doubled at its seam (a kernel
       cgroup fact cannot be produced locally; it is C-host work in
       tests/integration/test_publication_recovery.py).

What must stay true (each test names the producer it kills):
  * admission is closed and handlers drained BEFORE any cell is stopped;
  * TERMINAL needs a positive observation — never a timeout, never an exception,
    never a missing observer;
  * anything short of that leaves the view STOPPING and owned;
  * `record_terminal` refuses an OPEN view (no skipping close/drain) and is
    idempotent; the view's own state stays STOPPING — terminality is a
    precondition of sealing, not a state the schema publishes.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

import fa.execution.publication as publication_module
import fa.execution.workspace as workspace_module
from fa.execution.publication import MANIFEST_NAME, SealResult, derive_revision_id, seal_view
from fa.execution.supervisor import SupervisorError, TerminalVerdict, ViewStopper
from fa.execution.types import Access, GrantReply, NamespaceRef, ViewPurpose, ViewRef
from fa.execution.workspace import WorkspaceAuthority
from fa.inner_loop.plan_admission import PlanRefError, read_plan_snapshot
from tests.test_execution_admission import claim as claim_operation
from tests.test_execution_admission import request as exec_request
from tests.test_execution_readers import record_path, ref
from tests.test_execution_views import native_profile
from tests.test_execution_workspace import ACTOR, PEER, Site, ok, until
from tests.test_execution_workspace import site as site

PROBE = "probe.txt"


def _view_root(site: Site, grant: GrantReply) -> Path:
    return record_path(site, grant).parent


def _record(site: Site, grant: GrantReply) -> dict[str, Any]:
    value = json.loads((_view_root(site, grant) / "view.json").read_text())
    assert isinstance(value, dict)
    return value


class RecordingCells:
    """The real backend's future seam: stop, then answer the kernel question.

    ``verdicts`` are returned in order (last value repeats); ``error`` makes the
    observation raise, which must never be read as terminality.
    """

    def __init__(
        self,
        authority: WorkspaceAuthority,
        grant: GrantReply,
        *,
        verdicts: list[bool | None],
        error: Exception | None = None,
    ) -> None:
        self.authority = authority
        self.grant = grant
        self.verdicts = verdicts
        self.error = error
        self.stop_calls = 0
        self.polls = 0
        self.write_error: str | None = None
        self.state_at_stop: str | None = None

    def stop_cells(self, namespace: NamespaceRef, view_ref: ViewRef, *, deadline: float) -> None:
        self.stop_calls += 1
        # The whole ordering claim in one observation: by the time cells are
        # stopped, a write must already be refused and the record must already
        # say STOPPING.
        self.state_at_stop = json.loads(
            (
                self.authority._state / "workspaces" / view_ref.workspace_id / "views" / view_ref.view_id / "view.json"
            ).read_text()
        )["state"]
        try:
            self.authority.write_file(
                PEER,
                ACTOR,
                view_ref=view_ref,
                capability=self.grant.capability,
                path=PROBE,
                content="late write\n",
                expected_sha256=None,
                deadline=deadline,
            )
        except SupervisorError as error:
            self.write_error = error.code
        else:
            self.write_error = "allowed"

    def cells_terminal(self, namespace: NamespaceRef, view_ref: ViewRef) -> bool | None:
        self.polls += 1
        if self.error is not None:
            raise self.error
        index = min(self.polls - 1, len(self.verdicts) - 1)
        return self.verdicts[index]


def _project_view(owner: WorkspaceAuthority, ids: dict[str, str], lease: GrantReply) -> GrantReply:
    return owner.create_view(
        PEER,
        ACTOR,
        workspace_id=ids["workspace_id"],
        capability=lease.capability,
        purpose=ViewPurpose.PROJECT,
        access=Access.WRITE,
        candidate_scope=None,
        plan_ref=None,
        formal_evidence=False,
        deadline=until(),
    )


# ---------------------------------------------------------------------------
# C3 — the stop flow
# ---------------------------------------------------------------------------


def test_stop_view_closes_admission_and_drains_before_it_stops_cells(site: Site) -> None:
    """producer-kill-check: drop the close_admission/drain calls from stop_view."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _project_view(owner, ids, lease)
        cells = RecordingCells(owner, grant, verdicts=[True])
        stopper = ViewStopper(owner, cells=cells, poll_interval_s=0.001)

        result = stopper.stop_view(
            PEER,
            ACTOR,
            view_ref=ref(grant),
            capability=grant.capability,
            deadline=until(),
        )

        assert result.verdict is TerminalVerdict.TERMINAL
        assert result.terminal is True
        assert cells.stop_calls == 1
        assert cells.write_error == "VIEW_CLOSED", "a late write was still admitted"
        assert cells.state_at_stop == "STOPPING", "cells were stopped before admission closed"
        # Terminality is a receipt, not a state: the view stays STOPPING until it is sealed.
        assert (_view_root(site, grant) / "terminal.json").is_file()
        assert _record(site, grant)["state"] == "STOPPING"


def test_stop_view_polls_until_the_observation_is_empty(site: Site) -> None:
    """producer-kill-check: accept the first observation whatever it says."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _project_view(owner, ids, lease)
        cells = RecordingCells(owner, grant, verdicts=[False, False, True])
        stopper = ViewStopper(owner, cells=cells, poll_interval_s=0.001)

        result = stopper.stop_view(PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until())

        assert result.verdict is TerminalVerdict.TERMINAL
        assert cells.polls == 3
        assert cells.stop_calls == 1


def test_a_populated_view_stays_stopping_and_keeps_its_record(site: Site) -> None:
    """producer-kill-check: mark terminal when the budget runs out."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _project_view(owner, ids, lease)
        cells = RecordingCells(owner, grant, verdicts=[False])
        stopper = ViewStopper(owner, cells=cells, poll_interval_s=0.001)

        result = stopper.stop_view(
            PEER,
            ACTOR,
            view_ref=ref(grant),
            capability=grant.capability,
            deadline=time.monotonic() + 0.05,
        )

        assert result.verdict is TerminalVerdict.POPULATED
        assert result.terminal is False
        assert result.reason is not None
        assert not (_view_root(site, grant) / "terminal.json").exists(), "an unproven view got a receipt"
        assert _record(site, grant)["state"] == "STOPPING"


def test_an_observation_failure_is_never_terminality(site: Site) -> None:
    """producer-kill-check: swallow the observer exception and continue to mark."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _project_view(owner, ids, lease)
        cells = RecordingCells(owner, grant, verdicts=[True], error=RuntimeError("cgroup unreadable"))
        stopper = ViewStopper(owner, cells=cells, poll_interval_s=0.001)

        result = stopper.stop_view(PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until())

        assert result.verdict is TerminalVerdict.UNKNOWN
        assert result.terminal is False
        assert not (_view_root(site, grant) / "terminal.json").exists()
        assert _record(site, grant)["state"] == "STOPPING"


def test_no_observer_means_no_terminality(site: Site) -> None:
    """producer-kill-check: treat a missing seam as 'probably stopped'."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _project_view(owner, ids, lease)
        stopper = ViewStopper(owner)

        result = stopper.stop_view(PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until())

        assert result.verdict is TerminalVerdict.UNKNOWN
        assert result.terminal is False
        assert not (_view_root(site, grant) / "terminal.json").exists()
        assert _record(site, grant)["state"] == "STOPPING"


def test_a_terminal_view_is_not_stopped_twice(site: Site) -> None:
    """producer-kill-check: re-run the whole stop flow on an already-terminal view."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _project_view(owner, ids, lease)
        cells = RecordingCells(owner, grant, verdicts=[True])
        stopper = ViewStopper(owner, cells=cells, poll_interval_s=0.001)

        first = stopper.stop_view(PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until())
        second = stopper.stop_view(PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until())

        assert first.terminal is True and second.terminal is True
        assert cells.stop_calls == 1
        assert cells.polls == 1


def test_an_unavailable_observation_is_not_terminality(site: Site) -> None:
    """producer-kill-check: collapse ``None`` (cannot tell) into ``True``."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _project_view(owner, ids, lease)
        cells = RecordingCells(owner, grant, verdicts=[None])
        stopper = ViewStopper(owner, cells=cells, poll_interval_s=0.001)

        result = stopper.stop_view(PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until())

        assert result.verdict is TerminalVerdict.UNKNOWN
        assert result.terminal is False
        assert cells.polls == 1, "an unreadable observation should not be retried as if it were 'not yet'"
        assert not (_view_root(site, grant) / "terminal.json").exists()


def test_stop_view_waits_for_a_live_dispatch_before_it_stops_cells(site: Site) -> None:
    """producer-kill-check: drop the drain call — cells are stopped under a live dispatch.

    A dispatch admission (the backend's create/start/send scope) is held outside
    the authority mutex, which is exactly the work ``drain`` exists to wait for.
    """
    approved = site.state.parent / "approved-cache"
    approved.mkdir(mode=0o755, exist_ok=True)
    with site.owner(view_profile=native_profile(), approved_cache=approved) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _project_view(owner, ids, lease)
        request = exec_request(grant)
        claim_operation(owner, request)
        scope = owner.admit(PEER, request, deadline=until())
        try:
            cells = RecordingCells(owner, grant, verdicts=[True])
            stopper = ViewStopper(owner, cells=cells, poll_interval_s=0.001)
            stopped: dict[str, Any] = {}

            def run() -> None:
                stopped["result"] = stopper.stop_view(
                    PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until()
                )

            thread = threading.Thread(target=run)
            thread.start()
            time.sleep(0.2)
            assert cells.stop_calls == 0, "cells were stopped while a dispatch was still live"
            scope.close()
            thread.join(10)
            assert not thread.is_alive(), "stop_view never drained the live dispatch"
            assert cells.stop_calls == 1
            assert stopped["result"].terminal is True
        finally:
            scope.close()


def test_a_record_that_does_not_persist_is_durability_unknown(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    """producer-kill-check: skip the read-back after the rewrite."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _project_view(owner, ids, lease)
        ok(
            lambda: owner.close_admission(
                PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until()
            )
        )
        monkeypatch.setattr(workspace_module, "_replace_private_bytes", lambda *a, **k: None)

        with pytest.raises(SupervisorError) as error:
            owner.record_terminal(PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until())

        assert error.value.code == "DURABILITY_UNKNOWN"
        assert not (_view_root(site, grant) / "terminal.json").exists()


# ---------------------------------------------------------------------------
# C0 — the single durable state transition
# ---------------------------------------------------------------------------


def test_record_terminal_refuses_an_open_view(site: Site) -> None:
    """producer-kill-check: drop record_terminal's OPEN/gate guard."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _project_view(owner, ids, lease)

        with pytest.raises(SupervisorError) as error:
            owner.record_terminal(PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until())

        assert error.value.code == "VIEW_CLOSED"
        assert _record(site, grant)["state"] == "OPEN"


def test_record_terminal_is_durable_and_idempotent(site: Site) -> None:
    """producer-kill-check: skip the read-back after the rewrite."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _project_view(owner, ids, lease)
        ok(
            lambda: owner.close_admission(
                PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until()
            )
        )

        first = ok(
            lambda: owner.record_terminal(
                PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until()
            )
        )
        second = ok(
            lambda: owner.record_terminal(
                PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until()
            )
        )

        assert first == second
        assert first["view_ref"] == ref(grant).to_dict()
        assert (_view_root(site, grant) / "terminal.json").is_file()
        # The state machine is untouched by the receipt: sealing owns SEALED.
        assert _record(site, grant)["state"] == "STOPPING"


# ---------------------------------------------------------------------------
# CT105 — the immutable sealed export (E267)
# ---------------------------------------------------------------------------
#
# Classes (knowledge/skills/tests-writing):
#   C0 — `WorkspaceAuthority.prepare_seal`/`mark_sealed` as the single owner of
#        seal preconditions and of the `STOPPING -> SEALED` transition;
#   C3 — `seal_view` over real view bytes on the real filesystem.
#
# What must stay true (each test names the producer it kills):
#   * the tree is RECOMPUTED after the barrier; no stored hash is trusted;
#   * nothing seals without a terminal receipt, a closed gate and a live writer;
#   * tombstones repeat base facts and never hide a deletion of protected bytes;
#   * the plan's canonical path cannot be rewritten through an ordinary seal;
#   * the manifest is durable BEFORE the state flip, and a failed read-back is
#     DURABILITY_UNKNOWN with the view still STOPPING;
#   * canonical roots, `current.json`, revisions and reader pins are untouched.


def _view(
    owner: WorkspaceAuthority,
    ids: dict[str, str],
    lease: GrantReply,
    *,
    plan_ref: Any = None,
    purpose: ViewPurpose = ViewPurpose.PROJECT,
) -> GrantReply:
    """Create one view without stopping it (so a case can still write)."""
    writable = purpose in {ViewPurpose.PROJECT, ViewPurpose.MUTATION, ViewPurpose.PROVISIONING}
    return owner.create_view(
        PEER,
        ACTOR,
        workspace_id=ids["workspace_id"],
        capability=lease.capability,
        purpose=purpose,
        access=Access.WRITE if writable else Access.READ,
        candidate_scope=None,
        plan_ref=plan_ref,
        formal_evidence=False,
        deadline=until(),
    )


def _stop(owner: WorkspaceAuthority, grant: GrantReply) -> None:
    stopper = ViewStopper(owner, cells=RecordingCells(owner, grant, verdicts=[True]), poll_interval_s=0.001)
    result = stopper.stop_view(PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until())
    assert result.terminal is True, "the fixture could not stop its own view"


def _stopped(
    owner: WorkspaceAuthority,
    ids: dict[str, str],
    lease: GrantReply,
    *,
    plan_ref: Any = None,
    purpose: ViewPurpose = ViewPurpose.PROJECT,
) -> GrantReply:
    """Create one view and stop it through the real barrier (CT104's flow)."""
    grant = _view(owner, ids, lease, plan_ref=plan_ref, purpose=purpose)
    _stop(owner, grant)
    return grant


def _seal(owner: WorkspaceAuthority, grant: GrantReply, deadline: float | None = None) -> SealResult:
    return seal_view(
        owner,
        PEER,
        ACTOR,
        view_ref=ref(grant),
        capability=grant.capability,
        deadline=until() if deadline is None else deadline,
    )


def _manifest(site: Site, grant: GrantReply) -> dict[str, Any]:
    value = json.loads((_view_root(site, grant) / MANIFEST_NAME).read_text())
    assert isinstance(value, dict)
    return value


def _source_root(site: Site, grant: GrantReply) -> Path:
    return _view_root(site, grant) / "source"


def test_seal_records_the_recomputed_tree_and_flips_the_view_to_sealed(site: Site) -> None:
    """producer-kill-check: drop `_validate_sealed_tree` (and the SEALED write)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)

        result = _seal(owner, grant)

        manifest = _manifest(site, grant)
        assert manifest["workspace_id"] == ids["workspace_id"]
        assert manifest["view_id"] == ref(grant).view_id
        assert manifest["base_revision"] == ref(grant).base_revision
        assert manifest["generation"] == ref(grant).generation
        assert [entry["path"] for entry in manifest["entries"]] == sorted(
            entry["path"] for entry in manifest["entries"]
        )
        assert all(entry["deleted"] is False for entry in manifest["entries"])
        assert result.tree_sha256 == manifest["tree_sha256"]
        assert result.sealed_manifest_id.startswith("seal-")
        assert result.revision_id == derive_revision_id(manifest)
        assert result.to_wire() == {
            "sealed_manifest_id": result.sealed_manifest_id,
            "revision_id": result.revision_id,
            "tree_sha256": result.tree_sha256,
        }
        record = _record(site, grant)
        assert record["state"] == "SEALED"
        assert record["sealed_manifest_id"] == result.sealed_manifest_id


def test_seal_recomputes_the_tree_instead_of_trusting_the_stored_hash(site: Site) -> None:
    """producer-kill-check: trust `input_tree_sha256`/a stored manifest (skip the recompute)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        # A cell wrote through the PTY: on disk, but not in the recorded input hash.
        (_source_root(site, grant) / "late.txt").write_text("written after the view was created\n")

        result = _seal(owner, grant)

        entries = {entry["path"]: entry for entry in _manifest(site, grant)["entries"]}
        assert entries["late.txt"]["deleted"] is False
        assert result.tree_sha256 != _record(site, grant)["input_tree_sha256"]


def test_seal_tombstones_a_base_file_that_the_view_deleted(site: Site) -> None:
    """producer-kill-check: drop the tombstone derivation (a deletion would vanish)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        gone = _source_root(site, grant) / "untracked.txt"
        base_entry = {
            "path": "untracked.txt",
            "type": "file",
            "mode": gone.stat().st_mode & 0o777,
            "size": gone.stat().st_size,
            "sha256": hashlib.sha256(gone.read_bytes()).hexdigest(),
            "deleted": False,
            "link_target": None,
        }
        gone.unlink()

        _seal(owner, grant)

        entries = {entry["path"]: entry for entry in _manifest(site, grant)["entries"]}
        assert entries["untracked.txt"]["deleted"] is True
        assert {key: entries["untracked.txt"][key] for key in base_entry if key != "deleted"} == {
            key: base_entry[key] for key in base_entry if key != "deleted"
        }
        # The digest covers the non-deleted domain only (spec §5).
        live = [entry for entry in _manifest(site, grant)["entries"] if not entry["deleted"]]
        assert (
            hashlib.sha256(
                json.dumps(live, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            == _manifest(site, grant)["tree_sha256"]
        )


def test_seal_accepts_an_unchanged_link_and_refuses_a_new_one(site: Site) -> None:
    """producer-kill-check: drop the new-link rejection in `_validate_against_base`."""
    (site.source / "kept.txt").write_text("kept\n")
    (site.source / "link-kept").symlink_to("kept.txt")
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        unchanged = _stopped(owner, ids, lease)
        added = _stopped(owner, ids, lease, purpose=ViewPurpose.PROVISIONING)
        (_source_root(site, added) / "link-new").symlink_to("kept.txt")

        _seal(owner, unchanged)

        assert any(entry["type"] == "symlink" for entry in _manifest(site, unchanged)["entries"])
        with pytest.raises(SupervisorError) as refused:
            _seal(owner, added)
        assert refused.value.code == "INPUT_POLICY"
        assert _record(site, added)["state"] == "STOPPING"


def test_a_plan_file_cannot_be_rewritten_through_an_ordinary_seal(site: Site) -> None:
    """producer-kill-check: drop `_validate_plan_boundary` (the coder edits its judge)."""
    (site.source / "plan.md").write_text("# admitted plan\n")
    admitted = read_plan_snapshot(site.source, Path("plan.md")).ref
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        unchanged = _stopped(owner, ids, lease, plan_ref=admitted)
        edited = _stopped(owner, ids, lease, plan_ref=admitted)
        (_source_root(site, edited) / "plan.md").write_text("# admitted plan\n\n## SLICE9: mine\n")

        _seal(owner, unchanged)

        with pytest.raises(SupervisorError) as refused:
            _seal(owner, edited)
        assert refused.value.code == "INPUT_POLICY"
        assert not (_view_root(site, edited) / MANIFEST_NAME).exists()
        assert _record(site, edited)["state"] == "STOPPING"


def test_seal_refuses_an_open_view_and_a_missing_receipt(site: Site) -> None:
    """producer-kill-check: drop the state/gate and terminal-receipt preconditions."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        open_view = _project_view(owner, ids, lease)
        stopped = _stopped(owner, ids, lease)
        # Admission closed and drained, but no descendant observation exists yet.
        owner.close_admission(PEER, ACTOR, view_ref=ref(stopped), capability=stopped.capability, deadline=until())
        owner.drain(PEER, ACTOR, view_ref=ref(stopped), capability=stopped.capability, deadline=until())
        (_view_root(site, stopped) / "terminal.json").unlink()

        with pytest.raises(SupervisorError) as still_open:
            _seal(owner, open_view)
        assert still_open.value.code == "VIEW_CLOSED"
        with pytest.raises(SupervisorError) as no_receipt:
            _seal(owner, stopped)
        assert no_receipt.value.code == "TERMINALITY_UNKNOWN"
        assert _record(site, open_view)["state"] == "OPEN"
        assert _record(site, stopped)["state"] == "STOPPING"
        # Refusal happens BEFORE the manifest: no durable junk for an unproven view.
        assert not (_view_root(site, stopped) / MANIFEST_NAME).exists()


def test_seal_is_idempotent_and_refuses_a_rewritten_manifest(site: Site) -> None:
    """producer-kill-check: drop the durable-manifest verification in the replay path."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)

        first = _seal(owner, grant)
        second = _seal(owner, grant)

        assert second == first
        assert len([name for name in os.listdir(_view_root(site, grant)) if name == MANIFEST_NAME]) == 1
        forged = _manifest(site, grant)
        forged["entries"] = [
            {**entry, "sha256": "f" * 64} if entry["type"] == "file" else entry for entry in forged["entries"]
        ]
        live = [entry for entry in forged["entries"] if not entry["deleted"]]
        forged["tree_sha256"] = hashlib.sha256(
            json.dumps(live, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        (_view_root(site, grant) / MANIFEST_NAME).write_text(json.dumps(forged))

        with pytest.raises(SupervisorError) as refused:
            _seal(owner, grant)
        assert refused.value.code == "CORRUPT_STATE"


def test_a_manifest_that_does_not_persist_is_durability_unknown(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    """producer-kill-check: flip SEALED without proving the manifest is on disk."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)

        def refuse(*args: Any, **kwargs: Any) -> None:
            raise OSError("sandbox: manifest write refused")

        monkeypatch.setattr(publication_module, "_replace_private_bytes", refuse)
        with pytest.raises(SupervisorError) as failed:
            _seal(owner, grant)

        assert failed.value.code == "DURABILITY_UNKNOWN"
        assert _record(site, grant)["state"] == "STOPPING"
        assert not (_view_root(site, grant) / MANIFEST_NAME).exists()


def test_seal_leaves_canonical_bytes_current_and_pins_untouched(site: Site) -> None:
    """producer-kill-check: write canonical bytes / move `current.json` during seal."""
    canonical = {
        path.relative_to(site.source): path.read_bytes()
        for path in sorted(site.source.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        pin = ok(
            lambda: owner.pin_reader(
                PEER,
                ACTOR,
                workspace_id=ids["workspace_id"],
                revision_id=ids["revision_id"],
                plan_ref=None,
                formal_evidence=False,
                deadline=until(),
            )
        )
        grant = _stopped(owner, ids, lease)
        current = (site.state / "workspaces" / ids["workspace_id"] / "current.json").read_bytes()
        revision = site.revision(ids)

        _seal(owner, grant)

        assert (site.state / "workspaces" / ids["workspace_id"] / "current.json").read_bytes() == current
        assert site.revision(ids) == revision
        assert {
            path.relative_to(site.source): path.read_bytes()
            for path in sorted(site.source.rglob("*"))
            if path.is_file() and not path.is_symlink()
        } == canonical
        pinned = owner.read_file(
            PEER,
            ACTOR,
            view_ref=ref(pin),
            capability=pin.capability,
            path="untracked.txt",
            offset_bytes=0,
            max_bytes=64,
            deadline=until(),
        )
        assert pinned["content"] == "untracked"


def test_the_validator_refuses_forged_paths_facts_and_digests(site: Site) -> None:
    """producer-kill-check: drop the path-domain, privilege and digest checks."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        _seal(owner, grant)
        manifest = _manifest(site, grant)

        def refuses(**changes: Any) -> None:
            forged = json.loads(json.dumps(manifest))
            forged.update(changes)
            with pytest.raises(SupervisorError):
                publication_module._validate_sealed_tree(forged, plan_path=None, base_entries=())

        refuses(entries=list(reversed(manifest["entries"])))
        refuses(
            entries=[{**entry, "path": ".git/index"} for entry in manifest["entries"][:1]] + manifest["entries"][1:]
        )
        refuses(
            entries=[{**entry, "mode": 0o4755} if entry["type"] == "file" else entry for entry in manifest["entries"]]
        )
        refuses(tree_sha256="0" * 64)


def test_the_validator_refuses_a_manifest_that_moves_the_plan(site: Site) -> None:
    """producer-kill-check: drop `_validate_plan_boundary`.

    End-to-end this rule is *masked*: `prepare_seal` rechecks the view's
    ProtectedPlanContext first, so an edited plan never reaches here through
    `seal_view`. The rule still guards the manifest itself (a future seal path
    that does not hold that context), so it is oracle-tested directly rather
    than credited to a seal-flow case it never decides.
    """
    (site.source / "plan.md").write_text("# admitted plan\n")
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        _seal(owner, grant)
        manifest = _manifest(site, grant)
        base = list(manifest["entries"])

        def refuses(entries: list[dict[str, Any]]) -> None:
            forged = json.loads(json.dumps(manifest))
            forged["entries"] = entries
            live = [entry for entry in entries if not entry["deleted"]]
            forged["tree_sha256"] = hashlib.sha256(
                json.dumps(live, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            with pytest.raises(SupervisorError) as refused:
                publication_module._validate_sealed_tree(forged, plan_path="plan.md", base_entries=base)
            assert refused.value.code == "INPUT_POLICY"

        moved = [{**entry, "sha256": "a" * 64} if entry["path"] == "plan.md" else entry for entry in base]
        refuses(moved)
        tombstoned = [{**entry, "deleted": True} if entry["path"] == "plan.md" else entry for entry in base]
        refuses(tombstoned)


def test_the_revision_id_is_derived_from_the_sealed_bytes(site: Site) -> None:
    """producer-kill-check: return a random or caller-supplied revision id."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)

        result = _seal(owner, grant)

        manifest = _manifest(site, grant)
        assert (
            result.revision_id
            == "rev-"
            + hashlib.sha256(
                json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()[:32]
        )
        changed = json.loads(json.dumps(manifest))
        changed["entries"] = changed["entries"][:-1] or changed["entries"]
        assert derive_revision_id(changed) != result.revision_id


def test_seal_refuses_a_writer_generation_that_moved_after_the_view(site: Site) -> None:
    """producer-kill-check: drop the generation equality in `prepare_seal`.

    White-box on purpose (C0): the generation is the one input this build cannot
    advance through the public surface until publish exists, and a seal against a
    stale writer is exactly the case that must never produce a `SEALED` receipt.
    """
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        binding = owner._bindings[ids["workspace_id"]]
        binding.metadata["generation"] = ref(grant).generation + 1

        with pytest.raises(SupervisorError) as refused:
            _seal(owner, grant)

        assert refused.value.code == "STALE_GENERATION"
        assert _record(site, grant)["state"] == "STOPPING"
        assert not (_view_root(site, grant) / MANIFEST_NAME).exists()


# ---------------------------------------------------------------------------
# Owner settlement — when may a writer be released? (spec §2.1 release row)
# ---------------------------------------------------------------------------


def _set_state(site: Site, grant: GrantReply, state: str) -> None:
    """White-box: publish/REJECTED are E268's transitions, not this build's."""
    path = record_path(site, grant)
    record = json.loads(path.read_text())
    record["state"] = state
    path.write_text(json.dumps(record))


def test_a_sealed_view_still_holds_the_writer(site: Site) -> None:
    """producer-kill-check: treat SEALED as settled (an unpublishable candidate is stranded)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        _seal(owner, grant)

        with pytest.raises(SupervisorError) as refused:
            site.release(owner, ids, lease)

        assert refused.value.code == "WORKSPACE_BUSY"
        assert site.metadata(ids)["status"] == "OWNED"


def test_a_published_view_settles_the_owner(site: Site) -> None:
    """producer-kill-check: refuse settlement on any non-READ view, whatever its state."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        _seal(owner, grant)
        _set_state(site, grant, "PUBLISHED")

        assert site.release(owner, ids, lease) == {"released": True}
        assert site.metadata(ids)["status"] == "AVAILABLE"

        # A settled owner can be re-claimed, and the generation advances durably.
        again = ok(lambda: site.claim(owner, ids))
        assert site.metadata(ids)["generation"] == lease.generation + 1
        assert site.metadata(ids)["status"] == "OWNED"
        assert again.capability != lease.capability


def test_a_rejected_view_also_settles_the_owner(site: Site) -> None:
    """producer-kill-check: an allowlist that names only PUBLISHED."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        _set_state(site, grant, "REJECTED")

        assert site.release(owner, ids, lease) == {"released": True}
        assert site.metadata(ids)["status"] == "AVAILABLE"


@pytest.mark.parametrize("state", ["OPEN", "STOPPING", "UNKNOWN"])
def test_an_unsettled_view_keeps_the_writer(site: Site, state: str) -> None:
    """producer-kill-check: allow settlement while a view can still change or is unproven."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        _set_state(site, grant, state)

        with pytest.raises(SupervisorError) as refused:
            site.release(owner, ids, lease)

        assert refused.value.code == "WORKSPACE_BUSY"
        assert site.metadata(ids)["status"] == "OWNED"


# ---------------------------------------------------------------------------
# View base CAS — the wire's `base_revision` is enforced, not ignored
# ---------------------------------------------------------------------------


def test_create_view_refuses_a_named_base_that_is_not_current(site: Site) -> None:
    """producer-kill-check: drop the base_revision comparison (silent newer-bytes view).

    `Operation.CREATE_VIEW` carries `base_revision` (`protocol.py:102`); before
    this check the authority accepted the payload, ignored it, and built the view
    on whatever `current` happened to be — a caller asking for revision A could
    receive revision B with no error.
    """
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        stale = "rev-" + "0" * 32

        with pytest.raises(SupervisorError) as refused:
            owner.create_view(
                PEER,
                ACTOR,
                workspace_id=ids["workspace_id"],
                capability=lease.capability,
                purpose=ViewPurpose.PROJECT,
                access=Access.WRITE,
                candidate_scope=None,
                plan_ref=None,
                formal_evidence=False,
                deadline=until(),
                base_revision=stale,
            )

        assert refused.value.code == "STALE_REVISION"
        views = site.state / "workspaces" / ids["workspace_id"] / "views"
        assert list(views.iterdir()) == [], "a refused view still materialized bytes"


def test_create_view_accepts_the_current_base_and_binds_it(site: Site) -> None:
    """producer-kill-check: accept any well-formed id (comparison removed)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))

        grant = owner.create_view(
            PEER,
            ACTOR,
            workspace_id=ids["workspace_id"],
            capability=lease.capability,
            purpose=ViewPurpose.PROJECT,
            access=Access.WRITE,
            candidate_scope=None,
            plan_ref=None,
            formal_evidence=False,
            deadline=until(),
            base_revision=ids["revision_id"],
        )

        assert ref(grant).base_revision == ids["revision_id"]
        assert _record(site, grant)["state"] == "OPEN"


# ---------------------------------------------------------------------------
# CT106 — publish: intent, pointer, projection (E269 / SLICE3 STEP2)
#
# Classes: C1 composition-root (real authority, real views, real barrier, real
# filesystem), C3 for the canonical-domain refusals, C0 for the pure manifest
# reader. Every case names the rule and the producer it kills.
# ---------------------------------------------------------------------------


def _op() -> str:
    from uuid import uuid4

    return "op-" + uuid4().hex


def _publish(
    owner: WorkspaceAuthority,
    grant: GrantReply,
    sealed: SealResult,
    *,
    operation_id: str | None = None,
    deadline: float | None = None,
) -> Any:
    from fa.execution.publication import publish_view

    return publish_view(
        owner,
        PEER,
        ACTOR,
        view_ref=ref(grant),
        capability=grant.capability,
        sealed_manifest_id=sealed.sealed_manifest_id,
        expected_base_revision=ref(grant).base_revision,
        operation_id=_op() if operation_id is None else operation_id,
        deadline=until() if deadline is None else deadline,
    )


def _workspace(site: Site, ids: dict[str, str]) -> Path:
    return site.state / "workspaces" / ids["workspace_id"]


def _current(site: Site, ids: dict[str, str]) -> dict[str, Any]:
    value = json.loads((_workspace(site, ids) / "current.json").read_text())
    assert isinstance(value, dict)
    return value


def _intent(site: Site, ids: dict[str, str]) -> dict[str, Any] | None:
    path = _workspace(site, ids) / "intent.json"
    if not path.exists():
        return None
    value = json.loads(path.read_text())
    assert isinstance(value, dict)
    return value


def _state(site: Site, grant: GrantReply) -> str:
    return str(_record(site, grant)["state"])


def test_publish_commits_the_pointer_projects_and_returns_the_committed_receipt(site: Site) -> None:
    """producer-kill-check: remove publish_view -> materialize/commit (R1,R4,R6,R7,R8)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _view(owner, ids, lease)
        owner.write_file(
            PEER,
            ACTOR,
            view_ref=ref(grant),
            capability=grant.capability,
            path="added.txt",
            content="added by the view\n",
            expected_sha256=None,
            deadline=until(),
        )
        _stop(owner, grant)
        sealed = _seal(owner, grant)
        untouched_inode = (site.source / "dirty.txt").stat().st_ino

        result = _publish(owner, grant, sealed)

        derived = derive_revision_id(_manifest(site, grant))
        assert result.revision_id == derived
        assert result.tree_sha256 == sealed.tree_sha256
        assert result.projection_complete is True
        assert _current(site, ids) == {
            "schema_version": 1,
            "workspace_id": ids["workspace_id"],
            "generation": site.metadata(ids)["generation"],
            "revision_id": derived,
            "tree_sha256": sealed.tree_sha256,
        }
        assert (site.source / "added.txt").read_text() == "added by the view\n"
        # R7 skip-if-equal: an identical file is never rewritten (same inode),
        # which is what makes a resumed projection converge instead of churn.
        assert (site.source / "dirty.txt").stat().st_ino == untouched_inode
        base_tree = json.loads((site.revision(ids) / "tree.json").read_text())
        assert base_tree["revision_id"] == ids["revision_id"]  # revisions are immutable
        revision = _workspace(site, ids) / "revisions" / derived
        tree = json.loads((revision / "tree.json").read_text())
        assert tree["tree_sha256"] == sealed.tree_sha256
        assert {entry["path"] for entry in tree["entries"]} == {"dirty.txt", "untracked.txt", "added.txt"}
        assert all(entry["deleted"] is False for entry in tree["entries"])
        assert _intent(site, ids) is None
        assert _state(site, grant) == "PUBLISHED"
        # The wire contract, decoded by the same validator the dispatcher uses.
        from fa.execution.protocol import decode_reply, encode_json

        decode_reply(
            encode_json(
                {
                    "protocol_version": 1,
                    "request_id": result.operation_id.removeprefix("op-"),
                    "status": "OK",
                    "result": result.to_wire(),
                    "error": None,
                }
            ),
            operation=__import__("fa.execution.primitives", fromlist=["Operation"]).Operation.PUBLISH,
            request_id=result.operation_id.removeprefix("op-"),
        )


def test_publish_restores_logical_modes_instead_of_retention_modes(site: Site) -> None:
    """producer-kill-check: project retention modes (0600) instead of manifest modes (R7)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        target = _source_root(site, grant) / "untracked.txt"
        target.chmod(0o755)
        sealed = _seal(owner, grant)

        _publish(owner, grant, sealed)

        assert site.source.joinpath("untracked.txt").stat().st_mode & 0o777 == 0o755


def test_publish_removes_a_tombstoned_path_from_canonical(site: Site) -> None:
    """producer-kill-check: skip tombstones during projection (R7, spec §5)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        (_source_root(site, grant) / "untracked.txt").unlink()
        sealed = _seal(owner, grant)

        _publish(owner, grant, sealed)

        assert not (site.source / "untracked.txt").exists()
        derived = derive_revision_id(_manifest(site, grant))
        tree = json.loads((_workspace(site, ids) / "revisions" / derived / "tree.json").read_text())
        assert "untracked.txt" not in {entry["path"] for entry in tree["entries"]}


def test_publish_leaves_git_and_excluded_trees_byte_identical(site: Site) -> None:
    """producer-kill-check: traverse an excluded component while projecting (R7,R10)."""
    (site.source / ".fa" / "artifacts").mkdir(parents=True)
    (site.source / ".fa" / "artifacts" / "keep.txt").write_text("artifact\n")
    (site.source / ".venv").mkdir()
    (site.source / ".venv" / "sentinel").write_text("venv\n")
    before = {
        path: (site.source / path).read_bytes() for path in (".git/index", ".fa/artifacts/keep.txt", ".venv/sentinel")
    }
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _view(owner, ids, lease)
        owner.write_file(
            PEER,
            ACTOR,
            view_ref=ref(grant),
            capability=grant.capability,
            path="added.txt",
            content="x\n",
            expected_sha256=None,
            deadline=until(),
        )
        _stop(owner, grant)
        sealed = _seal(owner, grant)

        _publish(owner, grant, sealed)

        assert {path: (site.source / path).read_bytes() for path in before} == before


def test_publish_refuses_a_base_that_moved_after_the_view(site: Site) -> None:
    """producer-kill-check: drop the base-revision CAS in R1 (STALE_REVISION)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        sealed = _seal(owner, grant)
        current = _current(site, ids)

        with pytest.raises(SupervisorError) as refused:
            from fa.execution.publication import publish_view

            publish_view(
                owner,
                PEER,
                ACTOR,
                view_ref=ref(grant),
                capability=grant.capability,
                sealed_manifest_id=sealed.sealed_manifest_id,
                expected_base_revision="rev-" + "0" * 32,
                operation_id=_op(),
                deadline=until(),
            )

        assert refused.value.code == "STALE_REVISION"
        assert _current(site, ids) == current
        assert not (_workspace(site, ids) / "revisions" / sealed.revision_id).exists()


def test_publish_refuses_a_manifest_id_the_view_did_not_seal(site: Site) -> None:
    """producer-kill-check: drop the sealed_manifest_id binding in R1."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        _seal(owner, grant)

        with pytest.raises(SupervisorError) as refused:
            from fa.execution.publication import publish_view

            publish_view(
                owner,
                PEER,
                ACTOR,
                view_ref=ref(grant),
                capability=grant.capability,
                sealed_manifest_id="seal-" + "0" * 32,
                expected_base_revision=ref(grant).base_revision,
                operation_id=_op(),
                deadline=until(),
            )

        assert refused.value.code == "STALE_REVISION"
        assert _state(site, grant) == "SEALED"


def test_publish_refuses_an_open_view_and_a_wrong_capability(site: Site) -> None:
    """producer-kill-check: dispatch on anything but SEALED/PUBLISHED; drop the proof."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _project_view(owner, ids, lease)
        sealed = SealResult("seal-" + "0" * 32, "rev-" + "0" * 32, "0" * 64)

        with pytest.raises(SupervisorError) as open_view:
            _publish(owner, grant, sealed)
        assert open_view.value.code == "VIEW_CLOSED"

        stopped = _stopped(owner, ids, lease)
        sealed = _seal(owner, stopped)
        with pytest.raises(SupervisorError) as unauthorized:
            from fa.execution.publication import publish_view

            publish_view(
                owner,
                PEER,
                ACTOR,
                view_ref=ref(stopped),
                capability="0" * 64,
                sealed_manifest_id=sealed.sealed_manifest_id,
                expected_base_revision=ref(stopped).base_revision,
                operation_id=_op(),
                deadline=until(),
            )
        assert unauthorized.value.code == "UNAUTHORIZED"


def test_publish_refuses_a_manifest_whose_digest_disagrees_with_its_bytes(site: Site) -> None:
    """producer-kill-check: skip the seal validator when re-reading the manifest (R2)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        sealed = _seal(owner, grant)
        manifest = _manifest(site, grant)
        manifest["entries"][0]["sha256"] = "0" * 64
        (_view_root(site, grant) / MANIFEST_NAME).write_text(json.dumps(manifest))

        with pytest.raises(SupervisorError) as refused:
            _publish(owner, grant, sealed)

        assert refused.value.code == "CORRUPT_STATE"
        assert _current(site, ids)["revision_id"] == ids["revision_id"]
        assert not (_workspace(site, ids) / "revisions" / sealed.revision_id).exists()


def test_publish_settles_the_owner_and_a_reclaim_advances_generation(site: Site) -> None:
    """producer-kill-check: write any state but PUBLISHED on completion (R8, E268 D1)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        sealed = _seal(owner, grant)
        _publish(owner, grant, sealed)

        assert site.release(owner, ids, lease) == {"released": True}
        assert site.metadata(ids)["status"] == "AVAILABLE"

        again = ok(lambda: site.claim(owner, ids))
        assert site.metadata(ids)["generation"] == lease.generation + 1
        assert again.capability != lease.capability


def test_publish_then_release_is_restart_clean_and_publish_without_release_is_not(site: Site) -> None:
    """producer-kill-check: quarantine a settled workspace / keep an owned one usable (R13)."""
    (site.roots / "second").mkdir()
    (site.roots / "second" / "file.txt").write_text("second\n")
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        sealed = _seal(owner, grant)
        _publish(owner, grant, sealed)
        assert site.release(owner, ids, lease) == {"released": True}

        ids2 = ok(lambda: site.register(owner, "second"))
        lease2 = ok(lambda: site.claim(owner, ids2))
        grant2 = _stopped(owner, ids2, lease2)
        sealed2 = _seal(owner, grant2)
        _publish(owner, grant2, sealed2)

    # Released: the published workspace survives a restart and stays reclaimable.
    with site.owner() as reopened:
        assert site.metadata(ids)["status"] == "AVAILABLE"
        assert _state(site, grant) == "PUBLISHED"
        assert _current(site, ids)["revision_id"] == derive_revision_id(_manifest(site, grant))
        assert ok(lambda: site.claim(reopened, ids)).generation == lease.generation + 1
    # Published but still owned: STEP4's limit, recorded rather than hidden.
    with site.owner() as reopened:
        assert site.metadata(ids2)["status"] == "QUARANTINED"


def test_publish_is_idempotent_and_replay_uses_the_callers_operation_id(site: Site) -> None:
    """producer-kill-check: drop the PUBLISHED replay branch (R9) — a retry would re-commit."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        sealed = _seal(owner, grant)
        first = _publish(owner, grant, sealed)
        current = _current(site, ids)

        second = _publish(owner, grant, sealed)

        assert (second.revision_id, second.tree_sha256) == (first.revision_id, first.tree_sha256)
        assert second.operation_id != first.operation_id
        assert _current(site, ids) == current
        assert _intent(site, ids) is None
        assert _state(site, grant) == "PUBLISHED"


def test_publish_refuses_to_start_on_top_of_a_foreign_intent(site: Site) -> None:
    """producer-kill-check: ignore an existing intent (a second attempt would overwrite it)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        sealed = _seal(owner, grant)
        planted = {
            "schema_version": 1,
            "kind": "REVISION",
            "operation_id": _op(),
            "workspace_id": ids["workspace_id"],
            "generation": site.metadata(ids)["generation"],
            "base_revision": ids["revision_id"],
            "next_revision": sealed.revision_id,
            "tree_sha256": sealed.tree_sha256,
            "phase": "PREPARED",
            "target_relative": None,
            "old_sha256": None,
            "new_sha256": None,
            "created_directories": [],
            "view_ref": ref(grant).to_dict(),
        }
        planted_path = _workspace(site, ids) / "intent.json"
        planted_path.write_text(json.dumps(planted))
        planted_path.chmod(0o600)  # `_private` refuses a world-readable control artifact
        current = _current(site, ids)

        with pytest.raises(SupervisorError) as refused:
            _publish(owner, grant, sealed)

        assert refused.value.code == "WORKSPACE_BUSY"
        assert _current(site, ids) == current


def test_a_projection_failure_after_the_pointer_is_durability_unknown_and_never_a_receipt(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: report success, roll back, or stay usable after a partial projection (R13)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _view(owner, ids, lease)
        owner.write_file(
            PEER,
            ACTOR,
            view_ref=ref(grant),
            capability=grant.capability,
            path="added.txt",
            content="added\n",
            expected_sha256=None,
            deadline=until(),
        )
        _stop(owner, grant)
        sealed = _seal(owner, grant)
        real_replace = os.replace

        def exploding(source: Any, destination: Any = None, **kwargs: Any) -> None:
            if isinstance(source, str) and source.endswith(".publish"):
                raise OSError(5, "injected projection failure")
            real_replace(source, destination, **kwargs)

        monkeypatch.setattr(workspace_module.os, "replace", exploding)

        with pytest.raises(SupervisorError) as refused:
            _publish(owner, grant, sealed)

        assert refused.value.code == "DURABILITY_UNKNOWN"
        # The pointer DID move: `current.json` is the discriminator, not the phase.
        assert _current(site, ids)["revision_id"] == sealed.revision_id
        assert _state(site, grant) == "SEALED"
        intent = _intent(site, ids)
        assert intent is not None and intent["phase"] == "PROJECTING"
        assert not (site.source / "added.txt").exists()
        # No further work is accepted from an authority that cannot prove its state.
        with pytest.raises(SupervisorError) as poisoned:
            site.release(owner, ids, lease)
        assert poisoned.value.code == "CORRUPT_STATE"


def test_publish_refuses_canonical_drift_before_any_write(site: Site) -> None:
    """producer-kill-check: drop the `_unchanged` pre-flight (D4) — stray bytes would publish."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        sealed = _seal(owner, grant)
        (site.source / "stray.txt").write_text("written behind the authority's back\n")
        current = _current(site, ids)

        with pytest.raises(SupervisorError) as refused:
            _publish(owner, grant, sealed)

        assert refused.value.code == "CORRUPT_STATE"
        assert _current(site, ids) == current
        assert not (_workspace(site, ids) / "revisions" / sealed.revision_id).exists()
        with pytest.raises(SupervisorError) as poisoned:
            site.release(owner, ids, lease)
        assert poisoned.value.code == "CORRUPT_STATE"


def test_publish_refuses_a_canonical_root_it_could_not_project_into(site: Site) -> None:
    """producer-kill-check: drop the mode branch of the Q81 no-write probe."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        sealed = _seal(owner, grant)
        current = _current(site, ids)
        before = sorted(path.name for path in site.source.iterdir())
        site.source.chmod(0o555)
        try:
            with pytest.raises(SupervisorError) as refused:
                _publish(owner, grant, sealed)
        finally:
            site.source.chmod(0o755)

        assert refused.value.code == "PATH_DENIED"
        assert _current(site, ids) == current
        assert sorted(path.name for path in site.source.iterdir()) == before  # the probe wrote nothing


def test_publish_refuses_a_read_only_mount_before_any_write(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    """producer-kill-check: drop the read-only-mount branch of the Q81 probe.

    The mount flag cannot be manufactured in a writable sandbox; the kernel fact
    is doubled at its seam and disclosed, like the cgroup observer (E266 pattern).
    """
    from types import SimpleNamespace

    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        sealed = _seal(owner, grant)
        monkeypatch.setattr(os, "fstatvfs", lambda _fd: SimpleNamespace(f_flag=os.ST_RDONLY))

        with pytest.raises(SupervisorError) as refused:
            _publish(owner, grant, sealed)

        monkeypatch.undo()
        assert refused.value.code == "PATH_DENIED"
        assert _current(site, ids)["revision_id"] == ids["revision_id"]


def test_publish_refuses_source_bytes_that_moved_after_the_barrier(site: Site) -> None:
    """producer-kill-check: skip the copied-tree-vs-manifest comparison (R4/R12)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        sealed = _seal(owner, grant)
        (_source_root(site, grant) / "untracked.txt").write_text("moved after the barrier\n")

        with pytest.raises(SupervisorError) as refused:
            _publish(owner, grant, sealed)

        assert refused.value.code == "CORRUPT_STATE"
        assert _current(site, ids)["revision_id"] == ids["revision_id"]
        assert not (_workspace(site, ids) / "revisions" / sealed.revision_id).exists()


def test_publish_refuses_a_symlink_standing_where_a_file_must_go(site: Site) -> None:
    """producer-kill-check: rewrite through/replace a link instead of refusing (D7, C3)."""
    (site.source / "link").symlink_to("untracked.txt")
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        replacement = _source_root(site, grant) / "link"
        replacement.unlink()
        replacement.write_text("now a regular file\n")
        sealed = _seal(owner, grant)

        with pytest.raises(SupervisorError) as refused:
            _publish(owner, grant, sealed)

        assert refused.value.code == "PATH_DENIED"
        assert (site.source / "link").is_symlink()
        assert _current(site, ids)["revision_id"] == ids["revision_id"]


def test_pinned_readers_keep_the_old_revision_across_publish(site: Site) -> None:
    """producer-kill-check: mutate a pinned revision's bytes while publishing (R7,R10)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        old = ok(
            lambda: owner.pin_reader(
                PEER,
                ACTOR,
                workspace_id=ids["workspace_id"],
                revision_id=ids["revision_id"],
                plan_ref=None,
                formal_evidence=False,
                deadline=until(),
            )
        )
        grant = _view(owner, ids, lease)
        original = hashlib.sha256((site.source / "untracked.txt").read_bytes()).hexdigest()
        owner.write_file(
            PEER,
            ACTOR,
            view_ref=ref(grant),
            capability=grant.capability,
            path="untracked.txt",
            content="changed by the view\n",
            expected_sha256=original,
            deadline=until(),
        )
        _stop(owner, grant)
        sealed = _seal(owner, grant)

        _publish(owner, grant, sealed)

        assert (site.source / "untracked.txt").read_text() == "changed by the view\n"
        assert (
            owner.read_file(
                PEER,
                ACTOR,
                view_ref=ref(old),
                capability=old.capability,
                path="untracked.txt",
                offset_bytes=0,
                max_bytes=64,
                deadline=until(),
            )["content"]
            == "untracked"
        )
        fresh = ok(
            lambda: owner.pin_reader(
                PEER,
                ACTOR,
                workspace_id=ids["workspace_id"],
                revision_id=sealed.revision_id,
                plan_ref=None,
                formal_evidence=False,
                deadline=until(),
            )
        )
        assert (
            owner.read_file(
                PEER,
                ACTOR,
                view_ref=ref(fresh),
                capability=fresh.capability,
                path="untracked.txt",
                offset_bytes=0,
                max_bytes=64,
                deadline=until(),
            )["content"]
            == "changed by the view\n"
        )


def test_registration_writes_the_five_key_pointer_and_load_refuses_a_foreign_one(site: Site) -> None:
    """producer-kill-check: keep the three-key shape / drop the _load identity check (Q80)."""
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        assert set(_current(site, ids)) == {
            "schema_version",
            "workspace_id",
            "generation",
            "revision_id",
            "tree_sha256",
        }
        assert _current(site, ids)["workspace_id"] == ids["workspace_id"]

    path = _workspace(site, ids) / "current.json"
    current = json.loads(path.read_text())
    current["workspace_id"] = "ws-" + "0" * 32
    path.write_text(json.dumps(current))
    with pytest.raises(SupervisorError) as refused, site.owner():
        pytest.fail("a pointer naming another workspace was accepted")
    assert refused.value.code == "CORRUPT_STATE"


def test_load_refuses_a_pointer_from_a_future_epoch_but_accepts_an_older_one(site: Site) -> None:
    """producer-kill-check: tolerate a generation ahead of its owner metadata (Q80)."""
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))

    path = _workspace(site, ids) / "current.json"
    current = json.loads(path.read_text())
    current["generation"] = current["generation"] + 1
    path.write_text(json.dumps(current))
    with pytest.raises(SupervisorError) as refused, site.owner():
        pytest.fail("a pointer from a future epoch was accepted")
    assert refused.value.code == "CORRUPT_STATE"

    current["generation"] = 1  # older than the metadata epoch is legal after release + re-claim
    path.write_text(json.dumps(current))
    with site.owner() as reopened:
        assert _current(site, ids)["generation"] == 1
        assert site.metadata(ids)["status"] == "AVAILABLE"
        del reopened


def test_publish_refuses_a_stopped_but_unsealed_view(site: Site) -> None:
    """producer-kill-check: accept STOPPING as publishable (seal is the only SEALED edge)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        assert _state(site, grant) == "STOPPING"

        with pytest.raises(SupervisorError) as refused:
            _publish(owner, grant, SealResult("seal-" + "0" * 32, "rev-" + "0" * 32, "0" * 64))

        assert refused.value.code == "VIEW_CLOSED"
        assert _state(site, grant) == "STOPPING"


def test_publish_refuses_a_writer_generation_that_moved_after_the_view(site: Site) -> None:
    """producer-kill-check: drop the generation equality in R1 (STALE_GENERATION)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        sealed = _seal(owner, grant)
        owner._bindings[ids["workspace_id"]].metadata["generation"] += 1  # white-box epoch move

        with pytest.raises(SupervisorError) as refused:
            _publish(owner, grant, sealed)

        assert refused.value.code == "STALE_GENERATION"
        assert _state(site, grant) == "SEALED"


def test_the_projection_verifier_refuses_a_tree_that_differs_from_the_manifest(site: Site) -> None:
    """producer-kill-check: make `_verify_projection` a no-op (R8's completion proof)."""

    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        sealed = _seal(owner, grant)
        _publish(owner, grant, sealed)
        inputs = owner.prepare_publish(
            PEER,
            ACTOR,
            view_ref=ref(grant),
            capability=grant.capability,
            sealed_manifest_id=sealed.sealed_manifest_id,
            expected_base_revision=ref(grant).base_revision,
            operation_id=_op(),
            manifest_reader=publication_module._read_sealed_manifest,
            deadline=until(),
        )
        ghost = {
            "path": "ghost.txt",
            "type": "file",
            "mode": 0o644,
            "size": 1,
            "sha256": "0" * 64,
            "deleted": False,
            "link_target": None,
        }

        with pytest.raises(SupervisorError) as refused:
            owner._verify_projection(
                owner._binding(ids["workspace_id"]),
                (*inputs.entries, ghost),
                inputs.tree_sha256,
                until(),
            )

        assert refused.value.code == "CORRUPT_STATE"


def test_commit_refuses_a_pointer_that_moved_between_prepare_and_commit(site: Site) -> None:
    """producer-kill-check: drop the durable CAS read in R6 — a newer pointer would be overwritten."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        sealed = _seal(owner, grant)
        inputs = owner.prepare_publish(
            PEER,
            ACTOR,
            view_ref=ref(grant),
            capability=grant.capability,
            sealed_manifest_id=sealed.sealed_manifest_id,
            expected_base_revision=ref(grant).base_revision,
            operation_id=_op(),
            manifest_reader=publication_module._read_sealed_manifest,
            deadline=until(),
        )
        owner.materialize_publication(PEER, ACTOR, capability=grant.capability, inputs=inputs, deadline=until())

        moved = _current(site, ids)
        moved["revision_id"] = "rev-" + "1" * 32
        path = _workspace(site, ids) / "current.json"
        path.write_text(json.dumps(moved))
        path.chmod(0o600)

        with pytest.raises(SupervisorError) as refused:
            owner.commit_revision_current(PEER, ACTOR, capability=grant.capability, inputs=inputs, deadline=until())

        assert refused.value.code == "STALE_REVISION"
        assert _current(site, ids)["revision_id"] == "rev-" + "1" * 32


def test_publish_refuses_a_valid_manifest_that_belongs_to_another_view(site: Site) -> None:
    """producer-kill-check: drop the manifest-vs-record cross-check in R2 (C3 substitution).

    Two views of the same revision can hold byte-identical trees, so a manifest
    stolen from a sibling view would pass every byte comparison. Only the
    identity fields (`view_id`, `workspace_id`, `generation`, `base_revision`)
    tie it to this grant — that is the whole point of the cross-check.
    """
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        first = _stopped(owner, ids, lease)
        first_sealed = _seal(owner, first)
        second = _stopped(owner, ids, lease)
        second_sealed = _seal(owner, second)
        assert first_sealed.revision_id != second_sealed.revision_id

        stolen = (_view_root(site, first) / MANIFEST_NAME).read_bytes()
        (_view_root(site, second) / MANIFEST_NAME).write_bytes(stolen)

        with pytest.raises(SupervisorError) as refused:
            _publish(owner, second, second_sealed)

        assert refused.value.code == "CORRUPT_STATE"
        assert _current(site, ids)["revision_id"] == ids["revision_id"]
        assert _state(site, second) == "SEALED"


# ---------------------------------------------------------------------------
# E271 — prepare_bundle: the trusted bounded renderer and its private store
#
# C0 for the pure renderer (literal fixtures), C1 for storage through the real
# authority, C3 for the metadata-smuggling and traversal refusals.
# ---------------------------------------------------------------------------

_ROADMAP_PROSE = "## Intent\n\nShip the thing.\n\n## Out-of-scope\n\nEverything else.\n"
_INCREMENT_PROSE = "## SLICE1: first\n\nSteps.\n\n## SLICE2: second\n\nSteps.\n"


def _bundle_digest(files: dict[str, bytes]) -> str:
    canonical = json.dumps(
        [[path, hashlib.sha256(files[path]).hexdigest()] for path in sorted(files)],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def test_the_renderer_emits_exactly_three_files_with_controller_metadata() -> None:
    """producer-kill-check: let the caller own any frontmatter field (spec §7.1)."""
    from fa.execution.publication import bundle_paths, render_bundle

    files = render_bundle("demo-project", "first-increment", _ROADMAP_PROSE, _INCREMENT_PROSE, created="2026-10-22")

    assert sorted(files) == sorted(bundle_paths("demo-project", "first-increment"))
    roadmap = files["worklogs/demo-project/roadmap.md"].decode()
    increment = files["worklogs/demo-project/increments/increment-01-first-increment.md"].decode()
    ledger = files["worklogs/demo-project/ledger.md"].decode()
    assert roadmap.startswith(
        "---\nRoadmap-ID: RM-demo-project\nslug: demo-project\ncreated: 2026-10-22\n"
        "status: IN PROGRESS\nactive-increment: I01\n---\n"
    )
    assert "| I01 | [first-increment](worklogs/demo-project/increments/increment-01-first-increment.md) |" in roadmap
    assert roadmap.endswith(_ROADMAP_PROSE)
    assert increment.startswith(
        "---\nIncrement-ID: RM-demo-project-I01\nRoadmap-ID: RM-demo-project\nslug: first-increment\n"
        "status: IN PROGRESS\nslices: 2\nshipped: —\n---\n"
    )
    assert ledger == "# Ledger — decision and evidence log\n\nFixed heading only; entries are appended by the run.\n"


def test_the_renderer_refuses_metadata_the_caller_disguised_outside_a_fence() -> None:
    """producer-kill-check: drop the disguised-metadata scan (C3)."""
    from fa.execution.publication import render_bundle

    for prose, kind in (
        ("## Intent\n\nRoadmap-ID: RM-evil\n\n## Out-of-scope\n\nnone\n", "roadmap"),
        ("## SLICE1: a\n\nslices: 99\n", "increment"),
        ("## SLICE1: a\n\n---\nIncrement-ID: X\n", "increment"),
    ):
        roadmap_text, increment_text = (_ROADMAP_PROSE, prose) if kind == "increment" else (prose, _INCREMENT_PROSE)
        with pytest.raises(SupervisorError) as refused:
            render_bundle("demo", "inc", roadmap_text, increment_text, created="2026-10-22")
        assert refused.value.code == "INPUT_POLICY"

    # The same words inside a fence are inert prose, not metadata.
    fenced = "## SLICE1: a\n\n```\nstatus: IN PROGRESS\n```\n"
    assert render_bundle("demo", "inc", _ROADMAP_PROSE, fenced, created="2026-10-22")


def test_the_renderer_refuses_a_roadmap_body_with_the_wrong_sections() -> None:
    """producer-kill-check: drop the exact-heading rule (a model could add sections)."""
    from fa.execution.publication import render_bundle

    for prose in (
        "## Intent\n\nonly one section\n",
        "## Out-of-scope\n\nthen\n\n## Intent\n\nreversed\n",
        "## Intent\n\nx\n\n## Out-of-scope\n\ny\n\n## Extra\n\nz\n",
    ):
        with pytest.raises(SupervisorError) as refused:
            render_bundle("demo", "inc", prose, _INCREMENT_PROSE, created="2026-10-22")
        assert refused.value.code == "INPUT_POLICY"


def test_the_renderer_refuses_non_contiguous_or_absent_slices() -> None:
    """producer-kill-check: drop the slice-contiguity rule (the count would lie)."""
    from fa.execution.publication import render_bundle

    for prose in ("no slices here\n", "## SLICE2: a\n\nx\n", "## SLICE1: a\n\n## SLICE3: c\n"):
        with pytest.raises(SupervisorError) as refused:
            render_bundle("demo", "inc", _ROADMAP_PROSE, prose, created="2026-10-22")
        assert refused.value.code == "INPUT_POLICY"


def test_the_renderer_refuses_a_bad_slug_or_date() -> None:
    """producer-kill-check: skip slug/date grammar (a path component would be caller-shaped)."""
    from fa.execution.publication import render_bundle

    for slug, created in (
        ("Demo", "2026-10-22"),
        ("demo-", "2026-10-22"),
        ("demo", "22-10-2026"),
        ("d" * 49, "2026-10-22"),
    ):
        with pytest.raises(SupervisorError) as refused:
            render_bundle(slug, "inc", _ROADMAP_PROSE, _INCREMENT_PROSE, created=created)
        assert refused.value.code == "INPUT_POLICY"


def _prepare_bundle(owner: WorkspaceAuthority, ids: dict[str, str], lease: GrantReply, **kwargs: Any) -> Any:
    from fa.execution.publication import prepare_bundle

    return prepare_bundle(
        owner,
        PEER,
        ACTOR,
        capability=kwargs.pop("capability", lease.capability),
        project_slug=kwargs.pop("project_slug", "demo-project"),
        increment_slug=kwargs.pop("increment_slug", "first-increment"),
        roadmap_text=kwargs.pop("roadmap_text", _ROADMAP_PROSE),
        increment_text=kwargs.pop("increment_text", _INCREMENT_PROSE),
        expected_base_revision=kwargs.pop("expected_base_revision", ids["revision_id"]),
        operation_id=kwargs.pop("operation_id", _op()),
        created=kwargs.pop("created", "2026-10-22"),
        deadline=until(),
    )


def test_prepare_bundle_stores_a_private_bundle_bound_to_its_base(site: Site) -> None:
    """producer-kill-check: store nothing / bind nothing (C1 over the real authority)."""
    from fa.execution.publication import bundle_paths

    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))

        result = _prepare_bundle(owner, ids, lease)

        stored = _workspace(site, ids) / "bundles" / result.validated_bundle_id
        manifest = json.loads((stored / "bundle.json").read_text())
        assert manifest["base_revision"] == ids["revision_id"]
        assert manifest["workspace_id"] == ids["workspace_id"]
        assert manifest["kind"] == "BUNDLE"
        assert [entry["path"] for entry in manifest["files"]] == sorted(bundle_paths("demo-project", "first-increment"))
        for entry in manifest["files"]:
            raw = (stored / entry["path"]).read_bytes()
            assert len(raw) == entry["size"]
            assert hashlib.sha256(raw).hexdigest() == entry["sha256"]
        assert result.bundle_sha256 == _bundle_digest(
            {entry["path"]: (stored / entry["path"]).read_bytes() for entry in manifest["files"]}
        )
        # Nothing was installed: a bundle is a pre-install object.
        assert not (site.source / "worklogs").exists()


def test_prepare_bundle_is_deterministic_and_refuses_a_stale_base(site: Site) -> None:
    """producer-kill-check: drop the base CAS (a bundle could be installed on another revision)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        first = _prepare_bundle(owner, ids, lease)
        second = _prepare_bundle(owner, ids, lease)

        assert first.bundle_sha256 == second.bundle_sha256  # same bytes, same digest
        assert first.validated_bundle_id != second.validated_bundle_id  # a fresh private id each time

        with pytest.raises(SupervisorError) as refused:
            _prepare_bundle(owner, ids, lease, expected_base_revision="rev-" + "0" * 32)

        assert refused.value.code == "STALE_REVISION"


def test_prepare_bundle_requires_the_owner_grant_and_no_open_view(site: Site) -> None:
    """producer-kill-check: accept a view capability / ignore an unsettled view."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        with pytest.raises(SupervisorError) as unauthorized:
            _prepare_bundle(owner, ids, lease, capability="0" * 64)
        assert unauthorized.value.code == "UNAUTHORIZED"

        _view(owner, ids, lease)
        with pytest.raises(SupervisorError) as busy:
            _prepare_bundle(owner, ids, lease)
        assert busy.value.code == "WORKSPACE_BUSY"


def test_store_bundle_refuses_a_path_that_escapes_the_bundle(site: Site) -> None:
    """producer-kill-check: drop the dot/`..` component guard (C3 traversal)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        for path in ("../escape.txt", "worklogs/./x.md", "worklogs/.hidden/x.md"):
            with pytest.raises(SupervisorError) as refused:
                owner.store_bundle(
                    PEER,
                    ACTOR,
                    capability=lease.capability,
                    project_slug="demo",
                    increment_slug="inc",
                    files={path: b"x"},
                    expected_base_revision=ids["revision_id"],
                    operation_id=_op(),
                    deadline=until(),
                )
            assert refused.value.code == "INPUT_POLICY"
        assert not (site.source / "escape.txt").exists()


# ---------------------------------------------------------------------------
# E272 — replay must survive a real manifest (F1) and crash debris (F2)
#
# Every pre-E272 publish test used a tree with no tombstone, no symlink and no
# plan, so R9's replay was only ever exercised against a degenerate manifest.
# Making the manifest representative is what exposed F1.
# ---------------------------------------------------------------------------


def test_replay_returns_the_receipt_for_a_manifest_with_a_tombstone(site: Site) -> None:
    """producer-kill-check: load base entries only for a SEALED view (F1)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        (_source_root(site, grant) / "untracked.txt").unlink()
        sealed = _seal(owner, grant)
        assert any(entry["deleted"] for entry in _manifest(site, grant)["entries"])

        first = _publish(owner, grant, sealed)
        second = _publish(owner, grant, sealed)

        assert (second.revision_id, second.tree_sha256) == (first.revision_id, first.tree_sha256)
        assert second.operation_id != first.operation_id
        assert not (site.source / "untracked.txt").exists()


def test_replay_returns_the_receipt_for_a_tree_that_contains_a_symlink(site: Site) -> None:
    """producer-kill-check: an empty base makes every symlink entry unpublishable (F1)."""
    (site.source / "linked.txt").symlink_to("untracked.txt")
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        sealed = _seal(owner, grant)
        assert any(entry["type"] == "symlink" for entry in _manifest(site, grant)["entries"])

        first = _publish(owner, grant, sealed)
        second = _publish(owner, grant, sealed)

        assert second.revision_id == first.revision_id
        assert (site.source / "linked.txt").is_symlink()


def test_replay_returns_the_receipt_for_a_plan_bound_view(site: Site) -> None:
    """producer-kill-check: an empty base makes the plan boundary refuse the plan entry (F1)."""
    (site.source / "plan.md").write_text("# admitted plan\n")
    admitted = read_plan_snapshot(site.source, Path("plan.md")).ref
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease, plan_ref=admitted)
        sealed = _seal(owner, grant)

        first = _publish(owner, grant, sealed)
        second = _publish(owner, grant, sealed)

        assert second.revision_id == first.revision_id
        assert (site.source / "plan.md").read_text() == "# admitted plan\n"


def test_projection_temporaries_never_exist_inside_the_canonical_tree(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: put the projection temporary in the user's tree (F2)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        # Projection then has to rewrite this file, which is where a temporary
        # would be created; an unchanged file takes the fast path instead.
        (_source_root(site, grant) / "untracked.txt").write_text("changed after the barrier\n")
        sealed = _seal(owner, grant)
        scratch = site.source / ".fa" / "publish-tmp"
        seen: list[dict[str, Any]] = []
        real_replace = os.replace

        def recording(source: Any, destination: Any = None, **kwargs: Any) -> None:
            if isinstance(source, str) and source.endswith(workspace_module._TEMPORARY_SUFFIX):
                seen.append(dict(kwargs))
                # At the exact instant the temporary exists, it must be nowhere
                # the project -- or any later `_unchanged` walk -- can see it.
                for path in site.source.rglob("*"):
                    assert ".fa" in path.parts or not path.name.endswith(workspace_module._TEMPORARY_SUFFIX), path
                assert Path(os.readlink(f"/proc/self/fd/{kwargs['src_dir_fd']}")) == scratch
                assert kwargs["src_dir_fd"] != kwargs["dst_dir_fd"]
            real_replace(source, destination, **kwargs)

        monkeypatch.setattr(workspace_module.os, "replace", recording)
        _publish(owner, grant, sealed)
        monkeypatch.undo()

    assert seen, "the fixture never rewrote a projected file"
    assert (site.source / "untracked.txt").read_text() == "changed after the barrier\n"


def test_publish_sweeps_abandoned_projection_temporaries(site: Site) -> None:
    """producer-kill-check: leave abandoned temporaries to accumulate forever (F2)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped(owner, ids, lease)
        sealed = _seal(owner, grant)
        scratch = site.source / ".fa" / "publish-tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        abandoned = scratch / ".stale.txt.deadbeef.publish"
        abandoned.write_text("left behind by a killed process")
        abandoned.chmod(0o600)
        # Debris the sweep does not recognise is not its business to delete.
        foreign = scratch / "keep.txt"
        foreign.write_text("not ours\n")

        result = _publish(owner, grant, sealed)

        assert result.revision_id.startswith("rev-")
        assert not abandoned.exists()
        assert foreign.exists()


def test_the_renderer_treats_tilde_and_indented_code_as_code_not_prose() -> None:
    """producer-kill-check: hand-rolled fence scanning instead of MarkdownIt (F4)."""
    from fa.execution.publication import render_bundle

    # `~~~` is a fence in CommonMark, so the metadata-looking line is code.
    tilde = "## SLICE1: a\n\n~~~\nstatus: IN PROGRESS\n~~~\n"
    assert render_bundle("demo", "inc", _ROADMAP_PROSE, tilde, created="2026-10-22")

    # So is a 4-space indented block.
    indented = "## SLICE1: a\n\n    status: IN PROGRESS\n"
    assert render_bundle("demo", "inc", _ROADMAP_PROSE, indented, created="2026-10-22")

    # A heading inside a fence is not a slice either.
    fenced_heading = "## SLICE1: a\n\n```\n## SLICE2: fake\n```\n"
    rendered = render_bundle("demo", "inc", _ROADMAP_PROSE, fenced_heading, created="2026-10-22")
    assert b"slices: 1\n" in rendered["worklogs/demo/increments/increment-01-inc.md"]

    # Outside any code block it is still metadata smuggling, and still refused.
    for prose in ("## SLICE1: a\n\nstatus: IN PROGRESS\n", "## SLICE1: a\n\n  shipped: yes\n"):
        with pytest.raises(SupervisorError) as refused:
            render_bundle("demo", "inc", _ROADMAP_PROSE, prose, created="2026-10-22")
        assert refused.value.code == "INPUT_POLICY"


def test_the_increment_header_counts_the_slices_it_rendered() -> None:
    """Pins the metadata line; `max` was equivalent only because §7.1 forces contiguity (F5)."""
    from fa.execution.publication import render_bundle

    rendered = render_bundle("demo", "inc", _ROADMAP_PROSE, _INCREMENT_PROSE, created="2026-10-22")
    body = rendered["worklogs/demo/increments/increment-01-inc.md"].decode()
    assert [line for line in body.splitlines() if line.startswith("slices:")] == ["slices: 2"]


def test_the_bundle_manifest_records_the_mode_install_will_apply(site: Site) -> None:
    """producer-kill-check: omit the mode (install would freeze a staging 0600) (F3)."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        result = _prepare_bundle(owner, ids, lease)

        stored = _workspace(site, ids) / "bundles" / result.validated_bundle_id
        manifest = json.loads((stored / "bundle.json").read_text())
        assert manifest["directory_mode"] == 0o755
        assert {entry["mode"] for entry in manifest["files"]} == {0o644}
        for entry in manifest["files"]:
            assert (stored / entry["path"]).stat().st_mode & 0o777 == 0o644


def test_owner_only_finds_the_binding_whose_grant_matches(site: Site) -> None:
    """producer-kill-check: select by principal/actor, then compare the capability (F7)."""
    second = site.roots / "second"
    second.mkdir()
    (second / "file.txt").write_text("second\n")
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        ids2 = ok(lambda: site.register(owner, "second"))
        lease2 = ok(lambda: site.claim(owner, ids2))
        assert lease.capability != lease2.capability

        # Two OWNED bindings share principal and actor; only the grant differs.
        result = _prepare_bundle(owner, ids2, lease2)

        stored = _workspace(site, ids2) / "bundles" / result.validated_bundle_id
        assert json.loads((stored / "bundle.json").read_text())["workspace_id"] == ids2["workspace_id"]
        assert not (_workspace(site, ids) / "bundles").exists()


# ---------------------------------------------------------------------------
# STEP3 unit B — `install_project`: BOOTSTRAP a bundle in place (Q82 (B))
#
# §5.1's BOOTSTRAP order is the opposite of publish's: the directory appears
# first (irreversible), then the revision and pointer describe it. Every case
# below therefore also asserts that a refusal wrote nothing.
# ---------------------------------------------------------------------------


def _install(
    owner: WorkspaceAuthority,
    ids: dict[str, str],
    lease: GrantReply,
    bundle: Any,
    *,
    project_slug: str = "demo-project",
    capability: str | None = None,
) -> Any:
    from fa.execution.publication import install_project

    return install_project(
        owner,
        PEER,
        ACTOR,
        capability=lease.capability if capability is None else capability,
        validated_bundle_id=bundle.validated_bundle_id,
        project_slug=project_slug,
        deadline=until(),
    )


def _bundle_root(site: Site, ids: dict[str, str], bundle: Any) -> Path:
    return _workspace(site, ids) / "bundles" / bundle.validated_bundle_id


def test_install_creates_the_project_commits_it_and_returns_the_wire_receipt(site: Site) -> None:
    """producer-kill-check: install writes the tree but never commits a revision."""
    import fastjsonschema

    from fa.execution.protocol import RESULTS, Operation

    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        bundle = _prepare_bundle(owner, ids, lease)

        result = _install(owner, ids, lease, bundle)

        root = site.source / "worklogs" / "demo-project"
        assert (root / "roadmap.md").read_text().startswith("---\nRoadmap-ID: RM-demo-project\n")
        assert (root / "ledger.md").exists()
        assert (root / "increments" / "increment-01-first-increment.md").exists()
        assert (root / "roadmap.md").stat().st_mode & 0o777 == 0o644
        assert root.stat().st_mode & 0o777 == 0o755
        assert root.joinpath("increments").stat().st_mode & 0o777 == 0o755

        current = _current(site, ids)
        assert current["revision_id"] == result.revision_id
        assert current["tree_sha256"] == result.tree_sha256
        tree = json.loads((_workspace(site, ids) / "revisions" / result.revision_id / "tree.json").read_text())
        assert result.tree_sha256 == hashlib.sha256(workspace_module._canonical(tree["entries"])).hexdigest()
        assert "worklogs/demo-project/roadmap.md" in {entry["path"] for entry in tree["entries"]}
        assert _intent(site, ids) is None
        # A bundle is retained, never consumed by the install.
        assert (_bundle_root(site, ids, bundle) / "bundle.json").exists()
        # The receipt is exactly the wire's `_COMMITTED`, not a private shape.
        fastjsonschema.validate(
            RESULTS[Operation.INSTALL_PROJECT],
            {
                "workspace_id": result.workspace_id,
                "revision_id": result.revision_id,
                "tree_sha256": result.tree_sha256,
                "operation_id": result.operation_id,
                "projection_complete": result.projection_complete,
            },
        )

    # A fresh authority must accept the committed revision as its baseline:
    # `_load` re-verifies the revision and `_unchanged` requires canonical bytes
    # to be exactly that revision, which is only true if install wrote both.
    with site.owner(view_profile=native_profile()) as reopened:
        assert site.register(reopened)["revision_id"] == result.revision_id


def test_install_refuses_an_existing_project_and_preserves_its_bytes(site: Site) -> None:
    """producer-kill-check: existence-check then ordinary rename (a silent overwrite)."""
    existing = site.source / "worklogs" / "demo-project"
    existing.mkdir(parents=True)
    (existing / "roadmap.md").write_text("someone else's roadmap\n")
    before = (existing / "roadmap.md").read_bytes()
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        bundle = _prepare_bundle(owner, ids, lease)
        base_revision = _current(site, ids)["revision_id"]

        with pytest.raises(SupervisorError) as refused:
            _install(owner, ids, lease, bundle)

        assert refused.value.code == "COLLISION"
        assert (existing / "roadmap.md").read_bytes() == before
        assert _current(site, ids)["revision_id"] == base_revision
        assert _intent(site, ids) is None


def test_install_never_overwrites_even_when_the_target_appears_after_the_check(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: rely on the pre-check instead of RENAME_NOREPLACE."""
    real_rename = workspace_module._rename_directory
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        bundle = _prepare_bundle(owner, ids, lease)
        base_revision = _current(site, ids)["revision_id"]

        def racing(source: int, name: str, destination: int, leaf: str) -> None:
            # An *empty* destination is the case an ordinary rename would silently
            # replace; only RENAME_NOREPLACE refuses it.
            os.mkdir(leaf, 0o700, dir_fd=destination)
            real_rename(source, name, destination, leaf)

        monkeypatch.setattr(workspace_module, "_rename_directory", racing)
        with pytest.raises(SupervisorError) as refused:
            _install(owner, ids, lease, bundle)
        monkeypatch.undo()

        assert refused.value.code == "COLLISION"
        installed = site.source / "worklogs" / "demo-project"
        assert installed.is_dir() and list(installed.iterdir()) == []
        assert _current(site, ids)["revision_id"] == base_revision
        assert _intent(site, ids) is None


def test_install_refuses_a_bundle_prepared_against_another_revision(site: Site) -> None:
    """producer-kill-check: drop the base-revision CAS on install."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        bundle = _prepare_bundle(owner, ids, lease)
        grant = _stopped(owner, ids, lease)
        _publish(owner, grant, _seal(owner, grant))
        assert _current(site, ids)["revision_id"] != ids["revision_id"]

        with pytest.raises(SupervisorError) as refused:
            _install(owner, ids, lease, bundle)

        assert refused.value.code == "STALE_REVISION"
        assert not (site.source / "worklogs").exists()


def test_install_refuses_another_workspaces_bundle_and_a_retargeted_slug(site: Site) -> None:
    """producer-kill-check: trust the caller's bundle id and slug (cross-project install)."""
    second = site.roots / "second"
    second.mkdir()
    (second / "file.txt").write_text("second\n")
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        ids2 = ok(lambda: site.register(owner, "second"))
        lease2 = ok(lambda: site.claim(owner, ids2))
        foreign = _prepare_bundle(owner, ids2, lease2)
        mine = _prepare_bundle(owner, ids, lease)

        # Bundles are per-workspace private storage, so an id that lives
        # elsewhere is simply not here: the refusal is the same closed code as
        # for any unknown id, and nothing about workspace 2's store leaks.
        with pytest.raises(SupervisorError) as absent:
            _install(owner, ids, lease, foreign)
        assert absent.value.code == "INPUT_POLICY"

        with pytest.raises(SupervisorError) as retargeted:
            _install(owner, ids, lease, mine, project_slug="someone-else")
        assert retargeted.value.code == "INPUT_POLICY"

        assert not (site.source / "worklogs").exists()

        # Defence in depth: a bundle directory copied into the wrong store is
        # refused by identity, not by luck of the lookup.
        import shutil

        shutil.copytree(_bundle_root(site, ids2, foreign), _bundle_root(site, ids, foreign))
        with pytest.raises(SupervisorError) as foreign_workspace:
            _install(owner, ids, lease, foreign)
        assert foreign_workspace.value.code == "UNAUTHORIZED"
        assert not (site.source / "worklogs").exists()


def test_install_refuses_a_live_view(site: Site) -> None:
    """producer-kill-check: install while a writer view is still unsettled."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        bundle = _prepare_bundle(owner, ids, lease)
        _view(owner, ids, lease)  # deliberately left open

        with pytest.raises(SupervisorError) as busy:
            _install(owner, ids, lease, bundle)

        assert busy.value.code == "WORKSPACE_BUSY"
        assert not (site.source / "worklogs").exists()


def test_install_refuses_a_missing_bundle_and_a_wrong_capability(site: Site) -> None:
    """producer-kill-check: install without the owner grant, or for an unknown id."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        bundle = _prepare_bundle(owner, ids, lease)

        with pytest.raises(SupervisorError) as absent:
            _install(owner, ids, lease, type("B", (), {"validated_bundle_id": "bundle-" + "0" * 32})())
        assert absent.value.code == "INPUT_POLICY"

        with pytest.raises(SupervisorError) as unauthorized:
            _install(owner, ids, lease, bundle, capability="0" * 64)
        assert unauthorized.value.code == "UNAUTHORIZED"
        assert not (site.source / "worklogs").exists()


def test_install_refuses_a_tampered_bundle_before_writing_anything(site: Site) -> None:
    """producer-kill-check: copy bundle bytes without proving them against the manifest."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        bundle = _prepare_bundle(owner, ids, lease)
        staged = _bundle_root(site, ids, bundle) / "worklogs" / "demo-project" / "roadmap.md"
        # Same length, different digest: only the digest check can catch this,
        # exactly like corruption that preserves size.
        original = staged.read_bytes()
        staged.write_bytes(bytes([original[0] ^ 0x01]) + original[1:])
        assert len(staged.read_bytes()) == len(original)

        with pytest.raises(SupervisorError) as refused:
            _install(owner, ids, lease, bundle)

        assert refused.value.code == "CORRUPT_STATE"
        assert not (site.source / "worklogs").exists()
        assert _intent(site, ids) is None


def test_a_failure_after_the_rename_keeps_the_project_and_its_intent(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: roll an installed project back, or install without an intent."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        bundle = _prepare_bundle(owner, ids, lease)
        base_revision = _current(site, ids)["revision_id"]

        def exploding(*_args: Any, **_kwargs: Any) -> None:
            raise OSError(5, "injected post-rename failure")

        monkeypatch.setattr(WorkspaceAuthority, "_write_revision_from_canonical", exploding)
        with pytest.raises(SupervisorError) as failed:
            _install(owner, ids, lease, bundle)
        monkeypatch.undo()

        assert failed.value.code == "DURABILITY_UNKNOWN"
        # The irreversible step happened: the project stays, byte for byte.
        assert (site.source / "worklogs" / "demo-project" / "roadmap.md").exists()
        # And the durable intent survives, so recovery dispatches instead of
        # guessing; the pointer is still the base revision.
        intent = _intent(site, ids)
        assert intent is not None
        assert intent["kind"] == "BOOTSTRAP"
        assert intent["target_relative"] == "worklogs/demo-project"
        assert intent["phase"] == "PREPARED"
        assert intent["base_revision"] == base_revision
        assert _current(site, ids)["revision_id"] == base_revision


def test_install_orders_entries_as_the_capture_walks(site: Site) -> None:
    """producer-kill-check: sort expected entries by plain path, not by components."""
    worklogs = site.source / "worklogs"
    worklogs.mkdir()
    # Plain string order and depth-first order disagree here: "demo-project.md"
    # sorts before "demo-project/increments", which a walk would visit first.
    # `_Capture.finish` sorts by path string, so that is the canonical order.
    (worklogs / "demo-project.md").write_text("stray notes\n")
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        bundle = _prepare_bundle(owner, ids, lease)

        result = _install(owner, ids, lease, bundle)

        tree = json.loads((_workspace(site, ids) / "revisions" / result.revision_id / "tree.json").read_text())
        paths = [entry["path"] for entry in tree["entries"]]
        assert paths.index("worklogs/demo-project.md") < paths.index("worklogs/demo-project/roadmap.md")
        assert paths.index("worklogs/demo-project") < paths.index("worklogs/demo-project.md")
        assert (worklogs / "demo-project.md").read_text() == "stray notes\n"


def test_install_preserves_an_existing_worklogs_directory_and_its_mode(site: Site) -> None:
    """producer-kill-check: rewrite a pre-existing directory's mode from the bundle."""
    worklogs = site.source / "worklogs"
    worklogs.mkdir()
    worklogs.chmod(0o700)
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        bundle = _prepare_bundle(owner, ids, lease)

        result = _install(owner, ids, lease, bundle)

        assert worklogs.stat().st_mode & 0o777 == 0o700  # not ours to change
        tree = json.loads((_workspace(site, ids) / "revisions" / result.revision_id / "tree.json").read_text())
        modes = {entry["path"]: entry["mode"] for entry in tree["entries"]}
        assert modes["worklogs"] == 0o700
        assert modes["worklogs/demo-project"] == 0o755


# ---------------------------------------------------------------------------
# STEP3 Q58 / CT107a — `publish_plan`: same-path canonical replacement
#
# The inverse of publish's order: the plan file *is* the irreversible point, and
# the revision/pointer are completed forward afterwards. Every case therefore
# also asserts that the canonical plan is either untouched or completely new.
# ---------------------------------------------------------------------------

PLAN_RELATIVE = "worklogs/demo/increments/increment-01-demo.md"
PLAN_OLD = "# plan\n\n## SLICE1: first\n\nDo it.\n"
PLAN_NEW = "# plan\n\n## SLICE1: first\n\nDo it.\n\n## SLICE2: repaired\n\nNow correctly.\n"


def _with_plan(site: Site, *, mode: int = 0o644) -> Any:
    path = site.source / PLAN_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PLAN_OLD)
    path.chmod(mode)
    return read_plan_snapshot(site.source, Path(PLAN_RELATIVE)).ref


def _candidate_plan_view(
    owner: WorkspaceAuthority,
    ids: dict[str, str],
    lease: GrantReply,
    plan_ref: Any,
    buffer: bytes = PLAN_NEW.encode(),
    *,
    stop: bool = True,
) -> GrantReply:
    """Stage candidate bytes only in the view's private supervisor buffer."""
    candidate_path = f".fa/admission/{ACTOR.run_id}/candidate-{uuid4().hex}.md"
    plan_wire = {
        "workspace_relative_path": plan_ref.workspace_relative_path,
        "source_kind": plan_ref.source_kind,
        "sha256": plan_ref.sha256,
    }
    grant = owner.create_view(
        PEER,
        ACTOR,
        workspace_id=ids["workspace_id"],
        capability=lease.capability,
        purpose=ViewPurpose.CANDIDATE,
        access=Access.READ,
        candidate_scope={"candidate_path": candidate_path, "plan_ref": plan_wire},
        plan_ref=plan_ref,
        formal_evidence=False,
        deadline=until(),
        base_revision=lease.revision_id,
    )
    try:
        text = buffer.decode("utf-8") if len(buffer) <= 1024 * 1024 else "temporary valid candidate\n"
    except UnicodeDecodeError:
        text = "temporary valid candidate\n"
    owner.write_candidate(
        PEER,
        ACTOR,
        view_ref=ref(grant),
        capability=grant.capability,
        path=candidate_path,
        content=text,
        expected_sha256=None,
        deadline=until(),
    )
    if buffer != text.encode("utf-8"):
        # Simulate private-store corruption that cannot be expressed by the TEXT wire codec.
        pin = owner._readers[ref(grant).view_id]
        fd = os.open("candidate", os.O_WRONLY | os.O_TRUNC, dir_fd=pin.directory)
        try:
            os.write(fd, buffer)
            os.fsync(fd)
        finally:
            os.close(fd)
    if stop:
        owner.close_admission(PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until())
        owner.drain(PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until())
        owner.record_terminal(PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until())
    return grant


def _publish_candidate(
    owner: WorkspaceAuthority,
    grant: GrantReply,
    *,
    operation_id: str | None = None,
    capability: str | None = None,
) -> Any:
    from fa.execution.publication import publish_plan

    return publish_plan(
        owner,
        PEER,
        ACTOR,
        view_ref=ref(grant),
        capability=grant.capability if capability is None else capability,
        operation_id=operation_id or "op-" + uuid4().hex,
        deadline=until(),
    )


def _publish_plan(owner: WorkspaceAuthority, plan_ref: Any, buffer: bytes = PLAN_NEW.encode(), **kwargs: Any) -> Any:
    lease = kwargs.pop("grant")
    capability = kwargs.pop("capability", None)
    operation_id = kwargs.pop("operation_id", None)
    ids = kwargs.pop("ids")
    candidate = _candidate_plan_view(owner, ids, lease, plan_ref, buffer)
    return _publish_candidate(owner, candidate, operation_id=operation_id, capability=capability)


def test_publish_plan_replaces_the_canonical_file_and_commits_a_revision(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: replace the plan but never commit the revision/pointer."""
    plan_ref = _with_plan(site, mode=0o640)
    old_bytes = (site.source / PLAN_RELATIVE).read_bytes()
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        base_revision = _current(site, ids)["revision_id"]

        captured: dict[str, Any] = {}
        prepare = WorkspaceAuthority._plan_prepare

        def capture_prepare(
            authority: WorkspaceAuthority,
            binding: Any,
            pinned_ref: Any,
            buffer: bytes,
            operation_id: str,
            deadline: float,
        ) -> Any:
            inputs = prepare(authority, binding, pinned_ref, buffer, operation_id, deadline)
            captured["inputs"] = inputs
            return inputs

        monkeypatch.setattr(WorkspaceAuthority, "_plan_prepare", capture_prepare)
        operation_id = "op-" + "a" * 32
        result = _publish_plan(owner, plan_ref, grant=lease, ids=ids, operation_id=operation_id)

        inputs = captured["inputs"]
        manifest = {
            "schema_version": 1,
            "kind": "PLAN",
            "operation_id": operation_id,
            "workspace_id": inputs.workspace_id,
            "generation": inputs.generation,
            "base_revision": inputs.base_revision,
            "target_relative": inputs.plan_relative,
            "new_sha256": inputs.new_sha256,
            "tree_sha256": inputs.tree_sha256,
            "entries": list(inputs.entries),
        }
        assert result.operation_id == operation_id
        assert derive_revision_id(manifest) == result.revision_id
        assert derive_revision_id({**manifest, "operation_id": "op-" + "b" * 32}) != result.revision_id

        canonical = site.source / PLAN_RELATIVE
        assert canonical.read_bytes() == PLAN_NEW.encode()  # complete new bytes, same path
        assert canonical.stat().st_mode & 0o777 == 0o640  # mode preserved
        assert result.plan_ref.workspace_relative_path == PLAN_RELATIVE
        assert result.plan_ref.sha256 == hashlib.sha256(PLAN_NEW.encode()).hexdigest()
        assert result.plan_ref.source_kind == plan_ref.source_kind
        assert result.projection_complete is True

        current = _current(site, ids)
        assert current["revision_id"] == result.revision_id
        assert current["tree_sha256"] == result.tree_sha256
        tree = json.loads((_workspace(site, ids) / "revisions" / result.revision_id / "tree.json").read_text())
        entries = {entry["path"]: entry for entry in tree["entries"]}
        assert entries[PLAN_RELATIVE]["sha256"] == result.plan_ref.sha256
        assert entries[PLAN_RELATIVE]["size"] == len(PLAN_NEW.encode())
        assert result.tree_sha256 == hashlib.sha256(workspace_module._canonical(tree["entries"])).hexdigest()

        # The superseded revision is retained byte-exact for its readers.
        base_data = _workspace(site, ids) / "revisions" / base_revision / "data" / PLAN_RELATIVE
        assert base_data.read_bytes() == old_bytes
        # No temporary survived beside the plan or in the scratch.
        assert not [path for path in canonical.parent.iterdir() if path.name.startswith(".")]
        assert not [path for path in (site.source / ".fa" / "publish-tmp").iterdir() if path.name.endswith(".publish")]
        assert _intent(site, ids) is None

    # A fresh authority accepts the committed revision as its baseline.
    with site.owner(view_profile=native_profile()) as reopened:
        assert site.register(reopened)["revision_id"] == result.revision_id


def test_candidate_publish_applies_a_patch_after_an_unrelated_revision_commit(site: Site) -> None:
    """producer-kill-check: restore workspace-wide base equality (a snapshot, not a patch)."""
    plan_ref = _with_plan(site)
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        candidate = _candidate_plan_view(owner, ids, lease, plan_ref)
        old_revision = lease.revision_id

        ordinary = _view(owner, ids, lease)
        owner.write_file(
            PEER,
            ACTOR,
            view_ref=ref(ordinary),
            capability=ordinary.capability,
            path="unrelated.txt",
            content="revision advanced without changing the plan\n",
            expected_sha256=None,
            deadline=until(),
        )
        _stop(owner, ordinary)
        _publish(owner, ordinary, _seal(owner, ordinary))
        advanced_revision = _current(site, ids)["revision_id"]
        assert advanced_revision != old_revision

        result = _publish_candidate(owner, candidate, operation_id="op-" + "1" * 32)

        # The patch lands on top of the newer revision instead of being refused.
        assert result.already_published is False
        assert result.revision_id != advanced_revision
        assert (site.source / PLAN_RELATIVE).read_text() == PLAN_NEW
        assert (site.source / "unrelated.txt").read_text() == "revision advanced without changing the plan\n"
        assert _current(site, ids)["revision_id"] == result.revision_id
        assert _intent(site, ids) is None


def test_candidate_publish_refuses_plan_bytes_that_moved_since_the_snapshot(site: Site) -> None:
    """producer-kill-check: drop the per-file CAS now that the view base is not compared."""
    plan_ref = _with_plan(site)
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        first = _publish_plan(owner, plan_ref, PLAN_NEW.encode(), grant=lease, ids=ids)
        assert first.already_published is False

        with pytest.raises(SupervisorError) as stale:
            _publish_plan(owner, plan_ref, (PLAN_NEW + "\n## SLICE3: third\n").encode(), grant=lease, ids=ids)

        assert stale.value.code == "STALE_REVISION"
        assert (site.source / PLAN_RELATIVE).read_text() == PLAN_NEW
        assert _current(site, ids)["revision_id"] == first.revision_id
        assert _intent(site, ids) is None


def test_candidate_publish_of_the_current_bytes_reports_a_repeat_and_writes_nothing(site: Site) -> None:
    """producer-kill-check: answer a re-applied intent with INPUT_POLICY instead of the evidence."""
    plan_ref = _with_plan(site)
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        before_current = _current(site, ids)
        canonical = site.source / PLAN_RELATIVE
        before_bytes = canonical.read_bytes()

        result = _publish_plan(owner, plan_ref, PLAN_OLD.encode(), grant=lease, ids=ids)

        assert result.already_published is True
        assert result.revision_id == before_current["revision_id"]
        assert result.tree_sha256 == before_current["tree_sha256"]
        assert result.plan_ref.sha256 == hashlib.sha256(PLAN_OLD.encode()).hexdigest()
        assert canonical.read_bytes() == before_bytes
        assert _current(site, ids) == before_current
        assert _intent(site, ids) is None
        assert not [path for path in canonical.parent.iterdir() if path.name.startswith(".")]

        # The same intent again is still a repeat, not a second commit.
        again = _publish_plan(owner, plan_ref, PLAN_OLD.encode(), grant=lease, ids=ids)
        assert again.already_published is True
        assert again.revision_id == before_current["revision_id"]
        assert _current(site, ids) == before_current


def test_plan_commit_path_is_fixed_by_the_pinned_ref_not_a_publish_argument(site: Site) -> None:
    """producer-kill-check: reintroduce a caller-supplied target in the publish API."""
    plan_ref = _with_plan(site)
    roadmap = site.source / "worklogs/demo/roadmap.md"
    roadmap.write_text("# roadmap\n")
    from inspect import signature

    from fa.execution.publication import publish_plan

    assert "plan_ref" not in signature(publish_plan).parameters
    assert "buffer" not in signature(publish_plan).parameters
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        bad_refs = (
            type(plan_ref)("src/fa/execution/workspace.py", plan_ref.source_kind, plan_ref.sha256),
            read_plan_snapshot(site.source, Path("worklogs/demo/roadmap.md")).ref,
            type(plan_ref)("worklogs/demo/notes/increment-01-demo.md", plan_ref.source_kind, plan_ref.sha256),
            type(plan_ref)("worklogs/demo/increments/increment-01-demo.txt", plan_ref.source_kind, plan_ref.sha256),
            type(plan_ref)("worklogs/demo/increments/../../escape.md", plan_ref.source_kind, plan_ref.sha256),
        )
        for bad_ref in bad_refs:
            with pytest.raises(SupervisorError) as refused:
                owner._plan_parts(bad_ref)
            assert refused.value.code == "INPUT_POLICY", bad_ref.workspace_relative_path
        protected = type(plan_ref)("worklogs/.fa/increments/x.md", plan_ref.source_kind, plan_ref.sha256)
        with pytest.raises(SupervisorError) as denied:
            owner._plan_parts(protected)
        assert denied.value.code == "PATH_DENIED"
        assert (site.source / PLAN_RELATIVE).read_text() == PLAN_OLD
        assert roadmap.read_text() == "# roadmap\n"
        assert _intent(site, ids) is None


def test_publish_plan_refuses_bytes_that_are_not_a_plan(site: Site) -> None:
    """producer-kill-check: write a caller buffer without the strict plan rules."""
    from fa.inner_loop.plan_admission import MAX_PLAN_BYTES

    plan_ref = _with_plan(site)
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))

        for buffer in (b"\xff\xfe\x00", b"", b"   \n\t\n", b"# plan\n" + b"x" * MAX_PLAN_BYTES):
            with pytest.raises(SupervisorError) as refused:
                _publish_plan(owner, plan_ref, buffer, grant=lease, ids=ids)
            assert refused.value.code == "INPUT_POLICY", buffer[:8]

        # Identical bytes are a repeat, not a replacement — covered by
        # `test_candidate_publish_of_the_current_bytes_reports_a_repeat_and_writes_nothing`.
        assert (site.source / PLAN_RELATIVE).read_text() == PLAN_OLD


def test_publish_plan_requires_the_owner_grant_and_no_live_view(site: Site) -> None:
    """producer-kill-check: replace a plan under a live writer or a bad capability."""
    plan_ref = _with_plan(site)
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        _view(owner, ids, lease)

        with pytest.raises(SupervisorError) as busy:
            _publish_plan(owner, plan_ref, grant=lease, ids=ids)
        assert busy.value.code == "WORKSPACE_BUSY"

        assert (site.source / PLAN_RELATIVE).read_text() == PLAN_OLD


def test_candidate_publish_requires_closed_view_and_matching_terminal_receipt(site: Site) -> None:
    """producer-kill-check: infer terminality from record_terminal or an OPEN view."""
    plan_ref = _with_plan(site)
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        open_candidate = _candidate_plan_view(owner, ids, lease, plan_ref, stop=False)
        with pytest.raises(SupervisorError) as open_view:
            _publish_candidate(owner, open_candidate)
        assert open_view.value.code == "VIEW_CLOSED"

        incomplete = _candidate_plan_view(owner, ids, lease, plan_ref, stop=False)
        owner.close_admission(PEER, ACTOR, view_ref=ref(incomplete), capability=incomplete.capability, deadline=until())
        owner.drain(PEER, ACTOR, view_ref=ref(incomplete), capability=incomplete.capability, deadline=until())
        with pytest.raises(SupervisorError) as no_receipt:
            _publish_candidate(owner, incomplete)
        assert no_receipt.value.code == "TERMINALITY_UNKNOWN"
        assert (site.source / PLAN_RELATIVE).read_text() == PLAN_OLD


def test_record_terminal_does_not_substitute_for_draining_active_candidate_work(site: Site) -> None:
    """producer-kill-check: allow PLAN replace after terminal.json while work is active."""
    plan_ref = _with_plan(site)
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        candidate = _candidate_plan_view(owner, ids, lease, plan_ref, stop=False)
        view_ref = ref(candidate)
        owner.close_admission(PEER, ACTOR, view_ref=view_ref, capability=candidate.capability, deadline=until())
        owner._gate(view_ref).active.add("held-work")
        owner.record_terminal(PEER, ACTOR, view_ref=view_ref, capability=candidate.capability, deadline=until())
        try:
            with pytest.raises(SupervisorError) as busy:
                _publish_candidate(owner, candidate, operation_id="op-" + "c" * 32)
            assert busy.value.code == "BACKEND_UNAVAILABLE"
            assert (site.source / PLAN_RELATIVE).read_text() == PLAN_OLD
            assert _intent(site, ids) is None
        finally:
            owner._gate(view_ref).active.discard("held-work")


def test_candidate_publish_refuses_owner_capability_in_place_of_view_grant(site: Site) -> None:
    """producer-kill-check: accept the OWNER grant instead of the candidate view grant."""
    plan_ref = _with_plan(site)
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))

        with pytest.raises(SupervisorError) as unauthorized:
            _publish_plan(owner, plan_ref, grant=lease, capability=lease.capability, ids=ids)

        assert unauthorized.value.code == "UNAUTHORIZED"
        assert (site.source / PLAN_RELATIVE).read_text() == PLAN_OLD


def test_publish_plan_refuses_a_plan_swapped_for_a_link_before_the_replace(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: follow whatever sits at the plan path at replace time."""
    outside = site.source.parent / "outside.md"
    outside.write_text("# outside\n")
    plan_ref = _with_plan(site)
    real_stage = WorkspaceAuthority._plan_stage
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))

        def stage_then_link(self: WorkspaceAuthority, binding: Any, inputs: Any, scratch: int) -> None:
            real_stage(self, binding, inputs, scratch)
            path = site.source / PLAN_RELATIVE
            path.unlink()
            path.symlink_to(outside)

        monkeypatch.setattr(WorkspaceAuthority, "_plan_stage", stage_then_link)
        with pytest.raises(SupervisorError) as refused:
            _publish_plan(owner, plan_ref, grant=lease, ids=ids)
        monkeypatch.undo()

        assert refused.value.code == "PATH_DENIED"
        assert (site.source / PLAN_RELATIVE).is_symlink()
        assert outside.read_text() == "# outside\n"
        assert _intent(site, ids) is None


def test_a_symlinked_plan_can_never_reach_a_revision_to_be_replaced(site: Site) -> None:
    """producer-kill-check: let a link stand in for the plan the authority replaces.

    Both sides refuse before `publish_plan` can run: admission will not mint a
    ref for a link, and registration will not admit a tree containing one. A
    symlink is therefore not a "replaceable plan" in either direction.
    """
    outside = site.source.parent / "outside.md"
    outside.write_text("# outside\n")
    path = site.source / PLAN_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(outside)

    with pytest.raises(PlanRefError) as admitted:
        read_plan_snapshot(site.source, Path(PLAN_RELATIVE))
    assert admitted.value.rule == "symlink"

    with site.owner(view_profile=native_profile()) as owner:
        with pytest.raises(SupervisorError) as refused:
            site.register(owner)
        assert refused.value.code in {"PATH_DENIED", "INPUT_POLICY"}

    assert path.is_symlink()
    assert outside.read_text() == "# outside\n"


def test_publish_plan_refuses_after_a_concurrent_write_between_staging_and_replace(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: check the source hash once, then replace blindly (Q58 CAS)."""
    plan_ref = _with_plan(site)
    real_stage = WorkspaceAuthority._plan_stage
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))

        def stage_then_lose_the_race(self: WorkspaceAuthority, binding: Any, inputs: Any, scratch: int) -> None:
            real_stage(self, binding, inputs, scratch)
            (site.source / PLAN_RELATIVE).write_text("# someone else wrote this\n")

        monkeypatch.setattr(WorkspaceAuthority, "_plan_stage", stage_then_lose_the_race)
        with pytest.raises(SupervisorError) as refused:
            _publish_plan(owner, plan_ref, grant=lease, ids=ids)
        monkeypatch.undo()

        assert refused.value.code == "STALE_REVISION"
        # The foreign write is preserved: this attempt replaced nothing.
        assert (site.source / PLAN_RELATIVE).read_text() == "# someone else wrote this\n"
        assert _intent(site, ids) is None


def test_publish_plan_refuses_bytes_that_are_not_the_ones_it_staged(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: install a revision from the expectation, never the copy.

    Q58's post-replace byte proof is the revision copy itself, so this is where
    bytes that differ from the staged buffer must be refused — after the
    replace, with the intent kept and no revision installed.
    """
    plan_ref = _with_plan(site, mode=0o600)
    wrong = PLAN_NEW.replace("repaired", "REPAIRED")  # same length, different bytes
    real_stage = WorkspaceAuthority._plan_stage
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        base_revision = _current(site, ids)["revision_id"]

        def stage_then_swap(self: WorkspaceAuthority, binding: Any, inputs: Any, scratch: int) -> None:
            real_stage(self, binding, inputs, scratch)
            fd = os.open(inputs.temporary, os.O_WRONLY, dir_fd=scratch)
            try:
                os.pwrite(fd, wrong.encode(), 0)
            finally:
                os.close(fd)

        monkeypatch.setattr(WorkspaceAuthority, "_plan_stage", stage_then_swap)
        with pytest.raises(SupervisorError) as refused:
            _publish_plan(owner, plan_ref, grant=lease, ids=ids)
        monkeypatch.undo()

        assert refused.value.code == "CORRUPT_STATE"
        # Same length, so only the copy's digest proof can see it.
        assert len(wrong.encode()) == len(PLAN_NEW.encode())
        assert (site.source / PLAN_RELATIVE).read_bytes() == wrong.encode()
        assert _current(site, ids)["revision_id"] == base_revision
        intent = _intent(site, ids)
        assert intent is not None and intent["phase"] == "PREPARED"
        # The workspace refuses further work: the canonical tree is no longer
        # the committed revision, so every forward step would begin from a lie.
        with pytest.raises(SupervisorError) as unusable:
            site.register(owner)
        assert unusable.value.code == "CORRUPT_STATE"


def test_publish_plan_refuses_a_replaced_plan_with_the_wrong_mode(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    """producer-kill-check: compare bytes only and never the mode (Q58)."""
    plan_ref = _with_plan(site, mode=0o640)
    real_stage = WorkspaceAuthority._plan_stage
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))

        def stage_then_lose_the_mode(self: WorkspaceAuthority, binding: Any, inputs: Any, scratch: int) -> None:
            real_stage(self, binding, inputs, scratch)
            os.chmod(inputs.temporary, 0o600, dir_fd=scratch)  # mode lost in staging

        monkeypatch.setattr(WorkspaceAuthority, "_plan_stage", stage_then_lose_the_mode)
        with pytest.raises(SupervisorError) as refused:
            _publish_plan(owner, plan_ref, grant=lease, ids=ids)
        monkeypatch.undo()

        assert refused.value.code == "CORRUPT_STATE"
        assert (site.source / PLAN_RELATIVE).read_bytes() == PLAN_NEW.encode()
        intent = _intent(site, ids)
        assert intent is not None and intent["phase"] == "PREPARED"


def test_a_failure_after_the_plan_replace_keeps_the_new_bytes_and_the_intent(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: roll a replaced plan back, or replace without an intent."""
    plan_ref = _with_plan(site)
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        base_revision = _current(site, ids)["revision_id"]

        def exploding(*_args: Any, **_kwargs: Any) -> None:
            raise OSError(5, "injected post-replace failure")

        monkeypatch.setattr(WorkspaceAuthority, "_write_revision_from_canonical", exploding)
        with pytest.raises(SupervisorError) as failed:
            _publish_plan(owner, plan_ref, grant=lease, ids=ids)
        monkeypatch.undo()

        assert failed.value.code == "DURABILITY_UNKNOWN"
        # Q58: the replacement is never rolled back.
        assert (site.source / PLAN_RELATIVE).read_bytes() == PLAN_NEW.encode()
        intent = _intent(site, ids)
        assert intent is not None
        assert intent["kind"] == "PLAN"
        assert intent["target_relative"] == PLAN_RELATIVE
        assert intent["old_sha256"] == plan_ref.sha256
        assert intent["new_sha256"] == hashlib.sha256(PLAN_NEW.encode()).hexdigest()
        assert intent["phase"] == "PREPARED"
        assert _current(site, ids)["revision_id"] == base_revision
        # Unknown side of the boundary: the authority stops serving.
        with pytest.raises(SupervisorError) as unusable:
            site.register(owner)
        assert unusable.value.code == "CORRUPT_STATE"
