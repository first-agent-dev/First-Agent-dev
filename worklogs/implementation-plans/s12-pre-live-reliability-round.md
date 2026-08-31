# PLAN: S12 — pre-live reliability round  Plan-ID: PLAN-s12-pre-live-reliability

Status: IMPLEMENTED (S12.1-S12.6 complete in working tree, 2026-08-31; awaiting patch + host apply + live env/pty rows)   Depth: P2 (cross-module engine + config + rollout; guard-gate change)

> **Execution note.** All contracts CT1-CT6 implemented. Per-slice verification:
> targeted suites + full mypy (408 files) + ruff format/check + mutation
> kill-checks (S12.2 x1, S12.4 x5, S12.5 x3, S12.6 x2 battery probes; S12.1/S12.3
> producer kill-checks in-suite). Full pytest 3702 passed; the remaining reds are
> the two deliberate S7 doc-gate baits plus sandbox-environment artifacts (exec
> bits, symlinks, pyrefly import resolution, uvx/semgrep/vulture binaries) -
> each triaged, none S12-caused. Battery: 25 OK, 0 missed, 0 defects.
Revision: v2   Changed-since-last: adversarial review pass — CT2 producer
re-anchored (ReadyState is discarded at manager.py:295/351, not plumbable to
the drive site); dead module removed from CT1 scope; CT4 given exact insertion
point + real test names + verified observe mechanism; CT5 corrected to three
calling seats; CT6 oracles made binary and env-row turn cap fixed (2→6,
enforce-mode ceremony); LT4 decoupled from deferred D10; timeout
double-execution documented as pre-existing (RK7).

S11 (constant closure) is PAUSED by operator decision 2026-08-31. S12 fixes the
high-ROI defects that the 2026-08-30/31 live trial (kimi k3 + gemini 3.7 med,
rows l1–l3) exposed, so the live re-test measures the product instead of the
harness's environment plumbing. Slice number `S12` verified free in repo
sources (historical `S13`/`S22` markers exist and are unrelated to the
live-trial series numbering).

## Preflight log

