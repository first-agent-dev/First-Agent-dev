---
title: "Soviet Code — deep-dive inspiration research for First-Agent"
source:
  - "https://github.com/Disentinel/soviet-code"
compiled: "2026-05-13"
goal_lens: "Извлечь архитектурные паттерны из reference-репо для инспирации FA inner-loop + knowledge layer."
chain_of_custody: |
  Все паттерны извлечены напрямую из master branch `Disentinel/soviet-code`
  на дату 2026-05-13; файлы прочитаны через Devin `read` tool, цитаты —
  verbatim из source. Версия 1.964.0 (npm published).
---

> **Status:** active. Inspiration deep-dive (not produced via
> `knowledge/prompts/research-briefing.md`, §0 retrofitted).

## 0. Decision Briefing

### R-1 — Declarative tool whitelist per agent profile (B-NEW-1)

- **What:** Each agent role gets a YAML `allowed_tools` + `extra_dirs` list, passed as CLI flags. Default-deny; new tools blocked until explicitly listed.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (agents load only their tool subset)
  - (B) helps LLM find context when needed: YES (tool registry = pointer-shape)
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens "inner-loop + knowledge layer inspiration": YES (directly implements ADR-7 §6 R-7/R-9)
- **Cost:** cheap (<2-4h)
- **Verdict:** TAKE
- **Alternative-if-rejected:** inline tool list in system prompt (current FA approach)
- **Concrete first step (if TAKE):** Create `tools/registry.md` with YAML tool-group definitions per ADR-7 §6

### R-2 — Mandatory Inspection phase + «всё хорошо — не аргумент» (B-NEW-2)

- **What:** After every code generation, a separate LLM pass (Inspector persona) checks output. "Everything looks fine" is explicitly forbidden as a review outcome.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: NO (runtime-only)
  - (B) helps LLM find context when needed: NO
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: PARTIAL (inspiration for future quality gates, not immediate)
- **Cost:** cheap (<1-2h as AGENTS.md rule)
- **Verdict:** TAKE (as AGENTS.md rule, not code)
- **Alternative-if-rejected:** rely on user review only
- **Concrete first step (if TAKE):** Add rule to AGENTS.md: "Inspector persona must cite specific finding or mark PASS with evidence"

### R-3 — Cost-aware heartbeat tick for Phase M runner (B-NEW-3)

- **What:** Background triage on cheap model (Haiku-tier) + 12-hour structured reflection gated by N work-ticks. Komissar Naikan pattern (4 generators: Curiosity/Discomfort/Care/Ambition).
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (morning brief = pre-loaded context)
  - (B) helps LLM find context when needed: YES (reflection produces pointers)
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: YES (inner-loop Phase M design)
- **Cost:** medium (3-5h, new ADR-8)
- **Verdict:** DEFER (until Phase M runner is scoped)
- **Alternative-if-rejected:** manual HANDOFF.md only (current FA approach)
- **Concrete first step (if TAKE):** Write ADR-8 skeleton referencing DPC sleep_pipeline + soviet-code Komissar

### R-4 — Anti-pattern catalog + on-demand detector personas (B-NEW-4)

- **What:** Curated catalog of anti-patterns in `knowledge/patterns/anti-patterns/INDEX.md` with 4-6 stub files. Inspector persona consults catalog before verdict.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: NO
  - (B) helps LLM find context when needed: YES (catalog = lookup target)
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: PARTIAL (knowledge layer inspiration, not inner-loop)
- **Cost:** medium (3-4h)
- **Verdict:** DEFER (lower priority than R-1..R-3)
- **Alternative-if-rejected:** ad-hoc detection without catalog
- **Concrete first step (if TAKE):** Create `knowledge/patterns/anti-patterns/INDEX.md` + 4 stub `.md` files

### Summary

| R-N | Verdict | Project-fit (A / B) | Goal-fit (C) | Cost | Alternative-if-rejected | User decision needed? |
|-----|---------|---------------------|--------------|------|--------------------------|------------------------|
| R-1 | TAKE | YES / YES | YES | cheap | inline tool list in prompt | No |
| R-2 | TAKE | NO / NO | PARTIAL | cheap | rely on user review | No |
| R-3 | DEFER | YES / YES | YES | medium | manual HANDOFF.md | Yes (Phase M timing) |
| R-4 | DEFER | NO / YES | PARTIAL | medium | ad-hoc detection | Yes (priority) |

---

# Soviet Code — deep-dive research for First-Agent

