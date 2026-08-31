"""Contract pins for scripts/run_live_check.sh (sheet rev4, deployment-native).

The rev3 live trial produced eight live-only defects from isolation layers;
the adversarial review of rev4 added six more (D1..D6). Rev4-final follows
worklogs/DEPLOYMENT-ANATOMY.md: the production mechanism is the host wrapper
./scripts/fa -> docker compose exec first-agent fa, keys injected by the
egress proxy, state read from the host side of the state bind. These pins
keep that contract from rotting:

R1  production mechanism only — wrapper fa, no host venv, no config/key
    copies, no env overrides reaching fa;
R2  guarded oracles — missing events is FAIL, rc is announced, run ids are
    PID-unique and events are cleared pre-run;
R3  the dispatch surface stays {setup,smoke,l1,l2,l3,l4,ledger};
R4  the ledger header stays the S11-agreed CSV shape and its dir is created
    before any capture copy.

Syntax is additionally gated by scripts/check_shell_syntax.sh; these tests
pin the SEMANTICS that bash -n cannot see, and run the stub-deployment
battery end to end.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "run_live_check.sh"
BATTERY = Path(__file__).resolve().parent.parent / "scripts" / "adversarial_battery_live_check.sh"


def _text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def _code() -> str:
    """Script text with comment lines stripped — for negative substring pins,
    so a header comment documenting a ban ('Never ./.venv/bin/fa') cannot
    trip the ban's own pin."""
    return "\n".join(line for line in _text().splitlines() if not line.lstrip().startswith("#"))


def test_script_exists_and_is_syntax_clean() -> None:
    assert SCRIPT.is_file(), "run_live_check.sh missing"
    proc = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert proc.returncode == 0, f"bash -n failed:\n{proc.stderr}"


def test_r1_deployment_mechanism_only() -> None:
    """R1: the runner uses the host wrapper and never a host venv or key copies."""
    text = _text()
    assert 'FA="./scripts/fa"' in text, "runner must invoke the deployment wrapper"
    code = _code()
    assert ".venv/bin/fa" not in code, (
        "host venv is not the deployment mechanism: production fa runs inside "
        "the container via docker compose exec (DEPLOYMENT-ANATOMY.md)"
    )
    assert "export FA_STATE_ROOT" not in code, "rev4 runner must not isolate FA_STATE_ROOT"
    assert "worktree add" not in code, "rev4 runner must not create git worktrees"
    assert "sudo cp" not in code, "no config copying — container models.yaml is a read-only bind"
    assert "~/.fa/.env" not in code and "fa.env" not in code, (
        "LLM keys live ONLY in the egress proxy (ADR-12 Option C); the runner must never reference a host-side key file"
    )


def test_r1_scrubs_override_env() -> None:
    """R1/D3: override env vars are scrubbed before fa is ever invoked."""
    text = _text()
    assert "unset FA_STATE_ROOT" in text, "env scrub removed"
    assert text.index("unset FA_STATE_ROOT") < text.index('"$FA" run'), "scrub must precede every fa invocation"


def test_r1_state_and_routing_paths() -> None:
    """R1: oracle reads the documented deployment paths; overrides are test-only."""
    text = _text()
    assert "/srv/first-agent/state" in text, "state-bind host path missing"
    assert "/srv/first-agent/sessions" in text, "sessions-bind host path missing"
    assert "/srv/first-agent/routing/models.yaml" in text, "routing source path missing"
    for var in ("FA_STATE_HOST", "FA_SESSIONS_HOST", "FA_ROUTING"):
        assert var in text, f"test-only path override {var} missing (battery depends on it)"


def test_session_audit_mirrors_manager_blocking_classes() -> None:
    """The audit flags only what manager._read_manifest actually raises on.

    A merely-pruned workspace must NOT block (resolve() tolerates missing
    paths); corrupt/incomplete/v!=v1/inactive manifests and /sessions escapes
    (the rev3 DoS class) must abort setup.
    """
    text = _text()
    body = text.split("audit_sessions()", 1)[1].split("\n}\n", 1)[0]
    for marker in ("schema_version", '"v1"', '"active"', "path_escape class", "pruned"):
        assert marker in body, f"audit lost the {marker} check"
    assert "sys.exit(1 if blocking else 0)" in body, "audit no longer distinguishes blocking"
    setup_body = text.split("cmd_setup()", 1)[1].split("\n}", 1)[0]
    assert "audit_sessions" in setup_body, "setup lost the session audit"
    assert "warn_stale_sessions" not in text, "old always-warn scan reintroduced"


