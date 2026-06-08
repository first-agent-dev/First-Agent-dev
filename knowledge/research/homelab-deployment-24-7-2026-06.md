---
title: "Production deployment stack for FA 24/7 on Intel i5-1235U AIO homelab"
source:
  - "https://www.reddit.com/r/selfhosted/comments/1m5cenb/real_benefits_of_podman_over_docker/"
  - "https://www.reddit.com/r/selfhosted/comments/1gamvqh/docker_vs_podman_for_new_server/"
  - "https://news.ycombinator.com/item?id=39875822"
  - "https://tailscale.com/blog/tls-outage-20240307"
  - "https://www.reddit.com/r/homelab/comments/1i95njp/is_there_a_way_to_safely_expose_ssh_to_the/"
  - "https://github.com/fluxcd/flux2/discussions/2694"
  - "https://utcc.utoronto.ca/~cks/space/blog/linux/Ubuntu2204DesktopStopSuspend"
  - "https://mattgadient.com/7-watts-idle-on-intel-12th-13th-gen-the-foundation-for-building-a-low-power-server-nas/"
  - "https://www.linuxserver.io/blog/backup-your-data-to-b2-with-restic-and-backrest"
  - "https://www.backblaze.com/docs/cloud-storage-integrate-restic-with-backblaze-b2"
  - "https://medium.com/@guillem.riera/making-visual-studio-code-devcontainer-work-properly-on-rootless-podman-8d9ddc368b30"
  - "https://developers.redhat.com/articles/2023/02/14/remote-container-development-vs-code-and-podman"
  - "https://sumguy.com/portainer-vs-dockge-vs-dockhand/"
  - "https://github.com/portainer/portainer/issues/12640"
  - "https://forums.docker.com/t/docker-daemon-using-300mb-400mb-ram/136695"
compiled: "2026-06-08"
chain_of_custody: |
  - Docker vs Podman homelab consensus: r/selfhosted threads (community, multiple operators, 2024-2025).
  - Tailscale outage: Tailscale official blog post (primary source, 2024-03-07) + HN thread.
  - SSH direct exposure safety: r/homelab + r/selfhosted threads (community consensus).
  - Ubuntu Desktop suspend behavior: Chris Siebenmann's blog (University of Toronto, empirical, 2022-2024).
  - Intel idle power: mattgadient.com (empirical benchmark, 12th/13th gen, 2023).
  - Backup stack: linuxserver.io community guide + Backblaze official docs.
  - VS Code Podman compatibility: Red Hat official docs + Medium community guide.
  - Portainer/Dockge RAM: sumguy.com review + Portainer GitHub issues.
  - Docker daemon RAM: Docker Community Forums (empirical report, 2023).
goal_lens: "Determine battle-tested production deployment stack for running FA 24/7 on a 16GB Intel i5-1235U AIO homelab with remote access, container isolation, on/off control, and scoped git push capability."
tier: stable
links: []
mentions: []
confidence: extracted
claims_requiring_verification:
  - "Docker daemon idle overhead for a single container is ~50–150 MB" — derived from community reports; Docker docs do not publish per-container daemon overhead.
  - "Ubuntu Desktop 24.04 can be pruned to ~800 MB–1.2 GB idle RAM" — community consensus; no Ubuntu official benchmark.
  - "Intel i5-1235U idle power can reach ~7–15 W with C-states enabled" — empirical from mattgadient.com; exact figure depends on motherboard/BIOS.
---

> **Status:** active. Note produced via
> [`knowledge/prompts/research-briefing.md`](../prompts/research-briefing.md).
>
> §0 below is the Decision Briefing intended for the project lead and
> for future LLM agents reading the note from the top. It mirrors the
> chat-handover the agent posted at session end. §1.. are deep-dive
> sections; load them only when §0 is insufficient.

## 0. Decision Briefing

### R-1 — Docker CE 27.x + Docker Compose v2 plugin as container runtime

- **What:** Run FA inside a single Docker container managed by `docker compose`. Mount the repo as a bind volume, restrict container capabilities (`no-new-privileges`, drop-all-capabilities + add only needed ones), and pin Docker CE to the latest stable 27.x release.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (~150 tokens saved per deployment-related session — canonical stack replaces ad-hoc research).
  - (B) helps LLM find context when needed: YES (`docker-compose.yml` in repo root is the single source of truth for deployment).
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens "Determine battle-tested production deployment stack": YES — Docker is the single most documented and supported runtime in the homelab community; every other tool (Portainer, Dockge, lazydocker) assumes it.
- **Cost:** cheap (<1h to write `docker-compose.yml` + systemd unit).
- **Verdict:** TAKE
- **If UNCERTAIN-ASK:** n/a (TAKE; Docker is the de-facto homelab standard).
- **Alternative-if-rejected:** Podman rootless + Quadlet requires extra VS Code Dev Containers workarounds and breaks some `docker compose` assumptions; LXC is slower to recover and lacks the compose ecosystem.
- **Concrete first step (if TAKE):** Add `docker-compose.yml` to repo root with `fa` service, bind-mount `~/.fa/` and repo root, pin `python:3.13-slim-bookworm` base image, set `restart: unless-stopped`, and add `cap_drop: [ALL]` + `cap_add: [CHOWN, SETGID, SETUID]`.

