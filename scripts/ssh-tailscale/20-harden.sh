#!/usr/bin/env bash
# 20-harden.sh — Apply the SSH-over-Tailscale defense-in-depth runbook on the AIO.
#
# Implements (idempotent, re-runnable):
#   Step 1  UFW: IPv6 filtering on, default deny-in, allow on tailscale0 only,
#           remove stray 'allow 22 from Anywhere' rules.
#   Step 2  sshd Match Address 100.64.0.0/10 + fd7a:115c:a1e0::/48 (identity layer
#           that does not depend on the interface), with default deny-all.
#   Step 3  fail2ban sshd jail with systemd backend (correct for Ubuntu 24.04).
#   Step 5  netfilter split-brain sanity (read-only report).
#   Step 6  systemd daemon-reload + mask sleep/suspend targets.
#
# Safety:
#   * Refuses to run unless the Step-0 dead-man failsafe is armed
#     (00-failsafe.sh arm) — pass --no-failsafe-check to override.
#   * Refuses if SSH_USER does not exist (anti-lockout).
#   * Validates sshd config with `sshd -t` AND asserts effective `allowusers`
#     for a LAN source vs a tailnet source with `sshd -T -C` BEFORE reloading.
#   * Uses `systemctl reload ssh` (never restart) so established sessions live.
#
# Usage:
#   sudo bash 20-harden.sh [--no-failsafe-check] [--yes]
#   SSH_USER=fa-operator  -> account allowed from the tailnet (default: fa-operator)
set -euo pipefail

SSH_USER="${SSH_USER:-${FA_USER:-fa-operator}}"
TS_V4_CGNAT="100.64.0.0/10"
TS_V6_ULA="fd7a:115c:a1e0::/48"
HARDENING_CONF="/etc/ssh/sshd_config.d/99-fa-hardening.conf"
TS_ONLY_CONF="/etc/ssh/sshd_config.d/99-tailscale-only.conf"
TS_PORT=22
STAMP="$(date +%Y%m%d-%H%M%S)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

NO_FAILSAFE_CHECK=0
ASSUME_YES=0
for arg in "$@"; do
    case "${arg}" in
        --no-failsafe-check) NO_FAILSAFE_CHECK=1 ;;
        --yes|-y)            ASSUME_YES=1 ;;
        *) log_error "Unknown argument: ${arg}"; exit 2 ;;
    esac
done

if [[ "${EUID}" -ne 0 ]]; then
    exec sudo -E bash "$0" "$@"
fi

SSHD_BIN="$(command -v sshd || echo /usr/sbin/sshd)"

confirm() {
    [[ "${ASSUME_YES}" -eq 1 ]] && return 0
    read -rp "$1 [y/N] " ans
    [[ "${ans}" =~ ^[Yy]$ ]]
}

# ---------------------------------------------------------------------------
# Pre-flight (anti-lockout)
# ---------------------------------------------------------------------------
log_info "Pre-flight checks (user=${SSH_USER})..."

home_dir="$(getent passwd "${SSH_USER}" | cut -d: -f6 || true)"
if [[ -z "${home_dir}" ]]; then
    log_error "User '${SSH_USER}' does not exist. Refusing to harden (anti-lockout)."
    log_error "Set SSH_USER to the real admin account, e.g.  SSH_USER=myuser sudo -E bash $0"
    exit 1
fi

if [[ ! -s "${home_dir}/.ssh/authorized_keys" ]]; then
    log_warn "No authorized_keys for '${SSH_USER}'."
    log_warn "If you reach this box via CLASSIC sshd (not Tailscale SSH) and"
    log_warn "PasswordAuthentication=no, applying this could lock you out."
    confirm "Continue anyway?" || { log_error "Aborted by user."; exit 1; }
fi

if [[ "${NO_FAILSAFE_CHECK}" -eq 0 ]]; then
    if ! systemctl is-active --quiet ufw-failsafe.timer; then
        log_error "Dead-man failsafe is NOT armed. Run first:"
        log_error "    sudo bash $(dirname "$0")/00-failsafe.sh arm"
        log_error "(open a SECOND SSH session too). Or pass --no-failsafe-check to override."
        exit 1
    fi
    log_info "Dead-man failsafe is armed."
fi

# ---------------------------------------------------------------------------
# Step 1 — UFW: IPv6 + default deny + tailscale0-only + stray-rule cleanup
# ---------------------------------------------------------------------------
log_info "Step 1: UFW firewall..."
if ! command -v ufw >/dev/null 2>&1; then
    log_error "ufw is not installed. Install it (apt-get install -y ufw) and re-run."
    exit 1
fi

