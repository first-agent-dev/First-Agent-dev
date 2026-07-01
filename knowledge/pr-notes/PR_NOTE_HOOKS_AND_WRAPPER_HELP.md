# PR: Agent-friendly hooks + host wrapper help

## Intent: CHORE
## Invariant: Safe mechanical cleanup is automated locally; GitHub CI remains the final authority.

## Problem

1. LLM-agent branches are usually landed as a few large commits. Safe mechanical failures
   (ruff autofix, formatting, whitespace, EOF, line endings, uv.lock drift) should be handled
   automatically instead of becoming manual review toil.
2. The custom pre-commit wrapper could re-stage hook edits, but it needed a stronger safety
   boundary for partially-staged files where `git add <path>` could also stage unrelated hunks.
3. Agents can still push a branch that fails the repo-native `uv run just check` gate.
4. `scripts/fa` listed host commands that did not all dispatch correctly (`clean-rebuild`) and
   swallowed `fa help <host-topic>` instead of showing detailed Russian operator help.

## Solution

| File | Change |
|------|--------|
| `.pre-commit-config.yaml` | Keep ruff autofix/format and add safe cleanup hooks: LF normalization plus shebang/executable consistency checks. |
| `src/fa/hygiene/hooks/pre-commit` | Run pre-commit through `uv`, auto-restage only modified staged files, refuse hook-modified partial-staging cases, optionally run `uv run just check` with `FA_HOOK_FULL_CHECK=1`. |
| `src/fa/hygiene/hooks/pre-push` | New hook: runs `uv run just check` before push; `FA_HOOK_SKIP_FULL_CHECK=1` is the explicit escape hatch. |
| `src/fa/hygiene/hooks/*` | Installer/status now manage all four hook seats: pre-commit, pre-push, prepare-commit-msg, commit-msg. |
| `src/fa/cli_help.py` | Extend the existing help registry with host-wrapper topics and renderers, keeping help text as the single source of truth. |
| `scripts/fa` | Shell wrapper now dispatches host commands but asks `python -m fa.cli_help` to render usage/topic help; it supports `fa help <topic>` and `fa <topic> --help/-h`, dispatches `clean-rebuild`, and delegates agent commands into the container. |
| `tests/` | Add regression coverage for hook auto-restage boundaries, pre-push behavior, wrapper syntax/help, and clean-rebuild dispatch. |
| `AGENTS.md`, `knowledge/ci-guardrails-reference.md`, `knowledge/llms.txt`, `justfile` | Document the hook policy and env vars. |

## Operator behavior

- Default commit path is fast and mechanical:
  - `ruff --fix`
  - `ruff format`
  - whitespace / EOF / LF cleanup
  - `uv-lock`
  - targeted auto-restage of already-staged files changed by hooks
- Commit-time full gate is opt-in:

  ```bash
  FA_HOOK_FULL_CHECK=1 git commit
  ```

- Push-time full gate is default:

  ```bash
  git push
  # runs: uv run just check
  ```

- Explicit push escape hatch:

  ```bash
  FA_HOOK_SKIP_FULL_CHECK=1 git push
  ```

## Help examples

```bash
fa help clean-rebuild
fa clean-rebuild --help
fa clean-rebuild -h
fa clean-rebuild -help  # compatibility alias
fa help update
fa update --help
fa help run             # delegated to Python CLI inside the agent container
fa run --help           # delegated to Python CLI inside the agent container
```

## Safety notes

- The hook only auto-restages paths that were already staged when the hook started.
- If hooks modify a file that was already partially staged, the hook refuses to auto-stage it and
  prints an explicit partial-staging message.
- Destructive deploy controls remain env-var based; `src/fa/cli_help.py` documents them but the wrapper does not invent
  new parsing like `--wipe-state=1`.

## Verification

Run locally:

```bash
bash -n scripts/fa
bash -n src/fa/hygiene/hooks/pre-commit
bash -n src/fa/hygiene/hooks/pre-push
uv run pytest tests/test_hygiene_hooks_install.py tests/test_deploy_scripts.py -q
uv run ruff check .
uv run ruff format --check .
uv run mypy
```
