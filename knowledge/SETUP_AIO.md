# First-Agent AIO Deployment Bootstrap

> **Cross-referenced, production-tested stack for running FA 24/7 on a dedicated Intel i5-1235U / 16GB AIO.**
> Canonical research: [`knowledge/research/First-Agent-ops-cross-reference.md`](./research/First-Agent-ops-cross-reference.md)
> Hardware: Intel i5-1235U (2P+8E, 12 threads), 16GB DDR4, NVMe SSD, AIO form factor.

## What You'll Have After This Guide

- **Ubuntu Desktop 24.04 LTS** running headless-ish (GUI available for emergency local access).
- **Docker CE** from the official docker.com repo with a hardened, read-only FA container.
- **Tailscale** as the sole remote access path — SSH is reachable **only** over the Tailscale interface.
- **systemd user service** auto-starting FA on boot.
- **SSH deploy key** for scoped, non-expiring git push from the container.
- **restic → Backblaze B2** (S3-compatible endpoint) for nightly off-site backup.
- Expected idle: **~1.5–2.4 GB RAM used**, **~15–30W at wall**.

---

## Phase 0 — Prerequisites

| Item | Requirement |
|------|-------------|
| **USB stick** | 8GB+ for Ubuntu Desktop 24.04 LTS installer |
| **Internet** | Wired Ethernet preferred (no Wi-Fi driver hassles) |
| **Tailscale account** | Free tier (20 devices) at [tailscale.com](https://tailscale.com) |
| **GitHub account** | Repo access to add deploy keys and branch protection |
| **Backblaze B2** | Free tier (10GB) for off-site backup |
| **Phone** | iOS/Android Tailscale app for remote verification |
| **Kill-a-watt or smart plug** | Optional — measure idle power at wall |

---

## Phase 1 — BIOS Setup (before installing Ubuntu)

Boot into the AIO's BIOS/UEFI setup. These settings are **critical** for 24/7 idle power.

| Setting | Value | Why |
|---------|-------|-----|
| **CPU C-states** | Enabled | Allows CPU to drop to deep sleep states |
| **Package C-state limit** | C10 (or C8 if C10 unavailable) | Deepest idle state |
| **PCIe ASPM** | L1 substates | Power-gate PCIe lanes |
| **Intel SpeedShift** | Enabled | Faster P-state transitions |
| **Restore on AC Power Loss** | Power On | Auto-boot after power outage |
| **Wake on LAN** | Disabled | Unnecessary attack surface |
| **Legacy USB / Serial** | Disabled if unused | Saves a few watts |
| **Secure Boot** | Optional — disable if Linux drivers complain | |

Save and exit.

---

## Phase 2 — Install Ubuntu Desktop 24.04 LTS

1. Boot from the Ubuntu USB stick.
2. Select **"Try or Install Ubuntu"**.
3. At the installer, choose **"Minimal installation"** (not the full one with office suites and games).
4. **Disk setup:** ZFS or ext4 — both work. ZFS has built-in snapshots; ext4 is simpler. Pick one.
5. **User setup:**
   - Create your primary user (e.g., `fa`).
   - Set a strong password.
   - **Do NOT check "automatic login"** — the cross-reference flagged this as a security risk.
6. Finish the install, reboot, remove the USB stick.

---

## Phase 3 — First Boot & Network

1. At the GNOME login screen, log in normally.
2. Connect to Ethernet (or Wi-Fi if Ethernet is unavailable).
3. Open a terminal (`Ctrl+Alt+T`).
4. Verify internet:
   ```bash
   curl -I https://github.com
   ```

---

## Phase 4 — Get the Setup Script

**Option A: On your laptop (review before deploying)**
```bash
git clone https://github.com/first-agent-dev/First-Agent-dev.git ~/First-Agent-dev
cd ~/First-Agent-dev
less scripts/setup-fa-desktop.sh
# Copy to USB or scp to AIO
```

**Option B: Directly on the AIO (if already logged in)**

```bash
# Download just the script — the repo will be cloned to /srv/... automatically
curl -fsSL -o /tmp/setup-fa-desktop.sh \
  https://raw.githubusercontent.com/first-agent-dev/First-Agent-dev/main/scripts/setup-fa-desktop.sh
less /tmp/setup-fa-desktop.sh
bash /tmp/setup-fa-desktop.sh
```
- The script is idempotent — you can re-run it safely.

**What the script does (from the cross-reference):**

- Updates system packages.
- Removes `gnome-software` (known memory leaks ~2-3GB).
- **Masks** (not removes) `tracker-miner-fs-3.service` — removing the package breaks the `ubuntu-desktop` metapackage.
- Disables `whoopsie` and `apport` (crash reporting).
- Disables Bluetooth.
- Dual-locks suspend prevention (`gsettings` + `logind.conf.d` drop-in).
- Sets screen blank to **60 seconds**, no lock.
- Sets power profile to **power-saver** via `power-profiles-daemon`.
- Hardens SSH: key-only, no root, `AllowUsers` (single account). The
  source-restricted **Tailscale CGNAT-range** layer (`sshd Match Address`) is
  applied separately by `scripts/ssh-tailscale/` — see Phase 5b.
- Configures UFW: default deny incoming; allows SSH **only** via `tailscale0` interface.
- Installs Docker CE from the **official docker.com apt repo** (not Ubuntu snap).
- Installs Tailscale.
- Creates `/srv/first-agent/{repo,state,secrets,backup,scripts}`.
- Generates an **ED25519 deploy key**.
- Pins GitHub's Ed25519 host key in `/srv/first-agent/secrets/known_hosts`.
- Installs `restic`.
- Sets `xset dpms 0 0 60` for aggressive AIO panel backlight blanking (~5-15W savings).
- Pins Docker CE packages with `apt-mark hold` to prevent surprise upgrades.
- Enables Docker `live-restore` + daemon-level log rotation (10m/3 files) so containers survive daemon restarts and logs don't fill the disk.
- Adds weekly `docker image prune -f` cron job (scoped to unused images only).
- Configures unattended-upgrades with **auto-reboot at 04:00**.
- Enables systemd **lingering** so user services survive logout and auto-start after reboot.
- Installs a systemd user service template at `~/.config/systemd/user/fa.service`.
- Creates a backup script template.

**After the script finishes, follow the printed next steps.**

---

## Phase 5 — Tailscale Authentication

```bash
sudo tailscale up --ssh
```

1. A URL will print to the terminal. Open it on your phone or laptop.
2. Log in with your Tailscale account.
3. The AIO is now on your tailnet.

**Verify from your phone (on cellular, not Wi-Fi):**

1. Open the Tailscale app.
2. You should see the AIO listed.
3. Copy the AIO's Tailscale IP (e.g., `100.x.y.z`).

**Test SSH over Tailscale:**

```bash
# From your laptop (NOT the AIO)
ssh fa@100.x.y.z
```

If this works, you've confirmed remote access without exposing SSH to the public internet.

---

## Phase 5b — SSH-over-Tailscale defense-in-depth hardening

`setup-fa-desktop.sh` (Phase 4) sets up the base SSH/UFW posture. To add the
remaining defense-in-depth layers from the ops SSOT — UFW IPv6 filtering,
`sshd Match Address` scoped to the Tailscale CGNAT ranges, a fail2ban jail with
the **systemd** backend (correct for 24.04), and a Tailscale ACL — run the
idempotent scripts in
[`scripts/ssh-tailscale/`](../scripts/ssh-tailscale/README.md). They include a
dead-man failsafe so a firewall/sshd mistake cannot lock you out.

```bash
cd /srv/first-agent/repo/First-Agent-dev/scripts/ssh-tailscale
sudo bash 10-diagnose.sh                       # read-only audit (run first)
sudo bash 00-failsafe.sh arm                   # + open a SECOND ssh session
sudo SSH_USER=fa bash 20-harden.sh    # apply layers (reload, not restart)
sudo bash 30-verify.sh                          # checklist; non-zero exit on fail
# apply tailscale-acl.jsonc in the admin console, then:
sudo bash 00-failsafe.sh disarm                 # only after a fresh login works
```

> **Which `:22` are you on?** `tailscale up --ssh` (Phase 5) makes `tailscaled`
> answer the Tailscale IP `:22`, **not** system `sshd`. Tailscale SSH sessions
> are governed by the ACL `ssh` rules in `tailscale-acl.jsonc`; the `sshd`
> Match-Address / UFW / fail2ban layers harden the classic `sshd` recovery path
> (LAN, or if Tailscale SSH is disabled). `10-diagnose.sh` reports which server
> is answering. See the script
> [`README`](../scripts/ssh-tailscale/README.md) for details.

---

## Phase 6 — GitHub Deploy Key + Branch Protection

1. In the AIO terminal, the setup script printed your **public deploy key**:
   ```bash
   cat /srv/first-agent/secrets/github_deploy_key.pub
   ```
2. Go to your GitHub repo → **Settings** → **Deploy keys** → **Add deploy key**.
3. Paste the public key, give it a title (e.g., `fa-aio-deploy`), and **check "Allow write access"**.
4. Go to **Settings** → **Branches** → **Add rule** for `main`:
   - Check **"Require a pull request before merging"**.
   - Check **"Require approvals"** (set to 1).
   - This prevents the agent from accidentally force-pushing to `main`.
5. The agent should push to branches named `agent/yyyy-mm-dd-topic`.

---

## Phase 6b — SSH Troubleshooting & Host Config

The setup script creates `~/.ssh/config` so the **host shell** (not just the container) can fetch/pull from GitHub using the deploy key. This matters because:

1. **Host-level git operations** (`git fetch`, `git pull` on the AIO shell) need the deploy key too — not just the container.
2. **Known hosts rotation** — GitHub rotates its Ed25519 host key periodically. If you see `WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!`, update the pinned key:
   ```bash
   ssh-keygen -f '/srv/first-agent/secrets/known_hosts' -R 'github.com'
   ssh-keyscan -H -t ed25519 github.com >> /srv/first-agent/secrets/known_hosts
   ```
3. **Container sees stale known_hosts** — the mount is read-only in the container. After updating on the host, run `docker compose -f docker-compose.fa.yml down && up -d` to remount.
4. **Deploy key without WRITE access** — GitHub deploy key must have "Allow write access" checked. Re-verify in repo Settings → Deploy keys.
5. **Verification checklist:**
   ```bash
   ssh -T git@github.com
   # Expected: "Hi <repo>! You've successfully authenticated..."
   ```

---

## Phase 7 — Build and Start the FA Container

The `docker-compose.fa.yml` and `Dockerfile.fa` in the repo root define the hardened container.

```bash
cd /srv/first-agent/repo/First-Agent-dev

# Build the image
docker compose -f docker-compose.fa.yml build

# Start in the background
docker compose -f docker-compose.fa.yml up -d

# Check logs
docker compose -f docker-compose.fa.yml logs -f
```

**One-shot bootstrap verification:**

After the container is up, run the post-setup script to verify git SSH, push a test branch, and enable the systemd service:

```bash
bash scripts/fa-post-setup.sh
```

This is idempotent — safe to re-run after any future `git pull` or `docker compose build`.

**Hardening applied (per cross-reference):**

- `read_only: true` — root filesystem is read-only.
- `cap_drop: [ALL]` — all Linux capabilities dropped.
- `cap_add: [CHOWN, SETGID, SETUID]` — only what's needed for uv/just.
- `security_opt: [no-new-privileges:true]` — container cannot gain new privileges.
- `pids: 512` under `deploy.resources.limits` — fork-bomb protection (Compose schema v3).
- `user: "1000:1000"` — runs as non-root.
- Resource limits: 8GB RAM max, 8 CPUs.
- Git key mounted at `/run/secrets/git_key` (read-only).
- `GIT_SSH_COMMAND` configured with `IdentitiesOnly=yes`.
- No `/var/run/docker.sock` mount.
- `init: true` — `tini` handles zombie process reaping (PID 1 responsibility).
- `hostname: first-agent` — identifiable in logs and `docker ps`.
- tmpfs mounts for `/tmp`, `~/.cache`, `~/.local`, `/tmp/uv-cache` — writable scratch space without compromising the read-only root fs.

**Restart policy:** The compose file uses `restart: unless-stopped`. This means:
- If the container crashes or the host reboots, it restarts automatically.
- If you **manually** run `docker compose down`, it stays down until you run `up` again.
- If you want the container to restart even after a manual `docker stop`, change to `restart: always` in `docker-compose.fa.yml`.

**Note on container entrypoint:** The Dockerfile currently runs `sleep infinity` as a placeholder. When FA's M-8 runtime loop (`fa run --task`) is wired into the container, replace the `CMD` in `Dockerfile.fa` with the actual entrypoint. Until then, the container stays alive and you can `docker exec` into it to run FA manually.

**Enable auto-start on boot:**

```bash
systemctl --user enable fa.service
systemctl --user start fa.service
```

---

## Phase 7b — Configure LLM API Keys

The deployment stack handles git auth (SSH deploy key) but never mentions LLM API keys. The compose file references `.env.fa` via `env_file:` — this is where your OpenRouter / Fireworks / etc. keys live.

1. Copy the template and edit with real keys:
   ```bash
   cd /srv/first-agent/repo/First-Agent-dev
   cp .env.fa.template .env.fa
   # Edit .env.fa with your keys
   chmod 600 .env.fa
   ```

2. Verify `models.yaml` exists (auto-copied by `setup-fa-desktop.sh`):
   ```bash
   ls /srv/first-agent/state/models.yaml
   ```
   If missing, copy from the example:
   ```bash
   cp knowledge/examples/models.yaml.example /srv/first-agent/state/models.yaml
   ```

3. **Convention separation:**
   - **Docker deployment** (AIO): uses `.env.fa` in repo root, loaded by compose.
   - **Local WSL dev**: uses `~/.fa/.env` (auto-loaded by CLI) or shell exports.
   - Never mix the two — the container does not read `~/.fa/.env`.

4. **Backup credentials** (`B2_KEY_ID`, `B2_APPLICATION_KEY`) belong in `/srv/first-agent/secrets/backup.env`, NOT in `.env.fa`. The container does not need them.

---

### Secrets Management

| Category | Storage | Scope |
| --- | --- | --- |
| **LLM API keys** | `.env.fa` (repo root) | Container runtime |
| **Backup credentials** | `/srv/first-agent/secrets/backup.env` | Host only (restic) |
| **Git deploy key** | `/srv/first-agent/secrets/github_deploy_key` | Host + container (read-only) |

**Why separation matters:**

- The operator user is in the `docker` group. Any member can `docker inspect` and see container env vars (including API keys from `.env.fa`). Backup credentials are never injected into the container, so a container compromise does not grant B2 access.
- `SecretRedactor` (exact-match + base64/URL encoding detection) masks secrets before they reach `events.jsonl` or `knowledge/trace/`. If a key leaks before redaction, the encrypted backup still contains it. Redaction is primary; encryption is secondary.
- restic encrypts backups *before* uploading to B2. Test restores quarterly to verify integrity.

---

### Security Notes for AIO Deployment

**Docker trust boundary.** The operator user is in the `docker` group. Any user in this group can run `docker inspect` and see container env vars (including API keys loaded from `.env.fa`). This is the trust boundary for the AIO deployment — keep the operator account exclusive.

**Docker log security.** Docker logs are not encrypted at rest. The compose uses `max-size: 10m`, `max-file: 3` to limit the leak window. FA's `SecretRedactor` masks API keys in `events.jsonl` before writing. Do NOT print API keys to stdout from FA code or tools.

**Backup security.** restic encrypts backups before sending to B2. If a key is leaked into `events.jsonl` before redaction, the encrypted backup still contains it. Redaction is the primary defense; encryption is secondary (protects against B2 compromise, not restore leakage). Test restores quarterly.

---

## Phase 8 — Test Git Push from the Container

```bash
# Enter the container
docker exec -it first-agent bash

# Test git can see the key
GIT_SSH_COMMAND="ssh -i /run/secrets/git_key -o IdentitiesOnly=yes -o UserKnownHostsFile=/run/secrets/known_hosts" git ls-remote $(git remote get-url origin | sed 's|https://github.com/|git@github.com:|')

# If that works, test a branch push
cd /workspace
git checkout -b agent/test-bootstrap
touch bootstrap-test.txt
git add bootstrap-test.txt
git commit -m "test: bootstrap verification"
GIT_SSH_COMMAND="ssh -i /run/secrets/git_key -o IdentitiesOnly=yes -o UserKnownHostsFile=/run/secrets/known_hosts" git push origin agent/test-bootstrap
```

If the push succeeds and appears on GitHub, your git auth is working end-to-end.

---

## Phase 8a — Process Toggle (How to Stop/Start FA Remotely)

> Cross-reference calls this a **tooling ecosystem gap** — there is no off-the-shelf "container stays up; agent toggles without SSH" solution.

Here are three options, from lowest friction to most sophisticated:

### Option A: Tailscale SSH (Recommended — Zero Custom Code)

The Tailscale mobile app has a built-in terminal. Two taps on your phone:

1. Open Tailscale app → tap the AIO machine.
2. Run: `systemctl --user stop fa.service` (or `start` to resume).

This stops the **entire container** (~10s). The container restarts automatically on next boot because `fa.service` is enabled.

### Option B: SSH Exec (Slightly Faster — One Command)

From your laptop:
```bash
ssh fa@100.x.y.z 'systemctl --user stop fa.service'
```

Or start it back up:
```bash
ssh fa@100.x.y.z 'systemctl --user start fa.service'
```

### Option C: iOS Shortcuts + Webhook (Future — One-Tap)

When you want a true one-tap button on your phone:

1. Deploy a tiny `adnanh/webhook` container alongside FA.
2. Configure it to receive an HTTP POST and run `docker exec first-agent pkill -f "fa run"`.
3. Expose the webhook **only** via Tailscale (never publicly).
4. Create an iOS Shortcut that sends the POST.

**Why this isn't implemented yet:** The cross-reference explicitly notes this is "custom engineering." Options A and B are fully functional today with no extra code.

---

## Phase 9 — Backup Configuration

1. Go to [Backblaze B2](https://www.backblaze.com/b2), create a bucket.
2. Generate an **Application Key** with read/write access to that bucket.
3. Edit `/srv/first-agent/scripts/backup-fa.sh`:
   ```bash
   B2_KEY_ID="your-key-id"
   B2_APPLICATION_KEY="your-app-key"
   B2_BUCKET="your-bucket-name"
   ```
4. Initialize the restic repository (one-time):
   ```bash
   cd /srv/first-agent/scripts
   export B2_KEY_ID="..."
   export B2_APPLICATION_KEY="..."
   export B2_BUCKET="..."
   export AWS_ACCESS_KEY_ID="$B2_KEY_ID"
   export AWS_SECRET_ACCESS_KEY="$B2_APPLICATION_KEY"
   RESTIC_REPO="s3:https://s3.us-west-004.backblazeb2.com/$B2_BUCKET"
   restic -r "$RESTIC_REPO" init
   ```
5. Test a backup:
   ```bash
   ./backup-fa.sh
   ```
6. Schedule nightly via cron:
   ```bash
   crontab -e
   # Add:
   0 3 * * * /srv/first-agent/scripts/backup-fa.sh >> /srv/first-agent/backup/backup.log 2>&1
   ```
7. **Test restore quarterly:**
   ```bash
   RESTIC_REPO="s3:https://s3.us-west-004.backblazeb2.com/$B2_BUCKET"
   restic -r "$RESTIC_REPO" restore latest --target /tmp/restore-test
   ```

---

## Phase 10 — Power Verification

1. **Check idle RAM:**
   ```bash
   free -h
   ```
   Expect: ~1.2–1.8 GB used by OS + Docker.

2. **Check power profile:**
   ```bash
   powerprofilesctl get
   ```
   Should say `power-saver`.

3. **Screen blank test:** Wait 60 seconds without touching mouse/keyboard. The screen should blank but the machine stays responsive over Tailscale SSH.

4. **Measure at wall** (if you have a kill-a-watt):
   - Screen on, idle: ~20–35W
   - Screen blanked: ~15–25W
   - Cross-reference target: ~7–15W for CPU+board alone (screen contributes the rest).

5. **powertop analysis** (optional):
   ```bash
   sudo powertop --html=/tmp/power-report.html
   ```
   Review the HTML for tunables, but **do not** enable `powertop --auto-tune` as a service — it is not persistent and can conflict with `power-profiles-daemon`.

---

## Operational Quick Reference

| Task | Command |
|------|---------|
| **Start FA** | `systemctl --user start fa.service` |
| **Stop FA** | `systemctl --user stop fa.service` |
| **Restart FA** | `systemctl --user restart fa.service` |
| **Check auto-reboot status** | `cat /etc/apt/apt.conf.d/50unattended-upgrades-fa` |
| **Manually trigger unattended upgrade** | `sudo unattended-upgrade --dry-run` |
| **View logs** | `docker compose -f /srv/first-agent/repo/First-Agent-dev/docker-compose.fa.yml logs -f` |
| **Enter container** | `docker exec -it first-agent bash` |
| **Check container status** | `docker ps` |
| **Tailscale status** | `tailscale status` |
| **Tailscale IP** | `tailscale ip -4` |
| **UFW status** | `sudo ufw status verbose` |
| **Run backup now** | `/srv/first-agent/scripts/backup-fa.sh` |
| **SSH over Tailscale** | `ssh fa@100.x.y.z` |
| **Emergency local access** | Plug in keyboard/mouse, log in at GNOME screen |

---

## Recovery Procedures

| Scenario | Recovery |
|----------|----------|
| **"Agent goes rogue"** | `systemctl --user stop fa.service && systemctl --user start fa.service` (~10s) |
| **"Container is wedged"** | `docker compose -f /srv/first-agent/repo/First-Agent-dev/docker-compose.fa.yml down && docker compose up -d` (~30s) |
| **"Tailscale won't connect"** | Local keyboard + monitor → `sudo tailscale up` again. WireGuard config on phone as cold backup. |
| **"NVMe dies"** | New NVMe → reinstall Ubuntu → run `scripts/setup-fa-desktop.sh` → `restic restore latest --target /srv/first-agent` (~30 min) |
| **"OS borked, data intact"** | Reinstall Ubuntu, run setup script, re-auth Tailscale, re-add deploy key, `systemctl --user start fa.service` (~1 hour) |
| **"Git push fails with host key error"** | The pinned Ed25519 key should prevent this. If GitHub rotates keys again, update `/srv/first-agent/secrets/known_hosts`. |

---

## Troubleshooting

**"Docker bypasses UFW"**
- This is by design. Docker directly manages `iptables`. Mitigation: do not publish ports publicly. The compose file binds nothing to `0.0.0.0`. All access is via Tailscale.

**"Tracker / evolution packages got removed and GNOME is broken"**
- The setup script **masks** these services (disables them at systemd level) rather than removing the packages. If you accidentally purged them, reinstall: `sudo apt install ubuntu-desktop`.

**"Screen locks despite gsettings"**
- The cross-reference found that `gsettings` alone is sometimes ignored. The setup script adds a `logind.conf.d` drop-in as a second lock. Reboot after running the script.

**"Tailscale SSH doesn't work"**
- Ensure you ran `sudo tailscale up --ssh` (not just `tailscale up`).
- Check `tailscale status` shows the AIO.
- Ensure UFW allows `tailscale0` to port 22.

**"Deploy key push is denied"**
- Verify the key has **write access** in GitHub repo settings.
- Verify branch protection on `main` isn't blocking the push — agent should push to `agent/*` branches.
- Check `GIT_SSH_COMMAND` is set correctly inside the container.

**"restic backup hangs"**
- The cross-reference flagged that restic's **native** B2 backend can hang. The backup script uses the **S3-compatible** endpoint (`s3:https://s3.us-west-004.backblazeb2.com/...`). Ensure your B2 Application Key has the S3 capabilities enabled.

**"FA doesn't auto-start after reboot"**
- Check that lingering is enabled: `loginctl show-user $USER | grep Linger` should say `yes`.
- Check the service status: `systemctl --user status fa.service`.
- Check that the service is enabled: `systemctl --user is-enabled fa.service`.

**"Container stopped but auto-reboot brought it back"**
- This is expected: `restart: unless-stopped` in the compose file means Docker will restart the container unless explicitly stopped via `docker compose down`.
- To stop FA and keep it stopped: `systemctl --user stop fa.service` (stops the systemd service, which runs `docker compose down`).

---

## References

- [`scripts/setup-fa-desktop.sh`](../scripts/setup-fa-desktop.sh) — automated host hardening
- [`docker-compose.fa.yml`](../docker-compose.fa.yml) — hardened FA container definition
- [`Dockerfile.fa`](../Dockerfile.fa) — FA runtime image
- [`scripts/fa.service`](../scripts/fa.service) — systemd user service
- [`.dockerignore`](../.dockerignore) — build context exclusions
- [`scripts/backup-fa.sh`](../scripts/backup-fa.sh) — restic backup script
- [`knowledge/research/First-Agent-ops-cross-reference.md`](./research/First-Agent-ops-cross-reference.md) — three-source cross-reference
- [`knowledge/research/homelab-deployment-24-7-2026-06.md`](./research/homelab-deployment-24-7-2026-06.md) — research note with citations
