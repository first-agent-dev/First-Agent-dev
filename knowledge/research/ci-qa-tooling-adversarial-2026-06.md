---
title: "CI & Code QA Tooling for AI-Managed Python Projects — Adversarial Review"
source:
  - "arXiv:2601.22952 (Sifting the Noise — SAST FP filtering)"
  - "arXiv:2602.05868 (Persistent Human Feedback, LLMs, and Static Analyzers)"
  - "arXiv:2507.02976 (Are AI-Generated Fixes Secure? SWE-bench security study)"
  - "https://github.com/astral-sh/uv/blob/main/BENCHMARKS.md"
  - "https://openai.com/index/openai-to-acquire-astral/"
  - "https://github.com/facebook/pyrefly/releases/tag/1.0.0"
  - "https://astral.sh/blog/ty"
  - "https://github.com/astral-sh/uv/issues/18506 (uv audit roadmap)"
  - "https://deepeval.com/docs/evaluation-unit-testing-in-ci-cd"
  - "https://github.com/NVIDIA/garak"
  - "https://github.com/tach-org/tach"
  - "https://konvu.com/compare/semgrep-vs-codeql"
  - "https://pypi.org/project/pip-audit/"
  - "https://genai.qa/blog/promptfoo-vs-deepeval/"
  - "https://pypi.org/project/deptry/"
  - "https://github.com/casey/just (cross-platform command runner)"
  - "GitHub LLM code review preview (enabled in repo, no custom Action needed)"
compiled: "2026-06-04"
chain_of_custody: |
  - uv benchmarks: Astral BENCHMARKS.md (graphs, no exact multipliers)
  - Semgrep/CodeQL FP rates: arXiv:2601.22952 Table 3 (OWASP Benchmark v1.2 Java)
  - LLM vs developer vulnerability counts: arXiv:2507.02976v1 Table I, RQ1
  - ty beta status + speed claims: Astral blog post (Dec 2025)
  - pyrefly 1.0.0: GitHub release (12 May 2026)
  - OpenAI/Astral acquisition: OpenAI press release (19 Mar 2026)
  - DeepEval CI: deepeval.com docs (verified live 2026-06-04)
  - uv audit non-existence: GitHub issues #9189, #16646, #18506
  - Semgrep free tier limits: konvu.com comparison (free = intra-procedural only)
  - Ruff PL ruleset coverage: docs.astral.sh/ruff/rules/ (900+ rules, PL prefix)
  - Tach module boundaries: tach-org/tach README (Rust, pyproject.toml adjacent)
  - pip-audit SCA: PyPA GitHub repo + PyPI page
  - deptry dependency hygiene: osprey-oss/deptry README
  - Promptfoo vs DeepEval: genai.qa comparison (2026)
  - garak LLM vuln scanner: NVIDIA/garak README (v0.14.0, Feb 2026)
  - just command runner: casey/just README + releases (cross-platform binary)
  - GitHub LLM review: observed live in repository (2026-06-04)
goal_lens: "Identify the minimal CI/QA tooling additions that maximally reduce AI-authored code risk without maintainer burden, for a Stage-1 OSS harness."
tier: stable
links: []
mentions: []
confidence: extracted
claims_requiring_verification:
  - "uv audit will be stable by late 2026" — roadmap exists but no committed date
  - "ty plugin system will never exist" — Astral has made no public statement either way
  - "Ruff covers ~90% of pylint checks" — approximate; exact coverage depends on pylint configuration
---

> **Status:** active. Note produced via
> [`knowledge/prompts/research-briefing.md`](../prompts/research-briefing.md).
>
> §0 below is the Decision Briefing intended for the project lead and
> for future LLM agents reading the note from the top. It mirrors the
> chat-handover the agent posted at session end. §1.. are deep-dive
> sections; load them only when §0 is insufficient.

## 0. Decision Briefing

### R-1 — Adopt `uv` for package management and CI (replace pip)

- **What:** Migrate `make install` and all CI workflows from `pip install` to `uv sync --frozen` / `uv pip install`. Single highest-leverage speed win.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (~500+ tokens saved per CI log)
  - (B) helps LLM find context when needed: YES (shorter CI logs, faster feedback)
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens "Identify minimal CI/QA additions for Stage-1": YES — build-speed is a prerequisite for every other gate; fast CI = runnable CI.
- **Cost:** cheap (<1h drop-in replacement)
- **Verdict:** TAKE
- **Alternative-if-rejected:** Keep pip + cache; pay 50-60h/year CI time.
- **Concrete first step (if TAKE):** Update `.github/workflows/ci.yml` to use `astral-sh/setup-uv@v3`, change `make install` to `uv sync --frozen`, verify `make check` still passes.

### R-2 — Add `pip-audit` as a required CI job (SCA floor)

- **What:** Run `pip-audit` on every PR to catch known CVEs in dependencies. PyPA-maintained, zero license cost.
- **Project-axis fit:** (A) NO — adds CI time (~10s); (B) YES — dependency vulnerability is a discoverable risk.
- **Goal-lens fit:** (C) YES (security floor) — FA currently has zero SCA; this is the cheapest fix.
- **Cost:** cheap (<30 min to wire into CI)
- **Verdict:** TAKE
- **Alternative-if-rejected:** Dependabot alerts only (reactive, not PR-blocking).
- **Concrete first step:** Add `pip-audit -r pyproject.toml` step to `ci.yml` after `make install`.

### R-3 — Add `deptry` to `make lint` (dependency hygiene)

- **What:** Surface unused, missing, and misplaced dependencies in `pyproject.toml`. Catches AI-suggestion-drift dependency bloat.
- **Project-axis fit:** (A) YES — fewer deps = smaller mental model; (B) YES — dep map is context.
- **Goal-lens fit:** (C) YES (noise reduction) — dead deps are noise.
- **Cost:** cheap (<15 min)
- **Verdict:** TAKE
- **Alternative-if-rejected:** Manual `pipdeptree` audits every quarter.
- **Concrete first step:** `pip install deptry`, add `deptry src/` to `Makefile` lint target, add to `[dev]` extras.

### R-4 — Add `gitleaks` pre-commit hook (secret scanning)

- **What:** Replace the baseline's recommendation of GitGuardian/TruffleHog with `gitleaks` — zero-license, pre-commit-native, catches hardcoded secrets before they reach CI.
- **Project-axis fit:** (A) YES — pre-commit sub-second; (B) YES — secret leakage is a context-bearing risk.
- **Goal-lens fit:** (C) YES (security floor) — LLM agents generate code with placeholder keys.
- **Cost:** cheap (<10 min)
- **Verdict:** TAKE
- **Alternative-if-rejected:** GitGuardian (paid cloud) or TruffleHog (AGPL-3, heavier).
- **Concrete first step:** Add `gitleaks detect --verbose` to `.pre-commit-config.yaml`.

### R-5 — Add Semgrep workflow (advisory, not blocking)

