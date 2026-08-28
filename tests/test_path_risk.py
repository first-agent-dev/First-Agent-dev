"""S10.2 — path-based risk tiers (CT3) + config knobs (CT7) + gate default (CT9).

root=tier-policy/config class=C0/C0p claim=G4/G5/G12 path=P1-P17
oracle=exact tier ints, loader warnings, config fields; deterministic.
"""

from __future__ import annotations

from fa.inner_loop.expansion import TIER_HIGH, TIER_MEDIUM, TIER_SAFE
from fa.inner_loop.path_risk import (
    TIER_NO_EVIDENCE,
    combine_tiers,
    default_scope_risk_config,
    load_scope_risk_tiers,
    observed_tiers,
    tier_for_path,
)
from fa.inner_loop.runtime_limits import (
    DEFAULT_CALIBRATION_EPSILON,
    DEFAULT_CHAT_ESCALATION_GATE,
    DEFAULT_MAX_WORKFLOW_INVOCATIONS,
    DEFAULT_MIN_FLAG_RUNS,
    RuntimeLimits,
    load_runtime_limits,
)

CFG = default_scope_risk_config()


# ── tier_for_path: defaults (P1/P2/P6) ─────────────────────────────────────


def test_src_path_is_high() -> None:
    assert tier_for_path("src/fa/cli.py", CFG) == TIER_HIGH
    assert tier_for_path("src/fa/inner_loop/expansion.py", CFG) == TIER_HIGH


def test_tests_and_knowledge_and_scripts_are_medium() -> None:
    # tests/** read and write both score medium — never high (Q26).
    assert tier_for_path("tests/test_expansion.py", CFG) == TIER_MEDIUM
    assert tier_for_path("tests/conftest.py", CFG) == TIER_MEDIUM
    assert tier_for_path("knowledge/skills/x/SKILL.md", CFG) == TIER_MEDIUM
    assert tier_for_path("scripts/fa", CFG) == TIER_MEDIUM
    # boundary: tests-* sibling dirs do not match the prefix
    assert tier_for_path("tests-legacy/old.py", CFG) == TIER_MEDIUM  # unknown, still medium by RK-J


def test_worklog_subtrees_are_safe() -> None:
    assert tier_for_path("worklogs/archive/2026/08/note.md", CFG) == TIER_SAFE
    assert tier_for_path("worklogs/research/paper.md", CFG) == TIER_SAFE
    assert tier_for_path("worklogs/implementation-plans/plan.md", CFG) == TIER_SAFE
    assert tier_for_path("worklogs/pr-notes/n.md", CFG) == TIER_SAFE
    assert tier_for_path("worklogs/reviews/r.md", CFG) == TIER_SAFE


def test_unknown_prefix_is_medium_rk_j() -> None:
    assert tier_for_path("vendor/lib/thing.py", CFG) == TIER_MEDIUM
    assert tier_for_path("README.md", CFG) == TIER_MEDIUM


def test_root_manifests_are_high() -> None:
    for name in ("pyproject.toml", "package.json", "Dockerfile", "Makefile", "justfile"):
        assert tier_for_path(name, CFG) == TIER_HIGH, name
    # nested manifests are NOT root manifests -> normal tiering
    assert tier_for_path("subdir/pyproject.toml", CFG) == TIER_MEDIUM


def test_github_ci_is_high() -> None:
    assert tier_for_path(".github/workflows/ci.yml", CFG) == TIER_HIGH


def test_prefix_respects_path_boundary() -> None:
    # src-legacy must not be classed as src
    assert tier_for_path("src-legacy/old.py", CFG) == TIER_MEDIUM
    assert tier_for_path("scripts-archive/x.sh", CFG) == TIER_MEDIUM


# ── combine_tiers: MAX dominance / commutativity (CT3 kill-check) ──────────


def test_combine_tiers_max_dominant() -> None:
    # lexical easy (1) + path high (5) must be 5, never averaged to 3.
    assert combine_tiers(TIER_SAFE, TIER_HIGH) == TIER_HIGH
    assert combine_tiers(TIER_HIGH, TIER_SAFE) == TIER_HIGH


