"""Kill-check tests for S14: Remove compaction_enabled flag gate (F-10 / G6).

Verifies:
1. compaction_enabled is derived from compaction_threshold is not None (SSoT)
2. context_compaction_enabled is NOT read by any production code outside feature_flags.py
3. context_compaction_enabled is marked DEPRECATED in FeatureFlags
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


CODER_LOOP_PATH = Path("src/fa/inner_loop/coder_loop.py")


# ── Kill-check 1: compaction_enabled uses SSoT ──────────────────────


def test_compaction_enabled_uses_threshold_ssoT():
    """In coder_loop.py, compaction_enabled must be derived from
    compaction_threshold is not None — not from the feature flag."""
    content = CODER_LOOP_PATH.read_text(encoding="utf-8")
    assert "compaction_enabled = compaction_threshold is not None" in content, (
        "Expected compaction_enabled = compaction_threshold is not None in coder_loop.py"
    )


# ── Kill-check 2: No production code reads context_compaction_enabled ─


def test_no_production_code_reads_compaction_flag():
    """No production code outside feature_flags.py should read
    context_compaction_enabled — it's deprecated."""
    result = subprocess.run(
        ["grep", "-rn", "context_compaction_enabled", "src/fa/", "--include=*.py"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    hits = [line for line in result.stdout.splitlines()
            if "__pycache__" not in line
            and "feature_flags.py" not in line
            and "deprecated" not in line.lower()
            and "DEPRECATED" not in line]
    # Allow: feature_flags.py (definition, as_dict, _KNOWN_FLAGS, FAIL_CLOSED, loader)
    # Allow: coder_loop.py comment mentioning "deprecated"
    non_flag_hits = []
    for line in hits:
        if "feature_flags.py" not in line:
            non_flag_hits.append(line)
    assert not non_flag_hits, (
        f"Production code reads context_compaction_enabled outside feature_flags.py:\n"
        + "\n".join(non_flag_hits)
    )


# ── Kill-check 3: context_compaction_enabled marked deprecated ───────


def test_compaction_flag_marked_deprecated():
    """The context_compaction_enabled field in FeatureFlags must be marked
    as DEPRECATED."""
    content = Path("src/fa/feature_flags.py").read_text(encoding="utf-8")
    assert "DEPRECATED" in content and "context_compaction_enabled" in content, (
        "context_compaction_enabled must be marked DEPRECATED in feature_flags.py"
    )
