---
title: "Bootstrap-cost baseline — post-2026-05 readability refactor"
source:
  - "https://app.devin.ai/sessions/925cf134572d4f9aaa611591d62720d8"
  - "https://app.devin.ai/sessions/0fc8f9b26cf04aec92f598031e0dcf0f"
  - "https://app.devin.ai/sessions/1f41214431bd4c888071b6598c725710"
  - "https://app.devin.ai/sessions/89c32745c44f47dea679af42ed2d2dd8"
compiled: "2026-05-12"
chain_of_custody: |
  Counts for sessions A-D (tool calls / files opened / context
  tokens) are self-reported by each Devin session in a BOOTSTRAP
  REPORT block at the end of its session. The session URLs above
  (`source:`) are the authoritative chain-of-thought audit trail for
  A-D; numbers are agent-self-reported and may carry accounting
  error of order ±10 % (see §7 caveats). Session E numbers cited in
  §6 outlier row and §8 come from the user-provided attachment file
  `agent-reading-optimization-input.md` §1.2 (not preserved in this
  PR's tree); its original Devin session URL was not captured at
  the time and is therefore not available — Session E is included
  only as cautionary datapoint, never as part of the baseline range.
  Sessions F / G / H added 2026-05-12 from Arena.ai Agent Mode: the
  user ran the same single-message ADR-7-prep prompt three times on
  arena.ai's agent harness (which surveys multiple LLMs and does
  not disclose the underlying model identity to the agent). BOOTSTRAP
  REPORT blocks for F / G / H were copy-pasted by the user into the
  authoring session chat; Arena does not surface session URLs to the
  agent runtime, so the audit trail for F / G / H is the user-quoted
  chat transcript (preserved in this PR's authoring session URL
  `89c32745…` rather than separate Arena URLs). Numbers carry the
  same ±10 % accounting error caveat as A-D.
goal_lens: "Establish a quantitative bootstrap-cost baseline for Devin sessions on this repo after the 2026-05 readability refactor, so future refactor cycles can measure delta against this datapoint."
tier: stable
links:
  - "../adr/DIGEST.md"
  - "../project-overview.md"
  - "../llms.txt"
  - "../../HANDOFF.md"
mentions:
  - "Devin (Cognition AI)"
confidence: extracted
claims_requiring_verification:
  - "Session B agent self-reported `session_model: Devin (Cognition AI)` rather than `Opus 4.7`, and session C self-reported `Claude (via Devin)` rather than `GPT-5.5`. Selection-labels reflect user-side model choice at session-creation; agent introspection does not consistently return the requested model name."
  - "Session E (66 calls / 51 files) used a two-message prompt with «thoroughly analyze» framing; included only as cautionary datapoint, not part of the baseline range."
---

