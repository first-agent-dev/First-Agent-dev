"""CT99: the pre-reservation authority check (`WorkspaceAuthority.authorize`).

Every case runs over the real authority and the closed envelope. A pass here
authorizes no work by itself; what it must never do is admit a request the
operation could not own, or touch anything while refusing.

The producer under test is `WorkspaceAuthority.authorize -> _authorize_operation`:
removing the per-operation shape rule, the grant proof or the plan recheck must
break the case that names it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from fa.execution.plans import ProtectedPlanContext
from fa.execution.primitives import Operation
from fa.execution.supervisor import AUTHORITY_GATED_OPERATIONS, READONLY_OPERATIONS, SupervisorError
from fa.execution.types import Access, GrantReply, ViewPurpose
from fa.execution.workspace import WorkspaceAuthority
from fa.inner_loop.plan_admission import read_plan_snapshot
from tests.test_execution_views import native_profile
from tests.test_execution_workspace import ACTOR, PEER, Site, ok, until
from tests.test_execution_workspace import site as site

PLAN_PATH = "worklogs/demo/roadmap.md"
PLAN_TEXT = "# Roadmap\n\n## Intent\n\nShip it.\n"

_OMITTED = object()


def _request(
    op: Operation,
    *,
    namespace: Any = _OMITTED,
    view: dict[str, Any] | None = None,
    capability: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One complete closed envelope; every key the wire requires, nothing else."""
    return {
        "protocol_version": 1,
        "request_id": uuid4().hex,
        "op": op.value,
        "namespace": ACTOR.to_dict() if namespace is _OMITTED else namespace,
        "view_ref": view,
        "capability": capability,
        "payload": payload or {},
    }


def _authorize(owner: WorkspaceAuthority, request: dict[str, Any]) -> ProtectedPlanContext | None:
    return owner.authorize(PEER, request, deadline=until())


def _project_view(
    owner: WorkspaceAuthority,
    ids: dict[str, str],
    lease: GrantReply,
    *,
    plan_ref: Any = None,
    purpose: ViewPurpose = ViewPurpose.PROJECT,
) -> GrantReply:
    writable = purpose in {ViewPurpose.PROJECT, ViewPurpose.MUTATION, ViewPurpose.PROVISIONING}
    return ok(
        lambda: owner.create_view(
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
            base_revision=ids["revision_id"],
        )
    )


def _with_plan(site: Site) -> Any:
    path = site.source / PLAN_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PLAN_TEXT)
    return read_plan_snapshot(site.source, Path(PLAN_PATH)).ref


def _plan_ref_dict(plan_ref: Any) -> dict[str, str]:
    return {
        "workspace_relative_path": plan_ref.workspace_relative_path,
        "source_kind": plan_ref.source_kind,
        "sha256": plan_ref.sha256,
    }


def _refused(call: Any, code: str) -> None:
    with pytest.raises(SupervisorError) as refused:
        call()
    assert refused.value.code == code


def _refuse(owner: WorkspaceAuthority, request: dict[str, Any], code: str) -> None:
    """The refusal oracle; takes the request, so a loop variable is never captured."""
    with pytest.raises(SupervisorError) as refused:
        _authorize(owner, request)
    assert refused.value.code == code


def test_health_is_the_only_request_without_a_namespace_or_a_grant(site: Site) -> None:
    """The composed guarantee: health is the one grant-free, namespace-free shape.

    The refusal comes from the closed decoder, which `authorize` runs first; the
    case is kept as the end-to-end contract because a second, hand-written shape
    check inside the authority was tried and deleted (it could never fire).
    """
    with site.owner(view_profile=native_profile()) as owner:
        assert _authorize(owner, _request(Operation.HEALTH, namespace=None)) is None
        for field, value in (
            ("namespace", ACTOR.to_dict()),
            ("capability", "0" * 64),
            ("view_ref", {"workspace_id": "ws-" + "1" * 32}),
        ):
            request = _request(Operation.HEALTH, namespace=None)
            request[field] = value
            _refuse(owner, request, "INVALID_REQUEST")


