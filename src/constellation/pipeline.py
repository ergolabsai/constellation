from __future__ import annotations

import shutil
from pathlib import Path

from .comparability import generate_semantic_cross_edges, load_comparability
from .extract import extract_corpus
from .report import write_report
from .sheaf import (
    build_evidence_comparability,
    build_sheaf,
    generate_prediction_edges,
    optimize_claim_rewrites,
    residual_for_edge,
    write_sheaf_artifacts,
)
from .stature import stature_weighted_lambda
from .subjects import discover_subjects
from .util import Json


HYGIENE_CONTRADICTION_THRESHOLD = 0.05


def run_pipeline(
    corpus: Path,
    output: Path,
    *,
    force: bool = False,
    new_paper_ids: set[str] | None = None,
) -> Json:
    """Build a constellation map from a corpus directory.

    The optimizer uses the stature-weighted cost model by default:
    rewrite cost scales with how many independent papers back each
    claim, so the map natively defends well-established knowledge
    instead of accommodating fresh contributions against it.

    When ``new_paper_ids`` is supplied, claims from those papers are
    treated as an incoming contribution and given a cheap rewrite
    discount -- the situate-style behavior, where the optimizer prefers
    to doubt the newcomer over the field. Cross-paper semantic edges
    are also restricted to those papers, so the implicit-headline
    propagator runs only over the contribution.
    """
    corpus = corpus.resolve()
    output = output.resolve()
    if output.exists():
        if not force:
            raise FileExistsError(f"output directory already exists: {output}")
        # Try to wipe the directory; if the filesystem refuses (e.g.,
        # mounted host directories with sticky xattrs), fall back to
        # clearing only the per-record subdirectories. We can usually
        # unlink the files themselves even when the parent dir is
        # locked. This prevents stale ideas/claims/evidence/papers from
        # a previous run from polluting the current one.
        try:
            shutil.rmtree(output)
        except PermissionError:
            for sub in ("ideas", "claims", "evidence", "papers"):
                d = output / sub
                if d.exists():
                    for f in d.glob("*.json"):
                        try:
                            f.unlink()
                        except PermissionError:
                            pass
    output.mkdir(parents=True, exist_ok=True)

    papers, claims, evidence = extract_corpus(corpus, output)
    observable_groups = build_evidence_comparability(evidence)
    base_edges = generate_prediction_edges(claims, evidence)

    cross_paper_groups = load_comparability(corpus)
    # Semantic propagation runs for every claim, not just the incoming
    # contribution: established priors that mutually corroborate within
    # a group accumulate stature from that agreement, and the optimizer
    # gets a faithful accountability signal across the full map. The
    # incoming-claim discount lives in the lambda factory, not here.
    semantic_edges = generate_semantic_cross_edges(
        claims,
        evidence,
        base_edges,
        cross_paper_groups,
    )
    edges = base_edges + semantic_edges

    lambda_fn, stature = stature_weighted_lambda(
        claims, evidence, edges, new_paper_ids=new_paper_ids
    )
    operations = optimize_claim_rewrites(claims, evidence, edges, lambda_fn=lambda_fn)
    lambda_model = "stature_weighted_situate" if new_paper_ids else "stature_weighted"

    claim_hygiene = _summarize_claim_hygiene(
        claims, evidence, semantic_edges, cross_paper_groups
    )
    sheaf = build_sheaf(
        corpus.name,
        claims,
        evidence,
        edges,
        operations,
        stature=stature,
        lambda_model=lambda_model,
        incoming_paper_ids=new_paper_ids,
        semantic_edge_ids={e["edge_id"] for e in semantic_edges},
        claim_hygiene=claim_hygiene,
    )
    subjects = discover_subjects(
        claims, evidence, cross_paper_groups,
        incoming_paper_ids=new_paper_ids,
    )
    # backward-compat: keep the name "ideas" downstream since report.py
    # and write_sheaf_artifacts both still call them ideas. Each subject
    # is the new schema (two-layer with assertions inside) and the report
    # renders accordingly.
    ideas = subjects

    write_sheaf_artifacts(output, observable_groups, edges, sheaf, ideas)
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
        "semantic_edges": len(semantic_edges),
        "ideas": len(ideas),
        "lambda_model": lambda_model,
        "incoming_paper_ids": sorted(new_paper_ids) if new_paper_ids else [],
        "initial_residual": sheaf["objective"]["initial_residual"],
        "final_residual": sheaf["objective"]["final_residual"],
    }


