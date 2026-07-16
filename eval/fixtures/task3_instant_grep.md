---
task_id: instant-grep-auth
role: researcher
scoring_kind: exact
expected: "instant_grep 'auth' finds Authentication substring in <50ms"
---

# Task: Instant grep auth

## Goal
fs.instant_grep "auth" should find "Authentication" substring via FTS5 trigram <50ms, returns paths not content

## Acceptance
- instant_grep "auth" → ["AuthMiddleware", "Authentication"] <50ms (0.1ms)
- Index incremental, stale cleanup, excludes sessions/ and .fa/
- FTS5 trigram tokenize, fallback porter WARNING

## Metrics
- latency_ms <50
- artifact trail: which files read
