"""S9 — stats and derived projections.

Plan: ``worklogs/implementation-plans/PLAN-cli-trace-S9-stats-projections.md``
(v1-reviewed).

**Test-class labelling** (tests-writing skill §10 — every test declares its
class so an unpaired C0/C0p cannot hide):

* **C2** — root is the shipped ``_cmd_run`` / ``_cmd_stats``; oracle is a
  durable artifact (``global_history.runs`` row, session authority DB) or an
  exit code. These carry the producer kill-checks.
* **C0p** — ``_parse_since`` over a table of inputs. Pure policy, and
  **paired** with the C2 call-site tests below it, never standalone.

**Oracle ranking** (plan §6): DB/FS effect > exit code > call trajectory >
prose. No test here uses rendered text as its primary oracle.

**Fixture honesty.** ``_run_args`` (not ``_make_run_args``) is used for every
run: ``_make_run_args`` predates the session selector, so a run built from it
takes the legacy path and writes no ``sessions/<id>/manifest.json``. Measured
during preflight — the first probe failed on exactly this.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from fa.cli import _cmd_run, _cmd_stats
from fa.stats import parse_session_db
from tests.test_cli import (
    _FAKE_MODELS_YAML,
    _TEST_SECRETS,
    _ScriptedTransport,
    _stop_body,
)
from tests.test_s7_cli_run_paths import _run_args


def _stats_args(**overrides: Any) -> argparse.Namespace:
    """Every attribute ``_cmd_stats`` reads, with sane defaults.

    The seven names were AST-extracted from ``_cmd_stats`` during plan review
    rather than copied from an existing test: the two existing examples
    disagree (``test_cli.py`` sets ``session_id``, ``test_stats_global_wiring.py``
    omits it), so hand-rolling a Namespace per test would bake that
    inconsistency in. One helper means a future attribute breaks in one place.
    """
    base: dict[str, Any] = {
        "dead_zones": False,
        "global_history": False,
        "output": "json",
        "run_id": None,
        "session_id": None,
        "since": None,
        "workspace": Path(),
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _fa_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Isolated ``$HOME`` plus a models config. Returns ``(config, home)``."""
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return config, home


def _do_run(tmp_path: Path, config: Path, run_id: str, **overrides: Any) -> int:
    """One real ``fa run`` through the shipped command, scripted transport.

    ``overrides`` forwards to ``_run_args`` — notably ``session_id=<id>`` to
    *attach* to an existing session. A second run in the same workspace
    **must** attach: creating a second session over an owned workspace is
    refused by the S5 reverse-ownership guard with
    ``workspace_already_owned`` (exit 2). Measured while writing this module;
    the same trap caught S7.
    """
    args = _run_args(tmp_path, config, run_id, **overrides)
    return _cmd_run(args, transport=_ScriptedTransport([_stop_body("ok")]), secrets=_TEST_SECRETS)


def _session_id_of(home: Path) -> str:
    manifests = sorted((home / ".fa" / "sessions").glob("*/manifest.json"))
    assert manifests, "no session manifest written; the run took the legacy path"
    return str(json.loads(manifests[0].read_text(encoding="utf-8"))["session_id"])


def _gh_row(home: Path, run_id: str) -> dict[str, Any]:
    db = home / ".fa" / "global_history.db"
    assert db.is_file(), f"no global_history.db at {db}"
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in con.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))]
    finally:
        con.close()
    assert len(rows) == 1, f"expected exactly one row for {run_id!r}, got {len(rows)}"
    return rows[0]


# ---------------------------------------------------------------------------
# CT5 / G5 — authority and projection agree
# ---------------------------------------------------------------------------


