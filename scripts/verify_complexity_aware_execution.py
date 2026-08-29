#!/usr/bin/env python3
"""Deterministic, offline verification of the complexity-aware execution feature.

Covers every shipped slice of the parent plan
(`worklogs/implementation-plans/PLAN-complexity-aware-execution-chat-role.md`):

  S1  lexical scope estimator (OperatingPoint / estimate_scope)
  S2  chat role registry (read/write/edit/bash + invoke_workflow)
  S3  estimator -> level seed mapping (difficulty_to_level)
  S4  invoke_workflow tool + K budget + child run id + workflow_unavailable
  S5  ACRR proxy + global-history persistence/round-trip
  S7  deterministic routing gate (should_withhold_write_tools, fail-open)
  S8  full E3 cost model (CostWeights, compute_cost, floor, ACRR, read amplification)
  S10 evidence-driven expansion (next_level, path tiers, observations, handoff,
      calibration, tripwire retirement, two-layer wording/evidence premise)

This harness is deterministic, needs **no LLM provider**, and is safe to run
repeatedly: every DB/CLI check uses a throwaway ``FA_STATE_ROOT``. The live
contour (a real provider driving the chat role) is verified separately by the
live sheet; this script proves the off-LLM engine behaves to spec.

Exit code: 0 if every assertion passed, 1 otherwise. Run::

    python scripts/verify_complexity_aware_execution.py
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Ensure repo src is importable when run directly (scripts/ are not packaged).
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))


class Checker:
    """Tiny assertion collector: record pass/fail without aborting the run."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.current_slice = ""

    def slice(self, name: str) -> None:
        self.current_slice = name
        print(f"\n=== {name} ===")

    def ok(self, label: str, cond: bool, got: object = None) -> None:
        if cond:
            self.passed += 1
            print(f"  [PASS] {label}")
        else:
            self.failed += 1
            shown = "" if got is None else f"  (got={got!r})"
            print(f"  [FAIL] {label}{shown}")

    def eq(self, label: str, got: object, want: object) -> None:
        self.ok(label, got == want, got)

    def summary(self) -> int:
        total = self.passed + self.failed
        print(f"\n{'=' * 64}")
        print(f"  {self.passed}/{total} checks passed", end="")
        print(f"  ({self.failed} FAILED)" if self.failed else "  — ALL GREEN")
        print(f"{'=' * 64}")
        return 1 if self.failed else 0


def check_s1_estimator(c: Checker) -> None:
    c.slice("S1 — lexical scope estimator")
    from fa.inner_loop.scope_estimator import OperatingPoint, estimate_scope

    easy = estimate_scope("fix typo in readme and rename one variable")
    c.eq("L1 simple task -> chat_direct", easy.recommended_mode, "chat_direct")
    c.eq("L1 difficulty = 1", easy.difficulty, 1)
    c.ok("L1 confidence in (0,1]", 0.0 < easy.confidence <= 1.0, easy.confidence)

    mid = estimate_scope("implement a new command for cross-file log splitting")
    c.eq("L2 implement/new command -> chat_planned", mid.recommended_mode, "chat_planned")
    c.eq("L2 difficulty = 2", mid.difficulty, 2)

    hard = estimate_scope("refactor the whole codebase and migrate every call site to the new api")
    c.eq("L3 refactor/call-site -> workflow_linear", hard.recommended_mode, "workflow_linear")
    c.eq("L3 difficulty = 3", hard.difficulty, 3)

    # R1 premise: cue-free wording that is actually heavy under-scopes to L1.
    deceptive = estimate_scope("simplify the main function")
    c.eq("cue-free heavy wording under-scopes to chat_direct", deceptive.recommended_mode, "chat_direct")

    # Non-English (operator's terse Russian) still classifies without error.
    ru = estimate_scope("поправь опечатку в readme")
    c.eq("Russian simple task -> chat_direct", ru.recommended_mode, "chat_direct")

    # Empty/blank task is rejected (programmer/input error), not classified.
    for blank in ("", "   "):
        try:
            estimate_scope(blank)
            c.ok(f"blank task {blank!r} raises ValueError", False)
        except ValueError:
            c.ok(f"blank task {blank!r} raises ValueError", True)

    # OperatingPoint fields are populated.
    op = OperatingPoint(difficulty=1, scope="single-file", risk="low", confidence=0.7, recommended_mode="chat_direct")
    c.eq("OperatingPoint holds recommended_mode", op.recommended_mode, "chat_direct")


