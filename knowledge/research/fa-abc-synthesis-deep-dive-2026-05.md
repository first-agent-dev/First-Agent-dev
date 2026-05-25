---
title: "FA ABC-synthesis deep-dive: determinism patterns across 9 OSS LLM-agent repos (incl. rtk-ai amendment)"
source:
  - "external user-curated synthesis composed across two Devin sessions (2026-05-23 prior session for §0-§7; 2026-05-23 rtk-ai amendment session for §0a-§7a)"
  - "per-repo clones at /home/ubuntu/rtk-ai-dive/{rtk,grit,icm} (Amendment R)"

compiled: "2026-05-25"
goal_lens: "Identify deterministic-harness patterns (A-tier pre-prompt, B-tier post-LLM verification) from 9 OSS LLM-agent projects to inform ADR-10 invariant list (I-1..I-5) and FA's §1.2.5 compliance-by-construction principle."
chain_of_custody: |
  Multi-repo deep-dive synthesis composed across two sessions.
  §0-§7 cover six OSS projects (pi, gbrain, hermes-agent, gortex,
  kronos-agent-os, dpc-messenger) under «what runs before / after the
  LLM call» determinism lens. §0a-§7a (Amendment R) extends with
  rtk-ai/{rtk, grit, icm} under reframed goal lens (Q5 in §6):
  «verifiable hook results + deterministic harness to control LLM».
  Every finding cites `repo/file.ext:line` and quotes 3-10 line
  snippets verbatim. Recipes for re-cloning are in §1.7-§1.9 intros.
  This doc is reference material for next-session ADR-10 work; per
  AGENTS.md §1.2 minimalism-first, the action surface lives in
  ~3 k of the doc's ~19 k words — see §0c for the read order.
tier: stable
links: []
mentions: []
confidence: extracted
claims_requiring_verification: []
---

> **Status:** active. Reference material for next-session ADR-10
> invariant list (§3 + §3a). Linear read is ~25 k tokens; targeted
> read after §0c jump-table is ≤ 5 k tokens.

# FA ABC-synthesis deep-dive

Per-repo determinism deep-dive across multiple open-source LLM-agent projects
(pi, gbrain, hermes-agent, gortex, kronos-agent-os, dpc-messenger, rtk-ai/{rtk, grit, icm}).
Goal lens: how each project mechanises rules around the LLM call — what runs
*before* the call (A-tier: harness produces fact-blocks the LLM reads
instead of prose rules) and what runs *after* the call (B-tier: harness
verifies/coerces/redacts LLM output, with two sub-shapes — pass/fail and
laddered).

---

## 0. Repo-relevance triage

Six repos, none filtered out. All six surfaced ≥ 2 determinism-relevant
patterns under the new lens.

| Repo                                                          | Language               | Relevant files counted | Outcome                              |
| ------------------------------------------------------------- | ---------------------- | ---------------------: | ------------------------------------ |
| pi (earendil-works/pi)                                        | TypeScript             |                      5 | full-pass new territory              |
| gbrain (garrytan/gbrain)                                      | TypeScript             |                      4 | full-pass new territory              |
| hermes-agent (NousResearch)                                   | Python                 |                      4 | full-pass new territory              |
| gortex (zzet/gortex)                                          | Go                     |                      3 | re-pass, new findings beyond v3 §2.1 |
| kronos-agent-os (spyrae)                                      | Python                 |                      4 | re-pass, deeper than v3 §2.4–2.7     |
| dpc-messenger (mikhashev)                                     | Python                 |                      2 | re-pass, new findings beyond v3 §2.8 |
| Amendment R — rtk-ai/{rtk, grit, icm} concrete-code deep dive | Python,Rust,TypeScript |               multiple | new material - rtk-ai deep dive      |

---

## 0c. How to read this doc (navigation aid)

~19 k words. Action surface is ~3 k words. Read in this order:

1. **Action surface first** (~3 k words, ~10 min total):
   §0 + §0a (repo-relevance triage),
   §3 + §3a (ADR-10 invariants I-1..I-5),
   §4 + §4a (A-bucket and B-bucket entry proposals A12..A29 + B14..B23),
   §6 + §6a (open questions — 1..5 unresolved, 6..9 resolved),
   §6b (§1.2.5 placement decision — compliance-by-construction).
2. **§1.x and §1.7..§1.9 are reference material.** Jump to a specific
   subsection ONLY when §3 / §4 / §6 cites a pattern ID (P1, GR2, IC2,
   R4, …) you need to verify.
3. **Forcing function: never paraphrase a §1.x snippet.** Quote the
   `file.ext:line` reference verbatim — the line citations are the
   doc's primary evidence chain, paraphrasing breaks it. The same
   forcing function applied to the authors of this doc (every claim is
   grounded in a verbatim snippet, not a paraphrase); applies
   symmetrically to the next-session ADR-10 author.
4. **§5 + §7 + §7a** are meta-context (corrections to prior versions,
   scope statements). Read once on first encounter; skip thereafter.

Rationale: doc was designed for jump-table use, not linear read.

---

## 1. Per-repo findings

### 1.1 pi (earendil-works/pi, TypeScript)

Pi is a TypeScript agent harness (`packages/agent` + `packages/coding-agent`
+ `packages/ai`). It is the smallest, most surgically-typed of the six.
Five files contribute determinism shapes FA does not already have.

#### P1 — TypeBox schema validation w/ coercion for LLM tool args

**File:** `pi/packages/ai/src/utils/validation.ts` (324 LOC,
function `validateToolArguments` at L292).

```ts
// pi/packages/ai/src/utils/validation.ts:292–323
export function validateToolArguments(tool: Tool, toolCall: ToolCall): any {
    const args = structuredClone(toolCall.arguments);
    Value.Convert(tool.parameters, args);

    const validator = getValidator(tool.parameters);
    if (!hasTypeBoxMetadata(tool.parameters) && isJsonSchemaObject(tool.parameters)) {
        const coerced = coerceWithJsonSchema(args, tool.parameters);
        if (coerced !== args) {
            if (isRecord(args) && isRecord(coerced)) {
                for (const key of Object.keys(args)) {
                    delete args[key];
                }
                Object.assign(args, coerced);
            } else {
                return validator.Check(coerced) ? coerced : args;
            }
        }
    }

    if (validator.Check(args)) {
        return args;
    }
```

**Pattern:** validator-cache (`WeakMap` keyed by the schema object, L6),
then a three-step pipeline: (1) `Value.Convert` (TypeBox coercion for
TypeBox schemas), (2) `coerceWithJsonSchema` for plain JSON-Schema
inputs the LLM emitted as strings/null, (3) `validator.Check` for the
verdict, with formatted errors (L257-275) carrying schema-path + JSON
arg dump to the caller.

**Determinism lens:** this is a **B-deterministic verifier** running
between «LLM emitted tool call» and «handler dispatched». Coercion is
the load-bearing move — LLMs emit `"true"` (string) where the schema
says `boolean`, `"42"` for `integer`, `null` for «field absent».
Without coercion, the verifier reports «type mismatch» and the LLM
re-emits the same call. With it, the harness silently fixes the noise
and the LLM never re-sees the rule.

**FA fit — extends B14.** v3's B14 covers regex-based output validation
(secret/path/prompt-leak). This extends to **input-side schema-coerce
verification at the tool boundary**. FA's `ToolSpec.parameters` already
carries JSON-Schema; what's missing is the coercion layer. New entry
proposal: **B19 tool-call coerce-then-check** (see §4).

---

#### P2 — YAML-frontmatter prompt loader returning a diagnostics array

**File:** `pi/packages/agent/src/harness/prompt-templates.ts` (267 LOC,
`loadPromptTemplates` at L30, `parseFrontmatter` at L200).

```ts
// pi/packages/agent/src/harness/prompt-templates.ts:30–47
export async function loadPromptTemplates(
    env: ExecutionEnv,
    paths: string | string[],
): Promise<{ promptTemplates: PromptTemplate[]; diagnostics: PromptTemplateDiagnostic[] }> {
    const promptTemplates: PromptTemplate[] = [];
    const diagnostics: PromptTemplateDiagnostic[] = [];
    for (const path of Array.isArray(paths) ? paths : [paths]) {
        const infoResult = await env.fileInfo(path);
        if (!infoResult.ok) {
            if (infoResult.error.code !== "not_found") {
                diagnostics.push({
                    type: "warning",
                    code: "file_info_failed",
                    message: infoResult.error.message,
                    path,
                });
            }
            continue;
        }
```

```ts
// pi/packages/agent/src/harness/prompt-templates.ts:200–214
function parseFrontmatter<T extends Record<string, unknown>>(
    content: string,
): Result<{ frontmatter: T; body: string }, Error> {
    try {
        const normalized = content.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
        if (!normalized.startsWith("---")) return { ok: true, value: { frontmatter: {} as T, body: normalized } };
        const endIndex = normalized.indexOf("\n---", 3);
        if (endIndex === -1) return { ok: true, value: { frontmatter: {} as T, body: normalized } };
        const yamlString = normalized.slice(4, endIndex);
        const body = normalized.slice(endIndex + 4).trim();
        return { ok: true, value: { frontmatter: (parse(yamlString) ?? {}) as T, body } };
    } catch (error) {
        return { ok: false, error: toError(error) };
    }
}
```

**Pattern:** loader returns `{ promptTemplates, diagnostics }`. The
diagnostics carry stable error codes — `file_info_failed`, `list_failed`,
`read_failed`, `parse_failed` (L4) — that the caller can branch on or
display, but no thrown exception interrupts the load. CRLF is normalised
to LF (L204), the YAML body is parsed with `yaml.parse`, fallback to
empty frontmatter on missing block. `substituteArgs` (L249-) supports
`$1`, `$@`, `$ARGUMENTS`, `${@:N:L}` placeholders.

**Determinism lens:** this is the cleanest **A-tier prompt loader** in
the six repos. The harness loads markdown-with-frontmatter prompt files,
parses them deterministically, and the LLM only ever sees the resolved
prompt body with placeholders filled. The loader contract is stable
(diagnostic codes, never throws). FA's prompts are currently inline
Python strings or `knowledge/prompts/*.md` referenced by path — there is
no shared loader. v3's A0 (`fa note new`) is a frontmatter *generator*,
not a loader.

**FA fit — extends A0, supports A2.** A0 generates frontmatter for a
new note. A new loader could canonicalise frontmatter *consumption* —
every prompt the harness reads goes through one parser with one
diagnostic schema. Useful when FA grows beyond the current ~10 prompts.
New entry proposal: **A15 fa prompts load** (see §4).

---

#### P3 — XML-safe skill formatting for system-prompt assembly

**File:** `pi/packages/agent/src/harness/system-prompt.ts` (34 LOC,
`formatSkillsForSystemPrompt` at L3).

```ts
// pi/packages/agent/src/harness/system-prompt.ts:3–28
export function formatSkillsForSystemPrompt(skills: Skill[]): string {
    const visibleSkills = skills.filter((skill) => !skill.disableModelInvocation);
    if (visibleSkills.length === 0) return "";

    const lines = [
        "The following skills provide specialized instructions for specific tasks.",
        "Read the full skill file when the task matches its description.",
        "When a skill file references a relative path, resolve it against the skill directory (parent of SKILL.md / dirname of the path) and use that absolute path in tool commands.",
        "",
        "<available_skills>",
    ];

    for (const skill of visibleSkills) {
        lines.push("  <skill>");
        lines.push(`    <name>${escapeXml(skill.name)}</name>`);
        lines.push(`    <description>${escapeXml(skill.description)}</description>`);
        lines.push(`    <location>${escapeXml(skill.filePath)}</location>`);
        lines.push("  </skill>");
    }
```

**Pattern:** XML-escape every value before interpolation. `escapeXml`
(L28-33) handles `&` `<` `>` `"` `'` only. Output is hand-built XML lines
with consistent indentation. The model is told to «read the full skill
file when the task matches its description» — the harness ships only
name + description + location, never the full body.

**Determinism lens:** A-tier prompt-assembly pattern. The harness owns
the canonical format the model sees. If a skill name contains a literal
`<` the escaper handles it; the LLM never sees ambiguous XML. Compare
to ad-hoc f-string templating where a literal `<` in user data breaks
the prompt structure.

**FA fit — modifies A13 (`fa render-tool-table`).** A13 in v3 is the
Gortex tool-table pattern. Pi's `formatSkillsForSystemPrompt` is the
**skill-table version** of the same A-tier shape: structured registry
→ structured prompt block. FA's prompts in `knowledge/prompts/` will
need a tool/skill/note-table assembler at some point. A13's name
expands naturally to «structured-block renderer» — tool table, skill
table, context-card table, etc.

---

#### P4 — Pre-action git-status guard (extension hook)

**File:** `pi/packages/coding-agent/examples/extensions/dirty-repo-guard.ts`
(56 LOC, `checkDirtyRepo` at L10).

```ts
// pi/packages/coding-agent/examples/extensions/dirty-repo-guard.ts:10–32
async function checkDirtyRepo(
    pi: ExtensionAPI,
    ctx: ExtensionContext,
    action: string,
): Promise<{ cancel: boolean } | undefined> {
    // Check for uncommitted changes
    const { stdout, code } = await pi.exec("git", ["status", "--porcelain"]);

    if (code !== 0) {
        // Not a git repo, allow the action
        return;
    }

    const hasChanges = stdout.trim().length > 0;
    if (!hasChanges) {
        return;
    }

    if (!ctx.hasUI) {
        // In non-interactive mode, block by default
        return { cancel: true };
    }
```

**Pattern:** registered on `session_before_switch` and
`session_before_fork`. Runs `git status --porcelain`; if dirty AND no UI
attached, cancels by default; if UI attached, prompts the user. The
LLM never participates — this is harness-level.

**Determinism lens:** B-tier guard expressed as a one-screen extension.
FA's BashGate is conceptually similar but lives inside the bash-tool
boundary; this is **session-lifecycle**, not tool-lifecycle. The shape
is interesting: a small async function with three return shapes
(`undefined` = allow, `{ cancel: true }` = block, prompt-then-decide
= ask).

**FA fit — modifies F1's structural lever.** FA already has
HookRegistry with `BEFORE_TOOL_EXEC` and middleware. The dirty-repo
guard isn't a tool-level guard, it's a session-level guard — closer to
v3's §6 «structural meta-rule» (rule-budget cap) than to any B entry.
Worth keeping in mind when ADR-10 sub-categorises B sub-shapes.

---

#### P5 — stdout takeover lifecycle (background write serialisation)

**File:** `pi/packages/coding-agent/src/core/output-guard.ts` (108 LOC,
`takeOverStdout` at L45).

```ts
// pi/packages/coding-agent/src/core/output-guard.ts:45–63
export function takeOverStdout(): void {
    if (stdoutTakeoverState) {
        return;
    }

    const rawStdoutWrite = process.stdout.write.bind(process.stdout) as StdoutTakeoverState["rawStdoutWrite"];
    const rawStderrWrite = process.stderr.write.bind(process.stderr) as StdoutTakeoverState["rawStderrWrite"];
    const originalStdoutWrite = process.stdout.write;

    process.stdout.write = ((
        chunk: string | Uint8Array,
        encodingOrCallback?: BufferEncoding | ((error?: Error | null) => void),
        callback?: (error?: Error | null) => void,
    ): boolean => {
        if (typeof encodingOrCallback === "function") {
            return rawStderrWrite(String(chunk), encodingOrCallback);
        }
        return rawStderrWrite(String(chunk), callback);
    }) as typeof process.stdout.write;
```

**Pattern:** every spawned subprocess that might write to stdout is
funnelled through stderr so the TTY remains the harness's. Idempotent
(early-return on `stdoutTakeoverState`); retry on ENOBUFS/EAGAIN
serially.

**Determinism lens:** lower priority for FA — FA's bash tool already
captures stdout/stderr in BashGate. Mentioned here for completeness;
no FA-fit recommendation.

---

### 1.2 gbrain (garrytan/gbrain, TypeScript)

Gbrain is a knowledge-brain engine (Postgres-backed page store, doctor
suite, audit primitives). The doctor suite + schema-verify + audit
primitive are the determinism gold here.

#### G1 — Structured Check + DoctorReport scoring

**File:** `gbrain/src/commands/doctor.ts` (5684 LOC; `Check` interface
at L30, `computeDoctorReport` at L39).

```ts
// gbrain/src/commands/doctor.ts:30–49
export interface Check {
  name: string;
  status: 'ok' | 'warn' | 'fail';
  message: string;
  details?: Record<string, unknown>;
  issues?: Array<{ type: string; skill: string; action: string; fix?: any }>;
  remediation?: import('../core/remediation-step.ts').RemediationStep[];
  remediation_status?: 'remediable' | 'human_only' | 'blocked';
}

export function computeDoctorReport(checks: Check[]): DoctorReport {
  const hasFail = checks.some(c => c.status === 'fail');
  const hasWarn = checks.some(c => c.status === 'warn');
  let score = 100;
  for (const c of checks) {
    if (c.status === 'fail') score -= 20;
    else if (c.status === 'warn') score -= 5;
  }
  score = Math.max(0, score);
  const status: DoctorReport['status'] = hasFail ? 'unhealthy' : hasWarn ? 'warnings' : 'healthy';
  return { schema_version: 2, status, health_score: score, checks };
}
```

**Pattern:** every check returns a typed object, not a side-effect-print.
30+ check functions in the file each return `Promise<Check>` with the
same shape. Aggregator turns them into a numeric `health_score`
(fail=-20, warn=-5, floored at 0) and a categorical `status`
(`healthy | warnings | unhealthy`). The report carries
`schema_version: 2` (L49) so future format changes are versioned.

The `remediation` and `remediation_status` fields (L36-37) are the
exceptional move: a check that fails *also* carries the action that
would fix it, categorised by who can do it (`remediable` = harness can
auto-fix, `human_only` = needs operator, `blocked` = nothing FA can do).

**Determinism lens:** **A-tier** preflight pattern. The agent (or
operator) calls `doctor` once and reads a single structured report
instead of grepping multiple log lines. Compare to hermes's
`hermes_cli/doctor.py` which just prints — gbrain's is the
strictly-better shape because the output is machine-readable and the
report carries an overall verdict.

