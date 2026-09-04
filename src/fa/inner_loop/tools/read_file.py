from __future__ import annotations

import importlib
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fa.inner_loop.artifacts import ArtifactStore
from fa.inner_loop.projection import render_tool_payload
from fa.inner_loop.registry import DEFAULT_TOOL_CONTEXT_BYTES, ToolResult, ToolSpec
from fa.inner_loop.state import SessionState
from fa.inner_loop.tools.base import (
    optional_int,
    optional_string,
    resolve_workspace_path,
)

logger = logging.getLogger(__name__)


def _read_pdf_text(path: Path) -> str | None:
    """Try to extract text from PDF via pymupdf (fitz), fallback to pdfminer, else None.

    Production-grade: graceful degradation, not crash, WARNING logged.
    For user data 01-11.pdf with table of reviews, pymupdf extracts 2282 chars per page.
    """
    # Try pymupdf (fitz) first - fastest, best for text tables
    try:
        fitz = importlib.import_module("fitz")

        doc = fitz.open(str(path))
        texts = []
        for page in doc:
            try:
                texts.append(page.get_text("text"))
            except Exception:  # noqa: BLE001, S112 # graceful degradation per Phase 0.5, failure-observable WARNING
                continue
        doc.close()
        full = "\n".join(texts)
        if len(full.strip()) > 50:
            return full
    except ImportError:
        # pymupdf is optional; fall through to pdfminer/pypdf fallback extractors.
        pass
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        logger.warning(f"pymupdf failed for {path}: {exc}")

    # Try pdfminer.six as fallback
    try:
        pdfminer_high_level = importlib.import_module("pdfminer.high_level")

        text = str(pdfminer_high_level.extract_text(str(path)))
        if text and len(text.strip()) > 50:
            return text
    except ImportError:
        # Optional dependency not installed; continue to next PDF fallback.
        pass
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        logger.warning(f"pdfminer failed for {path}: {exc}")

    # Try pypdf as last fallback
    try:
        pypdf = importlib.import_module("pypdf")

        reader = pypdf.PdfReader(str(path))
        texts = []
        for page in reader.pages:
            try:
                texts.append(page.extract_text() or "")
            except Exception:  # noqa: BLE001, S112 # graceful degradation per Phase 0.5, failure-observable WARNING
                continue
        full = "\n".join(texts)
        if len(full.strip()) > 50:
            return full
    except ImportError:
        # pypdf is optional; if unavailable, silently fall through to return None.
        pass
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        logger.warning(f"pypdf failed for {path}: {exc}")

    return None


def _read_file_text(path: Path) -> str | ToolResult:
    """PDF-aware text read (S12.7 extraction; behavior unchanged).

    PDF via dedicated extractor (pymupdf → pdfminer → pypdf fallback chain,
    graceful degradation per Phase 0.5) with a utf-8 last resort; every
    other file is a plain utf-8 read. Returns the text or a structured
    ``read_failed`` fail.
    """
    if path.suffix.lower() == ".pdf":
        pdf_text = _read_pdf_text(path)
        if pdf_text is not None:
            return pdf_text
        try:
            # Fallback try utf-8 read (may fail)
            return path.read_text(encoding="utf-8")
        except (OSError, PermissionError, ValueError) as exc:
            return ToolResult.fail(
                "read_failed",
                f"PDF extraction failed and utf-8 read failed for {path}: {exc}. "
                f"Install pymupdf (pip install pymupdf) for PDF support.",
                retryable=True,
            )
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, PermissionError, ValueError) as exc:
        return ToolResult.fail("read_failed", str(exc), retryable=True)


def _validated_window(start_line: int | None, end_line: int | None, total_lines: int) -> tuple[int, int] | None:
    """S12.7 (CT7): shared line-window semantics for file AND artifact reads.

    Returns the validated ``(start, end)`` (1-based, inclusive) or ``None``
    when the window is invalid — identical semantics in both branches so
    they cannot drift apart.
    """
    start = 1 if start_line is None else start_line
    end = total_lines if end_line is None else end_line
    if start < 1 or end < start:
        return None
    return start, end


