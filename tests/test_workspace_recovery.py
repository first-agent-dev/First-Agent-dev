"""SLICE3 STEP4 — CT107 forward recovery at every durable boundary.

Classes (knowledge/skills/tests-writing):
  C3 — `_recover_intent` driven through the real authority: a crash is simulated
       by killing the process at a named step (`SystemExit` is caught by neither
       `except SupervisorError` nor `except OSError`, so the abort/cleanup paths
       never run and the state left behind is exactly what a SIGKILL leaves),
       then a *new* `WorkspaceAuthority` is entered — the one hook `_load` offers.
  C1 — the inspection itself, over planted intent/pointer states the live
       producers cannot reach without a second bug.

What must stay true (each test names the producer it kills):
  * the discriminator is the inspected target (`current.json`, the plan's hash,
    the installed directory), never `phase`;
  * an attempt that never reached its irreversible point is discarded, and only
    its own scratch and its own created directories are touched;
  * an attempt past that point is completed forward — never rolled back;
  * anything else is quarantined with the intent kept as evidence;
  * a workspace that cannot be settled never takes the whole authority down, and
    abandoned `pending/` scratch is discarded only when it is provably ours.

Note on assertions: `_load` writes `OWNED -> QUARANTINED` for every owned
workspace (CT104: a restart cannot release a live old writer), so a recovered
workspace is consistent but not writable again. Recovery is therefore proved on
the state it leaves on disk, and `intent.json`'s absence is the positive signal
that it settled the attempt instead of being held.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

import fa.execution.workspace as workspace_module
from fa.execution.supervisor import SupervisorError
from fa.execution.workspace import WorkspaceAuthority
from tests.test_execution_readers import ref
from tests.test_execution_views import native_profile
from tests.test_execution_workspace import ACTOR, PEER, Site, ok, until
from tests.test_execution_workspace import site as site
from tests.test_workspace_publication import (
    PLAN_NEW,
    PLAN_OLD,
    PLAN_RELATIVE,
    _current,
    _install,
    _intent,
    _prepare_bundle,
    _publish,
    _publish_plan,
    _record,
    _seal,
    _state,
    _view,
    _with_plan,
    _workspace,
)

PROBE = "added.txt"


def _reopen(site: Site) -> WorkspaceAuthority:
    """Enter a fresh authority — the one place `_load` runs recovery."""
    return site.owner(view_profile=native_profile())


def _plan_path(site: Site) -> Path:
    return site.source / PLAN_RELATIVE


def _add_probe(owner: WorkspaceAuthority, grant: Any) -> None:
    owner.write_file(
        PEER,
        ACTOR,
        view_ref=ref(grant),
        capability=grant.capability,
        path=PROBE,
        content="added by the view\n",
        expected_sha256=None,
        deadline=until(),
    )


# ---------------------------------------------------------------------------
# REVISION — `current.json` is the discriminator
# ---------------------------------------------------------------------------


def test_recovery_discards_an_uncommitted_revision_when_the_pointer_never_moved(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: keep the owned revision, or roll the pointer forward."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped_probe(owner, ids, lease)
        sealed = _seal(owner, grant)
        base_revision, base_tree = _current(site, ids)["revision_id"], _current(site, ids)["tree_sha256"]

        # Killed after the revision was staged and installed, before the CAS.
        monkeypatch.setattr(WorkspaceAuthority, "commit_revision_current", _killed)
        with pytest.raises(SystemExit):
            _publish(owner, grant, sealed)
        monkeypatch.undo()

        assert (_workspace(site, ids) / "revisions" / sealed.revision_id).is_dir()
        assert _intent(site, ids) is not None and _intent(site, ids)["phase"] == "PREPARED"  # type: ignore[index]
        assert _current(site, ids)["revision_id"] == base_revision
        assert not (site.source / PROBE).exists()

    with _reopen(site) as recovered:
        assert _intent(site, ids) is None, "recovery did not settle the attempt"
        assert not (_workspace(site, ids) / "revisions" / sealed.revision_id).exists(), "orphan revision kept"
        assert _current(site, ids)["revision_id"] == base_revision
        assert _current(site, ids)["tree_sha256"] == base_tree
        assert not (site.source / PROBE).exists()
        assert site.metadata(ids)["status"] == "QUARANTINED"
        assert recovered is not None


def test_recovery_completes_a_projection_the_pointer_already_committed(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: leave a committed revision half-projected."""
    real_replace = os.replace
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped_probe(owner, ids, lease)
        sealed = _seal(owner, grant)

        def exploding(source: Any, destination: Any = None, **kwargs: Any) -> None:
            if isinstance(source, str) and source.endswith(".publish"):
                raise OSError(5, "injected projection crash")
            real_replace(source, destination, **kwargs)

        monkeypatch.setattr(workspace_module.os, "replace", exploding)
        with pytest.raises(SupervisorError) as failed:
            _publish(owner, grant, sealed)
        monkeypatch.undo()

        assert failed.value.code == "DURABILITY_UNKNOWN"
        assert _current(site, ids)["revision_id"] == sealed.revision_id
        assert not (site.source / PROBE).exists()

    with _reopen(site) as recovered:
        assert _intent(site, ids) is None
        assert (site.source / PROBE).read_text() == "added by the view\n", "projection not completed"
        assert _current(site, ids)["revision_id"] == sealed.revision_id
        assert _state(site, grant) == "PUBLISHED", "the recovered publish never settled its view"
        assert recovered is not None


