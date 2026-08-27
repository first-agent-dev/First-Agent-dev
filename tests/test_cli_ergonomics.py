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
from fa.inner_loop.session_db import SessionDatabase
from fa.providers import SecretStore
from fa.providers.base import TransportResponse

_TEST_SECRETS = SecretStore({"TEST_FA_RUN_KEY": "sk-test-x"})

_FAKE_MODELS_YAML = """\
planner:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: TEST_FA_RUN_KEY
coder:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: TEST_FA_RUN_KEY
eval:
  name: "test-model"
  family: "anthropic"
  chain:
    - provider: openrouter
      model: "test/model"
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


def test_resolve_task_transparent_piping_only(monkeypatch: pytest.MonkeyPatch) -> None:
    # Under mock, sys.stdin.isatty() will return False, so transparent stdin is read
    monkeypatch.setattr("sys.stdin", io.StringIO("  piped task only  "))
    # Mock isatty to return False explicitly if needed, but StringIO already does.
    assert _resolve_task(None, None) == "piped task only"


def test_resolve_task_transparent_piping_concatenation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("piped context data"))
    expected = "explicit instruction\n\n<stdin>\npiped context data\n</stdin>"
    assert _resolve_task("explicit instruction", None) == expected


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


def test_session_selector_parser_preserves_workspace_default() -> None:
    run_args = build_parser().parse_args(["run", "--task", "work"])
    workflow_args = build_parser().parse_args(["workflow", "planner", "work"])

    assert run_args.session_id is None
    assert workflow_args.session_id is None
    assert run_args.workspace is None
    assert workflow_args.workspace is None


def test_workflow_session_manager_uses_one_invocation_run_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C2 producer proof: workflow stages share one manager-admitted run ID."""
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    args = _workflow_args(tmp_path, config, run_id="", session_id=None)

    # Q35b (S10c.2): the eval verdict here is BLOCKED, so the exit code is 1.
    # The assertion below is about session/run identity, which is unaffected.
    assert _cmd_workflow(args, transport=_ScriptedTransport(), secrets=_TEST_SECRETS) == 1

    manifests = sorted((home / ".fa" / "sessions").glob("*/manifest.json"))
    assert len(manifests) == 1
    session_id = json.loads(manifests[0].read_text(encoding="utf-8"))["session_id"]
    run_dirs = sorted(d for d in (home / ".fa" / "session-log").iterdir() if d.is_dir())
    assert len(run_dirs) == 1
    run_id = run_dirs[0].name
    assert (run_dirs[0] / "flow_state.json").is_file()
    assert (run_dirs[0] / "eval_report.json").is_file()

    db = SessionDatabase.open_existing(home / ".fa" / "sessions" / session_id / "session.db", session_id=session_id)
    rows = db.read_event_rows(run_id=run_id)
    assert rows
    assert {row["run_id"] for row in rows} == {run_id}
    assert {row["session_id"] for row in rows} == {session_id}


def test_workflow_drives_all_stages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    transport = _ScriptedTransport()
    args = _workflow_args(tmp_path, config)

    code = _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS)

    # Q35b (S10c.2): all three stages RAN, but the eval verdict is BLOCKED, so
    # the exit code is 1. "the pipeline ran" and "the code was accepted" are now
    # different questions; this test asks the first, via transport.calls.
    assert code == 1
    # Three roles → three driven sessions (at least one transport call each).
    assert len(transport.calls) >= 3


