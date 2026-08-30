#!/usr/bin/env bash
# scripts/run_live_check.sh — S10 live-verification runner (sheet rev4, deployment-native).
#
# Follows worklogs/DEPLOYMENT-ANATOMY.md exactly. The production mechanism is:
#   host wrapper ./scripts/fa  ->  docker compose exec first-agent fa  ->  proxy-injected keys
# No host venv (the runtime venv is /opt/fa-venv INSIDE the image), no config
# copies (container models.yaml is a read-only bind of the routing file), no
# key files on the agent side (proxy mode: SecretStore is empty by design).
#
# Design rules:
#   R1  Production mechanism only: fa == ./scripts/fa (the same file as
#       /usr/local/bin/fa). Never ./.venv/bin/fa, never direct docker calls,
#       never `fa cmd -e VAR=...` (wrapper does not forward env).
#       The oracle reads events.jsonl from the HOST side of the state bind
#       (/srv/first-agent/state == container ~/.fa). FA_STATE_HOST/FA_ROUTING
#       override those two paths for TESTS ONLY — they never change where fa
#       itself runs or writes.
#   R2  Guarded oracles: missing events file is a FAIL, never a PASS; a nonzero
#       fa exit is announced before any verdict; the run id carries a PID
#       suffix and the events path is cleared pre-run, so no row can ever be
#       scored against another row's events.
#   R3  All logic lives in THIS committed, bash -n'd file, functions defined
#       before use. Operators paste one short command per row.
#   R4  The ledger is appended by this script only; its directory is created
#       before any capture copy.
#
# Rows run INSIDE the container's per-session workspace clone (/sessions/<id>
# from /repo). The host checkout is never modified by a row — no clean-tree
# gates, no commit/restore choreography between rows.
#
# Usage:
#   scripts/run_live_check.sh setup    # preflight: stack, probe, routing, schema, ledger
#   scripts/run_live_check.sh l1       # docs-only negative control (expect 0 escalations)
#   scripts/run_live_check.sh l2       # src/ task (expect escalation; session clone only)
#   scripts/run_live_check.sh l3       # doc-defect full cycle (40 turns, session clone)
#   scripts/run_live_check.sh l4       # durable history + calibration
#   scripts/run_live_check.sh ledger   # show the capture ledger
set -euo pipefail

# R1 hygiene: a leaked override in the operator shell must not reach fa.
unset FA_STATE_ROOT FA_SECRETS_FILE FA_MODELS_CONFIG 2>/dev/null || true

REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
FA="./scripts/fa"                                        # host wrapper -> container
STATE_HOST="${FA_STATE_HOST:-/srv/first-agent/state}"    # host side of container ~/.fa
ROUTING="${FA_ROUTING:-/srv/first-agent/routing/models.yaml}"
PY="python3"                                             # host stdlib python (parsing only)
LEDGER_DIR="worklogs/reviews/live-trial-data"
LEDGER="$LEDGER_DIR/ledger.csv"
HDR="run_id,date,row,recommended_mode,level_path,expansion_n,observed_n,exhausted,exit_code,notes"

die() { echo "ERROR: $*" >&2; exit 2; }

need_fa() {
  [ -x "$FA" ] || die "$FA missing or not executable — run from the deployment checkout"
  command -v docker >/dev/null 2>&1 || die "docker not on PATH — the wrapper cannot reach the stack"
}

check_history_schema() {
  # fix6 (migration single-source-of-truth) must be in this checkout, else
  # per-run exports against a pre-S3.5 global_history.db fail.
  local db="$STATE_HOST/global_history.db"
  [ -f "$db" ] || return 0
  "$PY" - "$db" <<'PYEOF' || echo "  [WARN] history schema check failed — skipping"
import sqlite3, sys
cols = {r[1] for r in sqlite3.connect(sys.argv[1]).execute("PRAGMA table_info(runs);")}
if "scope_estimate_json" not in cols:
    print("  [WARN] global_history.db predates S3.5 and this checkout lacks the")
    print("         fix6 migration — exports will fail. Run 'fa update'.")
    sys.exit(1)
print("  history schema OK (scope_estimate_json present)")
PYEOF
}

