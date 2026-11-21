# Q-V2-ACC-R1 / Q-V2-ACC-R6 — who may attest, and against what (source audit, 2026-11-20)

**Status: SOURCE AUDIT + recommendation. No code change in this note.** The operator asked for R1 and R6
to be decided "through a source audit, through the prism of our values", and fixed **R5 = 30 days**.
Every claim below is grounded in the checkout at `6ceb27a` (the commit that landed R2).

Operator answers that shape this note:

| Question | Answer |
| :--- | :--- |
| R5 — maximum age of a disposition | **30 days** (chosen option `d30`) |
| R1 — how ratification becomes external | *decide by source audit, through our values* |
| R6 — what `doc:<path>@<sha256>` resolves against | *must satisfy system behaviour and stay flexible enough that the agent works confidently and precisely* |

## 0. Values this audit measures the options against

1. **Verdict strength ≤ evidence strength** (E575/E576): a claim may never be reported stronger than what
   actually backs it.
2. **The model returns semantics; authority is caller input.** Ratified in E575 for slugs ("letting the model
   restate it would make the slug a model claim rather than an operator input",
   `workflow_controller.py:2557-2559`) and applied to R2 for evidence.
3. **Silence is the failure mode.** A planner that may not express an un-testable claim will *omit* it —
   producing exactly the false confidence R2 exists to kill — or invent a test it cannot honestly write.
4. **Strength comes from bytes, not from directories.** A digest pins evidence; a path prefix does not.
5. **Closed vocabularies, no free text** (`plan_v2.py:48-56`, `admission_schema.py` rule sets).
6. **Purity of the grammar.** `parse_plan` is a pure function of two documents; anything needing I/O or a
   clock must live outside it.

## 1. Verified facts

| Fact | Source |
| :--- | :--- |
| `parse_plan` is pure: `(roadmap, increment) -> PlanGraph`, no port, no clock, no filesystem. | `plan_v2.py:637`; callers `plan_admission.py:221`, `workflow_controller.py:2820` |
| **No ratification channel exists.** No code reads an operator ratification: `ratif` appears only in docstrings, a comment and one rule name. | grep over `src/` → `plan_v2.py:9,55,309` only |
| **No human gate exists in a run.** The only "approval" objects are a write-approval guard middleware and a telemetry field that is always `None`. | `hooks/builtin.py:178-190`; `state.py:902 human_approval=None` |
| **The initial plan does not exist before the run.** The V2 body is a *proposal* validated in-memory before install; the run has no chance to consult an operator after seeing it. | `workflow_controller.py:2813-2832` |
| Caller authority enters through **closed tool parameters**, validated in `_prepare_invocation`; the schema forbids extras. | `workflow_tool.py:200-246` (`additionalProperties: False`), `:738-766` |
| The precedent for "one thing the caller may decide" is explicit and argues G1 in advance. | `workflow_controller.py:2550-2564` |
| Today the *planner* writes `DISPOSITION-OWNER`, and the only check is membership in a two-value set — so a waiver costs the model one token. | `plan_v2.py:296-300` (`_field(... "DISPOSITION-OWNER" ...)`, `DISPOSITION_OWNERS = {"W4","operator"}`) |
| Resolving evidence needs I/O, and the only in-run read port is the substrate port used for the existing re-admission path. | `workflow_controller.py:2935` (`substrate.port.read_file`) |
| The acceptance closure is the **execution oracle**: `acceptance/` only, inventory + digests. A readiness sheet inside it would become executable input. | `acceptance_bundle.py` `_collect`/`_require_sealed_root`; `acceptance_closure.collect_acceptance_closure` |
| The v2 project tree (D-V2-7) is roadmap + ledger + open-questions + `increments/` + `acceptance/`: **no docs home**. Operator artefacts in this repo live in `worklogs/<slug>/notes|reviews|research|implementation-plans/` and the repo-wide `knowledge/` base. | `find worklogs -name "q-v2-*"` → three notes; `ls knowledge` |
| Install creates `worklogs/<slug>/` (no-clobber), so for I01 the tree does not exist when the caller declares anything. | `workspace.py:3638+`, `_install_prepare` |

## 2. R1 — the three options against those facts

| Option | Closes G1? | Implementable for I01 (no human gate)? | Other consequences |
| :--- | :--- | :--- | :--- |
| **(a) plan keeps the triple as a claim; admission compares it to a ratified record** | partially — the model still writes the owner, and the comparison legitimises it | **No.** Ratifying requires the invariant ids, which exist only inside the run (fact 4). The operator would ratify a plan they have not seen | Keeps `DISPOSITION-EVIDENCE` as model-authored text; G2 resolution lands on model prose. Biggest diff: comparison rules across three fields, plus the record format, plus still needing option (b)'s channel to get the record in |
| **(b) the plan *requests* by reason; the caller declaration supplies owner, evidence, reviewed-at** | **yes** — owner/evidence are never in the plan text, so nothing the model writes can authorise itself | **Yes.** The reason is the only thing that must be known before the plan exists, and the reason is semantics (the planner is the one that knows *why* it cannot test the claim) | One new closed tool parameter (`dispositions`), same shape as `project_slug`. `parse_plan` stays pure. R5/R6/R2 attach to the declaration: `reviewed_at` for the age, typed evidence for the resolution, `attested` in the seal already reports the result. Reverses B-narrow's *field placement* only: closed reasons, cap 16, no free text all stay |
| **(c) refuse every disposition in the initial plan** | yes, trivially | Yes, zero new surface | Forces the planner to omit an un-testable claim (silence, value 3) or fake a test (dishonest evidence). Strands the ratified reason vocabulary and leaves R2's `attested` permanently empty. Buys nothing that R2 does not already disclose |

