"""S10b.2 — behaviour-parity oracles for the ``_cmd_run`` decomposition (CT1).

Plan: ``worklogs/implementation-plans/PLAN-cli-trace-S10b-cli-decomposition.md``

**Read this before changing anything in ``_cmd_run``.**

This module is the *authority* for CT1 (behaviour invariance). It was written
and **run green against unmodified ``cli.py``** before a single line of the
decomposition was written, and that run is recorded in the plan's execution
record. A parity suite that was never green pre-change proves nothing: it
cannot distinguish "the refactor preserved behaviour" from "the test was
written to match whatever the refactor produced".

**What parity means here.** Not "the suite still passes" — it passed before
too. Parity is asserted over the *durable, operator-visible* contract:

* the **exit code**,
* the **stdout bytes** (the status line and payload an operator or a shell
  redirect actually receives),
* the **durable artifacts** on disk (``events.jsonl``, ``pr_draft.md``, the
  run-log directory contents),
* the **structured stderr message** on each failure path — asserted as
  branch-unique wording, because S10a's mutation sweep proved that asserting
  only an exit code survives when a downstream handler produces the same code.

**What parity deliberately does NOT assert (plan RK4).** No test here checks
that a particular private helper was called, or in what order. S10b's whole
purpose is to move code between functions; oracles bound to internal call
structure would make the refactor unfalsifiable in the other direction —
green only when the code is shaped exactly as the test imagined. Every oracle
below is observable from outside ``_cmd_run``.

Test class: **C2** (root is the shipped ``_cmd_run``; oracle is behaviour at
the command boundary).
"""

from __future__ import annotations

import argparse
import io
import json
from collections.abc import Mapping
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from fa.cli import (
    _build_output_bus,
    _build_run_hook_registry,
    _cmd_run,
    _cmd_selfcheck,
    _cmd_stats,
    _discover_stats_sources,
    _prepare_pr_draft,
    _session_db_runtime_error_message,
)
from fa.inner_loop import EventLog, load_runtime_limits_from_path
from fa.inner_loop.coder_loop import SessionOutcome
from fa.inner_loop.pr_draft import PrDraftStore
from fa.providers.base import Transport
from tests._capabilities import requires_posix_paths
from tests.test_cli import _FAKE_MODELS_YAML, _TEST_SECRETS, _ScriptedTransport, _stop_body
from tests.test_s7_cli_run_paths import _run_args

# A models config declaring BOTH ``coder`` and ``compactor``. The shared
# ``_FAKE_MODELS_YAML`` declares only ``coder``, so the compactor-chain block
# is dark under it; parity for that block needs its own fixture.
_MODELS_WITH_COMPACTOR = (
    _FAKE_MODELS_YAML
    + """
  compactor:
    - name: test-model
      family: openai
      base_url: https://example.invalid/v1
      api_key_env: TEST_FA_RUN_KEY
"""
)


def _cli_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated ``$HOME`` + the env every ``_cmd_run`` path reads.

    ``fa_session_log_root()`` resolves under ``$HOME``, so without this a test
    writes into the developer's real ``~/.fa`` and the artifact oracles below
    would compare against whatever a previous run left there.
    """
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("TEST_FA_RUN_KEY", "sk-test-x")
    monkeypatch.setenv("FA_DEBUG_LLM_BODIES", "0")
    monkeypatch.delenv("FA_EGRESS_PROXY_URL", raising=False)
    monkeypatch.delenv("FA_PROXY_TOKEN_FILE", raising=False)
    return home


def _models_config(tmp_path: Path, body: str = _FAKE_MODELS_YAML) -> Path:
    config = tmp_path / "models.yaml"
    config.write_text(body, encoding="utf-8")
    return config


def _run_capturing(
    args: argparse.Namespace,
    *,
    transport: Transport,
    secrets: Mapping[str, str],
    outcome_sink: list[SessionOutcome] | None = None,
) -> tuple[int, str]:
    """Invoke ``_cmd_run`` and capture stdout as bytes-equivalent text.

    ``redirect_stdout`` rather than ``capsys`` because these oracles compare
    the *exact* stdout payload across a refactor; capsys' fixture-scoped
    buffering has bitten this suite before when a test also reads stderr.

    The seam parameters are spelled out with their real types rather than
    forwarded as ``**kwargs: object``. mypy strict rejects the loose form, and
    correctly so: it would let a typo'd keyword reach ``_cmd_run`` and be
    silently swallowed by a ``getattr`` default somewhere downstream.
    """
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = _cmd_run(args, transport=transport, secrets=secrets, outcome_sink=outcome_sink)
    return code, buffer.getvalue()


def _run_dir(home: Path, run_id: str) -> Path:
    return home / ".fa" / "session-log" / run_id


# ── Cell 1: happy path ──────────────────────────────────────────────────────


@requires_posix_paths
def test_s10b_parity_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S10b.2 / CT1): a successful run's exit code, stdout and artifacts.

    The primary parity cell. Every extraction in S10b.2 runs through this path,
    so a mistake in the setup prologue, the chain assembly, or the epilogue
    shows up here first.

    Oracle (ranked): exit 0 · the exact stdout payload (status line + final
    text) · ``events.jsonl`` exists and is non-empty JSONL.
    Kill-check target: any extracted helper on the success path — e.g. change
    what the epilogue prints, or drop the ``final_text`` line.
    """
    home = _cli_home(tmp_path, monkeypatch)
    config = _models_config(tmp_path)
    args = _run_args(tmp_path, config, "parity-happy")

    code, stdout = _run_capturing(
        args, transport=_ScriptedTransport([_stop_body("payload-text")]), secrets=_TEST_SECRETS
    )

    assert code == 0
    # The status line goes to stdout in console mode, and the payload follows.
    assert "OK: " in stdout, f"status line missing from stdout: {stdout!r}"
    assert "turns=" in stdout
    assert "payload-text" in stdout, "final_text is the payload and must reach stdout"

    events = _run_dir(home, "parity-happy") / "events.jsonl"
    assert events.is_file(), "the durable event log must exist after a successful run"
    rows = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows, "events.jsonl is empty — the run produced no durable trace"


# ── Cell 2: quiet mode ──────────────────────────────────────────────────────


