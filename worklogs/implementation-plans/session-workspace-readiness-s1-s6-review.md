# S1–S6 integrated workspace-readiness production review

Date: 2026-08-13
Plan: `PLAN-session-workspace-readiness-bootstrap` v17
Review slice: S6.5
Review depth: P3, Pyramid A C0/C1/C2/C3/C4

## 1. Admission state

```text
S7_ADMISSION=ALLOW
```

The final post-Q7/E12 exact candidate remained clean and every blocking
`just check` subgate returned zero. S6.5 therefore admits S7 measurement.

This is admission to S7 measurement, not a shipped-feature declaration. Actual
GitHub publication, deployment-mirror immutability, PR/CI observation, and human
merge authority remain S9-owned.

## 2. Review method and boundaries

The review read the actual composition roots and production diffs rather than
accepting prior completion summaries:

- Git provisioning: `src/fa/session/workspace.py`,
  `SessionManager._provision_workspace`, CLI composition, entrypoint, and
  post-setup publication smoke;
- readiness: `ensure_workspace_ready`, `check_workspace_ready`, locked repair,
  private marker/log/sentinel state, process execution, wrappers, and aliases;
- hooks: effective/default path resolution, installer/status, all four tracked
  hook sources, actual checked-out wrapper execution, stdin, argv, and return
  codes;
- mutation: explicit/configured runner, targeted selector, Git discovery,
  permanent config, workflow, CODEOWNERS, and protected-path authority;
- S6 operator/deployment roles, recovery commands, VS Code convenience task,
  Markdown, and internal links;
- exact changed/untracked inventory plus unchanged mode/config authorities.

No provider/model call, external GitHub push, cache-topology change, secret copy,
new dependency, ignore, pragma, allowlist, skip weakening, threshold change, or
mutation-survivor relabeling was used.

## 3. Confirmed findings and remediation ledger

| Finding | Confirmation | Severity | Remediation | Negative proof | Final status |
| --- | --- | --- | --- | --- | --- |
| D26: S6 named the permanent C4 suite for alias/docs checks | core mutation scope would absorb non-core assertions | medium | moved authority to `tests/test_workspace_bootstrap_aliases.py` | alias suite and permanent-scope config checks | verified |
| D27/GAP18: readiness children inherited hook stdin | pipe probe captured the pre-push ref line in a child | blocker | `_run_process` uses `stdin=subprocess.DEVNULL` | child-stdin and real-wrapper producer mutants fail | verified |
| D28/GAP19: real commit path was blocked by type diagnostics | full Mypy had six findings; Pyrefly had two | blocker | minimal signatures/narrowing/annotations; no suppressions | full types and real second commit pass | verified |
| D29/GAP20: CODEOWNERS parity parser omitted real patterns | focused semantic parity test failed | high | exact/prefix/wildcard semantic authority | runner-seat removal fails parity test | verified |
| D30/GAP17: dirty worktree could not establish merge readiness | authoring gate failed in the implementation checkout | blocker | exact-byte isolated clean Git candidate | clean authoring and `just check` gate | verified |
| E9: clean materialization omitted public export, deterministic capabilities, one mode, and dependency authority | first corrected candidate exposed all four | high | export `ReadyReason`; collection decorators; mode 0755; selective contract copy and force-add | affected suites repeated green; mode/manifest assertions | verified |
| E10: deptry treated internal scripts as dependencies and found dead `tomli` fallback | live and candidate `_lint` reproduced 12 DEP001 + one DEP003 | high | native first-party config; stdlib-only import under Python ≥3.13 | removing config produces 12 DEP001; restoring fallback produces one DEP003 | verified |
| Q7/M17: automatic readiness overwrote external/non-FA hooks | scratch external `core.hooksPath` changed operator hook SHA-256 | blocker | custom paths and non-FA collisions are preserved and typed DEGRADED; no chaining | three E12 producer mutants fail; bytes/modes/config remain exact | verified |

Confirmed Q7 scratch evidence:

```text
operator pre-commit before = 004a1dbb52e21ef8b040e7eb867e83b5e8b97b9104df42ec869a2fe5e23f40cb
operator pre-commit after  = 8c8a903470c46194bc42780b4099ad2ef249128407fd2f28106ca99bd07c196b
overwritten                = true (pre-remediation scratch only)
```

The scratch directory was trap-cleaned. Post-remediation tests prove the same
path and collision are not mutated.

## 4. CT13 closed claim ledger

Each row supplies the CT13 fields:
`claim_id, intent, slice, artifacts, producer, consumer, runtime_paths,
current_behavior, target_behavior, failure_behavior, evidence, test_class,
producer_kill, verdict, severity, remediation, final_status`.

| claim_id | intent | slice | artifacts | producer | consumer | runtime_paths | current_behavior | target_behavior | failure_behavior | evidence | test_class | producer_kill | verdict | severity | remediation | final_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CL01/G1 | B2 routing | S1–S2 | A3–A10, A31–A32 | `provision_git_workspace`; entrypoint config | Git fetch/push | P1–P3, P13–P14; M6–M8 | local fetch; canonical/validated push; custom Q5 preserved/redacted | same | typed provision/config failure; no credential output | `test_manager_git_source_provisions_clean_b2_workspace`; entrypoint suites | C1/C2/C3 | remove pushurl/config producer | present | none | none | verified |
| CL02/G2 | clean commit-capable clone and identity | S1–S2 | A3–A9 | provisioner + manager dispatch | commit/hook path | P1, P3, P5; M7, M9 | captured revision, clean branch, local identity | same | rollback helper-created target only | real commit identity tests; A55 second commit | C1/C2 | revert manager to copytree | present | none | none | verified |
| CL03/G3 | readiness before model execution | S3 | A4, A7, A11–A13, A31–A32 | manager/entrypoint/CLI preparer | provider roots and hooks | P1–P4, P10–P11 | lifecycle invokes locked readiness before active/provider use | same | typed degraded state, fail-open | manager C1, entrypoint ordering, zero-provider-call assertions | C1/C2/C3 | remove lifecycle call | present | none | none | verified |
| CL04/G4 | no LLM bootstrap work | S3–S6 | A11–A16, A23–A25, A37, A53 | deterministic lifecycle and wrappers | managed session/operator | P1–P6 | env/hooks/prewarm occur before model; docs assign no model task | same | structured operator recovery | alias/docs tests and A55 | C1/C2 | remove wrapper/lifecycle producer | present | none | none | verified |
| CL05/G5 | warn-only bootstrap, strict quality rc | S3–S5 | A11, A19–A21, A40–A42 | typed readiness + hook prelude | Git operation | P7–P9 | bootstrap failure allows; normal gate rc unchanged | same | warning/log; no quality fail-open | hook ready/degraded/rc suites; real wrapper | C1/C3 | broaden exit-zero or remove prelude | present | none | none | verified |
| CL06/G6 | operator clone ready; deployment mirror not dev surface | S4/S6 | A14–A18, A22–A25, A37, A53 | wrapper/aliases/docs | operator | P6, P15; M4–M5, M10 | explicit operator recovery; VS Code convenience only | same | stable missing-tool recovery | 10 alias/doc tests; links/Markdown | C1/static | remove S6 role assertion | present | none | none | verified |
| CL07/G9 | trustworthy mutation feedback | S3.5 | A45–A52, A65 | `run_slice`; selectors/workflow | operator/pre-push/CI | P16–P20; M11–M14 | isolated strict result identity and separate type-invalid | same | action-required or infrastructure rc; exact artifacts | real mutmut fixture; config/workflow/TCB suites | C1/C3/C4 | remove classifier/delegate/workflow seat | present | none | none | verified |
| CL08/G10/GAP17 | integrated S1–S6 acceptance | S6.5 | A54–A55 | CT13 review + clean candidate | S7 admission | P21–P24; M15–M17 | one clean real runtime/gate root | same | any unexplained red sets BLOCK | A55; 184 focused; final exact candidate green | C1/C2/C3/C4 | remove ledger/runtime producer | present | none | A54 and A55 | verified |
| CL09/GAP18 | isolate hook stdin from readiness children | S6.5 | A11, A13, A20 | `_run_process(stdin=DEVNULL)` | child and pre-push body | P22; M16 | child EOF; parent forwards exact bytes once | same | typed bootstrap degradation; normal payload preserved | `test_real_wrapper_children_cannot_consume_pre_push_stdin` | C1/C3 | delete DEVNULL | present | none | D27 fix | verified |
| CL10/GAP19 | zero-diagnostic real commit path | S6.5 | A57–A61 | valid source/test types | Mypy, Pyrefly, hooks | P23; M15 | no suppressions; commit succeeds | same | diagnostics block | Mypy 362 files; Pyrefly zero; A55 | C1/C2/static | restore invalid narrowing/signature | present | none | minimal type fixes | verified |
| CL11/GAP20 | semantic governance parity | S6.5 | A50–A52, A56 | workflow + CODEOWNERS + TCB sets | authoring gate | P20, P23 | exact/prefix/wildcard patterns cover runner | same | missing seat blocks | parity/workflow tests | C1/static | remove runner seat | present | none | semantic parser | verified |
| CL12/Q7 | preserve custom/unowned hook code | S6.5 | A11, A13, A21, A44 | default/effective resolver + ownership preflight | readiness and operator hook state | P7–P8, P24; M17 | custom/collision returns typed DEGRADED without mutation | same | reasons `custom_hooks_unmanaged` or `hook_seat_collision`; rc 75 | external/collision, fast-path, closed-reason tests | C0/C1/C3 | remove either ownership producer | present | none | conservative preservation | verified |
| CL13/S6 | truthful roles and recovery | S6 | A22–A25, A37, A53 | maintained docs/aliases | operator and agent | P6, P15 | managed clone/operator/deployment roles separated | same | docs gate blocks contradiction | Markdown 0; links; 10 tests | C1/static | remove role/recovery claim | present | none | mechanical normalization | verified |
| CL14/S9 | actual GitHub publication and deployment observation | S9 | A1, A30 | future live branch/CI probe | operator/human merge gate | external publication | not executed in S6.5 by design | live proof in S9 | S9 blocks shipped claim, not S7 benchmark | local bare publication only; no external push | C3/live | N/A until S9 | unverified | none | owner S9 | deferred-with-owner |