def test_s9_authority_and_projection_agree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S9.1 / CT5): the derived row matches the authority for one run.

    This is the parent's first exit criterion, which until now rested on a
    one-off manual probe.

    Oracle: ``global_history.runs`` fields vs ``parse_session_db`` analytics.
    Kill-check target: remove ``export_session_to_global_history`` in
    ``_cmd_run`` — ``_gh_row``'s existence assertion fails.
    """
    config, home = _fa_home(tmp_path, monkeypatch)
    assert _do_run(tmp_path, config, "s9-agree") == 0

    session_id = _session_id_of(home)
    analytics = parse_session_db(
        home / ".fa" / "sessions" / session_id / "session.db",
        session_id=session_id,
        run_id="s9-agree",
    )
    assert analytics is not None
    row = _gh_row(home, "s9-agree")

    # Liveness witness FIRST: comparing two zeroes would agree vacuously.
    assert analytics.total_in > 0
    assert analytics.total_out > 0
    assert analytics.turns > 0

    assert analytics.total_in == row["input_tokens"]
    assert analytics.total_out == row["output_tokens"]
    assert analytics.turns == row["turns"]


# ---------------------------------------------------------------------------
# Do#1 — stats-side manifest guards (added after the S9.6 sweep found them
# unverified; see the module docstring note below)
# ---------------------------------------------------------------------------
#
# These two tests exist because the S9.6 statement-deletion sweep produced two
# SURVIVORS: deleting the ``manifest_path_mismatch`` and
# ``inactive-or-malformed`` guards inside ``_discover_stats_sources`` left the
# entire 2270-test suite green.
#
# The preflight had rated parent Do#1 as **L3** by reading those guards. They
# exist and they are correct — but ``_discover_stats_sources`` carries its own
# copies, independent of ``SessionManager``'s (``manager.py:144-164``), and
# stats never constructs a manager. So the existing
# ``test_session_manifest_guards.py`` coverage does not reach them.
#
# "The guard is present" is not "the guard is verified". Mutation testing is
# what turned a reading into a measurement.


def _seed_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_id: str) -> tuple[Path, Path]:
    """Produce one real session on disk. Returns ``(home, session_dir)``."""
    config, home = _fa_home(tmp_path, monkeypatch)
    assert _do_run(tmp_path, config, run_id) == 0
    session_dir = home / ".fa" / "sessions" / _session_id_of(home)
    return home, session_dir


def test_s9_discovery_rejects_manifest_pointing_elsewhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (Do#1): a manifest whose ``session_db_path`` is not the sibling DB is refused.

    Adversarial: rewrite the manifest to point at another file. Without the
    guard, ``fa stats`` would open and report on a database that does not
    belong to the session directory it was discovered in.

    Oracle: exit code 2 + the coded ``manifest_path_mismatch`` message.
    Kill-check target: the ``db_path != expected_db`` raise in
    ``_discover_stats_sources`` — **verified by sweep mutation S9-M4**, which
    survived before this test existed.
    """
    _home, session_dir = _seed_session(tmp_path, monkeypatch, "s9-mm")
    manifest_path = session_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    elsewhere = tmp_path / "not-my-session.db"
    elsewhere.write_bytes(b"")
    manifest["session_db_path"] = str(elsewhere)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert _cmd_stats(_stats_args(workspace=tmp_path)) == 2
    assert "manifest_path_mismatch" in capsys.readouterr().err


