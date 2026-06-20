from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from typing import Callable, Iterable

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
    lambda_fn: Callable[[str], float] | None = None,
    lambda_claim: float = DEFAULT_LAMBDA_CLAIM,
) -> list[Json]:
    """Hill-climb each claim's out-of-regime strength to minimize
    residual + lambda * rewrite_penalty.

    When ``lambda_fn`` is supplied it is consulted per claim, so the
    rewrite cost can scale with stature (claims backed by many
    independent papers cost more to doubt) or be discounted for an
    incoming contribution. When ``lambda_fn`` is absent, the optimizer
    falls back to the flat ``lambda_claim`` for every claim -- the old
    behavior, preserved so non-stature callers keep working.
    """
    evidence_by_id = {ev["evidence_id"]: ev for ev in evidence}
    edges_by_claim: dict[str, list[Json]] = defaultdict(list)
    for edge in edges:
        edges_by_claim[edge["claim_id"]].append(edge)

    if lambda_fn is None:
        flat_lambda = float(lambda_claim)

        def lambda_fn(_cid: str) -> float:
            return flat_lambda

    operations: list[Json] = []
    candidate_out_strengths = [1.0, 0.8, 0.6, 0.4, 0.2, 0.0]
    for claim in claims:
        claim_edges = edges_by_claim.get(claim["claim_id"], [])
        if not claim_edges:
            continue

        lam = float(lambda_fn(claim["claim_id"]))
        original_state = list(claim["x_final"])
        best_state = original_state
        best_score = _claim_objective(claim, claim_edges, evidence_by_id, lam)
        best_residual = _claim_residual_total(claim, claim_edges, evidence_by_id)

        for out_strength in candidate_out_strengths:
            claim["x_final"] = [1.0, out_strength]
            score = _claim_objective(claim, claim_edges, evidence_by_id, lam)
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
                "lambda": lam,
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
    stature: dict[str, int] | None = None,
    lambda_model: str = "flat",
    incoming_paper_ids: set[str] | None = None,
    semantic_edge_ids: set[str] | None = None,
    claim_hygiene: dict[str, Json] | None = None,
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
            "lambda_model": lambda_model,
        },
        "operations": operations,
        "remaining_tensions": remaining_tensions,
        "stature": dict(stature) if stature else {},
        "incoming_paper_ids": sorted(incoming_paper_ids) if incoming_paper_ids else [],
        "semantic_edge_ids": sorted(semantic_edge_ids) if semantic_edge_ids else [],
        "claim_hygiene": dict(claim_hygiene) if claim_hygiene else {},
        "provenance": {
            "builder": "constellation.v0.5.standard_library",
            "evidence_core_policy": "locked",
        },
    }


