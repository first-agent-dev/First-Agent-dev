"""E280 — `pty_control` over the exact live episode, never a process-global shell.

Classes (knowledge/skills/tests-writing):
  C3 — real `WorkspaceAuthority`, real journal on disk, literal HTTP Docker peer
       (`Endpoint`), and the real local PTY worker inside the cell;
  C1 — the unavailable-transport seam (`WorkerClient.request`), doubled, because
       a dead attach cannot be produced without a dead daemon;
  C0 — the request-shape and refusal-code surface.

PTY control path inventory (I03 SLICE1 STEP3, spec §2.1 + the cell-frame
paragraph):

  P1 LIST on a live episode answers the worker's own listing; it creates no cell.
  P2 INTERRUPT answers the listing plus the worker's message, and the shell and
     cell survive (a later command still runs in the same CID).
  P3 CLOSE drops that session, and a later command recreates it on demand.
  P4 An absent session is refused with a closed code and writes NO frame: the
     cell protocol answers an unknown session by failing the exchange, so a
     caller-supplied typo must never cost the live shell.
  P5 A view with no live episode is `EXECUTION_UNKNOWN` for every action, never
     an invented empty listing (a cell that survived a restart still owns
     sessions this process cannot enumerate).
  P6 A noninteractive profile has no PTY surface (`INPUT_POLICY`).
  P7 A foreign view or a wrong capability is `UNAUTHORIZED` and sends nothing.
  P8 A non-`pty_control` envelope is `INPUT_POLICY` before any side effect.
  P9 A worker that cannot answer is `EXECUTION_UNKNOWN`, never a success.
"""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from fa.execution.backend import CellBackend
from fa.execution.types import NamespaceRef
from fa.execution.worker_client import WorkerClient, WorkerUnavailableError
from tests.test_execution_admission import request as admission_request
from tests.test_execution_backend import Backend, ObservedEngine, denied, native_profile, prepare
from tests.test_execution_backend import backend as backend
from tests.test_execution_docker import Endpoint
from tests.test_execution_workspace import ACTOR, PEER, Site, until
from tests.test_execution_workspace import site as site

ZERO = "0" * 64


def control(case: Backend, action: str, session_id: str | None, rid: str, **changes: Any) -> dict[str, Any]:
    """One exact closed `pty_control` envelope; nothing is retyped per test."""
    request = {
        "protocol_version": 1,
        "request_id": rid,
        "op": "pty_control",
        "namespace": ACTOR.to_dict(),
        "view_ref": case.view.to_dict(),
        "capability": case.grant.capability,
        "payload": {"action": action, "session_id": session_id},
    }
    request.update(changes)
    return request


def live(case: Backend, rid: str, command: str) -> None:
    """One real command, so the view has a live episode with session `main`."""
    request = prepare(case, rid, command)
    case.peer.replies.extend(case.episode_replies(request["payload"]["operation_id"]))
    assert case.owner().execute(PEER, request, deadline=until()).exit_code == 0
    assert case.owner().episode_count() == 1


# ---------------------------------------------------------------------------
# P1 — LIST
# ---------------------------------------------------------------------------


def test_list_reports_the_sessions_of_this_episodes_live_cell(backend: Backend) -> None:
    """producer-kill-check: answer from a fabricated listing, or create a cell to ask."""
    live(backend, "1" * 32, "true")
    before = len(backend.peer.seen)
    listing = backend.owner().pty_control(PEER, control(backend, "LIST", None, "2" * 32), deadline=until())
    assert listing == {"sessions": ["main"], "message": ""}
    assert len(backend.peer.seen) == before, "a control exchange created a cell"
    assert backend.owner().episode_count() == 1
    # The control path reserves nothing: it is not a command.
    assert backend.authority.journal.lookup("op-" + "2" * 32, ACTOR) is None


# ---------------------------------------------------------------------------
# P2/P3 — interrupt and close act on the same cell
# ---------------------------------------------------------------------------


def test_interrupt_and_close_keep_the_same_live_cell(backend: Backend) -> None:
    """producer-kill-check: replace the cell, or lose the shell, on a control verb."""
    live(backend, "2" * 32, "export FA_PTY_KEPT=1")
    interrupted = backend.owner().pty_control(PEER, control(backend, "INTERRUPT", "main", "3" * 32), deadline=until())
    assert interrupted["sessions"] == ["main"]
    assert isinstance(interrupted["message"], str)  # ACK text, NOT process terminality.
    # The very same cell and session still execute, with its environment intact.
    after = prepare(backend, "4" * 32, 'printf "%s" "$FA_PTY_KEPT"')
    outcome = backend.owner().execute(PEER, after, deadline=until())
    assert outcome.container_id == backend.owner().episode_container(PEER, ACTOR, backend.view)
    assert outcome.exit_code == 0 and "1" in outcome.stdout

    closed = backend.owner().pty_control(PEER, control(backend, "CLOSE", "main", "5" * 32), deadline=until())
    assert closed["sessions"] == [] and closed["message"] == ""
    listed = backend.owner().pty_control(PEER, control(backend, "LIST", None, "6" * 32), deadline=until())
    assert listed["sessions"] == []
    # A later command gets its session back on the same cell, not a second cell.
    reused = prepare(backend, "7" * 32, "printf again")
    assert backend.owner().execute(PEER, reused, deadline=until()).exit_code == 0
    assert backend.owner().episode_count() == 1
    assert backend.owner().pty_control(PEER, control(backend, "LIST", None, "8" * 32), deadline=until())[
        "sessions"
    ] == ["main"]


