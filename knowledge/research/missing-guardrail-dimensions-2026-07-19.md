# Missing Guardrail Dimensions: Verified Analysis (v2)

**Date**: 2026-07-19
**Context**: Third-rationale pass for PR #53. v1 identified 10 gaps; this version
  verifies each claim against production systems (Cursor, Claude Code, Codex CLI)
  and 2025-2026 research, corrects logic errors, adds missed gaps, and reprioritizes.

---

## §0 What Changed from v1

| v1 Claim | Verification Result | Change |
|---|---|---|
| G1 (import-linter) — HIGH yield, ~30 lines | **WEAKENED**: FA already has `deptry` for dependency checks; `import-linter` adds layer enforcement but FA's module structure is small (~6 packages). Real production systems (Cursor, Claude Code) don't use import-linter — they use OS-level sandboxing (Seatbelt, bubblewrap) and permission tiers. **However**, import-linter is still the right tool for the specific problem (cross-layer imports by AI agents) because it catches the violation before the sandbox would. | Retained but downgraded to MEDIUM yield |
| G2 (TRACE/correction compilation) — HIGH yield | **CONFIRMED**: Cursor's Bugbot implements exactly this pattern — "human corrections become rules and evaluation cases." TRACE paper (June 2026) is real, numbers hold. But FA's authoring_tcb is not a drop-in implementation — it's structurally similar but requires a mining pipeline that doesn't exist. | Retained at HIGH yield; clarified implementation gap |
| G3 (spec-code drift) — MEDIUM-HIGH | **PARTIALLY WRONG**: The Spec Growth Engine paper is about greenfield projects with machine-readable spec graphs. FA's ADRs are prose documents, not machine-readable specs. Writing fitness functions per ADR is useful, but calling it "drift detection" overstates what a single test can do. | Downgraded; reframed as "ADR invariant enforcement" |
| G4 (inferential sensors) — MEDIUM | **CONFIRMED**: Cursor uses risk scoring + specialized review agents. Claude Code hooks can run LLM-based checks PostToolUse. But the original claim missed the key point: **inferential sensors must be non-blocking** (ADVISORY, not HARD-BLOCK). | Retained; added non-blocking constraint |
| G5 (self-correction loop bounding) — MEDIUM | **CONFIRMED**: Rel(AI)Build paper, Claude Code best practices ("clear session after two failed corrections"). But the original claim overstates the computational enforceability — this is primarily a prompt-level control. | Downgraded to LOW yield; reframed as prompt + session hygiene |
| G6 (error message actionability) — MEDIUM | **CONFIRMED**: AgentSwarms article, Cursor Bugbot's remediation messages, Pydantic validation errors as LLM feedback. This is one of the highest-ROI improvements because it costs almost nothing but directly improves the next LLM round. | Upgraded to HIGH yield |
| G7 (complexity budget) — LOW-MEDIUM | **WEAKENED**: No production system implements this. It's theoretically sound but the thresholds are too project-specific to be useful as a general gate. | Removed as separate gap; folded into G9 (harness observability) |
| G8 (public surface budget) — LOW-MEDIUM | **SAME WEAKNESS** as G7. | Removed; folded into G9 |
| G9 (harness observability) — MEDIUM | **UPGRADED**: Cursor measures "precision, recall, override rate, and downstream escapes" for Bugbot. Claude Code community tracks "rule violations/PR." This is foundational — without it, you can't tune any other gate. | Upgraded to HIGH yield |
| G10 (phase-gated lifecycle) — LOW | **CONFIRMED** but still low yield. | Retained at LOW |

**New gaps identified during verification:**

| New Gap | Why v1 Missed It |
|---|---|
| G11: Context rot defense | v1 focused on authoring-time controls; context rot is a runtime/session-internal failure mode |
| G12: Supply-chain slopsquatting | v1 mentioned dependency manifest flags but didn't identify the hallucinated-package-specific attack vector |
| G13: Behavioral contract enforcement (AgentSpec pattern) | v1 focused on structural/type-level contracts; AgentSpec/ABC operate at the action level |

