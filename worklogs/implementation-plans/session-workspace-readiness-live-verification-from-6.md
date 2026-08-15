# Managed workspace readiness — post-merge live verification from §6

Status: **S9.0 LIVE HOTFIX PENDING — mode restored; verifier umask correction next**

Date: 2026-08-14

Parent plan:
[`PLAN-session-workspace-readiness-bootstrap`](./PLAN-session-workspace-readiness-bootstrap.md)

Closure subplan:
[`PLAN-session-workspace-readiness-live-closure`](./PLAN-session-workspace-readiness-live-closure.md)

Current section state:

```text
SECTION_6=PASS
SECTION_7=PASS
CAUSE_STATUS=CACHE_PRIMARY_CONFIRMED
PATCH_STATUS=MERGED_DEPLOYED
MERGED_SHA=33943fa3c21647057bb47b771c9a6997f8683717
MANAGED_WORKSPACE_READINESS_GOAL=VERIFIED
S9_STATUS=PENDING
FEATURE_PRODUCTION_READINESS=UNCLAIMED
```

This sheet begins from the post-merge §6 evidence supplied by the operator and
binds each later claim to fresh live output. It does not treat the provisional
npm patch as applied or approved.

## 0. Revision model

Public `main` at investigation start:

```text
PUBLIC_MAIN_HEAD=e8f7ee5b3bf4e62402dcb8ca35a672939b726fac
```

`e8f7ee5` adds only the tracked reference artifact
`npm-cache-readiness-closure-on-7ba1361.patch`. The operator did not apply that
patch. The deployed runtime is intentionally one commit behind public `main` and
contains the same runtime code as public `main` minus that inert patch file.

Expected live runtime revision:

```text
EXPECTED_RUNTIME_HEAD=7ba13616e3d649c0d593612dc266734e8bccc9fe
```

## 1. S0 identity binding — 2026-08-14

### 1.1 Deployment checkout

```text
DEPLOYMENT_HEAD=7ba13616e3d649c0d593612dc266734e8bccc9fe
DEPLOYMENT_STATUS_HASH=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
DEPLOYMENT_CLEAN=yes
```

### 1.2 Container and image

```text
CONTAINER_ID=f17737fb7a5f23ee0f6984356bf4e8f9b3a2aa440e30c837ccccb93bdbdae67f
CONTAINER_IMAGE_ID=sha256:8f2f655f521ad18961b393027178d7e93989c5c135a4255b2f2d59b802698281
CONTAINER_STARTED_AT=2026-08-13T21:07:30.746505917Z
CONTAINER_STATUS=running
CONTAINER_HEALTH=healthy
IMAGE_ID=sha256:8f2f655f521ad18961b393027178d7e93989c5c135a4255b2f2d59b802698281
IMAGE_REVISION=7ba13616e3d649c0d593612dc266734e8bccc9fe
IMAGE_CREATED_AT=2026-08-14T01:03:53.642080945+04:00
```

Image ID and revision agree with the deployed runtime authority.

### 1.3 Read-only source authority

```text
SOURCE_HEAD=7ba13616e3d649c0d593612dc266734e8bccc9fe
SOURCE_STATUS_HASH=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
SOURCE_CLEAN=yes
```

### 1.4 Active and failed workspace

```text
ACTIVE_WORKSPACE=/sessions/session-20260813T210730-7
ACTIVE_MODE=0644
ACTIVE_MTIME=2026-08-13T21:07:56.083438838Z
FAILED_WORKSPACE=/sessions/session-20260813T210730-7
FAILED_WORKSPACE_HEAD=7ba13616e3d649c0d593612dc266734e8bccc9fe
FAILED_WORKSPACE_STATUS_HASH=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
FAILED_WORKSPACE_CLEAN=yes
```

The active publication occurred approximately 25 seconds after container start.
This timestamp proves only the current startup publication ordering. It does not
prove when Docker health first became green and therefore does not by itself
confirm the previously suspected health/verifier race.

## 2. Historical retained pre-commit log

Expected retained artifact from the prior reproduction:

```text
EXPECTED_LOG_BYTES=672275
EXPECTED_LOG_SHA256=1d9ca6cf756da4d4e77fe37eb154390389636a94ead70f1490e2d6ebf7321065
```

S0 first tested the standard pre-commit error-log location implied by the live
`PRE_COMMIT_HOME` contract:

```text
ATTEMPTED_CONTAINER_LOG=/home/fa/.cache/pre-commit/pre-commit.log
HOST_RETAINED_COPY=/tmp/fa-precommit-retained.log
```

Actual output:

```text
Error response from daemon: Could not find the file
/home/fa/.cache/pre-commit/pre-commit.log in container first-agent

stat: cannot statx '/tmp/fa-precommit-retained.log': No such file or directory
LOG_SIZE_RC=2
sha256sum: /tmp/fa-precommit-retained.log: No such file or directory
/tmp/fa-precommit-retained.log: FAILED open or read
```

This falsifies only the assumed current container path. It does not prove that
the previously reported artifact never existed or that its SHA-256 was wrong.

### 2.1 Exact-size metadata discovery

The operator searched for regular files of exactly `672275` bytes and requested
SHA-256 only for matches. No file content was printed.

```text
SEARCH=host_tmp
RESULT=no accessible candidate
SEARCH_RC=1
LIMITATION=root-owned systemd/snap private directories returned permission denied

SEARCH=container_tmp
RESULT=no candidate
SEARCH_RC=0

SEARCH=container_precommit_cache
RESULT=no candidate
SEARCH_RC=0

SEARCH=host_home
RESULT=no candidate
SEARCH_RC=0

SEARCH=host_sessions
RESULT=no candidate
SEARCH_RC=0

SEARCH=privileged_transient_roots
ROOTS=/tmp,/var/tmp,/root
RESULT=no candidate
SEARCH_RC=0
```

Combined result:

```text
ORIGINAL_RETAINED_LOG_DISCOVERY=NO_MATCH_AFTER_COMPLETE_BOUNDED_SEARCH
ORIGINAL_RETAINED_A=UNAVAILABLE
S0_IDENTITY_STATUS=PASS
S0_LOG_STATUS=UNAVAILABLE
CAUSE_STATUS=UNPROVEN
```

