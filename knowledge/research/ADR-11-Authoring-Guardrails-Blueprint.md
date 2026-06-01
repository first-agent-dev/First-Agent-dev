---
title: "ADR-11: Authoring Guardrails — Production Implementation Blueprint"
status: draft
date: 2026-05-31
supersedes: adr-11-authoring-guardrails-research-2026-05.md
source:
  - https://github.com/nousresearch/hermes-agent
  - https://github.com/coleam00/Archon
  - https://github.com/Disentinel/grafema
  - https://github.com/NVIDIA-NeMo/Guardrails
  - https://github.com/MondayInRussian/First-Agent-fork2
chain_of_custody: |
  Hermes Agent analysed at HEAD 4ccd141 (2026-05-31).
  Archon@ab1bee7, grafema@004480b, Guardrails@a6fc06f,
  First-Agent-fork2@872d4ee.
  See §14 for full file inventories with importance ratings.
mentions:
  - ADR-10
  - ADR-11
goal_lens: |
  Analyze OSS governance patterns for mechanical anti-tampering
  (CI/CODEOWNERS/I-FROZEN); discover zero-dependency deterministic
  Level 0 dispatchers/kernels; identify cross-file structural invariant
  enforcement; investigate test semantic decay locks; examine
  false-positive budgets via HARD-BLOCK vs ADVISORY lifecycles.
---

# ADR-11: Authoring Guardrails — Full Production Implementation Blueprint

## Table of Contents

0. TL;DR & Decision Briefing
1. Context & Threat Model
2. Research Scope & Method
3. Key Concepts (Glossary)
4. Important Files Inventory
5. Architectural Mapping — Archon
6. Architectural Mapping — Grafema
7. Architectural Mapping — NeMo Guardrails
8. First-Agent Target Fit
9. Architecture & Two-Tier TCB
10. Requirement Specifications (R-1..R-18)
11. Hermes Agent Cross-Validation & Conflict Audit
12. Blueprint Fit Audit
13. Risks & Caveats
14. Files Used
15. Out of Scope
Appendix A: R-N Summary Table
Appendix B: Production Rollout Sequence

---

## §0. TL;DR & Decision Briefing

### 0.1 TL;DR

- Four OSS repositories analysed: **Hermes Agent** (NousResearch),
  **Archon**, **Grafema**, **NeMo Guardrails**, plus the
  **First-Agent-fork2** target.
- **Hermes Agent** is the strongest new prior art for: write-path
  denylists (`agent/file_safety.py`), approval gating, curator
  self-improvement constraints, and always-run CI discipline
  (`contributor-check.yml`). These inform R-15 (denylist pattern),
  R-16 (save-time feedback), R-17 (network watchdog), R-18
  (self-improvement constraints).
- **Archon** is strongest for **generated parity** and anti-tampering
  through CI: committed generated files regenerated in `--check` mode
  before typecheck/lint/tests. Workflow loader shows warn-and-drop vs
  hard-error split. Marketplace lint is network-bound — not Level 0.
- **Grafema** is strongest for **cross-file structural invariants**:
  AST walkers, severity-as-false-positive-budget, guarantee lifecycle
  with drift/freshness, test `.only`/`.skip` locks.
- **NeMo Guardrails** is runtime prior art only. Template-method rail
  action, `RailResult`, short-circuit semantics, config validation
  tests. Dependency footprint (aiohttp, onnxruntime, pydantic, etc.)
  confirms NeMo is not Level 0.
- **First-Agent-fork2** already contains production-grade seeds:
  `pr_intent.py` + `tests/test_pr_intent_snapshot.py` pin hook
  constants to canonical skill text. `src/fa/hygiene/` and `verifiers/`
  directories show the project already has deterministic verification
  infrastructure ready for ADR-11 integration.
- **Critical negative: standalone CODEOWNERS, pre-commit-only, and
  path-skipped CI are all insufficient** as primary enforcement.
  Required CI over deterministic offline checks is the enforcement
  surface; CODEOWNERS matters only with branch protection and
  protected-path checks.
- **8 R-N conflicts identified and resolved** via Hermes cross-validation
  (see §11).

### 0.2 Decision Briefing: R-1..R-14 (from research note)

Each recommendation below follows the same structured format:
**What** / **Project-axis fit** / **Goal-lens fit** / **Cost** /
**Verdict** / **If UNCERTAIN-ASK** / **Alternative-if-rejected** /
**Concrete first step**.

#### R-1 — Level 0 authoring-check kernel

- **What:** Сделать один stdlib-only entrypoint `fa authoring-check`,
  который запускает маленький набор детерминированных repository rules
  и возвращает findings в text/json. Это не новый framework, а тонкий
  dispatcher поверх Python-функций.
- **Project-axis fit:** YES
- **Goal-lens fit:** YES
- **Cost:** medium (1–4h)
- **Verdict:** TAKE
- **If UNCERTAIN-ASK:** n/a (совпадает с ADR-10 compliance-by-construction
  и не требует новой runtime dependency).
- **Alternative-if-rejected:** Оставить authoring-time checks рассыпанными
  между pytest, pre-commit и review prose; это дешевле сейчас, но усилит
  drift между правилами.
- **Concrete first step:** Add `src/fa/authoring_tcb.py` + CLI subcommand
  `fa authoring-check --format text|json`; wire it into `make check` after
  current tests.

#### R-2 — RuleResult severity lifecycle

- **What:** Каждое authoring-time rule должно возвращать structured
  `RuleResult` with `severity`, `code`, `path`, `message`, `rationale`,
  and optional `expires_on`. CI fails only `HARD-BLOCK`; `ADVISORY`
  remains visible and time-bounded.
- **Project-axis fit:** YES
- **Goal-lens fit:** YES
- **Cost:** medium (1–4h)
- **Verdict:** TAKE
- **If UNCERTAIN-ASK:** n/a (mirrors Grafema's `error|warning|info`
  false-positive budget without importing Grafema).
- **Alternative-if-rejected:** All-or-nothing checks; noisy rules will be
  removed or bypassed instead of managed.
- **Concrete first step:** Define `RuleResult` frozen dataclass with
  `severity: Literal["HARD-BLOCK", "ADVISORY", "INFO"]`.

#### R-3 — Generated parity + I-FROZEN blocks

- **What:** Borrow Archon's `generate --check` pattern: for every committed
  generated or hand-mirrored artifact, record source-of-truth paths and fail
  when regenerated content differs. Add `I-FROZEN:` marker convention for
  guarded blocks editable only through checker.
- **Project-axis fit:** YES
- **Goal-lens fit:** YES
- **Cost:** medium (1–4h)
- **Verdict:** TAKE
- **If UNCERTAIN-ASK:** n/a (First-Agent already has the seed in
  `tests/test_pr_intent_snapshot.py`).
- **Alternative-if-rejected:** Human review only for mirrored files; will
  not catch stale parity before merge.
- **Concrete first step:** Create `src/fa/authoring_rules/parity.py` with
  one pair: `knowledge/skills/pr-creation/SKILL.md` ↔
  `src/fa/hygiene/pr_intent.py` constants.

#### R-4 — Minimal Python AST Visitor rules

- **What:** Use stdlib `ast.NodeVisitor` for source-code authoring rules
  needing structure: unsafe `yaml.load`, weak test assertions, mutable rule
  maps, broad swallowed exceptions, edits to frozen blocks. Regex stays only
  for file inventory and simple text markers.
- **Project-axis fit:** YES
- **Goal-lens fit:** YES
- **Cost:** medium (1–4h)
- **Verdict:** TAKE
- **If UNCERTAIN-ASK:** n/a (stdlib `ast` is enough for Python-only FA rules).
- **Alternative-if-rejected:** Grep-only lint; faster to write but brittle
  for comments/strings/nesting and easy for agents to bypass.
- **Concrete first step:** Add `src/fa/authoring_rules/exports.py` with one
  `NodeVisitor` rule: reject `yaml.load(...)` unless callee is `safe_load`.

#### R-5 — Test semantic decay lock

- **What:** Dedicated check that fails on new or unallowlisted `pytest.skip`,
  `pytest.mark.skip`, non-strict `xfail`, `.only`-style focus markers, and
  placeholder assertions (`assert True`). Prevents agents making tests easier
  instead of fixing code.
- **Project-axis fit:** YES
- **Goal-lens fit:** YES
- **Cost:** cheap (<1h)
- **Verdict:** TAKE
- **If UNCERTAIN-ASK:** n/a (small script, high protection against V11-style
  assertion decay).
- **Alternative-if-rejected:** Code review catches weakened tests — exactly
  the semantic-decay failure mode ADR-11 should mechanise.
- **Severity split (CONFLICT 3 resolution):**
  - HARD-BLOCK: `pytest.skip`, `pytest.mark.skip`, non-strict xfail,
    `.only`-style focus markers, `assert True` / `assert False is False`.
  - ADVISORY (until corpus validation): `==` → `in`, exact exception →
    broad `Exception`, other assertion weakening.
- **Concrete first step:** Add `src/fa/authoring_rules/tests.py` with
  AST visitor for test-semantic patterns.

#### R-6 — CI-enforced, not pre-commit-only

- **What:** Pre-commit hooks = developer convenience only. Authoritative
  ADR-11 checks run inside `make check` and GitHub CI. Do not path-skip
  authoring checks for docs-only or `.github/**` changes until ADR-11
  explicitly proves the skip is safe.
- **Project-axis fit:** YES
- **Goal-lens fit:** YES
- **Cost:** cheap (<1h)
- **Verdict:** TAKE
- **If UNCERTAIN-ASK:** n/a (local hooks bypassable with `--no-verify`).
- **Alternative-if-rejected:** Rules only in pre-commit; agents/contributors
  bypass or edit without hooks.
- **Concrete first step:** Extend `Makefile`: `check: lint typecheck authoring-check test`.
  CI workflow must always run (no path filter) per Hermes `contributor-check.yml` pattern.

#### R-7 — Borrow concepts, not Grafema/NeMo runtimes

- **What:** Grafema/NeMo = prior art only. Grafema's graph+Datalog stack and
  NeMo's runtime rails are too heavy for Level 0 authoring guardrails.
- **Project-axis fit:** YES
- **Goal-lens fit:** YES
- **Cost:** cheap (<1h)
- **Verdict:** TAKE
- **If UNCERTAIN-ASK:** n/a (minimalism-first guardrail on ADR-11 itself).
- **Alternative-if-rejected:** Introduce rich rule engine early; dependency,
  bootstrapping, and FP-management costs dominate first PR.
- **Concrete first step:** In ADR-11 §Prior Art, mark Grafema/NeMo as
  "pattern only, not dependency".

#### R-8 — Skip network validation in Level 0

- **What:** Do not copy Archon marketplace's live GitHub SHA/source URL
  validation into Level 0. Network checks useful for marketplace governance,
  but ADR-11 kernel = offline, deterministic, reproducible without secrets
  or internet.
- **Project-axis fit:** YES
- **Goal-lens fit:** PARTIAL (pinned-source validation relevant, but network
  violates Level 0 determinism)
- **Cost:** cheap (<1h)
- **Verdict:** SKIP
- **Alternative-if-rejected:** Add separate `fa provenance-check --network`
  later, never inside `make check`'s required Level 0 path.
