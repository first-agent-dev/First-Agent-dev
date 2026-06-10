# SSH-over-Tailscale hardening (AIO)

Operational runbook for the dedicated Ubuntu 24.04 AIO host that runs First-Agent.
It hardens **remote admin SSH access to the host** so it is reachable only over
Tailscale, with defense-in-depth so that no single layer is a single point of
failure. This implements the team's SSOT runbook as idempotent, re-runnable
scripts.

This is **host-level** work. The FA workload itself runs in a container
(`docker-compose.fa.yml`) that has **no sshd** — these scripts do not touch it.
Canonical deployment guide: [`knowledge/SETUP_AIO.md`](../../knowledge/SETUP_AIO.md).

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
| `tailscale-acl.jsonc` | **Step 4 ACL** for the Tailscale admin console (control-plane deny). Not applied by any script — paste/merge it, replacing the `<...>` placeholders. |

## Order of operations (run on the AIO)

```bash
cd /srv/first-agent/repo/First-Agent-dev/scripts/ssh-tailscale

# 0. Audit current state.
sudo bash 10-diagnose.sh

# 1. SAFETY: arm the dead-man rollback AND open a SECOND ssh session, keep it open.
sudo bash 00-failsafe.sh arm

# 2. Harden (override the operator account if it isn't fa-operator).
sudo SSH_USER=fa-operator bash 20-harden.sh

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