## 5. Goal, gap, contract, path, and matrix coverage

### 5.1 Goals

| ID | S6.5 disposition | Evidence/owner |
| --- | --- | --- |
| G1 | verified | CL01; CT1–CT2 |
| G2 | verified | CL02; CT1/CT6 |
| G3 | verified | CL03; CT3–CT4/CT6 |
| G4 | verified | CL04 |
| G5 | verified | CL05; CT5/CT8 |
| G6 | verified | CL06; CT7 |
| G7 | deferred with owner | S7/CT9 measurement starts only after ALLOW |
| G8 | partially implemented, later owner explicit | S6 truthful subset verified; S8 docs and S9 live proof remain |
| G9 | verified | CL07; CT10–CT12 |
| G10 | verified | CL08; CT13; final exact candidate |

### 5.2 Gaps

| ID | Disposition | Authority |
| --- | --- | --- |
| GAP1 | closed | B2 provisioner/entrypoint tests |
| GAP2 | closed | Git dispatch and clean-state tests |
| GAP3 | closed | entrypoint readiness ordering |
| GAP4 | closed | new/attach lifecycle tests |
| GAP5 | closed | checked-out stdlib wrapper and aliases |
| GAP6 | closed | marker plus cache sentinel |
| GAP7 | closed | four hook preludes and typed mapping |
| GAP8 | closed for S6 scope | operator/deployment role authority |
| GAP9 | deferred with owner | S7 measurement |
| GAP10 | deferred with owner | S8 canonical docs |
| GAP11 | deferred with owner | S9 live publication |
| GAP12 | closed | validated read-only probe T0 |
| GAP13 | closed | trusted local identity and real commit |
| GAP14 | closed | isolated slice runner |
| GAP15 | closed | scoped Pyrefly type-invalid classification |
| GAP16 | closed | permanent scope and complete CI artifacts |
| GAP17 | closed | A54/A55/T21–T24 and final exact candidate |
| GAP18 | closed | DEVNULL + exact forwarding |
| GAP19 | closed | full types + real commit + clean gate |
| GAP20 | closed | semantic CODEOWNERS/TCB parity |

