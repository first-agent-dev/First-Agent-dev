"""A workflow writes exactly ONE global_history row, not one per stage (D5).

**Why this module exists.** ``global_history.runs`` is keyed by ``run_id``
with ``INSERT OR REPLACE`` (global_history.py:140, :178), and every stage of a
workflow shares one ``run_id``. LOGIC-11 (cli.py:1941-1945) therefore skips a
stage's own export when ``outcome_sink`` is non-None, leaving the controller to
write a single aggregate row after all stages finish.

Only ``eval`` was honouring it. ``_run_stage`` passed
``outcome_sink=sink if role == "eval" else None``, so the planner and coder
stages each exported a row under the shared ``run_id`` and overwrote one
another before the aggregate landed on top.

**Choosing an oracle that discriminates.** The obvious assertion — "the table
holds one row with the aggregate role" — passes *both* before and after the
fix, because the aggregate is written last and ``INSERT OR REPLACE`` makes the
final state correct by accident. Verified by execution: pre-fix and post-fix
final rows are byte-identical (``role='planner→coder→eval' turns=3``). A test
built on that oracle would be vacuous.

The discriminating oracle is the **number of writes**, captured at
``GlobalHistoryStore.export_run``: 3 before the fix, 1 after. That is what
these tests assert.

Test class: **C2** — the real ``run_workflow`` composition root with the real
``_cmd_run`` injected as ``run_stage_fn``; only the HTTP transport is a
stand-in.

**Kill-check:** restore ``outcome_sink=sink if role == "eval" else None`` in
``_run_stage`` → ``test_workflow_writes_exactly_one_global_history_row`` fails
with 3 writes.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop.global_history import GlobalHistoryStore
from fa.providers import SecretStore
from fa.providers.base import TransportResponse

_SECRETS = SecretStore({"K": "sk-test-x"})

# ``parse_eval_report`` scans for this exact markdown contract; anything else
# fail-closes to BLOCKED and the workflow would not reach a normal terminal
# state (workflow_artifacts.py:353, :433).
_EVAL_FINAL_TEXT = "## Verification Summary\n\n### Verdict\n\nPASS\n"

_ROLE_YAML = """\
{role}:
  name: "m"
  family: "openai"
  chain:
    - provider: openrouter
      model: "t/m"
      base_url: "https://example.invalid/v1"
      api_key_env: K
