# PR: Fix CI and Update Scripts Workspace Isolation Regressions

**Intent:** FIX
**Goal Lens:** Ensure CI and deployment scripts correctly interface with the newly introduced ADR-13 workspace isolation mechanism.

## Summary

Resolves CI failures (`fatal: destination path already exists`) caused by redundant git clones, and patches `fa-update.sh` to ensure smoke tests operate against a fresh repository clone. Also ensures `fa-clean-rebuild.sh` respects the `WIPE_STATE` directive across all isolated partitions.

## Changes

1. **`.github/workflows/advisory.yml`**:
   - Removed the manual `git clone`, `cd`, and `git checkout` commands in the `container-build` job's entrypoint execution.
   - `fa-entrypoint.sh` now natively performs this cloning operation automatically. The CI now accurately tests that the entrypoint *succeeded* in setting up the environment (`test -d .git`, `test -f .active`, and `PWD`).

2. **`scripts/fa-update.sh`**:
   - Added a `rm -rf /sessions/deploy-smoke-test` wipe before executing the smoke tests (`uv sync` and `pytest`).
   - Because `fa-entrypoint.sh` handles existing sessions via resumption, subsequent `fa-update.sh` executions would have inadvertently tested against yesterday's stale code clone. This ensures the smoke test evaluates the freshly pulled `main` branch.

3. **`scripts/fa-clean-rebuild.sh`**:
   - Extended the `WIPE_STATE=1` conditional to clear `"${FA_DIR}/sessions/"*` as well. State is now functionally split between `/state` and `/sessions`, and a hard wipe must clear both to prevent orphaned workspaces.

## Subtraction Evaluated
- Removing what makes this redundant: none.
- What capability is lost: Stale cached code for the deploy-smoke-test.
- Open-source agent-stack precedent: Open SWE.
