"""D10-D12: schema_version 2 admission provenance, receipts, and closed refusals."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import pytest

from fa.execution.client import (
    ExecutionUnavailableError,
    ExecutionUncertainError,
)
from fa.execution.composition import (
    BoundPlanPublisher,
    ManagedExecution,
    managed_execution_for_run,
)
from fa.execution.publication import render_bundle
from fa.execution.service import SupervisorService, read_config_file
from fa.execution.types import Access, GrantReply, NamespaceRef, ViewPurpose
from fa.inner_loop.admission_schema import validate_admission_record
from fa.inner_loop.coder_loop import SessionOutcome
from fa.inner_loop.plan_promotion import PlanPromotionError
from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind
from fa.inner_loop.project_scaffold import scaffold_files
from fa.inner_loop.tools.workflow_tool import (
    WorkflowInvocationContext,
    build_invoke_workflow_tool,
)
from fa.inner_loop.workflow_controller import (
    AcquisitionSubstrateRequest,
    run_workflow,
    workflow_artifact_paths,
)
from fa.session.manager import RunContext, SessionManager
from fa.session.provisioning import ProvisionedWorkspace
from fa.workspace_bootstrap import ReadyState, ReadyStatus
from tests.test_execution_composition import _serving_supervisor
from tests.test_execution_service import _registered
from tests.test_execution_views import native_profile, read_only_profile
from tests.test_execution_workspace import Site
from tests.test_execution_workspace import site as site

_OP_ID_RE = re.compile(r"op-[0-9a-f]{32}")
_REV_ID_RE = re.compile(r"rev-[0-9a-f]{32}")

_VALID_ROADMAP = "## Intent\n\nBuild the demo slice cleanly.\n\n## Out of scope\n\nEverything outside SLICE1.\n"
_VALID_INCREMENT = (
    "## SLICE1: Foundation\n"
    "CONTRACTS:\n"
    "  CT1 [CONSTRAINT]: initial boundary holds.\n"
    "TESTS: tests/test_admission_v2_provenance.py\n"
)
_INVALID_INCREMENT = "## SLICE1: Foundation\nCONTRACTS:\n  CT1 [CONSTRAINT]: initial boundary holds.\n"

# D-V2-1: a NEW project is authored under PLAN-V2, so the bootstrap fixtures are
# real V2 documents. The existing-project fixtures above stay V1 on purpose: that
# route is the frozen legacy one, and CTRL-V1 admission still owns it.
#: The slice body the scaffold leaves empty. `slices: 1` in the frontmatter plus one
#: SLICE heading is the smallest pair the V2 grammar admits.
_INCREMENT_BODY = (
    "\n## SLICE1: Foundation\n\n"
    "CONTRACTS:\n"
    "  CT1 [CONSTRAINT]: the initial boundary holds.\n"
    "TESTS:\n"
    "  - worklogs/demo-project/acceptance/tests/test_initial.py::test_initial\n"
)
#: The typed payload a PLAN-V2 bootstrap carries (D-V2-7). The planner writes semantics;
#: the controller renders the Markdown these tests then read back from the authority.
_V2_SEMANTICS: dict[str, object] = {
    "intent": "Build the demo slice cleanly.",
    "out_of_scope": "Everything outside SLICE1.",
    "questions": [],
    "invariants": [
        {
            "number": "1",
            "kind": "HARD",
            "text": "the initial boundary holds.",
            "evidence": "TEST_REQUIRED",
            "reason": None,
        }
    ],
    "scenarios": [],
    "slices": [
        {
            "number": "1",
            "name": "Foundation",
            "steps_mode": "prescriptive",
            "contracts": [{"number": "1", "cls": "CONSTRAINT", "inv": "INV-1", "text": "the initial boundary holds"}],
            "acceptance": [
                {
                    "test_id": "TEST-1.1",
                    "ct": "CT-1.1",
                    "selector": "acceptance/tests/test_foundation.py::test_foundation",
                }
            ],
            "kill_targets": [],
            "exit_checks": [{"check": "CHECK-1", "step": "STEP1", "test_ids": ["TEST-1.1"]}],
            "steps": [{"number": "1", "text": "hold the boundary.", "check": "CHECK-1"}],
        }
    ],
}
#: A payload that renders an inadmissible pair: `parse_acquisition_choice` refuses it, so
#: this is the "the model sent semantics the grammar rejects" case on the real wire.
_V2_INVALID_SEMANTICS: dict[str, object] = {
    **_V2_SEMANTICS,
    "invariants": [],
}
# The pair a real authoring stage publishes: the harness's scaffold with a body the
# parser accepts. Built from the scaffold rather than a renderer, because D-V2-9
# deleted the renderer -- a test that rendered would be testing a dead wire.
def _scaffolded_pair(slug: str = "demo-project", *, extra: str = "") -> tuple[str, str]:
    files = scaffold_files(slug, created="2026-11-05")
    roadmap = files[f"worklogs/{slug}/roadmap.md"].replace(
        "## Intent\n\n## Out of scope\n",
        f"## Intent\n\nBuild the demo slice cleanly.{extra}\n\n## Out of scope\n\nEverything outside SLICE1.\n",
    )
    increment = files[f"worklogs/{slug}/increments/increment-01-initial-plan.md"].replace("slices: 0", "slices: 1")
    return roadmap, increment + _INCREMENT_BODY


_V2_ROADMAP, _V2_INCREMENT = _scaffolded_pair()
# Invalid for the same reason a V2 document is ever invalid on this route: the
# marker is what makes it a V2 plan at all.
_V2_INVALID_INCREMENT = _V2_INCREMENT.replace("Plan-Format: AI-NATIVE-PLAN-V2\n\n", "", 1)
_KILL_INCREMENT = _VALID_INCREMENT.replace(
    "TESTS:",
    "  CT2 [FUNCTIONAL]: bounded repair must validate the directive.\n"
    "    kill: neutralise src/fa/inner_loop/slice_verification.py::_run_one\nTESTS:",
)
_MALFORMED_KILL_INCREMENT = _KILL_INCREMENT.replace("::_run_one", " missing_symbol")
_REPAIRED_KILL_INCREMENT = _KILL_INCREMENT


def _service_document(site: Site) -> dict[str, Any]:
    return {
        "state_root": str(site.state),
        "socket_path": str(site.state.parent / "supervisor.sock"),
        "controller_uids": [os.getuid()],
        "approved_roots": {"projects": str(site.roots)},
        "profiles": [asdict(native_profile()), asdict(read_only_profile())],
        "rpc_timeout_ms": 2000,
        "lock_timeout_ms": 25,
        "view_profile_id": native_profile().profile_id,
        "read_only_profile_id": read_only_profile().profile_id,
    }


def _write_configs(tmp_path: Path, site: Site) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    service_path = tmp_path / "execution.json"
    service_path.write_text(json.dumps(_service_document(site)), encoding="utf-8")
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(f"execution:\n  service_config: {service_path}\n", encoding="utf-8")
    return service_path, yaml_path


def _write_project_files(workspace: Path, slug: str, increment_body: str, *, include_warn_gap: bool = False) -> None:
    files = render_bundle(slug, "foundation", _VALID_ROADMAP, increment_body, created="2026-11-05")
    for rel, content in files.items():
        if include_warn_gap and rel.endswith(".md") and "increment-01" in rel:
            text = content.decode("utf-8").replace(
                "CONTRACTS:\n",
                "CONTRACTS:\n  CT2 [FUNCTIONAL]: functional entry without kill directive; see CT99.\n",
            )
            content = text.encode("utf-8")
        target = workspace / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def _read_admission(logs_dir: Path, run_id: str) -> dict[str, Any]:
    path = workflow_artifact_paths(run_id, base_dir=logs_dir).admission
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


@contextmanager
def _managed_child_env(
    site: Site,
    tmp_path: Path,
    *,
    parent_run_id: str = "parent-run-1",
    child_run_id: str = "child-run-1",
) -> Any:
    service_path, yaml_path = _write_configs(tmp_path, site)
    logs_dir = tmp_path / "logs"
    parent_ctx = RunContext(parent_run_id, "session-1", site.source, site.source / ".db", logs_dir)
    child_ctx = RunContext(child_run_id, "session-1", site.source, site.source / ".db", logs_dir)
    with SupervisorService(read_config_file(service_path)) as service:
        _registered(service)
        with _serving_supervisor(service):
            managed = managed_execution_for_run(parent_ctx, config_path=yaml_path)
            assert managed is not None
            managed.handoff_to(NamespaceRef("session-1", child_run_id, parent_run_id=parent_run_id))
            publisher = BoundPlanPublisher(managed, managed.binding)
            try:
                yield managed, publisher, child_ctx, yaml_path
            finally:
                managed.handoff_to(NamespaceRef("session-1", parent_run_id))
                managed.close()


def _eval_pass_stage(sink: list[SessionOutcome] | None) -> int:
    if isinstance(sink, list):
        sink.append(
            SessionOutcome(
                exit_code=0,
                stop_reason="stopped_by_llm",
                turns=1,
                final_text=(
                    "## Verification Summary\n\n### Step results\n- SLICE1: PASS\n\n"
                    "### Verdict\nPASS\n\n### Route decision\ncomplete\n"
                ),
            )
        )
    return 0


def test_q150a_top_level_managed_run_keeps_v1_while_child_emits_acquiring_then_v2(site: Site, tmp_path: Path) -> None:
    """Q150=A: owner_run_id == run_id stays v1; managed child emits v2 ACQUIRING then EXISTING_SELECTION."""
    _write_project_files(site.source, "demo-project", _VALID_INCREMENT)
    service_path, yaml_path = _write_configs(tmp_path, site)
    top_logs = tmp_path / "top-logs"
    top_ctx = RunContext("parent-run-1", "session-1", site.source, site.source / ".db", top_logs)

    with SupervisorService(read_config_file(service_path)) as service:
        _registered(service)
        with _serving_supervisor(service):
            top_managed = managed_execution_for_run(top_ctx, config_path=yaml_path)
            assert top_managed is not None
            top_publisher = BoundPlanPublisher(top_managed, top_managed.binding)
            top_selection = json.dumps(
                {"kind": "SELECT_EXISTING", "project_slug": "demo-project", "increment_id": "I01"}
            )

            def top_stage(args: argparse.Namespace, **kwargs: Any) -> int:
                role = str(getattr(args, "role", ""))
                sink = kwargs.get("outcome_sink")
                if role == "planner" and isinstance(sink, list):
                    sink.append(SessionOutcome(0, "stopped_by_llm", 1, top_selection))
                elif role == "eval":
                    return _eval_pass_stage(sink)
                return 0

            code, state = run_workflow(
                roles=["planner", "coder"],
                task="run",
                per_role_task={},
                mode="linear",
                max_repairs=0,
                max_replans=0,
                run_id="parent-run-1",
                config=yaml_path,
                workspace=site.source,
                max_turns=2,
                output_mode="quiet",
                run_stage_fn=top_stage,
                run_context=top_ctx,
                plan_publisher=top_publisher,
                managed_execution=top_managed,
                acquisition=AcquisitionSubstrateRequest(),
            )
            assert code == 0 and state is not None and state.status == "DONE"
            top_record = _read_admission(top_logs, "parent-run-1")
            assert top_record["schema_version"] == 1
            assert validate_admission_record(top_record, run_id="parent-run-1") == top_record
            top_managed.close()

            child_ctx = RunContext(
                "child-run-1", "session-1", site.source, site.source / ".db", tmp_path / "child-logs"
            )
            managed = managed_execution_for_run(top_ctx, config_path=yaml_path)
            assert managed is not None
            managed.handoff_to(NamespaceRef("session-1", child_ctx.run_id, parent_run_id="parent-run-1"))
            publisher = BoundPlanPublisher(managed, managed.binding)
            observed_acquiring: list[dict[str, Any]] = []

            def child_stage(args: argparse.Namespace, **kwargs: Any) -> int:
                role = str(getattr(args, "role", ""))
                sink = kwargs.get("outcome_sink")
                if role == "planner":
                    observed_acquiring.append(_read_admission(child_ctx.run_log_dir, child_ctx.run_id))
                    if isinstance(sink, list):
                        sink.append(SessionOutcome(0, "stopped_by_llm", 1, top_selection))
                elif role == "eval":
                    return _eval_pass_stage(sink)
                return 0

            try:
                code, state = run_workflow(
                    roles=["planner", "coder"],
                    task="run",
                    per_role_task={},
                    mode="linear",
                    max_repairs=0,
                    max_replans=0,
                    run_id=child_ctx.run_id,
                    config=yaml_path,
                    workspace=site.source,
                    max_turns=2,
                    output_mode="quiet",
                    run_stage_fn=child_stage,
                    run_context=child_ctx,
                    plan_publisher=publisher,
                    managed_execution=managed,
                    acquisition=AcquisitionSubstrateRequest(),
                )
                assert code == 0 and state is not None and state.status == "DONE"
                assert len(observed_acquiring) == 1
                acquiring = observed_acquiring[0]
                assert acquiring["schema_version"] == 2
                assert acquiring["status"] == "ACQUIRING"
                assert acquiring["plan_ref"] is None
                assert acquiring["attempts"] == []
                assert acquiring["owner_run_id"] == "parent-run-1"
                assert validate_admission_record(acquiring, run_id=child_ctx.run_id) == acquiring

                final = _read_admission(child_ctx.run_log_dir, child_ctx.run_id)
                assert final["schema_version"] == 2
                assert final["status"] == "ADMITTED"
                assert final["plan_ref"]["source_kind"] == "EXISTING_SELECTION"
                assert validate_admission_record(final, run_id=child_ctx.run_id) == final
                attempt = final["attempts"][0]
                assert attempt["dispatch_kind"] == "ACQUISITION"
                assert attempt["source_sha256"] == final["plan_ref"]["sha256"]
                assert attempt["candidate_sha256"] is None
                assert attempt["promoted_sha256"] is None
                assert attempt["bundle_sha256"] is None
                assert attempt["operation_id"] is None
                assert attempt["input_revision"] == attempt["output_revision"] == final["base_revision"]
            finally:
                managed.handoff_to(NamespaceRef("session-1", "parent-run-1"))
                managed.close()


@pytest.mark.parametrize("repair_allowed", [True, False])
def test_ct52_malformed_kill_directive_requires_bounded_repair_before_coder(
    site: Site, tmp_path: Path, repair_allowed: bool
) -> None:
    """C1: CT52 diagnostic reaches admission; only a validated repair can admit coder."""
    _write_project_files(site.source, "demo-project", _MALFORMED_KILL_INCREMENT)
    repaired_files = render_bundle(
        "demo-project", "foundation", _VALID_ROADMAP, _REPAIRED_KILL_INCREMENT, created="2026-11-05"
    )
    repaired_body = repaired_files["worklogs/demo-project/increments/increment-01-foundation.md"].decode("utf-8")
    stages: list[str] = []
    with _managed_child_env(site, tmp_path) as (managed, publisher, child_ctx, yaml_path):
        initial_revision = managed.current_revision_id
        selection = json.dumps({"kind": "SELECT_EXISTING", "project_slug": "demo-project", "increment_id": "I01"})

        def stage_fn(args: argparse.Namespace, **kwargs: Any) -> int:
            role = str(getattr(args, "role", ""))
            dispatch: PlannerDispatch | None = kwargs.get("planner_dispatch")
            sink = kwargs.get("outcome_sink")
            if role == "planner":
                assert dispatch is not None
                stages.append(dispatch.kind.value)
                if dispatch.kind == PlannerDispatchKind.ADMISSION_REPAIR:
                    assert repair_allowed and dispatch.candidate_target is not None
                    (site.source / dispatch.candidate_target).write_text(repaired_body, encoding="utf-8")
                    if isinstance(sink, list):
                        sink.append(SessionOutcome(0, "stopped_by_llm", 1, "corrected"))
                elif isinstance(sink, list):
                    sink.append(SessionOutcome(0, "stopped_by_llm", 1, selection))
            elif role == "eval":
                return _eval_pass_stage(sink)
            elif role == "coder":
                stages.append("coder")
                assert repair_allowed
                assert _read_admission(child_ctx.run_log_dir, child_ctx.run_id)["status"] == "ADMITTED"
            return 0

        code, state = run_workflow(
            roles=["planner", "coder"],
            task="repair directive",
            per_role_task={},
            mode="adaptive",
            max_repairs=0,
            max_replans=1 if repair_allowed else 0,
            run_id=child_ctx.run_id,
            config=yaml_path,
            workspace=site.source,
            max_turns=2,
            output_mode="quiet",
            run_stage_fn=stage_fn,
            run_context=child_ctx,
            plan_publisher=publisher,
            managed_execution=managed,
            acquisition=AcquisitionSubstrateRequest(),
        )
        record = _read_admission(child_ctx.run_log_dir, child_ctx.run_id)
        assert validate_admission_record(record, run_id=child_ctx.run_id) == record
        assert record["attempts"][0]["route"] == "RETRY"
        assert any(d["rule"] == "kill-directive-malformed" for d in record["attempts"][0]["diagnostics"])
        if repair_allowed:
            assert code == 0 and state is not None and state.status == "DONE"
            assert stages == ["ACQUISITION", "ADMISSION_REPAIR", "coder"]
            assert record["status"] == "ADMITTED"
            assert record["attempts"][-1]["route"] == "ADMITTED"
            assert record["attempts"][-1]["output_revision"] != initial_revision
        else:
            assert code != 0 and state is not None and state.status == "FAILED"
            assert stages == ["ACQUISITION"]
            assert record["status"] == "BLOCKED"
            assert record["attempts"][-1]["route"] == "BLOCKED"
            assert record["attempts"][-1]["output_revision"] == initial_revision


def test_v2_existing_selection_repair_records_fail_only_retry_and_published_receipts(
    site: Site, tmp_path: Path
) -> None:
    """EXISTING_SELECTION with FAIL+WARN -> RETRY (FAIL only) -> ADMISSION_REPAIR ADMITTED via BoundPlanPublisher."""
    _write_project_files(site.source, "demo-project", _INVALID_INCREMENT, include_warn_gap=True)
    repaired_files = render_bundle("demo-project", "foundation", _VALID_ROADMAP, _VALID_INCREMENT, created="2026-11-05")
    repaired_body = repaired_files["worklogs/demo-project/increments/increment-01-foundation.md"].decode("utf-8")

    with _managed_child_env(site, tmp_path) as (managed, publisher, child_ctx, yaml_path):
        initial_rev = managed.current_revision_id
        selection = json.dumps({"kind": "SELECT_EXISTING", "project_slug": "demo-project", "increment_id": "I01"})

        def stage_fn(args: argparse.Namespace, **kwargs: Any) -> int:
            role = str(getattr(args, "role", ""))
            sink = kwargs.get("outcome_sink")
            if role == "planner":
                dispatch: PlannerDispatch | None = kwargs.get("planner_dispatch")
                assert dispatch is not None
                if dispatch.kind == PlannerDispatchKind.ADMISSION_REPAIR:
                    assert dispatch.candidate_target is not None
                    (site.source / dispatch.candidate_target).write_text(repaired_body, encoding="utf-8")
                    if isinstance(sink, list):
                        sink.append(SessionOutcome(0, "stopped_by_llm", 1, "repaired"))
                    return 0
                if isinstance(sink, list):
                    sink.append(SessionOutcome(0, "stopped_by_llm", 1, selection))
                return 0
            if role == "eval":
                return _eval_pass_stage(sink)
            return 0

        code, state = run_workflow(
            roles=["planner", "coder"],
            task="repair existing plan",
            per_role_task={},
            mode="adaptive",
            max_repairs=0,
            max_replans=1,
            run_id=child_ctx.run_id,
            config=yaml_path,
            workspace=site.source,
            max_turns=2,
            output_mode="quiet",
            run_stage_fn=stage_fn,
            run_context=child_ctx,
            plan_publisher=publisher,
            managed_execution=managed,
            acquisition=AcquisitionSubstrateRequest(),
        )
        assert code == 0 and state is not None and state.status == "DONE"
        record = _read_admission(child_ctx.run_log_dir, child_ctx.run_id)
        assert validate_admission_record(record, run_id=child_ctx.run_id) == record
        assert len(record["attempts"]) == 2
        first, second = record["attempts"]
        assert first["dispatch_kind"] == "ACQUISITION" and first["route"] == "RETRY"
        assert all(item["severity"] == "FAIL" for item in first["diagnostics"])
        assert first["input_revision"] == first["output_revision"] == initial_rev
        assert second["dispatch_kind"] == "ADMISSION_REPAIR" and second["route"] == "ADMITTED"
        assert second["input_revision"] == initial_rev
        assert second["output_revision"] == managed.current_revision_id != initial_rev
        assert _OP_ID_RE.fullmatch(second["operation_id"] or "") is not None
        assert second["bundle_sha256"] is None
        assert second["promoted_sha256"] == second["candidate_sha256"] == record["plan_ref"]["sha256"]


def test_v2_existing_selection_with_zero_planner_budget_blocks_via_retry_then_blocked_repair(
    site: Site, tmp_path: Path
) -> None:
    """EXISTING_SELECTION with max_repairs=0 emits ACQUISITION RETRY -> ADMISSION_REPAIR BLOCKED in v2."""
    _write_project_files(site.source, "demo-project", _INVALID_INCREMENT)
    repair_dispatched: list[PlannerDispatchKind] = []

    with _managed_child_env(site, tmp_path) as (managed, publisher, child_ctx, yaml_path):
        selection = json.dumps({"kind": "SELECT_EXISTING", "project_slug": "demo-project", "increment_id": "I01"})

        def stage_fn(args: argparse.Namespace, **kwargs: Any) -> int:
            dispatch: PlannerDispatch | None = kwargs.get("planner_dispatch")
            if dispatch is not None and dispatch.kind != PlannerDispatchKind.ACQUISITION:
                repair_dispatched.append(dispatch.kind)
            sink = kwargs.get("outcome_sink")
            if isinstance(sink, list):
                sink.append(SessionOutcome(0, "stopped_by_llm", 1, selection))
            return 0

        code, state = run_workflow(
            roles=["planner", "coder"],
            task="blocked budget",
            per_role_task={},
            mode="linear",
            max_repairs=0,
            max_replans=0,
            run_id=child_ctx.run_id,
            config=yaml_path,
            workspace=site.source,
            max_turns=2,
            output_mode="quiet",
            run_stage_fn=stage_fn,
            run_context=child_ctx,
            plan_publisher=publisher,
            managed_execution=managed,
            acquisition=AcquisitionSubstrateRequest(),
        )
        assert code == 2 and state is not None and state.status == "FAILED"
        assert repair_dispatched == []
        record = _read_admission(child_ctx.run_log_dir, child_ctx.run_id)
        assert validate_admission_record(record, run_id=child_ctx.run_id) == record
        assert record["status"] == "BLOCKED"
        assert [a["dispatch_kind"] for a in record["attempts"]] == ["ACQUISITION", "ADMISSION_REPAIR"]
        assert [a["route"] for a in record["attempts"]] == ["RETRY", "BLOCKED"]


def test_v2_bootstrap_invalid_body_blocks_with_candidate_and_bundle_evidence_and_no_ref(
    site: Site, tmp_path: Path
) -> None:
    """A PLAN-V2 body that does not parse is refused BEFORE the install.

    This used to assert the opposite order — install, then block — because the
    V1 route had no pre-install grammar. Under D-V2-1 a new project is V2, so the
    pair is parsed while nothing exists yet: no bundle, no operation, no project.
    """
    with _managed_child_env(site, tmp_path) as (managed, publisher, child_ctx, yaml_path):
        choice = json.dumps(
            {
                "kind": "BOOTSTRAP_NEW_PROJECT",
                "semantics": _V2_INVALID_SEMANTICS,
            }
        )

        def stage_fn(args: argparse.Namespace, **kwargs: Any) -> int:
            sink = kwargs.get("outcome_sink")
            if isinstance(sink, list):
                sink.append(SessionOutcome(0, "stopped_by_llm", 1, choice))
            return 0

        code, state = run_workflow(
            roles=["planner", "coder"],
            task="bootstrap bad body",
            per_role_task={},
            mode="linear",
            max_repairs=1,
            max_replans=0,
            run_id=child_ctx.run_id,
            config=yaml_path,
            workspace=site.source,
            max_turns=2,
            output_mode="quiet",
            run_stage_fn=stage_fn,
            run_context=child_ctx,
            plan_publisher=publisher,
            managed_execution=managed,
            acquisition=AcquisitionSubstrateRequest(project_slug="bad-project"),
        )
        assert code == 2 and state is not None and state.status == "FAILED"
        record = _read_admission(child_ctx.run_log_dir, child_ctx.run_id)
        assert validate_admission_record(record, run_id=child_ctx.run_id) == record
        assert record["status"] == "BLOCKED" and record["plan_ref"] is None
        attempt = record["attempts"][0]
        assert attempt["diagnostics"][0]["validator"] == "bootstrap"
        assert attempt["diagnostics"][0]["rule"] == "invalid-body"
        # Nothing was rendered into a bundle and nothing was installed, so there
        # is no candidate, no bundle and no operation to report.
        assert attempt["candidate_sha256"] is None and attempt["bundle_sha256"] is None
        assert attempt["operation_id"] is None
        assert attempt["promoted_sha256"] is None and attempt["output_revision"] is None
        assert not (site.source / "worklogs" / "bad-project").exists()


@pytest.mark.parametrize(
    ("final_text", "expected_pair", "expect_refusal_stderr"),
    [
        # With a caller-supplied slug the stage is an *authoring* stage (D-V2-9), so
        # there is no choice wire to test here: an absent, malformed or clarifying
        # reply all mean the same thing -- no documents were authored. The property
        # that survives the deletion is that this is a closed, pre-coder refusal
        # recorded under the admission vocabulary, which is what this case asserts.
        ("", ("bootstrap", "invalid-body"), False),
    ],
)
def test_a_failed_authoring_stage_records_a_closed_pre_coder_refusal(
    site: Site,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    final_text: str,
    expected_pair: tuple[str, str],
    expect_refusal_stderr: bool,
) -> None:
    """D12 (D-V2-9): an authoring stage that authored nothing writes BLOCKED v2 + FAILED state."""
    with _managed_child_env(site, tmp_path) as (managed, publisher, child_ctx, yaml_path):

        def stage_fn(args: argparse.Namespace, **kwargs: Any) -> int:
            sink = kwargs.get("outcome_sink")
            if isinstance(sink, list) and final_text:
                sink.append(SessionOutcome(0, "stopped_by_llm", 1, final_text))
            return 0

        code, state = run_workflow(
            roles=["planner", "coder"],
            task="bad choice",
            per_role_task={},
            mode="linear",
            max_repairs=0,
            max_replans=0,
            run_id=child_ctx.run_id,
            config=yaml_path,
            workspace=site.source,
            max_turns=2,
            output_mode="quiet",
            run_stage_fn=stage_fn,
            run_context=child_ctx,
            plan_publisher=publisher,
            managed_execution=managed,
            acquisition=AcquisitionSubstrateRequest(project_slug="demo-fail"),
        )
        assert code == 2 and state is not None and state.status == "FAILED"
        if expect_refusal_stderr:
            assert f"fa workflow: acquisition choice refused: {expected_pair[1]}" in capsys.readouterr().err
        record = _read_admission(child_ctx.run_log_dir, child_ctx.run_id)
        assert validate_admission_record(record, run_id=child_ctx.run_id) == record
        # A refusal is recorded as BLOCKED with its rule, exactly like every other
        # closed refusal; an authoring stage that published nothing leaves no plan ref
        # (D-V2-8) but must still tell the operator *why*.
        assert record["status"] == "BLOCKED" and record["plan_ref"] is None
        diag = record["attempts"][0]["diagnostics"][0]
        assert (diag["validator"], diag["rule"]) == expected_pair


def test_d11_repair_publish_uncertainty_propagates_operation_id_and_leaves_output_revision_null(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D11: ExecutionUncertainError during repair publish propagates op_id with output_revision=None."""
    _write_project_files(site.source, "demo-project", _INVALID_INCREMENT)
    repaired_files = render_bundle("demo-project", "foundation", _VALID_ROADMAP, _VALID_INCREMENT, created="2026-11-05")
    repaired_body = repaired_files["worklogs/demo-project/increments/increment-01-foundation.md"].decode("utf-8")
    uncertain_op = "op-" + "d" * 32

    with _managed_child_env(site, tmp_path) as (managed, publisher, child_ctx, yaml_path):

        def uncertain_publish(*_a: Any, **_k: Any) -> Any:
            raise ExecutionUncertainError(uncertain_op, code="DURABILITY_UNKNOWN")

        monkeypatch.setattr(BoundPlanPublisher, "publish_candidate_receipt", uncertain_publish)
        selection = json.dumps({"kind": "SELECT_EXISTING", "project_slug": "demo-project", "increment_id": "I01"})

        def stage_fn(args: argparse.Namespace, **kwargs: Any) -> int:
            dispatch: PlannerDispatch | None = kwargs.get("planner_dispatch")
            sink = kwargs.get("outcome_sink")
            if dispatch is not None and dispatch.kind == PlannerDispatchKind.ADMISSION_REPAIR:
                assert dispatch.candidate_target is not None
                (site.source / dispatch.candidate_target).write_text(repaired_body, encoding="utf-8")
                if isinstance(sink, list):
                    sink.append(SessionOutcome(0, "stopped_by_llm", 1, "repaired"))
                return 0
            if isinstance(sink, list):
                sink.append(SessionOutcome(0, "stopped_by_llm", 1, selection))
            return 0

        code, state = run_workflow(
            roles=["planner", "coder"],
            task="uncertain publish",
            per_role_task={},
            mode="adaptive",
            max_repairs=0,
            max_replans=1,
            run_id=child_ctx.run_id,
            config=yaml_path,
            workspace=site.source,
            max_turns=2,
            output_mode="quiet",
            run_stage_fn=stage_fn,
            run_context=child_ctx,
            plan_publisher=publisher,
            managed_execution=managed,
            acquisition=AcquisitionSubstrateRequest(),
        )
        assert code == 2 and state is not None and state.status == "FAILED"
        record = _read_admission(child_ctx.run_log_dir, child_ctx.run_id)
        assert validate_admission_record(record, run_id=child_ctx.run_id) == record
        second = record["attempts"][1]
        assert second["dispatch_kind"] == "ADMISSION_REPAIR"
        assert second["validation"] == "INDETERMINATE" and second["route"] == "BLOCKED"
        assert second["operation_id"] == uncertain_op
        assert second["output_revision"] is None
        assert second["promoted_sha256"] is None


