"""``record_gotcha`` — append-only learning loop entry point.

The function appends one timestamped section to a Markdown file
(default ``knowledge/trace/gotchas.md``). Writes are atomic per
call: the new content is staged to a ``.tmp`` sibling and
``os.replace``d into the target, so the target never contains a
half-written body. Concurrent invocation from multiple processes
is **not** safe — see :mod:`fa.tools` package docstring for the
single-writer contract and BACKLOG M-1 deferral.

Format of each appended section (stable; matches Aperant
``record-gotcha.ts:42-61`` shape):

.. code-block:: markdown

    ## 2026-05-20T14:23:01Z — <subject>

    <body>

    **Tags:** tag-one, tag-two
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_GOTCHAS_PATH = Path("knowledge/trace/gotchas.md")

_WHITESPACE_RUN = re.compile(r"\s+")


def _now_iso_z() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalise_subject(subject: str) -> str:
    cleaned = _WHITESPACE_RUN.sub(" ", subject).strip()
    if not cleaned:
        raise ValueError("gotcha subject must be non-empty after whitespace strip")
    return cleaned


def record_gotcha(
    subject: str,
    body: str,
    *,
    tags: Iterable[str] = (),
    path: Path = DEFAULT_GOTCHAS_PATH,
    now: str | None = None,
) -> Path:
    """Append one gotcha section to ``path`` and return the path.

    ``subject`` is the one-line title (whitespace-normalised; rejected
    if it would be empty). ``body`` is the free-text section content.
    ``tags`` are optional short slugs rendered as a ``**Tags:**``
    trailer. ``now`` lets tests inject a fixed timestamp.

    The file's parent directory is created if missing. Existing
    content is preserved verbatim — the function reads the file
    bytes, appends a separator + the new section, then atomically
    renames the temp file over the target.
    """

    target = Path(path)
    cleaned_subject = _normalise_subject(subject)
    timestamp = now if now is not None else _now_iso_z()
    tag_list = [tag.strip() for tag in tags if tag.strip()]

    target.parent.mkdir(parents=True, exist_ok=True)

    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    separator = (
        ""
        if not existing or existing.endswith("\n\n")
        else ("\n" if existing.endswith("\n") else "\n\n")
    )

    section_lines = [f"## {timestamp} — {cleaned_subject}", "", body.rstrip()]
    if tag_list:
        section_lines.extend(["", f"**Tags:** {', '.join(tag_list)}"])
    new_section = "\n".join(section_lines) + "\n"

    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(existing + separator + new_section, encoding="utf-8")
    os.replace(tmp, target)
    return target


__all__ = ["DEFAULT_GOTCHAS_PATH", "record_gotcha"]
