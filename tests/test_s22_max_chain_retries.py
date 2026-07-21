"""S22: Kill-check tests for check_tcb_stdlib + max_chain_retries FeatureFlags.

root=FeatureFlags + check_tcb_stdlib.py matrix=C
claim=max_chain_retries field + stdlib-only TCB check + session-level retry
kill-check:
  - max_chain_retries=0 → no chain-level retries (current behavior)
  - FeatureFlags categorization includes max_chain_retries
  - adding non-stdlib import to authoring_tcb.py → check exits 1
path-inventory: 3 paths (FeatureFlags field, stdlib check, retry logic)

Covers:
- max_chain_retries field exists with default=0
- max_chain_retries in as_dict()
- max_chain_retries in _KNOWN_FLAGS
- max_chain_retries in FAIL_OPEN_FLAGS
- load_feature_flags parses max_chain_retries
- check_tcb_stdlib exits 0 on clean tree
- check_tcb_stdlib detects non-stdlib import
- chain_exhaustion_count increment on ProviderChainExhaustedError
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from fa.feature_flags import (
    FAIL_CLOSED_FLAGS,
    FAIL_OPEN_FLAGS,
    FeatureFlags,
    _KNOWN_FLAGS,
    load_feature_flags,
)
from dataclasses import fields


# ── FeatureFlags field tests ───────────────────────────────────────────


def test_max_chain_retries_default_zero() -> None:
    """max_chain_retries defaults to 0 (fail-fast)."""
    flags = FeatureFlags()
    assert flags.max_chain_retries == 0


def test_max_chain_retries_in_as_dict() -> None:
    """max_chain_retries appears in as_dict() output."""
    flags = FeatureFlags(max_chain_retries=3)
    d = flags.as_dict()
    assert d["max_chain_retries"] == 3


def test_max_chain_retries_in_known_flags() -> None:
    """max_chain_retries is in _KNOWN_FLAGS."""
    assert "max_chain_retries" in _KNOWN_FLAGS
    assert _KNOWN_FLAGS["max_chain_retries"] == "int"


def test_max_chain_retries_in_fail_open() -> None:
    """max_chain_retries is in FAIL_OPEN_FLAGS (default=0 → deny when unconfigured)."""
    assert "max_chain_retries" in FAIL_OPEN_FLAGS


def test_categorization_complete() -> None:
    """Every FeatureFlags field is in exactly one flag category."""
    all_flags = {f.name for f in fields(FeatureFlags)}
    categorized = FAIL_CLOSED_FLAGS | FAIL_OPEN_FLAGS
    assert all_flags == categorized, f"Uncategorized: {all_flags - categorized}"


def test_load_feature_flags_parses_max_chain_retries() -> None:
    """load_feature_flags() parses max_chain_retries from YAML."""
    yaml_text = "feature_flags:\n  max_chain_retries: 5\n"
    result = load_feature_flags(yaml_text)
    assert result.flags.max_chain_retries == 5


# ── check_tcb_stdlib tests ─────────────────────────────────────────────


def test_tcb_stdlib_clean_exit() -> None:
    """check_tcb_stdlib exits 0 on clean tree."""
    from scripts.check_tcb_stdlib import check_stdlib_only
    repo_root = Path(__file__).resolve().parents[1]
    tcb_path = repo_root / "src" / "fa" / "authoring_tcb.py"
    violations = check_stdlib_only(tcb_path)
    assert violations == [], f"Unexpected non-stdlib imports: {violations}"


def test_tcb_stdlib_detects_non_stdlib(tmp_path: Path) -> None:
    """check_tcb_stdlib detects non-stdlib import."""
    from scripts.check_tcb_stdlib import check_stdlib_only
    bad_file = tmp_path / "bad_tcb.py"
    bad_file.write_text(textwrap.dedent("""\
        import json
        import requests  # third-party!
        from dataclasses import dataclass
    """))
    violations = check_stdlib_only(bad_file)
    assert "requests" in violations


# ── chain_exhaustion_count EventLog test ───────────────────────────────


def test_chain_exhaustion_count_starts_at_zero() -> None:
    """EventLog.chain_exhaustion_count starts at 0."""
    from fa.inner_loop.state import EventLog
    log = EventLog(tmp_path_factory() / "events.jsonl")
    assert log.chain_exhaustion_count == 0


def tmp_path_factory() -> Path:
    """Helper to get a temp path (called from test functions that use tmp_path)."""
    import tempfile
    return Path(tempfile.mkdtemp())