### 5.3 Contracts

| ID | Disposition | Evidence |
| --- | --- | --- |
| CT1 | verified | real Git provision/config/rollback tests |
| CT2 | verified | B2/custom Q5 URL and publication rewrite tests |
| CT3 | verified | closed readiness state/reason/process tests |
| CT4 | verified | private atomic marker/sentinel/fingerprint tests |
| CT5 | verified | four real hook source paths and exact rc/stdin |
| CT6 | verified | manager/entrypoint lifecycle admission |
| CT7 | verified | operator wrapper/aliases/docs |
| CT8 | verified | private structured logs and warnings |
| CT9 | deferred with owner | S7 benchmark report |
| CT10 | verified | isolated strict slice runner |
| CT11 | verified | scoped type-invalid filtering |
| CT12 | verified | permanent config/workflow/TCB |
| CT13 | verified | this ledger, A55, kills, final candidate gate |

### 5.4 Runtime paths

| ID | Disposition | ID | Disposition |
| --- | --- | --- | --- |
| P1 | verified | P13 | verified |
| P2 | verified | P14 | verified |
| P3 | verified | P15 | verified |
| P4 | verified | P16 | verified |
| P5 | verified | P17 | verified |
| P6 | verified | P18 | verified |
| P7 | verified | P19 | verified |
| P8 | verified | P20 | verified |
| P9 | verified | P21 | verified |
| P10 | verified | P22 | verified |
| P11 | verified | P23 | verified |
| P12 | verified | P24 | verified: Q7 stop/decision/restart occurred |

### 5.5 Matrix rows

| ID | Disposition | Evidence/owner |
| --- | --- | --- |
| M1 | deferred with owner | S7 cold tmpfs measurement |
| M2 | readiness warm path verified; cost deferred | fast-path tests; S7 benchmark |
| M3 | verified | missing-sentinel repair |
| M4 | verified | operator alias live/static authority |
| M5 | verified | missing uv/just recovery |
| M6 | verified | HTTPS normalization |
| M7 | verified | SSH + cleared identity commit |
| M8 | verified | explicit override composition |
| M9 | verified | non-Git fallback compatibility |
| M10 | verified | CI hook-seat exemption/docs |
| M11 | verified | tracked/worktree/untracked slice input |
| M12 | verified | closed exits/result identity |
| M13 | verified | scoped Pyrefly classification |
| M14 | verified | CLI/targeted/weekly consumers |
| M15 | verified | final post-E12 exact candidate and A55 green |
| M16 | verified | child EOF + exact ref bytes |
| M17 | verified | Q7 custom path/default collision preservation |

## 6. Exact candidate artifact inventory

The pre-A54 Git inventory contained 51 changed/untracked paths. A54 is path 52.
The table is the exact union expected by T21. “Static/type remediation” rows are
behavior-neutral corrections required by blocking gates.