```text
roots checked:
  fa CLI drive path (src/fa/cli.py), hook registration (cli.py:1661-1665),
  inner-loop bash execution (src/fa/inner_loop/run_bash.py,
  src/fa/inner_loop/tools/run_bash.py), PTY runtime
  (src/fa/runtime/pty_pool.py), feature flags (src/fa/feature_flags.py),
  PR-intent hygiene (src/fa/hygiene/pr_intent.py,
  src/fa/inner_loop/tools/prepare_pr.py, src/fa/inner_loop/hooks/intent_guard.py),
  workspace readiness (src/fa/workspace_bootstrap.py),
  live-verification runner (scripts/run_live_check.sh + battery + pins),
  image env (Dockerfile.fa:11,95-96).

greps/reads -> findings:
  - Readiness provisions workspace/.venv via `uv sync --locked --extra dev`
    (workspace_bootstrap.py:74,588; UV_PROJECT_ENVIRONMENT pinned, :259).
    Live proof: session-d18bbe2f…/.venv/bin/pytest existed during the
    2026-08-31 l2 run (turn-6 `find /` output) and `uv run pytest` collected
    145 items (turn 17).
  - Readiness success is SILENT: _prepare_managed_workspace (cli.py:141-150)
    prints only when status != READY. No prompt-side announcement exists
    ("absent after grep" over src/fa for readiness prompt injection).
  - Container PATH = /opt/fa-venv/bin:… (Dockerfile.fa:11); runtime venv built
    `uv sync --frozen --no-dev` (:96) while pytest is in the dev group
    (pyproject.toml:49-54) → bare `pytest`/`python3 -m pytest` cannot work in
    the agent shell. No PATH/venv wiring exists in pty_pool.py,
    bash_executor.py, or bash_env.py (grep: zero hits).
  - PtySession tmux init already sends an export setup line
    (pty_pool.py:186-195: PS1/PROMPT_COMMAND/PAGER/TERM) — insertion seam for
    PATH. pexpect fallback takes env= dict (:134). Subprocess fallback builds
    env via build_scrubbed_env (tools/run_bash.py:246; PATH is allowlisted,
    bash_env.py:31).
  - _run_tmux timeout branch (pty_pool.py:317-432) returns timed_out=True with
    NO interrupt sent; `output` is only assigned on success → the
    "Timeout Ns partial:" branch (:424) is dead code. send_ctrl_c +
    _wait_for_sentinel exist (:453-470, :202) but are wired only to the
    fs_send_ctrl_c tool. Live proof: after the t12 30s timeout, EVERY later
    pty call — including `which uv || which pip` (t16) — returned
    "Timeout 30s: no output captured" (orphaned command holds the pane).
  - IntentGuard: GuardMiddleware.handle -> Decision.allow()/deny(reason)
    (hooks/base.py:109-111; intent_guard.py:267-314); registered at
    cli.py:1665. hook_decision events already flow to the session log via
    hooks.set_event_sink (loop.py:551).
  - FeatureFlags pattern to mirror: frozen dataclass, anchored defaults,
    dotted config keys in _KNOWN_FLAGS (worktree.mode has BOTH spellings),
    FAIL_CLOSED_FLAGS / FAIL_OPEN_FLAGS categorization enforced by
    tests/test_s13_fail_closed_open.py::test_all_fields_categorized
    ("every field must be in exactly one set") +
    ::test_fail_closed_flags_default_restrictive.
  - Invariant shape table: _INVARIANT_REQUIRED_PREFIXES
    (pr_intent.py) maps RESEARCH→("n/a",), CHORE→("n/a",), ADR_RULE→
    ("Contract:",), IMPLEMENT→("Implements:",), FIX→("Affects:",). Enforced at
    TWO seats: pr_prepare tool (_validate_invariant_prefix, prepare_pr.py:157)
    and commit-msg hook (validate_commit_msg Check 3, pr_intent.py:614-633).
    The tool input schema (prepare_pr.py:67-85) documents NONE of this.
    Live proof: 3 reproductions × 2 models (D11).
  - tool_batching.enabled flag gates parallel dispatch (loop.py:548-560) —
    earlier session claim "not flag-gated" REJECTED (see RN1).
  - SKILL.md pr-creation documents the n/a rows (:101,:105) — doc-sync
    required for F4.
  - v2 review pass (all fresh reads):
    * ReadyState is DISCARDED at both preparer call sites
      (manager.py:294-295, 350-351; preparer wired at cli.py:178) — the
      announcement cannot consume it; the drive site must use a local
      predicate. `workspace` is in scope in _cmd_run (cli.py:1925; used at
      :2124,:2133,:2136) including at the system_prompt_extra site (:2179).
    * src/fa/inner_loop/run_bash.py is DEAD in src: zero importers
      (absolute + relative greps). All five fs_run_bash registration sites
      use fa.inner_loop.tools.run_bash (tools/__init__.py:180,213,249,297;
      profiles.py:330-332). Subagents = same builder with executor=None →
      _run_subprocess_fallback (tools/run_bash.py:331-339).
    * Invariant shape has THREE calling seats, two code paths:
      pr_prepare tool (_validate_invariant_prefix), commit-msg hook AND
      IntentGuard (intent_guard.py:298) — the latter two both via
      validate_commit_msg Check 3.
    * Observe-mode telemetry is implementable WITHOUT new event kinds:
      Decision.reason propagates for allow decisions
      (base.py:159-164 DispatchRecord(reason=decision.reason)) and the sink
      persists {middleware, point, decision, reason} (loop.py:77-93).
    * _wait_for_sentinel RAISES TimeoutError on expiry (pty_pool.py:219) —
      the timeout-interrupt path must catch it.
    * Categorization gate real names: tests/test_s13_fail_closed_open.py::
      test_all_fields_categorized + ::test_fail_closed_flags_default_restrictive.
    * _build_run_hook_registry (cli.py:1584) has NO flags parameter;
      established pattern is a lazy `from fa.feature_flags import
      load_feature_flags_from_path` inside the function
      (profiles.py:343-345 precedent).
    * DEFAULT_CONFIG_PATH = ~/.fa/config.yaml (config.py:40) → host side
      $STATE_HOST/config.yaml (state bind).
    * test_s10b_cli_parity.py imports _build_run_hook_registry (line 50) —
      regression gate for any registration-order/branch change.
  - Live runner v4.4 (main ece9bcc + S10.9-live-v4.4 patch): subcommands
    setup|smoke|l1|l2|l3|l4|ledger, exit contract 0/1/2/3, timeline v2 with
    per-turn model/latency/failover + summary + [STOP].

gold patterns mirrored:
  - Flag plumbing: tool_batching_enabled end-to-end (feature_flags.py →
    loop.py:548-560 fail-open read with None-guard).
  - String-mode flag: worktree_mode ("shared") incl. dual spelling in
    _KNOWN_FLAGS.
  - Observe-only gate precedent: S10.9 CAE shipped observe-only, default off.
  - Sheet/runner/battery/pins discipline: S10.9 rev4 (adversarial battery +
    contract pins + live rows).

conflicts/invariants:
  - Two doc-gate tests stay RED deliberately (S7 bait, row L3). S12 must not
    "fix" them and must not add new doc-link breakage.
  - FAIL_CLOSED categorization test will fail until intent_guard_mode is
    added to exactly one set (decision: FAIL_CLOSED — missing config must
    yield the restrictive value "enforce").
  - ADR-16 stays `proposed`; S11 constants (ε, K, tiers incl. D12) are NOT
    S12 scope — changing tier defaults mid-trial would pollute S11's
    calibration feed.
  - Live rows must keep running through the production mechanism only
    (./scripts/fa wrapper; no worktrees/host venv on the live path).

current liveness:
  - Readiness venv provisioning: L3 (proven live 2026-08-31).
  - PATH wiring / announcement: L0 (absent after grep).
  - PtyPool timeout interrupt: L0 (absent); partial-output branch: dead code.
  - IntentGuard mode toggle: L0. CHORE invariant relaxation: L0 (today
    enforced at two seats).
  - Live rows env/pty: L0.

unresolved -> Q#: Q9 (RESEARCH relaxation scope) and Q10 (flag spelling)
  non-blocking with defaults; Q1-Q4 resolved by operator 2026-08-31.
```

## 0. Executive intent

**Goals**

- **G1** An agent bash call in a managed session workspace resolves
  `pytest`/`python` to the readiness-provisioned `workspace/.venv` — and the
  model is TOLD the workspace is ready and how to run tests. (closes GAP1)
- **G2** A bash command that exceeds the timeout must not brick the session's
  persistent shell: interrupt on timeout, return partial output, next command
  runs immediately. (closes GAP2)
- **G3** IntentGuard gets an operator mode toggle — `enforce | observe | off`,
  default `enforce` — so live trials can run without draft-ceremony blocking
  while denial telemetry keeps flowing. (closes GAP3)
- **G4** The CHORE invariant-shape check stops demanding the magic literal
  `n/a`: shape requirement dropped for CHORE (empty-tuple semantics at both
  enforcement seats), and the required prefixes for the remaining intents are
  documented in the `pr_prepare` tool schema + one prompt-side guidance line.
  (closes GAP4)
