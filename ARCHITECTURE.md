# Landscape Map: Architecture (v2, paper-as-stalk)

## What This Document Is

This is the consolidated architecture for the Landscape Map v2 pipeline. It supersedes the v1 pipeline (cluster-first-then-score-frustration) and replaces its cluster-level `stalk_schema` with a pair of schemas — `sheaf_schema` and `idea_schema` — that carry the hypothesis-space stalks, restriction maps, MAP section, and consolidated knowledge units respectively. The central architectural shift: clustering no longer happens before coherence-checking. Claims are first placed into a sheaf where each claim's hypothesis-space stalk contains the original statement plus evidence-faithful alternative rewrites; a Maximum-A-Posteriori global section is chosen over the sheaf to maximize coherence minus rewrite cost; then the surviving section is partitioned into Ideas (ε-states) that are the corpus's deliverable knowledge units.

## Scope

The Landscape Map is a research dashboard for literature exploration and gap-finding. Given a curated set of papers, it extracts their claims, records the argument DAG inside each paper, places claims into a sheaf over their comparability complex, selects the maximally-coherent global section under an evidence-faithfulness constraint, and consolidates the surviving claims into Ideas that carry consensus, frustration, and open-question metrics. The deliverable is a set of Idea documents plus a Sheaf document that records how they were derived.

**MVP scale:** 10–20 papers, curated by the researcher.

**Out of scope for MVP:** automated paper discovery, visualization UI beyond the current D3 HTML view, formal verification of claims, incremental processing, cross-corpus loop closure, Rashomon analysis over sections, causal-state partition computed from a predictive structure rather than hand-curated. These are all Phase 2 or later; see the Deferred section.

## Core Objects

Four object types carry the architecture.

**Paper.** The paper's semilattice coordinate (what it studied, at what model level, under what conditions) together with its internal argument DAG — every extracted claim flagged as `primary` or `supporting`, with `depends_on` edges recording which claim rests on which within the paper. See `paper_schema.json` (v0.5).

**Claim.** A simple directed relation extracted from a paper: X causes Y, X modulates Y, X contradicts Y, etc. Every claim carries two scopes (claimed vs evidenced) and an `evidence` object that records the evidence type, description, honest strengths, honest weaknesses, and optional structured quantitative content. The weaknesses are load-bearing: they justify the rewrites generated in the sheaf stage. See `claim_schema.json` (v0.5).

**Sheaf.** The corpus-level structural object. Records, for each claim, its hypothesis-space stalk (the original plus any evidence-faithful alternative readings); for each comparable pair of claims, the restriction map with a full variant-pair compatibility matrix; for the whole corpus, the MAP global section, residual H¹ (unresolved edges), and Penrose-frustration diagnostics. One sheaf per corpus run. See `sheaf_schema.json` (v0.1).

**Idea.** A consolidated knowledge unit extracted from a sheaf's MAP section — an ε-state in the corpus's ε-machine. Records the contributing claims (with their MAP-selected variants), the idea's own first-class scope (meet of contributing claims' evidenced scopes), consensus and frustration metrics, ε-transitions to other Ideas, and open questions tied to residual frustration. Each open question carries a `suggested_next_steps` array with typed entries (experiment / simulation / theoretical_development / further_extraction / literature_review / code_capability / instrumentation) so research-priority dashboards can group and rank work-to-do. One Idea per ε-state; typically 3–10 Ideas per corpus. See `idea_schema.json` (v0.2). The corpus-level ε-machine metrics are stored separately in `epsilon_machine_schema.json` (v0.1).

The Sheaf is where the structural work happens; the Idea is what a reader browses. The old v1 `Stalk` object has no direct successor — its three conflated roles (hypothesis space, pre-clustering, within-cluster coherence) now live in Sheaf.stalks, in the absence of pre-clustering, and in Idea.frustration respectively.

## Pipeline

Nine stages, run in sequence as a batch over the full paper set.

### 1. Extract paper + claims + argument DAG

**Input:** One paper (PDF or structured text).
**Output:** One `paper_schema` instance with populated `claims` DAG, N `claim_schema` instances.

One or more LLM calls per paper return:

- The paper's `observational_ground` (physical_system, phenomena_studied, parameter_regime, computational_framework, geometry, measurements) and `model_level`.
- A list of claims with cause / effect / direction / strength, `scope.claimed` and `scope.evidenced`, `evidence.{type, description, strengths, weaknesses, quantitative}`, and a `credibility_score`.
- The paper's internal argument DAG — each extracted claim tagged as `primary` or `supporting`, with `depends_on` edges listing the claims (within the same paper) it directly rests on.

