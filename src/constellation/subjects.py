"""Subjects + nested ideas: the two-layer consolidation.

A SUBJECT is a phenomenon the field is collectively investigating --
one per comparability group. It is the OBSERVABLE axis.

An IDEA is one paper's (or claim cluster's) coherent stance within a
subject -- the predicted value at every group-member evidence node the
contributor explicitly addresses. Ideas are paper-shaped because each
paper's claims tell us what size the unit of contribution is.

Within a subject, ideas relate to each other via:
  - CONTESTS: two ideas have explicit predictions on the same evidence
    with incompatible values. The map's structural tension surface.
  - SUPPORTS: ideas agree on every shared position (mutual corroboration).

Each idea carries a LIFECYCLE STATUS:
  - established: backed by 2+ independent contributors, OR a single
    contributor with no contests (foundation results stay established).
  - contested: at least one contests link to another idea.
  - novel: only contributor is the incoming paper (situate operation)
    and the idea has no other support yet.

Novel ideas get next-step suggestions so the LLM has concrete moves
to propose: cross-paper replication, boundary probing, parameter
sensitivity. Contested ideas surface which other idea(s) they
contradict and where the disagreement lives.

This is the ε-machine causal-state view of the constellation: each idea
is a candidate state in the field's reconstruction; established states
have been ratified; contested states have a candidate split or merge
that the algorithm hasn't decided yet; novel states are proposals that
need more independent observations before refinement.
"""
from __future__ import annotations

from collections import defaultdict

from .util import Json


AGREE_TOLERANCE = 0.05


def discover_subjects(
    claims: list[Json],
    evidence: list[Json],
    comparability: dict[str, Json],
    incoming_paper_ids: set[str] | None = None,
) -> list[Json]:
    """Two-layer consolidation. One subject per comparability group;
    each subject contains a list of ideas (paper-shaped contributions)
    with contests/supports relations and lifecycle status."""
    incoming = set(incoming_paper_ids or [])
    evidence_by_id = {ev["evidence_id"]: ev for ev in evidence}
    claim_by_id = {c["claim_id"]: c for c in claims}

    subjects: list[Json] = []
    covered_evidence: set[str] = set()
    for idx, (group_name, group) in enumerate(sorted(comparability.items()), 1):
        members = list(group.get("members", []))
        present_members = [m for m in members if m in evidence_by_id]
        if not present_members:
            continue

        ideas = _build_ideas(claims, claim_by_id, group_name, group, present_members, evidence_by_id, incoming)
        _annotate_relations(ideas)
        _annotate_status(ideas, incoming)
        _annotate_next_steps(ideas, group)

        # Sort ideas: novel first, then contested, then established
        order = {"novel": 0, "contested": 1, "established": 2}
        ideas.sort(key=lambda i: (order.get(i["status"], 9), i["idea_id"]))

        subj_claims = sorted({cid for i in ideas for cid in i["contributing_claims"]})
        subj_evidence = sorted({eid for i in ideas for eid in i["stance"]})
        subj_papers = sorted({i["contributing_papers"][0] for i in ideas})
        covered_evidence.update(subj_evidence)

        subjects.append({
            "idea_id": f"subject_{idx:02d}_{group_name}",
            "group_id": group_name,
            "title": group.get("title") or group_name,
            "description": group.get("description", ""),
            "ideas": ideas,
            "tensions": _detect_tensions(ideas),
            "contributing_claims": subj_claims,
            "contributing_evidence": subj_evidence,
            "contributing_papers": subj_papers,
            # legacy / vis fields
            "scope": _subject_level_scope(ideas),
            "remaining_tensions": [],
            "tensions_resolved": [],
            "open_questions": _legacy_open_questions(ideas, group),
            "provenance": {
                "consolidator": "subjects_with_lifecycle_ideas",
                "group": group_name,
            },
        })

    # Ungrouped catch-all -- evidence AND claims that no comparability
    # group covers. Including orphan claims here matters for the HTML
    # layout: every node needs a position, and the layout assigns
    # positions via subject membership.
    covered_claims_global: set[str] = set()
    for s in subjects:
        covered_claims_global.update(s["contributing_claims"])
    ungrouped_evidence = sorted(eid for eid in evidence_by_id if eid not in covered_evidence)
    ungrouped_claims = sorted(cid for cid in claim_by_id if cid not in covered_claims_global)
    if ungrouped_evidence or ungrouped_claims:
        subjects.append({
            "idea_id": f"subject_{len(subjects)+1:02d}_ungrouped",
            "group_id": "ungrouped",
            "title": "Ungrouped (no comparability group authored yet)",
            "description": (
                "Claims and evidence not covered by any comparability group. "
                "Add a group to the corpus's comparability.json to surface "
                "these as a first-class subject."
            ),
            "ideas": [],
            "tensions": [],
            "contributing_claims": ungrouped_claims,
            "contributing_evidence": ungrouped_evidence,
            "contributing_papers": sorted({
                claim_by_id[cid]["paper_id"]
                for cid in ungrouped_claims if cid in claim_by_id
            }),
            "scope": {"system": "", "framework": "", "regime": "ungrouped"},
            "remaining_tensions": [],
            "tensions_resolved": [],
            "open_questions": [],
            "provenance": {
                "consolidator": "subjects_with_lifecycle_ideas",
                "group": "ungrouped",
            },
        })
    return subjects


