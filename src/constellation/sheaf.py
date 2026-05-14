from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from typing import Iterable

from .seeds import atlas_seeded_ideas
from .util import Json, now_utc, write_json


DEFAULT_LAMBDA_CLAIM = 1.0
DEFAULT_LAMBDA_CONTEXT = 5.0


def build_evidence_comparability(evidence: list[Json]) -> Json:
    groups: dict[str, list[str]] = defaultdict(list)
    for ev in evidence:
        for dim in ev["core"]["dimensions"]:
            groups[dim["name"]].append(ev["evidence_id"])
    return {
        "groups": [
            {"observable": observable, "evidence_ids": sorted(ids)}
            for observable, ids in sorted(groups.items())
        ]
    }


def generate_prediction_edges(claims: list[Json], evidence: list[Json]) -> list[Json]:
    evidence_by_observable: dict[str, list[Json]] = defaultdict(list)
    for ev in evidence:
        for dim in ev["core"]["dimensions"]:
            evidence_by_observable[dim["name"]].append(ev)

    edges: list[Json] = []
    seen: set[str] = set()
    for claim in claims:
        for prediction in claim.get("predictions", []):
            observable = prediction["observable"]
            target_ids = set(prediction.get("evidence_ids", []))
            for ev in evidence_by_observable.get(observable, []):
                if target_ids and ev["evidence_id"] not in target_ids:
                    continue
                edge_id = f"{claim['claim_id']}__{ev['evidence_id']}"
                if edge_id in seen:
                    continue
                seen.add(edge_id)
                tag = prediction.get("regime_tag") or regime_tag(claim, ev)
                edges.append(
                    {
                        "edge_id": edge_id,
                        "claim_id": claim["claim_id"],
                        "evidence_id": ev["evidence_id"],
                        "base_prediction": {
                            "dimensions": [
                                {
                                    "name": observable,
                                    "value": float(prediction["value"]),
                                    "scale": prediction.get("scale", "normalized_binary"),
                                }
                            ]
                        },
                        "regime_tag": tag,
                        "edge_stalk": {
                            "dimensions": [
                                {
                                    "name": observable,
                                    "scale": prediction.get("scale", "normalized_binary"),
                                }
                            ]
                        },
                        "prediction_rationale": (
                            f"Claim {claim['claim_id']} predicts {observable}="
                            f"{prediction['value']} at evidence {ev['evidence_id']}."
                        ),
                        "provenance": {
                            "prediction_generated_by": "deterministic_observable_match",
                            "confidence": min(
                                claim["provenance"].get("confidence", 0.5),
                                ev["provenance"].get("confidence", 0.5),
                            ),
                            "review_status": "unreviewed",
                        },
                    }
                )
    return edges


def regime_tag(claim: Json, evidence: Json) -> str:
    haystack = " ".join(
        [
            evidence.get("paper_id", ""),
            evidence.get("label", ""),
            evidence.get("context", {}).get("system", ""),
            evidence.get("context", {}).get("framework", ""),
            evidence.get("context", {}).get("regime", ""),
        ]
    ).lower()
    keywords = [k.lower() for k in claim.get("home_regime", {}).get("regime_keywords", [])]
    if evidence["paper_id"] == claim["paper_id"]:
        return "in_regime"
    if keywords and any(k in haystack for k in keywords):
        return "in_regime"
    return "out_of_regime"


def actual_dimension(evidence: Json, name: str) -> Json:
    for dim in evidence["core"]["dimensions"]:
        if dim["name"] == name:
            return dim
    raise KeyError(f"evidence {evidence['evidence_id']} has no dimension {name}")


def residual_for_edge(claim: Json, evidence: Json, edge: Json, *, use_final: bool) -> Json:
    claim_state = claim["x_final"] if use_final else claim["x_init"]
    strength = float(claim_state[0] if edge["regime_tag"] == "in_regime" else claim_state[1])
    residual_dims = []
    residual_sq = 0.0
    for pred in edge["base_prediction"]["dimensions"]:
        actual = actual_dimension(evidence, pred["name"])
        predicted = strength * float(pred["value"]) + (1.0 - strength) * float(actual["value"])
        residual = predicted - float(actual["value"])
        residual_sq += residual * residual
        residual_dims.append(
            {
                "name": pred["name"],
                "actual": float(actual["value"]),
                "base_prediction": float(pred["value"]),
                "predicted": predicted,
                "residual": residual,
                "strength": strength,
            }
        )
    return {
        "edge_id": edge["edge_id"],
        "residual_sq": residual_sq,
        "dimensions": residual_dims,
    }


