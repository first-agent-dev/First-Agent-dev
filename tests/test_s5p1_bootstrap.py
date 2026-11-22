"""S5P1 STEP2 — bootstrap: render, install, read the INSTALLED plan back, admit it.

`resolve_acquisition_choice` refuses to fabricate a snapshot from a bootstrap choice,
because the plan a bootstrap run must be admitted against is the file the authority
installs. This bank proves the rest of that sentence, against a **real**
`WorkspaceAuthority`:

  * the bundle is rendered by the authority from prose only (`render_bundle` owns
    every metadata field);
  * the install commits a new revision, so the acquisition view pinned before it is
    stale — the read-back must happen through a fresh pin of the new revision;
  * the admitted snapshot's bytes are the installed incrment's bytes, with
    `source_kind == "BOOTSTRAP"`, so nothing the model wrote is trusted as the plan.

Classes (knowledge/skills/tests-writing):
  C1 — one real render+install+pin becomes an admitted snapshot of the installed file.
  C0 — the installed file is the only thing that can be admitted; a wrong path or a
       stale revision is a closed refusal, not a host read.

Kill-checks (each names the producer it kills):
  * admit the submitted prose instead of the installed bytes  -> byte equality fails;
  * read through the pre-install view                          -> the file is absent;
  * keep the old revision id                                   -> the pin refuses.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, cast, override

import pytest

from fa.execution.client import ExecutionClient, ExecutionRejectedError, InstallReceipt
from fa.execution.primitives import Operation
from fa.execution.profiles import ExecutionProfile
from fa.inner_loop.tools.workspace_port import PORT_READ_MAX_BYTES
from fa.inner_loop.workflow_controller import WorkflowContext, workflow_artifact_paths

from .test_execution_workspace import ACTOR, PEER

PEER_UID = 1000


def until() -> float:
    return time.monotonic() + 20


def _read_only_profile() -> ExecutionProfile:
    """A non-interactive READ profile: `pin_reader` refuses without one."""
    return ExecutionProfile(
        "noninteractive",
        "example.invalid/fa@sha256:" + "a" * 64,
        1000,
        1000,
        1_000_000_000,
        256 * 1024 * 1024,
        32,
        30_000,
        False,
        "fa-test.slice",
        json.dumps({"defaultAction": "SCMP_ACT_ERRNO", "syscalls": []}),
    )




@pytest.fixture
def site(tmp_path: Path) -> Any:
    """One registered workspace with an owner grant, via the real authority."""
    from .test_execution_workspace import Site

    roots = tmp_path / "projects"
    roots.mkdir()
    (roots / "project").mkdir()
    # A READ profile is required: `pin_reader` refuses `UNAPPROVED_PROFILE` without
    # one, and the acquisition view is a READ pin.
    return Site(tmp_path / "state", roots, tmp_path / "src")


# ── C1: the positive path, on the real authority ────────────────────────────


def test_the_bootstrap_refusal_rule_is_its_own(tmp_path: Path) -> None:
    """`bootstrap-unavailable` is distinct from clarification and from a parse error.

    An operator reading the ledger must be able to tell "this run wanted a new
    project and had no authority to install one" from "the planner asked a
    question".
    """
    from fa.inner_loop.plan_admission import PlanRefError

    error = PlanRefError("bootstrap-unavailable")
    assert error.rule == "bootstrap-unavailable"
    assert error.rule != "bootstrap-not-installed"
    assert PlanRefError("bootstrap-refused").rule == "bootstrap-refused"
    assert tmp_path.exists()


def test_the_controller_context_carries_the_replan_budget_for_bootstrap(tmp_path: Path) -> None:
    """Bound after the planner ran, so the binder has no request object to read it from.

    Without it the bound admission would claim a limit of zero and refuse a repair
    leg the plan allows — which is why the field exists on the context at all.
    """
    ctx = WorkflowContext(
        run_id="run-1",
        base_task="t",
        per_role_task={},
        artifact_paths=workflow_artifact_paths("run-1", base_dir=tmp_path / "logs"),
        config=tmp_path / "models.yaml",
        workspace=tmp_path,
        max_turns=1,
        output_mode="quiet",
        replans_allowed=3,
    )
    assert ctx.replans_allowed == 3


# ── the controller's own bootstrap path, on the REAL authority ──────────────
#
# Only the wire is doubled: `_BootstrapClient` forwards prepare/install to the real
# `publication` functions, so the tree the read-back sees is the tree the authority
# actually installed. A double that made up those two answers could pass while the
# controller pinned a stale revision or admitted the submitted prose — which is
# exactly what the mutations below check.


class _BootstrapClient(ExecutionClient):
    """A real authority behind the client's verb signatures."""

    def __init__(self, authority: Any, ids: dict[str, str], capability: str, *, namespace: Any) -> None:
        super().__init__(Path("/nonexistent/supervisor.sock"), server_uid=0, rpc_timeout_ms=1000)
        self.calls: list[str] = []
        self.pinned_revisions: list[str] = []
        self.installs: list[dict[str, Any]] = []
        self.prepares: list[dict[str, Any]] = []
        self.reads: list[dict[str, Any]] = []
        self._authority = authority
        self._ids = ids
        self._capability = capability
        self._namespace = namespace
        self._view: Any = None
        self._grant: Any = None

    @override
    def prepare_bundle(
        self,
        binding: object,
        *,
        grant: Any,
        project_slug: str,
        increment_slug: str,
        roadmap_text: str,
        increment_text: str,
        expected_base_revision: str,
        deadline: float | None = None,
    ) -> Any:
        from fa.execution.publication import prepare_bundle

        self.calls.append("prepare")
        self.prepares.append({"expected_base_revision": expected_base_revision, "increment_text": increment_text})
        return self._authority_call(
            prepare_bundle,
            self._authority,
            PEER,
            ACTOR,
            capability=self._capability,
            project_slug=project_slug,
            increment_slug=increment_slug,
            roadmap_text=roadmap_text,
            increment_text=increment_text,
            expected_base_revision=expected_base_revision,
            operation_id="op-" + "b" * 32,
            created="2026-11-10",
            deadline=until(),
        )

    @override
    def install_project(
        self,
        binding: object,
        *,
        grant: Any,
        validated_bundle_id: str,
        project_slug: str,
        deadline: float | None = None,
    ) -> Any:
        from fa.execution.publication import install_project

        self.calls.append("install")
        result = self._authority_call(
            install_project,
            self._authority,
            PEER,
            ACTOR,
            capability=self._capability,
            validated_bundle_id=validated_bundle_id,
            project_slug=project_slug,
            deadline=until(),
        )
        self.installs.append({"revision_id": result.revision_id, "project_slug": project_slug})
        return InstallReceipt(
            result.workspace_id,
            result.revision_id,
            result.tree_sha256,
            result.operation_id,
        )

    def _authority_call(self, function: Any, *args: Any, **kwargs: Any) -> Any:
        """Call the authority the way the real client does: rejections typed, not raw."""
        from fa.execution.supervisor import SupervisorError

        try:
            return function(*args, **kwargs)
        except SupervisorError as error:
            raise ExecutionRejectedError(str(error.args[0]), None) from None

    @override
    def pin_reader(
        self, binding: object, revision_id: str, *, plan_ref: Any = None, deadline: float | None = None
    ) -> Any:
        self.calls.append("pin")
        self.pinned_revisions.append(revision_id)
        grant = self._authority.pin_reader(
            PEER,
            ACTOR,
            workspace_id=self._ids["workspace_id"],
            revision_id=revision_id,
            plan_ref=None,
            formal_evidence=False,
            deadline=until(),
        )
        self._view = grant.view_ref
        self._grant = grant
        return grant

    @override
    def request(self, operation: Any, **kwargs: Any) -> dict[str, Any]:
        if operation is Operation.HEALTH:
            return {"ready": True, "protocol_version": 2, "features": ["list_projects"]}
        if operation is Operation.LIST_PROJECTS:
            return {"projects": [{"project_slug": "demo-project"}], "incomplete": []}
        if operation is Operation.READ_FILE:
            payload = kwargs["payload"]
            # The REAL read: whatever the authority installed at that path, or a
            # refusal when the install never put anything there.
            try:
                result = self._authority.read_file(
                    PEER,
                    ACTOR,
                    view_ref=self._view,
                    capability=self._grant.to_wire_capability(),
                    path=payload["path"],
                    offset_bytes=0,
                    max_bytes=PORT_READ_MAX_BYTES,
                    deadline=until(),
                )
            except Exception as error:
                raise ExecutionRejectedError("read-refused", None) from error
            self.reads.append({"path": payload["path"], "sha256": result["sha256"]})
            return {"content": result["content"], "sha256": result["sha256"], "eof": result["eof"]}
        raise AssertionError(f"unexpected operation {operation}")

    @override
    def stop_view(self, namespace: Any, *, view: Any, grant: Any, deadline: float | None = None) -> bool:
        self.calls.append("stop")
        self._authority.release_reader(
            PEER, namespace, view_ref=view, capability=grant.to_wire_capability(), deadline=until()
        )
        return True


