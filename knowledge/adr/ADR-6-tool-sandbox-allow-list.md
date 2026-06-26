# ADR-6 — Tool sandbox & path allow-list policy for v0.1

- **Status:** accepted
- **Date:** 2026-04-29
- **Deciders:** project owner (`0oi9z7m1z8`), Agent (drafting)

## Context

[ADR-1](./ADR-1-v01-use-case-scope.md) §UC1 ships a Coder role
that **edits files** on the user's local filesystem and pushes
to a controlled allow-list of GitHub repos. Two facts make this
risky enough that an explicit policy is required before the
first chunker / loop / tool implementation lands:

1. **Mid-tier OSS Coder hallucinates more than top-tier Planner**
   ([ADR-2](./ADR-2-llm-tiering.md) §Decision and §Consequences
   "Coder turn fails loudly"). The same model that picks edits
   also picks file paths. There is **no second pair of eyes** in
   v0.1 because no Critic / Reflector role exists (per ADR-2
   amendment 2026-04-29). A path allow-list is the only structural
   guard between a Coder hallucination and the user's filesystem.
2. **`project-overview.md` §4 only restricts PR-write to a
   controlled repo allow-list. Read-side is wide open.** Every
   tool call that reads a file ends up with the file's contents
   in the LLM conversation accumulator — which, for the
   user's mix (`~99 %` remote API per project-overview §6),
   means the contents are sent to OpenRouter / Anthropic / vLLM
   on the next turn. **Reads are de-facto network egress** for
   any non-air-gapped configuration. So allow-list must cover
   reads too, not only writes.

The cross-reference review
[`research/cross-reference-ampcode-sliders-to-adr-2026-04.md`](../research/cross-reference-ampcode-sliders-to-adr-2026-04.md)
§4.1, §9.3, §10 R-2 calls this out as the single highest-risk
gap in the v0.1 ADR set, and the user agreed in the
2026-04-29 session that this ADR must land **before** any
filesystem-touching tool is implemented.

This ADR specifies the policy. The implementation lives in the
inner-loop contract
([ADR-7](./ADR-7-inner-loop-tool-registry.md) §8, where
`SandboxHook` is the v0.1 `pre_tool` hook of record) and in
`src/fa/sandbox/`.

## Options considered

### Option A — No sandbox (Coder edits / reads anything under user's home)

- Pros: zero implementation cost; matches the way `gh` /
  `git` already operate.
- Cons:
  - One Coder hallucination on a file path away from
    overwriting / corrupting `~/.ssh/authorized_keys`,
    `~/.aws/credentials`, `~/.gnupg/`, browser profiles,
    `~/.fa/secrets.env`, etc.
  - Read-side: any LLM turn on a non-air-gapped Coder leaks
    arbitrary `~` content to the provider on the next turn.
  - Forks of FA inherit this risk by default — most educational
    forks will not realise the implication.
  - Violates the spirit of `project-overview.md` §4 (PR-write
    allow-list) by leaving the local FS half-open while
    locking down the remote half.

### Option B — Path allow-list with explicit read / write policy (chosen)

A small file (`~/.fa/sandbox.toml`) lists **path globs allowed
for read** and **path globs allowed for write** (plus a
**block-list** that overrides allow). Every tool call that
takes a path goes through a `Sandbox.check_read(path)` /
`Sandbox.check_write(path)` gate before exec. Default is
**deny**; the user must opt in to each new directory.

- Pros:
  - **Loud, fast, stoppable**: a Coder hallucinated path is
    rejected at the tool call, never gets to disk, never
    enters the LLM conversation as `read_file` content.
  - **Config-driven, single file, diffable.** The user can
    audit and version `~/.fa/sandbox.toml`.
  - **Symmetric with PR-write allow-list** in
    `~/.fa/repos.toml` — same shape, same audit story.
  - Implementation is ~150 lines of Python; no new runtime
    dependencies (`pathlib.Path.resolve()` + `fnmatch` /
    `pathspec`).
  - Forks see the policy in the ADR and the config file at
    install time; the safe default is the documented one.
