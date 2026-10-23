"""E283 — CT113 `handoff`: the ONE mutator grant moves, the write epoch does not.

Classes (knowledge/skills/tests-writing):
  C0 — the authority's own rules: the settlement predicate, the wire invariants,
       the unfenced-ownership guard and the exact refusal codes;
  C1 — the real `WorkspaceAuthority` over real files and real grants (no faked
       authority, no fabricated capability, no monkeypatched proof);
  C3 — the composed `SupervisorService` over a real socket, the real journal and
       the real replay cache, for the route and the Q75 replay pair.

What must stay true (each test names the producer it kills):
  * `handoff` replaces `active_actor` and the capability in ONE durable write and
    leaves `owner_namespace`, `generation`, `status` and `revision_id` unchanged —
    the generation is never advanced (a handoff is not a new write epoch);
  * the old capability is dead for fresh work the moment the new one exists, and
    a reader pin opened before the handoff still answers its own revision;
  * every refusal (settlement, invariants, ownership, unfenced fd) happens before
    any write, so `workspace.json` is byte-identical afterwards;
  * the target must be this actor's own child run: same session, `parent_run_id`
    equal to the caller's run, and a different run;
  * the grant is resolved from the proof alone, so no request can retarget it at
    another workspace;
  * one handoff appends exactly one durable operation record, ending `DONE`, with
    no capability in it, and the same request id replays its original reply.

Not claimed here: a real `begin_run` child run, a real cgroup-backed settlement or
a deployed service. Those are `I03-LIVE-27` on the approved host.
"""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

import pytest

import fa.execution.workspace as workspace_module
from fa.execution.service import SupervisorService
from fa.execution.supervisor import PeerIdentity, SupervisorError
from fa.execution.types import GrantReply, NamespaceRef, Operation
from fa.execution.workspace import WorkspaceAuthority
from tests.test_execution_readers import pin, read, ref
from tests.test_execution_service import _config, _registered, _writer, exchange
from tests.test_execution_views import native_profile
from tests.test_execution_workspace import ACTOR, PEER, Site, ok, until
from tests.test_execution_workspace import site as site
from tests.test_workspace_publication import _seal, _stopped

CHILD = NamespaceRef("session-a", "run-child", "run-a")
GRANDCHILD = NamespaceRef("session-a", "run-grandchild", "run-child")
HEX = frozenset("0123456789abcdef")


def workspace_file(site: Site, ids: dict[str, str]) -> Path:
    return site.state / "workspaces" / ids["workspace_id"] / "workspace.json"


def view_file(site: Site, grant: GrantReply) -> Path:
    reference = ref(grant)
    return site.state / "workspaces" / reference.workspace_id / "views" / reference.view_id / "view.json"


def move(
    owner: WorkspaceAuthority,
    grant: GrantReply,
    target: NamespaceRef = CHILD,
    **kwargs: Any,
) -> GrantReply:
    return owner.handoff(
        kwargs.get("peer", PEER),
        kwargs.get("namespace", ACTOR),
        target=kwargs.get("target", target),
        capability=kwargs.get("capability", grant.capability),
        deadline=kwargs.get("deadline", until()),
    )


# ---------------------------------------------------------------------------
# C0/C1 — the authority's own rules
# ---------------------------------------------------------------------------


