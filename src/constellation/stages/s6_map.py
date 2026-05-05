"""Stage 6: MAP global section.

Input:  run.sheaf_path  (full compatibility cube populated by stage 5)
Output: run.sheaf_path  (map_section: selected, total_score, coherence,
                         rewrite_cost, alternative_sections, residual_h1)

PURE CODE — no LLM. Maximize coherence(σ) − λ × rewrite_cost(σ) over the
product space Π F(c). Exhaustive enumeration at MVP scale; this stage will
need a smarter solver (loopy BP / ILP) if |Π F(c)| ever exceeds ~10^5.

`residual_h1` lists every edge whose selected-pair score is ≤ 0. We
distinguish:
  - structural residual: max score on the edge is ≤ 0 — no rewrite resolves it
  - tradeoff residual:   max score > 0 but MAP picked a lower-scoring pair
                         because the variant is doing more work elsewhere
"""
from __future__ import annotations

import json
import time
from itertools import product

from rich.console import Console

from ..paths import Corpus, Run
from ..schemas import validate_sheaf

console = Console()

LAMBDA_REWRITE_PENALTY = 0.4   # architecture default
N_ALTERNATIVE_SECTIONS = 4     # how many runners-up to keep
ENUMERATE_LIMIT = 100_000      # use coord-ascent when |Π F(c)| exceeds this
COORD_ASCENT_RESTARTS = 5      # restarts to escape local optima


def _build_indexes(sheaf: dict) -> tuple[dict, dict, dict]:
    """Construct (variants_per_claim, rewrite_distance, score_by_pair)."""
    variants_per_claim: dict[str, list[str]] = {}
    rewrite_distance: dict[str, float] = {}
    for cid, stalk in sheaf["stalks"].items():
        variants_per_claim[cid] = [v["variant_id"] for v in stalk["variants"]]
        for v in stalk["variants"]:
            rewrite_distance[v["variant_id"]] = float(v["rewrite_distance"])

    score_by_pair: dict[tuple[str, str], dict] = {}
    for rm in sheaf["restriction_maps"]:
        for s in rm["compatibility_scores"]:
            score_by_pair[(s["variant_a_id"], s["variant_b_id"])] = {
                **s,
                "edge_id": rm["edge_id"],
                "claim_a": rm["claim_a"],
                "claim_b": rm["claim_b"],
            }
    return variants_per_claim, rewrite_distance, score_by_pair


def _evaluate_section(
    selected: dict[str, str],
    rms: list[dict],
    rewrite_distance: dict[str, float],
    score_by_pair: dict[tuple[str, str], dict],
    lam: float,
) -> dict:
    """Score one section. Returns {selected, coherence, rewrite_cost, total_score}."""
    coherence = 0.0
    for rm in rms:
        va = selected[rm["claim_a"]]
        vb = selected[rm["claim_b"]]
        coherence += score_by_pair[(va, vb)]["score"]
    rewrite_cost = sum(rewrite_distance[vid] for vid in selected.values())
    return {
        "selected": dict(selected),
        "coherence": coherence,
        "rewrite_cost": rewrite_cost,
        "total_score": coherence - lam * rewrite_cost,
    }


def _enumerate_sections(
    variants_per_claim: dict[str, list[str]],
    rms: list[dict],
    rewrite_distance: dict[str, float],
    score_by_pair: dict[tuple[str, str], dict],
    lam: float,
) -> list[dict]:
    """Score every section in the product space. Returned sorted by -total_score."""
    claim_ids = sorted(variants_per_claim.keys())
    variant_lists = [variants_per_claim[cid] for cid in claim_ids]
    sections: list[dict] = []
    for combo in product(*variant_lists):
        selected = dict(zip(claim_ids, combo, strict=True))
        sections.append(
            _evaluate_section(selected, rms, rewrite_distance, score_by_pair, lam)
        )
    sections.sort(key=lambda s: -s["total_score"])
    return sections