def test_recovery_resumes_a_projection_that_only_partly_applied(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    """producer-kill-check: re-project from scratch instead of converging per entry."""
    real_project = WorkspaceAuthority._project_file
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _view(owner, ids, lease)
        for name in ("a.txt", "b.txt"):
            owner.write_file(
                PEER,
                ACTOR,
                view_ref=ref(grant),
                capability=grant.capability,
                path=name,
                content=f"{name}\n",
                expected_sha256=None,
                deadline=until(),
            )
        from tests.test_workspace_publication import _stop

        _stop(owner, grant)
        sealed = _seal(owner, grant)

        def flaky(instance: WorkspaceAuthority, binding: Any, source: int, entry: Any, deadline: float) -> None:
            if entry["path"] == "b.txt":
                raise OSError(5, "killed mid-projection")
            real_project(instance, binding, source, entry, deadline)

        monkeypatch.setattr(WorkspaceAuthority, "_project_file", flaky)
        with pytest.raises(SupervisorError) as failed:
            _publish(owner, grant, sealed)
        monkeypatch.undo()

        assert failed.value.code == "DURABILITY_UNKNOWN"
        assert (site.source / "a.txt").exists() and not (site.source / "b.txt").exists()

    with _reopen(site) as recovered:
        assert _intent(site, ids) is None
        assert (site.source / "a.txt").read_text() == "a.txt\n"
        assert (site.source / "b.txt").read_text() == "b.txt\n", "the partial entry was never applied"
        assert _current(site, ids)["revision_id"] == sealed.revision_id
        assert _state(site, grant) == "PUBLISHED"
        assert recovered is not None


def test_recovery_refuses_a_publish_whose_view_record_is_gone(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    """producer-kill-check: project committed bytes without proving which view owns them."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped_probe(owner, ids, lease)
        sealed = _seal(owner, grant)
        view_dir = _workspace(site, ids) / "views" / ref(grant).view_id

        monkeypatch.setattr(WorkspaceAuthority, "_project_entries", _killed)
        with pytest.raises(SystemExit):
            _publish(owner, grant, sealed)
        monkeypatch.undo()
        assert _intent(site, ids) is not None

        for child in view_dir.iterdir():
            if child.is_dir():
                import shutil

                shutil.rmtree(child)
            else:
                child.unlink()
        view_dir.rmdir()

    with _reopen(site) as recovered:
        assert _intent(site, ids) is not None, "recovery invented progress it could not prove"
        assert not (site.source / PROBE).exists(), "canonical bytes were written before the view was proved"
        assert _current(site, ids)["revision_id"] == sealed.revision_id
        assert site.metadata(ids)["status"] == "QUARANTINED"
        assert recovered is not None


@pytest.mark.parametrize("corruption", ["state", "view_ref"])
def test_recovery_refuses_a_view_record_that_is_not_the_one_it_committed(
    site: Site, monkeypatch: pytest.MonkeyPatch, corruption: str
) -> None:
    """producer-kill-check: settle whatever record happens to sit in that directory."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped_probe(owner, ids, lease)
        sealed = _seal(owner, grant)

        monkeypatch.setattr(WorkspaceAuthority, "_project_entries", _killed)
        with pytest.raises(SystemExit):
            _publish(owner, grant, sealed)
        monkeypatch.undo()

        record = _record(site, grant)
        if corruption == "state":
            record["state"] = "STOPPING"
        else:
            record["view_ref"] = {**record["view_ref"], "view_id": "view-" + uuid4().hex}
        path = _workspace(site, ids) / "views" / ref(grant).view_id / "view.json"
        path.write_text(json.dumps(record))
        path.chmod(0o600)

    with _reopen(site) as recovered:
        assert _intent(site, ids) is not None, "a foreign view record was accepted as this publish's"
        assert not (site.source / PROBE).exists(), "projection started before the view was proved"
        assert site.metadata(ids)["status"] == "QUARANTINED"
        assert recovered is not None


def test_recovery_refuses_a_revision_the_pointer_does_not_name(site: Site) -> None:
    """producer-kill-check: complete whatever revision the intent names.

    Two views that seal the same entries derive **different** revision ids (the
    id covers the manifest, not just the tree), so this intent names a durable,
    projectable revision the pointer has already moved past. Only the pointer
    comparison refuses it: the projection itself would succeed.
    """
    from tests.test_workspace_publication import _stop

    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        base_revision = _current(site, ids)["revision_id"]
        first = _stopped_probe(owner, ids, lease)
        sealed_first = _seal(owner, first)
        _publish(owner, first, sealed_first)
        first_tree = _current(site, ids)["tree_sha256"]

        second = _view(owner, ids, lease)  # seals the same entries the pointer holds
        _stop(owner, second)
        sealed_second = _seal(owner, second)
        _publish(owner, second, sealed_second)
        committed = _current(site, ids)["revision_id"]
        assert committed == sealed_second.revision_id
        assert committed != sealed_first.revision_id
        assert _current(site, ids)["tree_sha256"] == first_tree == sealed_first.tree_sha256

        planted = {
            "schema_version": 1,
            "kind": "REVISION",
            "operation_id": "op-" + uuid4().hex,
            "workspace_id": ids["workspace_id"],
            "generation": site.metadata(ids)["generation"],
            "base_revision": base_revision,
            "next_revision": sealed_first.revision_id,
            "tree_sha256": sealed_first.tree_sha256,
            "phase": "PROJECTING",
            "target_relative": None,
            "old_sha256": None,
            "new_sha256": None,
            "created_directories": [],
            "view_ref": ref(first).to_dict(),
        }
        _write_intent(site, ids, planted)

    with _reopen(site) as recovered:
        assert _intent(site, ids) == planted, "a revision the pointer never named was published"
        assert _current(site, ids)["revision_id"] == committed
        assert site.metadata(ids)["status"] == "QUARANTINED"
        assert recovered is not None


def test_recovery_writes_no_canonical_byte_before_the_intent_is_proved(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: project first and let the hash check refuse afterwards."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped_probe(owner, ids, lease)
        sealed = _seal(owner, grant)

        monkeypatch.setattr(WorkspaceAuthority, "_project_entries", _killed)
        with pytest.raises(SystemExit):
            _publish(owner, grant, sealed)
        monkeypatch.undo()

        intent = _intent(site, ids)
        assert intent is not None
        intent["tree_sha256"] = "0" * 64  # the durable revision is not what was promised
        _write_intent(site, ids, intent)

    with _reopen(site) as recovered:
        assert _intent(site, ids) == intent
        assert not (site.source / PROBE).exists(), "canonical bytes were written for an unproved intent"
        assert site.metadata(ids)["status"] == "QUARANTINED"
        assert recovered is not None


def test_recovery_refuses_a_phase_that_contradicts_the_pointer(site: Site) -> None:
    """producer-kill-check: trust `phase` — a projection marker with no commit."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        assert ok(lambda: site.claim(owner, ids))
        planted = _planted_intent(site, ids, phase="PROJECTING", next_revision="rev-" + uuid4().hex)
        _write_intent(site, ids, planted)

    with _reopen(site) as recovered:
        assert _intent(site, ids) == planted
        assert site.metadata(ids)["status"] == "QUARANTINED"
        assert recovered is not None


def test_recovery_refuses_another_workspaces_intent(site: Site) -> None:
    """producer-kill-check: run an intent against whatever workspace it sits in."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        assert ok(lambda: site.claim(owner, ids))
        planted = _planted_intent(site, ids, phase="PREPARED", next_revision="rev-" + uuid4().hex)
        planted["workspace_id"] = "ws-" + uuid4().hex
        _write_intent(site, ids, planted)

    with _reopen(site) as recovered:
        assert _intent(site, ids) == planted
        assert site.metadata(ids)["status"] == "QUARANTINED"
        assert recovered is not None


def test_recovery_refuses_a_projection_with_bytes_the_revision_does_not_own(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: drop the completed-projection proof from recovery."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _stopped_probe(owner, ids, lease)
        sealed = _seal(owner, grant)

        monkeypatch.setattr(WorkspaceAuthority, "_project_entries", _killed)
        with pytest.raises(SystemExit):
            _publish(owner, grant, sealed)
        monkeypatch.undo()
        # Bytes the committed revision does not own: projection will not remove
        # them, so only a full-tree proof can refuse to call this a publish.
        (site.source / "stray.txt").write_text("written behind the authority's back\n")

    with _reopen(site) as recovered:
        assert _intent(site, ids) is not None, "an unprovable projection was accepted"
        assert (site.source / "stray.txt").read_text() == "written behind the authority's back\n"
        assert _state(site, grant) != "PUBLISHED", "the view was settled without a completed projection"
        assert site.metadata(ids)["status"] == "QUARANTINED"
        assert recovered is not None


# ---------------------------------------------------------------------------
# PLAN — the canonical file's own hash is the discriminator
# ---------------------------------------------------------------------------


def test_recovery_completes_a_replaced_plan_forward(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    """producer-kill-check: roll a replaced plan back, or leave it without a revision."""
    plan_ref = _with_plan(site)
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        base_revision = _current(site, ids)["revision_id"]

        monkeypatch.setattr(WorkspaceAuthority, "_write_revision_from_canonical", _killed)
        with pytest.raises(SystemExit):
            _publish_plan(owner, plan_ref, PLAN_NEW.encode(), grant=lease, ids=ids)
        monkeypatch.undo()

        assert _plan_path(site).read_bytes() == PLAN_NEW.encode()
        intent = _intent(site, ids)
        assert intent is not None and intent["kind"] == "PLAN" and intent["phase"] == "PREPARED"
        assert _current(site, ids)["revision_id"] == base_revision

    with _reopen(site) as recovered:
        assert _intent(site, ids) is None
        assert _plan_path(site).read_bytes() == PLAN_NEW.encode(), "the replacement was rolled back"
        current = _current(site, ids)
        assert current["revision_id"] != base_revision, "the replacement never became a revision"
        tree = json.loads((_workspace(site, ids) / "revisions" / current["revision_id"] / "tree.json").read_text())
        assert current["tree_sha256"] == hashlib.sha256(workspace_module._canonical(tree["entries"])).hexdigest()
        assert (
            _workspace(site, ids) / "revisions" / current["revision_id"] / "data" / PLAN_RELATIVE
        ).read_bytes() == PLAN_NEW.encode()
        assert (_workspace(site, ids) / "revisions" / base_revision).is_dir(), "the old revision was deleted"
        assert recovered is not None


def test_recovery_clears_a_plan_intent_when_the_old_bytes_are_still_there(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: treat an early plan kill as a completed replacement."""
    plan_ref = _with_plan(site)
    real_replace = os.replace
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        base_revision = _current(site, ids)["revision_id"]

        def killed_replace(source: Any, destination: Any = None, **kwargs: Any) -> None:
            # Only the plan's own staged buffer, never the intent/pointer writes
            # that `_replace_private_bytes` also performs through `os.replace`.
            if isinstance(source, str) and source.startswith(".plan."):
                raise SystemExit("killed before the plan replace")
            real_replace(source, destination, **kwargs)

        monkeypatch.setattr(workspace_module.os, "replace", killed_replace)
        with pytest.raises(SystemExit):
            _publish_plan(owner, plan_ref, PLAN_NEW.encode(), grant=lease, ids=ids)
        monkeypatch.undo()

        assert _plan_path(site).read_text() == PLAN_OLD
        assert _intent(site, ids) is not None and _intent(site, ids)["phase"] == "PREPARED"  # type: ignore[index]

    with _reopen(site) as recovered:
        assert _intent(site, ids) is None
        assert _plan_path(site).read_text() == PLAN_OLD, "old bytes were rewritten by recovery"
        assert _current(site, ids)["revision_id"] == base_revision
        assert recovered is not None


def test_recovery_refuses_a_plan_that_matches_neither_hash(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    """producer-kill-check: overwrite a third version with the intended bytes."""
    plan_ref = _with_plan(site)
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        monkeypatch.setattr(WorkspaceAuthority, "_write_revision_from_canonical", _killed)
        with pytest.raises(SystemExit):
            _publish_plan(owner, plan_ref, PLAN_NEW.encode(), grant=lease, ids=ids)
        monkeypatch.undo()

        third = PLAN_NEW + "\n## SLICE3: written by someone else\n"
        _plan_path(site).write_text(third)

    with _reopen(site) as recovered:
        assert _intent(site, ids) is not None
        assert _plan_path(site).read_text() == third, "a third version was overwritten"
        assert site.metadata(ids)["status"] == "QUARANTINED"
        assert recovered is not None


def test_recovery_refuses_a_plan_intent_that_does_not_describe_the_bytes(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: trust a recomputation over the tree the intent promised."""
    plan_ref = _with_plan(site)
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        base_revision = _current(site, ids)["revision_id"]
        monkeypatch.setattr(WorkspaceAuthority, "_write_revision_from_canonical", _killed)
        with pytest.raises(SystemExit):
            _publish_plan(owner, plan_ref, PLAN_NEW.encode(), grant=lease, ids=ids)
        monkeypatch.undo()

        intent = _intent(site, ids)
        assert intent is not None
        intent["tree_sha256"] = "0" * 64
        _write_intent(site, ids, intent)

    with _reopen(site) as recovered:
        assert _intent(site, ids) == intent, "the intent was cleared although it described nothing"
        assert _current(site, ids)["revision_id"] == base_revision
        assert _plan_path(site).read_bytes() == PLAN_NEW.encode()
        assert site.metadata(ids)["status"] == "QUARANTINED"
        assert recovered is not None


# ---------------------------------------------------------------------------
# BOOTSTRAP — the installed directory is the discriminator
# ---------------------------------------------------------------------------


def test_recovery_finishes_an_install_whose_rename_happened(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    """producer-kill-check: delete the installed directory, or leave it without a revision."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        bundle = _prepare_bundle(owner, ids, lease)
        base_revision = _current(site, ids)["revision_id"]

        monkeypatch.setattr(WorkspaceAuthority, "_write_revision_from_canonical", _killed)
        with pytest.raises(SystemExit):
            _install(owner, ids, lease, bundle)
        monkeypatch.undo()

        intent = _intent(site, ids)
        assert intent is not None and intent["kind"] == "BOOTSTRAP" and intent["phase"] == "PREPARED"
        assert (site.source / "worklogs" / "demo-project" / "roadmap.md").is_file()
        assert _current(site, ids)["revision_id"] == base_revision

    with _reopen(site) as recovered:
        assert _intent(site, ids) is None
        installed = site.source / "worklogs" / "demo-project"
        assert (installed / "roadmap.md").is_file() and (installed / "ledger.md").is_file()
        current = _current(site, ids)
        assert current["revision_id"] == intent["next_revision"]
        assert current["tree_sha256"] == intent["tree_sha256"]
        assert (_workspace(site, ids) / "revisions" / intent["next_revision"] / "data").is_dir()
        assert recovered is not None


def test_recovery_removes_exactly_the_directories_the_attempt_created(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: leave the created ancestor, or undo more than it created."""
    real_rename = workspace_module._rename_directory
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        bundle = _prepare_bundle(owner, ids, lease)
        base_revision, base_tree = _current(site, ids)["revision_id"], _current(site, ids)["tree_sha256"]

        def killed_rename(source: int, name: str, destination: int, leaf: str) -> None:
            if leaf == "demo-project":
                raise SystemExit("killed before RENAME_NOREPLACE")
            real_rename(source, name, destination, leaf)

        monkeypatch.setattr(workspace_module, "_rename_directory", killed_rename)
        with pytest.raises(SystemExit):
            _install(owner, ids, lease, bundle)
        monkeypatch.undo()

        assert (site.source / "worklogs").is_dir()
        assert list((site.source / "worklogs").iterdir()) == []
        assert _intent(site, ids) is not None

    with _reopen(site) as recovered:
        assert _intent(site, ids) is None
        assert not (site.source / "worklogs").exists(), "the attempt's own created directory was kept"
        assert _current(site, ids)["revision_id"] == base_revision
        assert _current(site, ids)["tree_sha256"] == base_tree
        assert recovered is not None


def test_recovery_keeps_a_directory_the_base_revision_already_owned(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: remove a pre-existing ancestor recorded as 'created'."""
    keep = site.source / "worklogs" / "other"
    keep.mkdir(parents=True)
    (keep / "keep.txt").write_text("someone else's project\n")
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        bundle = _prepare_bundle(owner, ids, lease)

        monkeypatch.setattr(workspace_module, "_rename_directory", _killed)
        with pytest.raises(SystemExit):
            _install(owner, ids, lease, bundle)
        monkeypatch.undo()
        assert _intent(site, ids) is not None

    with _reopen(site) as recovered:
        assert _intent(site, ids) is None
        assert (keep / "keep.txt").read_text() == "someone else's project\n"
        assert not (site.source / "worklogs" / "demo-project").exists()
        assert recovered is not None


def test_recovery_refuses_an_installed_tree_that_is_not_the_approved_bundle(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: repair or delete a directory that is not what was promised."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        bundle = _prepare_bundle(owner, ids, lease)
        monkeypatch.setattr(WorkspaceAuthority, "_write_revision_from_canonical", _killed)
        with pytest.raises(SystemExit):
            _install(owner, ids, lease, bundle)
        monkeypatch.undo()

        roadmap = site.source / "worklogs" / "demo-project" / "roadmap.md"
        roadmap.write_text("edited after the install\n")

    with _reopen(site) as recovered:
        assert _intent(site, ids) is not None, "an unprovable install was completed anyway"
        assert roadmap.read_text() == "edited after the install\n", "the mismatched bytes were rewritten"
        assert site.metadata(ids)["status"] == "QUARANTINED"
        assert recovered is not None


def test_recovery_refuses_to_undo_an_install_over_drifted_canonical(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: call an early install kill 'nothing happened' without proving it."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        bundle = _prepare_bundle(owner, ids, lease)

        monkeypatch.setattr(workspace_module, "_rename_directory", _killed)
        with pytest.raises(SystemExit):
            _install(owner, ids, lease, bundle)
        monkeypatch.undo()
        (site.source / "stray.txt").write_text("written behind the authority's back\n")

    with _reopen(site) as recovered:
        assert _intent(site, ids) is not None, "drift was accepted as 'the rename never happened'"
        assert (site.source / "stray.txt").read_text() == "written behind the authority's back\n"
        assert site.metadata(ids)["status"] == "QUARANTINED"
        assert recovered is not None


# ---------------------------------------------------------------------------
# Stale `pending/` staging — discard only what is provably this authority's
# ---------------------------------------------------------------------------


def test_recovery_discards_its_own_staging_and_never_a_committed_revision(site: Site) -> None:
    """producer-kill-check: leave abandoned scratch, or sweep the revisions tree with it."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        revision = _current(site, ids)["revision_id"]
        stage = site.state / "pending" / uuid4().hex
        (stage / "revisions" / revision / "data").mkdir(parents=True, mode=0o700)
        (stage / "revisions" / revision / "data" / "half.txt").write_text("half written\n")
        stage.chmod(0o700)

    with _reopen(site) as recovered:
        assert list((site.state / "pending").iterdir()) == [], "owned staging was never classified"
        assert (_workspace(site, ids) / "revisions" / revision / "tree.json").is_file()
        assert recovered is not None


def test_recovery_refuses_staging_it_cannot_prove_it_created(site: Site) -> None:
    """producer-kill-check: delete any directory found in `pending/`."""
    with site.owner(view_profile=native_profile()):
        stray = site.state / "pending" / "not-ours"
        stray.mkdir(mode=0o700)
        (stray / "foreign.bin").write_bytes(b"someone else\n")

    with pytest.raises(SupervisorError) as refused:
        with site.owner(view_profile=native_profile()):
            pass

    assert refused.value.code == "CORRUPT_STATE"
    assert (stray / "foreign.bin").read_bytes() == b"someone else\n", "unattributable bytes were deleted"


def test_recovery_quarantines_one_workspace_without_stopping_the_others(site: Site) -> None:
    """producer-kill-check: fail the whole authority for one unsettled workspace."""
    second = site.roots / "second"
    second.mkdir()
    (second / "file.txt").write_text("second\n")
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        other = ok(lambda: site.register(owner, "second"))
        assert ok(lambda: site.claim(owner, ids))
        assert ok(lambda: site.claim(owner, other))
        planted = _planted_intent(site, ids, phase="PREPARED", next_revision="rev-" + uuid4().hex)
        planted["generation"] = 99  # an epoch that never ran here
        _write_intent(site, ids, planted)

    with _reopen(site) as recovered:
        assert _intent(site, ids) == planted
        assert site.metadata(ids)["status"] == "QUARANTINED"
        assert site.metadata(other)["status"] == "QUARANTINED"
        assert all(path.name != "intent.json" for path in (_workspace(site, other)).iterdir()), (
            "an unrelated workspace grew an intent"
        )
        assert recovered is not None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _killed(*_args: Any, **_kwargs: Any) -> None:
    """A process death: neither `except OSError` nor `except SupervisorError` sees it."""
    raise SystemExit("killed")


def _stopped_probe(owner: WorkspaceAuthority, ids: dict[str, str], lease: Any) -> Any:
    from tests.test_workspace_publication import _stop

    grant = _view(owner, ids, lease)
    _add_probe(owner, grant)
    _stop(owner, grant)
    return grant


def _planted_intent(site: Site, ids: dict[str, str], *, phase: str, next_revision: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "REVISION",
        "operation_id": "op-" + uuid4().hex,
        "workspace_id": ids["workspace_id"],
        "generation": site.metadata(ids)["generation"],
        "base_revision": _current(site, ids)["revision_id"],
        "next_revision": next_revision,
        "tree_sha256": _current(site, ids)["tree_sha256"],
        "phase": phase,
        "target_relative": None,
        "old_sha256": None,
        "new_sha256": None,
        "created_directories": [],
        "view_ref": None,
    }


def _write_intent(site: Site, ids: dict[str, str], intent: dict[str, Any]) -> None:
    path = _workspace(site, ids) / "intent.json"
    path.write_text(json.dumps(intent))
    path.chmod(0o600)  # `_private` refuses a world-readable control artifact
