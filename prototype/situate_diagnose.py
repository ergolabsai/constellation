"""
PROTOTYPE — not wired into the pipeline, does not modify src/.

Demonstrates the "living map" loop we're designing:

    1. situate()  - drop a new finding (claims + evidence) into an existing map
    2. assess()   - decide whether it is a CREDIBLE contribution or a SUSPECT
                    result that fights established, independent prior work
    3. brief()    - emit the structured brief an LLM uses to start interrogating
                    the setup (the "what to ask" seed)

It reads existing run outputs (claims/, evidence/) as the current map state and
reuses the existing pure functions in constellation.sheaf WITHOUT changing them.

Run:
    PYTHONPATH=src python prototype/situate_diagnose.py \
        --map corpora/atlas_prior/v05_prior \
        --finding-from corpora/atlas/v05 --finding-paper atlas2026
"""
from __future__ import annotations

import argparse
import copy
import json
from collections import defaultdict
from pathlib import Path

from constellation.sheaf import (
    generate_prediction_edges,
    optimize_claim_rewrites,
    residuals,
    residual_total,
)

CONTRADICTION = 0.30  # |residual| above this on an edge = a real disagreement
SUSPECT_MIN_INDEPENDENT = 2  # contradicted by >= this many independent papers -> suspect


def load_nodes(run_dir: Path) -> tuple[list[dict], list[dict]]:
    claims = [json.loads(p.read_text()) for p in sorted((run_dir / "claims").glob("*.json"))]
    evidence = [json.loads(p.read_text()) for p in sorted((run_dir / "evidence").glob("*.json"))]
    return claims, evidence


def situate(map_claims, map_evidence, new_claims, new_evidence):
    """Splice a contribution into the map and return (claims, evidence, edges)."""
    claims = copy.deepcopy(map_claims) + copy.deepcopy(new_claims)
    evidence = copy.deepcopy(map_evidence) + copy.deepcopy(new_evidence)
    for c in claims:
        c["x_final"] = list(c["x_init"])  # start unaccommodated
    edges = generate_prediction_edges(claims, evidence)
    return claims, evidence, edges


def assess(map_claims, map_evidence, new_claims, new_evidence):
    new_claim_ids = {c["claim_id"] for c in new_claims}
    new_ev_ids = {e["evidence_id"] for e in new_evidence}
    label = {c["claim_id"]: c["label"] for c in map_claims + new_claims}
    paper = {c["claim_id"]: c["paper_id"] for c in map_claims + new_claims}
    conf = {c["claim_id"]: c["provenance"].get("confidence") for c in map_claims + new_claims}
    ev_label = {e["evidence_id"]: e["label"] for e in map_evidence + new_evidence}

    claims, evidence, edges = situate(map_claims, map_evidence, new_claims, new_evidence)

    # raw reaction: residuals with every prior claim at FULL strength (no accommodation)
    raw = {r["edge_id"]: r for r in residuals(claims, evidence, edges, use_final=True)}
    raw_total = residual_total(raw.values())

    # what the CURRENT architecture does: accommodate by narrowing prior claims
    accom_claims = copy.deepcopy(claims)
    accom_ops = optimize_claim_rewrites(accom_claims, evidence, edges)
    accom = residuals(accom_claims, evidence, edges, use_final=True)
    accom_total = residual_total(accom)
    surviving = [r for r in accom if r["residual_sq"] > 0.05]

    # per new finding: which established (other-paper) claims contradict it, at full strength
    findings = []
    for ev in new_evidence:
        eid = ev["evidence_id"]
        contradictors = []
        for e in edges:
            if e["evidence_id"] != eid:
                continue
            cid = e["claim_id"]
            if cid in new_claim_ids:
                continue  # only PRIOR claims count as independent challenge
            r = raw[e["edge_id"]]["dimensions"][0]["residual"]
            if abs(r) > CONTRADICTION:
                contradictors.append(
                    {"claim_id": cid, "paper": paper[cid], "confidence": conf[cid],
                     "residual": round(r, 3), "says": label[cid]}
                )
        independent_papers = sorted({c["paper"] for c in contradictors})
        # what does the finding lean on to escape? new claims wired to this node
        escape = sorted({e["claim_id"] for e in edges
                         if e["evidence_id"] == eid and e["claim_id"] in new_claim_ids})
        verdict = ("suspect" if len(independent_papers) >= SUSPECT_MIN_INDEPENDENT
                   else ("contested" if contradictors else "credible"))
        findings.append({
            "evidence_id": eid,
            "label": ev_label[eid],
            "verdict": verdict,
            "n_independent_contradictors": len(independent_papers),
            "contradicting_papers": independent_papers,
            "contradictors": contradictors,
            "leans_on": [{"claim_id": cid, "label": label[cid]} for cid in escape],
        })

    findings.sort(key=lambda f: -f["n_independent_contradictors"])
    return {
        "raw_residual": round(raw_total, 3),
        "accommodated_residual": round(accom_total, 3),
        "accommodation": [{"claim_id": o["claim_id"], "from": o["from"], "to": o["to"]} for o in accom_ops],
        "surviving_tensions": [
            {"edge_id": r["edge_id"], "residual_sq": round(r["residual_sq"], 3)} for r in surviving
        ],
        "findings": findings,
    }


