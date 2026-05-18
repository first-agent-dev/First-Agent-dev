---
title: "Correlated LLM errors + multi-model ensembling vs First-Agent ADR-1/2/7"
source:
  - "https://arxiv.org/abs/2506.07962"
  - "https://arxiv.org/html/2506.07962v1"
  - "https://arxiv.org/abs/2510.21513"
  - "https://arxiv.org/html/2510.21513v2"
  - "https://arxiv.org/abs/2603.27844"
  - "https://arxiv.org/html/2603.27844v2"
  - "https://arxiv.org/abs/2605.01172"
  - "https://arxiv.org/html/2605.01172v1"
  - "../adr/ADR-1-v01-use-case-scope.md"
  - "../adr/ADR-2-llm-tiering.md"
  - "../adr/ADR-7-inner-loop-tool-registry.md"
  - "../adr/DIGEST.md"
  - "../../AGENTS.md"
  - "./efficient-llm-agent-harness-2026-05.md"
  - "./latent-verifier-evolve-research-2026-05.md"
compiled: "2026-05-13"
chain_of_custody: |
  Все числовые claims по papers 1-3 вытащены напрямую из arxiv HTML
  страниц перечисленных в `source:`:
  - Paper 1 (Kim, Garg, Peng, Garg — Cornell, ICML 2025;
    arXiv:2506.07962v1): «60% agreement when both wrong on Helm vs 33%
    random»; «349 LLMs / 12 032 MCQ HuggingFace + 71 LLMs / 14 042 MCQ
    Helm + 20 LLMs / 1 800 resume-job pairs»; «larger and more accurate
    models have highly correlated errors, even with distinct architectures
    and providers»; «judges overinflate the accuracy of models that are
    less accurate than it — especially for models of the same provider
    or architecture» — все из §Abstract + §1 Introduction + §4
    LLM-as-judge HTML fetch на 2026-05-13.
  - Paper 2 (Vallecillos-Ruiz, Hort, Moonen — Simula, 2026;
    arXiv:2510.21513v2): «10 LLMs from 5 families × 3 SE benchmarks»;
    «theoretical upper bound 83% above best single»; «consensus-based ⇒
    popularity trap»; «diversity-based realizes up to 95% of theoretical
    potential»; «works on 2-model ensembles» — все из §Abstract + §1
    + §Contributions HTML fetch на 2026-05-13.
  - Paper 3 (Nitarach — Apr 2026; arXiv:2603.27844v2 / "Model Capability
    Dominates: Inference-Time Optimization Lessons from AIMO 3"):
    «gpt-oss-120b ↑̂p=0.69 score 39.3 vs gpt-oss-20b ↑̂p=0.61 score 31.0
    at N=8»; «temperature T=1.0 optimal; T=0.8→40, T=0.5→38, T=1.2→37»;
    «19 computable ρ̂-points, all negative; mean −0.122 for N≥7»;
    «gpt-oss-20b drops 31.0(N=8) → 26(N=32)»; «majority-vote 42 vs
    pass@20 ≈45.5 = selection loss, not prompt loss» — все из
    §Abstract + §2 System Architecture + §3 Diverse Prompt Mixer +
    §4 Why It Fails + Table 1/2 + Figure 1/2/3 HTML fetch на 2026-05-13.
  - Paper 4 (Litman & Guo — Stanford, May 2026; arXiv:2605.01172v1
    "A Theory of Generalization in Deep Learning"): абстракт зафиксирован
    в §4.4 / §9 как primary-source цитата, но note не опирается на его
    численные claims; оценка относится только к relevance к UC1+UC3
    harness scope (training-time generalization theory ⊥ inference-time
    multi-model orchestration).
  All ADR / AGENTS.md facts — из локального git checkout
  Bupitsa-ai/First-Agent-debloat main HEAD `59dcb9b` (2026-05-12)
  на момент компиляции.

  §10 «Secondary lens» append — добавлен 2026-05-13 in-PR (повторный
  pass по тем же четырём papers под non-primary goal_lens-2:
  loop-creation / sandbox / tool-calling, по запросу project lead).
  Те же primary-source URLs из `source:`; никаких новых fetches не
  понадобилось. Goal_lens-2 verbatim — в §10.0; три новых R-7..R-9
  TAKE верификации, шесть CUT-ов задокументированы для transparency.
goal_lens: "Снизить session-start context noise для будущих агентов + найти один immediate-improvement, implementable в следующий PR (combined (a)+(b) per research-briefing.md Stage 1)."
tier: stable
links:
  - "../adr/ADR-1-v01-use-case-scope.md"
  - "../adr/ADR-2-llm-tiering.md"
  - "../adr/ADR-7-inner-loop-tool-registry.md"
  - "../adr/DIGEST.md"
  - "./efficient-llm-agent-harness-2026-05.md"
  - "./latent-verifier-evolve-research-2026-05.md"
  - "./cutting-edge-agent-research-radar-2026-05.md"
mentions:
  - "Cornell University"
  - "Simula Research Laboratory"
  - "Stanford University"
  - "ICML 2025"
  - "Helm leaderboard"
  - "HuggingFace leaderboard"
  - "AIMO 3 competition"
  - "gpt-oss-120b / gpt-oss-20b"
  - "Qwen3.5-35B-A3B"
  - "Nemotron-Super-120B"
  - "Diverse Prompt Mixer"
  - "Condorcet Jury Theorem"
  - "popularity trap"
  - "algorithmic monoculture"
confidence: extracted
claims_requiring_verification:
  - "Paper 1 §4.2 точная регрессионная цифра для «same-provider judge
    over-inflation» в процентных пунктах не вынесена в abstract —
    в этой ноте мы цитируем общий направленческий вывод («especially
    for models of the same provider or architecture»), не конкретный
    point-estimate. Прежде чем закрепить в ADR-2 числа типа «+X pp
    over-inflation», нужен прогон full PDF / open-access reproduction."
  - "Paper 3 ρ̂≈−0.122 measured на AIMO 3 math problems с tool-integrated
    Python code execution — это узкая domain (IMO-level math с verifier
    answer-keys). Распространение «temperature already decorrelates»
    на code-gen / agent-tool-call workloads требует отдельной replication;
    paper 2 §1 цитирует Lu et al. 2024 + Ashiga et al. 2025 как survey-coverage,
    но pairwise-correlation на code-gen specifically — open empirical
    question. **§10 R-8 (F-B intra-role retry temperature default) inherits
    этот caveat**: temperature-as-decorrelator finding из P-3 §4.1 проверен
    только на IMO math; до domain-replication на FA Coder workload R-8
    остаётся docs-only conditional TAKE."
  - "Paper 2 «95% of theoretical 83% uplift» measured на 10 LLMs from 5
    families. Если FA в production окажется с overlap-providers (например,
    Planner=GLM 5.1 и Eval=Kimi 2.6 — оба top-tier OSS из общего
    провайдер-облака OpenRouter), эта цифра может деградировать; paper 1
    говорит, что top-tier accuracy → higher correlation независимо от
    provider, что в худшем сценарии режет diversity-selector benefit."
  - "Paper 4 (NTK generalization theory) применимости к FA не оценен
    количественно — отнесён к §9 Out of scope на основании topic-match,
    не negative empirical test. Если v0.2 будет рассматривать
    fine-tuning OSS-моделей внутри FA harness, paper 4 SNR-preconditioner
    может всплыть снова — relevance переоценить при таком триггере."
superseded_by: none
---

> **Status:** active. Note produced via
> [`knowledge/prompts/research-briefing.md`](../prompts/research-briefing.md)
> workflow. §0 — Decision Briefing для project lead и future LLM agents,
> читающих ноту сверху; §1.. — deep-dive, грузить только если §0
> недостаточно.

## 0. Decision Briefing

Шесть основных рекомендаций (`R-1..R-6`) на основе трёх papers (`P-1`
Cornell correlated-errors, `P-2` Simula LLM-ensembles, `P-3` Nitarach
AIMO 3), плюс `R-6` SKIP по `P-4` (Stanford NTK theory) как
out-of-scope. Все verdicts resolved — UNCERTAIN-ASK блоков нет.
Goal-lens см. в frontmatter и §2.

**Secondary lens addendum** (2026-05-13). Те же четыре papers переоценены
под non-primary goal_lens-2 (loop-creation / sandbox / tool-calling — см.
§10.0 verbatim); три дополнительных рекомендации `R-7..R-9` (все TAKE,
docs-only) задокументированы в **§10**, не в §6. R-7/R-8/R-9 включены в
summary table ниже для один-stop §0 read. Шесть отвергнутых findings
перечислены в §10.4 для transparency. Все verdicts resolved — снова без
UNCERTAIN-ASK.

### R-1 — ADR-2 Amendment: Eval-role MUST использовать provider+family disjoint от Planner и Coder

- **What:** ADR-2 §Decision сейчас фиксирует Eval-роль как «DIFFERENT
  top-tier OSS / DIFFERENT model; isolated config slot so judge can
  be version-pinned» — без формального constraint на
  provider/architecture-family. P-1 §4 (LLM-as-judge downstream
  experiment, 349 + 71 LLMs) показал: judge **over-inflates** accuracy
  of judged models «especially for models of the same provider or
  architecture». Для FA это прямой риск: если Planner=`z-ai/glm-5.1`,
  Coder=`qwen/qwen3-coder-27b`, а judge=`z-ai/kimi 2.6` (все три из
  GLM/Qwen-семейства common OpenRouter pool), Eval-баллы Planner-output
  и Coder-output будут систематически смещены вверх. Amendment должен
  ужесточить правило: `judge.primary.provider ≠ {planner.primary.provider,
  coder.primary.provider}` AND `judge.primary.architecture_family ≠
  {planner.primary.architecture_family, coder.primary.architecture_family}`,
  с loader-validation как hard error на старте (симметрично к ADR-2
  §Amendment 2026-04-29 `tool_protocol` mixed-chain validation).
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (~300 tokens сэкономлены в
    каждой будущей ADR-2 / Eval-related сессии — primary-source-cited
    rule заменяет ad-hoc обсуждение «какую judge-model выбрать»).
  - (B) helps LLM find context when needed: YES (pointer-shape —
    `models.yaml` validator → ADR-2 §Amendment 2026-05-XX → paper P-1
    §4 finding; вместо «расскажите, почему Eval нельзя на той же
    модели»).
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens "Снизить session-start context noise
    + найти один immediate-improvement implementable в следующий PR":
    YES (это immediate-PR-target — одна страница amendment в ADR-2
    + одна row в DIGEST.md + одна exploration_log Q-block; покрывает
    обе половины goal_lens).
- **Cost:** cheap (<1h — amendment write + DIGEST row + exploration_log
  Q-2-bis block; loader-validator implementation отдельный PR в
  `src/fa/llm/router.py`, но shape-decision и rule wording — это
  immediate PR).
- **Verdict:** TAKE
- **If UNCERTAIN-ASK:** n/a (TAKE resolved).
- **Alternative-if-rejected:** Оставить «DIFFERENT model» как soft
  guideline → принять risk что v0.2 Eval baselines будут carry +X pp
  систематического смещения (см. §5 caveat #1 про неопределённость X)
  → invalidate первые UC5 eval-runs и потребовать full re-run после
  обнаружения. Cost-of-rejection ≥ 1-2 дня re-run + repuration cost
  Pillar-4 «iteration via measurement» если bias выяснится post-baseline.
- **Concrete first step (if TAKE):** В
  [`knowledge/adr/ADR-2-llm-tiering.md`](../adr/ADR-2-llm-tiering.md)
  §Amendments добавить блок `### Amendment 2026-05-XX — Eval-role
  provider/family disjoint constraint` с (a) формальным правилом, (b)
  ссылкой на P-1 §4 как primary-source, (c) one-line config example,
  (d) loader-error wording. В same PR обновить
  [`adr/DIGEST.md`](../adr/DIGEST.md) ADR-2 row, добавить bullet под
  `**Amendments.**`. Per AGENTS.md PR Checklist rule #9 — appended
  block в [`knowledge/trace/exploration_log.md`](../trace/exploration_log.md)
  для ADR-2 Q-2 («judge selection») как amendment, не новый Q.

### R-2 — Strengthen ADR-2 «no cross-tier auto-escalation» rationale primary-source citation

- **What:** ADR-2 §Decision §Option B обосновывает «no cross-tier
  auto-escalation» через user-stated preference + Cons-list
  (predictable cost, predictable behaviour, simple to debug). P-1
  (top-tier accuracy → higher correlation, even cross-provider) +
  P-3 (model capability dominates, prompt-level interventions fail
  to recover ±2pt gap) обе дают независимое primary-source backing:
  cross-tier auto-escalation **expected-return ≈ noise** в первом
  приближении, поскольку (a) errors top-tier OSS Planner и elite Debug
  частично correlate (P-1 finding), и (b) если Coder упёрся в hard
  task, Critique-loop или larger-model-swap ↑capability дешевле и
  надёжнее, чем prompt-divergence (P-3 finding). Это **strengthen-only**
  изменение: текущее decision сохраняется; добавляется одно-два
  предложение в §Rationale с cross-reference на эту ноту.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: PARTIAL (saves ~150 tokens в
    будущих обсуждениях ADR-2 escalation-policy; небольшой эффект,
    т.к. ADR-2 уже не predmet активного debate).
  - (B) helps LLM find context when needed: YES (pointer-shape — будущий
    reader ADR-2 видит primary-source evidence-trail для key trade-off
    «predictable vs auto-recover»).
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: YES (часть half-(a) noise-reduction;
    half-(b) immediate-PR — пишется в same PR как R-1).
- **Cost:** cheap (<30 min — два sentence добавления в существующий
  §Decision / §Consequences без shape change).
- **Verdict:** TAKE
- **If UNCERTAIN-ASK:** n/a (TAKE resolved).
- **Alternative-if-rejected:** Оставить rationale как есть; принять
  риск что v0.2 reviewer когда-нибудь предложит auto-escalation snub
  user-preference аргументом «but other harnesses do it» — без
  primary-source backing аргумент сложнее парировать одной ссылкой.
- **Concrete first step (if TAKE):** В same PR как R-1, в ADR-2
  §Consequences §«No auto-escalation» добавить one-sentence reference
  на эту ноту §4.1 + P-1 §4 + P-3 §4 evidence pair.

### R-3 — AGENTS.md rule #10 minimalism-first evidence: «prompt-diversity layer» как recognized anti-pattern

- **What:** AGENTS.md PR Checklist rule #10 (Harness-component PRs
  cite minimalism-first evidence, 4-question test) требует от PR-author
  показать «research-evidence supporting the component's necessity»
  AND «open-source agent-stack precedent that already removed or did
  not add a similar component». P-3 предоставляет **прямое
  negative-evidence** для семейства предложений «add prompt-diversity
  layer» (persona-rotation, role-templates, Diverse Prompt Mixer
  multi-persona): 23+ experiments, 4 strategies, **monotonically degrades
  performance**, root cause `T=1.0` уже decorrelates errors (ρ̂≈−0.12).
  Это не сразу in-tree код-изменение — это **citation-row в DIGEST.md /
  AGENTS.md cross-reference** который будущий PR-author может потянуть,
  когда какой-нибудь reviewer / sub-agent предложит «давайте добавим 3
  persona-prompt»; rule #10 question 1 («research-evidence supporting
  necessity») закрывается reference на эту ноту §4.3.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (~200-300 tokens сэкономлены
    в каждой будущей rule #10 evaluation, где prompt-diversity на
    столе — short-circuit через primary-source quote вместо повторного
    обсуждения).
  - (B) helps LLM find context when needed: YES (pointer-shape — rule
    #10 4-question test получает named evidence-source для
    common-but-rejected harness pattern).
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: YES (half-(a) noise-reduction для
    minimalism-first evaluations; half-(b) immediate-PR в same или
    follow-up PR).