The historical size/SHA remain a prior evidence claim but cannot be current
chain-of-custody authority. Closure plan v4 therefore authorizes exactly one
fresh bounded replacement A after S1 captures environment/mount state. A must
preserve source/workspace Git hashes and reproduce the same pre-commit failure
class before B is allowed.

## 3. S1 live environment and topology — PASS

### 3.1 Runtime identity and environment

```text
RUNTIME_UID=1000
RUNTIME_GID=1000
HOME=/home/fa
PRE_COMMIT_HOME=/home/fa/.cache/pre-commit
NPM_CONFIG_CACHE=<unset>
FA_AUTO_RUN=<unset>
```

All inspected process proxy variables were unset:

```text
HTTP_PROXY=<unset>
HTTPS_PROXY=<unset>
ALL_PROXY=<unset>
NO_PROXY=<unset>
http_proxy=<unset>
https_proxy=<unset>
all_proxy=<unset>
no_proxy=<unset>
```

This eliminates a direct process-environment proxy discrepancy between
entrypoint readiness and the replacement A/B baseline. npm-specific config
(`proxy`, `https-proxy`, registry) remains to be inspected before proxy influence
is fully classified.

### 3.2 Rendered and effective mount contract

Rendered Docker state:

```text
READ_ONLY_ROOT=true
/home/fa/.cache=rw,nosuid,nodev,exec,size=1536m,mode=0700,uid=1000,gid=1000
/home/fa/.local=rw,nosuid,nodev,exec,size=500m,mode=0700,uid=1000,gid=1000
```

Effective state:

```text
ROOT_TARGET=/
ROOT_FSTYPE=overlay
ROOT_OPTIONS=ro,relatime
CACHE_TARGET=/home/fa/.cache
CACHE_FSTYPE=tmpfs
CACHE_OPTIONS=rw,nosuid,nodev,relatime
CACHE_SUPER_OPTIONS=rw,size=1572864k,mode=700,uid=1000,gid=1000,inode64
CACHE_NOEXEC=no
```

### 3.3 Actual write behavior and errno

Exact default npm path creation:

```text
mkdir: cannot create directory '/home/fa/.npm': Read-only file system
HOME_NPM_MKDIR_RC=1
```

Writable cache sibling:

```text
CACHE_WRITE_RC=0
```

Capacity at measurement:

```text
CACHE_TOTAL_BYTES=1610612736
CACHE_USED_BYTES=35545088
CACHE_AVAILABLE_BYTES=1575067648
CACHE_USE_PERCENT=3
```

This directly confirms the filesystem mechanism:

- `/home/fa/.npm` cannot be created because the root mount is read-only;
- `/home/fa/.cache` is writable and has ample measured headroom.

It does not yet explain why npm historically reported `ENOENT` rather than the
shell's `EROFS` wording. Replacement-A chronology and the failed Node runtime's
own mkdir result remain required.

### 3.4 Preservation

```text
SOURCE_HEAD=7ba13616e3d649c0d593612dc266734e8bccc9fe
SOURCE_STATUS_HASH=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
WORKSPACE_HEAD=7ba13616e3d649c0d593612dc266734e8bccc9fe
WORKSPACE_STATUS_HASH=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
SOURCE_CLEAN=yes
WORKSPACE_CLEAN=yes
```

### 3.5 S1 disposition

```text
S1_STATUS=PASS
GAP4_FILESYSTEM_BOUNDARY=CONFIRMED
PROCESS_ENV_PROXY_DISCREPANCY=NOT_PRESENT
CACHE_CAPACITY_EXHAUSTED=no
CAUSE_STATUS=UNPROVEN
```

## 4. Confirmed facts versus unresolved hypotheses

### Confirmed

- deployed runtime, image label, `/repo`, and failed workspace use `7ba1361`;
- deployment, `/repo`, and failed workspace are clean;
- public `main` differs only by the un-applied reference patch artifact;
- current `.active` selects the expected failed workspace;
- the historical retained artifact is unavailable after complete bounded search;
- runtime npm cache override is unset;
- all inspected environment proxy variables are unset;
- `/home/fa/.npm` creation fails on the read-only root;
- `/home/fa/.cache` is writable and has 1,575,067,648 bytes available;
- no npm or pre-commit operation was run during S0/S1.

### Still hypotheses

- npm's effective cache is `/home/fa/.npm`;
- inability to use that path is the primary prewarm failure;
- tarball warnings are secondary to cache failure;
- npm-specific proxy/registry configuration is or is not material;
- npm's ENOENT is compatible with the direct shell/Node errno path;
- the historical §7B/§7C workspace change was caused by health/publication
  timing.

## 5. Next bounded action

Run exactly one replacement A under the unchanged environment:

```text
NEXT=S2_REPLACEMENT_A_CAPTURE
REPLACEMENT_A_AUTHORIZED=yes
REPLACEMENT_A_MAX_RUNS=1
NPM_CONFIG_CACHE=<unset>
SOURCE_MUTATION=none
SESSION_GIT_MUTATION=none
```

Operator command-delivery decision:

```text
COMMAND_DELIVERY=ONE_COPY_PASTEABLE_BASH_BLOCK_PER_STAGE
HEREDOC=forbidden
PER_OPERATION_TIMEOUT=required
STAGE_BLOCK_PREFIX=set_+e
EXPECTED_NONZERO=capture_before_decision
UNEXPECTED_NONZERO=stop_stage
```

## 6. S2A replacement control capture

The first combined S2A block inherited shell `errexit` because it enabled
`nounset` but did not explicitly disable an existing `errexit` setting. The
expected nonzero pre-commit command therefore ended the wrapper before its exact
outer rc was printed. The operation itself ran and produced a bounded host log.

```text
A_STDOUT=/tmp/fa-precommit-a-replacement.log
A_STDOUT_BYTES=336511
A_STDOUT_MODE=0644
A_STDOUT_MTIME=2026-08-14T15:45:57.573114193+04:00
A_STDOUT_SHA256=bbab5beae4331ee979b11ce1b490797b6422b7a3ea636821522539996ab58689
A_OUTER_RESULT=nonzero
A_OUTER_RC_EXACT=<lost_by_wrapper>
A_RERUN_ALLOWED=no
```