# S12.7 (CT3, R16 rendered-measure rule): the binary framing rule is the
# MEASURE — len(render_tool_payload(result).encode()), the exact quantity
# projection compares — never a magic raw-byte count (JSON escaping adds
# ~1B per newline plus quote/backslash escapes; a 32,000B raw window can
# render >32,768B). Budget source: the single-sourced ceiling constant; the
# scatter-table pin (tests/test_s127_budget.py) holds registered == default
# for fs_read_file, so handler and projection cannot drift.
_FRAME_WHOLE_WINDOW_PROMISE = "windows of <=~750 lines (~30,000B) are typically returned whole"
# projection appends "\n\n[artifact: tool-result-<16hex>]" AFTER clipping the
# elided block to max_bytes; reserve keeps the visible total tight.
_ARTIFACT_FOOTER_RESERVE = 128


def _rendered_bytes(result_dict: Mapping[str, object]) -> int:
    return len(render_tool_payload(result_dict).encode("utf-8"))


def _file_frame_header(rel: str, total_lines: int, start: int, end: int, text_bytes: int) -> str:
    end = min(end, total_lines)  # a window never extends past EOF
    if start == 1 and end == total_lines:
        return f"[File: {rel} — {total_lines} lines, {text_bytes} bytes — showing ALL]"
    above, below = start - 1, total_lines - end
    return (
        f"[File: {rel} — {total_lines} lines total — showing {start}-{end} — "
        f"{above} above, {below} below — continue with start_line={end + 1} — "
        f"{_FRAME_WHOLE_WINDOW_PROMISE}]"
    )


def _artifact_frame_header(artifact_id: str, total_lines: int, start: int, end: int) -> str:
    end = min(end, total_lines)  # a window never extends past EOF
    if start == 1 and end == total_lines:
        return f"[Artifact: {artifact_id} — {total_lines} lines — showing ALL]"
    above, below = start - 1, total_lines - end
    return (
        f"[Artifact: {artifact_id} — {total_lines} lines total — showing {start}-{end} — "
        f"{above} above, {below} below — continue with start_line={end + 1} "
        f"(artifact_id={artifact_id})]"
    )


def _used_bounds(start_line: int | None, end_line: int | None, total: int) -> tuple[int, int]:
    """Effective 1-based inclusive window after None-defaulting (pre-validated)."""
    return (
        1 if start_line is None else start_line,
        total if end_line is None else end_line,
    )


def _framed_or_raw(base_payload: dict[str, object], frame: str, summary: str) -> ToolResult:
    """CT3 measure-then-handoff: return the framed result iff its RENDERED
    size fits the ceiling; otherwise the RAW unframed payload (window fields
    kept) so projection's ``_read_head_frame`` builds the T3 frame."""
    framed = dict(base_payload)
    framed["frame"] = frame
    if _rendered_bytes(framed) <= DEFAULT_TOOL_CONTEXT_BYTES:
        return ToolResult.ok(summary, result=framed)
    return ToolResult.ok(summary, result=base_payload)