- **G5** Every S12 change is live-verifiable: new sheet rows `env` and `pty`,
  setup prints effective flag modes, l1 gains a ceremony expectation; the
  deferred items land in BACKLOG.md with unblock-triggers. (closes GAP5)

**Non-goals** (explicit)

- IntentGuard refactor (operator: low priority; toggle only).
- D10 LoopGuard truncated-read thrash fix; D17 proper read-only-bash
  exemption (needs command classification; folds into the future refactor).
- D12 tier-default change, verify_failed evidence quality, ε/K constants —
  all S11-owned, paused.
- Bash timeout double-execution (RK7): pre-existing, needs its own contract
  (idempotency token or no-retry-on-timeout) — BACKLOG entry added in S12.6.

**Deferred-with-eyes-open (trajectory check).** D10 (LoopGuard counts
truncated continuation reads as path thrash) is NOT fixed here, and it can
still block an l2/l3 edit — the live 2026-08-30 kimi l2 row died that way.
S12 therefore does NOT claim "l2 completes"; LT4 claims only "the edit is
reached and the environment is not the reason it was not". Promoting D10
into S12 was considered and rejected: it is a guard-semantics change with no
live reproduction on the current model, and bundling it would make the S12
diff touch three guard subsystems at once.
- No Dockerfile/compose changes; no new dependencies.

**Minimal mechanism.** Extend existing seams only: the tmux setup-export line,
the pexpect env dict, build_scrubbed_env output, the FeatureFlags dataclass,
the existing prefix table (empty-tuple = no shape check), the existing
Decision/hook_decision telemetry path. No new subsystems.

**Proof sketch.** Unit + fake-tmux + battery tests per contract with producer
kill-checks; live proof = the new `env` and `pty` rows on the host after
`fa update`, plus an l2 re-run that must reach the edit phase with zero
environment archaeology turns.

## 1. Current state → target state (GAP ledger)

| GAP | Current (verified) | Target |
|---|---|---|
| GAP1 | `.venv` exists but agent shell PATH = `/opt/fa-venv/bin:…` (no pytest); readiness success silent; 12/20 turns of l2 burned on archaeology | PATH prepends `workdir/.venv/bin` in all three exec paths when present; READY state announced in the system-prompt extras with test-run + pr_prepare guidance |
| GAP2 | `_run_tmux` timeout: no interrupt, dead partial branch, orphaned command holds the pane; 7 calls × 30 s tax in one live run | timeout sends C-c + waits for sentinel, partial output returned, next command unaffected |
| GAP3 | IntentGuard always enforces; read-only bash denied pre-draft (D17 live, t9); no operator control | `intent_guard_mode` ∈ {enforce, observe, off}, default enforce, FAIL_CLOSED; observe logs would-be denials via existing telemetry and allows |
| GAP4 | CHORE/RESEARCH invariant must literally start with `n/a`; schema documents nothing; 3 live reproductions × 2 models, ~2 turns + ~50 s each | CHORE shape check dropped (empty tuple; RESEARCH per Q9 default: also dropped); schema documents remaining prefixes; prompt guidance line added |
| GAP5 | Sheet proves CAE behavior but not env readiness / pty recovery / flag state | `env` + `pty` rows, setup flag printout, l1 ceremony expectation, battery + pins; BACKLOG.md entries for deferred items |

## 2. Contracts

```text
CT1: venv-path-wiring  TYPE:function/module
PRODUCER: src/fa/runtime/pty_pool.py PtySession.__init__ — tmux setup_cmd
  (MODIFIED: `;`-separated clause appended after the existing export chain so
  a missing venv can never break the && chain) + pexpect spawn env dict
  (MODIFIED: PATH computed from os.environ with the prepend; note the
  existing env dict replaces the child environment wholesale, so PATH must
  be constructed, not assumed) ; src/fa/inner_loop/tools/run_bash.py
  _run_subprocess_fallback (MODIFIED: post-scrub PATH prepend).
  SCOPE NOTE (v2): src/fa/inner_loop/run_bash.py is DEAD in src (zero
  importers, absolute + relative) and is NOT edited — all five registration
  sites use fa.inner_loop.tools.run_bash; subagents reach the same
  _run_subprocess_fallback via executor=None (tools/run_bash.py:331-339).
ROOTS/CALLERS: every fs_run_bash call in main-agent (stateful pty) and
  subagent (stateless subprocess) sessions
INPUTS/OUTPUTS/ERRORS: workdir/.venv/bin exists → prepended to PATH (tmux:
  `[ -d .venv/bin ] && export PATH="$PWD/.venv/bin:$PATH"` appended to
  setup_cmd, $PWD = pane start_directory = session workspace; pexpect/
  subprocess: env["PATH"] prepend) ; absent → env UNCHANGED (raw clones
  behave exactly as today)
SIDE EFFECTS: none beyond child-process env
INVARIANTS: prepend is first-on-PATH; system paths preserved after it;
  no mutation when .venv missing; scrubbing order unchanged (PATH prepend
  happens AFTER build_scrubbed_env, never bypasses the secret filter);
  child login shells spawned BY the model (bash -lc) re-source profile and
  lose the prepend — accepted, documented in the tool description (existing
  "stateful" wording covers the main path)
KILL-CHECK: removing the prepend makes T1 (PATH order assertions, all three
  backends) fail
```

