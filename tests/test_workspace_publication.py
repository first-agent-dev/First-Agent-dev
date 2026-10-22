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


def _stopped(
    owner: WorkspaceAuthority,
    ids: dict[str, str],
    lease: GrantReply,
    *,
    plan_ref: Any = None,
    purpose: ViewPurpose = ViewPurpose.PROJECT,
) -> GrantReply:
    """Create one view and stop it through the real barrier (CT104's flow)."""
    writable = purpose in {ViewPurpose.PROJECT, ViewPurpose.MUTATION, ViewPurpose.PROVISIONING}
    grant = owner.create_view(
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
    stopper = ViewStopper(owner, cells=RecordingCells(owner, grant, verdicts=[True]), poll_interval_s=0.001)
    result = stopper.stop_view(PEER, ACTOR, view_ref=ref(grant), capability=grant.capability, deadline=until())
    assert result.terminal is True, "the fixture could not stop its own view"
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