def test_handoff_moves_the_grant_without_advancing_the_generation(site: Site) -> None:
    """producer-kill-check: advance the generation (or skip the replace) on handoff."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        retained = ok(lambda: pin(owner, ids))
        before = site.metadata(ids)

        moved = ok(lambda: move(owner, lease))

        after = site.metadata(ids)
        # ONE field moved and nothing else: the epoch, the root owner and the
        # status are exactly the values they were before the call.
        assert after == {**before, "active_actor": CHILD.to_dict()}
        assert after["generation"] == before["generation"]
        assert after["owner_namespace"] == before["owner_namespace"] == ACTOR.to_dict()
        assert after["status"] == "OWNED"
        current = json.loads((site.state / "workspaces" / ids["workspace_id"] / "current.json").read_text())
        assert current["revision_id"] == ids["revision_id"]

        assert isinstance(moved, GrantReply) and moved.operation is Operation.HANDOFF
        assert moved.view_ref is None
        assert moved.generation == before["generation"] and moved.revision_id == ids["revision_id"]
        assert moved.capability != lease.capability
        assert len(moved.capability) == 64 and set(moved.capability) <= HEX
        assert moved.capability.encode() not in workspace_file(site, ids).read_bytes()

        # The new capability is the only live proof, and the old one is dead.
        with pytest.raises(SupervisorError) as rejected:
            site.release(owner, ids, lease)
        assert rejected.value.code == "UNAUTHORIZED"
        with pytest.raises(SupervisorError) as rejected:
            site.claim(owner, ids)
        assert rejected.value.code == "WORKSPACE_BUSY"

        # The reader pin opened before the move still answers its own revision:
        # a handoff is not a generation, so `view_ref.generation` still matches.
        # (The pinned bytes are the exact R0 input, not a re-materialization.)
        assert ok(lambda: read(owner, retained))["content"] == "untracked"
        assert ref(retained).generation == before["generation"]

        # The child holds the writer and can settle it; the next claim advances
        # exactly one generation, proving the handoff consumed none.
        assert ok(lambda: site.release(owner, ids, moved, actor=CHILD)) == {"released": True}
        next_lease = ok(lambda: site.claim(owner, ids))
        assert next_lease.generation == before["generation"] + 1
        assert next_lease.capability not in {lease.capability, moved.capability}


@pytest.mark.parametrize("pending", ["open-view", "sealed-view", "intent"])
def test_nothing_unsettled_may_move_the_grant(site: Site, pending: str) -> None:
    """producer-kill-check: skip the settlement predicate, or settle on `SEALED`."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        if pending == "intent":
            (site.state / "workspaces" / ids["workspace_id"] / "intent.json").write_text("unfinished")
        else:
            view = ok(lambda: _stopped(owner, ids, lease))
            if pending == "sealed-view":
                assert ok(lambda: _seal(owner, view)) is not None
                assert json.loads(view_file(site, view).read_text())["state"] == "SEALED"
        before = workspace_file(site, ids).read_bytes()

        with pytest.raises(SupervisorError) as rejected:
            move(owner, lease)

        assert rejected.value.code == "WORKSPACE_BUSY"
        assert workspace_file(site, ids).read_bytes() == before
        assert site.metadata(ids)["active_actor"] == ACTOR.to_dict()


@pytest.mark.parametrize(
    "target",
    [
        {"session_id": "session-b", "run_id": "run-child", "parent_run_id": "run-a"},
        {"session_id": "session-a", "run_id": "run-child", "parent_run_id": "run-b"},
        {"session_id": "session-a", "run_id": "run-child", "parent_run_id": None},
        {"session_id": "session-a", "run_id": "run-a", "parent_run_id": "run-a"},
    ],
    ids=["foreign-session", "wrong-parent", "no-parent", "self-target"],
)
def test_only_the_callers_own_child_may_receive_the_grant(site: Site, target: dict[str, Any]) -> None:
    """producer-kill-check: drop a wire invariant, or check them after the swap."""
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        before = workspace_file(site, ids).read_bytes()

        with pytest.raises(SupervisorError) as rejected:
            move(owner, lease, target=NamespaceRef(**target))

        assert rejected.value.code == "INPUT_POLICY"
        assert workspace_file(site, ids).read_bytes() == before
        # Nothing moved: the caller's own grant still settles the workspace.
        assert ok(lambda: site.release(owner, ids, lease)) == {"released": True}


