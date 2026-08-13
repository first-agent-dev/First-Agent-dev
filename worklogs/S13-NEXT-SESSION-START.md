# S13 next-session start prompt

> [!CAUTION]
> **HISTORICAL / SUPERSEDED (2026-08-13).** Do not execute the environment,
> checkout, patch, identity, or bootstrap commands below. They describe an old
> session handoff. Current workspace authority:
> [ADR-13](../knowledge/adr/ADR-13-workspace-isolation.md) and
> [AP-004](../knowledge/anti-patterns/AP-004-symptom-chasing-without-model.md).

Paste everything below the line into a fresh session.

---

## Task

Continue the First-Agent **CLI/formal-trace substrate re-baselining workplan** at
**Slice 13 (S13) — multi-provider conformance**, then the next items (live
confirmation, S13.7–S13.9, thinking-mode toggle). The **closed core of S13 is
implemented and green**; what remains is live-on-the-box confirmation and the
open-exploration provider work.

**Do not write code yet.** First task is: clone, set up the environment, read
the plans and the code they touch, and give me a source-verified assessment of
current state vs the S13 plan's Definition of Done. Then stop and report before
any edit.

## Repository and patch

```bash
git clone https://github.com/first-agent-dev/First-Agent-dev.git
cd First-Agent-dev
git checkout 6cd60f1b5affe22cdb32f89a9f0a993e27d43e4a    # "slice 13 first halve" (the S13 base)
git apply /path/to/S13-since-first-half.patch            # all S13 work since that base
```

- Patch: `/home/user/S13-since-first-half.patch` — sha256
  `8e2a587b5757728a23fe2589d976e1eef2128cbea8ace979f4249501991a19be`, 11780 lines,
  210 files (src + tests + docs + plans). Base = `6cd60f1`. **Verify it applies with
  `git apply --check` first.**
- If the base commit or patch is not reachable (shallow clone), fetch it:
  `git fetch --depth=2 https://github.com/first-agent-dev/First-Agent-dev 6cd60f1b5affe22cdb32f89a9f0a993e27d43e4a`
- Also present in `/home/user/`:
  - `S13-multi-provider-conformance.patch` (older, S13.0–S13.6 pre-S13.10 — superseded),
  - `S13-prompt-cache-backlog-notes.patch` (I-54 prompt-cache backlog note),
  - `assessment-vs-main-workplan.md`, `wire-search-lost-capabilities.md`,
    `research-blackboard-query-tool-gap.md`, `research-simple-thinking-lane.md`,
    `research-temperature-topsampling.md`, `research-thinkingflag-edgecases.md`.

## Environment (the sandbox resets; `uv`/`.venv` disappear every turn)

```bash
pip install -q uv
export PATH="/usr/local/bin:$PATH:$HOME/.local/bin"
uv sync --frozen --extra dev
git config user.email "fa@local" && git config user.name "fa"
```

**Two instrument checks before trusting any measurement** (both have produced
false results in this workplan):

```bash
uv run python -c "import fa; print(fa.__file__)"   # must be <repo>/src/fa/__init__.py
uv run which pytest                                 # MUST resolve inside .venv/
```

Also: the sandbox strips exec-bits from `scripts/*.sh` and
`src/fa/hygiene/hooks/*` (mode-only diffs). Restore at the end with
`git diff --name-only | while read f; do case "$f" in *.sh|*/hooks/*|scripts/fa) chmod 755 "$f";; *) chmod 644 "$f";; esac; done` —
but keep `src/fa/inner_loop/hooks/*.py` at 644.

**Current baseline (verify before editing):** full suite **2575 passed, 15
skipped, 1 xfailed**; the 1 xfail is the pre-existing Q19 subagent-containment
gap (unchanged). `just check` gates all pass (ruff, mypy, deptry, pylint,
authoring-check, contract-check, log-kind-check, no-mocked-dataclasses,
cli-coverage-floor).

## Skills (loaded via knowledge/skills/ — use them)

- **plan-authoring** — READY-gated, source-grounded plans; kill-checks; anti-theater.
- **tests-writing** — C0/C0p/C1/C2/C3 classes; producer kill-checks; no dead-path/consumer-only tests.
- **feature-planning** — large-feature execution; per-edit gates; after-edit gates.
- **repo-audit** — gap/wire-search.
- **doc-maintenance** — cross-reference cascade (llms.txt/AGENTS.md/reference.md).
- **mutation-clearing**, **pr-creation**, **skill-writing** — as applicable.

## Read these, in this order

1. **Parent plan (tracks ALL slices before S13):**
   `worklogs/implementation-plans/cli-trace-substrate-rebaseline-2026-07-25.md`
   — `PLAN-cli-trace-substrate-20260725`. This is the "cli substrate" workplan
   that S1–S12 and S13 are slices of. Status DRAFT/P3. It records progression of
   every prior slice and S13's place in the sequence.
2. **The slice you are executing:**
   `worklogs/implementation-plans/PLAN-cli-trace-S13-multi-provider-conformance.md`
   — open-scope. Closed core S13.0–S13.4c (DONE), open exploration S13.5–S13.9.
   Contracts CT1–CT8, kill-checks K1–K10, open questions Q61–Q65.
