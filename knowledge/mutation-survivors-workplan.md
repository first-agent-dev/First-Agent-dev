# Mutation-survivors workplan — sandbox scope

> **Lifecycle.** This file is the active consumer of the weekly mutation-run
> stats (`tests.yml` → `mutants/mutmut-cicd-stats.json`). It is cleared out
> incrementally as survivors are killed and **DELETED when the table reaches
> zero** — its deletion is the trigger that flips
> `.github/workflows/tests.yml` to blocking (`continue-on-error: false`,
> gate `survived == 0`). Tracked in
> [`BACKLOG.md` §I-23](./BACKLOG.md#i-23--mutation-testing-promotion-to-blocking-gate).
>
> **Baseline.** First honest run after the mutmut-3.x repair
> (2026-06-12; the prior weekly workflow had been erroring instantly on a
> removed 2.x CLI flag since adoption — every earlier "green" run tested
> nothing): **633 mutants / 470 killed / 163 survived.**
>
> A *survivor* is a mutation (flipped comparison, off-by-one boundary,
> deleted branch, …) that the test suite did NOT catch — i.e. a real bug of
> that shape could merge today. Clearing a survivor means adding/sharpening
> an assertion, not editing the source under mutation.

## How to work this plan

```bash
just mutation               # run scope + list survivors + export stats
mutmut show <mutant-id>     # exact diff of one surviving mutation
mutmut tests-for-mutant <mutant-id>   # which tests ran against it
```

Per module: kill survivors by strengthening the four sandbox test files;
re-run `just mutation`; update the table row in the SAME PR that kills the
survivors. A module is done when `mutmut results` lists no survivors for it.
When ALL rows hit 0: delete this file, flip `tests.yml` per its header
comment, close BACKLOG I-23 with a «landed in PR #N» marker.

## Survivor table (baseline 2026-06-12)

Clearing order: smallest + most security-adjacent first.

| Order | Module | Baseline survivors | Remaining | Status |
| :--- | :--- | ---: | ---: | :--- |
| 1 | `fa/sandbox/path_containment.py` | 15 | 0 | cleared |
| 2 | `fa/sandbox/secret_paths.py` | 69 | 0 | cleared |
| 3 | `fa/sandbox/bash_gate.py` | 32 | 37 | open |
| 4 | `fa/sandbox/classifier.py` | 46 | 0 | cleared |
| 5 | `fa/sandbox/validators.py` | 70 | 0 | cleared |
| | **Total** | **232** | **37** | |

## Notes for the clearing sessions

- `path_containment` survivors cluster in `is_contained` (mutants 17-20+) —
  boundary-comparison flips the containment tests never pin. Start there:
  these guard the sandbox escape surface.
- Survivor counts are per-mutant, not per-line; one weak assertion commonly
  accounts for 5-10 survivors. Expect the table to drop in chunks.
- Do NOT chase 100 % by writing mutation-shaped assertions that mirror the
  implementation (that re-creates the «looks-thorough» problem mutation
  testing exists to catch). If a survivor is genuinely unobservable
  behaviour (e.g. a logging string), record it under an «accepted» row with
  one-line rationale instead of force-killing it; accepted rows count as
  cleared for the deletion trigger.

## Accepted Equivalent Mutants / Pragmas Ledger

| Module | Line / Function | Mutation Shape | Rationale |
| :--- | :--- | :--- | :--- |
| `secret_paths.py` | `_lexical_abs` (`part == ""` / `"."`) | Deleted branches | `pathlib.Path.parts` strips empty/dot components upon instantiation; branches are dead defensive guards. |
| `secret_paths.py` | `_within` (`path_str.rstrip("/")`) | Strip mutated | Redundant with `a.startswith(b + "/")` and identical behavior under `rstrip("XX/XX")`. |
| `secret_paths.py` | `command_reads_secret_path` (`norm.rstrip...`) | Branch return flipped | Line 147 right above already matches exact strings via `_within(norm, pref)`; line 153 is unreachable for exact matches. |
| `secret_paths.py` | `_safe_tokens` (`posix=True`) | Keyword stripped | Standard library `shlex.split()` defaults to `posix=True`. |
| `classifier.py` | `tokenize` (`posix=True`) | Keyword stripped | Threat-model audited: standard library `shlex.split()` defaults to `posix=True`. |
| `validators.py` | `_grants_world_write` (`digits = ...`) | `lstrip("0")` / `or "0"` mutated | Threat-model audited: leading zeros never alter the trailing digit `digits[-1]` evaluated for bit-2 (`0b010`). All-zero numeric mode `000` has bit-2 cleared (`0 & 2 == 0`). |
| `validators.py` | `_grants_world_write` (symbolic parsing) | Fallback / defensive checks | Threat-model audited: `op_idx < 0` vs `-2` when no operator `+-=` present both evaluate $<0$ (malformed deny); bare operator scope default `'a'` lowered matches `('o', 'a')`. |
| `validators.py` | `validate_git` (`subcommand`) | Default `""` mutated | Threat-model audited: when `non_flag` is empty (e.g. `git --version`), defaulting `subcommand` to `""` vs `"XXXX"` neither matches `"config"` nor `"push"`, allowing routine non-mutating command. |
| `validators.py` | `validate_command` (`validate_git` call) | `workspace_root=None` | Threat-model audited: `validate_git` begins with `del workspace_root`; parameter is deleted unread. |
