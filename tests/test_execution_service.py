"""E277 — the composed service: one route per closed operation, over real owners.

Classes (knowledge/skills/tests-writing):
  C0 — the route table, the config contract and the profile-set digest;
  C3 — the composed supervisor over a real AF_UNIX socket, the real closed codec
       and the real `WorkspaceAuthority` state directory. No fake authority, no
       fake journal, no fabricated receipt.

What must stay true (each test names the producer it kills):
  * every `Operation` member has exactly one route and no route is unreachable;
  * `health` publishes the digest of the profiles actually enforced;
  * a mutating request goes through reservation -> authority proof -> handler and
    returns the exact closed reply shape;
  * `create_view` forwards the wire `base_revision` into the authority's CAS;
  * `release` (empty payload) settles the grant it was proved with;
  * `stop_view` never claims terminality without a descendant observation, and
    `seal` therefore refuses rather than inventing a terminal receipt;
  * the six ownerless routes refuse with a closed error code, never a silent
    success and never a host-side fallback;
  * the socket is 0600, appears only after startup recovery, and is unlinked on
    shutdown.
"""

from __future__ import annotations

import json
import os
import socket
import stat
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from fa.execution.profiles import profile_set_sha256
from fa.execution.protocol import decode_reply, encode_json, read_frame, write_frame
from fa.execution.service import (
    _ROUTE_NAMES,
    ServiceConfig,
    SupervisorService,
    load_config,
    read_config_file,
)
from fa.execution.supervisor import SupervisorError, build_supervisor, main
from fa.execution.types import ExecutionContractError, Operation
from tests.test_execution_views import native_profile
from tests.test_execution_workspace import ACTOR, PEER, Site
from tests.test_execution_workspace import site as site

RID = "1" * 32


def until() -> float:
    return time.monotonic() + 10


def _config(site: Site, **overrides: Any) -> ServiceConfig:
    values: dict[str, Any] = {
        "state_root": site.state,
        "socket_path": site.state.parent / "supervisor.sock",
        "controller_uids": frozenset({PEER.uid}),
        "approved_roots": {"projects": site.roots},
        "profiles": (native_profile(),),
        "rpc_timeout_ms": 2000,
        "lock_timeout_ms": 25,
        "view_profile_id": native_profile().profile_id,
    }
    values.update(overrides)
    return ServiceConfig(**values)


def request(
    operation: Operation,
    payload: dict[str, Any],
    *,
    request_id: str = RID,
    view_ref: dict[str, Any] | None = None,
    capability: str | None = None,
) -> dict[str, Any]:
    """One exact closed envelope; the caller supplies only what the op owns."""
    return {
        "protocol_version": 1,
        "request_id": request_id,
        "op": operation.value,
        "namespace": None if operation is Operation.HEALTH else ACTOR.to_dict(),
        "view_ref": view_ref,
        "capability": capability,
        "payload": payload,
    }


def exchange(
    service: SupervisorService, operation: Operation, payload: dict[str, Any], *, request_id: str = RID, **kwargs: Any
) -> dict[str, Any]:
    """One real connection through the dispatcher: frame in, decoded reply out."""
    raw = encode_json(request(operation, payload, request_id=request_id, **kwargs))
    controller, accepted = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    with ThreadPoolExecutor(max_workers=1) as workers:
        future = workers.submit(service.dispatcher.serve_connection, accepted)
        with controller:
            controller.settimeout(5)
            write_frame(controller, raw)
            response = read_frame(controller)
        future.result(timeout=8)
    return decode_reply(response, operation=operation, request_id=request_id)


def _error(reply: dict[str, Any]) -> str:
    assert reply["status"] == "ERROR", reply
    assert reply["result"] is None
    return str(reply["error"]["code"])


# ---------------------------------------------------------------------------
# C0 — the shape of the composition
# ---------------------------------------------------------------------------


def test_the_route_table_covers_each_closed_operation_exactly_once(site: Site) -> None:
    """producer-kill-check: add an `Operation` member without a route, or a second route."""
    # Asserted before construction so a missing row is a coverage failure, not
    # merely a construction error that hides which operation lost its route.
    assert set(_ROUTE_NAMES) == set(Operation)
    assert len(set(_ROUTE_NAMES.values())) == len(Operation)
    with SupervisorService(_config(site)) as service:
        for name in _ROUTE_NAMES.values():
            assert callable(getattr(service, name, None)), name