def _coord_ascent(
    variants_per_claim: dict[str, list[str]],
    rms: list[dict],
    rewrite_distance: dict[str, float],
    score_by_pair: dict[tuple[str, str], dict],
    lam: float,
    *,
    seed: dict[str, str] | None = None,
) -> dict:
    """Coordinate-ascent MAP solver — usable when |Π F(c)| is too large for
    exhaustive enumeration. Greedy: starting from the seed, iterate over each
    claim and switch to whichever variant locally maximizes total_score, holding
    every other claim fixed. Repeat until a full pass produces no change.

    Converges in O(n_claims × max_variants × n_passes × n_edges) time. Often
    finds the global optimum; can get stuck in local optima — caller should
    multi-restart and keep the best.
    """
    claim_ids = sorted(variants_per_claim.keys())
    if seed is None:
        # Default seed: every claim's first variant (canonically the original)
        selected = {cid: variants_per_claim[cid][0] for cid in claim_ids}
    else:
        selected = dict(seed)

    # Per-claim edge index for fast incremental scoring
    edges_by_claim: dict[str, list[dict]] = {cid: [] for cid in claim_ids}
    for rm in rms:
        edges_by_claim[rm["claim_a"]].append(rm)
        edges_by_claim[rm["claim_b"]].append(rm)

    def _claim_local_score(cid: str, vid: str) -> float:
        """Sum of compatibility on every edge touching `cid`, with `cid`
        assigned variant `vid` and all other selections held fixed.
        Plus the −λ·rewrite_distance contribution from this claim."""
        coh = 0.0
        for rm in edges_by_claim[cid]:
            other = rm["claim_b"] if rm["claim_a"] == cid else rm["claim_a"]
            other_vid = selected[other]
            if rm["claim_a"] == cid:
                key = (vid, other_vid)
            else:
                key = (other_vid, vid)
            coh += score_by_pair[key]["score"]
        return coh - lam * rewrite_distance[vid]

    changed = True
    while changed:
        changed = False
        for cid in claim_ids:
            variants = variants_per_claim[cid]
            if len(variants) == 1:
                continue
            best_vid = selected[cid]
            best_local = _claim_local_score(cid, best_vid)
            for vid in variants:
                if vid == best_vid:
                    continue
                s = _claim_local_score(cid, vid)
                if s > best_local + 1e-12:
                    best_local = s
                    best_vid = vid
            if best_vid != selected[cid]:
                selected[cid] = best_vid
                changed = True

    return _evaluate_section(selected, rms, rewrite_distance, score_by_pair, lam)


def _coord_ascent_multistart(
    variants_per_claim: dict[str, list[str]],
    rms: list[dict],
    rewrite_distance: dict[str, float],
    score_by_pair: dict[tuple[str, str], dict],
    lam: float,
    n_restarts: int,
) -> list[dict]:
    """Run coordinate ascent from multiple seeds; return all found sections
    sorted by −total_score. Seeds: first is all-originals; remaining are random.
    """
    import random

    rng = random.Random(0xC0DE)
    claim_ids = sorted(variants_per_claim.keys())

    seeds = [None]   # all-originals seed
    for _ in range(max(0, n_restarts - 1)):
        seeds.append({cid: rng.choice(variants_per_claim[cid]) for cid in claim_ids})

    seen: dict[tuple, dict] = {}
    for seed in seeds:
        result = _coord_ascent(
            variants_per_claim, rms, rewrite_distance, score_by_pair, lam, seed=seed
        )
        # De-dup by selected tuple
        key = tuple(sorted(result["selected"].items()))
        if key not in seen or seen[key]["total_score"] < result["total_score"]:
            seen[key] = result
    sections = list(seen.values())
    sections.sort(key=lambda s: -s["total_score"])
    return sections


def _residual_h1(
    selected: dict[str, str],
    rms: list[dict],
    score_by_pair: dict[tuple[str, str], dict],
) -> list[dict]:
    """Edges where the MAP-selected pair scores ≤ 0, with structural-vs-tradeoff
    annotation."""
    residual = []
    for rm in rms:
        va = selected[rm["claim_a"]]
        vb = selected[rm["claim_b"]]
        s = score_by_pair[(va, vb)]
        if s["score"] > 0:
            continue
        max_on_edge = max(c["score"] for c in rm["compatibility_scores"])
        if max_on_edge <= 0:
            why = (
                f"Structural: every variant pair on this edge scored ≤ 0 "
                f"(max {max_on_edge:+.2f}). No rewrite within evidence-faithful "
                f"distance resolves the contradiction. Selected pair scored "
                f"{s['score']:+.2f} ({s['kind']})."
            )
        else:
            why = (
                f"Tradeoff: a higher-scoring pair exists on this edge "
                f"(max {max_on_edge:+.2f}) but MAP chose {va} ↔ {vb} "
                f"(score {s['score']:+.2f}, kind {s['kind']}) because the "
                f"variant choice was driven by a different edge."
            )
        residual.append(
            {
                "edge_id": rm["edge_id"],
                "claim_a": rm["claim_a"],
                "claim_b": rm["claim_b"],
                "selected_score": s["score"],
                "why_unresolved": why,
            }
        )
    return residual