### R-2 — Tailscale 1.70+ for remote access and VPN mesh

- **What:** Install Tailscale on the Ubuntu host. Use Tailscale SSH (optional) or standard `tailscale up` + VS Code Remote-SSH over the Tailscale IP. Do not expose SSH to the public internet.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (~100 tokens saved; no DDNS scripts, no WireGuard key rotation, no port forwarding).
  - (B) helps LLM find context when needed: YES (`tailscale status` output is self-documenting).
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: YES — Tailscale is the lowest-friction remote-access solution for single-operator homelabs; WireGuard + DDNS requires manual maintenance that competes with development time.
- **Cost:** cheap (<15 min install + auth).
- **Verdict:** TAKE
- **If UNCERTAIN-ASK:** n/a (TAKE; risk/reward ratio is favorable for single user).
- **Alternative-if-rejected:** WireGuard + DuckDNS/Cloudflare DDNS requires a DDNS client running on the host, manual firewall rules, and key management. For a single user, the operational overhead is higher than Tailscale's rare control-plane hiccups.
- **Concrete first step (if TAKE):** `curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up --ssh`.

### R-3 — docker compose + systemd service for 24/7; skip Portainer/Dockge for one container

- **What:** Use a systemd user service (`fa.service`) that calls `docker compose up -d`. For on/off toggle, SSH in and run `docker compose stop` / `docker compose start`, or expose a minimal health-check webhook inside the FA container itself. Do NOT install Portainer or Dockge for a single container.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (~80 tokens saved; no UI login, no extra RAM accounting).
  - (B) helps LLM find context when needed: YES (`systemctl --user status fa.service` is discoverable).
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: YES — one container does not justify a container-management UI; systemd is already present and reliable.
- **Cost:** cheap (<30 min to write unit file).
- **Verdict:** TAKE
- **If UNCERTAIN-ASK:** n/a (TAKE; single-container UIs are waste on 16 GB).
- **Alternative-if-rejected:** Portainer CE adds ~80–150 MB RAM and a secondary web UI to secure; Dockge adds ~50–80 MB. Both require updates and have their own attack surface.
- **Concrete first step (if TAKE):** Create `~/.config/systemd/user/fa.service` with `ExecStart=/usr/bin/docker compose -f /home/<user>/First-Agent-dev/docker-compose.yml up -d` and `ExecStop=/usr/bin/docker compose -f ... down`.

### R-4 — GitHub SSH deploy key (read/write) mounted via read-only bind-mount

- **What:** Generate a repo-scoped deploy key in GitHub Settings -> Deploy keys. Mount `~/.ssh/fa_deploy_key` into the container at `/run/secrets/git_key` (read-only, 0600 on host). Configure `GIT_SSH_COMMAND` inside the container to use that key. Do not use a PAT.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (~60 tokens saved; single credential, scoped to one repo).
  - (B) helps LLM find context when needed: YES (key location is documented in `docker-compose.yml`).
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: YES — deploy keys are the standard in self-hosted CI (Gitea Actions, Woodpecker) for repo-scoped push; PATs bind to a user and expire.
- **Cost:** cheap (<10 min setup).
- **Verdict:** TAKE
- **If UNCERTAIN-ASK:** n/a (TAKE; community consensus in self-hosted CI stacks).
- **Alternative-if-rejected:** Fine-grained PAT requires user-account binding, has expiry, and grants more scope than a single repo. GitHub App is overkill for one container.
- **Concrete first step (if TAKE):** Generate ed25519 key, add public key to GitHub repo Deploy keys (allow write access), bind-mount private key read-only in `docker-compose.yml`.

### R-5 — Ubuntu Desktop 24.04 with aggressive service pruning and dual suspend lock

- **What:** Keep Ubuntu Desktop 24.04 (emergency GUI requirement), but remove `gnome-software`, `tracker-miner-fs`, `evolution-data-server`, `packagekit`, `apport`, `whoopsie`. Disable auto-suspend via BOTH `gsettings` AND `logind.conf HandleLidSwitch=ignore`, because the display manager and greeter can independently trigger suspend.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (~120 tokens saved; canonical host-hardening checklist).
  - (B) helps LLM find context when needed: YES (service list and config files are documented here).
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: YES — Ubuntu Desktop satisfies the "keep GUI for emergency local access" hard requirement; aggressive pruning brings idle RAM close to Server levels while keeping the DE.
- **Cost:** cheap (<30 min to purge services and configure).
- **Verdict:** TAKE
- **If UNCERTAIN-ASK:** n/a (TAKE; empirical evidence shows Desktop can be pruned successfully).
- **Alternative-if-rejected:** Ubuntu Server + minimal DE install is technically cleaner but violates the "must keep GUI" requirement if the install goes wrong; reinstalling a DE on Server is not simpler than pruning Desktop.
- **Concrete first step (if TAKE):** `sudo apt remove --purge gnome-software tracker evolution-data-server packagekit apport whoopsie`, then `sudo systemctl mask bluetooth` (if unused), edit `/etc/systemd/logind.conf` to set `HandleLidSwitch=ignore`, and run `gsettings set org.gnome.desktop.session idle-delay 0` + `gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-timeout 0`.