def test_combine_tiers_commutative_and_idempotent() -> None:
    for a in (TIER_SAFE, TIER_MEDIUM, TIER_HIGH):
        for b in (TIER_SAFE, TIER_MEDIUM, TIER_HIGH):
            assert combine_tiers(a, b) == combine_tiers(b, a)
            assert combine_tiers(a, a) == a


# ── observed_tiers: positional read/write split ────────────────────────────


def test_observed_tiers_empty_sets() -> None:
    out = observed_tiers(frozenset(), frozenset(), CFG)
    assert out == {"read_max": TIER_NO_EVIDENCE, "write_max": TIER_NO_EVIDENCE}


def test_observed_tiers_read_high_write_safe() -> None:
    out = observed_tiers(
        frozenset({"src/fa/cli.py"}),
        frozenset({"worklogs/archive/note.md"}),
        CFG,
    )
    assert out["read_max"] == TIER_HIGH
    assert out["write_max"] == TIER_SAFE


def test_tests_write_is_medium_not_high_q26() -> None:
    # tests/** write = medium posture: must never score high.
    out = observed_tiers(frozenset(), frozenset({"tests/test_x.py"}), CFG)
    assert out["write_max"] == TIER_MEDIUM


def test_observed_tiers_max_over_set() -> None:
    out = observed_tiers(
        frozenset({"worklogs/research/a.md", "tests/t.py", "src/m/x.py"}),
        frozenset({"scripts/s.sh"}),
        CFG,
    )
    assert out["read_max"] == TIER_HIGH
    assert out["write_max"] == TIER_MEDIUM


# ── R3: edit-position suite (tests-only helper semantics, ≥5 cases) ────────
# Runtime truth = observed_tiers over the actual write set. Task-text claims
# of "I'll verify" never enter the write set (verify-only commands produce no
# diff), so position is derived from what was ACTUALLY modified.


def r3_write_tier(*written: str) -> int:
    return observed_tiers(frozenset(), frozenset(written), CFG)["write_max"]


def test_r3_edit_position_matrix() -> None:
    cases = [
        # (description, paths actually modified, expected tier)
        ("single src edit", ("src/fa/cli.py",), TIER_HIGH),
        ("multi-path src + test", ("src/fa/a.py", "tests/test_a.py"), TIER_HIGH),
        ("tests-only edit", ("tests/test_a.py", "tests/conftest.py"), TIER_MEDIUM),
        ("docs-only edit in safe tree", ("worklogs/reviews/r1.md",), TIER_SAFE),
        ("root manifest edit", ("pyproject.toml",), TIER_HIGH),
        ("multi-path all safe", ("worklogs/archive/a.md", "worklogs/research/b.md"), TIER_SAFE),
        ("src nested deep", ("src/fa/tools/workflow_tool.py",), TIER_HIGH),
    ]
    for desc, paths, expected in cases:
        assert r3_write_tier(*paths) == expected, desc


# ── loader (CT7) ───────────────────────────────────────────────────────────


def test_loader_absent_block_gives_defaults() -> None:
    result = load_scope_risk_tiers("other: 1\n")
    assert result.config == default_scope_risk_config()
    assert result.warnings == ()


def test_loader_empty_text_gives_defaults() -> None:
    result = load_scope_risk_tiers("")
    assert result.config == default_scope_risk_config()


def test_loader_additive_prefixes_inline_and_child_list() -> None:
    text = """
scope_risk_tiers:
  medium: [docs, notes]
  high:
    - infra
"""
    result = load_scope_risk_tiers(text)
    assert result.warnings == ()
    assert tier_for_path("docs/readme.md", result.config) == TIER_MEDIUM
    assert tier_for_path("infra/deploy.tf", result.config) == TIER_HIGH
    # defaults retained
    assert tier_for_path("src/x.py", result.config) == TIER_HIGH
    assert tier_for_path("worklogs/archive/x.md", result.config) == TIER_SAFE


def test_loader_unknown_tier_warns_but_keeps_defaults() -> None:
    text = """
scope_risk_tiers:
  ultra: [secret]
"""
    result = load_scope_risk_tiers(text)
    assert len(result.warnings) == 1
    assert "unknown tier" in result.warnings[0].detail
    assert result.config == default_scope_risk_config()


