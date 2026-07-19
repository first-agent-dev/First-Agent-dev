# Research Briefing: Independent Verification of Guardrail Gap Analysis

## Your Task

You are an expert research agent specializing in LLM reliability engineering, software architecture governance, and AI-assisted development workflows. Your job is to perform an **independent, adversarial analysis** of a guardrail gap assessment for the First-Agent (FA) project — an open-source LLM coding-agent harness.

You must find what the previous analysis missed, overclaimed, or got wrong. You must bring a different lens. The goal is not agreement — it is stronger claims through independent verification.

---

## Repository

**GitHub**: `https://github.com/MondayInRussian/First-Agent-dev`

Read the repository structure first. Key files to read (in order of priority):

1. `AGENTS.md` — the steering document for LLM agents working in this repo
2. `knowledge/skills/tests-writing/SKILL.md` — the test-writing methodology
3. `knowledge/research/deep-research-failure-mode-closure-2026-07-19.md` — previous deep research on discriminated unions, Parse-Don't-Validate, and property-typed state
4. `knowledge/research/missing-guardrail-dimensions-2026-07-19.md` — the gap analysis you are verifying (v2)
5. `src/fa/authoring_tcb.py` — the Level-0 authoring guardrail kernel
6. `src/fa/authoring_rules/` — Level-1 authoring rules (exports completeness, test semantic decay, placeholder assertions)
7. `scripts/check_producer_consumer_contract.py` — contract verification script
8. `scripts/check_dead_flags.py` — feature flag liveness check
9. `scripts/check_protected_paths.py` — TCB path governance
10. `knowledge/adr/` — architectural decision records
11. `justfile` — the CI gate definitions
12. `.pre-commit-config.yaml` — pre-commit hooks
13. `pyproject.toml` — project configuration including deptry, mutmut, coverage

---

## Context: What Problem Are We Solving?

The FA project is an LLM coding-agent harness. Code is written primarily by LLMs (Claude Code, Devin, Cursor). The project has built an extensive authoring-time guardrail stack:

- **ADR-11 two-tier TCB**: Level-0 kernel (frozen, stdlib-only) + Level-1 rules (dispatched by kernel)
- **Level-1 authoring rules**: V2 (exports completeness), V4 (test semantic decay — skip/xfail/focus), V11 (placeholder assertions)
- **Contract checks**: producer-consumer verification for 14 EventTypes
- **Feature flag governance**: dead-flag detection, phantom-flag detection
- **Protected-path governance**: TCB path changes flagged for human review, dependency manifest changes flagged
- **Pre-commit / pre-push hooks**: ruff, mypy, deptry, gitleaks, doc-link checking
- **PR-intent classification**: 5-intent closed-enum classifier with commit-msg validation
- **Mutation testing**: scheduled weekly via mutmut

The question: **what failure modes are still not caught by this guardrail stack, specifically for code written by LLM agents?**

---

## The Previous Analysis (v2) Found 10 Gaps

1. G6: Error message actionability (HIGH) — error messages must be self-contained and actionable for LLM feedback loops
2. G9: Harness observability / meta-metrics (HIGH) — no data on which guardrails are effective
3. G2: Correction compilation / TRACE pattern (HIGH) — corrections are ephemeral, not compiled into rules
4. G1: Architecture fitness via import-linter (MEDIUM) — no enforcement of module layering
5. G11: Context rot defense (MEDIUM) — session-internal degradation from context growth
6. G4: Inferential sensors (MEDIUM) — all sensors are computational; none use semantic judgment
7. G12: Supply-chain slopsquatting (MEDIUM) — hallucinated package names by LLMs
8. G13: Behavioral contract enforcement (MEDIUM) — runtime contracts for FA's own agent loop
9. G3: ADR invariant enforcement (LOW-MEDIUM) — ADRs are prose, not executable contracts
10. G5: Self-correction loop bounding (LOW) — no cap on LLM retry loops

---

## Your Specific Research Questions

### Q1: Operator Experience Gaps
The previous analysis focused on **authoring-time** and **CI-time** controls. It mostly missed **operator-time** (runtime) failures — the person running `fa run` who sees the agent loop misbehave. What guardrails does an operator need that the current stack doesn't provide? Think about:
- Observable signals during a running session (not just after it ends)
- Abort conditions that should trigger automatically
- Operator-facing error messages vs developer-facing error messages

