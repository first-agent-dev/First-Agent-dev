#!/usr/bin/env bash
# Live (provider-backed) trial of the complexity-aware chat contour.
#
# Unlike scripts/verify_complexity_aware_execution.py (which proves the off-LLM
# engine with NO provider), this script drives a REAL `fa run --role chat` and
# then measures the deterministic signals the engine leaves behind. It cannot
# self-oracle the model's choices; it reports what happened and flags the
# deterministic scaffolding.
#
# Isolation (S10.9 / D-H2 — claims below are enforced by this script, not hoped):
#   - the agent's workspace is a throwaway `git worktree` of HEAD under a temp
#     dir, so the trial's writes can NEVER touch your checkout (the agent's own
#     edits inside the worktree are the trial's data);
#   - a unique --run-id per invocation;
#   - an isolated FA_STATE_ROOT, so your ~/.fa (history, session logs, config
#     reads excepted) is untouched;
#   - artifacts are kept for inspection; pass --clean to remove the temp dir
#     AND prune the worktree registration.
#
# SIGNAL SOURCE (S10.9 / GAP-H10): the engine's durable footprint lives in the
# session event log ($FA_STATE_ROOT/session-log/<run-id>/events.jsonl), NOT in
# console output — scope_expansion/expansion_exhausted are console-mirrored as
# one-liners, but the machine-readable oracle is the JSONL. This script greps
# the JSONL. The console tee is kept as narrative only.
#
# Usage:
#   scripts/run_live_expansion_trial.sh "the task to run" [max_turns] [workspace]
#   scripts/run_live_expansion_trial.sh --clean "the task" 20   # run, then clean
#   scripts/run_live_expansion_trial.sh --clean                 # sweep leftovers only
#
# Requires: `fa` on PATH (or .venv/bin/fa), git >= 2.5 for the default worktree
# isolation, and a top-level `chat:` key in ~/.fa/models.yaml (preflighted).
set -uo pipefail

CLEAN=0
if [ "${1:-}" = "--clean" ]; then CLEAN=1; shift; fi

TASK="${1:-simplify the main function in a small module without changing behaviour}"
MAX_TURNS="${2:-20}"
WORKSPACE_ARG="${3:-}"

# ── Bare --clean (no task): sweep ALL leftover trial dirs + worktrees, exit. ──
# Cleanup must never require a provider, config, or secrets (live-fix #5).
if [ "$CLEAN" = "1" ] && [ "$#" -eq 0 ]; then
  REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || REPO="$(cd "$(dirname "$0")/.." && pwd)"
  shopt -s nullglob
  TRIAL_DIRS=(/tmp/fa-live-trial-*)
  shopt -u nullglob
  if [ "${#TRIAL_DIRS[@]}" -eq 0 ]; then
    echo "no trial dirs under /tmp/fa-live-trial-* — nothing to clean"
  fi
  for d in "${TRIAL_DIRS[@]}"; do
    [ -d "$d/worktree" ] && git -C "$REPO" worktree remove --force "$d/worktree" >/dev/null 2>&1
    rm -rf "$d"
    echo "removed $d"
  done
  git -C "$REPO" worktree prune
  echo "worktree registry pruned"
  exit 0
fi

# Locate fa + repo.
# NOTE: not `git ... || cd ... && pwd` — that parses as (A||B)&&C and appends
# pwd's output when git succeeds (caught live 2026-08-29: two-line REPO broke
# the -x test and fell through to the compose wrapper).
REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || REPO="$(cd "$(dirname "$0")/.." && pwd)"
FA="${FA:-$REPO/.venv/bin/fa}"
[ -x "$FA" ] || FA="$(command -v fa || true)"
if [ -z "$FA" ] || [ ! -x "$FA" ]; then
  echo "ERROR: 'fa' not found on PATH or in $REPO/.venv/bin. Run 'uv sync --extra dev' first." >&2
  exit 2
fi

# Refuse the docker-compose wrapper (scripts/fa): it delegates inside the agent
# container, which cannot see this host worktree (S10.9 live-sheet fix #2).
case "$(readlink -f "$FA" 2>/dev/null || echo "")" in
  */scripts/fa)
    echo "ERROR: \$FA resolves to scripts/fa (docker-compose wrapper -> container)." >&2
    echo "       Run 'uv sync' in the repo, or set FA=/path/to/repo/.venv/bin/fa." >&2
    exit 2 ;;
esac

