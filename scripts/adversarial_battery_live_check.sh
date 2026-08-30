#!/usr/bin/env bash
# Adversarial battery for scripts/run_live_check.sh — runs the REAL runner
# against a stub deployment (stub ./scripts/fa, stub docker, temp state root
# and routing file) in a disposable repo+HOME. No provider, no network, no
# real containers.
#
# S0..S3 are behavioural checks (must be OK); the numbered defect probes
# re-demonstrate the adversarial-review defect classes (D2 rc-blindness,
# D3 env leak, D6 stale events) plus deployment guards (probe-fail, chat-role):
# each must print [CLOSED]; [DEFECT-CONFIRMED] means a regression -> exit 1.
# KEEP_TESTBED=1 keeps the disposable tree for inspection. Manual use:
#   scripts/adversarial_battery_live_check.sh [path/to/run_live_check.sh]
set -u

SRC_SCRIPT="${1:-$(cd "$(dirname "$0")" && pwd)/run_live_check.sh}"
ROOT="$(mktemp -d /tmp/adv-XXXXXX)"
export HOME="$ROOT/home"
mkdir -p "$HOME/.fa" "$ROOT/repo/scripts" "$ROOT/state/session-log" "$ROOT/routing" "$ROOT/bin" "$ROOT/sessions"

# ── testbed repo (host-checkout stand-in) ──
cp "$SRC_SCRIPT" "$ROOT/repo/scripts/run_live_check.sh"
chmod +x "$ROOT/repo/scripts/run_live_check.sh"

# ── stub docker (the runner only checks it exists; the stub fa does the work) ──
printf '#!/usr/bin/env bash\nexit 0\n' > "$ROOT/bin/docker"
chmod +x "$ROOT/bin/docker"
export PATH="$ROOT/bin:$PATH"

# ── stub scripts/fa: mimics the host wrapper -> container surface ──
cat > "$ROOT/repo/scripts/fa" <<'STUB'
#!/usr/bin/env bash
cmd="${1:-}"; shift || true
case "$cmd" in
  status) echo "first-agent Up (healthy)"; exit "${STUB_STATUS:-0}" ;;
  probe)  echo "probe: providers reachable via proxy"; exit "${STUB_PROBE:-0}" ;;
  routing-check) echo "routing-check: OK (stub)"; exit 0 ;;
  stats)
    case "${STUB_STATS:-hist}" in
      hist) echo '[{"run_id":"cae-l1-1","role":"chat","exit_code":0}]' ;;
      *) echo '{}' ;;
    esac
    exit 0 ;;
  run)
    # D3 probe: record the env the wrapper was invoked with.
    printf 'ENV: FA_STATE_ROOT=%s\n' "${FA_STATE_ROOT:-<unset>}" >> "$HOME/envprobe"
    rid=""
    while [ $# -gt 0 ]; do case "$1" in --run-id) rid="${2:-}"; shift 2 ;; *) shift ;; esac; done
    # The container writes events into its state bind; the stub writes them to
    # the same host-visible path the oracle reads.
    d="$FA_STATE_HOST/session-log/$rid"; mkdir -p "$d"
    case "${STUB_MODE:-ok-l1}" in
      no-events) exit "${STUB_EXIT:-0}" ;;
      fail-with-events)
        printf '{"kind": "tool_call"}\n' > "$d/events.jsonl"
        exit "${STUB_EXIT:-1}" ;;
      refusal-noise)
        {
          echo '{"kind": "tool_call", "content": {"turn": 7}, "tool_name": "fs_edit_file"}'
          echo '{"kind": "tool_result", "content": {"turn": 7, "ok": false, "error": {"summary": "tool call skipped: session stopped — LoopGuard: path src/fa/cli.py thrashed across 5 distinct attempts (high_tier_write mention inside refusal text)"}}, "tool_name": "fs_edit_file"}'
        } > "$d/events.jsonl"
        exit 0 ;;
      ok-l2)
        {
          echo '{"kind": "tool_call", "scope_estimate": {"recommended_mode": "chat_direct"}}'
          echo '{"kind": "scope_expansion", "data": {"level_from": 1, "level_to": 2, "evidence": "read_high_arm"}}'
          echo '{"kind": "expansion_observed", "data": {"turn": 2}}'
        } > "$d/events.jsonl"
        echo "planner sees: Start here: src/fa/cli.py"
        exit 0 ;;
      *)
        printf '{"kind": "tool_call", "scope_estimate": {"recommended_mode": "chat_direct"}}\n' > "$d/events.jsonl"
        exit 0 ;;
    esac ;;
  *) exit 0 ;;
esac
STUB
chmod +x "$ROOT/repo/scripts/fa"

# ── deployment-path fixtures (tests-only overrides of two documented paths) ──
printf 'chat:\n  name: stub\n  chain:\n    - provider: p\n      model: m\n' > "$ROOT/routing/models.yaml"
export FA_STATE_HOST="$ROOT/state"
export FA_SESSIONS_HOST="$ROOT/sessions"
export FA_ROUTING="$ROOT/routing/models.yaml"

