# PLAN: fs_blackboard_query tool                    Plan-ID: PLAN-fs-blackboard-query
Status: IMPLEMENTED (S1-S5 green; full suite 2575 passed)          Depth: P1            Revision: v4
Changed-since-last: final production-review pass (2026-08-06) — gap closure: T2 (key filter) and T6
    (invalid params) were specified in §6 but had NO test; added both to tests/test_blackboard_query_tool.py
    (14 tests now). Verified session-scoping (Blackboard.query filters by session_id on the normal path),
    kill-checks for T2. Static gates + full suite green.
Upstream: user request — "Build `fs_blackboard_query` — a real tool wrapping `Blackboard.query()`";
research brief `research-blackboard-query-tool-gap.md` (2026-08-06).

## Preflight log
  roots checked:
    - fa.inner_loop.coder_loop drive_session (tool registry build + dispatch)
    - fa.inner_loop.profiles build_registry_for_role (per-role tool registration)
    - fa.inner_loop.tools.__init__ _register_extra_tools (supplemental registration)
    - fa.inner_loop.tools.instant_grep (gold read-only artifact tool)
    - fa.blackboard.blackboard Blackboard.query (the capability to wrap)
    - fa.inner_loop.context get_current_session (tool->session/blackboard injection seam)

  greps/reads -> findings:
    - ToolSpec(name, description, input_schema, permission, handler, tags, ...) @ registry.py:74
    - ToolPermission = Literal["read","workspace"] @ registry.py:20
    - ToolResult.ok/fail + ToolError @ registry.py:37
    - instant_grep handler pattern (read-only, returns paths not content) @ tools/instant_grep.py:145-232
    - Blackboard.query(type,key)->list[BlackboardEntry] @ blackboard/blackboard.py:297
    - Blackboard binds SessionDatabase via ctor; tool accesses via contextvar get_current_session() @ context.py:30
    - SessionState.blackboard: Blackboard|None @ state.py:361; populated FAIL-OPEN @ state.py:469-485
    - profiles.py: PROFILES_RAW per-role tool lists @ :30-99; _build_tool_builders @ :220+; _add_optional_tool_builders @ :107
    - tools/__init__.py: _register_extra_tools + build_baseline_registry/planner/eval @ :86-260
    - tool_names.py: LEGACY_TO_NEW + TOOL_NAMES=frozenset(LEGACY_TO_NEW.values()) + is_valid_wire_name;
      CT5 test test_map_covers_all_tool_spec_names asserts ToolSpec names ⊆ TOOL_NAMES;
      test_all_legacy_names_are_dotted asserts every legacy KEY is dotted (tool_names.py:58-61).
    - TOOL_NAMES is a pure function of LEGACY_TO_NEW.values() → a non-legacy tool must be added via a UNION,
      not as a LEGACY_TO_NEW key (would break the dotted-legacy-key test).
    - Blackboard.query / query_blackboard_rows have NO LIMIT (session_db.py:852-862); rows are ordered
      timestamp ASC (oldest first) → the tool must slice rows[-limit:] for "most recent N".
    - ToolRegistry.dispatch wraps a handler Exception as ToolResult.fail("internal_error", ...)
      (registry.py:190-201) → the handler MUST catch Blackboard.query exceptions itself to surface
      "blackboard_query_failed".
    - Production roles: _build_role_registry (cli.py:2176-2193) builds implementer (baseline/coder),
      planner, verifier (eval). The `researcher` profile in PROFILES_RAW is NEVER built by a production root
      → DEAD profile; do not wire into it.
    - blackboard currently holds ONLY type="file_version" rows (writer=mutation_guard.py:207 via _entry_for). No src code writes type="skill"/"research". ← KEY FINDING
    - Registration seam: build_registry_for_role reads PROFILES_RAW[role]["tools"] and builds each via
      _build_tool_builders (profile path = role-scoped artifact tools: instant_grep/glob/grep/read).
      _register_extra_tools is the UNIFORM observability+pair supplement applied to every role
      (chronicle/usage/list_tasks/checkpoint/undo/diff/send_ctrl_c); instant_grep is profile-scoped, NOT a
      default extra (include_instant_grep=False). ARCHITECTURE: fs_blackboard_query is an artifact-discovery
      tool → belongs in the profile path (implementer/planner), like instant_grep, NOT in _register_extra_tools.

  gold patterns mirrored:
    - tools/instant_grep.py (build_*_tool -> handler(params)->ToolResult, read permission, returns paths not content)
    - tools/observability.py build_usage_tool (stateless read tool, no filesystem/DB deps)
    - tests: test_inner_loop_tools.py, test_coverage_failure_paths.py (tool dispatch C1 patterns)

  conflicts/invariants found:
    - ADR I-6.2: blackboard "append-only, content-hashed, queryable, detect_conflict()" — queryable is a documented invariant.
    - S13.10 wire-name rule ^[a-zA-Z0-9_-]{1,64}$; new tool must be underscore, added to TOOL_NAMES.
    - AGENTS.md / llms.txt / reference.md reference blackboard.query(...) — today that tool does not exist (dead instruction).
    - Permission tiers: read/workspace only; a read-only query tool is "read".

  as-is liveness:
    - Blackboard.query capability: L3 (tested via session_db authority).
    - blackboard as an LLM tool: L0 (no ToolSpec; no builder; not registered).
    - AGENTS.md instruction: L1 (import-reachable text, but callable tool absent) → dead.

  unresolved -> Q#:
    - Q1 (NON-BLOCKING): does AGENTS.md's claimed type="skill"/"research" data exist to query? Finding: NO writer today. Default: build the tool to query whatever rows exist (file_version now; skill/research later when a writer lands). Recorded; not blocking the tool build.
    - Q2 (RESOLVED via review): which profiles get the tool? **Reachable production roles only** (verified): `_build_role_registry` (cli.py:2176-2193) builds `implementer` (baseline → coder), `planner`, and `verifier` (eval). The `researcher` profile exists in PROFILES_RAW but is **never built by any production root** (grep: no `build_registry_for_role("researcher")` call). So the tool is wired into **implementer + planner** profiles; **verifier (eval) stays excluded**. Do NOT add to researcher (dead profile) or verifier. Recorded, blocking S2 scope.