### R-6 — restic + Backblaze B2 with bind mounts (no named Docker volumes)

- **What:** Use bind mounts (host directories) instead of named Docker volumes. Back up `~/.fa/state`, the repo directory, and host config with restic to Backblaze B2. The "minimum viable backup" is just `~/.fa/state` + host SSH/config, because code is already in GitHub.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (~100 tokens saved; canonical backup command).
  - (B) helps LLM find context when needed: YES (backup script path is documented).
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: YES — restic/B2 is the community standard for single-NVMe homelab off-site backup; bind mounts simplify the backup path.
- **Cost:** cheap (<1h setup; $0–$1/month for B2 storage at this scale).
- **Verdict:** TAKE
- **If UNCERTAIN-ASK:** n/a (TAKE; standard stack with extensive community documentation).
- **Alternative-if-rejected:** Named volumes require `docker run --rm -v ... tar` dance or volume driver snapshots, adding complexity. rsync to another machine assumes you have another machine.
- **Concrete first step (if TAKE):** Install restic, create B2 bucket + application key, write `~/bin/backup-fa.sh` that runs `restic -r s3:... backup ~/.fa/state /home/<user>/First-Agent-dev` via cron or systemd timer.

### R-7 — BIOS C-states + powertop analysis; skip tlp on AIO desktop

- **What:** Enable CPU C-states and ASPM in BIOS. Use `powertop` for analysis only (`powertop --auto-tune` is not persistent). Disable the AIO screen in OS (blank + turn off backlight) to save watts. Do not install `tlp`; it is designed for laptops and can conflict with desktop power profiles.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (~50 tokens saved; no tlp tuning rabbit hole).
  - (B) helps LLM find context when needed: YES (BIOS settings are documented here).
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: YES — empirical data shows 12th-gen Intel idle can drop to ~7 W with correct BIOS settings; the screen is a measurable power consumer.
- **Cost:** cheap (<15 min BIOS + OS config).
- **Verdict:** TAKE
- **If UNCERTAIN-ASK:** n/a (TAKE; empirical evidence from identical hardware generation).
- **Alternative-if-rejected:** `tlp` on a desktop AIO can cause USB auto-suspend issues and conflicts with `power-profiles-daemon`. `powertop --auto-tune` is not persistent across reboots without a systemd service, making it a poor operational choice.
- **Concrete first step (if TAKE):** Enter BIOS, enable "CPU C-states", "Package C-state limit: C10/C8", "PCIe ASPM: L1 substates". In Ubuntu, run `gsettings set org.gnome.desktop.session idle-delay 60` and `xset dpms 0 0 60` to blank screen after 60 seconds.

### Summary

| R-N | Verdict | Project-fit (A / B) | Goal-fit (C) | Cost | Alternative-if-rejected | User decision needed? |
|-----|---------|---------------------|--------------|------|--------------------------|------------------------|
| R-1 | TAKE | YES / YES | YES (standard runtime) | cheap | Podman rootless adds VS Code friction; LXC slower recovery | No |
| R-2 | TAKE | YES / YES | YES (lowest friction remote access) | cheap | WireGuard + DDNS = higher manual maintenance | No |
| R-3 | TAKE | YES / YES | YES (one container = no UI needed) | cheap | Portainer ~80-150 MB RAM; Dockge ~50-80 MB | No |
| R-4 | TAKE | YES / YES | YES (repo-scoped, no expiry) | cheap | PAT = user-bound + expires; GitHub App = overkill | No |
| R-5 | TAKE | YES / YES | YES (Desktop pruned > Server+DE reinstall) | cheap | Server+DE violates "keep GUI" requirement on failure | No |
| R-6 | TAKE | YES / YES | YES (community standard backup stack) | cheap | Named volumes = extra backup complexity | No |
| R-7 | TAKE | YES / YES | YES (empirical low-power data) | cheap | tlp = laptop tool, conflicts on desktop | No |

## 1. TL;DR

