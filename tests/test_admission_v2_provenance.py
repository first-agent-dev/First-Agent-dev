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
    ExecutionClient,
    ExecutionRejectedError,
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


def test_v2_bootstrap_admitted_emits_distinct_bundle_and_plan_hashes_with_install_receipt(
    site: Site, tmp_path: Path
) -> None:
    """BOOTSTRAP_NEW_PROJECT installs via real authority, reads back fresh revision, and validates v2 record."""
    with _managed_child_env(site, tmp_path) as (managed, publisher, child_ctx, yaml_path):
        initial_rev = managed.current_revision_id
        choice = json.dumps(
            {
                "kind": "BOOTSTRAP_NEW_PROJECT",
                "project_slug": "new-project",
                "increment_slug": "foundation",
                "roadmap_body": _VALID_ROADMAP,
                "increment_body": _VALID_INCREMENT,
            }
        )

        def stage_fn(args: argparse.Namespace, **kwargs: Any) -> int:
            role = str(getattr(args, "role", ""))
            sink = kwargs.get("outcome_sink")
            if role == "planner" and isinstance(sink, list):
                sink.append(SessionOutcome(0, "stopped_by_llm", 1, choice))
            elif role == "eval":
                return _eval_pass_stage(sink)
            return 0

        code, state = run_workflow(
            roles=["planner", "coder"],
            task="bootstrap new",
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
        assert code == 0 and state is not None and state.status == "DONE"
        record = _read_admission(child_ctx.run_log_dir, child_ctx.run_id)
        assert validate_admission_record(record, run_id=child_ctx.run_id) == record
        assert record["status"] == "ADMITTED"
        assert record["plan_ref"]["source_kind"] == "BOOTSTRAP"
        attempt = record["attempts"][0]
        assert attempt["dispatch_kind"] == "ACQUISITION"
        assert attempt["source_sha256"] is None
        assert attempt["candidate_sha256"] == attempt["promoted_sha256"] == record["plan_ref"]["sha256"]
        assert attempt["bundle_sha256"] is not None
        assert attempt["bundle_sha256"] != attempt["candidate_sha256"]
        assert attempt["input_revision"] == initial_rev
        assert attempt["output_revision"] == managed.current_revision_id != initial_rev
        assert _OP_ID_RE.fullmatch(attempt["operation_id"] or "") is not None


def test_v2_bootstrap_invalid_body_blocks_with_candidate_and_bundle_evidence_and_no_ref(
    site: Site, tmp_path: Path
) -> None:
    """Installed bootstrap increment missing TESTS is blocked under bootstrap/invalid-body with v2 evidence."""
    with _managed_child_env(site, tmp_path) as (managed, publisher, child_ctx, yaml_path):
        choice = json.dumps(
            {
                "kind": "BOOTSTRAP_NEW_PROJECT",
                "project_slug": "bad-project",
                "increment_slug": "foundation",
                "roadmap_body": _VALID_ROADMAP,
                "increment_body": _INVALID_INCREMENT,
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
            acquisition=AcquisitionSubstrateRequest(),
        )
        assert code == 2 and state is not None and state.status == "FAILED"
        record = _read_admission(child_ctx.run_log_dir, child_ctx.run_id)
        assert validate_admission_record(record, run_id=child_ctx.run_id) == record
        assert record["status"] == "BLOCKED" and record["plan_ref"] is None
        attempt = record["attempts"][0]
        assert attempt["diagnostics"][0]["validator"] == "bootstrap"
        assert attempt["diagnostics"][0]["rule"] == "invalid-body"
        assert attempt["candidate_sha256"] is not None and attempt["bundle_sha256"] is not None
        assert attempt["promoted_sha256"] is None and attempt["output_revision"] is None


@pytest.mark.parametrize(
    ("phase", "exc_factory", "expected_pair", "expect_hashes", "expect_op"),
    [
        (
            "prepare",
            lambda: ExecutionRejectedError("INPUT_POLICY", None),
            ("bootstrap", "invalid-grammar"),
            False,
            False,
        ),
        (
            "prepare",
            lambda: ExecutionRejectedError("COLLISION", None),
            ("bootstrap", "collision"),
            False,
            False,
        ),
        (
            "install",
            lambda: ExecutionRejectedError("COLLISION", None),
            ("bootstrap", "collision"),
            True,
            False,
        ),
        (
            "install",
            lambda: ExecutionRejectedError("STALE_REVISION", None),
            ("workspace", "stale-revision"),
            True,
            False,
        ),
        (
            "install",
            lambda: ExecutionUncertainError("op-" + "a" * 32, code="DURABILITY_UNKNOWN"),
            ("bootstrap", "durability-unknown"),
            True,
            True,
        ),
        (
            "install",
            lambda: ExecutionUnavailableError(),
            ("workspace", "backend-unavailable"),
            True,
            False,
        ),
    ],
)
def test_v2_bootstrap_authority_failures_emit_valid_v2_records(
    site: Site,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
    exc_factory: Any,
    expected_pair: tuple[str, str],
    expect_hashes: bool,
    expect_op: bool,
) -> None:
    """D10/D12: prepare/install refusals and uncertainties validate under v2 admission schema."""
    with _managed_child_env(site, tmp_path) as (managed, publisher, child_ctx, yaml_path):
        if phase == "prepare":

            def fail_prepare(*_a: Any, **_k: Any) -> Any:
                raise exc_factory()

            monkeypatch.setattr(ExecutionClient, "prepare_bundle", fail_prepare)
        else:

            def fail_install(*_a: Any, **_k: Any) -> Any:
                raise exc_factory()

            monkeypatch.setattr(ExecutionClient, "install_project", fail_install)

        choice = json.dumps(
            {
                "kind": "BOOTSTRAP_NEW_PROJECT",
                "project_slug": "demo-fail",
                "increment_slug": "foundation",
                "roadmap_body": _VALID_ROADMAP,
                "increment_body": _VALID_INCREMENT,
            }
        )

        def stage_fn(args: argparse.Namespace, **kwargs: Any) -> int:
            sink = kwargs.get("outcome_sink")
            if isinstance(sink, list):
                sink.append(SessionOutcome(0, "stopped_by_llm", 1, choice))
            return 0

        code, state = run_workflow(
            roles=["planner", "coder"],
            task="bootstrap error",
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
        assert (attempt["diagnostics"][0]["validator"], attempt["diagnostics"][0]["rule"]) == expected_pair
        if expect_hashes:
            assert attempt["candidate_sha256"] is not None and attempt["bundle_sha256"] is not None
        else:
            assert attempt["candidate_sha256"] is None and attempt["bundle_sha256"] is None
        assert (attempt["operation_id"] is not None) is expect_op


@pytest.mark.parametrize(
    ("final_text", "expected_pair", "expect_refusal_stderr"),
    [
        ("", ("selection", "choice-missing"), True),
        ("not json", ("selection", "choice-malformed"), True),
        (
            json.dumps(
                {
                    "kind": "BOOTSTRAP_NEW_PROJECT",
                    "project_slug": "demo-bad",
                    "increment_slug": "foundation",
                    "roadmap_body": [],
                    "increment_body": "x",
                }
            ),
            ("bootstrap", "invalid-body"),
            True,
        ),
        (
            json.dumps({"kind": "SELECT_EXISTING", "project_slug": "missing-proj", "increment_id": "I01"}),
            ("selection", "needs-clarification"),
            False,
        ),
        (
            json.dumps({"kind": "NEEDS_CLARIFICATION", "reason": "AMBIGUOUS_PROJECT"}),
            ("selection", "ambiguous-project"),
            False,
        ),
        (
            json.dumps({"kind": "NEEDS_CLARIFICATION", "reason": "UNKNOWN_INCREMENT"}),
            ("selection", "unknown-increment"),
            False,
        ),
        (
            json.dumps({"kind": "NEEDS_CLARIFICATION", "reason": "MISSING_CONTEXT"}),
            ("selection", "needs-clarification"),
            False,
        ),
    ],
)
def test_d12_acquisition_choice_errors_and_clarifications_persist_blocked_v2_record(
    site: Site,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    final_text: str,
    expected_pair: tuple[str, str],
    expect_refusal_stderr: bool,
) -> None:
    """D12: AcquisitionChoiceError and NEEDS_CLARIFICATION write BLOCKED v2 admission + FAILED FlowState."""
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
            acquisition=AcquisitionSubstrateRequest(),
        )
        assert code == 2 and state is not None and state.status == "FAILED"
        if expect_refusal_stderr:
            assert f"fa workflow: acquisition choice refused: {expected_pair[1]}" in capsys.readouterr().err
        record = _read_admission(child_ctx.run_log_dir, child_ctx.run_id)
        assert validate_admission_record(record, run_id=child_ctx.run_id) == record
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
            bootstrap_choice = json.dumps(
                {
                    "kind": "BOOTSTRAP_NEW_PROJECT",
                    "project_slug": "child-proj",
                    "increment_slug": "foundation",
                    "roadmap_body": _VALID_ROADMAP,
                    "increment_body": _VALID_INCREMENT,
                }
            )

            def stage_fn(args: argparse.Namespace, **kwargs: Any) -> int:
                child_ids.append(str(getattr(args, "run_id", "")))
                role = str(getattr(args, "role", ""))
                sink = kwargs.get("outcome_sink")
                if role == "planner" and isinstance(sink, list):
                    sink.append(SessionOutcome(0, "stopped_by_llm", 1, bootstrap_choice))
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
            result = tool.handler({"task": "bootstrap child", "roles": "planner,coder", "mode": "linear"})
            assert result.error is None, result.error
            assert isinstance(result.result, dict)
            child_run_id = result.result["run_id"]
            child_logs_dir = state_root / "session-log" / child_run_id
            record = _read_admission(child_logs_dir, child_run_id)
            assert validate_admission_record(record, run_id=child_run_id) == record
            assert record["schema_version"] == 2
            assert record["owner_run_id"] == parent_run
            assert record["plan_ref"]["source_kind"] == "BOOTSTRAP"
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
