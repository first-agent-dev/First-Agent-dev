"""C0/C3 replay/type proof only; NOT C1 service, journal or kernel proof.

The caller is deliberately a unit fixture standing in for the trusted journal
owner. No test here proves durable DONE, authenticated UDS dispatch, grant
revocation, cell launch, or the normative SLICE1 CT99/CT100 producer paths.
"""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from typing import Any, cast

import pytest

from fa.execution.supervisor import (
    CompletedReplyCache,
    ReplayBinding,
    ReplayConflictError,
    ReplyUnavailableError,
    operation_input_sha256,
)
from fa.execution.types import (
    GRANT_OPERATIONS,
    Access,
    ExecutionContractError,
    GrantReply,
    NamespaceRef,
    Operation,
    ViewPurpose,
    ViewRef,
)

PROOF = "a" * 64
GRANT = "b" * 64
NAMESPACE = NamespaceRef("session-1", "run-1", "parent-1")
VIEW = ViewRef("ws-" + "1" * 32, "view-" + "2" * 32, "rev-" + "3" * 32, "run-1", 2, Access.WRITE, ViewPurpose.PROJECT)


def _unchecked_replace[T: (NamespaceRef, ViewRef, ReplayBinding, GrantReply)](
    instance: T,
    changes: dict[str, object],
) -> T:
    """Intentional malformed constructor input ONLY, not a valid-fixture cast.

    Confine the dynamic kwargs boundary here; each production __post_init__ must
    reject these actual runtime values. Valid fixtures above remain fully typed.
    """
    return replace(instance, **cast(dict[str, Any], changes))


def binding(operation: Operation = Operation.HANDOFF) -> ReplayBinding:
    if operation is Operation.HANDOFF:
        payload: dict[str, object] = {"target_namespace": NamespaceRef("session-1", "child-1", "run-1").to_dict()}
    elif operation is Operation.CREATE_VIEW:
        payload = {
            "workspace_id": VIEW.workspace_id,
            "base_revision": VIEW.base_revision,
            "access": "WRITE",
            "purpose": "PROJECT",
            "candidate_scope": None,
        }
    elif operation is Operation.PIN_READER:
        payload = {"workspace_id": VIEW.workspace_id, "revision_id": VIEW.base_revision}
    else:
        payload = {"workspace_id": VIEW.workspace_id}
    return ReplayBinding(
        "authenticated-controller",
        NAMESPACE,
        operation,
        "4" * 32,
        operation_input_sha256(operation, NAMESPACE, None, payload),
    )


def reply(operation: Operation = Operation.HANDOFF) -> GrantReply:
    if operation in {Operation.ACQUIRE_WRITER, Operation.HANDOFF}:
        return GrantReply(operation, GRANT, None, 2, "rev-" + "3" * 32)
    return GrantReply(
        operation, GRANT, replace(VIEW, access=Access.READ) if operation is Operation.PIN_READER else VIEW, None, None
    )


@pytest.mark.parametrize("operation", sorted(GRANT_OPERATIONS))
def test_exact_original_reply_and_journal_projection(operation: Operation) -> None:
    """C0: revoked-proof exception is a cache read, not a fresh-authority check."""
    cache = CompletedReplyCache(max_entries=1)
    original_proof = None if operation in {Operation.ACQUIRE_WRITER, Operation.PIN_READER} else PROOF
    key, original = binding(operation), reply(operation)
    cache.remember_completed(key, original_proof, original)
    # No live-grant table/callback exists here: this does NOT prove revocation.
    assert cache.replay(key, original_proof) is original
    wire = original.to_wire_result()
    public = original.to_journal_result(original_proof=original_proof)
    assert set(wire) - set(public) == {"capability"}
    assert wire == {**public, "capability": GRANT}
    assert "capability" not in json.dumps(public)
    assert GRANT not in json.dumps(public) and PROOF not in json.dumps(public)
    # Serializing/mutating returned dictionaries cannot mutate the cached reply.
    wire["capability"] = "forged"
    if original.view_ref is not None:
        wire["view_ref"]["owner_run_id"] = "forged"
        public["view_ref"]["generation"] = -1
    assert cache.replay(key, original_proof).to_wire_result() == {
        **original.to_journal_result(original_proof=original_proof),
        "capability": GRANT,
    }
    assert GRANT not in repr(original) and PROOF not in repr(cache)


