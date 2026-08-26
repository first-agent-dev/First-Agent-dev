> **Status:** archived 2026-08-25 — moved from implementation-plans per 30-day rule

# PLAN: Rushed patch foundation closure — 4-signal production fix (v2)

**Plan-ID:** `PLAN-rushed-patch-foundation-closure`
**Status:** READY
**Depth:** P1
**Size:** S
**Revision:** R02 (2026-08-25) — aligned with operator: S13 deleted intentionally (minimalism), isolation XFAIL out of scope, readiness fix = pop+set explicit pinning, doc-links fix both pr-notes
**Author:** agent
**Upstream context:**
- `knowledge/BACKLOG.md` I-34 — isolation boundary P0, XFAIL intentional — OUT OF SCOPE for this slice (confirmed)
- `knowledge/adr/ADR-13-workspace-isolation.md` (amended 2026-08-13) — workspace isolation + historical banner pattern
- `knowledge/adr/ADR-11-authoring-guardrails.md` I9 — triple oracle blocking (pyrefly/mypy/ruff)
- `tests/test_deploy_scripts.py:832-861` `test_historical_workspace_docs_have_top_level_superseded_banner` — currently expects 4 docs, but 2 were ephemeral S13 prompts deleted in f2ed2c9 file work (intentional)
- `tests/test_deploy_scripts.py:863-898` `test_workspace_stale_claims_are_confined_to_historical_evidence` — allowed_paths includes deleted S13 docs
- `scripts/check_doc_links.py` — 5 broken links in `worklogs/pr-notes/PR_NOTE_substrate_gap_closure.md`, plus `knowledge/pr-notes/` version points to `knowledge/research/` while canonical after move is `worklogs/archive/`
- `src/fa/inner_loop/runtime_limits.py:452-453` — `role: str|None` narrowing bug → pyrefly bad-index + dict.get overload
- `tests/test_iteration_cap.py:207-210` — `DenyAfter.handle` missing `@override`
- `tests/test_workspace_readiness_integration.py:68-156` — C2/C3 real Git→readiness→hooks→commit→local-push, fails when pyrefly hook fails + VIRTUAL_ENV leak

**Parent:** `worklogs/implementation-plans/PLAN-session-workspace-readiness-bootstrap.md` A38 banner task + `PLAN-cli-trace-S5-authority-correctness.md` Q19

---

## 0. PREFLIGHT LOG

**Roots checked:**
- `src/fa/inner_loop/runtime_limits.py:resolve_limits_for_role:439-458`
- `src/fa/workspace_bootstrap.py:_command_environment:232-237` + `_run_process:239-260`
- `src/fa/hygiene/hooks/pre-commit` — calls `python3 scripts/bootstrap/workspace.py ensure` + `uv run --no-sync pre-commit run`
- `tests/test_deploy_scripts.py:832-900` — banner + stale-claims confinement
- `scripts/check_doc_links.py` + `_LEGACY_SKIP`
- `tests/test_workspace_readiness_integration.py:100-135` clean_env

**Greps → findings:**
- `git log --diff-filter=D -- worklogs/S13-NEXT-SESSION-START.md` → `f2ed2c9 file work` deleted both S13 docs; `git show fa9b987:...` shows 176/181 lines of ephemeral prompt: `git clone https://...`, `git checkout 6cd60f1...`, `git apply /path/to/patch` — not long-term doc, session-start helper
- `ls worklogs/` + `ls worklogs/archive/` → S13 docs absent everywhere — intentional cleanup of `fa-s9-*.sh`, `ANALYSIS-windows-gate`, `SESSION-...-PATCH-LESSONS`, `S0-baseline`, `s11-scripts`
- `python scripts/check_doc_links.py worklogs/pr-notes/PR_NOTE_substrate_gap_closure.md` → 5 broken to `implementation-plans/substrate-*.md`; `ls worklogs/archive/ | grep substrate` → 7 files exist there
- `python scripts/check_doc_links.py --all knowledge/pr-notes/PR_NOTE_substrate_gap_closure.md` → OK (links to `../research/` which exists), but `ls knowledge/research/ | grep substrate` also has copies — duplicate canonical after move; fixing both to `archive/` is consistent
- `sed -n 452,453p runtime_limits.py` → `if role in _LIVE_ROLE_NAMES: return replace(..., get(role, ROLE_ITERATION_DEFAULTS[role]))` — `role: str|None`, pyrefly doesn't narrow via `in` on `frozenset[str]` → 2 errors
- `grep -n override tests/test_iteration_cap.py` → no import, `handle` overrides without decorator → pyrefly error
- `grep -n VIRTUAL_ENV src/fa/workspace_bootstrap.py` → no handling; `_command_environment` copies os.environ verbatim + sets GIT_TERMINAL_PROMPT, UV_LINK_MODE
- `cat tests/test_workspace_readiness_integration.py:103-110` → clean_env pops GIT_* but not VIRTUAL_ENV/CONDA/UV_*

**Gold patterns:**
- `knowledge/pr-notes/workspace-isolation.md:1-10` banner shape: `> [!WARNING] **HISTORICAL / SUPERSEDED (2026-08-13).** ... Current authority: [ADR-13] and [AP-004]` — template for historical docs, but S13 prompts don't need it because they are not workspace-isolation docs
- `src/fa/workspace_bootstrap.py:239 _run_process(cwd=Path, ...)` — already has workspace Path as cwd, so we can pass it to env builder to set `UV_PROJECT_ENVIRONMENT`
- `tests/test_iteration_cap.py:20 from typing import Any` → add `override` from same module (Python 3.13)

**Conflicts/invariants:**
- Minimalism-first (project goal): don't preserve every ephemeral prompt forever. File work f2ed2c9 cleaned 8 temporary files + moved 15+ plans to archive — S13 deletion aligns with that.
- Substrate formality: type narrowing must be explicit, override explicit, env hermeticity explicit
- Failure-observable: doc-links checker, pyrefly, deploy-suite must be green; kill-checks must fail when fix reverted

**As-is liveness:**
- historical banner: L0 FileNotFound for 2/4 expected, but intentional deletion → should be L3 after test fix to expect 2
- doc-links: L1 broken → target L3
- pyrefly: L1 3 errors → target L3
- readiness integration: L2 reachable but blocked by pyrefly + env leak → target L3
- isolation XFAIL: out of scope, stays XFAIL P0 backlog

