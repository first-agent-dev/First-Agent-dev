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
     [AGENTS.md §PR Checklist rule #10 question 1 «Spawn-
     recursion anti-pattern»](../AGENTS.md#pr-checklist).
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
- **Path (a) `.agents/skills/<name>/SKILL.md`** (Devin auto-load
  convention) **deferred** per minimalism-first: a second
  filesystem surface for the same content is not justified
  while only two skills exist. Re-evaluate once ≥ 3 skills
  exist or once a session demonstrates the Devin auto-load
  surface produces materially better behaviour than the
  AGENTS.md PR Checklist rule #12 load-directive (the OSS-LLM
  audience already loads via the explicit rule).

## M-1 — Inner-loop scaffolding / HookRegistry runtime

- **Status:** **closed by PR #24** (2026-05-20). Runtime now lives at
  `src/fa/inner_loop/` with the full ADR-7 §1–§10 + ADR-8 contract:
  JSON-Schema validation on every dispatch (§5), modify→re-validate +
  sandbox replay on every `Decision.modify` (§8), `SandboxHook` gating
  `fs.read_file` / `fs.write_file` paths in addition to `fs.run_bash`,
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
  rework on every ADR amendment surfaced by Devin Review.
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
  - [`HANDOFF.md`](../HANDOFF.md) lines 164, 176.
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
    writer (per-run, `~/.fa/state/runs/<run_id>/attempt_history.json`,
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
    contracts for the three M-1 tools (`fs.read_file`, `fs.write_file`,
    `fs.run_bash`) plus the documentation-anchor `edit_file.yaml`.
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
  (`devin/1779480362-t2-llm-provider-client`). Seven modules under
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
  - Q-2 per-entry `httpx_retries` + `tiktoken` pre-call estimate.
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
  - [`HANDOFF.md` §Current state ADR list](../HANDOFF.md) —
    ADR-9 bullet with `M-4` cross-reference.

## M-5 — T-4 `~/.fa/models.yaml` loader (closes M3 of release roadmap)

- **Status:** closed 2026-05-22 — landed in T-4 implementation PR
  (`devin/1779515293-t4-models-yaml-loader`). One module
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
    fields (cooldown_seconds, httpx_retries, timeout_seconds,
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
  - [`HANDOFF.md` §Current state ADR list](../HANDOFF.md) —
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
  - [`HANDOFF.md`](../HANDOFF.md) §Process / rule changes
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
  reason echoes hook wording). The session bootstrap that wires
  `IntentGuard` into the loop driver + the deferred `prepare-pr`
  tool / sub-agent that populates `pr_draft.md` remain
  follow-ups (HANDOFF §Next #2).
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
    tree (`fs.write_file`, `edit_file` shapes,
    `git add` / `git commit` via `fs.run_bash`), re-runs
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
    a known location under `~/.fa/state/runs/<run_id>/pr_draft.md`
    populated by the agent itself; agent populates it on
    session start via a new `prepare-pr` tool or sub-agent.
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
  - [`HANDOFF.md`](../HANDOFF.md) §Process / rule changes
    2026-05-25 last paragraph — feasibility verified by the
    session-start audit of `src/fa/inner_loop/hooks/base.py`.
- **Blocked-on:** M-6 (PR B) — closed by PR #20; `IntentGuard` imports
  `fa.hygiene.pr_intent.classify_intent`. Both PR B and PR C are now
  closed (landed 2026-05-27).

## M-8 — PR D — LLM-driven coder loop (`drive_session`) + `fa run` CLI + `UrllibTransport`

- **Status:** **in flight (PR D, 2026-05-27).**
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

## See also

- [`knowledge/MAINTENANCE.md`](./MAINTENANCE.md) — recurring
  sweeps + cross-reference cascade rules; companion to this file.
- [`HANDOFF.md`](../HANDOFF.md) §Current state — for items
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
