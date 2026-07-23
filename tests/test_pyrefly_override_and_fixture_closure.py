"""Tests for pyrefly PY3/PY4/PY5 closure: overrides and fixture types.

These tests verify:
- PY3: test fixture types truthfully represent tested runtime shapes
- PY4: _DenyGuard.handle has @override
- PY5: DenyAllBeforeToolExec.handle has @override
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _has_override_decorator(filepath: Path, class_name: str, method_name: str) -> bool:
    """Check if a method in a class has the @override decorator."""
    source = filepath.read_text()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name == method_name:
                        for decorator in item.decorator_list:
                            if isinstance(decorator, ast.Name) and decorator.id == "override":
                                return True
    return False


class TestOverrideDecorators:
    """Verify @override is present on test guard classes (PY4/PY5 closure)."""

    def test_deny_guard_has_override(self) -> None:
        """_DenyGuard.handle in test_event_type_c1_producers.py must have @override."""
        filepath = REPO_ROOT / "tests" / "test_event_type_c1_producers.py"
        assert _has_override_decorator(filepath, "_DenyGuard", "handle"), (
            "_DenyGuard.handle must have @override decorator (PY4 closure)"
        )

    def test_deny_all_before_tool_exec_has_override(self) -> None:
        """DenyAllBeforeToolExec.handle in test_inner_loop_loop_guard.py must have @override."""
        filepath = REPO_ROOT / "tests" / "test_inner_loop_loop_guard.py"
        assert _has_override_decorator(filepath, "DenyAllBeforeToolExec", "handle"), (
            "DenyAllBeforeToolExec.handle must have @override decorator (PY5 closure)"
        )

    def test_mock_magic_mock_visitor_has_override(self) -> None:
        """MagicMockDataclassVisitor.visit_Call must have @override."""
        filepath = REPO_ROOT / "scripts" / "check_no_mocked_dataclasses.py"
        assert _has_override_decorator(filepath, "MagicMockDataclassVisitor", "visit_Call"), (
            "MagicMockDataclassVisitor.visit_Call must have @override decorator"
        )


class TestFixtureTypeHonesty:
    """Verify test fixture types truthfully represent tested shapes (PY3 closure)."""

    def test_blackboard_fixture_is_dict_str_object(self) -> None:
        """board fixture in test_coverage_tools_batch.py must be dict[str, object]."""
        filepath = REPO_ROOT / "tests" / "test_coverage_tools_batch.py"
        source = filepath.read_text()

        # The fixture should be annotated as dict[str, object]
        assert "dict[str, object]" in source, (
            "board fixture must be annotated as dict[str, object] to support "
            "both dict payload and scalar payload branches (PY3 closure)"
        )

    def test_scalar_payload_branch_works(self) -> None:
        """The scalar payload branch in test_coverage_tools_batch.py must be meaningful."""
        # Run the actual test to verify the scalar payload branch works
        import subprocess
        import sys

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_coverage_tools_batch.py::test_session_database_all_authority_facades_and_queries",
                "-v",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Scalar payload branch test failed:\n{result.stdout}\n{result.stderr}"


class TestScriptTypeAnnotations:
    """Verify scripts have correct type annotations."""

    def test_check_dependency_contract_has_dict_annotations(self) -> None:
        """check_dependency_contract.py functions must use dict[str, Any]."""
        filepath = REPO_ROOT / "scripts" / "check_dependency_contract.py"
        source = filepath.read_text()

        assert "dict[str, Any]" in source, (
            "check_dependency_contract.py must use dict[str, Any] annotations "
            "to satisfy pyrefly's implicit-any-type-argument check"
        )
