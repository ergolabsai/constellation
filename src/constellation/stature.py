"""Stature -- how established each claim is in the current map.

A claim's stature is the count of distinct papers whose evidence
corroborates it at full strength. It is an emergent property of the
graph (no hardcoded weights, no extractor-set "importance"), and it is
the signal the optimizer uses to scale rewrite cost: a claim backed by
many independent papers should cost more to doubt than one that only
its own paper backs.

Crucially, we count only edges where the claim and the evidence agree
at full strength (residual below ``residual_threshold``). Contradicting
edges -- a prior claim wired to a new evidence node that disagrees with
it -- do NOT count as backing. Without that filter, a strongly
contradicted claim would gain stature from its own contradictions.

A nice side effect: scope-aware claims that explicitly predict prior
results in their own regimes inherit stature from those agreements. So
A_05 in the Atlas corpus (which explicitly predicts Newcomb, Angus,
Bondeson, Goedbloed, Brughmans values at their home evidence nodes and
matches each) ends up with stature ~6, while A_01/A_04/A_06/A_07
(which just assert stability at Atlas's own evidence and stay silent
on the others) stay at stature 1. The optimizer reads this directly:
A_05 is hard to doubt, the unscoped variants are easy.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable

from .sheaf import residual_for_edge
from .util import Json


DEFAULT_BACKING_RESIDUAL = 0.05
DEFAULT_LAMBDA_BASE = 1.0
DEFAULT_STATURE_ALPHA = 8.0
DEFAULT_NEW_CLAIM_DISCOUNT = 0.3


def compute_stature(
    claims: list[Json],
    evidence: list[Json],
    edges: list[Json],
    *,
    residual_threshold: float = DEFAULT_BACKING_RESIDUAL,
) -> dict[str, int]:
    """Return ``{claim_id: number of distinct backing papers}``.

    A paper backs a claim when at least one of its evidence pieces is
    wired to that claim and the prediction agrees with the measurement
    at full strength (residual_sq <= ``residual_threshold``).
    """
    evidence_by_id = {ev["evidence_id"]: ev for ev in evidence}
    paper_by_ev = {ev["evidence_id"]: ev["paper_id"] for ev in evidence}
    claim_by_id = {c["claim_id"]: c for c in claims}

    backing: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        cid = edge["claim_id"]
        eid = edge["evidence_id"]
        ev = evidence_by_id.get(eid)
        claim = claim_by_id.get(cid)
        if ev is None or claim is None:
            continue
        # Score the edge as if no accommodation had happened, so the
        # stature signal reflects raw consistency, not the optimizer's
        # later narrowing.
        probe = {**claim, "x_final": list(claim["x_init"])}
        r = residual_for_edge(probe, ev, edge, use_final=True)
        if r["residual_sq"] <= residual_threshold:
            backing[cid].add(paper_by_ev[eid])

    return {cid: len(papers) for cid, papers in backing.items()}


def stature_weighted_lambda(
    claims: list[Json],
    evidence: list[Json],
    edges: list[Json],
    *,
    new_paper_ids: set[str] | None = None,
    base: float = DEFAULT_LAMBDA_BASE,
    alpha: float = DEFAULT_STATURE_ALPHA,
    new_discount: float = DEFAULT_NEW_CLAIM_DISCOUNT,
    residual_threshold: float = DEFAULT_BACKING_RESIDUAL,
) -> tuple[Callable[[str], float], dict[str, int]]:
    """Build a per-claim lambda function for the optimizer, plus stature.

    The returned callable maps ``claim_id`` -> rewrite cost:

    * claims from ``new_paper_ids`` (the incoming contribution, when
      doing a situate operation) get the cheap ``new_discount``; the
      optimizer prefers to doubt the newcomer over the field.
    * every other claim gets ``base * (1 + alpha * stature(c))``;
      strongly backed claims become correspondingly expensive to doubt.

    Returns the lambda function and the underlying stature map (so
    callers can record or display it).
    """
    stature = compute_stature(
        claims, evidence, edges, residual_threshold=residual_threshold
    )
    incoming_papers = new_paper_ids or set()
    incoming_claim_ids = {
        c["claim_id"] for c in claims if c["paper_id"] in incoming_papers
    }

    def lambda_fn(claim_id: str) -> float:
        if claim_id in incoming_claim_ids:
            return new_discount
        return base * (1.0 + alpha * stature.get(claim_id, 0))

    return lambda_fn, stature