def test_workflow_emits_eval_report_and_records_route(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    # Q35b (S10c.2): terminal status is REPAIR_REQUIRED, not DONE, so the
    # exit code is now 1. The loop/budget assertions below are unchanged.
    assert code == 1

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


# D4: ``--mode repair`` was removed; adaptive with a planner-less role list
# ("coder,eval") is its exact replacement. These tests were migrated rather than
# deleted precisely because they encode the repair contract — if planner-less
# adaptive did not reproduce it, they would fail, so keeping them IS the
# equivalence proof. Role list changed from the default planner,coder,eval to
# coder,eval so the initial pass runs the same two stages repair used to run.
def _repair_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return config, home / ".fa" / "session-log" / "wf-test"


def test_adaptive_planner_less_loops_until_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fa.inner_loop.workflow_artifacts import load_eval_report, load_flow_state

    config, session_dir = _repair_env(tmp_path, monkeypatch)
    # First eval routes back to coder; the repair eval passes.
    transport = _RoleAwareTransport([("REPAIR_REQUIRED", "return_to_coder"), ("PASS", "complete")])
    args = _workflow_args(tmp_path, config, roles="coder,eval", mode="adaptive", max_repairs=2)

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


def test_adaptive_planner_less_enforces_repair_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fa.inner_loop.workflow_artifacts import load_flow_state

    config, session_dir = _repair_env(tmp_path, monkeypatch)
    # Eval always routes back to coder → budget must cap the loop.
    transport = _RoleAwareTransport([("REPAIR_REQUIRED", "return_to_coder")] * 10)
    args = _workflow_args(tmp_path, config, roles="coder,eval", mode="adaptive", max_repairs=2)

    code = _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS)
    # Q35b (S10c.2): terminal status is REPAIR_REQUIRED, not DONE, so the
    # exit code is now 1. The loop/budget assertions below are unchanged.
    assert code == 1
    # 1 initial eval + 2 repair evals = 3; coders: 1 initial + 2 repair = 3.
    assert transport.eval_calls == 3
    assert transport.coder_calls == 3

    state = load_flow_state(session_dir / "flow_state.json")
    assert state.status == "REPAIR_REQUIRED"
    assert state.repair_round == 2
    assert state.last_route_decision == "return_to_coder"


def test_adaptive_zero_repair_budget_behaves_like_one_eval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fa.inner_loop.workflow_artifacts import load_flow_state

    config, session_dir = _repair_env(tmp_path, monkeypatch)
    transport = _RoleAwareTransport([("REPAIR_REQUIRED", "return_to_coder")] * 4)
    args = _workflow_args(tmp_path, config, roles="coder,eval", mode="adaptive", max_repairs=0)

    code = _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS)
    # Q35b (S10c.2): terminal status is REPAIR_REQUIRED, not DONE, so the
    # exit code is now 1. The loop/budget assertions below are unchanged.
    assert code == 1
    # No repair rounds: only the initial coder + initial eval.
    assert transport.coder_calls == 1
    assert transport.eval_calls == 1
    state = load_flow_state(session_dir / "flow_state.json")
    assert state.repair_round == 0


def test_adaptive_without_planner_terminates_on_return_to_planner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fa.inner_loop.workflow_artifacts import load_flow_state

    config, session_dir = _repair_env(tmp_path, monkeypatch)
    # REPLAN routes to planner — this slice records but does NOT re-enter.
    transport = _RoleAwareTransport([("REPLAN_REQUIRED", "return_to_planner")])
    args = _workflow_args(tmp_path, config, roles="coder,eval", mode="adaptive", max_repairs=2)

    code = _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS)
    # Q35b (S10c.2): terminal status is REPLAN_REQUIRED, not DONE, so the
    # exit code is now 1. The loop/budget assertions below are unchanged.
    assert code == 1
    assert transport.coder_calls == 1  # no repair coder round
    assert transport.eval_calls == 1
    state = load_flow_state(session_dir / "flow_state.json")
    assert state.status == "REPLAN_REQUIRED"
    assert state.last_route_decision == "return_to_planner"
    assert state.repair_round == 0


