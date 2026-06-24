# PR: Ops verbs + trace auto-commit + workspace isolation research

## Intent: CHORE
## Invariant: Zero code logic changes; operator convenience + documentation.

## Problem

1. Operator has no `fa update` command — must remember `scripts/fa-update.sh`.
2. `fa help` (no dash) shows Python argparse error instead of help text.
3. Session trace artifacts (`knowledge/trace/`) dirty the worktree,
   blocking `fa-update.sh` before every update.
4. No documentation for the 3-layer observability architecture in llms.txt.
5. Workspace isolation architecture decision needed for next phase.

## Solution

| File | Change |
|------|--------|
| `scripts/fa` | Add `update`, `commit-traces`, `help` (no-dash) verbs |
| `scripts/fa-update.sh` | Auto-commit `knowledge/trace/` before dirty-tree check |
| `.gitignore` | `knowledge/trace/gotchas.md` + `codebase_map.json` |
| `HANDOFF.md` | §Current state + workspace isolation as §Next #1 |
| `knowledge/llms.txt` | Output+Analytics section + codemap + research entries |
| `knowledge/research/workspace-isolation-research.md` | NEW — 5 patterns surveyed, recommends Pattern 2 |

## Subtraction check

- **Removing what?** None — ops verbs are missing functionality, not new abstractions.
- **Lost if omitted?** Operator friction on every update; no research foundation for workspace isolation.
- **OSS precedent?** Docker AI Sandbox, Open SWE, SWE-Next all use isolated workspaces.
