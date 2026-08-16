# PLAN: Live managed-workspace readiness closure

Plan-ID: `PLAN-session-workspace-readiness-live-closure`

Status: **LIVE-VERIFIED v19 — recreated PID1 workspace passes §7; later parent proof pending**

Depth: **P2** — live diagnosis, cross-layer runtime configuration, blocking
container CI, operator-controlled rollout, and rollback. No ADR or public API
change is planned.

Revision: **v19 — merged SHA 33943fa3 deployed; identity, topology, readiness, and preservation all PASS**

Date: 2026-08-14

Upstream context:

- parent plan:
  [`PLAN-session-workspace-readiness-bootstrap`](./PLAN-session-workspace-readiness-bootstrap.md)
  v23;
- controlled cache evidence:
  [`session-workspace-readiness-benchmark`](./session-workspace-readiness-benchmark.md);
- tracked pre-merge/live protocol:
  [`session-workspace-readiness-live-verification`](./session-workspace-readiness-live-verification.md);
- NEW post-merge diagnosis/evidence sheet named by the operator:
  `session-workspace-readiness-live-verification-from-6.md`;
- integrated S1–S6 review:
  [`session-workspace-readiness-s1-s6-review`](./session-workspace-readiness-s1-s6-review.md);
- provisional patch: `npm-cache-readiness-closure-on-7ba1361.patch`;
- current public `main` at plan authoring:
  `e8f7ee5b3bf4e62402dcb8ca35a672939b726fac`;
- deployed/runtime evidence revision:
  `7ba13616e3d649c0d593612dc266734e8bccc9fe`.

This is a child plan for the blocked live portion of parent S9/T16. It does not
reopen completed S1–S8 design decisions. It closes the live cause, repairs only
the proven producer, and requires a recreated deployment to pass §7 before the
parent may continue.

---

## Preflight log

### Roots checked

Runtime/admission:

- `scripts/fa-entrypoint.sh::_prepare_entrypoint_workspace` and startup
  publication around lines 162–223;
- `src/fa/cli.py:_prepare_managed_workspace` and
  `_session_manager_for_args` around lines 126–163;
- `src/fa/session/manager.py:SessionManager._new_session` and
  `_attach_session` around lines 256–355;
- `src/fa/workspace_bootstrap.py:_command_environment`, `_run_process`,
  `_ensure_locked`, `check_workspace_ready`, and `ensure_workspace_ready`;
- `scripts/bootstrap/workspace.py`, the checked-out stdlib wrapper.

Container/deployment:

- `Dockerfile.fa` runtime `HOME`, user, and workdir block;
- `docker-compose.fa.yml` read-only root, environment, tmpfs, mounts, and
  healthcheck;
- `.github/workflows/advisory.yml:container-build`, including the session
  workspace smoke;
- `scripts/fa-update.sh:verify_runtime_storage` and its main call site;
- runtime storage blocks in `scripts/fa-clean-rebuild.sh` and
  `scripts/fa-post-setup.sh`;
- `scripts/fa` delegation to update/clean-rebuild.

Hooks/pre-commit:

- `.pre-commit-config.yaml`; the local file identifies remote repositories but does not itself prove which one owns the failed Node environment — CT2 binds that from the retained log;
- `src/fa/hygiene/hooks/pre-commit`, especially readiness-before-`NO_PROXY`
  ordering;
- `src/fa/hygiene/hooks/install.py`, `status.py`, and all four source seats;
- `tests/test_workspace_bootstrap.py` reason/process/log contracts;
- `tests/test_hygiene_hooks_self_bootstrap.py` checked-out wrapper and stdin
  authority.

Container/deploy tests:

- `tests/test_container_build_invariants.py` Dockerfile/Compose/workflow
  structural authority;
- `tests/test_deploy_scripts.py` runtime storage producer authority;
- `tests/test_fa_entrypoint.py` actual shell entrypoint composition;
- `tests/test_workspace_readiness_integration.py` clean real readiness and local
  publication pattern;
- `tests/test_session_lifecycle.py` new/attach ordering;
- `tests/test_cli.py` readiness-before-provider root.

Plans/docs:

- parent plan CT3–CT9, S6.5–S9, T16, GAP11, risks, DoD, and artifact ledger;
- benchmark M1–M3 and Q2/Q8 disposition;
- tracked live verification protocol;
- provisional patch bytes;
- `AGENTS.md`, `knowledge/project-overview.md`, ADR digest/reference,
  `plan-authoring`, `tests-writing`, `feature-planning`, and `doc-maintenance`
  skills.

### Source-verified findings

1. `src/fa/workspace_bootstrap.py:_command_environment` copies `os.environ` and
   adds only `GIT_TERMINAL_PROMPT=0` and `UV_LINK_MODE=copy`. A container-level
   `NPM_CONFIG_CACHE` will therefore reach pre-commit/npm without adding an npm
   branch to the readiness engine.
2. `_ensure_locked` invokes exactly
   `<workspace>/.venv/bin/pre-commit install-hooks`, with workspace cwd,
   captured output, closed stdin, and a 900-second internal bound.
3. `_run_process` preserves only the child's return code in the typed
   `_ReadinessError`. `_append_log` records closed `stage`, `argv`, reason,
   return code, elapsed time, and workspace; it intentionally does not persist
   captured child stdout/stderr. The retained pre-commit log is therefore a
   separate evidence source.
4. `Dockerfile.fa` pins `HOME=/home/fa` for runtime uid/gid `1000:1000` and does
   not set `NPM_CONFIG_CACHE` in merged runtime code.
5. Compose makes the container root read-only, sets
   `PRE_COMMIT_HOME=/home/fa/.cache/pre-commit`, and mounts
   `/home/fa/.cache` as private writable executable tmpfs. No merged Compose
   entry sets `NPM_CONFIG_CACHE`.
6. The pre-commit wrapper exports `NO_PROXY=*` only after its readiness prelude.
   Entrypoint readiness and hook-triggered readiness therefore both see the
   pre-existing container proxy environment. The later wrapper export is not an
   explanation for the prewarm failure.
7. New and attached logical sessions call the injected workspace preparer before
   manifest activation/last-used mutation. The preparer returns a typed degraded
   state rather than raising, so fail-open policy is preserved.
8. Entrypoint startup invokes readiness before replacing `/sessions/.active`,
   but publishes after either READY or typed fail-open degradation.
9. The Compose healthcheck runs only `fa --version`. Container health can become
   green while entrypoint prewarming is still running. This proves the timing
   window is structurally possible, not that the observed §7B workspace change
   was conclusively caused by it.
10. The current CI session smoke creates an empty Git source repository. The
    provisional patch adds a hard readiness check against its cloned workspace.
    The production checker run against that fixture shape returns
    `status=degraded_internal`, `reason_code=invalid_workspace`, exit `70`.
    Therefore the provisional patch cannot be approved unchanged.
11. `.github/workflows/advisory.yml` is named `CI`; `container-build` has no
    `continue-on-error`. It is a blocking per-PR job. Jobs below its advisory
    boundary explicitly opt into `continue-on-error: true`.
12. A real CI readiness fixture must contain the current First-Agent checkout,
    a normal `.git` directory, the four required root inputs, and a canonical
    credential-free push URL. It must be owned/readable by container uid 1000.
13. The proposed environment producer belongs in Dockerfile/Compose, not in
    `workspace_bootstrap.py`: npm is an implicit child of a pre-commit language
    environment, and the writable-root topology is container policy.
14. The reported live classifier field `missing_executable=true` was triggered
    by generic “no such file or directory” text. It is not executable evidence.
15. The requested file
    `worklogs/implementation-plans/session-workspace-readiness-live-verification-from-6.md`
    is absent from public `main`; the tracked file is the older protocol. The
    requested path is therefore a **NEW** execution artifact. S0 creates it only
    after the retained inputs are rebound to live identity; if the operator
    supplies an external copy first, S0 compares hashes/content and preserves its
    evidence instead of overwriting it.
16. `fa-update.sh:run_tests` saves and may restore `/sessions/.active` around a
    nested entrypoint invocation (`scripts/fa-update.sh:865-930`). A simple
    “active changed from its pre-update value” oracle can therefore select the
    wrong workspace. Recreated verification must derive the startup workspace
    from PID 1's timestamped `Created session workspace:` log and require final
    `.active` to equal that path.
17. The repository's only currently tracked `*.patch` file is the provisional
    npm artifact added by `e8f7ee5`. A corrected delivery patch cannot safely be
    regenerated in-place while also representing its own application. The final
    transport patch is emitted outside the repository against `e8f7ee5` and
    deletes the stale tracked provisional artifact in the applied tree.
18. Existing invalid-workspace behavior is already covered in
    `tests/test_workspace_bootstrap.py:1160-1210`; S6 needs no duplicate behavior
    test. The container structural test instead pins the real-source CI fixture.

### Evidence supplied but not independently re-run in this workspace

The following are accepted as retained raw evidence inputs, not as inherited
causal conclusions:

- §6 authority and cleanliness outputs are PASS on deployed revision `7ba1361`;
- §7C bootstrap record is `precommit_prewarm_failed`, child rc `3`;
- locked uv check passed;
- the direct pre-commit reproduction returned `3` and preserved workspace Git
  status;
- the retained pre-commit log was reported as `672275` bytes with SHA-256
  `1d9ca6cf756da4d4e77fe37eb154390389636a94ead70f1490e2d6ebf7321065`;
- the log contained repeated npm tarball warnings and ended with an npm
  `ENOENT` mkdir report for `/home/fa/.npm` plus log-directory failure;
- cache capacity was not exhausted;
- mode and mount remediations passed independently.

Every past-tense item above must be re-bound to its actual live artifact or
output in S0–S4 before it can support a cause verdict.

### Gold patterns mirrored

- Parent S6.5 claim ledger: separate present/partial/unsafe/unverified evidence
  and require a binary admission result.
- `tests/test_workspace_readiness_integration.py`: real checkout/readiness root,
  external publication mocked locally, source status preserved.
- `tests/test_container_build_invariants.py`: parse Compose/workflow and pin
  exact producer order/shape without requiring Docker locally.
- `tests/test_hygiene_hooks_self_bootstrap.py`: execute checked-out wrappers and
  test the actual process boundary.
- Parent S9 live protocol: source/image identity, clean status, no provider
  calls, and guarded cleanup.

### Conflicts and invariants

- Managed clones only are inside the readiness guarantee.
- No `--session-id` creates a logical session; explicit `--session-id` attaches.
- Readiness remains `uv sync --locked`, not `--frozen`.
- All pre-commit environments are part of READY.
- Bootstrap remains fail-open for agent, commit, and push. This plan does not
  silently convert runtime admission into fail-closed policy.
- CI is the hard automated gate.
- B2 remains local `file:///repo` fetch plus canonical GitHub SSH push.
- `/repo` and the deployment checkout must remain clean and unchanged.
- Agent authority ends at feature-branch push/PR; human controls merge/deploy.
- No test may print credential-bearing proxy values or raw secret material.
- No source/index/ref/session mutation is allowed during S0–S4. Only bounded,
  self-cleaning writes below the ephemeral cache and host `/tmp` evidence paths
  are allowed.
- §8 and later parent live proof stays blocked until a recreated deployment
  passes §7.

### Current liveness

