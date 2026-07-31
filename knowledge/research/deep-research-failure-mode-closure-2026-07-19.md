# Deep Research: Comprehensive Failure-Mode Closure for String-Typed Identifiers and Type Erasure in AI-Developed Codebases

**Date**: 2026-07-19
**Context**: PR #53 observability work + FA provider chain. Two failure modes:
  1. **F-2**: String-typed identifiers (30 log kinds, 14 event types) allow typos = silent bugs
  2. **F-5**: `Any | None` type erasure (9 fields) forces 19 getattr workarounds with duplicated defaults
**Goal**: Find the comprehensive pattern — not just patch current instances, but structurally prevent recurrence when AI agents add new features.

---

## Part 1: The Failure Mode — "Stringly-Typed Events" in Agent-Written Code

### The Problem Anatomy

The FA codebase has **three independent string-typed event channels** with zero compile-time consistency enforcement:

| Channel | Identifier Type | Count | Producers | Consumers | Type Safety |
|---------|----------------|-------|-----------|-----------|-------------|
| EventLog | `kind: str` | 30 | `log.append()` | `fa stats` (elif chains) | ❌ None |
| EventBus | `type: str` (via `EventType = Literal[...]`) | 14 | `output.emit()` | `ConsoleRenderer._handle_*()` | ✅ Literal type |
| Tool names | `tool_name: str` | ~15 | `state.record_tool_call()` | `fa stats`, hooks | ❌ None |

When an AI agent adds a new feature (say, a "document_library" tool for Mistral Conversations API), it must:
1. Add `kind="document_library_start"` to `log.append()` calls ← no compile-time check
2. Add `elif kind == "document_library_start":` parser to `fa stats` ← no compile-time check
3. Optionally add `type="document_library_start"` to `output.emit()` ← EventType Literal catches typos
4. Optionally add `_handle_document_library_start()` to ConsoleRenderer ← contract check validates

Step 1 and 2 are the **unprotected surface**. The agent can introduce a typo in step 1 or forget step 2 entirely, and nothing catches it until a human notices `fa stats` is missing data.

### Why This Is Especially Dangerous in AI-Written Code