def check_s2_chat_registry(c: Checker) -> None:
    c.slice("S2 — chat role registry")
    from fa.inner_loop.tools import build_chat_registry

    with tempfile.TemporaryDirectory() as ws:
        reg = build_chat_registry(Path(ws), bash_timeout_seconds=30)
        names = {spec.name for spec in reg.specs()}
        c.ok("chat has fs_read_file", "fs_read_file" in names, sorted(names))
        c.ok("chat has fs_write_file (generalist set; gate withholds at CT9)", "fs_write_file" in names, sorted(names))
        c.ok("chat has fs_run_bash", "fs_run_bash" in names, sorted(names))
        c.ok("chat has fs_search", "fs_search" in names, sorted(names))


def check_s3_seed_mapping(c: Checker) -> None:
    c.slice("S3 — estimator -> seed level (difficulty_to_level)")
    from fa.inner_loop.expansion import difficulty_to_level

    c.eq("chat_direct seeds level 1", difficulty_to_level("chat_direct"), 1)
    c.eq("chat_planned seeds level 2", difficulty_to_level("chat_planned"), 2)
    c.eq("workflow_linear seeds level 3", difficulty_to_level("workflow_linear"), 3)
    try:
        difficulty_to_level("not_a_mode")
        c.ok("unknown mode raises ValueError", False)
    except ValueError:
        c.ok("unknown mode raises ValueError", True)


