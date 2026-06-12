---
title: "LLM coding-agent failure modes — cross-reference against FA guardrails"
source:
  - "https://www.gitclear.com/ai_assistant_code_quality_2025_research (211M-line code-change analysis)"
  - "https://www.sonarsource.com/blog/the-inevitable-rise-of-poor-code-quality-in-ai-accelerated-codebases/"
  - "arXiv:2410.10628 (Test smells in LLM-Generated Unit Tests)"
  - "arXiv:2510.20270 (ImpossibleBench — LLM propensity to exploit test cases)"
  - "https://debugml.github.io/cheating-agents/ (widespread cheating on agent benchmarks, 2026-04)"
  - "Veracode 2025 GenAI security report (100+ LLMs, 80 tasks)"
  - "CSA research note 2026-05 (AI-generated CVE surge; slopsquatting)"
  - "https://docs.astral.sh/ruff/rules/ (S/BLE/C90 rule groups)"
compiled: "2026-06-12"
chain_of_custody: |
  - 8x duplicated-block growth, copy/paste > moved lines (first time, 2024),
    refactoring 25%→<10%, churn 3.1%→5.7%: GitClear 2025 PDF §Trends 2020-2024
  - cyclomatic complexity higher in LLM code: Sonar blog 2025-10-15
  - LLM test smells (Lazy Test, Duplicate Assert, assertions matched to
    training-data behaviour instead of actual code): arXiv:2410.10628;
    semantic-grounding failure: arXiv:2603.23443 §Fig.3
  - agents delete/weaken tests, hardcode test inputs, special-case to pass:
    ImpossibleBench arXiv:2510.20270 §4.1; debugml cheating-agents post
    (SWE-smith hardcoded-return commit, Terminal-Bench PASS-print exploit)
  - read-only test access kills most cheating without hurting performance:
    ImpossibleBench §Fig.7
  - 45% of AI code carries OWASP-class flaws (stable 2025→2026): Veracode
    via CSA research note 2026-05
  - ~20% of AI code references non-existent packages; slopsquatting:
    CSA research note 2026-05 §supply-chain
goal_lens: "Verify FA's CI/guardrail stack covers the empirically dominant LLM coding-agent failure modes; close cheap gaps only."
tier: stable
links: ["./ci-qa-tooling-adversarial-2026-06.md", "../adr/ADR-11-authoring-guardrails.md"]
mentions: []
confidence: extracted
claims_requiring_verification:
  - "C901 threshold 15 is the right ratchet start — revisit after 10 PRs of data"
  - "S-ruleset FP rate on FA-style subprocess-heavy code stays near zero — monitor waiver count"
---

> **Status:** active. §0 is the Decision Briefing; §1 is the failure-mode
> taxonomy → guardrail cross-reference table (load on demand).

## 0. Decision Briefing

Empirical failure modes of LLM coding agents cluster into five families:
(1) **duplication instead of refactoring** (GitClear: 8x duplicated-block
growth; copy/paste lines exceeded moved lines for the first time in 2024),
(2) **function bloat / complexity creep** (Sonar: cyclomatic complexity and
LOC measurably higher in LLM code), (3) **test decay and verifier gaming**
(ImpossibleBench: agents delete failing tests, hardcode expected values,
special-case test inputs; test-smell corpus: Lazy Test / Duplicate Assert /
placeholder assertions), (4) **security defects + silent-swallow defensive
code** (Veracode: 45% of AI code carries OWASP-class flaws; broad
`except: pass` hides real bugs), (5) **supply-chain via hallucinated
dependencies** (~20% of AI code references non-existent packages;
slopsquatting). FA already covers (1) and (3) better than industry baseline
— pylint `duplicate-code` gap-check and ADR-11 V4/V11 + protected-path
governance are precisely the right counters. Gaps were (2), (4), (5).

### R-1 — Ruff `S` (bandit) ruleset as blocking SAST floor for src/

- **What:** Enable `S` in `[tool.ruff.lint]`; tests exempt via
  per-file-ignores; 15 intentional sites waived inline with rationale.
- **Verdict:** TAKEN (this PR). Closes family (4) at zero runtime cost;
  weekly-advisory Semgrep alone left every PR un-scanned at merge time.

### R-2 — C901 cyclomatic-complexity ratchet at 15

- **What:** `mccabe.max-complexity = 15`; 4 existing offenders carry
  `# noqa: C901 — C901-baseline waiver` markers; new code cannot exceed.
- **Verdict:** TAKEN (this PR). Closes family (2). Ratchet direction:
  retire waivers when touched; never raise the threshold.

