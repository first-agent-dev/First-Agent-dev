# ADR-13 — Workspace Isolation

- **Status:** accepted; amended 2026-08-13
- **Date:** 2026-06-25
- **Deciders:** First-Agent Core Team

## Context

The original deployment mounted the host Git checkout read-write into the agent
container. Agent sessions could dirty the same worktree that the operator needed
to keep clean for `fa update`.

The current deployment separates three roles:

- `/srv/first-agent/repo/First-Agent-dev` is the clean deployment mirror and is
  mounted read-only at `/repo`;
- `/srv/first-agent/sessions/<session-id>` contains writable managed session
  clones on `agent/<session-id>` branches;
- `~/First-Agent-dev` is the operator development clone for reviewed edits,
  local checks, commits, and PR preparation.

A managed workspace must preserve full Git capability without inheriting source
administrative state, ignored files, a source `.venv`, or source worktree dirt.
It must also have a publication destination distinct from the read-only local
fetch authority.

## Prior art

The research in
[`workspace-isolation-research.md`](../research/workspace-isolation-research.md)
covers clone-in-sandbox, read-only source plus private clone, copy-on-start, and
Git worktree designs. The accepted design remains a read-only source plus one
full managed clone per persistent logical session.

## Options considered

### Option A — read-only source plus managed full clone

Git clones one captured source commit through the local `file://` transport into
`/sessions/<session-id>`, creates `agent/<session-id>`, and configures trusted
local author identity. Fetch remains local; push uses a validated GitHub URL or
an explicit credential-free override.

- **Pros:** source checkout remains outside agent write authority; full Git
  history and normal commits; no shared writable Git administration; exact
  rollback of helper-created partial targets.
- **Cons:** each session owns Git objects and its prepared `.venv`; retention and
  disk use require operator management.

### Option B — Git worktree per agent

Each agent gets a worktree sharing Git administration with the source.

- **Pros:** low creation and object-storage cost.
- **Cons:** shared writable metadata couples otherwise independent sessions and
  weakens the source/session ownership boundary.

## Decision

Choose **Option A**.

- Entrypoint startup creates or resumes `/sessions/<session-id>` from
  `file:///repo`. The URL form intentionally uses Git transport rather than a
  filesystem-link optimization.
- `fa run` or `fa workflow` without `--session-id` creates a new persistent
  logical session. An explicit `--session-id` attaches the existing session;
  `--resume` requires that explicit identity.
- Managed clones fetch from the local source and publish only through their
  validated `origin.pushurl`. The default is the deployment mirror's canonical
  GitHub publication authority; `FA_REPO_PUSH_URL` is the optional non-secret,
  credential-free override.
- Lifecycle readiness runs before provider/model use. It prepares the project
  environment, four Git hook seats, and every configured pre-commit environment.
  Bootstrap unavailability is typed and fail-open; actual quality failures stay
  blocking.
- Cache state remains bounded and ephemeral: uv has a separate 2 GiB tmpfs and
  HOME/pre-commit cache has a measured 1536 MiB tmpfs ceiling. Persistence is
  deferred until production latency demonstrates a need.

## Amendment — 2026-08-13

The original ADR text coupled workspace creation to a filesystem-local link
optimization and coupled logical-session identity to container recreation.
Production review rejected both assumptions:

- URL-form local transport is portable across the deployment/session boundary
  and avoids shared-ownership and cross-device behavior;
- logical sessions are selected by session identity and can outlive/reuse one
  container process;
- Python `SessionManager` and CLI lifecycle code, not only the entrypoint shell,
  are required composition roots;
- readiness is part of workspace admission rather than work delegated to the
  model.

This amendment supersedes those original mechanism and lifecycle details while
retaining the accepted isolation decision.

## Consequences

- The deployment mirror remains outside managed agent write authority.
- New and attached managed sessions have independent Git administration,
  branch, identity, environment, and hook state.
- Local fetch can intentionally lag upstream until operator-controlled
  `fa update`; agent publication ends at a feature branch and PR.
- Clone and readiness costs are real rather than described as zero. The S7
  benchmark measured a 16.9 MB fresh clone before readiness, approximately
  76.4 s cold readiness in the controlled proxy, and approximately 0.112 s warm
  readiness.
- Session retention/pruning remains a separate operator backlog item.
- Actual GitHub publication, CI observation, and deployment verification remain
  operator-controlled live evidence.

## References

- [`knowledge/research/workspace-isolation-research.md`](../research/workspace-isolation-research.md)
- [`AP-004 — Symptom-chasing without a system model`](../anti-patterns/AP-004-symptom-chasing-without-model.md)
- [`session-workspace-readiness-benchmark.md`](../../worklogs/implementation-plans/session-workspace-readiness-benchmark.md)
- [Docker AI Sandbox Isolation](https://docs.docker.com/ai/sandboxes/security/isolation/)
