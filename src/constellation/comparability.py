"""Cross-paper comparability groups -- evidence that measures the same
phenomenon across different papers.

A comparability group says: "these evidence nodes report the same
underlying physical quantity, even if their observable names or
contexts differ." When a claim makes a prediction targeting one member
of a group (its HOME member) but does not explicitly address the
others, the silence is treated as an implicit headline -- the claim is,
by omission, asserting that its home result extends to the rest of the
group. ``generate_semantic_cross_edges`` turns that silence into
auditable cross-edges the optimizer can score.

This is at a different level of abstraction than
``constellation.sheaf.build_evidence_comparability`` (which groups
evidence by raw observable name): cross-paper groups carry meaning
about which evidence ACTUALLY MEASURES THE SAME PHENOMENON across
papers, not just which strings happen to match.

In production the registry would be authored by a curator or written
by an LLM proposer. For now it lives as a JSON file alongside the
corpus, e.g. ``corpora/atlas/comparability.json``::

    {
      "groups": {
        "<group_name>": {
          "description": "...",
          "members": ["<evidence_id>", ...]
        }
      }
    }
"""
from __future__ import annotations

import json
from pathlib import Path

from .util import Json


def load_comparability(corpus_dir: Path) -> dict[str, Json]:
    """Read ``<corpus_dir>/comparability.json`` if present.

    Returns ``{}`` when no file exists. Each group entry is normalized
    to ``{"title": str, "description": str, "members": [evidence_ids]}``
    so downstream consumers (semantic propagator, idea consolidator)
    can read uniformly. Legacy v1 files that supply only a member list
    are accepted for back compat.
    """
    path = corpus_dir / "comparability.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    groups: dict[str, Json] = {}
    for name, body in data.get("groups", {}).items():
        if isinstance(body, dict):
            members = body.get("members", [])
            title = body.get("title", name)
            description = body.get("description", "")
        else:
            members = list(body)
            title = name
            description = ""
        groups[name] = {
            "title": str(title),
            "description": str(description),
            "members": [str(eid) for eid in members],
        }
    return groups


def group_members(groups: dict[str, Json]) -> dict[str, list[str]]:
    """Helper: extract just the ``{group_name: [members]}`` projection."""
    return {name: list(body.get("members", [])) for name, body in groups.items()}


def generate_semantic_cross_edges(
    claims: list[Json],
    evidence: list[Json],
    base_edges: list[Json],
    comparability: dict[str, Json] | dict[str, list[str]],
    *,
    scope_to_paper_ids: set[str] | None = None,
) -> list[Json]:
    """Propagate each claim's home stance across its comparability group.

    For every claim that has a HOME prediction inside a group (a
    prediction whose evidence_id belongs both to the group and to the
    claim's own paper), generate cross-edges to every OTHER member of
    the group the claim has not explicitly addressed. The cross-edge's
    base prediction value is the claim's home value -- the implicit
    extrapolation.

    Parameters
    ----------
    claims, evidence: all nodes in the map.
    base_edges: edges produced by ``generate_prediction_edges``. Used to
        avoid duplicating any (claim, evidence) wiring that already
        exists.
    comparability: ``{group_name: [evidence_ids]}`` from
        :func:`load_comparability`.
    scope_to_paper_ids: when set, propagate cross-edges only for claims
        from these papers (e.g., the incoming contribution in a situate
        operation). When ``None`` (default), apply to all claims.
    """
    if not comparability:
        return []

    ev_by_id = {ev["evidence_id"]: ev for ev in evidence}
    existing_pairs = {(e["claim_id"], e["evidence_id"]) for e in base_edges}
    new_edges: list[Json] = []

    # Normalize comparability to {group_name: [members]} for this function;
    # the rich-format dict has members under "members".
    members_by_group: dict[str, list[str]] = {}
    for name, body in comparability.items():
        if isinstance(body, dict):
            members_by_group[name] = list(body.get("members", []))
        else:
            members_by_group[name] = list(body)

    for claim in claims:
        if scope_to_paper_ids is not None and claim["paper_id"] not in scope_to_paper_ids:
            continue

        explicit_targets: set[str] = set()
        for pred in claim.get("predictions", []) or []:
            explicit_targets.update(pred.get("evidence_ids") or [])

        for group_name, members in members_by_group.items():
            home_ev, home_val = _find_home(claim, members, ev_by_id)
            if home_ev is None:
                continue
            for eid in members:
                if eid == home_ev or eid in explicit_targets:
                    continue
                if (claim["claim_id"], eid) in existing_pairs:
                    continue
                ev = ev_by_id.get(eid)
                if ev is None:
                    continue
                new_edges.append(_make_semantic_edge(claim, ev, home_ev, home_val, group_name))

    return new_edges


def _find_home(
    claim: Json,
    members: list[str],
    ev_by_id: dict[str, Json],
) -> tuple[str | None, float | None]:
    for pred in claim.get("predictions", []) or []:
        for eid in (pred.get("evidence_ids") or []):
            ev = ev_by_id.get(eid)
            if ev is None or eid not in members:
                continue
            if ev["paper_id"] == claim["paper_id"]:
                return eid, float(pred["value"])
    return None, None


def _make_semantic_edge(
    claim: Json,
    evidence: Json,
    home_ev: str,
    home_val: float,
    group_name: str,
) -> Json:
    dim = evidence["core"]["dimensions"][0]
    return {
        "edge_id": f"{claim['claim_id']}__{evidence['evidence_id']}__semantic",
        "claim_id": claim["claim_id"],
        "evidence_id": evidence["evidence_id"],
        "base_prediction": {
            "dimensions": [{
                "name": dim["name"],
                "value": home_val,
                "scale": dim.get("scale", "normalized_binary"),
            }]
        },
        "regime_tag": "out_of_regime",
        "edge_stalk": {
            "dimensions": [{
                "name": dim["name"],
                "scale": dim.get("scale", "normalized_binary"),
            }]
        },
        "prediction_rationale": (
            f"semantic cross-edge ({group_name}): {claim['claim_id']} states "
            f"{home_ev}={home_val} but does not address comparable "
            f"{evidence['evidence_id']}; propagating home stance."
        ),
        "provenance": {
            "prediction_generated_by": "semantic_comparability_group",
            "group": group_name,
            "home_evidence": home_ev,
            "confidence": 0.5,
            "review_status": "unreviewed",
        },
    }