def test_schema_check_warms_up_the_fix6_migration() -> None:
    """fix6 migrates on open — the check must warm it via the wrapper, not die."""
    text = _text()
    body = text.split("check_history_schema()", 1)[1].split("\n}\n", 1)[0]
    assert '"$FA" stats --global-history' in body, (
        "schema check must trigger the additive/idempotent migration through the production wrapper and re-verify"
    )
    assert "mode=ro" in text, "schema probe must open the production db read-only"


def test_r2_missing_events_is_fail_never_pass() -> None:
    """R2: the events-file guard exists and no false-pass pattern remains."""
    text = _text()
    assert '[ ! -f "$events" ]' in text, "missing-events guard removed"
    assert "[FAIL] no events file" in text, "missing-events FAIL branch removed"
    assert '|| echo "  [PASS]' not in text, "unguarded PASS fallback reintroduced"


def test_r2_failed_run_is_flagged() -> None:
    """R2/D2: a nonzero fa exit must be announced before any verdict."""
    text = _text()
    assert "[FAIL] fa exited" in text, "rc-aware oracle removed"
    l1_body = text.split("    l1)\n", 1)[1].split(";;", 1)[0]
    assert '"$rc" -eq 0' in l1_body, "l1 PASS no longer requires fa exit 0"


def test_r2_no_stale_event_reads() -> None:
    """R2/D6: RID is PID-unique and the events path is cleared pre-run."""
    text = _text()
    assert '-$$"' in text, "run_id lost its PID suffix (same-second collisions)"
    assert 'rm -f "$events"' in text, "pre-run events delete removed"
    assert text.index('rm -f "$events"') < text.index('"$FA" run'), "events must be cleared before the run, not after"


def test_r4_ledger_dir_before_capture_and_header_shape() -> None:
    """R4/D1: ledger dir before any capture copy; header stays the agreed shape."""
    text = _text()
    assert text.index('mkdir -p "$LEDGER_DIR"') < text.index('cp "$events"'), (
        "capture copy runs before the ledger dir exists (defect D1)"
    )
    header_line = next(line for line in text.splitlines() if line.startswith("HDR="))
    cols = header_line.split('"', 2)[1].split(",")
    assert cols == [
        "run_id",
        "date",
        "row",
        "recommended_mode",
        "level_path",
        "expansion_n",
        "observed_n",
        "exhausted",
        "exit_code",
        "notes",
    ], f"ledger header drifted: {cols}"


def test_evidence_grep_is_anchored_to_escalation_events() -> None:
    """The evidence-name check must run over scope_expansion events ONLY.

    Unanchored, it matches guard-refusal text stored in tool_result payloads:
    the 2026-08-30 l3 run printed "[PASS] expansion evidence names present"
    with expansion_n=0 because a LoopGuard refusal string contained
    "high_tier_write".
    """
    text = _text()
    assert """grep '"kind": "scope_expansion"' "$events" """ in text, (
        "evidence check no longer anchored to escalation events"
    )
    assert '"${exp:-0}" -gt 0 ]; then' in text.split("l2|l3)", 1)[1], "evidence check must be gated on exp > 0"


def test_near_miss_note_distinguishes_declined_from_ignored() -> None:
    """observed_n>0 without escalation = policy declined; not 'advice not taken'."""
    text = _text()
    assert "near-miss telemetry present" in text, "the no-handoff NOTE must explain the near-miss case separately"


def test_row_diagnostics_detail_and_timeline() -> None:
    """Operator feedback 2026-08-30: rows must show the broader picture."""
    text = _text()
    assert "CAE_DETAIL:-verbose" in text, "detail level must be overridable (debug adds ms timing)"
    body = text.split("row_run()", 1)[1].split("\n}\n", 1)[0]
    assert "print_timeline" in body, "row_run lost its per-turn timeline printout"
    assert 'kind == "tool_result"' in text and "loop_guard_warn" in text, (
        "timeline must surface guard denials and loop warnings from events"
    )
    assert 'kind == "model_msg"' in text, (
        "turn bucketing must be order-based on model_msg boundaries: "
        "tool_call/tool_result events carry no turn field (state.py), so a "
        "content.turn lookup piles everything into turn 0 — the bug the "
        "2026-08-31 gemini l1 run exposed (t0 [parallel x7])"
    )


