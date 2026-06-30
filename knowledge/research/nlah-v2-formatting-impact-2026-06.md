---
title: "NLAH v2 + Prompt Formatting Impact — research note"
source:
  - "https://arxiv.org/html/2603.25723v2 (Tsinghua NLAH v2, May 2026)"
  - "https://arxiv.org/abs/2411.10541 (Does Prompt Formatting Have Any Impact on LLM Performance?, Nov 2024)"
  - "https://arxiv.org/abs/2501.15000 (MDEval: Markdown Awareness benchmark, Jan 2025, WWW'25)"
  - "https://arxiv.org/abs/2602.06384 (FMBench: Adaptive LLM Output Formatting, Feb 2026)"
  - "https://research.chroma.dev/context-rot (Context Rot, Chroma Research, Jul 2025)"
  - "https://tianpan.co/blog/2026-05-07-context-format-decision-agent-reasoning-json-markdown-plain-text"
  - "https://tenacity.io/snippets/supercharge-ai-prompts-with-markdown-for-better-results/"
  - "https://arize.com/blog/llm-instruction-following-benchmark-2026/ (Arize instruction-following, May 2026)"
  - "https://news.ycombinator.com/item?id=45458455 (HN table format benchmark, Oct 2025)"
  - "https://checksum.ai/blog/does-output-format-actually-matter (Checksum format experiment, Dec 2025)"
compiled: "2026-06-27"
goal_lens: "Does formatting (Markdown, JSON, YAML, HTML, plain text) help or hurt LLM agents in modern harnesses? What does the NLAH v2 paper add to this question?"
tier: stable
topic: "prompt-formatting, nlah, context-engineering, harness-engineering"
---

## 0. Executive Summary

**Question:** Do LLM agents in modern harnesses benefit from Markdown/structured
formatting, or would plain text save tokens and improve accuracy?

**Answer:** *It depends on the model, the task, and the role of the text.*
The evidence splits into three clear findings:

1. **For harness policy (AGENTS.md, system prompts, NLAHs):** Markdown
   structure **helps** — it provides hierarchy, section boundaries, and
   scannable gates. The NLAH v2 paper shows that 2.9k tokens of structured
   NL policy matches or exceeds 60.1k tokens of code (§1 below).
   Token savings are 10–20× while preserving task performance.

2. **For data fed into context (tool results, file contents):** Format
   matters hugely (up to 40% accuracy swing) but **there is no universal
   winner**. Markdown wins for GPT-4+, JSON wins for GPT-3.5, CSV wins
   for tabular data across most models (§2 below). The right default is
   Markdown for prose/instructions, CSV/Markdown-table for tabular data.

3. **For raw token volume:** More tokens ≠ better. Context Rot (Chroma
   2025) shows performance degrades 13–50% well before the context limit.
   Counterintuitively, *coherent structured* input can hurt attention
   *more* than shuffled input. This means concise, well-structured
   Markdown that **saves tokens** is doubly beneficial: it improves both
   comprehension and accuracy (§3 below).

**Bottom line for First-Agent:** Use Markdown for system prompts, AGENTS.md,
and NLAHs. Use Markdown tables or CSV for tool results with tabular data.
Strip HTML to Markdown before injecting into context. Keep total context
as short as possible — every saved token helps accuracy, not just cost.


## 1. NLAH v2: Natural-Language Harness Policy Works

### 1.1 What changed from v1 to v2

The Tsinghua NLAH paper (`arXiv:2603.25723`) was updated to v2 on 2026-05-18.
The core claim is unchanged: agent harness policy — the logic controlling
roles, state, validation, recovery, and stopping — can be expressed as
compact natural-language documents (NLAHs) and executed by a shared runtime
(IHR), achieving performance comparable to hand-coded harnesses.

Key v2 numbers (Table 1 from paper):

| Benchmark | Code Harness | NLAH | Prompted NLAH |
|---|---|---|---|
| SWE-bench Verified | 67.0% | **73.0%** | 77.0% |
| Terminal-Bench 2.0 (MHTBA) | 36.0% | **53.9%** | 57.3% |
| OSWorld (SeeAct) | **47.1%** | 46.3% | 47.9% |

