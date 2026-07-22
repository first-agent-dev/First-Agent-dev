"""Kill-check tests for S6: Type EventLog.append(kind: LogKind) + compaction_warning producer.

Verifies:
1. EventLog.append accepts kind: LogKind (not kind: str)
2. TraceEvent.kind remains str (JSONL round-trip compatibility)
3. compaction_warning producer exists in coder_loop.py
4. compaction_warning fires in BOTH compaction-enabled and compaction-disabled paths
5. TODO comment present in spawn_subagent.py for dynamic kind
"""

from __future__ import annotations

import inspect
from pathlib import Path

from fa.inner_loop import EventLog

CODER_LOOP_PATH = Path("src/fa/inner_loop/coder_loop.py")
SPAWN_SUBAGENT_PATH = Path("src/fa/inner_loop/tools/spawn_subagent.py")


# ── Kill-check 1: EventLog.append kind parameter is LogKind ─────────


def test_append_kind_parameter_is_log_kind() -> None:
    """EventLog.append's kind parameter must be typed as LogKind, not str."""
    sig = inspect.signature(EventLog.append)
    param = sig.parameters.get("kind")
    assert param is not None, "kind parameter not found"
    annotation_str = str(param.annotation)
    assert "LogKind" in annotation_str, f"Expected LogKind in kind annotation, got: {annotation_str}"
    assert param.annotation is not str, "kind parameter is still typed as str — should be LogKind"


# ── Kill-check 2: TraceEvent.kind is still str ─────────────────────


def test_trace_event_kind_is_str() -> None:
    """TraceEvent.kind must remain str for JSONL round-trip compatibility."""
    import dataclasses

    from fa.inner_loop.state import TraceEvent

    kind_field = None
    for f in dataclasses.fields(TraceEvent):
        if f.name == "kind":
            kind_field = f
            break
    assert kind_field is not None, "kind field not found on TraceEvent"
    # With `from __future__ import annotations`, field.type is a string
    type_str = str(kind_field.type)
    assert type_str == "str", f"TraceEvent.kind should be str for JSONL round-trip, got: {type_str}"


# ── Kill-check 3: compaction_warning producer exists in source ──────


def test_compaction_warning_producer_in_source() -> None:
    """coder_loop.py must contain a log.append(kind='compaction_warning', ...) call."""
    content = CODER_LOOP_PATH.read_text(encoding="utf-8")
    assert 'kind="compaction_warning"' in content, "compaction_warning producer not found in coder_loop.py"


# ── Kill-check 4: compaction_warning content includes compaction_enabled field ─


def test_compaction_warning_content_includes_enabled() -> None:
    """The compaction_warning event content must include 'compaction_enabled' field."""
    content = CODER_LOOP_PATH.read_text(encoding="utf-8")
    # Find the compaction_warning emit block
    assert '"compaction_enabled"' in content, (
        "compaction_warning content must include compaction_enabled field "
        "for observability of both enabled and disabled cases"
    )


# ── Kill-check 5: compaction_warning fires before compaction_enabled branch ─


def test_compaction_warning_before_compaction_branch() -> None:
    """In the source code, the compaction_warning emit must appear BEFORE
    the `if not compaction_enabled:` branch so it fires in BOTH cases."""
    content = CODER_LOOP_PATH.read_text(encoding="utf-8")
    warning_pos = content.find('kind="compaction_warning"')
    branch_pos = content.find("if not compaction_enabled:")
    assert warning_pos > 0, "compaction_warning emit not found"
    assert branch_pos > 0, "if not compaction_enabled branch not found"
    assert warning_pos < branch_pos, (
        f"compaction_warning (pos {warning_pos}) must appear BEFORE if not compaction_enabled branch (pos {branch_pos})"
    )


# ── Kill-check 6: typed dynamic kind in spawn_subagent.py ─────────


def test_spawn_subagent_dynamic_kind_is_typed() -> None:
    """The dynamic completion kind is constrained to the LogKind union."""
    content = SPAWN_SUBAGENT_PATH.read_text(encoding="utf-8")
    assert "kind: LogKind" in content
    assert '"subagent_spawn_done"' in content
    assert '"subagent_spawn_fail"' in content


# ── Kill-check 7: EventLog.append rejects non-LogKind at runtime ──
# (Design intent: pyright catches this at lint time; runtime allows
# any string because TraceEvent.kind: str. This test verifies the
# type annotation is LogKind, which is the enforcement mechanism.)


def test_log_kind_import_in_state() -> None:
    """state.py must import LogKind from fa.output for the type annotation."""
    content = Path("src/fa/inner_loop/state.py").read_text(encoding="utf-8")
    assert "from fa.output import LogKind" in content, (
        "state.py must import LogKind for EventLog.append kind parameter typing"
    )