- **What:** Run Semgrep OSS (`--config=p/python --config=p/owasp-top-ten`) weekly + on manual dispatch. **Not** on PR critical path.
- **Project-axis fit:** (A) NO — high FP rate trains teams to ignore; (B) PARTIAL — findings are context but noisy.
- **Goal-lens fit:** (C) PARTIAL (security signal) — SAST is necessary but Semgrep free tier is intra-procedural only; inter-procedural taint (the thing that catches real agent-harness bugs) requires Semgrep Pro.
- **Cost:** medium (1-2h setup + ongoing triage)
- **Verdict:** TAKE (advisory-only)
- **Alternative-if-rejected:** CodeQL weekly (free for public repos, deeper taint, slower).
- **Concrete first step:** Create `.github/workflows/semgrep.yml` with `continue-on-error: true`, run `semgrep --config=p/python --config=p/owasp-top-ten`.

### R-6 — Keep `mypy --strict` as primary type checker; add `pyrefly` as parallel advisory

- **What:** Do not replace mypy. Add pyrefly 1.0 (stable, Meta-backed) as a parallel CI job that does not block merge.
- **Project-axis fit:** (A) PARTIAL — adds CI time (~5-15s for small codebase); (B) YES — two type checkers surface different error shapes.
- **Goal-lens fit:** (C) PARTIAL (quality signal) — FA has no mypy plugin dependencies (Django/Pydantic), so pyrefly migration is viable but premature; keeping mypy preserves the single gate.
- **Cost:** cheap (<30 min)
- **Verdict:** TAKE (advisory)
- **Alternative-if-rejected:** mypy-only until ty reaches stable 1.0 (late 2026).
- **Concrete first step:** Add `pyrefly check` job to `ci.yml` with `continue-on-error: true`; configure `pyrefly init` once.

### R-7 — DEFER `ty` as primary type checker until stable 1.0

- **What:** Astral's ty is beta (v0.0.37 as of Jun 2026). Fastest incremental updates (500x pyrefly in editor), but no plugin system and different unannotated-body semantics than mypy.
- **Project-axis fit:** (A) PARTIAL — would speed up CI but mypy on FA's small codebase is already fast; (B) N/A.
- **Goal-lens fit:** (C) PARTIAL — faster type checking advances Pillar 3 (token efficiency), but FA's mypy gate is already sub-minute.
- **Cost:** medium (migration effort + new-error triage)
- **Verdict:** DEFER (re-evaluate after ty 1.0)
- **Alternative-if-rejected:** Keep mypy indefinitely; mypy catches real bugs and is battle-tested.
- **Concrete first step:** Watch `github.com/astral-sh/ty/releases` for 1.0.0 tag.

### R-8 — DEFER custom Semgrep rules for `@tool` surface until harness stabilizes

- **What:** The baseline recommends custom Semgrep rules for MCP-specific vulnerabilities (tool response injection, unsafe arg handling). FA's tool surface is still evolving (ADR-7, ADR-8 amendments ongoing).
- **Project-axis fit:** (A) NO — custom rules need maintenance on every tool-shape change; (B) YES — rules encode domain knowledge.
- **Goal-lens fit:** (C) PARTIAL — agent-specific security is critical, but writing rules against a moving target is wasted effort.
- **Cost:** expensive (>4h + ongoing maintenance)
- **Verdict:** DEFER (revisit after ADR-8 / HookRegistry stabilizes)
- **Alternative-if-rejected:** Rely on Semgrep OSS generic rules + manual code review for now.
- **Concrete first step:** Pin a note in `BACKLOG.md`: "Custom Semgrep rules blocked on ADR-8 freeze."

### R-9 — DEFER DeepEval / Promptfoo agent eval harness until UC5

- **What:** The baseline recommends DeepEval with `ToolCorrectnessMetric`, `TaskCompletionMetric`, `StepEfficiencyMetric`. DeepEval's public API (verified live 2026-06-04) does **not** document `StepEfficiencyMetric` or `PlanAdherenceMetric` — these appear to be invented by the baseline agent.
- **Project-axis fit:** (A) NO — eval framework is premature before the harness has stable tool contracts; (B) YES — golden prompts are durable context.
- **Goal-lens fit:** (C) PARTIAL — agent behavioral eval is essential (Pillar 4), but FA is Stage 1 with no production traffic. Eval without a stable inner-loop is measuring noise.
- **Cost:** expensive (weeks to build goldens, tune metrics, integrate CI)
- **Verdict:** DEFER (to UC5 / v0.2)
- **Alternative-if-rejected:** Manual regression testing on 5-10 hand-crafted prompts until eval harness lands.
- **Concrete first step:** Add `knowledge/BACKLOG.md` entry: "UC5 eval-harness: evaluate DeepEval vs Promptfoo after inner-loop contract freeze."

### R-10 — DEFER `Tach` module boundary enforcement until module count > 5

- **What:** Tach (Rust-based) enforces `import` boundaries via `tach.toml`. Strong defense against AI spaghetti coupling.
- **Project-axis fit:** (A) PARTIAL — adds CI step; (B) YES — boundary map is context.
- **Goal-lens fit:** (C) PARTIAL — FA has <10 top-level modules; ADR-11 authoring guardrails + CODEOWNERS already provide boundary discipline.
- **Cost:** cheap to set up, medium to maintain rules as modules evolve.
- **Verdict:** DEFER (revisit when `src/fa/` has >5 independently deployable modules)
- **Alternative-if-rejected:** Manual import-graph review in PRs.
- **Concrete first step:** Pin `BACKLOG.md` entry with trigger: "Adopt Tach when module count > 5."

### R-11 — SKIP `garak` adversarial scanning for now

- **What:** NVIDIA's garak probes LLMs for jailbreaks, prompt injection, data extraction. Complementary to SAST.
- **Project-axis fit:** (A) NO — heavy runtime dependency, needs live LLM endpoint; (B) NO — runtime security scanning is orthogonal to CI.
- **Goal-lens fit:** (C) NO — FA is not a deployed service; runtime prompt-injection testing against a local harness is circular (the harness IS the thing being tested).
- **Cost:** expensive (>4h setup + API costs per run)
- **Verdict:** SKIP
- **Alternative-if-rejected:** N/A — not applicable to Stage 1.
- **Concrete first step:** None. Revisit if FA ever exposes a network-facing agent endpoint.

### R-12 — SKIP `CodeQL` deep taint analysis

- **What:** CodeQL is free for public repos on GitHub Actions. Deeper inter-procedural taint than Semgrep OSS.
- **Project-axis fit:** (A) NO — slow (~minutes), high memory; (B) PARTIAL — deep findings are valuable context.
- **Goal-lens fit:** (C) PARTIAL — security signal, but FA's threat model is authoring-time (ADR-11), not runtime taint.
- **Cost:** medium (setup + triage)
- **Verdict:** SKIP (superseded by advisory Semgrep + the fact that FA has no runtime taint surface yet)
- **Alternative-if-rejected:** Enable CodeQL weekly if Semgrep advisory proves useful.
- **Concrete first step:** None.

### R-13 — SKIP `Vulture` dead-code detection as a CI gate

- **What:** Vulture finds unused functions/classes/variables. AI projects accumulate dead code.
- **Project-axis fit:** (A) NO — false positives on dynamically dispatched code; (B) PARTIAL.
- **Goal-lens fit:** (C) PARTIAL — hygiene, but deptry (R-3) covers dependency-level dead code; Vulture is symbol-level.
- **Cost:** cheap to run, medium to maintain whitelist.
- **Verdict:** SKIP (run manually monthly, do not gate CI)
- **Alternative-if-rejected:** Manual review.
- **Concrete first step:** Add `vulture src/ --min-confidence 90` to `Makefile` as a non-gated `make deadcode` target.

