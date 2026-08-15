#!/usr/bin/env bash
# Sandbox qualification for the S9.0 repair patch/apply/verifier scripts.
# Uses real temporary Git repositories and shadow external tools.

set -Eeuo pipefail
umask 077

BASE_SHA=33943fa3c21647057bb47b771c9a6997f8683717
EXPECTED_URL=https://github.com/first-agent-dev/First-Agent-dev.git
SCRIPT_PATH=$(readlink -f "${BASH_SOURCE[0]}")
SCRIPT_DIR=$(cd "$(dirname "$SCRIPT_PATH")" && pwd)
APPLY=$SCRIPT_DIR/fa-s9-apply-repair.sh
VERIFY=$SCRIPT_DIR/fa-s9-verify-repair.sh
PATCH_NAME=fa-s9-prepare-hook-locked-ci-repair.patch
PATCH=${FA_S9_REPAIR_PATCH:-}
if [[ -z "$PATCH" ]]; then
  for candidate in "$SCRIPT_DIR/$PATCH_NAME" "$HOME/$PATCH_NAME"; do
    if [[ -f "$candidate" && ! -L "$candidate" ]]; then
      PATCH=$candidate
      break
    fi
  done
fi
SHA_FILE=${FA_S9_REPAIR_PATCH_SHA_FILE:-$PATCH.sha256}
ROOT_PARENT=${FA_S9_TEST_TMP_ROOT:-$HOME}
ROOT=$(mktemp -d "$ROOT_PARENT/.fa-s9-repair-tests.XXXXXX")
TEMPLATE=$ROOT/template
FAKEBIN=$ROOT/fakebin
REAL_PYTHON=$(command -v python3)

cleanup() {
  rm -rf -- "$ROOT"
}
trap cleanup EXIT

fail() {
  printf 'S9_REPAIR_SCRIPT_TESTS=FAIL\nS9_REPAIR_SCRIPT_TEST_FAIL=%s\n' "$1" >&2
  exit 1
}

for path in "$APPLY" "$VERIFY" "$PATCH" "$SHA_FILE"; do
  [[ -f "$path" && ! -L "$path" ]] || fail "missing_or_symlink_$(basename "$path")"
done
for command in git timeout sha256sum readlink python3; do
  command -v "$command" >/dev/null 2>&1 || fail "missing_command_$command"
done

mkdir -p "$FAKEBIN"
# shellcheck disable=SC2016  # Child-script variables must expand in the child, not this parent.
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'set -eu' \
  'if [[ "${1:-}" == inspect ]]; then printf "%s\n" "${FA_TEST_DEPLOYMENT_REPO:?}"; exit 0; fi' \
  'exit 97' >"$FAKEBIN/docker"
# shellcheck disable=SC2016  # Child-script variables must expand in the child, not this parent.
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'set -eu' \
  'printf "uv %s umask=%s\n" "$*" "$(umask)" >>"${FA_TEST_TOOL_LOG:?}"' \
  'if [[ -n "${FA_TEST_TOOL_SLEEP:-}" ]]; then sleep "$FA_TEST_TOOL_SLEEP"; fi' \
  'exit "${FA_TEST_TOOL_RC:-0}"' >"$FAKEBIN/uv"
# shellcheck disable=SC2016  # Child-script variables must expand in the child, not this parent.
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'set -eu' \
  'printf "uvx %s umask=%s\n" "$*" "$(umask)" >>"${FA_TEST_TOOL_LOG:?}"' \
  'exit "${FA_TEST_TOOL_RC:-0}"' >"$FAKEBIN/uvx"
# shellcheck disable=SC2016  # Child-script variables must expand in the child, not this parent.
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'set -eu' \
  'if [[ "${1:-}" == scripts/bootstrap/workspace.py ]]; then printf "{\"status\":\"ready\"}\n"; exit 0; fi' \
  "exec '$REAL_PYTHON' \"\$@\"" >"$FAKEBIN/python3"
chmod 0755 "$FAKEBIN/docker" "$FAKEBIN/uv" "$FAKEBIN/uvx" "$FAKEBIN/python3"

export PATH="$FAKEBIN:$PATH"
export FA_S9_REPAIR_PATCH="$PATCH"
export FA_S9_REPAIR_PATCH_SHA_FILE="$SHA_FILE"
export FA_S9_PYTHON="$FAKEBIN/python3"
export FA_TEST_TOOL_LOG=$ROOT/tool.log
export FA_TEST_TOOL_RC=0

timeout --foreground --kill-after=5s 60s git clone --no-hardlinks "$EXPECTED_URL" "$TEMPLATE" >/dev/null 2>&1 \
  || fail template_clone_failed
