import os
import re

def repl(filepath, old, new):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    if isinstance(old, str):
        text = text.replace(old, new)
    else:
        text = old.sub(new, text)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)

# 1. AGENTS.md
new_overview = """## Project Overview

> **Agent Pitch:** Welcome to First-Agent. This is not a standard open-ended sandbox. You are operating inside a strict, zero-trust Trusted Computing Base (TCB Level-0). Your code edits will be checked via AST analysis, and your bash commands are monitored by IntentGuard. Use `llms.txt` to strictly manage your context window. Minimalism and deterministic precision are the highest virtues here.

**First-Agent** is an implementation-first project aimed at becoming the most token- and tool-call-efficient open-source coding-agent harness.

Goal-formulation in 4 pillars + minimalism-first principle:
[`knowledge/project-overview.md` §1.1](./knowledge/project-overview.md#11-четыре-столпа-цели-project-goal--four-pillars).
"""
repl("AGENTS.md", re.compile(r'## Project Overview.*?## Repository Structure', re.DOTALL), new_overview + "\n## Repository Structure")

# 2. knowledge/project-overview.md
repl("knowledge/project-overview.md", re.compile(r'## 1\.3\. Three-stage project evolution.*?(?=\n## 2\. Users)', re.DOTALL), '')
repl("knowledge/project-overview.md", "- **Audience for documentation:** other LLM agents (Devin, Codex,\n  Claude Code) navigating the repo.", "- **Audience for documentation:** other LLM agents navigating the repo.")
repl("knowledge/project-overview.md", "Pattern взят из Anthropic Claude Skills + Devin `.devin/skills/`,", "Pattern взят из Anthropic Claude Skills,")

# 3. knowledge/llms.txt
repl("knowledge/llms.txt", re.compile(r'> \*\*Project stage\.\*\* Currently in \*\*Stage 1\*\*.+?\n', re.DOTALL), '')
repl("knowledge/llms.txt", "Stage 1 goal_lens", "goal_lens")
repl("knowledge/llms.txt", re.compile(r'> agent development via Devin.+?\n', re.DOTALL), '')
repl("knowledge/llms.txt", re.compile(r'> in \[knowledge/project-overview\.md.+?\n', re.DOTALL), '')

# 4. knowledge/BACKLOG.md
repl("knowledge/BACKLOG.md", re.compile(r'Stage 1 \(Devin-driven, per\n> \[`project-overview.md`\]\(\./project-overview.md\)\)', re.DOTALL), 'early agent-driven stages')
repl("knowledge/BACKLOG.md", "Stage 1 is Devin-driven; Devin decides", "agents decide")
repl("knowledge/BACKLOG.md", "a non-Devin agent", "the agent")
repl("knowledge/BACKLOG.md", "LOW ROI for Stage 1. Devin reads", "LOW ROI currently. The agent reads")
repl("knowledge/BACKLOG.md", "First non-Devin session", "First autonomous session")
repl("knowledge/BACKLOG.md", "Devin picks the template", "The agent picks the template")
repl("knowledge/BACKLOG.md", "Each Devin (or First-Agent OWN\n  session)", "Each agent session")
repl("knowledge/BACKLOG.md", "(3 Devin\n  sessions vs 3 open-source)", "(3 agent sessions vs 3 open-source)")
repl("knowledge/BACKLOG.md", "still Devin's harness", "still external harness")
repl("knowledge/BACKLOG.md", "(Devin auto-load\n  target)", "(auto-load target)")
repl("knowledge/BACKLOG.md", "the Devin auto-load", "the auto-load")
repl("knowledge/BACKLOG.md", "Devin Review", "Agent Review")
repl("knowledge/BACKLOG.md", re.compile(r'`devin/(\d+)'), r'`agent/\1')

# 5. knowledge/glossary.md
with open("knowledge/glossary.md", "r", encoding="utf-8") as f:
    lines = f.readlines()
