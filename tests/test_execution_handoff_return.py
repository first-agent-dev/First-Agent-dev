"""Q102: a live writer returns only along the exact delegation path."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fa.execution.client import ExecutionRejectedError, ExecutionUncertainError
from fa.execution.composition import ExecutionBinding
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


def test_return_and_child_client_verbs_over_real_socket(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _plan_ref(site)
    with _served(site, tmp_path) as managed:
        parent_binding = managed.binding
        parent_grant = managed.grant
        child_ns = NamespaceRef(parent_binding.namespace.session_id, "child-run", parent_binding.namespace.run_id)
        invalid_child = NamespaceRef(parent_binding.namespace.session_id, "child-run", "not-the-parent")

        with pytest.raises(ExecutionRejectedError):
            managed.handoff_to(invalid_child)
        assert not managed.handoff_pending
        assert managed.binding is parent_binding and managed.grant is parent_grant

        real_request = managed.client.request
        seen: list[tuple[Operation, str, NamespaceRef, object, dict[str, object]]] = []
        lose_first_reply = True

        def lose_first_handoff_reply(operation: Operation, **kwargs: Any) -> dict[str, object]:
            nonlocal lose_first_reply
            if operation is Operation.HANDOFF:
                seen.append(
                    (
                        operation,
                        str(kwargs["request_id"]),
                        kwargs["namespace"],
                        kwargs["grant"],
                        kwargs["payload"],
                    )
                )
            result = real_request(operation, **kwargs)
            if operation is Operation.HANDOFF and lose_first_reply:
                lose_first_reply = False
                raise ExecutionUncertainError("op-" + str(kwargs["request_id"]))
            return result

        monkeypatch.setattr(managed.client, "request", lose_first_handoff_reply)
        with pytest.raises(ExecutionUncertainError):
            managed.handoff_to(child_ns)
        assert managed.handoff_pending
        assert managed.binding is parent_binding and managed.grant is parent_grant

        child_grant = managed.reconcile_handoff()
        assert not managed.handoff_pending
        assert managed.binding == ExecutionBinding(child_ns, parent_binding.workspace_id)
        assert len(seen) == 2 and seen[0][1] == seen[1][1]
        assert seen[0][2] == seen[1][2] == parent_binding.namespace
        assert seen[0][3] is seen[1][3] is parent_grant
        assert seen[0][4] == seen[1][4] == {"target_namespace": child_ns.to_dict()}
        assert child_grant.operation is Operation.HANDOFF

        published = managed.publish_plan(
            read_plan_snapshot(site.source, Path(PLAN_RELATIVE)),
            snapshot_from_bytes("draft.md", b"# child plan\n"),
        )
        stage = managed.open_view(
            access=Access.WRITE,
            purpose=ViewPurpose.MUTATION,
            base_revision=published.revision_id,
            plan_ref=published.plan_ref,
        )
        stage_result = managed.publish_stage(stage)
        returned = managed.handoff_to(parent_binding.namespace)
        assert managed.binding == parent_binding
        assert returned.generation == parent_grant.generation
        assert returned.revision_id == stage_result.revision_id
        assert returned.capability not in {parent_grant.capability, child_grant.capability}
        assert managed.close()


def test_unresolved_handoff_keeps_writer_and_blocks_all_other_operations(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _served(site, tmp_path) as managed:
        parent_binding = managed.binding
        child_ns = NamespaceRef(parent_binding.namespace.session_id, "child-run", parent_binding.namespace.run_id)
        real_request = managed.client.request
        handoffs: list[tuple[str, NamespaceRef, object, dict[str, object]]] = []
        operations: list[Operation] = []

        def lose_every_handoff_reply(operation: Operation, **kwargs: Any) -> dict[str, object]:
            operations.append(operation)
            result = real_request(operation, **kwargs)
            if operation is Operation.HANDOFF:
                handoffs.append(
                    (
                        str(kwargs["request_id"]),
                        kwargs["namespace"],
                        kwargs["grant"],
                        kwargs["payload"],
                    )
                )
                raise ExecutionUncertainError("op-" + str(kwargs["request_id"]))
            return result

        monkeypatch.setattr(managed.client, "request", lose_every_handoff_reply)
        with pytest.raises(ExecutionUncertainError):
            managed.handoff_to(child_ns)
        with pytest.raises(ExecutionUncertainError):
            managed.reconcile_handoff()
        assert managed.handoff_pending
        assert managed.binding is parent_binding
        with pytest.raises(ExecutionUncertainError):
            managed.open_view(
                access=Access.WRITE,
                purpose=ViewPurpose.PROJECT,
                base_revision=managed.current_revision_id,
            )
        assert managed.close() is False
        assert len(handoffs) == 2
        assert handoffs[0] == handoffs[1]
        assert handoffs[0][2] is managed.grant
        assert operations == [Operation.HANDOFF, Operation.HANDOFF]


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
