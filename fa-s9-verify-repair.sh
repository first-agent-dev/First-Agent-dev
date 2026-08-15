#!/usr/bin/env bash
# Independently verify the S9.0 repair candidate and all blocking local gates.
# Run as a child script: bash /path/to/fa-s9-verify-repair.sh

set -Eeuo pipefail
umask 077

BASE_SHA=33943fa3c21647057bb47b771c9a6997f8683717
EXPECTED_REPOSITORY=first-agent-dev/First-Agent-dev
BRANCH=fa/20260814-s9-prepare-hook-locked-ci-repair
PATCH_NAME=fa-s9-prepare-hook-locked-ci-repair.patch
SCRIPT_PATH=$(readlink -f "${BASH_SOURCE[0]}")
SCRIPT_DIR=$(cd "$(dirname "$SCRIPT_PATH")" && pwd)
PATCH=${FA_S9_REPAIR_PATCH:-}
SERVICE=${FA_SERVICE:-first-agent}
PYTHON_BIN=${FA_S9_PYTHON:-python3}
LOG=${FA_S9_REPAIR_VERIFY_LOG:-/tmp/fa-s9-repair-verify-$$.log}
SYNC_TIMEOUT_SECONDS=${FA_S9_SYNC_TIMEOUT_SECONDS:-900}

fail() {
  printf 'S9_REPAIR_CANDIDATE_PROOF=FAIL\nS9_REPAIR_VERIFY_FAIL=%s\nS9_REPAIR_VERIFY_LOG=%s\n' "$1" "$LOG" >&2
  [[ -f "$LOG" ]] && tail -n 80 "$LOG" >&2 || true
  exit 1
}

for command in git docker timeout sha256sum readlink; do
  command -v "$command" >/dev/null 2>&1 || fail "missing_command_$command"