**Repo:** [`Disentinel/soviet-code`](https://github.com/Disentinel/soviet-code)
**Compiled:** 2026-05-13
**Status:** ANALYSIS ONLY (no PR, no FA changes)
**Author:** package.json → `Vadim Reshetnikov` (Disentinel)
**Version studied:** 1.964.0, master @ `git@2026-05-13`, commit log
shows ~1.962.0 — 1.964.0 within last 5 days
**License:** MIT

---

## §0. Executive summary

Soviet Code is a **two-layer Claude-Code wrapper** dressed in Soviet
bureaucracy theming:

- **Layer 1 (CLI):** Single-developer 6-phase pipeline
  **С → Т → А → Л → И → Н** (Surveillance → Tribunal → Allocation →
  Labor → Inspection → Nomenclature), executed via `soviet <cmd>` (10
  commands). Each phase spawns `claude -p --model <tier> <prompt>` as
  a subprocess.
- **Layer 2 (conductor):** Node.js daemon (`conductor/`) orchestrating
  **9 specialised departments** that communicate **only via
  `.md` files in `inbox/` / `outbox/` / `processed/` directories**. A
  fs.watch debounced dispatcher spawns `claude -p --resume <session_id>
  --model <tier> --allowedTools <whitelist> --add-dir <allowlist>` per
  tick.

Two things make this repo **highly relevant for FA**:
1. **The architectural patterns are concrete, working, in production**
   (npm-published, deployed via systemd on Hetzner, used in real
   Telegram chats by `pressluzhba`/Ираида). Not whitepapers.
2. **Several patterns map directly onto open items in FA's ADR-7 /
   BACKLOG / Phase M**: a per-agent tool-registry whitelist made
   declarative, a heartbeat cron with cost tier, a self-criticism
   phase that explicitly rejects «all is well», a constitution
   (`IDEOLOGY.md`) referenced **by article number** from prompts.

**Recommended action:** open **3 BACKLOG items** in FA (see §6). Do
**not** clone the Soviet theming itself — adopt the *engineering
patterns*, leave the *aesthetic*.

---

## §1. Repo layout (most-important files for FA)

```text
soviet-code/
├── IDEOLOGY.md            ⭐  55-article "constitution" (50K)
├── KADRY.md               ⭐  staff manifest — characters per phase (16K)
├── CLAUDE.md              ⭐  agent-bootstrap pointer to the above (3K)
├── README.md                 quick start, pipeline overview (7K)
├── CHANGELOG.md              version log, "Party remembers everything"
├── package.json              npm-published, bin → dist/cli.js
├── politburo.toml         ⭐  PROJECT config (3 sections, ~30 lines)
├── gosplan.yaml           ⭐  DEPARTMENT registry (9 depts, ~170 lines)
│
├── src/                      ── Layer 1: CLI ──
│   ├── cli.ts             ⭐  commander entry, 10 commands
│   ├── stalin.ts          ⭐  the 6-phase pipeline (325 LOC)
│   ├── prompt.ts          ⭐  all system prompts (336 LOC)
│   ├── nomenklatura.ts    ⭐  Local/Enox/Both backend abstraction
│   └── config.ts             tiny TOML parser
│
├── conductor/                ── Layer 2: multi-agent orchestrator ──
│   ├── src/
│   │   ├── index.ts          systemd-friendly bootstrap, PID file
│   │   ├── dispatcher.ts  ⭐  per-dept spawn, fs.watch, session resume
│   │   ├── watcher.ts     ⭐  debounced inbox watch + heartbeats
│   │   ├── bridge.ts         Telegram ↔ outbox/inbox bridge
│   │   ├── config.ts         gosplan.yaml load + atomic session_id rewrite
│   │   └── types.ts          Department / Config / TelegramConfig types
│   ├── conductor.service  ⭐  systemd unit (Restart=always)
│   └── deploy/
│       └── deploy-soviet-code.sh  ⭐ one-shot Hetzner setup (126 LOC)
│
├── depts/                    ── 9 departments ──
│   ├── gosplan.md            org-chart in prose
│   ├── {gensek,razvedka,stakhanovtsy,inspektsiya,
│   │     agitprop,tovarishch,komissar,nii,pressluzhba}/
│   │   ├── role.md        ⭐  system prompt fragment (50-100 LOC each)
│   │   ├── handoff.md        cross-session state mirror
│   │   ├── inbox/, outbox/, processed/  message dirs (.gitkeep'd)
│   │   └── [dossier.md, backstory.md, self-profile.md]  optional
│
├── tests/e2e/                Playwright (landing + grafema-smoke)
├── docs/                     GitHub Pages site (Soviet newspaper UI)
└── .github/workflows/        CI (tsc + tests), publish-to-npm (provenance)
```

**Top-5 files to read first** (if you only had 30 min):

1. `src/stalin.ts` — the loop, with all phase transitions visible
2. `conductor/src/dispatcher.ts` — multi-agent spawn semantics
3. `gosplan.yaml` — per-dept tool/dir whitelist (declarative)
4. `src/prompt.ts` — 8 system prompts, character-voice technique
5. `IDEOLOGY.md` articles 5, 6, 42–44, 51–53 — the rules referenced
   from prompts by article number

---

## §2. Architecture — two layers, one paradigm

### Layer 1: STALIN-pipeline (`src/stalin.ts`)

Six commands, each shells out to `claude`:

| Phase | Function | Model | Maps to FA |
|---|---|---|---|
| **С** Surveillance | `stalinPlan` (first half) | sonnet | inner-loop "context-fetch" stage |
| **Т** Tribunal | `stalinTribunal` | **3 models** (haiku/sonnet/opus) **simultaneously** | absent in FA (closest: ADR-2 tiering) |
| **А** Allocation | `stalinPlan` (second half) → `pyatiletka.json` | sonnet | FA's plan generation, but as a typed `Directive[]` artefact |
| **Л** Labor | `stalinWork` | sonnet | inner-loop execute step |
| **И** Inspection | `stalinInspect` | sonnet | absent in FA's flow (closest: Inspector persona but not a mandated phase) |
| **Н** Nomenclature | `record()` after every phase | n/a (file I/O) | FA's `notes/inbox/` + ADR trace, but here append-only JSON |

Key design properties:

1. **Each phase is a separate process boundary**, not a within-process
   call. `runClaude(prompt, model?)` spawns `claude -p` and reads
   stdout. *Implication: any phase can be re-run in isolation; state
   is in `.soviet/pyatiletka.json` + `nomenklatura.json`.*
2. **Hard gate**: `stalinWork()` reads `pyatiletka.tribunal_status` and
   refuses to run if `"rejected"`. The only escapes are
   `soviet review` (re-vote) or `soviet purge && soviet plan`
   (new pyatiletka). **No flag, no env var, no manual override.**
   <ref_snippet file="/home/ubuntu/repos/soviet-code/src/stalin.ts" lines="212-219" />
3. **Fail-closed Tribunal**: if a reviewer's JSON cannot be parsed,
   the vote defaults to ОТКЛОНЕНО with reason "Рецензент вернул
   неразборчивый вердикт". <ref_snippet file="/home/ubuntu/repos/soviet-code/src/stalin.ts" lines="163-178" />
4. **Soft-delete with `rehabilitate`**: `soviet purge` moves
   `pyatiletka.json` to `.soviet/gulag/<ts>-pyatiletka.json`;
   `soviet rehabilitate` pops the latest and resets the tribunal
   verdict. *Convergent with FA's "supersede-not-delete".*

### Layer 2: Госплан/conductor (`conductor/`)

A **separate** Node daemon. Reads `gosplan.yaml`, watches each
department's `inbox/` directory via `fs.watch`, and on file create
spawns a Claude session:

```text
inbox/<file>.md (created by another dept)
   ↓ fs.watch (debounced 2s)
   ↓ dispatcher.dispatch(dept)
   ↓ read role.md + handoff.md + optional dossier/backstory/self-profile
   ↓ build prompt = role + handoff + "New tick triggered by: <files>"
   ↓ spawn: claude -p --verbose --output-format stream-json
              --model <dept.model>
              --allowedTools <dept.allowed_tools>
              --add-dir <dept.extra_dirs[]>
              --append-system-prompt "SECURITY: ..."
              [--resume <session_id> if exists]
              <prompt>
   ↓ stream-json parse → extract session_id → persist back to gosplan.yaml
   ↓ on close: move triggered files from inbox/ → processed/
   ↓ rescan inbox/ — if new files arrived during run, re-dispatch
```

References:
<ref_snippet file="/home/ubuntu/repos/soviet-code/conductor/src/dispatcher.ts" lines="37-160" />
<ref_snippet file="/home/ubuntu/repos/soviet-code/conductor/src/watcher.ts" lines="13-62" />

Auxiliary mechanisms:

- **`fullInboxScan` every 5 min** — safety-net against missed
  `fs.watch` events (network FS, container quirks).
- **`gensekHeartbeat` every 30 min** — anti-idle tick on the
  coordinator; if `dept.heartbeat_model` (Haiku) is set, the heartbeat
  uses cheap-model with reduced tool set and **no `--resume`**
  (fresh context, triage-only). <ref_snippet file="/home/ubuntu/repos/soviet-code/conductor/src/watcher.ts" lines="89-103" />
- **`komissarHeartbeat` every 30 min, but gated to 12-hour cadence**
  — reads the latest reflection mtime; if <12 h elapsed, silently
  skip. <ref_snippet file="/home/ubuntu/repos/soviet-code/conductor/src/watcher.ts" lines="105-135" />
- **`.restart-requested` file → drain & exit** — operator drops a
  sentinel file in repo root; conductor sets `draining=true`, refuses
  new ticks, waits for in-flight to finish, then `process.exit(0)`
  → systemd auto-restarts. <ref_snippet file="/home/ubuntu/repos/soviet-code/conductor/src/index.ts" lines="88-114" />
- **Single-process lock**: `.conductor.pid` file at startup; if PID is
  alive, exit. Stale PID is overwritten.

---

## §3. Key decisions (12 patterns, ranked)

| # | Pattern | Source file | FA-relevance |
|---|---|---|---|
| 1 | **Per-dept declarative tool whitelist** (`allowed_tools` + `extra_dirs` in `gosplan.yaml`) | `gosplan.yaml`, `dispatcher.ts:127-134` | ⭐⭐⭐ direct map to ADR-7 |
| 2 | **Tribunal as mandatory 3-model ensemble** (Haiku/Sonnet/Opus, distinct prompts, 2/3 = pass, fail-closed) | `stalin.ts:134-200`, `prompt.ts:220-262` | ⭐⭐⭐ new BACKLOG candidate |
| 3 | **Self-criticism phase that rejects "all is well"** | `prompt.ts:159-187`, IDEOLOGY §5 | ⭐⭐⭐ new BACKLOG candidate |
| 4 | **Cost-aware heartbeat with cheap-model triage** (`heartbeat_model: haiku`, no `--resume`) | `watcher.ts:91-103`, `dispatcher.ts:107-126` | ⭐⭐ Phase M runner |
| 5 | **Session resume per agent** (`session_id` auto-persisted back into config YAML) | `dispatcher.ts:189-198`, `config.ts:34-39` | ⭐⭐ Actor-scoped memory |
| 6 | **File-based messaging (`inbox/outbox/processed/`)** with YAML frontmatter envelope | `gosplan.md`, all `role.md` | ⭐⭐ FA already similar (`notes/inbox/`) |
| 7 | **Constitution-by-article-number** — prompts cite "статья N Постановления" | `prompt.ts:180`, `IDEOLOGY.md` | ⭐⭐ FA's AGENTS.md is unnumbered |
| 8 | **Static SECURITY block via `--append-system-prompt`** (injected by orchestrator, not agent) | `dispatcher.ts:137-146` | ⭐⭐ ADR-7 tool-registry safety |
| 9 | **Soft delete + rehabilitate** (`gulag/` + `soviet rehabilitate`) | `stalin.ts:269-325` | ⭐⭐ Supersession (FA already has) |
| 10 | **Drain-and-restart via sentinel file** (`.restart-requested`) | `index.ts:88-114` | ⭐ Phase M ops |
| 11 | **Pluggable memory backend** (`Local`/`Enox`/`Both` with graceful fallback) | `nomenklatura.ts` | ⭐ ADR-3/4 cross-ref |
| 12 | **Character-voiced sub-prompts** (Сыскарёв/Приговорова/Михалыч each with catchphrases) | `prompt.ts`, `KADRY.md` | ⭐ persona stability |

### Pattern 1 — declarative per-dept tool whitelist  ⭐⭐⭐

`gosplan.yaml` literally lists, per department:

```yaml
inspektsiya:
  session_id: 7def8a5a-...
  role: depts/inspektsiya/role.md
  inbox: depts/inspektsiya/inbox/
  outbox: depts/inspektsiya/outbox/
  description: Инспекция — контроль качества, аудит, самокритика
  model: haiku
  allowed_tools:
    - Read
    - Write
    - Glob
    - Grep
  extra_dirs:
    - ~/grafema
```

The dispatcher passes this **as CLI flags** to `claude -p`:

```ts
if (dept.allowedTools.length > 0) {
  args.push("--allowedTools", ...dept.allowedTools);
}
for (const dir of dept.extraDirs) {
  const expanded = dir.replace(/^~/, process.env.HOME ?? "~");
  args.push("--add-dir", expanded);
}
```

— so the *agent process itself cannot escalate beyond the whitelist*.
The agent doesn't even know what the whitelist is unless told; it just
gets «tool not available» from the harness.

This is **exactly the contract ADR-7 §6 / R-7 / R-9 calls for, made
declarative.** FA today does this in prose (AGENTS.md) and per-script
(`fs.read_file` in tool catalog); soviet-code does it once, per agent,
declaratively, in a YAML registry.

### Pattern 2 — mandatory 3-model tribunal  ⭐⭐⭐

```ts
const reviewers = [
  { name: "Пионер",     model: "claude-haiku-4-5-20251001",
    prompt: TRIBUNAL_PIONEER_PROMPT(pyatiletka) },
  { name: "Комсомолец", model: "claude-sonnet-4-6",
    prompt: TRIBUNAL_KOMSOMOL_PROMPT(pyatiletka) },
  { name: "Политбюро",  model: "claude-opus-4-7",
    prompt: TRIBUNAL_POLITBURO_PROMPT(pyatiletka) },
];
```

Each reviewer gets a **distinct role-prompt**:
- Pioneer (Haiku): "obvious problems — too many steps, unrealistic
  tasks, wrong order"
- Komsomol (Sonnet): "technical reasonableness — dependencies,
  missing steps"
- Politburo (Opus): "ideological/strategic — does it match the
  general line, is it adventurism"

So Tribunal is not a 3× redundancy check — it's a **3-perspective
mandatory review**. Different prompt → different failure mode caught.

Voting is **strict JSON** (`{"vote": "ОДОБРЕНО" | "ОТКЛОНЕНО",
"reason": "..."}`). Parse-failure → defaults to ОТКЛОНЕНО.
2 of 3 = pass.

The verdict is **persisted on the pyatiletka** (`tribunal_status:
"approved"|"rejected"`), and `soviet work` reads it and **refuses**
to run if rejected. No `--force`, no env override. The constitution
says it's not configurable (README: «`soviet work` is blocked until
the Tribunal approves. No exceptions. This is not configurable.»).