TRIAL_DIR="$(mktemp -d -t fa-live-trial-XXXXXX)"
export FA_STATE_ROOT="$TRIAL_DIR/state"
mkdir -p "$FA_STATE_ROOT"
LOG="$TRIAL_DIR/live.log"
RID="s10-live-$(date +%s)-$$"
EVENTS="$FA_STATE_ROOT/session-log/$RID/events.jsonl"

# Secrets (live-fix #4b, 2026-08-29): fa reads a FILE-ONLY secret store whose
# default path resolves under FA_STATE_ROOT — which this script isolates, so
# ~/.fa/.env would be invisible. Bridge the host secrets file in explicitly.
if [ -z "${FA_SECRETS_FILE:-}" ] && [ -r "${HOME}/.fa/.env" ]; then
  export FA_SECRETS_FILE="${HOME}/.fa/.env"
fi
if [ -n "${FA_SECRETS_FILE:-}" ] && [ ! -r "${FA_SECRETS_FILE}" ]; then
  echo "ERROR: FA_SECRETS_FILE=${FA_SECRETS_FILE} exists but is not readable by $(id -un)." >&2
  echo "       Production secret files are usually root-only — copy instead of pointing:" >&2
  echo "         sudo cp <prod fa.env> ~/.fa/.env && sudo chown $(id -un): ~/.fa/.env && chmod 600 ~/.fa/.env" >&2
  [ -n "${WORKTREE_DIR:-}" ] && git -C "$REPO" worktree remove --force "$WORKTREE_DIR" >/dev/null 2>&1
  rm -rf "$TRIAL_DIR"
  exit 2
fi
if [ -z "${FA_SECRETS_FILE:-}" ] && [ ! -f /run/secrets/fa.env ]; then
  echo "ERROR: no provider secrets (checked FA_SECRETS_FILE, ${HOME}/.fa/.env, /run/secrets/fa.env)." >&2
  echo "       Create ${HOME}/.fa/.env with KEY=value lines (chmod 600), or export" >&2
  echo "       FA_SECRETS_FILE=/path/to/fa.env. The isolated FA_STATE_ROOT hides the" >&2
  echo "       default location from fa." >&2
  [ -n "${WORKTREE_DIR:-}" ] && git -C "$REPO" worktree remove --force "$WORKTREE_DIR" >/dev/null 2>&1
  rm -rf "$TRIAL_DIR"
  exit 2
fi

# ── Workspace isolation (S10.9 / D-H2): default to a throwaway worktree. ──
WORKTREE_DIR=""
WS="${WORKSPACE_ARG:-}"
if [ -z "$WS" ]; then
  if git -C "$REPO" worktree add --detach "$TRIAL_DIR/worktree" HEAD >/dev/null 2>&1; then
    WORKTREE_DIR="$TRIAL_DIR/worktree"
    WS="$WORKTREE_DIR"
  else
    echo "WARNING: 'git worktree add' failed — the trial would run against your REAL repo." >&2
    printf "Type 'yes' to run in-repo anyway (your checkout may be edited), anything else aborts: " >&2
    read -r REPLY
    if [ "${REPLY:-}" = "yes" ]; then
      WS="$REPO"
    else
      rm -rf "$TRIAL_DIR"
      echo "Aborted; nothing was run." >&2
      exit 2
    fi
  fi
fi

# ── Preflight: the chat role must be configured (fail fast, not mid-run). ──
# FA_MODELS_CONFIG lets operators point at an existing (e.g. production)
# models.yaml instead of copying one into ~/.fa (live-fix #4, 2026-08-29:
# a MISSING file used to sail through this preflight and die mid-run with
# "role 'chat' not found" after the worktree was already built).
MODELS_YAML="${FA_MODELS_CONFIG:-${HOME}/.fa/models.yaml}"
if [ ! -f "$MODELS_YAML" ]; then
  echo "ERROR: no models config at $MODELS_YAML — host-side fa has no model routes." >&2
  echo "       Create one from knowledge/templates/models.yaml.example (needs a" >&2
  echo "       top-level 'chat:' role), or set FA_MODELS_CONFIG=/path/to/models.yaml." >&2
  [ -n "$WORKTREE_DIR" ] && git -C "$REPO" worktree remove --force "$WORKTREE_DIR" >/dev/null 2>&1
  rm -rf "$TRIAL_DIR"
  exit 2
fi
if ! grep -qE '^chat:' "$MODELS_YAML"; then
  echo "ERROR: no top-level 'chat:' key in $MODELS_YAML — the chat role cannot run." >&2
  [ -n "$WORKTREE_DIR" ] && git -C "$REPO" worktree remove --force "$WORKTREE_DIR" >/dev/null 2>&1
  rm -rf "$TRIAL_DIR"
  exit 2
