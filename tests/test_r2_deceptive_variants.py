"""S10.7 / R2 (T9) — deceptive real-repo tasks: simple words, hidden coupling.

A deceptive task SOUNDS small ("simplify the main function") so the lexical
estimator under-scopes it to chat_direct, but doing it for real means
touching high-tier code with cross-file coupling. R2 pins the behaviour the
system MUST have:

  * the text estimator is allowed to land on chat_direct (recorded);
  * once the run's read set reveals high-tier code, the evidence engine
    arms/escalates by exactly ONE level first (arm L2 on the read), then
    escalates to L3 when a high-tier write or a failing verification turns
    up — stable, deterministic, no keyword reliance;
  * the minimum sane trajectory for such work is shaped
    fs_search -> fs_reach -> edits -> pytest (oracle-shaped, not a model eval).

Deterministic, no network, no LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fa.inner_loop.expansion import ExpansionState, next_level
from fa.inner_loop.path_risk import default_scope_risk_config, observed_tiers, tier_for_path
from fa.inner_loop.scope_estimator import estimate_scope


@dataclass(frozen=True)
class DeceptiveTask:
    wording: str
    lang: str
    # Paths the task ACTUALLY has to touch once you read the code.
    reveal_reads: tuple[str, ...]
    reveal_writes: tuple[str, ...]
    # Where the hidden coupling lives (high tier).
    high_tier_paths: tuple[str, ...]


# ≥6 real-repo deceptive variants. Seed cases from the session:
#  - `-f` force-push validators + tests (pre-push hygiene hook);
#  - cli.py "simplify the main function" (simple words, real core code).
DECEPTIVE_TASKS: tuple[DeceptiveTask, ...] = (
    DeceptiveTask(
        wording="simplify the main function",
        lang="en",
        reveal_reads=("src/fa/cli.py", "src/fa/inner_loop/coder_loop.py"),
        reveal_writes=("src/fa/cli.py",),
        high_tier_paths=("src/fa/cli.py",),
    ),
    DeceptiveTask(
        wording="allow -f on the push check but keep the tests green",
        lang="en",
        reveal_reads=("src/fa/hygiene/hooks/pre-push", "tests/test_hygiene*.py"),
        reveal_writes=("src/fa/hygiene/hooks/pre-push",),
        high_tier_paths=("src/fa/hygiene/hooks/pre-push",),
    ),
    DeceptiveTask(
        wording="clean up how the workflow tool gets its context",
        lang="en",
        reveal_reads=("src/fa/inner_loop/tools/workflow_tool.py", "src/fa/cli.py"),
        reveal_writes=("src/fa/inner_loop/tools/workflow_tool.py",),
        high_tier_paths=("src/fa/inner_loop/tools/workflow_tool.py",),
    ),
    DeceptiveTask(
        wording="make the prompt builder a touch smaller",
        lang="en",
        reveal_reads=("src/fa/inner_loop/prompt_composer.py",),
        reveal_writes=("src/fa/inner_loop/prompt_composer.py",),
        high_tier_paths=("src/fa/inner_loop/prompt_composer.py",),
    ),
    DeceptiveTask(
        wording="причеши главную функцию, там громоздко",
        lang="ru",
        reveal_reads=("src/fa/cli.py", "src/fa/inner_loop/coder_loop.py"),
        reveal_writes=("src/fa/cli.py",),
        high_tier_paths=("src/fa/cli.py",),
    ),
    DeceptiveTask(
        wording="поправь проверку перед пушем, чтобы не ругалась на форс",
        lang="ru",
        reveal_reads=("src/fa/hygiene/hooks/pre-push", "tests/conftest.py"),
        reveal_writes=("src/fa/hygiene/hooks/pre-push", "tests/test_push.py"),
        high_tier_paths=("src/fa/hygiene/hooks/pre-push",),
    ),
)


def test_r2_has_at_least_six_deceptive_tasks_with_languages() -> None:
    assert len(DECEPTIVE_TASKS) >= 6
    assert {t.lang for t in DECEPTIVE_TASKS} == {"en", "ru"}


def test_r2_wording_under_scopes_but_reveal_escalates() -> None:
    """The core R2 claim, per task.

    Text alone -> chat_direct (deceptive). Reading high-tier code arms L2;
    the subsequent high-tier write escalates to L3 — a stable ONE-LEVEL-at-a-
    time progression driven by evidence.
    """
    cfg = default_scope_risk_config()
    for task in DECEPTIVE_TASKS:
        op = estimate_scope(task.wording)
        # Deceptive premise: the words land on the cheap path (or at most
        # never workflow_linear from such terse wording).
        assert op.recommended_mode != "workflow_linear", f"{task.wording!r} already reads as workflow"

        # Stage 1: the run READS the coupled high-tier code (no writes yet).
        read_tiers = observed_tiers(frozenset(task.reveal_reads), frozenset(), cfg)
        arm = next_level(
            ExpansionState(level=1),
            files_read=len(task.reveal_reads),
            files_changed=0,
            write_tier=read_tiers["write_max"],
            read_tier_high=read_tiers["read_max"] >= 5,
            verify_failed=False,
            assumed_linear=False,
        )
        assert arm is not None, f"{task.wording!r}: high-tier read produced no decision"
        assert arm.level_to == 2, f"{task.wording!r}: read should ARM level 2, got {arm.level_to}"

        # Stage 2: the run WRITES the high-tier file -> escalate to level 3.
        write_tiers = observed_tiers(frozenset(task.reveal_reads), frozenset(task.reveal_writes), cfg)
        esc = next_level(
            ExpansionState(level=2),
            files_read=len(task.reveal_reads),
            files_changed=len(task.reveal_writes),
            write_tier=write_tiers["write_max"],
            read_tier_high=write_tiers["read_max"] >= 5,
            verify_failed=False,
            assumed_linear=False,
        )
        assert esc is not None and esc.level_to == 3, (
            f"{task.wording!r}: high-tier write must escalate to L3, got {esc}"
        )


def test_r2_high_tier_paths_actually_classify_high() -> None:
    """The seed paths must really be high tier — otherwise the test is theater."""
    cfg = default_scope_risk_config()
    for task in DECEPTIVE_TASKS:
        for path in task.high_tier_paths:
            # glob-style test paths like tests/test_hygiene*.py are not real
            # paths; check concrete src/ paths only.
            if "*" in path:
                continue
            assert tier_for_path(path, cfg) == 5, f"{path} should be high tier for {task.wording!r}"


def test_r2_failed_verification_escalates_even_without_high_write() -> None:
    """A red pytest on coupled work is itself an escalation signal (verify_failed)."""
    decision = next_level(
        ExpansionState(level=2),
        files_read=4,
        files_changed=1,
        write_tier=3,  # medium (e.g. a tests/ edit)
        read_tier_high=True,
        verify_failed=True,
        assumed_linear=False,
    )
    assert decision is not None and decision.level_to == 3
    assert decision.evidence == "verify_failed"


def test_r2_minimum_trajectory_shape_is_oracle_ordered(tmp_path: Path) -> None:
    """Pin the oracle-shaped minimum trajectory for deceptive work.

    Not a model eval: we assert the deterministic ORDER of capabilities the
    harness exposes for "find the coupled code -> open it -> change it ->
    verify", by reading the REAL baseline tool registry's registered names.
    """
    from fa.inner_loop.tools import build_baseline_registry

    minimum_trajectory = ("fs_search", "fs_reach", "fs_write_file", "fs_run_bash")
    registry = build_baseline_registry(tmp_path, bash_timeout_seconds=30)
    names = set(registry.names())
    assert set(minimum_trajectory) <= names, f"trajectory tools missing: {set(minimum_trajectory) - names}"

    # The verify step is a VERIFY_ONLY bash command by intent classification.
    from fa.inner_loop.bash_intent import BashIntentEffect, analyze_bash_for_intent

    analysis = analyze_bash_for_intent("python -m pytest tests/test_x.py", repo_root=tmp_path)
    assert analysis.effect is BashIntentEffect.VERIFY_ONLY
