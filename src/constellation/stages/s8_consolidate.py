"""Stage 8: consolidate into Ideas (ε-machine partition).

Input:  run.sheaf_path  (with map_section + frustration; full pipeline through stage 7)
        run.claims_dir
        run.tags_path
Output: run.ideas_dir/<idea_id>.json   (one per ε-state, validates against idea_schema)
        run.epsilon_machine_path       (C_mu + transition metrics)

LLM proposes the partition + transitions + open questions. Code fills in the
deterministic pieces:
  - idea_id from the slug of the label
  - consensus block (n_papers, mean_credibility, agreement_score, rewrite stats)
  - intra-Idea frustration (Penrose triangles + residual negative edges within the Idea)
  - transitions_in (inverted from transitions_out)
  - sheaf_ref (back-pointer)
  - epsilon_machine.json (state distribution + statistical complexity)
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import UTC, datetime

from rich.console import Console

from ..config import model_name, stage_config
from ..epsilon_machine import write_epsilon_machine_metrics
from ..idea_partition import validate_idea_partition as _validate_idea_partition
from ..llm import LLM, parse_json_response
from ..llm_cache import LLMCacheHandle
from ..llm_cache import lookup as cache_lookup
from ..llm_cache import write_success as cache_write_success
from ..paths import Corpus, Run
from ..prompt_loader import load_prompt
from ..schemas import validate_idea

console = Console()

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


def _propose_partition(
    llm: LLM, run: Run, payload: dict, *, max_retries: int
) -> tuple[list[dict], LLMCacheHandle, str, dict]:
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
    for attempt in range(max_retries + 1):
        cache_handle = cache_lookup(
            run=run,
            stage="stage8_consolidate",
            llm=llm,
            system=system,
            messages=messages,
            max_tokens=32768,
        )
        try:
            # Big payload — corpora with hundreds of claims need substantial
            # output room. Sonnet supports up to 64K output tokens.
            if cache_handle.hit:
                text = cache_handle.raw_response
                parsed = cache_handle.parsed_response
            else:
                text = llm.chat(system=system, messages=messages, max_tokens=32768)
                parsed = parse_json_response(text)
            if not isinstance(parsed, dict) or "ideas" not in parsed:
                raise ValueError("response must be {'ideas': [...]}")
            ideas = parsed["ideas"]
            if not isinstance(ideas, list) or not ideas:
                raise ValueError("'ideas' must be a non-empty list")
            return ideas, cache_handle, text, parsed
        except (ValueError, json.JSONDecodeError) as e:
            last_error = e
            if attempt == max_retries:
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
        kind = t.get("kind")
        # Drop transitions missing required schema fields; downstream
        # validation rejects the whole Idea otherwise.
        if not target_label or target_label not in label_to_id or not kind:
            continue
        transitions_out.append(
            {
                "to_idea_id": label_to_id[target_label],
                "kind": kind,
                "note": t.get("note", ""),
                "supporting_edges": t.get("supporting_edges", []) or [],
            }
        )

    open_questions = []
    for q in proposed.get("open_questions", []) or []:
        if not isinstance(q, dict) or not q.get("question"):
            continue
        feeds_from = dict(q.get("feeds_from", {}) or {})
        if "transition_pointers" in feeds_from:
            feeds_from["transition_pointers"] = [
                label_to_id.get(label, label)
                for label in feeds_from["transition_pointers"]
            ]
        # Filter out malformed steps — schema requires `kind` and `description`.
        clean_steps = [
            s for s in (q.get("suggested_next_steps", []) or [])
            if isinstance(s, dict) and s.get("kind") and s.get("description")
        ]
        open_questions.append(
            {
                "question": q["question"],
                "feeds_from": feeds_from,
                "suggested_next_steps": clean_steps,
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


def _deduplicate_ideas(ideas: list[dict]) -> list[dict]:
    """Remove claims that appear in multiple Ideas, keeping first occurrence.

    Returns deduplicated ideas and logs a warning if any duplicates were found.
    """
    claim_to_idea: dict[str, str] = {}
    duplicates: dict[str, list[str]] = {}

    for idea in ideas:
        idea_id = idea.get("idea_id", "unknown")
        for contrib in idea.get("contributing_claims", []) or []:
            claim_id = contrib.get("claim_id")
            if not claim_id:
                continue
            if claim_id in claim_to_idea:
                # Track duplicate
                if claim_id not in duplicates:
                    duplicates[claim_id] = [claim_to_idea[claim_id]]
                duplicates[claim_id].append(idea_id)
            else:
                claim_to_idea[claim_id] = idea_id

    if not duplicates:
        return ideas

    # Log the duplicates
    console.print(f"  [yellow]warning[/yellow]: found {len(duplicates)} duplicated claims")
    for claim_id, idea_ids in sorted(duplicates.items()):
        console.print(
            f"    {claim_id}: keeping in {idea_ids[0]}, "
            f"removing from {', '.join(idea_ids[1:])}"
        )

    # Remove duplicates: keep in first Idea, remove from rest
    first_idea_per_claim = {
        claim_id: idea_ids[0] for claim_id, idea_ids in duplicates.items()
    }

    for idea in ideas:
        idea_id = idea.get("idea_id", "unknown")
        original_count = len(idea.get("contributing_claims", []) or [])
        idea["contributing_claims"] = [
            contrib
            for contrib in (idea.get("contributing_claims", []) or [])
            if contrib.get("claim_id") not in first_idea_per_claim
            or first_idea_per_claim[contrib["claim_id"]] == idea_id
        ]
        removed = original_count - len(idea["contributing_claims"])
        if removed > 0:
            console.print(f"    → {idea_id}: removed {removed} duplicate(s)")

    return ideas


def _validate_and_write_ideas(
    run: Run,
    ideas: list[dict],
    selected_claim_ids: set[str],
    selected_edges: list[dict],
    sheaf: dict,
) -> None:
    """Validate a new Idea set, then replace the run's Idea JSON files."""
    ideas = _deduplicate_ideas(ideas)

    # Recompute consensus and frustration blocks if any ideas lost claims
    for idea in ideas:
        contributing = idea.get("contributing_claims", []) or []
        if contributing:
            idea["consensus"] = _compute_consensus(contributing, selected_edges)
            contributing_ids = {c["claim_id"] for c in contributing}
            sheaf_penrose = sheaf.get("frustration", {}).get("penrose_triangles", [])
            idea["frustration"] = _compute_intra_frustration(
                contributing_ids, selected_edges, sheaf_penrose
            )

    _validate_idea_partition(ideas, selected_claim_ids)
    for idea in ideas:
        validate_idea(idea)

    for old_path in sorted(run.ideas_dir.glob("*.json")):
        old_path.unlink()
    for idea in ideas:
        out_path = run.ideas_dir / _idea_filename(idea["idea_id"])
        out_path.write_text(json.dumps(idea, indent=2))
    write_epsilon_machine_metrics(run, ideas)


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

    cfg = stage_config(run, corpus, "stage8_consolidate")
    llm = LLM(model=model_name(run, corpus))
    proposed, cache_handle, cache_text, cache_parsed = _propose_partition(
        llm, run, payload, max_retries=int(cfg["max_retries"])
    )
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
    selected_ids = set(sheaf["map_section"]["selected"].keys())
    _validate_and_write_ideas(run, ideas, selected_ids, selected_edges, sheaf)
    cache_write_success(
        cache_handle,
        raw_response=cache_text,
        parsed_response=cache_parsed,
    )

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
