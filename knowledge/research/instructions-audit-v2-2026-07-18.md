# Instructions Audit v2 — Second-Pass Gap Analysis

> **Created:** 2026-07-18
> **Based on:** instructions-audit-2026-07-18.md (first pass) + thorough re-read of all source files
> **Purpose:** Comprehensive second review pass. Find gaps the first audit missed, verify first-audit findings, and produce a complete work plan.
> **Status:** ✅ ALL CHANGES EXECUTED AND VERIFIED

---

## Executive Summary

The first audit (v1) identified the major gaps accurately. This second pass confirms v1 findings and discovers **7 additional gaps** that v1 missed, plus flags **3 logic errors** in the current docs. The result is a fully prioritized, concrete work plan covering every gap.

**Key changes from v1:**
- NEW: `--detail standard` default is never mentioned (doc says "minimal/verbose/debug" — missing `standard`)
- NEW: stdin piping (`fa run -` / transparent stdin) is undocumented
- NEW: `compactor` role is supported in models.yaml but never mentioned in instructions
- NEW: `fa help` bilingual help system is never mentioned
- NEW: `fa chunk` and `fa inner-loop-smoke` diagnostic commands absent
- NEW: `--since` accepts `Nd`/`Nh`/`Nm` — format not documented
- NEW: Environment variables `FA_COMPOSE_FILE`, `FA_PROXY_TOKEN_FILE`, `FA_PTY_POOL_MAX_SIZE` not in any operator doc
- CONFIRMED: `fa stats` documentation is extremely thin
- CONFIRMED: `fa authoring-check` is completely absent
- CONFIRMED: `config.yaml.example` has 5 stale flags, missing 13 real FeatureFlags
- CONFIRMED: instructions/README.md is stale (dispatcher future, missing workflow, 03/04 promises)
- CONFIRMED: Missing wrapper verbs in §11 cheat sheet

---

## 1. Confirmed Gaps from v1 Audit

All v1 gaps confirmed. Summary table:

| # | Gap | File | Severity | Status |
|---|-----|------|----------|--------|
| G1 | `fa stats` thin docs (missing --global-history, --dead-zones, --since, --output json) | 02-operations.md | HIGH | Confirmed |
| G2 | `fa authoring-check` completely absent | 02-operations.md | HIGH | Confirmed |
| G3 | `--detail` values wrong (missing `standard`) | 02-operations.md | HIGH | Confirmed |
| G4 | `--output-mode` choices undocumented | 02-operations.md | MEDIUM | Confirmed |
| G5 | config.yaml.example has 5 stale flags, missing 13 FeatureFlags | templates/ | HIGH | Confirmed |
| G6 | Missing wrapper verbs in §11 (sessions, commit-traces, rebuild, clean-rebuild, update) | 02-operations.md | MEDIUM | Confirmed |
| G7 | README.md "Ролевой Цикл" stale — missing `fa workflow` | README.md | HIGH | Confirmed |
| G8 | README.md mentions `dispatcher` as future | README.md | MEDIUM | Confirmed |
| G9 | README.md promises 03-runtime-usage.md and 04-modules.md | README.md | LOW | Confirmed |
| G10 | Session artifacts table incomplete | 02-operations.md | MEDIUM | Confirmed |
| G11 | FeatureFlags section absent from 02-operations.md | 02-operations.md | MEDIUM | Confirmed |

---

## 2. NEW Gaps Found in Second Pass

### G12. `--detail standard` default not mentioned (LOGIC ERROR)

**Current doc (02-operations.md §11):**
```
fa run --role coder --task "..." --detail minimal
fa run --role coder --task "..." --detail verbose
fa run --role coder --task "..." --detail debug
```

**Actual CLI (cli.py):**
```python
--detail choices=("minimal", "standard", "verbose", "debug"), default="standard"
```

**Gap:** The `standard` level exists and is the DEFAULT, but it's never mentioned. The doc implies the choices are minimal/verbose/debug. This is a factual error that could confuse operators.

