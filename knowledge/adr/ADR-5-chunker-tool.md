# ADR-5 — Chunker tool selection for v0.1

- **Status:** accepted
- **Date:** 2026-04-28
- **Deciders:** 0oi9z7m1z8 (project lead) + Agent session 2f45f66e

## Context

ADR-3 (Memory architecture variant for v0.1) chose **Variant A
(mechanical wiki)**: filesystem-canonical Markdown / YAML plus a
deterministic Python chunker plus SQLite FTS5. ADR-3 §Consequences
explicitly deferred the chunker tool choice to a follow-up
research note plus an ADR.

The research note
[`research/chunker-design.md`](../research/chunker-design.md)
closes that open question. It compares five tool classes
(naive fixed-window, heading-aware splitters, symbol extractors,
concrete-syntax-tree parsers, per-language regex) across the six
target languages from `project-overview.md` §4 (Markdown / plain
text, Python, Go, PowerShell `.ps1`, TypeScript / JavaScript,
YAML / TOML / JSON), and proposes a two-tool baseline.

This ADR locks that proposal in.

## Options considered

Same options as the research note §3 — Naive fixed-window,
heading-aware splitter (markdown-it-py / mistune), symbol
extractor (universal-ctags), CST parser (tree-sitter,
optionally via `tree-sitter-language-pack`), per-language regex
(sparks-style). Detailed comparison: research note §4-§6. Only the
viable shortlist for v0.1 is reproduced here.

### Option A — universal-ctags (code) + markdown-it-py (prose)

- Pros:
  - Native PowerShell support
    ([ctags-lang-powershell](https://docs.ctags.io/en/latest/man/ctags-lang-powershell.7.html),
    enum-label kind merged 2024-05); covers all 6 target languages.
  - Single C-binary for code + small Python lib for prose; ~1 MB
    Python wheel, ~6 MB system dependency.
  - Stable JSON output (`ctags --output-format=json`); no Python
    wrapper needed.
  - Loud failure modes (empty output / stderr) — easy to detect in
    unit tests.
  - `chunker_version` field in `meta` table is a single composite
    string; cache invalidation is straightforward
    (research note §6.4).
- Cons:
  - No intra-symbol splitting: a 500-line PowerShell function
    becomes one chunk. Mitigated by post-processing on `#region`
    boundaries plus blank-line splits — and re-evaluation is
    explicit (see Consequences).
  - PowerShell ctags support not yet end-to-end-tested on the
    user's actual 1500-line `.ps1` profile (research note §9
    OQ-2). Sample-test is a hard gate before the implementation
    PR (research note §8) — not before this ADR.

### Option B — tree-sitter-language-pack (everything)

- Pros: 305 grammars in one wheel, full CST so intra-symbol
  splitting is feasible, future-proof for code-graph (Variant C).