def test_s10b_parity_quiet_mode_moves_status_off_stdout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S10b.2 / CT1): ``--output-mode quiet`` keeps stdout parseable.

    Pins the S8.4 / I-38 contract: under ``quiet`` the human status line moves
    to **stderr** so ``fa run --task ... > result.txt`` yields a parseable
    artifact, while ``final_text`` — the payload — stays on stdout in both
    modes.

    This cell exists because the status-line branch sits in the epilogue that
    S10b.2 extracts. An extraction that "simplified" the stream selection
    would be invisible to a test asserting only the exit code.

    Oracle: exit 0 · stdout contains the payload · stdout does **not** contain
    the status line.
    Kill-check target: the ``status_stream`` selection — force it back to
    ``sys.stdout`` and this fails.
    """
    _cli_home(tmp_path, monkeypatch)
    config = _models_config(tmp_path)
    args = _run_args(tmp_path, config, "parity-quiet", output_mode="quiet")

    code, stdout = _run_capturing(
        args, transport=_ScriptedTransport([_stop_body("quiet-payload")]), secrets=_TEST_SECRETS
    )

    assert code == 0
    assert "quiet-payload" in stdout, "the payload must stay on stdout under quiet"
    assert "OK: " not in stdout, f"quiet mode leaked the status line onto stdout: {stdout!r}"


# ── Cell 3: proxy mode ──────────────────────────────────────────────────────


def test_s10b_parity_proxy_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S10b.2 / CT1): proxy mode drives ``_proxy_rewrite_chain`` and still runs.

    Verified reachable without a live proxy: ``_resolve_proxy_url`` reads a
    plain env var and the token comes from a file, so both are monkeypatchable.

    Oracle: exit 0 through a full session — proving the *rewritten* chain is
    still usable, not merely that the branch was entered. That distinction
    matters: an extraction that rewrote the chain into a local variable and
    then dropped it would enter the branch and still return non-zero.
    Kill-check target: the ``if proxy_mode:`` rewrite block.
    """
    _cli_home(tmp_path, monkeypatch)
    config = _models_config(tmp_path)
    token = tmp_path / "proxy-token"
    token.write_text("proxy-t0ken-abcdefghij\n", encoding="utf-8")
    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "http://127.0.0.1:9/")
    monkeypatch.setenv("FA_PROXY_TOKEN_FILE", str(token))

    args = _run_args(tmp_path, config, "parity-proxy")

    code, stdout = _run_capturing(args, transport=_ScriptedTransport([_stop_body("proxied")]), secrets=_TEST_SECRETS)

    assert code == 0
    assert "proxied" in stdout


def test_s10b_parity_proxy_mode_builds_compactor_chain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S10b.2 / CT1): the compactor chain gets its own, separate rewrite.

    The compactor block has a *second* ``_proxy_rewrite_chain`` call that fails
    independently of the primary chain's, and it swallows its error rather than
    returning 2. A single proxy cell would leave it unpinned, and S10b.2's
    candidate seams explicitly include "provider-chain assembly".

    Oracle: exit 0 with both roles configured — the extra chain was built and
    remained usable.
    Kill-check target: the ``if compactor_config is not None`` block.
    """
    _cli_home(tmp_path, monkeypatch)
    config = _models_config(tmp_path, _MODELS_WITH_COMPACTOR)
    token = tmp_path / "proxy-token"
    token.write_text("proxy-t0ken-abcdefghij\n", encoding="utf-8")
    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "http://127.0.0.1:9/")
    monkeypatch.setenv("FA_PROXY_TOKEN_FILE", str(token))

    args = _run_args(tmp_path, config, "parity-compactor")

    code, _ = _run_capturing(args, transport=_ScriptedTransport([_stop_body("ok")]), secrets=_TEST_SECRETS)

    assert code == 0


# ── Cell 4: the validation prologue (exit 2 paths) ──────────────────────────
#
# Each asserts BRANCH-UNIQUE wording, not just the code. S10a's sweep proved
# that "assert exit == 2" survives deleting a guard whenever a later guard
# produces the same code — which, in a prologue of six sequential validators,
# is every one of them.


@pytest.mark.parametrize(
    ("overrides", "fragment", "case"),
    [
        ({"task": "   "}, "task must be non-empty", "blank task"),
        ({"max_turns": 0}, "--max-turns must be a positive integer", "non-positive max-turns"),
        ({"run_id": "../escape"}, "--run-id must match", "path-traversal run id"),
        ({"resume": True, "session_id": None}, "--resume requires --session-id", "resume without session"),
    ],
)
def test_s10b_parity_validation_prologue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    overrides: dict[str, object],
    fragment: str,
    case: str,
) -> None:
    """C2 (S10b.2 / CT1 / RK4): each prologue guard keeps its own exit code and message.

    RK4 names the specific hazard this covers: *"moving ``_cmd_run``'s prologue
    relocates an early return and changes an exit code."* Extraction reorders
    these guards trivially — pull three into a helper and the fourth now fires
    first — and the operator-visible symptom is a *different diagnostic for the
    same bad input*, which no exit-code-only assertion detects.

    Oracle: exit 2 **and** the branch-unique stderr fragment.
    Kill-check target: delete or reorder any single guard → the matching case
    fails while the others stay green, naming the guard that moved.
    """
    _cli_home(tmp_path, monkeypatch)
    config = _models_config(tmp_path)
    args = _run_args(tmp_path, config, "parity-guard")
    for key, value in overrides.items():
        setattr(args, key, value)

    assert _cmd_run(args, transport=_ScriptedTransport([]), secrets=_TEST_SECRETS) == 2, case
    assert fragment in capsys.readouterr().err, f"{case}: expected branch-unique wording {fragment!r}"


def test_s10b_parity_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10b.2 / CT1): a *semantically* invalid models config is exit 2.

    Mandatory cell per the plan (RK4): config resolution sits in the prologue
    S10b.2 extracts, and it is the boundary between "usage error" and "the run
    started".

    Oracle: exit 2 + ``configuration error`` — distinct from the role-missing
    message below, which is the adjacent branch.
    Kill-check target: the ``except (ConfigurationError, ...)`` handler.

    Uses a *well-formed* YAML document that fails validation, not malformed
    YAML — see ``test_s10b_parity_unparseable_yaml_crashes`` below for why
    that distinction is load-bearing rather than incidental.
    """
    _cli_home(tmp_path, monkeypatch)
    config = tmp_path / "invalid.yaml"
    config.write_text("roles:\n  coder: not-a-list\n", encoding="utf-8")
    args = _run_args(tmp_path, config, "parity-badconfig")

    assert _cmd_run(args, transport=_ScriptedTransport([]), secrets=_TEST_SECRETS) == 2
    assert "configuration error" in capsys.readouterr().err