| Signal/capability | Current liveness | Evidence |
| --- | ---: | --- |
| readiness invocation before provider construction | L3 locally | C1/C2 ordering tests and S6.5 kills |
| live entrypoint readiness result | L2/degraded | §7 bootstrap record; not READY |
| npm effective cache selection | L1 hypothesis | final log path only; `npm config` not yet run |
| cache-path causal claim | L0 | no controlled live A/B |
| tarball/network integrity | L0 | warnings exist; chronology/cause unclassified |
| errno explanation | L0 | npm says ENOENT; direct shell/Node comparison absent |
| proxy discrepancy | L1 source model | wrapper ordering known; live values not captured safely |
| startup publication race occurrence | L1 hypothesis | code permits it; actual timeline absent |
| hard container readiness CI | L0 | current smoke is existence-only |
| provisional patch | L1 | artifact exists; causal gate and valid CI fixture absent |
| feature production readiness | L0 | parent §7 degraded; later proof blocked |

### Adversarial v2 review record

Confirmed plan defects corrected before READY:

| Review ID | v1 defect | Source evidence | v2 correction |
| --- | --- | --- | --- |
| RV1 | exact A rerun could overwrite the retained pre-commit log | readiness telemetry does not retain child stderr; pre-commit owns its separate error log | S0 copies and hashes the retained log on the host before any npm/pre-commit command |
| RV2 | redundant full control A added shared-store mutation | user requires the smallest bounded proof | CT5 uses bound historical A when available; RV15 permits exactly one replacement only after complete no-match search |
| RV3 | `.active != old` could select a restored/non-PID1 workspace | `fa-update.sh:865-930` saves/restores `.active` around nested entrypoint work | CT9/S7 derive startup workspace from PID 1 logs and require final `.active` equality |
| RV4 | CI fixture recipe could pre-create clone target and kept stale assertions | workflow currently `mkdir`/`git init`/`remote add`; test pins that exact shape | S6 supplies a replacement block and updates the structural oracle |
| RV5 | npm-directory existence was a brittle CI oracle | READY already consumes npm through pre-commit; deploy probes own path creation | CT7 requires exact env + READY, not npm cache directory persistence |
| RV6 | patch output was self-referential/stale-base ambiguous | current main tracks the provisional patch at `e8f7ee5` | S6 emits `/home/user/npm-cache-readiness-closure-on-e8f7ee5.patch` and deletes the tracked provisional in the candidate |
| RV7 | causal result was modeled as blocking Q2 | cause can only be learned during execution | replaced by decision gate DG1; no execution result blocks plan READY |
| RV8 | child S8/S9 collided with blocked parent §§8–12 | parent status remains blocked at §7 | closeout collapsed into child S7.1–S7.4 |
| RV9 | FIX PR omitted protected test-edit declaration | `pr-creation` skill requires `TEST-EDITS` for existing tests | S6/S7 require skill load and exact declarations |
| RV10 | Node hook owner was asserted from local YAML | local YAML lists remote repo, not its manifest language/runtime path | CT2 binds owner/path from retained log |
| RV11 | duplicate invalid-workspace test was planned | existing tests at `test_workspace_bootstrap.py:1160-1210` already pin it | reuse existing behavior; test only CI fixture structure |
| RV12 | network fallback was a list, not an executable branch | no argv/order/decision rule in v1 | S5.N defines registry/package/proxy probes and outcomes |
| RV13 | live probes lacked a copy-paste command authority | prose required executor interpretation | §5.1 fixed atomic command sheet is the only operator command authority |
| RV14 | external runtime patch was emitted before plan/evidence edits | operator PR would omit reviewed authority and causal record | S6 final candidate includes reviewed plan, llms row, pre-merge evidence sheet, parent link, runtime/tests, and provisional-patch deletion before emission |
| RV15 | v2 had no executable path when the historical retained log was absent | S0 exact-size searches completed across host/container transient, home, cache, and session roots with no candidate | S2 captures one fresh bounded replacement A, preserves host/internal logs, and requires reproduction before S3/S4 |
| RV16 | v3 exposed each atomic command as a separate paste operation | operator selected one copy/pasteable block per stage | chat groups commands by stage while preserving per-command timeout, labels, expected-failure handling, and no-heredoc rule |
| RV17 | first replacement-A block did not explicitly disable inherited `errexit` | A output exists and is complete enough to preserve, but the wrapper exited before recording exact outer rc | no rerun; recover chronology from A logs, and every later stage block begins `set +e` before expected-nonzero probes |
| RV18 | S3.1 mixed evidence collection with assertions about unknown npm behavior | operator received only wrapper rc 1; exact failing label/output is unavailable | inspect side effects without npm, then use collection-only subprobes that always preserve rc/output before agent classification |
| RV19 | pasted blocks used top-level `exit`, closing the operator's interactive Bash window | operator observed the window close and lost the block status surface | every future block runs inside `( ... )`; parent shell captures `$?` and prints `<stage>_BLOCK_RC`, with no top-level `exit` |
| RV20 | failed S3.1 output was unavailable, so execution depth was unknown | recovery found no verify logs/cache dirs/children and exact clean source/workspace hashes | only idempotent config/version/Node observations may repeat; collector has no npm-value assertions and cache verify remains blocked |
| RV21 | v9 assumed the failed Node environment remained probeable | exact A path now lacks node/npm and every exec returns 127, while A log proves both ran before failure | classify pre-commit cleanup separately; do not substitute system tools; run exact B and inspect retained env only after B success |
| RV22 | cache cause remained a hypothesis despite strong terminal-path evidence | exact B changed only `NPM_CONFIG_CACHE`, returned 0, retained Node/npm, and eliminated all 2632 tarball warnings/18 npm errors | set `CAUSE_STATUS=CACHE_PRIMARY_CONFIRMED`; post-B config/errno probes are corroboration, not a competing admission gate |
| RV23 | READY plan retained known-broken historical command blocks | §5.1 still referenced deleted failed-env binaries, top-level script variants, and pre-B micro-probes | replace the command monolith with a delivery contract, executed-state ledger, and exact next-probe contract |
| RV24 | post-B cache verify remained mandatory after exact full B | B already exercised package downloads, cache writes, extraction, and all eager environments | delete cache verify P/T/DoD requirements; retain only config and direct Node errno corroboration |
| RV25 | current status fields still said cause unproven | evidence §10 proves controlled B rc 0 and zero warnings/errors | reconcile plan/evidence current state to `CACHE_PRIMARY_CONFIRMED` and `PATCH_MECHANISM_APPROVED` |
| RV26 | S5/DG1 was still modeled as future | DG1 is already closed by exact A/B | mark S4/DG1 executed and gate S6 only on the bounded S4.1a evidence closure |
| RV27 | S4.1a directly executed npm's symlink and relied on PATH | live rc 127 says `/usr/bin/env: node: No such file`; A log proves pre-commit invokes explicit Node then npm script | retain Node errno result; rerun config only as `NODE_BIN NPM_BIN ...`, matching the production calling convention |
| RV28 | CI real-source fixture used a transport clone | current promisor clone failed upload-pack with missing object/early EOF; the tested object-copying local clone succeeded at exact HEAD | use the clone command pinned in workflow/tests, then reset canonical origin and make source world-readable without changing ownership |
| RV29 | CI fixture inherited/expanded privileged ownership repair | hosted runner is fresh; source is read-only; session/state are disposable | Q4 selects no-sudo CI: runner-owned read-only source plus uid-1000 tmpfs session/state mounts with automatic cleanup |

Items genuinely fine and retained:

- container environment is the correct producer layer;
- no readiness-engine npm branch is added;
- existing tmpfs capacity/mount topology remains unchanged;
- runtime fail-open and CI hard-gate policy remains unchanged;
- healthcheck remains service liveness, not workspace readiness;
- parent commit/push/PR proof remains blocked after this child closes §7.

### Execution decision gates (not open questions)

- **DG1 cause — CLOSED:** `CACHE_PRIMARY_CONFIRMED` by exact B, evidence §10.
- **DG2 patch:** S6 is admitted after the bounded S4.1a config/Node-errno record;
  this is evidence closure, not a competing cause gate.
- **DG3 live:** parent §7 passes only when S7.3 satisfies CT9–CT10.

Historical startup-race occurrence may remain `UNVERIFIED_MISSING_TIME`; DG3 is
still deterministic because it binds the recreated PID 1 workspace directly.

---

## 0. Executive intent

**IDEA.** Prove why live managed-workspace readiness fails at pre-commit
prewarming, change only the producer proven causal, add a blocking
production-shaped container gate, and require a recreated deployment to pass
§7 before any commit/push/PR proof resumes.

**PROJECT MEANING.** In the managed-session lifecycle, this is the final closure
between deterministic readiness code and the deployed read-only-container
filesystem. It belongs at container environment/CI/deploy boundaries unless
live evidence demonstrates a different npm/pre-commit defect.

### Goals

- **G1 — evidence authority:** Bind every diagnosis claim to the exact deployed
  revision, container, workspace, retained log, environment, mount, and
  pre/post-cleanliness output.
- **G2 — causal classification:** Prove or falsify that npm's effective default
  cache `/home/fa/.npm` is the primary cause of the rc `3` prewarm failure.
- **G3 — competing causes:** Independently classify tarball integrity, proxy
  environment, executable availability, and errno semantics.
- **G4 — patch disposition:** Approve, revise, or discard the provisional patch
  using a binary decision rule; never merge it from plausibility.
- **G5 — CI closure:** Make blocking container CI exercise a real First-Agent
  managed workspace and hard-fail unless `check_workspace_ready` returns READY.
- **G6 — live rollout closure:** After human merge and operator deployment,
  verify a newly published startup workspace reaches READY on the recreated
  container while deployment/source authorities remain unchanged.
- **G7 — trajectory preservation:** Keep parent §§8–12 blocked until §7 passes,
  preserve fail-open runtime policy, and leave no false shipped claim.

### Intent

Whenever `fa run "some task"` creates or attaches a managed workspace, the
harness must complete the locked environment, four hook seats, and eager
pre-commit environment preparation before provider construction. The read-only
deployment checkout must remain unchanged. Container CI must fail if the
production topology cannot support that transaction.

### Mechanism sketch

```text
exact live identity
  → bounded environment/mount/log/npm probes
  → same-workspace A/B changing only NPM_CONFIG_CACHE
  → closed causal verdict
  → proven branch only: minimal container-env repair
  → real-source blocking container readiness check
  → human PR/merge + operator recreate
  → wait for new .active publication
  → §7 READY/source-preservation proof
```

### Proof sketch

The live A control must reproduce the exact npm/pre-commit failure with the
current environment. The B command uses the same container, workspace, npm,
pre-commit store, proxies, registry, and argv, changing only
`NPM_CONFIG_CACHE`. A cache-cause verdict requires B to return zero and the log
chronology/errno probes to agree with the mechanism. The implementation proof is
the blocking `container-build` job: removing the Dockerfile npm environment
producer must make the real managed readiness assertion fail.

Size: **M** — evidence-heavy, small runtime change, non-trivial CI/rollout proof.

---

## 1. Non-goals and minimal-mechanism check

### Non-goals

- No merge, deployment, or section advancement during causal diagnosis.
- No persistent npm/pre-commit/uv cache and no new bind mount.
- No increase to existing tmpfs capacities without a new measured overflow.
- No pre-commit hook removal, weakening, revision change, or package pin change.
- No `--no-verify`, hook-skip variable, frozen sync, or quality-gate bypass.
- No change to runtime fail-open policy.
- No change to `fa --version` service-health semantics unless the later plan
  review proves that a health-policy decision is required.
- No npm-specific branch in the stdlib readiness engine if environment policy
  suffices.
- No generic cache abstraction, package-manager registry, retry framework, or
  new dependency.
- No raw proxy value, secret URL userinfo, provider key, deploy-key content, or
  full environment dump in evidence.
- No editing/removing the failed managed workspace during diagnosis.
- No continuation to managed commit/push/disposable PR/cleanup until the
  recreated startup workspace passes §7.

### Minimal-mechanism decisions

1. **Environment variable, not code adapter.** `_command_environment` already
   propagates container policy to all readiness children. If the cache cause is
   proven, one npm-native environment variable closes the degree of freedom.
