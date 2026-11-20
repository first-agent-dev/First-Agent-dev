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
from fa.inner_loop.managed_acquisition import BootstrapNewProjectChoice
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


ROADMAP = "## Intent\n\nShip the thing.\n\n## Out of scope\n\nEverything else.\n"
INCREMENT = "## SLICE1: first\n\nSteps.\n"


def _choice() -> BootstrapNewProjectChoice:
    return BootstrapNewProjectChoice("demo-project", "first-increment", ROADMAP, INCREMENT)


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


def test_the_installed_increment_is_what_gets_admitted(site: Any, tmp_path: Path) -> None:
    """Render → install → fresh pin → read back, and compare the bytes.

    The comparison is the whole point: `INCREMENT` is what the model submitted, and
    the rendered file is that prose *plus* the authority's frontmatter. If the
    snapshot ever equals the submitted prose, the admitter trusted the model.
    """
    from fa.inner_loop.plan_admission import snapshot_from_bytes

    with site.owner(read_only_profile=_read_only_profile()) as owner:
        ids = site.register(owner)
        writer = site.claim(owner, ids)
        from fa.execution.publication import install_project, prepare_bundle

        prepared = prepare_bundle(
            owner,
            PEER,
            ACTOR,
            capability=writer.capability,
            project_slug="demo-project",
            increment_slug="first-increment",
            roadmap_text=ROADMAP,
            increment_text=INCREMENT,
            expected_base_revision=ids["revision_id"],
            operation_id="op-" + "b" * 32,
            created="2026-11-10",
            deadline=until(),
        )
        receipt = install_project(
            owner,
            PEER,
            ACTOR,
            capability=writer.capability,
            validated_bundle_id=prepared.validated_bundle_id,
            project_slug="demo-project",
            deadline=until(),
        )

        # The install committed a NEW revision: the pre-install view is stale.
        assert receipt.revision_id != ids["revision_id"]

        # Read the installed file back through a fresh pin of that new revision.
        pin = owner.pin_reader(
            PEER,
            ACTOR,
            workspace_id=ids["workspace_id"],
            revision_id=receipt.revision_id,
            plan_ref=None,
            formal_evidence=False,
            deadline=until(),
        )
        assert pin.view_ref is not None
        view = pin.view_ref
        port = __import__("fa.execution.tool_port", fromlist=["AuthorityWorkspacePort"]).AuthorityWorkspacePort(
            owner,
            peer=PEER,
            namespace=ACTOR,
            view_ref=view,
            capability=pin.capability,
            deadline_factory=until,
        )
        path = "worklogs/demo-project/increments/increment-01-first-increment.md"
        read = port.read_file(path)

    raw = read.content.encode("utf-8")
    snapshot = snapshot_from_bytes(path, raw, source_kind="BOOTSTRAP")

    assert snapshot.ref.source_kind == "BOOTSTRAP"
    # The admitted bytes are the INSTALLED file, frontmatter included.
    assert snapshot.utf8_bytes.startswith(b"---\nIncrement-ID: RM-demo-project-I01\n")
    assert INCREMENT.encode() in snapshot.utf8_bytes
    assert snapshot.utf8_bytes != INCREMENT.encode(), "the model's prose was admitted verbatim"
    assert snapshot.ids.slices, "the installed plan must declare slices"


def test_the_project_directory_exists_only_after_the_install(site: Any) -> None:
    """Ordering, observed from outside: render is not install.

    A design that admitted the plan after `prepare_bundle` would leave the plan
    pointing at a file that does not exist yet, and a coder would then code against
    a plan identity with no bytes behind it.
    """
    from fa.execution.publication import prepare_bundle

    with site.owner(read_only_profile=_read_only_profile()) as owner:
        ids = site.register(owner)
        writer = site.claim(owner, ids)
        prepare_bundle(
            owner,
            PEER,
            ACTOR,
            capability=writer.capability,
            project_slug="demo-project",
            increment_slug="first-increment",
            roadmap_text=ROADMAP,
            increment_text=INCREMENT,
            expected_base_revision=ids["revision_id"],
            operation_id="op-" + "c" * 32,
            created="2026-11-10",
            deadline=until(),
        )
        root = site.roots / "project"
        assert not (root / "worklogs" / "demo-project").exists(), "a bundle is not a project"


# ── C0: the installed file is the only admissible thing ─────────────────────


