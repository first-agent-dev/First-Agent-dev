#!/usr/bin/env bash
# Backup First-Agent persistent host state to Backblaze B2 (S3-compatible endpoint)
# Cross-reference: restic community recommends S3-compatible B2 endpoint over native B2 backend.
#
# Backup scope:
#   - /srv/first-agent/state      agent state/history/config (no LLM keys)
#   - /srv/first-agent/routing    source-of-truth models.yaml
#   - /srv/first-agent/secrets    LLM keys, proxy token, deploy key, backup creds
#   - .env.fa                    NON-SECRET runtime controls only
#
# ADR-12 secret/routing policy:
#   - LLM API keys live in /srv/first-agent/secrets/fa.env only.
#   - .env.fa is backed up only as non-secret runtime controls.
#   - /srv/first-agent/proxy is intentionally not backed up: after unified
#     routing it is legacy/not mounted and is not a source of truth.
#
# Pre-requisites:
#   1. Create a Backblaze B2 bucket
#   2. Generate an Application Key with read/write access to that bucket
#   3. Fill in B2_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET in /srv/first-agent/secrets/backup.env
#   4. Run once manually: restic -r "$RESTIC_REPO" init
#   5. Add to cron or systemd timer for nightly execution
#
# Schedule example (cron):
#   0 3 * * * /srv/first-agent/scripts/backup-fa.sh >> /srv/first-agent/backup/backup.log 2>&1
#
# Test restore quarterly:
#   restic -r "$RESTIC_REPO" restore latest --target /tmp/restore-test

set -euo pipefail

# Source credentials from host secrets directory (outside repo, not tracked)
if [ -f /srv/first-agent/secrets/backup.env ]; then
    # shellcheck source=/dev/null
    source /srv/first-agent/secrets/backup.env
fi

B2_KEY_ID="${B2_KEY_ID:-CHANGEME}"
B2_APPLICATION_KEY="${B2_APPLICATION_KEY:-CHANGEME}"
B2_BUCKET="${B2_BUCKET:-CHANGEME}"
# Use S3-compatible B2 endpoint (NOT native b2: backend)
RESTIC_REPO="s3:https://s3.us-west-004.backblazeb2.com/${B2_BUCKET}"
BACKUP_TAG="fa-$(hostname)"

if [[ "$B2_KEY_ID" == "CHANGEME" || "$B2_APPLICATION_KEY" == "CHANGEME" || "$B2_BUCKET" == "CHANGEME" ]]; then
    echo "ERROR: Backblaze B2 credentials not configured." >&2
    echo "Edit /srv/first-agent/secrets/backup.env and re-run." >&2
    exit 1
fi

export AWS_ACCESS_KEY_ID="$B2_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$B2_APPLICATION_KEY"

# If FA uses SQLite, uncomment to stop the agent process before snapshot for consistency
# docker exec first-agent pkill -f "fa run" || true
# sleep 2

restic -r "$RESTIC_REPO" backup \
    /srv/first-agent/state \
    /srv/first-agent/routing \
    /srv/first-agent/secrets \
    /srv/first-agent/scripts \
    /srv/first-agent/repo/First-Agent-dev/docker-compose.fa.yml \
    /srv/first-agent/repo/First-Agent-dev/.env.fa \
    /etc/ssh/sshd_config.d/99-fa-hardening.conf \
    /etc/systemd/logind.conf.d/no-suspend.conf \
    /etc/apt/apt.conf.d/50unattended-upgrades-fa \
    /etc/docker/daemon.json \
    --tag "$BACKUP_TAG" \
    --exclude-if-present .nobackup \
    --exclude "**/__pycache__" \
    --exclude "**/.mypy_cache" \
    --exclude "**/.pytest_cache" \
    --exclude "**/.ruff_cache" \
    --exclude "**/.venv" \
    --exclude "**/*.pyc"

# Retention: 7 daily + 4 weekly + 6 monthly
restic -r "$RESTIC_REPO" forget \
    --tag "$BACKUP_TAG" \
    --keep-daily 7 \
    --keep-weekly 4 \
    --keep-monthly 6 \
    --prune
