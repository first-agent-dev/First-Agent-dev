"""S13.4c — Eval independence: blocking → adversarial.

Plan: ``worklogs/implementation-plans/PLAN-cli-trace-S13-multi-provider-conformance.md``
§S13.4c.

**Why.** A same-family eval (eval family == planner or coder) used to raise
``EvalFamilyConflictError`` and exit 2. That gate was trivially defeated by a
``family:`` string edit (the live box ran mistral-small in all three roles) and
it blocked legitimate free-tier multi-provider setups. S13.4c replaces the
blocking rule with a *recorded risk* plus an *adversarial eval stance*: a
same-family eval loads, emits exactly one warning, and the eval role actively
seeks disconfirming evidence.

**Tests labelled per tests-writing skill:**
- **C1** — the adversarial preamble reaches the **composed** eval system message
  via the real ``build_prompt_parts_v2`` path (the DoD's "asserted on the composed
  prompt, not on a flag"); a neutral eval composes WITHOUT it.
- **C0p** — ``assess_eval_independence`` (in ``test_roles.py``) + the config
  loader carrying ``eval_independence`` on ``ModelsConfig``.
- **C1 (CLI stance threading)** — ``_eval_system_prompt_extra`` returns the
  adversarial preamble for an eval role with a same-family config, and ``""``
  otherwise.
- **C0p** — ``EvalReport`` round-trips ``eval_independence`` through
  ``eval_report.json``.

**Kill-checks:** K9 (same-family → loads + one warning + adversarial stance);
K10 (disjoint → zero warnings + neutral); producer kill-check (force
``stance="neutral"`` on a same-family config → the adversarial-prompt assertion
fails, naming the missing stance).
"""

from __future__ import annotations

from pathlib import Path

from fa.inner_loop.prompt import ADVERSARIAL_EVAL_STANCE_PREAMBLE
from fa.inner_loop.prompt_composer import build_prompt_parts_v2
from fa.inner_loop.workflow_artifacts import EvalReport, parse_eval_report, write_eval_report
from fa.providers.config import ModelsConfig
from fa.roles import EvalIndependence

# --- C1: the adversarial preamble reaches the COMPOSED eval system message ---


def test_adversarial_preamble_reaches_composed_eval_system_message() -> None:
    """C1 — threading the stance via system_prompt_extra lands in the eval prompt.

    The production path passes ``system_prompt_extra`` (the adversarial preamble)
    through ``extract_pinned_content``, which becomes the ``agents_md_map`` system
    message in ``build_prompt_parts_v2``. This composes the REAL eval request and
    asserts the preamble is present in a system message — the DoD's "asserted on
    the composed prompt", not on a flag or a shadow function.
    """
    stance_extra = ADVERSARIAL_EVAL_STANCE_PREAMBLE
    # extract_pinned_content wraps extra_instructions under this header:
    agents_md_map = f"### STANDING PROFILE GUIDELINES (hash:abcd)\n{stance_extra}\n"

    parts, _key = build_prompt_parts_v2(
        base_system="eval base system",
        agents_md_map=agents_md_map,
        tool_defs=[],
        role_id="eval",
        task="verify",
        observations=[],
    )
    system_contents = [str(m.get("content", "")) for m in parts.cacheable if m.get("role") == "system"]
    joined = "\n".join(system_contents)
    assert ADVERSARIAL_EVAL_STANCE_PREAMBLE in joined
    assert "DISCONFIRMING" in joined


def test_neutral_eval_has_no_adversarial_preamble_in_composed_prompt() -> None:
    """C1 — a neutral (disjoint) eval composes WITHOUT the adversarial preamble."""
    parts, _key = build_prompt_parts_v2(
        base_system="eval base system",
        agents_md_map="",  # no system_prompt_extra for neutral/disjoint eval
        tool_defs=[],
        role_id="eval",
        task="verify",
        observations=[],
    )
    system_contents = [str(m.get("content", "")) for m in parts.cacheable if m.get("role") == "system"]
    joined = "\n".join(system_contents)
    assert "DISCONFIRMING" not in joined
    assert "Adversarial evaluation stance" not in joined


# --- C1: CLI stance threading (helper under test) ----------------------------


def test_eval_system_prompt_extra_adversarial_for_same_family_eval() -> None:
    from fa.cli import _eval_system_prompt_extra

    models = ModelsConfig(
        roles={},
        warnings=(),
        eval_independence=EvalIndependence(
            disjoint=False,
            reason="eval matches planner",
            stance="adversarial",
        ),
    )
    extra = _eval_system_prompt_extra("eval", models)
    assert extra == ADVERSARIAL_EVAL_STANCE_PREAMBLE


def test_eval_system_prompt_extra_empty_for_non_eval_role() -> None:
    from fa.cli import _eval_system_prompt_extra

    models = ModelsConfig(
        roles={},
        warnings=(),
        eval_independence=EvalIndependence(
            disjoint=False,
            reason="eval matches planner",
            stance="adversarial",
        ),
    )
    assert _eval_system_prompt_extra("coder", models) == ""
    assert _eval_system_prompt_extra("planner", models) == ""


def test_eval_system_prompt_extra_empty_for_neutral_eval() -> None:
    from fa.cli import _eval_system_prompt_extra

    models = ModelsConfig(
        roles={},
        warnings=(),
        eval_independence=EvalIndependence(
            disjoint=True,
            reason="disjoint",
            stance="neutral",
        ),
    )
    assert _eval_system_prompt_extra("eval", models) == ""


def test_eval_system_prompt_extra_empty_when_no_assessment() -> None:
    from fa.cli import _eval_system_prompt_extra

    models = ModelsConfig(roles={}, warnings=())  # eval_independence None
    assert _eval_system_prompt_extra("eval", models) == ""


# --- C0p: EvalReport carries eval_independence -------------------------------


def test_eval_report_round_trips_eval_independence(tmp_path: Path) -> None:
    path = tmp_path / "eval_report.json"
    report = parse_eval_report(
        "## Verification Summary\n### Verdict\nPASS\n",
        run_id="run-1",
        plan_id="plan-a",
        evaluation_id="eval-1",
        plan_version=1,
        eval_independence={"disjoint": False, "stance": "adversarial"},
    )
    write_eval_report(path, report)
    loaded = EvalReport.from_json_dict(__import__("json").loads(path.read_text(encoding="utf-8")))
    assert loaded.eval_independence == {"disjoint": False, "stance": "adversarial"}


def test_eval_report_omits_eval_independence_when_none(tmp_path: Path) -> None:
    path = tmp_path / "eval_report.json"
    report = parse_eval_report(
        "## Verification Summary\n### Verdict\nPASS\n",
        run_id="run-1",
        plan_id="plan-a",
        evaluation_id="eval-1",
        plan_version=1,
        eval_independence=None,
    )
    write_eval_report(path, report)
    data = __import__("json").loads(path.read_text(encoding="utf-8"))
    assert "eval_independence" not in data
