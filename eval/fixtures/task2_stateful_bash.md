---
task_id: stateful-bash-pty
role: implementer
scoring_kind: exact
expected: "cd /tmp && pwd returns /tmp, export FOO=bar + echo $FOO returns bar"
---

# Task: Verify PtyPool stateful bash persistence

## Goal
cd /tmp && pwd should persist across calls, export FOO=bar + echo $FOO should return bar, ANSI stripped, Ctrl+C interrupts sleep 10

## Steps
1. cd /tmp && pwd
2. pwd should return /tmp
3. export FOO=bar
4. echo $FOO should return bar
5. ls --color=always | cat should have no \x1b[
6. sleep 10 + send_ctrl_c should interrupt

## Acceptance
- Second pwd returns /tmp
- echo $FOO returns bar
- ANSI stripped
- Ctrl+C interrupts
- No global pool singleton, SessionState holds executor via DI, shared Server instance with socket isolation fa_<run_id>
- Fallback pexpect WARNING when tmux missing

## Metrics
- state consistency, safety compliance