def brief(a: dict) -> str:
    out = []
    out.append("=" * 70)
    out.append("SITUATE REPORT")
    out.append("=" * 70)
    out.append(f"Dropping this contribution moved the map's tension from 0.0 -> {a['raw_residual']} (raw).")
    out.append(f"The current cost model would 'resolve' it down to {a['accommodated_residual']} by")
    out.append("narrowing established claims:")
    for op in a["accommodation"]:
        out.append(f"    - {op['claim_id']}: {op['from']} -> {op['to']}  (discount a prior result)")
    if a["surviving_tensions"]:
        out.append(f"  ...and yet {len(a['surviving_tensions'])} tension(s) refuse to die even after that.")

    suspects = [f for f in a["findings"] if f["verdict"] == "suspect"]
    passed = [f for f in a["findings"] if f["verdict"] != "suspect"]
    out.append("")
    out.append(f"Of {len(a['findings'])} new findings, {len(suspects)} flagged SUSPECT, {len(passed)} passed.")

    for f in suspects:
        out.append("")
        out.append(f"  [SUSPECT] {f['evidence_id']}")
        out.append(f"      {f['label']}")
        out.append(f"      Contradicted by {f['n_independent_contradictors']} INDEPENDENT established results:")
        for c in f["contradictors"]:
            out.append(f"        - {c['claim_id']} ({c['paper']}): {c['says'][:58]}")
        out.append("      It escapes them only by leaning on:")
        for e in f["leans_on"]:
            out.append(f"        - {e['claim_id']}: {e['label'][:60]}")
        out.append("      => One new result overturning several independent obstructions is")
        out.append("         either a major discovery or an artifact. Audit the finding's")
        out.append("         setup before rewriting the field. Interrogate what it leans on.")

    if passed:
        out.append("")
        out.append("  Findings that passed (cohere or only mildly contested):")
        for f in passed:
            out.append(f"        - {f['evidence_id']} [{f['verdict']}]")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True, type=Path, help="run dir to use as the current map")
    ap.add_argument("--finding-from", required=True, type=Path, help="run dir to pull the new finding from")
    ap.add_argument("--finding-paper", required=True, help="paper_id of the contribution to drop in")
    ap.add_argument("--json", action="store_true", help="dump raw assessment json")
    args = ap.parse_args()

    map_claims, map_evidence = load_nodes(args.map)
    src_claims, src_evidence = load_nodes(args.finding_from)
    new_claims = [c for c in src_claims if c["paper_id"] == args.finding_paper]
    new_evidence = [e for e in src_evidence if e["paper_id"] == args.finding_paper]

    a = assess(map_claims, map_evidence, new_claims, new_evidence)
    if args.json:
        print(json.dumps(a, indent=2))
    else:
        print(brief(a))


if __name__ == "__main__":
    main()
