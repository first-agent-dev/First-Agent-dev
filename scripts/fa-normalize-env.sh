#!/usr/bin/env bash
# Normalize ADR-12 environment files without losing operator settings.
#
# - LLM provider keys belong in /srv/first-agent/secrets/fa.env (proxy only).
# - .env.fa is non-secret FA_* runtime controls only.
# - Existing active FA_* controls are preserved; active legacy secret lines are
#   migrated to the secrets file and removed from .env.fa.

set -euo pipefail

REPO_DIR="${REPO_DIR:-/srv/first-agent/repo/First-Agent-dev}"
ENV_FA="${ENV_FA:-${REPO_DIR}/.env.fa}"
ENV_TEMPLATE="${ENV_TEMPLATE:-${REPO_DIR}/.env.fa.template}"
SECRETS_ENV="${SECRETS_ENV:-/srv/first-agent/secrets/fa.env}"
SECRETS_TEMPLATE="${SECRETS_TEMPLATE:-${REPO_DIR}/secrets/fa.env.template}"
BACKUP_DIR="${BACKUP_DIR:-/srv/first-agent/secrets}"

if [[ "${FA_NORMALIZE_USE_SUDO:-1}" == "0" ]]; then
    SUDO=()
else
    SUDO=(sudo)
fi

_SECRET_LINE_RE='^[[:space:]]*([A-Z0-9_]+(API_KEY|_TOKEN|_SECRET))[[:space:]]*='
_ACTIVE_ASSIGN_RE='^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*[[:space:]]*='
_ACTIVE_FA_RE='^[[:space:]]*FA_[A-Z0-9_]+[[:space:]]*='
_LEGACY_ENV_HINT_RE='LLM API keys[[:space:]]*->[[:space:]]*.env.fa|Uncomment and fill in the keys|^[[:space:]]*#[[:space:]]*[A-Z0-9_]+(API_KEY|_TOKEN|_SECRET)[[:space:]]*='

log_info() { echo "[INFO] $*"; }
log_warn() { echo "[WARN] $*" >&2; }

ensure_secrets_env() {
    "${SUDO[@]}" mkdir -p "$(dirname "${SECRETS_ENV}")"
    if [[ ! -f "${SECRETS_ENV}" ]]; then
        if [[ -f "${SECRETS_TEMPLATE}" ]]; then
            "${SUDO[@]}" cp "${SECRETS_TEMPLATE}" "${SECRETS_ENV}"
        else
            "${SUDO[@]}" tee "${SECRETS_ENV}" >/dev/null <<'EOF'
# First-Agent LLM API KEYS — consumed ONLY by the fa-egress-proxy container.
# NEVER commit. Uncomment and fill in the providers you use.
# OPENROUTER_API_KEY=sk-or-v1-CHANGEME
# FIREWORKS_API_KEY=fw-CHANGEME
# ANTHROPIC_API_KEY=sk-ant-CHANGEME
# OPENAI_API_KEY=sk-CHANGEME
EOF
        fi
        log_warn "API-keys file created at ${SECRETS_ENV}. EDIT IT (with: micro ${SECRETS_ENV}) before first run."
    fi
    "${SUDO[@]}" chown 1000:1000 "${SECRETS_ENV}" 2>/dev/null || true
    "${SUDO[@]}" chmod 600 "${SECRETS_ENV}"
}

ensure_env_fa() {
    if [[ ! -f "${ENV_FA}" ]]; then
        if [[ -f "${ENV_TEMPLATE}" ]]; then
            cp "${ENV_TEMPLATE}" "${ENV_FA}"
        else
            cat >"${ENV_FA}" <<'EOF'
# First-Agent NON-SECRET runtime controls (loaded by Docker Compose env_file).
# API KEYS do NOT go here — they live in /srv/first-agent/secrets/fa.env (ADR-12).
# Optional one-shot auto-run controls:
# FA_AUTO_RUN=0
# FA_TASK=...
# FA_ROLE=coder
# FA_RUN_ID=my-run-id
EOF
        fi
        chmod 600 "${ENV_FA}"
        log_warn "Created ${ENV_FA} for non-secret controls. API keys go in ${SECRETS_ENV}."
    fi
}

backup_env_fa() {
    "${SUDO[@]}" mkdir -p "${BACKUP_DIR}"
    local backup_path
    backup_path="${BACKUP_DIR}/.env.fa.pre-adr12-normalize.$(date +%s).bak"
    "${SUDO[@]}" cp "${ENV_FA}" "${backup_path}"
    "${SUDO[@]}" chmod 600 "${backup_path}"
    # Remove any old in-workspace migration backup left by pre-ADR-12 scripts.
    rm -f "${ENV_FA}.pre-secret-migration.bak" 2>/dev/null || true
    log_warn "Backed up previous .env.fa to ${backup_path}"
}