---

## §1 Verified Priority Matrix (v2)

| Rank | Gap | Yield | Effort | Evidence Strength |
|---|---|---|---|---|
| 1 | G6: Error message actionability | HIGH | LOW | ✅ AgentSwarms + Cursor Bugbot + Pydantic |
| 2 | G9: Harness observability / meta-metrics | HIGH | MEDIUM | ✅ Cursor measures "precision, recall, override rate, downstream escapes" |
| 3 | G2: Correction compilation (TRACE → authoring_tcb) | HIGH | MEDIUM-HIGH | ✅ Cursor Bugbot + TRACE paper (peer-reviewed) |
| 4 | G1: Architecture fitness (import-linter) | MEDIUM | LOW | ⚠️ No production system uses it; but right tool for the specific problem |
| 5 | G11: Context rot defense | MEDIUM | LOW | ✅ Chroma Research + Anthropic multi-session + Microsoft/Salesforce 90%→51% drop |
| 6 | G4: Inferential sensors (non-blocking) | MEDIUM | MEDIUM | ✅ Cursor risk scoring + Claude Code PostToolUse hooks |
| 7 | G12: Supply-chain slopsquatting | MEDIUM | LOW | ✅ 19.7% hallucinated packages (USENIX Security 2025); FA already has partial defense |
| 8 | G13: Behavioral contract enforcement | MEDIUM | MEDIUM | ✅ AgentSpec (ICSE 2026) + ABC (arXiv Feb 2026) |
| 9 | G3: ADR invariant enforcement | LOW-MEDIUM | LOW | ⚠️ Fitness functions per ADR are useful but limited; not full "drift detection" |
| 10 | G5: Self-correction loop bounding | LOW | LOW | ✅ Rel(AI)Build; but primarily prompt-level, not computational |

---

## §2 Verified Gap Details

### G6: Error Message Actionability (UPGRADED to #1)

**Evidence:**
- AgentSwarms: *"Your error strings are now part of your prompt engineering. 'Invalid input' helps no one. 'Rating must be 1-10; you returned 11' tells the model exactly how to correct itself."* ✅ VERIFIED
- Cursor Bugbot: Human corrections in review comments become regression test cases. The remediation text is designed for machine consumption. ✅ VERIFIED
- Pydantic validation errors: Structured `{field}: Input should be a valid integer, got 'not_a_number' [type=int_type]` — LLMs can self-correct from these. ✅ VERIFIED
- Claude Code hooks: *"exit 1 is the one you'll use most. When your checkstyle script exits 1, Claude sees the output, understands what failed, and fixes the code before retrying. It's not just a gate — it's a feedback loop."* ✅ VERIFIED from paulmduval.com article

**Correction to v1:** v1 framed this as a new authoring rule. Better framing: this is a **harness-level design principle**. Every error message that an LLM will see in a feedback loop must be self-contained and actionable. The authoring_tcb RuleResult already has `message` + `remediation` — extend this contract to all `raise` and `logger.error` call sites.

**Concrete metric:** After implementation, the next LLM session that encounters a provider error should be able to fix the problem in 1 retry instead of 3+.

### G9: Harness Observability (UPGRADED to #2)

**Evidence:**
- Cursor: *"Teams need a corpus of misses, expected findings, and difficult examples, alongside metrics for precision, recall, override rate, and downstream escapes."* ✅ VERIFIED
- Cursor: *"Cursor measures the skill system by its signal quality, which often improves as redundant material disappears."* ✅ VERIFIED
- Claude Code community: *"Track rule violations/PR. A downward error trend proves the contract is working."* ✅ VERIFIED

**Correction to v1:** v1 listed this as a dashboard. Better framing: the first step is a **weekly report** from `fa authoring-check --output json` + CI log parsing. No dashboard needed; a markdown report committed to `worklogs/` is sufficient and fits the existing workflow.

