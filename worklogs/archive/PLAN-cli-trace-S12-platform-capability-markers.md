> **Status:** archived 2026-08-25 — moved from implementation-plans per 30-day rule

# PLAN: S12 — platform capability markers (native-Windows dev parity)

**Status:** COMPLETE (2026-08-02) — `tests/_capabilities.py` shipped with six cached
probes; 85 tests marked; `test_s12_marker_hygiene.py` enforces named reasons.
Linux gate 2460 passed / 15 skipped; Windows simulated 2362 / 104 skipped;
coverage floor 82.27% maintained. All I-42/I-43 follow-ups filed to BACKLOG.
HANDOFF §S12 COMPLETE records full gate numbers.
**Author:** agent, 2026-08-02
**Parent:** `cli-trace-substrate-rebaseline-2026-07-25.md`
**Closes:** BACKLOG **I-11** (partially — see §10), resolves **Q58**
**Ceremony:** lean
**Blast radius:** `tests/` only. **Zero `src/` changes.** (See §1.5 — the one
candidate product change was investigated and rejected.)

---

## 0. One-paragraph statement

The operator runs `just check` via the `pre-push` hook on native Windows 11
(VS Code, Git Bash on PATH, cp1251 console). 92 tests fail. **None is a product
defect**; all are tests that assume a POSIX host. The existing guard
`skipif(shutil.which("bash") is None)` asks *"is bash installed?"* when it means
*"can bash here speak this host's path dialect?"* — Git Bash satisfies the former
and fails the latter, so the guard passes and the test runs into MSYS path
translation. This slice replaces installation checks with **capability probes**,
so ~92 tests skip with an honest named reason on Windows while **2,336 keep
running**, and the identical file runs everything on Linux/WSL/CI.

---

## 1. Preflight — every claim below was verified by reading the repo or the log

### 1.1 The gate now reaches `test` for the first time

Operator log `git-error-1785668071658.md` (4,681 lines). Green on Windows:
`uv lock --locked`, `check_dependency_contract`, `ruff check`,
`ruff format --check` (643 files), `deptry`, `pylint` **10.00/10**, `mypy`
**323 files**, `fa authoring-check` (`exit_code: 0`),
`check_producer_consumer_contract`, `check_log_kind_contract`,
`check_no_mocked_dataclasses`. Then:

```
92 failed, 2334 passed, 17 skipped, 1 xfailed in 377.15s
error: recipe `test` failed on line 117 with exit code 1
```

Both prior encoding defects are **fixed and confirmed** by this log (the `✅`
characters render; the scripts print their `PASS:` lines).

### 1.2 This is not a regression from the S1–S11 stack

- Skip decorators were **not** loosened: `grep -c 'which("bash")'` over `tests/`
  returns **8 files at `ddbd03f`** and **8 files at HEAD** — identical.
- `src/fa/hygiene/hooks/pre-push` is **byte-identical** to base
  (`git diff ddbd03f..HEAD -- <hook>` is empty).
- **21 of 28** failing test files were never touched by the 103 commits. Only
  `test_s7_cli_run_paths.py` (+14/−1) and `test_stats_global_wiring.py` (+21/−8)
  were modified, and neither fails for a reason the diff introduced.
- `just check` gained only `cli-coverage-floor` and `--cov-report=json`.

### 1.3 Why the operator never saw this before

`scripts/check_dependency_contract.py` already contained `✅` **at `ddbd03f`**
(`git show ddbd03f:… | grep -c '✅'` → 3). Had `just check` ever completed on
this cp1251 console it would have crashed there. It did not crash before ⇒
**the full suite has never run to completion on this box.** The hook was
installed/re-installed recently. Nothing regressed; a pre-existing wall was
reached for the first time.

### 1.4 The root cause is the *predicate*, not the platform

```python
# tests/test_inner_loop_tools.py:58 — guard PASSES, test then FAILS
@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_run_bash_tool_runs_in_workspace(tmp_path):
    ...
>   assert result.result["stdout"].strip() == str(tmp_path)
E   - C:\Users\Администратор\...\test_run_bash_tool_runs_in_wor0
E   + /c/Users/Администратор/.../test_run_bash_tool_runs_in_wor0
```

Git Bash is on PATH ⇒ guard is False ⇒ test runs ⇒ MSYS answers `pwd` in
`/c/...` while Python asked in `C:\...`. **A box with no bash at all would have
skipped cleanly.** Adding a second blunt `skipif(platform=="win32")` on top of a
broken predicate would hide the bug rather than fix it — hence capability
probes (Q58 answer, operator-confirmed).

### 1.5 REJECTED product change — `pty_pool.py` has no hardcoded `/tmp`

I previously proposed fixing a "hardcoded `/tmp`" at `pty_pool.py:630`. **The
operator challenged it and was right.** Source:

```python
# src/fa/runtime/pty_pool.py:502  — the default is /workspace, correct for the container
base_cwd: Path = (Path("/workspace"),)
self.base_cwd = Path(base_cwd).resolve()  # :507
...
if not cwd.exists():
    raise RuntimeError(f"workdir {cwd} not exists")  # :630 — deliberate Gap-6 fail-fast
```

The `/tmp` is **test-supplied**, 11 times, e.g. `tests/test_pty_persistence.py:14`
`PtyPool(max_size=1, base_cwd=Path("/tmp"))`. On Windows `Path("/tmp").resolve()`
→ `C:\tmp`, which does not exist, so the guard correctly refuses. All three
product call sites pass a real workspace (`cli.py:2240`,
`inner_loop/state.py:539`, `runtime/server.py:53`).

**Verdict: `src/` is untouched by this slice.** The 11 shared-global-`/tmp` test
sites are a separate fragility → BACKLOG (§10, I-42), not fixed here.

### 1.6 The authoring TCB already blesses this pattern

`src/fa/authoring_rules/tests.py:11` (V4 rule docstring), verbatim:

> ``FA-AUTHORING-V4-PYTEST-SKIP`` — ``pytest.skip(...)`` call or
> ``@pytest.mark.skip`` decorator (**NOT** ``skipif``: cross-platform
> conditional skips are a legitimate pattern and the codebase uses them
> extensively for ``shutil.which("bash")``-style guards).

So `skipif` is permitted and `skip`/non-strict `xfail` are HARD_BLOCK. This
slice must use **`skipif` only** — never a bare `skip`, never `xfail`.

### 1.7 pytest configuration constraints (`pyproject.toml:165–185`)

```toml
addopts = ["-ra", "--strict-config", "--strict-markers"]
testpaths = ["tests"]
pythonpath = ["."]
asyncio_mode = "auto"
```

`--strict-markers` is ON and **no `markers =` key exists**. Consequence: if this
slice registers custom marks it MUST add a `markers` list or every use errors.
**Design decision D1 (§3):** use module-level `skipif` constants, *not* custom
marks — zero config change, no `--strict-markers` interaction.

### 1.8 Existing capability-probe precedent in-repo

`tests/test_deploy_scripts.py:177` already does exactly the right thing:

```python
@pytest.mark.skipif(not os.access(_SCRIPTS / "fa", os.X_OK),
                    reason="Filesystem does not support executable bits")
```

This is the house style to extend, not a new invention. It also proves the
probe pattern survives the authoring gate today.

### 1.9 Verified Linux baseline (this sandbox, after a corrected `uv sync`)

