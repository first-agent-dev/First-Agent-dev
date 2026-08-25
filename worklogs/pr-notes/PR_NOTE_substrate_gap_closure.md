# PR NOTE — Substrate Gap Closure (substrate → main)

**Date:** 2026-07-16
**Branch:** substrate
**Intent:** FIX — Close Stage A/B/C substrate gaps + harden authoring guardrails per ADR-11 I9
**Scope:** Vast — DB authority, observability, Stage C, governance, subagent, bash/PTY, scheduler/search, logging, global export, authoring wiring

---

## Brief (not verbose)

This PR lands the full substrate modernization that was partially present as code + unit-green but unwired from live session path (Stage C theater class).

Instead of verbose feature list, this note points to the workplans that scheduled and tracked progress:

**Decision Freeze & Workplans (scheduling):**

- Decision freeze D8/D9/D10: [`substrate-decision-freeze-2026-07-15.md`](../../worklogs/archive/substrate-decision-freeze-2026-07-15.md)
- Gap-closure workplan round2 (FIND-001..018, 11 slices): [`substrate-gap-closure-workplan-round2-2026-07-15.md`](../archive/substrate-gap-closure-workplan-round2-2026-07-15.md)

**Slice implementation plans (execution):**

- Slice 0/1 prep: [`substrate-slice0-slice1-implementation-plan-2026-07-15.md`](../archive/substrate-slice0-slice1-implementation-plan-2026-07-15.md)
- Slice 1 closure + Slice 2 init: [`substrate-slice1-closure-pass-and-slice2-init-2026-07-15.md`](../../worklogs/archive/substrate-slice1-closure-pass-and-slice2-init-2026-07-15.md)
- Slice 2 patch design (observability): [`substrate-slice2-patch-design-2026-07-15.md`](../archive/substrate-slice2-patch-design-2026-07-15.md)
- Slice 3 patch design (Stage C): [`substrate-slice3-patch-design-2026-07-15.md`](../archive/substrate-slice3-patch-design-2026-07-15.md)
- Slice 4 patch design (governance): [`substrate-slice4-patch-design-2026-07-15.md`](../archive/substrate-slice4-patch-design-2026-07-15.md)
- Slice 5-7 closure (safety & execution truthfulness): [`substrate-slice5-6-7-closure-2026-07-15.md`](../../worklogs/archive/substrate-slice5-6-7-closure-2026-07-15.md) + state assessment [`substrate-state-assessment-2026-07-15-round3.md`](../../worklogs/archive/substrate-state-assessment-2026-07-15-round3.md)

**Slice 9 (global history):**

- Patch design: [`substrate-slice9-patch-design-2026-07-15.md`](../../worklogs/archive/substrate-slice9-patch-design-2026-07-15.md)
- Closure: [`substrate-slice9-closure-2026-07-15.md`](../../worklogs/archive/substrate-slice9-closure-2026-07-15.md)

**Authoring hardening (ADR-11 I9):**

- Amendment I9: [`ADR-11-authoring-guardrails.md`](../../knowledge/adr/ADR-11-authoring-guardrails.md) Amendment 2026-07-15
- Skill: [`tests-writing`](../../knowledge/skills/tests-writing/SKILL.md)
- Compliance review: [`substrate-tests-writing-compliance-2026-07-15.md`](../../knowledge/research/substrate-tests-writing-compliance-2026-07-15.md)
- Workplan v1: [`authoring-hardening-workplan-2026-07-16.md`](../../worklogs/archive/authoring-hardening-workplan-2026-07-16.md)
- Workplan v2 (gap review + ROI): [`authoring-hardening-workplan-v2-2026-07-16.md`](../../knowledge/research/authoring-hardening-workplan-v2-2026-07-16.md)

---

## What shipped (high level, not verbose)