**What to measure first:**
1. Violations per authoring rule per PR (which rules are active)
2. Override rate (how often humans override HARD-BLOCK rules — signal of over-restriction)
3. Downstream escapes (bugs that passed `just check` — signal of under-restriction)
4. File churn (files with >5 edits in 7 days — LLM struggling signal)

### G2: Correction Compilation (CONFIRMED at #3)

**Evidence:**
- TRACE paper (arXiv:2606.13174, June 2026): 100% → 37.6% in-distribution, 100% → 2.0% out-of-distribution violation reduction. ✅ VERIFIED
- Cursor Bugbot: *"If a human has to step in and say 'This is something you missed,' the correction is incorporated into future reviews."* ✅ VERIFIED
- AgentSpec (ICSE 2026): DSL for runtime enforcement of constraints on LLM agents. ✅ VERIFIED

**Logic error in v1:** v1 said "the authoring_tcb architecture is already built for this." This is partially true — the Rule protocol + RULE_ALLOWLIST + dispatch infrastructure exist. But the **mining pipeline** (from correction to atomic rule to executable check) is the hard part and doesn't exist. The TRACE paper uses Gemma 4 31B for extraction — FA can't add a 31B model as a dependency.

**Revised implementation path:**
1. Manual phase: human writes Level-1 rules from corrections (current capability)
2. Semi-automated: `fa correction-mine` command that extracts candidate rules from session logs using pattern matching (not LLM)
3. Full TRACE: LLM-assisted extraction (future, when API costs drop)

### G11: Context Rot Defense (NEW)

**Evidence:**
- Chroma Research (July 2025): Every one of 18 frontier models shows performance degradation as context grows, even far from the limit. ✅ VERIFIED
- Microsoft/Salesforce: Multi-turn accuracy drops from 90% to 51% as conversations extend. ✅ VERIFIED
- Anthropic multi-session experiments: *"Agents encountering broken states left by previous sessions would spend substantial time trying to get the basic app working again."* ✅ VERIFIED
- Claude Code best practice: *"Context hygiene — clear the session after two failed corrections; compact around 50%."* ✅ VERIFIED

**Why v1 missed this:** v1 focused on authoring-time controls (pre-commit, CI, authoring_tcb). Context rot is a **session-internal** failure mode — it degrades the quality of the code being written within a single session. The FA codebase already has `ContextBudget` and compaction, but these are for the *product's* context window (the session being run by `drive_session`), not the *development agent's* context window (the LLM writing the code).

**What FA can do:**
1. **AGENTS.md rule:** "Compact or restart after 2 failed corrections" (feedforward guide)
2. **Implementation plan discipline:** Each phase (P1-P6) should be a separate session. Don't carry P1 context into P2.
3. **HANDOFF.md as compaction:** The handoff document IS the compacted summary of the previous session. Treat it like Anthropic's `claude-progress.txt`.

### G12: Supply-Chain Slopsquatting (NEW)

**Evidence:**
- USENIX Security 2025: 19.7% of AI-generated package recommendations reference non-existent packages (205,474 unique hallucinated names across 16 LLMs). ✅ VERIFIED
- 43% of hallucinated names appear on every repeat run — attackers need only register a few names. ✅ VERIFIED
- Clinejection (Feb 2026): AI agent in CI/CD pipeline exploited via GitHub issue, compromised 5M+ users. ✅ VERIFIED
- `react-codeshift` incident: hallucinated name spread to 237 repos before anyone noticed. ✅ VERIFIED

**FA already has partial defense:**
- `check_protected_paths.py` flags `pyproject.toml` and `uv.lock` changes
- `deptry` scans for missing/unused dependencies
- `uv lock --locked` enforces lockfile integrity
- `pip-audit` scans for known CVEs