@pytest.mark.parametrize(
    "changes",
    [
        {"principal": "different-authenticated-principal"},
        {"namespace": replace(NAMESPACE, session_id="session-2")},
        {"namespace": replace(NAMESPACE, run_id="run-2")},
        {"namespace": replace(NAMESPACE, parent_run_id=None)},
        {"operation": Operation.CREATE_VIEW},
        {"input_sha256": "f" * 64},
    ],
)
def test_replay_binding_mismatch_never_returns_original(changes: dict[str, object]) -> None:
    cache = CompletedReplyCache(max_entries=1)
    original = reply()
    cache.remember_completed(binding(), PROOF, original)
    with pytest.raises(ReplayConflictError, match=r"^execution_replay_conflict$"):
        cache.replay(_unchecked_replace(binding(), changes), PROOF)
    assert cache.replay(binding(), PROOF) is original


@pytest.mark.parametrize("proof", ["c" * 64, "", None, "ü" * 64])
def test_original_proof_required_even_when_all_public_ids_match(proof: str | None) -> None:
    cache = CompletedReplyCache(max_entries=1)
    cache.remember_completed(binding(), PROOF, reply())
    with pytest.raises((ReplayConflictError, ExecutionContractError)) as caught:
        cache.replay(binding(), proof)
    assert PROOF not in str(caught.value) and GRANT not in str(caught.value)


def test_repeated_completion_is_not_grant_renewal_or_result_replacement() -> None:
    cache = CompletedReplyCache(max_entries=1)
    original = reply()
    cache.remember_completed(binding(), PROOF, original)
    cache.remember_completed(binding(), PROOF, reply())
    for changed in [
        replace(original, capability="c" * 64),
        replace(original, generation=3),
        replace(original, revision_id="rev-" + "d" * 32),
    ]:
        with pytest.raises(ReplayConflictError):
            cache.remember_completed(binding(), PROOF, changed)
        assert cache.replay(binding(), PROOF) is original
    with pytest.raises(ReplayConflictError):
        cache.remember_completed(replace(binding(), principal="other"), PROOF, reply())


def test_cache_loss_unknown_request_and_saturation_fail_closed() -> None:
    cache = CompletedReplyCache(max_entries=1)
    original = reply()
    with pytest.raises(ReplyUnavailableError, match=r"^execution_reply_unavailable$"):
        cache.replay(binding(), PROOF)
    cache.remember_completed(binding(), PROOF, original)
    other = replace(binding(), request_id="5" * 32)
    with pytest.raises(ReplyUnavailableError):
        cache.remember_completed(other, PROOF, reply())
    with pytest.raises(ReplyUnavailableError):
        cache.replay(other, PROOF)
    assert cache.replay(binding(), PROOF) is original
    restarted = CompletedReplyCache(max_entries=1)
    # Durable metadata contains no means to reconstruct the original grant.
    assert "capability" not in original.to_journal_result(original_proof=PROOF)
    with pytest.raises(ReplyUnavailableError):
        restarted.replay(binding(), PROOF)


@pytest.mark.parametrize("capacity", [0, -1, True, 1.5])
def test_invalid_capacity_is_not_an_unbounded_cache(capacity: object) -> None:
    with pytest.raises(ExecutionContractError):
        CompletedReplyCache(max_entries=cast(int, capacity))  # Deliberately malformed runtime input.


def test_concurrent_duplicate_completions_keep_one_original_and_reject_replacement() -> None:
    cache = CompletedReplyCache(max_entries=1)
    original = reply()
    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(lambda _: cache.remember_completed(binding(), PROOF, original), range(32)))
        assert all(item is original for item in workers.map(lambda _: cache.replay(binding(), PROOF), range(32)))
    with pytest.raises(ReplayConflictError):
        cache.remember_completed(binding(), PROOF, replace(original, capability="c" * 64))