The extractor is expected to populate `evidence.weaknesses` honestly — these drive the alternative-generation step downstream and a pipeline that routinely leaves this field empty produces weak sheaves.

Single-pass extraction at MVP. Median-of-runs is deferred until extraction instability is observed.

### 2. Tag claims with (semilattice, SNAG) coordinates

**Input:** All extracted claims.
**Output:** Each claim gains `_tags.semilattice` and `_tags.snag_nodes` (pipeline-internal, not schema fields).

Each claim is projected onto a fixed-dimension semilattice coordinate (mode, profile, framework, scope, wavelength, geometry — or the per-domain equivalent) and tagged with the SNAG node list drawn from its `cause`/`effect` mechanism variables. This structured projection replaces the free-form `scope.evidenced.conditions` prose with coordinates that support mechanical comparability checks in the next stage.

The tag ontology is domain-specific. The MVP pipeline accepts a hand-authored tag vocabulary per domain; a Phase 2 step would generate tags from a controlled vocabulary the LLM is given via few-shot.

### 3. Build the comparability complex

**Input:** All tagged claims.
**Output:** A graph whose 0-cells are claims and whose 1-cells are comparability edges — the nerve of the sheaf.

Two claims are an edge iff their semilattice coordinates meet (regime compatibility: modes compatible, frameworks in the same hierarchy branch, profiles specializable) AND their SNAG node lists overlap (mechanism compatibility). The first test filters for "these claims are about overlapping regimes"; the second tests "they talk about overlapping mechanism." Both are required.

The comparability complex replaces v1's cosine-similarity clustering. Crucially, this stage produces a graph, not a partition — a claim can appear on many comparability edges.

### 4. Generate hypothesis-space stalks

**Input:** The comparability complex; the claim schema's `evidence.strengths` and `evidence.weaknesses`.
**Output:** Per-claim stalks — for each claim, a list of variants containing the `#original` plus any evidence-faithful alternatives.

For each claim c and each neighbor d, test whether c's original statement restricts compatibly into d under the meet of their scopes. If not, generate one or more alternative variants of c that (a) preserve the strengths invoked by c's own evidence, (b) narrow the scope by invoking one or more of c's own stated weaknesses, and (c) restrict compatibly into d. Each variant is scored for `rewrite_distance` (how far from the original) and tagged with `targets` (which neighbor claim_ids triggered its generation), `evidence_strengths_invoked`, `evidence_weaknesses_invoked`, and an `evidence_faithful` boolean with a `faithfulness_note`.

Most claims' stalks remain singletons (just the `#original`) — only contested claims accumulate alternatives. A representative MVP run over 15 claims produced 3 variants for one claim; other corpora will vary.

### 5. Score the full compatibility cube

**Input:** The comparability complex with per-claim stalks.
**Output:** For each comparability edge, a full |stalk_a| × |stalk_b| matrix of compatibility scores.

One LLM call per variant pair. For each restriction-map edge, every cross product of variants is scored in [−1, +1] with a categorical `kind` (agreement / extension / refinement / qualification / boundary / contradiction) and a prose `explanation`. Storing the full cube (not just the pair MAP will eventually pick) lets the section be replayed at different λ rewrite penalties or under different solver rules without re-scoring — it's the load-bearing reason the sheaf JSON is large.

At MVP scale (~15 claims, ~10 edges, ~1–3 variants per contested claim), the cube has ~30–60 entries — easily LLM-judged in a single batch.

### 6. MAP global section

**Input:** The scored compatibility cube; the rewrite distances; a chosen λ.
**Output:** `map_section.selected` — one variant_id per claim — together with total score, coherence, rewrite cost, top-N alternative sections, and residual H¹.

Maximize coherence(σ) − λ × rewrite_cost(σ) over the product space Π F(c). At MVP scale the product space is small enough for exhaustive enumeration; at larger scale use loopy belief propagation on the factor graph, ILP for exact solutions, or simulated annealing for stochastic approximation. The solver identity and runtime are recorded in `map_section.solver`.

λ is a modeling knob — how aggressively to preserve originals vs rewrite for coherence. Stage 6 reports the canonical MAP section at the configured primary λ and also replays the solver across the configured sensitivity sweep (default λ ∈ {0.1, 0.2, 0.4, 0.8}). This identifies λ-stable selections (high confidence) and λ-sensitive ones (where MAP depends on the prior).

