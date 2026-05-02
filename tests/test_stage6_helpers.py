"""Tests for stage 6 helpers (pure code, no LLM)."""
from __future__ import annotations

from constellation.stages.s6_map import (
    _build_indexes,
    _enumerate_sections,
    _evaluate_section,
    _residual_h1,
)


def _toy_sheaf() -> dict:
    """3-claim toy with 1 stalk having 2 variants and 2 restriction edges."""
    return {
        "stalks": {
            "p:01": {
                "claim_id": "p:01",
                "variants": [
                    {"variant_id": "p:01#original", "rewrite_distance": 0.0},
                    {"variant_id": "p:01#alt", "rewrite_distance": 0.3},
                ],
            },
            "p:02": {
                "claim_id": "p:02",
                "variants": [{"variant_id": "p:02#original", "rewrite_distance": 0.0}],
            },
            "p:03": {
                "claim_id": "p:03",
                "variants": [{"variant_id": "p:03#original", "rewrite_distance": 0.0}],
            },
        },
        "restriction_maps": [
            {
                "edge_id": "restriction:p:01↔p:02",
                "claim_a": "p:01",
                "claim_b": "p:02",
                "compatibility_scores": [
                    {"variant_a_id": "p:01#original", "variant_b_id": "p:02#original",
                     "score": -0.5, "kind": "contradiction"},
                    {"variant_a_id": "p:01#alt", "variant_b_id": "p:02#original",
                     "score": +0.4, "kind": "qualification"},
                ],
            },
            {
                "edge_id": "restriction:p:02↔p:03",
                "claim_a": "p:02",
                "claim_b": "p:03",
                "compatibility_scores": [
                    {"variant_a_id": "p:02#original", "variant_b_id": "p:03#original",
                     "score": +0.6, "kind": "agreement"},
                ],
            },
        ],
    }


# ---------- _build_indexes ---------------------------------------------------


def test_build_indexes_extracts_variants_and_distances():
    vpc, rd, sbp = _build_indexes(_toy_sheaf())
    assert vpc == {
        "p:01": ["p:01#original", "p:01#alt"],
        "p:02": ["p:02#original"],
        "p:03": ["p:03#original"],
    }
    assert rd["p:01#alt"] == 0.3
    assert rd["p:01#original"] == 0.0
    assert ("p:01#original", "p:02#original") in sbp
    assert sbp[("p:01#alt", "p:02#original")]["score"] == 0.4


# ---------- _evaluate_section ------------------------------------------------


def test_evaluate_section_sums_coherence_and_rewrite_cost():
    sheaf = _toy_sheaf()
    _, rd, sbp = _build_indexes(sheaf)
    selected = {"p:01": "p:01#alt", "p:02": "p:02#original", "p:03": "p:03#original"}
    result = _evaluate_section(selected, sheaf["restriction_maps"], rd, sbp, lam=0.4)
    # coherence: 0.4 (alt↔orig) + 0.6 (orig↔orig) = 1.0
    assert result["coherence"] == 1.0
    # rewrite cost: 0.3 + 0 + 0 = 0.3
    assert result["rewrite_cost"] == 0.3
    # total = 1.0 - 0.4 * 0.3 = 0.88
    assert abs(result["total_score"] - 0.88) < 1e-9


# ---------- _enumerate_sections ----------------------------------------------


def test_enumerate_sections_explores_full_product_space_and_picks_best():
    sheaf = _toy_sheaf()
    vpc, rd, sbp = _build_indexes(sheaf)
    sections = _enumerate_sections(vpc, sheaf["restriction_maps"], rd, sbp, lam=0.4)
    # Product space: 2 × 1 × 1 = 2 sections
    assert len(sections) == 2
    # Sorted by -total_score
    assert sections[0]["total_score"] >= sections[1]["total_score"]
    # Winner should be alt (coherence 1.0 - 0.12 = 0.88) over original (0.1 - 0 = 0.1)
    assert sections[0]["selected"]["p:01"] == "p:01#alt"


def test_enumerate_sections_respects_lambda():
    sheaf = _toy_sheaf()
    vpc, rd, sbp = _build_indexes(sheaf)
    # With huge lambda, original wins (rewrite cost dominates)
    sections = _enumerate_sections(vpc, sheaf["restriction_maps"], rd, sbp, lam=100.0)
    assert sections[0]["selected"]["p:01"] == "p:01#original"


# ---------- _residual_h1 -----------------------------------------------------


def test_residual_h1_empty_when_all_selected_positive():
    sheaf = _toy_sheaf()
    _, _, sbp = _build_indexes(sheaf)
    selected = {"p:01": "p:01#alt", "p:02": "p:02#original", "p:03": "p:03#original"}
    residual = _residual_h1(selected, sheaf["restriction_maps"], sbp)
    assert residual == []


def test_residual_h1_marks_tradeoff_when_better_pair_exists():
    """If MAP picks a low-scoring pair on an edge but a better pair was available."""
    sheaf = _toy_sheaf()
    _, _, sbp = _build_indexes(sheaf)
    # Force selection of original on p:01 — that puts p:01↔p:02 at -0.5 (contradiction)
    # but the alt variant could have scored +0.4 on the same edge.
    selected = {"p:01": "p:01#original", "p:02": "p:02#original", "p:03": "p:03#original"}
    residual = _residual_h1(selected, sheaf["restriction_maps"], sbp)
    assert len(residual) == 1
    assert residual[0]["selected_score"] == -0.5
    assert residual[0]["why_unresolved"].startswith("Tradeoff")


def test_residual_h1_marks_structural_when_no_pair_positive():
    """If every variant pair on an edge is ≤ 0, residual is structural."""
    sheaf = _toy_sheaf()
    # Mutate: drop the +0.4 pair so the edge has no positive option
    sheaf["restriction_maps"][0]["compatibility_scores"] = [
        {"variant_a_id": "p:01#original", "variant_b_id": "p:02#original",
         "score": -0.5, "kind": "contradiction"},
        {"variant_a_id": "p:01#alt", "variant_b_id": "p:02#original",
         "score": -0.3, "kind": "contradiction"},
    ]
    _, _, sbp = _build_indexes(sheaf)
    selected = {"p:01": "p:01#alt", "p:02": "p:02#original", "p:03": "p:03#original"}
    residual = _residual_h1(selected, sheaf["restriction_maps"], sbp)
    assert len(residual) == 1
    assert residual[0]["why_unresolved"].startswith("Structural")
