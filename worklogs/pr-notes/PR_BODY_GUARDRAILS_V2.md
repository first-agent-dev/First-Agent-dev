CHORE: CI guardrails v2 — align gates with empirical LLM-agent failure modes

## Intent

`CHORE` (tooling/CI; one behavioural surface touched: `scripts/check_protected_paths.py` gains two annotation tiers, covered by new tests).

- goal_lens: Verify FA's CI/guardrail stack covers the empirically dominant LLM coding-agent failure modes; close cheap gaps only.
- project-axes advanced: A noise-reduction (agents stop hand-fixing style; one autofix loop), C goal_lens-advancement (failure-mode coverage closed for security/bloat/swallow/supply-chain).
- subtraction evaluated: YES — removes `.github/workflows/pylint.yml`, `.pylintrc-tests`, and ~95 lines of pylint config; net config -201/+81 across tooling files. Every addition is a rule-group in already-running tools (ruff, pylint, existing CI script) — zero new tools on the PR critical path.
- session-type: chore (CI/QA hardening)

## Why

Researched typical LLM coding-agent failure modes and cross-referenced against our gates
(full note: `knowledge/research/llm-agent-failure-modes-guardrails-2026-06.md`, house R-N format):

| Failure family (evidence) | Before this PR | After |
| :--- | :--- | :--- |
| Copy-paste duplication (GitClear: 8x duplicated-block growth 2024) | pylint duplicate-code, but **9.0 score gate silently absorbed findings** | binary gate: `disable=all` + `enable=[duplicate-code, cyclic-import]` + explicit `fail-on` |
| Function bloat / complexity creep (Sonar 2025) | no gate | `C901 max-complexity=15` ratchet; 4 baseline waivers |
| Test decay / verifier gaming (ImpossibleBench) | ADR-11 V4/V11 — already strong | unchanged; 2 follow-ups filed (see §Deferred) |
| OWASP-class security defects (Veracode: 45% of AI code) | Semgrep weekly-advisory only — **no per-PR SAST** | ruff `S` (bandit) blocking on src/; tests exempt |
| Silent error-swallowing | comment-only convention | `BLE`/`S110` blocking; intent now machine-checked |
| Hallucinated deps / slopsquatting (~20% of AI code) | `uv lock` (existence) + pip-audit (known CVEs) — **intent unverified** | dependency-manifest PR annotation tier |
| Gate bypass via suppression comments | unmonitored | `PGH` (no blanket `noqa`/`type: ignore`) + suppression-audit annotation tier |

## What changed

### Lint/CI policy (pyproject.toml, justfile, Makefile, workflows)

- **ruff `select` += `S`, `BLE`, `C90`, `PGH`** (each with an in-config rationale comment). `tests/**` exempt from `S` via per-file-ignores (`assert` IS the framework there). `mccabe.max-complexity = 15` — comment forbids raising; lower it as waivers retire.
- **pylint → gap-checks-only profile**: `disable=all`, `enable=[duplicate-code, cyclic-import]` (the two checks ruff lacks), `fail-on` both so the gate is binary and score-independent. Runs in `just lint` (~7s, src/ only). Deleted `pylint.yml` workflow and `.pylintrc-tests`.
- **`just fix` contract fixed**: `ruff check --fix-only .` → `ruff format .` → `ruff check .`. Previous `--fix`-first ordering exited non-zero on any unfixable finding, skipping the format step exactly when an agent hit a judgment rule.
- **Coverage gate moved out of pytest `addopts`** into `just test` / CI: bare `pytest tests/test_x.py` now works for single-file iteration; the 90% `fail_under` still blocks merges (full-suite runs).
- **Makefile parity**: `lock-check` added to `make check` (was justfile-only → Windows devs could pass locally, fail CI); `fix` target mirrored.
- `vulture` added to dev extras (the existing `just deadcode` recipe was a no-op without it); `uv.lock` regenerated.

### Waivers (26 sites, all pre-existing code)

Pattern: rationale comment **above**, short `# noqa: CODE` inline — because ruff's E501 exempts noqa-bearing lines, long inline rationales would live in a lint-free zone. Breakdown: 6×S101 (mypy narrowing asserts), 7×BLE001+1×S110 (documented observer/fail-closed boundaries), 4×C901 (baseline: `drive_session` 25, `load_contract` 18, `classify_command` 16, `_public_symbols` 16 — each annotated with its retirement path), 5×subprocess (fixed git argv / sandboxed `shell=True`), 2×S310, S104, S108. Two stale `pylint: disable-next=broad-exception-caught` directives removed.

### `scripts/check_protected_paths.py` — two annotation tiers (non-blocking, same enforcement-ceiling as TCB flags)

1. **Dependency manifests**: edits to `pyproject.toml`/`uv.lock` emit a `::warning` telling the reviewer to verify each package name (slopsquatting counter).
2. **Suppression audit**: newly **added** diff lines (`.py` only, corpus dirs excluded) containing `noqa` / `pylint: disable` / `pragma: no cover` / `type: ignore` are annotated — every blocking gate in this repo is comment-bypassable, so waiver issuance is now visible at review. Pre-existing waivers never re-flag.

+5 tests for both tiers (script coverage 97%).

### Docs / knowledge

- `AGENTS.md`: autofix-first rule (`just fix` after every edit) + judgment-rules section (S/BLE/C901/duplicate-code = fix the design; waive only when the pattern is the intended design).
- `knowledge/research/llm-agent-failure-modes-guardrails-2026-06.md` (new): failure-mode→guardrail cross-reference, 6 TAKEN / 2 DEFER, chain-of-custody to primary sources.
- `knowledge/llms.txt` §Tooling & CI rewritten; `HANDOFF.md` §Current state updated.

## Note for reviewer (expected CI annotations on this PR)

This PR itself triggers its own new flags — that is correct behaviour, not noise:
TCB-path warnings (it edits `check_protected_paths.py` and `authoring_rules/exports.py`),
2 dependency-manifest warnings (vulture added), and ~30 suppression warnings (the 26
documented waivers). All are review-once annotations; none block.

## Deferred (filed in the research note, not this PR)

- **R-6** — read-only `tests/**` for IMPLEMENT/FIX intents (ImpossibleBench's strongest anti-cheating lever; needs an ADR-6 intent-conditional sandbox amendment).
- **R-7** — mutmut survivor budget (promote weekly mutation run from `|| true` after ~4 baseline runs, mirroring the Semgrep promotion protocol).

## Verification

All on a clean checkout of `main` + this patch:

```text
ruff check .                  All checks passed (incl. S/BLE/C90/PGH)
ruff format --check .         clean
mypy                          strict, 137 files, no issues
pylint src/fa                 0 messages (gap profile, fail-on)
deptry src/                   clean
pytest (full + cov gate)      1083 passed (+8 vs main), coverage 90.42% >= 90
fa authoring-check            0 diagnostics
uv lock --check               OK
vulture src/ (advisory)       0 findings at confidence 90
workflow YAML                 4/4 parse
```

Adversarial probes run during review: injected cross-file duplicate → pylint exit 8 (caught); cyclic-import probe → exit 8; bare `# noqa` → PGH004 blocks; waived line's neighbour violation still fires; suppression scanner flags added markers only, ignores pre-existing ones.
