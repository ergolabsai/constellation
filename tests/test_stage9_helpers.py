"""Tests for stage 9 helpers (no LLM, no file I/O)."""
from __future__ import annotations

from io import StringIO

import pytest

from constellation.stages.s9_report import (
    _gather_priorities,
    _validate_artifacts,
    _write_diagnostics,
    _write_epsilon_machine,
    _write_idea,
    _write_priorities,
)


def _toy_idea(label: str, qs: list[dict]) -> dict:
    return {
        "idea_id": f"corp/idea_01_{label.lower().replace(' ', '_')}",
        "label": label,
        "description": "desc.",
        "scope": {"generality": "domain_specific", "framework": "X", "conditions": []},
        "consensus": {
            "n_claims": 2,
            "n_papers_represented": 1,
            "mean_credibility": 0.8,
            "agreement_score": 0.5,
            "all_originals": True,
            "n_rewritten": 0,
            "total_rewrite_cost": 0.0,
        },
        "frustration": {
            "rho": 0.0,
            "n_triangles": 0,
            "n_signed_triangles": 0,
            "n_penrose": 0,
            "penrose_triangles": [],
            "residual_negative_edges": [],
        },
        "contributing_claims": [
            {
                "claim_id": "p:01",
                "selected_variant_id": "p:01#original",
                "paper_id": "p",
                "credibility": 0.8,
                "rewrite_distance": 0.0,
                "role_in_idea": "primary",
            }
        ],
        "transitions_out": [],
        "transitions_in": [],
        "open_questions": qs,
    }


def _toy_art(ideas: list[dict], selected: set[str] | None = None) -> dict:
    return {
        "sheaf": {
            "map_section": {
                "selected": {
                    cid: f"{cid}#original"
                    for cid in (selected or {"p:01"})
                }
            }
        },
        "ideas": ideas,
    }


def _q(question: str, priority: str, kind: str, effort: str) -> dict:
    return {
        "question": question,
        "feeds_from": {},
        "suggested_next_steps": [
            {
                "kind": kind,
                "description": f"do {kind} for {question}",
                "effort": effort,
                "maturity": "immediate",
                "expected_outcome": "ok",
            }
        ],
        "priority": priority,
    }


# ---------- _gather_priorities ----------------------------------------------


def test_gather_priorities_sorts_by_priority_then_effort():
    ideas = [
        _toy_idea("A", [_q("Q1", "low", "experiment", "high")]),
        _toy_idea("B", [_q("Q2", "high", "simulation", "medium")]),
        _toy_idea("C", [_q("Q3", "high", "experiment", "low")]),
        _toy_idea("D", [_q("Q4", "medium", "simulation", "low")]),
    ]
    rows = _gather_priorities(ideas)
    questions = [r["question"] for r in rows]
    # Q3 (high/low) before Q2 (high/medium) before Q4 (medium/low) before Q1 (low/high)
    assert questions == ["Q3", "Q2", "Q4", "Q1"]


def test_gather_priorities_flattens_multiple_steps():
    """One question with two steps -> two rows."""
    idea = _toy_idea("A", [_q("Q1", "high", "experiment", "low")])
    idea["open_questions"][0]["suggested_next_steps"].append(
        {
            "kind": "simulation",
            "description": "second step",
            "effort": "low",
            "maturity": "immediate",
            "expected_outcome": "",
        }
    )
    rows = _gather_priorities([idea])
    assert len(rows) == 2
    assert {r["kind"] for r in rows} == {"experiment", "simulation"}


# ---------- _write_priorities ------------------------------------------------


def test_write_priorities_groups_by_kind():
    ideas = [
        _toy_idea("A", [_q("Q1", "high", "experiment", "low")]),
        _toy_idea("B", [_q("Q2", "high", "simulation", "low")]),
    ]
    buf = StringIO()
    _write_priorities(buf, ideas)
    text = buf.getvalue()
    assert "## Research priorities" in text
    assert "### Experiment" in text
    assert "### Simulation" in text


