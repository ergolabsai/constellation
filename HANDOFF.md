# Constellation / Landscape Map — handoff

This document is for resuming the conversation on a different machine. It captures the working state, the conceptual vocabulary that's been built up, the most recent decisions, and the threads in flight.

## What this project is

A pipeline that turns curated scientific paper corpora into consolidated knowledge structures using cellular sheaf theory. The high-level flow:

```
papers → claims + evidence (extraction)
       → bipartite cellular sheaf with restriction maps (encoding)
       → optimizer settles into a state with rewrites, residuals (inference)
       → Ideas with scope, tensions, open questions, transitions (consolidation)
       → interactive constellation visualization (navigation)
```

The latest run is on the **Atlas corpus** (20 papers around the Kumar et al. 2026 result on m=1 stability of the rotating helical Z-pinch). The output is in `/Users/chelsea/ErgoLabs/constellation/corpora/atlas/v05/`.

## Conceptual vocabulary

The next session needs to know these terms because they get used heavily without re-explanation.

**Bipartite cellular sheaf.** Two vertex sets: claims and evidence. Claim stalks are F(c) = ℝ² = (x_in, x_out) — strength of the claim in its home regime and out of its home regime. Evidence stalks are F(v) = ℝ² = (core, context) — core observation value (immovable) and context-regime parameter (fillable at cost). Edges are (claim, evidence) pairs each carrying a base_prediction and an in_regime flag. The restriction map is the prediction function `pred = strength × base + (1−strength) × actual`.

**Three-tier cost.** λ_claim = 1.0 (claim rewrites are cheap), λ_evidence_context = 5.0 (context fills are expensive), evidence_core change is forbidden. Encodes: "observation is the truth, context can be made explicit at cost, claim scope is freely revisable."

**Sum-of-individual-squares cost (not square-of-sum).** This was a fix made during the Atlas run. The original Shumlak cost was λ·(Σdᵢ)² which penalizes a second rewrite by the cross-term with the first. Atlas needed three independent narrowings — switched to λ·Σdᵢ² so each rewrite is judged on its own. The Shumlak run only ever applied one rewrite so the bug didn't surface there.

**H⁰ and H¹ (sheaf cohomology).** H⁰ = global sections = an assignment where every edge prediction equals every observation. Usually empty for real corpora. H¹ = coker(δ) ≅ im(δ)⊥ = the part of the residual that *no* assignment can kill — it's a structural feature of the sheaf, not the assignment. The optimizer minimizes ||δx||² within a fixed sheaf, and the residual that survives is the H¹ projection. Rewrites change the sheaf itself, so they move you to a different H¹.

**Ideas.** Consolidated knowledge units. Each Idea has:
- `scope` (regime, framework, conditions)
- `contributing_claims` and `contributing_evidence` (with paper-of-origin and rewrite/fill status)
- `tensions_resolved` (before/after pairs naming what apparent conflict was resolved and how)
- `open_questions` with priority, feeds_into, and **typed `suggested_next_steps`**
- `transitions_out` (graph edges to neighboring Ideas)

The typed next-steps vocabulary: `experiment`, `simulation`, `theory_extension`, `literature`, `corpus_expansion`, `re_examine_claim`. This is the structured output downstream tooling dispatches on.

**The "next-Idea predictor" framing.** A thread the user is actively chewing on. By analogy to LLMs as next-token predictors, what would a next-Idea predictor look like? The architecture we converged on factors like AlphaGo: LLM-as-proposer (given the current Idea-graph and open questions, generate candidate new claims/evidence) + sheaf-as-scorer (splice each candidate in, measure how much H¹ it kills, penalize cascading rewrites of trusted claims). Three semantics of "next": logical-next (implied by open questions), empirical-next (Bayesian experimental design, lines up with three-tier cost), field-trajectory-next (learned across many fields).

## What's been built and runs

**Scripts (in `/Users/chelsea/Library/Application Support/Claude/local-agent-mode-sessions/.../outputs/`)** — these are scratch but everything important they produce lands in the corpus folders:

- `atlas_v05.py` — encodes 30 claims, 25 evidence, 63 edges for the Atlas corpus; runs the three-tier-cost optimizer; writes `final_state.json`.
- `atlas_v05_ideas.py` — consolidates the settled state into 5 Ideas with scope/tensions/questions/transitions; writes per-Idea JSONs + `ideas_summary.json`.
- `atlas_v05_viz.py` — builds the constellation HTML (stars for Atlas claims, diamonds for Atlas evidence, per-paper coloring on all nodes, clickable Ideas + clickable nodes with detail panels).

Earlier Shumlak run lives at `/Users/chelsea/ErgoLabs/claude_cowork/restriction rewriting/v05/` with the same shape of artifacts (`shumlak_v05.py`, `shumlak_v05_ideas.py`, `shumlak_v05_ideas_graph_viz.py`).

**Atlas corpus output (`/Users/chelsea/ErgoLabs/constellation/corpora/atlas/v05/`):**
- `final_state.json` — settled state: residual 3.00 → 0.17 (94.3% reduction); three rewrites applied (N_01 narrowed to static, AN_01 narrowed to no-H3 profiles, B_01 narrowed to toroidal-without-H3)
- `ideas_summary.json` + `ideas/*.json` — five Ideas
- `claims/*.json`, `evidence/*.json` — per-node JSONs
- `constellation_v05_ideas.html` — interactive viz
- `results.md` — written summary

**The viz (current state).** Open the HTML at `constellation_v05_ideas.html`. Atlas claims appear as **gold stars**, Atlas evidence as **gold diamonds**. Prior claims are circles, prior evidence are squares — both colored by paper-of-origin (themed palette: blues for static obstruction, purples for Hameiri framework, oranges for Z-pinch experimental, teals for Beltrami foundations, greens for Hall regularization, pinks for SARI/MRI, grays for codes). Five Idea blobs cluster around their member nodes. Edge color = residual magnitude (gray = agreement, orange = mild tension 0.01–0.05, red = strong tension ≥0.05). Click an Idea blob → focuses + populates right panel. Click a node → focuses + shows node detail (claim or evidence) with all connected edges (residual badges) and which Ideas it appears in. Edge rows and Idea pills inside detail panels are click-to-navigate.

**The three surviving tension edges (post-rewrite) all converge on Atlas's central evidence `ev_atlas_kink_zero`.** B_01→ev_atlas_kink_zero is red (0.09); N_01 and AN_01→ev_atlas_kink_zero are orange (0.04 each). This is the residual H¹ obstruction — the *residual softness* of scope-narrowed prior claims still pushing back against Atlas's headline result.

## Recent decisions / aesthetic preferences worth preserving

The user pushed back on a few things during this session — these are the choices that should stick:

1. **No dashed edges.** I tried encoding in-regime/out-of-regime as solid/dashed. The user said this was overthinking. Color alone communicates residual; the in/out-of-regime distinction is conceptual scaffolding, not viewer-facing. Keep edges solid.

2. **Edge color thresholds are tuned for the actual residual distribution.** The original Shumlak thresholds (>0.5, >0.1) were too coarse for Atlas (max residual was 0.09). Current thresholds are >0.05 red, >0.01 orange. Re-tune per corpus.

3. **Sum-of-individual-squares cost** for rewrites (not square-of-sum). See "vocabulary" above.

4. **Prose over bullets** in conversational replies. The user has expressed multiple times that they prefer prose. Headers and bullet lists are for documents like this one, not for chat answers.

5. **Stars for the latest paper, diamonds for its evidence.** This is a generalizable convention worth keeping across future corpora — whichever paper is "the latest" gets the star/diamond treatment with a gold accent.

## Conceptual threads in flight

These are the open intellectual threads the user is actively working on. The next session should be ready to pick them up.

**The next-Idea predictor (AlphaGo factoring).** Already discussed in depth — LLM-proposer + sheaf-scorer. The candidate site for next-Ideas is "neighborhoods in some embedding space that have downstream gravity but no consolidated Idea yet." Where this thread is heading: building the proposer.

**Cohomology as the math.** I wrote a long response walking through how H⁰ = global sections, H¹ = obstructions, the residual after optimization projects onto H¹, rewrites change the sheaf so they navigate between H¹'s, "next Idea = thing that drops H¹ the most when added as local data." The user found this useful framing. Use the vocabulary freely.