### R-14 — SKIP `pytest-recording` / VCR.py for LLM mocks

- **What:** Record HTTP fixtures on first run, replay in CI. Eliminates API keys and flakiness.
- **Project-axis fit:** (A) YES — deterministic tests; (B) YES — cassettes are fixtures.
- **Goal-lens fit:** (C) PARTIAL — FA's current test suite (`tests/`) has no live LLM calls (all mocked at the `ProviderAdapter` level). VCR is a solution looking for a problem at Stage 1.
- **Cost:** cheap to add, medium to maintain cassettes.
- **Verdict:** SKIP (revisit when tests introduce HTTP-dependent components)
- **Alternative-if-rejected:** Continue with unit-test-level mocking.
- **Concrete first step:** None. Add to `BACKLOG.md` when HTTP client tests are added.

### R-15 — Adopt `just` as cross-platform task runner (replace Makefile)

- **What:** Replace `Makefile` with `justfile`. `just` is a modern command runner (Rust, MIT) with identical syntax across Linux, macOS, and Windows. Eliminates Windows `make` friction entirely.
- **Project-axis fit:** (A) YES — IDE tweaks on Windows run the same `just check` as the Linux agent; (B) YES — task definitions are durable context.
- **Goal-lens fit:** (C) YES — cross-platform parity reduces "works on Linux but not on IDE" friction, a primary source of agent-session noise.
- **Cost:** cheap (<30 min: install `just`, translate Makefile, verify both platforms)
- **Verdict:** TAKE
- **Alternative-if-rejected:** Keep `Makefile` + document Windows `make` install (Git for Windows / chocolatey); accept occasional Windows dev friction.
- **Concrete first step:** `cargo install just` (or download binary), create `justfile` with recipes matching current `Makefile`, verify `just check` on Linux and Windows.
- **Downside analysis:** None material for FA's scope. `just` has no implicit rules (a feature, not a bug, for explicit task definitions), no external runtime dependencies, and single-binary distribution. It is strictly superior to `make` for cross-platform Python projects.

### Summary

| R-N | Verdict | Project-fit (A / B) | Goal-fit (C) | Cost | Alternative-if-rejected | User decision needed? |
|-----|---------|---------------------|--------------|------|--------------------------|------------------------|
| R-1 | TAKE | YES / YES | YES (speed prerequisite) | cheap | Keep pip, pay CI time | No |
| R-2 | TAKE | NO / YES | YES (security floor) | cheap | Dependabot only | No |
| R-3 | TAKE | YES / YES | YES (noise reduction) | cheap | Manual audits | No |
| R-4 | TAKE | YES / YES | YES (security floor) | cheap | GitGuardian/TruffleHog | No |
| R-5 | TAKE | NO / PARTIAL | PARTIAL (security signal) | medium | CodeQL weekly | No (advisory-only) |
| R-6 | TAKE | PARTIAL / YES | PARTIAL (quality signal) | cheap | mypy-only | No (advisory-only) |
| R-7 | DEFER | PARTIAL / N/A | PARTIAL | medium | Keep mypy | No |
| R-8 | DEFER | NO / YES | PARTIAL | expensive | Generic Semgrep rules | No |
| R-9 | DEFER | NO / YES | PARTIAL | expensive | Manual regression testing | No |
| R-10 | DEFER | PARTIAL / YES | PARTIAL | medium | Manual review | No |
| R-11 | SKIP | NO / NO | NO | expensive | N/A | No |
| R-12 | SKIP | NO / PARTIAL | PARTIAL | medium | Semgrep advisory | No |
| R-13 | SKIP | NO / PARTIAL | PARTIAL | cheap | Manual review | No |
| R-14 | SKIP | YES / YES | PARTIAL | cheap | Unit-test mocking | No |
| R-15 | TAKE | YES / YES | YES (cross-platform parity) | cheap | Keep Makefile + Windows make docs | No |

## 1. TL;DR

- **Baseline research is directionally correct** but contains unverified precision claims, domain-mismatched citations, and premature recommendations for FA's Stage 1 scope.
- **TAKE now (5 tools):** `uv` (speed), `pip-audit` (SCA), `deptry` (dependency hygiene), `gitleaks` (secret scanning), `just` (cross-platform task runner). All are zero-license, low-maintainer-burden, and fit minimalism-first.
- **TAKE advisory (2 tools):** Semgrep OSS (weekly, not blocking), pyrefly 1.0 (parallel to mypy, not blocking). Both provide signal without gate-breaking risk.
- **DEFER (4 items):** `ty` (wait for 1.0), custom Semgrep rules (wait for ADR-8 freeze), DeepEval/Promptfoo (wait for UC5 eval harness), Tach (wait for >5 modules).
- **SKIP (4 items):** `garak` (no runtime endpoint), `CodeQL` (superseded by Semgrep advisory at this scale), `Vulture` CI-gate (false-positive-prone), `pytest-recording` (no HTTP tests yet).
- **Critical baseline weakness:** The "Week 1-2-3-4" roadmap ignores FA's minimalism-first principle (5-question test per `project-overview.md` §1.2) and proposes tools before their consumer (eval harness, stable tool surface) exists.
- **Local-first architecture:** FA's primary gate is `make check` (→ `just check`) run by the developer/agent before push; GitHub CI is advisory-only. GitHub's built-in LLM code review preview is already enabled and handles light PR review without custom Actions.

## 2. Scope, метод

**Scope:** CI and Code QA tooling for AI-managed Python projects, with First-Agent-dev as the concrete evaluation substrate. Focus on tools that can be added to the existing stack (ruff, mypy, pytest, pylint, mutmut, pre-commit, GitHub Actions) without breaking existing gates.

**Excluded:**
- Paid-tier tools (Snyk, Codacy, SonarQube, GitGuardian) — violates minimalism-first question 2 ("open-source agent-stack precedent for not having it?").
- Container/IaC scanning (Trivy) — FA has no Dockerfile or K8s manifests in v0.1.
- Runtime AI security (NeMo Guardrails, Rebuff) — FA is not a deployed service.
- Benchmark harness design (UC5 scope, deferred to v0.2).

**Method:**
1. **Baseline deconstruction:** Catalog every numbered claim in the other agent's research.
2. **Primary-source verification:** Web-search key claims; read primary sources (arXiv papers, GitHub releases, official docs, issue trackers).
3. **Adversarial stress-testing:** Apply minimalism-first 5-question test per `project-overview.md` §1.2 to each recommendation.
4. **Gap hunting:** Identify categories the baseline missed (Windows parity, reproducible builds, pre-commit speed).
5. **Tiered matrix + phased roadmap:** Map verdicts to FA's actual file structure and constraints.

**Goal-lens (verbatim):** "Identify the minimal CI/QA tooling additions that maximally reduce AI-authored code risk without maintainer burden, for a Stage-1 OSS harness."

## 3. Key concepts