git -C "$TEMPLATE" switch -C main "$BASE_SHA" >/dev/null 2>&1 || fail template_base_checkout_failed
[[ "$(git -C "$TEMPLATE" rev-parse HEAD)" == "$BASE_SHA" ]] || fail template_wrong_base

make_repo() {
  local name=$1
  local repo=$ROOT/$name
  git clone --quiet --no-hardlinks "$TEMPLATE" "$repo"
  git -C "$repo" remote set-url origin "$EXPECTED_URL"
  git -C "$repo" config user.name "S9 Script Test"
  git -C "$repo" config user.email "s9-script-test@example.invalid"
  printf '%s\n' "$repo"
}

run_apply() {
  local repo=$1 out=$2 deployment=${3:-$ROOT/not-deployment}
  FA_OPERATOR_REPO="$repo" FA_TEST_DEPLOYMENT_REPO="$deployment" bash "$APPLY" >"$out" 2>&1
}

run_verify() {
  local repo=$1 out=$2 deployment=${3:-$ROOT/not-deployment}
  FA_OPERATOR_REPO="$repo" FA_TEST_DEPLOYMENT_REPO="$deployment" \
    FA_S9_REPAIR_VERIFY_LOG="$ROOT/verify-$(basename "$repo").log" \
    bash "$VERIFY" >"$out" 2>&1
}

expect_failure() {
  local label=$1 expected=$2
  shift 2
  local out=$ROOT/$label.out rc
  set +e
  "$@" >"$out" 2>&1
  rc=$?
  set -e
  [[ "$rc" -ne 0 ]] || fail "${label}_unexpected_success"
  grep -q "$expected" "$out" || { tail -n 40 "$out" >&2; fail "${label}_wrong_failure"; }
  printf 'PASS expected-failure %s rc=%s\n' "$label" "$rc"
}

repo_success=$(make_repo success)
out=$ROOT/apply-success.out
run_apply "$repo_success" "$out"
grep -qx 'S9_REPAIR_APPLY=PASS' "$out" || fail apply_success_token_missing
grep -qx 'REUSED_EXISTING=no' "$out" || fail apply_first_not_new
[[ "$(git -C "$repo_success" branch --show-current)" == fa/20260814-s9-prepare-hook-locked-ci-repair ]] \
  || fail apply_branch_wrong
for path in \
  fa-s9-apply-repair.sh \
  fa-s9-verify-repair.sh \
  fa-s9-test-scripts.sh \
  src/fa/hygiene/hooks/prepare-commit-msg
do
  [[ "$(stat -c %a "$repo_success/$path")" == 755 ]] || fail "apply_exec_mode_wrong_$path"
done
for path in \
  .github/workflows/advisory.yml \
  .github/workflows/authoring-guardrails.yml \
  tests/test_container_build_invariants.py \
  tests/test_hygiene_hooks_self_bootstrap.py \
  worklogs/implementation-plans/PLAN-session-workspace-readiness-bootstrap.md \
  worklogs/implementation-plans/session-workspace-readiness-live-verification-from-6.md
do
  [[ "$(stat -c %a "$repo_success/$path")" == 644 ]] || fail "apply_regular_mode_wrong_$path"
done
printf 'PASS apply-success\n'

run_apply "$repo_success" "$out"
grep -qx 'S9_REPAIR_APPLY=PASS' "$out" || fail apply_repeat_token_missing
grep -qx 'REUSED_EXISTING=yes' "$out" || fail apply_repeat_not_reused
printf 'PASS apply-idempotent\n'

repo_recovery=$(make_repo interrupted-apply)
git -C "$repo_recovery" switch -c fa/20260814-s9-prepare-hook-locked-ci-repair >/dev/null 2>&1
git -C "$repo_recovery" apply --binary --whitespace=error-all "$PATCH"
git -C "$repo_recovery" add -N -- fa-s9-apply-repair.sh fa-s9-verify-repair.sh fa-s9-test-scripts.sh
recovery_out=$ROOT/apply-recovery.out
run_apply "$repo_recovery" "$recovery_out"
grep -qx 'S9_REPAIR_APPLY=PASS' "$recovery_out" || fail apply_recovery_token_missing
grep -qx 'REUSED_EXISTING=yes' "$recovery_out" || fail apply_recovery_not_reused
printf 'PASS apply-interrupted-recovery\n'

verify_out=$ROOT/verify-success.out
run_verify "$repo_success" "$verify_out"
grep -qx 'S9_REPAIR_CANDIDATE_PROOF=PASS' "$verify_out" || { tail -n 80 "$verify_out" >&2; fail verify_success_token_missing; }
grep -q '^uv sync --locked --extra dev umask=0022$' "$FA_TEST_TOOL_LOG" || fail verify_sync_or_umask_wrong
grep -q '^uvx --from rust-just==1.57.0 just check umask=0022$' "$FA_TEST_TOOL_LOG" || fail verify_full_gate_or_umask_wrong
printf 'PASS verify-success\n'