- **Cost:** cheap (<30 min — one bullet в DIGEST §«See also» или
  one-row в AGENTS.md cross-references; альтернатива — отдельный bullet
  в §Recommended secondary reading этой ноты).
- **Verdict:** TAKE
- **If UNCERTAIN-ASK:** n/a (TAKE resolved).
- **Alternative-if-rejected:** Каждый будущий PR-author проходит rule
  #10 question 1 заново для «add prompt-diversity layer»; risk = some
  weaker OSS Coder reviewer **не** найдёт P-3 на 5-min search и одобрит
  prompt-diversity, который при baseline-prove deteriorate UC5 metrics.
- **Concrete first step (if TAKE):** В same PR как R-1+R-2 добавить
  однострочный mention в [`adr/DIGEST.md`](../adr/DIGEST.md) §See also
  или в [`AGENTS.md`](../../AGENTS.md) PR Checklist rule #10 (выбор
  места — в §6 R-3 deep-dive обоснован выбор DIGEST §See also как
  менее invasive AGENTS-edit).

### R-4 — DEFER: multi-model ensembling с diversity-based selector → UC5d (eval-driven harness iteration)

- **What:** P-2 §4-6 показывает, что ensembling 2-10 LLMs с
  **diversity-based** selection (NOT consensus, который попадает в
  «popularity trap») realizes 95% теоретического 83% uplift над best
  single на code-gen + APR benchmarks. Для FA это потенциальный major
  Pillar-3 win, но **противоречит v0.1 scope**: ADR-1 ставит UC1+UC3
  в scope, multi-model ensembling под UC2 (multi-source research)
  best-effort или UC5 (eval-driven harness iteration) deferred. Кроме
  того, ensembling требует selector-machinery (latent-verifier-like;
  см. cross-reference с `latent-verifier-evolve-research-2026-05.md`
  R-4 «latent-space watch-list only»), которого в v0.1 нет. Правильное
  место — UC5 §5b-bis (Amendment ADR-1) или BACKLOG.md новый entry.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: PARTIAL (если попадёт в BACKLOG —
    унифицирует «multi-LLM ensembling» discussion в одну row; если в
    ADR-1 — добавляет ещё одну UC5-sub-bullet, slight noise growth).
  - (B) helps LLM find context when needed: YES (anchors future v0.2
    proposals «давайте сделаем ensemble Planner» на primary-source +
    deferred-decision row).
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: PARTIAL (goal-lens half-(a)
    noise-reduction слабо; half-(b) immediate-PR — нет, это DEFER).
- **Cost:** cheap-to-defer (<30 min — BACKLOG row или ADR-1 §UC5
  bullet); medium-to-expensive если build now (требует selector
  implementation + per-model adapter cost ≥ ADR-3 chunker scope).
- **Verdict:** DEFER
- **If UNCERTAIN-ASK:** n/a (DEFER resolved).
- **Alternative-if-rejected:** Build-now (TAKE) — нарушает ADR-1 v0.1
  scope; SKIP-permanently — теряет один из самых empirically-strong
  Pillar-3 efficient-harness wins на горизонте 2026 года.
- **Concrete first step (if TAKE → defer marker):** Добавить entry
  в [`knowledge/BACKLOG.md`](../BACKLOG.md) — новый `I-10` row:
  «Multi-model ensembling with diversity-based selector (UC5-candidate)»
  с unblock-trigger «UC5d implementation (score tracking / leaderboard)
  ships + selector primitive lands». В **отдельном** последующем PR;
  не обязательно в same PR как R-1..R-3.

### R-5 — DEFER: verifier-based selection > majority-vote (P-3 §4.4 finding) → UC5 candidate