```text
CT2: readiness-announcement  TYPE:signal
PRODUCER: src/fa/cli.py _cmd_run (def at :1925) — at the existing
  system_prompt_extra argument of the drive_session call (:2179), append the
  readiness block when `(workspace / ".venv" / "bin").is_dir()` (NEW
  predicate; `workspace` already in scope, used at :2124/:2133/:2136).
  v2 CORRECTION: v1 said "when _prepare_managed_workspace returned READY" —
  NOT IMPLEMENTABLE: the ReadyState return value is discarded at both
  preparer call sites (manager.py:294-295, 350-351) and never reaches
  _cmd_run. The venv-exists predicate is the exact truth condition for what
  the announcement CLAIMS (venv + how to run tests); hook/marker readiness
  is not claimed and needs no plumbing. Degraded bootstrap without venv →
  no announcement (matches old intent).
CONSUMER: model system prompt (cacheable prefix, per D7 static-content rule)
TRIGGER/PAYLOAD/STATE: payload = workspace-ready line + "tests: `uv run
  pytest …` or `.venv/bin/pytest`" + "call pr_prepare before the first
  workspace mutation (CHORE for chores)" (the F4 guidance line rides here).
  Exact wording pinned verbatim by T2.
DUAL-WRITE: no — prompt-only by design; the stderr WARN stays the operator
  channel
PATHS/MATRIX: P1 (venv present → announced), P2 (venv absent → absent),
  P3 (raw/unmanaged workspace → absent, same predicate)
PRODUCER KILL-CHECK: removing the append makes T2 (drive-level assertion on
  system_prompt_extra content) fail
CONSUMER KILL-CHECK: n/a (model consumption proven by live `env` row, LT1)
```

```text
CT3: pty-timeout-hygiene  TYPE:function/module (reliability add-on)
PRODUCER: src/fa/runtime/pty_pool.py _run_tmux timeout branch (MODIFIED) +
  poll loop partial accumulation (MODIFIED); _run_fallback parity (MODIFIED)
ROOTS/CALLERS: _run_pty_executor → every stateful fs_run_bash
INPUTS/OUTPUTS/ERRORS: on timeout: send C-c
  (`self.pane.send_keys("C-c")`), then `_wait_for_sentinel(timeout=5)`
  WRAPPED IN try/except TimeoutError — the helper RAISES on expiry
  (pty_pool.py:219) and an uncaught raise here would replace a clean
  timeout result with an exception path (P5). Return
  PtyResult(timed_out=True, stdout=partial + timeout marker). Next run()
  call starts from a clean prompt.
  Partial accumulation: each poll iteration stores the cleaned
  after-start-token snapshot; the existing "Timeout Ns partial:" branch
  (pty_pool.py:424, currently DEAD because `output` is only assigned on
  success) becomes live. Success path byte-identical.
  _run_fallback parity: on pexpect TIMEOUT, `sendcontrol("c")` before
  returning (partial already returned via `before`).
INVARIANTS: timed_out semantics unchanged for callers; C-c only for the
  timed-out invocation; heredoc script cleanup still runs (_cleanup_script
  already precedes the return — keep it there); success path byte-identical
SIDE EFFECTS: SIGINT to the pane's foreground process on timeout
SCOPE NOTE: the pty-timeout → subprocess-fallback RE-RUN of the same command
  (double execution for non-idempotent commands) is PRE-EXISTING behavior
  (tools/run_bash.py:208-210 raises → :339 fallback). S12 does not change
  it; see RK7.
KILL-CHECK: removing interrupt-on-timeout makes T3b (fake-tmux: command
  after a timeout completes without its own timeout) fail; removing partial
  accumulation makes T3a fail; removing the TimeoutError catch makes T3c
  fail with an unhandled exception instead of a timeout result
BUDGET: added latency on timeout ≤ 5 s sentinel wait (vs today's 30 s × every
  subsequent call)
```

```text
CT4: intent-guard-mode  TYPE:signal + security gate
PRODUCER:
  (a) src/fa/feature_flags.py FeatureFlags.intent_guard_mode: str =
    "enforce" (NEW field; _KNOWN_FLAGS gets BOTH "intent_guard.mode" and
    "intent_guard_mode" per the worktree.mode dual-spelling precedent;
    FAIL_CLOSED_FLAGS member; as_dict entry) ;
  (b) src/fa/cli.py _build_run_hook_registry (def :1584) — lazy
    `from fa.feature_flags import load_feature_flags_from_path` INSIDE the
    function (established pattern: profiles.py:343-345; the builder has no
    flags parameter and gains none), read `.flags.intent_guard_mode`;
    `off` → skip the IntentGuard registration line (:1665); otherwise pass
    `mode=` into the constructor ;
  (c) src/fa/inner_loop/hooks/intent_guard.py IntentGuard.__init__ (def
    :242) gains `mode: str = "enforce"` (default keeps every other caller/
    test constructing IntentGuard unchanged); handle() (deny returns at
    :277 and :314) — in observe mode, a computed deny is converted to
    `Decision(action="allow", reason="would-deny(observe): " + <original
    reason>)`. VERIFIED mechanism: DispatchRecord.reason = decision.reason
    for allow decisions (base.py:159-164) and the sink persists
    {middleware, point, decision, reason} (loop.py:77-93) — the would-deny
    text reaches the durable hook_decision event with NO new event kind.
CONSUMER: tool-admission path (Decision), session log (hook_decision events),
  live sheet setup printout
TRIGGER/PAYLOAD/STATE:
  enforce → today's behavior exactly (registration + decisions untouched);
  observe → evaluation runs unchanged; deny → allow with the
    "would-deny(observe): " prefixed reason (persisted by the sink);
  off     → guard not registered; pr_prepare tool and draft_store remain
    (harmless; draft-store cleanup at session end is guard-independent);
  unknown value → loader warning (fail-observable, existing
    FeatureFlagWarning path) + enforce.
SECURITY: FAIL_CLOSED — flags unreadable ⇒ enforce (restrictive). Rationale:
  a missing config must never silently unguard mutations. Off is an explicit
  operator act, visible in setup printout + ledger notes.
PATHS/MATRIX: M1 enforce default, M2 observe deny→allow+log, M3 observe
  allow stays allow (reason NOT prefixed), M4 off (no IntentGuard
  hook_decision events), M5 config missing→enforce, M6 garbage value→
  warn+enforce
REGRESSION GATES: tests/test_s13_fail_closed_open.py::
  test_all_fields_categorized + ::test_fail_closed_flags_default_restrictive
  (new field must be categorized FAIL_CLOSED and default restrictive) ;
  tests/test_s10b_cli_parity.py (imports _build_run_hook_registry at :50 —
  default enforce must keep the assembled stack byte-identical) ;
  tests/test_intent_guard.py (constructor default keeps existing cases green)
PRODUCER KILL-CHECK: deleting the mode branch in handle() makes T4 (observe
  allows + logs; enforce denies) fail
CONSUMER KILL-CHECK: removing the reason prefixing makes T4b (hook_decision
  event content assertion) fail
```

