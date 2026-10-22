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

import pytest

import fa.execution.publication as publication_module
import fa.execution.workspace as workspace_module
from fa.execution.publication import MANIFEST_NAME, SealResult, derive_revision_id, seal_view
from fa.execution.supervisor import SupervisorError, TerminalVerdict, ViewStopper
from fa.execution.types import Access, GrantReply, NamespaceRef, ViewPurpose, ViewRef
from fa.execution.workspace import WorkspaceAuthority
from fa.inner_loop.plan_admission import read_plan_snapshot
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
    from dataclasses import replace

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
                owner._binding(ids["workspace_id"]), replace(inputs, entries=(*inputs.entries, ghost)), until()
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