def test_adaptive_mode_requires_coder_and_eval_roles(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """D4: adaptive needs coder+eval; planner is optional (it was mandatory before)."""
    args = _workflow_args(tmp_path, tmp_path / "models.yaml", roles="planner", mode="adaptive")
    code = _cmd_workflow(args, transport=_ScriptedTransport())
    assert code == 2
    err = capsys.readouterr().err
    assert "requires roles to include" in err
    assert "coder and eval" in err


def test_repair_mode_is_no_longer_accepted(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """D4: ``--mode repair`` is gone; the error names the surviving modes.

    Kill-check for the removal itself: if "repair" were still in
    WORKFLOW_MODES this returns 0/1 rather than the 2 of a rejected flag.
    """
    args = _workflow_args(tmp_path, tmp_path / "models.yaml", mode="repair")
    assert _cmd_workflow(args, transport=_ScriptedTransport()) == 2
    err = capsys.readouterr().err
    assert "--mode must be one of" in err
    assert "linear, adaptive" in err
    assert "repair" not in err.split("(got")[0]


def test_adaptive_accepts_planner_less_roles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """D4: coder,eval is a valid adaptive role list — repair's migration path.

    Before D4 adaptive hard-rejected a planner-less list (exit 2, "requires
    roles to include planner"), which would have stranded every documented
    ``fa workflow coder,eval --mode repair`` invocation.
    """
    from fa.inner_loop.workflow_artifacts import load_flow_state

    config, session_dir = _repair_env(tmp_path, monkeypatch)
    transport = _RoleAwareTransport([("REPAIR_REQUIRED", "return_to_coder"), ("PASS", "complete")])
    args = _workflow_args(tmp_path, config, roles="coder,eval", mode="adaptive", max_repairs=2)

    assert _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS) == 0
    assert load_flow_state(session_dir / "flow_state.json").status == "DONE"


def test_adaptive_without_planner_does_not_spin_on_replan_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D4: return_to_planner with no planner terminates instead of looping.

    Without the explicit guard, _canonical_loop_roles silently drops the
    absent planner and the loop would re-run coder→eval against an unchanged
    plan until the replan budget drained. The stage counts are the oracle:
    one coder and one eval, not one per replan round.
    """
    from fa.inner_loop.workflow_artifacts import load_flow_state

    config, session_dir = _repair_env(tmp_path, monkeypatch)
    transport = _RoleAwareTransport([("REPLAN_REQUIRED", "return_to_planner")] * 10)
    args = _workflow_args(tmp_path, config, roles="coder,eval", mode="adaptive", max_replans=2)

    assert _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS) == 1
    assert transport.coder_calls == 1, "replan loop ran despite there being no planner"
    assert transport.eval_calls == 1
    state = load_flow_state(session_dir / "flow_state.json")
    assert state.status == "REPLAN_REQUIRED"
    assert state.replan_round == 0


def test_workflow_invalid_mode_rejected(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    args = _workflow_args(tmp_path, tmp_path / "models.yaml", mode="bogus")
    code = _cmd_workflow(args, transport=_ScriptedTransport())
    assert code == 2
    assert "--mode must be one of" in capsys.readouterr().err


def test_workflow_parses_mode_and_max_repairs() -> None:
    args = build_parser().parse_args(["workflow", "coder,eval", "do X", "--mode", "adaptive", "--max-repairs", "3"])
    assert args.mode == "adaptive"
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
    assert set(COMMANDS) <= real, f"help registry references unknown commands: {set(COMMANDS) - real}"


def test_conformance_help_distinguishes_offline_and_live_cases() -> None:
    """C2 T7: parser and bilingual registry describe the same case boundary."""

    entry = COMMANDS["conformance"]
    combined_registry_en = f"{entry['summary_en']} {entry['args']['--provider']['en']}"
    assert "CONF-1..7" in combined_registry_en
    assert "CONF-1..8" in combined_registry_en
    assert entry["summary_ru"]
    assert entry["args"]["--provider"]["ru"]

    parser = build_parser()
    subparsers = parser._subparsers
    assert subparsers is not None
    sub = next(action for action in subparsers._group_actions if hasattr(action, "choices"))
    choices = getattr(sub, "choices", None)
    assert choices is not None
    help_text = choices["conformance"].format_help()
    assert "CONF-1..7" in help_text
    assert "CONF-1..8" in help_text
    assert "exact production" in help_text


def test_adaptive_mode_replans_until_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fa.inner_loop.workflow_artifacts import load_eval_report, load_flow_state

    config, session_dir = _repair_env(tmp_path, monkeypatch)
    transport = _RoleAwareTransport([("REPLAN_REQUIRED", "return_to_planner"), ("PASS", "complete")])
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


def test_adaptive_mode_enforces_replan_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fa.inner_loop.workflow_artifacts import load_flow_state

    config, session_dir = _repair_env(tmp_path, monkeypatch)
    transport = _RoleAwareTransport([("REPLAN_REQUIRED", "return_to_planner")] * 6)
    args = _workflow_args(tmp_path, config, mode="adaptive", max_repairs=2, max_replans=1)

    code = _cmd_workflow(args, transport=transport, secrets=_TEST_SECRETS)
    # Q35b (S10c.2): terminal status is REPLAN_REQUIRED, not DONE, so the
    # exit code is now 1. The loop/budget assertions below are unchanged.
    assert code == 1
    assert transport.planner_calls == 2
    assert transport.coder_calls == 2
    assert transport.eval_calls == 2

    state = load_flow_state(session_dir / "flow_state.json")
    assert state.status == "REPLAN_REQUIRED"
    assert state.replan_round == 1
    assert state.active_plan_version == 2
    assert state.last_route_decision == "return_to_planner"


def test_adaptive_mode_can_mix_repair_then_replan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    args = _workflow_args(Path("."), Path("models.yaml"), roles="coder,eval", mode="adaptive")
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


# ── S3: scope estimation for chat role ──────────────────────────────────────


class _CapturingTransport:
    """Captures the system prompt sent to the LLM for inspection."""

    def __init__(self) -> None:
        self.system_prompt: str = ""
        self.system_messages: list[str] = []
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
        self.system_messages = [m.get("content", "") for m in messages if m.get("role") == "system"]
        if messages:
            self.system_prompt = messages[0].get("content", "")
        body = {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "done", "tool_calls": []},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        return TransportResponse(status=200, body=body)


def test_chat_role_logs_scope_estimate_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C1: fa run -r chat logs scope_estimate event to events.jsonl."""
    from fa.cli import _cmd_run

    config = tmp_path / "models.yaml"
    chat_models_yaml = """\
chat:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: TEST_FA_RUN_KEY
"""
    config.write_text(chat_models_yaml, encoding="utf-8")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    transport = _CapturingTransport()
    args = build_parser().parse_args(
        ["run", "-r", "chat", "--config", str(config), "--workspace", str(tmp_path), "fix typo in README"]
    )

    code = _cmd_run(args, transport=transport, secrets=_TEST_SECRETS)
    assert code == 0

    # Find the session log directory
    session_log_dir = home / ".fa" / "session-log"
    run_dirs = list(session_log_dir.iterdir())
    assert len(run_dirs) == 1
    events_jsonl = run_dirs[0] / "events.jsonl"
    assert events_jsonl.exists()

    # Parse events and find scope_estimate
    events = [json.loads(line) for line in events_jsonl.read_text(encoding="utf-8").splitlines()]
    scope_events = [e for e in events if e.get("kind") == "scope_estimate"]
    assert len(scope_events) == 1, f"Expected 1 scope_estimate event, got {len(scope_events)}"

    scope_event = scope_events[0]
    content = scope_event["content"]
    assert content["difficulty"] == 1
    assert content["scope"] == "single-file"
    assert content["recommended_mode"] == "chat_direct"
    assert "fix typo" in content["task_preview"]


def test_coder_role_does_not_log_scope_estimate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C1: fa run -r coder does NOT log scope_estimate (only chat role)."""
    from fa.cli import _cmd_run

    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    transport = _CapturingTransport()
    args = build_parser().parse_args(
        ["run", "-r", "coder", "--config", str(config), "--workspace", str(tmp_path), "fix typo in README"]
    )

    code = _cmd_run(args, transport=transport, secrets=_TEST_SECRETS)
    assert code == 0

    session_log_dir = home / ".fa" / "session-log"
    run_dirs = list(session_log_dir.iterdir())
    assert len(run_dirs) == 1
    events_jsonl = run_dirs[0] / "events.jsonl"

    events = [json.loads(line) for line in events_jsonl.read_text(encoding="utf-8").splitlines()]
    scope_events = [e for e in events if e.get("kind") == "scope_estimate"]
    assert len(scope_events) == 0, f"Expected 0 scope_estimate events for coder, got {len(scope_events)}"


def test_chat_role_system_prompt_contains_scope_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C1: the scope hint is delivered, in the NON-cacheable block (D7).

    REVISED 2026-08-26. This test previously asserted the hint landed in the
    AGENTS.md map (the second system message). That routing was the defect:
    ``agents_md_map`` is hashed into ``hash_map``, a cache-key component, so
    every distinct scope estimate produced a distinct cache key and the
    cacheable prefix was never reused. The hint now travels via
    ``drive_session(turn_context=...)`` into the non-cacheable block.
    See tests/test_scope_hint_cache_key.py for the invariance proof.
    """
    from fa.cli import _cmd_run

    config = tmp_path / "models.yaml"
    chat_models_yaml = """\
chat:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: TEST_FA_RUN_KEY
"""
    config.write_text(chat_models_yaml, encoding="utf-8")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    transport = _CapturingTransport()
    args = build_parser().parse_args(
        ["run", "-r", "chat", "--config", str(config), "--workspace", str(tmp_path), "refactor auth module"]
    )

    code = _cmd_run(args, transport=transport, secrets=_TEST_SECRETS)
    assert code == 0

    assert len(transport.system_messages) >= 2, f"Expected ≥2 system messages, got {len(transport.system_messages)}"

    # The hint must be delivered somewhere the model can read it. Skip index 0:
    # the chat base prompt itself documents the mechanism using the literal
    # string "## Task Scope Estimate" (prompt.py:927), so matching there would
    # pass even if the injection were removed entirely.
    injected = [m for m in transport.system_messages[1:] if "## Task Scope Estimate" in m]
    assert injected, "Scope hint was not injected into any system message"
    assert "Difficulty:" in injected[0]
    assert "Recommended mode:" in injected[0]

    # And it must NOT be in the AGENTS.md map, which is cache-key material.
    agents_md_content = transport.system_messages[1]
    assert "## Task Scope Estimate" not in agents_md_content, (
        "Scope hint is back in agents_md_map — this re-breaks prefix caching (D7)"
    )


def test_chat_role_empty_task_does_not_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C1: empty task handled gracefully (ValueError caught, no crash)."""
    from fa.cli import _cmd_run

    config = tmp_path / "models.yaml"
    chat_models_yaml = """\
chat:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: TEST_FA_RUN_KEY
"""
    config.write_text(chat_models_yaml, encoding="utf-8")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    transport = _CapturingTransport()
    # Empty task (whitespace only) should trigger ValueError in estimate_scope
    args = build_parser().parse_args(
        ["run", "-r", "chat", "--config", str(config), "--workspace", str(tmp_path), "   "]
    )

    # Should not crash — whitespace-only task is rejected by _validate_run_args
    # with exit code 2 (usage error), which IS graceful handling.
    # The ValueError handler in the scope estimation block is defense-in-depth
    # for tasks that pass CLI validation but trigger the estimator.
    code = _cmd_run(args, transport=transport, secrets=_TEST_SECRETS)
    assert code == 2  # validation rejects empty tasks before scope estimation

    # No session directory or events should be created for a rejected task.
    session_log_dir = home / ".fa" / "session-log"
    if session_log_dir.exists():
        run_dirs = list(session_log_dir.iterdir())
        for run_dir in run_dirs:
            events_jsonl = run_dir / "events.jsonl"
            if events_jsonl.exists():
                events = [json.loads(line) for line in events_jsonl.read_text(encoding="utf-8").splitlines()]
                scope_events = [e for e in events if e.get("kind") == "scope_estimate"]
                assert len(scope_events) == 0, "Empty task should not produce scope_estimate event"


def test_chat_role_scope_estimate_in_blackboard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C1 (S3.5): scope_estimate event written to blackboard after chat run."""
    from fa.cli import _cmd_run
    from fa.inner_loop.session_db import SessionDatabase

    config = tmp_path / "models.yaml"
    chat_models_yaml = """\
chat:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: TEST_FA_RUN_KEY
"""
    config.write_text(chat_models_yaml, encoding="utf-8")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    transport = _CapturingTransport()
    args = build_parser().parse_args(
        ["run", "-r", "chat", "--config", str(config), "--workspace", str(tmp_path), "fix typo in README"]
    )

    code = _cmd_run(args, transport=transport, secrets=_TEST_SECRETS)
    assert code == 0

    # Find session DB and query blackboard for scope_estimate entries
    session_dir = home / ".fa" / "sessions"
    session_dirs = list(session_dir.iterdir()) if session_dir.exists() else []
    assert len(session_dirs) >= 1, "Expected at least one session directory"

    # Find the manifest to get session_id and db path
    manifest_path = session_dirs[0] / "manifest.json"
    assert manifest_path.exists(), "Session manifest not found"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    session_id = manifest["session_id"]
    db_path = Path(manifest["session_db_path"])

    db = SessionDatabase.open_existing(db_path, session_id=session_id)
    # Find run_id from the session
    run_ids = db.list_run_ids()
    assert len(run_ids) >= 1

    # Query blackboard for scope_estimate type
    rows = db.query_blackboard_rows("scope_estimate", None)
    assert len(rows) >= 1, f"Expected blackboard scope_estimate entry, found {len(rows)}"

    entry = rows[0]
    assert entry["type"] == "scope_estimate"
    payload = entry["payload"]
    assert payload["difficulty"] == 1
    assert payload["scope"] == "single-file"
    assert payload["recommended_mode"] == "chat_direct"


def test_scope_estimate_in_global_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C1 (S3.5): global_history.db contains scope_estimate_json after chat run."""
    from fa.cli import _cmd_run
    from fa.inner_loop.global_history import GlobalHistoryStore

    config = tmp_path / "models.yaml"
    chat_models_yaml = """\
chat:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: TEST_FA_RUN_KEY
"""
    config.write_text(chat_models_yaml, encoding="utf-8")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    transport = _CapturingTransport()
    args = build_parser().parse_args(
        ["run", "-r", "chat", "--config", str(config), "--workspace", str(tmp_path), "refactor auth module"]
    )

    code = _cmd_run(args, transport=transport, secrets=_TEST_SECRETS)
    assert code == 0

    # Read global_history.db
    gh_path = home / ".fa" / "global_history.db"
    assert gh_path.exists(), f"global_history.db not found at {gh_path}"

    store = GlobalHistoryStore(db_path=gh_path)
    rows = store.read_all()
    assert len(rows) >= 1, "Expected at least one row in global_history"

    row = rows[0]
    scope_json = row.get("scope_estimate_json", "{}")
    scope = json.loads(scope_json)
    # "refactor" → L3 keyword → difficulty=3, mode=workflow_linear
    # "auth" → security keyword → boost, but L3 already at max
    assert scope.get("difficulty") == 3, f"Expected difficulty=3 for 'refactor auth module', got {scope}"
    assert scope.get("recommended_mode") == "workflow_linear"