```text
CT5: chore-invariant-relaxation + schema docs  TYPE:data/function
PRODUCER: src/fa/hygiene/pr_intent.py _INVARIANT_REQUIRED_PREFIXES:
  Intent.CHORE → () (and Intent.RESEARCH → () per Q9 default) ; empty tuple
  means "no shape check" at BOTH code paths that read the table:
  (1) prepare_pr.py _validate_invariant_prefix (:157) — add
    `if not required: return None` BEFORE the any() test (an empty tuple
    makes any() False — without the early return the check would reject
    EVERY value, the exact inverse of the intent) ;
  (2) pr_intent.py validate_commit_msg Check 3 (:614-633) — gate as
    `if required and not any(...)`.
  v2 CORRECTION — THREE calling seats, two code paths: the commit-msg hook
  AND IntentGuard (intent_guard.py:298) both reach Check 3 through
  validate_commit_msg; the pr_prepare tool has its own helper. v1 said
  "both seats" and undercounted the guard.
SCHEMA/COMPATIBILITY: additive-behavioral; drafts with literal `n/a` remain
  valid (empty tuple accepts any non-empty value; invariant_missing check
  unchanged — field still required)
AUTHORITY: knowledge/skills/pr-creation/SKILL.md rows updated in the same
  slice (CHORE/RESEARCH invariant: "free-form (no shape enforced)")
READ/WRITE PATHS: pr_prepare tool seat + validate_commit_msg (shared by the
  commit-msg hook and IntentGuard) — table + both readers change in ONE
  slice, never separately
FIXTURE HONESTY: tests use the real table, not a copy
KILL-CHECK: new T5a (free-form CHORE invariant accepted at ALL THREE seats:
  tool handler, validate_commit_msg, IntentGuard.handle with a CHORE draft)
  fails if any seat keeps the prefix check; T5b (FIX still requires
  "Affects:", IMPLEMENT "Implements:", ADR_RULE "Contract:") fails on
  over-relaxation; T5c: schema description contains the per-intent prefix
  table; T5d: existing `n/a` snapshot suite stays green
```

```text
CT6: live-verification rows  TYPE:signal (operator surface)
PRODUCER: scripts/run_live_check.sh NEW subcommands `env`, `pty` (both via
  row_run, inheriting the v4.4 exit contract); setup prints effective
  intent_guard/tool_batching modes parsed from $STATE_HOST/config.yaml
  (host side of container ~/.fa/config.yaml, config.py:40) with
  "intent_guard.mode: enforce (default)" when the file/key is absent; l1
  verdict adds ceremony note (IntentGuard denial count from events,
  expectation ≤1 → [NOTE] when exceeded, never a FAIL — model variance)
CONSUMER: operator terminal + ledger rows (row=env / row=pty)
TRIGGER/PAYLOAD/STATE:
  env row (6-turn cap — v2 FIX: enforce-mode IntentGuard ceremony costs ≥2
  turns before the probe even runs (live evidence: 2026-08-31 l2 t9), so the
  v1 2-turn cap was unachievable in the default mode):
    task: "Using bash, run `pytest --version` in this workspace and reply
    with only the version."
    PASS oracle (binary, transcript-grep): fa rc=0 AND log matches
    `pytest [0-9]+\.[0-9]+` AND log contains NEITHER "command not found"
    NOR "No module named pytest". Oracle failure with rc=0 → exit 3 +
    ledger flag ENV_PROBE_FAILED (v4.4 objective-miss contract).
    v2: dropped v1's "zero archaeology" grep — unanchored and fragile;
    the two absence-greps above are the honest signal (they are exactly
    the strings the 2026-08-31 failure produced).
  pty row (6-turn cap):
    task: "Run `sleep 35` via bash (it will time out — that is expected),
    then run `echo RECOVERED` and reply with its output."
    PASS oracle (binary): log contains "RECOVERED" AND
    `grep -c 'PtyPool executor timeout' log` ≤ 1 (the sleep's own pty
    attempt is expected to fall back exactly once; a dirty pane taxes every
    later command — the 2026-08-31 run showed 7). Failure → exit 3 +
    PTY_RECOVERY_FAILED.
    v2: replaced v1's "no preamble attributable to the second command" —
    console text cannot be turn-attributed; occurrence counting is the
    same guarantee, mechanically checkable.
KILL-CHECK: battery stubs reproduce both oracles against the stub fa
  (S17 env: version-line stub passes, "command not found" stub exits 3 with
  the flag; S18 pty: 1-preamble stub passes, 3-preamble stub exits 3);
  removing an oracle branch fails the battery
```

## 3. Path / edge / matrix inventory