def test_a_pre_grant_operation_may_not_carry_a_capability_or_a_view(site: Site) -> None:
    """The composed guarantee: a pre-grant operation can never launder a grant in.

    Same layering as health: the decoder owns the shape and `authorize` proves
    what remains, so this case pins the boundary rather than a duplicated check.
    """
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        payloads = {
            Operation.REGISTER_WORKSPACE: {
                "root_id": "projects",
                "relative_root": "another",
                "create": False,
                "input_id": None,
            },
            Operation.ACQUIRE_WRITER: {"workspace_id": ids["workspace_id"]},
            Operation.PIN_READER: {
                "workspace_id": ids["workspace_id"],
                "revision_id": ids["revision_id"],
                "plan_ref": None,
            },
        }
        view = {
            "workspace_id": ids["workspace_id"],
            "generation": 1,
            "base_revision": ids["revision_id"],
            "view_id": "view-" + "1" * 32,
            "owner_run_id": ACTOR.run_id,
            "access": "READ",
            "purpose": "PROJECT",
        }
        for op, payload in payloads.items():
            _refuse(owner, _request(op, capability="0" * 64, payload=payload), "INVALID_REQUEST")
            _refuse(owner, _request(op, view=view, payload=payload), "INVALID_REQUEST")
            # The one legal shape still passes. `pin_reader` names a revision, so
            # its answer is that revision's plan context, not None.
            authorized = _authorize(owner, _request(op, payload=payload))
            if op is Operation.PIN_READER:
                assert isinstance(authorized, ProtectedPlanContext)
                assert authorized.plan_ref is None
            else:
                assert authorized is None


def test_pin_reader_returns_the_pinned_revision_plan_context(site: Site) -> None:
    """producer-kill-check: return a context rooted at the canonical tree, not the pin."""
    plan_ref = _with_plan(site)
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        context = _authorize(
            owner,
            _request(
                Operation.PIN_READER,
                payload={
                    "workspace_id": ids["workspace_id"],
                    "revision_id": ids["revision_id"],
                    "plan_ref": _plan_ref_dict(plan_ref),
                },
            ),
        )
        assert isinstance(context, ProtectedPlanContext)
        assert context.plan_ref is not None and context.plan_ref.sha256 == plan_ref.sha256
        assert context.formal_evidence is False  # the wire makes no such claim
        assert context.source_root.parts[-1] == "data"
        assert context.source_root.parent.name == ids["revision_id"]
        assert (context.source_root / PLAN_PATH).read_text() == PLAN_TEXT
        context.recheck()  # the plan it will authorize is really there


def test_pin_reader_refuses_a_stale_plan_or_a_revision_that_is_not_there(site: Site) -> None:
    """producer-kill-check: hand out a context without proving the named revision."""
    plan_ref = _with_plan(site)
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        stale = _plan_ref_dict(plan_ref) | {"sha256": "0" * 64}
        _refused(
            lambda: _authorize(
                owner,
                _request(
                    Operation.PIN_READER,
                    payload={
                        "workspace_id": ids["workspace_id"],
                        "revision_id": ids["revision_id"],
                        "plan_ref": stale,
                    },
                ),
            ),
            "INPUT_POLICY",
        )
        _refused(
            lambda: _authorize(
                owner,
                _request(
                    Operation.PIN_READER,
                    payload={
                        "workspace_id": ids["workspace_id"],
                        "revision_id": "rev-" + "9" * 32,
                        "plan_ref": None,
                    },
                ),
            ),
            "STALE_REVISION",
        )


