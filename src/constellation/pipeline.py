from __future__ import annotations

import shutil
from pathlib import Path

from .extract import extract_corpus
from .report import write_report
from .sheaf import (
    build_evidence_comparability,
    build_sheaf,
    consolidate_ideas,
    generate_prediction_edges,
    optimize_claim_rewrites,
    write_sheaf_artifacts,
)
from .util import Json


def run_pipeline(corpus: Path, output: Path, *, force: bool = False) -> Json:
    corpus = corpus.resolve()
    output = output.resolve()
    if output.exists():
        if not force:
            raise FileExistsError(f"output directory already exists: {output}")
        shutil.rmtree(output)
    output.mkdir(parents=True)

    papers, claims, evidence = extract_corpus(corpus, output)
    comparability = build_evidence_comparability(evidence)
    edges = generate_prediction_edges(claims, evidence)
    operations = optimize_claim_rewrites(claims, evidence, edges)
    sheaf = build_sheaf(corpus.name, claims, evidence, edges, operations)
    ideas = consolidate_ideas(corpus.name, claims, evidence, sheaf)

    write_sheaf_artifacts(output, comparability, edges, sheaf, ideas)
    for claim in claims:
        from .util import write_json

        write_json(output / "claims" / f"{claim['claim_id']}.json", claim)
    write_report(output, papers, claims, evidence, sheaf, ideas)

    return {
        "output": str(output),
        "papers": len(papers),
        "claims": len(claims),
        "evidence": len(evidence),
        "edges": len(edges),
        "ideas": len(ideas),
        "initial_residual": sheaf["objective"]["initial_residual"],
        "final_residual": sheaf["objective"]["final_residual"],
    }