def test_invoke_workflow_handoff_child_writes_validated_v2_bootstrap_admission(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real parent-to-child HANDOFF via invoke_workflow writes a validated schema_version=2 admission.json."""
    service_path, yaml_path = _write_configs(tmp_path, site)
    state_root = tmp_path / "fa-state"
    monkeypatch.setenv("FA_STATE_ROOT", str(state_root))
    manager = SessionManager(
        state_root=state_root,
        workspace_root=site.roots,
        workspace_preparer=lambda ws, _ctx: ReadyState(
            status=ReadyStatus.READY,
            fingerprint="sha256:test",
            reason_code="ready_managed_artifact",
            log_path=ws / ".fa" / "ready.log",
            repaired=False,
            elapsed_ms=1,
        ),
        workspace_provisioner=lambda _req: ProvisionedWorkspace(
            registered=True,
            workspace_id="ws-" + "1" * 32,
            revision_id="rev-" + "1" * 32,
            tree_sha256="1" * 64,
        ),
    )
    # The child selects an existing project through the parent's published view, so
    # the project has to exist in that view before the handoff.
    _write_project_files(site.source, "child-proj", _VALID_INCREMENT)
    session_ctx = manager.provision_entrypoint_session(session_id="session-1", workspace_override=site.source)
    parent_run = "parent-invoke-1"
    parent_ctx = manager.begin_run(session_ctx, requested_run_id=parent_run)
    child_ids: list[str] = []

    class _ParentLease:
        def __init__(self, managed: ManagedExecution, reader: GrantReply) -> None:
            self._managed = managed
            self._reader = reader

        @property
        def is_handoff_enabled(self) -> bool:
            return True

        def suspend(self, *, deadline: float | None = None) -> str:
            publication = self._managed.publish_stage(self._reader, deadline=deadline)
            return publication.revision_id

        def resume(self, *, deadline: float | None = None) -> None:
            self._reader = self._managed.open_view(
                access=Access.WRITE,
                purpose=ViewPurpose.PROJECT,
                base_revision=self._managed.current_revision_id,
                deadline=deadline,
            )

    with SupervisorService(read_config_file(service_path)) as service:
        _registered(service)
        with _serving_supervisor(service):
            managed = managed_execution_for_run(parent_ctx, config_path=yaml_path)
            assert managed is not None
            reader = managed.open_view(
                access=Access.WRITE,
                purpose=ViewPurpose.PROJECT,
                base_revision=managed.current_revision_id,
            )
            lease = _ParentLease(managed, reader)
            parent_choice = json.dumps(
                {"kind": "SELECT_EXISTING", "project_slug": "child-proj", "increment_id": "I01"}
            )

            def stage_fn(args: argparse.Namespace, **kwargs: Any) -> int:
                child_ids.append(str(getattr(args, "run_id", "")))
                role = str(getattr(args, "role", ""))
                sink = kwargs.get("outcome_sink")
                if role == "planner" and isinstance(sink, list):
                    sink.append(SessionOutcome(0, "stopped_by_llm", 1, parent_choice))
                elif role == "eval":
                    return _eval_pass_stage(sink)
                return 0

            tool = build_invoke_workflow_tool(
                run_workflow,
                lambda: WorkflowInvocationContext(
                    parent_run_id=parent_run,
                    config=yaml_path,
                    workspace=site.source,
                    max_turns=2,
                    run_stage_fn=stage_fn,
                    workflow_timeout_seconds=30,
                    session_context=session_ctx,
                    run_context=parent_ctx,
                    managed_execution=managed,
                    parent_stage_lease=lease,
                ),
            )
            result = tool.handler(
                {
                    "task": "bootstrap child",
                    "roles": "planner,coder",
                    "mode": "linear",
                    # The child is a selection run: it binds the plan an existing
                    # project already carries, through the parent's published view.
                    "project_action": "AUTO_SELECT_EXISTING",
                }
            )
            assert result.error is None, result.error
            assert isinstance(result.result, dict)
            child_run_id = result.result["run_id"]
            child_logs_dir = state_root / "session-log" / child_run_id
            record = _read_admission(child_logs_dir, child_run_id)
            assert validate_admission_record(record, run_id=child_run_id) == record
            assert record["schema_version"] == 2
            assert record["owner_run_id"] == parent_run
            assert record["plan_ref"]["source_kind"] == "EXISTING_SELECTION"
            assert _REV_ID_RE.fullmatch(record["attempts"][0]["output_revision"] or "") is not None
            lease.suspend(deadline=time.monotonic() + 5.0)
            managed.close()


def test_d11_eval_replan_records_revision_chain_and_operation_ids(site: Site, tmp_path: Path) -> None:
    """D11: EVAL_REPLAN after ADMITTED EXISTING_SELECTION records input_rev -> output_rev + operation_id."""
    _write_project_files(site.source, "demo-project", _VALID_INCREMENT)
    replanned_files = render_bundle(
        "demo-project",
        "foundation",
        _VALID_ROADMAP,
        _VALID_INCREMENT.replace("initial boundary holds.", "replanned boundary holds."),
        created="2026-11-05",
    )
    replanned_body = replanned_files["worklogs/demo-project/increments/increment-01-foundation.md"].decode("utf-8")

    with _managed_child_env(site, tmp_path) as (managed, publisher, child_ctx, yaml_path):
        initial_rev = managed.current_revision_id
        selection = json.dumps({"kind": "SELECT_EXISTING", "project_slug": "demo-project", "increment_id": "I01"})
        eval_calls = 0

        def stage_fn(args: argparse.Namespace, **kwargs: Any) -> int:
            nonlocal eval_calls
            role = str(getattr(args, "role", ""))
            sink = kwargs.get("outcome_sink")
            if role == "planner":
                dispatch: PlannerDispatch | None = kwargs.get("planner_dispatch")
                if dispatch is not None and dispatch.kind == PlannerDispatchKind.EVAL_REPLAN:
                    assert dispatch.candidate_target is not None
                    (site.source / dispatch.candidate_target).write_text(replanned_body, encoding="utf-8")
                    if isinstance(sink, list):
                        sink.append(SessionOutcome(0, "stopped_by_llm", 1, "replanned"))
                    return 0
                if isinstance(sink, list):
                    sink.append(SessionOutcome(0, "stopped_by_llm", 1, selection))
                return 0
            if role == "eval":
                eval_calls += 1
                if eval_calls == 1 and isinstance(sink, list):
                    sink.append(
                        SessionOutcome(
                            0,
                            "stopped_by_llm",
                            1,
                            "## Verification Summary\n\n### Step results\n- SLICE1: FAIL\n\n"
                            "### Verdict\nREPLAN_REQUIRED\n\n### Route decision\nreturn_to_planner\n",
                        )
                    )
                    return 0
                return _eval_pass_stage(sink)
            return 0

        code, state = run_workflow(
            roles=["planner", "coder"],
            task="replan after eval",
            per_role_task={},
            mode="adaptive",
            max_repairs=0,
            max_replans=1,
            run_id=child_ctx.run_id,
            config=yaml_path,
            workspace=site.source,
            max_turns=2,
            output_mode="quiet",
            run_stage_fn=stage_fn,
            run_context=child_ctx,
            plan_publisher=publisher,
            managed_execution=managed,
            acquisition=AcquisitionSubstrateRequest(),
        )
        assert code == 0 and state is not None and state.status == "DONE"
        record = _read_admission(child_ctx.run_log_dir, child_ctx.run_id)
        assert validate_admission_record(record, run_id=child_ctx.run_id) == record
        assert [a["dispatch_kind"] for a in record["attempts"]] == ["ACQUISITION", "EVAL_REPLAN"]
        first, second = record["attempts"]
        assert first["input_revision"] == first["output_revision"] == initial_rev
        assert second["input_revision"] == initial_rev
        assert second["output_revision"] == managed.current_revision_id != initial_rev
        assert _OP_ID_RE.fullmatch(second["operation_id"] or "") is not None
        assert second["promoted_sha256"] == second["candidate_sha256"] == record["plan_ref"]["sha256"]


def test_plan_promotion_scope_allows_acquired_project_slugs_only(tmp_path: Path) -> None:
    """EXPLICIT keeps the CT94 canonical prefix, while EXISTING_SELECTION/BOOTSTRAP accept valid project slugs."""
    from fa.inner_loop.plan_admission import snapshot_from_bytes
    from fa.inner_loop.plan_promotion import seed_plan_candidate

    valid_existing = snapshot_from_bytes(
        "worklogs/demo-project/increments/increment-01-foundation.md",
        b"# plan\n",
        source_kind="EXISTING_SELECTION",
    )
    dispatched = seed_plan_candidate(
        tmp_path, valid_existing, run_id="run-1", kind=PlannerDispatchKind.ADMISSION_REPAIR
    )
    assert dispatched.candidate_target is not None

    explicit_other = snapshot_from_bytes(
        "worklogs/demo-project/increments/increment-01-foundation.md",
        b"# plan\n",
        source_kind="EXPLICIT",
    )
    with pytest.raises(PlanPromotionError) as refused:
        seed_plan_candidate(tmp_path, explicit_other, run_id="run-1", kind=PlannerDispatchKind.ADMISSION_REPAIR)
    assert refused.value.rule == "scope-denied"

    for bad_path in (
        "worklogs/Bad_Slug/increments/increment-01-foundation.md",
        "worklogs/demo-project/increments/.md",
        "worklogs/demo-project/increments/.hidden.md",
    ):
        bad_snap = snapshot_from_bytes(bad_path, b"# plan\n", source_kind="BOOTSTRAP")
        with pytest.raises(PlanPromotionError) as bad_refused:
            seed_plan_candidate(tmp_path, bad_snap, run_id="run-1", kind=PlannerDispatchKind.ADMISSION_REPAIR)
        assert bad_refused.value.rule == "scope-denied"


def test_plan_promotion_error_keeps_operation_id_and_sanitized_message() -> None:
    op = "op-" + "f" * 32
    err = PlanPromotionError("durability-unknown", replaced=True, operation_id=op)
    assert err.rule == "durability-unknown"
    assert err.replaced is True
    assert err.operation_id == op
    assert str(err) == "plan promotion failed: durability-unknown"


def test_v2_existing_selection_source_changed_keeps_output_revision_equal_to_input(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """EXISTING_SELECTION + source-changed in v2 keeps output_revision == input_revision and op_id=None."""
    from fa.inner_loop import workflow_controller
    from fa.inner_loop.plan_admission import PlanRefError

    _write_project_files(site.source, "demo-project", _VALID_INCREMENT)
    with _managed_child_env(site, tmp_path) as (managed, publisher, child_ctx, yaml_path):
        initial_rev = managed.current_revision_id
        selection = json.dumps({"kind": "SELECT_EXISTING", "project_slug": "demo-project", "increment_id": "I01"})
        orig_check = workflow_controller._check_admission_source

        def raise_source_changed(ctx: Any) -> None:
            if ctx.admission is not None and ctx.admission.from_acquisition:
                raise PlanRefError("source-changed")
            orig_check(ctx)

        monkeypatch.setattr(workflow_controller, "_check_admission_source", raise_source_changed)

        def stage_fn(args: argparse.Namespace, **kwargs: Any) -> int:
            sink = kwargs.get("outcome_sink")
            if isinstance(sink, list):
                sink.append(SessionOutcome(0, "stopped_by_llm", 1, selection))
            return 0

        code, state = run_workflow(
            roles=["planner", "coder"],
            task="source changed",
            per_role_task={},
            mode="linear",
            max_repairs=0,
            max_replans=0,
            run_id=child_ctx.run_id,
            config=yaml_path,
            workspace=site.source,
            max_turns=2,
            output_mode="quiet",
            run_stage_fn=stage_fn,
            run_context=child_ctx,
            plan_publisher=publisher,
            managed_execution=managed,
            acquisition=AcquisitionSubstrateRequest(),
        )
        assert code == 2 and state is not None and state.status == "FAILED"
        record = _read_admission(child_ctx.run_log_dir, child_ctx.run_id)
        assert validate_admission_record(record, run_id=child_ctx.run_id) == record
        attempt = record["attempts"][0]
        assert attempt["dispatch_kind"] == "ACQUISITION"
        assert attempt["route"] == "BLOCKED"
        assert attempt["input_revision"] == attempt["output_revision"] == initial_rev
        assert attempt["operation_id"] is None
        assert attempt["diagnostics"][0]["validator"] == "plan-ref"
        assert attempt["diagnostics"][0]["rule"] == "source-changed"


@pytest.mark.parametrize(
    "pin_exc",
    [
        ExecutionUnavailableError(),
        ExecutionUncertainError("op-" + "7" * 32, code="TERMINALITY_UNKNOWN"),
    ],
)
def test_v2_acquisition_unavailable_records_workspace_backend_unavailable(
    site: Site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pin_exc: BaseException
) -> None:
    """pin_reader transport/uncertainty failure records workspace/backend-unavailable in v2."""
    with _managed_child_env(site, tmp_path) as (managed, publisher, child_ctx, yaml_path):

        def fail_pin(*_a: Any, **_k: Any) -> Any:
            raise pin_exc

        monkeypatch.setattr(managed.client, "pin_reader", fail_pin)
        code, state = run_workflow(
            roles=["planner", "coder"],
            task="pin unavailable",
            per_role_task={},
            mode="linear",
            max_repairs=0,
            max_replans=0,
            run_id=child_ctx.run_id,
            config=yaml_path,
            workspace=site.source,
            max_turns=2,
            output_mode="quiet",
            run_stage_fn=lambda *_a, **_k: 0,
            run_context=child_ctx,
            plan_publisher=publisher,
            managed_execution=managed,
            acquisition=AcquisitionSubstrateRequest(),
        )
        assert code == 2 and state is not None and state.status == "FAILED"
        record = _read_admission(child_ctx.run_log_dir, child_ctx.run_id)
        assert validate_admission_record(record, run_id=child_ctx.run_id) == record
        attempt = record["attempts"][0]
        assert attempt["dispatch_kind"] == "ACQUISITION"
        assert attempt["route"] == "BLOCKED"
        assert attempt["diagnostics"][0]["validator"] == "workspace"
        assert attempt["diagnostics"][0]["rule"] == "backend-unavailable"


def test_d11_eval_replan_budget_exhausted_emits_blocked_eval_replan_in_v2(site: Site, tmp_path: Path) -> None:
    """D11: EVAL_REPLAN with exhausted replan budget emits valid v2 EVAL_REPLAN/BLOCKED attempt."""
    _write_project_files(site.source, "demo-project", _VALID_INCREMENT)
    with _managed_child_env(site, tmp_path) as (managed, publisher, child_ctx, yaml_path):
        initial_rev = managed.current_revision_id
        selection = json.dumps({"kind": "SELECT_EXISTING", "project_slug": "demo-project", "increment_id": "I01"})

        def stage_fn(args: argparse.Namespace, **kwargs: Any) -> int:
            role = str(getattr(args, "role", ""))
            sink = kwargs.get("outcome_sink")
            if role == "planner" and isinstance(sink, list):
                sink.append(SessionOutcome(0, "stopped_by_llm", 1, selection))
            elif role == "eval" and isinstance(sink, list):
                sink.append(
                    SessionOutcome(
                        0,
                        "stopped_by_llm",
                        1,
                        "## Verification Summary\n\n### Step results\n- SLICE1: FAIL\n\n"
                        "### Verdict\nREPLAN_REQUIRED\n\n### Route decision\nreturn_to_planner\n",
                    )
                )
            return 0

        code, state = run_workflow(
            roles=["planner", "coder", "eval"],
            task="eval replan zero budget",
            per_role_task={},
            mode="adaptive",
            max_repairs=0,
            max_replans=0,
            run_id=child_ctx.run_id,
            config=yaml_path,
            workspace=site.source,
            max_turns=2,
            output_mode="quiet",
            run_stage_fn=stage_fn,
            run_context=child_ctx,
            plan_publisher=publisher,
            managed_execution=managed,
            acquisition=AcquisitionSubstrateRequest(),
        )
        assert code == 1 and state is not None
        record = _read_admission(child_ctx.run_log_dir, child_ctx.run_id)
        assert validate_admission_record(record, run_id=child_ctx.run_id) == record
        assert record["status"] == "BLOCKED"
        assert [(a["dispatch_kind"], a["route"]) for a in record["attempts"]] == [
            ("ACQUISITION", "ADMITTED"),
            ("EVAL_REPLAN", "BLOCKED"),
        ]
        blocked = record["attempts"][1]
        assert blocked["input_revision"] == blocked["output_revision"] == initial_rev
        assert blocked["operation_id"] is None
        assert blocked["candidate_sha256"] is None
        assert blocked["promoted_sha256"] is None