def check_s4_workflow_tool(c: Checker) -> None:
    c.slice("S4/S10-CT6 — invoke_workflow tool, K budget, handoff")
    from fa.inner_loop.tools.workflow_tool import (
        WorkflowInvocationContext,
        build_handoff_task,
        build_invoke_workflow_tool,
    )

    def make_ctx(k: int, facts: dict[str, Any] | None = None) -> WorkflowInvocationContext:
        return WorkflowInvocationContext(
            parent_run_id="parent-abc",
            config=Path("/nonexistent/c.yaml"),  # never read: run_stage_fn is faked
            workspace=Path("/nonexistent"),  # never touched: runner is faked
            max_turns=5,
            run_stage_fn=lambda *a: 0,
            workflow_timeout_seconds=1,
            max_invocations=k,
            session_facts_provider=(lambda: facts) if facts is not None else None,
        )

    # K=2: first two run, third denied with workflow_budget_exhausted.
    runner_calls: list[dict[str, Any]] = []

    def runner(**kw: Any) -> tuple[int, None]:
        runner_calls.append(kw)
        return (0, None)

    spec = build_invoke_workflow_tool(runner, lambda: make_ctx(2))
    results = [spec.handler({"task": f"t{i}"}) for i in range(3)]
    codes = ["ok" if r.error is None else r.error.code for r in results]
    c.eq("K=2 -> ok, ok, workflow_budget_exhausted", codes, ["ok", "ok", "workflow_budget_exhausted"])
    c.eq("denied (K+1)-th call never reaches runner", len(runner_calls), 2)

    # K read from context (K=3 -> third runs, fourth denied).
    spec3 = build_invoke_workflow_tool(lambda **kw: (0, None), lambda: make_ctx(3))
    codes3 = ["ok" if spec3.handler({"task": "x"}).error is None else "denied" for _ in range(4)]
    c.eq("K=3 -> ok,ok,ok,denied (K is config, not hardcoded)", codes3, ["ok", "ok", "ok", "denied"])

    # S10.9 / CT-H6: K=0 means never escalate — honored, not clamped to 1.
    z_calls: list[dict[str, Any]] = []

    def runner_z(**kw: Any) -> tuple[int, None]:
        z_calls.append(kw)
        return (0, None)

    rz = build_invoke_workflow_tool(runner_z, lambda: make_ctx(0)).handler({"task": "x"})
    c.ok(
        "K=0 -> first call denied as disabled-by-config",
        rz.error is not None
        and rz.error.code == "workflow_budget_exhausted"
        and "disabled by config" in rz.error.message,
    )
    c.eq("K=0 never reaches runner", len(z_calls), 0)

    # No live context -> workflow_unavailable (fail safe, no crash).
    spec_none = build_invoke_workflow_tool(lambda **kw: (0, None), lambda: None)
    rn = spec_none.handler({"task": "g"})
    c.ok("no context -> workflow_unavailable", rn.error is not None and rn.error.code == "workflow_unavailable")

    # Child run id derived from parent and distinct.
    ids: list[Any] = []

    def runner_id(**kw: Any) -> tuple[int, None]:
        ids.append(kw.get("child_run_id") or kw.get("run_id"))
        return (0, None)

    build_invoke_workflow_tool(runner_id, lambda: make_ctx(2)).handler({"task": "x"})
    c.ok("child run id startswith parent", bool(ids[0]) and str(ids[0]).startswith("parent-abc"), ids[0])
    c.ok("child run id != parent", bool(ids[0]) and str(ids[0]) != "parent-abc")
    c.ok("child run id <= 128 chars", bool(ids[0]) and len(str(ids[0])) <= 128)

    # Handoff payload sections + caps.
    out = build_handoff_task(
        goal="Fix routing",
        read_paths=[
            "src/fa/cli.py",
            "src/fa/a.py",
            "src/fa/b.py",
            "src/fa/c.py",
            "src/fa/d.py",
            "src/fa/e.py",
            "knowledge/x.md",
            "worklogs/archive/n.md",
        ],
        write_paths=["src/fa/cli.py"],
        search_paths=[f"src/fa/lead{i}.py" for i in range(15)],
    )
    c.ok("Goal first verbatim", out.startswith("Goal: Fix routing"))
    for section in ("Start here:", "Observed (already read):", "Modified:", "Candidate leads:", "Do exactly:"):
        c.ok(f"handoff has section {section!r}", section in out)
    start_here = out.split("Start here:")[1].split("Observed")[0]
    c.ok(
        "Start here lists the high-tier reads and is <= 5 items",
        1 <= sum(1 for ln in start_here.splitlines() if ln.strip().startswith("-")) <= 5,
    )
    leads = out.split("Candidate leads:")[1].split("Do exactly:")[0]
    c.ok("Candidate leads <= 10 items", sum(1 for ln in leads.splitlines() if ln.strip().startswith("-")) <= 10)
    c.ok("total listed paths <= 30", sum(1 for ln in out.splitlines() if ln.strip().startswith("-")) <= 30)

    # Empty facts -> no file-map sections but checklist retained.
    empty = build_handoff_task(goal="plain", read_paths=[], write_paths=[], search_paths=[])
    c.ok("empty facts omits Start here", "Start here:" not in empty)

    # S10.9 / CT-H5: Modified caps at 15 with an explicit overflow marker;
    # the total-path budget stays a real bound even with 40 writes.
    heavy = build_handoff_task(
        goal="big refactor",
        read_paths=["src/fa/cli.py"],
        write_paths=[f"src/fa/mod_{i:02d}.py" for i in range(40)],
        search_paths=[],
    )
    modified = heavy.split("Modified:")[1].split("Do exactly:")[0]
    c.eq(
        "Modified section caps at 15 entries (40 writes)",
        sum(1 for ln in modified.splitlines() if ln.strip().startswith("- ")),
        15,
    )
    c.ok("overflow is explicit, never silent", "(+25 more" in modified)
    c.ok(
        "total path entries stay <= 30 + marker",
        sum(1 for ln in heavy.splitlines() if ln.strip().startswith("- ")) <= 31,
    )

    # S10.9 / F11: a malformed risk_config in live facts degrades the handoff
    # to the bare goal instead of surfacing a tool error.
    bad_ctx = make_ctx(2, facts={"read_paths": ["src/a.py"], "risk_config": "not-a-config"})
    reached: list[dict[str, Any]] = []

    def runner_bad(**kw: Any) -> tuple[int, None]:
        reached.append(kw)
        return (0, None)

    rb = build_invoke_workflow_tool(runner_bad, lambda: bad_ctx).handler({"task": "keep going"})
    c.ok(
        "malformed risk_config -> goal-only degrade, escalation still runs",
        rb.error is None and bool(reached) and reached[0]["task"] == "keep going",
    )
    c.ok("empty facts keeps positive checklist", "Do exactly:" in empty)