- **Note:** Hermes `skills-index-freshness.yml` watchdog is valid pattern
  for external monitoring (R-17), but stays outside Level 0.

#### R-9 — Do not rely on standalone CODEOWNERS

- **What:** CODEOWNERS alone ≠ ADR-11 enforcement mechanism. Useful only
  as part of protected-path bundle (R-12): CODEOWNERS + branch protection +
  required CI diff-check.
- **Project-axis fit:** YES
- **Goal-lens fit:** YES
- **Cost:** cheap (<1h)
- **Verdict:** SKIP standalone; TAKE bundle via R-12
- **Alternative-if-rejected:** Standalone CODEOWNERS = false security
  boundary; I-FROZEN remains advisory, bypassable when branch protection
  absent.

#### R-10 — Add ADR thesis: LLM as Untrusted Compiler

- **What:** Frame LLM author as untrusted compiler translating intent into
  multi-file patches. Turns ADR from lint-rule list into threat-modelled
  authoring architecture.
- **Project-axis fit:** YES
- **Goal-lens fit:** YES
- **Cost:** cheap (<1h)
- **Verdict:** TAKE
- **Alternative-if-rejected:** ADR-11 reads as bag of checks; reviewers
  debate individual rules without shared threat model.
- **Concrete first step:** Add thesis to ADR-11 §Context.

#### R-11 — Level 0 TCB: TOML manifests + snapshot-bound verdicts

- **What:** Level 0 = frozen, stdlib-only TCB: parse TOML with `tomllib`,
  validate manifest shape, enumerate files deterministically, dispatch
  allowlisted Level 1 rules, bind every verdict to `snapshot_id`,
  `kernel_hash`, `rule_pack_hash`.
- **Project-axis fit:** YES
- **Goal-lens fit:** YES
- **Cost:** medium (1–4h)
- **Verdict:** TAKE
- **Alternative-if-rejected:** Kernel can be tampered with or produce
  non-reproducible findings; ADR-11 fails authoring-time determinism.
- **Concrete first step:** Draft `src/fa/authoring_tcb.py` API around
  `tomllib`, sorted path enumeration, SHA-256 hashing, deterministic
  JSON/text output.

#### R-12 — Protected-path governance is TAKE, not DEFER

- **What:** Protected paths (`authoring_tcb.py`, TOML schemas/manifests,
  authoring CI, hooks) must be covered by CODEOWNERS + branch protection +
  required CI diff-check. CODEOWNERS alone is weak; the bundle is the
  security boundary.
- **Project-axis fit:** YES
- **Goal-lens fit:** YES
- **Cost:** medium (1–4h plus GitHub settings)
- **Verdict:** TAKE
- **Alternative-if-rejected:** I-FROZEN remains documentary; agent edits
  checker/rule pack in same PR that bypasses checks.
- **Concrete first step:** Add `.github/CODEOWNERS` + `scripts/check_protected_paths.py`.

#### R-13 — Session seam and bootstrap invariants

- **What:** `.fa/session.toml` = source of truth for authoring seam, session
  id, trailers, bootstrap file expectations. First rule: staged diff ⊆
  declared seam. I-BOOT procedural until harness emits read receipts.
- **Project-axis fit:** YES
- **Goal-lens fit:** YES
- **Cost:** medium (1–4h)
- **Verdict:** TAKE
- **Alternative-if-rejected:** ADR-11 catches local rule violations but
  doesn't address LLM focus drift / position-bias edits outside intended area.
- **Concrete first step:** Define `.fa/session.toml` schema; add Level 1
  `seam_diff_subset` rule.

#### R-14 — Catch-corpus / FP-corpus measurement loop

- **What:** Convert historical omissions F-1..F-10 into fixture diffs
  (catch-corpus); recent green commits into FP-corpus. ADVISORY → HARD-BLOCK
  promotion requires measured FP rate below ADR threshold.
- **Project-axis fit:** YES
- **Goal-lens fit:** YES
- **Cost:** expensive (>4h)
- **Verdict:** TAKE
- **Alternative-if-rejected:** Severity classes remain subjective; reviewers
  cannot distinguish safe hard-blocks from noisy heuristics.
- **Concrete first step:** Add ADR-11 §Verification with `catch-corpus/`
  and `fp-corpus/` directory shapes; corpus fixtures in later PRs.

### 0.3 Summary table (R-1..R-14)

| R-N | Title | Verdict | Cost | Project fit | Goal-lens fit |
|-----|-------|---------|------|-------------|---------------|
| R-1 | Level 0 authoring-check kernel | TAKE | medium | YES | YES |
| R-2 | RuleResult severity lifecycle | TAKE | medium | YES | YES |
| R-3 | Generated parity + I-FROZEN | TAKE | medium | YES | YES |
| R-4 | Python AST Visitor rules | TAKE | medium | YES | YES |
| R-5 | Test semantic decay lock | TAKE | cheap | YES | YES |
| R-6 | CI-enforced, not pre-commit-only | TAKE | cheap | YES | YES |
| R-7 | Borrow concepts, not runtimes | TAKE | cheap | YES | YES |
| R-8 | Skip network validation in Level 0 | SKIP | cheap | YES | PARTIAL |
| R-9 | Standalone CODEOWNERS alone | SKIP | cheap | YES | YES |
| R-10 | LLM as Untrusted Compiler thesis | TAKE | cheap | YES | YES |
| R-11 | Level 0 TCB: TOML + snapshot | TAKE | medium | YES | YES |
| R-12 | Protected-path governance bundle | TAKE | medium | YES | YES |
| R-13 | Session seam + bootstrap invariants | TAKE | medium | YES | YES |
| R-14 | Catch/FP corpus measurement loop | TAKE | expensive | YES | YES |

---

## §1. Context & Threat Model

### 1.1 Core thesis: LLM as Untrusted Compiler

First-Agent (FA) needs a deterministic, offline authoring-time guardrail
system that prevents LLM agents from violating repository invariants
during PR authoring. This ADR specifies the production architecture,
threat model, R-N conflict resolution, and rollout sequence.

The core thesis: **LLM as Untrusted Compiler**. The LLM author is an
untrusted compiler that:

1. Receives intent (natural language task description)
2. Translates intent into multi-file patches
3. Can edit **any** file in the repository — including guardrails themselves
4. Can skip, weaken, or bypass validation in the same patch

This turns authoring-time validation from a linting problem into an
**admission-control boundary** problem. Ordinary lint/test tools are
insufficient because they do not model this threat.

### 1.2 Attack surface

| Attack vector | ADR-11 countermeasure | R-N |
|---|---|---|
| Edit guardrail TCB to bypass checks | Level 0 protected path | R-11, R-12 |
| Weaken tests instead of fixing code | Test semantic decay lock | R-5 |
| Edit generated parity without updating source | I-FROZEN + parity checker | R-3 |
| Use regex-bypassable patterns | AST Visitor rules | R-4 |
| Commit outside declared seam | Session seam enforcement | R-13 |
| Bypass pre-commit hooks | CI-enforced, not pre-commit-only | R-6 |
| Create false-positive noise to obscure real violations | Severity lifecycle + catch/FP corpus | R-2, R-14 |
| Mutate guardrail rules via LLM | Self-improvement constraints (DEFER) | R-18 |
| Use network-based checks that are flaky in CI | Level 0 remains offline | R-8, R-17 |
| Save-time lint bypassed; only CI catches | Save-time feedback = nice-to-have, CI = authority | R-16 |

### 1.3 Tooling boundary

Existing tools vs ADR-11:

| Tool | Scope | ADR-11 relation | Why not sufficient |
|---|---|---|---|
| `ruff` | Code style, import sorting, basic lint | Supplements, not replaces | No semantic/structural repo invariants |
| `mypy` | Static typing | Supplements, not replaces | Cannot detect stale parity, test decay, seam drift |
| `pytest` | Runtime correctness | Supplements, not replaces | Tests can be skipped/weakened by same agent |
| `pre-commit` | Developer convenience hooks | **Bypassable**; not authoritative | `--no-verify` bypass; no enforcement in CI |
| `fa authoring-check` | Repository-invariant guardrails (**THIS ADR**) | **Authoritative** | Deterministic, offline, CI-enforced, TCB-protected |

### 1.4 Prior art

- **Hermes Agent** (NousResearch): Production-grade agent with file-safety
  denylists (`agent/file_safety.py`), approval gating, curator
  self-improvement (`agent/curator.py`), always-run CI discipline
  (`contributor-check.yml`), network freshness watchdogs
  (`skills-index-freshness.yml`). Strongest evidence for save-time feedback
  (R-16, Conflict 6), self-improvement guardrails (R-18, Conflict 8),
  write-path denylist pattern (R-15), and always-run CI (R-6).
- **Archon** (`coleam00/Archon`): Generated parity via `--check` mode,
  deterministic DAG validation, structured severity (error vs warning),
  warn-and-drop vs hard-error boundary in workflow loader.
- **Grafema** (`Disentinel/grafema`): AST walker architecture, guarantee
  lifecycle with drift/freshness, severity as false-positive budget
  (three tiers with comments calibrating "no false-positive CI failures").
- **NeMo Guardrails** (`NVIDIA-NeMo/Guardrails`): Rail action template
  method, `RailResult(is_safe, reason)`, short-circuit/parallel-cancel
  semantics, config validation tests that pin failure messages.

---

## §2. Research Scope & Method

### 2.1 Goal lens (verbatim)

> Analyze OSS governance patterns for mechanical anti-tampering
> (CI/CODEOWNERS/I-FROZEN); discover zero-dependency deterministic
> Level 0 dispatchers/kernels; identify cross-file structural invariant
> enforcement; investigate test semantic decay locks; examine
> false-positive budgets via HARD-BLOCK vs ADVISORY lifecycles.

### 2.2 Clone / workspace status

All source repositories were analysed at specific HEADs:

| Repo | Local path | Branch | HEAD | Role in this ADR |
|------|------------|--------|------|-------------------|
| Hermes Agent | `nousresearch/hermes-agent` | `main` | `4ccd141` | Write denylists, approval gating, curator, CI discipline |
| Archon | `coleam00/Archon` | `dev` | `ab1bee7` | Generated parity, workflow validation, CI anti-tamper |
| Grafema | `Disentinel/grafema` | `main` | `004480b` | AST/graph rules, cross-file invariants, severity lifecycle |
| NeMo Guardrails | `NVIDIA-NeMo/Guardrails` | `develop` | `a6fc06f` | Runtime rails (negative evidence), config tests |
| First-Agent-fork2 | `MondayInRussian/First-Agent-fork2` | `main` | `872d4ee` | Target fit; existing seeds (pr_intent.py, chunker, verifiers) |

### 2.3 Relevance gate

| Project | Direct prior art | Indirect / concept only | Negative evidence |
|---------|-----------------|------------------------|-------------------|
| Archon | CI/generated-parity | — | Marketplace lint (network-bound) |
| Grafema | Cross-file invariants/severity | Datalog engine | — |
| NeMo | Config validation tests | Template-method rail | Runtime dependency footprint |
| Hermes Agent | Write denylists, always-run CI, curator constraints | — | Dynamic plugin discovery, YOLO mode |

### 2.4 Method