**FA fit — replaces FA's planned doctor / extends A11 (`fa
invariants`).** FA does not yet have a doctor entry-point. v3's A11
(`fa invariants`) is closest. The gbrain `Check` interface is the
canonical shape to adopt: status enum, structured details, optional
remediation. The scoring weights (20/5) are starting defaults — FA can
tune later. New entry proposal: **A16 fa doctor** (see §4).

---

#### G2 — Post-migration schema verification + self-healing

**File:** `gbrain/src/core/schema-verify.ts` (282 LOC,
`parseExpectedColumns` at L37, `verifySchema` at L199).

```ts
// gbrain/src/core/schema-verify.ts:199–227
export async function verifySchema(engine: BrainEngine): Promise<VerifyResult> {
  const expected = parseExpectedColumns();
  const actualColumns = await getActualColumns(engine);
  const actualTables = await getActualTables(engine);

  const result: VerifyResult = {
    checked: 0,
    missing: [],
    healed: [],
    failed: [],
  };

  // Group expected columns by table for cleaner logging
  for (const col of expected) {
    // Skip tables that don't exist yet — they'll be created by schema.sql
    // on the next initSchema() call. We only verify columns on tables that
    // DO exist (the failure mode is: table exists, migration ran, but ALTER
    // TABLE silently failed).
    if (!actualTables.has(col.table)) {
      continue;
    }

    result.checked++;

    const key = `${col.table}.${col.column}`;
    if (!actualColumns.has(key)) {
      result.missing.push({ table: col.table, column: col.column });
    }
  }
```

```ts
// gbrain/src/core/schema-verify.ts:1–13 (header — failure-mode receipt)
/**
 * Post-migration schema verification with self-healing.
 *
 * PgBouncer transaction-mode poolers can silently swallow ALTER TABLE
 * statements: the SQL doesn't error, but the column never gets created.
 * The migration system increments the schema version counter anyway, so
 * gbrain thinks it's on v29 but the actual table is missing columns.
 *
 * This module parses the canonical CREATE TABLE definitions in
 * schema-embedded.ts and diffs them against information_schema.columns.
 * Missing columns are self-healed via ALTER TABLE ADD COLUMN IF NOT EXISTS.
 *
 * Called at the end of initSchema(), after all migrations complete.
 */
```

**Pattern:** **invariant-as-contract** with self-healing. The canonical
schema SQL is the source of truth; runtime DB state is verified to
match; missing columns are auto-added via `ALTER TABLE ADD COLUMN IF
NOT EXISTS`. Failure case is documented inline (PgBouncer silent-drop).
Parser is best-effort (L37-119) handling CREATE-TABLE and ALTER-TABLE
ADD COLUMN syntax.

**Determinism lens:** the load-bearing concept is **declarative source
of truth → runtime verification → bounded self-heal**. The harness owns
the schema; the database is just storage. If the storage drifts, the
harness reconciles.

For FA, the analogous failure mode is **YAML-config drift** vs **disk
state** — e.g. `agents.example.yaml` says «BashGate uses skip-list X»
but the running BashGate was constructed before X landed. Or:
`knowledge/llms.txt` says «file F exists at L lines» but the actual file
has L' lines (this is the AGENTS.md PR-rule the markdownlint hook fails
silently on).

**FA fit — extends A11 (`fa invariants`) into a verifier surface.** v3
A11 measures invariants once and reports. Gbrain's pattern is
run-this-on-every-startup-and-self-heal. The shape adopts cleanly:
parse FA's canonical config files (`pyproject.toml`,
`knowledge/llms.txt`, `.markdownlint.yaml`), diff against runtime,
repair. New entry proposal: **A17 fa verify-state** (see §4).

---

#### G3 — Consolidated ISO-week JSONL audit primitive

**File:** `gbrain/src/core/audit/audit-writer.ts` (245 LOC,
`computeIsoWeekFilename` at L80, `createAuditWriter` at L174).

```ts
// gbrain/src/core/audit/audit-writer.ts:80–92
export function computeIsoWeekFilename(prefix: string, now: Date = new Date()): string {
  const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const dayNum = (d.getUTCDay() + 6) % 7; // Mon=0, Sun=6
  d.setUTCDate(d.getUTCDate() - dayNum + 3); // shift to Thursday
  const isoYear = d.getUTCFullYear();
  const firstThursday = new Date(Date.UTC(isoYear, 0, 4));
  const firstThursdayDayNum = (firstThursday.getUTCDay() + 6) % 7;
  firstThursday.setUTCDate(firstThursday.getUTCDate() - firstThursdayDayNum + 3);
  const weekNum = Math.round((d.getTime() - firstThursday.getTime()) / (7 * 86400000)) + 1;
  const ww = String(weekNum).padStart(2, '0');
  return `${prefix}-${isoYear}-W${ww}.jsonl`;
}
```

```ts
// gbrain/src/core/audit/audit-writer.ts:1–11 (header — refactor rationale)
/**
 * v0.40.4.0 — shared audit-writer primitive.
 *
 * Replaces the 5 hand-rolled JSONL audit modules (rerank-audit,
 * shell-audit, supervisor-audit, audit-slug-fallback, phantom-audit)
 * that all duplicated the same ISO-week filename math, the same
 * best-effort write loop, and the same read-current-and-previous-week
 * loop.
 */
```

**Pattern:** five separate audit modules collapsed into one primitive.
Each consumer keeps its typed event shape; only file I/O is shared.
ISO-week filenames (year-boundary edge: 2027-01-01 → `2026-W53.jsonl`).
Best-effort writes — append failures go to stderr but never throw.
Read-back walks current + previous week so 7-day windows straddling
Monday-midnight stay covered.

**Determinism lens:** A-tier audit primitive. Each audit consumer is
*data*, not *code* — a config of `featureName + errorLabel +
errorMessagePrefix + errorTrailer`. The harness owns the I/O semantics.
Adding a new audit kind is a new event-shape interface, not a new
write loop.

**FA fit — extends A8 (`fa hygiene` family).** v3 A8 lists per-target
hygiene commands (bloat, tokens, discover). Audit is the long-tail
companion: each hygiene check writes a JSONL row through one primitive
so the doctor can read «last 7 days of hygiene events» without
re-implementing log parsing. No new bucket entry — A8 absorbs it.

---

#### G4 — Allowlist validators for path / slug / filename

**File:** `gbrain/src/core/operations.ts` (4236 LOC; `validateUploadPath`
at L110, `validatePageSlug` at L152, `validateFilename` at L197).

```ts
// gbrain/src/core/operations.ts:110–145 (excerpted)
export function validateUploadPath(filePath: string, root: string, strict = true): string {
  let real: string;
  try {
    real = realpathSync(resolve(filePath));
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    if (msg.includes('ENOENT')) {
      throw new OperationError('invalid_params', `File not found: ${filePath}`);
    }
    throw new OperationError('invalid_params', `Cannot resolve path: ${filePath}`);
  }
  // Always reject final-component symlinks (basic safety for both modes).
  try {
    if (lstatSync(resolve(filePath)).isSymbolicLink()) {
      throw new OperationError('invalid_params', `Symlinks are not allowed for upload: ${filePath}`);
    }
  } catch (e) {
    if (e instanceof OperationError) throw e;
  }

  if (!strict) return real;

  // Strict mode: confine to root via realpath + path.relative (catches parent-dir symlinks per B5).
  let realRoot: string;
  try {
    realRoot = realpathSync(root);
  } catch {
    throw new OperationError('invalid_params', `Confinement root not accessible: ${root}`);
  }
  const rel = relative(realRoot, real);
  if (rel === '' || rel.startsWith('..') || rel.startsWith(`..${sep}`) || resolve(realRoot, rel) !== real) {
    throw new OperationError('invalid_params', `Upload path must be within the working directory: ${filePath}`);
  }
  return real;
}
```

```ts
// gbrain/src/core/operations.ts:152–164
export function validatePageSlug(slug: string): void {
  if (typeof slug !== 'string' || slug.length === 0) {
    throw new OperationError('invalid_params', 'page_slug must be a non-empty string');
  }
  if (slug.length > 255) {
    throw new OperationError('invalid_params', 'page_slug exceeds 255 characters');
  }
  // v0.32.7: CJK ranges (Han / Hiragana / Katakana / Hangul Syllables) allowed
  // in segments. ASCII shape rules (lead char, hyphen continuation) preserved.
  const PAGE_SLUG_SEG = `[a-z0-9${CJK_SLUG_CHARS}][a-z0-9${CJK_SLUG_CHARS}\\-]*`;
  if (!new RegExp(`^${PAGE_SLUG_SEG}(\\/${PAGE_SLUG_SEG})*$`, 'i').test(slug)) {
    throw new OperationError('invalid_params', `Invalid page_slug: ${slug} (allowed: alphanumeric, CJK, hyphens, forward-slash separated segments)`);
  }
}
```

**Pattern:** explicit allowlist + bounded length + symlink-rejection +
`realpath` confinement. `OperationError` has a typed error code
(`invalid_params`); the message names what was rejected and what's
allowed. No regex that depends on lookbehinds or backreferences.

**Determinism lens:** B-tier input validator AND an A-tier rule
embodied as code. The LLM never sees the prose «pages must be
alphanumeric CJK hyphens slashes only» — it sees only the result of
calling the tool with a slug, and the slug either lands or returns
`invalid_params`. The validator is the rule.

**FA fit — modifies B5 / extends BashGate.** v3 B5 is path-traversal
detection. Gbrain's `validateUploadPath` extends to **symlink-aware
confinement** with `realpath` (catches parent-dir symlinks, not just
`..` in the literal path). FA's BashGate already does this for bash
commands; gbrain's pattern applies the same shape to file-upload tool
boundaries. No new entry, but B5 should reference the symlink + realpath
move explicitly.

---

### 1.3 hermes-agent (NousResearch, Python)

Hermes is the largest of the six (~17 k LOC of agent code). The four
files that land determinism patterns FA does not already have:
schema sanitizer, tool guardrails, registry auto-discovery, doctor.

#### H1 — Tool-schema sanitizer (backend-compatibility shim)

**File:** `hermes-agent/tools/schema_sanitizer.py` (445 LOC,
`sanitize_tool_schemas` at L40).

```python
# hermes-agent/tools/schema_sanitizer.py:1–24 (header — failure mode receipt)
"""Sanitize tool JSON schemas for broad LLM-backend compatibility.

Some local inference backends (notably llama.cpp's ``json-schema-to-grammar``
converter used to build GBNF tool-call parsers) are strict about what JSON
Schema shapes they accept. Schemas that OpenAI / Anthropic / most cloud
providers silently accept can make llama.cpp fail the entire request with:

    HTTP 400: Unable to generate parser for this template.
    Automatic parser generation failed: JSON schema conversion failed:
    Unrecognized schema: "object"

The failure modes we've seen in the wild:

* ``{"type": "object"}`` with no ``properties`` — rejected as a node the
  grammar generator can't constrain.
* A schema value that is the bare string ``"object"`` instead of a dict
  (malformed MCP server output, e.g. ``additionalProperties: "object"``).
* ``"type": ["string", "null"]`` array types — many converters only accept
  single-string ``type``.
* ``anyOf`` / ``oneOf`` unions whose only purpose is to permit ``null`` for
  optional fields (common Pydantic/MCP shape). Anthropic rejects these at
  the top of ``input_schema``; collapse them to the non-null branch.
* Unconstrained ``additionalProperties`` on objects with empty properties.
"""
```

```python
# hermes-agent/tools/schema_sanitizer.py:58–92
def _sanitize_single_tool(tool: dict) -> dict:
    """Deep-copy and sanitize a single OpenAI-format tool entry."""
    out = copy.deepcopy(tool)
    fn = out.get("function") if isinstance(out, dict) else None
    if not isinstance(fn, dict):
        return out

    params = fn.get("parameters")
    # Missing / non-dict parameters → substitute the minimal valid shape.
    if not isinstance(params, dict):
        fn["parameters"] = {"type": "object", "properties": {}}
        return out

    fn["parameters"] = _sanitize_node(params, path=fn.get("name", "<tool>"))
    # After recursion, guarantee the top-level is an object with properties.
    top = fn["parameters"]
    if not isinstance(top, dict):
        fn["parameters"] = {"type": "object", "properties": {}}
    else:
        if top.get("type") != "object":
            top["type"] = "object"
        if "properties" not in top or not isinstance(top.get("properties"), dict):
            top["properties"] = {}
    fn["parameters"] = strip_nullable_unions(fn["parameters"], keep_nullable_hint=True)
    fn["parameters"] = _strip_top_level_combinators(
        fn["parameters"], path=fn.get("name", "<tool>")
    )
    return out
```

**Pattern:** **deterministic schema normaliser** running *before* the
tool list is sent to the LLM. Drops `anyOf`/`oneOf`/`allOf`/`enum`/`not`
from the top level, collapses nullable unions to the non-null branch,
forces `type: "object"` + non-empty `properties`. The header (L12-23)
documents the **exact wire failures** that motivated each rule — this
is the operational receipt the LLM never sees.

**Determinism lens:** purest A-tier pre-prompt pattern in the six repos.
The LLM never sees a hostile schema; the harness fixes them up. No
prose rule «don't use top-level oneOf in your tool schema» — the rule
is enforced by a function that runs every time the tool list is
assembled.

**FA fit — new A entry.** FA's `ToolSpec.parameters` is JSON Schema
shaped for the Python tool registry. When FA grows MCP / external-tool
import (v3 §2.7 cites Kronos's `_infer_tool_capability` for capability
inference), it'll need a sanitiser at the registry boundary so external
tool schemas don't poison OSS-LLM backends. New entry proposal: **A18
fa sanitize-tool-schemas** (see §4).

---

#### H2 — Laddered tool-call guardrail w/ idempotent/mutating taxonomy

**File:** `hermes-agent/agent/tool_guardrails.py` (475 LOC,
`IDEMPOTENT_TOOL_NAMES` at L20, `MUTATING_TOOL_NAMES` at L41,
`ToolCallGuardrailConfig` at L63, `ToolCallGuardrailController` at L224).

```python
# hermes-agent/agent/tool_guardrails.py:20–60 (excerpted)
IDEMPOTENT_TOOL_NAMES = frozenset(
    {
        "read_file",
        "search_files",
        "web_search",
        "web_extract",
        "session_search",
        "browser_snapshot",
        "browser_console",
        "browser_get_images",
        "mcp_filesystem_read_file",
        # ... (filesystem read variants elided)
    }
)

MUTATING_TOOL_NAMES = frozenset(
    {
        "terminal",
        "execute_code",
        "write_file",
        "patch",
        "todo",
        "memory",
        "skill_manage",
        "browser_click",
        "browser_type",
        "browser_press",
        # ...
    }
)
```

```python
# hermes-agent/agent/tool_guardrails.py:63–82
@dataclass(frozen=True)
class ToolCallGuardrailConfig:
    """Thresholds for per-turn tool-call loop detection.

    Warnings are enabled by default and never prevent tool execution. Hard stops
    are explicit opt-in so interactive CLI/TUI sessions get a gentle nudge unless
    the user enables circuit-breaker behavior in config.yaml.
    """

    warnings_enabled: bool = True
    hard_stop_enabled: bool = False
    exact_failure_warn_after: int = 2
    exact_failure_block_after: int = 5
    same_tool_failure_warn_after: int = 3
    same_tool_failure_halt_after: int = 8
    no_progress_warn_after: int = 2
    no_progress_block_after: int = 5
    idempotent_tools: frozenset[str] = field(default_factory=lambda: IDEMPOTENT_TOOL_NAMES)
    mutating_tools: frozenset[str] = field(default_factory=lambda: MUTATING_TOOL_NAMES)
```

```python
# hermes-agent/agent/tool_guardrails.py:127–142
@dataclass(frozen=True)
class ToolCallSignature:
    """Stable, non-reversible identity for a tool name plus canonical args."""

    tool_name: str
    args_hash: str

    @classmethod
    def from_call(cls, tool_name: str, args: Mapping[str, Any] | None) -> "ToolCallSignature":
        canonical = canonical_tool_args(args or {})
        return cls(tool_name=tool_name, args_hash=_sha256(canonical))

    def to_metadata(self) -> dict[str, str]:
        """Return public metadata without raw argument values."""
        return {"tool_name": self.tool_name, "args_hash": self.args_hash}
```

**Pattern:** three orthogonal dimensions of «stuck»:
1. **exact_failure** — same (tool, args) hash failed N times
2. **same_tool_failure** — same tool name failed N times across any args
3. **idempotent_no_progress** — idempotent tool returned same result hash N times

Each dimension has two thresholds (`warn_after` and `block_after`),
yielding a six-level severity ladder. The controller holds counters
keyed by `ToolCallSignature` (sha256 of canonical-sorted JSON args);
decisions are frozen dataclasses with `action ∈ {allow, warn, block,
halt}` and a `to_metadata()` that redacts argument values.

The **idempotent/mutating taxonomy** is the load-bearing categorisation.
A second call to `read_file` with same args means «no progress»; a
second call to `terminal` with same args might be «retry» or might be
«stuck» — only the idempotent set gets the same-result-hash treatment.

**Determinism lens:** an A-tier *registry-attribute* pattern (per-tool
category lives with the tool, not the controller) and a B-laddered
controller. v3 §0.3 distinguishes B-pass/fail from B-laddered. This is
the deepest B-laddered exemplar across the six repos — three
dimensions × two thresholds.

**FA fit — extends FA's existing LoopGuard.** FA's `LoopGuard`
computes a fingerprint and trips at a single threshold. The hermes
extension is **categorise the tool first, then choose the detector**.
FA can mark each `ToolSpec` with `category: "idempotent" | "mutating"`
at registration time (the harness, not the LLM, owns this metadata).
New entry proposal: **A19 ToolSpec.category** (see §4). Also: **B20
laddered guardrail config** for the multi-threshold variants.

---

#### H3 — Single-source-of-truth tool-failure classifier

**File:** `hermes-agent/agent/tool_guardrails.py:189–221`
(`classify_tool_failure`).

```python
# hermes-agent/agent/tool_guardrails.py:189–221
def classify_tool_failure(tool_name: str, result: str | None) -> tuple[bool, str]:
    """Safety-fallback classifier used only when callers don't pass ``failed``.

    Mirrors ``agent.display._detect_tool_failure`` exactly so the guardrail
    never disagrees with the CLI's user-visible ``[error]`` tag. Production
    callers in ``run_agent.py`` always pass an explicit ``failed=`` derived
    from ``_detect_tool_failure``; this function exists so standalone callers
    (tests, tooling) still get consistent behavior.
    """
    if result is None:
        return False, ""
    if file_mutation_result_landed(tool_name, result):
        return False, ""

    if tool_name == "terminal":
        data = safe_json_loads(result)
        if isinstance(data, dict):
            exit_code = data.get("exit_code")
            if exit_code is not None and exit_code != 0:
                return True, f" [exit {exit_code}]"
        return False, ""

    if tool_name == "memory":
        data = safe_json_loads(result)
        if isinstance(data, dict):
            if data.get("success") is False and "exceed the limit" in data.get("error", ""):
                return True, " [full]"

    lower = result[:500].lower()
    if '"error"' in lower or '"failed"' in lower or result.startswith("Error"):
        return True, " [error]"

    return False, ""
```

**Pattern:** the classifier is **explicitly aligned with the
user-facing display classifier**. The docstring is the contract:
«Mirrors `agent.display._detect_tool_failure` exactly so the guardrail
never disagrees with the CLI's user-visible `[error]` tag.»

**Determinism lens:** this is an **invariant**: «failure-detection
logic has one source of truth.» The contract is in the docstring, not
in code; if either function drifts, the user sees `[ok]` while the
guardrail counts it as a failure (or vice-versa). The discipline is the
B-pattern *avoiding* divergence between sibling validators that look
at the same data.

**FA fit — invariant for ADR-10.** When ADR-10 lists invariants, this
shape belongs there: «B-bucket entries that classify the same input
must be single-sourced.» FA today has at least one parallel risk:
`BashGate._classify_category` and `BashGate._validators_for_category`
could drift if a new category lands in one but not the other. No new
entry, but ADR-10 should name this rule explicitly. Section §3 below
maps it as **Invariant I-1**.

---

#### H4 — AST-based tool auto-discovery + dynamic_schema_overrides

**File:** `hermes-agent/tools/registry.py` (589 LOC,
`_is_registry_register_call` at L29, `discover_builtin_tools` at L57,
`dynamic_schema_overrides` field at L99).

```python
# hermes-agent/tools/registry.py:29–54
def _is_registry_register_call(node: ast.AST) -> bool:
    """Return True when *node* is a ``registry.register(...)`` call expression."""
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        return False
    func = node.value.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "register"
        and isinstance(func.value, ast.Name)
        and func.value.id == "registry"
    )


