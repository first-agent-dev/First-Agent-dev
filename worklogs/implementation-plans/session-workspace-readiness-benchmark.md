# Workspace readiness cache benchmark

Date: 2026-08-13
Plan: `PLAN-session-workspace-readiness-bootstrap` v21
Slice: S7
Contract: CT9
Verification: T14
Matrices: M1–M3

## 1. Decision

```text
Q2=PERSISTENCE_DEFERRED
CACHE_TOPOLOGY=EPHEMERAL_TMPFS
HOME_CACHE_CAP=1536M
UV_CACHE_CAP=2G
```

Keep both caches ephemeral. Increase only `/home/fa/.cache` from 500 MiB to
1536 MiB. Do not add a persistent uv or pre-commit bind, do not bake hook
environments, and do not weaken or remove gitleaks or any other hook.

The decision is deliberately conservative: cold readiness completed in a
controlled proxy, warm readiness is fast, and the completed HOME-cache peak fits
1536 MiB with 616,704,512 bytes (38.29%) allocated-block headroom. Persistence
would add ownership, poisoning, permissions, quota, prune, and rollback policy
without a demonstrated latency problem in the real deployment.

Reopen Q2 only if a production-equivalent run reaches the cap, cold latency is
operationally unacceptable, or restarts become frequent enough that rebuilding
is a measured cost. Any persistent mount still requires the separate P2 plan
specified by S7.

## 2. Evidence classification and limitations

This Arena execution environment has no Docker daemon and does not expose the
host `/srv` deployment tree. It must not be represented as the First-Agent image.
The controlled proxy used:

- exact candidate bytes committed before measurement;
- ext4 workspace storage, matching the recorded production `/sessions` type;
- empty isolated cache roots;
- actual locked uv/pre-commit versions;
- tmpfs for direct uv and failed capacity trials;
- ext4 cache storage for completed pre-commit/combined latency and full
  allocated-block peak measurement because the largest available isolated tmpfs
  was only 1,040,695,296 bytes;
- `UV_LINK_MODE=copy`, closed Git prompting, and disposable HOME/TMPDIR roots.

Consequences:

- size and cap decisions use completed logical and allocated-byte peaks;
- direct uv cold/warm timing is a tmpfs measurement;
- pre-commit and combined timing are controlled ext4-cache proxies, not an
  actual project-image latency claim;
- repeated download trials may benefit from host/network caches outside the
  disposable roots, so cold network timing is indicative rather than a service
  objective;
- actual image identity and current production session `.venv` inventory are
  explicitly unavailable here and remain S9 live-evidence fields.

The report still closes Q2 conservatively because it authorizes no persistence.
It cannot be used later as evidence to add a persistent cache.

## 3. Identity

| Field | Value |
| --- | --- |
| Source HEAD | `ac5ba1adc7fa7ff24ec77134f56d8eb87676f317` |
| Source description | `ac5ba1a-dirty` |
| Changed/untracked paths at final capture | 54 |
| Exact benchmark candidate commit | `5e897f329e23067bc1585d2b2d57acbd08bc5c68` |
| Exact candidate tracked files | 791 |
| Recorded live deployment HEAD from S0 | `eb2c03c15adab72569cac400027add09ce8dce6f` |
| Actual First-Agent image ID | unavailable in sandbox; must be captured in S9 |
| Dockerfile recipe SHA-256 | `ac5132cf1e917faa14f84049f9ca52b8c8b509ad8c0be437ab94006b02cd8010` |
| Compose SHA-256 with 1536M cap | `57268ef27adea6933cd3c424b6f7bf53efbc16312b717f3f68ccb6a0573e6ab2` |
| Kernel | `Linux e2b.local 6.1.158+ x86_64` |
| OS | Debian GNU/Linux 13.6 (trixie) |
| uv | `uv 0.12.3 (x86_64-unknown-linux-gnu)` |
| Python | `Python 3.13.14` |
| pre-commit | `pre-commit 4.6.0` |
| Git | `git version 2.47.3` |

## 4. Filesystem and cap matrix

