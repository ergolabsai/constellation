"""Validation helpers for Idea membership.

The LLM can propose labels, prose, transitions, and questions, but claim
membership is a hard contract: Ideas must form an exact partition of the
MAP-selected claims.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable


def _short_list(values: list[str], *, limit: int = 8) -> str:
    if len(values) <= limit:
        return ", ".join(values)
    return ", ".join(values[:limit]) + f", ... (+{len(values) - limit} more)"


def validate_idea_partition(ideas: list[dict], selected_claim_ids: Iterable[str]) -> None:
    """Require Ideas to form an exact partition of the MAP-selected claims."""
    selected = set(selected_claim_ids)
    empty_ideas: list[str] = []
    claim_to_ideas: dict[str, list[str]] = defaultdict(list)

    for i, idea in enumerate(ideas, 1):
        idea_id = str(idea.get("idea_id") or f"<idea {i}>")
        contributing = idea.get("contributing_claims", []) or []
        if not contributing:
            empty_ideas.append(idea_id)
            continue
        for contribution in contributing:
            if not isinstance(contribution, dict) or not contribution.get("claim_id"):
                claim_to_ideas["<missing claim_id>"].append(idea_id)
                continue
            claim_to_ideas[str(contribution["claim_id"])].append(idea_id)

    covered = set(claim_to_ideas)
    missing = sorted(selected - covered)
    unknown = {
        cid: ids for cid, ids in claim_to_ideas.items() if cid not in selected
    }
    duplicated = {
        cid: ids for cid, ids in claim_to_ideas.items()
        if cid in selected and len(ids) > 1
    }

    if not (empty_ideas or missing or unknown or duplicated):
        return

    parts: list[str] = []
    if empty_ideas:
        parts.append(f"empty Ideas: {_short_list(sorted(empty_ideas))}")
    if missing:
        parts.append(f"missing MAP claims: {_short_list(missing)}")
    if unknown:
        rows = [
            f"{cid} in {_short_list(ids, limit=3)}"
            for cid, ids in sorted(unknown.items())
        ]
        parts.append(f"non-MAP claims referenced: {'; '.join(rows)}")
    if duplicated:
        rows = [
            f"{cid} in {_short_list(ids, limit=3)}"
            for cid, ids in sorted(duplicated.items())
        ]
        parts.append(f"duplicated MAP claims: {'; '.join(rows)}")

    raise ValueError("Idea partition invalid: " + " | ".join(parts))