# ---------------------------------------------------------------------------
# idea construction
# ---------------------------------------------------------------------------

def _build_ideas(
    claims: list[Json],
    claim_by_id: dict[str, Json],
    group_name: str,
    group: Json,
    present_members: list[str],
    evidence_by_id: dict[str, Json],
    incoming: set[str],
) -> list[Json]:
    """One candidate idea per (paper, claim) whose claim has explicit
    predictions in the group. Within the same paper, merge candidates
    with identical stance vectors so A_01/A_04/A_06/A_07 (which share
    the implicit-headline stance) collapse into one idea."""
    member_set = set(present_members)
    candidates_by_paper: dict[str, list[dict]] = defaultdict(list)
    for c in claims:
        stance: dict[str, float] = {}
        for pred in c.get("predictions", []) or []:
            for eid in pred.get("evidence_ids") or []:
                if eid in member_set:
                    stance[eid] = float(pred["value"])
        if not stance:
            continue
        candidates_by_paper[c["paper_id"]].append({
            "claim_id": c["claim_id"],
            "stance": stance,
        })

    ideas: list[Json] = []
    counter = 0
    for paper_id, cands in candidates_by_paper.items():
        # Merge candidates with identical stance vectors within the paper.
        by_stance: dict[tuple, list[str]] = defaultdict(list)
        for cand in cands:
            sig = tuple(sorted((k, round(v, 2)) for k, v in cand["stance"].items()))
            by_stance[sig].append(cand["claim_id"])

        for sig, claim_ids in by_stance.items():
            counter += 1
            stance = dict(sig)
            scope = _synthesize_scope(claim_ids, claim_by_id)
            supporting, contesting = _score_against_evidence(stance, evidence_by_id)
            ideas.append({
                "idea_id": f"idea_{group_name}_{counter:03d}",
                "title": _idea_title(paper_id, claim_ids, claim_by_id, stance),
                "status": None,
                "contributing_papers": [paper_id],
                "contributing_claims": sorted(claim_ids),
                "stance": {k: float(v) for k, v in stance.items()},
                "scope": scope,
                "supporting_evidence": supporting,
                "contesting_evidence": contesting,
                "contests": [],
                "supports": [],
                "next_steps": [],
            })
    return ideas


def _score_against_evidence(
    stance: dict[str, float],
    evidence_by_id: dict[str, Json],
) -> tuple[list[str], list[str]]:
    """Split the stance's evidence into supporting (prediction matches
    measurement) and contesting (prediction differs from measurement)."""
    supporting, contesting = [], []
    for eid, predicted in stance.items():
        ev = evidence_by_id.get(eid)
        if not ev:
            continue
        actual = float(ev["core"]["dimensions"][0]["value"])
        if abs(float(predicted) - actual) < AGREE_TOLERANCE:
            supporting.append(eid)
        else:
            contesting.append(eid)
    return sorted(set(supporting)), sorted(set(contesting))


def _idea_title(
    paper_id: str,
    claim_ids: list[str],
    claim_by_id: dict[str, Json],
    stance: dict[str, float],
) -> str:
    # Use the first contributing claim's label in full -- the HTML
    # callouts wrap and scroll, so no need to truncate here.
    if claim_ids:
        c = claim_by_id.get(claim_ids[0])
        if c and c.get("label"):
            return f"{paper_id} ({', '.join(sorted(claim_ids))}): {c['label']}"
    return f"{paper_id} ({', '.join(sorted(claim_ids))})"


