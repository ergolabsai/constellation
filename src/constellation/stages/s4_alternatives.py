"""Stage 4: generate hypothesis-space stalks (per-claim variants).

Per the architecture and our design choice D + "both sides":

  4a. Score every original-original pair on each comparability edge
      (one LLM call per edge). The score is stored in the restriction_map's
      compatibility_scores so stage 5 doesn't need to rescore it.

  4b. Identify contested edges: those with score < CONTEST_THRESHOLD.
      For each contested edge, BOTH endpoint claims are flagged for
      alternative generation, with the other endpoint as a "failing neighbor".

  4c. For each flagged claim, one LLM call generates 1-3 evidence-faithful
      alternatives. Each alternative carries metadata: which neighbors it was
      generated to satisfy, which weaknesses it invokes, which strengths it
      preserves. Most stalks remain singletons.

Output: run.sheaf_path is initialized with `base`, `stalks`, and
`restriction_maps` (each with the original-original score already populated).
The sheaf is incomplete at this point — `map_section` and the rest of the
cube come later. Final schema validation is deferred to stage 7.
"""
from __future__ import annotations

import json
from typing import Any

from rich.console import Console

from ..llm import LLM, parse_json_response
from ..paths import Corpus, Run
from ..prompt_loader import load_prompt
from ..scoring import VariantHandle, canonical_text, score_pair

console = Console()

# Pairs with original-original score < this trigger alternative generation
# for both endpoints. 0.0 = "anything negative is contested"; tighten or loosen
# as we observe behavior.
CONTEST_THRESHOLD = 0.0
MAX_RETRIES = 1


# ---------- helpers ----------------------------------------------------------


def _load_inputs(run: Run) -> tuple[dict, dict[str, dict]]:
    if not run.complex_path.exists():
        raise RuntimeError(
            f"missing comparability_complex.json under {run.root}; run stage 3 first"
        )
    complex_doc = json.loads(run.complex_path.read_text())
    claim_files = sorted(run.claims_dir.glob("*.json"))
    claim_by_id: dict[str, dict] = {}
    for f in claim_files:
        c = json.loads(f.read_text())
        claim_by_id[c["claim_id"]] = c
    return complex_doc, claim_by_id


def _original_handle(claim: dict) -> VariantHandle:
    return VariantHandle(
        claim_id=claim["claim_id"],
        variant_id=f"{claim['claim_id']}#original",
        text=canonical_text(claim),
        full_claim=claim,
    )


def _build_original_variant_record(claim: dict) -> dict:
    """The `#original` entry in a stalk's variants array."""
    return {
        "variant_id": f"{claim['claim_id']}#original",
        "text": canonical_text(claim),
        "rewrite_distance": 0.0,
        "targets": [],
        "evidence_strengths_invoked": list(
            claim.get("evidence", {}).get("strengths", []) or []
        ),
        "evidence_weaknesses_invoked": [],
        "evidence_faithful": True,
        "faithfulness_note": "Original claim as extracted from the paper.",
        "extraction": {
            "method": "paper",
            "confidence": 1.0,
        },
    }


def _validate_alternative(
    alt: Any, claim: dict, allowed_targets: set[str]
) -> dict:
    """Light validation of an LLM-generated alternative. Raises ValueError on issues."""
    if not isinstance(alt, dict):
        raise ValueError(f"alternative must be an object, got {type(alt).__name__}")
    for k in (
        "variant_id",
        "text",
        "rewrite_distance",
        "targets",
        "evidence_strengths_invoked",
        "evidence_weaknesses_invoked",
        "evidence_faithful",
    ):
        if k not in alt:
            raise ValueError(f"alternative missing key '{k}'")

    cid = claim["claim_id"]
    if not alt["variant_id"].startswith(f"{cid}#"):
        raise ValueError(
            f"variant_id {alt['variant_id']!r} must start with {cid}#"
        )
    if alt["variant_id"] == f"{cid}#original":
        raise ValueError("variant_id '#original' is reserved")

    rd = alt["rewrite_distance"]
    if not isinstance(rd, int | float) or not (0.0 <= rd <= 1.0):
        raise ValueError(
            f"rewrite_distance must be a number in [0, 1], got {rd!r}"
        )

    if not isinstance(alt["targets"], list) or not alt["targets"]:
        raise ValueError("targets must be a non-empty list of neighbor claim_ids")
    for t in alt["targets"]:
        if t not in allowed_targets:
            raise ValueError(
                f"target {t!r} is not in this claim's contested neighbors "
                f"{sorted(allowed_targets)}"
            )

    if not isinstance(alt["evidence_strengths_invoked"], list):
        raise ValueError("evidence_strengths_invoked must be a list")
    if not isinstance(alt["evidence_weaknesses_invoked"], list):
        raise ValueError("evidence_weaknesses_invoked must be a list")

    return {
        "variant_id": alt["variant_id"],
        "text": str(alt["text"]),
        "rewrite_distance": float(rd),
        "targets": list(alt["targets"]),
        "evidence_strengths_invoked": list(alt["evidence_strengths_invoked"]),
        "evidence_weaknesses_invoked": list(alt["evidence_weaknesses_invoked"]),
        "evidence_faithful": bool(alt["evidence_faithful"]),
        "faithfulness_note": str(alt.get("faithfulness_note", "")),
        "extraction": {
            "method": "llm_single",
        },
    }