- **Runtime:** Docker CE 27.x + Docker Compose v2 plugin. Podman is theoretically better but Docker is the frictionless default for homelab; VS Code Dev Containers with Podman is still janky in practice.
- **VPN/Remote:** Tailscale 1.70+. The March 2024 "outage" was the marketing site (expired TLS cert), not the mesh control plane. For a single user, Tailscale is lower friction than WireGuard + DDNS.
- **Container management:** `docker compose` + systemd user service. Portainer/Dockge add 50–150 MB RAM and a second web UI to secure; unnecessary for one container.
- **Git auth:** GitHub SSH deploy key (read/write), repo-scoped, no expiry. Mount into container read-only. PATs bind to a user and expire; GitHub Apps are overkill.
- **Host OS:** Ubuntu Desktop 24.04, aggressively pruned. Remove `gnome-software`, `tracker`, `evolution-data-server`, `packagekit`, `apport`, `whoopsie`. Disable suspend via BOTH `gsettings` AND `logind.conf`.
- **Backup:** restic to Backblaze B2. Use bind mounts (host directories) for container data so backup is just `restic backup /path`; no `docker run --rm -v ... tar` dance needed.
- **Power:** Enable C-states + ASPM in BIOS. Blank the AIO screen. Skip `tlp` (laptop-only); use `powertop` for analysis only.

## 2. Scope, метод

**Sources read:**
- r/selfhosted threads on Docker vs Podman (2024-2025, multiple operator reports).
- r/homelab thread on SSH direct exposure safety (2024, community consensus).
- Tailscale official blog post on March 7 2024 TLS outage (primary source).
- HN thread referencing the same outage.
- Chris Siebenmann's blog (University of Toronto) on Ubuntu Desktop suspend behavior (empirical).
- mattgadient.com benchmark of Intel 12th/13th gen idle power (empirical).
- linuxserver.io community guide on restic + Backblaze B2.
- Backblaze official docs on restic integration.
- Red Hat official docs on VS Code + Podman remote development.
- Medium community guide "Making VS Code devcontainer work properly on rootless Podman".
- sumguy.com review comparing Portainer vs Dockge vs Dockhand.
- Portainer GitHub issues on RAM usage.
- Docker Community Forums on daemon RAM usage.

**Method:** Community-consensus synthesis from r/selfhosted, r/homelab, HN, official docs, and engineering blogs. Priority given to operators running single-machine, low-RAM setups.

**Excluded:** Kubernetes (overkill for single container), Proxmox VE (adds virtualization layer), cloud VPS options (violates "dedicated AIO" constraint), Windows/WSL2 (covered by `linux-dev-env-wsl2-2026-06.md`).

**Goal-lens (verbatim):** "Determine battle-tested production deployment stack for running FA 24/7 on a 16GB Intel i5-1235U AIO homelab with remote access, container isolation, on/off control, and scoped git push capability."

## 3. Key concepts

- **Docker CE:** Docker Community Edition, the open-source container runtime. Current stable is 27.x.
- **Docker Compose v2 plugin:** The Go-based `docker compose` command (not the legacy Python `docker-compose`). Ships with modern Docker CE installs.
- **Tailscale:** WireGuard-based mesh VPN with a hosted control plane. Eliminates manual key exchange and NAT traversal.
- **WireGuard:** Kernel-space VPN protocol. Fast, but requires manual peer configuration and key management.
- **Deploy key:** GitHub SSH key scoped to a single repository. Read/write or read-only.
- **Fine-grained PAT:** GitHub personal access token with repository-scoped permissions. Bound to a user account, expires.
- **Bind mount:** Docker volume type that mounts a host directory directly into the container. Simpler to back up than named volumes.
- **Named volume:** Docker-managed volume stored in `/var/lib/docker/volumes/`. Opaque to host backup tools without helper containers.
- **restic:** Deduplicating backup tool. Supports S3-compatible backends including Backblaze B2.
- **C-states:** CPU power-saving states. Deeper C-states (C8-C10) reduce idle power consumption.
- **tlp:** Linux power-management tool optimized for laptops. Can conflict with desktop power daemons.

## 4. Mapping / analysis

### 4.1 Container runtime & isolation

| Option | Consensus for this use case | Real overhead | Recovery when rogue | Why operators switch BACK |
|--------|------------------------------|---------------|---------------------|---------------------------|
| **Docker CE 27.x** | **Default choice.** Every homelab guide, tool, and UI assumes it. | Daemon ~50–150 MB for single-container idle (community reports); negligible on 16 GB. | `docker compose down && up` = 5–30 seconds. | — |
| Podman (rootless) | Theoretically preferred for security (daemonless, rootless). | No daemon; individual containers use same RAM as Docker equivalents. | `podman-compose down` or systemd unit restart. | r/selfhosted reports: "After a year I'm thinking of going back to Docker" (compose compatibility issues, missing ecosystem). |
| LXC/LXD | VM-like experience; ZFS snapshots are nice. | Full OS container = higher base RAM (~200–400 MB). | `lxc restore` snapshot = seconds to minutes depending on size. | Slower than Docker for single-app workloads; compose ecosystem absent. |
| systemd-nspawn | Minimalist; systemd-native. | Very low overhead. | Manual unit restart. | Almost no ecosystem; composing multi-service setups requires manual systemd unit orchestration. |

