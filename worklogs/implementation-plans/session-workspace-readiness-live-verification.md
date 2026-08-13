# Managed workspace readiness — live verification protocol

Status: **PENDING LIVE EXECUTION — NOT A PASS RECORD**

Plan: [`PLAN-session-workspace-readiness-bootstrap`](./PLAN-session-workspace-readiness-bootstrap.md)
Slice: S9
Contract: CT1–CT9
Verification: T16

> Run this protocol only after the S1–S8 PR is green, human-merged, and deployed
> through operator-controlled `fa update`. Do not run it against a dirty
> deployment mirror or a patch-only checkout. Stop on the first mismatch; do not
> repair production while collecting evidence.

## 0. Pre-S9 host-wrapper incident (2026-08-13)

This is a **precondition incident**, not S9 evidence. A clean rebuild completed
and both containers became healthy, but the host then returned:

```text
bash: /usr/local/bin/fa: Permission denied
```

S9 remains pending. Do not collect live-readiness evidence until the permanent
wrapper fix is human-merged, deployed, and the deployment mirror is clean.

### Confirmed as-is defect and target behavior

- `/usr/local/bin/fa` is produced as a symlink to
  `/srv/first-agent/repo/First-Agent-dev/scripts/fa`.
- the source revision records `scripts/fa` and the directly executed maintenance
  scripts as mode `100644`;
- `fa-clean-rebuild.sh` previously installed the symlink only when the target was
  already executable, so it did not repair a mode-stripped checkout and did not
  fail when the wrapper remained unusable;
- `fa-update.sh::ensure_host_scripts()` already attempted defensive mode repair,
  but used broad fail-open `chmod +x`/symlink operations; clean-rebuild lacked
  even that repair;
- live `namei`/`stat` evidence confirmed `/usr/local/bin/fa` is the expected
  symlink, every parent directory is traversable, and the sole execution blocker
  is the canonical target's `0644` mode;
- the target state records directly executed host scripts as `100755`, enforces
  exact runtime mode `0755` in setup, post-setup, update, and clean-rebuild,
  verifies the exact resolved symlink and executable postcondition, and exits
  nonzero instead of reporting success when any postcondition fails.

The following diagnostic captured the live evidence. It prints paths, ownership,
and modes but no secret values:

```bash
set -euo pipefail
REPO=/srv/first-agent/repo/First-Agent-dev
WRAPPER="$REPO/scripts/fa"

ls -ld /usr /usr/local /usr/local/bin "$REPO" "$REPO/scripts"
ls -l /usr/local/bin/fa "$WRAPPER"
readlink /usr/local/bin/fa
readlink -f /usr/local/bin/fa
namei -l /usr/local/bin/fa
stat -c 'mode=%A (%a) owner=%U:%G path=%n' /usr/local/bin/fa "$WRAPPER"
```

Minimal pre-S9 recovery, guarded against following an unexpected symlink target:

```bash
set -euo pipefail
REPO=/srv/first-agent/repo/First-Agent-dev
WRAPPER="$REPO/scripts/fa"
TARGET=$(readlink -f /usr/local/bin/fa)
test "$TARGET" = "$WRAPPER"
sudo chmod 0755 -- "$WRAPPER"
sudo ln -sfn -- "$WRAPPER" /usr/local/bin/fa
hash -r
test -x /usr/local/bin/fa
fa --version
git -C "$REPO" status --short
```

If `namei -l` shows a parent without execute/traverse permission, stop rather
than recursively changing directory modes. If `git status --short` reports the
emergency mode repair, the deployment mirror is not eligible for S9. After the
permanent fix merges, restore only that emergency worktree mode and run the
tracked update script through Bash; the merged `100755` mode then becomes the
clean repository state:

```bash
cd /srv/first-agent/repo/First-Agent-dev
git restore --worktree -- scripts/fa
bash scripts/fa-update.sh
test -x /usr/local/bin/fa
test -z "$(git status --porcelain=v1 --untracked-files=all)"
```

### Mechanism, test class, and definition of done

- **Mechanism:** tracked executable modes plus exact `chmod 0755`, symlink
  refresh, canonical-target verification, and executable postcondition in
  fail-closed order across all four host wrapper producers.
- **Production practice:** source control owns direct-execution metadata;
  deterministic `0755` repair remains defense in depth for filesystems/export
  paths that lose mode bits and also rejects over-permissive `0777` drift.
- **Failure behavior:** missing target, failed chmod, failed symlink creation, or
  failed executable postcondition exits `1`; healthy containers are preserved,
  but the rebuild is not falsely reported complete.
