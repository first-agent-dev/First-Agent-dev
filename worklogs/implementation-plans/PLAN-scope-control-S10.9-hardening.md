# PLAN — S10.9: Hardening + live-verification rev3 (pre-merge)

**Slice:** S10.9 (scope-control hardening) · lands on PR #63 branch **before** merge
**Status:** READY (Q-H1/Q-H2 carry defaults; neither blocks)
**Traces-to:** review findings B1, F1–F13 (`REVIEW-PR63-findings.md`) + sheet findings
P1–P5 (`REVIEW-live-sheet-rev2.md`) · second-agent confirmation pass (zero false positives)
**Depends-on:** S1–S10 (shipped at `afaac84`) · **Target liveness:** L0→L2
(pure cores C0, wiring C1, real-CLI C2 for the calibration/mirror seams; live rows
themselves remain the L3 sheet, unblocked by this slice)
**Standing order honored:** the two doc-gate reds (`test_doc_links`,
`test_historical_workspace_docs_have_top_level_superseded_banner`) **stay red** —
they are the staged live-trial bait (sheet row L3). This slice must not fix them.

---

## 0. Read-before-plan log (all facts verified in-session against `afaac84`)

| Fact | Evidence |
|---|---|
| B1 red at tip | `scripts/verify_complexity_aware_execution.py:358` bare `write_text()`; encoding contract test fails deterministically; patch exists (`pr63-ci-fixes.patch`, applied in review clone) |
| E1101 red at tip | `reg.all_specs()` (no such member; `ToolRegistry` has `specs()`/`names()`); CI pylint on `scripts/` flags it; runtime fell through `hasattr` fallback → dead branch; same patch fixes |
| F1 | `calibration.py` flag `rate < (1.0 - epsilon)`; pytest covers 0.94/0.96 only; `<`→`<=` mutant survives pytest (16/16), killed by harness line 561 |
| F3 | `next_level()` validates `files_read/files_changed` but no branch reads them; `READ_LIMIT=10`/`CHANGE_LIMIT=3` inert |
| F4 | `cli.py:1447` facts provider passes `default_scope_risk_config()`; coder_loop uses loaded config |
| F5 | `coder_loop._load_scope_risk_config` prefers `<workspace>/.fa/config.yaml`; no other knob reads a workspace-level config (all use `DEFAULT_CONFIG_PATH = ~/.fa/config.yaml`) |
| F6 | `scope_expansion` appended only inside `if level_to != level_from:` (coder_loop ~:813/:821) |
| F7 | `build_handoff_task`: writes never trimmed; 40-write call renders 45 path items (verified by execution) |
| F8 | `_check_budget` does `max(1, int(...))`; K=0 silently becomes 1 (verified by execution) |
| F10 | `_prefix_matches` uses `lstrip("./")` (char-set strip); `fnmatch` `*` spans `/` despite comment |
| F11 | `_resolve_handoff_task`: provider call wrapped, `build_handoff_task(...)` outside try |
| P1 | `scope_expansion`/`expansion_exhausted` ∉ `CONSOLE_MIRROR_KINDS` (output.py:159–177); no `OutputEvent` at coder_loop :821/:1882; renderer prints `path`/`command` hints only; observation strings never rendered → **console is blind to the engine** |
| P2 | driver header claims "throwaway workspace copy"; code is `WS="${WORKSPACE_ARG:-$REPO}"` |
| Mirror pattern | `OutputEvent(type=..., turn=..., max_turns=..., data={...})` beside `log.append` (context_warn exemplar, coder_loop:983–994); renderer dispatches per `EventType` member |
| Event JSONL | `fa_session_log_root()/<run-id>/events.jsonl`; rows `json.dumps(asdict(event), ensure_ascii=False, sort_keys=True)` → `grep '"kind": "scope_expansion"'` is exact |
| Kind registration | new kinds need: `LogKind` literal (output.py) + `UNPARSED_KINDS` (stats.py) + producer/consumer contract script pass; console-mirrored kinds additionally need `CONSOLE_MIRROR_KINDS` + `EventType` member + renderer handler (dual-write contract auto-validated) |

---

## 1. Goals

