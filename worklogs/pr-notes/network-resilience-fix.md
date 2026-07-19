# PR: Network Resilience & Robust Stash Recovery in Update Scripts

**Intent:** FIX
**Goal Lens:** Ensure host-side deployment scripts gracefully handle transient network errors and safely recover uncommitted state across network failures.

## Summary

Resolves network fragility in `fa-clean-rebuild.sh` and `fa-update.sh` that caused `git fetch`/`git pull` to fail on transient DNS errors (e.g., `ssh: Could not resolve hostname github.com`). Crucially, patches a severe logic error where a failed network command would abort the script *without* popping the `git stash`, leaving operators with orphaned stashed code.

## Changes

1. **Network Retries:**
   - Introduced a `retry()` wrapper function into both scripts to wrap `git fetch` and `git pull`.
   - The wrapper attempts the command up to 3 times with a 5-second delay, native mitigation for "Temporary failure in name resolution" and other transient upstream drops.

2. **Robust `git stash` Recovery (`ERR` trap update):**
   - Transferred the `git stash pop` fallback logic directly into the bash `trap_err` (`ERR` trap) in both `fa-clean-rebuild.sh` and `fa-update.sh`.
   - If the script fails *anywhere* between `git stash push` and the intended success branch, the error trap executes and safely pops the operator's stashed changes back into the working directory before aborting.

## Subtraction Evaluated
- Removing what makes this redundant: none.
- What capability is lost: Brittle, fail-fast unrecovered networking behavior.
- Open-source agent-stack precedent: standard retry backoffs for cloud integration tasks.
