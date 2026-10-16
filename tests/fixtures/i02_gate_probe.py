"""Q69 leaf C1 bank: real workflow, no FUNCTIONAL contracts in its own plan.

The constructed outer plan runs THIS WHOLE FILE under each of its nine kills.
Its deterministic subject cannot recursively boot another verification workflow.
The normative SLICE6 TESTS path remains tests/test_verify_gate_live.py for all 16 kills.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from fa import feature_flags
from fa.cli import _cmd_run
from fa.inner_loop.workflow_artifacts import load_eval_report
from fa.inner_loop.workflow_controller import run_workflow, workflow_artifact_paths
from fa.providers import ProviderChain, SecretStore
from fa.providers.base import RequestInfo, ResponseInfo
from tests.test_verify_gate_live import _EVAL_FINAL_TEXT, _ROLE_YAML


def test_real_composition_without_recursive_contracts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    (workspace / "tests").mkdir(parents=True)
    shutil.copy2(root / "tests/fixtures/i02_gate_subject.py", workspace / "tests/test_subject.py")
    (workspace / ".venv").symlink_to(root / ".venv", target_is_directory=True)
    state = tmp_path / "state"
    monkeypatch.setenv("FA_STATE_ROOT", str(state))
    monkeypatch.delenv("FA_EGRESS_PROXY_URL", raising=False)
    monkeypatch.delenv("FA_PROXY_TOKEN_FILE", raising=False)
    flags = tmp_path / "flags.yaml"
    flags.write_text("feature_flags:\n  workflow:\n    verify_gate:\n      mode: enforce\n")
    monkeypatch.setattr(feature_flags, "DEFAULT_CONFIG_PATH", flags)
    config = workspace / "models.yaml"
    config.write_text("".join(_ROLE_YAML.format(role=r) for r in ("planner", "coder", "eval")))
    plan = workspace / "plan.md"
    marker = workspace / "once.txt"
    plan.write_text(
        "Plan-ID: PLAN-i02-leaf\n\n```verify\n"
        "python -c \"from pathlib import Path; Path('once.txt').open('a').write('once\\n'); raise SystemExit(7)\"\n"
        "```\n\n## SLICE1: first owner\nCONTRACTS:\n  CT1 [CONSTRAINT]: first ownership.\n"
        "TESTS: tests/test_subject.py\n```verify\npython -c \"print('first-owner')\"\n```\n\n"
        "## SLICE2: second owner\nCONTRACTS:\n  CT2 [CONSTRAINT]: second ownership.\n"
        "TESTS: tests/test_subject.py\n```verify\npython -c \"print('second-owner')\"\n```\n"
    )
    roles: list[str] = []
    eval_messages: list[str] = []

    def provider(
        chain: ProviderChain, request: RequestInfo, *, logical_call_id: str | None = None
    ) -> tuple[ResponseInfo, str, list[Any]]:
        role = chain.config.role
        roles.append(role)
        if role == "eval":
            eval_messages.append(str(request.messages))
        return ResponseInfo(_EVAL_FINAL_TEXT if role == "eval" else "done", 1, 1, "stop"), logical_call_id or "leaf", []

    monkeypatch.setattr(ProviderChain, "request", provider)
    code, terminal = run_workflow(
        roles=["planner", "coder"],
        task="test ownership",
        per_role_task={},
        mode="linear",
        max_repairs=0,
        max_replans=0,
        run_id="i02-leaf",
        config=config,
        workspace=workspace,
        max_turns=1,
        output_mode="quiet",
        run_stage_fn=_cmd_run,
        secrets=SecretStore({"K": "sk-test-leaf"}),
        plan_path=plan,
    )
    assert code == 1 and terminal is not None and terminal.status == "REPAIR_REQUIRED"
    assert terminal.judged is True and terminal.last_route_decision == "return_to_coder"
    assert roles == ["planner", "coder", "eval"]
    paths = workflow_artifact_paths("i02-leaf")
    baseline = json.loads(paths.verify_baseline.read_text())
    assert baseline["run_id"] == "i02-leaf" and set(baseline["slices"]) == {"SLICE1", "SLICE2"}
    assert all(row["nodeids"] for row in baseline["slices"].values())
    verification = json.loads(paths.verification.read_text())["attempts"][0]
    assert verification["mode"] == "enforce" and verification["blocking"] is True
    assert len(verification["plan_commands"]) == 1
    assert verification["plan_commands"][0]["exit_code"] == 7
    first, second = verification["slices"]
    assert first["slice_id"] == "SLICE1" and second["slice_id"] == "SLICE2"
    assert len(first["commands"]) == len(second["commands"]) == 1
    assert "first-owner" in first["commands"][0]["stdout_tail"]
    assert "second-owner" in second["commands"][0]["stdout_tail"]
    assert "second-owner" not in first["commands"][0]["command"]
    assert "first-owner" not in second["commands"][0]["command"]
    assert marker.read_text() == "once\n"
    report = load_eval_report(paths.eval_report)
    assert report is not None and report.verdict == "PASS" and report.route_decision == "complete"
    assert "Harness verify gate (mode=enforce" in eval_messages[0]
    assert "Plan command: outcome=fail, exit_code=7" in eval_messages[0]
    assert "SLICE1" in eval_messages[0] and "SLICE2" in eval_messages[0]