The internal pre-commit log became visible through `docker exec test -f`, but
`docker cp` could not archive the tmpfs-mounted path:

```text
CONTAINER_INTERNAL_LOG_PRESENT=yes
DOCKER_CP_RC=1
DOCKER_CP_ERROR=container_path_not_found_by_copy_transport
```

This is a copy-transport/path-visibility discrepancy, not evidence that the
in-container `test -f` was false. S2B uses `docker exec cat` with a host redirect
and an external timeout.

Post-A safety evidence:

```text
CHILD_PROCESS_REMAINS=no
HOME_NPM_EXISTS=no
NPM_OVERRIDE_CACHE_EXISTS=no
CACHE_AVAILABLE_BYTES=1575063552
SOURCE_HEAD=7ba13616e3d649c0d593612dc266734e8bccc9fe
SOURCE_STATUS_HASH=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
WORKSPACE_HEAD=7ba13616e3d649c0d593612dc266734e8bccc9fe
WORKSPACE_STATUS_HASH=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

Classification:

```text
S2A_EXECUTED=yes
S2A_CAPTURE_PRESENT=yes
S2A_EXACT_OUTER_RC_BOUND=no
S2A_GIT_PRESERVATION=PASS
S2A_RERUN_FORBIDDEN=yes
CAUSE_STATUS=UNPROVEN
NEXT=S2B_INTERNAL_COPY_AND_CHRONOLOGY
```

S2B recovered the detailed internal log through `docker exec cat`; no A rerun
was performed.

The first S3.1 command block later exited with wrapper code `1`. Its complete
terminal output was not retained in this conversation, so the failing label is
unknown. No conclusion is drawn about npm config, proxy config, Node errno, or
cache micro-A/B from that wrapper rc. Before any npm command is repeated, a
non-mutating inspection records whether S3.1 created `.npm`, `npm-probe`, left a
child process, or changed source/workspace Git state.

```text
S3_1_WRAPPER_RC=1
S3_1_FAILING_LABEL=<unknown>
S3_1_RESULTS_BOUND=no
S3_1_TERMINAL_WINDOW_CLOSED_BY_TOP_LEVEL_EXIT=yes
NPM_RERUN_AUTHORIZED=no
CAUSE_STATUS=UNPROVEN
NEXT=S3_1_SIDE_EFFECT_INSPECTION_IN_SUBSHELL
```

## 7. S2B exact command and failure chronology — PASS

### 7.1 Evidence artifacts

```text
A_STDOUT=/tmp/fa-precommit-a-replacement.log
A_STDOUT_BYTES=336511
A_STDOUT_SHA256=bbab5beae4331ee979b11ce1b490797b6422b7a3ea636821522539996ab58689
A_INTERNAL=/tmp/fa-precommit-a-internal-recovery.log
A_INTERNAL_BYTES=674689
A_INTERNAL_SHA256=83fa2e3babf5023c217b48a4086d2ba0f102bf3b48f03e3b21b1b5a2086da82a
INTERNAL_EQUALS_STDOUT=no
PRIMARY_DETAIL_LOG=A_INTERNAL
TOTAL_DETAIL_LINES=2747
```

The internal log is larger because it includes pre-commit version/system/error
metadata and complete child stderr. It is the chronology authority for A.

### 7.2 Return-code layers

The original entrypoint bootstrap record remains present in the failed
workspace:

```json
{"argv":[".venv/bin/pre-commit","install-hooks"],"elapsed_ms":24219,"reason_code":"precommit_prewarm_failed","return_code":3,"stage":"precommit_prewarm","status":"degraded_environment","timestamp":"2026-08-13T21:07:56.062997Z","workspace":"/sessions/session-20260813T210730-7"}
```

Replacement A's detailed child failure:

```text
PRECOMMIT_VERSION=4.6.0
GIT_VERSION=2.43.0
PROJECT_PYTHON=3.13.15
NODE_VERSION=26.7.0
NPM_VERSION=11.19.0
NPM_CHILD_RETURN_CODE=254
REPLACEMENT_A_OUTER_RESULT=nonzero
REPLACEMENT_A_OUTER_RC_EXACT=<lost_by_wrapper>
```

The outer readiness child rc `3` and inner npm child rc `254` are different
layers and must not be conflated. The current replacement's exact outer value is
not reconstructed; its nonzero result and detailed npm failure are preserved.

### 7.3 Exact npm command

```text
/home/fa/.cache/pre-commit/repokdu__ovx/node_env-default/bin/node
/home/fa/.cache/pre-commit/repokdu__ovx/node_env-default/bin/npm
install
--include=dev
--include=prod
--ignore-prepublish
--no-progress
--no-save
```

This independently rejects the old generic classifier:

```text
MISSING_EXECUTABLE_CLASSIFIER=FALSE_POSITIVE
NPM_EXECUTED=yes
NODE_EXECUTED=yes
```

### 7.4 Ordered failure sequence

```text
LINE_20=npm warning: --ignore-prepublish will be unsupported in a future npm
LINE_21=EBADENGINE warning begins
NODE_CURRENT=26.7.0
AVA_SUPPORTED_NODE=^18.18 || ^20.8 || ^21 || ^22
LINE_26=first tarball-corruption warning
TARBALL_WARNING_LINES=2632
LINE_1342=first TAR_ENTRY_ERROR ENOENT under node_modules extraction
LINE_1353=npm error code ENOENT
LINE_1354=npm error syscall mkdir
LINE_1355=npm error path /home/fa/.npm
LINE_1356=npm errno -2
LINE_1357=ENOENT mkdir /home/fa/.npm
FINAL=npm could not write logs under /home/fa/.npm/_logs
NPM_ERROR_LINES=18
ENOENT_LINES=26
EROFS_LINES=0
EACCES_LINES=0
```

The tarball warnings precede the terminal error. Their scale across thousands of
different package tarballs is inconsistent with a single corrupt package, but
network/content failure is not yet formally excluded. The terminal npm error is
creation of the default cache/log root `/home/fa/.npm`.

The Node/npm version warning is non-terminal in A. Exact B must determine whether
it remains only a warning once cache placement is corrected.

### 7.5 S2 disposition

```text
S2_STATUS=PASS_CHRONOLOGY_BOUND
NPM_TERMINAL_FAILURE=mkdir_/home/fa/.npm
NPM_CHILD_RC=254
PRECOMMIT_BOOTSTRAP_RC=3
MISSING_EXECUTABLE=false
TARBALL_PRIMARY=<unproven>
CACHE_PRIMARY=<strongly_supported_not_yet_proven>
A_RERUN_FORBIDDEN=yes
CAUSE_STATUS=UNPROVEN
NEXT=S3_NPM_CONFIG_NODE_ERRNO_CACHE_MICRO_AB
```

## 8. S3.1 failed collector side-effect inspection

The first S3.1 collector closed the operator shell before its stage output was
retained. A subshell-isolated recovery then completed with block rc `0` and
confirmed:

```text
DEFAULT_CACHE_VERIFY_LOG_PRESENT=no
OVERRIDE_CACHE_VERIFY_LOG_PRESENT=no
HOME_NPM_PRESENT=no
NPM_CANDIDATE_CACHE_PRESENT=no
NPM_PROBE_CACHE_PRESENT=no
PRECOMMIT_INTERNAL_LOG_PRESENT=yes
PRECOMMIT_INTERNAL_LOG_BYTES=674689
CHILD_PROCESS_REMAINS=no
SOURCE_HEAD=7ba13616e3d649c0d593612dc266734e8bccc9fe
SOURCE_STATUS_HASH=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
WORKSPACE_HEAD=7ba13616e3d649c0d593612dc266734e8bccc9fe
WORKSPACE_STATUS_HASH=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