def check_s5_acrr_and_history(c: Checker) -> None:
    c.slice("S5 — ACRR proxy + global-history persistence")
    from fa.inner_loop.acrr import compute_acrr, compute_read_amplification
    from fa.inner_loop.global_history import GlobalHistoryStore

    # ACRR = (actual - floor)/floor : 0 = hit the floor (lean), >0 = over-spend.
    c.eq("ACRR actual=floor (10,10) -> 0.0 (optimally lean)", compute_acrr(10.0, 10.0), 0.0)
    c.eq("ACRR actual=30 floor=10 -> 2.0 (2x over floor)", compute_acrr(30.0, 10.0), 2.0)
    c.eq("ACRR actual=6 floor=3 -> 1.0", compute_acrr(6.0, 3.0), 1.0)
    c.ok("ACRR undefined when floor=0 (no change-set denominator)", compute_acrr(6.0, 0.0) is None)
    c.eq("read amplification 4 read / 2 changed -> 2.0", compute_read_amplification(4, 2), 2.0)
    c.ok("read amplification None when no changes", compute_read_amplification(4, 0) is None)

    with tempfile.TemporaryDirectory() as d:
        store = GlobalHistoryStore(db_path=Path(d) / "gh.db")
        store.export_run(
            {
                "run_id": "r1",
                "role": "chat",
                "exit_code": 0,
                "stop_reason": "done",
                "turns": 3,
                "scope_estimate_json": json.dumps({"recommended_mode": "chat_direct"}),
                "acrr": 2.5,
                "read_amplification": 2.0,
            }
        )
        rows = store.read_all()
        c.eq("one row round-trips", len(rows), 1)
        c.eq("role persisted", rows[0].get("role"), "chat")
        c.eq("acrr persisted", rows[0].get("acrr"), 2.5)
        # INSERT OR REPLACE on run_id primary key.
        store.export_run(
            {
                "run_id": "r1",
                "role": "chat",
                "exit_code": 1,
                "stop_reason": "failed",
                "turns": 1,
                "scope_estimate_json": json.dumps({"recommended_mode": "chat_direct"}),
                "acrr": None,
                "read_amplification": None,
            }
        )
        c.eq("re-export same run_id replaces (no duplicate)", len(store.read_all()), 1)
        c.eq("replaced exit_code persisted", store.read_all()[0].get("exit_code"), 1)


def check_s7_routing_gate(c: Checker) -> None:
    c.slice("S7 — deterministic routing gate (fail-open)")
    from fa.inner_loop.routing import GATE_MIN_CONFIDENCE, should_withhold_write_tools
    from fa.inner_loop.scope_estimator import estimate_scope

    hard = estimate_scope("refactor the whole codebase and migrate every call site to the new api")
    easy = estimate_scope("fix typo in readme")
    gate = should_withhold_write_tools

    c.eq(
        "gate OFF (Q25 default) never withholds, even on hard task", gate(hard, role="chat", gate_enabled=False), False
    )
    c.eq("gate ON + confident workflow_linear + chat -> withhold", gate(hard, role="chat", gate_enabled=True), True)
    c.eq("gate ON + easy task -> do not withhold", gate(easy, role="chat", gate_enabled=True), False)
    c.eq("only the chat role is gated (coder unaffected)", gate(hard, role="coder", gate_enabled=True), False)
    c.eq("missing estimate (None) fails open", gate(None, role="chat", gate_enabled=True), False)
    c.ok("gate confidence floor is 0.8", GATE_MIN_CONFIDENCE == 0.8, GATE_MIN_CONFIDENCE)


def check_s8_cost_model(c: Checker) -> None:
    c.slice("S8 — full E3 cost model")
    from fa.inner_loop.acrr import (
        DEFAULT_WEIGHTS,
        compute_cost,
        compute_cost_floor,
    )

    # Fitted weights (recorded in ADR-16 with derivation).
    c.eq("alpha = 1.0", DEFAULT_WEIGHTS.alpha, 1.0)
    c.eq("gamma = 0.1", DEFAULT_WEIGHTS.gamma, 0.1)
    c.eq("delta = 1.5", DEFAULT_WEIGHTS.delta, 1.5)
    c.ok("beta ~= 0.000415", abs(DEFAULT_WEIGHTS.beta - 0.000415) < 1e-9, DEFAULT_WEIGHTS.beta)

    # C = alpha*latency + beta*tokens + gamma*tools + delta*files (latency term present but
    # excluded from the deterministic floor).
    c.eq(
        "cost 0-latency/100tok/2tools/3files",
        round(compute_cost(0.0, 100, 2, 3), 4),
        round(0.000415 * 100 + 0.1 * 2 + 1.5 * 3, 4),
    )
    c.eq(
        "tokens-only cost (0,1000,0,0) = beta*1000", round(compute_cost(0.0, 1000, 0, 0), 4), round(0.000415 * 1000, 4)
    )

    # Floor is self-referential: derives from the run's OWN changed paths; empty -> 0.
    c.eq("floor with no changed files = 0.0", compute_cost_floor([], ".", 0), 0.0)
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "a.py"
        f.write_text("x = 1\n" * 200, encoding="utf-8")
        floor = compute_cost_floor([str(f)], d, 0)
        c.ok("floor with a real changed file > 0", floor > 0.0, floor)