| Seat | Production authority | Controlled measurement | Cap |
| --- | --- | --- | ---: |
| session workspace | ext4 bind at `/sessions` | ext4 workspace root | host filesystem |
| uv cache | tmpfs at `/tmp/uv-cache` | tmpfs for direct uv; ext4 for combined proxy | 2,147,483,648 bytes |
| HOME/pre-commit cache | tmpfs at `/home/fa/.cache` | failed tmpfs trials; completed ext4 size proxy | 1,610,612,736 bytes |
| general `/tmp` | tmpfs | disposable ext4 TMPDIR for isolated HOME sizing | 1 GiB production |

The original HOME-cache cap was 524,288,000 bytes. It was below every completed
or near-complete cold peak and is replaced by the tested `1536M` Compose value.
The cap is a ceiling, not preallocated memory.

## 5. Fixed command sheet

Each run started from a fresh exact Git clone or the stated retained workspace.
The sampler walked declared cache/environment roots every 100 ms and recorded
both logical bytes and allocated blocks.

```text
# Component cold/warm uv; UV_CACHE_DIR is empty tmpfs for cold.
uv sync --locked --extra dev
uv sync --locked --extra dev

# Component cold/warm pre-commit; PRE_COMMIT_HOME/HOME are empty for cold.
.venv/bin/pre-commit install-hooks
.venv/bin/pre-commit install-hooks

# Combined cold/warm readiness.
<control-python> scripts/bootstrap/workspace.py ensure --workspace <candidate>
<control-python> scripts/bootstrap/workspace.py ensure --workspace <candidate>

# M3: retain workspace, .venv, marker, and uv cache; delete HOME cache.
rm -rf <isolated-home>/.cache
<control-python> scripts/bootstrap/workspace.py ensure --workspace <candidate>
```

Environment contract:

```text
UV_LINK_MODE=copy
GIT_TERMINAL_PROMPT=0
UV_CACHE_DIR=<isolated-root>
PRE_COMMIT_HOME=<isolated-home>/.cache/pre-commit
HOME=<isolated-home>
TMPDIR=<disposable-root>
```

All command arguments were list-form. No provider/model call, external push,
secret read, cache reuse, or production path mutation was performed.

## 6. Capacity discovery and failed trials

Nonzero trials are retained because they discovered Q8 and define the negative
boundary; they are not included as successful timing rows.

| Trial | HOME/pre-commit observed peak | Result |
| --- | ---: | --- |
| shared 993 MiB `/tmp`, first cold run | HOME logical 610,702,469; pre-commit logical 543,865,009 | rc 3, ENOSPC while expanding gitleaks Go modules |
| shared 993 MiB `/tmp`, isolated transients | HOME logical 801,613,988; pre-commit logical 677,728,683 | rc 3, ENOSPC copying gitleaks executables |
| empty 1,040,695,296-byte `/dev/shm` | HOME logical 877,152,067; tmpfs used 1,000,177,664 | rc 3, ENOSPC copying generated gitleaks config binary |

A completed ext4 run then measured the full peak:

| Tree | Peak logical bytes | Peak allocated bytes | Final logical bytes | Final allocated bytes |
| --- | ---: | ---: | ---: | ---: |
| total isolated HOME cache | 921,239,936 | **993,908,224** | 638,264,447 | 700,472,832 |
| pre-commit subtree | 709,725,635 | 767,550,976 | 368,773,223 | 417,901,568 |

The completed maximum is the sizing authority. At 1 GiB it leaves only
79,833,600 bytes (7.4%), which is not robust. At 1536 MiB it uses 61.71% and
leaves 616,704,512 bytes (38.29%). A 2 GiB HOME cap is unnecessary on current
evidence.

## 7. Component timing matrix

All rows returned zero.

| Component | Cold wall | Warm wall | Cold/warm oracle |
| --- | ---: | ---: | --- |
| `uv sync --locked --extra dev` on tmpfs cache | 1.612073 s | 0.065653 s | exact locked argv; 91 packages; warm checked 76 packages |
| `pre-commit install-hooks` ext4 cache proxy | 71.922611 s | 0.222198 s | all configured environments installed; second invocation no output |

Direct uv cache size:

| Metric | Bytes |
| --- | ---: |
| cold logical peak | 180,253,579 |
| warm/final logical | 178,128,905 |
| warm/final allocated | 189,992,960 |

Prepared `.venv` size:

| Metric | Bytes |
| --- | ---: |
| logical | 178,797,184 |
| allocated | 189,746,688 |

