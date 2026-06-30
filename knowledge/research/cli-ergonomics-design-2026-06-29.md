---
title: "CLI ergonomics redesign — multi-role workflows, Russian help, WebUI-ready help metadata"
compiled: 2026-06-29
status: proposal
---

# §0 Decision Briefing

**Goal.** Make `fa` faster and smarter to drive — especially multi-role workflows
(planner → coder → eval) — without making the surface hard to remember; add
Russian `-h/--help` everywhere; lay a foundation a future WebUI can reuse for
per-command help buttons.

**Three problems today**

1. **Multi-role is three near-identical long lines.** Per `02-operations.md §7.2`:
   ```bash
   fa run --role planner --workspace /workspace --run-id work-1 --task "Спланируй X"
   fa run --role coder   --workspace /workspace --run-id work-1 --resume --task "Реализуй X"
   fa run --role eval    --workspace /workspace --run-id work-1 --resume --task "Проверь X"
   ```
   `--workspace`, `--run-id`, `--resume` are repeated by hand; the task is retyped.
2. **No Russian help; help is English-only argparse.** No machine-readable help a
   WebUI could render.
3. **`fa clean-rebuild` doesn't exist** in the wrapper; `fa-update.sh` /
   `fa-clean-rebuild.sh` have no `-h/--help`.

**Recommendation (what this note proposes to implement)**

- **R-1 — task becomes positional + quoted** (industry-standard): `fa run "do X"`.
  Keep `--task` as a back-compat alias (no breakage).
- **R-2 — `-m/--model`-style short role flag**: `fa run -r planner "do X"`
  (`-r` == `--role`). Short single-char flags are the one single-dash form argparse
  supports natively, matching `llm -m`, `claude -p`, `aichat -m`.
- **R-3 — NEW `fa workflow` command for multi-role chains.** One line drives the
  whole pipeline with shared workspace/run-id and auto-`--resume`:
  ```bash
  fa workflow planner,coder,eval "Реализуй X"
  ```
  This is the high-ROI win for your stated focus.
- **R-4 — Russian help via a structured command registry** (one source of truth)
  consumed by both CLI and a future WebUI.
- **R-5 — wire `fa clean-rebuild`** into the wrapper; add `-h/--help` to both
  `fa-update.sh` and `fa-clean-rebuild.sh`.

**Explicitly NOT doing** single-dash multi-char flags (`-task`, `-role`): argparse
rejects them; emulating it means hand-rolling a parser and losing argparse's help,
error messages, and test surface — high cost, low value once R-1/R-2/R-3 land.

---

# §1 Prior art (5-min scan)

| Tool | Task/prompt | Model/role | Notes |
|---|---|---|---|
| Simon Willison `llm` | **positional** `llm "Hello"` | `-m claude-3` | `-s` system prompt; pipe-friendly |
| Claude Code | **positional** `claude "do X"` / `-p` print-mode | `--model opus` | wrappers bake in always-on flags |
| `aichat` | **positional** `aichat "Hello"` | `-m claude:opus` | `provider:model` compact value |
| AWS Bedrock CLI | JSON `--body "{...}"` | in body | verbose; enterprise — anti-pattern for us |

**Convergent lesson:** the expensive-to-type thing (the task/prompt) is **positional
and quoted**; the model/role is a **short flag with a compact value**; **wrappers
exist precisely to stop re-typing the always-on flags**. FA's `fa run --task "..."`
is the outlier. Sources captured in web research 2026-06-29.

---

# §2 Why not `fa run -planner,coder,eval "task"` literally

Your first instinct — a bare keyword `-planner,coder,eval` — is close to right; the
refinement is *where* the keyword goes:

- argparse cannot bind `-planner` (single-dash, multi-char) to an option; it parses
  it as the cluster of short flags `-p -l -a …`. Supporting it means abandoning
  argparse's parser. **Cost > benefit.**
- The robust, memorable form keeps the task quoted (so any prompt text is safe) and
  puts the role list where a value belongs:
  - single role: `fa run -r planner "task"`
  - multi-role pipeline: `fa workflow planner,coder,eval "task"`  (NEW command —
    the role list is the first positional, the quoted task the second)
- This is *more* robust than a bare keyword because the quoted task can contain
  dashes, commas, quotes — the parser never confuses task text for flags.

---

# §3 The four invocation strategies (pick the ones to ship)