fi

echo "=================================================================="
echo " LIVE EXPANSION TRIAL"
echo "   fa:        $FA"
echo "   run-id:    $RID"
echo "   workspace: $WS"
if [ -n "$WORKTREE_DIR" ]; then
  echo "              (throwaway git worktree — your checkout is untouched)"
fi
echo "   state:     $FA_STATE_ROOT (isolated; your ~/.fa is untouched)"
echo "   events:    $EVENTS"
echo "   max-turns: $MAX_TURNS"
echo "   task:      $TASK"
echo "   log:       $LOG (console narrative)"
echo "=================================================================="

# Preflight: the chat role must be runnable.
if ! "$FA" run --help >/dev/null 2>&1; then
  echo "ERROR: 'fa run' unavailable." >&2; exit 2
fi

set +e
CONFIG_ARG=()
[ -n "${FA_MODELS_CONFIG:-}" ] && CONFIG_ARG=(--config "$FA_MODELS_CONFIG")
"$FA" run --role chat --run-id "$RID" --workspace "$WS" \
  --max-turns "$MAX_TURNS" --detail verbose "${CONFIG_ARG[@]}" --task "$TASK" >"$LOG" 2>&1
RC=$?
set -e
echo
echo "fa EXIT=$RC (console: $(wc -l <"$LOG") log lines)"
echo
echo "------------------------------------------------------------------"
echo " DETERMINISTIC SIGNALS (from the durable event log, not console)"
echo "------------------------------------------------------------------"

if [ ! -f "$EVENTS" ]; then
  echo "  [NOTE] no events.jsonl at $EVENTS — did the session start?"
else
  count() { grep -c "\"kind\": \"$1\"" "$EVENTS" 2>/dev/null || true; }

  n_exp="$(count scope_expansion)"
  n_obs="$(count expansion_observed)"
  n_exh="$(count expansion_exhausted)"
  n_wf="$(grep -c invoke_workflow "$LOG" 2>/dev/null || true)"
  n_map="$(grep -c 'Start here' "$LOG" 2>/dev/null || true)"

  printf "  %-42s %s\n" "scope_expansion events (posture changes):" "${n_exp:-0}"
  printf "  %-42s %s\n" "  evidence names seen:" \
    "$(grep -oE 'read_high_arm|high_tier_write|verify_failed' "$EVENTS" | sort -u | tr '\n' ' ')"
  printf "  %-42s %s\n" "expansion_observed events (near-miss):" "${n_obs:-0}"
  printf "  %-42s %s\n" "expansion_exhausted (K spent):" "${n_exh:-0}"
  printf "  %-42s %s\n" "invoke_workflow mentioned (console):" "${n_wf:-0}"
  printf "  %-42s %s\n" "planner handoff file-map ('Start here'):" "${n_map:-0}"

  echo
  echo "  level transitions (level_from -> level_to):"
  grep -oE '"level_from": [0-9]+, "level_to": [0-9]+' "$EVENTS" | sort -u | sed 's/^/    /' || true
fi

echo
echo "------------------------------------------------------------------"
echo " READING THE RESULT (not auto-asserted — model choice is live)"
echo "------------------------------------------------------------------"
echo "  - a docs-only task should show ~0 scope_expansion;"
echo "    a src/ task should show read_high_arm (->2) and/or high_tier_write (->3)."
echo "  - escalation is ADVICE: the model may accept (invoke_workflow + 'Start here')"
echo "    or finish in chat. The durable truth is the events.jsonl rows above."
echo "  - expansion_observed rows are the near-miss telemetry feeding S11 tuning;"
echo "    they never escalate anything by themselves."
echo "  - K budget: a denied (K+1)-th escalation shows expansion_exhausted and a"
echo "    terminal 'report to operator' line."

echo
echo "Trial artifacts kept in: $TRIAL_DIR"
if [ "$CLEAN" -eq 1 ]; then
  [ -n "$WORKTREE_DIR" ] && git -C "$REPO" worktree remove --force "$WORKTREE_DIR" >/dev/null 2>&1
  rm -rf "$TRIAL_DIR"
  echo "(--clean removed the trial dir and worktree)"
elif [ -n "$WORKTREE_DIR" ]; then
  echo "(worktree still registered; 'git -C $REPO worktree remove --force $WORKTREE_DIR' or run bare --clean to sweep all trials)"
fi
exit "$RC"