- **Tests:** static producer-order contract, executable-mode invariant, Bash
  syntax, deploy-script suite, and secret-isolation regression suite.
- **Negative proof / producer kill-check:** changing a producer's `chmod 0755`
  to `chmod 0644` must fail the producer contract; stripping a tracked direct
  script to `0644` or widening it to `0777` must fail the exact-mode test;
  restoring the value-scanning secret probe must fail the name-only contract.
- **DoD:** `readlink -f` resolves to the canonical wrapper, `namei -l` has no
  traversal defect, `/usr/local/bin/fa` is executable, `fa --version` succeeds,
  the deployment mirror is clean at the merged revision, and only then may
  section 3 onward begin.

### Separate key-shaped-variable warning assessment

The old warning scanned complete `NAME=value` lines for the word `SECRET`.
Expected non-key variables such as `GIT_SSH_COMMAND` and
`FA_PROXY_TOKEN_FILE` contain `/run/secrets/...` in their values, so this scan
produces a deterministic false positive even though no LLM-key file is mounted.
The live name-only report confirmed the broad scan was triggered by exactly
`FA_PROXY_TOKEN_FILE` and `GIT_SSH_COMMAND`; neither name satisfies the corrected
provider-key suffix policy. The corrected producer checks **names only**,
anchored to `API_KEY`, `_TOKEN`, or `_SECRET` suffixes, and never prints values.

Safe live classification before the corrected producer is deployed:

```bash
# Names that triggered the old broad scan; values are discarded before output.
docker exec first-agent sh -c \
  'printenv | grep -iE "API_KEY|_TOKEN=|SECRET" | cut -d= -f1 | sort -u'

# Actual provider-key-shaped names under the corrected policy (expect empty).
docker exec first-agent sh -c \
  'printenv | cut -d= -f1 | grep -E "(API_KEY|_TOKEN|_SECRET)$" | sort -u' || true
```

If the second command prints any name, stop and investigate that variable's
producer without printing its value. The absence of names plus the already
observed absence of `/run/secrets/fa.env` classifies the old warning as a false
positive; it does not by itself complete the rest of ADR-12 or S9 evidence.

## 1. Inputs to fill before execution

```text
PR_URL=<merged implementation PR>
PR_CI_URL=<green required-check run>
MERGED_SHA=<40-character merge/main SHA>
OPERATOR=<name or handle>
STARTED_UTC=<ISO-8601 UTC>
```

Expected implementation patch, for preparing the PR before this live protocol:

```text
path=/home/user/session-workspace-readiness-s1-s8-on-ac5ba1a.patch
base=ac5ba1adc7fa7ff24ec77134f56d8eb87676f317
sha256=c39b7b039557a0143a94a89de888cc5675600b730ba4eb52bda39baa5e093904
changed_paths=65
```

The patch intentionally excludes this pending S9 protocol because S9 begins only
after the S1–S8 implementation is merged and deployed.

## 2. Pre-merge patch protocol

Run in a disposable development clone, never in the deployment mirror:

```bash
set -euo pipefail
REMOTE=https://github.com/first-agent-dev/First-Agent-dev.git
BASE=ac5ba1adc7fa7ff24ec77134f56d8eb87676f317
PATCH=/home/user/session-workspace-readiness-s1-s8-on-ac5ba1a.patch
BRANCH=agent/session-workspace-readiness-s1-s8

printf '%s  %s\n' \
  c39b7b039557a0143a94a89de888cc5675600b730ba4eb52bda39baa5e093904 \
  "$PATCH" | sha256sum --check --strict

git clone "$REMOTE" First-Agent-readiness-review
cd First-Agent-readiness-review
test "$(git rev-parse HEAD)" = "$BASE"
git switch -c "$BRANCH"
git apply --check --binary --whitespace=error-all "$PATCH"
git apply --binary --whitespace=error-all "$PATCH"
test "$(git status --porcelain=v1 --untracked-files=all | wc -l)" -eq 65
git diff --check
```

Install/sync the project environment and run the repository gates before
committing. The operator may run those tests later, but the PR must not merge
until they and GitHub CI are green.

```bash
uv sync --locked --extra dev
just check
git add -f -A
git commit -m "feat: managed session workspace readiness"
git push --set-upstream origin "$BRANCH"
```

Open a PR, wait for required checks, review all 65 paths, and merge as a human.
Record `PR_URL`, `PR_CI_URL`, and `MERGED_SHA` above.