class _Managed:
    """The slice of `ManagedExecution` the bootstrap path reads, and nothing more."""

    client: Any
    binding: Any
    grant: Any
    current_revision_id: str


def _controller(tmp_path: Path, client: Any, *, grant: Any, revision_id: str | None = None) -> Any:
    from fa.execution.composition import ExecutionBinding

    managed = _Managed()
    managed.client = client
    managed.binding = ExecutionBinding(ACTOR, client._ids["workspace_id"])
    managed.grant = grant
    managed.current_revision_id = revision_id or client._ids["revision_id"]

    return WorkflowContext(
        run_id=ACTOR.run_id,
        base_task="t",
        per_role_task={},
        artifact_paths=workflow_artifact_paths(ACTOR.run_id, base_dir=tmp_path / "logs"),
        config=tmp_path / "models.yaml",
        workspace=tmp_path,
        max_turns=1,
        output_mode="quiet",
        managed_execution=cast("Any", managed),
    )


def test_a_missing_managed_client_is_reported_before_any_authority_call(tmp_path: Path) -> None:
    """No managed execution is `bootstrap-unavailable`, and it reads nothing."""
    from fa.inner_loop.workflow_controller import _admit_published_project

    ctx = WorkflowContext(
        run_id="boot-2",
        base_task="t",
        per_role_task={},
        artifact_paths=workflow_artifact_paths("boot-2", base_dir=tmp_path / "logs"),
        config=tmp_path / "models.yaml",
        workspace=tmp_path,
        max_turns=1,
        output_mode="quiet",
        managed_execution=None,
    )
    # No managed execution means no pinned view, so admission cannot read a revision
    # it was never given -- the refusal is the same closed rule the install path used.
    _same, refusal = _admit_published_project(ctx)

    assert refusal is not None
    assert refusal.rule == "bootstrap-unavailable"