def test_journal_projection_checks_both_known_secrets_before_durability() -> None:
    # Existing run-ID grammar permits a hex string, but that is not permission
    # to persist the known current/original capability disguised as an ID.
    with pytest.raises(ExecutionContractError):
        GrantReply(Operation.CREATE_VIEW, GRANT, replace(VIEW, owner_run_id=GRANT), None, None)
    disguised = GrantReply(Operation.CREATE_VIEW, GRANT, replace(VIEW, owner_run_id=PROOF), None, None)
    with pytest.raises(ExecutionContractError):
        disguised.to_journal_result(original_proof=PROOF)
    cache = CompletedReplyCache(max_entries=1)
    with pytest.raises(ExecutionContractError):
        cache.remember_completed(binding(Operation.CREATE_VIEW), PROOF, disguised)
    with pytest.raises(ReplyUnavailableError):
        cache.replay(binding(Operation.CREATE_VIEW), PROOF)


@pytest.mark.parametrize(
    "operation,proof",
    [
        (Operation.ACQUIRE_WRITER, PROOF),
        (Operation.PIN_READER, PROOF),
        (Operation.HANDOFF, None),
        (Operation.CREATE_VIEW, None),
    ],
)
def test_operation_specific_original_proof_shape(operation: Operation, proof: str | None) -> None:
    cache = CompletedReplyCache(max_entries=1)
    with pytest.raises(ExecutionContractError):
        cache.remember_completed(binding(operation), proof, reply(operation))


def test_completion_result_must_match_operation() -> None:
    cache = CompletedReplyCache(max_entries=1)
    with pytest.raises(ReplayConflictError):
        cache.remember_completed(binding(), PROOF, reply(Operation.ACQUIRE_WRITER))
    with pytest.raises(ReplyUnavailableError):
        cache.replay(binding(), PROOF)


def test_canonical_input_digest_matches_v1_and_binds_all_input() -> None:
    payload: dict[str, object] = {
        "operation_id": "op-" + "4" * 32,
        "profile_id": "verification",
        "command": "printf ü",
        "cwd": ".",
        "timeout_ms": 1000,
        "session_id": None,
    }
    actual = operation_input_sha256(Operation.EXEC, NAMESPACE, VIEW, payload)
    canonical = json.dumps(
        {"op": "exec", "namespace": NAMESPACE.to_dict(), "view_ref": VIEW.to_dict(), "payload": payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert actual == hashlib.sha256(canonical).hexdigest()
    assert actual == operation_input_sha256(Operation.EXEC, NAMESPACE, VIEW, dict(reversed(list(payload.items()))))
    # Hash sensitivity, not a claim that every changed combination is a valid
    # operation schema. The real wire decoder/authority must establish that.
    for op, ns, view, body in [
        (Operation.READ_FILE, NAMESPACE, VIEW, payload),
        (Operation.EXEC, replace(NAMESPACE, run_id="run-2"), VIEW, payload),
        (Operation.EXEC, NAMESPACE, replace(VIEW, generation=3), payload),
        (Operation.EXEC, NAMESPACE, None, payload),
        (Operation.EXEC, NAMESPACE, VIEW, {**payload, "command": "printf changed"}),
    ]:
        assert operation_input_sha256(op, ns, view, body) != actual
    payload["command"] = "mutated-after-hashing"
    assert actual != operation_input_sha256(Operation.EXEC, NAMESPACE, VIEW, payload)


@pytest.mark.parametrize("payload", [{"bad": float("nan")}, {"bad": object()}, {"bad": "\ud800"}])
def test_invalid_canonical_json_is_sanitized(payload: dict[str, object]) -> None:
    with pytest.raises(ExecutionContractError, match=r"^execution_contract_invalid$"):
        operation_input_sha256(Operation.HANDOFF, NAMESPACE, None, payload)


@pytest.mark.parametrize("changes", [{"session_id": "../escape"}, {"run_id": ""}, {"parent_run_id": "bad/id"}])
def test_namespace_reuses_existing_id_grammar(changes: dict[str, str]) -> None:
    with pytest.raises(ExecutionContractError):
        replace(NAMESPACE, **changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"workspace_id": "ws-" + "A" * 32},
        {"view_id": "view-../escape"},
        {"base_revision": "rev-short"},
        {"owner_run_id": "../escape"},
        {"generation": True},
        {"generation": 0},
        {"access": "WRITE"},
        {"purpose": "unknown"},
    ],
)
def test_view_shape_rejects_invalid_identity_and_open_enums(changes: dict[str, object]) -> None:
    with pytest.raises(ExecutionContractError):
        _unchecked_replace(VIEW, changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"principal": ""},
        {"principal": "x\0y"},
        {"principal": "ü" * 129},
        {"principal": "\ud800"},
        {"namespace": "untrusted"},
        {"request_id": "request-id"},
        {"input_sha256": "hash"},
        {"operation": Operation.HEALTH},
        {"operation": "handoff"},
    ],
)
def test_replay_binding_rejects_invalid_or_health_operation(changes: dict[str, object]) -> None:
    with pytest.raises(ExecutionContractError):
        _unchecked_replace(binding(), changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"capability": "short"},
        {"operation": Operation.EXEC},
        {"operation": "handoff"},
        {"view_ref": VIEW},
        {"generation": True},
        {"generation": -1},
        {"revision_id": None},
        {"generation": 10**5000},
    ],
)
def test_owner_grant_reply_rejects_wrong_shapes(changes: dict[str, object]) -> None:
    with pytest.raises(ExecutionContractError):
        _unchecked_replace(reply(), changes)