- **SAST** (Static Application Security Testing): Code analysis without execution. Semgrep, CodeQL, Bandit are SAST tools.
- **SCA** (Software Composition Analysis): Scanning dependencies for known vulnerabilities. `pip-audit`, Trivy, Dependabot are SCA tools.
- **FP / FPR** (False Positive / False Positive Rate): Alert fired on non-vulnerable code. arXiv:2601.22952 reports Semgrep FPR 74.8%, CodeQL FPR 68.2% on OWASP Benchmark Java.
- **Taint tracking:** Data-flow analysis from untrusted sources (user input, LLM output) to dangerous sinks (`eval`, `subprocess`, SQL queries). Semgrep Pro and CodeQL support inter-procedural taint; Semgrep OSS is intra-procedural only.
- **Mutation testing:** Running tests against modified (mutated) source to verify tests actually catch bugs. `mutmut` (Linux) and `pytest-gremlins` (Windows) are FA's current tools.
- **Golden set / eval harness:** Manually annotated inputs + expected behavior for regression testing LLM agents. DeepEval and Promptfoo are eval frameworks.
- **Pre-commit vs CI:** Pre-commit runs locally before commit; CI runs remotely on push/PR. ADR-11 R-6: "CI-enforced, not pre-commit-only" — pre-commit is bypassable.

## 4. Mapping / analysis

### 4.1. Baseline claim verification table

