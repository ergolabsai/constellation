"""Tests for stage 3 helpers (pure code, no LLM)."""
from __future__ import annotations

from constellation.stages.s3_complex import (
    _edge_id,
    _hierarchical_meet,
    _per_dim_meet,
    _semilattice_meet,
    _snag_overlap,
)

# ---------- _hierarchical_meet -----------------------------------------------


HIER = {
    "ideal_mhd": None,         # root A
    "resistive_mhd": "ideal_mhd",
    "two_fluid": "resistive_mhd",
    "gyrokinetic": "two_fluid",
    "experimental": None,      # root B (separate branch)
}


def test_hierarchical_meet_equal_values():
    assert _hierarchical_meet("ideal_mhd", "ideal_mhd", HIER) == "ideal_mhd"


def test_hierarchical_meet_ancestor_returns_ancestor():
    # ideal_mhd is ancestor of gyrokinetic
    assert _hierarchical_meet("ideal_mhd", "gyrokinetic", HIER) == "ideal_mhd"
    # symmetric
    assert _hierarchical_meet("gyrokinetic", "ideal_mhd", HIER) == "ideal_mhd"


def test_hierarchical_meet_siblings_returns_lca():
    # both two_fluid and resistive_mhd descend from ideal_mhd; LCA is resistive_mhd
    # (since two_fluid descends from resistive_mhd)
    assert _hierarchical_meet("two_fluid", "resistive_mhd", HIER) == "resistive_mhd"


def test_hierarchical_meet_different_roots_returns_none():
    # ideal_mhd and experimental are on separate roots
    assert _hierarchical_meet("ideal_mhd", "experimental", HIER) is None
    assert _hierarchical_meet("gyrokinetic", "experimental", HIER) is None


# ---------- _per_dim_meet ----------------------------------------------------


def test_per_dim_meet_discrete_equal():
    dim = {"name": "x", "ordering": "discrete", "values": ["a", "b"]}
    assert _per_dim_meet("a", "a", dim) == ("a", True)


def test_per_dim_meet_discrete_unequal():
    dim = {"name": "x", "ordering": "discrete", "values": ["a", "b"]}
    assert _per_dim_meet("a", "b", dim) == (None, False)


def test_per_dim_meet_null_is_unconstrained():
    dim = {"name": "x", "ordering": "discrete", "values": ["a", "b"]}
    assert _per_dim_meet(None, "a", dim) == ("a", True)
    assert _per_dim_meet("a", None, dim) == ("a", True)
    assert _per_dim_meet(None, None, dim) == (None, True)


def test_per_dim_meet_hierarchical_uses_lca():
    dim = {"name": "x", "ordering": "hierarchical", "hierarchy": HIER}
    assert _per_dim_meet("ideal_mhd", "gyrokinetic", dim) == ("ideal_mhd", True)
    assert _per_dim_meet("ideal_mhd", "experimental", dim) == (None, False)


def test_per_dim_meet_wildcard_is_universally_compatible():
    """A value in `wildcards` meets anything; the meet is the other side."""
    dim = {
        "name": "framework",
        "ordering": "hierarchical",
        "hierarchy": HIER,
        "wildcards": ["experimental"],
    }
    # experimental ↔ ideal_mhd: previously incompatible (separate roots);
    # with wildcard, meet exists and equals the non-wildcard side.
    assert _per_dim_meet("experimental", "ideal_mhd", dim) == ("ideal_mhd", True)
    assert _per_dim_meet("ideal_mhd", "experimental", dim) == ("ideal_mhd", True)
    # both wildcards: pick either (here, the first).
    assert _per_dim_meet("experimental", "experimental", dim) == ("experimental", True)


def test_per_dim_meet_set_inclusion_intersects():
    dim = {"name": "x", "ordering": "set_inclusion", "values": []}
    # Single-string values get singletonized
    assert _per_dim_meet("a", "a", dim) == ("a", True)
    assert _per_dim_meet("a", "b", dim) == (None, False)
    # List values
    assert _per_dim_meet(["a", "b"], ["b", "c"], dim) == ("b", True)


# ---------- _semilattice_meet ------------------------------------------------


def _vocab() -> dict:
    return {
        "semilattice_dimensions": [
            {"name": "mode", "ordering": "discrete", "values": ["m0", "m1"]},
            {
                "name": "framework",
                "ordering": "hierarchical",
                "hierarchy": HIER,
                "values": list(HIER.keys()),
            },
        ]
    }


def test_semilattice_meet_all_compat():
    sl_a = {"mode": "m1", "framework": "ideal_mhd"}
    sl_b = {"mode": "m1", "framework": "gyrokinetic"}
    meet, incompat = _semilattice_meet(sl_a, sl_b, _vocab())
    assert incompat == []
    assert meet == {"mode": "m1", "framework": "ideal_mhd"}


def test_semilattice_meet_one_dim_incompat():
    sl_a = {"mode": "m0", "framework": "ideal_mhd"}
    sl_b = {"mode": "m1", "framework": "gyrokinetic"}
    meet, incompat = _semilattice_meet(sl_a, sl_b, _vocab())
    assert meet is None
    assert incompat == ["mode"]


def test_semilattice_meet_multiple_dims_incompat():
    sl_a = {"mode": "m0", "framework": "ideal_mhd"}
    sl_b = {"mode": "m1", "framework": "experimental"}
    meet, incompat = _semilattice_meet(sl_a, sl_b, _vocab())
    assert meet is None
    assert set(incompat) == {"mode", "framework"}


def test_semilattice_meet_with_nulls():
    sl_a = {"mode": None, "framework": "ideal_mhd"}
    sl_b = {"mode": "m1", "framework": None}
    meet, incompat = _semilattice_meet(sl_a, sl_b, _vocab())
    assert incompat == []
    assert meet == {"mode": "m1", "framework": "ideal_mhd"}


# ---------- _snag_overlap ----------------------------------------------------


def test_snag_overlap_returns_sorted_intersection():
    assert _snag_overlap(["c", "b", "a"], ["b", "d", "a"]) == ["a", "b"]
    assert _snag_overlap(["a"], ["b"]) == []


# ---------- _edge_id ---------------------------------------------------------


def test_edge_id_alphabetical_canonical():
    assert _edge_id("p:02", "p:01") == "edge:p:01↔p:02"
    assert _edge_id("a:01", "z:01") == "edge:a:01↔z:01"
