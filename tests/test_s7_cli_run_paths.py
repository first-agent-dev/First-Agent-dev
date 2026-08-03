"""S7 — direct ``fa run`` vertical slice: the paths S7.0 measured as ABSENT.

Scope discipline
----------------
S7.0 audited P1-P15 against the tree rather than assuming gaps. Most rows were
already covered at the CLI root by ``tests/test_cli.py`` — P1/P2/P3 by
``test_fa_run_session_manager_creates_and_attaches_with_fresh_run_ids:950``, and
matrix cells A/B/C by ``test_fa_run_debug_body_capture_follows_exact_env_gate:423``
(which already proves ``--detail debug`` is *not* the body-capture gate).

Duplicating those would add a second oracle for one behaviour — the exact
reasoning that produced the S6 matrix-E tautology. This file therefore covers
only what was measured missing:

* **P15 / matrix D** — quiet mode at the CLI root;
* **parent Do #9** — command-local state must not leak between two
  invocations in one process;
* **S7.5 / S4-F1** — ``inner-loop-smoke`` must not leave a session-less
  authority (Q28 option b).

Correlation joins (parent Do #8) live in ``tests/test_s7_correlation.py``.

Test classes: C2 (shipped ``_cmd_run`` / ``_cmd_inner_loop_smoke``) and C3
(adversarial identity write).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import pytest

from fa.cli import _cmd_inner_loop_smoke, _cmd_run
from fa.inner_loop.session_db import SessionDatabase, SessionDatabaseError
from tests._capabilities import requires_pty_backend
from tests.test_cli import (
    _FAKE_MODELS_YAML,
    _TEST_SECRETS,
    _make_run_args,
    _ScriptedTransport,
    _stop_body,
)


def _run_args(tmp_path: Path, config: Path, run_id: str, **overrides: object) -> argparse.Namespace:
    """A full ``fa run`` namespace, including the flags ``_make_run_args`` omits.

    ``_make_run_args`` predates the output flags, so ``_cmd_run`` reads them via
    ``getattr(..., default)``. Setting them explicitly is the flag-honesty rule:
    a matrix test must not depend on a getattr fallback for the value under test.
    """
    args = _make_run_args(workspace=tmp_path, config=config, run_id=run_id)
    args.session_id = None
    args.resume = False
    args.output_mode = "console"
    args.detail = "standard"
    args.no_color = False
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


@pytest.fixture
def cli_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("TEST_FA_RUN_KEY", "sk-test-x")
    monkeypatch.setenv("FA_DEBUG_LLM_BODIES", "0")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


# ---------------------------------------------------------------------------
# P15 / matrix D — quiet mode at the CLI root
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("output_mode", ["console", "quiet"], ids=["D-console", "D-quiet"])
def test_output_mode_never_suppresses_the_durable_trace(
    tmp_path: Path, cli_home: Path, output_mode: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (P15, matrix D): quiet silences the console, never the authority.

    The operator-facing risk is not "quiet prints too much" — it is a future
    change that implements quiet by *not emitting*, which would silence the
    durable trace too. Console silence must never mean trace silence, so both
    cells assert the DB rows and only the stderr expectation differs.
    """
    config = tmp_path / "models.yaml"
    run_id = f"s7-{output_mode}"
    args = _run_args(tmp_path, config, run_id, output_mode=output_mode)

    assert _cmd_run(args, transport=_ScriptedTransport([_stop_body("ok")]), secrets=_TEST_SECRETS) == 0
    captured = capsys.readouterr()

    manifests = sorted((cli_home / ".fa" / "sessions").glob("*/manifest.json"))
    session_id = json.loads(manifests[0].read_text(encoding="utf-8"))["session_id"]
    db = SessionDatabase.open_existing(cli_home / ".fa" / "sessions" / session_id / "session.db", session_id=session_id)
    rows = db.read_event_rows(run_id=run_id)
    assert rows, f"{output_mode}: the durable trace must be written regardless of output mode"

    if output_mode == "quiet":
        # S8.4 / I-38 revised this cell deliberately. Quiet's guarantee is a
        # clean **stdout** (so ``> result.txt`` is parseable), not a silent
        # stderr — S6 §Q23 already carved out listener-failure diagnostics for
        # the same reason. S8.4 moved the one-line human status there too, so
        # stderr now legitimately carries it while the live renderer stays off.
        #
        # The claim this cell defends is unchanged and asserted above: the
        # durable trace is written regardless of output mode. What is pinned
        # here is that quiet still suppresses the *live renderer* — the
        # multi-line per-turn progress — rather than that stderr is empty.
        assert "OK: stopped_by_llm" in captured.err
        assert "[turn " not in captured.err, f"quiet mode ran the live renderer: {captured.err[:200]!r}"
        assert captured.out == "ok\n", f"quiet mode must leave stdout as the payload: {captured.out!r}"
    else:
        assert captured.err != "", "console mode produced no live output at all"


# ---------------------------------------------------------------------------
# Parent Do #9 — invocation isolation
# ---------------------------------------------------------------------------