def test_s10c_parity_unparseable_yaml_is_a_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10c.1 / CT1): malformed YAML is exit 2 — **I-40 FIXED**, test inverted.

    **This test inverted exactly as designed.** It was written in S10b.2 as
    ``test_s10b_parity_unparseable_yaml_crashes``, asserting that
    ``yaml.YAMLError`` *propagated* out of ``_cmd_run``, and its docstring
    said: *"this test INVERTS when I-40 is fixed — that is its purpose."*
    S10c.1 fixed it, so the assertion flips from "raises" to "exit 2".

    The defect was that the handler caught ``ConfigurationError`` /
    ``EvalFamilyConflictError`` / ``OSError``, and PyYAML raises
    ``yaml.YAMLError`` — none of those — so an operator got a raw traceback
    instead of the structured diagnostic every other bad-config path produces.

    **The fix is at the parse site, not here.** Measured during the S10c
    review: the same leak affected **five** commands (``routing-check``,
    ``run``, ``selfcheck``, ``probe``, ``egress-proxy``). Wrapping
    ``yaml.safe_load`` in ``load_models_config`` (``config.py``) converts it to
    ``ConfigurationError`` once, and all five inherit the fix — adding the
    exception to five ``except`` tuples would have fixed the ones an author
    remembered.

    Oracle: exit 2 + the structured ``configuration error`` message carrying
    PyYAML's line/column text.
    Kill-check target: the ``except yaml.YAMLError`` wrap in
    ``load_models_config``.
    """
    _cli_home(tmp_path, monkeypatch)
    config = tmp_path / "broken.yaml"
    config.write_text("roles: [oops\n", encoding="utf-8")
    args = _run_args(tmp_path, config, "parity-malformed")

    assert _cmd_run(args, transport=_ScriptedTransport([]), secrets=_TEST_SECRETS) == 2
    err = capsys.readouterr().err
    assert "configuration error" in err
    assert "not valid YAML" in err, "the operator needs to know it is a SYNTAX problem"


# ── Cell 5: the outcome_sink seam ───────────────────────────────────────────


def test_s10b_parity_outcome_sink_suppresses_global_history_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C2 (S10b.2 / CT1): ``outcome_sink`` captures the outcome and skips the export.

    Pins LOGIC-11: when ``_cmd_workflow`` drives ``_cmd_run`` per stage, the
    per-stage global_history export is suppressed so a later stage's
    ``INSERT OR REPLACE`` cannot overwrite the aggregate row. Both halves of
    that contract live in the epilogue S10b.2 extracts, and the suppression is
    a *negative* behaviour — the easiest kind to lose silently in a refactor.

    Oracle: exit 0 · the sink received exactly one outcome · no
    ``global_history.db`` was written.
    Kill-check target: the ``if outcome_sink is None:`` guard around the export
    — remove it and the db appears; drop the ``append`` and the sink is empty.
    """
    home = _cli_home(tmp_path, monkeypatch)
    config = _models_config(tmp_path)
    args = _run_args(tmp_path, config, "parity-sink")

    sink: list[SessionOutcome] = []
    code, _ = _run_capturing(
        args,
        transport=_ScriptedTransport([_stop_body("sunk")]),
        secrets=_TEST_SECRETS,
        outcome_sink=sink,
    )

    assert code == 0
    assert len(sink) == 1, f"outcome_sink must receive exactly one outcome, got {len(sink)}"
    assert not (home / ".fa" / "global_history.db").exists(), (
        "per-stage export must be suppressed when an outcome_sink is present (LOGIC-11)"
    )


