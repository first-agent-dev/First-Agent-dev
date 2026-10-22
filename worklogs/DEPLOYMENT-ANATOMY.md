# FA host/deployment anatomy (for humans and agents)

Verified summary for host `fa@fa-HP` (as of 2026-10-22). Execution is via managed workspace (managed views + cells) — see `knowledge/project-overview.md §5.1` and `i03-execution-workspace-spec`.

## Participants
- **Host:** `fa@fa-HP` (Ubuntu), user `fa` (non-root, needs `sudo` for `/srv/first-agent`, docker).
- **Repository:** `/srv/first-agent/repo/First-Agent-dev` (NOT `~/First-Agent-dev`).
- **Wrapper `/usr/local/bin/fa`** → symlink to `<repo>/scripts/fa`.
- **Container `first-agent`** — FA Python code, **has no LLM keys**.
- **Container `fa-egress-proxy`** — injects keys upstream, listens at `http://fa-egress-proxy:8080`.

## Bind mounts (`docker-compose.fa.yml`)

| host source | container target | mode | contents |
|---|---|---|---|
| `<repo>` | `/repo` | ro | sources (build-context, not runtime import) |
| `/srv/first-agent/sessions` | `/sessions` | rw | per-session workspace clones |
| `/srv/first-agent/state` | `/home/fa/.fa` | rw | state root: runs, session.db, drafts |
| `/srv/first-agent/routing/models.yaml` | `/home/fa/.fa/models.yaml` | ro | active role routing |
| `/srv/first-agent/secrets/fa_proxy_token` | `/run/secrets/fa_proxy_token` | ro | fa→proxy token |
| `/srv/first-agent/secrets/fa.env` | `/run/secrets/fa.env` | ro, **proxy only** | real API keys |

Agent **does not see** `fa.env` — the proxy injects keys itself.

### Managed workspace mounts

| host source | container target | mode | contents |
|---|---|---|---|
| `/srv/first-agent/workspaces` | `/workspaces` (ro FD) | `RootedViewIO` | materialized views (`view.json`/`terminal.json`/`seal/manifest.json`) — supervisor opens via `O_NOFOLLOW\|O_CLOEXEC` |
| `/srv/first-agent/workspaces/<ws>/views/<view>/cache` | `cache_dir` | rw | private indexes `search.db`/`structural.db` — not in project tree |
| private UDS `supervisor.sock` (0600) | `supervisor.sock` | — | `WorkspaceAuthority` + `CellBackend` — only supervisor holds Docker socket; controller/cells do not see it |
| `cgroup v2` `populated` | — | — | `stop_view` waits for `populated=0` — terminal barrier |

## Host prerequisites

- **cgroup v2** with `populated` — `stat -fc %T /sys/fs/cgroup` must be `cgroup2fs`; `docker info | grep -i cgroup` must show `systemd, Version: 2`. `stop_view` waits for `cgroup populated=0`.
- **Docker CE** with `live-restore` and log rotation (`10m/3`); image is pre-installed and immutable (`/opt/first-agent/src` + `/opt/fa-venv`), not `pip install` at runtime.
- **Private UDS** `supervisor.sock` at `/run/fa/supervisor.sock` (`0600`, controller group only) — only the supervisor holds the Docker socket; controller/cells see only the UDS.
- **Filesystem:** `/srv/first-agent/workspaces` (managed views), `/srv/first-agent/sessions` (`/sessions`), `/srv/first-agent/state` (`~/.fa`), `/srv/first-agent/routing/models.yaml`, and `/opt/toolchain-cache` (read-only toolchain cache in cells).
- **Check on any host:**
  ```bash
  stat -fc %T /sys/fs/cgroup; docker info | grep -i cgroup; ls -l /run/fa/supervisor.sock; ls -ld /srv/first-agent/workspaces
  ```

## How code gets into the container
- `Dockerfile.fa` copies `src/` into `/opt/first-agent/src` and runs `uv sync --frozen --no-dev` → `/opt/fa-venv` during `docker build`.
- Runtime imports come from `/opt/first-agent/src`, venv `/opt/fa-venv`.
- `/repo` bind-mount is **not** used for runtime import.
- Python code changes require `fa update` (git pull + build + up + smoke).
- `/usr/local/bin/fa` inside the container is `scripts/fa-entrypoint.sh`, which ultimately calls `fa` from `/opt/fa-venv/bin`.

## How `fa ...` is routed from the host
`scripts/fa` (host wrapper):
1. `COMPOSE=(docker compose -f <repo>/docker-compose.fa.yml)`.
2. Infra verbs (`logs|status|up|down|restart|update|shell|...`) run on the host via `exec "${COMPOSE[@]}" ...`.
3. Other commands (`run|probe|conformance|selfcheck|workflow|...`) → `exec "${COMPOSE[@]}" exec first-agent fa "$@"` **inside the container**.
4. `TTY_FLAG=(-T)` if stdin is not a terminal; otherwise empty (TTY passthrough).
5. **Host env vars are not forwarded** into `docker compose exec` by default. Use `-e VAR=...`.

## Artifacts inside the container
| path | what |
|---|---|
| `~/.fa/models.yaml` | bind to `/srv/first-agent/routing/models.yaml` (ro) |
| `~/.fa/session-log/<run_id>/` | per-run logs: `events.jsonl`, `llm_bodies.jsonl`, `manifest.json` |
| `~/.fa/session-log/conformance/conf-<prov>-<ts>/` | live-conformance results |
| `~/.fa/sessions/<uuid>/session.db` | authoritative SQLite (`event_log` table, including usage rows) |
| `/sessions/<session-id>/` | workspace clone for the current session (`/workspace` in cell) |
| `/run/secrets/fa_proxy_token` | fa→proxy token |

