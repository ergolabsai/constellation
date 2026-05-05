"""Render a self-contained HTML visualization of a completed pipeline run.

Loads sheaf.json + claims/ + papers/ + ideas/ from a run directory, projects
them into a viz-friendly payload, and substitutes that into an HTML template
that ships with the package. The output is a single self-contained file:
double-click it, no server needed (D3 loads from CDN).

Two modes baked in:
  - structural  (nodes by paper, edges by sign, hulls per Idea)
  - priority    (nodes red on residual-edge participation, hulls by ρ,
                 side panel = aggregated next-steps)
"""
from __future__ import annotations

import json
from pathlib import Path

from .epsilon_machine import compute_epsilon_machine_metrics
from .idea_partition import validate_idea_partition
from .paths import Run

TEMPLATE_PATH = Path(__file__).parent / "templates" / "viz.html"


def _build_payload(run: Run, synthesis_paper_id: str | None = None) -> dict:
    sheaf = json.loads(run.sheaf_path.read_text())

    # papers
    papers = []
    available_paper_ids = set()
    for f in sorted(run.papers_dir.glob("*.json")):
        p = json.loads(f.read_text())
        papers.append(
            {
                "paper_id": p["paper_id"],
                "title": p.get("bibliographic", {}).get("title", p["paper_id"]),
                "year": p.get("bibliographic", {}).get("year"),
                "is_synthesis": p["paper_id"] == synthesis_paper_id,
            }
        )
        available_paper_ids.add(p["paper_id"])

    if synthesis_paper_id and synthesis_paper_id not in available_paper_ids:
        raise ValueError(
            f"--synthesis-paper {synthesis_paper_id!r} not found in run; "
            f"available paper_ids: {sorted(available_paper_ids)}"
        )

    # claims (full records, indexed by id)
    claim_by_id = {}
    for f in sorted(run.claims_dir.glob("*.json")):
        c = json.loads(f.read_text())
        claim_by_id[c["claim_id"]] = c

    # ideas (full records) + claim → idea mapping
    ideas_full = []
    for f in sorted(run.ideas_dir.glob("*.json")):
        idea = json.loads(f.read_text())
        ideas_full.append(idea)
    epsilon_machine = (
        json.loads(run.epsilon_machine_path.read_text())
        if run.epsilon_machine_path.exists()
        else compute_epsilon_machine_metrics(ideas_full)
    )

    # MAP section
    selected = sheaf["map_section"]["selected"]
    validate_idea_partition(ideas_full, selected.keys())

    claim_to_idea = {}
    for idea in ideas_full:
        for cc in idea["contributing_claims"]:
            claim_to_idea[cc["claim_id"]] = idea["idea_id"]

    residual_pairs = {
        (r["claim_a"], r["claim_b"])
        for r in sheaf["map_section"].get("residual_h1", [])
    }
    sensitivity = sheaf.get("lambda_sensitivity", {}) or {}
    sensitivity_by_claim = {
        row["claim_id"]: row
        for row in sensitivity.get("sensitive_claims", []) or []
    }

    # build edges (one per restriction_map, using the MAP-selected pair score)
    edges = []
    residual_claim_ids: set[str] = set()
    for rm in sheaf["restriction_maps"]:
        a, b = rm["claim_a"], rm["claim_b"]
        va, vb = selected[a], selected[b]
        score_entry = next(
            s
            for s in rm["compatibility_scores"]
            if s["variant_a_id"] == va and s["variant_b_id"] == vb
        )
        is_residual = (a, b) in residual_pairs
        if score_entry["score"] <= 0:
            residual_claim_ids.add(a)
            residual_claim_ids.add(b)
        edges.append(
            {
                "edge_id": rm["edge_id"],
                "source": a,
                "target": b,
                "selected_score": score_entry["score"],
                "kind": score_entry["kind"],
                "explanation": score_entry["explanation"],
                "is_residual": is_residual,
            }
        )

    # build viz-side claims (only those in MAP)
    viz_claims = []
    for cid, vid in selected.items():
        c = claim_by_id.get(cid, {})
        is_rewritten = not vid.endswith("#original")
        # For rewritten claims, pull the full variant record from the stalk so
        # the side panel can show original AND rewritten side-by-side.
        rewrite_info: dict | None = None
        if is_rewritten:
            stalk = sheaf["stalks"].get(cid, {})
            for v in stalk.get("variants", []):
                if v["variant_id"] == vid:
                    rewrite_info = {
                        "text": v.get("text", ""),
                        "rewrite_distance": v.get("rewrite_distance", 0.0),
                        "targets": v.get("targets", []),
                        "evidence_strengths_invoked": v.get(
                            "evidence_strengths_invoked", []
                        ),
                        "evidence_weaknesses_invoked": v.get(
                            "evidence_weaknesses_invoked", []
                        ),
                        "faithfulness_note": v.get("faithfulness_note", ""),
                    }
                    break
        viz_claims.append(
            {
                "claim_id": cid,
                "paper_id": c.get("paper_id"),
                "credibility": c.get("credibility_score", 0.5),
                "cause": (c.get("cause") or "")[:600],
                "effect": (c.get("effect") or "")[:600],
                "direction": c.get("direction"),
                "selected_variant_id": vid,
                "is_rewritten": is_rewritten,
                "rewrite_info": rewrite_info,
                "in_residual_edge": cid in residual_claim_ids,
                "is_lambda_sensitive": cid in sensitivity_by_claim,
                "lambda_selections": sensitivity_by_claim.get(cid, {}).get(
                    "selections_by_lambda", []
                ),
                "idea_id": claim_to_idea.get(cid),
                "is_synthesis_paper": c.get("paper_id") == synthesis_paper_id,
            }
        )

    # viz-side ideas
    viz_ideas = []
    state_by_idea = {
        state["idea_id"]: state
        for state in epsilon_machine.get("state_distribution", []) or []
    }
    for idea in ideas_full:
        claim_ids = [cc["claim_id"] for cc in idea["contributing_claims"]]
        open_questions = idea.get("open_questions", []) or []
        priority_counts: dict[str, int] = {}
        next_step_counts: dict[str, int] = {}
        n_next_steps = 0
        for question in open_questions:
            priority = question.get("priority", "medium")
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
            for step in question.get("suggested_next_steps", []) or []:
                kind = step.get("kind", "unknown")
                next_step_counts[kind] = next_step_counts.get(kind, 0) + 1
                n_next_steps += 1
        state = state_by_idea.get(idea["idea_id"], {})
        viz_ideas.append(
            {
                "idea_id": idea["idea_id"],
                "label": idea["label"],
                "description": idea["description"],
                "scope": idea.get("scope", {}),
                "claim_ids": claim_ids,
                "rho": idea["frustration"]["rho"],
                "n_penrose": idea["frustration"].get("n_penrose", 0),
                "n_residual_edges": len(
                    idea["frustration"].get("residual_negative_edges", []) or []
                ),
                "agreement_score": idea["consensus"]["agreement_score"],
                "n_papers": idea["consensus"]["n_papers_represented"],
                "n_rewritten": idea["consensus"].get("n_rewritten", 0),
                "n_sensitive_claims": sum(
                    1 for cid in claim_ids if cid in sensitivity_by_claim
                ),
                "n_residual_claims": sum(1 for cid in claim_ids if cid in residual_claim_ids),
                "n_open_questions": len(open_questions),
                "n_next_steps": n_next_steps,
                "open_question_priorities": priority_counts,
                "next_step_kinds": next_step_counts,
                "open_questions": open_questions,
                "state_probability": state.get("probability", 0),
                "transitions_out_count": state.get(
                    "transitions_out", len(idea.get("transitions_out", []) or [])
                ),
                "transitions_in_count": state.get(
                    "transitions_in", len(idea.get("transitions_in", []) or [])
                ),
            }
        )

    fr = sheaf.get("frustration", {})
    ms = sheaf["map_section"]
    return {
        "corpus": sheaf.get("corpus", run.root.name),
        "run_id": sheaf.get("sheaf_id", run.root.name),
        "synthesis_paper_id": synthesis_paper_id,
        "lambda_rewrite_penalty": ms.get("lambda_rewrite_penalty"),
        "stats": {
            "n_papers": len(papers),
            "n_claims": len(viz_claims),
            "n_edges": len(edges),
            "n_ideas": len(viz_ideas),
            "rho": fr.get("rho", 0),
            "n_penrose": fr.get("n_penrose", 0),
            "n_residual_h1": len(ms.get("residual_h1", [])),
            "n_rewrites": sum(1 for c in viz_claims if c["is_rewritten"]),
            "n_lambda_sensitive": len(sensitivity_by_claim),
            "coherence": ms.get("coherence", 0),
            "rewrite_cost": ms.get("rewrite_cost", 0),
            "c_mu_bits": epsilon_machine.get("statistical_complexity_bits", 0),
            "effective_states": epsilon_machine.get("effective_states", 0),
            "transition_density": epsilon_machine.get("transition_graph", {}).get(
                "transition_density", 0
            ),
        },
        "papers": papers,
        "claims": viz_claims,
        "edges": edges,
        "ideas": viz_ideas,
        "epsilon_machine": epsilon_machine,
        "lambda_sensitivity": sensitivity,
    }


def render(
    run: Run,
    out_path: Path | None = None,
    synthesis_paper_id: str | None = None,
) -> Path:
    """Render the viz HTML for `run`. Returns the path written.

    If `synthesis_paper_id` is given, that paper is flagged as a synthesis /
    review paper — its claim nodes are rendered as ★ instead of ○ and an
    "Idea coverage" panel is shown by default in the side panel.
    """
    payload = _build_payload(run, synthesis_paper_id=synthesis_paper_id)
    template = TEMPLATE_PATH.read_text()
    html = template.replace("__PAYLOAD_JSON__", json.dumps(payload))
    if out_path is None:
        out_path = run.root / "constellation.html"
    out_path.write_text(html)
    return out_path