```
2428 passed, 15 skipped, 1 xfailed in 131.54s
SKIPPED [12] tests/test_deploy_scripts.py:164: shellcheck not installed
SKIPPED  [1] tests/test_deploy_scripts.py:177: Filesystem does not support executable bits
SKIPPED  [2] tests/test_runtime_server_c1.py:49,65: runtime server extra is deferred
```

**15 is the number that must not move.** (Operator's Windows run showed 17
skipped: the same 15 minus the 2 that Linux skips for other reasons, plus
Windows-only `test_chunker_plaintext.py:95` and
`test_hygiene_hooks_install.py:338` / `test_inner_loop_runtime.py:399`.)

---

## 2. Measured failure ledger — all 92, bucketed from the log

Bucketing script: parse `FAILED` lines + per-section `E ` tracebacks from the
operator log. Reproducible; kept in §9 DoD.

| bucket | count | discriminating evidence | marker |
|---|---:|---|---|
| **B1 POSIX shell dialect** | 15 | `/c/Users/...` vs `C:\Users\...`; `bash exited -1 / No fallback available` | `requires_posix_shell` |
| **B2 POSIX file modes** | 11 | `assert 438 == 384` (`0o666`≠`0o600`), `0o777` dirs, `missing executable bit` | `requires_posix_modes` |
| **B3 tmux / PTY** | 10 | `tmux binary not found, falling back to pexpect` → `RuntimeError: workdir C:\tmp not exists` | `requires_tmux` |
| **B4 POSIX path semantics** | ~14 | `'src\fa\dead.py' == 'src/fa/dead.py'`; `'/\\' == '/'`; `resolved path C:\etc\passwd`; `is not in the subpath of` | `requires_posix_paths` |
| **B5 symlinks** | 3 | `exists and is not a symlink`; `copy-fallback target must be executable` | `requires_symlinks` |
| **B6 8.3 short paths** | 2 | `C:\Users\836D~1\...` vs `C:\Users\Администратор\...` | `requires_stable_tmpdir` |
| **B7 cascades** | ~37 | downstream of B1–B4 (`fa run` smoke → `assert 1 == 0`; s10b parity; entrypoint) | inherit parent marker |

**B7 is the risk in this plan.** Cascades must be attributed to a *cause*, not
blanket-skipped. Step S12.1 exists to force per-test attribution before any
marker is applied (§5).

Named examples of correct attribution (read from the log, not guessed):

- `test_repo_has_no_broken_internal_file_links` → **B4**: the link resolver
  joins with `/` and produces `knowledge\research\knowledge\prompts\...` — a
  path-join bug *in the test helper*, not a broken doc link.
- `test_log_kind_member_count_matches_source` → **B4**: the source scanner globs
  with `/`-joined paths and finds **zero** producers, so all 32 LogKind members
  look orphaned. A blanket skip would hide a real contract; the marker must be
  `requires_posix_paths` with that reason.
- `test_validate_rm_denies_etc` → **B4**: product returns the *correct* denial;
  only the interpolated `resolved path C:\etc\passwd` differs from `/etc/passwd`.
  **Security control verified working.**
- `test_defaults_to_home_dot_fa` → **B4 + fixture**: `fa_state_root()` returns
  the real `C:/Users/…/.fa`, i.e. the monkeypatched `HOME` did not take effect
  on Windows (`HOME` vs `USERPROFILE`). Attribute precisely.
- `test_workspace_env_files_are_not_present` → **B1**: `bash exited 1, stderr:
  ⥬㇠㪠.` — mojibake from cp1251↔UTF-8 in the Git Bash pipe. Shell dialect.

---

## 3. Design decisions

**D1 — module-level `skipif` constants, not custom marks.**
`--strict-markers` is on and `markers =` is absent (§1.7). Custom marks would
require a `pyproject.toml` change and would silently error if misspelled.
Constants are plain Python, typo-safe under mypy, and match the existing house
style (§1.8).

```python
# tests/_capabilities.py  (NEW)
requires_posix_shell = pytest.mark.skipif(not _probe_posix_shell(), reason="no POSIX shell that agrees with host paths")
```

**D2 — probes are capability tests, never `sys.platform` checks.**
A `platform == "win32"` test would also skip on WSL, where these tests pass, and
would keep skipping forever if the underlying issue were fixed. Every probe
asks the functional question.

**D3 — probes are cached, cheap, and never raise.**
`@functools.cache`; each wrapped in `try/except Exception → False`. A probe that
throws during collection would take down the whole suite — worse than the
disease.

**D4 — `_probe_posix_shell` must test the *dialect*, not the binary.**
This is the crux of the whole slice:

```python
out = subprocess.run([bash, "-c", "pwd"], cwd=tmpdir, capture_output=True, text=True)
return Path(out.stdout.strip()) == Path(tmpdir)  # False under MSYS: /c/... != C:\...
```

**D5 — no `noqa`, no `pytest.skip()`, no `xfail`.** Per standing policy and
§1.6 (V4 HARD_BLOCK).

**D6 — one reason string per bucket, naming the capability.** Reasons appear in
`-rs` output and are the operator's only signal about what is not being
verified locally. `"windows"` is not an acceptable reason.

**D7 — `tests/_capabilities.py` is type-checked and must be fully annotated.**
Review finding: `pyproject.toml:162` sets `files = ["src", "tests"]`, so mypy
covers `tests/`. The new module needs complete annotations
(`def _probe_tmux() -> bool:`) or `just typecheck` fails. Note there is **no
existing non-`test_*` helper-module precedent** in `tests/` — only
`__init__.py` and `conftest.py`. The leading underscore keeps pytest from
collecting it; `tests/` is already a package (`tests/__init__.py` exists), so
`from tests._capabilities import ...` resolves, consistent with
`pythonpath = ["."]` (`pyproject.toml:184`).

---

## 4. Contracts

**CT1 — a probe reports the capability it names.**
Forcing a probe False skips exactly its bucket; forcing it True makes those
tests attempt to run. Negative proof: monkeypatched-False run shows the skip
count rise by exactly that bucket's size.

**CT2 — Linux/CI coverage is unchanged.**
On this sandbox the suite stays **2428 passed / 15 skipped / 1 xfailed**. Any
increase in Linux skips means a probe is wrong and coverage was silently
deleted. This is the single most important assertion in the slice.

**CT3 — every skip names a capability, not a platform.**
An executable meta-test asserts no reason string in `tests/` matches
`/windows|win32|platform/i` unless it also names a capability.

**CT4 — the Windows gate goes green without weakening the product.**
`just check` exits 0 on the operator's box; `src/` diff is empty
(`git diff --numstat HEAD -- src/` → no lines).

**CT4a — the coverage floor still holds on Windows.**
**Review finding — the draft missed a hard gate.** `pyproject.toml:202` sets
`fail_under = 80`, and `just test` runs with `--cov`, so skipping ~92 tests
*lowers coverage* and could fail the gate even with 0 test failures. Measured on
Linux by deselecting the exact 85 unique failing node IDs from the operator log:

```
# baseline
2428 passed, 15 skipped, 1 xfailed     TOTAL 83%   Total coverage: 83.22%
# with all 92 (85 unique IDs) deselected
2336 passed, 14 skipped, 93 deselected TOTAL 82%   Total coverage: 82.22%
Required test coverage of 80.0% reached.
```