> **Status:** active. Measurement-evidence note (not a research-briefing
> note — exempt from [`pr-creation` skill PR Checklist rule #8](../skills/pr-creation/SKILL.md#pr-checklist)
> §0 Decision Briefing requirement, which is forward-only for the
> research-briefing workflow). First persistent datapoint for
> [`project-overview.md` §1.1](../project-overview.md#11-четыре-столпа-цели-project-goal--four-pillars)
> Pillar 4 (iteration via measurement).

## 1. Method

**Prompt** (single message, no attachments, sent verbatim to each session):

```text
Read repo MondayInRussian/First-Agent-fork2 until you would be ready to
start work on the next ADR (ADR-7 — inner-loop + tool-registry contract,
per HANDOFF.md §Next steps item 1).

Stop the moment you feel ready, and output exactly the following
report:

================ BOOTSTRAP REPORT ================
tool_calls_total: <int — ALL calls in this session>
  read_calls: <int>
  exec_calls: <int>
  other_calls: <int>

files_opened_count: <int — unique files opened via tool calls>
files_opened_list:
  - <relative path 1>
  ...
(Count only files YOU opened via read/exec; exclude system-injected
content like rules / knowledge notes / blueprint.)

context_tokens_estimate: <int, K tokens — best estimate of total
context-window consumption at this moment>

session_model: <model name>
session_url: <this session's URL>

stopping_reason: <one sentence — why you decided you were ready>
================ END REPORT ================
```

**Stopping criterion.** Model self-declares ready to start drafting
ADR-7. No external constraints on what to read.

**Sessions.** Seven sessions total. Sessions A / B / C / D are Devin
sessions on this repo at HEAD `a1aa74e8c114035d4745216e8745ec82e739346d`
(2026-05-11). Labels A / B / C reflect user-side model selection at
session creation; the `session_model` field in BOOTSTRAP REPORT blocks
frequently returns the generic «Devin (Cognition AI)» rather than the
requested model, so labels are selection-tags, not verified model
identity. Session D is the meta-session that processed the original
baseline; it ran a different task-shape (analysis of an improvements
file, not ADR-7 prep) and is excluded from the baseline range.
Sessions F / G / H were added 2026-05-12: the user ran the same
single-message ADR-7-prep prompt three times on **arena.ai Agent
Mode**, an external agent harness that surveys multiple LLMs per
request and does not disclose the underlying model identity. Each
Arena run hit `main` after PR #6 merge (HEAD shifted but `MUST READ
FIRST` / `TASK ROUTING` surface unchanged between A-D and F-H heads).
Sessions F-H are included as cross-harness validation that the
routing surface works for non-Devin agents (repo-readability test);
they are **not** a substitute for re-measuring First-Agent's own
future mid-tier harness (BACKLOG I-8).

## 2. Results

| # | Selection-label / harness    | Calls  | Reads | Exec | Other | Files | Context (≈) |
|---|------------------------------|--------|-------|------|-------|-------|-------------|
| A | "Sonnet 4 standard" (Devin)  | 32     | 21    | 3    | 8     | 16    | ~95 K       |
| B | "Opus 4.7" (Devin)           | 24     | 12    | 7    | 5     | 7     | ~95 K       |
| C | "GPT-5.5" (Devin)            | 43     | 27    | 7    | 9     | 16    | ~80 K       |
| D | "Sonnet 4.5" (Devin, meta)   | ~22    | ~12   | 2    | ~8    | 7     | ~43 K       |
| F | Arena.ai Agent Mode #1       | 18     | 0     | 14   | 4     | 21    | ~85 K       |
| G | Arena.ai Agent Mode #2       | 18     | 14    | 3    | 1     | 16    | ~95 K       |
| H | Arena.ai Agent Mode #3       | **9**  | 5     | 3    | 1     | **8** | ~70 K       |

Session URLs in frontmatter `source:` (D = this PR's authoring session;
F / G / H — Arena.ai does not surface session URLs to the agent
runtime, audit trail is the user-quoted BOOTSTRAP REPORT blocks in
the authoring chat). Bold = current best-case routing-compliant
floor across all measured harnesses.

## 3. The post-refactor bootstrap core (6-file irreducible / 9-file typical)

All six ADR-7-prep sessions (A, B, C, F, G, H — six independent
runs across two agent harnesses and ≥4 distinct model selections)
independently opened the same **six** files. This is the
**irreducible** core — observed in every session:

- `HANDOFF.md`
- `knowledge/llms.txt`
- `knowledge/adr/DIGEST.md`
- `knowledge/adr/ADR-template.md`
- `knowledge/research/efficient-llm-agent-harness-2026-05.md`
- `knowledge/trace/exploration_log.md`

Four of these six (`HANDOFF`, `llms.txt`, `DIGEST`,
`efficient-llm-agent-harness`) reproduce `llms.txt` §MUST READ FIRST
top-4 + §TASK ROUTING ADR-7 primary entry. `ADR-template.md` and
`exploration_log.md` are mandated for ADR-authoring tasks by
[`pr-creation` skill PR Checklist rule #9](../skills/pr-creation/SKILL.md#pr-checklist) and
the §When merging an ADR amendment cascade in
[`MAINTENANCE.md`](../MAINTENANCE.md).

A larger **typical** set of nine files appears in 4–5 of the six
sessions but not all six — model-specific or harness-specific
additions on top of the irreducible core:

- `AGENTS.md` *(typical, 5/6 sessions; B = Opus skipped, reading
  HANDOFF + llms.txt + DIGEST as the rule-surface proxy)*
- `knowledge/adr/ADR-2-llm-tiering.md` *(typical, 5/6 sessions;
  H = Arena #3 skipped)*
- `knowledge/project-overview.md` *(typical, 4/6 sessions; B and H
  skipped)*

Six independent agents (Sonnet 4, Opus 4.7, GPT-5.5, Arena #1,
Arena #2, Arena #3 — three of these on a non-Devin harness) сошлись
на одной и той же 6-файловой irreducible траектории чтения — strong
empirical evidence что routing-сигналы после 2026-05 refactor'а
работают **независимо от model selection и agent harness** (routing
surface, not harness-specific behaviour, drives the convergence).
Notably **`AGENTS.md` is not in the irreducible core** despite
[HANDOFF.md §60-second bootstrap step 1](../../HANDOFF.md#60-second-bootstrap)
mandating it — Opus B treated `HANDOFF` + `llms.txt` + `DIGEST` as
sufficient rule-surface. The sample is N = 1 and `AGENTS.md` remains
the authoritative rule-surface; the observation is a soft signal,
not a [BACKLOG](../BACKLOG.md) entry.

## 4. Where models diverged from the core

**A (Sonnet 4)** прочёл core + extended docs (README.md, AGENTS.md,
project-overview.md, glossary.md, adr/README.md, ADR-6) + **3 src/fa
code files** (`chunker/types.py`, `chunker/__init__.py`, `cli.py`).
Inner-loop ADR хочется проектировать с пониманием существующего
scaffold'а — разумный инженерный инстинкт; routing-сигналы такое
поведение не запрещают и не должны.

**C ("GPT-5.5")** прочёл core + extended docs + **3 extra research-
notes** (semi-autonomous, cutting-edge-radar, cross-reference-ampcode
-sliders). TASK ROUTING явно называет efficient-llm-agent-harness
primary, остальные — secondary; C прочёл всех secondary без явной
необходимости (+9 calls vs B при сопоставимом deliverable). CoT длился
3 м 40 с — модель плохо отслеживает свою call-history и тратит
cognitive effort на самопересчёт для report-формата. Это **structural
цена report-format**, не bootstrap-cost.

**B (Opus)** = clean minimum among Devin sessions: 7-файловый core,
100 % compliance с TASK ROUTING.

**F (Arena #1)** = patterns of A: 21 files including 5 `src/fa/` code
files + 2 secondary research-notes (semi-autonomous, cutting-edge-
radar). Like A, wants to see existing scaffold before designing
ADR-7. Distinguishing detail: 14 `exec` calls vs 0 `read` calls —
the Arena harness uses bash listings (`ls -la`, `cat`) where Devin
uses `read`; raw bash counts inflate total call count cosmetically
but don't change information consumption.

**G (Arena #2)** = patterns of A: 16 files including `pyproject.toml`
+ ADR-3 + `src/fa/chunker/types.py` + `src/fa/cli.py`. Same
«engineer-instinct» reading as A.

**H (Arena #3)** = new best-case floor across all measured harnesses:
9 calls / 8 files / ~70 K. Read exactly the 6-file irreducible core
plus `AGENTS.md` and a `ls -la` of repo root. Did **not** open
`project-overview.md` or `ADR-2-llm-tiering.md` that B and the other
top-tier Devin sessions included. Earliest «ready-to-draft» stopping
decision in the dataset — −60 % calls vs B. Whether this is
model-specific (Arena 3 reported «Claude family, specific model not
disclosed») or random variance is unresolved (N = 1 per Arena cell,
same caveat as §7).

## 5. Context-saturation effect

| # | Harness  | Files | Context (K) | Tokens-per-file |
|---|----------|-------|-------------|-----------------|
| A | Devin    | 16    | ~95         | ~5.9 K          |
| B | Devin    | 7     | ~95         | ~13.6 K         |
| C | Devin    | 16    | ~80         | ~5.0 K          |
| F | Arena.ai | 21    | ~85         | ~4.0 K          |
| G | Arena.ai | 16    | ~95         | ~5.9 K          |
| H | Arena.ai | 8     | ~70         | ~8.8 K          |

Devin sessions сходятся к ~80–95 K context при 2.3× разнице в files-
count — внутренний «feel ready» threshold ≈ 85 K у Devin-агентов.
Arena.ai sessions показывают более широкий разброс: 70–95 K со
стандартным отклонением ~12 K vs ~8 K у Devin. Session H (70 K)
stops below the Devin saturation band — либо разные harnesses имеют
разные feel-ready thresholds, либо это within-harness variance (N = 1
per cell). В обоих случаях главный вывод сохраняется: routing-signals
меняют **что именно** агент читает, не **сколько токенов** он тратит.
Польза refactor'а — в качестве потреблённых токенов (нужный core), не
в их сокращении.

## 6. Baseline range

| Метрика                                          | Значение                              | Источник                              |
|--------------------------------------------------|---------------------------------------|---------------------------------------|
| Bootstrap-floor (across all harnesses)           | **9 calls / 8 files / ~70 K**         | Session H (Arena.ai)                  |
| Bootstrap-floor (Devin only)                     | **24 calls / 7 files / ~95 K**        | Session B (Devin / Opus)              |
| Bootstrap-typical (Devin A + C range)            | **32–43 calls / 16 files / ~80–95 K** | Sessions A + C                        |
| Bootstrap-typical (Arena.ai F + G range)         | **18 calls / 16–21 files / ~85–95 K** | Sessions F + G                        |
| Bootstrap-outlier (deprecated framing)           | 66 calls / 51 files / ~87 K (read)    | Session E — see §8                    |
| Irreducible core size (across 6 sessions)        | **6 files**                           | §3 intersection of A∩B∩C∩F∩G∩H        |

## 7. Caveats

- **N = 1 per cell.** Within-model variance не измерена. Future PR
  может повторить тот же промпт на каждом label'е 2-3 раза для
  оценки variance.
- **No pre-refactor baseline.** Effectiveness claim — structural
  (6-файловый irreducible core воспроизводится во всех
  шести ADR-7-prep сессиях → routing работает), не количественный
  («стало на N % дешевле»).
- **Model identity not verified.** `session_model` field в BOOTSTRAP
  REPORT — agent self-report; Devin часто возвращает обобщённое
  «Devin (Cognition AI)». Selection-labels = user-side flag.
- **CoT-overhead structural.** GPT-семейство тратит ощутимый CoT
  cost на самопересчёт tool-calls для report-формата (Session C —
  3 м 40 с). Claude-семейство (A, B, D) — заметно лучше. Это
  свойство report-format, не bootstrap-cost.
- **Self-reported context tokens** — приблизительные оценки агентов,
  не authoritative metering. Real cost будет точнее после landing
  UC5 eval-harness (auto-collected metrics).

## 8. Excluded prior measurement (Session E)

Предшествующая сессия (66 calls, 51 files, ~86.5 K tokens read) была
исключена из baseline-диапазона. **Источник чисел:** user-provided
attachment file `agent-reading-optimization-input.md` §1.2 (artefact
не в дереве этого PR; original Devin session URL не зафиксирован в
момент сессии — см. также `chain_of_custody` frontmatter выше).
Причины exclusion: two-message prompt-shape с «thoroughly analyze»
framing'ом сместил агента в режим overview read-all; второе сообщение
запрашивало дополнительную статистику и удвоило tool-calls vs
single-message control. Сохранено здесь как cautionary datapoint —
future measurement prompts должны быть single-message и без
«overview / thorough» framing'а в формулировке.

## 9. Re-measurement trigger

Повторить эксперимент when ANY of:

1. [`knowledge/llms.txt`](../llms.txt) §MUST READ FIRST или
   §TASK ROUTING materially changed (more than typo / link fix).
2. [`HANDOFF.md`](../../HANDOFF.md) §60-second bootstrap rewritten.
3. [`knowledge/adr/DIGEST.md`](../adr/DIGEST.md) restructured or
   becomes stale.
4. A new model tier landed in
   [ADR-2](../adr/ADR-2-llm-tiering.md) — re-measure with the new tier.
5. First-Agent's own mid-tier OSS harness ships (Phase M; tracked
   as [BACKLOG I-8](../BACKLOG.md)) — re-measure on that harness to
   isolate harness-specific vs routing-surface effects (Arena.ai
   F-H validates repo readability across external harnesses but is
   not a substitute for the own-harness measurement).
6. UC5 eval-harness lands with auto-collected metrics (tracked as
   [BACKLOG I-7](../BACKLOG.md)) — at that point self-reported
   counts are superseded by traces and this baseline note becomes
   the migration source (§6 table → KPI schema).

В остальных случаях этот baseline остаётся valid reference до landing
UC5 eval-harness, который заменит self-reported метрики на auto-
collected traces.
