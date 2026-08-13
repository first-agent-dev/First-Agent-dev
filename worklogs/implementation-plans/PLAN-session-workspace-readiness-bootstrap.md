# PLAN: Managed session workspace provisioning and readiness

Plan-ID: `PLAN-session-workspace-readiness-bootstrap`

Status: **READY v23 — S1–S8 complete; S9 external proof is next**

Depth: **P3** — changes the accepted workspace-isolation implementation,
Git remote security boundary, container/session lifecycle wiring, local Git
hooks, mutation-gate TCB, host developer bootstrap, and deployment verification.

Revision: **v23 — S8 documentation contract complete**

Changed-since-v22: ADR-13, digest, README, operations, FEATURES, runtime template,
and four historical records now match the implemented transport, persistent
selector, B2 routing, readiness, session DB authority, and measured cache model.
T15 has deterministic current/historical/secret-template authority; all 12 docs
are Markdown/link clean. S8 is complete. G8's external publication/deployment
claim remains S9/T16 owned.

Changed-since-v14: S6 now defines `~/First-Agent-dev` as the operator development
clone, `/srv/first-agent/repo/First-Agent-dev` as the clean deployment mirror,
and managed session workspaces as lifecycle-prepared clones. Agent-owned
bootstrap, frozen/old-marker/deleted-recipe prose is removed; one pinned uvx
command and missing-uv recovery are documented. T13 static/live authority passes,
VS Code remains byte-unchanged convenience, and mandatory S6.5 is next.

Changed-since-v13: adds mandatory S6.5 before S7. The new slice re-verifies
S1–S6 intent-to-module translation against actual roots, records a per-claim
production review ledger, repairs only reproduced defects, and requires a clean
candidate to pass real hook/commit and repository gates. Preflight confirmed
three gaps: readiness children inherit hook stdin, current full type gates block
a real commit, and CODEOWNERS parity authority is false-red. S6's static tests
are corrected to the alias suite so core readiness C4 remains isolated.

Changed-since-v12: S5 is implemented through identical four-seat readiness preludes, narrow bootstrap-only fail-open mapping, network-free normal gates, retained argument/stdin behavior, and explicit T9–T12 producer kill-checks. Live missing-venv repair, tool-missing degradation, installed-seat fast path, and normal quality-failure blocking all pass. S6 is next.

Changed-since-v11: S4 is implemented through read-only CT3 checking, the
checked-out stdlib wrapper, bounded host adapter, converged just aliases, old
marker deletion, and separated alias C1 tests. Live install/check/doctor/agent
aliases converge on one fingerprint; C4 closes with only five prior equivalents.
S5 is next.

Changed-since-v10: S4 preflight found that `doctor` cannot prove CT4 readiness
from hook status alone and that host bootstrap subprocess failure/timeout policy
was incomplete. CT3 now includes a non-mutating `check_workspace_ready`/`check`
CLI projection reusing fast-readiness authority; S4 also requires bounded host
commands and structured return codes. No new product policy is introduced.

Changed-since-v9: S3.5 is implemented across the isolated runner, targeted
selector, bounded Git discovery, permanent mutation/type/gremlins config,
weekly workflow, tests, and TCB governance. Twenty S3.5 authority tests, 382
permanent selected tests, changed-file static gates, exact readiness C4 evidence,
and four producer-removal checks pass. Repository-wide results retain three
classified non-S3/worktree-baseline failures. S4 is next.

Changed-since-v8: implementation gates are green and the explicit readiness C4
run exactly reproduced `874 = 329 killed + 540 type-invalid + 5 equivalent`.
A configured-scope probe correctly failed as infrastructure after 1,500 seconds
while still generating mutants and left no stage residue. The weekly consumer
now passes 18,000 seconds (five hours), below GitHub's six-hour job ceiling while
retaining one hour for setup/reporting. Full configured completion remains the
advisory workflow's authority.

Changed-since-v7: the S3.5 review closed six executable-plan defects without a
new policy choice: exact mutmut 3.6.0 compatibility, overlap rejection,
non-POSIX preflight, bounded/NUL-safe/error-checked Git discovery, valid Pyrefly
nonzero diagnostic semantics, and weekly `uv sync --locked`. Contracts, tests,
and edit packets now make each correction binary and kill-checkable.

Changed-since-v6: the operator approved a bounded S3.5 before S4: add an
isolated explicit-slice mutation runner, enable scoped type-invalid mutant
filtering, and permanently include the readiness engine in Linux mutmut and
Windows pytest-gremlins scope. Source probes found that locked mutmut 3.6.0
returns zero with survivors, omits type-filtered counts from its CI export, and
that the existing targeted wrapper mutates test files, ignores working-tree and
untracked files, rewrites the real `pyproject.toml`, and sets an ineffective
timeout environment variable. S3.5 replaces those unsafe authorities without
changing the existing skills, equivalent-mutant policy, or advisory weekly-CI
policy. S4 remains unimplemented.

Changed-since-v5: S3 is implemented through the readiness engine, hook-source
seam, manager/CLI lifecycle producers, and entrypoint producer. Final hardening
closed state-path symlink escape, cache/marker mode trust, unbounded hook-path
Git lookup, and repeated telemetry policy. Behavioral/static gates, targeted
mutation classification, and producer-removal checks pass. S4 remains
unimplemented.

Changed-since-v4: S2 is implemented through the entrypoint and post-setup
consumers. Final review fixed custom-remote admission when source publication
authority is unusable and closed query/assignment credential leakage in Git
error diagnostics. Behavioral/static gates, targeted mutation classification,
and shell producer-removal checks pass. S3 remains unimplemented.

Changed-since-v3: S1 is implemented and slice-specific gates pass. Q5 resolved
preserved unsafe custom push URLs as non-mutated Git config plus the stable
`<preserved-custom-redacted>` result sentinel and generic warning; S2 admission
continues without credential disclosure.

Changed-since-v2: adversarial source/caller/test review found and corrected
twelve executable-plan defects: clean-clone Git identity, missing push-URL
composition-root wiring, undefined provisioner-error mapping, Git-invalid branch
names admitted by the session-id regex, an unsafe live-source HEAD comparison,
a contradictory fake-remote test, premature S1 repair scope, fallback rollback
test ownership, an unresolved S3 lifecycle-injection choice, and open-ended
S8/S9 file authority, the missed hook-installer package wrapper, and an
under-specified/contradictory readiness result/timeout contract. S1 now has
closed data/error/ordering/test contracts. No production code was edited by this
review.

Baselines:

```text
plan/source main     = ac5ba1adc7fa7ff24ec77134f56d8eb87676f317
live deployment HEAD = eb2c03c15adab72569cac400027add09ce8dce6f
active workspace HEAD= eb2c03c15adab72569cac400027add09ce8dce6f
```

Upstream context:

- operator intent recorded in the planning conversation, 2026-08-12;
- [`ADR-13`](../../knowledge/adr/ADR-13-workspace-isolation.md);
- [`ADR-10` I-2](../../knowledge/adr/ADR-10-deterministic-harness-invariants.md#i-2--numbered-mandatory-workflows-are-a-bucket-residue);
- [`project-overview.md` §1.2.5](../../knowledge/project-overview.md#125--compliance-by-construction-failure-observable);
- first and second prior-agent reviews, dispositioned in §8 rather than treated
  as authority.

---

## Preflight log

### Roots checked

- Host deployment/install:
  - `scripts/setup-fa-desktop.sh`
  - `scripts/fa-post-setup.sh`
  - `scripts/fa-update.sh`
  - `scripts/fa`
  - `scripts/bootstrap/host_bootstrap.py`
  - `.vscode/tasks.json`
- Container/session:
  - `docker-compose.fa.yml`
  - `Dockerfile.fa`
  - `scripts/fa-entrypoint.sh`
  - `src/fa/cli.py:_session_manager_for_args`
  - `src/fa/cli.py:_resolve_cli_run_context`
  - `src/fa/session/manager.py:SessionManager`
- Hook/readiness:
  - `justfile:doctor/install/agent-bootstrap/_install-hooks`
  - `src/fa/hygiene/hooks/install.py`
  - `src/fa/hygiene/hooks/status.py`
  - all four hook source scripts
  - `.pre-commit-config.yaml`
- Canonical docs:
  - `AGENTS.md`
  - `knowledge/project-overview.md`
  - `knowledge/llms.txt`
  - `worklogs/HANDOFF.md`
  - `knowledge/adr/DIGEST.md`
  - `knowledge/reference.md`
  - `knowledge/instructions/01-install.md`
  - `knowledge/instructions/02-operations.md`
  - `worklogs/DEPLOYMENT-ANATOMY.md`
  - `knowledge/anti-patterns/AP-004-symptom-chasing-without-model.md`

### Greps/probes and findings

1. `git clone file:///repo` appears in `scripts/fa-entrypoint.sh:170`.
   `git remote set-url --push` is absent from all production scripts.
2. A controlled Git probe confirmed that `git clone file://<source>` sets the
   clone's `origin` to the local `file://` URL, not to the source repository's
   upstream remote.
3. `SessionManager._provision_workspace()` uses
   `shutil.copytree(source_workspace, workspace_path, symlinks=True)` with no
   ignore filter.
4. A controlled production-module probe confirmed that raw manager provisioning
   copies `.venv`, `.git/hooks`, and untracked files.
5. A controlled Git-source probe confirmed that manager provisioning preserves
   branch `main`, copies ignored `.env.fa`, and copies source Git config.
6. `fa run`/`fa workflow` with no `--session-id` intentionally creates a new
   persistent logical session. Explicit `--session-id` attaches. This accepted
   S2 selector model is preserved; the earlier proposal to collapse all runs
   onto the entrypoint workspace is rejected.
7. `/srv/first-agent/repo/First-Agent-dev` is the physical deployment clone.
   `/repo` is its read-only bind view. `/srv/first-agent/sessions` and container
   `/sessions` are two views of the same RW bind-mounted host storage.
8. `~/First-Agent-dev` is a separate optional clone from install Phase 4 Option
   A. Operator decision promotes it to canonical VS Code SSH development clone;
   it is not the deployment mirror.
9. The `ac5ba1a` patch makes the four tracked hook source scripts executable,
   but a fresh clone still has no custom `.git/hooks/*` seats.
10. Current `just install` prewarms pre-commit environments before installing
    custom hook wrappers. The proposed bootstrap must preserve that behavior.
11. `/tmp/uv-cache` and `/home/fa/.cache` are tmpfs. A persistent workspace
    marker can survive while the pre-commit cache disappears on container
    restart.
12. `file:///repo` uses Git pack transport, not hardlinks. ADR-13, README, and
    multiple operational docs still claim `git clone --local`/near-zero
    hardlink overhead. `AP-004` records the later transport correction.
13. `fa-post-setup.sh` computes an SSH URL for `git ls-remote`, then performs
    `git push origin`; it does not install a pushurl. Connectivity and push
    therefore test different destinations.
14. Existing entrypoint tests prove clone/cwd separately, but no C2 test proves
    the complete producer chain:

    ```text
    session clone → B2 remote → ready env/hooks → first commit/push
    ```

15. Existing manager tests use non-Git source fixtures and therefore cannot
    detect copied Git branch/remotes/ignored-file behavior.
16. Probe v1 was reviewed before operator use and found unsafe/inaccurate edges:
    missing `.active` under `pipefail`, optional Git index refresh, potential
    fsmonitor command execution, Python import from agent-writable CWD, unredacted
    remote userinfo, and terminal-control text from manifests. The corrected
    probe closes those paths before S0.

### Gold patterns mirrored

- `src/fa/session/manager.py:_atomic_write_json` — temp + fsync + replace marker
  writes.
- `scripts/fa-update.sh` — process-wide `flock`, explicit re-exec ownership,
  source-verified diagnostics.
- `src/fa/hygiene/hooks/_util.py:resolve_hooks_dir` — effective Git hook path,
  including worktrees and `core.hooksPath`.
- `tests/test_hygiene_hooks_install.py` — fake executables in PATH, hook seat
  content/mode checks, failure-code preservation.
- `tests/test_fa_entrypoint.py` — real temporary Git repositories and controlled
  shell-entrypoint execution.
- `tests/test_session_lifecycle.py` — session rollback/ownership/manifest
  assertions.
- `PLAN-cli-trace-S2-session-manager-and-authority.md` — identity and authority
  planning shape.

### Conflicts/invariants

- ADR-13's read-only deployment mirror remains binding.
- The later S2 selector model supersedes ADR-13's older sentence equating one
  container lifecycle with exactly one logical session. This plan amends docs;
  it does not revert the S2 model.
- `git clone --local /repo` is forbidden by AP-004 absent new evidence; it failed
  on ownership/cross-device boundaries.
- Local hooks are best-effort because the operator selected warn-only bootstrap
  failure. GitHub CI + branch permissions + human merge remain authoritative.
- LLM bootstrap instructions are orchestration residue under ADR-10 I-2 and must
  be removed only after production wiring is live.
- No LLM/provider key may enter bootstrap logs or marker files.

### Current liveness

| Signal/capability | Current liveness | Evidence |
| --- | ---: | --- |
| Entrypoint local clone | L3 | shell tests prove clone/cwd; deployed path historically exercised |
| B2 fetch-local/push-remote | L0 | no pushurl producer exists |
| Manager clean Git session clone | L0 | production uses raw copytree |
| Four tracked hook sources | L2 | source exists/executable; fresh-clone seats absent |
| Managed workspace readiness before LLM | L0 | no lifecycle call site |
| Host dev bootstrap | L2 | VS Code/alias exists but permission/manual invocation remains |
| Cold/warm cache cost evidence | L0 | no measured baseline for this feature |
| GitHub CI/human merge authority | external accepted boundary | unchanged by this plan |
| Explicit slice mutation runner | L0 | no safe explicit source/test runner exists |
| Targeted mutation verdict | L2, false authority | wrapper is invoked, but raw mutmut rc cannot report survivors |
| Type-invalid mutant filter | L0 | `[tool.mutmut]` has no `type_check_command` |
| Readiness in permanent mutation scope | L0 | source/test absent from mutmut and gremlins lists |

### S3.5 planning preflight — 2026-08-13

#### S3.5 roots checked

- Mutation entrypoints and configuration:
  - `scripts/run_targeted_mutmut.py`
  - `scripts/_git_diff.py`
  - `scripts/mutation_sweep.py`
  - `pyproject.toml:[tool.mutmut]`
  - `pyproject.toml:[tool.pytest-gremlins]`
  - `justfile:check-deep/_targeted-mutmut`
  - `.github/workflows/tests.yml`
- Mutation tests/governance:
  - `tests/test_targeted_gates_smoke.py`
  - `.github/CODEOWNERS`
  - `scripts/check_protected_paths.py`
- Readiness authority:
  - `src/fa/workspace_bootstrap.py`
  - `tests/test_workspace_bootstrap.py`
  - the retained S3 mutation result/log artifacts named in the execution record
- Exact installed-tool authority:
  - `uv.lock` (`mutmut==3.6.0`, `pyrefly==1.1.1`, `mypy==2.1.0`)
  - extracted mutmut 3.6.0 source: `configuration.py`, `type_checking.py`,
    `mutation/file_mutation.py`, and `__main__.py`
  - official mutmut configuration/architecture documentation

#### Source findings and reproducible probes

1. `scripts/run_targeted_mutmut.py:47-93` parses and regex-rewrites the real
   `pyproject.toml`; restoration is best-effort after mutation rather than
   unnecessary by construction.
2. `scripts/_git_diff.py:139-145` asks only for `base...HEAD`, so the current
   wrapper does not see unstaged, staged-but-uncommitted, or untracked files.
3. `scripts/run_targeted_mutmut.py:60-68` admits both configured production
   roots and every `tests/` path, then writes all admitted paths into
   `source_paths`; a changed test can therefore be mutated as production source
   instead of remaining an oracle.
4. `scripts/run_targeted_mutmut.py:151-155` exports
   `MUTANT_TIMEOUT_SECONDS=600`, but exact mutmut 3.6.0 source has no consumer
   for that variable. Mutmut uses configured per-mutant multiplier/constant
   limits; the parent wrapper currently has no wall-clock/process-group bound.
5. Exact mutmut 3.6.0 source shows `run()` returns normally after printing
   results. A controlled fixture produced two survivors with `run_rc=0`.
   Therefore the wrapper's “real survivor findings exit non-zero” claim is
   false and `just check-deep` can be green with survivors.
6. `export-cicd-stats` omits both `caught_by_type_check` and `not_checked` even
   though those statuses exist in mutmut's internal result model. A controlled
   fixture exported `total=3, survived=2` while `mutmut results` additionally
   listed one `caught by type check` mutant.
7. Mypy 2.1 with `--output json` emits one blank line on a clean result. Mutmut
   3.6.0 attempts `json.loads("")` for that line and aborts. It is not a usable
   permanent filter without a compatibility adapter, which would be avoidable
   mechanism.
8. Repository-wide Pyrefly has the two already-classified non-S3 errors, but the
   exact permanent mutmut source list plus `src/fa/workspace_bootstrap.py`
   returns valid `{"errors":[]}` with rc 0. Scoped Pyrefly is therefore the
   minimal working type-filter authority.
9. An isolated root-backed readiness run with the proposed scoped Pyrefly
   command produced the closed identity:

   ```text
   total              = 874
   killed by tests    = 329
   caught by typecheck= 540
   survived           = 5
   other statuses     = 0
   raw mutmut run rc  = 0
   ```

   The five survivors are the previously classified equivalent
   `x__open_private__mutmut_7`, `x__read_python_minor__mutmut_7/8`, and
   `x__hooks_current__mutmut_12/13`. The former three downstream-normalization
   equivalents became type-invalid; no new survivor appeared.
10. Current permanent configuration ends at `src/fa/stats.py` and does not list
    the readiness source/test. `[tool.pytest-gremlins].paths` claims to mirror
    mutmut but also omits readiness.
11. `also_copy` must include `src/fa` for sibling imports. The S3 direct probe
    reproduced `ModuleNotFoundError: fa.hygiene` without it. S4 keeps alias/config
    C1 tests outside this core C4 seat per D24.
12. `.fa/*` and repository `mutants/` are already ignored. A root-backed
    per-invocation staging directory can be deleted after artifact extraction;
    S3.5 does not need a new persistent cache or ignore rule.

#### Confirmed S3.5 plan defects corrected in v8

**D13 — mutmut compatibility was broader than the parser.** CT10 parsed the
locked 3.6 result/export shape but accepted any 3.x executable. Require exact
`mutmut, version 3.6.0`; a lock/tool mismatch is infrastructure failure.

**D14 — overlapping source/test selections could duplicate identity.** Reject
exact duplicates and ancestor/descendant overlap inside source and test roles.
`also_copy` may overlap source intentionally because `src/fa` supplies imports.

**D15 — unsupported native Windows execution was implicit.** Mutmut 3 requires
fork. Explicit runner/configured modes reject non-POSIX before staging with an
actionable pytest-gremlins diagnostic; gremlins parity remains CT12 authority.

**D16 — Git selection remained unbounded and partial-output tolerant.** Add a
30-second timeout to every merge-base/diff/ls-files call, use `-z` bytes, and
fail open with a diagnostic on every nonzero/timeout before accepting output.

**D17 — Pyrefly failure semantics conflated diagnostics with failure.** Pyrefly
returns nonzero for valid mutant type errors. Valid JSON diagnostics continue;
malformed/missing JSON, launch failure, or errors that mutmut cannot map to a
mutated function are infrastructure failure.

**D18 — the touched weekly workflow retained stale lock semantics.** Replace
`uv sync --frozen --extra dev` with accepted `uv sync --locked --extra dev` and
pin it in T20; no lock rewrite is allowed.

**D19 — explicit-slice timeout was too narrow for weekly configured scope.** A
1,500-second configured probe remained in mutant generation when CT10 correctly
terminated it. Keep the one-hour explicit default, but pass 18,000 seconds from
the weekly workflow—below GitHub's six-hour ceiling with reporting headroom.

#### S3.5 gold patterns mirrored

- `scripts/mutation_sweep.py:_scratch_root/_require_space` — root-backed staging,
  preflighted capacity, and explicit harness-failure classification.
- `scripts/mutation_sweep.py:_classify` — never count collection/harness failure
  as mutation success.
- `scripts/_git_diff.py` — list-form subprocess arguments and contained,
  repository-relative path normalization.
- `tests/test_targeted_gates_smoke.py` — shipped-script subprocess and AST
  authority; S3.5 adds behavioral oracles rather than replacing it with mocks.
- `src/fa/session/manager.py:_atomic_write_json` — write-temp/fsync/replace shape
  for completed result artifacts.

#### S3.5 conflicts and invariants

- Tests are immutable oracles for a run; they must never enter `source_paths`.
- Explicit slice mode is strict. Type-invalid mutants are a separate accepted
  category; survivors/no-tests/timeout/suspicious/skipped/interrupted/segfault/
  not-checked are not success.
- Known equivalent survivors are not silently allowlisted. The five current
  readiness equivalents intentionally yield exit 1 and require human review;
  `FA_SKIP_TARGETED_MUTATION=1` remains the explicit operator override after
  review.
- Targeted discovery may retain its existing fail-open behavior before a run
  starts (tool missing, Git unavailable, oversized diff, explicit skip). Once
  mutmut starts, harness/config/result failure is blocking and observable.
- Weekly mutation remains advisory through the existing job-level
  `continue-on-error: true`; S3.5 improves scope and evidence but does not change
  merge policy.
- Mutmut and pytest-gremlins stay complementary. Type-invalid filtering applies
  to Linux mutmut only; gremlins remains the native-Windows operator mirror.
- Existing skills are inputs, not edit targets. No S3.5 task modifies
  `feature-planning`, `tests-writing`, or `mutation-clearing`.
- No `mutate_only_covered_lines`, equivalent-mutant ledger, source pragma,
  blanket baseline, dependency, or whole-`src` scope is added in S3.5.

### Adversarial v3 review disposition

This review treated READY v2 as a candidate to break, not as authority. Findings
below are grounded in the current production tree at baseline `ac5ba1a`; line
numbers therefore refer to that baseline, not to this plan's moving line numbers.

#### Confirmed defects corrected in v3

**D1 — clean-clone identity was missing.**

- Evidence: `scripts/fa-post-setup.sh:258-261` writes `user.name` and
  `user.email` only to the startup `.active` workspace;
  `Dockerfile.fa:42-46` writes only `safe.directory`; and
  `src/fa/sandbox/validators.py:242-282` denies agent-issued identity rewrites.
- Defect: a clean manager clone cannot make its first commit without a denied
  LLM action or test-only identity.
- Correction: CT1/S1 install trusted repository-local
  `First Agent <agent@first-agent.local>` identity. T1 makes a real commit with
  no identity environment.

**D2 — the push-URL override had no composition-root wiring.**

- Evidence: `src/fa/cli.py:125-146` constructs `SessionManager` with roots/source
  only, and no production reference consumes `FA_REPO_PUSH_URL`.
- Defect: the advertised override could not reach manager-created sessions.
- Correction: S1 adds an optional constructor field and wires the existing
  Compose `env_file` value through `_session_manager_for_args`.

**D3 — provisioner error mapping was undefined.**

- Evidence: `src/fa/session/manager.py:30-37,215-223` exposes
  `SessionManagerError.code="workspace_provision_failed"`;
  `tests/test_session_manifest_guards.py:280-338` inventories every literal
  manager error code.
- Defect: v2 introduced `WorkspaceProvisionError` but did not say what public
  manager callers receive.
- Correction: CT1 closes the private typed error set and maps every case to the
  existing public code; no new manager code is introduced.

**D4 — logical session-id validity did not imply Git-ref validity.**

- Evidence: `src/fa/session/manager.py:27,87-94` accepts the broad logical-ID
  regex, while `scripts/fa-entrypoint.sh:156-170` derives `agent/<id>` directly.
  Repro probes show Git rejects regex-valid `a..b`, `x.lock`, `a.`, and `.a`.
- Defect: “validated SessionManager id” was not a valid branch precondition.
- Correction: CT1 runs `git check-ref-format --branch` before target creation and
  rejects rather than silently maps.

**D5 — moving fallback ownership would invalidate a live rollback oracle.**

- Evidence: `tests/test_session_lifecycle.py:215-229` monkeypatches manager-owned
  `shutil.copytree` and asserts rollback.
- Defect: moving all fallback ownership into the new module would silently delete
  a live test oracle.
- Correction: S1 dispatches only normal `.git` directories to CT1 and leaves the
  non-Git copy/rollback block in `SessionManager`.

**D6 — S1 contained a premature repair API.**

- Evidence: repository-wide caller search finds no current consumer for
  `repair_managed_remote`; its first consumer is the S2 entrypoint resume path.
- Defect: v2 asked S1 to ship unused repair abstraction.
- Correction: S1 deletes it from scope; S2 adds the repair command with its real
  shell consumer and tests.

**D7 — the proposed current-source HEAD postcondition raced `fa update`.**

- Evidence: `/repo` is a live read-only bind of the host mirror, which
  operator-controlled `fa update` can fast-forward.
- Defect: comparing target HEAD with the current source HEAD after clone can
  reject a valid snapshot.
- Correction: CT1 captures one source commit, clones `--no-checkout`, branches
  from that capture, and never uses a second live read as snapshot authority.

**D8 — the fake publication-remote test contradicted CT2.**

- Evidence: CT2 rejected local push URLs while T1 required `git push origin` into
  a local bare “GitHub” remote.
- Defect: an implementer had to weaken URL validation or invent an SSH test
  server.
- Correction: T1 stores the canonical SSH URL and uses a command-local Git
  `url.<file>.insteadOf` rewrite. The real push stays network-free without
  changing production config.

**D9 — S3 left its lifecycle seam as a choice.**

- Evidence: `src/fa/cli.py:2482-2495,2521-2527` admits the session before provider
  construction, but S3 said “inject callback/strategy if needed” and omitted the
  CLI composition root.
- Defect: generic manager compatibility versus production readiness wiring was
  unresolved.
- Correction: CT6/S3 require an optional constructor callback, default `None`,
  and pass a real-readiness + degraded-warning adapter only from
  `_session_manager_for_args`.

**D10 — S8/S9 still delegated file selection to the implementer.**

- Evidence: stale current claims exist in README, ADR-13/DIGEST, operations, and
  FEATURES, plus two duplicated historical PR notes; v2 said “other hits” and
  left the S9 report path undecided.
- Defect: artifact inventory and per-step edit authority disagreed, so execution
  either missed current docs or edited unreviewed research/history.
- Correction: S8 now lists every edited file plus an explicit historical
  allowlist; S9 has one fixed report path; A30/A33–A35/A37–A39 close the
  inventory.

**D11 — S3 omitted a public wrapper dependent of the hook installer.**

- Evidence: `src/fa/hygiene/hooks/__init__.py:32-38` mirrors and forwards the
  current `install_hooks(repo_root, force=...)` signature; existing lazy-export
  tests consume it.
- Defect: adding explicit workspace hook-source selection only in `install.py`
  either bypassed the package API or left wrapper behavior divergent.
- Correction: S3 gives both concrete and lazy-wrapper functions the same optional
  `hook_source_dir` contract, lists both files, and pins forwarding/default tests.

**D12 — readiness state, timeout, and degraded persistence were not closed.**

- Evidence: CT3 named statuses but no concrete enum/dataclass types or reason-code
  set and called lock wait merely “bounded”; CT4 defined only a READY marker while
  the transition prose also required a “non-ready marker.”
- Defect: implementations could hang indefinitely, emit incompatible reason
  strings, or leave contradictory marker states.
- Correction: CT3 now fixes types, reason codes, command/lock timeouts, shell CLI,
  and total-return behavior. CT4 removes the stale READY marker before repair and
  persists degradation only in the typed result/log, never as a second marker.

#### Suspicions not promoted to defects

- Legacy resumed workspaces may contain bespoke non-local push URLs. No evidence
  permits classifying them as safe or stale, so S2 preserves them and warns; S9
  inventories live managed sessions before any cleanup.
- Persistent uv/pre-commit cache may materially improve startup, but S0 has no
  cold/warm timing evidence. S7 remains measurement-first and no mount is added.
- No additional actionable S1 suspicion remains after the contracts and tests
  below. If implementation reveals a new security/policy choice, execution stops
  and revises this plan rather than guessing.

#### Sound decisions retained

The production Git-source `copytree` replacement is necessary and directly fixes
the observed `.venv`/ignored/admin-state amplification. Keeping plain-directory
fallback compatibility, preserving explicit attach semantics, using B2 local
fetch plus GitHub push, and retaining CI/human merge as the hard gate are all
sound. They are tightened here, not redesigned.

### Live S0 execution record — 2026-08-12

The corrected probe completed with its read-only terminal sentinel. Relevant
operator evidence:

```text
operator clone:
  path=/home/fa/First-Agent-dev
  HEAD=ac5ba1a
  branch=main
  fetch=https://github.com/first-agent-dev/First-Agent-dev.git
  push=https://github.com/first-agent-dev/First-Agent-dev.git
  status.lines=2
  .venv=yes
  custom hook seats=none

deployment mirror:
  path=/srv/first-agent/repo/First-Agent-dev
  HEAD=eb2c03c
  branch=main
  fetch=git@github.com:first-agent-dev/First-Agent-dev.git
  push=git@github.com:first-agent-dev/First-Agent-dev.git
  status.lines=0
  .venv=yes
  custom hook seats=none

bind topology:
  /srv/.../repo/First-Agent-dev -> /repo       ro
  /srv/.../sessions             -> /sessions  rw
  /srv/.../state                -> /home/fa/.fa rw

active startup workspace:
  /sessions/session-20260808T152800-7
  HEAD=eb2c03c
  branch=agent/session-20260808T152800-7
  origin.fetch=file:///repo
  origin.push=file:///repo
  .venv=no
  ready marker=no
  four hook seats=missing
  manifest=no
  host/container inode=13011685 on device 66306

default fa run manager selection:
  args.workspace=None
  workspace_root=/sessions
  source_workspace=/repo
  result=new generated logical session

cache/filesystem:
  /sessions          = ext4
  /tmp/uv-cache      = tmpfs, 2 GiB cap, 181 MiB used
  /home/fa/.cache    = tmpfs, 500 MiB cap, 0 used
  pre-commit cache   = absent/empty
```

There are 33 active manifests in the returned listing. One historical manifest
uses a logical session id different from its workspace basename, which is legal
under the current override contract and is not changed by this plan. Session
retention remains the existing separate backlog item.

The deployment mirror's live `.venv=yes` upgrades GAP2 from a theoretical risk
to a production-reachable copy-amplification path: every default manager
`copytree(/repo, ...)` can carry that host environment into the new workspace.
The live startup workspace independently proves GAP1/GAP3: its push destination
is local RO `/repo`, and all readiness artifacts are absent.

The operator clone's two dirty status lines are not inspected by the probe to
avoid printing filenames. S6 must capture `git status --short` before editing
and preserve any pre-existing operator work. This does not block S1–S5.

### S1/S2 execution record — 2026-08-13

S1 and S2 are implemented in the canonical operator checkout and remain
uncommitted for operator review. No live deployment checkout or active session
was mutated.

Implemented state:

- manager-created Git sessions use a clean `file://` clone at one captured
  source revision, exact `agent/<session-id>` branch, canonical/overridden GitHub
  pushurl, and repository-local trusted identity;
- entrypoint fresh/resumed workspaces run the aggregate adapter before `.active`;
- exact-empty override semantics, Git ref validation, fetch authority, narrow
  local-push repair, custom preservation, Q5 redaction, stable JSON, and safe
  exit-2 diagnostics are enforced;
- fresh configuration failure removes the clone; resumed failure preserves all
  workspace content and never checks out, resets, deletes, or cleans;
- post-setup no longer writes identity, reads the workspace's actual pushurl for
  connectivity, and compares `/repo` HEAD/status across publication smoke.

Final-review defects found and corrected:

1. custom workspace state was initially blocked by missing/invalid source
   publication authority even though no repair was needed; source authority is
   now strict for local repair but advisory for preserving a non-local custom
   pushurl;
2. Git diagnostic sanitization initially redacted URL userinfo but not query,
   fragment, or loose sensitive assignments; all are now redacted before control
   escaping and length capping;
3. the post-setup identity regression test matched only contiguous
   `git config`; it now also detects valid option placement such as
   `git -C <path> config`.

Verification record:

```text
workspace aggregate tests                  = 96 passed
combined S2 behavior                       = 194 passed, 13 skipped
Ruff lint/format                            = passed
Mypy (MYPYPATH=src where required)          = passed
Pyrefly                                     = passed
compileall                                  = passed
Bash syntax / repository shell syntax       = passed
Markdownlint / documentation links          = passed
Git whitespace and mode-summary checks      = passed
full targeted mutation run                  = 940 killed / 946, 6 survived
post-oracle targeted mutant                 = configure-existing #141 killed
final mutation classification               = 941 killed / 946, 5 equivalent
mutation timeout/error/suspicious            = 0 / 0 / 0
```

Equivalent mutants are three URL-control boundary variants still rejected by
the strict repository regex, fresh-clone `git switch -c` versus `-C` where the
branch cannot preexist, and `None` versus empty internal unavailable-authority
sentinels that both preserve a non-empty custom Git remote.

Producer-removal proofs:

- removing the entrypoint aggregate adapter made all four selected fresh,
  resumed, custom, and override C2 tests fail;
- removing the post-setup actual-pushurl read failed its command contract;
- removing the `/repo` source snapshot failed the integrity contract;
- reintroducing a `git -C ... config user.name` write failed the strengthened
  identity-masking contract.

Temporary mutation configuration, source edits, shell edits, and root-backed
test directories were restored/removed after every check. Readiness artifacts
are intentionally not claimed by this S2 record; the S3 execution record follows.

### S3 execution record — 2026-08-13

S3 is implemented in the canonical operator checkout and remains uncommitted for
operator review. No live deployment checkout or active session was mutated.

Implemented state:

- `ensure_workspace_ready()` returns the closed `ReadyState`/`ReadyStatus` CT3
  contract and serializes repair with a bounded non-blocking `flock`;
- active readiness requires the exact fingerprinted project inputs, project
  interpreter, four executable/current workspace-owned hook seats,
  `uv sync --locked --extra dev --check`, private cache sentinel, and private
  marker; marker-only readiness is impossible;
- repair installs workspace hook seats, runs locked uv sync with
  `UV_LINK_MODE=copy`, prewarms pre-commit, reinstalls outer wrappers, verifies
  all active state, and atomically writes the 0600 sentinel/marker;
- append-only 0600 NDJSON and stable CLI JSON/exit 0/75/70 expose every typed
  result without environment, task, provider, or credential output;
- `SessionManager` prepares new sessions after DB creation/before active manifest
  and attached sessions after DB validation/before `last_used_at` mutation;
- the production CLI factory injects the total adapter before provider-chain
  construction and model calls; degraded state warns and remains fail-open;
- the entrypoint invokes the readiness CLI after S2 Git configuration and before
  `.active`, command override, or auto-run, preserving degraded stderr and adding
  a generic rc warning for command-start failures.

Final-review defects found and corrected:

1. individual hook files/utilities could be symlinks escaping the selected
   workspace source despite directory-level containment; every fingerprinted
   hook input is now a contained regular file;
2. `.fa`, `bootstrap.log`, or `bootstrap.lock` symlinks could redirect trusted
   writes; private opens now reject symlinks and use `O_NOFOLLOW` where available;
3. permissive marker/sentinel modes could satisfy fast readiness; active checks
   now require 0600 and repair otherwise;
4. hook-path Git resolution was unbounded; it now has CT3's 120-second timeout
   and deterministic pure-Python fallback;
5. the first implementation duplicated failure status/stage/argv policy across
   many call sites; reason projection is now centralized, reducing the engine
   from 833 to 684 lines and eliminating inconsistent representable states;
6. marker-removal I/O failure could lose its original failure observability at
   the recording boundary; it now returns/logs `state_io_failed` with the known
   fingerprint.

Verification record:

```text
readiness engine tests                      = 80 passed
combined S1-S3 affected behavior            = 356 passed, 13 skipped
repository-wide pytest                      = 2892 passed, 15 skipped, 1 xfailed
repository-wide pre-existing failures       = 3 (CODEOWNERS, authoring clean, Pyrefly seat)
Ruff lint/format                            = passed
Mypy (MYPYPATH=src)                         = passed
Pyrefly (all changed S1-S3 files)           = passed
compileall                                  = passed
Bash syntax / repository shell syntax       = passed
Markdownlint / documentation links          = passed
Git whitespace and mode-summary checks      = passed
initial targeted mutation run               = 816 killed / 1291, 475 survived
final targeted mutation run                 = 866 killed / 874, 8 equivalent
mutation timeout/error/suspicious            = 0 / 0 / 0
```

Equivalent mutants are one create-mode omission neutralized by immediate
`fchmod(0600)` before use, four Linux-inactive Windows-branch string variants,
and three marker-removal error-code variants normalized by the recording
boundary to the same observable `state_io_failed` result/log/fingerprint.

The repository-wide failures reproduce unrelated baseline authority gaps:
CODEOWNERS does not cover seven existing TCB paths; the authoring check rejects
the intentionally uncommitted implementation tree; and the full Pyrefly seat
reports the pre-existing `_EgressProxyHandler.log_message` parameter-name issue
plus `tests/test_semgrep_pin.py` narrowing of `list[str] | None`. Changed-file
Mypy/Pyrefly and all S3 behavioral roots are green.

Producer-removal proofs:

- removing both manager preparation producers failed the new-session and attach
  ordering tests;
- removing CLI factory injection failed the exact `ready, build, call` C2 proof;
- removing the entrypoint producer failed ordering, real-artifact, and degraded
  continuation tests.

Temporary mutation configuration, copied staging tree, production mutations,
and root-backed test directories were restored/removed. The operator subsequently
approved tooling-only S3.5 as the next permitted slice; S4 remains the next
runtime-product slice.

### S3.5 execution record — 2026-08-13

Implemented state:

- NEW `scripts/run_slice_mutmut.py` is the sole explicit/configured mutation
  executor: strict repo-relative roles, overlap/symlink/UTF-8 checks, exact
  mutmut 3.6.0 gate, root-backed mode-0700 staging, complete test-oracle copy,
  generated scoped Pyrefly command, process-group wall timeout, count identity,
  atomic schema-v1 JSON/actionable diffs, repository-input digests, and checked
  cleanup before rc 0/1;
- `scripts/run_targeted_mutmut.py` is a thin production-only selector and
  delegates the configured tests/copy policy to the executor;
- `scripts/_git_diff.py` has 30-second return-code-checked NUL-safe committed,
  worktree, and untracked discovery; Semgrep defaults remain committed-only;
- permanent mutmut and pytest-gremlins paths include readiness, selected tests
  include `tests/test_workspace_bootstrap.py`, `also_copy=["src/fa"]`, and the
  direct Pyrefly path segment exactly equals `source_paths`;
- weekly mutation uses locked sync, configured runner, complete result/diff
  artifacts, unchanged advisory policy, and an explicit 18,000-second bound
  below GitHub's six-hour ceiling;
- the new runner is covered by CODEOWNERS and `_TCB_PATHS`;
- existing planning/testing/mutation skills remain unchanged.

Production review defects closed during execution:

1. exact 3.6.0 compatibility replaced broad 3.x acceptance;
2. duplicate/ancestor source/test overlaps are rejected;
3. non-POSIX execution is rejected before staging with gremlins guidance;
4. every Git discovery subprocess is bounded and partial failure output is
   rejected;
5. valid Pyrefly nonzero diagnostic output is distinguished from malformed or
   unmappable infrastructure failure;
6. resolved fallback tool directories are prepended for mutmut's literal
   `pyrefly` child command;
7. stage cleanup is verified before clean/actionable artifact publication;
8. the configured weekly timeout is separated from the explicit-slice default.

Verification record:

```text
S3.5 authority tests                         = 20 passed
permanent mutmut-selected suites + S3.5      = 382 passed
real three-mutant fixture                    = 2 killed + 1 type-invalid
readiness via shipped runner                 = 874 total
readiness test-killed / type-invalid         = 329 / 540
readiness survivors                          = 5 equivalent
readiness other statuses                     = 0
readiness runner rc/verdict                   = 1 / action_required
configured 1500-second probe                 = rc 3 mutation_timeout (during generation)
configured timeout residue                   = none
repository-wide pytest                       = 2912 passed, 15 skipped, 1 xfailed
repository-wide classified failures          = 3 (CODEOWNERS parser, authoring dirty, full Pyrefly)
Ruff lint/format (384 files)                  = passed
changed-file Mypy/Pyrefly                     = passed
full Pyrefly                                  = 2 known non-S3 errors
full Mypy                                     = 6 non-S3/pre-existing findings
compileall / shell syntax                     = passed
uv lock --check                               = passed
four deterministic contract scripts          = passed
markdownlint / documentation links            = passed
Git whitespace / executable-mode summary      = passed / clean
```

The five exact survivor diffs remain
`x__open_private__mutmut_7`, `x__read_python_minor__mutmut_7/8`, and
`x__hooks_current__mutmut_12/13`; they reproduce the previously proven
post-`fchmod` and Linux-inactive Windows equivalents. No allowlist, pragma, or
clean relabel was added.

Producer-removal proofs (all source trap-restored, then green tests rerun):

- replacing targeted executor invocation with success failed both delegate
  authority tests;
- forcing action-required classification to exit zero failed the raw-rc survivor
  test;
- removing permanent `type_check_command` failed exact config authority;
- replacing weekly configured runner with raw `mutmut run` failed workflow
  authority.

The configured local probe deliberately used a 1,500-second diagnostic bound and
proved timeout/process cleanup; it did not complete the large permanent scope.
The scheduled advisory workflow is the long-running completion authority at
18,000 seconds. S3.5 is complete; S4 is the next permitted slice.

### S4 planning preflight correction — 2026-08-13

Source facts:

- `scripts/bootstrap/workspace.py` is absent;
- `host_bootstrap.py` owns a second fingerprint/marker transaction, uses
  `--frozen`, and has unbounded raising subprocess calls;
- `just install` duplicates sync/install/status; `agent-bootstrap` uses plain
  `uv run`; `doctor` uses plain `uv run` and checks hooks but not CT4 state;
- tracked `.fa/host-bootstrap.json` is explicitly re-included from `.fa/*`;
- `.vscode/tasks.json` already points to the stable `agent-bootstrap` alias and
  remains unchanged.

Confirmed S4 plan defects corrected:

- **D20 — no read-only full-readiness authority.** Add
  `check_workspace_ready()` and CLI `check`, reusing `_fast_ready` without
  calling `_ensure_private_state_paths`, lock acquisition, repair, logging, or
  state writes. It uses existing `ready_fast_path`, `locked_check_failed`, and
  other CT3 reason/status/exit mappings; no new reason code is introduced.
- **D21 — host command failure was not bounded or total.** Version checks use a
  30-second bound, `uv tool install` uses 900 seconds, optional `update-shell`
  uses 120 seconds, and readiness wrapper uses 2,000 seconds. Missing uv returns
  2; host tool setup failure returns 75; wrapper rc 0/75/70 propagates exactly;
  `FA_AGENT_READY=1` appears only after rc 0.
- **D22 — doctor status could trigger sync and still miss CT4 drift.** Replace
  hook-only plain `uv run` with direct stdlib wrapper `check`; CI retains its
  explicit no-local-hook/readiness exemption.
- **D23 — read-only check could trust redirected/permissive private state.**
  Before reading marker state, require a non-symlink mode-0700 `.fa` directory
  and non-symlink mode-0600 log/lock files. Symlink redirection returns
  `state_io_failed`; missing/mode drift returns `locked_check_failed`; check
  never chmods or creates them.
- **D24 — alias C1 tests were placed inside the core C4-selected file.** Copying
  scripts/config into the mutant tree made collection honest but coupled
  unrelated subprocess/static tests to every readiness mutant and destabilized
  execution. Move those unchanged oracles to NEW
  `tests/test_workspace_bootstrap_aliases.py`; keep only core-function tests in
  the permanently selected readiness suite and retain `also_copy=["src/fa"]`.
- **D25 — nonzero mutmut parent exit could leave worker children alive.** CT10
  now terminates the process group after every parent exit, not only timeout,
  before stage cleanup. A fake parent-plus-sleeping-child test pins teardown.

No blocking S4 question remains.

### S4 execution record — 2026-08-13

Implemented state:

- `check_workspace_ready()` and CLI `check` reuse full fast-readiness authority
  without lock, repair, log, marker, sentinel, chmod, or directory creation;
- read-only status rejects symlinked/permissive/missing private state and retains
  computed fingerprints for active-state drift;
- NEW `scripts/bootstrap/workspace.py` imports only the checked-out source and
  forwards exact CLI argv before any uv-managed environment is required;
- `host_bootstrap.py` is reduced to bounded conditional `just` setup plus exact
  wrapper delegation; duplicate fingerprint/marker/sync/hook logic is deleted;
- `just install`, `agent-bootstrap`, and local `doctor` select ensure, host
  adapter, and read-only check respectively; old private recipes are deleted;
- tracked `.fa/host-bootstrap.json` and its ignore negation are deleted;
- `.vscode/tasks.json` remains unchanged and non-authoritative;
- alias/config tests live in A53 outside the core permanent C4 test seat;
- CT10 process-group teardown is hardened for nonzero parent exits.

Live operator-checkout proof:

```text
cold check before readiness          = rc 75 locked_check_failed, no state write
first just install                   = rc 0 ready_repaired, 59.3 s
warm just install                    = rc 0 ready_fast_path, 40 ms
agent-bootstrap                      = rc 0, wrapper fast path, FA_AGENT_READY=1 last
doctor after final pyproject state   = rc 0, readiness current
final check                          = rc 0 ready_fast_path, 40 ms
read-only marker/log/lock/sentinel   = byte/mtime/mode unchanged
final fingerprint                    = sha256:bcf3c60d4b1874b93c36a76b8b839d71973d4572d1e871605c8ba182bcec5155
```

Verification record:

```text
core readiness authority                    = 88 passed
S4 alias/host/marker authority              = 7 passed
affected combined suites                    = 179 passed, 13 skipped
repository-wide pytest                      = 2928 passed, 15 skipped, 1 xfailed
repository-wide classified failures         = 3 (CODEOWNERS parser, authoring dirty, full Pyrefly)
S4 readiness C4                             = 996 total
C4 test-killed / type-invalid               = 355 / 636
C4 survivors                                = 5 prior equivalents
C4 timeout/error/suspicious/no-test          = 0 / 0 / 0 / 0
Ruff/Mypy/Pyrefly changed-file gates         = passed
shell syntax / just parser / compileall      = passed
```

All five S4 producer-removal checks were killed and trap-restored: check CLI
dispatch, checkout wrapper call, host readiness delegation, install ensure
alias, and doctor check alias. Seven initial new C4 survivors were closed with
missing-log/lock and fingerprint tests plus production simplification; only the
five previously proven equivalents remain. Root-backed TMPDIR was required
after measured `/tmp/pytest-of-user` growth exhausted 627 MiB of tmpfs.

S4 is complete; S5 is the next permitted slice.

### S5 execution record — 2026-08-13

Implemented state:

- each tracked hook source owns the same self-contained prelude: quiet
  `git rev-parse --show-toplevel`, checked-out stdlib wrapper `ensure`, captured
  READY JSON, inherited degraded stderr, and a generic rc/log warning;
- every bootstrap nonzero returns 0 before the normal body, while bootstrap rc 0
  reaches the original body outside the fail-open branch;
- all existing normal commands use `uv run --no-sync` with their original
  command order, arguments, message-hook positional behavior, and pre-push stdin;
- no shared helper, recursive `exec "$0"`, missing-seat self-install claim, or
  quality-failure catch was added;
- NEW `tests/test_hygiene_hooks_self_bootstrap.py` drives real shell subprocesses
  in repositories with spaced paths and exact wrapper/uv process-boundary
  records; retained installer/hook tests now provide valid Git/readiness
  preconditions without bypassing the new producer.

Verification record:

```text
new S5 shell-hook authority                  = 16 passed
new + retained hook authority                = 55 passed
hook + readiness/alias/slice broad authority = 171 passed
repository-wide pytest                       = 2944 passed, 15 skipped, 1 xfailed
repository-wide classified failures          = 3 (CODEOWNERS parity, authoring dirty, full Pyrefly)
full Ruff/format                              = 710 files passed
changed Mypy/Pyrefly + compileall/uv lock     = passed
Bash syntax / repository shell syntax        = passed
four deterministic contract scripts          = passed
markdownlint / internal document links        = passed
identical prelude SHA-256                     = 00c56ef30270dfe56310990fa3aaa8a04599d5b0fc9e411f1a939475fcb6fd4b
source modes / installed seat modes           = 755 / executable
Git diff integrity                            = passed
```

T9–T12 negative proof:

- deleting the pre-commit readiness block made the ready-path phase oracle fail
  (`normal` instead of `bootstrap → normal`), pytest rc 1;
- changing prepare-commit-msg normal rc 7 into broad `exit 0` made the exact-rc
  oracle fail, pytest rc 1;
- both source mutations were trap-restored byte-for-byte at mode 0755, then the
  hook authority plus core concurrent-lock oracle passed;
- all four extracted preludes have one hash; static authority rejects recursive
  self-exec and any remaining plain `uv run` body call.

Live proof:

```text
isolated missing-venv before hook            = .venv absent, managed seats 0
isolated real readiness after hook           = ready_repaired, .venv executable, seats 4
isolated post-ready normal argv               = run --no-sync pre-commit run --hook-stage pre-commit
isolated successful hook                      = rc 0, bootstrap JSON stdout silent
isolated uv-missing pre-push                  = rc 0, tool_missing + one generic warning
isolated degraded artifacts/body              = no READY marker, no venv, normal body not run
unshimmed post-ready pre-commit baseline       = rc 1 preserved (known full Mypy/Pyrefly findings)
canonical ensure after S5 hook-byte changes   = ready_repaired, 288 ms
canonical installed pre-push skip fast path   = rc 0, 117 ms, stdout empty
final canonical read-only check               = ready_fast_path, engine 39 ms
canonical S5 fingerprint                      = sha256:a5be105395a80da1fabc757355cdecb2e7eaf486b2834d2b56b127edb3b8456f
```

The successful isolated repair probe delegated every readiness uv command to the
real uv binary and stubbed only the exact post-ready normal gate argv, separating
readiness convergence from classified repository-wide quality findings. A prior
unshimmed probe ran that real normal gate and returned rc 1, proving the hook did
not broaden bootstrap fail-open into quality fail-open. Both scratch workspaces
were trap-cleaned. No new policy choice or unresolved S5 blocker appeared.

S5 implementation is complete; S6 is the next permitted slice. The later
S6.5 preflight supersedes only S5's integrated stdin-verification claim: D27 is
owned by S6.5/T23 and blocks S7, not S6 documentation work.

### S6.5 planning preflight — 2026-08-13

Mode: `/plan-authoring` audit at plan depth P3. Prior execution summaries were
inputs, not authority. Production roots, focused tests, full gates, and current
documentation were re-read before this revision.

Roots checked:

- `src/fa/session/workspace.py`, `SessionManager`, and CLI composition;
- `scripts/fa-entrypoint.sh` and `scripts/fa-post-setup.sh`;
- `src/fa/workspace_bootstrap.py`, checked-out/host wrappers, and just aliases;
- all four hook sources plus installer/status/path resolution;
- isolated mutation runner, selectors, permanent config, workflow, and TCB seats;
- S6 target docs, VS Code task, focused C1/C2/C3 tests, and repository-wide gate
  failures.

Verified findings:

- **D26 — S6 named the wrong test seat.** It assigned host alias/task static
  assertions to core `tests/test_workspace_bootstrap.py`, contradicting D24 and
  permanently coupling documentation/config probes to every readiness mutant.
  S6 must use `tests/test_workspace_bootstrap_aliases.py`.
- **D27 — “noninteractive” readiness children inherit stdin.**
  `workspace_bootstrap._run_process` sets timeouts/capture/env but no stdin.
  Reproducible pipe probe produced
  `child_captured='pre-push-ref-line\n'` and `parent_remaining=''`. The S5 fake
  wrapper never launches core children, so its pre-push stdin oracle could not
  detect this contract breach.
- **D28 — real repository commitability is not proved.** Provisioner and
  entrypoint commit tests use minimal repositories/fake pre-commit boundaries.
  The unshimmed S5 live probe reached the shipped normal gate and returned rc 1;
  current full Mypy reports six findings and full Pyrefly reports two. Preserving
  rc is correct S5 behavior, but a candidate that cannot commit is not G2 L3.
- **D29 — mutation-governance parity authority is false-red.** CODEOWNERS and
  `_TCB_PATHS` contain the new runner, but
  `tests/test_authoring_protected_paths_parity.py` filters CODEOWNERS by a short
  authoring-name marker list and excludes eight real gate paths. Its focused C2
  test fails before semantic parity can be established.
- **D30 — dirty-worktree classification is not merge readiness.** The authoring
  failure is expected while implementing a large uncommitted plan, but it cannot
  be carried as an accepted final baseline. S6.5 needs an isolated clean
  materialization of the exact candidate bytes and a zero-diagnostic blocking
  gate result.

Current review verdict:

| Slice | Current evidence | Review status before S6.5 |
| --- | --- | --- |
| S1–S2 | real Git C1/C2, branch/B2/identity/read-back/rollback | strong; integrated publication remains S9 |
| S3–S4 | real repair, lock/marker/sentinel, wrappers/aliases | strong with confirmed D27 stdin gap |
| S3.5 | real mutation fixtures and classified C4 | strong executor; D29 governance proof red |
| S5 | 16 focused tests, manual kills, live repair/degraded/rc proof | correct mapping; D28 blocks commit-capable claim |
| S6 | role/recovery docs, unchanged VS Code task, live host alias | implemented; T13 static/live authority green; review again in S6.5 |

No blocking policy question exists for the known fixes. If review finds a new
compatibility, security, permissions, custom-hook preservation, or public
behavior choice, execution stops and adds a blocking Q# before changing code.

### S6 execution record — 2026-08-13

Implemented state:

- `AGENTS.md` assigns commits/branches/PR work to `~/First-Agent-dev`, assigns
  operator update/deployment only to `/srv/first-agent/repo/First-Agent-dev`,
  removes model-owned bootstrap work, and documents one pinned uvx recovery path;
- install and operations guides repeat both checkout roles, missing-uv recovery,
  managed-clone scope, and the explicit no-commit deployment boundary;
- CI/guardrail reference now names lifecycle readiness before providers, the
  checked-out wrapper, read-only `just doctor`, `uv run --no-sync` hook bodies,
  `check-deep` pre-push behavior, and CI's local-seat exemption;
- `.vscode/tasks.json` remains the unchanged permission-dependent folderOpen
  convenience consumer; explicit terminal recovery remains authoritative;
- S6 static assertions live in A53 outside permanent core readiness C4.

Verification record:

```text
new/retained S6 alias/document authority      = 10 passed
S6 + hook + lock + provider-order authority   = 28 passed
final affected readiness/hook authority       = 153 passed
canonical uvx host bootstrap                  = rc 0, ready_fast_path, 47 ms
canonical readiness signal                    = FA_AGENT_READY=1
canonical just doctor                         = rc 0, readiness current
final canonical read-only check               = ready_fast_path, 94 ms
canonical fingerprint                         = sha256:a5be105395a80da1fabc757355cdecb2e7eaf486b2834d2b56b127edb3b8456f
stale frozen/old-marker/deleted-recipe sweep   = 0 hits
deployment-mirror fenced commit blocks        = 0
VS Code task tracked diff / SHA-256            = empty / 131731c081feab41378c750db490c80352d1d22d326062bdf43200221953be14
document internal links                       = passed
CI guardrail markdownlint                     = 0 errors
Ruff/format/Mypy/Pyrefly on A53                = passed / 0 errors
Git diff integrity                             = passed
```

Whole-file markdownlint retains pre-existing diagnostics outside the S6-added
ranges in `AGENTS.md` and the long installation/operations guides. They are not
relabeled clean or widened into opportunistic S6 edits; S6.5/T24 and S8/T15 own
the clean-candidate/full-document gate. No policy choice or blocking S6 question
appeared.

S6 is complete.

### S6.5 execution record — 2026-08-13

Implemented and reviewed state:

- D27 is closed: every readiness child receives closed stdin while the real
  checked-out pre-push wrapper forwards the original ref-update bytes exactly;
- CODEOWNERS/protected-path parity is semantic for exact, prefix, and wildcard
  gate patterns; blocking type findings were minimally corrected without
  ignores or product-behavior changes;
- A55 proves real Git provisioning, readiness, installed hooks, identity-cleared
  second commit, local bare publication, source immutability, and zero provider
  calls;
- deterministic collection capability markers replaced dynamic skips;
  `ReadyReason` is public, shell mode is 0755, and exact candidates preserve the
  ignored-but-tracked dependency contract;
- deptry models `scripts` as first-party and the unreachable pre-3.11 `tomli`
  fallback is deleted under the Python ≥3.13 project floor;
- Q7's M17/P24 stop worked: automatic readiness now preserves every custom hook
  path and non-FA default-seat collision, returns typed DEGRADED state, and does
  not overwrite or chain unknown executable code;
- A54 contains the closed CT13 ledger, exact 52-path inventory, all remediation
  and producer-kill evidence, later-slice owners, and binary admission.

Verification record:

```text
post-E12 focused/integrated authority = 184 passed in 96.45 s
exact manifest / tracked files        = 791 / 791
shell mode / dependency contract      = 0755 / present
readiness                              = ready_repaired in 35.552 s
clean candidate just check             = rc 0; all blocking subgates passed
full pytest                            = 2,958 passed, 15 skipped, 1 xfailed
full coverage                          = 84.67%
full Mypy                              = 0 issues in 362 files
full Pyrefly                           = 0 errors
Ruff/format/deptry/pylint              = passed / no issues / 10.00
contracts/shell/lock/authoring         = passed / 0 diagnostics
candidate status                       = clean before/after readiness/check
```

Ten trap-restored S6.5 producer kills failed their named oracles: stdin
isolation, manager Git dispatch, lifecycle readiness, hook prelude, CODEOWNERS
runner seat, deptry first-party classification, dead `tomli` use, pre-fast hook
ownership, automatic-install ownership, and default/effective-path separation.
Hashes and modes restored exactly; affected gates reran green. Strict mutation
equivalents remain visible and unrelabeled.

No model call, external push, cache topology, secret copy, hook chaining, or
unowned policy change occurred. External GitHub/deployment claims remain S9
owned. A54 records:

```text
S7_ADMISSION=ALLOW
```

S6.5 is complete. S7 measurement is now permitted.

### S7 execution record — 2026-08-13

A26 records the complete CT9/T14 command sheet and evidence. The execution
environment exposes no Docker daemon or `/srv` deployment tree, so actual image
identity and current production session `.venv` inventory remain explicitly S9
owned. The controlled proxy used exact candidates on ext4, isolated caches,
locked tools, `UV_LINK_MODE=copy`, and 100 ms logical/allocated-size sampling.

The first 500 MiB and near-1-GiB tmpfs trials correctly failed on gitleaks cold
preparation and triggered Q8. A completed ext4 size proxy established the
993,908,224-byte allocated HOME-cache peak. The operator-approved ephemeral
ceiling was therefore calibrated to `1536M`, leaving 616,704,512 bytes (38.29%)
headroom; uv retains its separate 2 GiB tmpfs.

```text
uv cold / warm                       = 1.612073 s / 0.065653 s
pre-commit cold / warm proxy         = 71.922611 s / 0.222198 s
readiness cold wrapper / engine      = 76.418005 s / 76.318 s
readiness warm wrapper / engine      = 0.111884 s / 0.045 s
cache-loss resume wrapper / engine   = 66.606732 s / 66.540 s
HOME peak logical / allocated        = 921,239,936 / 993,908,224 bytes
pre-commit peak logical / allocated  = 709,725,635 / 767,550,976 bytes
uv cache logical peak                = 180,253,579 bytes
.venv logical / allocated            = 178,797,184 / 189,746,688 bytes
legacy raw-copy logical              = 240,764,558 bytes
fresh clean clone logical            = 16,867,636 bytes (92.99% smaller)
ready clean clone logical            = 195,766,647 bytes (18.69% smaller)
final just check                      = rc 0; 2,959 passed; 84.69% coverage
```

M1 returned `ready_repaired`, M2 returned `ready_fast_path`, and M3 rebuilt the
cache and rewrote the marker with `ready_repaired`; candidate Git status remained
clean. All disposable roots were deleted. A66/A67 enforce the distinct ephemeral
1536M HOME and 2G uv seats; reverting the HOME cap killed the parsed-YAML test.
Removing A26's Q2 decision killed its deterministic report validator.

Q2 is resolved as `PERSISTENCE_DEFERRED_WITH_MEASURED_REASON`. No persistent
mount, cache service, bake, hook redesign, or quality weakening was added. S7 is
complete.

### S8 execution record — 2026-08-13

Current documentation now states the actual system:

- `file:///repo` uses Git pack transport; no filesystem-link or zero-cost claim;
- no session selector creates a new persistent logical session, while explicit
  `--session-id` attaches; restart reapplies that selector rather than erasing a
  pinned session;
- managed clones fetch locally and publish through validated `origin.pushurl`;
  the credential-free `FA_REPO_PUSH_URL` override is documented only in the
  non-secret runtime template;
- lifecycle readiness prepares `.venv`, four hook seats, and pre-commit
  environments before model use, with typed bootstrap fail-open and strict
  quality failures;
- authoritative session DB lives under `~/.fa/sessions/<session-id>/`, while
  `~/.fa/session-log/<run-id>/` contains per-run mirrors/debug artifacts;
- S7's ephemeral 1536M HOME/2G uv cache decision is reflected without claiming
  production latency;
- agent authority ends at feature branch/PR; merge/update/deployment remain
  operator-controlled.

ADR-13 carries a dated amendment, DIGEST/README/operations/FEATURES are current,
and four preserved historical PR-note/session-prompt bodies have top-level
superseded banners linking ADR-13 and AP-004. The guardrail reference was already
source-aligned and remained unchanged.

```text
S8/T15 focused authority        = 80 passed, 13 capability skips
S8 Markdown                     = 12 files, 0 errors
S8 internal links               = passed
current stale-claim paths       = 0
remaining historical paths     = 10, all explicitly classified
Ruff/format/Mypy/Pyrefly        = passed / 0 errors
Authoring check                 = 0 diagnostics
producer kills                  = 6 failed as required; hashes/modes restored
final just check                = rc 0; 2,963 passed; 84.69% coverage
```

The six negative proofs covered unclassified stale paths, current transport,
runtime override placement, historical banners, session DB authority, and
restart/selector semantics. No historical research body was rewritten and no
new policy choice appeared. S8 is complete; S9/T16 retains actual GitHub, CI,
deployment, and human-boundary proof.

### Unresolved

- `Q1` — **RESOLVED** by the S0 live record above.
- `Q2` — **RESOLVED/DEFERRED WITH MEASURED REASON** by A26: keep bounded
  ephemeral tmpfs; persistence requires later measured need and a separate P2 plan.
- `Q6` — **RESOLVED** by unchanged strict mutation policy: survivors stay exit 1;
  no baseline/pragma/allowlist is added.

---

## 0. Executive intent

**IDEA.** Every First-Agent-managed session workspace must start from the
operator-approved local deployment snapshot, be able to push only through an
explicit GitHub push URL, and have its project environment plus all Git-hook
environments prepared by deterministic lifecycle code before the first LLM call.

**PROJECT MEANING.** This belongs at workspace provisioning/admission, not in
AGENTS.md, because cloning, remote selection, environment sync, and hook setup
are deterministic orchestration. The two-stage filter remains: local mirror and
local gates first; remote branch/PR CI and human merge second.

### Goals

- **G1 — B2 Git routing.** Every managed session has
  `origin.fetch=file:///repo` and
  `origin.push=git@github.com:first-agent-dev/First-Agent-dev.git` (or an
  explicit validated override), with a session-owned feature branch.
- **G2 — clean, commit-capable logical-session clone.** A default `fa run`
  creates its new workspace from committed Git state, not raw deployment
  filesystem state, and trusted provisioning installs repository-local author
  identity before the agent can commit.
- **G3 — readiness before model execution.** `.venv`, dev dependencies, custom
  hook seats, and all pre-commit environments are prepared before provider/LLM
  invocation on fresh and attached managed sessions.
- **G4 — zero LLM bootstrap work.** No model instruction or tool call is needed
  to build `.venv`, install hooks, or diagnose ordinary staleness.
- **G5 — deterministic warn-only degradation.** Environment/bootstrap
  unavailability emits structured state/log output and allows agent/Git
  continuation; an actual quality-gate finding still blocks as today.
- **G6 — operator development clone.** `~/First-Agent-dev` gets the same
  idempotent readiness mechanism through VS Code and explicit aliases, while the
  `/srv/...` deployment mirror stays free of dev lifecycle obligations.
- **G7 — measured cache decision.** Cold/warm uv and pre-commit setup latency and
  disk use are measured before any persistent cache mount is added.
- **G8 — truthful docs and live proof.** ADR/ops docs describe the actual pack
  transport, persistent-session selector, B2 remotes, and managed readiness;
  live server evidence closes the product claim.
- **G9 — trustworthy mutation feedback for readiness maintenance.** Operators
  and agents can run an explicit tracked-or-untracked production slice against
  explicit tests without mutating repository config or test source; results
  distinguish tests-killed, type-invalid, surviving, untested, timeout, and
  harness-failure states; the readiness engine is permanently selected by both
  configured mutation tools.
- **G10 — integrated S1–S6 production acceptance.** Every intended S1–S6 claim
  maps to its actual producer, consumer, state transition, failure boundary, and
  production root; a clean candidate runs real readiness/hooks/commit and all
  blocking repository gates with no unexplained failure or surviving producer
  kill-check before benchmark/documentation/live-deploy work continues.

### Intent

Code must ensure the managed-workspace invariant whenever First-Agent creates,
resumes, or admits a session, while preserving explicit session selection,
read-only `/repo`, branch-only agent rights, PR CI, and human-controlled merge
and deployment.

### Mechanism sketch

```text
trusted /repo commit
  → Git-aware session provisioner
  → local fetch remote + GitHub SSH pushurl + agent/<session-id> branch
  → trusted repository-local Git author identity
  → locked stdlib readiness transaction
  → network-free hook seats
  → uv --locked dev sync
  → pre-commit environment prewarm
  → final seat/status verification + atomic marker/cache sentinel
  → session admission / LLM call
```

On bootstrap unavailability, the producer returns typed `DEGRADED` state,
appends a log, removes stale READY authority, and warns; it does not persist a
second marker. Hooks fail open only before the normal gate starts. Quality-gate
exit codes remain blocking.

S3.5 adds a separate deterministic tooling path:

```text
validated repo-relative source/test/dependency paths
  → root-backed isolated staging tree + generated temporary mutmut table
  → scoped Pyrefly JSON type filter
  → native mutmut clean/forced-fail/mutation phases under a wall bound
  → parse per-mutant statuses; close exact count identity
  → atomic JSON result + actionable-mutant diff report
  → strict synthesized exit (never raw `mutmut run` rc)
```

### Proof sketch

C1 tests boot real `SessionManager` and hook scripts over real temporary Git
repositories. C2 entrypoint tests execute the shipped shell root. A local bare
"GitHub" remote proves B2 by receiving a pushed branch while the local source
mirror remains unchanged. Removing clone/pushurl/bootstrap producer sites must
fail their named tests. A final operator-run live sheet verifies real bind/tmpfs
mount behavior.

For S3.5, C0/C1 script tests use a recording fake mutmut at the process boundary
to prove staging, path roles, restoration-by-construction, result parsing,
timeout cleanup, and synthesized exits. A Linux C4 fixture runs locked real
mutmut/Pyrefly and must report `2 killed + 1 type_invalid + 0 actionable` from an
untracked source/test pair. A second real/fake survivor fixture proves raw
`mutmut run` rc 0 becomes runner rc 1. Removing the runner producer from the
targeted wrapper or workflow must fail its wiring test.

Size: **L**, implemented as bounded sequential slices.

---

## 1. Non-goals and minimal-mechanism check

### Non-goals

- No change to `fa run --session-id` semantics.
- No collapse to one logical session per container lifecycle.
- No writable `/repo` mount.
- No agent merge permission or automated merge to `main`.
- No automatic `fa update`; the operator remains the deployment gate.
- No `git clone --local`, worktree-sharing, alternates, or hardlink revival.
- No persistent package/pre-commit cache in the first implementation PR.
- No new dependency; workspace code is stdlib + existing `uv`, `git`,
  `pre-commit`, and `just` surfaces.
- No global `~/.gitconfig`, `init.templateDir`, or global `core.hooksPath` edits.
- No promise that an arbitrary unmanaged `git clone` auto-installs hooks.
- No promotion of weekly mutation CI from advisory to blocking; S3.5 may replace
  its raw mutmut command/reporting path while preserving job-level
  `continue-on-error: true`.
- No mutation of tests, whole-`src` expansion, coverage-line mutation filter,
  mutation-score threshold, survivor baseline/allowlist, new `# pragma: no
  mutate`, or automatic equivalent-mutant decision in S3.5.
- No persistent mutation cache in S3.5; staging is root-backed and disposable.
- No edits to `feature-planning`, `tests-writing`, or `mutation-clearing`.
- No worktree-specific dispatcher redesign in this plan; managed v0.1 sessions
  are independent full clones. Existing worktree behavior remains covered by
  current hook tests and is not upgraded to a new claim.
- S6.5 is not authority for unrelated refactoring, new dependencies, public
  behavior changes, cache topology, live GitHub publication, or deployment. It
  may repair only reproduced correctness/gate defects within its explicit
  artifact inventory; new policy or artifacts require a plan revision/Q#.

### Minimal-mechanism decisions

1. **Reuse Git transport, do not sanitize copytree manually.** Excluding every
   ignored/admin artifact from raw copy would reimplement an inferior checkout.
2. **Retain non-Git copy fallback.** SessionManager fixtures/embedders may provide
   a plain source directory; only Git sources select the production clone path.
3. **One readiness implementation, thin entry aliases.** Core logic is NEW
   stdlib-only Python under `src/fa`; `scripts/bootstrap/workspace.py`, `just
   install`, and `just agent-bootstrap` are adapters, not duplicate engines.
4. **No background sync.** Foreground execution under an interprocess lock is
   simpler and still consumes zero LLM tokens.
5. **No cache topology before measurement.** A persistent uv cache alone does
   not preserve pre-commit environments; S7 measures both.
6. **No new daemon/service.** Provisioning roots already exist and are the active
   consumers.
7. **Trusted local identity, not an agent workaround.** Provisioning writes only
   repository-local `user.name`/`user.email`; global Git config remains forbidden
   and the LLM is not asked to repair identity.
8. **No speculative repair API in S1.** Fresh-clone creation ships first. Existing
   workspace repair is added in S2 with the entrypoint resume consumer that
   defines its preservation policy.
9. **One mutation executor, thin selectors.** NEW
   `scripts/run_slice_mutmut.py` owns staging, execution, classification, and
   artifacts. `run_targeted_mutmut.py` owns only Git-diff selection/fail-open
   admission; weekly CI selects configured scope. Neither reimplements result
   policy.
10. **Isolate instead of backup/restore.** Copy only validated declared inputs
    plus temporary configuration into a root-backed staging tree. Never write the
    repository's `pyproject.toml` and never use tests as mutation source.
11. **Use scoped Pyrefly directly.** It already exists in the locked dev set and
    emits valid mutmut-compatible JSON. A Mypy output adapter would add code only
    to work around the verified mutmut 3.6/Mypy 2.1 blank-line incompatibility.
12. **Compute verdict from closed statuses.** Raw mutmut rc means harness launch,
    not survivor absence. Parse the supported results surface, verify all counts
    sum to `total`, and derive the runner exit from that identity.

---

## 2. Current state → target state

### 2.1 Current-state facts

| Dimension | AS-IS |
| --- | --- |
| Deployment source | physical host clone `/srv/.../repo/...`, RO bind `/repo` |
| Session storage | physical host `/srv/.../sessions`, RW bind `/sessions` |
| Entrypoint fresh workspace | `git clone file:///repo`; branch created; pushurl missing |
| Manager fresh logical workspace | raw `shutil.copytree(/repo, /sessions/<id>)`; branch/config/artifacts copied |
| Explicit attach | opens manifest workspace; no readiness check |
| Startup/command override | publishes `.active`; no readiness check |
| Virtual env | absent in clean Git clone; per-workspace `.venv` ignored by Git |
| Hook sources | four tracked executable scripts after `ac5ba1a` |
| Hook seats | absent in fresh clone until manual installer |
| Pre-commit envs | current `just install` prewarms; lifecycle does not call it |
| Marker | tracked `.fa/host-bootstrap.json`; machine-specific semantics |
| uv cache | `/tmp/uv-cache` tmpfs 2 GiB |
| pre-commit cache | under `/home/fa/.cache` tmpfs 500 MiB |
| Failure policy | provisioning clone failures hard-stop; proposed readiness failure policy absent |
| Local gate authority | hooks bypassable; CI/human merge authoritative |
| Slice mutation | no explicit isolated runner; targeted wrapper edits live config and mutates changed tests |
| Mutation verdict | raw mutmut rc; survivors can produce success; type-filtered count absent from export |
| Readiness mutation scope | absent from permanent mutmut/gremlins source and test lists |

### 2.2 Target-state facts

- Git-backed managed workspaces are created by one verified provisioner
  contract with:

  ```text
  fetch URL = file:///repo
  push URL  = GitHub SSH
  branch    = agent/<session-id>
  identity  = First Agent <agent@first-agent.local> (repository-local)
  ```

- A plain-directory `source_workspace` retains copy fallback with an explicit
  non-production status and tests.
- Readiness is represented by a typed result, not an overloaded session
  manifest status.
- `manifest.status` remains `active|provisioning` under its current schema.
- Fresh and attached sessions invoke readiness before LLM/provider execution.
- Entrypoint workspaces invoke readiness before `.active` publication and
  before command override/auto-run.
- Hooks can invoke the same readiness engine without model participation.
- Workspace marker is ignored/untracked and atomic.
- Pre-commit cache sentinel is stored inside `PRE_COMMIT_HOME`; tmpfs reset makes
  the sentinel disappear and forces prewarm even when workspace marker persists.
- `uv sync --locked --extra dev` treats pyproject/lock drift as bootstrap
  degradation; bootstrap never rewrites `uv.lock`.
- Bootstrap unavailability is warn-only. A gate that successfully starts and
  reports code/test failure remains blocking.
- An explicit slice runner accepts tracked or untracked repo-relative production
  paths and explicit tests, stages them outside `/tmp`, never edits repository
  config/source/tests, bounds the process group, and emits atomic structured
  results plus exact actionable-mutant diffs.
- Mutation result identity is closed:

  ```text
  total = killed + type_invalid + survived + no_tests + timeout + suspicious
          + skipped + interrupted + segfault + not_checked
  ```

  Missing/unknown/mismatched status data is infrastructure failure, never green.
- `src/fa/workspace_bootstrap.py` and `tests/test_workspace_bootstrap.py` are
  permanent mutmut source/test authority; pytest-gremlins includes the readiness
  source as its Windows mirror.
- Linux mutmut uses scoped Pyrefly JSON filtering. Type-invalid mutants remain a
  separate reported count and are not relabeled as test-killed.

### 2.3 GAP ledger

| GAP | Verified gap | Owner | Verification |
| --- | --- | --- | --- |
| GAP1 | `file:///repo` clone has local push destination; GitHub pushurl producer absent | S1–S2 | T1–T3 |
| GAP2 | manager Git source uses raw copytree and preserves ignored/admin/main state | S1 | T1–T2 |
| GAP3 | fresh entrypoint workspace has no lifecycle readiness | S3 | T4, T8 |
| GAP4 | new/attached logical sessions have no readiness admission | S3 | T5–T6 |
| GAP5 | current bootstrap entrypoints duplicate sequencing and plain `uv run` may mutate/sync before stdlib code | S4 | T7 |
| GAP6 | marker does not model ephemeral pre-commit cache and is currently tracked | S4 | T6–T7 |
| GAP7 | self-bootstrap cannot help when seats are absent and has no typed fail-open mapping | S5 | T9–T12 |
| GAP8 | operator clone depends on VS Code permission/manual command; deployment mirror and dev clone roles are conflated in prose | S6 | T13 |
| GAP9 | no cold/warm uv + pre-commit latency/disk evidence | S7 | T14 |
| GAP10 | ADR/README/ops claim hardlink `--local` and old one-session model | S8 | T15 |
| GAP11 | no live path proves first managed commit/push has all gates before model work | S9 | T16 |
| GAP12 | probe v1 could execute/modify through diagnostic side paths | S0 | T0 |
| GAP13 | clean manager clones lack local identity; entrypoint gets it only in late post-setup; agent repair is denied | S1–S2 | T1–T3/T8 |
| GAP14 | no explicit slice runner; current wrapper misses in-flight/untracked source, mutates tests, rewrites live config, and trusts a survivor-blind rc | S3.5 | T17–T18 |
| GAP15 | no type-invalid filter; Mypy path is incompatible and repository-wide Pyrefly baseline is not clean | S3.5 | T18–T19 |
| GAP16 | readiness source/test are absent from permanent mutmut/gremlins scope and weekly evidence omits type-invalid counts | S3.5 | T19–T20 |
| GAP17 | no post-S6 claim ledger or clean-candidate integration gate verifies S1–S6 as one runtime system | S6.5 | T21–T24 |
| GAP18 | readiness subprocesses inherit pre-push stdin despite the noninteractive/preservation contract | S6.5 | T22–T23 |
| GAP19 | focused commit tests use minimal/fake gates while current real Mypy/Pyrefly findings block the shipped commit path | S6.5 | T22–T24 |
| GAP20 | CODEOWNERS parity test excludes real gate patterns and cannot verify S3.5 TCB governance | S6.5 | T21/T24 |

### 2.4 State transitions

```text
STATE workspace_git
  ABSENT
    → PROVISIONING
    → READY_GIT
  failure
    → CLEANED_PARTIAL + structured provisioning error

STATE workspace_readiness
  UNKNOWN | STALE
    → BOOTSTRAPPING (under lock)
    → READY
  environment/internal failure
    → DEGRADED (typed result + warning/log; no READY marker)

STATE local_gate
  READY + gate rc=0
    → ALLOW
  READY + gate rc!=0
    → BLOCK (preserve gate rc)
  DEGRADED bootstrap
    → WARN_ALLOW (operator-selected policy)

STATE slice_mutation
  DECLARED_INPUTS
    → VALIDATED → STAGED → RUNNING → CLASSIFIED
  CLASSIFIED + only killed/type_invalid
    → CLEAN (exit 0 + complete artifacts)
  CLASSIFIED + any actionable/unclassified status
    → ACTION_REQUIRED (exit 1 + exact names/diffs)
  invalid input/tool/config/process/result identity
    → INFRASTRUCTURE_FAILURE (exit 2/3; never mutation-clean)
```

Target liveness for G1–G6, G8, and G9: **L3**. G7 reaches L3 when the
measurement artifact exists; persistent cache itself is deferred.

---

## 3. Contracts

### CT1 — Git-backed session workspace provisioner

Type: function/module contract.

```text
NEW: fa.session.workspace.provision_git_workspace
IN:
  source: Path (existing normal non-bare Git worktree; `.git` is a directory)
  target: Path (must not exist)
  session_id: SessionManager-validated logical id
  push_url_override: str | None
OUT:
  GitWorkspaceState(
    source_revision: str,
    target_revision: str,
    branch: str,
    fetch_url: str,
    push_url: str,
    author_name: str,
    author_email: str,
  )
PRE:
  source is contained/approved by caller; target parent is caller-owned
POST:
  target is an independent clean checkout at the commit captured before clone
  branch == agent/<session_id> and passes `git check-ref-format --branch`
  origin.fetch == source.resolve().as_uri()
  origin.push == canonical GitHub SSH URL
  local user.name == "First Agent"
  local user.email == "agent@first-agent.local"
ERRORS:
  WorkspaceProvisionError with public read-only `.code`, `.stage`, `.detail`
  string attributes; `str(error) == "<code> [<stage>]: <detail>"`
SIDE EFFECTS:
  bounded subprocess Git commands; target directory creation/cleanup
```

Closed command order:

1. reject a pre-existing target before running Git;
2. verify `source/.git` is a directory and capture exactly one
   `source_revision` with `git -C <source> rev-parse --verify HEAD^{commit}`;
3. derive `branch=agent/<session_id>` and run
   `git check-ref-format --branch <branch>` **before target creation**; reject an
   invalid ref, do not sanitize/map it;
4. resolve the push authority: a non-empty explicit override wins, otherwise
   read `git -C <source> remote get-url --push origin`, then apply CT2;
5. run `git clone --no-checkout <source.resolve().as_uri()> <target>`;
6. run `git -C <target> switch -c <branch> <source_revision>`; the captured
   revision, not a second read of live `/repo`, is the snapshot authority;
7. run `git -C <target> remote set-url --push origin <canonical-push-url>`;
8. run `git -C <target> config --local user.name "First Agent"` and the analogous
   `user.email` command;
9. read back branch, fetch URL, push URL, target commit, local identity, and
   `git status --porcelain=v1 --untracked-files=all`; return only if every field
   matches and status is empty.

All commands are argument vectors with `shell=False`, `text=True`, captured
stdout/stderr, `GIT_TERMINAL_PROMPT=0`, and a module-private 120-second timeout.
No full environment/config is logged. Error detail is control-safe, credential-
redacted, and capped at 4096 characters. After clone creates the target, a
success-guarded `finally` removes it on every unwind, including
`KeyboardInterrupt`/`SystemExit`, while re-raising those `BaseException` types;
this composes with the manager's existing `finally` rollback at
`manager.py:292-305`.

Exact private error codes:

```text
source_not_git
source_revision_unavailable
target_exists
invalid_branch
push_url_unavailable
push_url_invalid
git_unavailable
git_timeout
git_command_failed
postcondition_failed
```

Exact `stage` values are likewise closed:

```text
validate_source
capture_source_revision
validate_branch
resolve_push_url
clone
checkout_branch
set_push_url
set_identity
verify_postconditions
```

`SessionManager._provision_workspace(workspace_path, *, session_id) -> bool`
retains its current `True`-on-success/no-`False` contract and dispatches to this
function only when its validated `source_workspace/.git` is a directory.
It catches every `WorkspaceProvisionError` and raises the existing public
`SessionManagerError("workspace_provision_failed", "<private-code>: <safe-detail>")`
from it. This adds no new public manager error code. The existing manager-owned
plain-directory `shutil.copytree(..., symlinks=True)` block and its current
cleanup mapping stay in place for non-Git fixtures/embedders.

`SessionManager.__init__` gains keyword-only `repo_push_url: str | None = None`.
`src/fa/cli.py:_session_manager_for_args` passes `FA_REPO_PUSH_URL` through:
unset or exactly empty means `None`; any non-empty value, including whitespace,
is preserved for CT2 validation rather than silently ignored. Existing direct
constructors remain source-compatible through the default.

`src/fa/session/__init__.py` remains unchanged: S1 imports the concrete helper
inside `manager.py` and does not expand the lazy public session API.

Kill-check: removing pushurl, branch, identity, captured-revision checkout, or
clone producer fails named T1 tests; replacing Git dispatch with copytree fails
ignored-file/branch assertions. Raising a new manager error code fails the
existing manifest error-inventory test.

### CT2 — B2 remote routing

Type: data/invariant + security contract.

```text
AUTHORITY:
  fetch snapshot authority = local /repo
  publication authority = configured GitHub SSH repository
FETCH:
  file:///repo
PUSH:
  git@github.com:first-agent-dev/First-Agent-dev.git by accepted default
  optional explicit operator override for fork/non-default deployment
FAILURE:
  unsupported/unresolvable source URL → structured warning/error;
  never silently set pushurl=file:///repo
```

`normalize_push_url(raw: str) -> str` returns the canonical SSH value or raises
`WorkspaceProvisionError(code="push_url_invalid", stage="resolve_push_url", ...)`.
URL derivation is closed rather than delegated to Git heuristics:

- explicit `FA_REPO_PUSH_URL` override wins; otherwise read the source mirror's
  `remote get-url --push origin` as publication authority;
- accept only these complete, credential-free input shapes and canonicalize all
  of them to `git@github.com:<owner>/<repo>.git`:
  - `git@github.com:<owner>/<repo>[.git]`;
  - `ssh://git@github.com/<owner>/<repo>[.git]`;
  - `https://github.com/<owner>/<repo>[.git]`;
- `<owner>` and `<repo>` are one non-empty path segment each, made only of
  ASCII letters, digits, `.`, `_`, or `-`; query, fragment, extra segments,
  leading/trailing whitespace, control characters, and dot-only segments fail;
- HTTPS userinfo, non-`git` SSH users, non-GitHub hosts, local/file paths, and
  unsupported schemes return `push_url_invalid`; its stable detail is exactly
  `push URL must be a credential-free GitHub HTTPS or SSH repository URL` and
  never interpolates the rejected input;
- missing source `origin`/push URL returns `push_url_unavailable`;
- live S0 evidence fixes the default result as
  `git@github.com:first-agent-dev/First-Agent-dev.git`; there is no separate
  hard-coded fallback if source authority is absent.

The S1 real-push test does **not** relax this production contract. It stores the
canonical SSH URL, then invokes Git with command-local
`url.file://<bare>.insteadOf=<canonical-ssh-url>` and
`protocol.file.allow=always`. A local bare remote receives the ref without
writing test-only config into the workspace or contacting GitHub.

### CT3 — workspace readiness function

Type: function/module + error/CLI contract.

```python
class ReadyStatus(str, Enum):
    READY = "ready"
    DEGRADED_ENVIRONMENT = "degraded_environment"
    DEGRADED_INTERNAL = "degraded_internal"

@dataclass(frozen=True, slots=True)
class ReadyState:
    status: ReadyStatus
    fingerprint: str | None
    reason_code: str
    log_path: Path
    repaired: bool
    elapsed_ms: int

ensure_workspace_ready(workspace: Path) -> ReadyState
check_workspace_ready(workspace: Path) -> ReadyState
```

`check_workspace_ready` is read-only: it validates workspace/tool/project
Python/fingerprint/marker/hooks/cache-sentinel/`uv sync --check` through the same
helpers as the ensure fast path, but does not create `.fa`, acquire the lock,
append the log, remove/write the marker, install hooks, sync, prewarm, or write a
sentinel. Current state returns `ready_fast_path`; any active-state mismatch
returns existing `locked_check_failed` with the computed fingerprint. Validation,
tool, and fingerprint failures retain their existing reason mappings.

Closed reason codes and status mapping:

```text
READY:
  ready_fast_path
  ready_repaired
DEGRADED_ENVIRONMENT:
  lock_timeout
  tool_missing
  sync_failed
  sync_timeout
  precommit_prewarm_failed
  precommit_prewarm_timeout
  locked_check_failed
  hook_status_failed
DEGRADED_INTERNAL:
  invalid_workspace
  fingerprint_failed
  state_io_failed
  unexpected_internal_error
```

The function is total for ordinary `Exception`: it converts failures to one of
the states above, appends CT8 detail when the log is writable, and never raises
through lifecycle/hook
admission. It does not catch `KeyboardInterrupt`, `SystemExit`, or process-kill
signals. `repaired=True` only when the current call completed at least one
successful mutation and reached READY; every degraded result sets it `False`.
`elapsed_ms` is monotonic elapsed wall time rounded down to an integer.

CLI contract:

```text
python -m fa.workspace_bootstrap ensure --workspace <absolute-or-relative-path>
python -m fa.workspace_bootstrap check  --workspace <absolute-or-relative-path>
exit 0  = READY
exit 75 = DEGRADED_ENVIRONMENT
exit 70 = DEGRADED_INTERNAL
stdout  = one JSON object containing the six ReadyState fields
stderr  = one [WORKSPACE_BOOTSTRAP] summary only for degraded results
```

Relative CLI paths resolve against CWD. JSON uses the enum string, absolute
`log_path`, integer `elapsed_ms`, boolean `repaired`, and JSON null fingerprint
when unavailable. Lifecycle Python callers consume the object directly.
Entrypoint/hook shell callers treat **every non-zero return from the bootstrap
invocation itself**, including command-not-found before the CLI starts, as
warn/fail-open; they do not wrap or rewrite the later quality-gate command.

Fixed bounds:

- `.fa/bootstrap.lock` acquisition uses `fcntl.flock(LOCK_EX | LOCK_NB)` every
  100 ms for at most 120 seconds measured by monotonic time; timeout returns
  `lock_timeout`;
- `uv sync` and `pre-commit install-hooks` each have a 900-second subprocess
  timeout;
- uv version/check and hook status/install subprocesses each have a 120-second
  timeout;
- every subprocess sets `GIT_TERMINAL_PROMPT=0` where Git may be reached, captures
  bounded output, and has no `shell=True`.

Transaction order:

1. resolve the workspace and require a First-Agent Git checkout containing
   `knowledge/llms.txt`, `pyproject.toml`, `uv.lock`, and
   `.pre-commit-config.yaml`; otherwise return `invalid_workspace`;
2. create `.fa` privately and acquire `.fa/bootstrap.lock` with the bound above;
3. compute CT4 fingerprint; failure returns `fingerprint_failed`;
4. fast-validate `.venv/bin/python`, four executable/current seats,
   `uv sync --locked --extra dev --check`, and the CT4 cache sentinel; if all
   pass, return `ready_fast_path` without a network-capable setup command;
5. remove any stale `.fa/ready-state.json` before the first repair mutation;
6. install/repair minimal custom seats from the explicit **workspace source**,
   never the image package directory;
7. run `uv sync --locked --extra dev` with `UV_LINK_MODE=copy`; non-zero/timeout
   maps to `sync_failed`/`sync_timeout` and never rewrites `uv.lock`;
8. run `<workspace>/.venv/bin/pre-commit install-hooks`; non-zero/timeout maps to
   the corresponding prewarm reason;
9. install custom seats again as final outer wrappers;
10. require the locked uv `--check`, exact hook status, executable project Python,
    and sentinel parent availability;
11. atomically write the cache sentinel, then CT4 workspace marker, then append
    CT8 READY summary and return `ready_repaired`.

The readiness engine performs no LLM call and never dumps its environment. Its
only potentially network-capable operations are the explicit uv sync and
pre-commit environment preparation required by readiness.

### CT4 — readiness marker and cache sentinel

Type: data contract.

Workspace marker (ignored, NEW):

```json
{
  "schema": 2,
  "state": "ready",
  "fingerprint": "sha256:...",
  "project_python": "3.13",
  "uv_version": "...",
  "checked_at": "..."
}
```

Pre-commit sentinel (NEW):

```text
path    = ${PRE_COMMIT_HOME:-~/.cache/pre-commit}/.fa-ready/<fingerprint>
content = <fingerprint> + "\\n"
mode    = 0600
write   = temp + flush/fsync + os.replace
```

Fingerprint inputs:

- bootstrap schema/version;
- `pyproject.toml` bytes;
- `uv.lock` bytes;
- `.pre-commit-config.yaml` bytes;
- four hook source bytes/modes;
- hook installer/status utility bytes;
- actual project Python minor;
- uv version.

Authority: matching marker is a cache hint; executable seats, project
interpreter, locked environment check, and pre-commit sentinel are active
consumers. A marker alone never proves readiness.

Write protocol: remove the stale READY marker before repair; write a new marker
only after every final validation and sentinel write succeeds; temp file,
flush/fsync, chmod 0600, then `os.replace`. A degraded call leaves no marker for
its fingerprint and records degradation only in `ReadyState` + CT8 append log.
No tracked or `state != "ready"` marker exists.

### CT5 — hook bootstrap/gate policy

Type: signal/security contract.

Producer: identical self-contained bootstrap prelude in each of the four tracked
hook scripts.

Consumer: the hook's normal gate body.

```text
bootstrap READY
  → execute normal hook body
bootstrap command rc != 0 (typed degraded rc or command-not-found)
  → print stable [WORKSPACE_BOOTSTRAP] warning with reason/log path when known
  → return 0 without executing unavailable local gate
normal gate rc != 0
  → preserve and return that rc (BLOCK)
```

The operator explicitly selected fail-open for bootstrap unavailability. The
prelude captures only the bootstrap command rc; after rc=0 it `exec`s/runs the
normal gate outside that branch and returns its rc unchanged. Thus accepting an
unexpected bootstrap rc does not catch or rewrite a quality-gate failure.

Self-repair is secondary: managed provisioning installs seats first. An arbitrary
unmanaged clone with no seat remains outside the guarantee.

Kill-check: removing bootstrap header fails T9; broadening the fail-open branch to
swallow normal gate failures fails T10–T12.

### CT6 — lifecycle readiness admission

Type: two-sided signal contract.

Producers:

- entrypoint fresh/resumed workspace before `.active` publication;
- SessionManager after new workspace provisioning and on explicit attach;
- host dev bootstrap aliases/tasks.

The manager seam is mandatory and exact:

```text
SessionManager.__init__(
  ...,
  workspace_preparer: Callable[[Path], ReadyState] | None = None,
)
```

The default is `None`, preserving generic/plain-directory embedding tests.
`src/fa/cli.py:_session_manager_for_args` is the production composition root and
passes NEW private `_prepare_managed_workspace(path) -> ReadyState`. That wrapper
calls `ensure_workspace_ready`, prints one CT8 warning to stderr only when status
is degraded, and returns the object. `_new_session` invokes the callback after the
workspace and session DB exist but before the active manifest is committed;
`_attach_session` invokes it after manifest/workspace/DB validation but before
`last_used_at` is written. The callback contract is total: it returns READY or a
typed degraded result and does not raise. Manager does not add a manifest field
or reinterpret the result.

The entrypoint invokes readiness independently before `.active`; a following
`fa run --session-id` may make a second call, which must take CT3's idempotent
fast path. This duplication is intentional composition-root coverage, not a
second implementation.

Consumers:

- entrypoint command override/auto-run continues after READY or warns on
  DEGRADED;
- CLI callback completion precedes provider-chain construction and every model
  call; a test records the callback/build/call ordering rather than relying on
  source order alone;
- hooks consume resulting marker/sentinel.

No session manifest status change. Optional bootstrap metadata in manifest is
explicitly deferred; log/marker are the current consumer surfaces.

### CT7 — operator development clone readiness

Type: lifecycle contract.

```text
workspace = ~/First-Agent-dev (operator-chosen canonical dev clone)
entrypoints:
  explicit python bootstrap wrapper
  just install
  just agent-bootstrap
  VS Code folderOpen convenience task
```

The explicit wrapper/just aliases are authoritative recovery paths; VS Code is
best-effort because automatic task permission is user-controlled. Deployment
`/srv/...` does not receive dev hooks/venv as a required invariant.

### CT8 — bootstrap observability

Type: signal contract.

Producer: readiness transaction.

Consumers:

- operator reads `<workspace>/.fa/bootstrap.log` and command warning;
- hooks preserve CLI degraded stderr; if the wrapper cannot start, they print a
  generic prefix + intended log path;
- tests parse ReadyState/exit code;
- live sheet records timings/status without secret content.

Stable warning prefix:

```text
[WORKSPACE_BOOTSTRAP]
```

`<workspace>/.fa/bootstrap.log` is mode 0600, append-only NDJSON written while
the bootstrap lock is held. Each record has ISO-8601 UTC timestamp, status,
reason code, resolved workspace path, command stage, redacted argv, return code,
and elapsed milliseconds. Captured stdout/stderr fields are optional, each
control-safe and capped at 4096 characters. If even the log path cannot be
created, return `state_io_failed` with that intended path and emit the warning
without recursively attempting another workspace mutation. No environment dump,
remote credentials, model config, task text, or provider data.

### CT9 — cache measurement artifact

Type: performance contract.

NEW measurement report records:

- cold/warm `uv sync --locked --extra dev` wall time;
- cold/warm `pre-commit install-hooks` wall time;
- total readiness wall time;
- `.venv`, uv cache, pre-commit cache sizes;
- filesystem types for `/sessions`, uv cache, pre-commit cache;
- container/image/commit identity.

The report decides, but does not itself add, persistent mounts.

### CT10 — isolated slice mutation runner

Type: TCB CLI/module contract.

Producer: NEW `scripts/run_slice_mutmut.py:main` backed by one typed internal
`run_slice(request: SliceRequest) -> SliceResult` authority. Consumers:

- an operator/agent invokes explicit mode during a bounded implementation slice;
- `scripts/run_targeted_mutmut.py` supplies auto-discovered production paths and
  permanent configured tests;
- `.github/workflows/tests.yml` supplies `--configured-scope` for the existing
  weekly advisory run.

CLI shape:

```text
python scripts/run_slice_mutmut.py \
  --source <repo-relative production file-or-directory> [--source ...] \
  --test <repo-relative test file-or-directory> [--test ...] \
  [--also-copy <repo-relative dependency file-or-directory> ...] \
  [--tmp-root <absolute root-backed directory>] \
  [--result-json <repo-relative output>] \
  [--diff-report <repo-relative output>] \
  [--max-children <positive int>] \
  [--timeout-seconds <positive int>]

python scripts/run_slice_mutmut.py --configured-scope [same execution/output flags]
```

`--configured-scope` is mutually exclusive with explicit source/test/copy
selection and reads those lists from validated `[tool.mutmut]`. Explicit mode
requires at least one `--source` and one `--test`; omitted `--also-copy` is an
empty caller list, while readiness callers pass `src/fa` explicitly. Defaults:

```text
tmp root       = repository parent/.fa-mutmut-runs
result JSON    = mutants/mutmut-slice-result.json
diff report    = mutants/mutmut-slice-diffs.md
max children   = os.cpu_count() or 4
timeout seconds= 3600 (targeted wrapper passes its existing 600-second budget)
```

Input invariants:

- source resolves under repository `src/`; test resolves under `tests/`;
  `also_copy` resolves inside the repository;
- every input exists, is a regular file/directory, and no selected path or
  descendant symlink escapes/follows outside the repository;
- source and test sets are disjoint; a test path can never enter generated
  `source_paths`; exact duplicates and ancestor/descendant overlap inside either
  set are invalid, while `also_copy=src/fa` may overlap source intentionally;
- execution requires POSIX/fork; non-POSIX exits 2 before staging and directs the
  caller to the permanent pytest-gremlins mirror;
- every path must round-trip strict UTF-8 for TOML/JSON artifact authority;
- values are passed as list-form argv only; no shell and no config-derived
  executable string;
- output paths are repository-relative under ignored `mutants/`, and parent
  symlinks are rejected before atomic write;
- explicit paths need not be Git-tracked, staged, or committed.

Mechanism:

1. require POSIX, resolve mutmut and Pyrefly from PATH/`.venv/bin`, record exact
   versions, and require the lock-compatible `mutmut, version 3.6.0` before
   staging;
2. preflight scratch capacity from source/copy inputs plus full test-oracle tree
   and bounded mutmut headroom;
3. make a unique mode-0700 directory under the root-backed tmp root;
4. copy declared source/copy inputs, the base `pyproject.toml`, and the complete
   `tests/` oracle/support tree without following symlinks; pytest selection
   remains the exact declared `--test` list so shared fixtures/imports exist
   without executing or mutating unselected tests;
5. replace only the staged `[tool.mutmut]` section using a section-aware
   generator, validate the completed document with `tomllib`, and set:
   - exact source/test/copy lists;
   - scoped CT11 Pyrefly command derived from source inputs;
   - existing reviewed timeout/scalar options from the permanent table;
6. byte-compare the real `pyproject.toml`, all source inputs, and all test inputs
   with their pre-run digests before publishing a result;
7. run `mutmut run` in a new process group, enforcing parent wall timeout with
   TERM then KILL cleanup; native mutmut clean-test and forced-fail phases remain
   mandatory;
8. run `mutmut results` and `export-cicd-stats`, parse only the closed mutmut 3.6
   statuses, and reject malformed, duplicate, unknown, missing, or count-inexact
   data;
9. call `mutmut show <name>` for actionable statuses only and build one exact
   diff report; type-invalid names remain in JSON but do not inflate the diff
   report;
10. atomically write completed artifacts, then remove staging in `finally` on
    success, actionable result, harness failure, timeout, and interrupt.

Result schema (`schema_version=1`) includes:

- `completed`, `verdict=clean|action_required|infrastructure_failure`;
- mutmut/Pyrefly versions, configured/explicit mode, normalized source/test/copy
  paths, start/end/duration, and whether type filtering ran;
- counts for `total`, `killed`, `type_invalid`, `survived`, `no_tests`,
  `timeout`, `suspicious`, `skipped`, `interrupted`, `segfault`, and
  `not_checked`;
- non-killed mutant records with exact name/status and optional diff-report
  anchor; no environment, test output, remote URL, credential, or model/task
  data;
- a non-type-invalid mutation score as informational data only, never the gate
  authority.

Exit contract:

```text
0 = completed; every mutant is killed or type_invalid
1 = completed; one or more actionable/unclassified statuses exist
2 = invalid CLI/input/config contract
3 = tool missing/wrong version, subprocess failure/timeout, malformed results,
    count mismatch, artifact failure, or source/config/test mutation detected
```

A missing artifact cannot accompany exit 0/1. Raw `mutmut run` rc 0 is never a
clean verdict. No result baseline, threshold, or equivalent allowlist exists.

Producer kill-checks:

- replace `run_targeted_mutmut.py`'s call to `run_slice` with success: T17 fails;
- replace workflow invocation with raw `mutmut run`: T20 fails;
- force raw mutmut rc 0 plus a survivor: T17/T18 require runner rc 1;
- delete type-invalid from count closure: T18/T19 fail exact identity.

### CT11 — scoped type-invalid mutant filtering

Type: configuration/classification contract.

Producer: `[tool.mutmut].type_check_command` and CT10's explicit-slice generated
command. Authority is direct Pyrefly invocation, not a wrapper:

```toml
type_check_command = [
  "pyrefly", "check",
  <exact source_paths entries in the same order>,
  "--output-format=json",
  "--summary=none",
  "--progress-bar=no",
]
```

The literal `"pyrefly"` token is required because mutmut 3.6 selects its JSON
parser by exact command-list membership. It runs from mutmut's `mutants/`
directory; `also_copy = ["src/fa"]` provides sibling imports. Permanent config
has a static test requiring the Pyrefly positional path list to equal
`source_paths`; explicit mode derives the list mechanically.

Semantics:

- valid JSON with zero errors continues mutation tests;
- valid JSON diagnostics may accompany Pyrefly's expected nonzero status; a
  generated mutant whose error maps to that mutant function is `type_invalid`,
  not killed and not survived;
- baseline type errors, malformed/missing JSON, an error outside a mutated
  function, or missing/unlaunchable Pyrefly are infrastructure failure;
- filtered count is always exposed separately and remains in `total`;
- type filtering does not prove runtime irrelevance. It removes statically
  invalid variants from the test-adequacy denominator while retaining names for
  audit.

Mypy is not an alternate path in S3.5: the locked 2.1/3.6 combination is
source-proven incompatible on clean JSON output. Repository-wide Pyrefly is not
used because its two unrelated baseline errors would make mutmut 3.6 fail to map
an error to a mutated function.

Kill-check: remove `type_check_command` from the real three-mutant fixture. T18's
oracle changes from `killed=2,type_invalid=1` to
`killed=3,type_invalid=0` and fails even though both variants have zero
survivors.

### CT12 — permanent readiness mutation scope and CI evidence

Type: configuration/wiring contract.

`pyproject.toml` target:

```toml
[tool.mutmut]
source_paths = [
  # existing entries unchanged,
  "src/fa/workspace_bootstrap.py",
]
pytest_add_cli_args_test_selection = [
  # existing entries unchanged,
  "tests/test_workspace_bootstrap.py",
]
also_copy = ["src/fa"]
type_check_command = [
  "pyrefly", "check",
  # exact source_paths list,
  "--output-format=json", "--summary=none", "--progress-bar=no",
]

[tool.pytest-gremlins]
paths = [
  # existing entries unchanged,
  "src/fa/workspace_bootstrap.py",
]
```

Invariants:

- mutmut and gremlins production path sets are exactly equal;
- each permanent source family has at least one selected authoritative test;
- readiness maps to `tests/test_workspace_bootstrap.py` explicitly;
- readiness dependencies are present in mutmut staging via `also_copy`;
- weekly workflow invokes CT10 `--configured-scope`, publishes schema-v1 JSON
  and actionable diff report, and keeps job-level advisory semantics;
- targeted wrapper intersects only changed production paths with permanent
  `source_paths`; changed tests may be staged as oracles but never mutated;
- discovery includes committed branch delta, index/worktree delta, and untracked
  Python files, with path containment and the existing 20-production-file cap.

The known filtered readiness baseline is evidence, not a pass allowlist:

```text
874 total = 329 killed + 540 type_invalid + 5 equivalent survivors
```

A configured run therefore exits 1 until those five are explicitly reviewed on
that run. S3.5 does not suppress or auto-accept them. Weekly CI remains advisory;
targeted users may use the already-existing explicit skip only after reviewing
the emitted five diffs.

Producer kill-checks:

- delete readiness source, test, gremlins mirror, `also_copy`, or type command:
  T19 config-contract test fails;
- remove configured runner call from weekly workflow: T20 fails;
- remove worktree/untracked discovery or re-admit `tests/` as source: T17 fails.

### CT13 — integrated S1–S6 production-acceptance ledger

Type: review/data/invariant contract.

Producer: S6.5 forensic review over the exact candidate diff and real
composition roots. Consumer: S7 admission and later S8/S9 handoff. S7 must not
start while any S1–S6 claim is `partial`, `unsafe`, `absent`, `unverified`, or
has an unexplained red blocking gate.

NEW A54 review rows have this closed shape:

```text
claim_id, intent, slice, artifacts, producer, consumer, runtime_paths,
current_behavior, target_behavior, failure_behavior, evidence,
test_class, producer_kill, verdict, severity, remediation, final_status
```

`verdict` is one of `present|partial|absent|unsafe|unverified`; `severity` is
`blocker|high|medium|low|none`; `final_status` is
`verified|deferred-with-owner|blocked`. Production acceptance permits only
`verified`, except external GitHub/deployment claims explicitly owned by S9.
Every row must cite file+symbol/line plus command output or a named test; prose
alone is invalid evidence.

Review rubric is mandatory for each touched production artifact:

- minimal/single authority and correct composition-root wiring;
- validated inputs, path/credential/permission boundary, and redaction;
- atomicity, rollback, idempotency, concurrency, and ownership;
- timeout, stdin, stdout/stderr, environment, and child-process cleanup;
- typed failure/fail-open boundary and operator observability;
- Linux/container/host assumptions and explicit unsupported matrices;
- real C1/C2/C3 coverage, producer kill-check, and C4 where logic is dense;
- clean-candidate gate, docs/recovery, and rollback truthfulness.

Deterministic consumers:

- T21 validates ledger completeness against S1–S6 artifact/claim inventories;
- T22/T23 prove actual runtime and stdin behavior;
- T24 requires clean gates and kills critical producers;
- any new policy-sensitive remediation appends a blocking Q# and stops.

Kill-check: delete manager Git dispatch, lifecycle readiness admission, hook
prelude, stdin isolation, mutation workflow producer, or an S6 authority claim;
its named test/ledger completeness assertion fails and S7 remains blocked.

---

## 4. Path and flag matrix

### 4.1 Runtime paths

| Path | Trigger | Current site | Target | Step | Verification |
| --- | --- | --- | --- | --- | --- |
| P1 | container start, fresh startup workspace | `fa-entrypoint.sh:160-178` | CT1+CT2+CT3 before `.active` | S2–S3 | T3, T8 |
| P2 | container start, existing startup workspace | `fa-entrypoint.sh:179-182` | repair B2/readiness, preserve commits | S2–S3 | T3, T6 |
| P3 | no-id `fa run`, Git `/repo` | manager new/provision | clean Git + identity + ready | S1, S3 | T1, T5 |
| P4 | explicit attach to existing session | `SessionManager._attach_session` | readiness attempt, no re-clone | S3 | T6 |
| P5 | non-Git SessionManager source | `_provision_workspace` | controlled copy fallback | S1 | T2 |
| P6 | operator dev fresh/stale clone | host aliases/VS Code | same readiness engine | S4, S6 | T7, T13 |
| P7 | ready hook invocation | four hook scripts | no sync; execute normal gate | S5 | T9–T12 |
| P8 | degraded hook invocation, missing uv/network | four hook scripts | warning + allow | S5 | T10–T12 |
| P9 | actual quality finding | hook normal body | preserve blocking rc | S5 | T10–T12 |
| P10 | pyproject/lock drift | readiness uv call | no lock rewrite; degraded warning | S4 | T7 |
| P11 | tmpfs pre-commit cache lost, workspace marker remains | attach/resume | sentinel miss forces prewarm | S4 | T6–T7 |
| P12 | missing/invalid `.active` diagnostic | probe | safe report, no path escape/import | S0 | T0 |
| P13 | old session local-only pushurl | attach/resume provision repair | set B2 only when missing/local | S2 | T2–T3 |
| P14 | user-customized non-local pushurl | attach/resume | preserve + warning, no clobber | S2 | T2 |
| P15 | CI checkout | GitHub workflows | hooks not required; CI gates unchanged | S6 | T13 |
| P16 | explicit tracked or untracked source + explicit tests | no current site | isolated strict slice run; tests remain oracle | S3.5 | T17–T18 |
| P17 | mutmut rc 0 with survivor/no-test/timeout/unknown status | current wrapper trusts rc | synthesize action-required/infrastructure exit and artifacts | S3.5 | T17–T18 |
| P18 | type-invalid generated mutant | no current filter | scoped Pyrefly classification, separate denominator | S3.5 | T18–T19 |
| P19 | changed source/test in index, worktree, or untracked set | `base...HEAD` only | production-only union; targeted delegate | S3.5 | T17 |
| P20 | weekly configured mutation | raw mutmut + incomplete export | configured CT10 report; advisory policy unchanged | S3.5 | T19–T20 |
| P21 | exact S1–S6 candidate in isolated clean Git checkout | no current integrated root | real locked readiness + real commit hooks + clean full gate | S6.5 | T21–T24 |
| P22 | pre-push receives ref-update stdin while readiness launches children | inherited stdin in `_run_process` | readiness children get DEVNULL; normal gate gets original bytes exactly | S6.5 | T22–T23 |
| P23 | current full Mypy/Pyrefly/CODEOWNERS gates | classified red baselines | minimal fixes, zero diagnostics, semantic governance parity | S6.5 | T21/T24 |
| P24 | review discovers policy-sensitive or out-of-inventory finding | no bounded review stop gate | append blocking Q#/plan revision; no opportunistic fix | S6.5 | T21 |

Coverage gate: 24/24 paths have a step and verification.

### 4.2 Environment/matrix rows

| Matrix | Environment/config | Proves | Coverage |
| --- | --- | --- | --- |
| M1 | container, cold tmpfs uv + pre-commit cache | first-session cost/readiness | S7/T14 |
| M2 | container, warm caches | idempotent fast path | S4/S7, T6/T14 |
| M3 | container restart, persisted workspace marker + lost cache sentinel | no false ready | S4, T6 |
| M4 | operator `~/First-Agent-dev` with uv/just present | host readiness | S6, T13 |
| M5 | operator clone missing uv/just | stable warning/recovery | S6, T13 |
| M6 | Git source with HTTPS upstream | deterministic GitHub SSH normalization | S1, T1 |
| M7 | Git source with SSH upstream and empty HOME/identity env | SSH canonicalization + trusted local commit identity | S1, T1 |
| M8 | explicit `FA_REPO_PUSH_URL` through CLI composition root | forks/non-default controlled repo | S1, T1 |
| M9 | non-Git source fixture | copy fallback compatibility | S1, T2 |
| M10 | CI=true | no hook-seat requirement; CI remains authority | S6, T13 |
| M11 | explicit slice: tracked vs staged/unstaged vs untracked production | same isolated bytes reach mutmut; no Git-presence precondition | S3.5, T17–T18 |
| M12 | result: all killed/type-invalid vs survivor vs malformed/harness failure | exits 0/1/3 and artifacts are non-vacuous | S3.5, T17–T18 |
| M13 | type checker: scoped clean/type-invalid vs unrelated full-project errors | direct scoped Pyrefly only; errors stay observable | S3.5, T18–T19 |
| M14 | consumer: explicit CLI vs targeted pre-push vs weekly configured CI | one executor, three selectors, unchanged advisory policy | S3.5, T17–T20 |
| M15 | clean isolated candidate, Linux/POSIX, real uv/just/pre-commit | merge/runtime readiness without dirty-worktree ambiguity | S6.5, T22/T24 |
| M16 | pre-push stdin with a readiness child that attempts to read | child isolation + exact normal-body forwarding | S6.5, T23 |
| M17 | effective hooks path/default seat plus custom/outside-path discovery | default path verified; policy-sensitive custom path triggers P24/Q# | S6.5, T21 |

---

## 5. Step-by-step implementation

### Step S0 — run and record the corrected read-only server preflight — EXECUTED

Traces-to: G7, G8; GAP7, GAP9, GAP12; CT8, CT9.

Depends-on: none. Parallelizable-with: none.

Target liveness: probe safety L1→L3; server facts unverified→recorded.

Edit:

- `fa-bootstrap-preflight-probe.sh` — operator-facing read-only probe, created
  outside production code at repository root for immediate use.
- plan §Preflight/Execution record — append exact safe output summary after run.

Degree of freedom closed:

- diagnostics could mutate Git index, import agent-controlled code, escape active
  path containment, terminate incorrectly on missing `.active`, or print remote
  credentials/control characters.

Deterministic mechanism:

- absolute default paths; command/container preflight;
- strict `/sessions/<validated-id>` shape;
- `GIT_OPTIONAL_LOCKS=0` + `core.fsmonitor=false`;
- `python3 -I -B` from image/default cwd, never agent-writable cwd;
- remote userinfo redaction + `%q`/`repr` terminal-safe values;
- no LLM/session creation, no general env/config/file-content output.

Do:

1. Run `bash -n` and ShellCheck if available.
2. Copy/run as normal `fa` user from any cwd:

   ```bash
   bash ~/First-Agent-dev/fa-bootstrap-preflight-probe.sh
   ```

3. Record checkout realpaths/inodes, remotes, mounts, active workspace,
   manager roots, hooks/venv, and cache sizes.
4. Compare actual with P1–P14 assumptions. Any contradiction becomes a blocking
   plan revision, not an opportunistic code fix.

Do-not:

- do not run `fa run`, create a test session, clean caches, print secret files,
  or mutate Git remotes during S0.

Exit criteria:

- [x] `bash -n` passes;
- [x] ShellCheck warning level is unavailable and explicitly recorded; repository
  shell syntax plus targeted mock safety checks pass;
- [x] output ends `probe=complete`;
- [x] deployment mirror remains clean; operator clone's two existing dirty lines
  are recorded for preservation before S6;
- [x] Q1 is resolved with recorded facts.

Kill-check: set `.active` to an invalid contained shape in a disposable script
fixture; probe must skip active Git/Python inspection and print a warning.

### Step S1 — add the Git-aware logical-session provisioner — EXECUTED

Traces-to: G1, G2; GAP1, GAP2, GAP13; CT1, CT2.

Depends-on: S0. Parallelizable-with: none.

Target liveness: clean logical-session Git workspace L0→L3.

Edit exactly:

- NEW `src/fa/session/workspace.py`:
  - immutable `GitWorkspaceState` with the seven CT1 fields;
  - `WorkspaceProvisionError` with the closed CT1 codes/stages;
  - `normalize_push_url`;
  - `provision_git_workspace`;
  - private subprocess/read-back/redaction/cleanup helpers only when consumed by
    those three public symbols;
- `src/fa/session/manager.py`:
  - constructor field `repo_push_url`;
  - `_provision_workspace(workspace_path, *, session_id)` Git dispatch/error map;
  - `_new_session` passes its already validated owner id;
  - retain the existing non-Git copy block in this module;
- `src/fa/cli.py:_session_manager_for_args` — pass the optional environment
  override into `SessionManager`;
- NEW `tests/test_session_workspace_provisioning.py` — CT1/CT2 tests over real
  repositories and a local bare publication remote;
- `tests/test_session_lifecycle.py` — keep and, where necessary, strengthen the
  manager-owned generic fallback/rollback oracle;
- `tests/test_cli.py` — composition-root propagation of `FA_REPO_PUSH_URL`.

Explicitly unchanged in S1:

- `src/fa/session/__init__.py` (no new package re-export);
- `scripts/fa-entrypoint.sh` and `scripts/fa-post-setup.sh` (S2 consumers);
- Compose/env templates (existing `docker-compose.fa.yml:64-68` already injects
  non-secret `.env.fa` controls into the agent container);
- readiness/bootstrap code (S3).

Degree of freedom closed:

- production source type implicitly selected raw copy behavior; branch/remotes,
  identity, and ignored/admin files varied with deployment filesystem state;
- `FA_REPO_PUSH_URL` existed only as prose;
- a live `/repo` update could invalidate a post-clone current-HEAD comparison;
- branch validity and public error mapping were unspecified.

Implementation order:

1. Write URL normalizer/error/state tests, then the pure normalizer/data types.
2. Write direct provisioner happy/failure tests, then implement the exact CT1
   command order and owned-target cleanup.
3. Add manager Git-dispatch tests; change only Git dispatch while preserving the
   literal non-Git `shutil.copytree` owner and rollback behavior.
4. Add the CLI override propagation test; add constructor/composition-root wiring.
5. Run targeted tests plus manifest error-code inventory before any next slice.

Named binary tests required in
`tests/test_session_workspace_provisioning.py` unless qualified otherwise:

```text
test_manager_git_source_provisions_clean_b2_workspace
test_provisioner_captures_revision_before_clone
test_provisioner_sets_local_identity_and_real_commit_needs_no_test_identity
tests/test_cli.py::test_cli_passes_fa_repo_push_url_override
test_push_origin_reaches_rewritten_local_bare_remote
test_https_ssh_and_override_urls_canonicalize_exactly
test_invalid_or_credentialed_push_urls_are_redacted_and_rejected
test_git_invalid_branch_id_fails_before_target_creation
test_clone_failure_removes_only_helper_created_target
test_manager_maps_private_failure_to_workspace_provision_failed
test_preexisting_target_is_never_removed
test_missing_git_is_structured_before_target_creation
test_git_timeout_is_structured_and_cleans_partial_target
test_interrupt_cleans_created_target_and_reraises
test_readback_mismatch_is_structured_and_cleans_target
```

The revision-race test inserts a source fast-forward after the helper's single
`rev-parse` capture and before clone (through the private Git runner seam), then
asserts target HEAD equals the captured old commit. The push test keeps
`origin.pushurl` canonical SSH and uses only command-local `url.*.insteadOf` to
route to the bare fixture. The identity test clears `HOME`,
`GIT_AUTHOR_*`, and `GIT_COMMITTER_*`, writes a tracked file, and proves ordinary
`git commit` succeeds from local config.

Existing tests that must remain green and meaningful:

```text
tests/test_session_lifecycle.py::test_partial_workspace_provision_is_removed_on_failure
tests/test_session_lifecycle.py (plain-directory create/attach cases)
tests/test_session_manifest_guards.py::test_every_error_code_is_named_in_some_test
tests/test_s5_state_root_contract.py (production manager composition root)
tests/test_s10c_artifact_posture.py (immediate private session-directory posture)
```

Do-not:

- no `repair_managed_remote` or existing-workspace mutation API in S1; S2 owns
  the first production consumer and preservation policy;
- no `--local`, `--shared`, alternates, hardlinks, shell command strings, source
  Git config copy, global Git config, implicit branch sanitization, or live
  source re-read as the postcondition authority;
- no test-side local/file push URL accepted by `normalize_push_url`;
- no readiness code in S1.

Exit criteria:

- [x] all fifteen named S1 tests exist and pass;
- [x] ignored `.env.fa`, `.venv`, source `.git/hooks`, and untracked fixture are
  absent from a manager-provisioned target;
- [x] target starts clean at the one captured source commit on exactly
  `agent/<session-id>` with exact local fetch/canonical SSH push URLs;
- [x] target local identity reads exactly `First Agent` and
  `agent@first-agent.local`, and a real commit succeeds with no test identity;
- [x] `git push origin agent/<session-id>` reaches the local bare fixture through
  command-local URL rewrite while `/repo` fixture HEAD/status remain unchanged;
- [x] invalid branch, invalid/redacted URL, missing Git, timeout, command failure,
  and read-back mismatch each return their named private code and leave no owned
  partial target;
- [x] manager callers receive only `workspace_provision_failed` with the private
  cause chained; manifest error inventory has no new public code;
- [x] the current manager-owned non-Git fallback and rollback tests pass without
  moving their monkeypatch target;
- [x] targeted Ruff/mypy/Pyrefly/pytest gates and diff inspection are green.

Kill-check: replace the manager's Git dispatch with `copytree`; the clean-state,
branch, remote, and identity tests must fail. Remove CLI override propagation;
the composition-root test must fail.

### Step S2 — route entrypoint fresh/resumed workspaces through the Git contract — EXECUTED

Traces-to: G1, G2, G8; GAP1, GAP13; CT1, CT2, CT6.

Depends-on: S1. Parallelizable-with: none.

Target liveness: entrypoint B2 L0→L3.

Edit:

- `src/fa/session/workspace.py` — add one aggregate
  `configure_existing_workspace(...) -> ExistingWorkspaceState` plus the
  mandatory `python -m fa.session.workspace configure-existing` adapter; remote
  repair and local identity setters remain private implementation helpers;
- `scripts/fa-entrypoint.sh` clone/resume block — invoke that adapter after a
  valid Git workspace exists and before publishing `.active`;
- `tests/test_fa_entrypoint.py` fresh/resume/override/invalid-branch assertions;
- `scripts/fa-post-setup.sh` — remove its startup-workspace-only identity writes;
  push smoke reads/verifies the active workspace's B2 destination instead of
  merely testing separate SSH connectivity;
- `tests/test_deploy_scripts.py` command-contract assertions.

Degree of freedom closed:

- entrypoint clone origin push destination defaulted to local RO source; resume
  paths could retain legacy local-only pushurl; identity was configured only by
  a later host script and only for `.active`.

Deterministic mechanism:

- shell remains owner of fresh clone/resume selection; the module adapter owns
  CT2 URL normalization/read-back and trusted local identity for both paths.

Exact aggregate result/adapter contract:

```text
ExistingWorkspaceState(
  branch: str,
  fetch_url: str,
  push_url: str,
  author_name: str,
  author_email: str,
  remote_action: "verified" | "repaired" | "preserved_custom",
)

python -m fa.session.workspace configure-existing \
  --source /repo \
  --workspace /sessions/<session-id> \
  --session-id <session-id>
```

The adapter consumes `FA_REPO_PUSH_URL` directly from its environment using the
same unset/empty rule as CT1. It first validates `agent/<session-id>` with Git and
requires `symbolic-ref --short HEAD` to equal that branch; mismatch is diagnostic,
not an automatic checkout/reset. Exit `0` means configured or intentionally
preserved-with-warning and stdout contains one JSON serialization of the six
fields. For a CT2-supported credential-free custom URL, `push_url` is the exact
current value. For any unsupported/unsafe custom URL, Git config remains
unchanged but JSON uses `push_url="<preserved-custom-redacted>"`; raw input never
enters stdout/stderr. `preserved_custom` prints one generic credential-free
warning to stderr. Exit `2` means validation/configuration failure, no stdout
state, and one safe stderr diagnostic. It never clones, checks out, resets,
deletes, or cleans an existing workspace.

Do:

1. Validate `agent/<FA_SESSION_ID>` with Git before fresh checkout; invalid refs
   enter the existing INVALID_CONFIG standby path and leave no partial target.
2. Configure/verify B2 and local identity before publishing `.active`.
3. On resume, repair only an absent pushurl or one exactly equal to the current
   `origin` fetch URL when that fetch URL uses `file://` (production:
   `file:///repo`); do not classify by substring.
4. Preserve every other non-local/custom pushurl, emit `[WORKSPACE_BOOTSTRAP]`
   warning, and
   still repair/verify local identity.
5. Make post-setup push assertion read the configured pushurl, push a disposable
   branch, and verify source `/repo` HEAD/status remain unchanged.
6. Keep the adapter's output machine-stable and credential-redacted; shell maps
   any non-zero configuration result to the existing clone/config standby error.

Do-not:

- no session-selector or manifest ownership changes;
- no duplicate shell URL parser or identity policy;
- no global Git config.

Exit criteria:

- [x] fresh and resumed entrypoint tests assert branch/fetch/push/local identity;
- [x] regex-valid but Git-invalid session IDs stop before `.active` and child run;
- [x] command override still executes in selected startup workspace;
- [x] failed remote/identity setup follows existing partial-clone cleanup/standby
  path for fresh workspaces and preserves resumed workspace contents;
- [x] missing/local pushurl repair and custom non-local preservation tests pass;
- [x] post-setup contains no identity write command, and its real push smoke
  targets the read-back B2 pushurl.

Kill-check: remove entrypoint configuration adapter call → T3 fails; re-add the
post-setup-only identity writes while removing S2 identity repair → fresh
entrypoint commit test fails before post-setup can mask the defect.

### Step S3 — implement one stdlib readiness engine and lifecycle wiring — EXECUTED

Traces-to: G3, G4, G5; GAP3, GAP4; CT3, CT4, CT6, CT8.

Depends-on: S1–S2. Parallelizable-with: none.

Target liveness: managed readiness L0→L3.

Edit:

- NEW `src/fa/workspace_bootstrap.py` — CT3/CT4/CT8 implementation + CLI;
- `src/fa/hygiene/hooks/install.py:install_hooks` — add keyword-only
  `hook_source_dir: Path | None = None`; `None` retains current `scripts_dir()`,
  while readiness passes `<workspace>/src/fa/hygiene/hooks` after containment
  validation;
- `src/fa/hygiene/hooks/__init__.py:install_hooks` — mirror and forward that exact
  optional keyword so the lazy public API cannot diverge;
- `src/fa/hygiene/hooks/_util.py:resolve_hooks_dir` — bound the existing Git
  lookup to CT3's 120-second status/install limit and retain pure-Python fallback;
- `scripts/fa-entrypoint.sh` — readiness before `.active`/override/auto-run;
- `src/fa/session/manager.py` — add the exact optional CT6 callback and invoke it
  at the two specified transaction points;
- `src/fa/cli.py:_prepare_managed_workspace/_session_manager_for_args` — add the
  degraded-warning adapter and pass it as production callback; direct
  `SessionManager` constructors retain `None`;
- NEW `tests/test_workspace_bootstrap.py`;
- `tests/test_session_lifecycle.py` — fake callback order and default-None
  compatibility;
- `tests/test_fa_entrypoint.py`;
- `tests/test_cli.py` — callback completion precedes provider build/call;
- `tests/test_hygiene_hooks_install.py` — explicit-source/default/lazy-forwarding
  contract.

Degree of freedom closed:

- managed workspace could become active/model-visible with absent or stale dev
  environment/hooks; imported image path could select wrong hook sources.

Deterministic mechanism:

- CT3 transaction under `fcntl.flock`, explicit workspace source, typed result,
  atomic CT4 state, caller-visible CT8 warning.

Do:

1. In entrypoint, run
   `python3 -m fa.workspace_bootstrap ensure --workspace "$SESSION_DIR"` after S2
   Git configuration and before `.active`; capture rc under `set -e`, warn on any
   non-zero rc, and continue without moving the call after publication.
2. Install minimal seats before network-dependent sync.
3. Use `uv sync --locked --extra dev` with `UV_LINK_MODE=copy`; never modify
   lock. This selects the copy behavior the current cross-filesystem fallback
   already requires, without adding a persistent mount.
4. Prewarm all hook environments.
5. Reinstall custom seats last.
6. Validate exact environment + seats + cache sentinel.
7. Return degraded state without raising through agent admission under the
   operator-selected policy.
8. Add `workspace_preparer` exactly as CT6 specifies: default `None`; new-session
   call after DB creation/before manifest commit; attach call after DB
   validation/before `last_used_at`; production callback supplied only by CLI.
   The CLI adapter emits one CT8 warning for degraded state and never raises.
9. In `tests/test_cli.py::test_readiness_completes_before_provider_build_or_call`,
   append `"ready"`, `"build"`, and `"call"` from fakes and assert the exact
   prefix `ready, build, call` plus provider call_count zero during readiness.
10. Add `test_install_hooks_uses_explicit_workspace_source` and
   `test_lazy_install_hooks_forwards_hook_source_dir`; keep current default-source
   tests unchanged so host/image callers preserve behavior.

Do-not:

- no background process, no manifest `status="bootstrap-warned"`, no environment
  dump, no persistent cache mount.

Exit criteria:

- [x] fresh entrypoint/new logical session has `.venv`, four executable/current
  seats, pre-commit sentinel, ready marker;
- [x] attach with matching state is idempotent;
- [x] one parametrized test forces every CT3 reason code and asserts exact status,
  rc, marker presence/absence, and `repaired` value;
- [x] lock/pyproject drift writes degraded warning and does not rewrite lock;
- [x] exact `ready, build, call` order and zero provider calls during readiness are
  asserted from the shipped CLI root;
- [x] direct generic managers with callback `None` preserve current behavior;
- [x] concrete and lazy hook installers select explicit workspace source, while
  omitted keyword retains image/default source behavior;
- [x] image-vs-workspace hook-source regression test passes.

Kill-check: remove readiness call from entrypoint or manager → T4/T5 fails.

### Step S3.5 — add trustworthy slice mutation feedback and permanent readiness scope — EXECUTED

Traces-to: G9; GAP14–GAP16; CT10–CT12; P16–P20; M11–M14.

Depends-on: S3. Parallelizable-with: none. S4 remains blocked until S3.5's
configured readiness evidence is classified and the repository is restored.

Target liveness: explicit runner L0→L3; targeted verdict false-L2→L3; type
filter L0→L3; permanent readiness mutation scope L0→L3.

#### S3.5 edit packet 1 — write runner authority tests first

Files:

- NEW `tests/test_slice_mutmut.py`.

Intent/as-is/to-be:

- **Intent:** create non-vacuous oracles before replacing the gate authority.
- **As-is:** `tests/test_targeted_gates_smoke.py` proves skip/AST subprocess
  shape only; it cannot detect live config mutation, test-as-source, untracked
  omission, raw-rc false green, missing type counts, or timeout leakage.
- **To-be:** one focused suite exercises CT10–CT12 through the shipped script and
  targeted wrapper, using a recording fake only at mutmut/Pyrefly process
  boundaries plus a tiny real locked-tool fixture.

Mechanism/best practice:

- build temporary synthetic repositories with untracked `src/` and `tests/`
  files, real TOML, and fake executables with exact signatures;
- assert structured result fields/count identity and file bytes/modes, not
  internal call count alone;
- actual mutmut fixture is POSIX/Linux-gated because mutmut 3 requires fork;
  Windows configuration parity remains static plus pytest-gremlins scope.

Failure behavior: fake or real harness setup/collection failure must fail the
test as infrastructure, never satisfy a survivor oracle.

DoD/negative proof/test class:

- [ ] C0: parser rejects unknown/duplicate/missing statuses and count mismatch;
- [ ] C0/C3: absolute/outside/symlink source, wrong source/test role,
  duplicate/overlapping/non-UTF-8 paths, output-parent symlink, non-POSIX,
  invalid timeout/children, and insufficient scratch space return exact
  input/infrastructure exits without invoking mutmut;
- [ ] C0/C1: missing/wrong-version mutmut and missing Pyrefly cannot create a
  clean result;
- [ ] C1: untracked source/test bytes are staged, test appears only in test
  selection/copy, and original source/test/pyproject stay byte-identical on
  clean, survivor, tool-failure, and timeout paths;
- [ ] C1: raw fake `mutmut run` rc 0 + survivor yields runner rc 1 and diff;
- [ ] C1: process timeout terminates the fake child process group and removes
  stage;
- [ ] C4 real fixture: exact assertion yields
  `total=3,killed=2,type_invalid=1`, zero actionable statuses, runner rc 0;
- [ ] C4 negative: omit the generated type command and the same fixture reports
  `killed=3,type_invalid=0`, failing the pinned type-filter oracle;
- [ ] producer kill: stub targeted delegate success or raw workflow command and
  wiring tests fail.

#### S3.5 edit packet 2 — implement the isolated executor

File:

- NEW `scripts/run_slice_mutmut.py`.

Intent/as-is/to-be:

- **Intent:** make selected inputs, status identity, and artifacts deterministic.
- **As-is:** only mutable global config plus raw mutmut output exists.
- **To-be:** CT10's stdlib typed CLI/module runs explicit or configured scope in
  isolated root-backed staging and derives its own verdict.

Mechanism/best practice:

- frozen request/result dataclasses and closed status literals;
- `argparse`, `tomllib`, `pathlib`, `subprocess`, `tempfile`, `hashlib`, and
  atomic JSON/text writes only; no new dependency;
- section-aware staged TOML generation followed by `tomllib.loads` validation;
- exact mutmut 3.6.0 and POSIX gates before any stage creation;
- list-form process argv, process-group timeout, exact UTF-8, no-follow path
  checks, duplicate/overlap rejection, digest-before/digest-after invariants,
  and `finally` cleanup;
- one status parser combines `mutmut results` with exported killed/total data,
  derives `type_invalid`/`not_checked`, and requires the CT10 count identity;
- generate diffs only for actionable statuses to prevent 540 filtered readiness
  mutants from recreating cleanup noise.

Failure behavior:

- invalid input/config exits 2 before tool invocation;
- missing tool, nonzero mutmut harness run, timeout, unknown/malformed/mismatched
  results, failed `show`, source/config/test drift, or artifact failure exits 3;
- runner does not catch-and-pass broad exceptions; a final boundary converts
  known OS/process/parse errors into one structured infrastructure result.

DoD/negative proof/test class: all packet-1 CT10 tests pass; deleting result
classification, staged-config replacement, source digest check, timeout kill, or
cleanup makes its named test fail. Ruff/Mypy/Pyrefly/compile checks cover both
module and tests.

#### S3.5 edit packet 3 — make targeted discovery a thin, truthful selector

Files:

- `scripts/_git_diff.py`;
- `scripts/run_targeted_mutmut.py`.

Intent/as-is/to-be:

- **Intent:** preserve the existing pre-push surface while deleting its unsafe
  execution/config policy.
- **As-is:** base...HEAD only, `tests/` admitted as sources, regex live-config
  rewrite, ineffective env timeout, and raw-rc verdict.
- **To-be:** `_git_diff.changed_python_files` has opt-in NUL-safe
  index/worktree/untracked discovery; targeted wrapper intersects production
  paths only with permanent source scope and delegates CT10 with configured
  tests/copy and 600-second wall timeout.

Mechanism/best practice:

- add explicit `include_worktree: bool = False` and
  `include_untracked: bool = False`; defaults preserve targeted Semgrep behavior;
- apply a 30-second timeout and return-code check to every Git subprocess;
- union `base...HEAD`, `git diff HEAD`, and
  `git ls-files --others --exclude-standard`, all `-z` byte output,
  strict-UTF-8-decode/normalize/contain once, deduplicate/sort, then apply
  extension/prefix/cap;
- parse permanent TOML with `tomllib`, never regex;
- delete `_rewrite_source_paths`, backup/restore, and
  `MUTANT_TIMEOUT_SECONDS` environment policy;
- preserve existing pre-start fail-open cases and explicit skip; return CT10 rc
  unchanged after execution starts.

Failure behavior: missing Git/tool/no base/too many production files remains a
loud skip rc 0 per existing policy. Any started CT10 infrastructure/actionable
result remains nonzero. A test-only change never becomes a mutation source; with
no changed permanent production source, emit a truthful no-source skip.

DoD/negative proof/test class:

- [ ] C0/C1: committed, staged, unstaged, and untracked production files are
  found when options are enabled; newline-bearing names are NUL-safe; Git
  timeout/nonzero returns a loud empty selection; Semgrep defaults are unchanged;
- [ ] C1: changed test is available in configured oracle bytes but absent from
  `source_paths`;
- [ ] C1: raw survivor result propagates rc 1;
- [ ] static: no backup suffix, source-path rewrite, or dead timeout env remains;
- [ ] producer kill: replace targeted delegate with `return 0`; T17 fails.

#### S3.5 edit packet 4 — enable permanent type/scope and configured CI consumer

Files:

- `pyproject.toml`;
- `.github/workflows/tests.yml`;
- `.github/CODEOWNERS`;
- `scripts/check_protected_paths.py`.

Intent/as-is/to-be:

- **Intent:** make readiness and the new TCB active in permanent local/CI
  configuration.
- **As-is:** readiness omitted; no type filter/also-copy; gremlins mirror stale;
  weekly raw command exports incomplete counts; new runner would not be owner
  protected.
- **To-be:** CT11/CT12 exact config, weekly configured runner artifacts with
  advisory policy unchanged, and runner added to both TCB lists.

Mechanism/best practice:

- append readiness source/test without reordering/removing existing entries;
- add the reviewed `also_copy` dependency closure and exact direct Pyrefly
  command whose positional paths equal `source_paths`;
- add readiness path to gremlins and test exact set equality;
- workflow installs with `uv sync --locked --extra dev`, then runs
  `uv run python scripts/run_slice_mutmut.py --configured-scope` with explicit
  result/diff paths, `--timeout-seconds 18000`, and `if: always()`
  summary/upload consumers;
- keep job `continue-on-error: true`, permissions, action pins, retention, and
  schedule unchanged;
- add `/scripts/run_slice_mutmut.py` to CODEOWNERS and exact `_TCB_PATHS`.

Failure behavior: Pyrefly baseline/JSON failure makes mutation infrastructure
red; weekly remains advisory at job boundary. Missing result artifact is warned
and cannot be summarized as clean. TCB parity failure remains visible under the
repository's existing governance semantics.

DoD/negative proof/test class:

- [ ] T19 static config contract proves source/test/copy/type command and exact
  mutmut↔gremlins parity;
- [ ] scoped permanent Pyrefly command returns rc 0 and valid zero-error JSON;
- [ ] T20 workflow test proves configured runner producer, schema-v1 JSON,
  type-invalid field, diff upload, and unchanged advisory posture;
- [ ] TCB parity includes the new runner;
- [ ] producer kills for each config/workflow/TCB seat fail a named assertion.

#### S3.5 execution and classification gate

Run in order after each packet: targeted tests, Ruff format/lint, Mypy with
`MYPYPATH=src` where needed, changed-file Pyrefly, compileall, diff/check/status.
After packet 4:

1. run the real three-mutant fixture from T18;
2. run explicit readiness scope with `--also-copy src/fa` and capture JSON/diffs;
3. require the source-verified identity or explain any source-caused change:
   `874 = killed + type_invalid + remaining statuses`;
4. classify every survivor; expected set is the five already-proven equivalents,
   but names/diffs from the new run—not this expectation—are authority;
5. run `--configured-scope` far enough to prove readiness selection, clean-test,
   forced-fail, type-filter, and artifact paths; a full weekly-scope completion
   may use the workflow because its runtime is already advisory/long-running;
6. run producer-removal checks for targeted delegate and workflow producer under
   trap-restored source;
7. run affected suites, `just check` (classifying only the known unrelated full
   baseline failures if still present), markdown/link checks, and inspect mode
   summary;
8. remove all staging trees and confirm real `pyproject.toml`, source, tests,
   and lock are byte-identical except intended edits.

S3.5 exit criteria:

- [x] CT10–CT12 and T17–T20 pass with actual command output recorded;
- [x] tests are never mutation sources;
- [x] explicit untracked slice works;
- [x] raw rc false-green is killed;
- [x] type-invalid count is separate and closes total identity;
- [x] readiness is permanent mutmut/gremlins scope with its test/dependencies;
- [x] five known equivalents are re-proven; no new/unclassified survivor remains;
- [x] weekly CI remains advisory and existing skills remain byte-identical;
- [x] no live config/source/test corruption, stage residue, or new dependency.

### Step S4 — collapse bootstrap aliases onto the readiness engine — EXECUTED

Traces-to: G3, G4, G6; GAP5, GAP6, GAP8; CT3, CT4, CT7, CT8.

Depends-on: S3. Parallelizable-with: none.

Target liveness: aliases L2→L3.

Edit:

- `src/fa/workspace_bootstrap.py` — add CT3 read-only check function/CLI without
  changing ensure behavior or reason schema;
- NEW `scripts/bootstrap/workspace.py` — thin stdlib wrapper that prepends the
  checked-out repository's `src` and invokes the CT3 CLI;
- `scripts/bootstrap/host_bootstrap.py` — retain compatibility entrypoint and
  bounded host-tool setup, delegate workspace state to CT3;
- `justfile:install/agent-bootstrap/doctor/_install-hooks/_hooks-status` — direct
  wrapper calls, read-only `check`, and deletion of obsolete private sequencing
  recipes;
- `.gitignore` and tracked `.fa/host-bootstrap.json` — migrate to ignored
  `.fa/ready-state.json`; remove machine state from version control;
- `.vscode/tasks.json` remains unchanged as a convenience consumer;
- `tests/test_workspace_bootstrap.py` — core read-only readiness tests;
- NEW `tests/test_workspace_bootstrap_aliases.py` — wrapper/host/just/marker
  convergence and failure tests, deliberately outside the core C4 selection.

Degree of freedom closed:

- aliases could execute different sync/install orders and plain `uv run` could
  mutate/sync before the stdlib bootstrap starts.

Deterministic mechanism:

- one core transaction, thin compatibility adapters, status verification.

Do:

1. `just install` runs exactly
   `python3 scripts/bootstrap/workspace.py ensure --workspace .`; it does not
   duplicate sync/hook commands.
2. `just agent-bootstrap` runs exactly
   `python3 scripts/bootstrap/host_bootstrap.py` without `uv run`; that script
   checks pinned `just`, installs it through bounded uv only when missing/wrong,
   then calls the same wrapper and emits `FA_AGENT_READY=1` only after wrapper
   rc=0. Missing uv returns 2; setup failure returns 75; wrapper rc propagates.
3. Delete private `_install-hooks` and `_hooks-status`: repository search proves
   their only production caller was old `just install`; they are not stable
   public recipes.
4. Keep host `just` tool installation/check separate from CT4 fingerprint.
5. Keep `just doctor` read-only; local status calls
   `python3 scripts/bootstrap/workspace.py check --workspace .` directly, with no
   `uv run` and no ensure/write path. CI retains its current explicit exemption.
6. Bound host version/tool/wrapper subprocesses at 30/900/2,000 seconds and map
   failures as D21 specifies.
7. Keep VS Code task best-effort and unchanged; do not add workspace auto-task
   permission.

Do-not:

- no requirement that `/srv` deployment mirror installs dev hooks/venv.

Exit criteria:

- [x] all three explicit entrypoints converge on identical marker/fingerprint;
- [x] read-only check detects marker/sentinel/fingerprint/hook/lock drift without
  creating or changing lock/log/marker/sentinel state;
- [x] second invocation performs no network setup;
- [x] missing uv/just, host timeout, and wrapper degradation have stable rc/text;
- [x] Git tracked status contains only intended source changes after bootstrap.

Kill-check: point one alias back to old sequence → alias convergence test fails.

### Step S5 — add hook self-repair with narrow warn-only mapping — EXECUTED

Traces-to: G3, G4, G5; GAP7; CT5, CT8.

Depends-on: S3–S4. Parallelizable-with: none.

Target liveness: hook fallback L0→L3.

Edit:

- four files under `src/fa/hygiene/hooks/` — each receives the same small,
  self-contained prelude that resolves the repository root and invokes the S4
  stdlib wrapper; no shared helper/file is added in this slice;
- NEW `tests/test_hygiene_hooks_self_bootstrap.py`;
- `tests/test_hygiene_hooks_install.py` existing gate behavior tests.

Degree of freedom closed:

- a stale/missing environment could skip or accidentally swallow quality
  failures without a typed distinction.

Deterministic mechanism:

- common bootstrap result mapping; readiness lock is recursion/concurrency guard;
  no `exec "$0"` retry loop is needed because prewarm/install does not execute
  the Git hook.

Each prelude runs exactly:

```bash
repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || bootstrap_rc=$?
if [[ -n "${repo_root:-}" ]]; then
  bootstrap_json="$(python3 "$repo_root/scripts/bootstrap/workspace.py" \
    ensure --workspace "$repo_root")" || bootstrap_rc=$?
fi
```

`bootstrap_rc` initializes to `0`. Its value is branched before any normal hook
command. Captured READY JSON is intentionally silent; degraded CLI stderr stays
visible, followed by one generic warning if the wrapper never started.

Do:

1. Invoke core bootstrap before normal body.
2. Continue normal body only on READY.
3. On any non-zero bootstrap invocation rc, print `[WORKSPACE_BOOTSTRAP]` plus
   log path when the CLI produced one, then return 0 before the normal body.
4. After bootstrap rc=0, preserve every normal gate failure return code.
5. After readiness, change every existing hook body invocation from `uv run` to
   `uv run --no-sync` without changing arguments/order:
   - pre-commit: `pre-commit run ...` and optional `just check`;
   - pre-push: `just check-deep`;
   - prepare-commit-msg/commit-msg: `python -m fa.hygiene prepare|validate`.

Do-not:

- no claim that source templates can self-install when no seat exists; lifecycle
  is the primary seat producer.

Exit criteria:

- [x] missing venv repairs before first commit;
- [x] simulated unavailable uv/network warns and allows;
- [x] ruff/pre-commit/check-deep failure remains blocking with original rc;
- [x] no recursive invocation/install loop;
- [ ] focused argument tests pass, but actual core-child pre-push stdin isolation is violated by D27; S6.5/T23 owns closure.

Kill-check: broaden catch to `exit 0` after normal gate failure → T10–T12 fail.

### Step S6 — wire and document the operator dev clone without touching deployment mirror — EXECUTED

Traces-to: G6; GAP8; CT7.

Depends-on: S4–S5. Parallelizable-with: none.

Target liveness: host dev readiness L2→L3.

Edit:

- `AGENTS.md` development workflow;
- `knowledge/instructions/01-install.md` operator-vs-deployment clone roles;
- `knowledge/instructions/02-operations.md` VS Code path/recovery commands;
- `knowledge/ci-guardrails-reference.md` — remove agent-run bootstrap authority and
  point recovery/status to lifecycle readiness + `just doctor`;
- `tests/test_workspace_bootstrap_aliases.py` — host alias/task/document authority, outside core readiness C4.

Explicitly unchanged: `.vscode/tasks.json` continues to run
`uvx --from rust-just==1.57.0 just agent-bootstrap`; S4 changes that alias's
consumer path, so the task needs no command edit.

Degree of freedom closed:

- operator could open deployment mirror or optional dev clone without knowing
  which lifecycle/permissions apply.

Deterministic mechanism:

- explicit path roles and one readiness command. VS Code permission is not an
  authority claim.

Do:

1. Document `~/First-Agent-dev` as operator dev clone and `/srv/...` as clean
   deployment mirror.
2. Remove LLM instruction to remember bootstrap only after lifecycle tests are
   L3; retain operator recovery/doctor commands.
3. State explicitly that the guarantee covers managed clones only and excludes
   arbitrary raw clones.

Do-not:

- no global Git config/task auto-authorization.

Exit criteria:

- [x] one command readies `~/First-Agent-dev`;
- [x] docs never tell operator to commit in deployment mirror;
- [x] docs link checker passes.

### Step S6.5 — review and harden integrated S1–S6 production behavior

Traces-to: G1–G6, G9–G10; GAP17–GAP20; CT1–CT8, CT10–CT13.

Depends-on: S6. Parallelizable-with: none. S7 is blocked until S6.5 exits green.

Target liveness: individually verified slices L2/L3→integrated clean-candidate
L3. External GitHub/host-deployment authority remains explicitly owned by S9.

Edit exactly:

- NEW `worklogs/implementation-plans/session-workspace-readiness-s1-s6-review.md`
  — A54 evidence ledger and final assessment;
- NEW `tests/test_workspace_readiness_integration.py` — A55 clean-candidate and
  real hook/readiness integration authority, separate from permanent core C4;
- `src/fa/workspace_bootstrap.py` and
  `tests/test_workspace_bootstrap.py` — close D27 with explicit child stdin
  isolation and a process-contract oracle;
- `tests/test_hygiene_hooks_self_bootstrap.py` — actual checked-out-wrapper
  pre-push stdin proof, not only a fake wrapper;
- `tests/test_authoring_protected_paths_parity.py` — semantic CODEOWNERS/TCB
  coverage parser that includes exact, prefix, and wildcard gate patterns;
- only while the diagnostics reproduce, minimally fix the blocking type findings
  in `src/fa/egress_proxy/server.py`, `scripts/_console.py`,
  `tests/test_no_builtin_shadow.py`, `tests/test_git_diff_helper.py`, and
  `tests/test_semgrep_pin.py` without changing product behavior;
- touched hook installer/status docstrings may be corrected when the review
  proves they describe removed recipes/plain `uv run`; no hook policy redesign;
- `AGENTS.md`, `knowledge/instructions/01-install.md`, and
  `knowledge/instructions/02-operations.md` — mechanical markdownlint
  normalization only for the reproduced whole-file T24 debt; S8 remains owner of
  transport/history semantics;
- `tests/test_slice_mutmut.py` and capability-gated readiness/integration tests —
  replace reproduced dynamic `pytest.skip()` calls with deterministic decorators;
- `scripts/check_shell_syntax.sh` — restore its tracked executable mode after
  workspace materialization; no shell behavior change;
- `pyproject.toml` deptry configuration and
  `scripts/check_dependency_contract.py` — model the internal scripts package as
  first-party and remove the unreachable pre-3.11 tomli fallback;
- `src/fa/hygiene/hooks/_util.py`, `src/fa/workspace_bootstrap.py`,
  `tests/test_hygiene_hooks_install.py`, and
  `tests/test_workspace_bootstrap.py` — resolve Q7 by distinguishing Git's
  default/effective hook directories and degrading without mutation on every
  custom path or non-FA default-seat collision;
- this plan: record final row counts, remediations, kills, and S7 admission.

Degree of freedom closed:

- focused fixtures and dirty-worktree classifications could be mistaken for an
  integrated production-ready candidate; review findings could also trigger
  opportunistic refactors or silent policy decisions.

Deterministic mechanism:

- CT13 closed-schema ledger, exact diff/artifact inventory, isolated clean Git
  materialization, real process/hook roots, zero-diagnostic gates, and explicit
  producer mutations. Findings outside the allowed files or requiring behavior
  policy stop at P24.

Execution packets:

1. **Inventory and intent translation.** Enumerate every S1–S6 changed/untracked
   artifact from Git, map each G#/GAP#/CT# intent to actual producer/consumer and
   state transition, inspect every production diff, and assign a CT13 verdict.
   Missing row or evidence blocks the slice.
2. **Senior production review.** Apply the CT13 rubric to Git provisioning,
   existing-workspace repair, manager/CLI/entrypoint ordering, readiness state
   security/concurrency, aliases, hooks, mutation tooling/governance, and S6
   docs/recovery. Record confirmed defects separately from suspicions.
3. **Repair reproduced deterministic defects.** Add `stdin=subprocess.DEVNULL`
   (or the platform-equivalent closed input) to readiness children while proving
   hook stdin remains at the parent; repair semantic TCB parity; resolve the
   exact Mypy/Pyrefly findings with annotations/narrowing/signature correctness,
   not ignores or gate weakening. Re-run focused gates after each edit.
4. **Clean-candidate runtime.** Materialize the exact candidate bytes in an
   isolated clean Git checkout excluding `.git`, `.venv`, `.fa`, caches, and
   secrets. Create the baseline commit before hook installation, run real
   `uv sync --locked`, readiness, installed prepare/pre-commit/commit hooks, and
   a second real commit with identity environment cleared. Run a local bare
   publication smoke with command-local URL rewrite; use the existing explicit
   mutation skip only if T24 has emitted/reviewed the strict actionable report.
   No provider/model call and no external GitHub push.
5. **Integrated gates and kills.** Require focused S1–S6 suites, full pytest,
   Ruff/format, full Mypy, full Pyrefly, shell syntax, compileall, lock,
   contracts, markdown/doc links, workflow/TCB parity, and `just check` from the
   clean candidate. Run CT13 producer removals under trap restoration and the
   existing readiness C4/configured mutation authority where affected.
6. **Assessment and admission.** A54 states whether code is production-grade,
   lists every remaining gap with owner/severity, and permits S7 only with no
   unowned/unexplained blocker. S9-only external claims remain visibly deferred.

Production best-practice constraints:

- no new dependency/interface/service/helper solely for review;
- no `type: ignore`, pragma, allowlist, test deletion, skip, or threshold change
  to manufacture green;
- mock only external publication/network, never SessionManager, entrypoint,
  checked-out wrapper, hook source, or normal Git process roots in T22/T23;
- preserve fail-open bootstrap policy and exact normal quality rc;
- preserve B2/custom-push Q5 behavior, `/repo` read-only authority, session
  selector semantics, and strict mutation survivor reporting;
- verify effective `core.hooksPath`; if it is outside the managed checkout or
  collides with non-FA seats, stop at P24 and add a policy Q# before overwrite or
  chaining behavior changes.

Exit criteria:

- [x] A54 has one evidence-bearing row for every S1–S6 claim/artifact and no
  unresolved internal `partial|absent|unsafe|unverified` verdict; the sole
  external S9 row is explicitly deferred with owner;
- [x] readiness children cannot consume hook stdin; pre-push normal body receives
  exact original bytes after real wrapper execution;
- [x] clean candidate creates READY state/seats, performs a real second commit,
  and local publication smoke leaves source authority unchanged;
- [x] focused and full blocking gates have zero unexplained failures; dirty
  authoring state is eliminated by the clean materialization, not waived;
- [x] CODEOWNERS/TCB semantic parity and mutation workflow authority are green;
- [x] critical producer-removal/branch-inversion kills fail named T21–T24 tests,
  source is byte/mode restored, and affected gates rerun;
- [x] no model/provider call, secret copy, external push, cache topology, or
  unapproved policy-sensitive remediation occurs;
- [x] report gives `S7_ADMISSION=ALLOW`; S7 is permitted.

Kill-check: remove manager Git dispatch, lifecycle readiness producer, checked-out
wrapper invocation, hook prelude, `_run_process` stdin isolation, or mutation
workflow/TCB consumer. A named T21–T24 oracle must fail and A54 must block S7.

### Step S7 — measure cold/warm readiness and decide cache follow-up

Traces-to: G7; GAP9; CT9.

Depends-on: S6.5. Parallelizable-with: none.

Target liveness: cost evidence L0→L3.

Edit:

- NEW `worklogs/implementation-plans/session-workspace-readiness-benchmark.md`
  (measurement artifact, no secret content);
- `docker-compose.fa.yml` — Q8-approved change of only the
  `/home/fa/.cache` tmpfs ceiling from 500 MiB to 1536 MiB; uv remains 2 GiB and
  no bind/persistent mount is added;
- `tests/test_container_build_invariants.py` — parsed-YAML authority for the
  distinct ephemeral HOME/uv cache seats and exact approved caps.

Degree of freedom closed:

- persistent cache topology could be added from intuition while measuring only
  uv and ignoring pre-commit.

Deterministic mechanism:

- fixed command sheet, commit/image identity, filesystem/size/time fields,
  cold/warm matrix M1–M3.

Do:

1. Measure cold after recreate, warm in same container, and resumed workspace
   after cache loss.
2. Measure uv and pre-commit independently and combined.
3. Record tmpfs caps and peak sizes.
4. Record the count and aggregate size of existing session `.venv` directories;
   compare a legacy manager-copy workspace with a new clean-clone workspace.
5. Decide follow-up:
   - keep tmpfs;
   - persist uv only;
   - persist uv + pre-commit;
   - bake immutable environments.
6. If persistent bind is chosen, author a separate P2 plan with ownership,
   poisoning, prune, quota, rollback, and `UV_LINK_MODE=copy` contracts.

Exit criteria:

- [x] A26 contains all CT9 fields and explicit proxy limitations;
- [x] Q2 is deferred with measured reason; tmpfs remains the selected topology;
- [x] no persistent cache mount was added; only Q8's approved ephemeral cap changed.

### Step S8 — align ADR and operational documentation

Traces-to: G8; GAP10; CT1, CT2, CT6.

Depends-on: S1–S7. Parallelizable-with: none.

Target liveness: documentation claims false→source-aligned.

Edit exactly:

- `knowledge/adr/ADR-13-workspace-isolation.md` — amendment superseding hardlink
  and one-container/one-session clauses;
- `knowledge/adr/DIGEST.md` — current ADR-13 summary;
- `README.md` — diagram transport label;
- `knowledge/instructions/02-operations.md` — operator topology/workflow;
- `knowledge/overview/FEATURES.md` — replace “instant hardlink clone” product
  claim with measured pack-transport/readiness wording;
- `knowledge/ci-guardrails-reference.md` — replace agent-run bootstrap and stale
  `just hooks-status` claims with lifecycle readiness + `just doctor` recovery;
- `.env.fa.template` — document optional non-secret `FA_REPO_PUSH_URL` and the
  default deployment-mirror authority;
- `tests/test_deploy_scripts.py` — static assertion that the root non-secret
  template documents the override and no secret template does;
- `knowledge/pr-notes/workspace-isolation.md` and
  `worklogs/pr-notes/workspace-isolation.md` — retain historical body but add a
  dated correction banner linking ADR-13/AP-004;
- `worklogs/S13-NEXT-SESSION-START.md` and
  `worklogs/S13-SESSION-START-PROMPT.md` — add a historical/superseded banner so
  their frozen-sync and identity commands cannot be reused as current bootstrap
  instructions.

The contradiction sweep may report but does not edit historical evidence under
`knowledge/research/**`, `knowledge/trace/**`, `worklogs/archive/**`, AP-004, or
this plan's own preflight/gap/execution record. Every remaining hit outside that
explicit evidence allowlist or the four correction-bannered files fails T15 and
requires a plan revision; “edit other hits” is not execution authority.

Degree of freedom closed:

- operators/agents could optimize or debug against hardlinks/one-session claims
  that code no longer implements.

Deterministic mechanism:

- same-PR source/doc correction plus doc-link/search checks.

Do:

1. State pack transport, no hardlink claim.
2. State persistent logical session selector separately from startup workspace.
3. State B2 fetch/push routing and authority sequence.
4. State managed readiness and warn-only bootstrap failure policy.

Do-not:

- do not rewrite historical research prose without marking accepted-vs-current
  distinction.

Exit criteria:

- [x] stale current transport/session claims are eliminated from canonical docs
  or fenced as explicitly historical evidence;
- [x] doc links and Markdown gates pass across all 12 S8 surfaces;
- [x] deploy-script static authority proves `FA_REPO_PUSH_URL` appears only in
  the non-secret runtime template/docs, not provider secret templates.

### Step S9 — execute live managed-session proof

Traces-to: G1–G8; GAP11; CT1–CT9.

Depends-on: S0–S8, green implementation PR CI, **human merge**, and
operator-controlled `fa update` of the deployment mirror. Parallelizable-with:
none. The agent may prepare the commands/report but cannot satisfy or bypass the
merge/deploy precondition.

Target liveness: product claim L2→L3.

Edit exactly:

- NEW `worklogs/implementation-plans/session-workspace-readiness-live-verification.md`;
- append only a link/status summary to this plan after the report is complete;
- no opportunistic product fix during evidence collection.

Degree of freedom closed:

- local/unit green could hide mount, ownership, cache, remote, or entrypoint
  differences on the AIO host.

Deterministic mechanism:

- controlled live sheet with source/image identity and rollback.

Do:

1. Re-run tracked A1 after the operator update and record its terminal
   `probe=complete` baseline in A30.
2. Record the entrypoint-created startup workspace from that container recreation
   and assert B2/identity/readiness existed before `.active` became consumable.
3. Create a separate fresh managed logical session with a `docker compose exec`
   Python here-document that calls `fa.cli._session_manager_for_args` using
   `SimpleNamespace(workspace=None)`, then
   `create_or_attach_session(session_id=None, workspace_override=None)` and emits
   only session id/path. This exercises the shipped CLI composition root and
   performs zero provider/model calls.
4. For both managed producers, assert branch/fetch/push/local identity, `.venv`,
   seats, marker, sentinel, and no copied `.env.fa`.
5. From the logical session, commit and push a disposable branch through
   pushurl; verify it appears on GitHub and `/repo` HEAD/status remain unchanged.
6. Verify no direct push/merge to main is possible for agent identity.
7. Run CI on the disposable PR; operator closes/deletes it without merge.
8. Record cold/warm evidence and clean disposable session/branch explicitly.

Exit criteria:

- [ ] live B2 push branch succeeds;
- [ ] local fetch remains `/repo`-bound;
- [ ] readiness predates LLM call;
- [ ] deployment mirror remains clean;
- [ ] GitHub CI/human merge boundary observed;
- [ ] all L3 kill-checks recorded.

---

## 6. Verification plan

### T0 — probe safety and correctness

Class: C0p/C2 shell diagnostic.

Oracles:

- bash syntax/static warnings;
- invalid/missing `.active` does not abort or inspect escaped path;
- fake remote with HTTPS userinfo is redacted;
- Git index mtime/hash unchanged across probe fixture;
- malicious cwd `fa`/`sitecustomize.py` is not imported;
- no session directories or run records created.

Kill-check: remove path validation, `-I`, or `GIT_OPTIONAL_LOCKS=0`; named
negative fixture fails.

### T1 — Git provisioner B2 producer proof

Class: C1, real Git repos and local bare publication remote.

Root: `SessionManager.create_or_attach_session` with a normal `.git` source;
helper-level cases exercise only CT1 internals that the root cannot force.

Oracles:

- target equals the once-captured source commit, is clean, and has exact
  branch/fetch/canonical-push/local-identity read-back;
- ignored/untracked files and source `.git/hooks` admin seats are absent; tracked
  `src/fa/hygiene/hooks/*` templates remain present;
- a real commit succeeds after clearing HOME and all author/committer variables;
- `git push origin` reaches a bare fixture only through command-local
  `url.<file>.insteadOf`, while stored pushurl remains canonical SSH;
- source HEAD/status remain unchanged;
- an injected source fast-forward between capture and clone does not create a
  false postcondition failure.

Kill-check: remove manager dispatch, captured-revision checkout, pushurl producer,
or either local identity command; its named S1 test fails.

Paths: P3; matrices M6–M8.

### T2 — provisioning compatibility/error/adversarial proof

Class: C0p/C3.

Oracles:

- existing manager-owned non-Git fallback copies the controlled fixture and its
  monkeypatched partial-copy rollback test still observes manager `copytree`;
- pre-existing target, invalid branch, invalid source/URL, missing Git, timeout,
  command failure, and read-back mismatch produce the exact CT1 private code;
- manager maps all helper errors to existing `workspace_provision_failed` and
  chains the private cause;
- helper deletes only a target it created; pre-existing/caller-owned targets and
  source are never removed;
- URL credentials/control text never appear in detail/log;
- S2 adds and tests custom non-local pushurl preservation; it is not an S1 API.

Paths: P5 in S1; P13/P14 in S2.

### T3 — entrypoint B2 composition proof

Class: C2 shipped shell root.

Root: `scripts/fa-entrypoint.sh` over real temp Git source/session roots.

Oracle: target branch/fetch/push/local identity + `.active` publication ordering;
Git-invalid IDs never publish `.active`; fake GitHub branch receives push.

Kill-check: remove shell-to-provisioner call.

Paths: P1, P2, P13, P14.

### T4 — entrypoint readiness producer proof

Class: C2.

Oracle: command override stub starts only after readiness stub records completion;
fresh workspace has marker/seats; degraded result prints warning and still
executes override under selected policy.

Kill-check: remove entrypoint readiness call.

Path: P1/P2.

### T5 — new logical-session readiness producer proof

Class: C1.

Root: SessionManager production Git path.

Oracle: readiness callback/real engine runs after clone and before active
manifest/run admission; degraded result emits one CLI warning and still admits;
READY artifacts are verified.

Kill-check: remove manager producer call.

Path: P3.

### T6 — attach/cache-loss/idempotency proof

Class: C1/C0p.

Oracles:

- matching marker + sentinel + env/seats returns fast READY;
- missing pre-commit sentinel forces prewarm;
- corrupt venv/hook/marker repairs;
- no clone/branch reset on attach;
- concurrent ensure calls serialize and finish with one valid marker.

Paths: P4, P11; matrices M2–M3.

### T7 — host alias/locked-state proof

Class: C1 with fake uv/just/pre-commit executables plus one real-uv integration.

Oracles:

- exact command order/flags (`--locked`, `--no-sync`);
- lock drift does not rewrite uv.lock and returns degraded state;
- aliases converge on one fingerprint/marker;
- missing tool has stable reason.

Paths: P6, P10; matrices M4–M5.

### T8 — first startup workspace ready contract

Class: C2.

Oracle: entrypoint-created workspace has CT1–CT4 before `.active`; a first
commit before post-setup sees local author identity and installed hook seats.

Paths: P1.

### T9 — hook ready-path proof

Class: C1 shell hook.

Oracle: bootstrap fast check precedes and then invokes normal hook exactly once;
arguments/stdin preserved.

Path: P7.

### T10 — hook degraded fail-open proof

Class: C3 policy boundary.

Oracle: simulated bootstrap unavailable prints stable warning/log path and
returns 0 for each hook; no normal unavailable command runs.

Path: P8.

### T11 — quality failures remain blocking

Class: C3.

Oracle: after READY, fake normal gate returns 7/9/etc.; hook returns same rc,
not 0.

Path: P9.

### T12 — no recursion/concurrency loss

Class: C0p/C1.

Oracle: concurrent hook/bootstrap attempts serialize; install/prewarm called once
per needed transaction; hook body runs at most once.

Paths: P7–P9.

### T13 — host/CI posture proof

Class: C1/static.

Oracles:

- operator clone alias works;
- deployment update path does not require host hooks/venv;
- CI doctor behavior unchanged;
- docs and task config identify VS Code as convenience.

Paths: P6, P15; matrices M4, M5, M10.

### T14 — cache benchmark

Class: controlled live performance measurement.

Oracle: CT9 report fields and reproducible command outputs, not an inferred
"fast" label.

Matrices: M1–M3.

### T15 — documentation contract

Class: static/docs.

Oracles:

- doc-link checker and markdownlint pass on A23–A25/A27–A29/A33–A35/A37–A39
  and the config-template static check passes on A43;
- repository search for `git clone --local`, `hardlink`, and one-container/
  one-session claims has no current-tense hit in README, ADR/DIGEST, instructions,
  FEATURES, AGENTS, or HANDOFF;
- remaining hits are only historical research/trace/archive/AP-004, this plan's
  own evidence record, or the four correction-bannered PR-note/session-prompt
  files; the test stores that allowlist explicitly and fails on any new path.

### T16 — final live path

Class: C2/C3 live deployment.

Root: host wrapper/container/session Git/GitHub branch and CI.

Oracle: branch remote, file artifacts, source cleanliness, PR checks, denied
merge boundary.

Kill-check: temporarily omit pushurl/readiness producer in a disposable candidate
and show the sheet fails before restoring.

### T17 — isolated runner and targeted-selector contract

Class: C0/C1/C3 shipped-script tests.

Roots: `scripts/run_slice_mutmut.py` subprocess and
`scripts/run_targeted_mutmut.py:main` over synthetic repositories/fake process
boundaries.

Oracles:

- explicit tracked/untracked source and test bytes reach a mode-0700 root-backed
  stage with exact generated TOML;
- test path is in pytest selection/copy but never source paths;
- original pyproject/source/test digests stay unchanged on clean, actionable,
  malformed-tool, timeout, and interrupt paths;
- result JSON validates schema/count identity and diff report contains exact
  actionable names/diffs only;
- raw mutmut rc 0 + survivor maps to rc 1; malformed/unknown/missing counts map
  to rc 3;
- process-group child is gone and stage removed after timeout;
- committed/index/worktree/untracked source union is timeout-bounded,
  return-code-checked, NUL-safe (including newline names), and Semgrep's default
  helper behavior is unchanged;
- targeted pre-start skips remain loud fail-open, while a started executor's
  nonzero rc propagates.

Negative proof:

- source outside `src`, test outside `tests`, source/test or intra-role path
  overlap, non-UTF-8 path, symlink escape, output-parent symlink, non-POSIX,
  wrong mutmut version, invalid numeric bound, and insufficient scratch space
  invoke no mutmut process and create no clean artifact.

Producer kill-check: replace target-wrapper executor call with `return 0`; C1
wiring assertion fails.

### T18 — real mutmut/Pyrefly type-filter and survivor verdict

Class: C4 Linux/POSIX integration using locked dev tools and a synthetic
untracked repository; skip only where mutmut's documented fork requirement is
unavailable.

Fixture source:

```python
def answer() -> str:
    value: str = "foo"
    return value
```

Fixture test asserts exact `answer() == "foo"`.

Oracle:

```text
completed=true
runner rc=0
total=3
killed=2
type_invalid=1
all actionable statuses=0
```

The result must include the type-invalid mutant name while the diff report has no
actionable entry. A sibling permissive fixture/raw fake produces a survivor with
raw mutmut rc 0 and runner rc 1.

Kill-check: remove generated `type_check_command`; expected count changes to
`killed=3,type_invalid=0`, so the test fails without depending on survivors.

### T19 — permanent scope/type configuration and readiness C4 proof

Class: C0 config contract + C4 real scoped mutation.

Oracles:

- exact TOML parsing proves readiness source/test, `also_copy`, literal Pyrefly
  command, positional source-list equality, and mutmut↔gremlins path parity;
- direct permanent scoped Pyrefly emits valid zero-error JSON;
- explicit readiness run completes native clean/forced-fail stages and closes
  `total=874` unless intended source edits change generation;
- current expected classification is `329 killed, 540 type_invalid, 5 survived,
  other=0`; each survivor diff is rechecked against the S3 equivalent rationale;
- no real source/test/config/lock byte changes and no stage residue.

Kill-check: remove any readiness source/test/copy/type/gremlins entry; a named
config assertion fails. Dropping type-invalid from the parser fails denominator
identity.

### T20 — configured weekly-CI and governance producer proof

Class: C1/static workflow/TCB contract.

Oracles:

- workflow installs with exact `uv sync --locked --extra dev`, invokes CT10
  `--configured-scope` rather than raw mutmut, and passes the measured
  five-hour/18,000-second weekly wall bound;
- result and diff paths match summary/upload consumers under `if: always()`;
- summary includes separate `type_invalid`; missing/malformed artifact cannot
  print a clean score;
- weekly job still has schedule/manual triggers, read-only permissions,
  `continue-on-error: true`, pinned actions, and 90-day retention;
- new runner appears in both CODEOWNERS and `_TCB_PATHS`.

Producer kill-check: remove configured runner command, artifact path, or either
TCB seat; test fails.

### T21 — S1–S6 forensic claim-ledger completeness

Class: C1/static review contract.

Oracles:

- exact Git changed/untracked S1–S6 inventory equals the union of CT13 ledger
  artifacts; every G#/GAP#/CT#/P#/M# through S6 has a row and evidence;
- each row names actual producer, consumer, failure behavior, test class, and
  producer kill; stale line references or prose-only evidence fail;
- reproduced findings are `confirmed`; suspicions remain labeled and cannot
  authorize edits; policy-sensitive findings produce a blocking Q#;
- S6 docs/task/alias claims match executable commands and do not assign bootstrap
  work to the model or deployment mirror.

Kill-check: remove any artifact/claim row or S6 authority assertion; completeness
or docs contract fails.

### T22 — clean-candidate real readiness, commit, and local publication

Class: C2/C3 integration.

Oracle: isolated clean candidate with real Git/uv/readiness/hooks has B2-equivalent
local fetch/canonical push config, trusted identity, READY marker/sentinel, four
executable seats, successful real second commit, and local bare branch receipt;
source HEAD/status and provider call count remain unchanged/zero.

Kill-check: remove Git dispatch, identity write, lifecycle readiness call, hook
install, or checked-out wrapper selection; the corresponding state/commit oracle
fails.

### T23 — subprocess and pre-push stdin isolation

Class: C1/C3 process-boundary integration.

Oracle: a readiness child that attempts `sys.stdin.read()` observes EOF, while
the post-ready pre-push normal body receives the original multi-line ref-update
payload byte-for-byte exactly once. Wrapper stdout remains silent and degraded
stderr behavior is unchanged.

Kill-check: remove `_run_process` closed stdin or bypass the hook prelude; child
capture/normal payload/phase oracle fails.

### T24 — clean blocking gates and critical producer mutations

Class: C1/C3/C4.

Oracles:

- clean-candidate full pytest, Ruff/format, Mypy, Pyrefly, shell, compileall,
  lock, four contracts, docs, governance, workflow, and `just check` are green;
- `just check-deep` is either green or emits exact strict actionable mutation
  evidence; no survivor is relabeled clean;
- trap-restored mutations remove/invert manager Git dispatch, readiness
  admission, stdin isolation, hook fail-open boundary, and mutation workflow/TCB
  producers; each is killed by a named test and hashes/modes restore.

Kill-check: the mutations themselves are the negative proof. Any survivor or
unexplained red gate sets `S7_ADMISSION=BLOCK`.

### LIVE-PATH PROOF blocks

#### LP1 — managed logical session

```text
root: SessionManager.create_or_attach_session
matrix: M1/M2
producer: fa.session.workspace.provision_git_workspace + readiness admission
consumer: CLI run workspace/session state + Git hooks
oracle: CT1–CT4 filesystem/Git state
kill-check: T1/T5
paths-covered: P3/P4/P11
pyramid: A
```

#### LP2 — entrypoint startup workspace

```text
root: scripts/fa-entrypoint.sh
matrix: M1/M3
producer: shell-to-provisioner/readiness calls
consumer: .active, command override/auto-run, post-setup Git
oracle: ordering + branch/fetch/push/identity/env/hooks
kill-check: T3/T4/T8
paths-covered: P1/P2/P13/P14
pyramid: A
```

#### LP3 — publication boundary

```text
root: managed session git push origin <feature-branch>
matrix: live AIO/GitHub
producer: B2 pushurl + session branch
consumer: GitHub feature ref/PR CI; human merge gate
oracle: remote feature ref + required checks + unchanged /repo
kill-check: T16
paths-covered: P3/P9
pyramid: A/C3
```

#### LP4 — mutation feedback authority

```text
root: scripts/run_slice_mutmut.py CLI / run_slice
matrix: M11–M14
producer: isolated mutmut/Pyrefly execution + status classifier
consumers: explicit operator, targeted pre-push selector, configured weekly CI
oracle: schema-v1 count identity + exact action diffs + synthesized exit
kill-check: T17/T18/T20
paths-covered: P16–P20
pyramid: A/C4
```

#### LP5 — integrated clean candidate

```text
root: isolated candidate Git checkout + checked-out wrapper + installed hooks
matrix: M15–M17
producer: S1–S6 Git/readiness/hook/alias/document authorities
consumer: real commit/local publication + S7 admission
oracle: CT13 ledger, READY/Git state, exact stdin, zero-diagnostic gates
kill-check: T21–T24
paths-covered: P21–P24
pyramid: A/C2/C3/C4
```

---

## 7. Risks, rollback, open questions

### Risks

| RK | Risk | Mitigation | Detection |
| --- | --- | --- | --- |
| RK1 | pushurl accidentally remains local `/repo` | final read-back assertion; B2 test | T1/T3/T16 |
| RK2 | HTTPS token printed in log/probe | redaction + `%q`/`repr`; no config dump | T0/T2 |
| RK3 | manager tests pass only through non-Git fallback | explicit real-Git C1 root | T1/T5 |
| RK4 | image-imported installer links hooks to `/opt` source | explicit workspace source dir contract | T5/T8 |
| RK5 | marker survives but pre-commit cache is gone | cache sentinel active consumer | T6 |
| RK6 | warn-only bootstrap swallows real test failure | typed state branch before normal gate; preserve rc | T10/T11 |
| RK7 | cold prewarm makes startup unacceptable | measurement-first S7; no latency claim before data | T14 |
| RK8 | pre-commit cache exceeds 500 MiB tmpfs | measure peak/size; degraded warning; separate cache plan | T14 |
| RK9 | concurrent attach/hook corrupts marker/seats | `flock` whole transaction + atomic marker | T6/T12 |
| RK10 | raw output executes terminal controls | safe formatting in probe/log | T0 |
| RK11 | diagnostic Git status writes index/executes fsmonitor | optional locks disabled; fsmonitor disabled | T0 |
| RK12 | production docs preserve obsolete hardlink/session claims | bounded contradiction sweep | T15 |
| RK13 | existing user-customized session remote is clobbered | repair only missing/local managed pushurl | T2/T3 |
| RK14 | Git clone pack increases disk/session growth | S7 sizes + existing retention backlog; no hardlink workaround | T14 |
| RK15 | host dev/deployment checkout roles mix again | explicit docs and alias paths | T13/T15 |
| RK16 | clean clone lacks author identity; agent repair denied | trusted local identity + real commit with identity env cleared | T1/T3/T8 |
| RK17 | `/repo` fast-forwards between source read and clone verification | capture one commit; checkout/read back that capture | T1 race test |
| RK18 | helper errors leak new/unstable manager codes | one `workspace_provision_failed` map + existing code inventory | T2 |
| RK19 | raw mutmut rc 0 falsely marks survivors clean | closed status/count classifier; survivor fixture | T17–T18 |
| RK20 | type filter hides its contribution or valid runtime concerns | separate count/names; no relabel as killed; readiness A/B record | T18–T19 |
| RK21 | repository source/test/config is damaged by mutation staging | isolated copies, no-follow containment, digest postcondition | T17/T19 |
| RK22 | timeout leaves mutmut fork children or stage residue | new process group, TERM/KILL, `finally` cleanup | T17 |
| RK23 | configured source/type/gremlins lists drift | exact TOML set/positional parity tests | T19 |
| RK24 | new runner becomes an unreviewed gate bypass | CODEOWNERS + `_TCB_PATHS` parity | T20 |
| RK25 | known Linux-equivalent survivors are silently accepted | strict rc 1, exact diffs, no baseline/pragma/allowlist | T19/Q6 |
| RK26 | focused fake roots hide integrated runtime failure | clean-candidate real wrapper/hooks/commit | T22–T24 |
| RK27 | readiness child consumes pre-push ref stdin | DEVNULL child input + real forwarding oracle | T23 |
| RK28 | dirty-worktree failures are carried as “known” into merge | isolated exact-byte clean candidate; zero unexplained gates | T24 |
| RK29 | review becomes unbounded refactor or policy change | explicit files, P24 stop/Q#, CT13 ledger | T21 |
| RK30 | custom/external hooks path is overwritten without policy | discover effective path; stop/Q# before remediation | T21/M17 |

### Rollback

No irreversible DB or source migration is introduced.

- Git provisioner rollback: revert S1/S2; disposable new workspaces may be deleted;
  existing sessions retain independent `.git` and continue to attach.
- Readiness rollback: revert lifecycle calls/core module; `.venv`, ignored markers,
  hook seats, and cache sentinels are disposable local artifacts.
- Hook rollback: reinstall current four hook sources via pre-change `just install`.
- Marker rollback: remove `.fa/ready-state.json`; no manifest/session DB change.
- S3.5 rollback: restore prior targeted/workflow commands and mutmut/gremlins
  lists, delete the new runner/tests, and remove disposable `mutants/` plus
  root-backed stage directories. No product/runtime state or DB migration exists.
  Do not partially retain `type_check_command` without the separate-count
  reporter: mutmut 3.6's stock export would make the denominator incomplete.
- No cache mount ships in this plan, so no cache data migration/rollback.
- If a deployed slice fails, keep `/repo` RO, stop creating new sessions, revert
  commit through operator-controlled main, run `fa update`, and preserve failed
  session/log for diagnosis before cleanup.

Feature flag: none. The existing explicit commands and warn-only degradation are
sufficient; adding a permanent config flag would create an unrequested bypass
surface. Git revert is the rollback authority.

### Open questions

#### Q1 — live server baseline (RESOLVED)

The 2026-08-12 S0 execution record above supplies both clone identities,
remotes, mounts, active workspace Git/readiness state, manager roots, and cache
filesystems/sizes. It confirmed rather than contradicted GAP1–GAP9. S1 is
unblocked.

#### Q2 — persistent cache (NON-BLOCKING; default DEFER)

Default: keep tmpfs through S7. Do not add `/srv/first-agent/cache/*` mounts in
this plan. After measurement, author a separate plan if persistence is justified.

#### Q3 — explicit push URL override surface (NON-BLOCKING)

Default: support `FA_REPO_PUSH_URL` as an operator-provided override. Existing
Compose `env_file` loading makes it available in-container; S1 explicitly wires
it through `src/fa/cli.py:_session_manager_for_args` and the manager constructor.
Without it, consume `/repo`'s verified `remote.origin.pushurl`; canonicalize only
the closed CT2 GitHub URL shapes. The live mirror already supplies the intended
SSH URL. Validate as a Git argv value, never shell.

#### Q4 — old session remote repair (NON-BLOCKING)

Default: repair only an absent pushurl or a pushurl exactly equal to the current
`file://` fetch URL (`file:///repo` in production). Preserve every other custom
pushurl and emit `[WORKSPACE_BOOTSTRAP]` warning. Missing/invalid source
publication authority remains fatal when local repair needs it, but does not
block preserving an already non-local custom workspace pushurl.

#### Q5 — safe result for preserved secret-bearing custom push URL (RESOLVED)

Decision: option 1, **preserve + redacted sentinel**, selected by the operator.
Unsafe/unsupported custom Git config remains untouched; JSON returns
`<preserved-custom-redacted>`, action is `preserved_custom`, warning is generic,
and S2 admission continues. CT2-supported credential-free custom values may be
returned exactly.

Verified conflict:

- S2/Q4 requires preserving every non-local custom `origin.pushurl` and
  continuing with a warning;
- CT2/CT8 prohibit credentials from command output/logs;
- `configure-existing` must serialize `ExistingWorkspaceState.push_url`;
- an existing custom URL may contain HTTPS userinfo, a query token, control
  text, or an unsupported scheme that cannot safely be returned raw.

Disposition:

- **Selected:** preserve + redacted sentinel. Leave Git config untouched, return
  `push_url="<preserved-custom-redacted>"`, set
  `remote_action="preserved_custom"`, and print a generic warning. Supported,
  credential-free custom URLs may still be returned exactly.
- **Rejected:** preserve + fail admission; this needlessly blocks an
  operator-customized workspace.
- **Rejected:** expand the result schema; the sentinel closes disclosure without
  a seventh field.
- **Rejected:** serialize the raw unsafe URL; that violates the established
  credential-nondisclosure boundary.

S2 is unblocked; tests for P14 must assert both config preservation and output
redaction.

#### Q6 — equivalent survivors under a strict slice runner (RESOLVED BY EXISTING POLICY)

Default/decision: do not auto-accept, baseline, suppress, or relabel equivalent
survivors. CT10 returns 1 for every survivor and emits its exact diff. The five
currently re-proven readiness equivalents therefore remain review-visible in
Linux runs. This follows the unchanged mutation-clearing rule that equivalence
is a human proof, not a percentage trick, and honors the user's bounded S3.5
scope (runner, type filtering, permanent readiness scope only).

The existing `FA_SKIP_TARGETED_MUTATION=1` is retained as an explicit operator
override after reviewing emitted evidence; S3.5 adds no second bypass. A later
request may approve pragmas or a reviewed equivalent ledger, but neither is
required or silently introduced here.

#### Q7 — custom hook-path ownership and collision policy (RESOLVED)

Confirmed M17/P24 behavior:

- `src/fa/hygiene/hooks/_util.py:resolve_hooks_dir` asks Git for the effective
  hooks path and accepts an absolute path outside the managed checkout;
- `src/fa/workspace_bootstrap.py:_install_workspace_hooks` invokes
  `install_hooks(..., force=True)`;
- `src/fa/hygiene/hooks/install.py:_install_one` unlinks an existing target when
  forced, with no FA-ownership or containment check;
- the existing custom-path test covers an empty checkout-contained directory,
  not an external path or a non-FA seat collision;
- a trap-cleaned scratch probe set an absolute external `core.hooksPath`, placed
  an operator `pre-commit` there, ran the shipped installer with `force=True`,
  and changed its SHA-256 from
  `004a1dbb52e21ef8b040e7eb867e83b5e8b97b9104df42ec869a2fe5e23f40cb` to
  `8c8a903470c46194bc42780b4099ad2ef249128407fd2f28106ca99bd07c196b`.

Operator decision: custom and unowned hooks are preserved, not integrated.
Automatic readiness manages only Git's default hooks directory, and only when
all four target seats are absent or verifiably FA-owned by exact current-copy or
exact checked-out-source symlink identity. Any configured effective custom path
is operator-owned even when checkout-contained. Any non-FA default-seat
collision is also operator-owned. In both cases readiness must:

- preserve hook bytes, modes, links, and Git config exactly;
- avoid installing, relocating, disabling, executing, or chaining unknown code;
- invalidate stale READY authority and return a typed DEGRADED environment state
  under the existing fail-open policy;
- emit no raw custom path or hook content in telemetry/warnings.

The explicitly invoked installer `--force` remains an operator repair tool; this
restriction applies to automatic readiness. Extensible hook dispatch is deferred
to a separate future plan only if a concrete use case justifies ordering,
recursion, argv/stdin, return-code, timeout, environment, and trust contracts.
Q7 is resolved; E12 and its M17 negative proof must pass before A54 can emit
`S7_ADMISSION=ALLOW`.

#### Q8 — cold pre-commit cache exceeds production tmpfs cap (RESOLVED)

S7's controlled cold run measured pre-commit cache peak at 543,865,009 bytes
and total isolated HOME-cache peak at 610,702,469 bytes before gitleaks' Go
environment failed with ENOSPC. Production Compose capped `/home/fa/.cache` at
524,288,000 bytes. The benchmark used an exact candidate, empty caches, ext4
workspace, tmpfs cache, and the locked commands; it aborted on rc 3 and cleaned
all disposable roots.

Operator decision: choose the simplest robust response until real latency data
justifies additional architecture. Keep uv's separate 2 GiB tmpfs, all cache
data non-persistent, and the current recreation/trust boundary. A provisional
1 GiB proxy still failed near its ceiling, so the same cold build was completed
on ext4 while sampling allocated blocks. HOME-cache peak was 993,908,224 bytes;
1 GiB would leave only 79,833,600 bytes (7.4%). The calibrated ceiling is
`1536M` (1,610,612,736 bytes), leaving 616,704,512 bytes (38.3%) headroom without
preallocating that memory.

Persistent caches, baked hook environments, hook-distribution redesign, and
quality-gate weakening are rejected for this slice. If a production-equivalent
run reaches 1536 MiB or shows unacceptable cold latency, stop again and author
the separate P2 cache/image plan. Persisting uv alone would not resolve the
finding because failure occurred in HOME/pre-commit state.

Q8 is resolved and verified: A66/A67 pin the 1536M/2G ephemeral seats, and A26
records the completed CT9/T14 matrix plus measured Q2 deferral.

---

## 8. Research-note and prior-agent disposition

| RN | Input claim/proposal | Verdict | Why | Anchor |
| --- | --- | --- | --- | --- |
| RN1 | one stdlib readiness function + fingerprint | **Accept/Rewrite** | marker is a hint; add lock, active checks, cache sentinel | CT3/CT4, S3 |
| RN2 | install only in manager provisioner | **Reject as incomplete** | entrypoint fresh/resume and attach stay uncovered | P1–P4, S2–S3 |
| RN3 | hook source can bootstrap a fresh clone with no seat | **Reject** | Git cannot invoke absent seat; lifecycle is primary producer | CT5, S5 |
| RN4 | self-repair in installed hooks | **Accept/Rewrite** | secondary fallback with typed warn-only mapping; no exec retry loop | CT5, S5 |
| RN5 | put bootstrap in all four hook headers | **Accept** | argument/stdin contracts must be preserved and tested | T9–T12 |
| RN6 | guard file prevents recursion | **Rewrite** | transaction `flock` is authority; install/prewarm does not itself fire Git events | CT3/CT5 |
| RN7 | bootstrap deployment mirror through `fa-update` hooks | **Reject** | `/srv` is clean deployment mirror, not commit surface | G6 non-goal, S6 |
| RN8 | bootstrap canonical operator `~/First-Agent-dev` | **Accept** | user-selected dev surface; explicit alias authoritative, VS Code convenience | CT7, S6 |
| RN9 | VS Code auto-task is guarantee | **Reject** | permission/user trust prevents repository authority | CT7 |
| RN10 | keep VS Code task as convenience | **Accept** | useful but non-load-bearing | S6 |
| RN11 | `uv sync --frozen` proves project/lock readiness | **Reject** | frozen skips lock freshness; operator chose `--locked` | CT3, T7 |
| RN12 | hooks need no network after custom seat install | **Reject** | remote pre-commit envs are lazy unless prewarmed | CT3, S3 |
| RN13 | prewarm all hook environments | **Accept** | explicit operator intent; cache sentinel required | CT3/CT4 |
| RN14 | persistent uv cache immediately | **Defer** | no measured latency/size; ignores pre-commit cache | S7/Q2 |
| RN15 | `/root/.cache/uv` is warm source | **Reject** | runtime config points to tmpfs `/tmp/uv-cache`; runtime user is `fa` | GAP9 |
| RN16 | set manifest status `bootstrap-warned` | **Reject** | current manager accepts only active; readiness is separate state | CT3/CT4 |
| RN17 | fail-closed agent run | **Reject by operator policy** | operator selected warn-only; CI/human merge authority retained | CT5/CT6 |
| RN18 | fail-open should swallow quality failures | **Reject** | only bootstrap unavailability allows; real gate rc blocks | CT5, T11 |
| RN19 | one container equals one logical session | **Reject as stale** | S2 selector creates/attaches persistent sessions | Non-goal, P3/P4 |
| RN20 | manager copytree is safe with clean mirror | **Reject for Git path** | ignored/main/admin state and copy race remain | CT1, S1 |
| RN21 | use `git clone --local` hardlinks | **Reject** | AP-004 ownership/cross-device evidence; current pack transport is intentional | Non-goal |
| RN22 | B2 local fetch + GitHub pushurl | **Accept** | explicit operator architecture; two-stage authority | CT2, S1–S2 |
| RN23 | hardcode GitHub URL at every call site | **Rewrite** | one normalizer + optional override avoids drift/fork breakage | CT2, S1 |
| RN24 | worktree dispatcher redesign in same PR | **Defer** | managed sessions are full clones; not required for current G# | Non-goal |
| RN25 | remove all bootstrap recovery docs | **Rewrite** | remove LLM responsibility, keep operator doctor/recovery surface | S6/S8 |
| RN26 | agent sets identity on first commit | **Reject** | sandbox denies it; trusted provisioning installs local identity | CT1, S1 |
| RN27 | implement existing-workspace repair in S1 | **Defer to S2** | no S1 production consumer; resume policy belongs with entrypoint consumer/tests | S2 |
| RN28 | add proper explicit slice mutation runner | **Accept/Rewrite** | isolate staging, separate source/test roles, synthesize verdict, and wire real consumers | CT10, S3.5, T17–T18 |
| RN29 | add type-invalid mutant filtering | **Accept/Rewrite** | direct scoped Pyrefly works; Mypy clean JSON and full-project Pyrefly do not | CT11, T18–T19 |
| RN30 | permanently include readiness engine | **Accept** | S3 risk/874-mutant evidence justifies permanent mutmut+gremlins scope | CT12, T19–T20 |
| RN31 | preserve incremental mutation cache | **Defer** | correctness-first disposable stages avoid mutmut 3.6 stale test/config results and cache policy | S3.5 non-goal |
| RN32 | enable `mutate_only_covered_lines` now | **Defer** | not operator-approved; requires full-vs-covered experiment | S3.5 non-goal |
| RN33 | add equivalent-mutant ledger/pragmas now | **Defer** | Q6 keeps exact survivors visible; no fourth feature added | Q6 |
| RN34 | modify planning/testing/mutation skills | **Defer by operator direction** | keep existing skills byte-identical for this slice | S3.5 non-goal |
| RN35 | add post-S6 code review/overall progress assessment | **Accept/Rewrite** | make it an evidence-bearing clean-candidate gate with bounded remediation, not a prose review | CT13/S6.5/T21–T24 |
| RN36 | treat focused green plus classified full-gate failures as production-grade | **Reject** | actual hook commit is blocked; clean candidate must close or own every gate | GAP19/T22–T24 |

---

## 9. Definition of Done

### State

Before:

```text
manager Git workspace = raw deployment filesystem copy
entrypoint origin.push = file:///repo
fresh session .venv/hooks = absent
pre-commit env readiness = unknown
bootstrap instruction = human/LLM/manual residue
cache cost = unmeasured
slice mutation = live config rewrite + raw survivor-blind rc
type-invalid mutants = not filtered/reported
readiness permanent mutation scope = absent
```

After:

```text
managed Git workspace = committed local /repo clone
branch = agent/<session-id>
origin.fetch = file:///repo
origin.push = canonical GitHub SSH (source authority or explicit validated override)
local author = First Agent <agent@first-agent.local>
readiness attempt completes before LLM
READY = locked env + four seats + prewarmed hook env + two sentinels
DEGRADED = structured warning/log + operator-selected allow
quality failure = still blocking
operator dev clone and deployment mirror roles are explicit
cache persistence decision is measurement-backed or explicitly deferred
slice mutation = isolated explicit/configured runner with exact artifacts/exits
type-invalid mutants = scoped Pyrefly, separate count in closed denominator
readiness = permanent mutmut + pytest-gremlins scope
```

### Falsifiable DoD checklist

- [x] **G1 L3:** T1/T3/T16 fail if pushurl producer is removed.
- [x] **G2 L3:** T1 fails if manager reverts to copytree, copies ignored state,
  omits local identity, or checks out a different commit from the captured
  source revision.
- [x] **G3 L3:** T4/T5/T8 fail if lifecycle readiness call is removed.
- [x] **G4 L3:** live trace/provider fake proves zero model calls before readiness;
  no AGENTS bootstrap instruction is needed for managed sessions.
- [x] **G5 L3:** T10 proves degraded allow; T11 proves real quality failure blocks.
- [x] **G6 L3:** T13 proves host dev alias and deployment-mirror non-requirement.
- [x] **G7 L3:** A26 records CT9 cold/warm/resumed evidence, cap sizing, and
  measured Q2 deferral.
- [ ] **G8 L3:** T15 docs clean and T16 live branch/CI/human boundary green.
- [x] **G9 L3:** T17/T18 fail if isolated executor, strict status classifier,
  type filter, or targeted delegate is removed; T19/T20 fail if permanent
  readiness/workflow producers are removed.
- [x] **G10 L3:** T21–T24 produced a complete S1–S6 ledger, clean candidate,
  real hook/commit/stdin proof, zero unexplained blocking gates, and killed
  critical producers before `S7_ADMISSION=ALLOW`.
- [x] All P1–P24 and M1–M17 have controlled coverage; A26 explicitly records
  the M1–M3 live-image limitations retained for S9.
- [x] No provider secrets, remote credentials, task text, raw model bodies, or
  environment dumps appear in markers/logs/mutation results.
- [x] `just check` passes on the final candidate. Strict mutation evidence emits
  reviewed equivalent diffs; known equivalents are never reported as clean.
- [x] Targeted manual mutation/kill-checks for clone, pushurl, lifecycle
  readiness, degraded mapping, quality rc, governance, dependency lint, and hook
  ownership all fail as specified, then source is restored and gates rerun.
- [ ] Deployment `/repo` status remains clean after live session/push proof.
- [ ] Agent branch can open PR and trigger GitHub CI but cannot merge/update main;
  operator retains final merge and `fa update` authority.

Contracts reach:

| Contract | Done state |
| --- | --- |
| CT1 | IMPLEMENTED + T1/T2/T3/T16 VERIFIED |
| CT2 | IMPLEMENTED + T1/T3/T16 VERIFIED |
| CT3 | IMPLEMENTED + T4–T8 VERIFIED |
| CT4 | IMPLEMENTED + T6/T7 VERIFIED |
| CT5 | IMPLEMENTED + T9–T12/T23 real-wrapper stdin/rc VERIFIED |
| CT6 | IMPLEMENTED + T4/T5/T8 VERIFIED |
| CT7 | IMPLEMENTED + T13 VERIFIED |
| CT8 | IMPLEMENTED + T0/T7/T10 VERIFIED |
| CT9 | IMPLEMENTED + A26/T14 measured Q2 decision VERIFIED |
| CT10 | IMPLEMENTED + T17/T18 isolated execution, identity, artifacts, and exits VERIFIED |
| CT11 | IMPLEMENTED + T18/T19 scoped type-invalid classification VERIFIED |
| CT12 | IMPLEMENTED + T19/T20 permanent readiness/configured CI producer VERIFIED |
| CT13 | IMPLEMENTED + T21–T24/A54 clean integrated acceptance VERIFIED |

---

## 10. Anti-theater and READY gate

### Anti-theater checklist

- [x] Every referenced current symbol/path was read/grepped; NEW artifacts are
  marked NEW.
- [x] Every G# maps to GAP#, CT#, S#, T#, and artifact/non-goal.
- [x] Signal contracts name producers and consumers.
- [x] Kill-checks target producer sites.
- [x] Path inventory covers all verified creation/attach/hook/host/cache/mutation paths.
- [x] Matrix rows have steps/tests.
- [x] Fixtures at Git/lifecycle boundaries use real temporary Git repositories;
  mutation tooling has both process-boundary fakes and a locked real C4 fixture.
- [x] Security boundaries have adversarial tests.
- [x] Prior-agent/research claims are dispositioned rather than copied.
- [x] No persistent cache/service/dependency added without evidence.
- [x] Tests cannot enter mutation source scope by construction and raw mutmut rc
  cannot satisfy the clean oracle.
- [x] All IDs in v14 resolve.

### READY gate

- [x] Non-trivial preflight recorded.
- [x] Depth P3 declared after preflight.
- [x] Intent/non-goals/current/target state concrete.
- [x] Function, signal, data, invariant, security contracts present.
- [x] Path/matrix coverage complete.
- [x] Steps are file/symbol specific with exit criteria.
- [x] Verification and live-path proof specified.
- [x] Research-note disposition complete.
- [x] Blocking Q1 resolved with actual server probe output and recorded S0 facts.
- [x] Q5 remains authoritative; Q6 is closed by strict existing mutation policy.
- [x] Non-blocking questions have defaults.

The v15 plan-authoring gate held before execution. S1–S6.5 are executed and
`S7_ADMISSION=ALLOW` admitted measurement. Q8's stop worked as designed and the
operator selected the bounded ephemeral-cap response, calibrated from a
completed allocated-block peak to 1536 MiB. A26/T14, Q2, and S8/T15 are complete.
Current plan status is **READY v23**; S9 is the remaining live slice and retains
its external prerequisites. Overall feature production readiness remains
unclaimed until S9.

---

## 11. Artifacts inventory

| Artifact | Path | Action | Owner |
| --- | --- | --- | --- |
| A1 | `fa-bootstrap-preflight-probe.sh` | add validated read-only operator probe; retain for S9 | S0/S9 |
| A2 | `worklogs/implementation-plans/PLAN-session-workspace-readiness-bootstrap.md` | add/update | plan/S0–S9 |
| A3 | `src/fa/session/workspace.py` | NEW Git provisioner/B2 contract | S1–S2 |
| A4 | `src/fa/session/manager.py` | edit production Git provisioning/readiness | S1/S3 |
| A5 | `tests/test_session_workspace_provisioning.py` | NEW | S1–S2 |
| A6 | `tests/test_session_lifecycle.py` | edit fallback/readiness coverage | S1/S3 |
| A7 | `scripts/fa-entrypoint.sh` | edit B2/readiness ordering | S2/S3 |
| A8 | `scripts/fa-post-setup.sh` | edit real push destination smoke | S2 |
| A9 | `tests/test_fa_entrypoint.py` | edit C2 contracts | S2/S3 |
| A10 | `tests/test_deploy_scripts.py` | edit script/config contract tests | S2/S8 |
| A11 | `src/fa/workspace_bootstrap.py` | NEW readiness engine | S3–S6.5 |
| A12 | `src/fa/hygiene/hooks/install.py` | edit explicit source-dir contract | S3/S6.5 |
| A13 | `tests/test_workspace_bootstrap.py` | NEW readiness and Q7 ownership authority | S3–S4/S6.5 |
| A14 | `scripts/bootstrap/workspace.py` | NEW thin stdlib wrapper | S4 |
| A15 | `scripts/bootstrap/host_bootstrap.py` | edit compatibility alias | S4 |
| A16 | `justfile` | edit alias/convergence | S4 |
| A17 | `.gitignore` | edit runtime marker policy | S4 |
| A18 | `.fa/host-bootstrap.json` | delete tracked machine marker after migration | S4 |
| A19 | `src/fa/hygiene/hooks/pre-commit` | edit self-repair header/locked runs | S5 |
| A20 | `tests/test_hygiene_hooks_self_bootstrap.py` | NEW | S5/S6.5 |
| A21 | `tests/test_hygiene_hooks_install.py` | edit normal rc/seat/default-path coverage | S3/S5/S6.5 |
| A22 | `.vscode/tasks.json` | verify unchanged convenience consumer | S6 |
| A23 | `AGENTS.md` | edit managed-bootstrap responsibility | S6/S6.5/S8 |
| A24 | `knowledge/instructions/01-install.md` | edit clone roles/recovery | S6/S6.5/S8 |
| A25 | `knowledge/instructions/02-operations.md` | edit topology/B2/readiness | S6/S6.5/S8 |
| A26 | `worklogs/implementation-plans/session-workspace-readiness-benchmark.md` | NEW measurement report | S7 |
| A27 | `knowledge/adr/ADR-13-workspace-isolation.md` | amendment | S8 |
| A28 | `knowledge/adr/DIGEST.md` | edit summary | S8 |
| A29 | `README.md` | edit diagram wording | S8 |
| A30 | `worklogs/implementation-plans/session-workspace-readiness-live-verification.md` | NEW | S9 |
| A31 | `src/fa/cli.py` | edit push-URL/readiness composition-root wiring | S1/S3 |
| A32 | `tests/test_cli.py` | edit composition-root and provider-order proof | S1/S3 |
| A33 | `knowledge/overview/FEATURES.md` | edit current transport/readiness claim | S8 |
| A34 | `knowledge/pr-notes/workspace-isolation.md` | add historical correction banner | S8 |
| A35 | `worklogs/pr-notes/workspace-isolation.md` | add historical correction banner | S8 |
| A36 | `src/fa/hygiene/hooks/__init__.py` | mirror explicit hook-source keyword | S3 |
| A37 | `knowledge/ci-guardrails-reference.md` | edit lifecycle/recovery authority | S6/S8 |
| A38 | `worklogs/S13-NEXT-SESSION-START.md` | add superseded-command banner | S8 |
| A39 | `worklogs/S13-SESSION-START-PROMPT.md` | add superseded-command banner | S8 |
| A40 | `src/fa/hygiene/hooks/pre-push` | edit self-repair header/locked runs | S5 |
| A41 | `src/fa/hygiene/hooks/prepare-commit-msg` | edit self-repair header/locked runs | S5 |
| A42 | `src/fa/hygiene/hooks/commit-msg` | edit self-repair header/locked runs | S5 |
| A43 | `.env.fa.template` | document optional push-URL override | S8 |
| A44 | `src/fa/hygiene/hooks/_util.py` | bound effective lookup + deterministic default hook path | S3/S6.5 |
| A45 | `scripts/run_slice_mutmut.py` | NEW isolated explicit/configured mutation executor | S3.5 |
| A46 | `tests/test_slice_mutmut.py` | NEW runner/selector/config/real-tool authority suite | S3.5/S6.5 |
| A47 | `scripts/run_targeted_mutmut.py` | reduce to Git selector + CT10 delegate | S3.5 |
| A48 | `scripts/_git_diff.py` | opt-in NUL-safe worktree/untracked discovery | S3.5 |
| A49 | `pyproject.toml` | permanent readiness/type/copy/gremlins mutation config | S3.5/S6.5 |
| A50 | `.github/workflows/tests.yml` | configured runner + complete result/diff artifacts | S3.5 |
| A51 | `.github/CODEOWNERS` | owner-protect NEW runner | S3.5 |
| A52 | `scripts/check_protected_paths.py` | add NEW runner to exact TCB authority | S3.5 |
| A53 | `tests/test_workspace_bootstrap_aliases.py` | NEW S4 wrapper/host/just/marker C1/C3 suite, outside core C4 selection | S4/S6 |
| A54 | `worklogs/implementation-plans/session-workspace-readiness-s1-s6-review.md` | NEW CT13 claim ledger and production assessment | S6.5 |
| A55 | `tests/test_workspace_readiness_integration.py` | NEW clean-candidate/real-hook C2/C3 authority | S6.5 |
| A56 | `tests/test_authoring_protected_paths_parity.py` | edit semantic CODEOWNERS/TCB parity oracle | S6.5 |
| A57 | `src/fa/egress_proxy/server.py` | minimal reproduced Pyrefly signature correction only | S6.5 |
| A58 | `scripts/_console.py` | minimal reproduced Mypy narrowing only | S6.5 |
| A59 | `tests/test_no_builtin_shadow.py` | minimal reproduced annotation only | S6.5 |
| A60 | `tests/test_git_diff_helper.py` | remove only reproduced stale ignores | S6.5 |
| A61 | `tests/test_semgrep_pin.py` | narrow optional argv before join | S6.5 |
| A62 | `src/fa/hygiene/hooks/status.py` | correct reproduced stale hook-status documentation only | S6.5 |
| A63 | `scripts/check_shell_syntax.sh` | restore tracked executable mode; no content change | S6.5 |
| A64 | `scripts/check_dependency_contract.py` | remove Python<3.11 fallback under project Python>=3.13 | S6.5 |
| A65 | `knowledge/research/ai-assisted-maintenance-mutation-feedback-loops-2026-08.md` | retained requested maintenance/mutation research note; no runtime authority | research/S3.5 |
| A66 | `docker-compose.fa.yml` | raise only ephemeral HOME-cache tmpfs ceiling 500 MiB→1536 MiB | S7/Q8 |
| A67 | `tests/test_container_build_invariants.py` | parsed-YAML cache-seat/cap authority | S7/Q8 |

No file outside this inventory may be edited during execution without revising
the plan and re-running the READY gate.

---

## Executor handoff

S1–S8 are implemented. S9 is next only after its declared green PR CI and human
merge prerequisites are available. Then:

1. follow S9's live sheet and keep edits inside its artifact subset;
2. run each slice's targeted/static/diff AFTER EDIT GATE and report actual output;
3. use CT10 for explicit mutation slices and preserve separate type-invalid
   counts; never treat raw mutmut rc as a clean verdict;
4. stop on new policy/security questions rather than adding a survivor baseline,
   pragma, filter, cache, or bypass;
5. keep the five readiness equivalents review-visible unless a later approved
   slice changes their policy;
6. complete S9 before calling the overall feature shipped.
