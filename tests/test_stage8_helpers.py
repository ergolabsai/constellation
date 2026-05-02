"""Tests for stage 8 helpers (no LLM calls)."""
from __future__ import annotations

from constellation.stages.s8_consolidate import (
    _compute_consensus,
    _compute_intra_frustration,
    _fill_transitions_in,
    _idea_filename,
    _slugify,
)

# ---------- _slugify ---------------------------------------------------------


def test_slugify_lowercases_and_underscores():
    assert _slugify("Period Amplitude Coupling") == "period_amplitude_coupling"


def test_slugify_drops_punctuation():
    assert _slugify("Shear stabilizes m=0!") == "shear_stabilizes_m0"


def test_slugify_truncates_long_text():
    long = "a really really really really really really really long label"
    out = _slugify(long)
    assert len(out) <= 40
    assert not out.endswith("_")


# ---------- _idea_filename ---------------------------------------------------


def test_idea_filename_replaces_slash():
    assert _idea_filename("shumlak/idea_01_kink") == "shumlak_idea_01_kink.json"


# ---------- _compute_consensus ----------------------------------------------


def _contributing(
    rows: list[tuple[str, str, str, float, float]],
) -> list[dict]:
    """Each row: (claim_id, paper_id, variant_id, credibility, rewrite_distance)."""
    return [
        {
            "claim_id": cid,
            "paper_id": pid,
            "selected_variant_id": vid,
            "credibility": cred,
            "rewrite_distance": rd,
            "role_in_idea": "primary",
        }
        for cid, pid, vid, cred, rd in rows
    ]


def test_consensus_counts_papers_and_rewrites():
    contrib = _contributing(
        [
            ("p:01", "P", "p:01#original", 0.8, 0.0),
            ("p:02", "P", "p:02#alt_x", 0.6, 0.3),
            ("q:01", "Q", "q:01#original", 0.9, 0.0),
        ]
    )
    edges = [
        {
            "claim_a": "p:01", "claim_b": "p:02", "selected_score": 0.6,
            "edge_id": "e1",
        },
    ]
    out = _compute_consensus(contrib, edges)
    assert out["n_papers_represented"] == 2
    assert out["n_claims"] == 3
    assert abs(out["mean_credibility"] - (0.8 + 0.6 + 0.9) / 3) < 1e-9
    assert out["n_rewritten"] == 1
    assert out["all_originals"] is False
    assert abs(out["total_rewrite_cost"] - 0.3) < 1e-9
    # agreement_score is mean of intra-Idea edges; only one edge fits
    assert out["agreement_score"] == 0.6


def test_consensus_zero_intra_edges_means_zero_agreement():
    contrib = _contributing([("p:01", "P", "p:01#original", 0.8, 0.0)])
    out = _compute_consensus(contrib, [])
    assert out["agreement_score"] == 0.0
    assert out["all_originals"] is True


# ---------- _compute_intra_frustration --------------------------------------


def test_intra_frustration_counts_only_inside_triangles():
    contributing_ids = {"a", "b", "c"}
    selected_edges = [
        {"claim_a": "a", "claim_b": "b", "selected_score": 0.5, "edge_id": "e1"},
        {"claim_a": "a", "claim_b": "c", "selected_score": 0.5, "edge_id": "e2"},
        {"claim_a": "b", "claim_b": "c", "selected_score": -0.5, "edge_id": "e3"},
        # An edge with a vertex OUTSIDE the idea should be ignored
        {"claim_a": "a", "claim_b": "z", "selected_score": -0.5, "edge_id": "e_out"},
    ]
    sheaf_penrose = [["a", "b", "c"]]
    f = _compute_intra_frustration(contributing_ids, selected_edges, sheaf_penrose)
    assert f["n_triangles"] == 1
    assert f["n_signed_triangles"] == 1
    assert f["n_penrose"] == 1
    assert f["rho"] == 1.0
    # residual_negative_edges only includes edges inside the idea
    assert len(f["residual_negative_edges"]) == 1
    assert f["residual_negative_edges"][0]["edge_id"] == "e3"


def test_intra_frustration_excludes_penrose_with_outside_vertex():
    contributing_ids = {"a", "b"}   # only 2 nodes — no triangles
    selected_edges = [
        {"claim_a": "a", "claim_b": "b", "selected_score": 0.5, "edge_id": "e1"},
    ]
    sheaf_penrose = [["a", "b", "c"]]   # has 'c' outside the idea
    f = _compute_intra_frustration(contributing_ids, selected_edges, sheaf_penrose)
    assert f["n_penrose"] == 0
    assert f["penrose_triangles"] == []
    assert f["rho"] == 0.0


# ---------- _fill_transitions_in --------------------------------------------


def test_fill_transitions_in_inverts_outs():
    ideas = [
        {
            "idea_id": "c/idea_01_a",
            "transitions_out": [
                {"to_idea_id": "c/idea_02_b", "kind": "tool_supply", "note": "n1"},
            ],
            "transitions_in": [],
        },
        {
            "idea_id": "c/idea_02_b",
            "transitions_out": [],
            "transitions_in": [],
        },
        {
            "idea_id": "c/idea_03_c",
            "transitions_out": [
                {"to_idea_id": "c/idea_02_b", "kind": "extension", "note": "n2"},
            ],
            "transitions_in": [],
        },
    ]
    _fill_transitions_in(ideas)
    in_b = next(i for i in ideas if i["idea_id"] == "c/idea_02_b")["transitions_in"]
    assert len(in_b) == 2
    assert {t["from_idea_id"] for t in in_b} == {"c/idea_01_a", "c/idea_03_c"}