def residuals(claims: list[Json], evidence: list[Json], edges: list[Json], *, use_final: bool) -> list[Json]:
    claim_by_id = {c["claim_id"]: c for c in claims}
    evidence_by_id = {ev["evidence_id"]: ev for ev in evidence}
    return [
        residual_for_edge(
            claim_by_id[edge["claim_id"]],
            evidence_by_id[edge["evidence_id"]],
            edge,
            use_final=use_final,
        )
        for edge in edges
    ]


def residual_total(items: Iterable[Json]) -> float:
    return sum(float(item["residual_sq"]) for item in items)


def optimize_claim_rewrites(
    claims: list[Json],
    evidence: list[Json],
    edges: list[Json],
    *,
    lambda_claim: float = DEFAULT_LAMBDA_CLAIM,
) -> list[Json]:
    evidence_by_id = {ev["evidence_id"]: ev for ev in evidence}
    edges_by_claim: dict[str, list[Json]] = defaultdict(list)
    for edge in edges:
        edges_by_claim[edge["claim_id"]].append(edge)

    operations: list[Json] = []
    candidate_out_strengths = [1.0, 0.8, 0.6, 0.4, 0.2, 0.0]
    for claim in claims:
        claim_edges = edges_by_claim.get(claim["claim_id"], [])
        if not claim_edges:
            continue

        original_state = list(claim["x_final"])
        best_state = original_state
        best_score = _claim_objective(claim, claim_edges, evidence_by_id, lambda_claim)
        best_residual = _claim_residual_total(claim, claim_edges, evidence_by_id)

        for out_strength in candidate_out_strengths:
            claim["x_final"] = [1.0, out_strength]
            score = _claim_objective(claim, claim_edges, evidence_by_id, lambda_claim)
            if score < best_score - 1e-12:
                best_score = score
                best_state = list(claim["x_final"])
                best_residual = _claim_residual_total(claim, claim_edges, evidence_by_id)

        claim["x_final"] = best_state
        if best_state != original_state:
            distance = sum((a - b) ** 2 for a, b in zip(best_state, claim["x_init"], strict=True)) ** 0.5
            initial_residual = _claim_residual_total(
                {**claim, "x_final": original_state},
                claim_edges,
                evidence_by_id,
            )
            op = {
                "operation": "narrow_out_of_regime_strength",
                "claim_id": claim["claim_id"],
                "from": original_state,
                "to": best_state,
                "distance": distance,
                "initial_residual": initial_residual,
                "final_residual": best_residual,
                "objective": best_score,
                "justification": (
                    "Out-of-regime predictions created residuals; narrowing preserves "
                    "in-regime strength while reducing cross-regime tension."
                ),
            }
            claim["rewrite_history"].append(op)
            operations.append(op)

    return operations


def _claim_residual_total(claim: Json, edges: list[Json], evidence_by_id: dict[str, Json]) -> float:
    return residual_total(
        residual_for_edge(claim, evidence_by_id[edge["evidence_id"]], edge, use_final=True)
        for edge in edges
    )


def _claim_objective(
    claim: Json,
    edges: list[Json],
    evidence_by_id: dict[str, Json],
    lambda_claim: float,
) -> float:
    rewrite_penalty = sum(
        (float(a) - float(b)) ** 2 for a, b in zip(claim["x_final"], claim["x_init"], strict=True)
    )
    return _claim_residual_total(claim, edges, evidence_by_id) + lambda_claim * rewrite_penalty