2. **Existing writable tmpfs, not new storage.** The S7 benchmark measured enough
   capacity under `/home/fa/.cache`; adding persistence or another mount has no
   evidence.
3. **Existing CI job, not another workflow.** `container-build` is already a
   blocking production-image root. Correct its source fixture and strengthen its
   oracle rather than adding a second Docker job.
4. **Existing tests, not a new test framework/file.** Dockerfile/Compose/workflow
   and deploy producers already have structural authority modules. Extend them
   and use the real CI job as C2.
5. **Verifier sequencing, not healthcheck expansion.** The startup code already
   replaces `.active` after readiness returns. The live verifier must wait for a
   new publication and then inspect its readiness. Whether service health itself
   should include readiness is a separate policy question and remains out of
   scope.
6. **No new diagnostic classifier.** First-error chronology and A/B output are
   stronger than adding another keyword classifier for one incident.

New-component gate:

```text
new service/dependency/cache topology = rejected
capability lost without a new component = none
existing native mechanism = npm NPM_CONFIG_CACHE + current tmpfs + current CI job
LLM call needed = no
value proof = exact live A/B + container C2 producer kill
```

---

## 2. Current state → target state

### 2.1 AS-IS

| Dimension | Verified current behavior |
| --- | --- |
| runtime child environment | copied from container; no npm override in merged code |
| runtime home | `HOME=/home/fa` |
| writable roots | separate `.cache`, `.local`, `.fa`, `/tmp`, and uv tmpfs seats |
| prewarm producer | `.venv/bin/pre-commit install-hooks` |
| failure state | typed `degraded_environment/precommit_prewarm_failed`, rc `3` |
| marker/sentinel | absent after degradation by design |
| active publication | after readiness returns, including fail-open degradation |
| service health | `fa --version`, independent of readiness |
| proxy wrapper | `NO_PROXY=*` exported only after readiness prelude |
| retained failure detail | pre-commit log reported; exact artifact must be re-bound |
| CI source fixture | empty Git repository; cannot satisfy readiness validation |
| CI oracle | workspace/mount existence and CLI only; no hard readiness result |
| deploy probes | `.cache`/`.local` writable+exec only; no npm child path assertion |
| provisional patch | plausible env/probe change plus invalid hard-check fixture |
| parent state | §6 PASS, §7 DEGRADED, later sections pending |

### 2.2 GAP ledger

| Gap | Current → target | Owner | Verification |
| --- | --- | --- | --- |
| GAP1 | final npm path is suggestive → effective cache selected by failed npm is measured | S2–S3 | T2–T4 |
| GAP2 | tarball warnings/final ENOENT unordered → first command/warning/error/exception chronology recorded | S2 | T2 |
| GAP3 | generic missing-executable classifier → exact npm/node path and runnable versions | S3 | T3 |
| GAP4 | read-only topology inferred → live mount plus shell/Node errno semantics | S1/S3 | T1/T3 |
| GAP5 | proxy concern speculative → safe live fingerprints and unchanged A/B environment | S1/S4 | T1/T5 |
| GAP6 | cache fix plausible → same-operation A/B changes only npm cache | S4–S5 | T5–T6 |
| GAP7 | patch hard-check fixture invalid → real current First-Agent clone and blocking READY oracle | S6 | T7–T10 |
| GAP8 | structural env tests only → positive Docker C2 plus one recorded producer-removal kill | S6 | T9/T10 |
| GAP9 | startup race structurally possible → current occurrence classified and recreated verifier binds PID 1 startup workspace | S2/S7 | T2/T12 |
| GAP10 | post-merge evidence sheet absent from public tree → NEW named sheet contains rebound evidence and status | S0/S5/S7 | T0/T11 |
| GAP11 | live deployment degraded → human-merged recreated deployment passes complete §7 | S7 | T12–T14 |
| GAP12 | parent could advance from patch/local green → explicit section block remains until GAP11 closes | S7 | T11/T15 |

Parent mapping: GAP1–GAP12 above are the child decomposition of parent `GAP11`
and S9/T16's live-readiness portion. They do not renumber or reopen parent
GAP1–GAP10.

### 2.3 TO-BE

- Every live probe carries container/image/revision/workspace/log identity.
- The first actual npm error is known, not inferred from the last lines.
- npm/node executable presence and npm's effective cache are directly measured.
- Shell and Node mkdir results explain or explicitly block the errno claim.
- Proxy state is fingerprinted safely and held constant through A/B.
- One binary causal outcome is recorded:
  `CACHE_PRIMARY`, `NETWORK_OR_CONTENT_PRIMARY`, `EXECUTABLE_ENVIRONMENT`,
  `TRANSIENT_NOT_REPRODUCED`, or `INCONCLUSIVE_STOP`.
- Only `CACHE_PRIMARY` admits the npm environment patch branch.
- The candidate CI fixture is a normal clone of `$GITHUB_WORKSPACE`, not an empty
  repository; its disposable origin is reset to the canonical SSH URL and its
  ownership is normalized to uid/gid 1000.
- Blocking container CI checks the actual startup workspace with
  `python3 -m fa.workspace_bootstrap check --workspace "$PWD"` and fails on any
  non-READY result. It asserts the exact npm environment but does not require an
  npm cache directory to persist after successful preparation.
- The candidate is tested in a disposable materialization; no direct deployment
  edit occurs. The external final patch is based on current main `e8f7ee5` and
  removes the stale tracked provisional patch artifact.
- Human merge and operator recreation produce a new image/revision/container.
- The verifier derives the startup workspace from PID 1's timestamped entrypoint
  log and requires final `.active` to equal it before testing §7.
- §7 ends `PASS` only with marker, sentinel, hooks, locked uv, clean Git, and
  source/deployment preservation.

### 2.4 State transitions

```text
DIAGNOSIS
UNBOUND_EVIDENCE
  → IDENTITY_BOUND
  → HISTORICAL_A_BOUND | HISTORICAL_A_UNAVAILABLE_AFTER_SEARCH
  → REPLACEMENT_A_CAPTURED (only for unavailable branch)
  → LOG_CHRONOLOGY_BOUND
  → MECHANISM_PROBED
  → B_EXECUTED
  → DG1=<closed CAUSE_* state or INCONCLUSIVE_STOP>

PATCH
PROVISIONAL_UNAPPROVED
  → DG1=CACHE_PRIMARY_CONFIRMED (live complete)
  → S4.1A_EVIDENCE_RECORDED
  → E8_CANDIDATE_REVISED
  → TARGETED_GREEN
  → C2_CONTAINER_GREEN + PRODUCER_KILL_RECORDED
  → EXTERNAL_E8_PATCH_EMITTED
  → HUMAN_REVIEWED/MERGED

LIVE
SECTION_7_DEGRADED
  → OPERATOR_RECREATED
  → PID1_STARTUP_WORKSPACE_BOUND
  → ACTIVE_EQUALS_PID1_WORKSPACE
  → STARTUP_WORKSPACE_READY
  → DG3=SECTION_7_PASS
```

No transition may skip its predecessor based on a narrative assertion.

---

## 3. Contracts

### CT1 — Safe live evidence identity

Type: data/security contract.

Required fields:

```text
public_main_head
expected_runtime_head
deployment_head
container_id
container_started_at
image_id
image_revision
active_workspace
failed_workspace
historical_retained_log_status=<BOUND | UNAVAILABLE_AFTER_SEARCH>
replacement_a_host_log=/tmp/fa-precommit-a-replacement.log
replacement_a_internal_log=/tmp/fa-precommit-a-internal.log|<absent>
replacement_a_bytes
replacement_a_sha256
source_status_hash_before/after
workspace_status_hash_before/after
```

Authority: Git/Docker/stat/sha256 outputs from the target host. The verification
sheet is the consumer, not the source of these values.

Security: proxy values are represented as `unset`, exact `*`, or a SHA-256
prefix. No secret-bearing value is printed.

Failure: any revision/workspace mismatch returns `INCONCLUSIVE_STOP`. A missing
historical log is admissible only after S0 records complete bounded search with
no exact-size/SHA candidate; S2 then owns exactly one replacement A.

Kill-check: changing runtime HEAD or replacement-A workspace identity makes
T0/T2 stop.

### CT2 — Retained log chronology

Type: evidence contract.

Producer: either (A) an exact historical retained-log copy bound in S0, or (B)
when S0 proves it unavailable after complete bounded metadata search, one fresh
replacement control A from the unchanged live container/workspace. Replacement
A writes command output to `/tmp/fa-precommit-a-replacement.log`; if pre-commit
creates its internal error log, S2 copies that separately to
`/tmp/fa-precommit-a-internal.log`. Neither file is overwritten by B.

Consumer: S2 cause classifier.

Required bounded windows:

- exact child command, cwd, and Node environment path;
- first `npm warn tarball` line plus context;
- first actual `npm error` line plus context;
- final exception/traceback plus context;
- npm/node/cache/log paths appearing in the failure.

The first error, not the final line, owns primary-failure classification.

Failure: replacement A timeout/success, changed Git state, surviving child, or
no detailed command/error context yields `TRANSIENT_NOT_REPRODUCED` or
`INCONCLUSIVE_STOP` and blocks B.

### CT3 — npm executable and effective configuration

Type: process contract.

Input: exact npm/Node paths from CT2. A proves they executed, but pre-commit may
remove the failed `node_env-default` during cleanup. Absence after failure is
recorded as `FAILED_NODE_ENV_CLEANED`, not `EXECUTABLE_ENVIRONMENT` cause, and no
system/different npm is substituted.

Exact B succeeded and retained the successful environment. S4.1a now records
`node --version`, `npm --version`, default/override `npm config get cache`,
npm-specific proxy/registry config, and direct Node mkdir errno. No cache verify
is needed: full B already exercised real package acquisition, extraction, cache
writes, and all eager environments.

Output:

```text
npm_path
node_path
npm_runnable_rc
node_version
npm_version
cache_default
cache_override
```

Failure: executable absence **during** A would be `EXECUTABLE_ENVIRONMENT`; CT2
proves the opposite. Post-failure absence is cleanup and defers CT3 until B.

Kill-check: the A command tuple plus npm child rc `254` must prevent
post-failure cleanup from being relabeled as the original cause.

### CT4 — Filesystem and errno semantics

Type: security/filesystem contract.

Producers:

- actual shell mkdir of exactly `/home/fa/.npm` when absent;
- actual write under a unique `/home/fa/.cache/.fa-npm-probe-*` path;
- Node `fs.mkdirSync('/home/fa/.npm', {recursive:true})` using CT3's Node.

Consumer: cause classifier.

Outputs include return code and structured Node `code`, `errno`, `syscall`, and
`path`. An unexpected successful root write is cleaned only if this probe created
the path and is a topology blocker.

Failure: npm ENOENT versus shell/Node EROFS must be explained by CT2 chronology
or remain `INCONCLUSIVE_STOP`.

### CT5 — Same-environment causal A/B

Type: reliability/process contract.

Control A selection is closed:

- use an exact historical retained reproduction only when S0 binds it; or
- after S0 proves that artifact unavailable, run exactly one fresh bounded A
  after S1 topology capture and before S2 chronology.

Replacement A uses unchanged live env with `NPM_CONFIG_CACHE` unset, exact failed
workspace/cwd/argv, separate host/internal logs, and pre/post Git hashes. A must
return nonzero with the same `precommit_prewarm` failure class and provide enough
detail for CT2; otherwise B is forbidden.

B holds constant:

- container and uid/gid;
- failed workspace and cwd;
- `.venv/bin/pre-commit` bytes;
- pre-commit store and failed Node environment;
- proxy fingerprints;
- registry/config;
- command argv;
- mounts and capacity;
- workspace/source HEAD and status.