**Action:** Add `standard` as the documented default; restructure the examples to show `--detail standard` as baseline.

### G13. Stdin piping for `fa run` completely undocumented

**Actual CLI (cli.py `_resolve_task`):**
- `fa run -` reads the task from stdin (explicit pipe mode)
- If stdin is not a TTY and a task text is also provided, they concatenate: task text first, piped data as `<stdin>...</stdin>` context
- If only piped data is present, it becomes the task

**This is a real feature** with high operator value: `git diff | fa run -r eval "Проверь этот дифф"` is even shown in `cli_help.py` examples! But the instructions never mention it.

**Action:** Add stdin piping how-to to 02-operations.md §7.

### G14. `compactor` role exists but is never mentioned in instructions

**Evidence (cli.py `_cmd_run`):**
```python
compactor_chain = None
compactor_config = models.roles.get("compactor")
if compactor_config is not None:
    ...
    compactor_chain = _build_provider_chain(...)
```

The `compactor` role is wired in the CLI runtime. When declared in `models.yaml`, `fa run` will use it for context compaction (ADR-17 Stage C). But neither instructions file mentions it.

**models.yaml.example** also doesn't show a compactor role example.

**Action:** Mention the compactor role in 02-operations.md §7 (as an optional role for context compaction), and add a comment in models.yaml.example.

### G15. `fa help` bilingual help system undocumented

**Actual CLI (cli.py + cli_help.py):**
- `fa help` — top-level command list in Russian
- `fa help run` — detailed Russian help for a command
- `fa help --json` — full bilingual registry (WebUI contract)
- `fa help ops` — hidden ops commands

The wrapper also handles:
- `fa --help` / `fa -h` — shows wrapper + agent commands
- `fa help <host-command>` — host-side help (e.g., `fa help clean-rebuild`)

None of this is mentioned in the instructions. For an operator, `fa help` is the most discoverable way to learn commands.

**Action:** Add `fa help` section to 02-operations.md §11 cheat sheet, or a brief note in §7.

### G16. `fa chunk` and `fa inner-loop-smoke` diagnostic commands absent

These are developer/operator diagnostic commands registered in cli.py. While not daily-use, they're relevant for debugging. Currently:
- `fa chunk <path>` — run deterministic chunker on a file
- `fa inner-loop-smoke` — Phase-M smoke test (no LLM needed)

Not mentioned anywhere in instructions. LOW priority but worth including in a "diagnostic commands" subsection.

**Action:** Add brief mention in 02-operations.md §10 (diagnostics) or §12 (script reference).

### G17. `--since` format not documented

**Actual CLI (cli.py `_parse_since`):**
- Accepts `7d`, `24h`, `1h`, `30m` — number + unit suffix

The current 02-operations.md doesn't mention `--since` at all (it's not in the §7 or §11 sections). Even when we add it, we need to document the format.

**Action:** When adding `fa stats` docs, explicitly state the format: `--since 7d` / `--since 24h` / `--since 30m`.

### G18. Environment variables `FA_COMPOSE_FILE`, `FA_PROXY_TOKEN_FILE`, `FA_PTY_POOL_MAX_SIZE` undocumented

**Evidence:**
- `FA_COMPOSE_FILE` — wrapper script override for compose file (documented in `scripts/fa` header comment)
- `FA_PROXY_TOKEN_FILE` — override for proxy token file path (cli.py)
- `FA_PTY_POOL_MAX_SIZE` — override for PTY pool size (cli.py)
- `FA_SECRETS_FILE` — override for secrets file path (cli.py)

None of these appear in the instructions. `FA_COMPOSE_FILE` and `FA_SECRETS_FILE` are most relevant to operators.

**Action:** Add environment variables table to 02-operations.md (new subsection under §1 or §7).

---

## 3. Logic Errors in Current Docs