| Path | Artifact | Slice/role | Evidence | Final status |
| --- | --- | --- | --- | --- |
| `.fa/host-bootstrap.json` | A18 | S4 tracked machine-state deletion | marker migration test | verified |
| `.github/CODEOWNERS` | A51 | S3.5 TCB owner seat | semantic parity test | verified |
| `.github/workflows/tests.yml` | A50 | configured mutation consumer | workflow contract test | verified |
| `.gitignore` | A17 | readiness runtime state policy | marker migration test | verified |
| `AGENTS.md` | A23 | managed/operator responsibility | S6 doc tests/Markdown | verified |
| `fa-bootstrap-preflight-probe.sh` | A1 | S0/S9 safe probe | shell/static probe authority | verified for S0; retained for S9 |
| `justfile` | A16 | wrapper/check aliases | alias tests and real `just check` | verified |
| `knowledge/ci-guardrails-reference.md` | A37 | lifecycle/hook recovery authority | S6 doc tests/Markdown | verified |
| `knowledge/instructions/01-install.md` | A24 | checkout roles/recovery | S6 doc tests/links | verified |
| `knowledge/instructions/02-operations.md` | A25 | B2/readiness operations | S6 doc tests/links | verified |
| `knowledge/research/ai-assisted-maintenance-mutation-feedback-loops-2026-08.md` | A65 | requested research note; no runtime authority | inventory/review | verified ancillary |
| `pyproject.toml` | A49 | mutation/type/deptry config | config tests, `_lint`, types | verified |
| `scripts/_console.py` | A58 | minimal type narrowing | full Mypy | verified |
| `scripts/_git_diff.py` | A48 | bounded NUL-safe discovery | slice tests | verified |
| `scripts/bootstrap/host_bootstrap.py` | A15 | bounded host adapter | alias tests | verified |
| `scripts/bootstrap/workspace.py` | A14 | checked-out stdlib wrapper | wrapper and real-hook tests | verified |
| `scripts/check_dependency_contract.py` | A64 | stdlib TOML under Python floor | 21 tests, deptry kill | verified |
| `scripts/check_protected_paths.py` | A52 | exact/prefix TCB authority | semantic parity | verified |
| `scripts/fa-entrypoint.sh` | A7 | B2/readiness startup root | entrypoint C2 tests | verified |
| `scripts/fa-post-setup.sh` | A8 | publication smoke root | deploy tests | verified |
| `scripts/run_slice_mutmut.py` | A45 | isolated strict executor | real/fake runner tests | verified |
| `scripts/run_targeted_mutmut.py` | A47 | Git selector/delegate | selector tests | verified |
| `src/fa/cli.py` | A31 | push/readiness composition | CLI/provider-order tests | verified |
| `src/fa/egress_proxy/server.py` | A57 | minimal signature correction | full Pyrefly | verified |
| `src/fa/hygiene/hooks/__init__.py` | A36 | explicit source wrapper | installer tests | verified |
| `src/fa/hygiene/hooks/_util.py` | A44 | bounded effective/default path resolver | E12 resolver tests/kill | verified |
| `src/fa/hygiene/hooks/commit-msg` | A42 | self-readiness + exact normal body | hook tests | verified |
| `src/fa/hygiene/hooks/install.py` | A12 | explicit checked-out source installer | installer/readiness tests | verified |
| `src/fa/hygiene/hooks/pre-commit` | A19 | self-readiness + strict normal gate | hook tests/real commit | verified |
| `src/fa/hygiene/hooks/pre-push` | A40 | self-readiness + exact stdin/check | real wrapper tests | verified |
| `src/fa/hygiene/hooks/prepare-commit-msg` | A41 | self-readiness + message argv | hook tests | verified |
| `src/fa/hygiene/hooks/status.py` | A62 | current status documentation | status tests/types | verified |
| `src/fa/session/manager.py` | A4 | Git dispatch/readiness lifecycle | manager C1 and kill | verified |
| `src/fa/session/workspace.py` | A3 | CT1/CT2 provisioner | real Git C1/C3 | verified |
| `src/fa/workspace_bootstrap.py` | A11 | CT3/CT4/CT8 + D27/Q7 | readiness/process/ownership tests | verified |
| `tests/test_authoring_protected_paths_parity.py` | A56 | semantic governance oracle | 2 passed + kill | verified |
| `tests/test_cli.py` | A32 | composition/provider-order proof | focused/full pytest | verified |
| `tests/test_deploy_scripts.py` | A10 | shell/config contracts | focused/full pytest | verified |
| `tests/test_fa_entrypoint.py` | A9 | entrypoint C2 authority | focused/full pytest | verified |
| `tests/test_git_diff_helper.py` | A60 | exact type-safe discovery tests | types/slice tests | verified |
| `tests/test_hygiene_hooks_install.py` | A21 | installer/status/default-path authority | E12 and hook suites | verified |
| `tests/test_hygiene_hooks_self_bootstrap.py` | A20 | real shell/wrapper/stdin authority | E1–E12 suites and kills | verified |
| `tests/test_no_builtin_shadow.py` | A59 | exact annotation correction | full Mypy | verified |
| `tests/test_semgrep_pin.py` | A61 | optional argv narrowing | full types | verified |
| `tests/test_session_lifecycle.py` | A6 | lifecycle/rollback/readiness ordering | C1 and kill | verified |
| `tests/test_session_workspace_provisioning.py` | A5 | CT1/CT2 real Git authority | focused/full pytest | verified |
| `tests/test_slice_mutmut.py` | A46 | CT10–CT12 authority | real tool/config/workflow tests | verified |
| `tests/test_workspace_bootstrap.py` | A13 | CT3/CT4/D27/Q7 authority | closed reasons, process, C1/C3 | verified |
| `tests/test_workspace_bootstrap_aliases.py` | A53 | S4/S6 aliases/docs | 10 passed | verified |
| `tests/test_workspace_readiness_integration.py` | A55 | clean real runtime/publication | real readiness/commit/local bare | verified |
| `worklogs/implementation-plans/PLAN-session-workspace-readiness-bootstrap.md` | A2 | plan/execution authority | Markdown/links/ID aliases | verified |
| `worklogs/implementation-plans/session-workspace-readiness-s1-s6-review.md` | A54 | CT13 review/admission | this file and final gate | verified |

