# Mutation-survivors workplan — sandbox scope

> **Lifecycle.** This file is the active consumer of the weekly mutation-run
> stats (`tests.yml` → `mutants/mutmut-cicd-stats.json`). It is cleared out
> incrementally as survivors are killed and **DELETED when the table reaches
> zero** — its deletion is the trigger that flips
> `.github/workflows/tests.yml` to blocking (`continue-on-error: false`,
> gate `survived == 0`). Tracked in
> [`BACKLOG.md` §I-23](../worklogs/BACKLOG.md#i-23--mutation-testing-promotion-to-blocking-gate).
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
| `slice_verification.py` | `_tail` (`raw.decode("utf-8", ...)`) | Encoding arg dropped / re-cased to `"UTF-8"` | Audited: `bytes.decode()` already defaults to UTF-8, and codec *names* are case-insensitive (unlike error-handler names, where the `"IGNORE"` mutant IS killed). Both shapes are behaviourally identical. |
| `slice_verification.py` | `_build_env` (`env.get("PATH", os.defpath)`) | Default arg dropped / set to `None` | Audited: the fallback fires only when `PATH` is absent from the scrubbed environment, but `PATH` is on the `bash_env.py` allowlist and always inherited. The *key* mutants (`'path'`, `'XXPATHXX'`) reach the fallback and ARE killed by the differential PATH oracle. |
| `slice_verification.py` | `_deadline_result` (`stderr_tail=` message) | String wrapped in `XX...XX` | Audited: operator-facing prose only. The text still names the cause ("deadline"), no machine consumer parses it, and pinning the exact sentence would over-fit a diagnostic that is meant to be reworded. |
| `slice_verification.py` | `_run_one` (`subprocess.run(...)` kwargs) | `check=False` / `text=False` dropped or set to `None` | Audited: both are the stdlib defaults, written explicitly because this call site must *stay* non-raising and byte-mode. Deleting them cannot change behaviour; keeping them is the readable form. |
| `slice_verification.py` | `run_commands` (`time.monotonic() >= deadline`) | `>=` weakened to `>` | Audited: the two differ only when the monotonic clock reads *exactly* the deadline float. No test can reliably manufacture that equality, and either way at most one extra command starts. |
| `slice_verification.py` | `validate_kill_directives` (`contract_line.get(cid, 0)`) | Fallback `0` mutated to `1` | Audited: the fallback fires only for a contract I01 declares that this module's locator cannot find. Since the locator was corrected to mirror `plan_ids._CONTRACT_ENTRY_RE` — optional class bracket included — no such contract exists, and `test_every_contract_in_a_real_plan_is_locatable` pins the agreement over both real plans. `0` is kept as the honest "unknown line" sentinel; `1` would point the operator at the first line of the file. |
| `slice_verification.py` | `_owner_at` | `site_line > line` -> `>= line` | Equivalent, provably. The two grammars are mutually exclusive at line level: a contract entry matches `^\s+CT\d+…` and a directive matches `^\s*kill:`, both anchored at line start. A declaration line can therefore never also be a directive line, so `_owner_at` is never queried with `line` equal to one of its own `site_line`s, and the boundary the mutant moves is unreachable. Pinning it would need a fixture that is not a legal plan. |
| `slice_verification.py` | `parse_kill_directives` (section-relative conversion) | `line - start_line + 1` -> `+ 2` | Equivalent, by the same invariant. Shifting every site by one changes the attributed owner only if some declaration sits exactly on the queried directive's line — the same unreachable case as above. Worth noting the two survivors share one root cause: the arithmetic has a coordinate system, and the only mutants it admits are ones the grammar forbids. |
| `plan_ids.py` | `_contract_declaration_sites`, `_line_at` | `count("\n", 0, …)` -> `count("\n", None, …)` | Equivalent: `str.count` treats a `None` start as 0, so the call is unchanged. A language-level identity, not a coverage gap. |
| `plan_ids.py` | `_contract_declaration_sites` | `count("\n", 0, …)` -> `count("\n", 1, …)` | Equivalent on reachable input. The count differs only when the section's byte 0 is a newline, and a section always begins at its own `##` heading (`_slice_spans`), so byte 0 is `#`. Pinning it would require a fixture that cannot be produced by the extractor. |
| `slice_verification.py` | `_prepend_pythonpath` | `env.get("PYTHONPATH", "")` -> `get(…, None)` / no default | Equivalent. The result feeds `if inherited:`, and `None` and `""` are both falsy, so every reachable path produces the same `PYTHONPATH`. Pinning it would mean asserting which falsy value an intermediate local holds, which is implementation-mirroring. |