**Unresolved → resolved via operator answers (R02):**
- Q1 historical intent → KEEP DELETED, update tests to expect 2 docs only (operator selected)
- Q2 readiness fix → POP+SET explicit pinning, change _command_environment signature to take workspace Path and set UV_PROJECT_ENVIRONMENT (operator selected)
- Q3 doc-links scope → fix BOTH pr-notes copies to archive/ (operator selected)

---

## 1. EXECUTIVE INTENT

**IDEA:** Rushed patch `f2ed2c9 file work` was intentional cleanup: removed ephemeral session-start prompts (S13-NEXT, S13-SESSION-PROMPT) + 6 temp scripts + moved 15+ old plans to archive/. Tests still expected 4 historical docs, so deploy-suite failed FileNotFound. Separately, 5 doc links pointed to moved files, pyrefly had 2 narrowing errors + 1 missing @override blocking commit hook, and readiness integration leaked VIRTUAL_ENV causing uv to use wrong venv. Need production-grade closure that respects minimalism (keep deleted, fix tests), fixes links to canonical archive/, narrows Optional correctly, adds @override, and makes readiness env hermetic with explicit UV_PROJECT_ENVIRONMENT pinning.

**PROJECT MEANING:** In `doc-maintenance` + `authoring-guardrails` + `session-workspace-readiness` subsystems, this slice is reference for: when to banner vs delete historical docs (banner only for docs that contain stale transport/session claims, not every prompt), how to maintain links after moves, how to satisfy pyrefly's strict Optional narrowing, and how to make uv-based readiness hermetic.

