"""Stage 7: Penrose-triangle frustration diagnostics on the MAP section.

Input:  run.sheaf_path  (with map_section populated by stage 6)
Output: run.sheaf_path  (frustration: n_triangles, n_signed_triangles,
                         n_penrose, rho, penrose_triangles)

PURE CODE — no LLM. For every 3-cycle in the comparability complex, look up
the sign (+1 / 0 / -1) of each edge under the MAP-selected variant pair.
A signed triangle has all three edges non-zero. A Penrose triangle is one
where sign(e_ab) × sign(e_ac) × sign(e_bc) < 0 — structurally inconsistent.

ρ = n_penrose / n_signed_triangles is a discrete-H¹ surrogate. ρ = 0 means
the corpus's signed triangles are fully balanced after MAP rewriting; ρ > 0
indicates structural three-way tensions no single-claim rewrite resolves.
"""
from __future__ import annotations

import json
from collections import defaultdict

from rich.console import Console

from ..paths import Corpus, Run
from ..schemas import validate_sheaf

console = Console()


def _build_signed_graph(sheaf: dict) -> dict[str, dict[str, int]]:
    """Adjacency dict {claim_id: {neighbor_id: sign}}; sign in {-1, 0, +1}."""
    selected = sheaf["map_section"]["selected"]

    score_by_pair: dict[tuple[str, str], float] = {}
    for rm in sheaf["restriction_maps"]:
        for s in rm["compatibility_scores"]:
            score_by_pair[(s["variant_a_id"], s["variant_b_id"])] = float(s["score"])

    adj: dict[str, dict[str, int]] = defaultdict(dict)
    for rm in sheaf["restriction_maps"]:
        a, b = rm["claim_a"], rm["claim_b"]
        va, vb = selected[a], selected[b]
        score = score_by_pair[(va, vb)]
        sign = 0 if score == 0 else (1 if score > 0 else -1)
        adj[a][b] = sign
        adj[b][a] = sign
    return dict(adj)


def _enumerate_triangles(adj: dict[str, dict[str, int]]) -> list[tuple[str, str, str]]:
    """Every (a, b, c) with a < b < c and all three edges present."""
    nodes = sorted(adj.keys())
    out: list[tuple[str, str, str]] = []
    for i, a in enumerate(nodes):
        a_neighbors = adj.get(a, {})
        for j in range(i + 1, len(nodes)):
            b = nodes[j]
            if b not in a_neighbors:
                continue
            b_neighbors = adj.get(b, {})
            for k in range(j + 1, len(nodes)):
                c = nodes[k]
                if c in a_neighbors and c in b_neighbors:
                    out.append((a, b, c))
    return out


def _classify(
    tri: tuple[str, str, str], adj: dict[str, dict[str, int]]
) -> tuple[int, int, int]:
    a, b, c = tri
    return adj[a][b], adj[a][c], adj[b][c]


def run(corpus: Corpus, run: Run) -> None:  # noqa: A002 (intentional shadow)
    if not run.sheaf_path.exists():
        raise RuntimeError(
            f"missing sheaf.json under {run.root}; run stage 6 first"
        )
    sheaf = json.loads(run.sheaf_path.read_text())
    if "map_section" not in sheaf:
        raise RuntimeError("sheaf has no map_section; run stage 6 first")

    adj = _build_signed_graph(sheaf)
    triangles = _enumerate_triangles(adj)

    n_signed = 0
    n_penrose = 0
    penrose_list: list[list[str]] = []
    for tri in triangles:
        s_ab, s_ac, s_bc = _classify(tri, adj)
        if s_ab == 0 or s_ac == 0 or s_bc == 0:
            continue
        n_signed += 1
        if s_ab * s_ac * s_bc < 0:
            n_penrose += 1
            penrose_list.append(list(tri))

    rho = n_penrose / n_signed if n_signed > 0 else 0.0

    sheaf["frustration"] = {
        "n_triangles": len(triangles),
        "n_signed_triangles": n_signed,
        "n_penrose": n_penrose,
        "rho": rho,
        "penrose_triangles": penrose_list,
    }
    sheaf["extraction"]["notes"] = (
        sheaf["extraction"].get("notes", "")
        + f" Stage 7 computed frustration: "
        f"ρ = {rho:.3f} ({n_penrose}/{n_signed} signed triangles)."
    )
    run.sheaf_path.write_text(json.dumps(sheaf, indent=2))
    validate_sheaf(sheaf)

    console.print(f"  triangles in complex: {len(triangles)}")
    console.print(f"  signed triangles (all 3 edges non-zero): {n_signed}")
    health = (
        "[bold green]healthy[/bold green]"
        if rho == 0.0
        else "[bold yellow]flagged[/bold yellow]" if rho < 0.2
        else "[bold red]high[/bold red]"
    )
    console.print(
        f"  Penrose triangles: [bold]{n_penrose}[/bold]   "
        f"ρ = {rho:.3f}   {health}"
    )
    for tri in penrose_list:
        signs = _classify(tuple(tri), adj)  # type: ignore[arg-type]
        console.print(
            f"    [red]△[/red] {tri[0]}, {tri[1]}, {tri[2]}  "
            f"signs={signs}"
        )