- **What:** P-3 §4.4 разделяет «prompt-diversity loss» (≈0pp) от
  «selection loss»: gap between majority-vote 42/50 и pass@20≈45.5 —
  это selection-loss, и **verifier-based selector** мог бы его закрыть,
  prompt engineering — не мог. Direct cross-reference: First-Agent
  `latent-verifier-evolve-research-2026-05.md` R-4 уже defer-аnula
  «universal verifier» как separate runtime; R-1 of that note ставит
  «acceptance rubric fixtures before verifier machinery» как cheaper
  predecessor. P-3 finding **усиливает** существующее latent-verifier
  R-4 DEFER: prompt-diversity не закроет selection-loss; нужна
  verifier-or-equivalent machinery, которая в v0.1 не строится.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: PARTIAL (saves ~100 tokens в
    будущих обсуждениях «зачем нам verifier» — short-circuit через
    P-3 quote).
  - (B) helps LLM find context when needed: YES (pointer-shape —
    cross-reference между этой нотой §4.3 / `latent-verifier-evolve`
    R-4 / hypothetical UC5 verifier ADR).
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: PARTIAL (half-(a) noise-reduction
    слабо; half-(b) immediate-PR — нет, DEFER).
- **Cost:** cheap-to-defer (<15 min — one-bullet cross-ref в
  `latent-verifier-evolve-research-2026-05.md` R-4 или в эту ноту §4.3);
  expensive-if-built (verifier-machinery в v0.1 → нарушает ADR-1).
- **Verdict:** DEFER
- **If UNCERTAIN-ASK:** n/a (DEFER resolved).
- **Alternative-if-rejected:** Build-now — нарушает ADR-1; SKIP — теряет
  cross-reference между этой нотой и latent-verifier defer-decision,
  что снижает navigation value для будущих v0.2 readers.
- **Concrete first step (if TAKE → defer marker):** В §4.3 этой ноты
  явная one-line ссылка на
  [`latent-verifier-evolve-research-2026-05.md` R-4](./latent-verifier-evolve-research-2026-05.md);
  при future-revision этой латер-noty (post-merge этого PR, либо в
  UC5 ADR draft) добавить symmetric cross-link.

### R-6 — SKIP: Paper 4 (NTK generalization theory) — out of scope для UC1+UC3 harness research

- **What:** P-4 (Litman & Guo, Stanford, arXiv:2605.01172v1) —
  non-asymptotic theory of generalization в deep learning через
  empirical-NTK partitioning output space на signal channel и
  reservoir; derives SNR-preconditioner on Adam (5× faster grokking,
  3× closer DPO under noisy preferences). Topic-match относительно
  ADR-1..7 = ≈0: FA — это inference-time orchestration single-user
  harness (UC1+UC3 v0.1; UC5 deferred), не training-time / fine-tuning
  research. NTK theory объясняет *почему* модели вообще обобщают; FA
  принимает их generalization as a black-box и оптимизирует *что
  делать с готовыми моделями*. Никакая часть P-4 не предлагает
  decision relevant для ADR-1..7.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: NO (skipping a paper не reduces
    noise; documenting *why* skipped — да, но это уже §9 Out of scope
    handling, не recommendation).
  - (B) helps LLM find context when needed: NO (no FA-side decision
    surface attaches to P-4).
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens: NO (P-4 не относится к UC1+UC3
    harness; ни half-(a) noise-reduction ни half-(b) immediate-PR не
    выигрывают).
- **Cost:** n/a (SKIP — нет action item).
- **Verdict:** SKIP
- **If UNCERTAIN-ASK:** n/a (SKIP resolved).
- **Alternative-if-rejected:** TAKE — потребует scope-expansion в
  fine-tuning territory, что v0.1 ADR-1 явно out-of-scope ставит;
  DEFER — нет actionable hook (P-4 не привязан к UC5 deferred slot).
- **Concrete first step (if TAKE → not taken):** §9 Out of scope этой
  ноты явно фиксирует rationale-rejection одним параграфом + P-4 listed
  в §8 Files used как «scanned, found not applicable». Re-evaluation
  trigger: v0.2 рассматривает fine-tuning OSS-моделей в FA harness
  loop — тогда P-4 SNR-preconditioner может стать актуальным.

### Summary

Primary-lens recommendations (§6, goal_lens-1 = noise-reduction + immediate-PR):

