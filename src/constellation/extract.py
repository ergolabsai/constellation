from __future__ import annotations

from pathlib import Path

from .pdf_text import discover_pdfs, pdf_to_text
from .seeds import extract_seeded_records
from .util import Json, write_json


def extract_corpus(corpus: Path, run_dir: Path) -> tuple[list[Json], list[Json], list[Json]]:
    papers: list[Json] = []
    claims: list[Json] = []
    evidence: list[Json] = []

    for pdf_path in discover_pdfs(corpus):
        text = pdf_to_text(pdf_path)
        paper, paper_claims, paper_evidence = extract_seeded_records(pdf_path, text)
        papers.append(paper)
        claims.extend(paper_claims)
        evidence.extend(paper_evidence)

    for paper in papers:
        write_json(run_dir / "papers" / f"{paper['paper_id']}.json", paper)
    for claim in claims:
        write_json(run_dir / "claims" / f"{claim['claim_id']}.json", claim)
    for ev in evidence:
        write_json(run_dir / "evidence" / f"{ev['evidence_id']}.json", ev)

    return papers, claims, evidence

