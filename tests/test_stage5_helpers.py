"""Tests for stage 5 helpers (no LLM calls)."""
from __future__ import annotations

from constellation.scoring import VariantHandle
from constellation.stages.s5_compatibility import _existing_pairs, _missing_pairs


def _vh(claim_id: str, variant_id: str) -> VariantHandle:
    return VariantHandle(
        claim_id=claim_id,
        variant_id=variant_id,
        text=f"text of {variant_id}",
        full_claim={"claim_id": claim_id},
    )


def test_existing_pairs_extracts_id_tuples():
    rm = {
        "compatibility_scores": [
            {"variant_a_id": "p:01#original", "variant_b_id": "p:02#original", "score": 0.5},
            {"variant_a_id": "p:01#alt_x", "variant_b_id": "p:02#original", "score": 0.7},
        ]
    }
    assert _existing_pairs(rm) == {
        ("p:01#original", "p:02#original"),
        ("p:01#alt_x", "p:02#original"),
    }


def test_existing_pairs_handles_missing_field():
    assert _existing_pairs({}) == set()


def test_missing_pairs_skips_already_scored():
    rm = {
        "compatibility_scores": [
            {"variant_a_id": "p:01#original", "variant_b_id": "p:02#original", "score": 0.5},
        ]
    }
    a = [_vh("p:01", "p:01#original"), _vh("p:01", "p:01#alt_x")]
    b = [_vh("p:02", "p:02#original")]
    missing = _missing_pairs(rm, a, b)
    # Should skip the (orig, orig) and produce only (alt, orig)
    assert len(missing) == 1
    assert missing[0][0].variant_id == "p:01#alt_x"
    assert missing[0][1].variant_id == "p:02#original"


def test_missing_pairs_singleton_singleton_with_score_returns_empty():
    rm = {
        "compatibility_scores": [
            {"variant_a_id": "p:01#original", "variant_b_id": "p:02#original", "score": 0.5},
        ]
    }
    a = [_vh("p:01", "p:01#original")]
    b = [_vh("p:02", "p:02#original")]
    assert _missing_pairs(rm, a, b) == []


def test_missing_pairs_full_cube_when_no_existing_scores():
    rm = {"compatibility_scores": []}
    a = [_vh("p:01", "p:01#original"), _vh("p:01", "p:01#alt_x")]
    b = [_vh("p:02", "p:02#original"), _vh("p:02", "p:02#alt_y")]
    missing = _missing_pairs(rm, a, b)
    assert len(missing) == 4
