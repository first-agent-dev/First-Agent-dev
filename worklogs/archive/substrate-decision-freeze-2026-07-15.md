# Substrate Decision Freeze — 2026-07-15

**Status:** Locked for gap-closure execution  
**Applies to:** Stage A/B/C substrate closure work  
**Parent plans:**
- `knowledge/research/substrate-modernization-plan-2026-07-14.md`
- `knowledge/research/substrate-gap-closure-workplan-round2-2026-07-15.md`

---

## D8 — Unified per-run DB authority

**Authoritative truth should be one unified per-run DB.**  
**Workspace/global databases should be derived projections, not hot-path authority.**

### Meaning
- Active runtime state must converge into the per-run database at:
  - `~/.fa/session-log/<run_id>/session.db`
- Hot-path authoritative tables should include at minimum:
  - `event_log`
  - `blackboard`
  - session metadata needed by runtime correctness
- Workspace/global DBs may exist only as:
  - export surfaces,
  - indexes,
  - analytics projections,
  - caches.

### Anti-goal
Do **not** maintain separate co-equal runtime authorities for:
- event log state,
- blackboard state,
- compaction/session metadata.

---

## D9 — Resume / PR draft semantics

**Previous PR draft / resume text must be inserted as mutable non-cacheable summary/history.**

### Meaning
- resume text is session context,
- resume text is mutable,
- resume text is allowed to be summarized/compacted,
- resume text is not governance.

### Therefore
Resume / PR draft text must **not** be:
- part of `PinnedBuffer`,
- treated as compaction-exempt standing constraint,
- represented as integrity-verified policy text.

---

## D10 — `fs_spawn_subagent` contract

`fs_spawn_subagent` is locked as:
- **narrow-scope**
- **role-bounded**
- **stateless**
- **limited-function**
- **not a bypass around main-agent shell/tool safety**

### Meaning
- subagent execution must not create a weaker shell/policy domain than the parent harness;
- allowed functionality must be explicit per role;
- role/config fields must affect real runtime behavior, not just schema surface;
- shared-workspace mode is acceptable only if safety semantics remain explicit.

### Anti-goal
`fs_spawn_subagent` must **not** remain a generic arbitrary-shell nested executor.

---

## D11 — Slice 1 scope discipline

**Do not try to solve all DB-related problems inside Slice 1.**  
**Slice 1 is for hot-path authority and split-brain removal.**

### Meaning
Slice 1 should focus on:
- authoritative runtime DB unification,
- split-brain elimination,
- compatibility-preserving facades.

### Out of scope for Slice 1
- full observability query-plane cleanup,
- global history export,
- Stage C ladder redesign,
- logging migration completion,
- all shared-workspace/subagent lifecycle hardening.

Those land in later slices.
