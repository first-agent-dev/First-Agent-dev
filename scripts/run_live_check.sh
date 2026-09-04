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

row_run() { # row_run <label> <max_turns> <task> [assert_hook]
  # assert_hook (S12.7): optional function called as `hook <events> <log> <rc>`
  # AFTER the run and BEFORE the ledger append. It prints [PASS]/[FAIL] lines and
  # may set the caller-scoped `vrc` / `flag` (bash dynamic scoping) to record an
  # objective miss. Existing rows pass no hook and keep their `case` verdicts.
  local label="$1" turns="$2" task="$3" hook="${4:-}"
  need_fa
  mkdir -p "$LEDGER_DIR" # R4: dir exists before ANY capture copy
  local rid="cae-${label}-$(date +%s)-$$"
  local log="/tmp/cae_${rid}.log"   # unique per run: re-runs never clobber prior transcripts
  local detail="${CAE_DETAIL:-verbose}"   # CAE_DETAIL=debug adds per-event ms timing
  local events="$STATE_HOST/session-log/$rid/events.jsonl"
  rm -f "$events" 2>/dev/null || true
  # S12.7 residual-gap radar: every live task also asks the model to grade the
  # agentic tools it just used. The model-visible framed string is NOT logged
  # (events keep the full raw, RD-1), so the model's own words are the only
  # direct window into what it SAW — confusing output, silent truncation, lost
  # context. Appended to EVERY row (s127 + the legacy s10 rows). Disable with
  # CAE_SELFREPORT=0. The block is extracted by print_self_report below.
  if [ "${CAE_SELFREPORT:-1}" != "0" ]; then task="${task}${SELF_REPORT}"; fi
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
  # S12.7: run the row's assert hook (if any) AFTER the legacy case verdicts and
  # BEFORE the ledger append, so a hook-set `flag` lands in the ledger notes and
  # a hook-set `vrc` becomes the row's exit code. Hooks rely on bash dynamic
  # scoping to assign this function's local `vrc` / `flag`.
  if [ -n "$hook" ]; then "$hook" "$events" "$log" "$rc"; fi
  [ "${exh:-0}" -gt 0 ] && echo "  [OBS] K budget exhausted -> operator-report path"

  local notes="auto-captured via=container stop=${stop_reason:-stopped_by_llm}"
  [ -n "$flag" ] && notes="$notes $flag"
  cp "$events" "$LEDGER_DIR/$rid.events.jsonl"
  append_ledger "$rid" "$label" "$rc" "$mode" "$levels" "$exp" "$obs" "$exh" "$notes"
  trap - INT TERM
  print_timeline "$events"
  print_self_report "$events"
  echo "  ledger + events captured (host checkout untouched by design)"
  return "$vrc"
}

# ── S12.7 e2e suite ──────────────────────────────────────────────────────────
# Live verification that S12.7 closed the gaps that blocked the S10 rows (the
# l2 LoopGuard path-thrash, D10/GAP1) and that every touched module serves its
# function under real agent behaviour. Each row = one bounded `fa run` session +
# assertions over its events.jsonl. Oracles, in rank order:
#   1. structural  — tool_call params, tool_result artifacts/ok, guard events
#   2. behavioural — the tool_call SEQUENCE (ladder, resume-follow, artifact-follow)
#   3. self-report — the model's own TOOL_FEEDBACK block (the only direct window
#                    into the model-visible framed string, which events do NOT log)
# Run after PR merge + `fa update`, pinned single model. Full model text prints
# every turn (CAE_LLM_FULL defaults to 1 below); CAE_LLM_FULL=0 restores the cap.

# Appended to EVERY live task (s127 + legacy s10 rows). The exact marker line
# TOOL_FEEDBACK: is what print_self_report greps for.
SELF_REPORT='

---
You are operating in a dev environment as part of an agentic-tool evaluation. Before you finish, reflect on the agentic tools you just used (fs_read_file, fs_search, fs_run_bash, and any others). End your FINAL message with a block whose first line is exactly "TOOL_FEEDBACK:" and then answer, specifically and critically:
- confusing output? (which tool, what was unclear)
- truncated? (did any result feel cut off; did the framing tell you how to continue?)
- lost context? (did you lose track of where you were or what you had already read?)
- worked as expected? (which tools behaved well)
- anything that cost you a wasted turn or a guess.
This is used to find residual tool defects, so be honest and concrete.'

