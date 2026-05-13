# Backlog — deferred ideas with unblock triggers

> **Purpose.** Single canonical list of architectural ideas
> deferred from Stage 1 (Devin-driven, per
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
> **Distinction from [`HANDOFF.md`](../HANDOFF.md) §Current state.**
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
  [AGENTS.md rule #11](../AGENTS.md#pr-checklist) explicitly
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
- **Blocked-on:** Stage 1 is Devin-driven; Devin decides EXEMPT
  per PR with full diff context. The ambiguity becomes a runtime
  LLM problem only when a non-Devin agent opens PRs.
- **Unblock-trigger:** First Stage-2 session opens a PR
  autonomously and needs to apply EXEMPT.
- **First concrete step once unblocked:** Enumerate EXEMPT
  criteria as a closed list — e.g. «(a) link-target update only;
  (b) typo / formatting only; (c) date / version bump only;
  (d) translation, no semantic change; (e) new section under
  existing artefact = NOT EXEMPT». Add a `docs/glossary.md` row
  for «EXEMPT (documentation-only PR)».
- **Why this is LOW ROI for Stage 1.** Devin reads full PR diff
  before deciding; mid-tier LLMs do not. Per
  `repo-audit-2026-05-10-revised.md` §3.6 — process-coordination
  concern, not runtime LLM performance.

## I-5 — RESOLVER.md T2-T5 rows lack standalone template files

- **Status:** deferred from Stage 1 (proposed 2026-05-10
  critical-re-pass of `repo-audit-2026-05-10.md`).
- **Idea:** [`knowledge/prompts/RESOLVER.md`](./prompts/RESOLVER.md)
  intent table routes T2-T5 (planner, coder, debug, eval) to
  template files that do not exist yet — the body is inlined in
  [`docs/prompting.md`](../docs/prompting.md) as fallback. A
  non-Devin agent following the intent table verbatim hits
  «no file yet» for T2-T5 and may misroute or hallucinate the
  missing template.
- **Blocked-on:** First non-Devin session attempts a planner /
  coder / debug / eval task from a template path.
- **Unblock-trigger:** Either (a) extract T2-T5 templates to
  standalone files (`knowledge/prompts/planner-fa.md`,
  `coder-fa.md`, `debug-fa.md`, `eval-fa.md`), or (b) update
  RESOLVER.md to cite `docs/prompting.md` anchors directly.
- **First concrete step once unblocked:** Decide between (a)
  and (b). Option (a) parallels the existing
  [`prompts/architect-fa.md`](./prompts/architect-fa.md) /
  [`architect-fa-compact.md`](./prompts/architect-fa-compact.md)
  split, but multiplies file count by 4. Option (b) is lower-
  touch (anchor-only change in RESOLVER.md).
- **Why this is LOW ROI for Stage 1.** Devin picks the template
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
  fails CI. After landing, [AGENTS.md PR Checklist rule #7](../AGENTS.md#pr-checklist)
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
- **References:** [`docs/workflow.md`](../docs/workflow.md) item 7
  (concept origin); AGENTS rule #7 (current manual rule);
  [`MAINTENANCE.md` §When adding a new file](./MAINTENANCE.md)
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
  to a continuously-tracked KPI. Each Devin (or First-Agent OWN
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
- **Idea:** PR #5 + this extension's 6-session baseline (3 Devin
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
  cross-fork sessions = still Devin's harness underneath).
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

- **Status:** deferred — added 2026-05-12, blocked on
  skill-loading mechanism. Not urgent — user noted no audits in
  the immediate pipeline; this item parks the artefact in plain
  sight until the unblock-trigger lands.
- **Idea:** The repo-audit workflow currently lives as a ~970-line
  playbook at
  [`knowledge/prompts/repo-audit-playbook.md`](./prompts/repo-audit-playbook.md)
  (filed alongside the prompt templates for convenience). Devin
  loads SKILL.md files automatically via the
  `.agents/skills/<name>/SKILL.md` convention (YAML frontmatter
  with `name:` + `description:`); OSS agents (DeepSeek 4,
  Kimi 2.6) have no equivalent auto-load mechanism. The playbook
  is therefore reachable today only via grep / explicit chat
  reference, not via session bootstrap.
- **Blocked-on:** one of —
  - (a) `.agents/skills/` convention adopted for this repo for
    Devin-side workflows, OR
  - (b) `knowledge/llms.txt §BY-DEMAND-INDEX` gains a dedicated
    «Playbooks» sub-section + AGENTS.md rule referencing it, so
    OSS agents pick it up on-demand (single-line bootstrap entry,
    no new directory).
- **Unblock-trigger:** first PR that creates `.agents/skills/`
  in this repo, OR first session where a non-Devin agent
  successfully invokes the playbook via a §BY-DEMAND-INDEX
  reference (whichever lands first).
- **First concrete step once unblocked (path a):** create
  `.agents/skills/repo-audit/SKILL.md` with YAML frontmatter
  (`name: repo-audit`, `description: 7-phase workflow for
  agent-oriented repo audits — see playbook for full procedure`)
  pointing at the playbook as canonical body. Move (or symlink)
  the playbook out of `knowledge/prompts/` once the SKILL
  directory is the authoritative home.
- **First concrete step once unblocked (path b):** split
  `§BY-DEMAND-INDEX` to add `### Playbooks (knowledge/playbooks/)`
  with one row per playbook (line-count + 1-sentence summary,
  same shape as the existing `### Prompts` rows); add a one-line
  rule in `AGENTS.md` Pre-flight Step 4 («if the user requests
  a repo-audit-style refactor, load
  `knowledge/playbooks/repo-audit.md` first»).
- **Prior art:** this session's `workflow-repo-audit.md` artefact
  (attached to session log 2026-05-11) is the literal source.
  Same author, same wording — the file at
  `knowledge/prompts/repo-audit-playbook.md` is a verbatim copy.
- **Why this is LOW ROI until either path lands.** Without an
  auto-load surface, every audit session re-discovers the
  playbook via grep or user pointer; the playbook still pays off
  because it's structured and self-contained, but the convention
  gap means the next OSS-agent audit session pays a discovery
  cost. Until the gap closes, the artefact lives where it can be
  found by a `find knowledge/prompts/` grep.

## See also

- [`knowledge/MAINTENANCE.md`](./MAINTENANCE.md) — recurring
  sweeps + cross-reference cascade rules; companion to this file.
- [`HANDOFF.md`](../HANDOFF.md) §Current state — for items
  actively in flight (not deferred).
- [`AGENTS.md` PR Checklist rule #11](../AGENTS.md#pr-checklist)
  — mitigations (a) and (b) reference I-2 and I-1/I-3
  respectively; the rule's «tracked in BACKLOG.md until ADR-7/8
  lands» wording points here.
- [`research/bootstrap-cost-baseline-2026-05.md`](./research/bootstrap-cost-baseline-2026-05.md)
  §9 re-measurement triggers items 5 and 6 reference I-7 and
  I-8 here.