def test_loader_scalar_block_warns_and_falls_back() -> None:
    result = load_scope_risk_tiers("scope_risk_tiers: yes\n")
    assert len(result.warnings) == 1
    assert result.config == default_scope_risk_config()


def test_loader_comment_and_blank_lines_ignored() -> None:
    text = """
# a comment
scope_risk_tiers:
  # inner comment
  safe:
    - letters   # trailing comment
"""
    result = load_scope_risk_tiers(text)
    assert result.warnings == ()
    assert tier_for_path("letters/out.md", result.config) == TIER_SAFE


def test_loader_highest_tier_wins_on_overlap() -> None:
    # Config cannot DOWNGRADE the anchored high prefix; and explicit high
    # overlap with safe keeps high.
    text = """
scope_risk_tiers:
  safe:
    - src
"""
    result = load_scope_risk_tiers(text)
    assert tier_for_path("src/fa/x.py", result.config) == TIER_HIGH


# ── runtime_limits knobs (CT7/CT9) ─────────────────────────────────────────


def test_gate_default_is_off_q25() -> None:
    assert DEFAULT_CHAT_ESCALATION_GATE is False
    assert RuntimeLimits().chat_escalation_gate is False
    assert RuntimeLimits.anchored_defaults().chat_escalation_gate is False


def test_gate_can_be_toggled_back_on() -> None:
    result = load_runtime_limits("runtime_limits:\n  chat_escalation_gate: true\n")
    assert result.limits.chat_escalation_gate is True
    result_off = load_runtime_limits("runtime_limits:\n  chat_escalation_gate: false\n")
    assert result_off.limits.chat_escalation_gate is False


def test_k_knob_default_and_override() -> None:
    assert DEFAULT_MAX_WORKFLOW_INVOCATIONS == 2
    assert RuntimeLimits().max_workflow_invocations == 2
    result = load_runtime_limits("runtime_limits:\n  max_workflow_invocations: 3\n")
    assert result.limits.max_workflow_invocations == 3


def test_k_knob_rejects_non_positive() -> None:
    result = load_runtime_limits("runtime_limits:\n  max_workflow_invocations: 0\n")
    assert result.limits.max_workflow_invocations == DEFAULT_MAX_WORKFLOW_INVOCATIONS
    assert any("max_workflow_invocations" in w.key for w in result.warnings)


def test_calibration_knobs_defaults_and_override() -> None:
    assert DEFAULT_CALIBRATION_EPSILON == 0.05
    assert DEFAULT_MIN_FLAG_RUNS == 10
    result = load_runtime_limits("runtime_limits:\n  calibration_epsilon: 0.1\n  min_flag_runs: 20\n")
    assert result.limits.calibration_epsilon == 0.1
    assert result.limits.min_flag_runs == 20


def test_calibration_epsilon_range_enforced() -> None:
    bad = load_runtime_limits("runtime_limits:\n  calibration_epsilon: 1.5\n")
    assert bad.limits.calibration_epsilon == DEFAULT_CALIBRATION_EPSILON
    assert any("(0.0, 1.0]" in w.detail for w in bad.warnings)
    zero = load_runtime_limits("runtime_limits:\n  calibration_epsilon: 0\n")
    # 0 parses as float 0.0 -> outside (0,1] -> warn + default stands
    assert zero.limits.calibration_epsilon == DEFAULT_CALIBRATION_EPSILON


def test_calibration_epsilon_non_numeric_warns() -> None:
    bad = load_runtime_limits("runtime_limits:\n  calibration_epsilon: abc\n")
    assert bad.limits.calibration_epsilon == DEFAULT_CALIBRATION_EPSILON
    assert any("non-numeric" in w.detail for w in bad.warnings)


# ── S10.2 mutation kill-checks (negative proof; restored afterwards) ───────
# These are asserted via the fixed cases above; the mutation sweep in S10.8
# re-applies them by hand. Documented here as the producer kill-check targets:
#   * combine MAX -> mean/AND  => test_combine_tiers_max_dominant fails
#   * unknown tier -> high     => test_unknown_prefix_is_medium_rk_j fails
#   * tests write scored high  => test_tests_write_is_medium_not_high_q26 fails
#   * gate default flips true  => test_gate_default_is_off_q25 fails
#   * epsilon range check gone => test_calibration_epsilon_range_enforced fails
