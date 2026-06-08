INTENT override: classifier suggested none (no src/tests/adr/research/ci paths match); overridden to CHORE because this is non-semantic deployment infrastructure with no logic or rule changes.
INTENT: CHORE
INVARIANT: n/a — non-semantic deployment infrastructure and documentation; no logic or rule changes.

## What ships

Production-ready deployment suite for running First-Agent 24/7 on a dedicated Ubuntu Desktop 24.04 AIO (Intel i5-1235U / 16GB). The stack is derived from a three-source cross-reference analysis (`knowledge/research/First-Agent-ops-cross-reference.md`) that consolidated recommendations from independent LLM research passes into an authoritative SSOT.

The suite covers the full lifecycle: host hardening → container runtime → remote access → Git authentication → backup → power management → bootstrap documentation.

## Files changed

| File | Change |
|------|--------|
| `scripts/setup-fa-desktop.sh` | Complete rewrite. Automated hardening script: conservative Ubuntu Desktop pruning, Docker CE from official repo with `apt-mark hold`, Tailscale, SSH hardening (key-only over `tailscale0`), UFW, `power-profiles-daemon`, `xset dpms` aggressive blanking, `unattended-upgrades` with auto-reboot at 04:00, Docker `live-restore` + log rotation, weekly `docker image prune`, systemd lingering, deploy key generation, known_hosts pinning. |
| `scripts/fa.service` | New. Systemd user service with `OOMScoreAdjust=-500`, `Restart=on-failure`, network/tailscale dependencies. |
| `scripts/backup-fa.sh` | New. `restic` backup to Backblaze B2 (S3-compatible endpoint). Backs up state, secrets, host config (ssh, logind, docker daemon, systemd service), compose files. Excludes Python caches. Retention: 7 daily + 4 weekly + 6 monthly. |
| `docker-compose.fa.yml` | Updated. Hardened container: `read_only: true`, `cap_drop: [ALL]`, `no-new-privileges`, `pids_limit: 512`, `init: true`, `hostname: first-agent`, resource limits (8GB/8 CPU), tmpfs layers (`/tmp`, `~/.cache`, `~/.local`, `/tmp/uv-cache`), deploy key at `/run/secrets/git_key`, `GIT_SSH_COMMAND` with `IdentitiesOnly=yes`. |
| `Dockerfile.fa` | Updated. Ubuntu 24.04 base with `uv`, `just`, Python 3.13, non-root user (`fa:1000`), `/run/secrets` mount point. Placeholder `sleep infinity` entrypoint until M-8 runtime is wired. |
| `knowledge/SETUP_AIO.md` | New. 10-phase bootstrap guide: BIOS tuning → Ubuntu install → script execution → Tailscale auth → deploy key setup → container build → Git push test → backup config → power verification. Includes operational quick reference, recovery procedures, troubleshooting, and process-toggle options (Tailscale SSH / SSH exec / future webhook). |
| `.dockerignore` | New. Build context exclusions for faster image builds. |
| `.gitignore` | Updated. Added `.env*`, `*.log`, `.DS_Store`, `Thumbs.db`. |

## Design rationale

**Tailscale as sole remote access.** SSH is hardened to key-only auth and UFW restricts port 22 to the `tailscale0` interface only. This avoids exposing any service to the public internet. The cross-reference unanimously recommended Tailscale over WireGuard or reverse SSH for homelab use.

**Conservative pruning over aggressive removal.** The cross-reference showed disagreement on Ubuntu Desktop pruning depth. We mask (`systemctl mask`) rather than purge packages like `tracker-miner-fs-3`, avoiding the metapackage breakage that aggressive removal causes. This follows the "start conservative, measure, then cut deeper" approach.

**Bind mounts over named volumes.** The workspace lives at `/srv/first-agent/` with explicit bind mounts for repo, state, and secrets. This makes host-level backup (`restic`) straightforward and avoids the opacity of Docker named volumes.

**No TLP, no Portainer, no auto-login.** The cross-reference converged on: `power-profiles-daemon` (not TLP) for desktop AIOs; raw `docker compose` via systemd (not Portainer/Dockge) for a single-container setup; manual login for emergency GUI access (not auto-login which is an attack surface).

**Process toggle: documented, not engineered.** The cross-reference explicitly calls the "container stays up; agent toggles without SSH" problem a tooling ecosystem gap with no off-the-shelf solution. Rather than building custom webhook infrastructure prematurely, we document three options — Tailscale mobile terminal (zero code), SSH exec (one command), and a future iOS Shortcuts + webhook architecture — and recommend the zero-friction path today.

## Scope / ordering

- All inline templates in `setup-fa-desktop.sh` are byte-for-byte consistent with their standalone counterparts in `scripts/`.
- The setup script is non-interactive and deploy-ready (cloud-init, Packer, or manual execution).
- No changes to `src/fa/**` or `tests/**`. The container entrypoint (`sleep infinity`) is a placeholder; wiring the actual `fa run --task` loop is a separate PR.

## Review & Testing Checklist

- [ ] `scripts/setup-fa-desktop.sh` syntax: `bash -n scripts/setup-fa-desktop.sh`
- [ ] `docker-compose.fa.yml` syntax: `docker compose -f docker-compose.fa.yml config`
- [ ] `.dockerignore` does not exclude files needed at build time
- [ ] `.gitignore` `.env*` rule does not block any committed example file
- [ ] `fa.service` parses: `systemd-analyze verify scripts/fa.service`
- [ ] `backup-fa.sh` syntax: `bash -n scripts/backup-fa.sh`
- [ ] `SETUP_AIO.md` renders correctly in GitHub preview (no broken markdown tables)

## Notes

- `knowledge/llms.txt` and `HANDOFF.md` were updated in the preceding session segment and are already reflected on this branch.
- The branch follows the `devin/<timestamp>-<slug>` convention per `AGENTS.md` §Development Workflow.

## AI-Session trailer

All commits in this PR driven by LLM-agent session.
