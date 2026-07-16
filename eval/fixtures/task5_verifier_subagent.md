---
task_id: verifier-subagent
role: verifier
scoring_kind: llm_judge
expected: "Verifier subagent pytest returns JSON PASS/FAIL, main sees only summary 500 tokens"
---

# Task: Verifier subagent

## Goal
Run cheap deterministic verifier subagent with minimal prompt <500 tokens, not full BASE+map: "You are verifier agent, tools=[fs.run_bash], input spec, output JSON {file_path, test_result PASS/FAIL, summary, risks}"

## Acceptance
- Subagent cheap deterministic minimal system prompt <500 tokens, not full BASE
- Filtered history task + 5 relevant files from instant_grep, not full parent 124 steps, total <8000 chars
- JSON validation cached at module load via fastjsonschema
- Artifact write .fa/subagents/<id>.json per task completion
- 1 subagent limit enforced via RuntimeLimits.max_subagent_spawns_per_session=3
- Main sees only summary 500 tokens, not 5k raw, context stays 180.5k not 185k
- Worklog contains Goal, Verification, Risks

## Metrics
- tokens/task, tool-calls/task, verification strength, context efficiency
