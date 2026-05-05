"""Tests for epsilon-machine metrics."""
from __future__ import annotations

from constellation.epsilon_machine import compute_epsilon_machine_metrics


def _idea(idea_id: str, claim_ids: list[str], transitions: list[dict] | None = None) -> dict:
    return {
        "idea_id": idea_id,
        "label": idea_id.rsplit("_", 1)[-1],
        "contributing_claims": [{"claim_id": cid} for cid in claim_ids],
        "transitions_out": transitions or [],
    }


def test_compute_epsilon_machine_metrics_uses_claim_occupancy_entropy():
    ideas = [
        _idea(
            "c/idea_01_a",
            ["a:01", "a:02", "a:03"],
            [{"to_idea_id": "c/idea_02_b", "kind": "extension", "note": "feeds"}],
        ),
        _idea("c/idea_02_b", ["b:01"]),
    ]

    metrics = compute_epsilon_machine_metrics(ideas)

    assert metrics["n_states"] == 2
    assert metrics["n_claims"] == 4
    assert abs(metrics["statistical_complexity_bits"] - 0.8112781244591328) < 1e-12
    assert abs(metrics["normalized_statistical_complexity"] - 0.8112781244591328) < 1e-12
    assert abs(metrics["effective_states"] - 1.7547653506033232) < 1e-12
    assert metrics["transition_graph"]["n_transitions"] == 1
    assert metrics["transition_graph"]["n_unique_transition_pairs"] == 1
    assert metrics["transition_graph"]["transition_density"] == 0.5


def test_compute_epsilon_machine_metrics_handles_single_state():
    metrics = compute_epsilon_machine_metrics([_idea("c/idea_01_a", ["a:01"])])

    assert metrics["statistical_complexity_bits"] == 0.0
    assert metrics["normalized_statistical_complexity"] == 0.0
    assert metrics["effective_states"] == 1.0
    assert metrics["transition_graph"]["transition_density"] == 0.0