- Cons:
  - Each new project the user wants Coder to touch needs an
    edit to the allow-list. v0.1 is single-user / single-machine,
    so this friction is small (~3-5 entries total).
  - Symlinks and `..` traversal must be handled correctly;
    bugs in path resolution defeat the policy. Mitigated by
    `Path.resolve()` plus a unit-test fixture pinned to the
    invariants below.
  - Does not help against an LLM that calls `run_command`
    (e.g. `cat /etc/passwd`). v0.1 does not ship `run_command`
    in the Coder tool set; when it lands, the same
    `Sandbox.check_read` gate applies to every path argument
    parsed out of the command (or, more practically, the
    command itself is allow-listed, not just the paths).

### Option C — OS-level sandbox (chroot, bubblewrap, Docker, macOS sandbox-exec)

- Pros:
  - **Strongest** isolation; defeats path-traversal bugs
    in the policy code.
  - Containerizes the whole FA process so `gh` / `git` / vLLM
    are also in scope.
- Cons:
  - **Cross-platform cost is high.** v0.1 targets the user's
    Linux desktop *and* keeps the door open for Windows /
    macOS forks. bubblewrap is Linux-only; `sandbox-exec` is
    macOS-only and deprecated; Docker adds ~250 MB of
    runtime overhead and breaks `gh auth` flows on every
    rebuild.
  - **Friction defeats use.** Coder needs to edit the user's
    actual repos at the user's actual paths. A chroot would
    require bind-mounting every allowed repo individually.
  - **Operational complexity** without commensurate v0.1
    benefit. Educational forks would mostly disable the
    sandbox to get FA working.
  - Re-evaluation trigger below covers this — when v0.2
    `run_command` ships, OS-level isolation becomes worth
    the cost.

### Option D — Pure prompt-level instruction ("only edit files inside FA repo")

- Pros: zero implementation cost.
- Cons:
  - Same as Option A in practice — a hallucinating Coder
    will violate the prompt. No structural guard.
  - Failure mode is silent (file gets overwritten before
    anyone reviews the prompt drift), which is the failure
    mode this ADR is trying to eliminate.

## Decision

We will choose **Option B (path allow-list with explicit
read / write policy)** for v0.1 with the following concrete
shape.

### Policy file

Single TOML file at `~/.fa/sandbox.toml` (path config-overridable
via `FA_SANDBOX_FILE` env var — useful for tests). Default
shape, shipped as a template by `fa init`:

```toml
# ~/.fa/sandbox.toml — Tool sandbox & path allow-list policy.
# See knowledge/adr/ADR-6-tool-sandbox-allow-list.md.

# Read allow-list. Coder tools (read_file, list_files,
# grep, BM25) only see paths matching one of these globs.
[read]
allow = [
  "~/repos/first-agent/**",       # FA itself
  "~/repos/<user-repo-1>/**",     # user's go library
  "~/repos/<user-repo-2>/**",     # user's pwsh script repo
  "~/.fa/**",                     # FA's own state (hot.md, sessions/, index.sqlite)
  "~/notes/**",                   # UC3 inbox + curated notes
]
# Block-list overrides allow (defence-in-depth for sensitive
# directories that happen to live under an allowed root).
deny = [
  "~/.fa/secrets.env",
  "**/.env",
  "**/.env.*",
  "**/credentials*",
  "**/*.pem",
  "**/*.key",
  "~/.ssh/**",
  "~/.aws/**",
  "~/.gnupg/**",
]

# Write allow-list. edit_file / write_file / shell tools that
# take an output path use this set, NOT the read set.
# v0.1 default is *strictly* a subset of read.allow.
[write]
allow = [
  "~/repos/first-agent/**",
  "~/repos/<user-repo-1>/**",
  "~/repos/<user-repo-2>/**",
  "~/.fa/state/**",               # FA's own writable state dir
]
deny = [
  # Same denylist as read; never write to a denied path even
  # if it matches an allow glob (e.g. an .env inside FA repo).
  "~/.fa/secrets.env",
  "**/.env",
  "**/.env.*",
  "**/credentials*",
  "**/*.pem",
  "**/*.key",
  "~/.ssh/**",
  "~/.aws/**",
  "~/.gnupg/**",
  "**/.git/**",                   # extra: never touch .git directly
]
```

### Policy semantics

