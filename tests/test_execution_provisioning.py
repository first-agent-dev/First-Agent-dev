"""C0/C1 proof for the managed provisioning adapter (E263).

Root: ``fa.execution.provisioning.ManagedProvisioner`` over a real
``WorkspaceAuthority`` in a temporary approved root. No container, no daemon, no
deployed-service claim: this is component evidence only.

Path inventory:
  P1 REUSE registers quiescent existing bytes and returns the frozen registered
     result; a second call is idempotent (same ids, bytes not re-copied)
  P2 PROVISION is the typed BLOCKED disposition until SLICE3 joins publication,
     and it has no effect (no registration, no directory)
  P3 a missing reference is rejected before the authority is touched
  P4 a reference outside the approved root is rejected as an escape
  P5 corrupt registered state is reported as ``workspace_corrupt``, never as a
     usable result
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import pytest

from fa.execution.provisioning import ManagedProvisioner
from fa.execution.supervisor import PeerIdentity
from fa.execution.workspace import WorkspaceAuthority, _canonical
from fa.session.manager import SessionManagerError
from fa.session.provisioning import ProvisionMode, ProvisionRequest

PEER = PeerIdentity(os.getpid(), os.getuid(), os.getgid())


def until() -> float:
    return time.monotonic() + 10


@pytest.fixture
def site(tmp_path: Path) -> tuple[Path, Path]:
    state = tmp_path / "protected"
    roots = tmp_path / "projects"
    workspace = roots / "project"
    workspace.mkdir(parents=True)
    (workspace / "dirty.txt").write_bytes(b"dirty staged and unstaged\x00binary\xff")
    (workspace / "untracked.txt").write_text("untracked", encoding="utf-8")
    (workspace / ".git").mkdir()
    (workspace / ".git" / "index").write_bytes(b"canonical index sentinel")
    return state, roots


def _request(workspace: Path, mode: ProvisionMode = ProvisionMode.REUSE, run_id: str = "run-a") -> ProvisionRequest:
    return ProvisionRequest(
        mode=mode,
        session_id="session-a",
        run_id=run_id,
        workspace_path=workspace,
        deadline=until(),
    )


def test_reuse_registers_existing_bytes_and_is_idempotent(site: tuple[Path, Path]) -> None:
    """C1 P1: registered result carries verified identity; repeat call keeps it."""

    state, roots = site
    workspace = roots / "project"
    with WorkspaceAuthority(
        state,
        approved_roots={"projects": roots},
        controller_uids=frozenset({PEER.uid}),
        lock_timeout_ms=25,
    ) as owner:
        provisioner = ManagedProvisioner(owner, peer=PEER, root_id="projects", approved_root=roots)
        first = provisioner(_request(workspace))

        assert first.registered is True
        assert first.workspace_id is not None and first.workspace_id.startswith("ws-")
        assert first.revision_id is not None and first.revision_id.startswith("rev-")
        assert first.tree_sha256 is not None and len(first.tree_sha256) == 64
        revision = state / "workspaces" / first.workspace_id / "revisions" / first.revision_id
        tree = json.loads((revision / "tree.json").read_text(encoding="utf-8"))
        assert first.tree_sha256 == hashlib.sha256(_canonical(tree["entries"])).hexdigest()
        assert (revision / "data" / "dirty.txt").read_bytes() == (workspace / "dirty.txt").read_bytes()

        second = provisioner(_request(workspace))
        assert second == first
        assert (workspace / ".git" / "index").read_bytes() == b"canonical index sentinel"


def test_provision_mode_is_a_typed_blocked_disposition_without_effect(site: tuple[Path, Path]) -> None:
    """C3 P2: no host fallback and no partial registration for a new root."""

    state, roots = site
    with WorkspaceAuthority(
        state,
        approved_roots={"projects": roots},
        controller_uids=frozenset({PEER.uid}),
        lock_timeout_ms=25,
    ) as owner:
        provisioner = ManagedProvisioner(owner, peer=PEER, root_id="projects", approved_root=roots)
        with pytest.raises(SessionManagerError) as blocked:
            provisioner(_request(roots / "new-project", mode=ProvisionMode.PROVISION))

    assert blocked.value.code == "provisioning_unavailable"
    assert not (roots / "new-project").exists()
    registered = state / "workspaces"
    assert not registered.exists() or list(registered.iterdir()) == []


def test_missing_reference_is_rejected_before_registration(site: tuple[Path, Path]) -> None:
    """C3 P3: a reference to non-existent bytes is a closed error."""

    state, roots = site
    with WorkspaceAuthority(
        state,
        approved_roots={"projects": roots},
        controller_uids=frozenset({PEER.uid}),
        lock_timeout_ms=25,
    ) as owner:
        provisioner = ManagedProvisioner(owner, peer=PEER, root_id="projects", approved_root=roots)
        with pytest.raises(SessionManagerError) as missing:
            provisioner(_request(roots / "absent"))

    assert missing.value.code == "workspace_missing"


def test_reference_outside_the_approved_root_is_an_escape(site: tuple[Path, Path]) -> None:
    """C3 P4: the adapter never widens the approved root."""

    state, roots = site
    outside = state.parent / "elsewhere"
    outside.mkdir()
    with WorkspaceAuthority(
        state,
        approved_roots={"projects": roots},
        controller_uids=frozenset({PEER.uid}),
        lock_timeout_ms=25,
    ) as owner:
        provisioner = ManagedProvisioner(owner, peer=PEER, root_id="projects", approved_root=roots)
        with pytest.raises(SessionManagerError) as escape:
            provisioner(_request(outside))

    assert escape.value.code == "workspace_escape"


def test_corrupt_registered_state_is_never_a_usable_result(site: tuple[Path, Path]) -> None:
    """C3 P5: tampered retained bytes surface as workspace_corrupt."""

    state, roots = site
    workspace = roots / "project"
    with WorkspaceAuthority(
        state,
        approved_roots={"projects": roots},
        controller_uids=frozenset({PEER.uid}),
        lock_timeout_ms=25,
    ) as owner:
        provisioner = ManagedProvisioner(owner, peer=PEER, root_id="projects", approved_root=roots)
        first = provisioner(_request(workspace))
        assert first.registered is True
        revision = state / "workspaces" / str(first.workspace_id) / "revisions" / str(first.revision_id)
        (revision / "data" / "dirty.txt").write_bytes(b"tampered")
        with pytest.raises(SessionManagerError) as corrupt:
            provisioner(_request(workspace))

    assert corrupt.value.code == "workspace_corrupt"
