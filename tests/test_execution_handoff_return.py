"""Q102: a live writer returns only along the exact delegation path."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from fa.execution.client import _grant
from fa.execution.composition import ExecutionBinding, ManagedExecution
from fa.execution.supervisor import SupervisorError
from fa.execution.types import Access, NamespaceRef, Operation, ViewPurpose
from fa.inner_loop.plan_admission import read_plan_snapshot, snapshot_from_bytes
from tests.test_execution_client_port import PLAN_RELATIVE, _plan_ref, _served
from tests.test_execution_handoff import CHILD, GRANDCHILD, move, workspace_file
from tests.test_execution_views import create, native_profile
from tests.test_execution_workspace import ACTOR, Site, ok
from tests.test_execution_workspace import site as site


def test_return_follows_full_parent_lineage_and_rotates_every_grant(site: Site) -> None:
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        original = ok(lambda: site.claim(owner, ids))
        child = ok(lambda: move(owner, original))
        grandchild = ok(lambda: move(owner, child, namespace=CHILD, target=GRANDCHILD))
        returned_child = ok(lambda: move(owner, grandchild, namespace=GRANDCHILD, target=CHILD))
        returned_parent = ok(lambda: move(owner, returned_child, namespace=CHILD, target=ACTOR))

        assert len({g.capability for g in (original, child, grandchild, returned_child, returned_parent)}) == 5
        assert all(g.generation == original.generation for g in (child, grandchild, returned_child, returned_parent))
        assert site.metadata(ids)["active_actor"] == ACTOR.to_dict()
        for grant, actor in ((original, ACTOR), (child, CHILD), (grandchild, GRANDCHILD), (returned_child, CHILD)):
            with pytest.raises(SupervisorError) as refused:
                site.release(owner, ids, grant, actor=actor)
            assert refused.value.code == "UNAUTHORIZED"
        assert ok(lambda: site.release(owner, ids, returned_parent, actor=ACTOR)) == {"released": True}
        new_owner = ok(lambda: site.claim(owner, ids))
        with pytest.raises(SupervisorError) as refused:
            move(owner, new_owner, target=CHILD, namespace=CHILD)
        assert refused.value.code == "UNAUTHORIZED"


@pytest.mark.parametrize(
    "target",
    [
        NamespaceRef("session-a", "run-a", "run-forged"),
        NamespaceRef("session-a", "run-other"),
        NamespaceRef("session-b", "run-a"),
        NamespaceRef("session-a", "run-a", "run-child"),
    ],
)
def test_unrelated_or_forged_parent_cannot_receive_the_writer(site: Site, target: NamespaceRef) -> None:
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        parent = ok(lambda: site.claim(owner, ids))
        child = ok(lambda: move(owner, parent))
        before = workspace_file(site, ids).read_bytes()
        with pytest.raises(SupervisorError) as refused:
            move(owner, child, namespace=CHILD, target=target)
        assert refused.value.code == "INPUT_POLICY"
        assert workspace_file(site, ids).read_bytes() == before
        assert ok(lambda: move(owner, child, namespace=CHILD, target=ACTOR)).generation == parent.generation


def test_unsettled_child_cannot_return_the_writer(site: Site) -> None:
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        parent = ok(lambda: site.claim(owner, ids))
        child = ok(lambda: move(owner, parent))
        ok(lambda: create(owner, ids, child, namespace=CHILD))
        before = workspace_file(site, ids).read_bytes()
        with pytest.raises(SupervisorError) as refused:
            move(owner, child, namespace=CHILD, target=ACTOR)
        assert refused.value.code == "WORKSPACE_BUSY"
        assert workspace_file(site, ids).read_bytes() == before


def test_return_and_child_client_verbs_over_real_socket(site: Site, tmp_path: Path) -> None:
    _plan_ref(site)
    with _served(site, tmp_path) as parent:
        child_ns = NamespaceRef(parent.binding.namespace.session_id, "child-run", parent.binding.namespace.run_id)
        raw = parent.client.request(
            Operation.HANDOFF,
            request_id=uuid4().hex,
            namespace=parent.binding.namespace,
            view=None,
            grant=parent.grant,
            payload={"target_namespace": child_ns.to_dict()},
            deadline=None,
        )
        child_grant = _grant(Operation.HANDOFF, raw)
        child = ManagedExecution(parent.client, ExecutionBinding(child_ns, parent.binding.workspace_id), child_grant)
        published = child.publish_plan(
            read_plan_snapshot(site.source, Path(PLAN_RELATIVE)),
            snapshot_from_bytes("draft.md", b"# child plan\n"),
        )
        stage = child.open_view(
            access=Access.WRITE,
            purpose=ViewPurpose.MUTATION,
            base_revision=published.revision_id,
            plan_ref=published.plan_ref,
        )
        stage_result = child.publish_stage(stage)
        result = child.client.request(
            Operation.HANDOFF,
            request_id=uuid4().hex,
            namespace=child_ns,
            view=None,
            grant=child_grant,
            payload={"target_namespace": parent.binding.namespace.to_dict()},
            deadline=None,
        )
        returned = _grant(Operation.HANDOFF, result)
        assert returned.generation == parent.grant.generation
        assert returned.revision_id == stage_result.revision_id
        assert returned.capability not in {parent.grant.capability, child_grant.capability}
        refreshed_parent = ManagedExecution(parent.client, parent.binding, returned)
        assert refreshed_parent.close()


def test_restart_with_child_owner_quarantines_instead_of_recreating_lineage(site: Site) -> None:
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        parent = ok(lambda: site.claim(owner, ids))
        child = ok(lambda: move(owner, parent))
    with site.owner() as restarted:
        assert site.metadata(ids)["status"] == "QUARANTINED"
        with pytest.raises(SupervisorError):
            move(restarted, child, namespace=CHILD, target=ACTOR)
        assert site.metadata(ids)["status"] == "QUARANTINED"
