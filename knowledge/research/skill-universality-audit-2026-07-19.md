# Universality Audit — tests-writing/SKILL.md

> **Created:** 2026-07-19
> **Question:** How well does the tests-writing skill hold up as a UNIVERSAL rulebook
> for all projects built with the FA harness, not just this repo's observability system?

---

## The Problem

The skill has **154 references** to FA-specific concepts (EventType, OutputEvent,
EventBus, ConsoleRenderer, drive_session, EventLog, ContextBudget, HookRegistry,
ProviderChain, FeatureFlags, etc.) in a document that's supposed to be universal.

The PRINCIPLES are universal. The FRAMING is not. An agent working on a different
project that uses the FA harness (e.g., a data pipeline, a code-review bot, a
document processing system) would encounter:

- Concepts it doesn't have (EventType, EventBus, OutputEvent)
- Composition roots it doesn't use (drive_session)
- Test fixtures it doesn't need (HookRegistry, ToolRegistry)
- Domain-specific examples (context_warn, compaction, circuit breaker)
- CI gates tied to this repo's scripts (check_producer_consumer_contract.py)

---

## Classification: Universal vs. FA-Specific

### TIER 1: Universal principles (applicable to ANY project)

These are the real value of the skill. They should be front-and-center, expressed
in domain-independent language:

| Principle | Current framing | Universal framing |
|-----------|----------------|-------------------|
| Kill-check targets producer | "Kill-check targets the PRODUCER emit call" | "Kill-check targets the code that PRODUCES the observable effect, not the code that CONSUMES it" |
| Vacuous pass detection | "Before kill-check, verify the emit call site EXISTS" | "Before kill-check, verify the production call site EXISTS. If it was never written, the kill-check is vacuous" |
| Two-sided contract | "For every EventType, BOTH producer (emit) and consumer (handler)" | "For every observable contract (signal/API/event), BOTH the producer (code that creates it) and consumer (code that handles it) must be verified" |
| Path inventory | "For EventType claims, enumerate ALL production code paths that emit the event" | "For any observable behavior, enumerate ALL code paths that produce it. Testing one path does not prove others" |
| Matrix coverage gate | "For every flag combination... at least one test per combination" | "For every configuration combination that creates a distinct code path, at least one test per combination" |
| Dual-write consistency | "When the system writes to both EventLog and EventBus" | "When the system writes to multiple outputs (e.g., database + cache, log + event bus, file + network), every code path that writes to one must also write to the other" |
| C0 consumer-only trap | "C0 consumer-only tests for EventTypes are theater" | "Consumer-only tests prove the handler works GIVEN input, but do not prove the input is ever produced. They are theater without a paired producer test" |
| Composition root testing | "drive_session / real factories" | "Boot the real composition root (the entry point that wires all components together)" |
| Ranked oracles | "Event kind+fields → SessionOutcome → tool trajectory" | "Structured side effects → outcome codes → trajectories → call counts → filesystem → free text" |

### TIER 2: FA-specific but universally applicable as PATTERN

These are concrete examples of universal patterns. They should be presented as
illustrations, not as the rule itself:

| Pattern | FA example | Universal pattern |
|---------|-----------|-------------------|
| Two-sided contract | EventType ↔ ConsoleRenderer handler | Any producer-consumer pair: event emitter ↔ listener, API call ↔ handler, message publisher ↔ subscriber |
| Composition root | `drive_session` | The main loop / entry point that wires all components |
| Flag matrix | FeatureFlags(budget, compaction) | Any configuration/feature-flag system |
| Dual-write | EventLog + EventBus | Any system with multiple write destinations |
| Kill-check target | `output.emit(OutputEvent(type="X"))` | The code line that creates the observable effect |
| C0 consumer test | `ConsoleRenderer._handle_context_warn` | Any test that verifies a handler GIVEN input, without verifying the input is produced |

### TIER 3: Purely FA-specific (should be in examples/references only)

These are implementation details of this specific repo and have no place in the
universal rule text:

- `drive_session`, `fa.cli._cmd_run`, `fa run`, `fa chunk`
- `EventType`, `OutputEvent`, `EventBus`, `ConsoleRenderer`
- `EventLog`, `log.append`, `output.emit`
- `ContextBudget`, `HookRegistry`, `ToolRegistry`, `ProviderChain`
- `FeatureFlags`, `SessionState`, `SessionOutcome`
- `scripts/check_producer_consumer_contract.py`
- `tests/fixtures/session_wiring.py`
- ADR-11-I9, ADR-11-I5, ADR-10 (repo-specific ADRs)
- `compaction`, `context_warn`, `hook_deny`, `circuit_breaker`
- `session.db`, `events.jsonl`

---

## Structural Problem: Rule vs. Example Confusion

The current skill intertwines UNIVERSAL RULES with FA-SPECIFIC EXAMPLES in the
same paragraphs. An LLM agent reading the skill cannot easily distinguish between:

> "Kill-check targets the PRODUCER" (universal rule)

and

> "Kill-check: removing `output.emit(OutputEvent(type='context_warn'))` from
> coder_loop.py makes the test fail" (FA-specific example)

The agent internalizes both as equally normative. When working on a different
project, it will either:
1. Try to find `output.emit(OutputEvent(...))` in code that doesn't have it
2. Ignore the entire rule because the example doesn't apply
3. Apply the principle but with less confidence because it's tied to unfamiliar concepts

---

## Proposed Fix: Three-Layer Architecture

### Layer 1: Universal Rules (top of each section)

