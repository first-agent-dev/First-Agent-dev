# PLAN: S14 — Blackboard substrate completion (artifact index + doc closure)

**Plan-ID:** `PLAN-cli-trace-S14-blackboard-substrate-completion`
**Status:** IMPLEMENTED in sandbox (2026-08-10); READY-gated items (Q-S14-1/2/3 and
the deep-intent questions Q4/Q5/Q6) resolved with operator on 2026-08-10 — all
defaults ratified (full 7 artifact types, enumerated root files, type=plan out,
narrow S14 scope, no excerpt/snippet, auto-pickup of planner-written research
notes). Patch emitted to `/home/user/s14-blackboard-artifact-index.patch`;
awaiting operator `git apply` + `fa update` + §S5 live smoke to flip the status
to LIVE-VERIFIED.
**Depth:** P2
**Revision:** v2 (2026-08-10) — implemented; 15+2 tests green; self-review SR-1..SR-13 closed;
patch produced.
**Author:** agent
**Parent:** `worklogs/implementation-plans/cli-trace-substrate-rebaseline-2026-07-25.md` (v11)
**Closes:** **I-56** (blackboard WIP/unfinished — "complete it as the next slice").
**Supersedes / companion to:** `worklogs/implementation-plans/PLAN-fs-blackboard-query.md` (status IMPLEMENTED, 14/14 green — that plan shipped step 1, the tool; this plan ships step 2 the writer and step 3 the doc-truth alignment).
**Last slice in parent workplan.** After S14 lands and is live-verified the parent re-baseline plan is fully closed (only Q11/I-34 P0 security backlog and I-55 subagent backlog remain outside this parent).
**Ceremony:** lean, but every edit carries intent / current→target / mechanism / rationale / failure / DoD / negative proof / tests-class / kill-check per operator mandate.

---

## 0. Executive intent

The blackboard is shipped and live for **write-conflict detection** (type=`file_version`, wired via `mutation_guard.check_mutation_allowed` + `record_mutation`; covered by `test_s5_blackboard_contract.py`, `test_blackboard_conflict.py`, `test_blackboard_query_tool.py`). `fs_blackboard_query` exists and is registered in implementer + planner profiles (PLAN-fs-blackboard-query / S13.x, 14/14 green).

What remains — and what I-56 tracks — is the **artifact-index half**: the agent-facing docs tell the model `fs_blackboard_query(type="skill"|"research"|"adr"|…)` returns those rows, but **no producer writes them**. So the tool returns `[]` for those types today, making the instruction a silent lie (G10 in the 2026-08-07 audit). The same audit flagged a residual "rank" claim; I re-audited and confirm it is already corrected by the S13.10 scrub (see §1.3).

This slice makes `fs_blackboard_query(type="skill"|…)` **actually return the documented artifact rows**, closes the doc-reality gap, and adds a focused C1 test suite.

### Non-goals (explicit)

- **NO separate `fa index-blackboard` CLI verb.** Lazy on-demand indexing is strictly smaller, requires zero operator action, and does not add a startup tax to every `fa run` (see §3 alternatives).
- **NO BM25/FTS ranking on blackboard results.** "rank" is NOT a blackboard concept (verified: zero `rank` field in `BlackboardEntry`, `session_db.blackboard`, or `Blackboard.query`). Entries return timestamp-ordered ASC; `_compact` takes `rows[-limit:]` for most-recent N. Content search is `fs_instant_grep`'s job, not blackboard's.
- **NO `type="plan"` producer for subagent filtered-history.** That path is behind `FeatureFlags.blackboard_filtered_history_include_plans=False` (default off, `feature_flags.py:43`); enabling it requires a plan-entry producer properly scoped to I-55 (subagent), out of scope here. This plan flips no defaults.
- **NO touching `file_version` rows or conflict detection.** That substrate is correct and heavily tested; any change is a regression risk. The artifact indexer writes into *disjoint types* (verified: `detect_conflict` filters by `new_entry.type` at `blackboard.py:348`, so new types cannot cause false-positive write conflicts).
- **NO startup-time indexing.** Indexing 100+ markdown files in `SessionState.__post_init__` would be a tax on every `fa run` (including runs that never ask about artifacts). We index lazily on first relevant tool call.
- **NO new ToolSpec, new config flag, new dependency.** One existing tool becomes truthful.

### Central mechanism (one paragraph)

Add a single module `src/fa/blackboard/artifact_index.py` exposing one function `ensure_artifacts_indexed(blackboard: Blackboard, workspace_root: Path, types: set[str] | None = None) -> ArtifactIndexStats` that walks the `knowledge/` tree, derives **deterministic logical ids** of the form `f"{entry_type}:{sha1(relpath)[:12]}"`, computes a per-file `file_hash = sha256(file_bytes)[:16]` (stored in payload; separate from `BlackboardEntry.content_hash` which hashes the entry payload itself), and writes a new typed entry when the file is new OR when its file_hash differs from the latest existing row for that logical id. Writing is done directly via `blackboard.write(...)` (NOT via `detect_conflict` — conflict detection is a mutation_guard concern for `file_version` only). An unchanged-file re-index is a no-op (either short-circuited by file_hash comparison or, under concurrent writes, caught as `blackboard_duplicate_id`). A changed file gets a *new physical entry* (random-suffixed id) whose `parent_id` points to the previous physical id, and whose `payload.logical_id` ties it to the stable logical id — the only shape consistent with I-6.3 append-only (V6 fix, S5).

The indexer is invoked from the existing `fs_blackboard_query` handler **only when** the query targets an artifact type (one of `{skill, adr, research, instruction, prompt, codemap, antipattern}`) OR when no `type` filter is given (wildcard). File-version queries (`type="file_version"`) skip indexing entirely (fast path). The cost is bounded:
- First artifact query in a session: walks ~200 files, `stat()` + hash-compare, writes new entries ≈ 30-80ms.
- Subsequent calls (any artifact type): O(100) `stat()` calls, zero writes ≈ 5-10ms.
- `type="file_version"` queries: one cached Python dict lookup in `sys.modules` (the lazy import resolves after the first call), plus the inner type-set check skips indexing entirely ≈ microseconds.

Wildcard (`type=None`) queries trigger indexing deliberately — they ask for "everything blackboard has", so the answer must include artifacts. Cost is the same 30-80ms once per session.

The indexer writes into the **same session-bound Blackboard and authority** (`session.blackboard`, already injected into the handler via `get_current_session()`), so artifact rows respect the same session scoping as file_version rows — different sessions see independent indexes. This is the correct scope: knowledge files change at the operator's pace, not per-session, but session-scoping the index keeps the blackboard's existing per-session authority model simple (no cross-session shared state to coordinate). The cost of re-indexing per session is bounded to ~30-80ms once.

### Why this shape (senior-eng reasoning)

1. **No silent overwrites.** V6 (S5) made `write_blackboard_row` reject duplicate ids via `blackboard_duplicate_id`. We respect that; new content = new entry + parent chain.
2. **No startup tax.** Lazy on first relevant query; runs that never ask about artifacts pay zero.
3. **No new surface area.** No new CLI verb/flag/ToolSpec/dep. The existing tool becomes truthful (minimal-mechanism check passes per plan-authoring skill).
4. **Idempotent.** Deterministic ids + content_hash diff means repeated calls are safe across resume/replan/workflow stages.
5. **Bounded output.** Tool already clamps to `limit=10`/`MAX_LIMIT=50`; indexer does not change output shape.
6. **Fail-degraded, not fail-closed.** Indexer errors are caught in the handler; the tool returns existing rows + a structured `"index_error"` note in the result dict, never crashes the loop (matches FTS/telemetry/artifact-store graceful-degradation pattern).
7. **No false-positive conflicts.** `detect_conflict` filters by `new_entry.type`; artifact types and `file_version` are disjoint, so adding them cannot regress write-safety. Verified.
8. **Artifacts entries are `read_set=[]`, `write_set=[relpath]`, no base_commit assumption** — they never trigger `_assumption_violated` on any future write.

---

## 1. Preflight — source-verified findings

Anchors verified against HEAD `103fb89 fix` in sandbox `/home/user/First-Agent-dev`.

### 1.1 Existing blackboard writers (only `file_version` in production)