- Unified per-run DB authority `session.db` (event_log + blackboard + session_meta), JSONL mirror-only, split-brain fixed
- Observability `fs_usage` / `fs_chronicle_search` read active authority via DI + run_id, no path guessing
- Stage C: explicit warn/stage2/stage3 ladder (70/80/90), dynamic threshold, compactor model reaches provider body, fallback 4-header, cache-control preserved for Anthropic (structured system) and OpenAI (extras)
- Governance: PinnedBuffer wholesale refresh (no stale), resume draft → mutable summary not pinned, prompt order contract
- Subagent: role preserved (researcher vs verifier), spawn limit respects FeatureFlags > RuntimeLimits, env injection with secret filter, safety via hooks, spawn_start/done/fail events
- Bash: artifact API `put()` fix, binary capture preserving `\r`, CR cleaning via `resolve_cr`, PtyPool wired into live CLI + SessionState auto-creation, stateful cd/env persistence, subshell wrapping to preserve stateful vs exit
- Scheduler: parallel batch preserves denied results in order
- Search: instant_grep read-only (no auto-index, no file creation when missing)
- Logging: 87 `print WARNING` → `logger.warning`
- Global history: `~/.fa/global_history.db` derived projection, WAL, idempotent INSERT OR REPLACE, concurrent safe, best-effort failure, `fa stats --global-history` active consumer
- Authoring: exports completeness HARD-BLOCK fixed (8 → 0), shared fixture `tests/fixtures/session_wiring.py`, C1 wiring suites for slices 5-7 + global history (14 tests), C2 for authoring allowlist + protected-paths parity + workflow no paths filter, dead flags sweep (runtime_mode, prompt_cache_key_per_role removed; pty_pool_max_size, fts_db_path wired)

---

## Verification

- `fa authoring-check` 0 diagnostics
- `pytest -q --ignore pty_persistence` 1526 passed + 6 new global_history + 8 new slice5_6_7 wiring + 5 new authoring wiring = 1545+ total
- `uv lock --locked` pass
- `rg "paths:" .github/workflows/authoring-guardrails.yml` with comment-aware check → no YAML key paths: (always-run per ADR-11-I6)

---

## Non-goals (locked)

No STATUS enums, no wiring-allowlist.toml, no new fs.* wiring-check tools, no CodeGraph gate, no LLM judge in CI, no human commit-msg strictness increase, no replacement of blueprint PR3 packs with I9.

---

## Active consumers per AGENTS rule #3

- EventLog → `fa stats` + `fa stats --global-history` (global_history.db) + `GlobalHistoryStore`
- Blackboard → `fs_write_file` / `edit_file` conflict detection
- ArtifactStore → `fs_run_bash` large output offload
- Global history write → `fa stats --global-history` read (new active consumer)
- PtyPool → `fs_run_bash` stateful

---

## LIVE-PATH PROOF (sample, full set in closure docs)

```
LIVE-PATH PROOF:
- root: drive_session
- test: tests/test_slice5_6_7_wiring.py::test_pr6_wiring_bash_large_output_offloads_artifact_via_live_path
- matrix: C-defaults
- oracle: event:tool_result with artifact_id + truncated
- kill-check: removing put() fails
- pyramid: A

LIVE-PATH PROOF:
- root: cli:authoring-check via run_all(..., rules=RULE_ALLOWLIST)
- test: tests/test_authoring_wiring.py::test_authoring_check_catches_f2_via_default_allowlist
- matrix: C-defaults
- oracle: diagnostic code FA-AUTHORING-V2-EXPORTS-COMPLETENESS
- kill-check: removing EXPORTS_COMPLETENESS from allowlist fails
- pyramid: A, C2
```

---

## Next (for next session/agent)

- Finish dead flags sweep (pty_pool_max_size, fts_db_path wired, runtime_mode/prompt_cache_key removed — done in this PR, but script `scripts/check_dead_flags.py` to be added)
- Extract shared fixture into gold `test_pr1..5_wiring.py` (reduce duplication)
- More C1 for slices 1-5 present vs promised + list_tasks + termination
- Doc cleanup enormous: project-overview, llms.txt, instructions, AGENTS, HANDOFF, DIGEST, README (prioritized in workplan v2)
- Blueprint PR3 parity/docs as ADVISORY with expires_on 2026-08-15 (optional)
- Final hostile re-audit Slice 10