| P# | Trigger | Target behavior | S# | T# |
|---|---|---|---|---|
| P1 | managed workspace, .venv present | PATH prepended, all 3 backends | S12.1 | T1 |
| P2 | raw clone, no .venv | env byte-identical to today | S12.1 | T1e |
| P3 | readiness degraded | no announcement; stderr WARN unchanged | S12.2 | T2b |
| P4 | command times out, pane busy | C-c + sentinel ≤5 s; partial returned | S12.3 | T3a/T3b |
| P5 | timed-out command ignores SIGINT | `_wait_for_sentinel` TimeoutError CAUGHT; clean timeout result still returned; next call may re-timeout once (documented, no loop) | S12.3 | T3c |
| P6 | heredoc command times out | script cleanup still runs | S12.3 | T3d |
| P7 | subagent (stateless) bash | same PATH prepend via subprocess fallback | S12.1 | T1s |
| M1–M6 | flag matrix per CT4 | per table | S12.4 | T4 |
| P8 | CHORE draft with free-form invariant | accepted at all three calling seats | S12.5 | T5a |
| P9 | FIX draft, wrong invariant prefix | still rejected (no over-relaxation) | S12.5 | T5b |
| P10 | existing `n/a` drafts | still valid | S12.5 | T5d (snapshot suite green) |
| P11 | live: env row on healthy stack | PASS oracle per CT6 (6-turn cap, ceremony tolerated) | S12.6 | LT1 + S17 |
| P12 | live: pty row | PASS oracle per CT6 (preamble count ≤1) | S12.6 | LT2 + S18 |
| P13 | live: env row, readiness BROKEN (venv removed) | exit 3 + ENV_PROBE_FAILED, never a silent pass | S12.6 | S17b |

Explicit non-goal paths: LoopGuard interplay (D10), tier re-classification
(D12), provider 429 behavior (D14 — chain failover already observable in
timeline v2).

## 4. Artifacts inventory

| A# | Path | Action | Owner S# |
|---|---|---|---|
| A1 | src/fa/runtime/pty_pool.py | modify (PATH setup clause; timeout hygiene; partial accumulation) | S12.1, S12.3 |
| A2 | src/fa/inner_loop/tools/run_bash.py | modify (subprocess env PATH prepend — covers main-agent fallback AND subagents; the dead src/fa/inner_loop/run_bash.py is NOT touched) | S12.1 |
| A3 | src/fa/cli.py | modify (announcement; IntentGuard mode plumbing) | S12.2, S12.4 |
| A4 | src/fa/feature_flags.py | modify (intent_guard_mode field, _KNOWN_FLAGS, FAIL_CLOSED, as_dict) | S12.4 |
| A5 | src/fa/inner_loop/hooks/intent_guard.py | modify (mode-aware handle) | S12.4 |
| A6 | src/fa/hygiene/pr_intent.py | modify (empty-tuple semantics; table) | S12.5 |
| A7 | src/fa/inner_loop/tools/prepare_pr.py | modify (validator semantics; schema descriptions) | S12.5 |
| A8 | knowledge/skills/pr-creation/SKILL.md | modify (CHORE/RESEARCH invariant rows) | S12.5 |
| A9 | knowledge/templates/config.yaml.example | modify (intent_guard.mode documented) | S12.4 |
| A10 | tests/test_pty_pool_narrowing.py, test_pty_persistence.py, test_pty_tmux_fake.py | modify/extend | S12.1, S12.3 |
| A10b | tests/test_s13_fail_closed_open.py, tests/test_s10b_cli_parity.py | extend/regression-gate (new flag categorized; default stack unchanged) | S12.4 |
| A11 | tests/test_run_bash_env_scrub.py (+ NEW test_venv_path_wiring.py) | extend/new | S12.1 |
| A12 | tests/test_intent_guard.py | extend (mode matrix) | S12.4 |
| A13 | NEW tests/test_feature_flags_intent_guard_mode.py (or extend existing feature-flag test) | new | S12.4 |
| A14 | tests/test_prepare_pr.py, test_pr_intent_snapshot.py | extend (relaxation + guardrails) | S12.5 |
| A15 | NEW tests/test_readiness_announcement.py | new | S12.2 |
| A16 | scripts/run_live_check.sh | modify (env, pty rows; setup flags; l1 ceremony) | S12.6 |
| A17 | scripts/adversarial_battery_live_check.sh | modify (S17, S18) | S12.6 |
| A18 | tests/test_live_check_script.py | modify (pins) | S12.6 |
| A19 | worklogs/reviews/S10-LIVE-VERIFICATION-rev4.md | modify (rows, triage) | S12.6 |
| A20 | worklogs/BACKLOG.md | modify (deferred entries, see §5 S12.6) | S12.6 |

## 5. Step-by-step implementation (edit packets)

**S12.1 — venv PATH wiring (CT1).**
(a) pty_pool.py tmux init: extend `setup_cmd` (:186) with
`[ -d .venv/bin ] && export PATH="$PWD/.venv/bin:$PATH"` — relative to the
pane's start_directory (session cwd), so per-session venvs never cross-wire.
(b) pexpect fallback (:134): compute prepend from `self.cwd` before spawn.
(c) tools/run_bash.py `_run_subprocess_fallback` only: after
`build_scrubbed_env`, if `(root/".venv"/"bin").is_dir()` prepend to
`env["PATH"]`. This one site covers the main-agent fallback AND subagents
(executor=None reaches the same function, tools/run_bash.py:331-339).
src/fa/inner_loop/run_bash.py is DEAD (zero src importers, absolute +
relative) and stays untouched.
Gates: T1 family; ruff; existing pty suites green.