The failed block did not reach cache verify and left no cache or Git mutation.
Filesystem state cannot identify which earlier config/version/Node subprobe
failed. Repeating only those idempotent observations is authorized; npm install,
pre-commit, cache verify, and exact B remain blocked.

```text
S3_1_SIDE_EFFECT_INSPECTION=PASS
S3_1_RESULTS_BOUND=no
SAFE_REPEAT_SCOPE=versions,npm_config_get,node_mkdir_failure
CACHE_VERIFY_AUTHORIZED=no
EXACT_B_AUTHORIZED=no
CAUSE_STATUS=UNPROVEN
NEXT=S3_1_COLLECTION_ONLY_RECOVERY
```

## 9. S3.1 collection-only recovery — failed Node environment cleaned

```text
FAILED_REPO=/home/fa/.cache/pre-commit/repokdu__ovx
FAILED_REPO_PRESENT=yes
FAILED_NODE_BIN=/home/fa/.cache/pre-commit/repokdu__ovx/node_env-default/bin/node
FAILED_NPM_BIN=/home/fa/.cache/pre-commit/repokdu__ovx/node_env-default/bin/npm
FAILED_NODE_BIN_PRESENT=no
FAILED_NPM_BIN_PRESENT=no
NODE_EXECUTABLE_RC=1
NPM_EXECUTABLE_RC=1
NODE_VERSION_RC=127
NPM_VERSION_RC=127
ALL_NPM_CONFIG_GET_RC=127
NODE_MKDIR_PROBE_RC=127
HOME_NPM_PRESENT=no
NPM_CANDIDATE_CACHE_PRESENT=no
NPM_PROBE_CACHE_PRESENT=no
SOURCE_STATUS_HASH=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
WORKSPACE_STATUS_HASH=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
COLLECTOR_BLOCK_RC=0
PARENT_BASH_STILL_OPEN=yes
```

CT2 proves these exact binaries executed during A and npm returned child rc
`254`. Their post-failure absence is therefore pre-commit cleanup, not the
original failure. No system npm or another cached Node environment may be used as
a substitute.

```text
MISSING_EXECUTABLE_AT_FAILURE=false
FAILED_NODE_ENV_CLEANED_AFTER_FAILURE=true
PRE_B_CONFIG_PROBES=unavailable_by_lifecycle
CACHE_VERIFY_PRE_B=not_run
EXACT_B_AUTHORIZED=yes
POST_B_CONFIG_PROBES=required_if_B_succeeds
CAUSE_STATUS=UNPROVEN
NEXT=S4_EXACT_B
```

## 10. S4 exact cache-override B — PASS

### 10.1 Controlled preconditions

```text
CONTAINER_ID=f17737fb7a5f23ee0f6984356bf4e8f9b3a2aa440e30c837ccccb93bdbdae67f
IMAGE_ID=sha256:8f2f655f521ad18961b393027178d7e93989c5c135a4255b2f2d59b802698281
IMAGE_REVISION=7ba13616e3d649c0d593612dc266734e8bccc9fe
ACTIVE_WORKSPACE=/sessions/session-20260813T210730-7
NPM_CONFIG_CACHE_BEFORE=<unset>
FA_AUTO_RUN=<unset>
PROCESS_PROXY_VARIABLES=all_unset
SOURCE_STATUS_HASH_BEFORE=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
WORKSPACE_STATUS_HASH_BEFORE=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
CHILD_PROCESS_BEFORE=no
CANDIDATE_CACHE_BEFORE=absent
```

The only intentional B change was command-local:

```text
NPM_CONFIG_CACHE=/home/fa/.cache/npm
```

### 10.2 Exact operation and result

```text
COMMAND=.venv/bin/pre-commit install-hooks
WORKSPACE=/sessions/session-20260813T210730-7
B_RC=0
B_STDOUT=/tmp/fa-precommit-b.log
B_STDOUT_BYTES=514
B_STDOUT_MODE=0600
B_STDOUT_SHA256=2c8306e6d5928f7ebd1e06b1a135450af22aa74544c76c592f963d5c65a45d02
B_TARBALL_WARNING_COUNT=0
B_NPM_ERROR_COUNT=0
```

B eagerly installed:

```text
https://github.com/igorshubovych/markdownlint-cli
https://github.com/gitleaks/gitleaks
https://github.com/astral-sh/uv-pre-commit
```

The historical internal A error log remained unchanged after B:

```text
B_INTERNAL_SHA256=83fa2e3babf5023c217b48a4086d2ba0f102bf3b48f03e3b21b1b5a2086da82a
B_INTERNAL_EQUALS_A_INTERNAL=yes
```

A successful pre-commit run does not clear the historical error log. Its mere
presence is not a current readiness oracle.