- **G-H1** Branch tip passes its own deterministic gates (encoding, pylint-on-scripts, full suite modulo the two staged reds).
- **G-H2** Every documented invariant has a CI (pytest) kill-check — no harness-only invariants.
- **G-H3** No dead inputs, no silently-clamped config, no forked config conventions in the S10 surface.
- **G-H4** The evidence engine is observable: posture changes visible on the console; near-miss evidence durable for S11 tuning.
- **G-H5** Live sheet rev3 oracles read an artifact that provably contains the signals; live write-rows cannot dirty an operator's checkout unawares.
- **G-H6** Spec/ADR/PR-note truthfulness: superseded requirements carry dispositions; counts and caps match the code.

## 2. Gap register (finding → gap)

| GAP | Source | One-liner |
|---|---|---|
| GAP-H1 | B1 | encoding gate red at tip |
| GAP-H2 | E1101 | dead `all_specs` branch; scripts-lint red |
| GAP-H3 | F1 | ε boundary unguarded in pytest |
| GAP-H4 | F3 | dead counter params + overstated docstring |
| GAP-H5 | F4/F5 | handoff ignores operator tiers; invented workspace-config location |
| GAP-H6 | F6 | no durable near-miss telemetry (S11 data starvation) |
| GAP-H7 | F7/F8 | handoff cap excludes writes; K=0 clamped |
| GAP-H8 | F10/F11 | path-match nits; unguarded handoff construction |
| GAP-H9 | F2 | spec §3.4 superseded without disposition |
| GAP-H10 | P1 | live oracles blind (console carries no engine signal) |
| GAP-H11 | P2/P3 | false isolation claims; real-repo writes without procedure |
| GAP-H12 | P4/P5 | python/bash portability; missing preflights; L1 target file |

## 3. Decisions (operator-confirmed 2026-08-29 unless noted)

- **D-H1** One hardening slice S10.9 on the PR branch; merge after. *(operator)*
- **D-H2** Live write-rows: `git worktree` isolation for driver + L2; **L3 stays in the real repo by design** with mandatory pre-clean check + post-run review/restore procedure. *(operator)*
- **D-H3** F6 = **new kind `expansion_observed`** (not kind reuse): shipped tooling (sheet/driver greps, S8/S9 projections) already reads `scope_expansion` as "posture changed"; production rule — never redefine an event's semantics, add a type. Delta-gated emission (fire when the policy-relevant evidence tuple changes) bounds volume. *(reviewer recommendation, operator lean confirmed)*
- **D-H4** Console mirror: **both** `scope_expansion` + `expansion_exhausted`; `expansion_observed` stays JSONL-only (noise); JSONL grep remains the sheet oracle (stable contract vs styled prose). *(operator)*
- **D-H5** F3 resolution: **remove** `files_read`/`files_changed` from `next_level()`; the constants get a real job in the new pure helper `near_miss_evidence()` (GAP-H4+H6 close together). *(reviewer ruling — dead params on a pure policy fn are a trap)*
- **D-H6** F7 resolution: cap **Modified at 15** with explicit overflow marker `(+N more — run git status for the full set)`; total rendered path entries ≤ 30 + marker line; ADR wording amended to match. *(reviewer ruling — "writes are truth" survives via the marker + git; the context budget stays a real bound)*
- **D-H7** F8 resolution: honor K=0 (first call denied, message says escalation disabled by config); negatives clamp to 0. *(reviewer ruling)*
- **D-H8** F5 resolution by removal: scope-risk config reads `DEFAULT_CONFIG_PATH` only; the workspace candidate is deleted. A per-workspace config convention, if ever wanted, is a repo-wide decision — not a single-call-site invention. *(reviewer ruling)*

---

## 4. Contracts (each with kill-check)

