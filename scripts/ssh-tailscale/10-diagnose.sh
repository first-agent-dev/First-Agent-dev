#!/usr/bin/env bash
# 10-diagnose.sh — Read-only audit of SSH-over-Tailscale remote access on the AIO.
#
# Makes NO changes. Run this FIRST to understand what is actually broken before
# applying 20-harden.sh. Surfaces which server answers :22 (system sshd vs
# Tailscale SSH), firewall state, effective sshd policy, fail2ban, and the
# common lock-out / Docker-bypass foot-guns.
#
# Usage:  sudo bash 10-diagnose.sh
#   SSH_USER may be set to override the audited account (default: fa-operator).
set -uo pipefail   # NOT -e: diagnostics must keep going past individual failures

SSH_USER="${SSH_USER:-${FA_USER:-fa-operator}}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()    { echo -e "  ${GREEN}[ OK ]${NC} $*"; }
warn()  { echo -e "  ${YELLOW}[WARN]${NC} $*"; }
bad()   { echo -e "  ${RED}[FAIL]${NC} $*"; }
info()  { echo -e "  ${BLUE}[info]${NC} $*"; }
head2() { echo -e "\n${BLUE}== $* ==${NC}"; }

if [[ "${EUID}" -ne 0 ]]; then
    exec sudo -E bash "$0" "$@"
fi

SSHD_BIN="$(command -v sshd || echo /usr/sbin/sshd)"

echo "SSH-over-Tailscale diagnostics — audited user: ${SSH_USER}"
echo "Host: $(hostname)   OS: $(. /etc/os-release && echo "${PRETTY_NAME}")"

# ---------------------------------------------------------------------------
head2 "1. Tailscale"
if command -v tailscale >/dev/null 2>&1; then
    if tailscale status >/dev/null 2>&1; then
        ok "tailscaled reachable."
        ts_ip4="$(tailscale ip -4 2>/dev/null | head -1)"
        ts_ip6="$(tailscale ip -6 2>/dev/null | head -1)"
        info "Tailscale IPv4: ${ts_ip4:-<none>}    IPv6: ${ts_ip6:-<none>}"
        # Is the Tailscale SSH server enabled? (tailscaled answers :22 from the tailnet,
        # BYPASSING system sshd for connections to the Tailscale IP.)
        run_ssh="$(tailscale debug prefs 2>/dev/null | grep -i '"RunSSH"' | head -1)"
        if echo "${run_ssh}" | grep -qi 'true'; then
            warn "Tailscale SSH is ENABLED (tailscale up --ssh)."
            warn "  -> Tailnet connections to ${ts_ip4:-<ts-ip>}:22 are served by tailscaled,"
            warn "     NOT system sshd. Access is governed by Tailscale ACL 'ssh' rules,"
            warn "     and fail2ban/sshd Match-Address do NOT see those sessions."
        else
            info "Tailscale SSH appears DISABLED -> tailnet :22 is served by system sshd."
        fi
    else
        bad "tailscale installed but 'tailscale status' failed (not logged in / tailscaled down?)."
        info "Try: sudo tailscale up --ssh"
    fi
else
    bad "tailscale not installed."
fi

# ---------------------------------------------------------------------------
head2 "2. What is listening on :22"
ss -tlnp 2>/dev/null | grep -E ':22\b' || warn "Nothing listening on :22 (no system sshd?)."
if systemctl list-unit-files 2>/dev/null | grep -q '^ssh\.socket'; then
    info "ssh.socket present (socket-activation): $(systemctl is-active ssh.socket 2>/dev/null)"
fi
info "ssh.service: $(systemctl is-active ssh 2>/dev/null) / $(systemctl is-enabled ssh 2>/dev/null)"

# ---------------------------------------------------------------------------
head2 "3. UFW firewall"
if command -v ufw >/dev/null 2>&1; then
    ufw_status="$(ufw status verbose 2>/dev/null)"
    echo "${ufw_status}" | sed 's/^/    /'
    echo "${ufw_status}" | grep -qi 'Status: active' && ok "UFW active." || bad "UFW INACTIVE."
    echo "${ufw_status}" | grep -qiE 'deny \(incoming\)' && ok "Default deny incoming." || warn "Default incoming is not deny."
    echo "${ufw_status}" | grep -qi 'tailscale0' && ok "Rule scoped to tailscale0 present." || warn "No tailscale0-scoped rule found."
    # Edge case 3: a plain 'allow 22 from Anywhere' (no interface) is an open door.
    if ufw status numbered 2>/dev/null | grep -E '22' | grep -qiE 'Anywhere' \
       && ! ufw status numbered 2>/dev/null | grep -E '22' | grep -qi 'tailscale0'; then
        bad "A port-22 rule allows 'Anywhere' WITHOUT tailscale0 — open to LAN/WAN."
    fi
    # Edge case 1: IPv6 filtering.
    if grep -qi '^IPV6=yes' /etc/default/ufw 2>/dev/null; then
        ok "UFW IPv6 filtering enabled (IPV6=yes)."
    else
        warn "UFW IPV6 is not 'yes' — sshd on [::]:22 may be unfiltered over IPv6."
    fi