def _synthesize_scope(
    claim_ids: list[str],
    claim_by_id: dict[str, Json],
) -> Json:
    systems: set[str] = set()
    frameworks: set[str] = set()
    keywords: set[str] = set()
    for cid in claim_ids:
        claim = claim_by_id.get(cid)
        if not claim:
            continue
        home = claim.get("home_regime", {}) or {}
        if home.get("system"):
            systems.add(home["system"])
        if home.get("framework"):
            frameworks.add(home["framework"])
        for kw in home.get("regime_keywords", []) or []:
            keywords.add(kw)
    return {
        "systems": sorted(systems),
        "frameworks": sorted(frameworks),
        "keywords": sorted(keywords),
    }


# ---------------------------------------------------------------------------
# idea-pair relations
# ---------------------------------------------------------------------------

def _annotate_relations(ideas: list[Json]) -> None:
    """For every pair of ideas in the subject, compute contests and
    supports relations by comparing their stance vectors at shared
    positions."""
    for i, a in enumerate(ideas):
        for b in ideas[i + 1:]:
            shared = set(a["stance"]) & set(b["stance"])
            if not shared:
                continue
            agree_at = sorted(
                eid for eid in shared
                if abs(a["stance"][eid] - b["stance"][eid]) < AGREE_TOLERANCE
            )
            contest_at = sorted(
                eid for eid in shared
                if abs(a["stance"][eid] - b["stance"][eid]) >= AGREE_TOLERANCE
            )
            if contest_at:
                a["contests"].append({
                    "idea_id": b["idea_id"],
                    "title": b["title"],
                    "papers": list(b["contributing_papers"]),
                    "at": contest_at,
                })
                b["contests"].append({
                    "idea_id": a["idea_id"],
                    "title": a["title"],
                    "papers": list(a["contributing_papers"]),
                    "at": contest_at,
                })
            elif agree_at:
                a["supports"].append({
                    "idea_id": b["idea_id"],
                    "title": b["title"],
                    "papers": list(b["contributing_papers"]),
                    "at": agree_at,
                })
                b["supports"].append({
                    "idea_id": a["idea_id"],
                    "title": a["title"],
                    "papers": list(a["contributing_papers"]),
                    "at": agree_at,
                })


# ---------------------------------------------------------------------------
# lifecycle status
# ---------------------------------------------------------------------------

def _annotate_status(ideas: list[Json], incoming: set[str]) -> None:
    """Assign one of {novel, contested, established} to each idea.

      novel       -- contributor is in incoming_paper_ids AND no other
                     paper makes the same stance (the contributor is
                     proposing a genuinely new causal state).
      contested   -- has at least one contests link.
      established -- everything else (foundational or replicated, with
                     no live disputes).

    Novel and contested can both be true in practice (Atlas's scoped
    A_05 idea is novel AND disagrees with priors at ev_atlas_kink_zero).
    The rule below prioritizes ``novel`` because that's the action item
    -- the newcomer that needs verification or scope refinement. The
    contests links are still populated and rendered alongside.
    """
    signatures: dict[tuple, list[str]] = defaultdict(list)
    for idea in ideas:
        sig = tuple(sorted((k, round(float(v), 2)) for k, v in idea["stance"].items()))
        signatures[sig].append(idea["idea_id"])

    for idea in ideas:
        paper = idea["contributing_papers"][0]
        sig = tuple(sorted((k, round(float(v), 2)) for k, v in idea["stance"].items()))
        is_unique = len(signatures[sig]) == 1
        is_incoming = paper in incoming
        has_contests = bool(idea["contests"])
        if is_incoming and is_unique:
            idea["status"] = "novel"
        elif has_contests:
            idea["status"] = "contested"
        else:
            idea["status"] = "established"


# ---------------------------------------------------------------------------
# next-step suggestions
# ---------------------------------------------------------------------------