def _read_head_frame(value: Any, max_bytes: int) -> str:
    """T3 elide adapter (S12.7 CT3; AP-006 named adapter, RD-2 chokepoint).

    Receives the RAW (unframed) read payload when the rendered result exceeds
    the ceiling; produces the model-visible T3 frame:

    - FILE payloads (``path``/``rel_path``): TRUNCATED header anchored at the
      REQUESTED window start when the payload carries one (a head-from-line-1
      frame for a 5000-9000 request would actively mislead — R16), the shown
      range, the resume call, and the structure steer
      (fs_search output_mode='outline' — delivered with this slice's PR
      together with S7; single-PR delivery makes the steer valid).
    - ARTIFACT payloads (``artifact_id``): same anchoring, header names the
      artifact, resume via windowed artifact read — NO outline steer.
    - Targets ``max_bytes - _ARTIFACT_FOOTER_RESERVE`` so projection's
      appended ``[artifact: …]`` footer keeps the visible total tight;
      projection's ``_clip_utf8`` stays the runtime belt-and-suspenders.
    """
    if not isinstance(value, Mapping):
        return str(value)
    content = str(value.get("content", ""))
    lines = content.splitlines()
    total_lines = int(value.get("line_count", len(lines)))
    artifact_id = value.get("artifact_id")
    rel = value.get("rel_path") or value.get("path", "<unknown>")

    # Display-numbering anchor: when the payload is a windowed read, content
    # line 1 IS window start (the handler hands off the window SLICE with
    # line_count = file total), so the anchor numbers lines for display —
    # it must never index into the slice.
    anchor_line = 1
    raw_start = value.get("start_line")
    if isinstance(raw_start, int) and raw_start >= 1:
        anchor_line = raw_start
    offset = anchor_line - 1

    usable = max(0, max_bytes - _ARTIFACT_FOOTER_RESERVE)
    if artifact_id is not None:
        header = (
            f"[Artifact: {artifact_id} — {total_lines} lines total — TRUNCATED: "
            f"showing lines {anchor_line}-{{end}} — {{below}} below — "
            f"continue with start_line={{next}} (artifact_id={artifact_id})]"
        )
    else:
        header = (
            f"[File: {rel} — {total_lines} lines total — TRUNCATED: "
            f"showing lines {anchor_line}-{{end}} — {{below}} below — "
            f"continue with start_line={{next}} — narrow windows "
            f"(<=~750 lines) return whole — structure: "
            f"fs_search(output_mode='outline', path={rel})]"
        )
    if not lines:
        return f"[File: {rel} — 0 lines — empty]"
    header_bytes = len(header.encode("utf-8"))
    body_budget = usable - header_bytes - 1  # 1 = the header/body newline
    shown: list[str] = []
    used = 0
    end_line = anchor_line - 1
    for i, line in enumerate(lines):
        cost = len(line.encode("utf-8")) + 1  # + trailing newline
        if shown and used + cost > body_budget:
            break
        shown.append(line)  # always keep >=1 line; projection clips as backstop
        used += cost
        end_line = offset + i + 1
        if used >= body_budget:
            break
    below = max(0, total_lines - end_line)
    header = header.format(end=end_line, below=below, next=end_line + 1)
    return header + "\n" + "\n".join(shown)


def _artifact_stores(session: SessionState) -> list[ArtifactStore]:
    """The session-owned artifact roots an ``artifact_id`` may live in.

    S12.7 (CT7): the codebase has TWO session-owned stores whose ids the
    model can legitimately see — ``session.artifact_store``
    (``workspace/.fa/artifacts``: run_bash/telemetry offloads) and the
    per-run projection store (``<run_log_dir>/artifacts``: refs emitted by
    ``project_for_model``). Resolution searches both; anything else is a
    foreign run. (Unifying the duplicated roots predates S12.7 and stays
    out of scope — see state.py's own note on the lazy init.)
    """
    # S11 typing discipline: direct typed attribute access only — never
    # duck-typed session lookups (fail-closed hygiene test pins this).
    stores: list[ArtifactStore] = []
    if session.artifact_store is not None:
        stores.append(session.artifact_store)
    try:
        stores.append(ArtifactStore.from_event_log(session.require_log()))
    except Exception as exc:  # noqa: BLE001 # expected pre-log: nothing was projected -> nothing to find
        logger.debug(f"artifact resolution: session log unavailable: {exc}")
    seen: set[Path] = set()
    unique: list[ArtifactStore] = []
    for store in stores:
        try:
            resolved = store.root.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(store)
    return unique