**Cost of the whole slice: −1.00 pp, landing at 82.22% against a floor of 80 —
2.22 pp of headroom.** The operator's own Windows run already reported
`Total coverage: 82.52%` with the failures counted, confirming the same order of
magnitude on their box. **The slice is viable, but the margin is thin**: a future
slice that skips more, or a coverage ratchet raising the floor to 85 (BACKLOG
I-28 wants 90), breaks Windows first. Recorded as R7.

**CT5 — markers are load-bearing.**
No marker may be applied to a test that passes without it. Each marker's
kill-check (§6) proves at least one test genuinely depends on it. A marker that
never fires is coverage theatre and must be deleted.

---

## 4a. Scope, non-goals, dependencies, stop conditions (parent §13)

**In scope:** `tests/` only — the new probe module, the marker applications
named by S12.1, and two new meta-tests.

**Explicit non-goals.**
- **No `src/` change.** Enforced as a DoD assertion, not an intention (§1.5).
- **No Windows shell backend** (`fs_run_cmd`). That is the real I-11 fix and is
  ADR-scale; S12 makes the suite honest, it does not make FA Windows-native.
- **No fixing of the tests that skip.** A skipped test is a recorded gap, not a
  solved one.
- **No coverage-floor change.** If S12 breached `fail_under`, the correct
  response is to stop and escalate, never to lower the floor (the file's own
  comment: *"never lower for convenience"*).
- **No `tests/test_authoring_rules_tests.py` edit** (S12.3).

**Depends-on:** nothing. S12 is independent of S11 and can land before or after
it. **Parallelizable-with:** S11 (disjoint files — S11 is a plan-only operator
sheet touching no source).

**Stop conditions — halt and promote to a Q# rather than proceeding:**
1. S12.1 cannot attribute a failure to a capability from log evidence
   (→ escalate as candidate defect, RV8).
2. Applying markers moves the Linux count off `2428/15/1` (→ probe is wrong).
3. Windows coverage lands below `fail_under = 80` (→ R7 realised; the slice's
   premise fails and the answer is not a floor change).
4. A 7th failure bucket appears that no probe explains.

**Rollback:** revert two commits (`tests/_capabilities.py` + markers). `src/` is
untouched, so rollback cannot affect the product or the deployed image.

**Artifact handling:** `worklogs/S12-failure-attribution.md` and
`tests/data/windows-baseline-2026-08-02.txt` are committed evidence, not
scratch. The operator log itself is **not** committed — it contains the
operator's Windows username in a path.

---

## 5. Steps

### S12.0 — Pin today's behaviour (no edits)

Record the Linux baseline `2428/15/1` and store the operator log's 92-item
failure list as a fixture (`tests/data/windows-baseline-2026-08-02.txt`) so
S12.1's attribution is checkable, not remembered.
**DoD:** baseline file committed; numbers quoted in the plan match a fresh run.
**Tests-writing class:** C0 (no behaviour change).

### S12.1 — Attribute all 92 failures to a cause (no edits)

Produce `worklogs/S12-failure-attribution.md`: one row per failing test →
bucket → the *specific* log line justifying it. Every B7 cascade must name its
upstream cause. **Stop rule:** any test that cannot be attributed from evidence
is escalated, not guessed.

**RV8 — a "cascade" is a hypothesis until the mechanism is named.** This is the
highest-risk step in the slice, because the cheap move is to label anything
confusing a cascade and skip it. Worked example that the draft got wrong:

```
tests/test_s10b_cli_parity.py:161
>   assert events.is_file(), "the durable event log must exist after a successful run"
E   AssertionError: assert False
E     where is_file = WindowsPath('.../home/.fa/session-log/parity-happy/events.jsonl').is_file
```

The run **succeeded** (`OK: stopped_by_llm (turns=1)` in captured stderr) and
then the durable event log **was not written**. `events.jsonl` is produced by
`src/fa/cli.py:1909` / `:2486`. Nothing in that assertion is about path
separators, file modes, or shell dialect. **This may be a genuine product defect
in which the event log silently fails to materialise on Windows — exactly the
"deriving one fact twice / silent artifact drift" class already on the board.**

**Mandatory rule:** a test may be marked `requires_*` only when the attribution
row names the **specific POSIX capability** the failure depends on. If the row
would read "downstream of something", the test is escalated as a candidate
product bug, NOT skipped. Escalated items go to §10 as new BACKLOG entries with
a one-line repro, per the standing "convert findings to BACKLOG items, not
fixes" directive.

**Named escalation candidates from the first read** (executor must resolve each
to defect-or-capability with evidence before S12.3):
`test_s10b_parity_happy_path`, `test_s10b_parity_without_sink_exports_global_history`,
`test_s10b_stats_parity_global_history_{json,console}_goes_to_std{out,err}`
("fixture did not write the projection"),
`test_s10b_prepare_pr_draft_clear_failure_is_fatal`.
If these are real, **S12 must not hide them** — that would be the precise
anti-pattern this whole workplan exists to prevent.

**DoD:** 92 failure lines / **85 unique node IDs** all attributed; zero
`UNCLASSIFIED`; each row cites a log line **and** names a capability or is
marked ESCALATED with a BACKLOG id.
**Producer kill-check target:** none (analysis step).

### S12.2 — `tests/_capabilities.py` (NEW) — the probes

**Idea implemented now:** one module that answers "can this host do X?" so no
test has to guess from `sys.platform`.

**Exact files allowed to change:** `tests/_capabilities.py` (new),
`tests/test_s12_capabilities.py` (new). Nothing else.

**Mechanism — the executor implements exactly these six, no more:**

| probe | mechanism | why not the obvious thing |
|---|---|---|
| `_probe_posix_shell` | `bash -c pwd` in a temp dir; `Path(stdout.strip()) == Path(tmpdir)` | `shutil.which("bash")` is the bug (§1.4) |
| `_probe_posix_modes` | write file, `chmod 0o600`, re-`stat`, assert `st_mode & 0o777 == 0o600` | NTFS accepts the call and ignores it — must round-trip |
| `_probe_posix_paths` | `os.sep == "/"` | cheap, total, no FS access |
| `_probe_symlinks` | `os.symlink` in a temp dir, catch `OSError`/`NotImplementedError` | Developer Mode is a runtime capability, not a platform fact |
| `_probe_tmux` | `shutil.which("tmux") is not None` | binary genuinely absent on Windows; nothing subtler needed |
| `_probe_stable_tmpdir` | `"~" not in str(Path(tempfile.gettempdir()))` | detects 8.3 short paths (`836D~1`) which break equality asserts |

Each is `@functools.cache`d and wrapped `try/except Exception: return False`.

**Production practice:** probes must not write outside `tempfile`, must not
depend on repo state, and must complete in well under a second (one `bash -c`
per session, cached). They run at **import time of the constants**, i.e. during
collection — so a raising probe would abort the entire suite. That is why D3's
`except` is mandatory rather than defensive style.

**Failure behaviour:** probe raises → returns False → tests skip. Degrade to
"don't run", never to "crash collection". A False probe is always the safe
direction; a True probe on an incapable host produces a confusing test failure,
which is why each probe tests the *effect*, not the *precondition*.

**DoD (concrete):**
- `tests/test_s12_capabilities.py` asserts all six return `True` on Linux
  (this sandbox) — if any is False here, the probe is wrong, not the host.
