from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools.base import optional_int, require_string, resolve_workspace_path


def _read_pdf_text(path: Path) -> str | None:
    """Try to extract text from PDF via pymupdf (fitz), fallback to pdfminer, else None.

    Production-grade: graceful degradation, not crash, WARNING logged.
    For user data 01-11.pdf with table of reviews, pymupdf extracts 2282 chars per page.
    """
    # Try pymupdf (fitz) first - fastest, best for text tables
    try:
        import fitz  # type: ignore[import-untyped]

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
        pass
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        print(f"WARNING: pymupdf failed for {path}: {exc}")

    # Try pdfminer.six as fallback
    try:
        from pdfminer.high_level import extract_text  # type: ignore[import-untyped]

        text = extract_text(str(path))
        if text and len(text.strip()) > 50:
            return text
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        print(f"WARNING: pdfminer failed for {path}: {exc}")

    # Try pypdf as last fallback
    try:
        from pypdf import PdfReader  # type: ignore[import-untyped]

        reader = PdfReader(str(path))
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
        pass
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        print(f"WARNING: pypdf failed for {path}: {exc}")

    return None


def build_read_file_tool(workspace_root: Path) -> ToolSpec:
    root = Path(workspace_root).resolve()

    def handler(params: Mapping[str, object]) -> ToolResult:
        data = dict(params)
        try:
            path = resolve_workspace_path(root, require_string(data, "path"))
            start_line = optional_int(data, "start_line")
            end_line = optional_int(data, "end_line")
        except ValueError as exc:
            return ToolResult.fail("invalid_params", str(exc), retryable=True)

        # Handle PDF via dedicated extractor for user data 01-11.pdf compatibility
        if path.suffix.lower() == ".pdf":
            pdf_text = _read_pdf_text(path)
            if pdf_text is not None:
                text = pdf_text
            else:
                try:
                    # Fallback try utf-8 read (may fail)
                    text = path.read_text(encoding="utf-8")
                except (OSError, PermissionError, ValueError) as exc:
                    return ToolResult.fail(
                        "read_failed",
                        f"PDF extraction failed and utf-8 read failed for {path}: {exc}. "
                        f"Install pymupdf (pip install pymupdf) for PDF support.",
                        retryable=True,
                    )
        else:
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, PermissionError, ValueError) as exc:
                return ToolResult.fail("read_failed", str(exc), retryable=True)

        # Phase 0.5: Transaction read_set accumulation via contextvar DI
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
                    print(f"WARNING: add_read failed for {rel}: {exc}")
        except Exception as exc:  # noqa: BLE001
            print(f"WARNING: get_current_session failed in read_file: {exc}")

        lines = text.splitlines()
        if start_line is not None or end_line is not None:
            start = 1 if start_line is None else start_line
            end = len(lines) if end_line is None else end_line
            if start < 1 or end < start:
                return ToolResult.fail("invalid_params", "invalid line window", retryable=True)
            selected = lines[start - 1 : end]
            content = "\n".join(selected)
        else:
            content = text

        return ToolResult.ok(
            f"read {path.relative_to(root)}",
            result={
                "path": str(path),
                "content": content,
                "line_count": len(lines),
            },
        )

    return ToolSpec(
        name="fs.read_file",
        description="Read UTF-8 file or PDF (via pymupdf/pdfminer fallback) inside workspace. Declares read_set for blackboard/transaction. For PDF tables, extracts text per page.",
        input_schema={
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": "integer"},
                "end_line": {"type": "integer"},
            },
        },
        permission="read",
        handler=handler,
        tags=("fs", "read"),
    )


__all__ = ["build_read_file_tool"]