def test_two_runs_in_one_process_do_not_leak_session_state(tmp_path: Path, cli_home: Path) -> None:
    """C2 (parent Do #9): command-local state must not survive an invocation.

    Preflight found no ``os.environ`` writes in ``cli.py`` and a
    ``reset_current_session`` in ``drive_session``'s ``finally``
    (``coder_loop.py:384``), so this *looks* safe by inspection. It is tested
    anyway because the S6.5 session measured real cross-test contamination
    through that same contextvar — absence of writes is not proof of absence
    of leakage.

    Negative proof: delete the ``reset_current_session`` in that ``finally``
    and the ambient-session assertion below fails.
    """
    from fa.inner_loop.context import get_current_session

    config = tmp_path / "models.yaml"

    first = _run_args(tmp_path, config, "s7-iso-a", no_color=False)
    assert _cmd_run(first, transport=_ScriptedTransport([_stop_body("a")]), secrets=_TEST_SECRETS) == 0
    assert get_current_session() is None, "run A left an ambient SessionState behind"

    manifests = sorted((cli_home / ".fa" / "sessions").glob("*/manifest.json"))
    assert len(manifests) == 1
    session_id = json.loads(manifests[0].read_text(encoding="utf-8"))["session_id"]

    # Second invocation ATTACHES to the same session and differs in --no-color.
    # It must not inherit any state from run A beyond that explicit attach.
    #
    # Two sessions cannot share one workspace by design — S5's reverse-ownership
    # guard (`manager.py:196`, `workspace_already_owned`). Attaching is therefore
    # the realistic repeat-invocation shape, and it is also the stronger test:
    # both runs write into one authority, so a leak would be visible as rows
    # attributed to the wrong run.
    second = _run_args(tmp_path, config, "s7-iso-b", no_color=True, session_id=session_id)
    assert _cmd_run(second, transport=_ScriptedTransport([_stop_body("b")]), secrets=_TEST_SECRETS) == 0
    assert get_current_session() is None, "run B left an ambient SessionState behind"

    db = SessionDatabase.open_existing(manifests[0].parent / "session.db", session_id=session_id)
    run_ids = {str(row["run_id"]) for row in db.read_event_rows()}
    assert run_ids == {"s7-iso-a", "s7-iso-b"}, f"unexpected run ids in the authority: {run_ids}"

    for run_id in ("s7-iso-a", "s7-iso-b"):
        rows = db.read_event_rows(run_id=run_id)
        assert rows, f"{run_id} wrote no events"
        assert {str(r["run_id"]) for r in rows} == {run_id}, (
            f"run-scoped read for {run_id} returned rows from another invocation"
        )


# ---------------------------------------------------------------------------
# S7.5 / S4-F1 — the smoke command's authority (Q28 option b)
# ---------------------------------------------------------------------------


def _smoke(tmp_path: Path) -> int:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "in.txt").write_text("hello\n", encoding="utf-8")
    args = argparse.Namespace(workspace=workspace, input="in.txt", output="out.txt")
    return _cmd_inner_loop_smoke(args)


@requires_pty_backend
def test_smoke_creates_no_session_less_authority_at_the_fa_root(tmp_path: Path) -> None:
    """C2 (S4-F1): the misleading artifact is gone.

    ``<workspace>/.fa/session.db`` is indistinguishable from the real authority
    by name. Kill-check: drop ``session_db=session_db`` from the ``EventLog``
    call and this fails, because ``__post_init__`` defaults one back into
    existence at the old path.
    """
    assert _smoke(tmp_path) == 0
    assert not (tmp_path / "ws" / ".fa" / "session.db").exists(), (
        "inner-loop-smoke recreated the session-less authority at .fa/session.db"
    )


@requires_pty_backend
def test_smoke_authority_is_labelled_and_scoped(tmp_path: Path) -> None:
    """C2 (S4-F1 / Q28b): the smoke DB exists, is labelled, and is confined.

    Kill-check: remove ``session_id=_SMOKE_SESSION_ID`` from the
    ``SessionDatabase(...)`` call → the identity assertion fails.
    """
    assert _smoke(tmp_path) == 0

    db_path = tmp_path / "ws" / ".fa" / "smoke" / "session.db"
    assert db_path.exists(), "the labelled smoke authority was not created"

    rows = sqlite3.connect(db_path).execute("SELECT DISTINCT session_id FROM event_log").fetchall()
    assert rows, "the smoke run persisted no events"
    assert {r[0] for r in rows} == {"cli-smoke"}, (
        f"smoke events must carry a non-empty, labelled session_id; got {rows}"
    )


@requires_pty_backend
def test_smoke_authority_rejects_a_foreign_session_row(tmp_path: Path) -> None:
    """C3: the guards are live again — this is *why* the label matters.

    Before S7.5 the smoke DB had ``session_id == ''``. Every identity guard is
    written ``if self.session_id and ...``, so an empty value disabled them and
    the DB accepted rows stamped for any session (measured in the S7 plan §9).

    This asserts the consequence, not the field: a foreign-session write must
    now raise. Naming the session re-armed the guard by construction, so this
    test fails if the label is removed — no separate check was added.
    """
    assert _smoke(tmp_path) == 0
    db = SessionDatabase(tmp_path / "ws" / ".fa" / "smoke" / "session.db", session_id="cli-smoke")

    with pytest.raises(SessionDatabaseError) as exc:
        db.append_event_row_allocating(
            {
                "event_id": "",
                "ts": "2026-07-29T00:00:00Z",
                "run_id": "r",
                "session_id": "somebody-elses-session",
                "actor": "coder",
                "kind": "tool_call",
                "content": {},
                "tool_name": "",
                "tool_call_id": "",
                "parent_event_id": "",
                "harness_id": "h",
            }
        )
    assert exc.value.code == "session_db_identity_mismatch"


@requires_pty_backend
def test_smoke_still_reports_success_and_writes_its_output(tmp_path: Path) -> None:
    """C2 happy-path control for the two guard tests above.

    A fix that made the smoke command fail-closed on everything would satisfy
    the rejection test while destroying the command. Pin the purpose the module
    actually states: exercise the registry without an LLM provider.
    """
    assert _smoke(tmp_path) == 0
    assert (tmp_path / "ws" / "out.txt").exists(), "the smoke run did not perform its write step"
