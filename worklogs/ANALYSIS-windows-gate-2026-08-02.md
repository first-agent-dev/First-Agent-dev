# Windows `just check` failure analysis — 2026-08-02

**Input:** operator log `git-error-1785668071658.md` (4,681 lines), Windows 11,
`C:\Users\Администратор\Documents\GitHub\First-Agent-dev`, CPython 3.13.13 win32,
pytest 9.0.3, via `uv`.

**Verdict: this is NOT a third encoding defect, and NOT a regression from the
S11 patch stack. It is BACKLOG item I-11 firing its documented unblock-trigger.**

---

## 1. The two encoding defects are FIXED — confirmed by this log

Every gate that crashed in the previous two runs now passes on the operator's box:

| gate | run 1 | run 2 | run 3 (this log) |
|---|---|---|---|
| `check_dependency_contract` | `UnicodeEncodeError` | pass | **PASS** (prints `✅` ×3, `PASS:`) |
| `check_producer_consumer_contract` | — | `UnicodeDecodeError` @ line 146 | **PASS** (`PASS: All non-dormant EventTypes...`) |
| `check_log_kind_contract` | — | — | **PASS** (`PASS: All LogKind contracts satisfied`) |
| `check_no_mocked_dataclasses` | — | — | **PASS** |

Also green on Windows: `uv lock --locked`, `ruff check`, `ruff format --check`
(643 files), `deptry`, `pylint` **10.00/10**, `mypy` **323 files**,
`fa authoring-check` (`exit_code: 0`).

The `\u2705` characters render correctly in the log. `force_utf8_stdio()` and the
`encoding="utf-8"` read fixes both hold on the real cp1251 box.

**The gate got 8 stages further than it ever has.** It now dies in `test`.

---

## 2. What actually failed

`92 failed, 2334 passed, 17 skipped, 1 xfailed in 377s`, then
`error: recipe 'test' failed on line 117`.

Root causes, bucketed from the 86 traceback sections:

| # | root cause | ~count | nature |
|---|---|---|---|
| A | **`bash` / PTY absent** — `RuntimeError: workdir C:\tmp not exists`, `bash exited -1 / No fallback available` | ~30 | test harness assumes POSIX shell |
| B | **POSIX file modes** — `assert 438 == 384` (`0o666` vs `0o600`), `0o777` dirs, `missing executable bit` | ~14 | Windows has no `st_mode` perm bits |
| C | **Path separator** — `'src\\fa\\dead.py' == 'src/fa/dead.py'`, `'/\\' == '/'`, `is not in the subpath of` | ~14 | tests compare literal `/` strings |
| D | **8.3 short paths / `TEMP`** — `C:\Users\836D~1\...` vs `C:\Users\Администратор\...` | ~6 | `tempfile` returns the short form |
| E | **Symlinks** — `FileExistsError: ... exists and is not a symlink`, `copy-fallback target must be executable` | ~4 | needs Developer Mode |
| F | **Shell-script tests** — `awk: cannot open 'C:UsersАдминистраторDocuments...'` (backslashes eaten by the shell) | ~4 | `.sh` under a Windows path |
| G | **Cascades** from A/B/C (`fa run` smoke → `assert 1 == 0`, s10b parity, entrypoint) | ~20 | downstream of the above |

### These are test-harness failures, not product defects

Verified by reading source. Example — the scariest-looking one,
`test_lexical_abs_path_collapsing`, `assert '/\\' == '/'`:

```python
# src/fa/sandbox/secret_paths.py:86
def _lexical_abs(p: Path) -> str:
    for part in p.parts:
        ...  # on Windows, Path("/").parts == ('\\',)
    return "/" + "/".join(parts)  # -> "/\"
```

`pathlib.Path` is `WindowsPath` on win32, so `.parts` yields `'\\'` instead of
`'/'` and the `part == "/"` guard misses. The **containment logic is correct**;
it is parameterised on POSIX path syntax, which is the only syntax the sandbox
ever sees (the sandbox runs in a Linux container — `Dockerfile.fa`,
`docker-compose.fa.yml`, `user: "1000:1000"`). Same story for
`validate_rm_denies_home` and the `0600` posture tests: **the artifacts they
guard only ever exist inside the container.**

**No security control is weaker than believed on the deployment target.**

---

## 3. Not a regression from this patch stack

- **21 of the 28** failing test files were **not touched** by the 103 commits.
  Only `test_s7_cli_run_paths.py` (+14/−1) and `test_stats_global_wiring.py`
  (+21/−8) were modified at all, and both fail for reason C/G, not for anything
  the diff changed.