Residual H¹ is the set of edges whose compatibility score on the selected variant pair is ≤ 0 — obstructions to a global section that no rewrite could resolve.

### 7. Frustration diagnostics on the MAP section

**Input:** The selected section; the compatibility cube.
**Output:** `sheaf.frustration` — triangle count, signed count, Penrose count, ρ, explicit list of Penrose triangles.

For the selected variant pair on each edge, determine the sign. Enumerate all triangles in the comparability complex. Count triangles where `sign(e_ab) × sign(e_ac) × sign(e_bc) < 0` — these are Penrose triangles (structurally inconsistent three-claim configurations). ρ = n_penrose / n_signed_triangles is a discrete-H¹ surrogate.

This replaces v1's stalk-level frustration. In v2, frustration is measured on the sheaf's selected section rather than on a pre-imposed cluster. A healthy sheaf has ρ near 0 on the MAP section; ρ > 0.2 indicates structural tension the alternative-generation step couldn't resolve, which is itself useful diagnostic information.

### 8. Consolidate into Ideas (ε-machine partition)

**Input:** The MAP section.
**Output:** A set of Idea JSON files, one per ε-state.

Partition the surviving claims (in their MAP-selected variants) into ε-states. Two claims land in the same state iff they have the same predictive structure under the corpus's claim DAG — same SNAG-ancestors, same SNAG-descendants, same semilattice-projection onto the Idea's scope. At MVP scale this is done by hand-curation guided by the LLM; Phase 2 would compute causal states programmatically from a predictive model over the claim-claim transition structure.

For each ε-state, populate an Idea document: `label`, `description`, `contributing_claims` with their MAP variants, `scope` (meet of contributing claims' evidenced scopes — the Idea's first-class scope, with a `derivation_timestamp` so staleness can be detected), `consensus` block (papers represented, mean credibility, agreement_score, count of rewrites), `frustration` block (intra-Idea ρ), `transitions_out` and `transitions_in` to other Ideas (with kinds: tool_supply, empirical_phenomenon, tool_under_critique, trust_scaffolding, critique_of_framework, extension, specialization), and `open_questions` tied to residual edges or under-developed transition targets. Each open question decomposes into typed `suggested_next_steps` — experiments, simulations, theoretical developments, further extractions, literature reviews, or code-capability / instrumentation needs — with per-step descriptions, required capabilities, expected outcomes, effort estimates, and maturity flags (immediate vs tool-development-required vs depends-on-other-step).

After the Idea partition validates, compute `epsilon_machine.json`: the Idea state distribution, statistical complexity Cμ = H[state] in bits, normalized Cμ, effective state count 2^Cμ, and transition graph density. The MVP state distribution is claim occupancy per Idea; future versions can add weighted distributions without changing the core artifact.

Ideas are the corpus's deliverable outputs. A typical corpus of 10–20 papers produces 3–10 Ideas.

### 9. Write artifacts

**Output:** A directory tree:

```
corpus_root/
  run_config.json         (model, schema, prompt hash, and parameter snapshot)
  papers/*.json            (paper_schema v0.5)
  claims/*.json            (claim_schema v0.5)
  sheaf.json               (sheaf_schema v0.1, including λ sensitivity)
  ideas/*.json             (idea_schema v0.1)
  epsilon_machine.json     (epsilon_machine_schema v0.1)
  report.md                (human-readable synthesis)
  constellation.html       (interactive D3 view — optional)
  failures.json            (structured stage failures, when present)
  llm_cache/               (successful validated LLM JSON responses)
```

JSON files remain the source of truth during development; a graph-DB derived artifact is produced downstream if the visualizer needs one.

## Storage During MVP

JSON files on disk, one per paper / per claim plus one sheaf and N Ideas per corpus run. Every file carries a `$schema` version tag for migration. No database until the schemas and pipeline stabilize. A corpus-run directory is the atomic unit; re-running the pipeline produces a new directory rather than mutating an old one.

## Configuration Parameters (MVP Defaults)

| Parameter | Default | Purpose |
|---|---|---|
| `LLM_MODEL` | current general-purpose model | Extraction, comparability tagging, alternative generation, compatibility scoring, ε-state curation |
| `SEMILATTICE_TAG_DIMENSIONS` | domain-authored | Ontology for stage 2 tagging (6 dimensions typical) |
| `SNAG_OVERLAP_THRESHOLD` | 2 literal + 1 soft keyword | Minimum overlap to form a comparability edge |
| `LAMBDA_REWRITE` | 0.4 | MAP objective's rewrite-distance penalty coefficient |
| `LAMBDA_SENSITIVITY_VALUES` | [0.1, 0.2, 0.4, 0.8] | λ sweep values replayed after the primary MAP section |
| `MAP_SOLVER` | `enumerate` | Exhaustive at MVP scale; loopy_bp at larger |
| `MIN_CLAIMS_PER_IDEA` | 2 | Below this, an Idea is suspect — usually indicates mis-partition |
| `FRUSTRATION_WARNING_RHO` | 0.2 | ρ above this flags the Idea or sheaf for manual review |

