"""Tests for the shared compatibility-scoring helpers (no LLM calls)."""
from __future__ import annotations

import pytest

from constellation.scoring import _validate_score


def test_validate_score_accepts_well_formed():
    out = _validate_score(
        {"score": 0.8, "kind": "agreement", "explanation": "they agree on the meet"}
    )
    assert out == {"score": 0.8, "kind": "agreement", "explanation": "they agree on the meet"}


def test_validate_score_rejects_score_out_of_range():
    with pytest.raises(ValueError, match=r"in \[-1, 1\]"):
        _validate_score({"score": 1.5, "kind": "agreement", "explanation": "x"})


def test_validate_score_rejects_unknown_kind():
    with pytest.raises(ValueError, match="kind must be one of"):
        _validate_score({"score": 0.5, "kind": "weirdo", "explanation": "x"})


def test_validate_score_rejects_contradiction_score_too_high():
    with pytest.raises(ValueError, match="contradiction.*requires score"):
        _validate_score({"score": 0.0, "kind": "contradiction", "explanation": "x"})


def test_validate_score_rejects_agreement_score_too_low():
    with pytest.raises(ValueError, match="agreement.*requires score"):
        _validate_score({"score": 0.3, "kind": "agreement", "explanation": "x"})


def test_validate_score_rejects_empty_explanation():
    with pytest.raises(ValueError, match="explanation"):
        _validate_score({"score": 0.5, "kind": "qualification", "explanation": "  "})


def test_validate_score_strips_explanation_whitespace():
    out = _validate_score(
        {"score": 0.5, "kind": "qualification", "explanation": "  hi  "}
    )
    assert out["explanation"] == "hi"