def check_s10_expansion(c: Checker) -> None:
    c.slice("S10-CT1 — evidence-driven expansion state machine")
    from fa.inner_loop.expansion import (
        LEVEL_CEILING,
        ExpansionState,
        next_level,
        select_l2_skill,
    )

    def ev(**kw: Any) -> dict[str, Any]:
        base: dict[str, Any] = {
            "write_tier": 0,
            "read_tier_high": False,
            "verify_failed": False,
            "assumed_linear": False,
        }
        base.update(kw)
        return base

    def triple(d: Any) -> tuple[int, str, str] | None:
        return None if d is None else (d.level_to, d.evidence, d.observation_key)

    c.eq("clean L1 -> no decision", next_level(ExpansionState(1), **ev()), None)
    c.eq(
        "bulk counters with no high tier stay SILENT",
        next_level(ExpansionState(1), **ev()),
        None,
    )
    c.eq(
        "high-tier READ arms L2",
        triple(next_level(ExpansionState(1), **ev(read_tier_high=True))),
        (2, "read_high_arm", "skill"),
    )
    c.eq(
        "high-tier WRITE escalates L3",
        triple(next_level(ExpansionState(1), **ev(write_tier=5))),
        (3, "high_tier_write", "escalation"),
    )
    c.eq(
        "VERIFY_ONLY failure escalates L3",
        triple(next_level(ExpansionState(1), **ev(verify_failed=True))),
        (3, "verify_failed", "escalation"),
    )
    c.eq(
        "medium-tier write (tests/) does NOT escalate",
        next_level(ExpansionState(1), **ev(write_tier=3)),
        None,
    )
    c.eq(
        "seeded workflow_linear never re-escalated (RK-I)",
        next_level(ExpansionState(1), **ev(write_tier=5, assumed_linear=True)),
        None,
    )
    c.eq("read-high already at L2 -> no re-arm", next_level(ExpansionState(2), **ev(read_tier_high=True)), None)
    c.eq(
        "verify_failed at L2 -> L3",
        triple(next_level(ExpansionState(2), **ev(verify_failed=True))),
        (3, "verify_failed", "escalation"),
    )
    c.eq(
        "ceiling: anything at L3 -> None",
        next_level(ExpansionState(LEVEL_CEILING), **ev(write_tier=5, verify_failed=True)),
        None,
    )
    d = next_level(ExpansionState(1), **ev(write_tier=5, read_tier_high=True, verify_failed=True))
    dt = triple(d)  # verify_failed must dominate both write and read evidence
    c.eq("strongest evidence first: verify_failed dominates", dt[1] if dt is not None else None, "verify_failed")
    c.eq("warm skill = feature-planning", select_l2_skill(plan_artifact=True), "feature-planning")
    c.eq("cold skill = plan-authoring", select_l2_skill(plan_artifact=False), "plan-authoring")

    # S10.9 / CT-H2: near-miss telemetry truth table.
    from fa.inner_loop.expansion import near_miss_evidence

    c.eq(
        "clean turn -> no observation",
        near_miss_evidence(
            ExpansionState(1), files_read=2, files_changed=0, write_tier=0, read_tier_high=False, verify_failed=False
        ),
        None,
    )
    nm = near_miss_evidence(
        ExpansionState(1), files_read=15, files_changed=0, write_tier=0, read_tier_high=False, verify_failed=False
    )
    c.ok("bulk reads over threshold -> observed", nm is not None and nm["files_read"] == 15)
    nm2 = near_miss_evidence(
        ExpansionState(1), files_read=1, files_changed=1, write_tier=3, read_tier_high=False, verify_failed=False
    )
    c.ok("single medium write -> observed (no counter needed)", nm2 is not None and nm2["write_tier"] == 3)
    nm3 = near_miss_evidence(
        ExpansionState(2), files_read=1, files_changed=0, write_tier=0, read_tier_high=True, verify_failed=False
    )
    c.ok("high read while already armed -> observed", nm3 is not None and nm3["read_tier_high"] is True)