def _summarize_claim_hygiene(
    claims: list[Json],
    evidence: list[Json],
    semantic_edges: list[Json],
    cross_paper_groups: dict[str, list[str]],
) -> dict[str, Json]:
    """Per-claim hygiene marker derived from the semantic propagator.

    A claim that touches a comparability group can land in one of:

    * ``implicit_headline``: at least one propagated cross-edge
      CONTRADICTS the evidence at full strength. The claim asserts a
      result it has not earned in regimes covered by the rest of the
      group. This is the structural suspect signal.
    * ``consensus_aligned``: cross-edges were propagated and they all
      agree with the field at full strength. The claim is implicitly
      restating field consensus -- not suspect, just confirming what
      the rest of the map already says.
    * ``scoped_explicit``: the claim already addresses every other
      member of the group through explicit predictions; the propagator
      had nothing to add.
    * ``not_applicable``: the claim touches no comparability group at
      all.
    """
    claim_by_id = {c["claim_id"]: c for c in claims}
    ev_by_id = {e["evidence_id"]: e for e in evidence}

    semantic_targets: dict[str, list[str]] = {}
    semantic_contradictions: dict[str, list[str]] = {}
    for edge in semantic_edges:
        cid = edge["claim_id"]
        claim = claim_by_id.get(cid)
        ev = ev_by_id.get(edge["evidence_id"])
        if claim is None or ev is None:
            continue
        probe = {**claim, "x_final": list(claim["x_init"])}
        r = residual_for_edge(probe, ev, edge, use_final=True)
        semantic_targets.setdefault(cid, []).append(edge["evidence_id"])
        if r["residual_sq"] > HYGIENE_CONTRADICTION_THRESHOLD:
            semantic_contradictions.setdefault(cid, []).append(edge["evidence_id"])

    group_members: dict[str, set[str]] = {
        name: set(members) for name, members in cross_paper_groups.items()
    }

    summary: dict[str, Json] = {}
    for claim in claims:
        explicit_targets: set[str] = set()
        for pred in claim.get("predictions", []) or []:
            explicit_targets.update(pred.get("evidence_ids") or [])

        groups_touched: list[str] = []
        groups_fully_addressed: list[str] = []
        for name, members in group_members.items():
            if explicit_targets & members:
                groups_touched.append(name)
                if members <= explicit_targets:
                    groups_fully_addressed.append(name)

        all_targets = sorted(semantic_targets.get(claim["claim_id"], []))
        contradicting = sorted(semantic_contradictions.get(claim["claim_id"], []))
        consistent = [t for t in all_targets if t not in set(contradicting)]

        # A claim is an implicit-headline suspect only when its propagation
        # contradicts MORE comparable evidence than it agrees with. A
        # consensus-aligned prior that brushes against a single suspect
        # newcomer (e.g., BR_01 propagating to ev_atlas_kink_zero) should
        # not be flagged -- the suspect is the newcomer, not BR_01.
        if contradicting and len(contradicting) > len(consistent):
            status = "implicit_headline"
        elif all_targets:
            status = "consensus_aligned"
        elif groups_touched:
            status = "scoped_explicit"
        else:
            status = "not_applicable"

        summary[claim["claim_id"]] = {
            "status": status,
            "groups_touched": groups_touched,
            "groups_fully_addressed": groups_fully_addressed,
            "propagated_targets": all_targets,
            "contradicting_targets": contradicting,
            "consistent_targets": consistent,
        }
    return summary

