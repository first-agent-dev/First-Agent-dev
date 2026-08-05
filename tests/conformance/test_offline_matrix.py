"""S13.5 — offline conformance matrix (CONF-1..7) run against the REAL composer.

Plan: ``worklogs/implementation-plans/PLAN-cli-trace-S13-multi-provider-conformance.md``
§S13.5 DoD: "all 7 run offline in CI". This is the CI ratchet — it exercises the
REAL composition root (``build_prompt_parts_v2``) and the REAL production
validator, and asserts the capability matrix is well-formed with positive
controls (D5a rule 1: every row carries ``ran`` so a green cell cannot come from
"never ran").

**Tests labelled per tests-writing skill:**
- **C1** — the matrix runs all 7 cases offline; each row carries a positive
  control (``ran=True``); CONF-1..4 (the emitter's own conformance) are ok.
- **C0p** — CONF-5/6 record the *capability* (not a pass/fail requirement): they
  are ok only when their provider capability allows the shape; CONF-7 records
  sizes and is never a pass/fail.
"""

from __future__ import annotations

from tests.conformance.harness import matrix_to_text, run_conformance_matrix


def test_matrix_runs_all_7_cases_offline() -> None:
    """C1 — all 7 CONF cases run offline; positive controls are present."""
    rows = run_conformance_matrix()
    assert len(rows) == 7
    assert [r["case"] for r in rows] == [1, 2, 3, 4, 5, 6, 7]
    # D5a rule 1: every row must carry a positive control (it actually ran).
    assert all(r["ran"] is True for r in rows), [r["name"] for r in rows if not r["ran"]]


def test_conf1_4_emitter_is_conformant() -> None:
    """C1 — the emitter's own conformance (CONF-1..4) is valid for a strict provider."""
    rows = run_conformance_matrix()
    for row in rows[:4]:
        assert row["ok"] is True, f"{row['name']}: {row['violations']}"
        assert row["violations"] == []


def test_conf5_6_record_capability_not_requirement() -> None:
    """C0p — CONF-5/6 are capability records, not blanket pass/fail.

    CONF-5 tolerates a trailing assistant (allow_trailing=True) so it is ok.
    CONF-6 (user-after-tool) records the violation when the strict default
    applies, documenting the capability rather than failing the suite.
    """
    rows = run_conformance_matrix()
    conf5 = rows[4]
    assert conf5["name"].startswith("CONF-5")
    # allow_trailing=True => the strict validator does not flag the trailing
    # assistant, so ok is True (capability recorded as tolerated).
    assert conf5["ok"] is True

    conf6 = rows[5]
    assert conf6["name"].startswith("CONF-6")
    # The strict default rejects user-after-tool; this is RECORDED (not asserted
    # as a failure of the suite). The row still ran (positive control).
    assert conf6["ran"] is True


def test_conf7_records_sizes_never_pass_fail() -> None:
    """C0p — CONF-7 records composition sizes and is never a pass/fail."""
    rows = run_conformance_matrix()
    conf7 = rows[6]
    assert conf7["name"].startswith("CONF-7")
    assert conf7["ok"] is True  # "recorded"
    sizes = conf7["sizes"]
    assert sizes["cacheable_bytes"] > 0
    assert sizes["non_cacheable_bytes"] > 0
    assert sizes["n_messages"] >= 1


def test_matrix_render_has_no_truncation() -> None:
    """C0p — the text render includes every row (D5a rule 3: no truncation)."""
    rows = run_conformance_matrix()
    text = matrix_to_text(rows)
    for name in ("CONF-1", "CONF-2", "CONF-3", "CONF-4", "CONF-5", "CONF-6", "CONF-7"):
        assert name in text