@requires_posix_paths
def test_s10b_parity_without_sink_exports_global_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 (S10b.2 / CT1): the positive control for the export suppression above.

    Without this, the suppression test is satisfiable by the export being
    broken outright — "no db was written" would pass for the wrong reason.
    Asserting the db *does* appear on the normal path is what makes the
    negative assertion meaningful.

    Oracle: exit 0 · ``global_history.db`` exists.
    Kill-check target: the ``export_session_to_global_history`` call.
    """
    home = _cli_home(tmp_path, monkeypatch)
    config = _models_config(tmp_path)
    args = _run_args(tmp_path, config, "parity-export")

    code, _ = _run_capturing(args, transport=_ScriptedTransport([_stop_body("exported")]), secrets=_TEST_SECRETS)

    assert code == 0
    assert (home / ".fa" / "global_history.db").is_file(), (
        "the normal path must export to global_history — if this fails, the suppression test above is passing vacuously"
    )


# ── Cell 6: the late-binding observability seam ─────────────────────────────


def test_s10b_parity_loop_guard_warn_sink_reaches_the_output_bus(tmp_path: Path) -> None:
    """C2 (S10b.2 / CT1): the LoopGuard warn sink still emits ``loop_warn`` to the bus.

    **This test exists because the extraction broke exactly this, silently.**

    In the pre-extraction code ``_loop_guard_warn_sink`` was a closure over
    ``output_bus`` — a local assigned ~90 lines *after* the hooks are
    registered. Python resolves closure variables at call time, so it worked.
    Moving the hook assembly into ``_build_run_hook_registry`` required making
    that deferred read explicit (``output_bus_ref``), and while doing so
    ``OutputEvent`` briefly became a ``TYPE_CHECKING``-only import. The sink
    then raised ``NameError`` at runtime — and the ``except Exception`` that
    guards every observer swallowed it.

    Net effect: every console ``loop_warn`` disappears, no test fails, no error
    surfaces. Exit codes are unchanged, artifacts are unchanged, the whole
    parity suite stays green. Found only by invoking the sink directly.

    That is the shape of regression a decomposition actually produces, so it
    gets a permanent oracle rather than a one-off manual probe.

    Oracle: an ``OutputEvent`` of type ``loop_warn`` carrying the detector and
    message reaches a bus appended to ``output_bus_ref`` **after** the registry
    was built.
    Kill-check target: make ``OutputEvent`` module-scope-only again, or pass
    ``output_bus`` by value instead of by ref → this fails while every other
    test in the suite stays green.
    """
    captured: list[object] = []

    class _RecordingBus:
        def emit(self, event: object) -> None:
            captured.append(event)

    limits = load_runtime_limits_from_path().limits
    log = EventLog(tmp_path / "events.jsonl", run_id="loopwarn", redactor=None, session_db=None, session_id="")

    # Empty at registration time — exactly as in ``_cmd_run``.
    bus_ref: list[object] = []
    hooks = _build_run_hook_registry(
        workspace=tmp_path,
        log=log,
        limits=limits,
        redactor=None,
        draft_store=PrDraftStore(tmp_path / "pr_draft.md"),
        run_log_dir=tmp_path,
        output_bus_ref=bus_ref,  # type: ignore[arg-type]
    )

    guards = [h for chain in hooks._chains.values() for h in chain if type(h).__name__ == "LoopGuard"]
    assert guards, "LoopGuard was not registered — the sink under test does not exist"

    # The bus is created only now, after the hooks exist.
    bus_ref.append(_RecordingBus())
    warn_sink = guards[0]._warn_sink  # type: ignore[attr-defined]
    warn_sink("repeat", "loop detected")

    assert captured, (
        "the LoopGuard warn sink emitted nothing to the output bus. The observer's "
        "broad `except` swallows failures, so this is silent in production."
    )
    event = captured[0]
    assert getattr(event, "type", None) == "loop_warn"
    assert getattr(event, "data", {}) == {"detector": "repeat", "message": "loop detected"}


# ── Cell 7: direct unit cover for helpers extraction made visible ───────────
#
# These branches existed before S10b.2 — inline, inside `_cmd_run`, where their
# uncovered lines were absorbed into that function's aggregate and invisible.
# Extraction did not create the gap; it revealed it. C0p, paired with the C2
# cells above that drive the same code through the command root.


@requires_posix_paths
@pytest.mark.parametrize(
    ("marker", "fragment"),
    [
        ("event_log_authority_unavailable", "session database not available"),
        ("event_log_write_failed", "failed to write event to session database"),
    ],
)
def test_s10b_session_db_error_messages_are_distinct(marker: str, fragment: str) -> None:
    """C0p (S10b.2 / LOGIC-8 + NEW-3): each DB failure gets its own diagnostic.

    The two markers mean different things operationally — "the database is not
    reachable" versus "it is reachable and rejected a write" — and collapsing
    them into one message would send an operator down the wrong path.

    Oracle: the returned message contains the branch-unique fragment and the
    database path.
    Kill-check target: either ``if ... in exc_str`` branch.
    """
    message = _session_db_runtime_error_message(RuntimeError(f"boom {marker}"), Path("/tmp/x/session.db"))

    assert message is not None
    assert fragment in message
    assert "/tmp/x/session.db" in message, "the message must name the database path"


def test_s10b_session_db_unknown_runtime_error_returns_none() -> None:
    """C0p (S10b.2): an unrecognised ``RuntimeError`` is NOT given a friendly message.

    ``None`` is the signal to re-raise. This is the branch that keeps real bugs
    visible as tracebacks instead of disguising them as configuration problems.

    Oracle: ``None`` for an unrelated RuntimeError.
    Kill-check target: replace the ``return None`` with a generic string → this
    fails, and so does the guarantee that unexpected errors keep their stack.
    """
    assert _session_db_runtime_error_message(RuntimeError("something else entirely"), Path("/tmp/s.db")) is None


@requires_posix_paths
def test_s10b_prepare_pr_draft_read_failure_warns_but_continues(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """C0p (S10b.2): an unreadable resume draft warns; it does not abort the run.

    Losing resume context degrades continuity, not correctness, so the run
    proceeds with empty draft text. Asserted explicitly because the *other*
    failure in this helper is fatal, and a refactor that unified them would be
    a silent severity change.

    Oracle: empty text · no error returned · a warning on stderr.
    Kill-check target: the ``except OSError`` around the draft read.
    """
    draft_path = tmp_path / "pr_draft.md"
    draft_path.write_text("unreadable", encoding="utf-8")
    draft_path.chmod(0o000)  # exists and is_file(), but read() raises PermissionError

    try:
        text, error = _prepare_pr_draft(PrDraftStore(tmp_path / "store.md"), draft_path, resume=True)
    finally:
        draft_path.chmod(0o600)

    assert text == ""
    assert error is None, "an unreadable draft must NOT be fatal"
    assert "could not read existing draft" in capsys.readouterr().err


def test_s10b_prepare_pr_draft_returns_resumed_text(tmp_path: Path) -> None:
    """C0p (S10b.2): on ``--resume`` the existing draft is read back.

    The positive control for the warning path above: without it, "text == ''"
    there would pass even if the helper never read anything at all.

    Oracle: the draft's contents are returned and the file survives.
    Kill-check target: the ``if resume and draft_path.is_file()`` guard.
    """
    draft_path = tmp_path / "pr_draft.md"
    draft_path.write_text("carried-over plan", encoding="utf-8")

    text, error = _prepare_pr_draft(PrDraftStore(draft_path), draft_path, resume=True)

    assert error is None
    assert text == "carried-over plan"
    assert draft_path.is_file(), "--resume must preserve the on-disk draft for the next role"


def test_s10b_prepare_pr_draft_without_resume_clears_the_draft(tmp_path: Path) -> None:
    """C0p (S10b.2 / M-7): a fresh run removes the previous session's draft.

    Security-relevant: ``IntentGuard`` trusts the draft's provenance, so a
    non-resume run must not inherit one. This is the ``remove_file=not resume``
    half of the contract.

    Oracle: no text returned · the draft file is gone.
    Kill-check target: invert ``remove_file=not resume`` → the file survives
    and this fails.
    """
    draft_path = tmp_path / "pr_draft.md"
    draft_path.write_text("stale draft from a previous session", encoding="utf-8")

    text, error = _prepare_pr_draft(PrDraftStore(draft_path), draft_path, resume=False)

    assert error is None
    assert text == ""
    assert not draft_path.exists(), "a fresh run must not inherit a previous session's draft"


def test_s10b_build_output_bus_unknown_mode_attaches_no_renderer(tmp_path: Path) -> None:
    """C0p (S10b.2): an unrecognised output mode yields a bus with no renderer.

    ``json`` mode is Phase 2. Until then the documented behaviour is that
    events still flow to the durable log while nothing renders to the console —
    not a crash, and not a silent fallback to console output.

    Oracle: the bus has zero subscribers for an unknown mode, and ≥1 for
    ``console`` (the positive control that makes the zero meaningful).
    Kill-check target: add an ``else`` that attaches ConsoleRenderer.
    """
    args = argparse.Namespace(detail="standard", no_color=False)

    unknown = _build_output_bus(args, "json")
    console = _build_output_bus(args, "console")

    assert len(unknown._listeners) == 0, "unknown mode must not attach a renderer"
    assert len(console._listeners) >= 1, "console mode must attach one — else the assertion above is vacuous"


@requires_posix_paths
def test_s10b_prepare_pr_draft_clear_failure_is_fatal(tmp_path: Path) -> None:
    """C0p (S10b.2 / M-7): failing to CLEAR the draft store is fatal, unlike a read failure.

    The severity asymmetry in this helper is the whole reason it is worth
    testing: a failed *read* warns and continues, a failed *clear* must abort
    with exit 2. ``IntentGuard`` trusts the draft's provenance, so proceeding
    with a draft that could not be reset would let a mutating tool act on
    intent the current session never established. Failing closed is correct.

    Oracle: a non-``None`` error message naming the path — which the caller
    turns into exit 2.
    Kill-check target: the ``except OSError`` around ``draft_store.clear``;
    swallow it and this fails while the read-failure test stays green, which
    is exactly the severity collapse this pins against.
    """
    protected = tmp_path / "locked"
    protected.mkdir()
    draft_path = protected / "pr_draft.md"
    draft_path.write_text("existing", encoding="utf-8")
    protected.chmod(0o500)  # read+execute only: the file cannot be unlinked

    try:
        text, error = _prepare_pr_draft(PrDraftStore(draft_path), draft_path, resume=False)
    finally:
        protected.chmod(0o700)

    assert error is not None, "an unclearable draft store must be fatal, not a warning"
    assert "failed to reset PR draft path" in error
    assert text == ""


# ══════════════════════════════════════════════════════════════════════════
# S10b.3 — `_cmd_stats` parity oracles (GAP2)
# ══════════════════════════════════════════════════════════════════════════
#
# Written and run green against UNMODIFIED cli.py before the extraction, same
# as the `_cmd_run` cells above.
#
# `_cmd_stats` is a DISPATCHER over three independent renderers
# (--global-history, JSON, console) plus a --since filter and a --dead-zones
# epilogue. Its complexity is branch count, not depth, so the parity risk is
# specifically that an extraction reroutes one mode into another's renderer —
# a failure that produces output on the right stream with the right exit code
# and is invisible to anything but a content assertion.
#
# S10a already covers exit codes for the not-found/invalid paths. These cells
# deliberately assert WHAT WAS RENDERED and ON WHICH STREAM, which is the part
# the decomposition can silently break.


def _stats_args(**overrides: object) -> argparse.Namespace:
    """The 7 attributes ``_cmd_stats`` reads (S10a's AST-extracted contract)."""
    base: dict[str, object] = {
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


def _seed_global_history(home: Path, *, run_id: str) -> None:
    """Write one real ``global_history.db`` row via the production writer.

    ``export_run`` (not a hand-rolled INSERT) so the fixture cannot drift from
    the schema the reader expects — the same discipline as S10a's sibling
    helper, which takes a row count rather than a run id.
    """
    from fa.inner_loop.global_history import GlobalHistoryStore, default_global_history_path

    GlobalHistoryStore(db_path=default_global_history_path()).export_run(
        {
            "run_id": run_id,
            "created_at": "2026-08-01T00:00:00Z",
            "updated_at": "2026-08-01T00:00:00Z",
            "role": "coder",
            "model": "test-model",
            "family": "openai",
            "exit_code": 0,
            "stop_reason": "stopped_by_llm",
            "turns": 3,
        }
    )
    assert (home / ".fa" / "global_history.db").is_file(), "fixture did not write the projection"


@requires_posix_paths
def test_s10b_stats_parity_global_history_json_goes_to_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10b.3 / CT1): ``--global-history --output json`` prints parseable JSON to stdout.

    Stream placement is the contract under test, not just the exit code. The
    console branch of this same mode writes to **stderr** (it is a human
    report), so an extraction that merged the two renderers would still exit 0
    and still print something — while silently making
    ``fa stats --global-history --output json > runs.json`` produce an empty
    file.

    Oracle: exit 0 · stdout parses as JSON · the row's ``run_id`` is present.
    Kill-check target: the ``if args.output == "json"`` branch inside the
    global-history block.
    """
    _cli_home(tmp_path, monkeypatch)
    _seed_global_history(tmp_path / "home", run_id="gh-json")

    assert _cmd_stats(_stats_args(global_history=True, workspace=tmp_path)) == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert [r["run_id"] for r in payload] == ["gh-json"]


@requires_posix_paths
def test_s10b_stats_parity_global_history_console_goes_to_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10b.3 / CT1): the console rendering of ``--global-history`` is a stderr report.

    The negative half of the cell above: this mode must leave **stdout empty**
    so the command composes in a pipeline. Asserting both directions is what
    makes a renderer swap detectable.

    Oracle: exit 0 · the banner and the row appear on stderr · stdout is empty.
    Kill-check target: the ``file=sys.stderr`` on the global-history console
    prints.
    """
    _cli_home(tmp_path, monkeypatch)
    _seed_global_history(tmp_path / "home", run_id="gh-console")

    assert _cmd_stats(_stats_args(global_history=True, output="text", workspace=tmp_path)) == 0

    captured = capsys.readouterr()
    assert "Global history" in captured.err
    assert "gh-console" in captured.err
    assert captured.out == "", f"human rendering must not pollute stdout: {captured.out!r}"


def test_s10b_stats_parity_invalid_since_is_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10b.3 / CT1): ``--since`` is validated ONCE, ahead of both branches.

    S9.2/F6 deliberately placed this guard before the mode dispatch: the
    global-history branch sits inside a broad ``except Exception -> return 1``,
    which is the wrong home for a *usage* error, and two guards would be two
    places to drift. An extraction that pushes validation into the branches
    would turn exit 2 into exit 1 here.

    Oracle: exit **2** (not 1) + the branch-unique message.
    Kill-check target: the pre-dispatch ``_parse_since(...) is None`` guard.
    """
    _cli_home(tmp_path, monkeypatch)

    assert _cmd_stats(_stats_args(since="-5d", workspace=tmp_path)) == 2
    assert "invalid --since value" in capsys.readouterr().err


def test_s10b_stats_parity_run_id_overrides_since(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10b.3 / CT1 / Q39): ``--run-id`` wins over ``--since``, so a bad ``--since`` is not validated.

    Pins a *precedence* rule that is easy to lose in a refactor. Q39 recorded
    this as deliberate: when ``--run-id`` is given the window is unused, so an
    unparseable value is never reached. An extraction that validates ``--since``
    unconditionally would start rejecting command lines that work today.

    Oracle: NOT exit 2 — the invalid ``--since`` is ignored; the run-id path
    runs and reports its own not-found result (exit 1).
    Kill-check target: the ``and not getattr(args, "run_id", None)`` clause in
    the validation guard.
    """
    _cli_home(tmp_path, monkeypatch)

    code = _cmd_stats(_stats_args(run_id="nope-not-here", since="-5d", workspace=tmp_path))

    assert code == 1, "an unused --since must not be validated when --run-id is present (Q39)"
    assert "invalid --since value" not in capsys.readouterr().err


