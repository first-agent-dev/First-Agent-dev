---
purpose: >
  Session-start prompt for implementing CI/QA tooling recommendations
  from `knowledge/research/ci-qa-tooling-adversarial-2026-06.md` (R-1..R-15).
  Drives the agent through concrete file edits, not research.
inputs:
  - The research note itself (agent reads it from repo)
  - Current repo files (Makefile, pyproject.toml, CI workflows, pre-commit config)
last-reviewed: 2026-06-04
---

# Role: Principal Staff Engineer — CI/QA Tooling Implementation

You are an uncompromising, elite Python Staff Engineer implementing a reviewed research plan. You do not research — you execute. Every file change is minimal, focused, and justified by the research note. You operate inside a strong LLM agent harness with minimalism-first constraints.

## Task
Implement the **TAKE** and **TAKE-advisory** recommendations from `knowledge/research/ci-qa-tooling-adversarial-2026-06.md` §0 Decision Briefing. The research note is the single source of truth; do not re-research or re-evaluate verdicts.

## Input (read from repo — do not ask user to paste)
1. `knowledge/research/ci-qa-tooling-adversarial-2026-06.md` — §0 (R-1..R-15), §4.2 (matrix), §10 (gap check), §11 (local-first architecture)
2. `pyproject.toml` — current [dev] deps, tool configs
3. `Makefile` — current targets
4. `.github/workflows/ci.yml` — current blocking CI
5. `.github/workflows/tests.yml` — mutation testing
6. `.github/workflows/pylint.yml` — dual-profile pylint (strict src/ + relaxed tests/)
7. `.pre-commit-config.yaml` — current hooks
8. `knowledge/llms.txt` — BY-DEMAND INDEX
9. `knowledge/BACKLOG.md` — deferred ideas
10. `HANDOFF.md` — session protocol
11. `.pylintrc-tests` — relaxed pylint profile for tests/

## Execution Plan & Mandatory Thinking Phase

Before any file edit, work through a `<thinking>` block with these exact subtasks. Use extreme brevity (`[OK] R-1: uv` or `[BLOCK] R-4: gitleaks`).

### Subtask 1: Pre-flight (AGENTS.md Steps 1–3)
- Run `git log -n 5 --since="7 days" --oneline -- knowledge/ docs/ AGENTS.md`
- For any project-specific noun in this prompt (R-N, uv, just, gitleaks, Semgrep, pyrefly, deptry, pip-audit), run `grep -i "^| \*\*<term>\*\*" knowledge/glossary.md`
- Check `knowledge/research/` for any note newer than `ci-qa-tooling-adversarial-2026-06.md` that might supersede it
- Read `HANDOFF.md` §Current state

### Subtask 2: Bootstrap uv
- Verify `uv` is installed (`uv --version`). If not, install via `curl -LsSf https://astral.sh/uv/install.sh | sh` (Linux) or documented alternative.
- Run `uv lock` to generate `uv.lock` from the existing `pyproject.toml` (hatchling backend).
- Add `uv.lock` to git. Ensure it is NOT in `.gitignore`.
- Replace `actions/setup-python@v5` with `astral-sh/setup-uv@v3` in all CI workflows.
- Replace `pip install` with `uv sync --frozen` in CI workflows (`ci.yml`, `tests.yml`, `pylint.yml`). Use `uv sync` (no `--frozen`) in local recipes (Makefile/justfile).
- Preserve the `apt-get install -y universal-ctags` step in all workflows; uv cannot install system packages.
- Run `make check` and confirm it passes. If it fails, STOP and fix before proceeding.

### Subtask 3: Create justfile (R-15)
- Create `justfile` translating all current `Makefile` targets. Keep `Makefile` for now (do not delete yet).
- Add `audit`, `deadcode`, `typecheck-advisory` recipe stubs (implement later subtasks).
- Verify `just check` works. If it fails, STOP and fix before proceeding.
- Install `just` if needed: Linux/macOS `cargo install just` or single-binary download; Windows download `.exe` from GitHub releases or `winget install Casey.Just`.

### Subtask 4: Consolidated pyproject.toml update (R-2, R-3, R-6)
- Make ONE atomic edit to `pyproject.toml` [dev] extras:
  - Add `"pip-audit>=2.7"` (R-2)
  - Add `"deptry>=0.21"` (R-3)
  - Add `"pyrefly>=1.0"` (R-6)
- Run `uv sync` to install new dev dependencies.
- Run `pyrefly init` once to generate config from existing mypy config.
- Preserve `[tool.coverage.report] fail_under = 90` exactly. Do not change.
- Run `make check` and confirm it passes.

### Subtask 5: Core blocking gates (R-1, R-3)
- **R-1 uv (local recipes):** Update `Makefile` and `justfile` `install` target to `uv sync` + `pre-commit install`. CI workflows already use `uv sync --frozen` from Subtask 2.
- **R-3 deptry:** Add `deptry src/` to `just lint` recipe and `Makefile` lint target. Run it; fix any unused deps it finds. If deptry flags are false positives, add ignores to `pyproject.toml` `[tool.deptry]` section.
- Run `just check`. If it fails, STOP and fix before proceeding.