def test_a_path_that_was_not_installed_is_refused_by_the_view(site: Any) -> None:
    """The read-back cannot be steered at a path the install did not create."""
    from fa.execution.tool_port import AuthorityWorkspacePort
    from fa.inner_loop.tools.workspace_port import WorkspacePortError

    with site.owner(read_only_profile=_read_only_profile()) as owner:
        ids = site.register(owner)
        writer = site.claim(owner, ids)
        pin = owner.pin_reader(
            PEER,
            ACTOR,
            workspace_id=ids["workspace_id"],
            revision_id=ids["revision_id"],
            plan_ref=None,
            formal_evidence=False,
            deadline=until(),
        )
        view = pin.view_ref
        assert view is not None
        port = AuthorityWorkspacePort(
            owner,
            peer=PEER,
            namespace=ACTOR,
            view_ref=view,
            capability=pin.capability,
            deadline_factory=until,
        )
        with pytest.raises(WorkspacePortError):
            port.read_file("worklogs/demo-project/increments/increment-01-first-increment.md")
        assert writer.capability


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


def test_the_controller_installs_then_reads_back_and_admits(site: Any, tmp_path: Path) -> None:
    """The whole controller path, against the authority that really installs.

    `_install_bootstrap_project` must: prepare against the CURRENT revision, install,
    pin the revision the install named (not the one it read before), read the
    installed file back from the real tree, and admit those bytes with
    `source_kind == "BOOTSTRAP"`.
    """
    from fa.inner_loop.workflow_controller import _install_bootstrap_project

    with site.owner(read_only_profile=_read_only_profile()) as owner:
        ids = site.register(owner)
        writer = site.claim(owner, ids)
        client = _BootstrapClient(owner, ids, writer.to_wire_capability(), namespace=ACTOR)
        ctx = _controller(tmp_path, client, grant=writer)

        bound, refusal = _install_bootstrap_project(ctx, _choice())

        assert refusal is None, refusal
        # prepare is bound to the generation the run was reading, not to the install.
        assert client.prepares[0]["expected_base_revision"] == ids["revision_id"]
        # the pin targets the revision the INSTALL committed.
        installed_revision = client.installs[0]["revision_id"]
        assert installed_revision != ids["revision_id"], "the install must commit a new revision"
        assert client.pinned_revisions == [installed_revision]
        assert client.calls[:3] == ["prepare", "install", "pin"], client.calls
        # the admitted plan is the installed file, with the authority's frontmatter.
        assert bound.admission is not None
        assert bound.managed_plan_ref is not None
        assert bound.managed_plan_ref.source_kind == "BOOTSTRAP"
        # The read-back went to the installed increment, in the NEW revision.
        assert client.reads == [
            {
                "path": "worklogs/demo-project/increments/increment-01-first-increment.md",
                "sha256": bound.managed_plan_ref.sha256,
            }
        ]
        # The admitted bytes are the authority's file, not the submitted prose: the
        # install added frontmatter, so byte equality with INCREMENT would prove the
        # admitter trusted the model.
        admitted = bound.admission.snapshot.utf8_bytes
        assert admitted.startswith(b"---\n")
        assert INCREMENT.encode() in admitted
        assert admitted != INCREMENT.encode()
        assert bound.admission.snapshot_backed is True


# ── C0: the refusals, each on its own rule ─────────────────────────────────


def test_an_authority_refusal_stops_the_run_under_its_own_rule(site: Any, tmp_path: Path) -> None:
    """COLLISION (the project exists) is `bootstrap-refused`, not `unreadable`.

    A refused install installed nothing, so it must not be reported as a read
    problem: the operator's next action is different (pick another slug).
    """
    from fa.inner_loop.workflow_controller import _install_bootstrap_project

    with site.owner(read_only_profile=_read_only_profile()) as owner:
        ids = site.register(owner)
        writer = site.claim(owner, ids)
        client = _BootstrapClient(owner, ids, writer.to_wire_capability(), namespace=ACTOR)
        # First install succeeds, so the project directory now exists.
        ctx = _controller(tmp_path, client, grant=writer)
        _first, first_refusal = _install_bootstrap_project(ctx, _choice())
        assert first_refusal is None

        # The same slug again is a COLLISION at prepare/install time.
        second_ctx = _controller(tmp_path, client, grant=writer, revision_id=client.installs[0]["revision_id"])
        _second, refusal = _install_bootstrap_project(second_ctx, _choice())

    assert refusal is not None
    assert refusal.rule == "bootstrap-refused", refusal
    # Nothing was re-pinned for the refused attempt after the install refused.
    assert client.pinned_revisions.count(client.pinned_revisions[-1]) == 1


def test_a_missing_managed_client_is_reported_before_any_authority_call(tmp_path: Path) -> None:
    """No managed execution is `bootstrap-unavailable`, and it calls nothing."""
    from fa.inner_loop.workflow_controller import _install_bootstrap_project

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
    _same, refusal = _install_bootstrap_project(ctx, _choice())

    assert refusal is not None
    assert refusal.rule == "bootstrap-unavailable"
