# ADR-13 — Workspace Isolation

- **Status:** accepted
- **Date:** 2026-06-25
- **Deciders:** First-Agent Core Team

## Context

The agent container bind-mounts the host git checkout (`/srv/first-agent/repo/First-Agent-dev/`) as `/workspace` (read-write). Agent sessions write code and trace artifacts into the host checkout, dirtying the worktree. 

This causes a direct architectural conflict:
- The operator runs `fa update`, which requires a pristine git worktree to execute `git pull --ff-only`.
- The agent runs tasks via `fa run`, which writes to the worktree and blocks `fa update` due to uncommitted changes or untracked files.

We need a way to isolate agent modifications from the main checkout while allowing the agent full access to version control (committing, pushing).

## Prior Art

As detailed in our research (`knowledge/research/workspace-isolation-research.md`), several open-source agent stacks have converged on workspace isolation patterns:
- **Clone-in-Sandbox:** (Open SWE, Stripe, Coinbase) Each task gets an isolated VM/container; repo is cloned in. High isolation but large disk overhead and slower start.
- **Docker AI Sandbox:** Host repo mounted read-only; container entrypoint creates a private clone. 
- **SWE-Next:** Copy-on-start mounting. Snapshot mounted read-only, copied to writable workspace. No git history.

## Options considered

### Option A — Pattern 2: Read-only mount + per-session clone (Docker AI Sandbox)
The host repo is mounted read-only. The container entrypoint creates a private `git clone --local` into a per-session writable directory.
- Pros: Minimal disk overhead (due to hardlinks via `--local`), host repo stays completely clean, full git capability inside the clone, zero Python code changes required (handled entirely by entrypoint and host wrapper).
- Cons: Requires one session per container lifecycle (new session = container restart).

### Option B — Git Worktree per agent
Each agent gets a separate git worktree sharing `.git` objects.
- Pros: Instant creation, near-zero overhead.
- Cons: Concurrent git operations can corrupt shared metadata, no runtime isolation between concurrent agents.

## Decision

We will choose **Option A (Read-only mount + per-session clone)** because it provides robust isolation while preserving full git capabilities and minimizing disk overhead, all with minimal changes to the existing architecture.

## Consequences

- Positive: Host repo is permanently clean; `fa update` can be run seamlessly at any time without stash/clean operations.
- Positive: Secret isolation remains intact; the egress-proxy container has no `/repo` or `/sessions` mounts.
- Negative: Enforces one session per container lifecycle. To start a new isolated session, the operator must restart the agent container (`fa restart` or `fa rebuild`).
- Follow-up work: A pruning mechanism (`fa sessions prune --older 7d`) will be needed to clean up old session workspaces from the host.

## References

- [`knowledge/research/workspace-isolation-research.md`](../research/workspace-isolation-research.md)
- [Docker AI Sandbox Isolation](https://docs.docker.com/ai/sandboxes/security/isolation/)
