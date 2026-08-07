# NOTE — Blackboard module: complete audit (as-planned vs as-built vs remaining)

*Date: 2026-08-07. MAX-effort, deep source-verified audit. Cross-references the prior substrate
note (`note-substrate-reality-vs-intent.md`).*

---

## Executive summary

The blackboard is **partially shipped**. Its **write-conflict-detection substrate is fully built,
wired into every mutating tool, and heavily tested** (this is the part that works and is live during
`fa run`/`fa workflow`). But its **second advertised role — a queryable artifact index over
skills/ADRs/research/plans/tool_specs consumed by the LLM — is NOT built**: the storage schema
supports it, a query tool exists, but **no producer writes those rows**, so the LLM-facing
"query the blackboard for knowledge artifacts" surface returns empty. Docs still advertise the
artifact-index role (false today).

---

## 1. What the plans intended (the full feature set)

From `substrate-formalization-and-reduction.md`, `substrate-*.md`, `project-overview.md §1.2.6`,
ADR-13/14/16:

**A. Storage — typed, versioned, content-hashed, append-only blackboard (I-6.2/I-6.4):**
- `BlackboardEntry` with: id, type, content_hash (sha256), toolchain_digest, schema_version,
  parent_id, read_set, write_set, assumptions, version_dependencies, timestamp, payload.
- Append-only, content-addressed, never overwritten (I-6.3).
- Dual-store: per-run SQLite `session.db.blackboard` (authority) + `.fa/blackboard/blackboard.jsonl`
  (best-effort mirror).

**B. Queryable artifact index (the "formal substrate" for the LLM):**
- Blackboard = **index over knowledge artifacts** (`index_repo()` like FTS): each ADR/skill/research/
  role/tool_spec = a typed `BlackboardEntry`.
- A single unified loader `load_artifacts(type, query, current_files)` returning entries "sorted by
  **rank**", replacing the 5 per-type markdown loaders.
- The LLM discovers artifacts via `blackboard.query(type, key)` → AGENTS.md/llms.txt say to use it.

**C. Conflict detection via transactional read/write-set semantics (I-6.1/I-6.3):**
- Every write declares read_set/write_set/assumptions/version_dependencies.
- `detect_conflict()` → no silent overwrite → `conflict_detected` fail code.

**D. Control Unit (L2MAC-style)** managing blackboard reads/writes.

## 2. What is ACTUALLY built and live (source-verified)

### A. Storage — ✅ COMPLETE
- `BlackboardEntry` dataclass (blackboard.py:29) has ALL 13 planned fields + `run_id`.
- `session.db.blackboard` table (session_db.py:216) has all columns; index on (session_id,type,timestamp).
- `write()` dual-writes to DB (authority) + JSONL mirror (best-effort), stamps writer `run_id` (blackboard.py:223).
- `read(id)`, `query(type,key)`, `detect_conflict()` all implemented with authority + JSONL fallback.
- `write_blackboard_row` is append-only (V6 fix — rejects duplicate id, `blackboard_duplicate_id`).
- **This half fully matches the plan.**

### B. Artifact index — ❌ NOT BUILT (the gap)
- **Storage machinery exists** (a `type` column, a `query(type)`), but **no code writes artifact rows**.
- The ONLY production writer is `mutation_guard.record_mutation` → `type="file_version"` (write-conflict log).
- No `index_repo()` over knowledge/ exists. No `type="skill"/"research"/"adr"/"role"/"tool_spec"`
  producer anywhere in `src/` (grep = only test fixtures).
- **`fs_blackboard_query`** tool exists and works, but querying `type="skill"/"research"/"adr"` returns
  **empty** on a real run.
- **`subagent_runner`** queries `type="plan"` for filtered history (subagent_runner.py:211) — returns
  **empty** unless a test wrote a plan fixture.
- No `load_artifacts` unified loader exists. `rank` is **not a blackboard concept**: the only `rank`
  in the codebase is the FTS5 relevance rank (`fts_index.py:188`, used by `fs_instant_grep`) and an
  unrelated diagnostic severity sort rank (`authoring_tcb.py`). The blackboard schema/entry has no
  `rank` field (verified: zero `rank` in `blackboard.py`/`session_db.py` blackboard code).
- The "Control Unit" (D) is not a distinct component; reads/writes are simple method calls.

### C. Conflict detection — ✅ COMPLETE + WIRED + TESTED
- `check_mutation_allowed` (mutation_guard.py:151) calls `detect_conflict` before every
  `fs_write_file`/`fs_edit_file`; returns `conflict_detected` or `blackboard_unavailable` (fail-closed).
- `record_mutation` (mutation_guard.py:207) writes the `file_version` entry after a successful write.
- read/write sets: `read_file` → transaction.read_set; write/edit → transaction.write_set; wired via
  `SessionState.record_tool_call` (state.py:651-658) + `transaction.add_read/add_write`.
- Tests: `test_s5_blackboard_contract.py` (V6 append-only, S3-F10 non-expiring, parent_id rule),
  `test_blackboard_conflict.py`, `test_quality_slice_coverage.py`, `test_session_db_authority.py`.
- **This half is genuinely shipped and is what the LLM's mutating tools interact with live.**

## 3. The LLM-visible substrate during `fa run` / `fa workflow` (what actually works)

During a real run, the blackboard's **only live, LLM-relevant role** is:
- **Conflict detection on writes** (silent, invisible to the LLM unless a conflict fires).
- `fs_blackboard_query` is registered, but returns **only `file_version` rows** (write history), not
  knowledge artifacts.