1. **Default-deny.** Any path not matched by `read.allow`
   (resp. `write.allow`) is rejected. Empty allow-list = no
   filesystem access for that operation.
2. **Deny overrides allow.** A path matched by `[read].deny`
   is rejected even if it matches `[read].allow`. Same for
   write. The check order is:
   `resolve(path)` → `deny ⇒ reject` → `allow ⇒ accept` →
   `else reject`.
3. **Path resolution.** Every input path is normalised via
   `pathlib.Path(p).expanduser().resolve(strict=False)`
   **before** matching. This collapses `..`, follows
   symlinks, and forces all comparisons to be against
   absolute, canonical paths. The matcher then runs against
   the absolute path; globs in the config are also expanded
   via `Path.expanduser()` at load time.
4. **Symlink handling.** `resolve(strict=False)` follows
   symlinks. Therefore an allow-listed directory containing
   a symlink to `/etc/shadow` does **not** grant read access
   to `/etc/shadow` (the resolved target is not in `read.allow`).
   This is by design.
5. **Globs use `pathspec` (gitignore-style).** `**` matches
   zero or more path components; `*` matches one component.
   Anchoring is at the absolute path's root after expanduser.
   No regex, no negation in v0.1 (gitignore `!` is rejected
   at config load).
6. **Write implies read.** A path that is in `write.allow`
   but **not** in `read.allow` is invalid (the chunker /
   reader needs to round-trip its own writes for diff /
   verification). The loader surfaces this as a hard error
   at startup.
7. **Single resolution call per tool invocation.** The path
   is resolved once, the result is what the tool actually
   acts on. This prevents TOCTOU races where a symlink is
   swapped between check and exec — the tool uses the
   already-resolved path, not the raw input.

### Tool wiring

Every tool that takes a path argument is responsible for
calling the sandbox **before** doing any I/O.
[ADR-7](./ADR-7-inner-loop-tool-registry.md) §8 runs sandbox
checks as the v0.1 `SandboxHook` `pre_tool` hook; the contract
is:

```python
class SandboxError(Exception):
    """Raised when a tool call attempts a path the policy denies."""

class Sandbox:
    def check_read(self, path: str | os.PathLike) -> pathlib.Path:
        """Resolve and validate. Returns the resolved Path or raises."""

    def check_write(self, path: str | os.PathLike) -> pathlib.Path: ...
```

The v0.1 tool set (per
[ADR-7](./ADR-7-inner-loop-tool-registry.md) §3 catalog) is
exactly:

| Tool | Gate |
|---|---|
| `read_file(path)` | `check_read` |
| `list_files(path)` | `check_read` (plus filtering: results outside allow are silently dropped) |
| `edit_file(path, …)` | `check_write` (which implicitly also passes `check_read`, see semantic 6) |
| `write_file(path, …)` | `check_write` |
| `grep(pattern, path)` | `check_read` recursively |

Tools that touch external services (LLM calls, `gh` CLI,
`git push`) do **not** go through the sandbox — they have
their own allow-lists (`models.yaml` for LLM endpoints,
`~/.fa/repos.toml` for PR-write).

### One-shot bypass for human-driven exceptions

A user invoking the CLI may pass `fa --sandbox-allow-once
<path>` to add a path to an in-process, session-only allow
list (write or read selected by another flag). Use case: the
user wants Coder to read a 50 KB file once, without making
the whole containing directory permanent allow. The override
is logged in `hot.md` with timestamp and reason. **No way to
bypass the deny-list** — denies are absolute. v0.1 ships
this flag mainly so the user is not tempted to edit
`sandbox.toml` for transient access.

### Audit log

Every `check_read` / `check_write` call appends one JSON line
to `~/.fa/state/sandbox.jsonl`:

```json
{"ts": "2026-04-29T12:34:56Z", "op": "read", "path": "/home/u/repos/fa/x.py", "decision": "allow", "tool": "read_file"}
{"ts": "2026-04-29T12:35:01Z", "op": "write", "path": "/home/u/.ssh/id_rsa", "decision": "deny", "tool": "edit_file", "reason": "deny-glob: ~/.ssh/**"}
```