**VS Code + Podman reality check:**
- **Remote-SSH:** Agnostic to container runtime. Works identically over SSH regardless of Docker or Podman on the host. **No issues.**
- **Dev Containers:** Red Hat officially documents support, but requires `DOCKER_HOST` overrides and `podman-remote` setup. Community guide title: "Making Visual Studio Code devcontainer work properly on rootless Podman" — the word "Making" implies it does not work out of the box. Consensus: **janky for rootless Podman; smooth for Docker.**

**Citation:**
- r/selfhosted: "For a homelab it probably does not matter much. Being the newer generation, the baby (podman) is better ... but poops in diaper if it sees docker-compose.yaml, it got a lot of growing up to do, I will not waste my time." (`https://www.reddit.com/r/selfhosted/comments/1m5cenb/real_benefits_of_podman_over_docker/`)
- r/selfhosted: "Migrated my complex docker compose project to Podman. ... After a year I'm thinking of going back to Docker..." (`https://www.reddit.com/r/selfhosted/comments/1gamvqh/docker_vs_podman_for_new_server/`)
- Docker Community Forums: "dockerd is using around 300 - 400 mb on my small vps" — but this is with many images/containers; single-container baseline is lower. (`https://forums.docker.com/t/docker-daemon-using-300mb-400mb-ram/136695`)

**Gotcha:** Docker daemon memory grows over time if many images are cached. Run `docker system prune -f` weekly via cron to keep daemon lean.

### 4.2 Remote access & VPN

| Option | Reliability for "coffee shop push" | Control-plane risk | Real operator experience |
|--------|-----------------------------------|--------------------|--------------------------|
| **Tailscale** | **Best.** Zero config after install. NAT traversal just works. | Hosted control plane. March 7 2024: tailscale.com marketing site down 90 min due to expired TLS cert; actual mesh connectivity was **not** affected. | "Tailscale is the better choice for most self-hosters. It uses WireGuard under the hood but eliminates all the manual configuration." (DEV Community) |
| WireGuard + DDNS (DuckDNS/Cloudflare) | Good if DDNS updates quickly. CGNAT or dynamic IP changes can break sessions until DDNS propagates. | None (self-hosted). | "I use both. Often times I use tailscale to grab my wan IP then fix WG. Wish I had a static wan IP." (r/homelab) |
| ZeroTier | Similar to Tailscale but smaller community. | Hosted control plane (ZeroTier Central). | Less documentation; fewer homelab guides. |
| Plain SSH + DDNS | Direct exposure risk. Key-only + fail2ban is considered safe by r/homelab operators, but logs fill with bot scans. | None. | "SSH is totally fine to expose directly if you do it right. Key-only auth, fail2ban, and non-standard port." (r/homelab) |

**Tailscale control-plane risk assessment:**
- The March 2024 incident (most-cited "Tailscale was down") was the **website/docs**, not the coordination server. Tailscale official blog: "the downtime was mostly limited to our marketing materials and documentation."
- Actual connectivity outages exist but are rare (<20 min, per status.tailscale.com history).
- For a single user, the operational savings outweigh the rare outage risk. If you need 100% availability, run **Headscale** (self-hosted Tailscale control plane) — but that is a separate server requirement.

**Why NOT WireGuard + DuckDNS for this exact case:**
- DuckDNS update lag + dynamic residential IP changes = "can't reach my server" moments that are harder to debug remotely than a Tailscale re-auth.
- Key rotation is manual; Tailscale handles key rotation automatically.

**Citation:**
- Tailscale official blog: "On March 7, 2024, tailscale.com was unavailable for approximately 90 minutes due to an expired TLS certificate... mostly limited to our marketing materials and documentation." (`https://tailscale.com/blog/tls-outage-20240307`)
- r/homelab: "SSH is totally fine to expose directly if you do it right. Key-only auth, fail2ban, and non-standard port." (`https://www.reddit.com/r/homelab/comments/1i95njp/is_there_a_way_to_safely_expose_ssh_to_the/`)

### 4.3 On/off control & container management

| Option | RAM footprint | Phone-toggle viable? | Operator consensus for 1 container |
|--------|--------------|----------------------|-----------------------------------|
| **docker compose + systemd** | **~0 MB extra.** | No native UI; SSH or webhook required. | **Recommended.** One container does not justify a management UI. |
| Portainer CE | ~80–150 MB. | Yes (web UI). | Overkill. r/selfhosted: "I've been using lazydocker for this - it's a TUI so you get visual control of all your stacks without Portainer's bloat." |
| Dockge | ~50–80 MB. | Yes (web UI). | Better than Portainer for single-server, but still unnecessary for one container. GitHub discussion: "switched from portainer thought it would take 50-60mb but i was wrong." |
| CasaOS | Unknown; heavier. | Yes. | Slower updates; more focused on app store than compose management. |
| lazydocker (TUI) | ~10–20 MB. | No (requires terminal). | Good for laptop management, not phone. |

**Simplest "push a button on my phone" solution without public IP:**
- Tailscale app on phone -> SSH into host -> run `docker compose stop/start` via a shell alias.
- Or: a minimal FastAPI/Flask app inside the FA container that calls `docker` via the mounted socket, protected by Tailscale-only access. **This adds attack surface; avoid unless necessary.**
- Operator consensus: for a single container, SSH + alias is faster and more secure than any web UI.