From the [AgentSwarms analysis of Pydantic as contract layer](https://agentswarms.fyi/blog/pydantic-the-contract-layer-of-agentic-ai):

> "Once you start seeing the model's output as untrusted input, you notice the same boundary repeating all over an agent. It's not one feature — it's a posture you apply everywhere untyped data tries to get in."

The key insight: **AI agents treat existing code patterns as implicit specifications**. If they see `kind="compaction_stage2_done"` they'll replicate the pattern with `kind="document_library_done"` — but they have no way to know this string must also appear in `stats.py`, `check_log_kind_contract.py`, and `CONSOLE_MIRROR_KINDS`. Each new string is a potential orphan.

The [Type-Safe Event Management pattern](https://mohammadshaker.com/en/tech/spatialx-frontend-explore-08-type-safe-event-management-enums) quantified this in a real system:

| Metric | Before (stringly-typed) | After (typed events) |
|--------|------------------------|---------------------|
| Event typo errors/month | 23 | 0% |
| Debugging time | 45 min | 5 min |
| IDE autocomplete | No | Yes |

### The Current Plan's Gap

The plan adds `LogKind = Literal[...]` + a contract check script. This is **necessary but not sufficient**. Here's why:

1. **Literal types are open sets** — adding a new kind requires manually updating the Literal, the producer, AND the consumer. The contract check validates AFTER the fact, not at construction time.

2. **Payload types are `dict[str, Any]`** — even if the kind string is correct, the content payload is untyped. A `compaction_stage2_done` event with `{"tokens_before": "not_a_number"}` silently corrupts stats.

3. **The producer-consumer mapping is undocumented** — there's no canonical declaration that `kind="compaction_stage2_done"` MUST have `tokens_before: int` and `tokens_after: int` in its content dict.

4. **No exhaustive matching** — `fa stats` uses `elif` chains with no `else: warn_about_unknown_kind()`. Unknown kinds silently pass through.

---

## Part 2: The Elegant Solution — Discriminated Union Events with Typed Payloads

### The Pattern: Parse, Don't Validate (Alexis King, 2019)

The foundational principle from [King's essay](https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/) and the [DevIQ summary](https://deviq.com/principles/parse-dont-validate/):

> "Parsing is just validation with a return value — and that return value proves you did the work. Validation discards all proof of work: it returns a boolean or throws an exception, but leaves the data in its original untyped form. Parsing preserves the proof by returning a new type."

Applied to events: **instead of `kind: str` + `content: dict`, parse the event into a typed variant that CANNOT represent invalid combinations.**

### The Pattern: Make Illegal States Unrepresentable (Yaron Minsky)

From the [DevIQ principle](https://deviq.com/principles/make-illegal-states-unrepresentable/) and the [encyclopedia of agentic coding](https://aipatternbook.com/make-illegal-states-unrepresentable):

> "When illegal states are unrepresentable, entire categories of bugs are eliminated at design time rather than discovered at runtime. Code becomes shorter because validation logic and defensive branches disappear."

The [Go type-driven design article](https://dev.to/gabrielanhaia/type-driven-domain-design-in-go-encoding-invariants-at-compile-time-497i) shows the concrete mechanism:

> "The boundary is the interesting part. Most codebases sprinkle validation across every layer 'just in case.' With parse-don't-validate, validation happens once, at the edge, and the type carries the result inward. Twelve files of defensive checks become one constructor."

### The Pattern: Discriminated Unions for Event Routing

The [Pydantic discriminated unions](https://docs.pydantic.dev/latest/concepts/unions/) pattern and the [MLflow feature request](https://github.com/mlflow/mlflow/issues/19551) demonstrate the production pattern:

```python
from typing import Literal, Annotated, Union
from pydantic import BaseModel, Field


class CompactionStage2Done(BaseModel):
    kind: Literal["compaction_stage2_done"]
    tokens_before: int
    tokens_after: int


class CompactionStage2Error(BaseModel):
    kind: Literal["compaction_stage2_error"]
    error: str


# The discriminator field routes parsing automatically
LogEvent = Annotated[
    Union[CompactionStage2Done, CompactionStage2Error, ...],
    Field(discriminator="kind"),
]
```

The [TypeScript discriminated unions for domain events](https://medium.com/@2nick2patel2/typescript-discriminated-unions-for-domain-events-eliminate-impossible-states-at-scale-ca78199f6680) article makes the maintenance argument:

> "Every consumer switch that claims to handle DomainEvent fails to compile until updated. That's how you prevent silent drift."

And the [AgentSwarms Pydantic article](https://agentswarms.fyi/blog/pydantic-the-contract-layer-of-agentic-ai) adds the AI-specific insight:

> "A malformed tool call — the right action name with the wrong arguments — cannot reach your execution layer, because it never validates into the corresponding model. The agent's intent and its arguments are checked together, as a unit."

### The Pattern: Fallback Catch-All for Evolving APIs

The [Pydantic v2 discriminated unions + fallbacks](https://www.lowlevelmanager.com/2025/05/pydantic-v2-discriminated-unions.html) pattern handles the real-world need for extensibility:

```python
class KnownLogEvent(BaseModel):
    kind: str  # unconstrained — catches unknown kinds
    content: dict[str, Any]


LogEvent = Annotated[
    Union[
        KnownDiscriminatedEvents,  # typed variants with Literal kinds
        KnownLogEvent,  # fallback for unknown kinds
    ],
    Field(union_mode="left_to_right"),
]
```

This gives you **type safety for known events AND graceful degradation for new/unknown events**, which is exactly what an evolving agent codebase needs.

---

## Part 3: The Comprehensive Solution for FA

### 3A: Replace `kind: str` + `content: dict` with Discriminated Union

**Current state** (two uncorrelated strings):
```python
@dataclass(frozen=True, slots=True)
class TraceEvent:
    kind: str  # 30 possible values, untyped
    content: Mapping[str, object]  # open schema, untyped
```

**Target state** (discriminated union with typed payloads):

```python
# src/fa/output.py — the canonical event schema registry

from typing import Literal, Annotated, Union
from pydantic import BaseModel, Field

# ── Typed event payloads (one per log kind) ──────────────────────────


class RunStartedPayload(BaseModel):
    kind: Literal["run_started"]
    role: str
    max_turns: int
    temperature: float


class UsagePayload(BaseModel):
    kind: Literal["usage"]
    input_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int
    output_tokens: int


class CompactionStage2DonePayload(BaseModel):
    kind: Literal["compaction_stage2_done"]
    tokens_before: int
    tokens_after: int


class CompactionStage2ErrorPayload(BaseModel):
    kind: Literal["compaction_stage2_error"]
    error: str


class ContextBudgetWarnPayload(BaseModel):
    kind: Literal["context_budget_warn"]
    action: str
    ratio: float
    message: str


# ... one class per log kind (30 total) ...

# ── Fallback for unknown/future kinds ────────────────────────────────


class UnknownLogPayload(BaseModel):
    kind: str  # unconstrained
    content: dict[str, Any]


# ── The discriminated union ──────────────────────────────────────────

KnownLogEvent = Annotated[
    Union[
        RunStartedPayload,
        UsagePayload,
        CompactionStage2DonePayload,
        CompactionStage2ErrorPayload,
        ContextBudgetWarnPayload,
        # ... all 30 ...
    ],
    Field(discriminator="kind"),
]

LogEvent = Annotated[
    Union[
        KnownLogEvent,  # typed — validates payload shape
        UnknownLogPayload,  # fallback — unknown kinds still parse
    ],
    Field(union_mode="left_to_right"),
]
```

### Why This Closes ALL the Gaps

| Gap | How discriminated union closes it |
|-----|----------------------------------|
| **Typo in kind string** | `kind: Literal[...]` catches typos at write time. Pylance won't autocomplete `"compaction_stage2_dne"`. |
| **Missing payload field** | `CompactionStage2DonePayload` requires `tokens_before: int`. Omitting it is a type error. |
| **Wrong payload type** | `tokens_before: int` rejects `{"tokens_before": "not_a_number"}`. |
| **Missing stats parser** | The `LogEvent` union IS the parser. Adding a new kind without a `fa stats` handler still works — `UnknownLogPayload` catches it. But `fa stats` can emit a WARNING: "unparsed event kind: document_library_start". |
| **Producer-consumer drift** | Adding a new kind to the union requires updating `KnownLogEvent`. Pylance then flags every `match` / `isinstance` / `elif` chain that doesn't handle it. |
| **Console-mirror gap** | Each payload class can declare `is_console_mirror: ClassVar[bool]`. The contract check reads this from the class definition — single source of truth. |
| **AI agent adding a feature** | The agent must: (1) define a new `*Payload` class, (2) add it to `KnownLogEvent`, (3) handle it in consumers. Pylance enforces (2) and (3). |

### 3B: The Same Pattern for OutputEvent

Currently `OutputEvent` has `type: EventType` (Literal) but `data: dict[str, Any]`. Apply the same discriminated union:

```python
class SessionStartData(BaseModel):
    type: Literal["session_start"]
    model: str
    role: str
    family: str = ""


class CompactionEndData(BaseModel):
    type: Literal["compaction_end"]
    stage: int
    ok: bool
    tokens_before: int = 0
    tokens_after: int = 0
    error: str = ""


# ... one class per EventType ...

ConsoleEvent = Annotated[
    Union[SessionStartData, CompactionEndData, ...],
    Field(discriminator="type"),
]
```

Now the `ConsoleRenderer._handle_compaction_end(e)` method gets `e: CompactionEndData` — it can access `e.stage`, `e.ok`, `e.tokens_before` with type safety. No more `e.data.get("stage", "?")` with string fallbacks.

### 3C: Exhaustive Matching via Protocol

The [mypy documentation on tagged unions](https://mypy.readthedocs.io/en/stable/literal_types.html) shows how `match` statements (Python 3.10+) provide exhaustive checking:

```python
def parse_log_event(event: LogEvent) -> None:
    match event:
        case RunStartedPayload(role=role, max_turns=mt):
            ...
        case UsagePayload(input_tokens=it, output_tokens=ot):
            ...
        case UnknownLogPayload(kind=kind):
            logger.warning("unparsed event kind: %s", kind)
        # mypy/pyright WARN if any KnownLogEvent variant is missing
```

For Python 3.9 compat, `isinstance` checks with the typed payloads give the same narrowing:

```python
if isinstance(event, CompactionStage2DonePayload):
    # event.tokens_before is int — no dict access, no .get()
    stats.add_compaction(event.tokens_before, event.tokens_after)
```

---

## Part 4: Extending the Type-Erasure Fix (F-5) — Beyond Just Typing the Fields

### The Deeper Problem: Lazy Initialization as Type Erasure

The 9 `Any | None` fields on `SessionState` exist because of Python's **lazy initialization pattern** — the fields are `None` at construction, then filled in during `__post_init__`. This is the "optional field roulette" pattern that the [TypeScript discriminated unions article](https://medium.com/@2nick2patel2/typescript-discriminated-unions-for-domain-events-eliminate-impossible-states-at-scale-ca78199f6680) warns about:

> "If a field is required for an event's meaning, make it required in the type. Consumers stop doing `if (!ev.orderId) return;` and your system stops hiding bugs."

### The Pattern: Builder Protocol / Phased Construction

Instead of one mutable dataclass with 9 optional fields, use a **phased construction** pattern:

```python
from __future__ import annotations
from typing import Protocol, TYPE_CHECKING

# ── Phase 1: Raw state (what tests construct) ────────────────────────


@dataclass
class SessionState:
    """Immutable-core + lazy-extensions pattern.

    Core fields are always present. Extensions are phased in
    during construction by cli.py or the test factory.
    """

    workspace_root: Path
    run_id: str
    log: EventLog
    observations: list[str] = field(default_factory=list)
    turn: int = 0
    subagent_spawns: int = 0

    # Extensions — set by the factory, never None in production.
    # Typed as Optional because __post_init__ fills them gradually,
    # but the factory guarantees they're set before the session starts.
    _extensions: _SessionExtensions = field(default_factory=_SessionExtensions, init=False, repr=False)

    @property
    def feature_flags(self) -> FeatureFlags:
        """Always available — factory guarantees initialization."""
        val = self._extensions.feature_flags
        if val is None:
            raise RuntimeError(
                "feature_flags not initialized — use make_session_state() "
                "or ensure SessionState.__post_init__ completed"
            )
        return val

    @property
    def output_bus(self) -> EventBus:
        """Always available — factory guarantees initialization."""
        val = self._extensions.output_bus
        if val is None:
            raise RuntimeError("output_bus not initialized — set via state.output_bus = bus or pass in constructor")
        return val

    # ... same pattern for all 9 fields ...


@dataclass
class _SessionExtensions:
    """Internal holder for lazily-initialized extensions."""

    feature_flags: FeatureFlags | None = None
    output_bus: EventBus | None = None
    transaction: Transaction | None = None
    # ... etc
```

The key insight: **the properties return non-Optional types, but the backing store is Optional**. This means:
- Pylance sees `state.feature_flags` as `FeatureFlags` (not `FeatureFlags | None`)
- No `getattr(state, "feature_flags", None)` needed
- If the lazy init fails, the RuntimeError is explicit: "feature_flags not initialized — use make_session_state()"
- Tests that need partial state can still construct `_SessionExtensions(feature_flags=...)` manually

### Why Properties Beat Direct Fields

| Approach | Type checker sees | `getattr` needed? | Fails how? |
|----------|------------------|-------------------|------------|
| `field: Any \| None` | `Any` | Yes (19 sites) | Silently None |
| `field: FeatureFlags \| None` | `FeatureFlags \| None` | Maybe (isinstance check) | `AttributeError` on `.context_budget_enabled` |
| `@property → FeatureFlags` | `FeatureFlags` (non-Optional!) | **No** | `RuntimeError` with actionable message |

The property pattern is the **Parse, Don't Validate** of lazy initialization:
- Validation: `if state.feature_flags is not None: state.feature_flags.context_budget_enabled` — checks every time, discards proof
- Parsing (property): `state.feature_flags.context_budget_enabled` — one-time init, type carries the proof

---

## Part 5: The Unified Pattern — "Typed Boundary, Open Interior"

### The Rule

> **Every string identifier that crosses a module boundary MUST be a Literal-typed field on a discriminated union variant. Interior code operates on the typed variant, never on raw strings.**

This is the agentic coding version of [Parse, Don't Validate](https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/): parse at the boundary (EventLog.append, EventBus.emit, SessionState.__post_init__), and let the type system enforce correctness everywhere else.

### Concrete Application to FA

| Boundary | Current | Target |
|----------|---------|--------|
| `EventLog.append(kind=...)` | `kind: str` | `kind: LogKind` (Literal) + `content` validated against `LogEvent` discriminated union |
| `EventBus.emit(OutputEvent(type=...))` | `type: EventType` (Literal) + `data: dict` | `type: EventType` + `data` typed per variant |
| `SessionState.__post_init__` | 9 `Any \| None` fields | Properties returning non-Optional types |
| `fa stats` parsing | `elif kind == "..."` chains | `isinstance(event, CompactionStage2DonePayload)` with type narrowing |
| `ConsoleRenderer._handle_*` | `e.data.get("field", default)` | `e.stage`, `e.ok` — direct typed access |
| New feature by AI agent | Must know to update 4+ files | Must define a `*Payload` class + add to union. Pylance catches omissions. |

### The Contract Check Evolution

The contract check evolves from a regex-based AST scanner to a **type-system-aware validator**:

```python
# scripts/check_event_contracts.py

# 1. Extract all variants from KnownLogEvent union
# 2. For each variant, verify:
#    a. Has at least one C1 test that constructs it
#    b. Has a fa stats parser (or is in UNPARSED_KINDS allowlist)
#    c. If is_console_mirror=True, has a corresponding OutputEvent variant
# 3. For OutputEvent variants, verify ConsoleRenderer handler exists
# 4. Verify no raw `kind="..."` strings that aren't in the union
```

This is fundamentally more robust than regex because the **type definitions ARE the contract**. Adding a new event type means adding a new class to the union, and the contract check validates the entire lifecycle.

### Why This Matters Specifically for AI-Written Code

From the [Parse Don't Validate Python adaptation](https://www.ricardodecal.com/opinions/parse-don-t-validate-in-python/):

> "I find [parse-don't-validate] improves code quality and is a good convention to use when heavily using coding agents, since it eliminates entire categories of mistakes."

The [AgentSwarms article](https://agentswarms.fyi/blog/pydantic-the-contract-layer-of-agentic-ai) extends this:

> "Once a validator's error can become a prompt, its wording matters. 'Invalid input' helps no one. 'rating must be an integer from 1 to 10; you returned 11' tells the model exactly how to correct itself on the next pass. Your error strings are now part of your prompt engineering."

In the FA context: when an AI agent writes a new feature and the discriminated union rejects its event payload, the **Pydantic validation error tells the agent exactly what's wrong**:

```
ValidationError: CompactionStage2DonePayload
  tokens_before: Input should be a valid integer, got 'not_a_number' [type=int_type]
```

This is dramatically more helpful than the current failure mode: silently writing `kind="compaction_stage2_dne"` to the audit log and wondering why `fa stats` shows no compaction data.

---

## Part 6: Implementation Strategy — Phased Migration

### Phase A: Define the Typed Event Schema (Non-Breaking)

1. Create `src/fa/events.py` with the `*Payload` classes and `LogEvent` discriminated union
2. Keep `TraceEvent.kind: str` and `EventLog.append(kind: str, ...)` as-is
3. Add a **parser function** that converts `TraceEvent` → `LogEvent`:
   ```python
   def parse_trace_event(raw: TraceEvent) -> LogEvent:
       """Parse a raw TraceEvent into a typed LogEvent variant.
       Unknown kinds fall through to UnknownLogPayload.
       """
       ...
   ```
4. `fa stats` uses `parse_trace_event()` instead of raw `elif kind ==` chains
5. Contract check validates the union is complete

### Phase B: Migrate Producers (Breaking Change)

1. Add `EventLog.append_typed(event: LogEvent)` as the new API
2. Migrate producers one module at a time
3. Deprecate `EventLog.append(kind=...)`
4. After full migration, make `append()` private

### Phase C: Migrate SessionState (Breaking Change)

1. Add properties returning non-Optional types
2. Migrate consumer sites from `getattr` to direct property access
3. Remove the `Any | None` field declarations

### Phase D: Migrate OutputEvent (Breaking Change)

1. Add typed `*Data` classes per EventType
2. Migrate `ConsoleRenderer._handle_*` methods to typed access
3. Deprecate `OutputEvent.data: dict[str, Any]`

---

## References

1. Yaron Minsky, "Make Illegal States Unrepresentable" — [DevIQ](https://deviq.com/principles/make-illegal-states-unrepresentable/)
2. Alexis King, "Parse, Don't Validate" (2019) — [Original](https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/) / [DevIQ summary](https://deviq.com/principles/parse-dont-validate/)
3. Type-Safe Event Management with TypeScript Enums — [mohammadshaker.com](https://mohammadshaker.com/en/tech/spatialx-frontend-explore-08-type-safe-event-management-enums)
4. Pydantic: The Contract Layer Your Agents Are Missing — [AgentSwarms](https://agentswarms.fyi/blog/pydantic-the-contract-layer-of-agentic-ai)
5. Pydantic v2 Discriminated Unions + Fallbacks — [lowlevelmanager.com](https://www.lowlevelmanager.com/2025/05/pydantic-v2-discriminated-unions.html)
6. TypeScript Discriminated Unions for Domain Events — [Medium](https://medium.com/@2nick2patel2/typescript-discriminated-unions-for-domain-events-eliminate-impossible-states-at-scale-ca78199f6680)
7. Type-Driven Domain Design in Go — [dev.to](https://dev.to/gabrielanhaia/type-driven-domain-design-in-go-encoding-invariants-at-compile-time-497i)
8. Pydantic Discriminated Unions Documentation — [docs.pydantic.dev](https://docs.pydantic.dev/latest/concepts/unions/)
9. mypy Tagged Unions with Literal Types — [mypy docs](https://mypy.readthedocs.io/en/stable/literal_types.html)
10. Parse, Don't Validate in Python — [ricardodecal.com](https://www.ricardodecal.com/opinions/parse-don-t-validate-in-python/)
11. MLflow Feature Request: Discriminated Unions for Type Narrowing — [GitHub](https://github.com/mlflow/mlflow/issues/19551)
12. ag-ui Protocol: Events as Discriminated Unions — [docs.ag-ui.com](https://docs.ag-ui.com/sdk/python/core/events)