**GOALS (G#):**
- G1 — Historical docs contract green with minimalism: `test_historical_workspace_docs_have_top_level_superseded_banner` passes expecting 2 docs (workspace-isolation.md ×2) with banner, not 4. `test_workspace_stale_claims_are_confined_to_historical_evidence` allowed_paths no longer includes deleted S13 docs.
- G2 — Doc-link contract green: both `worklogs/pr-notes/PR_NOTE_substrate_gap_closure.md` and `knowledge/pr-notes/PR_NOTE_substrate_gap_closure.md` have 0 broken links, pointing to canonical `worklogs/archive/` (or `../../worklogs/archive/` from knowledge)
- G3 — Type-safety triple oracle green: `pyrefly check` 0 errors for `runtime_limits.py:453` and `test_iteration_cap.py:210`
- G4 — Readiness integration C2/C3 green: `test_clean_candidate_real_readiness_commit_and_local_publication` passes with explicit env pinning (`UV_PROJECT_ENVIRONMENT=workspace/.venv` + pop VIRTUAL_ENV etc.), commit through real hooks succeeds

**NON-GOALS:**
- NG1 — No isolation boundary fix (BACKLOG I-34 P0, XFAIL out of scope, confirmed)
- NG2 — No new artifact types, flags, dependencies
- NG3 — No restoring S13 docs (keep deleted per operator intent)
- NG4 — No changing canonical archive location (archive/ is canonical after file work)

**INTENT:** Code should ensure ephemeral prompts can be deleted without breaking deploy-suite (tests reflect minimalism), doc links stay valid after moves (both pr-notes copies point to archive/), Optional types are narrowed explicitly before dict access, overrides are explicit, and readiness env is hermetic and explicitly pinned to workspace/.venv so parent VIRTUAL_ENV never leaks.

**MECHANISM SKETCH:**
- S13 deletion rationale: ephemeral prompts contain `git clone https://...` + `git checkout <sha>` + `git apply /path/to/patch` — one-time operator instructions, not long-term docs. Minimalism says delete, not banner. Fix tests to expect 2 docs (workspace-isolation.md ×2) which actually contain stale transport claims like `git clone --local`, `hardlink`, `container lifecycle corresponds to one session` and thus need banner.
- Doc-links: `worklogs/archive/` contains 7 substrate files after move. Change 5 links in worklogs/pr-notes from `../../worklogs/implementation-plans/` → `../archive/`. Change knowledge/pr-notes from `../research/` → `../../worklogs/archive/` for consistency (research/ still has copies but archive/ is canonical after file work).
- Type narrowing: `if role is not None and role in _LIVE_ROLE_NAMES: role_str: str = role; return replace(..., get(role_str, ROLE_ITERATION_DEFAULTS[role_str]))`
- Override: `from typing import override` + `@override` on `DenyAfter.handle`
- Readiness env: change `_command_environment(workspace: Path | None = None)` to pop `VIRTUAL_ENV`, `VIRTUAL_ENV_PROMPT`, `CONDA_PREFIX`, `UV_PROJECT_ENVIRONMENT`, `UV_PYTHON`, `PYTHONHOME` and if workspace provided, set `UV_PROJECT_ENVIRONMENT=str(workspace/.venv)`. Update `_run_process` to call `_command_environment(cwd)` where cwd is workspace Path. Update integration test clean_env to pop same keys.

**PROOF SKETCH:** Deploy-suite observes 2 files with banner; kill-check deletes banner or re-adds deleted S13 to expected list → fails. Link checker observes resolution; kill-check reverts to old path → fails. Pyrefly observes narrowing + override; kill-check reverts → fails. Readiness integration observes `ready_repaired` + commit rc 0 + push head match; kill-check leaks VIRTUAL_ENV → fails.

**SIZE:** S (<100 LOC: 2 test edits + 2 doc edits + 2 src/tests type fixes + 2 env hardening edits)

---

## 2. CURRENT STATE → TARGET STATE

### AS-IS

| Dim | Finding |
|---|---|
| Entry points | `test_deploy_scripts.py:832` banner expects 4, `test_deploy_scripts.py:877` allowed_paths includes S13, `check_doc_links.py`, `runtime_limits.py:452`, `test_iteration_cap.py:210`, `workspace_bootstrap.py:232`, `test_workspace_readiness_integration.py:103` |
| Types | `RuntimeLimits`, `ROLE_ITERATION_DEFAULTS`, `_LIVE_ROLE_NAMES`, `ReadyState`, `GuardMiddleware` |
| Producers/consumers | Banner producer: 2 present (workspace-isolation.md ×2) with banner, 2 deleted (S13) → consumer expects 4 → FileNotFound. Link producer broken. Type producer not narrowed. Readiness producer leaks env. |
| State | FS docs, `.fa/ready-state.json`, `.venv`, PRE_COMMIT_HOME |
| Tests today | banner FAIL FileNotFound, doc-links FAIL 5 broken, pyrefly FAIL 3 errors, readiness SKIP locally but FAIL in CI due to hook, isolation XFAIL out of scope |
| Liveness | banner L0 (but intentional), doc-links L1, pyrefly L1, readiness L2 |

### TO-BE

- GAP ledger:

| GAP# | Gap | Owner |
|---|---|---|
| GAP1 | S13 docs deleted intentionally but tests expect 4 → update tests to expect 2, remove S13 from allowed_paths | S1, T1 |
| GAP2 | 5 broken links in worklogs/pr-notes + knowledge/pr-notes points to research/ while canonical is archive/ | S2, T2 |
| GAP3 | role Optional not narrowed → pyrefly bad-index + bad-arg | S3, T3 |
| GAP4 | DenyAfter.handle missing @override | S4, T3 |
| GAP5 | _command_environment leaks VIRTUAL_ENV, no explicit UV_PROJECT_ENVIRONMENT pin | S5, T4 |
| GAP6 | integration test clean_env leaks same vars | S6, T4 |

- State transitions:
  - historical docs: AS-IS 2 present + 2 deleted but expected 4 → TO-BE 2 present expected, S13 removed from allowed_paths, minimalism preserved
  - doc links: 5 broken + inconsistent canonical → 0 broken, both pr-notes point to archive/
  - type safety: 3 errors → 0 errors, role narrowed, override present
  - readiness env: leak → hermetic + explicit pinning, .venv/bin/python exists, commit rc 0

- Target liveness: banner L3 (with 2 docs), doc-links L3, pyrefly L3, readiness L3

---

## 3. NON-GOALS & MINIMAL-MECHANISM CHECK

- NG1 isolation out of scope — no SandboxHook changes
- NG2-4 above

**Minimalism checks:**
- Historical: updating test to expect 2 docs is smaller than restoring 357 lines of ephemeral prompts + banners. Banner is only needed for docs that contain stale transport claims (`git clone --local`, `hardlink`, `container lifecycle...`). S13 prompts don't contain those; they contain `git clone https://` + `git checkout <sha>` — not stale claims, just old instructions. Deleting is minimalism-first.
- Doc-links: fixing to archive/ is 1-line per link, vs moving files back (larger) or adding sunset notes. Fixing both pr-notes to same canonical (archive/) prevents future drift.
- Type narrowing: `role is not None and role in ...` + `role_str: str = role` is 2 lines, vs `cast` (hides intent) or restructuring types. Pyrefly understands `is not None`.
- Override: import + decorator minimal, required by pyrefly explicit override rule.
- Env: pop+set explicit pinning is production-grade: pop removes leak, set makes intent explicit. Changing signature to take workspace Path is minimal API change (optional arg, backward compatible) and lets `_run_process` pass cwd which it already has. Alternative pop-only is smaller but implicit; explicit pinning is more robust and operator chose it.

**New component gate:** no new service, dep, tool, LLM, cache, queue, worker, subagent, topology.

---

## 4. CONTRACTS

### CT1 — Historical docs banner contract (updated to 2 docs, minimalism)

**Type:** invariant + data
**File:** `tests/test_deploy_scripts.py:832-861` + `knowledge/pr-notes/workspace-isolation.md`, `worklogs/pr-notes/workspace-isolation.md`
**Shape:** Exactly 2 files must exist, each top 12 lines contain `HISTORICAL / SUPERSEDED` + `ADR-13` + `AP-004`. S13 docs are intentionally deleted and NOT in expected list.
**Authority:** test is source of truth; ADR-13 + AP-004 canonical; minimalism-first says ephemeral prompts don't need preservation
**Mechanism:** `Path.read_text().splitlines()[:12]` check; banner `> [!WARNING] **HISTORICAL / SUPERSEDED (2026-08-13).** ... Current authority: [ADR-13] and [AP-004]`
**Failure:** FileNotFound or missing substring → assertion fails
**Kill-check:** remove banner from workspace-isolation.md or add S13 back to expected list without restoring file → T1 fails

### CT2 — Doc-link resolution contract

**Type:** invariant
**File:** `scripts/check_doc_links.py` + both pr-notes
**PRE:** markdown link `](path)`
**POST:** relative file link resolves to existing file
**Mechanism:** `_iter_links` regex + `Path.resolve()` existence
**Failure:** prints Broken + exit 1, pre-commit hook fails
**Kill-check:** revert one link to old `implementation-plans/` → T2 fails

### CT3 — Runtime limits role narrowing

**Type:** function contract
**Symbol:** `src/fa/inner_loop/runtime_limits.py:resolve_limits_for_role`
**Signature:** `def resolve_limits_for_role(loaded: RuntimeLimitsLoadResult, role: str | None) -> RuntimeLimits`
**PRE:** `role: str|None`, `_LIVE_ROLE_NAMES: frozenset[str]`
**POST:** if `role is not None and role in _LIVE_ROLE_NAMES`: `role_str: str = role; return replace(..., get(role_str, ROLE_ITERATION_DEFAULTS[role_str]))` else return global
**Mechanism:** explicit `is not None` guard + local `str` var
**Kill-check:** revert to `if role in _LIVE_ROLE_NAMES:` → pyrefly bad-index → T3 fails

### CT4 — Override explicitness

**Type:** function contract
**Symbol:** `tests/test_iteration_cap.py:DenyAfter.handle`
**Signature:** `@override def handle(...) -> Decision`
**Mechanism:** `from typing import override` + decorator
**Kill-check:** remove decorator → pyrefly missing-override → T3 fails

### CT5 — Workspace readiness env hermeticity + explicit pinning (production-grade)

**Type:** function contract
**Symbol:** `src/fa/workspace_bootstrap.py:_command_environment(workspace: Path | None = None)` + `_run_process`
**Signature:** `def _command_environment(workspace: Path | None = None) -> dict[str,str]`
**PRE:** `os.environ` may contain `VIRTUAL_ENV`, `CONDA_PREFIX`, `UV_PROJECT_ENVIRONMENT`, etc., `workspace` may be Path to managed clone
**POST:** returns env copy WITHOUT `VIRTUAL_ENV`, `VIRTUAL_ENV_PROMPT`, `CONDA_PREFIX`, `UV_PROJECT_ENVIRONMENT`, `UV_PYTHON`, `PYTHONHOME`, with `GIT_TERMINAL_PROMPT=0`, `UV_LINK_MODE=copy`, and if workspace is not None, `UV_PROJECT_ENVIRONMENT=str(workspace/.venv)` set explicitly
**Side effects:** none, pure
**Mechanism:** pop leak keys, then if workspace: `environment["UV_PROJECT_ENVIRONMENT"] = str((workspace / ".venv").resolve())`
**Failure:** if leak not popped or not pinned, uv uses external venv, `.venv/bin/python` missing → `locked_check_failed` → readiness degraded
**Kill-check:** re-add VIRTUAL_ENV or remove UV_PROJECT_ENVIRONMENT set → T4 fails when parent VIRTUAL_ENV set

### CT6 — Readiness integration C2/C3 signal

**Type:** signal contract
**Signal:** `ready_repaired` + git commit through real hooks + local push
**Producer:** `ensure_workspace_ready` writes `.fa/ready-state.json`, `.venv/bin/python`, installs hooks; CLI prints `{"status":"ready","reason_code":"ready_repaired"}`
**Consumer:** `test_clean_candidate...` asserts status ready, reason_code ready_repaired, .venv exists, hooks executable, commit rc 0, push head matches
**Dual-write:** marker + sentinel + log
**Kill-check:** revert env fix or pyrefly fixes → commit rc !=0 → T4 fails

---

## 5. PATH & FLAG MATRIX

### 5.1 Path inventory

| P# | Trigger | File:line | Flag | Covering S# | T# |
|---|---|---|---|---|---|
| P1 | Historical docs: workspace-isolation.md ×2 present with banner | `knowledge/pr-notes/workspace-isolation.md:1`, `worklogs/pr-notes/workspace-isolation.md:1` | any | S1 | T1 |
| P2 | Historical docs: S13 deleted intentionally, tests updated to not expect them | `tests/test_deploy_scripts.py:832` expected tuple | any | S1 | T1 |
| P3 | Stale claims confinement: allowed_paths no longer includes S13 | `tests/test_deploy_scripts.py:877` allowed_paths set | any | S1 | T1 |
| P4 | Doc link broken worklogs/pr-notes:19 | `worklogs/pr-notes/PR_NOTE_substrate_gap_closure.md:19` | any | S2 | T2 |
| P5 | Doc links broken worklogs/pr-notes:23,25,26,27 (×4) | same:23,25,26,27 | any | S2 | T2 |
| P6 | Doc links knowledge/pr-notes points to research/ but canonical is archive/ | `knowledge/pr-notes/PR_NOTE_substrate_gap_closure.md:19` etc | any | S2 | T2 |
| P7 | resolve_limits_for_role(None) → global | `runtime_limits.py:439` | role=None | S3 | T3 |
| P8 | resolve_limits_for_role("coder") with config → role_iterations | `runtime_limits.py:452` | role=coder + config | S3 | T3 |
| P9 | resolve_limits_for_role("coder") without config → 99 | same | role=coder no config | S3 | T3 |
| P10 | resolve_limits_for_role("researcher") stub → global | same | role=researcher | S3 | T3 |
| P11 | DenyAfter.handle missing @override | `test_iteration_cap.py:210` | any | S4 | T3 |
| P12 | _command_environment with VIRTUAL_ENV=/tmp/fake → pop + set UV_PROJECT_ENVIRONMENT | `workspace_bootstrap.py:232` | VIRTUAL_ENV set | S5 | T4 |
| P13 | _command_environment with workspace=None → pop only, no set | same | no workspace arg | S5 | T4 |
| P14 | Integration clean_env with VIRTUAL_ENV set → pop | `test_workspace_readiness_integration.py:103` | VIRTUAL_ENV set | S6 | T4 |

### 5.2 Flag/provider matrix

| ID | Flags/env | Proves | T# |
|---|---|---|---|
| A | primary (no VIRTUAL_ENV) | happy path: banner 2 docs, links, pyrefly green | T1,T2,T3 |
| B | VIRTUAL_ENV=/tmp/fake + UV_PROJECT_ENVIRONMENT=/other set in parent | env hermetic + explicit pin: pop + set → still creates workspace/.venv | T4 |
| C | defaults no config file | runtime_limits anchored defaults | T3 |
| D | role=coder + config max_iterations_coder:2 | per-role cap via config seam | T3 |
| P-x | provider N/A | — | N/A |

---

## 6. STEP-BY-STEP IMPLEMENTATION

### Step S1: Keep S13 deleted, update deploy-suite tests to expect 2 docs only

**Traces-to:** G1, GAP1, CT1
**Depends-on:** none
**Parallelizable-with:** S2,S3,S4
**Target liveness:** L0→L3 (with 2 docs)

**Edit:**
- path: `tests/test_deploy_scripts.py` symbol: `test_historical_workspace_docs_have_top_level_superseded_banner` line 835-840 change: expected tuple from 4 to 2
- path: same file symbol: `test_workspace_stale_claims_are_confined_to_historical_evidence` line 877-890 allowed_paths remove S13 entries

**Degree of freedom closed:** Deletion vs preservation — minimalism says ephemeral prompts don't need banner. Only docs containing stale transport claims (`git clone --local`, `hardlink`, `container lifecycle...`) need banner and confinement.

**Deterministic mechanism:**
- In `test_historical_workspace_docs_have_top_level_superseded_banner`, change:

  historical_docs = (
      _ROOT / "knowledge" / "pr-notes" / "workspace-isolation.md",
      _ROOT / "worklogs" / "pr-notes" / "workspace-isolation.md",
  )
  ```
  Remove S13 entries.
- In `test_workspace_stale_claims_are_confined_to_historical_evidence`, `allowed_paths` set currently has 6 entries including S13 + PLAN-bootstrap. Remove S13 entries, keep only workspace-isolation.md ×2 + PLAN-bootstrap (which is allowed because it documents banner task):

  allowed_paths = {
      Path("knowledge/pr-notes/workspace-isolation.md"),
      Path("worklogs/pr-notes/workspace-isolation.md"),
      Path("worklogs/implementation-plans/PLAN-session-workspace-readiness-bootstrap.md"),
  }
  ```
- Verify S13 files still absent: `ls worklogs/S13*` should fail

**Do:**
1. Open `tests/test_deploy_scripts.py:832-845` and `877-892`
2. Edit expected tuple to 2 entries
3. Edit allowed_paths to 3 entries (2 isolation + 1 bootstrap plan)
4. Run `pytest tests/test_deploy_scripts.py::test_historical_workspace_docs_have_top_level_superseded_banner -xvs` → PASS
5. Run `pytest tests/test_deploy_scripts.py::test_workspace_stale_claims_are_confined_to_historical_evidence -xvs` → PASS
6. Run `ls worklogs/S13-NEXT-SESSION-START.md` → should fail (confirm deleted)

**Do-not:**
- Do not restore S13 files
- Do not add new historical docs
- Do not change banner content of existing isolation docs (they already have correct banner)

**Exit criteria:**
- [ ] `pytest tests/test_deploy_scripts.py::test_historical_workspace_docs_have_top_level_superseded_banner -xvs` PASS
- [ ] `pytest tests/test_deploy_scripts.py::test_workspace_stale_claims_are_confined_to_historical_evidence -xvs` PASS
- [ ] `ls worklogs/S13*` → no such file (deleted kept)
- [ ] `head -n 12 knowledge/pr-notes/workspace-isolation.md` contains HISTORICAL/SUPERSEDED + ADR-13 + AP-004 (existing)

**Kill-check:** re-add S13 to expected tuple without restoring file → FileNotFound → T1 fails; remove banner from isolation doc → T1 fails

---

### Step S2: Fix 5+ broken doc links to archive/ in both pr-notes copies

**Traces-to:** G2, GAP2, CT2
**Depends-on:** none
**Parallelizable-with:** S1,S3,S4
**Target liveness:** L1→L3

**Edit:**
- path: `worklogs/pr-notes/PR_NOTE_substrate_gap_closure.md` symbol: lines 19,23,25,26,27 change: `../../worklogs/implementation-plans/` → `../archive/`
- path: `knowledge/pr-notes/PR_NOTE_substrate_gap_closure.md` symbol: lines 19,23,25,26,27 etc change: `../research/` → `../../worklogs/archive/` for substrate files (since canonical after move is archive/)

**Degree of freedom closed:** Link target after move — doc-maintenance skill requires fixing links. Canonical is `worklogs/archive/` after f2ed2c9.

**Mechanism:**
- `worklogs/archive/` contains: `substrate-decision-freeze-2026-07-15.md`, `substrate-gap-closure-workplan-round2-2026-07-15.md`, `substrate-slice0-slice1-implementation-plan-2026-07-15.md`, `substrate-slice2-patch-design-2026-07-15.md`, `substrate-slice3-patch-design-2026-07-15.md`, `substrate-slice4-patch-design-2026-07-15.md`, `substrate-slice5-6-7-closure-2026-07-15.md`, `substrate-state-assessment-2026-07-15-round3.md`, `substrate-slice9-patch-design-2026-07-15.md`, `substrate-slice9-closure-2026-07-15.md`, etc.
- For `worklogs/pr-notes/` (depth 1 from worklogs): `../archive/<file>` resolves to `worklogs/archive/<file>`
- For `knowledge/pr-notes/` (depth 1 from knowledge): `../../worklogs/archive/<file>` resolves to `worklogs/archive/<file>`

**Do:**
1. `sed -n '19,30p' worklogs/pr-notes/PR_NOTE_substrate_gap_closure.md`
2. Replace 5 links:
   - `substrate-gap-closure-workplan-round2-2026-07-15.md` → `../archive/substrate-gap-closure-workplan-round2-2026-07-15.md`
   - `substrate-slice0-slice1-implementation-plan-2026-07-15.md` → `../archive/substrate-slice0-slice1-implementation-plan-2026-07-15.md`
   - `substrate-slice2-patch-design-2026-07-15.md` → `../archive/substrate-slice2-patch-design-2026-07-15.md`
   - `substrate-slice3-patch-design-2026-07-15.md` → `../archive/substrate-slice3-patch-design-2026-07-15.md`
   - `substrate-slice4-patch-design-2026-07-15.md` → `../archive/substrate-slice4-patch-design-2026-07-15.md`
3. For `knowledge/pr-notes/PR_NOTE_substrate_gap_closure.md`, check its current links: they are `../research/...` — change those 5-7 substrate links to `../../worklogs/archive/...` (keep other research links that are not substrate? The file has many: decision-freeze, workplan-round2, slice0/1, slice1 closure, slice2, slice3, slice4, slice5-7, state-assessment, slice9 patch, slice9 closure, plus authoring workplans. For consistency, fix all substrate-related to archive/, keep authoring workplan v2 which is in research/ and still exists)
   - Simplest: fix the 5 that were broken in worklogs version, plus same 5 in knowledge version if they exist there too. Actually knowledge version's links to research/ still resolve (since research/ has copies), so they are not broken per checker with --all, but for canonical consistency, point to archive/.
4. Run `python scripts/check_doc_links.py worklogs/pr-notes/PR_NOTE_substrate_gap_closure.md knowledge/pr-notes/PR_NOTE_substrate_gap_closure.md` → OK
5. Run `python scripts/check_doc_links.py --all` → OK (or only LEGACY_SKIP remaining)

**Do-not:**
- Do not change non-substrate links (authoring-hardening-workplan-v2, ADR-11, skill links) — they still valid
- Do not add new files

**Exit criteria:**
- [ ] `python scripts/check_doc_links.py worklogs/pr-notes/PR_NOTE_substrate_gap_closure.md knowledge/pr-notes/PR_NOTE_substrate_gap_closure.md` → OK 2 files
- [ ] `python scripts/check_doc_links.py` whole-repo → 0 broken (excluding LEGACY_SKIP)
- [ ] No `implementation-plans/substrate-` remains in worklogs/pr-notes file

**Kill-check:** revert one link to old path → checker exit 1 → T2 fails

---

### Step S3: Fix runtime_limits.py Optional narrowing (production-grade)

**Traces-to:** G3, GAP3, CT3
**Depends-on:** none
**Parallelizable-with:** S1,S2,S4
**Target liveness:** L1→L3

**Edit:**
- path: `src/fa/inner_loop/runtime_limits.py` symbol: `resolve_limits_for_role` 452-453

**Degree of freedom closed:** Optional not narrowed before dict access.

**Mechanism:**
```python
# before:
if role in _LIVE_ROLE_NAMES:
    return replace(
        loaded.limits,
        max_iterations=loaded.role_iterations.get(role, ROLE_ITERATION_DEFAULTS[role]),
    )

# after (production-grade):
if role is not None and role in _LIVE_ROLE_NAMES:
    role_str: str = role
    return replace(
        loaded.limits,
        max_iterations=loaded.role_iterations.get(role_str, ROLE_ITERATION_DEFAULTS[role_str]),
    )
return loaded.limits
```

**Do:**
1. Edit file
2. `python -m py_compile src/fa/inner_loop/runtime_limits.py`
3. If pyrefly available: `pyrefly check src/fa/inner_loop/runtime_limits.py` → 0 errors at 453
4. `pytest tests/test_inner_loop_runtime_limits.py -xvs -k role` → PASS

**Do-not:**
- Change stub roles logic
- Change ROLE_ITERATION_DEFAULTS values

**Exit criteria:**
- [ ] pyrefly 0 errors for this file
- [ ] unit tests pass
- [ ] `role_str: str = role` present

**Kill-check:** revert guard → pyrefly fails

---

### Step S4: Add @override to DenyAfter.handle

**Traces-to:** G3, GAP4, CT4
**Depends-on:** none
**Parallelizable-with:** S1,S2,S3

**Edit:**
- path: `tests/test_iteration_cap.py` symbol: import + DenyAfter

**Mechanism:**
```python
from typing import Any, override
...
class DenyAfter(GuardMiddleware):
    attaches_to = (LifecyclePoint.AFTER_TOOL_EXEC,)

    @override
    def handle(...) -> Decision:
```

**Do:**
1. Edit
2. `pyrefly check tests/test_iteration_cap.py` → 0 errors
3. `pytest tests/test_iteration_cap.py -xvs` → PASS

**Exit criteria:**
- [ ] @override present
- [ ] pyrefly 0 errors
- [ ] tests pass

**Kill-check:** remove decorator → pyrefly fails

---

### Step S5: Harden _command_environment to pop+set explicit pinning (production-grade)

**Traces-to:** G4, GAP5, CT5, CT6
**Depends-on:** S3,S4 (pyrefly green needed for commit)
**Parallelizable-with:** S6 (but S5 should land first)

**Edit:**
- path: `src/fa/workspace_bootstrap.py` symbol: `_command_environment` + `_run_process`

**Degree of freedom closed:** Parent VIRTUAL_ENV leaks, uv uses wrong venv. Production-grade fix = pop leak + explicitly set UV_PROJECT_ENVIRONMENT to workspace/.venv (operator chose pop+set).

**Mechanism:**
- Change signature: `def _command_environment(workspace: Path | None = None) -> dict[str,str]`
- Pop: `VIRTUAL_ENV`, `VIRTUAL_ENV_PROMPT`, `CONDA_PREFIX`, `UV_PROJECT_ENVIRONMENT`, `UV_PYTHON`, `PYTHONHOME`
- Set: `GIT_TERMINAL_PROMPT=0`, `UV_LINK_MODE=copy`
- If workspace is not None: `environment["UV_PROJECT_ENVIRONMENT"] = str((workspace / ".venv").resolve())`
- Update `_run_process` to call `_command_environment(cwd)` where cwd is workspace Path (it already has cwd param). Change line 264 from `env=_command_environment(),` to `env=_command_environment(cwd),`
- Also update `_uv_executable` and other call sites if they call _command_environment directly (only _run_process does)

**Do:**
1. Edit `_command_environment` signature and body as above
2. Edit `_run_process` to pass `cwd` to `_command_environment`
3. Verify: `grep -rn "_command_environment" src/` → only 2 places (def + call in _run_process)
4. Unit repro:
```python
import os
from pathlib import Path
from fa.workspace_bootstrap import _command_environment

os.environ["VIRTUAL_ENV"] = "/tmp/fake"
env = _command_environment(Path("/tmp/ws"))
assert "VIRTUAL_ENV" not in env
assert env["UV_PROJECT_ENVIRONMENT"] == str((Path("/tmp/ws") / ".venv").resolve())
env2 = _command_environment(None)
assert "VIRTUAL_ENV" not in env2
assert "UV_PROJECT_ENVIRONMENT" not in env2
print("ok")
```
5. `pytest tests/test_workspace_bootstrap.py -xvs` → PASS (if exists, else manual check)

**Do-not:**
- Do not set UV_PROJECT_ENVIRONMENT to hardcoded path, must be workspace/.venv
- Do not forget to pop PYTHONHOME etc.
- Do not change timeout logic

**Exit criteria:**
- [ ] `_command_environment(Path("/tmp/ws"))` returns env without VIRTUAL_ENV and with UV_PROJECT_ENVIRONMENT = /tmp/ws/.venv
- [ ] `_command_environment(None)` returns env without VIRTUAL_ENV and without UV_PROJECT_ENVIRONMENT (or with it unset, not set to fake)
- [ ] `pytest tests/test_workspace_bootstrap.py -xvs` PASS

**Kill-check:** re-add VIRTUAL_ENV or remove set → unit repro fails → T4 fails

---

### Step S6: Harden integration test clean_env to pop same leak vars

**Traces-to:** G4, GAP6, CT5, CT6
**Depends-on:** S5
**Parallelizable-with:** none (after S5)

**Edit:**
- path: `tests/test_workspace_readiness_integration.py` symbol: clean_env block 103-110

**Mechanism:** After popping GIT_* vars, also pop `VIRTUAL_ENV`, `VIRTUAL_ENV_PROMPT`, `CONDA_PREFIX`, `UV_PROJECT_ENVIRONMENT`, `UV_PYTHON`, `PYTHONHOME`

**Do:**
1. Open file 100-115
2. Add loop popping those 6 keys from clean_env
3. Run `pytest tests/test_workspace_readiness_integration.py -k test_clean_candidate -xvs` in env with uv (will SKIP if uv missing, but should PASS in CI)
4. Also test with `VIRTUAL_ENV=/tmp/fake pytest ...` → should still PASS (hermetic)

**Exit criteria:**
- [ ] clean_env has no VIRTUAL_ENV even when parent has it
- [ ] integration test PASS when uv available, or SKIP with unit repro PASS when uv missing
- [ ] git commit inside target workspace succeeds (rc 0)

**Kill-check:** remove pop → with VIRTUAL_ENV set, commit fails or readiness degraded → T4 fails

---

## 7. VERIFICATION PLAN

### CT1 — Historical banner (2 docs, minimalism)

- **Class:** C0 deploy-suite
- **Oracle:** file exists + top12 contains HISTORICAL/SUPERSEDED + ADR-13 + AP-004
- **Test:** `pytest tests/test_deploy_scripts.py::test_historical_workspace_docs_have_top_level_superseded_banner -xvs` + `test_workspace_stale_claims_are_confined_to_historical_evidence`
- **Kill-check:** add S13 back to expected tuple without file → FileNotFound → T1 fails; remove banner from isolation doc → T1 fails
- **Paths:** P1,P2,P3

### CT2 — Doc-links

- **Class:** C0 static gate
- **Oracle:** `check_doc_links.py` exit 0
- **Test:** `python scripts/check_doc_links.py worklogs/pr-notes/PR_NOTE_substrate_gap_closure.md knowledge/pr-notes/PR_NOTE_substrate_gap_closure.md` + whole-repo
- **Kill-check:** revert link → exit 1
- **Paths:** P4,P5,P6

### CT3 — Type safety

- **Class:** C0p type gate + C1 unit
- **Oracle:** pyrefly exit 0, mypy exit 0
- **Tests:** `pyrefly check src/fa/inner_loop/runtime_limits.py tests/test_iteration_cap.py`, `pytest tests/test_inner_loop_runtime_limits.py tests/test_iteration_cap.py -xvs`
- **Kill-check:** revert narrowing or remove @override → pyrefly fails
- **Paths:** P7-P11

### CT4 — Readiness env hermetic + explicit pinning

- **Class:** C0 unit + C1 readiness + C2/C3 integration
- **Oracle:** ReadyState ready, reason_code ready_repaired, .venv exists, hooks executable, commit rc 0, push head matches, env without VIRTUAL_ENV and with UV_PROJECT_ENVIRONMENT pinned
- **Tests:**
  - Unit repro for _command_environment pop+set
  - `tests/test_workspace_bootstrap.py`
  - `tests/test_workspace_readiness_integration.py::test_clean_candidate...` (requires uv, else SKIP but unit repro must PASS)
- **Kill-check:** leak VIRTUAL_ENV or remove pin → unit repro fails or integration commit fails
- **Paths:** P12,P13,P14

**Overall commands:**
```bash
pytest tests/test_deploy_scripts.py::test_historical_workspace_docs_have_top_level_superseded_banner -xvs
pytest tests/test_deploy_scripts.py::test_workspace_stale_claims_are_confined_to_historical_evidence -xvs
python scripts/check_doc_links.py worklogs/pr-notes/PR_NOTE_substrate_gap_closure.md knowledge/pr-notes/PR_NOTE_substrate_gap_closure.md
python scripts/check_doc_links.py
# if pyrefly installed:
pyrefly check src/fa/inner_loop/runtime_limits.py tests/test_iteration_cap.py
pytest tests/test_inner_loop_runtime_limits.py tests/test_iteration_cap.py -xvs
# env hermetic unit:
python -c "
import os
from pathlib import Path
from fa.workspace_bootstrap import _command_environment
os.environ['VIRTUAL_ENV']='/tmp/fake'
env=_command_environment(Path('/tmp/ws'))
assert 'VIRTUAL_ENV' not in env
assert 'UV_PROJECT_ENVIRONMENT' in env and env['UV_PROJECT_ENVIRONMENT'].endswith('.venv')
print('env hermetic ok')
"
# integration (requires uv):
pytest tests/test_workspace_readiness_integration.py -k test_clean_candidate -xvs
```

---

## 8. RISKS, ROLLBACK, OPEN QUESTIONS

### Risks

| RK# | Risk | Mitigation | Detection |
|---|---|---|---|
| RK1 | Updating test to expect 2 docs instead of 4 could hide future accidental deletion of isolation docs | Isolation docs still expected and checked for banner; if they get deleted, test fails FileNotFound → T1 fails | T1 |
| RK2 | Fixing knowledge/pr-notes links to archive/ makes them point outside knowledge/ (to worklogs/) — is that allowed? | Yes, relative links across repo are allowed; archive/ is canonical historical store after file work; alternative is to keep research/ copies but then duplicate canonical. Fixing both to archive/ makes single source of truth. | T2 |
| RK3 | Changing _command_environment signature to take workspace Path is API change, could break other callers | Signature has optional arg with default None, backward compatible; only internal call site is _run_process which already has cwd; grep confirms no other callers | T4 unit repro |
| RK4 | Setting UV_PROJECT_ENVIRONMENT explicitly to workspace/.venv could break if uv version doesn't support it | UV_PROJECT_ENVIRONMENT is documented uv env var (since uv 0.4+), supported; fallback is pop-only would still work; we do pop+set, so if set is ignored, pop still ensures hermeticity | T4 |
| RK5 | Integration test SKIP locally due to missing uv → failure only visible in CI | Provide unit repro that doesn't require uv; document that just check requires uv | T4 |
| RK6 | Knowledge/research/ still has substrate copies, so fixing links to archive/ leaves duplicate files | That's existing duplication after file work; archive/ is canonical for historical evidence, research/ is LEGACY_SKIP-covered but still contains copies. Future cleanup could dedup, but out of scope for this slice. | T2 |

### Rollback

- No flag, additive fixes. `git revert` restores old test expectations (4 docs) and broken links and type errors — tests will fail, observable.
- No DB migration.

### Open Questions (resolved)

| Q# | Question | Resolution | Gated S# |
|---|---|---|---|
| Q1 | Historical S13 deletion intentional? | Yes, keep deleted, update tests to 2 docs — minimalism-first (operator confirmed) | S1 |
| Q2 | Readiness fix pop vs pop+set? | Pop+set explicit pinning, change signature to take workspace Path (operator chose) | S5 |
| Q3 | Doc-links fix both copies? | Yes, fix both to archive/ canonical (operator chose) | S2 |

---

## 9. RESEARCH-NOTE DISPOSITION (updated)

| RN# | Note | Verdict | Why | Anchor |
|---|---|---|---|---|
| RN1 | Isolation XFAIL Q19 | Reject (out of scope) | BACKLOG I-34 P0, needs ADR-6 + mount namespace, confirmed out of scope per operator | NG1 |
| RN2 | Historical S13 deletion FileNotFound | Accept (keep deleted) | Verified f2ed2c9 deleted ephemeral prompts (176/181 lines of git clone/checkout/apply instructions), not long-term docs. Minimalism says delete, not banner. Fix tests to expect 2 docs (isolation.md ×2) which actually contain stale transport claims. | CT1, S1, T1 |
| RN3 | Doc-links 5 broken | Accept (fix both) | Verified 5 broken to implementation-plans/, files in archive/. Fix both pr-notes to archive/ canonical per operator choice. | CT2, S2, T2 |
| RN4 | pyrefly 3 errors runtime_limits + iteration_cap | Accept | Verified narrowing bug + missing @override. Fix via is not None guard + role_str + @override. | CT3,CT4,S3,S4,T3 |
| RN5 | Readiness integration commit fails | Accept (pop+set) | Root cause = RN4 + VIRTUAL_ENV leak. Production-grade fix = pop leak + set UV_PROJECT_ENVIRONMENT=workspace/.venv explicitly, change signature to take workspace. Operator chose pop+set. | CT5,CT6,S5,S6,T4 |

---

## 10. DEFINITION OF DONE (falsifiable)

**STATE:**
- [ ] Historical: 2 files exist with banner, S13 absent, tests expect 2
- [ ] Doc-links: 0 broken in both pr-notes, both point to archive/
- [ ] Type: 0 pyrefly errors for runtime_limits:453 and iteration_cap:210
- [ ] Readiness: env hermetic + pinned, .venv exists, commit rc 0, push head matches

**ARTIFACTS:**
- [ ] `tests/test_deploy_scripts.py` updated to expect 2 docs, allowed_paths updated to remove S13
- [ ] `worklogs/pr-notes/PR_NOTE_substrate_gap_closure.md` 5 links → `../archive/`
- [ ] `knowledge/pr-notes/PR_NOTE_substrate_gap_closure.md` substrate links → `../../worklogs/archive/`
- [ ] `src/fa/inner_loop/runtime_limits.py` narrowed
- [ ] `tests/test_iteration_cap.py` @override added
- [ ] `src/fa/workspace_bootstrap.py` _command_environment(workspace) pop+set
- [ ] `tests/test_workspace_readiness_integration.py` clean_env pop

**CONTRACTS:**
- [ ] CT1 VERIFIED: banner tests PASS with 2 docs
- [ ] CT2 VERIFIED: check_doc_links PASS for both files + whole-repo
- [ ] CT3,CT4 VERIFIED: pyrefly PASS + unit tests PASS
- [ ] CT5,CT6 VERIFIED: env unit repro PASS + integration PASS (or SKIP with unit repro PASS)

**NEGATIVE PROOF:**
- [ ] Re-add S13 to expected without file → T1 fails
- [ ] Revert one link → T2 fails
- [ ] Revert narrowing → pyrefly fails
- [ ] Remove @override → pyrefly fails
- [ ] Leak VIRTUAL_ENV or remove pin → T4 fails

**ANTI-THEATER:**
- [ ] No new deps/flags/services
- [ ] Every file:line verified via preflight
- [ ] Minimalism respected (keep deleted)

---

## 11. GATES

### Anti-theater checklist

- [ ] Every symbol verified or NEW — YES
- [ ] Every G# maps to CT#, S#, T# — YES: G1→CT1→S1→T1, G2→CT2→S2→T2, G3→CT3/CT4→S3/S4→T3, G4→CT5/CT6→S5/S6→T4
- [ ] Every CT# has producer+consumer or explicit deferral — YES
- [ ] Path inventory covers all triggers, every P# has S# and T# — YES P1-P14
- [ ] Flag matrix has verification or N/A — YES
- [ ] Kill-checks producer-side — YES
- [ ] DoD falsifiable — YES
- [ ] No vacuous Done — YES
- [ ] Research notes dispositioned — YES
- [ ] Non-goals explicit, minimal-mechanism checked — YES
- [ ] No symbol without verification — YES
- [ ] Pyramid A only — YES
- [ ] Dual-write planned — YES CT6

### READY gate

- [ ] Preflight log recorded — YES
- [ ] Executive intent G#, non-goals, mechanism, proof — YES
- [ ] Current→Target GAP ledger — YES GAP1-6
- [ ] Contracts CT1-CT6 with mechanism + kill-check — YES
- [ ] Path & flag matrix — YES P1-P14
- [ ] Steps S1-S6 with Traces-to, Depends-on, Edit, Do, Do-not, Exit, Kill-check — YES
- [ ] Verification plan with class, oracle, kill-check, live-path — YES
- [ ] Risks, rollback, open questions resolved — YES
- [ ] DoD falsifiable — YES
- [ ] No blocking questions — YES (all resolved via operator answers)

**Status = READY**

---

## 12. EXECUTOR HANDOFF

- Follow S# order; S1-S4 parallelizable; S5 depends on S3,S4; S6 depends on S5
- After each step run Exit criteria; never mark complete on partial
- If producer missing, implement, don't weaken test
- No scope expansion without plan revision
- Final message: DoD checklist with PASS/FAIL + actual command output

---

## 13. APPENDIX — Production-grade rationale for chosen options

### Why keep S13 deleted (vs restore+banner)?

- **Content analysis:** S13 docs are `git clone https://...`, `git checkout <sha>`, `git apply /path/to/patch` — one-time operator instructions for a specific slice, not architectural docs. They don't contain stale transport claims like `git clone --local`, `hardlink`, `container lifecycle corresponds to one session` which are the actual stale claims that C0 S8/T15 guards against.
- **Minimalism-first (project goal):** Don't preserve every prompt forever. File work f2ed2c9 deleted 8 temp files + moved 15+ plans to archive/ — S13 deletion aligns.
- **Banner contract scope:** Historical banner is for docs that contain obsolete workspace-isolation mechanisms (read-only bind + clone vs worktree etc.). S13 prompts are not about isolation mechanism, they are about multi-provider conformance. So they shouldn't be in historical banner list.
- **Production practice:** When cleaning ephemeral files, update tests to reflect new minimal set, don't restore deleted files to satisfy outdated test. Test is the one that needs fixing.

### Why pop+set explicit pinning (vs pop-only) for readiness?

- **Pop-only:** Removes leak, lets uv default to `.venv` in cwd. Works, minimal.
- **Pop+set:** Removes leak AND explicitly sets `UV_PROJECT_ENVIRONMENT=workspace/.venv`. More robust: even if uv changes default behavior, or if some other env var like `UV_PROJECT_ENVIRONMENT` was set externally to wrong path, we override it to correct path. Explicit is better than implicit (production-grade).
- **Implementation cost:** Change signature to `def _command_environment(workspace: Path | None = None)` — optional arg, backward compatible. `_run_process` already has `cwd: Path` which is workspace, so pass it. Small change, big robustness gain.
- **Operator chose pop+set** — aligns with substrate formality (deterministic, explicit).

### Why fix both pr-notes copies?

- `worklogs/pr-notes/` is the active PR note (5 broken links, deterministic failure).
- `knowledge/pr-notes/` is a mirror that still points to `knowledge/research/` which exists, so checker with default LEGACY_SKIP passes, but with `--all` it would also be checked. After file work, canonical historical store is `worklogs/archive/`, not `knowledge/research/` (which is legacy). Fixing both to same canonical prevents future drift and makes `check_doc_links.py --all` green.

**End of PLAN R02**
