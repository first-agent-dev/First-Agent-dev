INTENT: CHORE
INVARIANT: n/a

## Summary

Tidies the Docker/AIO deployment surface and ships a beginner-friendly operator
manual, without changing any runtime agent behaviour:

- **De-duplicates the host deploy scripts** so each piece of logic has one home,
  while keeping the bootstrap script self-contained.
- **Fixes a stale, invalid `scripts/fa.service`** (a systemd *user* unit that
  declared `Requires=docker.service`, which a user unit cannot satisfy).
- **Rewrites `DOCKER_USAGE_GUIDE.md`** as a structured, Russian-language
  production manual aimed at an operator who has never used Docker, with both an
  automated (full-script) and a bare-bones manual workflow.
- **Corrects two documentation bugs** (one I introduced mid-work and caught in
  review, one pre-existing in `SETUP_AIO.md`).
- **Adds a drift-guard test** so the consolidation cannot silently regress.

> Note on intent: labelled `CHORE` because the deliverable is documentation +
> script tidy with no change to running-agent behaviour. It does embed two small
> correctness fixes (the `fa.service` user-unit and the `.env.fa` reload doc);
> relabel to `FIX/REPAIR` if you prefer to foreground those.

## Background

The repo's deployment flow is intentionally **two-phase**: `setup-fa-desktop.sh`
(host bootstrap) → manual gates (GitHub deploy key, Tailscale auth, `.env.fa`) →
`fa-post-setup.sh` (build + verify + service). A true single-command deploy is
not possible without weakening security, so the "one-click" experience is a
documented sequence, not a merged mega-script. This PR keeps that architecture
and improves the parts around it.

## Code Changes

### Script consolidation (single source of truth)

- `scripts/setup-fa-desktop.sh` now installs the systemd unit **from**
  `scripts/fa.service` (in the cloned repo) and the backup script **from**
  `scripts/backup-fa.sh`, instead of carrying inline heredoc copies that had
  already drifted. The `WorkingDirectory=` line is rewritten to the resolved
  `$FA_DIR` so a non-default install path still works.
- Removed the inline systemd unit heredoc and the inline `backup-fa.sh` fallback
  heredoc (the restic command no longer appears twice).
- The script stays **self-contained**: it does *not* source any helper library.
  This is required by `knowledge/SETUP_AIO.md` Phase 4 **Option B**, which
  downloads only this one file to `/tmp` and runs it — the repo is cloned later,
  by the script itself. A sourced library would die before the clone exists.
  Both the service- and backup-template installs read from the **cloned-repo
  path** (which exists in both run modes), not from the script's own directory.

### `scripts/fa.service` — valid systemd user unit

Dropped `After=docker.service` / `Requires=docker.service`. A user unit cannot
depend on a system unit, so those lines were inert at best. This aligns the
committed template with the unit that was actually being installed and with the
2026-06-10 decision recorded in `HANDOFF.md`. Boot ordering against Docker is
handled by the container's own `restart: unless-stopped` plus Docker
`live-restore`; the unit keeps a soft `After=/Wants=` on networking only.

### `scripts/fa-update.sh`

One-line `# shellcheck disable=SC2154` with rationale on the `ERR` trap (`rc` is
assigned inside the same trap string; shellcheck cannot see into it). No logic
change.

## Documentation Changes

### `DOCKER_USAGE_GUIDE.md` — full rewrite (Russian)

Replaces the prior loosely-structured guide with a navigable operator manual:
mental-model + a beginner Docker glossary, first-deploy workflow, **automated**
update via `fa-update.sh` (all flags documented) **and** a bare-bones **manual**
update path for when scripts fail, service/container admin, agent-task workflows
(stand-by / auto-run / planner→coder→eval), backup & restore, a security section
that links to `scripts/ssh-tailscale/`, troubleshooting, and a cheat-sheet. Every
command has a one-line Russian explanation.

### `knowledge/SETUP_AIO.md` — Phase 9 correctness fix (pre-existing bug)

Phase 9 told operators to edit B2 credentials directly into `backup-fa.sh`, but
the script `source`s `/srv/first-agent/secrets/backup.env` and is **overwritten
from the repo on every `setup-fa-desktop.sh` re-run** — so inline edits would
silently vanish and backups would fail. Rewrote Phase 9 to put credentials in
`backup.env` and use absolute paths.

## Tests

- New `tests/test_deploy_scripts.py` (cheap, static — no Docker):
  - `bash -n` syntax + `shellcheck -S warning` over every deploy/admin script
    (shellcheck test self-skips if the binary is absent).
  - Pins the invariants this PR establishes: the bootstrap stays self-contained
    (no `source …/lib/…`), `fa.service` is installed from the cloned repo, no
    re-inlined heredocs, and `fa.service` is a valid user unit (no
    `Requires=docker.service`).

## Review Fixes Applied During Final Pass

A self-review pass against `SETUP_AIO.md` caught a regression in an earlier draft
of this same PR and a latent doc bug:

1. **Bootstrap-breaking regression (caught pre-merge).** An earlier draft
   extracted a `scripts/lib/common.sh` and `source`d it from the top of
   `setup-fa-desktop.sh`. That broke `SETUP_AIO.md` Phase 4 Option B
   (download-to-`/tmp`) with an immediate exit 2. Resolution: dropped the shared
   library entirely (its only other consumer was a single script — no real DRY
   payoff) and kept the architecture-respecting SSOT fixes only. Added the
   self-contained-bootstrap test so it cannot return.
2. **`.env.fa` reload logic error in the guide.** An early draft said "edit
   `.env.fa`, then `docker compose restart`". `restart` does **not** re-read
   `env_file`; the container must be recreated. Fixed to `up -d
   --force-recreate`, with a note that `systemctl --user restart fa.service`
   *is* correct because the unit runs `down`+`up`.

## Validation Performed

- `bash -n` and `shellcheck -S warning`: clean on all 9 deploy/admin scripts.
- Reproduced the original standalone-bootstrap failure, then confirmed the fix.
- `pytest tests/test_deploy_scripts.py tests/test_fa_update_script.py
  tests/test_fa_entrypoint.py` → **31 passed**.
- `markdownlint-cli` pinned `v0.41.0` (repo's pre-commit version): clean on
  `DOCKER_USAGE_GUIDE.md`; **no new** findings in `SETUP_AIO.md` / `HANDOFF.md`.
- `ruff check` + `ruff format --check` on the new test: clean.
- All internal anchors and `scripts/*` links in the guide resolve.

> Sandbox caveat: `uv`/`docker` are not installed here, so validation is static
> (syntax + shellcheck + markdownlint + the doc/path checks). The live deploy
> path should be exercised on a scratch host before relying on it in production.

## Files Changed

- `scripts/setup-fa-desktop.sh` — install unit + backup from repo; no inline dupes; self-contained.
- `scripts/fa.service` — valid systemd user unit.
- `scripts/fa-update.sh` — shellcheck rationale (no logic change).
- `DOCKER_USAGE_GUIDE.md` — full Russian operator-manual rewrite.
- `knowledge/SETUP_AIO.md` — Phase 9 backup-credentials correctness fix.
- `knowledge/llms.txt` — index rows for the rewritten guide + new test.
- `HANDOFF.md` — current-state entry for this work.
- `tests/test_deploy_scripts.py` — new drift-guard test.

## Not In This PR (proposed follow-ups)

- Documentation information-architecture consolidation (e.g. a
  `knowledge/instructions/` home for operator-facing guides) — discussed
  separately; intentionally deferred so this PR stays a focused tidy + manual.
- Pending operator docs not yet written: runtime-usage instructions and a
  user-facing module overview.