| File:line | type produced | Notes |
|---|---|---|
| `src/fa/inner_loop/tools/mutation_guard.py:116-127` (`_entry_for`) | `file_version` | Pre-flight conflict-check entry (`pre-<uuid>`); only fed to `detect_conflict`, never written. |
| `src/fa/inner_loop/tools/mutation_guard.py:190-209` (`record_mutation`) | `file_version` | Post-write entry (`post-<uuid>`), stamped with writer `run_id`. Only production writer today. |

Grep for other writers:

```
$ grep -rnE 'type\s*=\s*"(skill|research|adr|plan|instruction|prompt|codemap|antipattern)"' src/
(zero hits)
```

Confirmed: no other type producer exists in `src/` outside test fixtures.

### 1.2 Blackboard consumers already live

| Consumer | File:line | Today | Post-slice |
|---|---|---|---|
| `fs_blackboard_query` handler | `src/fa/inner_loop/tools/blackboard_query.py:79-112` | Returns `file_version` rows only; `type="skill"` → `[]`. | Returns artifact rows + file_version rows after lazy indexing; same output schema. |
| `mutation_guard.check_mutation_allowed` | `src/fa/inner_loop/tools/mutation_guard.py:143-164` | Calls `detect_conflict` on a synthetic `file_version` entry; queries `type="file_version"` only. | **Unchanged.** New types are not scanned. |
| `subagent_runner._build_filtered_history` | `src/fa/inner_loop/subagent_runner.py:208-220` | Queries `type="plan"`, gated off by default flag. | **Unchanged.** We don't produce `plan` rows; flag remains off. |

### 1.3 Docs audit (re-verified 2026-08-10)

| Doc | Reference | "rank" claim? | Action |
|---|---|---|---|
| `AGENTS.md:7` | "Use `fs_blackboard_query` and `fs_instant_grep` tools…" | No | None (tool name correct). |
| `AGENTS.md:265` | Tool example `fs_blackboard_query(type="skill", key="api")` | No | None (becomes true post-slice). |
| `AGENTS.md:271` | "Query blackboard: `fs_blackboard_query(type="research")` or `fs_glob(\"knowledge/**/*.md\")` but prefer blackboard query." | No | **Becomes true** post-slice (was returning `[]`). Add one sentence noting lazy indexing. |
| `knowledge/llms.txt:42,44,85-87` | Same tool examples | No | Same truth-fix; add one lazy-index sentence. |
| `knowledge/reference.md:14` | Quick-ref table | No | Same truth-fix. |
| `knowledge/reference.md` BM25/FTS row | Describes `fs_instant_grep`'s ranker | Yes, but correctly scoped to FTS, not blackboard | None (this was mis-cited in earlier notes; the blackboard itself never claims rank). |

**Conclusion:** the "false rank claim" doc gap (I-56 step 3) is **already closed** by the S13.10 doc scrub. We ship a tiny clarifying sentence about lazy indexing; no further doc scrub needed.

### 1.4 Conflict-detection isolation (critical safety check)

```python
# blackboard.py:348
existing = self.query(type=new_entry.type)   # ← type-scoped
```

So `detect_conflict(new_entry of type=file_version)` iterates **only** `file_version` rows. Adding rows of other types cannot trigger false conflicts. Verified.

Conversely: artifact indexer calls `blackboard.write(entry)` directly; it does NOT call `detect_conflict`, because:
- Artifact entries describe immutable-once-written facts about on-disk documentation; they don't express read/write intent on editable user files.
- Two concurrent agents would both re-index on demand; the id is content-addressed, so the second write of unchanged content is `blackboard_duplicate_id` (caught). Changed content → new entry → parent chain; no conflict semantics needed.
- Running `detect_conflict` for artifact entries would require constructing synthetic `read_set/write_set` that overlap with… nothing (artifacts never claim to write user code). It's a no-op by construction, so skipping it is correct and minimal.

### 1.5 Session workspace layout and knowledge/ location

Verified in `src/fa/cli.py:128-144` and `src/fa/session/manager.py:77-81,211-214`:

- In container: `workspace_root = /sessions/<sid>/workspace/` (or `/sessions` in shorthand), populated by `shutil.copytree(self.source_workspace, workspace_path, symlinks=True)` where `source_workspace = /repo` (the bind-mounted repo).
- So `<workspace_root>/knowledge/...` mirrors the repo's `knowledge/` tree at session-start time (symlinks=True is used — knowledge files are symlinked, not copied, so `stat()` reflects edits the operator makes to the source repo mid-session). This is correct for us: the indexer should reflect the current knowledge contents, and symlink resolution means live edits are visible.
- In sandbox/dev/CI: `workspace_root = Path.cwd()` or an explicit `--workspace`; `knowledge/` is a direct subdir. The indexer uses `workspace_root / "knowledge"` and gracefully skips if the directory is absent (defensive).

### 1.6 Existing constants and patterns to mirror