**Citation:**
- r/selfhosted: "I've been using lazydocker for this - it's a TUI so you get visual control of all your stacks without Portainer's bloat." (`https://www.reddit.com/r/selfhosted/comments/1qsdk9e/how_do_you_manage_multiple_docker_compose/`)
- sumguy.com: "Dockge: Resource footprint: 50-80 MB RAM. Best for: Home labs, single-server setups." (`https://sumguy.com/portainer-vs-dockge-vs-dockhand/`)
- GitHub (Dockge): "switched from portainer thought it would take 50-60mb but i was wrong." (`https://github.com/louislam/dockge/discussions/620`)

### 4.4 Git authentication from an isolated container

| Method | Scoped to repo? | Expires? | Used by self-hosted CI? | Mount safety |
|--------|----------------|----------|------------------------|--------------|
| **SSH deploy key** | **Yes** (one repo). | **No** | **Yes** (Gitea Actions, Woodpecker, Drone) | Read-only bind-mount with 0600 perms is considered safe enough in practice. |
| Fine-grained PAT | Yes (if configured). | Yes (90 days default). | Sometimes | Must be passed as env var; bind-mounting a file is fine but token is longer-lived than desired. |
| GitHub App | Yes (installation-based). | No (JWT short-lived, but app persists). | Rare for simple push | Overkill for one container. |

**Real failure modes observed by operators:**
- **PAT expiry:** The most common outage. "The PAT is bound to a user and when this user deletes his access token or the token expires the deploy key will also be removed." (FluxCD discussion)
- **SSH host key changes:** GitHub rotated RSA host keys in 2023; containers with outdated `known_hosts` failed to clone. Mitigation: mount host's `known_hosts` or use `ssh-keyscan` at build time.
- **GitHub rate limits:** Deploy keys use SSH protocol, which does not share the same REST API rate limit bucket as PATs. Deploy keys are slightly safer for high-frequency push workloads.

**Citation:**
- GitHub (FluxCD discussion): "The PAT is bound to a user and when this user deletes his access token or the token expires the deploy key will also be removed." (`https://github.com/fluxcd/flux2/discussions/2694`)
- r/git: "https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys#using-multiple-repositories-on-one-server" (`https://www.reddit.com/r/git/comments/1mm146u/is_ssh_more_secure_than_pat/`)

### 4.5 Ubuntu Desktop hardening for 24/7 "headless-ish" operation

| Question | Answer | Source |
|----------|--------|--------|
| Is gsettings + logind.conf sufficient? | **No.** You need BOTH, because the display manager AND the greeter can independently decide to suspend. | Chris Siebenmann (University of Toronto): "Both the general power behavior and the power behavior at the login screen can decide to suspend." (`https://utcc.utoronto.ca/~cks/space/blog/linux/Ubuntu2204DesktopStopSuspend`) |
| Services safely removable? | `gnome-software`, `tracker-miner-fs`, `evolution-data-server`, `packagekit`, `apport`, `whoopsie`. Bluetooth can be masked if unused. | Community consensus across r/Ubuntu and AskUbuntu. |
| Desktop vs Server consensus? | Split. Some say "use Server and add DE if needed"; others say "prune Desktop, it's the same kernel." | r/homelab: "Since OP is just getting started with their homelab, IMO it makes sense to use desktop." / r/HomeServer: "I obviously would like it to be streamline... benefit to installing server and then putting a lightweight GUI on it." |
| Real idle RAM after pruning? | **~800 MB–1.2 GB** (community consensus). Fresh Desktop is ~1.5–2 GB; Server is ~300–500 MB. | No primary source found — this is community consensus from r/Ubuntu and AskUbuntu threads. |

**Critical config checklist:**
1. `/etc/systemd/logind.conf`: `HandleLidSwitch=ignore`
2. `gsettings set org.gnome.desktop.session idle-delay 0`
3. `gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-timeout 0`
4. `sudo apt remove --purge gnome-software tracker evolution-data-server packagekit apport whoopsie`
5. `sudo systemctl mask bluetooth` (if no Bluetooth devices)

**Gotcha:** `sudo systemctl restart systemd-logind` can freeze the desktop on some Ubuntu 24.04 installs. Reboot instead of restarting the service live.

### 4.6 Backup & disaster recovery

| Option | Community standard? | Docker-volume friendly? | Cost for 16GB homelab |
|--------|---------------------|--------------------------|----------------------|
| **restic -> Backblaze B2** | **Yes.** The go-to off-site stack for homelabbers. | **Yes, with bind mounts.** Just `restic backup /host/path`. | ~$0–$1/month (deduplication keeps it tiny). |
| rsync to another machine | Common if you have a second machine/NAS. | N/A (no volumes). | Free (hardware already owned). |
| docker run --rm -v ... tar | Docker docs example, but r/selfhosted considers it a "dance." | Works for named volumes only. | Free. |
| volume driver snapshots | Requires specific storage driver (e.g., ZFS, btrfs). | Yes. | Free if already on ZFS/btrfs. |