print_self_report() { # print_self_report <events.jsonl> — surface the model's tool-UX self-report
  "$PY" - "$1" <<'PYEOF' || echo "  [WARN] self-report parse failed"
import json, sys
last = None
for line in open(sys.argv[1], encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    try:
        e = json.loads(line)
    except Exception:
        continue
    if e.get("kind") == "model_msg":
        txt = str((e.get("content") or {}).get("text") or "")
        if "TOOL_FEEDBACK:" in txt:
            last = txt
print("  ── model tool-UX self-report (residual-gap radar) ──")
if last is None:
    print("  [NOTE] no TOOL_FEEDBACK block found — the model did not comply; record it")
else:
    for ln in last[last.index("TOOL_FEEDBACK:"):].rstrip().splitlines():
        print("  📝 " + ln)
PYEOF
}

s127_expect() { # s127_expect <events> <log> <desc> <present|absent> <egrep> [events|log]
  local ev="$1" lg="$2" desc="$3" mode="$4" pat="$5" src="${6:-events}"
  local f="$ev"; [ "$src" = "log" ] && f="$lg"
  local hit=1
  grep -qE "$pat" "$f" 2>/dev/null && hit=0
  if { [ "$mode" = "present" ] && [ "$hit" -eq 0 ]; } || { [ "$mode" = "absent" ] && [ "$hit" -eq 1 ]; }; then
    echo "  [PASS] $desc"
  else
    echo "  [FAIL] $desc  (expected $mode: /$pat/ in $src)"
    S127_ROW_FAILED=1
  fi
}

s127_expect_count() { # s127_expect_count <events> <desc> <min> <egrep>
  local ev="$1" desc="$2" min="$3" pat="$4"
  # `|| true` (not `|| echo 0`): grep -c already prints 0 on no-match but exits
  # 1; `|| echo 0` would append a SECOND 0 ("0\n0") and break the integer test.
  # `|| true` keeps grep's own 0 and stays set -e safe.
  local n; n="$(grep -cE "$pat" "$ev" 2>/dev/null || true)"; n="${n:-0}"
  if [ "$n" -ge "$min" ]; then
    echo "  [PASS] $desc (n=$n)"
  else
    echo "  [FAIL] $desc  (expected >=$min matches of /$pat/, got ${n:-0})"
    S127_ROW_FAILED=1
  fi
}

s127_finish() { # s127_finish <FLAG> — set vrc/flag if any expectation failed
  if [ "${S127_ROW_FAILED:-0}" = "1" ]; then vrc=3; flag="$1"; fi
}

s127_row() { # s127_row <name> <turns> <task> <hook>
  # S12.7: print the FULL model text every turn for the gate rows (the operator
  # reads the model's own words to find residual gaps). Scoped to this row's
  # invocation only — legacy rows keep the S12.6c 2000-char default cap that
  # tests/test_live_check_script.py's battery pins. CAE_LLM_FULL=0 overrides.
  export CAE_LLM_FULL="${CAE_LLM_FULL:-1}"
  row_run "s127-$1" "$2" "$3" "$4"
}

# ── GUARD (S1) — the gap-closure headline ─────────────────────────────────────

cmd_s127_advancing() { # GAP1/D10 closure: 5 distinct advancing reads must NOT trip the guard
  s127_row advancing 14 \
    "Read src/fa/cli.py in five separate, DIFFERENT windows to understand its structure: lines 1-150, then 900-1050, then 1800-1950, then 2700-2850, then 3300-3450. After each read note one thing you learned. Do not re-read the same window." \
    s127_assert_advancing
}
s127_assert_advancing() {
  S127_ROW_FAILED=0
  s127_expect "$1" "$2" "no LoopGuard stop on 5 advancing reads (D10/GAP1 closed)" absent '"reason": "LoopGuard'
  s127_expect "$1" "$2" "advancing reads were served (fs_read_file ran)" present '"tool_name": "fs_read_file"'
  s127_expect "$1" "$2" "session ended normally (no abnormal stop)" absent '"kind": "run_stopped"'
  s127_finish "S127_ADVANCING_FAILED"
}

cmd_s127_repeat() { # Detector 1: identical repeat still warns then denies, in-band, with the prefix
  s127_row repeat 12 \
    "Read lines 1-40 of src/fa/cli.py. Then read the EXACT same lines 1-40 again. Repeat this identical read five times total. After the fifth, stop and report what the tool told you." \
    s127_assert_repeat
}
s127_assert_repeat() {
  S127_ROW_FAILED=0
  s127_expect "$1" "$2" "identical-repeat produced a guard signal (warn or deny)" present '"kind": "loop_guard_warn"|"reason": "LoopGuard'
  s127_finish "S127_REPEAT_FAILED"
}

cmd_s127_pingpong() { # Detector 3 (preventive): exact A-B alternation warns at 3 cycles, denies at 4
  s127_row pingpong 14 \
    "Alternate two reads exactly eight times: read lines 1-30 of src/fa/cli.py, then lines 1-30 of src/fa/__init__.py, then lines 1-30 of src/fa/cli.py again, and so on, strictly alternating. After eight reads, stop." \
    s127_assert_pingpong
}
s127_assert_pingpong() {
  S127_ROW_FAILED=0
  # Preventive/field-driven detector: a miss is a NOTE, not a row failure (RK3/RN11).
  if grep -qE '"kind": "loop_guard_warn"|"reason": "LoopGuard' "$1" 2>/dev/null; then
    echo "  [PASS] ping-pong alternation produced a guard signal"
  else
    echo "  [NOTE] no ping-pong signal — preventive detector; confirm the model truly alternated (see timeline)"
  fi
}

# ── READ FRAMES + BUDGET (S2/S4/S6) ───────────────────────────────────────────

cmd_s127_read_small() { # T1: a small file arrives whole and inline, no artifact
  s127_row read-small 8 \
    "Read the entire file src/fa/__init__.py (it is small) and report its full contents." \
    s127_assert_read_small
}
s127_assert_read_small() {
  S127_ROW_FAILED=0
  s127_expect "$1" "$2" "small read served" present '"tool_name": "fs_read_file"'
  s127_expect "$1" "$2" "small read stayed INLINE (no artifact minted)" absent 'tool-result-[0-9a-f]{16}'
  s127_finish "S127_READ_SMALL_FAILED"
}

cmd_s127_read_oversize() { # T3 + CT6 audit: oversize read elides to an artifact; events keep full raw, no preview key
  s127_row read-oversize 10 \
    "Read the entire file src/fa/cli.py with NO line window. It is large. Report how many lines it has and exactly what the framing/truncation notice told you." \
    s127_assert_read_oversize
}
s127_assert_read_oversize() {
  S127_ROW_FAILED=0
  s127_expect "$1" "$2" "oversize read minted an artifact (elision fired at the ceiling)" present 'tool-result-[0-9a-f]{16}'
  s127_expect "$1" "$2" "events carry the full raw, NOT a 500-char preview (CT6/RD-1)" absent '"preview":'
  s127_finish "S127_READ_OVERSIZE_FAILED"
}

cmd_s127_read_window() { # T2: windowed read shows a resume line; following it returns the contiguous next block
  s127_row read-window 12 \
    "Read lines 3300-3400 of src/fa/cli.py. Then follow the resume instruction the result gives you to read the next block. Report whether the two blocks were contiguous (no gap, no overlap)." \
    s127_assert_read_window
}
s127_assert_read_window() {
  S127_ROW_FAILED=0
  s127_expect "$1" "$2" "windowed read used a start_line" present '"start_line":'
  s127_expect_count "$1" "resume was followed (>=2 fs_read_file calls)" 2 '"kind": "tool_call".*"tool_name": "fs_read_file"'
  s127_finish "S127_READ_WINDOW_FAILED"
}

# ── ARTIFACTS (S3) ────────────────────────────────────────────────────────────

cmd_s127_artifact_follow() { # CT7: an [artifact: id] pointer is followable to the full payload
  s127_row artifact-follow 12 \
    "Read all of src/fa/cli.py (it will be truncated with an [artifact: ...] reference). Then call fs_read_file with that artifact_id to recover the full content. Report the total line count." \
    s127_assert_artifact_follow
}
s127_assert_artifact_follow() {
  S127_ROW_FAILED=0
  s127_expect "$1" "$2" "an artifact was minted by the oversize read" present 'tool-result-[0-9a-f]{16}'
  s127_expect "$1" "$2" "the artifact_id was followed (read by artifact_id)" present '"artifact_id":'
  s127_finish "S127_ARTIFACT_FOLLOW_FAILED"
}

cmd_s127_artifact_unknown() { # CT7: a fabricated id fails closed with steering; the session continues
  s127_row artifact-unknown 8 \
    "Call fs_read_file with artifact_id set to tool-result-0000000000000000 (a fabricated id). Report exactly what the tool said." \
    s127_assert_artifact_unknown
}
s127_assert_artifact_unknown() {
  S127_ROW_FAILED=0
  s127_expect "$1" "$2" "unknown id failed closed (artifact_not_found steering)" present 'artifact_not_found|not_found|No such artifact|unknown artifact'
  s127_expect "$1" "$2" "session continued (no abnormal stop on a bad id)" absent '"kind": "run_stopped"'
  s127_finish "S127_ARTIFACT_UNKNOWN_FAILED"
}

# ── RUN_BASH TAIL FRAME (S5) ──────────────────────────────────────────────────

cmd_s127_bash_tail() { # CT4: >30KB stdout is tail-biased; the tail marker survives, an artifact stores the rest
  s127_row bash-tail 10 \
    "Run a bash command that prints 40000 numbered lines with the literal text START_MARKER on the first line and END_MARKER on the last (for example: { echo START_MARKER; seq 1 40000; echo END_MARKER; }). Report whether you can see END_MARKER and whether the output was truncated." \
    s127_assert_bash_tail
}
s127_assert_bash_tail() {
  S127_ROW_FAILED=0
  s127_expect "$1" "$2" "bash ran" present '"tool_name": "fs_run_bash"'
  s127_expect "$1" "$2" "oversize bash output flagged truncated and/or stored" present '"truncated": true|tool-result-[0-9a-f]{16}'
  s127_finish "S127_BASH_TAIL_FAILED"
}

cmd_s127_bash_stderr() { # CT4: stderr is preserved in the last bytes of the visible result
  s127_row bash-stderr 10 \
    "Run a bash command that fails with a long stderr traceback (for example: python3 -c 'import sys; print(\"x\"*4000, file=sys.stderr); raise SystemExit(2)'). Report the actual error text you saw at the end." \
    s127_assert_bash_stderr
}
s127_assert_bash_stderr() {
  S127_ROW_FAILED=0
  s127_expect "$1" "$2" "failing bash ran" present '"tool_name": "fs_run_bash"'
  # A non-zero exit is surfaced in the result SUMMARY ("bash exited N",
  # run_bash.py:186/289) — never in the task text, so this cannot false-pass on
  # the prompt. The stderr-TEXT preservation itself is the model's self-report
  # (the visible result's last bytes), read from the timeline/📝 block.
  s127_expect "$1" "$2" "the non-zero exit was surfaced (bash exited N)" present 'bash exited [1-9]|"ok": false'
  s127_finish "S127_BASH_STDERR_FAILED"
}

cmd_s127_bash_small() { # CT4 complement: small output is whole, unflagged, artifactless
  s127_row bash-small 8 \
    "Run \`echo hello\` and then \`ls\` via bash. Report both outputs." \
    s127_assert_bash_small
}
s127_assert_bash_small() {
  S127_ROW_FAILED=0
  s127_expect "$1" "$2" "small bash ran" present '"tool_name": "fs_run_bash"'
  s127_expect "$1" "$2" "small output stayed inline (no artifact)" absent 'tool-result-[0-9a-f]{16}'
  s127_finish "S127_BASH_SMALL_FAILED"
}

# ── FS_SEARCH SURFACE (S7a/S7b/S8) ────────────────────────────────────────────

cmd_s127_outline() { # CT9 + ladder: outline gives exact ranges that paste into a windowed read
  s127_row outline 14 \
    "Use fs_search with output_mode='outline' on src/fa/cli.py to list its functions with line ranges. Find the _cmd_stats function's exact start and end lines, then fs_read_file exactly that range. Report whether the outline's range matched the code you read." \
    s127_assert_outline
}
s127_assert_outline() {
  S127_ROW_FAILED=0
  s127_expect "$1" "$2" "outline mode was used" present '"output_mode": "outline"'
  # `_cmd_stats.*"kind": "tool_result"` matches only a tool_result whose payload
  # carries the symbol — NOT the user_msg task text (which also names _cmd_stats
  # but is followed by "kind": "user_msg"). Keys serialize alphabetically, so
  # content (with the symbol) always precedes "kind" on the line.
  s127_expect "$1" "$2" "a tool result carried the _cmd_stats symbol" present '_cmd_stats.*"kind": "tool_result"'
  s127_expect "$1" "$2" "the range was read back (windowed read followed)" present '"start_line":'
  s127_finish "S127_OUTLINE_FAILED"
}

cmd_s127_search_modes() { # CT8: no-query files listing + matches grep, current row shapes
  s127_row search-modes 12 \
    "First call fs_search with NO query to list the files under src/fa/inner_loop/. Then call fs_search in matches mode for the token 'LoopGuard'. Report the shape of the rows each mode returned." \
    s127_assert_search_modes
}
s127_assert_search_modes() {
  S127_ROW_FAILED=0
  s127_expect "$1" "$2" "fs_search ran" present '"tool_name": "fs_search"'
  s127_expect "$1" "$2" "matches mode was exercised" present '"output_mode": "matches"|"query":'
  s127_finish "S127_SEARCH_MODES_FAILED"
}

cmd_s127_search_leniency() { # CT11: all six removed knobs are accepted-but-ignored with warnings, not rejected
  s127_row search-leniency 10 \
    "Call fs_search ONCE passing ALL of these together: query='LoopGuard', context_lines=3, glob='*.py', case_sensitive=true, max_file_size=999, include_tests=true, order='bm25'. Report what the tool said about those parameters." \
    s127_assert_search_leniency
}
s127_assert_search_leniency() {
  S127_ROW_FAILED=0
  s127_expect "$1" "$2" "the call carried a removed knob" present '"context_lines"|"case_sensitive"|"include_tests"|"max_file_size"|"order"|"glob"'
  s127_expect "$1" "$2" "leniency: the call was NOT rejected (no schema/enum error)" absent 'additional_properties|not allowed|unknown mode|invalid.*param'
  s127_finish "S127_SEARCH_LENIENCY_FAILED"
}

cmd_s127_search_removed_mode() { # CT8/GAP12: a removed mode steers (no alias); the model re-issues with matches
  s127_row search-removed-mode 12 \
    "Call fs_search with output_mode='regions' and query='LoopGuard'. If it errors, do what the error tells you and try again. Report what happened." \
    s127_assert_search_removed_mode
}
s127_assert_search_removed_mode() {
  S127_ROW_FAILED=0
  s127_expect "$1" "$2" "the removed mode was attempted" present '"output_mode": "regions"'
  s127_expect "$1" "$2" "recovery: a valid mode was issued afterwards" present '"output_mode": "matches"|"output_mode": "files"|"output_mode": "outline"'
  s127_finish "S127_SEARCH_REMOVED_MODE_FAILED"
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
  echo "       S12.7 gate (run FIRST after merge + fa update): scripts/run_live_check.sh s127-list"
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
  # ── S12.7 e2e suite (run after PR merge + `fa update`, pinned model) ──
  s127-advancing)          cmd_s127_advancing ;;
  s127-repeat)             cmd_s127_repeat ;;
  s127-pingpong)           cmd_s127_pingpong ;;
  s127-read-small)         cmd_s127_read_small ;;
  s127-read-oversize)      cmd_s127_read_oversize ;;
  s127-read-window)        cmd_s127_read_window ;;
  s127-artifact-follow)    cmd_s127_artifact_follow ;;
  s127-artifact-unknown)   cmd_s127_artifact_unknown ;;
  s127-bash-tail)          cmd_s127_bash_tail ;;
  s127-bash-stderr)        cmd_s127_bash_stderr ;;
  s127-bash-small)         cmd_s127_bash_small ;;
  s127-outline)            cmd_s127_outline ;;
  s127-search-modes)       cmd_s127_search_modes ;;
  s127-search-leniency)    cmd_s127_search_leniency ;;
  s127-search-removed-mode) cmd_s127_search_removed_mode ;;
  s127|s127-list)
    echo "S12.7 e2e rows (run in order; each is one bounded live session):"
    echo "  s127-advancing   GAP1/D10 closure: 5 advancing reads, no LoopGuard  <- headline"
    echo "  s127-repeat      identical repeat warns/denies in-band (Detector 1)"
    echo "  s127-pingpong    A-B alternation warns@3/denies@4 (Detector 3, preventive)"
    echo "  s127-read-small  small read inline, no artifact (T1)"
    echo "  s127-read-oversize  oversize read elides to artifact; events full raw (T3/CT6)"
    echo "  s127-read-window  windowed read + resume contiguous (T2)"
    echo "  s127-artifact-follow  [artifact:id] followable to full payload (CT7)"
    echo "  s127-artifact-unknown  fabricated id fails closed + steers (CT7)"
    echo "  s127-bash-tail   >30KB stdout tail-biased + stored (CT4)"
    echo "  s127-bash-stderr stderr preserved in last bytes (CT4)"
    echo "  s127-bash-small  small output whole, artifactless (CT4)"
    echo "  s127-outline     outline ranges paste into a windowed read (CT9/ladder)"
    echo "  s127-search-modes  no-query files + matches shapes (CT8)"
    echo "  s127-search-leniency  six removed knobs ignored, not rejected (CT11)"
    echo "  s127-search-removed-mode  removed mode steers; model re-issues (GAP12)"
    echo "offline-pinned (NOT live rows; see rev5 sheet §4): registry scatter,"
    echo "  description ladder, PauseGuard sentinel, compaction, >200KB skip, pty parity."
    ;;
  *)
    echo "usage: scripts/run_live_check.sh {setup|smoke|env|pty|l1|l2|l3|l4|ledger|s127-list|s127-<row>}" >&2
    echo "       s127 rows: scripts/run_live_check.sh s127-list" >&2
    exit 2
    ;;
esac
