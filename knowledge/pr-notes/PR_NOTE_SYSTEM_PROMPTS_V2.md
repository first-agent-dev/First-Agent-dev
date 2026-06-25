# PR: System prompts rewrite — full architect + structured coder/eval

## Intent: IMPLEMENT
## Invariant: All three role prompts (planner, coder, eval) rewritten for production agent sessions.

## Problem

System prompts in `prompt.py` were minimal stubs from early development:
- **Planner:** 93-line stripped version of `architect-fa.md`, missing
  operating priorities, bounded recon budgets, decide-vs-block protocol,
  pre-output self-check, Delta Plan recovery, worked example.
- **Coder:** 43 lines — no project context, no code standards, no error
  handling guidance, no quality checklist. 5 negative instructions.
- **Eval:** 33 lines — flat verification list, no phased protocol, no
  code quality review, no structured verdict format. 2 negative instructions.

## Solution

### Planner (93 → 461 lines)

Restored the full `architect-fa.md` v2.1 prompt verbatim, with appended
tool usage section. Includes all decision protocols the strong planner
model (GLM-5.2 / Kimi-2.7 class, 1M context) benefits from:
- Operating priorities (8 items, ordered)
- Bounded recon with per-class budgets (TRIVIAL ≤4, STANDARD ≤8, LARGE ≤16)
- Decide vs block protocol (MUST block / MAY block / default)
- Step writing rules (7 rules for coder-executable steps)
- Acceptance taxonomy (mechanical predicates only)
- Pre-output self-check (11 items)
- Delta Plan for failure recovery
- Worked example (pagination fix)

### Coder (43 → 123 lines)

Rewritten with concrete, actionable sections:
- **Project context:** Python 3.13, mypy strict, `just fix`/`just check`,
  src/tests layout — agent knows the stack from turn 1.
- **Execution protocol:** 5-step numbered workflow (understand plan →
  declare intent → implement steps → regression → final message).
- **Writing code:** Type hints, `__all__`, tests, `require_string` pattern
  from the codebase, `just fix` after edits.
- **Working with files:** `fs.write_file` replaces entire file (read first),
  `start_line`/`end_line` for large files, sandbox limits.
- **When things go wrong:** Classified by failure type (simple fix, test
  failure, plan-level issue, harness deny).
- **Quality checklist:** 5-item self-check before final message.

### Eval (33 → 144 lines)

Rewritten with 3-phase verification protocol:
- **Phase 1 — Per-step:** existence check → acceptance predicate → scope check.
- **Phase 2 — Integration:** focused test → regression (`just check`) →
  cross-reference between components.
- **Phase 3 — Beyond plan:** security scan (for sandbox/secrets paths),
  documentation gaps, dead code.
- **Structured verdict:** Markdown table per step + MERGE / FIX REQUIRED /
  REPLAN recommendation.

### Negative instructions: 9 → 0

All "DO NOT" / "Never" instructions across coder and eval converted to
positive framing. Planner retains negative-form hard rules (strong model
handles them well; they're inherited from the reviewed architect-fa.md).

## Files changed

| File | Change |
|------|--------|
| `src/fa/inner_loop/prompt.py` | All three prompt constants rewritten |
| `tests/test_prompt.py` | Assertions updated for new opening text |
| `tests/test_cli.py` | pr.prepare assertion updated for new wording |

## Subtraction check

- **Removing what?** Stub prompts → production prompts. No new modules or deps.
- **Lost if omitted?** Agents operate without project context, code standards,
  or structured verification protocol. Mid-tier models produce significantly
  worse output without structured instructions.
- **OSS precedent?** Open SWE, SWE-agent, Claude Code all use role-specific
  system prompts with project context and tool guidance.