repo_timeout=$(make_repo verify-timeout)
run_apply "$repo_timeout" "$ROOT/apply-timeout.out"
expect_failure verify-timeout gate_sync_locked_rc_124 env \
  FA_OPERATOR_REPO="$repo_timeout" FA_TEST_DEPLOYMENT_REPO="$ROOT/not-deployment" \
  FA_S9_REPAIR_VERIFY_LOG="$ROOT/verify-timeout.log" FA_TEST_TOOL_SLEEP=3 \
  FA_S9_SYNC_TIMEOUT_SECONDS=1 bash "$VERIFY"

repo_wrong=$(make_repo wrong-base)
git -C "$repo_wrong" commit --quiet --allow-empty -m "wrong base"
expect_failure wrong-base operator_repo_wrong_base env \
  FA_OPERATOR_REPO="$repo_wrong" FA_TEST_DEPLOYMENT_REPO="$ROOT/not-deployment" bash "$APPLY"

repo_dirty=$(make_repo dirty)
printf 'dirty\n' >>"$repo_dirty/README.md"
expect_failure dirty operator_repo_not_clean env \
  FA_OPERATOR_REPO="$repo_dirty" FA_TEST_DEPLOYMENT_REPO="$ROOT/not-deployment" bash "$APPLY"

repo_deploy=$(make_repo deployment)
expect_failure deployment deployment_checkout_forbidden env \
  FA_OPERATOR_REPO="$repo_deploy" FA_TEST_DEPLOYMENT_REPO="$repo_deploy" bash "$APPLY"

bad_patch=$ROOT/bad.patch
cp "$PATCH" "$bad_patch"
printf '\n# mutation\n' >>"$bad_patch"
repo_bad_patch=$(make_repo bad-patch)
expect_failure patch-sha patch_sha_mismatch env \
  FA_OPERATOR_REPO="$repo_bad_patch" FA_TEST_DEPLOYMENT_REPO="$ROOT/not-deployment" \
  FA_S9_REPAIR_PATCH="$bad_patch" bash "$APPLY"

bad_sha_file=$ROOT/bad.sha256
printf 'not-a-sha  %s\n' "$PATCH_NAME" >"$bad_sha_file"
repo_bad_sha_file=$(make_repo bad-sha-file)
expect_failure patch-sha-file patch_sha_file_invalid env \
  FA_OPERATOR_REPO="$repo_bad_sha_file" FA_TEST_DEPLOYMENT_REPO="$ROOT/not-deployment" \
  FA_S9_REPAIR_PATCH_SHA_FILE="$bad_sha_file" bash "$APPLY"

sha_link=$ROOT/sha-link
ln -s "$SHA_FILE" "$sha_link"
repo_sha_link=$(make_repo sha-link-repo)
expect_failure patch-sha-symlink patch_sha_file_missing_or_symlink env \
  FA_OPERATOR_REPO="$repo_sha_link" FA_TEST_DEPLOYMENT_REPO="$ROOT/not-deployment" \
  FA_S9_REPAIR_PATCH_SHA_FILE="$sha_link" bash "$APPLY"

patch_link=$ROOT/patch-link
ln -s "$PATCH" "$patch_link"
repo_patch_link=$(make_repo patch-link-repo)
expect_failure patch-symlink patch_missing_or_symlink env \
  FA_OPERATOR_REPO="$repo_patch_link" FA_TEST_DEPLOYMENT_REPO="$ROOT/not-deployment" \
  FA_S9_REPAIR_PATCH="$patch_link" bash "$APPLY"

repo_bad_diff=$(make_repo bad-diff)
run_apply "$repo_bad_diff" "$ROOT/apply-bad-diff.out"
printf '\n# unreviewed mutation\n' >>"$repo_bad_diff/src/fa/hygiene/hooks/prepare-commit-msg"
expect_failure verify-diff candidate_diff_mismatch env \
  FA_OPERATOR_REPO="$repo_bad_diff" FA_TEST_DEPLOYMENT_REPO="$ROOT/not-deployment" \
  FA_S9_REPAIR_VERIFY_LOG="$ROOT/verify-bad-diff.log" bash "$VERIFY"

printf 'S9_REPAIR_SCRIPT_TESTS=PASS\nCASES=apply-success,apply-idempotent,apply-interrupted-recovery,verify-success,verify-timeout,wrong-base,dirty,deployment,patch-sha,patch-sha-file,patch-sha-symlink,patch-symlink,verify-diff\n'