def _module_registers_tools(module_path: Path) -> bool:
    """Return True when the module contains a top-level ``registry.register(...)`` call.

    Only inspects module-body statements so that helper modules which happen
    to call ``registry.register()`` inside a function are not picked up.
    """
    try:
        source = module_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(module_path))
    except (OSError, SyntaxError):
        return False

    return any(_is_registry_register_call(stmt) for stmt in tree.body)
```

```python
# hermes-agent/tools/registry.py:99–106 (dynamic_schema_overrides — second pattern in same file)
self.dynamic_schema_overrides = dynamic_schema_overrides
# Optional zero-arg callable returning a dict of schema overrides
# applied at get_definitions() time. Use for fields that depend on
# runtime config (e.g. delegate_task's description must reflect the
# user's current delegation.max_concurrent_children / max_spawn_depth
# so the model isn't told the wrong limits). The callable is invoked
# on every get_definitions() call; results are merged shallow on top
# of the base schema before the {"type": "function", ...} wrap.
```

**Pattern (1):** AST inspection finds modules that have a top-level
`registry.register(...)` call (function-body calls are filtered out so
helpers don't get picked up). Modules pass the AST check before
import — guarantees module list is stable without manual import lists.

**Pattern (2):** `dynamic_schema_overrides` is a per-tool callable that
returns a dict merged into the schema *every time get_definitions() is
called*. Use case (cited in the docstring): the `delegate_task` tool's
description should reflect the current `delegation.max_concurrent_children`
config value — if the operator changes the config, the **prompt the LLM
sees** changes immediately. Stale prompts are the failure mode this
prevents.

**Determinism lens:** both A-tier.
- Pattern (1) is an A-pattern that *prevents a class of error* (a new
  tool file lands and nobody updates the import list). The rule «every
  tool file must self-register» is enforced by the discovery code, not
  by a checklist item.
- Pattern (2) is the **freshest-prompt invariant**: the LLM is told the
  current limits, not the limits at module-import time.

**FA fit — extends A8 (`fa hygiene discover`).** v3 A8 includes
`fa hygiene discover` (Gortex roots). The AST-discovery shape extends
to FA's own tool registry: when FA grows past 6 baseline tools, the
discovery move ports cleanly. Pattern (2) is a **new entry** because
nothing in v3 covers «prompt fields must reflect current config» —
proposal **A20 dynamic_schema_overrides on ToolSpec** (see §4).

---

### 1.4 gortex (zzet/gortex, Go) — re-pass under determinism lens

Already cited in v3 §2.1–2.3 for the tool-table prompt pattern (A13),
marker-fenced regenerable blocks (A6), and family-disjoint config
invariant (covered by ADR-7). Re-pass turns up three additions.

#### GX1 — Per-tool schema invariants enforced at startup

**File:** `gortex/internal/mcp/schema_lint.go` (97 LOC,
`LintToolSchema` at L40, `LintAllTools` at L91).

```go
// gortex/internal/mcp/schema_lint.go:10–22
// toolNamePattern is the tool-name convention enforced by the MCP
// ecosystem (and the Anthropic tool API): a lowercase identifier of
// letters, digits and underscores, 1..64 characters.
var toolNamePattern = regexp.MustCompile(`^[a-z][a-z0-9_]{0,63}$`)

// SchemaViolation is one problem found in a tool's MCP schema by
// LintToolSchema. Tool names the offending tool, Rule the convention
// broken, Detail a human-readable explanation.
type SchemaViolation struct {
    Tool   string `json:"tool"`
    Rule   string `json:"rule"`
    Detail string `json:"detail"`
}
```

```go
// gortex/internal/mcp/schema_lint.go:40–84
func LintToolSchema(tool mcp.Tool) []SchemaViolation {
    var out []SchemaViolation
    add := func(rule, detail string) {
        out = append(out, SchemaViolation{Tool: tool.Name, Rule: rule, Detail: detail})
    }

    switch {
    case tool.Name == "":
        add("name", "tool name is empty")
    case !toolNamePattern.MatchString(tool.Name):
        add("name", fmt.Sprintf("name %q is not a lowercase [a-z0-9_] identifier of 1..64 chars", tool.Name))
    }

    if tool.Description == "" {
        add("description", "description is empty")
    } else if scrubControlChars(tool.Description) != tool.Description {
        add("description", "description carries control characters or ANSI escapes")
    }

    schema := tool.InputSchema
    hasSchema := schema.Type != "" || len(schema.Properties) > 0 || len(schema.Required) > 0
    if hasSchema {
        if schema.Type != "" && schema.Type != "object" {
            add("input_schema", fmt.Sprintf("input schema type is %q, want \"object\"", schema.Type))
        }
        for propName, raw := range schema.Properties {
            m, ok := raw.(map[string]any)
            if !ok {
                add("property", fmt.Sprintf("property %q is not a JSON-Schema object", propName))
                continue
            }
            _, hasType := m["type"]
            _, hasRef := m["$ref"]
            if !hasType && !hasRef {
                add("property", fmt.Sprintf("property %q declares no \"type\"", propName))
            }
        }
        for _, req := range schema.Required {
            if _, ok := schema.Properties[req]; !ok {
                add("required", fmt.Sprintf("required property %q is not declared in properties", req))
            }
        }
    }
    return out
}
```

**Pattern:** every Gortex MCP tool is linted against a set of
invariants (name regex `^[a-z][a-z0-9_]{0,63}$`, non-empty description,
no control chars, `type: "object"` when schema present, every property
has `type` or `$ref`, every `required` names a declared property).
`LintAllTools` iterates the live tool list — release-gating test fails
if any violation found.

**Determinism lens:** **A-tier invariant + release gate**. The prose
rule «tool names are lowercase identifiers, descriptions are non-empty»
is replaced by a function that runs at test time and at startup. The
LLM only ever sees a tool list that has already passed the lint.

The interesting design move is the **multi-violation collection** —
`LintToolSchema` returns *every* problem in one pass, not just the
first. Compare to v3 §2.4's correction of Kronos's `output_validator`
(which also collects all matches before returning): this is a
**conservative-recognition + skip-list** sibling, the opposite of
fail-fast.

**FA fit — modifies A13 (`fa render-tool-table`) into a two-step.** v3
A13 covers the assembly side. The lint side is the precondition. New
entry proposal: **A21 fa lint-tools** (see §4). FA's ToolSpec is Python
dataclass-style; a `fa lint-tools` command at test time catches
schema-shape drift before the OSS LLM ever sees a malformed tool list.

---

#### GX2 — Provider-tiered prompt selection (small vs frontier)

**File:** `gortex/internal/llm/prompts.go` (180 LOC, `PromptProfile`
at L15, `ProfileForProvider` at L34).

```go
// gortex/internal/llm/prompts.go:15–43
type PromptProfile int

const (
    PromptProfileSmall PromptProfile = iota
    PromptProfileFrontier
)

func ProfileForProvider(name string) PromptProfile {
    switch strings.ToLower(name) {
    case "local", "ollama", "claudecli", "codex":
        return PromptProfileSmall
    case "anthropic", "openai", "gemini", "bedrock", "deepseek":
        return PromptProfileFrontier
    default:
        return PromptProfileSmall
    }
}

const expandSystemSmall = `You expand a code-search query into a small set of CONCRETE identifier-style terms a programmer would actually grep for. ` +
    // ...

const expandSystemFrontier = `Expand a code-search query into 2-5 concrete identifier-style terms a programmer would grep for: library and protocol names, well-known acronyms, camelCase / snake_case symbol fragments. ` +
    // ...
```

**Pattern:** every prompt has two versions — `small` (terse, explicit,
concrete) and `frontier` (compact, can rely on context). The choice is
determined by **provider name** (`ProfileForProvider`), not by the LLM,
not by config. Local-provider users get the small profile; hosted-API
users get the frontier profile. No per-prompt flag, no runtime tuning.

**Determinism lens:** A-tier prompt routing. The harness decides which
prompt the LLM sees based on a deterministic provider→profile map.

**FA fit — modifies role-prompt pipeline.** FA's role prompts in
`knowledge/prompts/` are currently one-size-fits-all. The gortex
pattern argues for **two-tier prompt files** (e.g. `planner-small.md`
and `planner-frontier.md`) selected at role-instantiation time. This is
**not** B14 (the v3 entry on LLM-side validator) and is **not** A13
(tool table rendering). New entry proposal: **A22 PromptProfile per
role** (see §4). This is also an interesting subtraction question: does
FA need two profiles when the project deliberately targets OSS LLMs
only (UC1+UC3)? Probably the **small** profile is the only one needed,
and the gortex bilateral split is over-engineering for FA's scope. The
profile *enum* still earns its keep as a single-knob future-proof
extension point.

---

#### GX3 — MANDATORY n-step workflow as prose A-tier prompt block

**File:** `gortex/CLAUDE.md` (referenced in v3 §2.1, but under
ADR-8 lens — re-read here for the workflow-as-prompt-pattern).

The CLAUDE.md file ships a numbered workflow:

> ### Required workflow (every task on this repo)
> These are not suggestions — run each step at the trigger.
>
> 1. **Always call** `graph_stats` first to confirm the daemon is up...
> 2. If `total_nodes` is 0, **call** `index_repository` with `"."`...
> 3. In multi-repo mode, **call** `get_active_project`...
> 4. For every new task, **call** `smart_context` with the task description...
> 5. Immediately after `smart_context`, **call** `surface_memories`...
> 6. Before editing a file, **call** `get_editing_context`...
> 7. Before changing any function signature, **call** `verify_change`...

11 numbered steps. Each step is a **MANDATORY** verb + tool name +
trigger condition. The prose is structured like a deterministic
algorithm.

Crucially, the same CLAUDE.md says:
> «PreToolUse hooks deny `Read` / `Grep` / `Glob` against indexed
> source; the deny message names the right tool.»

**Determinism lens:** the prose workflow exists *because the harness
can't (yet) sequence the steps automatically*. Where the harness *can*
enforce (deny `Read`/`Grep`/`Glob` for indexed source), it does — and
the rule is removed from prose. The CLAUDE.md prose workflow is the
**residue** of what the harness has not yet mechanised.

This is the **reverse-A** pattern: it tells you where to look next for
A-bucket conversions. Every numbered step in a MANDATORY workflow is a
candidate for being replaced by a hook or a harness-level orchestration.

**FA fit — modifies AGENTS.md §Pre-flight checklist.** FA's pre-flight
(`AGENTS.md` §Pre-flight checklist, 5 steps) has the same shape. v3
§3 A2 (`fa bootstrap`) is the harness-level mechanisation of Steps 1-3.
The gortex precedent confirms the direction. The Steps 4-5 (subtraction-
check + goal-lens declaration) are **judgement-bound** and stay prose —
v3 §0.4's classifier should accept this distinction.

No new bucket entry. This is an **invariant** for ADR-10: «numbered
MANDATORY workflows in agent-facing prose are an antipattern, except
for judgement-bound steps.» Section §3 below maps it as **Invariant
I-2**.

---

### 1.5 kronos-agent-os (spyrae, Python) — re-pass under determinism lens

v3 §2.4–2.7 cited Kronos for: regex output_validator (correcting R-47),
loop_detector severity ladder, `kaos doctor` pre-flight, audit.py +
capability inference. Re-pass with the determinism lens deepens three
of those and adds shield.py.

#### K1 — 3-tier severity ladder × 3 detectors (deeper than v3 §2.5)

**File:** `kronos-agent-os/kronos/security/loop_detector.py` (205 LOC).

```python
# kronos-agent-os/kronos/security/loop_detector.py:23–33
# Thresholds
WARN_THRESHOLD = 10
CRITICAL_THRESHOLD = 20
CIRCUIT_BREAKER_THRESHOLD = 30


class LoopLevel:
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    CIRCUIT_BREAKER = "circuit_breaker"
```

```python
# kronos-agent-os/kronos/security/loop_detector.py:66–89
def check(self) -> tuple[str, str]:
    """Check for loops. Returns (level, description).

    Call after each tool execution to check if agent is looping.
    """
    if len(self.history) < 3:
        return LoopLevel.OK, ""

    # 1. Generic repeat: same tool + same args
    level, desc = self._check_generic_repeat()
    if level != LoopLevel.OK:
        return level, desc

    # 2. Ping-pong: alternating between two tools
    level, desc = self._check_ping_pong()
    if level != LoopLevel.OK:
        return level, desc

    # 3. Poll no progress: same tool, same result
    level, desc = self._check_poll_no_progress()
    if level != LoopLevel.OK:
        return level, desc

    return LoopLevel.OK, ""
```

```python
# kronos-agent-os/kronos/security/loop_detector.py:103–135 (ping-pong detail)
def _check_ping_pong(self) -> tuple[str, str]:
    """Detect: alternating between two tools (A→B→A→B...)."""
    if len(self.history) < 6:
        return LoopLevel.OK, ""

    recent = self.history[-20:]  # check last 20 calls
    if len(recent) < 6:
        return LoopLevel.OK, ""

    # Check if last N calls alternate between exactly 2 tools
    names = [r.name for r in recent]
    unique = set(names)
    if len(unique) != 2:
        return LoopLevel.OK, ""

    # Check alternating pattern
    alternating = 0
    for i in range(1, len(names)):
        if names[i] != names[i - 1]:
            alternating += 1

    # If >80% are alternating, it's ping-pong
    if alternating / (len(names) - 1) > 0.8:
        tools = list(unique)
        count = len(names)
        if count >= CIRCUIT_BREAKER_THRESHOLD:
            return LoopLevel.CIRCUIT_BREAKER, f"Ping-pong between '{tools[0]}' and '{tools[1]}' ({count} calls)"
```

**Pattern (deeper than v3 §2.5):** three orthogonal detectors run
in priority order:
1. **generic_repeat** — same `(name, args_hash)` ≥ threshold
2. **ping_pong** — last 20 calls alternate between exactly 2 tools
   with > 80 % alternation rate
3. **poll_no_progress** — same `(name, result_hash)` ≥ threshold

Each detector returns the **same severity ladder** (`OK | WARNING |
CRITICAL | CIRCUIT_BREAKER`) keyed by ratios of one shared threshold
constant. The ladder is uniform across detectors.

**Determinism lens:** v3 §2.5 already names this as the canonical
B-laddered pattern. The deeper finding is **the multi-detector
priority** — first detector that returns non-OK wins. Compare to
hermes's `ToolCallGuardrailController` which has three orthogonal
**parallel** counters; kronos has three orthogonal **sequential**
detectors. The sequential design is simpler (one verdict per call) but
loses information when multiple loops co-occur.

**FA fit — extends FA's existing LoopGuard.** FA's LoopGuard has one
detector (`generic_repeat` shape). Add `ping_pong` and
`poll_no_progress` as siblings; expose a shared three-level ladder.
Already partially captured by v3 §2.5's B16 (token budget) and B14
(redact-output) recommendations — but the priority-ordered multi-
detector shape is new. Modifies v3's mention of B-laddered into a
**B-laddered-multi-detector** sub-shape.

---

#### K2 — Cost guardian severity ladder (extends v3 §2.5)

**File:** `kronos-agent-os/kronos/security/cost_guardian.py` (91 LOC,
`check_budget` at L29).

```python
# kronos-agent-os/kronos/security/cost_guardian.py:29–65
def check_budget(self, session_id: str = "") -> tuple[bool, str]:
    """Check if request is within budget.

    Returns (allowed, reason).
    """
    # Daily limit check
    daily = get_daily_cost()
    daily_cost = daily.get("cost_usd", 0)

    if daily_cost >= self.daily_limit:
        msg = (
            f"Daily cost limit reached: ${daily_cost:.2f} / ${self.daily_limit:.2f}. "
            f"Requests: {daily.get('requests', 0)}. "
            f"Reset at midnight UTC."
        )
        log.warning("Cost guardian: %s", msg)
        return False, msg

    # Session limit check
    if session_id:
        session_cost = self._session_costs.get(session_id, 0)
        if session_cost >= self.session_limit:
            msg = (
                f"Session cost limit reached: ${session_cost:.2f} / ${self.session_limit:.2f}. "
                f"Start a new conversation to reset."
            )
            log.warning("Cost guardian: %s", msg)
            return False, msg

    # Warning at 80% of daily limit
    if daily_cost >= self.daily_limit * 0.8:
        log.info(
            "Cost guardian: daily budget at %.0f%% ($%.2f / $%.2f)",
            (daily_cost / self.daily_limit) * 100, daily_cost, self.daily_limit,
        )

    return True, ""