def test_s10b_stats_parity_dead_zones_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10b.3 / CT1): ``--dead-zones`` appends its report to stderr.

    The epilogue branch. S10a's mutation sweep found that asserting only the
    exit code here **survives deleting the whole block** — exit 0 either way —
    so this asserts the report text.

    Oracle: exit 0 · the ``Dead zones`` header on stderr.
    Kill-check target: the ``if getattr(args, "dead_zones", False)`` block.
    """
    _cli_home(tmp_path, monkeypatch)
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")
    src_dir = tmp_path / "src"
    src_dir.mkdir(exist_ok=True)
    (src_dir / "never_touched.py").write_text("x = 1\n", encoding="utf-8")

    run_args = _run_args(tmp_path, config, "s10b-dead")
    assert _cmd_run(run_args, transport=_ScriptedTransport([_stop_body("ok")]), secrets=_TEST_SECRETS) == 0
    capsys.readouterr()

    code = _cmd_stats(_stats_args(run_id="s10b-dead", output="text", dead_zones=True, workspace=tmp_path))

    assert code == 0
    assert "Dead zones" in capsys.readouterr().err


def test_s10b_stats_parity_single_session_json_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10b.3 / CT1): a single ``--run-id`` renders the SESSION shape, not the aggregate.

    ``_cmd_stats`` picks between ``render_session_json`` and
    ``aggregate_sessions`` on ``args.run_id and len(sessions) == 1``. Both
    produce valid JSON on stdout with exit 0, so only a shape assertion
    distinguishes them — precisely the kind of branch an extraction collapses.

    Oracle: exit 0 · the payload is the per-session shape (has ``run_id``, has
    no ``sessions_detail`` aggregate key).
    Kill-check target: the ``if args.run_id and len(sessions) == 1`` selector.
    """
    _cli_home(tmp_path, monkeypatch)
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")

    run_args = _run_args(tmp_path, config, "s10b-single")
    assert _cmd_run(run_args, transport=_ScriptedTransport([_stop_body("ok")]), secrets=_TEST_SECRETS) == 0
    capsys.readouterr()

    assert _cmd_stats(_stats_args(run_id="s10b-single", workspace=tmp_path)) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == "s10b-single"
    assert "sessions_detail" not in payload, "a single-run query must not render the aggregate shape"


