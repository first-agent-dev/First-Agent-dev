# PR Note: Hook workflow closure — bootstrap reliability and visibility

**Intent:** CHORE
**Date:** 2026-06-28
**Scope:** `justfile`, `src/fa/hygiene/hooks/`, `tests/test_hygiene_hooks_install.py`, `knowledge/`

## Problem

The local hook system was not reliably installed or visible after a fresh clone. Three concrete failure modes were observed and confirmed from the reviewed implementation plan.

First, `just install` ran `uv sync` (without `--extra dev`) followed by a bare `pre-commit install` shell command. Because `pre-commit` is declared in `[project.optional-dependencies] dev`, plain `uv sync` did not install it, and the subsequent `pre-commit install` failed with "command not found" on Windows/PowerShell — the user's actual working environment. This was the highest-ROI bug in the entire hook topic.

Second, there was no deterministic way to verify whether hooks were installed in a given clone. A contributor could reasonably believe hooks were active while they were not, creating false confidence that local commits were guarded.

Third, the `install-hooks` justfile recipe used raw `cp -f` and `chmod +x` shell commands that are fragile on PowerShell (where `chmod` does not exist), while a tested Python installer (`fa.hygiene.hooks.install`) already existed with proper idempotency, force flags, and workspace resolution — but was not wired into the justfile.

A subsequent code review found one additional critical bug: when the installer fell back from symlink to copy (Windows without Developer Mode), it chmod'd the *source* file but not the *target* copy, producing a non-executable hook that git silently skips — exactly on the platform where the fallback fires.

## Changes

### `justfile`