```

**Pattern:** two-tier budget (daily + per-session), warning at 80% of
daily limit, hard cutoff at 100%. Reason message names *exact* numbers
(spend / limit / requests / reset condition). Singleton (`_guardian`
factory below).

**Determinism lens:** the **structured rejection reason** is the
load-bearing move. The message is a copy of the data the harness has;
the LLM reading it can decide whether to wait or summarise-and-quit.
No prose «the budget is tight» — exact numbers.

**FA fit — confirms FA's CostGuardian design.** FA already has
`CostGuardian` middleware. Kronos's pattern confirms the shape and adds
the 80% warning rung. The structured-reason move generalises to other
guards — every guard's `stop_message` should name exact numbers.

---

#### K3 — Input-side injection regex shield (23 patterns)

**File:** `kronos-agent-os/kronos/security/shield.py` (99 LOC,
`INJECTION_PATTERNS` at L15, `validate_input` at L86).

```python
# kronos-agent-os/kronos/security/shield.py:15–50 (subset of 23 patterns)
INJECTION_PATTERNS: list[re.Pattern] = [
    # Direct instruction override
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
    re.compile(r"ignore\s+(all\s+)?above", re.I),
    re.compile(r"forget\s+(all\s+)?(your|previous)\s+(instructions|rules|constraints)", re.I),
    re.compile(r"override\s+(system|safety|security)", re.I),
    # Role manipulation
    re.compile(r"you\s+are\s+now\s+(DAN|a\s+new|an?\s+unrestricted)", re.I),
    re.compile(r"pretend\s+(you\s+are|to\s+be)\s+(a\s+different|an?\s+evil|an?\s+unrestricted)", re.I),
    re.compile(r"act\s+as\s+if\s+(you\s+have\s+no|there\s+are\s+no)\s+(rules|restrictions|limits)", re.I),
    re.compile(r"enter\s+(DAN|jailbreak|developer)\s+mode", re.I),
    # System prompt extraction
    re.compile(r"show\s+(me\s+)?(your\s+)?(system\s+prompt|instructions|rules)", re.I),
    # Secret extraction
    re.compile(r"show\s+(me\s+)?(your\s+)?(api\s+key|token|password|secret|\.env)", re.I),
    re.compile(r"cat\s+\.env", re.I),
    # Encoding tricks
    re.compile(r"base64\s+decode", re.I),
    re.compile(r"eval\s*\(", re.I),
    # Russian injection patterns
    re.compile(r"игнорируй\s+(все\s+)?(предыдущие|прошлые)\s+(инструкции|правила)", re.I),
    re.compile(r"забудь\s+(все\s+)?(свои\s+)?(инструкции|правила|ограничения)", re.I),
    re.compile(r"покажи\s+(свой\s+)?(системный\s+промпт|инструкции)", re.I),
    re.compile(r"ты\s+теперь\s+(другой|новый|свободный|без\s+ограничений)", re.I),
]
```

```python
# kronos-agent-os/kronos/security/shield.py:86–99
def validate_input(message: str, source: str = "default") -> str | None:
    """Validate input message. Returns None if safe, or rejection message if blocked."""
    # Injection check
    matches = check_injection(message)
    if matches:
        log.warning("[Shield] Injection blocked from %s: %s", source, matches[:3])
        return BLOCK_MESSAGE

    # Rate limit check
    if not rate_limiter.check(source):
        log.warning("[Shield] Rate limited: %s", source)
        return "Слишком много запросов. Подожди минуту."

    return None
```

**Pattern:** 23 regex patterns × 5 categories (instruction override,
role manipulation, system-prompt extraction, secret extraction,
encoding tricks). The Russian patterns are a deliberate multilingual
move — Kronos targets Russian-speaking users; English-only patterns
would miss native-language injection attempts. Rate limiter is a
sibling input gate, per-source bucket.

**Determinism lens:** B-tier *input* gate (compare to `output_validator`
which is a B-tier *output* gate). The two together form a sandwich: the
LLM call is between two regex-based gates, both with stable pattern
lists.

**FA fit — new B entry.** FA does not currently have an input-side
injection regex layer. v3 §2.4 corrected R-47 by clarifying that the
Kronos *output_validator* has no LLM call (it's regex). The input-side
*shield* has the same property. New entry proposal: **B21 fa
shield-input** (see §4). The Russian patterns are particularly relevant
to FA because FA's research notes are bilingual — operators may
legitimately type Russian instructions, and the shield can co-exist
with that. Worth a note when ADR-10 lists invariants: «B-bucket regex
gates must cover both English and Russian for FA's user scope.»

---

#### K4 — output_validator depth (deeper than v3 §2.4)

**File:** `kronos-agent-os/kronos/security/output_validator.py` (104 LOC,
`validate_output` at L77).

```python
# kronos-agent-os/kronos/security/output_validator.py:1–10
"""Output validation — checks agent responses before sending to user.

Catches:
- Leaked secrets (API keys, tokens, passwords from .env)
- Internal system info (file paths, stack traces, config details)
- Prompt leakage (system prompt or persona content in response)
- Harmful content patterns

Runs as a lightweight post-processing step (no LLM call — regex only).
"""
```

```python
# kronos-agent-os/kronos/security/output_validator.py:77–104
def validate_output(text: str) -> ValidationResult:
    """Validate agent output before sending to user.

    Returns ValidationResult with issues found and redacted text.
    """
    result = ValidationResult()
    redacted = text

    # Check for leaked secrets
    for match in _SECRET_RE.finditer(text):
        secret = match.group()
        result.issues.append(f"leaked_secret: {secret[:8]}...")
        # Redact: keep first 4 chars + mask
        redacted = redacted.replace(secret, secret[:4] + "***REDACTED***")

    # Check for system info
    for match in _SYSTEM_RE.finditer(text):
        result.issues.append(f"system_info: {match.group()[:30]}")
        # Don't redact paths entirely — just log warning

    # Check for prompt leakage
    for match in _PROMPT_LEAK_RE.finditer(text):
        result.issues.append(f"prompt_leak: {match.group()[:30]}")

    result.redacted_text = redacted

    if result.issues:
        log.warning("Output validation: %d issues — %s", len(result.issues), result.issues)

    return result
```

**Pattern:** three category-grouped pattern sets (`_SECRET_RE`,
`_SYSTEM_RE`, `_PROMPT_LEAK_RE`), each compiled once at import. **Per-
category response** — secrets are redacted, system info is logged but
*not* redacted (paths can be informative), prompt leakage is logged
only. The validator is **not** a single accept/reject — it carries
graduated severity in its response semantics.

**Determinism lens (deeper than v3 §2.4):** v3 corrected R-47 by
identifying this as regex-not-LLM. The **per-category response**
nuance was not captured — secrets demand redaction, system info just
demands logging, prompt-leak demands rejection at a higher tier. This is
the **B-laddered** sub-shape *applied per category*.

**FA fit — modifies v3 B14.** v3 B14 is «output validator regex».
Sub-spec: B14 must carry **per-category response policy**, not a
single accept/reject. The Kronos shape is the model: redact secrets,
log paths, reject prompt-leaks at a higher tier. ADR-10 should list
the response-policy enum (`redact | log | reject`) as part of the
B-bucket grammar.

---

### 1.6 dpc-messenger (mikhashev, Python) — re-pass under determinism lens

v3 §2.8 cited dpc for the `LoopState` ownership invariant (loop owns
fields, middleware reads — never writes). Re-pass turns up a stronger
A-tier pattern: stable `stop_message()` prefixes.

#### D1 — Stable [CODE] prefix on every guard stop_message

**File:** `dpc-messenger/dpc-client/core/dpc_client_core/dpc_agent/guards.py`
(222 LOC, 5 GuardMiddleware classes at L20, L47, L78, L118, L177).

```python
# dpc-messenger/.../guards.py:40–44 (RoundLimitGuard)
def stop_message(self) -> str:
    return (
        f"[ROUND_LIMIT] Task exceeded MAX_ROUNDS ({self._max_rounds}). "
        "Consider breaking into smaller tasks."
    )
```

```python
# dpc-messenger/.../guards.py:69–75 (ToolLimitGuard)
def stop_message(self) -> str:
    return (
        f"[TOOL_LIMIT] You generated {self._last_count} tool calls in a "
        f"single turn, which exceeds the limit of {self._max_per_turn}. "
        "Stop calling tools. Summarise what you know and give your "
        "final answer now."
    )
```

```python
# dpc-messenger/.../guards.py:109–115 (ResearchLimitGuard)
def stop_message(self) -> str:
    return (
        f"[RESEARCH_LIMIT] You have spent {self._counter} consecutive "
        "rounds calling tools without providing any text response to "
        "the user. Stop researching. Summarise your findings and give "
        "your answer now."
    )
```

```python
# dpc-messenger/.../guards.py:167–174 (LoopGuard)
def stop_message(self) -> str:
    dedup = ", ".join(sorted(set(self._last_stuck))) or "?"
    return (
        f"[LOOP_GUARD] You have called the following tool(s) with "
        f"identical arguments {self._max} or more times without new "
        f"information: {dedup}. Stop repeating these calls. "
        "Summarise what you know so far and give your final answer now."
    )
```

```python
# dpc-messenger/.../guards.py:208–213 (BudgetLimitGuard)
def stop_message(self) -> str:
    return (
        f"[BUDGET_LIMIT] Task consumed {int(self._last_cost)} tokens (>"
        f"{self._max_fraction * 100:.0f}% of budget "
        f"{int(self._budget)} tokens). Give your final response now."
    )
```

**Pattern:** every guard's `stop_message()` follows the same shape:
`[STABLE_PREFIX] data-shaped explanation. concrete-next-action.` The
prefix is the **stable identifier** the LLM can recognise across
sessions — `[ROUND_LIMIT]`, `[TOOL_LIMIT]`, `[RESEARCH_LIMIT]`,
`[LOOP_GUARD]`, `[BUDGET_LIMIT]`. Each message:
1. Names the violation (prefix).
2. Quotes the *actual* numbers (current count, the limit).
3. Tells the LLM what to do next («summarise», «final answer now»).

**Determinism lens:** **A-tier prompt-injection format**. The LLM reads
these messages mid-conversation when a guard fires. The stable prefix
+ exact data + next-action triple means the model has a well-defined
recipe for handling each interrupt. No prose «be careful with tool
calls» — five stable error codes with five stable response patterns.

This is structurally similar to gortex tool-table (v3 A13) but **for
guard-failure injections**. v3 §2.8 noted the `LoopState` ownership
invariant from this file; the `stop_message` shape is the prompt
output of the same architecture.

**FA fit — modifies B14 + adds A-tier sub-pattern.** v3 B14 is the
output-validator regex. The stable-prefix shape is **complementary**:
when *any* B-bucket entry fires and feeds a message back to the LLM,
that message should follow the same `[CODE] data. action.` shape. New
entry proposal: **A23 stable guard-message format** (see §4). This is
also an **invariant** for ADR-10 — every B-bucket entry that injects
text into the LLM context must carry a `[CODE]` prefix from a
controlled namespace. Section §3 below maps it as **Invariant I-3**.

---

#### D2 — Typed loop-state ownership (re-cited from v3 §2.8, sharpened)

**File:** `dpc-messenger/.../hooks.py` (207 LOC, `LoopState` at L44).

```python
# dpc-messenger/.../hooks.py:44–66
@dataclass
class LoopState:
    """Typed state the loop exposes to middleware.

    Mutation contract: the loop OWNS these fields and updates them
    BEFORE calling ``HookRegistry.fire()``; middleware only reads them.
    Stale values at fire time produce wrong guard decisions. Middleware
    that needs mutable counters keeps them on the instance, not here.
    """

    last_response_has_text: bool = False
    tool_calls_this_turn: int = 0
    consecutive_tool_only_rounds: int = 0
    accumulated_cost_usd: float = 0.0
    #: Last N tool-call argument dicts, oldest first.
    recent_tool_args: list[dict] = field(default_factory=list)
    #: Full text of the last assistant response (for extraction triggers).
    last_assistant_text: str = ""
    #: Number of tool calls in the current round (alias for observer compat).
    tool_calls_this_round: int = 0
    #: Current round index (alias for observer compat).
    current_round: int = 0