## 0. Executive intent
  IDEA: Add a real, LLM-callable `fs_blackboard_query` tool that wraps `Blackboard.query()` and
        returns compact artifact rows (id, type, content_hash, read/write sets, timestamp), so the model
        can discover artifacts without grep -ril (which AGENTS.md says caused a 124-step timeout) and so
        the AGENTS.md instruction becomes true. NOTE: the docs' "rank" claim is FALSE (no rank field
        exists) — this tool returns timestamp-ordered rows, NOT rank.

  PROJECT MEANING: In the inner-loop tool registry, this becomes the formal-substrate artifact-lookup
        tool — the same surface AGENTS.md/llms.txt/reference.md already promise. It belongs here
        (tools/) because it must be registered in the per-role registry and dispatched through the
        standard ToolSpec handler contract, reusing the existing get_current_session()->blackboard seam.

  GOAL (G1): `fs_blackboard_query` is a registered, dispatchable tool returning structured
        blackboard rows via the real `Blackboard.query()`.
  GOAL (G2): The tool is wired into the reachable read-only+implementer roles — **implementer (coder baseline) + planner** — and the canonical
        TOOL_NAMES set (no dotted legacy anywhere). Verifier (eval) is excluded by design.
  GOAL (G3): The AGENTS.md dead reference becomes true (tool exists); docs aligned to `fs_blackboard_query`.

  NON-GOALS:
    - Do NOT build a skill/research blackboard WRITER (no producer for type="skill" today). Out of scope.
    - Do NOT change Blackboard.query / session_db (read-only wrapper).
    - Do NOT add the tool to verifier profile (bash-only role).
    - Do NOT wire into the `researcher` profile — it is a declared-but-not-yet-built subagent role (no
      production root builds its registry; run_stateless runs raw bash). Out of scope; tracked as M3 N/A.
    - Do NOT build prompt-cache, conformance, or thinking-mode work here.
    - Do NOT add fuzzy/rank scoring — use existing rows + timestamp ordering as-is; the docs' "rank" is a
      false claim (GAP-5), not a feature to build.

  INTENT: Whenever a role has a session blackboard, the model can query it through a real tool
        whose result is structured, and when no blackboard exists the failure is an explicit
        `blackboard_unavailable` ToolResult (never a silent empty or a crash).

  MECHANISM SKETCH: registry/dispatch → handler → get_current_session() → session.blackboard →
        Blackboard.query(type,key) → compact rows → ToolResult.ok(..., result=rows). No blackboard →
        ToolResult.fail("blackboard_unavailable").

  PROOF SKETCH: root=real ToolRegistry + a SessionState with a bound Blackboard; oracle=ToolResult.result
        contains the queried rows; kill-check removes the `blackboard.query(...)` call in the handler
        → test fails.

  SIZE: S

## 1. Non-goals & minimal-mechanism check
  Non-goals: §0 above.
  Minimal mechanism: reuses existing ToolSpec/ToolResult contract, existing
        get_current_session()->blackboard seam, existing Blackboard.query. New code is ~one tool
        module + one builder + registration lines + one TOOL_NAMES entry. No new deps, no new seams,
        no new DB/API.
  New-component gate: tool is justified because AGENTS.md/llms.txt/reference.md already instruct the
        model to call it (documented capability); omitting it leaves a dead instruction + forces
        grep -ril (documented 124-step timeout); existing instant_grep/glob do NOT expose the
        blackboard's content-hash/read-write-set/assumption metadata; it is deterministic (no LLM call).

