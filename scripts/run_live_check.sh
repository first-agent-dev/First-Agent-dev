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
# Exit codes: 0 = row objective met; 1 = run failure (fa rc!=0 or no events);
# 2 = preflight/usage error; 3 = run completed but the row OBJECTIVE was missed
# (negative control escalated, or expected escalation never fired) — a finding,
# ledgered with an explicit flag in notes.
#
# Usage:
#   scripts/run_live_check.sh setup    # preflight: stack, probe, routing, schema, ledger
#   scripts/run_live_check.sh smoke    # 2-turn chat-role end-to-end (probe tests coder!)
#   scripts/run_live_check.sh l1       # docs-only negative control (expect 0 escalations)
#   scripts/run_live_check.sh env      # S12: readiness handoff (venv pytest reachable; D15)
#   scripts/run_live_check.sh pty      # S12: pty timeout -> recovery (C-c reclaim; D16)
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
SESSIONS_HOST="${FA_SESSIONS_HOST:-/srv/first-agent/sessions}" # host side of container /sessions
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

schema_has_col() { # schema_has_col <db> — exit 0 iff runs.scope_estimate_json exists
  "$PY" - "$1" <<'PYEOF'
import sqlite3, sys
try:
    cols = {r[1] for r in sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True).execute("PRAGMA table_info(runs);")}
except Exception:
    sys.exit(1)
sys.exit(0 if "scope_estimate_json" in cols else 1)
PYEOF
}

check_history_schema() {
  # fix6 migrates global_history.db ON EVERY OPEN (additive + idempotent —
  # see _init_db in src/fa/inner_loop/global_history.py). A pre-S3.5 db is
  # therefore not broken, just not yet opened by updated code: warm the
  # migration up through the wrapper and re-verify.
  local db="$STATE_HOST/global_history.db"
  [ -f "$db" ] || { echo "  no global_history.db yet (first run creates it)"; return 0; }
  if schema_has_col "$db"; then
    echo "  history schema OK (scope_estimate_json present)"
  else
    echo "  history schema pre-S3.5 — warming up (fix6 migration runs on open)..."
    "$FA" stats --global-history --output json >/dev/null 2>&1 || true
    if schema_has_col "$db"; then
      echo "  history schema migrated OK (scope_estimate_json present)"
    else
      echo "  [WARN] warm-up did not add scope_estimate_json — exports may fail; investigate before l4"
    fi
  fi
}

