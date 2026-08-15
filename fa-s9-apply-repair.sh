#!/usr/bin/env bash
# Apply the reviewed S9.0 prepare-hook/locked-CI repair to the operator clone.
# Run as a child script: bash /path/to/fa-s9-apply-repair.sh

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
NEW_PATHS=(fa-s9-apply-repair.sh fa-s9-verify-repair.sh fa-s9-test-scripts.sh)
EXECUTABLE_PATHS=(
  fa-s9-apply-repair.sh
  fa-s9-verify-repair.sh
  fa-s9-test-scripts.sh
  src/fa/hygiene/hooks/prepare-commit-msg
)
REGULAR_PATHS=(
  .github/workflows/advisory.yml
  .github/workflows/authoring-guardrails.yml
  tests/test_container_build_invariants.py
  tests/test_hygiene_hooks_self_bootstrap.py
  worklogs/implementation-plans/PLAN-session-workspace-readiness-bootstrap.md
  worklogs/implementation-plans/session-workspace-readiness-live-verification-from-6.md
)

fail() {
  printf 'S9_REPAIR_APPLY=FAIL\nS9_REPAIR_APPLY_FAIL=%s\n' "$1" >&2
  exit 1
}

for command in git docker timeout sha256sum readlink python3; do
  command -v "$command" >/dev/null 2>&1 || fail "missing_command_$command"
done
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
actual_patch_sha=$(sha256sum "$PATCH" | awk '{print $1}')
[[ "$actual_patch_sha" == "$EXPECTED_PATCH_SHA" ]] || fail patch_sha_mismatch

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
  done < <(python3 -c 'from pathlib import Path; h=Path.home(); print("\n".join(str(p) for p in sorted(h.iterdir()) if p.is_dir()))')
fi
[[ "${#CANDIDATES[@]}" -eq 1 ]] || fail "operator_repo_discovery_count_${#CANDIDATES[@]}"
REPO=${CANDIDATES[0]}

DEPLOYMENT_REPO=$(timeout 8s docker inspect -f '{{range .Mounts}}{{if eq .Destination "/repo"}}{{.Source}}{{end}}{{end}}' "$SERVICE" 2>/dev/null) \
  || fail deployment_repo_discovery_failed
[[ -n "$DEPLOYMENT_REPO" ]] || fail deployment_repo_empty
[[ "$(readlink -f "$REPO")" != "$(readlink -f "$DEPLOYMENT_REPO")" ]] || fail deployment_checkout_forbidden

current_branch=$(timeout 8s git -C "$REPO" branch --show-current) || fail branch_read_failed
current_diff_sha=$(timeout 15s git -C "$REPO" diff --binary "$BASE_SHA" | sha256sum | awk '{print $1}') \
  || fail diff_hash_failed
if [[ "$current_diff_sha" == "$EXPECTED_PATCH_SHA" ]]; then
  [[ "$current_branch" == "$BRANCH" ]] || fail exact_patch_on_wrong_branch
  [[ -z "$(timeout 8s git -C "$REPO" status --porcelain=v1 --untracked-files=all | awk '$1 == "??" {print}')" ]] \
    || fail exact_patch_has_untracked_files
  timeout 8s git -C "$REPO" diff --cached --quiet || fail exact_patch_has_staged_changes
  chmod 0755 "${EXECUTABLE_PATHS[@]/#/$REPO/}" || fail executable_mode_normalization_failed
  chmod 0644 "${REGULAR_PATHS[@]/#/$REPO/}" || fail regular_mode_normalization_failed
  printf 'OPERATOR_REPO=%s\nBASE_SHA=%s\nBRANCH=%s\nPATCH_SHA256=%s\nS9_REPAIR_APPLY=PASS\nREUSED_EXISTING=yes\n' \
    "$REPO" "$BASE_SHA" "$BRANCH" "$EXPECTED_PATCH_SHA"
  exit 0
fi

[[ -z "$(timeout 8s git -C "$REPO" status --porcelain=v1 --untracked-files=all)" ]] || fail operator_repo_not_clean
[[ "$(timeout 8s git -C "$REPO" rev-parse HEAD)" == "$BASE_SHA" ]] || fail operator_repo_wrong_base

if timeout 8s git -C "$REPO" show-ref --verify --quiet "refs/heads/$BRANCH"; then
  [[ "$(timeout 8s git -C "$REPO" rev-parse "refs/heads/$BRANCH")" == "$BASE_SHA" ]] || fail existing_branch_wrong_base
  timeout 15s git -C "$REPO" switch "$BRANCH" >/dev/null || fail existing_branch_switch_failed
else
  timeout 15s git -C "$REPO" switch -c "$BRANCH" >/dev/null || fail branch_create_failed
fi

timeout 15s git -C "$REPO" apply --check --binary --whitespace=error-all "$PATCH" || fail patch_apply_check_failed
(
  umask 022
  timeout 30s git -C "$REPO" apply --binary --whitespace=error-all "$PATCH"
) || fail patch_apply_failed
for path in "${NEW_PATHS[@]}"; do
  [[ -f "$REPO/$path" && ! -L "$REPO/$path" ]] || fail "new_script_missing_or_symlink_$path"
done
chmod 0755 "${EXECUTABLE_PATHS[@]/#/$REPO/}" || fail executable_mode_normalization_failed
chmod 0644 "${REGULAR_PATHS[@]/#/$REPO/}" || fail regular_mode_normalization_failed
timeout 8s git -C "$REPO" add -N -- "${NEW_PATHS[@]}" || fail new_script_intent_to_add_failed

applied_diff_sha=$(timeout 15s git -C "$REPO" diff --binary "$BASE_SHA" | sha256sum | awk '{print $1}') \
  || fail applied_diff_hash_failed
[[ "$applied_diff_sha" == "$EXPECTED_PATCH_SHA" ]] || fail applied_diff_mismatch
[[ -z "$(timeout 8s git -C "$REPO" status --porcelain=v1 --untracked-files=all | awk '$1 == "??" {print}')" ]] \
  || fail applied_patch_has_untracked_files
timeout 8s git -C "$REPO" diff --cached --quiet || fail applied_patch_unexpectedly_staged

printf 'OPERATOR_REPO=%s\nBASE_SHA=%s\nBRANCH=%s\nPATCH_SHA256=%s\nS9_REPAIR_APPLY=PASS\nREUSED_EXISTING=no\nNEXT=RUN_S9_REPAIR_VERIFIER\n' \
  "$REPO" "$BASE_SHA" "$BRANCH" "$EXPECTED_PATCH_SHA"