## 2. Current state → target state (liveness-scored)
  AS-IS:
    Dimension          | Finding
    Entry points       | drive_session builds registry via _build_role_registry -> build_registry_for_role (cli.py:2193); supplemental via _register_extra_tools
    Existing types     | ToolSpec, ToolResult, ToolError, BlackboardEntry
    Producers/consumers| Blackboard.query is a tested capability (session_db); NO tool consumes it; AGENTS.md text references it (dead)
    State stores       | session.db `blackboard` table (authoritative) + blackboard.jsonl mirror
    Flags/defaults     | blackboard_enabled default True (FAIL-OPEN, state.py:469)
    Tests today        | test_session_db_authority (query capability L3); tool-level: instant_grep tests
    Liveness           | Blackboard.query: L3; as LLM tool: L0; AGENTS.md instruction: L1(dead)

  GAP ledger:
    GAP-1: No `fs_blackboard_query` ToolSpec / builder / registration → L0.
    GAP-2: No TOOL_NAMES entry → S13.10 CT5 would fail if a tool used an unlisted name.
    GAP-3: AGENTS.md/llms.txt/reference.md reference a tool that does not exist (dead instruction).
    GAP-4: No writer for type="skill"/"research" (documented in research brief) → query returns only
           file_version rows today. NON-GOAL; recorded.
    GAP-5: Docs advertise `blackboard.query` returns "rank" — VERIFIED FALSE (no rank field in
           BlackboardEntry/query/session_db). The new tool must NOT emit rank; S4 corrects the agent-facing
           docs' rank wording. NON-GOAL to build a rank feature.

  TO-BE:
    - New tool `fs_blackboard_query` (read permission) in tools/; builder `build_blackboard_query_tool()`.
    - Registered in implementer + planner profiles (the only reachable artifact roles; Q2 resolved).
    - `fs_blackboard_query` added to TOOL_NAMES (tool_names.py) via a direct canonical frozenset;
      LEGACY_TO_NEW / legacy_to_new pruned (completed migration ledger).
    - Docs (AGENTS.md §Querying Artifacts, llms.txt §42-89, reference.md:14) aligned to `fs_blackboard_query`
      (dot removed, tool now real).
    - Target liveness: L3 — C1 dispatch test with real registry + bound blackboard, kill-check on the
      `blackboard.query` call.