def build_sheaf(
    corpus_name: str,
    claims: list[Json],
    evidence: list[Json],
    edges: list[Json],
    operations: list[Json],
    *,
    lambda_claim: float = DEFAULT_LAMBDA_CLAIM,
    lambda_context: float = DEFAULT_LAMBDA_CONTEXT,
) -> Json:
    initial_residuals = residuals(claims, evidence, edges, use_final=False)
    final_residuals = residuals(claims, evidence, edges, use_final=True)

    residual_by_edge = {
        item["edge_id"]: item for item in final_residuals if item["residual_sq"] > 0.05
    }
    remaining_tensions = []
    for edge in edges:
        residual = residual_by_edge.get(edge["edge_id"])
        if not residual:
            continue
        remaining_tensions.append(
            {
                "edge_id": edge["edge_id"],
                "claim_id": edge["claim_id"],
                "evidence_id": edge["evidence_id"],
                "residual": residual["residual_sq"],
                "interpretation": (
                    f"{edge['claim_id']} still predicts poorly at {edge['evidence_id']} "
                    f"after allowed rewrites."
                ),
            }
        )

    claim_rewrite_distance = sum(float(op["distance"]) for op in operations)
    return {
        "sheaf_id": f"{corpus_name}_v05",
        "version": "v0.5_bipartite",
        "created_at": now_utc(),
        "claim_vertices": [c["claim_id"] for c in claims],
        "evidence_vertices": [ev["evidence_id"] for ev in evidence],
        "edges": edges,
        "residuals": {
            "initial": initial_residuals,
            "final": final_residuals,
        },
        "objective": {
            "initial_residual": residual_total(initial_residuals),
            "final_residual": residual_total(final_residuals),
            "claim_rewrite_distance": claim_rewrite_distance,
            "context_fill_distance": 0.0,
            "lambda_claim": lambda_claim,
            "lambda_context": lambda_context,
        },
        "operations": operations,
        "remaining_tensions": remaining_tensions,
        "provenance": {
            "builder": "constellation.v0.5.standard_library",
            "evidence_core_policy": "locked",
        },
    }


