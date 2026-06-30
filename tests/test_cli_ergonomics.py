"""Tests for the CLI ergonomics layer: positional task, short flags, stdin,
the ``workflow`` multi-role pipeline, and the bilingual ``help`` registry.
"""

from __future__ import annotations

import argparse
import io
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from _pytest.capture import CaptureFixture

from fa.cli import _cmd_help, _cmd_workflow, _resolve_task, build_parser
from fa.cli_help import COMMANDS, help_as_json
from fa.providers import SecretStore
from fa.providers.base import TransportResponse

_TEST_SECRETS = SecretStore({"TEST_FA_RUN_KEY": "sk-test-x"})

_FAKE_MODELS_YAML = """\
planner:
  model: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      slug: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: TEST_FA_RUN_KEY
coder:
  model: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      slug: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: TEST_FA_RUN_KEY
eval:
  model: "test-model"
  family: "anthropic"
  chain:
    - provider: openrouter
      slug: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: TEST_FA_RUN_KEY
"""


class _ScriptedTransport:
    """Returns a ``stop`` body for every call (enough for N workflow stages)."""

    def __init__(self, stop_text: str = "done") -> None:
        self._stop_text = stop_text
        self.calls: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout_seconds: float,
        transport_retries: int,
    ) -> TransportResponse:
        del url, headers, timeout_seconds, transport_retries
        self.calls.append(dict(json_body))
        body = {
            "choices": [
                {
                    "message": {"role": "assistant", "content": self._stop_text, "tool_calls": []},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        return TransportResponse(status=200, body=body)


def _verdict_message(verdict: str, route: str) -> str:
    return (
        "## Verification Summary\n\n"
        "### Step results\n- S1: PASS — landed\n\n"
        f"### Verdict\n{verdict}\n\n"
        f"### Route decision\n{route}\n"
    )


class _RoleAwareTransport:
    """Returns scripted eval verdicts and counts planner/coder/eval calls.

    The role is detected from the system prompt. Eval calls pop the next
    scripted ``(verdict, route)`` pair; planner/coder default to plain ``done``.
    This makes repair and adaptive workflow tests fully deterministic.
    """

    def __init__(self, eval_script: list[tuple[str, str]]) -> None:
        self._eval_script = list(eval_script)
        self.eval_calls = 0
        self.coder_calls = 0
        self.planner_calls = 0
        self.calls: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout_seconds: float,
        transport_retries: int,
    ) -> TransportResponse:
        del url, headers, timeout_seconds, transport_retries
        self.calls.append(dict(json_body))
        messages = json_body.get("messages", [])
        system = messages[0]["content"] if messages else ""
        is_eval = "First-Agent evaluator" in system
        is_coder = "First-Agent coder" in system
        is_planner = "Architect for First-Agent" in system
        if is_eval:
            self.eval_calls += 1
            verdict, route = self._eval_script.pop(0) if self._eval_script else ("PASS", "complete")
            content = _verdict_message(verdict, route)
        else:
            if is_coder:
                self.coder_calls += 1
            if is_planner:
                self.planner_calls += 1
            content = "done"
        body = {
            "choices": [
                {
                    "message": {"role": "assistant", "content": content, "tool_calls": []},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        return TransportResponse(status=200, body=body)


# ── _resolve_task ──────────────────────────────────────────────────────────


def test_resolve_task_positional() -> None:
    assert _resolve_task("hello", None) == "hello"


def test_resolve_task_flag_wins_over_positional() -> None:
    # --task is authoritative for back-compat.
    assert _resolve_task("pos", "flag") == "flag"


def test_resolve_task_none_when_absent() -> None:
    assert _resolve_task(None, None) is None


def test_resolve_task_stdin_dash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("  piped task \n"))
    assert _resolve_task("-", None) == "piped task"


# ── parser: positional + short flags + back-compat ─────────────────────────


def test_run_positional_task_parses() -> None:
    args = build_parser().parse_args(["run", "do X"])
    assert args.task_pos == "do X"
    assert args.role == "coder"


def test_run_short_flags_parse() -> None:
    args = build_parser().parse_args(["run", "-r", "planner", "-n", "20", "-i", "work-1", "do X"])
    assert (args.role, args.max_turns, args.run_id, args.task_pos) == (
        "planner",
        20,
        "work-1",
        "do X",
    )


def test_run_double_dash_task_still_works() -> None:
    args = build_parser().parse_args(["run", "--task", "legacy"])
    assert args.task == "legacy"


# ── workflow parser + dispatch ─────────────────────────────────────────────


def test_workflow_parses_roles_and_task() -> None:
    args = build_parser().parse_args(["workflow", "planner,coder,eval", "build X"])
    assert args.roles == "planner,coder,eval"
    assert args.task == "build X"


def test_workflow_per_role_overrides_parse() -> None:
    args = build_parser().parse_args(
        ["workflow", "planner,coder", "--task-planner", "p", "--task-coder", "c", "shared"]
    )
    assert args.task_planner == "p"
    assert args.task_coder == "c"


def _workflow_args(tmp_path: Path, config: Path, **over: Any) -> argparse.Namespace:
    base = {
        "roles": "planner,coder,eval",
        "task": "do the thing",
        "workspace": tmp_path,
        "run_id": "wf-test",
        "config": config,
        "max_turns": 4,
        "mode": "linear",
        "max_repairs": 2,
        "max_replans": 1,
        "task_planner": None,
        "task_coder": None,
        "task_eval": None,
    }
    base.update(over)
    return argparse.Namespace(**base)


def test_workflow_drives_all_stages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    transport = _ScriptedTransport()
    args = _workflow_args(tmp_path, config)

    code = _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS)

    assert code == 0
    # Three roles → three driven sessions (at least one transport call each).
    assert len(transport.calls) >= 3


def test_workflow_emits_eval_report_and_records_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fa.inner_loop.workflow_artifacts import load_eval_report, load_flow_state

    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    eval_message = (
        "## Verification Summary\n\n"
        "### Step results\n- S1: PASS — landed\n\n"
        "### Verdict\nREPAIR_REQUIRED\n\n"
        "### Route decision\nreturn_to_coder\n"
    )
    transport = _ScriptedTransport(stop_text=eval_message)
    args = _workflow_args(tmp_path, config)

    code = _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS)
    assert code == 0

    session_dir = home / ".fa" / "session-log" / "wf-test"
    report = load_eval_report(session_dir / "eval_report.json")
    assert report.verdict == "REPAIR_REQUIRED"
    assert report.route_decision == "return_to_coder"
    assert report.run_id == "wf-test"

    # FlowState records the eval route as persisted controller truth; the
    # linear baseline does not loop yet, but it must not claim DONE on a
    # non-PASS verdict.
    state = load_flow_state(session_dir / "flow_state.json")
    assert state.status == "REPAIR_REQUIRED"
    assert state.last_route_decision == "return_to_coder"


def _repair_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return config, home / ".fa" / "session-log" / "wf-test"


def test_repair_mode_loops_until_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fa.inner_loop.workflow_artifacts import load_eval_report, load_flow_state

    config, session_dir = _repair_env(tmp_path, monkeypatch)
    # First eval routes back to coder; the repair eval passes.
    transport = _RoleAwareTransport([("REPAIR_REQUIRED", "return_to_coder"), ("PASS", "complete")])
    args = _workflow_args(tmp_path, config, mode="repair", max_repairs=2)

    code = _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS)
    assert code == 0
    # Initial coder + 1 repair coder = 2 coder sessions; 2 eval sessions.
    assert transport.coder_calls == 2
    assert transport.eval_calls == 2

    report = load_eval_report(session_dir / "eval_report.json")
    assert report.verdict == "PASS"  # latest eval is controller truth
    state = load_flow_state(session_dir / "flow_state.json")
    assert state.status == "DONE"
    assert state.repair_round == 1
    assert state.last_route_decision == "complete"


def test_repair_mode_enforces_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fa.inner_loop.workflow_artifacts import load_flow_state

    config, session_dir = _repair_env(tmp_path, monkeypatch)
    # Eval always routes back to coder → budget must cap the loop.
    transport = _RoleAwareTransport([("REPAIR_REQUIRED", "return_to_coder")] * 10)
    args = _workflow_args(tmp_path, config, mode="repair", max_repairs=2)

    code = _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS)
    assert code == 0  # linear/repair baseline does not fail the process
    # 1 initial eval + 2 repair evals = 3; coders: 1 initial + 2 repair = 3.
    assert transport.eval_calls == 3
    assert transport.coder_calls == 3

    state = load_flow_state(session_dir / "flow_state.json")
    assert state.status == "REPAIR_REQUIRED"
    assert state.repair_round == 2
    assert state.last_route_decision == "return_to_coder"