active_secret_keys_in_file() {
    local file="$1"
    grep -E "${_SECRET_LINE_RE}" "${file}" 2>/dev/null \
        | sed -E 's/^[[:space:]]*([A-Z0-9_]+)[[:space:]]*=.*$/\1/'
}

migrate_active_env_fa_secrets() {
    local secret_lines
    secret_lines="$(grep -E "${_SECRET_LINE_RE}" "${ENV_FA}" 2>/dev/null || true)"
    [[ -n "${secret_lines}" ]] || return 0

    ensure_secrets_env
    backup_env_fa

    while IFS= read -r line; do
        [[ -n "${line}" ]] || continue
        local key
        key="$(sed -E 's/^[[:space:]]*([A-Z0-9_]+)[[:space:]]*=.*$/\1/' <<<"${line}")"
        if active_secret_keys_in_file "${SECRETS_ENV}" | grep -qx "${key}"; then
            log_warn "${key} already present in ${SECRETS_ENV}; removing legacy copy from .env.fa."
        else
            printf '%s\n' "${line}" | "${SUDO[@]}" tee -a "${SECRETS_ENV}" >/dev/null
            log_warn "Migrated ${key} from .env.fa to ${SECRETS_ENV}."
        fi
    done <<<"${secret_lines}"

    sed -i -E "/${_SECRET_LINE_RE}/d" "${ENV_FA}"
    chmod 600 "${ENV_FA}"
    "${SUDO[@]}" chown 1000:1000 "${SECRETS_ENV}" 2>/dev/null || true
    "${SUDO[@]}" chmod 600 "${SECRETS_ENV}"
}

append_secret_template_placeholders_if_missing() {
    [[ -f "${SECRETS_TEMPLATE}" ]] || return 0
    [[ -f "${SECRETS_ENV}" ]] || return 0
    # If the ADR-12 provider-key template marker is absent, the file likely came
    # from the old .env.fa template or from a hand-written minimal key file.
    # Append commented provider examples without touching active keys.
    if ! grep -q 'First-Agent LLM API KEYS' "${SECRETS_ENV}"; then
        {
            printf '\n# --- Provider placeholders from secrets/fa.env.template (added by fa-normalize-env.sh) ---\n'
            cat "${SECRETS_TEMPLATE}"
        } | "${SUDO[@]}" tee -a "${SECRETS_ENV}" >/dev/null
        "${SUDO[@]}" chmod 600 "${SECRETS_ENV}"
        log_warn "Added commented provider placeholders to ${SECRETS_ENV}."
    fi
}

normalize_legacy_env_fa_comments() {
    grep -qE "${_LEGACY_ENV_HINT_RE}" "${ENV_FA}" 2>/dev/null || return 0
    [[ -f "${ENV_TEMPLATE}" ]] || { log_warn "Legacy .env.fa comments detected, but ${ENV_TEMPLATE} is missing; leaving file unchanged."; return 0; }

    local active_unknown active_fa tmp
    active_unknown="$(grep -E "${_ACTIVE_ASSIGN_RE}" "${ENV_FA}" 2>/dev/null | grep -Ev "${_ACTIVE_FA_RE}" || true)"
    if [[ -n "${active_unknown}" ]]; then
        log_warn "Legacy .env.fa comments detected, but unknown active assignments are present; leaving comments unchanged."
        log_warn "Move secrets to ${SECRETS_ENV}, keep only FA_* controls in .env.fa, then re-run."
        return 0
    fi

    active_fa="$(grep -E "${_ACTIVE_FA_RE}" "${ENV_FA}" 2>/dev/null || true)"
    backup_env_fa
    tmp="$(mktemp)"
    cp "${ENV_TEMPLATE}" "${tmp}"
    if [[ -n "${active_fa}" ]]; then
        {
            printf '\n# Active local controls preserved from previous .env.fa:\n'
            printf '%s\n' "${active_fa}"
        } >>"${tmp}"
    fi
    cp "${tmp}" "${ENV_FA}"
    rm -f "${tmp}"
    chmod 600 "${ENV_FA}"
    log_warn "Replaced legacy .env.fa comments with the ADR-12 non-secret template."
}

main() {
    ensure_env_fa
    ensure_secrets_env
    migrate_active_env_fa_secrets
    normalize_legacy_env_fa_comments
    append_secret_template_placeholders_if_missing
}

main "$@"
