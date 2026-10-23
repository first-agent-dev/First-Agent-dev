# I03 live-host E2E test plan — how to build the suite, in dependency order

**Status:** PLAN ONLY. No case below has been executed, no row in
[e2e-live-verification-register.md](e2e-live-verification-register.md) is promoted, and nothing here
is evidence of live behaviour. Dates this plan: 2026-10-22, after E265 (SLICE2 STEP4 part B-1).

**Current acceptance-scope ruling (2026-10-23):** final I03 acceptance requires live-host E2E for all
changes in I01–I03 of this project. This plan and the existing 26-surface/8-join I03 inventory do not
currently include I01 live cases; Q87 tracks the required I01 producer-to-case mapping. Its absence
blocks the final gate, not the separate I03-only planning statements below. The canonical package is
`worklogs/planning-topology-and-executable-contracts-loop/e2e/`.

**Purpose.** The register already says *what* the host fixture must arrange and observe, one row per
producer (26 surfaces, 8 joins as of 2026-10-23, all `PLANNED / UNEXECUTED`; I01 rows remain absent under Q87). It does not say *how to build the suite*:
what the harness must be, in what order the cases become writable, what counts as a valid oracle when
the assertion cannot run in-process, and which cases are impossible before a later slice lands. This
document answers that, so the suite can be written mechanically at SLICE6 instead of being designed
under time pressure against a live host.

**Non-negotiable framing (inherited rules).**
- Deployment is Linux/Docker/Ubuntu/Python only; no added Go runtime. Cases run against the actual
  approved image, never a `tmp_path` stand-in for `/sessions/<id>/`.
- A runner/collection/timeout/infra failure cannot be evidence either way (kill or survival). A case
  that cannot arrange its fixture is `BLOCKED`, not `PASS`.
- Unknown terminality leaves ownership quarantined and the case `UNEXECUTED`; no retry is allowed to
  manufacture a verdict.
- Every case must have a **negative control** in the same file: the same fixture with one producer
  disabled, proving the oracle can see the producer at all. "Green twice" is not a proof.

---

## 1. Harness shape

Three layers, deliberately separate, because each fails differently:

| Layer | Location | Purpose | Runs in CI? |
| :--- | :--- | :--- | :--- |
| `tests/integration/conftest.py` | in-repo | host probe + session-scoped fixtures (image, daemon, sessions root, evidence sink) | no (skipped without host) |
| `tests/integration/live/test_*.py` | in-repo | the cases; each maps to exactly one register row or join | no |
| `scripts/e2e_live.py` | in-repo | driver that runs the suite as an *external* observer, captures evidence, and writes the run manifest | no |

Rules that make the layer honest:

1. **Markers must be registered before the first case is written** (`pyproject.toml`
   `[tool.pytest.ini_options] markers`). The plan's verify fences already invoke
   `-m execution_host`; with `--strict-markers` on, an unregistered marker is a hard error, so
   registration is step 1, not a detail. Two markers: `execution_host` (needs Docker + approved
   image) and `live_e2e` (needs Docker + approved image + real provider credentials — the S08 cases).
2. **Skip is not pass, and a skip must say why.** The fixture skips at *collection* only when
   `FA_REQUIRE_EXECUTION_HOST` is unset; when it is set (`FA_REQUIRE_EXECUTION_HOST=1`), a missing
   daemon/image is a **failure**, not a skip. This is the single guard that stops a green-looking run
   on a host that never had Docker.
3. **Assertions read persisted evidence, never in-process objects.** For anything that claims "the
   deployed controller did X", the oracle is: the on-disk run artifact
   (`/srv/first-agent/state/session-log/<run_id>/…`), the Docker API response the driver captured, the
   kernel's own view (`/sys/fs/cgroup/…`), or a sentinel file written by a shim the image executed.
   In-process objects are acceptable only for `unit`-level cases that stay in `tests/`.
4. **One evidence directory per run**, `notes/evidence/i03-e2e/<run-id>/`, containing: image digest,
   wheel SHA, daemon version, kernel/cgroup facts, the pytest JUnit XML, the driver manifest, and any
   captured frames/sentinels. Evidence is append-only; a later run adds a directory, never rewrites.