warn_stale_sessions() {
  # A session manifest whose workspace_path no longer exists makes
  # SessionManager refuse runs (path_escape). Production state is NOT ours to
  # delete — report and let the operator decide.
  [ -d "$STATE_HOST/sessions" ] || return 0
  "$PY" - "$STATE_HOST" <<'PYEOF' || echo "  [WARN] stale-session scan failed — skipping"
import glob, json, os, sys
stale = []
for m in glob.glob(os.path.join(sys.argv[1], "sessions", "*", "manifest.json")):
    try:
        with open(m, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        continue
    wp = data.get("workspace_path") or ""
    if wp and not os.path.isdir(wp):
        stale.append((os.path.basename(os.path.dirname(m)), wp))
for name, wp in stale:
    print(f"  [WARN] stale session {name}: workspace missing: {wp}")
if not stale:
    print("  no stale session manifests")
PYEOF
}

append_ledger() { # rid row exit mode levels exp obs exh notes
  mkdir -p "$LEDGER_DIR"
  [ -f "$LEDGER" ] || echo "$HDR" > "$LEDGER"
  printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,"%s"\n' \
    "$1" "$(date +%F)" "$2" "${4:-?}" "${5:-none}" "${6:-0}" "${7:-0}" "${8:-0}" "$3" "$9" >> "$LEDGER"
}

row_run() { # row_run <label> <max_turns> <task>
  local label="$1" turns="$2" task="$3"
  need_fa
  mkdir -p "$LEDGER_DIR" # R4: dir exists before ANY capture copy
  local rid="cae-${label}-$(date +%s)-$$"
  local log="/tmp/cae_${label}.log"
  local events="$STATE_HOST/session-log/$rid/events.jsonl"
  rm -f "$events" 2>/dev/null || true
  echo "RID=$rid  (log: $log)"

  # Ctrl-C must not silently lose the capture (rows are token-expensive).
  trap 'echo "  [FAIL] interrupted"; { [ -f "$events" ] && cp "$events" "$LEDGER_DIR/$rid.events.jsonl"; } 2>/dev/null; append_ledger "$rid" "$label" 130 "?" "none" 0 0 0 "INTERRUPTED via=container"; exit 130' INT TERM

  local rc=0
  set +e
  "$FA" run --role chat --run-id "$rid" --max-turns "$turns" --detail verbose \
    --task "$task" 2>&1 | tee "$log"
  rc=${PIPESTATUS[0]}
  set -e
  echo "fa EXIT=$rc"

  if [ "$rc" -ne 0 ]; then
    echo "  [FAIL] fa exited $rc — the run FAILED; verdicts below are diagnostics only, do NOT ledger this row as a pass"
  fi

  if [ ! -f "$events" ]; then
    echo "  [FAIL] no events file at $events — session never started; nothing measured"
    append_ledger "$rid" "$label" "$rc" "?" "none" 0 0 0 "NO_EVENTS via=container"
    trap - INT TERM
    return 1
  fi

  local mode levels exp obs exh
  mode="$(grep -o '"recommended_mode": "[a-z_]*"' "$events" | head -1 | cut -d'"' -f4 || true)"
  levels="$(grep -o '"level_from": [0-9], "level_to": [0-9]' "$events" \
    | sed 's/"level_from": //; s/, "level_to": />/' | tr '\n' ';' || true)"
  exp="$(grep -c '"kind": "scope_expansion"' "$events" || true)"
  obs="$(grep -c '"kind": "expansion_observed"' "$events" || true)"
  exh="$(grep -c '"kind": "expansion_exhausted"' "$events" || true)"

  case "$label" in
    l1)
      if [ "$rc" -eq 0 ] && [ "${exp:-0}" -eq 0 ]; then
        echo "  [PASS] no escalation on a safe docs task"
      elif [ "${exp:-0}" -ne 0 ]; then
        echo "  [NOTE] UNEXPECTED scope_expansion ($exp) — inspect $events"
      fi
      ;;
    l2|l3)
      if [ "${exp:-0}" -gt 0 ]; then
        echo "  [PASS] scope_expansion fired ($exp): ${levels:-?}"
      else
        echo "  [NOTE] no escalation within the turn cap (src/ not touched?)"
      fi
      grep -qE 'read_high_arm|high_tier_write|verify_failed' "$events" \
        && echo "  [PASS] expansion evidence names present" \
        || echo "  [NOTE] no evidence names in events"
      grep -q "Start here" "$log" \
        && echo "  [PASS] planner handoff map reached the workflow" \
        || echo "  [NOTE] model finished in chat (advice not taken — legitimate, note it)"
      ;;
  esac
  [ "${exh:-0}" -gt 0 ] && echo "  [OBS] K budget exhausted -> operator-report path"

  cp "$events" "$LEDGER_DIR/$rid.events.jsonl"
  append_ledger "$rid" "$label" "$rc" "$mode" "$levels" "$exp" "$obs" "$exh" \
    "auto-captured via=container"
  trap - INT TERM
  echo "  ledger + events captured (host checkout untouched by design)"
}