This is the audit trail the user reads after a session to
spot Coder drift early. File rotation is out of scope for
v0.1 (manual rotation is fine).

## Consequences

- **Positive — structural guard against Coder hallucination.**
  A wrong path produced by mid-tier Coder is rejected at the
  tool call boundary, before disk / before LLM conversation.
- **Positive — symmetric to PR-write allow-list.** The user
  sees the same shape (`~/.fa/sandbox.toml` for FS,
  `~/.fa/repos.toml` for GitHub) and audits both the same way.
- **Positive — single source of truth.** The path policy lives
  in one TOML file, not scattered across tool implementations.
  Forks read the policy, copy-edit the allow list, done.
- **Positive — testable.** Pure-function check
  (`Sandbox.check_read(path) -> ResolvedPath | raise`), no
  filesystem side effects in the check itself, easy to unit
  test with parametrised path / glob fixtures.
- **Negative — friction on first use of a new repo.** The
  user must add the repo to `sandbox.toml` before Coder can
  see it. v0.1 single-user means this is ~5 edits total over
  a few weeks; v0.2 (multi-user TG mode, ADR-1 §Out of
  scope) will need a smarter onboarding flow.
- **Negative — does not stop `run_command`-style escapes.**
  If a future tool runs arbitrary shell, path-level checks
  are insufficient. v0.1 explicitly does not ship a
  `run_command` tool. When it lands the **same allow-list
  applies to the command's parsed file arguments** plus
  command-level allow-list (e.g. only `git`, `gh`, `pytest`,
  `pre-commit run` are runnable).
- **Negative — no protection if the user edits
  `~/.fa/sandbox.toml` directly with a too-broad glob.**
  This is by-design (the user is the principal). v0.1
  documents the trade-off; v0.2 may add a "warn on
  `~/**` allow" lint at config load.
- **Re-evaluation triggers (when to revisit this ADR).**
  - **`run_command` lands.** Action: extend allow-list to
    cover commands; re-evaluate Option C (OS-level
    sandbox).
  - **Multi-user mode (ADR-1 §UC4) lands.** Per-user
    sandbox files; this becomes per-user policy, not a
    single TOML.
  - **Coder hallucination causes a denied write that the
    user wanted.** Investigate as a Coder reliability
    incident first; only widen the allow-list after the
    incident is understood.
- **Follow-up work this unlocks.**
  - `src/fa/sandbox/policy.py` — TOML loader + `Sandbox`
    class + `check_read` / `check_write` + audit-log writer.
  - `src/fa/sandbox/tests/` — fixture-based tests for
    symlink, `..`, glob anchoring, deny-overrides-allow,
    write-implies-read.
  - `fa init` template — ship a starter `sandbox.toml`
    pre-populated with `~/.fa/`, FA repo, and an empty
    user-repo block.
  - **[ADR-7](./ADR-7-inner-loop-tool-registry.md)** wires every
    tool in the registry through `Sandbox.check_*` before exec
    (as the `SandboxHook` `pre_tool` hook).
  - `docs/glossary.md` — entry for "sandbox" / "path
    allow-list" (cross-reference §10 R-8).

## Amendments

### Amendment 2026-05-13 — `[roles]` block in sandbox.toml