Interpretation: NLAHs match or exceed code harnesses on 2/3 benchmarks.
On TB2, both NL variants dramatically outperform code (36→54/57) because
the code harness was over-specialized for one model.

### 1.2 The formatting finding: policy compression

Table 2 from the paper (static harness materials):

| Harness | Code tokens | NLAH tokens | Code files | NLAH files |
|---|---|---|---|---|
| Live-SWE | 60,100 | **2,900** | 68 | 3 |
| MHTBA | 10,500 | **800** | 3 | 1 |
| SeeAct | 47,500 | **1,400** | 5 | 1 |

**20× compression** of harness policy from code to structured NL.
This is the strongest argument for Markdown-structured harness documents:
they preserve the *information density* that matters (stages, gates,
evidence rules) while stripping implementation noise (tool adapters,
parsers, retry logic, sandboxing).

### 1.3 Module ablation: what helps

Table 5 (RQ3) — each row adds one module to a "Basic" condition:

| Module | SWE Δ | OSWorld Δ | Verdict |
|---|---|---|---|
| File-backed state | **+2.6** | **+13.9** | Helps everywhere |
| Self-evolution | **+5.8** | **+8.4** | Strongest single module |
| Evidence-backed answering | **+2.8** | **+2.8** | Consistent small gain |
| Verifier | +0.2 | +8.4 | Task-dependent |
| Multi-candidate search | **−1.6** | +2.8 | Expensive, mixed results |
| Context compression | **−1.0** | **−8.3** | **Hurts** — summarization drifts from evaluator |
| Markdown memory | **−2.8** | +5.6 | Mixed — task-dependent |

**Key takeaway:** Modules that *tighten acceptance discipline* (state,
evidence, self-evolution) help. Modules that *add process layers* without
aligning to the evaluator (compression, extra branching) hurt or are
neutral. Context compression — summarizing intermediate work — actively
degrades performance on SWE-bench and severely on OSWorld.

### 1.4 Handoff loss is the main weakness

Tables 3–4 show that Information Handoff Recall drops to 0.32 (SWE) and
0.55 (TB2) under parent-child execution, versus 1.0 in single-context
prompting. Multi-agent handoff *loses information*. This is directly
relevant to First-Agent's planner→coder→eval chain.


## 2. Formatting Impact: The Evidence Base

### 2.1 The foundational study (arXiv:2411.10541, Nov 2024)

"Does Prompt Formatting Have Any Impact on LLM Performance?" tested
plain text, Markdown, JSON, and YAML across GPT-3.5 and GPT-4 on
MMLU, HumanEval, NER, and code translation tasks.

Key findings (statistically significant, p<0.001):

| Task | GPT-3.5 Best | GPT-3.5 Worst | GPT-4 Best | GPT-4 Worst |
|---|---|---|---|---|
| MMLU | JSON (59.7) | MD (50.0) | MD (81.2) | JSON (73.9) |
| HumanEval | JSON (59.8) | Plain (40.2) | MD (86.6) | Plain (82.9) |
| Code translation | JSON (78.4) | Plain (66.5) | MD (77.0) | Plain (68.2) |

**Model-dependent:** GPT-3.5 prefers JSON; GPT-4+ prefers Markdown.
Accuracy swings of **20–40%** from format alone, identical content.

Likely explanation: training data distribution. GPT-4+ trained on more
GitHub Markdown, documentation, and Stack Overflow. JSON training data
dominated in GPT-3.5's training mix.

### 2.2 MDEval benchmark (WWW'25, Jan 2025)

"Markdown Awareness" formalized as a measurable LLM property.
20K instances, 10 subjects, English + Chinese.
- Spearman correlation **0.791** with human preference scores
- Models fine-tuned on MDEval data reach GPT-4o-level Markdown quality
- Confirms: *how well a model handles Markdown predicts response quality*

### 2.3 FMBench (arXiv:2602.06384, Feb 2026)

Markdown-focused output formatting benchmark. Key finding:
there is an **inherent trade-off** between semantic fidelity and
structural compliance. SFT improves semantic alignment; RLFT (GRPO)
improves structural robustness. Both are needed.