cd "$ROOT/repo"
git init -q . && git add -A && git -c user.email=t@t -c user.name=t commit -qm init

PASS=0; FAIL=0
DEFECTS=""
ok()     { PASS=$((PASS+1)); echo "  [OK]   $1"; }
miss()   { FAIL=$((FAIL+1)); echo "  [MISS] $1${2:+ — $2}"; }
defect() { DEFECTS="$DEFECTS,$1"; echo "  [DEFECT-CONFIRMED] $1"; }
closed() { echo "  [CLOSED] $1"; }

echo "== S0: setup happy path (stack up, probe green, chat role present)"
OUT="$(bash scripts/run_live_check.sh setup 2>&1)"; RC=$?
[ $RC -eq 0 ] && ok "S0 setup exit 0" || miss "S0 setup exit 0" "rc=$RC out=$OUT"
printf '%s' "$OUT" | grep -qF 'READY' && ok "S0 READY banner" || miss "S0 READY banner"

echo "== S1: l1 happy path (stub writes clean events, exit 0)"
OUT="$(STUB_MODE=ok-l1 bash scripts/run_live_check.sh l1 2>&1)"; RC=$?
[ $RC -eq 0 ] && ok "S1 exit 0" || miss "S1 exit 0" "rc=$RC out=$OUT"
printf '%s' "$OUT" | grep -qF '[PASS] no escalation' && ok "S1 PASS verdict" || miss "S1 PASS verdict"
grep -qF 'cae-l1-' worklogs/reviews/live-trial-data/ledger.csv 2>/dev/null \
  && ok "S1 ledger row" || miss "S1 ledger row"
printf '%s' "$OUT" | grep -qF 'captured' && ok "S1 events captured" || miss "S1 events captured"
printf '%s' "$OUT" | grep -qF 'turn timeline' && ok "S1 timeline printed" || miss "S1 timeline printed"

echo "== S2: session never starts (no events file) — must FAIL, never PASS"
OUT="$(STUB_MODE=no-events bash scripts/run_live_check.sh l1 2>&1)"; RC=$?
[ $RC -ne 0 ] && ok "S2 nonzero exit" || miss "S2 nonzero exit"
printf '%s' "$OUT" | grep -qF '[FAIL] no events file' && ok "S2 FAIL verdict" || miss "S2 FAIL verdict"
if printf '%s' "$OUT" | grep -qF '[PASS]'; then miss "S2 no false PASS" "found: $(printf '%s' "$OUT" | grep -F '[PASS]')"
else ok "S2 no false PASS"; fi
grep -qF 'NO_EVENTS' worklogs/reviews/live-trial-data/ledger.csv 2>/dev/null \
  && ok "S2 ledger NO_EVENTS" || miss "S2 ledger NO_EVENTS"

echo "== S3: l2 escalation path (events + handoff) + host checkout untouched"
OUT="$(STUB_MODE=ok-l2 bash scripts/run_live_check.sh l2 2>&1)"; RC=$?
printf '%s' "$OUT" | grep -qF '[PASS] scope_expansion fired' && ok "S3 PASS escalation" || miss "S3 PASS escalation" "$OUT"
printf '%s' "$OUT" | grep -qF '[PASS] expansion evidence names present' && ok "S3 evidence names" || miss "S3 evidence names"
grep -qF '1>2' worklogs/reviews/live-trial-data/ledger.csv 2>/dev/null \
  && ok "S3 levels captured" || miss "S3 levels captured"
DIRTY="$(git status --porcelain -- . ':(exclude)worklogs/reviews/live-trial-data')"
[ -z "$DIRTY" ] && ok "S3 host checkout untouched by the row" || miss "S3 host checkout untouched" "$DIRTY"

echo "== S4 (DEFECT PROBE D2): fa exits 1 but wrote events — is the failure admitted?"
OUT="$(STUB_MODE=fail-with-events STUB_EXIT=1 bash scripts/run_live_check.sh l1 2>&1)"
if printf '%s' "$OUT" | grep -qF 'fa exited 1'; then closed "S4: failed run is flagged before verdicts"
else defect "S4: failed run not flagged"; fi

echo "== S5 (DEPLOYMENT GUARD): broken stack/proxy — setup must refuse before tokens are spent"
OUT="$(STUB_PROBE=1 bash scripts/run_live_check.sh setup 2>&1)"; RC=$?
if [ $RC -ne 0 ] && printf '%s' "$OUT" | grep -qF 'fa probe failed'; then
  closed "S5: setup aborts on failed probe"
else
  defect "S5: setup continued despite failed probe"
fi

echo "== S6 (DEFECT PROBE D3): leaked FA_STATE_ROOT in operator shell — does fa see it?"
rm -f "$HOME/envprobe"
OUT="$(FA_STATE_ROOT=/tmp/leaked-root STUB_MODE=ok-l1 bash scripts/run_live_check.sh l1 2>&1)" || true
if grep -q 'FA_STATE_ROOT=/tmp/leaked-root' "$HOME/envprobe" 2>/dev/null; then
  defect "S6: FA_STATE_ROOT leaks through to fa"