def test_write_priorities_skips_when_no_questions():
    ideas = [_toy_idea("A", [])]
    buf = StringIO()
    _write_priorities(buf, ideas)
    assert buf.getvalue() == ""


# ---------- _write_diagnostics ----------------------------------------------


def test_write_diagnostics_includes_lambda_sensitivity():
    sheaf = {
        "map_section": {
            "selected": {"p:01": "p:01#original"},
            "residual_h1": [],
        },
        "lambda_sensitivity": {
            "lambdas": [0.1, 0.4, 0.8],
            "n_stable_claims": 0,
            "n_sensitive_claims": 1,
            "sections": [
                {
                    "lambda_rewrite_penalty": 0.1,
                    "total_score": 1.0,
                    "coherence": 1.0,
                    "rewrite_cost": 0.2,
                    "n_rewritten": 1,
                }
            ],
            "sensitive_claims": [
                {
                    "claim_id": "p:01",
                    "selections_by_lambda": [
                        {
                            "lambda_rewrite_penalty": 0.1,
                            "variant_id": "p:01#alt",
                        },
                        {
                            "lambda_rewrite_penalty": 0.8,
                            "variant_id": "p:01#original",
                        },
                    ],
                }
            ],
        },
        "frustration": {},
    }
    buf = StringIO()

    _write_diagnostics(buf, sheaf)

    text = buf.getvalue()
    assert "### Lambda sensitivity" in text
    assert "Sensitive claims: **1/1**" in text
    assert "`p:01#alt` at λ=0.1" in text


# ---------- _write_epsilon_machine ------------------------------------------


def test_write_epsilon_machine_reports_complexity_and_distribution():
    machine = {
        "n_states": 2,
        "n_claims": 4,
        "statistical_complexity_bits": 0.811278,
        "normalized_statistical_complexity": 0.811278,
        "effective_states": 1.754765,
        "state_distribution": [
            {
                "idea_id": "c/idea_01_a",
                "probability": 0.75,
                "n_claims": 3,
                "transitions_out": 1,
                "transitions_in": 0,
            },
            {
                "idea_id": "c/idea_02_b",
                "probability": 0.25,
                "n_claims": 1,
                "transitions_out": 0,
                "transitions_in": 1,
            },
        ],
        "transition_graph": {
            "n_unique_transition_pairs": 1,
            "transition_density": 0.5,
            "n_transitions": 1,
        },
    }
    buf = StringIO()

    _write_epsilon_machine(buf, machine)

    text = buf.getvalue()
    assert "## ε-machine complexity" in text
    assert "Cμ = **0.811 bits**" in text
    assert "`c/idea_01_a`: p=0.750" in text


# ---------- _write_idea ------------------------------------------------------


def test_write_idea_includes_label_description_scope_claims():
    idea = _toy_idea("Test Label", [])
    buf = StringIO()
    _write_idea(buf, idea, {"p:01": {"cause": "the cause text"}})
    text = buf.getvalue()
    assert "Test Label" in text
    assert "desc." in text
    assert "Contributing claims" in text
    assert "p:01" in text
    assert "the cause text" in text


# ---------- _validate_artifacts ---------------------------------------------


def test_validate_artifacts_accepts_exact_idea_partition():
    _validate_artifacts(_toy_art([_toy_idea("A", [])]))


def test_validate_artifacts_rejects_duplicate_membership():
    ideas = [_toy_idea("A", []), _toy_idea("B", [])]
    with pytest.raises(ValueError, match="duplicated MAP claims"):
        _validate_artifacts(_toy_art(ideas))


def test_validate_artifacts_rejects_empty_idea():
    idea = _toy_idea("A", [])
    idea["contributing_claims"] = []
    with pytest.raises(ValueError, match="empty Ideas"):
        _validate_artifacts(_toy_art([idea]))


def test_validate_artifacts_rejects_missing_membership():
    with pytest.raises(ValueError, match="missing MAP claims"):
        _validate_artifacts(_toy_art([_toy_idea("A", [])], {"p:01", "p:02"}))