- For each probe, one test monkeypatches its dependency away and asserts `False`
  (`shutil.which → None`; `os.symlink → raises OSError`; `os.sep → "\\"`;
  `subprocess.run → returns MSYS-style '/c/tmp/...'`).
- One test asserts a raising probe returns `False` and does not propagate (K7).
- `uv run mypy` clean — the module is inside `files = ["src", "tests"]` (D7).

**Tests-writing class:** C1.
**Producer kill-check target:** `_probe_posix_shell` — patch it to return the
MSYS string and confirm the constant flips to skip; this is the single
behaviour the whole slice rests on.

### S12.3 — Apply markers per the S12.1 attribution

**Current source-verified behaviour.** There are **24** `@pytest.mark.skipif(
shutil.which("bash") is None, ...)` decorators across **7** test files
(`test_cli.py` 9, `test_hygiene_hooks_install.py` 7, `test_inner_loop_tools.py`
3, `test_inner_loop_runtime.py` 2, `test_deploy_scripts.py` 1,
`test_fa_update_script.py` 1, `test_inner_loop_runtime_limits.py` 1). An 8th
file, `tests/test_authoring_rules_tests.py`, contains the string **twice but as
fixture data inside `test_pytest_mark_skipif_is_not_flagged`** (lines 134/139) —
it is the V4 rule's own regression corpus, not a guard.

**RV7 — do NOT blanket-replace the 24 guards.** Measured against the operator
log: **11 of the 24 bash-guarded tests PASS on Windows.** Replacing their guard
with `requires_posix_shell` would newly skip 11 currently-working tests —
deleting live Windows coverage in a slice whose entire purpose is to preserve it.

The discriminator is *how* the test uses bash, and it is mechanical:

| | uses bash as | Windows result | correct marker |
|---|---|---|---|
| `test_pre_push_runs_full_check_by_default` (+10 others) | a **subprocess interpreter** for a script; assertions read a log file / exit code | **PASSES** | keep `which("bash")` — the existing predicate is exactly right |
| `test_run_bash_tool_runs_in_workspace` (+12 others) | a **path-speaking shell**; assertions compare shell output to a host path (`assert stdout.strip() == str(tmp_path)`) | **FAILS** (`/c/...` vs `C:\...`) | replace with `requires_posix_shell` |

**Rule for the executor:** replace the guard **only** where the test asserts on a
path that crossed the shell boundary, or where S12.1 attributed it to B1.
Otherwise leave `which("bash")` untouched. When in doubt, the S12.1 attribution
table decides — never the file name.

**Exact files allowed to change:** the 7 guard files above plus the files named
in the S12.1 attribution. **`tests/test_authoring_rules_tests.py` is explicitly
OUT OF SCOPE** — editing its fixture strings would silently weaken the V4 rule's
own test corpus.

**Failure behaviour:** if a marker is applied to a passing test, K6 catches it on
Linux only if that test also passes on Linux; the Windows-side proof is S12.5's
skip count, which must be **≈107, not ≈118**. An overshoot of ~11 is the
signature of this exact mistake — call it out by name in the S12.5 report.

**DoD:** `git diff --numstat -- src/` empty; Linux run still `2428/15/1`; the 11
Windows-passing bash tests still **run** on Windows (verified by name in the
S12.5 `-rs` output, not by count alone).
**Tests-writing class:** C0p (parity).
**Producer kill-check target:** for each of the 13 replaced guards, forcing
`_probe_posix_shell → False` must skip it (K1); forcing it True must let it
attempt to run.

### S12.4 — CT3 meta-test

`tests/test_s12_marker_hygiene.py`: AST-walk `tests/`, assert every `skipif`
reason names a capability; assert zero `pytest.mark.skip` / non-strict `xfail`.
**AST, not regex** (house rule; regex would trip on reason strings in
docstrings).
**Tests-writing class:** C2.

### S12.5 — Kill-check sweep (§6) and Windows verification

Operator re-runs `just check`. Expect **0 failed, ~107 skipped**.
**Tests-writing class:** C3.

---

## 6. Kill-checks — mandatory, per marker

Board lesson: *"a kill-check that does not fail is a claim about the
kill-check"*, and *"run the kill-check; don't trust it"*.

| # | force | expected | proves |
|---|---|---|---|
| K1 | `_probe_posix_shell → False` on Linux | +15 skips, 0 failures | B1 attribution exact |
| K2 | `_probe_posix_modes → False` | +11 skips | B2 exact |
| K3 | `_probe_tmux → False` | +10 skips | B3 exact |
| K4 | `_probe_posix_paths → False` | +14 skips | B4 exact |
| K5 | `_probe_symlinks → False` | +3 skips | B5 exact |
| K6 | all probes → **True** on Linux | **2428/15/1**, unchanged | **CT2 — no coverage lost** |
| K7 | probe raises `OSError` | returns False, suite still collects | D3 |
| K8 | new test with `@pytest.mark.skip` | CT3 meta-test fails, naming it | S12.4 is live |
| K9 | **apply `requires_posix_shell` to one of the 11 Windows-PASSING bash tests** | Windows skip count overshoots to ~108 and that test name appears in `-rs` | **RV7 is live** — proves over-skipping is detectable, not just asserted |

K6 is the one that matters. If any marker fires on Linux, coverage was deleted.
K9 is its Windows twin: it proves the slice can *detect* the over-skip mistake
rather than merely promising not to make it. Both must produce real output in
§12 — per the board lesson, *"a kill-check that does not fail is a claim about
the kill-check"*, so K9's expected result is a **deliberate failure** that is
then reverted.

---

## 7. Risks and rollback

| # | risk | mitigation |
|---|---|---|
| R1 | **Over-skipping** — a marker hides a genuine bug | K6 + CT2 pin the Linux count at 2428/15/1 |
| R2 | **Under-attribution** — a B7 cascade skipped for the wrong reason | S12.1 gates S12.3; every row cites a log line |
| R3 | **Security tests skipped on Windows** — `test_s10c_artifact_posture` (12) and the sandbox validators never run locally | §10 discloses; Linux CI blocking; documented in HANDOFF |
| R4 | Probe cost on every session | `functools.cache`; one `bash -c pwd` per run |
| R5 | `--strict-markers` breakage | D1 avoids custom marks entirely |
| R6 | Windows box reveals a 7th bucket | expected; S12.5 is operator-gated and iterative |
| R7 | **Coverage floor** — skipping 92 tests costs 1.00 pp (83.22→82.22 vs `fail_under = 80`) | measured (CT4a); 2.22 pp headroom. **Blocks a future ratchet to 85** — must be named in BACKLOG I-28 so the ratchet slice does not break Windows silently |
| R8 | **`fa authoring-check` runs on the operator's box and passes today** — a malformed reason string or a stray `skip` would newly fail it there | S12.4 CT3 meta-test + DoD item 6 run `authoring-check` before handing the patch over |

**Rollback:** revert `tests/_capabilities.py` + the marker commit. `src/` is
untouched, so rollback cannot affect the product.

---

## 8. Verification plan

0. **Coverage floor check (new, from CT4a):** the Windows run must print
   `Required test coverage of 80.0% reached.` A green suite that fails the
   coverage gate is still a red `just check` — this is the failure mode the
   draft would have shipped into.