def test_repair_mode_zero_budget_behaves_like_one_eval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fa.inner_loop.workflow_artifacts import load_flow_state

    config, session_dir = _repair_env(tmp_path, monkeypatch)
    transport = _RoleAwareTransport([("REPAIR_REQUIRED", "return_to_coder")] * 4)
    args = _workflow_args(tmp_path, config, mode="repair", max_repairs=0)

    code = _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS)
    assert code == 0
    # No repair rounds: only the initial coder + initial eval.
    assert transport.coder_calls == 1
    assert transport.eval_calls == 1
    state = load_flow_state(session_dir / "flow_state.json")
    assert state.repair_round == 0


def test_repair_mode_does_not_loop_on_return_to_planner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fa.inner_loop.workflow_artifacts import load_flow_state

    config, session_dir = _repair_env(tmp_path, monkeypatch)
    # REPLAN routes to planner — this slice records but does NOT re-enter.
    transport = _RoleAwareTransport([("REPLAN_REQUIRED", "return_to_planner")])
    args = _workflow_args(tmp_path, config, mode="repair", max_repairs=2)

    code = _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS)
    assert code == 0
    assert transport.coder_calls == 1  # no repair coder round
    assert transport.eval_calls == 1
    state = load_flow_state(session_dir / "flow_state.json")
    assert state.status == "REPLAN_REQUIRED"
    assert state.last_route_decision == "return_to_planner"
    assert state.repair_round == 0