## 3. Live host preconditions

Run as the normal First-Agent host operator. Do not use `sudo` except where the
existing deployment procedure already requires it.

```bash
set -euo pipefail
umask 077

REPO=/srv/first-agent/repo/First-Agent-dev
COMPOSE="$REPO/docker-compose.fa.yml"
SERVICE=first-agent
MERGED_SHA=REPLACE_WITH_40_CHARACTER_MERGED_SHA

case "$MERGED_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]* ) ;;
  *) echo "MERGED_SHA is not set" >&2; exit 2 ;;
esac
test "${#MERGED_SHA}" -eq 40
cd "$REPO"
test -z "$(git status --porcelain=v1 --untracked-files=all)"

docker compose -f "$COMPOSE" config --quiet
docker compose -f "$COMPOSE" ps
```

If the deployment mirror is dirty, stop. Do not stash, clean, or reset it as
part of evidence collection.

## 4. Operator update and image identity

Run the normal deployment path:

```bash
cd "$REPO"
scripts/fa update

test "$(git rev-parse HEAD)" = "$MERGED_SHA"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
docker compose -f "$COMPOSE" ps

docker inspect "$SERVICE" --format \
  'container={{.Name}} image={{.Image}} started={{.State.StartedAt}} status={{.State.Status}}'
docker image inspect "$(docker inspect "$SERVICE" --format '{{.Image}}')" --format \
  'image_id={{.Id}} created={{.Created}} repo_digests={{json .RepoDigests}}'
```

Record:

```text
DEPLOYMENT_HEAD=
CONTAINER_IMAGE_ID=
CONTAINER_STARTED_AT=
COMPOSE_SERVICES_HEALTHY=yes|no
```

Any mismatch is `S9_STATUS=BLOCK`.

## 5. Read-only topology baseline

Run the tracked A1 probe and retain its complete output. It does not create a
session or invoke a model.

```bash
cd "$REPO"
bash ./fa-bootstrap-preflight-probe.sh | tee /tmp/fa-s9-preflight.txt
grep -F 'probe=complete (read-only diagnostics; no session or LLM was created)' \
  /tmp/fa-s9-preflight.txt
```

Required baseline observations:

```text
operator development clone and deployment mirror identities are distinct
/repo mount is read-only
/sessions and /home/fa/.fa mounts are read-write
active workspace path is canonical or explicitly missing
no raw credential-bearing URL is printed
```

## 6. Capture immutable source baseline

Do not print source filenames; hash the porcelain output.

```bash
SOURCE_HEAD_BEFORE=$(docker compose -f "$COMPOSE" exec -T "$SERVICE" \
  git -C /repo rev-parse HEAD | tr -d '\r')
SOURCE_STATUS_HASH_BEFORE=$(docker compose -f "$COMPOSE" exec -T "$SERVICE" \
  sh -c 'GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false -C /repo \
    status --porcelain=v1 --untracked-files=all | sha256sum' | awk '{print $1}')

printf 'SOURCE_HEAD_BEFORE=%s\n' "$SOURCE_HEAD_BEFORE"
printf 'SOURCE_STATUS_HASH_BEFORE=%s\n' "$SOURCE_STATUS_HASH_BEFORE"
test "$SOURCE_HEAD_BEFORE" = "$MERGED_SHA"
```

## 7. Validate the entrypoint-created startup workspace

Read and validate the active path without `eval`:

```bash
STARTUP_WS=$(docker compose -f "$COMPOSE" exec -T "$SERVICE" \
  cat /sessions/.active | tr -d '\r' | tail -n 1)
case "$STARTUP_WS" in
  /sessions/[A-Za-z0-9]* ) ;;
  *) echo "invalid startup workspace: $STARTUP_WS" >&2; exit 3 ;;
esac
STARTUP_SID=${STARTUP_WS#/sessions/}
case "$STARTUP_SID" in
  *[!A-Za-z0-9_.-]*|'') echo "invalid startup session id" >&2; exit 3 ;;
esac
printf 'STARTUP_SID=%s\nSTARTUP_WS=%s\n' "$STARTUP_SID" "$STARTUP_WS"
```

Run the stdlib verifier. It prints only controlled state, never environment or
file contents.

