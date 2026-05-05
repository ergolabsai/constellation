"""Stage 3: build the comparability complex.

Input:  run.tag_vocabulary_path, run.tags_path
Output: run.complex_path  (edge list with semilattice meet + SNAG overlap)

PURE CODE — no LLM. Two claims form an edge iff:
  1. Their semilattice coordinates meet on every dimension (regime-compatible)
  2. Their SNAG node lists overlap by at least the configured threshold

Per-dimension meet rules:
  - discrete:        meet exists iff values are equal
  - hierarchical:    meet is the lowest common ancestor in the hierarchy;
                     None if values are on different roots
  - set_inclusion:   meet is the set intersection; None if empty
  - null on either side is treated as "no constraint" (trivially compatible)
  - any value listed in the dimension's optional `wildcards` array is
    "compatible with all" — meet with anything else exists and equals the
    other side. This handles cases like physics_framework=experimental, which
    the architecture says is comparable with any model level.
"""
from __future__ import annotations

import json
from itertools import combinations
from typing import Any

from rich.console import Console

from ..config import stage_config
from ..paths import Corpus, Run

console = Console()


def _hierarchical_meet(
    va: str, vb: str, hierarchy: dict[str, str | None]
) -> str | None:
    """LCA of va and vb in the hierarchy. None if on different roots.

    Each value's parent is `hierarchy[value]`; root values have parent None.
    The meet (LCA) is the deepest value present in both ancestor chains.
    Per the architecture: this is the COARSER (more general) of the two when
    one is an ancestor of the other.
    """
    if va == vb:
        return va

    def chain(v: str) -> list[str]:
        out = [v]
        cur = v
        while hierarchy.get(cur) is not None:
            cur = hierarchy[cur]  # type: ignore[assignment]
            out.append(cur)
        return out

    a_chain = chain(va)
    b_chain = chain(vb)

    # Walk b_chain from leaf to root; first hit in a_set is the LCA.
    a_set = set(a_chain)
    for v in b_chain:
        if v in a_set:
            return v
    return None


def _per_dim_meet(
    va: Any, vb: Any, dim: dict
) -> tuple[Any, bool]:
    """Compute meet for one dimension. Returns (meet_value, compatible)."""
    if va is None and vb is None:
        return None, True
    if va is None:
        return vb, True
    if vb is None:
        return va, True

    # Wildcards are string labels (hashable); guard so list-valued set_inclusion
    # values don't blow up the membership test.
    wildcards = set(dim.get("wildcards", []))
    a_wild = isinstance(va, str) and va in wildcards
    b_wild = isinstance(vb, str) and vb in wildcards
    if a_wild and b_wild:
        return va, True  # both wildcards; pick either
    if a_wild:
        return vb, True  # va is "compatible with all"; meet = vb
    if b_wild:
        return va, True

    ordering = dim["ordering"]
    if ordering == "discrete":
        return (va, True) if va == vb else (None, False)
    if ordering == "hierarchical":
        m = _hierarchical_meet(va, vb, dim.get("hierarchy", {}))
        return (m, m is not None)
    if ordering == "set_inclusion":
        sa = {va} if isinstance(va, str) else set(va)
        sb = {vb} if isinstance(vb, str) else set(vb)
        inter = sa & sb
        if not inter:
            return None, False
        return (sorted(inter) if len(inter) > 1 else next(iter(inter))), True
    # Unknown ordering: fall back to strict equality
    return (va, True) if va == vb else (None, False)


def _semilattice_meet(
    sl_a: dict, sl_b: dict, vocab: dict
) -> tuple[dict | None, list[str]]:
    """Compute the full semilattice meet across all dimensions.

    Returns (meet_dict, incompatible_dims). The meet_dict is non-None iff
    every dimension is compatible. incompatible_dims lists the dims where the
    meet failed — useful for filter-attribution stats even when the pair is
    rejected.
    """
    meet: dict[str, Any] = {}
    incompatible: list[str] = []

    for dim in vocab["semilattice_dimensions"]:
        name = dim["name"]
        m, ok = _per_dim_meet(sl_a.get(name), sl_b.get(name), dim)
        if ok:
            meet[name] = m
        else:
            incompatible.append(name)

    if incompatible:
        return None, incompatible
    return meet, []


