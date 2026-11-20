# Q-V2-ACC-1 — acceptance closure and trusted external inputs: source audit (2026-11-20)

**Status: SOURCE AUDIT — answers Q-V2-ACC-1 for STEP9A/SLICE3; Q-V2-ACC-2 remains open and is escalated
separately.** No implementation, no fixture, no host claim. Grounded on the checkout at `b0358ea` plus
E556's reproduced gate bank. The selected boundaries stay as ratified: fixed `acceptance/tests/` root
inside `worklogs/<slug>/`, artifact C (new schema, no v1 fallback), visibility mode A (read-only
inspection), no second runner.

## 1. How the harness runs acceptance tests today (verified)

| Fact | Source |
| :--- | :--- |
| The kill/nodeid capture command is `python -m pytest {paths} -p fa.inner_loop.junit_nodeid_plugin --junitxml={report} -q`. There is **no** `-c`, no `--rootdir`, no `-p no:cacheprovider`, no `-o` override. | `slice_verification.py:162` |
| The in-band variant (`slice_verification.py:168`) is the same pytest invocation wrapped to write the report inside the cell. | `slice_verification.py:164-175` |
| Every verify command runs with `cwd = _workspace_cwd(workspace)`, i.e. the workspace root. | `slice_verification.py:317, 612, 622` |
| Nodeid authority comes from the JUnit adapter's exact `Item.nodeid` property plus a run-id binding; a collection/setup/teardown error is classified as an error, never a kill. | `slice_verification.py:686-711`, `junit_nodeid_plugin.py` |
| The repository pytest configuration lives in `pyproject.toml [tool.pytest.ini_options]`: `addopts` (`-ra`, `--strict-config`, `--strict-markers`, `-m "not execution_host and not live_e2e"`), `testpaths = ["tests"]`, `markers`, `filterwarnings`. | `pyproject.toml` |
| There is **no** root `conftest.py`; `tests/conftest.py` exists and would not be an ancestor of `worklogs/<slug>/acceptance/tests/...`. | repository layout |
| The in-repo pytest plugin `fa.inner_loop.junit_nodeid_plugin` is loaded by name from the installed package, so it is part of the image, not of the workspace. | `slice_verification.py:61, 162` |

**Consequence.** With today's argv, what pytest actually uses for an acceptance test under
`worklogs/<slug>/acceptance/` is decided by files the coder can edit: the workspace `pyproject.toml`
(addopts, markers, filterwarnings, `testpaths`) and any `conftest.py` between rootdir and the test. So
"seal the test bytes" alone is **not** custody — the run configuration is part of the oracle. This is
exactly the gap Q-V2-ACC-1 asks to close.

## 2. Answer to Q-V2-ACC-1, part 1 — what is inside the closure

**Inside `worklogs/<slug>/acceptance/` (planner-authored, sealed, immutable after admission):**

- `tests/**` — the acceptance tests themselves.
- `support/**` — helpers/fixtures imported by those tests.
- `conftest.py` (only at the acceptance root, no deeper conftest) — the planner's own fixtures.
- `pytest.ini` — the acceptance run configuration (see §3).
- `manifest.json` — the closure manifest: per-file path, sha256, size, mode; the ordered `TEST-ID`
  table with `INV`, `CT`, `selector`, resolved `nodeid`; the closure digest.

**Trusted external inputs (must be pinned by identity, not bytes, because they are image content):**

| Input | Pin |
| :--- | :--- |
| The pytest runner argv | exact literal string built by the harness (not planner text): `python -m pytest <sealed tests> -c <sealed>/pytest.ini --rootdir <sealed> -p fa.inner_loop.junit_nodeid_plugin -p no:cacheprovider --junitxml=<run-scoped report> -q` |
| The nodeid plugin | module path + its own source digest recorded in the bundle (`fa.inner_loop.junit_nodeid_plugin`) |
| Interpreter/venv and installed dependency set | the existing environment identity already used by verification (`uv.lock` digest + interpreter version), recorded in the bundle |
| The action overlay / provenance probe | unchanged; already a separate recorded outcome |

