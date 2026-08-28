#!/usr/bin/env bash
# Live (provider-backed) trial of the complexity-aware chat contour.
#
# Unlike scripts/verify_complexity_aware_execution.py (which proves the off-LLM
# engine with NO provider), this script drives a REAL `fa run --role chat` and
# then measures the deterministic signals the engine is supposed to leave
# behind. It cannot self-oracle the model's choices; it reports what happened
# and flags the deterministic scaffolding.
#
# Safe + idempotent:
#   - runs in a throwaway workspace copy under a temp dir (your repo is never
#     edited by the trial itself),
#   - a unique --run-id per invocation,
#   - uses an isolated FA_STATE_ROOT so your ~/.fa global history is untouched,
#   - removes nothing on exit (keeps the log for inspection); pass --clean to
#     remove the temp dir afterwards.
#
# Usage:
#   scripts/run_live_expansion_trial.sh "the task to run" [max_turns] [workspace]
#   scripts/run_live_expansion_trial.sh --clean "the task" 20
#
# Requires: `fa` on PATH (or .venv/bin/fa) and a top-level `chat:` in models.yaml.
set -uo pipefail

CLEAN=0
if [ "${1:-}" = "--clean" ]; then CLEAN=1; shift; fi

TASK="${1:-simplify the main function in a small module without changing behaviour}"
MAX_TURNS="${2:-20}"
WORKSPACE_ARG="${3:-}"

# Locate fa + repo.
REPO="$(git rev-parse --show-toplevel 2>/dev/null || cd "$(dirname "$0")/.." && pwd)"
FA="${FA:-$REPO/.venv/bin/fa}"
[ -x "$FA" ] || FA="$(command -v fa || true)"
if [ -z "$FA" ] || [ ! -x "$FA" ]; then
  echo "ERROR: 'fa' not found on PATH or in $REPO/.venv/bin. Run 'uv sync --extra dev' first." >&2
  exit 2
fi

TRIAL_DIR="$(mktemp -d -t fa-live-trial-XXXXXX)"
export FA_STATE_ROOT="$TRIAL_DIR/state"
mkdir -p "$FA_STATE_ROOT"
LOG="$TRIAL_DIR/live.log"
RID="s10-live-$(date +%s)-$$"

# The chat role needs the repo as its workspace (tools resolve against it).
# Default to the repo root; the trial writes only via the agent's own actions.
WS="${WORKSPACE_ARG:-$REPO}"

echo "=================================================================="
echo " LIVE EXPANSION TRIAL"
echo "   fa:        $FA"
echo "   run-id:    $RID"
echo "   workspace: $WS"
echo "   state:     $FA_STATE_ROOT (isolated; your ~/.fa is untouched)"
echo "   max-turns: $MAX_TURNS"
echo "   task:      $TASK"
echo "   log:       $LOG"
echo "=================================================================="

# Preflight: the chat role must be runnable.
if ! "$FA" run --help >/dev/null 2>&1; then
  echo "ERROR: 'fa run' unavailable." >&2; exit 2
fi

set +e
"$FA" run --role chat --run-id "$RID" --workspace "$WS" \
  --max-turns "$MAX_TURNS" --detail verbose --task "$TASK" >"$LOG" 2>&1
RC=$?
set -e
echo
echo "fa EXIT=$RC (capture: $(wc -l <"$LOG") log lines)"
echo
echo "------------------------------------------------------------------"
echo " DETERMINISTIC SIGNALS (the evidence engine's durable footprint)"
echo "------------------------------------------------------------------"

count() { grep -c "$1" "$LOG" 2>/dev/null | head -1 || true; }

n_exp="$(count 'scope_expansion')"
n_exh="$(count 'expansion_exhausted\|workflow_budget_exhausted')"
n_wf="$(count 'invoke_workflow')"
n_map="$(count 'Start here')"
n_high="$(count 'Risk tier high')"
n_escal="$(count 'Scope escalation')"

printf "  %-42s %s\n" "scope_expansion events:" "$n_exp"
printf "  %-42s %s\n" "  evidence names seen:" \
  "$(grep -oE 'read_high_arm|high_tier_write|verify_failed' "$LOG" | sort -u | tr '\n' ' ')"
printf "  %-42s %s\n" "Scope escalation advice rendered:" "$n_escal"
printf "  %-42s %s\n" "high-tier verification posture:" "$n_high"
printf "  %-42s %s\n" "invoke_workflow mentioned:" "$n_wf"
printf "  %-42s %s\n" "planner handoff file-map ('Start here'):" "$n_map"
printf "  %-42s %s\n" "budget exhaustion (K spent):" "$n_exh"

echo
echo "  level transitions (level_from -> level_to, if visible):"
grep -oE 'level_from[^,]*|level_to[^,}]*' "$LOG" | sort -u | sed 's/^/    /' || true

echo
echo "------------------------------------------------------------------"
echo " READING THE RESULT (not auto-asserted — model choice is live)"
echo "------------------------------------------------------------------"
echo "  - A high/safe-tier mismatch: a docs-only task should show ~0 scope_expansion;"
echo "    a src/ task should show read_high_arm (->2) and/or high_tier_write (->3)."
echo "  - escalation is ADVICE: the model may accept (invoke_workflow + 'Start here')"
echo "    or finish in chat. The durable truth is the scope_expansion event."
echo "  - K budget: if the (K+1)-th escalation was denied you'll see workflow_budget_exhausted"
echo "    and a terminal 'report to operator' line."

echo
echo "Trial artifacts kept in: $TRIAL_DIR"
[ "$CLEAN" -eq 1 ] && { rm -rf "$TRIAL_DIR"; echo "(--clean removed the trial dir)"; }
exit "$RC"
