# ADR-6 — Tool sandbox & path allow-list policy for v0.1

- **Status:** accepted
- **Date:** 2026-04-29
- **Deciders:** project owner (`0oi9z7m1z8`), Devin (drafting)

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
