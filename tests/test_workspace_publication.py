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

import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest

import fa.execution.workspace as workspace_module
from fa.execution.supervisor import SupervisorError, TerminalVerdict, ViewStopper
from fa.execution.types import Access, GrantReply, NamespaceRef, ViewPurpose, ViewRef
from fa.execution.workspace import WorkspaceAuthority
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
