# CI & guardrail mechanisms — reference (as of 2026-06-28)

> **Purpose.** One-page inventory of every quality / safety mechanism in the
> repo, with its seat (where it runs), gate class (blocking / advisory /
> annotation), and bypass surface. Audience: humans reviewing agent PRs and
> agents loading guardrail context. Update this file in the same PR that
> changes any mechanism listed here.
>
> **Threat model recap (ADR-11):** the LLM author is an untrusted compiler;
> it can edit any file including the guardrails, and will route around a
> blocking gate if a cheaper path exists. Every mechanism below is judged by
> who can edit it and what watches that edit.
>
> **Deployment context:** agent runs on Ubuntu 24 in Docker (`Dockerfile.fa`)
> with a dedicated non-CODEOWNER GitHub account (planned); PR-only rights,
> human merges. CI runs from the PR branch.

## Layer 0 — deterministic local gates (`just check`)

Authoritative per local-first architecture; CI re-runs the same commands.
**PR-handoff rule:** `just check` must pass before a PR is opened for
human review. This is distinct from commit-time hygiene (which is fast
and bypassable per ADR-11-I6) — it is the authoritative local gate.

| Mechanism | Command seat | What it catches | Gate |
| :--- | :--- | :--- | :--- |
| ruff lint `B,BLE,C4,C90,E,F,I,N,PGH,PYI,RUF,S,UP,W` | `just lint` → `ruff check .` | bugs (B/F), blind-except swallow (BLE), complexity >15 ratchet (C901, 4 baseline waivers), security floor / bandit (S; tests exempt), blanket-suppression guard (PGH003/004), style+imports (auto-fixed via `just fix`) | blocking |
| ruff format | `just lint` → `--check` | canonical formatting (zero agent context cost via `just fix` = `--fix-only` → `format` → `check`) | blocking |
| mypy `--strict` | `just typecheck` | type errors at integration seams (138 files) | blocking |
| pylint gap-profile | `just lint` → `pylint src/fa` | ONLY `duplicate-code` (R0801, cross-file copy-paste — #1 LLM smell) + `cyclic-import` (R0401); `disable=all` + explicit `fail-on` (binary gate, score-independent) | blocking |
| deptry | `just lint` | unused / missing / misplaced dependencies | blocking |
| pytest + coverage | `just test` (cov flags here, NOT in addopts — bare `pytest` is iteration-friendly) | regressions; branch coverage `fail_under = 90` | blocking |
| `uv lock --locked` | `just lock-check` | pyproject/lock drift; non-existent (hallucinated) packages cannot resolve | blocking |
| `fa authoring-check` | `just authoring-check` | ADR-11 Level-0/1 rules (below) | blocking (HARD-BLOCK exits 1) |
| vulture | `just deadcode` | dead code left by rewrite-instead-of-refactor | advisory (manual; high FP on dynamic dispatch) |
| mutmut 3.x | `just mutation` | tests that execute code without verifying it (survivors = bugs the suite would miss); sandbox scope, baseline 163/633 | advisory until `knowledge/mutation-survivors-workplan.md` is deleted → then blocking at survivors=0 (BACKLOG I-23) |

## Layer 1 — ADR-11 authoring kernel (`fa authoring-check`)

Frozen stdlib-only Level-0 TCB dispatching allow-listed Level-1 AST rules;
deterministic, hash-bound (`kernel_hash` / `rule_pack_hash` / `snapshot_id`),
fail-closed (rule crash → HARD-BLOCK diagnostic).

| Rule | Code namespace | Catches |
| :--- | :--- | :--- |
| V2 exports-completeness | `FA-AUTHORING-V2-*` | public symbol missing from `__all__` (cross-file omission) |
| V4 test semantic decay | `FA-AUTHORING-V4-*` | `pytest.skip` (call + decorator), non-strict `xfail`, focus markers — **in all import shapes** incl. `from pytest import skip`, `import pytest as pt`, renamed imports, bare `mark.<X>` (I-13 alias-map closure; local same-name def shadows conservatively) |
| V11 placeholder asserts | `FA-AUTHORING-V11-*` | tautological (`assert True`, `x == x`) and self-contradictory assertions |

## Layer 2 — runtime hook pipeline (inside `fa run`)

`BEFORE_TOOL_EXEC` middleware chain (ADR-7/8): SandboxHook (workspace path
containment + bash classify/deny) → LoopGuard → Rate/Lockfile/Auth blockers →
**IntentGuard** → AuditHook (events.jsonl) → SecretGuard (leak prevention;
gitleaks mirrors at commit/CI) → CostGuardian (budget). Role-aware tool
registries: planner/eval get read-only tools; only coder can write.

**IntentGuard** re-runs the M-6 classifier over the projected staged set per
mutating tool call; requires a trusted same-session `pr.prepare` draft; and
enforces **existing-test protection** (R-6, ImpossibleBench counter):

- `D`/`R`/`C` on `tests/**.py` → denied under every intent. No escape field.
- `M` on `tests/**.py` under a FIX-shaped diff → denied unless declared in
  the draft's `TEST-EDITS: <path> — <reason>` block.
- Keyed on **classifier** intent — the typed `INTENT:` D-5 override cannot
  disarm it (the draft is agent-authored; security invariant pinned by test).
- Two-seat closure: `OPAQUE_EXEC` evasions (`git rm`, `python -c` writes)
  surface as real staged `D` rows at the next `git add`/`commit`
  (INDEX_WRITE validation against the live snapshot).

## Layer 3 — git-hook seat (M-6)

`prepare-commit-msg` / `commit-msg` invoke the SAME
`fa.hygiene.pr_intent` functions as IntentGuard (ADR-10 I-1: one
classifier + one validator + one test-protection rule, multiple seats).
This seat is intentionally **narrower** than the runtime seat: ordinary
manual commits with **no PR-intent metadata headers at all** are allowed
through, while any explicit metadata block (`INTENT:`, `INVARIANT:`,
`CLASS:`, `TEST-EDITS:`, FIX-only clauses) is validated strictly.
When strict validation applies, it checks INTENT/CLASS/INVARIANT shape,
FIX anti-shallow-fix clauses (DOF/MECHANISM + resolving citation), and
`validate_test_edits`. Installed by `just install`
(→ `uv sync --extra dev` + `install-hooks` + `hooks-status`);
all three hooks are scripts from `src/fa/hygiene/hooks/` installed via
our tested Python installer. The `pre-commit` hook invokes
`uv run pre-commit run` so it works on Windows/PowerShell where the
framework's own generated hook cannot find the executable, and if hooks
auto-fix already-staged files it re-stages only that staged subset and
retries once. Snapshot tests pin hook constants to the skill
§Output format / §Test-edit declaration so the two views cannot drift.
**Bypassable locally** (`--no-verify`, by design per ADR-11-I6) — CI is
the authority, this seat is fast feedback.

Hook activation can be verified at any time with `just hooks-status`,
which checks all three seats (pre-commit, prepare-commit-msg, commit-msg)
and flags missing, stale, or non-executable hooks. Without running
`just install` in a fresh clone, local commit hooks are not active; CI
does not install hooks in the contributor's local clone — it only
re-runs checks on the PR branch.

## Layer 4 — GitHub CI (PR branch; agent is NOT a codeowner)

| Workflow | Jobs | Gate |
| :--- | :--- | :--- |
| `advisory.yml` | sanity-check (`uv lock --check` + full `just check`), pip-audit (known CVEs), gitleaks (full-history secrets; version-pinned to the pre-commit hook) | blocking |
| `authoring-guardrails.yml` | `fa authoring-check` (always-run, NO `paths:` filter — ADR-11-I6) + `check_protected_paths.py` | check blocking; flags non-blocking |
| `pylint` | (deleted — runs inside `just lint`) | — |
| `tests.yml` | weekly mutation run; stats → job summary + artifact | advisory (promotion trigger above) |
| `semgrep.yml` | weekly OWASP/python SAST | advisory |
| `pyrefly` (in advisory.yml) | second type-checker signal | advisory |

**`check_protected_paths.py` — three annotation tiers** (exit 0; loud
`::warning` annotations the human merge-gate acts on):

1. **TCB tier** — edits to `authoring_tcb.py`, `authoring_rules/**`,
   `authoring-guardrails.yml`, `CODEOWNERS`, the script itself
   (realpath-resolved, symlink-bypass safe). Self-protecting: editing the
   script flags the edit.
2. **Dependency tier** — any `pyproject.toml`/`uv.lock` edit → reviewer
   verifies each package name (slopsquatting counter; `uv lock` proves
   existence, pip-audit proves no known CVE, only a human proves intent).
3. **Suppression tier** — newly ADDED `noqa` / `pylint: disable` /
   `pragma: no cover` / `type: ignore` lines in `.py` diffs (corpus dirs
   excluded; pre-existing waivers never re-flag). Every blocking gate is
   comment-bypassable; this makes waiver issuance visible at review.

## Layer 5 — process & enforcement ceiling

- **Agent rights:** open PRs only; cannot merge; not a CODEOWNER. Branch
  protection + required human review at merge is the ultimate gate — CI
  detects, the human decides (ADR-11 enforcement-ceiling).
- **CODEOWNERS** routes TCB-path review (recommended, not load-bearing).
- **Waiver discipline** (AGENTS.md §Judgment rules): S/BLE/C901/
  duplicate-code findings mean fix-the-design; `# noqa: CODE` allowed only
  for intended-design patterns, rationale comment above, surfaced by the
  suppression tier.
- **pre-commit hooks** (ruff, gitleaks, hygiene basics, uv-lock) —
  convenience seat, bypassable, never the authority. Installed by
  `just install` as a script that calls `uv run pre-commit run`;
  verify with `just hooks-status`.

## Known residual gaps (accepted, tracked)

| Gap | Why accepted | Tracking |
| :--- | :--- | :--- |
| Same-PR edits to `advisory.yml` / `justfile` / `Makefile` / pyproject tool-config can weaken gates; only `authoring-guardrails.yml` is TCB-protected | Enforcement-ceiling: human reviews every merge; diff of CI/config files is small and visible. Optional hardening: extend `_TCB_PREFIXES` with `.github/workflows/` | candidate for next guardrail PR |
| `# pylint: disable=duplicate-code` in ONE copy kills pair detection | Suppression tier flags the added disable line for review | PR #28 design note |
| V4 alias-map: pytest import + same-name decoy def in one file evades | Conservative shadowing rule avoids FPs; cost-of-bypass already ≈ commenting the rule out (ADR-11 §12.4 bar is raising cost, not impossibility) | fp-corpus loop (ADR-11 PR-4) |
| `--no-verify` skips git hooks | By design (ADR-11-I6): CI re-validates | — |
| Mutation gate not yet blocking | First honest baseline only measured 2026-06-12 (prior runs were silently dead) | I-23 + workplan |
