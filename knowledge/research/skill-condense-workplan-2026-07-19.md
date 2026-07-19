# Workplan: Condense tests-writing SKILL.md by ~20%

> **Created:** 2026-07-19
> **Current:** 891 lines
> **Target:** ≤710 lines (≥20% reduction)
> **Method:** Remove, merge, and tighten — never weaken rules

---

## Phase 1: Remove user-specified sections (est. -92 lines)

| # | What | Lines | Action |
|---|------|-------|--------|
| 1a | Trigger section (§Trigger) | 21 | REMOVE — triggers already in YAML frontmatter, which the skill loader reads. Duplicating them in the body wastes tokens and adds no value. |
| 1b | §18 Sibling skills | 14 | REMOVE — agents can discover sibling skills via the skill directory or AGENTS.md. Listing them here adds no normative guidance. |
| 1c | §19 Authority vs steering | 13 | REMOVE — the concept is already expressed by I-TW-2 ("Authority is pytest in `just check`") and the Escalation table. No new information. |
| 1d | Prior art section | 18 | REMOVE — historical context doesn't change how the agent writes tests. The PR53 structural fix scripts are referenced in the contract check section where they're actionable. |
| 1e | References section | 10 | REMOVE — ADR links are valuable but the agent already has them in AGENTS.md and in the invariants (I-TW-2, I-TW-11). The root-cause-analysis link is in the contract check section. None are needed at the end. |
| 1f | Decision points (simplify) | 22→10 | COMPRESS from 16 enumerated items to a single-line-per-item list. The decision tree at the top already covers these in detail. The bottom list is redundant; keep only the items NOT already in the decision tree (items 4-9 are the gap-fix additions). |

**Phase 1 subtotal: ~-92 lines → ~799 lines**

---

## Phase 2: Dissolve Adaptation Guide into skill body (est. -20 lines net)

| # | What | Lines | Action |
|---|------|-------|--------|
| 2a | Adaptation guide table (33 lines) | 33 | DISSOLVE — add one-line universal translations as parentheticals at the FIRST mention of each FA concept, then remove the section. E.g., in §8.1: "For every **EventType** (universal: observable signal) in output.py..." This embeds the universality into the rule text without a separate section. After embedding, remove the §Adaptation guide (saves ~33 lines, adds ~13 lines of parentheticals). |

Embedding plan — add universal parentheticals at first mention:

| FA concept | Where first mentioned | Universal parenthetical |
|---|---|---|
| EventType | §8.1, central laws | (universal: any observable signal — event, API, message) |
| output.emit() | §8.2, central laws | (universal: code that produces the signal) |
| _handle_X() | §8.3, central laws | (universal: code that consumes/handles the signal) |
| drive_session | §1 | (universal: the composition root / main entry point) |
| FeatureFlags | §4 | (universal: configuration / feature flags) |
| HookRegistry | §5 | (universal: middleware / plugin registry) |
| ProviderChain.request | §1 | (universal: external I/O boundary) |
| SessionOutcome | §6 | (universal: entry-point result code) |
| ContextBudget | §5 | (universal: resource / budget policy) |
| log.append() + output.emit() | §10 | (universal: any dual-write — persist + notify) |
| just check | central laws | (universal: CI gate command) |

**Phase 2 subtotal: ~-20 lines net → ~779 lines**

---

## Phase 3: Remove meta-commentary (est. -25 lines)

| # | What | Lines | Action |
|---|------|-------|--------|
| 3a | ADR refs in central laws | ~5 | Remove "ADR-11-I6", "ADR-11-I9" from central law blockquotes. These are implementation details, not rules. The invariants already reference them. |
| 3b | PR #53 origin stories | ~12 | Remove "This section addresses the 'not wired / partial implementation' bug class that caused 6 failures in PR #53" from §8, §9, §10. These are historical context, not normative guidance. The rules stand on their own. |
| 3c | Verbose section headers | ~4 | Simplify: "### 8. Two-sided contract verification (CRITICAL)" → "### 8. Two-sided contract verification". "### 9. Path inventory (mandatory for EventType claims)" → "### 9. Path inventory". Remove parenthetical qualifiers from headers — the rules inside are already mandatory. |
| 3d | Redundant "the problem" subsections | ~4 | §9.1 "The problem" and §10.1 "The problem" repeat the rule text. Merge the problem statement into the rule. Saves 2 subsection headers + 2 redundant paragraphs. |

**Phase 3 subtotal: ~-25 lines → ~754 lines**

---

## Phase 4: Trim Gold files and Worked examples (est. -28 lines)

| # | What | Lines | Action |
|---|------|-------|--------|
| 4a | §16 Gold files: keep best 3 | 19→8 | Keep test_pr1_wiring.py (canonical C1 pattern), test_coder_loop.py (mature trajectory patterns), test_event_type_c1_producers.py (new producer-test pattern). Remove the other 6 entries. |
| 4b | Worked examples: merge C0 examples | 16→8 | The "C0 complete for class API" and "C0 consumer-only — theater" examples make the same point. Merge into one example that shows both the C0 consumer test and the warning that it needs a C1 pair. |

**Phase 4 subtotal: ~-28 lines → ~726 lines**

---

## Phase 5: My suggested high-ROI simplifications (est. -16 lines)

| # | What | Lines | Action |
|---|------|-------|--------|
| 5a | §7 Trajectory and event assertions → inline into §6 | 35→25 | §7 is 35 lines of code examples that repeat what §6 (Ranked oracles) already describes. Merge the assertion patterns INTO the oracle rank table as a "Example assertion" column. One table row = oracle + how to assert it. Eliminates an entire section. |
| 5b | §11 Kill-check mechanics → fold into §3 item 2 | 44→36 | §11 is 44 lines but adds only 3 concepts beyond what §3 already says: (a) kill-check target = producer, (b) vacuous pass detection, (c) two kill-checks for contracts. Items (a) and (b) are already in §3 items 2 and 1. Item (c) is a small addition. Fold the unique content into §3, remove §11 as a standalone section. |
| 5c | "What CI / hooks validate" → merge into §17 | 15→5 | This 15-line table is largely redundant with I-TW-2 and I-TW-19. Merge the 2 non-redundant rows (meaningful asserts, test path edits) into §17 Naming/CI as bullet points. Remove the section. |

**Phase 5 subtotal: ~-16 lines → ~710 lines**

---

## Summary

| Phase | Action | Est. lines saved |
|-------|--------|-----------------|
| 1 | Remove Trigger, Sibling, Authority, Prior art, References; simplify Decision points | -92 |
| 2 | Dissolve Adaptation Guide into parentheticals | -20 |
| 3 | Remove meta-commentary (ADR refs, PR#53 stories, verbose headers) | -25 |
| 4 | Trim Gold files to 3, merge worked examples | -28 |
| 5 | My suggestions: merge §7→§6, fold §11→§3, merge CI→§17 | -16 |
| **Total** | | **-181** |

**891 - 181 = 710 lines (20.3% reduction)**

---

## Execution order

Phases 1-3 are non-controversial removals. Execute first.
Phase 4 requires judgment on which examples to keep. Execute second.
Phase 5 requires structural merging. Execute last (most risk of introducing errors).

After each phase: verify with `wc -l` and check doc links.

---

## What I will NOT cut

- Any of the 10 gap-fix rules (§8-12 core content)
- Any of the 19 invariants
- The decision tree (it's the most-read section)
- The anti-theater checklist (it's the reference the agent actually follows)
- The ranked oracles table (it's the most actionable guidance)
- The escalation table (it maps failure modes to actions)

These are the load-bearing walls. Everything else is trim.