@pytest.mark.parametrize("wrong", ["principal", "actor", "token"])
def test_a_foreign_peer_namespace_or_capability_cannot_move_the_grant(site: Site, wrong: str) -> None:
    """producer-kill-check: resolve the binding without the exact owner proof."""
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        kwargs = (
            {"peer": PeerIdentity(PEER.pid, PEER.uid, PEER.gid + 1)}
            if wrong == "principal"
            else {"namespace": NamespaceRef("session-b", "run-b")}
            if wrong == "actor"
            else {"capability": secrets.token_hex(32)}
        )
        before = workspace_file(site, ids).read_bytes()

        with pytest.raises(SupervisorError) as rejected:
            move(owner, lease, **kwargs)

        assert rejected.value.code == "UNAUTHORIZED"
        assert workspace_file(site, ids).read_bytes() == before


def test_an_unfenced_ownership_cannot_be_moved(site: Site) -> None:
    """producer-kill-check: move ownership without the live writer fd this process holds."""
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        # White box on purpose: close only the fd, keeping the grant, so the
        # guard against moving an ownership this process cannot fence is the
        # producer under test rather than the ownership proof.
        binding = owner._binding(ids["workspace_id"])
        assert binding.writer is not None
        os.close(binding.writer)
        binding.writer = None
        before = workspace_file(site, ids).read_bytes()

        with pytest.raises(SupervisorError) as rejected:
            move(owner, lease)

        assert rejected.value.code == "STALE_GENERATION"
        assert workspace_file(site, ids).read_bytes() == before


def test_the_chain_child_to_grandchild_keeps_one_generation(site: Site) -> None:
    """producer-kill-check: model handoff as a one-shot transfer instead of a chain."""
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        generation = site.metadata(ids)["generation"]

        child = ok(lambda: move(owner, lease))
        grandchild = ok(lambda: move(owner, child, target=GRANDCHILD, namespace=CHILD))

        assert child.generation == grandchild.generation == generation
        assert len({lease.capability, child.capability, grandchild.capability}) == 3
        assert site.metadata(ids)["active_actor"] == GRANDCHILD.to_dict()
        assert site.metadata(ids)["generation"] == generation
        # Only the grandchild can settle it, and the move renewed nothing.
        with pytest.raises(SupervisorError) as rejected:
            site.release(owner, ids, child, actor=CHILD)
        assert rejected.value.code == "UNAUTHORIZED"
        assert ok(lambda: site.release(owner, ids, grandchild, actor=GRANDCHILD)) == {"released": True}


def test_the_grant_is_resolved_from_its_proof_and_never_retargeted(site: Site) -> None:
    """producer-kill-check: let a request name the workspace whose grant it moves."""
    (site.roots / "other").mkdir()
    with site.owner() as owner:
        first = ok(lambda: site.register(owner))
        second = ok(lambda: site.register(owner, relative="other"))
        first_lease = ok(lambda: site.claim(owner, first))
        second_lease = ok(lambda: site.claim(owner, second))

        moved = ok(lambda: move(owner, first_lease))

        # Only the proved binding moved; the other workspace keeps its own grant.
        assert site.metadata(first)["active_actor"] == CHILD.to_dict()
        assert site.metadata(second)["active_actor"] == ACTOR.to_dict()
        assert site.metadata(second)["generation"] == 2
        assert ok(lambda: site.release(owner, second, second_lease)) == {"released": True}
        with pytest.raises(SupervisorError) as rejected:
            site.release(owner, second, moved)
        assert rejected.value.code == "UNAUTHORIZED"