Express each principle in domain-independent language. No FA-specific symbols,
no FA-specific file paths, no FA-specific class names.

### Layer 2: Pattern Templates (middle)

Abstract patterns that can be instantiated for any project:

```text
PATTERN: Two-sided contract verification
For every [SIGNAL_TYPE] in the system:
  1. PRODUCER proof: Test exercises [PRODUCER_CODE] and asserts [SIGNAL] is produced
  2. CONSUMER proof: Test verifies [CONSUMER_CODE] handles [SIGNAL] correctly
  3. CONTRACT CHECK: Automated script verifies both sides exist for every [SIGNAL_TYPE]
```

### Layer 3: FA-Specific Examples (bottom, clearly marked)

Concrete examples from this repo that illustrate the patterns:

```text
EXAMPLE (FA observability):
  SIGNAL_TYPE = EventType (e.g., "context_warn", "hook_deny")
  PRODUCER_CODE = output.emit(OutputEvent(type="X")) in coder_loop.py
  CONSUMER_CODE = ConsoleRenderer._handle_X() in output.py
  CONTRACT CHECK = scripts/check_producer_consumer_contract.py
```

---

## Impact Assessment: Which Sections Need Work

| Section | Universality | Issue |
|---------|:---:|-------|
| §0 Two pyramids | ⚠️ | Examples (budget/compaction/hooks) are FA-specific. Pyramid concept is universal. |
| §1 Taxonomy | ⚠️ | `drive_session`, `fa`, `_cmd_*` are FA-specific. C0-C4 taxonomy is universal. |
| §2 Composition roots | ❌ | Entirely FA-specific table. L1-L3 levels are universal but examples are not. |
| §3 Anti-theater | ⚠️ | Items 1-2 (existence pre-check, kill-check on producer) are universal. Items 13-16 (two-sided contract, path inventory, dual-write) use FA-specific language. |
| §4 Flag/provider matrix | ⚠️ | Matrix concept universal. Examples (budget, compaction) are FA-specific. |
| §5 Type-honest fixtures | ❌ | Entirely FA-specific table (tool_calls, EventLog, HookRegistry, etc.) |
| §6 Ranked oracles | ⚠️ | Oracle ranking is universal. Specific oracle types (SessionOutcome, tool trajectory) are FA-specific. |
| §7 Trajectory and event assertions | ❌ | Entirely FA-specific code examples |
| §8 Two-sided contract | ❌ | **Most FA-specific section.** 6 paragraphs about EventType, OutputEvent, EventBus, ConsoleRenderer. The PRINCIPLE is universal; the framing is not. |
| §9 Path inventory | ❌ | Entirely about EventType emit paths in coder_loop.py. Principle is universal. |
| §10 Dual-write consistency | ⚠️ | Identifies the correct universal pattern (multiple write destinations) but immediately collapses into EventLog/EventBus specifics. |
| §11 Kill-check mechanics | ⚠️ | Producer vs. consumer framing is universal. `output.emit()`/`log.append()` specifics are not. |
| §12 C0 consumer-only trap | ⚠️ | The trap is universal. The example (context_warn handler) is not. |
| §13 Security boundaries | ⚠️ | Most boundaries are universal (sandbox, secrets, path containment). IntentGuard is FA-specific. |
| §14-15 Pyramid B, mutation | ✅ | Mostly universal |
| §16 Gold files | ❌ | Entirely FA-specific |
| §17 Naming, isolation, CI | ⚠️ | `just check` is FA-specific. Naming conventions are universal. |
| §18-19 Sibling skills, authority | ⚠️ | FA-specific skill names and ADR references |
| Decision points | ⚠️ | Some universal, some FA-specific |
| Output format | ⚠️ | Template is universal; specific fields (event:kind, outcome:stop_reason) are FA-specific |
| What CI / hooks validate | ❌ | Entirely FA-specific |
| Escalation | ⚠️ | Some universal, some FA-specific |
| Worked examples | ❌ | Entirely FA-specific |
| Invariants | ❌ | I-TW-14 through I-TW-19 are all framed in FA-specific language (EventType, EventLog, EventBus) |

**Summary:** ~30% universal, ~40% mixed (universal principle + FA-specific framing), ~30% purely FA-specific.

---

## Key Insight: The Skill Has a Scope Identity Crisis

The skill was ORIGINALLY designed as a universal rulebook for testing AI agent
harnesses. My rewrite added critical new principles (two-sided contracts, path
inventory, dual-write consistency, vacuous pass detection) but framed them
entirely in terms of THIS REPO's observability system.

The result is a skill that:
- Contains universally important principles that ANY project needs
- But expresses them so tied to FA's specific architecture that other projects
  can't use them without translation
- And contains so many FA-specific details that the universal principles are
  hard to extract

This is the same bug class as the producer-consumer gap: the PRINCIPLE (universal)
was implemented in a specific CONTEXT (FA observability), and the gap between
them wasn't verified.

---

## Recommendation

Split the skill into two documents:

1. **`tests-writing/SKILL.md`** — Universal principles, pattern templates, and
   abstract rules. No FA-specific symbols in the rule text. FA examples in
   clearly marked sidebars.

2. **`tests-writing/FA-EXAMPLES.md`** (or inline in SKILL.md) — Concrete FA
   examples that instantiate each universal pattern. This is where EventType,
   drive_session, EventLog, etc. live.

The universal document should pass this test: an agent working on a completely
different project (a Rust CLI tool, a data pipeline, a web API) can read it and
know how to apply every principle without needing to understand FA's architecture.