### 2.4 Table format benchmark (HN, Oct 2025)

Community benchmark across frontier models on tabular data:

| Format | Accuracy |
|---|---|
| CSV | **84.25%** |
| Markdown Table | 82.65% |
| YAML | 81.85% |
| JSON Lines | 79.85% |
| Markdown KV | 79.83% |
| JSON | 77.73% |
| HTML Table | 75.80% |
| XML | 73.80% |

For tabular data: CSV > Markdown Table > YAML > JSON > HTML > XML.
Caveat: "there are a thousand confounders" — data content affects
results as much as format.

### 2.5 Checksum format experiment (Dec 2025)

Output format impact on code generation and bug fixing:
- Code generation: **all formats perform similarly**
- Bug fixing: **dramatic variance** (scores 0→10 on same task by format)
- JSON performs best for narrative tasks (unexpected)
- XML struggles significantly with precise find/replace patterns

### 2.6 Synthesis: the format decision matrix

| Text type | Best format | Why |
|---|---|---|
| System prompt / policy | **Markdown** | Hierarchy, section boundaries, scannable |
| Tabular tool results | **CSV or Markdown table** | Highest accuracy across models |
| Code snippets | **Fenced code blocks** (Markdown) | Training data alignment |
| Structured records | **Markdown KV** or **YAML** | Token-efficient vs JSON, schema-like |
| Raw HTML from web | **Convert to Markdown** | 80% token reduction, better comprehension |
| Chain-of-thought scratchpad | **Plain text or numbered MD** | Outperforms JSON-wrapped reasoning |
| Schema-heavy machine data | **JSON** (only when data is already JSON) | Avoid format conversion artifacts |


## 3. Context Rot: Why Token Savings Matter for Accuracy

### 3.1 The Chroma finding (Jul 2025)

"Context Rot: How Increasing Input Tokens Impacts LLM Performance"
tested 18 frontier models (GPT-4.1, Claude 4, Gemini 2.5, Qwen3).

Core findings:
- Performance degrades **13.9% to 85%** as input length increases,
  even with 100% perfect retrieval of relevant information
- Degradation occurs even when irrelevant tokens are replaced with
  **whitespace** — sheer length imposes a cognitive tax
- **Coherent, structured input degrades attention MORE than shuffled
  input** — structural patterns in text interfere with attention
  mechanisms at scale
- Accuracy drops **30%+** when relevant info sits in the middle
  ("lost in the middle" effect persists across all 18 models)

### 3.2 Implications for formatting

This creates a **double benefit** for concise Markdown:
1. **Fewer tokens** → less context rot → better accuracy
2. **Better structure** → easier section scanning → relevant info found

But there's a tension at extreme lengths: Chroma found that *coherent*
long documents hurt more than *shuffled* ones. This means:
- Short, well-structured Markdown: **optimal** (structure helps, length is small)
- Long, well-structured Markdown: **worse than expected** (structure
  patterns interfere with attention at scale)
- Short, unstructured plain text: **suboptimal** (no hierarchy to scan)

**Practical conclusion:** Keep context short AND structured. Don't stuff
everything into a huge Markdown document hoping structure will save you.
Use section boundaries to enable targeted retrieval, not as a substitute
for context management.


## 4. Recommendations for First-Agent

### R-1. Keep AGENTS.md and system prompts in Markdown

The NLAH v2 paper validates that structured NL policy achieves 73% on
SWE-bench with 2.9k tokens vs 67% with 60.1k tokens of code. Our
AGENTS.md (currently ~3.5k tokens) is in the right size range.

### R-2. Strip HTML before context injection

HTML→Markdown conversion yields **80% token reduction** (Cloudflare
analysis) and 7pp accuracy improvement on table extraction (60.7% vs
53.6%). The `file_read` tool should strip HTML when possible.

### R-3. Use Markdown tables or CSV for structured tool output

Tabular data performs best as CSV (84.25%) or Markdown table (82.65%),
significantly better than JSON (77.73%) or HTML (75.80%).

### R-4. Avoid context compression as a harness module

