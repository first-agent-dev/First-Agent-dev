---
task_id: instant-grep-auth
role: researcher
scoring_kind: exact
expected: "fs_search 'auth' (output_mode=files) finds Authentication substring via BM25+trigram <50ms after first-call index"
---

# Task: Search for auth references (S14b.1 fs_search)

## Goal
fs_search "auth" (output_mode="files") should find files containing "Authentication"
via FTS5 BM25+trigram <50ms (after the first-call lazy index), returning paths with
match_count and a short first-match snippet.

## Acceptance
- fs_search query="auth" output_mode="files" → returns files including any that
  contain "AuthMiddleware" or "Authentication" (trigram catches partial identifiers
  split by the unicode61 tokenizer; BM25 provides ranked ordering).
- Index is lazy on first call, mtime/size-incremental thereafter, stale cleanup,
  prunes sessions/, node_modules/, .fa/, etc.
- BM25 tokenizer splits snake_case and camelCase so "auth_middleware" and
  "AuthMiddleware" both match the token "auth".
- Fail-degraded: any FTS error falls back to a streaming Python walk.

## Metrics
- latency_ms <50 on second call (cached index)
- artifact trail: which files surfaced
