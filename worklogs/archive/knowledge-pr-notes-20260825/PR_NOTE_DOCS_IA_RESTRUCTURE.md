INTENT: CHORE
INVARIANT: n/a

## Summary

Documentation information-architecture restructure: move operator docs out of the
cluttered repo root into a task-scoped home, de-overlap the two deployment guides,
add a human "start here" front door, and make doc-pruning safe by replacing the
"never delete" rule with a "no dangling links" rule — enforced by a new offline
link checker. No source or runtime behaviour changes.

Delivered as **two commits** for review:

1. `docs: relocate operator guides + PR notes; prune dead docs (move-only)` —
   pure `git mv` / `git rm`, zero content edits (shows as clean renames under
   `--find-renames`).
2. `docs: de-overlap install/operations, add indexes + link-checker, allow
   pruning` — content rewrites, link fixes, policy change, tooling.

## Motivation

The repo root held 11 `.md` files; only 3 are true front-matter
(`README`/`AGENTS`/`HANDOFF`). The rest — an operator guide and a pile of PR
artifacts — buried the "how do I run this" answer. The two deployment guides
(`SETUP_AIO.md`, `DOCKER_USAGE_GUIDE.md`) also overlapped on ~6 topics, a drift
hazard (it had already produced one stale backup-credentials section).

## Moves / prunes (commit 1)

| From (root / knowledge) | To |
|---|---|
| `DOCKER_USAGE_GUIDE.md` | `knowledge/instructions/02-operations.md` |
| `knowledge/SETUP_AIO.md` | `knowledge/instructions/01-install.md` |
| `PR_BODY*.md`, `PR_NOTE_*.md` | `knowledge/pr-notes/` |
| `Inner_Loop_..._20260608_092335.md` | `knowledge/codemaps/inner-loop-hooks-runtime-pipeline.md` |
| `FINAL_DELIVERABLE.md` | **pruned** (unreferenced; superseded by `HANDOFF.md` + the runtime PR note) |

Root `.md` is now just `README.md`, `AGENTS.md`, `HANDOFF.md`.

## Content + structure (commit 2)

- **De-overlap by lifecycle.** `01-install.md` owns the strictly one-time
  bring-up (BIOS → OS → Docker → Tailscale → deploy key → first container).
  `02-operations.md` owns everything recurring (update, backup, service control,
  recovery, troubleshooting). Where they overlapped, each topic is assigned to
  its owner and the other doc links across. SSH hardening stays single-sourced in
  `scripts/ssh-tailscale/README.md`.
  - `01-install.md`: **full Russian rewrite** (was English) to match
    `02-operations.md`; recurring sections trimmed to forward-pointers.
  - `02-operations.md` §3 "Первый запуск" shrunk from a ~130-line duplicate of
    the install flow to a quick-start that links to `01-install.md`.
- **Front door.** New `knowledge/instructions/README.md` — a thin Russian
  "start here" that routes by task (install vs operate vs harden) and lists the
  two planned docs (`03-runtime-usage.md`, `04-modules.md`) as coming-soon rather
  than creating empty files (AGENTS rule: every write target needs a consumer).
  Linked from the top of `README.md`.
- **PR-notes index** (`knowledge/pr-notes/README.md`) doubles as a dated
  changelog of merged PRs.

## Policy change (the rule you asked to amend)

- `knowledge/README.md` "Never silently overwrite" → **"Prune deliberately;
  never leave a dangling link."** Deleting/replacing is allowed (PRs are
  human-reviewed); the binding rule is **link integrity in the same PR**, not
  file permanence.
- `knowledge/MAINTENANCE.md`: archiving step 3 relaxed ("re-path or remove the
  row"); new **§When moving or pruning a doc** checklist (grep old path → fix
  `llms.txt`/`HANDOFF`/in-doc links/code comments → verify no dangling links).

## Link integrity (every reference fixed in-PR)

- Re-pathed: `knowledge/llms.txt` (BY-DEMAND rows + new TASK ROUTING entries),
  `scripts/ssh-tailscale/README.md`, code comments in `scripts/setup-fa-desktop.sh`
  and `tests/test_deploy_scripts.py`, the `HANDOFF.md` Landmarks table (active
  links to the moved `SETUP_AIO.md` / `PR_NOTE_LOOP_FOUNDATION.md`).