### 10.3 Retained environment and cache

```text
HOME_NPM_PRESENT=no
CANDIDATE_CACHE=/home/fa/.cache/npm
CANDIDATE_CACHE_PRESENT=yes
CANDIDATE_CACHE_MODE=0755
NODE_BIN_PRESENT=yes
NODE_BIN_BYTES=147870928
NPM_BIN_PRESENT=yes
NPM_BIN_TYPE=symlink
CACHE_TOTAL_BYTES=1610612736
CACHE_USED_BYTES=934731776
CACHE_AVAILABLE_BYTES=675880960
CACHE_USE_PERCENT=59
```

The 1536 MiB tmpfs remains within capacity with approximately 645 MiB available
after eager preparation.

### 10.4 Preservation

```text
CHILD_PROCESS_AFTER=no
SOURCE_HEAD=7ba13616e3d649c0d593612dc266734e8bccc9fe
SOURCE_STATUS_HASH_AFTER=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
WORKSPACE_HEAD=7ba13616e3d649c0d593612dc266734e8bccc9fe
WORKSPACE_STATUS_HASH_AFTER=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

### 10.5 Causal decision

```text
CAUSE_STATUS=CACHE_PRIMARY_CONFIRMED
A_TERMINAL=npm_child_254_mkdir_/home/fa/.npm
A_TARBALL_WARNING_LINES=2632
B_RC=0
B_TARBALL_WARNING_LINES=0
B_NPM_ERROR_LINES=0
ONLY_INTENTIONAL_CHANGE=NPM_CONFIG_CACHE
TARBALL_NETWORK_PRIMARY=false
PROXY_PRIMARY=false
MISSING_EXECUTABLE_PRIMARY=false
NODE_ENGINE_WARNING_TERMINAL=false
PATCH_MECHANISM=APPROVED_PENDING_POST_B_CONTRACT_COMPLETION
SECTION_7=DEGRADED
```

The A/B proves the cache path is causal. The tarball warnings were non-primary
symptoms of the failing npm/cache/extraction path: with identical live network,
registry, package inputs, container, workspace, and pre-commit store, changing
only the npm cache root removed every warning/error and completed all eager
environments.

Direct B does not write the readiness marker or sentinel. A recreated deployment
with the patch must still pass §7 before later parent work can begin.

```text
NEXT=S4_1A_POST_B_CONFIG_AND_NODE_ERRNO
```

## 11. S4.1a partial — Node errno closed, npm config invocation corrected

The successful B environment remains present and writable:

```text
NODE_BIN_PRESENT=yes
NODE_BIN_EXECUTABLE=yes
NPM_BIN_PRESENT=yes
NPM_BIN_TYPE=symlink
CANDIDATE_CACHE_PRESENT=yes
CANDIDATE_CACHE_WRITABLE=yes
NODE_VERSION=v26.7.0
```

Direct Node recursive mkdir produced:

```json
{"result":"error","code":"ENOENT","errno":-2,"syscall":"mkdir","path":"/home/fa/.npm"}
```

This matches npm's terminal code/errno/syscall/path exactly. The errno question is
closed: shell/coreutils reported read-only filesystem wording, while the exact
Node v26 filesystem API used by npm surfaced `ENOENT/-2` for recursive mkdir.
The npm error was primary cache-path failure, not merely a secondary log-write
error.

Direct execution of the npm symlink returned:

```text
NPM_DIRECT_EXEC_RC=127
/usr/bin/env: 'node': No such file or directory
```

This is a probe calling-convention defect. The A log shows pre-commit's actual
argv explicitly invokes the environment Node binary followed by the npm script.
The corrected config probe must use:

```text
NODE_BIN NPM_BIN config get <key>
```

No cache/config conclusion is drawn from the direct-symlink rc `127`.

Preservation remained exact:

```text
HOME_NPM_PRESENT=no
CANDIDATE_CACHE_PRESENT=yes
SOURCE_STATUS_HASH=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
WORKSPACE_STATUS_HASH=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
CACHE_AVAILABLE_BYTES=675880960
```

```text
NODE_ERRNO_CONTRACT=PASS
NPM_CONFIG_CONTRACT=pending_corrected_invocation
CACHE_VERIFY_REQUIRED=no
CAUSE_STATUS=CACHE_PRIMARY_CONFIRMED
NEXT=S4_1A_CORRECTED_NPM_CONFIG
```

## 12. S4.1a corrected npm config/calling convention — PASS

The npm script is a symlink to `npm-cli.js` with `#!/usr/bin/env node`, while the
pre-commit Node bin directory is not on normal Docker-exec PATH. Direct symlink
execution therefore returned 127, but pre-commit's actual explicit Node+script
calling convention succeeds.

```text
NODE_EXECUTABLE_RC=0
NPM_PRESENT_RC=0
NPM_LINK_TARGET=../lib/node_modules/npm/bin/npm-cli.js
NPM_RESOLVED=/home/fa/.cache/pre-commit/repokdu__ovx/node_env-default/lib/node_modules/npm/bin/npm-cli.js
NPM_SCRIPT_SHEBANG=#!/usr/bin/env node
NODE_ENV_BIN_ON_PATH=no
NODE_VERSION=v26.7.0
NPM_VERSION=11.19.0
```

Exact config through `NODE_BIN NPM_BIN config get ...`:

```text
CACHE_DEFAULT=/home/fa/.npm
CACHE_OVERRIDE=/home/fa/.cache/npm
NPM_PROXY=<none>
NPM_HTTPS_PROXY=<none>
NPM_NOPROXY=<none>
NPM_REGISTRY=https://registry.npmjs.org/
NPM_STRICT_SSL=true
```

This closes the proxy/config alternatives. The exact Node errno from §11 remains:

```text
NODE_MKDIR_CODE=ENOENT
NODE_MKDIR_ERRNO=-2
NODE_MKDIR_SYSCALL=mkdir
NODE_MKDIR_PATH=/home/fa/.npm
```

Final state remained preserved:

```text
HOME_NPM_PRESENT=no
CANDIDATE_CACHE_PRESENT=yes
SOURCE_HEAD=7ba13616e3d649c0d593612dc266734e8bccc9fe
SOURCE_STATUS_HASH=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
WORKSPACE_HEAD=7ba13616e3d649c0d593612dc266734e8bccc9fe
WORKSPACE_STATUS_HASH=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
CACHE_USED_BYTES=934735872
CACHE_AVAILABLE_BYTES=675876864
```