Only B adds:

```text
NPM_CONFIG_CACHE=/home/fa/.cache/npm
```

B has an in-container process timeout and a slightly larger host
`timeout --foreground --kill-after` bound. Output goes to host
`/tmp/fa-precommit-b.log` and is inspected only through
size/hash/count/bounded windows. The sequential-store limitation is explicit,
but exact B installed all missing environments, created the fresh candidate npm
cache, eliminated every npm/tarball warning, and preserved Git state. Together
with CT2 chronology and CT4 filesystem proof, this closes `CACHE_PRIMARY`.

Failure: timeout, identity/environment drift, changed workspace status, or a
different first error makes the result inconclusive.

### CT6 — npm runtime cache producer

Type: configuration contract, conditional on `CACHE_PRIMARY`.

Producer A: `Dockerfile.fa` runtime environment after `HOME`:

```text
ENV NPM_CONFIG_CACHE=/home/fa/.cache/npm
```

Producer B: Compose first-agent environment with the same exact value.

Consumers:

- readiness child environment via `_command_environment`;
- npm in pre-commit Node environment;
- deployment storage probes;
- blocking container CI.

Invariant: the path is within existing `/home/fa/.cache` tmpfs; no capacity or
mount change.

Failure: missing/mismatched/unwritable path blocks deploy checks or container
readiness.

Primary kill-check: remove Dockerfile producer from the raw `docker run` CI
candidate; T9 must fail the hard READY assertion.

### CT7 — Blocking real-source container readiness

Type: C2 CI contract.

Producer: `.github/workflows/advisory.yml:container-build` requires an absent
source destination, runs the tested object-copying local clone command, resets
canonical SSH origin, and grants read/traverse bits without changing ownership.
Writable `/sessions` and `/home/fa/.fa` are created as private uid/gid-1000 tmpfs
mounts; container removal cleans them automatically. No CI workflow uses sudo.

Runtime root: production image entrypoint under read-only root with the same
cache/local execution policy. CI session/state are intentionally ephemeral;
operator §7 remains authority for the production bind filesystem.

Consumer: hard check in the command override:

```text
python3 -m fa.workspace_bootstrap check --workspace "$PWD"
```

Oracle:

- source contains readiness inputs;
- `/sessions/.active` equals `PWD`;
- npm environment is exact;
- checker exits zero and emits READY;
- `fa --version` remains available.

CI deliberately does not assert that npm leaves a cache directory behind; READY
is the consumer proof, while CT8 owns writable-path creation/validation.

Failure: any nonzero entrypoint/check command fails blocking CI. No
`continue-on-error`, `|| true`, or output-only assertion is permitted.

Kill-checks:

- restore empty source fixture → checker returns `invalid_workspace`;
- remove Dockerfile npm producer → prewarm/check fails;
- delete hard check → structural workflow test fails.

### CT8 — Runtime storage deployment probe

Type: operator/deploy contract, conditional on `CACHE_PRIMARY`.

Producers:

- `scripts/fa-update.sh:verify_runtime_storage`;
- equivalent blocks in `fa-clean-rebuild.sh` and `fa-post-setup.sh`.

They require exact `NPM_CONFIG_CACHE`, create that directory, and require it to
be a directory writable/traversable by runtime uid 1000 before reporting the
runtime storage contract green. Existing executable `.cache`/`.local` probes
remain unchanged.

Consumer: operator update/rebuild result.

Failure: return nonzero with the existing “workspace readiness cannot complete”
surface; do not silently warn.

Kill-check: change expected cache path or remove mkdir/writability test; T8
fails for all three producers.

### CT9 — New-active publication verifier

Type: live protocol contract.

Before recreation record old container ID, old `.active`, and its mtime. After
operator update:

1. require a new container ID/start time;
2. read only PID 1 container logs since that start and extract exactly one
   timestamped `Created session workspace: /sessions/<sid>` line;
3. under an external bound, require `/sessions/.active` to equal that exact PID 1
   startup workspace;
4. require `.active` mtime and the workspace bootstrap terminal record to be no
   earlier than container start; and
5. reject any final value restored by `fa-update.sh` that does not equal the PID
   1 workspace.

Then inspect only the bound PID 1 workspace. Health and “different from old” are
never readiness/publication oracles.

Failure: missing/ambiguous PID 1 log, active mismatch, stale mtime, timeout, or
publication before terminal bootstrap record sets §7 BLOCK. It does not trigger
healthcheck redesign in this slice.

### CT10 — §7 READY and authority preservation

Type: live acceptance contract.

The new startup workspace must satisfy:

- canonical path and managed branch;
- local file fetch and canonical SSH push;
- expected local Git identity;
- `.venv` and executable project Python;
- four executable/current hook seats;
- private marker mode `0600`, `state=ready`;
- matching pre-commit sentinel;
- locked uv check;
- clean workspace;
- marker mtime not later than `.active` mtime;
- source and deployment HEAD/status hashes unchanged;
- zero provider/model calls.

Failure: `SECTION_7=DEGRADED` and all later parent sections remain blocked.

### CT11 — Evidence/documentation authority

Type: documentation contract.

NEW `worklogs/implementation-plans/session-workspace-readiness-live-verification-from-6.md` records:

- confirmed facts versus hypotheses;
- every S0–S5 safe output and causal verdict;
- provisional patch defect and final disposition;
- test/gate/kill outputs;
- merge/deploy/image identity;
- recreated §7 result;
- explicit later-section block or release.

No status line may say confirmed/READY before its binary oracle passes.

---

## 4. Path and environment matrix

### 4.1 Runtime paths

| Path | Trigger | Current site | Target behavior | Owner | Verification |
| --- | --- | --- | --- | --- | --- |
| P1 | retained log matches expected identity | pre-commit log | bounded chronology accepted | S0/S2 | T0/T2 |
| P2 | retained log mismatch/missing | evidence boundary | stop; no substitute | S0 | T0 |
| P3 | npm binary remains runnable | failed Node env | versions/config captured | S3 | T3 |
| P4 | npm binary absent/non-runnable | failed Node env | separate executable cause | S3/S5 | T3/T6 |
| P5 | `/home/fa/.npm` absent on RO root | live container | shell+Node errno recorded | S1/S3 | T1/T3 |
| P6 | `/home/fa/.cache` writable | live container | transient write succeeds/cleans | S1 | T1 |
| P7 | historical A bound or complete search proves unavailable | evidence boundary | select historical A or one replacement A | S0/S2 | T0/T2 |
| P8 | replacement A succeeds/times out/differs/changes Git | failed workspace | transient/inconclusive stop; B forbidden | S2/S5 | T2/T6 |
| P9 | B exact prewarm succeeds | cache override only | cache cause admitted | S4/S5 | T5/T6 |
| P10 | B retains tarball/integrity failure | override only | npm patch held; network branch | S4/S5 | T5/T6 |
| P11 | B retains exact Node/npm environment | post-B config/Node probe | default/override cache paths and errno recorded | S4.1a | T4 |
| P12 | current §7B/§7C timeline available | old evidence | race confirmed or remains hypothesis | S2/S5 | T2/T6 |
| P13 | CI with real source | image entrypoint | hard READY | S6 | T9 |
| P14 | CI with empty source mutant | image/checker | `invalid_workspace`, job fails | S6 | T10 |
| P15 | recreated deployment PID 1 logs one startup workspace | entrypoint | final `.active` equals that exact workspace | S7.3 | T12 |
| P16 | recreated workspace READY | §7 verifier | section passes | S7.3 | T13 |
| P17 | recreated workspace degraded | §7 verifier | preserve and stop | S7.3 | T13 |

### 4.2 Environment matrix

| Matrix | Environment | Proves | Owner | Verification |
| --- | --- | --- | --- | --- |
| M1 | live default; npm cache unset | actual failed baseline | S1–S4 | T1–T5 |
| M2 | same live env + npm cache override only | causal B | S4 | T5 |
| M3 | proxy fingerprints unchanged A→B | proxy not confounding A/B | S1/S4 | T1/T5 |
| M4 | raw Docker image, no Compose env injection | Dockerfile producer owns CI runtime | S6 | T7/T9/T10 |
| M5 | rendered production Compose | explicit production env/path/mount agreement | S6/S7.3 | T7/T12 |
| M6 | update/clean-rebuild/post-setup | all bring-up producers reject bad path | S6 | T8 |
| M7 | recreated cold HOME/pre-commit tmpfs | production readiness from empty cache | S7.3 | T12/T13 |
| M8 | warm read-only checker | marker/sentinel/locked state current | S7.3 | T13 |

Every matrix row has an owner and named verification. No provider-family matrix
applies; no model/provider call occurs.

---

## 5. Step-by-step plan

### 5.1 Command delivery contract and executed-state ledger

Known-broken or superseded command blocks are not retained as executable
authority. Exact safe outputs live in the post-§6 evidence sheet; the next
operator block is generated from the contract below and validated before use.

Every operator block:

- runs inside `( ... )`, never the interactive parent shell;
- begins with `set +e`; no top-level `exit` is permitted;
- prints a final `<stage>_BLOCK_RC` and `PARENT_BASH_STILL_OPEN=yes`;
- contains no heredoc;
- gives every potentially blocking operation an external timeout;
- collects unknown external-tool outcomes without inline policy assertions;
- may fail closed only on already-established identity, containment, or
  source-preservation invariants;
- is syntax-checked and mock-executed in both success and all-observations-fail
  modes before presentation.

Executed live state:

| Step | Result | Authority |
| --- | --- | --- |
| S0 | PASS identity; historical retained log unavailable after complete bounded search | evidence §§1–2 |
| S1 | PASS root/cache topology, EROFS/writable sibling, capacity, clean state | evidence §3 |
| S2 | PASS replacement A and full npm/pre-commit chronology | evidence §§6–7 |
| S3 | PASS lifecycle classification: failed Node env cleaned after npm child rc 254 | evidence §§8–9 |
| S4 | PASS exact B rc 0; only cache env changed; zero npm/tarball errors | evidence §10 |
| S4.1a | PASS: exact Node+script invocation; default/override cache, no proxy, canonical registry, strict SSL, Node `ENOENT/-2`, clean preservation | evidence §§11–12 |
| DG1 | `CACHE_PRIMARY_CONFIRMED` | evidence §10.5 |
| DG2 | `S6_ADMISSION=ALLOW` | evidence §12 |

Next slice: **S6 implementation**.

Required inputs:

```text
node=/home/fa/.cache/pre-commit/repokdu__ovx/node_env-default/bin/node
npm=/home/fa/.cache/pre-commit/repokdu__ovx/node_env-default/bin/npm
cwd=/home/fa/.cache/pre-commit/repokdu__ovx
candidate_cache=/home/fa/.cache/npm
```

The corrected collector invokes npm exactly as pre-commit did:

```text
NODE_BIN NPM_BIN <npm args>
```

It records npm version, default/override cache, `proxy`, `https-proxy`,
`noproxy`, `registry`, `strict-ssl`, final paths, and source/workspace hashes.
Direct Node mkdir is already complete: Node v26 returned `ENOENT/-2`, matching
npm and explaining the shell/coreutils `EROFS` wording difference.

It must not rerun Node mkdir, npm install, pre-commit, `npm cache verify`,
readiness `ensure`, or delete the successful candidate cache. After this config
record, execution moves directly to S6; S5/DG1 is closed.

### Step S0 — bind authorities and create the evidence sheet

Traces-to: G1, G7; GAP10, GAP12; CT1, CT11; P1–P2.

Depends-on: none. Parallelizable-with: none.

Target liveness: evidence authority L1→L2.

Edit during execution:

- NEW
  `worklogs/implementation-plans/session-workspace-readiness-live-verification-from-6.md`;
- no runtime/source edit.

If the operator supplies an external file at that path before S0, compare it to
the NEW candidate and preserve all non-conflicting raw evidence; never overwrite
it silently.

Do:

1. Run §5.1 S0 commands exactly.
2. In the operator development checkout, record `git rev-parse HEAD`,
   `origin/main`, and porcelain status. Require current public main or a named
   descendant; do not reset automatically.
3. Record deployment/source/failed-workspace identity and status hashes.
4. Copy the retained pre-commit log to host `/tmp` before any npm/pre-commit
   command; require exact expected size/SHA.
5. Create the NEW sheet with a closed-schema header containing CT1 fields and
   mark every supplied claim `bound`, `mismatch`, or `unavailable`.
6. If identity/log mismatches, write only the mismatch record and stop.

Do-not:

- do not repair, recreate, clean, stash, reset, or run pre-commit;
- do not choose a different log because it is newer;
- do not reconstruct raw log text from the prompt when the artifact is missing.

Exit criteria:

- [ ] NEW sheet exists or an external same-path sheet was safely reconciled;
- [ ] CT1 identity fields are present;
- [ ] historical log is either exact-bound or classified unavailable after all
  bounded metadata searches complete with no candidate;
- [ ] failed workspace matches or the plan stops at P2;
- [ ] source/deployment/workspace status baselines are recorded.

Kill-check: a partial/permission-denied search cannot admit replacement A.

### Step S1 — capture live environment, mounts, and write boundaries

Traces-to: G1–G3; GAP4–G5; CT1, CT4; P5–P6; M1, M3.

Depends-on: S0. Parallelizable-with: none.

Target liveness: topology evidence L1→L3.

Edit: none. Operator runs short independent probes.

Do, each with a five-second external timeout:

1. Print uid/gid, `HOME`, `PRE_COMMIT_HOME`, and
   `${NPM_CONFIG_CACHE-<unset>}`.
2. Print each proxy variable as `unset`, exact `*`, or `sha256:<16 hex>`.
3. Inspect `ReadonlyRootfs` and rendered tmpfs from `docker inspect`.
4. Inspect effective mount target/type/options for `/home/fa` and
   `/home/fa/.cache`.
5. If `/home/fa/.npm` is absent, attempt exactly one mkdir, print stderr/rc, and
   remove it only on unexpected success.
6. Create/write/remove one unique probe below `/home/fa/.cache` and require rc 0.
7. Record available bytes for the cache filesystem; do not run a size walk.
8. Require `FA_AUTO_RUN` unset/false before claiming zero provider/model calls;
   otherwise stop and classify the live evidence boundary before diagnosis.

Do-not:

- no source/session paths;
- no raw `printenv` or proxy values;
- no recursive filesystem scan.

Exit criteria:

- [ ] M1/M3 environment fingerprints and non-truthy `FA_AUTO_RUN` recorded;
- [ ] root and cache effective mount options recorded;
- [ ] exact `/home/fa/.npm` mkdir result recorded;
- [ ] cache write succeeds and self-cleans;
- [ ] no source/workspace status hash changes.

Kill-check: point the cache probe at `/home/fa`; T1 must report nonzero rather
than treating mode bits as write proof.

### Step S2 — capture replacement A when required, then inspect chronology

Traces-to: G1–G3; GAP2, GAP5–G6, GAP9; CT2, CT5, CT9; P1–P2,
P7–P8, P12.

Depends-on: S1. Parallelizable-with: none.

Target liveness: replacement control/chronology L0→L2/L3 or explicit stop.

Edit: none.

Do:

1. If S0 bound historical A, re-stat/hash it and set `A_DETAIL_COPY` to that
   immutable host copy. If S0 classified it unavailable, run §5.1 replacement-A
   commands exactly once.
2. For replacement A require: unchanged container/workspace/env, candidate npm
   cache absent, bounded non-timeout nonzero rc, no surviving child, and
   unchanged workspace/source hashes.
3. Preserve host output and any internal pre-commit log separately; select
   `A_DETAIL_COPY` only when it contains exact command/error context.
4. Run §5.1 chronology commands for the exact npm command, first tarball warning,
   first npm error, final exception, and npm/node paths.
5. Identify whether the first error is cache/filesystem, integrity/content,
   DNS/TLS/proxy, executable, or another typed category.
6. For P12, read only timestamps/metadata from container start, entrypoint logs,
   `.active`, workspace bootstrap log/marker, and directory stats. Do not infer
   probe time if the evidence sheet lacks it.
7. Classify the historical race `CONFIRMED`, `NOT_OBSERVED`, or
   `UNVERIFIED_MISSING_TIME`.

Do-not:

- no second replacement A;
- do not print an entire large log;
- do not let the final exception override an earlier primary error;
- do not mark the race confirmed from source ordering alone.

Exit criteria:

- [ ] A is exact-bound historical evidence or one successful replacement capture;
- [ ] replacement A reproduces nonzero prewarm without timeout/state mutation;
- [ ] CT2 has all five bounded evidence windows;
- [ ] first actual error category is explicit;
- [ ] exact npm/Node path candidate is known or S3 has a bounded lookup rule;
- [ ] P12 has one honest race classification.

Kill-check: A success/timeout/different error or final-lines-only classification
must block S3/B.

### Step S3 — classify failed-environment cleanup and defer live config probes

Traces-to: G2–G3; GAP1, GAP3–G4, GAP6; CT3–CT5; P3–P6, P11; M1–M3.

Depends-on: S2. Parallelizable-with: none.

Target liveness: executable-cause hypothesis L1→rejected; CT3 deferred to B.

Edit: none.

Do:

1. Check only the exact npm/Node paths from CT2. Record that the failed repo
   remains but `node_env-default/bin/{node,npm}` are absent and exec returns 127.
2. Preserve CT2 proof that both exact binaries executed during A and npm returned
   child rc `254`.
3. Classify post-failure absence as pre-commit cleanup, not original cause.
4. Do not search for or substitute system/other pre-commit npm/Node binaries.
5. Admit exact full B using the pre-commit root itself. B succeeded and retained
   the exact environment; continue to S4.1a config/Node-errno corroboration.

Do-not:

- no second A;
- no system npm substitution;
- no cache verify;
- no deletion under `PRE_COMMIT_HOME`.

Exit criteria:

- [x] exact post-failure npm/Node paths are absent;
- [x] A chronology proves both executed before cleanup;
- [x] generic missing-executable classifier is rejected as original cause;
- [x] source/workspace and candidate cache paths remain unchanged;
- [x] S4 exact B is admitted; CT3 values remain pending.

Kill-check: removing CT2's command tuple/child rc would make cleanup versus cause
indistinguishable and must block S4.

### Step S4 — run the exact bounded pre-commit A/B

Traces-to: G2–G3; GAP5–G6; CT1, CT2, CT5; P7–P10; M1–M3.

Depends-on: S3. Parallelizable-with: none.

Target liveness: cache causal claim L0→L3 or falsified.

Edit: no source/index/ref/session edit. Allowed writes are host `/tmp` logs and
npm/pre-commit cache state only.

Preconditions:

- failed workspace still exists and is clean;
- source/deployment/workspace HEAD/status hashes equal CT1 baseline;
- no `pre-commit install-hooks` process remains;
- default live `NPM_CONFIG_CACHE` is unset;
- CT2 binds the exact pre-commit/npm command and S3 records post-failure cleanup;
- cache filesystem has measured headroom;
- A/B proxy fingerprints are identical.

Do:

1. Treat S2's exact-bound historical or replacement command/log as control A.
   Recheck all CT5 identity fields; any mismatch stops at P8. Never run a second
   full A.
2. Run §5.1 S4 commands. Print workspace/container/cache identity before the
   slower operation.
3. Require candidate `/home/fa/.cache/npm` to be absent before B; S3 used a
   different probe path.
4. Run exact B with the fixed inner/outer bounds and only Docker exec environment
   `NPM_CONFIG_CACHE=/home/fa/.cache/npm`, logging to
   `/tmp/fa-precommit-b.log`.
5. Record B rc, bytes, SHA, warning count, first error, and final context. If B
   fails, preserve its new internal pre-commit log separately from A.
6. Confirm no child process remains and recheck workspace/source/deployment
   hashes.
7. B succeeded. Run S4.1a against the newly retained exact environment: npm/Node
   versions, default/override cache config, npm proxy/registry, and direct Node
   mkdir errno. Do not run cache verify or another install.
8. Leave failed workspace Git state untouched. A later container recreation
   clears diagnostic cache state; do not delete candidate cache before S5 has
   classified the result.

Fixed bounds:

```text
inner pre-commit command = 220 seconds, kill-after 5 seconds
host docker exec bound   = 240 seconds, kill-after 5 seconds
fast stat/grep/hash       = 5 seconds each
process-presence check    = 5 seconds
```

Do-not:

- no heredoc or combined cold-install script;
- no `NO_PROXY=*` in B;
- no registry/package revision change;
- no readiness `ensure` on the failed workspace because that would write
  marker/sentinel state and weaken preservation evidence;
- no interpretation from wall time alone.

Exit criteria:

- [x] single replacement A matches CT5 identity fields;
- [x] B differs only by npm cache environment;
- [x] A and B logs are separately identified and bounded;
- [x] B rc is 0 with zero npm/tarball errors;
- [x] source/deployment/workspace hashes are unchanged;
- [x] no child process survives timeout/exit.

Kill-check: add `NO_PROXY=*` to B; T5 must reject the run as a two-variable test.

### Step S5 — record causal decision and admit implementation — EXECUTED

Traces-to: G2–G4; GAP1–G6; CT2–CT6; P3–P11.

Depends-on: S4. Parallelizable-with: none.

Target liveness: cause hypothesis L0→L3.

Decision:

```text
DG1=CACHE_PRIMARY_CONFIRMED
PATCH_DISPOSITION=REVISE
S6_ADMISSION=ALLOW_AFTER_S4_1A_EVIDENCE_RECORD
```

Evidence:

- A terminal: npm child rc `254`, mkdir `/home/fa/.npm`, 2,632 tarball warnings;
- B: same operation, only `NPM_CONFIG_CACHE` changed, rc `0`, zero tarball
  warnings, zero npm errors;
- all eager hook environments installed;
- source/workspace hashes unchanged;
- no child survived;
- existing 1536 MiB tmpfs retained 675,880,960 bytes available.

S4.1a is the sole remaining diagnostic action. It closes config/errno wording;
it cannot reverse DG1 unless it reveals identity or source-preservation drift.
No network/proxy contingency branch remains active because exact B succeeded
under unchanged network/proxy inputs.

Kill-check: remove the B cache override and the exact operation returns to A's
terminal path; remove the causal A/B evidence and S6 admission must be revoked.

### Step S6 — revise and verify the candidate patch

Traces-to: G4–G5; GAP7–G8; CT6–CT8; P13–P14; M4–M6.

Depends-on: S5 executed and S4.1a evidence recorded. Parallelizable-with: none.

Target liveness: patch L1→L3 candidate; not deployed.

Build/test the candidate in a disposable clone of current main. Emit the final
transport patch under `/home/user`; the operator later applies it in canonical
`~/First-Agent-dev`. Never edit the deployment checkout.

Candidate edit set relative to `e8f7ee5`:

- `worklogs/implementation-plans/PLAN-session-workspace-readiness-live-closure.md`
  — ADD reviewed v2 plus pre-merge execution record;
- `worklogs/implementation-plans/session-workspace-readiness-live-verification-from-6.md`
  — ADD rebound diagnosis and pre-merge candidate evidence;
- `worklogs/implementation-plans/PLAN-session-workspace-readiness-bootstrap.md`
  — append child link, DG1, candidate state, and explicit §7 block;