- **CT-H1 (ε boundary).** `build_calibration_report` flags iff `runs_total ≥ min_flag_runs` **and** `rate < 1 − ε`; rate exactly `1 − ε` is **not** flagged — now pinned in pytest, not only the harness. *Kill-check:* flip `<`→`<=` → `test_epsilon_boundary_exactly_at_target_not_flagged` fails.
- **CT-H2 (honest policy core).** `next_level()` takes no counter params; tier/verify evidence only. `near_miss_evidence()` returns a payload iff no decision fired AND (`files_read > READ_LIMIT` OR `files_changed > CHANGE_LIMIT` OR `write_tier ≥ TIER_MEDIUM` OR (`read_tier_high` AND `level ≥ 2`)). *Kill-check:* make the helper return a constant truthy → truth-table test fails; re-add a counter branch to `next_level` → safe-bulk-silence tests fail (existing).
- **CT-H3 (delta-gated observation event).** `expansion_observed` is appended at most once per distinct evidence tuple per run, never on a transition turn (that turn belongs to `scope_expansion`), for all seeded modes including `workflow_linear` (telemetry records the seed-was-right case too). *Kill-check:* remove the delta gate → "no re-emit on unchanged evidence" test fails; emit on transition → "not on transition turn" test fails.
- **CT-H4 (dual-write mirror).** `scope_expansion` and `expansion_exhausted` are `CONSOLE_MIRROR_KINDS` members with `OutputEvent` emits beside their `log.append`s; renderer shows one line each at ≥ standard detail; `expansion_observed` is NOT mirrored. *Kill-check:* delete either emit → `check_log_kind_contract.py` fails (automatic); delete a renderer handler → renderer test fails.
- **CT-H5 (handoff caps).** `build_handoff_task` renders ≤ 30 path entries + at most one overflow marker; Modified capped at 15; writes beyond the cap are summarized, never silently dropped. *Kill-check:* remove the Modified cap → 40-write fixture test fails on total count.
- **CT-H6 (K honesty).** `_check_budget` denies when `invocation_count ≥ max(0, K)`; K=0 denies the first call with a config-disabled message; denied calls never reach the runner and never consume budget. *Kill-check:* restore `max(1, ...)` → K=0 harness check fails.
- **CT-H7 (tier-config consistency).** Escalation evidence and planner handoff classify paths with the **same** resolved config (`load_scope_risk_config()` from `path_risk.py`, reading `DEFAULT_CONFIG_PATH`). *Kill-check:* revert the facts provider to `default_scope_risk_config()` → configured-high-prefix handoff test fails.
- **CT-H8 (path-match correctness).** `_prefix_matches` strips `./` by prefix loop (dot-directories survive); glob prefixes match **segment-anchored** (`src/*` matches `src/a.py`, not `src/a/b.py`; `/**` remains subtree); literal prefixes remain boundary-aware. *Kill-check:* restore `lstrip("./")` → dot-prefix test fails; restore whole-path `fnmatch` → segment test fails.

---

## 5. Edit packets

### S10.9.0 — land the CI patch (GAP-H1, GAP-H2)
`scripts/verify_complexity_aware_execution.py`: apply `pr63-ci-fixes.patch` if not already
on the branch (line 358 `encoding="utf-8"`; `check_s2_chat_registry` → `reg.specs()`,
delete `_registry_has`). Verify: encoding test green; `pylint --disable=all
--enable=E,F,R0801,R0401 scripts/` clean; harness still ALL GREEN.

### S10.9.1 — ε boundary test (GAP-H3 / CT-H1)
`tests/test_calibration_success_rate.py`: add `test_epsilon_boundary_exactly_at_target_not_flagged`
(n=20, 19 ok, ε=0.05 → rate 0.95 → **not** flagged) and assert the 18-ok sibling (0.90)
**is** flagged, same builder.

### S10.9.2 — expansion.py: honest core + near-miss helper (GAP-H4, GAP-H6 / CT-H2)
- Remove `files_read`/`files_changed` from `next_level()`; docstring: policy is
  tier/verify-gated; counters live in caller telemetry and `near_miss_evidence`.
  **Regression guard (Phase-A audit):** `tests/test_expansion.py::test_negative_counters_rejected`
  (:219) pins the counter ValueError on `next_level` — migrate it to
  `near_miss_evidence` (which inherits the same validation). Call sites to update
  (mypy-enforced, 34 total): coder_loop ×1, test_expansion ×14, R1 ×3, R2 ×3,
  verify harness ×13.
- Add `near_miss_evidence(state, *, files_read, files_changed, write_tier,
  read_tier_high, verify_failed) -> dict[str, int | bool] | None` per CT-H2 (returns the
  evidence payload: counters, tiers, verify flag, level). `READ_LIMIT`/`CHANGE_LIMIT`
  finally load-bearing. `__all__` updated.
