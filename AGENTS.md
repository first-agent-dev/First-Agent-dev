# AGENTS.md

## Project Overview

> **Agent Pitch:** You are operating inside a strict, zero-trust TCB.
Your code edits are checked via AST analysis, bash commands are monitored by IntentGuard.
Use `fs_blackboard_query` and `fs_search` tools to strictly manage your context window.
Highest virtues are scoped changes and deterministic precision.

**First-Agent** is an implementation-first project aimed at becoming the most token- and tool-call-efficient open-source coding-agent harness.

Session state is managed by per-run SQLite authority (`session.db`). See `knowledge/reference.md` §Session Data Layout.

Goal-formulation in 4 pillars + minimalism-first principle:
[`knowledge/project-overview.md` §1.1](./knowledge/project-overview.md#11-четыре-столпа-цели-project-goal--four-pillars).

## Repository Structure

- [`AGENTS.md`](./AGENTS.md) — main conventions.
- [`worklogs/HANDOFF.md`](./worklogs/HANDOFF.md) — worklog snapshot for cross-session work.
- [`worklogs/`](./worklogs) — session work artifacts: HANDOFF, BACKLOG, implementation plans, pr-notes, archive.
- [`knowledge/llms.txt`](./knowledge/llms.txt) — legacy routing fallback (one-fetch file index).
- [`knowledge/README.md`](./knowledge/README.md) — memory system overview.
- [`knowledge/reference.md`](./knowledge/reference.md) — terms, features, session architecture (single lookup).
- [`knowledge/`](./knowledge) — durable memory for /skills, /codemaps, /ADR, /research, /prompts, etc.
- [`knowledge/instructions/`](./knowledge/instructions/README.md) — deploy and operating docs for human.
- [`knowledge/adr/README.md`](./knowledge/adr/README.md) — index of ADRs.

## Pre-flight checklist

Run BEFORE making any edits, opening a branch, or writing analysis on
non-trivial tasks. Five steps. Output is cheap; skipping is the failure
mode.

Steps 1–3 are literal shell commands; Steps 4–5 are declarations posted
in your analysis openly. Pattern-match the templates exactly.

**Step 1 — Recency surface.** Run:

```bash
git log -n 5 --since="7 days" --oneline -- knowledge/ docs/ AGENTS.md
```

Expect ≤5 commit lines. For any commit touching a 2026-MM-DD research
note in `knowledge/research/`, open the note and skim only its §0
Decision Briefing. Rationale: supersessions and ADR amendments land on
`main` between sessions and silently invalidate older notes; this command
surfaces them in one read.

**Step 2 — Term expansion.** For every project-specific noun in the
prompt (axis, lens, pillar, harness, hook, ACI, UC1..UC5, NLAH, MCP,
subtraction-first, minimalism-first, R-S-M, …), run:

```bash
grep -i "^| \*\*<term>\*\*" knowledge/reference.md
```

Expect exactly one matching row. If the row is missing, fall back to
[`knowledge/project-overview.md` §1.1–§1.2](./knowledge/project-overview.md);
add the term to `knowledge/reference.md` §Terms in the same PR if it is in active use.
Reference.md is the single source of truth for definitions.

**Step 3 — Symmetric reading.** Before citing a research note as
evidence, run:

```bash
grep -ril "<key-term>" knowledge/research/
```

Expect 1..N file paths. Open every file in the output!
Cite from the most recent (`compiled:` date in frontmatter)
unless explicitly superseded.
Reading every match is cheaper than missing one.

**Step 4 — Subtraction-check.** Before adding any artefact (file,
section, rule, frontmatter field, dependency), answer the three
questions verbatim in your analysis:

```text
- Removing what makes this redundant? <name an existing artefact
  that already covers ≥80% of this scope, or "none">
- What capability is lost if this artefact is omitted? <one
  sentence; concrete, not "reduced clarity">
- Open-source agent-stack precedent for not having it? <one URL
  or repo path; or "none found in 5-min search">
```

If the third answer is "none found", keep the existing code as-is —
the burden of proof is on adding, per
[`knowledge/project-overview.md` §1.2](./knowledge/project-overview.md#12-enforceable-principle--minimalism-first)

**Step 5 — Goal-lens declaration.** State in your analysis openly, every session:

```text
- goal_lens: <one-sentence research goal; pick from
  knowledge/prompts/research-briefing.md Stage 1,
  or write free-text>
- project-axes advanced: <pick ≥1 of A noise-reduction |
  B context-finding | C goal_lens-advancement>
- subtraction evaluated: <YES — answers in Step 4 | EXEMPT
  (documentation-only PR with no new artefact) — restate why>
- session-type: <new-feature | bug-fix | refactor | doc-edit |
  reference-edit | dep-bump | research-briefing | other-explain>
```

Four named slots. Pattern-match the template exactly; respect four-pillar goal stated in
[`knowledge/project-overview.md` §1.1](./knowledge/project-overview.md#11-четыре-столпа-цели-project-goal--four-pillars).
`goal_lens` is universal across sessions.

## Working in This Repo

- **Session bootstrap.** Read [`HANDOFF.md`](./worklogs/HANDOFF.md) § 60-second
  bootstrap — it points to `knowledge/llms.txt` §MUST READ FIRST
  (five files, in order). If HANDOFF and llms.txt disagree, llms.txt
  wins. Complete the bootstrap first, then navigate as needed.

- All documentation is Markdown. ATX headings (`#`, `##`), short lines ~150 chars.
- Fenced code blocks
  - ALWAYS open with a language tag:
    - Code: `python`, `yaml`, `json`, `bash`.
    - Non-code (ASCII art, directory trees, prompts, logs): `text`.
  -Close with bare ` ``` `.
- New docs go in the right folder:
  - Guides / references → `knowledge/` (the former `docs/` folder was retired 2026-05-29). Update [`knowledge/llms.txt`](./knowledge/llms.txt) §BY-DEMAND INDEX.
  - Project artifacts (decisions, research, prompts) → `knowledge/`.
- Research notes are read by both humans and agents. Prefer Russian for
  analytical prose, project recommendations. Keep protocol names, API field names, code,
  and direct quotes in their source language.
- readability > size
- Architectural decisions → ADR from [`knowledge/adr/ADR-template.md`](./knowledge/adr/ADR-template.md).
- **Workspace resolution.** Locate the repo root by checking for
  `./AGENTS.md` in the current directory. If present →
  FA root is `.` Always anchor on the current directory.

## Context-budget discipline

When loading context for a task, collect what is **necessary** to complete it — not breadth-first.
Navigate the repo, identify relevant files, read only the parts that move the task forward.
Use [`knowledge/llms.txt`](./knowledge/llms.txt) as the routing surface and [`HANDOFF.md`](./worklogs/HANDOFF.md) as the bootstrap surface.
`session.db` reduces context need: query `session.session_db` instead of scanning JSONL files for session data.
Use §-anchors and grep-windows! Goal - keep the agent's working prompt focused on the task
and to leave headroom for the actual edits, traces, and tool-output.

**Design invariant**
Any single LLM call's total input — system prompt + role prompt + tool definitions + retrieved chunks + scrollback + in-line memory

## Industry-proven rules (from prior art in OSS agent stacks)

Following rules are standard practice across multiple open-source
agent projects. Violations of any of these caused reverts in production.

1. **Keep the system human-curated.** Self-improving subsystems
   are a known anti-pattern — write them only when the host
   system is mature enough to validate their output.

2. **Estimate tasks by scale (files touched).** Measure scope
   by files touched or eval-pass count. Use scope-only metrics.

3. **Every write target must have an active consumer.** Every new
   file, table, metric, or event-channel lands with a named
   automated or human consumer in the same PR.

4. **Every new ADR requires a §Prior Art section.** Document
   existing tools, papers, or projects that solve the same problem.

5. **Build the runtime model before fixing infrastructure errors.**
   When failure occurs: state what implicit behaviors the tool has in that environment. Then read the tool's documentation. Focus on fixing the abstraction.
   Use [Anti-patterns](./knowledge/anti-patterns/) for debugging.

## Loadable skills

Per-task agent-loadable disciplines live in
[`knowledge/skills/`](./knowledge/skills/) — directory-per-skill,
shapes - `.agents/skills/<name>/SKILL.md`
Skills are loaded on the trigger condition:

| Skill | Trigger and scope |
| :--- | :--- |
| [`pr-creation`](./knowledge/skills/pr-creation/SKILL.md) | **Trigger:** Before opening any PR (including pure-doc PRs).<br><br>Canonical PR-creation rulebook. Carries the 5-intent classifier (`RESEARCH / ADR-RULE / IMPLEMENT / FIX / CHORE`). The PR description AND the first commit message body MUST open with the header lines specified by the skill's §Output format. The planned `prepare-commit-msg` / `commit-msg` reads the skill's §Reference tables as the single source of truth. Applies to every PR. |
| [`repo-audit`](./knowledge/skills/repo-audit/SKILL.md) | **Trigger:** When asked to perform a critical structure / doc / skill review.<br><br>Carries the 7-phase audit workflow (orientation → inventory → cross-reference → invariants → contradiction sweep → demotion ledger → final report). |
| [`mutation-clearing`](./knowledge/skills/mutation-clearing/SKILL.md) | **Trigger:** When tasked with mutation testing fixes (`mutmut`) or mutant hunts.<br><br>Carries the 4-archetype triage taxonomy, spy isolation rules, and accepted equivalent mutants ledger criteria for zero-trust mutation clearing. |
| [`tests-writing`](./knowledge/skills/tests-writing/SKILL.md) | **Trigger:** Before writing/changing tests, or when IMPLEMENT/FIX under `src/fa/` claims product/session behavior.<br><br>Live-path Definition-of-Done (ADR-11-I9): composition-root tests (`drive_session` / shipped CLI), anti-theater kill-check, flag matrices. Authority remains `just check` / pytest — this skill steers how tests are written. |
| [`feature-planning`](./knowledge/skills/feature-planning/SKILL.md) | **Trigger:** Large feature implementation, new-project work, or MAX-effort plan→execute slices.<br><br>Source-grounded production orchestration: preflight, GAP#/CT#/S#/T# traceability, deterministic authority, before/per/after edit gates, live-path tests, producer kill-checks, mutation handoff, and minimal-code/evidence gates. |
| [`doc-maintenance`](./knowledge/skills/doc-maintenance/SKILL.md) | **Trigger:** At session close, or when moving/pruning/adding any file under `knowledge/` or `worklogs/`.<br><br>Ensures link integrity, llms.txt updates, and HANDOFF freshness. Replaces former `knowledge/MAINTENANCE.md` routing file. |

New skills land as `knowledge/skills/<name>/SKILL.md` with a row added to this table.

## Development Workflow

- Branch: `fa/<timestamp>-<slug>` from `main`.
- All changes via Pull Request.
- You focus on logic implementation. Harness tool does styling.

### Checkout roles and workspace readiness

- `~/First-Agent-dev` is the **operator development clone**. Open this path for
  VS Code/SSH development, commits, feature branches, and PR preparation.
- `/srv/first-agent/repo/First-Agent-dev` is the **clean deployment mirror**.
  It is updated only through the operator-controlled deployment flow; do not
  develop, create feature branches, or commit there.
- First-Agent-created session workspaces are managed clones. Their lifecycle
  prepares `.venv`, all four Git-hook seats, and pre-commit environments before
  model/provider work. The model must not spend tool calls rebuilding them.
- The readiness guarantee covers managed clones and the canonical operator clone
  after the command below. It does not claim that arbitrary raw clones can
  self-install hooks when no hook seat exists.

From the operator development clone, one command performs host-tool setup and
locked workspace readiness:

```bash
cd ~/First-Agent-dev
uvx --from rust-just==1.57.0 just agent-bootstrap
```

If `uv`/`uvx` is missing, install uv once using the
[official installation guide](https://docs.astral.sh/uv/getting-started/installation/),
then rerun the same command. `just doctor` is the read-only status/recovery
check.

The VS Code `folderOpen` task is a **best-effort convenience**, not readiness
authority: task execution depends on user permission. Explicit terminal recovery
must continue to work when VS Code does not run or authorize the task.

## Just recipes (public surface)

Agents and humans use the **six public recipes** below. Underscore-prefixed
recipes (e.g. `_lint`, `_targeted-mutmut`) are INTERNAL; they exist for
composition and are hidden from `just --list`. Do not rely on them as a
stable surface — invoke them only when debugging a single gate.

| Recipe | Purpose |
| --- | --- |
| `just doctor` | Read-only readiness check (uv/just/python≥3.13/environment/hooks/marker/cache sentinel/uv.lock). |
| `just install` | Direct checked-out workspace readiness: locked dev sync, pre-commit prewarm, four hook seats, and verification. |
| `just fix` | Auto-fix every mechanical finding: `ruff check --fix-only` → `ruff format` → trailing `ruff check`. |
| `just test` | Pytest with branch coverage + CLI coverage-floor gate. |
| `just check` | Full blocking gate chain (no fail-fast, collects ALL errors): lock-check, lint, mypy strict, pyrefly, authoring, contracts, shell-syntax, test+coverage. Advisory vulture prints at the end and does NOT fail the run. |
| `just check-deep` | `just check` + targeted-mutmut + targeted-semgrep on changed files. This is what `pre-push` runs. |

Harness-facing compatibility alias: `just agent-bootstrap`. It conditionally
prepares pinned `just`, delegates workspace state to the same checked-out
readiness engine, and emits `FA_AGENT_READY=1` only after READY.

- **Workspace bootstrap is deterministic lifecycle work.** Managed session
  admission runs it before provider construction; agents do not run bootstrap
  commands as task work. Operators may use the explicit recovery command above.
- **Lint is autofix-first.** Run `just fix` after editing code — it
  handles formatting (import order, `__all__` sorting, quoting, line
  wrapping). The pre-commit hook also applies these safe fixes.
- **pre-commit (per commit):** runs ruff/format/deptry/pylint-gap/mypy/
  pyrefly/shell-syntax/gitleaks/markdownlint/doc-links/uv-lock/whitespace.
  Budget: ~60 seconds on the operator's i5-1235U (much faster on warm cache).
- **pre-push (per push):** runs `just check-deep` which is `just check`
  plus targeted-mutmut and targeted-semgrep on changed files. pip-audit
  runs ONLY in CI (network access). Full-repo mutmut/semgrep run weekly,
  not on the push path.
- **Escape hatches:** `FA_HOOK_SKIP_FULL_CHECK=1 git push` skips the entire
  pre-push gate (operator-only). Narrower: `FA_SKIP_TARGETED_MUTATION=1`
  or `FA_SKIP_TARGETED_SEMGREP=1`.
- **Before opening a PR for review**, `just check-deep` should be green.
  The pre-push hook enforces this; CI duplicates in parallel for
  cross-machine confirmation.
- **Judgment rules** (`S`, `BLE001`, `C901`, pylint `duplicate-code`/
  `cyclic-import`, TRY201/203/401, RUF012/013/015): these signal a
  design problem — fix the design that caused the finding. Waive with
  `# noqa: <code> — <reason>` only when you can explain why the flagged
  pattern is intentional (e.g. a fail-closed boundary, a sandboxed
  `shell=True`, an observer that must never throw). Every waiver MUST
  carry a one-line rationale; the CI surface treats a bare `# noqa: XXX`
  without explanation as a failing finding.
- **Type-checker errors** (mypy strict, pyrefly): fix by writing
  code that validates data at the boundary — the type checker error
  disappears because the logic is genuinely correct, not silenced.
  Pattern from `src/fa/inner_loop/tools/base.py`:

  ```python
  def require_string(params: Mapping[str, object], key: str) -> str:
      value = params.get(key)
      if not isinstance(value, str):
          raise ValueError(f"{key} must be a string")
      return value  # type checker knows this is str
  ```

  The `isinstance` check serves two purposes: it validates untrusted
  input at runtime AND narrows the type for the checker. Both the
  code and the types are correct — no annotation shortcuts needed.
- **Harness product behavior** is not done until a composition-root test would
  fail if the production call site were removed (ADR-11-I9). Load
  [`tests-writing`](./knowledge/skills/tests-writing/SKILL.md) before writing
  those tests. Prefer `tests/test_*_wiring.py` patterns already in tree.
- **Existing tests are protected.** Deleting/renaming any `tests/**`
  file is blocked at the hook and harness seats; modifying one during a
  FIX-shaped diff requires a `TEST-EDITS:` declaration in the PR draft
  (see [`pr-creation` skill §Test-edit declaration](./knowledge/skills/pr-creation/SKILL.md#test-edit-declaration)).
  Fix the code to pass the test, keep the test as spec.
- Commit messages: descriptive, English, present tense (`docs: add architecture note`).
- Push to your branch; merge to `main` only via Pull Request.
- **`AI-Session:` git trailer** rule (per-commit; example included) lives in the [`pr-creation` skill §AI-Session trailer](./knowledge/skills/pr-creation/SKILL.md#ai-session-trailer)

## Query Routing

Route questions to the right folder. Load only what the task needs.

| Question type | Look first | Verify with |
| --- | --- | --- |
| Architecture, patterns, Decisions and rationale | [`knowledge/adr/`](./knowledge/adr/) | ADR |
| Current task | [`worklogs/HANDOFF.md`](./worklogs/HANDOFF.md) | Session start |
| Research findings | [`knowledge/research/`](./knowledge/research/) | Primary sources from `source:` frontmatter |
| Specific decision / quote / number / date | **Primary source** (URL / code / gist), not a summary note | — |
| Terms | [`knowledge/reference.md`](./knowledge/reference.md) §Terms | — |
| Session state / event history / data layout | [`knowledge/reference.md`](./knowledge/reference.md) §Session Data Layout | `session.db` (SQLite authority) |

**Chain-of-custody rule.** If citing a specific decision / quote / number / date,
go to the primary source and quote from there.
Summaries in `knowledge/research/` are pointers, not authoritative sources.

- **Session close.** Update [`worklogs/HANDOFF.md`](./worklogs/HANDOFF.md) per its
  §Session Protocol (overwrite §Current state, rewrite §Next); load [`doc-maintenance`](./knowledge/skills/doc-maintenance/SKILL.md) skill before committing.
  Update [`knowledge/llms.txt`](./knowledge/llms.txt) rows per doc-maintenance skill §When adding a new file.

## Querying Artifacts — Tool Selection by Intent (ADR-14/15, S14, 2026-08-10)

- **Bootstrap (mandatory, unchanged):** Read AGENTS.md → llms.txt §MUST READ FIRST (5 files in order) → project-overview.md → HANDOFF.md before any tool use.

### Intent → tool (exhaustive, ordered)

| Intent | Tool | Why this one |
| --- | --- | --- |
| «What artifact _types_ exist? List all skills/ADRs/research/...» | `fs_blackboard_query(type="skill")` (or adr/research/instruction/prompt/codemap/antipattern/file_version) | Returns typed, content-hashed rows with id, title, path, timestamps; triggers lazy index on first call; 50-row cap, token-cheap. **Does not search file bodies.** |
| «Find an artifact whose _title or path_ mentions X (e.g. skill name contains "api")» | `fs_blackboard_query(type=…, key="api")` | `key` matches substring against entry metadata (title/path/hash), NOT body content. Used for name-scoped lookup. |
| «Which file versions did I (or a prior step) already touch in this session?» | `fs_blackboard_query(type="file_version")` | Returns `pre-<uuid>`/`post-<uuid>` mutation snapshots with read_set/write_set — the substrate's change log. |
| «Find _content_ somewhere in the repo — body substring, across code AND docs, don't know type yet» (DEFAULT START) | `fs_search(query="…", output_mode="files", limit=10)` | FTS5 BM25 + trigram, <50ms after first-call index, returns **paths with match_count + first-match snippet** (respects .gitignore, prunes code + docs equally). Add `glob="*.py"` for path filter; `include_tests=false` to exclude tests/. |
| «Find files whose names/paths match a glob (e.g. all test files under X)» | `fs_search(query="", glob="tests/**/test_*.py", …)` — or `fs_search(query=" ", glob="pattern")` | Glob is a parameter on fs_search; no standalone glob tool. For pure name listing use fs_search with a broad query and the glob filter. |
| «I have a path — read the actual bytes now» | `fs_read_file(path=…)` | Body retrieval is a separate step; discovery tools return metadata/paths, not bodies. |
| «I need matching lines with content/numbers inline (use sparingly)» | `fs_search(query="…", output_mode="matches", context_lines=1, glob="*.py")` | Returns `{path,line,content,before,after}`. Use only after `files`-mode identified the relevant files and you need exact line numbers (e.g. to target an edit_file). |
| «I need contiguous snippets around matches to read code without a separate read_file» | `fs_search(query="…", output_mode="regions", context_lines=2)` | Groups adjacent matches into contiguous `{path, start_line, end_line, snippet}` windows. Token-efficient alternative to fs_read_file when the answer is a short code region. |
| «I am about to WRITE a file» | Mutation guard flow: declare read_set + write_set + assumptions (base `git rev-parse HEAD`, llms.txt hash) + version_dependencies; blackboard runs `detect_conflict()`; on conflict return structured `ToolResult.fail(code="conflict_detected")`, never silent overwrite (fixes Claude bug #55708). | Prevents cross-run/cross-agent stomps via type-scoped write_set overlap. |

### Combinators you will actually use

1. **Type-browse:** `fs_blackboard_query(type="adr")` → skim titles → `fs_read_file(path=…)` on the relevant ones.
2. **Body search (S14b.1):** Start with `fs_search(query="auth", output_mode="files")` → inspect returned paths (each includes a short snippet so you can usually decide without a separate read) → if you need the typed metadata/hash, `fs_blackboard_query(key=<filename>)` (key is a substring of the relpath) → use its `content_hash` in `version_dependencies`. Only escalate to `output_mode="matches"` (exact lines) or `output_mode="regions"` (contiguous snippets) when files-mode snippets are insufficient.
3. **Before writing:** gather read_set from tools above → invoke mutation guard → blackboard serializes.

### Hard rules (S14b.1)

- **Do NOT** slurp llms.txt/BACKLOG.md wholesale for "full list of artifacts" (deprecated by ADR-14/15); use `fs_blackboard_query(type=…)` or `fs_search(query="…", glob="knowledge/**")`.
- **Do NOT** call `fs_blackboard_query(key="…")` expecting body-content hits — it searches metadata only. For body, `fs_search`.
- **Do NOT** invoke `grep`/`rg`/`find`/`ag`/`ack` via `fs_run_bash` for discovery. The two approved discovery tools (`fs_blackboard_query` for typed artifact metadata; `fs_search` for file body/path/glob/line content) enforce token budgets, 30KB response caps, and .gitignore pruning; raw shell grep historically caused 124-step timeouts.
- **Do NOT** call `fs_search` with `output_mode="matches"` or `"regions"` as your first move. DEFAULT to `output_mode="files"`; escalate only after you know which files matter. This is the primary token-budget defense.
- **Do NOT** invent additional search flags or tools; the set above is closed. If a query truly cannot be expressed within them, surface the gap as an observation rather than reaching for bash.
- Rows are lazily indexed on first artifact-typed query; the returned `"indexed"` field reports scanned/added/updated/skipped/errors — useful for diagnostics but do NOT surface raw stats to the user unless asked.
- fs_search `context_lines` is clamped to 0–5 and `limit` to 1–50; requesting higher values is silently clamped with a warning, not an error.

### Single-entry point & authority

- Blackboard is the single entry point for **typed artifacts and mutation history**; it is NOT the session bootstrap (bootstrap stays AGENTS.md + llms.txt MUST READ FIRST).
- `session.db` is the SQLite authority for hot-path runtime state (3 tables: event_log, blackboard, session_meta). JSONL files (`.fa/blackboard/*.jsonl`) are best-effort mirrors — if they disagree with `session.db`, `session.db` wins. See `knowledge/reference.md` §Session Data Layout for the full schema and authority hierarchy.
