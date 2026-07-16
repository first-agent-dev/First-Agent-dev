---
task_id: read-repo-planner
role: planner
scoring_kind: llm_judge
expected: "Should list architecture, key files, and open tasks"
---

# Task: Read repository and tell what you found

## Goal
Read repository structure via glob, grep, read_file, instant_grep and produce summary of architecture, key files, and open tasks.

## Acceptance
- Uses glob **/*.py, read AGENTS.md, llms.txt, README.md
- Returns summary with architecture, key files, open tasks
- Measures baseline 124 steps before Phase 3, target 30-40 after

## Metrics
- tokens/task, tool-calls/task, tools-in-context, cost/task, success-rate