```bash
docker compose -f "$COMPOSE" exec -T \
  -e WS="$STARTUP_WS" -e SID="$STARTUP_SID" -e CHECK_ACTIVE_ORDER=1 \
  "$SERVICE" python3 -I -B - <<'PY'
import json
import os
import re
import stat
import subprocess
from pathlib import Path

ws = Path(os.environ["WS"])
sid = os.environ["SID"]
assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", sid)
assert ws == Path("/sessions") / sid
assert ws.is_dir() and (ws / ".git").is_dir()

def git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ws), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"},
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()

branch = git("branch", "--show-current")
fetch = git("remote", "get-url", "origin")
push = git("remote", "get-url", "--push", "origin")
name = git("config", "--local", "user.name")
email = git("config", "--local", "user.email")
status = git("-c", "core.fsmonitor=false", "status", "--porcelain=v1", "--untracked-files=all")
assert branch == f"agent/{sid}"
assert fetch == Path("/repo").resolve().as_uri()
assert push == "git@github.com:first-agent-dev/First-Agent-dev.git"
assert name == "First Agent"
assert email == "agent@first-agent.local"
assert status == ""
assert not (ws / ".env.fa").exists()
assert (ws / ".venv" / "bin" / "python").is_file()

hooks_raw = git("rev-parse", "--git-path", "hooks")
hooks = Path(hooks_raw)
if not hooks.is_absolute():
    hooks = (ws / hooks).resolve()
for hook in ("pre-commit", "pre-push", "prepare-commit-msg", "commit-msg"):
    seat = hooks / hook
    assert seat.is_file() and os.access(seat, os.X_OK), hook

marker = ws / ".fa" / "ready-state.json"
assert marker.is_file() and not marker.is_symlink()
assert stat.S_IMODE(marker.stat().st_mode) == 0o600
payload = json.loads(marker.read_text(encoding="utf-8"))
assert payload["state"] == "ready"
fingerprint = payload["fingerprint"]
assert isinstance(fingerprint, str) and fingerprint.startswith("sha256:")
precommit_home = Path(os.environ.get("PRE_COMMIT_HOME", Path.home() / ".cache" / "pre-commit")).resolve()
sentinel = precommit_home / ".fa-ready" / fingerprint
assert sentinel.is_file() and sentinel.read_text(encoding="utf-8") == fingerprint + "\n"
manifest = Path("/home/fa/.fa/sessions") / sid / "manifest.json"
assert manifest.is_file()

if os.environ.get("CHECK_ACTIVE_ORDER") == "1":
    active = Path("/sessions/.active")
    assert active.is_file()
    assert marker.stat().st_mtime_ns <= active.stat().st_mtime_ns

print(json.dumps({
    "branch": branch,
    "fetch": fetch,
    "push": push,
    "identity": f"{name} <{email}>",
    "fingerprint": fingerprint,
    "marker_before_active": True,
    "hooks": 4,
    "status": "clean",
}, sort_keys=True))
PY
```

A failure proves the startup workspace was published without its required state.
Do not repair it during S9.

## 8. Create a separate managed logical session through the shipped CLI root

This operation creates no run and performs no provider/model request.

```bash
SESSION_STARTED_NS=$(date +%s%N)
SESSION_JSON=$(docker compose -f "$COMPOSE" exec -T "$SERVICE" \
  python3 -I -B - <<'PY'
import json
from types import SimpleNamespace
from fa.cli import _session_manager_for_args

manager = _session_manager_for_args(SimpleNamespace(workspace=None))
session = manager.create_or_attach_session(session_id=None, workspace_override=None)
print(json.dumps({
    "session_id": session.session_id,
    "workspace": str(session.workspace_path),
}, sort_keys=True))
PY
)
SESSION_FINISHED_NS=$(date +%s%N)
printf '%s\n' "$SESSION_JSON"
printf 'fresh_session_wall_ms=%s\n' "$(((SESSION_FINISHED_NS-SESSION_STARTED_NS)/1000000))"

SID=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["session_id"])' \
  <<<"$SESSION_JSON")
WS=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["workspace"])' \
  <<<"$SESSION_JSON")
case "$SID" in *[!A-Za-z0-9_.-]*|'') exit 3;; esac
test "$WS" = "/sessions/$SID"
```

Run the verifier from §7 again with `WS`, `SID`, and
`CHECK_ACTIVE_ORDER=0`. It must produce the same B2/identity/readiness state and
must not change `/sessions/.active`.

Then measure the warm read-only state:

