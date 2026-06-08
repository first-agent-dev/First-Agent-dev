#!/usr/bin/env bash
# Backup First-Agent state to Backblaze B2 (S3-compatible endpoint)
# Cross-reference: restic community recommends S3-compatible B2 endpoint over native B2 backend.
#
# Pre-requisites:
#   1. Create a Backblaze B2 bucket
#   2. Generate an Application Key with read/write access to that bucket
#   3. Fill in B2_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET below
#   4. Run once manually: restic -r "$RESTIC_REPO" init
#   5. Add to cron or systemd timer for nightly execution
#
# Schedule example (cron):
#   0 3 * * * /srv/first-agent/scripts/backup-fa.sh >> /srv/first-agent/backup/backup.log 2>&1
#
# Test restore quarterly:
#   restic -r "$RESTIC_REPO" restore latest --target /tmp/restore-test

set -euo pipefail

B2_KEY_ID="${B2_KEY_ID:-CHANGEME}"
B2_APPLICATION_KEY="${B2_APPLICATION_KEY:-CHANGEME}"
B2_BUCKET="${B2_BUCKET:-CHANGEME}"
# Use S3-compatible B2 endpoint (NOT native b2: backend)
RESTIC_REPO="s3:https://s3.us-west-004.backblazeb2.com/${B2_BUCKET}"
BACKUP_TAG="fa-$(hostname)"

export AWS_ACCESS_KEY_ID="$B2_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$B2_APPLICATION_KEY"

# If FA uses SQLite, uncomment to stop the agent process before snapshot for consistency
# docker exec first-agent pkill -f "fa run" || true
# sleep 2

restic -r "$RESTIC_REPO" backup \
    /srv/first-agent/state \
    /srv/first-agent/secrets \
    /srv/first-agent/scripts \
    /srv/first-agent/repo/First-Agent-dev/docker-compose.fa.yml \
    /srv/first-agent/repo/First-Agent-dev/.env.fa \
    /etc/ssh/sshd_config.d/99-fa-hardening.conf \
    /etc/systemd/logind.conf.d/no-suspend.conf \
    /etc/apt/apt.conf.d/50unattended-upgrades-fa \
    /etc/docker/daemon.json \
    "$HOME/.config/systemd/user/fa.service" \
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
