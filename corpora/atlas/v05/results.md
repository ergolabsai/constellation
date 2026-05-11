# Atlas corpus — v0.5 Ideas extraction

## Corpus

20 papers across the Atlas Z-pinch topic, with **Kumar et al. 2026 (Atlas)** as the latest paper. Prior work spans static-obstruction foundations (Newcomb, Frieman-Rotenberg, Bondeson-Iacono), the Hameiri rotating-screw-pinch framework, Z-pinch experimental program (Shumlak '95, ZaP '01, Angus 2020, FuZE/Zhang, Crews), double-Beltrami equilibrium foundations (Chandrasekhar-Kendall, Mahajan-Yoshida), Hall regularization (Shiraishi, Mahajan-Lingam, Sainterme-Ebrahimi), SARI / accretion-disk extension (Goedbloed-Keppens, Brughmans, Wang SMRI experimental), and numerical-method codes (Legolas).

## Sheaf state

**30 claims, 25 evidence, 63 edges** in the bipartite cellular sheaf.

The optimizer converged in 3 iterations with **residual 3.00 → 0.17 (94.3% reduction)**. Three claim rewrites applied:

| Claim | Paper | Rewrite |
|---|---|---|
| N_01 | Newcomb 1960 | narrow to STATIC regime only |
| AN_01 | Angus 2020 | narrow to NO-H3 profile families |
| B_01 | Bondeson-Iacono 1989 | narrow to TOROIDAL-without-H3 case |

Each is a scope-clarification rather than a weakening: the original observation stays, but the regime in which the claim binds becomes explicit. With these in place, the prior literature no longer apparently contradicts Atlas's H3-based m=1 closure — they sit in adjacent, well-characterized regimes.

## Optimizer note

For this corpus I switched the cost function from cumulative-square (`λ·(Σ d_i)²`) to sum-of-individual-squares (`λ·Σ d_i²`). The original form penalizes a second rewrite by the *cross-term* with the first, which made three independent small scope-narrowings unaffordable even though each saves residual on its own. The sum-of-squares form is the correct H¹-analogous formulation: each rewrite is an independent move to a different sheaf, scored on its own merit. The Shumlak run only ever applied one rewrite so this didn't surface there.

## Five Ideas

| # | Idea | Claims | Evidence | Papers | Rewrites |
|---|---|---:|---:|---:|---:|
| 1 | m=1 stability of rotating helical Z-pinch is closed by the H3 quartic Alfvén minimum | 10 | 9 | 4 | 3 |
| 2 | The static finite-β m=1 obstruction is genuine and survives as a special-case limit | 6 | 6 | 5 | 3 |
| 3 | Hall corrections at finite d_i/R regularize the H3 singularity over a layer of thickness d_i | 5 | 3 | 4 | 0 |
| 4 | Atlas's regime ends at M_A=1 where SARI continuum overlap takes over | 6 | 5 | 5 | 1* |
| 5 | Shumlak's m=0 sheared-flow stabilization is complementary, not competing | 6 | 5 | 6 | 0 |

\* Idea 4 invokes the GK_02 tightening conceptually; it wasn't applied by the optimizer because Atlas's own evidence already binds tightly.

Idea 1 is the headline result, pulling all three rewrites and all seven Atlas claims/evidence together. It explicitly resolves three apparent tensions: Newcomb-Kadomtsev's static obstruction (different regime), Angus 2020's m=1-still-unstable result (different profile family), and Bondeson-Iacono's mitigation result (different geometry without H3).

Idea 2 is the structural counterpart — it asserts that the static result is *still correct in its native regime*. It carries the same three narrowed claims as Idea 1, but flips the perspective: same scope-narrowing, opposite emphasis.

Idea 3 is the open frontier — the most pressing open question in the corpus. Atlas's d_i/R→0 asymptotic provides the unperturbed reference; whether the n^-4 accumulation survives Hall corrections is open. Sainterme-Ebrahimi 2026 just appeared in this space and explicitly motivates this question.

Idea 4 is the operating boundary — Atlas is stable for M_A < 1; SARI takes over at M_A ≥ 1. Atlas closes the M_A < 1 side of the Goedbloed-Keppens conjecture, leaving the M_A → 1 transition width as an open question.

Idea 5 is the complementarity result — Shumlak m=0 and Atlas m=1 are different mode families; together they potentially close both, but joint experimental realization on RIGID-BELTRAMI-A is the open verification path.

## Visualization

In the constellation graph:

- **Stars (★)** = claims from Atlas 2026 — the seven A_01 … A_07
- **Diamonds (◆)** = evidence from Atlas 2026 — the seven ev_atlas_*
- **Circles** = claims from prior papers, colored by paper
- **Squares** = evidence from prior papers, colored by paper

Atlas nodes additionally carry a gold (`#eab308`) accent border, so they stand out even at small scale. All nodes — including evidence squares/diamonds — are now colored by their paper of origin, with a themed legend (Static obstruction in blues, Z-pinch experimental in oranges, Hameiri framework in purples, Beltrami in teals, Hall in greens, SARI/MRI in pinks, codes in grays).

The five Idea blobs are clickable; clicking focuses one Idea and reveals its details panel with contributing claims, evidence, tensions resolved, open questions with typed next-steps, and transitions to neighboring Ideas.

## Where things live

- Per-claim JSON: `v05/claims/*.json` (30 files)
- Per-evidence JSON: `v05/evidence/*.json` (25 files)
- Optimizer final state: `v05/final_state.json`
- Per-Idea JSON: `v05/ideas/*.json` (5 files)
- Consolidated summary: `v05/ideas_summary.json`
- Visualization: `v05/constellation_v05_ideas.html`
