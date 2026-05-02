"""Stage 8: consolidate into Ideas (ε-machine partition).

Input:  run.sheaf_path  (with map_section + frustration; full pipeline through stage 7)
        run.claims_dir
        run.tags_path
Output: run.ideas_dir/<idea_id>.json   (one per ε-state, validates against idea_schema)

LLM proposes the partition + transitions + open questions. Code fills in the
deterministic pieces:
  - idea_id from the slug of the label
  - consensus block (n_papers, mean_credibility, agreement_score, rewrite stats)
  - intra-Idea frustration (Penrose triangles + residual negative edges within the Idea)
  - transitions_in (inverted from transitions_out)
  - sheaf_ref (back-pointer)
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import UTC, datetime

from rich.console import Console

from ..llm import LLM, parse_json_response
from ..paths import Corpus, Run
from ..prompt_loader import load_prompt
from ..schemas import validate_idea

console = Console()

MAX_RETRIES = 1
SLUG_MAX_LEN = 40


# ---------- helpers ----------------------------------------------------------


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9 ]+", "", text.lower())
    s = re.sub(r"\s+", "_", s.strip())
    return s[:SLUG_MAX_LEN].rstrip("_")


def _idea_filename(idea_id: str) -> str:
    """Replace `/` with `_` so the id is filesystem-safe."""
    return idea_id.replace("/", "_") + ".json"


def _selected_pair_score(rm: dict, va: str, vb: str) -> dict:
    """Look up the compatibility_scores entry for the (va, vb) pair on this edge."""
    for s in rm["compatibility_scores"]:
        if s["variant_a_id"] == va and s["variant_b_id"] == vb:
            return s
    raise KeyError(f"no score for ({va}, {vb}) on {rm['edge_id']}")


def _build_payload(sheaf: dict, claim_by_id: dict, tags: dict) -> dict:
    """Compose the JSON the LLM will read in the user message."""
    selected = sheaf["map_section"]["selected"]

    selected_claims = []
    for cid, vid in selected.items():
        claim = claim_by_id[cid]
        variant = next(
            v for v in sheaf["stalks"][cid]["variants"] if v["variant_id"] == vid
        )
        selected_claims.append(
            {
                "claim_id": cid,
                "paper_id": claim["paper_id"],
                "selected_variant_id": vid,
                "variant_text": variant["text"],
                "rewrite_distance": variant["rewrite_distance"],
                "credibility": claim.get("credibility_score"),
                "scope_evidenced": claim.get("scope", {}).get("evidenced"),
                "tags": tags.get(cid, {}),
            }
        )

    selected_edges = []
    for rm in sheaf["restriction_maps"]:
        va = selected[rm["claim_a"]]
        vb = selected[rm["claim_b"]]
        s = _selected_pair_score(rm, va, vb)
        selected_edges.append(
            {
                "edge_id": rm["edge_id"],
                "claim_a": rm["claim_a"],
                "claim_b": rm["claim_b"],
                "selected_score": s["score"],
                "kind": s["kind"],
                "explanation": s["explanation"],
            }
        )

    return {
        "selected_claims": selected_claims,
        "selected_restriction_edges": selected_edges,
        "residual_h1": sheaf["map_section"].get("residual_h1", []),
        "frustration": sheaf.get("frustration", {}),
    }


# ---------- LLM call --------------------------------------------------------


def _propose_partition(llm: LLM, payload: dict) -> list[dict]:
    """One LLM call (with retry) returning the list of proposed Ideas."""
    system = load_prompt("s8_consolidate")
    user_text = (
        "Partition the corpus's MAP-selected claims into Ideas. "
        "Return ONLY the JSON object specified by the system prompt.\n\n"
        "```json\n"
        + json.dumps(payload, indent=2, default=str)
        + "\n```"
    )
    messages = [{"role": "user", "content": [{"type": "text", "text": user_text}]}]

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            text = llm.chat(system=system, messages=messages, max_tokens=16384)
            parsed = parse_json_response(text)
            if not isinstance(parsed, dict) or "ideas" not in parsed:
                raise ValueError("response must be {'ideas': [...]}")
            ideas = parsed["ideas"]
            if not isinstance(ideas, list) or not ideas:
                raise ValueError("'ideas' must be a non-empty list")
            return ideas
        except (ValueError, json.JSONDecodeError) as e:
            last_error = e
            if attempt == MAX_RETRIES:
                break
            messages = [
                *messages,
                {"role": "assistant", "content": [{"type": "text", "text": text}]},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Your previous output failed validation:\n\n{e}\n\n"
                                "Re-emit the corrected JSON object."
                            ),
                        }
                    ],
                },
            ]
    raise RuntimeError(f"partition proposal failed: {last_error}")


# ---------- per-Idea computed blocks ----------------------------------------


def _compute_consensus(
    contributing: list[dict], selected_edges: list[dict]
) -> dict:
    paper_ids = {c["paper_id"] for c in contributing}
    n_rewritten = sum(
        1 for c in contributing if not c["selected_variant_id"].endswith("#original")
    )
    total_rewrite_cost = sum(c["rewrite_distance"] for c in contributing)
    creds = [c["credibility"] for c in contributing if c.get("credibility") is not None]
    mean_cred = sum(creds) / len(creds) if creds else 0.0

    contributing_ids = {c["claim_id"] for c in contributing}
    intra_scores = [
        e["selected_score"]
        for e in selected_edges
        if e["claim_a"] in contributing_ids and e["claim_b"] in contributing_ids
    ]
    agreement_score = sum(intra_scores) / len(intra_scores) if intra_scores else 0.0

    return {
        "n_papers_represented": len(paper_ids),
        "n_claims": len(contributing),
        "mean_credibility": mean_cred,
        "agreement_score": agreement_score,
        "all_originals": n_rewritten == 0,
        "n_rewritten": n_rewritten,
        "total_rewrite_cost": total_rewrite_cost,
    }


def _compute_intra_frustration(
    contributing_ids: set[str],
    selected_edges: list[dict],
    sheaf_penrose: list[list[str]],
) -> dict:
    """Triangles entirely inside this Idea + Penrose count + residual negative edges."""
    intra_pen = [
        list(tri) for tri in sheaf_penrose if all(c in contributing_ids for c in tri)
    ]

    intra_adj: dict[str, dict[str, int]] = defaultdict(dict)
    for e in selected_edges:
        if e["claim_a"] in contributing_ids and e["claim_b"] in contributing_ids:
            score = e["selected_score"]
            sign = 0 if score == 0 else (1 if score > 0 else -1)
            intra_adj[e["claim_a"]][e["claim_b"]] = sign
            intra_adj[e["claim_b"]][e["claim_a"]] = sign

    nodes = sorted(intra_adj.keys())
    n_triangles = 0
    n_signed = 0
    for i, a in enumerate(nodes):
        for j in range(i + 1, len(nodes)):
            b = nodes[j]
            if b not in intra_adj[a]:
                continue
            for k in range(j + 1, len(nodes)):
                c = nodes[k]
                if c in intra_adj[a] and c in intra_adj[b]:
                    n_triangles += 1
                    s_ab = intra_adj[a][b]
                    s_ac = intra_adj[a][c]
                    s_bc = intra_adj[b][c]
                    if s_ab and s_ac and s_bc:
                        n_signed += 1

    rho = len(intra_pen) / n_signed if n_signed > 0 else 0.0

    residual_negative = [
        {
            "edge_id": e["edge_id"],
            "claim_a": e["claim_a"],
            "claim_b": e["claim_b"],
            "selected_score": e["selected_score"],
        }
        for e in selected_edges
        if e["claim_a"] in contributing_ids
        and e["claim_b"] in contributing_ids
        and e["selected_score"] <= 0
    ]

    return {
        "rho": rho,
        "n_triangles": n_triangles,
        "n_signed_triangles": n_signed,
        "n_penrose": len(intra_pen),
        "penrose_triangles": intra_pen,
        "residual_negative_edges": residual_negative,
    }


def _build_idea_record(
    proposed: dict,
    ordinal: int,
    corpus_name: str,
    sheaf: dict,
    claim_by_id: dict,
    label_to_id: dict[str, str],
    selected_edges: list[dict],
    timestamp: str,
    model: str,
) -> dict:
    """Convert one LLM-proposed idea to a full schema-conforming Idea record."""
    label = proposed["label"]
    slug = _slugify(label)
    idea_id = f"{corpus_name}/idea_{ordinal:02d}_{slug}"

    selected = sheaf["map_section"]["selected"]
    contributing = []
    for cc in proposed["contributing_claims"]:
        cid = cc["claim_id"]
        if cid not in claim_by_id:
            raise ValueError(
                f"Idea {label!r} references unknown claim_id {cid}"
            )
        if cid not in selected:
            raise ValueError(
                f"Idea {label!r} references claim {cid} not in MAP section"
            )
        claim = claim_by_id[cid]
        vid = selected[cid]
        variant = next(
            v for v in sheaf["stalks"][cid]["variants"] if v["variant_id"] == vid
        )
        contributing.append(
            {
                "claim_id": cid,
                "selected_variant_id": vid,
                "paper_id": claim["paper_id"],
                "credibility": claim.get("credibility_score"),
                "rewrite_distance": variant["rewrite_distance"],
                "role_in_idea": cc.get("role_in_idea", "supporting"),
            }
        )
    contributing.sort(key=lambda c: -(c["credibility"] or 0))

    scope_proposed = proposed.get("scope", {}) or {}
    scope = {
        "generality": scope_proposed.get("generality", "domain_specific"),
        "framework": scope_proposed.get("framework", ""),
        "conditions": scope_proposed.get("conditions", []) or [],
        "derived_from_claims": [c["claim_id"] for c in contributing],
        "derivation_timestamp": timestamp,
    }

    consensus = _compute_consensus(contributing, selected_edges)

    contributing_ids = {c["claim_id"] for c in contributing}
    sheaf_penrose = sheaf.get("frustration", {}).get("penrose_triangles", [])
    frustration_block = _compute_intra_frustration(
        contributing_ids, selected_edges, sheaf_penrose
    )

    transitions_out = []
    for t in proposed.get("transitions_out", []) or []:
        target_label = t.get("to_idea_label")
        if not target_label or target_label not in label_to_id:
            continue   # silently drop dangling references
        transitions_out.append(
            {
                "to_idea_id": label_to_id[target_label],
                "kind": t["kind"],
                "note": t.get("note", ""),
                "supporting_edges": t.get("supporting_edges", []) or [],
            }
        )

    open_questions = []
    for q in proposed.get("open_questions", []) or []:
        feeds_from = dict(q.get("feeds_from", {}) or {})
        if "transition_pointers" in feeds_from:
            feeds_from["transition_pointers"] = [
                label_to_id.get(label, label)
                for label in feeds_from["transition_pointers"]
            ]
        open_questions.append(
            {
                "question": q["question"],
                "feeds_from": feeds_from,
                "suggested_next_steps": q.get("suggested_next_steps", []) or [],
                "priority": q.get("priority", "medium"),
            }
        )

    return {
        "$schema": "landscape-map/idea/v0.2",
        "idea_id": idea_id,
        "label": label,
        "description": proposed["description"],
        "sheaf_ref": {
            "sheaf_id": sheaf["sheaf_id"],
            "section_label": "primary",
            "created_at": timestamp,
        },
        "contributing_claims": contributing,
        "scope": scope,
        "consensus": consensus,
        "frustration": frustration_block,
        "transitions_out": transitions_out,
        "transitions_in": [],   # filled in second pass
        "open_questions": open_questions,
        "extraction": {
            "method": "llm_single",
            "model": model,
            "human_reviewed": False,
        },
    }


def _fill_transitions_in(ideas: list[dict]) -> None:
    """Invert transitions_out across all ideas to populate each Idea's transitions_in."""
    in_map: dict[str, list[dict]] = defaultdict(list)
    by_id = {idea["idea_id"]: idea for idea in ideas}
    for idea in ideas:
        for t in idea["transitions_out"]:
            target_id = t["to_idea_id"]
            if target_id in by_id:
                in_map[target_id].append(
                    {
                        "from_idea_id": idea["idea_id"],
                        "kind": t["kind"],
                        "note": t.get("note", ""),
                        "supporting_edges": t.get("supporting_edges", []),
                    }
                )
    for idea in ideas:
        idea["transitions_in"] = in_map.get(idea["idea_id"], [])