- Module docstring: drop the "bulk counters fire ONLY when a high tier is present"
  sentence (described a trigger that never existed); state the real policy + telemetry role.

### S10.9.3 — coder_loop wiring (GAP-H6 / CT-H3)
- Update the `next_level(...)` call (drop counter kwargs).
- After the transition branch: when `expansion_decision is None`, call
  `near_miss_evidence(...)`; keep `_last_observed_evidence` (tuple of sorted items);
  on change → `log.append(kind="expansion_observed", content={"turn", **evidence})`.
- Works for `workflow_linear`-seeded runs too (the block already runs for any
  `scope_mode`; `assumed_linear` only short-circuits `next_level`).

### S10.9.4 — kinds + mirror (GAP-H10 / CT-H4, D-H3/D-H4)
- `output.py`: `LogKind` += `"expansion_observed"`; `EventType` += `"scope_expansion"`,
  `"expansion_exhausted"`; `CONSOLE_MIRROR_KINDS` += those two (not `expansion_observed`).
- `stats.py`: `UNPARSED_KINDS` += `"expansion_observed"`.
- `coder_loop.py`: beside the transition `log.append` emit
  `OutputEvent(type="scope_expansion", turn=..., max_turns=..., data={level_from,
  level_to, evidence})`; beside the exhausted append emit
  `OutputEvent(type="expansion_exhausted", ...)`. Follow the context_warn exemplar
  (coder_loop:983–994).
- `ConsoleRenderer`: handlers rendering one line each at ≥ standard, e.g.
  `⤴ scope L1→L3 (high_tier_write)` / `⛔ escalation budget exhausted — finish and report`.
- **Regression guard (Phase-A audit):** `tests/test_s6_renderers.py` parametrizes from
  `typing.get_args(EventType)` and `test_payload_table_covers_every_event_type` asserts
  `set(_PAYLOADS) == set(ALL_EVENT_TYPES)` — add `_PAYLOADS` entries for both new types
  (payload keys must match the emitted `data` dicts) or that guard fails. Dispatch itself
  is `getattr(self, f"_handle_{type}", None)` — no exhaustiveness crash risk.
- Run `check_log_kind_contract.py` + `check_producer_consumer_contract.py` (dual-write
  and consumer registration are machine-checked).

### S10.9.5 — workflow_tool caps + K honesty + guard (GAP-H7, GAP-H8 / CT-H5, CT-H6)
- `build_handoff_task`: `modified_cap = 15`; overflow → single marker line; budget math
  updated so total path entries ≤ 30 + marker. Docstring updated.
- `_check_budget`: `budget = max(0, int(getattr(ctx, "max_invocations", 2)))`; message
  distinguishes `budget == 0` ("escalation disabled by config").
- `_resolve_handoff_task`: move `build_handoff_task(...)` **inside** the try; any raise →
  warning + return the bare goal (CT: construction failures degrade like provider failures).

### S10.9.6 — config plumbing (GAP-H5 / CT-H7, D-H8)
- Move `_load_scope_risk_config` from coder_loop → `path_risk.py` as public
  `load_scope_risk_config(config_path: Path | None = None)`; **remove** the
  `<workspace>/.fa/config.yaml` candidate; default `DEFAULT_CONFIG_PATH`; warnings logged.
- coder_loop imports it; `cli.py` `session_facts_provider` returns
  `"risk_config": load_scope_risk_config()` (replacing `default_scope_risk_config()`).

### S10.9.7 — path_risk match correctness (GAP-H8 / CT-H8)
`_prefix_matches`: replace `lstrip("./")` with the `while startswith("./")` loop (same as
`tier_for_path`); glob prefixes: keep `/**` subtree case; otherwise split on `/` and
fnmatch segment-wise with equal segment counts. Fix the comment (no more "single-segment"
claim contradicted by fnmatch semantics). **Phase-A audit:** existing config tests use
literal prefixes only (`medium: [docs, notes]`), so segment-anchoring is purely additive —
new T-H8 cases supply the glob coverage. Also confirmed: the TCB contract binds only
`authoring_tcb.py` (path_risk is free to import `fa.config`, which itself imports no
inner_loop modules — no cycle).