- The three **new** files that fail (`test_s10b_cli_parity`,
  `test_s10c_artifact_posture`, `test_s10b_complexity_ratchet`) fail for
  reason B/C — `test_s10c_artifact_posture` is *by construction* a POSIX-mode
  test (it asserts `0o600`/`0o700`), so it cannot pass on NTFS.
- Re-ran all five locally after a **corrected** `uv sync`: **151 passed.**
- Linux CI (`advisory.yml`, `runs-on: ubuntu-latest`, `uv run just check`) is
  the blocking authority and is green.

**Conclusion: pushing this stack does not break anything. The pre-push hook is
running a Linux-targeted suite on a Windows host.**

---

## 4. This is BACKLOG I-11, and its trigger just fired

`knowledge/BACKLOG.md:1129` — *"I-11 — Cross-platform test suite (Windows
without bash / Developer Mode)"*, deferred 2026-06-04. It predicted categories
A, E and the chunker skip precisely. Its recorded unblock-trigger:

> **Unblock-trigger:** First user reports running FA on native Windows without
> WSL, OR a CI job is added that runs on `windows-latest` and fails.

That is exactly what happened. Its recorded blocking question is a **policy
choice, not an implementation detail**, so per the stop rule it is promoted to
**Q58** rather than answered unilaterally.

> **Blocked-on:** Decision on whether FA targets POSIX-only environments (WSL,
> Git Bash, etc.) or native Windows.

Current evidence that FA is POSIX-only *by design*: the product ships as a Linux
container; `scripts/fa-entrypoint.sh`, `scripts/fa`, `scripts/fa-clean-rebuild.sh`
are bash; `fs_run_bash` is the only shell tool; the S11 deployment target is
docker-compose with `read_only: true` rootfs.

---

## 5. Q58 — options

**Q58: what is the supported development platform, and what should the
Windows pre-push hook do?**

| opt | action | effort | honest? |
|---|---|---|---|
| **1** | **Operator develops in WSL2** — clone inside the WSL filesystem, run the gate there. Zero code change; the gate becomes a true CI mirror. | ~30 min, one-time | ✅ fully |
| **2** | **Capability-gate the suite** — add `tests/conftest.py` autouse markers: `requires_bash`, `requires_posix_modes`, `requires_symlinks`, `requires_posix_paths`. ~92 tests SKIP on Windows. Gate goes green. | ~1 slice | ⚠️ Windows dev never validates containment locally — I-11 flags this as the real cost |
| **3** | **Port the suite to be path/mode agnostic** — `Path.as_posix()` everywhere, `os.stat` shims, `cmd.exe` backend for `fs_run_bash`. | multi-slice, ADR-scale | ✅ but large, and buys nothing for a Linux-only product |
| **4** | **Scope the hook** — pre-push runs the full gate on POSIX; on Windows it runs everything *except* `test` and prints a loud "full suite runs in CI / WSL" notice. | ~small | ⚠️ weakens the local gate |

**My recommendation: option 1 now, option 2 only if you must stay native.**

Rationale, in the spirit of the lesson already on the board — *"a gate that
fails when the thing it guards is healthy is worse than no gate"*. Right now the
hook is doing exactly that: 2,334 tests pass, every static gate passes, Linux CI
is green, the product is healthy — and the hook blocks the push. Option 2 makes
the gate green by making it *quieter*, which is the same failure mode in a nicer
suit: it would have hidden the two real encoding bugs the operator just found.
Option 1 makes the gate *true* — WSL2 runs the identical Linux suite the
container and CI run, so a green hook means something again.

**Escape hatch for right now (already built in, `src/fa/hygiene/hooks/pre-push`):**

```
FA_HOOK_SKIP_FULL_CHECK=1 git push origin main:main
```

This is a legitimate use: the gate's own authority (Linux CI) is green, and the
failures are platform artifacts, not defects. The hook's docstring reserves this
for "exceptional operator cases" — a suite that cannot physically pass on the
host qualifies.

---

## 6. Sandbox instrument note (error #7 recurrence)

At session start `uv sync --frozen --extra dev` reported *"Checked 76 packages
in 3ms"* and `import fa` resolved correctly — but **`.venv/bin` contained no
`pytest`**, and `uv run pytest` silently fell through to
`/usr/local/bin/pytest`, which reported `ModuleNotFoundError: No module named
'fa'`. The `import fa` probe alone is **not sufficient**; it passed while the
venv was half-populated. A second `uv sync` installed the dev extras properly.

**Added instrument check: `uv run which pytest` must resolve inside `.venv/`
before trusting any test result.**
