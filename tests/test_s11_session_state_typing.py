"""Kill-check tests for S11: Type 9 Any|None fields on SessionState.

Verifies:
1. Only pty_pool remains Any | None
2. bash_executor is a declared field (BashExecutor | None)
3. Other 8 fields have real type annotations (not Any)
4. TYPE_CHECKING imports are present
5. SessionState construction still works
"""

from __future__ import annotations

import dataclasses
import inspect
from pathlib import Path
from typing import get_type_hints

import pytest

from fa.inner_loop.state import SessionState


STATE_PATH = Path("src/fa/inner_loop/state.py")


# ── Kill-check 1: Only pty_pool has Any | None ──────────────────────


def test_only_pty_pool_has_any_none():
    """In the SessionState class, only pty_pool should have Any | None.
    All other fields must be typed with their real types."""
    content = STATE_PATH.read_text(encoding="utf-8")

    # Find the SessionState class fields section
    in_class = False
    any_none_fields = []
    for line in content.splitlines():
        if "class SessionState" in line:
            in_class = True
            continue
        if in_class and line.startswith("    ") and ": " in line and " | None" in line:
            if "Any | None" in line:
                field_name = line.strip().split(":")[0]
                any_none_fields.append(field_name)
        if in_class and not line.startswith("    ") and line.strip() and "class" not in line:
            break

    assert any_none_fields == ["pty_pool"], (
        f"Expected only pty_pool with Any | None, got: {any_none_fields}"
    )


# ── Kill-check 2: bash_executor is a declared field ─────────────────


def test_bash_executor_field_exists():
    """bash_executor must be a declared field on SessionState as
    BashExecutor | None = None (user Q1: standardize approach, no getattr)."""
    field_names = {f.name for f in dataclasses.fields(SessionState)}
    assert "bash_executor" in field_names, (
        f"bash_executor not in SessionState fields: {sorted(field_names)}"
    )


# ── Kill-check 3: TYPE_CHECKING imports include BashExecutor ─────────


def test_type_checking_imports_bash_executor():
    """state.py must import BashExecutor under TYPE_CHECKING."""
    content = STATE_PATH.read_text(encoding="utf-8")
    assert "from fa.runtime.bash_executor import BashExecutor" in content, (
        "BashExecutor not imported in TYPE_CHECKING block"
    )


# ── Kill-check 4: Typed fields present in source ───────────────────


def test_typed_fields_in_source():
    """The source code must have real type annotations for the 8 typed fields."""
    content = STATE_PATH.read_text(encoding="utf-8")
    expected_types = {
        "transaction: Transaction",
        "blackboard: Blackboard",
        "telemetry: TelemetryLogger",
        "feature_flags: FeatureFlags",
        "artifact_store: ArtifactStore",
        "bash_executor: BashExecutor",
        "worktree_manager: WorktreeManager",
        "session_db: SessionDatabase",
        "output_bus: EventBus",
    }
    for expected in expected_types:
        assert expected in content, (
            f"Expected type annotation '{expected}' not found in state.py"
        )


# ── Kill-check 5: SessionState construction works ───────────────────


def test_session_state_construction(tmp_path: Path):
    """SessionState must still construct normally with the typed fields."""
    state = SessionState(workspace_root=tmp_path, run_id="test-s11")
    assert state.transaction is not None
    assert state.feature_flags is not None
    assert state.bash_executor is None  # Not auto-initialized
    assert state.pty_pool is not None  # Auto-initialized by __post_init__


# ── Kill-check 6: No circular import at runtime ─────────────────────


def test_no_runtime_import_of_typed_modules():
    """The TYPE_CHECKING imports should NOT cause runtime imports.
    Verify by checking that importing state.py doesn't trigger imports
    of the heavy modules (Blackboard, TelemetryLogger, etc.)."""
    import sys

    # Track which modules were loaded before
    before = set(sys.modules.keys())

    # Re-import state
    import importlib
    import fa.inner_loop.state
    importlib.reload(fa.inner_loop.state)

    after = set(sys.modules.keys())
    new_modules = after - before

    # These should NOT have been imported at runtime
    forbidden = {
        "fa.blackboard.blackboard",
        "fa.telemetry.telemetry",
        "fa.workspace.worktree_manager",
        "fa.runtime.bash_executor",
    }
    actually_imported = forbidden & new_modules
    assert not actually_imported, (
        f"TYPE_CHECKING guard failed — runtime import of: {actually_imported}"
    )