```text
S4_1A_STATUS=PASS
CAUSE_STATUS=CACHE_PRIMARY_CONFIRMED
PROXY_PRIMARY=false
REGISTRY_PRIMARY=false
ERRNO_SEMANTICS=EXPLAINED_BY_EXACT_NODE_RUNTIME
PATCH_MECHANISM=APPROVED
S6_ADMISSION=ALLOW
SECTION_7=DEGRADED
NEXT=S6_IMPLEMENTATION
```

## 13. S6 local repair candidate

Implemented mechanism:

```text
Dockerfile.fa: NPM_CONFIG_CACHE=/home/fa/.cache/npm
docker-compose.fa.yml: exact production env
fa-update/fa-clean-rebuild/fa-post-setup: exact path + mkdir + rw/x checks
container-build CI: real current-source clone + hard read-only READY check
```

CI fixture correction:

- the current checkout is cloned with object-file links disabled using the
  exact command pinned in workflow/tests;
- canonical SSH origin is restored and source read/traverse bits are guaranteed;
- source is bind-mounted read-only without ownership changes;
- session/state roots are private bounded uid/gid-1000 tmpfs mounts;
- container removal automatically discards writable roots;
- entrypoint performs cold readiness before the checker;
- checker JSON is visible and any nonzero rc blocks CI;
- CI does not fabricate npm directories or markers.

Strict review and Q4 no-sudo hardening:

- every workflow YAML is rejected if it contains sudo;
- source destination must be absent before clone;
- source remains runner-owned, read/traverse-only to uid 1000, and bind-mounted
  read-only;
- `/sessions` is bounded executable uid-1000 tmpfs;
- `/home/fa/.fa` is bounded noexec uid-1000 tmpfs;
- host session/state writable binds, chown, cleanup traps, and privileged repair
  are absent;
- npm deploy producers are unique and ordered before executable cache probes;
- no documentation allowlist/test weakening was used.

Local verification:

```text
TARGETED_PYTEST=134_passed_12_capability_skips
YAML_PARSE=PASS
SHELL_SYNTAX=PASS
PY_COMPILE=PASS
DOC_LINKS=PASS
TARGETED_MUTATIONS=9_current_producers_killed_0_survived
REAL_SOURCE_CLONE=PASS
REAL_SOURCE_CHECK=locked_check_failed_rc75
EMPTY_SOURCE_CHECK=invalid_workspace_rc70
EXTERNAL_PATCH_BASE=e8f7ee5b3bf4e62402dcb8ca35a672939b726fac
EXTERNAL_PATCH_PATHS=13
CLEAN_CLONE_RC=0
APPLY_CHECK_RC=0
APPLY_RC=0
APPLIED_DIFF_CHECK_RC=0
APPLIED_TARGETED_TESTS=134_passed_12_capability_skips
APPLIED_DOC_LINKS=219_files_0_broken
```

The real-source rc 75 is expected before entrypoint readiness and proves the
fixture is a valid First-Agent checkout rather than the old empty repository.
The blocking Docker job remains the C2 authority and is pending GitHub execution.

Unavailable sandbox gates:

```text
DOCKER_C2=unavailable_no_daemon
JUST_CHECK=unavailable_no_uv_or_just
RUFF=unavailable
MYPY=unavailable
PYREFLY=unavailable
```

No threshold, skip, ignore, hook revision, cache capacity, persistent mount,
runtime fail-open policy, or readiness-engine code changed.

```text
CAUSE_STATUS=CACHE_PRIMARY_CONFIRMED
PATCH_STATUS=DELIVERY_READY_CLEAN_APPLY_TARGETED_GREEN
SECTION_7=DEGRADED
GITHUB_CI=PENDING
HUMAN_MERGE=PENDING
RECREATED_DEPLOYMENT=PENDING
FEATURE_PRODUCTION_READINESS=UNCLAIMED
NEXT=S7_1_EXTERNAL_PATCH_AND_OPERATOR_PR
```

## 14. Recreated deployment §7 — PASS

Merged/deployed authority:

```text
MERGED_SHA=33943fa3c21647057bb47b771c9a6997f8683717
DEPLOYMENT_HEAD=33943fa3c21647057bb47b771c9a6997f8683717
IMAGE_ID=sha256:50ee3a6030338af2cdcbe5bcb238d507da8b78db31141885efb20cb8571f3100
IMAGE_REVISION=33943fa3c21647057bb47b771c9a6997f8683717
CONTAINER_ID=402034445edc94e377b1a5e3ea5e44b5ad366b8ba3fc989f3edf4e8b29212d5a
CONTAINER_STARTED_AT=2026-08-14T14:22:37.352436815Z
AGENT_HEALTH=healthy
PROXY_HEALTH=healthy
DEPLOYMENT_STATUS_HASH=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
SOURCE_STATUS_HASH=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

Image/source byte parity:

```text
WORKSPACE_BOOTSTRAP_SHA=b8c390fc15e076a62af35851c14ca6bb0d34410a764f6d4ed89b3417fa6fe56b
ENTRYPOINT_SHA=5f12d02f1de5e686bddc9e35dd885f396370f400d9bac71d3a648edaab61c65c
IMAGE_SOURCE_PARITY=PASS
```

Runtime topology:

```text
RUNTIME_UID_GID=1000:1000
HOME=/home/fa
PRE_COMMIT_HOME=/home/fa/.cache/pre-commit
NPM_CONFIG_CACHE=/home/fa/.cache/npm
FA_AUTO_RUN=<unset>
ROOT=overlay_ro
HOME_CACHE=tmpfs_rw_exec_1536m_uid1000_gid1000
HOME_LOCAL=tmpfs_rw_exec_500m_uid1000_gid1000
TMP=tmpfs_rw_noexec
UV_CACHE=tmpfs_rw_noexec
```

PID1 publication:

```text
PID1_CREATED_COUNT=1
PID1_WORKSPACE=/sessions/session-20260814T142237-7
ACTIVE_WORKSPACE=/sessions/session-20260814T142237-7
CONTAINER_STARTED_EPOCH=1786717357.352436
ACTIVE_MTIME_EPOCH=1786717420.9705675
ACTIVE_DELAY_SECONDS=63.6181315
PID1_ACTIVE_BINDING=PASS
```

The approximately 63.6-second delay demonstrates why health or an old `.active`
value cannot be the verifier authority. This run bound the exact PID1 workspace;
it does not independently identify the timestamp of the first successful Docker
health probe.

Managed Git contract:

```text
BRANCH=agent/session-20260814T142237-7
FETCH=file:///repo
PUSH=git@github.com:first-agent-dev/First-Agent-dev.git
IDENTITY=First Agent <agent@first-agent.local>
WORKSPACE_STATUS_HASH=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

