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
  template **sections** inside
  [`knowledge/prompts/prompting.md`](./prompts/prompting.md)
  rather than standalone files. A non-Devin agent following the
  intent table reaches the §T2-T5 anchors but the templates are
  inline, not split into per-role files.
- **Partial progress (2026-05-29):** `prompting.md` moved from
  `docs/` to `knowledge/prompts/` next to RESOLVER.md, and the
  RESOLVER T2-T5 rows now cite the co-located `./prompting.md §Tn`
  anchors (option (b) below, partially realised — the cross-folder
  «no file yet» fallback is gone). Item stays open: the templates
  are still inline sections, not the standalone per-role files of
  option (a).
- **Blocked-on:** First non-Devin session attempts a planner /
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
  reason echoes hook wording). **Both former follow-ups are now
  closed:** the `prepare-pr` producer shipped in PR #24
  (`pr.prepare`, see §Q-N below) and `IntentGuard` is wired into
  the `fa run` bootstrap (`cli.py` `_cmd_run`, landed in PR #23
  final-review). **Scope expanded post-#24 (commit 78ced94):**
  `IntentGuard` now also gates `fs.run_bash` via a dedicated
  AST analyzer ([`bash_intent.py`](../src/fa/inner_loop/bash_intent.py),
  READ_ONLY / VERIFY_ONLY / INDEX_WRITE / REPO_WRITE /
  OPAQUE_EXEC) and trusts only current-session drafts via the
  [`PrDraftStore`](../src/fa/inner_loop/pr_draft.py) (stale /
  externally-fabricated drafts rejected) — closing the remaining
  `fs.run_bash` bypass of the draft-first contract.
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
    **Closed by PR E (2026-05-28):** `pr.prepare` tool ships in
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
  - [`HANDOFF.md`](../HANDOFF.md) §Process / rule changes
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

- **Status:** deferred from test audit (2026-06-04).
- **Idea:** Three categories of tests fail on vanilla Windows:
  1. **Bash-dependent tests** (6 in `test_cli.py`, 1 in
     `test_inner_loop_runtime.py`, 1 in `test_inner_loop_runtime_limits.py`,
     2 in `test_inner_loop_tools.py`). They invoke `fs.run_bash` which spawns
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
- **Worth fixing?** The bash tests reveal the real gap: `fs.run_bash` is a
  POSIX shell tool. A Windows-native agent would need `fs.run_cmd` or a shell
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
  skip("nope")          # not detected
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