# ---------------------------------------------------------------------------
# P4 — an unknown session is refused, and the shell survives it
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("action", ["INTERRUPT", "CLOSE"])
def test_an_absent_session_is_refused_without_poisoning_the_cell(backend: Backend, action: str) -> None:
    """producer-kill-check: forward the frame and let the worker fail the exchange."""
    live(backend, "9" * 32, "true")
    denied(
        "EXECUTION_UNKNOWN",
        lambda: backend.owner().pty_control(PEER, control(backend, action, "nobody", "a" * 32), deadline=until()),
    )
    # The decisive observation: the attach is still usable, so no frame was written.
    assert backend.owner().pty_control(PEER, control(backend, "LIST", None, "b" * 32), deadline=until())[
        "sessions"
    ] == ["main"]
    following = prepare(backend, "c" * 32, "printf survived")
    assert backend.owner().execute(PEER, following, deadline=until()).exit_code == 0


# ---------------------------------------------------------------------------
# P5/P6 — nothing to control
# ---------------------------------------------------------------------------


def test_a_view_without_a_live_episode_is_unknown_and_creates_nothing(backend: Backend) -> None:
    """producer-kill-check: answer LIST with an invented empty listing."""
    before = len(backend.peer.seen)
    for action, session_id, rid in (
        ("LIST", None, "d" * 32),
        ("INTERRUPT", "main", "e" * 32),
        ("CLOSE", "main", "f" * 32),
    ):
        denied(
            "EXECUTION_UNKNOWN",
            lambda action=action, session_id=session_id, rid=rid: backend.owner().pty_control(
                PEER, control(backend, action, session_id, rid), deadline=until()
            ),
        )
    assert len(backend.peer.seen) == before, "a control exchange without an episode reached the daemon"
    assert backend.owner().episode_count() == 0


def test_a_noninteractive_profile_has_no_pty_surface(site: Site, tmp_path: Path) -> None:
    """producer-kill-check: control a one-shot cell that has no persistent shell."""
    profile = replace(native_profile(), profile_id="verification", interactive=False)
    case = Backend(site, tmp_path, profile_override=profile)
    private = tmp_path / "private-pty"
    private.mkdir(mode=0o700)
    case.peer = Endpoint(private / "engine.sock")
    case.engine = ObservedEngine(case.peer.path, daemon_uid=os.getuid(), api_version="1.45", rpc_timeout_ms=1000)
    case.backend = CellBackend(case.authority, case.engine, case.authority.journal)
    try:
        request = control(case, "LIST", None, "1" * 32)
        denied("INPUT_POLICY", lambda: case.owner().pty_control(PEER, request, deadline=until()))
        assert len(case.peer.seen) == 0 and case.owner().episode_count() == 0
    finally:
        case.close()
        case.peer.close()


# ---------------------------------------------------------------------------
# P7/P8/P9 — proof and failure behaviour
# ---------------------------------------------------------------------------


def test_a_foreign_view_or_grant_is_unauthorized_and_sends_nothing(
    backend: Backend, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: resolve the episode before proving the grant."""
    live(backend, "2" * 32, "true")
    sent: list[bytes] = []
    original = WorkerClient.request

    def spy(self: WorkerClient, raw: bytes, *, deadline: float) -> dict[str, Any]:
        sent.append(raw)
        return original(self, raw, deadline=deadline)

    monkeypatch.setattr(WorkerClient, "request", spy)
    other = {**backend.view.to_dict(), "view_id": "view-" + "3" * 32}
    denied(
        "UNAUTHORIZED",
        lambda: backend.owner().pty_control(
            PEER, control(backend, "INTERRUPT", "main", "4" * 32, view_ref=other), deadline=until()
        ),
    )
    denied(
        "UNAUTHORIZED",
        lambda: backend.owner().pty_control(
            PEER, control(backend, "INTERRUPT", "main", "5" * 32, capability=ZERO), deadline=until()
        ),
    )
    denied(
        "UNAUTHORIZED",
        lambda: backend.owner().pty_control(
            PEER,
            control(
                backend,
                "LIST",
                None,
                "6" * 32,
                namespace=NamespaceRef("session-b", "run-b").to_dict(),
            ),
            deadline=until(),
        ),
    )
    assert sent == [], "a refused control request still reached the cell"


def test_a_non_control_envelope_is_refused(backend: Backend) -> None:
    """producer-kill-check: run whatever the envelope happens to be."""
    request = admission_request(backend.grant)
    denied("INPUT_POLICY", lambda: backend.owner().pty_control(PEER, request, deadline=until()))
    assert backend.owner().episode_count() == 0 and backend.peer.seen == []


@pytest.mark.parametrize("fault", [WorkerUnavailableError, TimeoutError], ids=["lost-attach", "expired"])
def test_a_worker_that_cannot_answer_is_unknown(
    backend: Backend, monkeypatch: pytest.MonkeyPatch, fault: type[Exception]
) -> None:
    """producer-kill-check: turn a dead attach or a spent budget into a success."""

    def broken(self: WorkerClient, raw: bytes, *, deadline: float) -> dict[str, Any]:
        raise fault

    # RUN (begin/await_reply) is untouched by this seam: only a control
    # exchange goes through `request`, which is exactly what must fail closed.
    live(backend, "7" * 32, "true")
    monkeypatch.setattr(WorkerClient, "request", broken)
    denied(
        "EXECUTION_UNKNOWN",
        lambda: backend.owner().pty_control(PEER, control(backend, "LIST", None, "8" * 32), deadline=until()),
    )
