"""Filesystem layout for an input corpus and a per-run output directory.

Convention:
  corpora/<name>/pdfs/*.pdf       — input
  runs/<name>_<utc-timestamp>/    — output of one pipeline run
    papers/<paper_id>.json
    claims/<paper_id>:<n>.json
    tags.json                     — sidecar for stage 2 (_tags by claim_id)
    comparability_complex.json    — stage 3 edge list
    sheaf.json                    — stages 4–7 collapsed into the sheaf artifact
    ideas/<idea_id>.json          — stage 8
    report.md                     — stage 9
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class Corpus:
    """An input corpus on disk."""

    root: Path

    @property
    def name(self) -> str:
        return self.root.name

    @property
    def pdfs_dir(self) -> Path:
        return self.root / "pdfs"

    def pdfs(self) -> list[Path]:
        return sorted(self.pdfs_dir.glob("*.pdf"))


@dataclass(frozen=True)
class Run:
    """A single pipeline-run output directory."""

    root: Path

    @classmethod
    def new(cls, corpus: Corpus, runs_root: Path) -> Run:
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        root = runs_root / f"{corpus.name}_{ts}"
        root.mkdir(parents=True, exist_ok=False)
        return cls(root=root)

    @classmethod
    def existing(cls, root: Path) -> Run:
        if not root.is_dir():
            raise FileNotFoundError(f"run directory not found: {root}")
        return cls(root=root)

    @property
    def papers_dir(self) -> Path:
        return self.root / "papers"

    @property
    def claims_dir(self) -> Path:
        return self.root / "claims"

    @property
    def tag_vocabulary_path(self) -> Path:
        """Stage 2a output: the corpus's proposed semilattice + SNAG vocabulary."""
        return self.root / "tag_vocabulary.json"

    @property
    def tags_path(self) -> Path:
        """Stage 2b output: per-claim tags keyed by claim_id."""
        return self.root / "tags.json"

    @property
    def complex_path(self) -> Path:
        return self.root / "comparability_complex.json"

    @property
    def sheaf_path(self) -> Path:
        return self.root / "sheaf.json"

    @property
    def ideas_dir(self) -> Path:
        return self.root / "ideas"

    @property
    def report_path(self) -> Path:
        return self.root / "report.md"

    def ensure_dirs(self) -> None:
        for d in (self.papers_dir, self.claims_dir, self.ideas_dir):
            d.mkdir(parents=True, exist_ok=True)