```bash
WARM_STARTED_NS=$(date +%s%N)
WARM_JSON=$(docker compose -f "$COMPOSE" exec -T -e WS="$WS" "$SERVICE" \
  python3 "$WS/scripts/bootstrap/workspace.py" check --workspace "$WS")
WARM_FINISHED_NS=$(date +%s%N)
printf '%s\n' "$WARM_JSON"
printf 'warm_check_wall_ms=%s\n' "$(((WARM_FINISHED_NS-WARM_STARTED_NS)/1000000))"
python3 -c 'import json,sys; p=json.load(sys.stdin); assert p["status"]=="ready" and p["reason_code"]=="ready_fast_path"' \
  <<<"$WARM_JSON"

docker compose -f "$COMPOSE" exec -T -e WS="$WS" "$SERVICE" sh -c '
  du -sh "$WS/.venv" /tmp/uv-cache /home/fa/.cache/pre-commit 2>/dev/null
  df -T "$WS" /tmp/uv-cache /home/fa/.cache
'
```

Record:

```text
LOGICAL_SESSION_ID=
LOGICAL_SESSION_WORKSPACE=
FRESH_SESSION_WALL_MS=
WARM_CHECK_WALL_MS=
READY_FINGERPRINT=
PROVIDER_MODEL_CALLS=0 (composition root did not call begin_run/provider code)
```

## 9. Real commit through installed hooks

Capture the remote feature branch and create one harmless proof file.

```bash
BRANCH=$(docker compose -f "$COMPOSE" exec -T -e WS="$WS" "$SERVICE" \
  git -C "$WS" branch --show-current | tr -d '\r')
test "$BRANCH" = "agent/$SID"
PROOF_FILE="s9-live-readiness-proof-$SID.txt"

docker compose -f "$COMPOSE" exec -T -e WS="$WS" -e PROOF_FILE="$PROOF_FILE" \
  "$SERVICE" sh -eu -c '
    printf "S9 managed workspace readiness proof\n" > "$WS/$PROOF_FILE"
    git -C "$WS" add -- "$PROOF_FILE"
    env -u GIT_AUTHOR_NAME -u GIT_AUTHOR_EMAIL \
        -u GIT_COMMITTER_NAME -u GIT_COMMITTER_EMAIL \
      git -C "$WS" commit -m "test: live managed workspace readiness proof"
  '
```

Required:

```text
commit succeeded with local First Agent identity
prepare-commit-msg, pre-commit, and commit-msg executed successfully
no bootstrap warning appeared
```

## 10. Publish the disposable feature branch

Do not set `FA_HOOK_SKIP_FULL_CHECK` and do not use `--no-verify`.

```bash
docker compose -f "$COMPOSE" exec -T -e WS="$WS" -e BRANCH="$BRANCH" \
  "$SERVICE" git -C "$WS" push --set-upstream origin "$BRANCH"

docker compose -f "$COMPOSE" exec -T -e WS="$WS" -e BRANCH="$BRANCH" \
  "$SERVICE" sh -eu -c '
    push_url=$(git -C "$WS" remote get-url --push origin)
    test "$push_url" = "git@github.com:first-agent-dev/First-Agent-dev.git"
    git ls-remote --exit-code "$push_url" "refs/heads/$BRANCH" >/dev/null
  '
```

Record:

```text
FEATURE_BRANCH=
FEATURE_COMMIT_SHA=
REMOTE_REF_PRESENT=yes|no
PRE_PUSH_GATE_RC=
```

## 11. Prove source authority remained unchanged

```bash
SOURCE_HEAD_AFTER=$(docker compose -f "$COMPOSE" exec -T "$SERVICE" \
  git -C /repo rev-parse HEAD | tr -d '\r')
SOURCE_STATUS_HASH_AFTER=$(docker compose -f "$COMPOSE" exec -T "$SERVICE" \
  sh -c 'GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false -C /repo \
    status --porcelain=v1 --untracked-files=all | sha256sum' | awk '{print $1}')

test "$SOURCE_HEAD_AFTER" = "$SOURCE_HEAD_BEFORE"
test "$SOURCE_STATUS_HASH_AFTER" = "$SOURCE_STATUS_HASH_BEFORE"
printf 'SOURCE_HEAD_AFTER=%s\n' "$SOURCE_HEAD_AFTER"
printf 'SOURCE_STATUS_HASH_AFTER=%s\n' "$SOURCE_STATUS_HASH_AFTER"
```

Any mismatch is a blocker. Preserve the session and stop.

## 12. GitHub PR, CI, and human boundary — manual direct steps

1. Open this URL in a browser, replacing `<FEATURE_BRANCH>` exactly:

   ```text
   https://github.com/first-agent-dev/First-Agent-dev/compare/main...<FEATURE_BRANCH>?expand=1
   ```