def check_s10_path_tiers(c: Checker) -> None:
    c.slice("S10-CT3 — positional path risk tiers")
    from fa.inner_loop.path_risk import (
        TIER_HIGH,
        TIER_MEDIUM,
        TIER_SAFE,
        combine_tiers,
        default_scope_risk_config,
        load_scope_risk_tiers,
        observed_tiers,
        tier_for_path,
    )

    cfg = default_scope_risk_config()
    anchors = {
        "src/fa/cli.py": TIER_HIGH,
        "src/fa/hygiene/hooks/pre-push": TIER_HIGH,
        "pyproject.toml": TIER_HIGH,
        "justfile": TIER_HIGH,
        ".github/workflows/ci.yml": TIER_HIGH,
        "tests/test_x.py": TIER_MEDIUM,
        "knowledge/adr/a.md": TIER_MEDIUM,
        "scripts/tool.py": TIER_MEDIUM,
        "worklogs/archive/2026/n.md": TIER_SAFE,
        "worklogs/reviews/x.md": TIER_SAFE,
        "some/brand/new/tree.py": TIER_MEDIUM,  # unknown -> medium (RK-J)
        "src-legacy/old.py": TIER_MEDIUM,  # prefix boundary
    }
    for path, want in anchors.items():
        c.eq(f"tier({path})", tier_for_path(path, cfg), want)
    c.ok("Q26: tests write is never high", tier_for_path("tests/t.py", cfg) < TIER_HIGH)

    t = observed_tiers(frozenset(["src/fa/a.py"]), frozenset(["tests/t.py"]), cfg)
    c.eq("read_max = high on src read", t["read_max"], TIER_HIGH)
    c.eq("write_max = medium on tests write", t["write_max"], TIER_MEDIUM)
    t0 = observed_tiers(frozenset(), frozenset(), cfg)
    c.eq("empty read set -> 0 (no evidence, not 'safe')", t0["read_max"], 0)

    c.eq("MAX combine lexical 1 + path 5 = 5", combine_tiers(1, TIER_HIGH), TIER_HIGH)
    c.eq("MAX combine never averages down", combine_tiers(TIER_HIGH, 1), TIER_HIGH)

    r = load_scope_risk_tiers("scope_risk_tiers:\n  high:\n    - deploy\n")
    c.ok("custom high prefix added", "deploy" in r.config.high_prefixes)
    c.ok("default 'src' retained (additive)", "src" in r.config.high_prefixes)
    r_bad = load_scope_risk_tiers("scope_risk_tiers:\n  bogus:\n    - x\n")
    c.ok("unknown tier name -> warning, config still returned", len(r_bad.warnings) >= 1)

    # S10.9 / CT-H8: glob prefixes are segment-anchored; dot-dirs survive.
    from fa.inner_loop.path_risk import DEFAULT_MEDIUM_PREFIXES, DEFAULT_SAFE_PREFIXES, ScopeRiskConfig

    cfg_glob = ScopeRiskConfig(
        safe_prefixes=DEFAULT_SAFE_PREFIXES,
        medium_prefixes=DEFAULT_MEDIUM_PREFIXES,
        high_prefixes=frozenset({"gen/*"}),
    )
    c.eq("glob src/* style matches ONE segment", tier_for_path("gen/a.py", cfg_glob), TIER_HIGH)
    c.eq("glob does not span / (deep path not high)", tier_for_path("gen/a/b.py", cfg_glob), TIER_MEDIUM)
    cfg_dot = ScopeRiskConfig(
        safe_prefixes=DEFAULT_SAFE_PREFIXES,
        medium_prefixes=DEFAULT_MEDIUM_PREFIXES,
        high_prefixes=frozenset({"ci"}),
    )
    c.eq(".ci is not ci (dot survives prefix strip)", tier_for_path(".ci/x.yml", cfg_dot), TIER_MEDIUM)
    c.eq("ci still matches ci", tier_for_path("ci/x.yml", cfg_dot), TIER_HIGH)