| R-N | Verdict | Project-fit (A / B) | Goal-fit (C) | Cost | Alternative-if-rejected | User decision needed? |
|-----|---------|---------------------|--------------|------|--------------------------|------------------------|
| R-1 | TAKE | YES / YES | YES (Eval-role disjoint, immediate-PR) | cheap | Soft guideline only; risk biased UC5 baselines | No (TAKE) |
| R-2 | TAKE | PARTIAL / YES | YES (rationale-hardening, immediate-PR) | cheap | Rely on user-pref only; harder to defend later | No (TAKE) |
| R-3 | TAKE | YES / YES | YES (rule #10 evidence, immediate-PR) | cheap | Repeat 4-question test from scratch each time | No (TAKE) |
| R-4 | DEFER | PARTIAL / YES | PARTIAL (UC5 candidate) | cheap-defer / medium-build | Build-now (violates ADR-1) / SKIP permanently | No (DEFER) |
| R-5 | DEFER | PARTIAL / YES | PARTIAL (verifier-defer) | cheap-defer | Build-now (violates ADR-1) / lose cross-ref | No (DEFER) |
| R-6 | SKIP | NO / NO | NO (P-4 out of scope) | n/a | Scope-expansion to fine-tuning territory | No (SKIP) |

Secondary-lens recommendations (§10, goal_lens-2 = loop / sandbox / tool-calling):

| R-N | Verdict | Project-fit (A / B) | Goal-fit (C — goal_lens-2) | Cost | Alternative-if-rejected | User decision needed? |
|-----|---------|---------------------|----------------------------|------|--------------------------|------------------------|
| R-7 | TAKE | YES / YES | YES (loop retry-budget invariant, ADR-7 evidence-row + DIGEST) | cheap | Implicit-only rule; risk unbounded inner-loop retries в future hook code | No (TAKE) |
| R-8 | TAKE (conditional, docs-only) | PARTIAL / YES | PARTIAL (intra-role retry temperature default; pending FA-domain replication) | cheap | Default to ad-hoc T=0.0..0.7 per agent; loses P-3 evidence-row | No (TAKE; promote to invariant after domain replication, см. Q-2) |
| R-9 | TAKE | YES / YES | YES (ADR-7 hook design constraint; symmetric к R-1) | cheap | LLM-using hooks без provider/family check; risk in-loop bias mirror R-1 issue | No (TAKE) |

<!--
  Goal-fit (C) cell carries Y / PARTIAL / N + a 2–3-word tag; the full
  1-sentence reason lives in the per-R block above.
-->

## 1. TL;DR

- **P-1 (Cornell, ICML 2025) headline**: на 349 + 71 LLMs модели
  соглашаются 60% времени при ошибке (vs 33% random); same-provider /
  same-architecture усиливают correlation; even top-tier cross-provider
  модели имеют высоко correlated errors; LLM-as-judge **over-inflates**
  judged-model accuracy при shared provider/architecture.
- **P-2 (Simula, 2026) headline**: 10 LLMs from 5 families на 3 SE
  benchmarks — theoretical ensemble upper bound 83% above best single;
  consensus-selection попадает в «popularity trap» (amplifies common-but-wrong);
  **diversity-based** selection realizes 95% теоретического потенциала
  даже на 2-model ensembles.
- **P-3 (Nitarach, Apr 2026) headline**: AIMO 3 competition, 23+
  experiments, 50 IMO-level problems — **every prompt-level intervention
  fails**; high-temperature sampling (T=1.0) уже decorrelates errors
  (ρ̂≈−0.122 mean for N≥7); 8-point capability gap (gpt-oss-120b 0.69
  vs gpt-oss-20b 0.61 at N=8) dwarfs ±2pt prompt-optimization range;
  scaling N beyond compute backfires.
- **P-4 (Stanford, May 2026) headline**: NTK partitioning theory of
  generalization (signal channel vs reservoir); SNR-preconditioner +1
  Adam state-vector; 5× grokking, 3× closer DPO. **Topic-orthogonal
  к UC1+UC3 inference-time harness** — out of scope (§9, R-6 SKIP).
- **For FA**: cross-reference triad P-1+P-2+P-3 даёт три primary-source
  hooks для ADR-2: (R-1) Eval-role provider/family disjointness
  amendment **as the immediate PR**; (R-2) no-cross-tier-escalation
  rationale hardening; (R-3) prompt-diversity-layer anti-pattern citation
  in AGENTS.md rule #10 evidence base.
- **Two DEFERs к UC5**: (R-4) multi-model ensembling with diversity
  selector — Pillar-3 candidate, blocked on UC5d; (R-5) verifier > majority
  vote — cross-references existing `latent-verifier-evolve-research-2026-05.md`
  R-4 defer-row.
- **Goal-lens (a)+(b) satisfied**: один immediate-PR (R-1+R-2+R-3 в
  одной shape) closes half-(b); session-start noise-reduction через
  named primary-source pointers вместо ad-hoc retro-debate closes half-(a).
- **Secondary-lens (loop / sandbox / tool-calling) findings (§10)**: три
  docs-only TAKE-рекомендации под goal_lens-2 — R-7 ADR-7 retry-budget
  invariant из P-3 §4.3 «N beyond compute backfires», R-8 intra-role retry
  temperature default T=1.0 из P-3 §4.1 (conditional, pending code-gen
  replication), R-9 ADR-7 hook design constraint (LLM-using hooks satisfy
  provider/family ≠ acting-role per P-1 §4 generalization). Шесть отвергнутых
  findings — в §10.4 (P-3 §4.4 selection-loss, P-1 §refusal-correlation, P-3
  tool-execution-as-verifier, P-1 §arch-correlation на tool-arg shape,
  P-2 §popularity-trap на tool-arg JSON, P-4 NTK reservoir/signal метафора)
  — все CUT по causes «confirms-existing-design» или «speculative bridge».

## 2. Scope, метод

**Sources read.** Четыре arXiv papers, перечисленных в `source:`
frontmatter, full HTML fetched на 2026-05-13. Локальный repo state —
git HEAD `59dcb9b` (Bupitsa-ai/First-Agent-debloat main, post ADR-7
merge 2026-05-12).

**Deliberately excluded.**

- Full PDF reading of P-1 §4 LLM-as-judge regression tables — abstract
  + introduction + §4 HTML вытащены, но per-regression-coefficient
  numbers (e.g. «X pp inflation at same-provider») не цитируются как
  point-estimates; см. `claims_requiring_verification` #1 в frontmatter.
- P-3 full appendices §G «Cross-Model Configurations» — read at section-title
  level only; main-paper Table 1 / Table 2 / §3-4 пройдены полностью.
- P-4 §3-9 (NTK theorem proofs, SNR-preconditioner derivation) — пройден
  только §Abstract + §1 Introduction + §Figure 1 caption; relevance
  оценена топик-уровнем (см. R-6 SKIP).
- Other FA research notes («cross-reference-ampcode-sliders», «sliders-structured-reasoning»,
  «agent-roles», etc.) — surface-grep only по ключевым терминам (`monoculture`,
  `judge`, `correlated`, `ensemble`) для confirm-by-absence: ни одна
  существующая нота не cross-references P-1..P-4 vs ADR-2. Subtraction-check
  (AGENTS.md Pre-flight Step 4) пройден.

**Method.** Cross-reference review — каждое paper-finding явно
маппинуется на конкретный ADR-claim или AGENTS.md rule (см. §4 mapping
table), и выписывается decision-relevant delta (R-N в §0 / §6).

**Goal-lens (verbatim from frontmatter).** «Снизить session-start
context noise для будущих агентов + найти один immediate-improvement,
implementable в следующий PR (combined (a)+(b) per research-briefing.md
Stage 1).»

## 3. Key concepts (source-language terms)

- **Correlated errors**: agreement rate of two LLMs **conditional on
  both being wrong** (P-1 §1 definition). Random-baseline для k-option
  MCQ: $1/(k-1)$.
- **Algorithmic monoculture**: ситуация, в которой многие decision-makers
  используют один и тот же model → systemic exclusion of one applicant
  by all firms (Kleinberg & Raghavan 2021, cited in P-1).
- **LLM-as-judge over-inflation**: judge model assigns higher accuracy
  scores to judged models with **shared provider or architecture**
  относительно cross-family judged models (P-1 §4 finding).
- **Popularity trap**: consensus-based ensemble selection (majority
  voting / pick-most-common) amplifies common-but-incorrect outputs
  when multiple models converge on a shared wrong answer (P-2 §1
  definition).
- **Diversity-based selection**: selection heuristic that prioritizes
  candidates whose features (lexical / semantic / structural) are
  outliers in the candidate pool; P-2 §6 reports up to 95% of theoretical
  83%-uplift с этим подходом.
- **Condorcet Jury Theorem**: $p > 0.5$ + independent errors → majority
  vote converges to correct answer as $N$ grows (de Condorcet 1785).
  P-3 §1 показывает, что independence assumption fails on math problems:
  ρ̂ near zero or negative, $N_{\text{eff}} \neq N$.
- **Effective sample size**: $N_{\text{eff}} = N / (1 + (N-1)\rho)$
  where $\rho$ — mean pairwise error correlation (P-3 Equation 1). At
  $\rho = 0.3$, eight attempts reduce to 2.6 effective votes.
- **Diverse Prompt Mixer**: P-3 §3 baseline approach — assign different
  reasoning system-prompts (Original / Small Cases First / Work Backwards
  / Classify Then Solve) to different voters; tested and **rejected**
  in P-3.
- **Selection loss**: P-3 §4.4 — gap between majority-vote score
  (42/50 on AIMO 3) and $\text{pass@}20$ ($\approx 45.5$), attributed
  to selection mechanism (verifier-shaped) rather than per-attempt
  diversity.
- **NTK signal channel / reservoir** (P-4): empirical neural tangent
  kernel partitions output space into directions training can move
  (signal channel) and test-invisible orthogonal directions (reservoir).
  Used in §4.4 only to confirm relevance assessment; not in any FA-side
  decision.

## 4. Mapping / analysis

### 4.1 P-1 «Correlated Errors» → ADR-2 Eval-role and «no cross-tier auto-escalation»

P-1 §1 ставит исследовательский вопрос: «How correlated are LLM errors
— how often do models converge on the same wrong answer?» Ответ §3
(regression analysis on 349-LLM HuggingFace + 71-LLM Helm + 20-LLM
resume-screening): **substantial correlation**, ~60% agreement when
both wrong on Helm (vs $1/3$ random baseline для 4-option MCQ). §3
factor analysis: same-provider, same-architecture, similar size →
increased correlation; critically, **«larger and more accurate models
have highly correlated errors, even with distinct architectures and
providers»** (P-1 Abstract).

§4 разворачивает downstream-effect для LLM-as-judge: «judges overinflate
the accuracy of models that are less accurate than it — especially for
models of the same provider or architecture». Это прямой удар по
текущему ADR-2 Eval-role decision:

| ADR-2 §Decision row | Текущий wording | P-1 §4 implication |
|---|---|---|
| `judge` row in `~/.fa/models.yaml` | «DIFFERENT top-tier OSS / DIFFERENT model ; isolated config slot so judge can be version-pinned» | «DIFFERENT model» — слишком мягкое: same-provider или same-architecture-family того же провайдера попадает в bias-zone |
| §Consequences §«Eval baseline drift mitigated by version-pin» | Корректно — но не покрывает per-snapshot bias введённый shared-family judge | Per-snapshot bias стабилен → version-pin **не** решает проблему inflation |
| §Amendment 2026-04-29 Critic clarification | Eval ≠ Critic; offline judge, не in-loop | Не противоречит — P-1 finding по-прежнему применим к offline judge-mode |

Отсюда R-1 (TAKE): formal `provider ≠` + `architecture_family ≠`
constraint, loader-level hard error.

P-1 §3 «top-tier accuracy → correlation» дополнительно даёт P-1-side
support для ADR-2 §Decision §Option B «no cross-tier auto-escalation»:
если elite Debug (Claude) и top-tier OSS Planner (GLM 5.1) частично
share error-set с mid-tier Coder hard-task failure mode (потому что
high-accuracy convergence — это feature, не bug current LLM ecosystem),
тогда auto-escalation **expected uplift** систематически меньше, чем
naive «escalate up the tier» heuristic подразумевает. Не drama-rebut
аргумент, но evidence-row для §Rationale (см. R-2 TAKE).

### 4.2 P-2 «Wisdom and Delusion of LLM Ensembles» → UC5 candidate + ADR-2 implication

P-2 §1 contributions выписывает (P-2 §1 verbatim quote):

> «We quantify the performance ceiling offered by ensembles of models,
> demonstrating a potential performance increase of up to 83% in the
> number of problems solved by the best individual model. … We identify
> the challenge of the "popularity trap" where models frequently converge
> on the same incorrect solution and provide a strategy to counter
> this trap that realizes up to 95% of the ensemble's theoretical
> potential.»

P-2 finding **complements P-1**: P-1 говорит «errors correlate
substantially», P-2 говорит «несмотря на correlation, complementarity
exists и diversity-based selector its capture — 95% of theoretical».
Это снимает риск over-pessimism «correlation kills ensembling»:
ensembling работает, если selector — diversity-based, не consensus.

Для FA это **Pillar-3 candidate**: token-efficient harness может
выиграть существенный accuracy uplift через 2-model ensembling, если
selector реализован. НО:

- ADR-1 v0.1 scope = UC1+UC3 single-model orchestration; multi-model
  ensembling = UC2 best-effort (deferred) или UC5 eval-driven iteration
  (deferred).
- P-2 ensembling требует **selector machinery**, которая ≈
  «universal verifier without runtime» (cross-ref с
  [`latent-verifier-evolve-research-2026-05.md`](./latent-verifier-evolve-research-2026-05.md)
  R-1 acceptance-rubric-fixtures, R-4 latent-watch-list-only); selector
  build cost = medium-to-expensive.
- AGENTS.md PR Checklist rule #10 question 1 (research-evidence) для
  any multi-LLM ensembling PR замыкается на эту ноту §4.2 + P-2.

Отсюда R-4 (DEFER): добавить BACKLOG row `I-10` с unblock-trigger
«UC5d ships + selector primitive lands». Не отдельный note, не
ADR-now.

P-2 §5 (heuristics evaluation) дополнительный finding: consensus-based
selection — это **default** в naive ensembling, и она **systematically
worse** than diversity-based. Для FA это означает: если в v0.2 кто-нибудь
proposes simple «majority vote between two Coders», это идёт в
**popularity trap** zone — пометить в BACKLOG как known-anti-pattern.

### 4.3 P-3 «Model Capability Dominates» → AGENTS.md rule #10 + ADR-7 prompt-design + UC5 verifier

P-3 — самая прямая negative-evidence в triade. §3 описывает Diverse
Prompt Mixer (DPM):

> «Four complementary strategies, each a different system prompt with
> all other parameters identical: Original (step-by-step), Small Cases
> First, Work Backwards, Classify Then Solve.»

§3 Table 1 results (gpt-oss-120b, $N=8$, AIMO 3 50 IMO problems):

| Configuration | LB Score |
|---|---|
| Baseline (21 runs, 8×Original) | 39.3 mean |
| Conservative (5+1+1+1) | 40 |
| Aggressive (3+2+2+1) | 40 |
| Equal (2+2+2+2) | 38 |
| 8× Small Cases | 37 |
| 8× Work Backwards | 39 |
| 8× Classify | 36 |
| 8× Code-first (3 runs) | 41, 38, 34 (mean 37.7) |
| Formalize-First | 39 |

P-3 §3 conclusion: «More diversity = worse performance. The relationship
is monotonic.» §4.1 объясняет почему:

- §4.1 temperature ablation: $T=0.5 \to 38$, $T=0.8 \to 40$, $T=1.0 \to
  39.3$, $T=1.2 \to 37$ — high temperature alone уже decorrelates
  внутри одного prompt.
- §4.2 method-of-moments estimator для pairwise correlation: 19
  computable points, **all negative**; mean $\hat{\rho} = -0.122$ for
  $N \geq 7$. Equation 1 ($N_{\text{eff}} = N / (1 + (N-1)\rho)$) при
  $\rho < 0$ даёт $N_{\text{eff}} > N$ — overdispersion, не correlation.
- §4.3 weaker strategies reduce per-attempt accuracy $\bar{p}$; decorrelation
  (если бы существовала headroom) не превышает accuracy loss.

P-3 §4.4 разделяет «prompt-loss» и «selection-loss»:

> «The gap between the best majority-vote score (42/50) and pass@20
> ($\approx 45.5$) is selection loss, not prompt loss. A verifier-based
> selector could close it. Prompt engineering cannot.»

Для FA это **direct evidence base для AGENTS.md rule #10 question 1**
(research-evidence supporting harness-component necessity):

- Любой будущий PR-author, который предлагает «add prompt-diversity
  layer / persona-rotation / role-template fanout», провалит rule #10
  question 1 с P-3 на руках reviewer'а.
- Rule #10 question 4 («Could this step be a deterministic Python
  function instead of an LLM call?») усиливается: если single-LLM с
  $T=1.0$ уже decorrelates, добавление persona-templates — это LLM-step
  без incremental capability, который рассматривается как «add Python
  formatting» альтернатива (но даже эта Python-альтернатива не нужна).