3. **The live-execution sheet (what needs running on the box):**
   `worklogs/S13-live-sheet.md` — S11-style copy-paste sheet. Steps S13.1–S13.10:
   probe, conformance matrix, run, **S13.3b sampling-omission on the wire**
   (`FA_DEBUG_LLM_BODIES=1`), workflow past stage 2, cache-hit ≥74% (R1 gate),
   routing-check, stats, selfcheck, request-shape error-surfacing, 429-resume.
4. `worklogs/S13-SESSION-START-PROMPT.md` — the PREVIOUS session-start (older base
   `35068c6`, patch `S13-on-35068c6`) — historical, superseded by this file.
5. `worklogs/implementation-plans/PLAN-cli-trace-S11-controlled-deployment.md` —
   the live evidence S13 is built on (execution notes R10–R26).
6. `knowledge/BACKLOG.md` — **I-55 (subagent WIP) and I-56 (blackboard WIP)** are
   the newest; I-46–I-54 are earlier S13 findings (I-54 = prompt-cache).

## Current state (source-verified as of this handoff — re-verify, don't trust)

**DONE and green:**

- S13 closed core (S13.0–S13.4): I-50/I-52/I-51 fixed; `MessageRules` +
  conformance finalizer at `chain.py:368`; K1–K7 verified.
- S13.4c/CT8: eval independence blocking → adversarial; K9/K10.
- S13.5: conformance harness (CONF-1..7 offline) + `fa conformance` CLI.
- S13.6: rate-limit-aware live runner (K8 resume).
- S13.10: tool-name dot→underscore rename; `TOOL_NAMES` now a direct frozenset
  (20 names, `LEGACY_TO_NEW` pruned); `fs_blackboard_query` tool built +
  registered in implementer/planner + tested (14 tests).
- `fa conformance` offline matrix works (CONF-6 recorded as tolerance).

**OPEN / next items:**

1. **Live confirmation on the deployed box** (`fa@fa-HP`) — run
   `worklogs/S13-live-sheet.md` step-by-step; share output for evaluation. The
   big unverified claims: sampling-omission on the wire, workflow past stage 2,
   cache-hit ≥74%, NVIDIA matrix no longer 400s.
2. **S13.7** — onboard Groq/Cerebras/NVIDIA (registry names exist; need live CONF +
   `MessageRules` from measured behaviour). Needs real keys (Q61).
3. **S13.8** — Gemini adapter (does not exist yet; the non-OpenAI-shaped adapter,
   ~200-line budget).
4. **S13.9** — cross-family workflow (planner→coder→eval across ≥2 families).
5. **S13-thinking-mode-toggle** — `worklogs/implementation-plans/PLAN-cli-trace-S13-thinking-mode-toggle.md`
   (DRAFT). The sampling-default change (omit temp/top_p) already shipped; the
   `--thinking_mode` flag itself is planned, not built.
6. **Backlog I-55 (subagent) / I-56 (blackboard)** — WIP features; blackboard is
   the next slice per I-56 (the `fs_blackboard_query` tool is the substrate side;
   the artifact index/writer + "rank" are the follow-up).

## Important notes / gotchas

- **`fa workflow` task is POSITIONAL** (`fa workflow <roles> <task>`), NOT `--task`
  (which is ambiguous with `--task-planner/--task-coder/--task-eval`). The live
  sheet uses the positional form.
- **`fa conformance --provider <name>` uses the `coder` role's chain** — requires
  `coder` in models.yaml.
- **Cache-hit ratio** = `cache_read / (cache_read + cache_creation + uncached)`,
  read from `event_log` rows where `kind='usage'` in `~/.fa/session-log/<run_id>/session.db`.
- **Sampling omission** is confirmed via `FA_DEBUG_LLM_BODIES=1` →
  `~/.fa/session-log/<run_id>/llm_bodies.jsonl`; assert no `temperature`/`top_p` key.
- **Provider registry**: 18 names → 4 adapters. `nvidia_build` is OpenAI-compat
  with `supports_prompt_cache=False` (its own rules). `mistral` has
  `requires_top_p_one_when_greedy=True` (I-48).
- **Decision already made — do not reopen:** eval independence is non-blocking +
  adversarial stance (not a hard config error). Same-family eval loads with a
  warning.
- **Never mark a step done from "no exception".** Use the plan's DoD/kill-checks
  and `just check` as the real gate. No `noqa` waivers unless the design genuinely
  cannot avoid it.

## Working agreement

State source-verified current behavior + contract/gap IDs + exact files allowed
before editing; per-edit state intent/current→target/mechanism/rationale/failure
behavior/DoD/negative-proof/tests-writing-class/kill-check; run targeted tests +
static checks + show git diff with actual command output; kill-check on the
PRODUCER, never consumer-only.

## Deliverables

- `.patch` files beside the repo clone in `/home/user/`.
- Update `worklogs/HANDOFF.md` (currently stale — it ends ~S10b/S11 era and does
  not record S13 core/5/6/10 completion or the open surface).
- Regenerate `S13-since-first-half.patch` after any change and verify it applies
  cleanly on a fresh `6cd60f1` checkout.
