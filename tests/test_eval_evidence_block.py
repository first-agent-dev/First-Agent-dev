"""R16: workflow eval receives bounded managed sealed-revision metadata.

The production-caller oracle lives in ``test_execution_composition.py`` and
runs ``cli._cmd_workflow`` through the local supervisor. These focused tests
pin the controller's formatting and, importantly, distinguish unavailable
metadata from a proven empty delta. The current LLM-eval/mechanical-verify
split remains unchanged.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

from fa.inner_loop import workflow_controller
from fa.inner_loop.workflow_controller import (
    EVAL_DIFF_MAX_CHARS,
    WorkflowContext,
    _eval_evidence_block,
    workflow_artifact_paths,
)


class _ManagedExecution:
    current_revision_id = "rev-" + "2" * 32

    def __init__(self, result: dict[str, Any] | Exception) -> None:
        self.result = result
        self.calls: list[tuple[str, str, float | None]] = []

    def revision_changes(self, base: str, target: str, *, deadline: float | None = None) -> dict[str, Any]:
        self.calls.append((base, target, deadline))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _ctx(workspace: Path, managed: _ManagedExecution) -> WorkflowContext:
    ctx = WorkflowContext(
        run_id="r16",
        base_task="judge the work",
        per_role_task={},
        artifact_paths=workflow_artifact_paths("r16"),
        config=workspace / "models.yaml",
        workspace=workspace,
        max_turns=1,
        output_mode="quiet",
        managed_execution=managed,  # type: ignore[arg-type]
        deadline_mono=123.0,
    )
    ctx.managed_revision_pair.base_revision_id = "rev-" + "1" * 32
    ctx.managed_revision_pair.target_revision_id = managed.current_revision_id
    return ctx


def test_evidence_uses_managed_revision_paths_without_file_bodies(tmp_path: Path) -> None:
    managed = _ManagedExecution(
        {
            "changes": [
                {"path": "src/new_module.py", "change": "added"},
                {"path": "src/existing.py", "change": "modified"},
                {"path": "obsolete.py", "change": "deleted"},
            ],
            "total_changes": 3,
            "truncated": False,
        }
    )

    block = _eval_evidence_block(_ctx(tmp_path, managed))

    assert "added: src/new_module.py" in block
    assert "modified: src/existing.py" in block
    assert "deleted: obsolete.py" in block
    assert "read relevant current files with fs_read_file" in block
    assert "MUTATED_CONTENT" not in block
    assert managed.calls == [("rev-" + "1" * 32, "rev-" + "2" * 32, 123.0)]


def test_empty_delta_is_reported_only_after_a_successful_managed_comparison(tmp_path: Path) -> None:
    managed = _ManagedExecution({"changes": [], "total_changes": 0, "truncated": False})

    block = _eval_evidence_block(_ctx(tmp_path, managed))

    assert "Changed files: NONE between the sealed managed revisions" in block
    assert "unavailable" not in block


def test_unavailable_comparison_is_never_reported_as_empty(tmp_path: Path) -> None:
    managed = _ManagedExecution(RuntimeError("read-only comparison unavailable"))

    block = _eval_evidence_block(_ctx(tmp_path, managed))

    assert "Changed files: unavailable" in block
    assert "Changed files: NONE" not in block


def test_absent_managed_revision_pair_is_unavailable_not_empty(tmp_path: Path) -> None:
    managed = _ManagedExecution({"changes": [], "total_changes": 0, "truncated": False})
    ctx = _ctx(tmp_path, managed)
    ctx.managed_revision_pair.base_revision_id = None

    block = _eval_evidence_block(ctx)

    assert "managed sealed-revision evidence was not captured" in block
    assert "Changed files: NONE" not in block
    assert not managed.calls


def test_truncated_revision_metadata_and_display_are_explicit(tmp_path: Path) -> None:
    changes = [{"path": f"src/{index:04d}-" + "x" * 500, "change": "modified"} for index in range(128)]
    managed = _ManagedExecution({"changes": changes, "total_changes": 300, "truncated": True})

    block = _eval_evidence_block(_ctx(tmp_path, managed))

    assert "300 total; metadata_truncated=True" in block
    assert "metadata display truncated" in block
    assert "fs_read_file" in block
    assert len(block) < EVAL_DIFF_MAX_CHARS * 2


def test_controller_has_no_git_command_runner_left() -> None:
    """Static caller-edge guard: evidence gathering cannot inspect project Git."""
    tree = ast.parse(inspect.getsource(workflow_controller))
    assert not any(
        isinstance(node, ast.Import) and any(alias.name == "subprocess" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert not any(isinstance(node, ast.ImportFrom) and node.module == "subprocess" for node in ast.walk(tree))
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"run", "check_output", "Popen"}
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
        for node in ast.walk(tree)
    )
    assert not hasattr(workflow_controller, "_git_output")