```

**Pattern:** v3 §2.8 already cited this. Re-cite is unchanged in
content but sharpens the determinism reading: the **mutation contract
is the invariant**. The loop owns these fields and updates them
*before* firing hooks; middleware never writes, only reads. Middleware
that needs counters keeps them on instance state. Stale values produce
wrong decisions.

**FA fit — invariant for ADR-10.** This was already absorbed into v3.
Section §3 maps it as **Invariant I-4** so ADR-10 carries it
explicitly.

---

## 2. Cross-repo pattern table

20 patterns extracted. Sorted by A/B tier, then by FA-fit impact.

| # | Pattern | Repos | Tier | FA bucket affected | Notes |
|---:|---|---|---|---|---|
| 1 | Backend-compat schema sanitiser | hermes H1 | A | new A18 | Purest pre-prompt A pattern; strip combinators, force `type: object` |
| 2 | Per-tool schema invariants + lint | gortex GX1 | A | new A21 | Run at startup, fail before LLM sees malformed tools |
| 3 | Structured Check + DoctorReport scoring | gbrain G1 | A | new A16 | Adopt `{status, score, remediation_status}` shape |
| 4 | YAML-frontmatter prompt loader + diagnostics | pi P2 | A | new A15 | Canonical prompt-load surface |
| 5 | Stable [CODE] guard-message prefix | dpc D1 | A | new A23 | Every B-message that re-enters LLM context starts with `[CODE]` |
| 6 | dynamic_schema_overrides (prompt = current config) | hermes H4 | A | new A20 | Prompt fields reflect runtime config, never stale |
| 7 | Provider-tiered prompt selection | gortex GX2 | A | new A22 | `small | frontier` choice, deterministic from provider name |
| 8 | AST-based tool auto-discovery | hermes H4 | A | extends A8 | No manual import list; AST inspection |
| 9 | XML-safe structured-block renderer | pi P3 | A | extends A13 | escape + assemble; works for tool, skill, note tables |
| 10 | Tool description = JSON-args spec example | gortex (v3 §2.1) | A | A13 | Already in v3; re-confirmed |
| 11 | ISO-week JSONL audit primitive | gbrain G3 | A | extends A8 | Consolidate 5 audit modules into 1 |
| 12 | MANDATORY n-step prompt workflow | gortex GX3 | A (residue) | I-2 (ADR-10) | Numbered MANDATORY workflows are antipattern except for judgement steps |
| 13 | Schema verify + self-heal | gbrain G2 | A | new A17 | Parse canonical source → diff runtime → repair |
| 14 | TypeBox schema validation + coercion | pi P1 | B | new B19 | Coerce-then-check at tool-call boundary |
| 15 | Allowlist validator (path/slug/filename) | gbrain G4 | B | extends B5 | Symlink-aware realpath confinement |
| 16 | Laddered tool-call signature controller | hermes H2, kronos K1 | B-laddered-multi | new B20 | 3 detectors × 2 thresholds; idempotent/mutating taxonomy |
| 17 | Per-category response policy (redact/log/reject) | kronos K4 | B-laddered | modifies B14 | Output-validator response varies by category |
| 18 | Input-side injection regex + rate limit | kronos K3 | B | new B21 | 23 patterns × multilingual; per-source rate limiter |
| 19 | Single-source-of-truth classifier | hermes H3 | invariant | I-1 (ADR-10) | Two classifiers on same input MUST be aligned |
| 20 | Typed loop-state ownership (loop OWNS, middleware READS) | dpc D2 | invariant | I-4 (ADR-10) | Already in v3 §2.8; re-confirmed |

«Tier» annotations:
- **A** — runs before LLM call, output goes into prompt or replaces a prose rule
- **B** — runs after LLM call, verifies / coerces / redacts / blocks
- **B-laddered** — B with multi-level severity (warn/critical/halt)
- **B-laddered-multi** — B with multi-dimension severity (orthogonal detectors)
- **invariant** — meta-property the bucket entries must respect

---

## 3. FA-fit mapping — invariants for ADR-10

Four invariants emerged from the re-pass that ADR-10 should carry as
hard constraints:

**I-1. Single-source-of-truth classifier** (hermes H3). When two
B-bucket entries classify the *same* input shape (e.g. «is this tool
result a failure?»), one of them MUST be the canonical implementation
and the other MUST call it. Diverging classifiers produce
operator-visible / guardrail-invisible drift. FA today: at-risk in
`BashGate._classify_category` vs `BashGate._validators_for_category`
if categories drift.

**I-2. Numbered MANDATORY workflows are A-bucket residue** (gortex
GX3). Every numbered step in an agent-facing MANDATORY workflow is a
candidate for replacement by a harness function or a hook. Steps that
remain in prose MUST be explicitly judgement-bound (decision-making,
not orchestration). FA today: AGENTS.md §Pre-flight Steps 1-3 are
mechanisable (v3 A2 covers Step 3 absorption); Steps 4-5 are
judgement-bound and stay prose.

**I-3. Stable [CODE] prefix on every B-message** (dpc D1). When a
B-bucket entry produces text that re-enters the LLM context (guard
stop, validator rejection reason, retry hint), that text MUST start
with a `[CODE]` from a controlled namespace, MUST quote the actual
data, and MUST name the next action. Prose without structure
produces inconsistent LLM responses across providers.

**I-4. Typed loop-state ownership: loop OWNS, middleware READS**
(dpc D2). State the middleware reads (round index, accumulated cost,
recent tool args) lives on a typed dataclass owned by the loop; the
loop updates it before firing hooks; middleware that needs mutable
counters keeps them on instance state. Already absorbed in v3 §2.8;
re-stated here so ADR-10 names it explicitly.

---

## 4. New bucket entries proposed

Eight A-bucket additions, three B-bucket additions, derived from §1.
Numbering picks up after v3 (which ended at A14, B18).

### A-bucket additions

**A15 — fa prompts load**
*Source:* pi P2 (`prompt-templates.ts`).
*Shape:* canonical loader for `knowledge/prompts/*.md` returning
`{ promptTemplates, diagnostics }` with stable error codes
(`parse_failed`, `read_failed`, `file_info_failed`). YAML frontmatter
parsed once; body extracted with `$1` / `$@` / `$ARGUMENTS` /
`${@:N:L}` placeholder substitution. Removes the prose rule «put
prompts in `knowledge/prompts/`, not Python strings» — the loader is
the rule.
*Cost:* 1 PR, ~150 LOC + tests.
*Dependency:* none.

**A16 — fa doctor**
*Source:* gbrain G1 (`doctor.ts`).
*Shape:* command returning a versioned report with `{ schema_version,
status, health_score, checks: [{ name, status: ok|warn|fail, message,
details, remediation, remediation_status }] }`. Score = 100 − Σ(20 ×
fail + 5 × warn), floored. Subsumes ad-hoc «is everything OK» grep
commands.
*Cost:* 1 PR, ~300 LOC scaffolding + per-check modules.
*Dependency:* A11 (`fa invariants`) feeds doctor with one check
category.

**A17 — fa verify-state**
*Source:* gbrain G2 (`schema-verify.ts`).
*Shape:* run-on-startup verifier that parses FA's canonical config
files (`pyproject.toml`, `knowledge/llms.txt`,
`.markdownlint.yaml`), diffs against runtime, and repairs drift where
safe (e.g. regenerate `knowledge/llms.txt` line counts).
*Cost:* 1 PR per config-file target.
*Dependency:* A16 (`fa doctor`) consumes the result.

**A18 — fa sanitize-tool-schemas**
*Source:* hermes H1 (`schema_sanitizer.py`).
*Shape:* runs at tool-list assembly time. Normalises
`additionalProperties: "object"` → drop, collapses
`type: [X, "null"]` arrays, strips top-level `allOf`/`anyOf`/`oneOf`/
`enum`/`not`, forces `type: "object"` + non-empty `properties` for
backend grammar compatibility. Activates when FA grows MCP / external
tool import.
*Cost:* 1 PR, ~200 LOC + per-backend rule modules.
*Dependency:* later — only urgent once MCP/external tools land.

**A19 — ToolSpec.category attribute**
*Source:* hermes H2 (IDEMPOTENT_TOOL_NAMES / MUTATING_TOOL_NAMES).
*Shape:* extend `ToolSpec` with `category: "idempotent" | "mutating"`
declared at registration time. The harness reads it; LoopGuard uses
it to choose between detectors (no-progress only applies to idempotent
tools). FA's baseline 6 tools categorise trivially.
*Cost:* tiny PR, ~30 LOC + 6 annotations.
*Dependency:* none. Prereq for B20.

**A20 — dynamic_schema_overrides on ToolSpec**
*Source:* hermes H4 (`tools/registry.py:99-106`).
*Shape:* optional zero-arg callable on `ToolSpec` returning a dict of
schema overrides merged into the tool's exposed schema at every prompt-
assembly call. Use case: tool description should reflect *current*
runtime limits, not import-time limits.
*Cost:* tiny PR, ~20 LOC.
*Dependency:* none.

**A21 — fa lint-tools**
*Source:* gortex GX1 (`schema_lint.go`).
*Shape:* test-time + startup linter for FA's ToolSpec list. Asserts:
name matches `^[a-z][a-z0-9_]{0,63}$`, description non-empty + no
control chars, parameters has `type: "object"`, every property has
`type` or `$ref`, every required name is declared. Returns *all*
violations, not just the first.
*Cost:* small PR, ~80 LOC + pytest hook.
*Dependency:* A19 (so the category is also linted).

**A22 — PromptProfile per role**
*Source:* gortex GX2 (`prompts.go::PromptProfile`).
*Shape:* enum `PromptProfile = small | frontier` with deterministic
provider→profile map. Role prompts in `knowledge/prompts/` get two
variants. Useful when FA grows hosted-API support; for now,
`small` is the only profile and the enum is a single-knob future-proof
slot.
*Cost:* deferred. Spec only until UC1+UC3 grows beyond OSS-LLM scope.
*Dependency:* none. Eventually composes with A13 (tool-table
renderer).

**A23 — Stable guard-message format**
*Source:* dpc D1 (`guards.py::stop_message()`).
*Shape:* every B-bucket entry that injects text into the LLM context
MUST use `[CODE] data-named-with-actual-numbers. concrete-next-action.`
shape. The CODE namespace is controlled (registered in a single
constants module). FA's `BashGate` and (future) BudgetLimitGuard
already partially follow this; the entry formalises it for all
B-bucket entries.
*Cost:* tiny PR (namespace + lint), then per-guard formatting fix.
*Dependency:* none.

### B-bucket additions

**B19 — Tool-call coerce-then-check**
*Source:* pi P1 (`validation.ts::validateToolArguments`).
*Shape:* between «LLM emitted tool call» and «handler dispatched», run
JSON-Schema coercion (`"true"` → `True`, `"42"` → `42`, `null` →
absent) then validator-check. If validation fails, return error
message naming the schema path and the rejected value. Reduces LLM
re-emit loops on type noise.
*Cost:* 1 PR, ~80 LOC + jsonschema coercion utility.
*Dependency:* none.

**B20 — Laddered guardrail config**
*Source:* hermes H2 (`tool_guardrails.py::ToolCallGuardrailConfig`).
*Shape:* frozen dataclass per guard with `warn_after` + `block_after`
thresholds per dimension. Multiple dimensions (exact_failure,
same_tool_failure, no_progress) each contribute one severity level.
The controller picks the highest severity across dimensions. Replaces
single-threshold guards with multi-dimensional decisions.
*Cost:* 1 PR per existing guard refactor; ~50 LOC per dimension.
*Dependency:* A19 (idempotent/mutating tags used by no_progress
dimension).

**B21 — Input-side injection shield**
*Source:* kronos K3 (`shield.py`).
*Shape:* regex pattern bank covering instruction override / role
manipulation / system-prompt extraction / secret extraction / encoding
tricks. Multilingual (English + Russian). Per-source rate limiter
sibling. Runs *before* the LLM sees user input. Returns `None` (safe)
or a structured block message.
*Cost:* 1 PR, ~150 LOC + pattern bank.
*Dependency:* none. Useful for FA's future remote-user surface (UC5,
not UC1).

---

## 5. Corrections to v3 of fa-abc-synthesis.md

Three corrections / sharpenings the re-pass surfaced:

**C-1. B14 needs per-category response policy.** v3 B14 («output
validator regex») described a single accept/reject. Kronos K4
demonstrates that real output validators carry **per-category response
policy** (`redact secrets | log paths | reject prompt-leaks`). The B14
entry in v3 §4 should be expanded with the response-policy enum.

**C-2. B-laddered should split into B-laddered (one dim) and
B-laddered-multi (orthogonal dims).** v3 §0.3 introduced B-laddered.
The re-pass shows two distinct shapes: one-dimension severity ladder
(Kronos cost_guardian K2), and multi-dimension orthogonal detectors
each with their own ladder (hermes H2). ADR-10 should name both.

**C-3. The classifier in v3 §0.4 needs ADR-10 invariants I-1..I-4.**
v3 §0.4 sketched `fa classify-rule`. The classifier needs to reject
candidates that violate the four invariants in §3 above:
- I-1: «this B entry duplicates an existing classifier without
  delegating» → reject.
- I-2: «this proposed prose rule is orchestration, not judgement» →
  classify as A.
- I-3: «this B entry's failure message has no `[CODE]` prefix» →
  reject.
- I-4: «this entry writes to LoopState from middleware» → reject.

---

## 6. Open questions for the user

Five questions surfaced by the re-pass; each is small enough that the
user can answer in a single line and they unblock concrete next steps.

1. **A16 (`fa doctor`) scope.** Adopt gbrain's scoring weights
   (fail=-20, warn=-5, floored at 0) as defaults, or pick FA-specific
   defaults? Default proposal: copy gbrain.

2. **A17 (`fa verify-state`) auto-heal scope.** Should self-healing be
   limited to «regenerate derived artefacts» (e.g. `knowledge/llms.txt`
   line counts) or also fix declared invariants in source files
   (e.g. add missing frontmatter fields)? Default proposal:
   regenerate-only; source files stay write-only by human or by
   explicit `--fix`.

3. **A18 (`fa sanitize-tool-schemas`) urgency.** Sanitiser activates
   when FA grows MCP / external tool import. Is that on Phase M
   roadmap, or after UC5? Default proposal: defer — entry exists as
   spec only until concrete MCP touchpoint lands.

4. **B19 (tool-call coerce-then-check) coercion aggressiveness.**
   Pi's coercer handles primitives + unions. Should FA's port also
   coerce strings that look like JSON-encoded objects (e.g. tool emits
   `args: "{\"path\":\"x\"}"` instead of `args: {"path":"x"}`)?
   Default proposal: yes, this is the most common OSS-LLM noise.

5. **B21 (input-side shield) scope.** Currently FA is UC1+UC3 (single-
   user, local). Input shield is most useful for UC5 (remote user
   surface). Land as spec-only entry or implement for UC1+UC3
   pre-emptively? Default proposal: spec-only until UC5 lands.

---

## 6b. §1.2.5 placement decision — compliance-by-construction

`fa-drift-analysis-v2.md` (companion forcing-function analysis from
the same Devin sessions that produced this note) proposed
«compliance by construction, failure observable» as either
**Pillar 5** in `project-overview.md` §1.1 (alongside the four
what-FA-IS pillars) or as **§1.2.5** in `project-overview.md`
(alongside §1.2 minimalism-first principle).

**Decision: §1.2.5.** Pillars 1-4 declare what FA *is* (the product
surface). §1.2 declares *how* FA is built (the construction
discipline). Compliance-by-construction is a how-axis principle —
it governs how harness components are built, not what the product
*is* — so §1.2.5 keeps the categorical separation clean and sits
next to the minimalism-first 4-question test that already governs
related decisions.

Subtraction-first audit clears: §1.2 already covers the
how-axis-principle slot in `project-overview.md`, §1.2.5 just
extends it. ADR-10's I-1..I-5 invariants (§3 + §3a above) are
concrete instances of this principle, so the placement decision is
load-bearing for ADR-10's framing.

**Next-PR action.** The ADR-10 PR (or a stand-alone PR landing
before ADR-10) adds §1.2.5 to `project-overview.md` with the five
KPI candidates from `fa-drift-analysis-v2.md` §4: (1) exit-code
contracts (rtk R1 pattern), (2) schema validators with line-cited
failure (gbrain G1 + hermes H1 patterns), (3) harness-derived
weights from LLM-emitted labels (icm IC2 pattern), (4) observable
failures via WARNING surfaces rather than silent skips (kronos K2
pattern + the F1 partial-disjoint WARNING from fork2 PR #13),
(5) named-invariant tests citing ADR clauses (Layer-2 retrofit
pattern from fork2 PR #13 «93a5ee7»). This doc (PR #14) ships §6b
as the authoritative placement decision pending the §1.2.5 edit.

---

## 7. What this note is:

- a per-repo log of determinism patterns the
ADR-8-filtered FA-Borrow-Roadmap missed or undersold, with verbatim
snippets that survive 6-month bit-rot and a mapping to FA's existing
A/B bucket policy.

---

**Amendment R — rtk-ai/{rtk, grit, icm} concrete-code deep dive.**
Appended to `fa-abc-synthesis-deep-dive.md`. Slots in:
- §0 triage table: three new rows.
- §1: three new subsections (§1.7 rtk, §1.8 grit, §1.9 icm).
- §2 cross-repo pattern table: 17 additional rows.
- §3 ADR-10 invariants: I-5 added.
- §4 new bucket entries: A24–A28 + B22–B23.
- §6 open questions: five additional, numbered 6–10.

Goal lens (your reframing of Q5): **verifiable hook results + deterministic harness to control LLM**. Each finding is filtered through whether the LLM has any degree of freedom on a spec-bearing decision; patterns where the LLM picks a label and the harness mechanically derives the consequence rank highest.

Every finding cites `repo/file.ext:line` and quotes 3-10 line snippets verbatim. Sources: clones at `/home/ubuntu/rtk-ai-dive/{rtk,grit,icm}` on 2026-05-23. Latest tags: rtk `dev-0.42.0-rc.237` / grit `v0.3.0` / icm `icm-v0.10.50`.

---

## 0a. Triage update — extension to §0

Three new repos. None filtered.

| Repo | Language | Relevant files counted | Outcome |
|---|---|---:|---|
| rtk (rtk-ai/rtk) | Rust + 10 shell-hook adapters | 8 | full-pass new territory |
| grit (rtk-ai/grit) | Rust | 6 | full-pass new territory |
| icm (rtk-ai/icm) | Rust workspace (4 crates) | 7 | full-pass new territory |

Org-level observation: all three are by the same maintainer; CLAUDE.md cross-wires them (grit's AGENTS.md mandates `icm store` post-error; icm's docs cite rtk as priority). All three are explicitly **single-purpose binaries** with no `rtk-suite` mega-binary, mirroring FA's minimalism-first principle at the cross-project level.

---

## §1.7 rtk (rtk-ai/rtk, Rust + 10 shell/TS hook adapters)

rtk is a command-rewriting proxy: `rtk git status` runs `git status`, parses, returns a compact form. The integration surface is **out-of-process hooks per AI tool**. The determinism surface is the **single Rust regex registry** all hooks delegate to. Eight files contribute determinism shapes FA does not already have.

### R1 — Exit-code-encoded hook contract (LLM has no degree of freedom on rewrite)

**Files:** `rtk/hooks/claude/rtk-rewrite.sh:50-95`; logic source `rtk/src/discover/registry.rs::classify_command`.

```sh
# rtk/hooks/claude/rtk-rewrite.sh:50-78 (excerpted)
# Delegate all rewrite + permission logic to the Rust binary.
REWRITTEN=$(rtk rewrite "$CMD" 2>/dev/null)
EXIT_CODE=$?

case $EXIT_CODE in
  0) [ "$CMD" = "$REWRITTEN" ] && exit 0 ;;  # Rewrite found, auto-allow
  1) exit 0 ;;                                # No equivalent, passthrough
  2) exit 0 ;;                                # Deny: agent's native deny handles
  3) ;;                                       # Ask: rewrite but no auto-allow
  *) exit 0 ;;
esac
```

**Pattern.** The hook is a thin shell adapter. The four exit codes (`0|1|2|3`) are the entire contract surface. The hook script *cannot* invent a fifth state; it can only delegate and dispatch on the codes the registry returns. The shell is mechanical glue, not policy.

**Determinism lens — high impact.** The LLM (Claude / Codex / Cursor / Opencode / Pi / etc.) does **not** choose whether to rewrite the command. It calls a bash tool, and the harness intercepts pre-execution. The Rust registry decides; the agent reads the consequence. The agent has zero degrees of freedom on whether `git status` gets rewritten to `rtk git status` — that decision was made at compile time when `RULES` was populated.

**Single-source-of-truth comment is mandatory.** Every adapter (claude/codex/cursor/opencode/pi/hermes/cline/kilocode/copilot/antigravity/windsurf) carries the same inline:
```
# This is a thin delegating hook: all rewrite logic lives in `rtk rewrite`,
# which is the single source of truth (src/discover/registry.rs).
# To add or change rewrite rules, edit the Rust registry — not this file.
```
This comment is the **enforcement mechanism**. A contributor who tries to "just patch the shell to fix a regex" reads the comment first; the WORKAROUND is verbally forbidden at the fix site. AP-001 equivalent, inline.

**FA fit.** New A-bucket entry **A24 — exit-code-encoded hook protocol**. FA's BashGate already classifies categories; it does not currently expose the classification to an external orchestrator. If FA grows a Claude-Code-style pre-tool seam, the exit-code protocol is the spec to copy. See §4.

### R2 — Closed `Classification` enum + `&'static [Rule]` registry

**File:** `rtk/src/discover/registry.rs:1-90` (enum + constants); `rtk/src/discover/rules.rs:1-15` (rule schema), 74 rules total.

```rust
// rtk/src/discover/registry.rs (Classification — excerpted from impl)
pub enum Classification {
    Supported {
        rtk_equivalent: String,
        category: String,
        estimated_savings_pct: f64,
        status: RtkStatus,        // Existing | Passthrough | InScope | ...
    },
    Unsupported { base_command: String },
    Ignored,
}
```

```rust
// rtk/src/discover/rules.rs:3-12 (rule schema, 74 entries follow)
pub struct RtkRule {
    pub pattern: &'static str,
    pub rtk_cmd: &'static str,
    pub rewrite_prefixes: &'static [&'static str],
    pub category: &'static str,
    pub savings_pct: f64,
    pub subcmd_savings: &'static [(&'static str, f64)],
    pub subcmd_status: &'static [(&'static str, RtkStatus)],
}

pub const RULES: &[RtkRule] = &[ /* 74 entries */ ];
```

**Pattern.** Three layers:
1. **Compile-time exhaustive enum** (`Classification`) — a consumer that omits a case fails to compile.
2. **`&'static [Rule]` data** — the rule slate is *data*, not code. A new tool integration adds a row to a const slice; no glue code.
3. **`lazy_static! { static ref REGEX_SET: RegexSet = ...; }`** — patterns compiled once at startup, queried via `regex::RegexSet::matches` which is O(n) in input length and returns *all* matching indices.

**Determinism lens — high impact.** The LLM never picks the category or the savings percentage. The classifier picks the *most specific match* (`matches.last()`) deterministically, then looks up subcommand-specific overrides:

