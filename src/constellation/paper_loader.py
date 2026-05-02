"""Convert a PDF into Anthropic user-content blocks.

The current implementation ships the PDF whole as a base64 document block — the
model sees equations, figures, tables, captions. Expensive: a 30-page paper is
~30K input tokens. Replace this body when cost matters more than recall:

  - text-only:  pdf -> extracted text via pypdf/pdfplumber
                returns [{"type": "text", "text": full_text}]
  - text+figs:  text + selected figure images
  - chunked:    pre-summarized sections with on-demand drill-down

Pipeline stages call paper_to_user_blocks(); they don't know what's inside.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any


def paper_to_user_blocks(pdf_path: Path) -> list[dict[str, Any]]:
    """Return Anthropic user-content blocks representing this paper."""
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"expected .pdf, got {pdf_path}")
    data = base64.standard_b64encode(pdf_path.read_bytes()).decode("ascii")
    return [
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": data,
            },
        },
    ]