NLAH v2 ablation shows context compression **hurts**: −1.0 on SWE,
−8.3 on OSWorld. Summarization drifts from what the evaluator measures.
Prefer targeted file reads over "summarize everything" approaches.

### R-5. Invest in state persistence, not extra branching

NLAH v2 shows file-backed state (+2.6/+13.9) and self-evolution
(+5.8/+8.4) are the strongest modules. Multi-candidate search
(−1.6/+2.8 with 5.2× cost increase) is not worth it at current
model capability. First-Agent's session-per-run isolation aligns
with the file-backed-state pattern.

### R-6. Watch handoff loss in multi-role chains

Handoff Recall drops to 0.32–0.55 in parent-child execution.
First-Agent's planner→coder→eval chain is a parent-child pattern.
Mitigation: explicit state files at each handoff boundary, not
implicit context carry-over.

### R-7. Format is a tuning variable, not a constant

The 2024 formatting study shows **20–40% accuracy swings** from format
alone. When switching models (e.g., GLM → Qwen → DeepSeek), test
whether the current prompt format is still optimal. Different model
families have different format preferences based on training data.


## 5. What's New in NLAH v2 vs v1

| Aspect | v1 (Mar 2026) | v2 (May 2026) |
|---|---|---|
| Benchmarks | Same 3 families | Same, but TB2 analysis deepened |
| Code Harness analysis | Brief | Appendix C: detailed MHTBA portability audit |
| Mechanism metrics | Introduced | Refined definitions, clearer baselines |
| Module ablation | 8 modules | Same 8, better statistical presentation |
| Writing guidelines | Section 3.2 (new) | Practical advice for NLAH authoring |
| Related work | Comprehensive | Expanded with 2026 skill/memory/workflow papers |
| Context rot citation | Absent | Added (Chroma 2025) — validates context discipline |
| OctoBench citation | Absent | Added — scaffold-aware benchmark evaluation |

The v2 paper does **not** change any experimental results — it refines
presentation, adds depth to the TB2/MHTBA analysis, and significantly
expands related work coverage.


## 6. Open Questions

1. **Format preference by model family:** The 2024 study only tested
   GPT-3.5/4. No equivalent study exists for Claude, Gemini, or OSS
   models (DeepSeek, Qwen, GLM). First-Agent uses multiple providers;
   format may need to be provider-aware.

2. **Markdown in reasoning traces:** Chain-of-thought in Markdown
   vs plain text — no controlled study exists. The Chroma finding that
   coherent structure hurts at long contexts suggests that reasoning
   traces (which are long) might benefit from *less* formatting.

3. **NL harness policy + tool-use interaction:** NLAH shows NL policy
   works, but all experiments use a single base agent (Codex CLI with
   gpt-5.4-mini). Generalization to weaker OSS models is untested.
   FA's use of GLM/DeepSeek/Qwen makes this a direct open question.


## 7. Citation Index

| # | Source | Year | Key finding |
|---|---|---|---|
| 1 | Pan et al., NLAH v2 (arXiv:2603.25723v2) | 2026 | NL harness policy matches code; 20× compression; module ablation |
| 2 | Tam et al. (arXiv:2411.10541) | 2024 | Format swings accuracy 20–40%; model-dependent preference |
| 3 | Chen et al., MDEval (arXiv:2501.15000) | 2025 | Markdown Awareness correlated 0.791 with human preference |
| 4 | Wang et al., FMBench (arXiv:2602.06384) | 2026 | Semantic vs structural trade-off in Markdown output |
| 5 | Hong et al., Context Rot (Chroma) | 2025 | Performance degrades with length; coherent structure can hurt |
| 6 | Liu et al., Lost in the Middle (arXiv:2307.03172) | 2024 | 30%+ accuracy drop for middle-positioned info |
| 7 | HN table format benchmark | 2025 | CSV > MD Table > YAML > JSON > HTML > XML for tables |
| 8 | Checksum format experiment | 2025 | Output format matters most for bug-fixing, least for code gen |
| 9 | Arize instruction-following | 2026 | Models improved 10× at instruction following 2024→2026 |
| 10 | Tian Pan, Context Format Decision | 2026 | Format affects reasoning mode, not just output structure |