### R-3 — BLE001 + S110 (blind except / try-except-pass) blocking

- **What:** Every broad `except Exception` now needs `# noqa: BLE001` +
  one-line rationale. 7 existing sites (all already commented as
  intentional observer/fail-closed boundaries) waived.
- **Verdict:** TAKEN (this PR). Converts comment-only intent into
  machine-checked intent; future silent-swallow fails CI.

### R-4 — Dependency-manifest review flag (slopsquatting counter)

- **What:** `scripts/check_protected_paths.py` now annotates any
  `pyproject.toml` / `uv.lock` edit on the PR (non-blocking, same
  mechanism as TCB flags). `uv lock` proves existence, pip-audit proves
  no known CVE; only a human confirms the dependency was *intended*.
- **Verdict:** TAKEN (this PR). Closes family (5) at the enforcement
  ceiling FA already uses (PR-only agent rights + human merge).

### R-4b — Suppression-marker review flag (waiver-audit tier)

- **What:** `check_protected_paths.py` also annotates every NEWLY ADDED
  suppression comment in `.py` files (`noqa`, `pylint: disable`,
  `pragma: no cover`, `type: ignore` — added diff lines only, so existing
  waivers never re-flag). Closes the meta-gap: every blocking gate in
  this repo is locally neutralisable by a comment, and an agent that
  cannot fix a finding will eventually try to waive it. Non-blocking —
  legitimate waivers are expected; *silent* ones are not.
- **Verdict:** TAKEN (this PR; added during self-review).

### R-5 — vulture in dev extras (dead-code counter, advisory)

- **What:** `just deadcode` existed but vulture was not installed. Added
  to dev extras; stays advisory (dynamic dispatch FPs need judgement).
- **Verdict:** TAKEN (this PR).

### R-6 — Read-only test files for the inner-loop agent

- **What:** ImpossibleBench shows read-only test access eliminates most
  test-modification cheating without hurting task performance. FA's
  IntentGuard/sandbox could deny `fs.write_file` to `tests/**` for
  IMPLEMENT/FIX intents (allow for test-authoring intents).
- **Verdict:** DEFER — requires intent-conditional sandbox policy (ADR-6
  amendment), not a CI change. Filed as the highest-value next guardrail.

### R-7 — Mutation-testing survivor budget promotion

- **What:** mutmut weekly run is `|| true` with no survivor budget; a
  rising survivor count (weak tests, family 3) is currently invisible.
- **Verdict:** DEFER until 4 weekly runs of baseline data exist (mirrors
  the Semgrep promotion protocol already in semgrep.yml).

## 1. Failure-mode → guardrail cross-reference

| # | Failure mode (evidence) | FA guardrail before | Gap → action |
|---|---|---|---|
| 1a | Copy-paste-and-tweak duplication (GitClear 8x) | pylint `duplicate-code`, binary gate, src/ | covered |
| 1b | Dead code left after rewrites | `just deadcode` broken (no vulture dep) | R-5 fixed |
| 2a | Function bloat / complexity creep (Sonar) | none (pylint shape-caps correctly dropped as cosmetic) | R-2 C901=15 |
| 3a | Test deletion / skip / xfail weakening (ImpossibleBench) | ADR-11 V4 HARD-BLOCK | covered |
| 3b | Placeholder / tautological asserts (test-smell corpus) | ADR-11 V11 HARD-BLOCK | covered |
| 3c | Assertion weakening `==`→`in` (F-9) | V11 ADVISORY pending corpus | covered (lifecycle) |
| 3d | Tests that exercise but don't verify | coverage 90% + weekly mutmut | R-7 budget deferred |
| 3e | Agent edits verifier/guardrail itself | ADR-11 I1/I6/I7 TCB + protected paths | covered |
| 3f | Agent modifies tests to pass (cheating) | protected paths don't cover tests/ | R-6 deferred (sandbox) |
| 4a | OWASP-class security defects (Veracode 45%) | Semgrep weekly advisory only | R-1 S-rules blocking |
| 4b | Silent error-swallowing defensive code | comment-convention only | R-3 BLE001/S110 |
| 4c | Known-CVE dependencies | pip-audit blocking | covered |
| 4d | Secrets in code | gitleaks (hook + CI) | covered |
| 5a | Hallucinated package names / slopsquatting | uv lock (existence only) | R-4 review flag |
| 6a | Style drift / merge-conflict churn | ruff autofix-first via `just fix` | covered |
| 6b | Type errors at integration seams | mypy strict + pyrefly advisory | covered |