def _generate_alternatives_for_claim(
    *,
    claim: dict,
    # each entry: {neighbor_id, neighbor_claim, score, kind, explanation, edge_id}
    contested_neighbors: list[dict],
    llm: LLM,
    system: str,
) -> list[dict]:
    """One LLM call. Returns the validated alternatives list (may be empty)."""
    payload = {
        "contested_claim": {
            "claim_id": claim["claim_id"],
            "paper_id": claim["paper_id"],
            "cause": claim.get("cause"),
            "effect": claim.get("effect"),
            "direction": claim.get("direction"),
            "scope_claimed": claim.get("scope", {}).get("claimed"),
            "scope_evidenced": claim.get("scope", {}).get("evidenced"),
            "evidence": claim.get("evidence"),
            "credibility_score": claim.get("credibility_score"),
        },
        "contested_neighbors": [
            {
                "claim_id": n["neighbor_id"],
                "paper_id": n["neighbor_claim"]["paper_id"],
                "cause": n["neighbor_claim"].get("cause"),
                "effect": n["neighbor_claim"].get("effect"),
                "direction": n["neighbor_claim"].get("direction"),
                "scope_evidenced": n["neighbor_claim"].get("scope", {}).get("evidenced"),
                "compatibility_with_original": {
                    "score": n["score"],
                    "kind": n["kind"],
                    "explanation": n["explanation"],
                    "edge_id": n["edge_id"],
                },
            }
            for n in contested_neighbors
        ],
    }
    user_text = (
        f"Generate evidence-faithful alternatives for claim {claim['claim_id']}. "
        "Return ONLY the JSON object.\n\n```json\n"
        + json.dumps(payload, indent=2)
        + "\n```"
    )

    allowed_targets = {n["neighbor_id"] for n in contested_neighbors}
    messages = [{"role": "user", "content": [{"type": "text", "text": user_text}]}]

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            text = llm.chat(system=system, messages=messages, max_tokens=4096)
            parsed = parse_json_response(text)
            if not isinstance(parsed, dict) or "alternatives" not in parsed:
                raise ValueError("response must be {'alternatives': [...]}")
            alts_raw = parsed["alternatives"]
            if not isinstance(alts_raw, list):
                raise ValueError("alternatives must be an array")
            if len(alts_raw) > 3:
                raise ValueError(
                    f"max 3 alternatives per claim; model returned {len(alts_raw)}"
                )
            validated: list[dict] = []
            seen_ids: set[str] = set()
            for alt in alts_raw:
                v = _validate_alternative(alt, claim, allowed_targets)
                if v["variant_id"] in seen_ids:
                    raise ValueError(f"duplicate variant_id {v['variant_id']!r}")
                seen_ids.add(v["variant_id"])
                # stamp model
                v["extraction"]["model"] = llm.model
                validated.append(v)
            return validated
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
    raise RuntimeError(
        f"alternative generation for {claim['claim_id']} failed: {last_error}"
    )


# ---------- orchestration ----------------------------------------------------