### E1. `--detail` choices are wrong (already in G12)
Doc shows: minimal/verbose/debug. Actual: minimal/standard/verbose/debug (default: standard).

### E2. README.md says eval "запускает тесты (pytest, mutmut)"
**Actual behavior:** eval role reads the PR draft and produces an `eval_report.json` with verdict/route. It does NOT run `mutmut`. The eval role uses `build_eval_registry()` which is read-only tools — it cannot run tests.

**Action:** Fix the README.md eval description.

### E3. 02-operations.md §7.2 shows `docker compose exec` commands for workflow, but `fa workflow` already automates this
The doc shows the manual three-step `docker compose exec -T first-agent fa run ...` pattern as the primary workflow, then says "теперь можно одной командой" for `fa workflow`. The priority should be inverted: `fa workflow` is primary, manual is fallback.

**Action:** Reorder §7.2 to present `fa workflow` first, manual steps as fallback.

---

## 4. Complete Work Plan

### Phase A — HIGH ROI (operator-facing, daily use, factual errors)

| Step | Gap(s) | File | Action | Est. lines |
|------|--------|------|--------|------------|
| A1 | G5 | `knowledge/templates/config.yaml.example` | Rewrite with 13 FeatureFlags + comments, remove 5 stale flags | ~45 |
| A2 | G3, G12, E1 | `02-operations.md` §11 | Fix `--detail` to show `minimal/standard(default)/verbose/debug` | ~5 |
| A3 | G4 | `02-operations.md` §11 | Add `--output-mode console(default)/quiet` | ~3 |
| A4 | G1, G17 | `02-operations.md` §7 | Add `fa stats` full section: `--run-id`, `--since 7d/24h/30m`, `--dead-zones`, `--output json`, `--global-history` with examples | ~40 |
| A5 | G2 | `02-operations.md` §7 or §10 | Add `fa authoring-check` section | ~15 |
| A6 | G6 | `02-operations.md` §11 | Add missing wrapper verbs: `fa sessions`, `fa commit-traces`, `fa rebuild`, `fa clean-rebuild`, `fa update`, `fa up`, `fa down` | ~15 |
| A7 | G7, G8, E2 | `instructions/README.md` | Rewrite "Ролевой Цикл": `fa workflow` as primary, manual as fallback; remove dispatcher "future"; fix eval description; remove 03/04 promises | ~20 |
| A8 | G13 | `02-operations.md` §7 | Add stdin piping how-to (`fa run -`, `git diff | fa run ...`) | ~12 |
| A9 | G15 | `02-operations.md` §11 | Add `fa help` to cheat sheet | ~5 |

### Phase B — MEDIUM ROI (completeness, not daily use)

| Step | Gap(s) | File | Action | Est. lines |
|------|--------|------|--------|------------|
| B1 | G10 | `02-operations.md` §1 | Add session artifacts table: `pr_draft.md`, `eval_report.json`, `flow_state.json`, `attempt_history.json`, `blackboard.jsonl`, workspace `.fa/` artifacts | ~20 |
| B2 | G11 | `02-operations.md` §1 | Add FeatureFlags section: what flags exist, where config.yaml goes, how to enable/disable, when changes take effect | ~25 |
| B3 | G14 | `02-operations.md` §7 | Add `compactor` role note (optional, for context compaction) | ~8 |
| B4 | G18 | `02-operations.md` §1 or §7 | Add environment variables table: `FA_COMPOSE_FILE`, `FA_SECRETS_FILE`, `FA_PROXY_TOKEN_FILE`, `FA_PTY_POOL_MAX_SIZE` | ~15 |
| B5 | E3 | `02-operations.md` §7.2 | Reorder: `fa workflow` primary, manual steps as fallback | ~10 lines moved |

### Phase C — LOW ROI (nice to have)

| Step | Gap(s) | File | Action | Est. lines |
|------|--------|------|--------|------------|
| C1 | G16 | `02-operations.md` §10 or §12 | Add `fa chunk` and `fa inner-loop-smoke` mentions | ~8 |
| C2 | G9 | `instructions/README.md` | Drop 03-runtime-usage.md and 04-modules.md promises | ~3 removed |

