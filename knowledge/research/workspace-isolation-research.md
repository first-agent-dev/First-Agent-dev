---
compiled: 2026-06-24
goal: Production workspace isolation patterns for agent sessions
source: Open SWE, Docker AI Sandbox, SWE-Next, Augment Code, Arcjet
---

# Research: Workspace Isolation for Agent Sessions

## §0 Decision Briefing

**Problem:** Single git checkout serves both `fa update` (needs clean
worktree) and agent sessions (writes code, traces, artifacts). These
conflict. **Recommendation:** Pattern 2 — Docker RO mount + private
clone per session. Minimal Docker change (~50-70 lines), matches
industry consensus (Open SWE, Docker AI Sandbox, SWE-Next).

## Problem

Single git checkout at `/srv/first-agent/repo/First-Agent-dev/` is
bind-mounted read-write as `/workspace` into the agent container.
Agent writes (code, trace artifacts, session events) dirty the host
worktree. `fa-update.sh` requires clean worktree for `git pull --ff-only`.
This creates an architectural conflict: the repo must be both immutable
(for updates) and writable (for agent work).

## Industry Patterns (2025-2026)

### Pattern 1: Clone-in-Sandbox (Open SWE / Stripe / Coinbase / Ramp)

Each task gets its own isolated cloud sandbox (container/VM). The repo
is cloned in. Agent gets full permissions. Blast radius contained.
All three companies converged on this independently.

Source: [Open SWE](https://www.langchain.com/blog/open-swe-an-open-source-framework-for-internal-coding-agents),
[DevOps.com](https://devops.com/open-swe-captures-the-architecture-that-stripe-coinbase-and-ramp-built-independently-for-internal-coding-agents/)

### Pattern 2: Read-only mount + private clone (Docker AI Sandbox)

Host repo mounted read-only. Entrypoint creates a private RW clone
inside the sandbox. Agent edits the clone. Results returned via
git-daemon → host fetches as remote.

```text
Host repo (.git/ + working tree)
    ↓ read-only bind mount
/run/sandbox/source (RO)
    ↓ git clone
/workspace (RW) ← agent edits here
    ↓ git push
GitHub (PR)
```

Key guarantees: agent cannot modify host .git/, cannot drop
hooks, nothing integrated until explicit merge.

Source: [Docker AI Sandbox docs](https://docs.docker.com/ai/sandboxes/security/isolation/)

### Pattern 3: Git Worktree per agent (Multi-agent parallel)

Each agent gets a separate worktree sharing .git objects. Near-instant
creation. Standard git tooling for merge/conflict resolution.

Cons: concurrent git operations can corrupt shared metadata; must
serialize git commands; no runtime isolation.

Source: [Augment Code](https://www.augmentcode.com/guides/git-worktrees-parallel-ai-agent-execution),
[Uncle Bob's multi-agent setup](https://www.buildmvpfast.com/blog/git-workflow-ai-assisted-development-agent-commits-2026)

### Pattern 4: Copy-on-Start (SWE-Next / SWE-bench)

Commit-specific repo snapshot mounted read-only. Container copies it
to writable workspace before agent edits and test runs.

Source: [SWE-Next](https://arxiv.org/html/2603.20691v1)

### Pattern 5: VM-per-workspace (Arcjet)

OrbStack VMs, one per workspace. 5-10 second creation from base VM.
Go CLI manages lifecycle (create/run/destroy).

Source: [Arcjet blog](https://blog.arcjet.com/from-devcontainers-to-vms-parallel-dev-environments-for-ai-agents/)

## Comparison

| Pattern | Creation time | Disk overhead | Git capable | Concurrent safe |
|---------|--------------|---------------|-------------|-----------------|
| Clone-in-sandbox | ~seconds | repo size | ✅ | ✅ |
| RO mount + clone | ~instant | ~0 (hardlinks) | ✅ | ✅ |
| Git worktree | ~instant | ~0 (shared .git) | ✅ | ⚠️ serialize |
| Copy-on-start | ~instant (8MB) | repo size | ❌ (no .git) | ✅ |
| VM-per-workspace | 5-10s | VM image | ✅ | ✅ |

## Recommendation: Pattern 2 for FA

**RO mount + `git clone --local`** — best fit because:

1. Minimal Docker change: swap one bind mount to read-only, add sessions volume.
2. `git clone --local` uses hardlinks for .git objects — near-zero disk overhead.
3. Full git capability: agent can commit, push, create branches.
4. Main checkout always clean: `fa update` works without stash/clean.
5. Future-proof: more agents = more clones, same pattern.

### Proposed topology

```text
Host:
  /srv/first-agent/repo/First-Agent-dev/  ← main (RO, fa update)
  /srv/first-agent/sessions/              ← writable, per-session clones

Container:
  /repo       ← RO bind mount of host repo
  /sessions/  ← RW bind mount of sessions dir

Entrypoint:
  git clone --local /repo /sessions/$RUN_ID
  cd /sessions/$RUN_ID
  git checkout -b agent/$RUN_ID
  export PYTHONPATH=/sessions/$RUN_ID/src
```

### Estimated changes

- `docker-compose.fa.yml`: ~10 lines (volume mounts)
- `fa-entrypoint.sh`: ~20 lines (clone-on-start)
- `scripts/fa`: ~15 lines (sessions verb)
- Total: ~50-70 lines + ADR
