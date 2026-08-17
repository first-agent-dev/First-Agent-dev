# Slice 4 Patch Design — Governance Plane Repair

**Date:** 2026-07-15
**Scope:** Slice 4 only
**Purpose:** separate standing governance from mutable session context and repair `PinnedBuffer` semantics.

---

## 1. Slice 4 targets

Slice 4 addresses the governance-plane defects left open after Slices 1–3:

1. previous PR draft / resume text is currently routed through `PinnedBuffer`
2. `PinnedBuffer` keeps stale content when pinned files disappear
3. pinned-file hash handling exists, but runtime semantics are not cleanly defined
4. tests do not prove the separation between standing governance and mutable session history

Slice 4 does **not** take on:
- subagent hardening
- PTY/bash wiring
- global export
- broad logging migration

---

## 2. Locked product/architecture rule

### D9 (already accepted)

Previous PR draft / resume text must be inserted as **mutable non-cacheable summary/history**.

### Consequence
It must **not** be:
- part of `PinnedBuffer`
- represented as standing governance
- compaction-exempt pinned policy text

---

## 3. Desired runtime model after Slice 4

Prompt-layer separation should be:

1. base system prompt
2. standing governance pins (`PinnedBuffer` only)
3. tool definitions
4. mutable summary/history (including resume draft text)
5. live conversation/tail

This means:
- standing constraints remain outside compaction overwrite risk,
- resume text can be summarized later,
- operators and tests can distinguish the two planes.

---

## 4. Implementation design

## 4.1 Separate mutable resume context from pinned context

### Current problem
`fa.cli._cmd_run()` reads `resume_draft_text` and passes it into `drive_session(..., system_prompt_extra=resume_draft_text)`.

`coder_loop.py` then routes `system_prompt_extra` into:
- `PinnedBuffer.extract_pinned_content(extra_instructions=system_prompt_extra)`

This incorrectly promotes mutable resume text into standing profile guidance.

### Proposed fix
Introduce a new `drive_session()` parameter:
- `initial_memory_summary: str = ""`

Then:
- keep `system_prompt_extra` for actual standing profile guidance only
- route resume draft into `initial_memory_summary`
- initialize `memory_summary` from it before or alongside rebuilt compaction summary

### Merge rule
If both exist:
- `initial_memory_summary` from CLI resume draft
- `memory_summary` rebuilt from prior `compaction_stage3_done`

combine them deterministically into one mutable summary block.

Recommended ordering:
1. resumed context first
2. previously compacted summary second

Reason:
- resume draft is the operator/developer-provided immediate cross-session state
- previous compaction summary is older synthetic memory

---

## 4.2 Make `PinnedBuffer.refresh()` authoritative per turn

### Current problem
`refresh()` only updates entries for files that currently exist.
If a previously loaded pinned file disappears, its old cached content remains.

### Proposed fix
On each `refresh()`:
1. snapshot previously cached file keys/hashes
2. build fresh `new_cache` / `new_hashes`
3. replace internal caches wholesale
4. if a previously cached pinned file is now missing, log warning and omit it
5. if a pinned file changed hash since last refresh, allow it and log at warning/info level as defined

### Result
PinnedBuffer becomes a true current-state view of standing files, not a sticky cache.

---

## 4.3 Define honest hash semantics

### Problem
The current docs/comments imply “verification via SHA-256 content hashes”, but runtime behavior is really only “compute and embed current hash”.

### Proposed Slice 4 semantics
For now, define hash behavior as:
- each refresh recomputes current pinned-file content hash
- extracted text includes the current hash
- changes or disappearance across turns are observable
- no immutable expected-hash enforcement yet

This is not a cryptographic attestation system; it is a deterministic integrity marker.

### Scope discipline
Do **not** build a full expected-hash registry in Slice 4.
That would be a different feature.

---

## 4.4 Exact file edit map

### Primary files
- `src/fa/memory/pinned_buffer.py`
- `src/fa/inner_loop/coder_loop.py`
- `src/fa/cli.py`

### Tests
- `tests/test_pr2_wiring.py`
- `tests/test_compaction_sota.py`

---

## 5. Concrete code changes

## 5.1 `src/fa/memory/pinned_buffer.py`

### Needed changes
1. rework `refresh()` to replace caches wholesale
2. drop stale entries when files disappear
3. optionally log when:
   - previously loaded pinned file disappears
   - pinned file hash changes between turns
4. keep `extra_instructions` support for explicit standing profile guidance, but do not use it for resume draft text in runtime wiring

### Expected outcome
- no stale pinned sections survive deletion
- file changes reload cleanly
- hash text remains stable and current

---

## 5.2 `src/fa/inner_loop/coder_loop.py`

### Needed changes
1. add new parameter:
   - `initial_memory_summary: str = ""`
2. stop using `system_prompt_extra` as resume-draft carrier
3. initialize mutable summary from `initial_memory_summary`
4. merge it with any rebuilt compaction summary from log
5. continue to feed only true standing extra instructions to `PinnedBuffer.extract_pinned_content(extra_instructions=...)`

### Expected outcome
- resume text appears in `Memory summary:` block, not pinned profile section
- later compaction can summarize it

---

## 5.3 `src/fa/cli.py`

### Needed changes
1. keep reading `resume_draft_text`
2. stop passing it via `system_prompt_extra`
3. pass it via new `initial_memory_summary` argument
4. update surrounding comments so they no longer claim system-prompt pinning semantics

### Expected outcome
CLI/runtime alignment with locked D9.

---

## 6. Tests to add/update

## 6.1 `tests/test_compaction_sota.py`

Add or update:

### A. pinned-file deletion test
- extract pinned content once
- delete `AGENTS.md`
- extract again
- assert old `AGENTS.md` content is gone

This directly covers the stale-cache defect.

## 6.2 `tests/test_pr2_wiring.py`

Add:

### B. resume context is mutable summary, not pinned guidance
- create pinned file content
- run `drive_session(..., initial_memory_summary="resume text")`
- inspect provider request messages
- assert:
  - one system message contains `Memory summary:\nresume text`
  - no `STANDING PROFILE GUIDELINES` section contains that resume text

### C. explicit standing extra instructions still remain pinned when intentionally passed
Optional but useful if we keep `system_prompt_extra` semantics.

## 6.3 Existing mid-session change test should keep passing
Current PR2 reload test already proves file mutation is re-read each turn. It should continue passing after cache replacement refactor.

---

## 7. Verification plan

### V1 — PinnedBuffer unit proof
- synthetic AGENTS + llms.txt
- extract
- mutate
- delete
- re-extract
- assert correct current-state behavior

### V2 — Runtime prompt-order proof
- active session run
- resume text passed as initial mutable summary
- inspect outbound request
- confirm separation between:
  - pinned constraints
  - memory summary

### V3 — Regression proof
- all previous PR2 pinning tests still pass
- no Stage C regressions from moving resume text out of pins

---

## 8. Anti-theater rules

Slice 4 is not done if tests only assert:
- that resume text appears somewhere in the prompt
- or that hashes exist as strings

They must specifically prove:
- **where** resume text appears
- **where it does not** appear
- and that stale pinned data is removed after deletion

---

## 9. Done definition

Slice 4 is done when:
1. resume draft text is no longer injected through `PinnedBuffer`
2. resume draft text appears as mutable summary/history
3. pinned-file deletion no longer leaves stale content in prompt
4. pinned-file changes reload cleanly each turn
5. hash semantics are honest and deterministic
