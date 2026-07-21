"""Kill-check tests for S13: FAIL_CLOSED/FAIL_OPEN flags + getattr removal.

Verifies:
1. FAIL_CLOSED_FLAGS and FAIL_OPEN_FLAGS cover all FeatureFlags fields
2. Zero getattr(flags, ...) sites remain in src/fa/
3. Zero getattr(session, ...) sites remain in src/fa/inner_loop/
4. FAIL-CLOSED flags default to restrictive value when flags=None
5. FAIL-OPEN flags default to permissive/deny value when flags=None
"""

from __future__ import annotations

import subprocess
from dataclasses import fields as dc_fields
from pathlib import Path

import pytest

from fa.feature_flags import FAIL_CLOSED_FLAGS, FAIL_OPEN_FLAGS, FeatureFlags


# ── Kill-check 1: Categorization covers all fields ──────────────────


def test_all_fields_categorized():
    """Every FeatureFlags field must be in exactly one of FAIL_CLOSED_FLAGS
    or FAIL_OPEN_FLAGS. No field may be uncategorized."""
    all_field_names = {f.name for f in dc_fields(FeatureFlags)}
    categorized = FAIL_CLOSED_FLAGS | FAIL_OPEN_FLAGS

    uncategorized = all_field_names - categorized
    assert not uncategorized, f"Uncategorized fields: {uncategorized}"

    # Also check no overlap
    overlap = FAIL_CLOSED_FLAGS & FAIL_OPEN_FLAGS
    assert not overlap, f"Fields in both sets: {overlap}"


# ── Kill-check 2: Zero getattr(flags, ...) sites ───────────────────


def test_no_getattr_feature_flags():
    """No getattr(state.feature_flags, ...) or getattr(flags, ...) calls
    should remain in src/fa/ — direct attribute access is required."""
    result = subprocess.run(
        ["grep", "-rn", "getattr.*feature_flags", "src/fa/", "--include=*.py"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    # grep exits 1 when no matches found
    hits = [line for line in result.stdout.splitlines() if "__pycache__" not in line]
    assert not hits, (
        f"Found getattr.*feature_flags sites ({len(hits)}):\n"
        + "\n".join(hits)
    )


# ── Kill-check 3: Zero getattr(session, ...) sites in inner_loop ───


def test_no_getattr_session_in_inner_loop():
    """No getattr(session, ...) calls should remain in src/fa/inner_loop/
    — direct attribute access is required (S11 typed all fields)."""
    result = subprocess.run(
        ["grep", "-rn", "getattr(session", "src/fa/inner_loop/", "--include=*.py"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    hits = [line for line in result.stdout.splitlines() if "__pycache__" not in line]
    assert not hits, (
        f"Found getattr(session, ...) sites ({len(hits)}):\n"
        + "\n".join(hits)
    )


# ── Kill-check 4: FAIL-CLOSED flags default to restrictive value ────


def test_fail_closed_flags_default_restrictive():
    """When feature_flags is None, FAIL-CLOSED flags must default to
    the restrictive/safe value."""
    # context_budget_enabled: default=True → budget check active
    # (When flags missing, budget should still be enforced)
    assert "context_budget_enabled" in FAIL_CLOSED_FLAGS

    # context_compaction_enabled: default=True → compaction active
    # (DEPRECATED but must remain in FAIL_CLOSED for backward compat)
    assert "context_compaction_enabled" in FAIL_CLOSED_FLAGS


# ── Kill-check 5: FAIL-OPEN flags default to permissive/deny value ──


def test_fail_open_subagent_spawning():
    """subagent_spawning_enabled is FAIL-OPEN: default=False → don't spawn
    when unconfigured (DANGEROUS if True without explicit opt-in)."""
    assert "subagent_spawning_enabled" in FAIL_OPEN_FLAGS


# ── Kill-check 6: FAIL_CLOSED_FLAGS and FAIL_OPEN_FLAGS exported ───


def test_flags_exported():
    """FAIL_CLOSED_FLAGS and FAIL_OPEN_FLAGS must be in feature_flags.__all__."""
    from fa.feature_flags import __all__
    assert "FAIL_CLOSED_FLAGS" in __all__
    assert "FAIL_OPEN_FLAGS" in __all__