- Source files read and classified using 5 axes:
  1. Mechanical anti-tampering
  2. Level 0 feasibility
  3. Cross-file invariant strength
  4. Test semantic decay protection
  5. False-positive budget management
- Target filter: pattern requiring graph DB, network, LLM, heavy parser
  stack, or daemon → "borrow concept only" for ADR-11 v0.1.

### 2.5 Limits

- Upstream tests were not run; source analysis only.
- GitHub branch protection / CODEOWNERS enforcement settings not audited.
- Exact upstream paths/lines may drift after this note; re-check before
  landing ADR-11 with citations.

---

## §3. Key Concepts (Glossary)

These terms are used throughout this ADR with specific meanings:

| Term | Definition |
|------|-----------|
| **Authoring-time guardrail** | Deterministic repository check that fires while writing/reviewing code, before runtime behaviour matters. |
| **Level 0 kernel** | Offline, stdlib-only, no daemon, no DB, no network, no LLM; suitable for `make check` and CI. |
| **Level 1 rule** | Semantic repository rule dispatched by Level 0. Uses stdlib `ast`, regex for text markers, or Python hashing. |
| **Generated parity** | Committed generated/mirrored artifact must match deterministic regeneration from source-of-truth. |
| **I-FROZEN** | FA marker for guarded blocks whose edits must pass a checker/generator. Syntax: `# I-FROZEN: source=<path#anchor> checker=<path-or-rule-code>`. |
| **AST Visitor** | Structural traversal using Python stdlib `ast.NodeVisitor` when regex is too weak. |
| **Datalog guarantee** | Grafema-style declarative graph invariant; useful as concept, too heavy for FA Level 0. |
| **Freshness check** | Verify derived analysis inputs match current file contents before trusting results. |
| **HARD-BLOCK** | Severity causing CI exit code 1. Used only for deterministic, low-noise rules. |
| **ADVISORY** | Severity visible in output but CI exit code 0. Must have `expires_on` or auto-escalation. |
| **INFO** | Severity for informational findings; never blocks CI. |
| **Warn-and-drop** | Parse invalid optional field, log warning, continue. Good for user config, bad for hard repo invariants. |
| **Semantic test decay** | Weakening tests via skip/xfail/focus/placeholder assertions rather than fixing code. |
| **Seam** | Declared boundary of intended edits for an authoring session (`.fa/session.toml`). |
| **Catch-corpus** | Fixture diffs from historical omissions F-1..F-10 that rules must catch. |
| **FP-corpus** | Green-commit diffs used to measure false-positive rate before severity promotion. |

---

## §4. Important Files Inventory

### 4.1 Archon — most important files

| Importance | File | Why it matters for ADR-11 |
|------------|------|---------------------------|
| Critical | `package.json` | Single `validate` script composes generated parity, typecheck, lint, format, tests. |
| Critical | `scripts/generate-bundled-defaults.ts` | Best direct generated-parity / anti-tamper pattern. |
| Critical | `scripts/generate-bundled-schema.ts` | Same parity pattern for embedded SQL schema. |
| Critical | `scripts/check-bundled-skill.ts` | Safety net for hand-maintained bundle completeness; substring check caveat. |
| Critical | `packages/workflows/src/defaults/bundled-defaults.test.ts` | Test-level parity lock: bundled content = on-disk source. |
| Critical | `packages/workflows/src/loader.ts` | Deterministic workflow parser, structural DAG checks, warn-vs-error boundary. |
| Critical | `packages/workflows/src/schemas/dag-node.ts` | Zod schema as source of truth; mutual exclusivity and field constraints. |
| Critical | `packages/workflows/src/validator.ts` | Structured `ValidationIssue` with error/warning and hints. |
| Supporting | `packages/workflows/src/command-validation.ts` | Tiny path-traversal/name validator; good Level 0 shape. |
| Supporting | `.github/workflows/test.yml` | CI runs check-bundled before normal checks. |
| Supporting | `.github/workflows/e2e-smoke.yml` | Tiered deterministic vs provider-backed smoke split. |
| Supporting | `packages/docs-web/scripts/lint-marketplace.ts` | Pinned external source validation; network-bound. |
| Supporting | `.husky/pre-commit`, `.lintstagedrc.json` | Local convenience only; not authoritative anti-tamper. |

### 4.2 Grafema — most important files

| Importance | File | Why it matters for ADR-11 |
|------------|------|---------------------------|
| Critical | `.grafema/guarantees.yaml` | Best rule-card corpus: structural/semantic tiers and severity. |
| Critical | `packages/util/src/core/GuaranteeManager.ts` | Rule lifecycle: create/list/check/import/export/drift/selective check. |
| Critical | `packages/cli/src/commands/check.ts` | CLI check surface with stale graph handling and failure semantics. |
| Critical | `packages/python-analyzer/src/Analysis/Walker.hs` | Python AST walker architecture; routing by syntactic construct. |
| Critical | `packages/python-analyzer/src/Rules/UnsafeDynamic.hs` | Closed-set unsafe calls detection with exact path/line. |
| Critical | `packages/util/src/core/GraphFreshnessChecker.ts` | Content-hash freshness before rule checks. |
| Critical | `.github/workflows/ci.yml` | CI `.only`/`.skip` lock and version-sync checks. |
| Supporting | `packages/rfdb-server/src/datalog/eval.rs` | Datalog evaluator limits; concept only for FA. |
| Supporting | `packages/mcp/src/definitions/guarantee-tools.ts` | Rule lifecycle as tools; future pattern. |
| Supporting | `scripts/test-regression.sh` | TAP log summarization; useful for CI diagnostics. |
| Supporting | `scripts/check-bench-regression.sh` | Threshold-based performance HARD-BLOCK pattern. |
| Supporting | `packages/util/src/manifest/types.ts` + `api/manifest.yaml` | Manifest-as-boundary pattern. |

### 4.3 NeMo Guardrails — most important files

| Importance | File | Why it matters for ADR-11 |
|------------|------|---------------------------|
| Critical | `nemoguardrails/guardrails/rail_action.py` | Template-method pipeline: extract → prompt → respond → parse. |
| Critical | `nemoguardrails/guardrails/guardrails_types.py` | Tiny `RailResult(is_safe, reason)` — minimal and composable. |
| Critical | `nemoguardrails/guardrails/rails_manager.py` | Sequential short-circuit / parallel cancel routing. |
| Critical | `nemoguardrails/guardrails/iorails.py` | Supported-subset gating; explicit unsupported reasons. |
| Critical | `nemoguardrails/rails/llm/config.py` | Typed config models, validators, warnings. |
| Critical | `tests/test_config_validation.py` | Config validation tests pin exception messages. |
| Supporting | `nemoguardrails/actions/action_dispatcher.py` | Dynamic discovery → caution for Level 0 static import. |
| Supporting | `nemoguardrails/guardrails/engine_registry.py` | Registry lifecycle; fail-fast startup rollback. |
| Supporting | `.pre-commit-config.yaml`, `.github/workflows/lint.yml` | Standard hygiene; not sufficient for ADR-11. |
| Supporting | `.github/workflows/pr-tests-skip.yml` | **Negative prior art**: broad path-skips dangerous for ADR-11. |
| Supporting | `pyproject.toml` | Dependency footprint confirming NeMo ≠ Level 0. |
| Supporting | `docs/resources/security/guidelines.md` | Fail-open/fail-closed reasoning: prefer allow-lists, fail-closed. |

### 4.4 First-Agent target — most important files

| Importance | File | Why it matters for ADR-11 |
|------------|------|---------------------------|
| Critical | `src/fa/hygiene/pr_intent.py` | Existing deterministic authoring-time rule implementation. |
| Critical | `tests/test_pr_intent_snapshot.py` | Existing rulebook↔code parity lock (snapshot test). |
| Critical | `src/fa/inner_loop/hooks/intent_guard.py` | Same classifier/validator reused at harness time; ADR-10 I-1 seed. |
| Critical | `Makefile` | Current `check` integration point (`check: lint typecheck test`). |
| Critical | `.github/workflows/ci.yml` | Current required CI surface. |
| Critical | `src/fa/chunker/` | Existing deterministic Markdown/plain-text chunker (ADR-5). |
| Critical | `verifiers/` | DSV YAML contracts for tool verification (PR-3 / Wave-2). |
| Supporting | `src/fa/cli.py` | Existing CLI with `fa chunk` subcommand; pattern for `fa authoring-check`. |
| Supporting | `.pre-commit-config.yaml` | Local hook layer; useful but bypassable. |
| Supporting | `pyproject.toml` | Existing deps; confirms stdlib AST has no new dependency. |
| Supporting | `knowledge/adr/ADR-10-deterministic-harness-invariants.md` | Binding invariant slate for ADR-11 design fit. |
| Supporting | `knowledge/skills/pr-creation/SKILL.md` | Source-of-truth text currently pinned by tests. |

### 4.5 Hermes Agent — most important files

| Importance | File | LOC | Why it matters for ADR-11 |
|------------|------|-----|---------------------------|
| Critical | `agent/file_safety.py` | 453 | Write-path deny list pattern (R-15). |
| Critical | `tools/file_operations.py` | 2143 | Save-time write gate for every `write_file` (R-16). |
| Critical | `tools/approval.py` | 1624 | Layered human-in-the-loop approval gating (R-6, R-12). |
| Critical | `agent/curator.py` | 1800 | Self-improvement loop with protected-asset constraints (R-18). |
| Critical | `.github/workflows/contributor-check.yml` | 85 | Always-run CI discipline with zero path filters (R-6, R-12). |
| Critical | `AGENTS.md` | 1132 | Architecture docs, tool governance, protected-path conventions. |
| Supporting | `.github/workflows/skills-index-freshness.yml` | — | Network watchdog cron pattern (R-17). |
| Supporting | `toolsets.py` | — | Tool whitelisting for background processes (R-18). |

---

## §5. Architectural Mapping — Archon

### 5.1 CI parity before normal checks

Archon's root script chain puts generated parity before typecheck/lint/tests:
`check:bundled`, `check:bundled-skill`, and `check:bundled-schema` all run
before `type-check`, `lint`, `format:check`, and `test`
(`Archon/package.json:17-33`). Its GitHub `Test Suite` repeats the contract:
install deps, run `bun run check:bundled`, then typecheck, lint, format,
tests (`Archon/.github/workflows/test.yml:24-41`).

**ADR-11 read:** Generated parity is not a separate optional maintenance
command; it belongs in the same check path as tests. First-Agent's current
`Makefile` has `check: lint typecheck test` only
(`First-Agent-fork2/Makefile:8-22`), so ADR-11 has a clear insertion point.

### 5.2 Deterministic generation details

`generate-bundled-defaults.ts` fixes bundle drift and Node/Bun compatibility
by inlining string literals. It:

- Sorts filenames before emission
- Validates input filenames are kebab-case
- Rejects duplicate names with multiple extensions
- Normalizes CRLF to LF
- Rejects empty bundled defaults
- Renders deterministic `Record<string, string>` entries
- In `--check` mode: normalizes committed file line endings before compare
- Exits code `2` if stale (not `1` — distinguishes stale from failed)
- Prints a remediation command

These details are visible in `collectFiles` and `--check` paths
(`Archon/scripts/generate-bundled-defaults.ts:56-89`, `:147-164`).

