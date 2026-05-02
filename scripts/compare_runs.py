"""Compare two pipeline runs side by side.

Usage:
    python scripts/compare_runs.py runs/shumlak_OLDts/ runs/shumlak_NEWts/

Reports stable-vs-drifted on the metrics that matter:
  - paper / claim / edge / Idea counts
  - which edges are contested (i.e. orig-orig score < 0)
  - which claims got rewritten by MAP
  - residual H¹ edge_ids
  - Penrose triangle vertex sets
  - per-Idea claim sets (paper-aligned vs cross-paper)

Pure read-only — never mutates the run directories.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load_run(root: Path) -> dict:
    sheaf = json.loads((root / "sheaf.json").read_text())
    ideas = [json.loads(p.read_text()) for p in sorted((root / "ideas").glob("*.json"))]
    claims = sorted((root / "claims").glob("*.json"))
    papers = sorted((root / "papers").glob("*.json"))
    return {"sheaf": sheaf, "ideas": ideas, "n_claims": len(claims), "n_papers": len(papers)}


def contested_edges(sheaf: dict) -> set[tuple[str, str]]:
    """Edges whose original-original score is < 0."""
    out: set[tuple[str, str]] = set()
    for rm in sheaf["restriction_maps"]:
        for s in rm["compatibility_scores"]:
            if "#original" in s["variant_a_id"] and "#original" in s["variant_b_id"]:
                if s["score"] < 0:
                    out.add((rm["claim_a"], rm["claim_b"]))
                break
    return out


def map_rewrites(sheaf: dict) -> set[str]:
    """claim_ids that MAP rewrote (selected variant != #original)."""
    return {
        cid
        for cid, vid in sheaf["map_section"]["selected"].items()
        if not vid.endswith("#original")
    }


def residual_pairs(sheaf: dict) -> set[tuple[str, str]]:
    return {
        (r["claim_a"], r["claim_b"])
        for r in sheaf["map_section"].get("residual_h1", [])
    }


def penrose_sets(sheaf: dict) -> set[frozenset]:
    return {frozenset(t) for t in sheaf.get("frustration", {}).get("penrose_triangles", [])}


def idea_partition(ideas: list[dict]) -> list[set[str]]:
    return [{c["claim_id"] for c in idea["contributing_claims"]} for idea in ideas]


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / max(len(a | b), 1)


def best_jaccard_pairing(parts_a: list[set], parts_b: list[set]) -> float:
    """Greedy best matching: avg Jaccard over best assignment of A's parts to B's parts."""
    if not parts_a or not parts_b:
        return 0.0
    used: set[int] = set()
    sims = []
    for sa in parts_a:
        best_idx, best_sim = -1, -1.0
        for j, sb in enumerate(parts_b):
            if j in used:
                continue
            s = jaccard(sa, sb)
            if s > best_sim:
                best_idx, best_sim = j, s
        if best_idx >= 0:
            used.add(best_idx)
            sims.append(best_sim)
    return sum(sims) / len(sims) if sims else 0.0


def report(label: str, lhs, rhs, formatter=str) -> None:
    eq = lhs == rhs
    marker = "[stable]" if eq else "[drift]"
    print(f"  {marker} {label}")
    if not eq:
        print(f"      OLD: {formatter(lhs)}")
        print(f"      NEW: {formatter(rhs)}")


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    old_root, new_root = Path(sys.argv[1]), Path(sys.argv[2])
    old = load_run(old_root)
    new = load_run(new_root)

    print(f"\nComparing: {old_root.name}  vs  {new_root.name}\n")

    print("== Counts ==")
    report("n papers", old["n_papers"], new["n_papers"])
    report("n claims", old["n_claims"], new["n_claims"])
    report("n edges", len(old["sheaf"]["restriction_maps"]), len(new["sheaf"]["restriction_maps"]))
    report("n Ideas", len(old["ideas"]), len(new["ideas"]))

    print("\n== Sheaf structure ==")
    o_contested = contested_edges(old["sheaf"])
    n_contested = contested_edges(new["sheaf"])
    print(f"  contested edges: OLD={len(o_contested)}  NEW={len(n_contested)}")
    if o_contested or n_contested:
        common = o_contested & n_contested
        print(f"    common: {len(common)}; OLD only: {len(o_contested - n_contested)}; NEW only: {len(n_contested - o_contested)}")

    o_rewrites = map_rewrites(old["sheaf"])
    n_rewrites = map_rewrites(new["sheaf"])
    print(f"  MAP rewrites: OLD={len(o_rewrites)}  NEW={len(n_rewrites)}")
    print(f"    common claim_ids rewritten: {sorted(o_rewrites & n_rewrites)}")

    o_resid = residual_pairs(old["sheaf"])
    n_resid = residual_pairs(new["sheaf"])
    report("residual H¹ pairs", o_resid, n_resid, lambda s: sorted(s))

    o_pen = penrose_sets(old["sheaf"])
    n_pen = penrose_sets(new["sheaf"])
    print(f"  Penrose triangles: OLD={len(o_pen)}  NEW={len(n_pen)}")
    if o_pen != n_pen:
        print(f"    OLD: {[sorted(t) for t in o_pen]}")
        print(f"    NEW: {[sorted(t) for t in n_pen]}")

    print("\n== MAP scoring ==")
    om = old["sheaf"]["map_section"]
    nm = new["sheaf"]["map_section"]
    print(f"  coherence:    OLD={om['coherence']:+.2f}   NEW={nm['coherence']:+.2f}")
    print(f"  rewrite_cost: OLD={om['rewrite_cost']:.2f}    NEW={nm['rewrite_cost']:.2f}")
    print(f"  total_score:  OLD={om['total_score']:+.2f}   NEW={nm['total_score']:+.2f}")
    print(f"  ρ (Penrose): OLD={old['sheaf']['frustration']['rho']:.3f}  NEW={new['sheaf']['frustration']['rho']:.3f}")

    print("\n== Idea partition ==")
    op = idea_partition(old["ideas"])
    np_ = idea_partition(new["ideas"])
    sim = best_jaccard_pairing(op, np_)
    print(f"  best-pairing Jaccard similarity: {sim:.3f}")
    print(f"  OLD partition sizes: {sorted(len(p) for p in op)}")
    print(f"  NEW partition sizes: {sorted(len(p) for p in np_)}")
    print(f"  OLD cross-paper Ideas: {sum(1 for p in op if len({c.split(':')[0] for c in p}) > 1)}/{len(op)}")
    print(f"  NEW cross-paper Ideas: {sum(1 for p in np_ if len({c.split(':')[0] for c in p}) > 1)}/{len(np_)}")


if __name__ == "__main__":
    main()