def consolidate_ideas(
    corpus_name: str,
    claims: list[Json],
    evidence: list[Json],
    sheaf: Json,
    comparability: dict[str, Json] | None = None,
) -> list[Json]:
    """Each comparability group becomes one idea.

    The idea's title and description come from the group registry.
    Contributing evidence = the group's members. Contributing claims =
    every claim with at least one edge to one of those evidence nodes.
    Resolved / remaining tensions are the subset of map operations and
    surviving residuals that live on edges inside the idea.

    Claims and evidence not covered by any group fall into a final
    ``Ungrouped`` idea so the demo always sees them, but they do not
    drive any tension surface.
    """
    comparability = comparability or {}
    claim_by_id = {c["claim_id"]: c for c in claims}
    evidence_by_id = {ev["evidence_id"]: ev for ev in evidence}
    initial_residual_by_edge = {
        r["edge_id"]: r["residual_sq"] for r in sheaf["residuals"]["initial"]
    }
    final_residual_by_edge = {
        r["edge_id"]: r["residual_sq"] for r in sheaf["residuals"]["final"]
    }
    remaining_by_edge = {t["edge_id"]: t for t in sheaf.get("remaining_tensions", [])}
    operations_by_claim = {op["claim_id"]: op for op in sheaf.get("operations", [])}
    edges_by_evidence: dict[str, list[Json]] = defaultdict(list)
    for edge in sheaf["edges"]:
        edges_by_evidence[edge["evidence_id"]].append(edge)

    ideas: list[Json] = []
    covered_evidence: set[str] = set()
    covered_claims: set[str] = set()

    for idx, (group_name, group) in enumerate(sorted(comparability.items()), 1):
        members = list(group.get("members", []))
        idea_evidence = [eid for eid in members if eid in evidence_by_id]
        if not idea_evidence:
            continue

        idea_claim_set: set[str] = set()
        idea_edge_ids: list[str] = []
        for eid in idea_evidence:
            for edge in edges_by_evidence.get(eid, []):
                idea_claim_set.add(edge["claim_id"])
                idea_edge_ids.append(edge["edge_id"])
        idea_claims = sorted(idea_claim_set)

        resolved = [
            {
                "edge_id": edge_id,
                "resolution": (
                    f"{edge_id.split('__')[0]} narrowed to reduce cross-regime "
                    "residual within this group."
                ),
            }
            for edge_id in idea_edge_ids
            if initial_residual_by_edge.get(edge_id, 0.0) > 0.05
            and final_residual_by_edge.get(edge_id, 0.0) < 0.1
            and operations_by_claim.get(edge_id.split("__")[0]) is not None
        ]
        remaining = [
            remaining_by_edge[edge_id]
            for edge_id in idea_edge_ids
            if edge_id in remaining_by_edge
        ]

        idea_id = f"idea_{idx:02d}_{group_name}"
        ideas.append(
            {
                "idea_id": idea_id,
                "group_id": group_name,
                "title": group.get("title") or group_name,
                "description": group.get("description", ""),
                "scope": _idea_scope(idea_claims, claim_by_id),
                "contributing_claims": idea_claims,
                "contributing_evidence": idea_evidence,
                "tensions_resolved": resolved,
                "remaining_tensions": remaining,
                "open_questions": _group_open_questions(
                    group, remaining, sheaf.get("claim_hygiene", {}), idea_claims
                ),
                "transitions_out": [],
                "provenance": {
                    "consolidator": "comparability_group",
                    "corpus": corpus_name,
                    "group": group_name,
                },
            }
        )
        covered_evidence.update(idea_evidence)
        covered_claims.update(idea_claims)

    # Catch-all "Ungrouped" idea for nodes that no comparability group
    # covers. These appear on the map but never drive a tension surface.
    ungrouped_evidence = sorted(
        eid for eid in evidence_by_id if eid not in covered_evidence
    )
    ungrouped_claims = sorted(
        cid for cid in claim_by_id
        if cid not in covered_claims
        and not any(
            edge["claim_id"] == cid and edge["evidence_id"] in covered_evidence
            for edge in sheaf["edges"]
        )
    )
    if ungrouped_evidence or ungrouped_claims:
        ideas.append(
            {
                "idea_id": f"idea_{len(ideas)+1:02d}_ungrouped",
                "group_id": "ungrouped",
                "title": "Ungrouped (no comparability group authored yet)",
                "description": (
                    "Claims and evidence not covered by any comparability group. "
                    "Add a group to the corpus's comparability.json to surface "
                    "these as a first-class idea with cross-paper accountability."
                ),
                "scope": _idea_scope(ungrouped_claims, claim_by_id),
                "contributing_claims": ungrouped_claims,
                "contributing_evidence": ungrouped_evidence,
                "tensions_resolved": [],
                "remaining_tensions": [],
                "open_questions": [],
                "transitions_out": [],
                "provenance": {
                    "consolidator": "comparability_group",
                    "corpus": corpus_name,
                    "group": "ungrouped",
                },
            }
        )
    return ideas


def _group_open_questions(
    group: Json,
    remaining: list[Json],
    claim_hygiene: dict[str, Json],
    idea_claims: list[str],
) -> list[Json]:
    questions: list[Json] = []
    implicit_in_idea = [
        cid for cid in idea_claims
        if claim_hygiene.get(cid, {}).get("status") == "implicit_headline"
    ]
    if remaining:
        questions.append({
            "question": (
                f"Which of the {len(remaining)} surviving tension(s) in this group "
                "are real disagreements vs. extraction or comparability artifacts?"
            ),
            "priority": "blocking",
            "suggested_next_steps": [
                _next_work(
                    "audit",
                    "Residual edge review",
                    "Inspect each remaining high-residual edge inside this group "
                    "against the source PDFs and decide whether the edge, regime "
                    "tag, or claim scope is wrong.",
                ),
            ],
        })
    if implicit_in_idea:
        questions.append({
            "question": (
                f"Are the implicit-headline claim(s) {', '.join(implicit_in_idea)} "
                "actually intended to generalize across this group, or do their "
                "authors scope them more narrowly than the propagator assumes?"
            ),
            "priority": "high",
            "suggested_next_steps": [
                _next_work(
                    "literature",
                    "Scope verification",
                    "Read each implicit-headline claim's source paper and decide "
                    "whether to add explicit out-of-regime predictions or to mark "
                    "the claim as scoped only to its home regime.",
                ),
            ],
        })
    if not remaining and not implicit_in_idea:
        questions.append({
            "question": (
                f"The field appears to agree about {group.get('title', 'this group')}. "
                "What experiment or derivation would actually change this consensus?"
            ),
            "priority": "exploratory",
            "suggested_next_steps": [
                _next_work(
                    "experiment",
                    "Counter-experiment proposal",
                    "Identify a measurement that, if it landed at a value contrary "
                    "to the current consensus, would force a rewrite within the group.",
                ),
            ],
        })
    return questions


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