def consolidate_ideas(corpus_name: str, claims: list[Json], evidence: list[Json], sheaf: Json) -> list[Json]:
    seeded_ideas = atlas_seeded_ideas(corpus_name, claims, evidence, sheaf)
    if seeded_ideas is not None:
        return seeded_ideas

    claim_ids = {c["claim_id"] for c in claims}
    evidence_ids = {ev["evidence_id"] for ev in evidence}
    graph: dict[str, set[str]] = {f"c:{cid}": set() for cid in claim_ids}
    graph.update({f"e:{eid}": set() for eid in evidence_ids})
    for edge in sheaf["edges"]:
        cnode = f"c:{edge['claim_id']}"
        enode = f"e:{edge['evidence_id']}"
        graph[cnode].add(enode)
        graph[enode].add(cnode)

    components: list[set[str]] = []
    seen: set[str] = set()
    for node in sorted(graph):
        if node in seen:
            continue
        queue = deque([node])
        seen.add(node)
        component: set[str] = set()
        while queue:
            cur = queue.popleft()
            component.add(cur)
            for nxt in graph[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        components.append(component)

    claim_by_id = {c["claim_id"]: c for c in claims}
    evidence_by_id = {ev["evidence_id"]: ev for ev in evidence}
    initial_residual_by_edge = {
        r["edge_id"]: r["residual_sq"] for r in sheaf["residuals"]["initial"]
    }
    final_residual_by_edge = {
        r["edge_id"]: r["residual_sq"] for r in sheaf["residuals"]["final"]
    }
    ideas: list[Json] = []
    for idx, component in enumerate(components, 1):
        component_claims = sorted(n[2:] for n in component if n.startswith("c:"))
        component_evidence = sorted(n[2:] for n in component if n.startswith("e:"))
        if not component_claims and not component_evidence:
            continue
        observables = sorted(
            {
                dim["name"]
                for ev_id in component_evidence
                for dim in evidence_by_id[ev_id]["core"]["dimensions"]
            }
        )
        title = _idea_title(observables)
        edge_ids = [
            edge["edge_id"]
            for edge in sheaf["edges"]
            if edge["claim_id"] in component_claims and edge["evidence_id"] in component_evidence
        ]
        resolved = [
            {
                "edge_id": edge["edge_id"],
                "resolution": f"{edge['claim_id']} narrowed to reduce cross-regime residual.",
            }
            for edge in sheaf["edges"]
            if edge["edge_id"] in edge_ids
            and any(op["claim_id"] == edge["claim_id"] for op in sheaf["operations"])
            and initial_residual_by_edge.get(edge["edge_id"], 0.0) > 0.05
            and final_residual_by_edge.get(edge["edge_id"], 0.0) < 0.1
        ]
        remaining = [
            tension for tension in sheaf["remaining_tensions"] if tension["edge_id"] in edge_ids
        ]
        idea_id = f"idea_{idx:02d}_{_idea_slug(observables)}"
        ideas.append(
            {
                "idea_id": idea_id,
                "title": title,
                "scope": _idea_scope(component_claims, claim_by_id),
                "contributing_claims": component_claims,
                "contributing_evidence": component_evidence,
                "tensions_resolved": resolved,
                "remaining_tensions": remaining,
                "open_questions": _open_questions(observables, remaining),
                "transitions_out": [],
                "provenance": {
                    "consolidator": "deterministic_connected_components",
                    "corpus": corpus_name,
                },
            }
        )
    return ideas


def _idea_title(observables: list[str]) -> str:
    if "m1_stabilized" in observables:
        return "m=1 stability is observed, but linear ideal-MHD explanations are scope-limited"
    if "m0_growth_reduced" in observables:
        return "m=0 growth reduction appears across MHD and gyrokinetic shear studies"
    if "ideal_mhd_short_scale_valid" in observables:
        return "Short-scale m=0 behavior needs kinetic or gyrokinetic physics"
    if "m0_threshold_profile_dependent" in observables:
        return "m=0 stabilization thresholds depend on equilibrium profile"
    return "Scoped claim-evidence knowledge unit"


def _idea_slug(observables: list[str]) -> str:
    return "_".join(observables) if observables else "ungrouped"


def _idea_scope(claim_ids: list[str], claim_by_id: dict[str, Json]) -> Json:
    systems = sorted({claim_by_id[cid].get("home_regime", {}).get("system", "") for cid in claim_ids})
    frameworks = sorted(
        {claim_by_id[cid].get("home_regime", {}).get("framework", "") for cid in claim_ids}
    )
    return {
        "system": "; ".join(s for s in systems if s) or "unspecified",
        "framework": "; ".join(f for f in frameworks if f) or "mixed",
        "regime": " / ".join(claim_ids),
    }


def _open_questions(observables: list[str], remaining: list[Json]) -> list[Json]:
    questions = []
    if "m1_stabilized" in observables:
        questions.append(
            {
                "question": "Which nonlinear, kinetic, or profile effects explain the observed m=1 stability outside the linear ideal-MHD threshold model?",
                "priority": "high",
                "suggested_next_steps": [
                    _next_work(
                        "theory",
                        "Mechanism split",
                        "Separate nonlinear, kinetic, and profile-shape explanations into distinct claim families before comparing them to m=1 evidence.",
                    ),
                    _next_work(
                        "simulation",
                        "Profile-effect scan",
                        "Run m=1 stability scans across the profile features missing from the linear ideal-MHD threshold model.",
                    ),
                    _next_work(
                        "literature",
                        "Corpus expansion",
                        "Add papers that test nonlinear and kinetic stabilization mechanisms in sheared Z-pinches.",
                    ),
                ],
            }
        )
    if "ideal_mhd_short_scale_valid" in observables:
        questions.append(
            {
                "question": "Where is the practical boundary between ideal-MHD and gyrokinetic descriptions for short-scale Z-pinch modes?",
                "priority": "medium",
                "suggested_next_steps": [
                    _next_work(
                        "benchmark",
                        "Shared mode benchmark",
                        "Compare ideal-MHD and gyrokinetic predictions on the same equilibrium and wavelength grid.",
                    ),
                    _next_work(
                        "simulation",
                        "Short-scale sweep",
                        "Sweep k rho_i and track where ideal-MHD predictions depart from gyrokinetic evidence.",
                    ),
                ],
            }
        )
    if remaining:
        questions.append(
            {
                "question": "Which remaining residuals need human domain review before consolidation?",
                "priority": "blocking",
                "suggested_next_steps": [
                    _next_work(
                        "audit",
                        "Residual review",
                        "Inspect the highest-residual edges and decide whether the issue is extraction, regime tagging, or a genuine scientific tension.",
                    )
                ],
            }
        )
    return questions


def _next_work(kind: str, title: str, description: str) -> Json:
    return {"kind": kind, "title": title, "description": description}


def write_sheaf_artifacts(run_dir: Path, comparability: Json, edges: list[Json], sheaf: Json, ideas: list[Json]) -> None:
    write_json(run_dir / "evidence_comparability.json", comparability)
    write_json(run_dir / "prediction_edges.json", {"edges": edges})
    write_json(run_dir / "sheaf.json", sheaf)
    write_json(run_dir / "operations.json", {"operations": sheaf["operations"]})
    for idea in ideas:
        write_json(run_dir / "ideas" / f"{idea['idea_id']}.json", idea)