Readiness contract:

```text
HOOKS_EXECUTABLE=4
READY_RC=0
READY_STATUS=ready
READY_REASON=ready_fast_path
READY_REPAIRED=false
READY_CHECK_ELAPSED_MS=59
FINGERPRINT=sha256:87010a40d580fbc8f21a97e2aa4578329dd4cd84a6ceddd3d6019af74469ae4c
MARKER_MODE=0600
MARKER_BEFORE_ACTIVE=yes
SENTINEL_OK=yes
```

Final preservation:

```text
SOURCE_HEAD_AFTER=33943fa3c21647057bb47b771c9a6997f8683717
SOURCE_STATUS_AFTER=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
DEPLOYMENT_HEAD_AFTER=33943fa3c21647057bb47b771c9a6997f8683717
DEPLOYMENT_STATUS_AFTER=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
PROVIDER_MODEL_CALLS=0
```

Binary result:

```text
SECTION_7=PASS
S9_STATUS=PENDING
FEATURE_PRODUCTION_READINESS=UNCLAIMED
NEXT=FRESH_LOGICAL_SESSION_PROOF
```

## 15. Fresh logical managed session — PASS

The verifier first repeated recreated §7 and received the same merged/image/
source/topology/readiness/preservation result. Warm startup-workspace check was
`ready_fast_path` in 54 ms with the same fingerprint.

The shipped CLI lifecycle factory then created a new logical session with no
explicit selector and stopped before run/provider construction:

```text
CONTAINER_ID=402034445edc94e377b1a5e3ea5e44b5ad366b8ba3fc989f3edf4e8b29212d5a
EXPECTED_SHA=33943fa3c21647057bb47b771c9a6997f8683717
PID1_WORKSPACE=/sessions/session-20260814T142237-7
SESSION_ID=session-fba3e51dcae249efbcd2d5c7dd95e7b6
SESSION_WORKSPACE=/sessions/session-fba3e51dcae249efbcd2d5c7dd95e7b6
CREATED_NOW=true
RECOVERED_PENDING=false
VERIFY_RECORD=/home/fa/.fa/live-verification/fresh-session-402034445edc.json
CREATE_OR_ATTACH_RC=0
```

Session authority was created without beginning a run:

```text
MANIFEST_STATUS=active
EVENT_COUNT=0
RUN_BINDING_COUNT=0
PROVIDER_MODEL_CALLS=0
```

The new session did not replace the PID1 startup selector:

```text
ACTIVE_BEFORE=/sessions/session-20260814T142237-7
ACTIVE_AFTER=/sessions/session-20260814T142237-7
ACTIVE_UNCHANGED=yes
NEW_WORKSPACE_DIFFERS_FROM_PID1=yes
```

Managed Git/readiness contract:

```text
BRANCH=agent/session-fba3e51dcae249efbcd2d5c7dd95e7b6
FETCH=file:///repo
PUSH=git@github.com:first-agent-dev/First-Agent-dev.git
IDENTITY=First Agent <agent@first-agent.local>
READY_RC=0
READY_STATUS=ready
READY_REASON=ready_fast_path
READY_CHECK_ELAPSED_MS=57
FINGERPRINT=sha256:87010a40d580fbc8f21a97e2aa4578329dd4cd84a6ceddd3d6019af74469ae4c
FRESH_SESSION_READINESS=PASS
```

The verifier also required executable project Python, four hook seats, no copied
`.env.fa`, canonical manifest/DB paths and private modes, and clean workspace
status; any mismatch would have failed before the PASS token.

Final preservation:

```text
SOURCE_HEAD=33943fa3c21647057bb47b771c9a6997f8683717
SOURCE_STATUS_HASH=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
DEPLOYMENT_HEAD=33943fa3c21647057bb47b771c9a6997f8683717
DEPLOYMENT_STATUS_HASH=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

Binary result:

```text
FRESH_SESSION_PROOF=PASS
MANAGED_WORKSPACE_READINESS_GOAL=VERIFIED
S9_STATUS=PENDING
FEATURE_PRODUCTION_READINESS=UNCLAIMED
NEXT=DISPOSABLE_COMMIT_PROOF
```

## 16. S9.0 prepare-hook and locked-CI repair candidate — PASS LOCAL

The v30 remaining-contract review invalidated the old next action before the
retained fresh session was mutated. Real Git reports `message` for `-m`, `-F`,
and `-F -`, and reports no source argument for a normal editor-driven commit.
The shipped prepare hook skipped all of those paths, while its test forced the
non-Git value `hook`.

Bounded repair:

- empty `COMMIT_SOURCE` now reaches the existing `fa.hygiene prepare` producer;
- authored/generated message sources retain their compatibility skip;
- a real-Git C2 test requires the editor to observe generated headers, then
  requires one prepare and one commit-msg validation call, one proof file, valid
  metadata/trailer, and a clean tree;
- all seven workflow dependency-sync producers use `uv sync --locked --extra
  dev`;
- repository-wide workflow authority rejects frozen or non-locked sync lines.

Focused and static evidence:

```text
HOOK_TESTS=26_passed
AFFECTED_TESTS_INITIAL=228_passed_12_shellcheck_skipped
AFFECTED_TESTS_FINAL=240_passed
RUFF_CHECK=PASS
RUFF_FORMAT=PASS
MYPY=PASS_no_issues_2_files
PYREFLY=PASS_0_errors
WORKFLOW_YAML_PARSE=PASS
SHELL_SYNTAX=PASS
GIT_DIFF_CHECK=PASS
```

Clean candidate authority:

```text
BASE_SHA=33943fa3c21647057bb47b771c9a6997f8683717
REMOTE_MAIN_AT_BUILD=33943fa3c21647057bb47b771c9a6997f8683717
CANDIDATE_PATHS=10
TRACKED_ROOT_SCRIPTS=3_mode_0755
PATCH_DIGEST_AUTHORITY=external_sidecar
JUST_CHECK_RC=0
JUST_CHECK_GATES=lock,lint,mypy,pyrefly,authoring,contracts,shell,test
FULL_PYTEST_INITIAL=2987_passed_14_skipped_1_xfailed
FULL_PYTEST_FINAL=2999_passed_2_skipped_1_xfailed
COVERAGE=84.68_percent
FULL_GATE_STATUS=PASS
```

Negative proof:

```text
PREPARE_EMPTY_SOURCE_MUTATION_RC=1
PREPARE_MUTATION_SURVIVED=no
PREPARE_RESTORED=yes
WORKFLOW_FROZEN_MUTATION_RC=1
WORKFLOW_MUTATION_SURVIVED=no
WORKFLOW_RESTORED=yes
TARGETED_MUTATIONS=2
SURVIVED=0
```

The apply, independent verifier, and sandbox test scripts are executable tracked
files at repository root with byte-identical external bootstrap copies. Exact
patch bytes are verified through an automatically discovered external
`.sha256` sidecar, avoiding an impossible self-referential embedded patch hash.
The root scripts were syntax-checked, ShellChecked, and exercised over real
temporary Git repositories with shadow external tools:

```text
SCRIPT_TEST_CASES=13
CASES=apply-success,apply-idempotent,apply-interrupted-recovery,verify-success,verify-timeout,wrong-base,dirty,deployment,patch-sha,patch-sha-file,patch-sha-symlink,patch-symlink,verify-diff
S9_REPAIR_SCRIPT_TESTS=PASS
SCRIPT_TEST_STDERR_BYTES=0
TRACKED_EXTERNAL_SCRIPT_PARITY=PASS
```

The first proposed repair probe correctly failed its clean-tree oracle because
the synthetic baseline left setup files untracked; the fixture was rebuilt and
passed. The first script test failed on a dependent same-line Bash `local`
assignment under `set -u`; it was split and rerun. A later patch-symlink fixture
collision produced false setup noise, was rejected, renamed, and rerun with zero
stderr. Once scripts became tracked, a broad `git apply --intent-to-add` trial
rewrote the available Git index as staged deletions; the exact-diff gate blocked
it. Delivery now uses plain `git apply` plus `git add -N --` on the exact three
new script paths, and all 13 fixtures pass from pristine repositories. The first
10-path candidate test also caught the prepare hook restored at mode 0644; mode
0755 was reinstated and the executable-mode test passed. A stale external
`rust-just` tool environment returned rc 2 before repository gates; after tool
reinstallation the exact candidate passed `just check` with 2,999 tests. No red
result was waived.

Current boundary:

```text
S9_0_LOCAL_CANDIDATE=PASS
REPAIR_PR=PENDING
REQUIRED_GITHUB_CI=PENDING
HUMAN_MERGE=PENDING
RECREATED_DEPLOYMENT=PENDING
REPLACEMENT_FRESH_SESSION=PENDING
RETAINED_PRE_REPAIR_SESSION=session-fba3e51dcae249efbcd2d5c7dd95e7b6
RETAINED_PRE_REPAIR_SESSION_MUTATED=no
S9_STATUS=PENDING
FEATURE_PRODUCTION_READINESS=UNCLAIMED
NEXT=APPLY_AND_VERIFY_S9_0_REPAIR_IN_OPERATOR_CLONE
```

## 17. S9.0 live apply feedback — verifier hotfix pending

The operator cleaned only the exact stale external verifier files and restored
the tracked preflight probe, then applied A79 successfully:

```text
S9_REPAIR_APPLY=PASS
REUSED_EXISTING=no
APPLY_SCRIPT_RC=0
```

The first independent verification correctly blocked at the executable-mode
oracle:

```text
READY=ready_repaired
TARGETED_PYTEST=FAIL
prepare-commit-msg_expected=0755
prepare-commit-msg_actual=0700
```

Cause: apply script `umask 077` governed Git's replacement-file creation. The
operator ran a guarded exact-path mode normalization; patch/diff identity stayed
unchanged. The second verification then passed locked sync, readiness, 228
focused tests, Ruff, format, Mypy, Pyrefly, shell, and workflow YAML, but full
`just check` reported ten failures:

```text
test_posix_modes_false_when_chmod_does_not_stick
fingerprint_changes[pyproject]
fingerprint_changes[lock]
fingerprint_changes[precommit_config]
fingerprint_changes[hook_bytes]
fingerprint_changes[hook_mode]
fingerprint_changes[installer]
fingerprint_changes[status]
fingerprint_changes[python_minor]
fingerprint_changes[uv_version]
```

All ten are one verifier-process defect. Global `umask 077` leaked into test
subprocesses: temporary executable hooks began at 0700 rather than 0755, every
fixed fingerprint changed, and the mocked no-op chmod probe began at its target
0600 mode. Product behavior, lock state, and targeted gates were green.

v33 correction:

- Git apply runs in an umask-022 subshell;
- exact four executable and six regular paths are normalized to 0755/0644 on
  first and idempotent recovery paths;
- every verifier gate runs in an umask-022 subshell, while logs/state retain
  outer umask 077;
- fake uv/uvx fixtures assert child `umask=0022`;
- all 13 script cases and ShellCheck pass locally;
- the exact ten former live failures pass under the corrected gate scope;
- full corrected-candidate `just check` passes with 2,999 tests.

```text
HOTFIX_UMASK_REGRESSION_TESTS=10_passed
HOTFIX_JUST_CHECK=2999_passed_2_skipped_1_xfailed
LIVE_BRANCH_HOTFIX=PENDING
LIVE_REPAIR_VERIFY=PENDING
S9_STATUS=PENDING
FEATURE_PRODUCTION_READINESS=UNCLAIMED
NEXT=APPLY_V33_INCREMENTAL_HOTFIX
```