- `knowledge/llms.txt` — route both new worklog artifacts;
- `Dockerfile.fa` — add exact runtime npm cache environment after `HOME`;
- `docker-compose.fa.yml` — add exact first-agent environment entry;
- `scripts/fa-update.sh` — extend `verify_runtime_storage`;
- `scripts/fa-clean-rebuild.sh` — extend runtime storage block;
- `scripts/fa-post-setup.sh` — extend runtime storage block;
- `.github/workflows/advisory.yml` — replace empty source fixture with current
  real Git clone and add hard READY oracle;
- `tests/test_container_build_invariants.py` — Dockerfile/Compose/workflow
  contracts, including the real-source fixture;
- `tests/test_deploy_scripts.py` — all three npm storage producers;
- `npm-cache-readiness-closure-on-7ba1361.patch` — **DELETE** as superseded
  provisional transport.

External output, not tracked in the candidate:

- `/home/user/npm-cache-readiness-closure-on-e8f7ee5.patch` — final binary diff
  from exact current main, including deletion of the stale provisional artifact.

No other product/source/test file is authorized without a plan revision.

Degree of freedom closed:

- npm could derive an unwritable cache/log root from `HOME`; CI could pass an
  empty non-project workspace and never observe readiness.

Deterministic mechanism:

- npm-native environment path inside the existing tmpfs plus blocking real-source
  entrypoint/checker execution.

Do:

1. Clone exact `e8f7ee5` into a disposable candidate, create a feature branch,
   and require a clean status.
2. Copy the reviewed child plan/llms delta and S0–S5 evidence sheet into the
   candidate; append the bounded child/DG1/§7-block summary to the parent plan.
3. Apply the tracked provisional patch to working code, then make the v2
   corrections. Remove the tracked provisional file from the candidate so the
   final applied tree has one source of truth: actual code.
4. Retain Dockerfile/Compose environment and deploy probes only because DG1
   proved them causal.
5. In workflow fixture setup, require an absent source destination, run the
tested object-copying clone, reset canonical origin, and grant read/traverse
bits. Mount `/sessions` and `/home/fa/.fa` as bounded private uid-1000 tmpfs;
remove every sudo/chown/host writable-root operation.
6. In the positive CI command, assert exact `NPM_CONFIG_CACHE`, then run the hard
   read-only checker before `fa --version`. Do not `mkdir` or assert persistence
   of npm's cache directory in this C2.
7. Keep the existing 300-second outer Docker bound unless measured cold CI
   exceeds it; do not inherit readiness's internal 900-second bound blindly.
8. Update `test_container_session_smoke_has_publication_authority_and_wall_bounds`
   to require source clone/readability, both session/state tmpfs mounts, hard
   checker, exact environment, and no host writable-root binds. Add a repository-
   wide workflow invariant forbidding sudo. Keep the two existing bounded Docker
   runs; do not add a third permanent cold run.
9. Reuse existing invalid-workspace tests at
   `tests/test_workspace_bootstrap.py:1160-1210`; do not add a duplicate.
10. Load `pr-creation` before PR preparation. Add exact declarations:
   `TEST-EDITS: tests/test_container_build_invariants.py — pins the corrected
   production-shaped CI fixture and hard readiness consumer` and
   `TEST-EDITS: tests/test_deploy_scripts.py — pins all runtime npm-cache storage
   producers`.
11. After each edit packet run targeted tests, relevant statics, and inspect the
    diff. After the chunk, run producer mutations under exact restoration.
12. After recording final pre-merge test/mutation results in A1/A3, run
    `git diff --binary e8f7ee5 > /home/user/npm-cache-readiness-closure-on-e8f7ee5.patch`.
    Verify that external patch in a second clean `e8f7ee5` clone with
    `git apply --check`, apply, and tree comparison; record SHA/bytes/path count.

Do-not:

- do not add `NPM_CONFIG_CACHE` inside `workspace_bootstrap.py`;
- do not create npm cache in CI before entrypoint and then claim entrypoint made
  readiness possible;
- do not mount the host development checkout writable into the container;
- do not alter hook revisions or cache capacities;
- do not delete the hard checker to make an environment-only test green;
- do not regenerate the tracked provisional patch in place or include both stale
  patch prose and applied source as competing authorities;
- do not merge or deploy in S6.

Exit criteria:

- [ ] targeted container/deploy tests pass;
- [ ] YAML parses and workflow hygiene passes;
- [ ] all changed shell scripts pass syntax checks;
- [ ] existing invalid-workspace tests remain green;
- [ ] real-source candidate reaches READY in Docker C2;
- [ ] Dockerfile producer removal fails the named structural test and, on a
  Docker-capable disposable host, the exact positive C2 command;
- [ ] Compose producer removal kills parsed production-config test;
- [ ] empty-fixture restoration kills the structural workflow authority;
- [ ] `just check` passes on the final candidate;
- [ ] external e8-based patch applies cleanly and its applied tree equals the
  candidate, including deletion of the stale provisional patch;
- [ ] no deployment/source/session mutation occurred.

Primary producer kill-check: remove
`ENV NPM_CONFIG_CACHE=/home/fa/.cache/npm`; raw image C2 must fail at hard
readiness.

#### S6 local execution record — 2026-08-14

Implemented source/config producers:

- exact Dockerfile and Compose npm environment;
- three fail-closed deployment storage probes;
- real-source blocking container readiness CI;
- structural/deploy test authority;
- stale provisional patch superseded by actual source.

Verification:

```text
targeted pytest = 134 passed, 12 capability skips
YAML parse = PASS
shell syntax = PASS
compileall changed tests = PASS
doc links = PASS
producer mutations = 9 current producers killed, 0 survived
real-source fixture clone = PASS on current promisor checkout
real-source read-only checker = degraded_environment/locked_check_failed rc 75
empty fixture baseline = degraded_internal/invalid_workspace rc 70
external patch base = e8f7ee5b3bf4e62402dcb8ca35a672939b726fac
external patch paths = 13
clean clone/apply-check/apply/diff = all rc 0
applied-tree targeted tests = 134 passed, 12 capability skips
applied-tree doc links = 219 files, 0 broken
```

The rc 75 fixture result is the expected pre-entrypoint state: real project input
validated and failed only because no readiness transaction had run. Container CI
runs the production entrypoint first and then requires the read-only checker to
return READY.

Full `just check`, Ruff, Mypy, Pyrefly, and Docker C2 are not available in this
sandbox because uv/just/dev dependencies and Docker are absent. GitHub CI remains
the hard gate; no local pass substitutes for it.

```text
S6_STATUS=DELIVERY_READY_EXTERNAL_PATCH
SECTION_7=DEGRADED
GITHUB_CI=PENDING
RECREATED_DEPLOYMENT=PENDING
```

### Step S7 — deliver, recreate, prove parent §7, and pause

Traces-to: G1, G4–G7; GAP9–GAP12; CT1, CT7–CT11; P15–P17; M5, M7–M8.

Depends-on: S6, then green required CI and human merge for S7.3.
Parallelizable-with: none.

Target liveness: candidate/evidence L2→live §7 L3 or explicit BLOCK.

#### S7.1 — candidate evidence and operator delivery

No candidate-content edit is allowed here; S6 emitted the final patch only after
recording DG1 and pre-merge tests in the reviewed plan, NEW evidence sheet,
parent summary, and llms routing rows.

Do:

1. Re-verify external patch base/SHA/bytes/path count and clean apply/tree
   equality; require it contains A1–A13 as applicable and deletes A5.
2. Confirm included docs still say `SECTION_7=DEGRADED` and
   `FEATURE_PRODUCTION_READINESS=UNCLAIMED`.
3. Present the external patch and operator application commands.

#### S7.2 — operator apply, PR, required CI, and human merge

1. Transfer the presented external patch to
   `~/npm-cache-readiness-closure-on-e8f7ee5.patch` on the operator host.
2. In canonical `~/First-Agent-dev`, require clean status and exact
   `HEAD=e8f7ee5`. If public main advanced, stop and regenerate/review a new-base
   patch; do not force-apply.
3. Create the normal feature branch, verify the patch SHA recorded by S6, run
   `git apply --check`, and apply it:

   ```bash
   cd ~/First-Agent-dev
   ```

   ```bash
   test "$(git rev-parse HEAD)" = e8f7ee5b3bf4e62402dcb8ca35a672939b726fac
   ```

   ```bash
   test -z "$(git status --porcelain=v1 --untracked-files=all)"
   ```

   ```bash
   git switch -c fa/20260814-npm-cache-readiness-closure
   ```

   ```bash
   sha256sum ~/npm-cache-readiness-closure-on-e8f7ee5.patch
   ```

   ```bash
   git apply --check --binary --whitespace=error-all ~/npm-cache-readiness-closure-on-e8f7ee5.patch
   ```

   ```bash
   git apply --binary --whitespace=error-all ~/npm-cache-readiness-closure-on-e8f7ee5.patch
   ```

4. Re-run targeted checks appropriate to the host. Load `pr-creation`. The first
   commit body and PR description open with the first five lines below, replacing
   `<line>` with the staged Dockerfile producer line. The PR description then
   carries the `TEST-EDITS` block:

   ```text
   INTENT: FIX
   CLASS: REPAIR
   INVARIANT: Managed-workspace readiness routes npm cache/log writes into the existing writable runtime cache mount and is hard-checked in container CI.
   DEGREE-OF-FREEDOM CLOSED: npm could derive an unwritable $HOME/.npm path while existence-only container CI still passed.
   DETERMINISTIC MECHANISM: The image pins NPM_CONFIG_CACHE and blocking real-source container CI requires workspace READY at Dockerfile.fa:<line>
   TEST-EDITS:
   tests/test_container_build_invariants.py — pins the corrected production-shaped CI fixture and hard readiness consumer
   tests/test_deploy_scripts.py — pins all runtime npm-cache storage producers
   ```

5. Commit/push the feature branch, open a PR, and require all blocking jobs,
   especially `container-build + smoke tests`, green.
6. Human reviews and merges. Record PR, CI, merge SHA, and merged tree identity.

Agent authority ends at branch push/PR. The human owns merge.

#### S7.3 — operator recreate and rerun parent §7 only

1. Record merged SHA, old container/active identities, deployment and `/repo`
   HEAD/status hashes.
2. Run §5.1 S7.3 commands around normal `fa update`.
3. Require new container/image revision and rendered exact npm/cache/mount
   contract.
4. Bind the startup workspace from the single PID 1 `Created session workspace`
   log and require final `.active` equality/mtime; do not use only health or
   old/new inequality.
5. Validate only `PID1_WS`: B2, identity, `.venv`, four hooks, private READY
   marker, matching sentinel, locked uv, clean status, marker-before-active.
6. Run the warm read-only checker and require `ready_fast_path`.
7. Recompare deployment and `/repo` HEAD/status hashes and record zero provider/
   model calls.
8. On any failure preserve the new workspace/logs, set §7 DEGRADED, and stop
   without repair.

Do-not:

- no managed commit/push/disposable PR after deployment;
- no cleanup of failed evidence;
- no parent §8–§12 continuation in this execution packet.

#### S7.4 — record §7 and pause

Only if S7.3 passes:

1. Set `SECTION_7=PASS` in the NEW evidence sheet and parent summary.
2. Keep `S9_STATUS=PENDING` and
   `FEATURE_PRODUCTION_READINESS=UNCLAIMED`; managed commit/push/PR boundary,
   final source comparison, and cleanup are still pending parent work.
3. Update this child execution/DoD record and `worklogs/HANDOFF.md` per
   doc-maintenance.
4. Run final docs/link/status-consistency checks and pause for a separate next
   task.

Execution record:

```text
MERGED_SHA=33943fa3c21647057bb47b771c9a6997f8683717
CONTAINER_ID=402034445edc94e377b1a5e3ea5e44b5ad366b8ba3fc989f3edf4e8b29212d5a
IMAGE_ID=sha256:50ee3a6030338af2cdcbe5bcb238d507da8b78db31141885efb20cb8571f3100
PID1_WORKSPACE=/sessions/session-20260814T142237-7
READY_REASON=ready_fast_path
READY_CHECK_MS=59
MARKER_MODE=0600
MARKER_BEFORE_ACTIVE=yes
SENTINEL_OK=yes
SOURCE_DEPLOYMENT_PRESERVATION=PASS
PROVIDER_MODEL_CALLS=0
SECTION_7=PASS
```

Exit criteria:

- [x] external e8 patch identity is exact and applied from exact base;
- [x] required CI and human merge identities are recorded;
- [x] recreated container runs merged image;
- [x] final `.active` equals the unique PID 1 startup workspace;
- [x] PID 1 workspace satisfies every CT10 cell and warm fast path;
- [x] deployment/source authorities remain unchanged and clean;
- [x] no model/provider call occurred;
- [x] §7 PASS is recorded without advancing later parent status;
- [x] next bounded task is the fresh logical-session proof.

Kill-checks:

- select old/non-PID1 `.active` → T12 fails;
- set feature readiness VERIFIED while S9 pending → T15 fails.

---

## 6. Verification plan

### T0 — evidence identity and stop behavior

Class: C3/live manual deterministic proxy.

Oracle: exact revision/container/workspace/log SHA and clean status hashes.

Paths: P1–P2. Matrix: M1.

Negative proof: wrong log SHA or missing failed workspace stops before any npm
command.

### T1 — live topology/write boundary

Class: C3 live filesystem.

Oracle: actual mkdir/write rc plus mount options, not `test -w` alone.

Paths: P5–P6. Matrix: M1/M3.

Negative proof: write probe aimed at read-only home returns nonzero.

### T2 — first-error chronology and race evidence

Class: forensic/manual deterministic.

Oracle: bounded line-numbered windows and timestamp ordering.

Paths: P1–P2/P12.

Negative proof: final-lines-only evidence is rejected.

### T3 — failed-environment lifecycle

Class: C2 live process boundary.

Oracle: A command tuple/npm child rc proves executables ran; post-failure rc 127
is classified as pre-commit cleanup, never original cause.

Paths: P3–P5. Matrix: M1.

Kill-check: removing A's executed command/child rc must make the cleanup
classification inconclusive.

### T4 — post-B config and Node errno

Class: C2 live process boundary.

Oracle: retained exact executable paths/versions, default and override cache
values, credential-safe proxy/registry values, structured Node mkdir errno, and
unchanged source/workspace hashes.

Paths: P11. Matrix: M2/M3.

No cache verify or package operation is part of T4.

### T5 — exact pre-commit A/B

Class: C2 live product dependency operation.

Oracle: exact-bound historical or single replacement-A identity/first-error plus
exact B rc/error class, separate bounded logs, and unchanged status hashes.

Paths: P7–P10. Matrix: M1–M3.

Kill-check: replacement A success/timeout/state drift, a second A, any second B
environment change, or A/B identity mismatch invalidates the run.

### T6 — cause conjunction

Class: C0p evidence-table validator/manual review.

Oracle: all mandatory cells for exactly one cause token.

Paths: P3–P11.

Kill-check: remove one `CACHE_PRIMARY` prerequisite; S6 admission becomes BLOCK.

### T7 — Dockerfile/Compose configuration

Class: C0 structural/config parse.

Tests:

- `test_npm_cache_uses_the_writable_home_cache_tmpfs`;
- extension of `test_agent_cache_tmpfs_caps_keep_home_and_uv_separate`.

Oracle: exact producer strings and parsed Compose environment/path containment.

Matrix: M4/M5.

Kill-check: remove each producer independently; its test fails.

### T8 — deployment storage producers

Class: C0/C2 shell structural.

Test: extend
`tests/test_deploy_scripts.py::test_deploy_producers_verify_runtime_user_tmpfs_write_and_exec`.

Oracle: all three scripts require exact env, mkdir, directory, writable, and
traversable state before green result.

Matrix: M6.

Kill-check: remove one producer block; parametrized authority fails.

### T9 — blocking real-source container C2

Class: C2 production image/entrypoint.

Root: `.github/workflows/advisory.yml:container-build` raw Docker run.

Oracle: real managed startup workspace plus read-only checker exit zero.

Paths: P13. Matrix: M4.

Primary kill-check: remove Dockerfile npm environment producer in a disposable
Docker-capable candidate; the exact positive C2 command fails. The structural
test must also fail immediately on that removal. Retained-A/live-B supplies the
production-environment negative/positive mechanism proof.

### T10 — CI anti-theater negatives

Class: C2/C4.

Mutations:

- restore empty `git init` source fixture;
- delete hard checker;
- add `|| true` to the hard checker;
- remove real-source ownership normalization;
- remove Dockerfile or Compose npm producer independently.

Oracle: the named structural test fails for every mutation; Dockerfile producer
removal additionally fails the exact disposable C2 when Docker is available.
Existing `test_workspace_bootstrap.py:1160-1210` remains the behavior authority
for invalid workspace input; no duplicate test is added.

Paths: P14. Matrix: M4.

### T11 — evidence/status documentation

Class: static/document contract.

Oracle: cause token, patch state, section state, and revision identities agree;
Markdown and links pass.

Negative proof: premature PASS/VERIFIED status is rejected.

### T12 — recreated publication identity

Class: C2 live entrypoint/deploy.

Oracle: new container/image, exactly one PID 1 startup-workspace log, final
`.active == PID1_WS`, and active/bootstrap times no earlier than container start,
all under external bounds.

Paths: P15. Matrix: M5/M7.

Kill-check: old, merely-different, or fa-update-restored non-PID1 active path
cannot satisfy recreated-publication assertion.

### T13 — complete §7 readiness

Class: C2/C3 live acceptance.

Oracle: CT10 structured fields plus `check_workspace_ready=ready_fast_path`.

Paths: P16–P17. Matrix: M7/M8.

Producer kill-check is inherited from T9 before deployment; live evidence proves
production topology, not a destructive live mutation.

### T14 — source/deployment preservation

Class: C3 live authority boundary.

Oracle: before/after HEAD and porcelain hashes equal for deployment and `/repo`;
managed workspace clean.

Negative proof: any mismatch blocks §7.

### T15 — parent trajectory/status consistency

Class: static/document contract.

Oracle:

```text
SECTION_7=PASS
S9_STATUS=PENDING
FEATURE_PRODUCTION_READINESS=UNCLAIMED
```

until remaining parent proof runs.

Negative proof: setting feature VERIFIED early fails review/status validator.

### LIVE-PATH PROOF LP1 — npm cache producer to managed READY

```text
root: image entrypoint → workspace_bootstrap ensure → pre-commit install-hooks
matrix: M4 cold raw image
producer: Dockerfile.fa runtime NPM_CONFIG_CACHE environment
consumer: npm inside pre-commit Node environment; readiness marker/sentinel
C2 test: .github/workflows/advisory.yml container-build session smoke
oracle: read-only checker returns READY; marker/sentinel/environment present
kill-check: remove Dockerfile ENV → cold container readiness fails
paths-covered: P13/P14 = 2/2
pyramid: A
```

### LIVE-PATH PROOF LP2 — recreated deployment

```text
root: operator fa update → PID 1 entrypoint log → exact /sessions/.active workspace
matrix: M5/M7/M8
producer: merged image+Compose npm cache policy and PID 1 publication
consumer: bound startup workspace readiness state and operator verifier
oracle: active==PID1_WS + CT10 complete + ready_fast_path + unchanged source/deployment hashes
kill-check: pre-merge C2 producer removal; old/non-PID1 active selection fails T12
paths-covered: P15/P16/P17 = 3/3
pyramid: A
```

### Static and gate commands for S6

Run in order, recording actual output:

```bash
uv run python -m pytest -q tests/test_container_build_invariants.py tests/test_deploy_scripts.py tests/test_workspace_bootstrap.py tests/test_workflow_hygiene.py
bash scripts/check_shell_syntax.sh scripts/fa-update.sh scripts/fa-clean-rebuild.sh scripts/fa-post-setup.sh
uv run ruff check tests/test_container_build_invariants.py tests/test_deploy_scripts.py
uv run ruff format --check tests/test_container_build_invariants.py tests/test_deploy_scripts.py
uv run mypy tests/test_container_build_invariants.py tests/test_deploy_scripts.py
uv run pyrefly check
python3 scripts/check_doc_links.py
uv run fa authoring-check
uv run just check
git apply --check /home/user/npm-cache-readiness-closure-on-e8f7ee5.patch
# Then required GitHub job: container-build + smoke tests
```

No completion claim may be made from “no exception.” Positive READY and negative
producer kills are both required.

---

## 7. Risks, rollback, and open questions

### Risks

| Risk | Description | Mitigation | Detection |
| --- | --- | --- | --- |
| RK1 | tarball warnings are primary and npm cache is secondary | **closed:** exact B removed every warning/error with only cache env changed | T2/T5 |
| RK2 | network changed between A/B | **closed for primary cause:** same live path plus zero-warning B; recreated cold CI remains independent proof | T5/T9 |
| RK3 | npm ENOENT conflicts with shell EROFS | S4.1a direct Node errno plus chronology; wording gap cannot reverse DG1 | T2/T4 |
| RK4 | wrong npm binary used for corroboration | bind S4.1a to the exact successful B environment paths | T4 |
| RK5 | timeout leaves child process | inner+outer timeout and post-process check | T5 |
| RK6 | A partial state helps B | exact B installed all environments; recreated cold container CI proves clean-cache behavior | T5/T9 |
| RK7 | CI hard check is fake-green on invalid source | real current source fixture + structural mutant; reuse existing invalid-input tests | T9/T10 |
| RK8 | CI cold network operation is flaky | existing pins, 300-second measured bound, classify timeout separately; no blind retry loop | T9 |
| RK9 | CI fixture leaks checkout credentials | set credential-free canonical remote; never print config values beyond validated URL | T9/T10 |
| RK10 | health or fa-update-restored `.active` selects wrong workspace | bind unique PID 1 log workspace and require final equality/mtime | T12 |
| RK11 | deploy scripts probe after readiness failure and are mistaken for readiness | probes are storage only; §7 checker remains separate | T8/T13 |
| RK12 | patch artifact and applied source diverge | external e8 patch generated last; second clean apply/tree comparison; tracked provisional deleted | S6/T11 |
| RK13 | post-merge evidence sheet is reconstructed as if raw evidence | NEW sheet writes only rebound outputs; missing raw artifact blocks claim | T0/T11 |
| RK14 | fail-open policy is silently reversed | no runtime status policy edit; CI only hard gate | diff review/T10 |
| RK15 | later parent proof is prematurely declared | status conjunction and explicit pause | T11/T15 |

### Rollback

No data migration exists.

If a merged cache patch must be rolled back:

1. human reverts the runtime patch through a PR;
2. operator runs normal `fa update` to rebuild/recreate;
3. ephemeral npm/pre-commit/uv cache state disappears with the old container;
4. no persistent cache/bind cleanup is required;
5. existing managed workspaces remain on `/sessions`; their Git state is not
   reset or deleted;
6. section status returns to DEGRADED/BLOCK until a replacement cause is proven.

Do not manually unset the variable in the live container as a rollback claim;
container mutation is non-persistent and breaks revision/image authority.

### Open questions

No blocking policy question remains. DG1/DG2/DG3 are execution gates, not Q#.