5. **Cleanup is part of the oracle.** Every case ends with the same assertion: zero containers
   carrying the run label, zero live `fa-*` cgroup entries, zero supervisor processes. A case that
   leaks is a failure even if its own assertion passed — leaked cells are how ownership bugs hide.

---

## 2. Phase order (what becomes writable when)

Cases cannot be written before their subject exists; writing them early produces the near-miss
proxies the project already paid for once (E259: duplicated producers masking each other). Order:

| Phase | Cases unlocked | Requires | Register rows |
| :--- | :--- | :--- | :--- |
| **P0 harness** | fixture, markers, driver, evidence sink, cleanup oracle | nothing beyond a host | — |
| **P1 images/entry** | installed wheel, isolated entry, profile rendering, PTY deadlines | approved image build (`Dockerfile.fa`), pinned CPython 3.13 | LIVE-01, 02, 05, 15, 16 |
| **P2 backend/cell** | create/start/attach/RUN, one-shot + interactive worker, cancel, force-stop | P1 | LIVE-10, 11, 12, 13, 18 |
| **P3 authority/views** | registration, R0, pinned readers, rooted IO, same-view read-your-writes | P2 | LIVE-03, 14, 17 |
| **P4 tools through the real port** | E264/E265 seams on an admitted view (below, §4) | P3 + the SLICE4 STEP2 composition | joins S02, S05, S07 |
| **P5 journal/recovery/seal** | supervisor kill at each durable boundary, seal/drain, forward recovery | P3 + SLICE3 | LIVE-06, 07, 08, 09, joins S01, S03, S04, S06 |
| **P6 composed service** | SessionManager/provisioner/CLI, strict readiness, real provider | P4, P5 + SLICE4 cutover + SLICE6 review | LIVE-04, joins S07, S08 |

**Blocked today:** P4 requires the actual composition root (SLICE4 STEP2 wires the provisioner and the
port); P5 requires SLICE3's seal/publication; P6 requires SLICE4's atomic cutover (including the named
146-occurrence readiness migration under Q78 option B). Writing those cases now would encode an
invented composition — the exact failure mode of asserting against a stub.

---

## 3. Case template (write this, not prose)

Every case file carries, above the test:

```
Register row:   I03-LIVE-14 (+ join S05 if the case spans)
Contract:       CT101/CT103a (as cited by the row)
Arrange:        what the fixture must exist (image, view purpose, plan_ref, session id)
Act:            the one externally-triggered action
Observe:        the persisted artifact / kernel fact / sentinel that decides it
Negative control: the mutation of the product this oracle must catch
Cleanup:        the leak assertion
```

The negative control is what makes a live case worth its cost. It must be *product code* disabled via
an environment switch the image respects, or a rebuilt image with the line removed — never a
monkeypatch of the process under test, which would prove nothing about the deployed artifact.

---

## 4. Cases this session's work adds (E264/E265), and how to verify them live

These are new obligations created by SLICE2 STEP4 part A/B. Unit proof exists; live proof needs the
admitted view, so all belong to P4.