new_lines = []
for line in lines:
    if line.startswith("| **Ask Devin**") or line.startswith("| **Auto-Fix**") or line.startswith("| **Devin Review**") or line.startswith("| **Managed Devin**") or line.startswith("| **Playbook**"):
        continue
    line = line.replace("Devin context", "agent context")
    line = line.replace("connecting Devin", "connecting the agent")
    line = line.replace("an LLM (or Devin)", "an LLM")
    line = line.replace("recurring Devin session", "recurring agent session")
    line = line.replace("that Devin automatically", "that the agent automatically")
    line = line.replace("that Devin knows", "that the agent knows")
    new_lines.append(line)
with open("knowledge/glossary.md", "w", encoding="utf-8") as f:
    f.writelines(new_lines)

# 6. HANDOFF.md
repl("HANDOFF.md", "Devin-style verbs", "agent-style verbs")
repl("HANDOFF.md", re.compile(r'branch `devin/'), "branch `agent/")

# 7. knowledge/README.md
repl("knowledge/README.md", "Devin Knowledge notes", "Agent Knowledge notes")
repl("knowledge/README.md", "The Devin-era `docs/` folder — including the former\n   `devin-reference.md`", "The legacy `docs/` folder — including the former\n   `agent-reference.md`")

# 8. knowledge/adr/DIGEST.md
repl("knowledge/adr/DIGEST.md", "80–95 K Devin", "80–95 K baseline")
repl("knowledge/adr/DIGEST.md", "Devin Review", "Agent Review")
repl("knowledge/adr/DIGEST.md", re.compile(r'`devin/(\d+)'), r'`agent/\1')

# 9. knowledge/skills/repo-audit/SKILL.md
repl("knowledge/skills/repo-audit/SKILL.md", "Devin / Sonnet-class", "elite")
repl("knowledge/skills/repo-audit/SKILL.md", "(Devin? Sonnet? DeepSeek 4? Kimi 2.6?)", "(Claude 3.7? Sonnet? DeepSeek? Kimi?)")
repl("knowledge/skills/repo-audit/SKILL.md", "Devin-only artefacts", "legacy artefacts")
repl("knowledge/skills/repo-audit/SKILL.md", "devin-reference.md", "agent-reference.md")
repl("knowledge/skills/repo-audit/SKILL.md", re.compile(r'devin/\$\(date'), r'agent/$(date')
repl("knowledge/skills/repo-audit/SKILL.md", "Devin Review", "Agent Review")

# 10. knowledge/skills/pr-creation/SKILL.md
repl("knowledge/skills/pr-creation/SKILL.md", "Devin-driven", "agent-driven")
repl("knowledge/skills/pr-creation/SKILL.md", "Devin (or other LLM-agent)", "LLM-agent")

# 11. scripts/fa-entrypoint.sh
repl("scripts/fa-entrypoint.sh", 'git checkout -b "devin/${SESSION_ID}"', 'git checkout -b "agent/${SESSION_ID}"')

# 12. tests/test_fa_entrypoint.py
repl("tests/test_fa_entrypoint.py", 'assert branch == "devin/test-session-123"', 'assert branch == "agent/test-session-123"')

# 13. src/fa/ and tests/ (Code Comments)
import glob
for root, _, files in os.walk("src"):
    for file in files:
        if file.endswith(".py"):
            filepath = os.path.join(root, file)
            repl(filepath, "Devin Review", "Agent Review")
            repl(filepath, "Devin-Review", "Agent-Review")

for root, _, files in os.walk("tests"):
    for file in files:
        if file.endswith(".py"):
            filepath = os.path.join(root, file)
            repl(filepath, "Devin Review", "Agent Review")
            repl(filepath, "Devin-Review", "Agent-Review")

# 14. Anti-patterns
for root, _, files in os.walk("knowledge/anti-patterns"):
    for file in files:
        if file.endswith(".md"):
            filepath = os.path.join(root, file)
            repl(filepath, "Devin Review", "Agent Review")
            repl(filepath, re.compile(r'`devin/(\d+)'), r'`agent/\1')

# 15. Other explicit deep-dives / instructions
repl("For cross-reference with ADR's/FA-inspiration-deep-dive.md", "Devin reviews itself", "agent reviews itself")
repl("For cross-reference with ADR's/FA-inspiration-deep-dive.md", "stops a Devin/agent", "stops an agent")

# 16. PR Notes
repl("knowledge/pr-notes/PR_NOTE_LIVE_OUTPUT.md", "Devin", "Agent")