- Depth-shifted links **inside** the moved docs fixed: 9 in `01-install.md`
  (`knowledge/` → `knowledge/instructions/`), 1 in `02-operations.md` (root →
  `knowledge/instructions/`).
- Dated *history prose* in `HANDOFF.md` "As of" entries left as written (history,
  not navigation).

## Tooling (high-ROI extra)

- New `scripts/check_doc_links.py` — offline, dependency-free internal-link
  checker. Default: relative file-link existence (the "moved doc" bug class);
  opt-in `--anchors` for heading fragments (off by default to avoid
  slug-algorithm noise). A `_LEGACY_SKIP` list excludes doc trees with
  pre-existing debt so the gate is green now while catching **new** breakage.
- Wired as a **pre-commit** hook (judges only changed `.md` files) and a **CI**
  gate via `tests/test_doc_links.py` (whole-repo file links + strict anchors on
  `knowledge/instructions/` + a negative test).
- Note: first tried the `tcort/markdown-link-check` pre-commit hook, but its
  v3.13.x CLI mishandles `--config` (exits 1, checks 0 links); the local Python
  checker is offline-deterministic and matches the repo's existing
  `check_protected_paths.py` pattern.

## Validation

- `markdownlint-cli` v0.41.0 (repo pin): **no new findings** on any edited doc;
  new files clean.
- `python scripts/check_doc_links.py` (whole repo): green; `--anchors` clean on
  all `knowledge/instructions/` docs; negative test confirms it catches breakage.
- `pytest tests/test_doc_links.py tests/test_deploy_scripts.py
  tests/test_fa_update_script.py` → all green (shellcheck cases skip when the
  binary is absent). `test_doc_links.py` covers file/anchor/title/inline-code/
  legacy-skip behaviour + a negative test.
- `ruff check` + `ruff format --check` on new Python: clean.
- Move commit verified as pure renames under `git show --find-renames`.

> Sandbox caveat: `pre-commit`/`uv`/`docker` not installed here; the hook config
> is YAML-validated and the checker is exercised directly + via pytest. Run
> `pre-commit run --all-files` once on a dev box to confirm hook wiring.

## Review fixes applied during final pass

A self-review pass before merge caught and fixed several issues in this PR's own
additions:

1. **Hook would block commits that merely touch a legacy doc.** `_LEGACY_SKIP`
   was only honoured in whole-repo discovery, not for explicitly-passed files —
   but the pre-commit hook passes filenames. Editing e.g.
   `knowledge/trace/exploration_log.md` would have failed the commit on
   pre-existing breakage. Fixed: explicit files are filtered against
   `_LEGACY_SKIP` too (override with `--all`). Pinned by a test.
2. **Link checker missed broken links carrying a `"title"`.** The target regex
   stopped at the first space, so `[x](./missing.md "t")` slipped through.
   Hardened the regex to parse optional titles and `<...>` angle brackets;
   added tests.
3. **Link checker false-positived on example link syntax in `` `backticks` ``.**
   The new `MAINTENANCE.md` legitimately shows `` `](../X)` `` as an example;
   the checker flagged it. Now inline code spans are neutralised before scanning
   (mirrors the existing fenced-block skip). This let `MAINTENANCE.md` leave
   `_LEGACY_SKIP` and be actively guarded.
4. **Stale tool reference in my own docs.** `MAINTENANCE.md` step 6 said "the
   repo's `markdown-link-check` pre-commit hook" — a tool this PR rejected.
   Corrected to `scripts/check_doc_links.py` / the `check-doc-links` hook.

## Decisions taken (per your answers)

Full RU rewrite of install; prune `FINAL_DELIVERABLE.md`; codemap → `knowledge/codemaps/`;
add the link checker this PR; two-commit split.

## Not in this PR (follow-ups)

- `03-runtime-usage.md` and `04-modules.md` (not yet written).
- Shrinking `_LEGACY_SKIP` by fixing the ~117 pre-existing broken links/anchors
  (notably the repo-wide `AGENTS.md#pr-checklist` anchor referenced from 27
  files — its target heading does not exist in `AGENTS.md`).
