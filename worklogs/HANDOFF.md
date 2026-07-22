# HANDOFF.md — для следующего агента / сессии

> Сначала прочитать [`knowledge/llms.txt`](../knowledge/llms.txt) §MUST READ FIRST.
> Этот файл содержит актуальное состояние и следующий приоритет.

## §Current state

**As of:** 2026-07-21 — quality/guardrail closure session, base patch target
`db6fd884e38092e44254a1f33f6c259aa1297d2b`.

### Verified

- Full behavioral suite: **1826 passed, 13 skipped**.
- Full strict mypy: **PASS — 274 files**.
- Production/source Ruff: **PASS**.
- Repository Ruff: one intentional remaining diagnostic, N999 for the
  operator-facing filename `scripts/fa_host_layout_audit.py` was resolved by
  renaming the file and updating references; re-run after applying the patch.
- Producer/consumer, dependency-contract, authoring, and no-mocked-dataclasses
  checks: PASS.
- Coverage: **80.25%**, configured blocking gate remains **86%**.
- Meaningful coverage added for PTY, registry optional builders, subagents,
  blackboard authority/conflicts, and analytics.
- Production defects fixed during coverage work: subagent context fallback,
  worklog failure isolation, empty analytics schema, workspace containment
  result mapping.

### CI workflow intent

- `.github/workflows/advisory.yml` and
  `.github/workflows/authoring-guardrails.yml` run on every `push` and
  `pull_request`; no path filter.
- `Advisory CI/sanity-check` invokes `uv run just check`.
- `pip-audit`, `gitleaks`, and container smoke are represented in advisory CI.
- Semgrep and mutation are schedule/manual advisory workflows until governance
  promotes them.
- Local hooks remain convenience only; GitHub CI is authoritative.

### Artifacts prepared

- Russian live-server plan:
  [`knowledge/instructions/03-live-server-ci-governance-plan-ru.md`](../knowledge/instructions/03-live-server-ci-governance-plan-ru.md)
- Patch to apply on top of the requested base commit:
  `first-agent-quality-closure.patch`

## §Next

1. On a controlled live server, follow the Russian plan §1–§3: bootstrap,
   verify push/PR workflows, run Docker/security simulation, and preserve logs.
2. Verify the shipped harness path per plan §4, including session DB authority,
   structured events, PTY cleanup, containment, and secret isolation.
3. Verify GitHub governance manually per plan §5: required checks, Code Owner
   review, agent permissions, and maintainer emergency override.
4. Review the worktree and patch application per plan §6–§8. Do not commit or
   push until a human reviews the final diff.
5. Keep the 86% coverage gate blocking. Continue meaningful coverage expansion
   in a follow-up slice; do not lower the threshold in this patch.
6. Decide whether the renamed operator script requires a compatibility symlink
   or a release-note migration for external operators.

## Session close protocol

- Load `knowledge/skills/doc-maintenance/SKILL.md` at session close.
- Run `python scripts/check_doc_links.py`.
- After any operator-script rename, grep for the old filename stem and confirm
  no active references remain; ignored cache files do not count.
- Preserve the exact base SHA and patch SHA/size in the handoff.