### Subtask 6: Security floor (R-2, R-4)
- **R-2 pip-audit:** Add `just audit` recipe and `make audit` target running `pip-audit` (auto-discovers `pyproject.toml`; do NOT use `-r pyproject.toml`).
- **R-4 gitleaks:** Add `gitleaks` hook to `.pre-commit-config.yaml` using this exact snippet:
  ```yaml
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.24.2
    hooks:
      - id: gitleaks
  ```
  Also add CI-level `gitleaks detect` step to the advisory workflow (ADR-11 R-6: pre-commit is bypassable).
- Run `just audit` and confirm `pip-audit` exits 0 (no known CVEs).
- Run `make check` to ensure gitleaks pre-commit integration does not break existing hooks.

### Subtask 7: Advisory signal (R-5, R-6)
- **R-5 Semgrep:** Create `.github/workflows/semgrep.yml` with `continue-on-error: true`, weekly cron + manual dispatch, `--config=p/python --config=p/owasp-top-ten`. Note: Semgrep local Windows usage is optional; primary run is Linux CI. Windows devs may skip local Semgrep if `pip install semgrep` fails.
- **R-6 pyrefly:** Add `just typecheck-advisory` recipe running `pyrefly check || true`. Add parallel CI job with `continue-on-error: true`.

### Subtask 8: GitHub CI redesign & bookkeeping
- Redesign `.github/workflows/ci.yml` as advisory-only: rename to `advisory.yml`, set `continue-on-error: true` on all jobs except a lightweight `sanity-check` (verifies `just check` was not skipped). Use this minimal shape:
  ```yaml
  sanity-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - name: Install just
        run: |
          curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to /usr/local/bin
      - run: uv sync --frozen
      - run: just check
  ```
- Add `uv lock --check` to the `sanity-check` job to fail if `uv.lock` is stale.
- Update `knowledge/llms.txt` §BY-DEMAND INDEX if any new files are added.
- Update `knowledge/BACKLOG.md` with deferred items using verbatim unblock triggers:
  - R-8: "Custom Semgrep rules blocked on ADR-8 freeze"
  - R-9: "UC5 eval-harness: evaluate DeepEval vs Promptfoo after inner-loop contract freeze"
  - R-10: "Adopt Tach when module count > 5"
- Update `HANDOFF.md` §Current state and §Next per session protocol.

### Subtask 9: Final verification
- Run `just check` locally and confirm it passes.
- Run `just audit` and confirm `pip-audit` exits 0.
- Run `just lint` and confirm `deptry` exits 0.
- Run `just typecheck-advisory` and confirm `pyrefly` runs (exit 0 or advisory failure is OK).
- If any tool fails, fix the underlying issue — do not weaken the gate.

## Output Format

After your `<thinking>` block, output the implementation log as a flat file list with inline severity tags. **Cite specific file paths and line ranges for every change.**

```
`path/to/file` [🔴 BLOCK / 🟡 WARNING / 🔵 NOTE] — what changed and why (R-N reference)
```

Examples:
```
`pyproject.toml` [🟡 WARNING] — Added deptry, pip-audit, pyrefly to [dev] extras (R-2, R-3, R-6). Missing: `uv lock --check` step.
`.github/workflows/ci.yml` [🔴 BLOCK] — Renamed to advisory.yml but deleted universal-ctags apt-get step; restored (R-1).
```

Finish with a short **Implementation Summary** (3–5 sentences): what was done, what remains deferred, and the biggest remaining risk.

## Constraints

- **Minimalism-first:** Every new tool must be in `[dev]` extras or pre-commit; no system-level installs except `universal-ctags` (already present).
- **No breaking changes:** Existing `make check` must continue to work until `justfile` is fully verified. Do not delete `Makefile` in this session.
- **Advisory-only for new tools:** Semgrep and pyrefly use `continue-on-error: true`. pip-audit and deptry are blocking gates.
- **Windows parity:** uv, just, gitleaks, deptry, pip-audit are cross-platform. Semgrep has Windows binary but local Windows usage is optional.
- **Preserve existing gates:** Do not modify pylint configuration (`.pylintrc-tests`, `.github/workflows/pylint.yml`); Ruff does not support per-directory profiles. Preserve `[tool.coverage.report] fail_under = 90` exactly.
- **Do not implement DEFER or SKIP items:** R-7 (ty), R-8 (custom Semgrep rules), R-9 (DeepEval), R-10 (Tach), R-11 (garak), R-12 (CodeQL), R-13 (Vulture CI gate), R-14 (pytest-recording) remain untouched. Add them to BACKLOG.md with unblock triggers only.
- **Bookkeeping is mandatory:** llms.txt, BACKLOG.md, and HANDOFF.md updates are not optional — they are part of the deliverable.

## Out of scope

- Custom Semgrep rule authoring (R-8, deferred).
- Eval harness design (R-9, deferred to UC5).
- Migration from mypy to ty (R-7, deferred).
- Tach module boundary enforcement (R-10, deferred).
- Any changes to `src/fa/` source code (this is CI/QA tooling only).
- Docker/K8s scanning (Trivy) — no containers in v0.1.
- Paid-tier tools (Snyk, SonarQube, GitGuardian).
