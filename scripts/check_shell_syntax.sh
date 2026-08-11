#!/usr/bin/env -S LC_ALL=C bash
# Shell-syntax preflight: `bash -n` every .sh in the repo plus every
# shipped git-hook shell script. Exits non-zero if any file has a syntax
# error; prints diagnostics prefixed with the path. Used by both
# `just _shell-syntax` and the pre-commit hook.
#
# LC_ALL=C is baked into the shebang so the interpreter starts in the
# POSIX locale from the very first fork. This avoids spurious
#   "bash: warning: setlocale: LC_ALL: cannot change locale (en_US.UTF-8)"
# noise on hosts (minimal containers, freshly provisioned laptops) that
# export en_US.UTF-8 but have not generated that locale, and it keeps
# any real bash syntax-error messages in a stable, grep-friendly form.
#
# Usage:
#   scripts/check_shell_syntax.sh            # full repo scan
#   scripts/check_shell_syntax.sh FILE...    # explicit file list (pre-commit)
#
# When called with arguments, only those files are checked (pre-commit
# pass_filenames mode). With no arguments, scans the default set: *.sh
# in the tree plus the four git hooks. Always skips .git, .venv, mutants.

set -euo pipefail
export LC_ALL=C

# Detect repo root (script lives in <repo>/scripts/).
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

rc=0
declare -A seen=()

add_path() {
    local p="$1"
    if [[ -z "${seen[$p]:-}" && -f "$p" ]]; then
        seen[$p]=1
    fi
}

if [[ $# -gt 0 ]]; then
    for f in "$@"; do
        # Only check shell scripts / hooks when pre-commit passes filenames.
        case "$f" in
            *.sh|src/fa/hygiene/hooks/pre-commit|src/fa/hygiene/hooks/pre-push|src/fa/hygiene/hooks/prepare-commit-msg|src/fa/hygiene/hooks/commit-msg)
                add_path "$f"
                ;;
        esac
    done
else
    while IFS= read -r -d '' f; do
        add_path "$f"
    done < <(
        find . -name '*.sh' -type f \
            -not -path './.git/*' \
            -not -path './.venv/*' \
            -not -path './mutants/*' \
            -print0
    )
    for h in pre-commit pre-push prepare-commit-msg commit-msg; do
        add_path "src/fa/hygiene/hooks/$h"
    done
fi

for s in "${!seen[@]}"; do
    # LC_ALL=C forces the POSIX locale for the syntax-checking sub-bash so
    # (a) hosts without an en_US.UTF-8 locale generated do not emit a
    #     "setlocale: LC_ALL: cannot change locale" startup warning to stderr
    #     (that warning is NOT a syntax error but was previously flagged as one),
    # (b) any real syntax-error messages come out in a stable, grep-friendly form.
    # We key on bash's actual exit code, not on non-empty stderr — warnings on
    # stderr during a successful parse are benign.
    err="$(LC_ALL=C bash -n "$s" 2>&1 1>/dev/null)"
    if [[ $? -ne 0 ]]; then
        printf '%s:\n%s\n' "$s" "$err" >&2
        rc=1
    fi
done

if [[ $rc -ne 0 ]]; then
    echo "shell-syntax: one or more shell scripts failed bash -n" >&2
fi
exit $rc