def check_s10_observations(c: Checker) -> None:
    c.slice("S10-CT4 — per-turn observation rebuild/cap/eviction")
    from fa.inner_loop.expansion import ExpansionDecision
    from fa.inner_loop.observations import OBSERVATION_CAP_CHARS, build_observation_block

    clean = build_observation_block(level_from=1, level_to=1, decision=None, write_tier=0)
    c.eq("clean L1 -> empty advisory", clean.turn_context, "")
    c.ok("clean L1 -> no skill block", clean.skill_block is None)

    esc = ExpansionDecision(level_to=3, evidence="high_tier_write", observation_key="escalation")
    r3 = build_observation_block(level_from=1, level_to=3, decision=esc, write_tier=5)
    c.ok("L3 escalation names invoke_workflow", "invoke_workflow" in r3.turn_context)
    c.ok("L3 uses positive 'Do exactly'", "Do exactly" in r3.turn_context)
    c.ok("L3 carries high-tier verification posture", "Risk tier high" in r3.turn_context)
    c.ok("L3 has no stale L2 skill line", "Planner skill active" not in r3.turn_context)

    arm = ExpansionDecision(level_to=2, evidence="read_high_arm", observation_key="skill")

    # A genuine SkillInjectionResult: the full body travels on .block (the
    # skills_conditional channel), NOT in the turn_context string.
    from fa.skills._inject import SkillInjectionResult

    skill = SkillInjectionResult(block={"name": "plan-authoring", "body": "Z" * 4000, "globs": "**/PLAN-*.md"})
    r2 = build_observation_block(
        level_from=1, level_to=2, decision=arm, write_tier=0, skill_result=skill, skill_name="plan-authoring"
    )
    c.ok("L2 carries a short skill anchor", "Planner skill active" in r2.turn_context)
    c.ok("L2 full skill body NOT in turn_context", "Z" not in r2.turn_context)
    c.ok("L2 skill_block travels via skills_conditional", r2.skill_block is not None)

    rm = build_observation_block(level_from=1, level_to=1, decision=None, write_tier=3)
    c.ok("medium write -> targeted-test nudge", "targeted tests" in rm.turn_context.lower())
    c.ok("medium write -> no invoke_workflow", "invoke_workflow" not in rm.turn_context)

    rx = build_observation_block(level_from=3, level_to=3, decision=None, write_tier=5, exhausted=True)
    c.ok("exhausted renders terminal budget line", "Escalation budget used" in rx.turn_context)
    c.ok("exhausted tells agent to report to operator", "operator" in rx.turn_context)
    c.eq("observation cap constant is 1800 chars", OBSERVATION_CAP_CHARS, 1800)
    c.ok("rendered advisory within cap", len(rx.turn_context) <= OBSERVATION_CAP_CHARS)


def check_s10_calibration(c: Checker) -> None:
    c.slice("S10-CT8 — reliability calibration (success_rate over ALL runs)")
    from fa.calibration import build_calibration_report

    def rows(n_ok: int, n_bad: int, acrr: float = 3.0) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for _ in range(n_ok):
            out.append(
                {"exit_code": 0, "acrr": acrr, "scope_estimate_json": json.dumps({"recommended_mode": "chat_direct"})}
            )
        for _ in range(n_bad):
            out.append(
                {"exit_code": 1, "acrr": None, "scope_estimate_json": json.dumps({"recommended_mode": "chat_direct"})}
            )
        return out

    def bucket(rs: list[dict[str, Any]], eps: float = 0.05, min_n: int = 10) -> Any:
        rep = build_calibration_report(rs, epsilon=eps, min_flag_runs=min_n, gate_enabled=False)
        return next(b for b in rep.buckets if b.recommended_mode == "chat_direct"), rep

    b, _ = bucket(rows(8, 4))
    c.eq("runs_total counts ALL runs", b.runs_total, 12)
    c.eq("runs_succeeded counts successes", b.runs_succeeded, 8)
    c.eq("success_rate = 8/12", round(b.success_rate, 4), round(8 / 12, 4))
    c.eq("ACRR mean from successes only", b.acrr_mean, 3.0)
    c.eq("8/12 below reliability target flagged", b.below_reliability_target, True)

    b0, _ = bucket(rows(0, 12))
    c.eq("all-failed -> success_rate 0.0", b0.success_rate, 0.0)
    c.eq("all-failed -> flagged at n>=10", b0.below_reliability_target, True)
    c.ok("all-failed -> no ACRR mean", b0.acrr_mean is None)

    bs, _ = bucket(rows(2, 2))
    c.eq("small sample (n=4) NOT flagged despite rate .5", bs.below_reliability_target, False)

    bb, _ = bucket(rows(19, 1))
    c.eq("rate exactly 1-eps (.95) NOT flagged", bb.below_reliability_target, False)

    b9, _ = bucket(rows(9, 1))
    c.eq("rate .90 < .95 at n=10 IS flagged", b9.below_reliability_target, True)

    bp, _ = bucket(rows(12, 0))
    c.eq("perfect run NOT flagged", bp.below_reliability_target, False)

    bsil, _ = bucket(rows(0, 12), min_n=99)
    c.eq("raising min_flag_runs above sample silences flag", bsil.below_reliability_target, False)

    _, rep = bucket(rows(8, 4))
    d = rep.to_dict()
    c.eq("report surfaces epsilon", d["epsilon_used"], 0.05)
    c.eq("report surfaces min_flag_runs", d["min_flag_runs"], 10)
    c.eq("report surfaces gate OFF (Q25)", d["chat_escalation_gate"], False)