**Source.** Inspiration note
[`research/soviet-code-inspiration-2026-05.md`](../research/soviet-code-inspiration-2026-05.md)
§0 R-1, §6.1, §3 Pattern #1. Companion amendment:
[ADR-7 §Amendment 2026-05-13](./ADR-7-inner-loop-tool-registry.md#amendment-2026-05-13--declarative-per-role-tool-whitelist-b-new-1)
(B-NEW-1). Both amendments land in the same PR.

**Change.** Extends `~/.fa/sandbox.toml` with an optional
`[roles.<name>]` block. Used by the ADR-7 dispatcher
(`src/fa/inner_loop/loop.py`); **not** evaluated by the
`SandboxPolicy.check_read` / `check_write` path checks defined
in §Policy semantics — those remain per-path, per-tool-call.

Schema (informal):

```toml
[roles.<name>]
allowed_tools = list[str]   # tool names from ADR-7 §3 catalog
allowed_dirs  = list[str]   # empty = inherit ADR-6 sandbox-root
                            # non-empty = restrict to listed globs
                            # (intersected with sandbox-root)
```

If `[roles.<active_role>]` is absent, the role inherits the
full ADR-7 §3 tool catalog and the §Policy semantics
sandbox-root path scope. Backward-compatible by construction.

**Two checks, two scopes.** This amendment adds the (role, tool)
pairing check; the §Policy semantics path check remains unchanged.
A `fs.write_file` call from a role with `allowed_tools` containing
it still goes through `check_write(path)` before exec. A
`fs.write_file` call from a role whose `allowed_tools` does NOT
contain it returns `E_ROLE_WHITELIST` before the path check fires
(per ADR-7 §Amendment 2026-05-13 enforcement-point spec).

**`allowed_dirs` deferred.** `allowed_dirs = []` (inherit
sandbox-root) is the only validated default in v0.1. Per-role
path scoping (e.g. Planner read-only to `~/project/`, Coder
read-write to `~/project/src/`) is shape-pinned but not
exercised; v0.2 ADR amendment if needed.

**Subtraction-check.** EXEMPT per AGENTS.md §Pre-flight Step 4:
schema-only amendment to the `[roles]` block reserved as
forward-compat by ADR-7 §11 R-4; no new TOML section beyond
that R-4 surface; the `[read]` / `[write]` / block-list shape
defined in §Policy file is unchanged.

### Amendment 2026-05-20 — Five capability flags (deny-by-default opt-in)

**Source.** Implementation roadmap
[`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
§R-21 (Wave 1 — independent of HookRegistry).
Reference impl: Kronos `kronos/config.py:62-69` (five-flag opt-in
model); convergence: soviet B-NEW-1 declarative tool whitelist
(`dpc-messenger-inspiration-2026-05.md` §4).

**Problem.** The §Policy file pins the **path** allow-list (read /
write globs), but says nothing about which *runtime capability
classes* are even available to the loop. Several capabilities are
naturally deny-by-default — dynamic tool loading, MCP gateway
management, server operations — but the original ADR-6 treated
"capability availability" and "path scope" as the same axis. They
are not. A user MAY want to grant `~/project/` write scope while
still keeping dynamic-tool-loading OFF; today there is no
config surface for that distinction.

Kronos solved this with **five flags**, all default `False`,
gated through a single `~/.fa/config.yaml` parse. Each flag is
named for the capability it gates; the names map 1:1 to the
original Kronos identifiers so future cross-reference is cheap.

**Decision.** First-Agent adopts the five-flag opt-in model
**verbatim** from Kronos. The flags live in `~/.fa/config.yaml`
under a top-level `capabilities:` map and the parser exposes them
as a `Capabilities` frozen dataclass (Python impl tracked in this
PR as `src/fa/config.py`):

| Flag | Default | Gates |
|------|---------|-------|
| `ENABLE_DYNAMIC_TOOLS` | `False` | Loading new tools at runtime (e.g. from a discovered SKILL.md or an MCP server). When `False`, the `ToolRegistry` is frozen at session start (matches ADR-7 §3 v0.1 static catalog). |
| `REQUIRE_DYNAMIC_TOOL_SANDBOX` | `False` | When `ENABLE_DYNAMIC_TOOLS=True`, this flag forces newly-loaded tools through the §Policy sandbox check on first call. Without this, a dynamically-loaded tool could in principle bypass the path allow-list. |
| `ENABLE_MCP_GATEWAY_MANAGEMENT` | `False` | The MCP gateway *management* surface (registering / deregistering / configuring upstream MCP servers from inside the loop). Read-only MCP calls do NOT require this flag. |
| `ENABLE_DYNAMIC_MCP_SERVERS` | `False` | Spawning new MCP server subprocesses at runtime. Pairs with `ENABLE_MCP_GATEWAY_MANAGEMENT` but is the narrower flag — turning gateway management on does NOT implicitly enable spawning new servers. |
| `ENABLE_SERVER_OPS` | `False` | "Server operations" — any call that mutates a remote service via API (deploy, restart, scale, …). Today no FA tool exposes this; the flag is reserved so the *infrastructure* for the rule lands before the first such tool. |

**Two layers.** The flags above are **Layer 1** (capability opt-in).
**Layer 2** is the per-role declarative tool whitelist already added
by §Amendment 2026-05-13 (`allowed_tools` in `~/.fa/sandbox.toml`
`[roles]` block). The two layers are AND-ed at the dispatcher: a
tool runs iff (1) its capability class flag is `True` AND (2) the
current role's `allowed_tools` lists it AND (3) the §Policy path
check passes.

**Why config-file opt-in, not CLI flag or env var.** Audit
trail. The capability set is the single most security-sensitive
configuration in the project (it determines what the agent can
do *at all*). A diffable file in the user's home — that lives
under version control alongside `sandbox.toml` — is the only
shape that survives 12 months of casual reading. CLI flags and
env vars leave no trace.

**Subtraction-check (AGENTS.md §Pre-flight Step 4).**

- Removing what makes this redundant? — None. §Amendment 2026-05-13
  introduces the role-tool whitelist (Layer 2) but does not gate
  *capability classes*. The two layers are orthogonal — Layer 2
  says "Coder may not run `bash`"; Layer 1 says "no role may load
  new tools at runtime". You need both.
- Capability lost if omitted? — `ENABLE_DYNAMIC_TOOLS=True` would
  in v0.1 silently be the default behaviour the moment the
  `ToolRegistry` learns to accept additions; without an explicit
  gate, the deny-by-default stance erodes by accretion.
- OSS precedent for not having it? — None among the FA reference
  set: Kronos has the five flags verbatim, DPC has a
  `[capabilities]` TOML block of similar shape, Aperant has
  `enable_*` boolean fields in its main YAML config. The pattern
  is universal across the corpus.

**Reversal triggers.**

- A future FA-workload eval shows ≥3 of the 5 flags are *always*
  flipped to `True` in practical use → demote those to defaults
  and keep only the minority as opt-in (audit cost vs gating
  benefit trade-off).
- The MCP integration matures past the point where
  `ENABLE_MCP_GATEWAY_MANAGEMENT` and `ENABLE_DYNAMIC_MCP_SERVERS`
  are meaningfully separable; collapse the two into one flag if
  the second is never set independently.

**Implementation pointer.** `src/fa/config.py` ships with this
amendment as a small frozen dataclass + YAML parse + 5 boolean
fields, all defaulting `False`. Reading the flags is exactly one
function (`load_capabilities(path: Path) -> Capabilities`); no
side effects, no global state. Capability checks at tool-dispatch
sites are tracked in BACKLOG M-1 (inner-loop scaffolding) — the
loop has to exist before it can read the flags.

### Amendment 2026-05-20 (Wave-1) — Bash sandbox gate (three-layer: classifier + validators + path-containment)

**Source.** Implementation roadmap
[`research/borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
§R-20 (Wave 1 — independent of HookRegistry).
Primary-source reference impls:

- Aperant `apps/desktop/src/main/ai/security/bash-validator.ts`
  (300 LOC) — per-command validators (`rm`, `chmod`, `git`, `pkill`,
  `psql`) on allow-by-default base, plus secret-scanner.
- Aperant `apps/desktop/src/main/ai/security/path-containment.ts`
  (147 LOC) — symlink-resolved containment with `..` guard.
- Gortex `internal/hooks/bash_classify.go` (266 LOC) — pattern-based
  command classifier (`read-only` / `git-write` / `package-manager-install`
  / `dangerous`), used as the no-LLM pre-pass that drives the
  PreToolUse hook's `permissionDecision`.

**Problem.** The §Policy file pins the **path** allow-list (read /
write globs) and §Amendment 2026-05-20 above adds **capability
flags** (deny-by-default opt-in surface). Neither says anything
about **command-shape** — the actual bash string a Coder-role
sends through `subprocess.run`. Two consequences:

1. `rm -rf /etc` is denied today only because `/etc` falls outside
   the path allow-list. But `git config --global user.email evil@x`
   (no path argument at all) **passes** the path check, runs, and
   rewrites the git identity. Aperant explicitly documents this as
   the canonical «looks innocent, mutates outside scope» trap.
2. A future LLM-using hook (the family-disjoint rule in
   ADR-7 §Amendment 2026-05-20) would have to LLM-classify every
   bash command to decide pass/deny/escalate. The Gortex
   classifier shows the alternative: pattern-match the head token +
   a few flag combinations and the «zero-latency, no-LLM, no-call»
   path holds for the overwhelming majority of commands. AGENTS.md
   PR Checklist rule #10 question 4 («could this be a deterministic
   Python function?») answers YES for command shape.

**Decision.** First-Agent adds a runtime **bash gate** under
`src/fa/sandbox/` with three composable layers, called from the
inner-loop's `run_shell` tool wiring once BACKLOG M-1 lands. The
gate is a pure function — no I/O beyond ``Path.resolve()`` — and
returns a structured `BashGateDecision { allow, category, reason,
validator_result }` for the audit log.

| Layer | File | Borrowed from | Role |
|-------|------|---------------|------|
| Classifier | `src/fa/sandbox/classifier.py` | Gortex `bash_classify.go` | Coarse pattern match → `BashCategory` ∈ {`READ_ONLY`, `GIT_WRITE`, `PACKAGE_INSTALL`, `DANGEROUS`, `GENERAL_WRITE`} |
| Validators | `src/fa/sandbox/validators.py` | Aperant `bash-validator.ts` | Per-command rules for `rm`, `chmod`, `git` (5 deny rules: world-write `chmod`, `git config user.email/name`, `git config --global/--system`, force-push to `main`/`master`, `rm` outside workspace) |
| Path containment | `src/fa/sandbox/path_containment.py` | Aperant `path-containment.ts` | Symlink-resolved «target inside base?» check, used by validators |
| Gate | `src/fa/sandbox/bash_gate.py` | composes the above | `evaluate_bash(command, *, workspace_root) -> BashGateDecision` |

**Pipeline (`evaluate_bash`).** In order:

1. Classify command. If `READ_ONLY` → allow (no validator, no
   containment — pure observation cannot mutate state).
2. If `DANGEROUS`: dispatch to validator (only `rm` / `chmod` have
   one — `rm -rf <safe-path>` MAY be allowed when the target is
   contained); if no validator exists for the head token, deny.
3. If `PACKAGE_INSTALL`: deny unless caller passes
   `allow_package_install=True`. Package installs mutate the
   runtime environment and need explicit caller-side opt-in
   (mirrors Aperant's per-tool decision).
4. If `GIT_WRITE`: dispatch to git validator. Rejects identity
   rewrites + global config + force-push to protected refs;
   passes commit/checkout/merge/etc.
5. If `GENERAL_WRITE`: dispatch to validator if one exists for the
   head token (catches non-recursive `rm` / `chmod` outside the
   workspace); otherwise allow if `allow_general_write=True`
   (default — workspace-internal writes are FA's bread-and-butter).

**Why not a single denylist regex.** Two reasons:

1. **Audit clarity.** A 3-layer pipeline produces a decision whose
   reason field names the specific layer that fired. A regex
   denylist is a black box: an audit reviewer sees only «matched
   pattern N» with no breakdown.
2. **Composition with capability flags.** The classifier's
   `PACKAGE_INSTALL` category is the natural seat for
   `ENABLE_DYNAMIC_TOOLS=True` opt-in (when a future ADR-7
   amendment extends the gate to forward package installs through
   the dynamic-tool path). A regex denylist would need rewriting;
   the classifier is one extension.

**Why deny-by-default at `DANGEROUS` with no validator.** Aperant's
denylist is built on the same stance — a command class that has
*no per-command validator* MUST be denied because the gate has no
way to express «scoped acceptable». `sudo`, `pkill`, `dd`, `mkfs`,
`shutdown`, `psql`, `mongo` all fall here; the validator slate
covers `rm`/`chmod`/`git` only, the rest stay denied until a real
caller produces a use-case and writes a validator.

**Layer interaction with ADR-6 §Policy file.** The bash gate is
the **command-shape** check; the §Policy file is the
**path-shape** check. They are AND-ed at the dispatcher: a `rm
file.py` invocation runs only if (1) the gate's `validate_rm`
returns allow AND (2) `file.py` matches a write-allowed glob in
`sandbox.toml`. Either layer can deny; neither layer can override
the other.

**Subtraction-check (AGENTS.md §Pre-flight Step 4 / rule #10).**

1. **Removing what makes this redundant?** — The §Policy file
   alone is insufficient (the `git config user.email` example
   above). The capability-flag layer alone is insufficient (it
   gates *capability classes*, not *individual command shapes*).
   The gate is the missing third layer; removing it would force a
   future LLM-using hook to take command-shape decisions, which
   AGENTS.md rule #10 question 4 explicitly rejects.
2. **Capability lost if omitted?** — The inner-loop scaffolding PR
   (BACKLOG M-1) would have to land bash dispatch with no shape
   check at all (only path check), and a Coder-role bug like
   `rm $UNSET_VAR/important_dir` would partially execute before
   the path check catches `/important_dir`. The pre-pass classifier
   stops shape-bugs before they reach the filesystem.
3. **OSS precedent for not having it?** — None among the FA
   reference set. Aperant has the validators + path-containment;
   Gortex has the classifier; Kronos has the capability flags
   (already shipped here) + relies on Aperant-style validation
   in its `bash_check` Python equivalent (see Kronos note §0
   R-2). All three converge on «gate is a shape check, not just
   a path check».
4. **Could this be a deterministic function (PR Checklist rule #10
   question 4)?** — YES. The entire gate is pure pattern-matching
   + path resolution; no LLM call, no model judgement. The Gortex
   author explicitly cited zero-latency as a design goal; FA
   inherits the rationale verbatim.

**Reversal triggers.**

- A future ADR introduces dynamic-tool loading with its own
  per-tool sandbox model that supersedes the head-token validator
  set (e.g. MCP-server-shipped validators). The bash gate
  collapses to a 2-layer (classifier + path-containment) form;
  validators are removed.
- The classifier produces too many false positives in real
  workload eval (≥5% of legitimate commands misclassified).
  Demote `PACKAGE_INSTALL` and `GENERAL_WRITE` to a single
  «caller-opt-in-required» bucket and reduce the category count
  to 3 (`READ_ONLY` / `DANGEROUS` / `OPT_IN`).
- An LLM-judge layer with proven KPI-lift over the deterministic
  classifier lands as a replacement (would require an ADR-8 hook
  middleware running BEFORE the deterministic gate, not after).
  The deterministic gate remains as backstop.

**Implementation pointer.** Five files under `src/fa/sandbox/`:
`__init__.py` (40 LOC, re-exports), `path_containment.py` (~95
LOC), `classifier.py` (~225 LOC), `validators.py` (~245 LOC),
`bash_gate.py` (~150 LOC). 4 test files under `tests/`:
`test_sandbox_path_containment.py` (10 tests),
`test_sandbox_classifier.py` (19 tests, parametrised — ~70 cases),
`test_sandbox_validators.py` (29 tests), `test_sandbox_bash_gate.py`
(15 tests). Wiring into the inner-loop's `run_shell` tool is
tracked in BACKLOG M-1; in Phase-M, the inner-loop's
`run_shell.execute` calls `evaluate_bash` before forwarding to
`subprocess.run`.

## References

- [ADR-1](./ADR-1-v01-use-case-scope.md) §UC1 — coding + PR
  scope; PR-write allow-list rationale.
- [ADR-2](./ADR-2-llm-tiering.md) §Decision (Coder mid-tier)
  + 2026-04-29 amendment (no Critic in v0.1).
- [`project-overview.md`](../project-overview.md) §4
  ("PR-write is restricted") and §6 ("remote API ≈ 99 %").
- [`research/cross-reference-ampcode-sliders-to-adr-2026-04.md`](../research/cross-reference-ampcode-sliders-to-adr-2026-04.md)
  §4.1 / §9.3 / §10 R-2 — sandbox gap analysis and ADR call.
- [`research/how-to-build-an-agent-ampcode-2026-04.md`](../research/how-to-build-an-agent-ampcode-2026-04.md)
  §4 — ampcode tool registry shape (read / list / edit).
- gitignore-glob library: <https://github.com/cpburnz/python-pathspec>.
- Python `pathlib.Path.resolve` semantics:
  <https://docs.python.org/3/library/pathlib.html#pathlib.Path.resolve>.