done
if [[ "$PYTHON_BIN" == */* ]]; then
  [[ -x "$PYTHON_BIN" ]] || fail python_not_executable
else
  command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail python_not_found
fi
[[ "$SYNC_TIMEOUT_SECONDS" =~ ^[1-9][0-9]*$ ]] || fail invalid_sync_timeout
if [[ -z "$PATCH" ]]; then
  for candidate in "$SCRIPT_DIR/$PATCH_NAME" "$HOME/$PATCH_NAME"; do
    if [[ -f "$candidate" && ! -L "$candidate" ]]; then
      PATCH=$candidate
      break
    fi
  done
fi
[[ -f "$PATCH" && ! -L "$PATCH" ]] || fail patch_missing_or_symlink
SHA_FILE=${FA_S9_REPAIR_PATCH_SHA_FILE:-$PATCH.sha256}
[[ -f "$SHA_FILE" && ! -L "$SHA_FILE" ]] || fail patch_sha_file_missing_or_symlink
EXPECTED_PATCH_SHA=$(awk 'NR == 1 {print $1}' "$SHA_FILE")
[[ "$EXPECTED_PATCH_SHA" =~ ^[0-9a-f]{64}$ ]] || fail patch_sha_file_invalid
[[ "$(sha256sum "$PATCH" | awk '{print $1}')" == "$EXPECTED_PATCH_SHA" ]] || fail patch_sha_mismatch
: >"$LOG"
chmod 0600 "$LOG"

origin_matches() {
  case "$1" in
    "git@github.com:${EXPECTED_REPOSITORY}.git"|"https://github.com/${EXPECTED_REPOSITORY}"|"https://github.com/${EXPECTED_REPOSITORY}.git") return 0 ;;
    *) return 1 ;;
  esac
}

candidate_ok() {
  local candidate=$1 root origin
  [[ -e "$candidate/.git" && -f "$candidate/AGENTS.md" ]] || return 1
  root=$(timeout 8s git -C "$candidate" rev-parse --show-toplevel 2>/dev/null) || return 1
  [[ "$(readlink -f "$root")" == "$(readlink -f "$candidate")" ]] || return 1
  origin=$(timeout 8s git -C "$candidate" remote get-url origin 2>/dev/null) || return 1
  origin_matches "$origin"
}

add_candidate() {
  local candidate=$1 resolved existing
  [[ -n "$candidate" ]] || return 0
  resolved=$(readlink -f "$candidate" 2>/dev/null || true)
  [[ -n "$resolved" ]] || return 0
  candidate_ok "$resolved" || return 0
  for existing in "${CANDIDATES[@]:-}"; do
    [[ "$existing" == "$resolved" ]] && return 0
  done
  CANDIDATES+=("$resolved")
}

CANDIDATES=()
if [[ -n "${FA_OPERATOR_REPO:-}" ]]; then
  add_candidate "$FA_OPERATOR_REPO"
else
  for start in "$PWD" "$SCRIPT_DIR"; do
    cursor=$(readlink -f "$start" 2>/dev/null || true)
    while [[ -n "$cursor" && "$cursor" != / ]]; do
      add_candidate "$cursor"
      cursor=${cursor%/*}
      [[ -n "$cursor" ]] || cursor=/
    done
  done
  while IFS= read -r candidate; do
    add_candidate "$candidate"
  done < <("$PYTHON_BIN" -c 'from pathlib import Path; h=Path.home(); print("\n".join(str(p) for p in sorted(h.iterdir()) if p.is_dir()))')
fi
[[ "${#CANDIDATES[@]}" -eq 1 ]] || fail "operator_repo_discovery_count_${#CANDIDATES[@]}"
REPO=${CANDIDATES[0]}

DEPLOYMENT_REPO=$(timeout 8s docker inspect -f '{{range .Mounts}}{{if eq .Destination "/repo"}}{{.Source}}{{end}}{{end}}' "$SERVICE" 2>/dev/null) \
  || fail deployment_repo_discovery_failed
[[ -n "$DEPLOYMENT_REPO" ]] || fail deployment_repo_empty
[[ "$(readlink -f "$REPO")" != "$(readlink -f "$DEPLOYMENT_REPO")" ]] || fail deployment_checkout_forbidden
[[ "$(timeout 8s git -C "$REPO" branch --show-current)" == "$BRANCH" ]] || fail wrong_branch
timeout 8s git -C "$REPO" merge-base --is-ancestor "$BASE_SHA" HEAD || fail base_not_ancestor

diff_sha=$(timeout 15s git -C "$REPO" diff --binary "$BASE_SHA" | sha256sum | awk '{print $1}') \
  || fail diff_hash_failed
[[ "$diff_sha" == "$EXPECTED_PATCH_SHA" ]] || fail candidate_diff_mismatch
[[ -z "$(timeout 8s git -C "$REPO" status --porcelain=v1 --untracked-files=all | awk '$1 == "??" {print}')" ]] \
  || fail candidate_has_untracked_files
timeout 8s git -C "$REPO" diff --cached --quiet || fail candidate_has_staged_changes

cd "$REPO"
timeout 8s git diff --check || fail diff_check_failed
"$PYTHON_BIN" -c 'from pathlib import Path; p=Path("src/fa/hygiene/hooks/prepare-commit-msg"); t=p.read_text(); assert "message|template|squash|merge|commit|\"\")" not in t; assert "message|template|squash|merge|commit)" in t' \
  || fail prepare_source_contract
"$PYTHON_BIN" -c 'from pathlib import Path; bad=[]
for p in sorted(Path(".github/workflows").glob("*.y*ml")):
    for i,line in enumerate(p.read_text().splitlines(),1):
        s=line.strip()
        if s.startswith("#") or "uv sync" not in s: continue
        if "--frozen" in s or "--locked" not in s: bad.append(f"{p}:{i}:{s}")
assert not bad,bad' || fail workflow_lock_contract

if command -v uv >/dev/null 2>&1; then
  UV=$(command -v uv)
elif [[ -x "$HOME/.local/bin/uv" ]]; then
  UV=$HOME/.local/bin/uv
else
  fail uv_not_found
fi
if command -v uvx >/dev/null 2>&1; then
  UVX=$(command -v uvx)
elif [[ -x "$HOME/.local/bin/uvx" ]]; then
  UVX=$HOME/.local/bin/uvx
else
  fail uvx_not_found
fi

run_gate() {
  local name=$1 seconds=$2
  shift 2
  printf '\n===== %s =====\n' "$name" >>"$LOG"
  if (
    umask 022
    timeout --foreground --kill-after=10s "${seconds}s" "$@"
  ) >>"$LOG" 2>&1; then
    printf 'PASS %s\n' "$name" | tee -a "$LOG"
  else
    local rc=$?
    printf 'FAIL %s rc=%s\n' "$name" "$rc" >>"$LOG"
    fail "gate_${name}_rc_${rc}"
  fi
}

run_gate sync_locked "$SYNC_TIMEOUT_SECONDS" "$UV" sync --locked --extra dev
run_gate readiness 2100 "$PYTHON_BIN" scripts/bootstrap/workspace.py ensure --workspace "$REPO"
run_gate targeted_pytest 600 "$UV" run --no-sync python -m pytest -q \
  tests/test_hygiene_hooks_self_bootstrap.py \
  tests/test_pr_intent_snapshot.py \
  tests/test_container_build_invariants.py \
  tests/test_workflow_hygiene.py \
  tests/test_deploy_scripts.py
run_gate ruff_check 180 "$UV" run --no-sync ruff check \
  tests/test_hygiene_hooks_self_bootstrap.py tests/test_container_build_invariants.py
run_gate ruff_format 180 "$UV" run --no-sync ruff format --check \
  tests/test_hygiene_hooks_self_bootstrap.py tests/test_container_build_invariants.py
run_gate mypy 240 "$UV" run --no-sync mypy \
  tests/test_hygiene_hooks_self_bootstrap.py tests/test_container_build_invariants.py
run_gate pyrefly 240 "$UV" run --no-sync pyrefly check \
  tests/test_hygiene_hooks_self_bootstrap.py tests/test_container_build_invariants.py
run_gate shell_syntax 180 bash scripts/check_shell_syntax.sh src/fa/hygiene/hooks/prepare-commit-msg
run_gate workflow_yaml 120 "$UV" run --no-sync python -c \
  'from pathlib import Path; import yaml; paths=sorted(Path(".github/workflows").glob("*.y*ml")); assert paths; assert all(isinstance(yaml.safe_load(p.read_text()),dict) for p in paths)'
run_gate full_just_check 1200 "$UVX" --from rust-just==1.57.0 just check

final_diff_sha=$(timeout 15s git -C "$REPO" diff --binary "$BASE_SHA" | sha256sum | awk '{print $1}') \
  || fail final_diff_hash_failed
[[ "$final_diff_sha" == "$EXPECTED_PATCH_SHA" ]] || fail gates_changed_candidate_diff
[[ -z "$(timeout 8s git -C "$REPO" status --porcelain=v1 --untracked-files=all | awk '$1 == "??" {print}')" ]] \
  || fail gates_left_untracked_files
timeout 8s git -C "$REPO" diff --cached --quiet || fail gates_left_staged_changes

printf 'OPERATOR_REPO=%s\nBASE_SHA=%s\nBRANCH=%s\nPATCH_SHA256=%s\nS9_REPAIR_VERIFY_LOG=%s\nS9_REPAIR_CANDIDATE_PROOF=PASS\nNEXT=COMMIT_REPAIR_BRANCH\n' \
  "$REPO" "$BASE_SHA" "$BRANCH" "$EXPECTED_PATCH_SHA" "$LOG"