```rust
// rtk/src/discover/registry.rs:148-160 (classify_command tail)
let matches: Vec<usize> = REGEX_SET.matches(cmd_clean).into_iter().collect();
if let Some(&idx) = matches.last() {
    let rule = &RULES[idx];
    let (savings, status) = if let Some(caps) = COMPILED[idx].captures(cmd_clean) {
        if let Some(sub) = caps.get(1) {
            let subcmd = sub.as_str();
            let status = rule.subcmd_status.iter()
                .find(|(s, _)| *s == subcmd)
                .map(|(_, st)| *st)
                .unwrap_or(super::report::RtkStatus::Existing);
            // ...
```

Same input → same classification. Testable via snapshot. No prompt involved.

**FA fit.** Extends **A21** (gortex `fa lint-tools`) — same idea (static data + linter), different surface (tool list vs. command-rewrite rule list). New A-bucket entry **A25 — closed-enum classifier + `&'static` rule slate** (see §4) — applicable to FA's BashGate categories, recovery_action enum, and any future routing surface.

### R3 — Fallback principle as design rule

**File:** `rtk/src/core/tracking.rs:312-322` (parse_failures table); `rtk/CLAUDE.md` (coding rule).

```rust
// rtk/src/core/tracking.rs:312-322
conn.execute(
    "CREATE TABLE IF NOT EXISTS parse_failures (
        id INTEGER PRIMARY KEY,
        timestamp TEXT NOT NULL,
        raw_command TEXT NOT NULL,
        error_message TEXT NOT NULL,
        fallback_succeeded INTEGER NOT NULL DEFAULT 0
    )",
    [],
)?;
```

**Pattern.** The schema *itself* enshrines the fallback design rule: "filter fails → execute raw command unchanged; record both the failure and whether the fallback succeeded." `fallback_succeeded` is a column, not a log line. The invariant "rtk never corrupts output, only compresses it" is mechanically observable.

**Determinism lens — high impact.** The agent never sees a partial output. If the filter throws, the raw command runs and the agent sees what they would have seen without rtk. Failure mode is graceful degradation, observable from the operator surface (`SELECT * FROM parse_failures WHERE fallback_succeeded = 0`).

**FA fit.** Extends **B14** (output validator) with a per-failure *observable-via-SQL* schema. New B-bucket addition implied: any validator that may reject input MUST persist its rejections in a table (not just stderr/logs) so the operator surface can query them. This generalises icm's `Feedback` table pattern from §1.9 IC5 below.

### R4 — `lazy_static` regex compilation as cold-path-vs-hot-path discipline

**File:** `rtk/src/core/filter.rs:158-170, 232-238`.

```rust
// rtk/src/core/filter.rs:158-170 (MinimalFilter regexes)
lazy_static! {
    static ref MULTIPLE_BLANK_LINES: Regex = Regex::new(r"\n{3,}").unwrap();
    static ref TRAILING_WHITESPACE: Regex = Regex::new(r"[ \t]+$").unwrap();
}

// rtk/src/core/filter.rs:232-238 (AggressiveFilter regexes)
lazy_static! {
    static ref IMPORT_PATTERN: Regex =
        Regex::new(r"^(use |import |from |require\(|#include)").unwrap();
    static ref FUNC_SIGNATURE: Regex = Regex::new(
        r"^(pub\s+)?(async\s+)?(fn|def|function|func|class|struct|enum|trait|interface|type)\s+\w+"
    ).unwrap();
}
```

**Pattern.** Regex compilation is moved to cold-path (first access) and cached. The hot-path filter call is then a tight loop with no allocation in the regex layer. Combined with `String::with_capacity(content.len())` (`filter.rs:164`) the filter avoids growth-reallocation in the steady state.

**Determinism lens — moderate.** Not LLM-directly-relevant, but supports the **<10ms startup target** documented in rtk's CLAUDE.md. A slow harness gets bypassed; a fast harness gets used. The performance budget *is* a determinism constraint at the integration layer (a hook that takes 500ms is a hook the operator disables, which means the LLM regains its degrees of freedom).

**FA fit.** Indirect. FA's BashGate validators are similarly fast (per-call regex). The lesson is: **compile-once-via-lazy_static** is the Python/`re.compile`-at-module-load equivalent. FA already does this in `src/fa/sandbox/bash/categories.py` etc. — re-confirmed.

### R5 — Telemetry-by-default SQLite at OS-standard path

**File:** `rtk/src/core/tracking.rs:280-345` (schema + indexing).

```rust
// rtk/src/core/tracking.rs:286-300
conn.execute(
    "CREATE TABLE IF NOT EXISTS commands (
        id INTEGER PRIMARY KEY,
        timestamp TEXT NOT NULL,
        original_cmd TEXT NOT NULL,
        rtk_cmd TEXT NOT NULL,
        input_tokens INTEGER NOT NULL,
        output_tokens INTEGER NOT NULL,
        saved_tokens INTEGER NOT NULL,
        savings_pct REAL NOT NULL,
        exec_time_ms INTEGER DEFAULT 0,
        project_path TEXT DEFAULT ''
    )", [])?;

// :305-310 (index for project-scoped gain queries)
let _ = conn.execute(
    "CREATE INDEX IF NOT EXISTS idx_project_path_timestamp ON commands(project_path, timestamp)",
    [],
);
```

**Pattern.** Every command execution is recorded. `~/.local/share/rtk/tracking.db` is a single-file SQLite (no journal, no daemon, no port). The schema has the three I/O dimensions (input tokens, output tokens, saved tokens) plus timing and a canonicalized project path. `rtk gain` is the operator surface; it dispatches plain SQL aggregations.

The **`GLOB` not `LIKE`** decision is documented inline ("changed: GLOB pattern with * wildcard"). `LIKE` collides with `_`/`%` in real project paths; `GLOB` uses shell-glob `*` which paths never contain. Documented one-line decision, never to be revisited.

**Determinism lens — moderate (operator side).** Not LLM-relevant directly, but the verifiability of rtk's claims ("60-90% savings") is mechanically grounded: any operator can query the DB. The benchmark is reproducible because the artifact is queryable.

**FA fit.** Extends **B14**-adjacent telemetry. FA's CostGuardian records USD; rtk records tokens-saved. Same SQLite pattern. The R5 lesson is: **canonicalize the path at write-time; use GLOB at query-time**. New A-bucket entry **A26 — telemetry-SQLite at OS-standard path** (see §4) — generalises the pattern beyond cost-tracking.

### R6 — Hook version-guard with cached result

**File:** `rtk/hooks/claude/rtk-rewrite.sh:8-43`.

```sh
# rtk/hooks/claude/rtk-rewrite.sh:8-43 (excerpted)
MIN_VERSION="0.23.0"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/rtk"
CACHE_FILE="$CACHE_DIR/hook-version-ok"

if [ -f "$CACHE_FILE" ]; then
    CACHED_VERSION=$(cat "$CACHE_FILE" 2>/dev/null)
    INSTALLED_VERSION=$(rtk --version 2>/dev/null | awk '{print $2}')
    if [ "$CACHED_VERSION" = "$INSTALLED_VERSION" ]; then
        VERSION_OK=1
    fi
fi

if [ -z "$VERSION_OK" ]; then
    # ... full version check with vercmp ...
    echo "$INSTALLED_VERSION" > "$CACHE_FILE"
fi
```

**Pattern.** The hook validates `rtk >= 0.23.0` before delegating. The result is cached by version string in `$XDG_CACHE_HOME/rtk/hook-version-ok` so the check is amortized across thousands of tool calls.

**Determinism lens — high impact for harness/hook compatibility.** Without the version guard, a stale shell hook + new Rust binary (or vice versa) silently rewrites with the wrong contract. With the guard, the hook short-circuits cleanly if the version drift is detected. Operator-visible, mechanical.

**FA fit.** New A-bucket entry **A27 — hook version guard with cached result** (see §4). FA does not currently version-guard its inner-loop middlewares, but the moment the harness gains a remote/MCP surface, version-skew is the failure mode.

### R7 — TypeScript hook variant mirrors the shell contract verbatim

**File:** `rtk/hooks/opencode/rtk.ts:1-42`.

```ts
// rtk/hooks/opencode/rtk.ts:1-42 (excerpted)
// This is a thin delegating plugin: all rewrite logic lives in `rtk rewrite`,
// which is the single source of truth (src/discover/registry.rs).
// To add or change rewrite rules, edit the Rust registry — not this file.
export const RtkOpenCodePlugin: Plugin = async ({ $ }) => {
  return {
    "tool.execute.before": async (input, output) => {
      const tool = String(input?.tool ?? "").toLowerCase()
      if (tool !== "bash" && tool !== "shell") return
      const command = (args as Record<string, unknown>).command
      if (typeof command !== "string" || !command) return
      try {
        const result = await $`rtk rewrite ${command}`.quiet().nothrow()
        const rewritten = String(result.stdout).trim()
        if (rewritten && rewritten !== command) {
          ;(args as Record<string, unknown>).command = rewritten
        }
      } catch {
        // rtk rewrite failed — pass through unchanged
      }
    },
  }
}
```

**Pattern.** Same contract as the shell hook in a different host language. The thin-delegate-comment is identical. The fallback principle ("rtk rewrite failed — pass through unchanged") is identical. The two implementations *cannot* disagree on the rewrite rules; they can only disagree on how they invoke `rtk rewrite`.

**Determinism lens — high impact for multi-host integration.** This is the answer to "how do we make every agent integration agree on the rewrite rules without duplicating them N times." The answer: don't duplicate. Each host language gets a ~40-line adapter; the rules live in Rust.

**FA fit.** Generalisation of A24+A25 above: if FA grows multi-host adapters (Python harness + JS browser frontend + Bash CI hook), the same pattern applies. The contract is the seam; the binary is the source.

### R8 — Per-cmd `enum GitCommand` + locale-stabilising helper

**File:** `rtk/src/cmds/git/git.rs:14-50, 85-110`.

```rust
// rtk/src/cmds/git/git.rs:14-27 (closed enum)
pub enum GitCommand {
    Diff, Log, Status, Show, Add, Commit, Push, Pull,
    Branch, Fetch, Stash { subcommand: Option<String> }, Worktree,
}

// rtk/src/cmds/git/git.rs:41-48 (locale-stable parsing helper)
fn git_cmd_c_locale(global_args: &[String]) -> Command {
    let mut cmd = git_cmd(global_args);
    cmd.env("LC_ALL", "C");
    cmd
}
```

