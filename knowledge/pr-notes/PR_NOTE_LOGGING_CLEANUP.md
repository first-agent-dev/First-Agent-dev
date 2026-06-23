# PR: Logging module cleanup — dedup + dead code + docs

**Intent:** REFACTOR  
**Invariant:** Zero behaviour change; eliminates copy-paste duplication and dead code.

## Problem

Post `fa stats` + `fa run --output-mode` landing, three minor issues:

1. **`_fmt_tokens()` duplicated** — identical 6-line function copy-pasted
   in `output.py` and `stats.py`. Any future formatting change requires
   editing two files.
2. **`stats` missing from `fa --help`** — wrapper delegates it correctly
   (wildcard passthrough), but operators running `fa --help` don't see it.
3. **Dead `LOGGER` in `recovery_observers.py`** — `import logging` +
   `LOGGER = logging.getLogger(...)` but zero `.debug()/.info()/.warning()`
   calls anywhere in the file.
4. **`BashCommand` missing from `stats.py` `__all__`** — authoring-check
   `FA-AUTHORING-V2-EXPORTS-COMPLETENESS` flagged it.

## Solution

| File | Change |
|------|--------|
| `src/fa/formatting.py` | **NEW** — shared `fmt_tokens()` (21 lines) |
| `src/fa/output.py` | Replace local `_fmt_tokens` with `from fa.formatting import fmt_tokens as _fmt_tokens` |
| `src/fa/stats.py` | Same import swap + add `BashCommand` to `__all__` |
| `src/fa/inner_loop/hooks/recovery_observers.py` | Remove `import logging` + `LOGGER` (dead code) |
| `scripts/fa` | Add `stats` line to help text |

## Subtraction check

- **Removing what?** Two copy-pasted `_fmt_tokens` defs → one canonical source.
  Dead `LOGGER` import → removed.
- **Lost if omitted?** Divergence risk on formatting changes; operator
  confusion on available commands; dead code in security-sensitive hooks path.
- **OSS precedent?** Standard DRY refactor — aider/litellm/openai-agents
  all extract shared formatters.

## Verification

- 1284 tests pass (excl. `test_deploy_scripts.py` executable-bit check — 
  pre-existing sandbox artifact, not related).
- `fa authoring-check` clean (0 diagnostics).
- All imports verified: `fa.formatting`, `fa.output`, `fa.stats`,
  `fa.inner_loop.hooks.recovery_observers`.