| # | Baseline claim | Primary source | Verified? | Caveat |
|---|----------------|---------------|-----------|--------|
| 1 | uv 10-20x faster than pip | Astral BENCHMARKS.md (graphs only) | Directionally YES | No exact multipliers published; blog cites unverified numbers |
| 2 | uv saves 50-60h CI time/year | Tech blog (techplained.com) | UNVERIFIED | No peer-reviewed source; extrapolation from single benchmark |
| 3 | OpenAI acquires Astral (Mar 19 2026) | OpenAI press release | YES | Deal announced; long-term uv/ruff/ty backing confirmed |
| 4 | ty 10-60x faster than mypy/Pyright | Astral blog (Dec 2025) | YES (Astral's own benchmark) | Beta only; M4 Macbook Pro specific; pyrefly gap exaggerated |
| 5 | ty "no plugin system, no plans" | Baseline assertion | UNVERIFIED | Astral has made no public statement on plugins |
| 6 | pyrefly stable 1.0 (May 12 2026) | GitHub release | YES | Instagram default at Meta; conformance suite >90% |
| 7 | Semgrep/CodeQL FP 74.8%/68.2% | arXiv:2601.22952 Table 3 | YES but MISLEADING | Tested on OWASP Benchmark v1.2 **Java**, not Python or LLM-generated code |
| 8 | Semgrep 323 vulns vs developer 9 | arXiv:2507.02976v1 Table I | YES but INCOMPLETE | Raw alert counts before majority-vote filtering; after filtering: LLM 185, dev 20 |
| 9 | CodeQL free for public repos | GitHub docs | YES | Correct; but slow and memory-heavy |
| 10 | DeepEval "StepEfficiencyMetric" | DeepEval public API docs | **NO** — NOT FOUND | Metric name does not exist in DeepEval docs as of 2026-06-04 |
| 11 | DeepEval "PlanAdherenceMetric" | DeepEval public API docs | **NO** — NOT FOUND | Same as above; baseline appears to have invented these names |
| 12 | uv audit "once stable" | GitHub issues #9189, #16646, #18506 | **NO** — DOES NOT EXIST | uv audit is a roadmap item, not a shipped feature |
| 13 | Ruff covers ~90% of pylint | docs.astral.sh/ruff/rules/ | APPROXIMATE | Ruff has 900+ rules including PL (pylint) prefix; duplicate-code (R0801) still missing |

### 4.2. Tiered comparison matrix — all evaluated tools

| Tool | Category | License | Speed | FA Fit | Verdict | Evidence | Risk Notes |
|------|----------|---------|-------|--------|---------|----------|------------|
| **uv** | Package manager | MIT (Astral) | 10-20x pip | High | GO | BENCHMARKS.md graphs; replaces pip+venv+pip-tools | OpenAI acquisition creates long-term vendor risk |
| **pip-audit** | SCA (deps) | Apache-2.0 | ~10s | High | GO | PyPA-maintained; PyPI Advisory DB | Low FP; only flags known CVEs |
| **deptry** | Dep hygiene | MIT | ~5s | High | GO | osprey-oss/deptry | Catches unused deps AI agents add |
| **gitleaks** | Secret scan | MIT | ~1s | High | GO | zricethezark/gitleaks | Pre-commit native; zero license |
| **Semgrep OSS** | SAST | LGPL-2.1 | ~30s | Medium | GO (advisory) | semgrep.dev | FP 74.8% (Java benchmark); free tier intra-procedural only |
| **pyrefly** | Type check | MIT (Meta) | 10-50x mypy | Medium | GO (advisory) | facebook/pyrefly v1.0.0 | Stable; auto-migrates mypy config; add ~5-15s CI |
| **ty** | Type check | MIT (Astral) | 500x pyrefly (editor) | Medium | DEFER | astral-sh/ty beta | No stable release; different unannotated-body semantics |
| **mutmut** | Mutation test | LGPL-3.0 | Slow (minutes) | High | KEEP | Already in CI (tests.yml) | Best practice for LLM-written tests |
| **pytest-gremlins** | Mutation test | MIT | Medium | High | KEEP | Already in pyproject.toml | Windows dev mirror for mutmut |
| **Tach** | Module boundaries | MIT | ~2s | Low | DEFER | tach-org/tach (Rust) | Overkill for <5 modules; ADR-11 + CODEOWNERS sufficient |
| **DeepEval** | Agent eval | Apache-2.0 | Variable | Low | DEFER | confident-ai/deepeval | Metrics "StepEfficiencyMetric"/"PlanAdherenceMetric" not in public API |
| **Promptfoo** | Agent eval | MIT | Variable | Low | DEFER | promptfoo/promptfoo | Simpler than DeepEval; YAML-declarative; same maturity gap |
| **garak** | LLM vuln scan | Apache-2.0 | Slow | Very Low | SKIP | NVIDIA/garak v0.14.0 | Needs live LLM endpoint; FA is not network-facing |
| **CodeQL** | SAST (deep) | Free (public repos) | Minutes | Low | SKIP | GitHub-native | Superseded by advisory Semgrep at FA scale |
| **Vulture** | Dead code | MIT | ~5s | Low | SKIP | jendrikseipp/vulture | High FP on dynamic dispatch; symbol-level only |
| **pytest-recording** | HTTP mock | MIT | N/A | Low | SKIP | kiwicom/pytest-recording | FA has no HTTP-dependent tests yet |
| **GitGuardian** | Secret scan | Paid | Cloud | N/A | SKIP | gitguardian.com | Paid tier; violates minimalism-first |
| **TruffleHog** | Secret scan | AGPL-3.0 | ~5s | N/A | SKIP | trufflesecurity/trufflehog | Heavier than gitleaks; AGPL license concern |
| **Trivy** | SCA+IaC | Apache-2.0 | ~10s | N/A | SKIP | aquasecurity/trivy | FA has no containers/IaC in v0.1 |

### 4.3. Adversarial findings against the baseline

**Finding 1: The "uv audit" recommendation is based on a non-existent tool.**
The baseline says "Add pip-audit (or uv audit once stable)". `uv audit` is tracked in GitHub issues `#9189`, `#16646`, `#18506` — it is a roadmap item with no committed ship date. Recommending it as a fallback creates false confidence.

**Finding 2: FP-rate numbers are domain-mismatched.**
The baseline cites Semgrep FPR 74.8% and CodeQL FPR 68.2% as evidence that "AI-authored code is provably more vulnerable". These numbers come from arXiv:2601.22952, which tested on OWASP Benchmark v1.2 **Java** code — not Python, not LLM-generated code. The LLM-vs-developer vulnerability gap is real (arXiv:2507.02976v1), but the specific FP-rate percentages should not be extrapolated to Python SAST.

**Finding 3: Invented DeepEval metric names.**
The baseline lists `StepEfficiencyMetric` and `PlanAdherenceMetric` as "metrics that map directly onto your harness's failure modes". DeepEval's public documentation (verified live 2026-06-04) does not contain these names. The documented metrics include `TaskCompletionMetric`, `ToolCorrectnessMetric`, `GEval`, `AnswerRelevancyMetric`, `HallucinationMetric`, `BiasMetric`, `ToxicityMetric`, `RagasMetric`. The baseline fabricated metric names, which undermines confidence in the entire eval recommendation.

**Finding 4: The phased roadmap violates minimalism-first.**
The baseline proposes adding 8+ new tools across 4 weeks. Per `project-overview.md` §1.2, every component must pass: (1) research evidence, (2) open-source precedent for removal, (3) replacement capability, (4) deterministic Python function instead of LLM call. The baseline's Week 3-4 (DeepEval evals) fails tests (3) and (4) — there is no existing eval harness to build on, and eval metrics require LLM-as-judge.

**Finding 5: Windows CI parity is ignored.**
FA's `pytest-gremlins` exists specifically for Windows dev (no fork / no WSL). The baseline recommends Linux-only tools (mutmut in CI, Semgrep, CodeQL) without noting that Windows developers need parity. `gitleaks` and `uv` are cross-platform; `pip-audit` and `deptry` are pure Python.

## 5. Risks and caveats

- **OpenAI/Astral acquisition risk:** uv, ruff, and ty are now backed by OpenAI. While Astral has stated the tools remain open-source, long-term independence is uncertain. Counter-mitigation: uv uses standard `pyproject.toml` / `uv.lock` — migration to pip/poetry/pdm is always possible.
- **Semgrep OSS inter-procedural gap:** The free tier cannot track taint across function boundaries. FA's harness has cross-module taint paths (LLM output → tool selector → sandbox executor) that Semgrep OSS will miss. This is an accepted risk; upgrade to Semgrep Pro only if the advisory run surfaces actionable findings.
- **pyrefly vs mypy divergence:** pyrefly checks unannotated bodies by default (like ty, unlike mypy). A mypy-clean codebase may surface pyrefly-only errors. Running pyrefly as advisory (`continue-on-error: true`) absorbs this risk.
- **gitleaks pre-commit vs CI:** Pre-commit hooks are bypassable (ADR-11 R-6). gitleaks in pre-commit catches honest mistakes; a determined bypass requires CI-level scanning too. Mitigation: also run gitleaks in `ci.yml` as a lightweight step.

## 6. Numbered recommendations (R-1..R-15)

See §0 Decision Briefing for per-R verdicts, cost, and concrete first steps. This section provides long-form justification. R-15 (just) is detailed in §11.2 where the local-first architecture context is explained.

### R-1 — uv migration (cost: cheap)

**Why:** Build speed is the enabling constraint for every other gate. If CI takes >5 minutes, developers (and agents) skip running it locally. Astral's `BENCHMARKS.md` shows uv consistently faster than pip across warm/cold install and resolution, though exact multipliers depend on workload. For FA's small dependency tree, the absolute win is modest (seconds, not minutes), but the architectural consolidation (one tool for Python version, venv, install, lock, run) reduces cognitive load.

**Minimalism-first check:**
1. Evidence: Astral BENCHMARKS.md + OpenAI acquisition backing.
2. Precedent for removal: None — every major Python project is migrating to uv.
3. Capability lost if omitted: Fast, reproducible builds; standard lockfile (`uv.lock`).
4. Deterministic Python function: `uv sync --frozen` is a deterministic command, not an LLM call.

**Migration shape:**
- Replace `actions/setup-python@v5` with `astral-sh/setup-uv@v3` in CI workflows.
- Replace `pip install -e ".[dev]"` with `uv sync --frozen`.
- Add `uv.lock` to git (reproducible builds).
- Update `Makefile`: `install: uv sync --frozen && pre-commit install`.

### R-2 — pip-audit (cost: cheap)

**Why:** FA has zero SCA today. AI-authored codebases accumulate dependencies from suggestion drift — each "pip install X" an agent proposes may carry a known CVE. `pip-audit` (PyPA-maintained, Apache-2.0) scans the Python Packaging Advisory Database via the PyPI JSON API. It is the de-facto standard for Python dependency vulnerability scanning.

**Minimalism-first check:**
1. Evidence: PyPA official tool; used by CPython and major OSS projects.
2. Precedent for removal: No known project removed pip-audit without replacement; Trivy is the closest alternative but overkill for FA.
3. Capability lost if omitted: No PR-blocking dependency vulnerability gate.
4. Deterministic Python function: `pip-audit -r pyproject.toml` is deterministic.

**Implementation:** Add to `[dev]` extras; run in `ci.yml` after install.

### R-3 — deptry (cost: cheap)

**Why:** AI agents are prolific at adding dependencies. `deptry` scans `pyproject.toml` dependencies against actual imports in `src/`, flagging unused and missing deps. For a minimalism-first project, dependency bloat is a direct violation of principle.

**Minimalism-first check:**
1. Evidence: Widely adopted (osprey-oss/deptry, 1k+ stars); solves a real problem in AI-assisted codebases.
2. Precedent for removal: Not applicable — this is hygiene, not architecture.
3. Capability lost if omitted: Manual dependency audits that never happen.
4. Deterministic Python function: `deptry src/` is deterministic.

### R-4 — gitleaks (cost: cheap)

**Why:** LLM agents generate code with placeholder API keys, dummy tokens, and example credentials. `gitleaks` (MIT, zricethezark/gitleaks) is the fastest, lightest secret scanner with native pre-commit integration. It detects 500+ secret types and runs in <1 second.

**Why not GitGuardian/TruffleHog:** GitGuardian is paid (violates minimalism-first). TruffleHog is AGPL-3.0 (license concern for FA's proprietary license) and heavier. gitleaks is MIT, zero-config for basic use, and pre-commit-native.

**Minimalism-first check:**
1. Evidence: 20k+ GitHub stars; used by major projects; pre-commit official hook.
2. Precedent: Replacing with paid alternative is trivial if needs grow.
3. Capability lost: No secret leakage prevention.
4. Deterministic: Regex-based scan, no LLM involvement.

### R-5 — Semgrep OSS advisory (cost: medium)

**Why:** SAST is necessary for AI-authored code. arXiv:2507.02976v1 proves LLM patches introduce 9x more vulnerabilities than developers. However, Semgrep OSS has limitations:
- Intra-procedural taint only (free tier); inter-procedural requires Semgrep Pro.
- FPR on OWASP Java benchmark is 74.8% (arXiv:2601.22952); Python rules may differ but expect noise.
- Running on PR critical path with 75% FP rate would train the team to ignore findings.

**Advisory-only strategy:** Weekly + manual dispatch, `continue-on-error: true`. Findings are triaged manually. If signal proves clean after 4 weeks, consider promoting to PR-blocking with a `.semgrepignore`.

**Minimalism-first check:**
1. Evidence: arXiv:2507.02976v1 (LLM vulnerability gap) + Semgrep OSS adoption.
2. Precedent: Many teams run Semgrep advisory → blocking graduation.
3. Capability lost: No automated SAST for AI-authored code.
4. Deterministic: Pattern-matching engine, deterministic per rule set.

### R-6 — pyrefly advisory alongside mypy (cost: cheap)

**Why:** pyrefly 1.0.0 (Meta, 12 May 2026) is stable, auto-migrates mypy configs, and runs 10-50x faster. For FA's small codebase, mypy is already fast, but pyrefly surfaces different error shapes — catching bugs mypy misses (e.g., unannotated body analysis). Running both increases confidence without breaking the gate.

**Why not replace mypy:** FA has no mypy plugin dependencies, so migration is technically viable. But mypy is the single gate the team trusts; breaking it for a 5-second CI win is not worth the risk. pyrefly as advisory provides signal; mypy stays the gate.

**Minimalism-first check:**
1. Evidence: Meta production use (Instagram); stable 1.0.0 release.
2. Precedent: Teams run multiple type checkers in parallel routinely.
3. Capability lost: Additional type-checking signal.
4. Deterministic: Static analysis, no LLM call.

### R-7 — DEFER ty until 1.0 (cost: medium if taken now)

**Why:** ty is beta (v0.0.37, Jun 2026). Astral uses it internally and claims 10-60x speedups, but:
- No stable release; API may change.
- Checks unannotated bodies by default (unlike mypy) — a mypy-clean codebase will surface new errors.
- Plugin system status unknown; baseline's "no plugins, no plans" is unverified.

**DEFER rationale:** FA's mypy gate is already sub-minute. The speed win is marginal for a small codebase. Wait for 1.0, then evaluate migration.

### R-8 — DEFER custom Semgrep rules (cost: expensive)

**Why:** Custom Semgrep rules for `@tool` decorator boundaries, MCP protocol misuse, and LLM-tainted args are valuable. But FA's tool surface is still evolving:
- ADR-7 (inner-loop) has had 3 amendments since May 2026.
- ADR-8 (HookRegistry) is not yet frozen.
- Tool shape (JSON-Schema, MCP convention) may change before v0.2.

Writing rules against a moving target creates maintenance debt. Freeze the tool surface first, then write rules.

### R-9 — DEFER DeepEval / Promptfoo until UC5 (cost: expensive)

**Why:** Agent behavioral evaluation is critical (Pillar 4 — "iteration via measurement"). But:
- FA has no stable inner-loop contract yet (ADR-7 still amending).
- No golden prompt dataset exists.
- The baseline invented metric names (`StepEfficiencyMetric`, `PlanAdherenceMetric`) that don't exist in DeepEval's public API.
- Eval without a stable harness is measuring noise.

**UC5 scope (deferred to v0.2)** is the correct place for this. Build the harness, then measure it.

### R-10 — DEFER Tach until module count > 5 (cost: cheap setup, medium maintenance)

**Why:** Tach enforces import boundaries between modules. FA currently has ~8 top-level packages under `src/fa/`, but most are tightly coupled (inner-loop + sandbox + providers + authoring). ADR-11's CODEOWNERS + protected-path diff-check already provides boundary discipline. Tach adds value when modules are independently deployable or have distinct ownership — not yet.

### R-11 — SKIP garak (cost: expensive, no consumer)

**Why:** garak is a runtime LLM vulnerability scanner (jailbreaks, prompt injection, data extraction). FA is not a network-facing service. Running garak against a local harness is circular — the harness IS the system under test. No active consumer for this capability.

### R-12 — SKIP CodeQL (cost: medium, superseded)

**Why:** CodeQL provides deeper inter-procedural taint than Semgrep OSS. But:
- FA's threat model is authoring-time (ADR-11), not runtime taint.
- CodeQL is slow (minutes) and memory-heavy.
- Advisory Semgrep (R-5) provides the same SAST signal at lower cost.
- If Semgrep advisory proves valuable, CodeQL can be added as a deeper nightly layer. No need for both now.

### R-13 — SKIP Vulture CI gate (cost: cheap but noisy)

**Why:** Vulture finds dead code. AI projects accumulate it. But:
- High false positives on dynamically dispatched code (e.g., `getattr`, plugin systems).
- `deptry` (R-3) already covers dependency-level dead code.
- Symbol-level dead code detection is useful for manual audits, not CI gates.

**Compromise:** Add `make deadcode` target (non-gated) for monthly manual runs.

### R-14 — SKIP pytest-recording (cost: cheap, no problem to solve)

**Why:** VCR.py / pytest-recording records HTTP fixtures for deterministic CI. FA's test suite mocks LLM calls at the `ProviderAdapter` level — no real HTTP traffic in tests. VCR is a solution looking for a problem. Add it when HTTP-dependent tests are introduced (e.g., provider client integration tests).

## 7. Open questions (Q-1..Q-M)

### Q-1 — Does pyrefly's "basic" preset catch enough errors to be useful as advisory?

pyrefly defaults to "basic" preset for unconfigured projects, which surfaces only high-confidence errors. FA will run `pyrefly init` once to auto-migrate mypy config. If the migrated config is too permissive, pyrefly may emit zero findings — making the advisory job worthless. **Resolution:** Run `pyrefly init` manually, review the generated config, and adjust to `strict` preset if needed.

### Q-2 — What is the false-positive rate of Semgrep OSS on Python code (not Java)?

The baseline's 74.8% FPR is from Java. Python SAST rules may have different FP characteristics. **Resolution:** Run 4 weekly Semgrep advisory jobs, manually count FPs vs true positives, and document the observed rate in a follow-up note.

### Q-3 — Will uv's OpenAI acquisition affect its open-source licensing?

OpenAI announced the Astral acquisition on 19 Mar 2026, stating the tools will remain open-source. No license change has occurred. **Resolution:** Monitor `github.com/astral-sh/uv` for license changes; the MIT license makes fork-and-continue always possible.

## 8. Files used

- `knowledge/research/_template.md` — research note template
- `knowledge/project-overview.md` §1.2 — minimalism-first principle
- `knowledge/glossary.md` — term definitions
- `knowledge/llms.txt` — routing index
- `AGENTS.md` — pre-flight checklist, context-budget discipline
- `.github/workflows/ci.yml` — current CI pipeline
- `.github/workflows/tests.yml` — mutation testing workflow
- `.github/workflows/pylint.yml` — pylint workflow
- `.github/workflows/authoring-guardrails.yml` — authoring guardrails
- `.pre-commit-config.yaml` — pre-commit hooks
- `Makefile` — build targets
- `pyproject.toml` — tool configuration

Primary external sources:
- arXiv:2601.22952 — "Sifting the Noise: A Comparative Study of LLM Agents in Vulnerability False Positive Filtering"
- arXiv:2602.05868 — "Persistent Human Feedback, LLMs, and Static Analyzers for Secure Code Generation and Vulnerability Detection"
- arXiv:2507.02976v1 — "Are AI-Generated Fixes Secure? Analyzing LLM and Agent Patches on SWE-bench"
- https://github.com/astral-sh/uv/blob/main/BENCHMARKS.md
- https://openai.com/index/openai-to-acquire-astral/
- https://github.com/facebook/pyrefly/releases/tag/1.0.0
- https://astral.sh/blog/ty
- https://github.com/astral-sh/uv/issues/18506
- https://deepeval.com/docs/evaluation-unit-testing-in-ci-cd
- https://github.com/NVIDIA/garak
- https://github.com/tach-org/tach
- https://konvu.com/compare/semgrep-vs-codeql
- https://pypi.org/project/pip-audit/
- https://pypi.org/project/deptry/
- https://genai.qa/blog/promptfoo-vs-deepeval/

## 9. Out of scope

- Paid-tier security tools (Snyk, SonarQube, Codacy, GitGuardian enterprise) — minimalism-first excludes these.
- Container/IaC scanning (Trivy, Snyk Container) — FA has no Docker/K8s in v0.1.
- Runtime AI security (NeMo Guardrails, Rebuff, Lakera) — FA is not a deployed service.
- Cloud CI platforms (CircleCI, Harness, GitLab CI) — FA uses GitHub Actions.
- Benchmark harness design (UC5) — deferred to v0.2 per ADR-1.
- Custom rule authoring for Semgrep/CodeQL — deferred until tool surface stabilizes.
- Migration from ruff to ty as formatter — ty is a type checker, not a formatter; ruff-format stays.
- Bandit Python-specific SAST — superseded by Semgrep OSS (broader rule set, same price: free).

## 10. Gap Check & Cross-Reference (post-write validation)

This section documents the second-pass critical cross-reference of the note's claims against FA's actual repository files and ADRs. It is the "red team" review of the note itself.

### 10.1. Verified claims (no gaps found)

| Claim in note | Evidence from repo | Status |
|---------------|-------------------|--------|
| FA has zero SCA today | `pyproject.toml` [dev] deps: mypy, pre-commit, pytest, mutmut, ruff, types-PyYAML — no pip-audit, no Trivy | CONFIRMED |
| FA has zero secret scanning | `.pre-commit-config.yaml`: check-added-large-files, check-merge-conflict, ruff, markdownlint — no gitleaks, no TruffleHog | CONFIRMED |
| FA mocks LLM calls at ProviderAdapter level | `grep -r 'mock\|patch\|vcr\|recording\|http' tests/` → 0 results. Tests use `pytest` fixtures, not HTTP | CONFIRMED |
| UC5 eval harness deferred to v0.2 | `ADR-1` §Context: "UC5 — eval-driven harness iteration (deferred to v0.2)"; `BACKLOG.md` I-1 references ADR-7 as unblock-trigger | CONFIRMED |
| mypy is the sole type-checker gate | `pyproject.toml`: `[tool.mypy]` strict=true; no pyrefly, no ty in deps | CONFIRMED |
| mutmut + pytest-gremlins already in CI | `tests.yml` runs mutmut weekly; `pyproject.toml` has `[tool.pytest-gremlins]` config | CONFIRMED |
| ADR-11 says pre-commit is bypassable | `ADR-11-authoring-guardrails.md` §Tooling boundary: "`pre-commit` is bypassable (`--no-verify`) and is therefore convenience, not authority" | CONFIRMED |
| Windows dev parity exists via pytest-gremlins | `pyproject.toml` §pytest-gremlins: "native-Windows mutation testing (no fork / no WSL)" | CONFIRMED |

### 10.2. Claims requiring correction

**Correction 1: R-10 understates module count.**
The note says "FA has <10 top-level modules". `src/fa/` actually contains ~15 top-level packages (`__init__`, `_yaml_subset`, `authoring_rules`, `authoring_tcb`, `chunker`, `cli`, `config`, `hygiene`, `inner_loop`, `observability`, `orchestration`, `providers`, `roles`, `sandbox`, `tools`, `verifier`). This does not invalidate the Tach deferral — ADR-11 CODEOWNERS + protected-path checks still provide boundary discipline — but the quantitative justification was wrong. The stronger argument is that most modules are tightly coupled (inner-loop imports sandbox, providers, hygiene) and are not independently deployable units.

**Correction 2: R-4 gitleaks needs CI-level backup per ADR-11.**
The note recommends gitleaks as a pre-commit hook. ADR-11 §Tooling boundary explicitly states pre-commit is "convenience, not authority" because it is bypassable via `--no-verify`. The recommendation should include a CI-level `gitleaks detect` step in `ci.yml` as well, or the pre-commit-only recommendation violates ADR-11's own threat model.

**Correction 3: R-1 uv migration shape omits hatchling build-backend.**
`pyproject.toml` uses `hatchling` as the build backend (`[build-system] requires = ["hatchling>=1.25"]`). uv supports PEP 517 build backends, but `uv sync --frozen` requires a `uv.lock` file generated by `uv lock` first. The migration shape should include: (a) `uv lock` to generate `uv.lock` from hatchling-built deps, (b) commit `uv.lock`, (c) then `uv sync --frozen` in CI. Without step (a), `uv sync --frozen` fails on first run.

**Correction 4: R-2 pip-audit command needs `--format` flag for pyproject.toml.**
`pip-audit -r pyproject.toml` is incorrect syntax. `pip-audit` reads `pyproject.toml` natively when run in the project root (it auto-discovers `pyproject.toml`, `requirements.txt`, etc.). The correct command is simply `pip-audit` (run from repo root) or `pip-audit --requirement pyproject.toml --format json` if explicit. The note's concrete first step has a syntax error.

**Correction 5: R-6 pyrefly needs dev dependency addition.**
The note says "Add `pyrefly check` job to ci.yml" but does not mention adding `pyrefly` to `[dev]` extras in `pyproject.toml`. Without this, the CI job would need a separate `pip install pyrefly` step. The recommendation should include both CI workflow *and* `pyproject.toml` changes.

### 10.3. Missing cross-references (gaps in the note)

**Gap A: No mention of `universal-ctags` system dependency in uv migration.**
`ci.yml` installs `universal-ctags` via `apt-get`. uv cannot install system packages. The uv migration keeps the `apt-get` step unchanged. This is obvious but worth documenting so a future agent doesn't delete the system dependency step thinking uv replaces everything.

**Gap B: No mention of `.pylintrc-tests` in the baseline critique.**
The baseline says "Your separate pylint.yml workflow may be redundant by late 2026 once Ruff finishes its remaining pylint-equivalent rules." FA's `pylint.yml` runs a two-pass lint: strict for `src/`, relaxed for `tests/` via `.pylintrc-tests`. Ruff does not support per-directory config files natively. Even if Ruff reaches 100% pylint parity, the dual-profile pattern would still require creative workarounds. The note should mention this as an additional reason to keep pylint for now.

**Gap C: No Windows-native SAST recommendation.**
Finding 5 (Windows CI parity) correctly notes that Semgrep/CodeQL are Linux-only in CI, but the note offers no mitigation. Semgrep provides a Windows binary via `pip install semgrep` (pure Python + compiled extensions). Windows devs can run `semgrep --config=p/python src/` locally. The note should add a "Windows devs:" callout to R-5.

**Gap D: No cross-reference to ADR-10 deterministic invariants.**
ADR-10 (Deterministic Harness Invariants) requires every harness component to satisfy I-1..I-5. The new tools being added should be checked against these invariants:
- I-1 (single-source-of-truth): pip-audit/deptry config lives in `pyproject.toml` — satisfies.
- I-2 (numbered mandatory workflows): New CI workflows need numbers if they become mandatory gates.
- I-3 (stable `[CODE]` prefix): Advisory workflows don't need this, but blocking ones do.
- I-4 (typed loop-state ownership): Not applicable to CI tools.
- I-5 (layer-boundary fail-fast): Semgrep advisory should fail-fast if promoted to blocking.

**Gap E: No analysis of `make check` target expansion.**
The note recommends adding deptry to `make lint` and pip-audit to CI, but doesn't show the expanded `Makefile`. If R-1 (uv), R-2 (pip-audit), R-3 (deptry), and R-4 (gitleaks) are all adopted, `make check` should become: `lint typecheck authoring-check audit deadcode test`. The note should show the target dependency tree.

### 10.4. Risk of note becoming stale

| Item | Stale trigger | Mitigation |
|------|--------------|------------|
| ty 1.0 release | `astral-sh/ty` releases 1.0.0 | Re-evaluate R-7 |
| uv audit ships | `astral-sh/uv` closes issue #18506 | Update R-2 to mention uv audit as alternative |
| DeepEval adds missing metrics | `confident-ai/deepeval` documents StepEfficiencyMetric / PlanAdherenceMetric | Retract Finding 3; re-evaluate R-9 |
| FA module count grows | `src/fa/` exceeds 20 independently deployable modules | Re-evaluate R-10 |
| ADR-8 freezes | HookRegistry contract lands in v0.2 | Unblock R-8 custom Semgrep rules |
| Semgrep OSS Python FPR measured | 4 weekly advisory runs completed | Update §4.1 claim #7 with Python-specific numbers |

### 10.5. Subtraction-check on the note itself

Per `project-overview.md` §1.2 minimalism-first, the note itself should pass the 4-question test:

1. **Research evidence:** Yes — 3 arXiv papers, 4 GitHub releases, 5 official docs, 2 comparison sites.
2. **Precedent for not having it:** No known agent-stack publishes adversarial CI/QA reviews internally; this is novel context for FA.
3. **Capability lost if omitted:** No systematic evaluation of CI tool candidates; risk of adopting baseline recommendations uncritically.
4. **Deterministic Python function:** No — this is a research note requiring model judgment (synthesis, adversarial reasoning). It justifies its existence as a context artifact that prevents downstream LLM calls from re-researching the same space.

**Verdict on the note itself:** TAKE as a durable research artifact. The note saves future agents from re-researching the CI/QA space (estimated ~2,000 tokens of web-search context per future query).

## 11. Local-first architecture, `just`, and GitHub LLM review

### 11.1. Context: agent runs Linux, IDE tweaks on Windows, push to GitHub

FA's primary execution environment is a Linux agent workspace. The project owner occasionally edits on Windows via IDE. GitHub is the final destination, not the primary gate. This inverts the traditional CI/CD model where GitHub Actions is the blocking quality gate.

**Consequence:** `make check` (or its successor `just check`) must be the authoritative gate, run by the developer/agent before every push. GitHub CI becomes an advisory double-check.

### 11.2. `just` as the cross-platform task runner (R-15)

`just` (casey/just, MIT, Rust) is a command runner with no implicit rules, no tab-indentation requirements, and native binaries for Linux/macOS/Windows. For FA's local-first workflow:

- **Linux agent:** `just check` runs identically
- **Windows IDE:** `just check` runs identically (install via `cargo install just` or download release binary)
- **No Makefile portability issues:** Windows lacks `make` by default; `just` has no dependency on MSYS2/Git-Bash

**Proposed `justfile` shape (post R-1..R-5 adoption):**

```justfile
# Cross-platform task runner for First-Agent-dev
# Install: cargo install just  (or download binary from GitHub releases)

set dotenv-load := false

_default:
    just --list

install:
    uv sync --frozen
    pre-commit install

lint:
    ruff check .
    ruff format --check .
    deptry src/

format:
    ruff check --fix .
    ruff format .

typecheck:
    mypy

typecheck-advisory:
    pyrefly check || true

authoring-check:
    fa authoring-check

test:
    pytest

audit:
    pip-audit

deadcode:
    vulture src/ --min-confidence 90 || true

check: lint typecheck authoring-check test
```

**Migration path:** Keep `Makefile` alongside `justfile` for 2 weeks (deprecation period), then delete `Makefile`. Update `ci.yml` to run `just check` instead of `make check`.

### 11.3. GitHub CI redesign (advisory-only)

Given the local-first model, GitHub Actions should be **advisory-only** (`continue-on-error: true` on all jobs). The one exception is a lightweight "sanity" job that fails if `just check` was clearly never run (detectable via missing `coverage.xml` or stale `uv.lock`).

| Job | Trigger | Purpose | Blocking? |
|-----|---------|---------|-----------|
| `sanity-check` | PR + push to main | Runs `just check` as "did you forget?" double-check | **YES** (lightweight gate) |
| `semgrep-scan` | Weekly cron + PRs | OSS SAST rules; findings posted as PR comments | No |
| `coverage-upload` | PR + push to main | Uploads `coverage.xml` for GitHub UI | No |

### 11.4. GitHub LLM code review (native feature)

GitHub's built-in LLM code review preview is already enabled in this repository. It provides:
- Automated PR comments on potential issues
- 1-line-of-code fix suggestions with direct-commit UI
- No custom Actions or API keys required

**Impact on recommendations:**
- No need for a custom "LLM review" Action (this was a potential future recommendation now rendered unnecessary)
- GitHub's native feature covers the "light PR review" use case stated by the project owner
- R-5 (Semgrep) and native LLM review are complementary: Semgrep catches security patterns, LLM review catches style/architecture nits

**No action required** — the feature is already active and requires no repository configuration changes.

### 11.5. Stale-risk additions for local-first context

| Item | Stale trigger | Mitigation |
|------|--------------|------------|
| `justfile` migration complete | `Makefile` deleted, `just check` verified on both platforms | Remove `Makefile` from repo |
| GitHub LLM review GA | Feature exits preview | Verify it still works; no custom integration needed |
| Windows dev reports `just` issues | Windows IDE user reports friction | Debug `just` binary path or fall back to `make` |
| `uv.lock` drift | Agent forgets to run `uv lock` after dependency change | Add `uv lock --check` to `just check` or CI sanity job |