**S12.2 — readiness announcement + guidance line (CT2, includes F4c).**
cli.py run path: when the prepared workspace ReadyState is READY, append to
`system_prompt_extra` (static per run — D7-compliant):
"Workspace ready: project venv at ./.venv (tests: `uv run pytest …`).
Before the first workspace mutation, call `pr_prepare` (CHORE for chores)."
Exact wording pinned by T2. Gates: T2a/T2b.

**S12.3 — PtyPool timeout hygiene (CT3).**
_run_tmux: accumulate `output` each poll iteration (last clean snapshot after
the start token); timeout branch: `send_keys("C-c")` then
`_wait_for_sentinel(timeout=5)` WRAPPED in try/except TimeoutError (the
helper RAISES on expiry, pty_pool.py:219 — P5); keep `timed_out=True`;
partial text prefixed with the existing marker (branch at :424 goes live).
_cleanup_script call order unchanged. _run_fallback: `sendcontrol("c")`
parity on pexpect TIMEOUT. Gates: T3a–T3d on fake tmux.

**S12.4 — intent_guard_mode (CT4).**
feature_flags.py: field + dual-spelling keys + FAIL_CLOSED membership +
as_dict; intent_guard.py: constructor `mode: str = "enforce"`, handle()
observe branch (log via existing sink, return allow); cli.py: read flag,
skip registration when off, pass mode otherwise; config.yaml.example row.
Gates: T4 matrix + tests/test_s13_fail_closed_open.py green (new field
categorized FAIL_CLOSED, default restrictive) + test_s10b_cli_parity green
(default enforce keeps the registered stack identical).

**S12.5 — CHORE relaxation + schema docs (CT5).**
pr_intent.py: `Intent.CHORE: ()` (+ `Intent.RESEARCH: ()` per Q9 default);
Check 3: `if required and not any(...)` — empty tuple skips shape check at
BOTH seats. prepare_pr.py: `_validate_invariant_prefix` same semantics;
`_INPUT_SCHEMA["invariant"]["description"]` documents per-intent prefixes.
SKILL.md rows 101/105 updated. Gates: T5a–T5d; snapshot suite green.

