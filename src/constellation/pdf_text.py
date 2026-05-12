from __future__ import annotations

import subprocess
from pathlib import Path


def pdf_to_text(path: Path) -> str:
    """Extract PDF text with the local poppler `pdftotext` binary."""
    result = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
    )
    return result.stdout


def discover_pdfs(corpus: Path) -> list[Path]:
    pdf_root = corpus / "pdfs"
    if not pdf_root.exists():
        raise FileNotFoundError(f"missing pdfs directory: {pdf_root}")
    return sorted(p for p in pdf_root.iterdir() if p.suffix.lower() == ".pdf")