def run(corpus: Corpus, run: Run) -> None:  # noqa: A002 (intentional shadow)
    llm = LLM()
    altgen_system = load_prompt("s4_generate_alternatives")

    complex_doc, claim_by_id = _load_inputs(run)
    edges = complex_doc["edges"]
    console.print(
        f"stage 4: scoring {len(edges)} edges and generating alternatives "
        f"for contested ones (threshold: score < {CONTEST_THRESHOLD})"
    )

    # ---- 4a: score every original-original pair ----
    console.print(f"  [bold]4a[/bold]: scoring original-original pairs ({len(edges)} edges)")
    edge_scores: dict[str, dict] = {}
    for i, edge in enumerate(edges, 1):
        a = _original_handle(claim_by_id[edge["claim_a"]])
        b = _original_handle(claim_by_id[edge["claim_b"]])
        result = score_pair(
            a=a,
            b=b,
            semilattice_meet=edge["semilattice_meet"],
            snag_overlap=edge["snag_overlap"],
            llm=llm,
        )
        edge_scores[edge["edge_id"]] = result
        marker = "[red]✗[/red]" if result["score"] < CONTEST_THRESHOLD else "[green]✓[/green]"
        console.print(
            f"    {marker} {edge['edge_id']}: {result['kind']} ({result['score']:+.2f})"
            + (f"  · {i}/{len(edges)}" if i % 5 == 0 else "")
        )

    # ---- 4b: group contested neighbors per claim ----
    contested_per_claim: dict[str, list[dict]] = {}
    for edge in edges:
        s = edge_scores[edge["edge_id"]]
        if s["score"] >= CONTEST_THRESHOLD:
            continue
        for self_id, other_id in (
            (edge["claim_a"], edge["claim_b"]),
            (edge["claim_b"], edge["claim_a"]),
        ):
            contested_per_claim.setdefault(self_id, []).append(
                {
                    "neighbor_id": other_id,
                    "neighbor_claim": claim_by_id[other_id],
                    "score": s["score"],
                    "kind": s["kind"],
                    "explanation": s["explanation"],
                    "edge_id": edge["edge_id"],
                }
            )

    n_contested_claims = len(contested_per_claim)
    n_contested_edges = sum(
        1 for s in edge_scores.values() if s["score"] < CONTEST_THRESHOLD
    )
    console.print(
        f"  [bold]4b[/bold]: {n_contested_edges} contested edges → "
        f"{n_contested_claims} contested claims (each gets alternative generation)"
    )

    # ---- 4c: generate alternatives ----
    stalks: dict[str, dict] = {}
    n_alts_total = 0
    for cid in complex_doc["claim_ids"]:
        original_record = _build_original_variant_record(claim_by_id[cid])
        variants = [original_record]
        if cid in contested_per_claim:
            console.print(f"    generating alternatives for [yellow]{cid}[/yellow]…")
            try:
                alts = _generate_alternatives_for_claim(
                    claim=claim_by_id[cid],
                    contested_neighbors=contested_per_claim[cid],
                    llm=llm,
                    system=altgen_system,
                )
            except Exception as e:
                console.print(f"      [red]failed[/red]: {e}")
                alts = []
            for a in alts:
                variants.append(a)
            n_alts_total += len(alts)
            console.print(
                f"      [green]→[/green] {len(alts)} alternative(s): "
                + ", ".join(a["variant_id"].split("#", 1)[1] for a in alts)
                if alts
                else "      [dim]no alternatives generated[/dim]"
            )
        stalks[cid] = {"claim_id": cid, "variants": variants}

    # ---- assemble partial sheaf and write ----
    restriction_maps = []
    for edge in edges:
        s = edge_scores[edge["edge_id"]]
        restriction_maps.append(
            {
                "edge_id": f"restriction:{edge['claim_a']}↔{edge['claim_b']}",
                "claim_a": edge["claim_a"],
                "claim_b": edge["claim_b"],
                "semilattice_meet": edge["semilattice_meet"],
                "snag_overlap": len(edge["snag_overlap"]),
                "snag_overlap_nodes": edge["snag_overlap"],   # extra info, not required by schema
                "restriction_kind": "symmetric_compatibility",
                "compatibility_scores": [s],   # original-original; stage 5 fills the rest
                "extraction": {
                    "method": "llm_single",
                    "model": llm.model,
                },
            }
        )

    sheaf = {
        "$schema": "landscape-map/sheaf/v0.1",
        "sheaf_id": f"{corpus.name}/{run.root.name}",
        "corpus": corpus.name,
        "pipeline_version": "v2_paper_as_stalk",
        "base": complex_doc["claim_ids"],
        "stalks": stalks,
        "restriction_maps": restriction_maps,
        # map_section, frustration come in stages 6/7
        "extraction": {
            "method": "llm_single",
            "model": llm.model,
            "notes": (
                "Partial sheaf written by stage 4: stalks initialized, "
                "original-original compatibility scores computed. "
                "Variant×variant cube to be filled by stage 5; map_section "
                "and frustration by stages 6 and 7."
            ),
        },
    }
    run.sheaf_path.write_text(json.dumps(sheaf, indent=2))

    # summary
    n_singletons = sum(1 for s in stalks.values() if len(s["variants"]) == 1)
    n_with_alts = len(stalks) - n_singletons
    console.print()
    console.print(
        f"[bold]stage 4 summary[/bold]: "
        f"{len(edges)} edges scored "
        f"({n_contested_edges} contested), "
        f"{n_with_alts}/{len(stalks)} stalks non-singleton "
        f"({n_alts_total} alternatives generated)"
    )