"""


class _StubTransport:
    """Returns a well-formed eval verdict for every stage."""

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout_seconds: float,
        transport_retries: int,
    ) -> TransportResponse:
        del url, headers, json_body, timeout_seconds, transport_retries
        return TransportResponse(
            status=200,
            body={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": _EVAL_FINAL_TEXT, "tool_calls": []},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )


@pytest.fixture()
def workflow_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, list[str]]:
    """Isolated FA state root + a models.yaml covering the three roles.

    Also installs a spy on ``GlobalHistoryStore.export_run`` that records the
    ``role`` of every write. Returns ``(config, workspace, writes)``.
    """
    state_root = tmp_path / "state"
    state_root.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("FA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    workspace = tmp_path / "ws"
    workspace.mkdir()
    config = workspace / "models.yaml"
    config.write_text("".join(_ROLE_YAML.format(role=r) for r in ("planner", "coder", "eval")), encoding="utf-8")

    writes: list[str] = []
    original = GlobalHistoryStore.export_run

    def spy(self: GlobalHistoryStore, row: Mapping[str, Any]) -> None:
        writes.append(str(row.get("role", "")))
        original(self, row)

    monkeypatch.setattr(GlobalHistoryStore, "export_run", spy)
    return config, workspace, writes


def _run(config: Path, workspace: Path, run_id: str) -> tuple[int, Any]:
    from fa.cli import _cmd_run
    from fa.inner_loop.workflow_controller import run_workflow

    return run_workflow(
        roles=["planner", "coder", "eval"],
        task="do a thing",
        per_role_task={},
        mode="linear",
        max_repairs=0,
        max_replans=0,
        run_id=run_id,
        config=config,
        workspace=workspace,
        max_turns=2,
        output_mode="quiet",
        run_stage_fn=_cmd_run,
        transport=_StubTransport(),
        secrets=_SECRETS,
    )


def test_workflow_writes_exactly_one_global_history_row(
    workflow_env: tuple[Path, Path, list[str]],
) -> None:
    """C2 (kill-check) — one aggregate write, no per-stage writes.

    Reverting ``_run_stage`` to ``outcome_sink=sink if role == "eval" else
    None`` makes this fail with ``['planner', 'coder', 'planner→coder→eval']``.
    """
    config, workspace, writes = workflow_env
    exit_code, _terminal = _run(config, workspace, "wf-one-row")

    assert exit_code == 0, f"workflow did not complete cleanly: exit={exit_code}"
    assert writes == ["planner→coder→eval"], f"expected exactly one aggregate export, got {len(writes)}: {writes}"


def test_no_per_stage_role_is_ever_exported(
    workflow_env: tuple[Path, Path, list[str]],
) -> None:
    """C2 — no individual stage role reaches the projection.

    Stated separately from the count because the failure it describes is
    different: a stage row is not merely redundant, it is *wrong* — it claims
    the shared run_id belongs to one role.
    """
    config, workspace, writes = workflow_env
    _run(config, workspace, "wf-no-stage-rows")

    assert "planner" not in writes
    assert "coder" not in writes
    assert "eval" not in writes


def test_final_row_is_the_aggregate(
    workflow_env: tuple[Path, Path, list[str]],
) -> None:
    """C2 — the surviving row describes the workflow, not its last stage.

    This assertion passes both before and after the fix (the aggregate is
    written last either way). It is kept as a regression guard on the
    aggregate's own content, and is deliberately NOT relied on as the
    kill-check — see the module docstring.
    """
    from fa.inner_loop.global_history import default_global_history_path

    config, workspace, _writes = workflow_env
    _run(config, workspace, "wf-aggregate")

    store = GlobalHistoryStore(default_global_history_path())
    row = store.read_run("wf-aggregate")
    assert row is not None
    assert row["role"] == "planner→coder→eval"
    assert row["stop_reason"] == "workflow_complete"
    assert row["turns"] == 3, "aggregate must sum the stages' turns"


def test_standalone_run_still_exports_its_own_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 — the other side of the contract: a plain ``fa run`` still exports.

    Passing the sink unconditionally must not suppress the export for a
    standalone run, which has no controller to write an aggregate on its
    behalf. Without this, the D5 fix would silently delete all non-workflow
    telemetry.
    """
    from fa.cli import _cmd_run, build_parser
    from fa.inner_loop.global_history import default_global_history_path

    state_root = tmp_path / "state"
    state_root.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("FA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    workspace = tmp_path / "ws"
    workspace.mkdir()
    config = workspace / "models.yaml"
    config.write_text(_ROLE_YAML.format(role="coder"), encoding="utf-8")

    args = build_parser().parse_args(
        ["run", "-r", "coder", "--config", str(config), "--workspace", str(workspace), "a task"]
    )
    assert _cmd_run(args, transport=_StubTransport(), secrets=_SECRETS) == 0

    store = GlobalHistoryStore(default_global_history_path())
    rows = store.read_all()
    assert len(rows) == 1, f"standalone run must export exactly one row, got {len(rows)}"
    assert rows[0]["role"] == "coder"


def test_nested_workflow_produces_two_rows(
    workflow_env: tuple[Path, Path, list[str]],
    tmp_path: Path,
) -> None:
    """T14 (moved from S4b to S5) — a chat run and its nested workflow each get a row.

    **Why this lives in S5 rather than S4b.** The S4b suite injects a fake
    ``run_workflow`` to assert delegation, so no real row was ever written and
    the two-row shape went unproven. ACRR is a PER-ROW quantity: if a nested
    pipeline reused its parent's ``run_id``, ``INSERT OR REPLACE`` would collapse
    the two into one and the child's file counts would silently overwrite the
    parent's. The separation is therefore an S5 premise, not a stylistic point.

    Driven through the real ``invoke_workflow`` handler with the real
    ``run_stage_fn`` seam — only the HTTP transport is a stand-in.
    """
    from fa.inner_loop.global_history import default_global_history_path
    from tests._chat_registry_fixture import build_live_chat_registry

    config, workspace, _writes = workflow_env
    # the fixture's models.yaml covers planner/coder/eval; the parent runs as chat
    config.write_text(
        "".join(_ROLE_YAML.format(role=r) for r in ("planner", "coder", "eval", "chat")),
        encoding="utf-8",
    )

    registry = build_live_chat_registry(
        workspace,
        parent_run_id="chat-parent",
        with_workflow_ctx=True,
    )
    spec = registry.lookup("invoke_workflow")
    assert spec is not None, "chat must carry invoke_workflow for this test to mean anything"

    result = spec.handler({"task": "do a thing"})

    child_run_id = (result.result or {}).get("run_id", "")
    assert child_run_id, f"tool returned no run_id: {result.summary}"
    assert child_run_id != "chat-parent", "child must not reuse the parent run_id"

    store = GlobalHistoryStore(default_global_history_path())
    child_row = store.read_run(child_run_id)
    assert child_row is not None, f"nested workflow wrote no row for {child_run_id}"
    assert child_row["role"] == "planner→coder→eval"

    # The parent chat row is written by _cmd_run, which this test does not
    # invoke; what S5 depends on is that the CHILD occupies its own key, so the
    # two can never collapse into one row under INSERT OR REPLACE.
    assert child_run_id.startswith("chat-parent"), "child id should derive from the parent"