@pytest.mark.parametrize("changes", [{"view_ref": None}, {"generation": 2}, {"revision_id": "rev-" + "3" * 32}])
def test_view_grant_reply_rejects_owner_shape_fields(changes: dict[str, object]) -> None:
    with pytest.raises(ExecutionContractError):
        _unchecked_replace(reply(Operation.CREATE_VIEW), changes)


def test_identity_and_reply_are_immutable_and_operation_vocabulary_is_closed() -> None:
    assert {op.value for op in Operation} == {
        "health",
        "register_workspace",
        "acquire_writer",
        "pin_reader",
        "create_view",
        "read_file",
        "write_file",
        "edit_file",
        "exec",
        "inspect",
        "cancel",
        "stop_view",
        "seal",
        "publish",
        "install_project",
        "release",
        "pty_control",
        "handoff",
        "prepare_bundle",
    }
    assert len(GRANT_OPERATIONS) == 4
    with pytest.raises(ValueError):
        Operation("arbitrary_shell")
    for value, field, replacement in [
        (NAMESPACE, "run_id", "changed"),
        (VIEW, "generation", 3),
        (binding(), "principal", "changed"),
        (reply(), "capability", "c" * 64),
    ]:
        with pytest.raises(FrozenInstanceError):
            setattr(value, field, replacement)


def test_view_wire_shape_and_purpose_vocabulary_match_spec() -> None:
    assert VIEW.to_dict() == {
        "workspace_id": "ws-" + "1" * 32,
        "view_id": "view-" + "2" * 32,
        "base_revision": "rev-" + "3" * 32,
        "owner_run_id": "run-1",
        "generation": 2,
        "access": "WRITE",
        "purpose": "PROJECT",
    }
    assert {p.value for p in ViewPurpose} == {"PROJECT", "PROVISIONING", "VERIFICATION", "MUTATION", "CANDIDATE"}
    with pytest.raises(ExecutionContractError):
        GrantReply(Operation.PIN_READER, GRANT, VIEW, None, None)


def test_non_grant_snapshot_is_immutable_and_completed_reply_not_fresh_authority() -> None:
    from fa.execution.types import PublicReply

    public = {"released": True}
    snapshot = PublicReply.from_result(Operation.RELEASE, public)
    public["released"] = False
    key = replace(binding(), operation=Operation.RELEASE)
    cache = CompletedReplyCache(max_entries=1)
    cache.remember_completed(key, PROOF, snapshot)
    assert cache.replay(key, PROOF).to_wire_result() == {"released": True}
    assert snapshot.to_journal_result(original_proof=PROOF) == {"released": True}
    assert "released" not in repr(snapshot)
    with pytest.raises(ReplayConflictError):
        cache.replay(key, GRANT)


def test_public_snapshot_refuses_grant_bodies_and_mutable_raw_data() -> None:
    from fa.execution.types import PublicReply

    with pytest.raises(ExecutionContractError):
        PublicReply.from_result(Operation.HANDOFF, reply().to_wire_result())
    with pytest.raises(ExecutionContractError):
        PublicReply(Operation.RELEASE, cast(Any, bytearray(b'{"released":true}')))
