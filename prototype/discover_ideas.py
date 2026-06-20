"""
PROTOTYPE -- not wired into the pipeline, does not modify src/.

Discovers ideas algorithmically from claim stance vectors, instead of
treating each comparability group as one idea. The mapping to the
epsilon-machine view:

    causal state           = (regime condition, predicted distribution)
    idea                   = maximal coherent submodel = a stance signature
                             on which several claims agree
    stance vector for C    = indexed by (group, evidence_id), value at
                             each position is C's explicit prediction
                             there, or its home-propagated value, or NA
                             if C does not address that evidence
    "C1 and C2 cohere"     = their stance vectors overlap and agree
                             everywhere they overlap
    discovered idea        = maximal clique in the coherence graph

The algorithm naturally handles multi-membership: a claim that
contributes stance in multiple groups will appear in any idea its
stance is consistent with. It also avoids the multi-paper grouping
mistake we made manually with `hall_two_fluid_corrections`, because
two claims that propagate to a shared evidence with incompatible values
are simply not connected in the coherence graph.

Run:
    PYTHONPATH=src python prototype/discover_ideas.py \\
        --map corpora/atlas/v05 --corpus corpora/atlas
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from constellation.comparability import load_comparability


AGREE_TOLERANCE = 0.05
MIN_SHARED_POSITIONS = 2  # cliques mode: how many positions two claims must overlap on


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def load_run(run_dir: Path) -> tuple[list[dict], list[dict], dict]:
    claims = [json.loads(p.read_text()) for p in sorted((run_dir / "claims").glob("*.json"))]
    evidence = [json.loads(p.read_text()) for p in sorted((run_dir / "evidence").glob("*.json"))]
    sheaf = json.loads((run_dir / "sheaf.json").read_text())
    return claims, evidence, sheaf


# ---------------------------------------------------------------------------
# stance vector
# ---------------------------------------------------------------------------

def build_stance(
    claim: dict,
    comparability: dict[str, dict],
    evidence_by_id: dict[str, dict],
) -> dict[tuple[str, str], float]:
    """Stance for `claim`: {(group, evidence_id): predicted_value}.

    Explicit predictions take precedence over home propagation. Positions
    the claim does not address are simply absent from the dict (== NA).
    """
    stance: dict[tuple[str, str], float] = {}

    # gather explicit predictions
    explicit: dict[str, float] = {}
    for pred in claim.get("predictions", []) or []:
        for eid in pred.get("evidence_ids") or []:
            explicit[eid] = float(pred["value"])

    for group_name, group in comparability.items():
        members = list(group.get("members", []))
        if not members:
            continue

        # find home value in this group
        home_val: float | None = None
        for pred in claim.get("predictions", []) or []:
            for eid in pred.get("evidence_ids") or []:
                if eid not in members:
                    continue
                ev = evidence_by_id.get(eid)
                if ev and ev["paper_id"] == claim["paper_id"]:
                    home_val = float(pred["value"])
                    break
            if home_val is not None:
                break

        for eid in members:
            if eid not in evidence_by_id:
                continue
            if eid in explicit:
                stance[(group_name, eid)] = explicit[eid]
            elif home_val is not None:
                stance[(group_name, eid)] = home_val
    return stance


def coheres(s1: dict, s2: dict, min_shared: int = MIN_SHARED_POSITIONS) -> bool:
    """True iff s1 and s2 share at least ``min_shared`` positions and
    agree everywhere they overlap (within ``AGREE_TOLERANCE``).

    The minimum-shared rule guards against spurious pairings where two
    claims happen to predict the same value at a single position by
    coincidence rather than because they share an underlying mechanism.
    """
    shared = set(s1.keys()) & set(s2.keys())
    if len(shared) < min_shared:
        return False
    return all(abs(s1[k] - s2[k]) < AGREE_TOLERANCE for k in shared)


# ---------------------------------------------------------------------------
# stance equivalence (partition mode)
# ---------------------------------------------------------------------------

def stance_signature(stance: dict[tuple[str, str], float]) -> tuple:
    """Hashable canonical form of a stance vector."""
    return tuple(sorted((k, round(v, 2)) for k, v in stance.items()))


def equivalence_partition(
    stances: dict[str, dict],
) -> list[set[str]]:
    buckets: dict[tuple, set[str]] = defaultdict(set)
    for cid, s in stances.items():
        buckets[stance_signature(s)].add(cid)
    return list(buckets.values())


# ---------------------------------------------------------------------------
# paper-level stance aggregation
# ---------------------------------------------------------------------------

def paper_stances(
    claims: list[dict],
    comparability: dict[str, dict],
    evidence_by_id: dict[str, dict],
) -> tuple[dict[str, dict], dict[str, list[str]]]:
    """Aggregate each paper's claims into a single union stance vector.

    Rule: explicit predictions override propagated home values within the
    paper. The paper's contribution at each (group, evidence) position is
    the most-explicit assertion any of its claims makes there.
    """
    by_paper: dict[str, list[dict]] = defaultdict(list)
    for c in claims:
        by_paper[c["paper_id"]].append(c)

    paper_stance: dict[str, dict] = {}
    paper_claims: dict[str, list[str]] = {}

    for paper_id, paper_claim_list in by_paper.items():
        explicit_positions: dict[tuple[str, str], float] = {}
        propagated_positions: dict[tuple[str, str], float] = {}

        for c in paper_claim_list:
            explicit_targets: dict[str, float] = {}
            for pred in c.get("predictions", []) or []:
                for eid in pred.get("evidence_ids") or []:
                    explicit_targets[eid] = float(pred["value"])

            for group_name, group in comparability.items():
                members = list(group.get("members", []))
                if not members:
                    continue

                home_val: float | None = None
                for eid, val in explicit_targets.items():
                    if eid not in members:
                        continue
                    ev = evidence_by_id.get(eid)
                    if ev and ev["paper_id"] == paper_id:
                        home_val = val
                        break

                for eid in members:
                    if eid not in evidence_by_id:
                        continue
                    if eid in explicit_targets:
                        explicit_positions[(group_name, eid)] = explicit_targets[eid]
                    elif home_val is not None and (group_name, eid) not in propagated_positions:
                        propagated_positions[(group_name, eid)] = home_val

        # explicit overrides propagated
        union = {**propagated_positions, **explicit_positions}
        if union:
            paper_stance[paper_id] = union
        paper_claims[paper_id] = sorted(c["claim_id"] for c in paper_claim_list)

    return paper_stance, paper_claims


# ---------------------------------------------------------------------------
# Mode E: (group, direction) buckets
# ---------------------------------------------------------------------------

def group_value_buckets(
    claims: list[dict],
    comparability: dict[str, dict],
    evidence_by_id: dict[str, dict],
) -> list[dict]:
    """Each (group, direction in {positive, negative}) tuple becomes one
    idea. A paper contributes to the idea iff at least one of its claims
    has an explicit prediction targeting an evidence node in the group
    whose value falls in that direction.

    Direction is chosen at threshold 0.5 because the corpus uses
    normalized binary semantics (1 = stable / exists / passes, 0 =
    unstable / absent / fails). Partial values (e.g., Angus's 0.85)
    still land on the positive side -- they're supporting the
    direction even if the magnitude is muted.
    """
    member_to_group: dict[str, str] = {}
    for group_name, group in comparability.items():
        for eid in group.get("members", []):
            member_to_group[eid] = group_name

    # idea_key = (group_name, direction)  ->  per-paper contributions
    raw: dict[tuple[str, str], dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for c in claims:
        for pred in c.get("predictions", []) or []:
            value = float(pred["value"])
            direction = "positive" if value >= 0.5 else "negative"
            for eid in pred.get("evidence_ids") or []:
                group_name = member_to_group.get(eid)
                if group_name is None:
                    continue
                raw[(group_name, direction)][c["paper_id"]].append({
                    "claim_id": c["claim_id"],
                    "evidence_id": eid,
                    "value": round(value, 2),
                })

    ideas: list[dict] = []
    for (group_name, direction), per_paper in raw.items():
        group = comparability[group_name]
        # supporting evidence: where the predicted direction matches the actual measurement
        members = list(group.get("members", []))
        supporting, contesting = [], []
        for eid in members:
            ev = evidence_by_id.get(eid)
            if not ev:
                continue
            actual = float(ev["core"]["dimensions"][0]["value"])
            actual_dir = "positive" if actual >= 0.5 else "negative"
            touched = any(
                contrib["evidence_id"] == eid
                for contribs in per_paper.values()
                for contrib in contribs
            )
            if not touched:
                continue
            if actual_dir == direction:
                supporting.append(eid)
            else:
                contesting.append(eid)
        ideas.append({
            "group": group_name,
            "direction": direction,
            "title": _stance_title(group, direction),
            "papers": dict(per_paper),
            "supporting": sorted(set(supporting)),
            "contesting": sorted(set(contesting)),
        })
    ideas.sort(key=lambda i: (-len(i["papers"]), i["group"], i["direction"]))
    return ideas


def _stance_title(group: dict, direction: str) -> str:
    base = group.get("title", "Unnamed group")
    if direction == "positive":
        return f"{base} :: holds"
    return f"{base} :: does NOT hold"


# ---------------------------------------------------------------------------
# Mode F: subjects with nested assertions (two-layer)
# ---------------------------------------------------------------------------

def discover_subjects(
    claims: list[dict],
    comparability: dict[str, dict],
    evidence_by_id: dict[str, dict],
) -> list[dict]:
    """Each comparability group becomes one SUBJECT (the phenomenon).
    Within each subject, the positive- and negative-direction buckets
    become ASSERTIONS of the form "(scope) -> outcome." Tensions between
    assertions are surfaced when both directions exist, with overlapping
    scope keywords highlighted as the interrogation point.
    """
    buckets = group_value_buckets(claims, comparability, evidence_by_id)
    by_subject: dict[str, list[dict]] = defaultdict(list)
    for b in buckets:
        by_subject[b["group"]].append(b)

    claim_by_id = {c["claim_id"]: c for c in claims}
    subjects: list[dict] = []
    for group_name, group in comparability.items():
        if group_name not in by_subject:
            continue
        assertions: list[dict] = []
        for b in by_subject[group_name]:
            scope = _synthesize_scope(b["papers"], claim_by_id)
            value_values = sorted({c["value"] for contribs in b["papers"].values() for c in contribs})
            assertions.append({
                "direction": b["direction"],
                "outcome": _outcome_text(group, b["direction"]),
                "contributing": b["papers"],
                "scope": scope,
                "value_values": value_values,
                "supporting": b["supporting"],
                "contesting": b["contesting"],
                "paper_count": len(b["papers"]),
            })
        assertions.sort(key=lambda a: 0 if a["direction"] == "positive" else 1)

        tensions: list[dict] = []
        pos_asserts = [a for a in assertions if a["direction"] == "positive"]
        neg_asserts = [a for a in assertions if a["direction"] == "negative"]
        if pos_asserts and neg_asserts:
            pa, na = pos_asserts[0], neg_asserts[0]
            overlap_kw = sorted(set(pa["scope"]["keywords"]) & set(na["scope"]["keywords"]))
            overlap_papers = sorted(set(pa["contributing"]) & set(na["contributing"]))
            tensions.append({
                "papers_yes": sorted(pa["contributing"].keys()),
                "papers_no": sorted(na["contributing"].keys()),
                "shared_keywords": overlap_kw,
                "shared_papers": overlap_papers,
            })

        subjects.append({
            "subject_id": group_name,
            "title": group.get("title", group_name),
            "description": group.get("description", ""),
            "assertions": assertions,
            "tensions": tensions,
        })
    return subjects


def _synthesize_scope(
    papers_dict: dict[str, list[dict]],
    claim_by_id: dict[str, dict],
) -> dict:
    systems: set[str] = set()
    frameworks: set[str] = set()
    keywords: set[str] = set()
    for paper_id, contribs in papers_dict.items():
        for contrib in contribs:
            claim = claim_by_id.get(contrib["claim_id"])
            if not claim:
                continue
            home = claim.get("home_regime", {})
            if home.get("system"):
                systems.add(home["system"])
            if home.get("framework"):
                frameworks.add(home["framework"])
            for kw in home.get("regime_keywords", []):
                keywords.add(kw)
    return {
        "systems": sorted(systems),
        "frameworks": sorted(frameworks),
        "keywords": sorted(keywords),
    }


def _outcome_text(group: dict, direction: str) -> str:
    title = group.get("title", "")
    if direction == "positive":
        return f"{title}  --  HOLDS"
    return f"{title}  --  does NOT HOLD"


# ---------------------------------------------------------------------------
# maximal cliques (Bron-Kerbosch with pivoting)
# ---------------------------------------------------------------------------

def maximal_cliques(claim_ids: list[str], adj: dict[str, set[str]]) -> list[set[str]]:
    cliques: list[set[str]] = []

    def bk(R: set[str], P: set[str], X: set[str]) -> None:
        if not P and not X:
            cliques.append(set(R))
            return
        # pivot vertex chosen to maximize neighborhood overlap with P
        pivot = max(P | X, key=lambda v: len(adj[v] & P))
        for v in list(P - adj[pivot]):
            bk(R | {v}, P & adj[v], X & adj[v])
            P = P - {v}
            X = X | {v}

    bk(set(), set(claim_ids), set())
    return cliques


# ---------------------------------------------------------------------------
# idea synthesis
# ---------------------------------------------------------------------------

def union_stance(
    clique: set[str],
    stances: dict[str, dict],
) -> dict[tuple[str, str], float]:
    union: dict[tuple[str, str], float] = {}
    for cid in clique:
        for k, v in stances[cid].items():
            if k in union and abs(union[k] - v) >= AGREE_TOLERANCE:
                # conflict -- skip (clique guarantees this shouldn't happen)
                continue
            union[k] = v
    return union


def title_for_idea(
    clique: set[str],
    stance: dict[tuple[str, str], float],
    comparability: dict[str, dict],
) -> str:
    by_group: dict[str, dict[str, float]] = defaultdict(dict)
    for (g, eid), v in stance.items():
        by_group[g][eid] = v
    if not by_group:
        return f"(no comparability-group stance, {len(clique)} claims)"
    parts: list[str] = []
    for g, vals in sorted(by_group.items()):
        group_title = comparability.get(g, {}).get("title", g)
        unique = sorted(set(round(v, 2) for v in vals.values()))
        if len(unique) == 1:
            parts.append(f"{group_title} = {unique[0]}")
        else:
            parts.append(f"{group_title} = mixed{unique}")
    return " | ".join(parts)


def scope_keywords(
    clique: set[str], claim_by_id: dict[str, dict]
) -> list[str]:
    kws: set[str] = set()
    for cid in clique:
        for kw in claim_by_id[cid].get("home_regime", {}).get("regime_keywords", []):
            kws.add(kw)
    return sorted(kws)


# ---------------------------------------------------------------------------
# residual check (which claims have their stance contradicted by evidence)
# ---------------------------------------------------------------------------

def residual_on_idea(
    stance: dict[tuple[str, str], float],
    evidence_by_id: dict[str, dict],
) -> tuple[list[str], list[str]]:
    """Return (supporting, contesting) evidence_ids based on the idea's
    stance vs. actual evidence values."""
    supporting, contesting = [], []
    for (group, eid), predicted in stance.items():
        ev = evidence_by_id.get(eid)
        if not ev:
            continue
        actual = float(ev["core"]["dimensions"][0]["value"])
        if abs(predicted - actual) < AGREE_TOLERANCE:
            supporting.append(eid)
        else:
            contesting.append(eid)
    return sorted(set(supporting)), sorted(set(contesting))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def discover(map_dir: Path, corpus_dir: Path) -> dict:
    claims, evidence, sheaf = load_run(map_dir)
    comparability = load_comparability(corpus_dir)
    ev_by_id = {e["evidence_id"]: e for e in evidence}
    claim_by_id = {c["claim_id"]: c for c in claims}

    stances: dict[str, dict] = {}
    for c in claims:
        s = build_stance(c, comparability, ev_by_id)
        if s:
            stances[c["claim_id"]] = s

    claim_ids = sorted(stances.keys())
    adj: dict[str, set[str]] = {cid: set() for cid in claim_ids}
    for i, c1 in enumerate(claim_ids):
        for c2 in claim_ids[i + 1:]:
            if coheres(stances[c1], stances[c2]):
                adj[c1].add(c2)
                adj[c2].add(c1)

    cliques = maximal_cliques(claim_ids, adj)
    cliques.sort(key=lambda c: (-len(c), sorted(c)))

    equiv_buckets = equivalence_partition(stances)
    equiv_buckets.sort(key=lambda c: (-len(c), sorted(c)))

    # Paper-level discovery
    p_stances, p_claims = paper_stances(claims, comparability, ev_by_id)
    paper_ids = sorted(p_stances.keys())
    p_adj: dict[str, set[str]] = {p: set() for p in paper_ids}
    for i, p1 in enumerate(paper_ids):
        for p2 in paper_ids[i + 1:]:
            if coheres(p_stances[p1], p_stances[p2]):
                p_adj[p1].add(p2)
                p_adj[p2].add(p1)
    p_cliques = maximal_cliques(paper_ids, p_adj)
    p_cliques.sort(key=lambda c: (-len(c), sorted(c)))
    p_equiv = equivalence_partition(p_stances)
    p_equiv.sort(key=lambda c: (-len(c), sorted(c)))

    # Group-value bucket discovery (Mode E)
    group_value_ideas = group_value_buckets(claims, comparability, ev_by_id)
    # Two-layer subjects + assertions (Mode F)
    subjects = discover_subjects(claims, comparability, ev_by_id)

    no_stance = sorted(c["claim_id"] for c in claims if c["claim_id"] not in stances)

    return {
        "comparability_groups": list(comparability.keys()),
        "claims_with_stance": len(stances),
        "claims_without_stance": no_stance,
        "cliques": cliques,
        "equiv_buckets": equiv_buckets,
        "paper_cliques": p_cliques,
        "paper_equiv": p_equiv,
        "paper_stances": p_stances,
        "paper_claims": p_claims,
        "group_value_ideas": group_value_ideas,
        "subjects": subjects,
        "stances": stances,
        "claim_by_id": claim_by_id,
        "evidence_by_id": ev_by_id,
        "comparability": comparability,
    }


def _format_ideas(L, label, buckets, out):
    L.append("=" * 74)
    L.append(label)
    L.append("=" * 74)
    L.append(f"  ideas discovered: {len(buckets)}")
    L.append("")
    for idx, bucket in enumerate(buckets, 1):
        stance = union_stance(bucket, out["stances"])
        title = title_for_idea(bucket, stance, out["comparability"])
        kws = scope_keywords(bucket, out["claim_by_id"])
        supporting, contesting = residual_on_idea(stance, out["evidence_by_id"])
        L.append(f"-- Idea {idx} ({len(bucket)} claim(s)) --")
        L.append(f"   contributors:  {', '.join(sorted(bucket))}")
        L.append(f"   stance:        {title}")
        if kws:
            L.append(f"   scope kw:      {', '.join(kws[:10])}")
        if contesting:
            L.append(f"   contesting:    {', '.join(contesting)}  <- structural tension")
        L.append("")


def _format_paper_ideas(L, label, buckets, out):
    L.append("=" * 74)
    L.append(label)
    L.append("=" * 74)
    L.append(f"  ideas discovered: {len(buckets)}  (over {len(out['paper_stances'])} papers)")
    L.append("")
    for idx, bucket in enumerate(buckets, 1):
        # build union stance from paper-level stances
        union: dict[tuple[str, str], float] = {}
        for pid in bucket:
            for k, v in out["paper_stances"][pid].items():
                if k in union and abs(union[k] - v) >= AGREE_TOLERANCE:
                    continue
                union[k] = v
        title = title_for_idea(set(bucket), union, out["comparability"])
        supporting, contesting = residual_on_idea(union, out["evidence_by_id"])
        L.append(f"-- Idea {idx} ({len(bucket)} paper(s)) --")
        papers = sorted(bucket)
        L.append(f"   papers:        {', '.join(papers)}")
        # also list contributing claims by paper
        for pid in papers:
            cls = out["paper_claims"].get(pid, [])
            L.append(f"     {pid}: {', '.join(cls)}")
        L.append(f"   stance:        {title}")
        if contesting:
            L.append(f"   contesting:    {', '.join(contesting)}  <- structural tension")
        L.append("")


def _format_group_value_ideas(L, out):
    L.append("=" * 74)
    L.append("MODE E: (group, direction) buckets  (each idea = one assertion, "
             "papers contribute via explicit predictions)")
    L.append("=" * 74)
    L.append(f"  ideas discovered: {len(out['group_value_ideas'])}")
    L.append("")
    for idx, idea in enumerate(out["group_value_ideas"], 1):
        papers = idea["papers"]
        L.append(f"-- Idea {idx} ({len(papers)} paper(s)) --")
        L.append(f"   title:         {idea['title']}")
        L.append(f"   contributing:")
        for paper_id, contribs in sorted(papers.items()):
            evidence_seen = sorted(set(c["evidence_id"] for c in contribs))
            claims_seen = sorted(set(c["claim_id"] for c in contribs))
            L.append(f"     {paper_id:18s}  via {', '.join(claims_seen)}  "
                     f"at {', '.join(evidence_seen)}")
        if idea["supporting"]:
            L.append(f"   supporting:    {', '.join(idea['supporting'])}")
        if idea["contesting"]:
            L.append(f"   contesting:    {', '.join(idea['contesting'])}  "
                     f"<- evidence DISAGREES with this direction")
        L.append("")
    # tensions between ideas
    L.append("-- tensions between ideas (same group, opposite direction) --")
    pos = {i["group"]: i for i in out["group_value_ideas"] if i["direction"] == "positive"}
    neg = {i["group"]: i for i in out["group_value_ideas"] if i["direction"] == "negative"}
    for g in sorted(pos.keys() & neg.keys()):
        L.append(f"   {g}: "
                 f"{len(pos[g]['papers'])} paper(s) say YES  vs  "
                 f"{len(neg[g]['papers'])} paper(s) say NO")
    L.append("")


def _format_subjects(L, subjects):
    L.append("=" * 74)
    L.append("MODE F: SUBJECTS & ASSERTIONS (two-layer)")
    L.append("  subject = phenomenon (one per comparability group)")
    L.append("  assertion = (scope -> outcome) within a subject")
    L.append("=" * 74)
    L.append(f"  subjects: {len(subjects)}")
    L.append("")
    for idx, subj in enumerate(subjects, 1):
        L.append(f"## Subject {idx}: {subj['title']}")
        L.append(f"   {subj['description'][:120]}")
        L.append("")
        for j, a in enumerate(subj["assertions"], 1):
            L.append(f"   [Assertion {j}]  {a['outcome']}")
            L.append(f"     contributors ({a['paper_count']} paper(s)):")
            for paper_id, contribs in sorted(a["contributing"].items()):
                claims_seen = sorted(set(c["claim_id"] for c in contribs))
                L.append(f"       {paper_id:18s}  via {', '.join(claims_seen)}")
            scope = a["scope"]
            if scope["systems"]:
                L.append(f"     scope.systems:    {' | '.join(scope['systems'])}")
            if scope["frameworks"]:
                L.append(f"     scope.frameworks: {' | '.join(scope['frameworks'])}")
            if scope["keywords"]:
                L.append(f"     scope.keywords:   {', '.join(scope['keywords'])}")
            if a["value_values"] and a["value_values"] != [1.0] and a["value_values"] != [0.0]:
                L.append(f"     value range:      {a['value_values']}")
            if a["supporting"]:
                L.append(f"     supporting ev:    {', '.join(a['supporting'])}")
            if a["contesting"]:
                L.append(f"     contesting ev:    {', '.join(a['contesting'])}")
            L.append("")
        for t in subj["tensions"]:
            L.append(f"   --> TENSION within this subject:")
            L.append(f"       {len(t['papers_yes'])} paper(s) say HOLDS:  "
                     f"{', '.join(t['papers_yes'])}")
            L.append(f"       {len(t['papers_no'])} paper(s) say DOES NOT HOLD:  "
                     f"{', '.join(t['papers_no'])}")
            if t["shared_papers"]:
                L.append(f"       multi-membership (papers in BOTH directions): "
                         f"{', '.join(t['shared_papers'])}  "
                         f"<- their scoped claims are where the field could resolve the split")
            if t["shared_keywords"]:
                L.append(f"       scope overlap (shared regime keywords): "
                         f"{', '.join(t['shared_keywords'])}  "
                         f"<- the interrogation question lives here")
            L.append("")


def report(out: dict) -> str:
    L: list[str] = []
    L.append(f"comparability groups in registry: {len(out['comparability_groups'])}")
    L.append(f"claims with stance: {out['claims_with_stance']}  /  "
             f"no stance: {len(out['claims_without_stance'])}")
    L.append(f"papers with stance: {len(out['paper_stances'])}")
    L.append("")
    _format_subjects(L, out["subjects"])
    _format_group_value_ideas(L, out)
    _format_ideas(L,
                  f"MODE A: claim-level CLIQUES  (>={MIN_SHARED_POSITIONS} shared positions)",
                  out["cliques"], out)
    _format_ideas(L,
                  "MODE B: claim-level EQUIVALENCE  (identical stance vectors)",
                  out["equiv_buckets"], out)
    _format_paper_ideas(L,
                        f"MODE C: paper-level CLIQUES",
                        out["paper_cliques"], out)
    _format_paper_ideas(L,
                        "MODE D: paper-level EQUIVALENCE",
                        out["paper_equiv"], out)
    if out["claims_without_stance"]:
        L.append(f"Claims with no comparability-group stance "
                 f"({len(out['claims_without_stance'])}): "
                 f"{', '.join(out['claims_without_stance'])}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", type=Path, required=True,
                    help="run dir (e.g. corpora/atlas/v05)")
    ap.add_argument("--corpus", type=Path, required=True,
                    help="corpus dir containing comparability.json")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    out = discover(args.map, args.corpus)
    if args.json:
        # strip non-serializable bits
        payload = {
            "comparability_groups": out["comparability_groups"],
            "claims_with_stance": out["claims_with_stance"],
            "claims_without_stance": out["claims_without_stance"],
            "cliques": [sorted(c) for c in out["cliques"]],
        }
        print(json.dumps(payload, indent=2))
    else:
        print(report(out))


if __name__ == "__main__":
    main()