# 1a. IPv6 filtering (Edge case 1).
if ! grep -qi '^IPV6=yes' /etc/default/ufw; then
    cp -a /etc/default/ufw "/etc/default/ufw.bak-${STAMP}"
    if grep -qiE '^IPV6=' /etc/default/ufw; then
        sed -i 's/^IPV6=.*/IPV6=yes/I' /etc/default/ufw
    else
        echo "IPV6=yes" >> /etc/default/ufw
    fi
    log_info "  Set IPV6=yes in /etc/default/ufw (backup: /etc/default/ufw.bak-${STAMP})."
else
    log_info "  IPV6=yes already set."
fi

# 1b. Remove stray port-22 'Anywhere' rules that are NOT scoped to tailscale0
#     (Edge case 3). Delete from highest index to keep numbering stable.
mapfile -t stray < <(ufw status numbered 2>/dev/null \
    | grep -E '\b22\b' | grep -iE 'Anywhere' | grep -iv 'tailscale0' \
    | grep -oE '^\[[ ]*[0-9]+\]' | grep -oE '[0-9]+' | sort -rn)
if [[ "${#stray[@]}" -gt 0 ]]; then
    log_warn "  Found stray port-22 ALLOW Anywhere rule(s) not bound to tailscale0: ${stray[*]}"
    for n in "${stray[@]}"; do
        log_warn "  Deleting UFW rule #${n}..."
        yes | ufw delete "${n}" >/dev/null 2>&1 || ufw --force delete "${n}" || true
    done
else
    log_info "  No stray open port-22 rules."
fi

# 1c. Defaults + tailscale0-only allow (idempotent; ufw dedupes identical rules).
ufw default deny incoming  >/dev/null
ufw default allow outgoing >/dev/null
ufw allow in on tailscale0 to any port "${TS_PORT}" proto tcp comment "SSH via Tailscale only" >/dev/null
ufw allow 41641/udp comment "Tailscale wireguard" >/dev/null
ufw --force enable >/dev/null
log_info "  UFW active: default deny-in, allow-out, SSH only on tailscale0."

# ---------------------------------------------------------------------------
# Step 2 — sshd Match Address (identity layer, interface-independent)
# ---------------------------------------------------------------------------
log_info "Step 2: sshd Match Address (tailnet CGNAT ranges)..."

# Reconcile: a global `AllowUsers` in 99-fa-hardening.conf is parsed BEFORE our
# file (alphabetical) and, being the first AllowUsers, would win for non-Match
# (LAN) sources — nullifying the source restriction. Neutralise it so the
# new file is the single owner of AllowUsers. Other hardening lines stay.
if [[ -f "${HARDENING_CONF}" ]] && grep -qE '^[[:space:]]*AllowUsers[[:space:]]' "${HARDENING_CONF}"; then
    cp -a "${HARDENING_CONF}" "${HARDENING_CONF}.bak-${STAMP}"
    sed -i -E 's/^([[:space:]]*AllowUsers[[:space:]].*)$/# \1  # neutralised by 20-harden.sh: AllowUsers owned by 99-tailscale-only.conf/' "${HARDENING_CONF}"
    log_info "  Commented out AllowUsers in ${HARDENING_CONF} (backup: ${HARDENING_CONF}.bak-${STAMP})."
fi

[[ -f "${TS_ONLY_CONF}" ]] && cp -a "${TS_ONLY_CONF}" "${TS_ONLY_CONF}.bak-${STAMP}"
cat > "${TS_ONLY_CONF}" <<EOF
# Managed by scripts/ssh-tailscale/20-harden.sh (SSOT Step 2).
# Identity-level gate that does NOT depend on the network interface: sshd keeps
# listening on 0.0.0.0 but only authenticates ${SSH_USER} from Tailscale source
# ranges (CGNAT 100.64.0.0/10 + fd7a:115c:a1e0::/48) plus loopback.
# Default: deny authentication to everyone.
AllowUsers nobody@127.0.0.1

Match Address ${TS_V4_CGNAT},${TS_V6_ULA},127.0.0.1,::1
    AllowUsers ${SSH_USER}
EOF
log_info "  Wrote ${TS_ONLY_CONF}."

# Validate syntax before doing anything that could break auth.
if ! "${SSHD_BIN}" -t; then
    log_error "  sshd -t FAILED. Restoring previous config and aborting (NOT reloaded)."
    if [[ -f "${TS_ONLY_CONF}.bak-${STAMP}" ]]; then
        mv -f "${TS_ONLY_CONF}.bak-${STAMP}" "${TS_ONLY_CONF}"
    else
        rm -f "${TS_ONLY_CONF}"
    fi
    if [[ -f "${HARDENING_CONF}.bak-${STAMP}" ]]; then
        mv -f "${HARDENING_CONF}.bak-${STAMP}" "${HARDENING_CONF}"
    fi
    exit 1