elif grep -q 'FA_STATE_ROOT=<unset>' "$HOME/envprobe" 2>/dev/null; then
  closed "S6: override scrubbed before fa is invoked"
else
  miss "S6 probe: envprobe missing (stub never ran?)" "$OUT"
fi

echo "== S7 (DEFECT PROBE D6): back-to-back rows — distinct RIDs, no stale-event false PASS"
O1="$(STUB_MODE=no-events bash scripts/run_live_check.sh l1 2>&1)" || true
O2="$(STUB_MODE=ok-l1   bash scripts/run_live_check.sh l1 2>&1)" || true
R1="$(printf '%s' "$O1" | grep -oE 'RID=[^ ]+' | head -1)"
R2="$(printf '%s' "$O2" | grep -oE 'RID=[^ ]+' | head -1)"
if [ -z "$R1" ] || [ -z "$R2" ]; then miss "S7 RID parse" "$R1 / $R2"
elif [ "$R1" = "$R2" ]; then defect "S7: RID collision across back-to-back runs ($R1)"
elif printf '%s' "$O1" | grep -qF '[FAIL] no events file'; then
  closed "S7: distinct RIDs; run without events cannot inherit a PASS"
else defect "S7: first (no-events) run did not FAIL — stale events read?"; fi

echo "== S8 (DEPLOYMENT GUARD): routing file without a chat role — setup must refuse"
printf 'coder:\n  name: stub\n' > "$ROOT/routing/models.yaml"
OUT="$(bash scripts/run_live_check.sh setup 2>&1)"; RC=$?
if [ $RC -ne 0 ] && printf '%s' "$OUT" | grep -qF "chat:'"; then
  closed "S8: setup aborts without a chat role"
else
  defect "S8: setup accepted routing without chat role"
fi
printf 'chat:\n  name: stub\n  chain:\n    - provider: p\n      model: m\n' > "$ROOT/routing/models.yaml"

echo "== S9: l4 reads durable history through the wrapper"
OUT="$(bash scripts/run_live_check.sh l4 2>&1)"; RC=$?
if [ $RC -eq 0 ] && printf '%s' "$OUT" | grep -qF 'rows visible: 1'; then ok "S9 l4 history parse"
else miss "S9 l4 history parse" "rc=$RC out=$OUT"; fi

echo "== S10 (SESSION AUDIT): pruned workspace is informational — setup must still pass"
mkdir -p "$ROOT/state/sessions/session-pruned"
printf '{"schema_version":"v1","session_id":"session-pruned","workspace_path":"/sessions/session-pruned","session_db_path":"/home/fa/.fa/sessions/session-pruned/session.db","status":"active"}\n' > "$ROOT/state/sessions/session-pruned/manifest.json"
OUT="$(bash scripts/run_live_check.sh setup 2>&1)"; RC=$?
if [ $RC -eq 0 ] && printf '%s' "$OUT" | grep -qF '1 pruned-workspace'; then
  closed "S10: pruned workspace does not block setup"
else
  defect "S10: pruned workspace treated as blocking"
fi

echo "== S11 (SESSION AUDIT): workspace escaping /sessions must abort setup (rev3 DoS class)"
mkdir -p "$ROOT/state/sessions/session-escape"
printf '{"schema_version":"v1","session_id":"session-escape","workspace_path":"/tmp/worktrees/gone","session_db_path":"/home/fa/.fa/sessions/session-escape/session.db","status":"active"}\n' > "$ROOT/state/sessions/session-escape/manifest.json"
OUT="$(bash scripts/run_live_check.sh setup 2>&1)"; RC=$?
if [ $RC -ne 0 ] && printf '%s' "$OUT" | grep -qF '[BLOCK] session-escape'; then
  closed "S11: escaping-workspace manifest aborts setup"
else
  defect "S11: escaping-workspace manifest accepted"
fi
rm -rf "$ROOT/state/sessions/session-escape" "$ROOT/state/sessions/session-pruned"

echo "== S12 (DEFECT PROBE): guard-refusal text containing evidence names must not fake [PASS]"
O="$(STUB_MODE=refusal-noise bash scripts/run_live_check.sh l2 2>&1)" || true
if printf '%s' "$O" | grep -qF '[PASS] expansion evidence names present'; then
  defect "S12: refusal payload faked the evidence PASS (l3 2026-08-30 defect)"
elif printf '%s' "$O" | grep -qF 'no escalation within the turn cap'; then
  closed "S12: refusal text cannot fake the evidence PASS"
else
  miss "S12 probe: unexpected verdicts" "$O"
fi

echo
echo "battery: $PASS checks OK, $FAIL missed; defect probes still open:${DEFECTS:- none}"
if [ "$FAIL" -gt 0 ] || [ -n "$DEFECTS" ]; then
  echo "testbed kept at: $ROOT"
  exit 1
fi
if [ "${KEEP_TESTBED:-0}" = "1" ]; then echo "testbed kept at: $ROOT"; else rm -rf "$ROOT"; fi
exit 0