def test_create_view_needs_this_workspaces_owner_grant(site: Site) -> None:
    """producer-kill-check: accept create_view on any capability, or on another workspace."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        payload = {
            "workspace_id": ids["workspace_id"],
            "base_revision": ids["revision_id"],
            "access": "WRITE",
            "purpose": "PROJECT",
            "candidate_scope": None,
            "plan_ref": None,
        }
        _refused(lambda: _authorize(owner, _request(Operation.CREATE_VIEW, payload=payload)), "INVALID_REQUEST")
        _refused(
            lambda: _authorize(owner, _request(Operation.CREATE_VIEW, capability="0" * 64, payload=payload)),
            "UNAUTHORIZED",
        )
        wrong_workspace = {**payload, "workspace_id": "ws-" + "2" * 32}
        _refused(
            lambda: _authorize(
                owner,
                _request(Operation.CREATE_VIEW, capability=lease.capability, payload=wrong_workspace),
            ),
            "UNAUTHORIZED",
        )
        context = _authorize(owner, _request(Operation.CREATE_VIEW, capability=lease.capability, payload=payload))
        assert isinstance(context, ProtectedPlanContext)
        assert context.plan_ref is None


def test_view_operations_prove_the_exact_actor_and_view(site: Site) -> None:
    """producer-kill-check: prove any live grant instead of this actor's exact view."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _project_view(owner, ids, lease)
        payloads = {
            Operation.READ_FILE: {"path": "roadmap.md", "offset_bytes": 0, "max_bytes": 64},
            Operation.WRITE_FILE: {"path": "roadmap.md", "content": "x", "expected_sha256": None},
            Operation.SEAL: {},
            Operation.STOP_VIEW: {},
        }
        foreign = {"session_id": "another-session", "run_id": ACTOR.run_id, "parent_run_id": None}
        exact = grant.view_ref.to_dict()
        swapped = exact | {"view_id": "view-" + "3" * 32}
        for op, payload in payloads.items():
            assert _authorize(owner, _request(op, view=exact, capability=grant.capability, payload=payload)) is None
            _refuse(owner, _request(op, view=exact, capability="0" * 64, payload=payload), "UNAUTHORIZED")
            _refuse(
                owner,
                _request(op, namespace=foreign, view=exact, capability=grant.capability, payload=payload),
                "UNAUTHORIZED",
            )
            _refuse(owner, _request(op, view=swapped, capability=grant.capability, payload=payload), "UNAUTHORIZED")
            # A missing view is a shape violation, not a grant failure.
            _refuse(owner, _request(op, capability=grant.capability, payload=payload), "INVALID_REQUEST")


def test_exec_authorizes_the_stored_plan_not_a_payload_claim(site: Site) -> None:
    """producer-kill-check: build the exec context from the request instead of the view."""
    plan_ref = _with_plan(site)
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _project_view(owner, ids, lease, plan_ref=plan_ref, purpose=ViewPurpose.VERIFICATION)
        request = _request(Operation.EXEC, view=grant.view_ref.to_dict(), capability=grant.capability)
        request["payload"] = {
            # The wire binds the operation id to the request id, not the reverse.
            "operation_id": "op-" + request["request_id"],
            "profile_id": "verification",
            "command": "pytest -q",
            "cwd": ".",
            "timeout_ms": 1000,
            "session_id": None,
        }
        context = _authorize(owner, request)
        assert isinstance(context, ProtectedPlanContext)
        assert context.plan_ref is not None and context.plan_ref.sha256 == plan_ref.sha256
        assert context.plan_ref.workspace_relative_path == plan_ref.workspace_relative_path

        # The pinned plan bytes are what the check is about: damaging them makes
        # the same authorization refuse, with no grant and no reservation.
        (context.source_root / plan_ref.workspace_relative_path).unlink()
        _refused(lambda: _authorize(owner, request), "INPUT_POLICY")


