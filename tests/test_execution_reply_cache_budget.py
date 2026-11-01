"""C0/C3 public byte budget; real journal/dispatcher, fixture authority, no host proof."""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from fa.execution.protocol import decode_request, encode_json
from fa.execution.supervisor import CompletedReplyCache, PeerIdentity, ReplayConflictError, ReplyUnavailableError
from fa.execution.types import ExecutionContractError, Operation, PublicReply
from tests.test_execution_dispatch import CAP, NS, RID, Fixture, request
from tests.test_execution_supervisor import PROOF, binding, reply


def public(text: str) -> PublicReply:
    return PublicReply.from_result(Operation.PTY_CONTROL, {"sessions": [], "message": text})


def test_exact_aggregate_boundary_and_duplicate_replay() -> None:
    first, second = public("x" * 25), public("ё" * 31)
    k1 = binding(Operation.PTY_CONTROL)
    k2, k3 = replace(k1, request_id="5" * 32), replace(k1, request_id="6" * 32)
    size = len(first.canonical_result) + len(second.canonical_result)
    cache = CompletedReplyCache(max_entries=5, max_public_bytes=size)
    cache.remember_completed(k1, PROOF, first)
    cache.remember_completed(k1, PROOF, first)  # Equal completion must not be charged twice.
    cache.remember_completed(k2, PROOF, second)
    assert cache.replay(k1, PROOF) is first and cache.replay(k2, PROOF) is second
    with pytest.raises(ReplyUnavailableError):
        cache.remember_completed(k3, PROOF, public("z"))
    with pytest.raises(ReplyUnavailableError):
        cache.replay(k3, PROOF)
    assert cache.replay(k1, PROOF) is first and cache.replay(k2, PROOF) is second


def test_one_byte_over_is_rejected_without_insertion() -> None:
    value = public("ё" * 100)
    key = binding(Operation.PTY_CONTROL)
    cache = CompletedReplyCache(max_entries=4, max_public_bytes=len(value.canonical_result) - 1)
    with pytest.raises(ReplyUnavailableError):
        cache.remember_completed(key, PROOF, value)
    with pytest.raises(ReplyUnavailableError):
        cache.replay(key, PROOF)


def test_existing_conflict_wins_over_full_budget_and_preserves_original() -> None:
    first = public("first")
    key = binding(Operation.PTY_CONTROL)
    cache = CompletedReplyCache(max_entries=1, max_public_bytes=len(first.canonical_result))
    cache.remember_completed(key, PROOF, first)
    with pytest.raises(ReplayConflictError):
        cache.remember_completed(key, PROOF, public("changed"))
    with pytest.raises(ReplayConflictError):
        cache.remember_completed(replace(key, principal="other"), PROOF, first)
    assert cache.replay(key, PROOF) is first


def test_grant_still_limited_by_entry_count_not_public_bytes() -> None:
    cache = CompletedReplyCache(max_entries=1, max_public_bytes=1)
    original = reply()
    key = binding()
    cache.remember_completed(key, PROOF, original)
    assert cache.replay(key, PROOF) is original
    with pytest.raises(ReplyUnavailableError):
        cache.remember_completed(replace(key, request_id="5" * 32), PROOF, original)


@pytest.mark.parametrize("bad", [0, -1, True, 1.5])
def test_invalid_public_budget_refused(bad: object) -> None:
    with pytest.raises(ExecutionContractError):
        CompletedReplyCache(max_entries=10, max_public_bytes=cast(int, bad))


def test_default_remains_count_only() -> None:
    value = public("x" * 10000)
    key = binding(Operation.PTY_CONTROL)
    cache = CompletedReplyCache(max_entries=1)
    cache.remember_completed(key, PROOF, value)
    assert cache.replay(key, PROOF) is value


def test_concurrent_distinct_completions_cannot_oversubscribe_budget() -> None:
    count, allowed = 8, 3
    value = public("x" * 1000)
    cache = CompletedReplyCache(max_entries=count, max_public_bytes=allowed * len(value.canonical_result))
    base = binding(Operation.PTY_CONTROL)
    barrier = threading.Barrier(count)

    def store(i: int) -> bool:
        key = replace(base, request_id=f"{i:032x}")
        barrier.wait(timeout=5)
        try:
            cache.remember_completed(key, PROOF, value)
        except ReplyUnavailableError:
            return False
        assert cache.replay(key, PROOF) is value
        return True

    with ThreadPoolExecutor(max_workers=count) as workers:
        results = list(workers.map(store, range(count)))
    assert sum(results) == allowed
    assert len(cache._entries) == allowed


def test_cache_saturation_after_durable_done_never_reexecutes(tmp_path: Path) -> None:
    # Real dispatcher and OperationJournal; Fixture is only the authority/handler.
    case = Fixture(tmp_path)
    case.service._replies = CompletedReplyCache(max_entries=32, max_public_bytes=1)
    req = decode_request(encode_json({**request(), "op": "release", "payload": {}}))
    peer = PeerIdentity(os.getpid(), os.getuid(), os.getgid())
    first = case.service._dispatch(peer, req, deadline=time.monotonic() + 3)
    assert first["status"] == "ERROR" and first["error"]["code"] == "EXECUTION_UNKNOWN"
    assert first["error"]["operation_id"] == "op-" + RID
    record = case.journal.lookup("op-" + RID, NS)
    assert record is not None and record["state"] == "DONE" and record["result"] == {"released": True}
    second = case.service._dispatch(peer, req, deadline=time.monotonic() + 3)
    assert second["status"] == "ERROR" and second["error"]["code"] == "EXECUTION_UNKNOWN"
    assert case.auth_calls == case.handler_calls == 1 and req["capability"] == CAP
    assert case.journal.lookup("op-" + RID, NS) == record