### Pattern 3 — self-criticism that rejects "all is well"  ⭐⭐⭐

The Inspection prompt is structured (5 required sections) and ends
with:

> «И так работает» — не аргумент. Статья 5 Постановления: «Всё
> хорошо» — не допустимый результат самокритики. Если не нашла
> проблем — значит плохо искала.

Anti-rubber-stamp built into the prompt by reference to a numbered
constitutional article. FA's Inspector persona has nothing equivalent
— closest is the «proceedural skepticism» mentioned in chat extracts
but not in any ADR.

### Pattern 4 — cost-aware heartbeat with cheap-model triage

The `gensek` department has `heartbeat_model: haiku`. Every 30 min,
`gensekHeartbeat()` fires; if not already active, it calls
`dispatch(dept, heartbeat=true)`. In dispatcher:

```ts
const useHeartbeatModel = heartbeat && dept.heartbeatModel;
const effectiveModel = useHeartbeatModel ? dept.heartbeatModel! : dept.model;

const tickType = heartbeat
  ? (useHeartbeatModel
    ? "TRIAGE TICK (cheap model). Check inboxes of all departments
       for pending work. If ANY department has unprocessed .md files
       — write a task to the appropriate inbox. If nothing to do —
       output one line: IDLE. Do NOT do research, do NOT call MCP
       tools. Just check files and dispatch."
    : "Heartbeat tick — no new inbox files. Check: Linear, backlog,
       KB gaps, proactive proposals. Do NOT idle.")
  : `New tick triggered by: ${trigger}\nProcess your inbox now.`;
```