else
    bad "ufw not installed."
fi

# ---------------------------------------------------------------------------
head2 "4. Effective sshd policy (system sshd)"
if [[ -x "${SSHD_BIN}" ]]; then
    if "${SSHD_BIN}" -t 2>/dev/null; then ok "sshd config syntax valid."; else bad "sshd -t reports INVALID config."; fi
    lan_au="$(${SSHD_BIN} -T -C "addr=192.168.1.100,user=${SSH_USER},host=x,laddr=0.0.0.0,lport=22" 2>/dev/null | grep -i '^allowusers')"
    ts_au="$(${SSHD_BIN}  -T -C "addr=100.100.100.100,user=${SSH_USER},host=x,laddr=0.0.0.0,lport=22" 2>/dev/null | grep -i '^allowusers')"
    info "allowusers (LAN src 192.168.x):   ${lan_au:-<unset = all users allowed>}"
    info "allowusers (tailnet src 100.x):   ${ts_au:-<unset = all users allowed>}"
    if [[ -n "${ts_au}" && -z "${lan_au/*nobody*/}" ]]; then
        ok "Match-Address layer looks active (LAN denied / tailnet allowed)."
    elif [[ -z "${lan_au}" ]]; then
        warn "No AllowUsers restriction by source — sshd Match-Address layer (SSOT Step 2) not applied."
    fi
    pra="$(${SSHD_BIN} -T 2>/dev/null | grep -i '^permitrootlogin' || true)"
    pwa="$(${SSHD_BIN} -T 2>/dev/null | grep -i '^passwordauthentication' || true)"
    info "${pra:-permitrootlogin <unknown>}    ${pwa:-passwordauthentication <unknown>}"
    echo "${pwa}" | grep -qi 'no'  || warn "PasswordAuthentication is not 'no'."
    echo "${pra}" | grep -qi 'no'  || warn "PermitRootLogin is not 'no'."
else
    warn "sshd binary not found at ${SSHD_BIN} (openssh-server not installed?)."
fi

# ---------------------------------------------------------------------------
head2 "5. Authorized keys for ${SSH_USER} (anti-lockout)"
home_dir="$(getent passwd "${SSH_USER}" | cut -d: -f6)"
if [[ -z "${home_dir}" ]]; then
    bad "User '${SSH_USER}' does not exist. Hardening would refuse to run."
else
    ak="${home_dir}/.ssh/authorized_keys"
    if [[ -s "${ak}" ]]; then
        ok "$(grep -cvE '^\s*(#|$)' "${ak}" 2>/dev/null) key(s) in ${ak}."
    else
        warn "No authorized_keys for ${SSH_USER}. If classic sshd is your access path and"
        warn "  PasswordAuthentication=no, hardening could lock you out. (Tailscale SSH is exempt.)"
    fi
fi

# ---------------------------------------------------------------------------
head2 "6. fail2ban"
if command -v fail2ban-client >/dev/null 2>&1; then
    info "service: $(systemctl is-active fail2ban 2>/dev/null)"
    if fail2ban-client status sshd >/dev/null 2>&1; then
        ok "sshd jail present."
        fail2ban-client status sshd 2>/dev/null | sed 's/^/    /'
        be="$(awk -F'=' '/^[[:space:]]*backend/ {print $2}' /etc/fail2ban/jail.d/*.conf /etc/fail2ban/jail.local 2>/dev/null | tr -d ' ' | tail -1)"
        info "configured backend (jail.d/jail.local): ${be:-<default>}"
        [[ "${be}" == "systemd" ]] || warn "Backend is not 'systemd'; on 24.04 (journald-only) it may see no logs."
    else
        warn "No active sshd jail. fail2ban may be installed but not jailing sshd."
    fi
else
    warn "fail2ban not installed."
fi

# ---------------------------------------------------------------------------
head2 "7. netfilter backend (split-brain check)"
update-alternatives --display iptables 2>/dev/null | grep -i 'link currently points to' | sed 's/^/    /' || true
chains="$(nft list ruleset 2>/dev/null | grep -c chain)"
info "nft chains: ${chains:-0}"
if iptables -L INPUT -n 2>/dev/null | grep -qiE 'tailscale|ts-input'; then
    info "tailscale-managed chains present in iptables view."
fi

# ---------------------------------------------------------------------------
head2 "8. Docker port-publish bypass (Edge case 2)"
if command -v docker >/dev/null 2>&1; then
    pub="$(docker ps --format '{{.Names}}\t{{.Ports}}' 2>/dev/null | grep -E '0\.0\.0\.0|:::' || true)"
    if [[ -n "${pub}" ]]; then
        warn "Containers publish ports to all interfaces (Docker writes DOCKER chain, bypasses UFW):"
        echo "${pub}" | sed 's/^/    /'
    else
        ok "No containers publishing ports to 0.0.0.0 (FA compose uses no host port-publish)."
    fi
fi

echo ""
echo "Diagnostics complete. Review WARN/FAIL above, then: 00-failsafe.sh arm -> 20-harden.sh -> 30-verify.sh"