def _read_artifact(artifact_id: str, start_line: int | None, end_line: int | None) -> ToolResult:
    payload: object | None = None
    session = None
    try:
        from fa.inner_loop.context import get_current_session

        session = get_current_session()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"get_current_session failed in read_file artifact branch: {exc}")

    if session is not None:
        for store in _artifact_stores(session):
            payload = store.get(artifact_id)
            if payload is not None:
                break

    if payload is None:
        return ToolResult.fail(
            "artifact_not_found",
            f"artifact {artifact_id!r} not found in this run's artifact stores; "
            "ids come from [artifact: tool-result-…] references in tool results",
            retryable=True,
        )

    text = payload if isinstance(payload, str) else render_tool_payload(payload)
    lines = text.splitlines()
    if start_line is not None or end_line is not None:
        window = _validated_window(start_line, end_line, len(lines))
        if window is None:
            return ToolResult.fail("invalid_params", "invalid line window", retryable=True)
        content = "\n".join(lines[window[0] - 1 : window[1]])
    else:
        content = text

    # NOTE: no file-read telemetry here — S15 record_file_read/read_set are
    # workspace-file semantics; artifact reads are not file reads.
    # S12.7 (CT3): same T1/T2 framing + measure-then-handoff as file reads.
    total = len(lines)
    start_used, end_used = _used_bounds(start_line, end_line, total)
    raw_payload: dict[str, object] = {
        "artifact_id": artifact_id,
        "content": content,
        "line_count": total,
    }
    if start_line is not None or end_line is not None:
        raw_payload["start_line"] = start_used
        raw_payload["end_line"] = end_used
    return _framed_or_raw(
        raw_payload, _artifact_frame_header(artifact_id, total, start_used, end_used), f"read artifact {artifact_id}"
    )


def _read_set_telemetry(path: Path, root: Path) -> tuple[SessionState | None, str]:
    """Phase 0.5 read_set accumulation via contextvar DI (best-effort).

    Returns ``(session, rel)``; degradation never fails the read. Order note:
    like the original inline code, add_read fires BEFORE window validation.
    """
    session = None
    rel = str(path)
    try:
        from fa.inner_loop.context import get_current_session

        session = get_current_session()
        if session is not None:
            try:
                rel = str(path.relative_to(root))
            except ValueError:
                rel = str(path)
            try:
                session.add_read(rel)
            except Exception as exc:  # noqa: BLE001 - best-effort
                logger.warning(f"add_read failed for {rel}: {exc}")
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"get_current_session failed in read_file: {exc}")
    return session, rel


def _record_file_read_telemetry(
    session: SessionState | None,
    rel: str,
    content: str,
    start_line: int | None,
    end_line: int | None,
) -> None:
    """S15 (CT-3) file_read telemetry — success path only.

    surfaced_by is deterministic: a read attributes to search_result iff the
    path appeared in a search result from an EARLIER batch (last_search_paths
    is mutated only at batch boundaries — race-free by construction).
    """
    if session is None:
        return
    try:
        surfaced = "search_result" if rel in session.last_search_paths else "direct_reference"
        session.record_file_read(
            rel,
            start_line=start_line,
            end_line=end_line,
            surfaced_by=surfaced,
            bytes_read=len(content.encode("utf-8")),
        )
    except Exception as exc:  # noqa: BLE001 - telemetry degradation must not fail the read
        logger.warning(f"record_file_read failed for {rel}: {exc}")


def _parse_read_params(
    data: Mapping[str, object],
) -> tuple[str | None, str | None, int | None, int | None] | ToolResult:
    """S12.7 (CT7): the path XOR artifact_id preamble, shared by dispatch.

    Returns ``(path, artifact_id, start_line, end_line)`` — exactly one of
    the first two is non-None — or an ``invalid_params`` fail for bad types,
    both, or neither.
    """
    try:
        path_raw = optional_string(data, "path")
        artifact_id = optional_string(data, "artifact_id")
        start_line = optional_int(data, "start_line")
        end_line = optional_int(data, "end_line")
    except ValueError as exc:
        return ToolResult.fail("invalid_params", str(exc), retryable=True)
    if path_raw is not None and artifact_id is not None:
        return ToolResult.fail(
            "invalid_params",
            "path and artifact_id are mutually exclusive; pass exactly one",
            retryable=True,
        )
    if path_raw is None and artifact_id is None:
        return ToolResult.fail("invalid_params", "provide path or artifact_id", retryable=True)
    return path_raw, artifact_id, start_line, end_line