def run(corpus: Corpus, run: Run) -> None:  # noqa: A002 (intentional shadow)
    if not run.sheaf_path.exists():
        raise RuntimeError(
            f"missing sheaf.json under {run.root}; run stages 4 + 5 first"
        )
    sheaf = json.loads(run.sheaf_path.read_text())

    variants_per_claim, rewrite_distance, score_by_pair = _build_indexes(sheaf)

    n_sections = 1
    for v in variants_per_claim.values():
        n_sections *= len(v)

    use_enumerate = n_sections <= ENUMERATE_LIMIT
    method = "enumerate" if use_enumerate else "coord_ascent"
    if use_enumerate:
        console.print(
            f"stage 6: enumerating MAP section over {n_sections:,} candidates "
            f"(λ = {LAMBDA_REWRITE_PENALTY})"
        )
    else:
        console.print(
            f"stage 6: section space is {n_sections:,} "
            f"(> {ENUMERATE_LIMIT:,} limit) — using coord ascent with "
            f"{COORD_ASCENT_RESTARTS} restarts (λ = {LAMBDA_REWRITE_PENALTY})"
        )

    t0 = time.perf_counter()
    if use_enumerate:
        sections = _enumerate_sections(
            variants_per_claim,
            sheaf["restriction_maps"],
            rewrite_distance,
            score_by_pair,
            LAMBDA_REWRITE_PENALTY,
        )
    else:
        sections = _coord_ascent_multistart(
            variants_per_claim,
            sheaf["restriction_maps"],
            rewrite_distance,
            score_by_pair,
            LAMBDA_REWRITE_PENALTY,
            n_restarts=COORD_ASCENT_RESTARTS,
        )
    runtime_ms = (time.perf_counter() - t0) * 1000.0

    winner = sections[0]
    alts_kept = sections[1 : 1 + N_ALTERNATIVE_SECTIONS]

    residual = _residual_h1(
        winner["selected"], sheaf["restriction_maps"], score_by_pair
    )

    sheaf["map_section"] = {
        "selected": winner["selected"],
        "total_score": winner["total_score"],
        "coherence": winner["coherence"],
        "rewrite_cost": winner["rewrite_cost"],
        "lambda_rewrite_penalty": LAMBDA_REWRITE_PENALTY,
        "alternative_sections": [
            {
                "selected": a["selected"],
                "total_score": a["total_score"],
                "coherence": a["coherence"],
                "rewrite_cost": a["rewrite_cost"],
                "rank": i + 2,
            }
            for i, a in enumerate(alts_kept)
        ],
        "residual_h1": residual,
        "solver": {
            "method": method,
            "runtime_ms": runtime_ms,
            "n_sections_evaluated": len(sections),
            "section_space_size": n_sections,
        },
    }
    sheaf["extraction"]["notes"] = (
        sheaf["extraction"].get("notes", "")
        + f" Stage 6 selected MAP section by exhaustive enumeration "
        f"(λ={LAMBDA_REWRITE_PENALTY})."
    )
    run.sheaf_path.write_text(json.dumps(sheaf, indent=2))

    # Validate now — sheaf is schema-complete except for frustration (optional)
    validate_sheaf(sheaf)

    # Operator summary
    n_rewritten = sum(
        1 for vid in winner["selected"].values() if not vid.endswith("#original")
    )
    n_residual_structural = sum(
        1 for r in residual if r["why_unresolved"].startswith("Structural")
    )
    n_residual_tradeoff = len(residual) - n_residual_structural
    console.print(
        f"  enumerated {len(sections)} sections in {runtime_ms:.1f} ms"
    )
    console.print(
        f"  [bold green]winner[/bold green]: total {winner['total_score']:+.2f} "
        f"(coherence {winner['coherence']:+.2f} − {LAMBDA_REWRITE_PENALTY}×rewrite "
        f"{winner['rewrite_cost']:.2f})"
    )
    console.print(
        f"  rewrites picked: {n_rewritten}/{len(winner['selected'])} claims"
    )
    if n_rewritten:
        for cid, vid in winner["selected"].items():
            if not vid.endswith("#original"):
                console.print(f"    [yellow]→[/yellow] {cid}: {vid.split('#', 1)[1]}")
    console.print(
        f"  residual H¹: [bold]{len(residual)}[/bold] edges "
        f"({n_residual_structural} structural, {n_residual_tradeoff} tradeoff)"
    )
    if alts_kept:
        gap = winner["total_score"] - alts_kept[0]["total_score"]
        console.print(
            f"  margin to runner-up: {gap:+.3f} "
            f"({'[green]decisive[/green]' if gap > 0.5 else '[yellow]close[/yellow]'})"
        )
