"""Tests for stage 2 helpers (no LLM calls)."""
from __future__ import annotations

import pytest

from constellation.stages.s2_tag import (
    _claim_summary,
    _paper_summary,
    _validate_tags,
    _validate_vocabulary,
)

# ---------- _claim_summary / _paper_summary ----------------------------------


def test_claim_summary_keeps_only_essentials():
    full = {
        "claim_id": "p:01",
        "paper_id": "p",
        "claim_type": "causal",
        "cause": "X",
        "effect": "Y",
        "direction": "causes",
        "scope": {"claimed": {"a": 1}, "evidenced": {"b": 2}},
        "evidence": {"description": "long..."},
        "credibility_score": 0.9,
    }
    s = _claim_summary(full)
    assert s["claim_id"] == "p:01"
    assert s["scope_evidenced"] == {"b": 2}
    # full evidence body should be dropped
    assert "evidence" not in s
    assert "credibility_score" not in s


def test_paper_summary_drops_argument_dag():
    full = {
        "paper_id": "p",
        "bibliographic": {"title": "T"},
        "model_level": "ideal_mhd",
        "paper_type": "computational",
        "observational_ground": {"physical_system": "Z-pinch"},
        "claims": [{"claim_id": "p:01", "kind": "primary"}],
    }
    s = _paper_summary(full)
    assert s["title"] == "T"
    assert "claims" not in s


# ---------- _validate_vocabulary ---------------------------------------------


def _ok_vocab() -> dict:
    return {
        "domain": "test",
        "rationale": "...",
        "semilattice_dimensions": [
            {
                "name": "mode",
                "description": "...",
                "values": ["a", "b"],
                "ordering": "discrete",
            },
            {
                "name": "framework",
                "description": "...",
                "values": ["x", "y", "z"],
                "ordering": "hierarchical",
                "hierarchy": {"x": None, "y": "x", "z": "y"},
            },
        ],
        "snag_nodes": [
            {"canonical": "shear", "aliases": []},
            {"canonical": "kink", "aliases": ["m=1"]},
        ],
    }


def test_validate_vocabulary_accepts_well_formed():
    _validate_vocabulary(_ok_vocab())


def test_validate_vocabulary_requires_dimensions():
    bad = _ok_vocab()
    bad["semilattice_dimensions"] = []
    with pytest.raises(ValueError, match="semilattice_dimensions"):
        _validate_vocabulary(bad)


def test_validate_vocabulary_rejects_unknown_ordering():
    bad = _ok_vocab()
    bad["semilattice_dimensions"][0]["ordering"] = "ladder"
    with pytest.raises(ValueError, match="unknown ordering"):
        _validate_vocabulary(bad)


def test_validate_vocabulary_rejects_hierarchical_without_hierarchy():
    bad = _ok_vocab()
    del bad["semilattice_dimensions"][1]["hierarchy"]
    with pytest.raises(ValueError, match="missing 'hierarchy'"):
        _validate_vocabulary(bad)


def test_validate_vocabulary_rejects_dup_dim_name():
    bad = _ok_vocab()
    bad["semilattice_dimensions"].append(
        {"name": "mode", "values": ["c"], "ordering": "discrete"}
    )
    with pytest.raises(ValueError, match="duplicate dimension"):
        _validate_vocabulary(bad)


def test_validate_vocabulary_rejects_dup_snag_canonical():
    bad = _ok_vocab()
    bad["snag_nodes"].append({"canonical": "shear"})
    with pytest.raises(ValueError, match="duplicate SNAG"):
        _validate_vocabulary(bad)


# ---------- _validate_tags ---------------------------------------------------


def _ok_tags(claim_ids: list[str]) -> dict:
    return {
        cid: {"semilattice": {"mode": "a"}, "snag_nodes": ["shear"]}
        for cid in claim_ids
    }


def test_validate_tags_accepts_well_formed():
    vocab = _ok_vocab()
    claims = [{"claim_id": "p:01"}, {"claim_id": "p:02"}]
    tags = _ok_tags(["p:01", "p:02"])
    _validate_tags(tags, vocab, claims)


def test_validate_tags_allows_null_for_dimension():
    vocab = _ok_vocab()
    claims = [{"claim_id": "p:01"}]
    tags = {"p:01": {"semilattice": {"mode": None}, "snag_nodes": []}}
    _validate_tags(tags, vocab, claims)


def test_validate_tags_rejects_missing_claim():
    vocab = _ok_vocab()
    claims = [{"claim_id": "p:01"}, {"claim_id": "p:02"}]
    tags = _ok_tags(["p:01"])  # missing p:02
    with pytest.raises(ValueError, match="missing tags"):
        _validate_tags(tags, vocab, claims)


def test_validate_tags_rejects_unknown_dimension():
    vocab = _ok_vocab()
    claims = [{"claim_id": "p:01"}]
    tags = {"p:01": {"semilattice": {"made_up": "x"}, "snag_nodes": []}}
    with pytest.raises(ValueError, match="unknown dimension"):
        _validate_tags(tags, vocab, claims)


def test_validate_tags_rejects_value_outside_vocab():
    vocab = _ok_vocab()
    claims = [{"claim_id": "p:01"}]
    tags = {"p:01": {"semilattice": {"mode": "z_not_in_vocab"}, "snag_nodes": []}}
    with pytest.raises(ValueError, match="not in vocabulary"):
        _validate_tags(tags, vocab, claims)


def test_validate_tags_rejects_unknown_snag_node():
    vocab = _ok_vocab()
    claims = [{"claim_id": "p:01"}]
    tags = {"p:01": {"semilattice": {"mode": "a"}, "snag_nodes": ["made_up_node"]}}
    with pytest.raises(ValueError, match="unknown SNAG node"):
        _validate_tags(tags, vocab, claims)
