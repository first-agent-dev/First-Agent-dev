#!/usr/bin/env bash
# 30-verify.sh — Verify the SSH-over-Tailscale hardening (SSOT final checklist).
#
# Read-only. Exits non-zero if any automated check fails, so it can gate a
# reboot test or CI. The LAN negative-test cannot be fully driven from the box
# itself (needs a second machine); its manual steps are printed at the end.
#
# Usage:  sudo bash 30-verify.sh
#   SSH_USER overrides the audited account (default: fa).
set -uo pipefail
# Force C locale so `ufw status` etc. parse in English on non-English systems
# (ru_RU prints "Состояние: активен" rather than "Status: active").
export LC_ALL=C

SSH_USER="${SSH_USER:-${FA_USER:-fa}}"
TS_ONLY_CONF="/etc/ssh/sshd_config.d/99-tailscale-only.conf"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
PASS=0; FAIL=0; WARN=0
pass() { echo -e "  ${GREEN}[PASS]${NC} $*"; PASS=$((PASS+1)); }
fail() { echo -e "  ${RED}[FAIL]${NC} $*"; FAIL=$((FAIL+1)); }
warn() { echo -e "  ${YELLOW}[WARN]${NC} $*"; WARN=$((WARN+1)); }

if [[ "${EUID}" -ne 0 ]]; then
    exec sudo -E bash "$0" "$@"
fi
SSHD_BIN="$(command -v sshd || echo /usr/sbin/sshd)"

echo "Verifying SSH-over-Tailscale hardening (user=${SSH_USER})"

# 1. sshd listens on 0.0.0.0:22 (intended — it filters by source, not bind addr).
if ss -tlnp 2>/dev/null | grep -qE ':22\b'; then
    pass "Something is listening on :22 ($(ss -tlnp 2>/dev/null | grep -E ':22\b' | grep -oE 'users:\(\("[^"]+' | grep -oE '"[^"]+$' | tr -d '"' | paste -sd, -))."
else
    warn "Nothing on :22 — OK only if access is exclusively Tailscale SSH (tailscaled)."
fi

# 2. UFW: active, deny-in, tailscale0 rule, IPv6.
ufw_v="$(ufw status verbose 2>/dev/null)"
echo "${ufw_v}" | grep -qi 'Status: active'      && pass "UFW active."             || fail "UFW not active."
echo "${ufw_v}" | grep -qiE 'deny \(incoming\)'  && pass "Default deny incoming."  || fail "Default incoming not deny."
echo "${ufw_v}" | grep -qi 'tailscale0'          && pass "tailscale0 SSH rule present." || fail "No tailscale0 rule."
grep -qi '^IPV6=yes' /etc/default/ufw 2>/dev/null && pass "UFW IPv6 filtering on."  || fail "UFW IPV6 not 'yes'."
if ufw status numbered 2>/dev/null | grep -E '\b22\b' | grep -iE 'Anywhere' | grep -qiv 'tailscale0'; then
    fail "A port-22 'Anywhere' rule without tailscale0 still exists."
else
    pass "No stray open port-22 rule."
fi

# 3. sshd Match Address active (authoritative -T self-test).
[[ -f "${TS_ONLY_CONF}" ]] && pass "${TS_ONLY_CONF} present." || warn "${TS_ONLY_CONF} missing."
if "${SSHD_BIN}" -t 2>/dev/null; then pass "sshd config valid."; else fail "sshd -t invalid."; fi
lan_au="$(${SSHD_BIN} -T -C "addr=192.168.1.100,user=${SSH_USER},host=x,laddr=0.0.0.0,lport=22" 2>/dev/null | grep -i '^allowusers' || true)"
ts_au="$(${SSHD_BIN}  -T -C "addr=100.100.100.100,user=${SSH_USER},host=x,laddr=0.0.0.0,lport=22" 2>/dev/null | grep -i '^allowusers' || true)"
echo "${lan_au}" | grep -qi 'nobody@127.0.0.1' && pass "LAN source -> denied (allowusers=${lan_au#allowusers })." || fail "LAN source not restricted (allowusers=${lan_au:-<unset>})."
echo "${ts_au}"  | grep -qiw "${SSH_USER}"     && pass "tailnet source -> allows ${SSH_USER}." || fail "tailnet source does not allow ${SSH_USER} (allowusers=${ts_au:-<unset>})."
"${SSHD_BIN}" -T 2>/dev/null | grep -qi '^passwordauthentication no' && pass "PasswordAuthentication no." || warn "PasswordAuthentication not no."
"${SSHD_BIN}" -T 2>/dev/null | grep -qi '^permitrootlogin no'        && pass "PermitRootLogin no."        || warn "PermitRootLogin not no."

# 4. fail2ban sshd jail with systemd backend.
if command -v fail2ban-client >/dev/null 2>&1 && fail2ban-client status sshd >/dev/null 2>&1; then
    pass "fail2ban sshd jail active."
    be="$(awk -F'=' '/^[[:space:]]*backend/ {print $2}' /etc/fail2ban/jail.d/*.conf 2>/dev/null | tr -d ' ' | tail -1)"
    [[ "${be}" == "systemd" ]] && pass "fail2ban backend=systemd." || warn "fail2ban backend is '${be:-default}', not systemd."
else
    warn "fail2ban sshd jail not active."
fi

echo ""
echo -e "Summary: ${GREEN}${PASS} passed${NC}, ${YELLOW}${WARN} warn${NC}, ${RED}${FAIL} failed${NC}."
cat <<EOF

Manual checks not automatable from this host:
  * LAN negative test (from another machine on the LAN, NOT the tailnet):
        ssh ${SSH_USER}@<AIO-LAN-IP>        # expect: timeout (UFW drop)
        # If you temporarily 'sudo ufw disable', the SAME attempt should then
        # return 'Permission denied' (sshd Match) — proving the second layer.
  * Reboot test: sudo reboot, then reconnect over Tailscale and re-run this script.
  * Tailscale ACL (control-plane deny): see tailscale-acl.jsonc.
EOF

[[ "${FAIL}" -eq 0 ]] || exit 1