def test_the_profile_set_digest_is_content_bound_and_order_independent(site: Site) -> None:
    """producer-kill-check: digest the config order (or a constant) instead of the set."""
    interactive = native_profile()
    one_shot = replace(interactive, profile_id="oneshot", interactive=False)
    assert profile_set_sha256((interactive, one_shot)) == profile_set_sha256((one_shot, interactive))
    assert profile_set_sha256((interactive, one_shot)) != profile_set_sha256(
        (replace(interactive, memory_bytes=interactive.memory_bytes // 2), one_shot)
    )


def test_config_refuses_unknown_keys_and_a_socket_reachable_through_a_root(site: Site) -> None:
    """producer-kill-check: accept an unknown key, or bind the socket inside a mounted root."""
    document = {
        "state_root": str(site.state),
        "socket_path": str(site.state.parent / "svc.sock"),
        "controller_uids": [PEER.uid],
        "approved_roots": {"projects": str(site.roots)},
        "profiles": [native_profile().to_dict()],
        "rpc_timeout_ms": 2000,
        "lock_timeout_ms": 25,
    }
    assert load_config(document).profiles == (native_profile(),)
    with pytest.raises(ExecutionContractError):
        load_config({**document, "unexpected": True})
    with pytest.raises(ExecutionContractError):
        load_config({**document, "socket_path": str(site.roots / "svc.sock")})


def test_health_publishes_the_digest_of_the_profiles_actually_enforced(site: Site) -> None:
    """producer-kill-check: hash the config file, or ignore profile content."""
    profile = native_profile()
    with SupervisorService(_config(site)) as service:
        reply = service.handle(PEER, request(Operation.HEALTH, {}), deadline=until())
        assert reply == {
            "ready": True,
            "protocol_version": 1,
            "profile_set_sha256": profile_set_sha256((profile,)),
        }
        assert service.profile_set_sha256 != profile_set_sha256((replace(profile, max_command_ms=999),))
        # Health is the one operation with no journal record at all.
        assert service.authority.journal.lookup("op-" + RID, ACTOR) is None


def test_health_over_the_wire_is_a_readonly_reply_with_no_reservation(site: Site) -> None:
    """producer-kill-check: reserve a journal record for health."""
    with SupervisorService(_config(site)) as service:
        reply = exchange(service, Operation.HEALTH, {})
        assert reply["status"] == "OK", reply
        assert reply["result"] == {
            "ready": True,
            "protocol_version": 1,
            "profile_set_sha256": profile_set_sha256((native_profile(),)),
        }
        assert service.authority.journal.lookup("op-" + RID, ACTOR) is None


# ---------------------------------------------------------------------------
# C3 — the real path through the socket
# ---------------------------------------------------------------------------


def test_register_acquire_view_write_read_release_round_trip(site: Site) -> None:
    """producer-kill-check: drop any one route's call into its real owner."""
    with SupervisorService(_config(site)) as service:
        workspace_id = _registered(service)
        capability, revision_id = _writer(service, workspace_id, request_id="2" * 32)
        view, view_capability = _view(service, workspace_id, revision_id, capability, request_id="3" * 32)
        assert view["workspace_id"] == workspace_id and view["base_revision"] == revision_id

        written = exchange(
            service,
            Operation.WRITE_FILE,
            {"path": "note.txt", "content": "composed\n", "expected_sha256": None},
            request_id="4" * 32,
            view_ref=view,
            capability=view_capability,
        )
        assert written["status"] == "OK", written
        assert set(written["result"]) == {"sha256", "bytes"}

        read = exchange(
            service,
            Operation.READ_FILE,
            {"path": "note.txt", "offset_bytes": 0, "max_bytes": 64},
            request_id="5" * 32,
            view_ref=view,
            capability=view_capability,
        )
        assert read["status"] == "OK", read
        assert read["result"]["content"] == "composed\n"
        assert read["result"]["eof"] is True

        # A WRITE view is not released: it is settled by publication. The pin is
        # the release-vocabulary owner, and it carries the view-scoped grant.
        pinned = exchange(
            service,
            Operation.PIN_READER,
            {"workspace_id": workspace_id, "revision_id": revision_id, "plan_ref": None},
            request_id="6" * 32,
        )
        assert pinned["status"] == "OK", pinned
        released = exchange(
            service,
            Operation.RELEASE,
            {},
            request_id="7" * 32,
            view_ref=pinned["result"]["view_ref"],
            capability=pinned["result"]["capability"],
        )
        assert released["status"] == "OK", released
        assert released["result"] == {"released": True}


def test_create_view_refuses_a_stale_wire_base_before_any_copy(site: Site) -> None:
    """producer-kill-check: call create_view without the wire's base_revision."""
    with SupervisorService(_config(site)) as service:
        workspace_id = _registered(service)
        capability, _revision = _writer(service, workspace_id, request_id="7" * 32)
        reply = exchange(
            service,
            Operation.CREATE_VIEW,
            {
                "workspace_id": workspace_id,
                "base_revision": "rev-" + "9" * 32,
                "access": "WRITE",
                "purpose": "PROJECT",
                "candidate_scope": None,
                "plan_ref": None,
            },
            request_id="8" * 32,
            capability=capability,
        )
        assert _error(reply) == "STALE_REVISION"
        assert os.listdir(site.state / "workspaces" / workspace_id / "views") == [], (
            "a refused create_view left a copied view behind"
        )


def test_create_view_forwards_the_wire_base_revision_into_the_authority(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: drop `base_revision` at the handler boundary.

    The authorizer also opens the named revision, so a refused create_view alone
    cannot prove the *handler* forwarded it: the handler's own argument is
    observed here, independent of any authority-side check.
    """
    with SupervisorService(_config(site)) as service:
        seen: dict[str, Any] = {}

        def create_view(*_args: Any, **kwargs: Any) -> Any:
            seen.update(kwargs)
            raise SupervisorError("INPUT_POLICY")

        monkeypatch.setattr(service.authority, "create_view", create_view)
        with pytest.raises(SupervisorError):
            service.handle(
                PEER,
                request(
                    Operation.CREATE_VIEW,
                    {
                        "workspace_id": "ws-" + "1" * 32,
                        "base_revision": "rev-" + "2" * 32,
                        "access": "WRITE",
                        "purpose": "PROJECT",
                        "candidate_scope": None,
                        "plan_ref": None,
                    },
                    capability="3" * 64,
                ),
                deadline=until(),
            )
        assert seen["base_revision"] == "rev-" + "2" * 32
        assert seen["purpose"].value == "PROJECT" and seen["access"].value == "WRITE"


def test_binding_happens_only_after_the_authority_recovery_hook(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    """producer-kill-check: create the socket before `_load`/recovery finished."""
    import fa.execution.service as service_module
    import fa.execution.workspace as workspace_module

    recovered: list[bool] = []
    original_load = workspace_module.WorkspaceAuthority._load
    original_bind = service_module.SupervisorService._bind

    def load(self: Any) -> None:
        original_load(self)
        recovered.append(True)

    def bind(self: Any) -> None:
        assert recovered, "the listening socket was created before startup recovery"
        original_bind(self)

    monkeypatch.setattr(workspace_module.WorkspaceAuthority, "_load", load)
    monkeypatch.setattr(service_module.SupervisorService, "_bind", bind)
    with SupervisorService(_config(site)):
        assert recovered == [True]


def test_release_without_a_view_settles_the_grant_it_was_proved_with(site: Site) -> None:
    """producer-kill-check: route view-less release through the workspace-id API."""
    with SupervisorService(_config(site)) as service:
        workspace_id = _registered(service)
        capability, _revision = _writer(service, workspace_id, request_id="a" * 32)
        reply = exchange(service, Operation.RELEASE, {}, request_id="b" * 32, capability=capability)
        assert reply["status"] == "OK", reply
        assert reply["result"] == {"released": True}
        metadata = json.loads((site.state / "workspaces" / workspace_id / "workspace.json").read_text())
        assert metadata["status"] == "AVAILABLE"


def test_stop_view_reports_no_terminality_without_a_descendant_observation(site: Site) -> None:
    """producer-kill-check: treat a missing cell observer as 'probably stopped'."""
    with SupervisorService(_config(site)) as service:
        workspace_id = _registered(service)
        capability, revision_id = _writer(service, workspace_id, request_id="c" * 32)
        view, view_capability = _view(service, workspace_id, revision_id, capability, request_id="d" * 32)
        reply = exchange(
            service, Operation.STOP_VIEW, {}, request_id="e" * 32, view_ref=view, capability=view_capability
        )
        assert reply["status"] == "OK", reply
        assert reply["result"] == {"view_id": view["view_id"], "terminal": False}
        root = site.state / "workspaces" / workspace_id / "views" / view["view_id"]
        assert json.loads((root / "view.json").read_text())["state"] == "STOPPING", (
            "admission closure did not reach the view record"
        )
        assert not (root / "terminal.json").exists(), "a view without a descendant observation got a receipt"

        sealed = exchange(service, Operation.SEAL, {}, request_id="f" * 32, view_ref=view, capability=view_capability)
        assert _error(sealed) == "TERMINALITY_UNKNOWN"


@pytest.mark.parametrize(
    ("operation", "payload", "view_scoped"),
    [
        (
            Operation.EXEC,
            {
                "operation_id": "op-" + "4" * 32,
                "profile_id": native_profile().profile_id,
                "command": "true",
                "cwd": ".",
                "timeout_ms": 10,
                "session_id": "main",
            },
            True,
        ),
        (Operation.INSPECT, {"operation_id": "op-" + "4" * 32}, True),
        (Operation.CANCEL, {"operation_id": "op-" + "4" * 32}, True),
        (Operation.PTY_CONTROL, {"action": "LIST", "session_id": None}, True),
        (
            Operation.HANDOFF,
            {"target_namespace": {"session_id": "session-a", "run_id": "child", "parent_run_id": "run-a"}},
            False,
        ),
    ],
)
def test_routes_without_an_owner_refuse_with_a_closed_code(
    site: Site, operation: Operation, payload: dict[str, Any], view_scoped: bool
) -> None:
    """producer-kill-check: return {} (or any synthetic result) for an ownerless route."""
    with SupervisorService(_config(site)) as service:
        workspace_id = _registered(service)
        capability, revision_id = _writer(service, workspace_id, request_id="1" * 32)
        view_ref, proof = None, capability
        if view_scoped:
            view_ref, proof = _view(service, workspace_id, revision_id, capability, request_id="2" * 32)
        reply = exchange(service, operation, payload, request_id="4" * 32, view_ref=view_ref, capability=proof)
        assert _error(reply) == "BACKEND_UNAVAILABLE"
        record = service.authority.journal.lookup("op-" + "4" * 32, ACTOR)
        if operation is Operation.INSPECT or (operation is Operation.PTY_CONTROL and payload["action"] == "LIST"):
            # The readonly class never reserves: observation leaves no history.
            assert record is None
        else:
            # The reservation exists and is durably uncertain, not DONE.
            assert record is not None and record["state"] == "UNKNOWN"


def test_register_create_true_refuses_because_no_provisioner_owner_exists(site: Site) -> None:
    """producer-kill-check: hand a create=true registration to `register_existing`."""
    with SupervisorService(_config(site)) as service:
        reply = exchange(
            service,
            Operation.REGISTER_WORKSPACE,
            {"root_id": "projects", "relative_root": "made-up", "create": True, "input_id": None},
        )
        assert _error(reply) == "BACKEND_UNAVAILABLE"
        assert not (site.roots / "made-up").exists()


# ---------------------------------------------------------------------------
# Socket ownership and life
# ---------------------------------------------------------------------------


def test_the_socket_is_private_and_appears_only_after_startup_recovery(site: Site) -> None:
    """producer-kill-check: bind before entering the authority, or leave a readable socket."""
    socket_path = _config(site).socket_path
    service = build_supervisor(_config(site))
    assert not socket_path.exists(), "the socket existed before startup recovery"
    with service:
        mode = socket_path.lstat()
        assert stat.S_ISSOCK(mode.st_mode)
        assert stat.S_IMODE(mode.st_mode) == 0o600, oct(stat.S_IMODE(mode.st_mode))
        assert service.socket_path == socket_path
    assert not socket_path.exists(), "shutdown left the socket behind"


def test_serve_forever_answers_each_connection_once_and_stops(site: Site) -> None:
    """producer-kill-check: keep accepting after the stop event, or reuse one connection."""
    service = build_supervisor(_config(site))
    stop = threading.Event()
    with service:
        runner = threading.Thread(target=service.serve_forever, args=(stop,), daemon=True)
        runner.start()
        for request_id in ("a" * 32, "b" * 32):
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as controller:
                controller.settimeout(5)
                controller.connect(str(service.socket_path))
                write_frame(controller, encode_json(request(Operation.HEALTH, {}, request_id=request_id)))
                reply = decode_reply(read_frame(controller), operation=Operation.HEALTH, request_id=request_id)
                assert reply["status"] == "OK", reply
                # One request per connection: the server closes after its reply.
                assert controller.recv(1) == b""
        stop.set()
        runner.join(timeout=5)
        assert not runner.is_alive(), "serve_forever ignored its stop event"


def test_main_refuses_an_invalid_config_without_serving(site: Site, tmp_path: Path) -> None:
    """producer-kill-check: fall back to defaults when the operator config is wrong."""
    config = tmp_path / "service.json"
    document = {
        "state_root": str(site.state),
        "socket_path": str(site.state.parent / "uncertain.sock"),
        "controller_uids": [PEER.uid],
        "approved_roots": {"projects": str(site.roots)},
        "profiles": [native_profile().to_dict()],
        "rpc_timeout_ms": 2000,
        "lock_timeout_ms": 25,
        "view_profile_id": "unknown-profile",
    }
    config.write_text(json.dumps(document))
    assert main(["--config", str(config)]) == 2
    assert not (site.state.parent / "uncertain.sock").exists()

    document["view_profile_id"] = native_profile().profile_id
    config.write_text(json.dumps(document))
    assert read_config_file(config).view_profile_id == native_profile().profile_id


def test_profiles_must_be_explicit_and_unique(site: Site) -> None:
    """producer-kill-check: accept an empty or duplicated approved profile set."""
    with pytest.raises(ExecutionContractError):
        _config(site, profiles=())
    profile = native_profile()
    with pytest.raises(ExecutionContractError):
        _config(site, profiles=(profile, profile))


# ---------------------------------------------------------------------------
# helpers that use the composed service, not a fixture authority
# ---------------------------------------------------------------------------


def _registered(service: SupervisorService) -> str:
    reply = exchange(
        service,
        Operation.REGISTER_WORKSPACE,
        {"root_id": "projects", "relative_root": "project", "create": False, "input_id": None},
        request_id="9" * 32,
    )
    assert reply["status"] == "OK", reply
    return str(reply["result"]["workspace_id"])


def _writer(service: SupervisorService, workspace_id: str, *, request_id: str) -> tuple[str, str]:
    reply = exchange(service, Operation.ACQUIRE_WRITER, {"workspace_id": workspace_id}, request_id=request_id)
    assert reply["status"] == "OK", reply
    assert reply["result"]["view_ref"] is None
    return str(reply["result"]["capability"]), str(reply["result"]["revision_id"])


def _view(
    service: SupervisorService,
    workspace_id: str,
    base_revision: str,
    capability: str,
    *,
    request_id: str,
) -> tuple[dict[str, Any], str]:
    reply = exchange(
        service,
        Operation.CREATE_VIEW,
        {
            "workspace_id": workspace_id,
            "base_revision": base_revision,
            "access": "WRITE",
            "purpose": "PROJECT",
            "candidate_scope": None,
            "plan_ref": None,
        },
        request_id=request_id,
        capability=capability,
    )
    assert reply["status"] == "OK", reply
    return reply["result"]["view_ref"], str(reply["result"]["capability"])