Отсюда R-3 (TAKE): one-line citation row в DIGEST.md §See also (либо в
AGENTS.md rule #10 reference list) с P-3 § и ссылкой на §4.3 этой ноты.

P-3 §4.4 «verifier > majority-vote» дополнительно cross-references
existing FA `latent-verifier-evolve-research-2026-05.md` R-4
(latent-space watch-list only, defer-row для universal verifier).
Это сводится к R-5 (DEFER): symmetric cross-link, no new artefact.

ADR-7 §Decision (inner-loop / tool-registry contract,
accepted 2026-05-12) уже не содержит prompt-diversity layer
(см. existing `efficient-llm-agent-harness-2026-05.md` R-1..R-8 — все
8 R-Ns касаются tool-disclosure / trace-separation / FTS5 reuse, не
prompt-fanout). P-3 backwards-validates это design choice как
empirically-evidenced minimalism-first wins, а не just-coincidence.

### 4.4 P-4 «NTK Generalization Theory» — relevance assessment

P-4 §Abstract (verbatim):

> «We present a non-asymptotic theory of generalization in deep
> learning where the empirical neural tangent kernel partitions the
> output space. In directions corresponding to signal, error dissipates
> rapidly; in the vast orthogonal dimensions corresponding to noise,
> the kernel's near-zero eigenvalues trap residual error in a
> test-invisible reservoir. … We derive an exact population-risk
> objective from a single training run with no validation data … it
> accelerates grokking by 5×, suppresses memorization in PINNs and
> implicit neural representations, and improves DPO fine-tuning under
> noisy preferences while staying 3× closer to the reference policy.»

P-4 — training-time mechanism. FA — inference-time orchestration.
Mapping table:

| P-4 finding | FA component с potential touch-point | Verdict |
|---|---|---|
| NTK partitioning explains generalization | ADR-2 LLM tiering — FA uses pre-trained models as black boxes | Out of scope (FA не тренирует модели в v0.1) |
| SNR-preconditioner on Adam, 1 extra state-vector | ADR-3 memory variant — FA uses external Markdown + SQLite, no optimizer | Out of scope (no FA-side optimizer) |
| 5× faster grokking | n/a (FA не делает model training) | Out of scope |
| DPO fine-tuning improvement (3× closer to reference) | UC5 deferred (ADR-1 §Amendment 2026-05-06 5a-5e eval-driven iteration; possibly future fine-tuning) | Re-evaluation trigger: если UC5 expands to «fine-tune FA-tier models» — открыть P-4 заново |
| Benign overfitting / double descent / implicit bias explanations | n/a (not relevant к agent-harness design) | Out of scope |
| Grokking explained as signal migration from reservoir → signal channel | n/a | Out of scope |

P-4 — **excellent paper в своём scope** (Stanford, May 2026,
arXiv:2605.01172v1; submission-quality theory). Просто не относится к
UC1+UC3 inference-time orchestration на горизонте v0.1..v0.2. R-6
SKIP — это **scope-judgment, не quality-judgment**.

Re-evaluation trigger (formally noted in §9):

- UC5d / UC5e ADR (когда / если) добавляет fine-tuning OSS-моделей
  внутри FA harness — P-4 SNR-preconditioner может быть Pillar-3
  efficiency win.
- Любая Phase-M PR, которая trains anything (адаптеры, LoRA, RM для
  preference-tuning) — re-fetch P-4, оценить P-4 §6 SNR-preconditioner
  ablation cost.

## 5. Risks and caveats

1. **P-1 §4 over-inflation magnitude — точная цифра в %pp не
   зафиксирована в этой ноте**. R-1 amendment wording в ADR-2 не
   должен утверждать конкретный «+X pp bias»; only direction
   («over-inflates»). Если в same PR кто-то захочет cite numeric
   estimate, full PDF P-1 §4 (или open-access reproduction in P-1
   GitHub `nikhgarg/llm_correlated_errors_public`) — required step.
2. **P-3 ρ̂ measurement domain ≠ FA target domain**. AIMO 3 — это
   IMO-level math с tool-integrated Python (verifier-style answer
   checking). FA UC1 — code-gen + PR-write; UC3 — local-docs-to-wiki.
   P-3 «temperature alone decorrelates ρ̂≈−0.122» **может** не
   обобщиться на FA Coder-output (which is free-form code / patches,
   not numeric answers с unique correct answer). До использования
   P-3 «high temperature alone decorrelates» в любом FA harness
   decision (вне R-3 / R-5 deferred) — нужна domain-replication.
3. **P-2 «95% of 83% uplift» под shared-provider degradation risk**.
   P-2 §6 measurement на 10 LLMs from 5 families; FA model-mix per
   ADR-2 (GLM 5.1 / Kimi 2.6 / Nemotron 3 Super / Qwen 3.6) частично
   overlap-provider (общий OpenRouter pool). Если v0.2 FA reaches
   multi-model ensembling, P-2 95% upper-bound — нужно re-replicate
   на actual FA model-set; до того **claim only directionally**.
4. **R-1 loader-validator implementation cost не в R-1 scope**.
   Текущий R-1 cost-estimate = «cheap < 1h» относится только к
   amendment wording + DIGEST row + exploration_log block. Сам
   `src/fa/llm/router.py` validation — отдельный PR (Phase M item),
   и его cost ≈ ADR-2 §Amendment 2026-04-29 mixed-`tool_protocol`
   validator (тоже отложен на implementation phase). Не блокирует
   immediate-PR R-1.
5. **P-1, P-2, P-3 — all empirical findings on snapshot data 2025-2026
   model ecosystem**. Future LLM releases (2026-2027) могут изменить
   correlation landscape: если major architecture innovations произойдут
   и diversity grows, P-1 finding ослабнет, и R-1 strict-disjointness
   rule может стать over-restrictive. Re-evaluation trigger: yearly
   sweep of cited papers (per AGENTS.md Pre-flight Step 1 recency-surface
   logic), либо UC5 baseline shows zero bias detection over N runs.

## 6. Numbered recommendations (R-1..R-6, primary lens)

> **Primary lens** (goal_lens-1 из frontmatter): noise-reduction +
> immediate-PR из P-1/P-2/P-3 vs ADR-1/2/7 и AGENTS.md rule #10.
> Secondary-lens recommendations R-7..R-9 (loop / sandbox / tool-calling) —
> в §10, не здесь, чтобы сохранить per-lens разделение по Stage-1 elicitation.

### R-1 — ADR-2 Eval-role provider/family disjointness (cost: cheap)

См. §0 R-1 для full eight-field block. Дополнительная prose:

The amendment лучше всего embed в ADR-2 §Amendments как `### Amendment
2026-05-XX — Eval-role provider/family disjointness constraint`. Body
≈ 30-40 lines:

- **Context**: P-1 §4 LLM-as-judge over-inflation finding, primary
  source citation.
- **Decision (additive)**: формальное правило `judge.primary.provider
  ≠ planner.primary.provider AND judge.primary.provider ≠
  coder.primary.provider`; и аналогично `architecture_family ≠`. Loader
  rejects mismatched config as hard error на startup, симметрично к
  ADR-2 §Amendment 2026-04-29 mixed-`tool_protocol` rule.
- **Configuration shape**: example showing valid (Planner=GLM 5.1 /
  Coder=Nemotron 3 Super / Judge=Claude Sonnet или Mistral Large —
  cross-family) vs invalid (Planner=GLM 5.1 / Coder=Qwen 3.6 / Judge=GLM 5.1
  Air — same family).
- **Consequences**: `models.yaml` schema additive; current Eval pick
  «Kimi 2.6» — verifiable cross-provider, если Planner ≠ Kimi-family.
  Existing model picks могут потребовать re-pick; document как
  forward-only rule (existing configs grandfathered только если they
  pass the new constraint).

В same PR:

- `adr/DIGEST.md` ADR-2 row — добавить amendment bullet (one paragraph).
- `knowledge/trace/exploration_log.md` ADR-2 Q-2 («judge selection
  policy») — добавить amendment-block с `Chosen:` updated, `Rejected:
  shared-provider-allowed` + `Reason: P-1 §4 over-inflation`, +
  `Lesson: re-open if open-access reproduction shows <5pp inflation
  for top-tier OSS judges`.

### R-2 — ADR-2 «no cross-tier auto-escalation» rationale hardening (cost: cheap)

См. §0 R-2 для full block. Embed: в ADR-2 §Consequences §«No
auto-escalation» добавить one-paragraph after existing «v0.2 may
revisit»:

> Эта позиция дополнительно подкрепляется primary-source evidence
> [P-1 §4](./correlated-llm-errors-and-ensembling-2026-05.md#4-1-p-1-correlated-errors--adr-2-eval-role-and-no-cross-tier-auto-escalation)
> (top-tier accuracy → cross-provider correlation persists) и
> [P-3 §4](./correlated-llm-errors-and-ensembling-2026-05.md#4-3-p-3-model-capability-dominates--agentsmd-rule-10--adr-7-prompt-design--uc5-verifier)
> (model capability dominates ±2pt prompt-optimization range). Если
> Coder failure на hard task — это primarily capability-bound (Pillar-3
> evidence), а не stochastic-bound, тогда auto-escalation **expected
> uplift** систематически меньше than naive «escalate up tier»
> heuristic подразумевает.

### R-3 — DIGEST.md / AGENTS.md rule #10 citation row for «prompt-diversity layer» anti-pattern (cost: cheap)

См. §0 R-3 для full block. Two options for embedding:

- (a) **DIGEST.md §See also** — добавить one-bullet «Prompt-diversity
  as harness component is empirically a known anti-pattern; primary
  source [P-3](./correlated-llm-errors-and-ensembling-2026-05.md#4-3-p-3-model-capability-dominates--agentsmd-rule-10--adr-7-prompt-design--uc5-verifier)
  §3 + §4». Less invasive AGENTS-edit; agents discover via DIGEST
  lookup.
- (b) **AGENTS.md rule #10** — добавить explicit example «E.g.,
  prompt-diversity / persona-rotation layers — research-evidence P-3
  shows monotonic degradation under standard temperature settings;
  do not add без replication on FA target workload.»

§6 recommend option (a) — DIGEST §See also — для меньшего PR diff и
для матчинга существующего DIGEST §See also pattern. Option (b) выше
escalation level и стоит follow-up PR-обсуждения.

### R-4 — BACKLOG row I-10: multi-model ensembling with diversity-based selector (cost: cheap-defer)

См. §0 R-4 для full block. Embed:

В [`knowledge/BACKLOG.md`](../BACKLOG.md) — новый row:

```text
## I-10 — Multi-model ensembling with diversity-based selector (UC5-candidate)

**Status:** deferred to UC5d.

**Rationale.** P-2 (arXiv:2510.21513v2) finds 95% of 83% theoretical
uplift via diversity-based selection across 2-10 LLM ensembles на
code-gen + APR. Pillar-3 candidate.

**Blocked-on:** UC5d eval-driven harness iteration (per ADR-1 §Amendment
2026-05-06). UC5d ships selector primitive + score-tracking.

**Unblock-trigger:** UC5d implementation reaches selector slot; selector
primitive can be reused (latent-watch-list or candidate-feature based).

**First concrete step once unblocked:** ADR-N proposing multi-Coder
config in `models.yaml`; selector implementation under
`src/fa/eval/select/`; cross-reference cycle with
`correlated-llm-errors-and-ensembling-2026-05.md` §4.2 + P-2.
```

Не обязательно в same PR как R-1..R-3.

### R-5 — Cross-link `latent-verifier-evolve` R-4 ↔ this note §4.3 (cost: cheap-defer)

См. §0 R-5 для full block. Embed:

Минимальная forma — one-line добавление в этой ноте §4.3 (уже сделано
в этом drafting pass; см. §4.3 final paragraph). При future-revision
[`latent-verifier-evolve-research-2026-05.md`](./latent-verifier-evolve-research-2026-05.md)
R-4 — symmetric back-link на эту ноту §4.3.

Не отдельный PR. Запись в §6 фиксирует обязательство для future maintainer.

### R-6 — P-4 NTK theory out-of-scope rationale (cost: n/a — SKIP)

См. §0 R-6 для full block. Embed: §9 Out of scope этой ноты явно
documents rejection. Re-evaluation trigger при UC5 expansion to
fine-tuning territory.

## 7. Open questions (Q-1..Q-3)

### Q-1 — Какой именно «architecture family» constraint loader должен энфорсить для R-1?

R-1 wording говорит про `architecture_family ≠`, но точное определение
family — open question. Опции:

- (a) **Provider-prefix-based**: `provider:family` (e.g.
  `openrouter:z-ai`, `openrouter:qwen`, `anthropic:claude`,
  `openai:gpt`) — крепкая heuristic для текущего landscape, но fragile
  при provider acquisitions / brand changes.
- (b) **Stated-architecture-string field в `models.yaml`**: user explicitly
  declares family per slug; loader validates by string equality. Less
  fragile, but user-burden.
- (c) **Inferred from model-slug pattern**: regex-based extraction
  (e.g. `glm-*` → `glm`, `qwen*` → `qwen`, `claude-*` → `claude`).
  Cheaper than (b), risky for less-canonical slugs.

Recommendation: (b) с (c) fallback при missing-field — least-fragile
+ fail-loud. Resolution в same PR как R-1 amendment, или в follow-up
implementation PR (loader-validator).

### Q-2 — Domain-replication P-3 «high temperature alone decorrelates» на FA Coder workload — кто проводит?

P-3 measurement domain = AIMO 3 IMO-level math с tool-integrated
Python execution and unique numeric answer. FA UC1 Coder workload =
code-gen / patch-write — diverse outputs, no «correct/wrong» binary,
verification = test-suite pass. ρ̂≈−0.122 finding **может** не
обобщиться. Resolution: deferred to UC5b benchmark suite (per ADR-1
§Amendment 2026-05-06); not blocking для R-1..R-5.

### Q-3 — Should ADR-2 «Eval ≠ Critic» rule (§Amendment 2026-04-29 #5) explicitly note P-1 §4 as bias-source для **future** Critic role (v0.2)?

ADR-2 §Amendment 2026-04-29 §point 5 фиксирует «v0.1 inner-loop has no
Critic / Reflector role» — future v0.2 ADR может вводить Critic.
Должен ли v0.2 Critic слот наследовать тот же `provider/family disjoint`
constraint, что и Eval / Judge? P-1 §4 finding относится к LLM-as-judge
(outcome-evaluation), не к LLM-as-critic (in-loop process critique) —
but the bias mechanism (shared-provider/architecture-error-set) теоретически
тот же. Resolution: open для v0.2 ADR drafter; зафиксировано здесь как
pointer. Not blocking для current v0.1 PR.

## 8. Files used

Primary sources:

- [arXiv:2506.07962v1](https://arxiv.org/abs/2506.07962) — Kim, Garg,
  Peng, Garg «Correlated Errors in Large Language Models» (Cornell,
  ICML 2025).
- [arXiv:2510.21513v2](https://arxiv.org/abs/2510.21513) —
  Vallecillos-Ruiz, Hort, Moonen «Wisdom and Delusion of LLM Ensembles
  for Code Generation and Repair» (Simula Research Laboratory, 2026).
- [arXiv:2603.27844v2](https://arxiv.org/abs/2603.27844) — Nitarach
  «Model Capability Dominates: Inference-Time Optimization Lessons
  from AIMO 3» (Apr 2026).
- [arXiv:2605.01172v1](https://arxiv.org/abs/2605.01172) — Litman, Guo
  «A Theory of Generalization in Deep Learning» (Stanford, May 2026)
  — scanned, found not applicable to UC1+UC3 harness scope (см. §4.4,
  §9, R-6 SKIP).

FA repo files (local git HEAD `59dcb9b`, 2026-05-12):

- [`AGENTS.md`](../../AGENTS.md) §PR Checklist rules #8 / #9 / #10 /
  #11; §Pre-flight checklist Steps 1-5.
- [`knowledge/adr/ADR-1-v01-use-case-scope.md`](../adr/ADR-1-v01-use-case-scope.md)
  §Decision (UC1+UC3 in scope; UC5 deferred) + §Amendment 2026-05-06
  (UC5a-5e eval-driven harness iteration).
- [`knowledge/adr/ADR-2-llm-tiering.md`](../adr/ADR-2-llm-tiering.md)
  §Decision §Option B + §Amendment 2026-04-29 (`tool_protocol`, no
  Critic) + §Amendment 2026-05-01 (MCP forward-compat).
- [`knowledge/adr/ADR-7-inner-loop-tool-registry.md`](../adr/ADR-7-inner-loop-tool-registry.md)
  §Decision (no prompt-diversity layer; tool-disclosure 3-tier; static
  layered prompt).
- [`knowledge/adr/DIGEST.md`](../adr/DIGEST.md) — ADR-2 / ADR-7 rows.
- [`knowledge/research/efficient-llm-agent-harness-2026-05.md`](./efficient-llm-agent-harness-2026-05.md)
  — surface-grep по `judge` / `ensemble` (absence-confirms unique value
  этой ноты).
- [`knowledge/research/latent-verifier-evolve-research-2026-05.md`](./latent-verifier-evolve-research-2026-05.md)
  §0 R-4 (latent-space watch-list only) — cross-link target из R-5.
- [`knowledge/BACKLOG.md`](../BACKLOG.md) — existing I-1..I-9; R-4
  proposes I-10.
- [`knowledge/prompts/research-briefing.md`](../prompts/research-briefing.md)
  — Stage 1-5 workflow (this note's production process).
- [`knowledge/research/_template.md`](./_template.md) — frontmatter
  + §0 + §1..§9 skeleton.

## 9. Out of scope

Эта нота **deliberately не покрывает**:

- **P-4 (Litman & Guo, Stanford, arXiv:2605.01172v1, May 2026)** —
  «A Theory of Generalization in Deep Learning». R-6 SKIP. Rationale:
  P-4 — training-time mechanism (empirical NTK partitioning, SNR-preconditioner
  on Adam, DPO fine-tuning improvement). FA v0.1 scope per ADR-1 = UC1+UC3
  inference-time orchestration on pre-trained models as black boxes;
  ни одно из ADR-1..7 не touches training / fine-tuning surface. Topic-match
  ≈ 0. Re-evaluation trigger: UC5d / UC5e ADR expands to fine-tuning OSS
  models внутри FA harness — тогда P-4 SNR-preconditioner может стать
  Pillar-3 efficiency candidate.
- **Implementation of R-1 loader-validator** (`src/fa/llm/router.py`
  schema-validation для `provider/family disjoint` rule). R-1 scope =
  amendment wording + DIGEST row + exploration_log block. Implementation
  — separate Phase M PR, симметрично к ADR-2 §Amendment 2026-04-29
  mixed-`tool_protocol` validator (deferred similarly).
- **P-3 ρ̂≈−0.122 replication on FA Coder workload**. См. Q-2 — deferred
  to UC5b benchmark suite.
- **P-1 §4 numeric over-inflation %pp estimate** (e.g. «+X pp for
  same-provider judge»). См. caveat #1 — full PDF reading / open-access
  reproduction required before any FA decision cite numeric estimate.
- **Modifications to existing accepted ADRs** beyond ADR-2 amendment
  для R-1 + R-2 rationale-row. Any ADR-1 §UC5 expansion (R-4 BACKLOG
  → eventually ADR-N) — separate PR after lead approval.
- **Modifications to existing research notes**. Cross-links (R-5)
  noted as future-maintenance pointer; not edited in this PR (per
  AGENTS.md rule #5 «supersession not overwrite» — this note is new,
  no existing note is superseded).
- **Multi-fork PR coordination** (Bupitsa-ai/First-Agent-debloat →
  upstream merge logistics). Handled by project lead per `knowledge/llms.txt`
  §Project stage paragraph.

## 10. Secondary lens — loop / sandbox / tool-calling (2026-05-13 addendum)

Этот раздел — повторный pass по тем же четырём papers под non-primary
goal_lens-2, инициированный project lead через chat 2026-05-13 после
landing первой шестёрки `R-1..R-6` в этой же PR. Стиль и format — те
же 8-field per-R-N блоки + единый CUT-список. Никаких новых sources не
читалось; ссылки те же, что и в §0/§4 — `arXiv:2506.07962v1`,
`arXiv:2510.21513v2`, `arXiv:2603.27844v2`, `arXiv:2605.01172v1`.

### 10.0 Goal_lens-2 (verbatim)

«Extract non-obvious insights from P-1..P-4 that improve FA
loop-creation / sandbox / tool-calling subsystems, where papers aren't
directly on these topics, and that correlate with current four-pillar
project axes.»

Подчёркнуто **non-obvious** — papers (Cornell correlated-errors / Simula
ensembling / Nitarach AIMO 3 / Stanford NTK) явно не про inner-loop
ReAct цикл, не про path-allow-list sandbox, и не про MCP-shaped
tool-registry. Лензy-2 интересуют пересекающиеся выводы: findings,
которые fall out из measurements авторов как side-effect, и которые
переносятся на FA subsystems по аналогии. Под этим лезвием большинство
findings отсекается как **confirms-existing-design** или
**speculative bridge** — см. §10.4 CUT-список. Три find переживают
триаж: R-7, R-8, R-9.

### 10.1 Triage rationale

Критерии acceptance в §10.2/10.3 — primary-source-citable, design-actionable
(не только «информационная заметка»), и cross-axis fit с двумя
из четырёх pillars project-overview.md §1.1 (research-backed implementation,
pragmatic single-user, most efficient OSS harness, iteration via measurement).
Findings, которые проходят только axis-A или axis-B (noise-reduction /
context-pointer), без axis-C (advances goal_lens-2 — concrete subsystem
delta), идут в CUT. P-4 NTK reservoir/signal-channel метафора рассмотрена
и отвергнута как **speculative bridge** — conceptual rhyme без
actionable transfer, см. §10.4 CUT #6.

### R-7 — ADR-7 retry-budget invariant: inner-loop retry budgets MUST be config-bounded (P-3 §4.3)

- **What:** ADR-7 §Decision §«Inner loop» текущий fix — single-thought →
  single-tool-call → observation → next-turn loop. Intra-role retry-loop
  «допустим в рамках same role per ADR-2 §Amendment 2026-04-29 §5» —
  без явного config bound. P-3 §4.3 Table 2 показывает: gpt-oss-20b
  $N{=}8 \to 31.0$, $N{=}32 \to 26.0$ — увеличение sample-N **без**
  пропорционального увеличения compute backfires monotonically.
  ADR-7 должен фиксировать это как primary-source-cited invariant:
  «intra-role retry budget config-bound; default $N \le 3$; promotion к
  более высокому $N$ требует UC5 measurement (Pillar-4)». Концретно
  — добавить в `ADR-7 §Decision §Inner loop` подпункт «Retry budgets»
  с одной строкой config-bound rule + 1-line citation P-3 §4.3.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (один primary-source-pin вместо
    ad-hoc «сколько раз retry-ить» обсуждений в каждой Phase-M PR).
  - (B) helps LLM find context when needed: YES (pointer-shape: ADR-7
    §Decision §Inner loop §Retry budgets → P-3 §4.3 Table 2).
- **Goal-lens fit (per session, dynamic — goal_lens-2):**
  - (C) advances chosen goal_lens-2 «loop / sandbox / tool-calling
    non-obvious insights»: YES (loop-creation: explicit retry-budget
    invariant в ADR-7, ранее implicit).
- **Cost:** cheap (<1h — single ADR-7 §Decision sub-bullet + DIGEST.md
  row update; no `src/fa/loop/` code touched since current implementation
  не реализует retry-loop yet — invariant вступает в силу при первой
  Phase-M PR, добавляющей intra-role retry).
- **Verdict:** TAKE
- **If UNCERTAIN-ASK:** n/a (TAKE resolved).
- **Alternative-if-rejected:** Оставить «retry budgets implicit», полагаясь
  на minimalism-first AGENTS.md rule #10 как single restraint. Risk: первый
  Phase-M PR, добавляющий intra-role retry для Coder/Debug, может зашить
  unbounded retry-loop или $N{=}\text{большое}$ default, тратя compute
  и landing AIMO-style regression (per P-3 §4.3). Cost-of-rejection ≥
  1 retro-amendment PR + 1 Pillar-4 measurement run для baseline.
- **Concrete first step (if TAKE):** В
  [`knowledge/adr/ADR-7-inner-loop-tool-registry.md`](../adr/ADR-7-inner-loop-tool-registry.md)
  §Decision §«Inner loop» добавить bullet `**Retry budgets.**` с
  rule «`max_retry_per_role <= 3` default; configurable per role;
  promotion к более высокому $N$ требует Pillar-4 measurement
  (UC5b benchmark)»; primary-source citation `P-3 §4.3 (arXiv:2603.27844v2
  Table 2) — gpt-oss-20b $N{=}8 \to 31.0$, $N{=}32 \to 26.0$; scaling N
  beyond compute backfires monotonically». DIGEST.md ADR-7 row — добавить
  bullet под `**Amendments / Inner-loop bullets.**`.

### R-8 — Intra-role retry temperature default T=1.0 (P-3 §4.1, conditional TAKE)

- **What:** Если intra-role retry-loop (R-7 above) когда-либо
  активируется, sampling temperature default должен быть высоким, **не**
  низким. P-3 §4.1: $T{=}0.5 \to 38$, $T{=}0.8 \to 40$, $T{=}1.0 \to 39.3$,
  $T{=}1.2 \to 37$. Концепт «retry with $T{=}0$ для consistency» —
  recognized anti-pattern: nominal consistency воспроизводит ту же ошибку.
  P-3 одновременно показывает $\hat{\rho} \approx -0.122$ для $N{\ge}7$
  при $T{=}1.0$ within single model — высокая температура **внутри**
  одной модели уже decorrelates errors enough, что explicit multi-model
  ensembling часто не нужен (см. R-4 DEFER в §6 для multi-model trajectory).
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (default temperature
    documentation вместо повторяющихся «какую temperature использовать
    для retry» дискуссий).
  - (B) helps LLM find context when needed: YES (pointer-shape:
    `~/.fa/models.yaml` schema doc → ADR-2/ADR-7 retry-temperature
    bullet → P-3 §4.1 Table 1).
- **Goal-lens fit (per session, dynamic — goal_lens-2):**
  - (C) advances chosen goal_lens-2: PARTIAL (loop-creation: concrete
    config default + explicit anti-pattern; HOWEVER conditional на
    domain replication — см. caveat ниже).
- **Cost:** cheap (<30 min — single bullet в ADR-2 §Amendment-NN OR
  ADR-7 §Decision §Inner-loop §Retry budgets с note о temperature
  default; OR `~/.fa/models.yaml` schema doc).
- **Verdict:** TAKE (conditional, docs-only). Promotion к hard-invariant
  blocked на FA Coder workload domain replication — см. Q-2.
- **If UNCERTAIN-ASK:** n/a (conditional TAKE resolved; conditional на
  Q-2 outcome, не блокирует embedding документации now).
- **Alternative-if-rejected:** Default to ad-hoc per-agent temperature
  (typically `T=0.0..0.7` для «consistency»), теряем primary-source
  evidence-row и оставляем anti-pattern undocumented. Risk: первая
  Phase-M PR, добавляющая intra-role retry, выбирает $T{=}0$ default,
  reproduce same error → loop невыходной.
- **Concrete first step (if TAKE):** В том же ADR-7 §Decision §Inner-loop
  bullet `**Retry budgets.**` (см. R-7 above) добавить под-строку:
  «temperature default $T{=}1.0$ on retry attempt (P-3 §4.1 — high-temp
  within single model decorrelates $\hat{\rho} \approx -0.122$); explicit
  anti-pattern: «retry with $T{=}0$ для consistency» — reproduces error.
  Conditional invariant: promote к hard rule после FA Coder domain
  replication per Q-2». ADR-2 §Amendments — нет изменений (config-default
  живёт в ADR-7 inner-loop scope).

### R-9 — ADR-7 hook design constraint: LLM-using hooks satisfy provider/family ≠ acting-role (P-1 §4 + R-1 generalization)

- **What:** ADR-7 §Decision §«Mini hook pipeline» (pre_tool / post_tool)
  currently описан как «mostly deterministic Python; hook may call LLM
  если task требует». R-1 (§6 above) добавил provider/family ≠
  acting-role constraint для Eval-role; та же P-1 §4 LLM-as-judge
  over-inflation finding применима к **любому** in-loop hook, который
  использует LLM для self-evaluation Coder/Planner output (i.e. hook-LLM
  judges another LLM's tool-call args или output). Constraint
  симметричный R-1: «LLM-using hooks MUST satisfy
  `hook.primary.provider ≠ acting-role.primary.provider` AND
  `hook.primary.architecture_family ≠ acting-role.primary.architecture_family`».
  Если hook чисто-deterministic (Python validators, regex matchers,
  schema-strict checks) — constraint не применим (no LLM call). Если
  hook делает LLM call для «is this output reasonable» — applies.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (хорошая default constraint
    предотвращает retro-amendment, когда первый LLM-using hook landed
    с shared-family bias).
  - (B) helps LLM find context when needed: YES (pointer: ADR-7
    §Decision §Hook pipeline → P-1 §4 finding → R-1 §0 block).
- **Goal-lens fit (per session, dynamic — goal_lens-2):**
  - (C) advances chosen goal_lens-2: YES (loop-creation + tool-calling:
    explicit design constraint, ранее implicit; cross-references R-1
    Eval-role rule для consistency).
- **Cost:** cheap (<30 min — single bullet в ADR-7 §Decision §Mini hook
  pipeline; no code change since hooks в v0.1 deterministic, constraint
  activates при первом LLM-using hook).
- **Verdict:** TAKE
- **If UNCERTAIN-ASK:** n/a (TAKE resolved).
- **Alternative-if-rejected:** Hooks без constraint → first Phase-M PR
  с LLM-using hook (e.g. «verify Coder output is reasonable» через
  Coder-family LLM call) reproduces P-1 §4 bias inside the loop. Cost-of-rejection
  ≥ 1 retro-amendment + потенциальный re-run UC5b baselines, если hook
  использовался для filter-pass measurements.
- **Concrete first step (if TAKE):** В
  [`knowledge/adr/ADR-7-inner-loop-tool-registry.md`](../adr/ADR-7-inner-loop-tool-registry.md)
  §Decision §«Mini hook pipeline» добавить bullet `**LLM-using hook
  constraint.**` с rule «если hook вызывает LLM (rare in v0.1; default
  hooks — deterministic Python), hook.primary MUST satisfy provider/family
  ≠ acting-role.primary per same rule as R-1 §6 для Eval-role; primary
  source — P-1 §4 (arXiv:2506.07962v1) LLM-as-judge over-inflation
  finding». DIGEST.md ADR-7 row — добавить bullet под `**Amendments /
  Hook pipeline.**`.

### 10.4 Considered-and-CUT (six findings)

Шесть findings из той же четвёрки papers рассмотрены и отвергнуты как
не-проходящие триаж §10.1 (либо **confirms-existing-design** — паттерн
уже зашит в ADR-1..7, no actionable delta; либо **speculative bridge** —
conceptual rhyme без primary-source-actionable transfer). Перечислены
для transparency и future-revisit if domain replication изменит cost-balance.

1. **P-3 §4.4 «selection loss > prompt loss» применительно к loop.**
   CUT — confirms-existing-design. ADR-7 §Decision уже центрируется
   на tool-execution → observation → next-turn-decision паттерне; это
   selection-driven, not prompt-driven, by design. Paper validates но
   не proposes change. (R-5 §6 уже DEFER'ит ту же finding под другой
   axis — verifier-defer pattern.)
2. **P-1 §refusal-correlation применительно к sandbox (ADR-6).**
   CUT — speculative bridge. ADR-6 deny-by-default chosen на
   threat-model grounds (sandbox = hard-allow-list, no model
   judgment); добавлять «P-1 supports it» как post-hoc rationalization
   не даёт actionable delta. Re-evaluate trigger: ADR-6 v2 considers
   model-driven sandbox bypass (вряд ли).
3. **P-3 tool-execution-as-verifier implicit паттерн.** CUT — informational
   only. AIMO 3 wins precisely потому что sandbox-execution = verifier;
   FA уже использует ту же модель (ADR-7 §Decision tool-call →
   observation). Adding citation row в DIGEST §ADR-6/-7 — noise без
   decision change. Subtraction-first per AGENTS.md rule #10 wins.
4. **P-1 §architecture-correlation применительно к tool-arg shape
   correlation.** CUT — confirms-existing-design. ADR-2 §Decision
   §Notes-on-model-slugs + Amendment 2026-04-29 verified-model-coverage
   list уже empirically pinned per-architecture (Qwen-coder 3.6 native,
   Kimi 2.6 prompt-only, GLM 5.1 native). P-1 backs choice conceptually,
   но ADR-2 уже cites primary-source evidence (P-1 в этой же ноте через
   R-1). Adding second citation row — duplication.
5. **P-2 popularity-trap on tool-arg JSON shape.** CUT — already
   mitigated. ADR-2 §Amendment 2026-05-01 #1 JSON-Schema-strict
   boundary validation catches «popular-but-wrong tool-arg shape» by
   design (schema rejection happens before model output ever reaches
   tool runtime). P-2 finding applies где schema validation **отсутствует**;
   FA's schema-strict invariant moots it.
6. **P-4 reservoir/signal-channel метафора применительно к loop.**
   CUT — speculative bridge. Tempting to say «reservoir = untested code
   paths, signal channel = observed tool-call/result pairs»; conceptual
   rhyme, но P-4 — training-time NTK theory, no inference-time transfer.
   Reaching for primary-source citation от P-4 для inference-loop
   decisions = misuse. P-4 correctly остаётся R-6 SKIP per §6.

### 10.5 Goal_lens-2 specific caveats

Дополнительные caveats, специфичные для §10 recommendations (общие
caveats §5 #1..#5 продолжают применяться):

- **F-B / R-8 inherits frontmatter caveat #2** (P-3 ρ̂≈−0.122 measured
  только на IMO math с tool-integrated Python verifier). FA Coder
  workload — code-gen + tool-call, **не верифицирован тем же
  measurement-protocol**. До domain replication R-8 остаётся
  conditional, docs-only — promotion к hard-invariant blocked на
  Q-2 outcome. Concrete unblock trigger: UC5b benchmark suite landed
  и показывает $\hat{\rho} < 0$ для $N{\ge}7$ at $T{=}1.0$ within
  single model на FA Coder targets.
- **F-A / R-7 measurement domain caveat**. P-3 §4.3 measurements
  делались на $N{=}1{,}2{,}4{,}8{,}16{,}32$ AIMO problems with
  Python execution verifier — closed-domain (math с answer-key).
  FA Coder loop — open-domain code-gen, где «retry budget» имеет
  иную failure-mode: код может пройти tests на retry #3 не потому
  что better sample, а потому что test-set itself недо-specified
  (overfit). R-7 «config-bound retry budget» — directionally safe
  (cap unbounded retries), но конкретный default `N <= 3` — **первая
  approximation** без FA-specific measurement. Promotion default-cap
  к более detailed «per-role budget» (e.g. `coder: N<=3, debug: N<=5`)
  — separate Phase-M PR после UC5b baseline.
- **F-C / R-9 LLM-using-hook scope ambiguity**. Constraint применяется
  к hooks, которые **вызывают** LLM. Граничные случаи: (a) hook,
  который только parses LLM output (no second LLM call) — constraint
  не применим; (b) hook, который вызывает LLM, но в read-only режиме
  (no decision-affecting return) — constraint **strictly** применим
  even though impact мал. Unblock через Q-NN (future) — нужно явное
  ADR-7 wording, что определяет «LLM call» для hook-purposes
  (probably: «any inference call к external/local LLM API, regardless
  of how its output is consumed»).

### 10.6 Cross-axis fit reminder

R-7/R-8/R-9 — **все три** docs-only, no code change. Combined cost ≈
1.5h aggregate (3 × ADR-7 sub-bullets + 1 DIGEST.md update + 1
exploration_log block для cluster). Implementation cost (actual
retry-loop code, hook code, etc.) **out of scope** — separate
Phase-M PRs activated when подсистема building. R-7/R-8/R-9 чисто
prep-of-evidence для future PR authors.