Reviewed unchanged authorities:

- A22 `.vscode/tasks.json`: no diff; SHA-256
  `131731c081feab41378c750db490c80352d1d22d326062bdf43200221953be14`;
- A63 `scripts/check_shell_syntax.sh`: tracked and working mode 0755;
- `.fa/dependency_contract.toml`: ignored-but-tracked authority present in exact
  candidates through selective copy and `git add -f -A`.

## 7. Integrated runtime evidence

A55 uses real Git roots, the checked-out wrapper, actual hook source, real uv,
real readiness, real installed hooks, a second real commit with identity
environment cleared, and a local bare publication rewrite. It does not mock
SessionManager, the entrypoint, wrapper, hook source, or normal Git roots.

Verified runtime state:

```text
branch                  = agent/s65-integration
fetch                   = source file URI (B2-equivalent local authority)
push                    = git@github.com:first-agent-dev/First-Agent-dev.git
identity                = First Agent <agent@first-agent.local>
readiness               = ready_repaired
project environment     = .venv/bin/python exists
hook seats              = four executable seats
second commit           = succeeded with identity environment cleared
publication             = local bare ref equals target HEAD
source                   = HEAD and porcelain status unchanged
provider/model calls     = zero
external pushes          = zero
```

Final post-Q7/E12 exact candidate evidence:

```text
manifest entries         = 791
candidate commit         = 17839d88e4360dfc0139b1042b12a232dbac9f70
shell mode               = 0755
readiness                = ready_repaired in 35.552 s
candidate status         = clean before/after readiness/check
just check               = rc 0; every blocking subgate passed
Mypy                     = 0 issues in 362 files
Pyrefly                   = 0 errors
pytest                    = 2,958 passed, 15 skipped, 1 xfailed in 280.36 s
coverage                  = 84.67%
```

The final report-only admission update is rematerialized once more below so the
exact ALLOW bytes, not this report's prior BLOCK state, receive the clean gate.

## 8. Gate record

| Gate | Result |
| --- | --- |
| E9 affected suites, repeated | 110 passed in 91.08 s; 110 passed in 86.44 s |
| E12 initial affected authority | 150 passed in 83.17 s |
| E12 post-mutation broad authority | 184 passed in 96.45 s |
| Ruff | passed |
| Ruff format | passed; 711 files formatted |
| deptry | no dependency issues |
| pylint gap profile | 10.00/10 |
| full Mypy | zero issues in 362 files |
| full Pyrefly | zero errors |
| dependency/producer/log/no-mock contracts | passed |
| shell syntax | passed |
| uv lock | current |
| plan/S6 Markdown | zero diagnostics |
| internal links | passed |
| CODEOWNERS/TCB parity | passed |
| Git diff integrity | passed |
| final post-E12 exact-candidate `just check` | rc 0; 2,958 passed; 84.67%; clean |