def test_a_grant_is_never_returned_unless_the_swap_reads_back(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    """producer-kill-check: drop the read-back, so an unproven capability ships."""
    with site.owner() as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        before = workspace_file(site, ids).read_bytes()

        # A replace that silently loses the swap: the durable bytes keep the OLD
        # actor while memory already moved. The authority must refuse the grant
        # and degrade, because recovery owns this workspace from now on.
        original = workspace_module._replace_private_bytes
        monkeypatch.setattr(
            workspace_module,
            "_replace_private_bytes",
            lambda directory_fd, name, raw: original(directory_fd, name, before),
        )

        with pytest.raises(SupervisorError) as rejected:
            move(owner, lease)

        assert rejected.value.code == "DURABILITY_UNKNOWN"
        assert owner.ready is False
        assert workspace_file(site, ids).read_bytes() == before
        with pytest.raises(SupervisorError) as poisoned:
            site.claim(owner, ids)
        assert poisoned.value.code == "CORRUPT_STATE"


# ---------------------------------------------------------------------------
# C3 — the composed route: one durable record, no capability, Q75 replay pair
# ---------------------------------------------------------------------------


def test_the_route_rotates_the_capability_and_reserves_exactly_one_record(site: Site) -> None:
    """producer-kill-check: route `handoff` to a stub, or lose the Q75 replay pair."""
    with SupervisorService(_config(site)) as service:
        workspace_id = _registered(service)
        capability, revision_id = _writer(service, workspace_id, request_id="2" * 32)
        generation = service.authority._binding(workspace_id).metadata["generation"]
        request_id = "7" * 32

        reply = exchange(
            service,
            Operation.HANDOFF,
            {"target_namespace": CHILD.to_dict()},
            request_id=request_id,
            capability=capability,
        )
        assert reply["status"] == "OK", reply
        moved = reply["result"]
        assert set(moved) == {"view_ref", "capability", "generation", "revision_id"}
        assert moved["view_ref"] is None and moved["generation"] == generation
        assert moved["revision_id"] == revision_id and moved["capability"] != capability

        # One durable record, ending DONE, with no capability in it (§5).
        record = site.state / "operations" / f"op-{request_id}.json"
        assert json.loads(record.read_text())["state"] == "DONE"
        raw = record.read_bytes()
        assert capability.encode() not in raw and moved["capability"].encode() not in raw

        # Q75: the same request id with the ORIGINAL proof replays that reply…
        replayed = exchange(
            service,
            Operation.HANDOFF,
            {"target_namespace": CHILD.to_dict()},
            request_id=request_id,
            capability=capability,
        )
        assert replayed["status"] == "OK" and replayed["result"] == moved
        # …while a NEW request id with the old proof is refused, not renewed.
        refused = exchange(
            service,
            Operation.HANDOFF,
            {"target_namespace": CHILD.to_dict()},
            request_id="8" * 32,
            capability=capability,
        )
        assert refused["status"] == "ERROR" and refused["error"]["code"] == "UNAUTHORIZED"

        # The child's proof is real: it opens a WRITE view at the same generation.
        view = exchange(
            service,
            Operation.CREATE_VIEW,
            {
                "workspace_id": workspace_id,
                "base_revision": revision_id,
                "access": "WRITE",
                "purpose": "PROJECT",
                "candidate_scope": None,
                "plan_ref": None,
            },
            request_id="6" * 32,
            namespace=CHILD.to_dict(),
            capability=moved["capability"],
        )
        assert view["status"] == "OK", view
        assert view["result"]["view_ref"]["generation"] == generation
        assert view["result"]["view_ref"]["owner_run_id"] == CHILD.run_id


def test_the_route_refuses_with_the_authority_code_not_the_stub(site: Site) -> None:
    """producer-kill-check: keep the E277 `BACKEND_UNAVAILABLE` stub in place."""
    with SupervisorService(_config(site)) as service:
        workspace_id = _registered(service)
        capability, _ = _writer(service, workspace_id, request_id="2" * 32)
        bad_target = {"session_id": "session-a", "run_id": "run-child", "parent_run_id": "run-b"}
        reply = exchange(
            service,
            Operation.HANDOFF,
            {"target_namespace": bad_target},
            request_id="5" * 32,
            capability=capability,
        )
        assert reply["status"] == "ERROR"
        # The authority answered, so the wire never claims the backend is missing.
        assert reply["error"]["code"] == "INPUT_POLICY"