`events.jsonl` is a projection; read `session.db` for cache-ratio.

### View artifacts (authority is the supervisor, not `~/.fa`)

| path (inside cell) | what |
|---|---|
| `/workspace` | read-only snapshot of `base_revision` (what `RootedViewIO` sees) |
| `/scratch` | writable view scratch (where tools write) |
| `/opt/toolchain-cache` | read-only toolchain cache |
| `workspaces/<ws>/views/<view>/terminal.json` | receipt `TERMINAL` after `cgroup populated=0` |
| `workspaces/<ws>/views/<view>/seal/manifest.json` | `tree_sha256` + entries (immutable export) |

## Proxy mode (critical!)
When `FA_EGRESS_PROXY_URL` is set (it is inside the container):
- Agent runs with `SecretStore({})` (empty); no local keys needed.
- Must call `_proxy_rewrite_chain(chain, proxy_url)` → rewrites `entry.base_url` to `<proxy>/route/<name>` and adds `X-FA-Proxy-Token` to `extra_headers`. **Miss it → 401 on every request.**
- Already done in `_cmd_probe`, `_cmd_run`, and after the fix — in `_run_live_conformance`. New CLI commands that hit a provider must repeat this pattern.
- `SecretRedactor.from_models_config(secrets, models, extra_values=_proxy_redactor_extra(), allow_empty=True)`.

## Live conformance for a single provider
- `fa conformance --provider X` always tests role **`coder`**, its **`chain[0]`**.
- To test a provider without touching the live `models.yaml`, create a temporary yaml at `/tmp/conf-X.yaml` with a single role `coder` whose chain[0] points to the desired provider, then run:
  ```bash
  docker compose ... exec -e FA_DEBUG_LLM_BODIES=1 first-agent \
    fa conformance --provider X --config /tmp/conf-X.yaml
  ```
- `--provider X` only affects run-id/labels; the real chain is taken from `coder.chain`.

## Debugging: running from the host
### Forcing env into the container:
```bash
docker compose -f <repo>/docker-compose.fa.yml exec -e FA_DEBUG_LLM_BODIES=1 first-agent fa <cmd>
```
Add `-T` for non-interactive; otherwise keep TTY.

### llm_bodies.jsonl:
Enabled with `FA_DEBUG_LLM_BODIES=1`; for conformance it lives at `~/.fa/session-log/conformance/conf-<prov>-<ts>/llm_bodies.jsonl`. Stream capture requires `wrap_transport_for_debug_bodies` — call it in any new CLI command as well.

### Cache-hit ratio:
Formula: `cache_read / (cache_read + cache_creation + uncached_input)` over rows with `kind='usage'` in `session.db`.
Response fields: `cache_read_input_tokens`, `cache_creation_input_tokens`, `input_tokens`. Find the `session.db` for a given run_id by scanning `~/.fa/sessions/**/session.db` for `run_id` substring in content.

## Agent checklist for live tests
1. Edit in sandbox `/home/user/First-Agent-dev`.
2. `uv run pytest -q` — full green run.
3. `bash -n scripts/*.sh`; verify manually that functions are defined before use.
4. For proxy-mode commands must:
   - load `models` with `require_api_keys=not proxy_mode`,
   - call `_proxy_rewrite_chain`,
   - wrap transport via `wrap_transport_for_debug_bodies` with `SecretRedactor(..., allow_empty=True)`.
5. Generate patch, verify `git apply` in a **clean checkout** of the target HEAD.
6. Give the user commands via heredoc `cat >/tmp/patch <<'EOF' ... EOF` (most reliable over SSH).
7. Host update order for the user: `git apply` → `commit/push` → `fa update` → live checks via direct `docker compose exec -e ...`.

## Common pitfalls
1. Do not use `fa <cmd> -e VAR=...` — wrapper does not forward env.
2. Do not extend the live `~/.fa/models.yaml` in experiments — use `/tmp/conf-*.yaml`.
3. Do not `cd ~/First-Agent-dev`; repo is at `/srv/first-agent/repo/First-Agent-dev`.
4. `fa-update.sh` uses `flock -n /tmp/fa-update.lock`. If "Another fa-update is running" — check `ps -p <pid>`, don't kill blindly.
5. Never use `set -m` + `kill -- -$$` in shell scripts — breaks sudo (pgroup signal from sudo + EXIT-trap panic → "Killed"). Reap children by PID, tracking long-lived descendants.
6. Bash functions must be defined above their call site.
7. Always state the base commit for a patch; if the user already committed a previous version — incremental patch or first `git checkout <base-sha> -- <file>`.

## Useful one-liners (host)
```bash
# Zombie/lock after fa-update
for p in $(ps -eo pid,cmd | grep -E 'fa-update\.sh|docker compose -f .*docker-compose\.fa\.yml' \
           | grep -v grep | awk '{print $1}'); do kill -KILL $p 2>/dev/null; done
rm -f /tmp/fa-update.lock

# Agent logs
docker compose -f <repo>/docker-compose.fa.yml logs --tail=200 first-agent

# Proxy check
docker compose -f <repo>/docker-compose.fa.yml exec first-agent fa probe
```