1. Linux: full suite → **must be 2428 passed / 15 skipped / 1 xfailed**.
2. `uv run just check` → exit 0 (includes `ruff`, `mypy`, `pylint`,
   `authoring-check`, `cli-coverage-floor`).
3. `git diff --numstat HEAD -- src/` → **empty**.
4. K1–K8 executed, actual output pasted into §12.
5. Operator: `just check` on Windows → 0 failed.
6. `uv run fa authoring-check` → 0 diagnostics (V4 compliance, §1.6).

**Instrument checks before trusting any number** (error #7 + this session's
new one):
- `uv run python -c "import fa; print(fa.__file__)"` → `/home/user/repo/src/fa/__init__.py`
- `uv run which pytest` → **must resolve inside `.venv/`**. This session
  `uv sync --frozen` reported *"Checked 76 packages"* while `.venv/bin/pytest`
  did **not exist**, and `uv run pytest` silently fell through to
  `/usr/local/bin/pytest`, reporting a bogus `ModuleNotFoundError: No module
  named 'fa'`. The `import fa` probe passed throughout. One probe is not enough.

---

## 9. Definition of Done

- [ ] 92 failure lines / 85 unique node IDs attributed with citations; zero
      `UNCLASSIFIED`; every ESCALATED row carries a BACKLOG id
- [ ] The 6 `test_s10b_*` escalation candidates (RV8) resolved to
      **defect** or **capability**, with evidence — not silently marked
- [ ] Exactly **13** bash guards replaced; the **11** Windows-passing ones
      left intact and named in the S12.5 `-rs` output (RV7)
- [ ] `tests/test_authoring_rules_tests.py` unchanged (`git diff --numstat`
      shows no entry)
- [ ] Windows skip count ≈**107**; an overshoot to ≈118 means RV7 was violated
- [ ] `tests/_capabilities.py` with 6 probes, all cached, none raising
- [ ] Markers applied; the 8 stale `which("bash")` guards **replaced**
- [ ] Linux: **15 skipped / 1 xfailed** — unchanged. Passed count *rises* by
      exactly the number of new S12 tests (2428 → 2460 = +19 probe +13 hygiene);
      the invariant is the **skip count and coverage**, not the passed count
- [ ] Linux coverage still **83.22%** (markers must not fire on Linux, so the
      number cannot move; any drop means a probe is wrong)
- [ ] Windows prints `Required test coverage of 80.0% reached.` (CT4a / R7)
- [ ] `just typecheck` clean — `tests/_capabilities.py` is under mypy (D7)
- [ ] `git diff --numstat -- src/` empty
- [ ] K1–K8 run, real output recorded in §12
- [ ] CT3 meta-test live and proven by K8
- [ ] `just check` exit 0 on Linux **and** on the operator's Windows box
- [ ] BACKLOG updated: I-11 partial, I-42 opened
- [ ] HANDOFF records what Windows no longer verifies locally (R3)

**Not done if:** the Linux skip count moved, any marker lacks a kill-check, or
any test was skipped without an attributed cause.

---

## 10. Open questions and disclosures

**Disclosure (R3) — what a Windows dev stops verifying locally.** After S12,
these never run on the operator's box: `test_s10c_artifact_posture` (12 —
`0600`/`0700` on-disk secret posture), 4 sandbox validator tests, 3
`secret_paths` traversal tests, 3 symlink-containment tests. All are
security-relevant. They remain enforced by blocking Linux CI and inside the
container, which is the only place the product runs. This is precisely the cost
BACKLOG I-11 flagged; recording it is a requirement of this slice, not a
footnote.

**I-11 closes only partially.** S12 makes the suite *honest* on Windows. It does
not give FA a Windows-native shell backend (`fs_run_cmd`). If native Windows
ever becomes a *product* target, that work is separate and ADR-scale.

**NEW → I-42 (P3):** 11 tests in `test_pty_persistence.py` share a hardcoded
global `base_cwd=Path("/tmp")` instead of `tmp_path`. Fragile under parallel
runs; unrelated to platform. Repro: `grep -c 'Path("/tmp")'
tests/test_pty_persistence.py` → 11.

**Q59 (new, non-blocking):** should CI gain a `windows-latest` matrix entry to
keep these probes honest? Without it, the markers can rot silently — the exact
failure mode I-11's unblock-trigger anticipated. Recommend yes, as a follow-up
slice; not in S12 scope.

---

## 11. Anti-theatre checklist

- [x] Every count in §2 derived from the operator log, not estimated
- [x] The one proposed `src/` change was investigated and **rejected** (§1.5)
- [x] Rejected the simpler `skipif(win32)` design with a stated reason (D2)
- [x] Authoring-rule compatibility checked *before* designing (§1.6)
- [x] `--strict-markers` interaction found before it could bite (§1.7)
- [x] Existing in-repo precedent reused rather than a new pattern (§1.8)
- [x] Negative proof (K6) is the primary DoD, not an afterthought
- [x] Security cost disclosed in §10 rather than buried
- [x] **Review pass found a gate the draft ignored** (`fail_under = 80`) and
      the cost was *measured* (−1.00 pp), not estimated — see §12
- [ ] READY — pending operator review

---

## 12. Review record — 2026-08-02 (second pass over this plan)

Findings from re-reading the code the plan touches, in review order.

| # | finding | severity | disposition |
|---|---|---|---|
| **RV1** | **`fail_under = 80` coverage gate was entirely absent from the draft.** Skipping ~92 tests lowers coverage; the slice could deliver 0 failures and still leave `just check` red. | **HIGH — would have shipped a broken slice** | Measured by deselecting the 85 unique node IDs: 83.22% → **82.22%**, floor 80. Viable, 2.22 pp headroom. Added CT4a, R7, DoD items, verification step 0. |
| **RV2** | `pyproject.toml:162` — `files = ["src", "tests"]`: mypy type-checks `tests/`. A new unannotated helper fails `just typecheck`. | MED | Added D7 + DoD item. |
| **RV3** | No non-`test_*` helper-module precedent exists in `tests/` (only `__init__.py`, `conftest.py`). The draft assumed one. | LOW | D7 now states this explicitly and justifies the import path via the existing `tests/__init__.py` + `pythonpath = ["."]`. |
| **RV4** | `fa authoring-check` **passes on the operator's Windows box today** (log line 40, `exit_code: 0`). This slice edits ~92 files it scans, so a stray `skip` would newly break their gate. | MED | Added R8; DoD already required `authoring-check`, now tied to the Windows handover. |
| **RV5** | `scripts/check_no_mocked_dataclasses.py:50` — `SCAN_DIRS = ("tests",)`. A gate script reads every file this slice touches. | LOW | No conflict (it looks for `MagicMock(spec=...)`), but S12.3 must re-run it; already covered by `just check` in DoD. |
| **RV6** | Bucket counts in §2 summed to 92 only with a `~` on B4/B7; the raw log has **85 unique node IDs** (92 counts parametrised cases separately). | LOW | Clarified here: 92 failure *lines*, 85 unique test IDs, 93 deselected including parametrisation. S12.1 must reconcile both numbers. |
| **RV7** | **S12.3 said "replace the 8 existing `which("bash")` guards".** Two errors. (a) There are **24 decorators across 7 files**, not 8 guards — the 8th file (`test_authoring_rules_tests.py`) holds the string as *fixture data* for the V4 rule's own corpus. (b) **11 of the 24 guarded tests PASS on Windows** — blanket replacement would newly skip 11 working tests, destroying live coverage in the slice meant to protect it. | **HIGH — would have deleted working Windows coverage** | Measured by cross-referencing the 24 guards against the log's FAILED set. S12.3 rewritten with the subprocess-interpreter vs path-speaking-shell discriminator, a 13/11 split, an explicit out-of-scope file, and kill-check **K9** to make the mistake detectable. |
| **RV8** | **S12.1 allowed "cascade" as an attribution.** The 6 `test_s10b_*` failures show a run that *succeeded* (`OK: stopped_by_llm`) yet produced no `events.jsonl` (`cli.py:1909`/`:2486`) — no path, mode, or shell mechanism explains that. The draft would have skipped a possible real product defect. | **HIGH — the slice could have hidden a bug** | S12.1 now forbids "downstream of something" as a reason: a test is either attributed to a **named capability** or **ESCALATED to BACKLOG**. Six candidates named explicitly. |
| **RV9** | Parent §13 mandates *slice scope + explicit non-goals*, *dependency and stop conditions*, and *rollback/artifact handling* in every subplan. The draft had rollback but no non-goals, no depends-on/parallelizable-with, and no stop conditions. | MED — trajectory conformance | Added **§4a** covering all four, matching the S10c/S11 sheet structure. |
| **RV10** | S12.2 named six probes but not their mechanisms, so two executors would build different things (e.g. `os.access(X_OK)` vs a `chmod` round-trip — NTFS passes the former and fails the latter). | MED — executability | S12.2 now specifies each probe's exact mechanism, the reason the naive version is wrong, the import-time/collection risk, and a concrete per-probe DoD. |