def test_rows_never_gate_or_touch_the_host_checkout() -> None:
    """Rows run in the container's session clone — no host-tree gates remain."""
    text = _text()
    assert "require_clean_tree" not in text, (
        "clean-tree gate reintroduced: rows never modify the host checkout "
        "(/repo bind is read-only; work happens in /sessions/<id>)"
    )
    assert "session-*/" not in text, "host bootstrap-dir sweeping is a dead host-venv artifact"


def test_r3_dispatch_surface() -> None:
    """R3: one command per row; dispatch surface is pinned."""
    text = _text()
    for sub in ("setup", "smoke", "l1", "l2", "l3", "l4", "ledger"):
        assert f"\n  {sub})" in text or f" {sub}) " in text or f"{sub})\n" in text, (
            f"subcommand {sub} missing from dispatch"
        )
    smoke_body = text.split("cmd_smoke()", 1)[1].split("\n}", 1)[0]
    assert '"$FA"' not in smoke_body and "row_run smoke" in smoke_body, (
        "smoke must reuse the row_run mechanism (same oracle, same ledger), not grow its own fa invocation path"
    )


def test_setup_fails_fast_on_unhealthy_stack() -> None:
    """setup must probe before any row spends tokens (deployment guard S5)."""
    text = _text()
    setup_body = text.split("cmd_setup()", 1)[1].split("\n}", 1)[0]
    assert '"$FA" probe' in setup_body, "setup lost its probe"
    assert "die" in setup_body.split('"$FA" probe', 1)[1][:120], "probe failure must abort setup"
    assert '"$FA" status' in setup_body, "setup lost its stack status check"


def test_interrupt_captures_ledger_row() -> None:
    """A Ctrl-C mid-row must land an INTERRUPTED ledger row, not silence."""
    text = _text()
    assert "trap '" in text and "INTERRUPTED" in text, "interrupt trap removed"
    assert "trap - INT TERM" in text, "trap never reset after the row completes"


def test_objective_misses_exit_three_and_flag_the_ledger() -> None:
    """A completed run that misses the row objective is a finding, not a note.

    An escalating negative control (l1) and a non-escalating l2 both exit 3
    with an explicit ledger flag — the 2026-08-31 review found both verdict
    classes exiting 0 behind a [NOTE].
    """
    text = _text()
    assert "NEGATIVE_CONTROL_FAILED" in text, "escalating-negative-control flag removed"
    assert "NO_ESCALATION_WHERE_EXPECTED" in text, "missed-l2-objective flag removed"
    assert "vrc=3" in text, "objective-miss exit code removed"
    assert 'return "$vrc"' in text, "row_run no longer propagates the verdict code"
    assert "3 = run completed but the row OBJECTIVE was missed" in text, (
        "exit-code contract no longer documented in the header"
    )


def test_timeline_surfaces_provider_rollup_and_stop_reason() -> None:
    """Observability contract: which model answered, how slow, did it fail
    over, why did the run stop — all readable from the events file alone."""
    text = _text()
    assert 'kind == "llm_call"' in text, "per-turn model/latency/failover meta removed"
    assert "failover x" in text, "failover counter removed from timeline meta"
    assert "summary:" in text, "run rollup summary line removed"
    assert '"kind": "run_stopped"' in text and "[STOP] abnormal stop" in text, (
        "abnormal stop reason is no longer extracted to the verdict"
    )
    assert "stop=${stop_reason:-stopped_by_llm}" in text, (
        "ledger notes lost the stop reason (stopped_by_llm is the default)"
    )


def test_adversarial_battery_is_green() -> None:
    """The committed stub-deployment battery (S0..S16) must pass with 0 defects."""
    assert BATTERY.is_file(), "adversarial_battery_live_check.sh missing"
    proc = subprocess.run(["bash", str(BATTERY)], capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, f"battery failed:\n{proc.stdout}\n{proc.stderr}"
    assert "0 missed" in proc.stdout
    assert "DEFECT-CONFIRMED" not in proc.stdout


def test_usage_exit_code() -> None:
    """No/unknown subcommand exits 2 with usage (never runs anything)."""
    proc = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, cwd=SCRIPT.parent.parent)
    assert proc.returncode == 2
    assert "usage:" in proc.stderr