## 3. Contracts
  CT1 (function) fs_blackboard_query
    TYPE: function/tool
    PRODUCER: NEW src/fa/inner_loop/tools/blackboard_query.py build_blackboard_query_tool() -> ToolSpec
    ROOTS/CALLERS: ToolRegistry.dispatch -> spec.handler; registered via PROFILES_RAW tools lists
        (implementer + planner) through build_registry_for_role. NOT via _register_extra_tools.
    INPUT: params {type?: str, key?: str, limit?: int} — `limit` is a NEW tool-level cap mirroring
        fs_instant_grep's limit param (instant_grep.py:224), NOT an existing Blackboard feature
        (Blackboard.query/query_blackboard_rows have no limit). The tool slices rows[-limit:] to cap output.
    OUTPUT: ToolResult.ok(summary, result={"rows":[{id,type,content_hash,read_set,write_set,assumptions,version_dependencies,timestamp,path}], "type","key","limit","count"})
        where `path` is derived from the entry's read_set/write_set (the artifact paths) plus
        `payload["path"]` when present (file_version writes payload={"path": write_set[0]}). Compact
        metadata only — NEVER the full payload blob.
    ERRORS: ToolResult.fail("blackboard_unavailable", ...) when no session/blackboard;
            ToolResult.fail("blackboard_query_failed", ...) on Blackboard.query exception — the handler
                MUST catch it itself (ToolRegistry.dispatch wraps a handler Exception as "internal_error",
                registry.py:190-201, which would mask the intended code);
            ToolResult.fail("invalid_params", ...) on schema violation.
    SIDE EFFECTS: none (read-only). No FS/DB write.
    INVARIANTS:
        - never returns payload blobs (token efficiency); returns compact metadata only.
        - `limit` is applied by SLICING the returned list (Blackboard.query/query_blackboard_rows have NO
          LIMIT; verified session_db.py:852-862). Rows are ordered timestamp ASC (oldest first), so the
          tool takes the LAST `limit` rows for "most recent N".
    IMPLEMENTATION CONSTRAINT (circular import): import `get_current_session` (and `fa.blackboard` if
        needed) lazily INSIDE the handler, mirroring edit_file.py:84 — module-level import would create
        a cycle via state.py/profiles.
    KILL-CHECK: removing the `blackboard.query(...)` call in the handler → T1 fails.

  CT2 (signal) blackboard_unavailable
    TYPE: signal/deny-reason (reuses existing code constant BLACKBOARD_UNAVAILABLE, mutation_guard.py:48)
    PRODUCER: blackboard_query handler when session is None or session.blackboard is None
    CONSUMER: ToolResult.fail error.code surfaced to the loop / model
    PATHS: P2
    KILL-CHECK: removing the guard → T3 fails.

  CT3 (data) TOOL_NAMES membership
    TYPE: data/constant
    SCHEMA: additive — add "fs_blackboard_query" to TOOL_NAMES (tool_names.py)
    READ/WRITE: tool_names.py; S13.10 test test_s13_10_tool_names.py asserts ToolSpec names ⊆ TOOL_NAMES
        (test_map_covers_all_tool_spec_names scrapes name="(fs|pr)_[a-z_]+" from tools/*.py).
    LEGACY PRUNING (operator direction + review): LEGACY_TO_NEW / legacy_to_new are a one-time migration
        ledger from the completed S13.10 rename. They are NOT used by any production src file (verified:
        tool_names.py is not imported anywhere in src; only test_s13_10_tool_names.py references it).
        Recommend REPLACING the LEGACY_TO_NEW-derived TOOL_NAMES with a direct canonical frozenset:
            TOOL_NAMES: frozenset[str] = frozenset({
                "fs_read_file", "fs_write_file", "fs_edit_file", "fs_run_bash", "fs_glob", "fs_grep",
                "fs_instant_grep", "fs_checkpoint", "fs_undo", "fs_diff", "fs_send_ctrl_c",
                "fs_chronicle_search", "fs_list_tasks", "fs_usage", "fs_spawn_subagent", "pr_prepare",
                "fs_write_file_limited", "fs_apply_patch", "fs_read", "fs_blackboard_query",
            })
        This removes the legacy ledger entirely, keeps the S13.10 enforcement (test still checks every
        ToolSpec.name ∈ TOOL_NAMES + no dots), and makes adding fs_blackboard_query trivial (just add to
        the set). REMOVE obsolete tests: test_all_legacy_names_are_dotted and
        test_legacy_to_new_identity_for_non_legacy (they test the deleted ledger, not a production
        invariant). Keep test_map_covers_all_tool_spec_names, test_no_dotted_tool_spec_names_remain,
        test_no_new_name_contains_a_dot, test_all_new_names_match_wire_pattern (real invariants).
        DECISION NEEDED: is this pruning in-scope for this slice or a separate cleanup? Default: in-scope
        (small, removes debt, makes S3 correct).
    KILL-CHECK: removing "fs_blackboard_query" from TOOL_NAMES → T5 fails.

  CT4 (invariant) no dotted wire name
    TYPE: invariant (S13.10 CT1)
    ENFORCED: is_valid_wire_name + test_s13_10_tool_names; new tool must be underscore
    KILL-CHECK: a dotted name reintroduced → test_s13_10 fails.

## 4. Path & flag matrix
  P# | Trigger | File:symbol | Flag | Covering S# | T#
  P1 | happy: session + blackboard, type/key/limit -> rows | NEW tool handler | blackboard_enabled=True | S1,S2 | T1
  P2 | no session / no blackboard -> blackboard_unavailable | NEW tool handler guard | blackboard_enabled=False | S1 | T3
  P3 | query exception -> blackboard_query_failed | NEW tool handler except | any | S1 | T4
  P4 | invalid params (schema) -> invalid_params | ToolRegistry.validate | any | S1 | T6
  P5 | empty result set -> ok with count=0, rows=[] | NEW tool handler | any | S1 | T7
  P6 | limit clamp (default 10, max 50) | NEW tool handler | any | S1 | T8

  M# | Flag/env/role | Proves | Covering | T#
  M1 | implementer profile (baseline/coder) | tool present in coder registry | S2 | T9
  M2 | planner profile | tool present | S2 | T9
  M3 | researcher profile | N/A — DEAD profile (never built by a production root; verified cli.py:2176-2193). No wiring, no test. | S2 | N/A (why: dead)
  M4 | verifier profile (eval) | tool ABSENT (non-goal) | S2 | T10
  M5 | `fa inner-loop-smoke` (build_baseline_registry) | tool present; session bound but blackboard disabled (FeatureFlags blackboard_enabled=False, cli.py:1056) → dispatch returns blackboard_unavailable, no crash | S2 | T11

## 5. Step-by-step implementation
  Default ordering: discover(√) -> types/schema -> producer tool module -> builder -> registration ->
  root wiring -> verification + kill-checks -> docs.

  ### Step S1: add tool module + handler (producer)
  Traces-to: G1, CT1, CT2; Depends-on: none; Target liveness: L0->L1
  Edit:
    - path: src/fa/inner_loop/tools/blackboard_query.py   symbol: NEW build_blackboard_query_tool
    - handler:
      1. validate type/key/limit via json-schema: schema enforces `type: object`, properties
         {type: string|null, key: string|null, limit: integer, minimum:1, maximum:50}; required: none
         (all optional). limit is clamped to default 10 / max 50 in the handler via optional_int +
         clamp (mirror validate_search_params, tools/_common.py). schema rejects wrong param types;
         handler normalizes limit.
      2. LAZY import get_current_session INSIDE handler (mirror edit_file.py:84; avoids circular import
         through state.py/profiles).
      3. session=get_current_session(); if None or session.blackboard is None ->
         ToolResult.fail(BLACKBOARD_UNAVAILABLE) (import the constant lazily or use the string literal
         "blackboard_unavailable" matching mutation_guard.py:48 value).
      4. rows = session.blackboard.query(type=type, key=key)  — in a try/except that returns
         ToolResult.fail("blackboard_query_failed", ...) on exception (REQUIRED so dispatch does NOT
         mask it as internal_error).
      5. rows = rows[-limit:]  (rows is list[BlackboardEntry]; ordered timestamp ASC oldest-first; take
         the most recent `limit`).
      6. compact each BlackboardEntry (attribute access — it is a dataclass, blackboard.py:29-50) to a
         metadata dict: {id: e.id, type: e.type, content_hash: e.content_hash,
         read_set: e.read_set, write_set: e.write_set, assumptions: e.assumptions,
         version_dependencies: e.version_dependencies, timestamp: e.timestamp,
         path: (e.payload.get("path") if isinstance(e.payload, dict) else None) or
               (e.write_set[0] if e.write_set else (e.read_set[0] if e.read_set else None))}
         Do NOT include the full payload blob.
      7. return ToolResult.ok(summary, result={"rows":[...], "type", "key", "limit",
         "count": len(rows)}).
  Do: mirror instant_grep handler + ToolResult.fail/ok + read permission + max_context_bytes (small, ~2048).
  Do-not: read payload content blobs; write anything; call Blackboard by constructing a new instance
      (must use the session-bound one, i.e. session.blackboard).
  Exit: [ ] grep confirms blackboard_query.py exists; [ ] handler returns ToolResult for all paths P1-P6.
  Kill-check: removing `blackboard.query(...)` call -> T1 fails.

  ### Step S2: builder + registration (root wiring, L1->L2/L3)
  Traces-to: G1, CT1; Depends-on: S1
  Edit:
    - profiles.py `_build_tool_builders`: add a lazy-import builder for fs_blackboard_query, e.g.
      `builders["fs_blackboard_query"] = lambda: build_blackboard_query_tool()` inside a try/except that
      logs WARNING on failure. Insert it in `_build_tool_builders` (after the fs_instant_grep block,
      before `_add_optional_tool_builders(builders, root)` at profiles.py:257) OR inside
      `_add_optional_tool_builders` — either is reachable; the builder must be in the dict returned by
      `_build_tool_builders` (profiles.py:262). Pattern mirrors fs_read_file/fs_instant_grep builders.
    - PROFILES_RAW: add "fs_blackboard_query" to the `implementer` and `planner` tools lists ONLY.
      Do NOT add to `researcher` (dead profile — never built; would be dead wiring) and NOT to `verifier`.
  Do-not: add to verifier or researcher profiles; do NOT touch _register_extra_tools. ARCHITECTURAL REASON
      (verified against project-overview Pillar-3 token-efficiency + I-7.2, not just tests):
      `_register_extra_tools` is the **uniform observability/pair supplement** applied to every role
      (chronicle/usage/list_tasks/checkpoint/undo/diff/send_ctrl_c). `fs_blackboard_query` is an
      **artifact-discovery tool** — it belongs with `instant_grep`/`glob`/`grep`, which ARE profile-scoped
      (implementer/planner/researcher get them, verifier doesn't; include_instant_grep default False in
      _register_extra_tools confirms this split). A role-scoped artifact tool must be wired through
      PROFILES_RAW tools lists + builder, not bolted on as a uniform extra. (Secondary: adding it to
      _register_extra_tools would also break test_quality_slice_coverage exact-set, but the primary reason
      is the architectural taxonomy.)
  Exit: [ ] grep shows builder wired in _build_tool_builders; [ ] implementer registry (build_baseline_registry)
      contains the tool; [ ] planner registry contains it; [ ] verifier registry does not.
  Kill-check: removing the builder/registration -> T9 (registry membership) fails.

  ### Step S3: canonical TOOL_NAMES entry (+ legacy-ledger pruning)
  Traces-to: G3, CT3, CT4; Depends-on: S1
  Edit:
    - src/fa/inner_loop/tool_names.py: REPLACE the LEGACY_TO_NEW-derived TOOL_NAMES with a direct canonical
      frozenset (see CT3 for the full list), including "fs_blackboard_query". Remove LEGACY_TO_NEW,
      legacy_to_new, and their __all__ entries (they are a completed migration ledger, not production code).
      Keep is_valid_wire_name and the wire-name regex.
    - tests/test_s13_10_tool_names.py: (a) UPDATE the import line 26 to remove `legacy_to_new`
      (`from fa.inner_loop.tool_names import TOOL_NAMES, is_valid_wire_name`) — otherwise the remaining
      tests fail with ImportError; (b) REMOVE test_all_legacy_names_are_dotted and
      test_legacy_to_new_identity_for_non_legacy (they test the deleted ledger). Keep the real-invariant
      tests (test_map_covers_all_tool_spec_names, test_no_dotted_tool_spec_names_remain,
      test_no_new_name_contains_a_dot, test_all_new_names_match_wire_pattern).
  Do-not: leave the tool name out of TOOL_NAMES (would fail test_map_covers_all_tool_spec_names); do NOT
      keep LEGACY_TO_NEW (dead ledger); do NOT leave `legacy_to_new` in the test import (ImportError).
  Exit: [ ] "fs_blackboard_query" in TOOL_NAMES; [ ] is_valid_wire_name("fs_blackboard_query") true;
      [ ] LEGACY_TO_NEW / legacy_to_new removed from src + __all__; [ ] test import updated (no
      legacy_to_new); [ ] no dotted name in any ToolSpec; [ ] S13.10 invariant tests still pass;
      [ ] no legacy-ledger test remains.
  Kill-check: removing "fs_blackboard_query" from TOOL_NAMES -> T5 fails.

  ### Step S4: docs alignment
  Traces-to: G3; Depends-on: S1-S3
  Edit — align ONLY the agent-facing operational docs (where the model/agent reads the tool name):
    - AGENTS.md §7 (line 7) + §Querying Artifacts (lines 260-271): change `blackboard.query` ->
      `fs_blackboard_query` everywhere it is used as an agent-callable tool.
    - knowledge/llms.txt lines 42,44,62,85-89: align `blackboard.query(...)` tool references to
      `fs_blackboard_query`.
    - knowledge/reference.md line 14: align the "How to find artifacts?" row.
  Do-not:
    - Do NOT rewrite historical/archival docs (knowledge/research/*.md, worklogs/archive/*, AP-003,
      skill-writing/SKILL.md). These record past intent/analysis and should NOT be retro-edited; the
      research brief and this plan supersede them. (Verified: 13 files reference blackboard.query; only
      3 are agent-facing operational docs.)
    - Do NOT claim type="skill"/"research"/"adr" returns data unless a writer exists (it does NOT today;
      verified: only mutation_guard writes type="file_version"). llms.txt:85-87 currently DOCUMENT
      `blackboard.query(type="research"/"adr"/"skill")` returning rows that no producer creates — keep the
      tool name aligned but do NOT add new claims of data that doesn't exist; note the gap is tracked
      (Q1/GAP-4) rather than asserted as fact.
    - Do NOT propagate the FALSE "rank" claim. AGENTS.md:265,269 and llms.txt:42,44,89 advertise that
      blackboard.query returns "rank" — VERIFIED FALSE: there is no `rank` field anywhere in BlackboardEntry,
      Blackboard.query, or session_db (grep returned zero). The new tool must NOT return a "rank" field, and
      S4 doc edits should remove/correct the unbacked "rank" wording in the agent-facing docs. Track as a
      doc-reality gap (GAP-5).
  Exit: [ ] grep shows no `blackboard.query` dotted tool reference in the agent-facing docs (AGENTS.md,
      llms.txt, reference.md); [ ] references use `fs_blackboard_query`; [ ] historical/archival docs
      left untouched; [ ] no new skill/research-writer claim added.

  ### Step S5: verification (see §6)
  Traces-to: G1-G3; Depends-on: S1-S4

## 6. Verification plan
  T1 (C1): happy path — real ToolRegistry + SessionState with bound Blackboard (inject a fake session_db
     with known rows); dispatch fs_blackboard_query; oracle=ToolResult.result["rows"] matches queried rows.
     kill-check: remove blackboard.query call in handler -> fail.
  T2 (C1): query filters — type and key filter returned rows; oracle=result rows subset.
     kill-check: remove filter pass-through -> fail. [IMPLEMENTED in final review: test_key_filter]
  T3 (C3): no session / blackboard None -> ToolResult.fail error.code=="blackboard_unavailable".
     kill-check: remove the guard branch -> fail.
  T4 (C1): Blackboard.query raises -> ToolResult.fail error.code=="blackboard_query_failed". NOTE: the
     handler MUST catch the exception itself (a bare handler raise would be masked as internal_error by
     ToolRegistry.dispatch, registry.py:190-201). Test asserts the code is blackboard_query_failed, NOT
     internal_error.
     kill-check: remove the handler's except -> fail.
  T5 (C0p): "fs_blackboard_query" in TOOL_NAMES AND is_valid_wire_name("fs_blackboard_query") true AND
     no dot (S13.10). After the legacy prune, the remaining S13.10 invariant tests still pass:
     test_map_covers_all_tool_spec_names (every ToolSpec.name ⊆ TOOL_NAMES),
     test_no_dotted_tool_spec_names_remain (no dotted name in tools/*.py),
     test_no_new_name_contains_a_dot, test_all_new_names_match_wire_pattern.
     (test_all_legacy_names_are_dotted and test_legacy_to_new_identity_for_non_legacy are DELETED in S3 —
     do NOT reference them as still-passing.)
     kill-check: remove "fs_blackboard_query" from TOOL_NAMES -> fail.
  T6 (C1): invalid params -> ToolResult.fail error.code=="invalid_params" (registry schema validation).
     kill-check: remove schema -> fail. [IMPLEMENTED in final review: test_invalid_params]
  T7 (C1): empty result -> ok with count=0, rows=[].
  T8 (C0p): limit clamp + slicing — default 10, max 50, takes the most-recent `limit` rows (ASC order ->
     tail slice). kill-check: remove the `rows[-limit:]` slice -> fail.
  T9 (C2): build_baseline_registry (implementer) AND build_planner_registry contain fs_blackboard_query.
     kill-check: remove builder/profile wiring -> fail.
  T10 (C2): build_eval_registry (verifier) does NOT contain it. oracle=not in registry.names().
  T11 (C2): build_baseline_registry (inner-loop-smoke path, cli.py:931) builds without error and contains
     fs_blackboard_query. PRECISE SMOKE RATIONALE (verified): `_cmd_inner_loop_smoke` creates a SessionState
     with `FeatureFlags(blackboard_enabled=False)` (cli.py:1056) and `run_session` binds it via
     set_current_session (loop.py:527). So at dispatch `get_current_session()` returns a real session whose
     `session.blackboard is None` (blackboard disabled) → the tool returns
     ToolResult.fail("blackboard_unavailable"), NOT a crash. NOTE: the session IS bound; blackboard is
     None because it is disabled. Test asserts no crash + the unavailable code, not "no bound session".
     kill-check: remove builder -> fail.

  LIVE-PATH PROOF: root=real ToolRegistry via build_registry_for_role("implementer",...) + a real
  SessionState with injected session_db (external DB mocked); matrix=M1; test=T1; oracle=ToolResult.result rows;
  kill-check=blackboard.query call in handler; producer=tool handler; consumer=ToolRegistry.dispatch/loop;
  paths-covered=6/6; contract-check: CT1/CT2/CT3; pyramid=A.

## 7. Risks, rollback, open questions
  RK-1 | Blackboard may be None at runtime (fail-open) | explicit blackboard_unavailable ToolResult (T3) | T3
  RK-2 | query returns only file_version rows today (no skill/research writer) | tool works on existing rows; documented non-goal; future writer separate | T7
  RK-3 | Registration wrong seam | register ONLY via PROFILES_RAW tools lists + builder. Architectural reason: _register_extra_tools is the uniform observability/pair supplement, not role-scoped artifact tools; fs_blackboard_query is an artifact tool (like instant_grep) → profile path. (test_quality_slice_coverage exact-set is a secondary symptom.) | T9
  RK-4 | S13.10 CT5 (dotted name / missing TOOL_NAMES) | prune LEGACY_TO_NEW and use a direct canonical TOOL_NAMES frozenset incl. fs_blackboard_query (S3); legacy-ledger tests deleted with the ledger | T5
  RK-5 | dispatch masks handler exceptions as internal_error | handler catches Blackboard.query exception itself and returns blackboard_query_failed (S1 step 4) | T4
  RK-6 | researcher profile is NOT-yet-built (a declared subagent role, never wired) — would create dead wiring | wire implementer + planner only; researcher documented as N/A (M3) + tracked as aspirational subagent role | T9/T10
  ROLLBACK: additive tool; revert commit. No flag/kill-switch needed (new capability, non-breaking).
  OPEN QUESTIONS:
    Q1 (non-blocking): no skill/research writer exists. Default recorded: build tool to query existing rows; writer deferred. Gated S#: none (S4 docs must not claim skill/research data).
    Q2 (RESOLVED in review): which profiles get the tool? RESOLVED: implementer + planner only (the reachable production artifact roles; verified cli.py:2176-2193). Verifier excluded; researcher is a not-yet-built subagent role (M3 N/A). Gated S#: S2. No open question remains.
    Q3 (RESOLVED by operator, 2026-08-06): is the legacy-ledger pruning in-scope for this slice? RESOLVED: YES — operator confirmed "LEGACY_TO_NEW → direct TOOL_NAMES pruning in-scope for this slice". S3 does the full prune (direct frozenset + delete 2 legacy-ledger tests + fix test import). No open question remains.

## 8. Research-note disposition
  RN1 | "AGENTS.md says use blackboard.query" | Accept — real dead instruction; G3 fixes it (verify: AGENTS.md:7,265,271)
  RN2 | "Blackboard.query is real and tested" | Accept — verified blackboard.py:297 + session_db authority tests
  RN3 | "no tool exposes it" | Accept — verified: no ToolSpec, no builder; grep returned zero
  RN4 | "blackboard should be queryable (I-6.2)" | Accept — ADR DIGEST:733
  RN5 | "query returns skill/research data" | Reject as tool-output claim — NO writer exists today (grep: only mutation_guard writes file_version). Non-goal.
  RN6 | "grep -ril caused 124-step timeout" | Accept as motivation (AGENTS.md), not as a measured fact here; tool is deterministic improvement regardless.
  RN7 | "wire into researcher profile" (from prior draft) | Rewrite — researcher is a DECLARED subagent role (SubagentEnvelope enum + PROFILES_RAW profile) but is NEVER built by any production root today (verified: no build_registry_for_role("researcher") call; run_stateless runs raw bash, no per-role registry). Aspirational, not-yet-built. Wire implementer+planner only; researcher = M3 N/A. G2/S2/M3.
  RN10 | "docs say blackboard.query returns rank" | Reject as a feature claim — no rank field exists (verified). Correct docs; do NOT build rank. GAP-5/S4.
  RN8 | "add identity entry to LEGACY_TO_NEW" (from prior draft) | Reject — breaks test_all_legacy_names_are_dotted (legacy keys must be dotted). Resolved by PRUNING LEGACY_TO_NEW entirely and using a direct canonical TOOL_NAMES frozenset (operator confirmed pruning in-scope), which also removes the two legacy-ledger tests. S3/CT3/T5.
  RN9 | "register via _register_extra_tools" (from prior draft) | Reject — ARCHITECTURAL: _register_extra_tools is the uniform observability/pair supplement (chronicle/usage/pair tools), not role-scoped artifact tools. fs_blackboard_query is an artifact-discovery tool → profile path (implementer/planner), like instant_grep. Secondary: exact-set test would break, but the primary reason is the profile-vs-extra taxonomy. S2/M3.

## 9. Definition of Done (falsifiable)
  STATE: fs_blackboard_query present in implementer (baseline/coder) + planner registries; absent in
         verifier (eval); dispatch returns structured rows via real Blackboard.query; blackboard_unavailable
         on None. Observation: C2 registry membership (T9/T10/T11) + C1 dispatch (T1).
  ARTIFACTS: NEW src/fa/inner_loop/tools/blackboard_query.py; EDIT src/fa/inner_loop/profiles.py
         (builder + PROFILES_RAW implementer/planner), src/fa/inner_loop/tool_names.py (direct canonical
         TOOL_NAMES frozenset + prune LEGACY_TO_NEW/legacy_to_new),
         AGENTS.md, knowledge/llms.txt, knowledge/reference.md, tests/ (test_blackboard_query_tool.py).
  CONTRACTS: CT1 VERIFIED (T1/T2/T4), CT2 VERIFIED (T3), CT3 VERIFIED (T5), CT4 VERIFIED (T5).
  DONE when: all G1-G3 at L3; T1-T11 green (incl. T2 key-filter and T6 invalid-params, added in the
         final review pass — previously specified but untested); remaining S13.10 invariant tests green (test_map_covers_all_tool_spec_names,
         test_no_dotted_tool_spec_names_remain, test_no_new_name_contains_a_dot, test_all_new_names_match_wire_pattern)
         + full `just check` green; legacy-ledger tests removed cleanly (no dangling import of legacy_to_new
         in tests/test_s13_10_tool_names.py line 26); docs no longer reference a non-existent `blackboard.query`
         tool; no skill/research-writer claim added; researcher profile untouched.

## 10. Anti-theater + READY gate
  - Symbols verified via preflight or marked NEW: yes (all file:symbol above read/grepped; blackboard_query.py NEW)
  - G# → CT#/S#/T# mapping: G1→CT1/CT2→S1→T1-4; G2→CT3/CT4→S2/S3→T5/T9/T10/T11; G3→S4→(grep doc check)
  - Signal contracts two-sided: CT2 producer(handler)/consumer(ToolResult) named
  - Kill-checks target producer: yes (blackboard.query call, registration, TOOL_NAMES membership, handler except)
  - Path matrix covered or explicit non-goal: P1-6 all have T#; M1-M5 covered (M3 = explicit N/A-why dead)
  - No vague verbs: all steps concrete; implementation constraints (lazy import, limit slicing, handler
    exception, registration seam) pinned in S1/S2/S3/CT1/CT3
  - READY gate: all Q# resolved (Q1 default recorded, Q2/Q3 RESOLVED). BLOCKED from READY only by the
    depth/scope decision on G3 doc edits (S4): whether the agent-facing doc alignment (AGENTS.md,
    llms.txt, reference.md) is in-scope for THIS slice or a separate doc slice. If the operator wants the
    tool-only slice first, status = READY for S1-S3/T1-T11 and S4 (docs) moved to a follow-up.

## 11. Artifacts inventory
  Artifact | Path | Action | Owner S#
  tool module | src/fa/inner_loop/tools/blackboard_query.py | add | S1
  profiles | src/fa/inner_loop/profiles.py | edit (builder in _build_tool_builders + PROFILES_RAW implementer/planner) | S2
  tools pkg | src/fa/inner_loop/tools/__init__.py | NO EDIT (registration via profiles only — avoids _register_extra_tools exact-set test) | S2
  canonical names | src/fa/inner_loop/tool_names.py | edit (direct canonical TOOL_NAMES frozenset incl. fs_blackboard_query; prune LEGACY_TO_NEW/legacy_to_new) | S3
  s13.10 test | tests/test_s13_10_tool_names.py | edit (fix import line 26; delete 2 legacy-ledger tests; keep 4 invariant tests) | S3
  docs | AGENTS.md, knowledge/llms.txt, knowledge/reference.md | edit (dot->tool name) | S4
  tests | tests/test_blackboard_query_tool.py | add | S5