**S12.6 — live verification + backlog bookkeeping (CT6).**
Runner: `cmd_env` (6-turn cap — enforce-mode ceremony headroom), `cmd_pty`
(6-turn cap), setup flag printout
(parse `$STATE_HOST/config.yaml` feature_flags; print defaults when absent),
l1 ceremony note from events (denial count). Battery: S17/S18 stubs with
format-faithful events. Pins: dispatch surface {…,env,pty}, oracles anchored,
flag-printout present. Sheet: §2/§4/§6 rows + triage lines.
BACKLOG.md entries (I-# with unblock-triggers): D10 LoopGuard truncated-read
thrash; D17 read-only-bash exemption (trigger: IntentGuard refactor);
IntentGuard refactor (trigger: post-live-trial review); D12 unknown-prefix
tier default (trigger: S11 unpaused); verify_failed evidence quality
(trigger: S11 unpaused); D13 /tmp write friction; D14 qwen 429 (provider
capacity — operational, not code); ACRR historical backfill (trigger: S11);
bash timeout double-execution / no-retry-on-timeout (trigger: PtyPool
reliability follow-up, surfaced by RK7).

Slice order: S12.1 → S12.3 (same file, one PR-friendly sequence) → S12.2 →
S12.4 → S12.5 → S12.6. Each slice independently revertable.

## 6. Verification plan

| T# | Kind | Asserts | Kill-check target |
|---|---|---|---|
| T1/T1e/T1s | unit | PATH order with/without .venv, all three backends | CT1 |
| T2/T2b | unit (drive-level) | announcement present iff READY; guidance line wording | CT2 |
| T3a | unit (fake tmux) | timeout returns accumulated partial output (the :424 branch executes — kill-check: it is dead code today) | CT3 |
| T3b | unit (fake tmux) | command AFTER a timeout completes normally (pane was cleaned; kill-check for interrupt-on-timeout) | CT3 |
| T3c | unit (fake tmux) | SIGINT-resistant command: sentinel wait raises TimeoutError internally, caller still gets a clean timed_out result (no exception escapes) | CT3/P5 |
| T3d | unit | heredoc temp script cleaned up on the timeout path too | CT3/P6 |
| T4/T4b | unit (matrix M1–M6) | mode semantics + hook_decision emission + fail-closed | CT4 |
| T5a | unit | free-form CHORE invariant accepted at ALL THREE seats: pr_prepare handler, validate_commit_msg, IntentGuard.handle (v2: guard seat added) | CT5 |
| T5b | unit | FIX "Affects:" / IMPLEMENT "Implements:" / ADR_RULE "Contract:" still enforced — over-relaxation kill-check | CT5 |
| T5c | unit | pr_prepare input schema documents the per-intent prefix table | CT5 |
| T5d | snapshot | existing `n/a` drafts stay valid; pr_intent snapshot suite green | CT5 |
| T6 | pins | live-check contract pins updated (dispatch, oracles, printout) | CT6 |
| S17/S18 | battery | env/pty oracles against stub fa | CT6 |
| LT1 | LIVE | host `env` row PASS after `fa update` | G1 |
| LT2 | LIVE | host `pty` row PASS | G2 |
| LT3 | LIVE | l1 with `intent_guard.mode: observe` set in $STATE_HOST/config.yaml: fa rc=0, transcript contains no guard-denied tool result, events.jsonl contains ≥1 hook_decision with `would-deny(observe)` when a mutation is attempted | G3 |
| LT4 | LIVE | l2 re-run (enforce mode): timeline shows an fs_edit_file ATTEMPT (edit phase reached); transcript contains none of `find / -name`, `which python`, `command not found`, `No module named pytest`; IntentGuard denials ≤1. v2: a LoopGuard `✗` on the edit is recorded as the known-deferred D10 and does NOT fail LT4 — the row's purpose here is proving the environment handoff, not re-litigating D10 | G1+G4 |

Repo gates per slice: `just check`-equivalent subsets locally (ruff, mypy
strict on touched files, targeted pytest). The two doc-gate reds stay red
(standing instruction); S12 adds no new doc-link breakage (SKILL.md edit
keeps existing link shapes).

## 7. Risks, rollback, open questions

| RK# | Risk | Mitigation |
|---|---|---|
| RK1 | PATH prepend shadows a system tool the model relied on | only `.venv/bin` prepended and only when present; live `env` row + l2 re-run detect regressions |
| RK2 | C-c kills a legitimate long job the model wanted alive | models are told timeouts are enforced (existing tool docs); background tools exist (fs_run_bash_background); behavior matches operator Ctrl-C semantics |
| RK3 | observe/off left on in production after trials | FAIL_CLOSED default; setup printout; ledger notes record mode; config template documents enforce as default |
| RK4 | announcement churns prompt-cache keys | content static per run (no paths that vary within a run); measured via existing cache_hit_ratio in session_summary |
| RK5 | SKILL.md drift vs validator | single table is the source; T5a covers all three calling seats; doc rows edited in the same slice |
| RK6 | engine rollout gap (container runs image code) | deploy step is part of DoD: land on main → update /srv mirror → `fa update` → verify `smoke` before LT rows |
| RK7 | timeout double-execution: pty timeout → subprocess fallback RE-RUNS the same command (non-idempotent commands execute twice) | PRE-EXISTING (tools/run_bash.py:208-210 → :339), NOT introduced by S12 and deliberately out of scope; CT3 reduces its blast radius (clean pane after timeout). Documented so the review record shows it was seen, not missed; a proper fix (idempotency token or no-retry on timeout) is a separate BACKLOG entry |

**Rollback.** S12.4 revertable at runtime via config (mode=enforce). All
other slices revert as single commits; sheet rows are additive (removable
without engine impact). No migrations, no data changes.

**Open questions.**

- Q9 (non-blocking, default YES): extend the invariant relaxation to RESEARCH
  (same degenerate `n/a` shape). Default applied in this plan; operator may
  veto → S12.5 keeps `Intent.RESEARCH: ("n/a",)`.
- Q10 (non-blocking, default): config key spelled `intent_guard.mode` with
  `intent_guard_mode` alias, mirroring `worktree.mode`.
- Resolved 2026-08-31 (operator): Q1 mode-3 default enforce; Q2 drop CHORE
  shape check, no auto-fill ("overkill"); Q3 both D15 halves; Q4 both live
  rows.

## 8. Research-note / claim disposition

- **RN1 REJECTED:** "parallel tool dispatch is not flag-gated" (earlier this
  session) — `tool_batching_enabled` gates it at loop.py:548-560, default
  True fail-open. Corrected on record; no S12 impact (default already on).
- **RN2 REJECTED:** "workspace readiness announces itself" — prints only on
  degradation (cli.py:145-149). Basis of GAP1.
- **RN3 REWRITTEN:** "D16 = pane bricked by orphaned command" — mechanism
  verified as *absence of interrupt on timeout* (code) + transcript
  consistent (every post-timeout call timed out, including trivial ones).
  T3b makes the mechanism testable rather than inferred.
- **RN4 ACCEPTED:** readiness venv provisioning works (live-proven
  2026-08-31: session venv existed; `uv run pytest` collected 145 items).
- **RN5 DEFERRED:** verify_failed evidence quality (env failure escalated
  l2 to L3) — S11 calibration input, BACKLOG entry.
- **RN6 REJECTED (v2 self-review):** "ReadyState reaches the drive site" —
  the preparer's return value is discarded at manager.py:294-295/350-351;
  CT2 rewritten to a local venv-exists predicate.
- **RN7 REJECTED (v2 self-review):** "invariant shape has two enforcement
  seats" — IntentGuard is a third calling seat via validate_commit_msg
  (intent_guard.py:298); CT5/T5a corrected to three seats, two code paths.
- **RN8 REJECTED (v2 self-review):** "the stateless builder in
  inner_loop/run_bash.py is a live insertion point" — module is dead in src
  (zero importers); removed from scope, single insertion in tools/run_bash.py.

## 9. Definition of Done / READY gate evidence

1. All T# green in pr63 worktree; battery green; ruff/mypy clean on touched
   files; two doc-gate reds unchanged (still exactly those two).
2. Patch series delivered against fetched remote main tip (modification
   diffs; verified clean-apply + byte-identical in a fresh clone, per the
   established patch discipline).
3. Host deploy: main updated → /srv mirror → `fa update` → `smoke` PASS.
4. LIVE proofs, each binary per its §6 oracle: LT1 (env row PASS), LT2 (pty
   row PASS, preamble count ≤1), LT3 (l1 under `intent_guard.mode: observe`
   — no denied tool results, ≥1 `would-deny(observe)` hook_decision when a
   mutation is attempted), LT4 (l2 re-run — edit ATTEMPT present, zero
   environment-archaeology strings, IntentGuard denials ≤1; a LoopGuard
   denial is recorded as deferred-D10, not an LT4 failure). All recorded in
   the ledger with stop reasons.
5. BACKLOG.md carries the deferred items with unblock-triggers; ADR-16
   untouched; S11 remains paused.
6. Sheet rev4 documents the new rows, the flag printout, and the S12 triage
   table.

READY gate: no blocking Q# (Q9/Q10 non-blocking with defaults); all symbols
cited above verified by read/grep this session or marked NEW.