def _annotate_next_steps(ideas: list[Json], group: Json) -> None:
    """Every idea gets next-step suggestions, tailored to its lifecycle
    state. Even established consensus ideas attract proposals -- the
    field could always be tested in a new regime, and recording these
    moves makes the map a forward-looking research surface, not a
    finished snapshot."""
    for idea in ideas:
        status = idea.get("status", "established")
        if status == "novel":
            idea["next_steps"] = _novel_next_steps(idea, group)
        elif status == "contested":
            idea["next_steps"] = _contested_next_steps(idea, group)
        else:
            idea["next_steps"] = _established_next_steps(idea, group)


def _contested_next_steps(idea: Json, group: Json) -> list[Json]:
    """For a contested idea: identify the scope-flipping parameter, then
    propose a controlled experiment in the scope overlap."""
    contested_ids = [c["title"] for c in idea.get("contests", [])]
    title = group.get("title", "this subject")
    contesting_clause = (
        f" against {len(contested_ids)} contesting idea(s)"
        if contested_ids else ""
    )
    return [
        {
            "kind": "theory",
            "title": "Identify the scope-flipping parameter",
            "description": (
                f"Compare this idea's home scope{contesting_clause} and isolate "
                "the parameter(s) whose value separates the outcomes. The "
                "interrogation question for {title} lives here.".replace(
                    "{title}", title
                )
            ),
        },
        {
            "kind": "simulation",
            "title": "Controlled scope-overlap sweep",
            "description": (
                "Run a parameter sweep that crosses from this idea's regime "
                "into the contesting idea's regime, holding everything else "
                "constant, and identify the transition point where the "
                "outcome flips."
            ),
        },
        {
            "kind": "literature",
            "title": "Audit the contesting idea's assumptions",
            "description": (
                "For each contesting idea, identify which structural "
                "assumption it makes that this idea does not (or vice "
                "versa). Decide whether the disagreement is a genuine "
                "physical split or a scope-labelling artifact."
            ),
        },
    ]


def _established_next_steps(idea: Json, group: Json) -> list[Json]:
    """For an established idea: propose moves that could either reinforce
    it (replication, new regime) or force a rewrite (counter-experiment).
    Even consensus is a working hypothesis; the next-steps make that
    explicit."""
    title = group.get("title", "this subject")
    return [
        {
            "kind": "experiment",
            "title": "Counter-experiment proposal",
            "description": (
                f"Identify a measurement that, if it landed at a value "
                f"contrary to this idea's prediction within {title}, would "
                "force a rewrite. Document what such a measurement would "
                "look like and which device could perform it."
            ),
        },
        {
            "kind": "theory",
            "title": "Foundational assumption review",
            "description": (
                "Walk the chain of assumptions that this idea rests on. "
                "Mark any that have NOT been directly tested in their own "
                "right -- those are the soft spots where a future "
                "counter-experiment could surface."
            ),
        },
        {
            "kind": "simulation",
            "title": "Adjacent-regime extrapolation",
            "description": (
                "Sweep into the boundary of this idea's claimed scope and "
                "report where its predictions become unreliable. The result "
                "is a refined scope description; it may also surface a new "
                "candidate subject the registry does not yet cover."
            ),
        },
    ]


def _novel_next_steps(idea: Json, group: Json) -> list[Json]:
    """A small catalog of generic moves a novel idea should attract.
    Each is concrete enough to act on; the LLM specializes them with
    paper context at runtime."""
    title = group.get("title", "this subject")
    steps: list[Json] = []
    contested_titles = [c["title"] for c in idea.get("contests", [])]
    if contested_titles:
        steps.append({
            "kind": "literature",
            "title": "Reconcile with contested ideas",
            "description": (
                "This novel idea contradicts " + str(len(contested_titles)) +
                " existing idea(s) at shared evidence. Identify the "
                "parameter that separates the contesting scopes (e.g., "
                "in the m=1 case, what about Atlas's H1-H5 regime is "
                "structurally different from prior rotating-Z-pinch setups?)."
            ),
        })
    steps.append({
        "kind": "experiment",
        "title": "Independent replication",
        "description": (
            f"Ask a different group to reproduce the supporting "
            f"measurement(s) inside {title} using their own pipeline. "
            "The map will record the new contributor as independent "
            "evidence and promote this idea toward established."
        ),
    })
    steps.append({
        "kind": "simulation",
        "title": "Probe the scope boundary",
        "description": (
            "Sweep the parameters at the edge of the claimed scope and "
            "look for the threshold where the predicted outcome flips. "
            "This either ratifies a new causal state or absorbs this "
            "idea into an existing one."
        ),
    })
    return steps