### Q2: The "Good Enough" Boundary
Not every gap needs a guardrail. Some failure modes are rare enough, cheap enough to fix, or well-enough caught by existing mechanisms that adding a dedicated control is over-engineering. For each of the 10 gaps, make a concrete argument for whether it crosses the "good enough" threshold. Use the FA codebase's own subtraction-first principle as your guide.

### Q3: Prompt-as-Control vs Code-as-Control
The previous analysis treated AGENTS.md and skills as "guides" (feedforward) and scripts/tests as "sensors" (feedback). But in practice, AGENTS.md rules often function as de facto sensors — an LLM that violates an AGENTS.md rule will be corrected in the review loop. Where does the FA codebase rely on prompt-level controls that should be code-level controls? Where does it have code-level controls that would be better as prompt-level controls (less surface, more flexible)?

### Q4: Cross-Layer Interaction Failures
The previous analysis treated each gap independently. But many real failures come from **interactions** between layers. For example: an import-linter rule might prevent a cross-layer import, but the LLM might work around it by using `importlib.import_module()` dynamically. What interaction failures between existing and proposed guardrails does the analysis miss?

### Q5: Failure Modes Specific to Python + Dataclasses
FA uses Python 3.13 with frozen dataclasses extensively. The mocked-dataclasses anti-pattern was already caught. But what other Python-specific failure modes exist when LLMs write code against frozen dataclasses? Think about:
- `__post_init__` mutations that silently fail
- `frozen=True` bypasses via `object.__setattr__`
- `slots=True` interaction with inheritance
- Pattern-match exhaustiveness (Python doesn't enforce it)

### Q6: What Production Systems Do That FA Doesn't
Cursor uses: risk scoring, behavioral artifacts (video/screenshot evidence), Bugbot (review agent that learns from corrections), 150 skills with pruning discipline, developer-like environments for agents, OS-level sandboxing. Claude Code uses: 7-layer permission classifier, hooks (PreToolUse/PostToolUse/Stop), skills, subagents, managed settings. What specific techniques from these systems are highest-ROI for FA to adopt? Don't list everything — pick the 3 that would close the most failure modes for the least implementation cost.

### Q7: The Meta-Question — Is the Guardrail Stack Itself a Liability?
Could the extensive guardrail stack be creating failure modes of its own? Think about:
- LLMs that learn to satisfy the linter without satisfying the intent (Goodhart's law)
- False confidence from passing all checks
- Maintenance burden of the guardrail infrastructure
- Context budget consumed by AGENTS.md + skills + authoring rules (is there a point where more rules = less compliance?)

---

## Methodology

1. **Read the code.** Don't rely on summaries. Open the actual source files and trace the control flow. The repository is small enough to read in a single session.

2. **Adversarial stance.** For every claim in the v2 analysis, ask: "What evidence would falsify this?" Then look for that evidence.

3. **Cross-reference research.** Search for the specific papers and articles cited. Verify the numbers. If a claim says "57.5% violation reduction," find the original source and check the experimental setup — was it in a domain comparable to FA?

4. **Production evidence.** For each proposed gap, find at least one real-world production system (Cursor, Claude Code, Codex CLI, Devin, Kiro) that implements or explicitly rejects the proposed solution. Quote their reasoning.

5. **Quantify.** Where possible, estimate the expected failure rate of the unguarded failure mode. A gap that prevents 1 bug per year is different from one that prevents 1 bug per week.

6. **Write your findings as a document** in `knowledge/research/external-verification-guardrail-gaps-YYYY-MM-DD.md` following the same format as the existing research notes.

---

## Deliverable

A markdown document containing:

1. **Per-gap verification** — for each of the 10 gaps: CONFIRMED / WEAKENED / REJECTED / REFINED, with evidence
2. **New gaps found** — any failure modes the previous analysis missed
3. **Interaction analysis** — cross-layer failure modes between proposed guardrails
4. **"Good enough" assessment** — which gaps don't justify dedicated controls
5. **Production system comparison** — what Cursor/Claude Code/Codex CLI do that FA should/shouldn't adopt
6. **Meta-assessment** — is the guardrail stack itself a liability?
7. **Reprioritized action list** — top 5 actions by verified yield/effort ratio

---

## Constraints

- Do NOT modify any source code. This is a research-only task.
- Do NOT add new dependencies or tools. Recommendations only.
- Do NOT rewrite AGENTS.md or any skill files.
- Cite every claim with a URL or repository path.
- If you cannot verify a claim, say so explicitly — do not guess.
- Follow the FA codebase's own conventions: ATX headings, short lines, fenced code blocks with language tags.