## 8. Combined readiness matrix

All rows returned zero and emitted typed JSON.

| Matrix | Wrapper wall | Engine elapsed | Reason | State oracle |
| --- | ---: | ---: | --- | --- |
| M1 cold candidate/cache | 76.418005 s | 76.318 s | `ready_repaired` | `.venv`, four seats, sentinel, marker present |
| M2 warm same container/cache | 0.111884 s | 0.045 s | `ready_fast_path` | no sync/prewarm mutation |
| M3 retained workspace after HOME cache loss | 66.606732 s | 66.540 s | `ready_repaired` | marker was rewritten; cache rebuilt |

Combined cold peaks:

| Tree | Peak logical bytes | Peak allocated bytes |
| --- | ---: | ---: |
| HOME cache | 877,211,967 | 945,579,008 |
| pre-commit cache | 681,103,411 | 737,793,024 |
| uv cache | 180,254,081 | 191,673,344 |
| `.venv` | 178,796,937 | 189,746,688 |

M3 proves that cache loss cannot reuse the retained marker as false READY. The
workspace Git porcelain status remained empty after all combined runs.

## 9. Session workspace and copy-amplification evidence

| Shape | Logical bytes | Allocated bytes |
| --- | ---: | ---: |
| legacy raw-copy source approximation | 240,764,558 | 256,765,952 |
| exact baseline repository | 17,511,224 | 20,933,120 |
| fresh clean clone before readiness | 16,867,636 | 18,531,328 |
| clean clone after readiness | 195,766,647 | 208,409,088 |

Before readiness, clean Git provisioning avoids 223,896,922 logical bytes
(92.99%) compared with the old raw-copy shape. After provisioning its own clean
`.venv`, it remains 44,997,911 logical bytes (18.69%) smaller than the legacy
source approximation and does not inherit source administrative/untracked state.

The local sandbox contains one existing `.venv`, 189,881,081 logical bytes.
Current production session `.venv` count/aggregate is unavailable because the
sandbox has no `/srv` or Docker access. The earlier S0 live record had 33 active
manifests and an active legacy workspace without `.venv`; S9 must capture the
post-deployment inventory before any retention or persistence claim.

## 10. Q2 disposition

Q2 is explicitly deferred with measured reason:

- uv cold cost is small in this controlled run and already has a separate 2 GiB
  ephemeral seat;
- warm readiness is approximately 0.112 s wrapper / 45 ms engine;
- cold and cache-loss pre-commit rebuilds are tens of seconds, but no real
  production operator evidence yet shows that restart frequency makes this an
  unacceptable cost;
- persistence would widen the trust and maintenance boundary;
- a 1536 MiB ephemeral HOME cap fits the completed peak with 38.29% headroom.

Therefore:

```text
Q2=PERSISTENCE_DEFERRED_WITH_MEASURED_REASON
S7_CACHE_DECISION=KEEP_TMPFS_WITH_1536M_HOME_CAP
```

## 11. Cleanup and reproducibility

The final benchmark workspace consumed 1,863,792,485 logical bytes and
2,047,175,680 allocated bytes while retaining multiple cold candidates/caches.
It and every tmpfs benchmark root were deleted. Final checks reported:

```text
benchmark_root_exists=no
ram_roots=<none>
/tmp available=922,476,544 bytes
/dev/shm available=1,040,695,296 bytes
```

The summarized raw JSON was retained only until this report and its validator
were complete; it is not a repository artifact and contains no secrets.

## 12. CT9/T14 completion checklist

- [x] cold/warm locked uv wall time;
- [x] cold/warm pre-commit preparation wall time;
- [x] cold/warm/resumed total readiness wall time and typed result;
- [x] `.venv`, uv, pre-commit, HOME-cache final and peak sizes;
- [x] workspace/cache filesystem types and production caps;
- [x] source, candidate, tool, OS, recipe, and unavailable-image identity;
- [x] session `.venv` evidence plus explicit production-inventory limitation;
- [x] legacy raw-copy versus clean-clone size comparison;
- [x] failed capacity trials retained rather than relabeled;
- [x] Q2 resolved as measured defer;
- [x] no persistent mount or cache service added.

```text
T14=PASS_CONTROLLED_PROXY
G7=L3_MEASURED_DECISION
S7_STATUS=COMPLETE
```