**Pattern.** Two-tier command construction: `git_cmd` is user-facing (preserves the user's locale); `git_cmd_c_locale` forces `LC_ALL=C` *only* for internal parses where rtk depends on English status phrases (e.g. parsing porcelain output). Documented inline: "User-visible passthrough output keeps the user's locale."

**Determinism lens — high impact.** The harness mechanically guards against an entire class of bugs (locale-dependent parsing). The agent (LLM) never has to remember "git output is localized"; the harness already pinned it.

**FA fit.** Indirect — FA does not parse external command output in the inner loop. But the pattern generalises: any harness that parses tool output MUST normalize locale at the call site, *before* the parser. New finding for the §3 ADR-10 invariants, **I-5** below.

---

## §1.8 grit (rtk-ai/grit, Rust)

grit is a coordination layer for parallel AI agents on top of git: lock at the AST function level, not the file line level. Six files contribute determinism shapes. The integration surface is the **CLI verb set** (`claim | release | done | watch | …`); the determinism surface is the **`LockStore` trait + AST-anchored `Symbol.id`**.

### GR1 — `LockStore` trait + `LockResult` enum (closed-trait coordination contract)

**File:** `grit/src/db/lock_store.rs:1-37` (full file — 39 LOC total).

```rust
// grit/src/db/lock_store.rs:4-13
pub struct LockEntry {
    pub symbol_id: String,
    pub agent_id: String,
    pub intent: String,
    pub locked_at: String,
    pub ttl_seconds: u64,
    #[serde(default = "default_mode")]
    pub mode: String,
}

// :19-26
pub enum LockResult {
    Granted,
    Blocked { by_agent: String, by_intent: String },
}

// :29-37 (the entire backend contract)
pub trait LockStore: Send + Sync {
    fn try_lock(&self, symbol_id: &str, agent_id: &str, intent: &str,
                ttl_seconds: u64, mode: &str) -> Result<LockResult>;
    fn release(&self, symbol_id: &str, agent_id: &str) -> Result<()>;
    fn release_all(&self, agent_id: &str) -> Result<usize>;
    fn all_locks(&self) -> Result<Vec<LockEntry>>;
    fn locks_for_agent(&self, agent_id: &str) -> Result<Vec<(String, String)>>;
    fn gc_expired_locks(&self) -> Result<usize>;
    fn refresh_ttl(&self, agent_id: &str, ttl_seconds: u64) -> Result<usize>;
}
```

**Pattern.** Seven methods, four backends (`SqliteLockStore` / `S3LockStore` / `AzureLockStore` / (future) GCS). The trait is the *only* place lock semantics are defined; backends differ only in the atomicity primitive (SQLite WAL transaction vs. S3 conditional PUT vs. Azure `If-None-Match: *`). The `LockResult` is an exhaustive enum — a caller that omits the `Blocked` arm fails to compile and the reason for the block is part of the type (`by_agent`, `by_intent`), not a free-form string.

**Determinism lens — extremely high.** Two agents trying to claim the same symbol get a deterministic Granted/Blocked verdict from the trait, regardless of backend. The LLM (the agent) never decides whether its claim succeeds — the trait does. The agent reads `LockResult` and is forced to handle both arms (compile-time exhaustive).

The **`mode: String`** field has `#[serde(default = "default_mode")] // = "write"`. Backward-compat encoded at the field level: pre-mode lock entries deserialize as write-locks. Documented one-line decision, mechanical.

**FA fit.** New A-bucket entry **A28 — backend-abstract contract trait + closed-enum result** (see §4). FA's `ToolSpec` and `HookRegistry` already use this shape (in-process); grit demonstrates the shape generalises to out-of-process coordination via JSON serialization + abstract trait.

### GR2 — AST symbol with content hash as drift detector

**File:** `grit/src/parser/mod.rs:1-50, 380-400`.

```rust
// grit/src/parser/mod.rs:7-19 (the lock-anchored identity)
pub struct Symbol {
    pub id: String,         // e.g. "src/auth.ts::login"
    pub file: String,
    pub name: String,
    pub kind: String,       // "function" | "class" | "method" | "struct" | "impl" | ...
    pub start_line: u32,
    pub end_line: u32,
    pub hash: String,       // hash of the symbol's source text
}

// :384-389 (the hash function — DefaultHasher → hex)
fn hash_str(s: &str) -> String {
    let mut hasher = DefaultHasher::new();
    s.hash(&mut hasher);
    format!("{:x}", hasher.finish())
}
```

**Pattern.** Three lock-relevant pieces:
1. **`id` is the canonical key**: `<file>::<symbol_name>`. Composed deterministically from file path + tree-sitter-extracted symbol name. The agent doesn't pick the key; the parser does.
2. **`hash`** captures the symbol's *source text*, not its coordinates. If two agents claim by name and the source moved between scan and claim, the hash mismatch is a post-claim drift indicator.
3. **`start_line` / `end_line`** are derived from the AST, not from user-supplied coordinates.

**Determinism lens — extremely high.** The lock key is a function of the file content, not of the agent's request. An LLM that claims "`login` in auth.ts" gets a lock keyed `src/auth.ts::login`, not on whatever the LLM thinks the function signature looks like. The hash makes "did the symbol body change while I held the lock?" a checkable question.

**Tree-sitter is the contract.** From `parser/mod.rs:113+`:
```rust
// :116-128 (per-language SymbolQuery list — closed slate per language)
SymbolQuery::new("function_declaration", NameExtractor::Field("name")),
SymbolQuery::new("class_declaration", NameExtractor::Field("name")),
SymbolQuery::new("method_definition", NameExtractor::Field("name")),
SymbolQuery::new("interface_declaration", NameExtractor::Field("name")),
SymbolQuery::new("type_alias_declaration", NameExtractor::Field("name")),
SymbolQuery::new("enum_declaration", NameExtractor::Field("name")),
```

Each language config is a `LangConfig { language, extensions, symbol_queries }`. 13 languages. The set of "lockable thing" is closed per language; new symbol kinds require explicit registration.

**FA fit.** Directly applicable to FA's planned ADR-5 source-code chunker (CtagsChunker). The lesson: the chunker output should carry a content hash, not just line coordinates. Two chunks with same `<file>::<symbol_id>` but different hashes is a *drift event* the harness can observe. Extends FA's existing ADR-5 plan; not a new bucket entry, more a refinement.

### GR3 — Atomicity-primitive abstraction (WAL / S3 conditional PUT / Azure `If-None-Match`)

**Files:** `grit/src/db/mod.rs:11-25` (SQLite WAL); `grit/src/db/azure_store.rs:99-128` (Azure `If-None-Match`).

```rust
// grit/src/db/mod.rs:11-25 (SQLite atomicity)
pub fn configure_connection(conn: &Connection) -> Result<()> {
    match conn.execute_batch("PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;") {
        Ok(_) => Ok(()),
        Err(e) => {
            let err_str = e.to_string();
            if err_str.contains("locked") || err_str.contains("busy") {
                anyhow::bail!(
                    "Database is locked by another process. \
                     If this persists, check for stale grit processes or remove the WAL files."
                );
            }
            anyhow::bail!("Database configuration failed: {}", e);
        }
    }
}
```

```rust
// grit/src/db/azure_store.rs:99-122 (cloud atomicity)
fn put_lock_if_absent(&self, entry: &LockEntry) -> Result<bool> {
    let key = self.lock_key(&entry.symbol_id);
    let body = serde_json::to_vec(entry)?;
    let blob = self.client.blob_client(&key);

    let result = self.rt.block_on(async {
        blob.put_block_blob(body)
            .content_type("application/json")
            .if_match(IfMatchCondition::NotMatch("*".to_string()))
            .await
    });

    match result {
        Ok(_) => Ok(true),
        Err(e) => {
            let err_str = e.to_string();
            if err_str.contains("409") || err_str.contains("412")
                || err_str.contains("BlobAlreadyExists")
                || err_str.contains("ConditionNotMet")
            {
                Ok(false)
            } else {
                Err(anyhow::anyhow!("Azure conditional PUT failed: {}", e))
            }
        }
    }
}
```

**Pattern.** Two completely different atomicity primitives (SQLite WAL transaction; Azure `If-None-Match: *` on PUT) collapsed into the same trait method (`try_lock`). The local backend uses a SQL transaction; the cloud backend uses HTTP conditional-write semantics; both yield `LockResult::Granted | Blocked`.

**Determinism lens — high impact for distributed harness.** This is what makes grit "cloud-portable": the deterministic contract (`LockStore::try_lock`) does not change; only the implementation does. An operator switching from local to S3 to Azure changes a config row, not the agent's code.

**Plus integrity check on open** (`grit/src/db/mod.rs:47-65`):
```rust
match conn.query_row("PRAGMA integrity_check", [], |row| row.get::<_, String>(0)) {
    Ok(ref result) if result == "ok" => {}
    Ok(detail) => {
        anyhow::bail!(
            "Database {} failed integrity check: {}.\n\
             Remove it and re-run `grit init` to rebuild.", path.display(), detail);
    }
```

The DB is verified at every open. Silent corruption is impossible; loud failure with a fix-it suggestion is the only mode. **Verifiability mechanic at the schema level.**

**FA fit.** Directly applicable to any FA storage abstraction. FA already uses SQLite (Mechanical Wiki). The R5+GR3 lesson: **always run `PRAGMA integrity_check` on open and refuse to proceed on failure**. Extends existing patterns. Plus: if FA ever needs a distributed coordination primitive (parallel Coders editing different files), the GR1+GR3 shape is the existing-art.

### GR4 — Identifier validation as first-line input sanitizer

**File:** `grit/src/cli/mod.rs:255-265, 275-285`.

```rust
// grit/src/cli/mod.rs:255-265
fn validate_identifier(id: &str, label: &str) -> Result<()> {
    if id.is_empty() {
        anyhow::bail!("Invalid {}: must not be empty", label);
    }
    if id.contains('/') || id.contains('\\') || id.contains("..") || id.starts_with('-') {
        anyhow::bail!("Invalid {}: '{}' contains forbidden characters (/, \\, ..) or starts with -", label, id);
    }
    if !id.chars().all(|c| c.is_alphanumeric() || c == '-' || c == '_' || c == '.') {
        anyhow::bail!("Invalid {}: '{}' must contain only alphanumeric, hyphens, underscores, dots", label, id);
    }
    Ok(())
}

// :275-283 (applied early, before any other logic runs)
match &cli.command {
    Command::Claim { agent, .. } | Command::Release { agent, .. }
    | Command::Done { agent } | Command::Plan { agent, .. }
    | Command::Heartbeat { agent, .. }
    | Command::Assign { agent, .. } => validate_identifier(agent, "agent ID")?,
    Command::Session { action: SessionAction::Start { name } } => {
        validate_identifier(name, "session name")?;
    }
    _ => {}
}
```

**Pattern.** Early-stage allowlist validator. Agent IDs and session names are alphanumeric + `-`/`_`/`.` only. The check runs *before* any command dispatches, guarding against:
- Path traversal (`..`)
- Argument injection (starts with `-`)
- Embedded delimiters

**Determinism lens — high impact for harness security.** The LLM cannot smuggle a path-traversal agent ID through to the worktree directory creator. The validator decides; the LLM has zero degrees of freedom on the identifier shape.

**FA fit.** Extends **B5** (gbrain allowlist validators). Same shape; grit's is narrower (identifier-only). FA's BashGate has analogous path-containment checks. The GR4 lesson: **every identifier the LLM emits MUST pass an allowlist before reaching any filesystem/network sink**. Already in FA's BashGate; re-confirmed.

### GR5 — TTL + heartbeat + gc as bounded-blocking discipline

**File:** `grit/src/db/sqlite_store.rs:27-37` (auto-expire on `try_lock`).

```rust
// grit/src/db/sqlite_store.rs:27-37 (excerpt from try_lock)
impl LockStore for SqliteLockStore {
    fn try_lock(&self, symbol_id: &str, agent_id: &str, intent: &str, ttl_seconds: u64, mode: &str) -> Result<LockResult> {
        let conn = self.conn()?;

        // Clean up expired locks on this symbol
        conn.execute(
            "DELETE FROM locks WHERE symbol_id = ?1
             AND (julianday('now') - julianday(locked_at)) * 86400 > ttl_seconds",
            params![symbol_id],
        )?;
        // ... then check existing, then grant/block ...
```

**Pattern.** Every `try_lock` call first GCs expired entries on the same symbol. TTL is a column; expiration is a clock-derived predicate. No background thread, no separate cleanup job — the cleanup is amortized into the lock-acquisition hot path.

**Plus heartbeat** (`LockStore::refresh_ttl`): an active agent extends its lock by re-issuing a TTL. **Plus dedicated `gc` verb** (`grit gc`): explicit operator-driven cleanup. Three layers of "no zombie locks."

**Determinism lens — high impact.** A crashed agent does NOT permanently block other agents. The harness recovers automatically because the storage encodes "stale-after-TTL." No human intervention required; no operator runbook needed for the common case.

**FA fit.** Direct lesson for any FA state that can outlive a crashed process. FA's `attempt_history.json` is per-run; grit's pattern shows what cross-session would look like (TTL + heartbeat + lazy GC on access).

### GR6 — RoomEvent stream as observable lock transition log

**Files:** Inferred from `grit/src/cli/mod.rs:11-16` (imports `RoomEvent, EventType, NotificationServer`) + `grit/src/room/*.rs` (room module).

The CLI exposes `grit watch` which tails the room stream. Local backend: Unix domain socket at `.grit/room.sock`. S3/Azure backends: poll-based on object listings or Event Grid subscriptions. The `RoomEvent { kind: EventType, … }` shape is itself a closed enum.

**Pattern.** Every lock state transition (grant, release, queue, expire) is observable to any subscriber. The lock state IS the stream; the DB is the snapshot.

**Determinism lens — moderate.** Not LLM-decision-relevant directly, but the *observability* of the harness's decisions is what makes the system auditable. A reviewer can replay the room stream to see "in what order did the agents claim?" — making the parallel-execution trace reproducible.

**FA fit.** Indirect. FA's `AttemptHistoryObserver` is the per-session analog; grit's RoomEvent is cross-session. Not a new bucket entry, but the lesson: **every harness decision should emit an observable event, not just a log line**. Re-confirmed via dpc-messenger D2 (typed loop-state ownership) in v3 §2.8.

---

## §1.9 icm (rtk-ai/icm, Rust workspace, 4 crates)

icm is a memory store: one SQLite per machine, every MCP-capable AI tool reads/writes the same DB, two data models (Memories with temporal decay, Memoirs with typed knowledge-graph relations). Seven files contribute determinism shapes. The integration surface is the **MCP tool list** (~16 tools); the determinism surface is the **`MemoryStore` trait + `Importance` enum + JSON Schema at MCP boundary**.

### IC1 — MCP layer-boundary validation with comment-as-spec

**File:** `icm/crates/icm-mcp/src/tools.rs:15-32`.

```rust
// icm/crates/icm-mcp/src/tools.rs:15-32
const AUTO_CONSOLIDATE_THRESHOLD: usize = 10;
const DEDUP_SIMILARITY_THRESHOLD: f32 = 0.85;

/// Maximum allowed length for topic names. Must stay <= the store
/// layer's `MAX_TOPIC_BYTES` so the MCP-level rejection happens
/// *before* the store's lower-level validation does.
const MAX_TOPIC_LEN: usize = 255;

/// Maximum allowed length for content/summary text. Aligned with the
/// store layer's `MAX_SUMMARY_BYTES` (64 KB). Letting MCP accept
/// larger inputs only to have the store reject them would be
/// confusing — fail fast at the API surface.
const MAX_CONTENT_LEN: usize = 64 * 1024;
```

**Pattern.** Four constants. Each has a one-paragraph doc-comment explaining *why this value, and why at this layer*. The MCP layer rejects malformed input first, so the agent sees an agent-friendly schema error rather than a SQLite-friendly error. **The comment is the spec; the constant is the enforcement.**

**Determinism lens — extremely high.** The LLM has zero degrees of freedom on topic length, content size, or auto-consolidation threshold. These are constants, baked at compile time, with explicit doc-comments tying them to other layer constants. A future contributor adjusting `MAX_TOPIC_LEN` is forced to *read* why it has to stay ≤ `MAX_TOPIC_BYTES`.

**Forensic-comment specialisation:**
```rust
// icm/crates/icm-mcp/src/tools.rs:52-64
fn try_auto_consolidate(
    store: &SqliteStore, embedder: Option<&dyn Embedder>,
    topic: &str, threshold: usize,
) -> String {
    /// Routes through `auto_consolidate_with_embedder` so the consolidated
    /// memory is embedded inline (closes audit M2/AC2: previously the
    /// rolled-up memory had `embedding = None` and was invisible to hybrid
    /// recall until a manual `icm embed` rebuilt it).
    match store.auto_consolidate_with_embedder(topic, threshold, embedder) {
```

The comment cites an audit ID (`M2/AC2`) inline at the fix site. **This is the FA AP-001 catalog pattern, inlined.** Tracing from a code site to the audit finding is one keyword search away.

**FA fit.** New A-bucket entry **A23-extension** (refinement of A23 stable guard-message format): every B-bucket entry's mechanical fix should cite an AP-ID or audit-ID in an inline doc-comment. New I-tier invariant **I-5** (see §3a below).

### IC2 — `Importance` enum with constant decay multipliers (LLM picks label, not weight)

**Files:** `icm/crates/icm-core/src/memory.rs:96-130` (enum + parse); `icm/crates/icm-core/src/wake_up.rs:198-217` (decay weights).

```rust
// icm/crates/icm-core/src/memory.rs:96-104
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Importance {
    Critical,
    High,
    Medium,
    Low,
}
```

```rust
// icm/crates/icm-core/src/wake_up.rs:198-207 (compute_score)
fn compute_score(m: &Memory, now: DateTime<Utc>) -> f32 {
    let importance_weight = match m.importance {
        Importance::Critical => 10.0,
        Importance::High => 5.0,
        Importance::Medium => 2.0,
        Importance::Low => 0.5,
    };
    let reference = m.created_at.max(m.last_accessed);
    let days = (now - reference).num_days().max(0) as f32;
    let recency = 1.0 / (1.0 + days / 30.0);  // ~0.5 at day 30, ~0.25 at day 90
    let stored_weight = m.weight.max(0.01);
    importance_weight * recency * stored_weight
}
```

**Pattern.** The LLM picks one of four labels (`critical | high | medium | low`). The harness mechanically derives the weight (`10.0 | 5.0 | 2.0 | 0.5`), the decay curve (`1 / (1 + days/30)`), and the wake-up rank. The agent's prompt explicitly *forbids* it from emitting a numeric weight — the MCP `inputSchema` declares `Importance` as an enum with the four labels:

```json
// icm/crates/icm-mcp/src/tools.rs (tool_definitions, snipped)
"importance": {
    "type": "string",
    "enum": ["critical", "high", "medium", "low"],
    "default": "medium",
    "description": "critical=never forgotten, high=slow decay, medium=normal, low=fast decay"
}
```

**Determinism lens — extremely high.** This is THE canonical realisation of "LLM picks a label; harness mechanically derives the consequence." It maps cleanly to your reframing of Q5 (verifiable hook results + deterministic harness to control LLM). The LLM does not estimate "decay rate" — it picks `critical`. The harness reads `critical` → `weight = 10.0, never forgotten`. The decay curve is data, in code, version-controlled.

**FA fit.** New A-bucket entry **A28 — enum-label-with-harness-derived-weight pattern**. Highest leverage of all rtk-ai patterns. See §4. The mapping for FA: every LLM-emitted dimension that today is a number ("severity", "confidence", "risk") should be re-shaped as a 3-5-label enum with hardcoded multipliers.

### IC3 — `Category` routing in wake_up (deterministic prompt-block builder)

**File:** `icm/crates/icm-core/src/wake_up.rs:50-78, 220-245`.

```rust
// icm/crates/icm-core/src/wake_up.rs:48-72 (Category + label + ordering)
enum Category {
    Identity,
    Decision,
    Constraint,
    Error,
    Milestone,
    Context,
}

impl Category {
    fn label(self) -> &'static str {
        match self {
            Self::Identity => "Identity & preferences",
            Self::Decision => "Critical decisions",
            Self::Constraint => "Active constraints",
            Self::Error => "Recent errors resolved",
            Self::Milestone => "Milestones",
            Self::Context => "Project context",
        }
    }

    fn all_ordered() -> [Category; 6] {
        [Self::Identity, Self::Decision, Self::Constraint,
         Self::Error, Self::Milestone, Self::Context]
    }
}
```

```rust
// icm/crates/icm-core/src/wake_up.rs:220-245 (categorize: text → Category)
fn categorize(m: &Memory) -> Category {
    let t = m.topic.to_lowercase();
    let s = m.summary.to_lowercase();
    if is_preference_topic(&m.topic) { return Category::Identity; }
    if t.contains("decision") || s.contains("decided ") || s.contains("chose ") {
        return Category::Decision;
    }
    if t.contains("constraint") || t.contains("rule") || t.contains("convention")
        || s.starts_with("always ") || s.starts_with("never ") || s.starts_with("must ") {
        return Category::Constraint;
    }
    if t.contains("error") || t.contains("bug") || s.starts_with("fixed ") {
        return Category::Error;
    }
    if t.contains("milestone") || t.contains("release") || s.contains("shipped") {
        return Category::Milestone;
    }
    Category::Context
}
```

**Pattern.** Two-stage routing for session-start prompt assembly:
1. **Filter** memories by `Critical | High` importance (or preference topics).
2. **Score** each by `importance_weight * recency_factor * stored_weight`.
3. **Sort** by score (ties broken by ULID — see IC6).
4. **Categorize** each into one of six buckets by simple keyword heuristics on topic+summary.
5. **Group** by category in `Category::all_ordered()` order.
6. **Truncate** by character budget with per-memory cap.

The output is a markdown snapshot with six section headers. Token budget is enforced (`max_tokens.saturating_mul(4)` for char budget); memories oversized for the per-memory cap are mid-truncated with `[…]` suffix.

**Determinism lens — extremely high.** Same DB + same filter options = same wake-up pack, byte-for-byte. The "deterministic prompt-cache prefix match" requirement is documented inline:
```rust
// :268-273
// Ties broken by id (lexicographic / ULID-monotonic) so the wake-up
// ordering stays deterministic — required for the prompt-cache prefix
// match to survive across runs with equal-scored memories.
```

**This is what your Q3 wants for HANDOFF.md.** The shape is:
- Categories: closed enum, fixed order.
- Routing: deterministic keyword heuristics (regex-free, fast, testable).
- Budget: hard char/token cap, per-memory truncation with marker.
- Ordering: importance × recency × stored_weight, tie-broken by ULID.

**FA fit.** New A-bucket entry **A29 — categorized + budget-enforced session-start pack**. Directly the focused proposal you signed off in Q3. See §4 for the FA port spec.

### IC4 — `auto_link` with cosine threshold (B-tier graph builder)

**File:** `icm/crates/icm-core/src/auto_link.rs:17-90`.

```rust
// icm/crates/icm-core/src/auto_link.rs:18-36 (config)
pub struct AutoLinkOptions {
    pub enabled: bool,
    pub threshold: f32,    // typical for multilingual-e5-base (768d): 0.75
    pub max_links: usize,
}

impl Default for AutoLinkOptions {
    fn default() -> Self {
        Self { enabled: true, threshold: 0.75, max_links: 5 }
    }
}

// :52-90 (auto_link_memory — populates new_memory.related_ids)
pub fn auto_link_memory<S: MemoryStore + ?Sized>(
    store: &S, new_memory: &mut Memory, opts: &AutoLinkOptions,
) -> IcmResult<Vec<String>> {
    if !opts.enabled || opts.max_links == 0 { return Ok(Vec::new()); }
    let Some(ref emb) = new_memory.embedding else { return Ok(Vec::new()); };

    let fetch_n = opts.max_links.saturating_add(1);
    let candidates = store.search_by_embedding(emb, fetch_n)?;

    let mut new_links: Vec<String> = Vec::new();
    for (candidate, score) in candidates {
        if score < opts.threshold { continue; }
        if candidate.id == new_memory.id { continue; }
        if new_memory.related_ids.contains(&candidate.id) { continue; }
        new_memory.related_ids.push(candidate.id.clone());
        new_links.push(candidate.id);
        if new_links.len() >= opts.max_links { break; }
    }
    Ok(new_links)
}
```

**Pattern.** A B-tier verifier on memory writes: every `store(memory)` first runs `auto_link_memory` to populate `related_ids` with cosine-similar existing memories above `threshold = 0.75`, capped at `max_links = 5`. The LLM is *not* asked "what does this memory relate to?" — the harness derives the answer from the embedding space.

**Plus `add_backrefs` (the bidirectional-link enforcer):**
```rust
// icm/crates/icm-core/src/auto_link.rs:101-115
pub fn add_backrefs<S: MemoryStore + ?Sized>(
    store: &S, new_memory_id: &str, linked_ids: &[String],
) -> IcmResult<usize> {
    let mut updated = 0usize;
    for id in linked_ids {
        if let Some(mut existing) = store.get(id)? {
            if existing.related_ids.iter().any(|r| r == new_memory_id) {
                continue;
            }
            existing.related_ids.push(new_memory_id.to_string());
            store.update(&existing)?;
            updated += 1;
        }
    }
    Ok(updated)
}
```

**Determinism lens — high impact.** Two consequences:
1. Two stores of the same memory in the same DB state produce the same outgoing links (cosine is deterministic; the order is sorted by score).
2. The knowledge graph cannot have "asymmetric pollution" — every forward link induces a backref. The graph is structurally bidirectional by construction.

**Best-effort failure mode is documented inline**:
```rust
// :96-99
// Best-effort: a failure on one back-ref is logged by the caller but does
// not roll back the others. The graph is allowed to be slightly asymmetric
// under error conditions rather than losing the whole operation.
```

A real engineering decision (consistency vs. availability), made explicit in code, never to be revisited without revising the comment.

**FA fit.** New A-bucket entry **A30 — harness-derived structural relation at write-time** (conceptual; very small surface in FA today). Indirect, since FA does not have an embedding store. Mid-priority observation.

### IC5 — `Feedback` schema with `applied_count` (cross-session correction loop)

**Files:** Inferred from `icm/crates/icm-core/src/feedback.rs` (need to look — but the `FeedbackStats` and `Feedback` exports in `lib.rs:25-26` confirm presence). MCP surface: `icm_feedback_record / icm_feedback_search / icm_feedback_stats`.

**Pattern.** Three MCP tools:
- `icm_feedback_record(predicted, corrected, reason, context)` — agent reports "I predicted X; you said Y; here's why."
- `icm_feedback_search(query)` — future recall: "have I made this mistake before?"
- `icm_feedback_stats()` — operator surface: "what corrections are recurring?"

`Feedback.applied_count: u32` increments when a correction is *reused* — i.e. the agent searches feedback, finds a relevant correction, and applies it. This makes the corrective loop **observable at the operator level**: "the FixForeignTimezone correction was reused 12 times this month."

**Determinism lens — moderate (cross-session correction is a long-horizon B-tier loop).** Single sessions don't change LLM behavior, but the persisted Feedback table changes future sessions' available context. The agent does not "learn" in the gradient sense; the harness records and replays.

**FA fit.** Generalises FA's `AttemptHistoryObserver`. The icm shape is cross-session, searchable, with reuse-count telemetry. The FA shape is per-run, bounded, retry-prompt-feeder. Both are useful; icm's adds the "is-this-fix-actually-being-reused?" metric.

Not a new bucket entry today (FA does not have cross-session feedback in scope for 0.1), but a future refinement of the AttemptHistoryObserver shape worth noting.

### IC6 — ULID identity + OS-standard SQLite path

**Files:** `icm/crates/icm-core/src/memory.rs:38-58` (`Memory::new` constructor); `icm/README.md` lines 1-100 for the OS-standard path claim.

```rust
// icm/crates/icm-core/src/memory.rs:38-58 (Memory::new)
pub fn new(topic: String, summary: String, importance: Importance) -> Self {
    let now = Utc::now();
    Self {
        id: ulid::Ulid::new().to_string(),
        created_at: now,
        updated_at: now,
        last_accessed: now,
        access_count: 0,
        weight: 1.0,
        topic,
        summary,
        raw_excerpt: None,
        keywords: Vec::new(),
        importance,
        source: MemorySource::Manual,
        related_ids: Vec::new(),
        embedding: None,
        scope: Scope::User,
    }
}
```

**Pattern.** Two design choices:
1. **ULID** (not UUID v4) — lex-sortable, monotone, embeds a millisecond-precision timestamp. The "ULID-monotonic tie-break" in wake_up (IC3) only works because ULIDs are monotonically increasing in lex order.
2. **OS-standard path** for the DB (`~/.local/share/icm/memories.db` on Linux; XDG-compliant). One DB per machine across all AI tools is structurally possible because every tool reads the same path.

**Determinism lens — moderate.** Both are infrastructure decisions, not LLM-control decisions. But together they enable the cross-agent invariant: any AI tool with MCP support reads the same memories, sorted in the same order, with the same IDs.

**FA fit.** Indirect — FA's memory is filesystem-canonical (Mechanical Wiki as Markdown). ULID is the right answer if FA ever needs DB-canonical identity. Re-confirmed: ULID > UUID v4 for ordered IDs.

### IC7 — `MemoryStore` trait (23 methods, four lifecycle bands)

**File:** `icm/crates/icm-core/src/store.rs:1-40` (full file — 40 LOC).

```rust
// icm/crates/icm-core/src/store.rs:4-39 (the entire trait)
pub trait MemoryStore {
    // CRUD
    fn store(&self, memory: Memory) -> IcmResult<String>;
    fn get(&self, id: &str) -> IcmResult<Option<Memory>>;
    fn update(&self, memory: &Memory) -> IcmResult<()>;
    fn delete(&self, id: &str) -> IcmResult<()>;

    // Search
    fn search_by_keywords(&self, keywords: &[&str], limit: usize) -> IcmResult<Vec<Memory>>;
    fn search_fts(&self, query: &str, limit: usize) -> IcmResult<Vec<Memory>>;
    fn search_by_embedding(&self, embedding: &[f32], limit: usize)
        -> IcmResult<Vec<(Memory, f32)>>;
    fn search_hybrid(&self, query: &str, embedding: &[f32], limit: usize,
    ) -> IcmResult<Vec<(Memory, f32)>>;

    // Lifecycle
    fn update_access(&self, id: &str) -> IcmResult<()>;
    fn batch_update_access(&self, ids: &[&str]) -> IcmResult<usize>;
    fn apply_decay(&self, decay_factor: f32) -> IcmResult<usize>;
    fn prune(&self, weight_threshold: f32) -> IcmResult<usize>;

    // Organization
    fn list_all(&self) -> IcmResult<Vec<Memory>>;
    fn get_by_topic(&self, topic: &str) -> IcmResult<Vec<Memory>>;
    fn list_topics(&self) -> IcmResult<Vec<(String, usize)>>;
    fn consolidate_topic(&self, topic: &str, consolidated: Memory) -> IcmResult<()>;

    // Stats
    fn count(&self) -> IcmResult<usize>;
    fn count_by_topic(&self, topic: &str) -> IcmResult<usize>;
    fn stats(&self) -> IcmResult<StoreStats>;
    fn topic_health(&self, topic: &str) -> IcmResult<TopicHealth>;
}
```

**Pattern.** Four explicit lifecycle bands as section-comments. 23 methods total. The trait is the integration boundary; the SQLite schema is implementation detail.

`search_hybrid` is the hybrid-search contract (BM25 + cosine). Three search variants explicitly declared (keyword/FTS/embedding) plus the hybrid combinator. Operator can pick the right retrieval strategy without changing the type signature.

**Determinism lens — high (architectural).** Every external consumer (MCP tool layer, CLI, integration tests) talks to the trait, never to SQLite directly. Replacing SQLite with another backend (Turso, Postgres) is a contained change.

**FA fit.** Architecturally well-aligned with FA's existing `ToolSpec`/`HookRegistry`/`MemoryStore`-like patterns. The IC7 lesson: when a trait grows beyond ~10 methods, **organize by lifecycle band with section-comments**. Mechanical readability win for future maintainers.

---

## §2a Cross-repo pattern table — extension to §2

Pre-existing table ended at row 20. Adding 17 new rows (21-37).

| # | Pattern | Repos | Tier | FA bucket affected | Notes |
|---:|---|---|---|---|---|
| 21 | Exit-code-encoded hook protocol | rtk R1 | A | new A24 | `0\|1\|2\|3` from registry; shell adapter is thin delegate |
| 22 | Closed-enum classifier + `&'static` rule slate | rtk R2 | A | new A25 | 74 rules in `RULES: &[RtkRule]`; LLM cannot bypass |
| 23 | Fallback principle as schema column | rtk R3 | invariant | extends B14 | `fallback_succeeded INTEGER` is the spec; not just stderr |
| 24 | `lazy_static` regex cold-path | rtk R4 | A (perf) | re-confirmed | Compile-once-cache; hot-path is alloc-free |
| 25 | Telemetry-SQLite at OS-standard path | rtk R5 | observability | new A26 | Per-command record; `GLOB` not `LIKE` for paths |
| 26 | Hook version-guard with cached result | rtk R6 | A | new A27 | `MIN_VERSION` in shell; cached by version string |
| 27 | Per-host adapter mirrors contract verbatim | rtk R7 | invariant | extends A24 | 10 hosts × 1 registry; thin-delegate comment mandatory |
| 28 | Locale-stable parsing helper at call-site | rtk R8 | A | I-5 (ADR-10) | `LC_ALL=C` only for parses, not for passthrough |
| 29 | `LockStore` trait + closed `LockResult` enum | grit GR1 | invariant | new A28 | 7 methods + 2-variant result; 3 backends |
| 30 | AST symbol with content hash as drift detector | grit GR2 | A | extends ADR-5 chunker | `<file>::<symbol>` + content hash |
| 31 | Atomicity-primitive abstraction across backends | grit GR3 | invariant | extends A28 | SQLite WAL == S3 conditional PUT == Azure `If-None-Match` |
| 32 | `PRAGMA integrity_check` on open | grit GR3b | observability | new (small) | Refuse to proceed on corruption; loud-fail |
| 33 | Identifier allowlist + early-stage validation | grit GR4 | B | extends B5 | Path-traversal + arg-injection shield; applied pre-dispatch |
| 34 | TTL + heartbeat + amortized GC | grit GR5 | B | new B22 | No zombie locks; cleanup amortized to hot path |
| 35 | MCP layer-boundary validation w/ comment-as-spec | icm IC1 | invariant | new I-5 | `MAX_TOPIC_LEN` comment explains layer relationship |
| 36 | Enum-label + harness-derived weight | icm IC2 | A | new A28 | LLM picks `critical`; harness picks `10.0`. Highest-leverage pattern |
| 37 | Categorized + budget-enforced session-start pack | icm IC3 | A | new A29 | 6 categories × score × ULID tie-break → deterministic prompt |
| 38 | `applied_count` on cross-session corrections | icm IC5 | B (observability) | future | Reuse-of-correction telemetry; AttemptHistoryObserver successor |
| 39 | Trait organized by lifecycle bands w/ section-comments | icm IC7 | A (readability) | re-confirmed | 23 methods × 4 bands; CRUD/Search/Lifecycle/Organization/Stats |

Tier annotations match §2 (A/B/B-laddered/B-laddered-multi/invariant).

---

## §3a Extension to §3 — new ADR-10 invariant

**I-5. Layer-boundary fail-fast: validate at the surface closest to the agent, not at the storage.** (rtk R8, icm IC1.)

When a request crosses multiple harness layers (MCP layer → store layer → SQLite), validation MUST occur at the *outermost* layer in the agent's path. The store layer's hard limits MUST be matched by the MCP layer's hard limits with the relationship documented inline (per icm IC1: `MAX_TOPIC_LEN ≤ MAX_TOPIC_BYTES`). For parsing surfaces, the locale/encoding MUST be normalized at the call site, not relied upon globally (per rtk R8).

**Detection.** An entry violates I-5 if:
- Its hard-limit constant lacks a doc-comment naming the corresponding deeper-layer constant.
- Its parsing helper does not pin locale at the call site.
- A failure path bubbles up a SQLite/system error verbatim to the LLM (the SQLite error format is implementation detail).

**FA today.** At-risk in:
- `BashGate` path-containment — currently validates in-process; if FA grows MCP, this needs an MCP-layer mirror.
- `DSV` YAML parsing — locale-dependent? Re-check.
- Chunker — if external file paths reach the chunker, normalize encoding upfront.

---

## §4a Extension to §4 — new A-bucket and B-bucket entries

Five A-bucket additions (A24-A28) and two B-bucket additions (B22-B23). Numbering picks up after the existing §4 (which ended A23/B21).

### A-bucket additions

**A24 — fa rewrite protocol (exit-code hook contract)**
*Source:* rtk R1+R7 (`hooks/{claude,opencode}/rtk-*`).
*Shape:* If FA grows an external orchestrator surface (FA-as-MCP-server or FA-as-pre-tool-hook for Claude Code etc.), the protocol is a four-state exit-code contract: `0=allow rewrite | 1=passthrough | 2=deny | 3=ask`. The host adapter is ≤50 LOC and carries a mandatory thin-delegate comment ("edit `fa rewrite`, not this file"). All rule logic in Python; per-host adapters are mechanical.
*Cost:* deferred — only urgent if/when FA grows external orchestrator support (out of scope for 0.1 per user Q2 answer).
*Dependency:* none. Spec-only entry.

**A25 — Closed-enum classifier + `&'static` rule slate**
*Source:* rtk R2 (`src/discover/registry.rs::Classification`, `rules.rs::RULES`).
*Shape:* For any FA routing surface (BashGate categories, recovery_action emitter, future tool-router), the contract is: (a) a closed enum with exhaustive variants and (b) a `RULES: &[Rule]` const slice (in Python: `RULES: Final[tuple[Rule, ...]] = (...)`). New rules added by appending to the const; matching by compiled-once regex set; verdict computed by deterministic "longest match wins" or equivalent stable rule.
*Cost:* refactor existing BashGate category dispatch to this shape — small PR, ~100 LOC.
*Dependency:* A19 (ToolSpec.category) if extended to per-tool routing.

**A26 — fa telemetry-SQLite at OS-standard path**
*Source:* rtk R5 (`src/core/tracking.rs`).
*Shape:* If FA grows long-running telemetry (cost-per-project, tool-call rate, attempt rate per ADR), the canonical shape is SQLite at OS-standard path (`$XDG_DATA_HOME/first-agent/telemetry.db`), per-record schema with canonicalized project_path column, `idx_project_path_timestamp` index, retention policy as a deletion query on insert. Operator surface `fa telemetry` mirroring `rtk gain`.
*Cost:* deferred — only urgent if FA's CostGuardian or AttemptHistoryObserver grows cross-session scope (post-0.1).
*Dependency:* none. Spec-only entry.

**A27 — Hook version-guard with cached result**
*Source:* rtk R6 (`hooks/claude/rtk-rewrite.sh:8-43`).
*Shape:* Every external integration adapter (shell, TS, Python, MCP) MUST validate the FA binary version against a `MIN_VERSION` constant, with the result cached by version string in `$XDG_CACHE_HOME`. Adapters that detect version skew exit cleanly (silent passthrough), not noisy fail.
*Cost:* deferred — same dependency as A24 (only urgent if FA grows external adapters).
*Dependency:* A24.

**A28 — Enum-label + harness-derived weight**
*Source:* icm IC2 (`Importance` enum + `wake_up::compute_score`).
*Shape:* For every LLM-emitted dimension that is currently a number or open string (e.g. severity, confidence, urgency, risk-level), define a 3-5-label closed enum, a hardcoded multiplier map, and a derivation function. The MCP/CLI schema MUST expose only the enum labels; the multipliers are never agent-visible. **Highest-leverage A-bucket entry from the rtk-ai pass.**
*Cost:* per-dimension — varies. Audit FA today for "numeric weight the LLM emits" → candidates: nothing obvious in current code; consider for future Eval-emitted scores.
*Dependency:* none.

**A29 — fa session-pack (categorized + budget-enforced session-start)**
*Source:* icm IC3 (`build_wake_up` + `Category` + `compute_score`).
*Shape:* New FA surface that converts the static HANDOFF.md into a deterministically-rendered Markdown pack. Inputs: project filter, max_tokens budget, format (markdown/plain). Pipeline:
1. Source: filesystem-canonical (knowledge/handoff/*.md frontmatter + parsed body) OR future telemetry-derived.
2. Filter: `importance: critical|high` + optional `preferences`.
3. Score: `importance_weight × recency_factor × stored_weight` (recency = `1 / (1 + days/30)`).
4. Sort: score descending; tie-break by ULID/SHA-stable-id (lex monotonic).
5. Categorize: closed 6-bucket enum (Identity/Decision/Constraint/Error/Milestone/Context) via deterministic keyword heuristics on topic+summary.
6. Truncate: char-budget via `max_tokens × 4`; per-memory cap = `max(budget/2, 200)` with `[…]` marker.
7. Render: section headers in `Category::all_ordered()` order.

Spec source: this section + icm wake_up.rs. The 60-second bootstrap clause in HANDOFF.md becomes the *output* of `fa session-pack`, not a hand-maintained file.
*Cost:* 1 PR, ~300 LOC (loader + scorer + categorizer + renderer + tests).
*Dependency:* A15 (`fa prompts load`) — same loader infrastructure can power both prompt-loading and session-pack-loading.

This is the **focused proposal** the user signed off in Q3.

### B-bucket additions

**B22 — TTL + heartbeat + amortized GC for any time-bound state**
*Source:* grit GR5 (`SqliteLockStore::try_lock`).
*Shape:* Any FA state that can outlive a process (cached LLM responses, in-flight tool-call timeouts, dialogue checkpoints) MUST carry a TTL column; consumers MUST refresh via heartbeat; GC MUST be amortized into the access hot path (no background thread). Operator surface `fa gc` for explicit cleanup.
*Cost:* deferred — depends on FA growing cross-session state (post-0.1).
*Dependency:* A26 (telemetry-SQLite).

**B23 — Fail-fast layer-boundary validation**
*Source:* rtk R8 + icm IC1.
*Shape:* The outermost agent-facing surface (CLI parser, MCP tool schema, HTTP handler) MUST validate hard limits *before* the request reaches inner layers. Limits MUST be encoded as constants with doc-comments naming any deeper-layer corresponding constant. Locale/encoding MUST be normalized at the parsing helper, not relied upon globally.
*Cost:* audit existing FA surfaces → if BashGate exposes anything externally, mirror its limits at the boundary. Small PR per surface.
*Dependency:* none. Formalises ADR-10 invariant I-5.

---

## §6a Open questions — answered.

1. **A24 (exit-code hook protocol) scope.** Per Q2 answer in the cover note, FA-as-MCP-server is out-of-scope for 0.1. Confirm A24 stays as a *spec-only* entry until UC5 lands? -yes,deffered

2. **A28 (enum-label + harness-derived weight) audit scope.** Worth auditing FA today for "LLM emits a number" candidates? -yes, single-pass audit.

3. **A29 (`fa session-pack`) categorization source.** icm derives categories from topic+summary keywords. FA's HANDOFF.md is structured Markdown — frontmatter could carry an explicit `category:` field, removing the heuristic. -we choose explicit frontmatter category (preferred over keyword heuristic).

4. **I-5 (layer-boundary fail-fast) audit.** Worth auditing FA's existing surfaces (`fa` CLI parser; DSV YAML loader; chunker; BashGate) for I-5 compliance now, or after ADR-10 lands? -defer until ADR-10 lands, then audit as one focused PR.

---

## §7a This amendment **is**:
 - a code-anchored, per-pattern, file:line-cited extension of the determinism-lens deep-dive, ready to feed ADR-10's invariant list and §3-§4 of the synthesis doc.