- Entry id form in mutation_guard: `f"pre-{uuid.uuid4().hex[:8]}"`, `f"post-{uuid.uuid4().hex[:8]}"` — random, suitable for per-run entries. For artifacts we use DETERMINISTIC ids (collision is the no-op signal, not a bug).
- Content hash: `BlackboardEntry.create` uses `sha256(canonical_json(payload))[:16]`. File content hash for change detection uses a separate `sha256(file_bytes)[:16]` (computed before entry creation, because the entry's `content_hash` hashes the entry payload, not the file bytes — that is used for blackboard-level append-only detection; for file-change detection we need a separate digest over the raw file bytes). We store the file-bytes digest in `payload["file_hash"]` to detect changes on subsequent index passes.
- Tool error codes: `blackboard_unavailable`, `blackboard_query_failed` already exist; we add NO new error codes (indexer failures surface as a soft note in the result dict, not a ToolResult.fail, per fail-degraded policy).
- MAX_LIMIT / DEFAULT_LIMIT from blackboard_query.py (`10`, `50`) are unchanged.

---

## 2. Gap ledger → S# mapping

| Gap (from blackboard-audit 2026-08-07 §4) | Status | Resolution |
|---|---|---|
| G1 | UNBUILT — artifact index | S1 (indexer module) + S2 (wire into tool handler) |
| G2 | UNBUILT — query returns empty for skill/research/adr | S2 (lazy index before query) |
| G3 | UNBUILT — unified load_artifacts | NOT built as a separate loader. `fs_blackboard_query` + the indexer IS the unified surface; `fs_instant_grep` remains the content-search surface. |
| G4 (rank) | N/A — not a blackboard feature | Already closed by S13.10 scrub; verified §1.3. |
| G5 | UNBUILT — `index_repo()` over knowledge/ | S1 (the `ensure_artifacts_indexed` function). |
| G6 (type="plan" for subagent) | UNBUILT producer | OUT OF SCOPE (I-55); flag stays off. |
| G7 (Control Unit) | N/A — not a distinct component; reads/writes are direct method calls | Accept as-is; no new layer. |
| G8 (storage schema) | DONE | No schema changes needed; existing type column is free-form. |
| G9 (conflict detection) | DONE/tested | No changes. |
| G10 (docs mislead) | MISLEADING | S3 (one-sentence clarification; docs become truthful because S1+S2 make them true). |

---

## 3. Alternatives considered (and why rejected)

| Alt | Shape | Why not |
|---|---|---|
| A. Eager startup indexing in `SessionState.__post_init__` | Walk knowledge/ during blackboard init | Adds ~30-80ms to every `fa run`, including runs that never query artifacts. Violates minimal-mechanism: most runs don't need it. |
| B. New `fa index-blackboard` CLI verb | Operator runs it before `fa run` | New surface area; operator can forget; first-run experience is broken (query returns [] until you run the command). Lazy indexing is strictly better DX. |
| C. Cross-session shared index in `~/.fa/` | Global blackboard of artifacts | Cross-session state violates the per-session authority model established in S5; adds concurrency coordination; makes testing harder; not worth the complexity when per-session indexing is <100ms. |
| D. Include artifact indexing under `detect_conflict` / mutation_guard flow | Treat knowledge files like user files | Knowledge files are not being mutated by the agent (planner has limited `knowledge/research/` write_allowlist, but writing a research note should produce a `file_version` entry for the write, not a new artifact-index entry; and the artifact indexer is a READ-side indexer, not a mutation). Mixing the two concerns breaks separation. |
| E. `INSERT OR REPLACE` for idempotent re-index | Replace existing row on hash change | Regresses V6 (S5 append-only guarantee). Forbidden. |
| F. Build a separate `fs_artifact_query` ToolSpec | New tool | Duplicates fs_blackboard_query; violates minimal-mechanism; requires new docs/wire-name/profile entries. The existing tool's contract says "query blackboard"; making it actually return all blackboard rows is the honest fix. |

---

## 4. Contracts

### CT1 (function) `ensure_artifacts_indexed`

- **TYPE:** function (NEW, `src/fa/blackboard/artifact_index.py`)
- **SIGNATURE:** `ensure_artifacts_indexed(blackboard: Blackboard, workspace_root: Path, types: set[str] | None = None) -> ArtifactIndexStats`
- **INPUT:**
  - `blackboard`: session-bound `Blackboard` (from `session.blackboard`).
  - `workspace_root`: resolved workspace root (so we can find `knowledge/`).
  - `types`: optional whitelist of artifact types to index; `None` = all ARTIFACT_TYPES.
- **OUTPUT:** `ArtifactIndexStats` dataclass `{scanned: int, added: int, updated: int, skipped_unchanged: int, errors: list[str], indexed_types: set[str]}`. Deterministic; purely additive to the blackboard.
- **ERRORS:** never raises. File IO errors are captured in `stats.errors` and logged at WARNING. If `knowledge/` doesn't exist, returns `scanned=0, added=0, …` (not an error).
- **SIDE EFFECTS:** writes 0..N Blackboard entries for each qualifying file under `knowledge/{skills,adr,research,instructions,prompts,codemaps,anti-patterns}/` matching `*.md` (and root-level `*.md` that are not AGENTS.md/HANDOPS/CHANGELOG/operational files — enumerated explicitly).
- **INVARIANTS:**
  - I1 Deterministic id per (type, relpath): `id = f"{type}:{sha1(relpath)[:12]}"` — uses sha1 of the relative POSIX path (not full path) so the id is stable across machines.
  - I2 Entry type is one of `ARTIFACT_TYPES = frozenset({"skill","adr","research","instruction","prompt","codemap","antipattern"})`.
  - I3 Only files under the whitelisted knowledge subdirectories (and a small root-of-knowledge/ whitelist: `BACKLOG.md`, `MAINTENANCE.md`, `README.md`, `project-overview.md`, `reference.md`, `llms.txt` — these are referenced by name in AGENTS.md bootstrap and are legitimate artifacts).
  - I4 For new files: a new entry is written with `parent_id=None`; `payload` includes `{path, relpath, title, file_hash, size, mtime}`.
  - I5 For changed files (file_hash differs from latest existing entry for that deterministic id): a NEW entry is written with `parent_id=<previous_id>`; content_hash is over the new payload; `timestamp` is fresh; `read_set=[]`, `write_set=[relpath]`, `assumptions=[]`, `version_dependencies={}`.
  - I6 For unchanged files (file_hash matches latest): no write; counted in `skipped_unchanged`.
  - I7 `Blackboard.write`'s `blackboard_duplicate_id` (same id re-written with identical payload) is caught and counted as `skipped_unchanged`.
  - I8 Indexer never calls `detect_conflict`; never mutates `file_version` entries.
  - I9 Indexer runs under whatever `run_id` the bound Blackboard carries (the session's run_id). `_is_same_writer` therefore treats successive index entries as self on future index passes.
  - I10 Max file size for indexing: 200_000 bytes (mirrors FTS indexer's `max_file_size=100_000` — we double it because research notes can be long; files over this size are skipped with an error entry in `stats.errors`, not crashed on).
- **KILL-CHECK:** removing the file-walk loop or the `blackboard.write(...)` call → C1 T3 fails (artifact rows appear in query).

### CT2 (constant) `ARTIFACT_TYPES` and `ARTIFACT_ROOTS`

- **TYPE:** module-level constants in `artifact_index.py`.
- **VALUE:** `ARTIFACT_TYPES` as in I2; `ARTIFACT_ROOTS: Mapping[str, str] = {"skill": "skills", "adr": "adr", "research": "research", "instruction": "instructions", "prompt": "prompts", "codemap": "codemaps", "antipattern": "anti-patterns"}` (maps blackboard type → subdir under `knowledge/`). Plus `ARTIFACT_ROOT_FILES: tuple[str, ...] = ("BACKLOG.md","MAINTENANCE.md","README.md","project-overview.md","reference.md","llms.txt")` mapped to type `"research"` (root-level knowledge docs act as general research/overview artifacts).
- **RATIONALE for roots:** subdir names match existing layout (preflight §find). For root-level files, we deliberately enumerate (NOT "all *.md at root") because AGENTS.md, llms.txt (indexed itself via this list), review-stage docs, and archive adjacents should not pollute the artifact index. Adding a new root-level artifact requires editing the tuple and the docs — explicit, not implicit.
- **KILL-CHECK:** removing a subdir from ARTIFACT_ROOTS → T1 count changes, fails.

### CT3 (wiring) handler triggers lazy indexing

- **TYPE:** edit to existing handler in `src/fa/inner_loop/tools/blackboard_query.py`.
- **CHANGE:** Before the `session.blackboard.query(...)` call, if `type_ is None or type_ in ARTIFACT_TYPES`, call `ensure_artifacts_indexed(session.blackboard, session.workspace_root, types={type_} if type_ else None)`. Wrap in try/except Exception → log WARNING, continue (fail-degraded; the `_compact` projection still works on whatever rows exist). Append a one-line `"indexed": {"added":…,"updated":…}` to the ToolResult.result dict when indexing ran (so a caller/tests can observe that indexing executed).
- **CONSUMER:** existing ToolResult.ok path (schema is additive).
- **DO-NOT:** index on every `type="file_version"` query (fast path for write-history inspection).
- **KILL-CHECK:** removing the `ensure_artifacts_indexed` call → T3/T4 fail (type="skill" returns []).

### CT4 (invariant) type-scoped conflict isolation holds

- **TYPE:** invariant (regression guard).
- **ENFORCED:** by existing `detect_conflict` filtering on `new_entry.type` (blackboard.py:348). C1 test T5 indexes a small knowledge tree then performs a synthetic `file_version` write (representative of mutation_guard's pre-write check) and asserts `detect_conflict` returns `[]`.
- **KILL-CHECK (feature-absence → test fails):** mutate T5's synthetic entry to use `type="skill"` (an artifact type that overlaps with a row in the indexed tree, sharing `write_set` path) → `detect_conflict` returns non-empty (because the overlap is now same-type) and T5's `assert []` fails. If the type filter in `detect_conflict` is removed, T5 fires because artifact rows are scanned for a file_version entry, again failing `assert []`; that also satisfies the kill-check property.

### CT5 (docs) agent-facing alignment

- **TYPE:** doc edit (no code change beyond CT3).
- **EDIT:** one sentence appended to AGENTS.md:271 (and mirrored in llms.txt:44): "Artifact rows are indexed lazily on first query (content-hash-addressed); `fs_instant_grep` remains the tool for substring content search."
- **DO-NOT:** rewrite history/archive docs (S4 doc-do-not of PLAN-fs-blackboard-query precedent).
- **KILL-CHECK:** n/a (doc-only); verified by grep.

---

## 5. Path & flag matrix

| Path | Trigger | Producer | Covering T# |
|---|---|---|---|
| P1 | `type="skill"/"adr"/"research"/…` artifact query, first call in session → index + return rows | handler → ensure_artifacts_indexed | T1, T3, T4 |
| P2 | Same artifact type, second call in session → no-op index (all files unchanged) → return existing rows | handler → ensure_artifacts_indexed (skipped_unchanged = all) | T2 (idempotency) |
| P3 | `type="file_version"` → NO indexing → return file_version rows as today | handler (skip branch) | T6 (no-index on file_version) |
| P4 | `type=None` wildcard → index all artifact types → return everything | handler → ensure_artifacts_indexed(types=None) | T4 |
| P5 | `knowledge/` directory missing → return [] gracefully, no raise | ensure_artifacts_indexed early return | T7 |
| P6 | File larger than size cap → skip with error note, not crash | ensure_artifacts_indexed size check | T8 |
| P7 | File IO error on one file → log + continue, index other files | ensure_artifacts_indexed per-file try/except | T9 |
| P8 | File changed between calls → NEW entry with parent_id set | ensure_artifacts_indexed change detection | T10 |
| P9 | Artifact entries exist → subsequent file write via mutation_guard → NO false conflict | detect_conflict type filter | T5 |
| P10 | Indexer raises unexpected exception at top level → handler catches, logs, returns existing rows (fail-degraded) | handler try/except | T11 |

Flag matrix:

| Matrix cell | Proves | T# |
|---|---|---|
| A — blackboard_enabled=True (default) | Indexer works against session-bound blackboard | T1, T3, T4, T10 |
| B — blackboard_enabled=False | Indexer never called; blackboard_unavailable returned as today | T12 |
| C — implementer profile (coder) | Tool + indexer reachable | T13 |
| D — planner profile | Tool + indexer reachable | T13 |
| E — verifier (eval) profile | Tool absent (non-goal preserved) | T13 |

---

## 6. Step-by-step implementation

### Step S1 — add artifact indexer module (NEW)

**Traces-to:** CT1, CT2, I-1..I-10, G1/G5; Depends-on: none; Target liveness: L0→L1 (import-reachable, not yet wired).

**File:** `src/fa/blackboard/artifact_index.py` (NEW).

**Edit content (structure, not final code — executor writes final code):**

The code below is the CORRECTED final structure (bugs fixed: see §11 "Plan self-review").

```python
"""Lazy on-demand artifact index for the Blackboard (S14 / I-56).

Populates typed entries for knowledge/ artifacts (skills, ADRs, research
notes, instructions, prompts, codemaps, anti-patterns, and an enumerated
set of root-level knowledge docs) on first ``fs_blackboard_query`` call.

Design choices (see PLAN-cli-trace-S14-... §0, §4, §11):
- Append-only (V6/S5): new file content gets a NEW physical entry with
  parent_id pointing to the previous revision; never INSERT OR REPLACE.
- Two-level id scheme:
    * logical_id  = f"{entry_type}:{sha1(relpath)[:12]}"   (stable, deterministic)
    * physical id = logical_id (v1)  OR  f"{logical_id}-r{uuid4().hex[:8]}" (revisions)
  payload["logical_id"] is set on every row so future passes can find the
  latest revision of a given logical artifact regardless of physical id.
- Never calls detect_conflict (that is mutation_guard's job for file_version).
- Fail-degraded: never raises out of ensure_artifacts_indexed; per-file and
  top-level errors accumulate in ArtifactIndexStats.errors and are logged.
- Path-contained: rejects symlinks escaping knowledge/ via is_relative_to.
"""
from __future__ import annotations

import hashlib
import logging
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fa.blackboard.blackboard import Blackboard, BlackboardEntry

logger = logging.getLogger(__name__)

ARTIFACT_TYPES: frozenset[str] = frozenset(
    {"skill", "adr", "research", "instruction", "prompt", "codemap", "antipattern"}
)
ARTIFACT_ROOTS: dict[str, str] = {
    "skill": "skills",
    "adr": "adr",
    "research": "research",
    "instruction": "instructions",
    "prompt": "prompts",
    "codemap": "codemaps",
    "antipattern": "anti-patterns",
}
# Root-level knowledge/ docs that are legitimate artifacts (EXPLICIT enumeration;
# NOT "*.md" — AGENTS.md / HANDOFF / archive / stage verification excluded).
_ARTIFACT_ROOT_SPECIAL: tuple[tuple[str, str], ...] = (
    ("BACKLOG.md", "research"),
    ("MAINTENANCE.md", "research"),
    ("README.md", "research"),
    ("project-overview.md", "research"),
    ("reference.md", "research"),
    ("llms.txt", "research"),
)
_MAX_FILE_BYTES = 200_000
_LOGICAL_ID_HASH_LEN = 12
_REVISION_SUFFIX_LEN = 8


@dataclass
class ArtifactIndexStats:
    scanned: int = 0
    added: int = 0
    updated: int = 0
    skipped_unchanged: int = 0
    errors: list[str] = field(default_factory=list)
    indexed_types: set[str] = field(default_factory=set)


def _logical_id(entry_type: str, relpath: str) -> str:
    h = hashlib.sha1(relpath.encode("utf-8")).hexdigest()[:_LOGICAL_ID_HASH_LEN]
    return f"{entry_type}:{h}"


def _revision_phys_id(logical: str) -> str:
    return f"{logical}-r{uuid.uuid4().hex[:_REVISION_SUFFIX_LEN]}"


def _title_from_content(text: str, fallback: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()[:200]
    for line in text.splitlines():
        s = line.strip()
        if s:
            return s[:200]
    return fallback


def _iter_candidate_files(knowledge_root: Path, types: set[str]):
    """Yield (entry_type, abs_p, relpath) for in-scope files."""
    for entry_type, sub in ARTIFACT_ROOTS.items():
        if entry_type not in types:
            continue
        d = knowledge_root / sub
        if not d.is_dir():
            continue
        for dirpath, _, filenames in os.walk(d):
            for fn in filenames:
                if not fn.endswith(".md"):
                    continue
                abs_p = Path(dirpath) / fn
                try:
                    rel = abs_p.relative_to(knowledge_root).as_posix()
                except ValueError:
                    continue
                yield entry_type, abs_p, rel
    for fname, entry_type in _ARTIFACT_ROOT_SPECIAL:
        if entry_type not in types:
            continue
        abs_p = knowledge_root / fname
        if abs_p.is_file():
            yield entry_type, abs_p, fname


def _is_within(child: Path, parent: Path) -> bool:
    """Containment check that survives symlinks — both sides resolved."""
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def _latest_by_logical_id(
    blackboard: Blackboard, types: set[str]
) -> dict[str, BlackboardEntry]:
    """Build ``{logical_id: latest_entry}`` across all artifact types.

    v1 rows have ``id == logical_id`` and no ``logical_id`` in payload.
    Revision rows carry ``payload["logical_id"]`` and a unique physical id.
    "Latest" = highest ``timestamp`` per logical_id (ISO-8601 string sort
    matches chronological sort when timestamps are produced by the same
    clock, which BlackboardEntry.create ensures via datetime.now(UTC)).
    """
    out: dict[str, BlackboardEntry] = {}
    for t in types:
        for e in blackboard.query(type=t):
            if isinstance(e.payload, dict) and isinstance(e.payload.get("logical_id"), str):
                lid = e.payload["logical_id"]
            else:
                lid = e.id
            prev = out.get(lid)
            if prev is None or e.timestamp >= prev.timestamp:
                out[lid] = e
    return out


def _file_hash_of(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()[:16]


def ensure_artifacts_indexed(
    blackboard: Blackboard,
    workspace_root: Path,
    types: set[str] | None = None,
) -> ArtifactIndexStats:
    """Index knowledge/ artifacts into ``blackboard`` if missing or stale.

    Purely additive. Never raises. Returns a stats struct describing what
    happened. Safe to call repeatedly (idempotent for unchanged files).
    """
    stats = ArtifactIndexStats()
    try:
        knowledge_root = (workspace_root / "knowledge").resolve()
    except OSError as exc:
        stats.errors.append(f"knowledge_root:{exc}")
        return stats
    if not knowledge_root.is_dir():
        return stats
    target_types = set(types) if types is not None else set(ARTIFACT_TYPES)
    target_types = target_types & set(ARTIFACT_TYPES)
    if not target_types:
        return stats
    latest = _latest_by_logical_id(blackboard, target_types)
    for entry_type, abs_p, rel in _iter_candidate_files(knowledge_root, target_types):
        stats.scanned += 1
        stats.indexed_types.add(entry_type)
        if not _is_within(abs_p, knowledge_root):
            stats.errors.append(f"escape:{rel}")
            continue
        try:
            st = abs_p.stat()
        except OSError as exc:
            stats.errors.append(f"stat:{rel}:{exc}")
            continue
        if st.st_size > _MAX_FILE_BYTES:
            stats.errors.append(f"too_large:{rel}:{st.st_size}")
            continue
        try:
            raw = abs_p.read_bytes()
        except OSError as exc:
            stats.errors.append(f"read:{rel}:{exc}")
            continue
        file_hash = _file_hash_of(raw)
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            text = ""
        logical = _logical_id(entry_type, rel)
        prev = latest.get(logical)
        prev_hash: str | None = None
        if prev is not None and isinstance(prev.payload, dict):
            prev_hash = prev.payload.get("file_hash") if isinstance(prev.payload, dict) else None
        if prev is not None and prev_hash == file_hash:
            stats.skipped_unchanged += 1
            continue
        payload: dict[str, Any] = {
            "path": rel,
            "relpath": rel,
            "title": _title_from_content(text, fallback=rel),
            "file_hash": file_hash,
            "logical_id": logical,
            "size": st.st_size,
            "mtime": int(st.st_mtime),
        }
        phys_id = logical if prev is None else _revision_phys_id(logical)
        try:
            entry = BlackboardEntry.create(
                id=phys_id,
                type=entry_type,
                payload=payload,
                read_set=[],
                write_set=[rel],
                assumptions=[],
                version_dependencies={},
                parent_id=(prev.id if prev is not None else None),
            )
            blackboard.write(entry)
            if prev is None:
                stats.added += 1
            else:
                stats.updated += 1
            latest[logical] = entry
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "blackboard_duplicate_id" in msg:
                # Concurrent indexer wrote the same logical id → treat as
                # already-indexed (idempotent under concurrency).
                stats.skipped_unchanged += 1
            else:
                stats.errors.append(f"write:{rel}:{exc}")
                logger.warning("artifact index write failed for %s: %s", rel, exc)
    return stats


__all__ = [
    "ARTIFACT_TYPES",
    "ArtifactIndexStats",
    "ensure_artifacts_indexed",
]
```

Executor writes the final code to match this structure; any deviation requires updating the plan first.


**Do:**

- Use `from __future__ import annotations`; module-level logger; never raise.
- Mirror `blackboard.py`'s own style (dataclasses, `from __future__ import annotations`, explicit try/except with `# noqa: BLE001` where fail-degraded catch-all is intended — matches `state.py`, `blackboard.py`, `fts_index.py` precedent).
- Add `__all__ = ["ARTIFACT_TYPES", "ArtifactIndexStats", "ensure_artifacts_indexed"]`.

**Do-not:**

- Import `mutation_guard`, `detect_conflict`, or any file-version machinery.
- Add a module-level side effect (no indexing on import).
- Add a CLI verb, subcommand, or feature flag.
- Import from `inner_loop` (this module lives under `fa.blackboard` and must not circular-import inner_loop; it uses only `fa.blackboard.blackboard.Blackboard/BlackboardEntry`).
- Index non-`.md` files (AVIF/PNG/JS/PYC binaries are not artifacts the LLM reads).
- Follow symlinks out of `knowledge/` (defensive path containment: resolve+is_relative_to check).

**Exit criteria for S1:**

- [ ] `python3 -c "from fa.blackboard.artifact_index import ensure_artifacts_indexed, ARTIFACT_TYPES; print(sorted(ARTIFACT_TYPES))"` prints the 7 types.
- [ ] Pure-python smoke (C0p) in tests (T0 helper test) confirms `_logical_id` is deterministic.
- [ ] `ruff` and `mypy` clean on the new module.
- [ ] No new dependency in `pyproject.toml`.

**Kill-check:** remove the `blackboard.write(entry)` call → T1/T3 fail.

---

### Step S2 — wire indexer into the fs_blackboard_query handler

**Traces-to:** CT3; Depends-on: S1; Target liveness: L1→L3 (behaviorally wired, with kill-check at composition root).

**File:** `src/fa/inner_loop/tools/blackboard_query.py`.

**Edit:**

1. Update the `ToolSpec` description (constant inside `build_blackboard_query_tool()`) to add one sentence so the model understands the artifact-indexing behavior:
   ```
   description=(
       "Query the session blackboard (formal substrate artifact store) and return compact "
       "metadata rows (id, type, content_hash, read/write sets, timestamp). Filters by optional "
       "type and key substring; returns at most limit rows (default 10, max 50). "
       "Artifact types (skill, adr, research, instruction, prompt, codemap, antipattern) are "
       "indexed lazily from knowledge/ on first such query and returned alongside file_version "
       "rows. Use fs_instant_grep (not this tool) for substring content search. "
       "Use for artifact discovery instead of grep -ril."
   ),
   ```

2. In `handler(params)` (around line 88, just before the `rows = session.blackboard.query(...)` call), add the lazy-index seam. **DRIFT PREVENTION:** the set of types that trigger indexing is imported lazily from `artifact_index` (not duplicated) so the handler and the indexer cannot drift apart:
   ```python
   index_stats = None
   # Lazy-index artifact types before querying. Imported lazily so the tool
   # still works (returning file_version rows) if the artifact_index module
   # fails to import for any reason (fail-degraded, same pattern as
   # get_current_session below).
   if session.blackboard is not None and (
       type_ is None or (isinstance(type_, str))
   ):
       try:
           from fa.blackboard import artifact_index
           if type_ is None or type_ in artifact_index.ARTIFACT_TYPES:
               ws_root = getattr(session, "workspace_root", None)
               if ws_root is not None:
                   target_types = None if type_ is None else {type_}
                   index_stats = artifact_index.ensure_artifacts_indexed(
                       session.blackboard, ws_root, types=target_types,
                   )
       except Exception as exc:  # noqa: BLE001  fail-degraded per Phase-0.5
           logger.warning("fs_blackboard_query: artifact index unavailable: %s", exc)
           index_stats = None
   ```
   Note on ordering: we perform the type-in-set check *after* lazy-importing so we use the single source of truth (`artifact_index.ARTIFACT_TYPES`). The unconditional first branch (`type_ is None or isinstance(type_, str)`) ensures we enter the block for any string type (including "file_version"), but the inner `if type_ is None or type_ in ARTIFACT_TYPES` skips indexing for non-artifact types like `file_version`. This costs one lazy import (cached by Python after first call) for every `file_version` query — acceptable.

3. In the `ToolResult.ok(...)` return, extend `result=` dict with an additive `"indexed"` key when indexing ran:
   ```python
   indexed_dict: dict[str, object] = {}
   if index_stats is not None:
       indexed_dict = {
           "indexed": {
               "scanned": index_stats.scanned,
               "added": index_stats.added,
               "updated": index_stats.updated,
               "skipped": index_stats.skipped_unchanged,
               "errors": index_stats.errors[:5],
               "types": sorted(index_stats.indexed_types),
           }
       }
   return ToolResult.ok(
       f"Found {len(compact_rows)} blackboard rows (type={type_ or '*'}, key={key or '*'} limit={limit})",
       result={
           "rows": compact_rows,
           "type": type_ if isinstance(type_, str) else None,
           "key": key if isinstance(key, str) else None,
           "limit": limit,
           "count": len(compact_rows),
           **indexed_dict,
       },
   )
   ```
   This is additive; existing consumers that look at `result["rows"]` are unaffected. When indexing didn't run, the `"indexed"` key is absent (so the model doesn't pay tokens for it on fast `file_version` queries).

**Do:**

- Lazy-import `ensure_artifacts_indexed` inside the handler (mirrors `get_current_session` pattern and keeps module-import side-effect-free).
- Defensive `getattr(session, "workspace_root", None)` — tests may build SessionState without all attributes; we skip indexing if the attr is missing (fail-degraded).
- Log WARNING (not ERROR) on indexer failure — indexing is advisory, query results still valid.
- Cap `errors[:5]` in the result dict to avoid token blowup if many files fail.

**Do-not:**

- Import `artifact_index` at module top-level (would add a hard dependency that breaks if the module has an import error; the handler should still work for file_version queries even if the indexer fails to import).
- Change `_compact`, limit-clamp logic, ToolSpec schema, permission, tags, max_context_bytes.
- Add any new parameter to the ToolSpec input_schema (no new LLM-facing surface; indexing is transparent).
- Move any existing behavior; add, don't modify.

**Exit:**
- [ ] `fs_blackboard_query(type="skill")` against a real session now returns rows (verified via C1 test T3).
- [ ] The 14 existing `test_blackboard_query_tool.py` tests still pass.
- [ ] `fs_blackboard_query(type="file_version")` does NOT invoke the indexer (proved by T6: mock ensure_artifacts_indexed, assert call_count == 0 when type=file_version).

**Kill-check:** remove the `ensure_artifacts_indexed(...)` call in the handler → T3/T4 fail (no rows for artifact types).

---

### Step S3 — doc alignment (minimal, additive)

**Traces-to:** CT5, G10; Depends-on: S1+S2 (docs become true because the feature ships, not by weakening the claim).

**Files:**

1. `AGENTS.md:271` — append after the existing sentence:
   > Artifact rows are indexed lazily on first such query (content-hash-addressed, append-only); use `fs_instant_grep` for substring content search.
2. `knowledge/llms.txt:44` — append the same sentence (single-line, keep llms.txt compact).
3. `knowledge/reference.md:14` Quick Ref — no change to the answer text (the answer is correct post-slice). No extra sentence needed here (Quick Ref is lookup-only).

**Do-not:**

- Edit archive/ docs (`worklogs/archive/*`, `knowledge/research/blackboard-audit-*.md`, historical notes).
- Edit `AGENTS.md:7` or `AGENTS.md:265` (already correct).
- Add new doc files, ADRs, skills (ADR-16 is already referenced by DIGEST; this slice completes an existing intent, does not introduce a new decision). If an ADR amendment is needed it will be a one-paragraph addendum to DIGEST only; defer that decision to the review step.

**Exit:**
- [ ] `grep -n "rank" AGENTS.md knowledge/llms.txt knowledge/reference.md | grep -iv "bm25\|fts5\|porter"` returns zero (i.e., no false blackboard-rank claim).
- [ ] `grep -c "blackboard.query(" AGENTS.md knowledge/llms.txt knowledge/reference.md` returns zero (all references use the tool's real name `fs_blackboard_query`).

---

### Step S4 — tests (full pyramid per tests-writing skill)

**Traces-to:** all contracts; Depends-on: S1+S2+S3.

**New file:** `tests/test_blackboard_artifact_index.py` (C1 primary + C0p helpers).
**Edits:** `tests/test_blackboard_query_tool.py` extended (one new C1 T4 case + T6 no-index case).

**Tests-class pyramid:**

- **C0p** `test_det_id_is_deterministic` — pure function, id for `("skill","skills/plan-authoring/SKILL.md")` is stable across calls and length-bounded.
- **C0p** `test_artifact_roots_layout_matches_live_tree` — walks the LIVE knowledge/ tree in the repo and asserts every ARTIFACT_ROOTS subdir exists; catches accidental dir renames in future.
- **C0p** `test_title_from_content_extracts_h1` — feed small markdown samples, assert the ATX heading is extracted.
- **C1** `test_indexing_populates_skill_adr_rows` (T1) — on a tmp workspace with a small knowledge/ tree (3 skills, 4 ADRs, 1 research note + BACKLOG.md), construct a real `SessionDatabase` + `Blackboard`, call `ensure_artifacts_indexed`, then `blackboard.query(type="skill")` and assert 3 rows returned with correct `path`/`title`/`file_hash`.
  - **Matrix:** A (default blackboard_enabled=True).
  - **Oracle rank 1+5:** event (rows present with right types) + FS (knowledge tree).
  - **Kill-check:** remove `blackboard.write(...)` in indexer → returns 0 rows.
- **C1** `test_indexing_is_idempotent` (T2) — call `ensure_artifacts_indexed` twice; second call has `added=0`, `updated=0`, `skipped_unchanged == scanned`. Also assert blackboard row count doesn't double.
  - **Kill-check:** remove the file_hash short-circuit → second call adds duplicates (fails uniqueness or count).
- **C1** `test_query_tool_lazy_indexes_on_first_artifact_call` (T3) — builds a real ToolRegistry with blackboard, real SessionState with a tmp workspace containing small knowledge tree, dispatches a `ToolCall(name="fs_blackboard_query", arguments={"type":"skill"})`, asserts `ToolResult.ok`, `len(result["rows"]) == 3`, `result["indexed"]["added"] == 3`.
  - **Matrix:** A; mirrors `test_happy_path` in `test_blackboard_query_tool.py` but with knowledge content present.
  - **Kill-check:** remove `ensure_artifacts_indexed` call in handler → `rows=[]`.
- **C1** `test_query_tool_wildcard_indexes_all_artifact_types` (T4) — same as T3 but `arguments={}` (no type filter); assert rows contain entries from ≥3 distinct types.
- **C1** `test_artifact_entries_do_not_trigger_file_version_conflict` (T5, safety-critical) — index knowledge tree; then construct a synthetic `BlackboardEntry(type="file_version", write_set=["src/foo.py"], read_set=["knowledge/adr/ADR-7.md"], assumptions=["base_commit abc"], …)` and call `blackboard.detect_conflict(new_entry)`. Assert returns `[]` (no false conflict).
  - **Kill-check:** change the entry type to `"skill"` (i.e., a same-type overlap) → conflict detected. Documents the isolation invariant.
- **C1** `test_query_tool_does_not_index_on_file_version_query` (T6) — dispatches `type="file_version"` against a session with a `write_file`-generated file_version row; monkeypatch `fa.blackboard.artifact_index.ensure_artifacts_indexed` with a spy; assert spy call_count == 0 and result contains no "indexed" key.
  - **Kill-check:** remove the `if type_ is None or type_ in artifact_index.ARTIFACT_TYPES:` inner guard in the handler → spy is called, test fails.
- **C1** `test_indexing_missing_knowledge_dir_is_noop` (T7) — tmp workspace without `knowledge/`; stats all zero, no raise, query returns [].
- **C1** `test_indexing_skips_oversized_files` (T8) — create a 300KB markdown file in `knowledge/skills/`; assert skipped, error message mentions "too_large", no crash.
- **C1** `test_indexing_continues_past_per_file_io_error` (T9) — chmod 000 a file (or use unreadable file via monkeypatch/open-mock); assert other files still indexed, error list contains the bad file.
- **C1** `test_changed_file_creates_new_entry_with_parent_id` (T10) — index once; modify a file's bytes; index again; assert new row count N+1, latest entry has `parent_id == first_entry.id`, `payload.logical_id` matches across revisions, old entry still exists (append-only preserved).
  - **Kill-check:** re-use same id (INSERT OR REPLACE) → row count stays N instead of N+1, fails.
- **C1** `test_query_tool_fail_degraded_when_indexer_raises` (T11) — monkeypatch `ensure_artifacts_indexed` to raise RuntimeError; dispatch artifact query; assert `ToolResult.ok` (not fail), result rows whatever is in blackboard (possibly []), no exception propagates.
- **C2** `test_indexer_respects_blackboard_disabled` (T12) — when session.blackboard is None, tool returns `blackboard_unavailable` as today (existing T3 in blackboard_query_tool.py already covers this; just double-check the new code path doesn't raise when blackboard is None).
- **C2** `test_tool_registered_in_implementer_and_planner_not_eval` (T13) — build_baseline_registry / build_planner_registry contain `fs_blackboard_query`; build_eval_registry does not. (Already tested in existing T9/T10; no NEW assertion needed, but re-run to confirm S2 didn't accidentally widen registration.)

All C1 tests follow §5 type-honest fixtures from tests-writing skill: real `SessionDatabase`, real `Blackboard`, real `ToolRegistry`, real `ToolCall`; LLM I/O is not involved (no provider calls needed — artifact queries are purely filesystem + SQLite).

**Total new tests:** 14 (matching PLAN-fs-blackboard-query precedent of 14 tests for a tool surface). Plus 2 tests added to existing `test_blackboard_query_tool.py`.

**Do:**

- Place fixture helpers `_make_session_with_knowledge(tmp_path, files: dict[str,str])` at top of new test file.
- Use `tmp_path` for all workspaces; never touch host filesystem.
- Use real `Blackboard` + `SessionDatabase` (C1), not mocks; only mock/monkeypatch for failure injection (T9, T11).
- Include docstring per test stating root/matrix/claim/kill-check/path-inventory per tests-writing skill template.

**Do-not:**

- Call `drive_session` (which requires a mocked LLM chain). Our composition root for this feature is the tool handler itself (via `ToolRegistry.dispatch`), which is one layer below `drive_session` and is where the indexing actually triggers. This is L3 because removing the handler call kills the behavior.
- Test the CLI parser (C2) — no new CLI surface.

---

### Step S5 — verification, static gates, live-path

- `PYTHONPATH=src python3 -m pytest tests/test_blackboard_artifact_index.py tests/test_blackboard_query_tool.py -q` → 14+14+2 = 30 passed.
- `PYTHONPATH=src python3 -m pytest tests/test_s5_blackboard_contract.py tests/test_blackboard_conflict.py tests/test_session_db_authority.py -q` → previously passing tests still pass (no regression on file_version / conflict / session_db authority).
- `PYTHONPATH=src python3 -m pytest -q` → full suite green (no regressions).
- `ruff check src/ tests/` → clean.
- `mypy src/` → clean (no new ignores; `# noqa: BLE001` where catch-all fail-degraded is intended, matching existing code pattern).
- **Live smoke** on host via the same `docker compose exec -T first-agent fa …` pattern as S13.9 (after patch applies + image rebuild via `fa update`):
  1. `… fa run "Use fs_blackboard_query to list available skills. Report the count and the first 3 titles." -n 8 -i s14-0-smoke`
  2. Expect agent successfully calls the tool, sees rows (not empty), and answers with e.g. "8 skills found" plus titles.
  3. Pull `events.jsonl`; assert ≥1 tool_call to `fs_blackboard_query` with `type="skill"`; assert the corresponding tool_result contains `"indexed": {"added": N, ...}` with N>0 on first call, `"added":0` on second call (idempotency).
  4. Exit code 0 (DONE) or 1 (BLOCKED) acceptable as with S13.9.

**Static gates:**

- `scripts/check_producer_consumer_contract.py` — no new EventTypes; unaffected.
- `tests/test_s13_10_tool_names.py` — no new ToolSpec name; unaffected.
- `tests/test_dead_flags.py` — no new feature flag; unaffected.

---

## 7. Risks and mitigations

| R# | Risk | Mitigation | T# |
|---|---|---|---|
| RK-1 | Indexer runs on every wildcard query, slowing casual use | Per-file mtime+file_hash short-circuit; subsequent calls O(stat) ~5ms; bounded by _MAX_FILE_BYTES; lazy import keeps import time zero. | T2 |
| RK-2 | False-positive conflicts for file_version writes | type-scoped query in detect_conflict; artifact entries don't express base_commit assumptions; tested. | T5 |
| RK-3 | Deterministic id collision (sha1[:12] of relpath collides) | 12 hex chars = 48 bits; expected collisions at ~10M entries (birthday); we have ~200 files → negligible. If a collision ever occurred, second insert raises blackboard_duplicate_id and gets counted as skipped_unchanged for the collided file, surfacing in stats.errors on the NEXT call when file_hash mismatches — safe failure mode, not silent corruption. | T0 |
| RK-4 | Symlink escape from knowledge/ to sensitive file | Defensive: `abs_p.resolve().is_relative_to(knowledge_root.resolve())` before reading (add to `_iter_candidate_files`). | T9 variant |
| RK-5 | Indexer import fails on a host with partial install | Handler lazy-imports inside try/except, degrades to returning existing rows + WARNING log. | T11 |
| RK-6 | Append-only parent chain grows unboundedly if file is edited many times in a session | Each session has its own blackboard; a session is one task (max-turns ≤30); artifact edits in-session are rare (planner occasionally writes to `knowledge/research/`), producing at most a handful of revisions per session. Not a problem; bounded by session lifetime. | Inspected, no separate test needed |
| RK-7 | Planner writes to knowledge/research/ mid-session, creating file_version entries (via mutation_guard) AND the indexer later sees the same path — type mismatch (file_version vs research) | `detect_conflict` filters by type, so no conflict; the artifact indexer writes type="research" entries which share a `write_set=[relpath]` but are different types than file_version. Each type has its own row namespace. Acceptable. | T5 covers disjointness |
| RK-8 | Changing knowledge files between stage boundaries in workflow (planner writes a research note, coder reads it) | Normal: each stage uses the same session blackboard, so planner's file_version write and the next artifact indexer call both observe the latest state. Indexer adds a new revision entry if file_hash changed. | Manual inspection via live smoke |

**Rollback:**

- S1+S2 are additive: revert the two files (`artifact_index.py` + the handler delta) and 1 test file → blackboard returns to pre-S14 state.
- No flag flip, no schema change, no data migration (artifact rows in existing session DBs are inert after rollback — they occupy space but are ignored because no code queries those types without the indexer).
- No new CLI surface → no UX regression on revert.

**Open questions (operator review needed):**

- Q-S14-1 Should `prompts/`, `codemaps/`, `anti-patterns/`, `instructions/` be indexed? My default is YES (they are knowledge artifacts AGENTS.md/llms.txt reference implicitly), but a narrower scope (just `skill|adr|research`) reduces index size ~30%. I recommend keeping the broader scope because the doc promise "query the blackboard for knowledge artifacts" implies all of them, and the incremental cost is small (<20 files per extra type).
- Q-S14-2 Should root-level `AGENTS.md`, `HANDOFF.md` be indexed? Default: NO (AGENTS.md is pre-boot; HANDOFF is cross-session mutable state, not a durable knowledge artifact). Only the enumerated `_ARTIFACT_ROOT_SPECIAL` list gets indexed.
- Q-S14-3 Do we want a follow-up to wire `type="plan"` for subagent_runner (I-55/G6)? My recommendation: NO, leave flag off and plan for a future slice dedicated to subagent; this slice's purpose is to close I-56, not restart I-55.

---

## 8. Definition of Done (falsifiable, concrete)

**STATE (before → after):**

- Before: `fs_blackboard_query(type="skill"|"adr"|"research"|…)` returns `[]`; docs promise otherwise.
- After: same call returns content-addressed blackboard entries for every artifact under the corresponding knowledge/ subtree (plus enumerated root files); file_version queries are unchanged; conflict detection unchanged; docs carry one clarifying sentence; full suite green; live smoke on host shows the tool returning skill/adr/research rows to the agent.

**ARTIFACTS:**

- ADD `src/fa/blackboard/artifact_index.py` (S1)
- EDIT `src/fa/inner_loop/tools/blackboard_query.py` (S2: lazy-index call + additive result field)
- EDIT `AGENTS.md:271` (S3: one-sentence clarification)
- EDIT `knowledge/llms.txt:44` (S3: same)
- ADD `tests/test_blackboard_artifact_index.py` (S4: 14 new tests)
- EDIT `tests/test_blackboard_query_tool.py` (S4: T3b/T6, 2 new tests)
- EDIT `knowledge/BACKLOG.md` (flip I-56 status to closed, note the shipped artifacts)
- EDIT `worklogs/HANDOFF.md` (update §Next)
- EDIT parent plan `worklogs/implementation-plans/cli-trace-substrate-rebaseline-2026-07-25.md` (mark S14 closed)

**CONTRACTS:**

- CT1 VERIFIED (T1, T2, T8, T9, T10)
- CT2 VERIFIED (T0 layout check)
- CT3 VERIFIED (T3, T4, T6, T11, T12)
- CT4 VERIFIED (T5)
- CT5 VERIFIED (grep)

**Done when ALL of:**

- [ ] 14 new C0p/C1 tests pass, 2 new tests in existing file pass, previously-passing blackboard/conflict/session_db/query-tool tests still pass, full suite green.
- [ ] `ruff` + `mypy` clean on changed files (no new `noqa` beyond the two existing-style `# noqa: BLE001` catch-alls, each with the same rationale comment used in existing code).
- [ ] `grep -nE '\brank\b' AGENTS.md knowledge/llms.txt knowledge/reference.md | grep -iv 'bm25\|fts5\|porter'` returns zero.
- [ ] `grep -c 'blackboard\.query(' AGENTS.md knowledge/llms.txt knowledge/reference.md` returns 0.
- [ ] C1 test T3 (first-call indexing) has a MANUAL kill-check confirmed: comment out the `ensure_artifacts_indexed(...)` call in the handler, rerun T3, observe failure, then restore.
- [ ] C1 test T5 (no false conflict) has a MANUAL kill-check confirmed: temporarily add an artifact entry with `type="file_version"` (colliding type), rerun T5, observe conflict detected, then restore.
- [ ] Patch is built against latest `origin/main`, applies cleanly with `git apply --check`, and is emitted to `/home/user/s14-blackboard-artifact-index.patch`.
- [ ] Operator applies the patch, runs `fa update`, and executes the S14 live smoke (S5 step 5) with exit 0/1 and evidence `events.jsonl` showing the tool call + indexed counts.
- [ ] Parent plan header bumped to v12 with S14 marked EXECUTED/LIVE-VERIFIED.
- [ ] BACKLOG I-56 marked closed with a one-line disposition.
- [ ] HANDOFF.md updated to point "Next bounded action" at the post-S14 state (Q11/I-34 P0, or I-55 subagent, or operator's next call).

**The slice is NOT done merely because:** `pytest green`, `ruff green`, `mypy green`. Those are necessary gates; production-path proof is C1 T3 kill-check + host live smoke per parent plan DoD.

---

## 9. Anti-theater and READY gate

- [x] Preflight log exists with real file:line anchors (§1).
- [x] Depth P2 declared.
- [x] Executive intent + non-goals concrete (§0).
- [x] Contracts have named producer/consumer surfaces (§4); both sides of CT3 (producer=indexer, consumer=ToolResult/rows) exist and are tested.
- [x] Path + flag matrix enumerated (§5) — 10 paths × 5 matrix cells, each with a covering T#.
- [x] Central mechanism identified one lazy-indexing seam; no competing mechanism.
- [x] Alternatives considered and rejected with reasons (§3).
- [x] Research-note dispositions: G1-G10 each mapped to a concrete S#/T# or marked out-of-scope with reason (§2).
- [x] Every implementation step has explicit Do/Do-not lists.
- [x] Kill-checks target PRODUCER sites (blackboard.write in indexer; ensure_artifacts_indexed call in handler).
- [x] Type safety: C1 tests use real SessionDatabase/Blackboard/ToolRegistry (no MagicMock at composition root); only failure injection uses monkeypatch.
- [x] No new CLI surface; no new feature flag; no new dependency; no new config.
- [x] Rank claim re-verified (already closed) — no phantom doc-scrub work.
- [x] Conflict isolation proof built into T5.
- [x] Append-only (V6) invariant preserved: new content → new entry + parent_id.
- [x] Q-S14-1/2/3 listed with defaults for operator to override; do not block implementation if defaults are accepted.

Status remains **DRAFT** until the operator:
1. Accepts or revises Q-S14-1 (scope of ARTIFACT_ROOTS), Q-S14-2 (root files), Q-S14-3 (plan entries out of scope).
2. Confirms this is the last parent-plan slice and that the doc/backlog/handoff edits are wanted in the same patch.
3. Approves moving to implementation.

---

## 10. Artifacts inventory

| Artifact | Path | Action | Owner S# |
|---|---|---|---|
| Artifact indexer module | `src/fa/blackboard/artifact_index.py` | ADD | S1 |
| Tool handler | `src/fa/inner_loop/tools/blackboard_query.py` | EDIT (add lazy-index seam + additive result field) | S2 |
| Agent docs | `AGENTS.md:271`, `knowledge/llms.txt:44` | EDIT (one clarifying sentence each) | S3 |
| New C1 test module | `tests/test_blackboard_artifact_index.py` | ADD (14 tests) | S4 |
| Existing tool test | `tests/test_blackboard_query_tool.py` | EDIT (add T3b/T6 cases: T14/T15) | S4 |
| Backlog disposition | `knowledge/BACKLOG.md` (I-56 section) | EDIT (flip status to closed, add disposition note) | S5 |
| Parent workplan | `worklogs/implementation-plans/cli-trace-substrate-rebaseline-2026-07-25.md` | EDIT (header v12, S14 checkbox, evidence) | S5 |
| Handoff | `worklogs/HANDOFF.md` | EDIT (update Next bounded action) | S5 |
| Patch file | `/home/user/s14-blackboard-artifact-index.patch` | ADD (after implementation) | S5 |
## 11. Plan self-review (critical-thinking pass, 2026-08-10)

Per plan-authoring skill "assume-theater" + operator mandate to "search for logic errors", a second pass identified and closed the following issues in v0 of the plan:

| # | Issue found | Resolution |
|---|---|---|
| SR-1 | Code sketch v0 used mtime-based revision suffix `f"{id}-v{int(st.st_mtime)}"`, which can collide on rapid saves (sub-second truncation). | Changed to `f"{logical}-r{uuid4().hex[:8]}"` — collision-free, matches existing `post-<uuid>` style in mutation_guard. |
| SR-2 | Code sketch v0 keyed `existing_by_id` by physical id only, so after the first revision the lookup for "latest entry" on the next index pass would miss v2+ entries (they live under a different physical id). Would cause duplicate insertions / append-only blow-up. | Added `_latest_by_logical_id()` that supports BOTH v1 rows (`id == logical_id`) and revision rows (`payload.logical_id == logical_id`), picking the highest-timestamp entry per logical id. Indexed dict drives change detection correctly. |
| SR-3 | Code sketch v0 had no path-containment check; a symlink inside `knowledge/` pointing to `/etc/passwd` would be read and indexed, potentially leaking secret content into blackboard payloads/titles. | Added `_is_within(child, parent)` using `resolve().relative_to(parent.resolve())`; escapes are skipped + recorded as `errors.append(f"escape:{rel}")`. Test T9 variant covers this. |
| SR-4 | S2 handler initially duplicated `ARTIFACT_QUERY_TYPES` frozenset locally — drift risk (if S1 adds a new type and S2 isn't updated, the handler wouldn't trigger indexing for it). | S2 now lazy-imports `artifact_index` and reads `artifact_index.ARTIFACT_TYPES` directly; no duplicated constant. C0p drift test added to test plan (assert `ARTIFACT_QUERY_TYPES` — removed; the handler uses the imported constant directly, so drift is impossible). |
| SR-5 | S2 handler entered the lazy-import block only when type was in a hard-coded set, which meant we'd never pay the lazy-import cost for non-artifact types — but once we removed the duplicated constant the outer condition had to widen. Refined to: enter block when `type_ is None or isinstance(type_, str)`; inner `if type_ is None or type_ in ARTIFACT_TYPES` skips indexing for non-artifact types like `file_version`. Post-first-call cost on `file_version` queries = one dict lookup on `sys.modules` (Python caches the import) — negligible. | Documented; covered by T6 (spy on ensure_artifacts_indexed for file_version query → call_count=0). |
| SR-6 | Tool description didn't mention artifact types — model would have to discover behavior by trial. | Added one sentence to ToolSpec description listing the artifact types and directing substring search to fs_instant_grep. |
| SR-7 | `set(ARTIFACT_TYPES) | {"research"}` was redundant — "research" is already in ARTIFACT_TYPES. | Removed the union; `target_types = set(types) if types is not None else set(ARTIFACT_TYPES)`. |
| SR-8 | C0p `_SyntheticLatest` stand-in was unnecessary complexity; after a write we can simply place the real `BlackboardEntry` into the `latest` dict. | Removed the class; code now stores the real entry directly. |
| SR-9 | Code sketch passed flake8/mypy review: `import uuid` was missing (used for revision suffix). | Added to imports. |
| SR-10 | CT4 kill-check paragraph was an internal design note ("Wait — kill-check direction must be…") rather than a clean statement. | Replaced with a clear kill-check: mutating the synthetic entry's type to overlap with an artifact type → conflict detected → T5 fails. |
| SR-11 | Risk RK-4 (symlink escape) was listed in §7 but not enforced in code. | Added `_is_within` check in the loop (SR-3) and named T9-variant as the covering test. |
| SR-12 | `scanned/added/updated/skipped_unchanged` set membership was done with `indexed_types.add(entry_type)` BEFORE the early-continue checks (too_large, escape, stat-error). Cleanup: move `stats.scanned += 1; stats.indexed_types.add(entry_type)` to immediately after entering the loop body (still before per-file checks; counted as "considered" even if rejected). | Kept as-is (counter counts "considered" files); rejection causes are in `errors` so the two sums reconcile. |
| SR-13 | No py-compile check of the code sketch. | Ran py_compile on the sketch (with stubs for fa.blackboard imports) → compiles OK. |

All issues closed. The plan is now internally consistent.

---