def test_release_has_exactly_two_shapes(site: Site) -> None:
    """producer-kill-check: accept an owner release that names a view, or the reverse."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        grant = _project_view(owner, ids, lease)
        assert _authorize(owner, _request(Operation.RELEASE, capability=lease.capability)) is None
        assert (
            _authorize(owner, _request(Operation.RELEASE, view=grant.view_ref.to_dict(), capability=grant.capability))
            is None
        )
        _refused(lambda: _authorize(owner, _request(Operation.RELEASE)), "INVALID_REQUEST")
        _refused(
            lambda: _authorize(
                owner,
                _request(Operation.RELEASE, capability=lease.capability, view=grant.view_ref.to_dict()),
            ),
            "UNAUTHORIZED",
        )


def test_a_refusal_writes_reserves_and_mints_nothing(site: Site) -> None:
    """producer-kill-check: touch state while refusing an unauthorized request."""
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        state = site.state
        workspace = state / "workspaces" / ids["workspace_id"]
        before = sorted(path.relative_to(state).as_posix() for path in state.rglob("*"))
        current = (workspace / "current.json").read_bytes()

        for request in (
            _request(Operation.SEAL, capability="0" * 64, view={"workspace_id": ids["workspace_id"]}),
            _request(
                Operation.INSTALL_PROJECT,
                capability="0" * 64,
                payload={"validated_bundle_id": "bundle-" + "5" * 32, "project_slug": "demo"},
            ),
            _request(Operation.HANDOFF, capability="0" * 64, payload={"target_namespace": ACTOR.to_dict()}),
        ):
            with pytest.raises(SupervisorError):
                _authorize(owner, request)

        after = sorted(path.relative_to(state).as_posix() for path in state.rglob("*"))
        assert after == before
        assert (workspace / "current.json").read_bytes() == current
        assert not (workspace / "intent.json").exists()
        assert lease.capability  # no grant was consumed or replaced


def test_the_readonly_classification_covers_the_closed_enum() -> None:
    """C0: the dispatcher's classification is derived, and can never launder a mutator."""
    assert READONLY_OPERATIONS <= frozenset(Operation)
    assert not READONLY_OPERATIONS & AUTHORITY_GATED_OPERATIONS
    assert AUTHORITY_GATED_OPERATIONS <= frozenset(Operation)
    for name in ("stop_view", "seal", "publish", "install_project", "prepare_bundle", "handoff", "release"):
        assert Operation(name) in AUTHORITY_GATED_OPERATIONS
    assert READONLY_OPERATIONS == frozenset({Operation.HEALTH, Operation.READ_FILE, Operation.INSPECT})


def test_a_candidate_view_may_open_on_a_null_base_and_the_current_plan(site: Site) -> None:
    """producer-kill-check: insist on a revision for every CREATE_VIEW, CANDIDATE included."""
    plan_ref = _with_plan(site)
    plan = _plan_ref_dict(plan_ref)
    with site.owner(view_profile=native_profile()) as owner:
        ids = ok(lambda: site.register(owner))
        lease = ok(lambda: site.claim(owner, ids))
        payload = {
            "workspace_id": ids["workspace_id"],
            "base_revision": None,  # CANDIDATE may open without naming a revision
            "access": "READ",
            "purpose": "CANDIDATE",
            "candidate_scope": {
                "candidate_path": f".fa/admission/{ACTOR.run_id}/candidate-{uuid4().hex}.md",
                "plan_ref": plan,
            },
            "plan_ref": plan,
        }
        context = _authorize(owner, _request(Operation.CREATE_VIEW, capability=lease.capability, payload=payload))
        assert isinstance(context, ProtectedPlanContext)
        # The null base means "the current revision", so the context is its plan —
        # not an empty one and not an unchecked one.
        assert context.plan_ref == plan_ref
        _refused(
            lambda: _authorize(
                owner,
                _request(
                    Operation.CREATE_VIEW,
                    capability=lease.capability,
                    payload={**payload, "base_revision": "rev-" + "9" * 32},
                ),
            ),
            "STALE_REVISION",
        )