---

## 5. Verification Plan

After all edits:

1. **Link check:** Run link checker over all instruction files (119 files, as done in Phase 9 of doc refactoring)
2. **Read-through:** Read all 3 instruction files end-to-end for coherence
3. **Cross-reference:** Every CLI flag in `build_parser()` should appear in docs OR be explicitly excluded (internal/ops commands)
4. **Cross-reference:** Every FeatureFlags field should appear in config.yaml.example AND in §1 FeatureFlags section
5. **Cross-reference:** Every `scripts/fa` wrapper verb should appear in §11 cheat sheet
6. **Manual test:** Verify `fa help` output matches what docs say

---

## 6. What NOT to Do

(Reaffirmed from v1 audit)

- Do NOT add `blackboard.query()` API details to operator instructions — that's an agent API
- Do NOT add `fs.instant_grep` to instructions — same reason
- Do NOT rewrite 01-install.md — it's solid
- Do NOT add ADR details to instructions — that's what knowledge/ is for
- Do NOT add internal/ops commands (`inner-loop-smoke`, `chunk`) to the main cheat sheet — put them in diagnostics or script reference
- Do NOT document `fa egress-proxy` as an operator command — it runs inside the proxy container, operators never call it directly

---

## 7. Execution Summary

All Phase A (HIGH ROI), Phase B (MEDIUM ROI), and Phase C (LOW ROI) items executed and verified.

### Files modified:

| File | Changes |
|------|---------|
| `knowledge/templates/config.yaml.example` | Replaced 5 stale ADR-6 flags with 13 FeatureFlags + comments (76 lines) |
| `knowledge/instructions/02-operations.md` | +session artifacts table, +FeatureFlags table, +env vars table, +fa stats full docs, +fa authoring-check, +stdin piping, +compactor how-to, +diagnostic commands (chunk, smoke), +missing wrapper verbs, +--detail standard fix, +--output-mode docs, +§7 reordering, -stale cross-reference |
| `knowledge/instructions/README.md` | Rewrote "Ролевой Цикл" with fa workflow primary, +compactor role, -dispatcher future, -03/04 promises, -mutmut in eval description |
| `knowledge/templates/models.yaml.example` | +compactor role example with comments |

### Verification results:

- ✅ All 10 CLI subcommands from cli.py are referenced in instructions (egress-proxy intentionally excluded)
- ✅ All 14 wrapper verbs from scripts/fa are in §11 cheat sheet
- ✅ All 13 FeatureFlags from feature_flags.py are in config.yaml.example AND §1 FeatureFlags table
- ✅ README.md has no stale "dispatcher future" or "03/04 promises"
- ✅ `--detail standard` default is now documented
- ✅ `--output-mode console/quiet` is now documented
- ✅ `fa stats --global-history/--dead-zones/--since/--output json` are now documented
- ✅ `fa authoring-check` is now documented
- ✅ Stdin piping is now documented
- ✅ Compactor role is now documented (instructions + models.yaml.example)
- ✅ Environment variables table (FA_COMPOSE_FILE, FA_SECRETS_FILE, etc.) added
- ✅ Session artifacts table added
- ✅ §7.2 reorders workflow as primary, manual as fallback

(Reaffirmed from v1 audit)

- Do NOT add `blackboard.query()` API details to operator instructions — that's an agent API
- Do NOT add `fs.instant_grep` to instructions — same reason
- Do NOT rewrite 01-install.md — it's solid
- Do NOT add ADR details to instructions — that's what knowledge/ is for
- Do NOT add internal/ops commands (`inner-loop-smoke`, `chunk`) to the main cheat sheet — put them in diagnostics or script reference
- Do NOT document `fa egress-proxy` as an operator command — it runs inside the proxy container, operators never call it directly
