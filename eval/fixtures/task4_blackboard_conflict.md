---
task_id: blackboard-conflict
role: implementer
scoring_kind: exact
expected: "Conflict for ['out.txt']: write/write overlap {'out.txt'} — concurrent without coordination. Conflicts: [...]"
---

# Task: Blackboard conflict detection

## Goal
Concurrent write without coordination should be detected as conflict_detected with read/write overlap check per Q2 base_commit linear frontier policy.

## Steps
1. Write file A with base_commit X
2. Concurrent write same file A with same base_commit X but different content, no parent relationship -> should conflict
3. Write file with different base_commit Y -> should NOT conflict (already serialized/rebased)

## Acceptance
- Same base_commit + no parent → concurrent → conflict_detected
- Different base_commit → not concurrent → no conflict (already serialized)
- parent_id == old.id → happens-before → no conflict
- Read/write overlap and assumption violated detected

## Metrics
- state consistency, safety compliance, verification strength