fi

# Authoritative self-test: effective allowusers per source.
lan_au="$(${SSHD_BIN} -T -C "addr=192.168.1.100,user=${SSH_USER},host=x,laddr=0.0.0.0,lport=22" 2>/dev/null | grep -i '^allowusers' || true)"
ts_au="$(${SSHD_BIN}  -T -C "addr=100.100.100.100,user=${SSH_USER},host=x,laddr=0.0.0.0,lport=22" 2>/dev/null | grep -i '^allowusers' || true)"
log_info "  self-test  LAN src  -> ${lan_au:-<unset>}"
log_info "  self-test  tailnet  -> ${ts_au:-<unset>}"
if ! echo "${lan_au}" | grep -qi 'nobody@127.0.0.1'; then
    log_error "  Self-test FAILED: LAN source is not restricted to nobody@127.0.0.1."
    log_error "  Another sshd_config file likely sets AllowUsers earlier. NOT reloading."
    log_error "  Inspect: grep -rn AllowUsers /etc/ssh/sshd_config /etc/ssh/sshd_config.d/"
    exit 1
fi
if ! echo "${ts_au}" | grep -qiw "${SSH_USER}"; then
    log_error "  Self-test FAILED: tailnet source does not allow '${SSH_USER}'. NOT reloading."
    exit 1
fi
log_info "  Self-tests passed (LAN denied / tailnet allows ${SSH_USER})."

# Reload (not restart) — established sessions survive.
systemctl reload ssh
log_info "  Reloaded ssh (config applied; existing sessions kept)."

# ---------------------------------------------------------------------------
# Step 3 — fail2ban sshd jail with systemd backend
# ---------------------------------------------------------------------------
log_info "Step 3: fail2ban (systemd backend)..."
if ! command -v fail2ban-client >/dev/null 2>&1; then
    log_warn "  fail2ban not installed; skipping (install: apt-get install -y fail2ban)."
else
    mkdir -p /etc/fail2ban/jail.d
    cat > /etc/fail2ban/jail.d/sshd-local.conf <<'EOF'
# Managed by scripts/ssh-tailscale/20-harden.sh (SSOT Step 3).
# systemd backend is required on Ubuntu 24.04 (journald-only; no /var/log/auth.log).
[sshd]
enabled = true
backend = systemd
mode = aggressive
maxretry = 3
findtime = 10m
bantime = 1h
bantime.increment = true
bantime.maxtime = 1w
# Whitelist loopback only. We deliberately do NOT ignore the whole tailnet:
# after Step 2 the only hosts that can attempt auth are tailnet nodes, so
# fail2ban now defends against a compromised tailnet device (lateral movement).
ignoreip = 127.0.0.1/8 ::1
EOF
    systemctl restart fail2ban
    sleep 1
    if fail2ban-client status sshd >/dev/null 2>&1; then
        log_info "  sshd jail active."
    else
        log_warn "  sshd jail not reporting active yet; check: fail2ban-client status sshd"
    fi
fi

# ---------------------------------------------------------------------------
# Step 5 — netfilter split-brain sanity (read-only)
# ---------------------------------------------------------------------------
log_info "Step 5: netfilter backend sanity (read-only)..."
alt="$(update-alternatives --query iptables 2>/dev/null | awk -F': ' '/^Value:/ {print $2}')"
[[ "${alt}" == *iptables-nft* ]] && log_info "  iptables alternative -> ${alt}" \
    || log_warn "  iptables alternative is '${alt:-unknown}' (expected iptables-nft on 24.04)."

# ---------------------------------------------------------------------------
# Step 6 — systemd hygiene: daemon-reload + mask sleep
# ---------------------------------------------------------------------------
log_info "Step 6: systemd daemon-reload + mask sleep targets..."
systemctl daemon-reload
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target >/dev/null 2>&1 || true
log_info "  Done."

# ---------------------------------------------------------------------------
echo ""
log_info "Hardening applied. NEXT:"
echo "  1. Confirm you can still open a NEW SSH session over Tailscale."
echo "  2. Run verification:        sudo bash $(dirname "$0")/30-verify.sh"
echo "  3. Apply Tailscale ACL:     see $(dirname "$0")/tailscale-acl.jsonc"
echo "  4. ONLY THEN disarm:        sudo bash $(dirname "$0")/00-failsafe.sh disarm"
log_warn "Do NOT disarm the failsafe until step 1 above is confirmed from a fresh connection."
