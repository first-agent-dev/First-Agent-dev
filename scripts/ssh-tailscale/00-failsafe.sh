#!/usr/bin/env bash
# 00-failsafe.sh — Dead-man switch for SSH-over-Tailscale hardening (SSOT Step 0).
#
# Schedules an automatic `ufw disable` after a timeout so that a mistake in
# firewall/sshd changes cannot lock you out of the AIO permanently. Standard
# remote-firewall practice (analogous to `iptables-apply` / Cisco `reload in`).
#
# Usage:
#   sudo bash 00-failsafe.sh arm [MINUTES]   # arm rollback (default 15 min)
#   sudo bash 00-failsafe.sh disarm          # cancel rollback after success
#   sudo bash 00-failsafe.sh status          # show timer state
#
# Re-exec under sudo if not already root.
set -euo pipefail

UNIT="ufw-failsafe"
DEFAULT_MINUTES=15

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

if [[ "${EUID}" -ne 0 ]]; then
    exec sudo -E bash "$0" "$@"
fi

cmd="${1:-}"

disarm() {
    # Stop the timer and clear any failed/lingering transient units.
    systemctl stop "${UNIT}.timer" 2>/dev/null || true
    systemctl stop "${UNIT}.service" 2>/dev/null || true
    systemctl reset-failed "${UNIT}.timer" 2>/dev/null || true
    systemctl reset-failed "${UNIT}.service" 2>/dev/null || true
    log_info "Failsafe disarmed (no pending 'ufw disable')."
}

case "${cmd}" in
    arm)
        minutes="${2:-${DEFAULT_MINUTES}}"
        if ! [[ "${minutes}" =~ ^[0-9]+$ ]] || [[ "${minutes}" -lt 1 ]]; then
            log_error "MINUTES must be a positive integer. Got: '${minutes}'"
            exit 2
        fi
        # Clear any previous instance first (idempotent re-arm).
        disarm
        systemd-run --on-active="${minutes}min" --unit="${UNIT}" \
            /bin/sh -c 'ufw disable' >/dev/null
        log_info "Failsafe ARMED: 'ufw disable' will run in ${minutes} minute(s)."
        log_warn "BEFORE you continue, open a SECOND SSH session to the AIO and keep it OPEN."
        log_warn "An established connection survives firewall changes (conntrack ESTABLISHED)"
        log_warn "and lets you roll back if the first session drops."
        echo ""
        log_warn "After you have CONFIRMED access still works post-hardening, disarm with:"
        echo "    sudo bash $0 disarm"
        ;;
    disarm)
        disarm
        ;;
    status|"")
        if systemctl is-active --quiet "${UNIT}.timer"; then
            log_warn "Failsafe is ARMED. Pending automatic 'ufw disable':"
            systemctl list-timers "${UNIT}.timer" --no-pager 2>/dev/null || true
        else
            log_info "Failsafe is NOT armed."
        fi
        if [[ -z "${cmd}" ]]; then
            echo ""
            echo "Usage: sudo bash $0 {arm [MINUTES]|disarm|status}"
        fi
        ;;
    *)
        log_error "Unknown command: '${cmd}'"
        echo "Usage: sudo bash $0 {arm [MINUTES]|disarm|status}"
        exit 2
        ;;
esac