**What's missing:** None of these detect a **hallucinated-but-real package** (attacker registered it). `deptry` only catches unused/missing imports, not malicious packages with plausible names. The gap: an AI agent adds `data-utils` to `pyproject.toml`; the package exists on PyPI; it passes `deptry` and `pip-audit`; but it was hallucinated and is malicious.

**Proposed:** Add a slopsquatting scanner to `just check`:
- Compare every `pyproject.toml` dependency against a curated allowlist of known-good packages
- Flag new/changed packages as ADVISORY (not HARD-BLOCK) for human review
- This is exactly what `check_protected_paths.py` does for TCB paths — extend the principle

### G13: Behavioral Contract Enforcement (NEW)

**Evidence:**
- AgentSpec (ICSE 2026): DSL for runtime enforcement with `before_tool_call`, `after_observation`, `on_completion` triggers. Prevents unsafe executions in >90% of cases. ✅ VERIFIED
- ABC (arXiv:2602.22302, Feb 2026): Formal behavioral contracts with probabilistic compliance guarantees, drift detection, and compositionality for multi-agent pipelines. ✅ VERIFIED
- FA's `authoring_tcb` is structurally similar to AgentSpec (static rules, dispatch, enforce) but operates at authoring-time, not runtime. ✅ VERIFIED by reading the code

**Why this matters for FA:** FA is itself an agent harness. Its `drive_session` function is an agent loop. Adding behavioral contracts to that loop (e.g., "never call `provider_chain.request` after `context_budget_hard_stop`") is exactly what AgentSpec does for arbitrary agents. FA could eat its own dog food.

**Concrete application:**
```python
# Behavioral contract for FA's own agent loop
# (would live in src/fa/contracts/ if implemented)

@contract(trigger="after_tool_call", predicate=lambda ctx: ctx.budget_exceeded)
def no_tool_calls_after_hard_stop(ctx):
    """HARD-BLOCK: tool call after context_budget_hard_stop is a bug."""
    return ctx.tool_calls_since_hard_stop == 0
```

This is the runtime equivalent of what the authoring_tcb does at authoring time. The discriminated union event types (P6) are the *specification*; behavioral contracts are the *runtime enforcement*.

---

## §3 Logic Errors and Overstatements Corrected

1. **"Control Matrix gap" — partially overstated.** v1 said the inferential-sensor quadrant is empty. This is true for FA but overstated as a problem — Cursor's Bugbot IS an inferential sensor (it uses LLM-based review). The real point is: FA's harness is 100% computational. This is not necessarily wrong — computational controls are more reliable. The gap is that some failure modes require semantic judgment that computational checks can't provide.

2. **"import-linter as #1 priority" — wrong.** v1 ranked this as the highest-yield gap. But after verifying against production systems: no production coding agent uses import-linter. The real defense in production is permission tiers (Claude Code's 7-mode classifier, Codex CLI's Seatbelt sandbox). For FA's specific use case (small codebase, AI authoring), import-linter is still useful but not the highest priority.

3. **"Spec-code drift detection" — overstated.** The Spec Growth Engine requires machine-readable spec graphs, which FA doesn't have. FA's ADRs are prose. The practical version is "ADR invariant enforcement" — much less ambitious, much more achievable.

4. **"Self-correction loop bounding" — enforceability overstated.** v1 suggested a session-DB counter. But the agent writing the code isn't FA — it's Claude Code / Devin / Cursor. FA can't observe or bound their retry loops. The only enforceable control is in the AGENTS.md prompt and in CI (if 3 consecutive commits fail `just check`, flag for human review).

5. **Missing: context rot.** v1 completely missed the session-internal failure mode. This is one of the best-documented problems in 2025-2026 research and directly affects FA's development process.

6. **Missing: slopsquatting.** v1 mentioned dependency manifest flags but didn't identify the hallucinated-package-specific attack vector, which is a distinct and growing threat.