**ADR-11 read:** FA parity checker must be byte-stable and boring. No
dependency on OS line endings, directory order, or human interpretation.

### 5.3 Hand-maintained bundle safety net

`check-bundled-skill.ts` verifies every `.claude/skills/archon/` file appears
in `bundled-skill.ts`, but the file documents the caveat: it is a **substring
check**, not structural verification (`Archon/scripts/check-bundled-skill.ts:3-16`).

**ADR-11 read:** Substring safety nets are acceptable as Level 0 seed checks
but should not be described as full invariant enforcement. For `I-FROZEN`
blocks, prefer structural extraction of fenced sections or AST constants over
raw substring search.

### 5.4 Workflow loader severity boundary

Archon's workflow loader has a deliberate severity split:

- **Warn-and-drop** for optional fields: `parseOptionalField` avoids aborting
  workflow discovery on one typo (`Archon/packages/workflows/src/loader.ts:39-62`).
- **Hard errors** for structure: duplicate IDs, unknown `depends_on`, cycles,
  invalid `$node.output` references (`:134-221`).
- **Hard errors** for explicit gates: provider identity, session-resume
  capability (`:303-378`).
- **Warnings** for AI-only fields on non-AI nodes (runtime ignores them)
  (`:106-129`).

**ADR-11 read:** Severity is not arbitrary. HARD-BLOCK when the artifact
would be structurally invalid or silently bypass a contract. ADVISORY for
optional/noisy/forward-compat fields.

### 5.5 Schema-as-source-of-truth

`dag-node.ts` describes a flat schema with `superRefine`, not implicit union,
because YAML lacks a discriminant (`Archon/packages/workflows/src/schemas/dag-node.ts:1-13`).
It enforces exactly-one node mode, non-empty IDs, command name validity,
timeout constraints, loop/retry incompatibility (`:260-378`).

**ADR-11 read:** Pattern is strong (one schema/validator site, typed outputs,
clear messages) but FA Level 0 should not add Zod-equivalent dependencies.
Python dataclasses + stdlib `ast` + small validators are sufficient.

### 5.6 ValidationIssue shape

Archon's `ValidationIssue`: `level: 'error' | 'warning'`, `nodeId`, `field`,
`message`, `hint`, `suggestions` (`Archon/packages/workflows/src/validator.ts:43-70`).
Missing command/MCP files = errors; unsupported provider capabilities = warnings
(`:324-430`).

**ADR-11 read:** FA's `RuleResult` should include actionable hints. Every
finding should have `code`, `path`, `line`, and one-line remediation.

### 5.7 Network validation is explicitly not Level 0

Archon's marketplace lint checks source URLs and pinned SHAs through live
GitHub raw/API requests. Good marketplace governance, but network-bound.
ADR-11 Level 0 must stay offline; otherwise CI flakiness and
credentials/network policy become part of the guardrail.

---

## §6. Architectural Mapping — Grafema

### 6.1 AST walker architecture

Grafema's Python analyzer (`Analysis.Walker`) emits a module node, then
routes each statement to rule modules: imports, declarations, control flow,
error flow, exports, calls
(`grafema/packages/python-analyzer/src/Analysis/Walker.hs:1-65`). It
separately walks expressions and recursively walks bodies so rules see
nested functions/classes/try bodies (`:67-125`).

**ADR-11 read:** FA should not put all authoring checks in one regex loop.
Use visitor methods by syntactic construct; keep each rule narrow.

### 6.2 Unsafe dynamic rule as direct analogue

Grafema's `Rules.UnsafeDynamic` declares a closed set of unsafe calls:
`eval`, `exec`, `getattr`, `setattr`, `delattr`, `compile`, 3-arg `type`,
and `importlib.import_module`
(`grafema/packages/python-analyzer/src/Rules/UnsafeDynamic.hs:1-43`, `:50-80`).
When detected, emits `UNSAFE_DYNAMIC` node with line/column and `CONTAINS`
edge (`:82-128`).

**ADR-11 read:** FA's first AST rules should mirror this style: small closed
lists, explicit node metadata, exact path/line in result. Examples: `yaml.load`,
`subprocess.run(..., shell=True)`, `pytest.skip`, placeholder assertions.

### 6.3 Guarantees as rule cards with severity

`.grafema/guarantees.yaml` is the strongest rule-card corpus with three tiers:

- **Tier 1** — structural containment as `severity: error`
- **Tier 2** — semantic integrity as `severity: warning`
- **Tier 3** — BEAM messageflow findings, with comments: "no false-positive
  CI failures", visibility-only → info

Representative: `export-has-target` = warning (export without target likely
bad but may have modeling caveats); `unsafe-dynamic-has-contains` = error
(dynamic constructs must be traceable).

**ADR-11 read:** Severity must encode false-positive budget. This is the
best evidence for R-2.

### 6.4 Guarantee lifecycle and drift

`GuaranteeManager` defines `GuaranteeSeverity = 'error' | 'warning' | 'info'`,
stores `rule`, `severity`, `governs`, checks rules, enriches violations with
node/file/line, supports import/export YAML, selective checks by extracted
types, drift comparison between graph and file
(`grafema/packages/util/src/core/GuaranteeManager.ts:22-119`, `:213-348`,
`:351-520`).

**ADR-11 read:** FA copies lifecycle, not engine: list rules → run rules →
emit structured findings → fail by severity → export json. Avoid database
until FA has enough code graph needs.

### 6.5 Freshness before trust

`GraphFreshnessChecker` compares `contentHash` stored in MODULE nodes against
current file hashes, reports changed/deleted/unreadable modules
(`grafema/packages/util/src/core/GraphFreshnessChecker.ts:1-35`, `:39-91`,
`:93-145`). `grafema check` can fail on stale modules in CI mode.

**ADR-11 read:** FA Level 0 does not need graph freshness (reads files live),
but generated parity checks must not trust cached inputs. If future ADR-11
uses an index, validate freshness first or fail closed.

### 6.6 Test semantic locks and regression summarization

Grafema CI checks for `.only()` in tests on every run and `.skip()` on stable
(`grafema/.github/workflows/ci.yml:123-140`). Also checks package/Cargo
version sync (`:217-264`). `scripts/test-regression.sh` parses TAP logs and
reports real non-TODO failures. `scripts/check-bench-regression.sh` uses
numeric threshold to fail only regressions above a multiplier.

**ADR-11 read:** FA should implement semantic test locks now (R-5). The
threshold pattern is useful for FP budgets: HARD-BLOCK only when signal is
above a clear line.

### 6.7 MCP guarantee tools are future, not v0.1

Grafema exposes guarantee CRUD as MCP tools with severity/priority/status/owner
(`grafema/packages/mcp/src/definitions/guarantee-tools.ts:6-68`) and formats
pass/fail in handlers (`:129-246`).

**ADR-11 read:** Useful for future agent-facing rule editor, but FA Stage 1
keeps authoring rules in code. No LLM-created HARD-BLOCK rules before static
kernel is proven.

---

## §7. Architectural Mapping — NeMo Guardrails

### 7.1 Template-method rail action

`RailAction` defines pipeline: `run()` validates flow name, resolves model,
extracts messages, creates prompt, gets response, parses response, returns
`RailResult` (`Guardrails/nemoguardrails/guardrails/rail_action.py:16-68`,
`:75-120`). Subclasses implement `_extract_messages`, `_create_prompt`,
`_get_response`, `_parse_response`.

**ADR-11 read:** Authoring rules should have similarly boring contract:
`collect input → evaluate → return RuleResult`. No rule should invent its
own output format.

### 7.2 Tiny result type

NeMo's `RailResult` = frozen dataclass with `is_safe` and optional `reason`
(`Guardrails/nemoguardrails/guardrails/guardrails_types.py:20-41`). Minimal
and composable.

**ADR-11 read:** FA's `RuleResult` slightly richer (path/line/severity).
Keep frozen and serializable.

### 7.3 Manager short-circuit and parallel cancel

`RailsManager` reads configured flows, builds action instances, runs
input/output rails (`Guardrails/nemoguardrails/guardrails/rails_manager.py:16-23`,
`:58-120`). Sequential returns on first unsafe; parallel cancels remaining on
first unsafe (`:151-225`).

**ADR-11 read:** HARD-BLOCK rules can short-circuit in fast text mode, but
`--json` should support collect-all so LLM repair gets all findings in one pass.

### 7.4 Supported subset and explicit unsupported reasons

`IORails` defines `SUPPORTED_RAILS`, `SUPPORTED_INPUT_FLOWS`,
`SUPPORTED_OUTPUT_FLOWS`, `unsupported_reason()`; unsupported configs fall
back rather than pretending to work
(`Guardrails/nemoguardrails/guardrails/iorails.py:74-120`).

**ADR-11 read:** Every rule that cannot analyse a file must produce observable
skip/advisory reason. Silent pass is forbidden.

### 7.5 Config validation tests pin failure messages

`tests/test_config_validation.py` asserts missing rails and missing prompt
templates raise specific errors (`Guardrails/tests/test_config_validation.py:18-101`).
This is test semantic locking at the config-contract layer.

**ADR-11 read:** When FA adds authoring checks, tests must assert both
positive and negative fixtures and pin error codes/messages where future LLM
agents will use them for recovery.

### 7.6 Action dispatcher: useful but caution

`ActionDispatcher` discovers action modules in package/library/cwd/config/import
paths, registers functions/classes with `action_meta`
(`Guardrails/nemoguardrails/actions/action_dispatcher.py:37-120`).
`execute_action` normalizes names, lazily instantiates classes, supports
sync/async/LangChain-like callables, logs failures, returns `(None, "failed")`
for many errors (`:171-250`).

**ADR-11 read:** Dynamic discovery is powerful but too permissive for hard
repository invariants. Level 0 kernel must use static rule list.

### 7.7 Negative evidence: dependency footprint and path skips

NeMo's runtime deps include `aiohttp`, `annoy`, `fastembed`, `onnxruntime`,
`httpx`, `jinja2`, `lark`, `pydantic`, `pyyaml`, `rich`, and many optional
extras (`Guardrails/pyproject.toml:46-115`). Normal for runtime guardrails
library but wrong for FA Level 0.

`pr-tests-skip.yml` skips tests for PRs touching Markdown or `.github/**`
(`Guardrails/.github/workflows/pr-tests-skip.yml:1-15`). Dangerous pattern
for ADR-11: `.github/**` changes can alter enforcement itself.

NeMo security docs say prefer allow-lists and fail-closed; AI Defense defaults
to blocking on missing/malformed results unless `fail_open=True`
(`docs/resources/security/guidelines.md`). Supports ADR-11 fail-closed
protected-path and malformed-config behaviour.

---

## §8. First-Agent Target Fit

### 8.1 Existing seed: `pr_intent.py`

`pr_intent.py` names the skill file as single source of truth and materializes
it as deterministic functions: classifier, required fields, commit-message
validator, citation resolver (`First-Agent-fork2/src/fa/hygiene/pr_intent.py:1-31`).
Uses closed enums, frozen dataclasses, path buckets, read-only mapping exports
(`:41-117`, `:300-332`).

This is already the right ADR-11 shape:

```
source-of-truth prose/table
  → deterministic extractor/constants
  → hook/runtime consumer
  → snapshot test that detects drift
```

### 8.2 Existing seed: snapshot test as parity lock

`tests/test_pr_intent_snapshot.py` reads `knowledge/skills/pr-creation/SKILL.md`
§Output format and asserts module constants match fenced-block shape; drift
fails CI (`First-Agent-fork2/tests/test_pr_intent_snapshot.py:1-15`, `:61-123`).

ADR-11 should **generalize this pattern**, not replace it.

### 8.3 Existing seed: one classifier, two consumers

`IntentGuard` reuses same `classify_intent` and `validate_commit_msg` functions
as git hooks, explicitly satisfying ADR-10 I-1 single-source-of-truth
(`First-Agent-fork2/src/fa/inner_loop/hooks/intent_guard.py:1-69`).

ADR-11 should require every future rule with multiple consumers to expose the
same canonical function/table, not duplicate logic.

### 8.4 Existing integration gap

First-Agent CI runs `make check` (`First-Agent-fork2/.github/workflows/ci.yml:1-32`),
and `make check` currently runs lint, typecheck, test only
(`First-Agent-fork2/Makefile:8-22`). No general authoring-check slot yet.

This makes R-1/R-6 the correct first implementation: add the slot, then add
rules incrementally.

### 8.5 Existing chunker infrastructure

`src/fa/chunker/` already has deterministic Markdown/plain-text chunker with:

- `Chunk` frozen dataclass with provenance
- `Chunker` Protocol
- `MarkdownChunker`, `PlainTextChunker`, `CompositeChunker`
- `fa chunk` CLI subcommand
- Snapshot tests with positive/negative fixtures

This infrastructure is directly reusable for ADR-11 document rules (docs
parity, llms.txt freshness). The chunker's deterministic path enumeration
and CLI integration are the same patterns needed for authoring-check.

### 8.6 Existing verifier contracts

`verifiers/` directory contains DSV YAML contracts for tool verification
(R-5 from borrow-roadmap). This is the Level 1 rule pattern: deterministic
verification against YAML manifests. ADR-11 should integrate or complement
this existing infrastructure.

---

## §9. Architecture & Two-Tier TCB

### 9.1 Minimal architecture (from synthesis)

Recommended ADR-11 v0.1 shape:

```
src/fa/authoring_tcb.py           # Level 0 kernel
  RuleResult dataclass
  Rule protocol
  run_all(repo_root, manifest) → list[RuleResult]

src/fa/authoring_rules/
  __init__.py                     # Static allowlist dispatch
  exports.py                      # V2: __all__ completeness
  parity.py                       # V3: generated parity
  docs.py                         # V5: doc integrity
  tests.py                        # V4/V10/V11: test semantics
  seam.py                         # V6: session seam
  messages.py                     # V12: message registry

scripts/
  check_protected_paths.py        # CI diff-checker

.github/
  CODEOWNERS                      # Protected paths
  workflows/
    authoring-guardrails.yml      # CI workflow (always-run)

.fa/
  session.toml                    # Session manifest

Makefile                          # check: lint typecheck authoring-check test
```

### 9.2 Rule metadata contract

Every rule should declare:

```python
@dataclass(frozen=True)
class RuleSpec:
    code: str                          # e.g. "FA-AUTHORING-V2-EXPORTS"
    severity: Literal["HARD-BLOCK", "ADVISORY", "INFO"]
    rationale: str                     # Why this rule exists (ADR ref)
    owner: str = "ADR-11"
    expires_on: str | None = None      # ISO date for ADVISORY expiry
```

`ADVISORY` without `expires_on` should itself be an ADVISORY finding so
warnings don't become permanent noise.

### 9.3 What should be HARD-BLOCK first

Low false-positive, high-value initial hard blocks:

1. Generated/frozen parity mismatch
2. `pytest.skip` / `pytest.mark.skip` / non-strict `xfail` in tests
   unless allowlisted in a tiny file
3. `assert True` / `assert False is False` placeholder assertions
4. `yaml.load` instead of `yaml.safe_load` in `src/fa/**`
5. Direct edits to generated files without matching source update

### 9.4 What should be ADVISORY first

Start advisory, promote only after FP experience (R-14):

1. Test function with no assertion-like check
2. Broad `except Exception` in authoring/guard code
3. Duplicated literals that look like rule enums
4. Stale `knowledge/llms.txt` inventory (until row-generation rules unambiguous)
5. CODEOWNERS absence

### 9.5 Explicit rejects for v0.1

- No Datalog engine
- No graph database
- No dynamic rule creation by LLM/MCP
- No network checks in required CI path
- No CODEOWNERS as primary enforcement
- No pre-commit-only enforcement
- No `--yolo` bypass flag (unlike Hermes `HERMES_YOLO_MODE`)

### 9.6 Level 0 detailed contract

Level 0 is **frozen code** under protected-path governance (R-12). It must:

1. Accept a single `--manifest <path>` argument (TOML file)
2. Parse manifest using stdlib `tomllib` (stdlib since Python 3.11)
3. Validate manifest shape (keys, types, required fields)
4. Enumerate repository paths in sorted order (deterministic)
5. Compute:
   - `snapshot_id = sha256(sorted(file_paths + file_hashes))`
   - `kernel_hash = sha256(Level 0 source)`
   - `rule_pack_hash = sha256(Level 1 rule modules)`
6. Dispatch allowlisted Level 1 rules (static import list only — no dynamic discovery)
7. Collect `list[Diagnostic]` from Level 1 rules
8. Sort diagnostics deterministically (severity rank → code → path → line → message)
9. Output structured JSON (or text)
10. Exit code: 0 if no HARD-BLOCK, 1 if any HARD-BLOCK

**Level 0 must never:**
- Import anything outside stdlib
- Make network calls
- Read environment variables for behaviour (only for paths like HOME)
- Load plugins dynamically
- Evaluate LLM output
- Use regex for structural analysis (only for text markers)

### 9.7 Deterministic output contract

```json
{
  "kernel_version": "0.1",
  "kernel_hash": "sha256:...",
  "snapshot_id": "sha256:...",
  "rule_pack_hash": "sha256:...",
  "session_hash": "sha256:... or null",
  "diagnostics": [
    {
      "severity": "HARD-BLOCK",
      "code": "FA-AUTHORING-V2-EXPORTS",
      "path": "src/fa/foo.py",
      "line": 12,
      "column": null,
      "message": "Public symbol foo is not exported from src/fa/__init__.py",
      "remediation": "Add foo to __all__ or rename it _foo if private.",
      "rule_input_hash": "sha256:..."
    }
  ],
  "exit_code": 1
}
```

Diagnostic sort order:
1. Severity rank: HARD-BLOCK=0, ADVISORY=1, INFO=2
2. Code (lexicographic)
3. Path (lexicographic)
4. Line (ascending)
5. Message (lexicographic)

### 9.8 Fail-closed behaviour

- Malformed manifest → exit code 1 + diagnostic
- Rule raises exception → exit code 1 + wrapped diagnostic
- Unknown manifest key → exit code 1 + diagnostic
- Empty snapshot → exit code 1 + diagnostic
- Missing required field → exit code 1 + diagnostic

---

## §10. Requirement Specifications (R-1..R-18)

### R-1 — Level 0 authoring-check kernel (TAKE, P0)

- **What:** stdlib-only dispatcher `fa authoring-check` in
  `src/fa/authoring_tcb.py`. Archon's `check:bundled` + Grafema's
  `check` CLI as direct prior art.
- **Evidence:**
  - Archon `package.json:17-33`: `validate` composes parity → typecheck → lint → format → tests
  - Grafema `cli/src/commands/check.ts`: structured CLI check surface
  - Hermes `AGENTS.md` `make check` pattern
- **Cost:** medium (1–4h)
- **First step:** Implement Level 0 TCB with TOML manifest parsing via
  `tomllib`, sorted path enumeration, SHA-256 hashing, deterministic sort.
- **Alternative-if-rejected:** Keep scattered pytest/pre-commit/prose checks;
  cheaper now but amplifies drift.

### R-11 — Level 0 TCB specifics (TAKE, P0)

- **What:** Level 0 uses `tomllib`, sorted path enumeration, SHA-256 hashing
  for snapshot/rule-pack/kernel, static allowlist dispatch. Grafema's
  `GuaranteeManager` lifecycle (list → run → emit → fail) is the conceptual
  pattern.
- **Evidence:**
  - Grafema `GuaranteeManager.ts:22-119`: `list checks → run → enrich → fail by severity`
  - Grafema `GraphFreshnessChecker.ts:1-35`: content-hash before trust
  - Hermes `file_safety.py`: realpath-based path comparison
- **Cost:** medium (1–4h)
- **Note:** R-1/R-11 define Level 0; R-3/R-4/R-5/R-13 are Level 1 rules
  dispatched by Level 0.

### R-2 — RuleResult severity lifecycle (TAKE, P0)

- **What:** `RuleResult` with HARD-BLOCK / ADVISORY / INFO severity. CI fails
  only on HARD-BLOCK. ADVISORY must have `expires_on` or auto-escalation rule.
  Grafema's `.grafema/guarantees.yaml` three-tier severity calibrated to
  "no false-positive CI failures" is the direct template.
- **Evidence:**
  - Grafema `.grafema/guarantees.yaml`: `severity: error|warning|info` with
    comments per tier
  - Archon `validator.ts:43-70`: `ValidationIssue` with `level: 'error'|'warning'`, hints, suggestions
  - NeMo `guardrails_types.py:20-41`: `RailResult(is_safe, reason)` — minimal frozen dataclass
- **Cost:** medium (1–4h)
- **First step:** Define `RuleResult` frozen dataclass with `severity`, `code`,
  `path`, `line`, `message`, `remediation`, `rule_input_hash`.

### R-3 — Generated parity + I-FROZEN blocks (TAKE, P1) [Level 1]

- **What:** For committed generated/mirrored artifacts, record source-of-truth
  paths and fail when regenerated content differs. `I-FROZEN:` marker for
  guarded blocks editable only through checker. **Archon's `generate --check`
  is the direct prior art.**
- **Evidence:**
  - Archon `generate-bundled-defaults.ts:3-23`: sorted filenames, CRLF→LF
    normalization, `--check` exit code 2
  - Archon `generate-bundled-defaults.ts:56-89, 147-164`: `collectFiles` and
    `--check` path with remediation command
  - FA `tests/test_pr_intent_snapshot.py:61-123`: existing seed for this pattern
- **Cost:** medium (1–4h)
- **First step:** `src/fa/authoring_rules/parity.py` with one pair:
  `knowledge/skills/pr-creation/SKILL.md` ↔ `src/fa/hygiene/pr_intent.py`.
- **I-FROZEN syntax:**
  ```
  # I-FROZEN: source=<path#anchor> checker=<path-or-rule-code>
  ```
  No YAML frontmatter in code comments. Checker extracts via stdlib regex or
  line-by-line scan in Level 1.

### R-4 — Python AST Visitor rules (TAKE, P1) [Level 1]

- **What:** stdlib `ast.NodeVisitor` for structural rules. Grafema's
  `Analysis.Walker` and `Rules.UnsafeDynamic` are the direct analogues.