**Recommendation: (b).** It is the only option that is both implementable for a bootstrap whose plan is authored
inside the run and consistent with value 2 — the same argument that decided `project_slug` in E575. It also
closes G1 *structurally* rather than by comparison: there is no owner field in the plan to compare, so no rule
can be softened later.

Shape (b) implies:

```text
plan (planner, semantics)                      declaration (caller, authority)
### INV-2                                      dispositions: [
KIND: HARD                                       {reason: HOST_READINESS,
TEXT: Host readiness is proven on the host.       owner: W4,
EVIDENCE: NON_EXECUTABLE                          evidence: "doc:worklogs/demo/notes/readiness.md@sha256:…",
DISPOSITION-REASON: HOST_READINESS                reviewed_at: "2026-11-19"}
                                                ]
```

Admission binds them: every `NON_EXECUTABLE` invariant must name a **declared** reason
(`disposition-undeclared`), the owner/evidence/reviewed-at are **copied** from the declaration, the age is
checked against 30 days (`disposition-review-stale`), and the evidence ref is resolved (R6). `DISPOSITION-OWNER`
or `DISPOSITION-EVIDENCE` in plan text is refused as `disposition-not-caller-authority` — a *stronger* rule than
today's membership check, and the one rule that makes G1 unrepresentable.

## 3. R6 — what `doc:<path>@<sha256>` resolves against

| Root | Verdict |
| :--- | :--- |
| The sealed project tree only (`worklogs/<slug>/acceptance/…`) | **Impossible** for I01 (the tree does not exist yet, fact 10) and **wrong by design**: the closure is executed, so evidence would become code |
| The project tree (`worklogs/<slug>/…`), non-closure | Works for later revisions, dead for I01, and the v2 tree has no docs home (fact 9) — it would force a copy step into a directory whose shape D-V2-7 just fixed |
| **Any workspace-relative regular file** | Works for I01 and every later revision; the digest is what pins the claim; the repo's own evidence already lives in `worklogs/<slug>/notes|reviews|research` and `knowledge/` |

**Recommendation:** resolve `doc:` against the workspace, with a `doc:` reference being
`doc:<workspace-relative path>@sha256:<64 hex>`; at admission the harness requires the file to exist, be a
regular file, be inside the workspace with no `..`/absolute/dot-leading part, avoid the install deny set
(`.git`, `.fa`, `.venv`, `.env`, `bundles`), and match the digest byte for byte. Refusals are closed:
`disposition-evidence-missing`, `disposition-evidence-mismatch`, `disposition-evidence-invalid`.
`issue:<KEY>` and `review:<id>` are validated syntactically and stay attested-with-reference (no network
resolution exists — egress is not part of this system; claiming to have verified a GitHub issue would itself be
false confidence).

Why this stays *precise* even though the root is broad: the caller cannot point at a file that does not exist,
cannot pin bytes it has not read, and cannot retarget it later without minting a new declaration — which is
exactly the "reviewed, then pinned" property. A root allowlist would add a fifth failure mode (legitimate
evidence living somewhere else) without adding any strength.

## 4. R5 — 30 days (operator decision)

`reviewed_at` becomes a required field of the declaration, an ISO-8601 date. Admission refuses a disposition
whose age exceeds **30 days** measured against the run clock (UTC), rule `disposition-review-stale`, not
retryable without a fresh declaration. A future date is refused as `disposition-review-invalid`. The constant
lives next to the reason set in `plan_v2.py` (`MAX_DISPOSITION_AGE_DAYS = 30`) so the grammar's vocabulary and its
lifetime stay in one file.

## 5. Implementation plan (dependency order, each step verified)

| Step | Change | Verification |
| :--- | :--- | :--- |
| S1 | Grammar: `DISPOSITION-REASON` stays; `DISPOSITION-OWNER`/`DISPOSITION-EVIDENCE` become `disposition-not-caller-authority`; `Invariant` keeps `reason`, drops the model-authored owner/evidence | existing B-narrow tests updated; mutants on the new refusal |
| S2 | Tool schema + `_prepare_invocation`: `dispositions` array (≤16, closed reason set, owner ∈ {W4, operator}, typed evidence, `reviewed_at`) | quadrant tests through the real handler |
| S3 | `DispositionDeclaration` type + binding at admission: undeclared reason, stale review, invalid/missing evidence; owner/evidence copied onto the graph's invariants for the run | unit + admission-diagnostic tests |
| S4 | `doc:` resolution through the substrate port at admission; `attested_contracts` (R2) unchanged and still the only coverage claim | resolution tests incl. digest mismatch, `..`, missing file |
| S5 | Prompt: the planner is told reason-only, told the closed list, and told it may not name an owner | prompt snapshot test |

**Open sub-question flagged, not decided here:** whether the binding is recorded in the admission attempt, the
run state, or only in diagnostics. The admission schema cannot hold a WARN on an admitted attempt (E576 §R2), so
the likely answer is "diagnostics on refusal, seal `attested` on success, ledger line for the audit trail". That
choice is small, reversible and does not block S1–S2.