### S10.9.8 — spec disposition (GAP-H9)
`worklogs/implementation-plans/E3-SYSTEM-MAP-AND-S10-SPEC.md` §3.4 (line 713, the ×0.6
table at :721) + the completion-criteria row (line 845):
append a disposition block — "SUPERSEDED 2026-08-29 (S10.9): the ĉ×0.6 conflict penalty is
replaced by the two-layer evidence engine (ADR-16 addendum §A). The estimator is
deliberately weak; disagreement is resolved by runtime evidence, not confidence surgery.
No code implements §3.4 and none will." No other spec text changes.

### S10.9.9 — driver script (GAP-H10, H11, H12 / D-H2)
`scripts/run_live_expansion_trial.sh`:
- **Worktree isolation:** `git worktree add --detach "$TRIAL_DIR/worktree" HEAD` →
  default `WS="$TRIAL_DIR/worktree"`; `--clean` runs `git worktree remove --force`.
  If `git worktree` fails → loud warning + fall back to in-repo **only with explicit
  operator confirmation prompt** (RK-H2).
- **Signals from JSONL:** `EVENTS="$FA_STATE_ROOT/session-log/$RID/events.jsonl"`;
  panel counts `"kind": "scope_expansion"`, `"kind": "expansion_observed"`,
  `"kind": "expansion_exhausted"`, evidence names via `grep -oE
  'read_high_arm|high_tier_write|verify_failed'` on `$EVENTS`; console tee kept as
  narrative only; print both paths.
- **Preflight:** top-level `chat:` key in `models.yaml` (fail fast, exit 2, message).
- Header comments corrected (no false isolation claims).

### S10.9.10 — sheet rev3 (GAP-H10–H12, capture)
New `worklogs/reviews/S10-LIVE-VERIFICATION-rev3.md`; rev2 gets a one-line
"Superseded by rev3" banner at top (kept as evidence):
- Part 1: all Python via `uv run python`; expected-tail count string updated to the
  post-S10.9 harness total (regenerated from an actual run — never hand-typed).
- Part 2 header: "bash required" + every row wrapped in `bash <<'EOF' … EOF` (kills the
  zsh `PIPESTATUS` silent-empty failure).
- Every live row defines `EVENTS="$HOME/.fa/session-log/$RID/events.jsonl"` and greps
  **it** for the engine signals; console log stays the narrative artifact.
- L1: task reworded to "create or append one line in `worklogs/reviews/live-check-notes.md`"
  (file need not pre-exist; safe tier).
