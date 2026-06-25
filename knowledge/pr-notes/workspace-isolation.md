# PR: Workspace Isolation (ADR-13)

**Intent:** IMPLEMENT
**Goal Lens:** Isolate agent writes from the host worktree using a read-only bind mount and per-session writable clones.

## Summary

Implemented Workspace Isolation via Pattern 2 (Docker AI Sandbox RO mount + per-session clone) according to ADR-13 to prevent the agent from dirtying the main host git checkout.

## Changes

1. **Host-Side Scripts:**
   - `scripts/fa-update.sh`: Refactored test phases to execute against the newly cloned read-only `/repo` mount by orchestrating through the `fa-entrypoint.sh` with a `FA_RUN_ID="deploy-smoke-test"`. This naturally spins up an ephemeral, writable, isolated per-deploy session clone. This elegantly bypasses the need for global venvs (`UV_PROJECT_ENVIRONMENT`) or Python cache redirects, and serves as an End-to-End integration test of the session cloning mechanism itself.
   - `scripts/fa`: Parses the host-relative `/srv/first-agent/sessions/.active` and forwards docker exec requests smoothly to the dynamic session environment inside the container (`/sessions/...`).
   - `scripts/fa-entrypoint.sh`: On auto-start, first spawn, or command override, checks for `/repo/.git`, generates a fast, hardlink-backed `git clone --local` per-session workspace inside `/sessions`, switches branches, atomically writes the path to `/sessions/.active`, and seamlessly executes the override command within the isolated context.

2. **Docker Architecture:**
   - `Dockerfile.fa`: Pre-initializes `/repo` and `/sessions` directories.
   - `docker-compose.fa.yml`: Replaced the legacy rw `/workspace` mount with the read-only `/repo` and writable per-session volume `/sessions`.

3. **Invariants Preserved & Enforced:**
   - Secrets remain completely inaccessible to the core `first-agent` sandbox.
   - `test_fa_update_runs_dev_sync_in_session_clone_not_image_snapshot` enforces that deploy script validation executes explicitly against a newly cloned live checkout rather than the stale immutable image (`/opt/first-agent`).
   - `test_entrypoint_command_override_executes_inside_session_clone` provides pure integration coverage verifying the clone latency, isolated cwd execution, and directory boundaries directly.

## Subtraction Evaluated
- Removing what makes this redundant: none.
- What capability is lost: The operator's main repo no longer becomes contaminated. While per-session clones introduce minimal latency, `git clone --local` utilizes underlying filesystem hardlinks natively providing near-zero disk-footprint/instant cloning.
- Open-source agent-stack precedent: SWE-Next, Open SWE.