All values are provisional and expected to shift once the pipeline has run against multiple real corpora.

## Deferred (Phase 2 and Beyond)

- **Automated tag ontology generation.** Derive the per-domain semilattice tag vocabulary from an LLM given few-shot examples, rather than hand-authoring it per corpus.
- **Causal-state partition from predictive structure.** Replace the hand-curated ε-state partition with a computed causal-state partition over a trained predictive model of claim-claim transitions. Requires enough corpus structure to estimate conditional distributions reliably — probably n > 50 claims.
- **Incremental sheaves.** Add a paper to an existing corpus without re-running the whole pipeline. Requires restricting recomputation to the affected part of the comparability complex.
- **Cross-corpus loop closure.** Detect when two independently-built Ideas (in different corpora) are really the same ε-state. The SLAM analogy is direct.
- **Formal verification.** Lean / AxiomProver for mathematically precise claims.
- **Active paper discovery.** An agent that selects candidate papers based on what the current Ideas collectively leave underdetermined. Feeds the pipeline's credibility_score and populates stalks with new alternatives.
- **Full interactive dashboard.** The current D3 artifact now surfaces Ideas, λ sensitivity, ε-machine metrics, and research-priority filters. A fuller UI could add persisted layouts, cross-run comparison, saved reviewer notes, and richer Idea-transition browsing.

Each item is additive; none requires rewriting the v2 pipeline.

## Theoretical Grounding (Condensed)

Three sources inspired the architecture; the v2 pipeline makes each more load-bearing than v1 did.

**Sheaf theory (Hansen-Ghrist, Robinson 2017).** The core semantics. Claims are local data; the comparability complex is the base space; per-claim hypothesis-space stalks carry the allowed local readings; restriction maps between comparable claims impose compatibility under the meet of their scopes; the MAP global section is the nearest-to-global-section the sheaf admits, and residual H¹ is the structural obstruction to a fully global one. v1 treated sheaf theory as distant inspiration; v2 implements the formal structure.

**Coherence-driven inference (Huntsman 2025).** The local/global split: LLMs score pairwise consistency (local), a global optimization selects a partition or section (global). v2's MAP step is exactly a coherence-driven inference — log-posterior maximization with a rewrite-distance prior. The paper-as-stalk refinement sharpens CDI by introducing the hypothesis-space stalk as the quantified unit: instead of voting over claims, MAP votes over variants of claims, with the rewrite-distance prior preventing free-for-all rewriting.

**Computational mechanics / ε-machines (Crutchfield-Shalizi).** The consolidation step. Once the MAP section is fixed, partition the surviving claims into causal states — equivalence classes of "same predictive structure over the claim DAG." Each ε-state becomes an Idea. The partition is the minimal sufficient statistic of the corpus's theoretical content, and statistical complexity Cμ measures its richness. At MVP scale the partition is hand-curated; computing it programmatically is a Phase 2 objective.

## Open Questions

1. **How are alternatives actually generated at scale?** MVP generates alternatives targeted at each failing neighbor restriction. Unclear whether this produces a bounded or explosive set of variants on larger corpora. A cap on |stalk| with a priority ranking (by rewrite distance ascending, then by number of neighbors satisfied descending) is the likely fallback.

2. **Should alternatives be generated before OR during MAP?** Currently all alternatives are generated in stage 4 and scored in stage 5 before MAP runs. A variant would defer alternative generation until MAP identifies which claims are under pressure — cheaper but harder to guarantee the MAP's optimality.

3. **How is the ε-state partition verified?** At MVP it's hand-curated and human-reviewed. Whether the partition is the unique or optimal one under any criterion is an open methodological question.

4. **λ-reporting discipline.** How wide should the default λ sweep be, and should reports flag a run as underdetermined when too many selections are λ-sensitive?

5. **What counts as a contested claim?** In stage 4, alternative generation is triggered by restriction failure. An edge case: a claim that has no failing neighbor under its original but would have one under a narrower scope — should speculative alternatives be generated? MVP says no; larger corpora may need to.