Strict mutation evidence remains truthful:

- S3.5 readiness acceptance: `874 = 329 killed + 540 type-invalid + 5
  equivalent`;
- later S4 readiness scope: `996 = 355 killed + 636 type-invalid + 5 prior
  equivalents`;
- the five equivalents remain visible; no baseline, pragma, allowlist, or
  relabeling was introduced;
- changed E12 ownership branches have direct producer kills below.

## 9. Producer kill ledger

All mutations ran under trap restoration. Each listed source recovered exact
SHA-256 and mode before affected gates reran.

| Producer mutation | Named oracle | Mutant result | Restoration |
| --- | --- | --- | --- |
| remove readiness child `DEVNULL` | child EOF/exact pre-push payload | failed | byte/mode exact |
| remove manager Git dispatch | real manager workspace state | failed | byte/mode exact |
| remove lifecycle readiness call | manager ordering/state | failed | byte/mode exact |
| bypass hook readiness prelude | checked-out wrapper phase | failed | byte/mode exact |
| remove CODEOWNERS runner seat | semantic parity | failed | byte/mode exact |
| remove deptry first-party classification | deptry | rc 1, exactly 12 DEP001 | SHA/mode exact |
| restore transitive `tomli` use | deptry | rc 1, exactly one DEP003 | SHA/mode exact |
| remove Q7 pre-fast ownership check | custom-current fast-path test | READY instead of DEGRADED; failed | SHA/mode exact |
| remove automatic-install ownership preflight | installer delegation test | ownership consumer absent; failed | SHA/mode exact |
| collapse default path into effective path | resolver boundary test | returned operator path; failed | SHA/mode exact |

## 10. Security and failure-boundary assessment

- Git URLs are argv values, normalized through a closed repository shape, and
  unsafe custom values are never serialized raw.
- Readiness private files use no-follow/private-mode/atomic-write contracts.
- Child processes are bounded, captured, noninteractive, and now stdin-closed.
- Bootstrap degradation remains fail-open; real quality failures retain their
  exact nonzero return codes.
- Q7 prevents automatic writes outside the default hook directory and preserves
  unknown executable code rather than chaining or running it.
- Hook-ownership telemetry emits only closed reason/stage values, not custom
  paths or hook content.
- Mutation input, stage, status identity, timeout/process-group cleanup, and
  result artifacts remain strict and isolated.
- Managed clones only are in the guarantee. Arbitrary raw clones remain outside
  it.

No new unowned blocker or unresolved policy question remains after Q7.

## 11. Remaining work with explicit owner

| Item | Why not an S6.5 blocker | Owner |
| --- | --- | --- |
| cold/warm uv and pre-commit latency/disk measurement | S7 is the purpose of the next admitted slice | S7/CT9 |
| persistent cache decision | intentionally evidence-dependent, default defer | Q2 after S7 |
| canonical ADR/README historical corrections | outside bounded S6.5 remediation | S8/T15 |
| actual GitHub feature-branch/PR/CI publication | external side effect prohibited in S6.5 | S9/T16 |
| deployment `/repo` post-publication observation | requires live operator environment | S9 |
| final shipped-feature declaration | requires S9 and operator-controlled merge/deploy | S9/operator |

## 12. Binary decision rule

Change the admission line to `S7_ADMISSION=ALLOW` only if all of the following
are true:

1. the exact post-E12 candidate includes all 52 inventory paths, the dependency
   contract, and executable shell mode;
2. readiness returns `ready_repaired` and leaves the candidate clean;
3. `just check` returns zero with every blocking subgate green;
4. full pytest, full types, authoring, contracts, shell, and dependency gates
   contain no unexplained failure;
5. the candidate remains clean after the gate.

All five conditions are recorded. The binary decision is:

```text
S7_ADMISSION=ALLOW
```