- **Evidence:**
  - Grafema `Analysis.Walker.hs:1-65`: routes statements to rule modules by
    syntactic construct
  - Grafema `Rules.UnsafeDynamic.hs:1-43, 50-80, 82-128`: closed set of unsafe
    calls, exact path/line emission
  - Archon `command-validation.ts`: tiny path/name validator as good Level 0
    shape (though this stays in Level 1)
- **Cost:** medium (1–4h)
- **First step:** `src/fa/authoring_rules/exports.py` with one `NodeVisitor`
  rule: reject `yaml.load(...)` unless callee is `safe_load`.

### R-5 — Test semantic decay lock (TAKE, P1) [Level 1]

- **What:** Fail on test-weakening patterns. Grafema CI `.only()`/`.skip()`
  checks are the direct prior art.
- **Evidence:**
  - Grafema `.github/workflows/ci.yml:123-140`: `.only()` and `.skip()` lock
  - FA `test_pr_intent_snapshot.py`: existing snapshot-as-parity-lock pattern
  - Hermes `curator.py`: self-improvement constrained to not mutate bundled skills
    (analogous: test rules should not be weakenable by same agent)
- **Cost:** cheap (<1h)
- **Severity split (CONFLICT 3):**
  - **HARD-BLOCK:** `pytest.skip`, `pytest.mark.skip`, non-strict xfail,
    `.only`-style focus markers, `assert True` / `assert False is False`
  - **ADVISORY (until corpus validation):** `==` → `in` weakening,
    exact exception → broad `Exception`, other assertion weakening
- **xfail allowlist:** Require `strict=True` + ADR/issue reference. Default
  is HARD-BLOCK. Allowlist file for edge cases with expiry date.

### R-6 — CI-enforced, not pre-commit-only (TAKE, P0)

- **What:** `make check` runs `authoring-check` before `test`. CI calls
  `make check`. Pre-commit is convenience only. **Hermes
  `contributor-check.yml` is the production pattern.**
- **Evidence:**
  - Hermes `contributor-check.yml`: zero path filters, always runs, filter
    step inside job, not workflow-level
  - FA `Makefile:8-22`: current `check: lint typecheck test` — missing slot
  - FA `.github/workflows/ci.yml:1-32`: currently runs `make check`
  - Archon `.github/workflows/test.yml:24-41`: parity before other checks
- **Cost:** cheap (<1h)
- **First step:** Extend `Makefile`: `check: lint typecheck authoring-check test`.
  CI workflow must use Hermes pattern: no `paths:` filter, gate work inside step.
- **No path-skip for `.github/**`:** NeMo `pr-tests-skip.yml` is negative prior
  art — `.github/**` changes can alter enforcement itself.

### R-7 — Borrow concepts, not runtimes (TAKE, P0)

- **What:** State explicitly: concepts from Grafema/NeMo (severity lifecycle,
  template-method), not their runtimes.
- **Evidence:**
  - Grafema: Datalog evaluator (`eval.rs`) + RFDB server — too heavy for Level 0
  - NeMo: `onnnxruntime`, `pydantic`, `aiohttp`, `jinja2` in
    `pyproject.toml:46-115` — confirms dependency scope wrong for Level 0
- **Cost:** cheap (<1h)

### R-8 — Skip network validation in Level 0 (SKIP)

- **What:** No network checks in Level 0. Archon marketplace lint
  (`lint-marketplace.ts`) is good governance but network-bound. Hermes
  `skills-index-freshness.yml` watchdog is external-only.
- **Cost:** cheap (<1h)
- **Alternative:** Separate `fa provenance-check --network` later, never
  inside `make check`'s required Level 0 path.

### R-9 — CODEOWNERS standalone is not enough (SKIP standalone)

- **What:** Standalone CODEOWNERS is documentary, not security boundary.
  Protected-path governance bundle (R-12) is TAKE.
- **Evidence:** None of the four OSS repos rely on standalone CODEOWNERS as
  enforcement mechanism. Hermes uses branch protection + required checks.
- **Cost:** cheap (<1h)

### R-10 — ADR thesis: LLM as Untrusted Compiler (TAKE, P0)

- **What:** Frame ADR with this threat model up front.
- **Cost:** cheap (<1h)
- **Implemented in §1 of this document.**

### R-12 — Protected-path governance bundle (TAKE, P0)

- **What:** CODEOWNERS + branch protection/ruleset + required CI diff-check +
  human owner review for TCB/protected paths.
- **CI cannot prove human approval by itself** — branch protection is authority.
  Hermes `contributor-check.yml` always-run pattern supports this: CI reports
  status, branch protection enforces review.
- **Protected paths:**
  - `src/fa/authoring_tcb.py`
  - `src/fa/authoring_rules/__init__.py`
  - `.github/workflows/authoring-guardrails.yml`
  - `.github/CODEOWNERS`
  - `scripts/check_protected_paths.py`
- **Cost:** medium (1–4h plus GitHub settings)
- **Concrete first step:** Add `.github/CODEOWNERS` for protected paths and
  `scripts/check_protected_paths.py` that fails PRs touching those paths unless
  branch-protection review is satisfied.

### R-13 — Session seam and bootstrap invariants (TAKE, P1) [Level 1]

- **What:** `.fa/session.toml` is source of truth for declared seam, session
  id, trailers. First enforceable rule: staged paths ⊆ declared seam.
- **Note (CONFLICT 5):** `.fa/session.toml` is authoritative for save-time/
  commit-time local checks. Merge-time CI enforcement requires trusted committed
  manifest. No silent claim that CI can validate local state it cannot see.
- **Cost:** medium (1–4h)
- **I-BOOT:** Procedural until harness can emit read receipts with path and hash.

### R-14 — Catch-corpus / FP-corpus measurement loop (TAKE, P2)

- **What:** Convert historical omissions (F-1..F-10) into fixture diffs.
  Use recent green commits as FP-corpus. Promote ADVISORY → HARD-BLOCK only
  when FP rate below threshold.
- **First step:** Add §Verification plan with directory shapes; implement
  corpus fixtures in later PRs.
- **Cost:** expensive (>4h)

### R-15 — Hermes file-safety denylist pattern (TAKE, P0)

- **What:** Adopt Hermes `agent/file_safety.py` write-path deny list pattern
  for TCB protection. Hermes denies writes to ~/.ssh, ~/.aws, ~/.gnupg,
  /etc/sudoers, .env, auth.json, config.yaml using both exact paths and
  prefixes, resolved via `os.path.realpath()`.
- **FA TCB denylist:**
  ```python
  _TCB_PATHS = frozenset({
      "src/fa/authoring_tcb.py",
      "src/fa/authoring_rules/__init__.py",
      ".fa/manifest.toml",  # if committed
      ".github/workflows/authoring-guardrails.yml",
      ".github/CODEOWNERS",
      "scripts/check_protected_paths.py",
  })
  _TCB_PREFIXES = ["src/fa/authoring_rules/"]
  ```