**Andrew White podcast (AI for Science / Latent Space).** The user shared the first episode (Andrew White, Future House / Edison Scientific). The connection I drew: Cosmos's "world model" is structurally what our sheaf is. Cosmos's filtration converged on verifier-in-the-loop (their Robin experiment); our sheaf is the structural version of the same idea. Things from Cosmos worth stealing: brute-force enumeration of candidate hypotheses, PaperQA-style provenance density, Bixbench-style structured benchmarks. Things we have they don't: explicit cohomology, cost-stratified rewrites, Ideas as navigable structural units, typed next-steps as dispatchable output.

**Kim et al. 2026 EDM paper (Sci Adv).** The user shared a paper on Embedding Disruptiveness Measure. Two embeddings per paper (past p_i + future f_i) trained via directional random walks on citation graph; cosine distance is the disruptiveness score; nearest neighbors in future-vector space identify simultaneous discoveries. My suggested changes to our algorithm:

1. **Give each claim a pair of past/future embeddings.** This is a per-claim disruptiveness signal independent of the sheaf residual. The disagreement between EDM-disruptiveness and sheaf-residual is the interesting axis — it separates "scope-controversial but downstream-cohesive" claims (like Atlas's A_02) from genuinely disruptive ones.

2. **Future-vector centroids of Ideas → detect duplicate/simultaneous Ideas.** When two Ideas have near-identical future centroids, they may be the same underlying contribution from different angles. Quality-control mechanism for Idea consolidation that doesn't currently exist.

3. **EDM as the proposer for the next-Idea predictor.** Cluster the future-vector space; neighborhoods with high activity but no existing Idea-centroid are candidate sites for the next Idea. This makes the AlphaGo proposer concrete.

4. **Borrow their randomized-network null model** for validating Ideas — scramble claim-paper assignments preserving counts and check that real Ideas score very differently from scrambled ones.

The EDM paper also *validates* the "two directional vectors per entity" pattern that we've been using at multiple levels (claim x_in/x_out, evidence core/context).

## What to pick up next (the open queue)

In rough priority order:

1. **Implement EDM-style future-vector centroids for Ideas** (smallest engineering, big quality-control payoff). Each Idea gets a centroid; all-pairs cosine distance flags duplicate candidates.

2. **Per-claim past/future embeddings as a diagnostic column.** Add EDM-disruptiveness as a column in the optimizer's diagnostic output so we can see the EDM-vs-residual disagreement axis.

3. **Build the candidate-neighborhood proposer** for next-Idea prediction once the embedding index is running.

4. **Randomized null model** for Idea validation (easy, can be done in parallel).

5. **Possibly: extend Atlas pipeline to handle the question "what's the next paper that should appear?"** — concrete instantiation of the next-Idea predictor on a real corpus.

## File map (quick reference)

- Atlas corpus inputs: `/Users/chelsea/ErgoLabs/constellation/corpora/atlas/pdfs/` (20 PDFs)
- Atlas v0.5 outputs: `/Users/chelsea/ErgoLabs/constellation/corpora/atlas/v05/`
- Atlas results writeup: `/Users/chelsea/ErgoLabs/constellation/corpora/atlas/v05/results.md`
- Shumlak v0.5 outputs (earlier run): `/Users/chelsea/ErgoLabs/claude_cowork/restriction rewriting/v05/`
- Architecture doc: `/Users/chelsea/ErgoLabs/claude_cowork/restriction rewriting/ARCHITECTURE.md`
- Scripts (working / scratch): `/Users/chelsea/Library/Application Support/Claude/local-agent-mode-sessions/.../outputs/atlas_v05*.py` and `shumlak_v05*.py`

## How to actually resume

When you (the next session) start, the user will likely just dive into one of the threads above. Re-read this doc, glance at the `final_state.json` and `ideas_summary.json` for the Atlas corpus to refresh on the concrete data, and look at the most recent `atlas_v05_viz.py` for the current viz code. You don't need to re-run anything to be useful — the artifacts are settled.

If the user wants to start a new corpus, the pattern is the same three scripts: encoding → ideas-consolidation → viz. The optimizer and viz code is reusable; the encoding (CLAIMS, EVIDENCE, EDGES, CLAIM_REWRITES, EVIDENCE_CONTEXT_FILLINGS dicts) is per-corpus.

If the user is in conceptual mode (like the next-Idea predictor or the EDM-integration threads), match their register — prose, specific, not over-formatted. Don't reach for the file tools unless they ask for something to be built.