- L2: worktree prelude (copy the driver's two lines) + post-run `git worktree remove`.
- L3: real repo **by design**; pre-run `git status --porcelain` must be empty (abort
  otherwise); recommend scratch branch; post-run mandatory `git diff` review with
  keep-or-`git restore .` instruction.
- **S11 capture step (every row):** `mkdir -p worklogs/reviews/live-trial-data`;
  `cp "$EVENTS" .../$RID.events.jsonl`; append CSV row
  `run_id,date,row,recommended_mode,level_path,expansion_n,observed_n,exhausted,exit_code,notes`
  (`recommended_mode`/`level_path` readable from the JSONL events).
- Safety table rewritten to truth: driver = isolated (worktree + temp state root);
  L1–L4 write the **real** `~/.fa` intentionally (L4's target); trial runs appear in the
  calibration table — record run-ids so S11 can exclude them.

### S10.9.11 — harness + docs truthfulness (G-H6)
- `scripts/verify_complexity_aware_execution.py`: add checks — K=0 first-call denial;
  Modified overflow marker + ≤30 cap under a 40-write fixture; `near_miss_evidence`
  truth table (bulk-safe silence / medium-write / high-read-at-L2 / negative);
  segment-anchored glob (`src/*` vs `src/a/b.py`); dot-prefix config match; malformed
  `risk_config` degrades to goal-only. Update the S2 registry section only if the count
  string moves.
- ADR-16 addendum: §B counters wording (telemetry, not policy); §C config resolution
  (`DEFAULT_CONFIG_PATH` only); §E caps (≤30 + Modified-15 + marker); §H kinds
  (`expansion_observed`, mirror set). Status stays `proposed`.
- PR note: regenerate the suite-claim line from the actual post-fix run; add an S10.9
  fix-list section referencing this plan.

---

## 6. Test plan (new/updated; C-class in parens)

- T-H1 (C0) ε boundary ± exact — kills M-H1
- T-H2 (C0) `near_miss_evidence` truth table + `next_level` counter-free signature — kills M-H2a
- T-H3 (C1) `expansion_observed` emission: once per tuple change; not on transitions; fires for `workflow_linear` seeds — kills M-H2b
- T-H4 (C1) mirror dual-write + renderer lines for both kinds; `expansion_observed` NOT on console — kills M-H3 (plus contract script, automatic)
- T-H5 (C0) handoff: 40 writes → ≤15 Modified + marker, ≤30 entries + marker — kills M-H4
- T-H6 (C0+C2) K=0 denied first call, runner untouched; K=2 behavior unchanged — kills M-H5
- T-H7 (C1) facts provider honors configured high prefix in Start-here — kills M-H6
- T-H8 (C0) `_prefix_matches`: dot-prefix, segment-anchored glob, boundary literal — kills M-H7
- T-H9 (C0) handoff construction raise → goal-only degrade — kills M-H8
- T-H10 (C0) R1/R2 suites updated to the new `next_level` signature (mechanical)
- T-H11 (C2) real-CLI: `fa stats --calibration` JSON unchanged in shape (regression guard for the S10.6 contract)

## 7. Mutation handoff

| Mutant | Target | Must be killed by |
|---|---|---|
| M-H1 `rate <` → `<=` | calibration.py | T-H1 (pytest, not just harness) |
| M-H2a `near_miss_evidence` → constant truthy | expansion.py | T-H2 |
| M-H2b drop delta gate (emit every boundary) | coder_loop.py | T-H3 |
| M-H3 remove either mirror emit | coder_loop.py | **T-H4** (verified: the contract script's dual-write check is heuristic — it greps for the emit's existence, not the code path — and does NOT kill an `if False:` guard; T-H4's live EventBus capture does) |
| M-H4 remove Modified cap | workflow_tool.py | T-H5 |
| M-H5 `max(0,` → `max(1,` | workflow_tool.py | T-H6 |
| M-H6 facts provider → `default_scope_risk_config()` | cli.py | T-H7 |
| M-H7 restore `lstrip("./")` / whole-path fnmatch | path_risk.py | T-H8 |
| M-H8 move `build_handoff_task` back outside try | workflow_tool.py | T-H9 |

Protocol: apply → run the named killer → confirm FAIL → restore → `git diff` byte-identical.

## 8. Constants introduced

`MODIFIED_SECTION_CAP = 15` (workflow_tool), `expansion_observed` content keys
(`turn, level, files_read, files_changed, write_tier, read_tier, verify_failed`).
No new tunables; K/ε/min_flag_runs remain the S10 knobs. All S11-seeded constants
unchanged — this slice adds no numbers for S11 to close beyond the cap above (record it
in the S11 closure list).

## 9. Risks

- **RK-H1 (literal churn):** `EventType`/`LogKind` members feed the console contract,
  WebUI help JSON, and contract scripts. Mitigation: run both contract scripts + full
  suite in the same pass; renderer tests pin the new lines.
- **RK-H2 (worktree availability):** needs git ≥ 2.5 and a clean-ish repo. Mitigation:
  loud fallback with explicit confirmation; never silent in-repo.
- **RK-H3 (signature change):** `next_level` is internal-only; mypy --strict over
  src+tests catches every call site (R1/R2/harness included).
- **RK-H4 (count-string drift):** sheet/PR-note harness counts must be regenerated from
  a real run — DoD greps the number out of the harness output and diffs it against both docs.
- **RK-H5 (event volume):** `expansion_observed` delta-gated; worst case ≤ one line per
  evidence change within ≤ 40 turns — negligible next to per-call `tool_call` rows.

## 10. Open questions (non-blocking, defaults ship)

- **Q-H1:** does `expansion_observed` carry up to 5 sample paths, or counts/tiers only?
  **Default: counts/tiers only** (payload stays small, no prose in events); revisit in S11
  if tuning needs exemplars.
- **Q-H2:** rev3 supersession banner wording on rev2. **Default:** one-line italic banner
  linking rev3, rev2 otherwise untouched (evidence retention).

## 11. Definition of Done / READY gate

Run in order; every command must match:

1. `pytest tests/test_console_encoding.py` → all pass (B1 closed)
2. `uv run pylint --disable=all --enable=E,F,R0801,R0401 scripts/` → 10.00, no E1101
3. Full `pytest` with coverage → only failures = the **two** staged doc-gate reds;
   coverage ≥ 80 floor; `check_cli_coverage_floor.py` OK
4. `uv run mypy --strict src tests` → 0 errors; ruff check+format; pyrefly 0; deptry clean
5. `uv run python scripts/verify_complexity_aware_execution.py` → N/N ALL GREEN (N = new
   total); the same N appears in sheet rev3 §1.1 and the PR note (grep-verified identical)
6. Contract scripts all PASS except `check_doc_links` (unchanged known-red, no **new**
   broken links introduced by this slice's docs)
7. Mutants M-H1…M-H8: all killed, byte-identical restores (`git status --porcelain` empty
   after each)
8. `bash scripts/check_shell_syntax.sh` (or shellcheck where available) green on the
   edited driver script
9. Sheet rev3 self-consistency: no bare `python ` invocations; no un-wrapped
   `PIPESTATUS`; L3 carries the clean-status pre-check; capture step present on every row
10. Commit message references this plan + both review files; PR description updated with
    the S10.9 section.

**READY:** ✅ — no blocking open questions; edit packets anchored to verified line
evidence; every gap has a contract, a test, and a mutant.

### 11.1 Execution record (2026-08-29, S10.9 implementation)

| # | Gate | Result |
|---|------|--------|
| 1 | console encoding suite | 14/14 pass (B1 closed) |
| 2 | pylint scripts (E,F,R0801,R0401) | 10.00/10, no E1101 |
| 3 | full pytest + coverage | **3642 passed, 2 failed** = the two staged doc-gate reds only; 86.14% ≥ 80; cli floor 27/27 |
| 4 | mypy --strict / ruff check+format / pyrefly / deptry | 0 errors (403 files) / clean / 0 / clean |
| 5 | harness | **151/151 ALL GREEN**; 151 grep-identical in rev3 sheet + PR note |
| 6 | contract scripts | 7/7 PASS; check_doc_links red unchanged (46 known, 0 from new docs) |
| 7 | mutants | M-H1,H2a,H2b,H4,H5,H6,H7,H8 killed on first pass; **M-H3 killed by T-H4** (contract script confirmed heuristic-only — table corrected); restores byte-identical |
| 8 | shell | check_shell_syntax.sh exit 0; `bash -n` OK on driver |
| 9 | rev3 self-consistency | no bare `python `; PIPESTATUS bash-flagged at Part 2 head; L3 clean-status pre-check present; ledger + per-row capture |
| 10 | docs | PR note S10.9 section + Apply-line 151/151; rev2 superseded banner; commit message to cite this plan + both reviews at commit time |

Deviations found during execution (both now fixed in-tree): `Path` import gap in
path_risk (mypy caught), and two exact-count pins the full suite surfaced that Phase A
had missed — `test_s5_console_mirror_kinds` 15→17 and `test_s19_stats_parsers`
LogKind 38→39 / UNPARSED 14→15, both updated with recorded TEST-EDIT reasons.

## 12. RN dispositions (review findings → where addressed)

| Finding | Disposition |
|---|---|
| B1, E1101 | S10.9.0 (patch lands) |
| F1 | S10.9.1 / CT-H1 |
| F2 | S10.9.8 |
| F3 | S10.9.2 (removal + helper) / CT-H2 |
| F4, F5 | S10.9.6 / CT-H7 |
| F6 | S10.9.3–4 / CT-H3 (kind `expansion_observed`) |
| F7 | S10.9.5 / CT-H5 |
| F8 | S10.9.5 / CT-H6 |
| F9 | **S11 watch-item** (tier-blind verify_failed; live-contour data first) — unchanged |
| F10, F11 | S10.9.5, S10.9.7 / CT-H8 |
| F12 | **S11 note** (unknown≠success sentinel) — unchanged |
| F13 | **Live-trial watch-item**; rev3 L2/L3 judge rows explicitly ask "was the one-shot advice acted on?" |
| P1–P5 | S10.9.4 (mirror), S10.9.9–10 (driver + rev3) |
| Doc-gate reds | **Stay red** (staged bait, standing order) |
