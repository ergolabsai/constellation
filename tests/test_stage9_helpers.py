"""Tests for stage 9 helpers (no LLM, no file I/O)."""
from __future__ import annotations

from io import StringIO

from constellation.stages.s9_report import (
    _gather_priorities,
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
