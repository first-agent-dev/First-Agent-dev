> **Status:** archived 2026-08-25 — moved from implementation-plans per 30-day rule

# PLAN: S10c — deploy-gate contracts, artifact posture, and request-cost fixes

Plan-ID: `PLAN-cli-trace-S10c-contract-and-posture-fixes`
Status: **COMPLETE (2026-08-01)** — I-36, I-39, I-40 closed; routing-check exits 2 on bad config;
`fa workflow` exits 1 on non-DONE verdict; session artifacts 0600/0700; inline
tool block reduced 29.6% (10,619 → 7,471 bytes). Gate green: 2415 passed, mypy
322, pyrefly 0, pylint 10.00/10, cli-coverage-floor 27/27, mutation 15/15.
Execution record in §11.
Depth: **P2** — two operator-visible **exit-code** contract changes plus a
file-permission change on the artifact path. Not P1: an exit code is an API,
and `scripts/fa-clean-rebuild.sh` and any operator `&&` chain are its
consumers.
Revision: **v1 (self-reviewed)** · Changed-since-draft: a review pass against
the source found **three defects in this plan**, all now fixed:
**(A)** S10c.2's obvious implementation — "reuse the `_terminal_state` local" —
would have **shipped a crash**: that name is bound *inside* the best-effort
`try/except Exception` guarding the telemetry export (`cli.py:1879`, `:1908`),
so an early export failure leaves it unbound and the new `return` raises
`UnboundLocalError` from the one place the code is written never to fail. The
read-back is now hoisted above the `try` (RK9, T10b).
**(B)** CT4's oracle was unreachable — the composer's extras are a dict
*literal*, not an exported constant, so the test could only scrape source; the
step now promotes them to `COMPOSER_EXTRA_BODY_KEYS` and asserts the constant
matches what the function emits (RK10).
**(C)** the I-36 fix shape carried over from the BACKLOG **does not compile**
(`Path.open()` rejects `opener=`), and silently leaves pre-existing `0644`
files untouched — both measured, now RN3 and Q56.
· **v2 (operator-answered + code-review pass)** — Q55/Q56/Q57 answered, and a
review that *ran* the code found **three scope errors in v1**, all now fixed:
**(D)** CT3 named 2 writers; a real `fa run` leaves **four** world-readable
artifacts — `events.jsonl`, `llm_bodies.jsonl`, **`session.db`** and
**`global_history.db`** (measured, §1.3a). `session.db` stores full event
`content` (`session_db.py:185`), i.e. the same prose the bodies file holds, so
omitting it would have shipped a half-fix of a security item.
**(E)** I-40's YAML half is **not** 2 sites but **five commands**
(`routing-check`, `run`, `selfcheck`, `probe`, `egress-proxy`) — proven by
executing each (§1.1a). Patching `except` tuples one at a time would have left
three leaking. The fix moves to the **single** `yaml.safe_load` at
`config.py:238`; prototyped, all five then exit 2.
**(F)** the Q56 comprehensive pass has two hazards a naive walker hits:
`os.chmod` **follows symlinks** (measured: chmod'ing a link changed its
target's mode) and `follow_symlinks=False` raises `NotImplementedError` on
Linux, so an explicit `is_symlink()` skip is mandatory; and chmod-ing
directories to `0600` makes them untraversable.
· Upstream: parent
[`cli-trace-substrate-rebaseline-2026-07-25.md`](./cli-trace-substrate-rebaseline-2026-07-25.md)
§Step S11. **Predecessors:** S10a (coverage), S10b (decomposition) — both
COMPLETE. **Successor: S11** (controlled deployment).

> **Why this slice exists, in one paragraph.** S11 deploys. Three of the items
> below are *in the deployment path itself*: a routing gate that passes while
> validating nothing (I-40), a workflow exit code that lets `&&` chains proceed
> on rejected code (Q35b), and world-readable prompt/response captures (I-36).
> Fixing them after S11 means fixing them in production. The operator's
> instruction was explicit: *"close as many as possible now so we won't have to
> come back here much in the future."*

---

## 1. Preflight (§2) — every symbol verified by reading the repo

Measured 2026-08-01 on `31de095` / `a66a3c4`. Nothing below is inferred.

### 1.1 I-40 — the deploy gate that validates nothing

| Fact | Evidence |
|---|---|
| `_cmd_routing_check` | `cli.py:2563` |
| exception tuple omits `yaml.YAMLError` | `cli.py:2580` — `except (ConfigurationError, EvalFamilyConflictError, OSError)` |
| the "no roles" success branch | returns **0** with `WARNING: no roles declared` |
| **consumer that makes it load-bearing** | `scripts/fa-clean-rebuild.sh:471` — `if uv run ... fa routing-check --config "${ROUTING_MODELS_FILE}"; then log_info "Routing lint: OK."` |
| today's behaviour is pinned | `tests/test_s10a_cli_coverage.py:194` `test_s10a_routing_check_missing_config_reports_no_roles` |

A typo in `ROUTING_MODELS_FILE` logs **"Routing lint: OK"** and proceeds to
build. The command's own docstring (`cli.py:2564-2573`) calls itself a gate
that "fails in well under a second, before a Docker image build" — which is
exactly what does not happen.

### 1.1a I-40's YAML half is CLI-wide — **five** commands, not two (v2)

Executed, not inferred (`/tmp/yaml_probe.py`, a malformed `roles: [oops`):

```text
routing-check   *** RAW yaml.YAMLError ESCAPED *** (ParserError)
selfcheck       *** RAW yaml.YAMLError ESCAPED *** (ParserError)
probe           *** RAW yaml.YAMLError ESCAPED *** (ParserError)
```

`_cmd_run` is the fourth (pinned by `test_s10b_parity_unparseable_yaml_crashes`)
and `_cmd_egress_proxy` (`cli.py:3374`) the fifth — it loads the same config at
**container start**, which is squarely in S11's path.

The four `except (ConfigurationError, EvalFamilyConflictError, OSError)` sites
are `_resolve_run_models:1994`, `_cmd_routing_check:2580`,
`_cmd_selfcheck:2760`, `_cmd_probe:2828`.

**The elegant fix is one line, not five.** Every one of those callers already
catches `ConfigurationError`, and `load_models_config` **already raises
`ConfigurationError`** two lines below the parse for a bad root type
(`config.py:240`). So the missing case belongs with its siblings, at the single
`yaml.safe_load` (`config.py:238`) — 19 call sites across the repo inherit the
fix, including any future one.

> **Prototyped during this review, then reverted.** Wrapping `safe_load` in a
> `try/except yaml.YAMLError -> ConfigurationError` made all three probed
> commands return **exit 2** with a structured message. No test asserts
> loader-level `YAMLError`, so nothing else depends on today's leak.

### 1.2 Q35b — the workflow exit code

| Fact | Evidence |
|---|---|
| `_cmd_workflow` | `cli.py:1728`; single terminal `return result_code` at `cli.py:1913` |
| every mode returns 0 on completion | `_run_linear` / `_run_repair` / `_run_adaptive` all `return 0` |
| verdict → terminal status map | `_EVAL_VERDICT_TO_TERMINAL_STATUS` (`cli.py:1100`): `PASS→DONE`, `REPAIR_REQUIRED→REPAIR_REQUIRED`, `REPLAN_REQUIRED→REPLAN_REQUIRED`, `BLOCKED→FAILED` |
| **the seam Q35b needs already exists** | S8.7 added `_read_back_terminal_state(...)` and `_WORKFLOW_STATUS_TO_STOP_REASON` (`cli.py:1122`), already called at `cli.py:1878` to derive `stop_reason` from the persisted `FlowState` rather than from `result_code` |
| blast radius, **measured not estimated** | **10** tests script a non-PASS verdict and assert exit 0 — `test_cli_ergonomics.py:294,338,360,380,396,500,523,543` and `test_s8_workflow_controller.py:236,284` |

**This is the decisive preflight finding.** S8 deferred Q35 saying *"S8.7 is a
prerequisite for ever answering Q35 cleanly"*. S8.7 shipped. The semantic
authority (`FlowState.status`) is already read back at the exact point where
the exit code is returned, so Q35b is now a **three-line change at one site**,
not a re-plumbing.

### 1.3 I-36 — artifact permissions

| Fact | Evidence |
|---|---|
| bodies writer | `providers/debug_bodies.py:169` — `self._path.open("a", encoding="utf-8")` |
| events writer | `inner_loop/state.py:286` — `self.path.open("a", encoding="utf-8")` |
| both on the `fa run` chain | `wrap_transport_for_debug_bodies` at `cli.py:2383`; `EventLog(...)` at `cli.py:921` |
| existing 0600 precedent | `session/manager.py:133` — `os.chmod(temp_path, 0o600)` for the manifest |
| measured modes | `0644` bodies/events vs `0600` manifest |

> **Two corrections to the BACKLOG entry, both measured (see §7 RN3).** The
> entry prescribes `Path.open(..., opener=...)`. **That raises
> `TypeError: Path.open() got an unexpected keyword argument 'opener'`** on
> Python 3.13.14 — verified. The builtin `open()` accepts `opener`;
> `pathlib.Path.open()` does not. An executor following the entry verbatim
> hits a wall.
>
> Second, and not mentioned in the entry at all: an `opener` sets the mode
> **only at creation**. Verified — appending to a pre-existing `0644` file
> leaves it `0644`. Deployed runs already have `0644` artifacts on disk, so
> create-mode alone does not close the exposure. **This is Q56.**

### 1.3a Measured: a real run leaves **four** world-readable artifacts (v2)

The BACKLOG entry names bodies and events. A real `_cmd_run` under
`umask 0022` with `FA_DEBUG_LLM_BODIES=1` actually produces:

```text
FILE  0o644  global_history.db                       <-- WORLD/GROUP READABLE
DIR   0o755  session-log/
DIR   0o755  session-log/modeprobe/
FILE  0o644  session-log/modeprobe/events.jsonl      <-- WORLD/GROUP READABLE
FILE  0o644  session-log/modeprobe/llm_bodies.jsonl  <-- WORLD/GROUP READABLE
DIR   0o755  sessions/<sid>/
FILE  0o600  sessions/<sid>/manifest.json            (already correct)
FILE  0o644  sessions/<sid>/session.db               <-- WORLD/GROUP READABLE
```

**`session.db` is the omission that matters.** It stores full event `content`
as TEXT (`session_db.py:185`, written at `:470`) — the same prompt/response
prose whose sensitivity is the entire justification for `llm_bodies.jsonl`
being opt-in. Fixing the two JSONL files while leaving the database
world-readable would close the *documented* hole and leave the larger one open.

**One fix point covers both databases.** Both go through
`create_sqlite_connection` (`_sqlite_common.py:27`; used by `session_db.py:24`).
Measured mechanism:

```text
sqlite3.connect on a fresh path      -> 0o644
pre-create with os.open(..., 0o600)  -> 0o600
  WAL sidecar -wal                   -> 0o600   (inherits)
  WAL sidecar -shm                   -> 0o600   (inherits)
```

A pre-create inside the shared factory therefore fixes `session.db`,
`global_history.db` **and** their WAL sidecars at once — no per-callsite work,
no new component.

**Also measured and deliberately OUT of scope:** `flow_state.json`,
`eval_report.json` and `attempt_history.json` go through
`tempfile.NamedTemporaryFile` / `.tmp` + `os.replace`
(`workflow_artifacts.py:499`, `attempt_history.py:168`), and
`NamedTemporaryFile` already creates at `0600`. Listed so an executor does not
"helpfully" widen the diff — **re-measure before changing any of them.**

### 1.4 I-39 — `prompt_cache_retention` dropped for Mistral

| Fact | Evidence |
|---|---|
| composer emits it unconditionally | `prompt_composer.py:188` — `extra_body = {"prompt_cache_key": ..., "prompt_cache_retention": "1h"}` |
| Mistral's recognised set omits it | `mistral.py:77` `MISTRAL_RECOGNIZED_PROVIDER_PARAMS_KEYS` — 7 keys, not including it |
| the drop is pinned without justification | `tests/test_mistral_provider.py:625` `test_unrecognized_extras_filtered_out` |
| **the lint already has the registry to reuse** | `routing_lint.py:99` `KNOWN_PROVIDER_PARAMS_KEYS` maps provider → the adapter's own constant, *"never duplicates the key list itself"* |

`routing_lint` check 3 validates `provider_params` **from `models.yaml`**;
composer-injected `extras` never pass through it. A key the composer invents
and an adapter silently drops is invisible to every existing check.

### 1.5 I-37 (partial) — `indent=2` on the inline tool block

| Fact | Evidence |
|---|---|
| site | `prompt_composer.py:98` — `json.dumps(tool_defs, indent=2)` |
| **measured saving** | 15 baseline tools: `indent=2` = **10,619 bytes**, compact = **7,471** → **3,148 bytes (29.6%) saved on every request** |

Measured by calling `render_tool_specs(build_baseline_registry(...).specs())`
directly, not estimated from the BACKLOG's 38% figure.

---

## 2. GAP ledger (§4)

| GAP# | Verified current | Target | Owner |
|---|---|---|---|
| **GAP1** | `routing-check` on a **missing** path exits **0**; deploy gate logs OK | exit **2**, structured message | S10c.1 |
| **GAP2** | unparseable YAML escapes as a raw `yaml.YAMLError` traceback from **five** commands — `routing-check`, `run`, `selfcheck`, `probe`, `egress-proxy` (§1.1a, executed) | `ConfigurationError` at the single parse site; all five exit **2** | S10c.1 |
| **GAP3** | `fa workflow` exits **0** on BLOCKED/REPAIR_REQUIRED/REPLAN_REQUIRED | non-zero on non-`DONE` terminal status | S10c.2 |
| **GAP4** | **four** artifacts created `0644` — `events.jsonl`, `llm_bodies.jsonl`, `session.db`, `global_history.db` — while the manifest is `0600`; run dirs `0755` (§1.3a, measured) | `0600` files / `0700` dirs at creation, no window | S10c.3 |
| **GAP5** | pre-existing `0644` artifacts stay `0644` after a create-mode fix | **Q56: comprehensive tightening pass**, symlink-safe | S10c.3 |
| **GAP6** | composer emits `prompt_cache_retention`; Mistral silently drops it | emit-then-drop eliminated **and** made impossible to reintroduce silently | S10c.4 |
| **GAP7** | inline tool JSON pretty-printed at `indent=2` | compact separators; 3,148 bytes/request saved | S10c.5 |

---

## 3. Contracts (§6)

### CT1 — a gate that cannot validate must fail

- **AUTHORITY:** `_cmd_routing_check`'s own docstring — a pre-build gate.
- **Contract:** exit **0** means *"the config was read and is clean"*. A config
  that could not be read is exit **2**. An empty-but-present config stays
  **0** — that is a legitimately clean state and the distinction is the point.
- **DETERMINISTIC MECHANISM:** two independent parts —
  (a) `Path.is_file()` before the load in `_cmd_routing_check` (absence);
  (b) `yaml.YAMLError → ConfigurationError` at the **single** parse site
  `config.py:238` (unparseability), which every caller already handles.
- **SCOPE NOTE (v2):** (b) is deliberately *not* four `except`-tuple edits.
  Five commands leak today (§1.1a); patching tuples one at a time fixes the
  ones an author remembers and leaves the rest — the exact drift this
  workstream keeps finding. The parse site is the one place the fact is known.
- **FAILURE SURFACE:** `ERROR: config not found: <path>` for (a); the existing
  `models config error: <exc>` prose for (b).
- **KILL-CHECK:** delete the existence check → T1 fails. Remove the
  `except yaml.YAMLError` → T2 **and** T2b/T2c (selfcheck, probe) fail.

### CT2 — the exit code reports the verdict, not merely that the tool ran

- **AUTHORITY:** the persisted terminal `FlowState.status` — already the
  semantic authority for `stop_reason` since S8.7 (`cli.py:1878`).
- **Contract:** `_cmd_workflow` returns **0** iff the terminal status is
  `DONE`; **1** for any other terminal status; **2** stays reserved for usage
  and configuration errors (`cli.py:1753-1811`, unchanged).
- **DETERMINISTIC MECHANISM:** one derivation from `_read_back_terminal_state`,
  the *same* call that already derives `stop_reason`. Two contracts, one
  source of truth — they cannot drift.
- **FAILURE SURFACE:** unchanged prose from `_print_terminal_summary`
  (`cli.py:1395`); only the integer changes.
- **KILL-CHECK:** force the derivation to `0` → the BLOCKED exit-code test
  fails while every artifact test stays green.

### CT3 — sensitive artifacts are private at creation

- **AUTHORITY:** ADR-12 (secret isolation) and `session/manager.py:133`, which
  already writes the manifest `0600`.
- **Contract:** every artifact the run writes under `~/.fa` is created mode
  `0600`; every directory it creates there is `0700`. No window exists between
  creation and the mode being correct. **Enumerated, not "every file":**
  `events.jsonl`, `llm_bodies.jsonl`, `session.db` (+ `-wal`/`-shm`),
  `global_history.db` (+ sidecars), and the `session-log/<run_id>` /
  `sessions/<sid>` directories (§1.3a).
- **DETERMINISTIC MECHANISM — two, because there are two kinds of writer:**
  (a) **JSONL append** — an `opener` passed to the **builtin** `open()` (§1.3);
  `pathlib.Path.open()` rejects `opener=` (measured `TypeError`).
  (b) **SQLite** — pre-create the file with `os.open(..., 0o600)` inside
  `create_sqlite_connection` (`_sqlite_common.py:27`) *before* `sqlite3.connect`.
  Measured: the DB and its WAL `-wal`/`-shm` sidecars all land `0600`.
  Both set the mode in the `os.open` syscall, so neither has a window.
- **RETROACTIVE (Q56):** a comprehensive tightening pass over the existing tree
  — see S10c.3 for the symlink hazard that makes the naive version unsafe.
- **FAILURE SURFACE:** n/a — a mode is asserted, not reported.
- **KILL-CHECK:** remove the `opener=` → T11/T12 fail. Remove the SQLite
  pre-create → T11b/T11c fail. Neither kill-check can substitute for the other,
  which is why they are separate tests.

**Security contract (explicit, per skill §6).** This slice *tightens* a
boundary. `llm_bodies.jsonl` carries raw prompt and response prose;
`SecretRedactor` masks known key **values** and cannot mask prose. Threat model:
a second local user, a shared CI runner, or a `docker cp`/volume snapshot
carrying the directory to a host with other readers. Not exploitable on the
current single-user container — which is why this is P2 and not P1 — but it is
a posture defect in the one subsystem whose entire reason for existing is
"this data is sensitive, so it is opt-in".

### CT4 — no key is emitted that its destination silently drops

- **AUTHORITY:** `routing_lint.py:99` `KNOWN_PROVIDER_PARAMS_KEYS` — the
  existing provider→recognised-keys registry, which imports each adapter's own
  constant rather than restating it.
- **Contract:** every key the composer injects into `extra_body` is either
  (a) recognised by the destination adapter, or (b) listed in an explicit
  **`_KNOWN_UNRECOGNISED`** allow-list with a reason. No third state — a key
  that is neither is a contract violation.
- **DETERMINISTIC MECHANISM:** a **C1 static contract test** comparing the
  composer's exported key set against the same registry the routing lint uses.
  Not a runtime check — the set is static, so the cheapest correct mechanism is
  a test (minimalism-first §1.2 Q4: prefer a deterministic Python check with no
  per-call cost).
- **WHY THE ALLOW-LIST (Q55, v2):** Mistral is a temporary test provider, so
  `prompt_cache_retention` stays unrecognised **by decision**. Without an
  explicit allow-list the test would either fail on a known-and-accepted state
  (a red gate people learn to ignore) or have to be weakened to a warning
  (no gate at all). An allow-list keeps it binary: the pair is *asserted* to be
  the only exception, so a **second** silent drop still fails.
- **KILL-CHECK:** add a fictional key to the composer → the test fails naming
  key and adapter. **Second kill-check:** delete the
  `("mistral", "prompt_cache_retention")` allow-list entry → the test fails,
  proving the entry is load-bearing and not decoration.

### CT5 — request composition is byte-efficient without semantic change

- **Contract:** the inline tool block carries identical JSON *semantics*;
  only whitespace changes. `json.loads(compact) == json.loads(pretty)`.
- **KILL-CHECK:** revert to `indent=2` → the byte-budget test fails.

---

## 4. Paths (§7, path sensitivity)

| P# | Path | Covered by |
|---|---|---|
| P1 | `routing-check` — config **missing** | S10c.1 / T1 |
| P2 | `routing-check` — config present, **unparseable YAML** | S10c.1 / T2 |
| P2b | `selfcheck` — unparseable YAML (**leaks today**, §1.1a) | S10c.1 / T2b |
| P2c | `probe` — unparseable YAML (**leaks today**) | S10c.1 / T2c |
| P2d | `run` — unparseable YAML (pinned by an S10b parity cell that **inverts**) | S10c.1 / T2d |
| P2e | `egress-proxy` — unparseable YAML at **container start** (S11 path) | S10c.1 / T2e |
| P3 | `routing-check` — config present, **empty roles** (must stay 0) | S10c.1 / T3 |
| P4 | `routing-check` — config present, valid, clean (0) / findings (1) | S10c.1 / T4 (regression) |
| P5 | `workflow` — terminal `DONE` → 0 | S10c.2 / T5 |
| P6 | `workflow` — terminal `FAILED` (BLOCKED verdict) → 1 | S10c.2 / T6 |
| P7 | `workflow` — terminal `REPAIR_REQUIRED` (budget exhausted) → 1 | S10c.2 / T7 |
| P8 | `workflow` — terminal `REPLAN_REQUIRED` → 1 | S10c.2 / T8 |
| P9 | `workflow` — usage/config error → 2 (**unchanged**) | S10c.2 / T9 |
| P10 | `workflow` — terminal state **unreadable** (fallback) | S10c.2 / T10 |
| P11 | `llm_bodies.jsonl` created by a real run | S10c.3 / T11 |
| P11b | `session.db` (+ `-wal`/`-shm`) created by a real run | S10c.3 / T11b |
| P11c | `global_history.db` created by the export | S10c.3 / T11c |
| P12 | `events.jsonl` created by a real run | S10c.3 / T12 |
| P13 | run directory + `sessions/<sid>` directory modes | S10c.3 / T13 |
| P14 | pre-existing `0644` artifact — **comprehensive pass** (Q56) | S10c.3 / T14 |
| P14b | tree containing a **symlink** — must not chmod its target | S10c.3 / T14b |
| P15 | composer extras vs **mistral** adapter | S10c.4 / T15 |
| P16 | composer extras vs **openai_compat** (passthrough, no fixed set) | S10c.4 / T15 |
| P17 | inline tool block byte budget | S10c.5 / T16 |

**P10 is the path an executor would skip.** `_read_back_terminal_state` returns
`None` on a missing/corrupt/identity-mismatched artifact (`cli.py:1383-1392`).
The exit code must have a defined answer there, and it must not be "0 because
we could not tell".

---

## 5. Steps (§8)

> **Per-step protocol.** Before editing: state source-verified behaviour, the
> GAP/CT IDs, the exact files allowed to change; stop if a blocking question is
> unresolved. Each edit: idea / intent / current→target / mechanism / best
> practice / failure behaviour / DoD + negative proof / test class /
> kill-check / degree-of-freedom closed. After: targeted tests, static checks
> on changed files, inspect `git diff`, report **actual command output**. Never
> mark a step complete from "no exception".

### Step S10c.0 — Pin today's behaviour before changing it

Traces-to: GAP1–GAP3, CT1, CT2. Depends-on: none.
**Files: none (verification only).**

Do:

1. Run `tests/test_s10a_cli_coverage.py::test_s10a_routing_check_missing_config_reports_no_roles`
   and record it **green** — it asserts today's exit 0.
2. Run the 10 workflow tests from §1.2 and record them green.
3. Record `_cmd_workflow`'s exit code for a scripted BLOCKED run, measured.

Exit criteria:

- [ ] the pre-change behaviour of every contract this slice inverts is recorded
      with actual output in the execution record.

**Why this is a step and not a preamble.** Both S10c.1 and S10c.2 *invert*
tests that currently pass. Without a recorded before-state, "the test changed"
is indistinguishable from "the test was wrong all along".

---

### Step S10c.1 — `routing-check` fails when it cannot validate (GAP1, GAP2 / CT1)

Traces-to: GAP1, GAP2, CT1. Depends-on: S10c.0. Parallelizable-with: S10c.3–.5.
Target liveness: L2→L3 (the gate becomes load-bearing).

Edit:

- path: `src/fa/providers/config.py` symbol: `load_models_config` (`:238`)
  change: wrap `yaml.safe_load` so `yaml.YAMLError` becomes `ConfigurationError`
- path: `src/fa/cli.py` symbol: `_cmd_routing_check` change: stat the config
  path before loading; return 2 with `ERROR: config not found: <path>`
- path: `tests/test_s10a_cli_coverage.py` symbol:
  `test_s10a_routing_check_missing_config_reports_no_roles` change: **invert**
  to assert exit 2 and rename to `..._missing_config_is_an_error`
- path: `tests/test_s10b_cli_parity.py` symbol:
  `test_s10b_parity_unparseable_yaml_crashes` change: **invert** to assert
  exit 2 and rename to `..._unparseable_yaml_is_a_config_error` (**Q57**)

Do:

1. **Fix the parse site, not the call sites.** Wrap `yaml.safe_load`
   (`config.py:238`) in `try/except yaml.YAMLError` and re-raise as
   `ConfigurationError(...) from exc`. Keep the message actionable: name the
   file and include the parser's own text, which carries line/column.
   `yaml` is already imported there (`config.py:90`) and `ConfigurationError`
   is already raised two lines below for a bad root type — the new case joins
   its siblings.
2. Insert the existence check in `_cmd_routing_check` immediately after
   `config_path` is resolved and **before** `load_models_config_from_path`.
3. Invert the two pinned tests. Each docstring must state that S10c.1 inverted
   it and why — an inverted test with no explanation is indistinguishable from
   a test someone weakened to get green.
4. Add T2b/T2c/T2e so the other three commands are pinned at exit 2 *by their
   own tests*, not by inheritance from the loader test.

> **Why one line beats four (v2 review).** v1 said "add `yaml.YAMLError` to the
> tuple at `:2580`" and forbade touching the others. Executing the code showed
> **five** commands leak (§1.1a), so that shape fixes one and leaves four —
> and `_cmd_egress_proxy` is on S11's container-start path. There are 19
> `load_models_config*` call sites; any future one inherits the fix
> automatically only if it lives at the parse site. Prototyped and reverted
> during review: all probed commands returned exit 2.

Do-not:

- do not make an **empty-but-present** config an error — P3 stays exit 0. The
  bug is "absent read as empty", not "empty is wrong";
- do not also add `yaml.YAMLError` to the four `except` tuples. After step 1 it
  is unreachable there, and ruff/coverage will not flag a dead exception class
  — it would be silent dead code that implies the loader is untrustworthy;
- do not change `load_models_config_from_path`'s **missing-file** behaviour.
  Verified at `config.py:329-331`: `except FileNotFoundError: return
  ModelsConfig(roles={})`, a *documented* policy (`:323-326`, "caller decides
  if absence is fatal"). It is a genuinely separate concern from a parse
  failure, which is why GAP1 is fixed in the command and GAP2 in the loader.
  Changing the loader here would alter all 19 call sites — including
  `_cmd_probe`'s "no roles found" message (`cli.py:2833`), which S10a pinned.

Exit criteria:

- [ ] `grep -n "is_file()" src/fa/cli.py` shows the check inside `_cmd_routing_check`
- [ ] `fa routing-check --config /does/not/exist` → exit **2**, message names the path
- [ ] malformed YAML → exit **2** from **all five**: `routing-check`, `run`,
      `selfcheck`, `probe`, `egress-proxy` (re-run `/tmp/yaml_probe.py`-style
      checks; assert per-command, not once)
- [ ] the `ConfigurationError` message contains the parser's line/column text
- [ ] an empty-but-present config → exit **0** (unchanged)
- [ ] a valid config with a near-miss URL → exit **1** (unchanged)
- [ ] both inverted tests carry a docstring naming S10c.1

Kill-check: remove the `is_file()` guard → T1 fails. Remove the
`except yaml.YAMLError` → T2, T2b, T2c, T2d, T2e all fail (one cause, five
observable failures — that is the point of fixing it at the source).

---

### Step S10c.2 — `fa workflow` exit code reports the verdict (GAP3 / CT2)

Traces-to: GAP3, CT2. Depends-on: S10c.0. **Not** parallelizable with S10c.1
(both edit `cli.py`; sequence to keep diffs reviewable).
Target liveness: L2→L3.

Edit:

- path: `src/fa/cli.py` symbol: `_cmd_workflow` change: at the single terminal
  `return result_code` (`:1913`), return non-zero when the already-read-back
  terminal status is not `DONE`

Do:

1. **Hoist the read-back out of the export `try` block.** `_terminal_state` is
   currently assigned at `cli.py:1879`, *inside* the best-effort
   `try: ... except Exception` that wraps the `global_history` export
   (`:1908`, `# noqa: BLE001 — best-effort, never crash workflow`).
   Read it **before** that `try`, into a local both consumers use.
2. Derive: `result_code` if non-zero (usage/config errors keep 2), else `0` if
   the terminal status is `DONE`, else `1`.
3. Fallback (P10): when the terminal state is `None`, keep `result_code`. An
   unreadable artifact must not silently become a failure *or* a success — it
   preserves the pipeline's own answer, and the existing `logger.warning` at
   `:1385/:1391` already records why.
4. Update the 10 tests in §1.2 to assert the new code, each with a one-line
   docstring note naming Q35b.
5. Update `knowledge/ci-guardrails-reference.md` and the `fa workflow` help
   text if either documents the exit code.

> **Why step 1 is mandatory, not stylistic — v1-review finding.** The obvious
> implementation ("reuse the `_terminal_state` local") is **wrong** and would
> ship a crash. That name is bound inside a `try` whose `except Exception`
> exists specifically so a telemetry failure can never break a workflow. If the
> export raises *before* line 1879 — e.g. `_EventLog(...)` construction at
> `:1864`, or `export_session_to_global_history` failing to import — the
> handler swallows it and execution reaches `return`, where `_terminal_state`
> is **unbound**. `UnboundLocalError` would then escape from the one place the
> code took pains to make unfailable, converting a best-effort export problem
> into a hard workflow crash.
>
> Hoisting the read-back above the `try` fixes it structurally: the exit-code
> contract must not depend on whether a *telemetry* export succeeded. The
> export keeps using the same local, so the "one read, two contracts" property
> is preserved — which was the real goal.

Do-not:

- do not change exit **2** for usage/config errors — that is a different
  contract and `cli.py:1753-1811` stays untouched;
- do not change `stop_reason`, `FlowState`, or any artifact — S8.7 already
  made those honest, and CT1 of S10b (behaviour invariance) applies to them;
- do not "fix" `_run_linear`/`_run_repair`/`_run_adaptive` to return non-zero.
  The pipeline **did** run to completion; the *verdict* is the thing being
  reported. Changing those returns would conflate two meanings again.

Example (illustrative sketch, real names):

```python
# cli.py — BEFORE the best-effort export try-block (~:1860), not inside it:
terminal_state = _read_back_terminal_state(artifact_paths.flow_state, run_id)

try:
    ...  # global_history export, unchanged,
    ...  # now consuming `terminal_state`
except Exception as exc:  # noqa: BLE001 — best-effort, never crash workflow
    ...

# at the single terminal return (~:1913)
if result_code != 0:
    return result_code  # usage / config error: unchanged
if terminal_state is None:
    return result_code  # P10: artifact unreadable
return 0 if terminal_state.status == "DONE" else 1
```

Exit criteria:

- [ ] BLOCKED verdict → exit **1**; `flow_state.json` still `FAILED`;
      `global_history.stop_reason` still `workflow_failed`
- [ ] PASS verdict → exit **0** (unchanged)
- [ ] repair-budget-exhausted → exit **1**, `REPAIR_REQUIRED` preserved
- [ ] usage error → exit **2** (unchanged)
- [ ] unreadable terminal artifact → falls back, warning logged
- [ ] `git diff src/fa/cli.py` touches exactly one return site

Kill-check: force the derivation to `return 0` → T6 fails while every artifact
assertion in `test_s8_workflow_controller.py` stays green. **That divergence is
the proof the change is confined to the exit code.**

---

### Step S10c.3 — sensitive artifacts are created private (GAP4, GAP5 / CT3)

Traces-to: GAP4, GAP5, CT3. Depends-on: none. Parallelizable-with: S10c.4/.5.
Target liveness: L2→L3.

Edit:

- path: `src/fa/paths.py` symbol: `private_opener` (**NEW**) change: shared
  `os.open(path, flags, 0o600)` opener
- path: `src/fa/paths.py` symbol: `tighten_fa_artifact_modes` (**NEW**) change:
  the Q56 retroactive pass, symlink-safe
- path: `src/fa/providers/debug_bodies.py` symbol: `DebugBodyTransport._write`
  (`:169`) change: builtin `open(self._path, "a", ..., opener=private_opener)`
- path: `src/fa/inner_loop/state.py` symbol: `EventLog.append` (`:286`)
  change: same
- path: `src/fa/inner_loop/_sqlite_common.py` symbol:
  `create_sqlite_connection` (`:27`) change: pre-create the DB file `0600`
  before `sqlite3.connect`
- path: `src/fa/session/manager.py` symbol: run-dir / session-dir creation
  change: `mkdir(mode=0o700)`

Do:

1. Add **one** `private_opener` in `fa/paths.py` — already the home of
   `fa_state_root` / `fa_session_log_root`, so no new module (component gate).
2. Switch both JSONL writers to the **builtin** `open()`. `Path.open()` does
   **not** accept `opener` (§1.3, measured `TypeError`).
3. **SQLite (v2 addition).** In `create_sqlite_connection`, before
   `sqlite3.connect`: if the path does not exist, create it with
   `os.open(path, os.O_CREAT | os.O_RDWR, 0o600)` and close the fd. Measured:
   the DB **and** its `-wal`/`-shm` sidecars then land `0600`. This single site
   covers `session.db` and `global_history.db`.
4. Directory modes `0700` on the run dir and `sessions/<sid>`.
5. **Q56 — comprehensive tightening pass.** `tighten_fa_artifact_modes(root)`
   walks `~/.fa` once and tightens anything more permissive than the target.
   Call it from the `fa run` / `fa workflow` entry path, after the state root
   is known.

> **The two mechanisms are complementary, not redundant — verified.**
> `os.open(..., O_CREAT, 0o600)` applies its mode **only when it creates the
> file**: run against an existing `0644` DB it preserves content (no
> truncation — good) and leaves the mode at `0644` (measured). So create-mode
> alone never repairs a deployed tree, and the Q56 pass alone leaves a window
> on every new file. Both are required; neither test can substitute for the
> other.

> **The naive walker is unsafe — two hazards, both measured (v2 review).**
>
> 1. **`os.chmod` follows symlinks.** Verified: chmod-ing a symlink changed its
>    *target's* mode. A crafted `~/.fa/session-log/x/evil -> /etc/passwd` would
>    have the pass chmod the target. And `os.chmod(..., follow_symlinks=False)`
>    raises **`NotImplementedError`** on Linux (`os.chmod not in
>    os.supports_follow_symlinks`) — so the guard **must** be an explicit
>    `if p.is_symlink(): continue`.
> 2. **Directories need `0700`, not `0600`.** Chmod-ing a directory to `0600`
>    strips `x` and makes it untraversable — the pass would lock the agent out
>    of its own state root.
>
> Also: tighten **only**, never widen (`mode & ~0o077`, or skip when already
> restrictive), so an operator who deliberately set `0400` keeps it.

Do-not:

- do not `chmod` after *writing* new files — there is a window between create
  and chmod in which the file is world-readable, which is the whole defect.
  (The Q56 pass is different: it repairs files that already exist and whose
  window closed long ago.);
- do not add a `umask` call — process-global, affects unrelated writes,
  classic action-at-a-distance;
- do not touch `flow_state.json`, `eval_report.json`, `attempt_history.json`
  or `manifest.json`: measured already `0600` via `NamedTemporaryFile` /
  explicit chmod (§1.3a). **Re-measure before changing** — a diff there is
  scope creep, not thoroughness;
- do not walk anything outside the resolved `~/.fa` root.

Exit criteria:

- [ ] after a real run: `S_IMODE == 0o600` for `events.jsonl`,
      `llm_bodies.jsonl`, `session.db`, `global_history.db`
- [ ] `-wal` / `-shm` sidecars are `0600` when WAL is active
- [ ] `session-log/<run_id>` and `sessions/<sid>` are `0o700`
- [ ] appending to an existing file preserves content
- [ ] Q56 pass: a pre-seeded `0644` file becomes `0600`; a `0755` dir becomes
      `0700`; a **symlink is skipped and its target's mode is unchanged**
- [ ] Q56 pass does not widen an already-`0400` file
- [ ] running the pass twice is idempotent (no churn, no error)

Kill-check: drop `opener=` from a JSONL writer → T11/T12 fail. Drop the SQLite
pre-create → T11b/T11c fail. Drop the `is_symlink()` guard → T14b fails.

---

### Step S10c.4 — no emit-then-drop (GAP6 / CT4)

Traces-to: GAP6, CT4. Depends-on: none.
Target liveness: L1→L3 (the class becomes machine-checked).

Edit:

- path: `src/fa/inner_loop/prompt_composer.py` symbol:
  `to_openai_request_v2` (`:188`) change: per **Q55**
- path: `src/fa/providers/mistral.py` symbol:
  `MISTRAL_RECOGNIZED_PROVIDER_PARAMS_KEYS` change: per **Q55**
- path: `tests/test_s10c_composer_extras_contract.py` (**NEW**) change: the
  CT4 static contract test
- path: `tests/test_mistral_provider.py` symbol:
  `test_unrecognized_extras_filtered_out` change: docstring records *why* the
  key is or is not recognised, not merely that filtering happens

Do:

1. **Q55 is answered: Mistral is a temporary test provider — best-effort
   only.** Do **not** research the API or add the key to
   `MISTRAL_RECOGNIZED_PROVIDER_PARAMS_KEYS`. Stop the *silent* part of the
   drop instead: the defect worth fixing is that the composer emits a key the
   destination discards with nothing recording it.
2. Implement the minimum that removes the silence: keep emitting from the
   composer (it is correct for OpenAI-compatible routes), and let **CT4's
   static test** be the thing that documents and enforces the mismatch. Add a
   one-line note at `mistral.py:77` saying `prompt_cache_retention` is
   knowingly unrecognised and why (temporary test provider), so the next
   reader does not re-litigate it.

> **Why this is the right shape for a throwaway provider.** Adding the key
> would claim support we have not verified; removing the emit would penalise
> the OpenAI-compatible routes where it *does* work
> (`test_providers_openai_compat.py:139`). The honest middle is: the mismatch
> is recorded, machine-checked, and cannot grow silently — which is the actual
> I-39 complaint ("a key the composer invents and an adapter silently drops is
> invisible to every existing check"). CT4 must therefore treat this pair as a
> **known, asserted** exception rather than a failure.
3. **Make the composer's emitted key set enumerable.** Today the keys are a
   dict *literal* inside `to_openai_request_v2` (`prompt_composer.py:186-188`),
   so a test can only reach them by calling the function or scraping source.
   Promote them to a module-level `COMPOSER_EXTRA_BODY_KEYS: frozenset[str]`
   and build the dict from it, mirroring how each adapter owns its own
   recognised-keys constant. This is the "single source of truth lives at the
   producer" shape `routing_lint.py:89-98` already documents.

   > **Do not AST-scrape the literal.** S9 manufactured an entirely fictional
   > finding from a regex over source (`[a-z_]+` silently dropped every kind
   > containing a digit), and S10b's sweep pre-check found two patterns that no
   > longer matched after a reformat. A test that parses source to learn a fact
   > the module could simply *export* is a fragile instrument.

4. Write the CT4 test against `routing_lint.KNOWN_PROVIDER_PARAMS_KEYS`
   (`routing_lint.py:99`) — **reuse**, do not restate the key lists. The
   registry's own comment says it "never duplicates the key list itself";
   honour that.
5. The test must skip providers absent from the registry
   (`openai_compat`, `anthropic` do unrestricted passthrough — P16) and must
   assert that at least one provider **was** checked, or it passes vacuously.
6. Assert the promoted constant is actually what the function emits —
   `set(to_openai_request_v2(...)["extra_body"]) == COMPOSER_EXTRA_BODY_KEYS`.
   Without this, the constant could drift from the literal and the contract
   test would validate a fiction.

Do-not:

- do not add a runtime warning on every request — a static key set deserves a
  static check (minimalism-first §1.2 Q4: prefer the deterministic Python
  check with no per-call cost).

Exit criteria:

- [ ] the composer's emitted extras are enumerable by the test (not
      regex-scraped from source — AST or an exported constant)
- [ ] a fictional key added to the composer fails CT4 naming key + adapter
- [ ] the liveness assertion (≥1 provider actually checked) is present

Kill-check: add `"nonexistent_key"` to the composer's `extra_body` → CT4 fails.

---

### Step S10c.5 — compact the inline tool block (GAP7 / CT5)

Traces-to: GAP7, CT5. Depends-on: none.
Target liveness: L3 (already live; this changes its cost).

Edit:

- path: `src/fa/inner_loop/prompt_composer.py` symbol:
  `build_prompt_parts_v2` (`:98`) change:
  `json.dumps(tool_defs, separators=(",", ":"))`

Do:

1. Change **only** the tool block at `:98`. Lines `:101` and `:108`
   (`AlwaysSkills`, `ConditionalSkills`) are a separate measurement —
   out of scope, and named here so an executor does not "consistently" change
   all three.
2. Add T16 asserting the semantic identity `json.loads(block) == tool_defs`
   **and** a byte-budget ceiling.

Do-not:

- **do not delete the inline tool listing.** That is I-37's main body and the
  BACKLOG mandates an A/B on the eval corpus first. Its own note observes the
  `AGENTS.md` map is 48.4% of a live request vs the tool block's 21% —
  *"fixing 21% while ignoring 48% is backwards."* Out of scope, deliberately.

Exit criteria:

- [ ] `json.loads` of the compact block equals the source `tool_defs`
- [ ] measured bytes drop ≥ 2,500 for the 15-tool baseline registry
      (measured 3,148; the floor allows registry growth without flapping)
- [ ] no prompt-composition test regresses

Kill-check: revert to `indent=2` → T16's byte ceiling fails.

---

### Step S10c.6 — mutation sweep (C4 handoff)

Traces-to: CT1–CT5. Depends-on: S10c.1–.5.

Do:

1. Author `scripts/sweep_specs/s10c_contract_fixes.json`.
2. **Verify every `old` pattern matches `src/` exactly once before running.**
   The harness scores an absent pattern as **SKIP**; in S10b two of fifteen
   patterns silently did not match, which would have reduced a "clean" sweep to
   13 mutations. This pre-check is mandatory, not optional.
3. Mutations, one per contract-bearing guard:
   the `is_file()` check · the `except yaml.YAMLError` wrap · the `DONE`
   comparison · the terminal-state `None` fallback · the hoist (bind
   `terminal_state` inside the `try` again → must fail, RK9) · each JSONL
   `opener=` · the SQLite pre-create · the `mkdir` mode · the Q56
   `is_symlink()` guard · the Q56 tighten-only comparison · the CT4 registry
   lookup · the CT4 `_KNOWN_UNRECOGNISED` entry · the compact `separators=`.
4. Every mutation must be **CAUGHT**. A survivor blocks shipped status.

Exit criteria:

- [ ] pattern pre-check: all patterns match exactly once
- [ ] `caught=N survived=0 skipped=0 harness-fail=0`

---

## 6. Verification plan (§9)

| T# | Test | Class | Oracle (ranked) | Kill-check target | Paths |
|---|---|---|---|---|---|
| T1 | `test_s10c_routing_check_missing_config_is_error` | C2 | exit 2 + path in message | `is_file()` guard | P1 |
| T2 | `test_s10c_routing_check_malformed_yaml_is_error` | C2 | exit 2 + parser line/col in message | the `except yaml.YAMLError` at `config.py:238` | P2 |
| T2b | `test_s10c_selfcheck_malformed_yaml_is_error` | C2 | exit 2, not a traceback | same single site | P2b |
| T2c | `test_s10c_probe_malformed_yaml_is_error` | C2 | exit 2, not a traceback | same single site | P2c |
| T2d | `test_s10b_parity_unparseable_yaml_is_a_config_error` (**inverted**) | C2 | exit 2 | same single site | P2d |
| T2e | `test_s10c_egress_proxy_malformed_yaml_is_error` | C2 | exit 2 at container-start path | same single site | P2e |
| T2f | `test_s10c_loader_raises_configuration_error_on_bad_yaml` | C0p | `ConfigurationError` from the loader directly | the wrap | P2–P2e |
| T3 | `test_s10c_routing_check_empty_config_still_passes` | C2 | exit **0** | the empty-roles branch | P3 |
| T4 | existing routing-check tests | C2 | exit 0/1 unchanged | — (regression) | P4 |
| T5 | `test_s10c_workflow_pass_exits_zero` | C2 | exit 0 + `DONE` | the `== "DONE"` comparison | P5 |
| T6 | `test_s10c_workflow_blocked_exits_nonzero` | C2 | **exit 1** + `FAILED` + `stop_reason` | the derivation | P6 |
| T7 | `test_s10c_workflow_repair_exhausted_exits_nonzero` | C2 | exit 1 + `REPAIR_REQUIRED` | the derivation | P7 |
| T8 | `test_s10c_workflow_replan_required_exits_nonzero` | C2 | exit 1 + `REPLAN_REQUIRED` | the derivation | P8 |
| T9 | `test_s10c_workflow_usage_error_still_exits_two` | C2 | exit 2 | the `result_code != 0` early return | P9 |
| T10 | `test_s10c_workflow_unreadable_terminal_state_falls_back` | C2 | exit == `result_code`; warning logged | the `None` branch | P10 |
| T10b | `test_s10c_workflow_exit_code_survives_export_failure` | C2 | export raises → exit still derived from the verdict, **no `UnboundLocalError`** | the hoist (RK9) | P6, P10 |
| T11 | `test_s10c_llm_bodies_created_0600` | C2 | `S_IMODE == 0o600` on a real file | `opener=` | P11 |
| T11b | `test_s10c_session_db_created_0600` | C2 | `S_IMODE == 0o600` on the DB **and** `-wal`/`-shm` | SQLite pre-create | P11b |
| T11c | `test_s10c_global_history_db_created_0600` | C2 | `S_IMODE == 0o600` | SQLite pre-create | P11c |
| T12 | `test_s10c_events_jsonl_created_0600` | C2 | `S_IMODE == 0o600` | `opener=` | P12 |
| T13 | `test_s10c_run_and_session_dirs_created_0700` | C2 | `S_IMODE == 0o700` both dirs | `mkdir(mode=)` | P13 |
| T14 | `test_s10c_tighten_pass_repairs_existing_modes` | C2 | seeded `0644`→`0600`, `0755` dir→`0700`; idempotent on a second run | the walk | P14 |
| T14b | `test_s10c_tighten_pass_skips_symlinks` | C2 | symlink target's mode **unchanged** | the `is_symlink()` guard | P14b |
| T14c | `test_s10c_tighten_pass_never_widens` | C2 | a `0400` file stays `0400` | the tighten-only comparison | P14 |
| T15 | `test_s10c_composer_extras_are_recognised` | C1 | composer key set ⊆ adapter set, + liveness ≥1 provider | the registry lookup | P15, P16 |
| T16 | `test_s10c_inline_tool_block_is_compact` | C0p | `json.loads` identity + byte ceiling | `separators=` | P17 |

**CI authority:** `just check`.

### LIVE-PATH PROOF — CT2 (the highest-risk claim)

```text
root:            cli:_cmd_workflow
matrix:          verdict = PASS | BLOCKED | REPAIR_REQUIRED | REPLAN_REQUIRED | unreadable
test:            tests/test_s10c_workflow_exit_contract.py::test_s10c_workflow_blocked_exits_nonzero
oracle:          exit code (1) > flow_state.status (FAILED) > global_history.stop_reason
kill-check:      forcing the derivation to `return 0` fails T6 while all artifact assertions stay green
producer:        src/fa/cli.py:_cmd_workflow terminal return (~:1913)
consumer:        operator `fa workflow && deploy`; scripts/fa-clean-rebuild.sh; CI gates
paths-covered:   5/5 (P5-P10)
contract-check:  PASS required
pyramid:         A
```

---

## 7. Research-note disposition (§11a) — every item gets a verdict

| RN# | Item (source) | Verdict | Why |
|---|---|---|---|
| RN1 | I-40: "stat the path; add `yaml.YAMLError`" | **Accept the intent, Rewrite the mechanism** | The stat belongs in the command. But "add it to the tuple" fixes 1 of **5** leaking commands (§1.1a, executed). Moved to the single parse site `config.py:238`; prototyped. |
| RN1b | I-36: scope is "bodies + events" | **Rewrite** | Measured: a real run leaves **four** world-readable artifacts. `session.db` holds the same prose and was unlisted. Both DBs fixed at one shared factory. |
| RN2 | I-40: "belongs in a slice that owns the CLI contract, not a coverage slice" | **Accept** | This is that slice. |
| RN3 | I-36: fix via `Path.open(..., opener=...)` | **Rewrite** | **Measured: raises `TypeError`.** `Path.open()` does not accept `opener`; the builtin `open()` does. Executor would have hit a wall. |
| RN4 | I-36: "needs a test asserting `S_IMODE(...) == 0o600`" | **Accept** | Trivially falsifiable, C2 producer class. |
| RN5 | I-36 (unstated) | **New — Q56** | An `opener` sets the mode only at **creation**; measured that pre-existing `0644` files stay `0644`. Migration is unaddressed by the entry. |
| RN6 | I-37: "add a FeatureFlags A/B, measure eval accuracy, then delete the inline block" | **Defer** | Sound, but it is a measurement project. Its own note: the `AGENTS.md` map is 48.4% vs the tool block's 21%. |
| RN7 | I-37: "drop `indent=2` — pure ~38% saving, zero semantic change" | **Accept (measured 29.6%)** | Re-measured directly: 10,619 → 7,471 bytes. The 38% figure was optimistic; the win is real. |
| RN8 | I-39: "confirm against Mistral's docs, then add or stop emitting" | **Defer the research (Q55 answered)** | Operator: Mistral is a temporary test provider — best-effort only. Neither add nor remove; make the mismatch *asserted* instead of silent, which is the actual complaint. |
| RN9 | I-39: "extend the lint so composer-emitted extras are checked" | **Accept, Rewrite the mechanism** | Do it as a **C1 test** reusing `KNOWN_PROVIDER_PARAMS_KEYS`, not a runtime check — static data deserves a static gate. |
| RN10 | I-35: fix DB concurrency here | **Reject (scope)** | Entry says don't patch `_ensure_identity` alone (prototyped, reverted, 6→3) and to resolve **with Q29**. Production does not reach the window. |
| RN11 | I-34: subagent containment | **Reject (scope)** | Needs an OS-level mount boundary; ADR-scale. The strict `xfail` is already the acceptance signal. |
| RN12 | Q35a (keep exit 0) | **Reject** | Operator selected Q35b. Recorded so the rejected fork is visible. |

---

## 8. Risks and rollback (§10)

| RK# | Risk | Mitigation | Detected by |
|---|---|---|---|
| RK1 | Q35b breaks an operator script or CI job that reads `$?` from `fa workflow` | Deliberate, documented change; §9 requires the S11 runbook note | T6; operator review |
| RK2 | I-40 turns a *previously green* deploy into a red one | **That is the fix working** — it was green while validating nothing. Message names the path. | T1 |
| RK3 | Exit-code change accidentally alters artifacts | CT2 derives from the artifact, never writes it; kill-check requires artifact assertions to stay green | T6 divergence |
| RK4 | `0600` breaks a consumer that reads artifacts as another user | Same-user container; `docker cp` unaffected | T11–T13; S11 container check |
| RK5 | Q56 pass chmods a file it should not | Scoped to the resolved `~/.fa` root; **tighten-only** comparison; `is_symlink()` skip | T14, T14c |
| **RK11** | **Q56 pass chmods a symlink's TARGET.** `os.chmod` follows symlinks (measured) and `follow_symlinks=False` is `NotImplementedError` on Linux — a crafted `~/.fa/.../evil -> /etc/passwd` would have its target's mode changed | explicit `if p.is_symlink(): continue`, asserted by a test that checks the *target's* mode | T14b |
| **RK12** | **Q56 pass locks the agent out of its own state root** by chmod-ing directories to `0600` (no `x` bit) | directories get `0700`; the pass distinguishes file from dir | T13, T14 |
| **RK13** | SQLite pre-create races another process creating the same DB | `os.open(..., O_CREAT)` without `O_EXCL` is idempotent — an existing file is opened, not truncated; mode is only set on creation | T11b + the existing multiprocess concerns in I-35 (unchanged by this slice) |
| RK6 | Compacting JSON changes model tool-selection behaviour | Whitespace-only; semantic identity asserted | T16 |
| RK7 | Executor "consistently" compacts the skills blocks too | Named as out-of-scope in S10c.5 Do-not | Review of `git diff --stat` |
| RK8 | Sweep spec patterns silently do not match | Mandatory pre-check (S10c.6 step 2) — this bit S10b | S10c.6 |
| **RK9** | **Q35b's exit code accidentally depends on the best-effort telemetry export.** `_terminal_state` is bound inside the `try/except Exception` at `cli.py:1879`; consuming it at the `return` without hoisting raises `UnboundLocalError` whenever the export fails early — converting a swallowed telemetry problem into a workflow crash | S10c.2 step 1 hoists the read-back **above** the `try`; the exit code must not depend on whether telemetry succeeded | T10 + a test that makes the export raise and asserts the exit code is still derived |
| **RK10** | CT4 validates a constant that has drifted from the dict the composer actually emits | S10c.4 step 6 asserts the emitted keys equal the exported constant | T15 |

**Rollback.** No feature flag. Every change is a small, self-contained revert:
S10c.1/.2 are single-site edits in `cli.py`; S10c.3 is an `opener=` argument;
S10c.5 is one `json.dumps` kwarg. No data migration is irreversible — Q56's
chmod is idempotent and does not alter content. **Explicitly not flagged:** a
flag on an exit-code contract would mean the contract is ambiguous, which is
the defect being fixed.

---

## 9. Definition of Done — S10c

- [ ] `fa routing-check --config <missing>` exits **2**; `fa-clean-rebuild.sh`
      would now abort. Empty-but-present still exits 0.
- [ ] Malformed YAML exits **2 from all five** commands — `routing-check`,
      `run`, `selfcheck`, `probe`, `egress-proxy` — asserted per command, and
      the message carries the parser's line/column.
- [ ] `fa workflow` exits **1** on any non-`DONE` terminal status, **0** on
      `DONE`, **2** on usage/config error, and falls back on an unreadable
      artifact.
- [ ] **Artifacts unchanged by S10c.2** — `flow_state.json`, `eval_report.json`
      and `global_history.stop_reason` byte-identical for the same run.
- [ ] **All four** artifacts are `0600` at creation — `events.jsonl`,
      `llm_bodies.jsonl`, `session.db` (+ WAL sidecars), `global_history.db` —
      and `session-log/<run_id>` / `sessions/<sid>` are `0700`.
- [ ] Q56 comprehensive pass: repairs existing `0644` files and `0755` dirs,
      **skips symlinks** (target mode unchanged), never widens, idempotent.
- [ ] No composer-emitted extra is silently dropped: every key is recognised or
      in `_KNOWN_UNRECOGNISED` with a reason. Two kill-checks pass — a fictional
      key fails, and **deleting the allow-list entry also fails** (proving the
      entry is load-bearing).
- [ ] Inline tool block compact; ≥2,500 bytes saved; semantics identical.
- [ ] Mutation sweep: pattern pre-check passed, **0 survivors**.
- [ ] `just check` green; **zero new `noqa`**; C901 waiver budget still **15**
      or lower.
- [ ] Every inverted test carries a docstring naming S10c and the reason.
- [ ] BACKLOG I-36, I-39, I-40 marked RESOLVED with evidence; I-37 updated to
      record that option 4 shipped and the A/B remains open.
- [ ] Handoff updated; S11 runbook notes the two exit-code changes.

**Negative proof.** "The suite is green" is not evidence for this slice — the
suite was green while `routing-check` validated nothing and `fa workflow`
reported success on rejected code. The proof is: (a) each inverted test failed
before its fix and passes after, recorded with actual output; (b) the CT2
kill-check shows the exit code changing while artifacts stay identical; (c) the
sweep's pattern pre-check passed before its results are believed.

---

## 10. Open questions

**Q55 — RESOLVED (operator, 2026-08-01).** *"Mistral is a temporary tests
provider, no need to optimize it further than best effort."*

**Decision: neither add the key nor stop emitting it.** Fix the *silence*, not
the mismatch. `prompt_cache_retention` keeps working on OpenAI-compatible
routes (`test_providers_openai_compat.py:139`) and stays unrecognised by
Mistral **by decision**, recorded in an explicit `_KNOWN_UNRECOGNISED`
allow-list that CT4 asserts. A *second*, unplanned silent drop still fails the
gate — which is the real I-39 complaint. Adding the key would claim support we
have not verified; removing the emit would penalise routes where it works.
Owner for revisiting: whoever promotes a provider out of "temporary test".

**Q56 — RESOLVED (operator, 2026-08-01).** *"Do tighten pre-existing 0644
artifacts in S10c.3. Comprehensive tightening pass."*

**Decision: a comprehensive pass over `~/.fa`, not the narrow per-writer
version v1 defaulted to.** Implemented as `tighten_fa_artifact_modes(root)` in
`fa/paths.py`, invoked from the run/workflow entry path.

Three constraints the review proved are mandatory (all measured, §S10c.3):
1. **skip symlinks explicitly** — `os.chmod` follows them, and
   `follow_symlinks=False` raises `NotImplementedError` on Linux;
2. **directories get `0700`, not `0600`** — otherwise the pass makes the state
   root untraversable;
3. **tighten only, never widen** — a deliberate `0400` must survive.

**Q57 — RESOLVED (operator, 2026-08-01).** *"Yes, as part of S10c.1."*

Superseded in mechanism by the v2 review: rather than fixing `_cmd_run`'s
handler specifically, the single parse site at `config.py:238` is wrapped, so
**all five** leaking commands are fixed at once (§1.1a). The S10b parity cell
`test_s10b_parity_unparseable_yaml_crashes` is inverted in the same commit —
exactly what its own docstring anticipated: *"this test INVERTS when I-40 is
fixed — that is its purpose."*

---

## 11. Anti-theater checklist + READY gate (§11.2)

- [x] Every referenced symbol verified at file:line, or marked **NEW**
      (`private_opener`, the two new test modules, the sweep spec)
- [x] Every GAP# has an owning step and at least one T#
- [x] Every CT# has a producer, a consumer, a deterministic mechanism, and a
      kill-check
- [x] Path sensitivity enumerated (P1–P17), including the fallback path P10 an
      executor would skip
- [x] Research notes each carry a verdict — including **two Rejects** and one
      **Rewrite** of a fix that does not compile as written
- [x] Component gate applied: `private_opener` and `tighten_fa_artifact_modes`
      go in the existing `fa/paths.py`; the SQLite fix goes in the existing
      shared `create_sqlite_connection`; CT4 reuses
      `KNOWN_PROVIDER_PARAMS_KEYS` rather than restating key lists;
      **no new modules**
- [x] **Every mechanism in this plan was executed against the real code, not
      reasoned about** — the five-command YAML leak, the four-artifact mode
      census, the SQLite + WAL pre-create, the symlink-follow hazard, the
      `NotImplementedError` on `follow_symlinks=False`, `O_CREAT` preserving
      content, and the 29.6% JSON saving
- [x] Minimalism-first (§1.2 Q4): every check is a deterministic Python
      function or a static test — no LLM call, no per-request runtime cost
- [x] Negative proof is not "coverage" or "green suite"
- [x] Non-blocking questions all carry defaults (Q55, Q56, Q57)
- [x] **BLOCKING question set EMPTY**

**→ Status: READY.** Order: S10c.0 → S10c.1 → S10c.2 → {S10c.3, S10c.4,
S10c.5 parallel} → S10c.6.

---

## 12. Execution record — 2026-08-01

Status: **S10c COMPLETE.** All seven GAPs closed; I-36, I-39 and I-40 marked
RESOLVED in the BACKLOG; I-37 updated to record that option 4 shipped.

| Step | Verdict | Evidence |
|---|---|---|
| S10c.0 | PASS | baseline recorded: GAP1 exit 0 · GAP2 leaking from 4 probed commands · 4 world-readable files + 4 open dirs · 10,619 bytes |
| S10c.1 | PASS | GAP1+GAP2 — all five commands exit 2 |
| S10c.2 | PASS | GAP3 — verdict-driven exit code |
| S10c.3 | PASS | GAP4+GAP5 — every file `0600`, every dir `0700` |
| S10c.4 | PASS | GAP6 — no silent drop, three exceptions asserted |
| S10c.5 | PASS | GAP7 — 3,148 bytes/request saved |
| S10c.6 | PASS | 15 mutations, 1 survivor **root-caused and killed** |

**Final gate:** 2415 passed / 14 skipped / 1 xfailed · ruff clean · mypy 322 ·
pyrefly 0 · pylint exit 0 · `cli-coverage-floor` 27/27 · all `just check`
stages PASS · C901 waiver budget still **15**.

### What execution found that the plan did not

Four things, all caught by running the code rather than reading it:

1. **The aggregate row disagreed with the process about its own exit code.**
   `global_history`'s `exit_code` column was built from `result_code` inside
   the export block while the process returned a value derived afterwards, so
   a BLOCKED run briefly reported `code == 1` with `row["exit_code"] == 0`.
   Two artifacts disagreeing about one run is precisely the class S8.7 existed
   to remove. Fixed by computing the exit code **once**, before the export.
2. **The C901 ratchet caught the Q35b change.** Adding the derivation inline
   pushed `_cmd_workflow` to 16 > 15. Fixed the design — extracted the pure
   `_workflow_exit_code()` — rather than adding a waiver. `cli.py` stays at
   zero C901 findings and the budget stays 15. *The gate S10b built paid for
   itself one slice later.*
3. **The CT4 gate found a third silent drop on its first run.** I-39
   documented `mistral`; `mistral_agents` has the identical gap. Verified
   against the adapter's own constant, not inferred from the family name.
4. **One of my own tests was vacuous.** The first CT5 draft re-encoded the
   tool specs locally and compared `separators` against `indent=2` — it passed
   with production reverted to `indent=2`, because it never read production.
   Found by *running* the kill-check instead of trusting it. Rewritten to read
   what `build_prompt_parts_v2` actually emits.

### RK9 was real — the kill-check reproduced it exactly

The plan predicted that reusing the `_terminal_state` local would ship a crash,
because that name is bound inside the `try/except Exception` guarding the
telemetry export. Moving the read-back back inside produces:

```text
UnboundLocalError: cannot access local variable 'terminal_state'
```

i.e. a swallowed export problem becoming a hard workflow crash, from the one
block written never to fail. `T10b` pins it by forcing the export to raise.

### The mutation survivor was worth the time

`caught=14 survived=1 skipped=0 harness-fail=0`. **M12** — deleting
`mode=PRIVATE_DIR_MODE` from `session_dir.mkdir` — changed nothing observable.

Root-caused instead of patched: disabling *both* that and the Q56 repair pass
was measured to leave the directory at `0755`, so the two layers are genuinely
independent and the survivor is **defence in depth**, not a weak oracle. Both
layers kept — the creation mode closes the window between `mkdir` and the
repair pass, and `SessionManager` is a library a caller can use without going
through `fa run` at all — and a new test exercises the creation layer in
isolation so each layer has its own oracle. M12 now fails a named test.

The sweep also demonstrates the security guards are genuinely tested: M6/M7/M8
(the openers and the SQLite pre-create) are invisible to every functional test
— a `0644` file behaves exactly like a `0600` one until someone else reads it
— yet each was caught. That is why the posture tests assert modes rather than
behaviour.

### Pattern pre-check earned its keep again

**M2 did not match** the source: ruff had reformatted the f-string onto one
line after the plan was written. The harness scores an absent pattern as
**SKIP**, so the run would have silently covered 14 of 15 while the summary
read clean — the same trap S10b hit with two patterns. Verifying every `old`
matches exactly once, before running, is now a standing step.

### Also fixed

A side effect of my own tests: `0400`/`0700` fixtures made pytest's `rm_rf`
leave `garbage-*` trees in `/tmp` on every run. An autouse teardown re-widens
`tmp_path`.

### Open, unchanged

**I-37 options 1–3** (delete the duplicated inline tool listing) still need the
eval-corpus A/B, and the `AGENTS.md` map remains the larger target at 48.4% of
a live request. **I-34** and **I-35** remain deliberately out of scope (RN10,
RN11).