def build_read_file_tool(workspace_root: Path) -> ToolSpec:
    root = Path(workspace_root).resolve()

    def handler(params: Mapping[str, object]) -> ToolResult:
        data = dict(params)
        parsed = _parse_read_params(data)
        if isinstance(parsed, ToolResult):
            return parsed
        path_raw, artifact_id, start_line, end_line = parsed
        if artifact_id is not None:
            return _read_artifact(artifact_id, start_line, end_line)
        try:
            path = resolve_workspace_path(root, path_raw)
        except (ValueError, PermissionError) as exc:
            return ToolResult.fail("invalid_params", str(exc), retryable=True)

        text_or_fail = _read_file_text(path)
        if isinstance(text_or_fail, ToolResult):
            return text_or_fail
        text = text_or_fail

        # Phase 0.5: Transaction read_set accumulation via contextvar DI
        session, rel = _read_set_telemetry(path, root)

        lines = text.splitlines()
        if start_line is not None or end_line is not None:
            window = _validated_window(start_line, end_line, len(lines))
            if window is None:
                return ToolResult.fail("invalid_params", "invalid line window", retryable=True)
            content = "\n".join(lines[window[0] - 1 : window[1]])
        else:
            content = text

        # S15 (CT-3): file_read telemetry — success path only.
        _record_file_read_telemetry(session, rel, content, start_line, end_line)

        # S12.7 (CT3): T1/T2 frames + measure-then-handoff. The frame names
        # totals and the exact resume call; the measure is the RENDERED size
        # (same renderer as projection). Framed-over -> raw unframed payload
        # (window fields kept so the T3 elider anchors at the requested start).
        total = len(lines)
        start_used, end_used = _used_bounds(start_line, end_line, total)
        try:
            rel = str(path.relative_to(root))
        except ValueError:
            rel = str(path)
        raw_payload: dict[str, object] = {
            "path": str(path),
            "rel_path": rel,
            "content": content,
            "line_count": total,
        }
        if start_line is not None or end_line is not None:
            raw_payload["start_line"] = start_used
            raw_payload["end_line"] = end_used
        return _framed_or_raw(
            raw_payload,
            _file_frame_header(rel, total, start_used, end_used, len(text.encode("utf-8"))),
            f"read {rel}",
        )

    return ToolSpec(
        name="fs_read_file",
        description=(
            "Read UTF-8 files or PDFs inside the workspace, using pymupdf/pdfminer fallback. "
            "Declares read_set for blackboard/transaction and extracts PDF text per page. "
            "Alternatively pass artifact_id to follow an [artifact: …] reference."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "artifact_id": {
                    "type": "string",
                    "description": (
                        "Read a stored artifact payload (from an "
                        "[artifact: tool-result-…] reference) instead of a file; "
                        "start_line/end_line window it. Mutually exclusive with path."
                    ),
                },
                "start_line": {
                    "type": "integer",
                    "description": "First line to read (1-based, inclusive).",
                },
                "end_line": {
                    "type": "integer",
                    "description": (
                        "Last line to read (inclusive). Windows of <=~750 lines "
                        "(~30,000B) are typically returned whole; every result "
                        "names total lines and the resume call."
                    ),
                },
            },
        },
        permission="read",
        handler=handler,
        tags=("fs", "read"),
        elide=_read_head_frame,
    )


__all__ = ["build_read_file_tool"]