def test_s9_discovery_rejects_inactive_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (Do#1): a non-``active`` manifest is refused rather than silently included.

    Oracle: exit code 2 + ``manifest_corrupt``.
    Kill-check target: the ``manifest.get("status") != "active"`` raise —
    **verified by sweep mutation S9-M5**, which survived before this test.
    """
    _home, session_dir = _seed_session(tmp_path, monkeypatch, "s9-inactive")
    manifest_path = session_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    manifest["status"] = "closed"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert _cmd_stats(_stats_args(workspace=tmp_path)) == 2
    assert "manifest_corrupt" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# CT1 / CT2 / G1 — --since is validated, not silently misapplied
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # valid windows — unchanged by S9.2
        ("7d", 604800.0),
        ("24h", 86400.0),
        ("30m", 1800.0),
        ("  7D  ", 604800.0),
        ("7.5d", 648000.0),
        ("1e3h", 3600000.0),  # scientific notation: unusual, not wrong
        # rejected
        ("-5d", None),  # F6: was -432000.0, pushed the cutoff into the future
        ("0d", None),  # zero-width window is never intentional
        ("7", None),  # no suffix
        ("abc", None),
        ("", None),
        ("d", None),  # suffix with no number
    ],
)
def test_s9_parse_since_table(raw: str, expected: float | None) -> None:
    """C0p (S9.2 / CT1): the whole input surface of the duration parser.

    Paired with the C2 call-site tests below — a C0p on a pure helper proves
    the policy, never the wiring (tests-writing skill §10).

    Kill-check target: remove the ``seconds <= 0`` guard in ``_parse_since``;
    the ``-5d`` and ``0d`` rows fail.
    """
    from fa.cli import _parse_since

    assert _parse_since(raw) == expected


def test_s9_since_rejects_negative_with_usage_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S9.2 / CT2): an invalid --since is a usage error, not an empty result.

    Before S9.2 this returned **1** with ``no matching sessions found`` — the
    operator could not distinguish a typo from having no data. Exit **2** is
    the established usage-error code: argparse itself exits 2 on an unknown
    flag, and ``_cmd_stats`` already returns 2 for source errors.

    Oracle: exit code **exactly 2** plus the coded stderr message. Asserting
    merely ``!= 0`` would pass on the old behaviour, which returned 1 for the
    wrong reason.
    Kill-check target: remove the pre-dispatch guard in ``_cmd_stats``.
    """
    _config, _home = _fa_home(tmp_path, monkeypatch)
    args = _stats_args(since="-5d", workspace=tmp_path)

    assert _cmd_stats(args) == 2
    assert "invalid --since" in capsys.readouterr().err


def test_s9_global_history_since_rejects_negative(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S9.2 / CT2, P2): the same guard covers the --global-history branch.

    Path sensitivity: ``--since`` is consumed at two call sites. A single
    pre-dispatch guard must protect both, otherwise the projection branch
    keeps the old silent behaviour.
    """
    _config, _home = _fa_home(tmp_path, monkeypatch)
    args = _stats_args(since="-5d", global_history=True, workspace=tmp_path)

    assert _cmd_stats(args) == 2


def test_s9_valid_since_is_not_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S9.2, P3): a well-formed window still reaches the normal path.

    The liveness control for the two rejection tests above: without this, a
    guard that rejected *everything* would satisfy them both.

    Exit 1 (``no matching sessions``) is the correct outcome for an empty
    isolated ``$HOME`` — the point is that it is **not** 2, i.e. the input was
    accepted and the command proceeded to look.
    """
    _config, _home = _fa_home(tmp_path, monkeypatch)
    args = _stats_args(since="7d", workspace=tmp_path)

    assert _cmd_stats(args) != 2


def test_s9_run_id_precedence_over_since_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S9.2, P5 / Q39): ``--run-id`` still overrides ``--since``.

    Pins the deliberate decision recorded as Q39: when ``--run-id`` is given,
    ``--since`` is never consulted, so an invalid value is **not** an error.
    Arguably a silently-ignored flag is its own smell, but changing it is a
    broader behaviour change than F6 and would reject command lines that work
    today. Pinning it here makes the precedence visible and deliberate rather
    than incidental — and makes any future change a failing test, not a
    surprise.
    """
    _config, _home = _fa_home(tmp_path, monkeypatch)
    args = _stats_args(since="-5d", run_id="nope", workspace=tmp_path)

    # Not 2: the invalid --since is never parsed because --run-id wins.
    assert _cmd_stats(args) == 1


def test_s9_run_id_reuse_is_refused_so_reexport_cannot_occur(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S9.5 / CT5): the CLI cannot re-export a ``run_id``, so F5 is unreachable.

    **This test replaces the one the plan specified, because the plan's premise
    was wrong.** S9.5 assumed a ``run_id`` could be re-run and asked us to pin
    that ``created_at`` survives ``INSERT OR REPLACE``. Measured here: the
    second invocation is refused outright.

    * fresh run_id, no session         → exit 0
    * **same run_id, attached**        → exit 2 ``run_id_reused`` (``manager.py:394``)
    * new run_id, attached             → exit 0

    So ``export_run`` is called at most once per ``run_id`` through the CLI:
    ``created_at`` cannot be clobbered because the second export never happens.
    F5 is **unreachable**, not merely latent — the earlier "latent" probe
    called ``GlobalHistoryStore.export_run`` directly, bypassing the session
    manager that makes it impossible.

    Pinning the *guard* is the honest version of this test: it protects the
    real invariant (one export per run) instead of a scenario production
    forbids.

    Oracle: exit codes + the row count staying at 1.
    Kill-check target: remove the ``run_id_reused`` raise in
    ``SessionManager`` — the second run would succeed and this fails.
    """
    config, home = _fa_home(tmp_path, monkeypatch)
    assert _do_run(tmp_path, config, "s9-once") == 0
    first = _gh_row(home, "s9-once")
    session_id = _session_id_of(home)

    # Re-using the run id is refused even when correctly attached.
    assert _do_run(tmp_path, config, "s9-once", session_id=session_id) == 2

    # The projection row is untouched by the refused attempt.
    assert _gh_row(home, "s9-once") == first

    # Liveness control: a *different* run id on the same session does succeed,
    # proving exit 2 above came from run-id reuse and not from a broken
    # attach or an unusable workspace.
    assert _do_run(tmp_path, config, "s9-second", session_id=session_id) == 0
    assert _gh_row(home, "s9-second")["run_id"] == "s9-second"
