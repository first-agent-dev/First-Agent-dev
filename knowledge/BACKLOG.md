# Backlog — deferred ideas with unblock triggers

> **Purpose.** Single canonical list of architectural ideas
> deferred from Stage 1 (Agent-driven, per
> [`project-overview.md` §1.3](./project-overview.md#13-three-stage-project-evolution)).
> Without this, deferred ideas get lost between sessions. Each
> entry has an **unblock-trigger** — the concrete artefact whose
> existence moves the idea from «deferred» to «actionable».
>
> **Maintenance rule.** When an idea becomes actionable, move it
> from this file into the next PR's scope; do not delete it
> silently — leave a one-line «landed in PR #N» marker so the
> session that originally deferred it can be audited. When a new
> idea is deferred (rather than rejected) during a session,
> append it here in the same session it was proposed.
>
> **Distinction from [`HANDOFF.md`](../worklogs/HANDOFF.md) §Current state.**
> HANDOFF tracks items **in flight right now**; BACKLOG tracks
> items **deferred with an unblock-trigger**. Different scopes,
> different cadences, do not merge.

## I-1 — Planner picks needed skills / tool-calls at planning stage

- **Status:** deferred from Stage 1 (proposed 2026-05-08 chat).
- **Idea:** The lower-tier Coder LLM should not see all ~20 tool
  specs in every call. The Planner pre-selects the relevant 3-5
  for the current task; the tool registry shape allows lazy load
  so unused specs never enter Coder context.
- **Blocked-on:** Implementation half of
  [ADR-7](./adr/ADR-7-inner-loop-tool-registry.md) — the
  contract has landed (ADR-7 §2 ToolSpec / ToolResult), but the
  `src/fa/inner_loop/` module that materialises it has not.
  Without a runnable registry, there is nothing to pick from.
- **Unblock-trigger:** ADR-7 merged ✅ (2026-05-12) **and**
  `src/fa/inner_loop/` module lands with the
  `src/fa/inner_loop/registry.py` `ToolSpec` dataclass plus
  loader per ADR-7 §2 — currently the canonical path; the
  earlier `src/fa/tool_registry/` working name is superseded.
- **First concrete step once unblocked:** Extend
  [`knowledge/prompts/architect-fa.md`](./prompts/architect-fa.md)
  Step 2 «Bounded recon» with a tool-selection sub-step; the
  Coder system prompt receives the selected subset, not the full
  registry.
- **Why it satisfies rule #11 mitigation (b) «Lazy-load».** This
  idea is the lazy-load primitive
  [`AGENTS.md` §Context-budget discipline (rule #11)](../AGENTS.md#context-budget-discipline) explicitly
  references when a harness component pushes past ~100 k tokens.

## I-2 — Agent + sub-agents for context-load reduction

- **Status:** deferred from Stage 1 (proposed 2026-05-08 chat).
- **Idea:** A parent orchestrator spawns child sub-agents for
  isolatable sub-tasks (research fan-out across multiple sources,
  parallel chunker over multiple inbox files, parallel test
  runs); the parent merges results. The parent's context stays
  bounded because the big-context work happens inside child
  contexts that vanish after returning their summary.
- **Blocked-on:** Phase-M `src/fa/` runner (child-process
  plumbing, sandbox propagation per
  [ADR-6](./adr/ADR-6-tool-sandbox-allow-list.md), merge
  protocol). No runner exists yet — only the chunker scaffolding
  under `src/fa/chunker/`.
- **Unblock-trigger:** UC1 end-to-end demo working **and** the
  first Phase-M PR lands a runner with a child-spawn primitive.
- **First concrete step once unblocked:** A small ADR (Pre-ADR-9?)
  scoping the sub-agent boundary — same model tier? Per-sub-agent
  audit log? Whose `sandbox.toml` applies, parent or child?
- **Prior art:** archived `research/agent-video-research.md` §12
  (deferred Mem0-style workspace), archived
  `research/llm-wiki-community-batch-2.md` (Whisper +
  Claude-subagents pattern — rejected for v0.1 single-user
  scope; revisit when UC4 returns).
- **Why it satisfies rule #11 mitigation (a) «Sub-agent split».**
  This is the canonical instance of the sub-agent split rule #11
  references; until I-2 lands, mitigation (a) is hypothetical.
- **Sub-agent invocation rules (R-23, captured 2026-05-20 docs-
  only — apply when this item unblocks).** Three non-obvious
  correctness fixes lifted ahead of time from Aperant
  `apps/desktop/src/main/ai/runners/subagent.ts` (item 7 in
  [`research/gortex-aperant-inspiration-2026-05.md`](./research/gortex-aperant-inspiration-2026-05.md)
  Part 2) — written here so the I-2 PR cannot regress:
  1. **`generateText`, not streaming.** Sub-agent output flows
     back to the orchestrator's context, not to a human-facing
     UI. Streaming adds per-token overhead with no consumer;
     `generateText` (or the FA equivalent: single non-streaming
     completion) is the correct invocation. Streaming MAY be
     used inside the sub-agent for its own tool-LLM calls if
     those tools need it; it MUST NOT be the sub-agent → parent
     interface.
  2. **Remove `SpawnSubAgent` from the sub-agent tool set.**
     Recursion is forbidden; the sub-agent MUST NOT spawn
     further sub-agents. The orchestrator removes the spawn-
     tool from the child's tool registry at dispatch time —
     not by trusting the child to «not call it». Cross-link:
     [`pr-creation` skill §PR Checklist rule #10 question 1 «Spawn-
     recursion anti-pattern»](skills/pr-creation/SKILL.md#pr-checklist).
  3. **`SUBAGENT_MAX_STEPS ≤ 100`.** Hard cap on a single sub-
     agent's iteration count. Aperant uses exactly `100`; FA
     inherits the number until measured otherwise. The cap
     lives in `~/.fa/config.yaml`, NOT in code (per
     [ADR-7 §Amendment 2026-05-20](./adr/ADR-7-inner-loop-tool-registry.md#amendment-2026-05-20--retry-budget-invariant-intra-role-t10-llm-using-hook-family-disjoint-rule)
     rule 1: «retry budget is config-bounded»).

  These three rules ALSO survive in
  [ADR-7 §Amendment 2026-05-20](./adr/ADR-7-inner-loop-tool-registry.md#amendment-2026-05-20--retry-budget-invariant-intra-role-t10-llm-using-hook-family-disjoint-rule)
  rule 5; that ADR amendment is the canonical version, this
  bullet is the read-side mirror so anyone landing the I-2
  unblock PR sees the rules without round-tripping through
  ADR-7.

## I-3 — Dispatcher LLM (lazy-load skills + collect repo parts on-the-fly)

- **Status:** deferred from Stage 1 (proposed 2026-05-08 chat).
- **Idea:** A small dispatcher LLM (between session-start router
  and main Coder) collects relevant repo parts on-the-fly and
  injects them into the main Coder context. Lazy-load skills
  (`~/.fa/skills/` or `knowledge/skills/`) and lazy-load research
  notes; cache invariants per
  [`research/efficient-llm-agent-harness-2026-05.md`](./research/efficient-llm-agent-harness-2026-05.md)
  R-8 static-layered-prompt finding.
- **Blocked-on:** Same as I-1 (tool registry exists) **plus** the
  skills system (ADR-8 TBD per
  [`project-overview.md` §1.1](./project-overview.md#11-четыре-столпа-цели-project-goal--four-pillars)
  Pillar 4 «iteration via measurement» — agent writes its own
  `SKILL.md`).
- **Unblock-trigger:** ADR-7 **and** ADR-8 both merged;
  `~/.fa/skills/` or `knowledge/skills/` directory exists with a
  loader contract.
- **First concrete step once unblocked:** Extend
  [`knowledge/prompts/RESOLVER.md`](./prompts/RESOLVER.md) from
  static intent table to a prompt-callable dispatcher; the
  current T1..T5 rows remain as the fallback table when the
  dispatcher cannot route.
- **Collapses with I-1.** Both need ADR-7 + ADR-8 first; the
  «lazy-load» framing is the key delta over today's static
  RESOLVER.md. Open question for ADR-8: do I-1 and I-3 ship as
  one component or two?

## I-4 — Pre-flight EXEMPT clause needs explicit scope criteria

- **Status:** deferred from Stage 1 (proposed 2026-05-10
  critical-re-pass of `repo-audit-2026-05-10.md`).
- **Idea:** [AGENTS.md §Pre-flight Step 4](../AGENTS.md#pre-flight-checklist)
  EXEMPT clause covers «documentation-only PRs that introduce no
  new artefact (translations, typo fixes, link updates)» — but
  boundary cases are ambiguous (new section under existing
  artefact? renaming a frontmatter field? bumping a date?). A
  mid-tier Stage-2 LLM would apply EXEMPT inconsistently and
  either over-claim (skipping subtraction proof on real additions)
  or under-claim (writing 3-question proof for a typo fix).
- **Blocked-on:** agents decide EXEMPT
  per PR with full diff context. The ambiguity becomes a runtime
  LLM problem only when the agent opens PRs.
- **Unblock-trigger:** First Stage-2 session opens a PR
  autonomously and needs to apply EXEMPT.
- **First concrete step once unblocked:** Enumerate EXEMPT
  criteria as a closed list — e.g. «(a) link-target update only;
  (b) typo / formatting only; (c) date / version bump only;
  (d) translation, no semantic change; (e) new section under
  existing artefact = NOT EXEMPT». Add a `docs/glossary.md` row
  for «EXEMPT (documentation-only PR)».
- **Why this is LOW ROI for Stage 1.** Agent reads full PR diff
  before deciding; mid-tier LLMs do not. Per
  `repo-audit-2026-05-10-revised.md` §3.6 — process-coordination
  concern, not runtime LLM performance.

## I-5 — RESOLVER.md T2-T5 rows lack standalone template files

- **Status:** deferred from Stage 1 (proposed 2026-05-10
  critical-re-pass of `repo-audit-2026-05-10.md`).
- **Idea:** [`knowledge/prompts/RESOLVER.md`](./prompts/RESOLVER.md)
  intent table routes T2-T5 (planner, coder, debug, eval) to
  template **sections** inside
  [`knowledge/prompts/prompting.md`](./prompts/prompting.md)
  rather than standalone files. A non-Agent agent following the
  intent table reaches the §T2-T5 anchors but the templates are
  inline, not split into per-role files.
- **Partial progress (2026-05-29):** `prompting.md` moved from
  `docs/` to `knowledge/prompts/` next to RESOLVER.md, and the
  RESOLVER T2-T5 rows now cite the co-located `./prompting.md §Tn`
  anchors (option (b) below, partially realised — the cross-folder
  «no file yet» fallback is gone). Item stays open: the templates
  are still inline sections, not the standalone per-role files of
  option (a).
- **Blocked-on:** First autonomous session attempts a planner /
  coder / debug / eval task from a template path.
- **Unblock-trigger:** Either (a) extract T2-T5 templates to
  standalone files (`knowledge/prompts/planner-fa.md`,
  `coder-fa.md`, `debug-fa.md`, `eval-fa.md`), or (b) ✅ done —
  RESOLVER.md cites `knowledge/prompts/prompting.md` anchors directly.
- **First concrete step once unblocked:** Decide between (a)
  and (b). Option (a) parallels the existing
  [`prompts/architect-fa.md`](./prompts/architect-fa.md) /
  [`architect-fa-compact.md`](./prompts/architect-fa-compact.md)
  split, but multiplies file count by 4. Option (b) is lower-
  touch (anchor-only change in RESOLVER.md).
- **Why this is LOW ROI for Stage 1.** The agent picks the template
  manually at session start with full context. Per
  `repo-audit-2026-05-10-revised.md` §3.22.

## I-6 — Pre-commit regenerator for `knowledge/llms.txt`

- **Status:** deferred from Stage 1 (proposed 2026-05-12 chat,
  post-PR #6 merge).
- **Idea:** Python script regenerates
  [`knowledge/llms.txt`](./llms.txt) §BY-DEMAND INDEX from the
  current tree of `docs/` + `knowledge/` (reads each `.md`
  frontmatter, collects path / description / line-count /
  supersession banner). A pre-commit hook + CI workflow run
  `python scripts/regenerate_llms_txt.py && git diff --exit-code
  knowledge/llms.txt` so a stale `llms.txt` blocks the commit /
  fails CI. After landing, [`pr-creation` skill PR Checklist rule #7](skills/pr-creation/SKILL.md#pr-checklist)
  and [`MAINTENANCE.md` §When adding a new file](./MAINTENANCE.md)
  stop being a human responsibility — drift becomes technically
  impossible.
- **Blocked-on:** `.pre-commit-config.yaml` does not exist in the
  repo yet (Phase S scaffolding not closed). Landing the
  regenerator hook in isolation creates a lone infrastructure
  file; better to land it alongside the base hooks (ruff /
  end-of-file-fixer / markdownlint).
- **Unblock-trigger:** `.pre-commit-config.yaml` lands in the
  repo with base hooks; **OR** the lead decides to add the
  regenerator as a standalone hook before the rest of the base
  pre-commit stack.
- **First concrete step once unblocked:** Add
  `scripts/regenerate_llms_txt.py` (~80 lines) walking `docs/` +
  `knowledge/`, reading frontmatter `description:` and counting
  lines, rendering the BY-DEMAND INDEX section in the existing
  format. Add a hook entry in `.pre-commit-config.yaml`. Add a
  CI workflow `.github/workflows/lint-llms-txt.yml` running the
  same `git diff --exit-code` check.
- **References:** the `llms.txt` auto-generator concept originated
  in the now-retired `docs/workflow.md` Phase-S step 7 (folder
  deleted 2026-05-29; concept preserved here); AGENTS rule #7
  (current manual rule); [`MAINTENANCE.md` §When adding a new file](./MAINTENANCE.md)
  (current manual checklist landed in PR #6).
- **Why this is LOW ROI until base pre-commit stack exists.**
  Adding a single hook before the rest of the stack means the
  next PR (basic ruff / format / markdownlint hooks) will have to
  re-touch `.pre-commit-config.yaml` anyway; bundling avoids two
  configuration touches.

## I-7 — Bootstrap-cost as auto-collected KPI (UC5-blocked)

- **Status:** deferred from Stage 1 (proposed 2026-05-12 chat,
  follow-up to PR #5 baseline).
- **Idea:** Move bootstrap-cost from a one-off measurement
  (current [`research/bootstrap-cost-baseline-2026-05.md`](./research/bootstrap-cost-baseline-2026-05.md))
  to a continuously-tracked KPI. Each Agent (or First-Agent OWN
  harness) session emits its bootstrap metrics — calls, files,
  context tokens, file-list — at session end; an aggregator
  produces medians, p90, and threshold alerts (e.g. median
  bootstrap-calls > 30 → red).
- **Blocked-on:** UC5 eval-harness (per
  [ADR-1 Amendment 2026-05-06](./adr/ADR-1-v01-use-case-scope.md))
  — no infrastructure to collect / aggregate metrics. Today the
  baseline is manual: chat → user → research note.
- **Unblock-trigger:** UC5 eval-harness ships a metrics-collection
  pipeline (probably under `src/fa/eval/`); ADR-1 §UC5 moves from
  *deferred* back to *in scope*.
- **First concrete step once unblocked:** Extend the UC5 metric
  schema with bootstrap-cost rows (tool_calls, files_opened,
  context_tokens, file_list); auto-emit from each session via a
  post-session hook; migrate the existing §6 baseline table from
  `bootstrap-cost-baseline-2026-05.md` into the KPI store as
  the historical row.
- **References:** [`research/bootstrap-cost-baseline-2026-05.md`](./research/bootstrap-cost-baseline-2026-05.md)
  §9 (re-measurement triggers, item 6 explicitly points here);
  [`project-overview.md` §1.1](./project-overview.md#11-четыре-столпа-цели-project-goal--four-pillars)
  Pillar 4 (iteration via measurement).
- **Prior-art enforcement (DPC ADR-015, added 2026-05-13):**
  Before any FA self-modification capability (auto-amend ADR /
  auto-edit config / auto-evolve skills) lands as an ADR, this
  eval-harness (I-7) **MUST be operational** AND show external
  (non-self-reported) fitness signal. Otherwise =
  «elaborate emptiness» trap (DPC ADR-015 — background evolution
  worker deleted after 20+ sessions / ~40 proposals with 0
  measurable improvement; see
  [`research/dpc-messenger-inspiration-2026-05.md`](./research/dpc-messenger-inspiration-2026-05.md)
  §0 R-5, §2 Pattern 13, §6 Anti-pattern AP1).

## I-8 — Mid-tier × First-Agent's own harness bootstrap re-test

- **Status:** deferred from Stage 1 (proposed 2026-05-12 chat,
  post Arena.ai F / G / H sessions added to PR #5 baseline).
- **Idea:** PR #5 + this extension's 6-session baseline (3 Agent
  + 3 Arena.ai) validates that the routing surface works **across
  external harnesses**. It does **not** validate that the routing
  surface works **on First-Agent's own future mid-tier harness**
  (the Pillar-3 goal: a minimalist OSS-coder-tier agent). Arena's
  harness is general-purpose; FA's own harness will be
  stripped-down. The confound: Arena's smart bootstrap behaviour
  may compensate for any routing-surface weakness that FA's own
  minimalist harness would expose. Until measured, this is
  unanswered.
- **Blocked-on:** First-Agent does not yet ship an end-to-end
  agent — only `src/fa/chunker/` scaffolding from ADR-5 exists.
  Phase M (per
  [`project-overview.md` §1.3](./project-overview.md#13-three-stage-project-evolution))
  will land the inner-loop after ADR-7 merges. Without a runnable
  agent there is nothing to re-measure on.
- **Unblock-trigger:** First-Agent Phase M ships an end-to-end
  agent (Coder tier per
  [ADR-2](./adr/ADR-2-llm-tiering.md)) capable of running the
  same single-message ADR-7-prep prompt that PR #5 / this PR
  used. The Coder tier is the canonical mid-tier OSS target.
- **First concrete step once unblocked:** Adapt the bootstrap
  prompt to FA's own harness invocation pattern; run 3 sessions;
  produce a supplementary measurement-evidence note
  `bootstrap-cost-mid-tier-2026-XX.md` (or amend the existing
  baseline note with §11 Mid-tier extension). If the 6-file
  irreducible core reproduces → routing-design proposals **A**
  (DIGEST.md routing for sequential-ADR readers), **D** (tiered
  bootstrap surface — split current §MUST READ FIRST into top-tier
  / mid-tier variants), and **H** (sequential-routing instruction
  inside DIGEST telling the reader to expand only on demand) stay
  **dropped** (their premise required the core to fail on
  mid-tier). If the core does not reproduce → re-evaluate A / D /
  H with the new evidence. Source artefact for these proposals is
  a session-internal review document (`agent-reading-optimization
  -review.md`, chat-only, not preserved in the repo tree — same
  status as `agent-reading-optimization-input.md` cross-referenced
  in [`research/bootstrap-cost-baseline-2026-05.md`](./research/bootstrap-cost-baseline-2026-05.md)
  `chain_of_custody` frontmatter block).
- **Out-of-scope alternative.** Running this on the Coder-tier
  LLM **without** FA's own harness (e.g. on Arena.ai with an
  OSS-tagged model) would not isolate harness vs routing — Arena
  routes to multiple unspecified models, and Arena's harness is
  not minimalist. Repo-readability across external harnesses is
  already validated by F-H; the open question is
  harness × routing interaction on FA's own harness.
- **References:**
  [`research/bootstrap-cost-baseline-2026-05.md`](./research/bootstrap-cost-baseline-2026-05.md)
  §3 (6-file irreducible core); §9 (re-measurement triggers,
  item 5 points here). Proposals A / D / H are inlined above —
  their authoritative source (`agent-reading-optimization-
  review.md`) is a session-internal review document not preserved
  in the repo tree; the inlined one-sentence labels above are
  sufficient for the re-test decision.
- **Why this is LOW ROI until Phase M lands.** Without the OWN
  harness existing, the measurement is non-executable; there is
  no good substitute (Arena = different harness; manual
  cross-fork sessions = still external harness underneath).
- **Prior-art enforcement (DPC ADR-015, added 2026-05-13):**
  Same constraint as I-7 above. Until I-8 re-test succeeds on
  FA's own harness, no autonomous self-improvement loop (skill
  evolution, config mutation, ADR-amendment bots) should ship.
  Empirical evidence: DPC removed 400 LOC + 7 tools of
  self-modification infrastructure after 0 of ~40 proposals
  passed their (insufficient) fitness bar; see
  [`research/dpc-messenger-inspiration-2026-05.md`](./research/dpc-messenger-inspiration-2026-05.md)
  §0 R-5 + ADR-015 citation in §2 Pattern 13.

## I-9 — Convert `knowledge/prompts/repo-audit-playbook.md` into a loadable SKILL

- **Status:** **closed by PR A' (2026-05-26)** — path (b) realised.
  `knowledge/skills/` directory established with self-declaring
  [`README.md`](./skills/README.md) (scope, template,
  skill-vs-prompt-vs-rule distinction) per
  [`borrow-roadmap-2026-05.md` §R-24](./research/borrow-roadmap-2026-05.md#r-24--filesystem-canonical-skill-store--safe-community-import);
  `repo-audit-playbook.md` migrated via `git mv` to
  [`knowledge/skills/repo-audit/SKILL.md`](./skills/repo-audit/SKILL.md)
  (history preserved); frontmatter normalised to the skill
  schema (`status: active`, `triggers:`, `last-reviewed:`,
  `relocated_from:`); `knowledge/llms.txt` §BY-DEMAND-INDEX
  gained the new `### Skills (knowledge/skills/)` subsection
  with row per skill (same shape as the existing `### Prompts`
  rows). Naming uses `knowledge/skills/` (not `playbooks/` as
  the path (b) wording originally said) per R-24's
  filesystem-canon naming + four-place commit on disk
  ([`project-overview.md`:70](./project-overview.md), the
  `R-22` entry in this file, `docs/glossary.md` §Self-evolving /
  §Skill); the inconsistency between R-24 + I-9 wording is
  resolved by R-24 winning. PR A' also externalised
  AGENTS.md §PR Intent Classification to
  [`knowledge/skills/pr-creation/SKILL.md`](./skills/pr-creation/SKILL.md)
  as the **second** skill in the directory, so the convention
  has two consumers from day one (subtraction-check passes for
  the directory: two non-trivial loaders, not one).
- **Path (a) `.agents/skills/<name>/SKILL.md`** (Agent auto-load
  convention) **deferred** per minimalism-first: a second
  filesystem surface for the same content is not justified
  while only two skills exist. Re-evaluate once ≥ 3 skills
  exist or once a session demonstrates the auto-load
  surface produces materially better behaviour than the
  AGENTS.md PR Checklist rule #12 load-directive (the OSS-LLM
  audience already loads via the explicit rule).

## M-1 — Inner-loop scaffolding / HookRegistry runtime

- **Status:** **closed by PR #24** (2026-05-20). Runtime now lives at
  `src/fa/inner_loop/` with the full ADR-7 §1–§10 + ADR-8 contract:
  JSON-Schema validation on every dispatch (§5), modify→re-validate +
  sandbox replay on every `Decision.modify` (§8), `SandboxHook` gating
  `fs_read_file` / `fs_write_file` paths in addition to `fs_run_bash`,
  `events.jsonl` with `ts` + `run_id` per §7 schema, `hook_decision`
  rows persisted through `HookRegistry` event-sink, `RuntimeLimits`
  for `max_iterations` (default 6) and `bash_timeout_seconds`
  (default 30) loaded from `~/.fa/config.yaml` per §Amendment
  2026-05-20 rule 1 «never code constants». Smoke CLI:
  `fa inner-loop-smoke --workspace . --input README.md` — 338 tests
  passing. Unblocks Wave-2 R-Ns.
- **Prior status (kept for audit trail):** deferred from Wave-1
  docs-only PRs (added 2026-05-20). Doc contract was frozen across
  three ADRs — runtime materialisation was gated by this milestone.
- **Idea:** Stand up the minimal `src/fa/inner_loop/` package that
  materialises the deliberately-minimal slate locked in
  [ADR-7 §2 / §8](./adr/ADR-7-inner-loop-tool-registry.md) and the
  HookRegistry contract in
  [ADR-8](./adr/ADR-8-hook-registry.md). Expected surface:
  - `registry.py` — `ToolRegistry` + first three tool subclasses
    (`read_file`, `write_file`, `run_bash`) with allow-list per
    [ADR-6](./adr/ADR-6-tool-sandbox-allow-list.md).
  - `loop.py` — single perceive–select–execute–observe loop with
    `max_iterations=6` (ADR-7 §Amendment 2026-05-20 retry-budget
    invariant) and the `T=1.0` intra-role retry rule.
  - `hooks/` — `HookRegistry` per ADR-8 (five lifecycle points;
    `GuardMiddleware` + `ObserverMiddleware`; first-deny short-
    circuit; family-disjoint rule enforced at `register()`).
  - `hooks/sandbox.py`, `hooks/approval.py`, `hooks/audit.py` —
    the three concrete hook subclasses from ADR-7 §8 wired to the
    HookRegistry surface.
  - Wire `fa.sandbox.bash_gate`, `fa.config.load_capabilities`,
    `fa.orchestration.pause`, and `fa.verifier.verify_action` as
    `GuardMiddleware` / post-call `ObserverMiddleware` so the
    Wave-0+Wave-1 standalone modules stop being inert.
  - First-call entry point: a CLI command that exercises a single
    `read_file → write_file → run_bash` trio through the registry +
    hook chain end-to-end.
  - Folds in the read-modify-write locking deferred from Wave-0
    (record-gotcha / record-discovery) — `HookRegistry` is the
    single-writer serialisation seat per
    [`src/fa/tools/__init__.py`](../src/fa/tools/__init__.py)
    docstring.
- **Blocked-on:**
  - Wave-0 PR #18 + Wave-1 PR #19 + Wave-1 PR #20 merged to `main`
    (ADR-6 / ADR-7 / ADR-8 amendments must be in `main` first so
    M-1 can cite them as canonical contracts).
  - Confirmation that no further Wave-1 docs-only amendments are
    pending against ADR-7 / ADR-8 (small risk surface; defaults to
    «not pending» after this PR).
- **Unblock-trigger:** all three Wave-0/Wave-1 PRs merged AND the
  matching session opens a fresh branch for `src/fa/inner_loop/`.
  No earlier start — landing M-1 before the doc PRs merge guarantees
  rework on every ADR amendment surfaced by Agent Review.
- **First concrete step once unblocked:** create
  `src/fa/inner_loop/__init__.py` + `registry.py` skeleton; port
  the ADR-7 §2 `ToolSpec` / `ToolResult` dataclasses verbatim from
  the ADR text; write one happy-path test that calls a single
  `EchoTool` through the registry without hooks; add a failing
  test for «register two `LLM_USING` hooks in the same family»
  to lock in the ADR-8 family-disjoint rule.
- **References that point here (12 sites across 6 files, added in
  Wave-0+Wave-1 PRs):**
  - [`knowledge/adr/ADR-8-hook-registry.md`](./adr/ADR-8-hook-registry.md)
    lines 35, 107, 240, 307, 358.
  - [`knowledge/adr/DIGEST.md`](./adr/DIGEST.md) line 244.
  - [`knowledge/adr/ADR-6-tool-sandbox-allow-list.md`](./adr/ADR-6-tool-sandbox-allow-list.md)
    line 496.
  - [`knowledge/trace/exploration_log.md`](./trace/exploration_log.md)
    lines 362, 385, 402, 427.
  - [`HANDOFF.md`](../worklogs/HANDOFF.md) lines 164, 176.
  - [`src/fa/tools/__init__.py`](../src/fa/tools/__init__.py)
    docstring (single-writer contract deferral).

## M-2 — Wave-2 LoopGuard + FailureClassifier + attempt_history

- **Status:** **closed by PR-2 stacking on PR #24** (2026-05-20).
  Three of the Wave-2 R-Ns from
  [`research/borrow-roadmap-2026-05.md`](./research/borrow-roadmap-2026-05.md)
  §3 landed as one stack on top of the M-1 substrate:
  - **R-2 LoopGuard** —
    [`src/fa/inner_loop/hooks/loop_guard.py`](../src/fa/inner_loop/hooks/loop_guard.py),
    a `GuardMiddleware` attached to `BEFORE_TOOL_EXEC` +
    `BETWEEN_ROUNDS`. Two detectors: identical-call repeat (same
    `(tool, params_hash)` ≥ N) and same-path thrash (same path,
    distinct params, ≥ N). Thresholds + window come from
    `RuntimeLimits.loop_guard_*` per ADR-7 §Amendment 2026-05-20 rule 1.
    Deny propagates through the same `BETWEEN_ROUNDS` catch that
    PauseGuard already uses (BUG-0001 fix in PR #24).
  - **R-3 FailureClassifier** —
    [`src/fa/inner_loop/recovery/classify.py`](../src/fa/inner_loop/recovery/classify.py)
    (pure-Python deterministic function per AGENTS.md PR Checklist
    rule #10 q4) +
    [`src/fa/inner_loop/hooks/recovery_observers.py`](../src/fa/inner_loop/hooks/recovery_observers.py)
    `FailureClassifierObserver` emitting `kind="recovery_action"`
    rows to `events.jsonl`.
  - **R-6 attempt_history.json** —
    [`src/fa/inner_loop/recovery/attempt_history.py`](../src/fa/inner_loop/recovery/attempt_history.py)
    writer (per-run, `~/.fa/session-log/<run_id>/attempt_history.json`,
    sliding window + cap from `RuntimeLimits`) +
    [`knowledge/prompts/coder-recovery.md`](./prompts/coder-recovery.md)
    reader-prompt fragment. Cross-session aggregation deferred to
    Wave-3 (R-10 / R-12).
- **Why M-2 (not Wave-3) closes here:** R-22 PII walker, R-29 family-
  disjoint LLM-using rule, and R-5 DSV YAML contracts are tracked
  under their own roadmap items; R-29 was already satisfied by PR #24
  (registry-time rejection of co-family LLM hooks). R-2 + R-3 + R-6
  pair tightly (FailureClassifier feeds AttemptHistory which feeds
  LoopGuard's future thrash-on-error detector), so they ship together.
- **References:**
  - [`research/borrow-roadmap-2026-05.md`](./research/borrow-roadmap-2026-05.md)
    §R-2 / §R-3 / §R-6.
  - [`knowledge/adr/ADR-7-inner-loop-tool-registry.md`](./adr/ADR-7-inner-loop-tool-registry.md)
    §Amendment 2026-05-20 rule 1 (config-bounded retry caps).
  - [`knowledge/adr/ADR-8-hook-registry.md`](./adr/ADR-8-hook-registry.md)
    §3 (Guard short-circuit) — LoopGuard reuses the same deny path.

## M-3 — Wave-2 pre-tool BlockerMiddleware + DSV YAML contracts + QA constants

- **Status:** **closed by PR-3 stacking on PR #25** (2026-05-20).
  Three more Wave-2 R-Ns from
  [`research/borrow-roadmap-2026-05.md`](./research/borrow-roadmap-2026-05.md)
  §3 land on top of the M-2 stack:
  - **R-4 pre-tool blockers** —
    [`src/fa/inner_loop/hooks/blockers.py`](../src/fa/inner_loop/hooks/blockers.py)
    introduces `BlockerMiddleware` + three subclasses (`RateLimitBlocker`,
    `LockfileBlocker`, `AuthExpiredBlocker`). Each is a `GuardMiddleware`
    attached to both `BEFORE_TOOL_EXEC` (gate) and `AFTER_TOOL_EXEC`
    (observe). The base class wires the observe-on-AFTER + gate-on-BEFORE
    flow so every subclass is a ~10-line specialisation that overrides
    `_detect(ToolResult) -> bool`. Suppression windows + category live in
    `RuntimeLimits` per ADR-7 §Amendment 2026-05-20 rule 1: 30s rate-limit
    (Aperant `pause-handler.ts:30-80` prod-tuned default), 5s lockfile,
    0s auth-expired (observe-only; synthetic re-auth lands with T-2).
  - **R-5 DSV YAML contracts** — [`src/fa/verifier/__init__.py`](../src/fa/verifier/__init__.py)
    adds `load_contracts_from_dir(directory)` batch-loader. The smoke CLI
    seeds `VerifierObserver` from
    [`verifiers/*.yaml`](../verifiers/), which now ships canonical
    contracts for the three M-1 tools (`fs_read_file`, `fs_write_file`,
    `fs_run_bash`) plus the documentation-anchor `edit_file.yaml`.
    Contracts are keyed by in-file `target_action`, not filename.
    `required_trace_events` is empty in M-1 — tool bodies don't yet emit
    per-step trace events; T-2 lands observation-event projection.
  - **R-34 HookRegistry guard constants** —
    [`src/fa/inner_loop/runtime_limits.py`](../src/fa/inner_loop/runtime_limits.py)
    surfaces `qa_max_iterations` / `qa_max_consecutive_errors` /
    `qa_recurring_issue_threshold` as documented anchors (Aperant
    `qa-loop.ts` magic-validated defaults: 50 / 3 / 3). The QA orchestrator
    itself is DEFER per roadmap §2.9 — landing the constants now keeps
    the rule-1 contract (config-bounded, never code constants) honoured
    when a future R-N consumer wires them. Same commit fixes a latent
    loader gap: prior to PR-3 the YAML loader accepted the QA + R-4
    suppression keys (no «unknown key» warning) but silently discarded
    their values; the loader now wires both groups through `RuntimeLimits`
    so user config actually takes effect.
- **Why M-3 (not deferred) closes here:** R-4 blockers, R-5 DSV
  loader, and R-34 constants are all subtractions of LLM reasoning
  cost (R-4 + R-5) and pre-vendored documented anchors (R-34). They
  share the same shape — all three plug into the existing
  `HookRegistry` / `RuntimeLimits` / `VerifierObserver` surfaces
  without restructuring, so they ship together.
- **References:**
  - [`research/borrow-roadmap-2026-05.md`](./research/borrow-roadmap-2026-05.md)
    §R-4 / §R-5 / §R-34.
  - [`knowledge/adr/ADR-7-inner-loop-tool-registry.md`](./adr/ADR-7-inner-loop-tool-registry.md)
    §Amendment 2026-05-20 rule 1 (config-bounded retry caps) — all
    three blocker suppression windows + three QA constants live in
    `RuntimeLimits`.
  - [`knowledge/adr/ADR-8-hook-registry.md`](./adr/ADR-8-hook-registry.md)
    §1 (lifecycle points) — blockers reuse `BEFORE_TOOL_EXEC` +
    `AFTER_TOOL_EXEC` symmetrically.

## M-4 — T-2 LLM provider client implementation (driver per ADR-9)

- **Status:** closed 2026-05-22 — landed in T-2 implementation PR
  (`agent/1779480362-t2-llm-provider-client`). Seven modules under
  `src/fa/providers/` + `src/fa/observability/cost_table.py`,
  ~1080 LOC including docstrings, plus six offline-only test
  modules (55 tests) covering the contract surface listed below.
  All gates pass: ruff check, ruff format --check, mypy --strict,
  pytest -q (544 total), pre-commit run --all-files.
- **Why milestone, not idea:** ADR-9 has been merged
  (status = proposed, locked design), so the implementation is
  a planned PR with explicit shape, not an open research
  question. `M-2` and `M-3` are already closed (Wave-2 stack);
  `M-4` is the next free milestone slot.
- **Contract source:**
  [`knowledge/adr/ADR-9-llm-provider-client.md`](./adr/ADR-9-llm-provider-client.md)
  — Option D + α (per-role explicit provider chain with
  cooldown) + companion survey
  [`knowledge/research/provider-client-survey-2026-05.md`](./research/provider-client-survey-2026-05.md).
- **Scope (~380 LOC across 6 files + ~30 LOC pricing seed):**
  - `src/fa/providers/base.py` (~60 LOC) — `Provider` Protocol,
    `RequestInfo` / `ResponseInfo` dataclasses with `extras:
    dict[str, Any]` parking surface.
  - `src/fa/providers/chain.py` (~100 LOC) — `ChainConfig` +
    `ChainConfig.validate()` (config-load enforcement per §1)
    + ordered chain dispatch + cooldown bookkeeping (§3) +
    adaptive `Retry-After` floor.
  - `src/fa/providers/openai_compat.py` (~80 LOC) — shared
    adapter posting to `/chat/completions`; covers OpenRouter,
    Fireworks, NVIDIA Build, Groq, GitHub Models, Modal,
    Together AI, etc. via 1-row entry in `PROVIDERS` dict.
  - `src/fa/providers/anthropic.py` (~70 LOC) — `/v1/messages`
    adapter (system-as-separate-field + tool-use content
    blocks); normalizes into canonical `ResponseInfo`.
  - `src/fa/providers/registry.py` (~30 LOC) — `PROVIDERS`
    dict + factory; one row per supported provider.
  - `src/fa/providers/errors.py` (~40 LOC) — six typed errors
    (`ConfigurationError` / `ReservedProviderError` /
    `ProviderTransientError` / `ProviderAuthError` /
    `ProviderRequestShapeError` / `ProviderChainExhaustedError`).
  - `src/fa/observability/cost_table.py` (~30 LOC) — seed
    pricing-lookup table; `cost_table.lookup(provider, family,
    slug) -> CostPerMillion | None`; misses return `None` and
    emit a `cost_estimate_missing` warning via the Tier-1
    `llm_call` row.
- **Tests:** offline-only (no real provider calls); fakes/stubs
  per ADR-7 §10 retry-test pattern. Covers: cooldown insert/
  expire/`Retry-After`-adaptive floor; 401/403 continue-chain
  vs 400/422 fail-fast split; chain-exhaustion → typed
  `ProviderChainExhaustedError`; response normalization for
  both adapter categories; `logical_call_id` propagation
  across the three observability tiers; config-load validator
  rejecting empty chain / empty `api_key_env` / unknown
  provider / reserved provider name / bad `base_url` scheme.
- **Q-N amendment items** (deferred from ADR-9 §9; each
  becomes its own future BACKLOG row when a re-evaluation
  trigger fires per ADR-9 §10):
  - Q-1 persistent cooldown across sessions.
  - Q-2 per-entry `transport_retries` + `tiktoken` pre-call estimate.
  - Q-3 named chains / round-robin support.
  - Q-4 provider-wide cooldown when N≥2 slugs cool concurrently.
  - Q-5 Anthropic prompt-cache preservation on fallback.
  - Q-6 reasoning-model parameter translation table
    (OpenAI o-series `max_completion_tokens`, Anthropic
    `thinking: {budget_tokens}`).
  - Q-7 per-role `timeout_seconds` override beyond the
    per-chain-entry default.
- **References:**
  - [`knowledge/adr/ADR-9-llm-provider-client.md`](./adr/ADR-9-llm-provider-client.md)
    §1–§10 (Decision, chain shape, runtime semantics, cooldown,
    observability, adapter split, reserved-key semantics,
    family-disjoint preservation, out-of-scope, future-
    amendment slots, re-evaluation triggers).
  - [`knowledge/adr/DIGEST.md` ADR-9 row](./adr/DIGEST.md) —
    one-paragraph reading-cheat-sheet view.
  - [`knowledge/trace/exploration_log.md` Q-13](./trace/exploration_log.md) —
    Options A/B1/B2/B3/C rejected with Reason + Lesson;
    Option D + α chosen 2026-05-22.
  - [`HANDOFF.md` §Current state ADR list](../worklogs/HANDOFF.md) —
    ADR-9 bullet with `M-4` cross-reference.

## M-5 — T-4 `~/.fa/models.yaml` loader (closes M3 of release roadmap)

- **Status:** closed 2026-05-22 — landed in T-4 implementation PR
  (`agent/1779515293-t4-models-yaml-loader`). One module
  `src/fa/providers/config.py` (~150 LOC) + 23 new offline tests
  in `tests/test_providers_config.py`; 584 total pytest pass.
  All gates pass: ruff check, ruff format --check,
  mypy --strict, pre-commit run --all-files.
- **Why milestone, not idea:** ADR-9 §1 schema is locked
  (proposed 2026-05-22 + T-2 driver landed in M-4); the loader
  is a planned PR with explicit shape, not an open research
  question. `M-4` is closed (T-2 driver landed), so `M-5` is
  the next free milestone slot. T-4 corresponds to the «M3 —
  T-2 + T-4: LLM provider client + config loader» entry in
  the release roadmap synthesis (the roadmap's milestone
  numbers diverge from this BACKLOG's M-N numbering; the
  roadmap groups T-2 and T-4 as one milestone, while this
  BACKLOG closes them as two adjacent milestones since the
  T-2 PR landed independently).
- **Contract source:**
  [`knowledge/adr/ADR-9-llm-provider-client.md`](./adr/ADR-9-llm-provider-client.md)
  §1 (chain configuration schema) + §7 (family-disjoint
  preservation across the chain). Cross-role family-disjoint
  rule from
  [`knowledge/adr/ADR-2-llm-tiering.md`](./adr/ADR-2-llm-tiering.md)
  §Amendment 2026-05-20 rule 1.
- **Scope (~150 LOC across 1 file):**
  - `src/fa/providers/config.py` — `ModelsConfig` frozen
    dataclass + `load_models_config(text, *, env=None)` +
    `load_models_config_from_path(path=DEFAULT_MODELS_YAML_PATH,
    *, env=None)` + `DEFAULT_MODELS_YAML_PATH` constant.
  - Loader composes existing primitives: `yaml.safe_load`
    (new runtime dep `pyyaml>=6.0`) →
    `chain_from_mapping(role, raw)` (in `src/fa/providers/chain.py`,
    landed M-4) → `chain_config.validate(env)` (warning
    accumulator) → `check_eval_disjoint(...)` (in
    `src/fa/roles.py`, landed PR-4) when planner / coder /
    eval are all declared.
  - Error model: `ConfigurationError` for malformed structure,
    null role value, non-mapping role config, and all chain-
    validator failures; `EvalFamilyConflictError` for family-
    disjoint violations. Both fail-fast at load time.
- **New runtime dependency: `pyyaml>=6.0`.** Justification: the
  hand-rolled `src/fa/_yaml_subset.py` parser (consumed by
  `fa.config` capability flags + `fa.verifier.verify_action`)
  covers inline-comment stripping only and cannot safely round-
  trip the §1 nested lists-of-mappings + `extra_headers` map
  schema. The `verifier/verify_action.py` parser comment
  already anticipated this transition: «adding `pyyaml` to
  `pyproject.toml` for a Wave-0 standalone module is overkill;
  the v0.2 HookRegistry PR (R-1) lands the broader YAML loader
  and this function will switch to it then». T-4 is the
  natural seat for the broader loader. The dep is added with
  a strict `yaml.safe_load` contract (no `yaml.load` tag
  execution); the pyproject.toml comment pins this discipline.
  `types-PyYAML>=6.0` is also added to the `dev` extras for
  mypy --strict type coverage.
- **Tests (23 offline-only, no real provider calls):**
  - Happy-path parse — ADR-9 §1 three-role example verbatim
    (coder + planner + eval; verifies model / family / chain
    surfaces); preservation of all four optional chain-entry
    fields (cooldown_seconds, transport_retries, timeout_seconds,
    extra_headers).
  - Empty / null / scalar root — empty text, whitespace-only,
    `~` (YAML null), list root rejected, scalar root rejected.
  - Malformed role entries — null role value, scalar role value,
    list role value all rejected with named role in error.
  - Chain-level validator propagation — empty chain → error,
    missing `api_key_env` env var → error, unknown provider →
    error, slug-family heuristic mismatch → warning accumulated
    via `ModelsConfig.warnings` (not raised).
  - Family-disjoint enforcement — eval=planner rejected,
    eval=coder rejected, planner=coder OK (ADR-2 §Decision
    allows shared coder-tier model), missing eval → check
    skipped, missing planner → check skipped, four-role
    (planner+coder+eval+debug) shape accepted with check
    constrained to the planner/coder/eval triad.
  - Path-based variant — reads from `tmp_path`, missing file
    returns empty `ModelsConfig` (matches `fa.config` deny-by-
    default policy), default path resolves under `Path.home()`.
- **Q-N amendment items** (none triggered): no contract drift
  surfaced during implementation; T-4 implements §1 verbatim.
- **References:**
  - [`knowledge/adr/ADR-9-llm-provider-client.md`](./adr/ADR-9-llm-provider-client.md)
    §1, §7.
  - [`knowledge/adr/ADR-2-llm-tiering.md`](./adr/ADR-2-llm-tiering.md)
    §Amendment 2026-05-20 rule 1 (eval-role family-disjoint).
  - [`knowledge/adr/DIGEST.md` ADR-9 row](./adr/DIGEST.md) —
    Amendments bullet extended with T-4 landing date.
  - [`HANDOFF.md` §Current state ADR list](../worklogs/HANDOFF.md) —
    ADR-9 bullet with `M-5` T-4 loader sub-clause.

## M-6 — PR B — `pr_intent` classifier module + `prepare-commit-msg` / `commit-msg` git hooks

- **Status:** **closed by PR B (2026-05-27).** Landed
  [`src/fa/hygiene/pr_intent.py`](../src/fa/hygiene/pr_intent.py)
  (classifier + validator + citation resolver + CLI),
  [`src/fa/hygiene/hooks/`](../src/fa/hygiene/hooks/)
  (bash wrappers + symlink installer), and
  [`tests/test_pr_intent_snapshot.py`](../tests/test_pr_intent_snapshot.py)
  (49 cases including the dual-located-rule guard pinning the
  hook constants to the skill's §Output format fenced blocks).
  Sanity-checked: intentionally adding a `SPURIOUS` enum value
  to the skill's §Output format fails the snapshot test; the
  hook's bash wrappers invoke `python -m fa.hygiene
  {prepare|validate}` against the staged-diff snapshot.
- **Why milestone, not idea:** the contract is locked — the
  [`pr-creation` skill](./skills/pr-creation/SKILL.md) §Reference
  (Level-1 INTENT table + Level-2 CLASS table + per-intent
  INVARIANT-content table), §Output format (header-line shape),
  and §What the hook validates (six explicit checks) collectively
  pin the hook's external behaviour. Implementation is a planned
  PR with explicit shape, not an open research question.
- **Contract source:** [`knowledge/skills/pr-creation/SKILL.md`](./skills/pr-creation/SKILL.md)
  §Reference + §Output format + §What the hook validates. The
  skill is the **single source of truth**; a snapshot test in PR
  B pins the hook's regex to §Output format so the two views
  cannot drift (the snapshot is the only legitimate consumer of
  the skill's section anchors and fails CI on any anchor or
  shape change). Companion declarative principle:
  [`project-overview.md` §1.2.5 anti-shallow-fix gate](./project-overview.md#125--compliance-by-construction-failure-observable).
  Anti-pattern back-stop: [`AP-003-shallow-fix-no-mechanism.md`](./anti-patterns/AP-003-shallow-fix-no-mechanism.md)
  (synthetic worked-history is a placeholder until the hook
  captures the first real escalation — that replacement is part
  of M-6's success criterion).
- **Scope (estimated ~250 LOC across 4 files + 1 snapshot file):**
  - `src/fa/hygiene/__init__.py` (~10 LOC) — package marker +
    public surface re-exports.
  - `src/fa/hygiene/pr_intent.py` (~150 LOC) — pure-Python
    deterministic functions:
    `classify_intent(staged_paths: list[StagedPath]) -> Intent`
    over `git diff --cached --name-status` (closed enum
    `RESEARCH / ADR-RULE / IMPLEMENT / FIX / CHORE`;
    cross-category resolution `ADR-RULE > IMPLEMENT > FIX >
    RESEARCH > CHORE` per skill §Reference);
    `derive_required_fields(intent: Intent) -> list[FieldSpec]`
    (per-intent placeholders for `prepare-commit-msg`);
    `validate_commit_msg(text: str, intent: Intent) -> list[Violation]`
    (all six checks from skill §What the hook validates, single
    pass, no short-circuit); `resolve_citation(
    citation: str, repo_root: Path, staged: list[StagedPath]) -> bool`
    (file-exists + line-in-bounds against staged tree or HEAD).
  - `src/fa/hygiene/hooks/prepare-commit-msg` (~30 LOC bash
    wrapper) — invokes `python -m fa.hygiene.pr_intent prepare
    <commit-msg-file>`; pre-populates the buffer with the
    mechanically-derived `INTENT:` line plus `<fill me>`
    placeholders for every required field per the intent's row.
  - `src/fa/hygiene/hooks/commit-msg` (~30 LOC bash wrapper) —
    invokes `python -m fa.hygiene.pr_intent validate
    <commit-msg-file>`; validates and prints all violations in
    one pass; non-zero exit blocks the commit.
  - `tests/test_pr_intent_snapshot.py` — snapshot test pinning
    the hook's regex to the skill's §Output format section
    (reads `knowledge/skills/pr-creation/SKILL.md` at test time,
    extracts the fenced code-block under §Output format, asserts
    structural identity with the regex's expected shape).
    Auxiliary tests cover the closed-enum classifier branches,
    cross-category resolution, citation-resolution edge cases
    (file-not-staged, line-out-of-bounds, `n/a (reason)`
    acceptance), and the tautology check
    (`DEGREE-OF-FREEDOM CLOSED:` and `DETERMINISTIC MECHANISM:`
    not string-identical modulo whitespace).
  - Installation: hooks landed under `src/fa/hygiene/hooks/`
    with a `make install-hooks` / `fa hygiene install-hooks`
    one-liner that symlinks them into `.git/hooks/`. Deferred
    decision: `pre-commit` framework integration vs. bare
    Git-hook symlink — pick whichever matches the rest of the
    repo's existing hook discipline at PR-B time.
- **Tests:** offline / pure-Python; no real git invocations
  (fixtures construct staged-path lists directly). The snapshot
  test is the most important — it fails CI the moment the
  skill's §Output format drifts from the hook's regex, which is
  the dual-located-rule guard recommended throughout the PR-A /
  PR-A' exploration_log (Q-15 + Amendments).
- **Q-N amendment items** (deferred from skill §What the hook
  validates; each becomes its own future BACKLOG row when a re-
  evaluation trigger fires):
  - Citation-resolution against `HEAD~` (not just staged tree)
    for FIX PRs that cite a removed line.
  - Multi-commit PRs — apply validation only to the first
    commit on the branch (header lines are PR-level), or to all
    commits with the trailer? Skill §AI-Session trailer
    currently says "per-commit".
  - LLM-judge fallback for `n/a (reason)` text quality (e.g.
    reject "n/a (just because)"). Deferred per skill
    §Escalation philosophy: «cheap-scope guard is cheap to
    write but expensive to dress up convincingly» — the human
    reviewer catches gaming faster than an LLM judge can.
- **References:**
  - [`knowledge/skills/pr-creation/SKILL.md`](./skills/pr-creation/SKILL.md)
    — single source of truth.
  - [`knowledge/trace/exploration_log.md` Q-15](./trace/exploration_log.md)
    (initial PR A decision rationale; Rejected option (c)
    «PR-description-only enforcement» explains why
    `prepare-commit-msg` is mandatory rather than optional) +
    Q-15 Amendment 2026-05-26 (PR A' externalisation: hook now
    reads the skill, not AGENTS.md) + Q-15 Amendment 2026-05-26
    (PR A' expansion: contract sources widened to skill
    §Reference + §Output format + §What the hook validates).
  - [`knowledge/anti-patterns/AP-003-shallow-fix-no-mechanism.md`](./anti-patterns/AP-003-shallow-fix-no-mechanism.md)
    — synthetic worked-history; placeholder until PR B's hook
    captures the first real escalation.
  - [`HANDOFF.md`](../worklogs/HANDOFF.md) §Process / rule changes
    2026-05-25 (PR A) and 2026-05-26 (PR A') — historical scoping
    context.
- **Blocked-on:** nothing — PR A landed (rule supersession);
  PR A' merging is not a strict gate (the skill is the contract
  source whether PR A' is merged to `main` or still on its
  branch), but practically PR A' should land first so the
  snapshot test's section-anchor reads remain stable.

## M-7 — PR C — `IntentGuard` `GuardMiddleware` on `BEFORE_TOOL_EXEC`

- **Status:** **closed by PR C (2026-05-27).** Landed
  [`src/fa/inner_loop/hooks/intent_guard.py`](../src/fa/inner_loop/hooks/intent_guard.py)
  (`IntentGuard(GuardMiddleware)` on `BEFORE_TOOL_EXEC`; re-runs
  `fa.hygiene.pr_intent.classify_intent` over the staged-diff
  snapshot projected with the about-to-mutate path; reuses
  `fa.hygiene.pr_intent.validate_commit_msg` against the
  session's PR-description draft; respects skill §D-5 user-typed
  INTENT override) and
  [`tests/test_intent_guard.py`](../tests/test_intent_guard.py)
  (18 offline test cases — non-mutating allow, no-draft allow,
  shape-mismatch deny, anti-shallow-fix deny on FIX without DOF
  / MECHANISM, git-add / git-commit triggers, skill §D-5
  override, path-projection for IMPLEMENT / RESEARCH buckets,
  identity-test for ADR-10 I-1 single-source-of-truth, deny
  reason echoes hook wording). **Both former follow-ups are now
  closed:** the `prepare-pr` producer shipped in PR #24
  (`pr_prepare`, see §Q-N below) and `IntentGuard` is wired into
  the `fa run` bootstrap (`cli.py` `_cmd_run`, landed in PR #23
  final-review). **Scope expanded post-#24 (commit 78ced94):**
  `IntentGuard` now also gates `fs_run_bash` via a dedicated
  AST analyzer ([`bash_intent.py`](../src/fa/inner_loop/bash_intent.py),
  READ_ONLY / VERIFY_ONLY / INDEX_WRITE / REPO_WRITE /
  OPAQUE_EXEC) and trusts only current-session drafts via the
  [`PrDraftStore`](../src/fa/inner_loop/pr_draft.py) (stale /
  externally-fabricated drafts rejected) — closing the remaining
  `fs_run_bash` bypass of the draft-first contract.
- **Why milestone, not idea:** the `HookRegistry` substrate is
  landed (M-1 closed by PR #24; verified by the session-start
  audit at [`src/fa/inner_loop/hooks/base.py`](../src/fa/inner_loop/hooks/base.py)
  per HANDOFF.md §Process / rule changes 2026-05-25 last
  paragraph); PR C is a `~10-line specialisation` of
  `GuardMiddleware` that reuses M-6's classifier module. Shape
  is locked, not exploratory.
- **Contract source:** [`knowledge/adr/ADR-8-hook-registry.md`](./adr/ADR-8-hook-registry.md)
  §3 (`GuardMiddleware` may deny / modify; first-deny short-
  circuit; `BEFORE_TOOL_EXEC` lifecycle point) +
  [`knowledge/skills/pr-creation/SKILL.md`](./skills/pr-creation/SKILL.md)
  §Reference (classifier contract; the harness-side guard
  reuses the SAME classifier function as the git hook so the
  two enforcement seats cannot drift).
- **Scope (estimated ~80 LOC across 2 files):**
  - `src/fa/inner_loop/hooks/intent_guard.py` (~50 LOC) —
    `IntentGuard(GuardMiddleware)` attached to
    `BEFORE_TOOL_EXEC`. On tool calls that mutate the staged
    tree (`fs_write_file`, `edit_file` shapes,
    `git add` / `git commit` via `fs_run_bash`), re-runs
    `fa.hygiene.pr_intent.classify_intent` over the staged-diff
    snapshot the call is about to produce; if the resulting
    intent or required-field shape would violate the skill's
    §Reference table (e.g. `INTENT: FIX` without
    `DETERMINISTIC MECHANISM:` populated upstream in the
    session's working PR description), emits a `Decision.deny`
    with the violation message echoing the git hook's wording
    (so agent error-recovery is identical whether the rule
    fires at hook time or harness time).
  - `tests/test_intent_guard.py` (~30 LOC) — fixtures construct
    a `ToolPayload` with a synthetic staged-diff and assert
    deny on contract violation, allow on conformant payloads.
    Reuses the same fixture catalogue as PR B's snapshot test.
- **Why dual enforcement (hook + middleware):** the git hook
  catches the rule at commit time (post-edit, pre-commit); the
  middleware catches it at tool-call time (pre-edit) — the
  earlier seat is the cheaper one per [`AP-001` §Why-wrong-shape-dominates](./anti-patterns/AP-001-spec-bypassing-workaround.md#why-the-wrong-shape-dominates)
  «action-count drift dominates rule-count drift». Both seats
  share the same classifier function, satisfying ADR-10 I-1
  single-source-of-truth (one validator, two consumers).
- **Tests:** offline / pure-Python; uses fake `ToolPayload`
  builders. No real git or LLM invocations.
- **Q-N amendment items:**
  - Should the middleware also fire on `BEFORE_LLM_CALL` to
    pre-inject the required-fields placeholder into the next
    LLM message? Defer until session-trace data shows the
    middleware catches violations the hook would have missed.
  - Synthetic-PR-description state tracking — the middleware
    needs visibility into the current session's draft PR
    description to validate field-presence. Decision: read from
    a known location under `~/.fa/session-log/<run_id>/pr_draft.md`
    populated by the agent itself; agent populates it on
    session start via a new `prepare-pr` tool or sub-agent.
    **Closed by PR E (2026-05-28):** `pr_prepare` tool ships in
    [`src/fa/inner_loop/tools/prepare_pr.py`](../src/fa/inner_loop/tools/prepare_pr.py)
    and is registered by `_cmd_run` alongside the baseline
    filesystem tools; closure-bound to the same `draft_path` the
    `IntentGuard` reads. Single-source-of-truth (ADR-10 I-1)
    maintained: the tool re-runs `validate_commit_msg` on the
    rendered draft so any contract drift surfaces as a tool-level
    failure rather than a corrupt-draft leak.
- **References:**
  - [`knowledge/adr/ADR-7-inner-loop-tool-registry.md`](./adr/ADR-7-inner-loop-tool-registry.md)
    §8 (hook chain).
  - [`knowledge/adr/ADR-8-hook-registry.md`](./adr/ADR-8-hook-registry.md)
    §3 (`GuardMiddleware` contract).
  - [`knowledge/skills/pr-creation/SKILL.md`](./skills/pr-creation/SKILL.md)
    §Reference + §What the hook validates.
  - [`knowledge/trace/exploration_log.md` Q-15 §Coupling](./trace/exploration_log.md)
    — explicit cross-link to Q-7 / Q-8 (HookRegistry seat) +
    AP-001 (action-count rationale).
  - [`HANDOFF.md`](../worklogs/HANDOFF.md) §Process / rule changes
    2026-05-25 last paragraph — feasibility verified by the
    session-start audit of `src/fa/inner_loop/hooks/base.py`.
- **Blocked-on:** M-6 (PR B) — closed by PR #20; `IntentGuard` imports
  `fa.hygiene.pr_intent.classify_intent`. Both PR B and PR C are now
  closed (landed 2026-05-27).

## M-8 — PR D — LLM-driven coder loop (`drive_session`) + `fa run` CLI + `UrllibTransport`

- **Status:** **closed by PR #23 (PR D, 2026-05-28).** Landed
  `coder_loop.drive_session`, `prompt.py` (A-bucket residue),
  `providers/transport.UrllibTransport`, and the `fa run --task`
  CLI subcommand. The PR #23 final-review pass additionally fixed
  three terminal-path bugs (run_session batch truncation breaking
  the OpenAI tool-call pairing protocol, `KeyboardInterrupt` not
  mapping to a typed `SessionOutcome`, duplicate `User-Agent` /
  missing defensive `Content-Type` in the transport), resolved a
  pre-existing Python-3.13 sandbox symlink-loop containment bug,
  and wired `IntentGuard` into the `fa run` bootstrap. Remaining
  follow-up is the first live `fa run --task` smoke against a real
  provider (HANDOFF §Next #1).
- **Why milestone, not idea:** the M-3 ProviderChain dispatcher
  (PR #18, 2026-05-22) and the M-1 inner-loop `run_session`
  (PR #24, 2026-05-18) both landed, but no code bridged
  `provider_chain.request(...)` → `run_session(calls, ...)`. The
  release-roadmap-post-m2 §3 «UC1 first usable demo» pillar can
  only be measured after this bridge exists; until then every
  «agent solves task X» claim is hypothetical because the harness
  has no way to receive a tool-call from an LLM.
- **Contract source:** the FA-ABC synthesis deep-dive
  [`fa-abc-synthesis-deep-dive-2026-05`](./research/fa-abc-synthesis-deep-dive-2026-05.md)
  §3 (A-bucket residue, I-2 non-LLM determinism, I-4 typed loop-
  state ownership, I-5 deterministic post-LLM filter) +
  [`ADR-9` §2 step-by-step](./adr/ADR-9-llm-provider-client.md)
  (per-call lifecycle) + [`ADR-7` §1](./adr/ADR-7-inner-loop-tool-registry.md)
  (`ToolSpec` / `ToolCall` / `ToolResult` contract that the
  driver projects into / out of canonical OpenAI function-tool
  wire shape).
- **Scope (~400 LOC source + ~470 LOC tests):**
  - [`src/fa/inner_loop/coder_loop.py`](../src/fa/inner_loop/coder_loop.py)
    (~200 LOC) — `drive_session(task, *, provider_chain,
    registry, hooks, state, …) -> SessionOutcome`. Per-turn
    loop: `BEFORE_LLM_CALL` → `RequestInfo` → `provider_chain
    .request(...)` → `AFTER_LLM_CALL` → parse `tool_calls` →
    `run_session(...)` → collect results → feed back as
    tool-role observations. Returns `SessionOutcome` (exit_code
    0/1/2 + stop_reason + turns + final_text + tool_results)
    rather than raising on terminal states; the determinism
    guard `_build_tool_calls()` produces a synthetic
    `__invalid__` call for malformed JSON args so registry
    validation surfaces the canonical error row (deep-dive §3
    I-5).
  - [`src/fa/inner_loop/prompt.py`](../src/fa/inner_loop/prompt.py)
    (~80 LOC) — `CODER_SYSTEM_PROMPT` constant +
    `render_tool_specs(specs)` projects `ToolSpec` tuple to
    OpenAI function-tool wire shape +
    `build_system_message(extra="")` deterministic composer
    (A-bucket residue per deep-dive §3 I-2).
  - [`src/fa/providers/transport.py`](../src/fa/providers/transport.py)
    (~110 LOC) — `UrllibTransport` stdlib `Transport` impl
    using `urllib.request`. No new third-party dep.
  - [`src/fa/cli.py`](../src/fa/cli.py) (+~120 LOC) —
    `fa run --task <task> [--role coder] [--config
    ~/.fa/models.yaml] [--workspace .] [--max-turns 16]
    [--run-id <id>]` subcommand. Builds registry + hooks
    (Sandbox, LoopGuard, blockers, AuditHook, CostGuardian,
    optional VerifierObserver) + provider chain via
    `build_provider` factory; exit codes mirror
    `SessionOutcome.exit_code`.
- **Tests (~470 LOC across 4 files):**
  - [`tests/test_coder_loop.py`](../tests/test_coder_loop.py)
    — `FakeProvider` fixture; 11 cases covering happy stop,
    tool-call dispatch, iteration cap, `ProviderChainExhaustedError`,
    `ProviderRequestShapeError`, abnormal `finish_reason`,
    tool-spec rendering into request body, malformed JSON args,
    audit-row emission, `DEFAULT_MAX_TURNS` snapshot, `state.log`
    enforcement.
  - [`tests/test_prompt.py`](../tests/test_prompt.py) — 7
    cases pinning the A-bucket determinism property.
  - [`tests/test_transport.py`](../tests/test_transport.py) —
    11 cases with monkeypatched `urlopen`; pure helpers
    (`_parse_retry_after`, `_decode_body`) covered against
    edge cases including the «non-object JSON returns empty
    body» branch.
  - [`tests/test_cli.py`](../tests/test_cli.py) — 4 new
    cases: `fa run` clean stop, role-missing exits 2,
    events.jsonl emission, turn-cap exits 1.
- **Out of scope (parking lot):**
  - `IntentGuard` registration in `fa run` bootstrap — folds
    into HANDOFF §Next #1 follow-up; PR C (M-7) merged
    2026-05-27, so the dependency is satisfied and the
    follow-up is unblocked.
  - `prepare-pr` tool that populates `pr_draft.md` (M-7 §Q-N).
  - `fa init` command for `~/.fa/models.yaml` template
    generation (deferred per user lock 2026-05-27 — `--config
    <path>` covers the explicit-path case).
  - Streaming response interfaces (R-23 forbids streaming on
    parent ↔ loop interface).
- **Q-N amendment items:**
  - Default `temperature=0.0` for v0.1 determinism; if a real
    workload surfaces «coder needs creativity», promote to a
    `--temperature` CLI flag.
  - `LearningObserver` is not registered by `fa run` in PR D
    (the smoke command registers it with a pinned clock for
    byte-stable artifacts; the LLM path needs live timestamps
    + workspace-agnostic defaults). Reconsider when
    cross-session memory is wired (Pillar-3 follow-up).
- **References:**
  - [`fa-abc-synthesis-deep-dive`](./research/fa-abc-synthesis-deep-dive-2026-05.md)
    §3 (I-2 / I-4 / I-5).
  - [`ADR-9`](./adr/ADR-9-llm-provider-client.md) §2 (runtime
    semantics) + §3 (cooldown) + §5 (adapter pattern).
  - [`ADR-8`](./adr/ADR-8-hook-registry.md) §1 (lifecycle
    points).
  - [`ADR-7`](./adr/ADR-7-inner-loop-tool-registry.md) §1
    (`ToolSpec` / `ToolCall` / `ToolResult` contract).
- **Blocked-on:** none (M-6 was the only hard dep — landed via
  PR #20). M-7 (PR C) is not a blocker because IntentGuard
  wiring is explicitly out of M-8 scope (deferred follow-up).

## I-10 — Remove `bashlex` dependency from `bash_intent` module

- **Status:** deferred from dependency audit (2026-06-04).
- **Idea:** `bashlex>=0.18` is the project's only stale runtime dependency
  (last release 2023, no commits in 18 months, 30+ open issues).
  It is used by `src/fa/inner_loop/bash_intent.py` to parse bash
  command syntax into an AST for IntentGuard classification
  (repo writes / index writes / verifier commands). Replace it
  with a solution that has zero external dependencies while
  preserving classification accuracy.
- **Replacement options (pre-ranked):**
  1. **Targeted `shlex` + heuristic regex** (preferred). `shlex`
     (stdlib) tokenizes correctly; add a small state machine
     (~60–80 lines) that classifies token sequences into the
     same three buckets `bash_intent` produces today. Risk:
     edge-case bash syntax (subshells, arrays, brace expansion)
     may misclassify; mitigated by the fact that LLM-generated
     bash in tool calls is overwhelmingly simple (single commands
     or short pipelines).
  2. **Vendor a minimal bash parser** (~200–300 lines). Fork the
     subset of `bashlex` actually used (parser + AST visitor for
     simple commands only). Higher maintenance burden, but
     preserves exact AST semantics.
  3. **Keep `bashlex` but pin exact version.** Not a removal, but
     prevents silent upgrade to a broken future release. Fallback
     if (1) or (2) proves infeasible.
- **Blocked-on:** bash_intent API surface audit — a precise map of
  every `bashlex` class/method used and the classification rules
  they implement. Without this map the replacement cannot prove
  parity.
- **Unblock-trigger:** Either (a) bashlex confirmed abandoned
  (no release in 24 months) OR (b) the API-surface audit PR lands
  with a test matrix showing current classification results for
  ≥20 representative bash snippets (simple command, pipeline,
  subshell, variable assignment, git add/commit/push, rm, cp,
  mkdir, pip install, etc.).
- **First concrete step once unblocked:** Open a research spike PR
  that replaces `bashlex` with option (1) (`shlex` + heuristics);
  run the ≥20-snippet test matrix; if classification accuracy
  ≥95 % → merge; if <95 % → try option (2) or fall back to
  option (3) with a 12-month re-evaluation trigger.
- **Why this satisfies minimalism-first.** Removing a stale
  single-purpose dependency eliminates supply-chain risk and
  reduces the project's external surface. The `shlex` path is
  deterministic Python (AGENTS.md PR Checklist rule #10 q4) —
  no LLM judgement required at runtime.
- **References:**
  - `src/fa/inner_loop/bash_intent.py` — current consumer.
  - `src/fa/inner_loop/hooks/intent_guard.py` — downstream
    consumer of `bash_intent` classifications.
  - [`research/ci-qa-tooling-adversarial-2026-06.md`](./research/ci-qa-tooling-adversarial-2026-06.md)
    §0 R-4 (gitleaks recommendation) — same audit session
    surfaced this dependency risk.

## I-11 — Cross-platform test suite (Windows without bash / Developer Mode)

- **Status:** PARTIALLY RESOLVED by S12 (2026-08-02). The unblock-trigger fired
  ("first user reports running FA on native Windows without WSL"). S12 made the
  suite *honest* on Windows: 85 tests now carry capability markers
  (`tests/_capabilities.py`) that probe an effect rather than asking whether a
  binary is installed. **Still open:** FA has no Windows shell backend
  (`fs_run_cmd`), so those 85 remain unverified on native Windows. That is the
  ADR-scale half of this item.
- **Superseded detail:** the old `shutil.which("bash")` guard was itself the
  bug — Git Bash satisfies it and then answers `/c/...` for `C:\...`. 11 of the
  24 guards were *correct* and were kept; 13 were replaced.
- **Status (original):** deferred from test audit (2026-06-04).
- **Idea:** Three categories of tests fail on vanilla Windows:
  1. **Bash-dependent tests** (6 in `test_cli.py`, 1 in
     `test_inner_loop_runtime.py`, 1 in `test_inner_loop_runtime_limits.py`,
     2 in `test_inner_loop_tools.py`). They invoke `fs_run_bash` which spawns
     `bash` — not installed by default on Windows. Currently mitigated with
     `@pytest.mark.skipif(shutil.which("bash") is None)` but this skips
     silently; a better solution would use `cmd.exe` as a fallback shell on
     Windows so the same logic is still exercised.
  2. **Symlink-dependent tests** (3 in `test_sandbox_path_containment.py`,
     3 in `test_hygiene_hooks_install.py`). They call `os.symlink()` which
     requires Windows Developer Mode or admin privileges. With Developer Mode
     enabled these pass; without it they fail. Mitigation:
     `try/except (OSError, NotImplementedError)` or capability-based skip.
  3. **POSIX-only tests** (1 in `test_chunker_plaintext.py`:
     `test_anchor_falls_back_to_chunk_for_dot_only_name`). Windows forbids
     creating files named `...` (path traversal pattern), so the test fixture
     cannot be constructed. The chunker logic itself is fine; this is a test
     construction limitation.
- **Worth fixing?** The bash tests reveal the real gap: `fs_run_bash` is a
  POSIX shell tool. A Windows-native agent would need `fs_run_cmd` or a shell
  abstraction. The symlink tests are security-critical (sandbox escape
  detection) — skipping them on Windows means the Windows dev never validates
  the containment boundary locally.
- **Blocked-on:** Decision on whether FA targets POSIX-only environments
  (WSL, Git Bash, etc.) or native Windows. If POSIX-only, skip decorators
  are sufficient and this item closes as "by design". If native Windows
  is a target, the bash tool needs a `cmd.exe` / PowerShell backend and the
  sandbox containment needs `os.path` semantics review.
- **Unblock-trigger:** First user reports running FA on native Windows
  without WSL, OR a CI job is added that runs on `windows-latest` and fails.
- **First concrete step once unblocked:** Add a `windows-latest` CI matrix
  entry (GitHub Actions) to surface these failures automatically. Then decide
  per-category: skip (acceptable for bash), fix (for chunker fixture
  construction), or refactor (for sandbox symlink escape — use junction
  points on Windows instead of symlinks).
- **References:**
  - `tests/test_cli.py` — bash skip decorators added 2026-06-04.
  - `tests/test_sandbox_path_containment.py` — symlink escape tests.
  - `tests/test_chunker_plaintext.py::test_anchor_falls_back_to_chunk_for_dot_only_name`.
  - `tests/test_hygiene_hooks_install.py` — hook symlink installation.

## I-42 — `test_pty_persistence.py` shares a hardcoded global `/tmp`

- **Status:** open (found during S12, 2026-08-02). P3.
- **Idea:** 11 tests construct `PtyPool(max_size=1, base_cwd=Path("/tmp"))`
  instead of using the `tmp_path` fixture. They share one global directory, so
  parallel or repeated runs can collide. Unrelated to platform: `pty_pool.py`
  itself is correct (its default is `/workspace`, and the `RuntimeError` at
  line 630 is a deliberate Gap-6 fail-fast).
- **Repro:** `grep -c 'Path("/tmp")' tests/test_pty_persistence.py` -> 11.
- **First concrete step:** replace with `tmp_path`; the tests do not depend on
  the directory being `/tmp`.

## I-43 — the suite writes into the developer's real `~/.fa` on Windows

- **Status:** open (found during S12, 2026-08-02). P2.
- **Idea:** several tests isolate state with
  `monkeypatch.setenv("HOME", str(tmp_path/"home"))`. On POSIX
  `Path.home()` reads `HOME`, so this works. On Windows `ntpath.expanduser`
  prefers **`USERPROFILE`**, so the override is ignored and the run writes to
  the operator's real `~/.fa`. Measured: `ntpath.expanduser('~')` returns
  `C:\Users\Real` even with `HOME=/fake/home`.
- **Evidence:** this produced 7 of the 85 Windows failures (they looked like a
  missing `events.jsonl`, i.e. a product defect, until root-caused). Confirmed
  independently by `test_s10c_no_artifact_is_group_or_world_accessible`
  reporting the operator's real artifacts (`'session-log\\posture\\events.jsonl':
  '0o666'`).
- **Why not fixed in S12:** S12 is `tests/`-scoped and marker-only; the correct
  fix is a `conftest.py` seam that also sets `USERPROFILE`, which touches the
  deliberately narrow `_isolate_fa_session_log_root` fixture (its docstring
  records that patching `Path.home` globally broke 25 tests). Needs its own
  slice.
- **First concrete step:** in `tests/conftest.py`, set `USERPROFILE` alongside
  `HOME` in the autouse isolation fixture; re-run the Windows gate.

## I-44 — `ruff format --check .` fails on 39 markdown files

- **Status:** open (observed during S12, 2026-08-02; pre-existing). P3.
- **Idea:** `just lint` runs `ruff format --check .`, which formats fenced
  Python blocks inside `.md`. 39 documentation files under `knowledge/` and
  `worklogs/` fail. All 353 tracked `.py` files are clean. Present at
  `cf1a980`, before S12 began.
- **Note:** the operator's Windows run reported `643 files already formatted`,
  so the failure is environment-dependent (file discovery differs). Decide
  whether docs should be format-gated at all, or excluded via
  `extend-exclude`.
- **Repro:** `uv run ruff format --check .` vs
  `uv run ruff format --check $(git ls-files '*.py')`.

## I-45 — `install_hooks` is not idempotent on Windows

- **Status:** open (found during S12 Windows verification, 2026-08-02). P2.
- **Idea:** `_install_one` (`src/fa/hygiene/hooks/install.py:55`) treats an
  existing target as replaceable only when `target.is_symlink()`. But
  `install.py:63` forces `shutil.copy2` on `win32` — deliberately, because Git
  for Windows does not reliably execute a symlinked hook — so the installed
  target is **always a real file** there. The second `install_hooks()` call
  therefore raises `FileExistsError` instead of refreshing the hook.
- **Impact:** an operator re-running `fa hooks install` after a `git pull` gets
  a hard error on Windows, and the hook silently keeps the **old** content
  until they pass `force=True`. On POSIX the symlink keeps it current
  automatically, so the platforms disagree about whether hooks self-update.
- **Evidence:** `test_install_hooks_is_idempotent_replacing_own_symlinks` failed
  on a Windows box with Developer Mode enabled (symlink creation available, yet
  the install still copied). Marked `requires_symlink_hook_installs` in S12 so
  the suite is honest; the product behaviour is unchanged and still wrong.
- **First concrete step:** in `_install_one`, treat a target whose content
  matches the source as replaceable on `win32` (or pass `force=True` from
  `install_hooks` when the existing file is one of ours). Then drop the marker.

## I-46 — 12 remaining hardcoded `python3` invocations in tests

- **Status:** open (found during the S12 proactive audit, 2026-08-02). P3.
- **Idea:** Windows ships an App Execution Alias at `python3.exe` that prints a
  Microsoft Store notice and exits 9009. `shutil.which("python3")` finds it, so
  presence checks do not help. S12 added `requires_python3_executable` (which
  runs it and requires real output) and applied it to the one test that
  surfaced. Twelve other call sites remain, in
  `test_bash_intent.py`, `test_pty_persistence.py`, `test_sandbox_secret_paths.py`,
  `test_slice5_6_7_wiring.py`, `test_run_bash_tool_projection.py`,
  `test_inner_loop_tools.py`, `test_deploy_scripts.py`.
- **Why not urgent:** each currently sits inside a test already gated by
  `requires_pty_backend` or `requires_stable_tmpdir`, or is pure string
  analysis with no subprocess. They cannot bite on Windows today.
- **Why it still matters:** the protection is *incidental*. Removing an
  unrelated marker later re-exposes the hazard silently.
- **First concrete step:** apply `requires_python3_executable` to every test
  that actually spawns `python3`, or introduce a `PYTHON3` constant resolved
  once via `sys.executable`.
- **Repro:** `grep -rn 'python3' tests/*.py | grep -v _capabilities`

## I-47 — stale session clones accumulate without bound

- **Status:** open (observed during live S11.3, 2026-08-03). P3.
- **Idea:** `/sessions/<id>/` holds a full repo clone per session. The
  production box carried **18**, the oldest from 2026-07-01. Nothing prunes
  them. Each is a complete checkout, so disk grows linearly with sessions run.
- **Not a correctness issue:** they are only importable when the entrypoint puts
  the *current* session's `src` on `PYTHONPATH`
  (`scripts/fa-entrypoint.sh:199`); historical clones are inert.
- **First concrete step:** decide a retention policy (keep N most recent, or age
  out past D days) and implement it in the entrypoint or a `fa` housekeeping
  subcommand. Confirm nothing reads a historical clone before deleting.
- **Repro:** `docker compose exec -T first-agent sh -lc 'ls -d /sessions/*/src/fa | wc -l'`

## I-48 — `mistral-medium-2604` rejects FA's request shape (greedy sampling)

- **Status:** open (found S11.4e, **re-diagnosed** 2026-08-03 after an operator
  model swap). P2 — the model is unusable in any role.
- **Corrected diagnosis.** The first reading blamed the *planner role*. The
  operator then swapped models between roles, which isolated the variable:

  | run | `mistral-medium-2604` | `mistral-small-2603` |
  |---|---|---|
  | initial | planner → **400** | coder → 200, eval → 200 |
  | after swap | coder → **400** | planner → 200, eval → 200 |

  The fault follows the **model**, not the role. Any role configured with
  `mistral-medium-2604` fails; every role on `mistral-small-2603` succeeds.
- **Error:** HTTP 400 `{"message": "top_p must be 1 when using greedy sampling",
  "type": "invalid_request_greedy_sampling", "code": "3054"}`.
- **FA does not send `top_p`.** Verified by reading every emit site:
  `RequestInfo.top_p` defaults to `None` (`base.py:52`), `chain.py:332` only
  fills it from an explicit `sampling.top_p`, and `mistral.py:150` /
  `openai_compat.py:61` emit it **only when not None**. The operator's
  `models.yaml` sets no `sampling` block at all — the only active provider param
  is `reasoning_effort: "high"`.
- **Therefore the `top_p` is server-side.** `mistral-medium-2604` appears to
  apply its own default `top_p` (≠ 1) and then reject the combination with the
  `temperature=0.0` FA sends, most likely tied to `reasoning_effort: "high"`
  putting the model in a reasoning/greedy mode.
- **Candidate next steps (needs one experiment, not a code change yet):**
  1. probe `mistral-medium-2604` **without** `reasoning_effort` — if it passes,
     the interaction is confirmed and the fix is config;
  2. probe it with an explicit `sampling: {top_p: 1}` — if it passes, FA should
     send `top_p: 1` whenever `temperature == 0` for this family;
  3. probe with `temperature` unset — isolates the greedy trigger.
- **Do NOT "fix" by omitting `top_p` in `mistral.py`:** FA already omits it. A
  change there would be a fix to code that is not at fault.
- **Repro:** `docker compose exec -T first-agent fa probe --role <any-role-set-to-mistral-medium-2604> --timeout 30`
- **Related but distinct:** **I-50** is a *different* `request_shape` failure —
  same HTTP 400 family, but on `mistral-small-2603` inside a workflow stage
  transition, with `in=0`. Do not merge them: I-48 reproduces on a bare `probe`
  with one model; I-50 reproduces on a model that passes that same probe.

## I-49 — `state/models.yaml` is a REQUIRED mountpoint stub, not dead state

- **Status:** open, **re-diagnosed 2026-08-03 after the earlier advice caused a
  live outage.** P3 (documentation/robustness, not correctness).
- **CORRECTION.** The first write-up called
  `/srv/first-agent/state/models.yaml` "dead state ... delete it". The operator
  did, and the agent immediately reported
  `role 'planner' not found in /home/fa/.fa/models.yaml; known: []`.
  Restoring the file fixed it. **The advice was wrong.**
- **Mechanism.** `docker-compose.fa.yml` performs two *nested* binds:
  `/srv/first-agent/state` → `/home/fa/.fa` (rw), then
  `/srv/first-agent/routing/models.yaml` → `/home/fa/.fa/models.yaml` (ro).
  The second target lives **inside** the first bind, so the kernel needs a file
  to exist at that path in the parent filesystem to attach the mount onto.
  The state-dir file **is that mountpoint stub**. Remove it and the nested
  mount has nothing to cover, so the agent reads an absent config.
- **So the `644` is on a stub whose content is never read** — the ro mount
  covers it. That is why the S10c.3 pass can never repair it, and why the
  count will show 1 forever. Both observations from S11.6 stand; only the
  *remedy* was wrong.
- **Real (small) improvements, none of which is "delete it":**
  1. rename the host file to something self-describing, e.g.
     `state/models.yaml` → keep, but add `state/README-mountpoints.md`
     explaining that it must exist and its content is ignored;
  2. have `fa-clean-rebuild.sh` `touch` it if missing, so a well-meaning
     cleanup cannot break the deployment;
  3. add the same note as a comment in `docker-compose.fa.yml` next to the
     nested mount (the existing comment says the mount "hides any legacy
     state/models.yaml", which is what misled the analysis).
- **Repro of the failure mode:** `sudo rm /srv/first-agent/state/models.yaml`,
  recreate the container, then `fa run --role planner "hi"` → `known: []`.

## I-50 — resumed workflow stage sends an assistant message last; provider 400s

- **Status:** open, **ROOT-CAUSED 2026-08-03** from the live error body.
  **P1 — the `planner→coder→eval` pipeline cannot complete against Mistral.**
- **The provider's own words** (recovered from `events.jsonl`, not the console):

  ```
  status=400 code=3230 type=invalid_request_message_order
  "Expected last role User or Tool (or Assistant with prefix True)
   for serving but got assistant"
  ```

- **Mechanism, confirmed in source:**
  1. `prompt_composer.py:123-125` appends the task as a `user` message and then
     `non_cacheable.extend(observations)` — **observations come after the task**;
  2. `coder_loop.py:450-490` rebuilds `observations` from the session DB,
     appending only `model_msg` → `{"role": "assistant"}` and `tool_result` →
     `{"role": "tool"}`. It **never replays `user_msg` rows**;
  3. `_run_stage` (`cli.py:1248`) passes `"resume": not fresh`, so stage 2
     inherits stage 1's transcript;
  4. the planner ended `stopped_by_llm` on a plain text turn — a `model_msg`
     with **no** trailing tool call.

  Net message order: `[system, system, system, user "Task: …", …history…,
  assistant]`. The final element is an assistant message, which Mistral rejects
  for a non-prefix completion.

- **Explains every observation** (why it looked model-specific and role-specific
  and was neither):

  | scenario | rebuilt history | last role | result |
  |---|---|---|---|
  | standalone `fa run` | empty | `user` | **200** |
  | planner, stage 1 (`fresh`) | empty | `user` | **200** |
  | coder, stage 2 (`resume`) | planner's turns | **`assistant`** | **400** |
  | turn 2+ inside one session | ends in tool result | `tool` | **200** |

- **Not provider-exotic.** OpenAI tolerates a trailing assistant message;
  Mistral and Anthropic do not. FA supports all three, so the ordering must be
  normalised by FA, not left to the provider.
- **Why local tests missed it:** S8 drives the workflow through a scripted
  transport that accepts any message order. `_assert_tool_pairing_invariant`
  (`coder_loop.py:176`) checks tool-call/result **pairing** but says nothing
  about the **final role** — the invariant that actually matters here.
- **Candidate fixes (needs a decision → Q#):**
  1. **append the task last** for a resumed session, i.e. put
     `{"role": "user", "content": f"Task: {task}"}` *after* `observations`.
     Smallest change; also more natural — the new instruction should follow the
     inherited context rather than precede it. Risk: alters prompt-cache key
     ordering, so measure the cache-hit impact (currently 74–99%).
  2. **replay `user_msg` rows** in the rebuild so history is faithful. More
     correct in principle, larger blast radius, and still ends on an assistant
     message unless combined with (1).
  3. **normalise in the provider adapter** — append a minimal continuation user
     message when the last role is `assistant`. Localised, but hides the real
     ordering bug from every other caller.
  Recommend **(1)** plus a new ordering invariant asserting the last
  provider-visible message is `user` or `tool`, with a kill-check.
- **Repro:** `fa workflow planner,coder,eval "<any task>" --mode linear`
  — fails at stage 2, turn 1, `in=0`. Three consecutive reproductions with
  different transcripts and targets.

## I-52 — resumed history is not a faithful replay (`user_msg` rows dropped)

- **Status:** open (found while root-causing I-50, 2026-08-03). P2.
- **Idea:** `coder_loop.py:450-490` rebuilds `conversation_history` from the
  session DB by translating **only** `model_msg` → `assistant` and
  `tool_result` → `tool`. `user_msg` rows are written (`coder_loop.py:493`) but
  **never replayed**.
- **Consequence:** a resumed stage sees the previous stage's assistant turns and
  tool output, but not the instruction those turns were responding to. The model
  is asked to continue work whose stated goal is missing from its context.
- **Relationship to I-50:** S13's normalization makes the request *valid*
  (message ordering). It does not make the history *complete*. These are
  separate defects and fixing the first does not fix the second.
- **Why not fixed in S13:** replaying `user_msg` changes the token cost and the
  cache key of every resumed request, and interacts with compaction
  (`latest_comp_idx` windowing at `coder_loop.py:455-463`). It needs its own
  measurement, not a rider on an ordering fix.
- **First concrete step:** add a C1 test asserting a resumed transcript contains
  the prior stage's user instruction; then decide whether to replay verbatim or
  to summarise prior stages into the task text.
- **Repro:** run `fa workflow planner,coder,eval`, then inspect the coder
  stage's outgoing body — no `user` message from the planner stage appears.

<<<<<<< ours
<<<<<<< ours
=======
>>>>>>> theirs
## I-53 — RESOLVED (2026-08-04): pre-S7.5 S4-F1 residue, not a live defect

- **Status:** **RESOLVED — no code change required.** Kept as a record because
  the diagnosis is reusable.
- **What it was:** `/sessions/session-20260728T075426-7/.fa/session.db`,
  **69,632 bytes**, found by S11.8a's stray-authority scan. Opened read-only:

  | field | value |
  |---|---|
  | `run_id` | `('cli-smoke',)` — sole value |
  | rows | 63 |
  | `session_id` | `('',)` — **empty** |
  | `session_meta` | `schema-version session-v1`, `2026-07-28T09:28:05.729Z` |

- **Diagnosis.** `cli-smoke` is `_SMOKE_SESSION_ID` (`cli.py:893`), written by
  `fa inner-loop-smoke`. The **empty `session_id` alongside a populated
  `run_id` is the exact S4-F1 signature** — `cli.py:890-892` records it
  verbatim: *"the S4-F1 defect was precisely that the run was labelled while the
  session was left empty."*
- **Dated conclusively.** Artifact written **2026-07-28T09:28Z**; S4-F1 fixed in
  `16145b9` on **2026-07-29** ("S7.0-S7.6 … fix S4-F1 (Q28b)"). The file
  pre-dates its own fix by one day.
- **The fix is already regression-locked.**
  `tests/test_s7_cli_run_paths.py:193
  test_smoke_creates_no_session_less_authority_at_the_fa_root` asserts
  `<workspace>/.fa/session.db` is never recreated, with a documented kill-check.
  So the defect cannot return silently.
- **Why the size was misleading.** 69 KB looked like an active misroute. It is
  63 rows of smoke-run events from a single pre-fix invocation — large because
  SQLite pages, not because traffic is still flowing.
- **Disposition:** delete the file, or leave it as a dated artifact. Either is
  safe. **Do not** treat it as evidence of a current routing bug.
- **Method note:** the 8a scan classified it `STRAY` correctly and the
  *classification was right while the initial interpretation was wrong*. Size
  alone suggested severity; only `run_id` + `session_id` + the timestamp
  identified it. Three cheap fields beat one expensive assumption.
<<<<<<< ours
=======
## I-53 — a session-clone-local `session.db` under `/sessions`

- **Status:** open (found during live S11.8a, 2026-08-04). P3 — explain before
  dismissing.
- **Observation:** the stray-authority scan found
  `/sessions/session-20260728T075426-7/.fa/session.db` — an authority database
  inside a *workspace clone*, not under the state root
  (`/home/fa/.fa/sessions/`). Exactly **one** of the ~18 historical clones has
  one.
- **Why it matters:** S5 made the state-root session DB the single authority.
  A second database inside a clone is either (a) legitimate clone-local state,
  (b) a leftover from a pre-S5 layout, or (c) a run that wrote its authority to
  the wrong root. Only (c) is a defect, but all three look identical from a
  file listing.
- **Why only one clone:** that is the discriminating question. If it were the
  normal layout, all 18 would have one; if it were pre-S5 residue, the *oldest*
  clones would have one and this is dated 2026-07-28, mid-range.
- **First concrete step:** open it read-only and read `session_meta` +
  `SELECT DISTINCT run_id FROM event_log`. A run_id matching a known S11 or
  earlier run identifies which run wrote it and when.
- **Repro:** `docker compose exec -T first-agent find /sessions -name session.db`
<<<<<<< ours
>>>>>>> theirs
=======
- **UPDATE 2026-08-04 (live S11.8a):** the file is **69,632 bytes**, not a stub.
  Something wrote a substantial event log into a workspace clone instead of the
  state root. That removes the "harmless leftover" reading and makes option (c)
  — a run whose authority went to the wrong root — the leading hypothesis.
  Raise to **P2** and read `session_meta` + `SELECT DISTINCT run_id` first.
>>>>>>> theirs
=======
>>>>>>> theirs

## I-51 — `request_shape` console output discards the provider's error

- **Status:** open (found while diagnosing I-50 live, 2026-08-03). P2 —
  observability; it is what made I-50 hard to diagnose.
- **Symptom:** a 400/422 from the provider renders as

  ```
  ⏳ retry in 0s (unknown/0)
  FAIL: request_shape (turns=1)
  ```

  `unknown/0` is a placeholder. The operator gets **no** indication of why the
  provider rejected the request.
- **Mechanism.** `coder_loop.py:1367-1379` builds the `api_retry` event with
  `provider="unknown"` and `status=0` **hardcoded**, discarding both values from
  the exception. The real detail is placed in a `reason` key —
  `f"request_shape_error: {exc}"` — but `ConsoleRenderer._handle_api_retry`
  (`output.py:347-352`) renders only `retry_after_s`, `provider` and `status`.
  **`reason` is never printed.**
- **Contrast:** `fa probe` prints the same exception directly
  (`cli.py:2978`) and shows the full body:
  `status=400 body={'message': 'top_p must be 1 ...', 'code': '3054'}`.
  Two paths, the same error class, radically different diagnosability.
- **The data is not lost** — `coder_loop.py:1363` writes
  `{"reason": "request_shape", "detail": str(exc)}` to `events.jsonl`, so the
  cause is recoverable post-hoc. Only the live console is blind.
- **Fix (small, two sites):**
  1. carry the real provider/status on the event instead of the placeholders —
     `ProviderRequestShapeError` already has `.status`;
  2. render `reason` in `_handle_api_retry` when present.
  Add a C1 test asserting the rendered line contains the provider's message,
  and a kill-check that reverting either half loses it.
- **Repro:** any workflow stage that 400s; compare console output against
  `jq -r 'select(.kind=="run_stopped")|.content.detail' events.jsonl`.

## I-54 — prompt caching: replace universal `prompt_cache_key` with a capability-driven model

- **Status:** open (found S13, 2026-08-05). P2 — affects cost and multi-provider
  compatibility; a *transition*, not a one-line bugfix.
- **Observation.** `prompt_composer.to_openai_request_v2` sends
  `prompt_cache_key` + `prompt_cache_retention` in **every** OpenAI-compatible
  request, unconditionally (`prompt_composer.py:241`). These are **not a
  universal standard**: OpenAI-style proxies accept them, Mistral accepts
  `prompt_cache_key` but drops `retention`, and **NVIDIA build rejects both with
  400 "Unsupported parameter(s)"** (the live breakage this backlog item records).
  The key is also **never read back** — FA only *measures* the provider-reported
  `cache_hit_ratio` (`coder_loop.py:144-164`), so the emitted key does not itself
  drive caching.
- **Source-verified context (2026-08-05).** No mainstream harness sends these two
  params universally:
  - **Hermes (Nous)** — read `agent/prompt_caching.py`: uses Anthropic
    `cache_control` **breakpoints** on a stable prefix (4 blocks: static system
    prefix + end of system + last 2 messages), with a frozen-snapshot stable
    prefix. Does **not** use `prompt_cache_key`. Handles envelope-vs-native
    wire-format differences (and tracks bug #20957 where caching silently does
    nothing on the OpenAI-compat wire path).
  - **opencode (sst)** — read `packages/opencode/src/provider/transform.ts`:
    sets `promptCacheKey` **gated** (`if providerID==="openai" ||
    setCacheKey`), uses AI-SDK `providerOptions.anthropic.cacheControl` for
    Anthropic breakpoints. Does not set it for all providers (issue #25984 shows
    proxies can ignore it; `pi-opencode-go-cache` table confirms opencode CLI
    sends neither `prompt_cache_key` nor `prompt_cache_retention` by default).
  - **pi agent** (pi.dev / `pi-opencode-go-cache`) — explicitly gates
    `prompt_cache_key`/`retention`/`cache_control` per model, skips providers
    that reject them (e.g. GLM), i.e. a capability-driven approach like our S13
    `MessageRules.supports_prompt_cache`.
- **Consequence for aggregate providers.** The operator plans one-key-many-models
  aggregate routing (OpenRouter-style, and NVIDIA's endpoint is an aggregator
  too). There, caching is whatever the **upstream** supports; `prompt_cache_key`
  may be honored, ignored, or rejected. Two wire formats matter (OpenAI-compat
  vs Anthropic-compat `cache_control`), and Anthropic breakpoints only work on
  the native wire.
- **Needed transition (proposal).** Move from a single unconditional key to a
  **per-provider capability-driven cache model**, applied at the single
  chokepoint (`validate_and_normalize`), e.g. a richer `MessageRules` cache-style
  (`auto` / `keyed` / `breakpoints` / `none`):
  1. default **automatic prefix caching** (OpenAI/DeepSeek-style, no key) for
     OpenAI-compat upstreams;
  2. **gate `prompt_cache_key`** to providers that actually support it (OpenAI,
     Mistral), never send it unconditionally;
  3. **Anthropic `cache_control` breakpoints** on the already byte-stable
     cacheable prefix (Hermes' proven approach) for the Anthropic wire path.
- **⚠️ Re-research needed to update the baseline** (this item is a *start*, not
  the final design): before implementing, re-verify against the **latest**
  releases of opencode, Hermes, and the **pi** agent, and re-read the provider
  docs (OpenAI prompt-cache options incl. newer `prompt_cache_options` for
  GPT-5.6+; Mistral `prompt_cache_key`; NVIDIA/NIM). Confirm current wire shapes
  and cache-hit pricing per provider — the research above is dated 2026-08-05.
- **Do NOT** keep the assumption that "sending `prompt_cache_key` universally =
  good caching." The S13 `supports_prompt_cache` flag is correct **containment**;
  the capability-driven model is the follow-up transition.
- **First concrete step:** extend `MessageRules` with a cache-style capability;
  wire it in `validate_and_normalize`; add per-provider live measurement of
  `cache_hit_ratio` (already computed) before/after; keep the live ≥74% cache-hit
  gate per provider.
- **Repro:** `fa workflow` on a provider that rejects `prompt_cache_key` (e.g.
  NVIDIA) → 400 "Unsupported parameter(s): prompt_cache_key, prompt_cache_retention".

## I-12 — Authoring rules: scope coverage gap (`scripts/`, `verifiers/`)

- **Status:** deferred from ADR-11 PR-2 self-review (2026-06-06).
- **Idea:** PR-2 Level-1 rules scope strictly: V2 (`exports.py`) scans
  `src/` only; V4 / V11 (`tests.py`) scan `tests/` only. Two real
  source trees are therefore **not** authoring-guarded today:
  - `scripts/` — contains `check_protected_paths.py`, the
    governance bundle's diff-checker. A regression here weakens the
    TCB-write defense (ADR-11-I7) but no rule catches it.
  - `verifiers/` — contains the DSV YAML contracts and helper Python.
- **Worth fixing?** Yes, but low priority. `scripts/` is one file
  today; `verifiers/` is YAML-heavy with little Python. The risk
  surfaces if either grows: new helpers added without `__all__`
  curation, or test helpers slipping into `verifiers/` with
  `pytest.skip`.
- **Blocked-on:** None. Two-line constant change in each rule
  (`_INCLUDED_PREFIXES` tuple).
- **Unblock-trigger:** Either tree gains a second `.py` file, OR a
  V2-class regression is detected manually in `scripts/`.
- **First concrete step once unblocked:** Extend `_INCLUDED_PREFIXES`
  in `src/fa/authoring_rules/exports.py` to `("src/", "scripts/",
  "verifiers/")`. Re-run `fa authoring-check` and triage any new
  findings the same way `TimeSource` was triaged in PR-2 (add to
  `__all__` or rename `_`-private).
- **References:**
  - `src/fa/authoring_rules/exports.py:41` — `_INCLUDED_PREFIXES`.
  - `src/fa/authoring_rules/tests.py:54` — `_INCLUDED_PREFIXES`.
  - ADR-11 §I-7 (protected-path bundle, lists `scripts/check_protected_paths.py`).

## I-13 — V4 import-alias bypass (`from pytest import skip`)

- **Status:** known limitation from ADR-11 PR-2 stress-test (2026-06-06).
- **Idea:** V4 `TEST_SEMANTIC_DECAY` binds to the literal AST shape
  `pytest.skip(...)` / `pytest.mark.skip`. An adversarial author (or
  an LLM that has read the rule) can bypass with:
  ```python
  from pytest import skip

  skip("nope")  # not detected
  ```
  The decorator form (`@pytest.mark.skip`) is unaffected because the
  attribute chain is the same regardless of how `pytest` was imported.
- **Cost / benefit:** Implementing full import-alias tracking via
  `ast.NodeVisitor` is ~half a day (one visitor that builds a
  `name → fully-qualified-name` map). The corresponding risk is real
  but small: bypass requires the author to deliberately write a less
  idiomatic import. Net cost-of-bypass is now ≈30 seconds of typing,
  same order as commenting the rule out — already covered by
  ADR-11 §12.4 (the bar is "raise the cost of bypass", not "prove
  impossibility").
- **Blocked-on:** None. Pure implementation work in
  `src/fa/authoring_rules/tests.py`.
- **Unblock-trigger:** Either an `fp-corpus` measurement (PR-4)
  surfaces a real bypass in production, OR ADR-11 §12.4 is amended
  to require full alias-tracking for all V4-class rules.
- **First concrete step once unblocked:** Add an import-walker pass
  before the AST-walk; build a `{local_name: pytest.<attr>}` map for
  each file; widen `_is_pytest_call` / `_pytest_mark_attr` to consult
  the map. Add fixture tests for the four bypass shapes
  (`from pytest import skip`, `import pytest as pt`, `pt.skip(...)`,
  `pt.mark.skip`).
- **References:**
  - `src/fa/authoring_rules/tests.py:62` — `_is_pytest_call`.
  - `src/fa/authoring_rules/tests.py:73` — `_pytest_mark_attr`.
  - ADR-11 §12.4 (regex/AST bypass acknowledged risk).

## I-14 — ADR-11 PR-3+ rule packs (V3, V5, V7, V10, V12, V14)

- **Status:** scheduled per blueprint Appendix B; PR-2 landed
  2026-06-06 with V2 / V4 / V11.
- **Idea:** Remaining V-N codes from the F-1..F-10 catch-corpus table:
  - **V3 — generation parity** (F-3 `SQUASH_MSG` Python↔Bash drift).
    Lives in `src/fa/authoring_rules/parity.py`. **PR-3.**
  - **V5 — doc integrity** (F-5 stale BACKLOG, F-6 missing `llms.txt`
    entry). Lives in `src/fa/authoring_rules/docs.py`. **PR-3.**
  - **V6 — session seam** (`.fa/session.toml` staged-paths ⊆ seam).
    Lives in `src/fa/authoring_rules/seam.py`. **PR-4** alongside
    the `catch-corpus/` + `fp-corpus/` directories.
  - **V7 — SSOT enum** (F-1 bash-intent classifier shape).
    Advisory-first. **PR-3 or later.**
  - **V10 — reference safety** (F-8 signature change with missed
    call-sites). Requires inter-procedural / call-graph analysis;
    **deferred indefinitely until a stdlib AST approach is proven
    cheap enough** (Semgrep-OSS is intra-procedural so wouldn't
    help; the adversarial note R-8 already documents this).
  - **V12 — message registry**. **PR-5.**
  - **V14 — AI session trailers** (F-10 `Co-authored-by` omitted).
    Procedural until harness emits read-receipts; **deferred per
    ADR-11-I8** ("I-BOOT is procedural until the harness can emit
    read receipts").
- **Blocked-on:** PR-2 has now landed. Roadmap proceeds PR-3 → PR-4 → PR-5.
- **Unblock-trigger:** PR-2 is merged + no FP regressions surface
  in the first week of production use.
- **First concrete step once unblocked:** PR-3 — create
  `src/fa/authoring_rules/parity.py` with a single rule pinning
  `SQUASH_MSG` between `src/fa/hygiene/pr_intent.py` and the
  git hook bash script (the existing
  `tests/test_pr_intent_snapshot.py` is the seed pattern).
- **References:**
  - `knowledge/research/ADR-11-Authoring-Guardrails-Blueprint.md`
    Appendix B (full rollout schedule).
  - `src/fa/authoring_rules/README.md` (rollout table, PR-2 marked done).

## R-7 — DEFER `ty` as primary type checker until stable 1.0

- **Status:** deferred from CI/QA tooling audit (2026-06-04).
- **Idea:** Astral's `ty` is beta (v0.0.37); no plugin system, different unannotated-body semantics than mypy. Migration is technically viable (FA has no mypy plugins) but premature.
- **Blocked-on:** `astral-sh/ty` releases 1.0.0.
- **Unblock-trigger:** `astral-sh/ty` releases 1.0.0.
- **First concrete step once unblocked:** Re-evaluate mypy vs ty migration on the then-current FA codebase; run both in parallel for one cycle before flipping the gate.
- **References:** [`research/ci-qa-tooling-adversarial-2026-06.md`](./research/ci-qa-tooling-adversarial-2026-06.md) §0 R-7.

## R-8 — DEFER custom Semgrep rules for `@tool` surface until harness stabilizes

- **Status:** deferred from CI/QA tooling audit (2026-06-04).
- **Idea:** Custom Semgrep rules for `@tool` decorator boundaries, MCP protocol misuse, and LLM-tainted args are valuable, but FA's tool surface is still evolving.
- **Blocked-on:** ADR-8 / HookRegistry contract freeze.
- **Unblock-trigger:** "Custom Semgrep rules blocked on ADR-8 freeze"
- **First concrete step once unblocked:** Author custom Semgrep YAML rules targeting `src/fa/inner_loop/tools/` and `src/fa/inner_loop/registry.py`; run them advisory for 4 weeks before promoting to blocking.
- **References:** [`research/ci-qa-tooling-adversarial-2026-06.md`](./research/ci-qa-tooling-adversarial-2026-06.md) §0 R-8.

## R-9 — DEFER DeepEval / Promptfoo agent eval harness until UC5

- **Status:** deferred from CI/QA tooling audit (2026-06-04).
- **Idea:** Agent behavioral evaluation is critical (Pillar 4), but FA has no stable inner-loop contract or golden prompt dataset yet. Eval without a stable harness measures noise.
- **Blocked-on:** UC5 eval-harness infrastructure + inner-loop contract freeze.
- **Unblock-trigger:** "UC5 eval-harness: evaluate DeepEval vs Promptfoo after inner-loop contract freeze"
- **First concrete step once unblocked:** Build a golden prompt dataset (≥20 hand-annotated sessions), integrate both DeepEval and Promptfoo in parallel advisory jobs, and pick the one with lower FP rate on the golden set.
- **References:** [`research/ci-qa-tooling-adversarial-2026-06.md`](./research/ci-qa-tooling-adversarial-2026-06.md) §0 R-9.

## R-10 — DEFER `Tach` module boundary enforcement until module count > 5

- **Status:** deferred from CI/QA tooling audit (2026-06-04).
- **Idea:** Tach enforces import boundaries between modules. FA currently has ~15 top-level packages under `src/fa/`, but most are tightly coupled and not independently deployable.
- **Blocked-on:** `src/fa/` exceeds 5 independently deployable modules.
- **Unblock-trigger:** "Adopt Tach when module count > 5"
- **First concrete step once unblocked:** Add `tach.toml` with import boundaries between the independently deployable modules; gate CI on `tach check`.
- **References:** [`research/ci-qa-tooling-adversarial-2026-06.md`](./research/ci-qa-tooling-adversarial-2026-06.md) §0 R-10.

## R-11 — SKIP `garak` adversarial scanning for now

- **Status:** skip from CI/QA tooling audit (2026-06-04).
- **Idea:** NVIDIA's `garak` probes LLMs for jailbreaks, prompt injection, and data extraction. Complementary to SAST.
- **Blocked-on:** FA exposes a network-facing agent endpoint.
- **Unblock-trigger:** FA exposes a network-facing agent endpoint.
- **First concrete step once unblocked:** Evaluate garak v0.14+ against the live endpoint; integrate as an advisory nightly scan.
- **References:** [`research/ci-qa-tooling-adversarial-2026-06.md`](./research/ci-qa-tooling-adversarial-2026-06.md) §0 R-11.

## R-12 — SKIP `CodeQL` deep taint analysis

- **Status:** skip from CI/QA tooling audit (2026-06-04).
- **Idea:** CodeQL provides deeper inter-procedural taint than Semgrep OSS, but it is slow and memory-heavy. FA's threat model is authoring-time, not runtime taint.
- **Blocked-on:** Semgrep advisory proves useful and deeper taint is needed.
- **Unblock-trigger:** Semgrep advisory surfaces actionable findings that require inter-procedural taint.
- **First concrete step once unblocked:** Enable CodeQL weekly as a deeper nightly layer alongside Semgrep.
- **References:** [`research/ci-qa-tooling-adversarial-2026-06.md`](./research/ci-qa-tooling-adversarial-2026-06.md) §0 R-12.

## R-13 — SKIP `Vulture` dead-code detection as a CI gate

- **Status:** skip from CI/QA tooling audit (2026-06-04). **Partial landing in
  PR #28 (guardrails-v2, 2026-06-12):** vulture added to dev extras so the
  existing `just deadcode` recipe actually runs (it was a silent no-op without
  the package). Still advisory-only / not a CI gate — the SKIP verdict on
  gating stands unchanged.
- **Idea:** Vulture finds dead code (unused functions/classes/variables). AI projects accumulate it, but Vulture has high false positives on dynamically dispatched code.
- **Blocked-on:** Manual dead-code audit desired (monthly).
- **Unblock-trigger:** Manual dead-code audit desired (monthly).
- **First concrete step once unblocked:** Run `make deadcode` (`vulture src/ --min-confidence 90`) manually; do not gate CI on it.
- **References:** [`research/ci-qa-tooling-adversarial-2026-06.md`](./research/ci-qa-tooling-adversarial-2026-06.md) §0 R-13.

## R-14 — SKIP `pytest-recording` / VCR.py for LLM mocks

- **Status:** skip from CI/QA tooling audit (2026-06-04).
- **Idea:** VCR.py records HTTP fixtures for deterministic CI. FA's test suite mocks LLM calls at the `ProviderAdapter` level — no real HTTP traffic in tests yet.
- **Blocked-on:** Tests introduce HTTP-dependent components (provider client integration tests).
- **Unblock-trigger:** Tests introduce HTTP-dependent components (provider client integration tests).
- **First concrete step once unblocked:** Add `pytest-recording` and record cassettes for the first HTTP-dependent test.
- **References:** [`research/ci-qa-tooling-adversarial-2026-06.md`](./research/ci-qa-tooling-adversarial-2026-06.md) §0 R-14.

## I-20 — V2 nested tuple-unpacking definitions

- **Status:** deferred from PR-11 (PR-10 follow-up).
- **Idea:** `_public_symbols` walks the first level of `ast.Tuple` / `ast.List` assignment targets at module scope, but does NOT recurse into nested tuples (`(a, (b, c)) = ...`). The structurally-correct extension is to recurse, registering each leaf `ast.Name` against the outer `Assign` node.
- **Blocked-on:** None technically; deferred because the live repo has zero instances of nested top-level tuple unpacking with `__all__`.
- **Unblock-trigger:** ≥1 instance of nested top-level tuple unpacking appears under `src/` in a module with `__all__`.
- **First concrete step once unblocked:** Extend `_register` in `_public_symbols` to recurse into nested `ast.Tuple`/`ast.List` targets; add fixture under `catch-corpus/F-2-nested/` and a regression test mirroring the existing `test_tuple_unpacking_at_top_level_is_flagged`.

## I-21 — V2 phantom-name inverse check

- **Status:** deferred from PR-11 (PR-10 follow-up). Originally proposed as a pass-1 HIGH item; dropped because the live repo has 16 `__init__.py` modules that re-export symbols via plain `from .x import Foo` listed in `__all__`. Naive enforcement would HARD-BLOCK every one of them.
- **Idea:** Catch names that appear in `__all__` but have no in-module definition (the F822 ruff check, lifted into the authoring kernel for completeness with ADR-11-I2's "kernel is authoritative" stance).
- **Blocked-on:** A definition-predicate extension that treats plain `from .x import Foo` as a "definition for the purpose of `__all__` membership only" (the rule's primary direction — defined-but-not-in-`__all__` — must continue to NOT count plain imports, or BLOCKER-1 territory re-opens).
- **Unblock-trigger:** Any PR with a phantom name in `__all__` slips past ruff F822 on `main`, OR ruff is removed / disabled in CI.
- **First concrete step once unblocked:** Add `_public_symbols_for_phantom_check(tree, declared_all)` that treats `ImportFrom` targets named in `declared_all` as definitions; emit `FA-AUTHORING-V2-EXPORTS-PHANTOM` for names in `__all__` absent from that extended set.

## I-12-bis — Manifest-driven scope for Level-1 rules

- **Status:** deferred from PR-11 (PR-10 follow-up). Original "PR-14" idea consolidated into the next PR-4 cycle per ADR-11 Appendix B.
- **Idea:** Replace the hard-coded `SRC_SCOPE`/`TEST_SCOPE` tuples in `src/fa/authoring_rules/_scan.py` with a manifest-driven scope read from `.fa/session.toml [scope]` (fields `src_prefixes`, `test_prefixes`). Lets monorepo layouts (`core/src/`, `plugins/src/`) scope the rules without rule-pack edits, and makes scope auditable from one place.
- **Blocked-on:** ADR-11 PR-4 (`.fa/session.toml` schema; `seam.py`). The manifest does not exist on `main` today (`ls .fa/` is empty); creating it ahead of PR-4 would invert the published Appendix B rollout.
- **Unblock-trigger:** ADR-11 PR-4 lands `.fa/session.toml` schema + `seam.py`.
- **First concrete step once unblocked:** Extend `parse_manifest` to recognise `[scope]` table; add `Manifest.scope: ScopeConfig` field; rule packs read `context.manifest.scope.<prefix>` with fall-back to `SRC_SCOPE`/`TEST_SCOPE` when no manifest is supplied.

## I-22 — Per-file source decode caching for rule packs

- **Status:** deferred from PR-12 (PR-10 follow-up).
- **Idea:** `iter_python_files` is called once per rule; each call reads bytes and re-parses. Cache `(path → (bytes, tree))` in `RuleContext` and have rules consume the pre-parsed tree. ~50 LOC; eliminates linear-in-rule-count IO/parse cost.
- **Blocked-on:** None technically; deferred because the rule count is small (3) and end-to-end runtime is 0.057 s on the test corpus. The improvement becomes visible only at ≥5 rules.
- **Unblock-trigger:** `len(RULE_ALLOWLIST) >= 5` on `main` (next reached when PR-3 lands `parity.py` + `docs.py`).
- **First concrete step once unblocked:** Extend `RuleContext` with `parsed: Mapping[str, tuple[bytes, ast.Module]]`; lazy-populate in the kernel pre-pass (PR-12's `_parse_visibility_diagnostics` already does the parse — share the result).

## I-15 — Visitor framework for shared `ast.walk`

- **Status:** deferred from PR-12 (PR-10 follow-up).
- **Idea:** Multiple Level-1 rules walk the same `ast.Module` independently. A small visitor framework (the Grafema `Analysis.Walker` pattern ADR-11 §Prior Art cites) lets N rules share one traversal per file.
- **Blocked-on:** I-22 (per-file caching) lands first — without cached trees, the visitor framework gains nothing.
- **Unblock-trigger:** I-22 merged AND `len(RULE_ALLOWLIST) >= 5`.
- **First concrete step once unblocked:** Define `Visitor` protocol with `visit_<NodeType>` dispatch; convert existing rules incrementally; benchmark before/after.

## I-16 — Read-receipt artefact (path + sha256) per rule inspection

- **Status:** deferred from PR-12 (PR-10 follow-up).
- **Idea:** The kernel logs `(rule, path, sha256)` for every file a rule actually inspected, surfaced in the JSON wire form. Enables byte-exact replay diff across PRs (the I-AUDIT operational invariant from `PR-10-review-pass2.md`).
- **Blocked-on:** Harness emits run-receipts in the inner loop (ADR-11-I8 procedural-until-receipts comment); without a consumer the artefact has no name.
- **Unblock-trigger:** Inner-loop run-receipt format is defined (cross-link to ADR-8 HookRegistry receipt work).
- **First concrete step once unblocked:** Extend `RuleContext` with a `record_inspection(rule, path, sha256)` callback; aggregate into `KernelReport.inspections` field; update JSON schema.

## I-17 — `.fa/authoring-suppressions.toml` mechanism

- **Status:** deferred from PR-12 (PR-10 follow-up).
- **Idea:** Frozen TOML file listing `(code, path, rule_input_hash, expires_on, justification, signed_by)` for kernel-acknowledged suppressions. Suppressions live OUTSIDE source code so agent edits are glaringly visible; the kernel drops matching diagnostics but emits an INFO listing every active suppression.
- **Blocked-on:** A measured need — ADR-11 currently has no suppression mechanism and minimalism-first says we add one only when forced.
- **Unblock-trigger:** ≥3 acknowledged false-positive findings on `main` cannot be resolved through the `fp-corpus/` measurement loop within 1 week.
- **First concrete step once unblocked:** One ADR-11 amendment paragraph choosing between "frozen suppression TOML" and "forbid loudly + corpus-only"; the amendment becomes the spec for the implementation PR.

## I-23 — Mutation testing: promotion to blocking gate

- **Status:** deferred from the test-gaming-hardening PR (2026-06-12), which repaired
  the silently-dead weekly mutation workflow (mutmut 2.x CLI flag removed in 3.x;
  `|| true` swallowed the instant error — every prior weekly run tested nothing) and
  measured the first honest baseline: 633 mutants / 470 killed / **163 survived**
  (sandbox scope).
- **Idea:** once all baseline survivors are cleared (or explicitly accepted with
  rationale), flip `.github/workflows/tests.yml` to `continue-on-error: false` and
  gate on `survived == 0` from `mutants/mutmut-cicd-stats.json`. No numeric budget
  file: the governance surface is the incremental workplan, not a threshold knob.
- **Blocked-on:** survivor-clearing work tracked in
  [`knowledge/mutation-survivors-workplan.md`](./mutation-survivors-workplan.md)
  (per-module table, clearing order, accepted-survivor rule).
- **Unblock-trigger:** `knowledge/mutation-survivors-workplan.md` is **deleted**
  (all rows cleared/accepted). The workplan's own header mirrors this trigger.
- **First concrete step once unblocked:** in `tests.yml` set
  `continue-on-error: false`; replace the `|| true` on the results step with a
  jq assert `.survived == 0` on the stats JSON; close this entry with a
  «landed in PR #N» marker.

## I-19 — `# fa-noqa` inline-suppression policy decision

- **Status:** deferred from PR-12 (PR-10 follow-up).
- **Idea:** Same problem space as I-17 but at line granularity. The kernel currently has no `# noqa`-style mechanism (good — keeps the trust boundary clean); when an LLM agent encounters a HARD-BLOCK, the path of least resistance is to look for an inline suppression syntax.
- **Blocked-on:** I-17 — the line-level decision should follow the file-level one, not lead it.
- **Unblock-trigger:** I-17 merged AND ≥1 PR explicitly asks for line-level suppression after file-level mechanism exists.
- **First concrete step once unblocked:** Decide on the suppression syntax (`# fa-noqa: V<N>` vs. `# fa-suppress(<CODE>): <justification>`); implement parser; integrate with the per-finding hash so a suppression cannot drift to a different finding silently.

## I-24 — Secret-isolation follow-ups (ADR-12)

- **Status (updated 2026-06-16):** the egress-injection proxy (formerly the
  "heavy v0.2" tier here) **shipped in v0.1** — LLM provider keys now live only
  in the `fa-egress-proxy` container; the agent cannot read OR redirect them.
  Two follow-ups remain, ordered by how unblock-ready they are.

- **(a) Constrained git interface — close the deploy-key residual (FIRST, unblock-ready).**
  The GitHub deploy key still lives in the agent container (git push runs there).
  It is protected by the bash-gate secret-path deny + the model-egress redactor,
  but a determined attacker who reads the key file via a bash form the lexical
  tripwire misses AND applies an exotic encoding (gzip+xor) the redactor doesn't
  know could still surface it. Airtight closure: expose git push as a narrow tool
  (or a second tiny proxy / credential-helper) that holds the key outside the
  agent's reach, mirroring the LLM-key proxy. LLM keys do NOT share this residual.
  - **First concrete step:** add a `git.push` tool that shells out with the key
    delivered via a credential helper the agent's uid cannot read, then remove
    the `git_key` mount from the agent container.

- **(b) Proxy egress allowlist — limit the proxy's own outbound.** Restrict the
  `fa-egress-proxy` container's outbound network to the provider hosts derived
  from `models.yaml` `base_url`s (host UFW/iptables or a tiny allowlist). The
  agent container itself can then be tightened (it only needs to reach the proxy
  and GitHub). Hardens a compromised-proxy scenario and prevents key redirection.
  - **First concrete step:** emit a UFW egress snippet from `models.yaml` hosts
    in `setup-fa-desktop.sh`; document update-together with `models.yaml`.

- **(c) Future hardening (v0.2+).** Per-route scopes + rotation hooks on the
  proxy; mTLS for fa→proxy instead of the shared bootstrap token; entropy-based
  output redaction (PII-Shield style) as an additional backstop.
- **Unblock-trigger:** (a) is ready now; (b)/(c) when remote sandboxes,
  multi-tenant use, or a compromised-proxy threat model land.

## I-25 — Externally configurable provider sampling parameters

- **Status:** deferred from the Docker/config review (2026-06-19).
- **Problem:** `~/.fa/models.yaml` configures ONLY routing — `provider`, `slug`,
  `base_url`, `api_key_env` (+ optional `cooldown_seconds`, `transport_retries`,
  `timeout_seconds`, `extra_headers`). The chain-entry parser
  (`src/fa/providers/chain.py` `chain_from_mapping`) reads no other keys, so any
  sampling field an operator adds to a chain entry (`temperature`, `top_p`,
  `top_k`, `min_p`, `max_tokens`, `presence_penalty`, `frequency_penalty`, …) is
  **silently ignored** — no error, no warning. The request body is built in
  `src/fa/inner_loop/coder_loop.py` and only ever sends `model`, `messages`,
  `temperature`, `max_tokens`, `tools`. Defaults are **hardcoded** in code:
  `DEFAULT_TEMPERATURE`, `DEFAULT_MAX_TOKENS` (coder loop) and a separate
  Anthropic-adapter `max_tokens` fallback. An operator cannot tune sampling per
  role/model from config — only by editing source.
- **Idea (three parts):**
  1. **Investigate main providers' HTTP API payloads.** Catalogue the chat/
     completions request schema for each registered provider
     (`src/fa/providers/registry.py`: openrouter, fireworks, nvidia_build, groq,
     github_models, modal, together_ai, lambda_labs, cerebras, perplexity, xai,
     anthropic). Note which sampling params each accepts, their ranges/defaults,
     and OpenAI-compat vs Anthropic shape differences (e.g. Anthropic requires
     `max_tokens`; `top_k`/`min_p` are non-OpenAI extensions).
  2. **Make all sampling params externally configurable, not hardcoded** —
     requires a code audit of every hardcoded default. Plumb a per-role (and/or
     per-chain-entry) `sampling:` block from `models.yaml` → `ChainEntry` /
     `ChainConfig` → `RequestInfo` → the adapter request body. Decide precedence
     (per-entry overrides per-role overrides code default) and where unknown/
     unsupported-for-provider keys are validated vs passed through `extras`.
  3. **Stop silently ignoring sampling keys.** Until full plumbing lands, the
     loader should at minimum WARN when a chain entry carries a key it does not
     consume, so a mis-set `temperature:` in `models.yaml` is visible instead of
     a silent no-op.
- **Blocked-on:** the provider-payload catalogue from part (1) — without it the
  schema for a `sampling:` block (which keys are universal vs provider-specific)
  cannot be designed.
- **Unblock-trigger:** a request-shape audit note lands enumerating, per
  provider, the accepted sampling params and their validation rules.
- **First concrete step once unblocked:** add an optional per-entry `sampling:`
  mapping to `chain_from_mapping` (passed through to `RequestInfo.extras` for
  OpenAI-compat providers), plus the loader WARN for unknown keys (part 3), with
  tests proving a configured `temperature`/`max_tokens` reaches the request body.
- **Why this satisfies minimalism-first.** It removes a silent-failure footgun
  (config keys that do nothing) and replaces three scattered hardcoded constants
  with one declared, auditable surface; no new dependency.
- **References:**
  - `src/fa/providers/chain.py` `chain_from_mapping` / `ChainEntry` — the keys
    actually parsed today.
  - `src/fa/inner_loop/coder_loop.py` `DEFAULT_TEMPERATURE` / `DEFAULT_MAX_TOKENS`
    + `RequestInfo(...)` construction — the hardcoded request body.
  - `src/fa/providers/openai_compat.py` / `src/fa/providers/anthropic.py` — the
    two request-body builders (note the separate Anthropic `max_tokens` default).
  - `knowledge/templates/models.yaml.example` — documents the routing-only shape.

## I-26 — `fa probe --all-entries` (full chain walk)

`fa probe` stops at the first successful chain entry (matching production
behaviour). `--all-entries` would test every entry even after one succeeds —
useful for pre-deployment validation ("are all my fallbacks alive?").
One-day scope: bypass `ProviderChain.request()` and walk entries directly
with per-entry reporting.

## I-27 — `fa help` progressive disclosure

## I-28 — Coverage ratchet: restore fail_under=90

`fail_under` temporarily lowered from 90 → 89 (2026-06-21) because
`cli.py` is 78% covered — the runtime paths in `_cmd_run`,
`_cmd_egress_proxy`, and `_cmd_selfcheck` lack unit tests (they require
a running proxy or complex mocking). Current total: 89.72%. Need ~16
more covered lines in `cli.py` to restore 90. Candidate: test the
`_cmd_probe` proxy-mode success path with a fake proxy server (same
pattern as `test_selfcheck_cli.py`'s `_proxy_server` context manager).

Project-centric help surface. `fa help` shows available subcommands with
one-line descriptions and usage examples tailored to the FA project.
Optionally: `fa help <subcommand>` shows detailed help with common patterns.
Low priority — argparse `--help` works today; this is UX polish.

## I-29 — Live output Phase 2: JsonLineWriter + config.yaml

Add `JsonLineWriter` listener (NDJSON to stdout for WebUI/pipes).
Add `output:` section to `~/.fa/config.yaml` (mode, detail, color,
show_cost, show_context_pct, show_reasoning). WebUI buttons control
these settings. Foundation already landed in I-29-prerequisite
(EventBus + ConsoleRenderer).

## I-30 — `fa replay` command

Re-render a past session from `~/.fa/session-log/<run_id>/events.jsonl`
through ConsoleRenderer. Read JSONL → emit as OutputEvent → render.
Prerequisite: I-29 (JsonLineWriter) or direct JSONL→OutputEvent
adapter.

## I-31 — `fa stats` aggregate dashboard

Read all `~/.fa/session-log/*/events.jsonl`, aggregate: total cost,
tokens, cache hit ratio, model distribution, p50/p95 latency.
`fa stats --since 7d`.

## I-32 — Multi-key rotation per `(provider, slug)` (quota resilience)

**Origin:** discovered 2026-07-23 via a real operator `models.yaml` that
declared 3 chain entries for `coder` — same `provider: mistral`, same
`slug: mistral-small-2603`, same `base_url`, but 3 *different*
`api_key_env` names (`MISTRAL_API_KEY` / `MISTRAL_API_KEY_1` /
`MISTRAL_API_KEY_2`). The intent (confirmed with the operator) was
key-rotation / quota-pooling across several API keys for the *same*
provider+model, to survive a single key's rate limit. This does not work
today, in either deployment mode:

- **Egress-proxy mode (ADR-12, the shipped deploy topology):**
  `fa.egress_proxy.routing.build_route_table` computes ONE route name per
  `(provider, slug)` pair (`route_name_for`), and a `RouteTable` can bind
  exactly one `api_key_env` per route name. Multiple entries sharing
  `(provider, slug)` with different `api_key_env` values collide and
  `build_route_table` correctly raises `ProxyConfigError` (fail-closed,
  not a bug — a route cannot inject two different keys). Reproduced via
  `fa routing-check` (see `src/fa/providers/routing_lint.py`, shipped
  2026-07-23) and directly via `build_route_table`.
- **Direct (non-proxy) mode:** even without the proxy, `ProviderChain`'s
  cooldown ledger (`src/fa/providers/chain.py::ProviderChain._cooldowns`,
  keyed on `(provider, slug)` per ADR-9 §3) means a transient failure
  (e.g. 429 rate-limit) on the FIRST entry cools down the *whole*
  `(provider, slug)` tuple — the second and third entries (different keys,
  otherwise healthy) are never attempted for that request. Reproduced via
  a fake-provider unit test: 3 identical-`(provider,slug)` entries with
  distinct keys, first entry raises `ProviderTransientError`, chain
  exhausts after exactly 1 attempt instead of trying the other 2 keys.

**What "make it work" requires** (not attempted yet — scoping only):

- A route/cooldown identity that includes the *credential*, not just
  `(provider, slug)` — e.g. `(provider, slug, api_key_env)` — so distinct
  keys for the same model are independently routable and independently
  cooled down. This touches:
  - `fa.egress_proxy.routing.route_name_for` / `RouteTable` (proxy mode);
  - `ProviderChain._cooldowns` keying (`src/fa/providers/chain.py`);
  - `fa.providers.routing_lint`'s conflict/near-miss checks (would need
    to stop treating same-`(provider,slug)`-different-`api_key_env` as
    a hard conflict once rotation is a supported shape, and instead
    validate it as a *legitimate* rotation chain).
- A decision on selection policy: round-robin, random, or "first not in
  cooldown" (matching the existing ordered-fallback semantics, just with
  a wider identity key) — needs its own ADR-9 amendment, not a silent
  behavior change.
- `fa selfcheck` / `fa probe` currently assume one key per route in their
  reporting shape; would need updating to report per-key health within a
  rotation group.

**Unblock-trigger:** an operator actually hits a persistent single-key
quota ceiling in production (this is currently a "nice to have" per the
reporting operator, not an active blocker) — implement then, with the
ADR-9 amendment written first so the selection-policy decision doesn't
get made implicitly by whichever PR happens to touch `chain.py` first.

## I-33 — LLM-call cost accounting: three disconnected, unfinished stubs

**Origin:** discovered 2026-07-24 during a code-review sweep prompted by the
`models.yaml` schema amendment (I-32's neighbor) — the reviewer asked
whether `src/fa/observability/cost_table.py` was redundant with something
else that already computes LLM-call cost. It is not: there are three
INDEPENDENT, mutually-unaware stubs, none of which produce a real dollar
figure anywhere in the runtime today. Not a priority now (operator: "not
sure if I need it, maybe later for evals") — recorded so a future session
doesn't rediscover this from scratch or add a 4th disconnected stub.

1. **`src/fa/observability/cost_table.py`** — a `(family, provider, slug) ->
   CostPerMillion` pricing lookup table with real seed data (9 rows) and a
   working `lookup()` function. **Zero production callers** (`grep -rn
   "cost_table.lookup\|from fa.observability.cost_table" src/fa/` returns
   nothing outside the module itself). Its own docstring claims it feeds an
   ADR-9 §4 `"llm_call"` Tier-1 observability row — that `LogKind`/`OutputEvent`
   kind was never implemented anywhere (`grep -rn 'kind="llm_call"'
   src/fa/` returns zero hits); the shipped observability schema uses
   `provider_attempt` / `usage` / `session_summary` kinds instead, none of
   which carry a cost field. The lookup table's keys are also now stale
   relative to the ADR-9 §Amendment 2026-07-23 schema (they use the old
   example `slug` strings like `"deepseek/deepseek-chat-v3"`, which is a
   value shape that still exists post-amendment as `ChainEntry.model`, but
   the table itself is unreachable regardless).

2. **`TelemetryEvent.cost_usd`** (`src/fa/telemetry/telemetry.py`) — a
   per-TOOL-CALL telemetry dataclass field (different granularity than
   per-LLM-call). Its only producer, `src/fa/inner_loop/state.py:570-576`,
   hardcodes `cost_usd=0.0` and `model_id=""` unconditionally on every
   construction — never actually computed from a real response or looked up
   from a pricing table. `TelemetryLogger` writes these zeros faithfully to
   `.fa/telemetry/telemetry.jsonl`.

3. **`OutputEvent.data["est_cost_usd"]`** — has a live CONSUMER
   (`src/fa/output.py:329-330`, gated behind `self.show_cost`, renders
   `~$0.0042` in the CLI's live turn-by-turn output) but **zero producers**
   anywhere (`grep -rn 'est_cost_usd' src/fa/` finds only the consumer line).
   This is the project's own named "dead handler, no producer emit()"
   anti-pattern (the shape `scripts/check_producer_consumer_contract.py`
   exists to catch) — it slipped past that automated gate because the key
   lives inside an untyped `OutputEvent.data: dict`, not a top-level typed
   `EventType` member the gate enumerates. `self.show_cost` can be enabled
   today and will silently render nothing (the `if ... is not None` guard
   means the line never appears, not that it errors) — a config-shaped
   footgun for an operator who turns the flag on expecting a cost readout.

**First concrete step whenever this is picked up:** decide the target
granularity FIRST (per-LLM-call, matching `cost_table.py`'s `(family,
provider, slug)` key shape and ADR-9 §4's original design intent, is
probably right for a cost-budget/eval use case — per-tool-call granularity
in `TelemetryEvent` answers a different question and should likely stay
separate, not be conflated). Then either wire `cost_table.lookup()` into
`ProviderChain.request()`'s success path (using `entry.model` /
`self._config.family` / `entry.provider` as the lookup key under the
current, amended schema) and thread the result into a genuinely emitted
`OutputEvent.data["est_cost_usd"]` — closing gap 3 — or delete all three
stubs if a different design is chosen. Do not add a fourth partial
implementation without first reading this entry.

**Unblock-trigger:** cost/budget accounting becomes a requirement for an
eval harness or a per-session spend cap (operator's own stated "maybe later
for evals" framing).

## I-34 — Subagent containment: OS-level writable-mount boundary (Q19 / V24+V25)

**Origin:** raised 2026-07-28 by the S5.6 preflight
([`PLAN-cli-trace-S5-authority-correctness.md`](../worklogs/implementation-plans/PLAN-cli-trace-S5-authority-correctness.md)
§11 Q19); re-confirmed 2026-07-29 during the S5 post-merge review, which found
it was tracked **only** in plans and PR notes — i.e. nowhere a future session
would look. This entry exists so an open *security* boundary cannot be lost
when its plan is archived.

**The gap, measured (not inferred).** The Q11-B enforcement mechanism does not
enforce. `SandboxHook` was pointed at the subagent artifact root and the runner
`cwd` moved to match; both were then measured **not to contain anything**:

- `workspace_root` is consulted only by the `rm` / `chmod` / `git` validators,
  so a shell redirect (`echo x > /outside/path`) classifies as `GENERAL_WRITE`
  and passes unchecked under *either* root;
- `cwd` is not a boundary — the subagent runs a real shell and can use absolute
  paths.

Denying `GENERAL_WRITE` for spawns *was* implemented and measured to deny
**8 of 10** realistic verifier commands (`pytest`, `mypy`, `make test`), so it
was reverted: it trades a security hole for an unusable feature.

**Why this is not "just" a missing test.** ADR-12's conclusion applies —
lexical filters are best-effort, not boundaries. Real containment needs an
OS-level writable-mount boundary (Q19 option (c)): a mount namespace or
read-only bind with a single writable artifact dir, the same shape the ADR-12
egress proxy uses for keys.

**Executable record.** `tests/test_s5_isolation_boundary.py::test_subagent_write_outside_artifact_root_denied`
is a **strict `xfail`** whose message carries the evidence above. It should
start **passing** when containment lands — that is the acceptance signal;
delete nothing.

**Related:** S7 Q29 (empty `session_id` as an "unscoped" sentinel) touches the
same subagent/session isolation surface.

## I-35 — `SessionDatabase` first-create is not concurrency-safe (DEFERRED DDL)

**Origin:** found 2026-07-29 by the S5 post-merge review (§13.4), following up
S5 §12 R3-2 — which recorded that all six write paths use bare `with conn:`
(DEFERRED) but was only acted on for one of them.

**Measured.** Of the five remaining paths, four are **write-only**
(`write_blackboard_row`, `append_event_row`, `set_meta`,
`reserve_run_binding`) and therefore safe — 6 processes × 5 writes gave
**30 attempted / 30 persisted / 0 lost**. Two do a read→write upgrade inside a
DEFERRED transaction, which SQLite answers with `SQLITE_BUSY` *without*
honouring `busy_timeout`:

- `_ensure_identity` (`session_db.py:303`);
- `_init_current_schema` (`:262`) — the actual failure site.

Concurrent **first-create** of a fresh DB: **6 of 30 opens** raise
`session_db_init_failed: database is locked`. Once the DB exists, concurrent
opens are clean: **0 of 40**.

**Severity: P3, deliberately.** Production does not reach the window.
`SessionManager._new_session` serialises creation with
`session_dir.mkdir(parents=True, exist_ok=False)` (`manager.py:252`), an atomic
filesystem primitive — exactly one process can create a session namespace. The
exposure is limited to the three sites that build a DB **without** that
serializer: `blackboard.py:207`, `state.py:176`,
`tools/observability.py:72`.

**Do not fix by patching `_ensure_identity` alone.** That was prototyped during
the review and reverted: it moved failures 6→3, proving `_ensure_identity` is a
symptom and the DDL path is the source. The fix belongs with **S7 Q29**, which
already proposes auditing those same three unserialised construction sites —
resolve them together, with a multiprocess barrier test as the oracle
(threads alone cannot falsify this; see S5 §12 R3-3).

## I-36 — RESOLVED 2026-08-01 (S10c.3) — artifact permissions

**Resolution.** Every artifact a run writes under `~/.fa` is now created
`0600`, every directory `0700`, and an existing over-permissive tree is
repaired.

**The entry's scope was too narrow — measured.** It named bodies and events; a
real run left **four** world-readable files. The missing one was
`sessions/<sid>/session.db`, which stores full event `content`
(`session_db.py:185`) — the same prose that makes `llm_bodies.jsonl` opt-in.
Fixing the JSONL files alone would have closed the documented hole and left the
larger one open.

**The entry's prescribed fix does not compile.** It specified
`Path.open(..., opener=...)`; `pathlib` rejects `opener` with `TypeError`
(verified on 3.13, and mypy reports it as `call-overload`). The builtin
`open()` accepts it. A test asserts the `TypeError` so the wrong shape cannot
come back.

Mechanisms: `private_opener` (`fa/paths.py`) for JSONL appends; an
`os.open(..., 0o600)` pre-create inside `create_sqlite_connection` for both
databases — one site, and the WAL `-wal`/`-shm` sidecars inherit the mode.
Both set the mode in the syscall, so there is no chmod window.

**Retroactive half (Q56, operator).** `tighten_fa_artifact_modes()` repairs an
existing tree once per run. Three properties are load-bearing, each with a
test: symlinks are **skipped** (`os.chmod` follows them and
`follow_symlinks=False` raises `NotImplementedError` on Linux, so a crafted
link inside `~/.fa` would otherwise have its *target* rewritten); directories
get `0700`, not `0600`, or the state root becomes untraversable; and the pass
tightens only, so a deliberate `0400` survives.

Pinned by `tests/test_s10c_artifact_posture.py` (13 tests). The headline one is
a **whole-tree sweep** rather than named files, because a fixed list is how the
`session.db` omission happened in the first place.

---

**Original report — Tier-3 `llm_bodies.jsonl` is world-readable (0644) while the session manifest is 0600**

**Found:** S7.C4 step 4d, on the live container, 2026-07-30.

Measured in the deployment (`umask 0022`):

```text
644 fa:fa /home/fa/.fa/session-log/s7-run-b/llm_bodies.jsonl
755 fa:fa /home/fa/.fa/session-log/s7-run-b
600 fa:fa /home/fa/.fa/sessions/<sid>/manifest.json
```

`DebugBodyTransport._write` (`providers/debug_bodies.py:167`) opens the file
with a plain `self._path.open("a", ...)`, so the mode is whatever `0666 & ~umask`
yields — `0644` here. `SessionManager._atomic_write_json` deliberately does
`os.chmod(temp_path, 0o600)` (`session/manager.py:133`) for the manifest.

**Why it matters.** The module's own docstring says bodies "may carry
UC5-sensitive context". `SecretRedactor` masks *known key values* — it does not
and cannot mask prompt or response prose, which is exactly what these files are
for. So the most sensitive artifact the system writes is the most permissive
one. On the current single-user container the practical exposure is nil; it
matters for multi-tenant hosts, for shared CI runners, and for any `docker cp`
or volume snapshot that carries the directory somewhere with other readers.

**The same applies to `events.jsonl`** — measured `0644` locally. Tier-1 content
is redacted per ADR-7, so the severity is lower, but the two writers should not
disagree about the policy.

**Fix shape (do not paper over with `chmod` after the fact — there is a window
between create and chmod where the file is readable):** pass an `opener` to
`Path.open`, which is the stdlib-supported way to set creation mode:

```python
def _private_opener(path: str, flags: int) -> int:
    return os.open(path, flags, 0o600)


with self._path.open("a", encoding="utf-8", opener=_private_opener) as handle:
    ...
```

Verified locally: `open(..., "a")` under `umask 0022` gives `0o644`; the
`os.open(..., 0o600)` opener gives `0o600` with no window. Directory creation
should likewise use `mkdir(mode=0o700)`.

**Severity: P2.** Not a correctness bug and not exploitable in the current
single-user deployment, but it is a security-posture defect in the exact
subsystem whose reason for existing is "this data is sensitive, so it is
opt-in". Should be fixed before any multi-tenant or shared-host deployment.

**Scope when picked up:** `providers/debug_bodies.py` (bodies),
`inner_loop/state.py` (`events.jsonl`), and the run-dir `mkdir` in
`session/manager.py:398`. Needs a test asserting `stat.S_IMODE(...) == 0o600`
on a real written file — a mode assertion is trivially falsifiable and belongs
in the C2 producer class.

---

## I-37 — Tool schemas are sent to the provider twice in every request (~43% of request bytes)

**Found:** while explaining the 58 KB body file recorded in S7.C4, 2026-07-30.
Measured from a real captured `llm_bodies.jsonl` row for a one-word task.

A single `pong` request decomposes as:

```text
total request bytes : 28,531   (58,095 on the container with its live tool set)
  base system prompt:  5,924  (21%)
  INLINE tool json  : 12,130  (43%)   <- system message #2
  NATIVE tools array:  8,762  (31%)   <- OpenAI `tools` parameter
  actual task       :     16  (0.06%)
```

The **same 16 tool schemas are transmitted twice**: once JSON-dumped with
`indent=2` into a system message by
`prompt_composer.build_prompt_parts_v2` (`prompt_composer.py:98`), and once as
the provider-native `tools` array via `RequestInfo(tools=tool_payload)`
(`coder_loop.py:1124`). Both derive from the same `render_tool_specs(...)`
result (`coder_loop.py:409-410`) — `tool_defs_for_prompt` is literally a copy
of `tool_payload`. Together they are **73% of the request**.

The inline copy is also the *more expensive* of the two at 12,130 vs 8,762
bytes, because `indent=2` pretty-printing inflates it ~38%.

**Is the duplication deliberate?** Nothing in the source says so. The docstring
for `build_prompt_parts_v2` describes the tool block only as a cacheable part;
there is no comment claiming the inline listing improves tool-selection
accuracy. Some 2023-era prompting practice did restate tools in the system
prompt for models with weak native tool support — if that is the reason, it
should be a documented, per-model decision, not an unconditional default.

**Why it is not free even with prompt caching.** The container run showed
`cache=100%` on the third call, so a warm cache does absorb much of the cost.
But: (a) the first call of every session pays full price; (b) cache hits are
still billed, typically at ~10% of input rate, so 43% waste becomes ~4.3%
permanent waste; (c) it consumes context window — the run reported "Context: 9%
of window" for a one-word task; (d) `_hash_tool_defs_stable` excludes
`description` from the cache key precisely because descriptions contain dates,
so a description change silently invalidates nothing while still shipping new
bytes.

**Do not "just delete the inline block".** That is a behavior change to prompt
composition and must be measured, not assumed:

1. Add an A/B under the existing `FeatureFlags` mechanism
   (`prompt.inline_tool_listing`, default ON to preserve current behavior).
2. Measure tool-selection accuracy on the eval corpus with it OFF.
3. If accuracy holds, flip the default and delete the branch.
4. Independently, if the block is kept, drop `indent=2` — that is a pure
   ~38% saving on that block with zero semantic change.

> **PARTIALLY RESOLVED 2026-08-01 (S10c.5) — option 4 shipped.** The
> `indent=2` pretty-printing is gone: measured **10,619 → 7,471 bytes**, a
> **29.6% saving on every request**, whitespace-only. (This entry estimated
> ~38%; re-measured directly against the 15-tool baseline registry.) The
> `AlwaysSkills` / `ConditionalSkills` blocks keep `indent=2` deliberately —
> separate measurement, not covered by this item.
>
> **Options 1-3 remain OPEN**: deleting the inline listing still needs the
> `FeatureFlags` A/B on the eval corpus. Note this entry's own container
> measurement — the `AGENTS.md` map is **48.4%** of a live request versus this
> block's 21% — so *"fixing 21% while ignoring 48% is backwards"* still stands.

**Severity: P2**, cost/performance rather than correctness. Worth doing: it is
one of the few changes that reduces spend on *every single call* the system
makes.

**Related:** I-33 (cost accounting stubs) — I-37 is the kind of regression that
proper per-call cost accounting would have surfaced automatically.

### Container measurement (S7.C4b, 2026-07-30) — the live picture is worse

The local capture above used an empty `AGENTS.md` map. On the real deployment
(`mistral-small-2603`, live pinned buffer) the same one-word task is **57,853
bytes**:

```text
  [0] system  base prompt      :  5,924  10.2%
  [1] system  AGENTS.md map    : 28,015  48.4%   <- largest single component
  [2] system  INLINE tool json : 12,130  21.0%
  [3] user    the actual task  :     38   0.1%
      native tools array       :  8,762  15.1%
      tool schemas sent TWICE  : 20,892  36%
```

Two corrections to the local estimate:

1. The duplicated tool schemas are **36% of the live request**, not 43% — the
   share fell only because a much larger `AGENTS.md` map diluted it. The
   absolute waste (12,130 bytes/call) is **identical**; it is a fixed cost.
> **RE-MEASURED LIVE 2026-08-04 (S11.8c), post-S10c.5, on the deployed box.**
> A real `fa run` request, `mistral-small-2603`, 16 tools:
>
> | component | bytes | share |
> |---|---:|---:|
> | **`AGENTS.md` map** | **28,665** | **55.4%** |
> | `Tools for role` (system text) | 8,396 | 16.2% |
> | native `tools` array | 8,762 | 16.9% |
> | base system prompt | 5,924 | 11.4% |
> | **the actual task** | **38** | **0.1%** |
> | total | 51,785 | |
>
> Two updates to the record. **(a)** The map has **grown**: 48.4% → **55.4%**.
> **(b)** The tool-schema duplication is confirmed *at source*, not inferred:
> `coder_loop.py:408` builds `tool_payload` once, `:409` renders it into system
> text and `:1124` passes the same object as the native `tools=` array — one
> source, two wire encodings, **33.1% combined**, every request.
>
> S10c.5 shipped and is vindicated (inline block 10,619 → 7,471 B); today's
> 8,396 B reflects registry growth to 16 tools. But it optimised the 16% while
> the 55% grew — the *"fixing 21% while ignoring 48% is backwards"* note in this
> item, now with harder numbers. **0.1% of a 51.8 KB request is the work.**

2. **The `AGENTS.md` map is now the single biggest component at 48.4%**, and it
   is *larger than `AGENTS.md` itself* (28,015 vs 17,127 bytes on disk). The
   pinned buffer is assembling more than one document into that slot. Nobody
   has ever measured what goes in there. Worth a follow-up of its own before
   anyone optimises the tool block: fixing 21% while ignoring 48% is
   backwards.

**Combined:** 84.5% of every live request is standing context. The task itself
is 0.1%.

---

## I-38 — RESOLVED 2026-07-30 (S8.4) — `--output-mode quiet` stdout contract

**Found:** S7.C5 on the live container, 2026-07-30.

`QuietRenderer`'s docstring (`output.py:449`) states the contract as:

> *nothing on **stdout** — so `fa run --task ... > result.txt` stays parseable,
> which is the reason the mode exists*

Measured on the deployment: **stdout 34 bytes, stderr 0 bytes.** Reconstructed
exactly from source — `cli.py:2212` prints `OK: stopped_by_llm (turns=1)\n`
(29 bytes) unconditionally, then `cli.py:2214` prints `outcome.final_text`
(`pong\n`, 5 bytes). 29 + 5 = 34. Exact match, no ambiguity about what wrote
those bytes.

**The renderer honours its contract; the command does not.** `QuietRenderer.on_event`
really is a `pass`, and `tests/test_s6_renderers.py:149` proves it for every
`EventType`. But those two `print()` calls in `_cmd_run` sit *outside* the
`EventBus` entirely, so no renderer-level test can see them — which is exactly
why a local unit suite passed while the live behaviour contradicts the
docstring.

**Why it is not cosmetic.** The stated purpose of the mode is that
`fa run ... > result.txt` yields a parseable artifact. It does not: the file
gets a human status line prepended to the payload. Any caller doing
`result = subprocess.check_output(...)` gets `"OK: stopped_by_llm (turns=1)\npong"`
and must strip a line whose format is undocumented and unversioned. The
docstring's own justification is falsified by the shipped behaviour.

**This is a policy fork, not a bug with an obvious fix.** Promote to a Q# before
touching it. The options:

- **(a)** Quiet means *only* `final_text` on stdout; status line moves to
  stderr. Best matches the docstring and normal Unix practice (data on stdout,
  status on stderr). Changes observable output for anyone parsing today.
- **(b)** Keep the behaviour, fix the docstring to say "quiet suppresses the
  live renderer; the status line and final text still go to stdout." Zero risk,
  but concedes that `> result.txt` is not clean.
- **(c)** Add `--output-mode raw` for payload-only, leave `quiet` as-is.
  Additive and safe; grows the surface.

Recommend **(a)**, with a C2 test asserting stdout is byte-identical to
`final_text` under quiet. It is the only option that makes the docstring true.

**Severity: P2.** Contract/documentation mismatch on a mode whose entire reason
for existing is machine-parseable output.

### RESOLVED — S8.4, 2026-07-30

Adopted **option (a), scoped to `quiet`** (operator decision, S8 plan Q32:
*"quiet mode outputs less info per turn, all info is processed as usual"*).

* Under `--output-mode quiet`, `_cmd_run`'s status line goes to **stderr** and
  stdout is byte-exactly `outcome.final_text`.
* Default `console` output is **unchanged** — the change is mode-scoped, not
  unconditional, so no existing console user is affected.
* `fa workflow` gained `--output-mode` and forwards it to every stage (this is
  where the defect compounded: 102 bytes across three stages).
* `QuietRenderer`'s docstring corrected in the same commit, and now states the
  contract the CLI actually keeps.
* Durable equivalence asserted: DB rows, workflow artifacts and the
  `global_history` row are identical in both modes.

Kill-checks bite in **both** directions (force-stdout fails the quiet tests;
force-stderr fails the console tests), which is what pins a conditional rather
than a constant.

---

## I-39 — RESOLVED 2026-08-01 (S10c.4 / Q55) — composer extras are no longer dropped *silently*

**Resolution.** The drop remains; the **silence** does not — which was the
actual complaint ("a key the composer invents and an adapter silently drops is
invisible to every existing check").

**Q55 (operator): Mistral is a temporary test provider, best-effort only.** So
the key was neither added to the recognised set (that would claim API support
nobody verified) nor removed from the composer (it works on
openai-compatible routes, asserted in `test_providers_openai_compat.py:139`).
It is recorded in a reviewed `_KNOWN_UNRECOGNISED` allow-list that a contract
test asserts, keeping the gate binary: a *second*, unplanned silent drop still
fails.

`COMPOSER_EXTRA_BODY_KEYS` is exported from `prompt_composer` so the test
compares constants instead of scraping source, and a companion test asserts the
constant equals what the function actually emits — otherwise the contract would
validate a fiction.

**The gate found a third instance on its first run.** This entry documented
`mistral`; `mistral_agents` has the identical gap (recognises
`prompt_cache_key`, not `prompt_cache_retention`), verified against
`MISTRAL_CONVERSATIONS_RECOGNIZED_PROVIDER_PARAMS_KEYS` rather than assumed
from the family name. A further test asserts every allow-list row still
describes a *real* mismatch, so a row cannot outlive its reason.

Pinned by `tests/test_s10c_composer_extras_contract.py`.

---

**Original report — `prompt_cache_retention` is silently dropped for every Mistral route**

**Found:** while reading the S7.C4b container output, 2026-07-30.

`prompt_composer.to_openai_request_v2` (`prompt_composer.py:188`)
unconditionally emits `extra_body = {"prompt_cache_key": ..., "prompt_cache_retention": "1h"}`.
The container body shows `prompt_cache_key` **present** and
`prompt_cache_retention` **absent**.

Confirmed by direct call, not inference — `_build_request_body` with both keys
in `extras` returns a body containing `prompt_cache_key` and not
`prompt_cache_retention`. Cause: `MISTRAL_RECOGNIZED_PROVIDER_PARAMS_KEYS`
(`mistral.py:77`) lists 7 keys and `prompt_cache_retention` is not among them,
so the `if key not in ...: continue` filter drops it. `openai_compat` does pass
it through (`tests/test_providers_openai_compat.py:139` asserts so).

So the retention hint reaches OpenAI-compatible routes and never reaches
Mistral routes. The system asks for 1-hour cache retention and, on the route it
actually runs in production, gets provider-default retention instead.

**The existing test documents the drop without justifying it.**
`tests/test_mistral_provider.py:626` asserts `"prompt_cache_retention" not in body`
with the docstring *"Unrecognized extras ... are filtered out."* That pins the
filter's mechanics, but nowhere is it recorded whether Mistral genuinely
rejects the field or whether it was simply never added to the set. Those need
different fixes and the test cannot tell them apart.

**Also a gap in the routing lint.** `routing_lint.py` check 3 flags unknown
`provider_params` keys from `models.yaml` — good — but composer-injected
`extras` never pass through that lint. A key the composer invents and an
adapter silently drops is invisible to every existing check.

**Action:** confirm against Mistral's current API docs whether
`prompt_cache_retention` is supported. If yes, add it to the recognised set. If
no, stop emitting it for Mistral routes rather than emitting-then-dropping, and
say so in the composer. Either way, extend the lint (or add a startup
assertion) so composer-emitted extras are checked against the destination
adapter's recognised set.

**Severity: P3.** Cost/performance only; no correctness impact. Cheap to fix.



---

## I-40 — RESOLVED 2026-08-01 (S10c.1) — the config gate fails when it cannot validate

**Resolution, both halves.**

*Missing config.* `_cmd_routing_check` now stats the path and exits **2**
naming it. `scripts/fa-clean-rebuild.sh:471` therefore aborts instead of
logging "Routing lint: OK" on a typo. The loader's missing-file policy is
**unchanged** — it is documented and correct for other callers
(`config.py:323-326`, "caller decides if absence is fatal"); the command is the
caller that has decided absence is fatal. An empty-but-present config still
exits 0, which is a legitimately clean state.

*Unparseable YAML — wider than this entry recorded.* Executing each command
showed **five** leaked a raw traceback: `routing-check`, `run`, `selfcheck`,
`probe` and `egress-proxy` (the last loads this config at **container start**).
Fixed once at the single `yaml.safe_load` in `load_models_config`, which
converts `yaml.YAMLError` to `ConfigurationError` — the exception every one of
those callers already handles, and the same one raised two lines below for a
bad root type. All 19 `load_models_config*` call sites inherit it; adding the
exception to five `except` tuples would have fixed the ones an author
remembered.

Two pinned tests were **inverted**, each with a docstring recording why —
including S10b's parity cell, whose own docstring predicted it: *"this test
INVERTS when I-40 is fixed — that is its purpose."*

Pinned by `tests/test_s10c_config_error_contract.py` (all five commands get
their own test, plus a C0p on the loader so a command regression is
distinguishable from a loader regression).

---

**Original report — `fa routing-check` passes green on a config path that does not exist**

**Found:** S10a.2, 2026-07-31, by a test written to assert exit 2 that failed.

`fa routing-check --config /path/that/does/not/exist` returns **0** and prints
`WARNING: no roles declared; nothing to check.`

Cause: `load_models_config_from_path` returns an empty `roles` mapping for a
missing file rather than raising, so `_cmd_routing_check` takes its
"no roles declared" branch (`cli.py`) and reports success.

**Why this is not cosmetic.** `scripts/fa-clean-rebuild.sh:471` runs this
command as a **pre-build deploy gate**:

```bash
if uv run --project "${REPO_DIR}" fa routing-check --config "${ROUTING_MODELS_FILE}"; then
    log_info "Routing lint: OK."
else
    log_error "... Aborting before build."
```

A typo in `ROUTING_MODELS_FILE` therefore logs **"Routing lint: OK"** and
proceeds to build, having validated nothing. The command's own docstring calls
it a gate that "fails in well under a second, before a Docker image build" —
which is exactly what does not happen.

**Second, smaller defect in the same handler.** `_cmd_routing_check` catches
`(ConfigurationError, EvalFamilyConflictError, OSError)`. **Unparseable YAML
raises `yaml.ParserError`**, which is none of those, so a syntactically broken
`models.yaml` escapes as an unhandled traceback instead of the structured
`ERROR: models config error` the command promises. Measured.

**Fix shape.** Distinguish *absent* from *empty*: stat the path first and
return **2** with a structured message when it does not exist, keeping 0 for a
genuinely empty-but-present config. Add `yaml.YAMLError` to the caught tuple.
Both are one-line changes, but both alter an operator-visible exit code, so
they belong in a slice that owns the CLI contract — **not** in a coverage
slice.

**Severity: P2.** Silent failure of a deploy gate. Today's behaviour is pinned
by `test_s10a_routing_check_missing_config_reports_no_roles` so the eventual
fix is a visible diff rather than drift.

---

## I-41 — RESOLVED 2026-08-01 (S10b.3 / Q53) — `fa stats` renderers bound `sys.stderr` at import time

**Resolution.** `render_session` / `render_aggregate` now take
`stream: TextIO | None = None` and resolve `sys.stderr` **inside the body**, so
the current stream is used on every call. Confirmed as a *live* defect while
writing the S10b.3 parity cells, not merely a smell: it surfaced as
`ValueError: I/O operation on closed file` (`stats.py:663`) when a renderer ran
after another test whose captured stderr had since been closed.

Fixing `.write` alone was insufficient — both functions also call
`stream.flush()`, which the first patch turned into `None.flush()`. The stream
is now resolved **once** into a local (`out`) so write and flush cannot
diverge. A repo-wide grep for `= sys.stderr` / `= sys.stdout` on `def` lines
confirms these were the only two sites in `src/fa`.

Pinned by three FIX-regression tests in `tests/test_s19_stats_parsers.py`
(`test_i41_*`), red before the fix, including a positive control asserting an
explicit `stream=` still wins — so a "fix" that ignored the argument and always
wrote to `sys.stderr` is also caught. Mutations verified: restoring the
import-time default fails the call-time test; ignoring the argument fails the
positive control.

---

**Original report — Found:** S10a.6, 2026-07-31, by a test that passed alone
and failed in the suite.

`fa.stats.render_session` and `render_aggregate` declare
`*, stream: TextIO = sys.stderr`. A default argument is evaluated **once, at
import**, so both functions write to whatever `sys.stderr` was bound to when
`fa.stats` was first imported — not to the current one.

**Symptom.** Under `pytest`, any test that runs after a test which replaced
`sys.stderr` gets `ValueError: I/O operation on closed file` from
`cli.py:2822`. Measured: `test_s10a_stats_console_render_and_dead_zones`
passes in isolation and fails in the full module.

**Why it is not only a test problem.** Any embedder that reassigns
`sys.stderr` — a TUI, a log-capture harness, a subprocess wrapper, `fa` running
inside another tool — silently loses the renderer's output or writes to a dead
handle. The CLI's own quiet/console stream contract (S8.4) assumes writes go to
the *current* stream.

**This is the third instance of one defect class in this codebase:**

| where | fixed by |
|---|---|
| `state.py` `DEFAULT_STATE_ROOT` | V10 — `default_state_root()` resolves at call time |
| `global_history.py` `DEFAULT_GLOBAL_HISTORY_PATH` | S8.8 — `default_global_history_path()` |
| **`stats.py` renderer `stream=` defaults** | **open (this item)** |

**Fix shape** (mirrors the two precedents): default to `None` and resolve
inside the body — `stream = stream if stream is not None else sys.stderr`.
Both call sites in `cli.py` already omit the argument, so nothing else changes.

**Severity: P3.** No production data is wrong; output can land on a stale
stream in embedded use. Deliberately **not** fixed in S10a — that slice's DoD
allows exactly one production edit (the `_cmd_probe` seam), and this is a
different module. The S10a test works around it by passing an explicit stream,
with a comment pointing here.

---

## I-55 — subagent capability is WIP/unfinished/untested: complete it before relying on it

- **Status:** open (assessed 2026-08-06). P2 — subagent is a declared feature with
  several unfinished/contradictory seams; it must be completed or explicitly
  scoped-down before it is treated as a production capability.
- **Assessment source:** verified by grep/read in the repo (not assumed).
  Subagent = `fa.inner_loop.subagent_runner` + `fa.inner_loop.tools.spawn_subagent` +
  `fa.inner_loop.subagent_envelope` + `fa.inner_loop.subagent_prompts`, plus the
  `researcher`/`verifier`/`code-reviewer`/`implementer`/`planner` role profiles in
  `profiles.py::PROFILES_RAW` and the `SubagentEnvelope.type` schema enum
  (`subagent_envelope.py:35`).
- **Why it is unfinished (verified):**
  1. **No per-role tool registry is ever built for a subagent.** `SubagentRunner.run_stateless`
     (`subagent_runner.py:302-343`) runs a raw `subprocess.run(command)` with a scrubbed env and
     **never constructs a `ToolRegistry`**. The `role` argument only sets the envelope `type`
     (`subagent_envelope.py:100`); it does **not** select a tool surface.
  2. **`build_registry_for_role("researcher")` is never called** anywhere in `src/`. Only
     `"implementer"` / `"planner"` / `"verifier"` are built (`tools/__init__.py:198,229,256`), and
     those feed the *main* loop (baseline/planner/eval registries), not subagents.
  3. **The `researcher` role is declared-but-unwired.** `PROFILES_RAW` defines `researcher`
     (`[glob,grep,read,instant_grep]`, 600-token profile, `profiles.py:39`), and `subagent_prompts.py:38`
     / `subagent_envelope.py:139` describe it as a "structured websearch agent." But no code path
     builds its registry or runs it as an LLM tool-user. Today `researcher` behaves like a bash/command
     subagent (same as verifier).
  4. **Docs overstate the blackboard-backed discovery.** AGENTS.md / llms.txt / reference.md instruct
     the agent to use `blackboard.query(...)` for artifact discovery (`type="skill"/"research"/"adr"`),
     but the blackboard only ever holds `type="file_version"` rows (writer = `mutation_guard.py:118,207`);
     no code writes skill/research/adr entries, and there is **no `rank` field** anywhere in
     `BlackboardEntry`/`Blackboard.query`/`session_db` (verified grep = zero). The subagent
     "researcher"/"websearch" capability that would consume such an index is therefore also unrealized.
- **Design intent (from docs):** `project-overview.md` §1.2.7 Pair-over-Autonomy + I-7.1..I-7.5:
  subagents are **cheap, deterministic, isolated puzzle-piece providers** (structured websearch,
  simple function) when main context is near limit (~180k). I-7.2: subagent task must be solvable with
  **<600 tokens tool defs** and **<8000 chars output**, returning structured JSON. I-7.3: stateless,
  scrubbed env, isolated via WorktreeManager. ADR-15 / I-6.3: simple chain planner→coder→eval is
  default; parallel subagents only when substrate is formal and the task is embarrassingly parallel
  with non-overlapping write_sets.
- **Known partial implementations / contradictions to resolve:**
  - `spawn_subagent` tool allows `role` ∈ `["verifier","researcher"]` (spawn_subagent.py:277) but only
    `run_stateless` (bash) exists — the `researcher` path is not implemented.
  - `subagent_envelope` mentions `from_researcher` (websearch) and `from_verifier` (bash); only
    `from_verifier` is wired into `run_stateless`.
  - The "filtered history" for a researcher subagent is logged but "would be injected as prompt" for
    future use (`subagent_runner.py:314-315`) — i.e. not actually used yet.
- **Unblock-trigger:** subagents become a required path — either (a) main context approaches the
  180k limit and needs a cheap isolated puzzle-piece (websearch/verification), or (b) an eval/benchmark
  task genuinely needs an isolated subagent and a simple chain is proven insufficient (I-7.4 / I-6.3).
- **First concrete step when picked up:** decide the minimal honest scope first —
  1. Either **finish the researcher path**: build a real per-role `ToolRegistry` for subagents (a
     `build_subagent_registry(role)` that constructs `[glob,grep,read,instant_grep]` for `researcher`,
     `[bash]` for `verifier`) and run the subagent as a real drive_session-like loop with that registry,
     OR
  2. **narrow the claim**: rename/deprecate the unimplemented `researcher` websearch path so docs do not
     promise a capability that does not exist, and keep subagent = bash-only verifier for now.
  Then close the doc-reality gap (blackboard skill/research index + `rank` either built or the docs
  corrected to not assert them).
- **Do NOT** treat `build_registry_for_role("researcher")` as "dead code to delete" without this
  decision — it is the intended seam for a real researcher subagent, not garbage. But do NOT claim
  subagent researcher works until its registry + loop + index are built and tested.

---

## I-56 — blackboard is a WIP/unfinished capability (same class as subagent): complete it as the next slice

- **Status:** open (assessed 2026-08-06). P2 — the blackboard is a declared, SQLite-backed substrate
  feature that is only partially realized; completing it (the `fs_blackboard_query` tool + an actual
  artifact index + docs-reality fix) is the next slice after the current tool plan.
- **Assessment source:** verified by grep/read in the repo, not assumed. The blackboard subsystem =
  `src/fa/blackboard/blackboard.py` + `src/fa/inner_loop/session_db.py` (`blackboard` table) +
  `src/fa/inner_loop/_sqlite_common.py` + writer `src/fa/inner_loop/tools/mutation_guard.py`.
- **Related research artifacts created (this session, 2026-08-06):**
  - `/home/user/research-blackboard-query-tool-gap.md` — the full gap analysis: `blackboard.query` is
    documented-but-never-built as an agent tool; the capability exists but no ToolSpec/builder exposes it.
  - `/home/user/wire-search-lost-capabilities.md` — repo-wide wire-search: `blackboard.query` is the ONE
    genuine dead-instruction tool; all other referenced tools/commands are real or illustrative.
  - `worklogs/implementation-plans/PLAN-fs-blackboard-query.md` — the DRAFT plan for building
    `fs_blackboard_query` (the concrete next slice).
  - `knowledge/research/blackboard-audit-as-planned-vs-as-built-2026-08-07.md` — **"NOTE — Blackboard
    module: complete audit (as-planned vs as-built vs remaining)"** — full source-verified audit:
    storage (complete) + conflict-detection (complete+wired) are DONE; the artifact-index role
    (G1-G7) is unbuilt; docs still advertise it (G10). This is the authoritative gap reference for
    this item.
- **Why it is unfinished (verified):**
  1. **The blackboard is only a conflict-detection log today, not an artifact index.** It holds ONLY
     `type="file_version"` rows (writer = `mutation_guard.py:118,207`), used for write-conflict detection
     (read_set/write_set). No code writes `type="skill"/"research"/"adr"/"role"/"tool_spec"` entries —
     the artifact-index intent from `knowledge/research/substrate-formalization-and-reduction.md`
     (`load_artifacts(type, query)` index over markdown files) is NOT implemented.
  2. **No `rank` field exists anywhere** in `BlackboardEntry`/`Blackboard.query`/`session_db` (verified
     grep = zero). AGENTS.md:265,269 + llms.txt:42,44,89 advertise `blackboard.query(...)` returning
     "rank" — a FALSE claim; the rank feature was never built.
  3. **`blackboard.query` is not an agent tool.** It is a Python method on `Blackboard`
     (blackboard.py:297) and a `query_blackboard_rows` on `SessionDatabase`, but there is **no
     ToolSpec/builder/registration** exposing it to the LLM. AGENTS.md:7,265,271 + llms.txt:42-89 +
     reference.md:14 instruct the agent to "use `blackboard.query`" — a dead instruction (the tool that
     would satisfy it does not exist).
  4. **`Blackboard.query` has no `limit` and no `rank` ordering.** It returns all matching rows ordered
     `timestamp ASC` (session_db.py:852-862). A real artifact-discovery tool must add an output cap and
     decide ordering.
- **Design intent (from docs):** `project-overview.md` §1.2.6 Substrate Formality + I-6.2 (blackboard
  append-only, content-hashed, queryable, detect_conflict()), I-6.4 (content-hash/toolchain-digest/
  schema-version stamps). The substrate-formalization research note describes the blackboard as a
  **queryable index over markdown files** (skills/ADRs/research/roles/tool_specs), with a unified
  `load_artifacts(type, query)` loader "sorted by rank", filesystem-canon markdown remaining the source
  of truth. This is the *target*; only the conflict-detection slice exists today.
- **Unblock-trigger / why now:** the dead `blackboard.query` instruction in the agent-facing docs
  (AGENTS.md/llms.txt/reference.md) actively misleads the model (it would call a non-existent tool).
  Building `fs_blackboard_query` (the PLAN) closes the tool gap; building the artifact index + rank is a
  larger follow-up that makes the tool actually return useful skill/research/adr rows.
- **First concrete step when picked up (the PLAN):**
  1. Build `fs_blackboard_query` — a read-only tool wrapping `Blackboard.query()` that returns compact
     metadata rows (id, type, content_hash, read/write sets, timestamp) with a `limit` output cap,
     registered in implementer + planner profiles, added to canonical `TOOL_NAMES` (direct frozenset;
     prune `LEGACY_TO_NEW`).
  2. Add a blackboard artifact index/writer so `type="skill"/"research"/"adr"` rows exist to query
     (deferred sub-slice — a real index builder, mirroring `index_repo()`/FTS).
  3. Fix the docs-reality gap: correct the false "rank" claims; align `blackboard.query` →
     `fs_blackboard_query` in agent-facing docs.
- **Do NOT** treat `Blackboard.query` as "complete" just because it is tested — it is tested only for
  the conflict-detection path, not as an artifact index or an agent tool. Do NOT propagate the docs'
  "rank" claim until a real rank/index feature lands.

---

## See also

- [`knowledge/MAINTENANCE.md`](./MAINTENANCE.md) — recurring
  sweeps + cross-reference cascade rules; companion to this file.
- [`HANDOFF.md`](../worklogs/HANDOFF.md) §Current state — for items
  actively in flight (not deferred).
- [`AGENTS.md` §Context-budget discipline](../AGENTS.md#context-budget-discipline)
  — mitigations (a) and (b) reference I-2 and I-1/I-3
  respectively; the rule's «tracked in BACKLOG.md until ADR-7/8
  lands» wording points here. (Rule was numbered «PR Checklist
  rule #11» pre-2026-05-26; PR A' moved the goal-oriented core
  into AGENTS.md §Context-budget discipline and the PR-time
  declaration into the [`pr-creation` skill](./skills/pr-creation/SKILL.md)
  §PR Checklist.)
- [`research/bootstrap-cost-baseline-2026-05.md`](./research/bootstrap-cost-baseline-2026-05.md)
  §9 re-measurement triggers items 5 and 6 reference I-7 and
  I-8 here.

## Method note — a slice-and-splice edit silently deleted a BACKLOG item (2026-08-04)

**I-51 vanished from this file for six commits and nobody noticed.**

Sequence: `0d12ec3` added I-51 correctly (35 lines). `eb99724` then rewrote I-50
using a start/end splice — `s[:s.index('## I-50')] + new + s[s.index('## I-12'):]`
— which is correct only if nothing sits between the two anchors. I-51 did. It
was deleted with no diff conflict, no test failure, and no gate complaint,
because BACKLOG is prose and nothing validates its contents.

It surfaced only when a claim in the S13 session-start prompt ("I-46 through
I-53") was verified item by item against the file.

**Two transferable points:**

1. **Anchor-to-anchor splices are unsafe on append-ordered documents.** Replace
   a section by locating *its own* end (the next `^## ` heading), never by
   assuming the next known heading is adjacent.
2. **The prompt-verification pass paid for itself immediately.** Every other
   claim checked out — line numbers, file paths, CT/K ranges, the 553-line
   count. The one that did not was a silent data loss in the project's own
   findings ledger, and it was found by checking a claim rather than by reading
   the file.