# ---------- orchestration ----------------------------------------------------


def run(corpus: Corpus, run: Run) -> None:  # noqa: A002 (intentional shadow)
    if not run.sheaf_path.exists():
        raise RuntimeError(
            f"missing sheaf.json under {run.root}; run stages 4-7 first"
        )
    sheaf = json.loads(run.sheaf_path.read_text())
    if "map_section" not in sheaf:
        raise RuntimeError("sheaf missing map_section; run stage 6 first")

    claim_files = sorted(run.claims_dir.glob("*.json"))
    claim_by_id = {
        json.loads(f.read_text())["claim_id"]: json.loads(f.read_text())
        for f in claim_files
    }
    tags = (
        json.loads(run.tags_path.read_text()) if run.tags_path.exists() else {}
    )

    payload = _build_payload(sheaf, claim_by_id, tags)
    selected_edges = payload["selected_restriction_edges"]
    n_claims = len(payload["selected_claims"])

    console.print(f"stage 8: consolidating {n_claims} claims into Ideas")

    llm = LLM()
    proposed = _propose_partition(llm, payload)
    console.print(f"  LLM proposed [bold]{len(proposed)}[/bold] Ideas")

    # First pass: compute idea_ids so we can resolve transition labels
    label_to_id: dict[str, str] = {}
    for i, p in enumerate(proposed, 1):
        label_to_id[p["label"]] = f"{corpus.name}/idea_{i:02d}_{_slugify(p['label'])}"

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    ideas: list[dict] = []
    for ordinal, p in enumerate(proposed, 1):
        idea = _build_idea_record(
            proposed=p,
            ordinal=ordinal,
            corpus_name=corpus.name,
            sheaf=sheaf,
            claim_by_id=claim_by_id,
            label_to_id=label_to_id,
            selected_edges=selected_edges,
            timestamp=timestamp,
            model=llm.model,
        )
        ideas.append(idea)

    _fill_transitions_in(ideas)

    # Validate + write
    for idea in ideas:
        validate_idea(idea)
        out_path = run.ideas_dir / _idea_filename(idea["idea_id"])
        out_path.write_text(json.dumps(idea, indent=2))

    # Coverage check
    covered: dict[str, list[str]] = defaultdict(list)
    for idea in ideas:
        for c in idea["contributing_claims"]:
            covered[c["claim_id"]].append(idea["idea_id"])
    selected_ids = set(sheaf["map_section"]["selected"].keys())
    missing = sorted(selected_ids - covered.keys())
    duplicated = {cid: ids for cid, ids in covered.items() if len(ids) > 1}

    console.print()
    console.print(f"[bold]stage 8 summary[/bold]: {len(ideas)} Ideas written")
    for idea in ideas:
        rho = idea["frustration"]["rho"]
        rho_marker = (
            "[green]ρ=0[/green]"
            if rho == 0
            else f"[yellow]ρ={rho:.2f}[/yellow]" if rho < 0.2
            else f"[red]ρ={rho:.2f}[/red]"
        )
        console.print(
            f"  • {idea['label'][:70]}\n"
            f"    {idea['consensus']['n_claims']} claims, "
            f"{idea['consensus']['n_papers_represented']} papers, "
            f"agreement {idea['consensus']['agreement_score']:+.2f}, "
            f"{rho_marker}, "
            f"{len(idea['open_questions'])} open Qs"
        )

    if missing:
        console.print(
            f"  [yellow]warning[/yellow]: {len(missing)} MAP claims not in any Idea: "
            f"{missing[:5]}{'...' if len(missing) > 5 else ''}"
        )
    if duplicated:
        console.print(
            f"  [yellow]warning[/yellow]: {len(duplicated)} claims appear in multiple Ideas"
        )