audit_sessions() {
  # Mirrors what actually blocks a NEW session (manager._read_manifest via
  # _check_reverse_workspace_ownership, which reads EVERY manifest with no
  # try/except): corrupt/unreadable, missing required fields, schema_version
  # != v1, status != active, or workspace_path escaping the /sessions root
  # (the rev3 DoS class). A workspace dir that was merely PRUNED does NOT
  # block — resolve() tolerates missing paths — so it is informational.
  # Paths: manifests live under the state bind; workspace_path is a CONTAINER
  # path (/sessions/...) mapped here to its host side for the dir check.
  if [ -e "$STATE_HOST/sessions" ] && [ ! -r "$STATE_HOST/sessions" ]; then
    echo "  [WARN] $STATE_HOST/sessions exists but is unreadable for $(id -un) — audit skipped"
    return 0
  fi
  if [ ! -d "$STATE_HOST/sessions" ]; then
    echo "  no sessions dir yet"
    return 0
  fi
  local rc=0
  set +e
  "$PY" - "$STATE_HOST" "$SESSIONS_HOST" <<'PYEOF'
import glob, json, os, sys
state_host, sessions_host = sys.argv[1], sys.argv[2]
REQUIRED = {"schema_version", "session_id", "workspace_path", "session_db_path", "status"}
blocking, pruned = [], []
for m in sorted(glob.glob(os.path.join(state_host, "sessions", "*", "manifest.json"))):
    name = os.path.basename(os.path.dirname(m))
    try:
        with open(m, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        blocking.append((name, f"unreadable/corrupt ({type(exc).__name__})"))
        continue
    if not isinstance(data, dict) or not REQUIRED.issubset(data):
        blocking.append((name, "missing required manifest fields"))
        continue
    if data.get("schema_version") != "v1":
        blocking.append((name, f"schema_version {data.get('schema_version')!r} != 'v1'"))
        continue
    if data.get("status") != "active":
        blocking.append((name, f"status {data.get('status')!r} != 'active'"))
        continue
    wp = os.path.normpath(str(data.get("workspace_path") or ""))
    if not (wp == "/sessions" or wp.startswith("/sessions/")):
        blocking.append((name, f"workspace escapes /sessions root: {wp} (path_escape class)"))
        continue
    rel = wp[len("/sessions/"):] if wp.startswith("/sessions/") else ""
    if not os.path.isdir(os.path.join(sessions_host, rel)):
        pruned.append(name)
for name, why in blocking[:5]:
    print(f"  [BLOCK] {name}: {why}")
if len(blocking) > 5:
    print(f"  [BLOCK] ...and {len(blocking) - 5} more")
print(f"  sessions: {len(blocking)} blocking, {len(pruned)} pruned-workspace (informational)")
sys.exit(1 if blocking else 0)
PYEOF
  rc=$?
  set -e
  if [ "$rc" -ne 0 ]; then
    die "blocking manifest(s) above make SessionManager refuse EVERY new session; quarantine the listed session dirs under $STATE_HOST/sessions/ (operator decision), then re-run setup"
  fi
}

append_ledger() { # rid row exit mode levels exp obs exh notes
  mkdir -p "$LEDGER_DIR"
  [ -f "$LEDGER" ] || echo "$HDR" > "$LEDGER"
  printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,"%s"\n' \
    "$1" "$(date +%F)" "$2" "${4:-?}" "${5:-none}" "${6:-0}" "${7:-0}" "${8:-0}" "$3" "$9" >> "$LEDGER"
}

print_timeline() { # print_timeline <events.jsonl> — per-turn activity + run summary
  "$PY" - "$1" <<'PYEOF' || echo "  [WARN] timeline parse failed"
import json, sys
from collections import OrderedDict
turns = OrderedDict()
turn = 0
pending = ""          # llm_call meta: logged BEFORE its turn's model_msg
totals = {}
stop = None
t_first = t_last = None
denials = {}
n_tools = n_esc = n_near = 0
def slot(t):
    return turns.setdefault(t, {"tools": [], "marks": [], "meta": "", "llm": ""})
for line in open(sys.argv[1], encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    try:
        e = json.loads(line)
    except Exception:
        continue
    kind, c = e.get("kind", ""), (e.get("content") or {})
    ts = e.get("ts") or ""
    if ts:
        t_first = t_first or ts
        t_last = ts
    # Turn attribution is ORDER-BASED: tool_call/tool_result events carry no
    # turn field (state.py), but exactly one model_msg is logged per LLM
    # response. Within a turn the durable order is: provider_attempt*,
    # llm_call, usage, model_msg, tools — so llm_call meta is stashed and
    # consumed by the next model_msg. Events that carry content.turn
    # (scope_expansion, expansion_observed) trust their own.
    if kind == "llm_call":
        bad = 0
        for a in (c.get("chain") or []):
            st = str(a.get("status", ""))
            if a.get("error") or st.startswith(("4", "5")):
                bad += 1
        secs = (c.get("wallclock_ms") or 0) / 1000.0
        pending = "[%s %.1fs%s]" % (c.get("model", "?"), secs, f" failover x{bad}" if bad else "")
        continue
    if kind == "model_msg":
        turn += 1
        s = slot(turn)
        s["meta"] = pending
        # S12.6c: full model text — the live console mirror truncates to 200
        # chars (output.py), the events carry everything.
        s["llm"] = str(c.get("text") or "")
        pending = ""
        continue
    if kind == "session_summary":
        totals = c
        continue
    if kind == "run_stopped":
        stop = str(c.get("reason") or "?")
        continue
    ct = c.get("turn")
    t = ct if isinstance(ct, int) and ct > 0 else turn
    if kind == "tool_result":
        ok = c.get("ok", True)
        err = (c.get("error") or {})
        why = str(err.get("summary") or err.get("message") or "")
        name = e.get("tool_name") or "?"
        guard = ""
        for label, needles in (("IntentGuard", ("IntentGuard", "required shape for `INTENT")),
                               ("LoopGuard", ("LoopGuard",)), ("PauseGuard", ("PauseGuard",))):
            if any(n in why for n in needles):
                guard = label
                break
        n_tools += 1
        if not ok:
            key = guard or "other"
            denials[key] = denials.get(key, 0) + 1
        slot(t)["tools"].append(f"{name}{'' if ok else ' ✗' + (':' + guard if guard else '')}")
    elif kind == "scope_expansion":
        n_esc += 1
        slot(t)["marks"].append(f"⤴L{c.get('level_from')}>{c.get('level_to')}({c.get('evidence')})")
    elif kind == "expansion_observed":
        n_near += 1
        slot(t)["marks"].append("near-miss")
    elif kind == "loop_guard_warn":
        slot(t)["marks"].append(f"loop:{c.get('detector','?')}")
print("  ── turn timeline ([model latency] per turn; ✗:Guard = guard denial; 💬 = model text) ──")
import os
_llm_cap = 0 if os.environ.get("CAE_LLM_FULL") else 2000
for t, s in turns.items():
    if not s["tools"] and not s["marks"] and not s["llm"]:
        continue
    n = len(s["tools"])
    par = " [parallel x%d]" % n if n > 1 else ""
    print(f"  t{t:>2} {s['meta']}{par}: {' '.join(s['tools']) if s['tools'] else '-'}"
          + (f"  {' '.join(s['marks'])}" if s["marks"] else ""))
    if s["llm"]:
        txt = s["llm"].rstrip()
        if _llm_cap and len(txt) > _llm_cap:
            txt = txt[:_llm_cap] + " …[+%d chars — CAE_LLM_FULL=1 for the full text]" % (len(s["llm"].rstrip()) - _llm_cap)
        lines = txt.splitlines() or [""]
        print("      💬 " + lines[0])
        for ln in lines[1:]:
            print("        " + ln)
wall = "?"
if t_first and t_last:
    try:
        from datetime import datetime
        f = datetime.fromisoformat(t_first.replace("Z", "+00:00"))
        l = datetime.fromisoformat(t_last.replace("Z", "+00:00"))
        wall = f"{(l - f).total_seconds():.0f}s"
    except Exception:
        pass
den = ", ".join(f"{v}x{k}" for k, v in sorted(denials.items())) or "0"
tok = ""
if totals:
    tok = f", {totals.get('input_tokens', 0)} in/{totals.get('output_tokens', 0)} out tok"
print(f"  summary: {turn} turns, {wall} wall, {n_tools} tools, denials[{den}], "
      f"{n_esc} escalations, {n_near} near-miss, stop={stop or 'stopped_by_llm'}{tok}")
PYEOF
}

row_run() { # row_run <label> <max_turns> <task>
  local label="$1" turns="$2" task="$3"
  need_fa
  mkdir -p "$LEDGER_DIR" # R4: dir exists before ANY capture copy
  local rid="cae-${label}-$(date +%s)-$$"
  local log="/tmp/cae_${rid}.log"   # unique per run: re-runs never clobber prior transcripts
  local detail="${CAE_DETAIL:-verbose}"   # CAE_DETAIL=debug adds per-event ms timing
  local events="$STATE_HOST/session-log/$rid/events.jsonl"
  rm -f "$events" 2>/dev/null || true
  echo "RID=$rid  (log: $log)"

  # Ctrl-C must not silently lose the capture (rows are token-expensive).
  trap 'echo "  [FAIL] interrupted"; { [ -f "$events" ] && cp "$events" "$LEDGER_DIR/$rid.events.jsonl"; } 2>/dev/null; append_ledger "$rid" "$label" 130 "?" "none" 0 0 0 "INTERRUPTED via=container"; exit 130' INT TERM

  local rc=0
  set +e
  "$FA" run --role chat --run-id "$rid" --max-turns "$turns" --detail "$detail" \
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

  local mode levels exp obs exh stop_reason=""
  if grep -q '"kind": "run_stopped"' "$events"; then
    stop_reason="$(grep '"kind": "run_stopped"' "$events" | tail -1 \
      | grep -o '"reason": "[^"]*"' | head -1 | cut -d'"' -f4 || true)"
  fi
  mode="$(grep -o '"recommended_mode": "[a-z_]*"' "$events" | head -1 | cut -d'"' -f4 || true)"
  levels="$(grep -o '"level_from": [0-9], "level_to": [0-9]' "$events" \
    | sed 's/"level_from": //; s/, "level_to": />/' | tr '\n' ';' || true)"
  exp="$(grep -c '"kind": "scope_expansion"' "$events" || true)"
  obs="$(grep -c '"kind": "expansion_observed"' "$events" || true)"
  exh="$(grep -c '"kind": "expansion_exhausted"' "$events" || true)"

  if [ -n "$stop_reason" ]; then
    echo "  [STOP] abnormal stop: $stop_reason (see events)"
  fi
  local vrc=0 flag=""
  if [ "$rc" -ne 0 ]; then
    vrc="$rc"
  fi
  case "$label" in
    smoke)
      if [ "$rc" -eq 0 ]; then
        echo "  [PASS] chat chain end-to-end (proxy -> chat provider -> session mechanics)"
      fi
      ;;
    l1)
      if [ "$rc" -eq 0 ] && [ "${exp:-0}" -eq 0 ]; then
        echo "  [PASS] no escalation on a safe docs task"
        # S12.6: ceremony cost is a NOTE, never a FAIL — denial counts vary
        # by model (2026-08-31 gemini l1: 2 IntentGuard denials was normal
        # enforce-mode behaviour). Expectation: <=1 once the agent knows the
        # draft flow; more means the prompt guidance is not landing.
        ig_denials="$(grep '"kind": "tool_result"' "$events" | grep -c 'IntentGuard' || true)"
        if [ "${ig_denials:-0}" -gt 1 ]; then
          echo "  [NOTE] IntentGuard denials: $ig_denials (expected <=1; ceremony friction, not a row failure)"
        else
          echo "  [OBS] IntentGuard denials: ${ig_denials:-0}"
        fi
      elif [ "${exp:-0}" -ne 0 ]; then
        # A negative control that escalates is a FINDING, not a note: the
        # row's whole purpose is "safe work must not escalate". Exit 3.
        echo "  [FAIL] UNEXPECTED scope_expansion ($exp) on the negative control — inspect $events"
        [ "$rc" -eq 0 ] && vrc=3
        flag="NEGATIVE_CONTROL_FAILED"
      fi
      ;;
    env)
      # S12.6 (CT6) + S12.6b: readiness-handoff probe. The session clone has a
      # .venv; the agent must find its pytest without archaeology (D15: 12/20
      # turns burned on 2026-08-31). S12.6b FIX (live false negative,
      # 2026-08-31 cae-env-1788177076): the console mirror shows only the tool
      # SUMMARY ("bash exited 0") — the command stdout (the pytest version
      # line) lives in the tool_result EVENT, so the version oracle greps the
      # events file (the log stays an OR-branch for a model that echoes the
      # full line). The two absence-greps are exactly the failure strings the
      # 2026-08-31 run produced; they are checked on BOTH surfaces. rc=0 with
      # a failed oracle is an objective miss -> exit 3 (v4.4 contract).
      if [ "$rc" -eq 0 ] \
         && { grep -qE 'pytest [0-9]+\.[0-9]+' "$events" || grep -qE 'pytest [0-9]+\.[0-9]+' "$log"; } \
         && ! grep -q "command not found" "$events" \
         && ! grep -q "command not found" "$log" \
         && ! grep -q "No module named pytest" "$events" \
         && ! grep -q "No module named pytest" "$log"; then
        echo "  [PASS] venv pytest reachable without archaeology (D15 fix verified)"
      else
        echo "  [FAIL] env probe: pytest not cleanly reachable — inspect $log and the captured events"
        [ "$rc" -eq 0 ] && vrc=3
        flag="ENV_PROBE_FAILED"
      fi
      ;;
    pty)
      # S12.6 (CT6): timeout -> recovery probe. The sleep's own pty attempt
      # is EXPECTED to log exactly one executor-timeout fallback; a dirty
      # pane taxes every later command (D16: 7 occurrences on 2026-08-31).
      ptys="$(grep -c 'PtyPool executor timeout' "$log" || true)"
      if grep -q "RECOVERED" "$log" && [ "${ptys:-0}" -le 1 ]; then
        echo "  [PASS] pane reclaimed after timeout; next command clean (pty preamble x${ptys:-0})"
      else
        echo "  [FAIL] pty probe: RECOVERED missing or preamble x${ptys:-0} > 1 — inspect $log"
        [ "$rc" -eq 0 ] && vrc=3
        flag="PTY_RECOVERY_FAILED"
      fi
      ;;
    l2|l3)
      if [ "${exp:-0}" -gt 0 ]; then
        echo "  [PASS] scope_expansion fired ($exp): ${levels:-?}"
      elif [ "$label" = "l2" ] && [ "$rc" -eq 0 ]; then
        # l2's objective IS the escalation; a clean run without one is a
        # missed objective (model finished in chat), distinct from a crash.
        echo "  [FAIL] expected escalation never fired within the turn cap (src/ not touched?)"
        vrc=3
        flag="NO_ESCALATION_WHERE_EXPECTED"
      else
        echo "  [NOTE] no escalation within the turn cap"
      fi
      # The evidence-name grep MUST run against the escalation events only.
      # Unanchored, it also matches the refusal text of a guard denial stored
      # in a tool_result payload — which is how a run with expansion_n=0
      # printed "[PASS] expansion evidence names present" on 2026-08-30.
      if [ "${exp:-0}" -gt 0 ]; then
        grep '"kind": "scope_expansion"' "$events" \
          | grep -qE 'read_high_arm|high_tier_write|verify_failed' \
          && echo "  [PASS] expansion evidence names present" \
          || echo "  [NOTE] escalation fired but no evidence name in it"
      fi
      if grep -q "Start here" "$log"; then
        echo "  [PASS] planner handoff map reached the workflow"
      else
        echo "  [NOTE] no handoff map in output."
        if [ "${obs:-0}" -gt 0 ]; then
          echo "        near-miss telemetry present (observed_n=$obs): the policy"
          echo "        deliberately declined to escalate. Not 'advice not taken'."
        else
          echo "        no escalation evidence at all (model finished in chat)."
        fi
      fi
      ;;
  esac
  [ "${exh:-0}" -gt 0 ] && echo "  [OBS] K budget exhausted -> operator-report path"

  local notes="auto-captured via=container stop=${stop_reason:-stopped_by_llm}"
  [ -n "$flag" ] && notes="$notes $flag"
  cp "$events" "$LEDGER_DIR/$rid.events.jsonl"
  append_ledger "$rid" "$label" "$rc" "$mode" "$levels" "$exp" "$obs" "$exh" "$notes"
  trap - INT TERM
  print_timeline "$events"
  echo "  ledger + events captured (host checkout untouched by design)"
  return "$vrc"
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
  echo "== session-manifest audit (blocking classes only; production state never swept):"
  audit_sessions
  # S12.6: print the effective operator modes so a trial row is never run
  # against a flag state the operator did not intend. Read from the HOST side
  # of the container config (~/.fa/config.yaml, config.py:40); absence of the
  # file or key means the shipped defaults.
  local cfg="$STATE_HOST/config.yaml"
  if [ -r "$cfg" ] && grep -qE '^\s*intent_guard(_|\.)mode:' "$cfg" 2>/dev/null; then
    echo "== intent_guard.mode: $(grep -oE 'intent_guard(_|\.)mode:\s*\S+' "$cfg" | head -1 | awk '{print $2}') (from $cfg)"
  else
    echo "== intent_guard.mode: enforce (default)"
  fi
  if [ -r "$cfg" ] && grep -qE '^\s*tool_batching\.enabled:' "$cfg" 2>/dev/null; then
    echo "== tool_batching.enabled: $(grep -oE 'tool_batching\.enabled:\s*\S+' "$cfg" | head -1 | awk '{print $2}') (from $cfg)"
  else
    echo "== tool_batching.enabled: true (default)"
  fi
  mkdir -p "$LEDGER_DIR"
  [ -f "$LEDGER" ] || echo "$HDR" > "$LEDGER"
  echo "== ledger: $LEDGER"
  echo "READY. Rows: smoke -> env -> pty -> l1 -> l2 -> l3 -> l4 (no git steps between rows; commit the ledger at the end)"
}