- **Key Hermes lessons:**
  1. Always use `os.path.realpath()` to prevent symlink bypass
  2. Check both exact paths and prefixes
  3. Distinguish "can't write to TCB through guardrails" (CI-enforced) vs
     "can't write to user creds" (sandbox-enforced)
  4. Hermes checks both active profile AND global root for control files
     (FA doesn't need multi-profile but should check realpath)
- **Cost:** cheap (<1h)

### R-16 — Save-time checks as feedback, not authority (DEFER, P3)

- **What:** Hermes `tools/file_operations.py` (2143 LOC) provides save-time
  feedback on every `write_file` via `is_write_denied()`. Excellent UX but
  not anti-tamper authority.
- **Verdict:** DEFER for v0.1. Save-time lint is not anti-tamper authority.
  Commit/CI/branch protection remains authoritative.
- **Future path:** Add `fa authoring-check --watch` as save-time feedback
  after TCB is stable and measured.

### R-17 — Network freshness watchdog outside Level 0 (DEFER, P3)

- **What:** Hermes `skills-index-freshness.yml` runs 4-hour cron that validates
  skills index freshness, checks per-source minimum counts (≥100 skills each),
  total minimum (≥1500), age (>26h = stale), files GitHub issues on failure.
  Uses title-prefixed issue naming so subsequent failures append comments.
- **Verdict:** Network watchdogs allowed outside Level 0. Not in required
  offline PR admission. Level 0 remains offline.
- **Future path:** Add freshness cron for `knowledge/llms.txt` or external
  knowledge source validation after v0.1.

### R-18 — Self-improvement with tool whitelist (DEFER, P3, documented)

- **What:** Hermes `agent/curator.py` (1800 LOC) is strong prior art for
  background self-improvement. Key constraints:
  - Restricted to memory+skills toolsets only (from `toolsets.py`)
  - Only touches `created_by: "agent"` provenance (never bundled/hub skills)
  - Pinned skills exempt from every auto-transition
  - Never deletes (max = archive to `~/.hermes/skills/.archive/`)
  - Writes per-run reports to `logs/curator/run.json + REPORT.md`
- **Verdict:** DEFER for v0.1. Self-improvement must be:
  - Tool-whitelisted (limited toolset like Hermes' memory+skills)
  - Report-backed (per-run reports)
  - Protected-asset-respecting (never mutates Level 0 / HARD-BLOCK rules)
- **Constraint for v0.1:** No Level 0 / HARD-BLOCK rule mutation by LLM.
  Future architecture must add governance layer before self-evolution of rules.

---

## §11. Hermes Agent Cross-Validation & Conflict Audit

### 11.1 Conflict 1 — Level 0 vs Level 1 mixing (R-1/R-11)

**Problem:** R-1 originally read as "authoring-check runner with rules",
mixing TCB with semantic rules. This conflicted with the two-tier plan.

**Hermes evidence:** Hermes `file_safety.py` is a pure denylist engine
(analogous to Level 0) while `curator.py` is a domain-specific rule system
(analogous to Level 1). They never mix — the denylist doesn't contain
curation logic, and the curator doesn't reimplement file safety.

**Resolution:**
- **Level 0** = protected `src/fa/authoring_tcb.py` (R-1/R-11)
- **Level 1** = semantic rules modules (R-3/R-4/R-5/R-13)
- Clear boundary: Level 0 has zero repo-specific semantic knowledge

### 11.2 Conflict 2 — Generated parity / AST / test rules in Level 0 (R-3/R-4/R-5)

**Problem:** Generated parity, AST visitor rules, and test semantic rules
could have been placed in Level 0, breaking stdlib-only TCB.

**Hermes evidence:** Hermes `tools/file_operations.py` (2143 LOC) contains
domain-specific logic (fence stripping, binary detection, search patterns)
that stays outside the core safety kernel (`file_safety.py` at 453 LOC).
The 5:1 size ratio shows separation of concerns.

**Resolution:**
- Generated parity = Level 1
- AST visitor rules = Level 1
- Test semantic rules = Level 1
- Level 0 only: TOML parse, manifest validate, sorted enumerate, hash,
  dispatch, sort diagnostics, fail closed

### 11.3 Conflict 3 — Test semantic decay: HARD-BLOCK vs ADVISORY (R-5)

**Problem:** R-5 originally hard-blocked too much. Blueprint says V11
assertion lock starts ADVISORY.

**Hermes evidence:** Hermes curator preserves nuance — it auto-archives stale
skills but never deletes, and pinned skills are fully exempt. Severity
granularity is built into the architecture.

**Resolution:**
- **HARD-BLOCK:** `pytest.skip`, `pytest.mark.skip`, non-strict xfail,
  focus markers, `assert True` / `assert False is False`
- **ADVISORY (until corpus validation):** `==` → `in` weakening, exact
  exception → broad `Exception`, other assertion weakening

### 11.4 Conflict 4 — CODEOWNERS standalone vs bundle (R-9/R-12)

**Problem:** Earlier notes had CODEOWNERS tension.

**Hermes evidence:** Hermes `contributor-check.yml` always runs and reports
status, but it doesn't claim to be a security boundary — it's a gate that
branch protection enforces. Hermes doesn't rely on standalone CODEOWNERS.

**Resolution:**
- Standalone CODEOWNERS = **SKIP** (false security boundary)
- Protected-path governance bundle = **TAKE**: CODEOWNERS + branch protection
  + CI diff-check + human owner review
- CI cannot prove human approval; branch protection is authority

### 11.5 Conflict 5 — `.fa/session.toml` seam authority (R-13)

**Problem:** `.fa/session.toml` is local. Merge-time CI cannot trust it.

**Hermes evidence:** Hermes distinguishes save-time (`file_operations.py`
write denylist — local, bypassable) from CI-time (contributor-check —
authoritative). Same pattern applies: session.toml = save-time; committed
manifest = CI-time.

**Resolution:**
- `.fa/session.toml` authoritative for save-time/commit-time local checks
- Merge-time seam enforcement requires trusted committed/session manifest
- No silent claim that CI can validate uncommitted local state

### 11.6 Conflict 6 — Save-time checks vs authoritative boundary (R-16)

**Problem:** Hermes `tools/file_operations.py` is excellent save-time feedback
but could be mistaken for anti-tamper authority.

**Hermes evidence:** `file_operations.py` is called on every `write_file`
but is NOT the security boundary — if the agent edits `file_safety.py` itself,
the save-time check is bypassed. This is why Hermes relies on CI and branch
protection, not the save-time hook.

**Resolution:**
- Save-time lint is not anti-tamper authority
- Commit/CI/branch protection remains authoritative
- R-16 is **DEFER**, not immediate P2
- Document as future feedback loop after TCB is stable

### 11.7 Conflict 7 — Network checks in Level 0 (R-8, R-17)

**Problem:** Hermes has network freshness watchdogs.

**Hermes evidence:** Hermes `skills-index-freshness.yml` is a 4-hour cron
that files GitHub issues — completely outside the PR admission path. It's
monitoring, not enforcement. Hermes cron threat scanner has a two-tier split:
strict mode for user prompts, loose mode for skill-assembled prompts. Neither
is in the PR merge path.

**Resolution:**
- Network watchdogs allowed outside Level 0
- Not in required offline PR admission
- Level 0 remains offline
- Hermes two-tier cron scanner pattern is good for future external monitoring

### 11.8 Conflict 8 — Self-improvement mutation of rules (R-18)

**Problem:** Hermes curator is strong prior art for self-improvement, but
LLM-mutated rules could bypass guardrails.

**Hermes evidence:** Hermes curator has 5 hard constraints:
1. Restricted to memory+skills toolsets only (from `toolsets.py`)
2. Only touches `created_by: "agent"` provenance
3. Pinned skills exempt from every auto-transition
4. Never deletes (max = archive)
5. Writes per-run reports

These constraints prevent the curator from editing its own governance.

**Resolution:**
- Self-improvement must be tool-whitelisted (Hermes pattern)
- Report-backed (per-run reports)
- Protected assets respected (never Level 0 / HARD-BLOCK rules)
- No Level 0 / HARD-BLOCK rule mutation by LLM in v0.1
- R-18 remains **DEFER**, documented as future architecture constraint

---

## §12. Blueprint Fit Audit

### 12.1 Fit matrix against the ADR-11 blueprint

| Blueprint element | Fit | Gap / correction |
|---|---|---|
| LLM as Untrusted Compiler | Now present | Added R-10; ADR leads with threat model, not rule list |
| Tooling boundary vs ruff/mypy/pytest | Present | Table showing each tool's scope and insufficiency |
| F-1..F-10 historical omissions | LOW | Plan's baseline absent from OSS evidence; must import from PR B/C audit |
| Two-tier TCB | Present | Level 0 with `tomllib`, sorted enumeration, hashing, static dispatch |
| Authoring-time determinism | Present | Exact I/O spec: snapshot hash, rule-pack hash, session hash, sorted diagnostics |
| I-FROZEN | PARTIAL | Marker concept present; authoritative enforcement = R-12 bundle |
| CODEOWNERS/branch protection | RESOLVED | CONFLICT 4: standalone SKIP, bundle TAKE |
| TOML rule manifests | Present | Level 0 uses `tomllib`; no YAML parser in Level 0 |
| V1/V7 SSOT taxonomy | PARTIAL | Parity recommendation helps; ADR must specify code-owned SSOT |
| V2 exports completeness | Present | Grafema evidence supports AST completeness; R-4 covers this |
| V3 Bash parity | PARTIAL | Archon parity evidence present; Jinja2 must not enter Level 0 |
| V4/V10/V11 noisy heuristics | Present | ADVISORY with catch/FP corpus before promotion (R-14) |
| V5 doc integrity | PARTIAL | Docs rule module defined; concrete markdown relation rules in PR 3 |
| V6 seam-bounded authoring | Present | R-13: `.fa/session.toml` + staged-diff subset check (CONFLICT 5) |
| V12 message registry | PARTIAL | Registry rule module defined; implementation in PR 5 |
| V14 trailers | LOW | Trailers documented as audit metadata, not access control |
| I-BOOT | PARTIAL | R-13; read receipts = future/harness-dependent |
| Metrics / P4 corpus | Present | R-14: catch-rate and FP targets for severity promotion |

### 12.2 Critical contradictions resolved

1. **CODEOWNERS conflict.** Resolution: TAKE protected-path bundle;
   standalone CODEOWNERS = false security boundary.
2. **Jinja2 vs Level 0 stdlib-only.** Resolution: Jinja2 must not enter
   Level 0. Prefer `string.Template` or direct Python rendering.
3. **`CONTRACT.yaml` vs TOML Level 0.** Resolution: Level 0 only parses
   TOML. YAML is Level 1 or generated artifact only.
4. **AI-authored protected-path changes.** Resolution: Protected paths
   enforced by required human review regardless of claimed authoring mode.
5. **CI diff-check cannot replace branch protection.** Resolution: CI detects
   changes; branch protection enforces review. ADR-11 treats branch protection
   as authoritative GitHub boundary.

### 12.3 Source re-pass findings for blueprint gaps

- **Archon supports deterministic scope gates but not CODEOWNERS.** Marketplace
  workflow verifies PR scope, runs deterministic schema/security checks, then
  AI review and deterministic decision logic. Supports scope-gated admission
  but not CODEOWNER enforcement.
- **Archon release workflow supports human approval gates.** Interactive mode,
  validates preconditions, pauses for human approval before writing files and
  before tagging/release. Supports human gate patterns.
- **Grafema supports manifest-as-boundary.** Package `manifest.yaml` files
  describe export/import/effect surfaces. YAML format is not Level 0-compatible
  but the pattern is relevant for rule-pack/session manifest design.
- **NeMo supports fail-open/fail-closed reasoning.** Security docs prefer
  allow-lists and fail-closed; AI Defense defaults to blocking on missing or
  malformed results unless `fail_open=True`. Supports ADR-11 fail-closed
  protected-path behaviour.

---

## §13. Risks & Caveats

### 13.1 Overfitting to current files

ADR-11 should start with rules that guard existing high-value contracts
(`SKILL.md` ↔ constants), not a broad speculative lint catalog.

### 13.2 False-positive escalation

If too many rules start as HARD-BLOCK, agents will learn to bypass. Use
ADVISORY with expiry. Hermes curator archives (never deletes) — similar
principle: downgrade severity rather than remove rules entirely.

### 13.3 Checker drift

A parity checker can itself drift. Keep checker code tiny, tested with
positive/negative fixtures, and cited from ADR-11. Hermes `contributor-check.yml`
pattern (always-run, path-filtered inside job) prevents checker-skip.

### 13.4 Regex bypass

Regex rules catch easy cases but fail on comments, strings, aliases, nested
constructs. Promote important rules to AST. Grafema's `UnsafeDynamic.hs`
shows the right pattern: closed sets with exact node metadata.

### 13.5 Path-skip trap

Skipping authoring checks for docs or `.github/**` is risky — docs are often
source-of-truth; workflows enforce the rules. NeMo `pr-tests-skip.yml` is
negative prior art. Hermes `contributor-check.yml` has zero path filters —
the correct pattern.

### 13.6 Dependency creep

Grafema/NeMo demonstrate rich engines, but FA Level 0 should remain
stdlib-only. PyYAML already exists in FA but authoring-check should not
need it for its first rules. Hermes `file_safety.py` manages with only
stdlib `os`, `pathlib`, `typing` — the right scope.

### 13.7 Branch-protection audit not performed

CODEOWNERS may become valuable later if required review enforcement is
enabled. Current analysis did not audit GitHub branch protection settings
for any of the four OSS repos.

### 13.8 Hermes-specific caveats

- Hermes is a ~175K LOC agent platform with 27K tests — FA is an order of
  magnitude smaller. Patterns must be scaled down.
- Hermes `approval.py` has `--yolo` flag that bypasses all approval prompts.
  FA guardrails must NOT have equivalent bypass.
- Hermes `file_operations.py` has terminal-fence-leak stripping that is
  irrelevant to FA's file-scoped authoring checks.

---

## §14. Files Used

### 14.1 Archon

- `Archon/package.json:17-33` — validate script chain
- `Archon/scripts/generate-bundled-defaults.ts:3-23, 56-89, 147-164` — parity checker
- `Archon/scripts/generate-bundled-schema.ts` — SQL schema parity
- `Archon/scripts/check-bundled-skill.ts:3-16` — substring safety net caveat
- `Archon/packages/workflows/src/defaults/bundled-defaults.test.ts` — test-level parity
- `Archon/packages/workflows/src/loader.ts:39-62, 106-129, 134-221, 303-378` — severity boundary
- `Archon/packages/workflows/src/schemas/dag-node.ts:1-13, 260-378` — schema as SSOT
- `Archon/packages/workflows/src/schemas/index.ts`
- `Archon/packages/workflows/src/command-validation.ts` — tiny validator (Level 0 shape)
- `Archon/packages/workflows/src/validator.ts:43-70, 324-430` — ValidationIssue + hints
- `Archon/packages/docs-web/scripts/lint-marketplace.ts` — network-bound (negative evidence)
- `Archon/.github/workflows/test.yml:24-41` — CI parity ordering
- `Archon/.github/workflows/e2e-smoke.yml`
- `Archon/.github/workflows/marketplace-lint.yml`
- `Archon/.github/workflows/marketplace-auto-review.yml`
- `Archon/.husky/pre-commit`
- `Archon/.lintstagedrc.json`
- `Archon/.archon/workflows/experimental/archon-release.yaml`
- `Archon/.archon/workflows/maintainer/marketplace-pr-review-and-merge.yaml`

### 14.2 Grafema

- `grafema/package.json`
- `grafema/.grafema/guarantees.yaml` — three-tier severity corpus
- `grafema/packages/util/src/core/GuaranteeManager.ts:22-119, 213-348, 351-520` — lifecycle
- `grafema/packages/cli/src/commands/check.ts` — CLI check surface
- `grafema/packages/python-analyzer/src/Analysis/Walker.hs:1-65, 67-125` — AST routing
- `grafema/packages/python-analyzer/src/Rules/UnsafeDynamic.hs:1-43, 50-80, 82-128`
- `grafema/packages/js-analyzer/src/Analysis/Walker.hs`
- `grafema/packages/js-analyzer/src/Rules/Declarations.hs`
- `grafema/packages/util/src/core/GraphFreshnessChecker.ts:1-35, 39-91, 93-145`
- `grafema/packages/rfdb-server/src/datalog/eval.rs`
- `grafema/packages/rfdb-server/src/datalog/parser.rs`
- `grafema/packages/mcp/src/definitions/guarantee-tools.ts:6-68`
- `grafema/packages/mcp/src/handlers/guarantee-handlers.ts:22-78, 129-246`
- `grafema/scripts/test-regression.sh`
- `grafema/scripts/check-bench-regression.sh`
- `grafema/.github/workflows/ci.yml:123-140, 217-264`
- `grafema/.husky/pre-commit`
- `grafema/.husky/pre-push`
- `grafema/packages/util/src/manifest/types.ts`
- `grafema/packages/api/manifest.yaml`

### 14.3 NeMo Guardrails

- `Guardrails/pyproject.toml:46-115` — dependency footprint
- `Guardrails/.pre-commit-config.yaml`
- `Guardrails/.github/workflows/lint.yml`
- `Guardrails/.github/workflows/pr-tests-skip.yml:1-15` — negative prior art
- `Guardrails/nemoguardrails/guardrails/rail_action.py:16-68, 75-120`
- `Guardrails/nemoguardrails/guardrails/guardrails_types.py:20-41`
- `Guardrails/nemoguardrails/guardrails/rails_manager.py:16-23, 58-120, 151-225`
- `Guardrails/nemoguardrails/guardrails/iorails.py:74-120`
- `Guardrails/nemoguardrails/guardrails/engine_registry.py`
- `Guardrails/nemoguardrails/rails/llm/config.py`
- `Guardrails/nemoguardrails/actions/action_dispatcher.py:37-120, 171-250`
- `Guardrails/tests/test_config_validation.py:18-101`
- `Guardrails/tests/test_action_dispatcher.py`
- `Guardrails/nemoguardrails/library/ai_defense/actions.py`
- `Guardrails/docs/resources/security/guidelines.md`

### 14.4 First-Agent target

- `First-Agent-fork2/AGENTS.md`
- `First-Agent-fork2/HANDOFF.md`
- `First-Agent-fork2/knowledge/llms.txt`
- `First-Agent-fork2/knowledge/project-overview.md`
- `First-Agent-fork2/knowledge/adr/ADR-10-deterministic-harness-invariants.md`
- `First-Agent-fork2/knowledge/skills/pr-creation/SKILL.md`
- `First-Agent-fork2/Makefile:8-22`
- `First-Agent-fork2/pyproject.toml`
- `First-Agent-fork2/.github/workflows/ci.yml:1-32`
- `First-Agent-fork2/.pre-commit-config.yaml`
- `First-Agent-fork2/src/fa/hygiene/pr_intent.py:1-31, 41-117, 300-332`
- `First-Agent-fork2/tests/test_pr_intent_snapshot.py:1-15, 61-123`
- `First-Agent-fork2/src/fa/inner_loop/hooks/intent_guard.py:1-69`
- `First-Agent-fork2/src/fa/sandbox/bash_gate.py`
- `First-Agent-fork2/src/fa/chunker/` (multiple files)
- `First-Agent-fork2/src/fa/cli.py`
- `First-Agent-fork2/verifiers/`

### 14.5 Hermes Agent

- `hermes-agent/agent/file_safety.py` (453 LOC)
- `hermes-agent/tools/file_operations.py` (2143 LOC)
- `hermes-agent/tools/approval.py` (1624 LOC)
- `hermes-agent/agent/curator.py` (1800 LOC)
- `hermes-agent/.github/workflows/contributor-check.yml` (85 LOC)
- `hermes-agent/.github/workflows/skills-index-freshness.yml`
- `hermes-agent/AGENTS.md` (1132 LOC)
- `hermes-agent/toolsets.py`
- `hermes-agent/hermes_constants.py`

---

## §15. Out of Scope

This ADR explicitly does not cover:

1. **Implementing ADR-11 code.** This is the blueprint; implementation
   is in the PR sequence (Appendix B) and subsequent commits.
2. **Running upstream test suites.** OSS repos analysed for patterns only;
   upstream build health was not validated.
3. **Auditing GitHub branch protection settings.** CODEOWNERS enforcement
   settings not verified for any OSS repo.
4. **Full multi-language static analysis.** ADR-11 covers Python-only
   authoring rules. Bash parity is noted as future scope.
5. **Network-dependent marketplace/source checks in Level 0.** These are
   explicitly rejected from Level 0 (R-8) and deferred for separate
   optional commands (R-17).
6. **Dynamic rule creation by LLM/MCP.** R-12's protected-path governance
   and R-18's self-improvement constraints ensure no LLM-created rules
   in v0.1.
7. **Pre-commit as authoritative enforcement.** R-6 explicitly demotes
   pre-commit to convenience-only.

---

## Appendix A: R-N Summary Table

| R-N | Title | Verdict | Level | Priority | Cost |
|-----|-------|---------|-------|----------|------|
| R-1 | Level 0 authoring-check kernel | TAKE | 0 | P0 | medium |
| R-11 | Level 0 TCB: TOML + snapshot | TAKE | 0 | P0 | medium |
| R-2 | RuleResult severity lifecycle | TAKE | 0/1 | P0 | medium |
| R-6 | CI-enforced, always-run | TAKE | 0 | P0 | cheap |
| R-7 | Borrow concepts, not runtimes | TAKE | 0 | P0 | cheap |
| R-10 | LLM as Untrusted Compiler thesis | TAKE | 0 | P0 | cheap |
| R-12 | Protected-path governance bundle | TAKE | 0 | P0 | medium |
| R-15 | Hermes file-safety denylist pattern | TAKE | 0 | P0 | cheap |
| R-3 | Generated parity + I-FROZEN | TAKE | 1 | P1 | medium |
| R-4 | Python AST Visitor rules | TAKE | 1 | P1 | medium |
| R-5 | Test semantic decay lock | TAKE | 1 | P1 | cheap |
| R-13 | Session seam + bootstrap invariants | TAKE | 1 | P1 | medium |
| R-14 | Catch/FP corpus measurement loop | TAKE | 1 | P2 | expensive |
| R-8 | Skip network validation in Level 0 | SKIP | — | — | cheap |
| R-9 | CODEOWNERS standalone | SKIP | — | — | cheap |
| R-16 | Save-time feedback (DEFER) | DEFER | — | P3 | cheap |
| R-17 | Network freshness watchdog (DEFER) | DEFER | — | P3 | cheap |
| R-18 | Self-improvement guardrails (DEFER) | DEFER | — | P3 | medium |

**Priority tiers:**
- **P0:** Required for first working version (PR 1–2)
- **P1:** Required for production parity (PR 3–4)
- **P2:** Required for severity measurement and tuning (PR 5)
- **P3:** Future enhancement (post-v0.1)

---

## Appendix B: Production Rollout Sequence

```
PR 1  ████████████████████░░░░░░░░░░░░░░░░░░  TCB skeleton + governance
      └── R-1, R-11, R-2, R-6, R-7, R-10, R-12, R-15 ──┘

PR 2  ██████████████████████████░░░░░░░░░░░░  First Level 1 teeth
      └── R-4 (exports), R-5 (tests) ────────┘

PR 3  ██████████████████████████████████░░░░  Parity + docs
      └── R-3 (parity), R-4 (docs) ──────────┘

PR 4  ██████████████████████████████████████  Corpus harness + seam
      └── R-13 (seam), R-14 (corpora) ───────┘

PR 5  ██████████████████████████████████████  Advisory experiments
      └── messages rule + severity tuning ───┘

      └── P0 ──┘└── P1 ──────────┘└── P2 ──┘
```

**Phase gates:**
- After PR 1: `fa authoring-check` exists and reports for every commit
- After PR 2: meaningful HARD-BLOCK protection for tests/exports
- After PR 3: generated parity cannot drift silently
- After PR 4: severity promotion is measurement-based, not subjective
- After PR 5: advisory experiments validated before promotion to HARD-BLOCK

### PR 1 — TCB skeleton + protected-path governance

Files:
```
src/fa/authoring_tcb.py                # Level 0 kernel
src/fa/authoring_rules/__init__.py     # Rule protocol + static allowlist
.github/CODEOWNERS                     # Protected paths
.github/workflows/authoring-guardrails.yml  # CI workflow (always-run)
scripts/check_protected_paths.py       # Diff checker
Makefile                               # check: ... authoring-check test
```

Deliverables:
- `fa authoring-check --help` works
- TOML manifest parsed via `tomllib`
- Sorted path enumeration
- SHA-256 snapshot/rule-pack/kernel hashing
- Zero rules → empty diagnostic output
- CI workflow always reports status (pass/skip)
- Protected paths governance documented

### PR 2 — First Level 1 rules (exports + tests)

Files:
```
src/fa/authoring_rules/exports.py      # V2: __all__ completeness
src/fa/authoring_rules/tests.py        # V4/V10/V11: test semantics
```

Deliverables:
- `exports.py`: public symbol not in `__all__` → ADVISORY
- `tests.py`: `pytest.skip` → HARD-BLOCK, `assert True` → HARD-BLOCK
- Snapshot test for each rule (positive + negative fixtures)
- Rule diagnostics appear in structured JSON output

### PR 3 — Parity + docs rules

Files:
```
src/fa/authoring_rules/parity.py       # V3: generated parity
src/fa/authoring_rules/docs.py         # V5: doc integrity
```

Deliverables:
- `parity.py`: SKILL.md ↔ pr_intent.py constant parity check
- `docs.py`: markdown relation rules (cross-reference validation)
- `I-FROZEN` marker convention documented

### PR 4 — Session seam + catch/FP corpora

Files:
```
src/fa/authoring_rules/seam.py         # V6: session seam
.fa/session.toml                       # Session manifest schema
catch-corpus/                          # Historical omission fixtures
fp-corpus/                             # Green commit corpora
```

Deliverables:
- `seam.py`: staged paths ⊆ declared seam
- `.fa/session.toml` schema defined
- F-1..F-10 committed as fixture diffs
- FP-corpus baseline measured

### PR 5 — Advisory experiments + severity tuning

Files:
```
src/fa/authoring_rules/messages.py     # V12: message registry
```

Deliverables:
- `messages.py`: bracketed message format rule
- ADVISORY rules with expiry dates
- False-positive rate measurement
- Severity promotion criteria documented