# ── subcommands ──────────────────────────────────────────────────────────────
cmd_setup() {
  need_fa
  [ -r "$ROUTING" ] || die "cannot read $ROUTING"
  grep -qE '^chat:' "$ROUTING" || die "no top-level 'chat:' role in $ROUTING"
  echo "== stack status:"
  "$FA" status
  echo "== proxy + provider probe (fails fast before tokens are spent):"
  "$FA" probe || die "fa probe failed — stack/proxy/routing not healthy; fix before running rows"
  echo "== routing-check (container view of the mounted routing file):"
  "$FA" routing-check
  echo "== history schema:"
  check_history_schema
  echo "== stale-session scan (report only — production state is not swept):"
  warn_stale_sessions
  mkdir -p "$LEDGER_DIR"
  [ -f "$LEDGER" ] || echo "$HDR" > "$LEDGER"
  echo "== ledger: $LEDGER"
  echo "READY. Rows: l1 -> l2 -> l3 -> l4 (no git steps between rows; commit the ledger at the end)"
}

cmd_l1() {
  row_run l1 8 "Create live-check-notes.md (or append one line to it) noting the live sheet was checked today."
}

cmd_l2() {
  row_run l2 20 "simplify the main function in src/fa/cli.py - make _cmd_stats a bit shorter without changing behaviour"
}

cmd_l3() {
  row_run l3 40 "The repo has broken internal documentation links (run scripts/check_doc_links.py). Investigate and fix what you can, verify with the checker, and report what you changed."
}

cmd_l4() {
  need_fa
  echo "== global history (container state root):"
  "$FA" stats --global-history --output json 2>/dev/null | "$PY" -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception as e:
    print("  [NOTE] no global-history json:", e); sys.exit(0)
rows = d if isinstance(d, list) else d.get("runs") or d.get("rows") or []
print(f"  rows visible: {len(rows)}")
if not rows:
    shape = list(d)[:8] if isinstance(d, dict) else type(d).__name__
    print("  [NOTE] zero rows; top-level shape:", shape)
for r in rows[-6:]:
    print("   ", r.get("run_id"), "| role=", r.get("role"), "| exit=", r.get("exit_code"))
'
  echo "== calibration:"
  "$FA" stats --calibration 2>&1 1>/dev/null | head -14
}

cmd_ledger() {
  [ -f "$LEDGER" ] || die "no ledger yet at $LEDGER"
  column -s, -t < "$LEDGER" 2>/dev/null || cat "$LEDGER"
  echo "($(($(wc -l < "$LEDGER") - 1)) row(s))"
}

case "${1:-}" in
  setup)  cmd_setup ;;
  l1)     cmd_l1 ;;
  l2)     cmd_l2 ;;
  l3)     cmd_l3 ;;
  l4)     cmd_l4 ;;
  ledger) cmd_ledger ;;
  *)
    echo "usage: scripts/run_live_check.sh {setup|l1|l2|l3|l4|ledger}" >&2
    exit 2
    ;;
esac