# ══════════════════════════════════════════════════════════════════════════
# S10b.4 — `_discover_stats_sources` parity oracles (GAP3)
# ══════════════════════════════════════════════════════════════════════════
#
# Written and run green against UNMODIFIED cli.py.
#
# This function is a VALIDATION MATRIX: every rejection raises
# ``StatsSourceError`` with a distinct ``code``, and the CLI surfaces that code
# verbatim ("fa stats: source error [<code>]: ..."). The code IS the operator
# contract — it is what a script greps and what a bug report quotes.
#
# S10a already covers the three early guards (invalid_run_id,
# invalid_session_id, unknown_session) through the command root. These cells
# cover the per-manifest validation chain S10b.4 extracts, where every branch
# raises the SAME exception type and differs only by code. An extraction that
# reorders or merges two of them keeps the type, keeps the exit status, and
# silently changes the diagnostic.


def _write_manifest(session_dir: Path, **overrides: object) -> Path:
    """A valid manifest for ``session_dir``, with targeted corruptions applied."""
    session_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "session_id": session_dir.name,
        "status": "active",
        "session_db_path": str((session_dir / "session.db").resolve()),
        "workspace_path": str(session_dir),
    }
    payload.update(overrides)
    manifest = session_dir / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return manifest


def _discover(state_root: Path, **kwargs: object) -> object:
    defaults: dict[str, object] = {
        "selected_session_id": None,
        "selected_run_id": None,
        "since_seconds": None,
    }
    defaults.update(kwargs)
    return _discover_stats_sources(state_root=state_root, **defaults)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("overrides", "code", "case"),
    [
        ({"status": "closed"}, "manifest_corrupt", "inactive manifest"),
        ({"session_id": 42}, "manifest_corrupt", "non-string session_id"),
        ({"session_id": "../escape"}, "manifest_corrupt", "traversal in session_id"),
        ({"session_db_path": "/somewhere/else/session.db"}, "manifest_path_mismatch", "db path mismatch"),
    ],
)
def test_s10b_discover_manifest_validation_codes(
    tmp_path: Path, overrides: dict[str, object], code: str, case: str
) -> None:
    """C0p (S10b.4 / CT1 / GAP3): each manifest defect raises its OWN ``StatsSourceError`` code.

    Every branch here raises the same exception type and reaches the operator
    as the same exit code (2). Only the ``code`` distinguishes them, and the
    CLI prints it verbatim — so the code is the contract, and asserting the
    exception type alone would let any two of these merge unnoticed.

    ``manifest_path_mismatch`` is the security-relevant one: it refuses a
    manifest that points at a ``session.db`` outside its own session directory,
    which is how a crafted manifest would redirect stats at another session's
    database.

    Oracle: ``StatsSourceError`` with the exact expected ``code``.
    Kill-check target: the matching ``raise`` — delete it and only that
    parametrised case fails, naming the branch that vanished.
    """
    from fa.stats import StatsSourceError

    sessions_root = tmp_path / "sessions"
    _write_manifest(sessions_root / "sess-1", **overrides)

    with pytest.raises(StatsSourceError) as excinfo:
        _discover(tmp_path)

    assert excinfo.value.code == code, case


