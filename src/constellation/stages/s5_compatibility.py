"""Stage 5: score the full compatibility cube.

Input:  run.sheaf_path  (stalks populated by stage 4; original-original scores
                         already present in restriction_maps)
Output: run.sheaf_path  (every variant_a × variant_b pair on every edge has
                         a compatibility score)

Same scoring primitive as stage 4 (`scoring.score_pair`). Per the architecture,
storing the FULL cube — not just MAP-selected pairs — lets the section be
replayed at different λ rewrite penalties without re-scoring.

Most edges are 1×1 (both stalks are singletons, no new cells). Edges touching
a claim with alternatives grow to 1×N or N×M; we score the cells that aren't
already in `compatibility_scores`.
"""
from __future__ import annotations

import json

from rich.console import Console

from ..config import model_name
from ..llm import LLM
from ..paths import Corpus, Run
from ..scoring import VariantHandle, score_pair

console = Console()


def _load_inputs(run: Run) -> tuple[dict, dict[str, dict]]:
    if not run.sheaf_path.exists():
        raise RuntimeError(
            f"missing sheaf.json under {run.root}; run stage 4 first"
        )
    sheaf = json.loads(run.sheaf_path.read_text())
    claim_files = sorted(run.claims_dir.glob("*.json"))
    claim_by_id = {
        json.loads(f.read_text())["claim_id"]: json.loads(f.read_text())
        for f in claim_files
    }
    return sheaf, claim_by_id


def _variant_handles(stalk: dict, claim: dict) -> list[VariantHandle]:
    """Build VariantHandle for each variant in a stalk."""
    return [
        VariantHandle(
            claim_id=stalk["claim_id"],
            variant_id=v["variant_id"],
            text=v["text"],
            full_claim=claim,
        )
        for v in stalk["variants"]
    ]


def _existing_pairs(rm: dict) -> set[tuple[str, str]]:
    """Set of (variant_a_id, variant_b_id) already scored on this edge."""
    return {
        (s["variant_a_id"], s["variant_b_id"])
        for s in rm.get("compatibility_scores", [])
    }


def _missing_pairs(
    rm: dict,
    variants_a: list[VariantHandle],
    variants_b: list[VariantHandle],
) -> list[tuple[VariantHandle, VariantHandle]]:
    """Cross product of variants minus pairs already scored."""
    have = _existing_pairs(rm)
    out = []
    for va in variants_a:
        for vb in variants_b:
            if (va.variant_id, vb.variant_id) in have:
                continue
            out.append((va, vb))
    return out


def run(corpus: Corpus, run: Run) -> None:  # noqa: A002 (intentional shadow)
    sheaf, claim_by_id = _load_inputs(run)
    stalks = sheaf["stalks"]
    rms = sheaf["restriction_maps"]

    # Tally what we need to do upfront so the operator sees the cost
    plan: list[tuple[dict, list[tuple[VariantHandle, VariantHandle]]]] = []
    total_new = 0
    for rm in rms:
        a_handles = _variant_handles(stalks[rm["claim_a"]], claim_by_id[rm["claim_a"]])
        b_handles = _variant_handles(stalks[rm["claim_b"]], claim_by_id[rm["claim_b"]])
        missing = _missing_pairs(rm, a_handles, b_handles)
        plan.append((rm, missing))
        total_new += len(missing)

    n_edges = len(rms)
    n_edges_with_work = sum(1 for _, m in plan if m)
    console.print(
        f"stage 5: filling compatibility cube — "
        f"{total_new} new variant-pair scorings across "
        f"{n_edges_with_work}/{n_edges} edges"
    )

    if total_new == 0:
        console.print("  [green]nothing to do — cube already complete[/green]")
        run.sheaf_path.write_text(json.dumps(sheaf, indent=2))
        return

    llm = LLM(model=model_name(run, corpus))
    n_done = 0
    for rm, missing in plan:
        if not missing:
            continue
        for va, vb in missing:
            result = score_pair(
                a=va,
                b=vb,
                semilattice_meet=rm["semilattice_meet"],
                snag_overlap=rm.get("snag_overlap_nodes", []),
                llm=llm,
                run=run,
                cache_stage="stage5_compatibility",
            )
            rm["compatibility_scores"].append(result)
            n_done += 1
            console.print(
                f"  [{n_done}/{total_new}] {result['variant_a_id']} ↔ "
                f"{result['variant_b_id']}: "
                f"{result['kind']} ({result['score']:+.2f})"
            )

    # Restamp extraction notes
    sheaf.setdefault("extraction", {})
    sheaf["extraction"]["notes"] = (
        sheaf["extraction"].get("notes", "")
        + f" Stage 5 added {n_done} variant-pair scorings to complete the cube."
    )
    run.sheaf_path.write_text(json.dumps(sheaf, indent=2))

    # summary
    cube_size = sum(len(rm["compatibility_scores"]) for rm in rms)
    by_kind: dict[str, int] = {}
    for rm in rms:
        for s in rm["compatibility_scores"]:
            by_kind[s["kind"]] = by_kind.get(s["kind"], 0) + 1
    console.print()
    console.print(
        f"[bold]stage 5 summary[/bold]: cube has {cube_size} entries across "
        f"{n_edges} edges"
    )
    for kind in (
        "agreement",
        "extension",
        "refinement",
        "qualification",
        "boundary",
        "contradiction",
    ):
        if kind in by_kind:
            console.print(f"  {kind}: {by_kind[kind]}")