The LLM's **working knowledge substrate** is the **filesystem + FTS index**: `fs_instant_grep`
(real queryable index), `fs_glob`, `fs_grep`. The docs (AGENTS.md §Querying Artifacts, llms.txt) that
say "query the blackboard for skills/ADRs/research" describe an **unbuilt** surface.

## 4. Complete gap ledger (what remains)

| # | Intended (plan) | Actual | Status | Owner |
|---|---|---|---|---|
| G1 | Blackboard = queryable index over knowledge artifacts | Only `file_version` (conflict log) rows | **UNBUILT** | I-56 |
| G2 | `blackboard.query(type="skill"/"research"/"adr")` returns artifacts | Returns empty (no writer) | **UNBUILT** | I-56 |
| G3 | Unified `load_artifacts(type,query)` loader | None; 5+ per-type markdown loaders remain | **UNBUILT** | I-56 |
| G4 | `rank` on blackboard query results | Blackboard has no `rank` field; `rank` only exists in FTS (`fts_index.py:188`) + diagnostic sort (`authoring_tcb.py`). Docs already corrected (S13.10 scrub) — no false claim remains. | **N/A (not a blackboard feature)** | I-56 |
| G5 | Artifact index `index_repo()` over knowledge/ | None | **UNBUILT** | I-56 |
| G6 | `subagent_runner` filtered-history `type="plan"` | Empty unless fixture | **UNBUILT producer** | I-55 |
| G7 | Control Unit managing blackboard | Simple method calls | **Not a distinct component** | I-56 |
| G8 | Storage schema (typed/versioned/content-hashed/append-only) | ✅ Complete + tested | **DONE** | — |
| G9 | Conflict detection (read/write-set, fail-closed, parent_id) | ✅ Complete + wired + tested | **DONE** | — |
| G10 | Docs advertise artifact-index role | llms.txt:42,44,85-87 + AGENTS.md still instruct `fs_blackboard_query(type="skill"/"research"/"adr")` which returns empty | **MISLEADING** | I-56 |

## 5. What "current state" really is (one paragraph)

The blackboard module is **a mature, tested write-conflict-detection substrate** (G8/G9 fully done),
not an artifact index. It is live and correct during `fa run`/`fa workflow` for detecting concurrent
write conflicts on mutating tools. But its other intended role — the **formal queryable substrate the
LLM uses to discover knowledge artifacts** — is entirely unbuilt (G1–G7), and the docs still tell the
LLM to use it that way (G10), which is false today. The LLM's actual knowledge-discovery substrate is
`fs_instant_grep` (FTS) + filesystem.

## 6. Recommended next slice (to close the gap, per I-56)

Build the **artifact index producer** (G1/G2/G3/G5):
1. `index_repo()` that walks `knowledge/` (skills, ADRs, research, roles, tool_specs) and writes typed
   `BlackboardEntry` rows (`type="skill"`, `"adr"`, `"research"`, ...) with content_hash + read_set.
2. A unified `load_artifacts(type, query, current_files)` loader (G3) OR wire the existing
   `fs_blackboard_query` to read the index.
3. Decide on `rank` (G4): either implement a real ranking (FTS/BM25 overlap) or correct the docs to
   not claim it.
4. Correct AGENTS.md/llms.txt/reference.md (G10) so the LLM isn't told to query an empty index.
5. Wire the `plan` producer for `subagent_runner` (G6) or gate it off.

Until then: **do not assume the blackboard is an artifact index.** It is a conflict log. The LLM's
working substrate for finding things is `fs_instant_grep`/`fs_glob`/`fs_grep`.

---

## 7. Source-verification log (every claim above was grep/read-confirmed)

| Claim | Verified at | Result |
|---|---|---|
| `BlackboardEntry` dataclass exists | `blackboard.py:29` | ✅ |
| `Blackboard.write` dual-writes authority+mirror | `blackboard.py:223` | ✅ |
| blackboard table schema in `session.db` | `session_db.py:216` | ✅ |
| only production writer is `type="file_version"` | `mutation_guard.py:118` | ✅ |
| no `type="skill"/"research"/"adr"/"tool_spec"/"role"` producer in src | grep over `src/fa/` | ✅ confirmed none |
| `check_mutation_allowed` → `detect_conflict` | `mutation_guard.py:130,151` | ✅ |
| `record_mutation` → `blackboard.write` | `mutation_guard.py:182,207` | ✅ |
| `read_file`→read_set, write/edit→write_set (transaction) | `state.py:651-658` | ✅ |
| `subagent_runner` queries `type="plan"` | `subagent_runner.py:211` | ✅ (empty in prod) |
| `fs_blackboard_query` registered (implementer/planner) | `profiles.py:74,83,262` | ✅ |
| no `load_artifacts` unified loader | grep `def load_artifacts` | ✅ confirmed none |
| `rank` only in FTS + diagnostic sort, not blackboard | `fts_index.py:188`, `authoring_tcb.py` | ✅ corrected |
| docs still instruct `fs_blackboard_query(type="skill")` | `llms.txt:42,85-87`, AGENTS.md | ✅ (G10 valid) |
| docs no longer claim blackboard `rank` | `AGENTS.md`/`llms.txt`/`reference.md` grep | ✅ already corrected |

> **Review note (2026-08-07):** two earlier claims were imprecise and are now corrected —
> (1) `rank` is NOT "zero anywhere" (FTS has one); it is simply not a blackboard field.
> (2) the docs' `rank` claim was already removed in the S13.10 doc scrub, so G4 is reframed as
> "not a blackboard feature" rather than "false doc claim". Everything else verified as written.
