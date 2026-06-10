# SSH-over-Tailscale hardening (AIO)

Operational runbook for the dedicated Ubuntu 24.04 AIO host that runs First-Agent.
It hardens **remote admin SSH access to the host** so it is reachable only over
Tailscale, with defense-in-depth so that no single layer is a single point of
failure. This implements the team's SSOT runbook as idempotent, re-runnable
scripts.

This is **host-level** work. The FA workload itself runs in a container
(`docker-compose.fa.yml`) that has **no sshd** — these scripts do not touch it.
Canonical deployment guide: [`knowledge/SETUP_AIO.md`](../../knowledge/SETUP_AIO.md).

> **Everyday access vs. hardening.** If you just want to reach the agent securely
> from your devices, you only need the next section
> ([Access your agent from any device](#access-your-agent-from-any-device-everyday-path))
> plus the `tailscale-acl.jsonc` policy. The `00`/`20`/`30` hardening scripts are
> **optional** defense-in-depth for the *classic-sshd* recovery path; they do not
> affect your everyday Tailscale-SSH login.

## Access your agent from any device (everyday path)

For a single operator who wants to reach the agent from many devices, the
production-standard, **key-free** path is **Tailscale SSH**: you authenticate with
your **Tailscale identity** (SSO), not an SSH key. The agent's CLI runs in a
container with no sshd, so "connecting to the agent" means getting a shell on the
**host** and running the `fa` CLI (or `docker exec` into the container).

### Onboard a new device (≈2 min, nothing to copy)

1. Install Tailscale on the device and sign in with the **same** account:
   <https://tailscale.com/download>.
2. Confirm it sees the host: `tailscale status` (look for `fa-hp` / its `100.x` IP).
3. Connect: `ssh fa@fa-hp` (MagicDNS) or `ssh fa@100.76.34.40`. A browser re-auth
   may appear ("check" mode — once per `checkPeriod`, set to 24h in the ACL); then
   you get a shell.

No `authorized_keys`, no key distribution — access is granted by the `ssh` rules
in [`tailscale-acl.jsonc`](./tailscale-acl.jsonc).

### Offboard a device (instant)

Admin console → **Machines** → the device → **Remove** (delete) or **Disable**
(pause). Its tailnet access, including SSH, is revoked immediately.

### Tag the host as `tag:aio` (do this once)

Tagging the server (a) **disables node-key expiry** so a headless 24/7 box is
never silently logged out (~every 6 months), and (b) lets ACL rules name a stable
identity. Tagging changes *which* rule matches your sessions, so follow this order
exactly to avoid locking yourself out:

```bash
# 1) In the admin console, save tailscale-acl.jsonc FIRST. It adds the tag:aio
#    ssh rule AND keeps the default "autogroup:self" rule as a safety net.
# 2) On the host, advertise the tag (re-auth in the browser when prompted):
sudo tailscale up --ssh --advertise-tags=tag:aio
# 3) From a SECOND device, confirm `ssh fa@fa-hp` still works BEFORE closing your
#    current session. Keep the physical console handy as a fallback.
```

### Break-glass: an emergency SSH key for `fa`

Tailscale SSH is your everyday path and the **physical console** is the primary
break-glass. An emergency SSH key is a useful extra (and a good way to learn keys).
Honest caveat: while `tailscale up --ssh` is on, `tailscaled` owns port 22 on the
tailnet IP, so this key only helps **after** you disable Tailscale SSH
(`sudo tailscale up --ssh=false`) from the console, or over the LAN — it is *not* a
second remote path on its own.

Generate the keypair **on your laptop** (never on the server — the private half
must stay with you):

```bash
# On your laptop:
ssh-keygen -t ed25519 -C "fa-breakglass" -f ~/.ssh/fa_breakglass
#   -> ~/.ssh/fa_breakglass      PRIVATE — never share, never commit
#      ~/.ssh/fa_breakglass.pub  PUBLIC  — safe to copy to the server
# Set a passphrase when asked (protects the key if the laptop is lost).
```

Install the **public** key on the host through your working Tailscale SSH session:

```bash
# From your laptop, append the public key to fa's authorized_keys on the host:
ssh fa@fa-hp 'install -d -m700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys' < ~/.ssh/fa_breakglass.pub
```

Use a **separate** keypair per device (repeat `ssh-keygen` and append each `.pub`)
rather than copying one private key around; revoke a device by deleting its line
from `~/.ssh/authorized_keys`.

## Defense-in-depth layers

```text
Attacker (LAN/WAN)
  -> [Tailscale ACL]      unauthorised tailnet node: WireGuard won't authorise dst:22
  -> [UFW deny-in]        packet not from tailscale0: DROP            (Step 1)
  -> [sshd Match Address] source not in 100.64/10 etc.: deny pre-auth (Step 2)
  -> [pubkey + AllowUsers] no key for the operator: deny
  -> [fail2ban systemd]   repeated tries from inside the tailnet: ban (Step 3)
```

No layer is pinned to a dynamic IP, and sshd starts independently of `tailscaled`
(it binds `0.0.0.0` and filters by **source**), so SSH stays a low-dependency
recovery path. Everything survives reboot / tailscale restart / network change.

## Scripts

| File | What it does |
|------|--------------|
| `00-failsafe.sh` | **Step 0 dead-man switch.** Schedules an automatic `ufw disable` after N minutes (default 15) so a mistake can't lock you out. `arm` / `disarm` / `status`. |
| `10-diagnose.sh` | **Read-only audit.** Run first. Reports which server answers `:22` (system sshd vs Tailscale SSH), UFW/IPv6, effective `sshd -T` policy, authorized_keys, fail2ban, netfilter backend, Docker port-publish bypass. |
| `20-harden.sh`   | **Apply Steps 1,2,3,5,6** idempotently. Refuses to run unless the failsafe is armed and `SSH_USER` exists; validates with `sshd -t` and asserts effective `allowusers` for a LAN vs tailnet source **before** `reload` (never `restart`). |
| `30-verify.sh`   | **Final checklist.** Non-zero exit on failure; prints the manual LAN negative-test + reboot-test steps. |
| `tailscale-acl.jsonc` | **Step 4 ACL** for the Tailscale admin console. Not applied by any script — paste it as the whole policy. Ships ready for the `fa` account + `tag:aio` (no placeholders to fill). |

## Order of operations (run on the AIO)

```bash
cd /srv/first-agent/repo/First-Agent-dev/scripts/ssh-tailscale

# 0. Audit current state.
sudo bash 10-diagnose.sh

# 1. SAFETY: arm the dead-man rollback AND open a SECOND ssh session, keep it open.
sudo bash 00-failsafe.sh arm

# 2. Harden (override the operator account if it isn't fa).
sudo SSH_USER=fa bash 20-harden.sh

# 3. From a FRESH connection over Tailscale, confirm you can still log in,
#    then verify.
sudo bash 30-verify.sh

# 4. Apply the Tailscale ACL in the admin console (see tailscale-acl.jsonc).

# 5. ONLY after a fresh login is confirmed: cancel the rollback.
sudo bash 00-failsafe.sh disarm
```

All scripts re-exec themselves under `sudo` if not already root, and are safe to
re-run.

## Which SSH path are you on? (read this)

The AIO setup runs `sudo tailscale up --ssh`, which enables **Tailscale SSH**:
connections to the AIO's Tailscale IP `:22` are served by `tailscaled`, **not**
system `sshd`. Consequences:

- **Tailscale SSH sessions** are governed by the `ssh` rules in
  `tailscale-acl.jsonc` (tailnet identity + optional SSO re-check). `sshd`'s
  `Match Address` and `fail2ban` do **not** see these sessions.
- The **`sshd` Match-Address / UFF / fail2ban** layers still matter: they cover
  classic `sshd` connections (e.g. from the LAN, or if Tailscale SSH is ever
  turned off) and keep `sshd` as a hardened recovery path.

`10-diagnose.sh` tells you which server is answering `:22`. If "ssh через
Tailscale" is broken, the most common causes are: Tailscale SSH not enabled /
ACL `ssh` rule missing, the host not authenticated to the tailnet
(`tailscale status`), or no authorized key for the operator. Fix those before
assuming a firewall problem.

## If you get locked out (recovery)

The hardening keeps **two independent ways back in** so a single mistake is
recoverable:

- **Tailscale SSH** (`tailscale up --ssh`) is served by `tailscaled`, so it
  bypasses system `sshd`, UFW, *and* fail2ban. A fail2ban ban or an `sshd`
  misconfig does **not** block it — use the Tailscale app/CLI to get a shell.
- **Dead-man failsafe** (`00-failsafe.sh arm`) auto-runs `ufw disable` after the
  timeout, undoing a bad firewall change.
- **Physical console** at the AIO is always the last resort.

Common self-lockout and its fix:

```bash
# fail2ban banned your own tailnet IP (key-only auth + a looping client)?
sudo fail2ban-client status sshd          # see banned IPs
sudo fail2ban-client set sshd unbanip <IP>
# Prevent recurrence: pin your STABLE admin tailnet IP into ignoreip.
sudo IGNORE_IP="100.x.y.z" bash 20-harden.sh
```

`IGNORE_IP` is whitespace-separated and additive to loopback. Use a **stable**
tailnet IP (the AIO peer's address for your laptop), not an ephemeral one.

## Notes / edge cases

- **IPv6 (Edge case 1).** `sshd` listens on `[::]:22`; if UFW `IPV6=no` it does
  not filter v6 at all. `20-harden.sh` sets `IPV6=yes`.
- **Docker (Edge case 2).** Docker writes its own `DOCKER` nftables chain and
  bypasses UFW for **published** ports. The FA compose file publishes none, so
  SSH is unaffected; `10-diagnose.sh` flags any container that does publish to
  `0.0.0.0`.
- **`AllowUsers` reconciliation.** `99-fa-hardening.conf` ships a global
  `AllowUsers`; because sshd takes the *first* `AllowUsers` it would override
  the source-scoped rule. `20-harden.sh` comments it out (with a timestamped
  backup) so `99-tailscale-only.conf` is the single owner, then proves the
  result with `sshd -T -C`. If *another* drop-in (or the main `sshd_config`)
  also sets `AllowUsers`, the `sshd -T -C` self-test fails closed and the
  reload is aborted — fix it with `grep -rn AllowUsers /etc/ssh/`.
- **`authorized_keys` check is best-effort.** The pre-flight key check reads the
  default `~/.ssh/authorized_keys`; if you use a custom `AuthorizedKeysFile`
  (e.g. `/etc/ssh/authorized_keys/%u`) it may warn even though keys exist.
  Confirm with `sudo sshd -T | grep -i authorizedkeysfile`.
- **fail2ban self-lockout.** Key-only auth + `maxretry=3` means a looping or
  misconfigured client can ban *your own* tailnet IP. Set `IGNORE_IP` to your
  stable admin tailnet IP (see "If you get locked out" above).
- **Config backups accumulate.** Each `20-harden.sh` run drops a
  `*.bak-<timestamp>` next to the edited file. These do **not** end in `.conf`,
  so sshd never loads them; prune them manually if they pile up.
- **No manual iptables drop-in.** UFW (nftables frontend) + sshd Match + the
  Tailscale ACL already provide independent layers; a hand-written netfilter
  rule would be a second source of truth and conflict with Tailscale's
  `ts-input` chain. `20-harden.sh` only *checks* the backend (`iptables-nft`).
- **No `sshd After=tailscaled` ordering.** `sshd` must not depend on
  `tailscaled` (it binds `0.0.0.0`); a hard dependency would turn a tailscaled
  failure into total SSH lockout.
