"""Tests for stage 7 helpers (pure code, no LLM)."""
from __future__ import annotations

from constellation.stages.s7_frustration import (
    _build_signed_graph,
    _classify,
    _enumerate_triangles,
)


def _sheaf_with_signs(*, edges: list[tuple[str, str, float]]) -> dict:
    """Tiny sheaf where every claim's MAP-selected variant is `#original`.
    `edges` is a list of (claim_a, claim_b, score) tuples."""
    claim_ids = sorted({c for e in edges for c in e[:2]})
    return {
        "stalks": {
            cid: {
                "claim_id": cid,
                "variants": [{"variant_id": f"{cid}#original", "rewrite_distance": 0.0}],
            }
            for cid in claim_ids
        },
        "restriction_maps": [
            {
                "edge_id": f"restriction:{a}↔{b}",
                "claim_a": a,
                "claim_b": b,
                "compatibility_scores": [
                    {
                        "variant_a_id": f"{a}#original",
                        "variant_b_id": f"{b}#original",
                        "score": score,
                    }
                ],
            }
            for a, b, score in edges
        ],
        "map_section": {
            "selected": {cid: f"{cid}#original" for cid in claim_ids}
        },
    }


# ---------- _build_signed_graph ----------------------------------------------


def test_build_signed_graph_assigns_signs():
    sheaf = _sheaf_with_signs(
        edges=[("a", "b", 0.5), ("b", "c", -0.3), ("a", "c", 0.0)]
    )
    adj = _build_signed_graph(sheaf)
    assert adj["a"]["b"] == 1
    assert adj["b"]["a"] == 1
    assert adj["b"]["c"] == -1
    assert adj["a"]["c"] == 0


# ---------- _enumerate_triangles ---------------------------------------------


def test_enumerate_triangles_finds_3cycles():
    sheaf = _sheaf_with_signs(
        edges=[("a", "b", 1), ("b", "c", 1), ("a", "c", 1)]
    )
    adj = _build_signed_graph(sheaf)
    tris = _enumerate_triangles(adj)
    assert tris == [("a", "b", "c")]


def test_enumerate_triangles_skips_paths_without_closure():
    # a-b-c is a path, not a triangle (no a-c edge)
    sheaf = _sheaf_with_signs(edges=[("a", "b", 1), ("b", "c", 1)])
    adj = _build_signed_graph(sheaf)
    assert _enumerate_triangles(adj) == []


def test_enumerate_triangles_handles_multiple():
    # K4 -> 4 triangles
    sheaf = _sheaf_with_signs(
        edges=[
            ("a", "b", 1), ("a", "c", 1), ("a", "d", 1),
            ("b", "c", 1), ("b", "d", 1), ("c", "d", 1),
        ]
    )
    adj = _build_signed_graph(sheaf)
    tris = _enumerate_triangles(adj)
    assert len(tris) == 4
    # Each triangle is sorted lexicographically
    for a, b, c in tris:
        assert a < b < c


# ---------- _classify --------------------------------------------------------


def test_classify_returns_signs_in_canonical_order():
    sheaf = _sheaf_with_signs(
        edges=[("a", "b", 0.5), ("a", "c", -0.5), ("b", "c", 0.5)]
    )
    adj = _build_signed_graph(sheaf)
    s_ab, s_ac, s_bc = _classify(("a", "b", "c"), adj)
    assert s_ab == 1
    assert s_ac == -1
    assert s_bc == 1


# ---------- end-to-end: balanced vs Penrose ---------------------------------


def test_balanced_triangle_is_not_penrose():
    """All-positive triangle: product +1, balanced."""
    sheaf = _sheaf_with_signs(
        edges=[("a", "b", 0.5), ("a", "c", 0.5), ("b", "c", 0.5)]
    )
    adj = _build_signed_graph(sheaf)
    s_ab, s_ac, s_bc = _classify(("a", "b", "c"), adj)
    assert s_ab * s_ac * s_bc > 0


def test_penrose_triangle_has_negative_product():
    """One-negative triangle: product -1, frustrated."""
    sheaf = _sheaf_with_signs(
        edges=[("a", "b", 0.5), ("a", "c", 0.5), ("b", "c", -0.5)]
    )
    adj = _build_signed_graph(sheaf)
    s_ab, s_ac, s_bc = _classify(("a", "b", "c"), adj)
    assert s_ab * s_ac * s_bc < 0


def test_three_negative_triangle_is_penrose():
    """All-negative triangle: product -1, frustrated."""
    sheaf = _sheaf_with_signs(
        edges=[("a", "b", -0.5), ("a", "c", -0.5), ("b", "c", -0.5)]
    )
    adj = _build_signed_graph(sheaf)
    s_ab, s_ac, s_bc = _classify(("a", "b", "c"), adj)
    assert s_ab * s_ac * s_bc < 0