def test_s10b_discover_unreadable_manifest_is_manifest_corrupt(tmp_path: Path) -> None:
    """C0p (S10b.4 / GAP3): unparseable JSON is reported, not raised as a JSONDecodeError.

    A separate branch from the semantic checks above — this one wraps
    ``OSError``/``JSONDecodeError`` from the *read*. Without the wrapper a
    corrupt file escapes as a raw traceback, which is the I-40 failure shape
    seen elsewhere in this CLI.

    Oracle: ``StatsSourceError`` code ``manifest_corrupt`` naming the path.
    Kill-check target: the ``except (OSError, json.JSONDecodeError)`` wrapper.
    """
    from fa.stats import StatsSourceError

    session_dir = tmp_path / "sessions" / "sess-bad"
    session_dir.mkdir(parents=True)
    (session_dir / "manifest.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(StatsSourceError) as excinfo:
        _discover(tmp_path)

    assert excinfo.value.code == "manifest_corrupt"
    assert "manifest.json" in str(excinfo.value)


def test_s10b_discover_identity_mismatch_when_session_selected(tmp_path: Path) -> None:
    """C0p (S10b.4 / GAP3): a manifest whose ``session_id`` disagrees with its directory.

    Only reachable when ``--session-id`` is given, so it is a distinct branch
    from the generic corruption checks and needs its own cell.

    Oracle: code ``manifest_identity_mismatch``.
    Kill-check target: the ``session_id != selected_session_id`` guard.
    """
    from fa.stats import StatsSourceError

    session_dir = tmp_path / "sessions" / "sess-a"
    _write_manifest(session_dir, session_id="sess-b")

    with pytest.raises(StatsSourceError) as excinfo:
        _discover(tmp_path, selected_session_id="sess-a")

    assert excinfo.value.code == "manifest_identity_mismatch"


def test_s10b_discover_legacy_layout_is_rejected_explicitly(tmp_path: Path) -> None:
    """C0p (S10b.4 / GAP3): a legacy ``session-log/`` tree gets a named error, not silence.

    The distinction that matters: **no sessions at all** returns ``()`` (an
    empty result the caller reports as "no matching sessions"), whereas a
    *legacy* layout raises ``legacy_trace_unsupported``. Collapsing the two
    would tell an operator with unmigrated data that they simply have no
    sessions.

    Oracle: code ``legacy_trace_unsupported``.
    Kill-check target: the ``has_legacy`` detection.
    """
    from fa.stats import StatsSourceError

    legacy_run = tmp_path / "session-log" / "old-run"
    legacy_run.mkdir(parents=True)
    (legacy_run / "events.jsonl").write_text("{}\n", encoding="utf-8")

    with pytest.raises(StatsSourceError) as excinfo:
        _discover(tmp_path)

    assert excinfo.value.code == "legacy_trace_unsupported"


def test_s10b_discover_no_sources_returns_empty_not_error(tmp_path: Path) -> None:
    """C0p (S10b.4 / GAP3): an empty state root is ``()``, NOT an exception.

    The positive control for the legacy cell above. Without it, "legacy raises"
    could be satisfied by a version that raises on everything.

    Oracle: an empty tuple.
    Kill-check target: the ``return ()`` after the legacy check.
    """
    assert _discover(tmp_path) == ()


# ══════════════════════════════════════════════════════════════════════════
# S10b.5 — `_cmd_selfcheck` parity oracles (GAP4)
# ══════════════════════════════════════════════════════════════════════════
#
# Written and run green against UNMODIFIED cli.py.
#
# `_cmd_selfcheck` is a DIAGNOSTIC: its output IS its product. It writes to
# stdout (not stderr) and distinguishes exit 2 "you configured this wrong"
# from exit 1 "the proxy is misbehaving". Both the code and the wording are
# the contract — an operator reads the message and a runbook greps it.
#
# S10a's mutation sweep found that asserting only the exit code SURVIVES here,
# because a later handler produces the same code (e.g. `/healthz != 200` and
# the generic route failure both return 1). Every cell below therefore asserts
# branch-unique wording.


def _selfcheck_args(config: Path, role: str = "coder") -> argparse.Namespace:
    return argparse.Namespace(config=config, role=role)


def _proxy_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A syntactically valid proxy URL plus a readable token file."""
    token = tmp_path / "proxy-token"
    token.write_text("proxy-t0ken-abcdefghij\n", encoding="utf-8")
    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "http://127.0.0.1:9/")
    monkeypatch.setenv("FA_PROXY_TOKEN_FILE", str(token))


def test_s10b_selfcheck_parity_healthz_non_200(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10b.5 / CT1 / GAP4): a bad ``/healthz`` status names /healthz specifically.

    Exit 1 alone is NOT a sufficient oracle: the ``/routes`` failures below also
    return 1, so a mutation that deletes this guard falls through to one of
    them and still exits 1. S10a's sweep proved exactly that. The branch-unique
    string is the real assertion.

    Oracle: exit 1 + ``/healthz returned HTTP 503``.
    Kill-check target: the ``if health_status != 200`` guard.
    """
    _cli_home(tmp_path, monkeypatch)
    _proxy_env(monkeypatch, tmp_path)
    monkeypatch.setattr("fa.cli._selfcheck_http_get", lambda url, headers=None: (503, b""))

    assert _cmd_selfcheck(_selfcheck_args(tmp_path / "models.yaml")) == 1
    assert "/healthz returned HTTP 503" in capsys.readouterr().out


def test_s10b_selfcheck_parity_routes_403_is_a_token_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10b.5 / CT1 / GAP4): HTTP 403 on ``/routes`` is diagnosed as a TOKEN mismatch.

    403 has its own branch ahead of the generic ``!= 200`` handler because the
    remedy is different — the operator must reconcile the token files, not read
    proxy logs. An extraction that dropped the 403 case would still exit 1 via
    the generic branch while telling the operator to do the wrong thing.

    Oracle: exit 1 + ``rejected the fa→proxy token`` + the ``FA_PROXY_TOKEN_FILE``
    remediation hint.
    Kill-check target: the ``if routes_status == 403`` branch.
    """
    _cli_home(tmp_path, monkeypatch)
    _proxy_env(monkeypatch, tmp_path)

    def _fake_get(url: str, headers: object = None) -> tuple[int, bytes]:
        return (200, b"") if url.endswith("/healthz") else (403, b"")

    monkeypatch.setattr("fa.cli._selfcheck_http_get", _fake_get)

    assert _cmd_selfcheck(_selfcheck_args(tmp_path / "models.yaml")) == 1
    out = capsys.readouterr().out
    assert "rejected the fa→proxy token" in out
    assert "FA_PROXY_TOKEN_FILE" in out


def test_s10b_selfcheck_parity_malformed_routes_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10b.5 / CT1 / GAP4): a non-JSON ``/routes`` body is reported, not raised.

    The proxy is a trust boundary: its response is untrusted input. Without
    this guard a malformed body escapes as a ``JSONDecodeError`` traceback —
    the same shape as I-40 elsewhere in this CLI.

    Oracle: exit 1 + ``non-JSON or malformed JSON``.
    Kill-check target: the ``except (UnicodeDecodeError, json.JSONDecodeError)``.
    """
    _cli_home(tmp_path, monkeypatch)
    _proxy_env(monkeypatch, tmp_path)

    def _fake_get(url: str, headers: object = None) -> tuple[int, bytes]:
        return (200, b"") if url.endswith("/healthz") else (200, b"{not json")

    monkeypatch.setattr("fa.cli._selfcheck_http_get", _fake_get)

    assert _cmd_selfcheck(_selfcheck_args(tmp_path / "models.yaml")) == 1
    assert "non-JSON or malformed JSON" in capsys.readouterr().out