- Cons: ~50-100 MB wheel; CHUNKER_VERSION management harder
  because 305 grammars upgrade independently inside one pinned
  pip release; PowerShell grammar status fragmented across three
  upstream repos
  ([archived](https://github.com/PowerShell/tree-sitter-PowerShell),
  [airbus-cert active](https://github.com/airbus-cert/tree-sitter-powershell),
  [wharflab newer fork](https://github.com/wharflab/tree-sitter-powershell));
  Markdown grammar weaker than markdown-it-py on corner cases
  (research note §4.2).

### Option C — Per-language regex (sparks-style)

- Pros: zero deps, full control.
- Cons: sparks needed >3000 lines of pure-Python `extract.py` for
  6 languages — that is the floor, not the ceiling. Maintenance
  burden disproportionate to the value that ctags already delivers
  for free (research note §3.5, §4.5).

## Decision

We will use **Option A — universal-ctags for code,
markdown-it-py for prose**.

Concrete pipeline (research note §7.1, reproduced for ADR
self-containment):

1. **Markdown / plain text** (`*.md`, `*.txt`) — markdown-it-py
   AST → split by H1 / H2 (configurable depth) → slugify heading
   for `anchor`. Files under ~500 lines stay as one chunk.
2. **Source code** (`*.py`, `*.go`, `*.ps1`, `*.psm1`, `*.ts`,
   `*.tsx`, `*.js`, `*.jsx`) — `subprocess.run(["ctags",
   "--output-format=json", "--fields=+ne", ...])`, parse JSON,
   slice file by line range up to next top-level symbol. Special
   case for PowerShell: pre-split by `#region` / `#endregion`
   markers before passing to ctags.
3. **Config files** (`*.yaml`, `*.yml`, `*.toml`, `*.json`) — no
   chunking. One file = one chunk. `anchor = filename`.
4. **Catch-all** (everything else) — one file = one chunk.

Stable interface (research note §7.3 — same shape; copied here so
implementers do not have to chase two files):

```python
@dataclass(frozen=True)
class Chunk:
    path: str
    anchor: str
    lang: str
    body: str
    line_start: int
    line_end: int

class Chunker(Protocol):
    def chunk_file(self, path: pathlib.Path) -> list[Chunk]: ...
```

Implementation in v0.1 will be a `CompositeChunker` with
per-extension delegation. A future swap to `TreeSitterChunker`
must not change the interface.

**Out of scope for v0.1** (explicit non-goals):

- tree-sitter in any form (re-evaluation triggers below).
- Per-language regex beyond what ctags already provides.
- Embeddings, vector stores, code-graph (per ADR-3).

## Consequences

- **Positive.**
  - One small dependency surface
    (`apt install universal-ctags` plus
    `pip install markdown-it-py`); educational forks of this repo
    bootstrap fast.
  - PowerShell, Python, Go, TypeScript / JavaScript, JSON, YAML
    are all covered without per-language code.
  - Failure modes are loud (ctags writes stderr; markdown-it-py
    raises). Easy to monitor.
  - `CHUNKER_VERSION` (composite string of ctags version plus
    markdown-it-py version plus our internal split-algorithm
    revision) lives in the `meta` table per
    [ADR-4](./ADR-4-storage-backend.md) §Cache Invalidation. One
    concept, two writers.
- **Negative.**
  - 500-line+ symbols become single chunks. UC1 retrieval can
    push more tokens into context than ideal. Re-evaluation
    trigger below.
  - PowerShell ctags coverage is "expected production-ready" but
    has **not** been verified on the user's own 1500-line `.ps1`
    profile. The implementation PR must include this test
    (research note §8, item 1).
  - Versioning discipline is on us: every change to the chunker
    code or its dependencies must bump `CHUNKER_VERSION`,
    otherwise the `meta`-vs-`chunks` consistency invariant breaks
    silently. Mitigation: a one-line invariant test in CI once
    Phase S scaffolding lands.
- **Re-evaluation triggers** (when to revisit this ADR).
  - Symbol-chunks > 2 K tokens degrade UC1 LLM-context behaviour
    on > 5 % of queries. Action: introduce intra-symbol split via
    tree-sitter for the offending language only (not a wholesale
    swap).
  - Sample-test (research note §8, item 1) shows ctags loses
    > 10 % of top-level functions on the user's `.ps1`. Action:
    fall back to airbus-cert tree-sitter-powershell for that one
    language.
  - We decide to ship code-graph (Variant C). Action: re-open as
    a new ADR; adopt tree-sitter wholesale.
- **Follow-up work this unlocks.**
  - **Phase S scaffolding** (`pyproject.toml`, ruff, mypy, pytest,
    pre-commit, CI, Makefile) can now name both runtime
    dependencies in `pyproject.toml`.
  - **Implementation PR** (`src/fa/chunker/`) gated by the four
    sample-tests in research note §8. Sample-test is a gate on
    that PR, not on this ADR.
  - Open questions OQ-3, OQ-9, OQ-10 in the research note are
    deferred to implementation time — defaults are good enough
    until then.

## Amendments

### Amendment 2026-04-29 — Chunk dataclass extension for doc-level metadata

**Source.** Cross-reference review
[`research/cross-reference-ampcode-sliders-to-adr-2026-04.md`](../research/cross-reference-ampcode-sliders-to-adr-2026-04.md)
§7.2 (Gap-6) and §10 R-5. SLIDERS contextualized chunking
(`m_G` / `m_L` per-document metadata, see SLIDERS §3.1) needs
the chunker to emit doc-level title and section breadcrumb on
each chunk. The current `Chunk` dataclass exposes only
`anchor` (last heading slug) and `path`. Adding
`parent_title` / `breadcrumb` / `byte_start` / `byte_end` now
is **additive** — the existing fields stay; the `Chunker`
Protocol signature is unchanged; downstream consumers that
ignore the new fields continue to work.

**Decision.** The `Chunk` dataclass for v0.1 gains five fields
(four mandatory + one optional):

```python
@dataclass(frozen=True)
class Chunk:
    path: str
    anchor: str
    parent_title: str            # H1 / frontmatter title / filename
    breadcrumb: tuple[str, ...]  # section-heading path; () for code or single-chunk files
    lang: str
    body: str
    line_start: int
    line_end: int
    byte_start: int              # 0-based, inclusive
    byte_end: int                # 0-based, exclusive
    topic: str | None = None     # frontmatter `topic:`; None if absent
```

**Per-extension semantics.**

- **Markdown / plain text** — `parent_title` is the frontmatter
  `title:` if present, else the first H1 (slugged is the
  `anchor`, raw text is `parent_title`), else the filename
  stem. `breadcrumb` is the tuple of ancestor headings up to
  but not including the chunk's own anchor (e.g. for `# README
  → ## Setup → ### Linux` chunk, breadcrumb is `("README",
  "Setup")`).
- **Source code** — `parent_title` is the filename (basename,
  no path). `breadcrumb` is `()` (PowerShell `#region` markers
  are not breadcrumb-bearing in v0.1; they only drive splitting
  per ADR §Decision step 2).
- **Config files** — `parent_title` is the filename;
  `breadcrumb` is `()`.
- **Catch-all** — same as config files.

**`byte_start` / `byte_end`** reference the canonical on-disk
file in its declared encoding (UTF-8 default). For Markdown
chunks the bytes cover the heading line through the last byte
of the chunk's body; for symbol chunks, the symbol's full
extent including any leading docstring or decorator block
captured by ctags. The byte offsets are advisory for v0.1
retrieval; they exist for v0.2 SLIDERS-style extraction (see
ADR-4 amendment 2026-04-29 §Notes).

**Compatibility.** The `Chunker` Protocol signature is
unchanged (still `chunk_file(path) -> list[Chunk]`). Code that
reads only the original six fields continues to compile.
`CHUNKER_VERSION` (per §Consequences) bumps because the
emission shape changes — invalidates the SQLite cache once
and only once.

**Topic propagation.** When the source file has frontmatter
with a `topic:` key (see frontmatter amendment in
[`knowledge/README.md`](../README.md)), the chunker copies the
value into every `Chunk.topic` produced from that file.
Source files without frontmatter (e.g. `.py`, `.ps1`) emit
`topic=None`. v0.1 retrieval ignores the field; it exists so
that v0.2 SLIDERS-style extraction can amortize schema
induction per topic without re-chunking.

**Out of scope for this amendment.**

- Per-symbol intra-symbol splitting — still gated by the
  re-evaluation triggers above.
- Topic auto-detection from corpus structure (path heuristics,
  embedding clustering) — v0.2 follow-up. v0.1 only honours
  the explicit frontmatter key.

## References

- Research note: [`research/chunker-design.md`](../research/chunker-design.md) — full comparison + open questions + sample-test plan.
- ADR-3: [`ADR-3-memory-architecture-variant.md`](./ADR-3-memory-architecture-variant.md) — Variant A frame.
- ADR-4: [`ADR-4-storage-backend.md`](./ADR-4-storage-backend.md) — `chunks` schema (incl. 2026-04-29 amendment) and `CHUNKER_VERSION` cache contract.
- [`research/cross-reference-ampcode-sliders-to-adr-2026-04.md`](../research/cross-reference-ampcode-sliders-to-adr-2026-04.md) §7.2 / §10 R-5 — rationale for the 2026-04-29 amendment.
- [`research/sliders-structured-reasoning-2026-04.md`](../research/sliders-structured-reasoning-2026-04.md) §3.1 — `m_G` / `m_L` chunking metadata.
- universal-ctags: <https://github.com/universal-ctags/ctags> ·
  <https://docs.ctags.io/>.
- markdown-it-py: <https://github.com/executablebooks/markdown-it-py>.
- tree-sitter-language-pack (rejected): <https://pypi.org/project/tree-sitter-language-pack/>.