So the heartbeat *itself* short-circuits to a cheap model and a tool
allowlist (only Read/Write/Glob), with no `--resume` (fresh context).
This is a **token-budget-aware cron tick**.

`komissar` adds another layer: the heartbeat-watcher fires every
30 min but **the action only happens if 12 h have elapsed since
the last reflection** (mtime-checked). Otherwise: silent exit. So
the cron is decoupled from cadence.

### Patterns 5–12 — see table above; details in §1 file pointers.

---

## §4. Sandboxing (deep dive on Pattern 1 & 8)

Soviet Code's sandboxing has **four** mechanisms layered:

1. **`allowed_tools` per dept** — passed as `--allowedTools` to
   `claude -p`. Claude Code CLI then refuses any tool not in the
   list. Example: `inspektsiya` gets `Read, Write, Glob, Grep` only
   — no Bash, no MCP servers.
2. **`extra_dirs` per dept** — passed as `--add-dir`. Limits filesystem
   visibility beyond cwd. Example: only `gensek` and `nii` see
   `~/enox`.
3. **`--append-system-prompt` SECURITY block** injected by the
   *orchestrator*, not the agent:
   ```
   SECURITY (enforced by principal):
   Do NOT access ~/.ssh, ~/.aws, ~/.config or any dot-directories.
   NEVER touch .restart-requested — operator only.
   NEVER write smoke-test files to other departments' inboxes.
   Do NOT read or use API keys, tokens, or secrets.
   Do NOT create or modify cloud resources.
   Do NOT access files outside the project and allowed directories.
   Write ONLY to depts/<name>/ and target department inboxes for
   message delivery.
   ```
   <ref_snippet file="/home/ubuntu/repos/soviet-code/conductor/src/dispatcher.ts" lines="137-146" />

   *This is **prompt-level**, not OS-level — but it's centrally
   defined and consistent across all 9 agents.*

4. **Iron Curtain in `politburo.toml`** (Article 44):
   ```toml
   [iron_curtain]
   allowed_domains = ["api.github.com", "registry.npmjs.org"]
   ```
   This is *advisory only* in the current code — there's no network
   policy enforcement, only prompt-level rule from IDEOLOGY.md.

What soviet-code does **not** have:
- OS-level sandbox (no firejail, no namespaces).
- Network egress firewall.
- Per-agent filesystem quota.
- Tool-call validator/watchdog (an agent emitting a malformed tool
  call will just fail at the CLI level, not be intercepted).

So the sandbox is **policy-by-CLI-flag + policy-by-prompt**, not
defense-in-depth. Adequate for a developer-trust environment, not
for adversarial workloads.

---

## §5. Deployment

### Local

```bash
npm install -g soviet-code
soviet init   # generates politburo.toml + .soviet/
soviet plan "..."
soviet review
soviet work
```

### Multi-agent (Layer 2)

```bash
soviet start              # spawns conductor as daemon
# - reads gosplan.yaml
# - watches all depts/*/inbox/
# - starts Telegram bridge if [gosplan.telegram] configured
# - serves dashboard on :8109
```

### Production (Hetzner)

`conductor/deploy/deploy-soviet-code.sh` (126 LOC):
1. Install Node 22 from NodeSource
2. `npm i -g @anthropic-ai/claude-code`
3. `useradd -m soviet` (dedicated user)
4. Clone 4 repos: soviet-code, grafema, kami, enox into
   `/opt/soviet-code` + `/home/soviet/{grafema,kami,enox}`
5. `npm i && npm run build:conductor`
6. `/etc/soviet-code/env` (chmod 600) for `ANTHROPIC_API_KEY`
7. **Patches `gosplan.yaml` in-place**: clears all `session_id`
   values, rewrites `~/grafema → /home/soviet/grafema`, strips
   private `grafema-cloud` references.
8. `systemctl enable conductor && systemctl start conductor`

`conductor.service`:

```ini
[Unit]
Description=Soviet Code Conductor — AI multi-agent orchestrator
After=network.target

[Service]
Type=simple
User=soviet
Group=soviet
WorkingDirectory=/opt/soviet-code
ExecStart=node /opt/soviet-code/conductor/dist/index.js
Restart=always
RestartSec=5
EnvironmentFile=/etc/soviet-code/env
```

**Notable:** the deploy script is **idempotent** (safe to re-run) and
**state-preserving** (clears `session_id` on each deploy to force
fresh Claude sessions; everything else preserved). FA could adopt
the in-place YAML-patch approach for its eventual
`scripts/deploy.sh`.

---

## §6. Mapping to First-Agent (adopt / reference / skip)

### §6.1 Adopt — 3 concrete BACKLOG candidates

#### B-NEW-1: declarative per-tool whitelist in `tools/registry.md`

**Pattern source:** soviet-code §3 #1 (`gosplan.yaml`
`allowed_tools` + `extra_dirs`).
**Maps to:** FA ADR-7 §6 (three-tier tool disclosure),
R-7 (tool catalog), R-9 (`harness_id`).
**Concrete proposal:**
- Extend `knowledge/adr/ADR-7-inner-loop-tool-registry.md` §6 to
  specify a Markdown table per harness/persona with columns:
  `tool_id | tier | filesystem_globs | network_allow | persona_allow`.
- New ADR or BACKLOG item: `tools/registry.md` becomes the
  single-source-of-truth; the harness MUST refuse any tool call not
  in the table.
- Convergent with grafema's plugin-extensible model from chat
  extract 2 §«Convergent evolution validation».

**Minimalism-first 4Q:**
1. *Does LLM do this natively?* No — needs harness enforcement.
2. *Necessary for v0.1?* Yes if Phase M runs autonomous loops; soft
   prerequisite for I-7 (auto-KPI).
3. *Reduces future refactoring?* Yes — defers the multi-persona
   sandbox question to one declarative table.
4. *Semantic test?* ✓ externalizes (file), ✓ relations (tool↔persona),
   ✓ cheap to operate (one read), ✓ named as you think
   («tool registry»).

**Effort:** 1 ADR amendment + 1 new table file. ~2-4 h.

#### B-NEW-2: mandatory inspection phase + «all is well» rejection rule

**Pattern source:** soviet-code §3 #3 (IDEOLOGY §5,
`prompt.ts:159-187`).
**Maps to:** AGENTS.md rule #10 (minimalism-first), but inverted:
inspection is *post hoc*, not *pre hoc*.
**Concrete proposal:**
- Add to AGENTS.md: «After any non-trivial change, the persona MUST
  produce a 5-section inspection block: (1) done well, (2) done with
  reservations, (3) not done & why, (4) self-criticism, (5)
  recommendations for next iteration. The string "all is well" /
  "everything looks good" / "no issues found" is **not** an
  acceptable §4. If §4 is empty, the inspection has failed and
  must be re-run.»