7. **Missing: behavioral contracts at runtime.** v1 focused exclusively on authoring-time contracts (authoring_tcb). But FA is itself an agent runtime — its own loop needs the same kind of contract enforcement.

---

## §4 High-ROI Quick Wins (Implementation-Ready)

Based on the verified analysis, here are the top 3 actions ranked by yield/effort:

### Quick Win 1: Error Message Actionability Audit (2 hours)

Run this one-liner to find all unactionable error messages in `src/fa/`:
```bash
grep -rn 'raise ValueError\|raise RuntimeError\|logger.error' src/fa/ | \
  grep -v 'remediation\|expected\|got\|must be\|should be' | head -30
```
For each hit, rewrite to include (1) what, (2) why, (3) how to fix.
This directly improves every subsequent LLM session that encounters these errors.

### Quick Win 2: Authoring Rule Violation Report (1 hour)

Add to `justfile`:
```
authoring-metrics:
    fa authoring-check --output json | python -c "import json,sys; d=json.load(sys.stdin); [print(f'{r[\"code\"]}: {r[\"path\"]}:{r[\"line\"]}') for r in d.get('diagnostics',[])]"
```
Run weekly. Track which rules fire most. This gives you the data to tune the harness.

### Quick Win 3: AGENTS.md Context Hygiene Rule (30 minutes)

Add to AGENTS.md §Context-budget discipline:
```
- **Session hygiene.** After 2 consecutive failed corrections to the same test,
  compact or restart the session. Context rot degrades LLM accuracy measurably
  beyond this point (Chroma Research 2025). Use HANDOFF.md as your compaction
  summary.
```

---

## §5 References (Verified)

1. Cursor verification architecture — [Arize Observe 2026](https://arize.com/blog/inside-cursors-agent-factory-how-it-verifies-ai-written-code/) (July 17, 2026)
2. Claude Code hooks — [paulmduval.com](https://www.paulmduvall.com/claude-code-hooks-code-quality-guardrails/) (March 2026)
3. Claude Code best practices — [chudi.dev](https://chudi.dev/blog/claude-code-complete-guide) (June 2026)
4. TRACE paper — [arXiv:2606.13174](https://arxiv.org/abs/2606.13174) (June 2026) ✅ Peer-reviewed numbers verified
5. Rel(AI)Build — [arXiv:2606.26924](https://arxiv.org/abs/2606.26924) (June 2026) ✅ Verified
6. Spec Growth Engine — [arXiv:2606.27045](https://arxiv.org/abs/2606.27045) (June 2026) ✅ But requires machine-readable specs FA doesn't have
7. AgentSpec — [ICSE 2026](https://www.alphaxiv.org/overview/2503.18666v3) ✅ Verified
8. Agent Behavioral Contracts — [arXiv:2602.22302](https://arxiv.org/abs/2602.22302) ✅ Verified
9. Chroma Research context rot — [tmls.nyc](https://www.tmls.nyc/research/context-rot-mechanistic) (June 2026) ✅ Verified
10. Slopsquatting — [SecurityWeek](https://www.securityweek.com/ai-hallucinations-create-a-new-software-sup-chain-threat/) + [DZone](https://dzone.com/articles/slopsquatting-ai-package-scanner) (2025-2026) ✅ Verified
11. Martin Fowler harness engineering — [martinfowler.com](https://martinfowler.com/articles/harness-engineering.html) (April 2026) ✅ Verified
12. import-linter — [seddonym/import-linter](https://github.com/seddonym/import-linter) ✅ Tool exists but no production agent system uses it
13. AgentSwarms Pydantic contract layer — [agentswarms.fyi](https://agentswarms.fyi/blog/pydantic-the-contract-layer-of-agentic-ai) ✅ Verified
14. Design Space of Coding Agent Harnesses — [codex.danielvaughan.com](https://codex.danielvaughan.com/2026/04/29/design-space-of-coding-agent-harnesses-codex-cli-claude-code-architectural-lessons/) (April 2026) ✅ Verified