def _snag_overlap(snag_a: list[str], snag_b: list[str]) -> list[str]:
    """Sorted list of shared canonical SNAG node names."""
    return sorted(set(snag_a) & set(snag_b))


def _edge_id(a: str, b: str) -> str:
    """Stable edge id, alphabetically lower first."""
    lo, hi = sorted([a, b])
    return f"edge:{lo}↔{hi}"


def run(corpus: Corpus, run: Run) -> None:  # noqa: A002 (intentional shadow)
    if not run.tag_vocabulary_path.exists() or not run.tags_path.exists():
        raise RuntimeError(
            f"missing tag artifacts under {run.root}; run stage 2 first"
        )

    cfg = stage_config(run, corpus, "stage3_complex")
    snag_overlap_threshold = int(cfg["snag_overlap_threshold"])

    vocab = json.loads(run.tag_vocabulary_path.read_text())
    tags = json.loads(run.tags_path.read_text())
    claim_ids = sorted(tags.keys())

    console.print(
        f"building comparability complex over {len(claim_ids)} claims"
    )
    console.print(
        f"  semilattice: {len(vocab['semilattice_dimensions'])} dims, "
        f"snag overlap threshold: ≥{snag_overlap_threshold}"
    )

    edges: list[dict] = []
    n_pairs_total = 0
    n_semi_compat = 0
    n_snag_compat = 0
    semi_filter_counts: dict[str, int] = {
        d["name"]: 0 for d in vocab["semilattice_dimensions"]
    }
    snag_overlap_dist_all: dict[int, int] = {}  # over semilattice-compat pairs

    for cid_a, cid_b in combinations(claim_ids, 2):
        n_pairs_total += 1
        sl_a = tags[cid_a]["semilattice"]
        sl_b = tags[cid_b]["semilattice"]

        meet, incompatible = _semilattice_meet(sl_a, sl_b, vocab)
        if meet is None:
            for d in incompatible:
                semi_filter_counts[d] += 1
            continue

        n_semi_compat += 1

        overlap = _snag_overlap(tags[cid_a]["snag_nodes"], tags[cid_b]["snag_nodes"])
        snag_overlap_dist_all[len(overlap)] = (
            snag_overlap_dist_all.get(len(overlap), 0) + 1
        )

        if len(overlap) < snag_overlap_threshold:
            continue

        n_snag_compat += 1
        edges.append(
            {
                "edge_id": _edge_id(cid_a, cid_b),
                "claim_a": cid_a,
                "claim_b": cid_b,
                "semilattice_meet": meet,
                "snag_overlap": overlap,
                "snag_overlap_count": len(overlap),
            }
        )

    # Edges (not all pairs) — overlap distribution among accepted edges
    edge_overlap_dist: dict[int, int] = {}
    for e in edges:
        edge_overlap_dist[e["snag_overlap_count"]] = (
            edge_overlap_dist.get(e["snag_overlap_count"], 0) + 1
        )

    output = {
        "n_claims": len(claim_ids),
        "n_edges": len(edges),
        "config": {"snag_overlap_threshold": snag_overlap_threshold},
        "claim_ids": claim_ids,
        "edges": edges,
        "stats": {
            "n_pairs_total": n_pairs_total,
            "n_pairs_semilattice_compatible": n_semi_compat,
            "n_pairs_both_compatible": n_snag_compat,
            "pairs_filtered_by_semilattice_dim": dict(
                sorted(semi_filter_counts.items(), key=lambda kv: -kv[1])
            ),
            "snag_overlap_distribution_among_semicompatible": dict(
                sorted(snag_overlap_dist_all.items())
            ),
            "snag_overlap_distribution_among_edges": dict(
                sorted(edge_overlap_dist.items())
            ),
        },
    }
    run.complex_path.write_text(json.dumps(output, indent=2))

    console.print(f"  pairs total: {n_pairs_total}")
    console.print(f"  pairs semilattice-compatible: {n_semi_compat}")
    console.print(
        f"  edges (also ≥{snag_overlap_threshold} SNAG overlap): "
        f"[bold green]{len(edges)}[/bold green]"
    )
    nonzero_filters = [(k, v) for k, v in semi_filter_counts.items() if v > 0]
    if nonzero_filters:
        nonzero_filters.sort(key=lambda kv: -kv[1])
        console.print(
            "  semilattice filtering by dim: "
            + ", ".join(f"{k}={v}" for k, v in nonzero_filters)
        )