- `install` recipe now uses `uv sync --extra dev` (matching CI's dependency surface) and `uv run pre-commit install` (invoking through the project environment instead of relying on PATH). Prints a success summary at the end.
- `install-hooks` recipe now delegates to `uv run python -m fa.hygiene.hooks.install --force` instead of raw `cp -f` / `chmod +x`, so the justfile and direct Python invocation share one tested code path.
- New `hooks-status` recipe runs `uv run python -m fa.hygiene.hooks.status` for deterministic install verification.
- **Removed `git config core.hooksPath .git/hooks`** from `install-hooks` recipe. The setting was a no-op (`.git/hooks` is already the default), and `pre-commit install` explicitly refuses to work when `core.hooksPath` is set — even to the default — causing "Cowardly refusing to install hooks" errors. The comment in the justfile explains why this line must not be re-added.

### `src/fa/hygiene/hooks/_util.py` (new)

- Shared `resolve_repo_root()` and `scripts_dir()` helpers extracted from the duplicated copies in `install.py` and `status.py`. Single place to update if the workspace marker or script layout changes.

### `src/fa/hygiene/hooks/install.py`

- Extracted hook installation into `_install_one()` for clarity.
- Added symlink-to-copy fallback: when `os.symlink` raises `OSError` (Windows without Developer Mode), the installer falls back to `shutil.copy2`. This ensures `just install` works across all contributor environments while still preferring symlinks (so hooks stay current after `git pull`).
- **Critical fix:** After the copy fallback, chmod *both* the source and the target file to add the execute bit. Without this, the copied hook lands without execute permission on Windows and git silently skips it.
- Output now indicates installation method (`symlink` or `copy`) per hook.
- Now imports `resolve_repo_root` and `scripts_dir` from `_util.py` instead of defining them locally.

### `src/fa/hygiene/hooks/status.py` (new)

- `check_hooks()` verifies all three local hook seats: `pre-commit`, `prepare-commit-msg`, `commit-msg`.
- For custom hooks installed as copies, compares content against the shipped source to detect stale hooks (e.g., after a `git pull` that changed the hook scripts without re-running `just install-hooks`).
- Returns exit code 0 if all hooks are active, 1 if any are missing or stale.
- Invoked by `just hooks-status` and by `python -m fa.hygiene.hooks.status`.
- Now imports `resolve_repo_root` and `scripts_dir` from `_util.py` instead of defining them locally.

### `src/fa/hygiene/hooks/__init__.py`

- Replaced eager imports with `__getattr__`-based lazy imports to eliminate the `RuntimeWarning` that fired when running submodules via `python -m fa.hygiene.hooks.{install,status}`.
- Added `check_hooks` to the package's public API.

### `tests/test_hygiene_hooks_install.py`

- Added `test_install_hooks_is_idempotent_replacing_own_copies` — verifies re-install works when the first install produced copies (force=True path).
- Added `test_install_one_symlink_fallback_to_copy` — verifies the OSError fallback.
- Added `test_install_one_copy_fallback_target_is_executable` — verifies the chmod fix: copy-fallback target must have the execute bit set (git requirement).
- Added six `check_hooks` tests: all installed, missing pre-commit, missing custom hook, stale copy, no .git/hooks, non-workspace rejection.
- Added four lazy-import tests for `__init__.py`: `HOOK_NAMES`, `install_hooks`, `check_hooks`, and unknown-attribute error.
- Existing tests preserved and passing (22 total, all green, 91.57% coverage on hooks package).

### `knowledge/ci-guardrails-reference.md`

- Layer 0 section now includes the PR-handoff rule: `just check` must pass before a PR is opened for human review.
- Layer 3 section updated to reflect new `just install` bootstrap path and `just hooks-status` verification. Explicitly states that CI does not install hooks in the contributor's local clone.
- Layer 5 pre-commit entry now mentions `just hooks-status`.
- Date updated to 2026-06-28.

### `AGENTS.md`

- Development Workflow section now explicitly states: "After cloning, run `just install`." Without it, local commit hooks are not active — VS Code commits and manual git commits will bypass local autofix and validation, even though CI will still check the PR.
- Added PR-readiness gate: "Before opening a PR for review, run `just check` — this is the PR-readiness gate. Commit hooks provide fast local hygiene; `just check` provides the full gate that ensures the PR is review-ready."
- Mentions `just hooks-status` for verification.

### `knowledge/llms.txt`

- Updated hook installer entry to describe symlink-with-copy-fallback and the new `status.py` and `_util.py` modules.
- Updated justfile entry to mention `install` (mandatory after clone), `install-hooks`, and `hooks-status`.

## What this PR does NOT do

Per the reviewed plan's explicit recommendations, this PR does not:

- Replace `.pre-commit-config.yaml` hook logic with `just fix` (deferred — see separate implementation plan).
- Add `just check` or `just fix` to the pre-commit hook chain (deferred — see separate implementation plan).
- Consolidate hook types under the pre-commit framework (deferred decision per BACKLOG M-6 — see separate implementation plan).
- Modify deployment/container scripts (hook installation is a contributor concern, not a container runtime concern — see discussion in the implementation plan).

These are deliberate deferrals, not omissions. The reviewed plan concluded that bootstrap reliability and visibility must be fixed first; policy changes should follow only after the hook system is provably installed everywhere.

## Acceptance criteria

1. In a fresh clone, `just install` activates all local commit hooks in one command.
2. That command works in Windows PowerShell with uv-managed environments (copy fallback produces executable hooks).
3. `just hooks-status` deterministically confirms or denies hook activation.
4. `just install-hooks` delegates to the tested Python installer (one code path).
5. All 22 tests pass (91.57% coverage on hooks package).
6. Docs explicitly state `just install` is required after clone, and state the failure mode if skipped.
7. Docs explicitly state the PR-handoff rule: `just check` before review.
8. No RuntimeWarning on `python -m fa.hygiene.hooks.{install,status}`.

## Refs

- Reviewed plan: `hook-workflow-implementation-plan-reviewed.md` (§4 Workstream A, §8 PR-1)
- ADR-11-I6: bypassable-by-design hook seat, CI is authority
- ADR-10 I-1: single validator across git hook / middleware / `pr.prepare`
