# PR: Update scripts — fix blocking defects

## Intent: FIX
## Invariant: fa-update.sh re-exec, state tracking, and change detection work correctly.

## Problem

Three interacting defects in `fa-update.sh` caused the "uv lock and
stops" symptom:

1. **flock/tee fd inheritance** — `tee` subshell inherited fd 9 (the
   flock fd). On re-exec, the child process couldn't acquire the lock
   (held by orphaned tee subshell), failed silently, and no build ran.

2. **State amnesia** — no record of what image the container actually
   runs. After a failed build, `git pull` is a no-op → script says
   "no changes" → skips rebuild → container stuck on old code.

3. **`--force-recreate` gating** — only applied when no build occurred.
   Build + env change → new image but potentially stale env in edge cases.

Additional: single env hash lumped all 4 input files → agent-only
changes unnecessarily restarted the proxy.

## Solution

### P0: Blocking fixes

- **Swap tee/flock order** — tee subshell starts before fd 9 is opened,
  never inherits it. Re-exec'd child acquires lock successfully.
  Changed `flock -n` to `flock -w 600` (10-min timeout vs instant fail).

- **Image-label state tracking** — Dockerfile gets
  `LABEL org.opencontainers.image.revision=${FA_BUILD_SHA}`. Build
  passes `--build-arg FA_BUILD_SHA=$(git rev-parse HEAD)`. At
  `evaluate_changes`, script reads running container's label via
  `docker inspect` and compares to working-tree HEAD. Stale image →
  rebuild triggered regardless of `git pull` status.

- **Always `--force-recreate`** when restart needed, not just on
  env-only changes.

### P1: Correctness fixes

- **Split hash** — agent inputs (`ENV_FA`, `MODELS_YAML_FILE`) and
  proxy inputs (`SECRETS_ENV`, `PROXY_TOKEN_FILE`, `MODELS_YAML_FILE`)
  hashed separately. Changing `.env.fa` only restarts the agent.

- **Skip git pull on re-exec** — re-exec'd child uses the parent's
  already-updated working tree. Eliminates double-pull waste and
  theoretical force-push race.

- **Explicit `cd "${REPO_DIR}"`** at top of main() — ensures cwd is
  correct regardless of re-exec path.

- **`df -P`** for portable disk-usage check (no wrapping on long paths).

- **Scoped `git add`** for trace auto-commit — only specific trace
  files, not the whole directory (prevents sweeping pre-staged changes).

- **fa-clean-rebuild.sh ERR trap** — replaced function-based trap with
  single-quoted trap string that correctly captures `BASH_COMMAND`.

- **fa-clean-rebuild.sh build-arg** — threads `FA_BUILD_SHA` so
  clean-rebuild images also get the revision label.

## Files changed

| File | Change |
|------|--------|
| `Dockerfile.fa` | +3: `ARG FA_BUILD_SHA` + `LABEL` (last instruction) |
| `scripts/fa-update.sh` | Tee/flock swap, image-label check, split hash, skip git on re-exec, df -P, scoped git add, force-recreate |
| `scripts/fa-clean-rebuild.sh` | ERR trap fix, build-arg threading |

## Subtraction check

- **Removing what?** Single-hash lump → split hash. `flock -n` → `flock -w 600`.
- **Lost if omitted?** Re-exec silently fails; failed builds leave system stuck.
- **OSS precedent?** OCI image.revision label is standard (Docker, Podman, GitHub Actions all use it).

## Verification

```bash
# 1. Break Dockerfile deliberately → build fails
#    Next fa update detects stale image → retries build

# 2. Change only .env.fa → only agent restarts, proxy stays

# 3. Re-exec works: modify scripts/fa-update.sh in git →
#    script re-execs → child acquires lock → build completes

# 4. df -P works on long filesystem paths
```