### Strategy A — positional task + short flags (low risk, big daily win)
```bash
fa run "Реализуй X"                  # role defaults to coder
fa run -r planner "Спланируй X"      # -r == --role
fa run -r coder -n 20 "Большая задача"   # -n == --max-turns
```
- `--task` kept as alias; all existing docs/scripts keep working.
- Short aliases proposed: `-r`/`--role`, `-n`/`--max-turns`, `-w`/`--workspace`,
  `-c`/`--config`, `-i`/`--run-id`.

### Strategy B — `fa workflow` multi-role pipeline (the headline feature)
```bash
fa workflow planner,coder,eval "Реализуй фичу X"
# = planner (fresh) → coder (--resume) → eval (--resume),
#   all sharing one auto-generated run-id + one workspace.
```
- Auto-derives a shared `--run-id` (timestamp+slug) once; passes it to every stage.
- First stage fresh; subsequent stages get `--resume` automatically (reads prior
  stage's PR draft — exactly the `§7.2` pattern, collapsed to one line).
- Per-stage task override (optional, power users):
  `fa workflow planner,coder,eval --task-planner "..." --task-coder "..."`.
- Stops the pipeline on the first non-zero stage exit (fail-fast); prints a
  per-stage summary.

### Strategy C — saved task "profiles" (optional, defer-able)
```bash
fa run --profile big-refactor "task"   # loads role/max-turns/detail from a profile
```
- A tiny `~/.fa/profiles/<name>.toml` of default flags. Defer to a follow-up unless
  wanted now — adds a file format + consumer.

### Strategy D — pipe the task in (free, comes with R-1)
```bash
echo "Многострочная задача…" | fa run -r coder -
git diff | fa run -r eval "Проверь этот дифф"
```
- `-` as the positional task means "read task from stdin" (llm/claude pattern).

**Ship now:** A, B, D. **Defer:** C (needs a profile file + consumer).

---

# §4 Russian help + WebUI-ready foundation (R-4)

**Single source of truth = a structured command registry**, not scattered argparse
strings. A small Python module (`src/fa/cli_help.py`) exporting one dict:

```python
COMMANDS = {
  "run": {
    "summary_ru": "Запустить LLM-сессию агента.",
    "summary_en": "Drive an LLM coder session.",
    "args": {
      "task":      {"ru": "Текст задачи (в кавычках). '-' = читать из stdin.",
                    "en": "Task text (quoted). '-' = read from stdin."},
      "--role/-r": {"ru": "Роль: planner | coder | eval (по умолчанию coder).", ...},
      ...
    },
    "examples": ['fa run "Исправь баг в src/x.py"',
                 'fa run -r planner "Спланируй рефакторинг"'],
  },
  ...
}
```

Consumers (all read the *same* dict):
1. **CLI** — `fa <cmd> -h` renders the Russian block (argparse stays for parsing;
   we override `format_help` / add an epilog from the registry).
2. **Wrapper** — `fa help` / `fa <cmd> -h` host-side prints the same Russian text
   without entering the container (fast, works even if the container is down).
3. **Future WebUI** — imports `COMMANDS` (or a `fa help --json` dump) to render
   help buttons/tooltips. **`fa help --json` is the WebUI contract** — stable,
   machine-readable, bilingual.

This keeps argparse's robust parsing while giving you bilingual + WebUI help from
one place. Adding a new command = add one dict entry (consumer rule satisfied).

---

# §5 `-h/--help` for the shell scripts (R-5)

- `fa-update.sh` and `fa-clean-rebuild.sh` each get a `usage_ru()` that fires on
  `-h|--help|help` **before** `set -e`/side effects, in Russian, listing env-var
  flags (e.g. `WIPE_STATE=1`, `SKIP_TESTS=1`).
- Wrapper: add `clean-rebuild)` case → `exec fa-clean-rebuild.sh "$@"` (mirrors the
  existing `update)` case). `fa clean-rebuild -h` then shows the script's Russian
  help.

---

# §6 Subtraction check (AGENTS.md Step 4)

- **Removing what makes this redundant?** `fa workflow` removes the need to hand-copy
  the 3-line `§7.2` block; the registry removes scattered help strings.
- **Capability lost if omitted?** Without `fa workflow`, multi-role stays 3 manual
  lines with copy-paste run-id errors (a real failure mode). Without the registry,
  no bilingual/WebUI help.
- **OSS precedent?** Positional task + short model flag = `llm`, `claude`, `aichat`.
  git-style pipeline subcommand = standard. JSON help dump = `aws … help`,
  `kubectl … -o json` discovery patterns.