**What the review did not change:** the core design (capability probes over
`sys.platform`), the zero-`src/` scope, and the K6 negative proof all survived
scrutiny. §1.5's rejection of the `pty_pool.py` change was re-verified against
source and stands.

**Trajectory check against the parent workplan.** S12 is not in the parent's
step list, which ends at S11. That is correct rather than a deviation: the
parent's §13 protocol defines how *approved slices* get subplans, and S12 exists
because I-11's recorded unblock-trigger fired ("First user reports running FA on
native Windows without WSL"). S12 serves parent goals G4/G5 (a trustworthy local
gate) by repairing the gate the parent's own hook depends on. It does **not**
touch the runtime authority, session lifecycle, or deployment contracts that
S5–S11 establish — verified by the zero-`src/` constraint. **S11 remains the
next production action; S12 is a prerequisite only for the operator's ability to
push, not for S11's correctness.**

**Second-pass verdict.** The first draft was structurally sound but contained
**two HIGH findings that would each have produced a bad outcome**: RV7 would
have deleted 11 working tests, and RV8 would have buried a possible product
defect behind a skip marker. Both came from reading the code and the log rather
than re-reading the plan — which is the argument for the review step existing at
all. The plan is now executable by an agent without further interpretation; the
remaining risk is concentrated in S12.1, which is deliberately gated as
analysis-only with an escalation path.

**Honest assessment of residual risk.** The thin coverage margin (RV1) is the
weakest point. It is not a reason to block the slice, but it means **S12 and any
future coverage ratchet are now coupled** — I-28 must be updated to say that
raising the floor above ~82 makes native-Windows development impossible without
first doing the real work behind I-11 (a Windows shell backend). That coupling
did not exist before this slice and is created by it; it should be an explicit,
recorded consequence rather than a surprise discovered later.

---

## 13. Execution record — 2026-08-02

Executed S12.0 → S12.4 on `s7-rebase`. Three commits, `tests/` and `worklogs/`
only. **`git diff --numstat -- src/` is empty**, as designed.

| step | commit | result |
|---|---|---|
| S12.0 baseline | `34ee6fb` | 2428/15/1, 83.22%; 92 lines / 85 unique IDs pinned |
| S12.1 attribution | `34ee6fb` | **85/85 attributed, 0 UNCLASSIFIED, 0 escalations** |
| S12.2 probes | `268ca22` | 6 probes, 19 tests, 0 `noqa` |
| S12.3 markers | `d7e9499` | 85 marked; 13 guards replaced, 11 kept |
| S12.4 CT3 gate | `d7e9499` | 13 tests, AST-based |

### Final gate (Linux)

```
lock-check · dependency-contract-check · ruff check · deptry ·
pylint 10.00/10 · mypy 326 files · authoring-check 0 diagnostics ·
contract-check · log-kind-check · no-mocked-dataclasses ·
2460 passed, 15 skipped, 1 xfailed · coverage 83.22% ·
cli-coverage-floor 27/27 · pyrefly 0 errors
```

**CT2 held exactly:** 15 skipped and 83.22% are *byte-identical* to the
pre-slice baseline. No marker fires on Linux; nothing was silently deleted.

### What execution found that the plan did not

**EX1 (HIGH) — the `tmux` probe in the plan was wrong.** §S12.2 specified
`shutil.which("tmux")`. Measured: tmux is **absent** on this Linux sandbox, yet
all 13 `test_pty_persistence` tests **pass** via the `pexpect` fallback
(`pty_pool.py:125`). Shipping the specified probe would have skipped **26 tests
that currently pass on Linux and in CI** — precisely the coverage deletion CT2
exists to prevent. The probe became `has_pty_backend` = "tmux **or** a usable
`pexpect.spawn`". Caught by the K6 positive assertion, not by review.

**EX2 (HIGH) — all 7 RV8 escalations were one test-fixture bug, not product
defects.** `monkeypatch.setenv("HOME", ...)` does not move the home directory on
Windows: `ntpath.expanduser` prefers `USERPROFILE`. Proven directly:

```
os.environ['HOME']='/fake/home'; os.environ['USERPROFILE']=r'C:\Users\Real'
ntpath.expanduser('~')  ->  C:\Users\Real      # HOME ignored
```

So the run wrote `events.jsonl` correctly — to the operator's **real** `~/.fa` —
and the test looked in `tmp_path`. Corroborated independently: the S10c posture
test reported real artifacts (`'session-log\posture\events.jsonl': '0o666'`)
it should never have been able to see. **No product defect. But the suite
leaks into the developer's real state directory on Windows → I-43.**

**EX3 (MED) — bucket deltas must be reconciled against *collected nodes*, not
unique IDs.** K2 showed +13 where 11 was expected and K4 +39 where 34 was
expected. Cause: parametrisation (`test_ignores_non_absolute_override` is one ID
and five nodes; `test_s10c_named_artifacts_are_0600` is one ID and three), plus
one test that already carried a pre-existing `skipif`. Every delta reconciles
exactly once counted properly. Recorded because the naive count looks like
over-skipping and would invite a wrong "fix".

**EX4 (MED) — my own hygiene test was vacuous on first run.** The anti-vacuity
guard fired immediately: the reason scan found **20** literal reasons where the
floor assumed more, and the token `"only"` made `"win32 only"` wrongly *pass*
CT3. Both fixed (`"semantics only"`; floor `>= 15`). The guard justified itself
within minutes of being written.