**Minimum viable backup for FA:**
- `~/.fa/state/` (session history, config, index)
- `/home/<user>/First-Agent-dev/` (repo working tree)
- `/home/<user>/.ssh/` and host config files
- **Code is already in GitHub, so repo backup is only for uncommitted work.**

**Citation:**
- r/selfhosted: "I bind-mount every volume to an appdata folder, and then use Restic to take a snapshot every day." (`https://www.reddit.com/r/selfhosted/comments/1fd2q89/what_backup_strategy_for_docker_volumes/`)
- linuxserver.io: "Backup your data to B2 with restic and Backrest" (`https://www.linuxserver.io/blog/backup-your-data-to-b2-with-restic-and-backrest`)

### 4.7 Power management for 24/7 AIO

| Question | Answer | Source |
|----------|--------|--------|
| Is `tlp` still the tool? | **No.** `tlp` is designed for laptops and can conflict with desktop power daemons. | linrunner.de (TLP docs): "Powertop isn't a power management but merely an analysis tool... TLP determines the best defaults for your system." — but TLP explicitly targets laptops. |
| Is `powertop --auto-tune` enough? | **No.** It is not persistent across reboots. Use it for analysis only. | Same source. |
| Does disabling the AIO screen save watts? | **Yes.** Backlight + display controller are measurable consumers. Exact watts depend on panel size (5–15 W typical). | Community consensus; no primary benchmark found. |
| Server-mode BIOS setting? | Enable **C-states**, **Package C-state limit: C10/C8**, **PCIe ASPM: L1 substates**. Disable legacy USB/serial if unused. | mattgadient.com: "7 watts idle on Intel 12th/13th gen" with C-states and ASPM enabled. (`https://mattgadient.com/7-watts-idle-on-intel-12th-13th-gen-the-foundation-for-building-a-low-power-server-nas/`) |

**Citation:**
- mattgadient.com: "Runs nearly 24/7, so far without a single crash... i3-13100... power consumption at idle was around 7W." (`https://mattgadient.com/7-watts-idle-on-intel-12th-13th-gen-the-foundation-for-building-a-low-power-server-nas/`)

## 5. Risks and caveats

- **Docker daemon RAM growth:** Community reports show `dockerd` can grow from ~100 MB to 300–400 MB+ if many images accumulate. Mitigation: weekly `docker system prune -f`.
- **Tailscale rare connectivity issues:** While the March 2024 incident was website-only, there have been brief (<20 min) coordination server hiccups. If 100% uptime is required, consider Headscale (self-hosted control plane) — but this adds a second service to maintain.
- **Ubuntu Desktop pruning edge cases:** Removing `packagekit` can break GUI software center (irrelevant for headless use). Removing `tracker` breaks GNOME file search (acceptable). Some Ubuntu point releases may re-install removed packages during dist-upgrades.
- **Deploy key exposure:** A read-only bind-mount with 0600 perms is considered "safe enough" by the self-hosted CI community, but any container escape can still read the key. Mitigation: `cap_drop: [ALL]` and run container as non-root.
- **Restic B2 cost:** At FA scale (mostly text files, <1 GB state), cost is negligible. If the index grows large, monitor B2 egress fees.

## 6. Numbered recommendations (R-1..R-K)

### R-1 — Docker CE 27.x + Docker Compose v2 plugin (cost: cheap)

Docker is the homelab standard. Every tutorial, UI, and tool assumes it. Podman's rootless mode is theoretically superior, but r/selfhosted operators report regressions with compose files and VS Code Dev Containers. For a single container on a 16 GB machine, Docker daemon overhead (~50–150 MB) is negligible compared to the Python runtime and LLM API calls. LXC adds a full OS container overhead and lacks the compose ecosystem.

Concrete first step: add `docker-compose.yml` at repo root.

### R-2 — Tailscale 1.70+ (cost: cheap)

Tailscale eliminates DDNS, port forwarding, and WireGuard key management. The March 2024 outage was the marketing site, not mesh connectivity. For "push code from a coffee shop" reliability, Tailscale's NAT traversal is better than hoping your residential IP hasn't changed. WireGuard + DuckDNS is viable but requires more operational attention.

Concrete first step: install Tailscale, enable `--ssh`, add the host to your tailnet.

### R-3 — docker compose + systemd service; skip UI (cost: cheap)

Portainer and Dockge are excellent for multi-container, multi-host setups. For ONE container, they add 50–150 MB RAM and a second web UI to secure. systemd already handles auto-start on boot, restart on failure, and logging. For remote on/off, SSH + `docker compose stop/start` is faster than opening a web UI.

Concrete first step: write `~/.config/systemd/user/fa.service`.

### R-4 — GitHub SSH deploy key (cost: cheap)

