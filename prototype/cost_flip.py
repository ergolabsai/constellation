"""
PROTOTYPE — not wired into the pipeline, does not modify src/.

Tests change #1 from the situate diagnosis: flip the epistemic cost model.

  CURRENT (in constellation.sheaf.optimize_claim_rewrites):
      Every claim has the same rewrite cost (lambda_claim = 1.0).
      When a new finding contradicts established priors, the optimizer
      cheerfully narrows ANY of them at the same price -> the field gets
      bent around the newcomer. This is what accommodates Kumar's
      ev_atlas_kink_zero against AN_01/B_01/N_01 in the live run.

  FLIPPED (this prototype):
      lambda_claim(c) scales with how established c is in the prior map
      (count of INDEPENDENT papers whose evidence corroborates it).
      Doubting a Newcomb-1960-grade claim is expensive; doubting a brand
      new, untested claim is cheap. The optimizer should now leave the
      priors alone and let the contradiction persist on the map.

Reuses residual_for_edge / residual_total / generate_prediction_edges from
constellation.sheaf so the physics math is identical.

Run:
    PYTHONPATH=src python prototype/cost_flip.py \\
        --map corpora/atlas_prior/v05_prior \\
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
    residual_for_edge,
    residual_total,
    residuals,
)

# Cost-model knobs we are testing. Defaults picked so that stature=1 priors
# (only their home paper backs them in this corpus) still resist narrowing
# enough to leave the contradiction visible on the map.
BASE_LAMBDA = 1.0          # cost of doubting a stature-0 claim
ALPHA = 8.0                # extra cost per independent supporting paper
NEW_CLAIM_DISCOUNT = 0.3   # cost of doubting a brand-new, untested incoming claim

SUSPECT_NODE = "ev_atlas_kink_zero"

# A claim is treated as "established" for the verdict heuristic if at least
# one prior paper backs it. Stature == 0 means the optimizer is free to
# rewrite it without epistemic cost.
ESTABLISHED_MIN_STATURE = 1

# Hardcoded for the prototype: evidence nodes that measure the same
# underlying phenomenon. In the production architecture this would come
# from a learned/curated comparability registry, or from the LLM
# proposer. The values are the reported measurement on a normalized
# binary scale (1 = m=1 stable, 0 = m=1 unstable).
#
# A claim that has an explicit prediction targeting any of these
# evidence nodes is taken to be HANDLING that node consciously
# (e.g., A_05 explicitly predicts both stable in its own regime and
# unstable in Newcomb-style regimes). For claims that only attach to
# their HOME group member without addressing the others, we propagate
# the home stance as a SEMANTIC CROSS-EDGE -- this is what makes the
# "implicit headline" claim auditable against the rest of the field.
COMPARABILITY_GROUPS: dict[str, list[str]] = {
    "m1_stability_outcome": [
        "ev_atlas_kink_zero",
        "ev_angus_m1_persists",
        "ev_bondeson_toroidal",
        "ev_newcomb_static",
        "ev_goedbloed_sari",
        "ev_brughmans_growth",
    ],
}


# ---------------------------------------------------------------------------
# load / stature
# ---------------------------------------------------------------------------

def load_nodes(run_dir: Path) -> tuple[list[dict], list[dict]]:
    claims = [json.loads(p.read_text()) for p in sorted((run_dir / "claims").glob("*.json"))]
    evidence = [json.loads(p.read_text()) for p in sorted((run_dir / "evidence").glob("*.json"))]
    return claims, evidence


def compute_stature(map_claims: list[dict], map_evidence: list[dict]) -> dict[str, int]:
    """For each PRIOR claim, count distinct papers whose evidence is wired to
    it in the prior-only map. Emergent property of the graph, not hardcoded."""
    paper_by_ev = {e["evidence_id"]: e["paper_id"] for e in map_evidence}
    prior_edges = generate_prediction_edges(map_claims, map_evidence)
    backing: dict[str, set[str]] = defaultdict(set)
    for edge in prior_edges:
        backing[edge["claim_id"]].add(paper_by_ev[edge["evidence_id"]])
    return {cid: len(papers) for cid, papers in backing.items()}


def lambda_for(claim_id: str, stature: dict[str, int], new_claim_ids: set[str]) -> float:
    if claim_id in new_claim_ids:
        return NEW_CLAIM_DISCOUNT
    return BASE_LAMBDA * (1.0 + ALPHA * stature.get(claim_id, 0))


# ---------------------------------------------------------------------------
# semantic cross-edge generator
# ---------------------------------------------------------------------------

def generate_semantic_cross_edges(
    new_claims: list[dict],
    all_evidence: list[dict],
    existing_edges: list[dict],
) -> list[dict]:
    """For each new claim, if it has a home prediction inside a comparability
    group, propagate that home stance as a cross-edge to every OTHER member
    of the group the claim has NOT explicitly addressed. This catches the
    'implicit headline' -- a claim that asserts a result without saying
    'only in this regime' is, by silence, claiming it elsewhere too."""
    ev_by_id = {e["evidence_id"]: e for e in all_evidence}
    existing_pairs = {(e["claim_id"], e["evidence_id"]) for e in existing_edges}
    new_edges: list[dict] = []

    for claim in new_claims:
        # Every evidence_id the claim explicitly mentions in any prediction
        # is treated as "consciously handled" and skipped.
        explicit_targets: set[str] = set()
        for pred in claim.get("predictions", []):
            explicit_targets.update(pred.get("evidence_ids", []) or [])

        for group_name, members in COMPARABILITY_GROUPS.items():
            # The HOME member is the one in this group that the claim's own
            # paper produced. We read the claim's prediction value there as
            # the "headline" stance for the group.
            home_ev = None
            home_val = None
            for pred in claim.get("predictions", []):
                for eid in pred.get("evidence_ids", []) or []:
                    ev = ev_by_id.get(eid)
                    if ev is None or eid not in members:
                        continue
                    if ev["paper_id"] == claim["paper_id"]:
                        home_ev = eid
                        home_val = float(pred["value"])
                        break
                if home_ev is not None:
                    break
            if home_ev is None:
                continue

            for eid in members:
                if eid == home_ev or eid in explicit_targets:
                    continue
                if (claim["claim_id"], eid) in existing_pairs:
                    continue
                ev = ev_by_id.get(eid)
                if ev is None:
                    continue
                dim = ev["core"]["dimensions"][0]
                new_edges.append({
                    "edge_id": f"{claim['claim_id']}__{eid}__semantic",
                    "claim_id": claim["claim_id"],
                    "evidence_id": eid,
                    "base_prediction": {
                        "dimensions": [{
                            "name": dim["name"],
                            "value": home_val,
                            "scale": dim.get("scale", "normalized_binary"),
                        }]
                    },
                    "regime_tag": "out_of_regime",
                    "edge_stalk": {
                        "dimensions": [{
                            "name": dim["name"],
                            "scale": dim.get("scale", "normalized_binary"),
                        }]
                    },
                    "prediction_rationale": (
                        f"semantic cross-edge: {claim['claim_id']} states "
                        f"{home_ev}={home_val} but does not address "
                        f"comparable {eid}; propagating home stance."
                    ),
                    "provenance": {
                        "prediction_generated_by": "semantic_comparability_group",
                        "group": group_name,
                        "confidence": 0.5,
                        "review_status": "unreviewed",
                    },
                })
    return new_edges


# ---------------------------------------------------------------------------
# stature-aware optimizer (parallels constellation.sheaf.optimize_claim_rewrites)
# ---------------------------------------------------------------------------

def _claim_residual_total(claim, claim_edges, evidence_by_id) -> float:
    return residual_total(
        residual_for_edge(claim, evidence_by_id[e["evidence_id"]], e, use_final=True)
        for e in claim_edges
    )


def _claim_objective(claim, claim_edges, evidence_by_id, lam) -> float:
    rewrite_penalty = sum(
        (float(a) - float(b)) ** 2 for a, b in zip(claim["x_final"], claim["x_init"], strict=True)
    )
    return _claim_residual_total(claim, claim_edges, evidence_by_id) + lam * rewrite_penalty


def optimize_with_lambda_fn(claims, evidence, edges, lambda_fn):
    evidence_by_id = {ev["evidence_id"]: ev for ev in evidence}
    edges_by_claim: dict[str, list] = defaultdict(list)
    for edge in edges:
        edges_by_claim[edge["claim_id"]].append(edge)
    operations = []
    candidates = [1.0, 0.8, 0.6, 0.4, 0.2, 0.0]
    for claim in claims:
        claim_edges = edges_by_claim.get(claim["claim_id"], [])
        if not claim_edges:
            continue
        lam = lambda_fn(claim["claim_id"])
        original = list(claim["x_final"])
        best_state = original
        best_score = _claim_objective(claim, claim_edges, evidence_by_id, lam)
        for out_strength in candidates:
            claim["x_final"] = [1.0, out_strength]
            score = _claim_objective(claim, claim_edges, evidence_by_id, lam)
            if score < best_score - 1e-12:
                best_score = score
                best_state = list(claim["x_final"])
        claim["x_final"] = best_state
        if best_state != original:
            operations.append({
                "claim_id": claim["claim_id"],
                "from": original,
                "to": best_state,
                "lambda": lam,
            })
    return operations


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

def run(map_dir: Path, finding_dir: Path, finding_paper: str) -> dict:
    map_claims, map_evidence = load_nodes(map_dir)
    src_claims, src_evidence = load_nodes(finding_dir)
    new_claims = [c for c in src_claims if c["paper_id"] == finding_paper]
    new_evidence = [e for e in src_evidence if e["paper_id"] == finding_paper]
    new_claim_ids = {c["claim_id"] for c in new_claims}

    # Stature is measured against the prior-only map.
    stature = compute_stature(map_claims, map_evidence)

    # Build the spliced map (prior + contribution) and reset x_final = x_init.
    all_claims = copy.deepcopy(map_claims) + copy.deepcopy(new_claims)
    all_evidence = copy.deepcopy(map_evidence) + copy.deepcopy(new_evidence)
    for c in all_claims:
        c["x_final"] = list(c["x_init"])
    base_edges = generate_prediction_edges(all_claims, all_evidence)
    semantic_edges = generate_semantic_cross_edges(new_claims, all_evidence, base_edges)
    all_edges = base_edges + semantic_edges
    raw_total = residual_total(residuals(all_claims, all_evidence, all_edges, use_final=True))

    # --- A: FLAT cost (current production behavior) ---
    flat_claims = copy.deepcopy(all_claims)
    flat_ops = optimize_with_lambda_fn(
        flat_claims, all_evidence, all_edges,
        lambda_fn=lambda _cid: BASE_LAMBDA,
    )
    flat_resid = residual_total(residuals(flat_claims, all_evidence, all_edges, use_final=True))

    # --- B: STATURE-WEIGHTED cost (proposed flip) ---
    sta_claims = copy.deepcopy(all_claims)
    sta_ops = optimize_with_lambda_fn(
        sta_claims, all_evidence, all_edges,
        lambda_fn=lambda cid: lambda_for(cid, stature, new_claim_ids),
    )
    sta_resid = residual_total(residuals(sta_claims, all_evidence, all_edges, use_final=True))

    # Surviving residuals on the suspect node, both models.
    def edges_to_suspect(claims):
        return [r for r in residuals(claims, all_evidence, all_edges, use_final=True)
                if r["edge_id"].endswith("__" + SUSPECT_NODE) and r["residual_sq"] > 1e-4]

    return {
        "raw_residual": round(raw_total, 3),
        "stature_top": sorted(stature.items(), key=lambda kv: -kv[1])[:10],
        "stature_all": sorted(stature.items()),
        "semantic_edges": [
            {"edge_id": e["edge_id"], "claim_id": e["claim_id"],
             "evidence_id": e["evidence_id"],
             "base_value": e["base_prediction"]["dimensions"][0]["value"]}
            for e in semantic_edges
        ],
        "flat": {
            "lambda_claim": BASE_LAMBDA,
            "total_residual": round(flat_resid, 3),
            "operations": flat_ops,
            "suspect_surviving": [
                {"edge_id": r["edge_id"], "residual_sq": round(r["residual_sq"], 3)}
                for r in edges_to_suspect(flat_claims)
            ],
        },
        "stature_weighted": {
            "base_lambda": BASE_LAMBDA,
            "alpha": ALPHA,
            "new_claim_discount": NEW_CLAIM_DISCOUNT,
            "total_residual": round(sta_resid, 3),
            "operations": sta_ops,
            "suspect_surviving": [
                {"edge_id": r["edge_id"], "residual_sq": round(r["residual_sq"], 3)}
                for r in edges_to_suspect(sta_claims)
            ],
        },
    }


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def _established_ids(stature: dict[str, int]) -> set[str]:
    return {cid for cid, n in stature.items() if n >= ESTABLISHED_MIN_STATURE}


def _narrowing_amount(op: dict) -> float:
    return float(op["from"][1]) - float(op["to"][1])  # 0 = untouched, larger = more doubted


def report(out: dict) -> str:
    L: list[str] = []
    L.append("=" * 72)
    L.append("EPISTEMIC COST-FLIP -- PROTOTYPE")
    L.append("=" * 72)
    L.append(f"Raw map tension after splicing in the contribution: {out['raw_residual']}")
    L.append("")
    L.append("Top-stature claims in the prior map (# of independent backing papers):")
    for cid, n in out["stature_top"]:
        L.append(f"    {cid:14s}  {n} paper(s)")
    L.append("")

    flat = out["flat"]; sta = out["stature_weighted"]
    established = _established_ids(dict(out["stature_all"]))

    def summarize(model_label: str, model: dict, lam_label: str) -> None:
        L.append(f"-- {model_label} --")
        L.append(f"   {lam_label}")
        L.append(f"   accommodated residual: {model['total_residual']}")
        prior_ops = [op for op in model["operations"] if op["claim_id"] in established]
        new_ops = [op for op in model["operations"] if op["claim_id"] not in established]
        L.append(f"   established priors narrowed: {len(prior_ops)} "
                 f"(avg amount {round(sum(_narrowing_amount(o) for o in prior_ops)/max(len(prior_ops),1),2)})")
        for op in prior_ops:
            L.append(f"     - {op['claim_id']:12s}  {op['from']} -> {op['to']}   lambda={op['lambda']:.2f}")
        L.append(f"   incoming claims narrowed: {len(new_ops)}")
        for op in new_ops:
            L.append(f"     - {op['claim_id']:12s}  {op['from']} -> {op['to']}   lambda={op['lambda']:.2f}")
        L.append(f"   surviving tensions on {SUSPECT_NODE}: {len(model['suspect_surviving'])}")
        for r in model["suspect_surviving"]:
            L.append(f"     {r['edge_id']}  resid^2={r['residual_sq']}")
        L.append("")

    summarize("A: FLAT cost (current production model)",
              flat, f"lambda = {flat['lambda_claim']:.1f} for every claim")
    summarize("B: STATURE-WEIGHTED cost (proposed flip)",
              sta, f"lambda(c) = {sta['base_lambda']} * (1 + {sta['alpha']} * stature(c));  "
                   f"incoming-claim lambda = {sta['new_claim_discount']}")

    # Semantic cross-edges -- what got generated and why it matters.
    sem = out.get("semantic_edges", [])
    if sem:
        L.append(f"Semantic cross-edges generated ({len(sem)}):")
        L.append("  (Implicit-headline propagation: a claim that asserts a result")
        L.append("   without scoping it is held accountable across the comparability group.)")
        for e in sem:
            L.append(f"     {e['claim_id']:6s} -> {e['evidence_id']:32s}  predicted={e['base_value']}")
        L.append("")

    L.append("=" * 72)
    L.append("VERDICT")
    L.append("=" * 72)
    delta_resid = sta["total_residual"] - flat["total_residual"]
    flat_prior_amt = sum(_narrowing_amount(op) for op in flat["operations"] if op["claim_id"] in established)
    sta_prior_amt  = sum(_narrowing_amount(op) for op in sta["operations"] if op["claim_id"] in established)
    L.append(f"  Total prior-narrowing magnitude:  flat={round(flat_prior_amt,2)}   stature={round(sta_prior_amt,2)}")
    L.append(f"  Residual preserved by stature model: {round(delta_resid,3)} above flat")
    fully_refused = (sta_prior_amt == 0.0) and (delta_resid > 0.5)
    softened = (sta_prior_amt < flat_prior_amt - 0.01) and (delta_resid > 0.1)
    if fully_refused:
        L.append("")
        L.append("  -> Stature weighting REFUSES to narrow any established prior.")
        L.append("     The contradiction stays on the map as a live disagreement.")
        L.append("     No separate suspect-detection rule needed: the optimizer itself")
        L.append("     now defends the field's accumulated independent evidence.")
    elif softened:
        L.append("")
        L.append("  -> Stature weighting SOFTENS prior-narrowing and preserves residual,")
        L.append("     but the priors are not yet fully refused. Either raise ALPHA or")
        L.append("     enrich the stature signal (e.g. neighbor-agreement) until")
        L.append("     established priors cross from 'narrowed less' to 'untouched'.")
    else:
        L.append("")
        L.append("  -> No structural change yet. Tune ALPHA / NEW_CLAIM_DISCOUNT.")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# sweep (find the regime where established priors are fully refused)
# ---------------------------------------------------------------------------

def sweep(map_dir: Path, finding_dir: Path, finding_paper: str) -> str:
    map_claims, map_evidence = load_nodes(map_dir)
    src_claims, src_evidence = load_nodes(finding_dir)
    new_claims = [c for c in src_claims if c["paper_id"] == finding_paper]
    new_evidence = [e for e in src_evidence if e["paper_id"] == finding_paper]
    new_claim_ids = {c["claim_id"] for c in new_claims}
    stature = compute_stature(map_claims, map_evidence)
    established = _established_ids(stature)

    all_claims_base = copy.deepcopy(map_claims) + copy.deepcopy(new_claims)
    all_evidence = copy.deepcopy(map_evidence) + copy.deepcopy(new_evidence)
    for c in all_claims_base:
        c["x_final"] = list(c["x_init"])
    base_edges = generate_prediction_edges(all_claims_base, all_evidence)
    semantic_edges = generate_semantic_cross_edges(new_claims, all_evidence, base_edges)
    all_edges = base_edges + semantic_edges

    L: list[str] = []
    L.append("=" * 72)
    L.append("PARAMETER SWEEP -- where do established priors become untouchable?")
    L.append("=" * 72)
    L.append(f"{'alpha':>7}  {'discount':>9}  {'prior_narrow':>13}  {'incoming_narrow':>16}  {'resid':>7}")
    for alpha in (1.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0):
        for discount in (0.3,):
            claims = copy.deepcopy(all_claims_base)
            ops = optimize_with_lambda_fn(
                claims, all_evidence, all_edges,
                lambda_fn=lambda cid, _a=alpha, _d=discount: (
                    _d if cid in new_claim_ids
                    else BASE_LAMBDA * (1.0 + _a * stature.get(cid, 0))
                ),
            )
            prior_amt = sum(_narrowing_amount(op) for op in ops if op["claim_id"] in established)
            incoming_amt = sum(_narrowing_amount(op) for op in ops if op["claim_id"] in new_claim_ids)
            resid = residual_total(residuals(claims, all_evidence, all_edges, use_final=True))
            L.append(f"{alpha:>7.1f}  {discount:>9.2f}  {prior_amt:>13.2f}  {incoming_amt:>16.2f}  {resid:>7.3f}")
    L.append("")
    L.append("(prior_narrow drops to 0 -> established field defended;"
             " incoming_narrow > 0 -> system doubts the new claim instead)")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True, type=Path)
    ap.add_argument("--finding-from", required=True, type=Path)
    ap.add_argument("--finding-paper", required=True)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--sweep", action="store_true",
                    help="scan (alpha, discount) and report where priors become untouchable")
    args = ap.parse_args()
    if args.sweep:
        print(sweep(args.map, args.finding_from, args.finding_paper))
        print()
    out = run(args.map, args.finding_from, args.finding_paper)
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(report(out))


if __name__ == "__main__":
    main()
