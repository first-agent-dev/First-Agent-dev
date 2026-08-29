"""RK8 (S5) — `fa workflow` rejects roles that are not pipeline stages.

Before this guard, ``--roles planner,chat,eval`` and even ``--roles bogus_role``
ran happily: cli.py split ``--roles`` on commas with no membership test, and
``status_for_role()`` silently maps an unknown role to 'CODING', so nothing
downstream ever objected.

The `chat` case is the one with teeth. A chat stage builds its own
``invoke_workflow`` tool and could recurse into a fresh workflow; S4b's
re-entrancy guard is thread-local and stages run in separate call frames, so it
cannot see that happen. The CLI boundary is the only place that can.
"""

from __future__ import annotations

import io
from contextlib import redirect_stderr
from pathlib import Path

import pytest

from fa.cli import _cmd_workflow, build_parser
from fa.inner_loop.workflow_controller import WORKFLOW_STAGE_ROLES


def _run_workflow_cli(roles: str) -> tuple[int, str]:
    """Invoke `fa workflow <roles> <task>` and capture (exit_code, stderr)."""
    args = build_parser().parse_args(["workflow", roles, "a task"])
    err = io.StringIO()
    with redirect_stderr(err):
        code = _cmd_workflow(args)
    return code, err.getvalue()


def test_rk8_chat_rejected_as_stage_role() -> None:
    """KILL-CHECK anchor: `chat` is refused as a workflow stage.

    This test binds to the ROLE, not merely to the presence of some check —
    adding "chat" to WORKFLOW_STAGE_ROLES must fail it.
    """
    code, err = _run_workflow_cli("planner,chat,eval")
    assert code == 2
    assert "chat" in err
    assert "unsupported stage role" in err


def test_rk8_chat_alone_rejected() -> None:
    """A single-role chat pipeline is the most direct recursion route.

    Asserts the SPECIFIC rejection message, not just exit 2. Verified by
    mutation: with the allowlist check deleted this command still exits 2 and
    still prints "chat" — because workspace bootstrap fails later and echoes
    the role — so an oracle of ``code == 2 and "chat" in err`` passes whether
    or not the guard exists.
    """
    code, err = _run_workflow_cli("chat")
    assert code == 2
    assert "unsupported stage role" in err, "must be REJECTED, not merely fail later"


def test_rk8_unknown_role_rejected() -> None:
    """A typo is refused rather than silently treated as a coder stage.

    Same discrimination concern as the chat case: the message, not the code.
    """
    code, err = _run_workflow_cli("bogus_role")
    assert code == 2
    assert "unsupported stage role" in err
    assert "bogus_role" in err


def test_rk8_error_names_the_permitted_set() -> None:
    """The operator is told what IS allowed, not just what is not."""
    _, err = _run_workflow_cli("researcher,coder")
    assert "researcher" in err
    for allowed in ("planner", "coder", "eval"):
        assert allowed in err


def test_rk8_reports_every_offending_role() -> None:
    """Two bad roles produce two names, so one fix-and-retry cycle suffices."""
    _, err = _run_workflow_cli("chat,researcher")
    assert "chat" in err
    assert "researcher" in err


def test_rk8_chat_is_not_in_the_allowlist() -> None:
    """The constant itself is the policy statement; assert it directly."""
    assert "chat" not in WORKFLOW_STAGE_ROLES
    assert WORKFLOW_STAGE_ROLES == frozenset({"planner", "coder", "eval"})


@pytest.mark.parametrize("roles", ["planner,coder,eval", "coder,eval", "planner"])
def test_rk8_valid_pipelines_pass_validation(roles: str) -> None:
    """Regression fence: legitimate role lists must clear the new check.

    They fail later on workspace bootstrap in this bare environment, which is
    itself the proof — reaching bootstrap means validation let them through.
    `coder,eval` is included because D4 made that planner-less list the
    supported replacement for the removed `repair` mode.
    """
    _, err = _run_workflow_cli(roles)
    assert "unsupported stage role" not in err


def test_rk8_validation_precedes_run_id_allocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rejected invocation must leave no session artifacts behind.

    Ordering matters: validating after run_id allocation would litter state for
    a command that never ran.
    """
    state_root = tmp_path / "state"
    monkeypatch.setenv("FA_STATE_ROOT", str(state_root))
    monkeypatch.chdir(tmp_path)

    code, _ = _run_workflow_cli("chat")
    assert code == 2
    session_dirs = list(tmp_path.glob("session-*")) + list(tmp_path.glob(".fa/**/session-*"))
    assert not session_dirs, f"rejected run left state behind: {session_dirs}"
    if state_root.exists():
        assert not list(state_root.glob("session-log/*"))