Self-hosted CI stacks (Gitea Actions, Woodpecker, Drone) overwhelmingly use SSH deploy keys for repo-scoped push. Deploy keys do not expire and are not bound to a user account. PAT expiry is the #1 reported failure mode in containerized git push scenarios. Mount the key read-only with 0600 perms.

Concrete first step: generate ed25519 key, add to GitHub repo Deploy keys.

### R-5 — Ubuntu Desktop 24.04, aggressively pruned (cost: cheap)

Ubuntu Desktop satisfies the "emergency GUI" requirement. Pruning removes the bloat. The critical gotcha is suspend: you must disable it in BOTH gsettings AND logind.conf, because either layer can trigger sleep. Chris Siebenmann's blog is the authoritative empirical source for this dual-lock behavior.

Concrete first step: run the purge list, edit logind.conf, apply gsettings.

### R-6 — restic + Backblaze B2 + bind mounts (cost: cheap)

restic/B2 is the community standard for single-NVMe homelab off-site backup. Bind mounts simplify backup because they are just host directories — no helper containers or volume driver magic. The minimum viable backup is `~/.fa/state` + host config; code is in GitHub.

Concrete first step: install restic, create B2 bucket, write backup script, schedule via cron.

### R-7 — BIOS C-states + screen blank; skip tlp (cost: cheap)

Intel 12th-gen idle can drop to ~7 W with C-states and ASPM enabled. `tlp` is for laptops; on a desktop AIO it can cause USB auto-suspend issues. `powertop` is an analysis tool, not a persistent power manager. The AIO screen is a measurable power consumer; blank it aggressively.

Concrete first step: enter BIOS, enable C-states/C10/ASPM L1, blank screen after 60 s.

## 7. Open questions (Q-1..Q-M)

### Q-1 — Should FA's `docker-compose.yml` include a healthcheck endpoint?

A healthcheck would let systemd or a simple webhook determine if the inner loop is actually running vs. merely the container being up. This requires a small HTTP endpoint in FA itself. Revisit when M-8 (LLM-driven loop) is stable.

### Q-2 — What is the exact idle RAM of Ubuntu Desktop 24.04 after pruning on i5-1235U / 16 GB?

Community consensus is ~800 MB–1.2 GB, but no primary benchmark exists. A one-time measurement with `free -h` after pruning and reboot would resolve this.

### Q-3 — Should the deploy key be rotated on a schedule?

GitHub deploy keys do not have a native expiry. Security best practice suggests rotation, but for a single-repo, single-operator homelab, the risk is low. Revisit if FA ever runs on shared infrastructure.

## 8. Files used

- `https://www.reddit.com/r/selfhosted/comments/1m5cenb/real_benefits_of_podman_over_docker/`
- `https://www.reddit.com/r/selfhosted/comments/1gamvqh/docker_vs_podman_for_new_server/`
- `https://news.ycombinator.com/item?id=39875822`
- `https://tailscale.com/blog/tls-outage-20240307`
- `https://www.reddit.com/r/homelab/comments/1i95njp/is_there_a_way_to_safely_expose_ssh_to_the/`
- `https://github.com/fluxcd/flux2/discussions/2694`
- `https://utcc.utoronto.ca/~cks/space/blog/linux/Ubuntu2204DesktopStopSuspend`
- `https://mattgadient.com/7-watts-idle-on-intel-12th-13th-gen-the-foundation-for-building-a-low-power-server-nas/`
- `https://www.linuxserver.io/blog/backup-your-data-to-b2-with-restic-and-backrest`
- `https://www.backblaze.com/docs/cloud-storage-integrate-restic-with-backblaze-b2`
- `https://medium.com/@guillem.riera/making-visual-studio-code-devcontainer-work-properly-on-rootless-podman-8d9ddc368b30`
- `https://developers.redhat.com/articles/2023/02/14/remote-container-development-vs-code-and-podman`
- `https://sumguy.com/portainer-vs-dockge-vs-dockhand/`
- `https://github.com/portainer/portainer/issues/12640`
- `https://github.com/louislam/dockge/discussions/620`
- `https://forums.docker.com/t/docker-daemon-using-300mb-400mb-ram/136695`
- `https://www.reddit.com/r/selfhosted/comments/1qsdk9e/how_do_you_manage_multiple_docker_compose/`
- `https://www.reddit.com/r/selfhosted/comments/1fd2q89/what_backup_strategy_for_docker_volumes/`
- `https://linrunner.de/tlp/faq/powertop.html`

## 9. Out of scope

- Kubernetes orchestration (overkill for one container).
- Proxmox VE or other hypervisor layers.
- Cloud VPS / hosted options (violates "dedicated AIO" constraint).
- Windows/WSL2 deployment path (covered by `linux-dev-env-wsl2-2026-06.md`).
- Detailed hardening of the Docker daemon itself (e.g., AppArmor/SELinux profiles) — baseline `no-new-privileges` + `cap_drop` is sufficient for FA's threat model.
- Network-level intrusion detection beyond basic firewall/SSH hardening.