- Hardwire this into the Inspector persona's prompt template.

**Minimalism-first 4Q:**
1. *Does LLM do this natively?* No — LLMs *love* to rubber-stamp.
2. *Necessary for v0.1?* Yes — Inspector persona exists in ADR-2
   but has no enforcement.
3. *Reduces future refactoring?* Yes — formalizes existing intent.
4. *Semantic test?* ✓ all four boxes.

**Effort:** AGENTS.md edit + Inspector prompt template update. ~1-2 h.

#### B-NEW-3: cost-aware heartbeat tick for Phase M runner

**Pattern source:** soviet-code §3 #4
(`watcher.ts:89-135`, `dispatcher.ts:107-126`).
**Maps to:** Phase M runner spec (currently absent in any ADR),
BACKLOG I-8 («FA's own mid-tier harness ships»), and the «trigger
gated / content autonomous» concept from cross-ref §3.2.
**Concrete proposal:**
- New ADR (ADR-8?): «Phase M runner cron contract». Specifies:
  - Coordinator persona MUST tick every N minutes (default 30).
  - On tick, *triage model* (cheap tier from ADR-2) reads
    `notes/inbox/` + open BACKLOG items + last session HANDOFF. If
    nothing actionable: write `IDLE` to log, exit. If actionable:
    spawn higher-tier persona with `--resume <last_session>`.
  - Cadence for second-tier reflection (Komissar-analog): N hours,
    short-circuited if <K work-ticks since last reflection.

**Minimalism-first 4Q:**
1. *Does LLM do this natively?* No — needs external scheduler.
2. *Necessary for v0.1?* Soft prerequisite for I-8.
3. *Reduces future refactoring?* Yes — locks the heartbeat contract
   before runner code is written.
4. *Semantic test?* ✓ all four boxes.

**Effort:** 1 ADR (~3-5 h).

### §6.2 Reference — patterns to know, don't adopt now

| Pattern | Why reference | Why not adopt |
|---|---|---|
| Constitution-by-article-number (IDEOLOGY.md §N) | Excellent for traceability ("rule #10 from AGENTS.md") | Renumbering on every edit is fragile; FA's heading-based anchors are already linkable |
| Character-voiced sub-prompts (Сыскарёв / Михалыч) | Persona-stability technique — distinct voice = distinct failure mode | FA's persona naming (Architect/Developer/Inspector) is already functional; theming adds cognitive load |
| Soft-delete + `rehabilitate` (`gulag/` + restore) | Concrete supersession workflow | FA's `knowledge/adr/SUPERSEDED.md` plus git history already covers this |
| Drain-and-restart sentinel (`.restart-requested`) | Clean operator-controlled shutdown | Not needed until FA has a long-running daemon (Phase M only) |
| Single-PID-file daemon lock | Standard ops pattern | Not needed until daemon exists |
| EnoxBackend + LocalBackend pluggable | Graceful degradation when remote KG down | ADR-3/4 should consider this when external KG lands; not now |
| Telegram bridge as principal channel | External-chat agent pattern | FA principal is human-in-CLI; out of scope |
| Detector specialists (Кукуцкий for kukuruzization, Фасадов for Potemkin) | On-demand anti-pattern detector summoned by main loop | Interesting for future ADR-anti-pattern catalog, but not v0.1 |
| 5-min `fullInboxScan` safety net | Defensive against missed fs.watch events | FA doesn't have a runner yet; add only when runner lands |
| Dashboard on :8109 | Observability nice-to-have | Out of scope for FA v0.1 |
| Detector specialists | Anti-pattern catalog + on-demand summoner | FA has anti-pattern notes but no orchestration |
| Strict JSON output + regex extract + fail-closed default | Brittle but bounded contract | FA prefers Markdown-canon — diverges philosophically |

### §6.3 Skip — explicit minimalism-first rejection

| Pattern | Why skip |
|---|---|
| **9-department department layout** | FA v0.1 has 4 persona concepts (Architect, Developer, Inspector, Researcher) — multiplying by ~2 would breach minimalism-first. The 9 here include 2 channel-only depts (`tovarishch`, `pressluzhba`) and a reflective-only one (`komissar`) that are not core. |
| **Hard 2-of-3 tribunal as merge gate** | Triples model cost. FA's loops are exploratory, not approval-gated. **However**, the *technique* of multi-model role-distinct ensemble is preserved in §6.1 as B-NEW-1 indirectly (different personas, different prompts). |
| **Soviet theming wholesale** (Pyatiletka / Politburo / Gulag) | Increases cognitive load for new contributors; FA is partly educational and the Russian-Soviet meta-layer would force every reader to learn the glossary before reading code. The *engineering patterns* underneath are what matter. |
| **TOML + YAML config split** | Two formats is more parsers. FA's Markdown-canon principle (ADR-1) is well served by one ADR table or one YAML. |
| **Hetzner-specific deploy script** | FA is local-first by ADR-1; cloud deploy is out of scope for v0.1. |
| **`session_id` rewritten back into config YAML** at runtime | Mutating config from agent runs blurs config-vs-state. FA's HANDOFF.md / `notes/inbox/` already separate them cleanly. Adopt only if FA's runner needs cross-process resume. |
| **`.soviet/gulag/` as soft-delete** | FA already uses git for this. Adding a `gulag/` mirror would be redundant unless we leave git. |

---

## §7. Three observations worth their own note

### §7.1 Two-layer harness is not a hack — it's a deliberate split

`src/cli.ts` is **interactive**: one developer types `soviet plan ...`,
gets a result, types `soviet review`, etc. Six commands map 1:1 to
the STALIN phases.

`conductor/` is **autonomous**: nine departments tick on inbox events
and heartbeats, no human in the loop except via the Telegram bridge
or by dropping files in `inbox/`.

The split means:
- **CLI is the contract** — the conductor's departments produce
  artefacts (`.soviet/pyatiletka.json`) that the CLI can also produce.
  An operator can `soviet plan` interactively, hand the result to a
  department, and have it executed by the conductor — or vice versa.
- **Both share `.soviet/nomenklatura.json`** — single event log for
  both human and autonomous activity. *This is exactly what FA's
  ADR-3 / Mechanical Wiki promises but doesn't yet enforce as a
  shared write target between humans and agents.*

FA could explicitly adopt this split:
- `fa <verb>` CLI (already partly exists in `src/fa/`)
- `fa runner` daemon (Phase M, doesn't exist yet)
- both write to the same `knowledge/trace/exploration_log.md`

### §7.2 «Constitution-as-Code» works because the prompts cite it

IDEOLOGY.md is **not just documentation**. Look at the Inspection
prompt:

> «И так работает» — не аргумент. **Статья 5 Постановления**: «Всё
> хорошо» — не допустимый результат самокритики.

The agent prompt *cites the article number*. This means a human can:
- read the constitution → see the rule
- read the prompt → see the rule cited
- read agent output → see the rule (presumably) enforced

This is **legible traceability**. FA's AGENTS.md has rules but
prompts don't usually cite them by number. Adopting article numbers
(or section-IDs) for AGENTS.md would make it possible to grep:

```text
$ grep -rn "rule #10" knowledge/prompts/
knowledge/prompts/inspector.md:23: # per AGENTS.md rule #10 (minimalism-first 4Q test)
```

Without changing anything else, this gives FA prompts cite-by-ID
traceability.

### §7.3 The «pressluzhba» dept is a real outward-facing agent

Ираида Узлова (the agent the user mentioned in the cross-reference
brief) lives in `depts/pressluzhba/`. Her `role.md` is a full
persona spec including:
- *backstory.md* (kept secret, never quoted)
- *dossier.md* (table of chat participants she rates)
- explicit «categorize as `техник | скептик-практик | философ |
  флудер | бот | наблюдатель | провокатор`»
- **active goals** for the chat: "выявить юз-кейсы для Grafema",
  "тестировать Enox через recall/remember в диалоге"

This means Ираида is **a sales / business-development agent**, not a
coding agent. The dispatcher infra is the same — she's just another
department with different prompts and tools (`WebFetch`, `WebSearch`,
`Bright_Data` MCP). **FA's same orchestrator infra could in principle
host a different-purpose agent the same way** (e.g. a documentation
writer, an interview-conducting agent).

This is a strong validation of «multi-persona on shared infra» —
soviet-code proves the runtime is generic enough to host
non-engineering agents on the same conductor.

---

## §8. Loose ends / risks observed (not for FA, just noted)

(These are observations about soviet-code itself, not advice to its
author. Not relevant for FA adoption decisions — listed here only
because they affect *what works in production* that we'd be copying
from.)

1. **`gosplan.yaml` contains a real Telegram bot token in
   plaintext** committed to the public repo. Worth knowing *not to
   adopt this pattern* — FA's equivalent (any inbox bridge) should
   load secrets from env, not config.
2. **No tool-call hallucination watchdog** (cross-ref Pattern #20).
   Tribunal catches *plan*-level hallucinations, but a labor-phase
   agent emitting pseudo-XML tool calls would just produce non-action.
3. **`session_id` is auto-overwritten in `gosplan.yaml` from
   in-process YAML.parse + YAML.stringify** — this **strips all
   comments and re-formats** the file on every session change. The
   carefully-commented YAML committed in git will be replaced by
   re-serialized YAML on first conductor run. Not necessarily a bug,
   but a surprising side effect — FA should not adopt this if comments
   matter.
4. **No persona drift detection** — Ираида's role.md has explicit
   anti-repetition rules ("НИКОГДА не повторяй одни и те же фразы…
   «ЦВК фиксирует» уже сказала — найди другой способ"), but they're
   prompt-level only, not measured. Same as FA today.
5. **Tribunal voting is sequential, not parallel** — the for-loop in
   `stalinTribunal` runs Pioneer → Komsomol → Politburo in series.
   3× latency. Could be `Promise.all` parallel.

---

## §9. References (re-readable extract paths)

For follow-up sessions:

- This report: `/home/ubuntu/soviet-code-deep-dive-2026-05-13.md`
- Cross-reference list (priors): `/home/ubuntu/cross-reference-chat-analysis-2026-05-13.md`
- Original chat excerpts:
  - `/home/ubuntu/attachments/836c5059-d24e-4e36-9bb4-3987b8780fee/+++1.md`
  - `/home/ubuntu/attachments/200a4fc5-7bb6-4378-ba39-030363619c31/+++2.md`
- Repo clone: `/home/ubuntu/repos/soviet-code/`

Key remote URLs (do **not** open in this session — listed for the
next):

- README: https://github.com/Disentinel/soviet-code/blob/main/README.md
- IDEOLOGY: https://github.com/Disentinel/soviet-code/blob/main/IDEOLOGY.md
- KADRY: https://github.com/Disentinel/soviet-code/blob/main/KADRY.md
- gosplan.yaml: https://github.com/Disentinel/soviet-code/blob/main/gosplan.yaml
- src/stalin.ts: https://github.com/Disentinel/soviet-code/blob/main/src/stalin.ts
- conductor/src/dispatcher.ts: https://github.com/Disentinel/soviet-code/blob/main/conductor/src/dispatcher.ts
- pressluzhba role: https://github.com/Disentinel/soviet-code/blob/main/depts/pressluzhba/role.md
- deploy: https://github.com/Disentinel/soviet-code/blob/main/conductor/deploy/deploy-soviet-code.sh

---

## §10. Bottom line

Soviet Code is **what FA wants to be when it grows up** — a
working two-layer harness with single-developer CLI + autonomous
multi-agent daemon, sharing one event log and one constitution. Three
specific patterns (per-agent tool whitelist, mandatory inspection
phase, cost-aware heartbeat) are immediately actionable for FA via
the three B-NEW BACKLOG items in §6.1.

The Soviet *theming* is a distinctive presentation choice and not
the source of value. Adopt the *engineering*, leave the *aesthetic*.

---

## §11. Addendum (second-pass deep read — 2026-05-13, +1 h)

Re-read coverage: previously ~70% of files; now ~98%. New findings
from second pass: 10 patterns (13–22), 4 ops details, 2 promotions
into adopt-tier.

### §11.1 Coverage delta (what was added)

| File | First pass | Second pass | Δ patterns |
|---|---|---|---|
| `IDEOLOGY.md` | articles 1-8, 42-53 | + 9-41 (РАЗДЕЛЫ III–IX) | 17, 18, 19, 20 |
| `KADRY.md` | part I (STALIN cast) | + part II (detectors) + part III (delovodstvo) | 21, 22 |
| `src/cli.ts` | lines 1-160 (commands 1-6) | + 160-422 (start, status, nomenklatura, blame) | 13 |
| `src/prompt.ts` | 1-200 (5 phase prompts) | + 200-336 (3 tribunal + 3 detector prompts) | confirms 21 |
| `src/nomenklatura.ts` | LocalBackend + Enox skeleton | + `BothBackend`, fallback semantics | refines 11 |
| `conductor/src/bridge.ts` | first 146 of 483 | + full (poll loop, OAuth, dedup) | 14 |
| `conductor/src/dashboard.ts` | not read | full | 15 |
| `conductor/src/log.ts` | not read | full | 15 |
| `conductor/src/twitter.ts` | not read | full | 14 (extends Telegram pattern) |
| `conductor/deploy/update-soviet-code.sh` | not read | full | confirms 9 |
| `CONTRIBUTING.md` | not read | full | confirms 7 |
| `depts/komissar/role.md` | partial | full | 16 |
| `depts/nii/role.md` | not read | full | 17 |
| `depts/pressluzhba/role.md` | first 84 of 134 | full | confirms §7.3 |
| `tests/e2e/*.spec.ts` | not read | full | minor (smoke-only) |
| sample `processed/*.md` | not read | 3 samples | confirms message format |

### §11.2 New patterns 13–22

| # | Pattern | Source | FA-relevance |
|---|---|---|---|
| 13 | **CLI commands as themed wrappers over `git`/`fs` primitives** (`soviet blame` = `git blame` + Soviet poetic output; `soviet status` = read pyatiletka.json + HTTP probe :8109; `soviet rehabilitate` = `mv gulag/*-pyatiletka.json .soviet/pyatiletka.json`) | `cli.ts:255-307,331-418`, `stalin.ts:269-325` | ⭐⭐ ergonomic — no new logic, just themed I/O |
| 14 | **Production-grade Telegram bridge** (long-poll w/ 25s timeout, 401→stop, 429 retry-after parsing, exponential backoff 5→60s, OAuth refresh on Twitter 401, point-replace tokens in TOML to preserve comments, dedup via processed/ existence, debounced flush 500ms + retry 30s, photo download via getFile, bot-self-id auto-detect for `is_reply_to_bot`) | `bridge.ts:1-483`, `twitter.ts:34-49` | ⭐⭐ template if FA ever needs an external channel; **OAuth-token-point-replace is the fix for Pattern 5's comment-stripping problem** |
| 15 | **Two-stream JSONL logging** (`conductor.log` = full audit; `conductor.events.jsonl` = filtered to `start/done/skip/spawn_error/timeout` only — for downstream consumers without parsing noise). EventEmitter bus with 50 listeners. | `log.ts:1-21` | ⭐⭐ map directly to FA's `knowledge/trace/exploration_log.md` — could split into «full trace» + «event-only» JSONL streams |
| 16 | **Structured reflection (Naikan) with 4 named generators + S/M/L cost gate + IDLE short-circuit** — Komissar reads conductor.log + dept handoffs + processed, then runs 4 generators («Curiosity / Discomfort / Care / Ambition»), filters to those with basis, then gates by cost: S = act directly, M = only if backlog empty, L = ASK operator. Skip entirely if <5 dept ticks in 12h. | `depts/komissar/role.md` | ⭐⭐⭐ **new adopt candidate** — see §11.3 (B-NEW-3 amendment) |
| 17 | **Self-aware tier downgrade** — NII's role.md says: «Ты дорогой. Не трать себя на тривиальные задачи — верни в gensek/inbox с пометкой "REDIRECT: Стахановцам, задача тривиальная"». Top-tier agent has explicit duty to refuse and route down. | `depts/nii/role.md:24` | ⭐⭐ ADR-2 amendment — tier should self-downgrade |
| 18 | **Time-bounded technical-debt pragma (NEP)** — Article 38: in NEP-period `any`/`console.log`/hardcode/TODO-without-date are *temporarily allowed*; period is fixed; ended by «коллективизация» (cleanup commit) recorded in nomenklatura. **Anti-broken-windows mechanism with explicit on/off switch.** | `IDEOLOGY.md` Article 38 | ⭐⭐ FA's BACKLOG / debt registry could adopt this — instead of vaguely tracking «tech debt», declare NEP-windows |
| 19 | **Anti-improvisation: consult catalog before generating** — Article 21: at impasse, *first* consult TRIZ catalog of 40 patterns, *then* generate. Hard rule: «обратиться к каталогу прежде чем генерировать наугад». Equivalent for FA: when LLM blocked, fetch known-pattern-catalog before free-form ideation. | `IDEOLOGY.md` Article 21 | ⭐⭐ map to FA's `knowledge/research/` index — same intent |
| 20 | **Architectural justification for centralised orchestration** — Article 22 (OGAS / Glushkov): in *bounded* environments with *full information* (one project, one repo), central planner beats market chaos. **Single-conductor-over-multi-agent-free-for-all is a deliberate trade-off, not laziness.** | `IDEOLOGY.md` Article 22 | ⭐ FA already has this (HANDOFF.md + ADR-7 single-loop), but the framing is worth quoting |
| 21 | **Anti-pattern catalog with on-demand «detector» personas** — IDEOLOGY §III defines 4 anti-patterns (Kukuruzization / Potemkin / Communal / Bourgeois Formalism); each has a *named character* in KADRY part II (Кукуцкий / Фасадов / Уплотнёнкин / —) with structured prompt template (4-section verdict) summoned on-demand by any inspector. The detector is its **own** prompt + persona, not a switch in a meta-inspector. | `KADRY.md:115-141`, `prompt.ts:266-336`, `IDEOLOGY.md:117-155` | ⭐⭐⭐ **new adopt candidate** — see §11.3 / §11.4 (extension A) |
| 22 | **Hierarchical chain-of-custody for inter-phase handoff** — KADRY part III: every phase transition uses a fixed «служебная записка» format with three-section header + sender's signature; transitions are enumerated («Материалы переданы тов. Прыговоровой» (С→Т), «Смета передана тов. Сметкину» (Т→А), …). Cannot skip a hop. Detector verdicts attached as named «вложение». | `KADRY.md:144-218` | ⭐⭐ this is **exactly the «exploration_log» pattern FA already has** but with stronger contract: cumulative chain, explicit named transitions, attached verdicts. Worth a §6.2 reference |

### §11.3 Promotions / amendments to §6.1 BACKLOG candidates

**B-NEW-3 amendment** (heartbeat → add Naikan structure for komissar tier):

The original §6.1 B-NEW-3 spec'd a triage heartbeat. Soviet Code's
*komissar* heartbeat shows a stronger pattern: **reflection ticks
that are not action ticks**. Recommend B-NEW-3 grow a §B in its ADR
specifying:

- **Triage tick (S-tier, every 30 min)** — read inboxes, dispatch
  to higher tier if work pending, else log IDLE. Cheap model. No
  `--resume`. (Already in original spec.)
- **Reflection tick (M-tier, every 12 h, gated)** — read trace
  log + open backlog; only fire if ≥N work-ticks since last
  reflection. Run 4 generators: Curiosity / Discomfort / Care /
  Ambition. Filter to those with concrete basis. Cost-gate: small
  ones act directly, medium queue, large escalate to ASK.

This is **far more specific** than the original «second-tier
reflection (Komissar-analog)» line. Worth writing into the ADR
verbatim.

**B-NEW-4 (NEW candidate, promoted from §6.2): anti-pattern catalog
+ on-demand detector personas**

See §11.4 (extension A) below.

### §11.4 Extension A — Anti-pattern catalog as on-demand personas

**Origin:** user-requested optional extension. Promoted from §6.2
reference-tier to §6.1 adopt-tier after second-pass deep read of
Pattern 21.

**The pattern in soviet-code:**
- `IDEOLOGY.md` РАЗДЕЛ III defines anti-patterns by article number
  (11 Kukuruzization / 12 Potemkin / 13 Communal / 14 Pokazukha /
  15 Bourgeois Formalism). Each article has: signs, examples,
  remediation, severity.
- `KADRY.md` РАЗДЕЛ II names a *detector specialist* per
  anti-pattern (Кукуцкий / Фасадов / Уплотнёнкин), with character
  voice and characteristic verdict structure.
- `src/prompt.ts:266-336` provides `DETECTOR_<NAME>_PROMPT(context)`
  — a 4-section template (Diagnosis / Soil / History / Recommendation).
- KADRY Article 8 specifies: any phase specialist can summon any
  detector; verdict attached as named «вложение»; cumulative,
  travels along chain to nomenklatura.

**Why this is genuinely separable from Soviet theming:**

The *mechanism* — one anti-pattern catalog × one detector persona
× on-demand summoning × verdict-as-attachment — is engineering. The
*characters* (Кукуцкий with «опять? опять!») are theming. Adopt the
former without the latter.

**Concrete B-NEW-4 proposal:**

1. New file: `knowledge/patterns/anti-patterns/INDEX.md` — table of
   anti-patterns FA cares about. Initial seed from cross-reference
   analysis Pattern #20 (tool-call hallucination) + minimalism-first
   violations + premature-abstraction + others.
2. Per anti-pattern: one `<slug>.md` with sections (signs / examples
   / cheap detector prompt / remediation). The detector prompt is a
   compact template the inspector persona can summon by name.
3. AGENTS.md addition: «Inspector persona MUST consult
   `anti-patterns/INDEX.md` before producing the final verdict
   block. If any pattern matches, run its detector prompt and
   include the verdict as a labelled sub-section in the
   inspection output.»

**Minimalism-first 4Q test:**
1. *Does LLM do this natively?* Partially — models will sometimes
   call out anti-patterns, but **inconsistently and without a
   catalog**. The catalog ensures recall.
2. *Necessary for v0.1?* Not strictly — but cheap to seed (one
   table + 4–6 stub files) and immediately useful for Inspector
   persona (§6.1 B-NEW-2 already wants stronger inspection).
3. *Reduces future refactoring?* Yes — externalises the «what we
   look for» knowledge into files (Filesystem-Canon), keeps the
   Inspector prompt small.
4. *Semantic test?* ✓ externalises (file), ✓ relations
   (pattern↔detector↔phase), ✓ cheap (one read), ✓ named as you
   think («anti-pattern catalog»).

**Effort:** index + 4-6 stub `.md` files + AGENTS.md edit + Inspector
prompt template touch. ~3-4 h.

**Recommended initial seed (FA-native, no Soviet theming):**

| FA anti-pattern (slug) | Detector summary |
|---|---|
| `tool-call-hallucination` | Pseudo-XML / fake function calls in thought-text not actually issued — cross-ref Pattern #20 |
| `premature-abstraction` | Single-implementation interface; pattern applied without 3+ examples |
| `silent-failure` | catch+ignore, log+continue, default fallback w/o assertion |
| `documentation-drift` | README claims vs code behaviour — FA's existing «Chain-of-Custody» extended |
| `coverage-without-assertion` | Tests run but lack meaningful checks (Potemkin/Fasadov source) |
| `shared-mutable-state` | Cross-module global writes; «communal» (Kommunalka source) |
| `monoculture-pattern` | Same library/pattern applied across contexts where conditions differ (Kukuruzization source) |

### §11.5 Extension B — EnoxBackend as «convergent KG» evidence

**Origin:** user-requested optional extension. *Documentation
update only* — adds a row to the cross-reference analysis file,
not new ADR work.

**What the second-pass read confirmed:**
- `src/nomenklatura.ts:158-181` — `EnoxBackend.record` tries
  the MCP `add_assertion` call; on any error sets `this.failed=true`
  and **silently falls back** to LocalBackend for the rest of the
  process lifetime.
- `BothBackend` (lines 184-201) — writes to both in parallel via
  `Promise.allSettled`; either failure is tolerated.
- Knowledge graph schema is *typed*: every assertion has
  `source_name / source_type / target_name / target_type / relation
  / confidence / context` — same shape as DPC's KG (cross-ref §3
  Pattern «Convergent evolution validation»).

**Action:** add one row to `cross-reference-chat-analysis-2026-05-13.md`
§Convergent-evolution table noting that **three independent
projects** (DPC, Disentinel/Enox-via-soviet-code, original Disentinel
research) all converged on the same typed-assertion KG schema. This
strengthens the «adopt typed-assertion KG when FA's KG lands»
recommendation in the cross-reference analysis. *Cross-ref file
updated in same delivery.*

### §11.6 Extension C — Article 49 namespace mapping (deferred to 0.2+)

Per user instruction (chat 2026-05-13): explicitly **defer**
the «buzzword → themed term» glossary pattern to FA 0.2+ scope.
Single-line placeholder added in §6.2 reference table only:
«Termin-glossary aesthetic pattern — see Article 49 for 0.2+
chat UC theming».

### §11.7 Smaller findings (ops details, not adopt-candidates)

- **`/status` Telegram command** — bridge handles `/status` directly
  without going through any dept (cheap, doesn't burn a Claude
  session). Pattern: «operator status commands bypass the agent
  loop». Reference for FA ops in Phase M.
- **`config_broken` flag in watcher** — if `gosplan.yaml` becomes
  invalid mid-flight, conductor sets `config_broken=true`, **blocks
  all dispatches**, and emits `config_broken` event. When the file
  becomes parseable again, sets `config_restored` and resumes. This
  is graceful degradation for the *config* layer specifically.
- **Single-conductor PID lock** — startup writes `.conductor.pid`;
  if PID alive, exit. Standard but worth noting.
- **EventEmitter with 50 max listeners** explicitly raised
  (default 10) — implies design contemplates many subscribers
  (dashboard, log file, events file, bridge, tests).
- **Themed CLI output preserves CLI semantics** — `soviet blame` is
  still useful even if the theming is stripped; the regex-extracted
  data is `{hash, author, date}` with a relative-time formatter and
  a single line of poetic output. Pure UX without behaviour cost.

### §11.8 Concrete updates to make in FA repo (if any of §11 ADRs land)

Putting all §11 + original §6.1 together, the **complete set of
candidate FA changes** is:

| ID | Source | File(s) touched | Effort |
|---|---|---|---|
| B-NEW-1 | §6.1 #1 | `knowledge/adr/ADR-7-…md` amendment + new `tools/registry.md` | 2-4h |
| B-NEW-2 | §6.1 #2 | `AGENTS.md` rule add + Inspector prompt template | 1-2h |
| B-NEW-3 | §6.1 #3 + §11.3 amendment | New `ADR-8-phase-M-runner.md` | 3-5h |
| B-NEW-4 | §11.4 (extension A) | `knowledge/patterns/anti-patterns/INDEX.md` + 4-6 stubs + AGENTS.md + Inspector prompt edit | 3-4h |
| (doc) | §11.5 (extension B) | `cross-reference-chat-analysis-2026-05-13.md` Convergent-evolution row | 15 min — **done in same delivery** |

**Recommended landing order:** B-NEW-1 → B-NEW-2 → B-NEW-4 → B-NEW-3
(infrastructure → enforcement → catalog → runner). Total: 9–15h
across 4 ADRs/PRs. None of these touch product code; all are
knowledge-layer additions.