2. Create a disposable PR titled `test: S9 managed workspace live proof`.
3. Confirm the PR contains only the one proof file.
4. Wait for every required GitHub check to finish. Record the PR and Actions URLs.
5. Confirm the merge UI reports that human review/required checks govern merge.
   The agent container has a deploy key for branch publication, not an operator
   browser/API credential. Do not test protection by attempting a destructive
   direct push to `main`.
6. Do **not** merge the disposable PR. Close it after recording the evidence.
7. Delete the remote feature branch from the GitHub UI.
8. Confirm the ref is absent:

```bash
docker compose -f "$COMPOSE" exec -T -e WS="$WS" -e BRANCH="$BRANCH" \
  "$SERVICE" sh -eu -c '
    push_url=$(git -C "$WS" remote get-url --push origin)
    test -z "$(git ls-remote "$push_url" "refs/heads/$BRANCH")"
  '
```

Record:

```text
DISPOSABLE_PR_URL=
CI_RUN_URL=
REQUIRED_CHECKS=green|red
HUMAN_REVIEW_BOUNDARY=observed|not-observed
PR_CLOSED_WITHOUT_MERGE=yes|no
REMOTE_BRANCH_DELETED=yes|no
```

If the merge UI permits unreviewed merge for the agent authority or required
checks are absent, set `S9_STATUS=BLOCK` and do not alter repository rules during
the evidence run.

## 13. Guarded disposable-session cleanup

Run only after the PR is closed and the remote branch is deleted. The cleanup
refuses to remove the active startup workspace.

```bash
docker compose -f "$COMPOSE" exec -T -e SID="$SID" -e WS="$WS" \
  "$SERVICE" python3 -I -B - <<'PY'
import json
import os
import re
import shutil
from pathlib import Path

sid = os.environ["SID"]
ws = Path(os.environ["WS"])
assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", sid)
assert ws == Path("/sessions") / sid
active = Path("/sessions/.active")
if active.is_file():
    assert active.read_text(encoding="utf-8").strip() != str(ws)
session_dir = Path("/home/fa/.fa/sessions") / sid
manifest = session_dir / "manifest.json"
assert manifest.is_file()
data = json.loads(manifest.read_text(encoding="utf-8"))
assert data["session_id"] == sid
assert Path(data["workspace_path"]) == ws
shutil.rmtree(ws)
shutil.rmtree(session_dir)
assert not ws.exists() and not session_dir.exists()
print("disposable_session_cleanup=complete")
PY
```

Re-run the read-only baseline:

```bash
cd "$REPO"
bash ./fa-bootstrap-preflight-probe.sh | tee /tmp/fa-s9-post-cleanup.txt
grep -F 'probe=complete (read-only diagnostics; no session or LLM was created)' \
  /tmp/fa-s9-post-cleanup.txt
test "$(git rev-parse HEAD)" = "$MERGED_SHA"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
```

## 14. Final result checklist

Every row requires direct evidence; do not infer PASS from local tests.

- [ ] implementation PR CI was green before human merge;
- [ ] operator `fa update` deployed exactly `MERGED_SHA`;
- [ ] tracked A1 probe completed before and after the live run;
- [ ] startup workspace had B2 routing, identity, readiness, and marker-before-active;
- [ ] CLI composition root created a separate fresh managed logical session;
- [ ] both managed producers had `.venv`, four seats, marker, sentinel, and no copied `.env.fa`;
- [ ] real identity-cleared commit passed installed hooks;
- [ ] real feature-branch push passed pre-push and appeared on GitHub;
- [ ] `/repo` HEAD/status hash remained unchanged;
- [ ] required PR CI became green;
- [ ] human merge boundary was observed without a direct-main push experiment;
- [ ] disposable PR closed without merge and remote branch deleted;
- [ ] disposable logical session/state removed safely;
- [ ] cold/warm sizes and timings recorded;
- [ ] no provider/model call or secret output occurred.

Final binary field—fill only after every checkbox is evidenced:

```text
S9_STATUS=PENDING
FEATURE_PRODUCTION_READINESS=UNCLAIMED
```

Allowed terminal states:

- `S9_STATUS=PASS` and `FEATURE_PRODUCTION_READINESS=VERIFIED`;
- `S9_STATUS=BLOCK` with the failed step, raw safe output, owner, and rollback.

Do not append a completion summary to the main plan until this report contains a
terminal state and all cleanup evidence.
