"""S7 — correlation joins across the trace (parent Step S7 Do #8).

Do #8 asks to *"verify correlation joins across ``run_id``, event ID, tool call
ID, and provider ``logical_call_id``; document any intentional non-join."*

Why this needs its own test rather than four field assertions
-------------------------------------------------------------
Each key is individually present in source — preflight found them at
``state.py`` (``run_id``, ``event_id``, ``tool_call_id``) and
``providers/chain.py:302`` (``logical_call_id``). What was never verified is
that they *join*: that an operator holding a run id can walk to the provider
attempt and then to the captured body without a broken link. A field that
exists but never correlates is worse than a missing one, because it looks like
evidence.

The chain this pins, measured on a real ``_cmd_run`` before being asserted:

    run_id ──> event_log rows (all share it)
            └> provider_attempt / llm_call rows
                 └> content["logical_call_id"]  (SAME uuid on both)
                      └> llm_bodies.jsonl row with that logical_call_id

Intentional non-joins, documented per Do #8:

* ``tool_call_id`` is **empty** on non-tool rows (``user_msg``, ``llm_call``,
  ``usage``, …). It correlates a tool call with its result, so it is absent by
  design where there is no tool call — not a broken link.
* body rows carry ``logical_call_id`` but **no** ``event_id``: the body file is
  keyed on the provider call, and one provider call can span several attempts.
  The join goes through ``logical_call_id``, deliberately.

Test class: C2 (shipped ``_cmd_run``), oracle = event kind + fields, which is
the top of the tests-writing ranked-oracle list.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from fa.cli import _cmd_run
from tests.test_cli import (
    _FAKE_MODELS_YAML,
    _TEST_SECRETS,
    _make_run_args,
    _ScriptedTransport,
    _stop_body,
)

_RUN_ID = "s7-corr"


@pytest.fixture
def correlated_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    """Drive one real run with body capture ON; return (home, session_id)."""
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    monkeypatch.setenv("TEST_FA_RUN_KEY", "sk-test-x")
    monkeypatch.setenv("FA_DEBUG_LLM_BODIES", "1")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    args = _make_run_args(workspace=tmp_path, config=config, run_id=_RUN_ID)
    args.session_id = None
    args.resume = False
    args.output_mode = "quiet"
    args.detail = "standard"
    args.no_color = True

    assert _cmd_run(args, transport=_ScriptedTransport([_stop_body("ok")]), secrets=_TEST_SECRETS) == 0

    manifest = sorted((home / ".fa" / "sessions").glob("*/manifest.json"))[0]
    session_id: str = json.loads(manifest.read_text(encoding="utf-8"))["session_id"]
    return home, session_id


def _rows(home: Path, session_id: str) -> list[dict[str, object]]:
    con = sqlite3.connect(home / ".fa" / "sessions" / session_id / "session.db")
    con.row_factory = sqlite3.Row
    return [dict(r) for r in con.execute("SELECT * FROM event_log ORDER BY event_id")]


def test_every_trace_row_carries_the_run_and_session_identity(
    correlated_run: tuple[Path, str],
) -> None:
    """C2: the outermost join key must be present on every row.

    Kill-check: drop ``run_id=self.run_id`` from the ``TraceEvent`` construction
    in ``EventLog.append`` → this fails.
    """
    home, session_id = correlated_run
    rows = _rows(home, session_id)

    assert rows, "the run persisted no events"
    assert {str(r["run_id"]) for r in rows} == {_RUN_ID}
    assert {str(r["session_id"]) for r in rows} == {session_id}
    assert all(str(r["event_id"]) for r in rows), "an event was persisted without an event_id"


def test_event_ids_are_unique_and_ordered_within_the_run(
    correlated_run: tuple[Path, str],
) -> None:
    """C2: ``event_id`` must be a usable primary correlation key.

    Uniqueness is S5's guarantee; this asserts it survives at the CLI root,
    which is the level an operator actually debugs from.
    """
    home, session_id = correlated_run
    ids = [str(r["event_id"]) for r in _rows(home, session_id)]

    assert len(ids) == len(set(ids)), f"duplicate event_id within one run: {ids}"
    assert ids == sorted(ids), "event ids are not monotonically ordered within the run"


def test_logical_call_id_joins_the_trace_to_the_captured_body(
    correlated_run: tuple[Path, str],
) -> None:
    """C2 (the join Do #8 exists for): trace row ─logical_call_id─> body row.

    This is the link that makes a captured body attributable. Without it the
    body file is an orphan blob: present, but not evidence *about* any
    particular provider attempt.

    Kill-check: stop threading ``logical_call_id`` into the ``provider_attempt``
    content (``coder_loop.py:1204``) → the intersection below is empty.
    """
    home, session_id = correlated_run
    rows = _rows(home, session_id)

    trace_ids: set[str] = set()
    for row in rows:
        raw = row.get("content")
        content = json.loads(str(raw)) if raw else {}
        if isinstance(content, dict) and content.get("logical_call_id"):
            trace_ids.add(str(content["logical_call_id"]))

    assert trace_ids, "no trace row carried a logical_call_id"

    body_path = home / ".fa" / "session-log" / _RUN_ID / "llm_bodies.jsonl"
    assert body_path.exists(), "body capture was enabled but no body file was written"
    body_ids = {
        str(json.loads(line)["logical_call_id"])
        for line in body_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }

    assert body_ids, "the body file holds no logical_call_id"
    assert body_ids <= trace_ids, (
        f"body rows reference provider calls absent from the trace: {sorted(body_ids - trace_ids)}"
    )


def test_one_provider_call_correlates_its_attempt_and_call_rows(
    correlated_run: tuple[Path, str],
) -> None:
    """C2: the same ``logical_call_id`` spans ``provider_attempt`` and ``llm_call``.

    Measured on a real run before being asserted: both rows carry the *same*
    uuid, which is what lets an operator reconstruct "this attempt produced
    this call". Asserting per-kind rather than in aggregate, so a regression
    that drops the id from one kind cannot hide behind the other.
    """
    home, session_id = correlated_run
    by_kind: dict[str, set[str]] = {}
    for row in _rows(home, session_id):
        raw = row.get("content")
        content = json.loads(str(raw)) if raw else {}
        if isinstance(content, dict) and content.get("logical_call_id"):
            by_kind.setdefault(str(row["kind"]), set()).add(str(content["logical_call_id"]))

    assert "provider_attempt" in by_kind, "no provider_attempt row carried a logical_call_id"
    assert "llm_call" in by_kind, "no llm_call row carried a logical_call_id"
    assert by_kind["provider_attempt"] == by_kind["llm_call"], (
        f"attempt and call rows disagree on the provider call id: {by_kind}"
    )


def test_documented_non_join_tool_call_id_is_empty_without_tool_calls(
    correlated_run: tuple[Path, str],
) -> None:
    """C2: the *documented* non-join, made executable rather than assumed.

    ``tool_call_id`` correlates a tool call with its result, so on a run with no
    tool calls it is empty everywhere. Do #8 asks for intentional non-joins to
    be documented; a characterisation test is stronger than a sentence, because
    it fails if the field silently starts carrying something else.
    """
    home, session_id = correlated_run
    rows = _rows(home, session_id)

    kinds = {str(r["kind"]) for r in rows}
    assert "tool_call" not in kinds, "fixture assumption broken: this run made a tool call"
    assert all(str(r["tool_call_id"]) == "" for r in rows), "tool_call_id is populated on a run that made no tool calls"
