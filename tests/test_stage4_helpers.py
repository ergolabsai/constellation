"""Tests for stage 4 helpers (no LLM calls)."""
from __future__ import annotations

import pytest

from constellation.scoring import canonical_text
from constellation.stages.s4_alternatives import (
    _build_original_variant_record,
    _validate_alternative,
)

# ---------- canonical_text (scoring helper) ----------------------------------


def test_canonical_text_basic():
    claim = {"cause": "X", "direction": "causes", "effect": "Y"}
    assert canonical_text(claim) == "X causes Y"


def test_canonical_text_includes_evidenced_conditions():
    claim = {
        "cause": "shear",
        "direction": "inhibits",
        "effect": "kink",
        "scope": {"evidenced": {"conditions": ["uniform shear", "ka=π"]}},
    }
    out = canonical_text(claim)
    assert "shear inhibits kink" in out
    assert "evidenced under: uniform shear; ka=π" in out


# ---------- _build_original_variant_record -----------------------------------


def test_original_variant_record_has_distance_zero_and_no_targets():
    claim = {
        "claim_id": "p:01",
        "cause": "X",
        "direction": "causes",
        "effect": "Y",
        "evidence": {"strengths": ["s1", "s2"], "weaknesses": ["w1"]},
    }
    rec = _build_original_variant_record(claim)
    assert rec["variant_id"] == "p:01#original"
    assert rec["rewrite_distance"] == 0.0
    assert rec["targets"] == []
    assert rec["evidence_faithful"] is True
    assert rec["evidence_strengths_invoked"] == ["s1", "s2"]
    # weaknesses_invoked stays empty for the original — it's not invoking any
    assert rec["evidence_weaknesses_invoked"] == []


# ---------- _validate_alternative --------------------------------------------


def _claim() -> dict:
    return {"claim_id": "p:01", "evidence": {"weaknesses": ["w1"], "strengths": ["s1"]}}


def _ok_alt() -> dict:
    return {
        "variant_id": "p:01#alt_narrow",
        "text": "X narrowly causes Y",
        "rewrite_distance": 0.3,
        "targets": ["p:02"],
        "evidence_strengths_invoked": ["s1"],
        "evidence_weaknesses_invoked": ["w1"],
        "evidence_faithful": True,
        "faithfulness_note": "narrowed scope by invoking w1",
    }


def test_validate_alternative_accepts_well_formed():
    out = _validate_alternative(_ok_alt(), _claim(), allowed_targets={"p:02", "p:03"})
    assert out["variant_id"] == "p:01#alt_narrow"
    assert out["rewrite_distance"] == 0.3


def test_validate_alternative_rejects_wrong_id_prefix():
    bad = _ok_alt()
    bad["variant_id"] = "wrong:99#alt_x"
    with pytest.raises(ValueError, match="must start with"):
        _validate_alternative(bad, _claim(), allowed_targets={"p:02"})


def test_validate_alternative_rejects_reserved_original_descriptor():
    bad = _ok_alt()
    bad["variant_id"] = "p:01#original"
    with pytest.raises(ValueError, match="reserved"):
        _validate_alternative(bad, _claim(), allowed_targets={"p:02"})


def test_validate_alternative_rejects_distance_out_of_range():
    bad = _ok_alt()
    bad["rewrite_distance"] = 1.5
    with pytest.raises(ValueError, match=r"in \[0, 1\]"):
        _validate_alternative(bad, _claim(), allowed_targets={"p:02"})


def test_validate_alternative_rejects_unknown_target():
    bad = _ok_alt()
    bad["targets"] = ["p:99"]
    with pytest.raises(ValueError, match="not in this claim's contested neighbors"):
        _validate_alternative(bad, _claim(), allowed_targets={"p:02"})


def test_validate_alternative_rejects_empty_targets():
    bad = _ok_alt()
    bad["targets"] = []
    with pytest.raises(ValueError, match="non-empty"):
        _validate_alternative(bad, _claim(), allowed_targets={"p:02"})


def test_validate_alternative_rejects_missing_field():
    bad = _ok_alt()
    del bad["evidence_faithful"]
    with pytest.raises(ValueError, match="missing key 'evidence_faithful'"):
        _validate_alternative(bad, _claim(), allowed_targets={"p:02"})