def test_repair_mode_requires_coder_and_eval_roles(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    args = _workflow_args(tmp_path, tmp_path / "models.yaml", roles="planner", mode="repair")
    code = _cmd_workflow(args, transport=_ScriptedTransport())
    assert code == 2
    err = capsys.readouterr().err
    assert "requires roles to include" in err
    assert "coder and eval" in err


def test_workflow_invalid_mode_rejected(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    args = _workflow_args(tmp_path, tmp_path / "models.yaml", mode="bogus")
    code = _cmd_workflow(args, transport=_ScriptedTransport())
    assert code == 2
    assert "--mode must be one of" in capsys.readouterr().err


def test_workflow_parses_mode_and_max_repairs() -> None:
    args = build_parser().parse_args(
        ["workflow", "coder,eval", "do X", "--mode", "repair", "--max-repairs", "3"]
    )
    assert args.mode == "repair"
    assert args.max_repairs == 3


def test_workflow_rejects_empty_roles(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    args = _workflow_args(tmp_path, tmp_path / "models.yaml", roles=" , ")
    code = _cmd_workflow(args, transport=_ScriptedTransport())
    assert code == 2
    assert "at least one role" in capsys.readouterr().err


def test_workflow_requires_task_for_each_role(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    # No shared task and no override for 'eval' → fail before driving anything.
    args = _workflow_args(
        tmp_path,
        tmp_path / "models.yaml",
        task=None,
        roles="planner,eval",
        task_planner="only-planner",
    )
    code = _cmd_workflow(args, transport=_ScriptedTransport())
    assert code == 2
    assert "no task for role 'eval'" in capsys.readouterr().err


# ── help registry ──────────────────────────────────────────────────────────


def test_help_json_is_valid_and_bilingual() -> None:
    data = json.loads(help_as_json())
    assert set(data) >= {"run", "workflow", "selfcheck", "probe", "stats"}
    for entry in data.values():
        assert entry["summary_ru"] and entry["summary_en"]
        for arg in entry["args"].values():
            assert arg["ru"] and arg["en"]


def test_help_command_json_flag(capsys: CaptureFixture[str]) -> None:
    code = _cmd_help(argparse.Namespace(json=True, topic=None))
    assert code == 0
    out = capsys.readouterr().out
    assert json.loads(out)  # parses


def test_help_command_topic(capsys: CaptureFixture[str]) -> None:
    code = _cmd_help(argparse.Namespace(json=False, topic="workflow"))
    assert code == 0
    assert "workflow" in capsys.readouterr().out or "pipeline" in capsys.readouterr().out


def test_help_command_unknown_topic(capsys: CaptureFixture[str]) -> None:
    code = _cmd_help(argparse.Namespace(json=False, topic="nope"))
    assert code == 2
    assert "неизвестная команда" in capsys.readouterr().err


def test_help_registry_covers_real_commands() -> None:
    # Every registry command must be a real subcommand (no drift).
    parser = build_parser()
    subparsers = parser._subparsers
    assert subparsers is not None
    sub = next(a for a in subparsers._group_actions if hasattr(a, "choices"))
    choices = getattr(sub, "choices", None)
    assert choices is not None
    real = set(choices)
    assert set(COMMANDS) <= real, (
        f"help registry references unknown commands: {set(COMMANDS) - real}"
    )


def test_adaptive_mode_replans_until_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fa.inner_loop.workflow_artifacts import load_eval_report, load_flow_state

    config, session_dir = _repair_env(tmp_path, monkeypatch)
    transport = _RoleAwareTransport(
        [("REPLAN_REQUIRED", "return_to_planner"), ("PASS", "complete")]
    )
    args = _workflow_args(tmp_path, config, mode="adaptive", max_repairs=2, max_replans=1)

    code = _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS)
    assert code == 0
    assert transport.planner_calls == 2
    assert transport.coder_calls == 2
    assert transport.eval_calls == 2

    report = load_eval_report(session_dir / "eval_report.json")
    assert report.verdict == "PASS"
    assert report.plan_version == 2
    state = load_flow_state(session_dir / "flow_state.json")
    assert state.status == "DONE"
    assert state.replan_round == 1
    assert state.active_plan_version == 2
    assert state.last_route_decision == "complete"


def test_adaptive_mode_enforces_replan_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fa.inner_loop.workflow_artifacts import load_flow_state

    config, session_dir = _repair_env(tmp_path, monkeypatch)
    transport = _RoleAwareTransport([("REPLAN_REQUIRED", "return_to_planner")] * 6)
    args = _workflow_args(tmp_path, config, mode="adaptive", max_repairs=2, max_replans=1)

    code = _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS)
    assert code == 0
    assert transport.planner_calls == 2
    assert transport.coder_calls == 2
    assert transport.eval_calls == 2

    state = load_flow_state(session_dir / "flow_state.json")
    assert state.status == "REPLAN_REQUIRED"
    assert state.replan_round == 1
    assert state.active_plan_version == 2
    assert state.last_route_decision == "return_to_planner"


def test_adaptive_mode_can_mix_repair_then_replan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fa.inner_loop.workflow_artifacts import load_eval_report, load_flow_state

    config, session_dir = _repair_env(tmp_path, monkeypatch)
    transport = _RoleAwareTransport(
        [
            ("REPAIR_REQUIRED", "return_to_coder"),
            ("REPLAN_REQUIRED", "return_to_planner"),
            ("PASS", "complete"),
        ]
    )
    args = _workflow_args(tmp_path, config, mode="adaptive", max_repairs=2, max_replans=1)

    code = _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS)
    assert code == 0
    assert transport.planner_calls == 2
    assert transport.coder_calls == 3
    assert transport.eval_calls == 3

    report = load_eval_report(session_dir / "eval_report.json")
    assert report.verdict == "PASS"
    assert report.plan_version == 2
    state = load_flow_state(session_dir / "flow_state.json")
    assert state.status == "DONE"
    assert state.repair_round == 1
    assert state.replan_round == 1
    assert state.active_plan_version == 2


def test_adaptive_mode_requires_planner_coder_eval_roles() -> None:
    args = _workflow_args(Path('.'), Path('models.yaml'), roles="coder,eval", mode="adaptive")
    assert _cmd_workflow(args, transport=_ScriptedTransport(), secrets=_TEST_SECRETS) == 2


def test_workflow_parses_mode_and_budgets() -> None:
    args = build_parser().parse_args(
        [
            "workflow",
            "planner,coder,eval",
            "do X",
            "--mode",
            "adaptive",
            "--max-repairs",
            "3",
            "--max-replans",
            "2",
        ]
    )
    assert args.mode == "adaptive"
    assert args.max_repairs == 3
    assert args.max_replans == 2