cmd_smoke() {
  row_run smoke 2 "Reply with the single word OK and nothing else. Do not use any tools."
}

cmd_l1() {
  row_run l1 8 "Create live-check-notes.md (or append one line to it) noting the live sheet was checked today."
}

cmd_env() {
  # S12.6: 6-turn cap — enforce-mode IntentGuard ceremony can cost >=2 turns
  # before the probe even runs (live evidence: 2026-08-31 l2 t9), so a 2-turn
  # cap was unachievable in the default mode.
  row_run env 6 "Using bash, run \`pytest --version\` in this workspace and reply with only the version."
}

cmd_pty() {
  row_run pty 6 "Run \`sleep 35\` via bash (it will time out — that is expected), then run \`echo RECOVERED\` and reply with its output."
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
trial = [r for r in rows if str(r.get("run_id", "")).startswith("cae-")]
print(f"  this trial (cae-*): {len(trial)} row(s)")
for r in trial[-8:]:
    print("   ", r.get("run_id"), "| role=", r.get("role"), "| exit=", r.get("exit_code"),
          "| stop=", r.get("stop_reason", "?"))
'
  echo "== calibration:"
  "$FA" stats --calibration 2>&1 1>/dev/null | head -40
}

cmd_ledger() {
  [ -f "$LEDGER" ] || die "no ledger yet at $LEDGER"
  column -s, -t < "$LEDGER" 2>/dev/null || cat "$LEDGER"
  echo "($(($(wc -l < "$LEDGER") - 1)) row(s))"
}

case "${1:-}" in
  setup)  cmd_setup ;;
  smoke)  cmd_smoke ;;
  env)    cmd_env ;;
  pty)    cmd_pty ;;
  l1)     cmd_l1 ;;
  l2)     cmd_l2 ;;
  l3)     cmd_l3 ;;
  l4)     cmd_l4 ;;
  ledger) cmd_ledger ;;
  *)
    echo "usage: scripts/run_live_check.sh {setup|smoke|env|pty|l1|l2|l3|l4|ledger}" >&2
    exit 2
    ;;
esac