| Case | Arrange | Observe | Negative control |
| :--- | :--- | :--- | :--- |
| **L-TOOL-1** write/read/edit through the port | admitted PROJECT view, real authority, controller process | bytes land in the view (`authority.read_file` agrees, host canonical untouched), denial for an unadmitted path leaves no file | remove the port injection → the tool writes the host path, which the case must catch by watching the canonical tree |
| **L-TOOL-2** stale-base edit | two controller principals on one view | second write returns the conflict result, concurrent bytes preserved | disable the digest check → lost update, case fails on content |
| **L-TOOL-3** PDF/binary/oversize are named refusals | view with a PDF, a NUL-containing blob, and a >1 MiB text file | three distinct, deterministic tool results; the canonical/host file is *never opened* (see trace below) | restore the host-path read → the trace shows an `open` outside the view |
| **L-TOOL-4** artifacts keep the controller path | an artifact minted by a real run, then an `artifact_id` read inside the view | content matches the stored artifact; no view IO for it | route artifacts through the port → refusal, case fails |
| **L-TOOL-5** search/reach indexes stay cell-local | one admitted view, `fs_search` + `fs_reach` invoked twice | index files appear under the view's cache dir only; `find <view> -name '*.db'` is empty; a second, pinned view answers its own revision | point the index at `<view>/.fa` → the tree gains a db (and the view digest changes) |
| **L-TOOL-6** zero host-Git reads | controller process with `git` replaced by a shim that appends to a sentinel and exits 127 | sentinel is empty after a full tool sweep; the JSON tool inventory contains no `fs_checkpoint`/`fs_undo`/`fs_diff` | re-enable the pair tools → sentinel non-empty |
| **L-TOOL-7** tools and PTY see each other | one view, a PTY inside the cell, a tool write | PTY output shows the tool's write and vice versa, with blackboard on and off; a *reader* view is unaffected | drop the shared view → the PTY sees stale bytes |

**Tracing "never opened the host file" / "never ran git".** Two cheap, external mechanisms; use both,
because each misses a case:
1. **Shim on `PATH`** for `git` (and any host helper) writing `argv`+`cwd` to a sentinel file. Catches
   every `execve` the controller spawns through `PATH`; deterministic, no privileges.
2. **`strace -f -e trace=execve,openat -o trace.txt --` around the controller** in the driver, filtered
   to paths outside the view and the approved roots. Catches absolute-path execution the shim cannot,
   and file opens. Requires `CAP_SYS_PTRACE` on the host — record its absence as `BLOCKED`, never as
   `PASS`.

---

## 5. Sequences worth spelling out (the ones a naive case gets wrong)

1. **Pinned reader vs active writer (S05/L-TOOL-5).** Order matters: create the reader view *while*
   the writer's second revision is in flight, then assert the reader answers revision R0 bytes even
   after the writer commits R1. Creating the reader afterwards proves nothing.
2. **Cancel before create / during create / during RUN (S04).** Three separate cases with distinct
   expected journal states (`not_created`, `create_uncertain`, `stopped`). The kernel barrier assertion
   is `/sys/fs/cgroup/<path>/cgroup.events` showing `populated 0`, read *after* the stop returns —
   never the API's 204.
3. **Supervisor death at a durable boundary (S06).** Kill `-9` between `fsync` and pointer replace;
   restart; the only acceptable outcomes are the complete old revision, the complete new revision, or
   quarantine. Any partial projection is a failure of the case, not a flake.
4. **Readiness gating (S07, after cutover).** With a provisioner injected, a workspace whose readiness
   can be forced degraded must produce `workspace_not_ready` and **no** active manifest, no run
   binding, no workspace bytes. Force degradation through the real environment (a broken prewarm
   input), not by stubbing the classifier.

---

## 6. Cost, flakiness and evidence policy

- Budget: P1 ≈ 10 min (image build amortised), P2 ≈ 15 min, P3 ≈ 10 min, P4 ≈ 10 min, P5 ≈ 20 min
  (kill/restart cycles), P6 ≈ 20 min with a real provider. Per-case timeout 120 s except the kill
  matrix (300 s) and provider cases (600 s).
- **No retries for evidence.** A flaky case is a defect in the case or the product; re-running until
  green converts an unknown into a false PASS.
- A case that fails to *arrange* is reported `BLOCKED` with the arranging command and its actual
  output; the run continues so one blocked case cannot hide the rest.
- Results are appended to the register row (`Actual live evidence` column or a dated subsection) with
  the evidence directory and the image digest — never edited in place.

---

## 7. What this plan deliberately does not do

- It does not promote any row, invent a verdict, or claim that unit proof transfers to the host.
- It does not schedule execution: the user's standing instruction is E2E at the end of I03, and P4–P6
  are blocked on SLICE3/SLICE4 work anyway.
- It does not add a second harness: `pytest` + the existing markers/driver conventions are enough. A
  bespoke runner would be one more thing to keep honest.