Nothing else is read: no workspace `pyproject.toml`, no repository conftest, no `tests/` tree, no
network, no cache dir. Any acceptance import that resolves outside `acceptance/` or the installed
interpreter/stdlib/site-packages is a closure violation (fail closed), not a warning.

## 3. Why `pytest.ini` inside the acceptance root + `-c` + `--rootdir`

- `-c <sealed>/pytest.ini` makes configuration part of the sealed bytes, so `addopts`, markers and
  filterwarnings cannot be changed by the coder through the workspace `pyproject.toml`.
- `--rootdir <sealed>` stops pytest from walking up to the workspace root for ini/rootdir discovery and
  from inserting the workspace root into `sys.path` via rootdir-relative `conftest` collection.
- `-p no:cacheprovider` prevents the run from writing `.pytest_cache` into the workspace revision, which
  would otherwise break the "verification must not mutate the pinned tree" invariant.
- The acceptance `pytest.ini` must itself be validated against a closed allowlist (a small fixed set of
  keys: `python_files`, `python_functions`, `addopts` limited to `-q`-class flags, `markers` restricted
  to declared names). Unknown keys, `-p` plugin injection, `--rootdir`/`-c` overrides or `conftest`
  collection hooks that reach outside the closure are refused at admission.

## 4. Answer to Q-V2-ACC-1, part 2 — enforceable budgets (existing authority limits)

| Budget | Existing value and source | Use for the acceptance closure |
| :--- | :--- | :--- |
| Path length | 4096 chars (`workspace.py:122`, `publication.py:61`) | unchanged, enforced per file |
| Tree depth | 64 (`publication.py:55, 281`) | unchanged; acceptance tree must fit inside it |
| Per-file bytes | 4 MiB per rendered text (`publication.py:515, 621`) | reuse as the per-file cap for acceptance sources |
| Manifest read cap | 1 MiB (`workspace.py:3585`, `bundle.json` read) | closure `manifest.json` must fit; keep the existing cap |
| Manifest/tree metadata cap | 64 MiB (`publication.py:54`) | unchanged outer bound |
| Mode bits | `_BUNDLE_FILE_MODE = 0o644`, dirs `0o755` (`workspace.py:129-130`) | sealed acceptance files get the same fixed modes |
| File count | **no existing cap** — `_BUNDLE.files` is an unbounded array (`workspace.py:142`) | new, explicit cap required: **512 files** total in the closure (tests + support + config + manifest) |
| Aggregate acceptance bytes | only the 4 MiB per-file bound today | new, explicit cap required: **16 MiB** aggregate (4× the per-file bound, below the 64 MiB metadata bound) |
| Selector/nodeid count | none today | bounded by the file cap; each `TEST-ID` must resolve to exactly one collected nodeid |

These caps are small, deterministic and enforceable at admission time from the same canonical
path/size/mode record the authority already computes, so no new storage or counting pass is needed.

## 5. What this means for STEP9A

1. The seal must cover the acceptance tree **and** its `pytest.ini`; the run argv must be harness-built
   with `-c`/`--rootdir`/`no:cacheprovider` so the coder's `pyproject.toml` cannot influence the oracle.
2. Closure validation becomes: allowlisted `pytest.ini`, no nested `conftest.py`, no imports outside the
   closure (static import scan of the sealed `tests/**` + `support/**`), path/byte/depth/file-count caps,
   per-file digest, aggregate closure digest.
3. Selector→nodeid resolution must be captured from a collection run **against the sealed bytes**, and
   stored in the bundle; a later mismatch (nodeid missing/duplicated/renamed) fails closed.
4. None of this requires a second runner or a new authority operation; it reuses `store_bundle`/
   `install_project` plus a manifest, as the Q-V2-BOOT-1 audit established.

**Open dependency.** `Q-V2-ACC-2` decides whether every hard `INV`/ready `CT` must have an executable
assertion or whether a typed `NON_EXECUTABLE` disposition is allowed. That choice changes the grammar
and the closure validator, so it is escalated before implementation; see the Q tracker.