**EX5 (LOW, pre-existing) — `ruff format --check .` fails on 39 markdown files.**
Present at session-start `cf1a980` (39 files) and unrelated to this slice: they
are `.md` docs under `knowledge/` and `worklogs/` whose fenced Python blocks ruff
reformats. **All 353 tracked `.py` files are clean.** The operator's Windows run
reported `643 files already formatted`, so this is sandbox-local (ruff sees more
files here). Two files I authored were in the delta and have been formatted; the
other 39 are out of scope → **I-44**.

### Windows simulation

Forcing all five POSIX probes false (the operator's condition):

```
2362 passed, 104 skipped, 1 xfailed
Required test coverage of 80.0% reached. Total coverage: 82.27%
```

**Coverage clears the floor with 2.27 pp of headroom**, matching the plan's
predicted 82.22% (CT4a) and the operator's observed 82.52%. The 8 "failures" in
that run are `test_s12_capabilities.py` correctly detecting the sabotage — i.e.
CT2 doing its job. The real Windows run will not have them.

### DoD status

- [x] 85/85 attributed, 0 UNCLASSIFIED, every row cites evidence
- [x] All 7 escalations resolved with evidence (EX2) — none silently marked
- [x] Exactly 13 guards replaced; 11 Windows-passing guards intact
- [x] `tests/test_authoring_rules_tests.py` unchanged
- [x] Linux 15 skipped / 83.22% — unchanged
- [x] `just typecheck` clean (326 files)
- [x] `git diff --numstat -- src/` empty
- [x] K1–K9 executed with real output
- [x] CT3 gate live, proven by K8
- [x] 0 `noqa` added
- [ ] Windows `just check` green — **operator-gated**
- [x] BACKLOG updated (I-11 partial, I-42/43/44 opened)

---

## 14. Self-review record — 2026-08-02 (adversarial pass over the shipped code)

Re-read the shipped implementation against the plan and the session guidelines,
re-deriving every number from the tree rather than from the execution record.

### RS1 (HIGH, FIXED) — CT3 was blind to the reasons it polices

`_test_files()` globbed `test_*.py`. All six `requires_*` reason strings live in
`tests/_capabilities.py`, which does not match that glob, so **the ~85
capability skips this slice produces — its entire output — were unchecked by the
gate written to check them.** A second hole: `_skipif_reasons()` collected only
inline `reason=` kwargs, never module-level `*_reason = "..."` constants, which
is the form `_capabilities.py` uses.

Proven before fixing, not argued: setting
`posix_paths_reason = "skipped on windows"` passed **all 13** hygiene tests.
After the fix the same sabotage fails, naming `_capabilities.py:238`.

Fixed in `0d6f939`. Reasons scanned **20 → 26**. This is the same failure class
as the board lesson *"simplification can silently convert a live check into a
vacuous one"* — the gate looked strict and was partly decorative.

### RS2 (MED, RESOLVED — no defect) — the 3-skip discrepancy

The execution record claimed the kill-check deltas "reconcile exactly". Re-derived
from the tree: 85 marked functions expand to **92 collected nodes**, predicting
`15 + 92 = 107` Windows-sim skips, but only **104** were observed. Three
unaccounted.

Root cause, fully closed:

| | nodes | why |
|---|---:|---|
| capability-reason skips observed | 89 | |
| `requires_stable_tmpdir` | +2 | the sim forced only **5** of 6 probes false; `has_stable_tmpdir` stayed True |
| `test_executable_script_modes_are_pinned` | +1 | already skipped under its **pre-existing** exec-bit `skipif`, so it reports that reason, not the new one |
| **total** | **92** | ✅ |

And `104 = 89 capability + 12 shellcheck + 1 exec-bit + 2 runtime-server`.
**No defect** — but the original "reconciles exactly" was asserted rather than
computed. Real Windows will skip ~106, not 104, because `stable_tmpdir` is
genuinely false there.

### RS3 (LOW, FIXED) — stale DoD target

The DoD read "Linux: **2428 passed** — unchanged", which the slice necessarily
violates: it adds 32 tests (19 probe + 13 hygiene), so 2428 → **2460**. The real
invariant is the **skip count and coverage**, both unmoved. DoD text corrected
so a future reader does not treat a correct result as a failed criterion.

### Verified clean (no change needed)

| check | result |
|---|---|
| marker ↔ failure bijection | **85 marked, 85 Windows failures, 0 over-skip, 0 unmarked** — verified in both directions against the operator log |
| `src/` untouched | `git diff --numstat 34ee6fb~1..HEAD -- src/` → **0** |
| RV7 split intact | 11 guards remain (2+1+1+7); `test_authoring_rules_tests.py` **0** lines changed |
| no `noqa` added | 0 in all three new files; the 6 diff matches are prose in docs |
| `type: ignore` justified | 2 × `import-untyped` for `pexpect`, which ships no stubs — matches production's own convention at `pty_pool.py:127`. Removing them fails mypy, so they are load-bearing, not cosmetic |
| probes cached | all 6 expose `cache_clear` |
| `has_posix_paths` lacks try/except | **correct** — `os.sep` is a module constant; a guard there would be dead code |
| `_PROBE_ERRORS` completeness | `TimeoutExpired`/`CalledProcessError` ⊂ `SubprocessError`; `FileNotFoundError`/`PermissionError` ⊂ `OSError`; **`UnicodeDecodeError` ⊂ `ValueError`** — verified the probe survives the exact cp1251 decode failure that started this thread |
| marker/cache interaction | markers are **import-time snapshots**; the test fixture's `cache_clear()` cannot retroactively alter any skip decision |
| MSYS false-positive | `PureWindowsPath("/c/Users/x") != PureWindowsPath("C:/Users/x")` — the probe cannot accidentally pass on Windows |
| self-healing | markers are `skipif(not probe())`, so a future Windows shell backend un-skips all 85 automatically; the rejected `sys.platform` design never would |
| gate | lock-check · dependency-contract · typecheck · authoring-check (0 diagnostics) · contract-check · log-kind · no-mocked-dataclasses · cli-coverage-floor **27/27** all PASS |
| suite | **2460 passed / 15 skipped / 1 xfailed · 83.22%** — skip count and coverage byte-identical to baseline |

**`lint` still fails on the 39 pre-existing markdown files (I-44).** Re-confirmed
by differencing against session-start `cf1a980`: **none of the 39 are mine**, and
all **354** tracked `.py` files are clean. Out of scope by decision, tracked.

### Assessment

The slice is production grade with RS1 fixed. RS1 is the finding that mattered:
a gate that cannot fail is worse than no gate, because it is *believed*. It
survived the plan review, the execution, and the first write-up — and was caught
only by sabotaging the artifact the gate was supposed to protect. The lesson
generalises beyond this slice: **when a check and the thing it checks live in
different files, verify the check's scope covers the thing.**

---

## 15. Windows verification round 2 — 2026-08-02

Operator applied the patch on a **different Windows machine** and ran the gate.

**92 → 9 failures. 107 skipped (predicted ~106). Coverage 81.85%, floor 80 — the
coverage gate PASSED,** confirming CT4a/R7 held with 1.85 pp of headroom.

Every static gate passed there: `ruff check`, `ruff format --check` (**650 files
clean** — I-44 does not reproduce on their box), `deptry`, `pylint 10.00/10`,
`mypy 326`, `authoring-check 0`, all four contract scripts.

Skip reasons rendered exactly as designed, e.g.
`needs a POSIX shell whose paths match the host (Git Bash reports /c/... for C:\...)`.

### The machine changed, which is why new defects appeared

| | round 1 | round 2 |
|---|---|---|
| user | `Администратор` (Cyrillic) | `r.kolomeichuk.ao` (ASCII) |
| Python | 3.13.13 | **3.14.5** |
| 8.3 short path | present (`836D~1`) | absent |
| Developer Mode | **off** | **on** |

Two capabilities that were *false* in round 1 are *true* in round 2
(`symlinks`, `stable_tmpdir`). This is the capability-probe design working as
intended — the same file behaves differently on two Windows boxes because it
asks about capabilities, not about `sys.platform`. A `skipif(win32)` design
would have hidden both.

### The four findings

**RS4 — 6 of the 9 failures were my own bug (HIGH).**
`test_every_probe_is_true_on_this_posix_host` and
`test_all_marker_constants_are_present_and_do_not_skip_here` asserted "every
capability is present" **unconditionally**. On Windows five of six are
legitimately absent, so the slice's own test file failed six times and reported
a healthy platform difference as a defect. **This is the exact anti-pattern the
slice exists to remove**, reintroduced one directory away from the fix. Both are
now gated on `requires_posix_paths`; a new *ungated*
`test_marker_constants_exist_on_every_platform` preserves the
platform-independent half (markers exist, are boolean, carry a reason) so
Windows does not lose that check entirely.

**RS5 — a real product finding (MED) → I-45.**
`install.py:63` forces `shutil.copy2` on `win32` because Git for Windows will
not execute a symlinked hook. So an installed hook is **never** a symlink there,
even with Developer Mode on, and `_install_one`'s idempotency test
(`target.is_symlink()`) is false → `FileExistsError` on the second install.
`requires_symlinks` was the wrong predicate: the test needs *symlink installs*,
not *symlink creation*. Added `installs_hooks_as_symlinks()`. **The product bug
is logged, not marked away** — on Windows a re-install errors and the hook keeps
stale content.

**RS6 — a capability I had missed (MED).**
Tests hardcode `python3`. Windows ships an **App Execution Alias** at
`python3.exe` that prints *"Python was not found… Microsoft Store"* and exits
`9009`. `shutil.which` finds it, so presence is not enough — the probe runs it
and requires real output. 19 call sites exist; only the one that surfaced is
marked, the rest are latent.

**RS7 — an incomplete marker (LOW).**
`test_s10c_tighten_pass_skips_symlinks` needs **both** symlinks *and* POSIX
modes: its setup calls `chmod(0o644)`, a no-op on NTFS, so the oracle compared
`0o666` to `0o644`. The symlink guard in `paths.py:123` is correct and was not
touched; only the marker was under-specified.

### Method note — a sabotage harness that lied

I built a Windows simulation by monkeypatching `os.chmod` to a global no-op and
forcing `sys.platform`. It produced **51 failures**, including six
`test_pre_commit_*` tests that **pass on the real Windows box**. The blunt
`chmod` stub broke unrelated fixtures, and overriding `sys.platform` broke
imports. The harness was discarded in favour of patching only the primitives the
probes read, then cross-checking each of the seven probe values against the
operator's actual log. *A simulation that disagrees with the ground truth it is
meant to model is evidence about the simulation.*

### Status

Linux after the fixes: **2461 passed / 15 skipped / 1 xfailed** — skip count and
coverage unchanged, CT2 still exact. Expected on the operator's box next run:
**0 failed**, ~113 skipped.

---

## 16. Proactive Windows hazard audit — 2026-08-02

Rather than wait for a fourth machine to surface the next defect, I swept the
tree for every failure mode of the same *shape* as the three already found.
Ten hazard classes; **one live defect, two latent, seven clean.**

### RS8 (HIGH, FIXED) — secret tests that pass vacuously on Windows

Generalisation of RS6. A test that (a) runs a POSIX-only command and (b) asserts
a secret is **absent** is satisfied by an empty string. Every probe here ends in
`|| true`, so a missing binary yields exit 0 and no output — the assertion holds
while verifying nothing.

**Seven affected, all reporting PASS on the operator's box:**

| file | tests |
|---|---|
| `test_run_bash_env_scrub.py` | `printenv`, `env`, `/proc/self/environ`, `python3` scrub tests |
| `test_secret_exfiltration.py` | `test_bash_cannot_exfiltrate_key` (**12 parametrised commands**), `test_bash_env_has_no_credential_named_vars` |
| `test_s6_subagent_fidelity.py` | persisted-envelope and researcher-role masking |

Proved before fixing: pointing the `printenv` probe at a nonexistent binary
keeps the assertion **green with env scrubbing entirely bypassed**.

Fix: every probe echoes `__FA_PROBE_RAN__` and asserts it arrived. Kill-check
confirmed — the sabotaged probe now fails with
`probe did not run: sentinel '__FA_PROBE_RAN__' missing from stdout`.

Three sibling tests in `test_s6_subagent_fidelity.py` were **left alone**: they
already carry a positive control (`***REDACTED***`, `"withheld"`, or an explicit
`assert KNOWN_SECRET in payload` pre-check). Adding a second would be noise.

### Latent, recorded not fixed

**L1 — 12 more `python3` call sites.** Only the one that surfaced is marked. The
rest sit inside tests already gated by `requires_pty_backend` /
`requires_stable_tmpdir`, so they are unreachable on Windows today — but the
gating is incidental, not intentional. If a future slice removes one of those
markers the `python3` hazard reappears. → **I-46**.

**L2 — I-42 unchanged.** The 11 `base_cwd=Path("/tmp")` sites are all inside
`requires_pty_backend` tests, so they cannot bite on Windows now.

### Verified clean — seven classes with no action needed

| # | hazard | finding |
|---|---|---|
| E | **CRLF line endings** | `.gitattributes` is `* text=auto eol=lf`; `git check-attr` confirms `eol: lf` on scripts, hooks and tests. Already neutralised — which is why three Windows rounds never saw it |
| F | **case-insensitive collisions** | `git ls-files \| tr A-Z a-z \| uniq -d` → **empty** |
| G | **filenames illegal on NTFS** (`: * ? < > \| "`) | **none** tracked |
| H | **POSIX-only stdlib** (`pwd`, `grp`, `fcntl`, `termios`, `resource`, `os.getuid`) | **zero** imports in `src/` or `tests/` |
| I | **POSIX signals / process model** (`SIGKILL`, `SIGALRM`, `os.fork`, `os.setsid`, `preexec_fn`) | **zero** occurrences in `src/` |
| J | **`MAX_PATH` 260** | longest tracked path 93 chars + operator root 56 = **149**. 111 chars of headroom |
| B | **other hardcoded binaries** | only `git` (52 sites), present on their box and exercised successfully |

### Why this audit was worth doing separately

The three defects found so far each needed a *specific machine* to appear:
Cyrillic username, then Developer Mode, then a Store-alias `python3`. RS8 needed
none — it was reachable by reasoning about the *shape* of the assertion, and it
is the most dangerous of the four because it produces **green** output. The
others announced themselves with a traceback; this one would have sat there
claiming the secret-scrubbing boundary was verified on Windows when it was not.

*A failing test tells you something is wrong. A vacuous test tells you nothing,
while looking exactly like a test that tells you something is right.*
