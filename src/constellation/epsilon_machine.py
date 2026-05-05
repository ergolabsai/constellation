"""Computed epsilon-machine metrics over a run's Idea partition."""
from __future__ import annotations

import json
import math

from .paths import Run
from .schemas import validate_epsilon_machine


def _transition_rows(ideas: list[dict]) -> list[dict]:
    rows = []
    for idea in ideas:
        from_id = idea["idea_id"]
        for transition in idea.get("transitions_out", []) or []:
            rows.append(
                {
                    "from_idea_id": from_id,
                    "to_idea_id": transition["to_idea_id"],
                    "kind": transition["kind"],
                    "note": transition.get("note", ""),
                    "supporting_edges": transition.get("supporting_edges", []) or [],
                }
            )
    rows.sort(key=lambda t: (t["from_idea_id"], t["to_idea_id"], t["kind"]))
    return rows


def compute_epsilon_machine_metrics(ideas: list[dict]) -> dict:
    """Compute C_mu and transition stats for the Idea epsilon-machine.

    The state distribution uses claim occupancy: an Idea with 4 of 20
    MAP-selected claims has probability 0.2. This is simple, reproducible, and
    matches the pipeline's current batch artifact shape; future versions can add
    weighted distributions without invalidating this one.
    """
    n_states = len(ideas)
    claim_counts = {
        idea["idea_id"]: len(idea.get("contributing_claims", []) or [])
        for idea in ideas
    }
    n_claims = sum(claim_counts.values())

    transitions = _transition_rows(ideas)
    transitions_out: dict[str, int] = {idea["idea_id"]: 0 for idea in ideas}
    transitions_in: dict[str, int] = {idea["idea_id"]: 0 for idea in ideas}
    for transition in transitions:
        transitions_out[transition["from_idea_id"]] = (
            transitions_out.get(transition["from_idea_id"], 0) + 1
        )
        transitions_in[transition["to_idea_id"]] = (
            transitions_in.get(transition["to_idea_id"], 0) + 1
        )

    state_distribution = []
    for idea in sorted(ideas, key=lambda i: i["idea_id"]):
        n = claim_counts[idea["idea_id"]]
        p = n / n_claims if n_claims else 0.0
        state_distribution.append(
            {
                "idea_id": idea["idea_id"],
                "label": idea.get("label", idea["idea_id"]),
                "n_claims": n,
                "probability": p,
                "transitions_out": transitions_out.get(idea["idea_id"], 0),
                "transitions_in": transitions_in.get(idea["idea_id"], 0),
            }
        )

    c_mu = -sum(
        row["probability"] * math.log2(row["probability"])
        for row in state_distribution
        if row["probability"] > 0
    )
    normalized = c_mu / math.log2(n_states) if n_states > 1 else 0.0
    effective_states = 2**c_mu if n_claims else 0.0
    unique_pairs = {
        (transition["from_idea_id"], transition["to_idea_id"])
        for transition in transitions
        if transition["from_idea_id"] != transition["to_idea_id"]
    }
    possible_pairs = n_states * (n_states - 1)
    transition_density = len(unique_pairs) / possible_pairs if possible_pairs else 0.0

    return {
        "$schema": "landscape-map/epsilon_machine/v0.1",
        "n_states": n_states,
        "n_claims": n_claims,
        "statistical_complexity_bits": c_mu,
        "normalized_statistical_complexity": normalized,
        "effective_states": effective_states,
        "state_distribution": state_distribution,
        "transition_graph": {
            "n_transitions": len(transitions),
            "n_unique_transition_pairs": len(unique_pairs),
            "transition_density": transition_density,
            "transitions": transitions,
        },
    }


def write_epsilon_machine_metrics(run: Run, ideas: list[dict]) -> dict:
    """Validate and write epsilon_machine.json for a completed Idea partition."""
    metrics = compute_epsilon_machine_metrics(ideas)
    validate_epsilon_machine(metrics)
    run.epsilon_machine_path.write_text(json.dumps(metrics, indent=2) + "\n")
    return metrics