#### Q1 — observed historical startup race (NON-BLOCKING; default UNVERIFIED)

Default: `UNVERIFIED_MISSING_TIME` unless S2 has actual probe/start/publication
timestamps. Regardless of historical classification, S7.3 binds the recreated
PID 1 workspace and does not use health or merely-different `.active` as
readiness.

#### Q2 — healthcheck should include readiness (NON-BLOCKING; default NO)

Default: no change. Service liveness and managed-workspace readiness are
separate contracts; fail-open runtime policy and the lightweight healthcheck are
standing decisions. Promote to a separate policy question only if recreated
verification proves PID1 binding cannot prevent operator misuse.

#### Q3 — npm cache persistence (RESOLVED/DEFERRED)

Keep existing ephemeral tmpfs per S7 benchmark. Reopen only from measured cap or
restart-frequency evidence under a separate P2 plan.

#### Q4 — sudo in CI workflows (RESOLVED: FORBIDDEN)

Use mount-time ownership for ephemeral writable roots. CI keeps source as a
runner-owned read-only bind and mounts `/sessions` plus `/home/fa/.fa` as bounded
uid/gid-1000 tmpfs. A repository-wide test rejects sudo in workflow YAML. Live §7
retains authority for production bind storage.

---

## 8. Prior-claim and patch disposition

| RN | Input claim | Verdict before execution | Reason | Anchor |
| --- | --- | --- | --- | --- |
| RN1 | npm cache path is confirmed root cause | **Rewrite as hypothesis** | final path/topology support it; no controlled A/B or chronology yet | S2–S5/CT5 |
| RN2 | tarball warnings prove registry corruption | **Rewrite as competing hypothesis** | warning order and relation to cache failure unknown | S2/S5 |
| RN3 | npm log-path failure is merely secondary | **Unverified** | requires first-error/stack chronology | CT2/T2 |
| RN4 | missing executable caused rc 3 | **Reject unless T3 proves it** | classifier matched generic ENOENT text | S3/T3 |
| RN5 | wrapper `NO_PROXY=*` distinguishes readiness | **Reject** | wrapper exports after readiness prelude | S1/S4 |
| RN6 | `NPM_CONFIG_CACHE=/home/fa/.cache/npm` is minimal if cache cause proven | **Accept conditionally** | native npm policy and existing tmpfs; no readiness branch needed | S5/S6/CT6 |
| RN7 | put npm path in Dockerfile only | **Rewrite** | raw image needs Dockerfile; rendered production contract/test also pins Compose | CT6/T7 |
| RN8 | deployment probes prove readiness | **Reject** | they prove storage only; §7 checker is separate | CT8/CT10 |
| RN9 | provisional hard CI check closes blind spot | **Reject as written** | empty source fixture always invalid | GAP7/S6 |
| RN10 | hard CI readiness is required | **Accept** | standing design says CI is hard gate; current gap confirmed | CT7/T9 |
| RN11 | health green before new `.active` proves a product race | **Rewrite** | code permits timing; historical occurrence needs timestamps; verifier must wait | CT9/T12 |
| RN12 | local cold override success proves sole live cause | **Reject as sole proof** | different environment/topology/network; capacity evidence only | S4/S5 |
| RN13 | cache capacities fit proposed npm path | **Accept** | controlled peaks fit 1536M with recorded headroom | CT6/Q3 |
| RN14 | change readiness to fail closed | **Reject for this slice** | conflicts with standing policy; CI remains hard gate | non-goal |
| RN15 | continue to managed commit/push after patch CI | **Reject** | recreated live §7 is mandatory first | S7.3/S7.4 |

---

## 9. Definition of Done

### State

Before:

```text
SECTION_6=PASS
SECTION_7=DEGRADED
CAUSE_STATUS=UNPROVEN
PATCH_STATUS=PROVISIONAL_UNAPPROVED
S9_STATUS=PENDING
FEATURE_PRODUCTION_READINESS=UNCLAIMED
```

After this child plan may close:

```text
CAUSE_STATUS=<closed token with evidence>
PATCH_STATUS=E8_PATCH_MERGED_AND_PROVISIONAL_DELETED
SECTION_7=PASS
S9_STATUS=PENDING
FEATURE_PRODUCTION_READINESS=UNCLAIMED
```

Full child completion requires recorded S4.1a evidence, merged e8-based repair,
and DG3 PASS. DG1 is already `CACHE_PRIMARY_CONFIRMED`. If recreated §7 fails,
the section remains DEGRADED and later work stays blocked.

### Artifacts

- this child plan exists and has execution evidence;
- NEW post-§6 verification sheet has exact diagnosis and §7 output;
- parent plan links the child and reflects section state;
- tracked provisional patch is deleted by the merged candidate;
- external e8-based patch has exact identity and applied-tree equality;
- conditional runtime/CI/test files match the merged patch branch;
- session-close handoff names the next bounded action.

### Contract completion table

| Contract | Planned completion oracle |
| --- | --- |
| CT1 | exact live identity and clean hashes |
| CT2 | bounded first-error chronology |
| CT3 | exact runnable npm/node and config |
| CT4 | live shell/Node/cache errno proof |
| CT5 | exact-bound historical or single replacement A + exact B/preservation |
| CT6 | conditional exact env producers + kills |
| CT7 | blocking real-source container READY |
| CT8 | all deploy storage producers verified |
| CT9 | recreated new-active selection |
| CT10 | complete §7 READY/preservation |
| CT11 | evidence/status authority consistent |

### Binary completion checklist

- [ ] retained evidence identity is exact;
- [ ] confirmed facts and hypotheses are separate;
- [ ] npm command, first warning, first error, and final exception are ordered;
- [ ] executable/config/errno/proxy alternatives are classified;
- [ ] A is exact-bound historical evidence or one bounded replacement, and exact B changes only npm cache;
- [ ] one cause token passes every mandatory cell;
- [ ] patch disposition follows that token;
- [ ] if revised, CI fixture is real source and hard READY is C2-live;
- [ ] targeted/static/full gates and producer kills are recorded;
- [ ] human merge and operator recreation identities are recorded;
- [ ] verifier bound the unique PID 1 startup workspace and final `.active` equals it;
- [ ] new workspace passes all §7 readiness cells;
- [ ] deployment and `/repo` remain clean and unchanged;
- [ ] no provider/model call occurred;
- [ ] later parent proof remains pending;
- [ ] no non-goal or unapproved policy change entered the diff.

Done is falsifiable: removing the Dockerfile environment producer must fail the
named structural gate and disposable cold container C2, while selecting an old,
merely-different, or non-PID1 active workspace must fail recreated publication
verification.

---

## 10. Anti-theater and READY gate

### Anti-theater checklist

- [x] Every referenced current symbol/file was source-verified or marked as a
  future conditional edit.
- [x] Every G# maps to GAP#, CT#, S#, T#, and an artifact/non-goal.
- [x] Every observable contract names producer and consumer.
- [x] Kill-checks target actual environment/CI/publication producers.
- [x] Every P# has a step and verification.
- [x] Every M# has a step and verification.
- [x] No dual-write event contract is introduced.
- [x] External I/O is bounded and raw logs/secrets are not primary oracles.
- [x] No “works correctly” or no-exception DoD is used.
- [x] Assumptions are marked as hypotheses or unresolved Q#.
- [x] Security boundaries have adversarial path/value/preservation checks.
- [x] All IDs referenced in v2 resolve.

### READY gate

- [x] Preflight is source-grounded and non-trivial.
- [x] P2 depth matches live/config/CI/rollout scope.
- [x] Intent, non-goals, current state, target state, and transitions are
  concrete.
- [x] Function/process, signal/config, data, invariant, and security contracts
  are present where applicable.
- [x] Path/environment matrices are covered.
- [x] Steps are file/symbol or exact live-boundary specific.
- [x] Verification includes C2 live paths and producer kills.
- [x] Prior claims/provisional patch items are dispositioned.
- [x] Separate adversarial plan review requested by the operator is complete.
- [x] No blocking open question remains; DG1–DG3 are executable state gates.
- [x] Fixed atomic commands bind historical A or capture one replacement and bind recreated PID 1.
- [x] Patch application/removal/output authority is exact at `e8f7ee5`.

Therefore v2 is **READY**. Execution is a separate task and begins at S0; this
review did not run live probes, apply the provisional patch, merge, or deploy.

---

## 11. Artifacts inventory

| Artifact | Path | Action | Owner |
| --- | --- | --- | --- |
| A1 | `worklogs/implementation-plans/PLAN-session-workspace-readiness-live-closure.md` | NEW reviewed plan/execution record | plan authoring/S7 |
| A2 | `knowledge/llms.txt` | route A1 now; route A3 during S7 | plan authoring/S7 |
| A3 | `worklogs/implementation-plans/session-workspace-readiness-live-verification-from-6.md` | NEW rebound diagnosis/live evidence | S0/S5/S7 |
| A4 | `PLAN-session-workspace-readiness-bootstrap.md` | append child status/link only | S7 |
| A5 | `npm-cache-readiness-closure-on-7ba1361.patch` | conditional DELETE as superseded | S6 |
| A6 | `Dockerfile.fa` | conditional env producer | S6 |
| A7 | `docker-compose.fa.yml` | conditional production env | S6 |
| A8 | `scripts/fa-update.sh` | conditional storage probe | S6 |
| A9 | `scripts/fa-clean-rebuild.sh` | conditional storage probe | S6 |
| A10 | `scripts/fa-post-setup.sh` | conditional storage probe | S6 |
| A11 | `.github/workflows/advisory.yml` | conditional real-source hard READY | S6 |
| A12 | `tests/test_container_build_invariants.py` | conditional config/workflow authority | S6 |
| A13 | `tests/test_deploy_scripts.py` | conditional deploy producer authority | S6 |
| A14 | `worklogs/HANDOFF.md` | session-close state/next action | S7 |
| A15 | host `/tmp/fa-precommit-a-replacement.log` | replacement-A command output | S2–S5 |
| A16 | host `/tmp/fa-precommit-a-internal.log` | replacement-A detailed internal log when produced | S2–S5 |
| A17 | `/home/user/npm-cache-readiness-closure-on-e8f7ee5.patch` | external final delivery patch | S6/S7 |
| A18 | host `/tmp/fa-recreated-pid1.log` | recreated PID 1 publication evidence | S7 |
| A19 | host `/tmp/fa-precommit-b.log` | B command output | S4–S5 |

No new source module, dependency, service, cache mount, test file, or runtime
schema is planned.

---

## Executor handoff

1. Execution is currently at S4.1a; S0–S5/DG1 are recorded complete.
2. Run only the bounded post-B config/Node-errno collector, record it, then enter
   S6 implementation. Do not run cache verify, another install, or another A/B.
3. Deliver one parenthesized copy/pasteable Bash block per stage with individual
   timeouts, collection-before-classification, no heredoc, and parent-alive rc.
4. Never edit deployment/source/session Git state while collecting S4.1a.
5. Stop on identity or source/workspace drift; do not normalize evidence.
6. Enter S6 only after S4.1a records exact retained binaries, cache config,
   proxy/registry posture, and Node errno; DG1 is already closed.
8. After each candidate edit: targeted test, relevant static check, diff
   inspection, and actual output before the next edit.
9. Run producer mutations after the candidate chunk and restore exact bytes/mode.
10. Emit the final patch outside the repository against exact `e8f7ee5`; it must
    delete the stale tracked provisional artifact in the applied tree.
11. Load `pr-creation`, include FIX/TEST-EDITS fields, and stop at agent branch/
    PR authority; human controls merge and deployment.
12. S7.3 performs parent §7 only; S7.4 records it and pauses. Parent commit/push/
    PR-boundary proof is a later task.
