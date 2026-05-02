"""Tests for the viz renderer (no LLM, no browser)."""
from __future__ import annotations

import json
from pathlib import Path

from constellation.paths import Run
from constellation.viz import _build_payload, render


def _toy_run(tmp_path: Path) -> Run:
    """Construct a tiny run directory the renderer can chew on."""
    root = tmp_path / "toy_20260502T000000Z"
    root.mkdir()
    (root / "papers").mkdir()
    (root / "claims").mkdir()
    (root / "ideas").mkdir()

    (root / "papers" / "p.json").write_text(
        json.dumps(
            {
                "paper_id": "p",
                "bibliographic": {"title": "Test paper", "authors": ["X"], "year": 2024},
                "observational_ground": {},
                "claims": [],
            }
        )
    )
    (root / "claims" / "p_01.json").write_text(
        json.dumps(
            {
                "claim_id": "p:01",
                "paper_id": "p",
                "cause": "X",
                "effect": "Y",
                "direction": "causes",
                "strength": "strong",
                "credibility_score": 0.8,
                "extraction": {"method": "manual"},
            }
        )
    )
    (root / "claims" / "p_02.json").write_text(
        json.dumps(
            {
                "claim_id": "p:02",
                "paper_id": "p",
                "cause": "A",
                "effect": "B",
                "direction": "causes",
                "strength": "moderate",
                "credibility_score": 0.6,
                "extraction": {"method": "manual"},
            }
        )
    )

    sheaf = {
        "$schema": "landscape-map/sheaf/v0.1",
        "sheaf_id": "toy/run",
        "corpus": "toy",
        "base": ["p:01", "p:02"],
        "stalks": {
            "p:01": {
                "claim_id": "p:01",
                "variants": [
                    {
                        "variant_id": "p:01#original",
                        "text": "X causes Y",
                        "rewrite_distance": 0.0,
                        "evidence_faithful": True,
                    }
                ],
            },
            "p:02": {
                "claim_id": "p:02",
                "variants": [
                    {
                        "variant_id": "p:02#original",
                        "text": "A causes B",
                        "rewrite_distance": 0.0,
                        "evidence_faithful": True,
                    }
                ],
            },
        },
        "restriction_maps": [
            {
                "edge_id": "restriction:p:01↔p:02",
                "claim_a": "p:01",
                "claim_b": "p:02",
                "compatibility_scores": [
                    {
                        "variant_a_id": "p:01#original",
                        "variant_b_id": "p:02#original",
                        "score": 0.5,
                        "kind": "qualification",
                        "explanation": "qualifying",
                    }
                ],
            }
        ],
        "map_section": {
            "selected": {"p:01": "p:01#original", "p:02": "p:02#original"},
            "total_score": 0.5,
            "coherence": 0.5,
            "rewrite_cost": 0.0,
            "lambda_rewrite_penalty": 0.4,
            "residual_h1": [],
        },
        "frustration": {"rho": 0.0, "n_penrose": 0, "n_signed_triangles": 0},
        "extraction": {"method": "llm_single"},
    }
    (root / "sheaf.json").write_text(json.dumps(sheaf))

    (root / "ideas" / "toy_idea_01_x_causes_y.json").write_text(
        json.dumps(
            {
                "$schema": "landscape-map/idea/v0.2",
                "idea_id": "toy/idea_01_x_causes_y",
                "label": "X causes Y consolidated",
                "description": "Both claims agree.",
                "sheaf_ref": {"sheaf_id": "toy/run"},
                "scope": {
                    "generality": "domain_specific",
                    "framework": "test",
                    "conditions": [],
                    "derived_from_claims": ["p:01", "p:02"],
                },
                "contributing_claims": [
                    {
                        "claim_id": "p:01",
                        "selected_variant_id": "p:01#original",
                        "paper_id": "p",
                        "credibility": 0.8,
                        "rewrite_distance": 0.0,
                        "role_in_idea": "primary",
                    },
                    {
                        "claim_id": "p:02",
                        "selected_variant_id": "p:02#original",
                        "paper_id": "p",
                        "credibility": 0.6,
                        "rewrite_distance": 0.0,
                        "role_in_idea": "supporting",
                    },
                ],
                "consensus": {
                    "n_papers_represented": 1,
                    "n_claims": 2,
                    "mean_credibility": 0.7,
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
                "open_questions": [],
                "extraction": {"method": "llm_single"},
            }
        )
    )

    return Run(root=root)


def test_build_payload_packs_expected_keys(tmp_path: Path):
    run = _toy_run(tmp_path)
    payload = _build_payload(run)
    for k in ("corpus", "stats", "papers", "claims", "edges", "ideas"):
        assert k in payload, f"missing key {k}"
    assert payload["stats"]["n_claims"] == 2
    assert payload["stats"]["n_edges"] == 1
    assert payload["stats"]["n_ideas"] == 1
    assert payload["stats"]["n_rewrites"] == 0


def test_build_payload_attaches_idea_to_claims(tmp_path: Path):
    run = _toy_run(tmp_path)
    payload = _build_payload(run)
    by_id = {c["claim_id"]: c for c in payload["claims"]}
    assert by_id["p:01"]["idea_id"] == "toy/idea_01_x_causes_y"
    assert by_id["p:02"]["idea_id"] == "toy/idea_01_x_causes_y"


def test_build_payload_marks_residual_participation(tmp_path: Path):
    run = _toy_run(tmp_path)
    # Mutate the sheaf to make the edge negative + residual
    sheaf = json.loads(run.sheaf_path.read_text())
    sheaf["restriction_maps"][0]["compatibility_scores"][0]["score"] = -0.5
    sheaf["restriction_maps"][0]["compatibility_scores"][0]["kind"] = "contradiction"
    sheaf["map_section"]["residual_h1"] = [
        {"edge_id": "restriction:p:01↔p:02", "claim_a": "p:01", "claim_b": "p:02",
         "selected_score": -0.5, "why_unresolved": "..."}
    ]
    run.sheaf_path.write_text(json.dumps(sheaf))

    payload = _build_payload(run)
    by_id = {c["claim_id"]: c for c in payload["claims"]}
    assert by_id["p:01"]["in_residual_edge"] is True
    assert by_id["p:02"]["in_residual_edge"] is True
    assert payload["edges"][0]["is_residual"] is True


def test_render_writes_html_with_inlined_payload(tmp_path: Path):
    run = _toy_run(tmp_path)
    out = render(run)
    assert out.exists()
    text = out.read_text()
    assert text.startswith("<!DOCTYPE html>")
    # Payload was substituted (no placeholder left)
    assert "__PAYLOAD_JSON__" not in text
    # Payload is parseable and has our corpus
    assert '"corpus": "toy"' in text
    # D3 script tag is present
    assert "d3.v7.min.js" in text


def test_render_to_custom_path(tmp_path: Path):
    run = _toy_run(tmp_path)
    custom = tmp_path / "elsewhere.html"
    out = render(run, out_path=custom)
    assert out == custom
    assert custom.exists()
