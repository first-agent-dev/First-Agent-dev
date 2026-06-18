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
_PROVIDER_PLACEHOLDERS_MARKER='Provider placeholders from secrets/fa.env.template'

ENV_FA_BACKED_UP=0
SECRETS_ENV_BACKED_UP=0

log_warn() { echo "[WARN] $*" >&2; }

unique_backup_path() {
    local prefix="$1"
    printf '%s/%s.%s.%s.%s.bak' \
        "${BACKUP_DIR}" \
        "${prefix}" \
        "$(date -u '+%Y%m%dT%H%M%SZ')" \
        "$$" \
        "${RANDOM}"
}

backup_env_fa_once() {
    [[ "${ENV_FA_BACKED_UP}" == "0" ]] || return 0
    [[ -f "${ENV_FA}" ]] || return 0
    "${SUDO[@]}" mkdir -p "${BACKUP_DIR}"
    local backup_path
    backup_path="$(unique_backup_path ".env.fa.pre-adr12-normalize")"
    "${SUDO[@]}" cp "${ENV_FA}" "${backup_path}"
    "${SUDO[@]}" chmod 600 "${backup_path}"
    # Remove any old in-workspace migration backup left by pre-ADR-12 scripts.
    rm -f "${ENV_FA}.pre-secret-migration.bak" 2>/dev/null || true
    ENV_FA_BACKED_UP=1
    log_warn "Backed up previous .env.fa to ${backup_path}"
}

backup_secrets_env_once() {
    [[ "${SECRETS_ENV_BACKED_UP}" == "0" ]] || return 0
    [[ -f "${SECRETS_ENV}" ]] || return 0
    "${SUDO[@]}" mkdir -p "${BACKUP_DIR}"
    local backup_path
    backup_path="$(unique_backup_path "fa.env.pre-adr12-normalize")"
    "${SUDO[@]}" cp "${SECRETS_ENV}" "${backup_path}"
    "${SUDO[@]}" chmod 600 "${backup_path}"
    SECRETS_ENV_BACKED_UP=1
    log_warn "Backed up previous fa.env to ${backup_path}"
}

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

active_secret_line_for_key() {
    local key="$1"
    grep -E "^[[:space:]]*${key}[[:space:]]*=" "${SECRETS_ENV}" 2>/dev/null | head -n1 || true
}

secret_line_is_placeholder() {
    local line="$1" value
    value="${line#*=}"
    value="${value#${value%%[![:space:]]*}}"
    value="${value%${value##*[![:space:]]}}"
    [[ -z "${value}" ]] || grep -qi 'CHANGEME' <<<"${value}"
}

append_secret_line() {
    local line="$1"
    backup_secrets_env_once
    printf '%s\n' "${line}" | "${SUDO[@]}" tee -a "${SECRETS_ENV}" >/dev/null
}

replace_active_secret_line() {
    local key="$1" replacement="$2" tmp
    backup_secrets_env_once
    tmp="$(mktemp)"
    awk -v key="${key}" -v replacement="${replacement}" '
        BEGIN { re = "^[[:space:]]*" key "[[:space:]]*="; done = 0 }
        $0 ~ re { if (!done) { print replacement; done = 1 }; next }
        { print }
        END { if (!done) print replacement }
    ' "${SECRETS_ENV}" >"${tmp}"
    "${SUDO[@]}" cp "${tmp}" "${SECRETS_ENV}"
    rm -f "${tmp}"
}

migrate_active_env_fa_secrets() {
    local secret_lines
    secret_lines="$(grep -E "${_SECRET_LINE_RE}" "${ENV_FA}" 2>/dev/null || true)"
    [[ -n "${secret_lines}" ]] || return 0

    ensure_secrets_env
    backup_env_fa_once

    while IFS= read -r line; do
        [[ -n "${line}" ]] || continue
        local key existing_line
        key="$(sed -E 's/^[[:space:]]*([A-Z0-9_]+)[[:space:]]*=.*$/\1/' <<<"${line}")"
        existing_line="$(active_secret_line_for_key "${key}")"
        if [[ -z "${existing_line}" ]]; then
            append_secret_line "${line}"
            log_warn "Migrated ${key} from .env.fa to ${SECRETS_ENV}."
        elif secret_line_is_placeholder "${existing_line}"; then
            replace_active_secret_line "${key}" "${line}"
            log_warn "Replaced placeholder ${key} in ${SECRETS_ENV} with the legacy .env.fa value."
        else
            log_warn "${key} already has a non-placeholder value in ${SECRETS_ENV}; removing duplicate from .env.fa."
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
    # If neither the stable append marker nor the template header is present,
    # the file likely came from the old .env.fa template or a hand-written
    # minimal key file. Append commented provider examples without touching
    # active keys.
    if ! grep -qE "${_PROVIDER_PLACEHOLDERS_MARKER}|First-Agent LLM API KEYS" "${SECRETS_ENV}"; then
        backup_secrets_env_once
        {
            printf '\n# --- %s (added by fa-normalize-env.sh) ---\n' "${_PROVIDER_PLACEHOLDERS_MARKER}"
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
    backup_env_fa_once
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