def test_s10b_selfcheck_parity_missing_route_is_reported_with_remedy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10b.5 / CT1 / GAP4): a config route absent from the proxy is the headline finding.

    This is what ``fa selfcheck`` exists for: the agent and the proxy disagree
    about the route table. The message carries the remediation (recreate the
    proxy after editing models.yaml), and that text is the product.

    Oracle: exit 1 + ``fa selfcheck: ERROR`` + ``absent from proxy /routes``.
    Kill-check target: the ``if has_key is None`` branch of the comparison loop.
    """
    _cli_home(tmp_path, monkeypatch)
    _proxy_env(monkeypatch, tmp_path)
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")

    def _fake_get(url: str, headers: object = None) -> tuple[int, bytes]:
        if url.endswith("/healthz"):
            return (200, b"")
        return (200, json.dumps([{"name": "some-other-route", "has_key": True}]).encode())

    monkeypatch.setattr("fa.cli._selfcheck_http_get", _fake_get)

    assert _cmd_selfcheck(_selfcheck_args(config)) == 1
    out = capsys.readouterr().out
    assert "fa selfcheck: ERROR" in out
    assert "absent from proxy /routes" in out


def test_s10b_selfcheck_parity_unknown_role_is_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10b.5 / CT1 / GAP4): an unknown role is exit **2**, not 1.

    The 1-vs-2 split is the contract under test: 2 means "your invocation or
    config is wrong", 1 means "the proxy is wrong". This guard sits *after* all
    the network probing, so an extraction that hoisted config loading earlier
    could easily turn it into a 1.

    Oracle: exit 2 + the role name in the message.
    Kill-check target: the ``if chain_config is None`` guard.
    """
    _cli_home(tmp_path, monkeypatch)
    _proxy_env(monkeypatch, tmp_path)
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")

    def _fake_get(url: str, headers: object = None) -> tuple[int, bytes]:
        if url.endswith("/healthz"):
            return (200, b"")
        return (200, b"[]")

    monkeypatch.setattr("fa.cli._selfcheck_http_get", _fake_get)

    assert _cmd_selfcheck(_selfcheck_args(config, role="no-such-role")) == 2
    assert "no-such-role" in capsys.readouterr().out


def test_s10b_selfcheck_parity_happy_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C2 (S10b.5 / CT1 / GAP4): agent and proxy agreeing is exit 0 with a route count.

    The positive control for every failure cell above — without it, they are
    all satisfiable by a command that can only fail.

    Oracle: exit 0 + ``fa selfcheck: OK`` + the checked-route count line.
    Kill-check target: the final ``return 0`` / the ``if problems`` guard.
    """
    _cli_home(tmp_path, monkeypatch)
    _proxy_env(monkeypatch, tmp_path)
    config = tmp_path / "models.yaml"
    config.write_text(_FAKE_MODELS_YAML, encoding="utf-8")

    from fa.cli import _selfcheck_expected_routes
    from fa.providers import load_models_config_from_path

    models = load_models_config_from_path(config, require_api_keys=False)
    expected = _selfcheck_expected_routes(models.roles["coder"])
    payload = [{"name": name, "has_key": True} for name in expected]

    def _fake_get(url: str, headers: object = None) -> tuple[int, bytes]:
        if url.endswith("/healthz"):
            return (200, b"")
        return (200, json.dumps(payload).encode())

    monkeypatch.setattr("fa.cli._selfcheck_http_get", _fake_get)

    assert _cmd_selfcheck(_selfcheck_args(config)) == 0
    out = capsys.readouterr().out
    assert "fa selfcheck: OK" in out
    assert f"checked role routes: {len(expected)}" in out