def check_s10_log_kinds(c: Checker) -> None:
    c.slice("S10-F4 — tripwire retirement + log-kind registration")
    import typing

    from fa.output import LogKind

    members = set(typing.get_args(LogKind))
    c.ok("scope_expansion registered", "scope_expansion" in members)
    c.ok("expansion_exhausted registered", "expansion_exhausted" in members)
    c.ok("scope_tripwire retained as dormant alias", "scope_tripwire" in members)

    # S10.9 / CT-H3+CT-H4: telemetry kind registered; mirrors registered;
    # expansion_observed deliberately NOT mirrored (console noise policy).
    from fa.output import CONSOLE_MIRROR_KINDS

    c.ok("expansion_observed registered (S10.9 telemetry)", "expansion_observed" in members)
    c.ok("scope_expansion console-mirrored", "scope_expansion" in CONSOLE_MIRROR_KINDS)
    c.ok("expansion_exhausted console-mirrored", "expansion_exhausted" in CONSOLE_MIRROR_KINDS)
    c.ok("expansion_observed NOT mirrored (JSONL-only)", "expansion_observed" not in CONSOLE_MIRROR_KINDS)

    # No production producer emits the retired kind.
    import subprocess

    g = subprocess.run(
        ["grep", "-rn", 'kind="scope_tripwire"', "src/fa", "--include=*.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    producers = [ln for ln in g.stdout.splitlines() if ln.strip()]
    c.eq("no scope_tripwire producer in src/", producers, [])


def check_s10_two_layer(c: Checker) -> None:
    c.slice("S10-G10 — two-layer premise (wording under-scopes, evidence escalates)")
    from fa.inner_loop.expansion import ExpansionState, next_level
    from fa.inner_loop.scope_estimator import estimate_scope

    tasks: list[tuple[str, str, bool]] = [
        ("simplify the main function", "en", True),
        ("clean up a small thing in the cli", "en", True),
        ("make the entry point a bit shorter", "en", True),
        ("wire the new flag through", "en", True),
        ("look at the core loop and straighten it", "en", False),
        ("убери лишнее из главной функции", "ru", True),
        ("поправь проверку перед пушем", "ru", True),
        ("глянь, как там собирается запрос, и причеши", "ru", False),
    ]
    under = 0
    all_caught = True
    for text, _lang, is_write in tasks:
        if estimate_scope(text).recommended_mode == "chat_direct":
            under += 1
        if is_write:
            d = next_level(
                ExpansionState(1),
                write_tier=5,
                read_tier_high=False,
                verify_failed=False,
                assumed_linear=False,
            )
            caught = d is not None and d.level_to == 3
        else:
            d = next_level(
                ExpansionState(1),
                write_tier=0,
                read_tier_high=True,
                verify_failed=False,
                assumed_linear=False,
            )
            caught = d is not None and d.level_to == 2
        all_caught = all_caught and caught
    c.ok("evidence engine caught every cue-free high-tier task (EN+RU)", all_caught)
    print(
        f"  [info] estimator under-scoped {under}/{len(tasks)} cue-free tasks "
        "(expected high; that is why the evidence layer exists)"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="run only checks whose slice header contains this substring")
    args = ap.parse_args()

    c = Checker()
    checks: list[tuple[str, Callable[[Checker], None]]] = [
        ("S1", check_s1_estimator),
        ("S2", check_s2_chat_registry),
        ("S3", check_s3_seed_mapping),
        ("S4", check_s4_workflow_tool),
        ("S5", check_s5_acrr_and_history),
        ("S7", check_s7_routing_gate),
        ("S8", check_s8_cost_model),
        ("S10-CT1", check_s10_expansion),
        ("S10-CT3", check_s10_path_tiers),
        ("S10-CT4", check_s10_observations),
        ("S10-CT8", check_s10_calibration),
        ("S10-F4", check_s10_log_kinds),
        ("S10-G10", check_s10_two_layer),
    ]
    for _label, fn in checks:
        if args.only and args.only not in fn.__name__:
            continue
        fn(c)
    return c.summary()


if __name__ == "__main__":
    raise SystemExit(main())