# ---------------------------------------------------------------------------
# subject-level helpers
# ---------------------------------------------------------------------------

def _detect_tensions(ideas: list[Json]) -> list[Json]:
    """Subject-level summary of contests: list the idea-pairs in
    disagreement so the report can show them prominently."""
    seen: set[frozenset[str]] = set()
    tensions: list[Json] = []
    for a in ideas:
        for c in a.get("contests", []):
            pair = frozenset({a["idea_id"], c["idea_id"]})
            if pair in seen:
                continue
            seen.add(pair)
            tensions.append({
                "between": sorted(pair),
                "papers_yes": a["contributing_papers"],
                "papers_no": c["papers"],
                "at_evidence": c["at"],
                "shared_keywords": [],  # backwards-compat field for report
                "shared_papers": [],
            })
    return tensions


def _subject_level_scope(ideas: list[Json]) -> Json:
    systems: set[str] = set()
    frameworks: set[str] = set()
    keywords: set[str] = set()
    for i in ideas:
        scope = i.get("scope") or {}
        systems.update(scope.get("systems") or [])
        frameworks.update(scope.get("frameworks") or [])
        keywords.update(scope.get("keywords") or [])
    return {
        "system": "; ".join(sorted(systems)),
        "framework": "; ".join(sorted(frameworks)),
        "regime": ", ".join(sorted(keywords)),
    }


def _legacy_open_questions(ideas: list[Json], group: Json) -> list[Json]:
    """Every subject gets at least one open question, regardless of its
    lifecycle composition. Subjects in full consensus still attract
    counter-experiment proposals; subjects with novel or contested
    ideas additionally surface those as priority questions."""
    questions: list[Json] = []
    novel = [i for i in ideas if i["status"] == "novel"]
    contested = [i for i in ideas if i["status"] == "contested"]
    title = group.get("title", "this subject")

    if novel:
        questions.append({
            "question": (
                f"{len(novel)} novel idea(s) in this subject need independent "
                "backing or refinement to ratify."
            ),
            "priority": "blocking",
            "suggested_next_steps": [
                {
                    "kind": "audit",
                    "title": "Novel-idea review",
                    "description": (
                        "Examine each novel idea's predicted scope and decide "
                        "whether to commission a replication, a boundary probe, "
                        "or a refinement that folds it into an established idea."
                    ),
                },
            ],
        })

    if contested:
        questions.append({
            "question": (
                f"{len(contested)} contested idea(s) in this subject. "
                "Which parameter(s) at the scope boundary actually flip the outcome?"
            ),
            "priority": "high",
            "suggested_next_steps": [
                {
                    "kind": "theory",
                    "title": "Scope-boundary interrogation",
                    "description": (
                        "Identify the specific physical parameters that separate "
                        "contesting ideas and isolate the dimension(s) of disagreement."
                    ),
                },
            ],
        })

    # Always-on prompt: every subject deserves a counter-experiment proposal,
    # even those in full consensus. This keeps the map a forward-looking
    # research surface rather than a snapshot of settled knowledge.
    if ideas:
        questions.append({
            "question": (
                f"What experiment or derivation, if it landed at a contrary "
                f"value, would force a rewrite within {title}?"
            ),
            "priority": "exploratory",
            "suggested_next_steps": [
                {
                    "kind": "experiment",
                    "title": "Counter-experiment proposal",
                    "description": (
                        f"Identify a measurement that, if it landed at a value "
                        f"contrary to the field's consensus inside {title}, "
                        "would force a rewrite. Document the device that could "
                        "perform it and the parameter range it should sweep."
                    ),
                },
                {
                    "kind": "literature",
                    "title": "Adjacent-regime survey",
                    "description": (
                        "Identify regimes adjacent to the scope this subject "
                        "covers where the field has NOT yet looked. Each is a "
                        "candidate next step that could either extend the "
                        "subject or split off a new one."
                    ),
                },
                {
                    "kind": "audit",
                    "title": "Foundational assumption audit",
                    "description": (
                        "Walk the chain of structural assumptions every "
                        "established idea in this subject shares. Any "
                        "assumption that hasn't been directly tested is a "
                        "soft spot where future work could surface."
                    ),
                },
            ],
        })

    return questions
